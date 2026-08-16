"""v24 P1a native hinge-friction probe.

``TORQUE_RAMP`` builds the source-locked v23 door-only ``InteractiveScene``
and drives its door articulation through IsaacLab's high-level API, records the
requested friction profile and a measured breakaway bracket, then
clears/restores the hinge state.  ``A_I_ACCEPTANCE`` composes the registered
door-only A--G acceptance trials on the same native backend and emits typed
pending receipts for the external H/I gates.  ``OFF_PARITY`` and
``FOOT_FORCE_DETECT`` remain planning specifications for later P1 lanes; this
producer does not execute them.

``--plan`` is CPU-only and never imports or starts IsaacSim.  Runtime output
folders are deliberately supplied by the caller under the canonical
``logs_eval/base_v24/p1/friction_backend/`` root.
"""

from __future__ import annotations

import argparse
import json
import math
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

try:
    from .p0_unit_contract import (
        USD_DEGREE_SURFACE,
        TRACE_CONFIG_SURFACE,
        normalize_realized_dynamics,
        scaled_distance,
    )
except ImportError:  # direct ``python scriptsFORhuman/v24/...py`` invocation
    from scriptsFORhuman.v24.p0_unit_contract import (
        USD_DEGREE_SURFACE,
        TRACE_CONFIG_SURFACE,
        normalize_realized_dynamics,
        scaled_distance,
    )


PROBE_SCHEMA = "a2_piper_v24_p1_native_friction_probe_v1"
FRICTION_BACKEND = "native_joint_friction_v1"
FIRST_RUNTIME_MODE = "TORQUE_RAMP"
AI_ACCEPTANCE_MODE = "A_I_ACCEPTANCE"
ENERGY_MODE = "D_V2_ENERGY"
MODE_ORDER = (FIRST_RUNTIME_MODE, AI_ACCEPTANCE_MODE, ENERGY_MODE, "OFF_PARITY", "FOOT_FORCE_DETECT")
PRODUCTION_CONFIG = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v24_p1_native_probe.yaml"
D_V2_CONFIG = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v24_p1_d_v2_energy.yaml"
SELECTED_CHECKPOINT = REPO_ROOT / (
    "logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt"
)
D_V2_PRODUCER_SCHEMA = "a2_piper_v24_p1_d_v2_energy_v1"
D_V2_TOLERANCE_SCHEMA = "a2_piper_v24_p1_d_v2_tolerance_freeze_v1"
D_V2_ADJUDICATION_SCHEMA = "a2_piper_base_v24_p1_d_v2_owner_revision_adjudication_v1"
D_V2_ARTIFACT_ROOT = V24_P1_FRICTION_ROOT / "d_v2_energy_r1_gpu0"
D_V2_SEED = 24017
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


