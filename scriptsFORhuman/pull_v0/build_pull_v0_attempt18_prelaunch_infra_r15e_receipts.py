#!/usr/bin/env python3
"""Build and validate the immutable Attempt18 prelaunch infrastructure/R15E chain."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
LOG_ROOT = ROOT / "logs_eval" / "a2_piper_pull_v0" / "p1_push_anchor"

R15_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15_RECEIPT.json"
R15_RECEIPT_SHA256 = "3b850232429e4cdaee96281ad16ba2216f34df5baeb5262312f8bba831f841a0"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
BASE_SHA = "4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09"

PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PLAN.json"
PLAN_SHA256 = "58c806cecfef15b876d21358f25742460669cd6e4c14e2c1d6c7ebd43678001f"
PLAN_IDENTITY_SHA256 = "2c9f1efa53423f6abf0a12c41040cfc0c75ed1fb23ce07c05e8c470f093e6d72"
INITIAL_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_LAUNCH_OCCUPANCY.json"
)
INITIAL_LAUNCH_OCCUPANCY_SHA256 = (
    "17f91b53a878c25677a96cd5f03a9c3329c5f32424faf6c4f56bab91f141c6ef"
)
CONFIG_PATH = LOG_ROOT / "attempt18/input/config.yaml"
CONFIG_SHA256 = "c9e2bd493a2d20a89fc8f7414b18225f14aeb902d37b6c638a1a72fc77d1ee89"
CHECKPOINT_PATH = LOG_ROOT / "attempt18/input/model_step_002500.pt"
CHECKPOINT_SHA256 = "f000f13e817309f7b73e33c5c4d95076397debb992713e5613dce567bfda806d"

PRELAUNCH_INFRA_RECEIPT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PRELAUNCH_INFRA1_RECEIPT.json"
)
PRELAUNCH_INFRA_RECEIPT_SHA256 = (
    "932b6349a339892ea1590d427140820f66884ba357666f35a1bc76f89421e5cf"
)
R15E_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15E_RECEIPT.json"
R15E_RECEIPT_SHA256 = (
    "bd384df10e61a0bacd79fdbe0bcdab9172f308ba71c3a6e1b5dac1c92b3e0360"
)
RETRY1_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY.json"
)
RETRY1_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT.json"
)

ERROR_TYPE = "RuntimeError"
ERROR_MESSAGE = (
    "R15 no-runtime scope was violated by Attempt18 artifact: "
    "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PLAN.json"
)
ERROR_SIGNATURE = f"{ERROR_TYPE}: {ERROR_MESSAGE}"
RUNTIME_COMMAND = (
    "/home/baoquanc/anaconda3/envs/isaaclab/bin/python "
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py --attempt 18 "
    "--repair-receipt scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R15_RECEIPT.json "
    "--repair-receipt-sha256 "
    f"{R15_RECEIPT_SHA256}"
)


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


def _validate_preserved_inputs() -> dict[str, Any]:
    r15_artifact = _artifact(R15_RECEIPT_PATH, R15_RECEIPT_SHA256)
    r15 = _read_json(R15_RECEIPT_PATH)
    _require(r15.get("schema_version") == "pull_v0_repair_r15_receipt_v1", "R15 schema changed.")
    _require(r15.get("repair_revision") == "R15", "R15 revision changed.")
    _require(r15.get("status") == "APPROVED_FOR_ATTEMPT18_PREPARATION_ONLY", "R15 status changed.")
    _require(r15.get("runtime_validation") == "NOT_RUN", "R15 runtime state changed.")
    _require(r15.get("stale_candidate_id") == STALE_CANDIDATE_ID, "R15 stale candidate changed.")

    plan_artifact = _artifact(PLAN_PATH, PLAN_SHA256)
    plan = _read_json(PLAN_PATH)
    _require(plan.get("schema_version") == "pull_v0_p1_push_anchor_plan_v1", "Attempt18 plan schema changed.")
    _require(plan.get("status") == "READY" and plan.get("attempt") == 18, "Attempt18 plan identity changed.")
    _require(plan.get("base_sha") == BASE_SHA, "Attempt18 plan base SHA changed.")
    _require(plan.get("plan_sha256") == PLAN_IDENTITY_SHA256, "Attempt18 plan identity hash changed.")
    _require(plan.get("gpu_resource_lease") == {"authorized_physical_devices": [2, 3], "selected_physical_device": 2, "gpu7_compute_authorized": False}, "Attempt18 GPU lease changed.")

    launch_artifact = _artifact(INITIAL_LAUNCH_OCCUPANCY_PATH, INITIAL_LAUNCH_OCCUPANCY_SHA256)
    launch = _read_json(INITIAL_LAUNCH_OCCUPANCY_PATH)
    binding = launch.get("plan")
    _require(launch.get("schema_version") == "pull_v0_p1_attempt18_launch_occupancy_v1", "Initial occupancy schema changed.")
    _require(launch.get("attempt") == 18 and launch.get("status") == "PASS", "Initial occupancy identity changed.")
    _require(launch.get("phase") == "IMMEDIATELY_BEFORE_LAUNCH", "Initial occupancy phase changed.")
    _require(launch.get("runtime_started") is False and launch.get("scientific_attempt_started") is False, "Initial occupancy crossed the runtime boundary.")
    _require(launch.get("selected_compute_physical_device") == 2, "Initial occupancy selected GPU changed.")
    _require(launch.get("authorized_compute_physical_devices") == [2, 3], "Initial occupancy lease changed.")
    _require(launch.get("unauthorized_compute_physical_devices") == [0, 1, 4, 5, 6, 7], "Initial unauthorized GPU contract changed.")
    _require(isinstance(binding, Mapping) and binding.get("path") == plan_artifact["path"] and binding.get("sha256") == plan_artifact["sha256"] and binding.get("plan_sha256") == PLAN_IDENTITY_SHA256, "Initial occupancy plan binding changed.")

    config_artifact = _artifact(CONFIG_PATH, CONFIG_SHA256)
    checkpoint_artifact = _artifact(CHECKPOINT_PATH, CHECKPOINT_SHA256)
    return {
        "r15": r15_artifact,
        "plan": plan_artifact,
        "plan_sha256": PLAN_IDENTITY_SHA256,
        "initial_launch_occupancy": launch_artifact,
        "input_config": config_artifact,
        "checkpoint": checkpoint_artifact,
    }


def _error_record() -> dict[str, Any]:
    return {
        "stage": "RUNNER_PREPARE_REENTRY",
        "type": ERROR_TYPE,
        "message": ERROR_MESSAGE,
        "signature": ERROR_SIGNATURE,
        "command": RUNTIME_COMMAND,
        "process_started": False,
        "isaacsim_started": False,
        "first_simulation_step_boundary_crossed": False,
        "scientific_attempt_started": False,
        "scientific_verdict_consumed": False,
    }


def _build_prelaunch_receipt(inputs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt18_prelaunch_infra_receipt_v1",
        "generated_at_hkt": _hkt_now(),
        "attempt": 18,
        "status": "INFRA_PRELAUNCH_RUNNER_VALIDATION",
        "runtime_validation": "INVALIDATED_BEFORE_LAUNCH",
        "scientific_verdict_consumed": False,
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "first_simulation_step_boundary_crossed": False,
        "scientific_attempt_started": False,
        "parent_receipt": {
            "path": inputs["r15"]["path"],
            "sha256": inputs["r15"]["sha256"],
            "repair_revision": "R15",
        },
        "error": _error_record(),
        "artifacts": {
            "plan": inputs["plan"],
            "initial_launch_occupancy": inputs["initial_launch_occupancy"],
            "input_config": inputs["input_config"],
            "checkpoint": inputs["checkpoint"],
        },
        "scope": {
            "plan_immutable": True,
            "initial_launch_occupancy_immutable": True,
            "process_started": False,
            "scientific_runtime_started": False,
            "fixture_changed": False,
            "thresholds_or_timeouts_changed": False,
            "gpu_selection_changed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "unverified_claims": [
            "No IsaacSim, GPU, first-step, physics, or scientific runtime result is asserted.",
            "The preserved plan and initial occupancy are prelaunch evidence only.",
        ],
    }


def _build_r15e_receipt(inputs: Mapping[str, Any], prelaunch_artifact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "pull_v0_repair_r15e_receipt_v1",
        "generated_at_hkt": _hkt_now(),
        "repair_revision": "R15E",
        "status": "APPROVED_FOR_ATTEMPT18_RETRY1_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "scientific_verdict_consumed": False,
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": "ATTEMPT18_PRELAUNCH_RUNNER_PLAN_REENTRY_CONTRADICTION",
            "conclusion": "The required prepare-only command creates the immutable Attempt18 plan, while the exact run path re-entered preparation and rejected that plan under R15 no-runtime validation before any subprocess or IsaacSim launch.",
            "error_signature": ERROR_SIGNATURE,
        },
        "parent_receipt": {
            "path": inputs["r15"]["path"],
            "sha256": inputs["r15"]["sha256"],
            "repair_revision": "R15",
        },
        "trigger": {
            "attempt": 18,
            "root_cause": "ATTEMPT18_PRELAUNCH_RUNNER_PLAN_REENTRY_CONTRADICTION",
            "prelaunch_infra_receipt": dict(prelaunch_artifact),
            "preserved_plan": inputs["plan"],
            "preserved_initial_launch_occupancy": inputs["initial_launch_occupancy"],
            "exact_error_signature": ERROR_SIGNATURE,
        },
        "scope": {
            "r15_parent_immutable": True,
            "prelaunch_infra_immutable": True,
            "attempt18_scientific_plan_immutable": True,
            "retry1_prepared": False,
            "retry1_runtime_executed": False,
            "process_started": False,
            "first_simulation_step_boundary_crossed": False,
            "scientific_attempt_consumed": False,
            "fixture_changed": False,
            "thresholds_or_timeouts_changed": False,
            "gpu_selection_changed": False,
            "product_mechanics_changed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "source_repair": {
            "bounded_change": "Allow run() to reuse an existing Attempt18 plan only after full semantic identity and plan_sha256 validation; preserve prepare-only no-artifact admission and reject existing scientific/retry artifacts.",
            "runner_reentry_only": True,
            "scientific_command_unchanged": True,
            "fixture_direction_thresholds_and_gpu_lease_unchanged": True,
            "low_level_usd_api": False,
        },
        "preserved_artifacts": {
            "plan": inputs["plan"],
            "initial_launch_occupancy": inputs["initial_launch_occupancy"],
            "input_config": inputs["input_config"],
            "checkpoint": inputs["checkpoint"],
        },
        "retry1_paths": {
            "launch_occupancy": str(RETRY1_LAUNCH_OCCUPANCY_PATH.relative_to(ROOT)),
            "steady_state_footprint": str(RETRY1_STEADY_STATE_FOOTPRINT_PATH.relative_to(ROOT)),
        },
        "acceptance": {
            "exact_error_bound": True,
            "no_process_started": True,
            "no_first_simulation_step": True,
            "no_scientific_verdict": True,
            "r15_ancestry_bound": True,
            "preserved_plan_bound": True,
            "preserved_initial_occupancy_bound": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "R15E does not assert a runtime, GPU, IsaacSim, physics, anchor, or pull-mechanism result.",
            "Retry1 occupancy and steady-state footprint are intentionally absent until a future authorized runtime.",
        ],
    }


def _validate_receipts(inputs: Mapping[str, Any]) -> dict[str, Any]:
    prelaunch_artifact = _artifact(
        PRELAUNCH_INFRA_RECEIPT_PATH, PRELAUNCH_INFRA_RECEIPT_SHA256
    )
    r15e_artifact = _artifact(R15E_RECEIPT_PATH, R15E_RECEIPT_SHA256)
    prelaunch = _read_json(PRELAUNCH_INFRA_RECEIPT_PATH)
    r15e = _read_json(R15E_RECEIPT_PATH)
    _require(prelaunch.get("schema_version") == "pull_v0_p1_push_anchor_attempt18_prelaunch_infra_receipt_v1", "Prelaunch receipt schema changed.")
    _require(prelaunch.get("status") == "INFRA_PRELAUNCH_RUNNER_VALIDATION" and prelaunch.get("attempt") == 18, "Prelaunch receipt identity changed.")
    _require(prelaunch.get("runtime_validation") == "INVALIDATED_BEFORE_LAUNCH", "Prelaunch receipt runtime state changed.")
    _require(prelaunch.get("error", {}).get("signature") == ERROR_SIGNATURE, "Prelaunch error signature changed.")
    _require(prelaunch.get("first_simulation_step_boundary_crossed") is False and prelaunch.get("scientific_attempt_started") is False, "Prelaunch receipt crossed the scientific boundary.")
    _require(prelaunch.get("parent_receipt") == {"path": inputs["r15"]["path"], "sha256": inputs["r15"]["sha256"], "repair_revision": "R15"}, "Prelaunch R15 parent changed.")
    for key, expected in (("plan", inputs["plan"]), ("initial_launch_occupancy", inputs["initial_launch_occupancy"]), ("input_config", inputs["input_config"]), ("checkpoint", inputs["checkpoint"])):
        _require(prelaunch.get("artifacts", {}).get(key) == expected, f"Prelaunch artifact binding changed: {key}.")
    _require(r15e.get("schema_version") == "pull_v0_repair_r15e_receipt_v1" and r15e.get("repair_revision") == "R15E", "R15E receipt identity changed.")
    _require(r15e.get("status") == "APPROVED_FOR_ATTEMPT18_RETRY1_PREPARATION_ONLY" and r15e.get("runtime_validation") == "NOT_RUN", "R15E runtime state changed.")
    _require(r15e.get("scientific_verdict_consumed") is False, "R15E consumed a scientific verdict.")
    _require(r15e.get("parent_receipt") == {"path": inputs["r15"]["path"], "sha256": inputs["r15"]["sha256"], "repair_revision": "R15"}, "R15E R15 parent changed.")
    _require(r15e.get("trigger", {}).get("prelaunch_infra_receipt") == prelaunch_artifact, "R15E prelaunch parent binding changed.")
    _require(r15e.get("trigger", {}).get("exact_error_signature") == ERROR_SIGNATURE, "R15E error signature changed.")
    _require(r15e.get("preserved_artifacts", {}).get("plan") == inputs["plan"], "R15E plan binding changed.")
    _require(r15e.get("preserved_artifacts", {}).get("initial_launch_occupancy") == inputs["initial_launch_occupancy"], "R15E launch binding changed.")
    return {"prelaunch_infra": prelaunch_artifact, "r15e": r15e_artifact}


def build_receipts() -> dict[str, Any]:
    inputs = _validate_preserved_inputs()
    if PRELAUNCH_INFRA_RECEIPT_PATH.exists() or R15E_RECEIPT_PATH.exists():
        raise RuntimeError("R15E receipt chain already exists; use --validate-only for readback.")
    prelaunch = _build_prelaunch_receipt(inputs)
    _write_once(PRELAUNCH_INFRA_RECEIPT_PATH, prelaunch)
    prelaunch_artifact = _artifact(PRELAUNCH_INFRA_RECEIPT_PATH)
    r15e = _build_r15e_receipt(inputs, prelaunch_artifact)
    _write_once(R15E_RECEIPT_PATH, r15e)
    return _validate_receipts(inputs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    inputs = _validate_preserved_inputs()
    if args.validate_only:
        result = _validate_receipts(inputs)
        print(json.dumps(result, sort_keys=True))
        return 0
    result = build_receipts()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
