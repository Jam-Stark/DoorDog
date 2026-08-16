"""v24 P1a native hinge-friction probe.

The first permitted runtime mode is ``TORQUE_RAMP``.  It builds the source-
locked v23 door-only ``InteractiveScene`` and drives its door articulation
through IsaacLab's high-level API, records the requested friction profile and a
measured breakaway bracket, then clears/restores the hinge state.
``OFF_PARITY`` and ``FOOT_FORCE_DETECT`` are planning specifications for later
P1 lanes; this producer does not execute them.

``--plan`` is CPU-only and never imports or starts IsaacSim.  Runtime output
folders are deliberately supplied by the caller under the canonical
``logs_eval/base_v24/p1/friction_backend/`` root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime dependency is explicit
    raise RuntimeError("PyYAML is required for the v24 friction probe plan") from exc

try:
    from ._v24_common import (
        REPO_ROOT,
        V24_P1_FRICTION_ROOT,
        absolute,
        finite_number,
        rel_path,
        require_file,
        write_json,
    )
except ImportError:  # direct ``python scriptsFORhuman/v24/...py`` invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v24._v24_common import (
        REPO_ROOT,
        V24_P1_FRICTION_ROOT,
        absolute,
        finite_number,
        rel_path,
        require_file,
        write_json,
    )


PROBE_SCHEMA = "a2_piper_v24_p1_native_friction_probe_v1"
FRICTION_BACKEND = "native_joint_friction_v1"
MODE_ORDER = ("TORQUE_RAMP", "OFF_PARITY", "FOOT_FORCE_DETECT")
FIRST_RUNTIME_MODE = "TORQUE_RAMP"
PRODUCTION_CONFIG = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v24_p1_native_probe.yaml"
SELECTED_CHECKPOINT = REPO_ROOT / (
    "logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt"
)
ACTOR_INPUT_DIM = 133
ACTION_DIM = 12
FOOT_BODY_NAMES = ("FL_foot", "RL_foot", "FR_foot", "RR_foot")
HINGE_PATTERN = ".*hinge.*"
V23_STATIC_TRIAL_FRAMES = 100

DOOR_FIXED_CONFIG = {
    "rand_door_width": 0.95,
    "rand_door_height": 2.05,
    "rand_door_handle_height": 0.975,
    "rand_door_handle_width": 0.12,
    "rand_door_weight": 120.0,
    "rand_door_handle_type": "lever",
    "rand_door_open_lr": "right",
    "rand_door_open_io": "out",
    "rand_total_wall_height": 2.70,
    "rand_axle_length": 0.195,
    "rand_handle_length": 0.125,
    "rand_hook_length": 0.05,
    "rand_handle_radius": 0.013,
    "rand_spawn_hook": False,
    "rand_hinge_drive_max_force": 100.0,
    "rand_hinge_drive_damping": 50.0,
    "rand_hinge_drive_stiffness": 6.0,
    "rand_handle_drive_max_force": 0.0,
    "randomize_material": False,
    "use_preloaded_materials": False,
    "dynamic_material_randomization": False,
    "activate_contact_sensors": False,
    "build_latch": False,
    "add_walls": False,
    "add_floors": False,
    "add_lights": False,
    "add_ceiling": False,
}


def _door_fixture_profile(probe_seed: int) -> dict[str, Any]:
    return {
        "probe_seed": probe_seed,
        "geometry": {
            "door_width_m": DOOR_FIXED_CONFIG["rand_door_width"],
            "door_height_m": DOOR_FIXED_CONFIG["rand_door_height"],
            "handle_height_m": DOOR_FIXED_CONFIG["rand_door_handle_height"],
            "handle_width_m": DOOR_FIXED_CONFIG["rand_door_handle_width"],
            "total_wall_height_m": DOOR_FIXED_CONFIG["rand_total_wall_height"],
            "axle_length_m": DOOR_FIXED_CONFIG["rand_axle_length"],
            "handle_length_m": DOOR_FIXED_CONFIG["rand_handle_length"],
            "hook_length_m": DOOR_FIXED_CONFIG["rand_hook_length"],
            "handle_radius_m": DOOR_FIXED_CONFIG["rand_handle_radius"],
            "handle_type": DOOR_FIXED_CONFIG["rand_door_handle_type"],
            "open_lr": DOOR_FIXED_CONFIG["rand_door_open_lr"],
            "open_io": DOOR_FIXED_CONFIG["rand_door_open_io"],
            "spawn_hook": DOOR_FIXED_CONFIG["rand_spawn_hook"],
        },
        "mass_inertia_inputs": {
            "door_panel_mass_kg": DOOR_FIXED_CONFIG["rand_door_weight"],
            "top_frame_mass_kg": 100.0,
            "axle_mass_kg": 0.2,
            "handle_inside_mass_kg": 0.1,
            "handle_outside_mass_kg": 0.1,
            "hook_mass_kg": 0.0,
            "grasp_target_mass_kg": 0.001,
        },
        "dynamics": {
            "hinge_drive_max_force_nm": DOOR_FIXED_CONFIG["rand_hinge_drive_max_force"],
            "hinge_drive_damping_native": DOOR_FIXED_CONFIG["rand_hinge_drive_damping"],
            "hinge_drive_stiffness_native": DOOR_FIXED_CONFIG["rand_hinge_drive_stiffness"],
            "handle_drive_max_force_nm": DOOR_FIXED_CONFIG["rand_handle_drive_max_force"],
        },
        "isolation": {
            "build_latch": DOOR_FIXED_CONFIG["build_latch"],
            "randomize_material": DOOR_FIXED_CONFIG["randomize_material"],
            "use_preloaded_materials": DOOR_FIXED_CONFIG["use_preloaded_materials"],
            "dynamic_material_randomization": DOOR_FIXED_CONFIG["dynamic_material_randomization"],
            "activate_contact_sensors": DOOR_FIXED_CONFIG["activate_contact_sensors"],
            "add_walls": DOOR_FIXED_CONFIG["add_walls"],
            "add_floors": DOOR_FIXED_CONFIG["add_floors"],
            "add_lights": DOOR_FIXED_CONFIG["add_lights"],
            "add_ceiling": DOOR_FIXED_CONFIG["add_ceiling"],
        },
    }


def _read_yaml(path: Path) -> dict[str, Any]:
    target = require_file(path, label="v24 probe config")
    payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"v24 probe config root must be a mapping: {target}")
    return payload


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, Mapping) or key not in value:
            raise KeyError("missing config key: " + ".".join(keys))
        value = value[key]
    return value


def _probe_config_values(config_path: Path = PRODUCTION_CONFIG) -> dict[str, Any]:
    payload = _read_yaml(config_path)
    env_config = _nested(payload, "env", "config")
    if not isinstance(env_config, Mapping):
        raise TypeError("v24 probe env.config must be a mapping")
    probe_seed = payload.get("v24_probe_seed")
    if isinstance(probe_seed, bool) or not isinstance(probe_seed, int) or probe_seed < 0:
        raise ValueError("v24_probe_seed must be a non-negative integer")
    enabled = env_config.get("a2_v24_friction_enabled")
    if enabled is not True:
        raise ValueError("v24 native probe overlay must enable a2_v24_friction_enabled")
    if env_config.get("a2_v24_friction_backend") != FRICTION_BACKEND:
        raise ValueError("v24 probe overlay must select native_joint_friction_v1")
    static_effort = finite_number(
        env_config.get("a2_v24_friction_static_effort"),
        label="a2_v24_friction_static_effort",
    )
    dynamic_effort = finite_number(
        env_config.get("a2_v24_friction_dynamic_effort"),
        label="a2_v24_friction_dynamic_effort",
    )
    viscous = finite_number(
        env_config.get("a2_v24_friction_viscous_coefficient"),
        label="a2_v24_friction_viscous_coefficient",
    )
    if min(static_effort, dynamic_effort, viscous) < 0.0:
        raise ValueError("v24 native friction profile must be non-negative")
    if dynamic_effort > static_effort:
        raise ValueError("v24 probe dynamic effort must be <= static effort")

    resolution = finite_number(
        env_config.get("a2_v24_probe_resolution_effort"),
        label="a2_v24_probe_resolution_effort",
    )
    if resolution <= 0.0:
        raise ValueError("a2_v24_probe_resolution_effort must be positive")
    hold_window = env_config.get("a2_v24_probe_hold_window_steps")
    ramp_steps = env_config.get("a2_v24_probe_ramp_steps")
    settle_steps = env_config.get("a2_v24_probe_settle_steps")
    if any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in (hold_window, ramp_steps, settle_steps)):
        raise ValueError("v24 probe hold/ramp/settle steps must be positive integers")
    if hold_window != V23_STATIC_TRIAL_FRAMES:
        raise ValueError(
            "v24 probe hold window must remain exactly the v23 100-frame static-trial convention"
        )
    ramp_start = finite_number(
        env_config.get("a2_v24_probe_ramp_start_effort"),
        label="a2_v24_probe_ramp_start_effort",
    )
    ramp_end = finite_number(
        env_config.get("a2_v24_probe_ramp_end_effort"),
        label="a2_v24_probe_ramp_end_effort",
    )
    if ramp_start < 0.0 or ramp_end <= ramp_start:
        raise ValueError("v24 probe ramp must be positive and end effort must exceed start effort")
    angle_resolution = finite_number(
        env_config.get("a2_v24_probe_angle_resolution_rad", 1.0e-4),
        label="a2_v24_probe_angle_resolution_rad",
    )
    velocity_threshold = finite_number(
        env_config.get("a2_v24_probe_velocity_threshold_rad_s", 1.0e-3),
        label="a2_v24_probe_velocity_threshold_rad_s",
    )
    if angle_resolution <= 0.0 or velocity_threshold < 0.0:
        raise ValueError("v24 probe angle resolution must be positive and velocity threshold non-negative")
    interval_count = (ramp_end - ramp_start) / resolution
    if not interval_count.is_integer() or int(interval_count) != ramp_steps:
        raise ValueError(
            "v24 probe ramp range must contain exactly ramp_steps intervals at the configured resolution"
        )
    stationarity_angle_tolerance = finite_number(
        env_config.get("a2_v24_probe_stationarity_angle_tolerance_rad", angle_resolution),
        label="a2_v24_probe_stationarity_angle_tolerance_rad",
    )
    stationarity_velocity_tolerance = finite_number(
        env_config.get("a2_v24_probe_stationarity_velocity_tolerance_rad_s", velocity_threshold),
        label="a2_v24_probe_stationarity_velocity_tolerance_rad_s",
    )
    if stationarity_angle_tolerance < 0.0 or stationarity_velocity_tolerance < 0.0:
        raise ValueError("v24 stationarity tolerances must be non-negative")
    dt_s = finite_number(env_config.get("a2_v24_probe_dt_s", 0.005), label="a2_v24_probe_dt_s")
    if dt_s <= 0.0:
        raise ValueError("v24 probe dt must be positive")
    return {
        "probe_seed": probe_seed,
        "enabled": enabled,
        "backend": FRICTION_BACKEND,
        "static_effort_nm": static_effort,
        "dynamic_effort_nm": dynamic_effort,
        "viscous_coefficient_nm_s_per_rad": viscous,
        "resolution_effort_nm": resolution,
        "hold_window_steps": hold_window,
        "ramp_start_effort_nm": ramp_start,
        "ramp_end_effort_nm": ramp_end,
        "ramp_steps": ramp_steps,
        "settle_steps": settle_steps,
        "angle_resolution_rad": angle_resolution,
        "velocity_threshold_rad_s": velocity_threshold,
        "stationarity_angle_tolerance_rad": stationarity_angle_tolerance,
        "stationarity_velocity_tolerance_rad_s": stationarity_velocity_tolerance,
        "ramp_interval_count": int(interval_count),
        "dt_s": dt_s,
    }


def _assert_selected_sources(config_path: Path = PRODUCTION_CONFIG) -> None:
    config_path = absolute(config_path).resolve()
    if config_path != PRODUCTION_CONFIG.resolve():
        raise ValueError(
            "runtime v24 torque-ramp receipts require the canonical selected-probe config"
        )
    require_file(config_path, label="v24 probe config")
    require_file(SELECTED_CHECKPOINT, label="v24 selected checkpoint")
    payload = _read_yaml(config_path)
    configured_checkpoint = payload.get("checkpoint")
    provenance = payload.get("v24_checkpoint_provenance")
    if configured_checkpoint is None or provenance is None:
        raise ValueError("v24 probe config must carry selected checkpoint provenance")
    if absolute(str(configured_checkpoint)).resolve() != SELECTED_CHECKPOINT.resolve():
        raise ValueError("v24 probe config checkpoint does not match the selected freeze")
    if absolute(str(provenance)).resolve() != SELECTED_CHECKPOINT.resolve():
        raise ValueError("v24 probe checkpoint provenance does not match the selected freeze")
    if payload.get("v24_runtime_mode") != FIRST_RUNTIME_MODE:
        raise ValueError("v24 probe config runtime mode must remain TORQUE_RAMP")
    if payload.get("v24_initialization") != "warm_head_reset":
        raise ValueError("v24 probe initialization provenance must remain warm_head_reset")
    if payload.get("v24_checkpoint_load_mode") != "selected_policy_only":
        raise ValueError("v24 probe must declare v24_checkpoint_load_mode=selected_policy_only")
    env_config = _nested(payload, "env", "config")
    if env_config.get("a2_v24_gate_enabled") is not False:
        raise ValueError("v24 torque-ramp source lock requires a2_v24_gate_enabled=false")
    if env_config.get("a2_v23_warm_head_reset_enabled") is not False:
        raise ValueError("v24 probe must disable the legacy warm-head reset reapplication")
    if env_config.get("a2_v23_d1_sampler_enabled") is not False:
        raise ValueError("v24 door-only probe must disable the v23 D1 sampler")


def build_off_parity_plan(config_path: Path = PRODUCTION_CONFIG) -> dict[str, Any]:
    _assert_selected_sources(config_path)
    return {
        "status": "PLANNED_NOT_EXECUTED",
        "mode": "OFF_PARITY",
        "checkpoint": rel_path(SELECTED_CHECKPOINT),
        "checkpoint_load_mode": "policy_only",
        "v24_checkpoint_load_mode": "selected_policy_only",
        "initialization": "warm_head_reset",
        "legacy_warm_head_reset_enabled": False,
        "feature_state": {"friction": False, "gate": False},
        "comparison": {
            "legacy_feature_disabled_trace": "deterministic_obs_action_terminal_trace",
            "v24_friction_gate_off_trace": "deterministic_obs_action_terminal_trace",
            "normalization": "none_added",
            "actor_input_dim": ACTOR_INPUT_DIM,
            "action_dim": ACTION_DIM,
        },
        "runtime_artifact_folder": rel_path(V24_P1_FRICTION_ROOT / "off_parity"),
    }


def build_foot_force_detect_plan() -> dict[str, Any]:
    return {
        "status": "PLANNED_NOT_EXECUTED",
        "mode": "FOOT_FORCE_DETECT",
        "source": "existing ContactSensor scene.sensors['contact_sensor']",
        "body_names": list(FOOT_BODY_NAMES),
        "normal_force_field": "ContactSensor.data.net_forces_w[..., 2]",
        "authority_if_present": "MEASURED_CONTACT_SENSOR_NET_FORCE_WORLD_Z",
        "missing_source_status": "FOOT_FORCE_SOURCE_UNAVAILABLE",
        "missing_source_action": "raise_typed_status_without_zero_fill",
        "runtime_artifact_folder": rel_path(V24_P1_FRICTION_ROOT / "foot_force_detect"),
    }


def detect_foot_force_source(simulator: Any) -> dict[str, Any]:
    """Feature-detect the existing robot ContactSensor without zero filling."""

    import torch

    sensor = simulator.scene.sensors.get("contact_sensor")
    if sensor is None:
        return {
            "status": "FOOT_FORCE_SOURCE_UNAVAILABLE",
            "reason": "contact_sensor_missing",
            "authority": "MISSING_SOURCE_TYPED_STATUS",
        }
    sensor_body_names = tuple(str(name) for name in sensor.body_names)
    missing = [name for name in FOOT_BODY_NAMES if name not in sensor_body_names]
    if missing:
        return {
            "status": "FOOT_FORCE_SOURCE_UNAVAILABLE",
            "reason": "foot_body_missing_from_contact_sensor",
            "missing_body_names": missing,
            "authority": "MISSING_SOURCE_TYPED_STATUS",
        }
    body_ids = [sensor_body_names.index(name) for name in FOOT_BODY_NAMES]
    force = sensor.data.net_forces_w
    if not torch.is_tensor(force) or force.ndim != 3 or force.shape[1] <= max(body_ids) or force.shape[2] != 3:
        raise RuntimeError(
            "contact_sensor.data.net_forces_w must be a (num_envs, body, 3) tensor for foot detection"
        )
    return {
        "status": "FOOT_FORCE_SOURCE_AVAILABLE",
        "body_names": list(FOOT_BODY_NAMES),
        "body_ids": body_ids,
        "normal_axis": 2,
        "normal_force_tensor": force[:, body_ids, 2],
        "authority": "MEASURED_CONTACT_SENSOR_NET_FORCE_WORLD_Z",
    }


def build_plan(config_path: Path = PRODUCTION_CONFIG) -> dict[str, Any]:
    _assert_selected_sources(config_path)
    friction = _probe_config_values(config_path)
    return {
        "schema": PROBE_SCHEMA,
        "status": "PLAN_ONLY",
        "first_runtime_mode": FIRST_RUNTIME_MODE,
        "mode_order": list(MODE_ORDER),
        "runtime_artifact_root": rel_path(V24_P1_FRICTION_ROOT),
        "source_lock": {
            "production_config": rel_path(config_path),
            "selected_checkpoint": rel_path(SELECTED_CHECKPOINT),
            "probe_seed": friction["probe_seed"],
            "door_articulation": "v23 DoorSpawnerCfg + InteractiveScene.articulations['door']",
            "scene_topology": "door_only_no_robot_no_contact_sensor",
            "deterministic_geometry": "0.95m x 2.05m, lever, right/out, fixed mass and drive properties",
            "door_fixture": _door_fixture_profile(friction["probe_seed"]),
            "hinge_resolution": "Articulation.find_joints('.*hinge.*', preserve_order=True)",
        },
        "friction_profile": friction,
        "torque_ramp": {
            "door_only": True,
            "door_fixture": _door_fixture_profile(friction["probe_seed"]),
            "command_api": "Articulation.set_joint_effort_target",
            "physics_order": "scene.write_data_to_sim -> sim.step -> scene.update",
            "dt_s": friction["dt_s"],
            "damping_stiffness": "read_neutralize_and_restore_with_readback",
            "effort_limit": "readback_headroom_and_restore",
            "friction": "native_write_and_selected_buffer_readback",
            "trial_protocol": "independent_static_friction_trial_per_grid_command",
            "trial_reset": "clear_hinge_target_write_baseline_joint_state_then_one_scene_step",
            "trial_frame_authority": "V23_EXTERNAL_TORQUE_PROBE_100_FRAME_TRIAL",
            "independent_reset_per_command": True,
            "breakaway_containment": "lower <= requested <= upper",
            "stop_at_first_breakaway": True,
            "scene_isolation": "door_only_no_robot_no_contact_sensor_handle_latch_isolated",
            "hinge_target_cleanup": "zero_and_restore_in_one_try_finally",
            "grid_spacing_nm": friction["resolution_effort_nm"],
            "first_sample_timing_step": friction["hold_window_steps"],
            "breakaway_definition": {
                "angle_resolution_rad": friction["angle_resolution_rad"],
                "velocity_threshold_rad_s": friction["velocity_threshold_rad_s"],
                "hold_window_steps": friction["hold_window_steps"],
                "hold_window_authority": "V23_EXTERNAL_TORQUE_PROBE_100_FRAME_TRIAL",
                "stationarity_angle_tolerance_rad": friction["stationarity_angle_tolerance_rad"],
                "stationarity_velocity_tolerance_rad_s": friction["stationarity_velocity_tolerance_rad_s"],
                "requested_static_must_be_in_measured_bracket": True,
                "containment_formula": "lower <= requested <= upper",
                "containment_tolerance_applied": False,
            },
            "receipt_fields": [
                "door_fixture",
                "independent_trial_protocol",
                "executed_command_count",
                "requested_static_effort_nm",
                "requested_dynamic_effort_nm",
                "requested_viscous_coefficient_nm_s_per_rad",
                "angle_rad",
                "velocity_rad_s",
                "command_effort_nm",
                "timing_step",
                "trial_index",
                "trial_frames",
                "start_angle_rad",
                "start_velocity_rad_s",
                "breakaway_definition",
                "measured_bracket_nm",
                "measured_threshold_nm",
                "tolerance_nm",
                "grid_resolution_nm",
                "containment_formula",
                "authority",
                "friction_readback",
            ],
        },
        "off_parity": build_off_parity_plan(config_path),
        "foot_force_detect": build_foot_force_detect_plan(),
    }


def _build_door_only_scene(
    *, device: str, dt: float, probe_seed: int
) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Build the source-locked v23 door-only InteractiveScene pattern."""

    import numpy as np

    if isinstance(probe_seed, bool) or not isinstance(probe_seed, int) or probe_seed < 0:
        raise ValueError("v24 torque-ramp probe_seed must be a non-negative integer")
    np.random.seed(probe_seed)

    import isaaclab.sim as sim_utils
    from isaaclab.assets import Articulation, ArticulationCfg, AssetBaseCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.utils import configclass

    from gr00t.rl.data.tasks.door.scenario_cfg.isaacsim import TaskObjCfgDict
    from gr00t.rl.isaac_utils.playground.env_rand.door import DoorSpawnerCfg

    base_door_cfg = TaskObjCfgDict["door"]
    base_spawn = base_door_cfg.spawn
    base_assets = list(base_spawn.assets_cfg)
    if not base_assets or not isinstance(base_assets[0], DoorSpawnerCfg):
        raise TypeError("v24 torque ramp requires the source-backed DoorSpawnerCfg base asset")
    base_asset = base_assets[0]
    source_asset = base_asset.replace(**DOOR_FIXED_CONFIG)
    door_spawn = base_spawn.replace(
        assets_cfg=[source_asset],
        random_choice=False,
        activate_contact_sensors=False,
    )
    door_joint_pos = dict(base_door_cfg.init_state.joint_pos)
    door_joint_pos.pop(".*latch.*", None)
    door_cfg = base_door_cfg.replace(
        spawn=door_spawn,
        prim_path="{ENV_REGEX_NS}/door",
        init_state=base_door_cfg.init_state.replace(joint_pos=door_joint_pos),
    )

    @configclass
    class DoorFrictionSceneCfg(InteractiveSceneCfg):
        ground = AssetBaseCfg(
            prim_path="/World/defaultGroundPlane",
            spawn=sim_utils.GroundPlaneCfg(),
        )
        dome_light = AssetBaseCfg(
            prim_path="/World/DomeLight",
            spawn=sim_utils.DomeLightCfg(intensity=1500.0),
        )
        door: ArticulationCfg = door_cfg

    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=dt, device=device))
    scene = InteractiveScene(
        DoorFrictionSceneCfg(num_envs=1, env_spacing=6.0, replicate_physics=False)
    )
    sim.reset()
    if set(scene.articulations) != {"door"}:
        raise RuntimeError(f"v24 torque ramp scene must contain only door articulation; got {scene.articulations.keys()!r}")
    if scene.sensors:
        raise RuntimeError("v24 torque ramp scene must not create contact or other sensors")
    door = scene["door"]
    return sim, scene, door, _door_fixture_profile(probe_seed)


