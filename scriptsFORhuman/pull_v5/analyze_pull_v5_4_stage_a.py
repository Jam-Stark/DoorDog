#!/usr/bin/env python3
"""CPU-only feasibility analysis for the Pull-v5.4 Stage-A gate.

The analyzer consumes only the preregistered v5.3 diagnostic traces and the
three v5.2 natural-anchor receipts.  It deliberately does not inspect
``terminal_after_step``: that field has stale semantics in the accepted v5.3
traces and is not a scientific input here.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping


# Frozen preregistration constants.  Keep these before any data-loading code.
VELOCITY_SETTLE_THRESHOLD_RAD_S = 0.05
A4_RAD_BUDGET = 0.10
MAX_SETTLE_S = 2.0
XY_DIRECT_BOUND_M = 0.03
YAW_THRESHOLD_RAD = 0.15
HOLD_S = 2.0
CONTROL_DT_S = 0.02
SAMPLE_RATE_HZ = 50.0
ENV_COUNT = 8
PURE_YAW_MAGNITUDES = (0.05, 0.1, 0.2, 0.4, 0.8, 2.0)
PURE_YAW_DURATIONS_S = (1.0, 2.0, 4.0)
COUPLING_MAGNITUDES = (0.2, 0.8)
COUPLING_PRIMITIVES = ("straight_minus_x", "side_step")
PREFERRED_POSITIVE_MAGNITUDES = (0.8, 2.0)
A3_CORRELATION_THRESHOLD = 0.30
A3_MEDIAN_GAP_THRESHOLD_RAD = 0.05

# The scheduler constants below are frozen from the same Stage-A input fields
# consumed by the feasibility analysis.  They are emitted into the Stage-A
# receipt so runtime code resolves every value from one current artifact.
SCHEDULER_B_TRIM_RAD = 0.22435537973512823
SCHEDULER_COARSE_CUTOFF_NEGATIVE_E_RAD = -0.4412067333804529
SCHEDULER_COARSE_CUTOFF_POSITIVE_E_RAD = -0.18526641527284796
SCHEDULER_TRIM_STEP_CAP = 200

A3_CONCENTRATION_RULE: dict[str, Any] = {
    "name": "waypoint_misses_concentrated_at_high_yaw_error",
    "miss_definition": "waypoint_arrived is false",
    "predictor": "abs(yaw_error_rad)",
    "point_biserial_correlation_min": A3_CORRELATION_THRESHOLD,
    "median_abs_yaw_error_miss_minus_hit_min_rad": A3_MEDIAN_GAP_THRESHOLD_RAD,
    "pass_condition": (
        "point-biserial correlation >= 0.30 and median abs yaw error among "
        "waypoint misses exceeds hits by >= 0.05 rad"
    ),
}

ROOT = Path(__file__).resolve().parents[2]
TRACE_ROOT = ROOT / "logs_eval/a2_piper_pull_v5"
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("V5_4_STAGE_A_FEASIBILITY.json")
PLANNER_ARTIFACT = TRACE_ROOT / "v5_4_planner_architecture_decision.json"
V5_3_ADJUDICATION = TRACE_ROOT / "v5_3_p0_adjudication.json"
ANCHOR_RECEIPTS = tuple(
    TRACE_ROOT / "pull_v5_2_p1_anchor_probe" / relative
    for relative in (
        "anchor/P1_v5_2_anchor_natural_attempt1_RECEIPT.json",
        "anchor_attempt2/P1_v5_2_anchor_natural_attempt2_RECEIPT.json",
        "anchor_attempt3/P1_v5_2_anchor_natural_attempt3_RECEIPT.json",
    )
)

TRACE_SCHEMA = "a2_piper_pull_v5_interface_characterization_trace_v1"
TRACE_PLAN_ID = "a2_piper_pull_v5_3_locomotion_interface_probe"
RECEIPT_SCHEMA = "a2_piper_pull_v5_4_stage_a_feasibility_v1"

TRACE_TOP_LEVEL_KEYS = {
    "schema",
    "record_class",
    "version",
    "cell_id",
    "fixture",
    "plan_id",
    "num_envs",
    "first_episode_only",
    "command_steps",
    "hold_steps",
    "window_steps",
    "duration_s",
    "hold_s",
    "requested_u",
    "xy_primitive",
    "control_dt",
    "scientific_denominator_included",
    "denominator_scope",
    "trace_writer",
    "rows",
}
TRACE_ROW_KEYS = {
    "record_class",
    "schema",
    "cell_id",
    "fixture",
    "env_id",
    "episode_index",
    "episode_id",
    "step_index",
    "command_phase",
    "zero_hold_phase",
    "phase",
    "requested_u",
    "cell_requested_u",
    "xy_primitive",
    "applied_raw_base_slice",
    "scaled_clipped_physical_base_command",
    "realized_world_yaw_pre",
    "realized_world_yaw_post",
    "yaw_delta_rad",
    "yaw_velocity_rad_s",
    "root_pos_pre_world",
    "root_pos_post_world",
    "root_motion_xy_world",
    "root_motion_m",
    "terminal_after_step",
    "control_dt",
}
ANCHOR_TOP_LEVEL_KEYS = {
    "anchor_attempt",
    "anchor_measurements",
    "anchor_pass",
    "anchored_sequences",
    "bucket_sequence_records",
    "closer_bucket",
    "closer_buckets",
    "command_library",
    "correction_retry",
    "evaluator_override",
    "fixture",
    "frame_passage_count",
    "implementation_defects",
    "interface_feasible",
    "lattice",
    "probe_records",
    "reset_source_group",
    "reset_sources",
    "schema",
    "sequence_counts",
    "sequence_ids",
    "sequence_phases",
    "sequence_results",
    "source",
    "status",
    "terminal_records",
}


def _token(value: float) -> str:
    text = f"{abs(value):g}".replace(".", "p")
    return ("p" if value >= 0.0 else "m") + text


def _cell_id(kind: str, requested_u: float, duration_s: float, primitive: str = "none") -> str:
    if kind == "pure_yaw":
        return f"pure_yaw_{_token(requested_u)}_T{duration_s:g}".replace(".", "p")
    return f"coupling_{primitive}_{_token(requested_u)}_T{duration_s:g}".replace(".", "p")


def _expected_grid() -> tuple[dict[str, Any], ...]:
    cells: list[dict[str, Any]] = []
    for magnitude in PURE_YAW_MAGNITUDES:
        for sign in (-1.0, 1.0):
            requested_u = sign * magnitude
            for duration_s in PURE_YAW_DURATIONS_S:
                cells.append(
                    {
                        "kind": "pure_yaw",
                        "cell_id": _cell_id("pure_yaw", requested_u, duration_s),
                        "requested_u": requested_u,
                        "duration_s": duration_s,
                        "hold_s": HOLD_S,
                        "xy_primitive": "none",
                        "command_steps": int(round(duration_s / CONTROL_DT_S)),
                        "hold_steps": int(round(HOLD_S / CONTROL_DT_S)),
                    }
                )
    for magnitude in COUPLING_MAGNITUDES:
        for sign in (-1.0, 1.0):
            requested_u = sign * magnitude
            for primitive in COUPLING_PRIMITIVES:
                duration_s = 2.0
                cells.append(
                    {
                        "kind": "coupling",
                        "cell_id": _cell_id("coupling", requested_u, duration_s, primitive),
                        "requested_u": requested_u,
                        "duration_s": duration_s,
                        "hold_s": HOLD_S,
                        "xy_primitive": primitive,
                        "command_steps": int(round(duration_s / CONTROL_DT_S)),
                        "hold_steps": int(round(HOLD_S / CONTROL_DT_S)),
                    }
                )
    return tuple(cells)


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be finite numeric; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite numeric; got {value!r}")
    return result


def _exact_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer; got {value!r}")
    return int(value)


def _exact_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be bool; got {value!r}")
    return value


def _finite_vector(value: object, length: int, field: str) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{field} must contain exactly {length} values; got {value!r}")
    return [_finite_float(item, f"{field}[{index}]") for index, item in enumerate(value)]


def _wrapped_yaw(value: float) -> float:
    return math.remainder(float(value), 2.0 * math.pi)


def _close(actual: float, expected: float, tolerance: float = 1.0e-9) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance)


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _validate_references() -> dict[str, Any]:
    planner = _read_json(PLANNER_ARTIFACT)
    if not isinstance(planner, Mapping):
        raise ValueError(f"planner artifact must be an object: {PLANNER_ARTIFACT}")
    required_planner = {
        "schema": "a2_piper_pull_v5_4_planner_architecture_decision_v1",
        "plan_id": "a2_piper_pull_v5_4_terminal_yaw_scheduler",
        "decision": "MODEL_BASED_SCHEDULER_FIRST",
        "residual_precommitted": True,
        "fine_tune_deferred": True,
        "scientific_denominator_included": False,
    }
    for field, expected in required_planner.items():
        if planner.get(field) != expected:
            raise ValueError(
                f"planner artifact {field!r} must equal {expected!r}; got {planner.get(field)!r}"
            )
    adjudication = _read_json(V5_3_ADJUDICATION)
    if not isinstance(adjudication, Mapping):
        raise ValueError(f"v5.3 adjudication must be an object: {V5_3_ADJUDICATION}")
    required_adjudication = {
        "schema": "a2_piper_pull_v5_3_p0_adjudication_v1",
        "hypothesis": "H-D",
        "downstream_admitted": False,
    }
    for field, expected in required_adjudication.items():
        if adjudication.get(field) != expected:
            raise ValueError(
                f"v5.3 adjudication {field!r} must equal {expected!r}; got {adjudication.get(field)!r}"
            )
    return {
        "planner_decision_artifact": {
            "path": str(PLANNER_ARTIFACT.relative_to(ROOT)),
            "immutable": True,
            "plan_id": planner["plan_id"],
            "decision": planner["decision"],
        },
        "v5_3_adjudication": {
            "path": str(V5_3_ADJUDICATION.relative_to(ROOT)),
            "immutable": True,
            "hypothesis": adjudication["hypothesis"],
            "downstream_admitted": adjudication["downstream_admitted"],
        },
    }


def _validate_trace(path: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"trace must be an object: {path}")
    if set(payload) != TRACE_TOP_LEVEL_KEYS:
        missing = sorted(TRACE_TOP_LEVEL_KEYS - set(payload))
        extra = sorted(set(payload) - TRACE_TOP_LEVEL_KEYS)
        raise ValueError(f"{path} has schema key mismatch; missing={missing}, extra={extra}")
    top_expected: dict[str, Any] = {
        "schema": TRACE_SCHEMA,
        "record_class": "interface_characterization",
        "version": 1,
        "cell_id": expected["cell_id"],
        "fixture": "open_field",
        "plan_id": TRACE_PLAN_ID,
        "num_envs": ENV_COUNT,
        "first_episode_only": True,
        "command_steps": expected["command_steps"],
        "hold_steps": expected["hold_steps"],
        "window_steps": expected["command_steps"] + expected["hold_steps"],
        "duration_s": expected["duration_s"],
        "hold_s": HOLD_S,
        "requested_u": expected["requested_u"],
        "xy_primitive": expected["xy_primitive"],
        "scientific_denominator_included": False,
        "denominator_scope": "none",
    }
    for field, wanted in top_expected.items():
        actual = payload.get(field)
        if isinstance(wanted, float):
            if not _close(_finite_float(actual, f"{path}.{field}"), wanted):
                raise ValueError(f"{path}.{field} expected {wanted}, got {actual}")
        elif actual != wanted:
            raise ValueError(f"{path}.{field} expected {wanted!r}, got {actual!r}")
    control_dt = _finite_float(payload["control_dt"], f"{path}.control_dt")
    if not _close(control_dt, CONTROL_DT_S, 1.0e-12):
        raise ValueError(f"{path}.control_dt must be exactly 50Hz 0.02s; got {control_dt}")
    rows = payload["rows"]
    if not isinstance(rows, list):
        raise ValueError(f"{path}.rows must be a list")
    window_steps = expected["command_steps"] + expected["hold_steps"]
    if len(rows) != ENV_COUNT * window_steps:
        raise ValueError(f"{path} expected {ENV_COUNT * window_steps} rows; got {len(rows)}")
    rows_by_env: dict[int, list[dict[str, Any]]] = {env_id: [] for env_id in range(ENV_COUNT)}
    for row_index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"{path} row {row_index} must be an object")
        if set(row) != TRACE_ROW_KEYS:
            missing = sorted(TRACE_ROW_KEYS - set(row))
            extra = sorted(set(row) - TRACE_ROW_KEYS)
            raise ValueError(
                f"{path} row {row_index} schema key mismatch; missing={missing}, extra={extra}"
            )
        env_id = row_index // window_steps
        step_index = row_index % window_steps
        if _exact_int(row["env_id"], f"{path} row {row_index}.env_id") != env_id:
            raise ValueError(f"{path} rows are not contiguous env-major at row {row_index}")
        if _exact_int(row["step_index"], f"{path} row {row_index}.step_index") != step_index:
            raise ValueError(f"{path} rows are not contiguous env-major at row {row_index}")
        if row["schema"] != TRACE_SCHEMA or row["record_class"] != "interface_characterization":
            raise ValueError(f"{path} row {row_index} has invalid schema/record_class")
        if row["cell_id"] != expected["cell_id"] or row["fixture"] != "open_field":
            raise ValueError(f"{path} row {row_index} has invalid cell/fixture")
        if _exact_int(row["episode_index"], f"{path} row {row_index}.episode_index") != 0:
            raise ValueError(f"{path} row {row_index} is not first-episode data")
        expected_episode = f"{expected['cell_id']}:env{env_id}:episode0"
        if row["episode_id"] != expected_episode:
            raise ValueError(f"{path} row {row_index} has invalid episode_id")
        command_phase = step_index < expected["command_steps"]
        if _exact_bool(row["command_phase"], f"{path} row {row_index}.command_phase") is not command_phase:
            raise ValueError(f"{path} row {row_index} has invalid command_phase")
        if _exact_bool(row["zero_hold_phase"], f"{path} row {row_index}.zero_hold_phase") is command_phase:
            raise ValueError(f"{path} row {row_index} has invalid zero_hold_phase")
        if row["phase"] != ("command" if command_phase else "zero_hold"):
            raise ValueError(f"{path} row {row_index} has invalid phase")
        row_u = _finite_float(row["requested_u"], f"{path} row {row_index}.requested_u")
        expected_row_u = expected["requested_u"] if command_phase else 0.0
        if not _close(row_u, expected_row_u, 1.0e-6):
            raise ValueError(f"{path} row {row_index} requested_u mismatch")
        cell_u = _finite_float(row["cell_requested_u"], f"{path} row {row_index}.cell_requested_u")
        if not _close(cell_u, expected["requested_u"], 1.0e-6):
            raise ValueError(f"{path} row {row_index} cell_requested_u mismatch")
        if row["xy_primitive"] != expected["xy_primitive"]:
            raise ValueError(f"{path} row {row_index} xy_primitive mismatch")
        raw = _finite_vector(row["applied_raw_base_slice"], 5, f"{path} row {row_index}.applied_raw_base_slice")
        if not _close(raw[2], expected_row_u, 1.0e-6):
            raise ValueError(f"{path} row {row_index} raw yaw command mismatch")
        _finite_vector(
            row["scaled_clipped_physical_base_command"],
            5,
            f"{path} row {row_index}.scaled_clipped_physical_base_command",
        )
        _finite_float(row["realized_world_yaw_pre"], f"{path} row {row_index}.realized_world_yaw_pre")
        _finite_float(row["realized_world_yaw_post"], f"{path} row {row_index}.realized_world_yaw_post")
        _finite_float(row["yaw_delta_rad"], f"{path} row {row_index}.yaw_delta_rad")
        _finite_float(row["yaw_velocity_rad_s"], f"{path} row {row_index}.yaw_velocity_rad_s")
        _finite_vector(row["root_pos_pre_world"], 3, f"{path} row {row_index}.root_pos_pre_world")
        _finite_vector(row["root_pos_post_world"], 3, f"{path} row {row_index}.root_pos_post_world")
        _finite_vector(row["root_motion_xy_world"], 2, f"{path} row {row_index}.root_motion_xy_world")
        if _finite_float(row["root_motion_m"], f"{path} row {row_index}.root_motion_m") < 0.0:
            raise ValueError(f"{path} row {row_index} has negative root_motion_m")
        row_dt = _finite_float(row["control_dt"], f"{path} row {row_index}.control_dt")
        if not _close(row_dt, CONTROL_DT_S, 1.0e-12):
            raise ValueError(f"{path} row {row_index} is not sampled at 50Hz")
        # Presence is part of the exact schema, but this stale field is never
        # read or used for science.
        if "terminal_after_step" not in row:
            raise ValueError(f"{path} row {row_index} is missing terminal_after_step")
        rows_by_env[env_id].append(dict(row))
    return {
        "path": path,
        "cell": dict(expected),
        "rows_by_env": rows_by_env,
        "row_count": len(rows),
        "control_dt": control_dt,
    }


def _summary(values: Iterable[float]) -> dict[str, float]:
    numbers = [float(value) for value in values]
    if not numbers:
        raise ValueError("cannot summarize an empty array")
    return {
        "min": min(numbers),
        "median": statistics.median(numbers),
        "max": max(numbers),
    }


def _derive_trace_metrics(validated: Mapping[str, Any]) -> dict[str, Any]:
    cell = validated["cell"]
    command_steps = int(cell["command_steps"])
    rows_by_env: Mapping[int, list[dict[str, Any]]] = validated["rows_by_env"]
    env_metrics: list[dict[str, Any]] = []
    for env_id in range(ENV_COUNT):
        rows = rows_by_env[env_id]
        command_rows = rows[:command_steps]
        hold_rows = rows[command_steps:]
        cutoff_yaw = _finite_float(command_rows[-1]["realized_world_yaw_post"], "cutoff yaw")
        hold_end_yaw = _finite_float(hold_rows[-1]["realized_world_yaw_post"], "hold-end yaw")
        stop_drift = _wrapped_yaw(hold_end_yaw - cutoff_yaw)
        above_threshold = [
            index
            for index, row in enumerate(hold_rows)
            if abs(_finite_float(row["yaw_velocity_rad_s"], "hold yaw velocity"))
            > VELOCITY_SETTLE_THRESHOLD_RAD_S
        ]
        last_above = above_threshold[-1] if above_threshold else None
        settle_time = 0.0 if last_above is None else (last_above + 1) * CONTROL_DT_S
        settle_source_yaw = (
            cutoff_yaw
            if last_above is None
            else _finite_float(hold_rows[last_above]["realized_world_yaw_post"], "settle source yaw")
        )
        residual_drift = _wrapped_yaw(hold_end_yaw - settle_source_yaw)
        last_one_second_rows = hold_rows[-int(round(1.0 / CONTROL_DT_S)) :]
        a2_last_one_second = max(
            abs(
                _wrapped_yaw(
                    _finite_float(row["realized_world_yaw_post"], "last-second yaw") - hold_end_yaw
                )
            )
            for row in last_one_second_rows
        )
        last_hold_velocity = _finite_float(hold_rows[-1]["yaw_velocity_rad_s"], "last-hold velocity")
        hold_xy = [
            sum(_finite_float(row["root_motion_xy_world"][axis], "hold XY") for row in hold_rows)
            for axis in range(2)
        ]
        hold_xy_norm = math.hypot(hold_xy[0], hold_xy[1])
        command_yaw = _wrapped_yaw(
            _finite_float(command_rows[-1]["realized_world_yaw_post"], "command-end yaw")
            - _finite_float(command_rows[0]["realized_world_yaw_pre"], "command-start yaw")
        )
        env_metrics.append(
            {
                "env_id": env_id,
                "cutoff_yaw_post_rad": cutoff_yaw,
                "hold_end_yaw_post_rad": hold_end_yaw,
                "stop_drift_rad": stop_drift,
                "last_above_threshold_hold_index": last_above,
                "last_above_threshold_step_index": (
                    None if last_above is None else command_steps + last_above
                ),
                "settle_time_s": settle_time,
                "settle_source_yaw_post_rad": settle_source_yaw,
                "residual_drift_rad": residual_drift,
                "a2_last_1s_max_abs_wrapped_rad": a2_last_one_second,
                "last_hold_yaw_velocity_rad_s": last_hold_velocity,
                "command_window_yaw_rad": command_yaw,
                "hold_xy_vector_m": hold_xy,
                "hold_xy_norm_m": hold_xy_norm,
            }
        )
    arrays = {
        "stop_drift_rad": [entry["stop_drift_rad"] for entry in env_metrics],
        "settle_time_s": [entry["settle_time_s"] for entry in env_metrics],
        "residual_drift_rad": [entry["residual_drift_rad"] for entry in env_metrics],
        "a2_last_1s_max_abs_wrapped_rad": [
            entry["a2_last_1s_max_abs_wrapped_rad"] for entry in env_metrics
        ],
        "last_hold_yaw_velocity_rad_s": [
            entry["last_hold_yaw_velocity_rad_s"] for entry in env_metrics
        ],
        "command_window_yaw_rad": [entry["command_window_yaw_rad"] for entry in env_metrics],
        "hold_xy_vector_m": [entry["hold_xy_vector_m"] for entry in env_metrics],
        "hold_xy_norm_m": [entry["hold_xy_norm_m"] for entry in env_metrics],
    }
    return {
        "cell_id": cell["cell_id"],
        "kind": cell["kind"],
        "requested_u": cell["requested_u"],
        "duration_s": cell["duration_s"],
        "xy_primitive": cell["xy_primitive"],
        "command_steps": command_steps,
        "hold_steps": cell["hold_steps"],
        "control_dt_s": CONTROL_DT_S,
        "per_env": env_metrics,
        "arrays": arrays,
        "summaries": {
            field: _summary(values)
            for field, values in arrays.items()
            if field != "hold_xy_vector_m"
        },
        "median_stop_drift_rad": statistics.median(arrays["stop_drift_rad"]),
        "dispersion_rad": max(
            abs(value - statistics.median(arrays["stop_drift_rad"]))
            for value in arrays["stop_drift_rad"]
        ),
        "a2_stability_max_rad": max(arrays["a2_last_1s_max_abs_wrapped_rad"]),
        "max_settle_s": max(arrays["settle_time_s"]),
        "max_hold_xy_m": max(arrays["hold_xy_norm_m"]),
    }


def _validate_anchor_receipt(path: Path, expected_attempt: int) -> list[dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"anchor receipt must be an object: {path}")
    if set(payload) != ANCHOR_TOP_LEVEL_KEYS:
        missing = sorted(ANCHOR_TOP_LEVEL_KEYS - set(payload))
        extra = sorted(set(payload) - ANCHOR_TOP_LEVEL_KEYS)
        raise ValueError(f"{path} anchor schema key mismatch; missing={missing}, extra={extra}")
    required = {
        "schema",
        "anchor_attempt",
        "anchor_measurements",
        "fixture",
        "source",
        "reset_source_group",
        "reset_sources",
        "sequence_counts",
        "terminal_records",
        "probe_records",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"{path} missing required anchor fields: {missing}")
    if payload["schema"] != "a2_piper_pull_v5_2_p1_receipt_v1":
        raise ValueError(f"{path} has unexpected anchor schema")
    if _exact_int(payload["anchor_attempt"], f"{path}.anchor_attempt") != expected_attempt:
        raise ValueError(f"{path} has unexpected anchor attempt")
    if payload["fixture"] != "anchor" or payload["source"] != "natural":
        raise ValueError(f"{path} is not a natural anchor receipt")
    if payload["reset_source_group"] != "natural" or payload["reset_sources"] != ["natural"]:
        raise ValueError(f"{path} has invalid reset-source provenance")
    sequence_counts = payload["sequence_counts"]
    if not isinstance(sequence_counts, Mapping) or set(sequence_counts) != {"S1", "S2", "S3", "S4"}:
        raise ValueError(f"{path} sequence_counts must contain exactly S1-S4")
    for sequence, count in sequence_counts.items():
        if _exact_int(count, f"{path}.sequence_counts.{sequence}") != 16:
            raise ValueError(f"{path} {sequence} must contain 16 measurements")
    if _exact_int(payload["terminal_records"], f"{path}.terminal_records") != 64:
        raise ValueError(f"{path} terminal_records must be 64")
    if _exact_int(payload["probe_records"], f"{path}.probe_records") != 64:
        raise ValueError(f"{path} probe_records must be 64")
    measurements = payload["anchor_measurements"]
    if not isinstance(measurements, Mapping) or set(measurements) != {"S1", "S2", "S3", "S4"}:
        raise ValueError(f"{path} anchor_measurements must contain exactly S1-S4")
    records: list[dict[str, Any]] = []
    for sequence in ("S1", "S2", "S3", "S4"):
        rows = measurements[sequence]
        if not isinstance(rows, list) or len(rows) != 16:
            raise ValueError(f"{path} {sequence} must contain exactly 16 measurements")
        for measurement_index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise ValueError(f"{path} {sequence}[{measurement_index}] must be an object")
            if set(row) != {
                "waypoint_arrived",
                "waypoint_position_error_m",
                "yaw_arrived",
                "yaw_error_rad",
            }:
                raise ValueError(f"{path} {sequence}[{measurement_index}] schema mismatch")
            waypoint_arrived = _exact_bool(
                row["waypoint_arrived"], f"{path} {sequence}[{measurement_index}].waypoint_arrived"
            )
            yaw_arrived = _exact_bool(
                row["yaw_arrived"], f"{path} {sequence}[{measurement_index}].yaw_arrived"
            )
            waypoint_error = _finite_float(
                row["waypoint_position_error_m"],
                f"{path} {sequence}[{measurement_index}].waypoint_position_error_m",
            )
            yaw_error = _finite_float(
                row["yaw_error_rad"], f"{path} {sequence}[{measurement_index}].yaw_error_rad"
            )
            if waypoint_error < 0.0 or yaw_error < 0.0:
                raise ValueError(f"{path} {sequence}[{measurement_index}] has negative error")
            records.append(
                {
                    "attempt": expected_attempt,
                    "sequence": sequence,
                    "measurement_index": measurement_index,
                    "waypoint_arrived": waypoint_arrived,
                    "waypoint_miss": not waypoint_arrived,
                    "waypoint_position_error_m": waypoint_error,
                    "yaw_arrived": yaw_arrived,
                    "yaw_error_rad": yaw_error,
                    "abs_yaw_error_rad": abs(yaw_error),
                }
            )
    return records


def _point_biserial(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("point-biserial input is empty")
    misses = [float(row["abs_yaw_error_rad"]) for row in records if row["waypoint_miss"]]
    hits = [float(row["abs_yaw_error_rad"]) for row in records if not row["waypoint_miss"]]
    if not misses or not hits:
        raise ValueError("point-biserial input requires both waypoint misses and hits")
    values = misses + hits
    n = len(values)
    mean_all = sum(values) / n
    sample_sd = math.sqrt(sum((value - mean_all) ** 2 for value in values) / (n - 1))
    if sample_sd == 0.0:
        correlation = 0.0
    else:
        correlation = (sum(misses) / len(misses) - sum(hits) / len(hits)) / sample_sd
        correlation *= math.sqrt((len(misses) * len(hits)) / (n * n))
    median_gap = statistics.median(misses) - statistics.median(hits)
    return {
        "n": n,
        "waypoint_miss_count": len(misses),
        "waypoint_hit_count": len(hits),
        "mean_abs_yaw_error_miss_rad": sum(misses) / len(misses),
        "mean_abs_yaw_error_hit_rad": sum(hits) / len(hits),
        "median_abs_yaw_error_miss_rad": statistics.median(misses),
        "median_abs_yaw_error_hit_rad": statistics.median(hits),
        "median_gap_miss_minus_hit_rad": median_gap,
        "point_biserial_correlation": correlation,
        "correlation_condition": correlation >= A3_CORRELATION_THRESHOLD,
        "median_gap_condition": median_gap >= A3_MEDIAN_GAP_THRESHOLD_RAD,
        "rule_passes": (
            correlation >= A3_CORRELATION_THRESHOLD
            and median_gap >= A3_MEDIAN_GAP_THRESHOLD_RAD
        ),
    }


def _coupling_bias(
    metrics_by_cell: Mapping[str, Mapping[str, Any]],
    coupling: Mapping[str, Any],
) -> dict[str, Any]:
    pure_id = _cell_id("pure_yaw", float(coupling["requested_u"]), float(coupling["duration_s"]))
    if pure_id not in metrics_by_cell:
        raise ValueError(f"missing pure match for coupling cell {coupling['cell_id']}: {pure_id}")
    pure = metrics_by_cell[pure_id]
    coupling_values = coupling["arrays"]["command_window_yaw_rad"]
    pure_values = pure["arrays"]["command_window_yaw_rad"]
    biases = [
        _wrapped_yaw(float(coupling_values[env_id]) - float(pure_values[env_id]))
        for env_id in range(ENV_COUNT)
    ]
    return {
        "cell_id": coupling["cell_id"],
        "requested_u": coupling["requested_u"],
        "duration_s": coupling["duration_s"],
        "xy_primitive": coupling["xy_primitive"],
        "matched_pure_cell_id": pure_id,
        "per_env": [
            {
                "env_id": env_id,
                "coupling_command_window_yaw_rad": coupling_values[env_id],
                "pure_command_window_yaw_rad": pure_values[env_id],
                "yaw_bias_rad": biases[env_id],
            }
            for env_id in range(ENV_COUNT)
        ],
        "yaw_bias_rad": biases,
        "summary": _summary(biases),
    }


def _a4_candidate(
    metric: Mapping[str, Any],
    concentration_rule_passes: bool,
) -> dict[str, Any]:
    dispersion = float(metric["dispersion_rad"])
    stability = float(metric["a2_stability_max_rad"])
    stop_stability_sum = dispersion + stability
    max_settle = float(metric["max_settle_s"])
    max_xy = float(metric["max_hold_xy_m"])
    condition_i = stop_stability_sum <= A4_RAD_BUDGET
    condition_ii = max_settle <= MAX_SETTLE_S
    xy_direct = max_xy <= XY_DIRECT_BOUND_M
    condition_iii = xy_direct or concentration_rule_passes
    # Selection margin is the minimum slack of numeric conditions actually
    # carrying the candidate.  A concentration pass has no XY distance slack,
    # so it does not introduce an invented numeric margin.
    condition_margins = {
        "i_rad": A4_RAD_BUDGET - stop_stability_sum,
        "ii_s": MAX_SETTLE_S - max_settle,
        "iii_direct_xy_m": XY_DIRECT_BOUND_M - max_xy,
    }
    active_margins = [condition_margins["i_rad"], condition_margins["ii_s"]]
    if xy_direct:
        active_margins.append(condition_margins["iii_direct_xy_m"])
    selection_margin = min(active_margins)
    return {
        "cell_id": metric["cell_id"],
        "requested_u": metric["requested_u"],
        "raw_command_direction": (
            "positive" if float(metric["requested_u"]) > 0.0 else "negative"
        ),
        "realized_command_window_yaw_summary_rad": metric["summaries"][
            "command_window_yaw_rad"
        ],
        "realized_command_window_yaw_direction": (
            "positive"
            if metric["summaries"]["command_window_yaw_rad"]["median"] > 0.0
            else "negative"
            if metric["summaries"]["command_window_yaw_rad"]["median"] < 0.0
            else "zero"
        ),
        "duration_s": metric["duration_s"],
        "median_stop_drift_rad": metric["median_stop_drift_rad"],
        "dispersion_rad": dispersion,
        "a2_stability_max_rad": stability,
        "dispersion_plus_stability_rad": stop_stability_sum,
        "max_settle_s": max_settle,
        "max_hold_xy_m": max_xy,
        "a3_concentration_rule_passes": concentration_rule_passes,
        "conditions": {
            "i_dispersion_plus_stability_le_0.10_rad": condition_i,
            "ii_max_settle_le_2.0_s": condition_ii,
            "iii_max_xy_le_0.03_m_or_a3_concentration": condition_iii,
            "iii_direct_xy_branch": xy_direct,
        },
        "condition_margins": condition_margins,
        "selection_margin": selection_margin,
        "passes": condition_i and condition_ii and condition_iii,
    }


def _select_candidate(candidates: list[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    passing = [dict(candidate) for candidate in candidates if candidate["passes"]]
    positive = [candidate for candidate in passing if float(candidate["requested_u"]) > 0.0]
    preferred_positive = [
        candidate
        for candidate in positive
        if math.isclose(abs(float(candidate["requested_u"])), 0.8, abs_tol=1.0e-12)
        or math.isclose(abs(float(candidate["requested_u"])), 2.0, abs_tol=1.0e-12)
    ]
    if preferred_positive:
        pool = preferred_positive
        policy = "preferred_positive_high_abs"
    elif positive:
        pool = positive
        policy = "positive_max_margin_fallback"
    else:
        pool = passing
        policy = "all_passing_max_margin_fallback"
    if not pool:
        return None, {
            "policy": policy,
            "passing_candidate_count": len(passing),
            "positive_passing_candidate_count": len(positive),
            "preferred_positive_passing_candidate_count": len(preferred_positive),
        }
    selected = sorted(
        pool,
        key=lambda candidate: (
            -float(candidate["selection_margin"]),
            float(candidate["duration_s"]),
            abs(float(candidate["requested_u"])),
            str(candidate["cell_id"]),
        ),
    )[0]
    return selected, {
        "policy": policy,
        "passing_candidate_count": len(passing),
        "positive_passing_candidate_count": len(positive),
        "preferred_positive_passing_candidate_count": len(preferred_positive),
    }


def _scheduler_derived_block(
    metrics_by_cell: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Freeze every runtime scheduler number into this Stage-A receipt.

    The measured rates, stop drift, settle counts, trim pulse and hold/deadline
    values are derived directly from validated Stage-A cells.  The two planning
    boundaries and trim band are the planner-frozen values, recorded here once
    so runtime consumers resolve them from this artifact rather than an absent
    external receipt.
    """

    negative = metrics_by_cell["pure_yaw_m2_T4"]
    positive = metrics_by_cell["pure_yaw_p2_T4"]
    trim = metrics_by_cell["pure_yaw_p0p05_T4"]

    def _last_above_plus_one(metric: Mapping[str, Any]) -> int:
        indices = [
            value
            for value in (row["last_above_threshold_hold_index"] for row in metric["per_env"])
            if value is not None
        ]
        if not indices:
            return 0
        return max(int(value) for value in indices) + 1

    negative_rate = float(negative["summaries"]["command_window_yaw_rad"]["median"]) / float(
        negative["duration_s"]
    )
    positive_rate = float(positive["summaries"]["command_window_yaw_rad"]["median"]) / float(
        positive["duration_s"]
    )
    trim_rate = float(trim["summaries"]["command_window_yaw_rad"]["median"]) / float(
        trim["duration_s"]
    )
    dt = float(negative["control_dt_s"])
    negative_stop = float(negative["median_stop_drift_rad"])
    positive_stop = float(positive["median_stop_drift_rad"])
    trim_stop = float(trim["median_stop_drift_rad"])
    trim_one_step = trim_rate * dt
    hold_steps = int(negative["hold_steps"])
    constants = {
        "dt_s": {
            "value": dt,
            "source_jsonpath": "$.preregistration.constants.control_dt_s",
            "derivation": "validated 50Hz control interval",
        },
        "planning_a_rad": {
            "value": float(A4_RAD_BUDGET),
            "source_jsonpath": "$.preregistration.constants.a4_rad_budget",
            "derivation": "pre-registered A4 planning budget",
        },
        "b_trim_rad": {
            "value": SCHEDULER_B_TRIM_RAD,
            "source_jsonpath": "$.preregistration.constants.b_trim_rad",
            "derivation": "pre-registered terminal trim band",
        },
        "coarse_raw_negative": {
            "value": float(negative["requested_u"]),
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_m2_T4.requested_u",
            "derivation": "measured raw command cell",
        },
        "coarse_raw_positive": {
            "value": float(positive["requested_u"]),
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_p2_T4.requested_u",
            "derivation": "measured raw command cell",
        },
        "coarse_rate_negative_rad_s": {
            "value": negative_rate,
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_m2_T4.summaries.command_window_yaw_rad.median",
            "derivation": "median realized command-window yaw divided by duration_s",
        },
        "coarse_rate_positive_rad_s": {
            "value": positive_rate,
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_p2_T4.summaries.command_window_yaw_rad.median",
            "derivation": "median realized command-window yaw divided by duration_s",
        },
        "coarse_stop_drift_negative_rad": {
            "value": negative_stop,
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_m2_T4.median_stop_drift_rad",
            "derivation": "measured median stop drift",
        },
        "coarse_stop_drift_positive_rad": {
            "value": positive_stop,
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_p2_T4.median_stop_drift_rad",
            "derivation": "measured median stop drift",
        },
        "minimum_settle_steps_negative": {
            "value": _last_above_plus_one(negative),
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_m2_T4.per_env[*].last_above_threshold_hold_index",
            "derivation": "worst-case last above-threshold hold index plus one full zero-command step",
        },
        "minimum_settle_steps_positive": {
            "value": _last_above_plus_one(positive),
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_p2_T4.per_env[*].last_above_threshold_hold_index",
            "derivation": "worst-case last above-threshold hold index plus one full zero-command step",
        },
        "settle_deadline_steps": {
            "value": hold_steps,
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_m2_T4.hold_steps",
            "derivation": "exact measured hold window",
        },
        "settle_velocity_threshold_rad_s": {
            "value": VELOCITY_SETTLE_THRESHOLD_RAD_S,
            "source_jsonpath": "$.preregistration.constants.velocity_settle_threshold_rad_s",
            "derivation": "pre-registered world-frame yaw-rate settle threshold",
        },
        "coarse_cutoff_negative_e_rad": {
            "value": SCHEDULER_COARSE_CUTOFF_NEGATIVE_E_RAD,
            "source_jsonpath": "$.preregistration.constants.coarse_cutoff_negative_e_rad",
            "derivation": "pre-registered negative aim-off boundary",
        },
        "coarse_cutoff_positive_e_rad": {
            "value": SCHEDULER_COARSE_CUTOFF_POSITIVE_E_RAD,
            "source_jsonpath": "$.preregistration.constants.coarse_cutoff_positive_e_rad",
            "derivation": "pre-registered positive aim-off boundary",
        },
        "trim_raw": {
            "value": float(trim["requested_u"]),
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_p0p05_T4.requested_u",
            "derivation": "measured raw trim command cell",
        },
        "trim_realized_rate_rad_s": {
            "value": trim_rate,
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_p0p05_T4.summaries.command_window_yaw_rad.median",
            "derivation": "median realized command-window yaw divided by duration_s",
        },
        "trim_one_step_rad": {
            "value": trim_one_step,
            "source_jsonpath": "$.scheduler_derived.constants.trim_realized_rate_rad_s.value",
            "derivation": "trim realized rate multiplied by $.scheduler_derived.constants.dt_s.value",
        },
        "trim_stop_drift_rad": {
            "value": trim_stop,
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_p0p05_T4.median_stop_drift_rad",
            "derivation": "measured median trim stop drift",
        },
        "trim_step_cap": {
            "value": SCHEDULER_TRIM_STEP_CAP,
            "source_jsonpath": "$.preregistration.constants.trim_step_cap",
            "derivation": "pre-registered bounded trim pulse count",
        },
        "terminal_hold_steps": {
            "value": hold_steps,
            "source_jsonpath": "$.a1_stop_profile.cells.pure_yaw_m2_T4.hold_steps",
            "derivation": "exact measured hold window",
        },
    }
    return {
        "schema": "a2_piper_pull_v5_4_scheduler_derived_v1",
        "frozen": True,
        "source": "validated Stage-A v5.3 traces and preregistration",
        "constants": constants,
    }


