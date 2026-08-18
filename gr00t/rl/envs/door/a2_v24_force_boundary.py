"""v24 P2 directional arm-capacity and door-load telemetry.

The P2 path is an estimate-only measurement hook.  It consumes IsaacLab's
public articulation tensors, computes the handle-opening direction, and keeps
the distinction between commanded/estimated torque and solver-applied torque
explicit.  It does not modify actions, observations, rewards, transitions, or
the articulation command path.
"""

from __future__ import annotations

import copy
import math
import json
import os
from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

import torch

from gr00t.rl.envs.door.a2_v24_df1_sampler import (
    F3Assignment,
    F3_FRICTION_PARAMETERS,
)


FORCE_BOUNDARY_SCHEMA = "a2_piper_v24_p2_force_boundary_v1"
ARM_BODY_NAME = "arm_body6_to_gripper"
ARM_JOINT_NAMES = tuple(f"arm_j{i}" for i in range(1, 7))
DOOR_HANDLE_NAME = "door_handle"
HINGE_PATTERN = ".*hinge.*"

CHECKPOINT_PATH = "logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt"
CHECKPOINT_LOAD_MODE = "selected_policy_only"

EPS_G_M = 1.0e-6
MARGIN_AUTHORITY = "ESTIMATE_ONLY_DIRECTIONAL_MARGIN"
PD_AUTHORITY = "ESTIMATE_ONLY_IMPLICIT_PD_COMMAND"
GRAVITY_AUTHORITY = "ISAACLAB_GRAVITY_COMPENSATION_ESTIMATE"
STATE_AUTHORITY = "HIGH_LEVEL_ARTICULATION_DATA"
MODELED_TORQUE_AUTHORITY = "MODELED_FROM_PARAMS"
ACTUAL_TORQUE_AUTHORITY = "UNAVAILABLE_NOT_USED"

PRIMARY_CAPS_NM = (100.0, 60.0, 40.0, 30.0, 25.0, 20.0)
CONTINGENCY_CAP_NM = 10.0
FORCE_WINDOW_TRANSITIONS = 25
FORCE_WINDOW_STABLE_GRASP_MIN_COUNT = 20
FORCE_WINDOW_OPENING_STAGES = frozenset((3, 4))
FORCE_WINDOW_SELECTION_STABLE_OPENING = "FIRST_STABLE_GRASP_OPENING_20_OF_25"
FORCE_WINDOW_SELECTION_ALPHA_FALLBACK = "NO_QUALIFYING_STABLE_GRASP_OPENING_FALLBACK_FIRST_ALPHA_VALID"
CONTROL_DT_S = 0.005
CONTROL_DECIMATION = 4
CONTROL_PERIOD_S = CONTROL_DT_S * CONTROL_DECIMATION
VELOCITY_EPSILON_RAD_S = 1.0e-3
FOOT_BODY_NAMES = ("FL_foot", "RL_foot", "FR_foot", "RR_foot")
FRICTION_PROFILES = {
    "F00": (0.0, 0.0, 0.0),
    "F05": (0.5, 0.375, 0.0),
    "F10": (1.0, 0.75, 0.0),
}
R13_FRICTION_PROFILES = {
    "P02": (2.0, 1.5, 0.0),
    "P05": (5.0, 3.75, 0.0),
    "P10": (10.0, 7.5, 0.0),
    "P20": (20.0, 15.0, 0.0),
}
REGISTERED_FRICTION_PROFILES = {**FRICTION_PROFILES, **R13_FRICTION_PROFILES}
R13_E1_SEMANTICS_REVISION = "R13_DOMAIN_ESCALATION"
RUNTIME_MODES = ("HI_FULL", "BOUNDARY_FULL", "BOUNDARY_RP0", "RESCUE_FULL")
AUTHORITY_SET = {
    "capacity_lambda": MARGIN_AUTHORITY,
    "pd_command": PD_AUTHORITY,
    "gravity": GRAVITY_AUTHORITY,
    "state": STATE_AUTHORITY,
    "actual_generalized_torque": ACTUAL_TORQUE_AUTHORITY,
    "door_friction": MODELED_TORQUE_AUTHORITY,
}
PARAMETER_VITALS_SCHEMA = "a2_piper_v24_p2_parameter_vitals_v1"
GRIPPER_JOINT_NAMES = ("arm_j7", "arm_j8")
GRIPPER_EFFORT_LIMITS_NM = (45.0, 45.0)
GRIPPER_STIFFNESS_NM_PER_RAD = (1300.0, 1300.0)
GRIPPER_DAMPING_NM_S_PER_RAD = (32.0, 32.0)
FRICTION_UNITS = {
    "static_friction_nm": "N*m",
    "dynamic_friction_nm": "N*m",
    "viscous_friction_nm_s_per_rad": "N*m*s/rad",
}


def _finite_tensor(value: Any, *, name: str, ndim: int | None = None) -> torch.Tensor:
    if not torch.is_tensor(value) or (ndim is not None and value.ndim != ndim):
        shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise TypeError(f"{name} must be a floating tensor with ndim={ndim}; got {shape}.")
    if not value.is_floating_point() or not torch.all(torch.isfinite(value)):
        raise ValueError(f"{name} must contain finite floating values.")
    return value


def _same_batch(values: Sequence[torch.Tensor], *, width: int | None = None, label: str) -> int:
    if not values:
        raise ValueError(f"{label} requires at least one tensor.")
    batch = int(values[0].shape[0])
    for index, value in enumerate(values):
        if value.ndim != 2 or value.shape[0] != batch or (width is not None and value.shape[1] != width):
            raise ValueError(f"{label}[{index}] must have shape ({batch}, {width}); got {tuple(value.shape)}.")
        if value.device != values[0].device or value.dtype != values[0].dtype:
            raise ValueError(f"{label} tensors must share dtype and device.")
    return batch


def _finite_nonnegative(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite non-negative real number.")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be a finite non-negative real number.")
    return number


