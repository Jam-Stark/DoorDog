"""Fail-fast construction guard for the A2+Piper pull-v0 task."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from typing import Any

import yaml

from gr00t.rl.envs.door.a2_pull_direction import (
    A2DoorDirection,
    A2_PULL_V0_DIRECTION_CONTRACT_VERSION,
)

A2_PULL_V0_PLAN_ID = "a2_piper_pull_v0_tensile_feasibility_v1"
A2_PULL_V0_TARGET_FRAME_VERSION = "grasp_target_active_face_io_z_pre_v1"
A2_PULL_V0_TARGET_ORIENTATION_WXYZ = (-0.5, -0.5, 0.5, 0.5)
A2_PULL_V0_STAGE_TIME_BUDGET_STEPS = (250, 100, 100, 100, 100, 200)
_REPO_ROOT = Path(__file__).resolve().parents[4]
A2_PULL_V0_SOURCE_FREEZE_PATH = _REPO_ROOT / "scriptsFORhuman/pull_v0/PULL_V0_SOURCE_FREEZE.json"
A2_PULL_V0_RESOLVED_G4_CONFIG_PATH = (
    _REPO_ROOT / "scriptsFORhuman/pull_v0/source_freeze/v20_G4_resolved_config.yaml"
)
_PULL_DIRECTION = A2DoorDirection(door_open_io="in", door_open_lr="right")
_RESOLVED_V20_G4_WEIGHT_RANGE = (80.0, 160.0)

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


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{context} must be a mapping; got {type(value).__name__}.")
    return value


def _mapping_item(mapping: Mapping[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise RuntimeError(f"{context} requires {key}.")
    return mapping[key]


def _string_item(mapping: Mapping[str, Any], key: str, context: str) -> str:
    value = _mapping_item(mapping, key, context)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{context}.{key} must be a non-empty string; got {value!r}.")
    return value


def _sha256_item(mapping: Mapping[str, Any], key: str, context: str) -> str:
    value = _string_item(mapping, key, context)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise RuntimeError(f"{context}.{key} must be a lowercase sha256 digest; got {value!r}.")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_relative_file(raw_path: str, context: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise RuntimeError(f"{context} must be a repository-relative path; got {raw_path!r}.")
    resolved = (_REPO_ROOT / path).resolve()
    if not resolved.is_relative_to(_REPO_ROOT):
        raise RuntimeError(f"{context} must stay inside {_REPO_ROOT}; got {raw_path!r}.")
    if not resolved.is_file():
        raise RuntimeError(f"{context} is missing: {resolved}")
    return resolved


def _resolved_g4_source_freeze_binding(manifest_path: Path = A2_PULL_V0_SOURCE_FREEZE_PATH) -> tuple[Path, str]:
    if not manifest_path.is_file():
        raise RuntimeError(f"P0-D source-freeze manifest is missing: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = _require_mapping(payload, "P0-D source-freeze manifest")
    if _string_item(manifest, "schema", "P0-D source-freeze manifest") != "a2_piper_pull_v0_source_freeze_v1":
        raise RuntimeError("P0-D source-freeze manifest schema is not a2_piper_pull_v0_source_freeze_v1.")
    if _string_item(manifest, "plan_id", "P0-D source-freeze manifest") != A2_PULL_V0_PLAN_ID:
        raise RuntimeError(f"P0-D source-freeze manifest plan_id must be {A2_PULL_V0_PLAN_ID!r}.")
    resolved_g4 = _require_mapping(
        _mapping_item(manifest, "resolved_v20_g4_config", "P0-D source-freeze manifest"),
        "P0-D resolved_v20_g4_config source-freeze entry",
    )
    archived_copy = _repo_relative_file(
        _string_item(resolved_g4, "archived_copy", "P0-D resolved_v20_g4_config"),
        "P0-D resolved_v20_g4_config.archived_copy",
    )
    expected_sha256 = _sha256_item(resolved_g4, "archived_copy_sha256", "P0-D resolved_v20_g4_config")
    actual_sha256 = _sha256_file(archived_copy)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            "P0-D archived resolved v20 G4 config SHA mismatch: "
            f"path={archived_copy}, expected={expected_sha256}, actual={actual_sha256}."
        )
    return archived_copy, expected_sha256


def _numeric_sequence(value: Any, context: str) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RuntimeError(f"{context} must be a numeric sequence; got {value!r}.")
    if any(isinstance(item, bool) or not isinstance(item, Real) for item in value):
        raise RuntimeError(f"{context} must contain only finite numbers; got {value!r}.")
    normalized = tuple(float(item) for item in value)
    if any(not math.isfinite(item) for item in normalized):
        raise RuntimeError(f"{context} must contain only finite numbers; got {normalized!r}.")
    return normalized


def _string_sequence(value: Any, context: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RuntimeError(f"{context} must be a string sequence; got {value!r}.")
    if any(not isinstance(item, str) or not item for item in value):
        raise RuntimeError(f"{context} must contain only non-empty strings; got {value!r}.")
    return tuple(value)


def _joint_pair_from_mapping(mapping: Mapping[str, Any], context: str) -> tuple[float, float]:
    pair = (_mapping_item(mapping, "arm_j7", context), _mapping_item(mapping, "arm_j8", context))
    if any(isinstance(item, bool) or not isinstance(item, Real) for item in pair):
        raise RuntimeError(f"{context} arm_j7/arm_j8 must be finite numbers; got {pair!r}.")
    normalized = (float(pair[0]), float(pair[1]))
    if any(not math.isfinite(item) for item in normalized):
        raise RuntimeError(f"{context} arm_j7/arm_j8 must be finite; got {normalized!r}.")
    return normalized


def _load_sha_verified_resolved_g4_config(config_path: Path | None) -> tuple[Path, str, Any]:
    archived_copy, expected_sha256 = _resolved_g4_source_freeze_binding()
    path = archived_copy if config_path is None else Path(config_path).resolve()
    if path != archived_copy:
        raise RuntimeError(
            "P0-D resolved v20 G4 config must use the source-freeze archived copy: "
            f"expected={archived_copy}, got={path}."
        )
    try:
        with path.open("r", encoding="utf-8") as stream:
            payload = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        raise RuntimeError(f"P0-D resolved v20 G4 config is not valid YAML: {path}") from exc
    return path, expected_sha256, payload


def _parse_resolved_g4_config(path: Path, expected_sha256: str, payload: Any) -> dict[str, Any]:
    root = _require_mapping(payload, "P0-D resolved v20 G4 config")
    env = _require_mapping(_mapping_item(root, "env", "P0-D resolved v20 G4 config"), "P0-D env")
    env_config = _require_mapping(_mapping_item(env, "config", "P0-D env"), "P0-D env.config")
    weight_range = _numeric_sequence(
        _mapping_item(env_config, "a2_door_weight_range", "P0-D env.config"),
        "P0-D env.config.a2_door_weight_range",
    )
    if weight_range != _RESOLVED_V20_G4_WEIGHT_RANGE:
        raise RuntimeError(
            "P0-D resolved v20 G4 config must carry a2_door_weight_range "
            f"{_RESOLVED_V20_G4_WEIGHT_RANGE}; got {weight_range}."
        )

    robot = _require_mapping(_mapping_item(root, "robot", "P0-D resolved v20 G4 config"), "P0-D robot")
    dof_names = _string_sequence(_mapping_item(robot, "dof_names", "P0-D robot"), "P0-D robot.dof_names")
    effort_values = _numeric_sequence(
        _mapping_item(robot, "dof_effort_limit_list", "P0-D robot"),
        "P0-D robot.dof_effort_limit_list",
    )
    if len(dof_names) != len(effort_values):
        raise RuntimeError("P0-D resolved v20 G4 dof_names and effort limits length mismatch.")
    finger_joint_names = ("arm_j7", "arm_j8")
    if any(dof_names.count(name) != 1 for name in finger_joint_names):
        raise RuntimeError("P0-D resolved v20 G4 config requires exactly one arm_j7 and arm_j8.")
    finger_effort = tuple(effort_values[dof_names.index(name)] for name in finger_joint_names)
    control = _require_mapping(_mapping_item(robot, "control", "P0-D robot"), "P0-D robot.control")
    stiffness = _joint_pair_from_mapping(
        _require_mapping(_mapping_item(control, "stiffness", "P0-D robot.control"), "P0-D stiffness"),
        "P0-D robot.control.stiffness",
    )
    damping = _joint_pair_from_mapping(
        _require_mapping(_mapping_item(control, "damping", "P0-D robot.control"), "P0-D damping"),
        "P0-D robot.control.damping",
    )
    expected = _FINGER_PROFILES["V20_G4_45N_KP1300_KD32"]
    if finger_effort != expected["effort_n"] or stiffness != expected["stiffness"] or damping != expected["damping"]:
        raise RuntimeError(
            "P0-D resolved v20 G4 config must bind finger effort/stiffness/damping to "
            f"{expected}; got effort={finger_effort}, stiffness={stiffness}, damping={damping}."
        )
    return {
        "source_config_path": str(path),
        "source_config_sha256": expected_sha256,
        "finger_effort_n": finger_effort,
        "finger_stiffness": stiffness,
        "finger_damping": damping,
        "a2_door_weight_range": weight_range,
    }


def validate_a2_pull_v0_resolved_g4_config(
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Assert P0-D against the source-freeze archived v20 G4 run config."""

    path, expected_sha256, payload = _load_sha_verified_resolved_g4_config(config_path)
    return _parse_resolved_g4_config(path, expected_sha256, payload)


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

    resolved_g4_config = None
    if finger_profile == "V20_G4_45N_KP1300_KD32":
        resolved_g4_config = validate_a2_pull_v0_resolved_g4_config()
        expected_profile = {
            "effort_n": resolved_g4_config["finger_effort_n"],
            "stiffness": resolved_g4_config["finger_stiffness"],
            "damping": resolved_g4_config["finger_damping"],
        }
    else:
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
        "resolved_config_path": None if resolved_g4_config is None else resolved_g4_config["source_config_path"],
    }


__all__ = [
    "A2_PULL_V0_DIRECTION_CONTRACT_VERSION",
    "A2_PULL_V0_PLAN_ID",
    "A2_PULL_V0_RESOLVED_G4_CONFIG_PATH",
    "A2_PULL_V0_SOURCE_FREEZE_PATH",
    "A2_PULL_V0_STAGE_TIME_BUDGET_STEPS",
    "A2_PULL_V0_TARGET_FRAME_VERSION",
    "A2_PULL_V0_TARGET_ORIENTATION_WXYZ",
    "validate_a2_pull_v0_guard",
    "validate_a2_pull_v0_resolved_g4_config",
]
