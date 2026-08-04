#!/usr/bin/env python3
"""Build and validate the immutable R15F retry1 launch-admission receipt."""

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

R15E_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15E_RECEIPT.json"
R15E_RECEIPT_SHA256 = (
    "bd384df10e61a0bacd79fdbe0bcdab9172f308ba71c3a6e1b5dac1c92b3e0360"
)
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
PRELAUNCH_INFRA_RECEIPT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PRELAUNCH_INFRA1_RECEIPT.json"
)
PRELAUNCH_INFRA_RECEIPT_SHA256 = (
    "932b6349a339892ea1590d427140820f66884ba357666f35a1bc76f89421e5cf"
)
RETRY1_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY.json"
)
RETRY1_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT.json"
)
ATTEMPT18_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RECEIPT.json"
ATTEMPT18_PROCESS_PATH = LOG_ROOT / "attempt18/process_receipt.json"
ATTEMPT18_LOG_PATH = LOG_ROOT / "attempt18/stdout_stderr.log"
ATTEMPT18_SUMMARY_PATH = LOG_ROOT / "attempt18/eval/a2_hold_oracle_summary.json"
ATTEMPT18_METRICS_PATH = LOG_ROOT / "attempt18/eval/metrics_eval.json"

R15F_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15F_RECEIPT.json"
R15F_RECEIPT_SHA256: str | None = (
    "77fda56deb58e5720711fae654da05301cab306162a8fd6b436e23bac00299e3"
)
R15F_SCHEMA = "pull_v0_repair_r15f_receipt_v1"
R15F_REVISION = "R15F"
R15F_STATUS = "APPROVED_FOR_ATTEMPT18_RETRY1_LAUNCH_ADMISSION_ONLY"
ROOT_CAUSE_CODE = "ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_ADMISSION_CONTRADICTION"


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


def _validate_preserved_chain() -> dict[str, dict[str, str]]:
    r15_artifact = _artifact(R15_RECEIPT_PATH, R15_RECEIPT_SHA256)
    r15 = _read_json(R15_RECEIPT_PATH)
    _require(r15.get("schema_version") == "pull_v0_repair_r15_receipt_v1", "R15 schema changed.")
    _require(r15.get("repair_revision") == "R15", "R15 revision changed.")
    _require(r15.get("status") == "APPROVED_FOR_ATTEMPT18_PREPARATION_ONLY", "R15 status changed.")
    _require(r15.get("runtime_validation") == "NOT_RUN", "R15 runtime state changed.")
    _require(r15.get("stale_candidate_id") == STALE_CANDIDATE_ID, "R15 stale candidate changed.")

    r15e_artifact = _artifact(R15E_RECEIPT_PATH, R15E_RECEIPT_SHA256)
    r15e = _read_json(R15E_RECEIPT_PATH)
    _require(r15e.get("schema_version") == "pull_v0_repair_r15e_receipt_v1", "R15E schema changed.")
    _require(r15e.get("repair_revision") == "R15E", "R15E revision changed.")
    _require(r15e.get("status") == "APPROVED_FOR_ATTEMPT18_RETRY1_PREPARATION_ONLY", "R15E status changed.")
    _require(r15e.get("runtime_validation") == "NOT_RUN", "R15E runtime state changed.")
    _require(r15e.get("scientific_verdict_consumed") is False, "R15E scientific state changed.")
    _require(
        r15e.get("parent_receipt")
        == {"path": r15_artifact["path"], "sha256": r15_artifact["sha256"], "repair_revision": "R15"},
        "R15E R15 parent binding changed.",
    )

    plan_artifact = _artifact(PLAN_PATH, PLAN_SHA256)
    plan = _read_json(PLAN_PATH)
    _require(plan.get("schema_version") == "pull_v0_p1_push_anchor_plan_v1", "Attempt18 plan schema changed.")
    _require(plan.get("status") == "READY" and plan.get("attempt") == 18, "Attempt18 plan identity changed.")
    _require(plan.get("base_sha") == BASE_SHA, "Attempt18 plan base SHA changed.")
    _require(plan.get("plan_sha256") == PLAN_IDENTITY_SHA256, "Attempt18 plan identity hash changed.")
    _require(
        plan.get("gpu_resource_lease")
        == {
            "authorized_physical_devices": [2, 3],
            "selected_physical_device": 2,
            "gpu7_compute_authorized": False,
        },
        "Attempt18 GPU lease changed.",
    )

    launch_artifact = _artifact(INITIAL_LAUNCH_OCCUPANCY_PATH, INITIAL_LAUNCH_OCCUPANCY_SHA256)
    launch = _read_json(INITIAL_LAUNCH_OCCUPANCY_PATH)
    _require(launch.get("schema_version") == "pull_v0_p1_attempt18_launch_occupancy_v1", "Initial occupancy schema changed.")
    _require(launch.get("attempt") == 18 and launch.get("status") == "PASS", "Initial occupancy identity changed.")
    _require(launch.get("phase") == "IMMEDIATELY_BEFORE_LAUNCH", "Initial occupancy phase changed.")
    _require(launch.get("runtime_started") is False and launch.get("scientific_attempt_started") is False, "Initial occupancy crossed runtime boundary.")
    _require(launch.get("selected_compute_physical_device") == 2, "Initial occupancy GPU selection changed.")
    _require(launch.get("authorized_compute_physical_devices") == [2, 3], "Initial occupancy lease changed.")
    _require(launch.get("cuda_visible_devices") == "UNSET", "Initial occupancy CUDA visibility changed.")
    _require(launch.get("container_isolation_used") is False, "Initial occupancy isolation changed.")
    _require(
        launch.get("plan")
        == {
            "path": plan_artifact["path"],
            "sha256": plan_artifact["sha256"],
            "plan_sha256": PLAN_IDENTITY_SHA256,
        },
        "Initial occupancy plan binding changed.",
    )

    prelaunch_artifact = _artifact(PRELAUNCH_INFRA_RECEIPT_PATH, PRELAUNCH_INFRA_RECEIPT_SHA256)
    prelaunch = _read_json(PRELAUNCH_INFRA_RECEIPT_PATH)
    _require(prelaunch.get("schema_version") == "pull_v0_p1_push_anchor_attempt18_prelaunch_infra_receipt_v1", "Prelaunch receipt schema changed.")
    _require(prelaunch.get("status") == "INFRA_PRELAUNCH_RUNNER_VALIDATION", "Prelaunch receipt status changed.")
    _require(prelaunch.get("runtime_validation") == "INVALIDATED_BEFORE_LAUNCH", "Prelaunch runtime state changed.")
    _require(
        prelaunch.get("parent_receipt")
        == {"path": r15_artifact["path"], "sha256": r15_artifact["sha256"], "repair_revision": "R15"},
        "Prelaunch R15 parent binding changed.",
    )
    _require(prelaunch.get("artifacts", {}).get("plan") == plan_artifact, "Prelaunch plan binding changed.")
    _require(
        prelaunch.get("artifacts", {}).get("initial_launch_occupancy") == launch_artifact,
        "Prelaunch occupancy binding changed.",
    )
    return {
        "r15": r15_artifact,
        "r15e": r15e_artifact,
        "plan": plan_artifact,
        "initial_launch_occupancy": launch_artifact,
        "prelaunch_infra": prelaunch_artifact,
    }


