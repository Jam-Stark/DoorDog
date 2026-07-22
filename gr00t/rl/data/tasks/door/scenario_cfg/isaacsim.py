# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import logging
import math
from collections.abc import Sequence
from numbers import Real

logging.getLogger("asyncio").setLevel(logging.WARNING)

import isaaclab.sim as sim_utils
import numpy as np
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg

from gr00t.rl.isaac_utils.playground.env_rand.door import DoorSpawnerCfg, spawn_door


def _build_eval_door_handle_height_grid(
    bounds: Sequence[Real], num_envs: int, door_handle_tblr: Sequence[Real]
) -> tuple[float, ...]:
    """Validate eval handle-height bounds and return an inclusive env-ordered grid."""
    if isinstance(bounds, (str, bytes)) or not isinstance(bounds, Sequence):
        raise TypeError(
            "a2_eval_door_handle_height_linspace must be a two-bound numeric sequence"
        )
    if len(bounds) != 2:
        raise ValueError(
            "a2_eval_door_handle_height_linspace must contain exactly two bounds"
        )
    if isinstance(num_envs, bool) or not isinstance(num_envs, int):
        raise TypeError(f"num_envs must be an integer, got {num_envs!r}")
    if num_envs < 2:
        raise ValueError(f"num_envs must be >= 2 for an endpoint grid, got {num_envs}")
    if any(isinstance(bound, bool) or not isinstance(bound, Real) for bound in bounds):
        raise TypeError(
            "a2_eval_door_handle_height_linspace bounds must be real numbers"
        )

    low, high = (float(bound) for bound in bounds)
    if not math.isfinite(low) or not math.isfinite(high):
        raise ValueError(
            "a2_eval_door_handle_height_linspace bounds must be finite"
        )
    if low >= high:
        raise ValueError(
            "a2_eval_door_handle_height_linspace requires low < high"
        )

    if (
        isinstance(door_handle_tblr, (str, bytes))
        or not isinstance(door_handle_tblr, Sequence)
        or len(door_handle_tblr) != 4
    ):
        raise ValueError(
            "door_handle_tblr must contain four values, "
            f"got {door_handle_tblr!r}"
        )
    if any(
        isinstance(bound, bool) or not isinstance(bound, Real)
        for bound in door_handle_tblr[:2]
    ):
        raise TypeError("door_handle_tblr height bounds must be real numbers")
    upper, lower = (float(bound) for bound in door_handle_tblr[:2])
    if not math.isfinite(upper) or not math.isfinite(lower) or lower >= upper:
        raise ValueError(
            "door_handle_tblr height bounds are invalid: "
            f"{door_handle_tblr!r}"
        )
    if low < lower or high > upper:
        raise ValueError(
            "a2_eval_door_handle_height_linspace must stay within "
            f"door_handle_tblr height bounds [{lower}, {upper}], got [{low}, {high}]"
        )

    grid = tuple(float(value) for value in np.linspace(low, high, num_envs))
    if (
        len(grid) != num_envs
        or grid[0] != low
        or grid[-1] != high
        or any(grid[index] >= grid[index + 1] for index in range(len(grid) - 1))
    ):
        raise ValueError(
            "a2_eval_door_handle_height_linspace produced an invalid count/order grid"
        )
    return grid


