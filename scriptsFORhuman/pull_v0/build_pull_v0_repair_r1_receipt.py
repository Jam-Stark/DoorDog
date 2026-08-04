#!/usr/bin/env python3
"""Build the deterministic Repair R1 scope and hash receipt.

This builder is static-only.  It records source hashes and validation commands;
it does not launch IsaacLab, allocate a GPU, or mutate runtime evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "scriptsFORhuman" / "pull_v0" / "PULL_V0_REPAIR_R1_RECEIPT.json"
BASE_SHA = "4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09"
STALE_CANDIDATE_ID = "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
REPAIR_REVISION = "R1"

CHANGED_PATHS = (
    "gr00t/rl/config/base_eval.yaml",
    "gr00t/rl/config/ablation/wbmanip/pull_v0_p1_push_anchor.yaml",
    "gr00t/rl/config/env/door_open_a2_pull.yaml",
    "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_pull.yaml",
    "gr00t/rl/envs/door/a2_pull_direction.py",
    "gr00t/rl/envs/door/a2_pull_telemetry.py",
    "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t/rl/envs/door/door_open_a2_pull.py",
    "gr00t/rl/tests/test_a2_pull_direction_contract.py",
    "gr00t/rl/tests/test_a2_pull_namespace.py",
    "gr00t/rl/tests/test_a2_pull_telemetry.py",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py",
    "scriptsFORhuman/pull_v0/build_pull_v0_repair_r1_receipt.py",
)

STALE_CANDIDATE_PRE_SHA256 = {
    "gr00t/rl/config/base_eval.yaml": "29d97abbebdfcf1b99cb98f46129094f849f202a95b98e19a26878b8759d5641",
    "gr00t/rl/config/ablation/wbmanip/pull_v0_p1_push_anchor.yaml": "78229fdc61681251e3c040aa82d3c210d067eadced8d1d5368d819c704f3b749",
    "gr00t/rl/config/env/door_open_a2_pull.yaml": "fce4cf3ed94e6b5210b8a67076a5416e11d8aac6497aca504932817d8a5d2bdd",
    "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_pull.yaml": "36a31a37fab82be504bc38f149f447189da22463290b0f759af890fef1803a4a",
    "gr00t/rl/envs/door/a2_pull_direction.py": "b73ee811ff5b1a6512c181bf79f3ebc673e8f6911cd792076ba595381c361b0d",
    "gr00t/rl/envs/door/a2_pull_telemetry.py": "8cbe23229cd4f9826a0c3c155e0dfc5e0d0c3907179d780638d6ad3f5260378d",
    "gr00t/rl/envs/door/door_open_a2_base.py": "08a2118bdbe459d252a19decae0d99eb9e7a73b9d05f68cdd1f49bc8a8af2559",
    "gr00t/rl/envs/door/door_open_a2_pull.py": "fb55aa214872d8b5439370ce2173ebc95b799946c71072b0e45fe8e5d0bba7e6",
    "gr00t/rl/tests/test_a2_pull_direction_contract.py": "94c249ef28c66761569f2d2b852c22fb29401265b2837da82f92445dea43de7d",
    "gr00t/rl/tests/test_a2_pull_namespace.py": "433a8221f64c6158ab1edf08661e29f654ef086f635a5ce68cbf711c518ef067",
    "gr00t/rl/tests/test_a2_pull_telemetry.py": "321a36d94931ceb834a6cb3f528118b8fef41802bcc5289f88813f0eee7eb4d0",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "6210b3e73a63f027dde65f57edababd4b1a3f7a3768e99f89859f0bde4109e89",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "ff0f0986407a14beedbbcd820865de6917b34fff07d5481b2cfdf009e4f0cedc",
}
NEW_REPAIR_BUILDER_PATH = "scriptsFORhuman/pull_v0/build_pull_v0_repair_r1_receipt.py"


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime(
        "%Y-%m-%d %H:%M:%S HKT"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _pre_sha256(relative_path: str) -> str:
    expected_paths = set(CHANGED_PATHS) - {NEW_REPAIR_BUILDER_PATH}
    if set(STALE_CANDIDATE_PRE_SHA256) != expected_paths:
        missing = sorted(expected_paths - set(STALE_CANDIDATE_PRE_SHA256))
        extra = sorted(set(STALE_CANDIDATE_PRE_SHA256) - expected_paths)
        raise RuntimeError(
            "Stale-candidate pre-hash mapping is incomplete or contains unexpected paths: "
            f"missing={missing}, extra={extra}."
        )
    if relative_path == NEW_REPAIR_BUILDER_PATH:
        return "N/A"
    try:
        return STALE_CANDIDATE_PRE_SHA256[relative_path]
    except KeyError as exc:
        raise RuntimeError(
            f"Missing exact stale-candidate pre_sha256 for {relative_path}."
        ) from exc


def _hash_entry(relative_path: str) -> dict[str, str]:
    path = ROOT / relative_path
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Changed path must be a regular file: {relative_path}")
    return {
        "pre_sha256": _pre_sha256(relative_path),
        "post_sha256": _sha256(path),
    }


def build_receipt() -> dict:
    hashes = {path: _hash_entry(path) for path in CHANGED_PATHS}
    return {
        "schema_version": "pull_v0_repair_r1_receipt_v1",
        "status": "STATIC_VALIDATION_PASS_RUNTIME_UNVERIFIED",
        "repair_revision": REPAIR_REVISION,
        "stale_candidate_id": STALE_CANDIDATE_ID,
        "base_sha": BASE_SHA,
        "generated_at_hkt": _hkt_now(),
        "scope": {
            "route": "STANDARD_PATH",
            "destination": "DoorDog-A2_Piper_pull_v0 pull-v0 Repair R1",
            "stopping_condition": (
                "Static contracts, config composition, and CPU tests pass; runtime remains unrun."
            ),
            "threshold_mode": "report_only",
            "effort_provenance": "ESTIMATE_ONLY",
        },
        "authorized_reason": {
            "admission_control_flow": (
                "A: resolve anchor NO_GATE by binding scripted acquisition to first-episode activity "
                "without requiring stage_buf==STAGE_GRASP; preserve stage-0 predicates as telemetry."
            ),
            "physical_proof_and_transitions": (
                "B: apply the tensile proof design to the shared world +X consumer, reset proof on "
                "contact loss or non-monotone retreat, and gate E2/E3/E4 transitions on contiguous evidence."
            ),
            "measured_terminal_evidence": (
                "Validator: require measured articulation clearance before E5, exact E7 whole-body "
                "completion, complete terminal episode records, and keep target-root reward inactive before E5."
            ),
        },
        "root_cause": {
            "conclusion": "ANCHOR_ADMISSION_CONTROL_FLOW",
            "physical_stage0_predicate_cause": "INCONCLUSIVE_BEFORE_R1_TELEMETRY",
            "runtime_mechanics_verdict": "UNVERIFIED",
        },
        "file_hashes": hashes,
        "validation": {
            "commands": [
                "python -m py_compile gr00t/rl/envs/door/a2_pull_direction.py gr00t/rl/envs/door/a2_pull_telemetry.py gr00t/rl/envs/door/door_open_a2_pull.py gr00t/rl/envs/door/door_open_a2_base.py scriptsFORhuman/pull_v0/build_pull_v0_repair_r1_receipt.py",
                "python -m pytest -q gr00t/rl/tests/test_a2_pull_direction_contract.py gr00t/rl/tests/test_a2_pull_geometry_proof.py gr00t/rl/tests/test_a2_pull_namespace.py gr00t/rl/tests/test_a2_pull_telemetry.py gr00t/rl/tests/test_a2_pull_v0_freeze_guard.py",
                "git diff --check",
            ],
            "static_result": "PASS",
            "full_pull_test_gate": {
                "test_files": [
                    "test_a2_pull_direction_contract.py",
                    "test_a2_pull_geometry_proof.py",
                    "test_a2_pull_namespace.py",
                    "test_a2_pull_telemetry.py",
                    "test_a2_pull_v0_freeze_guard.py",
                ],
                "passed": 51,
                "warnings": 2,
                "result": "PASS",
            },
            "py_compile_result": "PASS",
            "diff_check_result": "PASS",
            "runtime_result": "INCONCLUSIVE_NOT_RUN_BY_WORKER",
            "negative_reached_event_step_time_checked": True,
            "review_lanes": ["code_reviewer", "isaaclab_reviewer", "runtime_qa_pending_parent_approval"],
        },
        "downstream_gates": {
            "runner_requires_this_receipt": True,
            "anchor_attempts_authorized_after_receipt": True,
            "push_anchor_runtime": "PENDING_PARENT_RUNTIME_LEASE",
            "pull_side_p1": "NOT_STARTED",
            "p2": "NOT_STARTED",
        },
        "unverified_claims": [
            "No IsaacSim/GPU runtime outcome is asserted by this receipt.",
            "No physical stage-0 predicate cause is asserted before R1 telemetry exists.",
        ],
        "receipt_self_hash": "N/A_SELF_REFERENTIAL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    receipt = build_receipt()
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.write:
        if OUTPUT.exists() and not args.overwrite:
            raise RuntimeError(f"Refusing to overwrite receipt: {OUTPUT}")
        OUTPUT.write_text(encoded, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
