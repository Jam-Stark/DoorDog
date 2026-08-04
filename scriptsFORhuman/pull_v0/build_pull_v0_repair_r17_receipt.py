#!/usr/bin/env python3
"""Build the immutable R17 preparation-only repair receipt."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Final, TypeAlias
from zoneinfo import ZoneInfo


ROOT: Final = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT: Final = ROOT / "scriptsFORhuman" / "pull_v0"
R16_PATH: Final = EVIDENCE_ROOT / "PULL_V0_REPAIR_R16_RECEIPT.json"
ATTEMPT19_PATH: Final = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_RECEIPT.json"
OUTPUT_PATH: Final = EVIDENCE_ROOT / "PULL_V0_REPAIR_R17_RECEIPT.json"
R16_SHA256: Final = "cf0d7107062bf8558adf4c64aaee03f91625950bdcaf2e1ee1d767883da1787e"
ATTEMPT19_SHA256: Final = "4f92eba02f157158803f3df7b031e865bdefccc6a5d9ea969e1cf43eaaa536cd"
FAILURE_SIGNATURE: Final = "RuntimeError: Attempt19 nonselected GPU0 compute-apps contains the Attempt19 PID."
JsonScalar: TypeAlias = str | int | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class ReceiptBuildError(RuntimeError):
    """Raised when R17 receipt inputs do not match their immutable contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path: Path, expected_sha256: str) -> JsonObject:
    if not path.is_file() or path.is_symlink():
        raise ReceiptBuildError(f"Expected a regular immutable artifact: {path}")
    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        raise ReceiptBuildError(
            f"Immutable artifact SHA-256 mismatch for {path}: "
            f"expected={expected_sha256}, actual={actual_sha256}"
        )
    return {"path": str(path.relative_to(ROOT)), "sha256": actual_sha256}


