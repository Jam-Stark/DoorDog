#!/usr/bin/env python3
"""Prepare, launch and finalize durable tmux-backed long runs."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('.ai/runtime/runs')
PENDING=Path('.ai/runtime/pending-events')

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

def load(path: Path): return json.loads(path.read_text(encoding='utf-8'))

def save(path: Path,data): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def prepare(args):
    run=ROOT/args.name; run.mkdir(parents=True,exist_ok=False)
    receipt=run/'RUN_RECEIPT.json'; data={'name':args.name,'session':args.session or args.name,'command':args.command,'cwd':str(Path(args.cwd).resolve()),'output':args.output,'checkpoint':args.checkpoint,'eval_command':args.eval_command,'state':'DECLARED','created_at':now()}
    save(receipt,data); print(receipt); return 0

def launch(args):
    r=load(args.receipt); run=args.receipt.parent; exit_file=run/'exit_code.txt'; finished=run/'finished_at.txt'; log=Path(r['output']); log.parent.mkdir(parents=True,exist_ok=True)
    wrapper=run/'run.sh'; command=r['command']
    wrapper.write_text(f"#!/usr/bin/env bash\nset +e\ncd {shlex.quote(r['cwd'])}\n{command} > {shlex.quote(str(log))} 2>&1\nrc=$?\necho $rc > {shlex.quote(str(exit_file))}\ndate -Iseconds > {shlex.quote(str(finished))}\ntmux wait-for -S {shlex.quote('doordog-'+r['name'])}\nexit $rc\n",encoding='utf-8'); wrapper.chmod(0o755)
    subprocess.run(['tmux','new-session','-d','-s',r['session'],str(wrapper)],check=True)
    r['state']='RUNNING'; r['launched_at']=now(); save(args.receipt,r); print(f"LAUNCHED {r['session']}"); return 0

def status(args):
    r=load(args.receipt); exit_file=args.receipt.parent/'exit_code.txt'
    if exit_file.exists(): print(f"PROCESS_EXITED rc={exit_file.read_text().strip()}")
    else:
        live=subprocess.run(['tmux','has-session','-t',r['session']],capture_output=True).returncode==0
        print('RUNNING' if live else 'UNKNOWN_NO_EXIT_RECORD')
    return 0

def finalize(args):
    r=load(args.receipt); run=args.receipt.parent; exit_file=run/'exit_code.txt'
    if not exit_file.exists(): raise SystemExit('process has not written exit_code.txt')
    rc=int(exit_file.read_text().strip()); r['process_returncode']=rc; r['state']='PROCESS_EXITED'
    checkpoint=r.get('checkpoint')
    if rc!=0: r['state']='FAIL'; summary=f"process exited {rc}"
    elif checkpoint and not Path(checkpoint).exists(): r['state']='FAIL'; summary=f"expected checkpoint missing: {checkpoint}"
    else:
        if checkpoint: r['state']='CHECKPOINT_VALIDATED'
        if args.run_eval and r.get('eval_command'):
            r['state']='EVAL_RUNNING'; save(args.receipt,r)
            ev=subprocess.run(r['eval_command'],cwd=r['cwd'],shell=True)
            r['eval_returncode']=ev.returncode; r['state']='PASS' if ev.returncode==0 else 'FAIL'; summary=f"eval return code {ev.returncode}"
        else:
            r['state']='PASS'; summary='process completed and expected checkpoint condition satisfied'
    r['finalized_at']=now(); r['summary']=summary; save(args.receipt,r)
    PENDING.mkdir(parents=True,exist_ok=True); save(PENDING/f"{r['name']}.json",{'state':r['state'],'summary':summary,'receipt':str(args.receipt),'created_at':now()})
    print(f"{r['state']}: {summary}"); return 0 if r['state']=='PASS' else 2

def parser():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('prepare'); a.add_argument('--name',required=True); a.add_argument('--session'); a.add_argument('--command',required=True); a.add_argument('--cwd',default='.'); a.add_argument('--output',required=True); a.add_argument('--checkpoint'); a.add_argument('--eval-command'); a.set_defaults(func=prepare)
    l=sub.add_parser('launch'); l.add_argument('--receipt',type=Path,required=True); l.set_defaults(func=launch)
    s=sub.add_parser('status'); s.add_argument('--receipt',type=Path,required=True); s.set_defaults(func=status)
    f=sub.add_parser('finalize'); f.add_argument('--receipt',type=Path,required=True); f.add_argument('--run-eval',action='store_true'); f.set_defaults(func=finalize)
    return p

if __name__=='__main__':
    args=parser().parse_args(); raise SystemExit(args.func(args))
