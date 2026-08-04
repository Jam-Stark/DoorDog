#!/usr/bin/env python3
"""Build the immutable R7 latch-repair receipt without a runtime claim."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

try:
    from .build_p1_anchor_stop_receipts import (
        EVIDENCE_ROOT,
        LOG_ROOT,
        ROOT,
        _artifact,
        _read_json,
        _sha256,
        _validate_actual_push_anchor_schema,
    )
except ImportError:
    from build_p1_anchor_stop_receipts import (
        EVIDENCE_ROOT,
        LOG_ROOT,
        ROOT,
        _artifact,
        _read_json,
        _sha256,
        _validate_actual_push_anchor_schema,
    )


R6_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R6_RECEIPT.json"
R6_RECEIPT_SHA256 = "7854607b14022fc1954ec024d791fe43e1fd3c0339fe48fb47c8a03cb2a2e6a6"
R6_REVISION = "R6"
R7_REVISION = "R7"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
ATTEMPT8_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT8_RECEIPT.json"
ATTEMPT8_RECEIPT_SHA256 = "dab0732f722bd8444b357b721acbc9c14d8b6725d81096bcfaeb039b9e8e0722"
ATTEMPT8_INVALIDATION_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT8_INVALIDATION.json"
ATTEMPT8_INVALIDATION_SHA256 = "dc43421bc12af85a18bbeb6398b1242daf4f293982894a5e17f0d01ec1535fd4"
ATTEMPT8_ARTIFACTS = {
    "plan": (
        EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT8_PLAN.json",
        "e3b20d5fb10e2b76c71af215a9be3cd99c4516dc7f03accc1ccb7734f4254813",
    ),
    "process_receipt": (
        LOG_ROOT / "attempt8/process_receipt.json",
        "49e2568dbe31affda5042494edf82c021bd95eb89b3f74f3352feb98e74c3591",
    ),
    "log": (
        LOG_ROOT / "attempt8/stdout_stderr.log",
        "9f44c9d19af710f7335c5e22aa3c8e5bdfb584791e47b68c754cbf19c58051fd",
    ),
    "summary": (
        LOG_ROOT / "attempt8/eval/a2_hold_oracle_summary.json",
        "1120c85539d6a2e83c02bb3cde76fe5aad01633216fc2cf6605989dfde4c46de",
    ),
    "metrics": (
        LOG_ROOT / "attempt8/eval/metrics_eval.json",
        "910d4f7f889d9160173c46a0d07fd9f763b65eedb66654f0a85810a33384afab",
    ),
}


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing R7 receipt: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def validate_r7_plus_actual_telemetry(
    summary: Mapping[str, Any], metrics: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Expose the strict generic validator used by R7+ receipt builders/tests."""
    return _validate_actual_push_anchor_schema(
        summary=summary,
        metrics=metrics,
        require_stage0_response=True,
    )


