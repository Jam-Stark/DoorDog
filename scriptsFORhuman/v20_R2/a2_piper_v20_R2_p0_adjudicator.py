"""Strict consumer for the R2 P0 process receipts.

The consumer reconstructs commands from the source lock, rehashes every
source and log, parses test/Hydra output, and only then emits STATIC_PASS.
Caller-authored counts, status fields, or a hand-written PASS cannot satisfy
this module.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

from ._r2_common import (
    R1_BLOCKER_COMMIT,
    R2Error,
    canonical_json,
    load_json,
    sha256_file,
    validate_clean_git,
    validate_raw_producer_payload,
    validate_regular_file,
    write_json_exclusive,
)
from .a2_piper_v20_R2_p0_runner import _validate_source_lock, build_expected_commands


_PYTEST_COUNT_RE = re.compile(r"(?:(?P<passed>\d+)\s+passed)?(?:,\s*)?(?:(?P<failed>\d+)\s+failed)?(?:,\s*)?(?:(?P<error>\d+)\s+errors?)?(?:,\s*)?(?:(?P<skipped>\d+)\s+skipped)?(?:,\s*)?(?:(?P<xfailed>\d+)\s+xfailed)?(?:,\s*)?(?:(?P<xpassed>\d+)\s+xpassed)?")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _sha(path: Path) -> str:
    return sha256_file(validate_regular_file(path, label="P0 receipt log"))


def _pytest_counts(text: str) -> dict[str, int]:
    candidates: list[dict[str, int]] = []
    for line in text.splitlines():
        match = _PYTEST_COUNT_RE.search(line)
        if not match or not any(value is not None for value in match.groupdict().values()):
            continue
        values = {key: int(value or 0) for key, value in match.groupdict().items()}
        if sum(values.values()) > 0:
            candidates.append(values)
    if not candidates:
        raise R2Error("pytest output has no executable test summary")
    return candidates[-1]


def _yaml_load(text: str, *, label: str) -> Mapping[str, Any]:
    try:
        import yaml

        value = yaml.safe_load(text)
    except (ImportError, UnicodeError, ValueError) as exc:
        raise R2Error(f"cannot parse Hydra YAML output: {label}") from exc
    if not isinstance(value, Mapping):
        raise R2Error(f"Hydra output is not a mapping: {label}")
    return value


def _lookup(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            raise R2Error(f"Hydra output missing factor key: {'.'.join(keys)}")
        current = current[key]
    return current


def _parse_factor_output(text: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(text.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise R2Error("factor/source-to-resolved command did not emit JSON") from exc
    if not isinstance(value, list):
        raise R2Error("factor/source-to-resolved output must be a list")
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _validate_receipt(repo_root: Path, receipt: Mapping[str, Any], expected: Mapping[str, Any], *, output_root: Path, commit: str, tree: str) -> None:
    required = ("schema", "producer_state", "name", "argv", "env", "pid", "started_at_utc", "ended_at_utc", "exit_code", "stdout_path", "stderr_path", "stdout_sha256", "stderr_sha256", "command_sha256", "observed_commit", "observed_tree")
    missing = [key for key in required if key not in receipt]
    if missing:
        raise R2Error(f"process receipt missing fields: {missing}")
    if receipt["schema"] != "a2_piper_base_v20_R2_process_receipt_v1" or receipt["producer_state"] != "PROCESS_COMPLETED":
        raise R2Error("P0 receipts must be completed process receipts")
    if receipt["name"] != expected["name"] or receipt["argv"] != expected["argv"] or receipt["env"] != expected["env"]:
        raise R2Error(f"receipt command differs from reconstructed command: {receipt.get('name')}")
    if receipt["command_sha256"] != expected["env_sha256"]:
        raise R2Error(f"receipt command hash mismatch: {receipt['name']}")
    if receipt["observed_commit"] != commit or receipt["observed_tree"] != tree:
        raise R2Error(f"receipt Git identity mismatch: {receipt['name']}")
    if isinstance(receipt["pid"], bool) or not isinstance(receipt["pid"], int) or receipt["pid"] <= 0:
        raise R2Error(f"receipt PID is invalid: {receipt['name']}")
    for key in ("started_at_utc", "ended_at_utc"):
        if not isinstance(receipt[key], str) or _UTC_RE.fullmatch(receipt[key]) is None:
            raise R2Error(f"receipt timestamp is not canonical UTC: {receipt['name']}")
    if receipt["ended_at_utc"] < receipt["started_at_utc"]:
        raise R2Error(f"receipt ended before it started: {receipt['name']}")
    stdout = repo_root / str(receipt["stdout_path"])
    stderr = repo_root / str(receipt["stderr_path"])
    expected_stdout = output_root / f"{expected['name']}.stdout.log"
    expected_stderr = output_root / f"{expected['name']}.stderr.log"
    if stdout != expected_stdout or stderr != expected_stderr:
        raise R2Error(f"receipt log path differs from output root: {receipt['name']}")
    if _sha(stdout) != receipt["stdout_sha256"] or _sha(stderr) != receipt["stderr_sha256"]:
        raise R2Error(f"receipt log hash mismatch: {receipt['name']}")
    if not isinstance(receipt["exit_code"], int):
        raise R2Error(f"receipt exit code is missing: {receipt['name']}")
    if receipt["exit_code"] != 0:
        raise R2Error(f"P0 command failed: {receipt['name']} exit={receipt['exit_code']}")


def _validate_semantic_outputs(repo_root: Path, lock: Mapping[str, Any], receipts: list[Mapping[str, Any]], output_root: Path) -> dict[str, Any]:
    by_name = {str(row["name"]): row for row in receipts}
    def stdout(name: str) -> str:
        row = by_name[name]
        return (repo_root / str(row["stdout_path"])).read_text(encoding="utf-8")

    if stdout("source_lock_rehash").strip() != sha256_file(repo_root / str(lock["_source_lock_path"])):
        raise R2Error("source-lock rehash command does not match lock bytes")
    if stdout("git_status").strip():
        raise R2Error("P0 Git status is dirty")
    if stdout("git_branch").strip() != "A2_Piper":
        raise R2Error("P0 branch receipt is not A2_Piper")
    if stdout("git_tree").strip() != str(lock["git"]["tree"]):
        raise R2Error("P0 tree receipt differs from source lock")
    if stdout("source_hashes").strip() != "SOURCE_HASHES_OK":
        raise R2Error("source hash command did not verify every source")
    compile_line = stdout("py_compile").strip().split()
    py_count = sum(str(row["path"]).endswith(".py") for row in lock["sources"])
    if compile_line != ["PY_COMPILE_OK", str(py_count)]:
        raise R2Error("py_compile coverage does not match source lock")
    if stdout("full_test_discovery").strip() != json.dumps(sorted(str(row["path"]) for row in lock["sources"] if row.get("kind") == "test"), separators=(",", ":")):
        raise R2Error("full test discovery differs from source lock")
    all_counts = _pytest_counts(stdout("full_pytest"))
    focused_counts = _pytest_counts(stdout("focused_pytest"))
    if all_counts["failed"] or all_counts["error"] or all_counts["skipped"] or all_counts["xfailed"]:
        raise R2Error("full pytest has failed/skipped/error/xfail tests")
    if focused_counts["failed"] or focused_counts["error"] or focused_counts["skipped"] or focused_counts["xfailed"]:
        raise R2Error("focused R2 pytest has failed/skipped/error/xfail tests")
    hydra_names = sorted(name for name in by_name if name.startswith("hydra_resolve_"))
    if len(hydra_names) != 8:
        raise R2Error(f"expected eight Hydra resolves, got {len(hydra_names)}")
    hydra_payloads: dict[str, Mapping[str, Any]] = {}
    for name in hydra_names:
        hydra_payloads[name.removeprefix("hydra_resolve_")] = _yaml_load(stdout(name), label=name)
        payload = hydra_payloads[name.removeprefix("hydra_resolve_")]
        if payload.get("scientific_plan_id") != "base_v20_R1_policy_behavior_v1" or payload.get("admission_plan_id") != "base_v20_R2_admission_execution_v1":
            raise R2Error(f"Hydra identity mismatch: {name}")
    factors = _parse_factor_output(stdout("factor_source_to_resolved"))
    expected_factors = [{key: row[key] for key in ("source_path", "seed", "num_envs", "batches", "send_curriculum", "economics", "arm_tie", "crossing_mode")} for row in lock["factor_bindings"]]
    actual_factors = [{"source_path": row.get("path"), "seed": row.get("seed"), "num_envs": row.get("num_envs"), "batches": row.get("batches"), "send_curriculum": str(row.get("send_curriculum")).lower() == "true", "economics": str(row.get("economics")).lower() == "true", "arm_tie": str(row.get("arm_tie")).lower() == "true", "crossing_mode": row.get("crossing_mode")} for row in factors]
    if sorted(actual_factors, key=lambda row: row["source_path"]) != sorted(expected_factors, key=lambda row: row["source_path"]):
        raise R2Error("factor/source-to-resolved output differs from frozen factor matrix")
    if stdout("v19_g2_disabled_parity").strip() != "V19_G2_DISABLED_PARITY_OK":
        raise R2Error("v19 G2 disabled parity did not execute the expected check")
    if stdout("dimensions").strip() != "DIMENSIONS_OK":
        raise R2Error("dimension parity command did not pass")
    for name in ("hidden_action_override", "staged_reset_ownership", "m48_consumer", "device_environment", "output_root_utc"):
        if not stdout(name).strip():
            raise R2Error(f"required P0 command emitted no evidence: {name}")
    return {"full": all_counts, "focused": focused_counts, "hydra_count": len(hydra_names), "factor_count": len(factors)}


def adjudicate(*, repo_root: Path, source_lock: Path, raw: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    lock_path = validate_regular_file(source_lock if source_lock.is_absolute() else root / source_lock, label="source lock")
    raw_path = validate_regular_file(raw if raw.is_absolute() else root / raw, label="P0 raw execution")
    lock = _validate_source_lock(root, lock_path)
    lock["_source_lock_path"] = str(lock_path)
    raw_payload = load_json(raw_path)
    if not isinstance(raw_payload, Mapping) or raw_payload.get("schema") != "a2_piper_base_v20_R2_p0_raw_v1":
        raise R2Error("P0 raw payload schema mismatch")
    validate_raw_producer_payload(raw_payload, producer_state="PROCESS_COMPLETED")
    if raw_payload.get("source_lock_sha256") != sha256_file(lock_path):
        raise R2Error("P0 raw source-lock hash mismatch")
    identity = validate_clean_git(root, branch="A2_Piper", required_ancestor=str(lock["git"]["required_ancestor"]))
    if raw_payload.get("observed_commit") != identity["commit"] or raw_payload.get("observed_tree") != identity["tree"]:
        raise R2Error("P0 raw observed Git identity mismatch")
    output_root_value = raw_payload.get("output_root")
    if not isinstance(output_root_value, str):
        raise R2Error("P0 raw output_root is missing")
    output_root = Path(output_root_value)
    if not output_root.is_absolute():
        output_root = root / output_root
    output_root = output_root.resolve()
    expected = build_expected_commands(root, lock, output_root=output_root, source_lock_path=lock_path)
    receipts = raw_payload.get("commands")
    if not isinstance(receipts, list) or len(receipts) != len(expected):
        raise R2Error("P0 raw command list does not match reconstructed command list")
    names = [str(row.get("name")) for row in receipts if isinstance(row, Mapping)]
    if names != [str(row["name"]) for row in expected] or len(set(names)) != len(names):
        raise R2Error("P0 command categories are missing, duplicated, or reordered")
    for row, command in zip(receipts, expected):
        if not isinstance(row, Mapping):
            raise R2Error("P0 raw command row is malformed")
        _validate_receipt(root, row, command, output_root=output_root, commit=identity["commit"], tree=identity["tree"])
    semantic = _validate_semantic_outputs(root, lock, [dict(row) for row in receipts], output_root)
    if raw_payload.get("expected_command_names") != names:
        raise R2Error("caller-authored command names differ from observed receipts")
    return {
        "schema": "a2_piper_base_v20_R2_p0_adjudication_v1",
        "adjudicator_state": "STATIC_PASS",
        "source_lock_sha256": sha256_file(lock_path),
        "raw_sha256": sha256_file(raw_path),
        "observed_commit": identity["commit"],
        "observed_tree": identity["tree"],
        "command_results": [{"name": command["name"], "category": command["category"], "exit_code": row["exit_code"], "stdout_sha256": row["stdout_sha256"], "stderr_sha256": row["stderr_sha256"], "rehashed": True} for row, command in zip(receipts, expected)],
        "reconstructed": {
            "command_count": len(expected),
            "all_exit_zero": all(row["exit_code"] == 0 for row in receipts),
            "source_lock_match": True,
            "full_tests_passed": semantic["full"]["passed"],
            "full_tests_failed": semantic["full"]["failed"] + semantic["full"]["error"],
            "focused_tests_passed": semantic["focused"]["passed"],
            "focused_tests_failed": semantic["focused"]["failed"] + semantic["focused"]["error"],
            "hydra_count": semantic["hydra_count"],
            "factor_count": semantic["factor_count"],
        },
    }


def _write_active_marker(*, lock_path: Path, p0_output: Path, adjudication: Mapping[str, Any]) -> Path:
    marker = lock_path.parent / "ACTIVE_SOURCE_LOCK.json"
    lock_payload = load_json(lock_path)
    payload = {
        "schema": "a2_piper_base_v20_R2_active_source_lock_v1",
        "adjudicator_state": "STATIC_PASS",
        "source_lock_sha256": sha256_file(lock_path),
        "p0_static_pass_sha256": sha256_file(p0_output),
        "source_lock": lock_payload,
        "activated_from": adjudication["raw_sha256"],
    }
    write_json_exclusive(marker, payload)
    return marker


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
    _write_active_marker(lock_path=(args.source_lock if args.source_lock.is_absolute() else root / args.source_lock), p0_output=output, adjudication=payload)
    print(canonical_json({"adjudicator_state": payload["adjudicator_state"], "command_count": len(payload["command_results"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
