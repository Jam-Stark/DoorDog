#!/usr/bin/env python3
"""Local v1.5.0 state. No model calls, daemon, network, or automatic expiry.

A cooperating-agent guardrail, not a security boundary against code that can
rewrite this file. SQLite must reside on one host's local filesystem.
"""
from __future__ import annotations
import argparse
import contextlib
import json
import re
import sqlite3
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any, Iterator

POLICY = {
    'default': ('gpt-6-sol', 'medium'),
    'explorer': ('gpt-6-luna', 'high'),
    'context_researcher': ('gpt-6-luna', 'high'),
    'memory_curator': ('gpt-6-luna', 'medium'),
    'runtime_qa': ('gpt-6-luna', 'high'),
    'worker': ('gpt-6-sol', 'medium'),
    'scope_planner': ('gpt-6-sol', 'medium'),
    'semantic_worker': ('gpt-6-sol', 'high'),
    'code_reviewer': ('gpt-6-sol', 'high'),
    'isaaclab_worker': ('gpt-6-sol', 'high'),
    'isaaclab_reviewer': ('gpt-6-sol', 'high'),
    'deep_researcher': ('gpt-6-astra', 'medium'),
}
MAX_ACTIVE = 5

def state_path(root: Path) -> Path:
    root = root.resolve()
    r = subprocess.run(['git', 'rev-parse', '--git-common-dir'], cwd=root,
                       text=True, capture_output=True, timeout=5)
    if r.returncode == 0:
        p = Path(r.stdout.strip())
        if not p.is_absolute():
            p = root / p
        return p.resolve() / 'jam-workflow-v150' / 'state.sqlite3'
    return root / '.ai/runtime/v150/state.sqlite3'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS actors (
 session TEXT PRIMARY KEY, team TEXT NOT NULL, is_main INTEGER NOT NULL,
 role TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS spawns (
 request TEXT PRIMARY KEY, team TEXT NOT NULL, actor TEXT NOT NULL,
 role TEXT NOT NULL, model TEXT NOT NULL, state TEXT NOT NULL,
 child TEXT UNIQUE, created REAL NOT NULL, evidence TEXT);
CREATE TABLE IF NOT EXISTS astra_slot (
 team TEXT PRIMARY KEY, request TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS peers (
 alias TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outbox (
 id TEXT PRIMARY KEY, sender TEXT NOT NULL, target TEXT NOT NULL,
 kind TEXT NOT NULL, task TEXT NOT NULL, stage TEXT NOT NULL,
 dedupe TEXT NOT NULL UNIQUE, payload TEXT NOT NULL,
 state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
 sent REAL, attempts INTEGER NOT NULL DEFAULT 0, evidence TEXT,
 channel TEXT);
CREATE TABLE IF NOT EXISTS audit (
 at REAL NOT NULL, event TEXT NOT NULL, data TEXT NOT NULL);
'''

@contextlib.contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA busy_timeout=5000')
        db.executescript(SCHEMA)
        path.chmod(0o600)
        db.execute('BEGIN IMMEDIATE')
        yield db
        db.execute('COMMIT')
    except BaseException:
        if db.in_transaction:
            db.execute('ROLLBACK')
        raise
    finally:
        db.close()


def audit_event(db: sqlite3.Connection, event: str, data: Any) -> None:
    db.execute('INSERT INTO audit VALUES (?,?,?)',
               (time.time(), event, json.dumps(data, ensure_ascii=False)))


def initialize_team(path: Path, session: str, team: str) -> None:
    if not session.strip() or not team.strip():
        raise ValueError('Actual session id and stable team id are required.')
    with transaction(path) as db:
        old = db.execute('SELECT * FROM actors WHERE session=?', (session,)).fetchone()
        if old and (old['team'] != team or not old['is_main']):
            raise ValueError('Cannot remap an existing actor or turn a child into a Main.')
        db.execute('INSERT OR IGNORE INTO actors VALUES (?,?,1,?)', (session, team, 'main'))
        audit_event(db, 'team-init', {'session': session, 'team': team})


def role_config(root: Path, role: str) -> dict[str, Any]:
    if role not in POLICY:
        raise ValueError(f'Unregistered role {role!r}; no implicit model fallback.')
    hits = []
    for p in (root / '.codex/agents').glob('*.toml'):
        d = tomllib.loads(p.read_text(encoding='utf-8'))
        if d.get('name') == role:
            hits.append(d)
    if len(hits) != 1:
        raise ValueError(f'Expected exactly one TOML for {role}.')
    d = hits[0]
    if (d.get('model'), d.get('model_reasoning_effort')) != POLICY[role]:
        raise ValueError(f'Role {role} violates the v1.5.0 model/effort allowlist.')
    w, c = d.get('model_context_window'), d.get('model_auto_compact_token_limit')
    cap = 65536 if POLICY[role][0] == 'gpt-6-luna' else 196608
    if type(w) is not int or type(c) is not int or not 0 < c < w <= cap:
        raise ValueError('Invalid explicit child context budget.')
    if d.get('model_auto_compact_token_limit_scope') != 'total':
        raise ValueError('Child compact scope must be total.')
    if d.get('agents', {}).get('enabled') is not False:
        raise ValueError('Child spawning must be disabled; no nested teams.')
    f = d.get('features', {})
    notes = f.get('context_management', {}).get('experimental_mode')
    if notes is not (role == 'deep_researcher'):
        raise ValueError('Wrong model-specific context strategy.')
    if 'use_history_notes_extension' in f.get('token_budget', {}):
        raise ValueError('Do not pin history_notes_extension in project roles.')
    return d


def tool_input(data: dict[str, Any]) -> dict[str, Any]:
    d = data.get('tool_input', data.get('toolInput', {}))
    if not isinstance(d, dict):
        raise ValueError('Unrecognized tool input; fail closed.')
    return d


def actor_id(data: dict[str, Any]) -> str:
    v = data.get('session_id')
    if not isinstance(v, str) or not v:
        raise ValueError('Missing actual hook session_id; do not fabricate one.')
    return v


def request_id(data: dict[str, Any]) -> str:
    v = data.get('tool_use_id')
    if not isinstance(v, str) or not v:
        raise ValueError('Missing stable tool_use_id; quota reservation cannot be safe.')
    return v


def reserve_spawn(root: Path, data: dict[str, Any], path: Path | None = None) -> dict:
    ti = tool_input(data)
    role = ti.get('agent_type') or ti.get('agentType') or 'default'
    if any(k in ti for k in ('model', 'model_reasoning_effort', 'reasoning_effort', 'effort')):
        raise ValueError('Explicit child model/effort overrides are forbidden; choose a role.')
    if ti.get('fork_turns') != 'none' or 'fork_context' in ti:
        raise ValueError('Verified MultiAgentV2 requires fork_turns="none", no fork_context.')
    cfg = role_config(root, role)
    actor, req = actor_id(data), request_id(data)
    with transaction(path or state_path(root)) as db:
        a = db.execute('SELECT * FROM actors WHERE session=?', (actor,)).fetchone()
        if not a or not a['is_main']:
            raise ValueError('Only a registered Main can spawn. Run workflow_state.py team-init first; children cannot spawn.')
        if db.execute('SELECT 1 FROM spawns WHERE request=?', (req,)).fetchone():
            raise ValueError('This spawn request is already reserved; reconcile rather than retry.')
        active = db.execute("SELECT count(*) FROM spawns WHERE team=? AND state IN ('reserved','active','uncertain')", (a['team'],)).fetchone()[0]
        if active >= MAX_ACTIVE:
            raise ValueError('Team active/reserved child limit reached; close/reconcile existing agents.')
        if role == 'deep_researcher':
            if db.execute('SELECT 1 FROM astra_slot WHERE team=?', (a['team'],)).fetchone():
                raise ValueError('Astra slot already allocated for this team. Reuse/resume that same child; no second identity.')
            db.execute('INSERT INTO astra_slot VALUES (?,?)', (a['team'], req))
        db.execute('INSERT INTO spawns VALUES (?,?,?,?,?,?,NULL,?,NULL)',
                   (req, a['team'], actor, role, cfg['model'], 'reserved', time.time()))
        audit_event(db, 'reserve', {'request': req, 'role': role, 'team': a['team']})
        return {'allow': True, 'request': req, 'role': role, 'team': a['team']}


def response_object(data: dict[str, Any]) -> dict:
    r = data.get('tool_response', data.get('toolResponse', {}))
    if isinstance(r, str):
        try:
            r = json.loads(r)
        except json.JSONDecodeError:
            return {}
    if not isinstance(r, dict):
        return {}
    # Deliberately narrow: unknown response shapes remain RESERVED/UNCERTAIN.
    return r


def complete_spawn(path: Path, data: dict) -> None:
    req = request_id(data)
    r = response_object(data)
    child = r.get('agent_id') or r.get('agentId') or r.get('thread_id')
    if not isinstance(child, str) or not child:
        child = None
    with transaction(path) as db:
        s = db.execute('SELECT * FROM spawns WHERE request=?', (req,)).fetchone()
        if not s:
            raise ValueError('Unreserved spawn reported; freeze team and inspect the hook path.')
        if s['child']:
            if child != s['child']:
                raise ValueError('Spawn result changed identity; manual reconciliation required.')
            return
        if child:
            db.execute('UPDATE spawns SET child=?,state=? WHERE request=?', (child, 'active', req))
            db.execute('INSERT INTO actors VALUES (?,?,0,?)', (child, s['team'], s['role']))
        else:
            db.execute('UPDATE spawns SET state=? WHERE request=?', ('uncertain', req))
        audit_event(db, 'spawn-result', {'request': req, 'child': child, 'state': 'active' if child else 'uncertain'})


def validate_resume(path: Path, data: dict) -> None:
    ti = tool_input(data)
    if any(k in ti for k in ('model', 'effort', 'reasoning_effort', 'model_reasoning_effort')):
        raise ValueError('Resume cannot change a child model or effort.')
    child = ti.get('id') or ti.get('agent_id')
    with transaction(path) as db:
        a = db.execute('SELECT * FROM actors WHERE session=?', (actor_id(data),)).fetchone()
        s = db.execute('SELECT * FROM spawns WHERE child=?', (child,)).fetchone()
        if not a or not a['is_main'] or not s or a['team'] != s['team']:
            raise ValueError('Resume requires an existing child of this registered Main/team.')
        active = db.execute("SELECT count(*) FROM spawns WHERE team=? AND state IN ('reserved','active','uncertain')", (a['team'],)).fetchone()[0]
        if s['state'] == 'closed' and active >= MAX_ACTIVE:
            raise ValueError('No free child slot for resume.')
        if s['state'] == 'closed':
            db.execute('UPDATE spawns SET state=? WHERE request=?', ('reserved', s['request']))


def close_child(path: Path, data: dict) -> None:
    ti, r = tool_input(data), response_object(data)
    child = ti.get('id') or ti.get('agent_id')
    # Never free on ambiguous/failed termination.
    if not (r.get('success') is True or r.get('status') == 'closed'):
        return
    with transaction(path) as db:
        a = db.execute('SELECT * FROM actors WHERE session=?', (actor_id(data),)).fetchone()
        s = db.execute('SELECT * FROM spawns WHERE child=?', (child,)).fetchone()
        if not a or not a['is_main'] or not s or a['team'] != s['team']:
            raise ValueError('Close result refers to an unowned child.')
        db.execute('UPDATE spawns SET state=? WHERE child=?', ('closed', child))
        # Astra identity slot intentionally survives close; only resume is allowed.
        audit_event(db, 'close', {'child': child})


def reconcile_failed(path: Path, req: str, evidence: Path) -> None:
    if not evidence.is_file() or not evidence.stat().st_size:
        raise ValueError('Nonempty evidence of NO child created is required.')
    evidence_text = evidence.read_text(encoding='utf-8')
    with transaction(path) as db:
        s = db.execute('SELECT * FROM spawns WHERE request=?', (req,)).fetchone()
        if not s or s['child'] or s['state'] not in ('reserved', 'uncertain'):
            raise ValueError('Only unbound reservations can be reconciled as never created.')
        db.execute('UPDATE spawns SET state=?,evidence=? WHERE request=?', ('failed', evidence_text, req))
        db.execute('DELETE FROM astra_slot WHERE request=?', (req,))
        audit_event(db, 'operator-reconciled-no-child', {'request': req, 'evidence_path': str(evidence.resolve()), 'evidence_text': evidence_text})


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('.'))
    sp = p.add_subparsers(dest='command', required=True)
    q = sp.add_parser('team-init'); q.add_argument('--session', required=True); q.add_argument('--team', required=True)
    sp.add_parser('status')
    q = sp.add_parser('reconcile-no-child'); q.add_argument('--request', required=True); q.add_argument('--evidence', type=Path, required=True)
    a = p.parse_args(); path = state_path(a.root)
    try:
        if a.command == 'team-init': initialize_team(path, a.session, a.team)
        elif a.command == 'reconcile-no-child': reconcile_failed(path, a.request, a.evidence)
        with transaction(path) as db:
            result = {t: [dict(r) for r in db.execute(f'SELECT * FROM {t}')] for t in ('actors','spawns','astra_slot')}
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(json.dumps({'error':str(exc)}, ensure_ascii=False)); return 2

if __name__ == '__main__':
    raise SystemExit(main())
