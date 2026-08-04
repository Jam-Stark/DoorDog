#!/usr/bin/env python3
"""Build the immutable R9 stage0-timeout-capacity repair receipt."""

from __future__ import annotations

import argparse
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


R8_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R8_RECEIPT.json"
R8_RECEIPT_SHA256 = "00e7abbc6612f7a841cb0a809c7053ba343dab1e7d14f94d092510a82f11b76b"
R8_REVISION = "R8"
R9_REVISION = "R9"
R9_SCHEMA = "pull_v0_repair_r9_receipt_v1"
R9_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R9_RECEIPT.json"
R9_ROOT_CAUSE = "STAGE0_TIMEOUT_BELOW_KINEMATIC_CAPACITY"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"

ATTEMPT10_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_RECEIPT.json"
ATTEMPT10_ARTIFACTS = {
    "plan": (
        EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_PLAN.json",
        "98bad3d8b617811e9db459be434f754d90bbafe1bc388035d84e0f219d12ae11",
    ),
    "process_receipt": (
        LOG_ROOT / "attempt10/process_receipt.json",
        "91094b6010c2a19545f6c5e31e66f2a8acdb61042fb714e0e61a5d2e3551ba88",
    ),
    "log": (
        LOG_ROOT / "attempt10/stdout_stderr.log",
        "dc5a0171a6cb2c4d59265761665fd314a9cc5fe918bc5074567f461de4a907ee",
    ),
    "summary": (
        LOG_ROOT / "attempt10/eval/a2_hold_oracle_summary.json",
        "b2c2904a18c4f5ffc675ee1da37e237a9265f7abc13e080417ffcee5123be06e",
    ),
    "metrics": (
        LOG_ROOT / "attempt10/eval/metrics_eval.json",
        "74f160458bf51cfd28e4fd15275b6cfd64f8a6987b12d6d031e0d5fadca2b3cb",
    ),
}
ATTEMPT10_PLAN_IDENTITY_SHA256 = "176d5c7de626d336040100c991439399ce385c6063bce6e1563e1174f7c616bc"
ATTEMPT10_RECEIPT_SHA256 = "725300a992e5e842b4335d62e8ee71bbcf4b3bcd414a5087ba6dca38ecdaaaf6"


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing R9 receipt: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _exact_artifact(path: Path, expected_sha256: str, label: str) -> dict[str, str]:
    artifact = _artifact(path)
    if artifact["sha256"] != expected_sha256:
        raise RuntimeError(
            f"{label} hash changed: expected={expected_sha256}, actual={artifact['sha256']}"
        )
    return artifact


def _validate_r8_parent() -> dict[str, Any]:
    artifact = _exact_artifact(R8_RECEIPT_PATH, R8_RECEIPT_SHA256, "R8 parent receipt")
    receipt = _read_json(R8_RECEIPT_PATH)
    if (
        receipt.get("schema_version") != "pull_v0_repair_r8_receipt_v1"
        or receipt.get("repair_revision") != R8_REVISION
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
    ):
        raise RuntimeError("R8 parent receipt identity is invalid.")
    return {"artifact": artifact, "receipt": receipt}


