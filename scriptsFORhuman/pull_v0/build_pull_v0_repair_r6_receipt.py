#!/usr/bin/env python3
"""Build the immutable R6 command-to-plant telemetry repair receipt."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R6_RECEIPT.json"
R5_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R5_RECEIPT.json"
ATTEMPT7_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT7_RECEIPT.json"
ATTEMPT7_ROOT = ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt7"
EXPECTED_R5_RECEIPT_SHA256 = (
    "fa66f0c204e5969529db7eba56a1949c4d897ad3d578ad3d477abd16200762ef"
)
EXPECTED_ATTEMPT7_RECEIPT_SHA256 = (
    "26256715bbf9d3885f87079e98b42c0a4a275a2a27eced1393cb33e0862f2989"
)
EXPECTED_STALE_CANDIDATE_ID = (
    "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
)
PRE_HASHES = {
    "gr00t/rl/envs/door/door_open_a2_base.py": "0901ce5920afd35c3794b38850cb6850a6013e1cf899136f63220fd04cda44ef",
    "gr00t/rl/tests/test_a2_pull_namespace.py": "44ebf1a6d0fc8f8cb93eedf2c833f2829954c5c2e501d13345e4d3811503bc36",
    "gr00t/rl/tests/test_a2_pull_telemetry.py": "837d50dc551e9392015dc10cfd9019b2d0b74b2ef4427e1ba6fa7b8768ec4b5b",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "2d2035a2f111b20670816c7ba18a0b8565671c433683a647fcd633109d192732",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "9e84c41d735331c659a81d290bac3ae83c9dd275707af2919c683102d6015c0b",
}
CHANGED_REASONS = {
    "gr00t/rl/envs/door/door_open_a2_base.py": "Add bounded post-executor stage0 command-to-plant telemetry without changing signed target, action mapping, timeout, predicates, or stage logic.",
    "gr00t/rl/tests/test_a2_pull_namespace.py": "Guard generic actual-schema receipt routing, Attempt7 stage0 blocker classification, and R6 ancestry/SHA fail-fast behavior.",
    "gr00t/rl/tests/test_a2_pull_telemetry.py": "Cover yaw-pi command projection, signed fixed target inference, finite/report-only progress metrics, and unchanged stage0 controls.",
    "scriptsFORhuman/pull_v0/build_p1_anchor_stop_receipts.py": "Route every attempt >=6 through one actual base-owned admission schema and classify known watchdog/stage0 outcomes without legacy pull namespace fabrication.",
    "scriptsFORhuman/pull_v0/run_p1_push_anchor.py": "Require exact explicit R6 SHA for Attempt8+ and validate R6->Attempt7->R5->Attempt6->R4 ancestry without a self-hash cycle.",
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
    if _sha256(R5_RECEIPT_PATH) != EXPECTED_R5_RECEIPT_SHA256:
        raise RuntimeError("Immutable Repair R5 receipt hash changed.")
    if _sha256(ATTEMPT7_RECEIPT_PATH) != EXPECTED_ATTEMPT7_RECEIPT_SHA256:
        raise RuntimeError("Immutable Attempt7 receipt hash changed.")
    r5 = _load(R5_RECEIPT_PATH)
    attempt7 = _load(ATTEMPT7_RECEIPT_PATH)
    if (
        r5.get("schema_version") != "pull_v0_repair_r5_receipt_v1"
        or r5.get("repair_revision") != "R5"
        or r5.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
        or attempt7.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v7"
        or attempt7.get("attempt") != 7
        or attempt7.get("status") != "BLOCKED"
        or attempt7.get("probe_validity") != "PROBE_INVALID"
        or attempt7.get("admission_blocker")
        != "STAGE0_COMMAND_TO_PLANT_RESPONSE_UNRESOLVED"
        or attempt7.get("pull_mechanism_verdict") != "NOT_ASSESSED"
    ):
        raise RuntimeError("Attempt7 receipt is not the authorized R6 trigger artifact.")

    immutable_paths = {
        "plan": EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT7_PLAN.json",
        "process_receipt": ATTEMPT7_ROOT / "process_receipt.json",
        "summary": ATTEMPT7_ROOT / "eval/a2_hold_oracle_summary.json",
        "metrics": ATTEMPT7_ROOT / "eval/metrics_eval.json",
        "log": ATTEMPT7_ROOT / "stdout_stderr.log",
    }
    immutable_artifacts = {name: _artifact(path) for name, path in immutable_paths.items()}
    expected_immutable_hashes = {
        "plan": "c7874901396979aae5ddd622f598203554bf798c387a61dff511ca900b8fc2dd",
        "process_receipt": "063b3a3b55871a59b005d1a977cf31a441dec8a6fd8f690055c9d66477a0bfe8",
        "summary": "f62c04772875ea343e417a2a686d5416808bf2f6bd53d8fbad5632098e71de45",
        "metrics": "c159cf4184a82bfbf700b8aba2097edb4d6e109f3367227ca4fcce07798f747e",
        "log": "0e56a0a3ff1770c8d444c3a4fa4a9310b75122b47a8b5be9d2bb868cd9d03417",
    }
    for name, expected in expected_immutable_hashes.items():
        if immutable_artifacts[name]["sha256"] != expected:
            raise RuntimeError(f"Immutable Attempt7 {name} hash changed.")

    summary = _load(immutable_paths["summary"])
    metrics = _load(immutable_paths["metrics"])
    if (
        summary.get("per_env_outcome") != ["PULL_P1_STAGE0_TIMEOUT"]
        or summary.get("per_env_pass") != [False]
        or summary.get("per_env_proof_completed") != [False]
        or summary.get("per_env_latch_released") != [True]
        or summary.get("per_env_max_hinge_rad") != [None]
        or summary.get("per_env_max_body_force_n") != [0.0]
        or summary.get("finalize_called") is not True
    ):
        raise RuntimeError("Attempt7 immutable summary does not preserve stage0 timeout.")
    terminal = metrics["episode_terminal_diagnostics"][0]
    admission = terminal["push_anchor_admission"]
    if (
        admission.get("schema")
        != "a2_piper_pull_v0_push_anchor_admission_terminal_v1"
        or "stage0_command_response" in admission
        or admission.get("trace_step_count") != len(admission.get("trace", []))
        or admission.get("trace_step_count") != 123
        or admission.get("terminal_snapshot", {}).get("outcome")
        != "PULL_P1_STAGE0_TIMEOUT"
        or any(str(key).startswith("pull_v0_") for key in admission)
    ):
        raise RuntimeError("Attempt7 immutable admission schema is not the expected actual base schema.")
    if metrics.get("completed_episodes") != 1 or metrics.get("episode_max_stage_reached") != [0]:
        raise RuntimeError("Attempt7 immutable metrics do not preserve the stage0 terminal.")

    changed_files = {}
    for relative, pre_hash in PRE_HASHES.items():
        path = ROOT / relative
        actual = _sha256(path)
        if actual == pre_hash:
            raise RuntimeError(f"R6 implementation did not change leased path: {relative}")
        changed_files[relative] = {
            "pre_sha256": pre_hash,
            "post_sha256": actual,
            "reason": CHANGED_REASONS[relative],
        }
    new_files = {
        "scriptsFORhuman/pull_v0/build_pull_v0_repair_r6_receipt.py": "Record exact R6 ancestry, immutable Attempt7 evidence, blocker boundary, and static/runtime validation status.",
        str(ATTEMPT7_RECEIPT_PATH.relative_to(ROOT)): "Immutable Attempt7 actual-schema receipt preserving the stage0 timeout and unresolved command-to-plant response boundary.",
    }
    for relative, reason in new_files.items():
        path = ROOT / relative
        changed_files[relative] = {
            "pre_sha256": None,
            "post_sha256": _sha256(path),
            "reason": reason,
        }

    return {
        "schema_version": "pull_v0_repair_r6_receipt_v1",
        "generated_at_hkt": _hkt_now(),
        "repair_revision": "R6",
        "status": "APPROVED_FOR_ATTEMPT8_PREPARATION_ONLY",
        "stale_candidate_id": EXPECTED_STALE_CANDIDATE_ID,
        "root_cause": {
            "code": "STAGE0_COMMAND_TO_PLANT_RESPONSE_UNRESOLVED",
            "conclusion": "Attempt7 preserved the signed stage0 target, body-frame command, and sole hard timeout, but its immutable actual-schema trace stopped before post-executor physical command, downstream lower-body command, and observed root response telemetry could be captured.",
            "attempt7_summary_outcome": "PULL_P1_STAGE0_TIMEOUT",
            "attempt7_trace_step_count": 123,
            "attempt7_stage0_rows": 120,
            "attempt7_command_response_telemetry_present": False,
            "stage0_timeout_remains_sole_hard_stop": True,
            "signed_target_and_band_unchanged": True,
        },
        "parent_receipt": {
            "path": str(R5_RECEIPT_PATH.relative_to(ROOT)),
            "sha256": EXPECTED_R5_RECEIPT_SHA256,
            "repair_revision": "R5",
        },
        "trigger": {
            "attempt": 7,
            "root_cause": "STAGE0_COMMAND_TO_PLANT_RESPONSE_UNRESOLVED",
            "attempt_receipt": _artifact(ATTEMPT7_RECEIPT_PATH),
            "immutable_runtime_artifacts": immutable_artifacts,
        },
        "scope": {
            "authorized": "Add bounded report-only stage0 command-to-plant observability using existing A2Base high-level action/command buffers and articulation root data; preserve signed target, axis mapping, base command, timeout, predicates, and stage ordering.",
            "attempt7_immutable": True,
            "attempt8_prepared": False,
            "gpu_or_isaacsim_runtime_executed": False,
            "pull_verdict": "NOT_ASSESSED",
        },
        "implementation_contract": {
            "raw_high_level_base_action": "A2Base._a2_base_command_raw",
            "physical_base_command": "A2Base.get_physical_base_command()",
            "desired_world_xy_reconstruction": "physical planar command rotated by observed root yaw",
            "downstream_lower_body_command": "A2Base._get_a2_dog_actions()",
            "observed_root_response": "ArticulationData.root_pos_w/root_quat_w/root_lin_vel_w",
            "progress_metrics": "finite dot/cosine with explicit undefined flags",
            "anti_alignment": "report_only; no stage/timeout predicate",
            "stage0_timeout_semantics": "unchanged and independent",
            "receipt_binding": "Attempt8+ requires explicit exact R6 receipt SHA and R6->Attempt7->R5->Attempt6->R4 ancestry",
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
            "runtime_not_run_reason": "R6 contract requires a separately authorized Attempt8 runtime; immutable Attempt7 evidence is not re-run.",
        },
        "acceptance": {
            "actual_attempt6_and_attempt7_generic_receipt_route": True,
            "unknown_actual_outcome_fails_fast": True,
            "no_legacy_pull_v0_admission_fields": True,
            "stage0_command_to_plant_response_fields_bounded_and_report_only": True,
            "signed_target_axis_mapping_and_timeout_unchanged": True,
            "attempt7_immutable": True,
            "r6_sha_and_ancestry_fail_fast": True,
            "no_self_hash_cycle": True,
            "runtime_pass_asserted": False,
        },
        "unverified_claims": [
            "No IsaacSim/GPU runtime PASS is asserted for R6.",
            "Telemetry fields are statically covered; response values await a separately authorized Attempt8 runtime.",
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
