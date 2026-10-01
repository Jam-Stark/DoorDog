#!/usr/bin/env python3
"""v1.5.0 spawn gate wrapping, not replacing, existing coordination hooks.

Native hooks/schema MUST be smoke-tested locally. Unknown identity/result shapes
fail closed or retain reservations. No Stop loop, wake call, cleanup daemon, LLM.
"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from workflow_state import (reserve_spawn, complete_spawn, validate_resume,
                            close_child, state_path, transaction, tool_input, actor_id)

def emit(event: str, reason: str, deny: bool = False) -> None:
    body: dict[str, Any] = {'hookEventName': event}
    if deny:
        body.update(permissionDecision='deny', permissionDecisionReason=reason)
    else:
        body['additionalContext'] = reason
    print(json.dumps({'hookSpecificOutput': body}, ensure_ascii=False))

def root_for(data: dict) -> Path:
    cwd = data.get('cwd')
    if not isinstance(cwd, str) or not Path(cwd).is_dir():
        raise ValueError('Invalid hook cwd.')
    r = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=cwd, capture_output=True,
                       text=True, check=True, timeout=5)
    return Path(r.stdout.strip()).resolve()

def legacy(root: Path, mode: str, data: dict) -> dict:
    script = root / '.ai/scripts/codex_team_hook.py'
    if not script.exists():
        # No legacy script is required on a fresh, unmanaged generic project.
        if (root / '.ai/runtime/team/coordination.json').exists():
            raise ValueError('Active legacy coordination exists but its hook is missing.')
        return {}
    r = subprocess.run([sys.executable, str(script), mode], input=json.dumps(data),
                       text=True, capture_output=True, cwd=root, timeout=9)
    if r.returncode:
        raise ValueError('Legacy coordination/continuity hook failed: ' + r.stderr[-1000:])
    if not r.stdout.strip():
        return {}
    obj = json.loads(r.stdout)
    if not isinstance(obj, dict):
        raise ValueError('Unrecognized legacy hook response.')
    return obj

def resume_done(path: Path, data: dict) -> None:
    # A validated resume retains the original identity even on ambiguous output.
    child = tool_input(data).get('id') or tool_input(data).get('agent_id')
    with transaction(path) as db:
        db.execute("UPDATE spawns SET state='active' WHERE child=? AND state='reserved'", (child,))

def run(mode: str, data: dict, root: Path) -> None:
    tool = str(data.get('tool_name', data.get('toolName', ''))).split('.')[-1]
    if mode == 'pre':
        if tool == 'spawn_agent':
            # Run ALL existing checks before reserving the new cost slot.
            old_data = dict(data); old_data['tool_name'] = 'spawn_agent'
            result = legacy(root, 'pre', old_data)
            h = result.get('hookSpecificOutput', {})
            if h.get('permissionDecision') == 'deny':
                print(json.dumps(result)); return
            reserve_spawn(root, data)
            if h.get('additionalContext'):
                emit('PreToolUse', h['additionalContext'])
        elif tool == 'resume_agent':
            validate_resume(state_path(root), data)
        elif tool == 'close_agent':
            # Closing is not permission to close a different team or owner.
            ti = tool_input(data); child = ti.get('id') or ti.get('agent_id')
            with transaction(state_path(root)) as db:
                a = db.execute('SELECT * FROM actors WHERE session=?', (actor_id(data),)).fetchone()
                s = db.execute('SELECT * FROM spawns WHERE child=?', (child,)).fetchone()
                if not a or not a['is_main'] or not s or a['team'] != s['team']:
                    raise ValueError('Cannot close an unowned child.')
    elif mode == 'post':
        if tool == 'spawn_agent': complete_spawn(state_path(root), data)
        elif tool == 'close_agent': close_child(state_path(root), data)
        elif tool == 'resume_agent': resume_done(state_path(root), data)
        old = legacy(root, 'post', data)
        if old: print(json.dumps(old))
    elif mode in ('session-start', 'post-compact'):
        # Do not delegate legacy SessionStart: v1.3 auto-archived unread events.
        # Read metadata pointers only; preserve v1.4 durable-run continuity as well.
        lines = []
        for directory, legacy_event in (('.ai/runtime/run-events/pending', False),
                                        ('.ai/runtime/pending-events', True)):
            paths = sorted((root / directory).glob('*.json'))
            for path in paths[:3]:
                obj = json.loads(path.read_text())
                if not isinstance(obj, dict):
                    raise ValueError('Malformed durable event pointer.')
                label = 'LEGACY_UNASSESSED' if legacy_event else str(obj.get('process_state', 'UNKNOWN'))
                lines.append(f"Pending {path.relative_to(root)}: {label}; notification is not resolution or experimental acceptance.")
            if len(paths) > 3:
                lines.append(f'{len(paths)-3} additional events in {directory}; inspect only assigned work.')
        active = []
        for path in sorted((root / '.ai/runtime/runs').glob('*/STATUS.json')):
            obj = json.loads(path.read_text())
            if obj.get('process_state') in ('LAUNCHING', 'RUNNING') or obj.get('acceptance_state') == 'EVAL_RUNNING':
                active.append(str(path.relative_to(root)))
        lines.extend('Active run pointer: ' + p for p in active[:3])
        if (root / '.ai/runtime/handoff.md').is_file():
            lines.append('Runtime handoff pointer: .ai/runtime/handoff.md; not new authority.')
        lines.append('v1.5.0: preserve the existing team_id/Astra identity and outbox. Use workflow_state.py status and session_bus.py status only when resuming assigned work. No auto-ACK, fresh spawn, periodic model polling or pending-event deletion.')
        emit('SessionStart' if mode == 'session-start' else 'PostCompact', '\n'.join(lines))
    else:
        raise ValueError('Unknown hook mode.')

def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict): raise ValueError('Hook payload must be an object.')
        run(mode, data, root_for(data)); return 0
    except Exception as exc:  # Guard boundary: every unexpected error must deny, never silently allow.
        if mode == 'pre':
            emit('PreToolUse', 'v1.5.0 blocked: ' + str(exc), True); return 0
        print('codex_v150_hook: ' + str(exc), file=sys.stderr); return 1
if __name__ == '__main__':
    raise SystemExit(main())