def _validate_attempt8_invalidation() -> dict:
    if _sha256(ATTEMPT8_RECEIPT_PATH) != ATTEMPT8_RECEIPT_SHA256:
        raise RuntimeError("Immutable Attempt8 flawed receipt hash changed.")
    if _sha256(ATTEMPT8_INVALIDATION_PATH) != ATTEMPT8_INVALIDATION_SHA256:
        raise RuntimeError("Attempt8 invalidation manifest hash does not match its canonical binding.")
    invalidation = _read_json(ATTEMPT8_INVALIDATION_PATH)
    if (
        invalidation.get("schema_version") != "pull_v0_p1_push_anchor_attempt_invalidation_v1"
        or invalidation.get("status") != "SUPERSEDED_INVALID"
        or invalidation.get("attempt") != 8
        or invalidation.get("receipt") != {
            "path": str(ATTEMPT8_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": ATTEMPT8_RECEIPT_SHA256,
        }
    ):
        raise RuntimeError("Attempt8 invalidation manifest identity is invalid.")
    reasons = invalidation.get("reasons")
    expected_codes = {
        "STALE_TERMINAL_RESPONSE_ROW",
        "SUMMARY_TERMINAL_STATUS_MISMATCH",
        "EXECUTOR_ACTION_MISMATCH",
        "HARD_CODED_OTHER_ATTEMPT_WORDING",
    }
    if (
        not isinstance(reasons, list)
        or {item.get("code") for item in reasons if isinstance(item, Mapping)} != expected_codes
        or any(not isinstance(item, Mapping) or not isinstance(item.get("evidence"), str) for item in reasons)
    ):
        raise RuntimeError("Attempt8 invalidation reasons are incomplete.")
    return invalidation


def _validate_attempt8_artifacts() -> dict[str, dict[str, str]]:
    bound = {}
    for label, (path, expected_sha256) in ATTEMPT8_ARTIFACTS.items():
        artifact = _artifact(path)
        if artifact["sha256"] != expected_sha256:
            raise RuntimeError(f"Immutable Attempt8 {label} artifact hash changed.")
        bound[label] = artifact
    return bound


def _validate_r6_parent() -> dict:
    artifact = _artifact(R6_RECEIPT_PATH)
    if artifact["sha256"] != R6_RECEIPT_SHA256:
        raise RuntimeError("R6 parent receipt hash does not match the authorized binding.")
    receipt = _read_json(R6_RECEIPT_PATH)
    if (
        receipt.get("schema_version") != "pull_v0_repair_r6_receipt_v1"
        or receipt.get("repair_revision") != R6_REVISION
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
    ):
        raise RuntimeError("R6 parent receipt identity is invalid.")
    return {"artifact": artifact, "receipt": receipt}


def _bound_changed_files() -> dict[str, dict[str, Any]]:
    paths = {
        "gr00t/rl/envs/base_task/a2_base.py": {
            "pre_sha256": "1a14fd023b7ad072024c31a6ee36b08b604752593bab05ed32a2b167efe0a1b1",
            "reason": "Invoke the explicit pre-physics A2 command callback with the exact executor tensors.",
        },
        "gr00t/rl/envs/door/door_open_a2_base.py": {
            "pre_sha256": "cf0c6b204042d49a53b1d52704cf067905a1907fef250441ce7683490c29c02a",
            "reason": "Bind stage0 response capture to episode generation, trace row, control step, and next post-physics root refresh.",
        },
        "gr00t/rl/tests/test_a2_pull_namespace.py": {
            "pre_sha256": "212a28dcd35980746a9fef38337caf7ab5eb77653d27d53a89f3e79b62b99b3e",
            "reason": "Guard latch ordering, immutable Attempt8 invalidation, and R7+ receipt ancestry.",
        },
        "gr00t/rl/tests/test_a2_pull_telemetry.py": {
            "pre_sha256": "b0fd28652fe1b5c84dda92d05fff705c2b6d4ec53ae777894a71182cb8d4b220",
            "reason": "Cover two-phase identity, exact executor tensors, reset failure, and bounded summary equality.",
        },
        "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": {
            "pre_sha256": "fa145a4495e5016164349e525d1f27e8fdab4d7159cf3cdb155e7b0240739074",
            "reason": "Require generic R7+ CAPTURED response mappings and reject missing, stale, mismatched, or cross-attempt telemetry.",
        },
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": {
            "pre_sha256": "49aaae3b981f4a0a705e8613df590ffc09eb4c1c8ab371c756f9416b88f95f3d",
            "reason": "Bind Attempt9+ preparation to the exact R7 receipt and full ancestry without a self-hash cycle.",
        },
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r7_receipt.py": {
            "pre_sha256": None,
            "reason": "Build the immutable R7 repair receipt and expose the strict R7+ telemetry validator.",
        },
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT8_INVALIDATION.json": {
            "pre_sha256": None,
            "reason": "Preserve the flawed Attempt8 receipt byte-identically as SUPERSEDED_INVALID evidence.",
        },
    }
    result = {}
    for relative, data in paths.items():
        path = ROOT / relative
        artifact = _artifact(path)
        if data["pre_sha256"] == "":
            raise RuntimeError("R7 base callback pre-hash must be bound before receipt generation.")
        post_sha256 = artifact["sha256"]
        hash_binding = None
        if relative in {
            "scriptsFORhuman/pull_v0/run_p1_push_anchor.py",
            "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py",
        }:
            # These validators pin the final R7 receipt SHA.  Including their
            # post-hashes in that receipt would create an unresolvable self-hash
            # cycle, so both paths are bound by exact path/reason only.
            post_sha256 = None
            hash_binding = "EXCLUDED_TO_AVOID_R7_RECEIPT_SHA_SELF_CYCLE"
        result[relative] = {
            "pre_sha256": data["pre_sha256"],
            "post_sha256": post_sha256,
            "reason": data["reason"],
        }
        if hash_binding is not None:
            result[relative]["hash_binding"] = hash_binding
    return result