def _step_door_scene(sim: Any, scene: Any, dt: float) -> None:
    scene.write_data_to_sim()
    sim.step()
    scene.update(dt)


def _select_single_hinge(door: Any) -> tuple[int, str]:
    hinge_ids, hinge_names = door.find_joints(HINGE_PATTERN, preserve_order=True)
    if len(hinge_ids) != 1 or len(hinge_names) != 1:
        raise RuntimeError(
            "TORQUE_RAMP requires exactly one production door hinge; "
            f"got ids={hinge_ids!r}, names={hinge_names!r}"
        )
    return int(hinge_ids[0]), str(hinge_names[0])


def _clear_hinge_target(door: Any, hinge_id: int, env_ids: Any) -> None:
    import torch

    target = door.data.joint_effort_target[env_ids].clone()
    target[:, hinge_id] = 0.0
    door.set_joint_effort_target(target, env_ids=env_ids)


def _selected_hinge_field(door: Any, field: str, env_ids: Any, hinge_id: int) -> Any:
    import torch

    value = getattr(door.data, field, None)
    if not torch.is_tensor(value) or value.ndim != 2 or value.shape[1] <= hinge_id:
        raise RuntimeError(f"door.data.{field} is unavailable for hinge {hinge_id}")
    selected = value[env_ids][:, [hinge_id]].clone()
    if selected.shape != (env_ids.numel(), 1):
        raise RuntimeError(f"door.data.{field} selected shape mismatch: {selected.shape}")
    return selected