def _validate_door_weight_range(value: Sequence[Real]) -> tuple[float, float]:
    """Validate an explicit per-version door-weight range before spawning."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(
            "a2_door_weight_range must be a two-bound numeric sequence"
        )
    if len(value) != 2:
        raise ValueError("a2_door_weight_range must contain exactly two bounds")
    if any(isinstance(bound, bool) or not isinstance(bound, Real) for bound in value):
        raise TypeError("a2_door_weight_range bounds must be real numbers")
    low, high = (float(bound) for bound in value)
    if not math.isfinite(low) or not math.isfinite(high):
        raise ValueError("a2_door_weight_range bounds must be finite")
    if low <= 0.0 or high <= 0.0 or low >= high:
        raise ValueError(
            "a2_door_weight_range requires positive bounds with low < high"
        )
    return low, high


def _validate_eval_door_handle_height_weight_pairs(
    pairs: Sequence[Sequence[Real]],
    num_envs: int,
    door_handle_tblr: Sequence[Real],
    door_weight_range: Sequence[Real],
) -> tuple[tuple[float, float], ...]:
    """Validate one explicit handle-height and door-weight pair per eval env."""
    if isinstance(num_envs, bool) or not isinstance(num_envs, int):
        raise TypeError(f"num_envs must be an integer, got {num_envs!r}")
    if num_envs < 1:
        raise ValueError(f"num_envs must be positive, got {num_envs}")
    if isinstance(pairs, (str, bytes)) or not isinstance(pairs, Sequence):
        raise TypeError(
            "a2_eval_door_handle_height_weight_pairs must be a sequence of pairs"
        )
    if len(pairs) != num_envs:
        raise ValueError(
            "a2_eval_door_handle_height_weight_pairs must contain exactly one "
            f"pair per environment: expected {num_envs}, got {len(pairs)}"
        )

    if (
        isinstance(door_handle_tblr, (str, bytes))
        or not isinstance(door_handle_tblr, Sequence)
        or len(door_handle_tblr) != 4
    ):
        raise ValueError(
            "door_handle_tblr must contain four values, "
            f"got {door_handle_tblr!r}"
        )
    if any(
        isinstance(bound, bool) or not isinstance(bound, Real)
        for bound in door_handle_tblr[:2]
    ):
        raise TypeError("door_handle_tblr height bounds must be real numbers")
    height_upper, height_lower = (
        float(bound) for bound in door_handle_tblr[:2]
    )
    if (
        not math.isfinite(height_upper)
        or not math.isfinite(height_lower)
        or height_lower >= height_upper
    ):
        raise ValueError(
            "door_handle_tblr height bounds are invalid: "
            f"{door_handle_tblr!r}"
        )
    weight_lower, weight_upper = _validate_door_weight_range(door_weight_range)

    validated = []
    for index, pair in enumerate(pairs):
        if isinstance(pair, (str, bytes)) or not isinstance(pair, Sequence):
            raise TypeError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] must be a two-value sequence"
            )
        if len(pair) != 2:
            raise ValueError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] must contain exactly two values"
            )
        if any(
            isinstance(value, bool) or not isinstance(value, Real) for value in pair
        ):
            raise TypeError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] values must be real numbers"
            )
        height, weight = (float(value) for value in pair)
        if not math.isfinite(height) or not math.isfinite(weight):
            raise ValueError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] values must be finite"
            )
        if not height_lower <= height <= height_upper:
            raise ValueError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] height must stay within [{height_lower}, {height_upper}], "
                f"got {height}"
            )
        if not weight_lower <= weight <= weight_upper:
            raise ValueError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] weight must stay within [{weight_lower}, {weight_upper}], "
                f"got {weight}"
            )
        validated.append((height, weight))
    return tuple(validated)


def _apply_door_weight_range(
    task_obj_cfg_dict: dict, door_weight_range: Sequence[Real]
) -> dict:
    """Apply a validated mass range through high-level immutable config replacement."""
    weight_range = _validate_door_weight_range(door_weight_range)
    if not isinstance(task_obj_cfg_dict, dict) or "door" not in task_obj_cfg_dict:
        raise ValueError("task-object configuration must contain the 'door' object")
    door_cfg = task_obj_cfg_dict["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("door spawn configuration must be MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("door MultiAssetSpawnerCfg.assets_cfg must be non-empty")
    variants = []
    for index, asset_cfg in enumerate(spawn_cfg.assets_cfg):
        if not isinstance(asset_cfg, DoorSpawnerCfg):
            raise TypeError(
                f"door assets_cfg[{index}] must be DoorSpawnerCfg, "
                f"got {type(asset_cfg).__name__}"
            )
        variants.append(asset_cfg.replace(door_weight=weight_range))
    ordered_spawn_cfg = spawn_cfg.replace(assets_cfg=variants)
    result = dict(task_obj_cfg_dict)
    result["door"] = door_cfg.replace(spawn=ordered_spawn_cfg)
    return result


def _validate_eval_door_handle_height_task_obj_cfg(
    task_obj_cfg_dict: dict, expected_heights: Sequence[Real]
) -> dict:
    """Validate the ordered multi-asset task config produced for deterministic eval."""
    if not isinstance(task_obj_cfg_dict, dict):
        raise TypeError(
            f"eval task-object configuration must be a dict, got {type(task_obj_cfg_dict).__name__}"
        )
    if "door" not in task_obj_cfg_dict:
        raise ValueError("eval task-object configuration must contain the 'door' object")

    door_cfg = task_obj_cfg_dict["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("eval door spawn configuration must be MultiAssetSpawnerCfg")
    if spawn_cfg.random_choice is not False:
        raise ValueError("eval door MultiAssetSpawnerCfg.random_choice must be False")
    if not isinstance(spawn_cfg.assets_cfg, list):
        raise TypeError("eval door assets_cfg must be a list")
    if len(spawn_cfg.assets_cfg) != len(expected_heights):
        raise ValueError(
            "eval door grid count mismatch: "
            f"expected {len(expected_heights)}, got {len(spawn_cfg.assets_cfg)}"
        )

    actual_heights = []
    for index, asset_cfg in enumerate(spawn_cfg.assets_cfg):
        if not isinstance(asset_cfg, DoorSpawnerCfg):
            raise TypeError(
                f"eval door assets_cfg[{index}] must be DoorSpawnerCfg, "
                f"got {type(asset_cfg).__name__}"
            )
        height = asset_cfg.rand_door_handle_height
        if isinstance(height, bool) or not isinstance(height, Real):
            raise TypeError(
                f"eval door assets_cfg[{index}].rand_door_handle_height must be real"
            )
        height = float(height)
        if not math.isfinite(height):
            raise ValueError(
                f"eval door assets_cfg[{index}].rand_door_handle_height must be finite"
            )
        actual_heights.append(height)

    expected = tuple(float(height) for height in expected_heights)
    if tuple(actual_heights) != expected:
        raise ValueError(
            "eval door grid order/value mismatch: "
            f"expected {expected!r}, got {tuple(actual_heights)!r}"
        )
    return task_obj_cfg_dict


def get_TaskObjCfgDict_for_eval_door_handle_height_linspace(
    num_envs: int,
    bounds: Sequence[Real],
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Return an ordered per-environment door config for an explicit eval height grid."""
    base_task_obj_cfg_dict = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    if not isinstance(base_task_obj_cfg_dict, dict):
        raise TypeError(
            "TaskObjCfgDict must be a dict, "
            f"got {type(base_task_obj_cfg_dict).__name__}"
        )
    if "door" not in base_task_obj_cfg_dict:
        raise ValueError("TaskObjCfgDict must contain the 'door' object")

    door_cfg = base_task_obj_cfg_dict["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("base door spawn configuration must be MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("base door MultiAssetSpawnerCfg.assets_cfg must be non-empty")

    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("base door assets_cfg[0] must be DoorSpawnerCfg")
    heights = _build_eval_door_handle_height_grid(
        bounds, num_envs, base_door_cfg.door_handle_tblr
    )
    variants = [
        base_door_cfg.replace(rand_door_handle_height=height) for height in heights
    ]
    if len(variants) != num_envs:
        raise ValueError(
            f"eval door variant count mismatch: expected {num_envs}, got {len(variants)}"
        )

    ordered_spawn_cfg = spawn_cfg.replace(assets_cfg=variants, random_choice=False)
    result = dict(base_task_obj_cfg_dict)
    result["door"] = door_cfg.replace(spawn=ordered_spawn_cfg)
    return _validate_eval_door_handle_height_task_obj_cfg(result, heights)


def get_TaskObjCfgDict_for_eval_door_handle_height_weight_pairs(
    num_envs: int,
    pairs: Sequence[Sequence[Real]],
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Return ordered deterministic door configs for explicit eval extrema pairs."""
    base_task_obj_cfg_dict = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    if not isinstance(base_task_obj_cfg_dict, dict):
        raise TypeError(
            "TaskObjCfgDict must be a dict, "
            f"got {type(base_task_obj_cfg_dict).__name__}"
        )
    if "door" not in base_task_obj_cfg_dict:
        raise ValueError("TaskObjCfgDict must contain the 'door' object")

    door_cfg = base_task_obj_cfg_dict["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("base door spawn configuration must be MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("base door MultiAssetSpawnerCfg.assets_cfg must be non-empty")
    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("base door assets_cfg[0] must be DoorSpawnerCfg")

    validated_pairs = _validate_eval_door_handle_height_weight_pairs(
        pairs,
        num_envs,
        base_door_cfg.door_handle_tblr,
        base_door_cfg.door_weight,
    )
    variants = [
        base_door_cfg.replace(
            rand_door_handle_height=height,
            rand_door_weight=weight,
        )
        for height, weight in validated_pairs
    ]
    ordered_spawn_cfg = spawn_cfg.replace(
        assets_cfg=variants,
        random_choice=False,
    )
    result = dict(base_task_obj_cfg_dict)
    result["door"] = door_cfg.replace(spawn=ordered_spawn_cfg)
    return result


def get_TaskObjCfgDict_for_door_config(num_envs: int, env_config) -> dict:
    """Compose explicit version selectors with the deterministic eval height hook."""
    if isinstance(env_config, (str, bytes)) or not hasattr(env_config, "__contains__"):
        raise TypeError("env_config must be a mapping-like configuration")
    height_grid_key = "a2_eval_door_handle_height_linspace"
    height_weight_pairs_key = "a2_eval_door_handle_height_weight_pairs"
    if height_grid_key in env_config and height_weight_pairs_key in env_config:
        raise ValueError(
            f"{height_grid_key} and {height_weight_pairs_key} are mutually exclusive"
        )
    result = TaskObjCfgDict
    if "a2_door_weight_range" in env_config:
        result = _apply_door_weight_range(result, env_config["a2_door_weight_range"])
    if height_weight_pairs_key in env_config:
        result = get_TaskObjCfgDict_for_eval_door_handle_height_weight_pairs(
            num_envs,
            env_config[height_weight_pairs_key],
            task_obj_cfg_dict=result,
        )
    elif height_grid_key in env_config:
        result = get_TaskObjCfgDict_for_eval_door_handle_height_linspace(
            num_envs,
            env_config[height_grid_key],
            task_obj_cfg_dict=result,
        )
    return result
door_spawner_cfg = DoorSpawnerCfg(
    func=spawn_door,
    articulation_props=sim_utils.ArticulationRootPropertiesCfg(
        enabled_self_collisions=True,
        solver_position_iteration_count=4,
        solver_velocity_iteration_count=4,
        fix_root_link=True,
    ),
    activate_contact_sensors=True,
    build_latch=True,
    add_floors=True,
    door_open_lr=["right"],
    door_open_io=["out"],
    door_handle_tblr=(1.10, 0.80, 0.08, 0.15),
    door_weight=(80.0, 120.0),
    hinge_drive_max_force_range=(2.5, 12.0),
    handle_drive_max_force_range=(1.0, 3.0),
    randomize_material=True,
    use_preloaded_materials=True,
    preloaded_materials_num_transform=20,
    preloaded_materials_num_color=100,
    dynamic_material_randomization=False,
    dynamic_material_randomization_interval=1.0,
)

multi_spawner_cfg = sim_utils.MultiAssetSpawnerCfg(
    assets_cfg=[door_spawner_cfg] * 4096,
    random_choice=False,
    activate_contact_sensors=True,
    rigid_props=sim_utils.RigidBodyPropertiesCfg(
        disable_gravity=False,
        retain_accelerations=False,
        linear_damping=0.0,
        angular_damping=0.0,
        max_linear_velocity=1000.0,
        max_angular_velocity=1000.0,
        max_depenetration_velocity=1.0,
    ),
)

TaskObjCfgDict = {
    "door": ArticulationCfg(
        spawn=multi_spawner_cfg,
        init_state=ArticulationCfg.InitialStateCfg(
            pos=(0.0, 0.0, 0.0),
            rot=(1.0, 0.0, 0.0, 0.0),
            joint_pos={
                ".*hinge.*": 0.0,
                ".*handle.*": 0.0,
                ".*latch.*": 0.0,
            },
            joint_vel={".*": 0.0},
        ),
        soft_joint_pos_limit_factor=0.9,
        actuators={
            "hinge": ImplicitActuatorCfg(
                joint_names_expr=[".*hinge.*"],
                velocity_limit_sim=100.0,
                stiffness=None,
                damping=None,
            ),
            "handle": ImplicitActuatorCfg(
                joint_names_expr=[".*handle.*"],
                velocity_limit_sim=100.0,
                stiffness=None,
                damping=None,
            ),
        },
    )
}
