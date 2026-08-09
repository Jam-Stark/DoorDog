"""v23 P0.4 high-level IsaacLab door dynamics producer.

The probe builds one deterministic door articulation per A0--A8 atlas cell,
resolves the hinge by its joint name, and records free-return and fixed-effort
responses from the public IsaacLab articulation interface.  It is intentionally
door-only: no robot, policy, controller, evaluator, or scientific E-zone label
is created here.  A3 is a ``FRICTION_PROXY`` cell because the registered door
spawner has no independent Coulomb/stiction control; its proxy is a near-closed
start together with high hinge stiffness and max force.

Implicit-actuator torque fields are actuator-model estimates only: PhysX does
not expose actual drive-force readback.  Their authority is recorded as
``ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE``.  Position tracking uses
the v21B contract ``joint_pos_target - joint_pos`` and keeps joint velocity as
context.

``--plan-only`` emits the same top-level ``rows`` shape without importing or
starting IsaacLab.  A measured run requires an explicit device and output path.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
import traceback
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        V23_D0_SOURCE_CONFIG,
        V23_EFFORT_RUNGS,
        V23Error,
        artifact_payload,
        emit_payload,
        finite_number,
    )
    from .characterize_hinge_dynamics import ATLAS_BOUNDS, ATLAS_CELLS
except ImportError:  # direct ``python scriptsFORhuman/v23/...py`` invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        V23_D0_SOURCE_CONFIG,
        V23_EFFORT_RUNGS,
        V23Error,
        artifact_payload,
        emit_payload,
        finite_number,
    )
    from scriptsFORhuman.v23.characterize_hinge_dynamics import ATLAS_BOUNDS, ATLAS_CELLS


SIM_DT = 0.005
FREE_RETURN_STEPS = 2400
FIXED_EFFORT_STEPS = 600
TRAJECTORY_STRIDE = 40
FREE_RETURN_MARKS_RAD = (0.90, 0.60, 0.30)
TORQUE_AUTHORITY = "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE"
EXTERNAL_WRENCH_AUTHORITY = "MEASURED_EXTERNAL_GLOBAL_TORQUE_HIGH_LEVEL_WRENCH_COMPOSER"
EXTERNAL_TORQUE_MAGNITUDES_NM = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 60.0, 100.0)
DIRECTIONAL_OPENING_BRACKET_SCHEMA = "a2_piper_v23_directional_opening_bracket_v1"
DIRECTIONAL_OPENING_CONTRACT = {
    "torque_sign": 1,
    "hinge_coordinate": "POSITIVE_OPENING",
    "basis": "TORQUE_SIGN_TIMES_RESOLVED_HINGE_AXIS; TASK_OPENING_IS_POSITIVE_HINGE_POSITION",
}
CANONICAL_GEOMETRY_SCHEMA = "a2_piper_v23_canonical_geometry_v1"
CANONICAL_GEOMETRY_FACTS = {
    "door_width_m": 0.95,
    "door_height_m": 2.05,
    "handle_height_m": 0.975,
    "handle_width_m": 0.12,
    "handle_type": "lever",
    "door_open_lr": "right",
    "door_open_io": "out",
    "door_open_lr_sign": -1,
    "door_open_io_sign": -1,
    "hinge_axis_local": [0.0, 0.0, 1.0],
    "hinge_anchor_local": [0.02, 0.475, 0.0],
}

SOURCE_IDENTITY = {
    "probe": "scriptsFORhuman/v23/p0_door_atlas_probe.py",
    "scenario_config": "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py:TaskObjCfgDict",
    "door_spawner": "gr00t/rl/isaac_utils/playground/env_rand/door.py:DoorSpawnerCfg",
    "high_level_runtime_api": {
        "launcher": "isaaclab.app.AppLauncher",
        "scene": "isaaclab.scene.InteractiveScene",
        "articulation": "isaaclab.assets.Articulation",
        "joint_lookup": "Articulation.find_joints",
        "joint_state_writer": "Articulation.write_joint_state_to_sim",
        "effort_writer": "Articulation.set_joint_effort_target",
        "external_wrench": "Articulation.permanent_wrench_composer.set_forces_and_torques",
        "wrench_reset": "Articulation.permanent_wrench_composer.reset",
    },
}


# These are requested spawn values, not measured dynamics classifications.  All
# configured hinge values stay inside the planner's validated global bounds.
ATLAS_PROFILES: dict[str, dict[str, Any]] = {
    "A0": {
        "damping_native": 50.0,
        "stiffness_native": 2.0,
        "max_force_nm": 4.5,
        "door_weight_kg": 120.0,
        "free_return_start_rad": 1.20,
        "free_return_marks_rad": FREE_RETURN_MARKS_RAD,
        "semantics": "CURRENT_EASY",
    },
    "A1": {
        "damping_native": 50.0,
        "stiffness_native": 30.0,
        "max_force_nm": 4.5,
        "door_weight_kg": 120.0,
        "free_return_start_rad": 1.20,
        "free_return_marks_rad": FREE_RETURN_MARKS_RAD,
        "semantics": "HIGH_STIFFNESS",
    },
    "A2": {
        "damping_native": 50.0,
        "stiffness_native": 6.0,
        "max_force_nm": 24.0,
        "door_weight_kg": 120.0,
        "free_return_start_rad": 1.20,
        "free_return_marks_rad": FREE_RETURN_MARKS_RAD,
        "semantics": "HIGH_SUSTAINED_RESISTIVE_TORQUE",
    },
    "A3": {
        "damping_native": 50.0,
        "stiffness_native": 30.0,
        "max_force_nm": 24.0,
        "door_weight_kg": 120.0,
        "free_return_start_rad": 0.12,
        "free_return_marks_rad": (0.09, 0.06, 0.03),
        "semantics": "FRICTION_PROXY",
    },
    "A4": {
        "damping_native": 200.0,
        "stiffness_native": 6.0,
        "max_force_nm": 10.0,
        "door_weight_kg": 120.0,
        "free_return_start_rad": 1.20,
        "free_return_marks_rad": FREE_RETURN_MARKS_RAD,
        "semantics": "HIGH_DAMPING",
    },
    "A5": {
        "damping_native": 50.0,
        "stiffness_native": 6.0,
        "max_force_nm": 10.0,
        "door_weight_kg": 160.0,
        "free_return_start_rad": 1.20,
        "free_return_marks_rad": FREE_RETURN_MARKS_RAD,
        "semantics": "HIGH_INERTIA",
    },
    "A6": {
        "damping_native": 50.0,
        "stiffness_native": 30.0,
        "max_force_nm": 10.0,
        "door_weight_kg": 120.0,
        "free_return_start_rad": 1.20,
        "free_return_marks_rad": FREE_RETURN_MARKS_RAD,
        "semantics": "HIGH_STIFFNESS_CALIBRATED_EFFORT",
    },
    "A7": {
        "damping_native": 50.0,
        "stiffness_native": 24.0,
        "max_force_nm": 24.0,
        "door_weight_kg": 120.0,
        "free_return_start_rad": 1.20,
        "free_return_marks_rad": FREE_RETURN_MARKS_RAD,
        "semantics": "HIGH_RESISTIVE_TORQUE_CALIBRATED_EFFORT",
    },
    "A8": {
        "damping_native": 200.0,
        "stiffness_native": 30.0,
        "max_force_nm": 24.0,
        "door_weight_kg": 160.0,
        "free_return_start_rad": 1.20,
        "free_return_marks_rad": FREE_RETURN_MARKS_RAD,
        "semantics": "COMPOUND_NEAR_BOUNDARY",
    },
}


def _validate_profiles() -> None:
    expected = {item[0] for item in ATLAS_CELLS}
    if set(ATLAS_PROFILES) != expected:
        raise V23Error(f"atlas profiles do not cover A0-A8: {sorted(ATLAS_PROFILES)}")
    for cell_id, profile in ATLAS_PROFILES.items():
        for field, bound_name in (
            ("damping_native", "hinge_damping_native"),
            ("stiffness_native", "hinge_stiffness_native"),
            ("max_force_nm", "hinge_max_force_nm"),
        ):
            value = finite_number(profile[field], name=f"{cell_id}.{field}")
            maximum = float(ATLAS_BOUNDS[bound_name]["max"])
            if value < 0.0 or value > maximum:
                raise V23Error(f"{cell_id}.{field}={value} exceeds bound {maximum}")
        if cell_id == "A3" and profile["semantics"] != "FRICTION_PROXY":
            raise V23Error("A3 must remain explicitly tagged FRICTION_PROXY")
        if cell_id == "A3" and profile["free_return_start_rad"] >= 0.30:
            raise V23Error("A3 friction proxy must start near closed")


def build_canonical_geometry_record(
    cell_id: str,
    *,
    realized_params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the one world-origin-independent geometry identity used by P0.4/P0.5."""

    _validate_profiles()
    if cell_id not in ATLAS_PROFILES:
        raise V23Error(f"unknown canonical A0-A8 geometry cell: {cell_id!r}")
    profile = ATLAS_PROFILES[cell_id]
    source = {
        "hinge_damping_native": profile["damping_native"],
        "hinge_stiffness_native": profile["stiffness_native"],
        "hinge_effort_limit_nm": profile["max_force_nm"],
        "door_weight_kg": profile["door_weight_kg"],
    }
    if realized_params is not None:
        if not isinstance(realized_params, Mapping):
            raise V23Error("canonical geometry realized_params must be a mapping")
        aliases = {
            "hinge_damping_native": ("hinge_damping_native",),
            "hinge_stiffness_native": ("hinge_stiffness_native",),
            "hinge_effort_limit_nm": ("hinge_effort_limit_nm", "hinge_max_force_nm"),
            "door_weight_kg": ("door_weight_kg", "door_mass_kg"),
        }
        for field, names in aliases.items():
            present = [name for name in names if name in realized_params]
            if not present:
                raise V23Error(f"canonical geometry realized_params requires {field} field")
            values = [finite_number(realized_params[name], name=f"realized_params.{name}") for name in present]
            if any(value != values[0] for value in values[1:]):
                raise V23Error(f"canonical geometry realized_params aliases disagree for {field}")
            value = values[0]
            source[field] = finite_number(value, name=f"realized_params.{present[0]}")
    for field, value in source.items():
        if field == "hinge_damping_native":
            if value < 0.0:
                raise V23Error("canonical hinge damping must be non-negative")
        elif value <= 0.0:
            raise V23Error(f"canonical geometry {field} must be positive")
    facts = {key: value[:] if isinstance(value, list) else value for key, value in CANONICAL_GEOMETRY_FACTS.items()}
    id_parts = [
        f"cell={cell_id}",
        f"width={facts['door_width_m']:.9f}",
        f"height={facts['door_height_m']:.9f}",
        f"handle_height={facts['handle_height_m']:.9f}",
        f"handle_width={facts['handle_width_m']:.9f}",
        f"handle_type={facts['handle_type']}",
        f"lr={facts['door_open_lr']}",
        f"io={facts['door_open_io']}",
        f"axis_local={','.join(f'{item:.9f}' for item in facts['hinge_axis_local'])}",
        f"anchor_local={','.join(f'{item:.9f}' for item in facts['hinge_anchor_local'])}",
        f"damping={source['hinge_damping_native']:.9f}",
        f"stiffness={source['hinge_stiffness_native']:.9f}",
        f"max_force={source['hinge_effort_limit_nm']:.9f}",
        f"mass={source['door_weight_kg']:.9f}",
    ]
    geometry_id = "a2-v23-geometry-v1|" + "|".join(id_parts)
    return {
        "schema": CANONICAL_GEOMETRY_SCHEMA,
        "geometry_id": geometry_id,
        "cell_id": cell_id,
        "realized_params": source,
        "local_facts": facts,
        "world_origin_excluded": True,
        "authority": "MEASURED_OR_RUNTIME_RECEIPT_CANONICAL_REALIZED_GEOMETRY",
    }


