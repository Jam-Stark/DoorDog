#!/usr/bin/env python3
"""Build immutable Attempt19 capture-failure evidence and its canonical receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, TypeAlias


ROOT: Final = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT: Final = ROOT / "scriptsFORhuman" / "pull_v0"
LOG_ROOT: Final = ROOT / "logs_eval" / "a2_piper_pull_v0" / "p1_push_anchor" / "attempt19"
PLAN_PATH: Final = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_PLAN.json"
LAUNCH_PATH: Final = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_LAUNCH_OCCUPANCY.json"
LOG_PATH: Final = LOG_ROOT / "stdout_stderr.log"
CAPTURE_FAILURE_PATH: Final = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_CAPTURE_FAILURE.json"
RECEIPT_PATH: Final = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_RECEIPT.json"
PLAN_SHA256: Final = "cf23ee03ec0c40e77582ec724d8c6d8855cebcd40791edb7c8d11e75d9800748"
LAUNCH_SHA256: Final = "035303242c307856a54bb3eabe09c391d75cca936f9a437946af4f938e2d08b8"
LOG_SHA256: Final = "2614844d86965bf648874d06360100e4997f8ecc49bf6d1a730dc7f0272bcbdc"
FAILURE_TIMESTAMP: Final = "2026-08-04 22:19:50 HKT"
FAILURE_MESSAGE: Final = "RuntimeError: Attempt19 nonselected GPU0 compute-apps contains the Attempt19 PID."
BOUNDARY_LINE: Final = "Starting evaluation with one episode per environment"
JsonScalar: TypeAlias = str | int | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class ReceiptBuildError(RuntimeError):
    """Raised when immutable Attempt19 evidence violates the receipt contract."""


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


def _verify_log_boundary() -> None:
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    if len(lines) != 621:
        raise ReceiptBuildError(f"Attempt19 log has {len(lines)} lines, expected 621.")
    if lines[-1] != BOUNDARY_LINE:
        raise ReceiptBuildError("Attempt19 log does not end at the required evaluation boundary.")


def _absence(path: Path) -> JsonObject:
    if path.exists():
        raise ReceiptBuildError(f"Attempt19 capture-failure receipt requires absent artifact: {path}")
    return {"path": str(path.relative_to(ROOT)), "present": False, "value": None, "status": "N/A"}


def _footprint_device(
    index: int,
    process_type: str,
    framebuffer_memory_mib: int,
    device_utilization_percent: int,
    sm_utilization_percent: int | None,
    memory_utilization_percent: int | None,
) -> JsonObject:
    return {
        "physical_device": index,
        "attempt_eval_pid": 2219040,
        "compute_app_present": True,
        "process_type": process_type,
        "framebuffer_memory_mib": framebuffer_memory_mib,
        "sm_utilization_percent": sm_utilization_percent,
        "sm_utilization_status": "REPORTED" if sm_utilization_percent is not None else "NOT_REPORTED",
        "memory_utilization_percent": memory_utilization_percent,
        "memory_utilization_status": "REPORTED" if memory_utilization_percent is not None else "NOT_REPORTED",
        "device_utilization_percent": device_utilization_percent,
    }


def _capture_failure(plan: JsonObject, launch: JsonObject, log: JsonObject) -> JsonObject:
    return {
        "schema_version": "pull_v0_p1_attempt19_capture_failure_v1",
        "generated_at_hkt": FAILURE_TIMESTAMP,
        "attempt": 19,
        "status": "PROBE_INVALID",
        "probe_validity": "PROBE_INVALID",
        "anchor_verdict": "NOT_ASSESSED",
        "pull_verdict": "NOT_ASSESSED",
        "scientific_verdict_consumed": False,
        "failure": {
            "observation_timestamp_hkt": FAILURE_TIMESTAMP,
            "exact_message": FAILURE_MESSAGE,
            "classification": "EVIDENCE_ADMISSION_FAILURE",
        },
        "immutable_evidence": {
            "plan": plan,
            "launch_occupancy": launch,
            "runtime_stdout": {**log, "total_lines": 621, "terminal_line_number": 621, "terminal_line": BOUNDARY_LINE, "ends_at_boundary": True},
        },
        "process_lifecycle": {
            "runner_pid": 2219008,
            "eval_pid": 2219040,
            "runner_stopped": True,
            "eval_stopped": True,
            "runner_fully_reaped": True,
            "eval_fully_reaped": True,
            "parent_termination": "KeyboardInterrupt before process_receipt.json was written",
            "stop_signal_timestamp_hkt": None,
            "stop_signal_timestamp_status": "NOT_RECORDED",
        },
        "capture_failure_footprint": {
            "observation": "The compute-app query listed eval PID 2219040 on every physical GPU.",
            "per_device": [
                _footprint_device(0, "C", 168, 0, None, None),
                _footprint_device(1, "C", 136, 0, None, None),
                _footprint_device(2, "C+G", 3083, 17, 16, 0),
                _footprint_device(3, "C+G", 140, 0, None, None),
                _footprint_device(4, "C", 136, 0, None, None),
                _footprint_device(5, "C", 136, 0, None, None),
                _footprint_device(6, "C", 136, 0, None, None),
                _footprint_device(7, "C", 136, 0, None, None),
            ],
            "interpretation": "Known Isaac/driver behavior created low-memory enumeration contexts on every visible GPU; selected GPU2 alone performed compute.",
            "selected_compute_physical_device": 2,
            "authorized_compute_physical_devices": [2, 3],
        },
        "absent_artifacts": {
            "process_receipt": _absence(LOG_ROOT / "process_receipt.json"),
            "summary": _absence(LOG_ROOT / "eval" / "a2_hold_oracle_summary.json"),
            "metrics": _absence(LOG_ROOT / "eval" / "metrics_eval.json"),
            "steady_state_footprint": _absence(EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_STEADY_STATE_FOOTPRINT.json"),
            "canonical_receipt_at_capture_failure_time": {"path": str(RECEIPT_PATH.relative_to(ROOT)), "present": False, "value": None, "status": "N/A"},
        },
        "classification_note": "Reaching the evaluation boundary does not convert a failed evidence-admission attempt into an anchor or scientific verdict.",
        "unverified_claims": [
            "No process receipt, summary, metrics, or steady-state footprint exists for Attempt19.",
            "No anchor, pull-mechanism, or scientific outcome is asserted.",
            "The stop-signal timestamp was not recorded and is represented as null.",
        ],
    }


def _receipt(plan: JsonObject, launch: JsonObject, log: JsonObject, capture_failure: JsonObject) -> JsonObject:
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v19",
        "generated_at_hkt": FAILURE_TIMESTAMP,
        "attempt": 19,
        "status": "PROBE_INVALID",
        "probe_validity": "PROBE_INVALID",
        "runtime_validation": "INVALIDATED_AT_CAPTURE_ADMISSION",
        "anchor_verdict": "NOT_ASSESSED",
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "scientific_verdict_consumed": False,
        "artifacts": {
            "plan": plan,
            "launch_occupancy": launch,
            "log": {**log, "total_lines": 621, "terminal_line_number": 621, "terminal_line": BOUNDARY_LINE},
            "capture_failure": capture_failure,
            "process_receipt": None,
            "summary": None,
            "metrics": None,
            "steady_state_footprint": None,
        },
        "runtime_failure": {
            "root_cause_code": "ATTEMPT19_NONSELECTED_GPU_COMPUTE_APP_ADMISSION_FAILURE",
            "exact_message": FAILURE_MESSAGE,
            "observation_timestamp_hkt": FAILURE_TIMESTAMP,
            "first_simulation_step_boundary_crossed": True,
            "scientific_attempt_started": True,
            "evidence_admission_passed": False,
            "scientific_verdict_consumed": False,
        },
        "termination": {
            "runner_pid": 2219008,
            "eval_pid": 2219040,
            "runner_fully_reaped": True,
            "eval_fully_reaped": True,
            "parent_termination": "KeyboardInterrupt before process_receipt.json was written",
            "stop_signal_timestamp_hkt": None,
            "stop_signal_timestamp_status": "NOT_RECORDED",
        },
        "required_telemetry": {
            "process_receipt": "N/A: absent after capture-admission failure",
            "summary": "N/A: absent after capture-admission failure",
            "metrics": "N/A: absent after capture-admission failure",
            "steady_state_footprint": "N/A: absent after capture-admission failure",
            "capture_failure": "recorded in the immutable capture-failure artifact",
        },
        "classification_note": "Reaching the evaluation boundary does not convert a failed evidence-admission attempt into an anchor or scientific verdict.",
        "unverified_claims": [
            "No anchor verdict is asserted.",
            "No pull-mechanism verdict is asserted.",
            "No scientific verdict is asserted.",
        ],
    }


def _write_json(path: Path, value: JsonObject) -> None:
    if path.exists():
        raise ReceiptBuildError(f"Refusing to overwrite immutable receipt: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    plan = _artifact(PLAN_PATH, PLAN_SHA256)
    launch = _artifact(LAUNCH_PATH, LAUNCH_SHA256)
    log = _artifact(LOG_PATH, LOG_SHA256)
    _verify_log_boundary()
    capture_failure = _capture_failure(plan, launch, log)
    _write_json(CAPTURE_FAILURE_PATH, capture_failure)
    capture_failure_artifact = _artifact(CAPTURE_FAILURE_PATH, _sha256(CAPTURE_FAILURE_PATH))
    _write_json(RECEIPT_PATH, _receipt(plan, launch, log, capture_failure_artifact))
    print(f"Wrote {CAPTURE_FAILURE_PATH.relative_to(ROOT)}")
    print(f"Wrote {RECEIPT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
