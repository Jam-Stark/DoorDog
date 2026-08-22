#!/usr/bin/env python3
"""Safely apply the DoorDog A2_Piper Jam Coding Role v1.2.0 overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError as exc:
    raise SystemExit('Python 3.11+ is required (tomllib missing).') from exc

PACKAGE=Path(__file__).resolve().parent
OVERLAY=PACKAGE/'overlay'
IGNORE_BLOCK="""\n# BEGIN jam-coding-role-v1.2.0 runtime\n.ai/runtime/\n.ai/outgoing-artifacts/\n.ai/run-receipts/\n.ai/pending-events/\n# END jam-coding-role-v1.2.0 runtime\n"""
PROTECTED_FILES=[Path('.codex/config.toml')]
PROTECTED_DIRS=[Path('.codex/agents')]


def run(cmd:list[str],cwd:Path,check=True)->subprocess.CompletedProcess[str]:
    return subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,check=check)


def git_root(path:Path)->Path:
    try: return Path(run(['git','rev-parse','--show-toplevel'],path).stdout.strip()).resolve()
    except subprocess.CalledProcessError as exc: raise SystemExit(f'Not a Git worktree: {path}\n{exc.stderr}')


def git(path:Path,*args:str,check=True)->str:
    return run(['git',*args],path,check=check).stdout.strip()


def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def protected_snapshot(root:Path)->dict[str,str]:
    result={}
    for rel in PROTECTED_FILES:
        p=root/rel
        if p.exists(): result[rel.as_posix()]=digest(p)
    for rel in PROTECTED_DIRS:
        p=root/rel
        if p.exists():
            for f in sorted(p.rglob('*')):
                if f.is_file(): result[f.relative_to(root).as_posix()]=digest(f)
    return result


def in_progress(root:Path)->list[str]:
    gitdir=Path(git(root,'rev-parse','--git-dir'))
    if not gitdir.is_absolute(): gitdir=root/gitdir
    markers=['MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply']
    found=[m for m in markers if (gitdir/m).exists()]
    if git(root,'diff','--name-only','--diff-filter=U'): found.append('unmerged-files')
    return found


def identity_ok(root:Path)->bool:
    return bool(git(root,'config','user.name',check=False) and git(root,'config','user.email',check=False))


def commit_visible(root:Path,message:str,dry:bool)->str:
    status=git(root,'status','--porcelain=v1')
    if not status:
        return git(root,'rev-parse','HEAD')
    if dry:
        print(f'WOULD COMMIT: {message}')
        return git(root,'rev-parse','HEAD')
    if not identity_ok(root):
        raise SystemExit('Git user.name/user.email is not configured; configure local identity before migration.')
    run(['git','add','-A'],root)
    run(['git','commit','-m',message],root)
    return git(root,'rev-parse','HEAD')


def planned_files()->list[Path]:
    return [p.relative_to(OVERLAY) for p in sorted(OVERLAY.rglob('*')) if p.is_file()]


def copy_overlay(root:Path,dry:bool)->None:
    for rel in planned_files():
        if rel==Path('.codex/config.toml') or str(rel).startswith('.codex/agents/'):
            raise SystemExit(f'Package illegally contains protected path: {rel}')
        src=OVERLAY/rel; dst=root/rel
        print(f'{"WOULD WRITE" if dry else "WRITE"}: {rel}')
        if not dry:
            dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    gi=root/'.gitignore'
    current=gi.read_text(encoding='utf-8') if gi.exists() else ''
    if 'BEGIN jam-coding-role-v1.2.0 runtime' not in current:
        print(f'{"WOULD APPEND" if dry else "APPEND"}: .gitignore runtime block')
        if not dry: gi.write_text(current.rstrip()+IGNORE_BLOCK,encoding='utf-8')


def validate(root:Path,before:dict[str,str],dry:bool)->None:
    if dry: return
    after=protected_snapshot(root)
    if before!=after:
        changed=sorted(set(before)|set(after))
        details=[p for p in changed if before.get(p)!=after.get(p)]
        raise SystemExit('Protected Codex config/role paths changed: '+', '.join(details))
    for rel in [Path('opencode.json'),Path('.claude/settings.json'),Path('.codex/hooks.json')]:
        json.loads((root/rel).read_text(encoding='utf-8'))
    for rel in [Path('.ai/team-state.toml'),Path('.ai/artifact-targets.toml'),Path('.ai/artifact-sync.toml')]:
        with (root/rel).open('rb') as f: tomllib.load(f)
    scripts=sorted((root/'.ai/scripts').glob('*.py'))
    run([sys.executable,'-m','py_compile',*map(str,scripts)],root)
    run([sys.executable,'.ai/scripts/team_state.py','init'],root)
    snap=root/'.ai/runtime/team/team-snapshot.json'
    if not snap.is_file(): raise SystemExit('team-state snapshot was not created')
    ignored=run(['git','check-ignore','.ai/runtime/team/team-snapshot.json'],root,check=False)
    if ignored.returncode!=0: raise SystemExit('.ai/runtime is not ignored by Git')


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--repo',type=Path,required=True); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    root=git_root(args.repo)
    if root!=args.repo.expanduser().resolve(): print(f'NOTE: using Git root {root}')
    blockers=in_progress(root)
    if blockers: raise SystemExit('Repository has in-progress/conflicted Git state: '+', '.join(blockers))
    before=protected_snapshot(root)
    print('BRANCH:',git(root,'branch','--show-current') or '(detached)')
    print('HEAD:',git(root,'rev-parse','HEAD'))
    print('STATUS BEFORE:\n'+(git(root,'status','--short') or '(clean)'))
    pre=commit_visible(root,'chore: checkpoint before AI workflow v1.2.0 migration',args.dry_run)
    copy_overlay(root,args.dry_run)
    validate(root,before,args.dry_run)
    if args.dry_run:
        print(f'PRE_MIGRATION_COMMIT={pre}')
        print('DRY RUN COMPLETE; no files or commits were changed.')
        return 0
    migration=commit_visible(root,'chore(ai): adopt Jam Coding Role v1.2.0',False)
    print('STATUS AFTER:\n'+(git(root,'status','--short') or '(clean)'))
    print(f'PRE_MIGRATION_COMMIT={pre}')
    print(f'MIGRATION_COMMIT={migration}')
    print('PUSH=NOT_RUN')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