def _door_fixture_profile(
    probe_seed: int, door_config: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    fixture_config = DOOR_FIXED_CONFIG if door_config is None else door_config
    return {
        "probe_seed": probe_seed,
        "geometry": {
            "door_width_m": fixture_config["rand_door_width"],
            "door_height_m": fixture_config["rand_door_height"],
            "handle_height_m": fixture_config["rand_door_handle_height"],
            "handle_width_m": fixture_config["rand_door_handle_width"],
            "total_wall_height_m": fixture_config["rand_total_wall_height"],
            "axle_length_m": fixture_config["rand_axle_length"],
            "handle_length_m": fixture_config["rand_handle_length"],
            "hook_length_m": fixture_config["rand_hook_length"],
            "handle_radius_m": fixture_config["rand_handle_radius"],
            "handle_type": fixture_config["rand_door_handle_type"],
            "open_lr": fixture_config["rand_door_open_lr"],
            "open_io": fixture_config["rand_door_open_io"],
            "spawn_hook": fixture_config["rand_spawn_hook"],
        },
        "mass_inertia_inputs": {
            "door_panel_mass_kg": fixture_config["rand_door_weight"],
            "top_frame_mass_kg": 100.0,
            "axle_mass_kg": 0.2,
            "handle_inside_mass_kg": 0.1,
            "handle_outside_mass_kg": 0.1,
            "hook_mass_kg": 0.0,
            "grasp_target_mass_kg": 0.001,
        },
        "dynamics": {
            "hinge_drive_max_force_nm": fixture_config["rand_hinge_drive_max_force"],
            "hinge_drive_damping_native": fixture_config["rand_hinge_drive_damping"],
            "hinge_drive_stiffness_native": fixture_config["rand_hinge_drive_stiffness"],
            "handle_drive_max_force_nm": fixture_config["rand_handle_drive_max_force"],
        },
        "isolation": {
            "build_latch": fixture_config["build_latch"],
            "randomize_material": fixture_config["randomize_material"],
            "use_preloaded_materials": fixture_config["use_preloaded_materials"],
            "dynamic_material_randomization": fixture_config["dynamic_material_randomization"],
            "activate_contact_sensors": fixture_config["activate_contact_sensors"],
            "add_walls": fixture_config["add_walls"],
            "add_floors": fixture_config["add_floors"],
            "add_lights": fixture_config["add_lights"],
            "add_ceiling": fixture_config["add_ceiling"],
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


def _d_v2_config_values(config_path: Path = D_V2_CONFIG) -> dict[str, Any]:
    """Read the dedicated D-v2 overlay without resolving Hydra defaults."""

    config_path = absolute(config_path).resolve()
    if config_path != D_V2_CONFIG.resolve():
        raise ValueError("D_V2_ENERGY requires the dedicated D-v2 overlay config")
    payload = _read_yaml(config_path)
    if payload.get("v24_schema") != D_V2_PRODUCER_SCHEMA:
        raise ValueError("D-v2 overlay schema does not match the producer schema")
    if payload.get("v24_runtime_mode") != ENERGY_MODE:
        raise ValueError("D-v2 overlay runtime mode must be D_V2_ENERGY")
    raw = payload.get("v24_d_v2")
    if not isinstance(raw, Mapping) or raw.get("enabled") is not True:
        raise ValueError("v24_d_v2.enabled must be true")
    if raw.get("producer_schema") != D_V2_PRODUCER_SCHEMA:
        raise ValueError("v24_d_v2.producer_schema mismatch")
    if raw.get("tolerance_schema") != D_V2_TOLERANCE_SCHEMA:
        raise ValueError("v24_d_v2.tolerance_schema mismatch")
    if raw.get("adjudication_schema") != D_V2_ADJUDICATION_SCHEMA:
        raise ValueError("v24_d_v2.adjudication_schema mismatch")
    probe_seed = raw.get("probe_seed")
    if isinstance(probe_seed, bool) or not isinstance(probe_seed, int) or probe_seed != D_V2_SEED:
        raise ValueError(f"v24_d_v2.probe_seed must be exactly {D_V2_SEED}")
    if raw.get("device") != "cuda:0":
        raise ValueError("v24_d_v2.device must be exactly cuda:0")

    model = raw.get("model")
    spring = raw.get("spring")
    trajectories = raw.get("trajectories")
    profiles_raw = raw.get("friction_profiles")
    tolerance = raw.get("tolerance")
    authorities = raw.get("authority_labels")
    for name, value in (
        ("model", model),
        ("spring", spring),
        ("trajectories", trajectories),
        ("friction_profiles", profiles_raw),
        ("tolerance", tolerance),
        ("authority_labels", authorities),
    ):
        if not isinstance(value, Mapping):
            raise TypeError(f"v24_d_v2.{name} must be a mapping")

    panel_mass = finite_number(model.get("panel_mass_kg"), label="d_v2.model.panel_mass_kg")
    panel_width = finite_number(model.get("panel_width_m"), label="d_v2.model.panel_width_m")
    inertia = finite_number(model.get("inertia_kg_m2"), label="d_v2.model.inertia_kg_m2")
    if panel_mass != 120.0 or panel_width != 0.95 or inertia != 36.1:
        raise ValueError("D-v2 model parameters must remain 120.0 kg, 0.95 m, and 36.1 kg*m^2")
    if model.get("inertia_formula") != "(1/3)*120*0.95^2=36.1 kg*m^2":
        raise ValueError("D-v2 inertia formula must remain explicit and parameter-derived")
    if model.get("inertia_authority") != "MODELED_FROM_PARAMS_UNIFORM_PANEL_EDGE":
        raise ValueError("D-v2 inertia authority must remain modeled-from-params")
    if "default_inertia" in model:
        raise ValueError("D-v2 must not use default_inertia")

    stiffness = finite_number(spring.get("stiffness_nm_per_rad"), label="d_v2.spring.stiffness_nm_per_rad")
    damping = finite_number(spring.get("damping_nm_s_per_rad"), label="d_v2.spring.damping_nm_s_per_rad")
    theta_ref = finite_number(spring.get("theta_ref_rad"), label="d_v2.spring.theta_ref_rad")
    theta_initial = finite_number(spring.get("theta_initial_rad"), label="d_v2.spring.theta_initial_rad")
    velocity_target = finite_number(spring.get("velocity_target_rad_s"), label="d_v2.spring.velocity_target_rad_s")
    if (stiffness, damping, theta_ref, theta_initial, velocity_target) != (6.0, 0.0, 0.5, 0.5, 0.0):
        raise ValueError("D-v2 spring/target values must remain k=6, damping=0, theta=0.5, omega=0")
    if spring.get("surface") != "HIGH_LEVEL_RAD_SURFACE" or spring.get("target_dependency") != "NONE":
        raise ValueError("D-v2 targets must identify the high-level rad surface with no USD dependency")

    raw_signs = trajectories.get("signs")
    if not isinstance(raw_signs, list) or tuple(raw_signs) != (-1, 1):
        raise ValueError("D-v2 trajectory signs must remain exactly [-1, +1]")
    stationarity_steps = trajectories.get("stationarity_steps")
    command_steps = trajectories.get("command_steps")
    coast_steps = trajectories.get("coast_steps")
    for name, value in (("stationarity_steps", stationarity_steps), ("command_steps", command_steps), ("coast_steps", coast_steps)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"D-v2 {name} must be a positive integer")
    command_effort = finite_number(trajectories.get("command_effort_nm"), label="d_v2.trajectories.command_effort_nm")
    dt_s = finite_number(trajectories.get("dt_s"), label="d_v2.trajectories.dt_s")
    if (stationarity_steps, command_steps, coast_steps, command_effort, dt_s) != (20, 100, 100, 2.0, 0.005):
        raise ValueError("D-v2 trajectory contract must remain 20/100/100 steps, 2.0 Nm, dt=0.005")

    if tuple(profiles_raw.keys()) != ("F00", "F10"):
        raise ValueError("D-v2 friction profiles must be ordered F00/F10")
    expected_profiles = {"F00": (0.0, 0.0, 0.0), "F10": (1.0, 0.75, 0.0)}
    profiles: dict[str, dict[str, float]] = {}
    for profile_name in ("F00", "F10"):
        profile = profiles_raw[profile_name]
        if not isinstance(profile, Mapping):
            raise TypeError(f"D-v2 friction profile {profile_name} must be a mapping")
        values = (
            finite_number(profile.get("static_effort_nm"), label=f"d_v2.{profile_name}.static_effort_nm"),
            finite_number(profile.get("dynamic_effort_nm"), label=f"d_v2.{profile_name}.dynamic_effort_nm"),
            finite_number(profile.get("viscous_coefficient_nm_s_per_rad"), label=f"d_v2.{profile_name}.viscous_coefficient_nm_s_per_rad"),
        )
        if values != expected_profiles[profile_name]:
            raise ValueError(f"D-v2 {profile_name} friction profile must remain {expected_profiles[profile_name]!r}")
        profiles[profile_name] = {
            "static_effort_nm": values[0],
            "dynamic_effort_nm": values[1],
            "viscous_coefficient_nm_s_per_rad": values[2],
        }

    multiplier = finite_number(tolerance.get("multiplier"), label="d_v2.tolerance.multiplier")
    floor_j = finite_number(tolerance.get("floor_j"), label="d_v2.tolerance.floor_j")
    if (multiplier, floor_j) != (2.0, 1.0e-12):
        raise ValueError("D-v2 tolerance overlay must fix multiplier=2.0 and floor=1e-12 J")
    expected_authorities = {
        "solver_friction_torque_component": "UNAVAILABLE_NOT_USED",
        "actual_generalized_torque_claim": False,
        "friction_params": "MODELED_FROM_PARAMS",
        "modeled_torque": "MODELED_FROM_PARAMS",
        "command_work": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
        "state": "HIGH_LEVEL_ARTICULATION_DATA",
        "stiffness": "CONFIGURED_HIGH_LEVEL_RAD_SURFACE_READBACK",
    }
    if dict(authorities) != expected_authorities:
        raise ValueError("D-v2 authority labels do not match the owner contract")
    return {
        "schema": D_V2_PRODUCER_SCHEMA,
        "tolerance_schema": D_V2_TOLERANCE_SCHEMA,
        "adjudication_schema": D_V2_ADJUDICATION_SCHEMA,
        "probe_seed": probe_seed,
        "device": "cuda:0",
        "config_path": config_path,
        "model": {
            "panel_mass_kg": panel_mass,
            "panel_width_m": panel_width,
            "inertia_kg_m2": inertia,
            "inertia_formula": model["inertia_formula"],
            "inertia_authority": model["inertia_authority"],
        },
        "spring": {
            "stiffness_nm_per_rad": stiffness,
            "damping_nm_s_per_rad": damping,
            "theta_ref_rad": theta_ref,
            "theta_initial_rad": theta_initial,
            "velocity_target_rad_s": velocity_target,
            "surface": spring["surface"],
            "target_dependency": spring["target_dependency"],
        },
        "trajectories": {
            "signs": list(raw_signs),
            "stationarity_steps": stationarity_steps,
            "command_steps": command_steps,
            "coast_steps": coast_steps,
            "command_effort_nm": command_effort,
            "dt_s": dt_s,
        },
        "friction_profiles": profiles,
        "tolerance": {"multiplier": multiplier, "floor_j": floor_j},
        "authority_labels": dict(authorities),
    }


AI_PROFILE_ORDER = ("F00", "F05", "F10")
AI_SPEED_ORDER = (-0.2, -0.1, 0.1, 0.2)
AI_SPARSE_CELL_ORDER = ("A0", "A1", "A4", "A5", "A8", "F10")
AI_SURFACE_TAGS = {
    "joint_position": "rad",
    "joint_velocity": "rad_s",
    "effort": "Nm_command_target_only",
    "degree_surface": "not_used_for_acceptance",
}


def _ai_acceptance_config(config_path: Path, friction: Mapping[str, Any]) -> dict[str, Any]:
    payload = _read_yaml(config_path)
    raw = payload.get("v24_ai_acceptance")
    if not isinstance(raw, Mapping):
        raise ValueError("v24_ai_acceptance config block is required")
    if raw.get("enabled") is not True:
        raise ValueError("v24_ai_acceptance.enabled must be true for A_I_ACCEPTANCE")
    batch_id = raw.get("batch_id")
    device = raw.get("device")
    if not isinstance(batch_id, str) or not batch_id:
        raise ValueError("v24_ai_acceptance.batch_id must be a non-empty string")
    if device != "cuda:0":
        raise ValueError("v24_ai_acceptance.device must be the single leased GPU0 device cuda:0")

    raw_profiles = raw.get("friction_profiles")
    if not isinstance(raw_profiles, Mapping) or tuple(raw_profiles.keys()) != AI_PROFILE_ORDER:
        raise ValueError("v24_ai_acceptance.friction_profiles must be ordered F00/F05/F10")
    profiles: dict[str, dict[str, float]] = {}
    expected_profiles = {
        "F00": (0.0, 0.0, 0.0),
        "F05": (0.5, 0.375, 0.0),
        "F10": (1.0, 0.75, 0.0),
    }
    for name in AI_PROFILE_ORDER:
        item = raw_profiles[name]
        if not isinstance(item, Mapping):
            raise TypeError(f"v24_ai_acceptance friction profile {name} must be a mapping")
        values = (
            finite_number(item.get("static_effort_nm"), label=f"{name}.static_effort_nm"),
            finite_number(item.get("dynamic_effort_nm"), label=f"{name}.dynamic_effort_nm"),
            finite_number(
                item.get("viscous_coefficient_nm_s_per_rad"),
                label=f"{name}.viscous_coefficient_nm_s_per_rad",
            ),
        )
        if values != expected_profiles[name]:
            raise ValueError(f"{name} friction profile must remain exactly {expected_profiles[name]!r}")
        profiles[name] = {
            "static_effort_nm": values[0],
            "dynamic_effort_nm": values[1],
            "viscous_coefficient_nm_s_per_rad": values[2],
        }
    if tuple(profiles["F10"].values()) != (
        friction["static_effort_nm"],
        friction["dynamic_effort_nm"],
        friction["viscous_coefficient_nm_s_per_rad"],
    ):
        raise ValueError("F10 acceptance profile must match the frozen native probe profile")

    plateau = raw.get("plateau")
    control = raw.get("control")
    dissipation = raw.get("dissipation")
    chatter = raw.get("chatter")
    fine = raw.get("fine_dt")
    orthogonality = raw.get("orthogonality")
    for name, value in (
        ("plateau", plateau),
        ("control", control),
        ("dissipation", dissipation),
        ("chatter", chatter),
        ("fine_dt", fine),
        ("orthogonality", orthogonality),
    ):
        if not isinstance(value, Mapping):
            raise TypeError(f"v24_ai_acceptance.{name} must be a mapping")

    initial_angle = finite_number(plateau.get("initial_angle_rad"), label="plateau.initial_angle_rad")
    interior_margin = finite_number(plateau.get("interior_margin_rad"), label="plateau.interior_margin_rad")
    speeds_raw = plateau.get("speeds_rad_s")
    if not isinstance(speeds_raw, list) or tuple(float(value) for value in speeds_raw) != AI_SPEED_ORDER:
        raise ValueError("plateau.speeds_rad_s must remain exactly [-0.2, -0.1, 0.1, 0.2]")
    plateau_frames = plateau.get("frames")
    if plateau_frames != V23_STATIC_TRIAL_FRAMES:
        raise ValueError("plateau.frames must remain exactly 100")
    plateau_relative_spread_max = finite_number(
        plateau.get("relative_spread_max"), label="plateau.relative_spread_max"
    )
    plateau_direction_asymmetry_max = finite_number(
        plateau.get("direction_asymmetry_max"), label="plateau.direction_asymmetry_max"
    )
    if (interior_margin, plateau_relative_spread_max, plateau_direction_asymmetry_max) != (0.25, 0.25, 0.25):
        raise ValueError("plateau interior/acceptance limits must remain exactly 0.25/0.25/0.25")

    friction_ratio_low = finite_number(control.get("friction_ratio_low"), label="control.friction_ratio_low")
    friction_ratio_high = finite_number(control.get("friction_ratio_high"), label="control.friction_ratio_high")
    damping_ratio_min = finite_number(control.get("damping_ratio_min"), label="control.damping_ratio_min")
    if (friction_ratio_low, friction_ratio_high, damping_ratio_min) != (0.75, 1.25, 1.5):
        raise ValueError("control ratio bounds must remain exactly [0.75, 1.25] and >=1.5")

    dissipation_increment_max = finite_number(
        dissipation.get("max_positive_abs_speed_increment_rad_s"),
        label="dissipation.max_positive_abs_speed_increment_rad_s",
    )
    if dissipation_increment_max != 1.0e-4:
        raise ValueError("dissipation increment limit must remain exactly 1e-4 rad/s")

    chatter_threshold = finite_number(
        chatter.get("slip_velocity_threshold_rad_s"), label="chatter.slip_velocity_threshold_rad_s"
    )
    max_slip_reentries = chatter.get("max_slip_reentries")
    if chatter_threshold != friction["velocity_threshold_rad_s"] or max_slip_reentries != 1:
        raise ValueError("chatter threshold/re-entry bound must match the frozen 0.001 rad/s and <2 contract")

    fine_dt = finite_number(fine.get("dt_s"), label="fine_dt.dt_s")
    fine_frames = fine.get("frames")
    fine_duration = finite_number(fine.get("duration_s"), label="fine_dt.duration_s")
    if fine_dt != 0.0025 or fine_frames != 200 or fine_duration != 0.5:
        raise ValueError("fine dt contract must remain 0.0025 s × 200 frames = 0.5 s")
    if fine_dt * fine_frames != fine_duration:
        raise ValueError("fine dt duration does not equal the declared physical observation duration")

    realized_scaled_distance_max = finite_number(
        orthogonality.get("realized_scaled_distance_max"),
        label="orthogonality.realized_scaled_distance_max",
    )
    if realized_scaled_distance_max != 1.0e-4:
        raise ValueError("orthogonality realized scaled-distance limit must remain exactly 1e-4")

    raw_cells = raw.get("sparse_cells")
    if not isinstance(raw_cells, list) or tuple(item.get("id") for item in raw_cells if isinstance(item, Mapping)) != AI_SPARSE_CELL_ORDER:
        raise ValueError("sparse_cells must be ordered A0/A1/A4/A5/A8/F10")
    expected_cells = {
        "A0": (120.0, 50.0, 2.0),
        "A1": (120.0, 50.0, 30.0),
        "A4": (120.0, 200.0, 6.0),
        "A5": (160.0, 50.0, 6.0),
        "A8": (160.0, 200.0, 30.0),
        "F10": (120.0, 50.0, 6.0),
    }
    sparse_cells: list[dict[str, Any]] = []
    for item in raw_cells:
        if not isinstance(item, Mapping):
            raise TypeError("each sparse cell must be a mapping")
        cell_id = item.get("id")
        values = (
            finite_number(item.get("door_weight_kg"), label=f"{cell_id}.door_weight_kg"),
            finite_number(item.get("damping_native"), label=f"{cell_id}.damping_native"),
            finite_number(item.get("stiffness_native"), label=f"{cell_id}.stiffness_native"),
        )
        if values != expected_cells[cell_id]:
            raise ValueError(f"sparse cell {cell_id} must remain exactly {expected_cells[cell_id]!r}")
        sparse_cells.append(
            {
                "id": cell_id,
                "door_weight_kg": values[0],
                "damping_native": values[1],
                "stiffness_native": values[2],
            }
        )
    return {
        "enabled": True,
        "batch_id": batch_id,
        "device": device,
        "friction_profiles": profiles,
        "plateau": {
            "initial_angle_rad": initial_angle,
            "interior_margin_rad": interior_margin,
            "speeds_rad_s": list(AI_SPEED_ORDER),
            "frames": plateau_frames,
            "relative_spread_max": plateau_relative_spread_max,
            "direction_asymmetry_max": plateau_direction_asymmetry_max,
        },
        "control": {
            "friction_ratio_low": friction_ratio_low,
            "friction_ratio_high": friction_ratio_high,
            "damping_ratio_min": damping_ratio_min,
        },
        "dissipation": {"max_positive_abs_speed_increment_rad_s": dissipation_increment_max},
        "chatter": {
            "slip_velocity_threshold_rad_s": chatter_threshold,
            "max_slip_reentries": max_slip_reentries,
        },
        "fine_dt": {"dt_s": fine_dt, "frames": fine_frames, "duration_s": fine_duration},
        "orthogonality": {"realized_scaled_distance_max": realized_scaled_distance_max},
        "sparse_cells": sparse_cells,
        "surface_tags": dict(AI_SURFACE_TAGS),
        "parameter_range_freeze": "NOT_PERFORMED",
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


def build_ai_acceptance_plan(ai: Mapping[str, Any], friction: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "PLANNED_NOT_EXECUTED",
        "mode": AI_ACCEPTANCE_MODE,
        "batch_id": ai["batch_id"],
        "device": ai["device"],
        "overall_status": "PENDING_H_I",
        "provisional_allowed_typed_result": "V24_FRICTION_AUTHORITY_INSUFFICIENT",
        "H": "PENDING_PRODUCTION_RESET_RECEIPT",
        "I": "PENDING_P0_PARITY_RECEIPT",
        "scene_isolation": {
            "acceptance_ordinary_stage": True,
            "cleanup": "SimulationContext.stop -> clear -> clear_all_callbacks -> clear_instance",
        },
        "surface_tags": ai["surface_tags"],
        "orthogonality": ai["orthogonality"],
        "parameter_range_freeze": ai["parameter_range_freeze"],
        "grid": {
            "resolution_effort_nm": friction["resolution_effort_nm"],
            "ramp_start_effort_nm": friction["ramp_start_effort_nm"],
            "ramp_end_effort_nm": friction["ramp_end_effort_nm"],
            "trial_frames": V23_STATIC_TRIAL_FRAMES,
            "stop_at_first_breakaway": True,
            "containment_formula": "lower <= requested <= upper",
        },
        "A": {
            "friction_profiles": ai["friction_profiles"],
            "independent_trials": True,
            "literal_containment": True,
            "common_full_joint_state_captured_before_f00": True,
            "profile_start_joint_position": "common_captured_full_joint_position",
            "profile_start_joint_velocity": "full_zero_joint_velocity",
            "cleanup_restores_full_captured_joint_state": True,
            "upper_brackets_non_decreasing": True,
            "f10_upper_strictly_greater_than_f00": True,
        },
        "B": {
            "profile": "F10",
            "zero_stiffness_damping_viscous": True,
            "initial_angle_rad": ai["plateau"]["initial_angle_rad"],
            "interior_margin_rad": ai["plateau"]["interior_margin_rad"],
            "initial_speeds_rad_s": ai["plateau"]["speeds_rad_s"],
            "frames": ai["plateau"]["frames"],
            "dynamic_readback": ai["friction_profiles"]["F10"]["dynamic_effort_nm"],
            "endpoint_abs_speed_loss_rate_positive": True,
            "relative_spread_max": ai["plateau"]["relative_spread_max"],
            "direction_asymmetry_max": ai["plateau"]["direction_asymmetry_max"],
            "authority": "BEHAVIORAL_SEMANTIC_ONLY_NO_FRICTION_TORQUE",
        },
        "C": {
            "control_profile": "F00",
            "damping_native": 50.0,
            "stiffness_native": 0.0,
            "frames": ai["plateau"]["frames"],
            "friction_high_low_ratio": [
                ai["control"]["friction_ratio_low"],
                ai["control"]["friction_ratio_high"],
            ],
            "damping_high_low_ratio_min": ai["control"]["damping_ratio_min"],
            "both_directions_must_agree": True,
            "authority": "BEHAVIORAL_SEMANTIC_ONLY_NO_FRICTION_TORQUE",
        },
        "D": {
            "status": "AUTHORITY_INSUFFICIENT",
            "source": "UNAVAILABLE_NO_SOLVER_FRICTION_TORQUE_VIEW",
            "direct_criterion": "AUTHORITY_INSUFFICIENT",
            "runtime_guard_positive_abs_speed_increment_rad_s": ai["dissipation"]["max_positive_abs_speed_increment_rad_s"],
            "proxy_final_abs_speed_le_initial": True,
            "proxy_max_positive_abs_speed_increment_rad_s": ai["dissipation"]["max_positive_abs_speed_increment_rad_s"],
            "cannot_pass_literal": "tau_friction * omega",
        },
        "E": {
            "profile": "F10",
            "frames": V23_STATIC_TRIAL_FRAMES,
            "slip_threshold_rad_s": ai["chatter"]["slip_velocity_threshold_rad_s"],
            "max_slip_reentries": ai["chatter"]["max_slip_reentries"],
            "record_sign_reversals_separately": True,
            "sign_reversal_state": "abs(velocity_rad_s) >= slip_threshold_rad_s",
        },
        "F": {
            "profile": "F10",
            "dt_s": ai["fine_dt"]["dt_s"],
            "frames": ai["fine_dt"]["frames"],
            "duration_s": ai["fine_dt"]["duration_s"],
            "qualitative_only": True,
            "compare_raw_metrics": False,
            "requires_observed_base_and_fine_breakaway": True,
            "requires_observed_base_and_fine_e_classification": True,
        },
        "G": {
            "sparse_cells": ai["sparse_cells"],
            "friction_profile": "F10",
            "independent_trials": True,
            "trial_frames": V23_STATIC_TRIAL_FRAMES,
            "finite_state_and_readback_required": True,
            "realized_fixture_gate": {
                "body_lookup": "Articulation.find_bodies('door_panel', preserve_order=True)",
                "mass_readback": "ArticulationData.default_mass",
                "joint_readbacks": ["joint_damping", "joint_stiffness", "joint_effort_limits"],
                "unit_contract": "DoorMechanicsUnitContractV1",
                "requested_surface": "TRACE_CONFIG_RAD",
                "realized_surface": "USD_DEGREE_READBACK",
                "usd_degree_readback_used": True,
                "scaled_distance_max": ai["orthogonality"]["realized_scaled_distance_max"],
            },
            "unexpected_sign_reversal_or_chatter": "FAIL",
            "parameter_range_freeze": "NOT_PERFORMED",
            "surface_tags": ai["surface_tags"],
        },
    }


def build_d_v2_plan(config_path: Path = D_V2_CONFIG) -> dict[str, Any]:
    d_v2 = _d_v2_config_values(config_path)
    return {
        "schema": D_V2_PRODUCER_SCHEMA,
        "status": "PLAN_ONLY",
        "mode": ENERGY_MODE,
        "config": rel_path(d_v2["config_path"]),
        "device": d_v2["device"],
        "probe_seed": d_v2["probe_seed"],
        "runtime_artifact_root": rel_path(D_V2_ARTIFACT_ROOT),
        "required_runtime_outputs": {
            "tolerance": rel_path(D_V2_ARTIFACT_ROOT / "D_V2_TOLERANCE_FREEZE.json"),
            "receipt": rel_path(D_V2_ARTIFACT_ROOT / "D_V2_ENERGY_RECEIPT.json"),
            "caller_supplied": True,
            "no_overwrite": True,
        },
        "model": d_v2["model"],
        "spring_and_targets": d_v2["spring"],
        "trajectory": {
            **d_v2["trajectories"],
            "fresh_calibration_before_tolerance": True,
            "calibration_profile": "F00",
            "test_profile": "F10",
            "trajectory_order": ["F00/-1", "F00/+1", "WRITE_TOLERANCE_FREEZE", "F10/-1", "F10/+1"],
            "physics_order": "scene.write_data_to_sim -> sim.step -> scene.update",
            "accounting": {
                "work": "dW=tau_cmd*(theta_next-theta)",
                "mechanical_energy": "E=0.5*I_model*omega^2+0.5*k*(theta-theta_ref)^2",
                "dissipation": "dD=dW-(E_next-E); D starts at 0 and accumulates",
            },
        },
        "friction_profiles": d_v2["friction_profiles"],
        "tolerance": {
            **d_v2["tolerance"],
            "freeze_formula": "tol_step=2*noise_step+floor; tol_cum=2*noise_cumulative+floor",
            "source": "both fresh F00 calibration trajectories only",
            "f10_recompute_forbidden": True,
        },
        "f10_acceptance": {
            "finite": True,
            "readbacks_match": True,
            "motion_angle": "max(sign*(theta-theta0)) >= 1e-4 rad",
            "motion_velocity": "max(sign*omega) >= 1e-3 rad/s",
            "d_cumulative": "every D >= -tol_cum",
            "d_step": "every dD >= -tol_step",
            "final": "D_final > tol_cum",
            "overall": "both signs PASS",
        },
        "authority_labels": d_v2["authority_labels"],
    }


def build_plan(config_path: Path = PRODUCTION_CONFIG) -> dict[str, Any]:
    _assert_selected_sources(config_path)
    friction = _probe_config_values(config_path)
    ai = _ai_acceptance_config(config_path, friction)
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
        "a_i_acceptance": build_ai_acceptance_plan(ai, friction),
        "off_parity": build_off_parity_plan(config_path),
        "foot_force_detect": build_foot_force_detect_plan(),
    }


def _build_door_only_scene(
    *,
    device: str,
    dt: float,
    probe_seed: int,
    door_configs: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[Any, Any, Any, list[dict[str, Any]]]:
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
    if door_configs is None:
        source_configs = [dict(DOOR_FIXED_CONFIG)]
    else:
        source_configs = [dict(config) for config in door_configs]
    if not source_configs:
        raise ValueError("door_configs must contain at least the base environment configuration")
    if door_configs is not None:
        allowed_overrides = {
            "rand_door_weight",
            "rand_hinge_drive_damping",
            "rand_hinge_drive_stiffness",
        }
        for source_config in source_configs:
            if not set(source_config).issuperset(DOOR_FIXED_CONFIG):
                raise ValueError("each door config must provide the complete fixed source configuration")
            if not set(source_config).difference(DOOR_FIXED_CONFIG).issubset(allowed_overrides):
                raise ValueError("A-I sparse cells may override only mass, damping, and stiffness")
    source_assets = [base_asset.replace(**source_config) for source_config in source_configs]
    door_spawn = base_spawn.replace(
        assets_cfg=source_assets,
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

    sim = sim_utils.SimulationContext(
        sim_utils.SimulationCfg(
            dt=dt,
            device=device,
        )
    )
    scene = InteractiveScene(
        DoorFrictionSceneCfg(num_envs=len(source_configs), env_spacing=6.0, replicate_physics=False)
    )
    sim.reset()
    if set(scene.articulations) != {"door"}:
        raise RuntimeError(f"v24 torque ramp scene must contain only door articulation; got {scene.articulations.keys()!r}")
    if scene.sensors:
        raise RuntimeError("v24 torque ramp scene must not create contact or other sensors")
    door = scene["door"]
    fixtures = [_door_fixture_profile(probe_seed, source_config) for source_config in source_configs]
    return sim, scene, door, fixtures


def _single_env_ids(door: Any, *, selected_env_index: int, device: str) -> Any:
    import torch

    if isinstance(selected_env_index, bool) or not isinstance(selected_env_index, int) or selected_env_index < 0:
        raise ValueError("selected_env_index must be a non-negative integer")
    joint_pos = door.data.joint_pos
    if not torch.is_tensor(joint_pos) or joint_pos.ndim != 2:
        raise RuntimeError("door.data.joint_pos must be a (num_envs, joint) tensor")
    if selected_env_index >= joint_pos.shape[0]:
        raise IndexError(
            f"selected_env_index {selected_env_index} is outside the scene environment count {joint_pos.shape[0]}"
        )
    env_ids = torch.tensor([selected_env_index], dtype=torch.long, device=joint_pos.device)
    if env_ids.shape != (1,) or env_ids.device != joint_pos.device:
        raise RuntimeError("selected door environment index/device contract failed")
    return env_ids


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


def _read_g_fixture_gate(
    door: Any,
    door_fixture: Mapping[str, Any],
    *,
    device: str,
    selected_env_index: int,
    realized_scaled_distance_max: float,
) -> dict[str, Any]:
    """Read and compare the realized sparse-cell fixture through public data tensors."""

    import torch

    hinge_id, hinge_name = _select_single_hinge(door)
    body_ids, body_names = door.find_bodies("door_panel", preserve_order=True)
    if len(body_ids) != 1 or list(body_names) != ["door_panel"]:
        raise RuntimeError(
            "G fixture gate requires exactly one public door_panel body; "
            f"got ids={body_ids!r}, names={body_names!r}"
        )
    body_id = int(body_ids[0])
    env_ids = _single_env_ids(door, selected_env_index=selected_env_index, device=device)
    default_mass = getattr(door.data, "default_mass", None)
    if (
        not torch.is_tensor(default_mass)
        or default_mass.ndim != 2
        or default_mass.shape[0] < env_ids.numel()
        or default_mass.shape[1] <= body_id
    ):
        raise RuntimeError("G fixture gate requires ArticulationData.default_mass with body columns")
    mass_value = default_mass[selected_env_index, body_id].reshape(1)
    if mass_value.shape != (1,) or not bool(torch.isfinite(mass_value).all().item()):
        raise RuntimeError("G fixture gate received a nonfinite door_panel mass readback")
    damping_value = _selected_hinge_field(door, "joint_damping", env_ids, hinge_id)
    stiffness_value = _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id)
    effort_limit_value = _selected_hinge_field(door, "joint_effort_limits", env_ids, hinge_id)
    if not bool(torch.isfinite(damping_value).all().item()) or not bool(torch.isfinite(stiffness_value).all().item()):
        raise RuntimeError("G fixture gate received a nonfinite hinge damping/stiffness readback")
    if not bool(torch.isfinite(effort_limit_value).all().item()):
        raise RuntimeError("G fixture gate received a nonfinite hinge effort-limit readback")

    requested = {
        "door_weight_kg": door_fixture["mass_inertia_inputs"]["door_panel_mass_kg"],
        "hinge_damping_native": door_fixture["dynamics"]["hinge_drive_damping_native"],
        "hinge_stiffness_native": door_fixture["dynamics"]["hinge_drive_stiffness_native"],
        "hinge_effort_limit_nm": door_fixture["dynamics"]["hinge_drive_max_force_nm"],
    }
    realized = {
        "door_weight_kg": float(mass_value[0].item()),
        "hinge_damping_native": float(damping_value[0, 0].item()),
        "hinge_stiffness_native": float(stiffness_value[0, 0].item()),
        "hinge_effort_limit_nm": float(effort_limit_value[0, 0].item()),
    }
    requested_normalized = normalize_realized_dynamics(
        requested,
        angular_surface=TRACE_CONFIG_SURFACE,
        authority_prefix="TRACE_CONFIG",
    )
    realized_normalized = normalize_realized_dynamics(
        realized,
        angular_surface=USD_DEGREE_SURFACE,
        authority_prefix="ARTICULATION_DATA_HIGH_LEVEL",
    )
    field_values = {
        "door_mass_kg": {
            "requested": requested_normalized["door_mass_kg"],
            "realized": realized_normalized["door_mass_kg"],
        },
        "damping_rad": {
            "requested": requested_normalized["damping_rad"],
            "realized": realized_normalized["damping_rad"],
        },
        "stiffness_rad": {
            "requested": requested_normalized["stiffness_rad"],
            "realized": realized_normalized["stiffness_rad"],
        },
        "effort_limit_nm": {
            "requested": requested_normalized["effort_limit_nm"],
            "realized": realized_normalized["effort_limit_nm"],
        },
    }
    realized_scaled_distance = scaled_distance(realized_normalized, requested_normalized)
    if not math.isfinite(realized_scaled_distance):
        raise RuntimeError("G fixture gate produced a nonfinite realized scaled distance")
    scaled_distance_passed = realized_scaled_distance <= realized_scaled_distance_max
    return {
        "status": "PASS" if scaled_distance_passed else "FAIL_REALIZED_FIXTURE_SCALED_DISTANCE",
        "passed": scaled_distance_passed,
        "hinge_joint_name": hinge_name,
        "hinge_joint_id": hinge_id,
        "door_panel_body_name": body_names[0],
        "door_panel_body_id": body_id,
        "unit_contract": "DoorMechanicsUnitContractV1",
        "requested_angular_surface": TRACE_CONFIG_SURFACE,
        "realized_angular_surface": USD_DEGREE_SURFACE,
        "usd_degree_readback_used": True,
        "conversion_metadata": realized_normalized["fields"],
        "field_values_descriptive": field_values,
        "realized_scaled_distance": realized_scaled_distance,
        "realized_scaled_distance_max": realized_scaled_distance_max,
        "scaled_distance_passed": scaled_distance_passed,
        "requested_normalized": requested_normalized,
        "realized_normalized": realized_normalized,
        "authority": "PUBLIC_ARTICULATION_DATA_HIGH_LEVEL",
    }


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
    record_raw_traces: bool = False,
    trial_frame_authority: str = "V23_EXTERNAL_TORQUE_PROBE_100_FRAME_TRIAL",
    neutralize_damping_stiffness: bool = True,
    trial_baseline_position: Any | None = None,
    trial_baseline_velocity: Any | None = None,
    selected_env_index: int = 0,
) -> dict[str, Any]:
    """Run independent static-friction trials in the door-only scene."""

    import torch

    from gr00t.rl.envs.door.a2_v24_friction import A2V24DoorFrictionBackend, V24FrictionConfig

    door = scene["door"]
    hinge_id, hinge_name = _select_single_hinge(door)
    env_ids = _single_env_ids(door, selected_env_index=selected_env_index, device=device)

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
    captured_baseline_position = door.data.joint_pos[env_ids].clone()
    captured_baseline_velocity = door.data.joint_vel[env_ids].clone()
    if trial_baseline_position is None:
        baseline_joint_position = captured_baseline_position.clone()
    else:
        if (
            not torch.is_tensor(trial_baseline_position)
            or trial_baseline_position.shape != captured_baseline_position.shape
            or trial_baseline_position.device != captured_baseline_position.device
            or trial_baseline_position.dtype != captured_baseline_position.dtype
        ):
            raise TypeError("trial_baseline_position must match the full door joint-position tensor")
        baseline_joint_position = trial_baseline_position.clone()
    if trial_baseline_velocity is None:
        baseline_joint_velocity = torch.zeros_like(captured_baseline_velocity)
    else:
        if (
            not torch.is_tensor(trial_baseline_velocity)
            or trial_baseline_velocity.shape != captured_baseline_velocity.shape
            or trial_baseline_velocity.device != captured_baseline_velocity.device
            or trial_baseline_velocity.dtype != captured_baseline_velocity.dtype
        ):
            raise TypeError("trial_baseline_velocity must match the full door joint-velocity tensor")
        baseline_joint_velocity = trial_baseline_velocity.clone()
    if not bool(torch.isfinite(baseline_joint_position).all().item()) or not bool(torch.isfinite(baseline_joint_velocity).all().item()):
        raise RuntimeError("trial baseline joint state is nonfinite")
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
        if neutralize_damping_stiffness:
            door.write_joint_damping_to_sim(torch.zeros_like(original_damping), joint_ids=[hinge_id], env_ids=env_ids)
            door.write_joint_stiffness_to_sim(torch.zeros_like(original_stiffness), joint_ids=[hinge_id], env_ids=env_ids)
            neutral_damping = _selected_hinge_field(door, "joint_damping", env_ids, hinge_id)
            neutral_stiffness = _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id)
            if not bool(torch.all(neutral_damping == 0.0).item()) or not bool(torch.all(neutral_stiffness == 0.0).item()):
                raise RuntimeError("damping/stiffness neutralization readback failed")
        else:
            neutral_damping = original_damping.clone()
            neutral_stiffness = original_stiffness.clone()

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
            if not math.isfinite(trial_start_angle) or not math.isfinite(trial_start_velocity):
                raise RuntimeError("independent trial reset produced a nonfinite hinge state")
            if abs(trial_start_velocity) > friction["stationarity_velocity_tolerance_rad_s"]:
                raise RuntimeError(
                    "independent trial reset did not reach the stationarity velocity tolerance: "
                    f"command={command}, velocity={trial_start_velocity}"
                )
            command_tensor = torch.full(
                (env_ids.numel(), 1), command, dtype=door.data.joint_pos.dtype, device=door.data.joint_pos.device
            )
            door.set_joint_effort_target(command_tensor, joint_ids=[hinge_id], env_ids=env_ids)
            angle_trace: list[float] = []
            velocity_trace: list[float] = []
            for _ in range(friction["hold_window_steps"]):
                _step_door_scene(sim, scene, dt)
                angle = float(door.data.joint_pos[env_ids, hinge_id].item())
                velocity = float(door.data.joint_vel[env_ids, hinge_id].item())
                if not math.isfinite(angle) or not math.isfinite(velocity):
                    raise RuntimeError("static-friction trial produced a nonfinite hinge state")
                if record_raw_traces:
                    angle_trace.append(angle)
                    velocity_trace.append(velocity)
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
            if record_raw_traces:
                rows[-1]["angle_trace_rad"] = angle_trace
                rows[-1]["velocity_trace_rad_s"] = velocity_trace
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
            door.write_joint_state_to_sim(
                captured_baseline_position,
                captured_baseline_velocity,
                env_ids=env_ids,
            )
            scene.write_data_to_sim()
            final_targets = door.data.joint_effort_target[env_ids].clone()
            final_joint_position = door.data.joint_pos[env_ids].clone()
            final_joint_velocity = door.data.joint_vel[env_ids].clone()
            if not bool(torch.all(final_targets[:, hinge_id] == 0.0).item()):
                raise RuntimeError("hinge effort target cleanup readback failed")
            if not bool(torch.allclose(final_joint_position, captured_baseline_position, atol=1.0e-6, rtol=0.0)):
                raise RuntimeError("full joint-position cleanup readback failed")
            if not bool(torch.allclose(final_joint_velocity, captured_baseline_velocity, atol=1.0e-6, rtol=0.0)):
                raise RuntimeError("full joint-velocity cleanup readback failed")
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
            "trial_frame_authority": trial_frame_authority,
            "baseline_joint_position": baseline_joint_position.detach().cpu().tolist(),
            "captured_baseline_position": captured_baseline_position.detach().cpu().tolist(),
            "captured_baseline_velocity": captured_baseline_velocity.detach().cpu().tolist(),
            "baseline_joint_velocity_written": baseline_joint_velocity.detach().cpu().tolist(),
            "common_profile_baseline_supplied": trial_baseline_position is not None,
            "stationarity_velocity_tolerance_rad_s": friction["stationarity_velocity_tolerance_rad_s"],
            "containment_formula": "lower <= requested <= upper",
            "stop_at_first_breakaway": True,
            "command_effort_authority": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
        },
        "neutralization": {
            "damping_recorded": original_damping.detach().cpu().tolist(),
            "stiffness_recorded": original_stiffness.detach().cpu().tolist(),
            "hinge_damping_neutralized": neutralize_damping_stiffness,
            "hinge_stiffness_neutralized": neutralize_damping_stiffness,
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
                "hold_window_authority": trial_frame_authority,
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
            "restored_full_joint_state": True,
            "restored_joint_position": final_joint_position.detach().cpu().tolist(),
            "restored_joint_velocity": final_joint_velocity.detach().cpu().tolist(),
            "restored_joint_state_atol": 1.0e-6,
            "restored_joint_state_rtol": 0.0,
        },
        "timing": {
            "physics_order": "scene.write_data_to_sim -> sim.step -> scene.update",
            "ramp_interval_count": friction["ramp_interval_count"],
            "grid_spacing_nm": actual_spacing,
            "dt_s": friction["dt_s"],
            "hold_window_steps": friction["hold_window_steps"],
            "trial_frame_authority": trial_frame_authority,
            "independent_reset_per_command": True,
            "executed_command_count": len(rows),
            "stopped_at_first_breakaway": breakaway_index is not None,
            "settle_steps_preregistered": friction["settle_steps"],
        },
    }


