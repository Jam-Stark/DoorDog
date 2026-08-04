#!/usr/bin/env python3
"""Build the immutable A4/A6 GPU-lease amendment preparation receipt."""

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
    )
except ImportError:
    from build_p1_anchor_stop_receipts import (
        EVIDENCE_ROOT,
        LOG_ROOT,
        ROOT,
        _artifact,
        _read_json,
        _sha256,
    )


AUTHORITY_PATH = Path(
    "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pull_task/"
    "a2_piper_pull_v0_gpu_lease_amendment_20260804.md"
)
AUTHORITY_SHA256 = "84e94561bac1eb39b49d27e67c9f5b192844f7b9f5e203961495beea683dfc49"
R14_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R14_RECEIPT.json"
R14_RECEIPT_SHA256 = "bedc40a3693db21981498573e5afd14e8ed736ca84eca5261dfacd9715b59d24"
R14_SCHEMA = "pull_v0_repair_r14_receipt_v1"
R14_REVISION = "R14"
AMENDMENT_SCHEMA = "pull_v0_gpu_lease_amendment_receipt_v1"
AMENDMENT_REVISION = "A4_A6"
AMENDMENT_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_GPU_LEASE_AMENDMENT_RECEIPT.json"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"

ATTEMPT15_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT15_RECEIPT.json"
ATTEMPT15_RECEIPT_SHA256 = "01c952a4402a887275ff53f02f26ea4a88f3f6c79ed0fc4388f4d32cbde763b0"
ATTEMPT16_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT16_RECEIPT.json"
ATTEMPT16_RECEIPT_SHA256 = "2cfbd95e10dc57e16cf2f566925593c41680f3592539676c013c4931a22c06c5"
ATTEMPT16_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT16_PLAN.json"
ATTEMPT16_PLAN_SHA256 = "7371fef9948e72a9900da45074daba9d5848556ebc9dac91eb9eba44fdaf55e9"
ATTEMPT16_STDOUT_PATH = LOG_ROOT / "attempt16/stdout_stderr.log"
ATTEMPT16_STDOUT_SHA256 = "f490a2540c700304de21598a95e7c6f787dccf0a6a8338cb3536838aff321e0d"
ATTEMPT16_KIT_LOG_PATH = Path(
    "/home/baoquanc/anaconda3/envs/isaaclab/lib/python3.11/site-packages/"
    "isaacsim/kit/logs/Kit/Isaac-Sim/5.1/kit_20260804_050202.log"
)
ATTEMPT16_KIT_LOG_SHA256 = "e3e1d25bae608e323122651f288b1528d7187f9d806779b581f8086d8ed25618"
VULKAN_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_VULKAN_ENUMERATION_CONTEXT_RECEIPT.json"
VULKAN_RECEIPT_SHA256 = "7d2fbc98a07355f989bc450e39b7ba85fe8deb29ecee32852605f07e6c7bd383"
INFRA_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_INFRA_RECLASSIFICATION_RECEIPT.json"
INFRA_RECEIPT_SHA256 = "b3b31ff57e63e87c7712db862fb56f523229b579df7195370eee5e650ebe8b43"
SINGLE_GPU_KIT_ARGS = (
    "--/renderer/multiGpu/enabled=False "
    "--/renderer/multiGpu/autoEnable=False "
    "--/renderer/multiGpu/maxGpuCount=1"
)
PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE = "+a2_pull_v0_renderer_single_gpu=true"


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite amendment receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _exact_artifact(path: Path, expected_sha256: str, label: str) -> dict[str, str]:
    artifact = _artifact(path)
    if artifact["sha256"] != expected_sha256:
        raise RuntimeError(
            f"{label} hash changed: expected={expected_sha256}, actual={artifact['sha256']}"
        )
    return artifact


def _validate_authority() -> dict[str, str]:
    return _exact_artifact(AUTHORITY_PATH, AUTHORITY_SHA256, "A4/A6 authority document")


