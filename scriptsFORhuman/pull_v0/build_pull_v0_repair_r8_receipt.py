#!/usr/bin/env python3
"""Build the immutable R8 canonical-root-quaternion repair receipt."""

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


R7_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R7_RECEIPT.json"
R7_RECEIPT_SHA256 = "a5f576c06718b145e992bd4927384efae9e7b8714f6f8b87836914da6c702b5f"
R7_REVISION = "R7"
R8_REVISION = "R8"
R8_SCHEMA = "pull_v0_repair_r8_receipt_v1"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"

ATTEMPT9_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_RECEIPT.json"
ATTEMPT9_RECEIPT_SHA256 = "286fa3b832911ce3530b17696049b0a5e9d5584bf78e5199d1506c208b043624"
ATTEMPT9_INVALIDATION_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_INVALIDATION.json"
ATTEMPT9_INVALIDATION_SHA256 = "ad21ae10c7f443fea640f195dfa5806eedfbb7374a740785c0b80d546d5eda1a"
ATTEMPT9_RESPONSE_TELEMETRY_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_RESPONSE_TELEMETRY.json"
ATTEMPT9_RESPONSE_TELEMETRY_SHA256 = "653a599a83e386251ee1a7dc98d51b93e3a474123569565ff311b1d99af9e937"

ATTEMPT9_ARTIFACTS = {
    "plan": (
        EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_PLAN.json",
        "460dd1fcbb0e51d080db730bbf0f020f5ec56d5d76468f8f48bfe322039cc2a8",
    ),
    "process_receipt": (
        LOG_ROOT / "attempt9/process_receipt.json",
        "830246b8cd9cec9d5ac0adb7eaaec92e43bae0d664ef7dcd3caf3aa6c577c12f",
    ),
    "log": (
        LOG_ROOT / "attempt9/stdout_stderr.log",
        "6aa8ffe29f219d62ae82faac4dfb17034a012cc09f5203b26d9a3ddd148f16a7",
    ),
    "summary": (
        LOG_ROOT / "attempt9/eval/a2_hold_oracle_summary.json",
        "cdd72c25960b68377a49285c2a3342468e3cc191b9b431d17779310eeb2903b1",
    ),
    "metrics": (
        LOG_ROOT / "attempt9/eval/metrics_eval.json",
        "5f89f0d2bfbd99853e823273277d297b21ba48af424ec15405f2f8470cebe178",
    ),
}


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing R8 receipt: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _exact_artifact(path: Path, expected_sha256: str, label: str) -> dict[str, str]:
    artifact = _artifact(path)
    if artifact["sha256"] != expected_sha256:
        raise RuntimeError(
            f"{label} hash changed: expected={expected_sha256}, actual={artifact['sha256']}"
        )
    return artifact


def _validate_r7_parent() -> dict[str, Any]:
    artifact = _exact_artifact(R7_RECEIPT_PATH, R7_RECEIPT_SHA256, "R7 parent receipt")
    receipt = _read_json(R7_RECEIPT_PATH)
    if (
        receipt.get("schema_version") != "pull_v0_repair_r7_receipt_v1"
        or receipt.get("repair_revision") != R7_REVISION
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
    ):
        raise RuntimeError("R7 parent receipt identity is invalid.")
    return {"artifact": artifact, "receipt": receipt}


def _validate_attempt9_flawed_receipt() -> dict[str, Any]:
    artifact = _exact_artifact(
        ATTEMPT9_RECEIPT_PATH, ATTEMPT9_RECEIPT_SHA256, "immutable Attempt9 receipt"
    )
    receipt = _read_json(ATTEMPT9_RECEIPT_PATH)
    command_response = receipt.get("command_to_plant_response")
    if (
        receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v9"
        or receipt.get("attempt") != 9
        or receipt.get("status") != "BLOCKED"
        or receipt.get("probe_validity") != "PROBE_INVALID"
        or receipt.get("runtime_validation") != "UNVERIFIED"
        or not isinstance(command_response, Mapping)
        or command_response.get("status") != "CAPTURED"
        or command_response.get("reason") is not None
    ):
        raise RuntimeError("Immutable Attempt9 receipt does not preserve the expected flawed payload.")
    return {"artifact": artifact, "receipt": receipt}