def build_r7_receipt() -> dict:
    parent = _validate_r6_parent()
    invalidation = _validate_attempt8_invalidation()
    attempt8_artifacts = _validate_attempt8_artifacts()
    summary = _read_json(ATTEMPT8_ARTIFACTS["summary"][0])
    metrics = _read_json(ATTEMPT8_ARTIFACTS["metrics"][0])
    if summary.get("per_env_stage0_command_response", [{}])[0].get("status") != "UNAVAILABLE":
        raise RuntimeError("R7 trigger must preserve the invalid Attempt8 UNAVAILABLE rollout summary.")
    terminal = metrics["episode_terminal_diagnostics"][0]["push_anchor_admission"]
    if terminal.get("stage0_command_response", {}).get("status") != "CAPTURED":
        raise RuntimeError("R7 trigger must preserve the invalid Attempt8 CAPTURED terminal response.")
    changed_files = _bound_changed_files()
    return {
        "schema_version": "pull_v0_repair_r7_receipt_v1",
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R7_REVISION,
        "status": "APPROVED_FOR_ATTEMPT9_PREPARATION_ONLY",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": "STAGE0_COMMAND_RESPONSE_LATCH_REQUIRED",
            "conclusion": "The two-phase command/response latch must bind each stage0 response to the exact executor invocation, episode generation, trace row, and next post-physics refresh; the flawed Attempt8 artifact is superseded because those identities are not causal or equal across terminal and rollout summaries.",
            "attempt8_summary_outcome": "PULL_P1_STAGE0_TIMEOUT",
            "attempt8_stage0_rows": 120,
            "attempt8_rollout_response_status": "UNAVAILABLE",
            "attempt8_terminal_response_status": "CAPTURED",
            "stage0_timeout_remains_sole_hard_stop": True,
            "signed_target_and_band_unchanged": True,
        },
        "parent_receipt": {
            "path": parent["artifact"]["path"],
            "sha256": parent["artifact"]["sha256"],
            "repair_revision": R6_REVISION,
        },
        "trigger": {
            "attempt": 8,
            "root_cause": "ATTEMPT8_TELEMETRY_SCHEMA_INVALIDATED",
            "attempt_receipt": _artifact(ATTEMPT8_RECEIPT_PATH),
            "invalidation_manifest": _artifact(ATTEMPT8_INVALIDATION_PATH),
            "immutable_runtime_artifacts": attempt8_artifacts,
        },
        "scope": {
            "authorized": "Add a bounded two-phase report-only stage0 command/response latch and generic receipt validation while preserving signed target, axis mapping, base command, timeout, predicates, stage ordering, and mechanism semantics.",
            "attempt8_immutable": True,
            "attempt9_prepared": False,
            "gpu_or_isaacsim_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "implementation_contract": {
            "pre_physics_callback": "A2Base._a2_base_pre_physics_command_callback(raw_base_action, physical_base_command, lower_body_action)",
            "pending_identity": "episode_generation + trace_row_index + control_step",
            "completion_boundary": "next _pre_compute_observations_callback(post_physics=True) after refreshed ArticulationData root pose/velocity",
            "reset_boundary": "pending response fails reset; completed response summary is latched before live trace clear",
            "response_schema": "a2_piper_pull_v0_stage0_command_response_v2",
            "summary_schema": "a2_piper_pull_v0_stage0_command_response_summary_v2",
            "threshold_mode": "report_only",
            "no_terminal_reconstruction": True,
        },
        "changed_files": changed_files,
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "strict R7+ synthetic response-schema validator tests",
                "Attempt9 runner SHA/ancestry fail-fast tests",
                "receipt/hash assertions",
                "git diff --check",
            ],
            "runtime_not_run_reason": "R7 stops before Attempt9 preparation or runtime; no GPU/IsaacSim resource was leased.",
        },
        "acceptance": {
            "direct_a2base_callback_before_physics": True,
            "exact_executor_raw_physical_and_12_leg_capture": True,
            "generation_trace_row_control_step_identity": True,
            "next_post_physics_completion": True,
            "pending_duplicate_and_reset_fail_fast": True,
            "terminal_summary_equals_rollout_latched_mapping": True,
            "attempt8_receipt_byte_identical_and_superseded": True,
            "r7_plus_generic_response_schema_validation": True,
            "attempt6_and_attempt7_compatibility_preserved": True,
            "attempt9_runner_exact_r7_sha_and_ancestry": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim/GPU runtime PASS is asserted for R7.",
            "No Attempt9 preparation or runtime was executed.",
            "No pull-mechanism verdict is asserted.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable R7 pull-v0 repair receipt.")
    parser.add_argument(
        "--output",
        type=Path,
        default=EVIDENCE_ROOT / "PULL_V0_REPAIR_R7_RECEIPT.json",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    _write_once(output, build_r7_receipt())
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
