"""Strict v18 M39 combined zero-shot probe reporter.

This reporter consumes one complete 16-environment evaluation directory.  It
does not discover alternative filenames or infer omitted values.  Result and
first-episode trace records, the effective Hydra configuration, and the
high-level runtime material provenance are all required before any admission
gate is evaluated.

The four zero-shot admission gates are deliberately small and explicit:

* at least 15/16 terminal goals;
* at least 99 percent bilateral contact before root-X crossing;
* less than 2 percent over-force in that same pre-crossing scope; and
* exactly zero stage-3/4 raw gripper-action sign-flip frames (a chatter proxy).

P1 slip reduction is reported as out of scope for this zero-shot admission;
the reporter never claims a spectrum or a slip result when that evidence is
not present.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

import yaml


SCHEMA: Final = "a2_piper_v18_m39_combined_zero_shot_report_v1"
EXPECTED_ENV_IDS: Final = set(range(16))
EXPECTED_ENV_COUNT: Final = 16
RESULT_FILENAME: Final = "a2_v14_per_env_records.json"
TRACE_FILENAME: Final = "stage2_5_step_trace.json"
DIAGNOSTIC_METADATA_FILENAME: Final = "a2_eval_diagnostic_metadata.json"
RUNTIME_METADATA_FILENAME: Final = "a2_hold_diagnostic_runtime_metadata.json"
EXIT_FILENAME: Final = "eval_exit_code.txt"
CONFIG_FILENAME: Final = ".hydra/config.yaml"
MATERIAL_SCHEMA: Final = "a2_m39_gripper_material_v1"
MATERIAL_EVENT_FUNCTION: Final = (
    "isaaclab.envs.mdp.events.randomize_rigid_body_material"
)
MATERIAL_SELECTOR_PATH: Final = "env.config.a2_m39_gripper_material_enabled"
EXPECTED_STATIC_FRICTION: Final = 1.1
EXPECTED_DYNAMIC_FRICTION: Final = 0.9
EXPECTED_RESTITUTION: Final = 0.0
EXPECTED_POST_MATERIAL_FLOAT32: Final = tuple(
    struct.unpack("<f", struct.pack("<f", value))[0]
    for value in (
        EXPECTED_STATIC_FRICTION, EXPECTED_DYNAMIC_FRICTION, EXPECTED_RESTITUTION
    )
)
EXPECTED_EFFORT_LIMIT: Final = 45.0
EXPECTED_STIFFNESS: Final = 1300.0
EXPECTED_DAMPING: Final = 32.0
EXPECTED_SQUEEZE_MAX: Final = 30.0
EXPECTED_OVER_FORCE_THRESHOLD: Final = 55.0
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
LOWER_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HANDLE_ENV0_PATH_RE = re.compile(r"^/World/envs/env_0(?:/[^/]+)+/door_handle$")
EXPECTED_HANDLE_SCOPE: Final = "exact_target_rigid_body_view_all_envs"


class CombinedProbeReportError(ValueError):
    """Malformed, incomplete, or failing M39 evidence."""


@dataclass(frozen=True, slots=True)
class EvalRecord:
    seed: int
    env_id: int
    goal_reached: bool
    max_stage: int | None
    final_stage: int | None
    hinge_force: float
    handle_height: float
    door_weight: float
    staging_standoff: float
    crossing_while_holding: bool | None
    hinge_at_crossing: float | None
    hinge_at_release: float | None
    root_x_at_release: float | None
    post_release_body_contact: bool | None
    post_release_body_force_max: float | None


@dataclass(frozen=True, slots=True)
class TraceRecord:
    env_id: int
    stage: int
    step_index: int
    episode_length_buf: int
    control_dt: float
    door_hinge_drive_max_force: float
    door_handle_height: float
    door_weight: float
    both_contact: bool
    over_force: bool
    root_x_ever_crossed: bool
    stage3_stage4_gripper_raw_sign_flip: bool
    terminal_reasons: str
    root_pos_rel: tuple[float, float, float]
    reward_episode_sums: Mapping[str, float]


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _finite_float(value: Any, field: str) -> float:
    if not _finite(value):
        raise CombinedProbeReportError(f"{field} must be a finite number; got {value!r}.")
    return float(value)


def _required(raw: Mapping[str, Any], name: str) -> Any:
    if name not in raw or raw[name] is None:
        raise CombinedProbeReportError(f"record is missing required field {name!r}.")
    return raw[name]


def _bool(raw: Mapping[str, Any], name: str) -> bool:
    value = _required(raw, name)
    if not isinstance(value, bool):
        raise CombinedProbeReportError(f"{name} must be bool; got {value!r}.")
    return value


def _nullable_bool(raw: Mapping[str, Any], name: str) -> bool | None:
    if name not in raw:
        raise CombinedProbeReportError(f"record is missing required field {name!r}.")
    value = raw[name]
    if value is not None and not isinstance(value, bool):
        raise CombinedProbeReportError(f"{name} must be bool or null; got {value!r}.")
    return value


def _nullable_float(raw: Mapping[str, Any], name: str) -> float | None:
    if name not in raw:
        raise CombinedProbeReportError(f"record is missing required field {name!r}.")
    value = raw[name]
    if value is None:
        return None
    return _finite_float(value, name)


def _stage(raw: Mapping[str, Any], name: str) -> int | None:
    if name not in raw:
        raise CombinedProbeReportError(f"record is missing required field {name!r}.")
    value = raw[name]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5:
        raise CombinedProbeReportError(
            f"{name} must be an integer stage in [0,5] or null; got {value!r}."
        )
    return value


def _vector3(value: Any, field: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise CombinedProbeReportError(f"{field} must contain exactly three values; got {value!r}.")
    return tuple(_finite_float(component, f"{field}[{index}]") for index, component in enumerate(value))


def _reward_sums(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise CombinedProbeReportError("reward_episode_sums must be a non-empty mapping.")
    if any(not isinstance(key, str) or not key for key in value):
        raise CombinedProbeReportError("reward_episode_sums keys must be non-empty strings.")
    return {key: _finite_float(component, f"reward_episode_sums[{key!r}]") for key, component in value.items()}


def _load_json(path: Path, label: str) -> Any:
    if not path.is_file():
        raise CombinedProbeReportError(f"required {label} does not exist: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CombinedProbeReportError(f"cannot read {label} {path}: {exc}") from exc


def _records(payload: Any, path: Path) -> list[Mapping[str, Any]]:
    if not isinstance(payload, list):
        raise CombinedProbeReportError(f"{path} must contain a JSON list of records.")
    if any(not isinstance(row, Mapping) for row in payload):
        raise CombinedProbeReportError(f"{path} contains a non-object record.")
    return list(payload)


def normalize_result(raw: Mapping[str, Any]) -> EvalRecord:
    seed = _required(raw, "seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed != 0:
        raise CombinedProbeReportError(f"result seed identity must be 0; got {seed!r}.")
    env_id = _required(raw, "env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in EXPECTED_ENV_IDS:
        raise CombinedProbeReportError(f"result env_id must be an integer in 0..15; got {env_id!r}.")
    goal = _bool(raw, "goal_reached")
    max_stage = _stage(raw, "max_stage")
    final_stage = _stage(raw, "final_stage")
    if max_stage is None and final_stage is None:
        raise CombinedProbeReportError(f"env{env_id} result requires max_stage or final_stage.")
    if max_stage is not None and final_stage is not None and final_stage > max_stage:
        raise CombinedProbeReportError(f"env{env_id} final_stage cannot exceed max_stage.")
    hinge_force = _finite_float(_required(raw, "door_hinge_drive_max_force"), "door_hinge_drive_max_force")
    handle_height = _finite_float(_required(raw, "door_handle_height"), "door_handle_height")
    door_weight = _finite_float(_required(raw, "door_weight"), "door_weight")
    standoff = _finite_float(_required(raw, "stage0_to1_staging_standoff"), "stage0_to1_staging_standoff")
    if not 2.5 <= hinge_force <= 12.0:
        raise CombinedProbeReportError(f"door_hinge_drive_max_force must be in [2.5,12]; got {hinge_force!r}.")
    if not 0.80 <= handle_height <= 1.10 + 1.0e-7:
        raise CombinedProbeReportError(f"door_handle_height must be in [0.80,1.10]; got {handle_height!r}.")
    if not 80.0 <= door_weight <= 160.0:
        raise CombinedProbeReportError(f"door_weight must be in [80,160]; got {door_weight!r}.")
    crossing = _nullable_bool(raw, "crossing_while_holding")
    hinge_crossing = _nullable_float(raw, "hinge_at_crossing")
    if (crossing is None) != (hinge_crossing is None):
        raise CombinedProbeReportError("crossing_while_holding and hinge_at_crossing must be both null or both non-null.")
    release_fields = (
        _nullable_float(raw, "hinge_at_release"),
        _nullable_float(raw, "root_x_at_release"),
        _nullable_bool(raw, "post_release_body_contact"),
        _nullable_float(raw, "post_release_body_force_max"),
    )
    if any(value is None for value in release_fields) != all(value is None for value in release_fields):
        raise CombinedProbeReportError("release telemetry fields must be all null or all non-null.")
    if release_fields[3] is not None and release_fields[3] < 0.0:
        raise CombinedProbeReportError("post_release_body_force_max must be non-negative.")
    if goal and (crossing is None or release_fields[0] is None):
        raise CombinedProbeReportError(
            f"env{env_id} goal_reached=true requires non-null crossing and release telemetry."
        )
    return EvalRecord(
        seed=0,
        env_id=env_id,
        goal_reached=goal,
        max_stage=max_stage,
        final_stage=final_stage,
        hinge_force=hinge_force,
        handle_height=handle_height,
        door_weight=door_weight,
        staging_standoff=standoff,
        crossing_while_holding=crossing,
        hinge_at_crossing=hinge_crossing,
        hinge_at_release=release_fields[0],
        root_x_at_release=release_fields[1],
        post_release_body_contact=release_fields[2],
        post_release_body_force_max=release_fields[3],
    )


def load_results(eval_dir: Path) -> list[EvalRecord]:
    path = eval_dir / RESULT_FILENAME
    raw_records = _records(_load_json(path, "result artifact"), path)
    if len(raw_records) != EXPECTED_ENV_COUNT:
        raise CombinedProbeReportError(f"result artifact must contain exactly 16 records; got {len(raw_records)}.")
    records = [normalize_result(raw) for raw in raw_records]
    ids = [record.env_id for record in records]
    if set(ids) != EXPECTED_ENV_IDS or len(set(ids)) != EXPECTED_ENV_COUNT:
        raise CombinedProbeReportError(f"result artifact requires unique env_id 0..15; got {sorted(ids)}.")
    return sorted(records, key=lambda record: record.env_id)


def normalize_trace(raw: Mapping[str, Any], result_by_env: Mapping[int, EvalRecord]) -> TraceRecord:
    active = _required(raw, "first_episode_active")
    if active is not True:
        raise CombinedProbeReportError(f"trace env{raw.get('env_id')!r} requires first_episode_active=true; got {active!r}.")
    episode_index = _required(raw, "episode_index")
    if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index != 0:
        raise CombinedProbeReportError(f"trace episode_index must be 0 for the first episode; got {episode_index!r}.")
    env_id = _required(raw, "env_id")
    if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in result_by_env:
        raise CombinedProbeReportError(f"trace env_id must identify result env 0..15; got {env_id!r}.")
    if "seed" in raw and raw["seed"] != 0:
        raise CombinedProbeReportError(f"trace env{env_id} seed identity must be 0; got {raw['seed']!r}.")
    stage = _required(raw, "stage_buf")
    if isinstance(stage, bool) or not isinstance(stage, int) or stage not in {2, 3, 4, 5}:
        raise CombinedProbeReportError(f"trace env{env_id} stage_buf must be integer 2..5; got {stage!r}.")
    step_index = _required(raw, "step_index")
    if isinstance(step_index, bool) or not isinstance(step_index, int) or step_index < 0:
        raise CombinedProbeReportError(f"trace env{env_id} step_index must be a non-negative int; got {step_index!r}.")
    episode_length = _required(raw, "episode_length_buf")
    if isinstance(episode_length, bool) or not isinstance(episode_length, int) or episode_length <= 0:
        raise CombinedProbeReportError(f"trace env{env_id} episode_length_buf must be a positive int; got {episode_length!r}.")
    control_dt = _finite_float(_required(raw, "control_dt"), "control_dt")
    if control_dt <= 0.0:
        raise CombinedProbeReportError(f"trace env{env_id} control_dt must be positive; got {control_dt!r}.")
    result = result_by_env[env_id]
    trace_hinge = _finite_float(_required(raw, "door_hinge_drive_max_force"), "trace door_hinge_drive_max_force")
    trace_height = _finite_float(_required(raw, "door_handle_height"), "trace door_handle_height")
    trace_weight = _finite_float(_required(raw, "door_weight"), "trace door_weight")
    if trace_hinge != result.hinge_force or trace_height != result.handle_height or trace_weight != result.door_weight:
        raise CombinedProbeReportError(f"trace env{env_id} metadata must exactly match its result record.")
    terminal = _required(raw, "terminal_reasons")
    if not isinstance(terminal, str) or not terminal:
        raise CombinedProbeReportError(f"trace env{env_id} terminal_reasons must be a non-empty string; got {terminal!r}.")
    return TraceRecord(
        env_id=env_id,
        stage=stage,
        step_index=step_index,
        episode_length_buf=episode_length,
        control_dt=control_dt,
        door_hinge_drive_max_force=trace_hinge,
        door_handle_height=trace_height,
        door_weight=trace_weight,
        both_contact=_bool(raw, "both_contact"),
        over_force=_bool(raw, "over_force"),
        root_x_ever_crossed=_bool(raw, "root_x_ever_crossed"),
        stage3_stage4_gripper_raw_sign_flip=_bool(raw, "stage3_stage4_gripper_raw_sign_flip"),
        terminal_reasons=terminal,
        root_pos_rel=_vector3(_required(raw, "root_pos_rel"), "root_pos_rel"),
        reward_episode_sums=_reward_sums(_required(raw, "reward_episode_sums")),
    )


def load_trace(eval_dir: Path, results: Sequence[EvalRecord]) -> dict[int, list[TraceRecord]]:
    path = eval_dir / TRACE_FILENAME
    raw_rows = _records(_load_json(path, "trace artifact"), path)
    result_by_env = {record.env_id: record for record in results}
    grouped: dict[int, list[TraceRecord]] = {env_id: [] for env_id in EXPECTED_ENV_IDS}
    for raw in raw_rows:
        row = normalize_trace(raw, result_by_env)
        grouped[row.env_id].append(row)
    for env_id, rows in grouped.items():
        if not rows:
            raise CombinedProbeReportError(f"trace artifact is missing env{env_id} first-episode rows.")
        if rows[0].stage != 2:
            raise CombinedProbeReportError(f"trace env{env_id} must start at stage2; got {rows[0].stage}.")
        for previous, current in zip(rows, rows[1:]):
            if current.step_index != previous.step_index + 1:
                raise CombinedProbeReportError(f"trace env{env_id} step_index must be unique, ordered, and contiguous.")
            if current.episode_length_buf != previous.episode_length_buf + 1:
                raise CombinedProbeReportError(f"trace env{env_id} episode_length_buf must be unique, ordered, and contiguous.")
        if rows[-1].terminal_reasons == "unknown_reset":
            raise CombinedProbeReportError(f"trace env{env_id} is missing terminal evidence at its final row.")
    return grouped


def _nested(mapping: Mapping[str, Any], *names: str) -> Any:
    value: Any = mapping
    for name in names:
        if not isinstance(value, Mapping) or name not in value or value[name] is None:
            raise CombinedProbeReportError(f"effective config is missing required path {'.'.join(names)!r}.")
        value = value[name]
    return value


def load_effective_config(eval_dir: Path) -> dict[str, Any]:
    path = eval_dir / CONFIG_FILENAME
    if not path.is_file():
        raise CombinedProbeReportError(f"required effective Hydra config does not exist: {path}")
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CombinedProbeReportError(f"cannot read effective Hydra config {path}: {exc}") from exc
    if not isinstance(config, Mapping):
        raise CombinedProbeReportError("effective Hydra config must be a mapping.")
    num_envs = _nested(config, "num_envs")
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs != EXPECTED_ENV_COUNT:
        raise CombinedProbeReportError(f"effective config num_envs must be 16; got {num_envs!r}.")
    if _nested(
        config,
        "algo",
        "config",
        "eval",
        "a2_eval_m41_strict_telemetry",
    ) is not True:
        raise CombinedProbeReportError(
            "effective config must enable "
            "algo.config.eval.a2_eval_m41_strict_telemetry=true."
        )
    env_config = _nested(config, "env", "config")
    if _nested(env_config, "a2_m39_gripper_material_enabled") is not True:
        raise CombinedProbeReportError(
            "effective config must enable env.config.a2_m39_gripper_material_enabled=true."
        )
    if _nested(env_config, "a2_hold_diagnostic_contact_detail_enabled") is not True:
        raise CombinedProbeReportError("effective config must enable a2_hold_diagnostic_contact_detail_enabled=true.")
    checks = {
        "a2_stage2_squeeze_force_max": EXPECTED_SQUEEZE_MAX,
        "a2_stage2_over_force_threshold": EXPECTED_OVER_FORCE_THRESHOLD,
    }
    for name, expected in checks.items():
        value = _finite_float(_nested(env_config, name), f"env.config.{name}")
        if value != expected:
            raise CombinedProbeReportError(f"env.config.{name} must be {expected}; got {value}.")
    stiffness = _nested(config, "robot", "control", "stiffness")
    damping = _nested(config, "robot", "control", "damping")
    for field, values, expected in (
        ("stiffness", stiffness, EXPECTED_STIFFNESS),
        ("damping", damping, EXPECTED_DAMPING),
    ):
        for joint in ("arm_j7", "arm_j8"):
            value = _finite_float(_nested(values, joint), f"robot.control.{field}.{joint}")
            if value != expected:
                raise CombinedProbeReportError(f"robot.control.{field}.{joint} must be {expected}; got {value}.")
    effort = _nested(config, "robot", "dof_effort_limit_list")
    if not isinstance(effort, list) or len(effort) != 20:
        raise CombinedProbeReportError("robot.dof_effort_limit_list must contain exactly 20 entries in canonical joint layout.")
    effort_values = [_finite_float(value, f"robot.dof_effort_limit_list[{index}]") for index, value in enumerate(effort)]
    if effort_values[-2:] != [EXPECTED_EFFORT_LIMIT, EXPECTED_EFFORT_LIMIT]:
        raise CombinedProbeReportError("robot.dof_effort_limit_list final arm_j7/arm_j8 entries must both be 45.0.")
    return {
        "path": str(path),
        "num_envs": num_envs,
        "robot_dof_effort_limit_list": effort_values,
        "arm_j7_j8_stiffness": [EXPECTED_STIFFNESS, EXPECTED_STIFFNESS],
        "arm_j7_j8_damping": [EXPECTED_DAMPING, EXPECTED_DAMPING],
        "squeeze_force_max_n": EXPECTED_SQUEEZE_MAX,
        "over_force_threshold_n": EXPECTED_OVER_FORCE_THRESHOLD,
        "m39_gripper_material_enabled": True,
        "contact_detail_enabled": True,
        "m41_strict_telemetry": True,
    }


def _summary(payload: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise CombinedProbeReportError(f"{label} must be a mapping.")
    required = ("shape", "min", "max", "unique", "sha256")
    missing = [name for name in required if name not in payload]
    if missing:
        raise CombinedProbeReportError(f"{label} is missing summary fields {missing}.")
    shape = payload["shape"]
    if not isinstance(shape, list) or not shape or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in shape):
        raise CombinedProbeReportError(f"{label}.shape must be a non-empty list of positive ints.")
    if not isinstance(payload["sha256"], str) or SHA256_RE.fullmatch(payload["sha256"]) is None:
        raise CombinedProbeReportError(f"{label}.sha256 must be a 64-character hex digest.")
    for name in ("min", "max", "unique"):
        if not isinstance(payload[name], (list, tuple, int, float)):
            raise CombinedProbeReportError(f"{label}.{name} must be numeric or a numeric list.")
    return payload


def _contains_triplet(value: Any, expected: Sequence[float]) -> bool:
    if isinstance(value, (list, tuple)):
        if len(value) == len(expected) and all(_finite(item) for item in value):
            if all(float(item) == float(want) for item, want in zip(value, expected)):
                return True
        return any(_contains_triplet(item, expected) for item in value)
    if isinstance(value, Mapping):
        return any(_contains_triplet(item, expected) for item in value.values())
    return False


def _material_body(raw: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    body_path = raw.get("body_path")
    if not isinstance(body_path, str) or not body_path:
        raise CombinedProbeReportError(f"m39 material {name}.body_path must be a non-empty string.")
    count = raw.get("shape_count")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise CombinedProbeReportError(f"m39 material {name}.shape_count must be a positive int.")
    pre = _summary(raw.get("pre"), f"m39 material {name}.pre")
    post = _summary(raw.get("post"), f"m39 material {name}.post")
    return {"body_path": body_path, "shape_count": count, "pre": pre, "post": post}


def _material_handle(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    if raw.get("unchanged") is not True:
        raise CombinedProbeReportError("m39 handle provenance must set unchanged=true.")
    if raw.get("scope") != EXPECTED_HANDLE_SCOPE:
        raise CombinedProbeReportError(
            "m39 handle scope must be exact_target_rigid_body_view_all_envs."
        )
    evidence_scope = raw.get("evidence_scope")
    if evidence_scope != EXPECTED_HANDLE_SCOPE:
        raise CombinedProbeReportError(
            "m39 handle evidence_scope must be exact_target_rigid_body_view_all_envs."
        )
    view_count = raw.get("view_count")
    if isinstance(view_count, bool) or not isinstance(view_count, int) or view_count != EXPECTED_ENV_COUNT:
        raise CombinedProbeReportError(
            f"m39 handle view_count must be {EXPECTED_ENV_COUNT}; got {view_count!r}."
        )
    prim_paths_sha256 = raw.get("prim_paths_sha256")
    if not isinstance(prim_paths_sha256, str) or LOWER_SHA256_RE.fullmatch(prim_paths_sha256) is None:
        raise CombinedProbeReportError(
            "m39 handle prim_paths_sha256 must be a lowercase 64-character hex digest."
        )
    handle_body = _material_body(raw, "handle")
    target_body = raw.get("target_body")
    if target_body != "door_handle":
        raise CombinedProbeReportError("m39 handle target_body must be door_handle.")
    target_path = raw.get("target_path")
    if target_path != handle_body["body_path"]:
        raise CombinedProbeReportError("m39 handle target_path must equal body_path.")
    if HANDLE_ENV0_PATH_RE.fullmatch(target_path) is None:
        raise CombinedProbeReportError(
            "m39 handle body_path/target_path must identify exact "
            "/World/envs/env_0/.../door_handle provenance."
        )
    prim_paths = sorted(
        target_path.replace("/env_0/", f"/env_{env_id}/", 1)
        for env_id in EXPECTED_ENV_IDS
    )
    expected_prim_paths_sha256 = sha256(
        "\n".join(prim_paths).encode("utf-8")
    ).hexdigest()
    if prim_paths_sha256 != expected_prim_paths_sha256:
        raise CombinedProbeReportError(
            "m39 handle prim_paths_sha256 does not match the canonical "
            "env0..15 target paths."
        )
    expected_summary_shape = [view_count, handle_body["shape_count"], 3]
    for label in ("pre", "post"):
        if handle_body[label]["shape"] != expected_summary_shape:
            raise CombinedProbeReportError(
                f"m39 handle {label}.shape must be {expected_summary_shape}; "
                f"got {handle_body[label]['shape']!r}."
            )
    if handle_body["pre"] != handle_body["post"]:
        raise CombinedProbeReportError("m39 handle pre/post material summaries must be identical.")
    return {
        **handle_body,
        "scope": EXPECTED_HANDLE_SCOPE,
        "target_path": target_path,
        "target_body": target_body,
        "evidence_scope": evidence_scope,
        "view_count": view_count,
        "prim_paths_sha256": prim_paths_sha256,
        "unchanged": True,
    }


def load_material_provenance(eval_dir: Path) -> dict[str, Any]:
    path = eval_dir / RUNTIME_METADATA_FILENAME
    payload = _load_json(path, "runtime material metadata")
    if not isinstance(payload, Mapping) or "m39_gripper_material" not in payload:
        raise CombinedProbeReportError("runtime metadata must contain the exact m39_gripper_material key.")
    raw = payload["m39_gripper_material"]
    if not isinstance(raw, Mapping) or raw.get("schema") != MATERIAL_SCHEMA:
        raise CombinedProbeReportError(f"m39_gripper_material.schema must be {MATERIAL_SCHEMA!r}.")
    if raw.get("selector_enabled") is not True or raw.get("all_envs") is not True:
        raise CombinedProbeReportError("m39 material selector_enabled and all_envs must both be true.")
    event = raw.get("event_term")
    if not isinstance(event, Mapping):
        raise CombinedProbeReportError("m39_gripper_material.event_term is required.")
    expected_event = {
        "function": MATERIAL_EVENT_FUNCTION,
        "mode": "startup",
        "asset": "robot",
        "target_bodies": ["arm_body7", "arm_body8"],
        "static_friction_range": [EXPECTED_STATIC_FRICTION, EXPECTED_STATIC_FRICTION],
        "dynamic_friction_range": [EXPECTED_DYNAMIC_FRICTION, EXPECTED_DYNAMIC_FRICTION],
        "restitution_range": [EXPECTED_RESTITUTION, EXPECTED_RESTITUTION],
        "num_buckets": 1,
        "make_consistent": True,
    }
    for key, expected in expected_event.items():
        if event.get(key) != expected:
            raise CombinedProbeReportError(f"m39 event_term.{key} has wrong or missing value: got {event.get(key)!r}.")
    fingers = raw.get("finger_bodies")
    if not isinstance(fingers, Mapping) or set(fingers) != {"arm_body7", "arm_body8"}:
        raise CombinedProbeReportError("m39 finger_bodies must contain exactly arm_body7 and arm_body8.")
    normalized_fingers: dict[str, Any] = {}
    for name in ("arm_body7", "arm_body8"):
        body = _material_body(fingers[name], name)
        if (
            not _contains_triplet(body["post"]["min"], EXPECTED_POST_MATERIAL_FLOAT32)
            or not _contains_triplet(body["post"]["max"], EXPECTED_POST_MATERIAL_FLOAT32)
        ):
            raise CombinedProbeReportError(
                f"m39 material {name}.post must show the exact float32 representation "
                f"{list(EXPECTED_POST_MATERIAL_FLOAT32)} of configured [1.1,0.9,0.0]."
            )
        normalized_fingers[name] = body
    handle = raw.get("handle")
    if not isinstance(handle, Mapping):
        raise CombinedProbeReportError("m39 handle provenance must be a mapping.")
    handle_record = _material_handle(handle)
    return {
        "schema": raw["schema"],
        "selector_enabled": True,
        "all_envs": True,
        "event_term": dict(event),
        "finger_bodies": normalized_fingers,
        "handle": handle_record,
        "source_file": str(path),
    }


def load_diagnostic_metadata(eval_dir: Path) -> dict[str, Any]:
    path = eval_dir / DIAGNOSTIC_METADATA_FILENAME
    payload = _load_json(path, "diagnostic metadata")
    if not isinstance(payload, Mapping):
        raise CombinedProbeReportError("diagnostic metadata must be a JSON object.")
    if payload.get("diagnostic_trace_enabled") is not True:
        raise CombinedProbeReportError("diagnostic metadata must enable diagnostic_trace_enabled=true.")
    if payload.get("m41_strict_telemetry") is not True:
        raise CombinedProbeReportError(
            "diagnostic metadata must prove m41_strict_telemetry=true."
        )
    if payload.get("forced_gripper_close_enabled") is not False:
        raise CombinedProbeReportError("combined zero-shot probe must have forced_gripper_close_enabled=false.")
    layout = payload.get("canonical_high_level_action_layout")
    if not isinstance(layout, Mapping) or layout.get("dim") != 12 or layout.get("gripper_index") != 11:
        raise CombinedProbeReportError("diagnostic metadata has missing/wrong canonical high-level action layout.")
    if not isinstance(payload.get("trace_timing"), Mapping) or not payload["trace_timing"]:
        raise CombinedProbeReportError("diagnostic metadata trace_timing schema is missing or empty.")
    if not isinstance(payload.get("first_episode_contract"), str) or not payload["first_episode_contract"]:
        raise CombinedProbeReportError("diagnostic metadata first_episode_contract is missing.")
    return {
        "source_file": str(path),
        "diagnostic_trace_enabled": True,
        "m41_strict_telemetry": True,
        "forced_gripper_close_enabled": False,
    }


def _load_exit_code(eval_dir: Path) -> int:
    path = eval_dir / EXIT_FILENAME
    if not path.is_file():
        raise CombinedProbeReportError(f"required eval exit artifact does not exist: {path}")
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise CombinedProbeReportError(f"cannot read eval exit artifact {path}: {exc}") from exc
    if text != "0":
        raise CombinedProbeReportError(f"eval_exit_code must be exactly 0; got {text!r}.")
    return 0


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        raise CombinedProbeReportError(f"invalid gate rate {numerator}/{denominator}.")
    return {"numerator": numerator, "denominator": denominator, "rate": numerator / denominator}


def build_report(eval_dir: Path) -> dict[str, Any]:
    eval_dir = eval_dir.expanduser()
    if not eval_dir.is_dir():
        raise CombinedProbeReportError(f"eval directory does not exist: {eval_dir}")
    exit_code = _load_exit_code(eval_dir)
    results = load_results(eval_dir)
    traces = load_trace(eval_dir, results)
    diagnostic = load_diagnostic_metadata(eval_dir)
    config = load_effective_config(eval_dir)
    material = load_material_provenance(eval_dir)
    all_traces = [row for env_rows in traces.values() for row in env_rows]
    pre_crossing = [row for row in all_traces if row.stage in (3, 4) and not row.root_x_ever_crossed]
    if not pre_crossing:
        raise CombinedProbeReportError("pre-crossing stage3/4 trace evidence is empty.")
    bilateral_count = sum(row.both_contact for row in pre_crossing)
    over_force_count = sum(row.over_force for row in pre_crossing)
    sign_flip_rows = [row for row in all_traces if row.stage in (3, 4)]
    sign_flip_count = sum(row.stage3_stage4_gripper_raw_sign_flip for row in sign_flip_rows)
    gates = {
        "goal": {**_rate(sum(record.goal_reached for record in results), len(results)), "threshold": "numerator >= 15 of 16"},
        "pre_crossing_bilateral_contact": {**_rate(bilateral_count, len(pre_crossing)), "threshold": "rate >= 0.99"},
        "pre_crossing_over_force": {**_rate(over_force_count, len(pre_crossing)), "threshold": "rate < 0.02"},
        "stage3_stage4_raw_gripper_action_sign_flip": {"count": sign_flip_count, "denominator": len(sign_flip_rows), "threshold": "count == 0", "proxy": "current chatter proxy; not a velocity spectrum"},
    }
    gates_pass = (
        gates["goal"]["numerator"] >= 15
        and gates["pre_crossing_bilateral_contact"]["rate"] >= 0.99
        and gates["pre_crossing_over_force"]["rate"] < 0.02
        and gates["stage3_stage4_raw_gripper_action_sign_flip"]["count"] == 0
    )
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "eval_dir": str(eval_dir),
        "eval_exit_code": exit_code,
        "topology": {
            "env_count": EXPECTED_ENV_COUNT,
            "env_ids": sorted(EXPECTED_ENV_IDS),
            "result_record_count": len(results),
            "trace_record_count": len(all_traces),
            "first_episode_only": True,
        },
        "gates": gates,
        "admission": {"all_four_gates_pass": gates_pass, "status": "PASS" if gates_pass else "FAIL"},
        "p1_slip_reduction": {"status": "NOT_AN_ADMISSION_GATE", "note": "P1 slip reduction is intentionally excluded from this zero-shot admission; no spectrum is claimed."},
        "provenance": {"config": config, "diagnostic_metadata": diagnostic, "m39_gripper_material": material},
        "records": [record.__dict__ if hasattr(record, "__dict__") else {"seed": record.seed, "env_id": record.env_id, "goal_reached": record.goal_reached} for record in results],
    }


def write_outputs(report: Mapping[str, Any], output_prefix: Path) -> tuple[Path, Path]:
    output_prefix = output_prefix.expanduser()
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_prefix.with_suffix(".json")
    md_path = output_prefix.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gates = report["gates"]
    lines = [
        "# A2+Piper v18 M39 combined zero-shot probe report",
        "",
        f"Schema: `{report['schema']}`",
        "",
        f"Admission: **{report['admission']['status']}**",
        "",
        "| Gate | Evidence | Threshold |",
        "|---|---:|---|",
        f"| Goal | {gates['goal']['numerator']}/{gates['goal']['denominator']} | >=15/16 |",
        f"| Pre-crossing bilateral contact | {gates['pre_crossing_bilateral_contact']['rate']:.6f} | >=99% |",
        f"| Pre-crossing over-force | {gates['pre_crossing_over_force']['rate']:.6f} | <2% |",
        f"| Stage3/4 raw sign flips (proxy) | {gates['stage3_stage4_raw_gripper_action_sign_flip']['count']} | exactly 0 |",
        "",
        "P1 slip reduction is not an admission gate; no velocity spectrum is claimed.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the strict v18 M39 combined zero-shot probe report.")
    parser.add_argument("--eval-dir", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report(args.eval_dir)
        paths = write_outputs(report, args.output_prefix)
    except CombinedProbeReportError as exc:
        print(f"v18 M39 combined probe FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"v18 M39 combined JSON: {paths[0]}")
    print(f"v18 M39 combined Markdown: {paths[1]}")
    return 0 if report["admission"]["all_four_gates_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