def _validate_attempt9_invalidation() -> dict[str, Any]:
    artifact = _exact_artifact(
        ATTEMPT9_INVALIDATION_PATH,
        ATTEMPT9_INVALIDATION_SHA256,
        "Attempt9 invalidation manifest",
    )
    manifest = _read_json(ATTEMPT9_INVALIDATION_PATH)
    reasons = manifest.get("reasons")
    expected_codes = {
        "NULL_NORMALIZED_RESPONSE",
        "STATIC_ONLY_RUNTIME_WORDING_AFTER_VALIDATED_RUNTIME",
        "DROPPED_RUNTIME_IDENTITY_AND_AGGREGATE_EVIDENCE",
    }
    if (
        manifest.get("schema_version") != "pull_v0_p1_push_anchor_attempt_invalidation_v2"
        or manifest.get("status") != "SUPERSEDED_INVALID"
        or manifest.get("attempt") != 9
        or manifest.get("receipt") != {
            "path": str(ATTEMPT9_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": ATTEMPT9_RECEIPT_SHA256,
        }
        or not isinstance(reasons, list)
        or {item.get("code") for item in reasons if isinstance(item, Mapping)} != expected_codes
        or any(not isinstance(item, Mapping) or not isinstance(item.get("evidence"), str) for item in reasons)
    ):
        raise RuntimeError("Attempt9 invalidation manifest identity or reasons are invalid.")
    replacement = manifest.get("replacement")
    if (
        not isinstance(replacement, Mapping)
        or replacement.get("runtime_validation") != "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY"
        or replacement.get("mechanism_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("Attempt9 invalidation replacement contract is invalid.")
    return {"artifact": artifact, "manifest": manifest}


def _validate_attempt9_artifacts() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for label, (path, expected_sha256) in ATTEMPT9_ARTIFACTS.items():
        result[label] = _exact_artifact(path, expected_sha256, f"Attempt9 {label} artifact")
    return result


def _validate_normalized_response(
    summary: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    artifact = _exact_artifact(
        ATTEMPT9_RESPONSE_TELEMETRY_PATH,
        ATTEMPT9_RESPONSE_TELEMETRY_SHA256,
        "Attempt9 normalized response telemetry",
    )
    normalized = _read_json(ATTEMPT9_RESPONSE_TELEMETRY_PATH)
    admission = _validate_actual_push_anchor_schema(
        summary=summary,
        metrics=metrics,
        require_stage0_response=True,
    )
    response_summary = admission["stage0_command_response"]
    normalized_summary = normalized.get("response_summary")
    expected_summary = {
        key: response_summary.get(key)
        for key in (
            "schema",
            "status",
            "threshold_mode",
            "response_count",
            "anti_alignment_count",
            "max_observed_world_xy_speed_mps",
            "max_observed_world_xy_displacement_m",
            "min_progress_velocity_cosine",
            "min_progress_displacement_cosine",
        )
    }
    if normalized_summary != expected_summary:
        raise RuntimeError("Attempt9 normalized response aggregates differ from runtime summary.")
    first = response_summary["first_response"]
    terminal = response_summary["terminal_response"]

    def identity(response: Mapping[str, Any]) -> dict[str, int]:
        return {
            key: response[key]
            for key in (
                "episode_generation",
                "trace_row_index",
                "control_step",
                "response_control_step",
            )
        }

    if (
        normalized.get("schema_version") != "pull_v0_p1_push_anchor_attempt9_response_telemetry_v1"
        or normalized.get("attempt") != 9
        or normalized.get("status") != "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY"
        or normalized.get("runtime_validation") != "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY"
        or normalized.get("mechanism_verdict") != "NOT_ASSESSED"
        or normalized.get("threshold_mode") != "report_only"
        or normalized.get("first_response_identity") != identity(first)
        or normalized.get("terminal_response_identity") != identity(terminal)
        or normalized.get("artifacts", {}).get("attempt9_receipt", {}).get("sha256")
        != ATTEMPT9_RECEIPT_SHA256
        or normalized.get("artifacts", {}).get("repair_r7", {}).get("sha256")
        != R7_RECEIPT_SHA256
    ):
        raise RuntimeError("Attempt9 normalized response telemetry identity is invalid.")
    return {"artifact": artifact, "telemetry": normalized}


def _bound_changed_files() -> dict[str, dict[str, Any]]:
    paths: dict[str, dict[str, Any]] = {
        "gr00t/rl/envs/door/door_open_a2_base.py": {
            "pre_sha256": "3c096ab037f065c27b4d240f884b8b982fe27d148d1acfddd789cb39869988ef",
            "reason": "Use canonical IsaacLab ArticulationData.root_quat_w (WXYZ) for stage0 admission and trace yaw while retaining root position and signed target geometry.",
        },
        "gr00t/rl/tests/test_a2_pull_namespace.py": {
            "pre_sha256": "828f8f196551306957bf3688bd719e6381c4d94800302ff1354f1a1a3e495d77",
            "reason": "Guard the stage0 canonical quaternion callsite and R8 ancestry/invalidation contracts.",
        },
        "gr00t/rl/tests/test_a2_pull_telemetry.py": {
            "pre_sha256": "e07d11a97d417607ba8c6c5e0c1f72ca7ec2c77a714eccb330bc2404004cf156",
            "reason": "Verify yaw-zero and yaw-pi body/world stage0 command reprojection semantics.",
        },
        "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": {
            "pre_sha256": None,
            "reason": "Normalize validated R7+ response identities and aggregates in later timeout receipts.",
            "hash_binding": "EXCLUDED_TO_AVOID_R8_RECEIPT_SHA_SELF_CYCLE",
        },
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": {
            "pre_sha256": None,
            "reason": "Bind Attempt10+ preparation to the exact R8 receipt and the immutable Attempt9 invalidation/telemetry chain.",
            "hash_binding": "EXCLUDED_TO_AVOID_R8_RECEIPT_SHA_SELF_CYCLE",
        },
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r8_receipt.py": {
            "pre_sha256": None,
            "reason": "Build the immutable R8 canonical-root-quaternion repair receipt.",
        },
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_INVALIDATION.json": {
            "pre_sha256": None,
            "reason": "Preserve the flawed Attempt9 receipt byte-identically as superseded invalid evidence.",
        },
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_RESPONSE_TELEMETRY.json": {
            "pre_sha256": None,
            "reason": "Preserve normalized validated Attempt9 response aggregates and boundary identities.",
        },
        "scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R8_RECEIPT.json": {
            "pre_sha256": None,
            "post_sha256": None,
            "reason": "Immutable R8 receipt output; its own post-hash is intentionally not self-bound.",
            "hash_binding": "EXCLUDED_TO_AVOID_R8_RECEIPT_SHA_SELF_CYCLE",
        },
    }
    result: dict[str, dict[str, Any]] = {}
    for relative, data in paths.items():
        path = ROOT / relative
        if relative.endswith("PULL_V0_REPAIR_R8_RECEIPT.json"):
            result[relative] = dict(data)
            continue
        artifact = _artifact(path)
        item = {
            "pre_sha256": data.get("pre_sha256"),
            "post_sha256": artifact["sha256"],
            "reason": data["reason"],
        }
        if "hash_binding" in data:
            item["hash_binding"] = data["hash_binding"]
            if data["hash_binding"].startswith("EXCLUDED"):
                item["post_sha256"] = None
        result[relative] = item
    return result