def _restore_friction(door: Any, env_ids: Any, hinge_id: int, original: Mapping[str, Any]) -> dict[str, Any]:
    import torch

    door.write_joint_friction_coefficient_to_sim(
        original["joint_friction_coeff"],
        original["joint_dynamic_friction_coeff"],
        original["joint_viscous_friction_coeff"],
        joint_ids=[hinge_id],
        env_ids=env_ids,
    )
    readback = {
        field: _selected_hinge_field(door, field, env_ids, hinge_id)
        for field in original
    }
    matches = {
        field: bool(torch.allclose(original[field], readback[field], atol=1.0e-6, rtol=0.0))
        for field in original
    }
    if not all(matches.values()):
        raise RuntimeError(f"friction cleanup readback mismatch: {matches!r}")
    return {
        "requested": {field: value.detach().cpu().tolist() for field, value in original.items()},
        "readback": {field: value.detach().cpu().tolist() for field, value in readback.items()},
        "matches": matches,
    }


def run_torque_ramp(
    *,
    sim: Any,
    scene: Any,
    friction: Mapping[str, Any],
    door_fixture: Mapping[str, Any],
    device: str,
    dt: float,
) -> dict[str, Any]:
    """Run independent 100-frame static-friction trials in the door-only scene."""

    import torch

    from gr00t.rl.envs.door.a2_v24_friction import A2V24DoorFrictionBackend, V24FrictionConfig

    door = scene["door"]
    hinge_id, hinge_name = _select_single_hinge(door)
    env_ids = torch.arange(1, dtype=torch.long, device=device)
    env_ids = env_ids.to(door.data.joint_pos.device)
    if env_ids.device != door.data.joint_pos.device:
        raise RuntimeError("door-only probe env id/device mismatch")

    friction_config = V24FrictionConfig.from_mapping(
        {
            "a2_v24_friction_enabled": True,
            "a2_v24_friction_backend": friction["backend"],
            "a2_v24_friction_static_effort": friction["static_effort_nm"],
            "a2_v24_friction_dynamic_effort": friction["dynamic_effort_nm"],
            "a2_v24_friction_viscous_coefficient": friction["viscous_coefficient_nm_s_per_rad"],
        }
    )
    backend = A2V24DoorFrictionBackend(door, friction_config, device=door.data.joint_pos.device)
    original_friction = {
        field: _selected_hinge_field(door, field, env_ids, hinge_id)
        for field in ("joint_friction_coeff", "joint_dynamic_friction_coeff", "joint_viscous_friction_coeff")
    }
    original_damping = _selected_hinge_field(door, "joint_damping", env_ids, hinge_id)
    original_stiffness = _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id)
    original_effort_limit = _selected_hinge_field(door, "joint_effort_limits", env_ids, hinge_id)
    original_targets = door.data.joint_effort_target[env_ids].clone()
    baseline_joint_position = door.data.joint_pos[env_ids].clone()
    captured_baseline_velocity = door.data.joint_vel[env_ids].clone()
    baseline_joint_velocity = torch.zeros_like(captured_baseline_velocity)
    max_command = float(friction["ramp_end_effort_nm"])
    limit_value = float(original_effort_limit.min().item())
    if limit_value <= max_command:
        raise RuntimeError(
            f"hinge effort-limit headroom is insufficient: limit={limit_value}, max_command={max_command}"
        )

    primary_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    receipt: dict[str, Any] | None = None
    try:
        receipt = backend.apply(env_ids)
        door.write_joint_damping_to_sim(torch.zeros_like(original_damping), joint_ids=[hinge_id], env_ids=env_ids)
        door.write_joint_stiffness_to_sim(torch.zeros_like(original_stiffness), joint_ids=[hinge_id], env_ids=env_ids)
        neutral_damping = _selected_hinge_field(door, "joint_damping", env_ids, hinge_id)
        neutral_stiffness = _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id)
        if not bool(torch.all(neutral_damping == 0.0).item()) or not bool(torch.all(neutral_stiffness == 0.0).item()):
            raise RuntimeError("damping/stiffness neutralization readback failed")

        _clear_hinge_target(door, hinge_id, env_ids)
        scene.write_data_to_sim()
        settle_start_angle = float(door.data.joint_pos[env_ids, hinge_id].item())
        settle_max_delta = 0.0
        settle_max_velocity = 0.0
        for _ in range(friction["settle_steps"]):
            _step_door_scene(sim, scene, dt)
            angle = float(door.data.joint_pos[env_ids, hinge_id].item())
            velocity = float(door.data.joint_vel[env_ids, hinge_id].item())
            settle_max_delta = max(settle_max_delta, abs(angle - settle_start_angle))
            settle_max_velocity = max(settle_max_velocity, abs(velocity))
        stationarity = {
            "settle_window_steps": friction["settle_steps"],
            "max_angle_delta_rad": settle_max_delta,
            "max_velocity_rad_s": settle_max_velocity,
            "angle_tolerance_rad": friction["stationarity_angle_tolerance_rad"],
            "velocity_tolerance_rad_s": friction["stationarity_velocity_tolerance_rad_s"],
            "passed": settle_max_delta <= friction["stationarity_angle_tolerance_rad"]
            and settle_max_velocity <= friction["stationarity_velocity_tolerance_rad_s"],
        }
        if not stationarity["passed"]:
            raise RuntimeError(f"zero-command stationarity prerequisite failed: {stationarity!r}")

        commands = friction["ramp_start_effort_nm"] + friction["resolution_effort_nm"] * torch.arange(
            friction["ramp_interval_count"] + 1,
            dtype=door.data.joint_pos.dtype,
            device=door.data.joint_pos.device,
        )
        actual_spacing = float((commands[1] - commands[0]).item())
        if actual_spacing != friction["resolution_effort_nm"]:
            raise RuntimeError(f"torque grid spacing drifted: {actual_spacing}")
        rows: list[dict[str, Any]] = []
        breakaway_index: int | None = None
        breakaway_threshold: float | None = None
        for step_index, command in enumerate(commands.tolist()):
            _clear_hinge_target(door, hinge_id, env_ids)
            door.write_joint_state_to_sim(
                baseline_joint_position,
                baseline_joint_velocity,
                env_ids=env_ids,
            )
            _step_door_scene(sim, scene, dt)
            trial_start_angle = float(door.data.joint_pos[env_ids, hinge_id].item())
            trial_start_velocity = float(door.data.joint_vel[env_ids, hinge_id].item())
            if abs(trial_start_velocity) > friction["stationarity_velocity_tolerance_rad_s"]:
                raise RuntimeError(
                    "independent trial reset did not reach the stationarity velocity tolerance: "
                    f"command={command}, velocity={trial_start_velocity}"
                )
            command_tensor = torch.full(
                (env_ids.numel(), 1), command, dtype=door.data.joint_pos.dtype, device=door.data.joint_pos.device
            )
            door.set_joint_effort_target(command_tensor, joint_ids=[hinge_id], env_ids=env_ids)
            for _ in range(friction["hold_window_steps"]):
                _step_door_scene(sim, scene, dt)
            angle = float(door.data.joint_pos[env_ids, hinge_id].item())
            velocity = float(door.data.joint_vel[env_ids, hinge_id].item())
            delta = abs(angle - trial_start_angle)
            rows.append(
                {
                    "step": step_index,
                    "trial_index": step_index,
                    "timing_step": friction["hold_window_steps"],
                    "trial_frames": friction["hold_window_steps"],
                    "command_effort_nm": command,
                    "start_angle_rad": trial_start_angle,
                    "start_velocity_rad_s": trial_start_velocity,
                    "angle_rad": angle,
                    "velocity_rad_s": velocity,
                    "angle_delta_rad": delta,
                    "independent_reset": True,
                }
            )
            if (
                delta >= friction["angle_resolution_rad"]
                and abs(velocity) >= friction["velocity_threshold_rad_s"]
            ):
                breakaway_index = step_index
                breakaway_threshold = command
                break

        if breakaway_index is None:
            measured_bracket = None
            requested_in_bracket = False
            measured_status = "BREAKAWAY_NOT_OBSERVED"
        else:
            if breakaway_index == 0:
                raise RuntimeError("breakaway at the first grid command has no previous command to bracket")
            lower = float(commands[breakaway_index - 1].item())
            upper = float(commands[breakaway_index].item())
            measured_bracket = [lower, upper]
            requested = friction["static_effort_nm"]
            requested_in_bracket = bool(lower <= requested <= upper)
            measured_status = "PASS" if requested_in_bracket else "FAIL_REQUESTED_STATIC_OUTSIDE_BRACKET"
    except BaseException as exc:
        primary_error = exc
    finally:
        try:
            cleanup_target = original_targets.clone()
            cleanup_target[:, hinge_id] = 0.0
            door.set_joint_effort_target(cleanup_target, env_ids=env_ids)
            door.write_joint_damping_to_sim(original_damping, joint_ids=[hinge_id], env_ids=env_ids)
            door.write_joint_stiffness_to_sim(original_stiffness, joint_ids=[hinge_id], env_ids=env_ids)
            door.write_joint_effort_limit_to_sim(original_effort_limit, joint_ids=[hinge_id], env_ids=env_ids)
            cleanup_friction = _restore_friction(door, env_ids, hinge_id, original_friction)
            scene.write_data_to_sim()
            final_targets = door.data.joint_effort_target[env_ids].clone()
            if not bool(torch.all(final_targets[:, hinge_id] == 0.0).item()):
                raise RuntimeError("hinge effort target cleanup readback failed")
            final_damping = _selected_hinge_field(door, "joint_damping", env_ids, hinge_id)
            final_stiffness = _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id)
            final_effort_limit = _selected_hinge_field(door, "joint_effort_limits", env_ids, hinge_id)
            if not bool(torch.allclose(final_damping, original_damping, atol=1.0e-6, rtol=0.0)):
                raise RuntimeError("damping cleanup readback failed")
            if not bool(torch.allclose(final_stiffness, original_stiffness, atol=1.0e-6, rtol=0.0)):
                raise RuntimeError("stiffness cleanup readback failed")
            if not bool(torch.allclose(final_effort_limit, original_effort_limit, atol=1.0e-6, rtol=0.0)):
                raise RuntimeError("effort-limit cleanup readback failed")
        except BaseException as exc:
            cleanup_error = exc

    if primary_error is not None:
        if cleanup_error is not None:
            raise RuntimeError("TORQUE_RAMP failed and cleanup also failed") from primary_error
        raise primary_error
    if cleanup_error is not None:
        raise cleanup_error
    if receipt is None:
        raise RuntimeError("TORQUE_RAMP completed without friction receipt")

    non_hinge_ids = [joint_id for joint_id in range(door.num_joints) if joint_id != hinge_id]
    non_hinge_unchanged = bool(torch.equal(final_targets[:, non_hinge_ids], original_targets[:, non_hinge_ids]))
    if not non_hinge_unchanged:
        raise RuntimeError("TORQUE_RAMP changed a non-hinge effort target")

    return {
        "schema": PROBE_SCHEMA,
        "status": measured_status,
        "mode": FIRST_RUNTIME_MODE,
        "door_fixture": dict(door_fixture),
        "backend": backend.receipt_fragment(),
        "friction_readback": receipt,
        "hinge_joint_name": hinge_name,
        "hinge_joint_id": hinge_id,
        "requested_profile": {
            "static_effort_nm": friction["static_effort_nm"],
            "dynamic_effort_nm": friction["dynamic_effort_nm"],
            "viscous_coefficient_nm_s_per_rad": friction["viscous_coefficient_nm_s_per_rad"],
        },
        "executed_command_count": len(rows),
        "independent_trial_protocol": {
            "reset_per_command": True,
            "reset_order": "clear_hinge_target -> write_joint_state_to_sim -> scene.write_data_to_sim -> sim.step -> scene.update",
            "state_writer": "Articulation.write_joint_state_to_sim",
            "trial_frames": friction["hold_window_steps"],
            "trial_frame_authority": "V23_EXTERNAL_TORQUE_PROBE_100_FRAME_TRIAL",
            "baseline_joint_position": baseline_joint_position.detach().cpu().tolist(),
            "captured_baseline_velocity": captured_baseline_velocity.detach().cpu().tolist(),
            "baseline_joint_velocity_written": baseline_joint_velocity.detach().cpu().tolist(),
            "stationarity_velocity_tolerance_rad_s": friction["stationarity_velocity_tolerance_rad_s"],
            "containment_formula": "lower <= requested <= upper",
            "stop_at_first_breakaway": True,
            "command_effort_authority": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
        },
        "neutralization": {
            "damping_recorded": original_damping.detach().cpu().tolist(),
            "stiffness_recorded": original_stiffness.detach().cpu().tolist(),
            "hinge_damping_neutralized": True,
            "hinge_stiffness_neutralized": True,
            "damping_neutral_readback": neutral_damping.detach().cpu().tolist(),
            "stiffness_neutral_readback": neutral_stiffness.detach().cpu().tolist(),
        },
        "scene_evidence": {
            "articulations": list(scene.articulations.keys()),
            "sensors": list(scene.sensors.keys()),
            "door_only": True,
            "handle_latch_isolation": {
                "build_latch": False,
                "handle_drive_max_force": 0.0,
                "contact_sensors": False,
            },
        },
        "effort_limit": {
            "readback_nm": original_effort_limit.detach().cpu().tolist(),
            "max_command_nm": max_command,
            "headroom_passed": limit_value > max_command,
            "authority": "HIGH_LEVEL_ARTICULATION_EFFORT_LIMIT_READBACK",
        },
        "stationarity": stationarity,
        "samples": rows,
        "breakaway": {
            "definition": {
                "angle_resolution_rad": friction["angle_resolution_rad"],
                "velocity_threshold_rad_s": friction["velocity_threshold_rad_s"],
                "hold_window_steps": friction["hold_window_steps"],
                "hold_window_authority": "V23_EXTERNAL_TORQUE_PROBE_100_FRAME_TRIAL",
            },
            "measured_bracket_nm": measured_bracket,
            "measured_threshold_nm": breakaway_threshold,
            "requested_static_effort_nm": friction["static_effort_nm"],
            "tolerance_nm": 0.0,
            "grid_resolution_nm": friction["resolution_effort_nm"],
            "requested_static_in_bracket": requested_in_bracket,
            "containment_formula": "lower <= requested <= upper",
            "containment_tolerance_applied": False,
            "authority": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
        },
        "non_hinge_effort_targets": {
            "unchanged": non_hinge_unchanged,
            "authority": "HIGH_LEVEL_ARTICULATION_JOINT_EFFORT_TARGET_BUFFER",
        },
        "robot_contact_source": {
            "status": "NOT_PRESENT_IN_DOOR_ONLY_SCENE",
            "authority": "DOOR_ONLY_SCENE_HAS_NO_ROBOT_OR_CONTACT_SENSOR",
        },
        "hinge_target_cleanup": {
            "cleared_at_ramp_completion": True,
            "non_hinge_targets_unchanged": non_hinge_unchanged,
            "restored_original_damping": True,
            "restored_original_stiffness": True,
            "restored_original_effort_limit": True,
            "restored_original_friction": cleanup_friction,
        },
        "timing": {
            "physics_order": "scene.write_data_to_sim -> sim.step -> scene.update",
            "ramp_interval_count": friction["ramp_interval_count"],
            "grid_spacing_nm": actual_spacing,
            "dt_s": friction["dt_s"],
            "hold_window_steps": friction["hold_window_steps"],
            "trial_frame_authority": "V23_EXTERNAL_TORQUE_PROBE_100_FRAME_TRIAL",
            "independent_reset_per_command": True,
            "executed_command_count": len(rows),
            "stopped_at_first_breakaway": breakaway_index is not None,
            "settle_steps_preregistered": friction["settle_steps"],
        },
    }


