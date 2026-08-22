from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'overlay/.ai/scripts/team_state.py'
CONFIG = Path(__file__).resolve().parents[1] / 'overlay/.ai/team-state.toml'


def run(tmp: Path, *args: str, check: bool=True):
    return subprocess.run([sys.executable, str(SCRIPT), '--config', str(CONFIG), *args], cwd=tmp, text=True, capture_output=True, check=check)


def test_inactive_status_has_no_side_effect(tmp_path: Path):
    result = run(tmp_path, 'status', '--json')
    assert json.loads(result.stdout)['active'] is False
    assert not (tmp_path / '.ai/runtime/team').exists()


def test_adaptive_allows_unregistered_and_validates_registered(tmp_path: Path):
    run(tmp_path, 'activate', '--mode', 'adaptive', '--reason', 'test')
    result = run(tmp_path, 'hook-check-spawn', '--task-name', 'quick_reader', '--role', 'context_researcher')
    assert json.loads(result.stdout)['allow'] is True
    run(tmp_path, 'contract-create', '--task-name', 'implement_fix', '--role', 'isaaclab_worker', '--outcome', 'fix')
    bad = run(tmp_path, 'hook-check-spawn', '--task-name', 'implement_fix', '--role', 'isaaclab_worker', check=False)
    assert bad.returncode == 2


def test_strict_writer_requires_contract_and_lease_conflicts(tmp_path: Path):
    run(tmp_path, 'activate', '--mode', 'strict', '--reason', 'formal')
    missing = run(tmp_path, 'hook-check-spawn', '--task-name', 'writer_a', '--role', 'isaaclab_worker', check=False)
    assert missing.returncode == 2
    for name, path in [('writer_a','a.py'),('writer_b','b.py')]:
        run(tmp_path, 'contract-create', '--task-name', name, '--role', 'isaaclab_worker', '--revision', 'r1', '--outcome', 'write', '--write-set', path, '--acceptance', 'proof')
    run(tmp_path, 'lease-acquire', '--task-name', 'writer_a', '--resource', 'gpu:0')
    conflict = run(tmp_path, 'lease-acquire', '--task-name', 'writer_b', '--resource', 'gpu:0', check=False)
    assert conflict.returncode == 3


def test_formal_freeze_and_targeted_invalidation(tmp_path: Path):
    run(tmp_path, 'activate', '--mode', 'strict', '--reason', 'review')
    run(tmp_path, 'contract-create', '--task-name', 'review_code', '--role', 'code_reviewer', '--revision', 'r2', '--outcome', 'review', '--read-set', 'x.py', '--acceptance', 'correct')
    run(tmp_path, 'freeze-create', '--revision', 'r2', '--purpose', 'formal_code_review', '--path', 'x.py')
    run(tmp_path, 'verdict-add', '--verdict-id', 'v1', '--task-name', 'review_code', '--revision', 'r2', '--reviewer-role', 'code_reviewer', '--status', 'PASS', '--path', 'x.py')
    result = run(tmp_path, 'invalidate', '--revision', 'r2', '--changed-path', 'x.py')
    assert 'INVALID' in result.stdout