def validate_canonical_geometry_record(
    record: Mapping[str, Any],
    *,
    cell_id: str | None = None,
    realized_params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != CANONICAL_GEOMETRY_SCHEMA:
        raise V23Error("canonical geometry record schema is invalid")
    resolved_cell = record.get("cell_id")
    if cell_id is not None and resolved_cell != cell_id:
        raise V23Error("canonical geometry cell_id disagrees with the declared cell")
    expected = build_canonical_geometry_record(str(resolved_cell), realized_params=realized_params)
    if record.get("geometry_id") != expected["geometry_id"]:
        raise V23Error("canonical geometry_id does not match realized geometry fields")
    if record.get("realized_params") != expected["realized_params"] or record.get("local_facts") != expected["local_facts"]:
        raise V23Error("canonical geometry realized/local facts disagree")
    if record.get("world_origin_excluded") is not True:
        raise V23Error("canonical geometry must exclude world-origin facts")
    return expected


def _parse_cells(value: str | None) -> tuple[str, ...]:
    _validate_profiles()
    if value is None or not value.strip():
        return tuple(item[0] for item in ATLAS_CELLS)
    cells = tuple(token.strip() for token in value.split(",") if token.strip())
    if not cells:
        raise V23Error("--cells must contain at least one atlas cell")
    unknown = [cell for cell in cells if cell not in ATLAS_PROFILES]
    if unknown:
        raise V23Error(f"unknown atlas cells: {unknown!r}")
    if len(set(cells)) != len(cells):
        raise V23Error("--cells must not contain duplicates")
    return cells


def _parse_float_list(value: str, *, name: str) -> tuple[float, ...]:
    values = tuple(finite_number(float(token.strip()), name=name) for token in value.split(","))
    if not values:
        raise V23Error(f"{name} must contain at least one value")
    if any(item < 0.0 for item in values):
        raise V23Error(f"{name} must be non-negative")
    return values


def _validate_probe_parameters(args: argparse.Namespace) -> None:
    for name in ("dt",):
        if not math.isfinite(float(getattr(args, name))) or float(getattr(args, name)) <= 0.0:
            raise V23Error(f"--{name} must be positive and finite")
    for name in ("free_steps", "fixed_steps", "trajectory_stride", "seed"):
        if int(getattr(args, name)) < 0:
            raise V23Error(f"--{name.replace('_', '-')} must be non-negative")
    if args.free_steps == 0 or args.fixed_steps == 0 or args.trajectory_stride == 0:
        raise V23Error("step counts and trajectory stride must be positive")


def _validate_runtime_args(args: argparse.Namespace) -> str:
    _validate_probe_parameters(args)
    if args.output is None:
        raise V23Error("a measured run requires explicit --output")
    if args.device is None and args.gpu is None:
        raise V23Error("a measured run requires explicit --device or --gpu")
    if args.gpu is not None and args.gpu < 0:
        raise V23Error("--gpu must be non-negative")
    device = args.device or f"cuda:{args.gpu}"
    if args.device is not None and args.gpu is not None and device != f"cuda:{args.gpu}":
        raise V23Error("--device and --gpu identify different devices")
    if not device or device.strip() == "":
        raise V23Error("--device must not be empty")
    return device


def _source_fields() -> dict[str, Any]:
    return {
        "source_identity": SOURCE_IDENTITY,
        "source_config_path": V23_D0_SOURCE_CONFIG,
        "authority": "HIGH_LEVEL_ARTICULATION_RUNTIME",
        "torque_authority": TORQUE_AUTHORITY,
    }


def _summary(values: Sequence[float]) -> dict[str, float]:
    if not values:
        raise RuntimeError("cannot summarize an empty runtime sample sequence")
    finite_values = [finite_number(value, name="runtime_summary_value") for value in values]
    return {
        "mean": sum(finite_values) / len(finite_values),
        "max_abs": max(abs(value) for value in finite_values),
        "last": finite_values[-1],
    }


def classify_external_torque_bracket(
    trials: Sequence[Mapping[str, Any]], *, progress_threshold_rad: float = 0.02
) -> dict[str, Any]:
    """Classify conservative per-cell A0-A8 brackets without interpolation."""

    if not trials:
        raise ValueError("external torque trials must not be empty")
    threshold = finite_number(progress_threshold_rad, name="progress_threshold_rad")
    if threshold <= 0.0:
        raise ValueError("progress_threshold_rad must be positive")
    cell_ids = sorted({str(row.get("cell_id", "A0")) for row in trials})
    cell_brackets = {}
    for cell_id in cell_ids:
        by_sign = {}
        for sign in (-1, 1):
            rows = [row for row in trials if str(row.get("cell_id", "A0")) == cell_id and row.get("sign") == sign]
            rows.sort(key=lambda row: float(row.get("magnitude_nm")))
            magnitudes = [finite_number(row.get("magnitude_nm"), name="magnitude_nm") for row in rows]
            if magnitudes != list(EXTERNAL_TORQUE_MAGNITUDES_NM):
                by_sign[sign] = {"status": "AMBIGUOUS_NONMONOTONE", "reason": "MISSING_OR_DUPLICATE_MAGNITUDE"}
                continue
            progress = [finite_number(row.get("max_progress_rad"), name="max_progress_rad") for row in rows]
            passed = [value >= threshold for value in progress]
            first_pass = next((index for index, value in enumerate(passed) if value), None)
            if first_pass is None:
                by_sign[sign] = {"status": "RIGHT_CENSORED", "last_fail_nm": magnitudes[-1], "first_pass_nm": None}
                continue
            if any(passed[index] for index in range(first_pass)) or any(not passed[index] for index in range(first_pass, len(passed))):
                by_sign[sign] = {"status": "AMBIGUOUS_NONMONOTONE", "reason": "FAIL_TO_PASS_MONOTONICITY_VIOLATION"}
                continue
            by_sign[sign] = {
                "status": "VALID_BRACKET" if first_pass > 0 else "LEFT_CENSORED",
                "last_fail_nm": magnitudes[first_pass - 1] if first_pass else None,
                "first_pass_nm": magnitudes[first_pass],
            }
        statuses = {item["status"] for item in by_sign.values()}
        if "AMBIGUOUS_NONMONOTONE" in statuses:
            cell_brackets[cell_id] = {"status": "AMBIGUOUS_NONMONOTONE", "by_sign": by_sign}
            continue
        if "RIGHT_CENSORED" in statuses:
            cell_brackets[cell_id] = {"status": "RIGHT_CENSORED", "by_sign": by_sign}
            continue
        upper = max(by_sign[sign]["first_pass_nm"] for sign in (-1, 1))
        tied_signs = [sign for sign in (-1, 1) if by_sign[sign]["first_pass_nm"] == upper]
        lower_candidates = [by_sign[sign]["last_fail_nm"] for sign in tied_signs]
        lower = max(value for value in lower_candidates if value is not None) if all(value is not None for value in lower_candidates) else None
        if lower is None or not lower < upper:
            status = "LEFT_CENSORED" if lower is None else "AMBIGUOUS_NONMONOTONE"
            cell_brackets[cell_id] = {"status": status, "by_sign": by_sign, "upper_nm": upper, "tied_signs": tied_signs}
            continue
        cell_brackets[cell_id] = {
            "status": "VALID_BRACKET",
            "by_sign": by_sign,
            "lower_nm": lower,
            "upper_nm": upper,
            "tied_signs": tied_signs,
            "conservative_rule": "U=max(first_pass_over_signs); L=max(last_fail_among_signs_tied_at_U); require L<U",
        }
    statuses = {item.get("status") for item in cell_brackets.values()}
    overall = "VALID_BRACKET" if statuses == {"VALID_BRACKET"} else (next(iter(statuses)) if len(statuses) == 1 else "AMBIGUOUS_NONMONOTONE")
    return {"status": overall, "threshold_rad": threshold, "cells": cell_brackets}


def _classify_directional_sign(
    rows: Sequence[Mapping[str, Any]], *, sign: int, threshold: float
) -> dict[str, Any]:
    expected = list(EXTERNAL_TORQUE_MAGNITUDES_NM)
    ordered = sorted(rows, key=lambda row: float(row.get("magnitude_nm")))
    magnitudes = [finite_number(row.get("magnitude_nm"), name="magnitude_nm") for row in ordered]
    if magnitudes != expected:
        raise ValueError(f"directional sign {sign} requires the exact registered magnitude ladder")
    progress = [finite_number(row.get("max_progress_rad"), name="max_progress_rad") for row in ordered]
    passed = [value >= threshold for value in progress]
    first_pass = next((index for index, value in enumerate(passed) if value), None)
    if first_pass is None:
        return {"status": "RIGHT_CENSORED", "last_fail_nm": magnitudes[-1], "first_pass_nm": None}
    if any(passed[index] for index in range(first_pass)) or any(
        not passed[index] for index in range(first_pass, len(passed))
    ):
        raise ValueError(f"directional sign {sign} violates fail-to-pass monotonicity")
    return {
        "status": "VALID_BRACKET" if first_pass > 0 else "LEFT_CENSORED",
        "last_fail_nm": magnitudes[first_pass - 1] if first_pass else None,
        "first_pass_nm": magnitudes[first_pass],
    }


def classify_directional_opening_bracket(
    trials: Sequence[Mapping[str, Any]], *, progress_threshold_rad: float = 0.02
) -> dict[str, Any]:
    """Classify the positive-opening bracket while preserving negative censoring."""

    if not trials:
        raise ValueError("directional external trials must not be empty")
    threshold = finite_number(progress_threshold_rad, name="progress_threshold_rad")
    if threshold <= 0.0:
        raise ValueError("progress_threshold_rad must be positive")
    cells = sorted({str(row.get("cell_id", "")) for row in trials})
    directional_cells: dict[str, dict[str, Any]] = {}
    for cell_id in cells:
        positive_rows = [row for row in trials if str(row.get("cell_id")) == cell_id and row.get("sign") == 1]
        negative_rows = [row for row in trials if str(row.get("cell_id")) == cell_id and row.get("sign") == -1]
        positive = _classify_directional_sign(positive_rows, sign=1, threshold=threshold)
        negative = _classify_directional_sign(negative_rows, sign=-1, threshold=threshold)
        if positive.get("status") != "VALID_BRACKET":
            raise ValueError(f"{cell_id} positive opening sign is not a valid bracket")
        if negative.get("status") != "RIGHT_CENSORED":
            raise ValueError(f"{cell_id} negative sign must remain RIGHT_CENSORED")
        lower = positive.get("last_fail_nm")
        upper = positive.get("first_pass_nm")
        if lower is None or upper is None or not float(lower) < float(upper):
            raise ValueError(f"{cell_id} positive opening bracket is not finite and ordered")
        directional_cells[cell_id] = {
            "cell_id": cell_id,
            "status": "UNIDIRECTIONAL_OPENING_BRACKET",
            "typed_state": "UNIDIRECTIONAL_OPENING_BRACKET",
            **DIRECTIONAL_OPENING_CONTRACT,
            "opening_bracket": {
                "status": "VALID_BRACKET",
                "lower_nm": float(lower),
                "upper_nm": float(upper),
                "last_fail_nm": float(lower),
                "first_pass_nm": float(upper),
            },
            "negative_censor": dict(negative),
        }
    return {
        "schema": DIRECTIONAL_OPENING_BRACKET_SCHEMA,
        "status": "DIRECTIONAL_OPENING_CLASSIFIED",
        "threshold_rad": threshold,
        "contract": dict(DIRECTIONAL_OPENING_CONTRACT),
        "cells": directional_cells,
    }


def _plan_payload(cells: Sequence[str], fixed_efforts_nm: Sequence[float], args: argparse.Namespace) -> dict[str, Any]:
    rows = []
    for cell_id in cells:
        profile = ATLAS_PROFILES[cell_id]
        geometry = build_canonical_geometry_record(cell_id)
        rows.append(
            {
                "cell_id": cell_id,
                "geometry_id": geometry["geometry_id"],
                "canonical_geometry": geometry,
                "status": "PLAN_ONLY",
                "authority": "REQUESTED_CONFIG_ONLY",
                "requested_params": {
                    "hinge_damping_native": profile["damping_native"],
                    "hinge_stiffness_native": profile["stiffness_native"],
                    "hinge_max_force_nm": profile["max_force_nm"],
                    "door_weight_kg": profile["door_weight_kg"],
                },
                "requested_probe": {
                    "free_return_start_rad": profile["free_return_start_rad"],
                    "free_return_marks_rad": list(profile["free_return_marks_rad"]),
                    "fixed_efforts_nm": list(fixed_efforts_nm),
                    "dt_s": args.dt,
                    "free_return_steps": args.free_steps,
                    "fixed_effort_steps": args.fixed_steps,
                    "trajectory_stride": args.trajectory_stride,
                    "seed": args.seed,
                    "device": args.device or (f"cuda:{args.gpu}" if args.gpu is not None else None),
                },
                "atlas_semantics": profile["semantics"],
                "a3_semantics": "FRICTION_PROXY" if cell_id == "A3" else None,
                "physics_class": "PENDING",
                "scientific_e_zone": None,
            }
        )
    return artifact_payload(
        "door_atlas_raw",
        status="PLAN_ONLY",
        **_source_fields(),
        rows=rows,
        atlas_bounds=ATLAS_BOUNDS,
        classification_basis="physics_first_free_return_and_fixed_effort_response",
        scientific_classification="PENDING_UNTIL_MEASURED",
    )


def _require_runtime_columns(door: Any, hinge_id: int) -> tuple[Any, Any, Any, Any, Any, Any]:
    columns = []
    for name in (
        "joint_pos",
        "joint_pos_target",
        "joint_vel",
        "computed_torque",
        "applied_torque",
        "joint_effort_limits",
    ):
        value = getattr(door.data, name, None)
        if value is None:
            raise RuntimeError(f"Articulation.data.{name} is unavailable for the hinge probe")
        if value.ndim != 2 or value.shape[1] <= hinge_id:
            raise RuntimeError(f"Articulation.data.{name} has no hinge column {hinge_id}")
        columns.append(value)
    return columns[0], columns[1], columns[2], columns[3], columns[4], columns[5]


def _tensor_column(value: Any, hinge_id: int, *, name: str) -> list[float]:
    result = value[:, hinge_id].detach().cpu().tolist()
    values = [finite_number(item, name=f"{name}[{index}]") for index, item in enumerate(result)]
    return values


def _run_probe(
    *,
    cells: Sequence[str],
    fixed_efforts_nm: Sequence[float],
    device: str,
    seed: int,
    dt: float,
    free_steps: int,
    fixed_steps: int,
    trajectory_stride: int,
) -> dict[str, Any]:
    """Launch one bounded door-only scene and return plain measured rows."""

    import numpy as np
    import torch

    import isaaclab.sim as sim_utils
    from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.utils import configclass

    from gr00t.rl.data.tasks.door.scenario_cfg.isaacsim import TaskObjCfgDict
    from gr00t.rl.isaac_utils.playground.env_rand.door import DoorSpawnerCfg

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    base_door_cfg = TaskObjCfgDict["door"]
    base_spawn = base_door_cfg.spawn
    base_assets = list(base_spawn.assets_cfg)
    if not base_assets or not isinstance(base_assets[0], DoorSpawnerCfg):
        raise TypeError("v23 atlas requires a DoorSpawnerCfg base asset")

    base_asset = base_assets[0]
    variants = []
    for cell_id in cells:
        profile = ATLAS_PROFILES[cell_id]
        variants.append(
            base_asset.replace(
                rand_door_width=0.95,
                rand_door_height=2.05,
                rand_door_handle_height=0.975,
                rand_door_handle_width=0.12,
                rand_door_weight=float(profile["door_weight_kg"]),
                rand_door_handle_type="lever",
                rand_door_open_lr="right",
                rand_door_open_io="out",
                rand_hinge_drive_max_force=float(profile["max_force_nm"]),
                rand_hinge_drive_damping=float(profile["damping_native"]),
                rand_hinge_drive_stiffness=float(profile["stiffness_native"]),
                rand_handle_drive_max_force=2.0,
                randomize_material=False,
                use_preloaded_materials=False,
                activate_contact_sensors=False,
                build_latch=False,
                add_floors=False,
                add_lights=False,
                add_ceiling=False,
            )
        )
    door_spawn = base_spawn.replace(
        assets_cfg=variants,
        random_choice=False,
        activate_contact_sensors=False,
    )
    atlas_joint_pos = dict(base_door_cfg.init_state.joint_pos)
    del atlas_joint_pos[".*latch.*"]
    door_cfg = base_door_cfg.replace(
        spawn=door_spawn,
        prim_path="{ENV_REGEX_NS}/door",
        init_state=base_door_cfg.init_state.replace(
            joint_pos=atlas_joint_pos,
        ),
    )

    @configclass
    class DoorAtlasSceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(
            prim_path="/World/defaultGroundPlane",
            spawn=sim_utils.GroundPlaneCfg(),
        )
        dome_light = AssetBaseCfg(
            prim_path="/World/DomeLight",
            spawn=sim_utils.DomeLightCfg(intensity=1500.0),
        )
        door: ArticulationCfg = door_cfg

    sim = sim_utils.SimulationContext(
        sim_utils.SimulationCfg(dt=dt, device=device)
    )
    scene = InteractiveScene(
        DoorAtlasSceneCfg(
            num_envs=len(cells),
            env_spacing=6.0,
            replicate_physics=False,
        )
    )
    print("V23_ATLAS_PROGRESS before-sim-reset", flush=True)
    sim.reset()
    print("V23_ATLAS_PROGRESS sim-reset-returned", flush=True)

    door: Articulation = scene["door"]
    hinge_ids, hinge_names = door.find_joints([".*hinge.*"], preserve_order=True)
    if len(hinge_ids) != 1 or len(hinge_names) != 1:
        raise RuntimeError(f"v23 atlas requires exactly one named hinge joint, got {hinge_names!r}")
    hinge_id = int(hinge_ids[0])
    hinge_name = str(hinge_names[0])
    panel_ids, panel_names = door.find_bodies("door_panel", preserve_order=True)
    if len(panel_ids) != 1 or list(panel_names) != ["door_panel"]:
        raise RuntimeError(f"v23 atlas requires exactly one door_panel body, got {panel_names!r}")
    panel_id = int(panel_ids[0])
    realized_damping = _tensor_column(door.data.joint_damping, hinge_id, name="joint_damping")
    realized_stiffness = _tensor_column(door.data.joint_stiffness, hinge_id, name="joint_stiffness")
    realized_limits = _tensor_column(door.data.joint_effort_limits, hinge_id, name="joint_effort_limits")
    masses = door.root_physx_view.get_masses()
    if tuple(masses.shape) != (len(cells), door.num_bodies):
        raise RuntimeError("external probe mass readback shape does not match the door topology")
    realized_masses = _tensor_column(masses, panel_id, name="door_panel_mass")
    joint_pos, joint_pos_target, joint_vel, computed_torque, applied_torque, effort_limits = (
        _require_runtime_columns(door, hinge_id)
    )
    del joint_pos, joint_pos_target, joint_vel, computed_torque, applied_torque
    realized_damping = _tensor_column(door.data.joint_damping, hinge_id, name="joint_damping")
    realized_stiffness = _tensor_column(door.data.joint_stiffness, hinge_id, name="joint_stiffness")
    realized_limits = _tensor_column(effort_limits, hinge_id, name="joint_effort_limits")
    masses = door.root_physx_view.get_masses()
    if tuple(masses.shape) != (len(cells), door.num_bodies):
        raise RuntimeError("v23 atlas mass readback shape does not match environment/body topology")
    realized_masses = _tensor_column(masses, panel_id, name="door_panel_mass")
    if any(value <= 0.0 for value in realized_limits):
        raise RuntimeError(f"hinge effort limits must be positive, got {realized_limits!r}")

    n_envs = len(cells)
    zero_target = torch.zeros_like(door.data.default_joint_pos)
    default_pos = door.data.default_joint_pos.clone()
    default_vel = door.data.default_joint_vel.clone()

    def reset_hinge(start_positions: Sequence[float]) -> None:
        if len(start_positions) != n_envs:
            raise RuntimeError("hinge reset vector does not match atlas environment count")
        positions = default_pos.clone()
        velocities = torch.zeros_like(default_vel)
        positions[:, hinge_id] = torch.as_tensor(
            list(start_positions), dtype=positions.dtype, device=positions.device
        )
        door.write_joint_state_to_sim(positions, velocities)
        door.set_joint_effort_target(zero_target)
        scene.write_data_to_sim()
        sim.step()
        scene.update(dt)

    def step_effort(
        target_effort_nm: float,
    ) -> tuple[list[float], list[float], list[float], list[float], list[float], list[float]]:
        target = torch.zeros_like(zero_target)
        target[:, hinge_id] = float(target_effort_nm)
        door.set_joint_effort_target(target)
        scene.write_data_to_sim()
        sim.step()
        scene.update(dt)
        positions = _tensor_column(door.data.joint_pos, hinge_id, name="joint_pos")
        position_targets = _tensor_column(
            door.data.joint_pos_target, hinge_id, name="joint_pos_target"
        )
        velocities = _tensor_column(door.data.joint_vel, hinge_id, name="joint_vel")
        nominal_estimates = _tensor_column(
            door.data.computed_torque,
            hinge_id,
            name="nominal_actuator_model_torque_estimate",
        )
        applied_estimates = _tensor_column(
            door.data.applied_torque,
            hinge_id,
            name="applied_actuator_model_torque_estimate",
        )
        tracking_errors = [
            target_position - position
            for target_position, position in zip(position_targets, positions)
        ]
        for index, error in enumerate(tracking_errors):
            finite_number(error, name=f"tracking_error_rad[{index}]")
        return (
            positions,
            position_targets,
            velocities,
            nominal_estimates,
            applied_estimates,
            tracking_errors,
        )

    starts = [float(ATLAS_PROFILES[cell]["free_return_start_rad"]) for cell in cells]
    mark_targets = [tuple(float(item) for item in ATLAS_PROFILES[cell]["free_return_marks_rad"]) for cell in cells]
    reset_hinge(starts)
    print("V23_ATLAS_PROGRESS initial-step-returned", flush=True)
    mark_steps = [[None for _ in marks] for marks in mark_targets]
    free_trajectories = [[] for _ in cells]
    free_peak_speed = [0.0 for _ in cells]
    free_impulse = [0.0 for _ in cells]
    free_applied_min = [float("inf") for _ in cells]
    free_applied_max = [float("-inf") for _ in cells]
    free_capped_steps = [0 for _ in cells]
    free_nominal_peak = [0.0 for _ in cells]
    free_clipped_peak = [0.0 for _ in cells]
    free_clipping_residual_peak = [0.0 for _ in cells]
    free_tracking_samples = [[] for _ in cells]
    free_velocity_samples = [[] for _ in cells]
    all_tracking_samples = [[] for _ in cells]
    all_velocity_samples = [[] for _ in cells]

    for step_index in range(free_steps):
        (
            positions,
            position_targets,
            velocities,
            nominal_estimates,
            applied_estimates,
            tracking_errors,
        ) = step_effort(0.0)
        for env_index, cell_id in enumerate(cells):
            for mark_index, mark in enumerate(mark_targets[env_index]):
                if mark_steps[env_index][mark_index] is None and positions[env_index] <= mark:
                    mark_steps[env_index][mark_index] = step_index + 1
            speed = abs(velocities[env_index])
            free_peak_speed[env_index] = max(free_peak_speed[env_index], speed)
            free_impulse[env_index] += max(0.0, -velocities[env_index]) * dt
            free_applied_min[env_index] = min(
                free_applied_min[env_index], applied_estimates[env_index]
            )
            free_applied_max[env_index] = max(
                free_applied_max[env_index], applied_estimates[env_index]
            )
            free_capped_steps[env_index] += int(
                abs(applied_estimates[env_index]) >= 0.995 * realized_limits[env_index]
            )
            free_nominal_peak[env_index] = max(
                free_nominal_peak[env_index], abs(nominal_estimates[env_index])
            )
            free_clipped_peak[env_index] = max(
                free_clipped_peak[env_index], abs(applied_estimates[env_index])
            )
            free_clipping_residual_peak[env_index] = max(
                free_clipping_residual_peak[env_index],
                abs(nominal_estimates[env_index] - applied_estimates[env_index]),
            )
            free_tracking_samples[env_index].append(tracking_errors[env_index])
            free_velocity_samples[env_index].append(velocities[env_index])
            all_tracking_samples[env_index].append(tracking_errors[env_index])
            all_velocity_samples[env_index].append(velocities[env_index])
            if step_index % trajectory_stride == 0 or step_index + 1 == free_steps:
                free_trajectories[env_index].append(
                    {
                        "step": step_index + 1,
                        "time_s": round((step_index + 1) * dt, 9),
                        "joint_pos_target_rad": position_targets[env_index],
                        "position_rad": positions[env_index],
                        "tracking_error_rad": tracking_errors[env_index],
                        "joint_velocity_rad_s": velocities[env_index],
                        "nominal_actuator_model_torque_estimate_nm": nominal_estimates[env_index],
                        "applied_actuator_model_torque_estimate_nm": applied_estimates[env_index],
                        "estimated_clipping_residual_nm": nominal_estimates[env_index]
                        - applied_estimates[env_index],
                        "torque_authority": TORQUE_AUTHORITY,
                    }
                )

    print("V23_ATLAS_PROGRESS free-loop-complete", flush=True)
    free_final_positions = _tensor_column(door.data.joint_pos, hinge_id, name="joint_pos")
    fixed_responses = [[] for _ in cells]
    fixed_nominal_peak = [0.0 for _ in cells]
    fixed_clipped_peak = [0.0 for _ in cells]
    fixed_clipping_residual_peak = [0.0 for _ in cells]
    for requested_effort in fixed_efforts_nm:
        reset_hinge([0.0 for _ in cells])
        response_trajectories = [[] for _ in cells]
        max_progress = [float("-inf") for _ in cells]
        peak_speed = [0.0 for _ in cells]
        capped_steps = [0 for _ in cells]
        final_positions = [0.0 for _ in cells]
        final_velocities = [0.0 for _ in cells]
        response_nominal_peak = [0.0 for _ in cells]
        response_clipped_peak = [0.0 for _ in cells]
        response_clipping_residual_peak = [0.0 for _ in cells]
        response_tracking_samples = [[] for _ in cells]
        response_velocity_samples = [[] for _ in cells]
        for step_index in range(fixed_steps):
            (
                positions,
                position_targets,
                velocities,
                nominal_estimates,
                applied_estimates,
                tracking_errors,
            ) = step_effort(requested_effort)
            for env_index in range(n_envs):
                max_progress[env_index] = max(max_progress[env_index], positions[env_index])
                peak_speed[env_index] = max(peak_speed[env_index], abs(velocities[env_index]))
                capped_steps[env_index] += int(
                    abs(applied_estimates[env_index]) >= 0.995 * realized_limits[env_index]
                )
                response_nominal_peak[env_index] = max(
                    response_nominal_peak[env_index], abs(nominal_estimates[env_index])
                )
                response_clipped_peak[env_index] = max(
                    response_clipped_peak[env_index], abs(applied_estimates[env_index])
                )
                response_clipping_residual_peak[env_index] = max(
                    response_clipping_residual_peak[env_index],
                    abs(nominal_estimates[env_index] - applied_estimates[env_index]),
                )
                fixed_nominal_peak[env_index] = max(
                    fixed_nominal_peak[env_index], abs(nominal_estimates[env_index])
                )
                fixed_clipped_peak[env_index] = max(
                    fixed_clipped_peak[env_index], abs(applied_estimates[env_index])
                )
                fixed_clipping_residual_peak[env_index] = max(
                    fixed_clipping_residual_peak[env_index],
                    abs(nominal_estimates[env_index] - applied_estimates[env_index]),
                )
                response_tracking_samples[env_index].append(tracking_errors[env_index])
                response_velocity_samples[env_index].append(velocities[env_index])
                all_tracking_samples[env_index].append(tracking_errors[env_index])
                all_velocity_samples[env_index].append(velocities[env_index])
                final_positions[env_index] = positions[env_index]
                final_velocities[env_index] = velocities[env_index]
                if step_index % trajectory_stride == 0 or step_index + 1 == fixed_steps:
                    response_trajectories[env_index].append(
                        {
                            "step": step_index + 1,
                            "time_s": round((step_index + 1) * dt, 9),
                            "joint_pos_target_rad": position_targets[env_index],
                            "position_rad": positions[env_index],
                            "tracking_error_rad": tracking_errors[env_index],
                            "joint_velocity_rad_s": velocities[env_index],
                            "nominal_actuator_model_torque_estimate_nm": nominal_estimates[env_index],
                            "applied_actuator_model_torque_estimate_nm": applied_estimates[env_index],
                            "estimated_clipping_residual_nm": nominal_estimates[env_index]
                            - applied_estimates[env_index],
                            "commanded_effort_target_nm": float(requested_effort),
                            "torque_authority": TORQUE_AUTHORITY,
                        }
                )
        for env_index in range(n_envs):
            fixed_responses[env_index].append(
                {
                    "commanded_effort_target_nm": float(requested_effort),
                    "command_authority": "USER_COMMAND",
                    "effort_limit_nm": realized_limits[env_index],
                    "final_position_rad": final_positions[env_index],
                    "final_joint_velocity_rad_s": final_velocities[env_index],
                    "max_progress_rad": max_progress[env_index],
                    "peak_abs_joint_velocity_rad_s": peak_speed[env_index],
                    "actuator_model_effort_limit_clipping_fraction": capped_steps[env_index]
                    / fixed_steps,
                    "nominal_actuator_model_torque_estimate_peak_nm": response_nominal_peak[
                        env_index
                    ],
                    "applied_actuator_model_torque_estimate_peak_nm": response_clipped_peak[
                        env_index
                    ],
                    "estimated_clipping_residual_peak_nm": response_clipping_residual_peak[
                        env_index
                    ],
                    "torque_authority": TORQUE_AUTHORITY,
                    "tracking_error_rad": _summary(response_tracking_samples[env_index]),
                    "joint_velocity_rad_s": _summary(response_velocity_samples[env_index]),
                    "trajectory": response_trajectories[env_index],
                }
            )

    print("V23_ATLAS_PROGRESS fixed-loop-complete", flush=True)
    rows = []
    for env_index, cell_id in enumerate(cells):
        mark_times = [
            None if step is None else round(step * dt, 9) for step in mark_steps[env_index]
        ]
        free_return = {
            "start_rad": starts[env_index],
            "mark_targets_rad": list(mark_targets[env_index]),
            "mark_steps": mark_steps[env_index],
            "mark_times_s": mark_times,
            "peak_closing_joint_velocity_rad_s": free_peak_speed[env_index],
            "closing_impulse_proxy_rad": free_impulse[env_index],
            "applied_actuator_model_torque_estimate_min_nm": free_applied_min[env_index],
            "applied_actuator_model_torque_estimate_max_nm": free_applied_max[env_index],
            "actuator_model_effort_limit_clipping_fraction": free_capped_steps[env_index]
            / free_steps,
            "torque_authority": TORQUE_AUTHORITY,
            "tracking_error_rad": _summary(free_tracking_samples[env_index]),
            "joint_velocity_rad_s": _summary(free_velocity_samples[env_index]),
            "final_position_rad": free_final_positions[env_index],
            "trajectory": free_trajectories[env_index],
        }
        realized_params = {
            "hinge_damping_native": realized_damping[env_index],
            "hinge_stiffness_native": realized_stiffness[env_index],
            "hinge_effort_limit_nm": realized_limits[env_index],
            "hinge_max_force_nm": realized_limits[env_index],
            "door_weight_kg": realized_masses[env_index],
        }
        geometry = build_canonical_geometry_record(cell_id, realized_params=realized_params)
        rows.append(
            {
                "cell_id": cell_id,
                "geometry_id": geometry["geometry_id"],
                "canonical_geometry": geometry,
                "status": "MEASURED_RAW",
                "authority": "HIGH_LEVEL_ARTICULATION_RUNTIME",
                "torque_authority": TORQUE_AUTHORITY,
                "source_identity": SOURCE_IDENTITY,
                "hinge_joint_name": hinge_name,
                "requested_params": {
                    "hinge_damping_native": ATLAS_PROFILES[cell_id]["damping_native"],
                    "hinge_stiffness_native": ATLAS_PROFILES[cell_id]["stiffness_native"],
                    "hinge_max_force_nm": ATLAS_PROFILES[cell_id]["max_force_nm"],
                    "door_weight_kg": ATLAS_PROFILES[cell_id]["door_weight_kg"],
                },
                "realized_params": {
                    "hinge_damping_native": realized_damping[env_index],
                    "hinge_stiffness_native": realized_stiffness[env_index],
                    "hinge_effort_limit_nm": realized_limits[env_index],
                    "hinge_max_force_nm": realized_limits[env_index],
                    "door_weight_kg": realized_masses[env_index],
                },
                "atlas_semantics": ATLAS_PROFILES[cell_id]["semantics"],
                "a3_semantics": "FRICTION_PROXY" if cell_id == "A3" else None,
                "free_return": free_return,
                "fixed_effort_responses": fixed_responses[env_index],
                "nominal_actuator_model_torque_estimate": {
                    "peak_abs_nm": max(free_nominal_peak[env_index], fixed_nominal_peak[env_index]),
                    "authority": TORQUE_AUTHORITY,
                },
                "applied_actuator_model_torque_estimate": {
                    "peak_abs_nm": max(free_clipped_peak[env_index], fixed_clipped_peak[env_index]),
                    "authority": TORQUE_AUTHORITY,
                },
                "estimated_clipping_residual": {
                    "peak_abs_nm": max(
                        free_clipping_residual_peak[env_index],
                        fixed_clipping_residual_peak[env_index],
                    ),
                    "definition": "nominal_actuator_model_torque_estimate_minus_applied_actuator_model_torque_estimate",
                    "authority": TORQUE_AUTHORITY,
                },
                "tracking_error_rad": _summary(all_tracking_samples[env_index]),
                "tracking_error_formula": "joint_pos_target - joint_pos",
                "joint_velocity_rad_s": _summary(all_velocity_samples[env_index]),
                "physics_class": "PENDING",
                "scientific_e_zone": None,
            }
        )

    payload = artifact_payload(
        "door_atlas_raw",
        status="MEASURED_RAW",
        **_source_fields(),
        runtime={
            "device": device,
            "seed": seed,
            "dt_s": dt,
            "free_return_steps": free_steps,
            "fixed_effort_steps": fixed_steps,
            "trajectory_stride": trajectory_stride,
            "fixed_efforts_nm": list(fixed_efforts_nm),
            "num_envs": len(cells),
            "hinge_joint_name": hinge_name,
        },
        rows=rows,
        atlas_bounds=ATLAS_BOUNDS,
        classification_basis="physics_first_free_return_and_fixed_effort_response",
        scientific_classification="PENDING_UNTIL_MEASURED",
    )
    print("V23_ATLAS_PROGRESS payload-built", flush=True)
    sim.clear_instance()
    print("V23_ATLAS_PROGRESS callbacks-cleared", flush=True)
    print("V23_ATLAS_PROGRESS context-cleared", flush=True)
    sim.stop()
    print("V23_ATLAS_PROGRESS stop-returned", flush=True)
    print("V23_ATLAS_PROGRESS returning", flush=True)
    return payload


def _run_external_torque_probe(*, cells: Sequence[str], device: str, seed: int, dt: float) -> dict[str, Any]:
    """Probe one panel/hinge with global external torque only.

    Each magnitude/sign is reset independently.  The composer is reset before
    every trial, the hinge drive target is zero, one settle step is taken, and
    exactly 100 physics frames receive the global wrench.
    """

    import numpy as np
    import torch

    import isaaclab.sim as sim_utils
    from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.utils.math import quat_apply
    from isaaclab.utils import configclass

    from gr00t.rl.data.tasks.door.scenario_cfg.isaacsim import TaskObjCfgDict
    from gr00t.rl.isaac_utils.playground.env_rand.door import DoorSpawnerCfg

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if abs(float(dt) - SIM_DT) > 1.0e-12:
        raise RuntimeError(f"external threshold requires dt exactly {SIM_DT:.3f} s; got {dt!r}")
    base_cfg = TaskObjCfgDict["door"]
    if not isinstance(base_cfg, ArticulationCfg):
        raise RuntimeError("external torque probe requires the semantic door ArticulationCfg")
    base_spawn = base_cfg.spawn
    if not isinstance(base_spawn, sim_utils.MultiAssetSpawnerCfg):
        raise RuntimeError("external torque probe requires a MultiAssetSpawnerCfg door spawn")
    if not isinstance(base_spawn.assets_cfg, list) or not base_spawn.assets_cfg:
        raise RuntimeError("external torque probe requires a non-empty DoorSpawnerCfg asset list")
    assets = list(base_spawn.assets_cfg)
    if any(not isinstance(asset, DoorSpawnerCfg) for asset in assets):
        raise TypeError("external torque probe requires every asset to be a DoorSpawnerCfg")
    base_asset = assets[0]
    if any(asset != base_asset for asset in assets[1:]):
        raise RuntimeError("external torque probe requires structurally uniform DoorSpawnerCfg templates")
    variants = []
    for cell_id in cells:
        profile = ATLAS_PROFILES[cell_id]
        variants.append(
            base_asset.replace(
                rand_door_width=0.95,
                rand_door_height=2.05,
                rand_door_handle_height=0.975,
                rand_door_handle_width=0.12,
                rand_door_weight=float(profile["door_weight_kg"]),
                rand_door_handle_type="lever",
                rand_door_open_lr="right",
                rand_door_open_io="out",
                rand_hinge_drive_max_force=float(profile["max_force_nm"]),
                rand_hinge_drive_damping=float(profile["damping_native"]),
                rand_hinge_drive_stiffness=float(profile["stiffness_native"]),
                rand_handle_drive_max_force=2.0,
                randomize_material=False,
                use_preloaded_materials=False,
                activate_contact_sensors=False,
                build_latch=False,
                add_floors=False,
                add_lights=False,
                add_ceiling=False,
            )
        )
    if any(variant.build_latch is not False for variant in variants):
        raise RuntimeError("external torque probe requires latchless DoorSpawnerCfg variants")
    base_joint_pos = dict(base_cfg.init_state.joint_pos)
    expected_joint_keys = {".*hinge.*", ".*handle.*", ".*latch.*"}
    if set(base_joint_pos) != expected_joint_keys:
        raise RuntimeError(
            "external torque probe requires exact hinge/handle/latch init-state joint keys"
        )
    external_joint_pos = dict(base_joint_pos)
    del external_joint_pos[".*latch.*"]
    door_cfg = base_cfg.replace(
        spawn=base_spawn.replace(assets_cfg=variants, random_choice=False, activate_contact_sensors=False),
        prim_path="{ENV_REGEX_NS}/door",
        init_state=base_cfg.init_state.replace(joint_pos=external_joint_pos),
    )

    @configclass
    class ExternalProbeSceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(prim_path="/World/defaultGroundPlane", spawn=sim_utils.GroundPlaneCfg())
        door: ArticulationCfg = door_cfg

    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=dt, device=device))
    scene = InteractiveScene(ExternalProbeSceneCfg(num_envs=len(cells), env_spacing=6.0, replicate_physics=False))
    sim.reset()
    door: Articulation = scene["door"]
    hinge_ids, hinge_names = door.find_joints(".*hinge.*", preserve_order=True)
    panel_ids, panel_names = door.find_bodies("door_panel", preserve_order=True)
    if len(hinge_ids) != 1 or len(panel_ids) != 1:
        raise RuntimeError(f"external probe requires exactly one hinge/panel; hinge={hinge_names!r}, panel={panel_names!r}")
    hinge_id = int(hinge_ids[0])
    panel_id = int(panel_ids[0])
    realized_damping = _tensor_column(door.data.joint_damping, hinge_id, name="joint_damping")
    realized_stiffness = _tensor_column(door.data.joint_stiffness, hinge_id, name="joint_stiffness")
    realized_limits = _tensor_column(door.data.joint_effort_limits, hinge_id, name="joint_effort_limits")
    masses = door.root_physx_view.get_masses()
    if tuple(masses.shape) != (len(cells), door.num_bodies):
        raise RuntimeError("external probe mass readback shape does not match the door topology")
    realized_masses = _tensor_column(masses, panel_id, name="door_panel_mass")
    zero_target = torch.zeros_like(door.data.default_joint_pos)
    default_pos = door.data.default_joint_pos.clone()
    default_vel = door.data.default_joint_vel.clone()
    if not torch.is_tensor(getattr(door.data, "root_pos_w", None)) or not torch.is_tensor(getattr(door.data, "root_quat_w", None)):
        raise RuntimeError("external threshold requires high-level door root_pos_w/root_quat_w pose data")
    env_ids = torch.arange(len(cells), dtype=torch.long, device=default_pos.device)
    body_ids = torch.tensor([panel_id], dtype=torch.long, device=default_pos.device)

    def reset_closed() -> tuple[list[float], list[dict[str, Any]], torch.Tensor, torch.Tensor]:
        positions = default_pos.clone()
        positions[:, hinge_id] = 0.0
        door.permanent_wrench_composer.reset()
        door.write_joint_state_to_sim(positions, default_vel.clone())
        door.set_joint_effort_target(zero_target)
        scene.write_data_to_sim()
        sim.step()
        scene.update(SIM_DT)
        q0 = door.data.joint_pos[:, hinge_id].detach().cpu().tolist()
        root_pos = door.data.root_pos_w.detach()
        root_quat = door.data.root_quat_w.detach()
        open_lr = -1.0
        anchor_root = torch.tensor([0.02, -0.475 * open_lr, 0.0], dtype=root_pos.dtype, device=root_pos.device)
        axis_root = torch.tensor([0.0, 0.0, 1.0 if open_lr < 0 else -1.0], dtype=root_pos.dtype, device=root_pos.device)
        anchor_world = root_pos + quat_apply(root_quat, anchor_root.expand(len(cells), -1))
        axis_world = quat_apply(root_quat, axis_root.expand(len(cells), -1))
        geometries = []
        for env_index, cell_id in enumerate(cells):
            geometries.append(
                build_canonical_geometry_record(
                    cell_id,
                    realized_params={
                        "hinge_damping_native": realized_damping[env_index],
                        "hinge_stiffness_native": realized_stiffness[env_index],
                        "hinge_effort_limit_nm": realized_limits[env_index],
                        "door_weight_kg": realized_masses[env_index],
                    },
                )
            )
        return q0, geometries, anchor_world, axis_world

    rows = []
    for sign in (-1, 1):
        for magnitude in EXTERNAL_TORQUE_MAGNITUDES_NM:
            q0, geometries, anchor_world, axis_world = reset_closed()
            if not torch.all(torch.isfinite(axis_world)) or not torch.all(torch.isfinite(door.data.body_pos_w[:, panel_id])):
                raise RuntimeError("external probe hinge axis/anchor transform is non-finite")
            door.permanent_wrench_composer.reset()
            torque = float(sign) * float(magnitude) * axis_world
            torque = torque.unsqueeze(1)
            door.permanent_wrench_composer.set_forces_and_torques(
                torques=torque,
                body_ids=body_ids,
                env_ids=env_ids,
                is_global=True,
            )
            max_progress = [0.0 for _ in cells]
            raw_q_trace = [[] for _ in cells]
            signed_trace = [[] for _ in cells]
            for frame in range(100):
                door.set_joint_effort_target(zero_target)
                scene.write_data_to_sim()
                sim.step()
                scene.update(SIM_DT)
                hinge = door.data.joint_pos[:, hinge_id].detach().cpu().tolist()
                for env_index, value in enumerate(hinge):
                    raw_q_trace[env_index].append(value)
                    signed = float(sign) * (value - q0[env_index])
                    signed_trace[env_index].append(signed)
                    max_progress[env_index] = max(max_progress[env_index], signed)
            for env_index, cell_id in enumerate(cells):
                rows.append(
                    {
                        "cell_id": cell_id,
                        "geometry_id": geometries[env_index]["geometry_id"],
                        "canonical_geometry": geometries[env_index],
                        "realized_params": geometries[env_index]["realized_params"],
                        "sign": sign,
                        "magnitude_nm": float(magnitude),
                        "q0_rad": q0[env_index],
                        "max_progress_rad": max_progress[env_index],
                        "raw_q_trace_rad": raw_q_trace[env_index],
                        "q_trace_rad": raw_q_trace[env_index],
                        "signed_progress_trace_rad": signed_trace[env_index],
                        "reset_closed": True,
                        "settle_steps": 1,
                        "composer_reset_before_trial": True,
                        "hinge_axis_root_frame": [0.0, 0.0, 1.0 if -1.0 < 0 else -1.0],
                        "hinge_anchor_root_frame": [0.02, 0.475, 0.0],
                        "hinge_axis_world": axis_world[env_index].detach().cpu().tolist(),
                        "hinge_anchor_world": anchor_world[env_index].detach().cpu().tolist(),
                        "body_name": panel_names[0],
                        "physics_frames": 100,
                        "dt_s": SIM_DT,
                        "door_joint_effort_target": 0.0,
                        "external_torque_authority": EXTERNAL_WRENCH_AUTHORITY,
                    }
                )
            door.permanent_wrench_composer.reset()
    bracket = classify_external_torque_bracket(rows)
    directional_opening_bracket = classify_directional_opening_bracket(rows)
    payload = artifact_payload(
        "door_external_torque_threshold",
        status="MEASURED_RAW",
        authority="HIGH_LEVEL_ARTICULATION_RUNTIME",
        external_torque_authority=EXTERNAL_WRENCH_AUTHORITY,
        source_identity=SOURCE_IDENTITY,
        probe_contract={
            "cells": list(cells),
            "single_hinge": hinge_names[0],
            "single_panel": panel_names[0],
            "magnitude_nm": list(EXTERNAL_TORQUE_MAGNITUDES_NM),
            "signs": [-1, 1],
            "settle_steps": 1,
            "physics_steps_per_trial": 100,
            "dt_s": SIM_DT,
            "door_joint_effort_target": 0.0,
            "wrench_frame": "GLOBAL",
            "composer": "Articulation.permanent_wrench_composer",
        },
        rows=rows,
        bracket=bracket,
        directional_opening_bracket=directional_opening_bracket,
        interpolation="FORBIDDEN",
        status_outcomes=("LEFT_CENSORED", "RIGHT_CENSORED", "AMBIGUOUS_NONMONOTONE", "VALID_BRACKET", "UNIDIRECTIONAL_OPENING_BRACKET"),
    )
    sim.clear_instance()
    sim.stop()
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, default=None, help="physical GPU index (maps to cuda:N)")
    parser.add_argument("--device", default=None, help="explicit IsaacLab device, e.g. cuda:0 or cpu")
    parser.add_argument("--output", "--out", dest="output", type=Path, required=True)
    parser.add_argument("--cells", default=None, help="comma-separated atlas cells, default A0,A1,...,A8")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dt", type=float, default=SIM_DT)
    parser.add_argument("--free-steps", type=int, default=FREE_RETURN_STEPS)
    parser.add_argument("--fixed-steps", type=int, default=FIXED_EFFORT_STEPS)
    parser.add_argument("--trajectory-stride", type=int, default=TRAJECTORY_STRIDE)
    parser.add_argument(
        "--fixed-efforts",
        default=",".join(str(item) for item in V23_EFFORT_RUNGS),
        help="comma-separated fixed effort targets in N*m",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="emit requested atlas rows without importing or starting IsaacLab",
    )
    parser.add_argument(
        "--external-threshold",
        action="store_true",
        help="run the one-hinge/panel external global-torque threshold probe",
    )
    return parser


