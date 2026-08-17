#!/usr/bin/env python3
"""Fail-closed static gates for the pull-v5.5 residual adapter ladder."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PLAN_ID = "a2_piper_pull_v5_5_residual_terminal_hold_adapter"
PLANNER_SCHEMA = "a2_piper_pull_v5_5_planner_architecture_decision_v1"
TRAINING_SCHEMA = "a2_piper_pull_v5_5_adapter_training_gate_v1"
REHEARSAL_SCHEMA = "a2_piper_pull_v5_5_adapter_rehearsal_v1"
ANCHOR_SCHEMA = "a2_piper_pull_v5_5_adapter_anchor_v1"
TRACE_SCHEMA = "a2_piper_pull_v5_5_adapter_holdtrack_trace_v1"
DEFAULT_PLANNER = ROOT / "logs_eval/a2_piper_pull_v5/v5_5_planner_architecture_decision.json"
DEFAULT_TRAINING = ROOT / "logs_eval/a2_piper_pull_v5/v5_5_adapter_gate/TRAINING_GATE.json"
DEFAULT_REHEARSAL = ROOT / "logs_eval/a2_piper_pull_v5/v5_5_adapter_rehearsal/REHEARSAL.json"
DEFAULT_ANCHOR = ROOT / "logs_eval/a2_piper_pull_v5/v5_5_adapter_anchor/ANCHOR.json"
PRELUDE_FAMILIES = (
    "near_rest",
    "coarse_neg",
    "coarse_pos",
    "straight_minus_x",
    "side_step",
)
SEQUENCES = ("S1", "S2", "S3", "S4")
TERMINAL_HOLD_STEPS = 100
WAYPOINT_TOLERANCE_M = 0.05
YAW_TOLERANCE_RAD = 0.15
MAX_ANCHOR_ATTEMPTS = 3


class GateRejected(RuntimeError):
    """Raised when a prerequisite is missing, malformed, stale, or failed."""


def _read(path: Path, label: str) -> Mapping[str, Any]:
    path = path.expanduser().resolve()
    if path.is_symlink() or not path.is_file():
        raise GateRejected(f"{label} is missing or not a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateRejected(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, Mapping):
        raise GateRejected(f"{label} must be a JSON object")
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise GateRejected(f"{label} must be finite numeric; got {value!r}")
    return float(value)


def _diagnostic(row: Mapping[str, Any], label: str) -> None:
    if row.get("record_class") != "interface_characterization":
        raise GateRejected(f"{label}.record_class must be interface_characterization")
    if row.get("scientific_denominator_included") is not False:
        raise GateRejected(f"{label} must be excluded from the scientific denominator")
    if row.get("denominator_scope") not in ("none", None):
        raise GateRejected(f"{label}.denominator_scope must be none")
    if row.get("schema") not in (None, TRACE_SCHEMA):
        raise GateRejected(f"{label}.schema is not the v5.5 trace schema")


def _terminal_row(row: object, label: str, *, expected_episode_prefix: str | None = None) -> Mapping[str, Any]:
    if not isinstance(row, Mapping):
        raise GateRejected(f"{label} must be an object")
    _diagnostic(row, label)
    if expected_episode_prefix is not None and not str(row.get("episode_id", "")).startswith(expected_episode_prefix):
        raise GateRejected(f"{label}.episode_id is not bound to the expected phase")
    if row.get("terminal_after_step") is not True:
        raise GateRejected(f"{label} must bind terminal timing to returned dones")
    if row.get("returned_dones_binding") != "env.step returned dones":
        raise GateRejected(f"{label} must declare env.step returned-dones binding")
    if row.get("terminal_hold_steps") != TERMINAL_HOLD_STEPS:
        raise GateRejected(f"{label}.terminal_hold_steps must equal 100")
    if row.get("terminal_current_state") is not True or row.get("done") is not True:
        raise GateRejected(f"{label} must be a terminal-current DONE row")
    if row.get("adapter_active") is not True:
        raise GateRejected(f"{label} must attest adapter_active=true")
    checkpoint = row.get("adapter_checkpoint")
    step = row.get("adapter_checkpoint_step")
    if not isinstance(checkpoint, str) or not checkpoint:
        raise GateRejected(f"{label} must record the adapter checkpoint path")
    if isinstance(step, bool) or not isinstance(step, int) or step < 0:
        raise GateRejected(f"{label} must record a non-negative adapter checkpoint step")
    _finite(row.get("xy_error_m"), f"{label}.xy_error_m")
    _finite(row.get("yaw_error_rad"), f"{label}.yaw_error_rad")
    if float(row["xy_error_m"]) > WAYPOINT_TOLERANCE_M:
        raise GateRejected(f"{label} exceeds 0.05 m waypoint tolerance")
    if abs(float(row["yaw_error_rad"])) > YAW_TOLERANCE_RAD:
        raise GateRejected(f"{label} exceeds 0.15 rad yaw tolerance")
    return row


def validate_planner_decision(path: Path = DEFAULT_PLANNER) -> dict[str, Any]:
    decision = _read(path, "v5.5 planner decision")
    if decision.get("schema") != PLANNER_SCHEMA or decision.get("plan_id") != PLAN_ID:
        raise GateRejected("planner decision schema/plan_id mismatch")
    if decision.get("decision") != "ACTIVATE_RESIDUAL_TERMINAL_HOLD_ADAPTER":
        raise GateRejected("planner decision does not activate the residual adapter rung")
    if decision.get("fine_tune_deferred") is not True:
        raise GateRejected("planner decision must defer HOMIE fine-tuning")
    if decision.get("scientific_denominator_included") is not False:
        raise GateRejected("planner decision must remain diagnostic-only")
    if decision.get("status") != "PLANNER_ACCEPTED":
        raise GateRejected("planner decision is not PLANNER_ACCEPTED")
    return dict(decision)


def training_gate_pass(counts: Mapping[str, int]) -> bool:
    if set(counts) != set(PRELUDE_FAMILIES):
        raise ValueError("training gate counts must cover exactly the five prelude families")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
        raise ValueError("training gate counts must be non-negative integers")
    return all(counts[family] >= 15 for family in PRELUDE_FAMILIES) and sum(counts.values()) >= 77


def validate_training_gate(
    path: Path = DEFAULT_TRAINING, *, planner_path: Path = DEFAULT_PLANNER
) -> dict[str, Any]:
    validate_planner_decision(planner_path)
    receipt = _read(path, "v5.5 training gate receipt")
    if receipt.get("schema") != TRAINING_SCHEMA or receipt.get("plan_id") != PLAN_ID:
        raise GateRejected("training gate schema/plan_id mismatch")
    status = receipt.get("status")
    if status == "NOT_RUN":
        return {"status": "NOT_RUN", "path": str(path.expanduser().resolve())}
    if status == "CRASH":
        raise GateRejected("training gate recorded a crash")
    if status != "PASS":
        raise GateRejected(f"training gate status is not PASS: {status!r}")
    rows = receipt.get("rows")
    if not isinstance(rows, list) or len(rows) != 80:
        raise GateRejected("training gate must contain exactly 80 held-out rows")
    row_counts = {family: 0 for family in PRELUDE_FAMILIES}
    done_counts = {family: 0 for family in PRELUDE_FAMILIES}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise GateRejected(f"training gate row {index} must be an object")
        _diagnostic(row, f"training row {index}")
        family = row.get("family")
        if family not in row_counts:
            raise GateRejected(f"training row {index} has unknown family {family!r}")
        if row.get("adapter_active") is not True:
            raise GateRejected(f"training row {index} must attest adapter_active=true")
        checkpoint = row.get("adapter_checkpoint")
        checkpoint_step = row.get("adapter_checkpoint_step")
        if not isinstance(checkpoint, str) or not checkpoint:
            raise GateRejected(f"training row {index} must record adapter checkpoint path")
        if isinstance(checkpoint_step, bool) or not isinstance(checkpoint_step, int) or checkpoint_step < 0:
            raise GateRejected(f"training row {index} must record non-negative adapter checkpoint step")
        if row.get("terminal_after_step") is not True or row.get("returned_dones_binding") != "env.step returned dones":
            raise GateRejected(f"training row {index} lacks returned-dones binding")
        if not isinstance(row.get("done"), bool):
            raise GateRejected(f"training row {index}.done must be bool")
        row_counts[family] += 1
        if row["done"]:
            done_counts[family] += 1
    if row_counts != {family: 16 for family in PRELUDE_FAMILIES}:
        raise GateRejected(f"training gate must have 16 rows per family: {row_counts}")
    declared_rows = receipt.get("family_row_counts")
    declared_done = receipt.get("family_done_counts")
    if declared_rows != row_counts or declared_done != done_counts or not training_gate_pass(done_counts):
        raise GateRejected("training gate fails per-family/overall 15/16 and 77/80 criteria")
    return {
        "status": "PASS",
        "path": str(path.expanduser().resolve()),
        "family_row_counts": row_counts,
        "family_done_counts": done_counts,
        "overall_done": sum(done_counts.values()),
    }


def validate_rehearsal(
    path: Path = DEFAULT_REHEARSAL,
    *,
    planner_path: Path = DEFAULT_PLANNER,
    training_path: Path = DEFAULT_TRAINING,
) -> dict[str, Any]:
    training = validate_training_gate(training_path, planner_path=planner_path)
    if training.get("status") != "PASS":
        raise GateRejected("rehearsal is blocked because the training gate is not PASS")
    receipt = _read(path, "v5.5 rehearsal receipt")
    if receipt.get("schema") != REHEARSAL_SCHEMA or receipt.get("plan_id") != PLAN_ID:
        raise GateRejected("rehearsal schema/plan_id mismatch")
    if receipt.get("status") != "PASS":
        raise GateRejected(f"rehearsal status is not PASS: {receipt.get('status')!r}")
    cells = receipt.get("cells")
    if not isinstance(cells, list) or len(cells) != 2:
        raise GateRejected("rehearsal must contain exactly two cells")
    seen_targets: set[tuple[float, float]] = set()
    for cell_index, cell in enumerate(cells):
        if not isinstance(cell, Mapping):
            raise GateRejected(f"rehearsal cell {cell_index} must be an object")
        target = (_finite(cell.get("yaw_delta_rad"), "rehearsal yaw_delta_rad"), _finite(cell.get("xy_delta_m"), "rehearsal xy_delta_m"))
        if target not in {(-2.5, 0.3), (1.0, 0.3)}:
            raise GateRejected(f"rehearsal target must be (-2.5,0.3) or (1.0,0.3), got {target}")
        seen_targets.add(target)
        rows = cell.get("rows")
        if not isinstance(rows, list) or len(rows) != 8:
            raise GateRejected("each rehearsal cell requires exactly eight rows")
        for row_index, row in enumerate(rows):
            _terminal_row(row, f"rehearsal cell {cell_index} row {row_index}", expected_episode_prefix="rehearsal:")
    if seen_targets != {(-2.5, 0.3), (1.0, 0.3)}:
        raise GateRejected("rehearsal cells do not cover both registered targets")
    return {"status": "PASS", "path": str(path.expanduser().resolve()), "cells": 2}


def validate_anchor(
    path: Path = DEFAULT_ANCHOR,
    *,
    planner_path: Path = DEFAULT_PLANNER,
    training_path: Path = DEFAULT_TRAINING,
    rehearsal_path: Path = DEFAULT_REHEARSAL,
) -> dict[str, Any]:
    rehearsal = validate_rehearsal(
        rehearsal_path, planner_path=planner_path, training_path=training_path
    )
    if rehearsal.get("status") != "PASS":
        raise GateRejected("anchor is blocked because rehearsal is not PASS")
    receipt = _read(path, "v5.5 anchor receipt")
    if receipt.get("schema") != ANCHOR_SCHEMA or receipt.get("plan_id") != PLAN_ID:
        raise GateRejected("anchor schema/plan_id mismatch")
    if receipt.get("status") != "PASS":
        raise GateRejected(f"anchor status is not PASS: {receipt.get('status')!r}")
    attempts = receipt.get("attempts")
    if not isinstance(attempts, list) or not attempts or len(attempts) > MAX_ANCHOR_ATTEMPTS:
        raise GateRejected("anchor permits one through three attempts")
    if any(not isinstance(item, Mapping) for item in attempts):
        raise GateRejected("anchor attempts must be objects")
    if [item.get("attempt") for item in attempts] != list(range(len(attempts))):
        raise GateRejected("anchor attempt revisions must be contiguous 0..2")
    final = attempts[-1]
    if not isinstance(final, Mapping) or final.get("status") != "PASS":
        raise GateRejected("final anchor attempt is not PASS")
    rows = final.get("rows")
    admitted = final.get("admitted_sequences")
    if not isinstance(admitted, list) or not admitted or any(sequence not in SEQUENCES for sequence in admitted):
        raise GateRejected("anchor final attempt must declare a non-empty admitted sequence subset")
    if len(set(admitted)) != len(admitted):
        raise GateRejected("anchor admitted sequence subset must not repeat sequences")
    if not isinstance(rows, list) or len(rows) != 16 * len(admitted):
        raise GateRejected("anchor requires sixteen terminal rows per admitted sequence")
    counts = {sequence: 0 for sequence in admitted}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or row.get("sequence") not in counts:
            raise GateRejected(f"anchor row {index} has an invalid sequence")
        _terminal_row(row, f"anchor row {index}", expected_episode_prefix="anchor:")
        counts[row["sequence"]] += 1
    if counts != {sequence: 16 for sequence in admitted}:
        raise GateRejected(f"anchor admitted sequence coverage is incomplete: {counts}")
    return {
        "status": "PASS",
        "path": str(path.expanduser().resolve()),
        "attempts": len(attempts),
        "sequence_counts": counts,
        "admitted_sequences": list(admitted),
    }


def validate_invariant12(
    rows: list[Mapping[str, Any]], *, expected_rows: int | None = None
) -> dict[str, Any]:
    """Assert adapter inactivity for P3/P4 training actions and DV rows."""

    if not isinstance(rows, list) or not rows:
        raise GateRejected("invariant 12 requires non-empty P3/P4/DV coverage")
    required = len(rows) if expected_rows is None else expected_rows
    if isinstance(required, bool) or not isinstance(required, int) or required <= 0:
        raise GateRejected("invariant 12 expected_rows must be a positive integer")
    if len(rows) != required:
        raise GateRejected(f"invariant 12 coverage is incomplete: {len(rows)} rows, expected {required}")
    checked = 0
    for index, row in enumerate(rows):
        phase = row.get("phase")
        if phase not in {"P3", "P4", "DV"}:
            continue
        if row.get("adapter_active") is not False:
            raise GateRejected(f"invariant 12 violation at row {index}: adapter_active must be false")
        if row.get("adapter_checkpoint") not in (None, ""):
            raise GateRejected(f"invariant 12 violation at row {index}: adapter checkpoint must be absent")
        if row.get("adapter_checkpoint_step") not in (None, ""):
            raise GateRejected(f"invariant 12 violation at row {index}: adapter checkpoint step must be absent")
        checked += 1
    if checked != required:
        raise GateRejected(f"invariant 12 checked {checked} rows, expected {required}")
    return {"status": "PASS", "checked_rows": checked, "invariant": 12}


def require_chain(
    level: str,
    *,
    planner_path: Path = DEFAULT_PLANNER,
    training_path: Path = DEFAULT_TRAINING,
    rehearsal_path: Path = DEFAULT_REHEARSAL,
    anchor_path: Path = DEFAULT_ANCHOR,
) -> dict[str, Any]:
    if level not in {"planner", "training", "rehearsal", "anchor"}:
        raise GateRejected(f"unknown chain level: {level!r}")
    result: dict[str, Any] = {"level": level, "planner": validate_planner_decision(planner_path)}
    if level in {"training", "rehearsal", "anchor"}:
        result["training"] = validate_training_gate(training_path, planner_path=planner_path)
    if level in {"rehearsal", "anchor"}:
        result["rehearsal"] = validate_rehearsal(
            rehearsal_path, planner_path=planner_path, training_path=training_path
        )
    if level == "anchor":
        result["anchor"] = validate_anchor(
            anchor_path,
            planner_path=planner_path,
            training_path=training_path,
            rehearsal_path=rehearsal_path,
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=("planner", "training", "rehearsal", "anchor"), required=True)
    parser.add_argument("--planner", type=Path, default=DEFAULT_PLANNER)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--rehearsal", type=Path, default=DEFAULT_REHEARSAL)
    parser.add_argument("--anchor", type=Path, default=DEFAULT_ANCHOR)
    args = parser.parse_args()
    try:
        result = require_chain(
            args.level,
            planner_path=args.planner,
            training_path=args.training,
            rehearsal_path=args.rehearsal,
            anchor_path=args.anchor,
        )
    except GateRejected as exc:
        parser.exit(2, f"REJECTED: {exc}\n")
    status = "PASS"
    if args.level == "training" and result.get("training", {}).get("status") == "NOT_RUN":
        status = "NOT_RUN"
    print(json.dumps({"schema": "a2_piper_pull_v5_5_gate_result_v1", "status": status, **result}, indent=2, sort_keys=True))
    return 3 if status == "NOT_RUN" else 0


if __name__ == "__main__":
    raise SystemExit(main())
