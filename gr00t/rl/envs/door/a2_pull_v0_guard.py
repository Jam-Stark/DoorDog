"""Fail-fast construction guard for the A2+Piper pull-v0 task."""

from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Real
from typing import Any

from gr00t.rl.envs.door.a2_pull_direction import (
    A2DoorDirection,
    A2_PULL_V0_DIRECTION_CONTRACT_VERSION,
)

A2_PULL_V0_PLAN_ID = "a2_piper_pull_v0_tensile_feasibility_v1"
A2_PULL_V0_TARGET_FRAME_VERSION = "grasp_target_active_face_io_z_pre_v1"
A2_PULL_V0_TARGET_ORIENTATION_WXYZ = (-0.5, -0.5, 0.5, 0.5)
A2_PULL_V0_STAGE_TIME_BUDGET_STEPS = (250, 100, 100, 100, 100, 200)
_PULL_DIRECTION = A2DoorDirection(door_open_io="in", door_open_lr="right")

_FINGER_PROFILES = {
    "V20_G4_45N_KP1300_KD32": {
        "effort_n": (45.0, 45.0),
        "stiffness": (1300.0, 1300.0),
        "damping": (32.0, 32.0),
    },
    "P1_10N_KP1300_KD32": {
        "effort_n": (10.0, 10.0),
        "stiffness": (1300.0, 1300.0),
        "damping": (32.0, 32.0),
    },
}
_HOOK_PROFILES = frozenset(("STOCHASTIC_BASELINE", "ABSENT", "PRESENT"))
_FRICTION_PROFILES = frozenset(("RESOLVED_V20_G4", "CALIBRATED_LOW", "CALIBRATED_HIGH"))


def _required(config: Any, key: str) -> Any:
    if key not in config:
        raise RuntimeError(f"Pull-v0 construction requires env.config.{key}.")
    return config[key]


def _require_exact(config: Any, key: str, expected: Any) -> Any:
    value = _required(config, key)
    if value != expected:
        raise RuntimeError(f"env.config.{key} must be exactly {expected!r}; got {value!r}.")
    return value


def _require_exact_number(config: Any, key: str, expected: float) -> float:
    value = _required(config, key)
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        raise RuntimeError(f"env.config.{key} must be a finite number; got {value!r}.")
    value = float(value)
    if value != expected:
        raise RuntimeError(f"env.config.{key} must be exactly {expected!r}; got {value!r}.")
    return value


def _require_exact_numeric_sequence(
    config: Any,
    key: str,
    expected: tuple[float, ...],
) -> tuple[float, ...]:
    value = _required(config, key)
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RuntimeError(f"env.config.{key} must be a numeric sequence; got {value!r}.")
    if any(isinstance(item, bool) or not isinstance(item, Real) for item in value):
        raise RuntimeError(f"env.config.{key} must contain only finite numbers; got {value!r}.")
    normalized = tuple(float(item) for item in value)
    if any(not math.isfinite(item) for item in normalized) or normalized != expected:
        raise RuntimeError(f"env.config.{key} must be exactly {expected!r}; got {normalized!r}.")
    return normalized


def _normalize_profile_rows(values: Any, field_name: str) -> tuple[tuple[float, float], ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
        raise RuntimeError(f"Pull-v0 {field_name} must contain at least one two-finger row.")
    first = values[0]
    rows = (values,) if isinstance(first, Real) and not isinstance(first, bool) else values
    normalized = []
    for row in rows:
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence) or len(row) != 2:
            raise RuntimeError(f"Pull-v0 {field_name} rows must have exactly two values; got {row!r}.")
        if any(isinstance(item, bool) or not isinstance(item, Real) for item in row):
            raise RuntimeError(f"Pull-v0 {field_name} rows must be finite numeric pairs; got {row!r}.")
        pair = (float(row[0]), float(row[1]))
        if any(not math.isfinite(item) for item in pair):
            raise RuntimeError(f"Pull-v0 {field_name} rows must be finite; got {pair!r}.")
        normalized.append(pair)
    return tuple(normalized)


def _require_profile_rows(
    values: Any,
    field_name: str,
    expected: tuple[float, float],
) -> tuple[tuple[float, float], ...]:
    rows = _normalize_profile_rows(values, field_name)
    if any(row != expected for row in rows):
        raise RuntimeError(
            f"Pull-v0 {field_name} must resolve to {expected!r} in every environment; got {rows!r}."
        )
    return rows


