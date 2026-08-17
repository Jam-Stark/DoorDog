#!/usr/bin/env python3
"""Fail-closed gates for the v5.6 terminal hold specialist ladder."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PLAN_ID = "a2_piper_pull_v5_6_terminal_hold_specialist_finetune"
PLANNER_SCHEMA = "a2_piper_pull_v5_6_planner_architecture_decision_v1"
WARM_START_SCHEMA = "a2_piper_pull_v5_6_specialist_warm_start_v1"
STEP0_SCHEMA = "a2_piper_pull_v5_6_specialist_step0_gate_v1"
TRAINING_SCHEMA = "a2_piper_pull_v5_6_specialist_training_gate_v1"
REHEARSAL_SCHEMA = "a2_piper_pull_v5_6_specialist_rehearsal_v1"
ANCHOR_SCHEMA = "a2_piper_pull_v5_6_specialist_anchor_v1"
TRACE_SCHEMA = "a2_piper_pull_v5_6_specialist_trace_v1"

DEFAULT_PLANNER = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_planner_architecture_decision.json"
DEFAULT_WARM_START = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_specialist_t0/WARM_START.json"
DEFAULT_STEP0 = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_specialist_gate_step0/STEP0_GATE.json"
DEFAULT_TRAINING = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_specialist_gate/TRAINING_GATE.json"
DEFAULT_REHEARSAL = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_specialist_rehearsal/REHEARSAL.json"
DEFAULT_ANCHOR = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_specialist_anchor/ANCHOR.json"

PRELUDE_FAMILIES = (
    "near_rest",
    "coarse_neg",
    "coarse_pos",
    "straight_minus_x",
    "side_step",
)
SEQUENCES = ("S1", "S2", "S3", "S4")
SPECIALIST_PHASES = {"holdtrack", "terminal_hold", "anchor", "door_positioning"}
FORBIDDEN_SPECIALIST_PHASES = {
    "P3", "P4", "DV", "canonical_DV", "natural_DV",
    "p3", "p4", "dv", "canonical_dv", "natural_dv",
}
CHARACTERIZATION_PHASES = {"step0", "training_gate", "rehearsal", "anchor"}
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
        raise GateRejected(f"{label}.schema is not the v5.6 trace schema")
    if row.get("plan_id") not in (None, PLAN_ID):
        raise GateRejected(f"{label}.plan_id is not bound to the v5.6 plan")


def _specialist_row(
    row: object,
    label: str,
    *,
    expected_episode_prefix: str | None = None,
    specialist_active: bool = True,
) -> Mapping[str, Any]:
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
    if row.get("hold_specialist_active") is not specialist_active:
        raise GateRejected(f"{label}.hold_specialist_active must be {specialist_active}")
    if specialist_active:
        checkpoint = row.get("specialist_checkpoint")
        step = row.get("specialist_checkpoint_step")
        if not isinstance(checkpoint, str) or not checkpoint:
            raise GateRejected(f"{label} must record the specialist checkpoint path")
        if isinstance(step, bool) or not isinstance(step, int) or step < 0:
            raise GateRejected(f"{label} must record a non-negative specialist checkpoint step")
    else:
        if row.get("specialist_checkpoint") not in (None, ""):
            raise GateRejected(f"{label} must not claim a specialist checkpoint in baseline mode")
        if row.get("specialist_checkpoint_step") not in (None, ""):
            raise GateRejected(f"{label} must not claim a specialist checkpoint step in baseline mode")
    if not isinstance(row.get("original_homie_checkpoint"), str) or not row["original_homie_checkpoint"]:
        raise GateRejected(f"{label} must record the immutable original HOMIE checkpoint")
    _finite(row.get("xy_error_m"), f"{label}.xy_error_m")
    _finite(row.get("yaw_error_rad"), f"{label}.yaw_error_rad")
    if float(row["xy_error_m"]) > WAYPOINT_TOLERANCE_M:
        raise GateRejected(f"{label} exceeds 0.05 m waypoint tolerance")
    if abs(float(row["yaw_error_rad"])) > YAW_TOLERANCE_RAD:
        raise GateRejected(f"{label} exceeds 0.15 rad yaw tolerance")
    return row


def _row_phase(row: Mapping[str, Any]) -> str:
    provenance = row.get("adapter_provenance")
    nested = provenance if isinstance(provenance, Mapping) else {}
    value = row.get("phase", row.get("specialist_phase", nested.get("phase", nested.get("specialist_phase", ""))))
    return str(value)


def _require_invariant_receipt(
    receipt: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    phase: str,
) -> dict[str, Any]:
    declared = receipt.get("invariant12_prime")
    if not isinstance(declared, Mapping) or declared.get("status") != "PASS":
        raise GateRejected(f"{phase} receipt must declare invariant12_prime PASS")
    result = validate_invariant12_prime(rows, expected_rows=len(rows), receipt=receipt)
    if declared.get("checked_rows") != result["checked_rows"]:
        raise GateRejected(f"{phase} invariant12_prime checked_rows is stale")
    return result


def validate_planner_decision(path: Path = DEFAULT_PLANNER) -> dict[str, Any]:
    decision = _read(path, "v5.6 planner decision")
    if decision.get("schema") != PLANNER_SCHEMA or decision.get("plan_id") != PLAN_ID:
        raise GateRejected("planner decision schema/plan_id mismatch")
    if decision.get("decision") != "ACTIVATE_TERMINAL_HOLD_SPECIALIST_FINETUNE":
        raise GateRejected("planner decision does not activate the terminal specialist rung")
    if decision.get("rung") != 3 or decision.get("ladder_final_rung") is not True:
        raise GateRejected("planner decision must identify the final rung 3")
    if decision.get("original_homie_immutable") is not True:
        raise GateRejected("planner decision must keep original HOMIE immutable")
    if decision.get("fine_tune_deferred") is not False:
        raise GateRejected("planner decision must record HOMIE fine-tune as deferred=false")
    if decision.get("scientific_denominator_included") is not False or decision.get("denominator_scope") != "none":
        raise GateRejected("planner decision must remain diagnostic-only")
    if decision.get("status") != "PLANNER_ACCEPTED":
        raise GateRejected("planner decision is not PLANNER_ACCEPTED")
    if decision.get("v5_5_reference") in (None, ""):
        raise GateRejected("planner decision must reference the immutable v5.5 baseline")
    if decision.get("v5_5_round_report") in (None, ""):
        raise GateRejected("planner decision must reference the immutable v5.5 round report")
    return dict(decision)


def validate_warm_start(path: Path = DEFAULT_WARM_START, *, planner_path: Path = DEFAULT_PLANNER) -> dict[str, Any]:
    validate_planner_decision(planner_path)
    receipt = _read(path, "v5.6 warm-start receipt")
    if receipt.get("schema") != WARM_START_SCHEMA or receipt.get("plan_id") != PLAN_ID:
        raise GateRejected("warm-start schema/plan_id mismatch")
    if receipt.get("status") != "PASS":
        raise GateRejected(f"warm-start status is not PASS: {receipt.get('status')!r}")
    checkpoint_path = receipt.get("checkpoint_path")
    if not isinstance(checkpoint_path, str) or not checkpoint_path:
        raise GateRejected("warm-start must record the versioned checkpoint path")
    checkpoint_ref = Path(checkpoint_path).expanduser()
    if checkpoint_ref.is_symlink() or not checkpoint_ref.is_file():
        raise GateRejected(f"warm-start versioned checkpoint is missing or not a regular file: {checkpoint_ref}")
    checkpoint_file = checkpoint_ref.resolve()
    if checkpoint_file.name != "model_step_000000.pt":
        raise GateRejected(f"warm-start versioned checkpoint is missing or misnamed: {checkpoint_file}")
    checkpoint_format = receipt.get("checkpoint_format")
    if not isinstance(checkpoint_format, Mapping):
        raise GateRejected("warm-start must record checkpoint-format evidence")
    if checkpoint_format.get("optimizer_state_dict") is not None or checkpoint_format.get("lr_scheduler_state_dict") is not None:
        raise GateRejected("warm-start must not carry optimizer or scheduler state")
    if checkpoint_format.get("state_global_step") != 0:
        raise GateRejected("warm-start checkpoint must be step 0")
    roundtrip = receipt.get("roundtrip")
    if not isinstance(roundtrip, Mapping) or roundtrip.get("actor_state_dict_strict") is not True or roundtrip.get("critic_state_dict_strict") is not True:
        raise GateRejected("warm-start must record strict actor/critic roundtrip evidence")
    if receipt.get("actor_loaded_from_raw_checkpoint") is not True:
        raise GateRejected("warm-start actor must load from raw dog checkpoint")
    if receipt.get("critic_init") != "fresh_incompatible_privileged_25d_semantics":
        raise GateRejected("warm-start critic must be fresh")
    if receipt.get("optimizer_init") != "fresh" or receipt.get("scheduler_init") != "fresh":
        raise GateRejected("warm-start optimizer and scheduler must be fresh")
    if _finite(receipt.get("resolved_std"), "warm-start resolved_std") != 1.0:
        raise GateRejected("warm-start std must be reset to original dog fresh 1.0")
    architecture = receipt.get("architecture")
    if not isinstance(architecture, Mapping) or architecture.get("obs_dim") != 1620 or architecture.get("latent_dim") != 25 or architecture.get("action_dim") != 12:
        raise GateRejected("warm-start architecture dimensions are not 1620->256->128->25 and 12-D")
    if not isinstance(receipt.get("raw_checkpoint"), str) or not receipt["raw_checkpoint"]:
        raise GateRejected("warm-start must record raw checkpoint source")
    return dict(receipt)


def validate_step0(path: Path = DEFAULT_STEP0, *, planner_path: Path = DEFAULT_PLANNER, warm_start_path: Path = DEFAULT_WARM_START) -> dict[str, Any]:
    validate_warm_start(warm_start_path, planner_path=planner_path)
    receipt = _read(path, "v5.6 step0 gate receipt")
    if receipt.get("schema") != STEP0_SCHEMA or receipt.get("plan_id") != PLAN_ID:
        raise GateRejected("step0 schema/plan_id mismatch")
    status = receipt.get("status")
    if status == "NOT_RUN":
        return {"status": "NOT_RUN", "path": str(path.expanduser().resolve())}
    if status != "PASS":
        raise GateRejected(f"step0 status is not PASS: {status!r}")
    if receipt.get("specialist_active") is not False or receipt.get("mode") != "original_jit_gain1_carrier":
        raise GateRejected("step0 must characterize original JIT with specialist disabled")
    rows = receipt.get("rows")
    if not isinstance(rows, list) or len(rows) != 80:
        raise GateRejected("step0 must contain exactly 80 diagnostic rows")
    if receipt.get("hold_specialist_active") is not False:
        raise GateRejected("step0 top-level hold_specialist_active must be false")
    if receipt.get("training_gate_registered_full") is not True or receipt.get("full_source") is not True:
        raise GateRejected("step0 must characterize the registered full training distribution")
    row_counts = {family: 0 for family in PRELUDE_FAMILIES}
    done_counts = {family: 0 for family in PRELUDE_FAMILIES}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise GateRejected(f"step0 row {index} must be an object")
        _diagnostic(row, f"step0 row {index}")
        family = row.get("family")
        if family not in row_counts:
            raise GateRejected(f"step0 row {index} has unknown family {family!r}")
        if row.get("hold_specialist_active") is not False:
            raise GateRejected(f"step0 row {index} must disable specialist")
        if row.get("specialist_checkpoint") not in (None, "") or row.get("specialist_checkpoint_step") not in (None, ""):
            raise GateRejected(f"step0 row {index} must not claim specialist provenance")
        if row.get("adapter_target_source") != "training_gate_registered_full":
            raise GateRejected(f"step0 row {index} must use the registered full target source")
        if row.get("terminal_after_step") is not True or row.get("returned_dones_binding") != "env.step returned dones":
            raise GateRejected(f"step0 row {index} lacks returned-dones binding")
        if not isinstance(row.get("done"), bool) or not isinstance(row.get("terminal_current_state"), bool):
            raise GateRejected(f"step0 row {index} done/current fields must be bool")
        hold_steps = row.get("terminal_hold_steps")
        if isinstance(hold_steps, bool) or not isinstance(hold_steps, int) or hold_steps < 0 or hold_steps > TERMINAL_HOLD_STEPS:
            raise GateRejected(f"step0 row {index}.terminal_hold_steps must be in [0,100]")
        _finite(row.get("xy_error_m"), f"step0 row {index}.xy_error_m")
        _finite(row.get("yaw_error_rad"), f"step0 row {index}.yaw_error_rad")
        if not isinstance(row.get("original_homie_checkpoint"), str) or not row["original_homie_checkpoint"]:
            raise GateRejected(f"step0 row {index} must record original HOMIE provenance")
        row_counts[family] += 1
        done_counts[family] += int(row["done"])
    expected_counts = {family: 16 for family in PRELUDE_FAMILIES}
    if row_counts != expected_counts:
        raise GateRejected(f"step0 must have 16 rows per family: {row_counts}")
    if receipt.get("family_row_counts") != row_counts or receipt.get("family_done_counts") != done_counts:
        raise GateRejected("step0 family counts do not match rows")
    capability_count = receipt.get("capability_count")
    if isinstance(capability_count, bool) or not isinstance(capability_count, int) or capability_count != sum(done_counts.values()):
        raise GateRejected("step0 capability_count does not match diagnostic rows")
    _require_invariant_receipt(receipt, rows, phase="step0")
    return {
        "status": "PASS",
        "path": str(path.expanduser().resolve()),
        "rows": len(rows),
        "family_row_counts": row_counts,
        "family_done_counts": done_counts,
        "capability_count": capability_count,
    }


def training_gate_pass(counts: Mapping[str, int]) -> bool:
    if set(counts) != set(PRELUDE_FAMILIES):
        raise ValueError("training gate counts must cover exactly the five prelude families")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
        raise ValueError("training gate counts must be non-negative integers")
    return all(counts[family] >= 15 for family in PRELUDE_FAMILIES) and sum(counts.values()) >= 77


def _validate_training_matrix_entry(entry: Mapping[str, Any], label: str) -> dict[str, Any]:
    entry_status = entry.get("status")
    if entry_status not in {"PASS", "FAIL"}:
        raise GateRejected(f"{label}.status must be PASS or FAIL")
    checkpoint = entry.get("checkpoint", entry.get("specialist_checkpoint"))
    step = entry.get("checkpoint_step", entry.get("specialist_checkpoint_step"))
    if not isinstance(checkpoint, str) or not checkpoint:
        raise GateRejected(f"{label} must record checkpoint path")
    if isinstance(step, bool) or not isinstance(step, int) or step < 0:
        raise GateRejected(f"{label} must record non-negative checkpoint step")
    if entry.get("training_gate_registered_full") is not True or entry.get("full_source") is not True:
        raise GateRejected(f"{label} must attest the registered full target distribution")
    rows = entry.get("rows")
    if not isinstance(rows, list) or len(rows) != 80:
        raise GateRejected(f"{label} must contain exactly 80 held-out rows")
    row_counts = {family: 0 for family in PRELUDE_FAMILIES}
    done_counts = {family: 0 for family in PRELUDE_FAMILIES}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise GateRejected(f"{label} row {index} must be an object")
        _diagnostic(row, f"{label} row {index}")
        family = row.get("family")
        if family not in row_counts:
            raise GateRejected(f"{label} row {index} has unknown family {family!r}")
        if row.get("hold_specialist_active") is not True:
            raise GateRejected(f"{label} row {index} must attest specialist active")
        if row.get("specialist_checkpoint") != checkpoint or row.get("specialist_checkpoint_step") != step:
            raise GateRejected(f"{label} row {index} checkpoint provenance disagrees with matrix entry")
        if row.get("adapter_target_source") != "training_gate_registered_full":
            raise GateRejected(f"{label} row {index} must use the registered full target source")
        if row.get("terminal_after_step") is not True or row.get("returned_dones_binding") != "env.step returned dones":
            raise GateRejected(f"{label} row {index} lacks returned-dones binding")
        if not isinstance(row.get("done"), bool) or not isinstance(row.get("terminal_current_state"), bool):
            raise GateRejected(f"{label} row {index} done/current fields must be bool")
        _finite(row.get("xy_error_m"), f"{label} row {index}.xy_error_m")
        _finite(row.get("yaw_error_rad"), f"{label} row {index}.yaw_error_rad")
        row_counts[family] += 1
        done_counts[family] += int(row["done"])
    expected_counts = {family: 16 for family in PRELUDE_FAMILIES}
    if row_counts != expected_counts:
        raise GateRejected(f"{label} must have 16 rows per family: {row_counts}")
    if entry.get("family_row_counts") != row_counts or entry.get("family_done_counts") != done_counts:
        raise GateRejected(f"{label} family counts do not match rows")
    _require_invariant_receipt(entry, rows, phase="training_gate")
    return {
        "status": entry_status,
        "checkpoint": checkpoint,
        "checkpoint_step": step,
        "family_row_counts": row_counts,
        "family_done_counts": done_counts,
        "overall_done": sum(done_counts.values()),
        "rows": rows,
    }


def validate_training_gate(path: Path = DEFAULT_TRAINING, *, planner_path: Path = DEFAULT_PLANNER, warm_start_path: Path = DEFAULT_WARM_START) -> dict[str, Any]:
    validate_warm_start(warm_start_path, planner_path=planner_path)
    receipt = _read(path, "v5.6 training gate receipt")
    if receipt.get("schema") != TRAINING_SCHEMA or receipt.get("plan_id") != PLAN_ID:
        raise GateRejected("training gate schema/plan_id mismatch")
    status = receipt.get("status")
    if status == "NOT_RUN":
        return {"status": "NOT_RUN", "path": str(path.expanduser().resolve())}
    if status == "CRASH":
        raise GateRejected("training gate recorded a crash")
    if status != "PASS":
        raise GateRejected(f"training gate status is not PASS: {status!r}")
    matrix = receipt.get("checkpoints", receipt.get("checkpoint_matrix"))
    if not isinstance(matrix, list) or not matrix:
        matrix = [receipt]
    validated = [_validate_training_matrix_entry(entry, f"training checkpoint matrix entry {index}") for index, entry in enumerate(matrix) if isinstance(entry, Mapping)]
    if len(validated) != len(matrix):
        raise GateRejected("training checkpoint matrix entries must be objects")
    selected = receipt.get("selected_checkpoint")
    selected_step = receipt.get("selected_checkpoint_step")
    if not isinstance(selected, str) or not selected or isinstance(selected_step, bool) or not isinstance(selected_step, int) or selected_step < 0:
        raise GateRejected("training gate must select a concrete passing checkpoint")
    selected_entries = [item for item in validated if item["checkpoint"] == selected and item["checkpoint_step"] == selected_step and item["status"] == "PASS"]
    if len(selected_entries) != 1:
        raise GateRejected("training selected checkpoint must identify exactly one PASS matrix entry")
    selected_entry = selected_entries[0]
    if not training_gate_pass(selected_entry["family_done_counts"]):
        raise GateRejected("selected training checkpoint fails per-family/overall 15/16 and 77/80 criteria")
    if receipt.get("rows") != selected_entry["rows"] or receipt.get("family_row_counts") != selected_entry["family_row_counts"] or receipt.get("family_done_counts") != selected_entry["family_done_counts"]:
        raise GateRejected("training receipt selected rows/counts disagree with checkpoint matrix")
    return {
        "status": "PASS",
        "path": str(path.expanduser().resolve()),
        "selected_checkpoint": selected,
        "selected_checkpoint_step": selected_step,
        "checkpoints": [
            {key: value for key, value in item.items() if key != "rows"} for item in validated
        ],
        "family_row_counts": selected_entry["family_row_counts"],
        "family_done_counts": selected_entry["family_done_counts"],
        "overall_done": selected_entry["overall_done"],
    }


def validate_rehearsal(path: Path = DEFAULT_REHEARSAL, *, planner_path: Path = DEFAULT_PLANNER, warm_start_path: Path = DEFAULT_WARM_START, training_path: Path = DEFAULT_TRAINING) -> dict[str, Any]:
    training = validate_training_gate(training_path, planner_path=planner_path, warm_start_path=warm_start_path)
    if training.get("status") != "PASS":
        raise GateRejected("rehearsal is blocked because the training gate is not PASS")
    receipt = _read(path, "v5.6 rehearsal receipt")
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
            _specialist_row(row, f"rehearsal cell {cell_index} row {row_index}", expected_episode_prefix="rehearsal:")
    if seen_targets != {(-2.5, 0.3), (1.0, 0.3)}:
        raise GateRejected("rehearsal cells do not cover both registered targets")
    flattened_rows = [row for cell in cells for row in cell["rows"]]
    _require_invariant_receipt(receipt, flattened_rows, phase="rehearsal")
    return {"status": "PASS", "path": str(path.expanduser().resolve()), "cells": 2}


def validate_anchor(path: Path = DEFAULT_ANCHOR, *, planner_path: Path = DEFAULT_PLANNER, warm_start_path: Path = DEFAULT_WARM_START, training_path: Path = DEFAULT_TRAINING, rehearsal_path: Path = DEFAULT_REHEARSAL) -> dict[str, Any]:
    rehearsal = validate_rehearsal(rehearsal_path, planner_path=planner_path, warm_start_path=warm_start_path, training_path=training_path)
    if rehearsal.get("status") != "PASS":
        raise GateRejected("anchor is blocked because rehearsal is not PASS")
    receipt = _read(path, "v5.6 anchor receipt")
    if receipt.get("schema") != ANCHOR_SCHEMA or receipt.get("plan_id") != PLAN_ID:
        raise GateRejected("anchor schema/plan_id mismatch")
    if receipt.get("status") != "PASS":
        raise GateRejected(f"anchor status is not PASS: {receipt.get('status')!r}")
    attempts = receipt.get("attempts")
    if not isinstance(attempts, list) or not attempts or len(attempts) > MAX_ANCHOR_ATTEMPTS:
        raise GateRejected("anchor permits one through three attempts")
    if [item.get("attempt") for item in attempts if isinstance(item, Mapping)] != list(range(len(attempts))):
        raise GateRejected("anchor attempt revisions must be contiguous 0..2")
    final = attempts[-1]
    if not isinstance(final, Mapping) or final.get("status") != "PASS":
        raise GateRejected("final anchor attempt is not PASS")
    admitted = final.get("admitted_sequences")
    rows = final.get("rows")
    if not isinstance(admitted, list) or not admitted or any(sequence not in SEQUENCES for sequence in admitted) or len(set(admitted)) != len(admitted):
        raise GateRejected("anchor final attempt must declare a non-empty admitted sequence subset")
    if not isinstance(rows, list) or len(rows) != 16 * len(admitted):
        raise GateRejected("anchor requires sixteen terminal rows per admitted sequence")
    counts = {sequence: 0 for sequence in admitted}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or row.get("sequence") not in counts:
            raise GateRejected(f"anchor row {index} has an invalid sequence")
        _specialist_row(row, f"anchor row {index}", expected_episode_prefix="anchor:")
        counts[row["sequence"]] += 1
    if counts != {sequence: 16 for sequence in admitted}:
        raise GateRejected(f"anchor admitted sequence coverage is incomplete: {counts}")
    _require_invariant_receipt(receipt, rows, phase="anchor")
    return {"status": "PASS", "path": str(path.expanduser().resolve()), "attempts": len(attempts), "sequence_counts": counts, "admitted_sequences": list(admitted)}


def validate_invariant12_prime(
    rows: list[Mapping[str, Any]],
    *,
    expected_rows: int | None = None,
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assert specialist provenance stays out of P3/P4/DV and is explicit elsewhere."""
    if not isinstance(rows, list) or not rows:
        raise GateRejected("invariant12-prime requires non-empty phase coverage")
    required = len(rows) if expected_rows is None else expected_rows
    if isinstance(required, bool) or not isinstance(required, int) or required <= 0 or len(rows) != required:
        raise GateRejected(f"invariant12-prime coverage is incomplete: {len(rows)} rows, expected {required}")
    checked = 0
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise GateRejected(f"invariant12-prime row {index} must be an object")
        active = row.get("hold_specialist_active")
        if not isinstance(active, bool):
            raise GateRejected(f"invariant12-prime row {index}.hold_specialist_active must be bool")
        phase = _row_phase(row)
        provenance = row.get("adapter_provenance")
        nested = provenance if isinstance(provenance, Mapping) else {}
        specialist_checkpoint = row.get("specialist_checkpoint", nested.get("specialist_checkpoint"))
        specialist_step = row.get("specialist_checkpoint_step", nested.get("specialist_checkpoint_step"))
        forbidden = phase in FORBIDDEN_SPECIALIST_PHASES or str(row.get("family", "")) in FORBIDDEN_SPECIALIST_PHASES
        if forbidden and active:
            raise GateRejected(f"invariant12-prime violation at row {index}: specialist active in {phase}")
        if forbidden and specialist_checkpoint not in (None, ""):
            raise GateRejected(f"invariant12-prime row {index} carries specialist checkpoint in forbidden phase")
        if forbidden and specialist_step not in (None, ""):
            raise GateRejected(f"invariant12-prime row {index} carries specialist checkpoint step in forbidden phase")
        if active and phase not in SPECIALIST_PHASES and phase not in CHARACTERIZATION_PHASES and row.get("specialist_phase") not in SPECIALIST_PHASES:
            raise GateRejected(f"invariant12-prime row {index} active outside terminal hold/anchor phase")
        if active and (not isinstance(specialist_checkpoint, str) or not specialist_checkpoint):
            raise GateRejected(f"invariant12-prime row {index} active without specialist checkpoint provenance")
        if active and (isinstance(specialist_step, bool) or not isinstance(specialist_step, int) or specialist_step < 0):
            raise GateRejected(f"invariant12-prime row {index} active without specialist checkpoint step")
        if phase in FORBIDDEN_SPECIALIST_PHASES or phase in SPECIALIST_PHASES or phase in CHARACTERIZATION_PHASES or active:
            checked += 1
    if checked != required:
        raise GateRejected(f"invariant12-prime checked {checked} rows, expected {required}")
    if receipt is not None:
        declared = receipt.get("invariant12_prime")
        if not isinstance(declared, Mapping) or declared.get("status") != "PASS":
            raise GateRejected("receipt must expose invariant12_prime PASS")
        if declared.get("checked_rows") != checked:
            raise GateRejected("receipt invariant12_prime checked_rows does not match rows")
    return {"status": "PASS", "checked_rows": checked, "invariant": "12-prime"}


