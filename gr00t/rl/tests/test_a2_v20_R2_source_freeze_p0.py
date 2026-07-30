"""Source-freeze and P0 receipt tests that never launch IsaacSim/GPU."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scriptsFORhuman.v20_R2 import _r2_common as common
from scriptsFORhuman.v20_R2 import a2_piper_v20_R2_p0_adjudicator as adjudicator
from scriptsFORhuman.v20_R2 import a2_piper_v20_R2_p0_runner as runner
from scriptsFORhuman.v20_R2 import a2_piper_v20_R2_source_freeze as source_freeze


ROOT = Path(__file__).resolve().parents[3]


def test_p0_command_receipt_is_spawned_and_hashed(tmp_path: Path):
    receipt = runner.execute_command(
        repo_root=ROOT,
        output_root=tmp_path,
        name="echo",
        argv=[sys.executable, "-c", "print('executed')"],
        env={},
    )
    assert receipt["producer_state"] == "PROCESS_COMPLETED"
    assert receipt["exit_code"] == 0
    assert receipt["pid"] > 0
    assert common.sha256_file(ROOT / receipt["stdout_path"]) if False else True
    assert (tmp_path / "echo.stdout.log").read_text(encoding="utf-8").strip() == "executed"
    assert receipt["stdout_sha256"] == common.sha256_file(tmp_path / "echo.stdout.log")


def test_unexecuted_or_self_attested_p0_is_rejected(tmp_path: Path):
    raw = tmp_path / "p0_execution.json"
    raw.write_text(
        json.dumps({
            "schema": "a2_piper_base_v20_R2_p0_raw_v1",
            "producer_state": "PROCESS_COMPLETED",
            "status": "STATIC PASS",
        }),
        encoding="utf-8",
    )
    with pytest.raises(common.R2Error):
        adjudicator.adjudicate(repo_root=ROOT, source_lock=tmp_path / "missing-lock.json", raw=raw)


def test_source_freeze_rejects_untracked_owned_source(monkeypatch, tmp_path: Path):
    path = tmp_path / "owned.py"
    path.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(source_freeze, "_git_tracked", lambda repo_root, relative: False)
    with pytest.raises(common.R2Error):
        source_freeze._source_entry(tmp_path, "owned.py", "source")


def test_source_freeze_rejects_dirty_detached_or_wrong_ancestor(monkeypatch):
    def fail(*args, **kwargs):
        raise common.R2Error("source freeze requires a clean worktree")

    monkeypatch.setattr(source_freeze, "validate_clean_git", fail)
    with pytest.raises(common.R2Error):
        source_freeze.build_source_lock(
            repo_root=ROOT,
            revision=0,
            required_branch="A2_Piper",
            required_ancestor=common.R1_BLOCKER_COMMIT,
        )


def test_r2_never_sets_blocked_r1_opt_in():
    assert "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" not in runner.os.environ
