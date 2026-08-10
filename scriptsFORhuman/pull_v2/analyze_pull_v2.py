#!/usr/bin/env python3
"""Analyze pull-v2 checkpoint evals with fail-closed trace and branch evidence checks."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "logs_eval/a2_piper_pull_v2"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "PULL_V2_ANALYSIS.json"
STEPS = (250, 500, 750)
HANDLE_THRESHOLD_RAD = 0.3
LATCH_THRESHOLD_M = 0.015

EVENT_NAMES = (
    "E0_RESET_VALID",
    "E1_OUTSIDE_FACE_PREGRASP",
    "E2_TENSILE_CAPTURE",
    "E3_LATCH_RELEASE",
    "E4_POSITIVE_HINGE_RETAINED",
    "E5_CLEARANCE_DECISION",
    "E6_PATH_REVERSAL_ENTRY",
    "E7_WHOLE_BODY_CLEAR",
)
APERTURE_READY_EVENT_STATES = frozenset(EVENT_NAMES[5:])
TRACE_PULL_REQUIRED = (
    "stage",
    "event_state",
    "root_x_rel_door_m",
    "handle_position_rad",
    "latch_position_m",
    "hinge_position_rad",
    "target_tcp_position_error_m",
    "gripper_handle_separation_m",
    "handle_local_slip_xyz_mps",
    "finger_effort_utilization_estimate",
    "arm_pd_effort_utilization_estimate",
    "reward_component_raw",
)
TRACE_REWARD_REQUIRED = (
    "dont_push_door_handle",
    "target_root_distance",
)
V2_TRACE_REWARD_REQUIRED = "a2_stage3_unlatch_hold"
UNLATCH_BOOLEAN_FIELDS = (
    "stable_unlatch_handle_based",
    "stable_unlatch_latch_based",
    "relock_handle_based",
    "relock_latch_based",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", default=[DEFAULT_INPUT])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--include-seed2",
        action="store_true",
        help="require and include the executable G4 seed2 cell set",
    )
    return parser.parse_args()


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object; got {type(value).__name__}")
    return value


def _require_finite(mapping: Mapping[str, Any], key: str, label: str) -> float:
    value = _finite(mapping.get(key))
    if value is None:
        raise ValueError(f"{label}.{key} must be a finite number; got {mapping.get(key)!r}")
    return value


def _require_bool(mapping: Mapping[str, Any], key: str, label: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{label}.{key} must be bool; got {value!r}")
    return value


def _walk_metrics(inputs: Iterable[Path]) -> list[Path]:
    paths: set[Path] = set()
    for raw in inputs:
        path = raw.resolve()
        if path.is_file() and path.name == "metrics_eval.json":
            paths.add(path)
        elif path.is_dir():
            paths.update(path.rglob("metrics_eval.json"))
        else:
            raise FileNotFoundError(path)
    if not paths:
        raise ValueError("pull-v2 analysis requires at least one metrics_eval.json input")
    return sorted(paths)


def _metadata(path: Path) -> tuple[int, int]:
    match = re.search(r"seed(?P<seed>[0-2])_step(?P<step>250|500|750)(?:/|$)", str(path))
    if match is None:
        raise ValueError(
            "metrics path must expose seed{0,1,2}_step{250,500,750} metadata: "
            f"{path}"
        )
    return int(match.group("seed")), int(match.group("step"))


def _validate_trace_row(row: Any, index: int) -> Mapping[str, Any]:
    label = f"step trace row {index}"
    top = _require_mapping(row, label)
    env_id = top.get("env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id < 0:
        raise ValueError(f"{label}.env_id must be a non-negative int; got {env_id!r}")
    step_index = top.get("step_index")
    if isinstance(step_index, bool) or not isinstance(step_index, int) or step_index < 0:
        raise ValueError(f"{label}.step_index must be a non-negative int; got {step_index!r}")
    threshold = _require_finite(top, "stage3_to4_door_hinge_threshold", label)
    margin = _require_finite(top, "stage3_to4_door_hinge_margin", label)
    if threshold <= 0.0 or not math.isfinite(margin):
        raise ValueError(f"{label} has invalid Stage3-to4 hinge threshold/margin")

    pull = _require_mapping(top.get("pull_v0"), f"{label}.pull_v0")
    for key in TRACE_PULL_REQUIRED:
        if key not in pull:
            raise ValueError(f"{label}.pull_v0 is missing required field {key!r}")
    stage = pull["stage"]
    if isinstance(stage, bool) or not isinstance(stage, int) or stage < 0:
        raise ValueError(f"{label}.pull_v0.stage must be a non-negative int; got {stage!r}")
    event_state = pull["event_state"]
    if event_state not in EVENT_NAMES:
        raise ValueError(f"{label}.pull_v0.event_state is not a known A2 event: {event_state!r}")
    for key in (
        "root_x_rel_door_m",
        "handle_position_rad",
        "latch_position_m",
        "hinge_position_rad",
        "target_tcp_position_error_m",
        "gripper_handle_separation_m",
    ):
        _require_finite(pull, key, f"{label}.pull_v0")

    slip = pull["handle_local_slip_xyz_mps"]
    if not isinstance(slip, list) or len(slip) != 3:
        raise ValueError(f"{label}.pull_v0.handle_local_slip_xyz_mps must be a 3-vector")
    if any(_finite(value) is None for value in slip):
        raise ValueError(f"{label}.pull_v0.handle_local_slip_xyz_mps must be finite")
    for key in ("finger_effort_utilization_estimate", "arm_pd_effort_utilization_estimate"):
        estimate = _require_mapping(pull[key], f"{label}.pull_v0.{key}")
        values = estimate.get("value")
        if not isinstance(values, list) or not values or any(_finite(value) is None for value in values):
            raise ValueError(f"{label}.pull_v0.{key}.value must be a non-empty finite list")
        provenance = estimate.get("provenance")
        if not isinstance(provenance, str) or not provenance:
            raise ValueError(f"{label}.pull_v0.{key}.provenance must be a non-empty string")

    rewards = _require_mapping(pull["reward_component_raw"], f"{label}.pull_v0.reward_component_raw")
    for key in TRACE_REWARD_REQUIRED:
        _require_finite(rewards, key, f"{label}.pull_v0.reward_component_raw")
    return top


def _validate_episode_record(record: Any, index: int) -> Mapping[str, Any]:
    label = f"terminal episode record {index}"
    terminal = _require_mapping(record, label)
    episode = _require_mapping(terminal.get("pull_v0_episode"), f"{label}.pull_v0_episode")
    events = _require_mapping(episode.get("event_reached"), f"{label}.pull_v0_episode.event_reached")
    if set(events) != set(EVENT_NAMES):
        raise ValueError(
            f"{label}.pull_v0_episode.event_reached must contain exactly {EVENT_NAMES}; "
            f"got {sorted(events)}"
        )
    for name in EVENT_NAMES:
        _require_bool(events, name, f"{label}.pull_v0_episode.event_reached")
    return terminal


def _load_cell(metrics_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"metrics payload must be an object: {metrics_path}")
    terminals = payload.get("episode_terminal_diagnostics")
    if not isinstance(terminals, list) or len(terminals) != 16:
        raise ValueError(
            f"{metrics_path} must contain exactly 16 episode_terminal_diagnostics records"
        )
    validated_terminals = [_validate_episode_record(record, index) for index, record in enumerate(terminals)]

    trace_path = metrics_path.parent / "stage2_5_step_trace.json"
    if not trace_path.is_file():
        raise FileNotFoundError(f"required stage2_5_step_trace.json is missing: {trace_path}")
    trace_rows = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(trace_rows, list) or not trace_rows:
        raise ValueError(f"required diagnostic trace must be a non-empty list: {trace_path}")
    validated_trace = [_validate_trace_row(row, index) for index, row in enumerate(trace_rows)]
    for index, row in enumerate(validated_trace):
        rewards = row["pull_v0"]["reward_component_raw"]
        _require_finite(
            rewards,
            V2_TRACE_REWARD_REQUIRED,
            f"step trace row {index}.pull_v0.reward_component_raw",
        )
    return payload, validated_terminals + [{"_trace_row": row} for row in validated_trace]


def _episode_records(terminals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(terminals) != 16:
        raise ValueError(f"each accepted cell requires exactly 16 terminal records; got {len(terminals)}")
    records = []
    for index, terminal in enumerate(terminals):
        validated = _validate_episode_record(terminal, index)
        records.append(dict(validated["pull_v0_episode"]))
    return records


def _primary_dvs(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    if len(episodes) != 16:
        raise ValueError(f"primary pull-v2 DVs require 16 episode records; got {len(episodes)}")
    e2 = [row for row in episodes if row["event_reached"]["E2_TENSILE_CAPTURE"]]
    e4 = [row for row in episodes if row["event_reached"]["E4_POSITIVE_HINGE_RETAINED"]]
    deltas = []
    positive = 0
    for row in e2:
        start = _finite(row.get("hinge_at_first_positive_progress_rad"))
        held = _finite(row.get("held_hinge_max_rad"))
        if start is None or held is None:
            raise ValueError("E2 episode is missing finite hinge progress/hold diagnostics")
        deltas.append(max(0.0, held - start))
        positive += held > start
    return {
        "episode_count": len(episodes),
        "true_stage3_to4_rate": len(e4) / len(episodes),
        "positive_hinge_while_valid_hold_rate": "N/A" if not e2 else positive / len(e2),
        "hinge_delta_while_valid_hold_rad": {
            "median": "N/A" if not deltas else median(deltas),
            "max": "N/A" if not deltas else max(deltas),
        },
    }


def _dwell_and_active(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bands = {
        "<0.02": 0,
        "0.02-0.08": 0,
        "0.08-0.105": 0,
        "0.105-0.25": 0,
        ">=0.25": 0,
    }
    active_unlatch_hold_010_025 = 0
    for row in rows:
        pull = row["pull_v0"]
        hinge = _require_finite(pull, "hinge_position_rad", "trace pull")
        if 0.1 < hinge < 0.25:
            rewards = pull["reward_component_raw"]
            if _require_finite(rewards, "a2_stage3_unlatch_hold", "trace rewards") != 0.0:
                active_unlatch_hold_010_025 += 1
        if hinge < 0.02:
            bands["<0.02"] += 1
        elif hinge < 0.08:
            bands["0.02-0.08"] += 1
        elif hinge < 0.105:
            bands["0.08-0.105"] += 1
        elif hinge < 0.25:
            bands["0.105-0.25"] += 1
        else:
            bands[">=0.25"] += 1
    return {
        "hinge_dwell_band_counts": bands,
        "finite_hinge_trace_steps": len(rows),
        "active_unlatch_hold_steps_hinge_0p1_0p25": active_unlatch_hold_010_025,
    }


def _unlatch_metrics(terminals: list[dict[str, Any]]) -> dict[str, Any]:
    if len(terminals) != 16:
        raise ValueError("unlatch metrics require exactly 16 terminal records")
    diagnostics = []
    for index, terminal in enumerate(terminals):
        label = f"terminal episode record {index}.pull_v2_unlatch"
        diagnostic = _require_mapping(terminal.get("pull_v2_unlatch"), label)
        for key in UNLATCH_BOOLEAN_FIELDS:
            _require_bool(diagnostic, key, label)
        handle_threshold = _require_finite(diagnostic, "handle_unlatch_threshold_rad", label)
        latch_threshold = _require_finite(diagnostic, "latch_unlatch_threshold_m", label)
        if handle_threshold <= 0.0 or latch_threshold <= 0.0:
            raise ValueError(f"{label} thresholds must be positive")
        definition = diagnostic.get("relock_definition")
        if not isinstance(definition, str) or not definition:
            raise ValueError(f"{label}.relock_definition must be a non-empty string")
        diagnostics.append(diagnostic)
    count = len(diagnostics)
    return {
        "available": True,
        "episode_count": count,
        "stable_unlatch_handle_based": sum(bool(row["stable_unlatch_handle_based"]) for row in diagnostics) / count,
        "stable_unlatch_latch_based": sum(bool(row["stable_unlatch_latch_based"]) for row in diagnostics) / count,
        "relock_handle_based": sum(bool(row["relock_handle_based"]) for row in diagnostics) / count,
        "relock_latch_based": sum(bool(row["relock_latch_based"]) for row in diagnostics) / count,
        "thresholds": {
            "handle_rad": diagnostics[0]["handle_unlatch_threshold_rad"],
            "latch_m": diagnostics[0]["latch_unlatch_threshold_m"],
        },
        "relock_definition": diagnostics[0]["relock_definition"],
    }


def _direct_stage3_to4_true(row: Mapping[str, Any]) -> bool:
    # `pull_v0.stage` is the direct producer stage buffer.  The event funnel
    # is independent telemetry and must not be substituted for the stage gate.
    return row["pull_v0"]["stage"] >= 4


def _aperture_ready(row: Mapping[str, Any]) -> bool:
    return row["pull_v0"]["event_state"] in APERTURE_READY_EVENT_STATES


def _first_stage4_admission_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select the first latched Stage4 trace snapshot for each environment.

    The staged task latches ``stage_buf`` at the 3->4 transition.  The trace
    producer can therefore emit later Stage4 rows after the hinge retreats
    below the admission threshold; those rows are post-admission state, not
    new admissions.  ``step_index`` is the control-step chronology and
    ``env_id`` is the per-environment admission unit.
    """

    first_by_env: dict[int, tuple[int, int, dict[str, Any]]] = {}
    for row_index, row in enumerate(rows):
        pull = row["pull_v0"]
        if pull["stage"] < 4:
            continue
        env_id = row["env_id"]
        candidate = (row["step_index"], row_index, row)
        previous = first_by_env.get(env_id)
        if previous is None or candidate[:2] < previous[:2]:
            first_by_env[env_id] = candidate
    return [entry[2] for _env_id, entry in sorted(first_by_env.items())]


