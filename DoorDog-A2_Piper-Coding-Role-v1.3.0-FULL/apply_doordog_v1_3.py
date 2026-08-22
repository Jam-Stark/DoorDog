#!/usr/bin/env python3
"""Apply the DoorDog A2_Piper Jam Coding Role v1.3.0 overlay safely.

Git commits are opt-in. The script never pushes, resets, stashes, cleans, or force-adds ignored artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError as exc:
    raise SystemExit('Python 3.11+ is required (tomllib missing).') from exc

PACKAGE = Path(__file__).resolve().parent
OVERLAY = PACKAGE / 'overlay'
IGNORE_BLOCK = """# BEGIN jam-coding-role-v1.3.0 runtime
.ai/runtime/
.ai/outgoing-artifacts/
.ai/run-receipts/
.ai/pending-events/
# END jam-coding-role-v1.3.0 runtime
"""
MANAGED_IGNORE_RE = re.compile(r'(?ms)^# BEGIN jam-coding-role-v1\.[23]\.0 runtime\n.*?^# END jam-coding-role-v1\.[23]\.0 runtime\n?')
PROTECTED_FILES = [Path('.codex/config.toml')]
PROTECTED_DIRS = [Path('.codex/agents')]


def run(cmd: list[str], cwd: Path, check: bool=True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def git_root(path: Path) -> Path:
    try:
        return Path(run(['git','rev-parse','--show-toplevel'], path).stdout.strip()).resolve()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f'Not a Git worktree: {path}\n{exc.stderr}')


def git(path: Path, *args: str, check: bool=True) -> str:
    return run(['git', *args], path, check=check).stdout.strip()


def protected_snapshot(root: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for rel in PROTECTED_FILES:
        path = root / rel
        if path.exists(): result[rel.as_posix()] = path.read_bytes()
    for rel in PROTECTED_DIRS:
        path = root / rel
        if path.exists():
            for file in sorted(path.rglob('*')):
                if file.is_file(): result[file.relative_to(root).as_posix()] = file.read_bytes()
    return result


def in_progress(root: Path) -> list[str]:
    gitdir = Path(git(root, 'rev-parse', '--git-dir'))
    if not gitdir.is_absolute(): gitdir = root / gitdir
    markers = ['MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply']
    found = [item for item in markers if (gitdir / item).exists()]
    if git(root, 'diff', '--name-only', '--diff-filter=U'): found.append('unmerged-files')
    return found


def identity_ok(root: Path) -> bool:
    return bool(git(root,'config','user.name',check=False) and git(root,'config','user.email',check=False))


def commit_all_visible(root: Path, message: str, dry_run: bool) -> str:
    if not git(root, 'status', '--porcelain=v1'):
        return git(root, 'rev-parse', 'HEAD')
    if dry_run:
        print(f'WOULD COMMIT ALL GIT-VISIBLE CHANGES: {message}')
        return git(root, 'rev-parse', 'HEAD')
    if not identity_ok(root):
        raise SystemExit('Git user.name/user.email is not configured.')
    run(['git','add','-A'], root)
    run(['git','commit','-m',message], root)
    return git(root, 'rev-parse', 'HEAD')


def planned_files() -> list[Path]:
    return [path.relative_to(OVERLAY) for path in sorted(OVERLAY.rglob('*')) if path.is_file()]


def copy_overlay(root: Path, dry_run: bool) -> None:
    for rel in planned_files():
        if rel == Path('.codex/config.toml') or str(rel).startswith('.codex/agents/'):
            raise SystemExit(f'Package illegally contains protected path: {rel}')
        src = OVERLAY / rel; dst = root / rel
        print(f'{"WOULD WRITE" if dry_run else "WRITE"}: {rel}')
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    gitignore = root / '.gitignore'
    current = gitignore.read_text(encoding='utf-8') if gitignore.exists() else ''
    normalized = MANAGED_IGNORE_RE.sub('', current).rstrip()
    updated = (normalized + '\n\n' + IGNORE_BLOCK).lstrip('\n')
    if current != updated:
        print(f'{"WOULD UPDATE" if dry_run else "UPDATE"}: .gitignore managed runtime block')
        if not dry_run: gitignore.write_text(updated, encoding='utf-8')


def validate(root: Path, before: dict[str, str], dry_run: bool) -> None:
    if dry_run: return
    after = protected_snapshot(root)
    if before != after:
        changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        raise SystemExit('Protected Codex config/role paths changed: ' + ', '.join(changed))
    for rel in [Path('opencode.json'), Path('.claude/settings.json'), Path('.codex/hooks.json'), Path('.omo/omo.jsonc')]:
        json.loads((root / rel).read_text(encoding='utf-8'))
    for rel in [Path('.ai/team-state.toml'), Path('.ai/artifact-targets.toml'), Path('.ai/artifact-sync.toml')]:
        with (root / rel).open('rb') as handle: tomllib.load(handle)
    scripts = sorted((root / '.ai/scripts').glob('*.py'))
    for script in scripts:
        compile(script.read_text(encoding='utf-8'), str(script), 'exec')
    before_runtime = (root / '.ai/runtime/team').exists()
    status = run([sys.executable, '.ai/scripts/team_state.py', 'status', '--json'], root)
    data = json.loads(status.stdout)
    if data.get('active') is not False:
        raise SystemExit('team state must remain inactive after migration')
    if not before_runtime and (root / '.ai/runtime/team').exists():
        raise SystemExit('validation unexpectedly initialized team runtime state')
    ignored = run(['git','check-ignore','.ai/runtime/example'], root, check=False)
    if ignored.returncode != 0:
        raise SystemExit('.ai/runtime is not ignored by Git')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--checkpoint-commit', action='store_true', help='Explicitly commit all Git-visible pre-migration changes.')
    parser.add_argument('--migration-commit', action='store_true', help='Explicitly commit the workflow migration after validation.')
    parser.add_argument('--confirm-user-authorized-commit', action='store_true', help='Confirm that the current Owner explicitly authorized the requested local commit(s).')
    parser.add_argument('--allow-dirty-without-checkpoint', action='store_true', help='Proceed on a dirty tree without a rollback commit; incompatible with --migration-commit.')
    parser.add_argument('--checkpoint-message', default='chore: checkpoint before AI workflow v1.3.0 migration')
    parser.add_argument('--migration-message', default='chore(ai): adopt Jam Coding Role v1.3.0')
    args = parser.parse_args()
    if args.apply and (args.checkpoint_commit or args.migration_commit) and not args.confirm_user_authorized_commit:
        raise SystemExit(
            'Commit flags require --confirm-user-authorized-commit after explicit current Owner authorization.'
        )

    root = git_root(args.repo.expanduser())
    blockers = in_progress(root)
    if blockers: raise SystemExit('Repository has in-progress/conflicted Git state: ' + ', '.join(blockers))
    dirty_before = bool(git(root, 'status', '--porcelain=v1'))
    if args.migration_commit and dirty_before and not args.checkpoint_commit:
        raise SystemExit('--migration-commit on an initially dirty tree requires --checkpoint-commit so unrelated changes are not mixed.')
    if dirty_before and not args.checkpoint_commit and not args.allow_dirty_without_checkpoint:
        raise SystemExit('Worktree is dirty. Use --checkpoint-commit with explicit Owner authorization, or --allow-dirty-without-checkpoint.')

    before = protected_snapshot(root)
    print('BRANCH:', git(root, 'branch', '--show-current') or '(detached)')
    print('HEAD:', git(root, 'rev-parse', 'HEAD'))
    print('STATUS BEFORE:\n' + (git(root, 'status', '--short') or '(clean)'))

    pre = git(root, 'rev-parse', 'HEAD')
    if args.checkpoint_commit:
        pre = commit_all_visible(root, args.checkpoint_message, args.dry_run)
    elif dirty_before:
        print('WARNING: proceeding without checkpoint commit; rollback point is not complete.')

    copy_overlay(root, args.dry_run)
    validate(root, before, args.dry_run)

    if args.dry_run:
        print(f'PRE_MIGRATION_COMMIT={pre}')
        print('DRY RUN COMPLETE; no files or commits were changed.')
        return 0

    migration = None
    if args.migration_commit:
        migration = commit_all_visible(root, args.migration_message, False)
    print('STATUS AFTER:\n' + (git(root, 'status', '--short') or '(clean)'))
    print(f'PRE_MIGRATION_COMMIT={pre}')
    print(f'MIGRATION_COMMIT={migration or "NOT_CREATED"}')
    print('PUSH=NOT_RUN')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