def build_r8_receipt() -> dict[str, Any]:
    parent = _validate_r7_parent()
    flawed = _validate_attempt9_flawed_receipt()
    invalidation = _validate_attempt9_invalidation()
    attempt9_artifacts = _validate_attempt9_artifacts()
    summary = _read_json(ATTEMPT9_ARTIFACTS["summary"][0])
    metrics = _read_json(ATTEMPT9_ARTIFACTS["metrics"][0])
    normalized = _validate_normalized_response(summary, metrics)
    return {
        "schema_version": R8_SCHEMA,
        "generated_at_hkt": _hkt_now(),
        "repair_revision": R8_REVISION,
        "status": "APPROVED_FOR_ATTEMPT10_PREPARATION_ONLY",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "root_cause": {
            "code": "STAGE0_ROOT_QUATERNION_SOURCE_MISMATCH",
            "conclusion": "P1 stage0 command and trace yaw must consume the canonical IsaacLab ArticulationData.root_quat_w WXYZ tensor; robot_root_states[:, 3:7] is a legacy XYZW slice and cannot be passed to WXYZ yaw/euler math.",
            "canonical_source": "self.simulator.scene.articulations[\"robot\"].data.root_quat_w",
            "canonical_order": "WXYZ",
            "legacy_source_forbidden": "self.simulator.robot_root_states[:, 3:7]",
            "signed_target_and_band_unchanged": True,
            "stage0_timeout_unchanged": True,
        },
        "parent_receipt": {
            "path": parent["artifact"]["path"],
            "sha256": parent["artifact"]["sha256"],
            "repair_revision": R7_REVISION,
        },
        "trigger": {
            "attempt": 9,
            "root_cause": "ATTEMPT9_QUATERNION_SOURCE_AND_RECEIPT_NORMALIZATION",
            "attempt_receipt": flawed["artifact"],
            "invalidation_manifest": invalidation["artifact"],
            "normalized_response_telemetry": normalized["artifact"],
            "immutable_runtime_artifacts": attempt9_artifacts,
        },
        "scope": {
            "authorized": "Replace only the P1 stage0/trace quaternion source with canonical WXYZ ArticulationData telemetry and normalize the immutable Attempt9 response evidence; preserve signed geometry, command scaling, timeout, stage ordering, and mechanism semantics.",
            "attempt9_immutable": True,
            "attempt10_prepared": False,
            "gpu_or_isaacsim_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "implementation_contract": {
            "stage0_root_position_source": "existing simulator.robot_root_states[:, :3] root position retained",
            "stage0_root_quaternion_source": "self.simulator.scene.articulations[\"robot\"].data.root_quat_w",
            "quaternion_order": "WXYZ",
            "strict_contract": "shape (num_envs, 4), floating, root-state dtype/device, finite",
            "trace_rpy_source": "the same validated stage0_root_quat_w tensor",
            "target_band_direction_scale_timeout_unchanged": True,
            "attempt9_response_schema": "a2_piper_pull_v0_stage0_command_response_summary_v2",
            "attempt9_response_validation": "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY",
            "threshold_mode": "report_only",
        },
        "changed_files": _bound_changed_files(),
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "stage0 yaw-zero/yaw-pi consumer tests and structural source test",
                "strict R7+ 120-row response-schema validator",
                "Attempt10 runner SHA/ancestry fail-fast tests",
                "receipt/hash assertions",
                "git diff --check",
            ],
            "runtime_not_run_reason": "R8 is CPU/static preparation only; no Attempt10 preparation or IsaacSim/GPU runtime was authorized.",
        },
        "acceptance": {
            "canonical_articulation_root_quat_w_stage0_callsite": True,
            "canonical_articulation_root_quat_w_trace_rpy": True,
            "legacy_robot_root_states_quaternion_slice_forbidden": True,
            "yaw_zero_world_xy_reprojection": True,
            "yaw_pi_world_xy_reprojection": True,
            "signed_target_band_direction_scale_timeout_unchanged": True,
            "attempt9_receipt_byte_identical_and_superseded": True,
            "attempt9_normalized_response_identity_and_aggregates_preserved": True,
            "r7_parent_and_attempt9_full_ancestry_bound": True,
            "attempt10_runner_exact_r8_sha_and_ancestry": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim/GPU runtime PASS is asserted for R8.",
            "No Attempt10 preparation or runtime was executed.",
            "No pull-mechanism verdict is asserted.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the immutable R8 pull-v0 repair receipt.")
    parser.add_argument(
        "--output",
        type=Path,
        default=EVIDENCE_ROOT / "PULL_V0_REPAIR_R8_RECEIPT.json",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    _write_once(output, build_r8_receipt())
    print(f"Wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