def _invariants(rows: list[dict[str, Any]], episodes: list[dict[str, Any]]) -> dict[str, Any]:
    fake_e4 = sum(
        1
        for episode in episodes
        if episode["event_reached"]["E4_POSITIVE_HINGE_RETAINED"]
        and not episode["event_reached"]["E2_TENSILE_CAPTURE"]
    )
    stage4_admission_rows = _first_stage4_admission_rows(rows)
    lower_gate_stage4 = 0
    dont_push_before_stage3_to4 = 0
    target_root_before_aperture = 0
    for row in stage4_admission_rows:
        pull = row["pull_v0"]
        hinge = pull["hinge_position_rad"]
        threshold = row["stage3_to4_door_hinge_threshold"]
        if pull["stage"] >= 4 and hinge < threshold:
            lower_gate_stage4 += 1
    for row in rows:
        pull = row["pull_v0"]
        rewards = pull["reward_component_raw"]
        if rewards["dont_push_door_handle"] != 0.0 and not _direct_stage3_to4_true(row):
            dont_push_before_stage3_to4 += 1
        if rewards["target_root_distance"] != 0.0 and not _aperture_ready(row):
            target_root_before_aperture += 1
    admission_snapshots = [
        {
            "env_id": row["env_id"],
            "step_index": row["step_index"],
            "event_state": row["pull_v0"]["event_state"],
            "hinge_position_rad": row["pull_v0"]["hinge_position_rad"],
            "hinge_threshold_rad": row["stage3_to4_door_hinge_threshold"],
            "below_hinge_gate": row["pull_v0"]["hinge_position_rad"]
            < row["stage3_to4_door_hinge_threshold"],
        }
        for row in stage4_admission_rows
    ]
    result = {
        "fake_e4": fake_e4,
        "stage4_snapshot_below_hinge_gate": lower_gate_stage4,
        "dont_push_before_true_stage3_to4": dont_push_before_stage3_to4,
        "target_root_before_aperture_ready": target_root_before_aperture,
        "stage4_admission": {
            "unit": "environment",
            "boundary": "first trace row with pull_v0.stage >= 4 per env_id",
            "post_admission_stage4_rows_excluded": len(rows)
            - sum(1 for row in rows if row["pull_v0"]["stage"] < 4)
            - len(stage4_admission_rows),
            "admission_snapshot_count": len(stage4_admission_rows),
            "below_hinge_gate_count": lower_gate_stage4,
            "below_hinge_gate_rate": (
                lower_gate_stage4 / len(stage4_admission_rows)
                if stage4_admission_rows
                else "N/A"
            ),
            "snapshots": admission_snapshots,
        },
    }
    result["all_zero"] = all(
        result[key] == 0
        for key in (
            "fake_e4",
            "stage4_snapshot_below_hinge_gate",
            "dont_push_before_true_stage3_to4",
            "target_root_before_aperture_ready",
        )
    )
    return result


