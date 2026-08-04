#!/usr/bin/env python3
"""Build the immutable R4 reset-boundary contact-qualification receipt."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R4_RECEIPT.json"
R3_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R3_RECEIPT.json"
ATTEMPT5_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT5_RECEIPT.json"
ATTEMPT5_ROOT = ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt5"
EXPECTED_R3_RECEIPT_SHA256 = (
    "49ca2e32a81f2635afc3303f40e5cf50c0b581f991b2fbe564f36090e72ebf25"
)
EXPECTED_ATTEMPT5_RECEIPT_SHA256 = (
    "64283e4aebe60bfd6ad4a61ec3fcda6dc7936cdb21e86d2f39a974bcc07211ce"
)
EXPECTED_STALE_CANDIDATE_ID = (
    "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
)
PRE_HASHES = {
    "gr00t/rl/config/base_eval.yaml": "8bf3a69f00fe534b3a845a2d9d9ecc43621c2e1cb44d0042b0d3f069560fa72c",
    "gr00t/rl/config/ablation/wbmanip/pull_v0_p1_push_anchor.yaml": "60bf3c860cfcd0106edc7f51796c9786e4cde956fb7909378c229a60ae69faa5",
    "gr00t/rl/envs/door/door_open_a2_base.py": "b1031beb30f63999434d214f0792d61585b70fa4d84f0378cbe936f47f4d5871",
    "gr00t/rl/tests/test_a2_pull_namespace.py": "98a2bf5d5dfe15265e57219fd707882ca41a59ab2d40e5bd53cc07cb618cac1f",
    "gr00t/rl/tests/test_a2_pull_telemetry.py": "f268a257bf21ad32bc7514ea7e096d9c122e809a8ce7eb2586e17d79248bd346",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "0187dca9f111373759d37627104b8db40d86d90794e6008b7af5966146817aa8",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "907b946992c5b3fb2fcc141cb48cb7c27afcdfba2a1de35a5e65e7acb656c33b",
}
CHANGED_REASONS = {
    "gr00t/rl/config/base_eval.yaml": "Expose the bounded reset qualification window and fail-fast upright/gripper contract.",
    "gr00t/rl/config/ablation/wbmanip/pull_v0_p1_push_anchor.yaml": "Bind the P1 push-anchor fixture to the same reset qualification parameters.",
    "gr00t/rl/envs/door/door_open_a2_base.py": "Qualify reset-boundary contact with zero base/arm commands before signed staging; defer commanded body collision classification until trace capture and export current-vs-max terminal telemetry.",
    "gr00t/rl/tests/test_a2_pull_namespace.py": "Guard the reset qualification namespace, no-staging preflight, and actual base admission schema.",
    "gr00t/rl/tests/test_a2_pull_telemetry.py": "Guard transient/persistent contact qualification and trace-before-failure telemetry contracts.",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "Keep attempt5 R3-bound and require canonical R4 parent/attempt5 bindings plus an explicit receipt SHA256 for attempt6+.",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "Consume the actual push_anchor_admission terminal schema for immutable attempt5 and validate R4 chain bindings.",
    "scriptsFORhuman/pull_v0/build_pull_v0_repair_r4_receipt.py": "Record the immutable R4 repair chain, exact hashes, and static/runtime validation boundary.",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Required artifact is not a regular file: {path}")
    return {"path": str(path.relative_to(ROOT)), "sha256": _sha256(path)}


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime(
        "%Y-%m-%d %H:%M:%S HKT"
    )


def build_receipt() -> dict:
    if _sha256(R3_RECEIPT_PATH) != EXPECTED_R3_RECEIPT_SHA256:
        raise RuntimeError("Immutable Repair R3 receipt hash changed.")
    if _sha256(ATTEMPT5_RECEIPT_PATH) != EXPECTED_ATTEMPT5_RECEIPT_SHA256:
        raise RuntimeError("Immutable attempt5 receipt hash changed.")
    attempt5 = json.loads(ATTEMPT5_RECEIPT_PATH.read_text(encoding="utf-8"))
    if (
        attempt5.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v5"
        or attempt5.get("attempt") != 5
        or attempt5.get("status") != "BLOCKED"
        or attempt5.get("probe_validity") != "PROBE_INVALID"
        or attempt5.get("admission_blocker")
        != "RESET_BOUNDARY_CONTACT_UNQUALIFIED_BEFORE_STAGING"
        or attempt5.get("pull_mechanism_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("Attempt5 receipt is not the authorized R4 trigger artifact.")
    immutable_paths = {
        "plan": EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT5_PLAN.json",
        "process_receipt": ATTEMPT5_ROOT / "process_receipt.json",
        "summary": ATTEMPT5_ROOT / "eval/a2_hold_oracle_summary.json",
        "metrics": ATTEMPT5_ROOT / "eval/metrics_eval.json",
        "log": ATTEMPT5_ROOT / "stdout_stderr.log",
    }
    immutable_artifacts = {name: _artifact(path) for name, path in immutable_paths.items()}
    expected_immutable_hashes = {
        "plan": "b5769c0fc11920630f95953dbd77d99ed5693e156179f667bb78691ea28983ba",
        "process_receipt": "0f8366b3bf730ebc38d2ee1d01f4c02ee32ae3684a5bf5b882ddf5651507ca47",
        "summary": "7599f907bf5ff38a545ec539623c23bb57aec8486b457329ce19d2265b89f726",
        "metrics": "1e5688f8baf22e759306a88783ea4d6382ebc480290f3eae735bcb0563914148",
        "log": "a6d1ae634693e1c195e5fca4d38b1b6a82721dd37c7aadea3cb16ec5ad35282f",
    }
    for name, expected in expected_immutable_hashes.items():
        if immutable_artifacts[name]["sha256"] != expected:
            raise RuntimeError(f"Immutable attempt5 {name} hash changed.")

    post_files = {}
    for relative, pre_hash in PRE_HASHES.items():
        path = ROOT / relative
        actual = _sha256(path)
        if actual == pre_hash:
            raise RuntimeError(f"R4 implementation did not change leased path: {relative}")
        post_files[relative] = {
            "pre_sha256": pre_hash,
            "post_sha256": actual,
            "reason": CHANGED_REASONS[relative],
        }
    new_builder_relative = "scriptsFORhuman/pull_v0/build_pull_v0_repair_r4_receipt.py"
    post_files[new_builder_relative] = {
        "pre_sha256": None,
        "post_sha256": _sha256(ROOT / new_builder_relative),
        "reason": CHANGED_REASONS[new_builder_relative],
    }
    post_files[str(ATTEMPT5_RECEIPT_PATH.relative_to(ROOT))] = {
        "pre_sha256": None,
        "post_sha256": _sha256(ATTEMPT5_RECEIPT_PATH),
        "reason": "Immutable attempt5 receipt preserving the R3-bound actual-schema reset-boundary blocker.",
    }

    return {
        "schema_version": "pull_v0_repair_r4_receipt_v1",
        "generated_at_hkt": _hkt_now(),
        "repair_revision": "R4",
        "status": "APPROVED_FOR_ATTEMPT6_PREPARATION_ONLY",
        "stale_candidate_id": EXPECTED_STALE_CANDIDATE_ID,
        "root_cause": {
            "code": "RESET_BOUNDARY_CONTACT_UNQUALIFIED_BEFORE_STAGING",
            "conclusion": "Attempt5 classified a reset-boundary contact sample as commanded body collision before any reset contact qualification window, so persistence and command causality were not established.",
            "attempt5_running_max_body_contact_n": 3817.004150390625,
            "attempt5_terminal_live_body_contact_n": 0.0,
            "attempt5_first_contact_step": 0,
            "attempt5_first_contact_filter": "trunk",
        },
        "parent_receipt": {
            "path": str(R3_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": EXPECTED_R3_RECEIPT_SHA256,
            "repair_revision": "R3",
        },
        "trigger": {
            "attempt": 5,
            "root_cause": "RESET_BOUNDARY_CONTACT_UNQUALIFIED_BEFORE_STAGING",
            "attempt_receipt": _artifact(ATTEMPT5_RECEIPT_PATH),
            "immutable_runtime_artifacts": immutable_artifacts,
        },
        "scope": {
            "authorized": "reset-boundary contact qualification and actual-schema receipt-chain repair only",
            "attempt5_immutable": True,
            "attempt6_runtime_prepared": False,
            "gpu_or_isaacsim_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "implementation_contract": {
            "qualification_window": "bounded zero-command high-level base/arm hold with configured gripper state",
            "qualification_contact_threshold_n": 1.0,
            "qualification_persistence": "consecutive samples above the existing 1 N threshold",
            "post_qualification_body_contact": "immediate hard failure during commanded staging/DLS/proof",
            "trace_order": "record sample and final action before applying outcome classification",
            "terminal_force_semantics": "terminal current contact is distinct from running maximum",
            "report_only_thresholds": True,
            "effort_provenance": "ESTIMATE_ONLY",
        },
        "changed_files": post_files,
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "receipt parser/hash assertions",
                "git diff --check",
            ],
            "runtime_not_run_reason": "R4 contract explicitly forbids preparing/running attempt6 in this task.",
        },
        "acceptance": {
            "step0_transient_not_hard_collision": True,
            "persistent_qualifying_contact_hard_fails": True,
            "no_staging_or_dls_before_qualification": True,
            "cleared_transient_advances_only_to_staging": True,
            "trace_before_failure": True,
            "terminal_current_vs_max_separate": True,
            "actual_schema_builder": True,
            "incomplete_gate_cannot_pass": True,
        },
        "unverified_claims": [
            "No IsaacSim/GPU runtime PASS is asserted for R4 or attempt6.",
            "The R4 reset qualification semantics are statically covered; runtime persistence/clearance behavior remains unverified until an authorized attempt6 run.",
        ],
    }


def main() -> int:
    if RECEIPT_PATH.exists():
        raise RuntimeError(f"Refusing to overwrite immutable receipt: {RECEIPT_PATH}")
    value = build_receipt()
    temporary = RECEIPT_PATH.with_suffix(RECEIPT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(RECEIPT_PATH)
    print(f"Wrote {RECEIPT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