def require_chain(level: str, *, planner_path: Path = DEFAULT_PLANNER, warm_start_path: Path = DEFAULT_WARM_START, step0_path: Path = DEFAULT_STEP0, training_path: Path = DEFAULT_TRAINING, rehearsal_path: Path = DEFAULT_REHEARSAL, anchor_path: Path = DEFAULT_ANCHOR) -> dict[str, Any]:
    if level not in {"planner", "warm", "step0", "training", "rehearsal", "anchor"}:
        raise GateRejected(f"unknown chain level: {level!r}")
    result: dict[str, Any] = {"level": level, "planner": validate_planner_decision(planner_path)}
    if level in {"warm", "step0", "training", "rehearsal", "anchor"}:
        result["warm_start"] = validate_warm_start(warm_start_path, planner_path=planner_path)
    if level == "step0":
        result["step0"] = validate_step0(step0_path, planner_path=planner_path, warm_start_path=warm_start_path)
    if level in {"training", "rehearsal", "anchor"}:
        result["step0"] = validate_step0(step0_path, planner_path=planner_path, warm_start_path=warm_start_path)
        if result["step0"].get("status") != "PASS":
            raise GateRejected("training launch requires a PASS structural step0 receipt")
        result["training"] = validate_training_gate(training_path, planner_path=planner_path, warm_start_path=warm_start_path)
    if level in {"rehearsal", "anchor"}:
        result["rehearsal"] = validate_rehearsal(rehearsal_path, planner_path=planner_path, warm_start_path=warm_start_path, training_path=training_path)
    if level == "anchor":
        result["anchor"] = validate_anchor(anchor_path, planner_path=planner_path, warm_start_path=warm_start_path, training_path=training_path, rehearsal_path=rehearsal_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=("planner", "warm", "step0", "training", "rehearsal", "anchor"), required=True)
    parser.add_argument("--planner", type=Path, default=DEFAULT_PLANNER)
    parser.add_argument("--warm-start", type=Path, default=DEFAULT_WARM_START)
    parser.add_argument("--step0", type=Path, default=DEFAULT_STEP0)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--rehearsal", type=Path, default=DEFAULT_REHEARSAL)
    parser.add_argument("--anchor", type=Path, default=DEFAULT_ANCHOR)
    args = parser.parse_args()
    try:
        result = require_chain(args.level, planner_path=args.planner, warm_start_path=args.warm_start, step0_path=args.step0, training_path=args.training, rehearsal_path=args.rehearsal, anchor_path=args.anchor)
    except GateRejected as exc:
        parser.exit(2, f"REJECTED: {exc}\n")
    status = "PASS"
    if result.get("step0", {}).get("status") == "NOT_RUN" or result.get("training", {}).get("status") == "NOT_RUN":
        status = "NOT_RUN"
    print(json.dumps({"schema": "a2_piper_pull_v5_6_gate_result_v1", "status": status, **result}, indent=2, sort_keys=True))
    return 3 if status == "NOT_RUN" else 0


if __name__ == "__main__":
    raise SystemExit(main())
