#!/usr/bin/env python3
"""Linux-only opt-in ownership wrapper for SHORT-LIVED tools / stdio MCP.

Never wrap training, shared services, the Codex App, or the shared app-server.
Child stdout is untouched. Diagnostics go to stderr; a receipt records ownership.
Cleanup uses pidfds plus an inherited random token, uid, boot ID and start ticks.
Unregistered legacy processes and descendants that scrub the token are NOT killed.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid
from typing import Any

TAG = 'JAM_V150_OWNED_TOOL'

def require_linux() -> None:
    if sys.platform != 'linux' or not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('This guard requires Linux with pidfd support. Other OS backends are not implemented.')

def identity(pid: int) -> dict | None:
    try:
        p = Path('/proc') / str(pid)
        fields = (p / 'stat').read_text().rsplit(') ', 1)[1].split()
        if fields[0] == 'Z':
            return None
        return {'pid': pid, 'start_ticks': int(fields[19]), 'uid': p.stat().st_uid,
                'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    except (OSError, ValueError, IndexError):
        return None

def same_process(record: dict | None) -> bool:
    return bool(record and identity(record['pid']) == record)

def has_tag(pid: int, token: str) -> bool:
    try:
        expected = f'{TAG}={token}'.encode()
        return expected in (Path('/proc') / str(pid) / 'environ').read_bytes().split(b'\0')
    except OSError:
        return False

def owned(token: str) -> list[dict]:
    result = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        record = identity(int(p.name))
        if record and record['uid'] == os.getuid() and has_tag(record['pid'], token):
            result.append(record)
    return result

def send_owned(record: dict, token: str, sig: int) -> bool:
    fd = None
    try:
        fd = os.pidfd_open(record['pid'])
        # Revalidate AFTER opening the stable process handle to defeat PID reuse.
        if identity(record['pid']) != record or not has_tag(record['pid'], token):
            return False
        signal.pidfd_send_signal(fd, sig)
        return True
    except (ProcessLookupError, PermissionError, FileNotFoundError):
        return False
    finally:
        if fd is not None:
            os.close(fd)

def cleanup(token: str, grace: float) -> list[dict]:
    for record in owned(token):
        send_owned(record, token, signal.SIGTERM)
    until = time.monotonic() + grace
    while time.monotonic() < until and owned(token):
        time.sleep(0.05)
    # Bounded rescans catch a late descendant; this is OS waiting, not model polling.
    for _ in range(3):
        rest = owned(token)
        if not rest:
            return []
        for record in rest:
            send_owned(record, token, signal.SIGKILL)
        time.sleep(0.05)
    return owned(token)

def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x', encoding='utf-8') as f:
        os.chmod(temp, 0o600)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)

def run(command: list[str], receipt: Path, owner_pid: int, grace: float, stdio: bool, *, owner_session: str | None = None, task_id: str | None = None) -> int:
    require_linux()
    if bool(owner_session) != bool(task_id):
        raise ValueError('Provide both owner_session and task_id, or neither.')
    if receipt.exists():
        raise ValueError('Receipt already exists; never overwrite ownership of an old tool.')
    owner = identity(owner_pid)
    if not owner or owner['uid'] != os.getuid():
        raise ValueError('A live same-user owner PID must be explicitly identifiable.')
    receipt.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(receipt, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)  # Atomic reservation: concurrent launches cannot reuse a receipt.
    token = uuid.uuid4().hex
    env = os.environ.copy(); env[TAG] = token
    record: dict[str, Any] = {'version': '1.5.0', 'scope': 'ephemeral-tool', 'owner': owner,
        'token': token, 'wrapper': identity(os.getpid()), 'created': time.time(),
        'executable_name': Path(command[0]).name,
        'status': 'STARTING', 'stdio': stdio, 'owner_session': owner_session, 'task_id': task_id}
    write_json(receipt, record)
    stopped = threading.Event(); eof = threading.Event()
    proc: subprocess.Popen | None = None
    previous = {}
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, lambda _s, _f: stopped.set())
        proc = subprocess.Popen(command, stdin=subprocess.PIPE if stdio else None,
                                env=env, start_new_session=True)
        record.update(status='RUNNING', child=identity(proc.pid)); write_json(receipt, record)
        if stdio:
            def forward() -> None:
                try:
                    while True:
                        # Unbuffered fd read avoids holding Python's stdin lock at shutdown.
                        block = os.read(sys.stdin.fileno(), 65536)
                        if not block: break
                        if proc is None or proc.stdin is None: break
                        proc.stdin.write(block); proc.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
                finally:
                    if proc is not None and proc.stdin:
                        try: proc.stdin.close()
                        except OSError: pass
                    eof.set()
            threading.Thread(target=forward, daemon=True).start()
        reason = 'child-exit'
        eof_at: float | None = None
        while proc.poll() is None:
            if stopped.is_set(): reason = 'wrapper-cancel'; break
            if not same_process(owner): reason = 'owner-exit'; break
            if stdio and eof.is_set():
                if eof_at is None: eof_at = time.monotonic()
                # First give the server a chance to exit on stdin EOF.
                if time.monotonic() - eof_at >= grace:
                    reason = 'stdio-eof'; break
            time.sleep(0.1)
        rest = cleanup(token, grace)
        try: code = proc.wait(timeout=max(grace, 1))
        except subprocess.TimeoutExpired: code = 125
        record.update(status='CLEAN' if not rest else 'REMAINDERS', reason=reason,
                      exit_code=code, remaining=rest, completed=time.time())
        write_json(receipt, record)
        return code if code >= 0 else 128 - code
    except BaseException as exc:
        rest = cleanup(token, grace)
        if proc is not None:
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired: pass
        record.update(status='ERROR', error=str(exc), remaining=rest, completed=time.time())
        write_json(receipt, record)
        raise
    finally:
        for sig, handler in previous.items(): signal.signal(sig, handler)

def reap(receipt: Path, apply: bool, grace: float) -> dict:
    require_linux()
    if receipt.stat().st_uid != os.getuid() or receipt.stat().st_mode & 0o077:
        raise ValueError('Receipt must be owned by this uid and private (0600).')
    d = json.loads(receipt.read_text())
    if d.get('scope') != 'ephemeral-tool' or d.get('version') != '1.5.0':
        raise ValueError('Not an owned ephemeral-tool receipt.')
    if same_process(d.get('owner')) or same_process(d.get('wrapper')):
        raise ValueError('Live owner/wrapper: cancel through that owner, not the orphan reaper.')
    before = owned(d['token'])
    after = cleanup(d['token'], grace) if apply else before
    return {'applied': apply, 'owned_before': before, 'remaining': after,
            'unregistered_processes': 'NOT_TOUCHED'}

def finish(receipt: Path, owner_session: str, task_id: str, apply: bool, grace: float) -> dict:
    """Explicit logical-task teardown, even when the shared host PID stays alive."""
    require_linux()
    if receipt.stat().st_uid != os.getuid() or receipt.stat().st_mode & 0o077:
        raise ValueError('A private same-user receipt is required.')
    d = json.loads(receipt.read_text())
    if d.get('scope') != 'ephemeral-tool' or d.get('version') != '1.5.0':
        raise ValueError('Not an ephemeral-tool receipt.')
    if not owner_session or not task_id or d.get('owner_session') != owner_session or d.get('task_id') != task_id:
        raise ValueError('Logical session/task does not own this tool receipt.')
    result = {'apply': apply, 'owner_session': owner_session, 'task_id': task_id,
              'owned_before': owned(d['token']), 'shared_host': 'NOT_SIGNALED'}
    if not apply:
        return result
    wrapper = d.get('wrapper')
    if d.get('status') in ('STARTING', 'RUNNING') and same_process(wrapper):
        if wrapper['pid'] == os.getpid():
            raise ValueError('Do not ask a wrapper to signal itself through finish.')
        fd = os.pidfd_open(wrapper['pid'])
        try:
            if same_process(wrapper):
                signal.pidfd_send_signal(fd, signal.SIGTERM)
        except ProcessLookupError:
            pass
        finally:
            os.close(fd)
        until = time.monotonic() + 2 * grace + 2
        while same_process(wrapper) and time.monotonic() < until:
            time.sleep(.05)
    # Task completion is explicit; only its tagged descendants are eligible.
    result['remaining'] = cleanup(d['token'], grace)
    result['wrapper_still_live'] = bool(d.get('status') in ('STARTING', 'RUNNING') and same_process(wrapper))
    return result

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    q = sub.add_parser('run'); q.add_argument('--receipt', type=Path, required=True)
    q.add_argument('--owner-pid', type=int, default=os.getppid()); q.add_argument('--grace-seconds', type=float, default=2)
    q.add_argument('--stdio', action='store_true'); q.add_argument('--owner-session'); q.add_argument('--task-id'); q.add_argument('command', nargs=argparse.REMAINDER)
    q = sub.add_parser('reap'); q.add_argument('--receipt', type=Path, required=True)
    q.add_argument('--apply', action='store_true'); q.add_argument('--grace-seconds', type=float, default=2)
    q = sub.add_parser('finish'); q.add_argument('--receipt', type=Path, required=True)
    q.add_argument('--owner-session', required=True); q.add_argument('--task-id', required=True)
    q.add_argument('--apply', action='store_true'); q.add_argument('--grace-seconds', type=float, default=2)
    a = p.parse_args()
    try:
        if a.grace_seconds < 0 or a.grace_seconds > 30: raise ValueError('Grace must be 0..30 seconds.')
        if a.mode == 'finish':
            print(json.dumps(finish(a.receipt, a.owner_session, a.task_id, a.apply, a.grace_seconds), indent=2)); return 0
        if a.mode == 'reap':
            print(json.dumps(reap(a.receipt, a.apply, a.grace_seconds), indent=2)); return 0
        command = a.command[1:] if a.command[:1] == ['--'] else a.command
        if not command: raise ValueError('An exact authorized tool command is required.')
        return run(command, a.receipt.resolve(), a.owner_pid, a.grace_seconds, a.stdio, owner_session=a.owner_session, task_id=a.task_id)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('tool_guard: ' + str(exc), file=sys.stderr); return 2
if __name__ == '__main__':
    raise SystemExit(main())
