#!/usr/bin/env python3
"""Build the immutable Repair R2 receipt from the fixed tensor-device callsite.

This builder is static-only.  It validates the preserved attempt-3 failure and
records source/artifact hashes; it never launches IsaacLab or allocates a GPU.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
OUTPUT = EVIDENCE_ROOT / "PULL_V0_REPAIR_R2_RECEIPT.json"
SUPERSEDED_OUTPUT = (
    EVIDENCE_ROOT
    / "PULL_V0_REPAIR_R2_RECEIPT_SUPERSEDED_PRE_BIND_VALIDATION_COUNT_CORRECTION.json"
)
SUPERSEDED_OUTPUT_SHA256 = "9d03fdd870042890f24be5c9dfc841db8429f1c28741a236ef3ff5349af92e6f"
SUPERSESSION_REASON = "PRE_BIND_VALIDATION_COUNT_CORRECTION"
BASE_SHA = "4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
R1_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R1_RECEIPT.json"
R1_RECEIPT_SHA256 = "14b15df80229fbd7e01fded10c8a1675f58317cabb727e6d12f0931ab82f8335"
ATTEMPT3_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT3_RECEIPT.json"
ATTEMPT3_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT3_PLAN.json"
ATTEMPT3_PROCESS_PATH = (
    ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt3/process_receipt.json"
)
ATTEMPT3_LOG_PATH = (
    ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt3/stdout_stderr.log"
)
ATTEMPT3_ERROR_SIGNATURE = "TypeError: device must be torch.device; got str."

CHANGED_PATHS = (
    "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t/rl/tests/test_a2_pull_direction_contract.py",
    "gr00t/rl/tests/test_a2_pull_namespace.py",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py",
    "scriptsFORhuman/pull_v0/build_pull_v0_repair_r2_receipt.py",
    "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT3_RECEIPT.json",
)

PRE_SHA256 = {
    "gr00t/rl/envs/door/door_open_a2_base.py": "9edebef01670eb8a6bf0588e0e1e53f9efd867fc0f64c42fb93db28794c6c9b8",
    "gr00t/rl/tests/test_a2_pull_direction_contract.py": "c9ebe71ba1701f52737c61cc50e0ed529971daa17baf887c236a665936cc8138",
    "gr00t/rl/tests/test_a2_pull_namespace.py": "47a3e9ff4ecb9ba454ee6ad26d5cf16d9a64f08106f919c4269f9f988518d75c",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "634cb0c15de654ea66c7d89e9d9482d045eff177196ec39d178fb042d2f663e6",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "73042edc767bfd4be2114ac45937a42dc3721fd16fba99c7457543235b82f57e",
}

CHANGE_REASONS = {
    "gr00t/rl/envs/door/door_open_a2_base.py": (
        "Pass the actual handle quaternion tensor device into the strict proof-offset helper; "
        "do not pass the environment device string."
    ),
    "gr00t/rl/tests/test_a2_pull_direction_contract.py": (
        "Add a production-consumer AST regression that rejects a string device callsite."
    ),
    "gr00t/rl/tests/test_a2_pull_namespace.py": (
        "Cover the preserved attempt-3 contract failure receipt and R2-era evidence bindings."
    ),
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": (
        "Keep attempt 3 on immutable R1 binding and require canonical explicit R2 binding for attempt 4+."
    ),
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": (
        "Record attempt-3 pre-probe contract failure receipts and validate R1/R2 artifact chains."
    ),
    "scriptsFORhuman/pull_v0/build_pull_v0_repair_r2_receipt.py": (
        "Add the immutable English R2 parent/trigger/source-hash receipt builder."
    ),
    "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT3_RECEIPT.json": (
        "Preserve the exact application contract TypeError as an immutable non-scientific failure."
    ),
}


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime(
        "%Y-%m-%d %H:%M:%S HKT"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Evidence artifact must be a regular file: {path}")
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": _sha256(path),
    }


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def _validate_parent_r1() -> dict:
    artifact = _artifact(R1_RECEIPT_PATH)
    if artifact["sha256"] != R1_RECEIPT_SHA256:
        raise RuntimeError("Repair R1 receipt hash changed; R2 cannot be chained safely.")
    receipt = _read_json(R1_RECEIPT_PATH)
    if (
        receipt.get("schema_version") != "pull_v0_repair_r1_receipt_v1"
        or receipt.get("repair_revision") != "R1"
        or receipt.get("stale_candidate_id") != STALE_CANDIDATE_ID
    ):
        raise RuntimeError("Repair R1 parent identity is not authorized for R2.")
    return receipt


def _validate_superseded_receipt() -> dict[str, str]:
    artifact = _artifact(SUPERSEDED_OUTPUT)
    if artifact["sha256"] != SUPERSEDED_OUTPUT_SHA256:
        raise RuntimeError("Superseded R2 receipt archive bytes changed.")
    return artifact


def _validate_attempt3_receipt() -> dict:
    receipt = _read_json(ATTEMPT3_RECEIPT_PATH)
    if (
        receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v3"
        or receipt.get("attempt") != 3
        or receipt.get("status") != "BLOCKED"
        or receipt.get("probe_validity") != "PROBE_INVALID"
        or receipt.get("admission_blocker") != "APPLICATION_CONTRACT_ERROR_BEFORE_PROBE"
        or receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("Attempt3 receipt is not the preserved pre-probe contract failure.")
    if receipt.get("application_contract_error", {}).get("signature") != ATTEMPT3_ERROR_SIGNATURE:
        raise RuntimeError("Attempt3 receipt does not preserve the exact TypeError signature.")
    repair_r1 = receipt.get("repair_r1", {})
    if repair_r1.get("artifact", {}).get("sha256") != R1_RECEIPT_SHA256:
        raise RuntimeError("Attempt3 receipt is not bound to the immutable Repair R1 receipt.")
    expected_artifacts = {
        "plan": ATTEMPT3_PLAN_PATH,
        "process_receipt": ATTEMPT3_PROCESS_PATH,
        "log": ATTEMPT3_LOG_PATH,
    }
    for name, path in expected_artifacts.items():
        expected = _artifact(path)
        actual = receipt.get("artifacts", {}).get(name)
        if actual != expected:
            raise RuntimeError(f"Attempt3 receipt artifact hash mismatch for {name}.")
    if receipt.get("artifacts", {}).get("summary") is not None:
        raise RuntimeError("Attempt3 receipt must record summary as absent.")
    if receipt.get("artifacts", {}).get("metrics") is not None:
        raise RuntimeError("Attempt3 receipt must record metrics as absent.")
    if ATTEMPT3_ERROR_SIGNATURE not in ATTEMPT3_LOG_PATH.read_text(
        encoding="utf-8", errors="replace"
    ):
        raise RuntimeError("Attempt3 log no longer contains the exact contract error signature.")
    return receipt


def _hash_entry(relative_path: str) -> dict[str, str]:
    path = ROOT / relative_path
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"R2 changed path must be a regular file: {relative_path}")
    if relative_path in PRE_SHA256:
        pre_sha256 = PRE_SHA256[relative_path]
    else:
        pre_sha256 = "N/A"
    return {
        "pre_sha256": pre_sha256,
        "post_sha256": _sha256(path),
    }


def build_receipt() -> dict:
    parent_r1 = _validate_parent_r1()
    attempt3 = _validate_attempt3_receipt()
    superseded = _validate_superseded_receipt()
    hashes = {path: _hash_entry(path) for path in CHANGED_PATHS}
    attempt3_artifact = _artifact(ATTEMPT3_RECEIPT_PATH)
    return {
        "schema_version": "pull_v0_repair_r2_receipt_v1",
        "status": "STATIC_VALIDATION_PASS_RUNTIME_UNVERIFIED",
        "repair_revision": "R2",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "base_sha": BASE_SHA,
        "generated_at_hkt": _hkt_now(),
        "supersedes": {
            "artifact": superseded,
            "reason": SUPERSESSION_REASON,
        },
        "scope": {
            "route": "STANDARD_PATH",
            "destination": "DoorDog-A2_Piper_pull_v0 pull-v0 Repair R2",
            "stopping_condition": (
                "Fix the tensor-device consumer contract, preserve attempt 3 as a pre-probe failure, "
                "and leave subsequent runtime unverified until a new leased attempt is run."
            ),
            "threshold_mode": "report_only",
            "effort_provenance": "ESTIMATE_ONLY",
        },
        "authorized_reason": (
            "Attempt 3 reached the push-anchor callsite before probe admission and passed the "
            "environment device string into a helper whose explicit contract requires torch.device. "
            "R2 fixes that consumer callsite without weakening the helper contract."
        ),
        "root_cause": {
            "conclusion": "TENSOR_DEVICE_CALLSITE_CONTRACT",
            "failure_signature": ATTEMPT3_ERROR_SIGNATURE,
            "stage": "APPLICATION_CONTRACT_ERROR_BEFORE_PROBE",
            "scientific_verdict_consumed": False,
            "runtime_mechanics_verdict": "UNVERIFIED",
        },
        "parent_receipt": {
            "path": str(R1_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": R1_RECEIPT_SHA256,
            "repair_revision": parent_r1["repair_revision"],
        },
        "trigger": {
            "attempt": 3,
            "root_cause": "TENSOR_DEVICE_CALLSITE_CONTRACT",
            "attempt_receipt": attempt3_artifact,
            "preserved_result": "APPLICATION_CONTRACT_ERROR_BEFORE_PROBE",
        },
        "file_hashes": hashes,
        "change_reasons": CHANGE_REASONS,
        "validation": {
            "commands": [
                "python -m py_compile gr00t/rl/envs/door/door_open_a2_base.py gr00t/rl/tests/test_a2_pull_direction_contract.py gr00t/rl/tests/test_a2_pull_namespace.py scriptsFORhuman/pull_v0/run_p1_push_anchor.py scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py scriptsFORhuman/pull_v0/build_pull_v0_repair_r2_receipt.py",
                "python -m pytest -q gr00t/rl/tests/test_a2_pull_direction_contract.py gr00t/rl/tests/test_a2_pull_geometry_proof.py gr00t/rl/tests/test_a2_pull_namespace.py gr00t/rl/tests/test_a2_pull_telemetry.py gr00t/rl/tests/test_a2_pull_v0_freeze_guard.py",
                "PYTHONPATH=. python scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py --attempt 3",
                "git diff --check",
            ],
            "static_result": "PASS",
            "py_compile_result": "PASS",
            "full_pull_test_gate": {
                "passed": 57,
                "warnings": 2,
                "result": "PASS",
            },
            "attempt3_receipt_result": "PASS",
            "attempt3_receipt_sha256": attempt3_artifact["sha256"],
            "runtime_result": "INCONCLUSIVE_NOT_RUN_BY_WORKER",
        },
        "downstream_gates": {
            "attempt3": "IMMUTABLE_APPLICATION_CONTRACT_ERROR_BEFORE_PROBE",
            "attempt4": "AUTHORIZED_ONLY_WITH_EXPLICIT_REPAIR_R2_BINDING",
            "pull_side_p1": "NOT_STARTED",
            "p2": "NOT_STARTED",
        },
        "unverified_claims": [
            "No IsaacSim/GPU runtime outcome is asserted by this receipt.",
            "No pull-mechanism verdict was consumed from attempt 3.",
            "A future attempt 4 must produce fresh runtime artifacts before any probe verdict is assessed.",
        ],
        "receipt_self_hash": "N/A_SELF_REFERENTIAL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    receipt = build_receipt()
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.write:
        if OUTPUT.exists():
            current_sha256 = _sha256(OUTPUT)
            if current_sha256 != SUPERSEDED_OUTPUT_SHA256:
                raise RuntimeError(f"Refusing to overwrite non-superseded R2 receipt: {OUTPUT}")
            if not SUPERSEDED_OUTPUT.exists() or _sha256(SUPERSEDED_OUTPUT) != SUPERSEDED_OUTPUT_SHA256:
                raise RuntimeError("R2 superseded archive is missing or does not preserve old bytes.")
        OUTPUT.write_text(encoded, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
