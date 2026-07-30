"""Reconstruct and adjudicate an executed R2 P0 receipt set.

The consumer rehashes the source lock, every process log, and every command
identity.  A caller-authored result field cannot satisfy this tool; only the
reconstructed evidence can produce ``adjudicator_state=STATIC_PASS``.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path
from typing import Any, Mapping

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
from .a2_piper_v20_R2_p0_runner import build_expected_commands


def _hash(path: Path) -> str:
    return sha256_file(validate_regular_file(path, label="P0 receipt log"))


def _load_lock(repo_root: Path, path: Path) -> Mapping[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, Mapping) or payload.get("schema") != "a2_piper_base_v20_R2_source_lock_v1":
        raise R2Error("P0 adjudicator requires a source_lock_v1 payload")
    validate_raw_producer_payload(payload, producer_state="SOURCE_FROZEN")
    if payload.get("git", {}).get("required_ancestor") != R1_BLOCKER_COMMIT:
        raise R2Error("source lock does not bind the R1 blocker ancestor")
    for row in payload.get("sources", []):
        if not isinstance(row, Mapping):
            raise R2Error("source lock source row is malformed")
        source = repo_root / str(row["path"])
        if _hash(source) != row["sha256"]:
            raise R2Error(f"source changed after freeze: {row['path']}")
    return payload


def _validate_receipt(repo_root: Path, receipt: Mapping[str, Any], expected: Mapping[str, Any], commit: str) -> None:
    required = ("schema", "producer_state", "name", "argv", "env", "pid", "started_at_utc", "ended_at_utc", "exit_code", "stdout_path", "stderr_path", "stdout_sha256", "stderr_sha256", "command_sha256", "observed_commit")
    missing = [key for key in required if key not in receipt]
    if missing:
        raise R2Error(f"process receipt missing fields: {missing}")
    if receipt["schema"] != "a2_piper_base_v20_R2_process_receipt_v1" or receipt["producer_state"] != "PROCESS_COMPLETED":
        raise R2Error("P0 receipts must be completed process receipts")
    if receipt["name"] != expected["name"] or receipt["argv"] != expected["argv"] or receipt["env"] != expected["env"]:
        raise R2Error(f"receipt command differs from reconstructed command: {receipt.get('name')}")
    if receipt["command_sha256"] != hash_command_env(receipt["argv"], receipt["env"]):
        raise R2Error(f"receipt command hash mismatch: {receipt['name']}")
    if receipt["observed_commit"] != commit:
        raise R2Error(f"receipt observed commit mismatch: {receipt['name']}")
    if isinstance(receipt["pid"], bool) or not isinstance(receipt["pid"], int) or receipt["pid"] <= 0:
        raise R2Error(f"receipt PID is invalid: {receipt['name']}")
    stdout = repo_root / str(receipt["stdout_path"])
    stderr = repo_root / str(receipt["stderr_path"])
    if _hash(stdout) != receipt["stdout_sha256"] or _hash(stderr) != receipt["stderr_sha256"]:
        raise R2Error(f"receipt log hash mismatch: {receipt['name']}")
    if not isinstance(receipt["exit_code"], int):
        raise R2Error(f"receipt exit code is missing: {receipt['name']}")
    if receipt["exit_code"] != 0:
        raise R2Error(f"P0 command failed: {receipt['name']} exit={receipt['exit_code']}")


def adjudicate(*, repo_root: Path, source_lock: Path, raw: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    lock_path = source_lock if source_lock.is_absolute() else root / source_lock
    raw_path = raw if raw.is_absolute() else root / raw
    lock = _load_lock(root, lock_path)
    raw_payload = load_json(raw_path)
    if not isinstance(raw_payload, Mapping) or raw_payload.get("schema") != "a2_piper_base_v20_R2_p0_raw_v1":
        raise R2Error("P0 raw payload schema mismatch")
    validate_raw_producer_payload(raw_payload, producer_state="PROCESS_COMPLETED")
    lock_sha = sha256_file(lock_path)
    if raw_payload.get("source_lock_sha256") != lock_sha:
        raise R2Error("P0 raw source-lock hash mismatch")
    identity = validate_clean_git(root, branch="A2_Piper", required_ancestor=str(lock["git"]["required_ancestor"]))
    if raw_payload.get("observed_commit") != identity["commit"]:
        raise R2Error("P0 raw observed commit mismatch")
    expected = build_expected_commands(root, lock)
    receipts = raw_payload.get("commands")
    if not isinstance(receipts, list) or len(receipts) != len(expected):
        raise R2Error("P0 raw command list does not match reconstructed command list")
    results = []
    for row, command in zip(receipts, expected):
        if not isinstance(row, Mapping):
            raise R2Error("P0 raw command row is malformed")
        _validate_receipt(root, row, command, identity["commit"])
        results.append(
            {
                "name": command["name"],
                "exit_code": row["exit_code"],
                "stdout_sha256": row["stdout_sha256"],
                "stderr_sha256": row["stderr_sha256"],
                "rehashed": True,
            }
        )
    return {
        "schema": "a2_piper_base_v20_R2_p0_adjudication_v1",
        "adjudicator_state": "STATIC_PASS",
        "source_lock_sha256": lock_sha,
        "raw_sha256": sha256_file(raw_path),
        "observed_commit": identity["commit"],
        "command_results": results,
        "reconstructed": {
            "command_count": len(results),
            "all_exit_zero": all(row["exit_code"] == 0 for row in results),
            "source_lock_match": True,
            "tests_failed": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    payload = adjudicate(repo_root=root, source_lock=args.source_lock, raw=args.raw)
    output = args.output if args.output.is_absolute() else root / args.output
    write_json_exclusive(output, payload)
    print(canonical_json({"adjudicator_state": payload["adjudicator_state"], "command_count": len(payload["command_results"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