def _validate_r14_parent() -> dict[str, Any]:
    artifact = _exact_artifact(R14_RECEIPT_PATH, R14_RECEIPT_SHA256, "R14 parent receipt")
    receipt = _read_json(R14_RECEIPT_PATH)
    parent = receipt.get("parent_receipt")
    scope = receipt.get("scope")
    if (
        receipt.get("schema_version") != R14_SCHEMA
        or receipt.get("repair_revision") != R14_REVISION
        or receipt.get("status") != "APPROVED_FOR_ATTEMPT16_PREPARATION_ONLY"
        or receipt.get("runtime_validation") != "NOT_RUN"
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
        or not isinstance(parent, Mapping)
        or parent.get("sha256") != "afc3466fc270f9f5166a29a06c34fc6e39c853d0441a52d4539cd0cff0304c32"
        or parent.get("repair_revision") != "R13"
        or not isinstance(scope, Mapping)
        or scope.get("attempt16_prepared") is not False
        or scope.get("attempt16_runtime_executed") is not False
        or scope.get("pull_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("R14 parent identity or Attempt16 preparation-only scope is invalid.")
    return {"artifact": artifact, "receipt": receipt}


def _validate_attempt16_receipt() -> dict[str, Any]:
    receipt_artifact = _exact_artifact(
        ATTEMPT16_RECEIPT_PATH, ATTEMPT16_RECEIPT_SHA256, "Attempt16 receipt"
    )
    plan_artifact = _exact_artifact(ATTEMPT16_PLAN_PATH, ATTEMPT16_PLAN_SHA256, "Attempt16 plan")
    stdout_artifact = _exact_artifact(ATTEMPT16_STDOUT_PATH, ATTEMPT16_STDOUT_SHA256, "Attempt16 stdout")
    kit_artifact = _exact_artifact(ATTEMPT16_KIT_LOG_PATH, ATTEMPT16_KIT_LOG_SHA256, "Attempt16 Kit log")
    receipt = _read_json(ATTEMPT16_RECEIPT_PATH)
    plan = _read_json(ATTEMPT16_PLAN_PATH)
    resource_stop = receipt.get("resource_stop")
    if (
        receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v16"
        or receipt.get("attempt") != 16
        or receipt.get("status") != "PROBE_INVALID"
        or receipt.get("probe_validity") != "PROBE_INVALID"
        or receipt.get("runtime_validation") != "INVALIDATED_BY_GPU_RESOURCE_TOPOLOGY"
        or receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
        or receipt.get("scientific_verdict_consumed") is not False
        or not isinstance(resource_stop, Mapping)
        or resource_stop.get("triggered") is not True
        or resource_stop.get("selected_physical_gpu") != 4
        or resource_stop.get("authorized_gpu_indices") not in (None, [4, 5, 6])
        or 7 not in resource_stop.get("unauthorized_gpu_indices", [])
        or not isinstance(plan.get("renderer_single_gpu_transport"), Mapping)
        or plan["renderer_single_gpu_transport"].get("raw_kit_args_in_argv") is not False
        or plan.get("renderer_single_gpu_transport", {}).get("hydra_override")
        != "+a2_pull_v0_renderer_single_gpu=true"
        or plan.get("gpu_resource_lease", {}).get("authorized_physical_devices") != [4, 5, 6]
        or plan.get("gpu_resource_lease", {}).get("selected_physical_device") != 4
        or plan.get("plan_sha256") != "3941c89a86bfb3115317d83fbd6c65d383f6893e4e6aed749cfed2c054f452ea"
    ):
        raise RuntimeError("Attempt16 receipt or single-renderer plan contract is invalid.")
    return {
        "receipt_artifact": receipt_artifact,
        "plan_artifact": plan_artifact,
        "stdout_artifact": stdout_artifact,
        "kit_artifact": kit_artifact,
        "receipt": receipt,
        "plan": plan,
    }


def _validate_supporting_receipts() -> tuple[dict[str, Any], dict[str, Any]]:
    footprint_artifact = _exact_artifact(VULKAN_RECEIPT_PATH, VULKAN_RECEIPT_SHA256, "Vulkan footprint receipt")
    footprint = _read_json(VULKAN_RECEIPT_PATH)
    infra_artifact = _exact_artifact(INFRA_RECEIPT_PATH, INFRA_RECEIPT_SHA256, "infra reclassification receipt")
    infra = _read_json(INFRA_RECEIPT_PATH)
    if (
        footprint.get("schema_version") != "pull_v0_vulkan_enumeration_context_receipt_v1"
        or footprint.get("status") != "MEASURED_INFRASTRUCTURE_CONTEXT"
        or footprint.get("authority", {}).get("sha256") != AUTHORITY_SHA256
        or footprint.get("attempt16_evidence", {}).get("plan", {}).get("sha256") != ATTEMPT16_PLAN_SHA256
        or footprint.get("attempt16_evidence", {}).get("stdout", {}).get("sha256") != ATTEMPT16_STDOUT_SHA256
        or footprint.get("attempt16_evidence", {}).get("kit_log", {}).get("sha256") != ATTEMPT16_KIT_LOG_SHA256
        or footprint.get("attempt16_evidence", {}).get("total_mib_by_physical_index")
        != [168, 136, 136, 140, 236, 136, 136, 136]
        or footprint.get("attempt16_evidence", {}).get("created_delta_mib_by_physical_index")
        != [167, 135, 135, 139, 235, 135, 135, 135]
        or footprint.get("interpretation", {}).get("max_non_leased_delta_mib") != 167
        or footprint.get("interpretation", {}).get("non_leased_stop_threshold_mib") != 1024
        or footprint.get("interpretation", {}).get("max_non_leased_delta_below_one_gib") is not True
    ):
        raise RuntimeError("Vulkan footprint receipt does not preserve the A4/A6 evidence.")
    if (
        infra.get("schema_version") != "pull_v0_p1_infra_reclassification_receipt_v1"
        or infra.get("status") != "INFRASTRUCTURE_RECLASSIFICATION_COMPLETE"
        or infra.get("authority", {}).get("sha256") != AUTHORITY_SHA256
        or infra.get("mapping") != [
            {
                "infra_id": "INFRA_001_HYDRA_KIT_ARGS_TRANSPORT",
                "original_attempt": 15,
                "receipt_path": "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT15_RECEIPT.json",
                "receipt_sha256": ATTEMPT15_RECEIPT_SHA256,
                "failure_boundary": "BEFORE_FIRST_SIMULATION_STEP",
                "scientific_verdict_consumed": False,
                "anchor_attempt_consumed": False,
                "root_cause": "ATTEMPT15_HYDRA_KIT_ARGS_TRANSPORT_FAILURE",
            },
            {
                "infra_id": "INFRA_002_VULKAN_ENUMERATION_AUTHORIZATION",
                "original_attempt": 16,
                "receipt_path": "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT16_RECEIPT.json",
                "receipt_sha256": ATTEMPT16_RECEIPT_SHA256,
                "failure_boundary": "BEFORE_FIRST_SIMULATION_STEP",
                "scientific_verdict_consumed": False,
                "anchor_attempt_consumed": False,
                "root_cause": "BARE_METAL_VULKAN_DEVICE_VISIBILITY_EXCEEDS_GPU_LEASE",
            },
        ]
        or infra.get("retry_accounting", {}).get("next_scientific_anchor_attempt") != 17
    ):
        raise RuntimeError("Infrastructure reclassification mapping is invalid.")
    return (
        {"artifact": footprint_artifact, "receipt": footprint},
        {"artifact": infra_artifact, "receipt": infra},
    )


def _changed_files() -> dict[str, dict[str, Any]]:
    paths = {
        "scriptsFORhuman/pull_v0/PULL_V0_VULKAN_ENUMERATION_CONTEXT_RECEIPT.json": (
            "Record the one-time Attempt16 per-device Vulkan enumeration footprint."
        ),
        "scriptsFORhuman/pull_v0/PULL_V0_P1_INFRA_RECLASSIFICATION_RECEIPT.json": (
            "Map Attempts15/16 to immutable INFRA sequence entries under Amendment 6."
        ),
        "scriptsFORhuman/pull_v0/build_pull_v0_gpu_lease_amendment_receipt.py": (
            "Build and validate the A4/A6 amendment preparation receipt."
        ),
        "gr00t/rl/tests/test_a2_pull_namespace.py": (
            "Guard the A4/A6 receipt chain, GPU2 lease, and Attempt17 preparation contract."
        ),
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": (
            "Rebind future Attempt17 preparation to the amended GPU2/3 lease; excluded to avoid receipt hash self-cycle."
        ),
        "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": (
            "Validate the amended Attempt17 receipt ancestry; excluded to avoid receipt hash self-cycle."
        ),
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
                "hash_binding": "EXCLUDED_TO_AVOID_AMENDMENT_RECEIPT_SHA_SELF_CYCLE",
            }
        else:
            path = ROOT / relative
            result[relative] = {
                "pre_sha256": None,
                "post_sha256": _sha256(path) if path.is_file() else None,
                "reason": reason,
            }
    return result


def build_amendment_receipt() -> dict[str, Any]:
    authority = _validate_authority()
    parent = _validate_r14_parent()
    attempt16 = _validate_attempt16_receipt()
    footprint, infra = _validate_supporting_receipts()
    return {
        "schema_version": AMENDMENT_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "amendment_revision": AMENDMENT_REVISION,
        "repair_revision": AMENDMENT_REVISION,
        "status": "APPROVED_FOR_ATTEMPT17_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "authority": authority,
        "parent_receipt": {
            "path": parent["artifact"]["path"],
            "sha256": parent["artifact"]["sha256"],
            "repair_revision": R14_REVISION,
        },
        "amendments": {
            "amendment4_compute_authorized_physical_devices": [2, 3],
            "amendment4_selected_physical_device": 2,
            "amendment4_revoked_physical_devices": [4, 5, 6],
            "amendment5_incidental_vulkan_enumeration_authorized_on_visible_devices": True,
            "amendment5_no_compute_on_non_leased_devices": True,
            "amendment5_container_isolation_authorized": False,
            "amendment5_container_isolation_required": False,
            "amendment6_attempt15_infra_id": "INFRA_001_HYDRA_KIT_ARGS_TRANSPORT",
            "amendment6_attempt16_infra_id": "INFRA_002_VULKAN_ENUMERATION_AUTHORIZATION",
            "amendment6_next_scientific_attempt": 17,
        },
        "trigger": {
            "attempt16": {
                "receipt": attempt16["receipt_artifact"],
                "plan": attempt16["plan_artifact"],
                "stdout": attempt16["stdout_artifact"],
                "kit_log": attempt16["kit_artifact"],
            },
            "one_time_vulkan_footprint_receipt": footprint["artifact"],
            "infra_reclassification_receipt": infra["artifact"],
        },
        "scope": {
            "r14_parent_immutable": True,
            "attempt15_and_16_receipts_preserved": True,
            "attempt15_and_16_anchor_attempts_consumed": False,
            "attempt17_prepared": False,
            "attempt17_runtime_executed": False,
            "product_mechanics_changed": False,
            "fixture_changed": False,
            "thresholds_or_timeouts_changed": False,
            "p1_p2_gates_changed": False,
        },
        "attempt17_preparation_contract": {
            "authorized_compute_physical_devices": [2, 3],
            "selected_physical_device": 2,
            "unauthorized_compute_physical_devices": [0, 1, 4, 5, 6, 7],
            "cuda_device": "cuda:2",
            "cuda_visible_devices": "UNSET",
            "renderer_multi_gpu_enabled": False,
            "renderer_multi_gpu_auto_enable": False,
            "renderer_multi_gpu_max_gpu_count": 1,
            "kit_args": SINGLE_GPU_KIT_ARGS,
            "hydra_override": "+a2_pull_v0_renderer_single_gpu=true",
            "transport": "Hydra boolean -> args_cli.multi_gpu/kit_args",
            "incidental_vulkan_contexts_authorized_on_all_visible_devices": True,
            "no_compute_on_non_leased_devices": True,
            "container_isolation_authorized": False,
            "container_isolation_required": False,
            "per_run_launch_occupancy_receipt_required": True,
            "steady_state_footprint_receipt_required": True,
            "infrastructure_to_anchor_transition": "first_simulation_step",
            "anchor_verdict_required_after_transition": True,
        },
        "evidence": {
            "authority": authority,
            "r14_parent": parent["artifact"],
            "attempt16_receipt": attempt16["receipt_artifact"],
            "attempt16_plan": attempt16["plan_artifact"],
            "attempt16_stdout": attempt16["stdout_artifact"],
            "attempt16_kit_log": attempt16["kit_artifact"],
            "vulkan_footprint_receipt": footprint["artifact"],
            "infra_reclassification_receipt": infra["artifact"],
            "max_non_leased_delta_mib": 167,
            "non_leased_stop_threshold_mib": 1024,
            "supporting_v21_inference_mib": 145,
            "supporting_v21_inference_role": "CORROBORATING_CONTEXT_ONLY_NOT_PROOF",
        },
        "changed_files": _changed_files(),
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "A4/A6 authority, receipt, footprint, and infrastructure mapping hash checks",
                "Attempt17 GPU2/Hydra argv and no-plan/no-runtime checks",
                "git diff --check",
            ],
            "runtime_not_run_reason": (
                "This amendment authorizes Attempt17 preparation only; no Attempt17 plan, IsaacSim, GPU, "
                "or anchor runtime was executed."
            ),
        },
        "acceptance": {
            "authority_sha_exact": True,
            "r14_parent_exact": True,
            "attempt15_infra_mapping_exact": True,
            "attempt16_infra_mapping_exact": True,
            "vulkan_footprint_exact": True,
            "max_non_leased_delta_below_1gib": True,
            "gpu2_selected": True,
            "gpu2_gpu3_compute_lease_exact": True,
            "gpu4_gpu5_gpu6_lease_revoked": True,
            "hydra_boolean_transport_preserved": True,
            "single_renderer_contract_preserved": True,
            "attempt17_preparation_only": True,
            "attempt17_not_prepared_or_run": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No Attempt17 anchor, physics, GPU, or IsaacSim runtime verdict is asserted.",
            "No reviewer, memory, staging, commit, P1 matrix, or P2 gate is cleared by this amendment.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable A4/A6 GPU-lease amendment receipt.")
    parser.add_argument("--output", type=Path, default=AMENDMENT_RECEIPT_PATH)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    _write_once(output, build_amendment_receipt())
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