def _a0(rows: list[dict[str, Any]]) -> dict[str, Any]:
    slip_norms = []
    finger_util = []
    arm_util = []
    root_rel = []
    tcp_error = []
    handle_frame_error = []
    for row in rows:
        pull = row["pull_v0"]
        slip = pull["handle_local_slip_xyz_mps"]
        slip_norms.append(math.sqrt(sum(float(value) ** 2 for value in slip)))
        finger_util.extend(float(value) for value in pull["finger_effort_utilization_estimate"]["value"])
        arm_util.extend(float(value) for value in pull["arm_pd_effort_utilization_estimate"]["value"])
        root_rel.append(float(pull["root_x_rel_door_m"]))
        tcp_error.append(float(pull["target_tcp_position_error_m"]))
        handle_frame_error.append(float(pull["gripper_handle_separation_m"]))

    def summarize(values: list[float]) -> dict[str, Any]:
        return {"count": len(values), "median": median(values), "max": max(values)}

    return {
        "status": "BOUNDED_OBSERVABLES_ONLY",
        "handle_local_slip_norm_mps": summarize(slip_norms),
        "finger_effort_utilization": summarize(finger_util),
        "arm_effort_utilization": summarize(arm_util),
        "root_relative_x": summarize(root_rel),
        "tcp_position_error_m": summarize(tcp_error),
        "handle_frame_movement_proxy_m": summarize(handle_frame_error),
        "unavailable": [
            "exact action decomposition by arm/base command channel",
            "joint-level applied actuator torque decomposition",
        ],
    }