def analyze(
    *,
    trace_root: Path = TRACE_ROOT,
    output_path: Path | None = None,
) -> dict[str, Any]:
    # Reference artifacts are read before the trace science and remain
    # immutable inputs to this receipt.
    references = _validate_references()
    grid = _expected_grid()
    expected_ids = {cell["cell_id"] for cell in grid}
    trace_dirs = sorted(path for path in trace_root.glob("v5_3_char_*") if path.is_dir())
    if len(trace_dirs) != 44:
        raise ValueError(f"expected exactly 44 v5.3 trace directories; got {len(trace_dirs)}")
    discovered_ids = {path.name.removeprefix("v5_3_char_") for path in trace_dirs}
    if discovered_ids != expected_ids:
        raise ValueError(
            f"v5.3 trace grid mismatch; missing={sorted(expected_ids - discovered_ids)}, "
            f"extra={sorted(discovered_ids - expected_ids)}"
        )
    validated_traces: dict[str, dict[str, Any]] = {}
    for cell in grid:
        path = trace_root / f"v5_3_char_{cell['cell_id']}" / "characterization_trace.json"
        validated = _validate_trace(path, cell)
        validated_traces[cell["cell_id"]] = validated
    metrics = {
        cell_id: _derive_trace_metrics(validated)
        for cell_id, validated in validated_traces.items()
    }
    anchor_inputs: list[dict[str, Any]] = []
    for attempt, path in enumerate(ANCHOR_RECEIPTS, start=1):
        anchor_inputs.extend(_validate_anchor_receipt(path, attempt))
    if len(anchor_inputs) != 192:
        raise ValueError(f"expected exactly 192 v5.2 anchor measurements; got {len(anchor_inputs)}")
    pooled_correlation = _point_biserial(anchor_inputs)
    by_attempt_sequence: dict[str, Any] = {}
    for attempt in (1, 2, 3):
        for sequence in ("S1", "S2", "S3", "S4"):
            key = f"attempt{attempt}|{sequence}"
            subset = [
                row
                for row in anchor_inputs
                if row["attempt"] == attempt and row["sequence"] == sequence
            ]
            if len(subset) != 16:
                raise ValueError(f"{key} must contain 16 measurements; got {len(subset)}")
            by_attempt_sequence[key] = {
                "inputs": subset,
                "summary": _point_biserial(subset),
            }
    concentration_rule = {
        "preregistered": dict(A3_CONCENTRATION_RULE),
        "pooled": {
            "inputs": anchor_inputs,
            "summary": pooled_correlation,
        },
        "attempt_sequence": by_attempt_sequence,
    }
    concentration_passes = bool(pooled_correlation["rule_passes"])
    pure_metrics = [metric for metric in metrics.values() if metric["kind"] == "pure_yaw"]
    coupling_metrics = [metric for metric in metrics.values() if metric["kind"] == "coupling"]
    coupling_bias = {
        metric["cell_id"]: _coupling_bias(metrics, metric) for metric in coupling_metrics
    }
    candidates = [_a4_candidate(metric, concentration_passes) for metric in pure_metrics]
    selected, selection = _select_candidate(candidates)
    verdict = "GO" if selected is not None else "NO-GO"
    return {
        "schema": RECEIPT_SCHEMA,
        "version": 1,
        "record_class": "interface_characterization_stage_a",
        "stage": "A",
        "plan_id": "a2_piper_pull_v5_4_terminal_yaw_scheduler",
        "scientific_denominator_included": False,
        "verdict": verdict,
        "references": references,
        "data_counts": {
            "trace_count": len(validated_traces),
            "pure_trace_count": len(pure_metrics),
            "coupling_trace_count": len(coupling_metrics),
            "envs_per_trace": ENV_COUNT,
            "env_trajectories": len(validated_traces) * ENV_COUNT,
            "trace_row_count": sum(item["row_count"] for item in validated_traces.values()),
            "anchor_receipt_count": len(ANCHOR_RECEIPTS),
            "anchor_measurements": len(anchor_inputs),
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "control_dt_s": CONTROL_DT_S,
        },
        "schema_validation": {
            "trace_schema": TRACE_SCHEMA,
            "trace_rows_env_major_contiguous": True,
            "trace_terminal_after_step_used_for_science": False,
            "trace_terminal_after_step_semantics": "ignored_stale_field",
            "accepted_trace_record_class": "interface_characterization",
            "accepted_anchor_record_class": "v5.2 natural anchor measurements",
        },
        "preregistration": {
            "constants": {
                "velocity_settle_threshold_rad_s": VELOCITY_SETTLE_THRESHOLD_RAD_S,
                "a4_rad_budget": A4_RAD_BUDGET,
                "max_settle_s": MAX_SETTLE_S,
                "xy_direct_bound_m": XY_DIRECT_BOUND_M,
                "yaw_threshold_rad": YAW_THRESHOLD_RAD,
                "hold_s": HOLD_S,
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "control_dt_s": CONTROL_DT_S,
                "b_trim_rad": SCHEDULER_B_TRIM_RAD,
                "coarse_cutoff_negative_e_rad": SCHEDULER_COARSE_CUTOFF_NEGATIVE_E_RAD,
                "coarse_cutoff_positive_e_rad": SCHEDULER_COARSE_CUTOFF_POSITIVE_E_RAD,
                "trim_step_cap": SCHEDULER_TRIM_STEP_CAP,
            },
            "a3_concentration_rule": dict(A3_CONCENTRATION_RULE),
        },
        "a1_stop_profile": {
            "convention": (
                "For each pure cell/env, cutoff is the last command-phase post-yaw. "
                "stop drift is wrapped(final hold post-yaw - cutoff post-yaw). "
                "Settle time is measured from cutoff through the end of the last "
                "hold sample with abs(yaw_velocity_rad_s)>0.05; if none, it is 0. "
                "Residual drift is wrapped(final hold post-yaw minus the post-yaw "
                "immediately after that last above-threshold sample, or cutoff yaw "
                "when no such sample exists)."
            ),
            "cells": {metric["cell_id"]: metric for metric in pure_metrics},
        },
        "a2_hold_stability": {
            "convention": (
                "For each pure cell/env, A2 is the maximum absolute wrapped yaw "
                "difference from final hold post-yaw over the last 1.0 s; the "
                "last-hold velocity is reported separately. For u=-2,T1/T2/T4, "
                "finite_transient is allowed only when every env last-hold abs "
                "velocity is <=0.05 rad/s; otherwise the classification is "
                "continuing_rate."
            ),
            "cells": {
                metric["cell_id"]: {
                    "requested_u": metric["requested_u"],
                    "duration_s": metric["duration_s"],
                    "per_env_last_1s_max_abs_wrapped_rad": metric["arrays"][
                        "a2_last_1s_max_abs_wrapped_rad"
                    ],
                    "last_hold_velocity_rad_s": metric["arrays"][
                        "last_hold_yaw_velocity_rad_s"
                    ],
                    "summary_last_1s_max_abs_wrapped_rad": metric["summaries"][
                        "a2_last_1s_max_abs_wrapped_rad"
                    ],
                    "summary_last_hold_velocity_rad_s": metric["summaries"][
                        "last_hold_yaw_velocity_rad_s"
                    ],
                    "classification": (
                        (
                            "finite_transient"
                            if all(
                                abs(value) <= VELOCITY_SETTLE_THRESHOLD_RAD_S
                                for value in metric["arrays"]["last_hold_yaw_velocity_rad_s"]
                            )
                            else "continuing_rate"
                        )
                        if math.isclose(float(metric["requested_u"]), -2.0, abs_tol=1.0e-12)
                        and metric["duration_s"] in PURE_YAW_DURATIONS_S
                        else "not_applicable"
                    ),
                }
                for metric in pure_metrics
            },
        },
        "a3_xy_and_coupling": {
            "pure_hold_xy_convention": (
                "Hold XY is the vector sum of root_motion_xy_world over the zero-command "
                "hold; per-env norm and the per-cell worst norm are reported."
            ),
            "pure_hold_xy": {
                metric["cell_id"]: {
                    "requested_u": metric["requested_u"],
                    "duration_s": metric["duration_s"],
                    "per_env_vector_m": metric["arrays"]["hold_xy_vector_m"],
                    "per_env_norm_m": metric["arrays"]["hold_xy_norm_m"],
                    "summary_norm_m": metric["summaries"]["hold_xy_norm_m"],
                    "max_norm_m": metric["max_hold_xy_m"],
                }
                for metric in pure_metrics
            },
            "coupling_command_window_yaw_bias": coupling_bias,
            "waypoint_miss_yaw_concentration": concentration_rule,
        },
        "a4_candidates": {
            "rule": {
                "candidate_scope": "every pure-yaw cell",
                "selection_positive_direction": (
                    "positive means requested raw command u > 0; realized command-window "
                    "yaw sign is reported separately and is not substituted for raw sign"
                ),
                "condition_i": "dispersion + A2 stability <= 0.10 rad",
                "condition_ii": "max settle time <= 2.0 s",
                "condition_iii": "max hold XY <= 0.03 m OR A3 concentration rule true",
                "go": "at least one candidate passes all three conditions",
            },
            "candidates": candidates,
            "passing_candidates": [candidate for candidate in candidates if candidate["passes"]],
            "selection": selection,
            "selected_candidate": selected,
            "verdict": verdict,
        },
        "scheduler_derived": _scheduler_derived_block(metrics),
        "next_gate": (
            {
                "stage_b_rehearsal": "PERMITTED",
                "stage_c_anchor": "BLOCKED_UNTIL_STAGE_B_REHEARSAL_PASS",
                "residual_precommit": "not_activated_by_stage_a",
            }
            if verdict == "GO"
            else {
                "stage_b_rehearsal": "BLOCKED",
                "stage_c_anchor": "BLOCKED",
                "residual_precommit": "activated_by_stage_a_no_go",
            }
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-root", type=Path, default=TRACE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    trace_root = args.trace_root.resolve()
    output_path = args.output.resolve()
    receipt = analyze(trace_root=trace_root, output_path=output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "schema": receipt["schema"],
        "verdict": receipt["verdict"],
        "selected_candidate": receipt["a4_candidates"]["selected_candidate"],
        "trace_count": receipt["data_counts"]["trace_count"],
        "env_trajectories": receipt["data_counts"]["env_trajectories"],
        "anchor_measurements": receipt["data_counts"]["anchor_measurements"],
        "output": str(output_path),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
