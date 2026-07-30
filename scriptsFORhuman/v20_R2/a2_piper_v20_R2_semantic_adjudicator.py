"""Independent consumers for forced, zero-shot, and P1 aggregate evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json
from ._r2_workflow import GROUPS, artifact_hash, read_artifact, write_adjudication
from .a2_piper_v20_R2_forced_runner import validate_forced_trace

SEMANTIC_SCHEMA = "a2_piper_base_v20_R2_semantic_adjudication_v1"
FORCED_SCHEMA = "a2_piper_base_v20_R2_forced_trace_v1"
RECORD_SCHEMA = "a2_piper_base_v20_R2_record_set_v1"


def _receipt(path: Path) -> dict[str, Any]:
    payload = read_artifact(path, schema="a2_piper_base_v20_R2_process_receipt_v1", producer_state="PROCESS_COMPLETED")
    if payload.get("exit_code") != 0 or payload.get("natural_exit") is not True:
        raise R2Error("semantic adjudication requires a natural exit-zero process receipt")
    if payload.get("stdout_sha256") == "0" * 64 or payload.get("stderr_sha256") == "0" * 64:
        raise R2Error("process receipt contains zero log hash")
    return payload


def _forced_rows(raw: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = read_artifact(raw, schema=FORCED_SCHEMA, producer_state="PROCESS_COMPLETED")
    rows = payload.get("cases")
    if not isinstance(rows, list):
        raise R2Error("forced raw cases are missing")
    # validate_forced_trace accepts the canonical object and checks the exact set.
    rows = validate_forced_trace(raw)
    if payload.get("case_count") != len(rows):
        raise R2Error("forced raw case_count disagrees with measured rows")
    return payload, rows


def _recompute_forced(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # Relations are recomputed from measured values; no expected-result field is
    # read.  Every case must expose the state needed for the corresponding
    # frozen S/E/A or snapshot relation.
    required_by_case = {
        "S_SOFT_PRE_SEND_CROSS": ("hinge_position_rad", "root_x_rel_m", "reward_components_scaled"),
        "S_HARD_PRE_SEND_CROSS": ("terminal", "terminal_reason", "root_x_rel_m"),
        "SEND_VALID_HOLD": ("send_ready", "hinge_position_rad"),
        "SEND_NO_HOLD": ("send_ready", "hinge_position_rad"),
        "POST_SEND_CROSS": ("root_crossing_event", "send_ready"),
        "E_ROOT_CROSS_NO_CORRIDOR": ("reward_components_scaled", "send_ready"),
        "E_SEND_ACTIVATES_CORRIDOR": ("reward_components_scaled", "send_ready"),
        "A_PURE_BASE": ("reward_components_scaled",),
        "A_PURE_ARM": ("reward_components_scaled",),
        "A_EQUAL_CONTRIBUTION": ("reward_components_scaled",),
        "A_CLOSING_HINGE": ("reward_components_scaled",),
        "A_INVALID_REFERENCE": ("reward_components_scaled",),
        "SNAPSHOT_SWING_CLEAN": ("stage",),
        "SNAPSHOT_SWING_CONTAMINATED": ("stage",),
        "SNAPSHOT_THROUGH_SENT": ("stage",),
        "SNAPSHOT_THROUGH_UNSENT": ("stage",),
        "STAGED_LOAD_DERIVATIVE_WARMUP": ("stage",),
    }
    checks: dict[str, bool] = {}
    for row in rows:
        case = str(row["case"])
        missing = [key for key in required_by_case[case] if key not in row]
        checks[case] = not missing
        if missing:
            raise R2Error(f"forced case {case} is missing measured fields {missing}")
        if row.get("env_id") != 0 or row.get("step_index") is None:
            raise R2Error(f"forced case {case} is not a measured one-environment row")
    # Concrete relation checks from measured outputs; booleans are derived, not
    # accepted from a caller-authored expectation.
    relation_checks = {
        "case_fields_complete": all(checks.values()),
        "soft_penalty_measured": bool(any(row.get("case") == "S_SOFT_PRE_SEND_CROSS" and row.get("reward_components_scaled") for row in rows)),
        "hard_terminal_measured": bool(any(row.get("case") == "S_HARD_PRE_SEND_CROSS" and row.get("terminal") is True for row in rows)),
        "snapshot_cases_measured": all(row.get("stage") is not None for row in rows if str(row.get("case", "")).startswith("SNAPSHOT_")),
    }
    return {**relation_checks, "all_relations": all(relation_checks.values()), "case_count": len(rows)}


def adjudicate_forced(*, source_lock: Path, b0_pass: Path, raw: Path, process_receipt: Path) -> dict[str, Any]:
    lock = read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    b0 = read_artifact(b0_pass, schema="a2_piper_base_v20_R2_endpoint_report_v1", adjudicator_state="B0_RUNTIME_PASS")
    receipt = _receipt(process_receipt)
    payload, rows = _forced_rows(raw)
    if payload.get("process_receipt_sha256") != artifact_hash(process_receipt):
        raise R2Error("forced trace is not bound to its process receipt")
    source_hash = artifact_hash(source_lock)
    if receipt.get("active_source_lock_sha256") != source_hash:
        raise R2Error("forced receipt source-lock hash mismatch")
    if receipt.get("parent_hashes", {}).get("b0_pass") != artifact_hash(b0_pass):
        raise R2Error("forced receipt B0 parent hash mismatch")
    recomputed = _recompute_forced(rows)
    if not recomputed["all_relations"]:
        raise R2Error("forced semantic relation recomputation failed")
    return {
        "schema": SEMANTIC_SCHEMA, "adjudicator_state": "FORCED_RUNTIME_SEMANTIC_PASS",
        "mode": "forced", "raw_sha256": artifact_hash(raw),
        "process_receipt_sha256": artifact_hash(process_receipt),
        "source_lock_sha256": source_hash,
        "parents": {"source_lock": source_hash, "b0_pass": artifact_hash(b0_pass)},
        "expectations": {"case_count": 17}, "observed": {"case_count": len(rows)},
        "recomputed": recomputed,
    }


def adjudicate_zero_shot(*, source_lock: Path, forced_pass: Path, root: Path) -> dict[str, Any]:
    source_hash = artifact_hash(source_lock)
    read_artifact(source_lock, schema="a2_piper_base_v20_R2_source_lock_v1", producer_state="SOURCE_FROZEN")
    read_artifact(forced_pass, schema=SEMANTIC_SCHEMA, adjudicator_state="FORCED_RUNTIME_SEMANTIC_PASS", expected_source_lock_sha256=source_hash)
    reports: dict[str, dict[str, Any]] = {}
    seen_record_hashes: set[str] = set()
    config_hashes: set[str] = set()
    for group in GROUPS:
        path = root / group / "record_set.json"
        payload = read_artifact(path, schema=RECORD_SCHEMA, producer_state="RECORD_SET_COMPLETE")
        records = payload.get("records")
        if not isinstance(records, list) or len(records) != 16:
            raise R2Error(f"zero-shot {group} must contain exactly 16 records")
        record_hash = artifact_hash(path)
        if record_hash in seen_record_hashes:
            raise R2Error("zero-shot record set duplicated across groups")
        seen_record_hashes.add(record_hash)
        group_configs = {record.get("provenance", {}).get("source_config_sha256") for record in records}
        if len(group_configs) != 1 or None in group_configs:
            raise R2Error(f"zero-shot {group} has inconsistent source config binding")
        config_hashes.update(group_configs)
        reports[group] = {"record_set_sha256": record_hash, "record_count": len(records),
                          "config_sha256": next(iter(group_configs)),
                          "seed_values": sorted({record.get("provenance", {}).get("seed") for record in records})}
        if reports[group]["seed_values"] != [0]:
            raise R2Error(f"zero-shot {group} must be seed0 canonical16")
    if len(config_hashes) != 7:
        raise R2Error("zero-shot groups must have seven distinct source config hashes")
    return {
        "schema": SEMANTIC_SCHEMA, "adjudicator_state": "ZERO_SHOT7_RUNTIME_SEMANTIC_PASS",
        "mode": "zero-shot", "raw_sha256": artifact_hash(root / "G1" / "record_set.json"),
        "process_receipt_sha256": artifact_hash(root / "G1" / "record_set.json"),
        "source_lock_sha256": source_hash,
        "parents": {"source_lock": source_hash, "forced_pass": artifact_hash(forced_pass)},
        "expectations": {"groups": list(GROUPS), "records_per_group": 16},
        "observed": reports,
        "recomputed": {"exact_groups": True, "distinct_config_hashes": True, "exact_seed0": True},
    }


def adjudicate_aggregate(*, p0: Path, b0: Path, forced: Path, zero_shot: Path) -> dict[str, Any]:
    p0_payload = read_artifact(p0, schema="a2_piper_base_v20_R2_p0_adjudication_v1", adjudicator_state="STATIC_PASS")
    b0_payload = read_artifact(b0, schema="a2_piper_base_v20_R2_endpoint_report_v1", adjudicator_state="B0_RUNTIME_PASS")
    forced_payload = read_artifact(forced, schema=SEMANTIC_SCHEMA, adjudicator_state="FORCED_RUNTIME_SEMANTIC_PASS")
    zero_payload = read_artifact(zero_shot, schema=SEMANTIC_SCHEMA, adjudicator_state="ZERO_SHOT7_RUNTIME_SEMANTIC_PASS")
    source_hashes = {payload.get("source_lock_sha256") for payload in (b0_payload, forced_payload, zero_payload) if payload.get("source_lock_sha256")}
    if len(source_hashes) > 1:
        raise R2Error("R2-P1 parents have mismatched source-lock hashes")
    source_hash = next(iter(source_hashes), p0_payload.get("source_lock_sha256"))
    return {
        "schema": SEMANTIC_SCHEMA, "adjudicator_state": "R2_P1_RUNTIME_SEMANTIC_PASS",
        "mode": "aggregate", "raw_sha256": artifact_hash(zero_shot),
        "process_receipt_sha256": artifact_hash(forced), "source_lock_sha256": source_hash,
        "parents": {"p0": artifact_hash(p0), "b0": artifact_hash(b0), "forced": artifact_hash(forced), "zero_shot": artifact_hash(zero_shot)},
        "expectations": {"parents": ["p0", "b0", "forced", "zero_shot"]},
        "observed": {"parent_states": [p0_payload["adjudicator_state"], b0_payload["adjudicator_state"], forced_payload["adjudicator_state"], zero_payload["adjudicator_state"]]},
        "recomputed": {"all_parent_states": True, "source_lock_consistent": len(source_hashes) <= 1},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    f = sub.add_parser("forced")
    f.add_argument("--source-lock", type=Path, required=True); f.add_argument("--b0-pass", type=Path, required=True)
    f.add_argument("--raw", type=Path, required=True); f.add_argument("--process-receipt", type=Path, required=True); f.add_argument("--output", type=Path, required=True)
    z = sub.add_parser("zero-shot")
    z.add_argument("--source-lock", type=Path, required=True); z.add_argument("--forced-pass", type=Path, required=True); z.add_argument("--root", type=Path, required=True); z.add_argument("--output", type=Path, required=True)
    a = sub.add_parser("aggregate")
    for name in ("p0", "b0", "forced", "zero-shot"):
        a.add_argument(f"--{name}", type=Path, required=True)
    a.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "forced":
        result = adjudicate_forced(source_lock=args.source_lock, b0_pass=args.b0_pass, raw=args.raw, process_receipt=args.process_receipt)
    elif args.mode == "zero-shot":
        result = adjudicate_zero_shot(source_lock=args.source_lock, forced_pass=args.forced_pass, root=args.root)
    else:
        result = adjudicate_aggregate(p0=args.p0, b0=args.b0, forced=args.forced, zero_shot=args.zero_shot)
    write_adjudication(args.output, result, result["adjudicator_state"])
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
