#!/usr/bin/env python3
"""Build the immutable R10 host-stage-overtime repair receipt."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import yaml

try:
    from .build_p1_anchor_stop_receipts import (
        ATTEMPT11_RECEIPT_PATH,
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
        ATTEMPT11_RECEIPT_PATH,
        EVIDENCE_ROOT,
        LOG_ROOT,
        ROOT,
        _artifact,
        _read_json,
        _sha256,
        _validate_actual_push_anchor_schema,
    )


R9_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R9_RECEIPT.json"
R9_RECEIPT_SHA256 = "3bed2ab4b7e4e21e3d0c05d07b36afa49d7e5a597c8c4efb41178e35f4d6cd69"
R9_REVISION = "R9"
R10_REVISION = "R10"
R10_SCHEMA = "pull_v0_repair_r10_receipt_v1"
R10_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R10_RECEIPT.json"
R10_ROOT_CAUSE = "PULL_P1_STAGE0_HOST_STAGE_OVERTIME_PREEMPTED_LOCAL_WATCHDOG"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"

ATTEMPT11_RECEIPT_SHA256 = "4e37e1c20667ba4d4c9c69ce848725dd1fbe5eda3954dff0f942cc7dbf3f595b"
ATTEMPT11_ARTIFACTS = {
    "plan": (
        EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT11_PLAN.json",
        "78be473a11f3b304c49ad34e0d82cc1a7c1edb0c147675fe7f15056fdb47fa81",
    ),
    "process_receipt": (
        LOG_ROOT / "attempt11/process_receipt.json",
        "2c55d7ac5412e331be36e12c75a4834415a0236077d8d1b2ca34f7af295c9b9a",
    ),
    "log": (
        LOG_ROOT / "attempt11/stdout_stderr.log",
        "81d2d7f8298fdbc20a2856e36af2f8774497b10097dd263fd726a52b8cd34fef",
    ),
    "summary": (
        LOG_ROOT / "attempt11/eval/a2_hold_oracle_summary.json",
        "28f52faedb360307add4b14df0a3d902510683482f39de7a972400c800436031",
    ),
    "metrics": (
        LOG_ROOT / "attempt11/eval/metrics_eval.json",
        "991070babb9e4ffe744f8a5f0a21dc56b067c1efeb386283b237b46687b587b4",
    ),
}
ATTEMPT11_PLAN_IDENTITY_SHA256 = "ecf47679407d4bfddd7a5d3046e6e4e2801d4f5d4a4fb769ecc7a1194849812f"
ATTEMPT11_INPUT_CONFIG = LOG_ROOT / "attempt11/input/config.yaml"
ATTEMPT11_INPUT_CONFIG_SHA256 = "e4619dd6e00aefafe5dc561ed1c3646c5f3e8a19cab256e054b686e09819267f"


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing R10 receipt: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _exact_artifact(path: Path, expected_sha256: str, label: str) -> dict[str, str]:
    artifact = _artifact(path)
    if artifact["sha256"] != expected_sha256:
        raise RuntimeError(
            f"{label} hash changed: expected={expected_sha256}, actual={artifact['sha256']}"
        )
    return artifact


def _validate_r9_parent() -> dict[str, Any]:
    artifact = _exact_artifact(R9_RECEIPT_PATH, R9_RECEIPT_SHA256, "R9 parent receipt")
    receipt = _read_json(R9_RECEIPT_PATH)
    if (
        receipt.get("schema_version") != "pull_v0_repair_r9_receipt_v1"
        or receipt.get("repair_revision") != R9_REVISION
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
    ):
        raise RuntimeError("R9 parent receipt identity is invalid.")
    return {"artifact": artifact, "receipt": receipt}


def _validate_attempt11_runtime() -> dict[str, Any]:
    artifacts: dict[str, dict[str, str]] = {}
    for label, (path, expected_sha256) in ATTEMPT11_ARTIFACTS.items():
        artifacts[label] = _exact_artifact(path, expected_sha256, f"Attempt11 {label} artifact")
    receipt_artifact = _exact_artifact(
        ATTEMPT11_RECEIPT_PATH, ATTEMPT11_RECEIPT_SHA256, "Attempt11 receipt"
    )
    plan = _read_json(ATTEMPT11_ARTIFACTS["plan"][0])
    process = _read_json(ATTEMPT11_ARTIFACTS["process_receipt"][0])
    summary = _read_json(ATTEMPT11_ARTIFACTS["summary"][0])
    metrics = _read_json(ATTEMPT11_ARTIFACTS["metrics"][0])
    if (
        plan.get("attempt") != 11
        or plan.get("plan_sha256") != ATTEMPT11_PLAN_IDENTITY_SHA256
        or process.get("attempt") != 11
        or process.get("plan_path") != artifacts["plan"]["path"]
        or process.get("plan_sha256") != ATTEMPT11_PLAN_IDENTITY_SHA256
        or process.get("repair_receipt_path")
        != str(R9_RECEIPT_PATH.relative_to(ROOT))
        or process.get("repair_receipt_sha256") != R9_RECEIPT_SHA256
        or process.get("stdout_stderr_path") != artifacts["log"]["path"]
        or process.get("stdout_stderr_sha256") != artifacts["log"]["sha256"]
        or process.get("summary_path") != artifacts["summary"]["path"]
        or process.get("summary_sha256") != artifacts["summary"]["sha256"]
        or process.get("metrics_path") != artifacts["metrics"]["path"]
        or process.get("metrics_sha256") != artifacts["metrics"]["sha256"]
        or process.get("application_success") is not True
        or process.get("natural_exit") is not True
        or process.get("returncode") != 0
    ):
        raise RuntimeError("Attempt11 process receipt does not preserve the immutable R9 binding.")
    config_artifact = _exact_artifact(
        ATTEMPT11_INPUT_CONFIG, ATTEMPT11_INPUT_CONFIG_SHA256, "Attempt11 materialized config"
    )
    if plan.get("resolved_config", {}).get("sha256") != config_artifact["sha256"]:
        raise RuntimeError("Attempt11 plan does not bind its immutable materialized config.")
    config = yaml.safe_load(ATTEMPT11_INPUT_CONFIG.read_text(encoding="utf-8"))
    max_stage_time = config["env"]["config"]["max_stage_time"]
    if max_stage_time != [250, 100, 100, 100, 100, 200]:
        raise RuntimeError(f"Attempt11 raw host-stage budget changed: {max_stage_time!r}")
    admission = _validate_actual_push_anchor_schema(
        summary=summary, metrics=metrics, require_stage0_response=True, attempt=11
    )
    terminal_diagnostics = metrics.get("episode_terminal_diagnostics")
    if not isinstance(terminal_diagnostics, list) or len(terminal_diagnostics) != 1:
        raise RuntimeError("Attempt11 metrics must contain one terminal diagnostic.")
    terminal = terminal_diagnostics[0]
    if (
        not isinstance(terminal, Mapping)
        or metrics.get("completed_episodes") != 1
        or metrics.get("episode_max_stage_reached") != [0]
        or metrics.get("episode_terminal_reasons") != ["stage_overtime"]
        or terminal.get("stage_buf") != 0
        or terminal.get("time_in_stage_buf") != 250
        or terminal.get("episode_length_buf") != 250
        or terminal.get("terminal_reasons") != "stage_overtime"
    ):
        raise RuntimeError("Attempt11 terminal boundary is not stage-0 host overtime.")
    stage0_predicates = admission.get("stage0_predicates")
    if stage0_predicates != {"staging_band": False, "settle_count": 0, "timed_out": False}:
        raise RuntimeError("Attempt11 local watchdog predicate is not false at the terminal boundary.")
    trace = admission.get("trace")
    stage0_rows = [
        row for row in trace if isinstance(row, Mapping) and "stage0_predicates" in row
    ]
    response = admission.get("stage0_command_response")
    if (
        not isinstance(trace, list)
        or len(trace) != 250
        or len(stage0_rows) != 247
        or not isinstance(response, Mapping)
        or response.get("response_count") != 247
        or response.get("anti_alignment_count") != 0
    ):
        raise RuntimeError("Attempt11 response trace does not preserve 247 aligned rows.")
    residuals = [float(row["target_residuals"]["stage0_horizontal_m"]) for row in stage0_rows]
    if (
        residuals[0] != 0.9215447306632996
        or residuals[-1] != 0.005086362361907959
        or any(next_value > value + 1.0e-12 for value, next_value in zip(residuals, residuals[1:]))
    ):
        raise RuntimeError("Attempt11 horizontal residual is not monotonic with canonical endpoints.")
    attempt11_receipt = _read_json(ATTEMPT11_RECEIPT_PATH)
    if (
        attempt11_receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v11"
        or attempt11_receipt.get("attempt") != 11
        or attempt11_receipt.get("status") != "BLOCKED"
        or attempt11_receipt.get("probe_validity") != "PROBE_INVALID"
        or attempt11_receipt.get("admission_blocker") != R10_ROOT_CAUSE
        or attempt11_receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
        or attempt11_receipt.get("observed", {}).get("raw_summary_outcome")
        != "ARC_PROBE_TIMEOUT"
        or attempt11_receipt.get("observed", {}).get("classified_outcome")
        != "PULL_P1_STAGE0_HOST_STAGE_OVERTIME"
        or attempt11_receipt.get("host_stage_timer", {}).get("actual_device_local_stage_timer_steps")
        != 250
        or attempt11_receipt.get("host_stage_timer", {}).get("local_stage0_watchdog_steps")
        != 360
        or attempt11_receipt.get("host_stage_timer", {}).get("reset_qualification_steps")
        != 3
        or attempt11_receipt.get("command_to_plant_response", {}).get("response_count") != 247
        or attempt11_receipt.get("command_to_plant_response", {}).get("aggregates", {}).get(
            "anti_alignment_count"
        )
        != 0
    ):
        raise RuntimeError("Attempt11 canonical receipt does not preserve host-overtime evidence.")
    return {
        "artifacts": artifacts,
        "receipt_artifact": receipt_artifact,
        "receipt": attempt11_receipt,
        "plan": plan,
        "process": process,
        "summary": summary,
        "metrics": metrics,
        "admission": admission,
        "config_artifact": config_artifact,
        "residuals": residuals,
    }


def _changed_files() -> dict[str, dict[str, Any]]:
    paths = {
        "gr00t/rl/envs/door/door_open_a2_base.py": "Append the pull-only host-stage-overtime outcome and classify it from latched device-local stage timing.",
        "gr00t/rl/config/ablation/wbmanip/pull_v0_p1_push_anchor.yaml": "Raise only the pull-anchor host stage-0 budget to 400 while preserving the global episode horizon.",
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r10_receipt.py": "Build and validate the immutable R10 repair receipt.",
        "gr00t/rl/tests/test_a2_pull_namespace.py": "Guard exact R9 ancestry, Attempt11 host-overtime evidence, and exact Attempt12 R10 binding.",
        "gr00t/rl/tests/test_a2_pull_telemetry.py": "Guard appended outcome IDs and pending/acquire/host-overtime classification semantics.",
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT11_RECEIPT.json": "Canonical Attempt11 PROBE_INVALID receipt with measured host-stage-overtime classification.",
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "R10 binding and host-stage contract; excluded to avoid receipt hash self-cycle.",
        "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "Attempt11/R10 receipt routing; excluded to avoid receipt hash self-cycle.",
    }
    result: dict[str, dict[str, Any]] = {}
    for relative, reason in paths.items():
        if relative in {
            "scriptsFORhuman/pull_v0/run_p1_push_anchor.py",
            "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py",
        }:
            result[relative] = {
                "pre_sha256": None,
                "post_sha256": None,
                "reason": reason,
                "hash_binding": "EXCLUDED_TO_AVOID_R10_RECEIPT_SHA_SELF_CYCLE",
            }
            continue
        if relative.endswith("PULL_V0_P1_PUSH_ANCHOR_ATTEMPT11_RECEIPT.json"):
            result[relative] = {
                "pre_sha256": None,
                "post_sha256": ATTEMPT11_RECEIPT_SHA256,
                "reason": reason,
            }
            continue
        path = ROOT / relative
        result[relative] = {
            "pre_sha256": None,
            "post_sha256": _sha256(path) if path.is_file() else None,
            "reason": reason,
        }
    return result


def build_r10_receipt() -> dict[str, Any]:
    parent = _validate_r9_parent()
    attempt11 = _validate_attempt11_runtime()
    return {
        "schema_version": R10_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R10_REVISION,
        "status": "APPROVED_FOR_ATTEMPT12_PREPARATION_ONLY",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": R10_ROOT_CAUSE,
            "conclusion": (
                "Immutable Attempt11 preserved 247 aligned stage0 responses and a monotonic signed "
                "horizontal residual, but the host stage-0 budget of 250 steps terminated the stage "
                "before the local 360-step watchdog could fire."
            ),
            "raw_summary_outcome": "ARC_PROBE_TIMEOUT",
            "classified_outcome": "PULL_P1_STAGE0_HOST_STAGE_OVERTIME",
            "host_stage_timer_steps": 250,
            "host_stage_budget_steps": 250,
            "reset_qualification_steps": 3,
            "local_stage0_watchdog_steps": 360,
            "host_budget_less_than_reset_plus_local_watchdog": True,
            "signed_target_and_band_unchanged": True,
        },
        "parent_receipt": {
            "path": parent["artifact"]["path"],
            "sha256": parent["artifact"]["sha256"],
            "repair_revision": R9_REVISION,
        },
        "trigger": {
            "attempt": 11,
            "root_cause": R10_ROOT_CAUSE,
            "attempt_receipt": attempt11["receipt_artifact"],
            "immutable_runtime_artifacts": attempt11["artifacts"],
        },
        "scope": {
            "authorized": (
                "Append one pull-only host-stage-overtime outcome; raise only the pull-anchor "
                "max_stage_time list to [400,100,100,100,100,200]; preserve the global 120-second "
                "episode horizon, local 360-step watchdog, reset qualification, settle/speed, signed "
                "target/band, and mechanism semantics."
            ),
            "r9_parent_immutable": True,
            "attempt11_immutable": True,
            "attempt12_prepared": False,
            "attempt12_runtime_executed": False,
            "gpu_or_isaacsim_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "host_stage_time_contract": {
            "pull_anchor_max_stage_time_steps": [400, 100, 100, 100, 100, 200],
            "global_max_episode_length_s": 120,
            "reset_qualification_steps": 3,
            "local_stage0_timeout_steps": 360,
            "relation": "400 > 3 + 360",
            "fail_fast_on_invalid_relation": True,
            "shared_default_configs_unchanged": True,
        },
        "attempt11_evidence": {
            "status": "BLOCKED",
            "probe_validity": "PROBE_INVALID",
            "raw_summary_outcome": "ARC_PROBE_TIMEOUT",
            "classified_outcome": "PULL_P1_STAGE0_HOST_STAGE_OVERTIME",
            "terminal_reason": "stage_overtime",
            "terminal_stage": 0,
            "terminal_host_stage_timer_steps": 250,
            "local_stage0_timeout_observed": False,
            "response_count": 247,
            "anti_alignment_count": 0,
            "residual_initial_m": attempt11["residuals"][0],
            "residual_terminal_m": attempt11["residuals"][-1],
            "residual_monotonic_nonincreasing": True,
            "pull_mechanism_verdict": "NOT_ASSESSED",
        },
        "quaternion_contract_closure": {
            "source": "canonical ArticulationData.root_quat_w WXYZ",
            "response_rows": 247,
            "anti_alignment_count": 0,
            "residual_monotonic_nonincreasing": True,
            "runtime_validation": "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY",
        },
        "changed_files": _changed_files(),
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "Attempt11 exact R9 ancestry, raw hashes, response and timer evidence",
                "Attempt12 runner exact R10 ancestry and immutable Attempt11 artifact assertions",
                "anchor-only 400 host budget relation and global 120-second preservation",
                "git diff --check",
            ],
            "runtime_not_run_reason": (
                "R10 authorizes Attempt12 preparation only; no Attempt12 preparation, IsaacSim, GPU, "
                "or pull-mechanism runtime was executed."
            ),
        },
        "acceptance": {
            "r9_parent_exact": True,
            "attempt11_receipt_exact": True,
            "attempt11_raw_arc_label_preserved": True,
            "attempt11_host_stage_overtime_classified": True,
            "attempt11_response_rows_247": True,
            "attempt11_zero_anti_alignment": True,
            "attempt11_residual_monotonic_nonincreasing": True,
            "attempt11_local_watchdog_not_reached": True,
            "pull_anchor_max_stage_time_400": True,
            "global_max_episode_length_120": True,
            "host_budget_relation_fail_fast": True,
            "shared_default_configs_unchanged": True,
            "attempt12_runner_exact_r10_binding": True,
            "attempt12_not_prepared_or_run": True,
            "pull_mechanism_verdict_not_assessed": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim/GPU runtime PASS is asserted for R10.",
            "No Attempt12 preparation or runtime was executed.",
            "No pull-mechanism verdict is asserted; all response and timer evidence is admission/watchdog-only.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable R10 pull-v0 repair receipt.")
    parser.add_argument("--output", type=Path, default=R10_RECEIPT_PATH)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    _write_once(output, build_r10_receipt())
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
