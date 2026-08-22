#!/usr/bin/env python3
"""DoorDog v1.2 first-class team ledger."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_DB = Path('.ai/runtime/team/team-state.sqlite3')
DEFAULT_SNAPSHOT = Path('.ai/runtime/team/team-snapshot.json')


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def split_csv(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        out.extend(item.strip() for item in value.split(',') if item.strip())
    return sorted(set(out))


def connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS tasks (
      task_name TEXT PRIMARY KEY,
      canonical_path TEXT,
      agent_id TEXT,
      role TEXT NOT NULL,
      revision TEXT,
      outcome TEXT,
      state TEXT NOT NULL DEFAULT 'declared',
      dependencies TEXT NOT NULL DEFAULT '[]',
      consumers TEXT NOT NULL DEFAULT '[]',
      read_set TEXT NOT NULL DEFAULT '[]',
      write_set TEXT NOT NULL DEFAULT '[]',
      resources TEXT NOT NULL DEFAULT '[]',
      acceptance TEXT,
      evidence TEXT,
      non_goals TEXT,
      latest_verdict TEXT,
      artifacts TEXT NOT NULL DEFAULT '[]',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS leases (
      resource TEXT PRIMARY KEY,
      task_name TEXT NOT NULL,
      kind TEXT NOT NULL,
      acquired_at TEXT NOT NULL,
      released_at TEXT
    );
    CREATE TABLE IF NOT EXISTS candidates (
      revision TEXT PRIMARY KEY,
      source_commit TEXT,
      paths TEXT NOT NULL,
      contracts TEXT NOT NULL,
      topology TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'frozen',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS verdicts (
      verdict_id TEXT PRIMARY KEY,
      task_name TEXT NOT NULL,
      revision TEXT NOT NULL,
      reviewer_role TEXT NOT NULL,
      status TEXT NOT NULL,
      paths TEXT NOT NULL,
      contracts TEXT NOT NULL,
      topology TEXT NOT NULL,
      evidence TEXT NOT NULL,
      validity TEXT NOT NULL DEFAULT 'VALID',
      reason TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      sender TEXT NOT NULL,
      receiver TEXT NOT NULL,
      message_type TEXT NOT NULL,
      revision TEXT,
      summary TEXT,
      material INTEGER NOT NULL DEFAULT 0,
      source_call_id TEXT
    );
    """)
    return con


def rows(con: sqlite3.Connection, table: str) -> list[dict]:
    result = []
    for row in con.execute(f'SELECT * FROM {table} ORDER BY rowid'):
        item = dict(row)
        for key in ('dependencies','consumers','read_set','write_set','resources','artifacts','paths','contracts','topology','evidence'):
            if key in item and isinstance(item[key], str):
                try:
                    item[key] = json.loads(item[key])
                except json.JSONDecodeError:
                    pass
        result.append(item)
    return result


