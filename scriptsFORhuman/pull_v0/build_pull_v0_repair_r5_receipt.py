#!/usr/bin/env python3
"""Build the immutable R5 generic-relief watchdog cross-talk receipt."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R5_RECEIPT.json"
R4_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R4_RECEIPT.json"
ATTEMPT6_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT6_RECEIPT.json"
ATTEMPT6_ROOT = ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt6"
EXPECTED_R4_RECEIPT_SHA256 = (
    "0c1debd42bbee1d9007190b2e3768670c23981a903df5ba9c5b6512d22b904aa"
)
EXPECTED_ATTEMPT6_RECEIPT_SHA256 = (
    "d358c53345ad95bad7086e005a8325ade3f46444c2a580379db771e699e81a34"
)
EXPECTED_STALE_CANDIDATE_ID = (
    "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
)
PRE_HASHES = {
    "gr00t/rl/envs/door/door_open_a2_base.py": "810b58e8528bd1d2598a89640dd6f347fc46e831c184eafdd9b7196d8802afba",
    "gr00t/rl/tests/test_a2_pull_namespace.py": "5e2308f398a6fdd655c6df0c3fb9ec5c6a0ac060f1e199ac31dc6a01e030877b",
    "gr00t/rl/tests/test_a2_pull_telemetry.py": "141b227cf6ce38d3bc3fc59603d7981c2c950b478496fb904a06f3873d4fc56f",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "84034bd39fdef0146035004d92fb3686449fedab358a7f1b9770643ba5bec042",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "b35c56765de73cb117d5970489dfc735f2eacf3e631241e52a97707cc4bc38f2",
}
CHANGED_REASONS = {
    "gr00t/rl/envs/door/door_open_a2_base.py": "Mask generic DLS/base-relief state and outcomes during explicit P1 acquisition-wait while preserving stage0 timeout and non-P1 relief semantics; latch reset qualification before buffer clearing.",
    "gr00t/rl/tests/test_a2_pull_namespace.py": "Guard actual Attempt6 receipt schema and fail-fast R5 runner ancestry/SHA bindings.",
    "gr00t/rl/tests/test_a2_pull_telemetry.py": "Guard long acquisition-wait relief masking and reset qualification latch agreement across terminal and summary telemetry.",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "Keep Attempt6 bound to canonical R4 and require explicit exact R5 receipt SHA plus R5/Attempt6/R4 ancestry for Attempt7+.",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "Classify immutable Attempt6 from the actual base-owned push_anchor_admission schema as probe-invalid generic-relief watchdog cross-talk.",
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


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def build_receipt() -> dict:
    if _sha256(R4_RECEIPT_PATH) != EXPECTED_R4_RECEIPT_SHA256:
        raise RuntimeError("Immutable Repair R4 receipt hash changed.")
    if _sha256(ATTEMPT6_RECEIPT_PATH) != EXPECTED_ATTEMPT6_RECEIPT_SHA256:
        raise RuntimeError("Immutable Attempt6 receipt hash changed.")
    attempt6 = _load(ATTEMPT6_RECEIPT_PATH)
    if (
        attempt6.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v6"
        or attempt6.get("attempt") != 6
        or attempt6.get("status") != "BLOCKED"
        or attempt6.get("probe_validity") != "PROBE_INVALID"
        or attempt6.get("admission_blocker") != "GENERIC_BASE_RELIEF_WATCHDOG_CROSS_TALK"
        or attempt6.get("pull_mechanism_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("Attempt6 receipt is not the authorized R5 trigger artifact.")

    immutable_paths = {
        "plan": EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT6_PLAN.json",
        "process_receipt": ATTEMPT6_ROOT / "process_receipt.json",
        "summary": ATTEMPT6_ROOT / "eval/a2_hold_oracle_summary.json",
        "metrics": ATTEMPT6_ROOT / "eval/metrics_eval.json",
        "log": ATTEMPT6_ROOT / "stdout_stderr.log",
    }
    immutable_artifacts = {name: _artifact(path) for name, path in immutable_paths.items()}
    expected_immutable_hashes = {
        "plan": "9344a1b4807830b835055b54ccb307bcb271402991cdfec005179c17f1b954e7",
        "process_receipt": "9a7a279c37b760beb0a01e526be354eb0a90bf88d03a8adcbb194d52d77dd6e4",
        "summary": "bfc3359123c53bcaab7577d92697bf4e61540e7d4501bbd5f45f2fc69cfe65d0",
        "metrics": "039e5dff055d96a0a408d09db4f8ad8e6aaf6ea7cb6c5bf902dda363661ee64f",
        "log": "5344ff72c8d17ea87e22f39ee88b7c1ed95cebc76664a4d13d84940ea9352421",
    }
    for name, expected in expected_immutable_hashes.items():
        if immutable_artifacts[name]["sha256"] != expected:
            raise RuntimeError(f"Immutable Attempt6 {name} hash changed.")

    summary = _load(immutable_paths["summary"])
    metrics = _load(immutable_paths["metrics"])
    admission = metrics["episode_terminal_diagnostics"][0]["push_anchor_admission"]
    if (
        summary.get("per_env_outcome") != ["BASE_RELIEF_TIMEOUT"]
        or summary.get("per_env_pass") != [False]
        or summary.get("per_env_reset_contact_qualification_complete") != [False]
        or summary.get("per_env_reset_transient_observed") != [False]
        or admission.get("reset_contact_qualification", {}).get("window_complete") is not True
        or admission.get("reset_contact_qualification", {}).get("reset_transient_observed") is not True
        or admission.get("trace_step_count") != 67
        or admission.get("body_panel_contact_total_current_n") != 0.0
        or admission.get("body_panel_contact_total_max_n") != 3817.004150390625
    ):
        raise RuntimeError("Attempt6 immutable evidence does not preserve the watchdog cross-talk signature.")

    changed_files = {}
    for relative, pre_hash in PRE_HASHES.items():
        path = ROOT / relative
        actual = _sha256(path)
        if actual == pre_hash:
            raise RuntimeError(f"R5 implementation did not change leased path: {relative}")
        changed_files[relative] = {
            "pre_sha256": pre_hash,
            "post_sha256": actual,
            "reason": CHANGED_REASONS[relative],
        }
    new_files = {
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r5_receipt.py": "Record the immutable R5 chain, exact hashes, blocker, and static/runtime validation boundary.",
        str(ATTEMPT6_RECEIPT_PATH.relative_to(ROOT)): "Immutable Attempt6 receipt preserving the actual-schema generic-relief watchdog cross-talk blocker.",
    }
    for relative, reason in new_files.items():
        path = ROOT / relative
        changed_files[relative] = {
            "pre_sha256": None,
            "post_sha256": _sha256(path),
            "reason": reason,
        }

    return {
        "schema_version": "pull_v0_repair_r5_receipt_v1",
        "generated_at_hkt": _hkt_now(),
        "repair_revision": "R5",
        "status": "APPROVED_FOR_ATTEMPT7_PREPARATION_ONLY",
        "stale_candidate_id": EXPECTED_STALE_CANDIDATE_ID,
        "root_cause": {
            "code": "GENERIC_BASE_RELIEF_WATCHDOG_CROSS_TALK",
            "conclusion": "Attempt6 completed reset qualification and emitted signed stage0 commands, but the generic DLS/base-relief watchdog remained active during explicit P1 acquisition-wait and produced BASE_RELIEF_TIMEOUT before stage0 admission could finish.",
            "attempt6_summary_outcome": "BASE_RELIEF_TIMEOUT",
            "attempt6_trace_step_count": 67,
            "generic_relief_timeout_steps": 60,
            "stage0_timeout_observed": False,
            "reset_qualification_complete": True,
            "reset_transient_observed": True,
        },
        "parent_receipt": {
            "path": str(R4_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": EXPECTED_R4_RECEIPT_SHA256,
            "repair_revision": "R4",
        },
        "trigger": {
            "attempt": 6,
            "root_cause": "GENERIC_BASE_RELIEF_WATCHDOG_CROSS_TALK",
            "attempt_receipt": _artifact(ATTEMPT6_RECEIPT_PATH),
            "immutable_runtime_artifacts": immutable_artifacts,
        },
        "scope": {
            "authorized": "Mask generic relief only during explicit P1 acquisition-wait, preserve stage0 timeout/non-P1 relief, latch reset qualification across reset, and repair receipt ancestry.",
            "attempt6_immutable": True,
            "attempt7_prepared": False,
            "gpu_or_isaacsim_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "implementation_contract": {
            "p1_generic_relief_mask": "active & ~(pull_p1_acquisition & acquisition_wait)",
            "stage0_timeout_semantics": "unchanged and independent",
            "non_p1_generic_relief_semantics": "active mask unchanged",
            "reset_qualification_persistence": "latch terminal evidence before reset buffer clear and consume it in terminal/summary exports",
            "receipt_binding": "Attempt7+ requires explicit exact R5 receipt SHA and R5->Attempt6->R4 ancestry",
            "report_only_thresholds": True,
            "effort_provenance": "ESTIMATE_ONLY",
        },
        "changed_files": changed_files,
        "validation": {
            "static": "PASS",
            "runtime": "UNVERIFIED",
            "commands": [
                "py_compile leased Python files",
                "pytest exact five-file pull gate",
                "receipt parser/hash assertions",
                "git diff --check",
            ],
            "runtime_not_run_reason": "R5 contract forbids preparing/running Attempt7; the repair requires a separately authorized runtime assessment.",
        },
        "acceptance": {
            "acquisition_wait_cannot_emit_generic_base_relief_timeout": True,
            "stage0_timeout_remains_independent": True,
            "non_p1_generic_relief_unchanged": True,
            "reset_summary_terminal_latch_agree": True,
            "actual_attempt6_schema_receipt": True,
            "r5_sha_and_ancestry_fail_fast": True,
            "attempt6_immutable": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim/GPU runtime PASS is asserted for R5.",
            "The generic relief mask and reset latch are statically covered; runtime behavior awaits a separately authorized follow-up.",
            "No pull-mechanism verdict is asserted.",
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