def _d_v2_energy(theta: float, omega: float, *, inertia: float, stiffness: float, theta_ref: float) -> float:
    value = 0.5 * inertia * omega**2 + 0.5 * stiffness * (theta - theta_ref) ** 2
    if not math.isfinite(value):
        raise RuntimeError("D-v2 mechanical energy became nonfinite")
    return value


def _d_v2_configure_profile(
    *,
    door: Any,
    scene: Any,
    env_ids: Any,
    hinge_id: int,
    d_v2: Mapping[str, Any],
    profile_name: str,
    original: Mapping[str, Any],
) -> dict[str, Any]:
    import torch

    profile = d_v2["friction_profiles"][profile_name]
    door.write_joint_friction_coefficient_to_sim(
        torch.full_like(original["joint_friction_coeff"], profile["static_effort_nm"]),
        torch.full_like(original["joint_dynamic_friction_coeff"], profile["dynamic_effort_nm"]),
        torch.full_like(original["joint_viscous_friction_coeff"], profile["viscous_coefficient_nm_s_per_rad"]),
        joint_ids=[hinge_id],
        env_ids=env_ids,
    )
    door.write_joint_stiffness_to_sim(
        torch.full_like(original["joint_stiffness"], d_v2["spring"]["stiffness_nm_per_rad"]),
        joint_ids=[hinge_id],
        env_ids=env_ids,
    )
    door.write_joint_damping_to_sim(
        torch.full_like(original["joint_damping"], d_v2["spring"]["damping_nm_s_per_rad"]),
        joint_ids=[hinge_id],
        env_ids=env_ids,
    )
    target_position = torch.full_like(
        original["joint_pos_target"][:, [hinge_id]], d_v2["spring"]["theta_ref_rad"]
    )
    target_velocity = torch.full_like(
        original["joint_vel_target"][:, [hinge_id]], d_v2["spring"]["velocity_target_rad_s"]
    )
    target_effort = torch.zeros_like(original["joint_effort_target"][:, [hinge_id]])
    door.set_joint_position_target(target_position, joint_ids=[hinge_id], env_ids=env_ids)
    door.set_joint_velocity_target(target_velocity, joint_ids=[hinge_id], env_ids=env_ids)
    door.set_joint_effort_target(target_effort, joint_ids=[hinge_id], env_ids=env_ids)
    scene.write_data_to_sim()

    readback = {
        "profile": {
            "static_effort_nm": _selected_hinge_field(door, "joint_friction_coeff", env_ids, hinge_id),
            "dynamic_effort_nm": _selected_hinge_field(door, "joint_dynamic_friction_coeff", env_ids, hinge_id),
            "viscous_coefficient_nm_s_per_rad": _selected_hinge_field(
                door, "joint_viscous_friction_coeff", env_ids, hinge_id
            ),
        },
        "stiffness_nm_per_rad": _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id),
        "damping_nm_s_per_rad": _selected_hinge_field(door, "joint_damping", env_ids, hinge_id),
        "theta_ref_rad": _selected_hinge_field(door, "joint_pos_target", env_ids, hinge_id),
        "velocity_target_rad_s": _selected_hinge_field(door, "joint_vel_target", env_ids, hinge_id),
    }
    expected = {
        "profile": {
            "static_effort_nm": profile["static_effort_nm"],
            "dynamic_effort_nm": profile["dynamic_effort_nm"],
            "viscous_coefficient_nm_s_per_rad": profile["viscous_coefficient_nm_s_per_rad"],
        },
        "stiffness_nm_per_rad": d_v2["spring"]["stiffness_nm_per_rad"],
        "damping_nm_s_per_rad": d_v2["spring"]["damping_nm_s_per_rad"],
        "theta_ref_rad": d_v2["spring"]["theta_ref_rad"],
        "velocity_target_rad_s": d_v2["spring"]["velocity_target_rad_s"],
    }
    matches = {
        "static_effort_nm": bool(torch.all(readback["profile"]["static_effort_nm"] == expected["profile"]["static_effort_nm"]).item()),
        "dynamic_effort_nm": bool(torch.all(readback["profile"]["dynamic_effort_nm"] == expected["profile"]["dynamic_effort_nm"]).item()),
        "viscous_coefficient_nm_s_per_rad": bool(
            torch.all(readback["profile"]["viscous_coefficient_nm_s_per_rad"] == expected["profile"]["viscous_coefficient_nm_s_per_rad"]).item()
        ),
        "stiffness_nm_per_rad": bool(torch.all(readback["stiffness_nm_per_rad"] == expected["stiffness_nm_per_rad"]).item()),
        "damping_nm_s_per_rad": bool(torch.all(readback["damping_nm_s_per_rad"] == expected["damping_nm_s_per_rad"]).item()),
        "theta_ref_rad": bool(torch.all(readback["theta_ref_rad"] == expected["theta_ref_rad"]).item()),
        "velocity_target_rad_s": bool(torch.all(readback["velocity_target_rad_s"] == expected["velocity_target_rad_s"]).item()),
    }
    if not all(matches.values()):
        raise RuntimeError(f"D-v2 configured high-level readback mismatch: {matches!r}")
    return {
        "profile_name": profile_name,
        "requested": expected,
        "readback": {
            "static_effort_nm": readback["profile"]["static_effort_nm"].detach().cpu().tolist(),
            "dynamic_effort_nm": readback["profile"]["dynamic_effort_nm"].detach().cpu().tolist(),
            "viscous_coefficient_nm_s_per_rad": readback["profile"]["viscous_coefficient_nm_s_per_rad"].detach().cpu().tolist(),
            "stiffness_nm_per_rad": readback["stiffness_nm_per_rad"].detach().cpu().tolist(),
            "damping_nm_s_per_rad": readback["damping_nm_s_per_rad"].detach().cpu().tolist(),
            "theta_ref_rad": readback["theta_ref_rad"].detach().cpu().tolist(),
            "velocity_target_rad_s": readback["velocity_target_rad_s"].detach().cpu().tolist(),
        },
        "matches": matches,
        "authority": d_v2["authority_labels"],
    }