def _probe_fail_fast() -> None:
    """Expose the producer traceback before Kit teardown can mask it."""

    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()
    sys.stdout.flush()
    os._exit(1)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cells = _parse_cells(args.cells)
    fixed_efforts_nm = _parse_float_list(args.fixed_efforts, name="--fixed-efforts")
    if args.external_threshold and abs(float(args.dt) - SIM_DT) > 1.0e-12:
        raise V23Error(f"--external-threshold requires --dt exactly {SIM_DT:.3f}")
    if args.plan_only:
        _validate_probe_parameters(args)
        if args.output is None:
            raise V23Error("--plan-only still requires explicit --output")
        if args.external_threshold:
            external_plan_rows = [
                {
                    "cell_id": cell_id,
                    "geometry_id": build_canonical_geometry_record(cell_id)["geometry_id"],
                    "canonical_geometry": build_canonical_geometry_record(cell_id),
                    "requested_params": dict(ATLAS_PROFILES[cell_id]),
                    "realized_params": build_canonical_geometry_record(cell_id)["realized_params"],
                    "status": "PLAN_ONLY",
                }
                for cell_id in cells
            ]
            emit_payload(
                artifact_payload(
                    "door_external_torque_threshold",
                    status="PLAN_ONLY",
                    authority="HIGH_LEVEL_ARTICULATION_RUNTIME",
                    external_torque_authority=EXTERNAL_WRENCH_AUTHORITY,
                    probe_contract={
                        "single_hinge": "PENDING_RUNTIME_RESOLUTION",
                        "single_panel": "PENDING_RUNTIME_RESOLUTION",
                        "cells": list(cells),
                        "magnitude_nm": list(EXTERNAL_TORQUE_MAGNITUDES_NM),
                        "signs": [-1, 1],
                        "settle_steps": 1,
                        "physics_steps_per_trial": 100,
                        "door_joint_effort_target": 0.0,
                        "wrench_frame": "GLOBAL",
                        "composer": "Articulation.permanent_wrench_composer",
                    },
                    rows=external_plan_rows,
                    bracket={"status": "PENDING"},
                    directional_opening_bracket={
                        "schema": DIRECTIONAL_OPENING_BRACKET_SCHEMA,
                        "status": "PENDING",
                    },
                    interpolation="FORBIDDEN",
                ),
                args.output,
            )
        else:
            emit_payload(_plan_payload(cells, fixed_efforts_nm, args), args.output)
        return 0

    device = _validate_runtime_args(args)
    from isaaclab.app import AppLauncher

    launcher = AppLauncher({"headless": True, "device": device, "enable_cameras": False})
    try:
        payload = (
            _run_external_torque_probe(cells=cells, device=device, seed=args.seed, dt=args.dt)
            if args.external_threshold
            else _run_probe(
                cells=cells,
                fixed_efforts_nm=fixed_efforts_nm,
                device=device,
                seed=args.seed,
                dt=args.dt,
                free_steps=args.free_steps,
                fixed_steps=args.fixed_steps,
                trajectory_stride=args.trajectory_stride,
            )
        )
        emit_payload(payload, args.output)
    except BaseException:
        _probe_fail_fast()
    finally:
        launcher.app.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 DOOR ATLAS PROBE FAIL: {exc}")