def _build_receipt(chain: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    retry1_label = str(RETRY1_LAUNCH_OCCUPANCY_PATH.relative_to(ROOT))
    steady_label = str(RETRY1_STEADY_STATE_FOOTPRINT_PATH.relative_to(ROOT))
    return {
        "schema_version": R15F_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R15F_REVISION,
        "status": R15F_STATUS,
        "runtime_validation": "NOT_RUN",
        "scientific_verdict_consumed": False,
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": ROOT_CAUSE_CODE,
            "conclusion": (
                "Amendment 5 makes a fresh retry1 launch-occupancy receipt mandatory immediately before launch. "
                "R15E allowed the existing plan to re-enter, but runner admission still classified the required "
                "retry1 occupancy as a pre-existing scientific artifact and blocked before subprocess launch."
            ),
        },
        "parent_receipt": {
            "path": chain["r15e"]["path"],
            "sha256": chain["r15e"]["sha256"],
            "repair_revision": "R15E",
        },
        "trigger": {
            "attempt": 18,
            "root_cause": ROOT_CAUSE_CODE,
            "r15e_receipt": dict(chain["r15e"]),
            "required_retry1_launch_occupancy": {
                "path": retry1_label,
                "schema_version": "pull_v0_p1_attempt18_launch_occupancy_v1",
                "phase": "IMMEDIATELY_BEFORE_LAUNCH",
                "selected_compute_physical_device": 2,
                "authorized_compute_physical_devices": [2, 3],
                "cuda_visible_devices": "UNSET",
                "container_isolation_used": False,
            },
            "exact_source_fix": (
                "Remove retry1 launch occupancy from R15 no-runtime scientific-artifact rejection; "
                "validate the canonical occupancy after exact plan re-entry and before subprocess.run."
            ),
        },
        "scope": {
            "r15e_parent_immutable": True,
            "prelaunch_infra_immutable": True,
            "attempt18_plan_immutable": True,
            "retry1_launch_occupancy_required_before_subprocess": True,
            "retry1_runtime_executed": False,
            "first_simulation_step_boundary_crossed": False,
            "scientific_attempt_consumed": False,
            "process_started": False,
            "fixture_changed": False,
            "thresholds_or_timeouts_changed": False,
            "gpu_selection_changed": False,
            "product_mechanics_changed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "source_repair": {
            "bounded_change": (
                "Allow only the canonical retry1 launch occupancy as a pre-subprocess admission artifact and "
                "validate its plan, GPU lease, runtime boundary, device coverage, and tenant attribution."
            ),
            "runner_admission_only": True,
            "scientific_command_unchanged": True,
            "fixture_direction_thresholds_and_gpu_lease_unchanged": True,
            "no_other_process_probe": True,
            "low_level_usd_api": False,
        },
        "preserved_artifacts": {
            "r15e": chain["r15e"],
            "prelaunch_infra": chain["prelaunch_infra"],
            "plan": chain["plan"],
            "initial_launch_occupancy": chain["initial_launch_occupancy"],
        },
        "retry1_paths": {
            "launch_occupancy": retry1_label,
            "steady_state_footprint": steady_label,
        },
        "acceptance": {
            "canonical_retry1_occupancy_required": True,
            "exact_plan_file_and_identity_required": True,
            "gpu2_authorized_2_3_required": True,
            "complete_devices_0_to_7_required": True,
            "explicit_other_tenant_attribution_required": True,
            "steady_process_log_summary_metrics_receipt_forbidden_before_launch": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "R15F does not assert GPU, IsaacSim, physics, anchor, pull-mechanism, or scientific runtime results.",
            "Retry1 launch occupancy is intentionally absent until a future authorized runtime admission.",
        ],
    }