def _d_v2_run_trajectory(
    *,
    sim: Any,
    scene: Any,
    door: Any,
    env_ids: Any,
    hinge_id: int,
    d_v2: Mapping[str, Any],
    profile_name: str,
    sign: int,
    original: Mapping[str, Any],
) -> dict[str, Any]:
    import torch

    profile_readback = _d_v2_configure_profile(
        door=door,
        scene=scene,
        env_ids=env_ids,
        hinge_id=hinge_id,
        d_v2=d_v2,
        profile_name=profile_name,
        original=original,
    )
    theta_ref = d_v2["spring"]["theta_ref_rad"]
    theta_initial = d_v2["spring"]["theta_initial_rad"]
    velocity_target = d_v2["spring"]["velocity_target_rad_s"]
    _clear_hinge_target(door, hinge_id, env_ids)
    stationarity_rows: list[dict[str, float]] = []
    for stationarity_index in range(d_v2["trajectories"]["stationarity_steps"]):
        _step_door_scene(sim, scene, d_v2["trajectories"]["dt_s"])
        theta = float(door.data.joint_pos[env_ids, hinge_id].item())
        omega = float(door.data.joint_vel[env_ids, hinge_id].item())
        if not math.isfinite(theta) or not math.isfinite(omega):
            raise RuntimeError("D-v2 zero-command stationarity state became nonfinite")
        stationarity_rows.append({"step": stationarity_index, "theta_rad": theta, "omega_rad_s": omega})

    exact_position = torch.full_like(_selected_hinge_field(door, "joint_pos", env_ids, hinge_id), theta_initial)
    exact_velocity = torch.full_like(_selected_hinge_field(door, "joint_vel", env_ids, hinge_id), velocity_target)
    door.write_joint_state_to_sim(exact_position, exact_velocity, joint_ids=[hinge_id], env_ids=env_ids)
    theta_before_rewrite = float(door.data.joint_pos[env_ids, hinge_id].item())
    omega_before_rewrite = float(door.data.joint_vel[env_ids, hinge_id].item())
    if theta_before_rewrite != theta_initial or omega_before_rewrite != velocity_target:
        raise RuntimeError("D-v2 exact initial-state rewrite readback mismatch")

    inertia = d_v2["model"]["inertia_kg_m2"]
    stiffness = d_v2["spring"]["stiffness_nm_per_rad"]
    cumulative_dissipation = 0.0
    rows: list[dict[str, Any]] = []
    phases = (
        ("command", d_v2["trajectories"]["command_steps"], sign * d_v2["trajectories"]["command_effort_nm"]),
        ("coast", d_v2["trajectories"]["coast_steps"], 0.0),
    )
    for phase, phase_steps, command_effort in phases:
        command_tensor = torch.full(
            (env_ids.numel(), 1), command_effort, dtype=door.data.joint_pos.dtype, device=door.data.joint_pos.device
        )
        door.set_joint_effort_target(command_tensor, joint_ids=[hinge_id], env_ids=env_ids)
        for phase_step in range(phase_steps):
            theta = float(door.data.joint_pos[env_ids, hinge_id].item())
            omega = float(door.data.joint_vel[env_ids, hinge_id].item())
            energy = _d_v2_energy(theta, omega, inertia=inertia, stiffness=stiffness, theta_ref=theta_ref)
            _step_door_scene(sim, scene, d_v2["trajectories"]["dt_s"])
            theta_next = float(door.data.joint_pos[env_ids, hinge_id].item())
            omega_next = float(door.data.joint_vel[env_ids, hinge_id].item())
            if not all(math.isfinite(value) for value in (theta, omega, theta_next, omega_next)):
                raise RuntimeError("D-v2 energy trajectory state became nonfinite")
            energy_next = _d_v2_energy(
                theta_next, omega_next, inertia=inertia, stiffness=stiffness, theta_ref=theta_ref
            )
            work = command_effort * (theta_next - theta)
            delta_energy = energy_next - energy
            delta_dissipation = work - delta_energy
            cumulative_dissipation += delta_dissipation
            if not all(math.isfinite(value) for value in (work, delta_energy, delta_dissipation, cumulative_dissipation)):
                raise RuntimeError("D-v2 energy accounting became nonfinite")
            rows.append(
                {
                    "step": len(rows),
                    "phase": phase,
                    "phase_step": phase_step,
                    "tau_cmd_nm": command_effort,
                    "theta_rad": theta,
                    "omega_rad_s": omega,
                    "theta_next_rad": theta_next,
                    "omega_next_rad_s": omega_next,
                    "E_j": energy,
                    "E_next_j": energy_next,
                    "dW_j": work,
                    "delta_E_j": delta_energy,
                    "dD_j": delta_dissipation,
                    "D_j": cumulative_dissipation,
                }
            )

    max_signed_angle = max(sign * (row["theta_next_rad"] - theta_initial) for row in rows)
    max_signed_velocity = max(sign * row["omega_next_rad_s"] for row in rows)
    noise_step = max(abs(row["dD_j"]) for row in rows)
    noise_cumulative = max(abs(row["D_j"]) for row in rows)
    return {
        "profile": profile_name,
        "sign": sign,
        "stationarity": {
            "steps": len(stationarity_rows),
            "rows": stationarity_rows,
            "theta_initial_rad": theta_initial,
            "omega_initial_rad_s": velocity_target,
        },
        "exact_state_rewrite": {
            "theta_initial_rad": theta_initial,
            "omega_initial_rad_s": velocity_target,
            "readback_theta_rad": theta_before_rewrite,
            "readback_omega_rad_s": omega_before_rewrite,
            "matches": theta_before_rewrite == theta_initial and omega_before_rewrite == velocity_target,
        },
        "readbacks": profile_readback,
        "rows": rows,
        "noise_step_j": noise_step,
        "noise_cumulative_j": noise_cumulative,
        "D_final_j": cumulative_dissipation,
        "motion": {
            "theta0_rad": theta_initial,
            "max_signed_angle_rad": max_signed_angle,
            "max_signed_velocity_rad_s": max_signed_velocity,
        },
        "finite": True,
    }


