#!/usr/bin/env python3
"""Optional tmux-backed long-run receipt and finalizer."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('.ai/runtime/runs')
PENDING = Path('.ai/runtime/pending-events')


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prepare(args: argparse.Namespace) -> int:
    run = ROOT / args.name
    run.mkdir(parents=True, exist_ok=False)
    receipt = run / 'RUN_RECEIPT.json'
    data = {'name': args.name, 'session': args.session or args.name, 'command': args.command, 'cwd': str(Path(args.cwd).resolve()), 'output': args.output, 'checkpoint': args.checkpoint, 'eval_command': args.eval_command, 'resources': args.resource or [], 'state': 'DECLARED', 'created_at': now()}
    save(receipt, data)
    print(receipt)
    return 0


def launch(args: argparse.Namespace) -> int:
    receipt = load(args.receipt); run = args.receipt.parent
    exit_file = run / 'exit_code.txt'; finished = run / 'finished_at.txt'; log = Path(receipt['output'])
    log.parent.mkdir(parents=True, exist_ok=True)
    wrapper = run / 'run.sh'
    wrapper.write_text(f"#!/usr/bin/env bash\nset +e\ncd {shlex.quote(receipt['cwd'])}\n{receipt['command']} > {shlex.quote(str(log))} 2>&1\nrc=$?\necho $rc > {shlex.quote(str(exit_file))}\ndate -Iseconds > {shlex.quote(str(finished))}\nexit $rc\n", encoding='utf-8')
    wrapper.chmod(0o755)
    subprocess.run(['tmux','new-session','-d','-s',receipt['session'],str(wrapper)], check=True)
    receipt['state'] = 'RUNNING'; receipt['launched_at'] = now(); save(args.receipt, receipt)
    print(f"LAUNCHED {receipt['session']}")
    return 0


def status(args: argparse.Namespace) -> int:
    receipt = load(args.receipt); exit_file = args.receipt.parent / 'exit_code.txt'
    if exit_file.exists():
        print(f"PROCESS_EXITED rc={exit_file.read_text().strip()}")
    else:
        live = subprocess.run(['tmux','has-session','-t',receipt['session']], capture_output=True).returncode == 0
        print('RUNNING' if live else 'UNKNOWN_NO_EXIT_RECORD')
    return 0


def finalize(args: argparse.Namespace) -> int:
    receipt = load(args.receipt); run = args.receipt.parent; exit_file = run / 'exit_code.txt'
    if not exit_file.exists():
        raise SystemExit('process has not written exit_code.txt')
    rc = int(exit_file.read_text().strip()); receipt['process_returncode'] = rc; receipt['state'] = 'PROCESS_EXITED'
    checkpoint = receipt.get('checkpoint')
    if rc != 0:
        receipt['state'] = 'FAIL'; summary = f'process exited {rc}'
    elif checkpoint and not Path(checkpoint).exists():
        receipt['state'] = 'FAIL'; summary = f'expected checkpoint missing: {checkpoint}'
    elif args.run_eval and receipt.get('eval_command'):
        if checkpoint: receipt['state'] = 'CHECKPOINT_VALIDATED'
        receipt['state'] = 'EVAL_RUNNING'; save(args.receipt, receipt)
        result = subprocess.run(receipt['eval_command'], cwd=receipt['cwd'], shell=True)
        receipt['eval_returncode'] = result.returncode; receipt['state'] = 'PASS' if result.returncode == 0 else 'FAIL'; summary = f'eval return code {result.returncode}'
    else:
        receipt['state'] = 'PASS'; summary = 'process completed and expected checkpoint condition satisfied'
    receipt['finalized_at'] = now(); receipt['summary'] = summary; save(args.receipt, receipt)
    PENDING.mkdir(parents=True, exist_ok=True)
    save(PENDING / f"{receipt['name']}.json", {'state': receipt['state'], 'summary': summary, 'receipt': str(args.receipt), 'created_at': now()})
    print(f"{receipt['state']}: {summary}")
    return 0 if receipt['state'] == 'PASS' else 2


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('prepare'); a.add_argument('--name', required=True); a.add_argument('--session'); a.add_argument('--command', required=True); a.add_argument('--cwd', default='.'); a.add_argument('--output', required=True); a.add_argument('--checkpoint'); a.add_argument('--eval-command'); a.add_argument('--resource', action='append'); a.set_defaults(func=prepare)
    l = sub.add_parser('launch'); l.add_argument('--receipt', type=Path, required=True); l.set_defaults(func=launch)
    s = sub.add_parser('status'); s.add_argument('--receipt', type=Path, required=True); s.set_defaults(func=status)
    f = sub.add_parser('finalize'); f.add_argument('--receipt', type=Path, required=True); f.add_argument('--run-eval', action='store_true'); f.set_defaults(func=finalize)
    return p


if __name__ == '__main__':
    args = parser().parse_args(); raise SystemExit(args.func(args))