def validate_a2_pull_v0_guard(
    config: Any,
    *,
    actual_finger_effort_n: Any,
    actual_finger_stiffness: Any,
    actual_finger_damping: Any,
) -> dict[str, Any]:
    """Validate the immutable pull-v0 construction contract before the first env step."""

    _require_exact(config, "a2_v20_R1_plan_id", A2_PULL_V0_PLAN_ID)
    _require_exact(
        config,
        "a2_pull_direction_contract_version",
        A2_PULL_V0_DIRECTION_CONTRACT_VERSION,
    )
    _require_exact(config, "a2_pull_target_frame_version", A2_PULL_V0_TARGET_FRAME_VERSION)
    _require_exact_numeric_sequence(
        config,
        "a2_pull_target_orientation_wxyz",
        A2_PULL_V0_TARGET_ORIENTATION_WXYZ,
    )
    _require_exact(config, "a2_pull_door_open_io", _PULL_DIRECTION.door_open_io)
    _require_exact(config, "a2_pull_door_open_lr", _PULL_DIRECTION.door_open_lr)
    _require_exact_number(
        config,
        "a2_pull_robot_initial_side_x_sign",
        float(_PULL_DIRECTION.approach_side_x),
    )
    _require_exact_number(config, "a2_pull_robot_initial_yaw_rad", math.pi)
    _require_exact_number(
        config,
        "a2_pull_active_handle_face_x_sign",
        float(_PULL_DIRECTION.active_handle_face_x),
    )
    _require_exact_number(
        config,
        "a2_pull_travel_dir_x",
        float(_PULL_DIRECTION.travel_dir_x),
    )
    _require_exact_numeric_sequence(
        config,
        "target_root_pos",
        (_PULL_DIRECTION.final_target_x(0.0, 2.0), 0.0, 0.5),
    )
    _require_exact_numeric_sequence(
        config,
        "max_stage_time",
        tuple(float(item) for item in A2_PULL_V0_STAGE_TIME_BUDGET_STEPS),
    )
    _require_exact(config, "a2_pull_threshold_mode", "report_only")
    _require_exact(config, "a2_pull_effort_provenance", "ESTIMATE_ONLY")
    _require_exact(config, "a2_pull_add_walls", False)

    hook_profile = _required(config, "a2_pull_hook_profile")
    if hook_profile not in _HOOK_PROFILES:
        raise RuntimeError(
            f"env.config.a2_pull_hook_profile must be one of {sorted(_HOOK_PROFILES)}; "
            f"got {hook_profile!r}."
        )
    friction_profile = _required(config, "a2_pull_friction_profile")
    if friction_profile not in _FRICTION_PROFILES:
        raise RuntimeError(
            f"env.config.a2_pull_friction_profile must be one of {sorted(_FRICTION_PROFILES)}; "
            f"got {friction_profile!r}."
        )
    finger_profile = _required(config, "a2_pull_finger_profile")
    if finger_profile not in _FINGER_PROFILES:
        raise RuntimeError(
            f"env.config.a2_pull_finger_profile must be one of {sorted(_FINGER_PROFILES)}; "
            f"got {finger_profile!r}."
        )

    for key, expected in (
        ("a2_v20_R1_send_curriculum_enabled", False),
        ("a2_v20_R1_snapshot_guard_enabled", False),
        ("a2_v20_send_latch_enabled", False),
        ("a2_v20_pre_send_crossing_mode", "disabled"),
        ("a2_v20_telemetry_enabled", False),
        ("a2_v20_traversal_economics_enabled", False),
        ("a2_v20_arm_tie_enabled", False),
        ("a2_corridor_enabled", False),
        ("a2_corridor_latch_mode", "legacy_root_or_hinge"),
        ("a2_v20_R2_evidence_enabled", False),
        ("a2_v20_formal_launch", False),
    ):
        _require_exact(config, key, expected)
    _require_exact_number(config, "a2_v20_arm_tangent_carry_scale", 0.0)
    _require_exact_number(config, "a2_v20_handle_arc_tracking_scale", 0.0)

    expected_profile = _FINGER_PROFILES[finger_profile]
    effort_rows = _require_profile_rows(
        actual_finger_effort_n,
        "finger effort",
        expected_profile["effort_n"],
    )
    stiffness_rows = _require_profile_rows(
        actual_finger_stiffness,
        "finger stiffness",
        expected_profile["stiffness"],
    )
    damping_rows = _require_profile_rows(
        actual_finger_damping,
        "finger damping",
        expected_profile["damping"],
    )
    if not (len(effort_rows) == len(stiffness_rows) == len(damping_rows)):
        raise RuntimeError("Pull-v0 resolved finger profile row counts disagree.")

    return {
        "plan_id": A2_PULL_V0_PLAN_ID,
        "direction_contract_version": A2_PULL_V0_DIRECTION_CONTRACT_VERSION,
        "target_frame_version": A2_PULL_V0_TARGET_FRAME_VERSION,
        "target_orientation_wxyz": A2_PULL_V0_TARGET_ORIENTATION_WXYZ,
        "io": _PULL_DIRECTION.door_open_io,
        "lr": _PULL_DIRECTION.door_open_lr,
        "finger_profile": finger_profile,
        "hook_profile": hook_profile,
        "friction_profile": friction_profile,
        "num_profile_rows": len(effort_rows),
        "threshold_mode": "report_only",
        "effort_provenance": "ESTIMATE_ONLY",
    }


__all__ = [
    "A2_PULL_V0_DIRECTION_CONTRACT_VERSION",
    "A2_PULL_V0_PLAN_ID",
    "A2_PULL_V0_STAGE_TIME_BUDGET_STEPS",
    "A2_PULL_V0_TARGET_FRAME_VERSION",
    "A2_PULL_V0_TARGET_ORIENTATION_WXYZ",
    "validate_a2_pull_v0_guard",
]
