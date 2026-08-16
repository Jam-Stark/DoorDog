#!/usr/bin/env python3
"""Materialize and run the preregistered v5.3 HOMIE yaw characterization grid.

Every cell is an open-field, first-episode evaluator run.  The evaluator writes
its own versioned ``interface_characterization`` trace; those rows are not
anchor, door, or P3 scientific denominator records.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
CHECKPOINT = ROOT / (
    "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v4_B_wave1_seed1/model_step_000750.pt"
)
OUTPUT_ROOT = ROOT / "logs_eval/a2_piper_pull_v5"
ALLOWED_GPUS = (4, 5, 6, 7)
ENV_COUNT = 8
HOLD_S = 2.0
PURE_YAW_MAGNITUDES = (0.05, 0.1, 0.2, 0.4, 0.8, 2.0)
PURE_YAW_DURATIONS_S = (1.0, 2.0, 4.0)
COUPLING_MAGNITUDES = (0.2, 0.8)
COUPLING_PRIMITIVES = ("straight_minus_x", "side_step")
RAW_YAW_LIMIT = 2.0
CONTROL_DT_S = 0.02
BASE_MAX_STAGE_TIME = (250, 100, 100, 100, 250, 300)
TRACE_SCHEMA = "a2_piper_pull_v5_interface_characterization_trace_v1"
RECEIPT_SCHEMA = "a2_piper_pull_v5_3_interface_characterization_receipt_v1"
PLAN_ID = "a2_piper_pull_v5_3_locomotion_interface_probe"
RECEIPT_FILENAME = "v5_3_interface_characterization_receipt.json"


def _token(value: float) -> str:
    text = f"{abs(value):g}".replace(".", "p")
    return ("p" if value >= 0.0 else "m") + text


def _cell_id(kind: str, requested_u: float, duration_s: float, primitive: str) -> str:
    if kind == "pure_yaw":
        return f"pure_yaw_{_token(requested_u)}_T{duration_s:g}".replace(".", "p")
    return f"coupling_{primitive}_{_token(requested_u)}_T{duration_s:g}".replace(".", "p")


def materialize_grid() -> tuple[dict[str, object], ...]:
    cells: list[dict[str, object]] = []
    for magnitude in PURE_YAW_MAGNITUDES:
        for sign in (-1.0, 1.0):
            requested_u = sign * magnitude
            for duration_s in PURE_YAW_DURATIONS_S:
                cells.append(
                    {
                        "kind": "pure_yaw",
                        "cell_id": _cell_id("pure_yaw", requested_u, duration_s, "none"),
                        "requested_u": requested_u,
                        "duration_s": duration_s,
                        "hold_s": HOLD_S,
                        "xy_primitive": "none",
                        "env_count": ENV_COUNT,
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
                        "env_count": ENV_COUNT,
                    }
                )
    return tuple(cells)


def _validate_grid(cells: tuple[dict[str, object], ...]) -> None:
    pure = [cell for cell in cells if cell["kind"] == "pure_yaw"]
    coupling = [cell for cell in cells if cell["kind"] == "coupling"]
    if len(cells) != 44 or len(pure) != 36 or len(coupling) != 8:
        raise AssertionError(
            f"v5.3 grid must contain 44 cells (36 pure + 8 coupling); got {len(cells)}"
        )
    if len({cell["cell_id"] for cell in cells}) != len(cells):
        raise AssertionError("v5.3 characterization cell IDs must be unique")
    for cell in cells:
        requested_u = float(cell["requested_u"])
        if abs(requested_u) > RAW_YAW_LIMIT:
            raise AssertionError(f"raw yaw request exceeds registered limit: {cell}")
        if float(cell["hold_s"]) < 2.0:
            raise AssertionError(f"zero-hold segment is shorter than 2s: {cell}")
        if int(cell["env_count"]) != ENV_COUNT:
            raise AssertionError(f"cell env count must be {ENV_COUNT}: {cell}")
        if cell["kind"] == "pure_yaw":
            if cell["xy_primitive"] != "none":
                raise AssertionError(f"pure-yaw cell has XY mechanics: {cell}")
            if float(cell["duration_s"]) not in PURE_YAW_DURATIONS_S:
                raise AssertionError(f"pure-yaw duration is not preregistered: {cell}")
        else:
            if float(cell["duration_s"]) != 2.0:
                raise AssertionError(f"coupling duration must be 2s: {cell}")
            if abs(requested_u) not in COUPLING_MAGNITUDES:
                raise AssertionError(f"coupling |u| is not preregistered: {cell}")
            if cell["xy_primitive"] not in COUPLING_PRIMITIVES:
                raise AssertionError(f"coupling primitive is not registered: {cell}")
    for duration_s, expected_steps, expected_episode_s in (
        (1.0, 150, 3.0),
        (2.0, 200, 4.0),
        (4.0, 300, 6.0),
    ):
        representative = next(
            cell for cell in cells if float(cell["duration_s"]) == duration_s
        )
        horizon = _characterization_horizon(representative)
        if (
            horizon["window_steps"] != expected_steps
            or horizon["episode_horizon_s"] != expected_episode_s
            or horizon["stage_time"][1:] != BASE_MAX_STAGE_TIME[1:]
        ):
            raise AssertionError(
                f"characterization horizon mismatch for T{duration_s:g}: {horizon}"
            )


def _characterization_horizon(cell: dict[str, object]) -> dict[str, object]:
    command_steps = max(1, math.ceil(float(cell["duration_s"]) / CONTROL_DT_S))
    hold_steps = max(1, math.ceil(float(cell["hold_s"]) / CONTROL_DT_S))
    window_steps = command_steps + hold_steps
    episode_horizon_s = float(cell["duration_s"]) + float(cell["hold_s"])
    stage_time = (window_steps, *BASE_MAX_STAGE_TIME[1:])
    return {
        "command_steps": command_steps,
        "hold_steps": hold_steps,
        "window_steps": window_steps,
        "episode_horizon_s": episode_horizon_s,
        "stage_time": stage_time,
    }


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number; got {value!r}")
    return result


def _exact_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer; got {value!r}")
    return int(value)


def _finite_vector(value: object, length: int, field: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f"{field} must contain exactly {length} values; got {value!r}")
    return [_finite_float(item, f"{field}[{index}]") for index, item in enumerate(value)]


def _wrapped_yaw(value: float) -> float:
    return math.remainder(float(value), 2.0 * math.pi)


def _validate_trace_payload(
    *,
    cell: dict[str, object],
    trace_path: Path,
    payload: object,
) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError(f"characterization trace must be a JSON object: {trace_path}")
    expected_top_level = {
        "schema": TRACE_SCHEMA,
        "record_class": "interface_characterization",
        "cell_id": cell["cell_id"],
        "fixture": "open_field",
        "plan_id": PLAN_ID,
        "num_envs": ENV_COUNT,
        "first_episode_only": True,
        "scientific_denominator_included": False,
        "denominator_scope": "none",
    }
    for field, expected in expected_top_level.items():
        if payload.get(field) != expected:
            raise ValueError(
                f"{trace_path} field {field!r} must equal {expected!r}; "
                f"got {payload.get(field)!r}"
            )

    command_steps = _exact_int(payload.get("command_steps"), "command_steps")
    hold_steps = _exact_int(payload.get("hold_steps"), "hold_steps")
    window_steps = _exact_int(payload.get("window_steps"), "window_steps")
    if command_steps <= 0 or hold_steps <= 0 or window_steps != command_steps + hold_steps:
        raise ValueError(
            f"{trace_path} has invalid command/hold/window steps: "
            f"{command_steps}, {hold_steps}, {window_steps}"
        )
    duration_s = _finite_float(payload.get("duration_s"), "duration_s")
    hold_s = _finite_float(payload.get("hold_s"), "hold_s")
    requested_u = _finite_float(payload.get("requested_u"), "requested_u")
    control_dt = _finite_float(payload.get("control_dt"), "control_dt")
    if control_dt <= 0.0:
        raise ValueError(f"{trace_path} control_dt must be positive")
    for field, expected in (
        ("duration_s", float(cell["duration_s"])),
        ("hold_s", float(cell["hold_s"])),
        ("requested_u", float(cell["requested_u"])),
    ):
        actual = _finite_float(payload.get(field), field)
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1.0e-9):
            raise ValueError(
                f"{trace_path} {field} disagrees with grid cell: expected {expected}, got {actual}"
            )
    if payload.get("xy_primitive") != cell["xy_primitive"]:
        raise ValueError(
            f"{trace_path} xy_primitive disagrees with grid cell: "
            f"expected {cell['xy_primitive']!r}, got {payload.get('xy_primitive')!r}"
        )

    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != ENV_COUNT * window_steps:
        raise ValueError(
            f"{trace_path} must contain exactly {ENV_COUNT * window_steps} rows; "
            f"got {None if not isinstance(rows, list) else len(rows)}"
        )
    by_env: dict[int, list[dict[str, object]]] = {env_id: [] for env_id in range(ENV_COUNT)}
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{trace_path} row {row_index} must be a JSON object")
        if row.get("schema") != TRACE_SCHEMA or row.get("record_class") != "interface_characterization":
            raise ValueError(f"{trace_path} row {row_index} has an invalid schema/record_class")
        if row.get("cell_id") != cell["cell_id"] or row.get("fixture") != "open_field":
            raise ValueError(f"{trace_path} row {row_index} has an invalid cell or fixture")
        env_id = _exact_int(row.get("env_id"), f"row[{row_index}].env_id")
        if env_id not in by_env:
            raise ValueError(f"{trace_path} row {row_index} has invalid env_id={env_id}")
        if _exact_int(row.get("episode_index"), f"row[{row_index}].episode_index") != 0:
            raise ValueError(f"{trace_path} row {row_index} is not first-episode data")
        expected_episode_id = f"{cell['cell_id']}:env{env_id}:episode0"
        if row.get("episode_id") != expected_episode_id:
            raise ValueError(f"{trace_path} row {row_index} has invalid episode_id")
        step_index = _exact_int(row.get("step_index"), f"row[{row_index}].step_index")
        if step_index < 0 or step_index >= window_steps:
            raise ValueError(f"{trace_path} row {row_index} has invalid step_index={step_index}")
        expected_command = step_index < command_steps
        if row.get("command_phase") is not expected_command:
            raise ValueError(f"{trace_path} row {row_index} has an invalid command_phase flag")
        if row.get("zero_hold_phase") is not (not expected_command):
            raise ValueError(f"{trace_path} row {row_index} has an invalid zero_hold_phase flag")
        expected_phase = "command" if expected_command else "zero_hold"
        if row.get("phase") != expected_phase:
            raise ValueError(f"{trace_path} row {row_index} has invalid phase={row.get('phase')!r}")
        row_requested_u = _finite_float(row.get("requested_u"), f"row[{row_index}].requested_u")
        expected_row_u = requested_u if expected_command else 0.0
        if not math.isclose(row_requested_u, expected_row_u, rel_tol=0.0, abs_tol=1.0e-6):
            raise ValueError(f"{trace_path} row {row_index} has an invalid requested_u")
        row_cell_u = _finite_float(row.get("cell_requested_u"), f"row[{row_index}].cell_requested_u")
        if not math.isclose(row_cell_u, requested_u, rel_tol=0.0, abs_tol=1.0e-6):
            raise ValueError(f"{trace_path} row {row_index} has an invalid cell_requested_u")
        if row.get("xy_primitive") != cell["xy_primitive"]:
            raise ValueError(f"{trace_path} row {row_index} has an invalid xy_primitive")
        raw_base = _finite_vector(row.get("applied_raw_base_slice"), 5, f"row[{row_index}].applied_raw_base_slice")
        if not math.isclose(raw_base[2], row_requested_u, rel_tol=0.0, abs_tol=1.0e-6):
            raise ValueError(f"{trace_path} row {row_index} is not auditable at raw yaw index 2")
        _finite_vector(
            row.get("scaled_clipped_physical_base_command"),
            5,
            f"row[{row_index}].scaled_clipped_physical_base_command",
        )
        _finite_float(row.get("realized_world_yaw_pre"), f"row[{row_index}].realized_world_yaw_pre")
        _finite_float(row.get("realized_world_yaw_post"), f"row[{row_index}].realized_world_yaw_post")
        _finite_float(row.get("yaw_delta_rad"), f"row[{row_index}].yaw_delta_rad")
        _finite_float(row.get("yaw_velocity_rad_s"), f"row[{row_index}].yaw_velocity_rad_s")
        _finite_vector(row.get("root_pos_pre_world"), 3, f"row[{row_index}].root_pos_pre_world")
        _finite_vector(row.get("root_pos_post_world"), 3, f"row[{row_index}].root_pos_post_world")
        _finite_vector(row.get("root_motion_xy_world"), 2, f"row[{row_index}].root_motion_xy_world")
        if _finite_float(row.get("root_motion_m"), f"row[{row_index}].root_motion_m") < 0.0:
            raise ValueError(f"{trace_path} row {row_index} has negative root_motion_m")
        _finite_float(row.get("control_dt"), f"row[{row_index}].control_dt")
        if not math.isclose(
            _finite_float(row.get("control_dt"), f"row[{row_index}].control_dt"),
            control_dt,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError(f"{trace_path} row {row_index} control_dt disagrees with trace metadata")
        if not isinstance(row.get("terminal_after_step"), bool):
            raise ValueError(f"{trace_path} row {row_index} terminal_after_step must be bool")
        by_env[env_id].append(row)

    for env_id, env_rows in by_env.items():
        env_rows.sort(key=lambda row: _exact_int(row["step_index"], f"env{env_id}.step_index"))
        steps = [_exact_int(row["step_index"], f"env{env_id}.step_index") for row in env_rows]
        if steps != list(range(window_steps)):
            raise ValueError(f"{trace_path} env{env_id} does not have a complete contiguous window")
    return {
        "schema": TRACE_SCHEMA,
        "command_steps": command_steps,
        "hold_steps": hold_steps,
        "window_steps": window_steps,
        "duration_s": duration_s,
        "hold_s": hold_s,
        "requested_u": requested_u,
        "control_dt": control_dt,
        "rows_by_env": by_env,
        "row_count": len(rows),
    }


def _derive_env_evidence(
    *,
    requested_u: float,
    env_id: int,
    rows: list[dict[str, object]],
    command_steps: int,
) -> dict[str, object]:
    command_rows = rows[:command_steps]
    hold_rows = rows[command_steps:]
    command_duration_s = sum(_finite_float(row["control_dt"], "control_dt") for row in command_rows)
    hold_duration_s = sum(_finite_float(row["control_dt"], "control_dt") for row in hold_rows)
    command_yaw = _wrapped_yaw(
        _finite_float(command_rows[-1]["realized_world_yaw_post"], "realized_world_yaw_post")
        - _finite_float(command_rows[0]["realized_world_yaw_pre"], "realized_world_yaw_pre")
    )
    hold_yaw = _wrapped_yaw(
        _finite_float(hold_rows[-1]["realized_world_yaw_post"], "realized_world_yaw_post")
        - _finite_float(hold_rows[0]["realized_world_yaw_pre"], "realized_world_yaw_pre")
    )
    full_yaw = _wrapped_yaw(
        _finite_float(hold_rows[-1]["realized_world_yaw_post"], "realized_world_yaw_post")
        - _finite_float(command_rows[0]["realized_world_yaw_pre"], "realized_world_yaw_pre")
    )
    command_rate = command_yaw / command_duration_s
    if requested_u == 0.0:
        raise ValueError("characterization grid does not permit zero requested_u")
    response_index = next(
        (
            index
            for index, row in enumerate(command_rows)
            if abs(_finite_float(row["yaw_delta_rad"], "yaw_delta_rad")) > 0.0
        ),
        None,
    )
    response_latency_s = (
        None
        if response_index is None
        else sum(
            _finite_float(row["control_dt"], "control_dt")
            for row in command_rows[: response_index + 1]
        )
    )

    def sum_xy(source_rows: list[dict[str, object]]) -> list[float]:
        return [
            sum(_finite_float(row["root_motion_xy_world"][axis], "root_motion_xy_world") for row in source_rows)
            for axis in range(2)
        ]

    command_xy = sum_xy(command_rows)
    hold_xy = sum_xy(hold_rows)
    full_xy = [command_xy[axis] + hold_xy[axis] for axis in range(2)]

    def norm(vector: list[float]) -> float:
        return math.hypot(vector[0], vector[1])

    return {
        "env_id": env_id,
        "episode_index": 0,
        "signed_wrapped_yaw_displacement_rad": command_yaw,
        "command_window_signed_wrapped_yaw_displacement_rad": command_yaw,
        "full_window_signed_wrapped_yaw_displacement_rad": full_yaw,
        "command_window_yaw_rate_rad_s": command_rate,
        "command_window_yaw_gain_rad_s_per_raw_u": command_rate / requested_u,
        "response_latency_s": response_latency_s,
        "response_observed": response_latency_s is not None,
        "hold_window_drift_rad": hold_yaw,
        "hold_window_drift_rate_rad_s": hold_yaw / hold_duration_s,
        "command_planar_displacement_xy_m": command_xy,
        "command_planar_displacement_m": norm(command_xy),
        "hold_planar_displacement_xy_m": hold_xy,
        "hold_planar_displacement_m": norm(hold_xy),
        "planar_displacement_xy_m": full_xy,
        "planar_displacement_m": norm(full_xy),
        "command_duration_s": command_duration_s,
        "hold_duration_s": hold_duration_s,
    }


def _aggregate_scalar(per_env: list[dict[str, object]], field: str) -> dict[str, object]:
    values = [
        float(item[field])
        for item in per_env
        if item[field] is not None
    ]
    if not values:
        return {"mean": None, "min": None, "max": None, "observed_env_count": 0}
    return {
        "mean": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
        "observed_env_count": len(values),
    }


def _aggregate_vector(per_env: list[dict[str, object]], field: str) -> dict[str, object]:
    values = [item[field] for item in per_env]
    return {
        "mean": [sum(value[axis] for value in values) / len(values) for axis in range(2)],
        "min": [min(value[axis] for value in values) for axis in range(2)],
        "max": [max(value[axis] for value in values) for axis in range(2)],
        "observed_env_count": len(values),
    }


def _derive_aggregate_evidence(per_env: list[dict[str, object]]) -> dict[str, object]:
    scalar_fields = (
        "signed_wrapped_yaw_displacement_rad",
        "command_window_signed_wrapped_yaw_displacement_rad",
        "full_window_signed_wrapped_yaw_displacement_rad",
        "command_window_yaw_rate_rad_s",
        "command_window_yaw_gain_rad_s_per_raw_u",
        "response_latency_s",
        "hold_window_drift_rad",
        "hold_window_drift_rate_rad_s",
        "command_planar_displacement_m",
        "hold_planar_displacement_m",
        "planar_displacement_m",
        "command_duration_s",
        "hold_duration_s",
    )
    aggregate = {field: _aggregate_scalar(per_env, field) for field in scalar_fields}
    aggregate["command_planar_displacement_xy_m"] = _aggregate_vector(
        per_env, "command_planar_displacement_xy_m"
    )
    aggregate["hold_planar_displacement_xy_m"] = _aggregate_vector(
        per_env, "hold_planar_displacement_xy_m"
    )
    aggregate["planar_displacement_xy_m"] = _aggregate_vector(
        per_env, "planar_displacement_xy_m"
    )
    aggregate["env_count"] = len(per_env)
    aggregate["response_observed_env_count"] = sum(
        1 for item in per_env if item["response_observed"]
    )
    return aggregate


def _load_cell_evidence(cell: dict[str, object], cell_dir: Path) -> dict[str, object]:
    trace_path = (cell_dir / "characterization_trace.json").resolve()
    if not trace_path.is_file():
        raise FileNotFoundError(f"v5.3 characterization trace is missing: {trace_path}")
    with trace_path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    validated = _validate_trace_payload(cell=cell, trace_path=trace_path, payload=payload)
    rows_by_env = validated["rows_by_env"]
    per_env = [
        _derive_env_evidence(
            requested_u=float(cell["requested_u"]),
            env_id=env_id,
            rows=rows_by_env[env_id],
            command_steps=int(validated["command_steps"]),
        )
        for env_id in range(ENV_COUNT)
    ]
    return {
        "cell_id": cell["cell_id"],
        "kind": cell["kind"],
        "requested_u": float(cell["requested_u"]),
        "requested_raw_u": float(cell["requested_u"]),
        "duration_s": float(cell["duration_s"]),
        "hold_s": float(cell["hold_s"]),
        "coupling_mode": "none" if cell["xy_primitive"] == "none" else cell["xy_primitive"],
        "xy_primitive": cell["xy_primitive"],
        "source_trace": {
            "path": str(trace_path),
            "schema": validated["schema"],
            "row_count": validated["row_count"],
            "preserved": True,
        },
        "trace_path": str(trace_path),
        "command_steps": validated["command_steps"],
        "hold_steps": validated["hold_steps"],
        "window_steps": validated["window_steps"],
        "control_dt": validated["control_dt"],
        "per_env": per_env,
        "aggregate": _derive_aggregate_evidence(per_env),
    }


def build_aggregate_receipt(
    *,
    cells: tuple[dict[str, object], ...],
    output_root: Path,
) -> tuple[Path, dict[str, object]]:
    _validate_grid(cells)
    receipt_path = (output_root / RECEIPT_FILENAME).resolve()
    if receipt_path.exists():
        raise FileExistsError(f"v5.3 aggregate receipt refuses existing path: {receipt_path}")
    cell_evidence = [
        _load_cell_evidence(cell, output_root / f"v5_3_char_{cell['cell_id']}")
        for cell in cells
    ]
    payload = {
        "schema": RECEIPT_SCHEMA,
        "record_class": "interface_characterization",
        "version": 1,
        "plan_id": PLAN_ID,
        "fixture": "open_field",
        "scientific_denominator_included": False,
        "denominator_scope": "none",
        "env_count": ENV_COUNT,
        "cell_count": len(cell_evidence),
        "completed_cells": len(cell_evidence),
        "source_trace_preserved": True,
        "receipt_writer": "run_pull_v5_interface_characterization.py",
        "cells": cell_evidence,
    }
    return receipt_path, payload


def build_command(
    *,
    cell: dict[str, object],
    checkpoint: Path,
    gpu: int,
    output_dir: Path,
    allow_missing_checkpoint: bool = False,
) -> tuple[list[str], dict[str, str]]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"v5.3 characterization only permits GPU4-7; got GPU{gpu}")
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    output_dir = output_dir.resolve()
    if not output_dir.is_relative_to(ROOT.resolve()):
        raise ValueError(f"v5.3 characterization output must remain inside repository: {output_dir}")
    trace_path = output_dir / "characterization_trace.json"
    command = [
        str(PYTHON),
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        f"num_envs={ENV_COUNT}",
        "seed=0",
        "headless=true",
        "use_wandb=false",
        "+ablation=wbmanip/pull_v5_M_s0",
        "algo.config.load_optimizer=false",
        "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=false",
        "algo.config.eval.save_videos=false",
        f"algo.config.eval.num_save_episodes={ENV_COUNT}",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=false",
        "env.config.a2_pull_v5_stage4_bank_injection_ratio=0.0",
        "env.config.a2_pull_v5_reset_source=natural",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_intervention_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        "env.config.a2_pull_v5_state_bank_allow_g8_pure_a=false",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/{cell['cell_id']}.json",
        "+env.config.a2_pull_v5_probe_enabled=false",
        "+env.config.a2_pull_v5_characterization_enabled=true",
        f"+env.config.a2_pull_v5_characterization_plan_id={PLAN_ID}",
        "+env.config.a2_pull_v5_characterization_fixture=open_field",
        f"+env.config.a2_pull_v5_characterization_cell_id={cell['cell_id']}",
        f"+env.config.a2_pull_v5_characterization_requested_u={float(cell['requested_u']):g}",
        f"+env.config.a2_pull_v5_characterization_duration_s={float(cell['duration_s']):g}",
        f"+env.config.a2_pull_v5_characterization_hold_s={float(cell['hold_s']):g}",
        f"+env.config.a2_pull_v5_characterization_xy_primitive={cell['xy_primitive']}",
        f"+env.config.a2_pull_v5_characterization_trace_path={trace_path}",
        "env.config.a2_pull_v5_start_override_enabled=false",
        "env.config.a2_pull_v5_start_override_steps=50",
        "+algo.config.eval.a2_pull_p2_intervention_enabled=false",
        f"eval_output_dir={output_dir / 'eval'}",
        f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}",
        "+device=cuda:0",
    ]
    return command, {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "WANDB_MODE": "offline",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    cells = materialize_grid()
    _validate_grid(cells)
    checkpoint = args.checkpoint.resolve()
    output_root = args.output_root.resolve()
    if not output_root.is_relative_to(ROOT.resolve()):
        raise ValueError(f"v5.3 characterization output root must remain inside repository: {output_root}")
    commands: list[tuple[dict[str, object], Path, list[str], dict[str, str]]] = []
    for cell in cells:
        cell_dir = output_root / f"v5_3_char_{cell['cell_id']}"
        command, process_env = build_command(
            cell=cell,
            checkpoint=checkpoint,
            gpu=args.gpu,
            output_dir=cell_dir,
            allow_missing_checkpoint=args.dry_run,
        )
        commands.append((cell, cell_dir, command, process_env))
    if any(
        any(
            token.startswith("env.config.max_stage_time=")
            or token.startswith("env.config.max_episode_length_s=")
            for token in command
        )
        for _, _, command, _ in commands
    ):
        raise AssertionError("v5.3 characterization command must preserve frozen horizon config")

    print(
        json.dumps(
            {
                "schema": "a2_piper_pull_v5_3_interface_characterization_grid_v1",
                "pure_yaw_cells": 36,
                "coupling_cells": 8,
                "total_cells": len(cells),
                "envs_per_cell": ENV_COUNT,
                "hold_s": HOLD_S,
                "output_prefix": "v5_3_char_",
                "trace_record_class": "interface_characterization",
                "scientific_denominator_included": False,
                "control_dt_s": CONTROL_DT_S,
                "frozen_max_episode_length_s": 24.0,
                "frozen_max_stage_time": list(BASE_MAX_STAGE_TIME),
                "horizon_examples": {
                    f"T{duration_s:g}": _characterization_horizon(
                        next(cell for cell in cells if float(cell["duration_s"]) == duration_s)
                    )
                    for duration_s in PURE_YAW_DURATIONS_S
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("[v5.3 T0] representative command:", " ".join(commands[0][2]))
    print("[v5.3 T0] grid contract assertions: PASS")
    if not args.run:
        return 0
    if args.dry_run:
        parser.error("--dry-run and --run are mutually exclusive")

    receipt_path = (output_root / RECEIPT_FILENAME).resolve()
    if receipt_path.exists():
        raise FileExistsError(f"v5.3 aggregate receipt refuses existing path: {receipt_path}")
    for cell, cell_dir, command, process_env in commands:
        if cell_dir.exists():
            raise FileExistsError(f"v5.3 characterization refuses existing cell output: {cell_dir}")
        cell_dir.mkdir(parents=True, exist_ok=False)
        run_env = os.environ.copy()
        run_env.update(process_env)
        with (cell_dir / "runner.log").open("x", encoding="utf-8") as stream:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=run_env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if result.returncode != 0:
            return result.returncode
        _load_cell_evidence(cell, cell_dir)
    receipt_path, receipt_payload = build_aggregate_receipt(
        cells=cells,
        output_root=output_root,
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt_payload, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"[v5.3 T0] completed {len(commands)} characterization cells")
    print(f"[v5.3 T0] wrote aggregate receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