def _read_json(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReceiptBuildError(f"Expected a JSON object: {path}")
    return value


def _validate_parents() -> tuple[JsonObject, JsonObject]:
    r16 = _read_json(R16_PATH)
    attempt19 = _read_json(ATTEMPT19_PATH)
    if r16.get("schema_version") != "pull_v0_repair_r16_receipt_v1":
        raise ReceiptBuildError("R17 requires the canonical R16.4 receipt schema.")
    if r16.get("revision_detail") != "R16.4":
        raise ReceiptBuildError("R17 requires parent revision R16.4.")
    if attempt19.get("status") != "PROBE_INVALID":
        raise ReceiptBuildError("R17 requires an Attempt19 PROBE_INVALID receipt.")
    if attempt19.get("scientific_verdict_consumed") is not False:
        raise ReceiptBuildError("R17 cannot chain an Attempt19 receipt that consumed a scientific verdict.")
    runtime_failure = attempt19.get("runtime_failure")
    if not isinstance(runtime_failure, dict) or runtime_failure.get("exact_message") != FAILURE_SIGNATURE:
        raise ReceiptBuildError("R17 Attempt19 parent does not contain the exact capture-admission failure.")
    return r16, attempt19


def _changed_file(path: Path, expected_sha256: str, reason: str) -> JsonObject:
    return {**_artifact(path, expected_sha256), "reason": reason}


def _receipt(parent: JsonObject, attempt19: JsonObject, source_files: JsonObject) -> JsonObject:
    return {
        "schema_version": "pull_v0_repair_r17_receipt_v1",
        "generated_at_hkt": datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT"),
        "repair_revision": "R17",
        "status": "APPROVED_FOR_ATTEMPT20_PREPARATION_ONLY",
        "runtime_validation": "NOT_RUN",
        "scientific_verdict_consumed": False,
        "stale_candidate_id": "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f",
        "parent_receipt": {**parent, "repair_revision": "R16"},
        "trigger": {
            "attempt": 19,
            "attempt19_probe_invalid_receipt": attempt19,
            "root_cause": "ATTEMPT19_EVIDENCE_ADMISSION_ENUMERATION_CLASSIFICATION",
            "exact_failure_signature": FAILURE_SIGNATURE,
        },
        "root_cause": {
            "code": "ATTEMPT19_EVIDENCE_ADMISSION_ENUMERATION_CLASSIFICATION",
            "conclusion": "Attempt19 steady evidence capture failed closed under the R16.4 G-only nonselected rule although the observed footprint was known NVIDIA driver/Kit enumeration behavior: low-memory contexts of the eval PID existed on every visible GPU while selected GPU2 alone computed.",
            "failure_class": "EVIDENCE_ADMISSION_DEFECT",
            "not_a_plant_or_pull_mechanism_verdict": True,
            "physical_plant_cause": "INCONCLUSIVE_NO_PROOF_SAMPLES",
            "source_signature": FAILURE_SIGNATURE,
        },
        "scope": {
            "attempt19_parent_immutable": True,
            "attempt19_artifacts_immutable": True,
            "product_mechanics_changed": False,
            "attempt19_scientific_verdict_consumed": False,
            "attempt20_prepared": False,
            "attempt20_runtime_executed": False,
            "attempt20_artifacts_created": False,
            "fixture_changed": False,
            "thresholds_or_timeouts_changed": False,
            "p1_p2_gates_changed": False,
            "gpu_lease_changed": False,
            "shared_default_capacity_changed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "source_repair": {
            "diff": [
                "Thread attempt identity through shared helper validation labels without changing the strict Attempt19 path.",
                "Classify Attempt20 low-memory same-PID C/G/C+G enumeration contexts as inactive when PMON fields and device utilization satisfy the bound contract.",
                "Add exact Attempt20 runner paths, preparation-only validation, and lifecycle-robust process receipts with honest null/NOT_RECORDED timestamps.",
                "Close Attempt19 with immutable capture-failure and PROBE_INVALID receipts; add focused isolation tests.",
            ],
            "reason": "The repair distinguishes known low-memory enumeration contexts from attempt compute without weakening the historical Attempt19 strict replay rule.",
        },
        "attempt20_preparation_contract": {
            "attempt": 20,
            "next_attempt": 20,
            "context_classification_mode": "LOW_MEMORY_SAME_PID_ENUMERATION_CONTEXTS",
            "process_receipt_on_interrupt_required": True,
            "lifecycle_signal_receipt_required": True,
            "other_tenant_attribution_for_attempt_pid_allowed": False,
            "plan_path": "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_PLAN.json",
            "output_namespace": "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt20",
            "launch_occupancy_path": "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_LAUNCH_OCCUPANCY.json",
            "steady_state_footprint_path": "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_STEADY_STATE_FOOTPRINT.json",
            "launch_occupancy_schema": "pull_v0_p1_attempt20_launch_occupancy_v1",
            "steady_state_footprint_schema": "pull_v0_p1_attempt20_steady_state_footprint_v1",
            "capture_tool": "scriptsFORhuman/pull_v0/capture_p1_anchor_gpu_evidence.py",
            "detailed_contact_capacity": 64,
            "shared_default_detailed_contact_capacity": 8,
            "config_key": "a2_hold_diagnostic_max_contact_data_count_per_prim",
            "selected_compute_physical_device": 2,
            "authorized_compute_physical_devices": [2, 3],
            "gpu7_compute_authorized": False,
            "first_simulation_step_boundary_required": True,
            "runtime_log_contract": {
                "app_launcher_line": "[INFO][AppLauncher]: Using device: cuda:2",
                "environment_device_suffix": "Environment device    : cuda:2",
                "kit_vulkan_tables_active_physical_devices": [2],
                "first_simulation_step_boundary": "Starting evaluation with one episode per environment",
            },
            "pmon_contract": {
                "attempt_gpu_context_classification_mode": "LOW_MEMORY_SAME_PID_ENUMERATION_CONTEXTS",
                "historical_attempt19_mode": "STRICT_G_ONLY_INACTIVE_VULKAN_ENUMERATION",
                "accepted_same_pid_context_types": ["C", "G", "C+G"],
                "same_pid_framebuffer_memory_mib_at_most": 1024,
                "not_reported_metric_policy": "Preserve NOT_REPORTED; never rewrite it to absence or numeric zero.",
                "nonselected_attempt_device_utilization": "exactly zero unless an exact OTHER_TENANT record explains it",
                "tenant_attribution": "OTHER_TENANT evidence remains separate and is never attributed to the attempt PID.",
            },
            "process_identity_contract": {
                "runner_pid_required": True,
                "eval_pid_required_and_live_at_capture": True,
                "module": "gr00t.rl.eval_agent_trl",
                "eval_output_dir": "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt20/eval",
            },
            "lifecycle_contract": {
                "child_wait_timeout_seconds": 600,
                "received_signal_forwarded_to_eval_child": True,
                "sigkill_only_after_child_wait_timeout": True,
                "unknown_timestamps": "null/NOT_RECORDED",
            },
            "runtime_validation": "NOT_RUN",
            "preparation_only": True,
        },
        "changed_files": {
            **source_files,
            "scriptsFORhuman/pull_v0/build_pull_v0_repair_r17_receipt.py": {"hash_binding": "EXCLUDED_TO_AVOID_R17_RECEIPT_SHA_SELF_CYCLE"},
            "scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R17_RECEIPT.json": {"hash_binding": "EXCLUDED_TO_AVOID_R17_RECEIPT_SHA_SELF_CYCLE"},
        },
        "validation": {
            "static": "PASS",
            "runtime": "NOT_RUN",
            "runtime_not_run_reason": "R17 authorizes Attempt20 preparation only; no Attempt20 plan, output, IsaacSim, GPU, or scientific runtime was created or executed.",
        },
        "acceptance": {
            "r16_4_parent_hash_bound": True,
            "attempt19_probe_invalid_hash_bound": True,
            "attempt19_evidence_admission_defect_recorded": True,
            "attempt20_preparation_only": True,
            "attempt20_enumeration_contract_bound": True,
            "attempt20_lifecycle_contract_bound": True,
            "runtime_pass_asserted": False,
        },
        "evidence_summary": {
            "attempt19_probe_validity": "PROBE_INVALID",
            "attempt19_anchor_verdict": "NOT_ASSESSED",
            "attempt19_pull_mechanism_verdict": "NOT_ASSESSED",
            "attempt19_scientific_verdict_consumed": False,
            "attempt19_physical_plant_cause": "INCONCLUSIVE_NO_PROOF_SAMPLES",
        },
        "unverified_claims": [
            "No Attempt20 runtime result or scientific verdict is asserted.",
            "R17 authorizes Attempt20 preparation only.",
            "Anchor-admission reruns do not consume the one-shot scientific verdict.",
            "The physical plant cause remains INCONCLUSIVE_NO_PROOF_SAMPLES.",
        ],
    }


def _write_json(path: Path, value: JsonObject) -> None:
    if path.exists():
        raise ReceiptBuildError(f"Refusing to overwrite immutable receipt: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    r16_artifact = _artifact(R16_PATH, R16_SHA256)
    attempt19_artifact = _artifact(ATTEMPT19_PATH, ATTEMPT19_SHA256)
    _validate_parents()
    source_files: JsonObject = {
        "scriptsFORhuman/pull_v0/capture_p1_anchor_gpu_evidence.py": _changed_file(EVIDENCE_ROOT / "capture_p1_anchor_gpu_evidence.py", "d0b8cb6c7d8447de7af6fbc1d7af9d71f820e72830b8cdae21c9017c2bb2f772", "Attempt-label threading and Attempt20 enumeration classification completion."),
        "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": _changed_file(EVIDENCE_ROOT / "run_p1_push_anchor.py", "2c48b43a21013e105213b56c52c2a84aca97e6dde676bad14c0f03e9e26301d6", "Exact Attempt20 support and lifecycle-robust process receipt."),
        "scriptsFORhuman/pull_v0/build_attempt19_capture_failure_receipts.py": _changed_file(EVIDENCE_ROOT / "build_attempt19_capture_failure_receipts.py", "c7edac58c2e6a818d9618283ed516e996d19760802e1dab02a225474fa363757", "Attempt19 capture-failure and PROBE_INVALID receipt builder."),
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_CAPTURE_FAILURE.json": _changed_file(EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_CAPTURE_FAILURE.json", "6fab55d01f9e0763167121c48fb54a16e5e4cf4c0eb970bed1a40c837f0b70bc", "Immutable Attempt19 capture-admission failure evidence."),
        "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_RECEIPT.json": _changed_file(ATTEMPT19_PATH, ATTEMPT19_SHA256, "Canonical Attempt19 PROBE_INVALID receipt."),
        "gr00t/rl/tests/test_a2_pull_namespace.py": _changed_file(ROOT / "gr00t" / "rl" / "tests" / "test_a2_pull_namespace.py", "38864b7056e38955a7f919276b9cc8d43f5549326f78facf12aa25d1a993f1f1", "Focused Attempt19 immutability and Attempt20 admission/lifecycle coverage."),
    }
    _write_json(OUTPUT_PATH, _receipt(r16_artifact, attempt19_artifact, source_files))
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
