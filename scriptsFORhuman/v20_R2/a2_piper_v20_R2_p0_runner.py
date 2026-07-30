"""Execute the CPU-only P0 command set and emit raw process receipts.

This module is a producer.  It records what actually ran and deliberately has
no ``status``, ``passed`` or verdict field.  The adjudicator is the only tool
allowed to turn these receipts into ``STATIC_PASS``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._r2_common import (
    R1_BLOCKER_COMMIT,
    R2Error,
    canonical_json,
    hash_command_env,
    load_json,
    sha256_file,
    validate_clean_git,
    validate_raw_producer_payload,
    validate_regular_file,
    write_json_exclusive,
)
from .a2_piper_v20_R2_source_freeze import discover_sources


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _source_lock_sha256(path: Path) -> str:
    return sha256_file(validate_regular_file(path, label="source lock"))


def _validate_source_lock(repo_root: Path, source_lock_path: Path) -> dict[str, Any]:
    payload = load_json(source_lock_path)
    if not isinstance(payload, Mapping) or payload.get("schema") != "a2_piper_base_v20_R2_source_lock_v1":
        raise R2Error("P0 requires an R2 source lock")
    validate_raw_producer_payload(payload, producer_state="SOURCE_FROZEN")
    if payload.get("git", {}).get("required_ancestor") != R1_BLOCKER_COMMIT:
        raise R2Error("source lock required ancestor is not the R1 blocker commit")
    for row in payload.get("sources", []):
        if not isinstance(row, Mapping):
            raise R2Error("source lock contains a malformed source row")
        relative = row.get("path")
        expected = row.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise R2Error("source lock source rows require path and SHA-256")
        path = repo_root / relative
        actual = sha256_file(path)
        if actual != expected:
            raise R2Error(f"source lock source changed: {relative}")
    return dict(payload)


def build_expected_commands(repo_root: Path, source_lock: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build a deterministic, CPU-only command list from the frozen lock."""

    py_files = sorted(
        row["path"] for row in source_lock.get("sources", []) if row.get("kind") == "source" and str(row["path"]).endswith(".py")
    )
    test_files = sorted(
        row["path"] for row in source_lock.get("sources", []) if row.get("kind") == "test" and str(row["path"]).endswith(".py")
    )
    ancestor = str(source_lock["git"]["required_ancestor"])
    # The checks are explicit commands rather than in-process claims.  The
    # Python snippets are intentionally tiny and only inspect the frozen files.
    hash_code = (
        "import hashlib, pathlib, sys; "
        "[(lambda p,e: (_ for _ in ()).throw(SystemExit(1)) if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()!=e else None)(p,e) "
        "for p,e in zip(sys.argv[1::2],sys.argv[2::2])]"
    )
    compile_code = (
        "import pathlib,sys; "
        "[compile(pathlib.Path(p).read_text(encoding='utf-8'),p,'exec') for p in sys.argv[1:]]"
    )
    hash_pairs: list[str] = []
    for row in source_lock.get("sources", []):
        hash_pairs.extend([str(row["path"]), str(row["sha256"])])
    commands: list[dict[str, Any]] = [
        {"name": "git_status", "argv": ["git", "status", "--porcelain=v1", "--untracked-files=all"], "env": {}},
        {"name": "git_branch", "argv": ["git", "branch", "--show-current"], "env": {}},
        {"name": "git_ancestor", "argv": ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"], "env": {}},
        {"name": "source_hashes", "argv": [sys.executable, "-B", "-c", hash_code, *hash_pairs], "env": {}},
        {"name": "py_compile", "argv": [sys.executable, "-B", "-c", compile_code, *py_files], "env": {}},
        {"name": "diff_check", "argv": ["git", "diff", "--check", ancestor, "HEAD", "--"], "env": {}},
    ]
    if test_files:
        commands.append(
            {"name": "focused_tests", "argv": [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *test_files], "env": {}}
        )
    # Exact command identity is carried in the receipt, not inferred from the
    # command name later.
    for command in commands:
        command["env_sha256"] = hash_command_env(command["argv"], command["env"])
    return commands


def execute_command(
    *,
    repo_root: Path,
    output_root: Path,
    name: str,
    argv: Sequence[str],
    env: Mapping[str, str],
) -> dict[str, Any]:
    if not argv or not all(isinstance(item, str) for item in argv):
        raise R2Error(f"{name}: argv must be non-empty string list")
    if any("BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" in item for item in argv) or "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" in env:
        raise R2Error("R2 may not set the blocked-R1 execution opt-in")
    output_root.mkdir(parents=True, exist_ok=True)
    stdout_path = output_root / f"{name}.stdout.log"
    stderr_path = output_root / f"{name}.stderr.log"
    if stdout_path.exists() or stderr_path.exists():
        raise R2Error(f"P0 command output already exists for {name}")
    selected_env = dict(sorted((str(key), str(value)) for key, value in env.items()))
    process_env = os.environ.copy()
    process_env.update(selected_env)
    started_at = _utc_now()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        try:
            process = subprocess.Popen(list(argv), cwd=repo_root, env=process_env, stdout=stdout, stderr=stderr)
        except OSError as exc:
            raise R2Error(f"failed to spawn P0 command {name}: {argv!r}") from exc
        pid = process.pid
        exit_code = process.wait()
    ended_at = _utc_now()
    try:
        stdout_ref = str(stdout_path.relative_to(repo_root))
        stderr_ref = str(stderr_path.relative_to(repo_root))
    except ValueError:
        stdout_ref = str(stdout_path)
        stderr_ref = str(stderr_path)
    receipt = {
        "schema": "a2_piper_base_v20_R2_process_receipt_v1",
        "producer_state": "PROCESS_COMPLETED",
        "name": name,
        "argv": list(argv),
        "env": selected_env,
        "pid": pid,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "exit_code": exit_code,
        "stdout_path": stdout_ref,
        "stderr_path": stderr_ref,
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "command_sha256": hash_command_env(argv, selected_env),
        "observed_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip(),
    }
    validate_raw_producer_payload(receipt)
    return receipt


def run_p0(*, repo_root: Path, source_lock: Path, output_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    lock = source_lock if source_lock.is_absolute() else root / source_lock
    lock_payload = _validate_source_lock(root, lock)
    validate_clean_git(root, branch="A2_Piper", required_ancestor=str(lock_payload["git"]["required_ancestor"]))
    output_root = output_root if output_root.is_absolute() else root / output_root
    if output_root.exists():
        raise R2Error(f"P0 output root already exists: {output_root}")
    output_root.mkdir(parents=True)
    receipts = []
    for command in build_expected_commands(root, lock_payload):
        receipts.append(
            execute_command(
                repo_root=root,
                output_root=output_root,
                name=command["name"],
                argv=command["argv"],
                env=command["env"],
            )
        )
    payload = {
        "schema": "a2_piper_base_v20_R2_p0_raw_v1",
        "producer_state": "PROCESS_COMPLETED",
        "source_lock_path": str(lock.relative_to(root)),
        "source_lock_sha256": _source_lock_sha256(lock),
        "observed_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "commands": receipts,
        "discovered_tests": sorted(row["path"] for row in lock_payload["sources"] if row["kind"] == "test"),
        "focused_tests": sorted(row["path"] for row in lock_payload["sources"] if row["kind"] == "test" and "R2" in row["path"]),
    }
    validate_raw_producer_payload(payload, producer_state="PROCESS_COMPLETED")
    write_json_exclusive(output_root / "p0_execution.json", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = run_p0(repo_root=args.repo_root, source_lock=args.source_lock, output_root=args.output_root)
    print(canonical_json({"producer_state": payload["producer_state"], "command_count": len(payload["commands"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
