"""Execute the CPU-only §10.5 P0 command matrix and retain raw receipts.

This module is a producer.  It records real subprocess execution and never
emits ``status``, ``passed`` or a verdict.  P0 adjudication is performed by
the separate strict consumer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
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
from .a2_piper_v20_R2_source_freeze import (
    CHECKPOINT_SIZE_BYTES,
    R1_CHECKPOINT_PATH,
    build_command_templates,
    discover_sources,
)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(path: Path) -> str:
    return sha256_file(validate_regular_file(path, label="P0 file"))


def _validate_source_lock(repo_root: Path, source_lock_path: Path) -> dict[str, Any]:
    payload = load_json(source_lock_path)
    if not isinstance(payload, Mapping) or payload.get("schema") != "a2_piper_base_v20_R2_source_lock_v1":
        raise R2Error("P0 requires an R2 source lock")
    validate_raw_producer_payload(payload, producer_state="SOURCE_FROZEN")
    git = payload.get("git")
    if not isinstance(git, Mapping) or git.get("required_ancestor") != R1_BLOCKER_COMMIT:
        raise R2Error("source lock required ancestor is not the R1 blocker commit")
    rows = payload.get("sources")
    if not isinstance(rows, list) or not rows:
        raise R2Error("source lock has no source rows")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise R2Error("source lock contains a malformed source row")
        relative = row.get("path")
        expected = row.get("sha256")
        size = row.get("size_bytes")
        if not isinstance(relative, str) or not isinstance(expected, str) or not isinstance(size, int):
            raise R2Error("source rows require path, sha256 and size_bytes")
        if relative in seen:
            raise R2Error(f"duplicate source-lock path: {relative}")
        seen.add(relative)
        source = repo_root / relative
        if _sha(source) != expected or source.stat().st_size != size:
            raise R2Error(f"source lock source changed: {relative}")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if relative == R1_CHECKPOINT_PATH:
            if tracked or size != CHECKPOINT_SIZE_BYTES:
                raise R2Error("checkpoint tracking/size contract changed")
        elif not tracked:
            raise R2Error(f"owned source is not tracked: {relative}")
    changed = payload.get("changed_candidates")
    if not isinstance(changed, list) or set(changed) != {str(row["path"]) for row in rows if "changed_candidate" in row.get("roles", [])}:
        raise R2Error("source lock changed-candidate binding is incomplete")
    immutable = payload.get("immutable_inputs")
    if not isinstance(immutable, Mapping):
        raise R2Error("source lock immutable input contract is missing")
    config_path = immutable.get("checkpoint_config_path")
    config_sha = immutable.get("checkpoint_config_sha256")
    config_size = immutable.get("checkpoint_config_size_bytes")
    if not isinstance(config_path, str) or not isinstance(config_sha, str) or not isinstance(config_size, int):
        raise R2Error("checkpoint-adjacent config binding is incomplete")
    config = repo_root / config_path
    if _sha(config) != config_sha or config.stat().st_size != config_size:
        raise R2Error("checkpoint-adjacent config changed after source freeze")
    return dict(payload)


def build_expected_commands(repo_root: Path, source_lock: Mapping[str, Any], *, output_root: Path | None = None, source_lock_path: Path | None = None) -> list[dict[str, Any]]:
    """Reconstruct the exact §10.5 command list from the frozen lock."""

    return build_command_templates(repo_root, source_lock, output_root=output_root, source_lock_path=source_lock_path)


def execute_command(*, repo_root: Path, output_root: Path, name: str, argv: Sequence[str], env: Mapping[str, str]) -> dict[str, Any]:
    if not argv or not all(isinstance(item, str) for item in argv):
        raise R2Error(f"{name}: argv must be a non-empty string list")
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
    started = _utc_now()
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            process = subprocess.Popen(list(argv), cwd=repo_root, env=process_env, stdout=stdout, stderr=stderr)
        except OSError as exc:
            raise R2Error(f"failed to spawn P0 command {name}: {argv!r}") from exc
        pid = int(process.pid)
        exit_code = int(process.wait())
    ended = _utc_now()
    receipt = {
        "schema": "a2_piper_base_v20_R2_process_receipt_v1",
        "producer_state": "PROCESS_COMPLETED",
        "name": name,
        "argv": list(argv),
        "env": selected_env,
        "pid": pid,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "exit_code": exit_code,
        "stdout_path": str(stdout_path.relative_to(repo_root)) if stdout_path.is_relative_to(repo_root) else str(stdout_path),
        "stderr_path": str(stderr_path.relative_to(repo_root)) if stderr_path.is_relative_to(repo_root) else str(stderr_path),
        "stdout_sha256": _sha(stdout_path),
        "stderr_sha256": _sha(stderr_path),
        "command_sha256": hash_command_env(argv, selected_env),
        "observed_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip(),
        "observed_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_root, text=True).strip(),
    }
    validate_raw_producer_payload(receipt)
    return receipt


def run_p0(*, repo_root: Path, source_lock: Path, output_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    lock_path = source_lock if source_lock.is_absolute() else root / source_lock
    lock_path = validate_regular_file(lock_path, label="source lock")
    lock = _validate_source_lock(root, lock_path)
    identity = validate_clean_git(root, branch="A2_Piper", required_ancestor=str(lock["git"]["required_ancestor"]))
    if identity["commit"] != lock["git"]["commit"] or identity["tree"] != lock["git"]["tree"]:
        raise R2Error("current Git commit/tree differs from source lock")
    output = output_root if output_root.is_absolute() else root / output_root
    if output.exists():
        raise R2Error(f"P0 output root already exists: {output}")
    output.mkdir(parents=True)
    commands = build_expected_commands(root, lock, output_root=output, source_lock_path=lock_path)
    receipts = [execute_command(repo_root=root, output_root=output, name=cmd["name"], argv=cmd["argv"], env=cmd["env"]) for cmd in commands]
    payload = {
        "schema": "a2_piper_base_v20_R2_p0_raw_v1",
        "producer_state": "PROCESS_COMPLETED",
        "source_lock_path": str(lock_path.relative_to(root)) if lock_path.is_relative_to(root) else str(lock_path),
        "source_lock_sha256": _sha(lock_path),
        "observed_commit": identity["commit"],
        "observed_tree": identity["tree"],
        "output_root": str(output.relative_to(root)) if output.is_relative_to(root) else str(output),
        "commands": receipts,
        "expected_command_names": [cmd["name"] for cmd in commands],
        "discovered_tests": sorted(str(row["path"]) for row in lock["sources"] if row.get("kind") == "test"),
        "focused_tests": sorted(str(row["path"]) for row in lock["sources"] if row.get("kind") == "test" and "_R2" in Path(str(row["path"])).stem),
    }
    validate_raw_producer_payload(payload, producer_state="PROCESS_COMPLETED")
    write_json_exclusive(output / "p0_execution.json", payload)
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
