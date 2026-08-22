from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'apply_doordog_v1_3.py'


def sh(cwd: Path, *args: str, check: bool=True):
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_repo(tmp: Path) -> Path:
    repo = tmp / 'repo'; repo.mkdir()
    sh(repo, 'git', 'init', '-q')
    sh(repo, 'git', 'config', 'user.name', 'Test User')
    sh(repo, 'git', 'config', 'user.email', 'test@example.com')
    (repo / '.codex/agents').mkdir(parents=True)
    (repo / '.codex/config.toml').write_text('model="keep"\n', encoding='utf-8')
    (repo / '.codex/agents/worker.toml').write_text('model="keep-agent"\n', encoding='utf-8')
    (repo / '.gitignore').write_text('logs_rl/\n', encoding='utf-8')
    (repo / 'MEMORY.md').write_text('# memory\n', encoding='utf-8')
    sh(repo, 'git', 'add', '-A'); sh(repo, 'git', 'commit', '-qm', 'base')
    return repo


def test_dirty_requires_explicit_git_choice(tmp_path: Path):
    repo = make_repo(tmp_path); (repo / 'dirty.txt').write_text('x')
    result = sh(repo, sys.executable, str(SCRIPT), '--repo', str(repo), '--apply', check=False)
    assert result.returncode != 0
    assert 'Worktree is dirty' in result.stderr



def test_commit_flags_require_current_authorization_confirmation(tmp_path: Path):
    repo = make_repo(tmp_path)
    result = sh(
        repo, sys.executable, str(SCRIPT), '--repo', str(repo), '--apply',
        '--migration-commit', check=False
    )
    assert result.returncode != 0
    assert '--confirm-user-authorized-commit' in result.stderr

def test_explicit_commits_preserve_protected_and_leave_ledger_inactive(tmp_path: Path):
    repo = make_repo(tmp_path); (repo / 'dirty.txt').write_text('x')
    config_hash = digest(repo / '.codex/config.toml'); role_hash = digest(repo / '.codex/agents/worker.toml')
    result = sh(repo, sys.executable, str(SCRIPT), '--repo', str(repo), '--apply', '--checkpoint-commit', '--migration-commit', '--confirm-user-authorized-commit')
    assert 'PUSH=NOT_RUN' in result.stdout
    assert digest(repo / '.codex/config.toml') == config_hash
    assert digest(repo / '.codex/agents/worker.toml') == role_hash
    assert not (repo / '.ai/runtime/team').exists()
    assert sh(repo, 'git', 'status', '--porcelain').stdout.strip() == ''
    assert int(sh(repo, 'git', 'rev-list', '--count', 'HEAD').stdout.strip()) == 3