def snapshot(con: sqlite3.Connection, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {table: rows(con, table) for table in ('tasks','leases','candidates','verdicts','messages')}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def role_group(role: str) -> str:
    value = role.lower()
    if 'research' in value or value in {'explore','librarian'}:
        return 'researcher'
    if 'planner' in value or value in {'prometheus','metis'}:
        return 'planner'
    if 'review' in value or value in {'oracle','momus'}:
        return 'reviewer'
    if 'runtime' in value or 'qa' in value or 'runner' in value:
        return 'runtime_qa'
    if 'memory' in value or 'curator' in value:
        return 'memory_curator'
    return 'writer'


def validate_task(row: sqlite3.Row | None) -> list[str]:
    if row is None:
        return ['task contract not found']
    group = role_group(row['role'])
    required = {
        'researcher': ('outcome','read_set'),
        'planner': ('outcome','acceptance'),
        'writer': ('outcome','revision','write_set','acceptance'),
        'reviewer': ('outcome','revision','read_set','acceptance'),
        'runtime_qa': ('outcome','revision','resources','acceptance'),
        'memory_curator': ('outcome','read_set','write_set'),
    }[group]
    missing = []
    for key in required:
        value = row[key]
        if key in {'read_set','write_set','resources'}:
            try:
                value = json.loads(value)
            except Exception:
                value = []
        if not value:
            missing.append(key)
    return missing


def cmd_init(args: argparse.Namespace) -> int:
    con = connect(args.db)
    snapshot(con, args.snapshot)
    print(f'INITIALIZED {args.db}')
    return 0


def cmd_contract_create(args: argparse.Namespace) -> int:
    con = connect(args.db)
    stamp = now()
    payload = (
        args.task_name, args.canonical_path, None, args.role, args.revision, args.outcome,
        'declared', json.dumps(split_csv(args.dependency)), json.dumps(split_csv(args.consumer)),
        json.dumps(split_csv(args.read_set)), json.dumps(split_csv(args.write_set)),
        json.dumps(split_csv(args.resource)), args.acceptance, args.evidence, args.non_goals,
        None, '[]', stamp, stamp,
    )
    con.execute("""INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(task_name) DO UPDATE SET
        canonical_path=excluded.canonical_path, role=excluded.role, revision=excluded.revision,
        outcome=excluded.outcome, dependencies=excluded.dependencies, consumers=excluded.consumers,
        read_set=excluded.read_set, write_set=excluded.write_set, resources=excluded.resources,
        acceptance=excluded.acceptance, evidence=excluded.evidence, non_goals=excluded.non_goals,
        updated_at=excluded.updated_at""", payload)
    con.commit()
    snapshot(con, args.snapshot)
    print(f'CONTRACT SAVED {args.task_name}')
    return 0


def cmd_contract_validate(args: argparse.Namespace) -> int:
    con = connect(args.db)
    row = con.execute('SELECT * FROM tasks WHERE task_name=?', (args.task_name,)).fetchone()
    missing = validate_task(row)
    if missing:
        print(f'INVALID {args.task_name}: {", ".join(missing)}', file=sys.stderr)
        return 2
    print(f'VALID {args.task_name}')
    return 0


def cmd_task_state(args: argparse.Namespace) -> int:
    con = connect(args.db)
    cur = con.execute('UPDATE tasks SET state=?, agent_id=COALESCE(?,agent_id), canonical_path=COALESCE(?,canonical_path), updated_at=? WHERE task_name=?',
                      (args.state,args.agent_id,args.canonical_path,now(),args.task_name))
    if cur.rowcount != 1:
        raise SystemExit(f'Unknown task: {args.task_name}')
    con.commit(); snapshot(con,args.snapshot)
    print(f'STATE {args.task_name}={args.state}')
    return 0


def cmd_lease_acquire(args: argparse.Namespace) -> int:
    con = connect(args.db)
    for resource in split_csv(args.resource):
        row = con.execute('SELECT * FROM leases WHERE resource=? AND released_at IS NULL',(resource,)).fetchone()
        if row and row['task_name'] != args.task_name:
            print(f'LEASE CONFLICT {resource}: owned by {row["task_name"]}', file=sys.stderr)
            return 3
    stamp=now()
    for resource in split_csv(args.resource):
        con.execute('INSERT INTO leases(resource,task_name,kind,acquired_at,released_at) VALUES(?,?,?,?,NULL) ON CONFLICT(resource) DO UPDATE SET task_name=excluded.task_name,kind=excluded.kind,acquired_at=excluded.acquired_at,released_at=NULL',
                    (resource,args.task_name,args.kind,stamp))
    con.commit(); snapshot(con,args.snapshot)
    print(f'LEASED {args.task_name}: {", ".join(split_csv(args.resource))}')
    return 0


def cmd_lease_release(args: argparse.Namespace) -> int:
    con=connect(args.db)
    con.execute('UPDATE leases SET released_at=? WHERE task_name=? AND released_at IS NULL',(now(),args.task_name))
    con.commit(); snapshot(con,args.snapshot)
    print(f'RELEASED {args.task_name}')
    return 0


def cmd_freeze(args: argparse.Namespace) -> int:
    con=connect(args.db)
    con.execute('INSERT OR REPLACE INTO candidates VALUES(?,?,?,?,?,?,?)',(
        args.revision,args.source_commit,json.dumps(split_csv(args.path)),json.dumps(split_csv(args.contract)),
        json.dumps(split_csv(args.topology)),'frozen',now()))
    con.commit(); snapshot(con,args.snapshot)
    print(f'FROZEN {args.revision}')
    return 0


def cmd_verdict(args: argparse.Namespace) -> int:
    con=connect(args.db); stamp=now()
    con.execute('INSERT OR REPLACE INTO verdicts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        args.verdict_id,args.task_name,args.revision,args.reviewer_role,args.status,
        json.dumps(split_csv(args.path)),json.dumps(split_csv(args.contract)),json.dumps(split_csv(args.topology)),
        json.dumps(split_csv(args.evidence_item)),'VALID',None,stamp,stamp))
    con.execute('UPDATE tasks SET latest_verdict=?,updated_at=? WHERE task_name=?',(args.status,stamp,args.task_name))
    con.commit(); snapshot(con,args.snapshot)
    print(f'VERDICT {args.verdict_id}={args.status}')
    return 0


def intersects(bound: list[str], changed: list[str]) -> bool:
    for a in bound:
        for b in changed:
            if a == b or a.startswith(b.rstrip('/') + '/') or b.startswith(a.rstrip('/') + '/'):
                return True
    return False