def _validate_receipt(
    chain: Mapping[str, Mapping[str, str]], expected_sha256: str | None = None
) -> dict[str, str]:
    receipt_artifact = _artifact(R15F_RECEIPT_PATH, expected_sha256)
    receipt = _read_json(R15F_RECEIPT_PATH)
    _require(receipt.get("schema_version") == R15F_SCHEMA, "R15F schema changed.")
    _require(receipt.get("repair_revision") == R15F_REVISION, "R15F revision changed.")
    _require(receipt.get("status") == R15F_STATUS, "R15F status changed.")
    _require(receipt.get("runtime_validation") == "NOT_RUN", "R15F runtime state changed.")
    _require(receipt.get("scientific_verdict_consumed") is False, "R15F scientific state changed.")
    _require(receipt.get("stale_candidate_id") == STALE_CANDIDATE_ID, "R15F stale candidate changed.")
    _require(
        receipt.get("parent_receipt")
        == {"path": chain["r15e"]["path"], "sha256": chain["r15e"]["sha256"], "repair_revision": "R15E"},
        "R15F R15E parent binding changed.",
    )
    _require(receipt.get("preserved_artifacts", {}).get("plan") == chain["plan"], "R15F plan binding changed.")
    _require(
        receipt.get("preserved_artifacts", {}).get("initial_launch_occupancy")
        == chain["initial_launch_occupancy"],
        "R15F initial occupancy binding changed.",
    )
    _require(
        receipt.get("preserved_artifacts", {}).get("prelaunch_infra") == chain["prelaunch_infra"],
        "R15F prelaunch binding changed.",
    )
    return receipt_artifact


def build_receipt() -> dict[str, str]:
    chain = _validate_preserved_chain()
    for path in (
        RETRY1_LAUNCH_OCCUPANCY_PATH,
        RETRY1_STEADY_STATE_FOOTPRINT_PATH,
        ATTEMPT18_PROCESS_PATH,
        ATTEMPT18_LOG_PATH,
        ATTEMPT18_SUMMARY_PATH,
        ATTEMPT18_METRICS_PATH,
        ATTEMPT18_RECEIPT_PATH,
    ):
        if path.exists():
            raise RuntimeError(
                "R15F preparation-only receipt refuses existing retry1/runtime artifact: "
                f"{path}"
            )
    if R15F_RECEIPT_PATH.exists():
        raise RuntimeError(f"Refusing to overwrite immutable receipt: {R15F_RECEIPT_PATH}")
    _write_once(R15F_RECEIPT_PATH, _build_receipt(chain))
    return _validate_receipt(chain)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    chain = _validate_preserved_chain()
    if args.validate_only:
        if R15F_RECEIPT_SHA256 is None:
            raise RuntimeError("R15F receipt hash is not sealed for validate-only readback.")
        print(json.dumps(_validate_receipt(chain, R15F_RECEIPT_SHA256), sort_keys=True))
        return 0
    print(json.dumps(build_receipt(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