def _validate_attempt10_runtime() -> dict[str, Any]:
    artifacts: dict[str, dict[str, str]] = {}
    for label, (path, expected_sha256) in ATTEMPT10_ARTIFACTS.items():
        artifacts[label] = _exact_artifact(path, expected_sha256, f"Attempt10 {label} artifact")
    plan = _read_json(ATTEMPT10_ARTIFACTS["plan"][0])
    process = _read_json(ATTEMPT10_ARTIFACTS["process_receipt"][0])
    if (
        plan.get("attempt") != 10
        or plan.get("plan_sha256") != ATTEMPT10_PLAN_IDENTITY_SHA256
        or process.get("attempt") != 10
        or process.get("plan_path") != artifacts["plan"]["path"]
        or process.get("plan_sha256") != ATTEMPT10_PLAN_IDENTITY_SHA256
        or process.get("stdout_stderr_path") != artifacts["log"]["path"]
        or process.get("stdout_stderr_sha256") != artifacts["log"]["sha256"]
        or process.get("summary_path") != artifacts["summary"]["path"]
        or process.get("summary_sha256") != artifacts["summary"]["sha256"]
        or process.get("metrics_path") != artifacts["metrics"]["path"]
        or process.get("metrics_sha256") != artifacts["metrics"]["sha256"]
        or process.get("repair_receipt_path")
        != str(R8_RECEIPT_PATH.relative_to(ROOT))
        or process.get("repair_receipt_sha256") != R8_RECEIPT_SHA256
        or process.get("application_success") is not True
        or process.get("natural_exit") is not True
        or process.get("returncode") != 0
    ):
        raise RuntimeError("Attempt10 process receipt does not preserve the immutable R8 execution binding.")
    summary = _read_json(ATTEMPT10_ARTIFACTS["summary"][0])
    metrics = _read_json(ATTEMPT10_ARTIFACTS["metrics"][0])
    admission = _validate_actual_push_anchor_schema(
        summary=summary,
        metrics=metrics,
        require_stage0_response=True,
        attempt=10,
    )
    response = admission["stage0_command_response"]
    trace = admission["trace"]
    stage0_rows = [row for row in trace if isinstance(row, Mapping) and "stage0_predicates" in row]
    residuals = [
        float(row["target_residuals"]["stage0_horizontal_m"])
        for row in stage0_rows
    ]
    if (
        len(stage0_rows) != 120
        or response.get("response_count") != 120
        or response.get("anti_alignment_count") != 0
        or not residuals
        or any(next_value > value + 1.0e-12 for value, next_value in zip(residuals, residuals[1:]))
        or residuals[0] != 0.9215447306632996
        or residuals[-1] != 0.5063455700874329
        or admission.get("stage0_predicates") != {
            "staging_band": False,
            "settle_count": 0,
            "timed_out": True,
        }
    ):
        raise RuntimeError("Attempt10 runtime telemetry does not preserve the timeout-capacity evidence.")
    receipt_artifact = _exact_artifact(
        ATTEMPT10_RECEIPT_PATH, ATTEMPT10_RECEIPT_SHA256, "Attempt10 receipt"
    )
    receipt = _read_json(ATTEMPT10_RECEIPT_PATH)
    budget = receipt.get("budget_analysis")
    closure = receipt.get("quaternion_contract_closure")
    expected_budget = {
        "initial_stage0_horizontal_m": 0.9215447306632996,
        "terminal_stage0_horizontal_m": 0.5063455700874329,
        "residual_monotonic_nonincreasing": True,
        "residual_increase_count": 0,
        "physical_speed_mps": 0.15,
        "control_dt_s": 0.02,
        "distance_per_control_step_m": 0.003,
        "kinematic_lower_bound_steps": 308,
        "settle_steps": 5,
        "minimum_steps_including_settle": 313,
        "configured_timeout_steps": 120,
        "timeout_shortfall_vs_kinematic_lower_bound_steps": 188,
        "r9_timeout_steps": 360,
        "r9_nominal_horizon_s": 7.2,
        "r9_nominal_travel_m": 1.08,
        "budget_role": "P1_STAGE0_ADMISSION_WATCHDOG_ONLY",
        "mechanism_threshold": False,
    }
    if (
        receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v10"
        or receipt.get("attempt") != 10
        or receipt.get("status") != "BLOCKED"
        or receipt.get("probe_validity") != "PROBE_INVALID"
        or receipt.get("admission_blocker") != R9_ROOT_CAUSE
        or receipt.get("runtime_validation") != "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY"
        or receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
        or budget != expected_budget
        or not isinstance(closure, Mapping)
        or closure.get("source") != "canonical ArticulationData.root_quat_w WXYZ"
        or closure.get("response_rows") != 120
        or closure.get("anti_alignment_count") != 0
        or closure.get("residual_monotonic_nonincreasing") is not True
        or receipt.get("repair_r8", {}).get("artifact") != {
            "path": str(R8_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": R8_RECEIPT_SHA256,
        }
    ):
        raise RuntimeError("Attempt10 receipt does not preserve the canonical R8/budget contract.")
    return {
        "artifacts": artifacts,
        "receipt_artifact": receipt_artifact,
        "receipt": receipt,
        "plan": plan,
        "process": process,
        "summary": summary,
        "metrics": metrics,
        "admission": admission,
    }


def _changed_files() -> dict[str, dict[str, Any]]:
    paths = {
        "gr00t/rl/config/ablation/wbmanip/pull_v0_p1_push_anchor.yaml": "Raise only the pull-anchor stage0 admission watchdog from 120 to 360 steps.",
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "Bind exact Attempt10/R8 and Attempt11/R9 ancestry and use the 360-step stage0 watchdog.",
        "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "Classify immutable Attempt10 timeout capacity and retain canonical WXYZ response closure.",
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r9_receipt.py": "Build and validate the immutable R9 repair receipt.",
        "gr00t/rl/tests/test_a2_pull_namespace.py": "Guard R7/R8/R9 receipt ancestry and the 360-step timeout binding.",
        "gr00t/rl/tests/test_a2_pull_telemetry.py": "Guard the Attempt10 residual-budget and response telemetry contract.",
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_RECEIPT.json": "Immutable Attempt10 canonical receipt; included by exact artifact hash.",
    }
    result: dict[str, dict[str, Any]] = {}
    for relative, reason in paths.items():
        path = ROOT / relative
        if relative in {
            "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py",
            "scriptsFORhuman/pull_v0/run_p1_push_anchor.py",
        }:
            result[relative] = {
                "pre_sha256": None,
                "post_sha256": None,
                "reason": reason,
                "hash_binding": "EXCLUDED_TO_AVOID_R9_RECEIPT_SHA_SELF_CYCLE",
            }
            continue
        if relative.endswith("PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_RECEIPT.json"):
            result[relative] = {
                "pre_sha256": None,
                "post_sha256": ATTEMPT10_RECEIPT_SHA256,
                "reason": reason,
            }
            continue
        result[relative] = {
            "pre_sha256": None,
            "post_sha256": _sha256(path) if path.is_file() else None,
            "reason": reason,
        }
    return result


def build_r9_receipt() -> dict[str, Any]:
    parent = _validate_r8_parent()
    attempt10 = _validate_attempt10_runtime()
    return {
        "schema_version": R9_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R9_REVISION,
        "status": "APPROVED_FOR_ATTEMPT11_PREPARATION_ONLY",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": R9_ROOT_CAUSE,
            "conclusion": (
                "Immutable Attempt10 reached the signed stage0 timeout with 120 response rows, "
                "zero anti-alignment, and monotonically decreasing horizontal residual, but the "
                "120-step watchdog was below the measured staging-distance capacity."
            ),
            "initial_stage0_horizontal_m": 0.9215447306632996,
            "physical_speed_mps": 0.15,
            "control_dt_s": 0.02,
            "distance_per_control_step_m": 0.003,
            "kinematic_lower_bound_steps": 308,
            "settle_steps": 5,
            "minimum_steps_including_settle": 313,
            "attempt10_timeout_steps": 120,
            "timeout_shortfall_vs_kinematic_lower_bound_steps": 188,
            "r9_timeout_steps": 360,
            "r9_nominal_horizon_s": 7.2,
            "r9_nominal_travel_m": 1.08,
            "budget_role": "P1_STAGE0_ADMISSION_WATCHDOG_ONLY",
            "mechanism_threshold": False,
            "signed_target_and_band_unchanged": True,
        },
        "parent_receipt": {
            "path": parent["artifact"]["path"],
            "sha256": parent["artifact"]["sha256"],
            "repair_revision": R8_REVISION,
        },
        "trigger": {
            "attempt": 10,
            "root_cause": R9_ROOT_CAUSE,
            "attempt_receipt": attempt10["receipt_artifact"],
            "immutable_runtime_artifacts": attempt10["artifacts"],
        },
        "scope": {
            "authorized": (
                "Raise only the P1 pull-anchor stage0 admission watchdog to 360 steps; "
                "preserve the signed target, staging band, staging speed, settle count, stage "
                "ordering, and mechanism semantics."
            ),
            "attempt9_r7_immutable": True,
            "attempt10_r8_immutable": True,
            "attempt11_prepared": False,
            "attempt11_runtime_executed": False,
            "gpu_or_isaacsim_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "quaternion_contract_closure": {
            "source": "canonical ArticulationData.root_quat_w WXYZ",
            "response_rows": 120,
            "anti_alignment_count": 0,
            "initial_stage0_horizontal_m": 0.9215447306632996,
            "terminal_stage0_horizontal_m": 0.5063455700874329,
            "residual_monotonic_nonincreasing": True,
            "runtime_validation": "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY",
        },
        "attempt10_evidence": {
            "status": "BLOCKED",
            "probe_validity": "PROBE_INVALID",
            "stage0_timeout_predicates": {
                "staging_band": False,
                "settle_count": 0,
                "timed_out": True,
            },
            "response_count": 120,
            "anti_alignment_count": 0,
            "residual_increase_count": 0,
            "response_metrics_report_only": True,
        },
        "changed_files": _changed_files(),
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "Attempt9 R7 and Attempt10 R8 exact receipt/hash assertions",
                "Attempt11 runner exact R9 ancestry and immutable Attempt10 artifact assertions",
                "360-step timeout confined to pull-anchor config and runner",
                "git diff --check",
            ],
            "runtime_not_run_reason": (
                "R9 authorizes preparation only; no Attempt11 preparation, IsaacSim, GPU, or "
                "pull-mechanism runtime was executed."
            ),
        },
        "acceptance": {
            "attempt9_r7_receipt_unchanged": True,
            "attempt10_exact_r8_parent_binding": True,
            "attempt10_response_rows_120": True,
            "attempt10_zero_anti_alignment": True,
            "attempt10_residual_monotonic_nonincreasing": True,
            "attempt10_timeout_below_kinematic_bound_explicit": True,
            "r9_timeout_360_only_pull_anchor_watchdog": True,
            "attempt11_runner_exact_r9_sha_and_full_attempt10_ancestry": True,
            "attempt11_not_prepared_or_run": True,
            "pull_mechanism_verdict_not_assessed": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim/GPU runtime PASS is asserted for R9.",
            "No Attempt11 preparation or runtime was executed.",
            "No pull-mechanism verdict is asserted; the timeout analysis is admission/watchdog-only.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable R9 pull-v0 repair receipt.")
    parser.add_argument(
        "--output",
        type=Path,
        default=R9_RECEIPT_PATH,
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    _write_once(output, build_r9_receipt())
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
