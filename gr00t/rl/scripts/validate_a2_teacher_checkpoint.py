#!/usr/bin/env python3
"""Validate or explicitly generate an immutable A2 Teacher artifact manifest.

This module intentionally has no IsaacSim imports.  A production A2 Student
trainer must provide all three paths and call :func:`validate_teacher_artifact`;
there is no automatic checkpoint discovery or mutable ``last.pt`` fallback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import torch
import yaml


SCHEMA_VERSION = "a2_teacher_manifest.v1"
TEACHER_OBS_TERMS = (
    "dof_pos",
    "relative_to_door",
    "dof_vel",
    "actions",
    "projected_gravity",
    "door_dof_pos",
    "base_lin_vel",
    "base_ang_vel",
    "hand_force",
    "stage",
    "privileged_door_info",
    "delta_actions",
    "gripper_handle_transform",
    "a2_base_command_raw",
    "a2_base_command",
)
TEACHER_OBS_DIMS = (20, 9, 20, 19, 3, 2, 3, 3, 6, 6, 8, 6, 18, 5, 5)
TEACHER_OBS_SCALES = {
    "dof_pos": 1.0,
    "relative_to_door": 1.0,
    "dof_vel": 0.05,
    "actions": 1.0,
    "projected_gravity": 1.0,
    "door_dof_pos": 1.0,
    "base_lin_vel": 1.0,
    "base_ang_vel": 0.5,
    "hand_force": 0.01,
    "stage": 1.0,
    "privileged_door_info": 1.0,
    "delta_actions": 1.0,
    "gripper_handle_transform": 1.0,
    "a2_base_command_raw": 1.0,
    "a2_base_command": 1.0,
}
A2_ROBOT_DOF_NAMES = (
    "FL_hip_joint",
    "FL_thigh_joint",
    "FL_calf_joint",
    "RL_hip_joint",
    "RL_thigh_joint",
    "RL_calf_joint",
    "FR_hip_joint",
    "FR_thigh_joint",
    "FR_calf_joint",
    "RR_hip_joint",
    "RR_thigh_joint",
    "RR_calf_joint",
    "arm_j1",
    "arm_j2",
    "arm_j3",
    "arm_j4",
    "arm_j5",
    "arm_j6",
    "arm_j7",
    "arm_j8",
)
A2_STAGE_COUNT = 6
A2_BASE_COMMAND_DIM = 5
A2_MANIPULATION_ACTION_DIM = 7

_TEACHER_OBS_DIM_EXPRESSIONS = {
    "dof_pos": "${robot.dof_obs_size}",
    "dof_vel": "${robot.dof_obs_size}",
    "actions": "${eval:'${env.config.a2_base.leg_action_dim} + ${algo.config.manipulation_action_dim}'}",
    "stage": "${eval:'len(${env.config.max_stage_time})'}",
    "delta_actions": "${eval:'len(${env.config.delta_action_indices})'}",
    "a2_base_command_raw": "${eval:'len(${env.config.warped_action.indices})'}",
}
_TEACHER_ACTION_DIM_EXPRESSION = (
    "${eval:'${algo.config.base_command_dim} + ${algo.config.manipulation_action_dim}'}"
)
_TEACHER_ACTOR_HIDDEN_DIMS = (512, 256, 128)
_TEACHER_ACTOR_ACTIVATION = "silu"

_TEACHER_STATE_SHAPES = {
    "std": (12,),
    "actor_module.module.0.weight": (512, 256),
    "actor_module.module.0.bias": (512,),
    "actor_module.module.2.weight": (256, 512),
    "actor_module.module.2.bias": (256,),
    "actor_module.module.4.weight": (128, 256),
    "actor_module.module.4.bias": (128,),
    "actor_module.module.6.weight": (12, 128),
    "actor_module.module.6.bias": (12,),
    "running_mean_std.running_mean": (133,),
    "running_mean_std.running_var": (133,),
    "running_mean_std.count": (),
    "memory.rnn.weight_ih_l0": (1024, 133),
    "memory.rnn.weight_hh_l0": (1024, 256),
    "memory.rnn.bias_ih_l0": (1024,),
    "memory.rnn.bias_hh_l0": (1024,),
    "memory.rnn.weight_ih_l1": (1024, 256),
    "memory.rnn.weight_hh_l1": (1024, 256),
    "memory.rnn.bias_ih_l1": (1024,),
    "memory.rnn.bias_hh_l1": (1024,),
}


def _require_mapping(value, path):
    if not isinstance(value, Mapping):
        raise ValueError(f"A2 Teacher config {path} must be a mapping; got {type(value).__name__}")
    return value


def _require_sequence(value, path):
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"A2 Teacher config {path} must be an explicit sequence")
    return list(value)


def _require_int(value, path, expected=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"A2 Teacher config {path} must be an integer; got {value!r}")
    if expected is not None and value != expected:
        raise ValueError(f"A2 Teacher config {path} must be {expected}; got {value!r}")
    return value


def _require_float(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"A2 Teacher config {path} must be numeric; got {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"A2 Teacher config {path} must be finite; got {value!r}")
    return value


def _obs_dims_mapping(obs_dims):
    if isinstance(obs_dims, Mapping):
        entries = list(obs_dims.items())
    else:
        entries = []
        for index, item in enumerate(_require_sequence(obs_dims, "obs.obs_dims")):
            item = _require_mapping(item, f"obs.obs_dims[{index}]")
            if len(item) != 1:
                raise ValueError(f"A2 Teacher config obs.obs_dims[{index}] must contain one term")
            entries.extend(item.items())
    result = {}
    for term, dim in entries:
        term = str(term)
        if term in result:
            raise ValueError(f"A2 Teacher config obs.obs_dims repeats {term!r}")
        result[term] = dim
    return result


def _mapping_path(config, path, label):
    value = config
    for component in path.split("."):
        value = _require_mapping(value, label)
        if component not in value:
            raise ValueError(f"A2 Teacher config {label} references missing {component!r}")
        value = value[component]
    return value


def _resolve_teacher_obs_dim(term, raw_dim, config):
    if isinstance(raw_dim, bool):
        raise ValueError(f"A2 Teacher config obs.obs_dims[{term!r}] must be an integer")
    if isinstance(raw_dim, int):
        return raw_dim
    if not isinstance(raw_dim, str):
        raise ValueError(
            f"A2 Teacher config obs.obs_dims[{term!r}] must be an integer or approved expression"
        )
    expected_expression = _TEACHER_OBS_DIM_EXPRESSIONS.get(term)
    if raw_dim != expected_expression:
        raise ValueError(
            f"A2 Teacher config obs.obs_dims[{term!r}] uses an unsupported expression: {raw_dim!r}"
        )
    if term in ("dof_pos", "dof_vel"):
        return _require_int(_mapping_path(config, "robot.dof_obs_size", "robot.dof_obs_size"), "robot.dof_obs_size")
    if term == "actions":
        leg_dim = _require_int(
            _mapping_path(config, "env.config.a2_base.leg_action_dim", "env.config.a2_base.leg_action_dim"),
            "env.config.a2_base.leg_action_dim",
        )
        manipulation_dim = _require_int(
            _mapping_path(
                config,
                "algo.config.manipulation_action_dim",
                "algo.config.manipulation_action_dim",
            ),
            "algo.config.manipulation_action_dim",
        )
        return leg_dim + manipulation_dim
    if term == "stage":
        stage_times = _require_sequence(
            _mapping_path(config, "env.config.max_stage_time", "env.config.max_stage_time"),
            "env.config.max_stage_time",
        )
        return len(stage_times)
    if term == "delta_actions":
        delta_indices = _require_sequence(
            _mapping_path(config, "env.config.delta_action_indices", "env.config.delta_action_indices"),
            "env.config.delta_action_indices",
        )
        return len(delta_indices)
    if term == "a2_base_command_raw":
        warped_indices = _require_sequence(
            _mapping_path(config, "env.config.warped_action.indices", "env.config.warped_action.indices"),
            "env.config.warped_action.indices",
        )
        return len(warped_indices)
    raise RuntimeError(f"No approved A2 Teacher expression resolver exists for {term!r}")


def _resolve_teacher_action_output_dim(raw_dim, config):
    if isinstance(raw_dim, int) and not isinstance(raw_dim, bool):
        return raw_dim
    if raw_dim != _TEACHER_ACTION_DIM_EXPRESSION:
        raise ValueError(
            "A2 Teacher actor output_dim must be 12 or the exact approved base+manipulation expression"
        )
    base_dim = _require_int(
        _mapping_path(config, "algo.config.base_command_dim", "algo.config.base_command_dim"),
        "algo.config.base_command_dim",
    )
    manipulation_dim = _require_int(
        _mapping_path(
            config,
            "algo.config.manipulation_action_dim",
            "algo.config.manipulation_action_dim",
        ),
        "algo.config.manipulation_action_dim",
    )
    return base_dim + manipulation_dim


def validate_teacher_config(config_path: str | Path) -> dict[str, Any]:
    """Validate the supplied resolved A2 Teacher config semantic contract."""
    config_file = Path(config_path).expanduser()
    if not config_file.is_file():
        raise FileNotFoundError(f"A2 Teacher config does not exist: {config_file}")
    with config_file.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    config = _require_mapping(config, "root")

    robot = _require_mapping(config.get("robot"), "robot")
    dof_names = tuple(_require_sequence(robot.get("dof_names"), "robot.dof_names"))
    if dof_names != A2_ROBOT_DOF_NAMES:
        raise ValueError(
            "A2 Teacher config robot.dof_names must be the exact A2_Piper 20-DOF order; "
            f"got {dof_names!r}"
        )

    env = _require_mapping(config.get("env"), "env")
    env_config = _require_mapping(env.get("config"), "env.config")
    stage_times = _require_sequence(env_config.get("max_stage_time"), "env.config.max_stage_time")
    if len(stage_times) != A2_STAGE_COUNT:
        raise ValueError(
            f"A2 Teacher config requires a six-stage max_stage_time contract; got {len(stage_times)}"
        )
    for index, value in enumerate(stage_times):
        _require_float(value, f"env.config.max_stage_time[{index}]")

    algo = _require_mapping(config.get("algo"), "algo")
    algo_config = _require_mapping(algo.get("config"), "algo.config")
    if algo_config.get("use_a2_base") is not True:
        raise ValueError("A2 Teacher config requires algo.config.use_a2_base=true")
    a2_base = _require_mapping(algo_config.get("a2_base"), "algo.config.a2_base")
    if a2_base.get("enabled") is not True:
        raise ValueError("A2 Teacher config requires algo.config.a2_base.enabled=true")
    _require_int(a2_base.get("obs_dim"), "algo.config.a2_base.obs_dim", 1620)
    _require_int(a2_base.get("action_dim"), "algo.config.a2_base.action_dim", 12)
    _require_int(algo_config.get("base_command_dim"), "algo.config.base_command_dim", A2_BASE_COMMAND_DIM)
    _require_int(
        algo_config.get("manipulation_action_dim"),
        "algo.config.manipulation_action_dim",
        A2_MANIPULATION_ACTION_DIM,
    )
    if A2_BASE_COMMAND_DIM + A2_MANIPULATION_ACTION_DIM != 12:
        raise RuntimeError("A2 Teacher action driver constants drifted from the 12D contract")

    obs = _require_mapping(config.get("obs"), "obs")
    obs_dict = _require_mapping(obs.get("obs_dict"), "obs.obs_dict")
    obs_keys = [key for key in ("actor_obs", "teacher_obs") if key in obs_dict]
    if not obs_keys:
        raise ValueError("A2 Teacher config requires obs.obs_dict.actor_obs or teacher_obs")
    for obs_key in obs_keys:
        terms = tuple(_require_sequence(obs_dict[obs_key], f"obs.obs_dict.{obs_key}"))
        if terms != TEACHER_OBS_TERMS:
            raise ValueError(
                f"A2 Teacher config obs.obs_dict.{obs_key} does not match the exact 133D A2 order"
            )
    selected_obs_key = "teacher_obs" if "teacher_obs" in obs_dict else "actor_obs"

    scales = _require_mapping(obs.get("obs_scales"), "obs.obs_scales")
    for term, expected_scale in TEACHER_OBS_SCALES.items():
        if term not in scales or not math.isclose(
            _require_float(scales[term], f"obs.obs_scales.{term}"), expected_scale, rel_tol=0.0, abs_tol=1.0e-12
        ):
            raise ValueError(f"A2 Teacher config obs.obs_scales.{term} drifted from the A2 contract")
    dims = _obs_dims_mapping(obs.get("obs_dims"))
    observed_dims = tuple(
        _resolve_teacher_obs_dim(term, dims[term], config) if term in dims else -1
        for term in TEACHER_OBS_TERMS
    )
    if observed_dims != TEACHER_OBS_DIMS or sum(observed_dims) != 133:
        raise ValueError(
            "A2 Teacher config obs dimensions must match the exact 133D A2 drivers; "
            f"got {observed_dims!r}"
        )

    actor = _require_mapping(algo_config.get("actor"), "algo.config.actor")
    actor_target = actor.get("_target_")
    if not isinstance(actor_target, str) or actor_target.rsplit(".", 1)[-1] != "RecurrentActor":
        raise ValueError("A2 Teacher actor must be the non-vision RecurrentActor")
    actor_input_key = actor.get("input_key", "actor_obs")
    if actor_input_key != selected_obs_key:
        raise ValueError(
            f"A2 Teacher actor input_key must be {selected_obs_key!r}; got {actor_input_key!r}"
        )
    if actor.get("running_mean_std") is not True:
        raise ValueError("A2 Teacher actor requires running_mean_std=true")
    if str(actor.get("rnn_type", "")).lower() != "lstm":
        raise ValueError("A2 Teacher actor requires rnn_type=lstm")
    _require_int(actor.get("rnn_hidden_dim"), "algo.config.actor.rnn_hidden_dim", 256)
    _require_int(actor.get("rnn_num_layers"), "algo.config.actor.rnn_num_layers", 2)
    backbone = _require_mapping(actor.get("backbone"), "algo.config.actor.backbone")
    module_config = _require_mapping(
        backbone.get("module_config_dict"),
        "algo.config.actor.backbone.module_config_dict",
    )
    output_dims = _require_sequence(
        module_config.get("output_dim"),
        "algo.config.actor.backbone.module_config_dict.output_dim",
    )
    if len(output_dims) != 1:
        raise ValueError("A2 Teacher actor backbone output_dim must contain exactly one driver")
    if _resolve_teacher_action_output_dim(output_dims[0], config) != 12:
        raise ValueError("A2 Teacher actor backbone output_dim must resolve to 12")
    layer_config = _require_mapping(
        module_config.get("layer_config"),
        "algo.config.actor.backbone.module_config_dict.layer_config",
    )
    hidden_dims = tuple(
        _require_int(value, "algo.config.actor.backbone.module_config_dict.layer_config.hidden_dims")
        for value in _require_sequence(
            layer_config.get("hidden_dims"),
            "algo.config.actor.backbone.module_config_dict.layer_config.hidden_dims",
        )
    )
    if hidden_dims != _TEACHER_ACTOR_HIDDEN_DIMS:
        raise ValueError(
            "A2 Teacher actor backbone hidden_dims must be [512, 256, 128]; "
            f"got {hidden_dims!r}"
        )
    activation = layer_config.get("activation")
    if activation is not None and str(activation).lower() != _TEACHER_ACTOR_ACTIVATION:
        raise ValueError(
            "A2 Teacher actor backbone activation must be SiLU when specified; "
            f"got {activation!r}"
        )

    return {
        "obs_key": selected_obs_key,
        "obs_terms": list(TEACHER_OBS_TERMS),
        "obs_dims": list(TEACHER_OBS_DIMS),
        "obs_scales": dict(TEACHER_OBS_SCALES),
        "robot_dof_names": list(A2_ROBOT_DOF_NAMES),
        "stage_count": A2_STAGE_COUNT,
        "action_drivers": {
            "base_command_dim": A2_BASE_COMMAND_DIM,
            "manipulation_action_dim": A2_MANIPULATION_ACTION_DIM,
            "total_dim": 12,
        },
    }


def sha256_file(path: str | Path) -> str:
    file_path = Path(path).expanduser()
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_mutable_checkpoint(path: Path) -> None:
    if path.name == "last.pt" or path.name.endswith("_last.pt"):
        raise ValueError(f"Mutable checkpoint filename is forbidden for A2 Teacher: {path}")


def _load_checkpoint(path: Path) -> dict[str, Any]:
    _reject_mutable_checkpoint(path)
    if not path.is_file():
        raise FileNotFoundError(f"A2 Teacher checkpoint does not exist: {path}")
    loaded = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(loaded, dict):
        raise ValueError(f"A2 Teacher checkpoint must be a mapping, got {type(loaded).__name__}")
    return loaded


def _find_state_dict_key(checkpoint: dict[str, Any], preferred: str | None = None) -> str:
    candidates = [preferred] if preferred else []
    candidates.extend(("actor_model_state_dict", "policy_state_dict"))
    for key in candidates:
        if key and key in checkpoint and isinstance(checkpoint[key], dict):
            return key
    raise ValueError(
        "A2 Teacher checkpoint has no supported actor state dict key; "
        f"available keys={sorted(checkpoint.keys())}"
    )


def _rms_shapes(state_dict: dict[str, Any]) -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for key, value in state_dict.items():
        if "running_mean_std" not in key or not torch.is_tensor(value):
            continue
        if key.endswith("running_mean"):
            found["running_mean"] = list(value.shape)
        elif key.endswith("running_var"):
            found["running_var"] = list(value.shape)
    return found


def _validate_teacher_state_dict(state_dict: dict[str, Any]) -> dict[str, Any]:
    """Validate the exact recurrent A2 Teacher policy state contract."""
    if not isinstance(state_dict, Mapping):
        raise ValueError(
            "A2 Teacher actor state_dict must be a mapping; "
            f"got {type(state_dict).__name__}"
        )
    expected_keys = set(_TEACHER_STATE_SHAPES)
    actual_keys = set(state_dict)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ValueError(
            "A2 Teacher policy state_dict keys do not match the exact 20-key contract; "
            f"missing={missing}, extra={extra}"
        )
    for key, expected_shape in _TEACHER_STATE_SHAPES.items():
        value = state_dict[key]
        if not torch.is_tensor(value):
            raise ValueError(f"A2 Teacher policy state_dict[{key!r}] must be a tensor")
        if tuple(value.shape) != expected_shape:
            raise ValueError(
                f"A2 Teacher policy state_dict[{key!r}] shape must be {expected_shape}; "
                f"got {tuple(value.shape)}"
            )
        if not torch.is_floating_point(value):
            raise ValueError(f"A2 Teacher policy state_dict[{key!r}] must use a floating dtype")
        if not bool(torch.all(torch.isfinite(value)).item()):
            raise ValueError(f"A2 Teacher policy state_dict[{key!r}] contains non-finite values")
    count = state_dict["running_mean_std.count"]
    count_value = float(count.item())
    if not math.isfinite(count_value) or count_value <= 0.0:
        raise ValueError(
            "A2 Teacher running_mean_std.count must be a finite positive scalar; "
            f"got {count_value!r}"
        )
    return dict(state_dict)


def _required_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"A2 Teacher manifest schema mismatch: expected {SCHEMA_VERSION!r}, "
            f"got {manifest.get('schema_version')!r}"
        )
    checkpoint = manifest.get("checkpoint")
    source = manifest.get("source")
    teacher = manifest.get("teacher")
    if not isinstance(checkpoint, dict) or not isinstance(source, dict) or not isinstance(teacher, dict):
        raise ValueError("A2 Teacher manifest requires checkpoint, source, and teacher mappings")
    for key in ("filename", "sha256", "state_dict_key"):
        if not isinstance(checkpoint.get(key), str) or not checkpoint[key]:
            raise ValueError(f"A2 Teacher manifest checkpoint.{key} is required")
    if not isinstance(source.get("commit"), str) or not source["commit"]:
        raise ValueError("A2 Teacher manifest source.commit is required")
    if not isinstance(source.get("config_sha256"), str) or len(source["config_sha256"]) != 64:
        raise ValueError("A2 Teacher manifest source.config_sha256 must be a SHA256 hex digest")

    obs = teacher.get("obs")
    if not isinstance(obs, dict):
        raise ValueError("A2 Teacher manifest teacher.obs is required")
    if tuple(obs.get("terms", ())) != TEACHER_OBS_TERMS:
        raise ValueError("A2 Teacher manifest teacher.obs.terms do not match the active A2 order")
    if tuple(obs.get("dims", ())) != TEACHER_OBS_DIMS:
        raise ValueError(
            f"A2 Teacher manifest must bind the 133D obs dims {TEACHER_OBS_DIMS}; got {obs.get('dims')!r}"
        )
    if obs.get("input_dim") != 133:
        raise ValueError(f"A2 Teacher manifest input_dim must be 133, got {obs.get('input_dim')!r}")
    if obs.get("scales") != TEACHER_OBS_SCALES:
        raise ValueError("A2 Teacher manifest teacher.obs.scales drifted from the active A2 scales")
    if teacher.get("action_dim") != 12:
        raise ValueError("A2 Teacher manifest action_dim must be 12")
    rms = teacher.get("running_mean_std")
    if not isinstance(rms, dict) or rms.get("present") is not True:
        raise ValueError("A2 Teacher manifest requires running_mean_std.present=true")
    if tuple(rms.get("running_mean_shape", ())) != (133,) or tuple(
        rms.get("running_var_shape", ())
    ) != (133,):
        raise ValueError("A2 Teacher RMS shapes must both be [133]")
    recurrent = teacher.get("recurrent")
    if recurrent != {"type": "lstm", "hidden_dim": 256, "num_layers": 2}:
        raise ValueError(
            "A2 Teacher recurrent contract must be LSTM hidden_dim=256 num_layers=2"
        )
    robot = teacher.get("robot")
    if not isinstance(robot, dict) or tuple(robot.get("dof_names", ())) != A2_ROBOT_DOF_NAMES:
        raise ValueError("A2 Teacher manifest robot.dof_names must match the exact A2_Piper order")
    action_drivers = teacher.get("action_drivers")
    if action_drivers != {
        "base_command_dim": A2_BASE_COMMAND_DIM,
        "manipulation_action_dim": A2_MANIPULATION_ACTION_DIM,
        "total_dim": 12,
    }:
        raise ValueError("A2 Teacher manifest action driver contract must be 5+7=12")
    if teacher.get("stage_count") != A2_STAGE_COUNT:
        raise ValueError("A2 Teacher manifest stage_count must be 6")


def _validate_manifest_config_identity(manifest, semantic):
    teacher = manifest["teacher"]
    if tuple(teacher["obs"]["terms"]) != tuple(semantic["obs_terms"]):
        raise ValueError("A2 Teacher manifest observation terms do not match the supplied config")
    if tuple(teacher["obs"]["dims"]) != tuple(semantic["obs_dims"]):
        raise ValueError("A2 Teacher manifest observation dims do not match the supplied config")
    if teacher["obs"]["scales"] != semantic["obs_scales"]:
        raise ValueError("A2 Teacher manifest observation scales do not match the supplied config")
    if tuple(teacher["robot"]["dof_names"]) != tuple(semantic["robot_dof_names"]):
        raise ValueError("A2 Teacher manifest robot identity does not match the supplied config")
    if teacher["action_drivers"] != semantic["action_drivers"]:
        raise ValueError("A2 Teacher manifest action drivers do not match the supplied config")
    if teacher["stage_count"] != semantic["stage_count"]:
        raise ValueError("A2 Teacher manifest stage contract does not match the supplied config")


def validate_teacher_artifact(
    checkpoint_path: str | Path,
    config_path: str | Path,
    manifest_path: str | Path,
) -> dict[str, Any]:
    """Validate checkpoint bytes, sidecar identity, and the A2 Teacher schema."""
    checkpoint_file = Path(checkpoint_path).expanduser()
    config_file = Path(config_path).expanduser()
    manifest_file = Path(manifest_path).expanduser()
    unresolved = [path for path in (checkpoint_file, config_file, manifest_file) if not path.is_file()]
    if unresolved:
        raise FileNotFoundError(
            "A2 Student requires existing Teacher checkpoint/config/manifest paths; "
            f"missing={unresolved}"
        )
    _reject_mutable_checkpoint(checkpoint_file)
    semantic = validate_teacher_config(config_file)
    with manifest_file.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    _required_manifest(manifest)
    _validate_manifest_config_identity(manifest, semantic)
    checkpoint = _load_checkpoint(checkpoint_file)
    if manifest["checkpoint"]["filename"] != checkpoint_file.name:
        raise ValueError("A2 Teacher manifest checkpoint filename does not match the selected artifact")
    if manifest["checkpoint"]["sha256"] != sha256_file(checkpoint_file):
        raise ValueError("A2 Teacher checkpoint SHA256 does not match its manifest")
    if manifest["source"]["config_sha256"] != sha256_file(config_file):
        raise ValueError("A2 Teacher config SHA256 does not match its manifest")
    state_key = _find_state_dict_key(checkpoint, manifest["checkpoint"]["state_dict_key"])
    if state_key != manifest["checkpoint"]["state_dict_key"]:
        raise ValueError("A2 Teacher state_dict key does not match its manifest")
    _validate_teacher_state_dict(checkpoint[state_key])
    return manifest


def build_teacher_manifest(
    checkpoint_path: str | Path,
    config_path: str | Path,
    source_commit: str,
    manifest_path: str | Path,
    state_dict_key: str | None = None,
) -> dict[str, Any]:
    """Generate a manifest only when explicitly requested for a completed checkpoint."""
    checkpoint_file = Path(checkpoint_path).expanduser()
    config_file = Path(config_path).expanduser()
    output_file = Path(manifest_path).expanduser()
    if output_file.exists() or output_file.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing A2 Teacher manifest: {output_file}")
    semantic = validate_teacher_config(config_file)
    checkpoint = _load_checkpoint(checkpoint_file)
    selected_key = _find_state_dict_key(checkpoint, state_dict_key)
    _validate_teacher_state_dict(checkpoint[selected_key])
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "checkpoint": {
            "filename": checkpoint_file.name,
            "sha256": sha256_file(checkpoint_file),
            "state_dict_key": selected_key,
        },
        "source": {"commit": source_commit, "config_sha256": sha256_file(config_file)},
        "teacher": {
            "obs": {
                "terms": semantic["obs_terms"],
                "dims": semantic["obs_dims"],
                "scales": semantic["obs_scales"],
                "input_dim": 133,
            },
            "action_dim": 12,
            "running_mean_std": {
                "present": True,
                "running_mean_shape": [133],
                "running_var_shape": [133],
            },
            "recurrent": {"type": "lstm", "hidden_dim": 256, "num_layers": 2},
            "robot": {"dof_names": semantic["robot_dof_names"]},
            "action_drivers": semantic["action_drivers"],
            "stage_count": semantic["stage_count"],
        },
    }
    _required_manifest(manifest)
    with output_file.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--source-commit", default=None)
    parser.add_argument("--state-dict-key", default=None)
    args = parser.parse_args()
    if args.generate:
        if not args.source_commit:
            parser.error("--generate requires --source-commit")
        result = build_teacher_manifest(
            args.checkpoint,
            args.config,
            args.source_commit,
            args.manifest,
            args.state_dict_key,
        )
    else:
        result = validate_teacher_artifact(args.checkpoint, args.config, args.manifest)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