def _d_v2_tolerance_freeze(d_v2: Mapping[str, Any], calibration: Sequence[Mapping[str, Any]], tolerance_path: Path) -> dict[str, Any]:
    noise_step = max(float(item["noise_step_j"]) for item in calibration)
    noise_cumulative = max(float(item["noise_cumulative_j"]) for item in calibration)
    multiplier = d_v2["tolerance"]["multiplier"]
    floor_j = d_v2["tolerance"]["floor_j"]
    tol_step = multiplier * noise_step + floor_j
    tol_cumulative = multiplier * noise_cumulative + floor_j
    if not all(math.isfinite(value) for value in (noise_step, noise_cumulative, tol_step, tol_cumulative)):
        raise RuntimeError("D-v2 tolerance calibration became nonfinite")
    return {
        "schema": D_V2_TOLERANCE_SCHEMA,
        "mode": ENERGY_MODE,
        "status": "FROZEN",
        "device": d_v2["device"],
        "probe_seed": d_v2["probe_seed"],
        "profile": "F00",
        "trajectory_signs": list(d_v2["trajectories"]["signs"]),
        "calibration_trajectory_count": len(calibration),
        "calibration_trajectories": list(calibration),
        "noise_step_j": noise_step,
        "noise_cumulative_j": noise_cumulative,
        "multiplier": multiplier,
        "floor_j": floor_j,
        "tol_step_j": tol_step,
        "tol_cumulative_j": tol_cumulative,
        "freeze_formula": "tol_step=2*noise_step+floor; tol_cum=2*noise_cumulative+floor",
        "source": "both fresh F00 calibration trajectories only",
        "f10_recompute_forbidden": True,
        "tolerance_path": rel_path(tolerance_path),
    }


def _d_v2_cleanup(
    *,
    scene: Any,
    door: Any,
    env_ids: Any,
    hinge_id: int,
    original: Mapping[str, Any],
) -> dict[str, Any]:
    import torch

    friction_cleanup = _restore_friction(
        door,
        env_ids,
        hinge_id,
        {
            "joint_friction_coeff": original["joint_friction_coeff"],
            "joint_dynamic_friction_coeff": original["joint_dynamic_friction_coeff"],
            "joint_viscous_friction_coeff": original["joint_viscous_friction_coeff"],
        },
    )
    door.set_joint_effort_target(original["joint_effort_target"], env_ids=env_ids)
    door.set_joint_position_target(original["joint_pos_target"], env_ids=env_ids)
    door.set_joint_velocity_target(original["joint_vel_target"], env_ids=env_ids)
    door.write_joint_stiffness_to_sim(original["joint_stiffness"], joint_ids=[hinge_id], env_ids=env_ids)
    door.write_joint_damping_to_sim(original["joint_damping"], joint_ids=[hinge_id], env_ids=env_ids)
    door.write_joint_effort_limit_to_sim(original["joint_effort_limits"], joint_ids=[hinge_id], env_ids=env_ids)
    door.write_joint_state_to_sim(original["joint_pos"], original["joint_vel"], env_ids=env_ids)
    scene.write_data_to_sim()
    restored = {
        "joint_pos": door.data.joint_pos[env_ids].clone(),
        "joint_vel": door.data.joint_vel[env_ids].clone(),
        "joint_effort_target": door.data.joint_effort_target[env_ids].clone(),
        "joint_pos_target": door.data.joint_pos_target[env_ids].clone(),
        "joint_vel_target": door.data.joint_vel_target[env_ids].clone(),
        "joint_stiffness": _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id),
        "joint_damping": _selected_hinge_field(door, "joint_damping", env_ids, hinge_id),
        "joint_effort_limits": _selected_hinge_field(door, "joint_effort_limits", env_ids, hinge_id),
        "joint_friction_coeff": _selected_hinge_field(door, "joint_friction_coeff", env_ids, hinge_id),
        "joint_dynamic_friction_coeff": _selected_hinge_field(
            door, "joint_dynamic_friction_coeff", env_ids, hinge_id
        ),
        "joint_viscous_friction_coeff": _selected_hinge_field(
            door, "joint_viscous_friction_coeff", env_ids, hinge_id
        ),
    }
    matches = {
        "joint_pos": bool(torch.allclose(restored["joint_pos"], original["joint_pos"], atol=1.0e-6, rtol=0.0)),
        "joint_vel": bool(torch.allclose(restored["joint_vel"], original["joint_vel"], atol=1.0e-6, rtol=0.0)),
        "joint_effort_target": bool(torch.equal(restored["joint_effort_target"], original["joint_effort_target"])),
        "joint_pos_target": bool(torch.equal(restored["joint_pos_target"], original["joint_pos_target"])),
        "joint_vel_target": bool(torch.equal(restored["joint_vel_target"], original["joint_vel_target"])),
        "joint_stiffness": bool(torch.allclose(restored["joint_stiffness"], original["joint_stiffness"], atol=1.0e-6, rtol=0.0)),
        "joint_damping": bool(torch.allclose(restored["joint_damping"], original["joint_damping"], atol=1.0e-6, rtol=0.0)),
        "joint_effort_limits": bool(
            torch.allclose(restored["joint_effort_limits"], original["joint_effort_limits"], atol=1.0e-6, rtol=0.0)
        ),
        "joint_friction_coeff": friction_cleanup["matches"]["joint_friction_coeff"],
        "joint_dynamic_friction_coeff": friction_cleanup["matches"]["joint_dynamic_friction_coeff"],
        "joint_viscous_friction_coeff": friction_cleanup["matches"]["joint_viscous_friction_coeff"],
    }
    if not all(matches.values()):
        raise RuntimeError(f"D-v2 cleanup readback mismatch: {matches!r}")
    return {"matches": matches, "friction": friction_cleanup, "authority": "HIGH_LEVEL_ARTICULATION_DATA"}


def _raise_d_v2_lifecycle_errors(errors: Sequence[BaseException]) -> None:
    if not errors:
        return
    if len(errors) == 1:
        raise errors[0]
    raise BaseExceptionGroup("D-v2 lifecycle failures", list(errors))


def _run_d_v2_runtime(config_path: Path, *, device: str, tolerance_path: Path, output: Path) -> None:
    d_v2 = _d_v2_config_values(config_path)
    if device != d_v2["device"]:
        raise ValueError("D_V2_ENERGY requires the configured device cuda:0")
    tolerance_path = absolute(tolerance_path).resolve()
    output = absolute(output).resolve()
    if tolerance_path.parent != D_V2_ARTIFACT_ROOT.resolve() or tolerance_path.name != "D_V2_TOLERANCE_FREEZE.json":
        raise ValueError("D-v2 tolerance output must be the canonical D_V2_TOLERANCE_FREEZE.json path")
    if output.parent != D_V2_ARTIFACT_ROOT.resolve() or output.name != "D_V2_ENERGY_RECEIPT.json":
        raise ValueError("D-v2 receipt output must be the canonical D_V2_ENERGY_RECEIPT.json path")
    if tolerance_path.exists() or output.exists():
        raise ValueError("D-v2 runtime refuses to overwrite an existing artifact")

    sim = None
    scene = None
    door = None
    env_ids = None
    hinge_id = None
    hinge_name = None
    original = None
    cleanup_ready = False
    primary_error: BaseException | None = None
    teardown_errors: list[BaseException] = []
    receipt_payload: dict[str, Any] | None = None
    cleanup_result: dict[str, Any] | None = None
    try:
        sim, scene, door, fixtures = _build_door_only_scene(
            device=device,
            dt=d_v2["trajectories"]["dt_s"],
            probe_seed=d_v2["probe_seed"],
        )
        if len(fixtures) != 1:
            raise RuntimeError("D-v2 requires exactly one door-only fixture")
        env_ids = _single_env_ids(door, selected_env_index=0, device=device)
        hinge_id, hinge_name = _select_single_hinge(door)
        original = {
            "joint_friction_coeff": _selected_hinge_field(door, "joint_friction_coeff", env_ids, hinge_id),
            "joint_dynamic_friction_coeff": _selected_hinge_field(door, "joint_dynamic_friction_coeff", env_ids, hinge_id),
            "joint_viscous_friction_coeff": _selected_hinge_field(door, "joint_viscous_friction_coeff", env_ids, hinge_id),
            "joint_stiffness": _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id),
            "joint_damping": _selected_hinge_field(door, "joint_damping", env_ids, hinge_id),
            "joint_effort_limits": _selected_hinge_field(door, "joint_effort_limits", env_ids, hinge_id),
            "joint_pos_target": door.data.joint_pos_target[env_ids].clone(),
            "joint_vel_target": door.data.joint_vel_target[env_ids].clone(),
            "joint_effort_target": door.data.joint_effort_target[env_ids].clone(),
            "joint_pos": door.data.joint_pos[env_ids].clone(),
            "joint_vel": door.data.joint_vel[env_ids].clone(),
        }
        cleanup_ready = True
        calibration = [
            _d_v2_run_trajectory(
                sim=sim,
                scene=scene,
                door=door,
                env_ids=env_ids,
                hinge_id=hinge_id,
                d_v2=d_v2,
                profile_name="F00",
                sign=sign,
                original=original,
            )
            for sign in d_v2["trajectories"]["signs"]
        ]
        tolerance = _d_v2_tolerance_freeze(d_v2, calibration, tolerance_path)
        write_json(tolerance_path, tolerance)
        f10_trajectories = [
            _d_v2_run_trajectory(
                sim=sim,
                scene=scene,
                door=door,
                env_ids=env_ids,
                hinge_id=hinge_id,
                d_v2=d_v2,
                profile_name="F10",
                sign=sign,
                original=original,
            )
            for sign in d_v2["trajectories"]["signs"]
        ]
        f10_results: list[dict[str, Any]] = []
        for trajectory in f10_trajectories:
            finite = bool(trajectory["finite"])
            readbacks_match = all(trajectory["readbacks"]["matches"].values())
            motion_angle = trajectory["motion"]["max_signed_angle_rad"] >= 1.0e-4
            motion_velocity = trajectory["motion"]["max_signed_velocity_rad_s"] >= 1.0e-3
            d_cumulative = all(row["D_j"] >= -tolerance["tol_cumulative_j"] for row in trajectory["rows"])
            d_step = all(row["dD_j"] >= -tolerance["tol_step_j"] for row in trajectory["rows"])
            final = trajectory["D_final_j"] > tolerance["tol_cumulative_j"]
            checks = {
                "finite": finite,
                "readbacks_match": readbacks_match,
                "motion_angle": motion_angle,
                "motion_velocity": motion_velocity,
                "D_nonnegative_within_tol": d_cumulative,
                "dD_nonnegative_within_tol": d_step,
                "D_final_above_tol": final,
            }
            f10_results.append(
                {
                    "sign": trajectory["sign"],
                    "checks": checks,
                    "scientific_verdict": "PASS" if all(checks.values()) else "FAIL",
                    "trajectory": trajectory,
                }
            )
        overall_pass = all(result["scientific_verdict"] == "PASS" for result in f10_results)
        receipt_payload = {
            "schema": D_V2_PRODUCER_SCHEMA,
            "mode": ENERGY_MODE,
            "status": "PASS" if overall_pass else "FAIL",
            "overall_status": "PASS" if overall_pass else "FAIL",
            "device": d_v2["device"],
            "probe_seed": d_v2["probe_seed"],
            "config": rel_path(d_v2["config_path"]),
            "door_only": True,
            "hinge_joint_name": hinge_name,
            "hinge_joint_id": hinge_id,
            "model": d_v2["model"],
            "spring_and_targets": d_v2["spring"],
            "trajectory_contract": d_v2["trajectories"],
            "authority_labels": d_v2["authority_labels"],
            "accounting_formula": {
                "dW": "tau_cmd*(theta_next-theta)",
                "E": "0.5*I_model*omega^2+0.5*k*(theta-theta_ref)^2",
                "dD": "dW-(E_next-E)",
                "D": "D starts at 0 and accumulates",
            },
            "calibration": {
                "profile": "F00",
                "trajectory_signs": list(d_v2["trajectories"]["signs"]),
                "trajectories": calibration,
                "completed_before_tolerance": True,
            },
            "tolerance_freeze": tolerance,
            "f10": {
                "profile": "F10",
                "trajectory_signs": list(d_v2["trajectories"]["signs"]),
                "per_sign": f10_results,
                "overall_pass": overall_pass,
                "tolerance_recomputed_from_f10": False,
            },
            "scientific_verdict": "PASS" if overall_pass else "FAIL",
            "cleanup": None,
        }
    except BaseException as exc:
        primary_error = exc
    finally:
        if cleanup_ready:
            try:
                cleanup_result = _d_v2_cleanup(
                    scene=scene, door=door, env_ids=env_ids, hinge_id=hinge_id, original=original
                )
            except BaseException as exc:
                teardown_errors.append(exc)
        if sim is not None:
            try:
                sim.clear_instance()
            except BaseException as exc:
                teardown_errors.append(exc)
    lifecycle_errors = ([] if primary_error is None else [primary_error]) + teardown_errors
    if lifecycle_errors:
        _raise_d_v2_lifecycle_errors(lifecycle_errors)
    if receipt_payload is None or cleanup_result is None:
        raise RuntimeError("D-v2 runtime completed without receipt and cleanup payloads")
    receipt_payload["cleanup"] = cleanup_result
    write_json(output, receipt_payload)


