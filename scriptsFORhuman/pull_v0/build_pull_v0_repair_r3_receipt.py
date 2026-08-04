#!/usr/bin/env python3
"""Build the immutable Pull-v0 Repair R3 admission-repair receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
R2_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R2_RECEIPT.json"
ATTEMPT4_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT4_RECEIPT.json"
OUTPUT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R3_RECEIPT.json"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
R2_RECEIPT_SHA256 = "9899b5bbb93455cea82c80bee6a2c58e00b7ad692c1302dfe7aedc553b5f5263"
ATTEMPT4_RECEIPT_SHA256 = "fba43435fb15a40dfb4be4cd4fe3c0ba5cc688a8137b5da89bb420d8f709b90e"
PRE_HASHES = {
    "gr00t/rl/config/base_eval.yaml": "2a2b1806514512c8c25051c2a3f92deb8820944ff6a47644830925f2eb917db3",
    "gr00t/rl/config/ablation/wbmanip/pull_v0_p1_push_anchor.yaml": "7de8e2d42a6d24ee9b495ef1576566eb084f9b202d234b5386dc14b8966feb64",
    "gr00t/rl/envs/door/door_open_a2_base.py": "d22a5fd76b38693009f60f39db8e6f4b9e0a1f0f1ccd938379ca2ad5ab8f6206",
    "gr00t/rl/envs/door/door_open_a2_pull.py": "78844673eab6d4a599640a964f66e6b1fd2376704a2ae670d62845b87bbbfda2",
    "gr00t/rl/tests/test_a2_pull_namespace.py": "3d2694b21f7b0b246bece6ce46c5660b4ffaf6a6d4a5fcf3df42543df3fa1018",
    "gr00t/rl/tests/test_a2_pull_telemetry.py": "fdfcf62fa639c641612c6fe00b1b243747e170e5eeac2c8dd4cc9a833af8d7df",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "d034f63754ec0d5ba94ecc60136981f90a86322ae071fb41d7c29c655af88cda",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "af6743598677a150c1014e6eea207762e30242e77e4dd01e13819173a1e888f3",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime(
        "%Y-%m-%d %H:%M:%S HKT"
    )


def _artifact(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Receipt artifact must be a regular file: {path}")
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": _sha256(path),
    }


def _read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def build_receipt(*, static_test_count: int, static_test_warnings: int) -> dict:
    if isinstance(static_test_count, bool) or not isinstance(static_test_count, int) or static_test_count <= 0:
        raise ValueError("static_test_count must be a positive integer")
    if isinstance(static_test_warnings, bool) or not isinstance(static_test_warnings, int) or static_test_warnings < 0:
        raise ValueError("static_test_warnings must be a non-negative integer")
    if _sha256(R2_RECEIPT_PATH) != R2_RECEIPT_SHA256:
        raise RuntimeError("Canonical Repair R2 receipt hash changed.")
    r2 = _read_object(R2_RECEIPT_PATH)
    if (
        r2.get("schema_version") != "pull_v0_repair_r2_receipt_v1"
        or r2.get("repair_revision") != "R2"
        or r2.get("stale_candidate_id") != STALE_CANDIDATE_ID
    ):
        raise RuntimeError("Canonical Repair R2 identity is not the authorized parent.")
    attempt4_artifact = _artifact(ATTEMPT4_RECEIPT_PATH)
    if attempt4_artifact["sha256"] != ATTEMPT4_RECEIPT_SHA256:
        raise RuntimeError("Immutable attempt4 receipt hash changed.")
    attempt4 = _read_object(ATTEMPT4_RECEIPT_PATH)
    if (
        attempt4.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v4"
        or attempt4.get("attempt") != 4
        or attempt4.get("status") != "BLOCKED"
        or attempt4.get("probe_validity") != "PROBE_INVALID"
        or attempt4.get("admission_blocker")
        != "ACQUISITION_CONTROL_CIRCULARITY_AND_TELEMETRY_INCOMPLETE"
        or attempt4.get("pull_mechanism_verdict") != "NOT_ASSESSED"
        or attempt4.get("causality", {}).get("classification") != "INCONCLUSIVE"
    ):
        raise RuntimeError("Immutable attempt4 receipt does not preserve the R3 blocker contract.")
    file_hashes = {}
    for relative_path, pre_sha256 in PRE_HASHES.items():
        path = ROOT / relative_path
        post_sha256 = _sha256(path)
        file_hashes[relative_path] = {
            "pre_sha256": pre_sha256,
            "post_sha256": post_sha256,
            "changed": post_sha256 != pre_sha256,
            "reason": (
                "R3 admission repair or regression/receipt binding update"
                if post_sha256 != pre_sha256
                else "R3 verified no duplicate pull-subclass terminal writer was required"
            ),
        }
    builder_path = Path(__file__).resolve()
    file_hashes[str(builder_path.relative_to(ROOT))] = {
        "pre_sha256": "N/A_NEW_FILE",
        "post_sha256": _sha256(builder_path),
        "reason": "Immutable R3 receipt-chain builder",
    }
    return {
        "schema_version": "pull_v0_repair_r3_receipt_v1",
        "generated_at_hkt": _hkt_now(),
        "repair_revision": "R3",
        "status": "STATIC_VALIDATION_PASS_RUNTIME_UNVERIFIED",
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "base_sha": "4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09",
        "scope": {
            "destination": "DoorDog-A2_Piper_pull_v0 pull-v0 Repair R3",
            "route": "STANDARD_PATH",
            "threshold_mode": "report_only",
            "effort_provenance": "ESTIMATE_ONLY",
            "stopping_condition": (
                "Repair stage-0 push-anchor admission circularity, preserve immutable attempt4, "
                "and leave attempt5 runtime unverified until separately authorized and run."
            ),
        },
        "authorized_reason": (
            "Attempt4 remained at stage0 because acquisition computed DLS but then zeroed base, "
            "arm, and gripper actions while waiting for stage_buf >= STAGE_PREGRASP. The same "
            "attempt lacked base-owned per-step anchor telemetry, so the running-max contact and "
            "terminal-zero contact cannot establish causality."
        ),
        "root_cause": {
            "conclusion": "ACQUISITION_CONTROL_CIRCULARITY_AND_TELEMETRY_INCOMPLETE",
            "stage": "P1_ACQUIRE_STAGE0",
            "mechanics": (
                "Stage0 admission waited on STAGE_PREGRASP while the acquisition override "
                "discarded all movement and the computed DLS candidate."
            ),
            "telemetry": (
                "Base push-anchor admission had no bounded first-episode trace or anchor-specific "
                "terminal export; pull-only E0-E7 records cannot substitute for it."
            ),
            "runtime_mechanics_verdict": "UNVERIFIED",
            "scientific_verdict_consumed": False,
        },
        "parent_receipt": {
            "path": str(R2_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": R2_RECEIPT_SHA256,
            "repair_revision": "R2",
        },
        "trigger": {
            "attempt": 4,
            "attempt_receipt": attempt4_artifact,
            "root_cause": "ACQUISITION_CONTROL_CIRCULARITY_AND_TELEMETRY_INCOMPLETE",
            "preserved_result": "BLOCKED_PROBE_INVALID",
            "observed_running_max_filtered_body_panel_contact_n": 3817.004150390625,
            "observed_terminal_body_panel_contact_n": 0.0,
            "causality": "INCONCLUSIVE",
            "pull_mechanism_verdict": "NOT_ASSESSED",
        },
        "file_hashes": file_hashes,
        "immutable_artifacts": {
            "parent_r2_receipt": _artifact(R2_RECEIPT_PATH),
            "attempt4_receipt": attempt4_artifact,
            "attempt4_artifacts": attempt4.get("artifacts"),
        },
        "implementation_reasons": {
            "stage0_control": (
                "Use signed staging-band membership/nearest target and existing high-level body "
                "velocity mapping; outside-band actions move toward the band, inside-band actions "
                "settle to zero without writing stage_buf."
            ),
            "dls_contract": (
                "Preserve the computed DLS candidate and report a distinct final-applied mask; "
                "stage0 waiting rows are the only rows whose arm action is withheld."
            ),
            "telemetry_contract": (
                "Base-owned first-episode traces are bounded by episode budget and include stage "
                "transitions, root state, residuals, candidate/applied actions, and contact maxima."
            ),
        },
        "validation": {
            "commands": [
                "python -m py_compile gr00t/rl/envs/door/door_open_a2_base.py gr00t/rl/envs/door/door_open_a2_pull.py gr00t/rl/tests/test_a2_pull_namespace.py gr00t/rl/tests/test_a2_pull_telemetry.py scriptsFORhuman/pull_v0/run_p1_push_anchor.py scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py scriptsFORhuman/pull_v0/build_pull_v0_repair_r3_receipt.py",
                "PYTHONPATH=. python -m pytest -q gr00t/rl/tests/test_a2_pull_direction_contract.py gr00t/rl/tests/test_a2_pull_geometry_proof.py gr00t/rl/tests/test_a2_pull_namespace.py gr00t/rl/tests/test_a2_pull_telemetry.py gr00t/rl/tests/test_a2_pull_v0_freeze_guard.py",
                "git diff --check",
                "receipt-chain parser/hash assertions",
            ],
            "full_pull_test_gate": {
                "passed": static_test_count,
                "warnings": static_test_warnings,
                "result": "PASS",
            },
            "py_compile_result": "PASS",
            "receipt_chain_result": "PASS",
            "static_result": "PASS",
            "runtime_result": "INCONCLUSIVE_NOT_RUN_BY_WORKER",
            "runtime_unverified_reason": "R3 worker is CPU/static-only and did not run IsaacSim/GPU or prepare attempt5.",
        },
        "threshold_mode": "report_only",
        "effort_provenance": "ESTIMATE_ONLY",
        "receipt_self_hash": "N/A_SELF_REFERENTIAL",
        "unverified_claims": [
            "No IsaacSim/GPU runtime outcome is asserted by R3.",
            "No attempt5 output is prepared or consumed.",
            "No pull-mechanism verdict is inferred from immutable attempt4.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", required=True)
    parser.add_argument("--static-test-count", type=int, default=60)
    parser.add_argument("--static-test-warnings", type=int, default=2)
    args = parser.parse_args()
    receipt = build_receipt(
        static_test_count=args.static_test_count,
        static_test_warnings=args.static_test_warnings,
    )
    if OUTPUT_PATH.exists():
        raise RuntimeError(f"Refusing to overwrite immutable R3 receipt: {OUTPUT_PATH}")
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"SHA256 {_sha256(OUTPUT_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