def cmd_invalidate(args: argparse.Namespace) -> int:
    con=connect(args.db)
    cp,cc,ct=split_csv(args.changed_path),split_csv(args.changed_contract),split_csv(args.changed_topology)
    for row in con.execute('SELECT * FROM verdicts WHERE revision=?',(args.revision,)):
        bp,bc,bt=json.loads(row['paths']),json.loads(row['contracts']),json.loads(row['topology'])
        if intersects(bp,cp) or set(bc)&set(cc) or set(bt)&set(ct):
            validity,reason='INVALID','bound dependency changed'
        elif args.explicitly_disjoint:
            validity,reason='RETAINED','explicitly disjoint change'
        else:
            validity,reason='REVIEW_REQUIRED','relationship not proven disjoint'
        con.execute('UPDATE verdicts SET validity=?,reason=?,updated_at=? WHERE verdict_id=?',(validity,reason,now(),row['verdict_id']))
        print(f'{row["verdict_id"]}: {validity}')
    con.commit(); snapshot(con,args.snapshot)
    return 0


def cmd_message(args: argparse.Namespace) -> int:
    con=connect(args.db)
    con.execute('INSERT INTO messages(timestamp,sender,receiver,message_type,revision,summary,material,source_call_id) VALUES(?,?,?,?,?,?,?,?)',
                (now(),args.sender,args.receiver,args.message_type,args.revision,args.summary,int(args.material),args.source_call_id))
    con.commit(); snapshot(con,args.snapshot)
    print('MESSAGE RECORDED')
    return 0


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=DEFAULT_DB)
    p.add_argument('--snapshot',type=Path,default=DEFAULT_SNAPSHOT)
    sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('init').set_defaults(func=cmd_init)

    c=sub.add_parser('contract-create'); c.add_argument('--task-name',required=True); c.add_argument('--role',required=True)
    c.add_argument('--canonical-path'); c.add_argument('--revision'); c.add_argument('--outcome',required=True)
    c.add_argument('--dependency',action='append'); c.add_argument('--consumer',action='append'); c.add_argument('--read-set',action='append')
    c.add_argument('--write-set',action='append'); c.add_argument('--resource',action='append'); c.add_argument('--acceptance')
    c.add_argument('--evidence'); c.add_argument('--non-goals'); c.set_defaults(func=cmd_contract_create)
    v=sub.add_parser('contract-validate'); v.add_argument('--task-name',required=True); v.set_defaults(func=cmd_contract_validate)
    s=sub.add_parser('task-state'); s.add_argument('--task-name',required=True); s.add_argument('--state',required=True); s.add_argument('--agent-id'); s.add_argument('--canonical-path'); s.set_defaults(func=cmd_task_state)
    la=sub.add_parser('lease-acquire'); la.add_argument('--task-name',required=True); la.add_argument('--resource',action='append',required=True); la.add_argument('--kind',default='exclusive'); la.set_defaults(func=cmd_lease_acquire)
    lr=sub.add_parser('lease-release'); lr.add_argument('--task-name',required=True); lr.set_defaults(func=cmd_lease_release)
    f=sub.add_parser('freeze-create'); f.add_argument('--revision',required=True); f.add_argument('--source-commit'); f.add_argument('--path',action='append',required=True); f.add_argument('--contract',action='append'); f.add_argument('--topology',action='append'); f.set_defaults(func=cmd_freeze)
    ve=sub.add_parser('verdict-add'); ve.add_argument('--verdict-id',required=True); ve.add_argument('--task-name',required=True); ve.add_argument('--revision',required=True); ve.add_argument('--reviewer-role',required=True); ve.add_argument('--status',required=True); ve.add_argument('--path',action='append'); ve.add_argument('--contract',action='append'); ve.add_argument('--topology',action='append'); ve.add_argument('--evidence-item',action='append'); ve.set_defaults(func=cmd_verdict)
    i=sub.add_parser('invalidate'); i.add_argument('--revision',required=True); i.add_argument('--changed-path',action='append'); i.add_argument('--changed-contract',action='append'); i.add_argument('--changed-topology',action='append'); i.add_argument('--explicitly-disjoint',action='store_true'); i.set_defaults(func=cmd_invalidate)
    m=sub.add_parser('message-record'); m.add_argument('--sender',required=True); m.add_argument('--receiver',required=True); m.add_argument('--message-type',choices=['PEER_FINDING','PEER_REQUEST','AUTHORITY_REQUEST'],required=True); m.add_argument('--revision'); m.add_argument('--summary'); m.add_argument('--material',action='store_true'); m.add_argument('--source-call-id'); m.set_defaults(func=cmd_message)
    snap=sub.add_parser('snapshot'); snap.set_defaults(func=lambda a:(snapshot(connect(a.db),a.snapshot),print(f'SNAPSHOT {a.snapshot}'),0)[2])
    return p


def main() -> int:
    args=parser().parse_args()
    return args.func(args)

if __name__=='__main__':
    raise SystemExit(main())
