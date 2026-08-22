#!/usr/bin/env python3
"""Adaptive Codex hook: no-op unless DoorDog coordination state is active."""

from __future__ import annotations

import json
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
    out: dict = {'continue': True}
    if context:
        out['hookSpecificOutput'] = {'hookEventName': event, 'additionalContext': context}
    return emit(out)


def pre_allow(context: str | None = None) -> int:
    if context is None:
        return 0
    return emit({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'additionalContext': context,
        }
    })


def pre_deny(reason: str) -> int:
    return emit({
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': reason,
        }
    })


def root_from(data: dict) -> Path:
    cwd = Path(data.get('cwd') or '.').resolve()
    try:
        out = subprocess.check_output(['git','rev-parse','--show-toplevel'], cwd=cwd, text=True).strip()
        return Path(out)
    except Exception:
        return cwd


def marker(root: Path) -> Path:
    return root / '.ai/runtime/team/coordination.json'


def pre(data: dict) -> int:
    tool = data.get('tool_name') or data.get('toolName') or ''
    if tool != 'spawn_agent':
        return pre_allow()
    root = root_from(data)
    if not marker(root).is_file():
        return pre_allow()
    tool_input = data.get('tool_input') or data.get('toolInput') or {}
    task_name = tool_input.get('task_name') or tool_input.get('taskName') or ''
    role = tool_input.get('agent_type') or tool_input.get('agentType') or ''
    script = root / '.ai/scripts/team_state.py'
    result = subprocess.run([sys.executable, str(script), 'hook-check-spawn', '--task-name', str(task_name), '--role', str(role)], cwd=root, text=True, capture_output=True)
    text = (result.stdout or result.stderr).strip()
    try:
        verdict = json.loads(text)
    except json.JSONDecodeError:
        verdict = {'allow': False, 'reason': text or 'coordination validation failed'}
    if result.returncode or not verdict.get('allow'):
        return pre_deny(str(verdict.get('reason') or 'coordination validation failed'))
    reason = str(verdict.get('reason') or '')
    return pre_allow(reason if verdict.get('managed') else None)


def post(data: dict) -> int:
    root = root_from(data)
    if not marker(root).is_file():
        return allow('PostToolUse')
    event_dir = root / '.ai/runtime/team'
    event_dir.mkdir(parents=True, exist_ok=True)
    with (event_dir / 'hook-events.jsonl').open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(data, ensure_ascii=False, default=str) + '\n')
    return allow('PostToolUse')


def session_start(data: dict) -> int:
    root = root_from(data)
    pending = root / '.ai/runtime/pending-events'
    if not pending.is_dir():
        return allow('SessionStart')
    items: list[str] = []
    for path in sorted(pending.glob('*.json')):
        try:
            obj = json.loads(path.read_text(encoding='utf-8'))
            items.append(f"{path.name}: {obj.get('state','UNKNOWN')} - {obj.get('summary','')}")
        except Exception:
            items.append(f'{path.name}: unreadable pending event')
    return allow('SessionStart', 'Pending long-run events:\n' + '\n'.join(f'- {x}' for x in items[:20])) if items else allow('SessionStart')


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    data = payload()
    if mode == 'pre':
        return pre(data)
    if mode == 'post':
        return post(data)
    if mode == 'session-start':
        return session_start(data)
    return allow(data.get('hook_event_name') or data.get('hookEventName') or 'PostToolUse')


if __name__ == '__main__':
    raise SystemExit(main())