def _profile_friction(friction: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(friction)
    result.update(profile)
    return result


def _trace_quality(velocity_trace: Sequence[float], slip_threshold: float) -> dict[str, Any]:
    if not velocity_trace:
        raise RuntimeError("behavioral trace is empty")
    previous_slip_sign = 0
    first_slip_index: int | None = None
    slip_reentries = 0
    was_slipping = False
    sign_reversals = 0
    for index, velocity in enumerate(velocity_trace):
        if not math.isfinite(float(velocity)):
            raise RuntimeError("behavioral trace contains a nonfinite velocity")
        value = float(velocity)
        slipping = abs(value) >= slip_threshold
        sign = 1 if value > 0.0 else -1 if value < 0.0 else 0
        if slipping:
            if previous_slip_sign != 0 and sign != previous_slip_sign:
                sign_reversals += 1
            previous_slip_sign = sign
        if slipping and first_slip_index is None:
            first_slip_index = index
        elif slipping and first_slip_index is not None and not was_slipping:
            slip_reentries += 1
        was_slipping = slipping
    return {
        "first_slip_index": first_slip_index,
        "slip_reentries_after_first": slip_reentries,
        "sign_reversals": sign_reversals,
        "slip_threshold_rad_s": slip_threshold,
    }


def _run_behavioral_decay_trials(
    *,
    sim: Any,
    scene: Any,
    friction: Mapping[str, Any],
    door_fixture: Mapping[str, Any],
    profile: Mapping[str, Any],
    device: str,
    dt: float,
    initial_angle_rad: float,
    interior_margin_rad: float,
    speeds_rad_s: Sequence[float],
    frames: int,
    damping_native: float,
    stiffness_native: float,
    max_positive_abs_speed_increment: float,
    trial_frame_authority: str,
    selected_env_index: int = 0,
) -> dict[str, Any]:
    import torch

    from gr00t.rl.envs.door.a2_v24_friction import A2V24DoorFrictionBackend, V24FrictionConfig

    door = scene["door"]
    hinge_id, hinge_name = _select_single_hinge(door)
    env_ids = _single_env_ids(door, selected_env_index=selected_env_index, device=device)
    friction_config = V24FrictionConfig.from_mapping(
        {
            "a2_v24_friction_enabled": True,
            "a2_v24_friction_backend": friction["backend"],
            "a2_v24_friction_static_effort": profile["static_effort_nm"],
            "a2_v24_friction_dynamic_effort": profile["dynamic_effort_nm"],
            "a2_v24_friction_viscous_coefficient": profile["viscous_coefficient_nm_s_per_rad"],
        }
    )
    backend = A2V24DoorFrictionBackend(door, friction_config, device=door.data.joint_pos.device)
    original_friction = {
        field: _selected_hinge_field(door, field, env_ids, hinge_id)
        for field in ("joint_friction_coeff", "joint_dynamic_friction_coeff", "joint_viscous_friction_coeff")
    }
    original_damping = _selected_hinge_field(door, "joint_damping", env_ids, hinge_id)
    original_stiffness = _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id)
    original_targets = door.data.joint_effort_target[env_ids].clone()
    baseline_position = door.data.joint_pos[env_ids].clone()
    captured_baseline_velocity = door.data.joint_vel[env_ids].clone()
    baseline_velocity = torch.zeros_like(captured_baseline_velocity)
    primary_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    result: dict[str, Any] | None = None
    try:
        friction_receipt = backend.apply(env_ids)
        dynamic_readback_rows = friction_receipt["readback"]["joint_dynamic_friction_coeff"]
        if len(dynamic_readback_rows) != 1 or len(dynamic_readback_rows[0]) != 1:
            raise RuntimeError("behavioral dynamic-friction readback shape mismatch")
        dynamic_readback = float(dynamic_readback_rows[0][0])
        if not math.isfinite(dynamic_readback) or abs(dynamic_readback - profile["dynamic_effort_nm"]) > 1.0e-6:
            raise RuntimeError(
                "behavioral dynamic-friction readback does not match the registered profile: "
                f"readback={dynamic_readback}, expected={profile['dynamic_effort_nm']}"
            )
        requested_damping = torch.full_like(original_damping, damping_native)
        requested_stiffness = torch.full_like(original_stiffness, stiffness_native)
        door.write_joint_damping_to_sim(requested_damping, joint_ids=[hinge_id], env_ids=env_ids)
        door.write_joint_stiffness_to_sim(requested_stiffness, joint_ids=[hinge_id], env_ids=env_ids)
        damping_readback = _selected_hinge_field(door, "joint_damping", env_ids, hinge_id)
        stiffness_readback = _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id)
        if not bool(torch.allclose(damping_readback, requested_damping, atol=1.0e-6, rtol=0.0)):
            raise RuntimeError("behavioral damping readback mismatch")
        if not bool(torch.allclose(stiffness_readback, requested_stiffness, atol=1.0e-6, rtol=0.0)):
            raise RuntimeError("behavioral stiffness readback mismatch")
        limits = door.data.joint_pos_limits[env_ids][:, hinge_id, :].clone()
        if tuple(limits.shape) != (env_ids.numel(), 2) or not bool(torch.all(torch.isfinite(limits)).item()):
            raise RuntimeError("behavioral hinge position limits are unavailable or nonfinite")
        lower_limit = float(limits[:, 0].min().item())
        upper_limit = float(limits[:, 1].min().item())
        if not lower_limit + interior_margin_rad < initial_angle_rad < upper_limit - interior_margin_rad:
            raise RuntimeError("behavioral initial hinge angle is not safely interior")

        trials: list[dict[str, Any]] = []
        for requested_speed in speeds_rad_s:
            _clear_hinge_target(door, hinge_id, env_ids)
            trial_position = baseline_position.clone()
            trial_position[:, hinge_id] = initial_angle_rad
            trial_velocity = baseline_velocity.clone()
            trial_velocity[:, hinge_id] = requested_speed
            door.write_joint_state_to_sim(trial_position, trial_velocity, env_ids=env_ids)
            scene.write_data_to_sim()
            start_angle = float(door.data.joint_pos[env_ids, hinge_id].item())
            start_velocity = float(door.data.joint_vel[env_ids, hinge_id].item())
            if not math.isfinite(start_angle) or not math.isfinite(start_velocity):
                raise RuntimeError("behavioral trial start state is nonfinite")
            if abs(start_velocity - requested_speed) > 1.0e-6:
                raise RuntimeError("behavioral trial start velocity readback mismatch")
            angle_trace = [start_angle]
            velocity_trace = [start_velocity]
            previous_abs_speed = abs(start_velocity)
            for _ in range(frames):
                _step_door_scene(sim, scene, dt)
                angle = float(door.data.joint_pos[env_ids, hinge_id].item())
                velocity = float(door.data.joint_vel[env_ids, hinge_id].item())
                if not math.isfinite(angle) or not math.isfinite(velocity):
                    raise RuntimeError("behavioral decay produced a nonfinite state")
                abs_speed_increment = abs(velocity) - previous_abs_speed
                if abs_speed_increment > max_positive_abs_speed_increment:
                    raise RuntimeError(
                        "behavioral decay positive abs-speed increment exceeded the registered tolerance: "
                        f"increment={abs_speed_increment}, limit={max_positive_abs_speed_increment}"
                    )
                previous_abs_speed = abs(velocity)
                angle_trace.append(angle)
                velocity_trace.append(velocity)
            final_abs_speed = abs(velocity_trace[-1])
            initial_abs_speed = abs(velocity_trace[0])
            loss_rate = (initial_abs_speed - final_abs_speed) / (frames * dt)
            trials.append(
                {
                    "requested_speed_rad_s": requested_speed,
                    "start_angle_rad": start_angle,
                    "start_velocity_rad_s": start_velocity,
                    "final_angle_rad": angle_trace[-1],
                    "final_velocity_rad_s": velocity_trace[-1],
                    "initial_abs_speed_rad_s": initial_abs_speed,
                    "final_abs_speed_rad_s": final_abs_speed,
                    "endpoint_abs_speed_loss_rate_rad_s2": loss_rate,
                    "frames": frames,
                    "dt_s": dt,
                    "angle_trace_rad": angle_trace,
                    "velocity_trace_rad_s": velocity_trace,
                    "authority": "BEHAVIORAL_SEMANTIC_ONLY_NO_FRICTION_TORQUE",
                }
            )
        result = {
            "status": "MEASURED_BEHAVIORAL",
            "profile": dict(profile),
            "hinge_joint_name": hinge_name,
            "friction_readback": friction_receipt,
            "damping_requested_native": damping_native,
            "damping_readback_native": damping_readback.detach().cpu().tolist(),
            "stiffness_requested_native": stiffness_native,
            "stiffness_readback_native": stiffness_readback.detach().cpu().tolist(),
            "dynamic_friction_readback": dynamic_readback,
            "initial_angle_rad": initial_angle_rad,
            "joint_limits_rad": limits.detach().cpu().tolist(),
            "interior_margin_rad": interior_margin_rad,
            "frames": frames,
            "dt_s": dt,
            "max_positive_abs_speed_increment_rad_s": max_positive_abs_speed_increment,
            "trial_frame_authority": trial_frame_authority,
            "trials": trials,
            "authority": "BEHAVIORAL_SEMANTIC_ONLY_NO_FRICTION_TORQUE",
        }
    except BaseException as exc:
        primary_error = exc
    finally:
        try:
            cleanup_target = original_targets.clone()
            cleanup_target[:, hinge_id] = 0.0
            door.set_joint_effort_target(cleanup_target, env_ids=env_ids)
            door.write_joint_damping_to_sim(original_damping, joint_ids=[hinge_id], env_ids=env_ids)
            door.write_joint_stiffness_to_sim(original_stiffness, joint_ids=[hinge_id], env_ids=env_ids)
            cleanup_friction = _restore_friction(door, env_ids, hinge_id, original_friction)
            door.write_joint_state_to_sim(baseline_position, captured_baseline_velocity, env_ids=env_ids)
            scene.write_data_to_sim()
            final_targets = door.data.joint_effort_target[env_ids].clone()
            if not bool(torch.all(final_targets[:, hinge_id] == 0.0).item()):
                raise RuntimeError("behavioral cleanup hinge target readback failed")
            if result is not None:
                result["cleanup"] = {
                    "restored_friction": cleanup_friction,
                    "restored_damping": True,
                    "restored_stiffness": True,
                    "baseline_state_restored": True,
                }
        except BaseException as exc:
            cleanup_error = exc
    if primary_error is not None:
        if cleanup_error is not None:
            raise RuntimeError("behavioral trial failed and cleanup also failed") from primary_error
        raise primary_error
    if cleanup_error is not None:
        raise cleanup_error
    if result is None:
        raise RuntimeError("behavioral trial completed without a receipt")
    return result


def _summarize_plateau(trials: Sequence[Mapping[str, Any]], relative_spread_max: float, direction_asymmetry_max: float) -> dict[str, Any]:
    rates = {float(trial["requested_speed_rad_s"]): float(trial["endpoint_abs_speed_loss_rate_rad_s2"]) for trial in trials}
    if set(rates) != set(AI_SPEED_ORDER):
        raise RuntimeError("plateau receipt does not contain the registered speed set")
    positive_rates = list(rates.values())
    endpoint_positive = all(rate > 0.0 for rate in positive_rates)
    rate_max = max(positive_rates)
    relative_spread = (max(positive_rates) - min(positive_rates)) / rate_max if rate_max > 0.0 else math.inf
    direction_asymmetries = {
        str(magnitude): abs(rates[magnitude] - rates[-magnitude]) / max(rates[magnitude], rates[-magnitude])
        for magnitude in (0.1, 0.2)
    }
    direction_asymmetry = max(direction_asymmetries.values())
    return {
        "loss_rates_rad_s2": {str(speed): rate for speed, rate in rates.items()},
        "endpoint_abs_speed_loss_rate_positive": endpoint_positive,
        "relative_spread": relative_spread,
        "relative_spread_max": relative_spread_max,
        "direction_asymmetries": direction_asymmetries,
        "direction_asymmetry": direction_asymmetry,
        "direction_asymmetry_max": direction_asymmetry_max,
        "passed": endpoint_positive and relative_spread <= relative_spread_max and direction_asymmetry <= direction_asymmetry_max,
        "authority": "BEHAVIORAL_SEMANTIC_ONLY_NO_FRICTION_TORQUE",
    }