def _decision(cells: list[dict[str, Any]], decision_seeds: tuple[int, ...] = (0, 1)) -> dict[str, Any]:
    expected = {(seed, step) for seed in decision_seeds for step in STEPS}
    observed = {(cell["seed"], cell["step"]) for cell in cells}
    if observed != expected:
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        raise ValueError(f"branch decision requires complete cells; missing={missing}, unexpected={unexpected}")
    by_seed: dict[int, list[dict[str, Any]]] = {seed: [] for seed in decision_seeds}
    for cell in cells:
        by_seed[cell["seed"]].append(cell)
    seed_inputs = {}
    seed_classes = {}
    for seed in decision_seeds:
        items = by_seed[seed]
        deltas = [
            cell["primary"]["hinge_delta_while_valid_hold_rad"]["max"]
            for cell in items
            if isinstance(cell["primary"]["hinge_delta_while_valid_hold_rad"]["max"], (int, float))
        ]
        max_delta = max(deltas, default=0.0)
        true_rate = max(float(cell["primary"]["true_stage3_to4_rate"]) for cell in items)
        seed_inputs[str(seed)] = {
            "max_hinge_delta_rad": max_delta,
            "max_true_stage3_to4_rate": true_rate,
        }
        if max_delta >= 0.2 or true_rate > 0.0:
            seed_classes[str(seed)] = "G1"
        elif max_delta <= 0.11:
            seed_classes[str(seed)] = "G3"
        else:
            seed_classes[str(seed)] = "G2"
    classes = list(seed_classes.values())
    g1 = any(label == "G1" for label in classes)
    g3 = all(label == "G3" for label in classes)
    g4 = (
        "0" in seed_classes
        and "1" in seed_classes
        and {seed_classes["0"], seed_classes["1"]} == {"G1", "G3"}
    )
    if g4:
        branch = "G4"
    elif g1:
        branch = "G1"
    elif g3:
        branch = "G3"
    else:
        branch = "G2"
    return {
        "decision_seeds": list(decision_seeds),
        "seed_inputs": seed_inputs,
        "G1_wall_supported": g1,
        "G2_partial_platform": branch == "G2",
        "G3_wall_falsified": g3,
        "G4_opposite_seed_conclusions": g4,
        "seed_classes": seed_classes,
        "selected_branch": branch,
    }


