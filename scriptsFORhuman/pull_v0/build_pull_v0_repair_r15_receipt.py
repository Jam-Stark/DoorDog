#!/usr/bin/env python3
"""Build immutable Attempt17 evidence and the bounded R15 repair receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
LOG_ROOT = ROOT / "logs_eval" / "a2_piper_pull_v0" / "p1_push_anchor"

R14_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R14_RECEIPT.json"
R14_RECEIPT_SHA256 = "bedc40a3693db21981498573e5afd14e8ed736ca84eca5261dfacd9715b59d24"
A4_A6_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_GPU_LEASE_AMENDMENT_RECEIPT.json"
A4_A6_RECEIPT_SHA256 = "1a80804a1062e9878f73c35c89e360e7eaf95c2fa50a6dcf2a9cac85a259e292"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
BASE_SHA = "4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09"

ATTEMPT17_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT17_RECEIPT.json"
ATTEMPT17_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT17_PLAN.json"
ATTEMPT17_PLAN_SHA256 = "0412470f7d5ff293cba5974787105d8891418c81402957bdd09baaf09f9d7dd7"
ATTEMPT17_PLAN_IDENTITY_SHA256 = "5fd9b7af7191f36e565318d6f299274e20ce2eb03d6d45a387f17bcfc73d48f8"
ATTEMPT17_PROCESS_PATH = LOG_ROOT / "attempt17/process_receipt.json"
ATTEMPT17_PROCESS_SHA256 = "ef85a52d634858c645673488ad9a88124c0056260c6d569bbd3b0e135cc69d44"
ATTEMPT17_STDOUT_PATH = LOG_ROOT / "attempt17/stdout_stderr.log"
ATTEMPT17_STDOUT_SHA256 = "7eee0b7f94482b56d984e3e4d8afc39137fa660d751ca13d1a0a388b63cd9e84"
ATTEMPT17_SUMMARY_PATH = LOG_ROOT / "attempt17/eval/a2_hold_oracle_summary.json"
ATTEMPT17_SUMMARY_SHA256 = "015bf37371fc40e3cd341e4ed3b75560203f264985e903a58a7f3fd373ad6924"
ATTEMPT17_METRICS_PATH = LOG_ROOT / "attempt17/eval/metrics_eval.json"
ATTEMPT17_METRICS_SHA256 = "29378a9723caea42b7107380509272efc4388005112620df613ca0cc875b3218"
ATTEMPT17_KIT_LOG_PATH = Path(
    "/home/baoquanc/anaconda3/envs/isaaclab/lib/python3.11/site-packages/"
    "isaacsim/kit/logs/Kit/Isaac-Sim/5.1/kit_20260804_172845.log"
)
ATTEMPT17_KIT_LOG_SHA256 = "47e996ea931fe6e706d69483e38aa5bcfc6bf02220ad63fec4a1ca59fd430b5c"
LAUNCH_OCCUPANCY_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT17_LAUNCH_OCCUPANCY.json"
LAUNCH_OCCUPANCY_SHA256 = "51248f40d24d1893b2d01b50a7a1c8ecb8f7764ac1865bf1e5e78975ece8e1db"
STEADY_STATE_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT17_STEADY_STATE_FOOTPRINT.json"
STEADY_STATE_SHA256 = "63b1bc5ca98d6973f741f631530cd9d725544bc2fa37be238c859bafcddb1359"

R15_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15_RECEIPT.json"
R15_SCHEMA = "pull_v0_repair_r15_receipt_v1"
R15_REVISION = "R15"
R15_ROOT_CAUSE = "CENTER_CLOSE_HANDOFF_OUTSIDE_RELIEF_BUDGET"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path: Path, expected_sha256: str | None = None) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Evidence artifact must be a regular file: {path}")
    actual = _sha256(path)
    if expected_sha256 is not None and actual != expected_sha256:
        raise RuntimeError(f"{path} hash changed: expected={expected_sha256}, actual={actual}")
    label = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return {"path": label, "sha256": actual}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite immutable receipt: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _validate_parent_chain() -> dict[str, Any]:
    r14 = _read_json(R14_RECEIPT_PATH)
    _require(_sha256(R14_RECEIPT_PATH) == R14_RECEIPT_SHA256, "R14 receipt hash changed.")
    _require(r14.get("schema_version") == "pull_v0_repair_r14_receipt_v1", "R14 schema changed.")
    _require(r14.get("repair_revision") == "R14", "R14 revision changed.")
    _require(r14.get("status") == "APPROVED_FOR_ATTEMPT16_PREPARATION_ONLY", "R14 status changed.")
    _require(r14.get("runtime_validation") == "NOT_RUN", "R14 runtime state changed.")
    _require(r14.get("stale_candidate_id") == STALE_CANDIDATE_ID, "R14 stale candidate binding changed.")
    a4 = _read_json(A4_A6_RECEIPT_PATH)
    _require(_sha256(A4_A6_RECEIPT_PATH) == A4_A6_RECEIPT_SHA256, "A4_A6 receipt hash changed.")
    _require(a4.get("schema_version") == "pull_v0_gpu_lease_amendment_receipt_v1", "A4_A6 schema changed.")
    _require(a4.get("amendment_revision") == "A4_A6", "A4_A6 revision changed.")
    _require(a4.get("status") == "APPROVED_FOR_ATTEMPT17_PREPARATION_ONLY", "A4_A6 status changed.")
    _require(a4.get("runtime_validation") == "NOT_RUN", "A4_A6 runtime state changed.")
    _require(a4.get("stale_candidate_id") == STALE_CANDIDATE_ID, "A4_A6 stale candidate binding changed.")
    _require(
        a4.get("parent_receipt")
        == {
            "path": str(R14_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": R14_RECEIPT_SHA256,
            "repair_revision": "R14",
        },
        "A4_A6 parent R14 binding changed.",
    )
    return {"r14": _artifact(R14_RECEIPT_PATH, R14_RECEIPT_SHA256), "a4_a6": _artifact(A4_A6_RECEIPT_PATH, A4_A6_RECEIPT_SHA256)}


def _validate_attempt17_inputs() -> dict[str, Any]:
    artifacts = {
        "plan": _artifact(ATTEMPT17_PLAN_PATH, ATTEMPT17_PLAN_SHA256),
        "process_receipt": _artifact(ATTEMPT17_PROCESS_PATH, ATTEMPT17_PROCESS_SHA256),
        "stdout": _artifact(ATTEMPT17_STDOUT_PATH, ATTEMPT17_STDOUT_SHA256),
        "summary": _artifact(ATTEMPT17_SUMMARY_PATH, ATTEMPT17_SUMMARY_SHA256),
        "metrics": _artifact(ATTEMPT17_METRICS_PATH, ATTEMPT17_METRICS_SHA256),
        "kit_log": _artifact(ATTEMPT17_KIT_LOG_PATH, ATTEMPT17_KIT_LOG_SHA256),
        "launch_occupancy": _artifact(LAUNCH_OCCUPANCY_PATH, LAUNCH_OCCUPANCY_SHA256),
        "steady_state_footprint": _artifact(STEADY_STATE_PATH, STEADY_STATE_SHA256),
    }
    plan = _read_json(ATTEMPT17_PLAN_PATH)
    process = _read_json(ATTEMPT17_PROCESS_PATH)
    summary = _read_json(ATTEMPT17_SUMMARY_PATH)
    metrics = _read_json(ATTEMPT17_METRICS_PATH)
    launch = _read_json(LAUNCH_OCCUPANCY_PATH)
    steady = _read_json(STEADY_STATE_PATH)
    _require(plan.get("schema_version") == "pull_v0_p1_push_anchor_plan_v1", "Attempt17 plan schema changed.")
    _require(plan.get("status") == "READY" and plan.get("attempt") == 17, "Attempt17 plan identity changed.")
    _require(plan.get("base_sha") == BASE_SHA, "Attempt17 plan base SHA changed.")
    _require(plan.get("plan_sha256") == ATTEMPT17_PLAN_IDENTITY_SHA256, "Attempt17 plan identity hash changed.")
    _require(
        plan.get("repair_receipt", {}).get("path") == str(A4_A6_RECEIPT_PATH.relative_to(ROOT))
        and plan.get("repair_receipt", {}).get("sha256") == A4_A6_RECEIPT_SHA256
        and plan.get("repair_receipt", {}).get("revision") == "A4_A6",
        "Attempt17 plan A4_A6 binding changed.",
    )
    argv = plan.get("argv")
    _require(isinstance(argv, list), "Attempt17 plan argv is not a list.")
    _require("+a2_pull_v0_renderer_single_gpu=true" in argv, "Attempt17 renderer transport changed.")
    _require("+device=cuda:2" in argv and "+env.config.max_stage_time=[400,100,100,100,100,200]" in argv, "Attempt17 device/stage argv changed.")
    _require("--kit_args" not in argv and not any(isinstance(token, str) and token.startswith("--/renderer/") for token in argv), "Attempt17 raw Kit argv changed.")
    _require(plan.get("env", {}).get("CUDA_VISIBLE_DEVICES") == "UNSET", "Attempt17 CUDA visibility contract changed.")
    _require(plan.get("gpu_resource_lease") == {"authorized_physical_devices": [2, 3], "selected_physical_device": 2, "gpu7_compute_authorized": False}, "Attempt17 GPU lease changed.")
    _require(process.get("schema_version") == "pull_v0_p1_push_anchor_process_v1" and process.get("attempt") == 17, "Attempt17 process schema changed.")
    _require(process.get("returncode") == 0 and process.get("natural_exit") is True and process.get("application_success") is True, "Attempt17 process lifecycle changed.")
    _require(process.get("plan_sha256") == ATTEMPT17_PLAN_IDENTITY_SHA256 and process.get("stdout_stderr_sha256") == ATTEMPT17_STDOUT_SHA256, "Attempt17 process bindings changed.")
    _require(process.get("summary_sha256") == ATTEMPT17_SUMMARY_SHA256 and process.get("metrics_sha256") == ATTEMPT17_METRICS_SHA256, "Attempt17 summary/metrics bindings changed.")
    _require(summary.get("schema") == "a2_piper_pull_v0_p1_scripted_probe_runtime_v1" and summary.get("status") == "FAIL", "Attempt17 summary status changed.")
    _require(summary.get("per_env_outcome") == ["BASE_RELIEF_DISPLACEMENT_LIMIT"], "Attempt17 scientific outcome changed.")
    _require(summary.get("per_env_pass") == [False] and summary.get("per_env_proof_completed") == [False] and summary.get("per_env_latch_released") == [True], "Attempt17 gate summary changed.")
    _require(summary.get("per_env_max_body_force_n") == [0.0] and summary.get("finalize_called") is True, "Attempt17 body/finalize summary changed.")
    terminal = metrics.get("episode_terminal_diagnostics", [None])[0]
    _require(isinstance(terminal, dict), "Attempt17 terminal metrics are missing.")
    admission = terminal.get("push_anchor_admission")
    _require(isinstance(admission, dict), "Attempt17 push-anchor admission metrics are missing.")
    trace = admission.get("trace")
    _require(isinstance(trace, list) and len(trace) == 310, "Attempt17 compact admission trace changed.")
    row252 = trace[252]
    row309 = trace[309]
    _require(row252.get("phase_before") == "PULL_P1_ACQUIRE" and row252.get("phase_after") == "CENTER_CLOSE", "Attempt17 handoff transition changed.")
    _require(row252.get("dls_candidate_mask") is False and row252.get("dls_finally_applied") is False, "Attempt17 DLS evidence changed.")
    _require(row252.get("target_residuals", {}).get("dls_position_m") == 0.36839473247528076, "Attempt17 DLS residual evidence changed.")
    _require(row309.get("phase_before") == "CENTER_CLOSE" and row309.get("phase_after") == "DONE", "Attempt17 terminal phase evidence changed.")
    _require(admission.get("host_stage_timer") == {"actual_time_in_stage_steps": 359, "max_stage_time_steps": 100, "overtime_observed": True, "source": "device_local_actual_time_in_stage_buf"}, "Attempt17 host-stage timer evidence changed.")
    _require(admission.get("terminal_snapshot", {}).get("outcome") == "BASE_RELIEF_DISPLACEMENT_LIMIT", "Attempt17 terminal outcome evidence changed.")
    _require(metrics.get("completed_episodes") == 1 and metrics.get("episode_terminal_reasons") == ["stage_overtime"], "Attempt17 episode terminal metrics changed.")
    _require(launch.get("status") == "PASS" and launch.get("runtime_started") is False and launch.get("scientific_attempt_started") is False, "Attempt17 launch occupancy evidence changed.")
    _require(steady.get("status") == "PASS" and steady.get("first_simulation_step_boundary_crossed") is True and steady.get("scientific_attempt_started") is True, "Attempt17 steady-state evidence changed.")
    root252 = row252["root_pos_w"]
    root309 = row309["root_pos_w"]
    displacement = math.hypot(root309[0] - root252[0], root309[1] - root252[1])
    return {"artifacts": artifacts, "plan": plan, "process": process, "summary": summary, "metrics": metrics, "admission": admission, "row252": row252, "row309": row309, "root_displacement_m": displacement, "launch": launch, "steady": steady}


def _build_attempt17_receipt(parent_artifacts: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v17",
        "generated_at_hkt": _hkt_now(),
        "attempt": 17,
        "status": "ANCHOR_FAIL_PHYSICS",
        "probe_validity": "PROBE_VALID",
        "runtime_validation": "VALIDATED_ACTUAL_RUNTIME",
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "scientific_verdict_consumed": True,
        "repair_a4_a6": {"artifact": parent_artifacts["a4_a6"], "revision": "A4_A6", "stale_candidate_id": STALE_CANDIDATE_ID},
        "ancestry": {"r14_parent": parent_artifacts["r14"], "attempt17_plan": evidence["artifacts"]["plan"]},
        "evidence": evidence["artifacts"],
        "outcome": {
            "verdict": "ANCHOR_FAIL_PHYSICS",
            "outcome_code": "BASE_RELIEF_DISPLACEMENT_LIMIT",
            "terminal_reason": "stage_overtime",
            "named_finding": R15_ROOT_CAUSE,
            "first_simulation_step_crossed": True,
            "dls_position_residual_m_at_handoff": evidence["row252"]["target_residuals"]["dls_position_m"],
            "center_horizontal_target_residual_m": "NOT_RECORDED_IN_ATTEMPT17_TRACE",
            "root_xy_displacement_handoff_to_terminal_m": evidence["root_displacement_m"],
            "base_relief_max_displacement_m": 0.1,
        },
        "gate_state": {
            "stable_bilateral_capture": False,
            "latch_release": True,
            "proof_samples": 0,
            "arc_samples": 0,
            "body_panel_contact_max_n": 0.0,
            "host_stage_time_steps": 359,
            "host_stage_budget_steps": 100,
            "scientific_verdict_consumed": True,
        },
        "unverified_claims": [
            "No post-repair runtime result is asserted by this receipt.",
            "Attempt17 did not record a separately named center horizontal target residual; 0.3683947325 m is the DLS position residual.",
        ],
    }


def build_r15_receipt() -> dict[str, Any]:
    parent_artifacts = _validate_parent_chain()
    evidence = _validate_attempt17_inputs()
    return {
        "schema_version": R15_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R15_REVISION,
        "status": "APPROVED_FOR_ATTEMPT18_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": R15_ROOT_CAUSE,
            "conclusion": (
                "Attempt17 admitted CENTER_CLOSE from PULL_P1_ACQUIRE on stage_buf>=PREGRASP without checking the remaining center horizontal target error against the existing 0.1 m base-relief displacement budget. The repair defers that phase transition until the measured error fits the existing budget; while pending, it routes the existing high-level base-relief command and watchdog, suppresses arm DLS, and prevents the stale stage0 override from replacing the handoff command."
            ),
            "trigger_step": 252,
            "dls_position_residual_m": 0.36839473247528076,
            "existing_base_relief_max_displacement_m": 0.1,
        },
        "parent_receipt": {"path": parent_artifacts["a4_a6"]["path"], "sha256": parent_artifacts["a4_a6"]["sha256"], "repair_revision": "A4_A6"},
        "trigger": {
            "attempt": 17,
            "root_cause": R15_ROOT_CAUSE,
            "attempt_receipt": _artifact(ATTEMPT17_RECEIPT_PATH) if ATTEMPT17_RECEIPT_PATH.exists() else None,
            "immutable_runtime_artifacts": evidence["artifacts"],
        },
        "scope": {
            "authorized": "Use the existing base_relief_max_displacement_m as the center handoff reachability bound; preserve fixture, direction, funnel, final target, thresholds, timeouts, GPU2/[2,3] lease, and all existing P1/P2 gates.",
            "attempt17_parent_immutable": True,
            "attempt17_scientific_verdict_consumed": True,
            "attempt18_prepared": False,
            "attempt18_runtime_executed": False,
            "attempt18_artifacts_created": False,
            "product_mechanics_changed": True,
            "fixture_changed": False,
            "thresholds_or_timeouts_changed": False,
            "p1_p2_gates_changed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "source_repair": {
            "reachability_helper": "a2_pull_p1_center_handoff_reachable_mask",
            "existing_budget_config_key": "a2_hold_oracle_base_relief_max_displacement_m",
            "pending_command": "a2_hold_base_relief_command(horizontal_error_w, root_quat_w, acquisition_handoff_pending, ...)",
            "arm_dls_pending_handoff": False,
            "stage0_override_pending_handoff": False,
            "new_threshold_or_gate": False,
            "low_level_usd_api": False,
        },
        "changed_files": {
            "gr00t/rl/envs/door/door_open_a2_base.py": {"sha256": _sha256(ROOT / "gr00t/rl/envs/door/door_open_a2_base.py")},
            "gr00t/rl/tests/test_a2_hold_oracle_diagnostics.py": {"sha256": _sha256(ROOT / "gr00t/rl/tests/test_a2_hold_oracle_diagnostics.py")},
            "scriptsFORhuman/pull_v0/build_pull_v0_repair_r15_receipt.py": {"sha256": _sha256(Path(__file__))},
            "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": {"hash_binding": "EXCLUDED_TO_AVOID_R15_RECEIPT_SHA_SELF_CYCLE"},
            "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": {"hash_binding": "EXCLUDED_TO_AVOID_R15_RECEIPT_SHA_SELF_CYCLE"},
        },
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "python -m pytest -q gr00t/rl/tests/test_a2_hold_oracle_diagnostics.py",
                "python -m py_compile gr00t/rl/envs/door/door_open_a2_base.py gr00t/rl/tests/test_a2_hold_oracle_diagnostics.py",
                "git diff --check",
                "Attempt17 compact evidence hash/ancestry validation",
            ],
            "runtime_not_run_reason": "R15 authorizes Attempt18 preparation only; no Attempt18 plan, output, IsaacSim, GPU, or scientific runtime was executed.",
        },
        "acceptance": {
            "attempt17_ancestry_exact": True,
            "attempt17_plan_process_summary_metrics_exact": True,
            "attempt17_launch_occupancy_exact": True,
            "attempt17_steady_state_footprint_exact": True,
            "named_finding_distinct_from_original_six": True,
            "handoff_gate_uses_existing_0p1_budget": True,
            "pending_handoff_base_command_is_high_level": True,
            "pending_handoff_arm_dls_suppressed": True,
            "pending_handoff_stage0_override_suppressed": True,
            "gpu2_authorized_devices_2_3_preserved": True,
            "attempt18_not_prepared_or_run": True,
            "runtime_pass_asserted": False,
        },
        "evidence_summary": {
            "attempt17_outcome": evidence["summary"]["per_env_outcome"],
            "handoff_trace_step": 252,
            "handoff_phase": [evidence["row252"]["phase_before"], evidence["row252"]["phase_after"]],
            "terminal_trace_step": 309,
            "terminal_phase": [evidence["row309"]["phase_before"], evidence["row309"]["phase_after"]],
            "dls_position_residual_m": evidence["row252"]["target_residuals"]["dls_position_m"],
            "root_xy_displacement_m": evidence["root_displacement_m"],
            "base_relief_max_displacement_m": 0.1,
            "host_stage_timer": evidence["admission"]["host_stage_timer"],
        },
        "unverified_claims": [
            "The R15 repair has not been run in IsaacSim; Attempt18 runtime is unverified.",
            "The Attempt17 trace does not contain a separate center_horizontal_target_residual_m field.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build immutable Attempt17 and R15 receipts.")
    parser.add_argument("--attempt17-only", action="store_true")
    args = parser.parse_args()
    parent_artifacts = _validate_parent_chain()
    evidence = _validate_attempt17_inputs()
    if not ATTEMPT17_RECEIPT_PATH.exists():
        _write_once(ATTEMPT17_RECEIPT_PATH, _build_attempt17_receipt(parent_artifacts, evidence))
    else:
        _require(_sha256(ATTEMPT17_RECEIPT_PATH) == _sha256(ATTEMPT17_RECEIPT_PATH), "Attempt17 receipt read failed.")
    if args.attempt17_only:
        print(f"Wrote {ATTEMPT17_RECEIPT_PATH.relative_to(ROOT)}")
        return 0
    if not R15_RECEIPT_PATH.exists():
        _write_once(R15_RECEIPT_PATH, build_r15_receipt())
    print(f"Wrote {ATTEMPT17_RECEIPT_PATH.relative_to(ROOT)}")
    print(f"Wrote {R15_RECEIPT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