def _summarize_control_ratios(
    friction_trials: Sequence[Mapping[str, Any]],
    damping_trials: Sequence[Mapping[str, Any]],
    friction_ratio_low: float,
    friction_ratio_high: float,
    damping_ratio_min: float,
) -> dict[str, Any]:
    friction_rates = {float(trial["requested_speed_rad_s"]): float(trial["endpoint_abs_speed_loss_rate_rad_s2"]) for trial in friction_trials}
    damping_rates = {float(trial["requested_speed_rad_s"]): float(trial["endpoint_abs_speed_loss_rate_rad_s2"]) for trial in damping_trials}
    friction_ratios = {
        str(magnitude): {
            "positive": friction_rates[magnitude] / friction_rates[magnitude / 2.0],
            "negative": friction_rates[-magnitude] / friction_rates[-magnitude / 2.0],
        }
        for magnitude in (0.2,)
    }
    damping_ratios = {
        str(magnitude): {
            "positive": damping_rates[magnitude] / damping_rates[magnitude / 2.0],
            "negative": damping_rates[-magnitude] / damping_rates[-magnitude / 2.0],
        }
        for magnitude in (0.2,)
    }
    friction_pass = all(
        friction_ratio_low <= value <= friction_ratio_high
        for values in friction_ratios.values()
        for value in values.values()
    )
    damping_pass = all(value >= damping_ratio_min for values in damping_ratios.values() for value in values.values())
    return {
        "friction_high_low_ratios": friction_ratios,
        "damping_high_low_ratios": damping_ratios,
        "friction_ratio_range": [friction_ratio_low, friction_ratio_high],
        "damping_ratio_min": damping_ratio_min,
        "both_directions_agree": friction_pass and damping_pass,
        "friction_pass": friction_pass,
        "damping_pass": damping_pass,
        "passed": friction_pass and damping_pass,
        "authority": "BEHAVIORAL_SEMANTIC_ONLY_NO_FRICTION_TORQUE",
    }


def _summarize_dissipation(
    trials: Sequence[Mapping[str, Any]], max_positive_increment: float
) -> dict[str, Any]:
    rows = []
    final_le_initial = True
    max_increment = 0.0
    for trial in trials:
        trace = [abs(float(value)) for value in trial["velocity_trace_rad_s"]]
        increments = [trace[index] - trace[index - 1] for index in range(1, len(trace))]
        trial_max_increment = max(increments) if increments else 0.0
        max_increment = max(max_increment, trial_max_increment)
        trial_final_le_initial = trace[-1] <= trace[0]
        final_le_initial = final_le_initial and trial_final_le_initial
        rows.append(
            {
                "requested_speed_rad_s": trial["requested_speed_rad_s"],
                "final_abs_speed_le_initial": trial_final_le_initial,
                "max_positive_abs_speed_increment_rad_s": trial_max_increment,
            }
        )
    proxy_pass = final_le_initial and max_increment <= max_positive_increment
    return {
        "status": "AUTHORITY_INSUFFICIENT",
        "direct_criterion": "AUTHORITY_INSUFFICIENT",
        "source": "UNAVAILABLE_NO_SOLVER_FRICTION_TORQUE_VIEW",
        "literal_target": "tau_friction * omega",
        "cannot_pass_literal_target": True,
        "proxy": {
            "final_abs_speed_le_initial": final_le_initial,
            "max_positive_abs_speed_increment_rad_s": max_increment,
            "increment_limit_rad_s": max_positive_increment,
            "proxy_pass": proxy_pass,
            "trials": rows,
        },
        "authority": "BEHAVIORAL_PROXY_ONLY",
    }


def _run_chatter_trial(
    *,
    sim: Any,
    scene: Any,
    friction: Mapping[str, Any],
    door_fixture: Mapping[str, Any],
    profile: Mapping[str, Any],
    command_effort_nm: float,
    device: str,
    dt: float,
    frames: int,
    slip_threshold: float,
    trial_frame_authority: str,
    selected_env_index: int = 0,
) -> dict[str, Any]:
    import torch

    from gr00t.rl.envs.door.a2_v24_friction import A2V24DoorFrictionBackend, V24FrictionConfig

    door = scene["door"]
    hinge_id, hinge_name = _select_single_hinge(door)
    env_ids = _single_env_ids(door, selected_env_index=selected_env_index, device=device)
    friction_config = V24FrictionConfig.from_mapping(
        {
            "a2_v24_friction_enabled": True,
            "a2_v24_friction_backend": friction["backend"],
            "a2_v24_friction_static_effort": profile["static_effort_nm"],
            "a2_v24_friction_dynamic_effort": profile["dynamic_effort_nm"],
            "a2_v24_friction_viscous_coefficient": profile["viscous_coefficient_nm_s_per_rad"],
        }
    )
    backend = A2V24DoorFrictionBackend(door, friction_config, device=door.data.joint_pos.device)
    original_friction = {
        field: _selected_hinge_field(door, field, env_ids, hinge_id)
        for field in ("joint_friction_coeff", "joint_dynamic_friction_coeff", "joint_viscous_friction_coeff")
    }
    original_damping = _selected_hinge_field(door, "joint_damping", env_ids, hinge_id)
    original_stiffness = _selected_hinge_field(door, "joint_stiffness", env_ids, hinge_id)
    original_targets = door.data.joint_effort_target[env_ids].clone()
    baseline_position = door.data.joint_pos[env_ids].clone()
    baseline_velocity = torch.zeros_like(door.data.joint_vel[env_ids])
    primary_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    result: dict[str, Any] | None = None
    try:
        friction_receipt = backend.apply(env_ids)
        door.write_joint_damping_to_sim(torch.zeros_like(original_damping), joint_ids=[hinge_id], env_ids=env_ids)
        door.write_joint_stiffness_to_sim(torch.zeros_like(original_stiffness), joint_ids=[hinge_id], env_ids=env_ids)
        _clear_hinge_target(door, hinge_id, env_ids)
        door.write_joint_state_to_sim(baseline_position, baseline_velocity, env_ids=env_ids)
        _step_door_scene(sim, scene, dt)
        start_velocity = float(door.data.joint_vel[env_ids, hinge_id].item())
        if abs(start_velocity) > friction["stationarity_velocity_tolerance_rad_s"]:
            raise RuntimeError("chatter trial reset did not meet stationarity velocity tolerance")
        command_tensor = torch.full(
            (env_ids.numel(), 1), command_effort_nm, dtype=door.data.joint_pos.dtype, device=door.data.joint_pos.device
        )
        door.set_joint_effort_target(command_tensor, joint_ids=[hinge_id], env_ids=env_ids)
        angle_trace = []
        velocity_trace = []
        for _ in range(frames):
            _step_door_scene(sim, scene, dt)
            angle = float(door.data.joint_pos[env_ids, hinge_id].item())
            velocity = float(door.data.joint_vel[env_ids, hinge_id].item())
            if not math.isfinite(angle) or not math.isfinite(velocity):
                raise RuntimeError("chatter trial produced a nonfinite hinge state")
            angle_trace.append(angle)
            velocity_trace.append(velocity)
        quality = _trace_quality(velocity_trace, slip_threshold)
        result = {
            "status": "MEASURED_CHATTER_BEHAVIOR",
            "profile": dict(profile),
            "hinge_joint_name": hinge_name,
            "command_effort_nm": command_effort_nm,
            "frames": frames,
            "dt_s": dt,
            "trial_frame_authority": trial_frame_authority,
            "start_velocity_rad_s": start_velocity,
            "angle_trace_rad": angle_trace,
            "velocity_trace_rad_s": velocity_trace,
            "quality": quality,
            "chatter_passed": quality["slip_reentries_after_first"] < 2,
            "friction_readback": friction_receipt,
            "authority": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
        }
    except BaseException as exc:
        primary_error = exc
    finally:
        try:
            cleanup_target = original_targets.clone()
            cleanup_target[:, hinge_id] = 0.0
            door.set_joint_effort_target(cleanup_target, env_ids=env_ids)
            door.write_joint_damping_to_sim(original_damping, joint_ids=[hinge_id], env_ids=env_ids)
            door.write_joint_stiffness_to_sim(original_stiffness, joint_ids=[hinge_id], env_ids=env_ids)
            cleanup_friction = _restore_friction(door, env_ids, hinge_id, original_friction)
            door.write_joint_state_to_sim(baseline_position, baseline_velocity, env_ids=env_ids)
            scene.write_data_to_sim()
            if result is not None:
                result["cleanup"] = {"restored_friction": cleanup_friction, "restored_damping": True, "restored_stiffness": True}
        except BaseException as exc:
            cleanup_error = exc
    if primary_error is not None:
        if cleanup_error is not None:
            raise RuntimeError("chatter trial failed and cleanup also failed") from primary_error
        raise primary_error
    if cleanup_error is not None:
        raise cleanup_error
    if result is None:
        raise RuntimeError("chatter trial completed without a receipt")
    return result