def analyze(inputs: Iterable[Path], decision_seeds: tuple[int, ...] = (0, 1)) -> dict[str, Any]:
    metrics_paths = _walk_metrics(inputs)
    expected = {(seed, step) for seed in decision_seeds for step in STEPS}
    by_cell: dict[tuple[int, int], Path] = {}
    for metrics_path in metrics_paths:
        cell_key = _metadata(metrics_path)
        if cell_key not in expected:
            raise ValueError(f"unexpected metrics cell {cell_key}; expected exactly {sorted(expected)}")
        if cell_key in by_cell:
            raise ValueError(f"duplicate metrics inputs for cell {cell_key}: {by_cell[cell_key]}, {metrics_path}")
        by_cell[cell_key] = metrics_path
    if set(by_cell) != expected:
        raise ValueError(f"missing required metrics cells: {sorted(expected - set(by_cell))}")

    cells = []
    for (seed, step), metrics_path in sorted(by_cell.items()):
        _payload, mixed = _load_cell(metrics_path)
        terminals = [row for row in mixed if "_trace_row" not in row]
        trace_rows = [row["_trace_row"] for row in mixed if "_trace_row" in row]
        episodes = _episode_records(terminals)
        try:
            source = str(metrics_path.relative_to(ROOT))
        except ValueError:
            source = str(metrics_path)
        cells.append(
            {
                "source": source,
                "seed": seed,
                "step": step,
                "primary": _primary_dvs(episodes),
                "secondary": _unlatch_metrics(terminals),
                "dwell": _dwell_and_active(trace_rows),
                "invariants": _invariants(trace_rows, episodes),
                "A0_observables": _a0(trace_rows),
            }
        )
    decision = _decision(cells, decision_seeds)
    return {
        "schema": "pull_v2_analysis_v2_fail_closed",
        "plan_id": "a2_piper_pull_v2_wall_removal_and_unlatch_calibration",
        "checkpoint_steps_required": list(STEPS),
        "cells": cells,
        "G1_G4_decision_inputs": decision,
        "A0": (
            {"status": "RUN_FROM_G3_CELL_OBSERVABLES", "cells": [cell["A0_observables"] for cell in cells]}
            if decision["selected_branch"] == "G3"
            else {"status": "NOT_TRIGGERED"}
        ),
    }


def main() -> int:
    args = _parse_args()
    decision_seeds = (0, 1, 2) if args.include_seed2 else (0, 1)
    result = analyze(args.input, decision_seeds=decision_seeds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
