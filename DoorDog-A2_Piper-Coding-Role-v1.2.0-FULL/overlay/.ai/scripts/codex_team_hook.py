#!/usr/bin/env python3
"""Codex hook adapter for DoorDog team-state validation and event recovery."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def emit(data: dict) -> int:
    print(json.dumps(data, ensure_ascii=False))
    return 0


def allow(event: str, context: str | None = None) -> int:
    out = {'continue': True}
    if context:
        out['hookSpecificOutput'] = {'hookEventName': event, 'additionalContext': context}
    return emit(out)


def deny(reason: str) -> int:
    return emit({
        'continue': True,
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': reason,
            'additionalContext': reason,
        },
    })


def root_from(data: dict) -> Path:
    cwd = Path(data.get('cwd') or '.').resolve()
    try:
        out = subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=cwd,text=True).strip()
        return Path(out)
    except Exception:
        return cwd


def pre(data: dict) -> int:
    tool = data.get('tool_name') or data.get('toolName') or ''
    if tool != 'spawn_agent':
        return allow('PreToolUse')
    tool_input = data.get('tool_input') or data.get('toolInput') or {}
    task_name = tool_input.get('task_name') or tool_input.get('taskName')
    if not task_name:
        return deny('DoorDog v1.2 requires a semantic task_name for spawn_agent.')
    root = root_from(data)
    script = root / '.ai/scripts/team_state.py'
    result = subprocess.run([sys.executable,str(script),'contract-validate','--task-name',str(task_name)],cwd=root,text=True,capture_output=True)
    if result.returncode:
        message=(result.stderr or result.stdout).strip() or 'task contract validation failed'
        return deny(message)
    return allow('PreToolUse', f'Team contract validated: {task_name}')


def post(data: dict) -> int:
    root=root_from(data)
    event_dir=root/'.ai/runtime/team'; event_dir.mkdir(parents=True,exist_ok=True)
    with (event_dir/'hook-events.jsonl').open('a',encoding='utf-8') as fh:
        fh.write(json.dumps(data,ensure_ascii=False,default=str)+'\n')
    return allow('PostToolUse')


def session_start(data: dict) -> int:
    root=root_from(data); pending=root/'.ai/runtime/pending-events'
    if not pending.is_dir():
        return allow('SessionStart')
    items=[]
    for path in sorted(pending.glob('*.json')):
        try:
            obj=json.loads(path.read_text(encoding='utf-8'))
            items.append(f"{path.name}: {obj.get('state','UNKNOWN')} - {obj.get('summary','')}")
        except Exception:
            items.append(f'{path.name}: unreadable pending event')
    if not items:
        return allow('SessionStart')
    return allow('SessionStart','Pending long-run events:\n'+'\n'.join(f'- {x}' for x in items[:20]))


def main() -> int:
    mode=sys.argv[1] if len(sys.argv)>1 else ''
    data=payload()
    if mode=='pre': return pre(data)
    if mode=='post': return post(data)
    if mode=='session-start': return session_start(data)
    return allow(data.get('hook_event_name') or data.get('hookEventName') or 'PostToolUse')

if __name__=='__main__':
    raise SystemExit(main())