def _summarize_breakaway_profiles(receipts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    brackets: dict[str, list[float] | None] = {}
    literal_results: dict[str, bool] = {}
    valid = True
    for name in AI_PROFILE_ORDER:
        breakaway = receipts[name]["breakaway"]
        bracket = breakaway["measured_bracket_nm"]
        brackets[name] = bracket
        literal_results[name] = bool(breakaway["requested_static_in_bracket"])
        valid = valid and isinstance(bracket, list) and len(bracket) == 2
        if valid and bracket is not None:
            valid = all(math.isfinite(float(value)) for value in bracket)
    upper_non_decreasing = False
    f10_upper_greater = False
    if valid:
        uppers = [float(brackets[name][1]) for name in AI_PROFILE_ORDER if brackets[name] is not None]
        upper_non_decreasing = uppers[0] <= uppers[1] <= uppers[2]
        f10_upper_greater = uppers[2] > uppers[0]
    passed = valid and all(literal_results.values()) and upper_non_decreasing and f10_upper_greater
    return {
        "profiles": brackets,
        "literal_containment": literal_results,
        "upper_brackets_non_decreasing": upper_non_decreasing,
        "f10_upper_strictly_greater_than_f00": f10_upper_greater,
        "passed": passed,
        "authority": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
    }


def _valid_breakaway_evidence(receipt: Mapping[str, Any]) -> bool:
    breakaway = receipt.get("breakaway")
    if not isinstance(breakaway, Mapping):
        return False
    bracket = breakaway.get("measured_bracket_nm")
    threshold = breakaway.get("measured_threshold_nm")
    return (
        receipt.get("status") == "PASS"
        and isinstance(bracket, list)
        and len(bracket) == 2
        and all(math.isfinite(float(value)) for value in bracket)
        and isinstance(threshold, (int, float))
        and math.isfinite(float(threshold))
        and breakaway.get("requested_static_in_bracket") is True
        and receipt.get("timing", {}).get("stopped_at_first_breakaway") is True
    )


def _valid_chatter_classification(receipt: Mapping[str, Any]) -> bool:
    quality = receipt.get("quality")
    if not isinstance(quality, Mapping):
        return False
    reentries = quality.get("slip_reentries_after_first")
    reversals = quality.get("sign_reversals")
    return (
        receipt.get("status") == "MEASURED_CHATTER_BEHAVIOR"
        and isinstance(receipt.get("chatter_passed"), bool)
        and isinstance(reentries, int)
        and reentries >= 0
        and isinstance(reversals, int)
        and reversals >= 0
    )


def _summarize_g_cell(
    receipt: Mapping[str, Any],
    slip_threshold: float,
    fixture_gate: Mapping[str, Any],
) -> dict[str, Any]:
    quality_rows = []
    finite = True
    unexpected_sign_reversal = False
    unexpected_chatter = False
    for row in receipt["samples"]:
        velocity_trace = row.get("velocity_trace_rad_s")
        if not isinstance(velocity_trace, list):
            raise RuntimeError("G receipt is missing registered raw velocity traces")
        quality = _trace_quality(velocity_trace, slip_threshold)
        quality_rows.append({"command_effort_nm": row["command_effort_nm"], **quality})
        unexpected_sign_reversal = unexpected_sign_reversal or quality["sign_reversals"] > 0
        unexpected_chatter = unexpected_chatter or quality["slip_reentries_after_first"] >= 2
        finite = finite and all(math.isfinite(float(value)) for value in velocity_trace)
    passed = bool(fixture_gate["passed"]) and finite and not unexpected_sign_reversal and not unexpected_chatter
    return {
        "finite_state_and_readback": finite,
        "realized_fixture_gate": dict(fixture_gate),
        "unexpected_sign_reversal": unexpected_sign_reversal,
        "unexpected_chatter": unexpected_chatter,
        "quality_rows": quality_rows,
        "passed": passed,
        "surface_tags": dict(AI_SURFACE_TAGS),
    }


def _build_ai_receipt(
    *,
    ai: Mapping[str, Any],
    friction: Mapping[str, Any],
    a_receipts: Mapping[str, Mapping[str, Any]],
    a_summary: Mapping[str, Any],
    b_receipt: Mapping[str, Any],
    b_summary: Mapping[str, Any],
    c_receipt: Mapping[str, Any],
    c_summary: Mapping[str, Any],
    d_summary: Mapping[str, Any],
    e_receipt: Mapping[str, Any],
    e_summary: Mapping[str, Any],
    f_summary: Mapping[str, Any],
    g_receipts: Mapping[str, Any],
    g_summary: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": PROBE_SCHEMA,
        "mode": AI_ACCEPTANCE_MODE,
        "status": "PENDING_H_I",
        "overall_status": "PENDING_H_I",
        "batch_id": ai["batch_id"],
        "device": ai["device"],
        "surface_tags": ai["surface_tags"],
        "orthogonality": ai["orthogonality"],
        "provisional_allowed_typed_result": "V24_FRICTION_AUTHORITY_INSUFFICIENT",
        "authority_boundary": {
            "command_effort_authority": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
            "solver_friction_torque_source": "UNAVAILABLE",
            "no_friction_torque_inference": True,
        },
        "A": {"summary": dict(a_summary), "raw_profile_receipts": dict(a_receipts)},
        "B": {"summary": dict(b_summary), "raw_behavioral_receipt": dict(b_receipt)},
        "C": {"summary": dict(c_summary), "raw_behavioral_receipt": dict(c_receipt)},
        "D": dict(d_summary),
        "E": {"summary": dict(e_summary), "raw_chatter_receipt": dict(e_receipt)},
        "F": dict(f_summary),
        "G": {"summary": dict(g_summary), "raw_sparse_cell_receipts": dict(g_receipts)},
        "H": {"status": "PENDING_PRODUCTION_RESET_RECEIPT"},
        "I": {"status": "PENDING_P0_PARITY_RECEIPT"},
        "parameter_range_freeze": "NOT_PERFORMED",
        "friction_profile_contract": {
            "static_effort_nm": friction["static_effort_nm"],
            "dynamic_effort_nm": friction["dynamic_effort_nm"],
            "viscous_coefficient_nm_s_per_rad": friction["viscous_coefficient_nm_s_per_rad"],
            "grid_resolution_nm": friction["resolution_effort_nm"],
        },
    }


def _run_ai_runtime(config_path: Path, *, device: str, output: Path) -> None:
    import torch

    _assert_selected_sources(config_path)
    friction = _probe_config_values(config_path)
    ai = _ai_acceptance_config(config_path, friction)
    if device != ai["device"]:
        raise ValueError(f"A_I_ACCEPTANCE requires the configured single GPU0 device {ai['device']!r}")
    profiles = ai["friction_profiles"]

    source_configs: list[dict[str, Any]] = [dict(DOOR_FIXED_CONFIG)]
    for cell in ai["sparse_cells"]:
        source_config = dict(DOOR_FIXED_CONFIG)
        source_config.update(
            {
                "rand_door_weight": cell["door_weight_kg"],
                "rand_hinge_drive_damping": cell["damping_native"],
                "rand_hinge_drive_stiffness": cell["stiffness_native"],
            }
        )
        source_configs.append(source_config)

    sim = None
    try:
        sim, scene, door, fixtures = _build_door_only_scene(
            device=device,
            dt=friction["dt_s"],
            probe_seed=friction["probe_seed"],
            door_configs=source_configs,
        )
        if len(fixtures) != len(source_configs) or len(fixtures) != 1 + len(ai["sparse_cells"]):
            raise RuntimeError("A-I scene fixture order/count does not match the registered sparse cells")
        base_fixture = fixtures[0]
        base_env_ids = _single_env_ids(door, selected_env_index=0, device=device)
        common_profile_position = door.data.joint_pos[base_env_ids].clone()
        common_profile_velocity = door.data.joint_vel[base_env_ids].clone()
        common_trial_velocity = torch.zeros_like(common_profile_velocity)
        if not bool(torch.isfinite(common_profile_position).all().item()) or not bool(torch.isfinite(common_profile_velocity).all().item()):
            raise RuntimeError("common A-profile baseline joint state is nonfinite")
        a_receipts: dict[str, Mapping[str, Any]] = {}
        for profile_name in AI_PROFILE_ORDER:
            a_receipts[profile_name] = run_torque_ramp(
                sim=sim,
                scene=scene,
                friction=_profile_friction(friction, profiles[profile_name]),
                door_fixture=base_fixture,
                device=device,
                dt=friction["dt_s"],
                record_raw_traces=True,
                trial_baseline_position=common_profile_position,
                trial_baseline_velocity=common_trial_velocity,
                selected_env_index=0,
            )
        a_summary = _summarize_breakaway_profiles(a_receipts)
        b_receipt = _run_behavioral_decay_trials(
            sim=sim,
            scene=scene,
            friction=friction,
            door_fixture=base_fixture,
            profile=profiles["F10"],
            device=device,
            dt=friction["dt_s"],
            initial_angle_rad=ai["plateau"]["initial_angle_rad"],
            interior_margin_rad=ai["plateau"]["interior_margin_rad"],
            speeds_rad_s=ai["plateau"]["speeds_rad_s"],
            frames=ai["plateau"]["frames"],
            damping_native=0.0,
            stiffness_native=0.0,
            max_positive_abs_speed_increment=ai["dissipation"]["max_positive_abs_speed_increment_rad_s"],
            trial_frame_authority="V23_BEHAVIORAL_100_FRAME_TRIAL",
            selected_env_index=0,
        )
        b_summary = _summarize_plateau(
            b_receipt["trials"],
            ai["plateau"]["relative_spread_max"],
            ai["plateau"]["direction_asymmetry_max"],
        )
        c_receipt = _run_behavioral_decay_trials(
            sim=sim,
            scene=scene,
            friction=friction,
            door_fixture=base_fixture,
            profile=profiles["F00"],
            device=device,
            dt=friction["dt_s"],
            initial_angle_rad=ai["plateau"]["initial_angle_rad"],
            interior_margin_rad=ai["plateau"]["interior_margin_rad"],
            speeds_rad_s=ai["plateau"]["speeds_rad_s"],
            frames=ai["plateau"]["frames"],
            damping_native=50.0,
            stiffness_native=0.0,
            max_positive_abs_speed_increment=ai["dissipation"]["max_positive_abs_speed_increment_rad_s"],
            trial_frame_authority="V23_CONTROL_100_FRAME_TRIAL",
            selected_env_index=0,
        )
        c_summary = _summarize_control_ratios(
            b_receipt["trials"],
            c_receipt["trials"],
            ai["control"]["friction_ratio_low"],
            ai["control"]["friction_ratio_high"],
            ai["control"]["damping_ratio_min"],
        )
        d_summary = _summarize_dissipation(
            b_receipt["trials"], ai["dissipation"]["max_positive_abs_speed_increment_rad_s"]
        )
        f10_threshold = a_receipts["F10"]["breakaway"]["measured_threshold_nm"]
        if f10_threshold is None:
            e_receipt = {
                "status": "PENDING_F10_BREAKAWAY",
                "reason": "F10 did not produce a measured first-breakaway command",
                "authority": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
            }
            e_summary = {"status": "PENDING_F10_BREAKAWAY", "passed": False}
        else:
            e_receipt = _run_chatter_trial(
                sim=sim,
                scene=scene,
                friction=friction,
                door_fixture=base_fixture,
                profile=profiles["F10"],
                command_effort_nm=float(f10_threshold),
                device=device,
                dt=friction["dt_s"],
                frames=V23_STATIC_TRIAL_FRAMES,
                slip_threshold=ai["chatter"]["slip_velocity_threshold_rad_s"],
                trial_frame_authority="V23_CHATTER_100_FRAME_TRIAL",
                selected_env_index=0,
            )
            e_summary = {
                "status": "PASS" if e_receipt["chatter_passed"] else "FAIL_CHATTER",
                "passed": e_receipt["chatter_passed"],
                "first_breakaway_command_nm": f10_threshold,
                "slip_reentries_after_first": e_receipt["quality"]["slip_reentries_after_first"],
                "sign_reversals": e_receipt["quality"]["sign_reversals"],
                "slip_threshold_rad_s": ai["chatter"]["slip_velocity_threshold_rad_s"],
            }

        g_receipts: dict[str, Mapping[str, Any]] = {}
        g_summary: dict[str, Any] = {"cells": {}, "parameter_range_freeze": "NOT_PERFORMED"}
        for cell_offset, cell in enumerate(ai["sparse_cells"], start=1):
            cell_id = cell["id"]
            cell_fixture = fixtures[cell_offset]
            fixture_gate = _read_g_fixture_gate(
                door,
                cell_fixture,
                device=device,
                selected_env_index=cell_offset,
                realized_scaled_distance_max=ai["orthogonality"]["realized_scaled_distance_max"],
            )
            if not fixture_gate["passed"]:
                raise RuntimeError(
                    f"G sparse cell {cell_id} failed the realized fixture scaled-distance gate: "
                    f"{fixture_gate['realized_scaled_distance']} > "
                    f"{fixture_gate['realized_scaled_distance_max']}"
                )
            cell_receipt = run_torque_ramp(
                sim=sim,
                scene=scene,
                friction=_profile_friction(friction, profiles["F10"]),
                door_fixture=cell_fixture,
                device=device,
                dt=friction["dt_s"],
                record_raw_traces=True,
                neutralize_damping_stiffness=False,
                selected_env_index=cell_offset,
            )
            g_receipts[cell_id] = {
                "cell": cell,
                "fixture_gate": fixture_gate,
                "receipt": cell_receipt,
            }
            g_summary["cells"][cell_id] = _summarize_g_cell(
                cell_receipt,
                ai["chatter"]["slip_velocity_threshold_rad_s"],
                fixture_gate,
            )
        g_summary["passed"] = all(item["passed"] for item in g_summary["cells"].values())
        g_summary["surface_tags"] = dict(ai["surface_tags"])

        fine_friction = dict(friction)
        fine_friction["hold_window_steps"] = ai["fine_dt"]["frames"]
        fine_friction["dt_s"] = ai["fine_dt"]["dt_s"]
        sim.set_simulation_dt(
            physics_dt=ai["fine_dt"]["dt_s"],
            rendering_dt=ai["fine_dt"]["dt_s"],
        )
        sim.reset()
        scene.update(ai["fine_dt"]["dt_s"])
        fine_fixture = fixtures[0]
        fine_a_receipt = run_torque_ramp(
            sim=sim,
            scene=scene,
            friction=_profile_friction(fine_friction, profiles["F10"]),
            door_fixture=fine_fixture,
            device=device,
            dt=ai["fine_dt"]["dt_s"],
            record_raw_traces=True,
            trial_frame_authority="V24_FINE_DT_200_FRAME_0P5S_TRIAL",
            selected_env_index=0,
        )
        fine_threshold = fine_a_receipt["breakaway"]["measured_threshold_nm"]
        if fine_threshold is None:
            fine_e_receipt = {"status": "PENDING_FINE_F10_BREAKAWAY", "passed": False}
        else:
            fine_e_receipt = _run_chatter_trial(
                sim=sim,
                scene=scene,
                friction=fine_friction,
                door_fixture=fine_fixture,
                profile=profiles["F10"],
                command_effort_nm=float(fine_threshold),
                device=device,
                dt=ai["fine_dt"]["dt_s"],
                frames=ai["fine_dt"]["frames"],
                slip_threshold=ai["chatter"]["slip_velocity_threshold_rad_s"],
                trial_frame_authority="V24_FINE_DT_200_FRAME_0P5S_CHATTER_TRIAL",
                selected_env_index=0,
            )
        base_a_observed = _valid_breakaway_evidence(a_receipts["F10"])
        fine_a_observed = _valid_breakaway_evidence(fine_a_receipt)
        base_e_observed = _valid_chatter_classification(e_receipt)
        fine_e_observed = _valid_chatter_classification(fine_e_receipt)
        base_a_class = bool(a_receipts["F10"]["breakaway"].get("requested_static_in_bracket")) if base_a_observed else False
        fine_a_class = bool(fine_a_receipt.get("breakaway", {}).get("requested_static_in_bracket")) if fine_a_observed else False
        base_e_class = bool(e_receipt.get("chatter_passed")) if base_e_observed else False
        fine_e_class = bool(fine_e_receipt.get("chatter_passed")) if fine_e_observed else False
        f_summary = {
            "base_dt_s": friction["dt_s"],
            "base_frames": friction["hold_window_steps"],
            "fine_dt_s": ai["fine_dt"]["dt_s"],
            "fine_frames": ai["fine_dt"]["frames"],
            "fine_duration_s": ai["fine_dt"]["duration_s"],
            "base_f10_breakaway_observed": base_a_observed,
            "fine_f10_breakaway_observed": fine_a_observed,
            "base_e_classification_observed": base_e_observed,
            "fine_e_classification_observed": fine_e_observed,
            "breakaway_containment_classification_match": base_a_class == fine_a_class,
            "chatter_classification_match": base_e_class == fine_e_class,
            "qualitative_only": True,
            "compare_raw_metrics": False,
            "base_f10_containment": base_a_class,
            "fine_f10_containment": fine_a_class,
            "base_f10_chatter_pass": base_e_class,
            "fine_f10_chatter_pass": fine_e_class,
            "fine_a_receipt": fine_a_receipt,
            "fine_e_receipt": fine_e_receipt,
        }
        f_summary["passed"] = (
            base_a_observed
            and fine_a_observed
            and base_e_observed
            and fine_e_observed
            and f_summary["breakaway_containment_classification_match"]
            and f_summary["chatter_classification_match"]
        )
        payload = _build_ai_receipt(
            ai=ai,
            friction=friction,
            a_receipts=a_receipts,
            a_summary=a_summary,
            b_receipt=b_receipt,
            b_summary=b_summary,
            c_receipt=c_receipt,
            c_summary=c_summary,
            d_summary=d_summary,
            e_receipt=e_receipt,
            e_summary=e_summary,
            f_summary=f_summary,
            g_receipts=g_receipts,
            g_summary=g_summary,
        )
        write_json(output, payload)
    finally:
        if sim is not None:
            sim.clear_instance()


def _run_runtime(config_path: Path, *, device: str, output: Path) -> None:
    _assert_selected_sources(config_path)
    friction = _probe_config_values(config_path)
    sim, scene, _door, door_fixtures = _build_door_only_scene(
        device=device,
        dt=friction["dt_s"],
        probe_seed=friction["probe_seed"],
    )
    door_fixture = door_fixtures[0]
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
    parser.add_argument("--tolerance", type=Path, default=None)
    parser.add_argument("--device", default="cuda:0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config_path = absolute(args.config)
    if args.plan:
        plan = build_d_v2_plan(config_path) if args.mode == ENERGY_MODE else build_plan(config_path)
        if args.output is None:
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            write_json(args.output, plan)
        return 0
    if args.mode not in (FIRST_RUNTIME_MODE, AI_ACCEPTANCE_MODE, ENERGY_MODE):
        raise RuntimeError(
            f"{args.mode} is not an executable v24 P1 runtime mode"
        )
    if args.output is None:
        raise ValueError(f"runtime {args.mode} requires --output under the canonical v24 artifact root")
    output = absolute(args.output)
    if V24_P1_FRICTION_ROOT not in output.parents:
        raise ValueError(
            "runtime output must be under logs_eval/base_v24/p1/friction_backend/"
        )
    if args.mode == ENERGY_MODE:
        if args.tolerance is None:
            raise ValueError("D_V2_ENERGY requires an explicit --tolerance path")
        _d_v2_config_values(config_path)
        tolerance_path = absolute(args.tolerance)
        from isaaclab.app import AppLauncher

        launcher = AppLauncher({"headless": True, "device": args.device, "enable_cameras": False})
        _run_d_v2_runtime(config_path, device=args.device, tolerance_path=tolerance_path, output=output)
        launcher.app.close()
        return 0
    _assert_selected_sources(config_path)
    friction = _probe_config_values(config_path)
    if args.mode == AI_ACCEPTANCE_MODE:
        ai = _ai_acceptance_config(config_path, friction)
        if args.device != ai["device"]:
            raise ValueError(f"A_I_ACCEPTANCE requires the configured single GPU0 device {ai['device']!r}")
    from isaaclab.app import AppLauncher

    launcher = AppLauncher({"headless": True, "device": args.device, "enable_cameras": False})
    if args.mode == AI_ACCEPTANCE_MODE:
        _run_ai_runtime(config_path, device=args.device, output=output)
    else:
        _run_runtime(config_path, device=args.device, output=output)
    launcher.app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
