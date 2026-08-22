from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'overlay/.ai/scripts/stage_artifacts.py'
CONFIG = Path(__file__).resolve().parents[1] / 'overlay/.ai/artifact-sync.toml'


def sh(cwd: Path, *args: str, check: bool=True):
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


def test_pack_requires_explicit_stage_handoff(tmp_path: Path):
    sh(tmp_path, 'git', 'init', '-q'); sh(tmp_path, 'git', 'config', 'user.name', 'T'); sh(tmp_path, 'git', 'config', 'user.email', 't@example.com')
    (tmp_path / 'base.txt').write_text('base'); sh(tmp_path, 'git', 'add', 'base.txt'); sh(tmp_path, 'git', 'commit', '-qm', 'base')
    (tmp_path / 'logs_eval/base_v25').mkdir(parents=True); (tmp_path / 'logs_eval/base_v25/metrics.json').write_text('{}')
    result = sh(tmp_path, sys.executable, str(SCRIPT), 'pack', '--repo', str(tmp_path), '--config', str(CONFIG), '--stage', 'base_v25', '--selector', 'base_v25', '--project', 'DoorDog', '--worktree', 'A2_Piper', '--trigger', 'owner-request', check=False)
    assert result.returncode != 0
    assert 'confirm-stage-handoff' in result.stderr