def _run_runtime(config_path: Path, *, device: str, output: Path) -> None:
    _assert_selected_sources(config_path)
    friction = _probe_config_values(config_path)
    sim, scene, _door, door_fixture = _build_door_only_scene(
        device=device,
        dt=friction["dt_s"],
        probe_seed=friction["probe_seed"],
    )
    try:
        payload = run_torque_ramp(
            sim=sim,
            scene=scene,
            friction=friction,
            door_fixture=door_fixture,
            device=device,
            dt=friction["dt_s"],
        )
        write_json(output, payload)
    finally:
        sim.clear_instance()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="emit a CPU-only execution plan")
    parser.add_argument("--mode", choices=MODE_ORDER, default=FIRST_RUNTIME_MODE)
    parser.add_argument("--config", type=Path, default=PRODUCTION_CONFIG)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--device", default="cuda:0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config_path = absolute(args.config)
    if args.plan:
        plan = build_plan(config_path)
        if args.output is None:
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            write_json(args.output, plan)
        return 0
    if args.mode != FIRST_RUNTIME_MODE:
        raise RuntimeError(
            f"{args.mode} is planned for a later P1 lane and is not executable in this first runtime producer"
        )
    if args.output is None:
        raise ValueError("runtime TORQUE_RAMP requires --output under the canonical v24 artifact root")
    output = absolute(args.output)
    if V24_P1_FRICTION_ROOT not in output.parents:
        raise ValueError(
            "runtime output must be under logs_eval/base_v24/p1/friction_backend/"
        )
    _assert_selected_sources(config_path)
    _probe_config_values(config_path)
    from isaaclab.app import AppLauncher

    launcher = AppLauncher({"headless": True, "device": args.device, "enable_cameras": False})
    try:
        _run_runtime(config_path, device=args.device, output=output)
    finally:
        launcher.app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