@dataclass(frozen=True)
class V24P2ForceBoundaryConfig:
    """Resolved additive P2 configuration.

    Disabled configs deliberately do not require the P2 fields.  Enabling the
    hook requires the complete frozen parameter set; there is no fallback
    configuration.
    """

    enabled: bool
    mode: str
    checkpoint: str
    checkpoint_load_mode: str
    panel_mass_kg: float
    panel_width_m: float
    panel_height_m: float
    handle_height_m: float
    handle_width_m: float
    opening_lr: str
    opening_io: str
    hinge_axis_local: tuple[float, float, float]
    theta_ref_rad: float
    inertia_kg_m2: float
    damping_nm_s_per_rad: float
    stiffness_nm_per_rad: float
    static_friction_nm: float
    dynamic_friction_nm: float
    viscous_friction_nm_s_per_rad: float
    arm_caps_nm: tuple[float, ...]
    contingency_cap_nm: float
    active_cap_nm: float
    friction_profile: str
    runtime_mode: str
    seed: int
    scenario_ids: tuple[str, ...]
    continuity_id: str
    runtime_export_path: str
    epsilon_g_m: float
    control_period_s: float
    velocity_epsilon_rad_s: float
    e1_semantics_revision: str
    demand_floor_nm: float
    capacity_floor_nm: float

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "V24P2ForceBoundaryConfig":
        enabled = config.get("a2_v24_force_boundary_enabled", False)
        if not isinstance(enabled, bool):
            raise TypeError("env.config.a2_v24_force_boundary_enabled must be bool.")
        if not enabled:
            return cls(
                enabled=False,
                mode="DISABLED",
                checkpoint=CHECKPOINT_PATH,
                checkpoint_load_mode=CHECKPOINT_LOAD_MODE,
                panel_mass_kg=120.0,
                panel_width_m=0.95,
                panel_height_m=2.05,
                handle_height_m=0.975,
                handle_width_m=0.12,
                opening_lr="right",
                opening_io="out",
                hinge_axis_local=(0.0, 0.0, 1.0),
                theta_ref_rad=0.0,
                inertia_kg_m2=36.1,
                damping_nm_s_per_rad=50.0,
                stiffness_nm_per_rad=6.0,
                static_friction_nm=0.0,
                dynamic_friction_nm=0.0,
                viscous_friction_nm_s_per_rad=0.0,
                arm_caps_nm=PRIMARY_CAPS_NM,
                contingency_cap_nm=CONTINGENCY_CAP_NM,
                active_cap_nm=PRIMARY_CAPS_NM[0],
                friction_profile="F00",
                runtime_mode="HI_FULL",
                seed=24021,
                scenario_ids=tuple(f"S{i:02d}" for i in range(16)),
                continuity_id="CALIBRATION",
                runtime_export_path="",
                epsilon_g_m=EPS_G_M,
                control_period_s=CONTROL_PERIOD_S,
                velocity_epsilon_rad_s=VELOCITY_EPSILON_RAD_S,
                e1_semantics_revision="R12_LEGACY",
                demand_floor_nm=0.0,
                capacity_floor_nm=0.0,
            )

        def required(name: str) -> Any:
            if name not in config:
                raise ValueError(f"enabled P2 force boundary requires env.config.{name}.")
            return config[name]

        mode = required("a2_v24_force_boundary_mode")
        if not isinstance(mode, str) or mode not in {"P2_TELEMETRY", "P2_PLAN"}:
            raise ValueError("a2_v24_force_boundary_mode must be P2_TELEMETRY or P2_PLAN.")
        checkpoint = required("a2_v24_force_boundary_checkpoint")
        if checkpoint != CHECKPOINT_PATH:
            raise ValueError("P2 checkpoint path is frozen to the selected v23 G7 step1500 checkpoint.")
        load_mode = required("a2_v24_force_boundary_checkpoint_load_mode")
        if load_mode != CHECKPOINT_LOAD_MODE:
            raise ValueError("P2 checkpoint load mode must be selected_policy_only.")

        numeric = {
            "panel_mass_kg": _finite_nonnegative(required("a2_v24_force_boundary_panel_mass_kg"), name="panel_mass_kg"),
            "panel_width_m": _finite_nonnegative(required("a2_v24_force_boundary_panel_width_m"), name="panel_width_m"),
            "panel_height_m": _finite_nonnegative(required("a2_v24_force_boundary_panel_height_m"), name="panel_height_m"),
            "handle_height_m": _finite_nonnegative(required("a2_v24_force_boundary_handle_height_m"), name="handle_height_m"),
            "handle_width_m": _finite_nonnegative(required("a2_v24_force_boundary_handle_width_m"), name="handle_width_m"),
            "theta_ref_rad": float(required("a2_v24_force_boundary_theta_ref_rad")),
            "inertia_kg_m2": _finite_nonnegative(required("a2_v24_force_boundary_inertia_kg_m2"), name="inertia_kg_m2"),
            "damping_nm_s_per_rad": _finite_nonnegative(required("a2_v24_force_boundary_damping_nm_s_per_rad"), name="damping_nm_s_per_rad"),
            "stiffness_nm_per_rad": _finite_nonnegative(required("a2_v24_force_boundary_stiffness_nm_per_rad"), name="stiffness_nm_per_rad"),
            "static_friction_nm": _finite_nonnegative(required("a2_v24_force_boundary_static_friction_nm"), name="static_friction_nm"),
            "dynamic_friction_nm": _finite_nonnegative(required("a2_v24_force_boundary_dynamic_friction_nm"), name="dynamic_friction_nm"),
            "viscous_friction_nm_s_per_rad": _finite_nonnegative(required("a2_v24_force_boundary_viscous_friction_nm_s_per_rad"), name="viscous_friction_nm_s_per_rad"),
            "epsilon_g_m": _finite_nonnegative(required("a2_v24_force_boundary_epsilon_g_m"), name="epsilon_g_m"),
            "control_period_s": _finite_nonnegative(required("a2_v24_force_boundary_control_period_s"), name="control_period_s"),
            "velocity_epsilon_rad_s": _finite_nonnegative(required("a2_v24_force_boundary_velocity_epsilon_rad_s"), name="velocity_epsilon_rad_s"),
        }
        if numeric["panel_mass_kg"] != 120.0 or numeric["panel_width_m"] != 0.95 or numeric["panel_height_m"] != 2.05:
            raise ValueError("P2 canonical panel geometry is frozen to 120 kg, 0.95 m x 2.05 m.")
        if numeric["handle_height_m"] != 0.975 or numeric["handle_width_m"] != 0.12:
            raise ValueError("P2 canonical handle geometry is frozen to 0.975 m x 0.12 m.")
        if numeric["theta_ref_rad"] != 0.0 or numeric["inertia_kg_m2"] != 36.1:
            raise ValueError("P2 theta_ref and modeled inertia are frozen to 0 rad and 36.1 kg*m^2.")
        if numeric["damping_nm_s_per_rad"] != 50.0 or numeric["stiffness_nm_per_rad"] != 6.0:
            raise ValueError("P2 modeled door damping/stiffness are frozen to 50 and 6.")
        opening_lr = required("a2_v24_force_boundary_opening_lr")
        opening_io = required("a2_v24_force_boundary_opening_io")
        if opening_lr != "right" or opening_io != "out":
            raise ValueError("P2 opening semantics are frozen to right/out.")
        hinge_axis_local = required("a2_v24_force_boundary_hinge_axis_local")
        if tuple(hinge_axis_local) != (0.0, 0.0, 1.0):
            raise ValueError("P2 hinge local axis is frozen to +Z.")
        static = numeric["static_friction_nm"]
        dynamic = numeric["dynamic_friction_nm"]
        if dynamic > static:
            raise ValueError("P2 dynamic friction must be <= static friction.")
        caps = tuple(float(value) for value in required("a2_v24_force_boundary_primary_caps_nm"))
        if caps != PRIMARY_CAPS_NM:
            raise ValueError("P2 primary arm caps are frozen to [100, 60, 40, 30, 25, 20] Nm.")
        contingency = float(required("a2_v24_force_boundary_contingency_cap_nm"))
        if contingency != CONTINGENCY_CAP_NM:
            raise ValueError("P2 contingency arm cap is frozen to 10 Nm.")
        active_cap = float(config.get("a2_v24_force_boundary_active_cap_nm", caps[0]))
        if active_cap not in (*caps, contingency):
            raise ValueError("P2 active cap must be one of the registered primary/contingency caps.")
        friction_profile = config.get("a2_v24_force_boundary_friction_profile")
        if friction_profile not in REGISTERED_FRICTION_PROFILES:
            raise ValueError(f"P2 friction profile must be one of {tuple(REGISTERED_FRICTION_PROFILES)!r}.")
        expected_friction = REGISTERED_FRICTION_PROFILES[friction_profile]
        if (numeric["static_friction_nm"], numeric["dynamic_friction_nm"], numeric["viscous_friction_nm_s_per_rad"]) != expected_friction:
            raise ValueError("P2 friction coefficients must match the selected registered profile.")
        e1_semantics_revision = config.get("a2_v24_force_boundary_e1_semantics_revision", "R12_LEGACY")
        if e1_semantics_revision not in {"R12_LEGACY", R13_E1_SEMANTICS_REVISION}:
            raise ValueError("P2 E1 semantics revision is unsupported.")
        if e1_semantics_revision == R13_E1_SEMANTICS_REVISION:
            demand_floor_nm = _finite_nonnegative(required("a2_v24_force_boundary_demand_floor_nm"), name="demand_floor_nm")
            capacity_floor_nm = _finite_nonnegative(required("a2_v24_force_boundary_capacity_floor_nm"), name="capacity_floor_nm")
            if demand_floor_nm != 2.0 or capacity_floor_nm != 2.0:
                raise ValueError("r13 E1 demand/capacity floors are frozen to 2 N*m.")
        else:
            demand_floor_nm = 0.0
            capacity_floor_nm = 0.0
        runtime_mode = config.get("a2_v24_force_boundary_runtime_mode")
        if runtime_mode not in RUNTIME_MODES:
            raise ValueError(f"P2 runtime mode must be one of {RUNTIME_MODES!r}.")
        seed = config.get("a2_v24_force_boundary_seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise TypeError("P2 runtime seed must be a non-negative integer.")
        scenario_ids_raw = config.get("a2_v24_force_boundary_scenario_ids")
        if isinstance(scenario_ids_raw, (str, bytes)) or not isinstance(scenario_ids_raw, SequenceABC) or not scenario_ids_raw or any(not isinstance(item, str) or not item for item in scenario_ids_raw):
            raise TypeError("P2 scenario ids must be a non-empty sequence of strings.")
        continuity_id = config.get("a2_v24_force_boundary_continuity_id")
        if not isinstance(continuity_id, str) or not continuity_id:
            raise TypeError("P2 continuity id must be a non-empty string.")
        runtime_export_path = config.get("a2_v24_force_boundary_runtime_export_path")
        if not isinstance(runtime_export_path, str) or not runtime_export_path:
            raise ValueError("enabled P2 requires a runtime_export_path.")
        if numeric["epsilon_g_m"] != EPS_G_M:
            raise ValueError("P2 epsilon_g_m is frozen to 1e-6 m.")
        if numeric["control_period_s"] != CONTROL_PERIOD_S:
            raise ValueError("P2 control period is frozen to dt 0.005 s x decimation 4 = 0.02 s.")
        if numeric["velocity_epsilon_rad_s"] != VELOCITY_EPSILON_RAD_S:
            raise ValueError("P2 velocity epsilon is frozen to 0.001 rad/s.")
        return cls(
            enabled=True,
            mode=mode,
            checkpoint=checkpoint,
            checkpoint_load_mode=load_mode,
            panel_mass_kg=numeric["panel_mass_kg"],
            panel_width_m=numeric["panel_width_m"],
            panel_height_m=numeric["panel_height_m"],
            handle_height_m=numeric["handle_height_m"],
            handle_width_m=numeric["handle_width_m"],
            opening_lr=opening_lr,
            opening_io=opening_io,
            hinge_axis_local=tuple(float(v) for v in hinge_axis_local),
            theta_ref_rad=numeric["theta_ref_rad"],
            inertia_kg_m2=numeric["inertia_kg_m2"],
            damping_nm_s_per_rad=numeric["damping_nm_s_per_rad"],
            stiffness_nm_per_rad=numeric["stiffness_nm_per_rad"],
            static_friction_nm=numeric["static_friction_nm"],
            dynamic_friction_nm=numeric["dynamic_friction_nm"],
            viscous_friction_nm_s_per_rad=numeric["viscous_friction_nm_s_per_rad"],
            arm_caps_nm=caps,
            contingency_cap_nm=contingency,
            active_cap_nm=active_cap,
            friction_profile=friction_profile,
            runtime_mode=runtime_mode,
            seed=seed,
            scenario_ids=tuple(scenario_ids_raw),
            continuity_id=continuity_id,
            runtime_export_path=runtime_export_path,
            epsilon_g_m=numeric["epsilon_g_m"],
            control_period_s=numeric["control_period_s"],
            velocity_epsilon_rad_s=numeric["velocity_epsilon_rad_s"],
            e1_semantics_revision=e1_semantics_revision,
            demand_floor_nm=demand_floor_nm,
            capacity_floor_nm=capacity_floor_nm,
        )


def _skew(vector: torch.Tensor) -> torch.Tensor:
    x, y, z = vector.unbind(dim=-1)
    zero = torch.zeros_like(x)
    return torch.stack(
        (
            torch.stack((zero, -z, y), dim=-1),
            torch.stack((z, zero, -x), dim=-1),
            torch.stack((-y, x, zero), dim=-1),
        ),
        dim=-2,
    )


def _quat_apply_wxyz(quat_w: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
    q_xyz = quat_w[..., 1:]
    q_w = quat_w[..., :1]
    uv = torch.cross(q_xyz, vector, dim=-1)
    uuv = torch.cross(q_xyz, uv, dim=-1)
    return vector + 2.0 * (q_w * uv + uuv)


def build_hinge_geometry(
    door_root_pos_w: torch.Tensor,
    door_root_quat_w: torch.Tensor,
    door_width_m: torch.Tensor,
    door_open_lr: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return the world hinge axis and anchor from the frozen door geometry."""

    root_pos = _finite_tensor(door_root_pos_w, name="door_root_pos_w", ndim=2)
    root_quat = _finite_tensor(door_root_quat_w, name="door_root_quat_w", ndim=2)
    width = _finite_tensor(door_width_m, name="door_width_m", ndim=1)
    opening = _finite_tensor(door_open_lr, name="door_open_lr", ndim=1)
    if root_pos.shape[1] != 3 or root_quat.shape[1] != 4:
        raise ValueError("door root pose tensors must have shape (N,3)/(N,4).")
    if width.shape != opening.shape or width.shape[0] != root_pos.shape[0]:
        raise ValueError("door geometry vectors must share the environment batch.")
    if root_pos.device != root_quat.device or width.device != root_pos.device or opening.device != root_pos.device:
        raise ValueError("door geometry tensors must share device.")
    if torch.any(width <= 0.0) or torch.any(torch.abs(opening) != 1.0):
        raise ValueError("door width must be positive and door_open_lr must be exactly +/-1.")
    quat_norm = torch.linalg.vector_norm(root_quat, dim=-1, keepdim=True)
    if torch.any(quat_norm <= torch.finfo(root_quat.dtype).eps):
        raise ValueError("door root quaternion is degenerate.")
    quat_unit = root_quat / quat_norm
    local_hinge = torch.stack(
        (
            torch.full_like(width, 0.02),
            -0.5 * width * opening,
            torch.zeros_like(width),
        ),
        dim=-1,
    )
    local_axis = torch.zeros_like(root_pos)
    local_axis[:, 2] = 1.0
    hinge_pos = root_pos + _quat_apply_wxyz(quat_unit, local_hinge)
    hinge_axis = (-opening[:, None]) * _quat_apply_wxyz(quat_unit, local_axis)
    return hinge_axis, hinge_pos


def directional_handle_kinematics(
    jacobian_w: torch.Tensor,
    body_com_position_w: torch.Tensor,
    handle_position_w: torch.Tensor,
    hinge_axis_w: torch.Tensor,
    hinge_position_w: torch.Tensor,
    *,
    arm_joint_ids: Sequence[int],
    epsilon_g_m: float = EPS_G_M,
) -> dict[str, torch.Tensor]:
    """Build the corrected handle Jacobian and opening-direction coefficients."""

    jac = _finite_tensor(jacobian_w, name="jacobian_w", ndim=3)
    body = _finite_tensor(body_com_position_w, name="body_com_position_w", ndim=2)
    handle = _finite_tensor(handle_position_w, name="handle_position_w", ndim=2)
    axis = _finite_tensor(hinge_axis_w, name="hinge_axis_w", ndim=2)
    hinge = _finite_tensor(hinge_position_w, name="hinge_position_w", ndim=2)
    if jac.shape[1] != 6:
        raise ValueError(f"jacobian_w must have shape (N,6,D); got {tuple(jac.shape)}.")
    batch = int(jac.shape[0])
    for name, value in (("body_com_position_w", body), ("handle_position_w", handle), ("hinge_axis_w", axis), ("hinge_position_w", hinge)):
        if tuple(value.shape) != (batch, 3):
            raise ValueError(f"{name} must have shape ({batch},3); got {tuple(value.shape)}.")
        if value.device != jac.device or value.dtype != jac.dtype:
            raise ValueError(f"{name} must share dtype and device with jacobian_w.")
    if isinstance(epsilon_g_m, bool) or not isinstance(epsilon_g_m, Real) or not math.isfinite(float(epsilon_g_m)) or float(epsilon_g_m) <= 0.0:
        raise ValueError("epsilon_g_m must be finite and positive.")
    if len(arm_joint_ids) != 6 or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in arm_joint_ids):
        raise ValueError("arm_joint_ids must contain six non-negative articulation indices.")
    if len(set(arm_joint_ids)) != 6:
        raise ValueError("arm_joint_ids must be unique and preserve articulation order.")
    jacobian_joint_ids = [int(item) + 6 for item in arm_joint_ids]
    if max(jacobian_joint_ids) >= jac.shape[2]:
        raise ValueError("floating-base Jacobian does not contain every arm articulation column +6.")
    selected_ids = torch.tensor(jacobian_joint_ids, dtype=torch.long, device=jac.device)
    jacobian_raw = jac.index_select(2, selected_ids)
    if tuple(jacobian_raw.shape) != (batch, 6, 6):
        raise ValueError(f"selected raw Jacobian must have shape ({batch},6,6); got {tuple(jacobian_raw.shape)}.")
    r_bh = handle - body
    jacobian_linear = jacobian_raw[:, :3, :] - torch.bmm(_skew(r_bh), jacobian_raw[:, 3:, :])
    axis_norm = torch.linalg.vector_norm(axis, dim=-1, keepdim=True)
    axis_valid = axis_norm > torch.finfo(axis.dtype).eps
    axis_unit = axis / torch.where(axis_valid, axis_norm, torch.ones_like(axis_norm))
    handle_radius = handle - hinge
    radial = handle_radius - axis_unit * torch.sum(axis_unit * handle_radius, dim=-1, keepdim=True)
    radius_m = torch.linalg.vector_norm(radial, dim=-1)
    radius_valid = radius_m > torch.finfo(axis.dtype).eps
    tangent_raw = torch.cross(
        axis_unit,
        radial / torch.where(radius_valid, radius_m, torch.ones_like(radius_m))[:, None],
        dim=-1,
    )
    tangent_norm = torch.linalg.vector_norm(tangent_raw, dim=-1, keepdim=True)
    tangent_valid = tangent_norm > torch.finfo(axis.dtype).eps
    tangent_w = tangent_raw / torch.where(tangent_valid, tangent_norm, torch.ones_like(tangent_norm))
    g_i = torch.einsum("ni,nij->nj", tangent_w, jacobian_linear)
    if not torch.all(torch.isfinite(g_i)) or not torch.all(torch.isfinite(tangent_w)):
        raise ValueError("directional handle Jacobian is non-finite.")
    return {
        "jacobian_raw": jacobian_raw,
        "jacobian_linear_corrected": jacobian_linear,
        "r_bh_w": r_bh,
        "tangent_w": tangent_w,
        "radius_m": radius_m,
        "axis_valid": axis_valid.squeeze(-1),
        "radius_valid": radius_valid,
        "tangent_valid": tangent_valid.squeeze(-1),
        "g_i": g_i,
        "jacobian_joint_ids": selected_ids,
    }


def compute_directional_capacity(
    jacobian_w: torch.Tensor,
    gravity_nm: torch.Tensor,
    effort_limit_nm: torch.Tensor,
    joint_pos: torch.Tensor,
    joint_vel: torch.Tensor,
    joint_pos_target: torch.Tensor,
    joint_stiffness: torch.Tensor,
    joint_damping: torch.Tensor,
    body_com_position_w: torch.Tensor,
    handle_position_w: torch.Tensor,
    hinge_axis_w: torch.Tensor,
    hinge_position_w: torch.Tensor,
    *,
    arm_joint_ids: Sequence[int],
    epsilon_g_m: float = EPS_G_M,
    tau_required_nm: torch.Tensor | None = None,
    tau_required_valid: torch.Tensor | None = None,
    capacity_floor_nm: float | None = None,
) -> dict[str, Any]:
    """Estimate directional force/torque capacity from implicit PD margins."""

    gravity = _finite_tensor(gravity_nm, name="gravity_nm", ndim=2)
    limits = _finite_tensor(effort_limit_nm, name="effort_limit_nm", ndim=2)
    q = _finite_tensor(joint_pos, name="joint_pos", ndim=2)
    qdot = _finite_tensor(joint_vel, name="joint_vel", ndim=2)
    q_target = _finite_tensor(joint_pos_target, name="joint_pos_target", ndim=2)
    kp = _finite_tensor(joint_stiffness, name="joint_stiffness", ndim=2)
    kd = _finite_tensor(joint_damping, name="joint_damping", ndim=2)
    _same_batch((gravity, limits, q, qdot, q_target, kp, kd), width=6, label="joint tensors")
    if torch.any(limits <= 0.0):
        raise ValueError("effort limits must be finite and positive.")
    kin = directional_handle_kinematics(
        jacobian_w,
        body_com_position_w,
        handle_position_w,
        hinge_axis_w,
        hinge_position_w,
        arm_joint_ids=arm_joint_ids,
        epsilon_g_m=epsilon_g_m,
    )
    g_i = kin["g_i"]
    if g_i.shape[0] != gravity.shape[0] or g_i.device != gravity.device or g_i.dtype != gravity.dtype:
        raise ValueError("directional coefficients and joint tensors must share batch, dtype, and device.")
    b_i = gravity + kp * (q_target - q) - kd * qdot
    margin_preclip_i = limits - torch.sign(g_i) * b_i
    margin_i = torch.clamp_min(margin_preclip_i, 0.0)
    active = torch.abs(g_i) > float(epsilon_g_m)
    load_bearing = active & (b_i * g_i > 0.0)
    directional_clipped = load_bearing & (torch.abs(b_i) > limits)
    ratio = torch.where(active, margin_i / torch.abs(g_i), torch.full_like(g_i, float("inf")))
    fmax_raw = torch.amin(ratio, dim=-1)
    has_active = torch.any(active, dim=-1)
    load_bearing_count = load_bearing.sum(dim=-1)
    has_load_bearing = load_bearing_count > 0
    exhausted_margin = torch.any(active & (margin_preclip_i < 0.0), dim=-1)
    radius_valid = kin["radius_valid"] & kin["axis_valid"] & kin["tangent_valid"]
    valid = has_active & has_load_bearing & radius_valid & torch.isfinite(fmax_raw)
    fmax_n = torch.where(valid, fmax_raw, torch.full_like(fmax_raw, float("nan")))
    tau_available_nm = kin["radius_m"] * fmax_n
    utilization_ratio = torch.where(
        load_bearing,
        torch.abs(b_i) / limits,
        torch.full_like(b_i, float("-inf")),
    )
    utilization = torch.amax(utilization_ratio, dim=-1)
    utilization = torch.where(has_load_bearing, utilization, torch.full_like(utilization, float("nan")))
    directional_clip_fraction = torch.where(
        load_bearing_count > 0,
        directional_clipped.sum(dim=-1).to(dtype=b_i.dtype) / load_bearing_count.to(dtype=b_i.dtype),
        torch.full_like(load_bearing_count, float("nan"), dtype=b_i.dtype),
    )
    status_by_sample: list[str] = []
    for index in range(g_i.shape[0]):
        if not bool(radius_valid[index].item()):
            status_by_sample.append("INVALID_RADIUS")
        elif not bool(has_load_bearing[index].item()):
            status_by_sample.append("INVALID_NO_LOAD_BEARING")
        elif not bool(has_active[index].item()):
            status_by_sample.append("INVALID_NO_ACTIVE_JOINT")
        elif bool(exhausted_margin[index].item()):
            status_by_sample.append("VALID_ZERO_MARGIN_DIRECTIONAL_CLIP")
        else:
            status_by_sample.append("VALID")
    result: dict[str, Any] = {
        **kin,
        "gravity_nm": gravity,
        "effort_limit_nm": limits,
        "joint_pos": q,
        "joint_vel": qdot,
        "joint_pos_target": q_target,
        "joint_stiffness": kp,
        "joint_damping": kd,
        "pd_command_estimate_nm": b_i,
        "joint_margin_nm": margin_i,
        "joint_margin_preclip_nm": margin_preclip_i,
        "active_relevant_joints": active,
        "load_bearing_joints": load_bearing,
        "directional_clipped_joints": directional_clipped,
        "fmax_directional_n": fmax_n,
        "fmax_directional_raw_n": fmax_raw,
        "capacity_valid": valid,
        "tau_available_directional_nm": tau_available_nm,
        "directional_load_utilization": utilization,
        "directional_load_utilization_ratio": utilization_ratio,
        "has_load_bearing": has_load_bearing,
        "directional_clip_fraction": directional_clip_fraction,
        "status_by_sample": status_by_sample,
        "authority": {
            "capacity_lambda": MARGIN_AUTHORITY,
            "pd_command": PD_AUTHORITY,
            "gravity": GRAVITY_AUTHORITY,
            "state": STATE_AUTHORITY,
            "actual_generalized_torque": ACTUAL_TORQUE_AUTHORITY,
        },
        "units": {"g": "m/rad", "force": "N", "torque": "N*m", "lambda": "1"},
    }
    if tau_required_nm is not None:
        if tau_required_valid is None:
            lambda_valid_mask = valid
        else:
            if (
                not torch.is_tensor(tau_required_valid)
                or tau_required_valid.shape != valid.shape
                or tau_required_valid.dtype != torch.bool
                or tau_required_valid.device != valid.device
            ):
                raise TypeError("valid_mask must be a device-local bool tensor matching torque shape.")
            lambda_valid_mask = valid & tau_required_valid
        result.update(
            compute_lambda(
                tau_required_nm,
                tau_available_nm,
                valid_mask=lambda_valid_mask,
                denominator_floor_nm=capacity_floor_nm,
            )
        )
    return result


def compute_lambda(
    tau_required_nm: torch.Tensor,
    tau_available_nm: torch.Tensor,
    *,
    valid_mask: torch.Tensor | None = None,
    denominator_floor_nm: float | None = None,
) -> dict[str, torch.Tensor]:
    if not torch.is_tensor(tau_required_nm) or tau_required_nm.ndim != 1 or not tau_required_nm.is_floating_point():
        raise TypeError("tau_required_nm must be a floating tensor with ndim=1.")
    required = tau_required_nm
    if not torch.is_tensor(tau_available_nm) or tau_available_nm.ndim != 1 or not tau_available_nm.is_floating_point():
        raise TypeError("tau_available_nm must be a floating tensor with ndim=1.")
    available = tau_available_nm
    if required.shape != available.shape or required.device != available.device or required.dtype != available.dtype:
        raise ValueError("tau_required_nm and tau_available_nm must share shape, dtype, and device.")
    if valid_mask is None:
        valid = torch.ones_like(available, dtype=torch.bool)
    else:
        if not torch.is_tensor(valid_mask) or valid_mask.shape != available.shape or valid_mask.dtype != torch.bool or valid_mask.device != available.device:
            raise TypeError("valid_mask must be a device-local bool tensor matching torque shape.")
        valid = valid_mask
    finite_required = torch.isfinite(required)
    finite_available = torch.isfinite(available)
    if torch.any(valid & (~finite_required | ~finite_available)):
        raise ValueError("tau_required_nm must be finite wherever valid_mask is true.")
    valid = valid & (available >= 0.0)
    if denominator_floor_nm is None:
        denominator = available + torch.full_like(available, 1.0e-6)
        capacity_collapsed = torch.zeros_like(valid)
    else:
        if isinstance(denominator_floor_nm, bool) or not isinstance(denominator_floor_nm, Real) or not math.isfinite(float(denominator_floor_nm)) or float(denominator_floor_nm) <= 0.0:
            raise ValueError("denominator_floor_nm must be finite and positive when supplied.")
        denominator = available
        capacity_collapsed = valid & (available < float(denominator_floor_nm))
        valid = valid & ~capacity_collapsed
    values = torch.where(valid, required / denominator, torch.full_like(required, float("nan")))
    return {
        "lambda_load": values,
        "lambda_denominator_nm": denominator,
        "lambda_valid": valid,
        "capacity_collapsed": capacity_collapsed,
    }


def compute_door_required_torque(
    theta_rad: torch.Tensor,
    omega_rad_s: torch.Tensor,
    alpha_rad_s2: torch.Tensor | None,
    *,
    inertia_kg_m2: float,
    damping_nm_s_per_rad: float,
    stiffness_nm_per_rad: float,
    theta_ref_rad: float,
    static_friction_nm: float,
    dynamic_friction_nm: float,
    viscous_friction_nm_s_per_rad: float,
    opening_direction: torch.Tensor | None = None,
    friction_mode: str = "prospective",
    alpha_valid: torch.Tensor | None = None,
    velocity_epsilon_rad_s: float = VELOCITY_EPSILON_RAD_S,
) -> dict[str, Any]:
    """Model required door torque while preserving unavailable acceleration.

    ``alpha_rad_s2=None`` is intentionally represented as an unavailable
    inertia component, never as zero.  Non-positive opening slip is marked
    ``DIRECTION_EXCLUDED`` for directional boundary analysis while retaining
    the finite modeled torque as measurement evidence.
    """

    theta = _finite_tensor(theta_rad, name="theta_rad", ndim=1)
    omega = _finite_tensor(omega_rad_s, name="omega_rad_s", ndim=1)
    if theta.shape != omega.shape or theta.device != omega.device or theta.dtype != omega.dtype:
        raise ValueError("theta_rad and omega_rad_s must share shape, dtype, and device.")
    if alpha_rad_s2 is not None:
        if not torch.is_tensor(alpha_rad_s2) or alpha_rad_s2.ndim != 1 or not alpha_rad_s2.is_floating_point():
            raise TypeError("alpha_rad_s2 must be a floating tensor with ndim=1 when supplied.")
        alpha = alpha_rad_s2
        if alpha.shape != theta.shape or alpha.device != theta.device or alpha.dtype != theta.dtype:
            raise ValueError("alpha_rad_s2 must share shape, dtype, and device when supplied.")
        if alpha_valid is None:
            alpha_valid_mask = torch.ones_like(theta, dtype=torch.bool)
        else:
            if not torch.is_tensor(alpha_valid) or alpha_valid.shape != theta.shape or alpha_valid.dtype != torch.bool or alpha_valid.device != theta.device:
                raise TypeError("alpha_valid must be a device-local bool tensor matching theta_rad.")
            alpha_valid_mask = alpha_valid
        if torch.any(alpha_valid_mask & ~torch.isfinite(alpha)):
            raise ValueError("alpha_rad_s2 must be finite wherever alpha_valid is true.")
    else:
        alpha = None
        if alpha_valid is not None:
            raise ValueError("alpha_valid cannot be supplied when alpha_rad_s2 is unavailable.")
        alpha_valid_mask = torch.zeros_like(theta, dtype=torch.bool)
    if friction_mode not in {"prospective", "static", "slip"}:
        raise ValueError("friction_mode must be prospective, static, or slip.")
    inertia = _finite_nonnegative(inertia_kg_m2, name="inertia_kg_m2")
    damping = _finite_nonnegative(damping_nm_s_per_rad, name="damping_nm_s_per_rad")
    stiffness = _finite_nonnegative(stiffness_nm_per_rad, name="stiffness_nm_per_rad")
    theta_ref = float(theta_ref_rad)
    if not math.isfinite(theta_ref):
        raise ValueError("theta_ref_rad must be finite.")
    static = _finite_nonnegative(static_friction_nm, name="static_friction_nm")
    dynamic = _finite_nonnegative(dynamic_friction_nm, name="dynamic_friction_nm")
    viscous = _finite_nonnegative(viscous_friction_nm_s_per_rad, name="viscous_friction_nm_s_per_rad")
    velocity_epsilon = _finite_nonnegative(velocity_epsilon_rad_s, name="velocity_epsilon_rad_s")
    if dynamic > static:
        raise ValueError("dynamic_friction_nm must be <= static_friction_nm.")
    if opening_direction is None:
        direction = torch.ones_like(omega)
    else:
        direction = _finite_tensor(opening_direction, name="opening_direction", ndim=1)
        if direction.shape != omega.shape or direction.device != omega.device or direction.dtype != omega.dtype:
            raise ValueError("opening_direction must share shape, dtype, and device with omega_rad_s.")
        if torch.any(torch.abs(direction) != 1.0):
            raise ValueError("opening_direction must contain exactly +/-1.")
    opening_speed = direction * omega
    direction_valid = opening_speed >= 0.0
    friction = torch.full_like(theta, static)
    if friction_mode == "slip":
        positive_slip = opening_speed > velocity_epsilon
        friction = torch.where(positive_slip, torch.full_like(theta, dynamic) + viscous * opening_speed, friction)
    damping_term = damping * omega
    stiffness_term = stiffness * (theta - theta_ref)
    friction_term = friction
    if alpha is None:
        inertia_term = None
        tau_required = damping_term + stiffness_term + friction_term
        opening_direction_valid = direction_valid
        model_valid = torch.isfinite(tau_required)
        direction_valid = opening_direction_valid & torch.isfinite(tau_required) & (tau_required > 0.0)
        status = ["DIRECTION_EXCLUDED" if not bool(flag.item()) else "ALPHA_UNAVAILABLE_PROSPECTIVE" if bool(direction_valid[index].item()) else "DIRECTION_EXCLUDED" for index, flag in enumerate(opening_direction_valid)]
    else:
        inertia_term = torch.where(alpha_valid_mask, inertia * alpha, torch.full_like(alpha, float("nan")))
        modeled = inertia * torch.where(alpha_valid_mask, alpha, torch.zeros_like(alpha)) + damping_term + stiffness_term + friction_term
        modeled = torch.where(alpha_valid_mask, modeled, torch.full_like(modeled, float("nan")))
        tau_required = modeled
        opening_direction_valid = direction_valid
        model_valid = alpha_valid_mask & torch.isfinite(tau_required)
        direction_valid = opening_direction_valid & alpha_valid_mask & torch.isfinite(tau_required) & (tau_required > 0.0)
        status = [
            "DIRECTION_EXCLUDED" if not bool(opening_direction_valid[index].item())
            else "ALPHA_UNAVAILABLE" if not bool(alpha_valid_mask[index].item())
            else "DIRECTION_EXCLUDED" if not bool(direction_valid[index].item())
            else "MODELED_FROM_PARAMS"
            for index in range(theta.shape[0])
        ]
    return {
        "tau_required_nm": tau_required,
        "inertia_term_nm": inertia_term,
        "damping_term_nm": damping_term,
        "stiffness_term_nm": stiffness_term,
        "friction_term_nm": friction_term,
        "opening_speed_rad_s": opening_speed,
        "direction_valid": direction_valid,
        "opening_direction_valid": opening_direction_valid,
        "model_valid": model_valid,
        "status_by_sample": status,
        "friction_mode": friction_mode,
        "alpha_available": alpha is not None,
        "alpha_valid": alpha_valid_mask,
        "velocity_epsilon_rad_s": velocity_epsilon,
        "authority": {
            "friction": MODELED_TORQUE_AUTHORITY,
            "required_torque": MODELED_TORQUE_AUTHORITY,
            "model_torque": MODELED_TORQUE_AUTHORITY,
            "solver_applied": False,
            "actual_generalized_torque": ACTUAL_TORQUE_AUTHORITY,
        },
        "parameters": {
            "inertia_kg_m2": inertia,
            "damping_nm_s_per_rad": damping,
            "stiffness_nm_per_rad": stiffness,
            "theta_ref_rad": theta_ref,
            "static_friction_nm": static,
            "dynamic_friction_nm": dynamic,
            "viscous_friction_nm_s_per_rad": viscous,
        },
    }


def compute_foot_slip(
    normal_force_n: torch.Tensor,
    body_lin_vel_w: torch.Tensor,
    *,
    loading_fraction: float = 0.10,
) -> dict[str, Any]:
    """Compute max loaded-foot planar speed from measured force and velocity tensors."""

    force = _finite_tensor(normal_force_n, name="normal_force_n", ndim=2)
    velocity = _finite_tensor(body_lin_vel_w, name="body_lin_vel_w", ndim=3)
    if force.shape[1] != 4 or velocity.shape[:2] != force.shape or velocity.shape[2] != 3:
        raise ValueError("foot slip requires normal_force_n (N,4) and body_lin_vel_w (N,4,3).")
    if force.device != velocity.device or force.dtype != velocity.dtype:
        raise ValueError("foot slip tensors must share dtype and device.")
    fraction = _finite_nonnegative(loading_fraction, name="loading_fraction")
    if fraction <= 0.0 or fraction > 1.0:
        raise ValueError("loading_fraction must be in (0,1].")
    positive_force = torch.clamp(normal_force_n, min=0.0)
    total_force = positive_force.sum(dim=-1)
    loaded = positive_force >= (fraction * total_force[:, None])
    speed = torch.linalg.vector_norm(body_lin_vel_w[..., :2], dim=-1)
    loaded_speed = torch.where(loaded, speed, torch.full_like(speed, float("-inf")))
    has_loaded = (total_force > 0.0) & torch.any(loaded, dim=-1)
    max_speed = torch.amax(loaded_speed, dim=-1)
    max_speed = torch.where(has_loaded, max_speed, torch.full_like(max_speed, float("nan")))
    status = ["FOOT_SLIP_AVAILABLE" if bool(flag.item()) else "NO_LOADED_FOOT" for flag in has_loaded]
    return {
        "normal_force_n": force,
        "body_lin_vel_w": velocity,
        "loaded_mask": loaded,
        "loaded_force_sum_n": total_force,
        "max_loaded_planar_speed_m_s": max_speed,
        "valid": has_loaded,
        "status_by_sample": status,
        "loading_fraction": fraction,
        "authority": "MEASURED_SIMULATOR_CONTACT_FORCES_WORLD_Z_AND_HIGH_LEVEL_BODY_LINEAR_VELOCITY",
    }


def validate_floating_base_articulation_signature(robot: Any) -> dict[str, Any]:
    if getattr(robot, "is_fixed_base", None) is not False:
        raise RuntimeError("v24 P2 force boundary requires a floating-base articulation.")
    body_ids, body_names = robot.find_bodies(ARM_BODY_NAME, preserve_order=True)
    if list(body_names) != [ARM_BODY_NAME] or len(body_ids) != 1:
        raise RuntimeError(f"v24 P2 requires exactly one {ARM_BODY_NAME!r} body; got {body_names!r}.")
    joint_ids, joint_names = robot.find_joints(list(ARM_JOINT_NAMES), preserve_order=True)
    if list(joint_names) != list(ARM_JOINT_NAMES) or len(joint_ids) != 6:
        raise RuntimeError(f"v24 P2 arm joint order mismatch: {joint_names!r}.")
    return {
        "body_id": int(body_ids[0]),
        "body_name": ARM_BODY_NAME,
        "arm_joint_ids": [int(item) for item in joint_ids],
        "arm_joint_names": list(ARM_JOINT_NAMES),
        "jacobian_joint_ids": [int(item) + 6 for item in joint_ids],
        "floating_base": True,
    }


class P2RuntimeExporter:
    """Collect one completed 25-transition force window per first episode."""

    def __init__(self, path: str, *, num_envs: int, config: V24P2ForceBoundaryConfig):
        if not isinstance(path, str) or not path:
            raise ValueError("P2 runtime exporter requires a non-empty path.")
        if len(config.scenario_ids) != num_envs:
            raise ValueError(
                f"P2 scenario identity count must equal num_envs={num_envs}; got {len(config.scenario_ids)}."
            )
        self.path = Path(path).expanduser()
        if self.path.exists() or self.path.is_symlink():
            raise RuntimeError(f"P2 runtime exporter refuses to overwrite existing path: {self.path}")
        self.num_envs = int(num_envs)
        self.config = config
        self._windows: list[list[dict[str, Any]]] = [[] for _ in range(self.num_envs)]
        self._fallback_windows: list[list[dict[str, Any]] | None] = [None] * self.num_envs
        self._selected_windows: list[list[dict[str, Any]] | None] = [None] * self.num_envs
        self._rows: list[dict[str, Any] | None] = [None] * self.num_envs
        self._completed = torch.zeros(self.num_envs, dtype=torch.bool)
        self._published = False

    def record(self, rows: Sequence[Mapping[str, Any]]) -> None:
        if self._published:
            raise RuntimeError("P2 runtime exporter received rows after publication.")
        if len(rows) != self.num_envs:
            raise ValueError("P2 runtime exporter requires one row per live environment.")
        for env_id, row in enumerate(rows):
            if self._completed[env_id] or self._rows[env_id] is not None or self._selected_windows[env_id] is not None:
                continue
            if not isinstance(row, Mapping):
                raise TypeError("P2 runtime exporter row must be a mapping.")
            if row.get("authority") != {**AUTHORITY_SET, "solver_applied": False}:
                raise RuntimeError("P2 exporter received a row with incomplete/mutated authority.")
            if row.get("alpha_valid") is not True:
                self._windows[env_id] = []
                continue
            step = row.get("episode_step")
            if isinstance(step, bool) or not isinstance(step, int):
                raise RuntimeError("P2 alpha-valid exporter rows require integer episode_step values.")
            if self._windows[env_id] and step != self._windows[env_id][-1].get("episode_step", None) + 1:
                self._windows[env_id] = []
            self._windows[env_id].append(dict(row))
            if len(self._windows[env_id]) > FORCE_WINDOW_TRANSITIONS:
                self._windows[env_id] = self._windows[env_id][-FORCE_WINDOW_TRANSITIONS:]
            if len(self._windows[env_id]) < FORCE_WINDOW_TRANSITIONS:
                continue
            candidate = self._windows[env_id][-FORCE_WINDOW_TRANSITIONS:]
            if self._fallback_windows[env_id] is None:
                self._fallback_windows[env_id] = [dict(item) for item in candidate]
            if self._qualifies_stable_opening(candidate):
                self._selected_windows[env_id] = [dict(item) for item in candidate]

    @staticmethod
    def _finite_values(window: Sequence[Mapping[str, Any]], field: str) -> list[float]:
        values = [row.get(field) for row in window]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
            return []
        return [float(value) for value in values]

    @staticmethod
    def _qualifies_stable_opening(window: Sequence[Mapping[str, Any]]) -> bool:
        if len(window) != FORCE_WINDOW_TRANSITIONS:
            raise RuntimeError("P2 stable-opening selection requires exactly 25 transitions.")
        stages = [row.get("stage_buf") for row in window]
        if any(isinstance(stage, bool) or not isinstance(stage, int) for stage in stages):
            raise RuntimeError("P2 stable-opening selection requires integer stage_buf values.")
        if any(stage not in FORCE_WINDOW_OPENING_STAGES for stage in stages):
            return False
        stable_values = [row.get("stable_grasp") for row in window]
        if any(not isinstance(value, bool) for value in stable_values):
            return False
        return sum(value is True for value in stable_values) >= FORCE_WINDOW_STABLE_GRASP_MIN_COUNT

    @staticmethod
    def _aggregate_window(window: Sequence[Mapping[str, Any]], *, selection_status: str) -> dict[str, Any]:
        if len(window) != FORCE_WINDOW_TRANSITIONS:
            raise RuntimeError("P2 force-window aggregation requires exactly 25 transitions.")
        if selection_status not in {
            FORCE_WINDOW_SELECTION_STABLE_OPENING,
            FORCE_WINDOW_SELECTION_ALPHA_FALLBACK,
        }:
            raise RuntimeError(f"P2 force-window selection status is unsupported: {selection_status!r}.")
        first, last = window[0], window[-1]
        authority = first.get("authority")
        if authority != {**AUTHORITY_SET, "solver_applied": False}:
            raise RuntimeError("P2 force-window authority is incomplete or mutated.")
        if any(row.get("authority") != authority for row in window):
            raise RuntimeError("P2 force-window authority changed within a window.")
        steps = [row.get("episode_step") for row in window]
        if any(isinstance(step, bool) or not isinstance(step, int) for step in steps) or steps != list(range(steps[0], steps[0] + FORCE_WINDOW_TRANSITIONS)):
            raise RuntimeError("P2 force-window episode steps must be 25 contiguous transitions.")
        stage_values = [row.get("stage_buf") for row in window]
        if any(isinstance(stage, bool) or not isinstance(stage, int) for stage in stage_values):
            raise RuntimeError("P2 force-window stage_buf values must be integers.")
        stable_opening = P2RuntimeExporter._qualifies_stable_opening(window)
        if selection_status == FORCE_WINDOW_SELECTION_STABLE_OPENING and not stable_opening:
            raise RuntimeError("P2 selected stable-opening window no longer satisfies its selection predicate.")
        theta_pre_values = P2RuntimeExporter._finite_values(window, "theta_pre_rad")
        theta_post_values = P2RuntimeExporter._finite_values(window, "theta_post_rad")
        theta_delta_values = P2RuntimeExporter._finite_values(window, "theta_delta_rad")
        if not all(len(values) == FORCE_WINDOW_TRANSITIONS for values in (theta_pre_values, theta_post_values, theta_delta_values)):
            raise RuntimeError("P2 force-window pre/post hinge angles and deltas must remain finite.")
        for index, (theta_pre, theta_post, theta_delta) in enumerate(zip(theta_pre_values, theta_post_values, theta_delta_values)):
            if not math.isclose(theta_post - theta_pre, theta_delta, rel_tol=1.0e-6, abs_tol=1.0e-6):
                raise RuntimeError(f"P2 force-window transition delta mismatch at index={index}.")
            if index and not math.isclose(theta_pre, theta_post_values[index - 1], rel_tol=1.0e-6, abs_tol=1.0e-6):
                raise RuntimeError(f"P2 force-window transition angle chain mismatch at index={index}.")
        tau_values = P2RuntimeExporter._finite_values(window, "tau_required_nm")
        tau_available_values = P2RuntimeExporter._finite_values(window, "tau_available_directional_nm")
        lambda_values = P2RuntimeExporter._finite_values(window, "lambda_load")
        utilization_values = P2RuntimeExporter._finite_values(window, "directional_utilization")
        capacity_collapsed_values = [row.get("capacity_collapsed") for row in window]
        if any(not isinstance(value, bool) for value in capacity_collapsed_values):
            raise RuntimeError("P2 capacity-collapse typing must be explicit for every transition.")
        capacity_collapsed_count = sum(capacity_collapsed_values)
        capacity_collapsed_window = capacity_collapsed_count > 0
        clip_count = sum(bool(row.get("directional_clipped")) for row in window)
        stable_values = [row.get("stable_grasp") for row in window]
        stable_available = all(isinstance(value, bool) for value in stable_values)
        stable_count = sum(bool(value) for value in stable_values) if stable_available else None
        stable_fraction = stable_count / FORCE_WINDOW_TRANSITIONS if stable_count is not None else None
        typed_fields = ("grasp_source_unavailable", "model_source_unavailable")
        if any(not isinstance(row.get(field), bool) for row in window for field in typed_fields):
            raise RuntimeError("P2 force-window source typing must be explicit for grasp and model.")
        grasp_source_unavailable = any(row["grasp_source_unavailable"] for row in window)
        model_source_unavailable = any(row["model_source_unavailable"] for row in window)
        for row in window:
            if row["grasp_source_unavailable"] is not (row.get("stable_grasp") is None):
                raise RuntimeError("P2 force-window grasp source typing contradicts stable-grasp value.")
            model_values = (
                row.get("tau_required_nm"),
                row.get("tau_available_directional_nm"),
                row.get("directional_utilization"),
            )
            if row.get("capacity_collapsed") is not True:
                model_values = (*model_values, row.get("lambda_load"))
            model_unavailable = any(
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
                for value in model_values
            )
            if row["model_source_unavailable"] is not model_unavailable:
                raise RuntimeError("P2 force-window model source typing contradicts required numerics.")
        foot_valid = all(row.get("foot_slip_valid") is True for row in window)
        foot_values = P2RuntimeExporter._finite_values(window, "foot_slip_m_s") if foot_valid else []
        mechanics_available = (
            len(tau_values) == FORCE_WINDOW_TRANSITIONS
            and len(tau_available_values) == FORCE_WINDOW_TRANSITIONS
            and len(utilization_values) == FORCE_WINDOW_TRANSITIONS
        )
        lambda_available = len(lambda_values) == FORCE_WINDOW_TRANSITIONS
        model_source_unavailable = model_source_unavailable or not mechanics_available
        source_unavailable = grasp_source_unavailable or model_source_unavailable
        model_valid = all(row.get("mechanics_valid") is True for row in window) and mechanics_available
        demand_floor_nm = float(first.get("demand_floor_nm", 0.0))
        demand_floor_pass = len(tau_values) == FORCE_WINDOW_TRANSITIONS and median(tau_values) >= demand_floor_nm
        e1_measurement_valid = model_valid and lambda_available and not capacity_collapsed_window and demand_floor_pass
        window_selection_valid = selection_status == FORCE_WINDOW_SELECTION_STABLE_OPENING
        excluded_window_selection = not window_selection_valid
        valid = e1_measurement_valid if window_selection_valid else False
        window_selection_admission_status = (
            "ADMITTED_FIRST_STABLE_GRASP_OPENING"
            if window_selection_valid
            else "NON_ADMISSIBLE_NO_QUALIFYING_STABLE_GRASP_OPENING"
        )
        window_selection_reason = (
            FORCE_WINDOW_SELECTION_STABLE_OPENING
            if window_selection_valid
            else FORCE_WINDOW_SELECTION_ALPHA_FALLBACK
        )
        progress = sum(theta_delta_values)
        final = dict(first)
        for raw_field in (
            "episode_step",
            "theta_rad",
            "theta_pre_rad",
            "theta_post_rad",
            "theta_delta_rad",
            "tau_required_nm",
            "tau_available_directional_nm",
            "lambda_load",
            "lambda_denominator_nm",
            "directional_utilization",
            "directional_clipped",
            "foot_slip_m_s",
            "stage_buf",
        ):
            final.pop(raw_field, None)
        final.update(
            {
                "window_transition_count": FORCE_WINDOW_TRANSITIONS,
                "window_start_step": int(first["episode_step"]),
                "window_end_step": int(last["episode_step"]),
                "window_selection": selection_status,
                "window_selection_status": selection_status,
                "window_selection_valid": window_selection_valid,
                "excluded_window_selection": excluded_window_selection,
                "window_selection_admission_status": window_selection_admission_status,
                "window_selection_reason": window_selection_reason,
                "window_stable_grasp_min_count": FORCE_WINDOW_STABLE_GRASP_MIN_COUNT,
                "window_stable_grasp_count": stable_count,
                "window_opening_stages": sorted(FORCE_WINDOW_OPENING_STAGES),
                "window_stage_ids": sorted(set(stage_values)),
                "window_stage_reach_valid": all(stage in FORCE_WINDOW_OPENING_STAGES for stage in stage_values),
                "theta_start_rad": theta_pre_values[0],
                "theta_end_rad": theta_post_values[-1],
                "progress_recovery_delta_rad": progress,
                "rescue_progress_rad": None,
                "rescue_gain_rad": None,
                "tau_req_median_nm": median(tau_values) if len(tau_values) == FORCE_WINDOW_TRANSITIONS else None,
                "tau_available_directional_median_nm": median(tau_available_values) if len(tau_available_values) == FORCE_WINDOW_TRANSITIONS else None,
                "lambda_median": median(lambda_values) if len(lambda_values) == FORCE_WINDOW_TRANSITIONS else None,
                "lambda": median(lambda_values) if len(lambda_values) == FORCE_WINDOW_TRANSITIONS else None,
                "capacity_collapsed_window": capacity_collapsed_window,
                "capacity_collapsed_transition_count": capacity_collapsed_count,
                "capacity_collapsed_fraction": capacity_collapsed_count / FORCE_WINDOW_TRANSITIONS,
                "capacity_window_status": "CAPACITY_COLLAPSED_WINDOW" if capacity_collapsed_window else "CAPACITY_VALID_WINDOW",
                "demand_floor_pass": demand_floor_pass,
                "e1_admission_status": (
                    "CAPACITY_COLLAPSED_WINDOW"
                    if capacity_collapsed_window
                    else "DEMAND_BELOW_FLOOR"
                    if not demand_floor_pass
                    else "E1_MEASUREMENT_ELIGIBLE"
                    if e1_measurement_valid
                    else "MEASUREMENT_INVALID"
                ),
                "directional_utilization_median": median(utilization_values) if len(utilization_values) == FORCE_WINDOW_TRANSITIONS else None,
                "directional_clip_fraction_median": clip_count / FORCE_WINDOW_TRANSITIONS,
                "stable_grasp_fraction": stable_fraction,
                "stable_grasp": stable_count >= 20 if stable_count is not None else None,
                "max_loaded_foot_slip_m_s": max(foot_values) if len(foot_values) == FORCE_WINDOW_TRANSITIONS else None,
                "foot_slip_valid": len(foot_values) == FORCE_WINDOW_TRANSITIONS,
                "source_unavailable": "SOURCE_UNAVAILABLE" if source_unavailable else None,
                "grasp_source_unavailable": grasp_source_unavailable,
                "model_source_unavailable": model_source_unavailable,
                "source_status": {
                    "foot": "AVAILABLE",
                    "grasp": "SOURCE_UNAVAILABLE" if grasp_source_unavailable else "AVAILABLE",
                    "model": "SOURCE_UNAVAILABLE" if model_source_unavailable else "AVAILABLE",
                },
                "directional_high_effort": (
                    not model_source_unavailable
                    and len(utilization_values) == FORCE_WINDOW_TRANSITIONS
                    and median(utilization_values) >= 0.90
                    and clip_count / FORCE_WINDOW_TRANSITIONS >= 0.30
                ),
                "model_valid": model_valid,
                "valid": valid,
                "nonbinding": clip_count == 0,
                "excluded_geometry": any(row.get("excluded_geometry") is True for row in window),
                "excluded_grasp": stable_count is not None and stable_count < 20,
                "excluded_direction": any(row.get("excluded_direction") is True for row in window),
                "excluded_slip": False,
                "excluded_pathology": any(row.get("excluded_pathology") is True for row in window),
                "alpha_valid": True,
                "source_api": first["source_api"],
                "authority": authority,
            }
        )
        return final

    def mark_completed(self, env_ids: torch.Tensor) -> None:
        if not torch.is_tensor(env_ids) or env_ids.ndim != 1 or env_ids.dtype != torch.long:
            raise TypeError("P2 completed env ids must be a one-dimensional torch.long tensor.")
        for env_id in env_ids.detach().cpu().tolist():
            index = int(env_id)
            if self._rows[index] is not None:
                self._completed[index] = True
                continue
            selected = self._selected_windows[index]
            if selected is not None:
                self._rows[index] = self._aggregate_window(
                    selected,
                    selection_status=FORCE_WINDOW_SELECTION_STABLE_OPENING,
                )
            else:
                fallback = self._fallback_windows[index]
                if fallback is None or len(fallback) != FORCE_WINDOW_TRANSITIONS:
                    raise RuntimeError(
                        "P2 episode completed without a qualifying stable-opening window or a complete "
                        f"first alpha-valid fallback for env_id={index}."
                    )
                self._rows[index] = self._aggregate_window(
                    fallback,
                    selection_status=FORCE_WINDOW_SELECTION_ALPHA_FALLBACK,
                )
            self._completed[int(env_id)] = True

    def publish(self) -> None:
        if self._published:
            raise RuntimeError("P2 runtime exporter publish called more than once.")
        if not bool(torch.all(self._completed).item()):
            missing = torch.nonzero(~self._completed, as_tuple=False).flatten().tolist()
            raise RuntimeError(f"P2 runtime exporter has incomplete first episodes for env_ids={missing!r}.")
        if any(row is None for row in self._rows):
            missing = [index for index, row in enumerate(self._rows) if row is None]
            raise RuntimeError(f"P2 runtime exporter is missing rows for env_ids={missing!r}.")
        if self.path.exists() or self.path.is_symlink():
            raise RuntimeError(f"P2 runtime exporter refuses to overwrite existing path: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("x", encoding="utf-8") as handle:
            for row in self._rows:
                handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._published = True

    @property
    def published(self) -> bool:
        return self._published


def aggregate_p2_force_window(
    window: Sequence[Mapping[str, Any]],
    *,
    selection_status: str,
) -> dict[str, Any]:
    """Pure public P2 window aggregation shared by training/eval evidence.

    The implementation is the existing P2 aggregation contract expressed as a
    static operation.  It has no exporter state and therefore cannot mutate or
    overwrite the current first-episode P2 lifecycle.
    """

    return P2RuntimeExporter._aggregate_window(window, selection_status=selection_status)


class A2V24ForceBoundaryRuntime:
    """Read high-level runtime tensors and produce one P2 telemetry sample."""

    def __init__(self, robot: Any, door: Any, config: V24P2ForceBoundaryConfig, *, device: str | torch.device):
        if not config.enabled:
            raise ValueError("A2V24ForceBoundaryRuntime requires an enabled P2 config.")
        self.robot = robot
        self.door = door
        self.config = config
        self.device = torch.device(device)
        self.signature = validate_floating_base_articulation_signature(robot)
        handle_ids, handle_names = door.find_bodies(DOOR_HANDLE_NAME, preserve_order=True)
        if list(handle_names) != [DOOR_HANDLE_NAME] or len(handle_ids) != 1:
            raise RuntimeError(f"v24 P2 requires exactly one {DOOR_HANDLE_NAME!r} body; got {handle_names!r}.")
        hinge_ids, hinge_names = door.find_joints(HINGE_PATTERN, preserve_order=True)
        if len(hinge_ids) != 1 or len(hinge_names) != 1:
            raise RuntimeError(f"v24 P2 requires exactly one door hinge joint; got {hinge_names!r}.")
        self.handle_body_id = int(handle_ids[0])
        self.hinge_joint_id = int(hinge_ids[0])
        self.hinge_joint_name = str(hinge_names[0])
        foot_ids, foot_names = robot.find_bodies(list(FOOT_BODY_NAMES), preserve_order=True)
        if list(foot_names) != list(FOOT_BODY_NAMES) or len(foot_ids) != 4:
            raise RuntimeError(f"v24 P2 requires the exact ordered foot body set {FOOT_BODY_NAMES!r}; got {foot_names!r}.")
        self.robot_body_id = self.signature["body_id"]
        self.arm_joint_ids = tuple(self.signature["arm_joint_ids"])
        self.arm_joint_id_tensor = torch.tensor(self.arm_joint_ids, dtype=torch.long, device=self.device)
        gripper_joint_ids, gripper_joint_names = robot.find_joints(list(GRIPPER_JOINT_NAMES), preserve_order=True)
        if list(gripper_joint_names) != list(GRIPPER_JOINT_NAMES) or len(gripper_joint_ids) != len(GRIPPER_JOINT_NAMES):
            raise RuntimeError(f"v24 P2 requires the exact gripper joint set {GRIPPER_JOINT_NAMES!r}; got {gripper_joint_names!r}.")
        self.gripper_joint_ids = tuple(int(item) for item in gripper_joint_ids)
        self.gripper_joint_id_tensor = torch.tensor(self.gripper_joint_ids, dtype=torch.long, device=self.device)
        self.foot_body_ids = tuple(int(item) for item in foot_ids)
        joint_pos = robot.data.joint_pos
        effort_limits = robot.data.joint_effort_limits
        if not torch.is_tensor(joint_pos) or joint_pos.ndim != 2 or joint_pos.device != self.device:
            raise TypeError("P2 robot data.joint_pos must be a device-local (N,J) tensor.")
        if not torch.is_tensor(effort_limits) or effort_limits.shape != joint_pos.shape or effort_limits.device != self.device:
            raise TypeError("P2 robot data.joint_effort_limits must match joint_pos shape/device.")
        self.num_envs = int(joint_pos.shape[0])
        self.dtype = joint_pos.dtype
        self.original_effort_limits = effort_limits.detach().clone()
        self.original_gripper_effort_limits = effort_limits[:, self.gripper_joint_id_tensor].detach().clone()
        gripper_stiffness = getattr(robot.data, "joint_stiffness", None)
        gripper_damping = getattr(robot.data, "joint_damping", None)
        for field, value in (("joint_stiffness", gripper_stiffness), ("joint_damping", gripper_damping)):
            if not torch.is_tensor(value) or value.shape != joint_pos.shape or value.device != self.device:
                raise RuntimeError(f"v24 P2 requires robot.data.{field} matching joint_pos for gripper vitals.")
        self.original_gripper_stiffness = gripper_stiffness[:, self.gripper_joint_id_tensor].detach().clone()
        self.original_gripper_damping = gripper_damping[:, self.gripper_joint_id_tensor].detach().clone()
        self._validate_gripper_face(torch.arange(self.num_envs, dtype=torch.long, device=self.device), "initialization")
        door_joint_pos = door.data.joint_pos
        if not torch.is_tensor(door_joint_pos) or door_joint_pos.ndim != 2 or door_joint_pos.device != self.device:
            raise TypeError("P2 door data.joint_pos must be a device-local (N,J) tensor.")
        self.original_door_friction = {}
        self.original_door_friction_all = {}
        for field in ("joint_friction_coeff", "joint_dynamic_friction_coeff", "joint_viscous_friction_coeff"):
            value = getattr(door.data, field, None)
            if (
                not torch.is_tensor(value)
                or value.ndim != 2
                or value.shape[0] != self.num_envs
                or value.shape[1] != door_joint_pos.shape[1]
                or value.shape[1] <= self.hinge_joint_id
                or value.device != self.device
            ):
                raise RuntimeError(f"P2 requires Articulation.data.{field} for native friction readback.")
            if not value.is_floating_point() or not torch.all(torch.isfinite(value)):
                raise RuntimeError(f"P2 requires finite floating Articulation.data.{field} for native friction readback.")
            self.original_door_friction[field] = value[:, [self.hinge_joint_id]].detach().clone()
            self.original_door_friction_all[field] = value.detach().clone()
        self.door_joint_count = int(door_joint_pos.shape[1])
        self.non_hinge_joint_ids = tuple(index for index in range(self.door_joint_count) if index != self.hinge_joint_id)
        if not hasattr(door, "write_joint_friction_coefficient_to_sim"):
            raise RuntimeError("P2 requires Articulation.write_joint_friction_coefficient_to_sim for native door friction.")
        self.current_cap_nm = torch.full((self.num_envs,), float("nan"), dtype=self.dtype, device=self.device)
        self._previous_hinge_omega = torch.zeros(self.num_envs, dtype=self.dtype, device=self.device)
        self._previous_hinge_valid = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self.last_sample: dict[str, Any] | None = None
        self._previous_hinge_theta = torch.full((self.num_envs,), float("nan"), dtype=self.dtype, device=self.device)
        self._parameter_vitals_cache: list[dict[str, Any] | None] = [None] * self.num_envs
        self.exporter = P2RuntimeExporter(config.runtime_export_path, num_envs=self.num_envs, config=config)
        self._closed = False
        all_env_ids = torch.arange(self.num_envs, dtype=torch.long, device=self.device)
        self.apply_cap(float(config.active_cap_nm), all_env_ids)
        self.apply_friction(config.friction_profile, all_env_ids)

    def _normalize_env_ids(self, env_ids: torch.Tensor | None) -> torch.Tensor:
        if env_ids is None:
            return torch.arange(self.num_envs, dtype=torch.long, device=self.device)
        if not torch.is_tensor(env_ids) or env_ids.ndim != 1 or env_ids.dtype != torch.long or env_ids.device != self.device:
            raise TypeError("P2 env_ids must be a device-local one-dimensional torch.long tensor.")
        if torch.any(env_ids < 0) or torch.any(env_ids >= self.num_envs):
            raise ValueError("P2 env_ids are outside the live environment range.")
        return env_ids

    def _validate_gripper_face(self, env_ids: torch.Tensor, context: str) -> None:
        ids = self._normalize_env_ids(env_ids)
        expected_effort = torch.tensor(GRIPPER_EFFORT_LIMITS_NM, dtype=self.dtype, device=self.device).expand(ids.numel(), -1)
        expected_stiffness = torch.tensor(GRIPPER_STIFFNESS_NM_PER_RAD, dtype=self.dtype, device=self.device).expand(ids.numel(), -1)
        expected_damping = torch.tensor(GRIPPER_DAMPING_NM_S_PER_RAD, dtype=self.dtype, device=self.device).expand(ids.numel(), -1)
        current_effort = self.robot.data.joint_effort_limits[ids][:, self.gripper_joint_id_tensor]
        current_stiffness = self.robot.data.joint_stiffness[ids][:, self.gripper_joint_id_tensor]
        current_damping = self.robot.data.joint_damping[ids][:, self.gripper_joint_id_tensor]
        for name, current, expected, original in (
            ("effort limits", current_effort, expected_effort, self.original_gripper_effort_limits[ids]),
            ("stiffness", current_stiffness, expected_stiffness, self.original_gripper_stiffness[ids]),
            ("damping", current_damping, expected_damping, self.original_gripper_damping[ids]),
        ):
            if not torch.is_tensor(current) or tuple(current.shape) != tuple(expected.shape) or not torch.all(torch.isfinite(current)):
                raise RuntimeError(f"P2 gripper {name} readback is not finite with the exact expected shape during {context}.")
            if not torch.allclose(current, expected, atol=1.0e-5, rtol=0.0):
                raise RuntimeError(f"P2 gripper {name} changed from the frozen [arm_j7, arm_j8] face during {context}.")
            if not torch.allclose(current, original, atol=1.0e-5, rtol=0.0):
                raise RuntimeError(f"P2 gripper {name} changed relative to its initialization readback during {context}.")

    def _validate_non_hinge_friction_unchanged(self, env_ids: torch.Tensor, context: str) -> None:
        ids = self._normalize_env_ids(env_ids)
        if not self.non_hinge_joint_ids:
            return
        joint_ids = list(self.non_hinge_joint_ids)
        for field, original_all in self.original_door_friction_all.items():
            current = getattr(self.door.data, field)[ids][:, joint_ids]
            original = original_all[ids][:, joint_ids]
            if not torch.is_tensor(current) or not torch.all(torch.isfinite(current)):
                raise RuntimeError(f"P2 non-hinge {field} readback is not finite during {context}.")
            if not torch.allclose(current, original, atol=1.0e-6, rtol=0.0):
                raise RuntimeError(f"P2 non-hinge {field} changed during {context}.")

    @staticmethod
    def _finite_list(value: torch.Tensor, *, label: str) -> list[float]:
        if not torch.is_tensor(value) or not value.is_floating_point() or not torch.all(torch.isfinite(value)):
            raise RuntimeError(f"P2 parameter vitals {label} must be finite floating values.")
        return [float(item) for item in value.detach().cpu().reshape(-1).tolist()]

    def _build_parameter_vitals(self, env_id: int) -> dict[str, Any]:
        if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < self.num_envs:
            raise ValueError(f"P2 parameter vitals env_id must be within 0..{self.num_envs - 1}; got {env_id!r}.")
        ids = torch.tensor([env_id], dtype=torch.long, device=self.device)
        self._validate_gripper_face(ids, f"aggregate env_id={env_id}")
        self._validate_non_hinge_friction_unchanged(ids, f"aggregate env_id={env_id}")
        cap = self.current_cap_nm[env_id]
        if not torch.is_tensor(cap) or not torch.isfinite(cap):
            raise RuntimeError(f"P2 parameter vitals active arm cap is not finite for env_id={env_id}.")
        cap_value = float(cap.item())
        arm_requested = torch.full((1, len(self.arm_joint_ids)), cap_value, dtype=self.dtype, device=self.device)
        arm_readback = self.robot.data.joint_effort_limits[ids][:, self.arm_joint_id_tensor]
        if not torch.allclose(arm_readback, arm_requested, atol=1.0e-5, rtol=0.0):
            raise RuntimeError(f"P2 parameter vitals arm cap readback mismatch for env_id={env_id}.")
        static, dynamic, viscous = REGISTERED_FRICTION_PROFILES[self.config.friction_profile]
        friction_requested = {
            "static_friction_nm": float(static),
            "dynamic_friction_nm": float(dynamic),
            "viscous_friction_nm_s_per_rad": float(viscous),
        }
        friction_readback: dict[str, float] = {}
        friction_fields = {
            "static_friction_nm": "joint_friction_coeff",
            "dynamic_friction_nm": "joint_dynamic_friction_coeff",
            "viscous_friction_nm_s_per_rad": "joint_viscous_friction_coeff",
        }
        for output_name, data_field in friction_fields.items():
            value = getattr(self.door.data, data_field)[env_id, self.hinge_joint_id]
            if not torch.is_tensor(value) or not torch.isfinite(value):
                raise RuntimeError(f"P2 parameter vitals {data_field} readback is not finite for env_id={env_id}.")
            actual = float(value.item())
            if actual != friction_requested[output_name]:
                raise RuntimeError(f"P2 parameter vitals {data_field} disagrees with requested/contract value for env_id={env_id}.")
            friction_readback[output_name] = actual
        non_hinge_before = {
            field: self._finite_list(original_all[env_id, list(self.non_hinge_joint_ids)], label=f"{field}.before")
            for field, original_all in self.original_door_friction_all.items()
        }
        non_hinge_after = {
            field: self._finite_list(getattr(self.door.data, field)[env_id, list(self.non_hinge_joint_ids)], label=f"{field}.after")
            for field in self.original_door_friction_all
        }
        if non_hinge_before != non_hinge_after:
            raise RuntimeError(f"P2 parameter vitals non-hinge friction changed for env_id={env_id}.")
        gripper_effort = self._finite_list(self.robot.data.joint_effort_limits[env_id, self.gripper_joint_id_tensor], label="gripper_effort_limits")
        gripper_stiffness = self._finite_list(self.robot.data.joint_stiffness[env_id, self.gripper_joint_id_tensor], label="gripper_stiffness")
        gripper_damping = self._finite_list(self.robot.data.joint_damping[env_id, self.gripper_joint_id_tensor], label="gripper_damping")
        return {
            "schema": PARAMETER_VITALS_SCHEMA,
            "authority": MODELED_TORQUE_AUTHORITY,
            "solver_applied": False,
            "actual_generalized_torque": ACTUAL_TORQUE_AUTHORITY,
            "arm": {
                "joint_names": list(ARM_JOINT_NAMES),
                "joint_ids": list(self.arm_joint_ids),
                "registered_active_cap_nm": cap_value,
                "registered_cap_values_nm": [*self.config.arm_caps_nm, self.config.contingency_cap_nm],
                "requested_effort_limit_nm": [cap_value] * len(self.arm_joint_ids),
                "readback_effort_limit_nm": self._finite_list(arm_readback[0], label="arm_effort_limits"),
                "contract_effort_limit_nm": [cap_value] * len(self.arm_joint_ids),
                "authority": STATE_AUTHORITY,
            },
            "gripper": {
                "joint_names": list(GRIPPER_JOINT_NAMES),
                "joint_ids": list(self.gripper_joint_ids),
                "effort_limit_nm": {
                    "readback": gripper_effort,
                    "contract": list(GRIPPER_EFFORT_LIMITS_NM),
                },
                "stiffness_nm_per_rad": {
                    "readback": gripper_stiffness,
                    "contract": list(GRIPPER_STIFFNESS_NM_PER_RAD),
                },
                "damping_nm_s_per_rad": {
                    "readback": gripper_damping,
                    "contract": list(GRIPPER_DAMPING_NM_S_PER_RAD),
                },
                "swept_by_arm_cap": False,
                "unchanged_by_arm_cap": True,
            },
            "door_friction": {
                "hinge_joint_name": self.hinge_joint_name,
                "hinge_joint_id": self.hinge_joint_id,
                "requested": dict(friction_requested),
                "readback": dict(friction_readback),
                "contract": dict(friction_requested),
                "units": dict(FRICTION_UNITS),
                "authority": MODELED_TORQUE_AUTHORITY,
                "solver_applied": False,
                "actual_generalized_torque": ACTUAL_TORQUE_AUTHORITY,
                "non_hinge_joint_ids": list(self.non_hinge_joint_ids),
                "non_hinge_unchanged": True,
                "non_hinge_before": non_hinge_before,
                "non_hinge_after": non_hinge_after,
            },
            "unit_boundary": {
                "analysis_surface": "radian",
                "degree_per_radian_boundary": 57.3,
                "static_dynamic_effort_conversion_applied": False,
                "viscous_conversion_applied": False,
                "viscous_nonzero_conversion_test": "NOT_APPLICABLE_ZERO_PROFILE" if viscous == 0.0 else "DECLARED_RAD_ANALYSIS_FACE",
            },
        }

    def _get_parameter_vitals(self, env_id: int) -> dict[str, Any]:
        if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < self.num_envs:
            raise ValueError(f"P2 parameter vitals env_id must be within 0..{self.num_envs - 1}; got {env_id!r}.")
        cached = self._parameter_vitals_cache[env_id]
        if cached is None:
            cached = self._build_parameter_vitals(env_id)
            self._parameter_vitals_cache[env_id] = cached
        return cached

    def _invalidate_parameter_vitals(self, env_ids: torch.Tensor | None = None) -> None:
        ids = self._normalize_env_ids(env_ids)
        for env_id in ids.detach().cpu().tolist():
            self._parameter_vitals_cache[int(env_id)] = None

    def apply_cap(self, cap_nm: float, env_ids: torch.Tensor | None = None) -> None:
        if self._closed:
            raise RuntimeError("v24 P2 force-boundary runtime is closed.")
        cap = float(cap_nm)
        registered = (*self.config.arm_caps_nm, self.config.contingency_cap_nm)
        if cap not in registered:
            raise ValueError(f"P2 cap must be one of the registered caps {registered!r}.")
        ids = self._normalize_env_ids(env_ids)
        requested = torch.full((ids.numel(), 6), cap, dtype=self.dtype, device=self.device)
        self.robot.write_joint_effort_limit_to_sim(requested, joint_ids=list(self.arm_joint_ids), env_ids=ids)
        readback = self.robot.data.joint_effort_limits[ids][:, self.arm_joint_id_tensor]
        if tuple(readback.shape) != tuple(requested.shape) or not torch.allclose(readback, requested, atol=1.0e-5, rtol=0.0):
            raise RuntimeError("v24 P2 effort-cap write/readback mismatch.")
        self._validate_gripper_face(ids, "arm-cap application")
        self.current_cap_nm[ids] = cap
        self._invalidate_parameter_vitals(ids)

    def apply_friction(self, profile: str, env_ids: torch.Tensor | None = None) -> None:
        if profile not in REGISTERED_FRICTION_PROFILES:
            raise ValueError(f"P2 friction profile must be one of {tuple(REGISTERED_FRICTION_PROFILES)!r}.")
        ids = self._normalize_env_ids(env_ids)
        static, dynamic, viscous = REGISTERED_FRICTION_PROFILES[profile]
        requested = {
            "joint_friction_coeff": torch.full((ids.numel(), 1), static, dtype=self.dtype, device=self.device),
            "joint_dynamic_friction_coeff": torch.full((ids.numel(), 1), dynamic, dtype=self.dtype, device=self.device),
            "joint_viscous_friction_coeff": torch.full((ids.numel(), 1), viscous, dtype=self.dtype, device=self.device),
        }
        self.door.write_joint_friction_coefficient_to_sim(
            requested["joint_friction_coeff"],
            requested["joint_dynamic_friction_coeff"],
            requested["joint_viscous_friction_coeff"],
            joint_ids=[self.hinge_joint_id],
            env_ids=ids,
        )
        for field, values in requested.items():
            readback_all = getattr(self.door.data, field)
            readback = readback_all[ids][:, [self.hinge_joint_id]]
            if not torch.allclose(readback, values, atol=1.0e-6, rtol=0.0):
                raise RuntimeError(f"P2 native friction {field} write/readback mismatch.")
        self._validate_non_hinge_friction_unchanged(ids, "friction application")
        self._invalidate_parameter_vitals(ids)

    def reset_envs(self, env_ids: torch.Tensor) -> None:
        ids = self._normalize_env_ids(env_ids)
        self._previous_hinge_omega[ids] = 0.0
        self._previous_hinge_valid[ids] = False
        self._previous_hinge_theta[ids] = float("nan")
        self.last_sample = None
        original = self.original_effort_limits[ids][:, self.arm_joint_id_tensor]
        self.robot.write_joint_effort_limit_to_sim(original, joint_ids=list(self.arm_joint_ids), env_ids=ids)
        readback = self.robot.data.joint_effort_limits[ids][:, self.arm_joint_id_tensor]
        if not torch.allclose(readback, original, atol=1.0e-5, rtol=0.0):
            raise RuntimeError("v24 P2 reset failed to restore original effort limits.")
        caps = self.current_cap_nm[ids]
        if torch.any(~torch.isfinite(caps)):
            raise RuntimeError("v24 P2 reset has no current cap for a reset environment.")
        reapplied = caps[:, None].expand(-1, 6)
        self.robot.write_joint_effort_limit_to_sim(reapplied, joint_ids=list(self.arm_joint_ids), env_ids=ids)
        readback = self.robot.data.joint_effort_limits[ids][:, self.arm_joint_id_tensor]
        if not torch.allclose(readback, reapplied, atol=1.0e-5, rtol=0.0):
            raise RuntimeError("v24 P2 reset failed to reapply the current effort cap.")
        self._validate_gripper_face(ids, "reset arm-cap reapplication")
        self._invalidate_parameter_vitals(ids)
        self.door.write_joint_friction_coefficient_to_sim(
            self.original_door_friction["joint_friction_coeff"][ids],
            self.original_door_friction["joint_dynamic_friction_coeff"][ids],
            self.original_door_friction["joint_viscous_friction_coeff"][ids],
            joint_ids=[self.hinge_joint_id],
            env_ids=ids,
        )
        for field, original_all in self.original_door_friction.items():
            original = original_all[ids]
            readback = getattr(self.door.data, field)[ids][:, [self.hinge_joint_id]]
            if not torch.allclose(readback, original, atol=1.0e-6, rtol=0.0):
                raise RuntimeError(f"P2 reset failed to restore original {field}.")
        self._validate_non_hinge_friction_unchanged(ids, "reset friction restoration")
        self.apply_friction(self.config.friction_profile, ids)

    def close(self) -> None:
        if self._closed:
            return
        all_env_ids = torch.arange(self.num_envs, dtype=torch.long, device=self.device)
        original = self.original_effort_limits[:, self.arm_joint_id_tensor]
        self.robot.write_joint_effort_limit_to_sim(original, joint_ids=list(self.arm_joint_ids), env_ids=all_env_ids)
        readback = self.robot.data.joint_effort_limits[:, self.arm_joint_id_tensor]
        if not torch.allclose(readback, original, atol=1.0e-5, rtol=0.0):
            raise RuntimeError("v24 P2 close failed to restore original effort limits.")
        self._validate_gripper_face(all_env_ids, "close arm-cap restoration")
        self.door.write_joint_friction_coefficient_to_sim(
            self.original_door_friction["joint_friction_coeff"],
            self.original_door_friction["joint_dynamic_friction_coeff"],
            self.original_door_friction["joint_viscous_friction_coeff"],
            joint_ids=[self.hinge_joint_id],
            env_ids=all_env_ids,
        )
        for field, original in self.original_door_friction.items():
            readback = getattr(self.door.data, field)[:, [self.hinge_joint_id]]
            if not torch.allclose(readback, original, atol=1.0e-6, rtol=0.0):
                raise RuntimeError(f"P2 close did not restore original {field}.")
        self._validate_non_hinge_friction_unchanged(all_env_ids, "close friction restoration")
        self.exporter.publish()
        self._closed = True
        self.last_sample = None

    @staticmethod
    def _row_tensor(value: Any, env_id: int) -> Any:
        if not torch.is_tensor(value):
            return value
        item = value[env_id].detach().cpu()
        if item.ndim == 0:
            number = float(item.item())
            return number if math.isfinite(number) else None
        values = item.tolist()
        return values

    def build_export_rows(
        self,
        sample: Mapping[str, Any],
        *,
        episode_step: torch.Tensor,
        stage_buf: torch.Tensor,
        stable_grasp: torch.Tensor | None = None,
    ) -> list[dict[str, Any]]:
        if not torch.is_tensor(episode_step) or episode_step.shape != (self.num_envs,) or episode_step.dtype not in (torch.long, torch.int32, torch.int64):
            raise TypeError("P2 exporter episode_step must be a device-local (N,) integer tensor.")
        if (
            not torch.is_tensor(stage_buf)
            or stage_buf.shape != (self.num_envs,)
            or stage_buf.dtype != torch.long
            or stage_buf.device != self.device
        ):
            shape = None if not torch.is_tensor(stage_buf) else tuple(stage_buf.shape)
            dtype = None if not torch.is_tensor(stage_buf) else stage_buf.dtype
            device = None if not torch.is_tensor(stage_buf) else stage_buf.device
            raise TypeError(
                "P2 exporter stage_buf must be a device-local torch.long tensor with "
                f"shape ({self.num_envs},); got shape={shape}, dtype={dtype}, device={device}."
            )
        if episode_step.device != self.device:
            raise TypeError("P2 exporter episode_step must be a device-local integer tensor.")
        authority = sample.get("authority")
        if authority != {**AUTHORITY_SET, "solver_applied": False}:
            raise RuntimeError("P2 runtime sample authority set is incomplete or mutated.")
        required = sample["door_required_torque"]
        foot = sample["foot_slip"]
        rows: list[dict[str, Any]] = []
        theta = sample["theta_rad"]
        for env_id in range(self.num_envs):
            theta_value = float(theta[env_id].detach().cpu().item())
            if not math.isfinite(theta_value):
                raise RuntimeError(f"P2 exporter received non-finite hinge angle for env_id={env_id}.")
            theta_pre_value = self._row_tensor(sample["theta_pre_rad"], env_id)
            theta_delta_value = self._row_tensor(sample["theta_delta_rad"], env_id)
            utilization = self._row_tensor(sample["directional_load_utilization"], env_id)
            stable_value = None if stable_grasp is None else bool(stable_grasp[env_id].item())
            foot_valid = bool(foot["valid"][env_id].item())
            tau_value = self._row_tensor(sample["tau_required_nm"], env_id)
            lambda_value = self._row_tensor(sample["lambda_load"], env_id)
            tau_available_value = self._row_tensor(sample["tau_available_directional_nm"], env_id)
            lambda_denominator_value = self._row_tensor(sample["lambda_denominator_nm"], env_id)
            capacity_collapsed = bool(sample["capacity_collapsed"][env_id].item())
            mechanics_source_unavailable = any(
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
                for value in (tau_value, tau_available_value, utilization)
            )
            lambda_source_unavailable = (
                not capacity_collapsed
                and (
                    isinstance(lambda_value, bool)
                    or not isinstance(lambda_value, (int, float))
                    or not math.isfinite(float(lambda_value))
                )
            )
            model_source_unavailable = mechanics_source_unavailable or lambda_source_unavailable
            mechanics_valid = bool(sample["capacity_valid"][env_id].item()) and not mechanics_source_unavailable
            if bool(sample["alpha_valid"][env_id].item()) and (
                not isinstance(theta_pre_value, (int, float))
                or not isinstance(theta_delta_value, (int, float))
                or not math.isfinite(float(theta_pre_value))
                or not math.isfinite(float(theta_delta_value))
            ):
                raise RuntimeError(f"P2 exporter requires a finite pre/post theta delta for env_id={env_id}.")
            grasp_source_unavailable = stable_value is None
            parameter_vitals = self._get_parameter_vitals(env_id)
            row = {
                "schema": FORCE_BOUNDARY_SCHEMA + ".runtime_row",
                "seed": self.config.seed,
                "env_id": env_id,
                "scenario_id": self.config.scenario_ids[env_id],
                "episode_index": 0,
                "episode_id": f"v24-p2-env{env_id}-episode0",
                "episode_step": int(episode_step[env_id].item()),
                "stage_buf": int(stage_buf[env_id].item()),
                "profile": self.config.friction_profile,
                "mode": self.config.runtime_mode,
                "cap_nm": self.config.active_cap_nm,
                "continuity_id": self.config.continuity_id,
                "theta_rad": theta_value,
                "theta_pre_rad": theta_pre_value,
                "theta_post_rad": theta_value,
                "theta_delta_rad": theta_delta_value,
                "tau_required_nm": tau_value,
                "tau_available_directional_nm": tau_available_value,
                "lambda_load": lambda_value,
                "lambda_denominator_nm": lambda_denominator_value,
                "lambda_denominator_floor_nm": self.config.capacity_floor_nm,
                "lambda_denominator_status": (
                    "CAPACITY_COLLAPSED_BELOW_FLOOR"
                    if capacity_collapsed
                    else "VALID_ABOVE_FLOOR"
                    if self.config.e1_semantics_revision == R13_E1_SEMANTICS_REVISION
                    else "R12_LEGACY_EPSILON"
                ),
                "capacity_collapsed": capacity_collapsed,
                "directional_utilization": utilization,
                "directional_clipped": bool(sample["directional_clipped_joints"][env_id].any().item()),
                "mechanics_valid": mechanics_valid,
                "valid": mechanics_valid and (bool(sample["lambda_valid"][env_id].item()) or capacity_collapsed),
                "stable_grasp": stable_value,
                "foot_slip_m_s": self._row_tensor(foot["max_loaded_planar_speed_m_s"], env_id),
                "foot_slip_valid": foot_valid,
                "grasp_source_unavailable": grasp_source_unavailable,
                "model_source_unavailable": model_source_unavailable,
                "source_unavailable": "SOURCE_UNAVAILABLE" if (grasp_source_unavailable or model_source_unavailable) else None,
                "source_status": {
                    "foot": "AVAILABLE",
                    "grasp": "SOURCE_UNAVAILABLE" if grasp_source_unavailable else "AVAILABLE",
                    "model": "SOURCE_UNAVAILABLE" if model_source_unavailable else "AVAILABLE",
                },
                "excluded_geometry": not bool(sample["capacity_valid"][env_id].item()),
                "excluded_grasp": stable_value is False,
                "excluded_direction": not bool(required["direction_valid"][env_id].item()),
                "excluded_slip": False,
                "excluded_pathology": False,
                "alpha_valid": bool(sample["alpha_valid"][env_id].item()),
                "door_friction_profile": self.config.friction_profile,
                "e1_semantics_revision": self.config.e1_semantics_revision,
                "demand_floor_nm": self.config.demand_floor_nm,
                "capacity_floor_nm": self.config.capacity_floor_nm,
                "door_friction_parameters": {
                    "static_friction_nm": self.config.static_friction_nm,
                    "dynamic_friction_nm": self.config.dynamic_friction_nm,
                    "viscous_friction_nm_s_per_rad": self.config.viscous_friction_nm_s_per_rad,
                    "authority": MODELED_TORQUE_AUTHORITY,
                    "solver_applied": False,
                },
                "parameter_vitals": parameter_vitals,
                "authority": {**AUTHORITY_SET, "solver_applied": False},
                "actual_generalized_torque": ACTUAL_TORQUE_AUTHORITY,
                "source_api": sample["source_api"],
            }
            rows.append(row)
        return rows

    def sample(
        self,
        hinge_axis_w: torch.Tensor,
        hinge_position_w: torch.Tensor,
        *,
        opening_direction: torch.Tensor | None = None,
        foot_normal_force_n: torch.Tensor,
        foot_body_lin_vel_w: torch.Tensor,
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("v24 P2 force-boundary runtime is closed.")
        robot_data = self.robot.data
        door_data = self.door.data
        jacobians = self.robot.root_physx_view.get_jacobians()
        if not torch.is_tensor(jacobians) or jacobians.ndim != 4:
            raise RuntimeError("P2 requires Articulation.root_physx_view.get_jacobians() with shape (N,B,6,D).")
        jacobian = jacobians[:, self.robot_body_id, :, :]
        gravity_all = self.robot.root_physx_view.get_gravity_compensation_forces()
        expected_gravity_width = int(robot_data.joint_pos.shape[1]) + 6
        if not torch.is_tensor(gravity_all) or tuple(gravity_all.shape) != (self.num_envs, expected_gravity_width):
            raise RuntimeError(
                f"P2 gravity compensation must have shape ({self.num_envs},{expected_gravity_width}); "
                f"got {None if not torch.is_tensor(gravity_all) else tuple(gravity_all.shape)}."
            )
        gravity = gravity_all[:, self.arm_joint_id_tensor + 6]
        ids = self.arm_joint_ids
        handle_position = door_data.body_pos_w[:, self.handle_body_id]
        theta = door_data.joint_pos[:, self.hinge_joint_id]
        omega = door_data.joint_vel[:, self.hinge_joint_id]
        theta_pre = self._previous_hinge_theta.detach().clone()
        alpha_valid = self._previous_hinge_valid & torch.isfinite(omega)
        alpha = torch.full_like(omega, float("nan"))
        alpha[alpha_valid] = (
            omega[alpha_valid] - self._previous_hinge_omega[alpha_valid]
        ) / self.config.control_period_s
        required = compute_door_required_torque(
            theta,
            omega,
            alpha,
            alpha_valid=alpha_valid,
            inertia_kg_m2=self.config.inertia_kg_m2,
            damping_nm_s_per_rad=self.config.damping_nm_s_per_rad,
            stiffness_nm_per_rad=self.config.stiffness_nm_per_rad,
            theta_ref_rad=self.config.theta_ref_rad,
            static_friction_nm=self.config.static_friction_nm,
            dynamic_friction_nm=self.config.dynamic_friction_nm,
            viscous_friction_nm_s_per_rad=self.config.viscous_friction_nm_s_per_rad,
            opening_direction=opening_direction,
            friction_mode="slip",
            velocity_epsilon_rad_s=self.config.velocity_epsilon_rad_s,
        )
        tau_valid = required["model_valid"] & alpha_valid
        capacity = compute_directional_capacity(
            jacobian,
            gravity,
            robot_data.joint_effort_limits[:, self.arm_joint_id_tensor],
            robot_data.joint_pos[:, self.arm_joint_id_tensor],
            robot_data.joint_vel[:, self.arm_joint_id_tensor],
            robot_data.joint_pos_target[:, self.arm_joint_id_tensor],
            robot_data.joint_stiffness[:, self.arm_joint_id_tensor],
            robot_data.joint_damping[:, self.arm_joint_id_tensor],
            robot_data.body_com_pos_w[:, self.robot_body_id],
            handle_position,
            hinge_axis_w,
            hinge_position_w,
            arm_joint_ids=ids,
            epsilon_g_m=self.config.epsilon_g_m,
            tau_required_nm=required["tau_required_nm"],
            tau_required_valid=tau_valid,
            capacity_floor_nm=(
                self.config.capacity_floor_nm
                if self.config.e1_semantics_revision == R13_E1_SEMANTICS_REVISION
                else None
            ),
        )
        capacity["lambda_valid"] &= tau_valid
        capacity["lambda_load"] = torch.where(
            capacity["lambda_valid"], capacity["lambda_load"], torch.full_like(capacity["lambda_load"], float("nan"))
        )
        foot = compute_foot_slip(foot_normal_force_n, foot_body_lin_vel_w)
        capacity.update(
            {
                "theta_rad": theta,
                "theta_pre_rad": theta_pre,
                "theta_post_rad": theta,
                "theta_delta_rad": theta - theta_pre,
                "omega_rad_s": omega,
                "alpha_rad_s2": alpha,
                "alpha_valid": alpha_valid,
                "tau_required_nm": required["tau_required_nm"],
                "door_required_torque": required,
                "foot_slip": foot,
                "authority": {**AUTHORITY_SET, "solver_applied": False},
                "source_api": {
                    "jacobian": "Articulation.root_physx_view.get_jacobians()[:, body_id, :, :]",
                    "gravity": "Articulation.root_physx_view.get_gravity_compensation_forces()[:, arm_joint_ids+6]",
                    "effort_limits": "Articulation.data.joint_effort_limits[:, arm_joint_ids]",
                    "state": "Articulation.data.{joint_pos,joint_vel,joint_pos_target,joint_stiffness,joint_damping}",
                    "body_com_position": "Articulation.data.body_com_pos_w[:, body_id]",
                    "handle_position": "Articulation.data.body_pos_w[:, handle_body_id]",
                    "foot_force": "simulator.contact_forces[:, self.feet_indices, 2]",
                    "foot_velocity": "Articulation.data.body_lin_vel_w[:, foot_body_ids, :]",
                },
            }
        )
        self._previous_hinge_omega = omega.detach().clone()
        self._previous_hinge_valid = torch.isfinite(omega).detach().clone()
        self._previous_hinge_theta = theta.detach().clone()
        self.last_sample = capacity
        return capacity

    def receipt_fragment(self) -> dict[str, Any]:
        return {
            "schema": FORCE_BOUNDARY_SCHEMA,
            "body_name": ARM_BODY_NAME,
            "handle_name": DOOR_HANDLE_NAME,
            "hinge_joint_name": self.hinge_joint_name,
            "arm_joint_names": list(ARM_JOINT_NAMES),
            "foot_body_names": list(FOOT_BODY_NAMES),
            "floating_base_jacobian_offset": 6,
            "epsilon_g_m": self.config.epsilon_g_m,
            "control_period_s": self.config.control_period_s,
            "velocity_epsilon_rad_s": self.config.velocity_epsilon_rad_s,
            "active_cap_nm": self.config.active_cap_nm,
            "authority": {
                "capacity_lambda": MARGIN_AUTHORITY,
                "pd_command": PD_AUTHORITY,
                "gravity": GRAVITY_AUTHORITY,
                "state": STATE_AUTHORITY,
                "actual_generalized_torque": ACTUAL_TORQUE_AUTHORITY,
                "door_friction": MODELED_TORQUE_AUTHORITY,
                "door_model": MODELED_TORQUE_AUTHORITY,
                "solver_applied": False,
            },
        }


class A2V24F3NativeAssignmentRuntime:
    """Apply F3 assignments through IsaacLab high-level articulation APIs.

    The runtime owns only the arm effort-limit face and the door hinge friction
    face.  It records the gripper and non-hinge door properties at construction
    and rejects any drift after assignment or reset reapplication.
    """

    def __init__(self, robot: Any, door: Any, *, device: str | torch.device, num_envs: int) -> None:
        if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs <= 0:
            raise ValueError("F3 native assignment runtime requires a positive num_envs.")
        self.robot = robot
        self.door = door
        self.device = torch.device(device)
        self.num_envs = num_envs
        for target, name in ((robot, "robot"), (door, "door")):
            if not callable(getattr(target, "find_joints", None)):
                raise RuntimeError(f"F3 requires {name}.find_joints().")
        if not callable(getattr(robot, "write_joint_effort_limit_to_sim", None)):
            raise RuntimeError("F3 requires Articulation.write_joint_effort_limit_to_sim().")
        if not callable(getattr(door, "write_joint_friction_coefficient_to_sim", None)):
            raise RuntimeError("F3 requires Articulation.write_joint_friction_coefficient_to_sim().")

        arm_ids, arm_names = robot.find_joints(list(ARM_JOINT_NAMES), preserve_order=True)
        if list(arm_names) != list(ARM_JOINT_NAMES) or len(arm_ids) != len(ARM_JOINT_NAMES):
            raise RuntimeError(f"F3 arm joints must be exactly {ARM_JOINT_NAMES!r}; got {arm_names!r}.")
        gripper_ids, gripper_names = robot.find_joints(list(GRIPPER_JOINT_NAMES), preserve_order=True)
        if list(gripper_names) != list(GRIPPER_JOINT_NAMES) or len(gripper_ids) != len(GRIPPER_JOINT_NAMES):
            raise RuntimeError(f"F3 gripper joints must be exactly {GRIPPER_JOINT_NAMES!r}; got {gripper_names!r}.")
        hinge_ids, hinge_names = door.find_joints(HINGE_PATTERN, preserve_order=True)
        if len(hinge_ids) != 1:
            raise RuntimeError(f"F3 requires exactly one door hinge joint; got {hinge_names!r}.")
        self.arm_joint_ids = tuple(int(item) for item in arm_ids)
        self.gripper_joint_ids = tuple(int(item) for item in gripper_ids)
        self.hinge_joint_id = int(hinge_ids[0])

        robot_data = getattr(robot, "data", None)
        door_data = getattr(door, "data", None)
        if robot_data is None or door_data is None:
            raise RuntimeError("F3 requires robot.data and door.data readback objects.")
        joint_pos = getattr(robot_data, "joint_pos", None)
        door_joint_pos = getattr(door_data, "joint_pos", None)
        if not torch.is_tensor(joint_pos) or joint_pos.ndim != 2 or joint_pos.shape[0] != num_envs or joint_pos.device != self.device:
            raise RuntimeError("F3 robot.data.joint_pos must be device-local with shape (num_envs,joints).")
        if not torch.is_tensor(door_joint_pos) or door_joint_pos.ndim != 2 or door_joint_pos.shape[0] != num_envs or door_joint_pos.device != self.device:
            raise RuntimeError("F3 door.data.joint_pos must be device-local with shape (num_envs,joints).")
        self.dtype = joint_pos.dtype
        self.door_joint_count = int(door_joint_pos.shape[1])
        if self.hinge_joint_id >= self.door_joint_count:
            raise RuntimeError("F3 hinge joint id is outside door.data.joint_pos.")
        self.non_hinge_joint_ids = tuple(index for index in range(self.door_joint_count) if index != self.hinge_joint_id)

        effort_limits = getattr(robot_data, "joint_effort_limits", None)
        stiffness = getattr(robot_data, "joint_stiffness", None)
        damping = getattr(robot_data, "joint_damping", None)
        for name, value in (("joint_effort_limits", effort_limits), ("joint_stiffness", stiffness), ("joint_damping", damping)):
            if not torch.is_tensor(value) or value.shape != joint_pos.shape or value.device != self.device:
                raise RuntimeError(f"F3 robot.data.{name} must match joint_pos on the runtime device.")
            if not value.is_floating_point() or not torch.all(torch.isfinite(value)):
                raise RuntimeError(f"F3 robot.data.{name} must be finite floating values.")
        self.original_gripper_effort_limits = effort_limits[:, self.gripper_joint_ids].detach().clone()
        self.original_gripper_stiffness = stiffness[:, self.gripper_joint_ids].detach().clone()
        self.original_gripper_damping = damping[:, self.gripper_joint_ids].detach().clone()
        self.original_arm_effort_limits = effort_limits[:, self.arm_joint_ids].detach().clone()
        self._validate_gripper_face("initialization")

        self.original_door_friction_all: dict[str, torch.Tensor] = {}
        for field in ("joint_friction_coeff", "joint_dynamic_friction_coeff", "joint_viscous_friction_coeff"):
            value = getattr(door_data, field, None)
            if (
                not torch.is_tensor(value)
                or value.ndim != 2
                or value.shape != door_joint_pos.shape
                or value.device != self.device
                or not value.is_floating_point()
                or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(f"F3 door.data.{field} must be finite and match door joint_pos.")
            self.original_door_friction_all[field] = value.detach().clone()
        self._assignments: tuple[F3Assignment, ...] | None = None
        self._last_receipt: dict[str, Any] | None = None

    def _validate_gripper_face(self, context: str) -> None:
        robot_data = self.robot.data
        expected_effort = torch.tensor(GRIPPER_EFFORT_LIMITS_NM, dtype=self.dtype, device=self.device)
        expected_stiffness = torch.tensor(GRIPPER_STIFFNESS_NM_PER_RAD, dtype=self.dtype, device=self.device)
        expected_damping = torch.tensor(GRIPPER_DAMPING_NM_S_PER_RAD, dtype=self.dtype, device=self.device)
        current = {
            "effort_limit_nm": robot_data.joint_effort_limits[:, self.gripper_joint_ids],
            "stiffness_nm_per_rad": robot_data.joint_stiffness[:, self.gripper_joint_ids],
            "damping_nm_s_per_rad": robot_data.joint_damping[:, self.gripper_joint_ids],
        }
        expected = {
            "effort_limit_nm": expected_effort,
            "stiffness_nm_per_rad": expected_stiffness,
            "damping_nm_s_per_rad": expected_damping,
        }
        original = {
            "effort_limit_nm": self.original_gripper_effort_limits,
            "stiffness_nm_per_rad": self.original_gripper_stiffness,
            "damping_nm_s_per_rad": self.original_gripper_damping,
        }
        for name, value in current.items():
            if not torch.all(torch.isfinite(value)):
                raise RuntimeError(f"F3 gripper {name} readback is non-finite during {context}.")
            expected_value = expected[name].expand_as(value)
            if not torch.allclose(value, expected_value, atol=1.0e-5, rtol=0.0):
                raise RuntimeError(f"F3 gripper {name} differs from the frozen contract during {context}.")
            if not torch.allclose(value, original[name], atol=1.0e-5, rtol=0.0):
                raise RuntimeError(f"F3 gripper {name} changed during {context}.")

    def _validate_non_hinge_friction(self, context: str) -> None:
        if not self.non_hinge_joint_ids:
            return
        for field, original in self.original_door_friction_all.items():
            current = getattr(self.door.data, field)[:, self.non_hinge_joint_ids]
            expected = original[:, self.non_hinge_joint_ids]
            if not torch.all(torch.isfinite(current)) or not torch.allclose(current, expected, atol=1.0e-6, rtol=0.0):
                raise RuntimeError(f"F3 non-hinge {field} changed during {context}.")

    def _normalize_assignments(self, assignments: Sequence[F3Assignment]) -> tuple[F3Assignment, ...]:
        if len(assignments) != self.num_envs:
            raise ValueError(f"F3 assignment count must equal num_envs={self.num_envs}.")
        ordered = tuple(assignments)
        for env_index, assignment in enumerate(ordered):
            if not isinstance(assignment, F3Assignment) or assignment.env_index != env_index:
                raise RuntimeError("F3 assignments must be ordered by contiguous env_index.")
            if assignment.cap_nm == 10.0 or assignment.confirmed_e2:
                raise RuntimeError("F3 rejects the contingency cap10 and confirmed-E2 assignments.")
            if assignment.friction_profile not in F3_FRICTION_PARAMETERS:
                raise RuntimeError(f"F3 friction profile is unsupported: {assignment.friction_profile!r}.")
        return ordered

    def _write_groups(self, assignments: Sequence[F3Assignment], env_ids: torch.Tensor) -> None:
        if env_ids.numel() == 0:
            return
        groups: dict[tuple[float, str], list[int]] = {}
        for env_id in env_ids.detach().cpu().tolist():
            assignment = assignments[int(env_id)]
            groups.setdefault((assignment.cap_nm, assignment.friction_profile), []).append(int(env_id))
        for (cap_nm, profile), indices in groups.items():
            ids = torch.tensor(indices, dtype=torch.long, device=self.device)
            cap = torch.full((ids.numel(), len(self.arm_joint_ids)), cap_nm, dtype=self.dtype, device=self.device)
            self.robot.write_joint_effort_limit_to_sim(cap, joint_ids=list(self.arm_joint_ids), env_ids=ids)
            static, dynamic, viscous = F3_FRICTION_PARAMETERS[profile]
            shape = (ids.numel(), 1)
            self.door.write_joint_friction_coefficient_to_sim(
                torch.full(shape, static, dtype=self.dtype, device=self.device),
                torch.full(shape, dynamic, dtype=self.dtype, device=self.device),
                torch.full(shape, viscous, dtype=self.dtype, device=self.device),
                joint_ids=[self.hinge_joint_id],
                env_ids=ids,
            )
            readback_cap = self.robot.data.joint_effort_limits[ids][:, self.arm_joint_ids]
            readback_static = self.door.data.joint_friction_coeff[ids][:, [self.hinge_joint_id]]
            readback_dynamic = self.door.data.joint_dynamic_friction_coeff[ids][:, [self.hinge_joint_id]]
            readback_viscous = self.door.data.joint_viscous_friction_coeff[ids][:, [self.hinge_joint_id]]
            if not torch.allclose(readback_cap, cap, atol=1.0e-5, rtol=0.0):
                raise RuntimeError("F3 arm cap write/readback disagreed with the intended assignment.")
            expected = (static, dynamic, viscous)
            for value, expected_value in zip((readback_static, readback_dynamic, readback_viscous), expected):
                if not torch.allclose(value, torch.full_like(value, expected_value), atol=1.0e-6, rtol=0.0):
                    raise RuntimeError("F3 hinge friction write/readback disagreed with the intended assignment.")

    def _readbacks(
        self,
        assignments: Sequence[F3Assignment],
        env_ids: torch.Tensor | None = None,
    ) -> list[dict[str, Any]]:
        selected_ids = (
            list(range(self.num_envs))
            if env_ids is None
            else [int(value) for value in env_ids.detach().cpu().tolist()]
        )
        rows = []
        for env_id in selected_ids:
            assignment = assignments[env_id]
            hinge = self.hinge_joint_id
            rows.append(
                {
                    "env_index": env_id,
                    "intended_bucket": assignment.intended_bucket,
                    "friction_profile": assignment.friction_profile,
                    "cap_nm": float(self.robot.data.joint_effort_limits[env_id, self.arm_joint_ids[0]].item()),
                    "hinge_static_friction": float(self.door.data.joint_friction_coeff[env_id, hinge].item()),
                    "hinge_dynamic_friction": float(self.door.data.joint_dynamic_friction_coeff[env_id, hinge].item()),
                    "hinge_viscous_friction": float(self.door.data.joint_viscous_friction_coeff[env_id, hinge].item()),
                    "gripper_effort_limit_nm": [float(value) for value in self.robot.data.joint_effort_limits[env_id, self.gripper_joint_ids].detach().cpu().tolist()],
                    "gripper_stiffness_nm_per_rad": [float(value) for value in self.robot.data.joint_stiffness[env_id, self.gripper_joint_ids].detach().cpu().tolist()],
                    "gripper_damping_nm_s_per_rad": [float(value) for value in self.robot.data.joint_damping[env_id, self.gripper_joint_ids].detach().cpu().tolist()],
                }
            )
        return rows

    def assignment_receipt(
        self,
        assignments: Sequence[F3Assignment] | None = None,
        *,
        global_batch: int | None = None,
        full_reset_boundary: bool = False,
    ) -> dict[str, Any]:
        selected = self._assignments if assignments is None else self._normalize_assignments(assignments)
        if selected is None:
            raise RuntimeError("F3 assignment receipt requested before an assignment was applied.")
        if global_batch is None:
            global_batch = selected[0].global_batch
        self._validate_gripper_face("assignment receipt")
        self._validate_non_hinge_friction("assignment receipt")
        for env_id, assignment in enumerate(selected):
            static, dynamic, viscous = F3_FRICTION_PARAMETERS[assignment.friction_profile]
            if not torch.allclose(
                self.robot.data.joint_effort_limits[env_id, self.arm_joint_ids],
                torch.full((len(self.arm_joint_ids),), assignment.cap_nm, dtype=self.dtype, device=self.device),
                atol=1.0e-5,
                rtol=0.0,
            ):
                raise RuntimeError(f"F3 assignment receipt arm cap mismatch for env_id={env_id}.")
            current_friction = (
                self.door.data.joint_friction_coeff[env_id, self.hinge_joint_id],
                self.door.data.joint_dynamic_friction_coeff[env_id, self.hinge_joint_id],
                self.door.data.joint_viscous_friction_coeff[env_id, self.hinge_joint_id],
            )
            if any(abs(float(value.item()) - expected) > 1.0e-6 for value, expected in zip(current_friction, (static, dynamic, viscous))):
                raise RuntimeError(f"F3 assignment receipt hinge friction mismatch for env_id={env_id}.")
        return {
            "schema": "a2_piper_v24_f3_marginal_e1_assignment_receipt_v1",
            "global_batch": int(global_batch),
            "full_reset_boundary": bool(full_reset_boundary),
            "intended_assignments": [assignment.as_dict() for assignment in selected],
            "applied_parameter_readbacks": self._readbacks(selected),
            "gripper_contract": {
                "joint_names": list(GRIPPER_JOINT_NAMES),
                "effort_limit_nm": list(GRIPPER_EFFORT_LIMITS_NM),
                "stiffness_nm_per_rad": list(GRIPPER_STIFFNESS_NM_PER_RAD),
                "damping_nm_s_per_rad": list(GRIPPER_DAMPING_NM_S_PER_RAD),
                "unchanged": True,
            },
            "door_non_hinge_unchanged": True,
            "confirmed_e2": False,
            "forbidden_cap_nm": 10.0,
        }

    def apply_assignments(self, assignments: Sequence[F3Assignment], *, full_reset_boundary: bool = True) -> dict[str, Any]:
        normalized = self._normalize_assignments(assignments)
        env_ids = torch.arange(self.num_envs, dtype=torch.long, device=self.device)
        self._write_groups(normalized, env_ids)
        self._validate_gripper_face("assignment application")
        self._validate_non_hinge_friction("assignment application")
        self._assignments = normalized
        receipt = self.assignment_receipt(
            normalized,
            global_batch=normalized[0].global_batch,
            full_reset_boundary=full_reset_boundary,
        )
        self._last_receipt = copy.deepcopy(receipt)
        return receipt

    def cached_assignment_receipt(self, *, global_batch: int, full_reset_boundary: bool = False) -> dict[str, Any]:
        if self._last_receipt is None:
            raise RuntimeError("F3 cached assignment receipt requested before the first phase application.")
        receipt = copy.deepcopy(self._last_receipt)
        receipt["global_batch"] = int(global_batch)
        receipt["full_reset_boundary"] = bool(full_reset_boundary)
        for assignment in receipt["intended_assignments"]:
            assignment["global_batch"] = int(global_batch)
        return receipt

    def reset_envs(self, env_ids: torch.Tensor) -> dict[str, Any]:
        if self._assignments is None:
            raise RuntimeError("F3 reset reapplication requires a current absolute-batch assignment.")
        if not torch.is_tensor(env_ids) or env_ids.ndim != 1 or env_ids.dtype != torch.long or env_ids.device != self.device:
            raise TypeError("F3 reset env_ids must be a device-local torch.long vector.")
        if torch.any(env_ids < 0) or torch.any(env_ids >= self.num_envs):
            raise ValueError("F3 reset env_ids are outside the live environment range.")
        self._write_groups(self._assignments, env_ids)
        self._validate_gripper_face("reset reapplication")
        self._validate_non_hinge_friction("reset reapplication")
        return {
            "schema": "a2_piper_v24_f3_marginal_e1_assignment_receipt_v1",
            "global_batch": self._assignments[0].global_batch,
            "full_reset_boundary": False,
            "reset_env_ids": [int(value) for value in env_ids.detach().cpu().tolist()],
            "intended_assignments": [self._assignments[int(value)].as_dict() for value in env_ids.detach().cpu().tolist()],
            "applied_parameter_readbacks": self._readbacks(self._assignments, env_ids),
            "gripper_contract": {
                "joint_names": list(GRIPPER_JOINT_NAMES),
                "effort_limit_nm": list(GRIPPER_EFFORT_LIMITS_NM),
                "stiffness_nm_per_rad": list(GRIPPER_STIFFNESS_NM_PER_RAD),
                "damping_nm_s_per_rad": list(GRIPPER_DAMPING_NM_S_PER_RAD),
                "unchanged": True,
            },
            "door_non_hinge_unchanged": True,
            "confirmed_e2": False,
            "forbidden_cap_nm": 10.0,
        }

    def close(self) -> None:
        all_ids = torch.arange(self.num_envs, dtype=torch.long, device=self.device)
        self.robot.write_joint_effort_limit_to_sim(
            self.original_arm_effort_limits,
            joint_ids=list(self.arm_joint_ids),
            env_ids=all_ids,
        )
        for field, values in self.original_door_friction_all.items():
            if field == "joint_friction_coeff":
                static = values
            elif field == "joint_dynamic_friction_coeff":
                dynamic = values
            else:
                viscous = values
        self.door.write_joint_friction_coefficient_to_sim(
            static,
            dynamic,
            viscous,
            joint_ids=list(range(self.door_joint_count)),
            env_ids=all_ids,
        )
        self._validate_gripper_face("close")
        self._validate_non_hinge_friction("close")


__all__ = [
    "ACTUAL_TORQUE_AUTHORITY",
    "ARM_BODY_NAME",
    "ARM_JOINT_NAMES",
    "A2V24ForceBoundaryRuntime",
    "A2V24F3NativeAssignmentRuntime",
    "aggregate_p2_force_window",
    "CHECKPOINT_LOAD_MODE",
    "CHECKPOINT_PATH",
    "CONTINGENCY_CAP_NM",
    "CONTROL_PERIOD_S",
    "DOOR_HANDLE_NAME",
    "EPS_G_M",
    "FORCE_BOUNDARY_SCHEMA",
    "FORCE_WINDOW_OPENING_STAGES",
    "FORCE_WINDOW_SELECTION_ALPHA_FALLBACK",
    "FORCE_WINDOW_SELECTION_STABLE_OPENING",
    "FORCE_WINDOW_STABLE_GRASP_MIN_COUNT",
    "FORCE_WINDOW_TRANSITIONS",
    "PARAMETER_VITALS_SCHEMA",
    "GRAVITY_AUTHORITY",
    "GRIPPER_JOINT_NAMES",
    "MARGIN_AUTHORITY",
    "MODELED_TORQUE_AUTHORITY",
    "PD_AUTHORITY",
    "PRIMARY_CAPS_NM",
    "FOOT_BODY_NAMES",
    "STATE_AUTHORITY",
    "V24P2ForceBoundaryConfig",
    "build_hinge_geometry",
    "compute_directional_capacity",
    "compute_door_required_torque",
    "compute_foot_slip",
    "compute_lambda",
    "directional_handle_kinematics",
    "validate_floating_base_articulation_signature",
]
