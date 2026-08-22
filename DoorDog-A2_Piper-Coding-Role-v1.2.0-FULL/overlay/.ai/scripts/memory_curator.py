#!/usr/bin/env python3
"""Create, review, promote and reindex DoorDog durable-memory candidates."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

INBOX=Path('.ai/runtime/memory-inbox')
INDEX=Path('memory/_index.json')


def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def safe_route(value: str) -> Path:
    route=Path(value)
    if route.is_absolute() or '..' in route.parts:
        raise SystemExit('target route must be repository-relative and cannot contain ..')
    return route


def add(args):
    INBOX.mkdir(parents=True,exist_ok=True)
    cid=f"mem-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    data={'id':cid,'created_at':now(),'title':args.title,'scope':args.scope,'status':'candidate','source':args.source,'evidence':args.evidence,'suggested_action':args.action,'target_route':args.target_route,'body':args.body}
    path=INBOX/f'{cid}.json'; path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(path); return 0


def list_candidates(args):
    if not INBOX.exists(): return 0
    for path in sorted(INBOX.glob('*.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        print(f"{data['id']}\t{data.get('status')}\t{data.get('suggested_action')}\t{data.get('target_route')}\t{data.get('title')}")
    return 0


def reindex(_args=None):
    entries=[]
    root=Path('memory')
    if root.exists():
        for path in sorted(root.rglob('description.md')):
            text=path.read_text(encoding='utf-8',errors='replace')
            status='active'; title=path.parent.name
            m=re.search(r'^status:\s*(.+)$',text,re.M); status=m.group(1).strip() if m else status
            m=re.search(r'^name:\s*(.+)$',text,re.M); title=m.group(1).strip() if m else title
            entries.append({'path':path.as_posix(),'route':path.parent.as_posix(),'title':title,'status':status})
    INDEX.parent.mkdir(parents=True,exist_ok=True); INDEX.write_text(json.dumps({'generated_at':now(),'entries':entries},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(INDEX); return 0


def promote(args):
    if not args.yes: raise SystemExit('promotion is a canonical repository write; pass --yes')
    path=INBOX/f'{args.candidate}.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    route=safe_route(data['target_route']); target=route/'description.md'; target.parent.mkdir(parents=True,exist_ok=True)
    section=f"\n## {data['title']}\n\n- Last verified: {now()}\n- Source: {data.get('source') or 'not recorded'}\n- Evidence: {data.get('evidence') or 'not recorded'}\n\n{data.get('body','').strip()}\n"
    if target.exists():
        target.write_text(target.read_text(encoding='utf-8').rstrip()+section,encoding='utf-8')
    else:
        front=f"---\nname: {data['title']}\nstatus: active\nscope: {data.get('scope','')}\nlast_verified: {now()}\n---\n"
        target.write_text(front+section,encoding='utf-8')
    data['status']='promoted'; data['promoted_at']=now(); data['promoted_to']=target.as_posix(); path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    reindex(); print(target); return 0


def parser():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('candidate-add'); a.add_argument('--title',required=True); a.add_argument('--scope',default=''); a.add_argument('--source',default=''); a.add_argument('--evidence',default=''); a.add_argument('--action',choices=['create','append','move','split','merge','supersede','retire'],required=True); a.add_argument('--target-route',required=True); a.add_argument('--body',required=True); a.set_defaults(func=add)
    l=sub.add_parser('candidate-list'); l.set_defaults(func=list_candidates)
    pr=sub.add_parser('promote'); pr.add_argument('--candidate',required=True); pr.add_argument('--yes',action='store_true'); pr.set_defaults(func=promote)
    r=sub.add_parser('reindex'); r.set_defaults(func=reindex)
    return p

if __name__=='__main__':
    args=parser().parse_args(); raise SystemExit(args.func(args))
