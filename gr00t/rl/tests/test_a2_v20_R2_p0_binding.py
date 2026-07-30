"""Binding-level CPU tests for the complete R2 source/P0 contract."""

from __future__ import annotations

import copy
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


def _in_memory_lock() -> dict:
    identity = common.git_identity(ROOT)
    original = source_freeze.validate_clean_git
    original_tracked = source_freeze._git_tracked
    source_freeze.validate_clean_git = lambda *args, **kwargs: {
        "commit": identity["commit"],
        "tree": identity["tree"],
        "branch": "A2_Piper",
    }
    source_freeze._git_tracked = lambda repo_root, relative: True if relative == Path(__file__).relative_to(ROOT).as_posix() else original_tracked(repo_root, relative)
    try:
        return source_freeze.build_source_lock(
            repo_root=ROOT,
            revision=1,
            required_branch="A2_Piper",
            required_ancestor=common.R1_BLOCKER_COMMIT,
        )
    finally:
        source_freeze.validate_clean_git = original
        source_freeze._git_tracked = original_tracked


def test_ignored_checkpoint_is_regular_exact_and_only_untracked_source(monkeypatch: pytest.MonkeyPatch) -> None:
    original_tracked = source_freeze._git_tracked
    monkeypatch.setattr(source_freeze, "_git_tracked", lambda repo_root, relative: True if relative == Path(__file__).relative_to(ROOT).as_posix() else original_tracked(repo_root, relative))
    rows = source_freeze.discover_sources(ROOT)
    row = next(row for row in rows if row["kind"] == "checkpoint")
    assert row["path"] == source_freeze.R1_CHECKPOINT_PATH
    assert row["tracked"] is False
    assert row["size_bytes"] == source_freeze.CHECKPOINT_SIZE_BYTES
    assert row["sha256"] == common.sha256_file(common.resolve_repo_path(ROOT, common.R1_CHECKPOINT_PATH))
    assert sum(not bool(item["tracked"]) for item in rows) == 1


def test_changed_candidate_coverage_is_dynamic_and_exact() -> None:
    lock = _in_memory_lock()
    changed = set(lock["changed_candidates"])
    marked = {row["path"] for row in lock["sources"] if "changed_candidate" in row.get("roles", [])}
    assert changed == marked
    expected = {
        path
        for path in subprocess.check_output(
            ["git", "diff", "--name-only", common.R1_BLOCKER_COMMIT, "HEAD"],
            cwd=ROOT,
            text=True,
        ).splitlines()
        if Path(path).suffix in {".py", ".yaml"}
    }
    assert changed == expected
    assert all(path.endswith((".py", ".yaml")) for path in changed)


def test_p0_command_matrix_has_separate_full_focused_and_eight_hydra_commands() -> None:
    lock = _in_memory_lock()
    commands = runner.build_expected_commands(ROOT, lock)
    names = [row["name"] for row in commands]
    assert len(names) == len(set(names))
    assert {"full_test_discovery", "full_pytest", "focused_pytest"} <= set(names)
    assert len([name for name in names if name.startswith("hydra_resolve_")]) == 8
    expected_categories = {"rehash", "git", "hash", "compile", "diff", "test_discovery", "full_pytest", "focused_pytest", "hydra_resolve", "factor_matrix", "reference_parity", "dimensions", "hidden_override", "staged_ownership", "m48_consumer", "device_environment", "output_root_utc"}
    assert {row["category"] for row in commands} == expected_categories


def test_receipt_commit_and_tree_mutation_is_rejected(tmp_path: Path) -> None:
    receipt = runner.execute_command(
        repo_root=ROOT,
        output_root=tmp_path,
        name="identity",
        argv=[sys.executable, "-B", "-c", "print('ok')"],
        env={},
    )
    expected = {"name": "identity", "argv": receipt["argv"], "env": receipt["env"], "env_sha256": receipt["command_sha256"]}
    mutated = dict(receipt, observed_commit="0" * 40)
    with pytest.raises(common.R2Error):
        adjudicator._validate_receipt(ROOT, mutated, expected, output_root=tmp_path, commit=receipt["observed_commit"], tree=receipt["observed_tree"])
    mutated = dict(receipt, observed_tree="0" * 40)
    with pytest.raises(common.R2Error):
        adjudicator._validate_receipt(ROOT, mutated, expected, output_root=tmp_path, commit=receipt["observed_commit"], tree=receipt["observed_tree"])


def test_missing_unexecuted_or_mutated_logs_are_rejected(tmp_path: Path) -> None:
    receipt = runner.execute_command(
        repo_root=ROOT,
        output_root=tmp_path,
        name="log_mutation",
        argv=[sys.executable, "-B", "-c", "print('ok')"],
        env={},
    )
    expected = {"name": "log_mutation", "argv": receipt["argv"], "env": receipt["env"], "env_sha256": receipt["command_sha256"]}
    stdout = tmp_path / "log_mutation.stdout.log"
    stdout.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(common.R2Error):
        adjudicator._validate_receipt(ROOT, receipt, expected, output_root=tmp_path, commit=receipt["observed_commit"], tree=receipt["observed_tree"])
    stdout.unlink()
    with pytest.raises(common.R2Error):
        adjudicator._validate_receipt(ROOT, receipt, expected, output_root=tmp_path, commit=receipt["observed_commit"], tree=receipt["observed_tree"])


def test_self_attested_status_and_counts_do_not_adjudicate(tmp_path: Path) -> None:
    raw = tmp_path / "p0_execution.json"
    raw.write_text(json.dumps({"schema": "a2_piper_base_v20_R2_p0_raw_v1", "producer_state": "PROCESS_COMPLETED", "status": "STATIC_PASS", "tests_failed": 0}), encoding="utf-8")
    with pytest.raises(common.R2Error):
        common.validate_raw_producer_payload(json.loads(raw.read_text(encoding="utf-8")))
