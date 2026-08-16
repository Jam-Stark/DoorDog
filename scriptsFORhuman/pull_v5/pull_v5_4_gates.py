#!/usr/bin/env python3
"""Fail-closed v5.4 admission gates.

The v5.3 H-D adjudication is an immutable source reference only.  It is
validated for identity and provenance, never imported as an admission verdict.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PLAN_ID = "a2_piper_pull_v5_4_terminal_yaw_scheduler"
DECISION_SCHEMA = "a2_piper_pull_v5_4_planner_architecture_decision_v1"
STAGE_A_SCHEMA = "a2_piper_pull_v5_4_stage_a_feasibility_v1"
REHEARSAL_SCHEMA = "a2_piper_pull_v5_4_stage_b_rehearsal_v1"
ANCHOR_SCHEMA = "a2_piper_pull_v5_4_p1_receipt_v1"
SCHEDULER_DERIVED_SCHEMA = "a2_piper_pull_v5_4_scheduler_derived_v1"
GATE_SCHEMA = "a2_piper_pull_v5_4_gate_receipt_v1"
V5_3_ADJUDICATION_SCHEMA = "a2_piper_pull_v5_3_p0_adjudication_v1"
V5_3_ADJUDICATION_REL = Path("logs_eval/a2_piper_pull_v5/v5_3_p0_adjudication.json")
DEFAULT_DECISION = ROOT / "logs_eval/a2_piper_pull_v5/v5_4_planner_architecture_decision.json"
DEFAULT_STAGE_A = ROOT / "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json"
DEFAULT_REHEARSAL = ROOT / "logs_eval/a2_piper_pull_v5/v5_4_stage_b_rehearsal/REHEARSAL_RECEIPT.json"


class GateRejected(RuntimeError):
    """Raised when a v5.4 prerequisite is absent, malformed, or failed."""


def _read(path: Path, label: str) -> Mapping[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file() or path.is_symlink():
        raise GateRejected(f"{label} is missing or not a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateRejected(f"{label} cannot be read as JSON: {path}") from exc
    if not isinstance(value, Mapping):
        raise GateRejected(f"{label} must be a JSON object: {path}")
    return value


def _path_from_repo(raw: object, label: str) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise GateRejected(f"{label} must be a repository-relative path; got {raw!r}")
    path = (ROOT / raw).resolve()
    if not path.is_relative_to(ROOT):
        raise GateRejected(f"{label} escapes repository: {raw!r}")
    return path


def _require(value: Mapping[str, Any], key: str, expected: object, label: str) -> None:
    actual = value.get(key)
    if actual != expected:
        raise GateRejected(f"{label}.{key} must equal {expected!r}; got {actual!r}")


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise GateRejected(f"{label} must be finite numeric; got {value!r}")
    return float(value)


def _diagnostic_denominator(value: Mapping[str, Any], label: str) -> None:
    if value.get("scientific_denominator_included") is not False:
        raise GateRejected(f"{label} must set scientific_denominator_included=false")
    if value.get("denominator_scope") not in ("none", None):
        raise GateRejected(f"{label} must set denominator_scope=none")


def validate_decision(path: Path = DEFAULT_DECISION) -> dict[str, Any]:
    decision = _read(path, "v5.4 planner decision")
    _require(decision, "schema", DECISION_SCHEMA, "planner decision")
    _require(decision, "plan_id", PLAN_ID, "planner decision")
    _require(decision, "decision", "MODEL_BASED_SCHEDULER_FIRST", "planner decision")
    _require(decision, "residual_precommitted", True, "planner decision")
    _require(decision, "fine_tune_deferred", True, "planner decision")
    _require(decision, "scientific_denominator_included", False, "planner decision")
    adjudication_rel = decision.get("v5_3_adjudication_path")
    if adjudication_rel != str(V5_3_ADJUDICATION_REL):
        raise GateRejected(
            "planner decision must reference the immutable v5.3 adjudication path; "
            f"got {adjudication_rel!r}"
        )
    adjudication_path = _path_from_repo(adjudication_rel, "immutable v5.3 adjudication path")
    adjudication = _read(adjudication_path, "immutable v5.3 adjudication")
    _require(adjudication, "schema", V5_3_ADJUDICATION_SCHEMA, "immutable v5.3 adjudication")
    _require(adjudication, "hypothesis", "H-D", "immutable v5.3 adjudication")
    _require(adjudication, "downstream_admitted", False, "immutable v5.3 adjudication")
    # The v5.3 record is deliberately not copied into this result as a verdict.
    return {
        "path": str(path.expanduser().resolve()),
        "schema": decision["schema"],
        "plan_id": decision["plan_id"],
        "decision": decision["decision"],
        "immutable_v5_3_reference": str(adjudication_path),
    }


def validate_stage_a(path: Path = DEFAULT_STAGE_A, *, decision_path: Path = DEFAULT_DECISION) -> dict[str, Any]:
    decision = validate_decision(decision_path)
    stage_a = _read(path, "v5.4 Stage-A receipt")
    _require(stage_a, "schema", STAGE_A_SCHEMA, "Stage-A receipt")
    _require(stage_a, "plan_id", PLAN_ID, "Stage-A receipt")
    _require(stage_a, "stage", "A", "Stage-A receipt")
    _require(stage_a, "record_class", "interface_characterization_stage_a", "Stage-A receipt")
    _require(stage_a, "scientific_denominator_included", False, "Stage-A receipt")
    if stage_a.get("verdict") != "GO":
        raise GateRejected(f"Stage-A verdict is not GO: {stage_a.get('verdict')!r}")
    next_gate = stage_a.get("next_gate")
    if not isinstance(next_gate, Mapping) or next_gate.get("stage_b_rehearsal") != "PERMITTED":
        raise GateRejected("Stage-A receipt does not permit Stage-B rehearsal")
    references = stage_a.get("references")
    if not isinstance(references, Mapping):
        raise GateRejected("Stage-A receipt is missing immutable references")
    planner_ref = references.get("planner_decision_artifact")
    if not isinstance(planner_ref, Mapping) or planner_ref.get("path") != str(Path(decision["path"]).relative_to(ROOT)):
        raise GateRejected("Stage-A planner reference does not match the admitted decision artifact")
    if planner_ref.get("immutable") is not True or planner_ref.get("decision") != decision["decision"]:
        raise GateRejected("Stage-A planner reference is not immutable or mismatched")
    adjudication_ref = references.get("v5_3_adjudication")
    if not isinstance(adjudication_ref, Mapping) or adjudication_ref.get("path") != str(V5_3_ADJUDICATION_REL):
        raise GateRejected("Stage-A v5.3 path reference is mismatched")
    scheduler = stage_a.get("scheduler_derived")
    if not isinstance(scheduler, Mapping) or scheduler.get("schema") != SCHEDULER_DERIVED_SCHEMA:
        raise GateRejected("Stage-A receipt is missing the frozen scheduler-derived block")
    if scheduler.get("frozen") is not True:
        raise GateRejected("Stage-A scheduler-derived block must be frozen")
    constants = scheduler.get("constants")
    if not isinstance(constants, Mapping):
        raise GateRejected("Stage-A scheduler-derived block is missing constants")
    required_constants = {
        "dt_s", "planning_a_rad", "b_trim_rad", "coarse_raw_negative", "coarse_raw_positive",
        "coarse_rate_negative_rad_s", "coarse_rate_positive_rad_s",
        "coarse_stop_drift_negative_rad", "coarse_stop_drift_positive_rad",
        "minimum_settle_steps_negative", "minimum_settle_steps_positive",
        "settle_deadline_steps", "settle_velocity_threshold_rad_s",
        "coarse_cutoff_negative_e_rad", "coarse_cutoff_positive_e_rad",
        "trim_raw", "trim_realized_rate_rad_s", "trim_one_step_rad", "trim_stop_drift_rad",
        "trim_step_cap", "terminal_hold_steps",
    }
    if set(constants) != required_constants:
        raise GateRejected(
            "Stage-A scheduler-derived constants mismatch: "
            f"missing={sorted(required_constants - set(constants))}, "
            f"extra={sorted(set(constants) - required_constants)}"
        )
    for name, entry in constants.items():
        if not isinstance(entry, Mapping):
            raise GateRejected(f"Stage-A scheduler constant {name} must be an object")
        _finite(entry.get("value"), f"scheduler_derived.constants.{name}.value")
        if not isinstance(entry.get("source_jsonpath"), str) or not entry["source_jsonpath"].startswith("$"):
            raise GateRejected(f"Stage-A scheduler constant {name} lacks a JSONPath provenance")
        if not isinstance(entry.get("derivation"), str) or not entry["derivation"]:
            raise GateRejected(f"Stage-A scheduler constant {name} lacks deterministic derivation")
    return {
        "path": str(path.expanduser().resolve()),
        "schema": stage_a["schema"],
        "plan_id": stage_a["plan_id"],
        "verdict": stage_a["verdict"],
        "decision": decision,
        "scheduler_derived": scheduler,
    }


def _terminal_row(row: object, label: str) -> tuple[int, float, bool]:
    if not isinstance(row, Mapping):
        raise GateRejected(f"{label} must be an object")
    if row.get("record_class") != "interface_characterization":
        raise GateRejected(f"{label} must be interface_characterization")
    _diagnostic_denominator(row, label)
    env_id = row.get("env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0:
        raise GateRejected(f"{label}.env_id must be a non-negative int")
    terminal_after_step = row.get("terminal_after_step")
    if not isinstance(terminal_after_step, bool):
        raise GateRejected(f"{label}.terminal_after_step must be actual returned-dones bool")
    if row.get("episode_index") != 0:
        raise GateRejected(f"{label}.episode_index must be first episode 0")
    env_id = int(env_id)
    if row.get("episode_id") != f"rehearsal:env{env_id}:episode0":
        raise GateRejected(f"{label}.episode_id does not identify first episode")
    if row.get("scheduler_state") != "DONE":
        raise GateRejected(f"{label}.scheduler_state must be DONE")
    if row.get("terminal_current_state") is not True:
        raise GateRejected(f"{label}.terminal_current_state must be true")
    if row.get("terminal_hold_steps") != 100:
        raise GateRejected(f"{label}.terminal_hold_steps must equal 100")
    error = row.get("terminal_error_original_target_rad")
    if error is None:
        raise GateRejected(f"{label} is missing original-target terminal error")
    return env_id, abs(_finite(error, f"{label}.terminal_error_rad")), terminal_after_step


def _attempt_rows(attempt: Mapping[str, Any], label: str) -> list[Mapping[str, Any]]:
    rows = attempt.get("terminal_rows", attempt.get("rows"))
    if not isinstance(rows, list) or len(rows) != 8:
        raise GateRejected(f"{label} must contain exactly 8 terminal rows")
    seen: set[int] = set()
    normalized: list[Mapping[str, Any]] = []
    for index, row in enumerate(rows):
        env_id, _error, terminal = _terminal_row(row, f"{label}.rows[{index}]")
        if env_id in seen or not terminal:
            raise GateRejected(f"{label} must have one terminal returned-dones row per env")
        seen.add(env_id)
        normalized.append(row)
    if seen != set(range(8)):
        raise GateRejected(f"{label} env ids must be exactly 0..7; got {sorted(seen)}")
    return normalized


def validate_rehearsal(
    path: Path = DEFAULT_REHEARSAL,
    *,
    stage_a_path: Path = DEFAULT_STAGE_A,
    decision_path: Path = DEFAULT_DECISION,
) -> dict[str, Any]:
    validate_stage_a(stage_a_path, decision_path=decision_path)
    rehearsal = _read(path, "v5.4 Stage-B rehearsal receipt")
    _require(rehearsal, "schema", REHEARSAL_SCHEMA, "rehearsal receipt")
    _require(rehearsal, "plan_id", PLAN_ID, "rehearsal receipt")
    _require(rehearsal, "record_class", "interface_characterization", "rehearsal receipt")
    _diagnostic_denominator(rehearsal, "rehearsal receipt")
    _require(rehearsal, "num_envs", 8, "rehearsal receipt")
    _require(rehearsal, "gpu", 4, "rehearsal receipt")
    cells = rehearsal.get("cells")
    if not isinstance(cells, list) or len(cells) != 2:
        raise GateRejected("rehearsal receipt must contain exactly two target cells")
    expected_targets = {-2.5, 1.0}
    seen_targets: set[float] = set()
    attempt1_rows: list[Mapping[str, Any]] = []
    cell_summaries: list[dict[str, Any]] = []
    for cell_index, cell in enumerate(cells):
        if not isinstance(cell, Mapping):
            raise GateRejected(f"rehearsal cell {cell_index} must be an object")
        target = _finite(cell.get("original_target_yaw_delta_rad"), f"cells[{cell_index}].original_target_yaw_delta_rad")
        if target not in expected_targets or target in seen_targets:
            raise GateRejected(f"rehearsal targets must be exactly -2.5 and +1.0; got {target!r}")
        seen_targets.add(target)
        attempts = cell.get("attempts")
        if not isinstance(attempts, list) or not attempts or len(attempts) > 2:
            raise GateRejected("each rehearsal cell permits attempt revision 0 and optional 1 only")
        revisions = [item.get("attempt") for item in attempts if isinstance(item, Mapping)]
        if revisions != list(range(len(attempts))) or any(rev not in (0, 1) for rev in revisions):
            raise GateRejected("rehearsal attempt revisions must be contiguous 0/1")
        final_attempt = attempts[-1]
        if not isinstance(final_attempt, Mapping):
            raise GateRejected("rehearsal final attempt must be an object")
        rows = _attempt_rows(final_attempt, f"cells[{cell_index}].attempt{len(attempts)-1}")
        errors = [_terminal_row(row, f"cells[{cell_index}].final_row")[1] for row in rows]
        if max(errors) > 0.15 or sum(errors) / len(errors) > 0.10:
            raise GateRejected(
                f"rehearsal target {target} fails terminal yaw criteria: max={max(errors)}, mean={sum(errors)/len(errors)}"
            )
        if len(attempts) == 2:
            attempt1_rows.extend(_attempt_rows(attempts[1], f"cells[{cell_index}].attempt1"))
        cell_summaries.append(
            {
                "target": target,
                "attempt": int(final_attempt["attempt"]),
                "terminal_count": len(rows),
                "max_abs_original_target_error_rad": max(errors),
                "mean_abs_original_target_error_rad": sum(errors) / len(errors),
            }
        )
    if seen_targets != expected_targets:
        raise GateRejected("rehearsal cells do not cover both -2.5 and +1.0 targets")
    correction = rehearsal.get("correction_revision")
    if attempt1_rows:
        if not isinstance(correction, Mapping) or correction.get("revision") != 1 or correction.get("source_revision") != 0:
            raise GateRejected("attempt-1 rehearsal rows require one shared correction revision=1")
        if correction.get("source_attempt") != 0 or correction.get("source_row_count") != 16:
            raise GateRejected("rehearsal correction must attest all 16 revision-0 rows")
        source_rows: list[Mapping[str, Any]] = []
        for cell in cells:
            attempts = cell["attempts"]
            source_rows.extend(_attempt_rows(attempts[0], "revision-0 source"))
        signed = [_finite(row.get("terminal_error_original_target_rad"), "revision-0 signed error") for row in source_rows]
        expected_median = sorted(signed)[len(signed) // 2] if len(signed) % 2 else (sorted(signed)[len(signed)//2 - 1] + sorted(signed)[len(signed)//2]) / 2.0
        applied_median = _finite(
            correction.get("shared_median_signed_original_target_error_rad"),
            "correction revision-0 median",
        )
        if not math.isclose(applied_median, expected_median, rel_tol=0.0, abs_tol=1.0e-9):
            raise GateRejected("rehearsal correction is not the shared revision-0 original-target median")
        if not math.isclose(
            _finite(correction.get("shared_median_signed_terminal_error_rad"), "correction median"),
            applied_median,
            rel_tol=0.0,
            abs_tol=1.0e-9,
        ):
            raise GateRejected("rehearsal correction receipt does not attest the applied revision-0 scalar")
        if correction.get("applied_to_planning_target") is not True:
            raise GateRejected("rehearsal correction must attest application to the planning target")
    if rehearsal.get("status") != "PASS":
        raise GateRejected(f"rehearsal status is not PASS: {rehearsal.get('status')!r}")
    return {
        "path": str(path.expanduser().resolve()),
        "schema": rehearsal["schema"],
        "status": rehearsal["status"],
        "cells": cell_summaries,
    }


def _anchor_probe(row: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    probe = row.get("pull_v5_probe", row)
    if not isinstance(probe, Mapping):
        raise GateRejected(f"{label} is missing pull_v5_probe telemetry")
    scheduler = probe.get("scheduler")
    scheduler_terminal = scheduler.get("terminal_current_state") if isinstance(scheduler, Mapping) else None
    if probe.get("terminal_current_state") is not True and scheduler_terminal is not True:
        raise GateRejected(f"{label} is not terminal current-state telemetry")
    if isinstance(scheduler, Mapping) and scheduler.get("state") != "DONE":
        raise GateRejected(f"{label} scheduler state is not DONE: {scheduler.get('state')!r}")
    if probe.get("waypoint_arrived") is not True or probe.get("yaw_arrived") is not True:
        raise GateRejected(f"{label} does not satisfy waypoint+yaw terminal acceptance")
    return probe


def validate_anchor(
    path: Path,
    *,
    rehearsal_path: Path = DEFAULT_REHEARSAL,
    stage_a_path: Path = DEFAULT_STAGE_A,
    decision_path: Path = DEFAULT_DECISION,
) -> dict[str, Any]:
    validate_rehearsal(rehearsal_path, stage_a_path=stage_a_path, decision_path=decision_path)
    anchor = _read(path, "v5.4 anchor receipt")
    _require(anchor, "schema", ANCHOR_SCHEMA, "anchor receipt")
    _require(anchor, "plan_id", PLAN_ID, "anchor receipt")
    _require(anchor, "fixture", "anchor", "anchor receipt")
    _require(anchor, "status", "PASS", "anchor receipt")
    _diagnostic_denominator(anchor, "anchor receipt")
    sequences = anchor.get("sequence_ids")
    if not isinstance(sequences, list) or not sequences or any(item not in {"S1", "S2", "S3", "S4"} for item in sequences):
        raise GateRejected("anchor receipt must identify a non-empty S1..S4 subset")
    if len(set(sequences)) != len(sequences):
        raise GateRejected("anchor sequence subset contains duplicates")
    anchored = anchor.get("anchored_sequences", sequences)
    if (
        not isinstance(anchored, list)
        or not anchored
        or any(item not in sequences for item in anchored)
        or len(set(anchored)) != len(anchored)
    ):
        raise GateRejected("anchor admitted subset must be a non-empty subset of sequence_ids")
    counts = anchor.get("sequence_counts")
    if not isinstance(counts, Mapping):
        raise GateRejected("anchor receipt is missing sequence_counts")
    if any(counts.get(sequence) != 16 for sequence in sequences):
        raise GateRejected("anchor sequence_counts must report exactly 16 rows for every requested sequence")
    rows = anchor.get("terminal_records")
    if isinstance(rows, Mapping):
        rows = rows.get("rows")
    if not isinstance(rows, list) or len(rows) != 16 * len(sequences):
        raise GateRejected("anchor receipt must contain exactly 16 terminal-current-state rows per admitted sequence")
    by_sequence: dict[str, int] = {sequence: 0 for sequence in sequences}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise GateRejected(f"anchor terminal row {index} must be an object")
        sequence = row.get("sequence")
        if sequence is None and isinstance(row.get("pull_v5_probe"), Mapping):
            sequence = row["pull_v5_probe"].get("sequence")
        if sequence not in by_sequence:
            raise GateRejected(f"anchor row {index} has non-admitted sequence {sequence!r}")
        if sequence in anchored:
            _anchor_probe(row, f"anchor terminal row {index}")
        by_sequence[str(sequence)] += 1
    if any(value != 16 for value in by_sequence.values()):
        raise GateRejected(f"anchor admitted subset must be 16/16 per sequence: {by_sequence}")
    sequence_results = anchor.get("sequence_results")
    if not isinstance(sequence_results, Mapping):
        raise GateRejected("anchor receipt is missing sequence_results")
    for sequence in anchored:
        result = sequence_results.get(sequence)
        if not isinstance(result, Mapping) or result.get("sequence_pass") is not True:
            raise GateRejected(f"anchor sequence {sequence} is not admitted")
        if result.get("terminal_records") != 16 or result.get("waypoint_arrived") != 16 or result.get("yaw_arrived") != 16:
            raise GateRejected(f"anchor sequence {sequence} counts are not 16/16")
    return {
        "path": str(path.expanduser().resolve()),
        "schema": anchor["schema"],
        "status": "PASS",
        "admitted_sequences": list(anchored),
        "sequence_counts": by_sequence,
    }


def validate_downstream_gate(
    path: Path,
    *,
    anchor_path: Path,
) -> dict[str, Any]:
    """Validate the current G1/G2 receipt and every bound producer path."""

    gate = _read(path, "v5.4 downstream gate receipt")
    _require(gate, "schema", GATE_SCHEMA, "downstream gate")
    _require(gate, "plan_id", PLAN_ID, "downstream gate")
    _diagnostic_denominator(gate, "downstream gate")
    if gate.get("status") not in {"G1_PASS", "G2_PASS"}:
        raise GateRejected(f"downstream gate status is not passage-positive: {gate.get('status')!r}")
    anchor_resolved = str(anchor_path.expanduser().resolve())
    if gate.get("anchor_receipt_path") != anchor_resolved:
        raise GateRejected("downstream gate does not bind the current anchor receipt")
    anchor_receipt = _read(anchor_path, "current anchor receipt")
    _require(anchor_receipt, "schema", ANCHOR_SCHEMA, "current anchor receipt")
    _require(anchor_receipt, "plan_id", PLAN_ID, "current anchor receipt")
    _require(anchor_receipt, "status", "PASS", "current anchor receipt")
    attempt = gate.get("p1_attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt not in (1, 2, 3):
        raise GateRejected("downstream gate p1_attempt must be 1, 2, or 3")
    if anchor_receipt.get("anchor_attempt") != attempt:
        raise GateRejected("downstream gate attempt does not match current anchor receipt")
    probe_paths = gate.get("probe_receipt_paths")
    if not isinstance(probe_paths, list) or len(probe_paths) != 3:
        raise GateRejected("downstream gate must bind exactly three current door-probe receipts")
    for raw_path in probe_paths:
        probe_path = Path(raw_path).expanduser().resolve() if isinstance(raw_path, str) else None
        if probe_path is None:
            raise GateRejected("downstream gate probe receipt path must be a string")
        probe = _read(probe_path, "current door-probe receipt")
        _require(probe, "schema", ANCHOR_SCHEMA, "current door-probe receipt")
        _require(probe, "plan_id", PLAN_ID, "current door-probe receipt")
        if probe.get("anchor_receipt_path") != anchor_resolved or probe.get("anchor_attempt") != attempt:
            raise GateRejected("door-probe receipt is stale or bound to a different anchor")
    if gate.get("status") == "G2_PASS":
        lattice_path_raw = gate.get("lattice_receipt_path")
        if not isinstance(lattice_path_raw, str) or not lattice_path_raw:
            raise GateRejected("G2 gate must bind a lattice receipt path")
        lattice = _read(Path(lattice_path_raw), "current lattice receipt")
        _require(lattice, "schema", ANCHOR_SCHEMA, "current lattice receipt")
        _require(lattice, "plan_id", PLAN_ID, "current lattice receipt")
        if lattice.get("anchor_receipt_path") != anchor_resolved or lattice.get("anchor_attempt") != attempt:
            raise GateRejected("lattice receipt is stale or bound to a different anchor")
    return {
        "path": str(path.expanduser().resolve()),
        "schema": gate["schema"],
        "status": gate["status"],
        "anchor_receipt_path": anchor_resolved,
        "probe_receipt_paths": list(probe_paths),
        "p1_attempt": attempt,
    }


# Stable descriptive aliases used by the orchestration scripts and by small
# external admission checks.  They intentionally remain thin wrappers so all
# validation follows the same fail-closed path above.
def require_v5_4_decision(path: Path = DEFAULT_DECISION) -> dict[str, Any]:
    return validate_decision(path)


def require_v5_4_stage_a(path: Path = DEFAULT_STAGE_A, *, decision_path: Path = DEFAULT_DECISION) -> dict[str, Any]:
    return validate_stage_a(path, decision_path=decision_path)


def require_v5_4_rehearsal(
    path: Path = DEFAULT_REHEARSAL,
    *,
    stage_a_path: Path = DEFAULT_STAGE_A,
    decision_path: Path = DEFAULT_DECISION,
) -> dict[str, Any]:
    return validate_rehearsal(path, stage_a_path=stage_a_path, decision_path=decision_path)


def require_v5_4_anchor(
    path: Path,
    *,
    rehearsal_path: Path = DEFAULT_REHEARSAL,
    stage_a_path: Path = DEFAULT_STAGE_A,
    decision_path: Path = DEFAULT_DECISION,
) -> dict[str, Any]:
    return validate_anchor(
        path,
        rehearsal_path=rehearsal_path,
        stage_a_path=stage_a_path,
        decision_path=decision_path,
    )


def require_v5_4_downstream_gate(path: Path, *, anchor_path: Path) -> dict[str, Any]:
    return validate_downstream_gate(path, anchor_path=anchor_path)


def require_chain(
    level: str,
    *,
    decision_path: Path = DEFAULT_DECISION,
    stage_a_path: Path = DEFAULT_STAGE_A,
    rehearsal_path: Path = DEFAULT_REHEARSAL,
    anchor_path: Path | None = None,
) -> dict[str, Any]:
    if level not in {"decision", "stage_a", "rehearsal", "anchor"}:
        raise GateRejected(f"unknown v5.4 gate level: {level!r}")
    result: dict[str, Any] = {"level": level, "decision": validate_decision(decision_path)}
    if level in {"stage_a", "rehearsal", "anchor"}:
        result["stage_a"] = validate_stage_a(stage_a_path, decision_path=decision_path)
    if level in {"rehearsal", "anchor"}:
        result["rehearsal"] = validate_rehearsal(
            rehearsal_path, stage_a_path=stage_a_path, decision_path=decision_path
        )
    if level == "anchor":
        if anchor_path is None:
            raise GateRejected("anchor gate requires --anchor")
        result["anchor"] = validate_anchor(
            anchor_path,
            rehearsal_path=rehearsal_path,
            stage_a_path=stage_a_path,
            decision_path=decision_path,
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=("decision", "stage_a", "rehearsal", "anchor"), required=True)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--stage-a", type=Path, default=DEFAULT_STAGE_A)
    parser.add_argument("--rehearsal", type=Path, default=DEFAULT_REHEARSAL)
    parser.add_argument("--anchor", type=Path)
    args = parser.parse_args()
    try:
        result = require_chain(
            args.level,
            decision_path=args.decision,
            stage_a_path=args.stage_a,
            rehearsal_path=args.rehearsal,
            anchor_path=args.anchor,
        )
    except GateRejected as exc:
        parser.exit(2, f"REJECTED: {exc}\n")
    print(json.dumps({"schema": "a2_piper_pull_v5_4_gate_result_v1", "status": "PASS", **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
