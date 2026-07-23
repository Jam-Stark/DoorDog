# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import math
import re
from collections import Counter

import isaaclab.sim as sim_utils
import omni.usd
import torch
import torch.nn.functional as F
from loguru import logger
from isaacsim.core.simulation_manager import SimulationManager
from isaaclab.sensors import ContactSensor, ContactSensorCfg, FrameTransformer, FrameTransformerCfg
from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
from isaaclab.sensors.frame_transformer import OffsetCfg
from isaaclab.utils.math import (
    apply_delta_pose,
    axis_angle_from_quat,
    combine_frame_transforms,
    compute_pose_error,
    euler_xyz_from_quat,
    is_identity_pose,
    matrix_from_quat,
    quat_apply,
    quat_apply_inverse,
    quat_from_euler_xyz,
    quat_inv,
    quat_mul,
    subtract_frame_transforms,
    skew_symmetric_matrix,
    wrap_to_pi,
    yaw_quat,
)
from pxr import PhysxSchema, Usd, UsdPhysics
from typing_extensions import override

from gr00t.rl.envs.base_task.delta_action_base import DeltaActionBase
from gr00t.rl.envs.base_task.a2_base import A2Base
from gr00t.rl.envs.base_task.finger_primitive_base import FingerPrimitiveBase
from gr00t.rl.envs.base_task.staged_task_base import StagedTaskBase
from gr00t.rl.envs.base_task.warped_action_base import WarpedActionBase
from gr00t.rl.envs.door.reset_from_dataset import ResetFromDataset
from gr00t.rl.isaac_utils.rotations import quat_to_tan_norm, wxyz_to_xyzw, xyzw_to_wxyz
from gr00t.rl.utils.torch_utils import torch_rand_float


A2_HOLD_PHASE_WAIT_GATE = 0
A2_HOLD_PHASE_CENTER_CLOSE = 1
A2_HOLD_PHASE_DEPRESS = 2
A2_HOLD_PHASE_FOLLOW_PUSH = 3
A2_HOLD_PHASE_DONE = 4
A2_HOLD_PHASE_MATCHED_CLEAN_RELEASE_RETREAT = 5
A2_HOLD_PHASE_MATCHED_CLEAN_STABILIZE = 6
A2_HOLD_PHASE_NAMES = {
    A2_HOLD_PHASE_WAIT_GATE: "WAIT_GATE",
    A2_HOLD_PHASE_CENTER_CLOSE: "CENTER_CLOSE",
    A2_HOLD_PHASE_DEPRESS: "DEPRESS",
    A2_HOLD_PHASE_FOLLOW_PUSH: "FOLLOW_PUSH",
    A2_HOLD_PHASE_DONE: "DONE",
    A2_HOLD_PHASE_MATCHED_CLEAN_RELEASE_RETREAT: "RELEASE_RETREAT",
    A2_HOLD_PHASE_MATCHED_CLEAN_STABILIZE: "CLEAN_STABILIZE",
}
A2_HOLD_TARGET_ORIENTATION_SEMANTIC = (
    "handle_orientation_composed_with_handoff_handle_to_gripper_relative_orientation"
)
A2_HOLD_OFFSET_TARGET_ORIENTATION_SEMANTIC = (
    "captured gate source quaternion is fixed-world residual reference; placement uses "
    "Cartesian DLS; static clamp uses accumulated joint-target hold with arm raw zero"
)
A2_HOLD_MATCHED_CLEAN_TARGET_ORIENTATION_SEMANTIC = (
    "RELEASE_RETREAT uses live OrderedTargetFrameTransformer pregrasp "
    "target_quat_w[:,1,:]; CLEAN_STABILIZE uses captured accumulated joint-target "
    "hold with arm raw zero"
)
A2_HOLD_OUTCOME_NAMES = (
    "PENDING",
    "NO_GATE",
    "CENTER_NO_BILATERAL",
    "UNILATERAL_WEDGE",
    "IK_TRACKING_FAILURE",
    "IK_INVALID",
    "JOINT_LIMIT",
    "BASE_RELIEF_WRONG_SIGN",
    "BASE_RELIEF_TIMEOUT",
    "BASE_RELIEF_DISPLACEMENT_LIMIT",
    "DEPRESS_WRONG_SIGN",
    "DEPRESS_TIMEOUT",
    "CONTACT_SLIP",
    "PUSH_WRONG_SIGN",
    "PUSH_PROGRESS",
    "PUSH_NO_PROGRESS",
    "PUSH_TIMEOUT",
    "RETAINED",
    "STATIC_CLAMP_COMPLETE",
    "STATIC_CLAMP_INCOMPLETE",
    "PLACEMENT_INCOMPLETE",
    "PLACEMENT_NOT_CONVERGED",
    "OFFSET_PLACEMENT_COMPLETE_EPISODE_ENDED",
    "STABILIZATION_CONTACT_CONTAMINATED",
    "STABILIZATION_GATE_LOST",
    "STABILIZATION_INCOMPLETE",
    "STABILIZATION_READY",
    "STABILIZATION_NOT_SETTLED",
    "MATCHED_CLEAN_NO_GATE",
    "MATCHED_CLEAN_RETREAT_IK_INVALID",
    "MATCHED_CLEAN_RETREAT_JOINT_LIMIT",
    "MATCHED_CLEAN_RETREAT_ACTION_INVALID",
    "MATCHED_CLEAN_RETREAT_TIMEOUT",
    "MATCHED_CLEAN_RETREAT_INCOMPLETE",
    "MATCHED_CLEAN_STABILIZE_CONTACT_CONTAMINATED",
    "MATCHED_CLEAN_STABILIZE_INCOMPLETE",
    "MATCHED_CLEAN_READY",
    "MATCHED_CLEAN_NOT_SETTLED",
)
A2_HOLD_OUTCOME_TO_ID = {name: index for index, name in enumerate(A2_HOLD_OUTCOME_NAMES)}


def a2_update_grasp_control_streak(
    streak: torch.Tensor,
    condition: torch.Tensor,
    reset_mask: torch.Tensor,
) -> torch.Tensor:
    """Advance one control-step streak update with explicit reset semantics."""
    if (
        not torch.is_tensor(streak)
        or streak.ndim != 1
        or streak.dtype != torch.long
        or not torch.is_tensor(condition)
        or condition.shape != streak.shape
        or condition.dtype != torch.bool
        or condition.device != streak.device
        or not torch.is_tensor(reset_mask)
        or reset_mask.shape != streak.shape
        or reset_mask.dtype != torch.bool
        or reset_mask.device != streak.device
        or torch.any(streak < 0)
    ):
        raise ValueError(
            "A2 grasp control streak requires a non-negative long streak and "
            "matching bool condition/reset tensors."
        )
    zeros = torch.zeros_like(streak)
    return torch.where(
        reset_mask,
        zeros,
        torch.where(condition, streak + 1, zeros),
    )


def a2_masked_grasp_streak_quantile(
    streak: torch.Tensor,
    active_mask: torch.Tensor,
    quantile: float,
) -> torch.Tensor:
    """Compute a stage-scoped streak quantile, returning zero when the stage is inactive."""
    if (
        not torch.is_tensor(streak)
        or streak.ndim != 1
        or streak.dtype != torch.long
        or torch.any(streak < 0)
        or not torch.is_tensor(active_mask)
        or active_mask.shape != streak.shape
        or active_mask.dtype != torch.bool
        or active_mask.device != streak.device
        or isinstance(quantile, bool)
        or not isinstance(quantile, (int, float))
        or not math.isfinite(float(quantile))
        or not 0.0 <= float(quantile) <= 1.0
    ):
        raise ValueError(
            "A2 grasp streak quantile requires a non-negative long streak, matching "
            "bool active mask, and finite quantile in [0, 1]."
        )
    active_streak = streak[active_mask].float()
    if active_streak.numel() == 0:
        return torch.zeros((), dtype=torch.float32, device=streak.device)
    return torch.quantile(active_streak, float(quantile))


def a2_masked_float_quantile(
    values: torch.Tensor,
    active_mask: torch.Tensor,
    quantile: float,
) -> torch.Tensor:
    """Compute a stage-scoped floating-point quantile."""
    if (
        not torch.is_tensor(values)
        or values.ndim != 1
        or not values.is_floating_point()
        or not torch.all(torch.isfinite(values))
        or not torch.is_tensor(active_mask)
        or active_mask.shape != values.shape
        or active_mask.dtype != torch.bool
        or active_mask.device != values.device
        or isinstance(quantile, bool)
        or not isinstance(quantile, (int, float))
        or not math.isfinite(float(quantile))
        or not 0.0 <= float(quantile) <= 1.0
    ):
        raise ValueError(
            "A2 masked quantile requires finite 1D floating values, matching bool "
            "active mask, and finite quantile in [0, 1]."
        )
    active_values = values[active_mask]
    if active_values.numel() == 0:
        return torch.zeros((), dtype=values.dtype, device=values.device)
    return torch.quantile(active_values, float(quantile))


def a2_masked_boolean_fraction(
    condition: torch.Tensor,
    active_mask: torch.Tensor,
) -> torch.Tensor:
    """Return the conditional fraction of active environments satisfying a mask."""
    if (
        not torch.is_tensor(condition)
        or condition.ndim != 1
        or condition.dtype != torch.bool
        or not torch.is_tensor(active_mask)
        or active_mask.shape != condition.shape
        or active_mask.dtype != torch.bool
        or active_mask.device != condition.device
    ):
        raise ValueError(
            "A2 masked fraction requires matching 1D bool condition and active mask."
        )
    active_count = active_mask.float().sum()
    return (condition & active_mask).float().sum() / active_count.clamp_min(1.0)


def a2_grasp_gated_door_reward_components(
    streak: torch.Tensor,
    required_streak_steps: int,
    handle_pos: torch.Tensor,
    hinge_pos: torch.Tensor,
    hinge_vel: torch.Tensor,
    unlatch_handle_position_norm: float,
    unlatch_near_closed_hinge_threshold: float,
    hold_and_drive_velocity_norm: float,
) -> dict[str, torch.Tensor]:
    """Compute grasp-gated unlatch and hold-and-drive reward components."""
    floating_values = (handle_pos, hinge_pos, hinge_vel)
    if (
        not torch.is_tensor(streak)
        or streak.ndim != 1
        or streak.dtype != torch.long
        or torch.any(streak < 0)
        or isinstance(required_streak_steps, bool)
        or not isinstance(required_streak_steps, int)
        or required_streak_steps <= 0
        or any(
            not torch.is_tensor(value)
            or value.shape != streak.shape
            or not value.is_floating_point()
            or value.device != streak.device
            or not torch.all(torch.isfinite(value))
            for value in floating_values
        )
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) <= 0.0
            for value in (
                unlatch_handle_position_norm,
                unlatch_near_closed_hinge_threshold,
                hold_and_drive_velocity_norm,
            )
        )
    ):
        raise ValueError(
            "A2 grasp-gated door rewards require a non-negative long streak, "
            "positive scalar thresholds, and matching finite floating door tensors."
        )

    hold_streak_ok = streak >= required_streak_steps
    unlatch_press = (
        handle_pos / float(unlatch_handle_position_norm)
    ).clamp(0.0, 1.0)
    near_closed = hinge_pos < float(unlatch_near_closed_hinge_threshold)
    drive = (hinge_vel / float(hold_and_drive_velocity_norm)).clamp(0.0, 1.0)
    hold_float = hold_streak_ok.float()
    return {
        "hold_streak_ok": hold_streak_ok,
        "unlatch_press": unlatch_press,
        "unlatch_hold": hold_float * unlatch_press * near_closed.float(),
        "hold_and_drive": hold_float * drive,
    }


def a2_stage3_to4_advance_mask(
    door_opened: torch.Tensor,
    hold_streak_ok: torch.Tensor,
    requires_grasp_streak: bool,
) -> torch.Tensor:
    """Apply the explicit v13 grasp requirement to the stage3->4 transition."""
    if (
        not torch.is_tensor(door_opened)
        or door_opened.ndim != 1
        or door_opened.dtype != torch.bool
        or not torch.is_tensor(hold_streak_ok)
        or hold_streak_ok.shape != door_opened.shape
        or hold_streak_ok.dtype != torch.bool
        or hold_streak_ok.device != door_opened.device
        or not isinstance(requires_grasp_streak, bool)
    ):
        raise ValueError(
            "A2 stage3->4 gate requires matching 1D bool door/hold masks and a bool mode."
        )
    return door_opened & hold_streak_ok if requires_grasp_streak else door_opened


def a2_stage3_to4_hold_streak_mask(
    current_streak_ok: torch.Tensor,
    stage3_highwater: torch.Tensor,
    requires_grasp_streak: bool,
    highwater_enabled: bool,
) -> torch.Tensor:
    """Return the stage3->4 grasp gate with an explicit high-water ablation.

    The default (``highwater_enabled=False``) is byte-for-byte equivalent to the
    current streak gate.  The emergency ablation only ORs the stage3 latch when
    the existing grasp requirement is enabled; it never changes the gate when
    ``requires_grasp_streak`` is false.
    """
    for name, value in (
        ("current_streak_ok", current_streak_ok),
        ("stage3_highwater", stage3_highwater),
    ):
        if (
            not torch.is_tensor(value)
            or value.ndim != 1
            or value.dtype != torch.bool
        ):
            raise ValueError(
                f"{name} must be a one-dimensional bool tensor; got "
                f"{None if not torch.is_tensor(value) else (tuple(value.shape), value.dtype)}."
            )
    if current_streak_ok.shape != stage3_highwater.shape:
        raise ValueError(
            "stage3 high-water gate tensors must have matching shapes; "
            f"got {tuple(current_streak_ok.shape)} and {tuple(stage3_highwater.shape)}."
        )
    if current_streak_ok.device != stage3_highwater.device:
        raise ValueError(
            "stage3 high-water gate tensors must share a device; "
            f"got {current_streak_ok.device} and {stage3_highwater.device}."
        )
    if not isinstance(requires_grasp_streak, bool) or not isinstance(highwater_enabled, bool):
        raise ValueError("stage3 high-water gate flags must be bool values.")
    if not requires_grasp_streak:
        return torch.ones_like(current_streak_ok)
    return current_streak_ok | (stage3_highwater if highwater_enabled else torch.zeros_like(stage3_highwater))


def a2_stage34_hold_income_mask(
    stage_buf: torch.Tensor,
    release_gate: torch.Tensor,
    stage_open: int,
    stage_swing: int,
) -> torch.Tensor:
    """Return the stage3/4 hold-income mask with an episode-latched release gate."""
    if (
        not torch.is_tensor(stage_buf)
        or stage_buf.ndim != 1
        or stage_buf.dtype != torch.long
        or not torch.is_tensor(release_gate)
        or release_gate.shape != stage_buf.shape
        or release_gate.dtype != torch.bool
        or release_gate.device != stage_buf.device
        or isinstance(stage_open, bool)
        or not isinstance(stage_open, int)
        or isinstance(stage_swing, bool)
        or not isinstance(stage_swing, int)
        or stage_open == stage_swing
    ):
        raise ValueError(
            "A2 stage3/4 hold-income mask requires a long stage vector, a matching "
            "bool release-gate vector, and distinct integer stage values."
        )
    return (stage_buf == stage_open) | ((stage_buf == stage_swing) & ~release_gate)

def a2_update_stage4_release_and_root_latches(
    release_gate: torch.Tensor,
    root_x_ever_crossed: torch.Tensor,
    stage_buf: torch.Tensor,
    hinge_pos: torch.Tensor,
    root_x: torch.Tensor,
    release_hinge_threshold: float,
    stage_swing: int,
    update_mask: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """OR-latch stage4 release and current-episode root-X crossing state."""
    if (
        not torch.is_tensor(release_gate)
        or release_gate.ndim != 1
        or release_gate.dtype != torch.bool
        or not torch.is_tensor(root_x_ever_crossed)
        or root_x_ever_crossed.shape != release_gate.shape
        or root_x_ever_crossed.dtype != torch.bool
        or root_x_ever_crossed.device != release_gate.device
        or not torch.is_tensor(stage_buf)
        or stage_buf.shape != release_gate.shape
        or stage_buf.dtype != torch.long
        or stage_buf.device != release_gate.device
        or not torch.is_tensor(hinge_pos)
        or hinge_pos.shape != release_gate.shape
        or not hinge_pos.is_floating_point()
        or hinge_pos.device != release_gate.device
        or not torch.is_tensor(root_x)
        or root_x.shape != release_gate.shape
        or not root_x.is_floating_point()
        or root_x.dtype != hinge_pos.dtype
        or root_x.device != release_gate.device
        or not torch.all(torch.isfinite(hinge_pos))
        or not torch.all(torch.isfinite(root_x))
        or isinstance(release_hinge_threshold, bool)
        or not isinstance(release_hinge_threshold, (int, float))
        or not math.isfinite(float(release_hinge_threshold))
        or float(release_hinge_threshold) <= 0.0
        or isinstance(stage_swing, bool)
        or not isinstance(stage_swing, int)
    ):
        raise ValueError("A2 route latches require matching device-local vectors and a finite positive threshold.")
    if update_mask is None:
        update_mask = torch.ones_like(release_gate)
    elif (
        not torch.is_tensor(update_mask)
        or update_mask.shape != release_gate.shape
        or update_mask.dtype != torch.bool
        or update_mask.device != release_gate.device
    ):
        raise ValueError("A2 route latch update_mask must be a matching device-local bool vector.")
    release_candidate = update_mask & (stage_buf == stage_swing) & (
        hinge_pos >= float(release_hinge_threshold)
    )
    root_crossing_candidate = update_mask & (root_x > 0.0)
    return (
        release_gate | release_candidate,
        root_x_ever_crossed | root_crossing_candidate,
    )


def a2_update_stage4_release_and_root_latches_through_stage5(
    release_gate: torch.Tensor,
    root_x_ever_crossed: torch.Tensor,
    stage_buf: torch.Tensor,
    hinge_pos: torch.Tensor,
    root_x: torch.Tensor,
    release_hinge_threshold: float,
    stage_swing: int,
    stage_through: int,
    stage5_continuity_enabled: bool,
    update_mask: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Extend the historical stage4 release latch into stage5 when selected."""
    if (
        isinstance(stage_through, bool)
        or not isinstance(stage_through, int)
        or stage_through == stage_swing
        or not isinstance(stage5_continuity_enabled, bool)
    ):
        raise ValueError(
            "A2 stage5 release continuity requires distinct integer stages and a bool selector."
        )
    updated_gate, updated_crossed = a2_update_stage4_release_and_root_latches(
        release_gate,
        root_x_ever_crossed,
        stage_buf,
        hinge_pos,
        root_x,
        release_hinge_threshold,
        stage_swing,
        update_mask,
    )
    if not stage5_continuity_enabled:
        return updated_gate, updated_crossed
    effective_update_mask = (
        torch.ones_like(release_gate) if update_mask is None else update_mask
    )
    stage5_release = effective_update_mask & (stage_buf == stage_through) & (
        hinge_pos >= float(release_hinge_threshold)
    )
    return updated_gate | stage5_release, updated_crossed


def a2_corridor_hold_and_drive_component(
    hold_streak_ok: torch.Tensor,
    hinge_vel: torch.Tensor,
    corridor_latched: torch.Tensor,
    normal_velocity_norm: float,
    corridor_velocity_norm: float,
    corridor_enabled: bool,
) -> torch.Tensor:
    """Compute hold-and-drive credit with an explicit versioned corridor phase."""
    if not isinstance(corridor_enabled, bool):
        raise ValueError("A2 corridor enabled selector must be bool.")
    if (
        not torch.is_tensor(hold_streak_ok)
        or hold_streak_ok.ndim != 1
        or hold_streak_ok.dtype != torch.bool
        or not torch.is_tensor(hinge_vel)
        or hinge_vel.shape != hold_streak_ok.shape
        or not hinge_vel.is_floating_point()
        or hinge_vel.device != hold_streak_ok.device
        or not torch.all(torch.isfinite(hinge_vel))
        or not torch.is_tensor(corridor_latched)
        or corridor_latched.shape != hold_streak_ok.shape
        or corridor_latched.dtype != torch.bool
        or corridor_latched.device != hold_streak_ok.device
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) <= 0.0
            for value in (normal_velocity_norm, corridor_velocity_norm)
        )
    ):
        raise ValueError(
            "A2 corridor hold-and-drive requires matching finite vectors and positive velocity norms."
        )
    if corridor_enabled and float(corridor_velocity_norm) <= float(normal_velocity_norm):
        raise ValueError(
            "A2 enabled corridor hold-and-drive requires corridor velocity norm above the historical norm."
        )
    velocity_norm = torch.where(
        corridor_latched if corridor_enabled else torch.zeros_like(corridor_latched),
        torch.full_like(hinge_vel, float(corridor_velocity_norm)),
        torch.full_like(hinge_vel, float(normal_velocity_norm)),
    )
    return hold_streak_ok.float() * (hinge_vel / velocity_norm).clamp(0.0, 1.0)



def a2_update_corridor_latch(
    corridor_latched: torch.Tensor,
    root_x_ever_crossed: torch.Tensor,
    stage_buf: torch.Tensor,
    hinge_pos: torch.Tensor,
    stage_swing: int,
    corridor_enabled: bool,
    update_mask: torch.Tensor | None = None,
) -> torch.Tensor:
    """Latch the versioned delivery corridor through the remainder of each episode."""
    if not isinstance(corridor_enabled, bool):
        raise ValueError("A2 corridor enabled selector must be bool.")
    if (
        not torch.is_tensor(corridor_latched)
        or corridor_latched.ndim != 1
        or corridor_latched.dtype != torch.bool
        or not torch.is_tensor(root_x_ever_crossed)
        or root_x_ever_crossed.shape != corridor_latched.shape
        or root_x_ever_crossed.dtype != torch.bool
        or root_x_ever_crossed.device != corridor_latched.device
        or not torch.is_tensor(stage_buf)
        or stage_buf.shape != corridor_latched.shape
        or stage_buf.dtype != torch.long
        or stage_buf.device != corridor_latched.device
        or not torch.is_tensor(hinge_pos)
        or hinge_pos.shape != corridor_latched.shape
        or not hinge_pos.is_floating_point()
        or hinge_pos.device != corridor_latched.device
        or not torch.all(torch.isfinite(hinge_pos))
        or isinstance(stage_swing, bool)
        or not isinstance(stage_swing, int)
    ):
        raise ValueError("A2 corridor latch requires matching finite device-local vectors.")
    if update_mask is None:
        update_mask = torch.ones_like(corridor_latched)
    elif (
        not torch.is_tensor(update_mask)
        or update_mask.shape != corridor_latched.shape
        or update_mask.dtype != torch.bool
        or update_mask.device != corridor_latched.device
    ):
        raise ValueError("A2 corridor latch update_mask must be a matching device-local bool vector.")
    if not corridor_enabled:
        return torch.zeros_like(corridor_latched)
    candidate = root_x_ever_crossed | (
        (stage_buf >= stage_swing) & (hinge_pos >= 1.0)
    )
    return corridor_latched | (update_mask & candidate)


def a2_door_body_contact_penalty_component(
    body_total: torch.Tensor, mode: str
) -> torch.Tensor:
    """Dispatch the exact historical/v16 body-panel penalty shape."""
    if (
        not torch.is_tensor(body_total)
        or body_total.ndim != 1
        or not body_total.is_floating_point()
        or not torch.all(torch.isfinite(body_total))
        or torch.any(body_total < 0.0)
    ):
        raise ValueError("A2 body contact penalty requires finite non-negative floating force.")
    if mode == "linear_v15":
        return (body_total / 20.0).clamp(0.0, 1.0)
    if mode == "quadratic_v16":
        return torch.square((body_total / 40.0).clamp(0.0, 1.0))
    raise ValueError(
        "A2 body contact penalty mode must be exactly 'linear_v15' or 'quadratic_v16'; "
        f"got {mode!r}."
    )


def a2_scope_door_body_contact_force(
    stage_buf: torch.Tensor,
    body_total: torch.Tensor,
    stage_open: int,
    stage_swing: int,
) -> torch.Tensor:
    """Exclude pre-opening and post-swing contact from event-state accumulation."""
    if (
        not torch.is_tensor(stage_buf)
        or stage_buf.ndim != 1
        or stage_buf.dtype != torch.long
        or not torch.is_tensor(body_total)
        or body_total.shape != stage_buf.shape
        or not body_total.is_floating_point()
        or body_total.device != stage_buf.device
        or not torch.all(torch.isfinite(body_total))
        or torch.any(body_total < 0.0)
        or isinstance(stage_open, bool)
        or not isinstance(stage_open, int)
        or isinstance(stage_swing, bool)
        or not isinstance(stage_swing, int)
        or stage_open == stage_swing
    ):
        raise ValueError(
            "A2 body-contact event scoping requires a long stage vector, a matching "
            "finite non-negative force vector, and distinct opening-stage values."
        )
    opening_stage = (stage_buf == stage_open) | (stage_buf == stage_swing)
    return torch.where(opening_stage, body_total, torch.zeros_like(body_total))


def a2_update_door_body_contact_event(
    active: torch.Tensor,
    peak_force: torch.Tensor,
    body_total: torch.Tensor,
    force_threshold: float,
    peak_force_norm: float,
    component_cap: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Advance one body-contact event and emit its normalized peak once at exit."""
    if (
        not torch.is_tensor(active)
        or active.ndim != 1
        or active.dtype != torch.bool
        or not torch.is_tensor(peak_force)
        or peak_force.shape != active.shape
        or not peak_force.is_floating_point()
        or peak_force.device != active.device
        or not torch.is_tensor(body_total)
        or body_total.shape != active.shape
        or not body_total.is_floating_point()
        or body_total.dtype != peak_force.dtype
        or body_total.device != active.device
        or not torch.all(torch.isfinite(peak_force))
        or not torch.all(torch.isfinite(body_total))
        or torch.any(peak_force < 0.0)
        or torch.any(body_total < 0.0)
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) <= 0.0
            for value in (force_threshold, peak_force_norm, component_cap)
        )
    ):
        raise ValueError(
            "A2 body-contact event requires matching finite non-negative vectors "
            "and finite positive threshold, norm, and cap."
        )
    contact_now = body_total >= float(force_threshold)
    ended = active & ~contact_now
    emitted = torch.where(
        ended,
        (peak_force / float(peak_force_norm)).clamp(0.0, float(component_cap)),
        torch.zeros_like(peak_force),
    )
    next_peak = torch.where(
        contact_now,
        torch.where(active, torch.maximum(peak_force, body_total), body_total),
        torch.zeros_like(peak_force),
    )
    return contact_now, next_peak, emitted


def a2_finalize_door_body_contact_event(
    active: torch.Tensor,
    peak_force: torch.Tensor,
    finalize_mask: torch.Tensor,
    peak_force_norm: float,
    component_cap: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Finalize active events selected by a reset or stage-boundary mask."""
    if (
        not torch.is_tensor(active)
        or active.ndim != 1
        or active.dtype != torch.bool
        or not torch.is_tensor(peak_force)
        or peak_force.shape != active.shape
        or not peak_force.is_floating_point()
        or peak_force.device != active.device
        or not torch.all(torch.isfinite(peak_force))
        or torch.any(peak_force < 0.0)
        or not torch.is_tensor(finalize_mask)
        or finalize_mask.shape != active.shape
        or finalize_mask.dtype != torch.bool
        or finalize_mask.device != active.device
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) <= 0.0
            for value in (peak_force_norm, component_cap)
        )
    ):
        raise ValueError(
            "A2 body-contact event finalization requires matching device-local state "
            "and finite positive norm and cap."
        )
    finalized = active & finalize_mask
    emitted = torch.where(
        finalized,
        (peak_force / float(peak_force_norm)).clamp(0.0, float(component_cap)),
        torch.zeros_like(peak_force),
    )
    next_active = active & ~finalize_mask
    next_peak = torch.where(next_active, peak_force, torch.zeros_like(peak_force))
    return next_active, next_peak, emitted


def a2_corridor_clean_passage_component(
    corridor_latched: torch.Tensor,
    body_total: torch.Tensor,
    force_threshold: float,
) -> torch.Tensor:
    """Pay corridor passage only when no priced body-panel contact is active."""
    if (
        not torch.is_tensor(corridor_latched)
        or corridor_latched.ndim != 1
        or corridor_latched.dtype != torch.bool
        or not torch.is_tensor(body_total)
        or body_total.shape != corridor_latched.shape
        or not body_total.is_floating_point()
        or body_total.device != corridor_latched.device
        or not torch.all(torch.isfinite(body_total))
        or torch.any(body_total < 0.0)
        or isinstance(force_threshold, bool)
        or not isinstance(force_threshold, (int, float))
        or not math.isfinite(float(force_threshold))
        or float(force_threshold) <= 0.0
    ):
        raise ValueError(
            "A2 clean passage requires a bool corridor mask, finite non-negative "
            "body force, and a finite positive threshold."
        )
    return corridor_latched.float() * (body_total < float(force_threshold)).float()


def a2_update_stage5_hold_continuation(
    continuation: torch.Tensor,
    stage_buf: torch.Tensor,
    both_contact: torch.Tensor,
    stage_through: int,
    enabled: bool,
) -> torch.Tensor:
    """Keep the stage5 hold latch only while bilateral contact remains continuous."""
    if (
        not torch.is_tensor(continuation)
        or continuation.ndim != 1
        or continuation.dtype != torch.bool
        or not torch.is_tensor(stage_buf)
        or stage_buf.shape != continuation.shape
        or stage_buf.dtype != torch.long
        or stage_buf.device != continuation.device
        or not torch.is_tensor(both_contact)
        or both_contact.shape != continuation.shape
        or both_contact.dtype != torch.bool
        or both_contact.device != continuation.device
        or isinstance(stage_through, bool)
        or not isinstance(stage_through, int)
        or not isinstance(enabled, bool)
    ):
        raise ValueError(
            "A2 stage5 hold continuation requires matching device-local masks, "
            "an integer stage, and a bool selector."
        )
    if not enabled:
        return torch.zeros_like(continuation)
    return continuation & (stage_buf == stage_through) & both_contact


def a2_apply_stage4_target_root_distance_scale(
    reward: torch.Tensor,
    stage_buf: torch.Tensor,
    release_gate: torch.Tensor,
    stage_swing: int,
) -> torch.Tensor:
    """Apply the unreleased-stage4 half scale while leaving stage5 unchanged."""
    if (
        not torch.is_tensor(reward)
        or reward.ndim != 1
        or not reward.is_floating_point()
        or not torch.all(torch.isfinite(reward))
        or not torch.is_tensor(stage_buf)
        or stage_buf.shape != reward.shape
        or stage_buf.dtype != torch.long
        or stage_buf.device != reward.device
        or not torch.is_tensor(release_gate)
        or release_gate.shape != reward.shape
        or release_gate.dtype != torch.bool
        or release_gate.device != reward.device
        or isinstance(stage_swing, bool)
        or not isinstance(stage_swing, int)
    ):
        raise ValueError("A2 target-root-distance scaling requires matching finite reward, long stage, and bool release-gate vectors.")
    scaled_reward = reward.clone()
    unreleased_stage4 = (stage_buf == stage_swing) & ~release_gate
    scaled_reward[unreleased_stage4] *= 0.5
    return scaled_reward

def a2_apply_stage45_doorframe_contact_scale(
    contact_force: torch.Tensor,
    stage_buf: torch.Tensor,
    stage_swing: int,
    stage_through: int,
    scale: float,
) -> torch.Tensor:
    """Scale only stage4/5 door-frame contact force for A2."""
    if (
        not torch.is_tensor(contact_force)
        or contact_force.ndim != 1
        or not contact_force.is_floating_point()
        or not torch.all(torch.isfinite(contact_force))
        or not torch.is_tensor(stage_buf)
        or stage_buf.shape != contact_force.shape
        or stage_buf.dtype != torch.long
        or stage_buf.device != contact_force.device
        or isinstance(stage_swing, bool)
        or not isinstance(stage_swing, int)
        or isinstance(stage_through, bool)
        or not isinstance(stage_through, int)
        or stage_swing == stage_through
        or isinstance(scale, bool)
        or not isinstance(scale, (int, float))
        or not math.isfinite(float(scale))
        or not 0.0 <= float(scale) <= 1.0
    ):
        raise ValueError("A2 stage4/5 door-frame scaling requires matching finite contact/stage vectors, distinct integer stages, and scale in [0, 1].")
    stage45 = (stage_buf == stage_swing) | (stage_buf == stage_through)
    multiplier = torch.where(
        stage45,
        contact_force.new_tensor(float(scale)),
        torch.ones_like(contact_force),
    )
    return contact_force * multiplier

def a2_root_x_first_crossing_env_count(root_x_ever_crossed: torch.Tensor) -> torch.Tensor:
    """Count environments that crossed root-X zero during the current episode."""
    if (
        not torch.is_tensor(root_x_ever_crossed)
        or root_x_ever_crossed.ndim != 1
        or root_x_ever_crossed.dtype != torch.bool
    ):
        raise ValueError("A2 root-X crossing count requires a 1D bool latch vector.")
    return root_x_ever_crossed.sum(dtype=torch.float32)


def a2_validate_stage0_staging_band(
    x_min: float,
    x_max: float,
    y_tol: float,
) -> tuple[float, float, float]:
    """Validate and normalize the A2 stage0 staging-band contract."""
    values = (x_min, x_max, y_tol)
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        raise ValueError("A2 stage0 staging band requires three numeric values.")
    x_min, x_max, y_tol = (float(value) for value in values)
    if not all(math.isfinite(value) for value in (x_min, x_max, y_tol)):
        raise ValueError("A2 stage0 staging band values must be finite.")
    if x_min <= 0.0 or x_max < x_min or y_tol <= 0.0:
        raise ValueError(
            "A2 stage0 staging band requires 0 < x_min <= x_max and y_tol > 0."
        )
    return x_min, x_max, y_tol


def _validate_a2_stage0_staging_tensors(
    root_pos: torch.Tensor,
    grasp_target: torch.Tensor,
) -> None:
    if (
        not torch.is_tensor(root_pos)
        or not torch.is_tensor(grasp_target)
        or root_pos.ndim != 2
        or tuple(root_pos.shape) != tuple(grasp_target.shape)
        or root_pos.shape[1] != 3
        or not root_pos.is_floating_point()
        or grasp_target.dtype != root_pos.dtype
        or grasp_target.device != root_pos.device
        or not torch.all(torch.isfinite(root_pos))
        or not torch.all(torch.isfinite(grasp_target))
    ):
        raise ValueError(
            "A2 stage0 staging geometry requires matching finite floating (N, 3) "
            "root and grasp tensors."
        )


def a2_stage0_staging_band_mask(
    root_pos: torch.Tensor,
    grasp_target: torch.Tensor,
    x_min: float,
    x_max: float,
    y_tol: float,
) -> torch.Tensor:
    """Return membership in the handle-relative stage0 staging band."""
    _validate_a2_stage0_staging_tensors(root_pos, grasp_target)
    x_min, x_max, y_tol = a2_validate_stage0_staging_band(
        x_min,
        x_max,
        y_tol,
    )
    dx = grasp_target[:, 0] - root_pos[:, 0]
    dy = root_pos[:, 1] - grasp_target[:, 1]
    return (dx >= x_min) & (dx <= x_max) & (dy.abs() < y_tol)


def a2_stage0_nearest_staging_target(
    root_pos: torch.Tensor,
    grasp_target: torch.Tensor,
    x_min: float,
    x_max: float,
    y_tol: float,
) -> torch.Tensor:
    """Return the nearest point in the stage0 band for each root pose."""
    _validate_a2_stage0_staging_tensors(root_pos, grasp_target)
    x_min, x_max, y_tol = a2_validate_stage0_staging_band(
        x_min,
        x_max,
        y_tol,
    )
    dx = grasp_target[:, 0] - root_pos[:, 0]
    dy = grasp_target[:, 1] - root_pos[:, 1]
    target = grasp_target.clone()
    target[:, 0] = grasp_target[:, 0] - dx.clamp(x_min, x_max)
    y_boundary = torch.full_like(dy, y_tol)
    interior_y_boundary = torch.nextafter(y_boundary, torch.zeros_like(y_boundary))
    clamped_dy = torch.maximum(
        torch.minimum(dy, interior_y_boundary),
        -interior_y_boundary,
    )
    target[:, 1] = grasp_target[:, 1] - clamped_dy
    target[:, 2] = root_pos[:, 2]
    return target


def a2_hold_quaternion_geodesic_rad(quat_a: torch.Tensor, quat_b: torch.Tensor):
    """Return the sign-invariant geodesic angle between unit WXYZ quaternions."""
    if (
        not torch.is_tensor(quat_a)
        or not torch.is_tensor(quat_b)
        or quat_a.shape != quat_b.shape
        or quat_a.ndim < 1
        or quat_a.shape[-1] != 4
        or not quat_a.is_floating_point()
        or quat_b.dtype != quat_a.dtype
        or quat_b.device != quat_a.device
        or not torch.all(torch.isfinite(quat_a))
        or not torch.all(torch.isfinite(quat_b))
    ):
        raise ValueError("quaternion geodesic inputs must be finite matching (...,4) tensors.")
    norm_a = torch.linalg.norm(quat_a, dim=-1)
    norm_b = torch.linalg.norm(quat_b, dim=-1)
    if not torch.allclose(norm_a, torch.ones_like(norm_a), atol=1.0e-5, rtol=0.0) or not torch.allclose(
        norm_b, torch.ones_like(norm_b), atol=1.0e-5, rtol=0.0
    ):
        raise ValueError("quaternion geodesic inputs must be unit length.")
    dot = torch.abs(torch.sum(quat_a * quat_b, dim=-1)).clamp(max=1.0)
    return 2.0 * torch.acos(dot)


def a2_hold_pose_motion_metrics(position: torch.Tensor, quaternion: torch.Tensor):
    """Compute adjacent and first-to-last motion for a time-major pose window."""
    if (
        not torch.is_tensor(position)
        or position.ndim != 3
        or position.shape[-1] != 3
        or position.shape[0] < 2
        or not torch.is_tensor(quaternion)
        or quaternion.shape != (*position.shape[:-1], 4)
        or not position.is_floating_point()
        or quaternion.dtype != position.dtype
        or quaternion.device != position.device
        or not torch.all(torch.isfinite(position))
        or not torch.all(torch.isfinite(quaternion))
    ):
        raise ValueError("pose motion inputs must be finite time-major (T,N,3)/(T,N,4) tensors.")
    adjacent_translation = torch.linalg.norm(position[1:] - position[:-1], dim=-1)
    adjacent_rotation = a2_hold_quaternion_geodesic_rad(quaternion[1:], quaternion[:-1])
    window_translation = torch.linalg.norm(position[-1] - position[0], dim=-1)
    window_rotation = a2_hold_quaternion_geodesic_rad(quaternion[-1], quaternion[0])
    return {
        "per_call_translation_max": adjacent_translation.max(dim=0).values,
        "per_call_rotation_max": adjacent_rotation.max(dim=0).values,
        "window_translation": window_translation,
        "window_rotation": window_rotation,
    }


def a2_hold_open_stabilization_action(
    policy_action: torch.Tensor, override_mask: torch.Tensor
):
    """Apply the exact base-zero, arm-raw-zero, gripper-open preflight action."""
    if (
        not torch.is_tensor(policy_action)
        or policy_action.ndim != 2
        or policy_action.shape[1] != 12
        or not policy_action.is_floating_point()
        or not torch.all(torch.isfinite(policy_action))
        or not torch.is_tensor(override_mask)
        or override_mask.shape != policy_action.shape[:1]
        or override_mask.dtype != torch.bool
        or override_mask.device != policy_action.device
    ):
        raise ValueError("open-stabilization action inputs violate the canonical A2 action contract.")
    action = policy_action.clone()
    action[override_mask, :11] = 0.0
    action[override_mask, 11] = 1.0
    return action


def a2_hold_matched_clean_release_action(
    policy_action: torch.Tensor,
    override_mask: torch.Tensor,
    arm_action_raw: torch.Tensor,
):
    """Apply the matched-clean release/retreat action without touching inactive rows."""
    if (
        not torch.is_tensor(policy_action)
        or policy_action.ndim != 2
        or policy_action.shape[1] != 12
        or not policy_action.is_floating_point()
        or not torch.all(torch.isfinite(policy_action))
        or not torch.is_tensor(override_mask)
        or override_mask.shape != policy_action.shape[:1]
        or override_mask.dtype != torch.bool
        or override_mask.device != policy_action.device
        or not torch.is_tensor(arm_action_raw)
        or tuple(arm_action_raw.shape) != (policy_action.shape[0], 6)
        or arm_action_raw.dtype != policy_action.dtype
        or arm_action_raw.device != policy_action.device
        or not torch.all(torch.isfinite(arm_action_raw))
    ):
        raise ValueError(
            "matched-clean release action inputs violate the canonical A2 action contract."
        )
    action = policy_action.clone()
    action[override_mask, :5] = 0.0
    action[override_mask, 5:11] = arm_action_raw[override_mask]
    action[override_mask, 11] = 1.0
    return action


def a2_hold_matched_clean_release_qualification(
    pregrasp_position_residual: torch.Tensor,
    pregrasp_orientation_residual: torch.Tensor,
    filtered_normal_force_magnitude: torch.Tensor,
    source_handle_distance: torch.Tensor,
    *,
    position_tolerance_m: float = 0.005,
    orientation_tolerance_rad: float = 0.10,
    contact_force_limit_n: float = 1.0,
    source_handle_distance_min_m: float = 0.095,
):
    """Return the strict post-action qualification mask for clean reacquisition."""
    values = (
        pregrasp_position_residual,
        pregrasp_orientation_residual,
        source_handle_distance,
    )
    if (
        any(
            not torch.is_tensor(value)
            or value.ndim != 1
            or not value.is_floating_point()
            for value in values
        )
        or any(value.shape != pregrasp_position_residual.shape for value in values)
        or not torch.is_tensor(filtered_normal_force_magnitude)
        or filtered_normal_force_magnitude.ndim != 2
        or filtered_normal_force_magnitude.shape[0] != pregrasp_position_residual.shape[0]
        or filtered_normal_force_magnitude.shape[1] != 2
        or filtered_normal_force_magnitude.dtype != pregrasp_position_residual.dtype
        or filtered_normal_force_magnitude.device != pregrasp_position_residual.device
        or any(value.device != pregrasp_position_residual.device for value in values)
        or not all(torch.all(torch.isfinite(value)) for value in values)
        or not torch.all(torch.isfinite(filtered_normal_force_magnitude))
    ):
        raise ValueError(
            "matched-clean qualification inputs require finite same-device residuals "
            "and filtered normal-force magnitudes shaped (N,2)."
        )
    for name, value in (
        ("position_tolerance_m", position_tolerance_m),
        ("orientation_tolerance_rad", orientation_tolerance_rad),
        ("contact_force_limit_n", contact_force_limit_n),
        ("source_handle_distance_min_m", source_handle_distance_min_m),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) <= 0.0
        ):
            raise ValueError(f"{name} must be a finite positive float.")
    return (
        (pregrasp_position_residual <= float(position_tolerance_m))
        & (pregrasp_orientation_residual <= float(orientation_tolerance_rad))
        & torch.all(filtered_normal_force_magnitude < float(contact_force_limit_n), dim=-1)
        & (source_handle_distance >= float(source_handle_distance_min_m))
    )


def a2_hold_matched_clean_release_step_masks(
    active: torch.Tensor,
    first_episode_active: torch.Tensor,
    action_count: torch.Tensor,
    qualification_count: torch.Tensor,
    qualified: torch.Tensor,
    contact_contaminated: torch.Tensor,
    retreat_timeout_steps: int,
    release_qualification_steps: int,
):
    """Advance asynchronous release/qualification state with contact-reset semantics."""
    tensors = (first_episode_active, qualified, contact_contaminated)
    if (
        not torch.is_tensor(active)
        or active.ndim != 1
        or active.dtype != torch.bool
        or any(
            not torch.is_tensor(value)
            or value.shape != active.shape
            or value.dtype != torch.bool
            or value.device != active.device
            for value in tensors
        )
        or not torch.is_tensor(action_count)
        or action_count.shape != active.shape
        or action_count.dtype != torch.long
        or action_count.device != active.device
        or torch.any(action_count < 0)
        or not torch.is_tensor(qualification_count)
        or qualification_count.shape != active.shape
        or qualification_count.dtype != torch.long
        or qualification_count.device != active.device
        or torch.any(qualification_count < 0)
        or isinstance(retreat_timeout_steps, bool)
        or not isinstance(retreat_timeout_steps, int)
        or retreat_timeout_steps <= 0
        or isinstance(release_qualification_steps, bool)
        or not isinstance(release_qualification_steps, int)
        or release_qualification_steps <= 0
    ):
        raise ValueError("matched-clean release step-state inputs are invalid.")
    if torch.any(action_count > retreat_timeout_steps):
        raise ValueError("matched-clean release action count exceeded its exact timeout.")
    if torch.any(qualification_count > release_qualification_steps):
        raise ValueError("matched-clean qualification count exceeded its exact target.")
    if torch.any(qualified & contact_contaminated):
        raise ValueError("matched-clean qualification cannot be true on a contact sample.")
    controlled = active & first_episode_active
    entered_contact = controlled & contact_contaminated
    next_qualification_count = qualification_count.clone()
    next_qualification_count[entered_contact] = 0
    next_qualification_count[controlled & ~contact_contaminated] = torch.where(
        qualified[controlled & ~contact_contaminated],
        qualification_count[controlled & ~contact_contaminated] + 1,
        torch.zeros_like(qualification_count[controlled & ~contact_contaminated]),
    )
    qualified_now = controlled & ~contact_contaminated & (
        next_qualification_count >= release_qualification_steps
    )
    timeout = controlled & ~qualified_now & (action_count >= retreat_timeout_steps)
    incomplete = active & ~first_episode_active
    next_active = controlled & ~qualified_now & ~timeout
    return {
        "qualified_now": qualified_now,
        "contact_reset": entered_contact,
        "timeout": timeout,
        "incomplete": incomplete,
        "active": next_active,
        "qualification_count": next_qualification_count,
    }


def a2_hold_matched_clean_stabilization_terminal_partition(
    affected_mask: torch.Tensor,
    action_count: torch.Tensor,
    contact_contaminated: torch.Tensor,
    target_steps: int,
):
    """Partition clean-stabilize completion; contact has terminal priority and gate is telemetry-only."""
    if (
        not torch.is_tensor(affected_mask)
        or affected_mask.ndim != 1
        or affected_mask.dtype != torch.bool
        or not torch.is_tensor(action_count)
        or action_count.shape != affected_mask.shape
        or action_count.dtype != torch.long
        or action_count.device != affected_mask.device
        or torch.any(action_count < 0)
        or not torch.is_tensor(contact_contaminated)
        or contact_contaminated.shape != affected_mask.shape
        or contact_contaminated.dtype != torch.bool
        or contact_contaminated.device != affected_mask.device
        or isinstance(target_steps, bool)
        or not isinstance(target_steps, int)
        or target_steps <= 0
    ):
        raise ValueError("matched-clean stabilization terminal inputs are invalid.")
    exceeded = affected_mask & (action_count > target_steps)
    if torch.any(exceeded):
        raise ValueError("matched-clean stabilization action count exceeded exact target.")
    contact = affected_mask & contact_contaminated
    endpoint = affected_mask & ~contact & (action_count == target_steps)
    incomplete = affected_mask & ~contact & (action_count < target_steps)
    return {
        "contact_contaminated": contact,
        "endpoint": endpoint,
        "incomplete": incomplete,
    }


def a2_hold_open_stabilization_terminal_partition(
    affected_mask: torch.Tensor,
    action_count: torch.Tensor,
    contact_contaminated: torch.Tensor,
    composite_gate: torch.Tensor,
    target_steps: int,
):
    """Partition a forced finish with CONTACT > GATE > endpoint > incomplete priority."""
    tensors = (affected_mask, contact_contaminated, composite_gate)
    if (
        any(
            not torch.is_tensor(value)
            or value.shape != affected_mask.shape
            or value.dtype != torch.bool
            or value.device != affected_mask.device
            for value in tensors
        )
        or affected_mask.ndim != 1
        or not torch.is_tensor(action_count)
        or action_count.shape != affected_mask.shape
        or action_count.dtype != torch.long
        or action_count.device != affected_mask.device
        or torch.any(action_count < 0)
        or isinstance(target_steps, bool)
        or not isinstance(target_steps, int)
        or target_steps <= 0
    ):
        raise ValueError("open-stabilization terminal partition inputs are invalid.")
    exceeded = affected_mask & (action_count > target_steps)
    if torch.any(exceeded):
        raise ValueError("open-stabilization action count exceeded its exact target.")
    contact = affected_mask & contact_contaminated
    gate_lost = affected_mask & ~contact & ~composite_gate
    endpoint = affected_mask & ~contact & composite_gate & (action_count == target_steps)
    incomplete = affected_mask & ~contact & composite_gate & (action_count < target_steps)
    return {
        "contact_contaminated": contact,
        "gate_lost": gate_lost,
        "endpoint": endpoint,
        "incomplete": incomplete,
    }


def a2_hold_validate_open_stabilization_runtime_invariants(
    captured_arm_target: torch.Tensor,
    accumulated_arm_target: torch.Tensor,
    post_delta_arm_target: torch.Tensor,
    stiffness: torch.Tensor,
    damping: torch.Tensor,
    effort_limit: torch.Tensor,
):
    """Fail immediately when a controlled preflight frame violates its fixed command/runtime tuple."""
    arm_values = (accumulated_arm_target, post_delta_arm_target)
    gripper_values = (stiffness, damping, effort_limit)
    if (
        not torch.is_tensor(captured_arm_target)
        or captured_arm_target.ndim != 2
        or captured_arm_target.shape[1] != 6
        or not captured_arm_target.is_floating_point()
        or any(
            not torch.is_tensor(value)
            or value.shape != captured_arm_target.shape
            or not value.is_floating_point()
            or value.dtype != captured_arm_target.dtype
            or value.device != captured_arm_target.device
            or not torch.all(torch.isfinite(value))
            for value in arm_values
        )
        or any(
            not torch.is_tensor(value)
            or value.shape != (captured_arm_target.shape[0], 2)
            or not value.is_floating_point()
            or value.dtype != captured_arm_target.dtype
            or value.device != captured_arm_target.device
            or not torch.all(torch.isfinite(value))
            for value in gripper_values
        )
        or not torch.all(torch.isfinite(captured_arm_target))
    ):
        raise ValueError(
            "open-stabilization runtime invariant inputs require finite same-device "
            "(N,6) arm targets and (N,2) gripper properties."
        )
    accumulated_ok = torch.all(accumulated_arm_target == captured_arm_target, dim=-1)
    if not torch.all(accumulated_ok):
        raise ValueError(
            "accumulated arm target changed from the captured gate target; "
            f"rows={torch.nonzero(~accumulated_ok, as_tuple=False).flatten().detach().cpu().tolist()}."
        )
    post_delta_ok = torch.all(post_delta_arm_target == captured_arm_target, dim=-1)
    if not torch.all(post_delta_ok):
        raise ValueError(
            "authoritative post-delta arm target differs from the captured gate target; "
            f"rows={torch.nonzero(~post_delta_ok, as_tuple=False).flatten().detach().cpu().tolist()}."
        )
    stiffness_ok = torch.all(stiffness == torch.full_like(stiffness, 80.0), dim=-1)
    damping_ok = torch.all(damping == torch.full_like(damping, 3.0), dim=-1)
    effort_ok = torch.all(effort_limit == torch.full_like(effort_limit, 10.0), dim=-1)
    gain_effort_ok = stiffness_ok & damping_ok & effort_ok
    if not torch.all(gain_effort_ok):
        raise ValueError(
            "actual gripper Kp/Kd/effort differs from exact 80/3/10; "
            f"rows={torch.nonzero(~gain_effort_ok, as_tuple=False).flatten().detach().cpu().tolist()}."
        )
    return {
        "accumulated_arm_target_invariant": accumulated_ok,
        "post_delta_arm_target_invariant": post_delta_ok,
        "runtime_gripper_gain_effort_exact": gain_effort_ok,
    }


def a2_hold_aggregate_normal_force_direction(normal_force_w: torch.Tensor):
    """Return aggregate normal-force direction and a validity mask without fabricating zero directions."""
    if not torch.is_tensor(normal_force_w) or normal_force_w.shape[-1] != 3:
        raise ValueError("normal_force_w must be a tensor with trailing dimension 3.")
    norm = torch.linalg.norm(normal_force_w, dim=-1)
    valid = norm > 0.0
    direction = torch.full_like(normal_force_w, float("nan"))
    direction[valid] = normal_force_w[valid] / norm[valid].unsqueeze(-1)
    return direction, valid


def a2_hold_nullable_tensor_list(value: torch.Tensor):
    """Convert an explicitly optional diagnostic tensor to JSON-safe nested values."""
    if not torch.is_tensor(value):
        raise ValueError("nullable diagnostic value must be a tensor.")
    result = value.detach().cpu().tolist()

    def convert(item):
        if isinstance(item, list):
            return [convert(child) for child in item]
        scalar = float(item)
        return scalar if math.isfinite(scalar) else None

    return convert(result)


def a2_hold_contact_sensor_detail_kwargs(enabled: bool, capacity):
    if not isinstance(enabled, bool):
        raise ValueError("contact detail enabled must be bool.")
    if not enabled:
        return {}
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise ValueError("detailed contact capacity must be a positive int.")
    return {
        "track_pose": True,
        "track_contact_points": True,
        "track_friction_forces": True,
        "max_contact_data_count_per_prim": capacity,
    }


def a2_hold_signed_gripper_opening_axes_from_jacobian(
    jacobian: torch.Tensor,
    body_ids: torch.Tensor,
    articulation_joint_ids: torch.Tensor,
    open_target: torch.Tensor,
    close_target: torch.Tensor,
    *,
    floating_base_joint_column_offset: int = 6,
    angular_tolerance: float = 1.0e-6,
):
    """Derive each finger's signed world opening axis from its own prismatic Jacobian column."""
    if (
        not torch.is_tensor(jacobian)
        or jacobian.ndim != 4
        or jacobian.shape[2] != 6
        or not jacobian.is_floating_point()
        or not torch.is_tensor(body_ids)
        or tuple(body_ids.shape) != (2,)
        or body_ids.dtype != torch.long
        or not torch.is_tensor(articulation_joint_ids)
        or tuple(articulation_joint_ids.shape) != (2,)
        or articulation_joint_ids.dtype != torch.long
        or not torch.is_tensor(open_target)
        or tuple(open_target.shape) != (2,)
        or not torch.is_tensor(close_target)
        or tuple(close_target.shape) != (2,)
    ):
        raise ValueError("signed opening-axis inputs have incompatible shapes or dtypes.")
    tensors = (body_ids, articulation_joint_ids, open_target, close_target)
    if any(value.device != jacobian.device for value in tensors):
        raise ValueError("signed opening-axis inputs must be on one common device.")
    if (
        open_target.dtype != jacobian.dtype
        or close_target.dtype != jacobian.dtype
        or not torch.all(torch.isfinite(jacobian))
        or not torch.all(torch.isfinite(open_target))
        or not torch.all(torch.isfinite(close_target))
    ):
        raise ValueError("signed opening-axis floating inputs must share a finite dtype.")
    if (
        isinstance(floating_base_joint_column_offset, bool)
        or not isinstance(floating_base_joint_column_offset, int)
        or floating_base_joint_column_offset != 6
    ):
        raise ValueError("signed opening-axis mapping requires floating-base column offset +6.")
    if (
        isinstance(angular_tolerance, bool)
        or not isinstance(angular_tolerance, (int, float))
        or not math.isfinite(float(angular_tolerance))
        or angular_tolerance < 0.0
    ):
        raise ValueError("signed opening-axis angular tolerance must be finite and non-negative.")
    joint_columns = articulation_joint_ids + floating_base_joint_column_offset
    if (
        torch.any(body_ids < 0)
        or torch.any(body_ids >= jacobian.shape[1])
        or torch.any(articulation_joint_ids < 0)
        or torch.any(joint_columns >= jacobian.shape[3])
    ):
        raise ValueError("signed opening-axis body/joint mapping is outside Jacobian bounds.")
    selected = torch.stack(
        [
            jacobian[:, int(body_ids[index].item()), :, int(joint_columns[index].item())]
            for index in range(2)
        ],
        dim=1,
    )
    linear = selected[:, :, :3]
    angular = selected[:, :, 3:]
    linear_norm = torch.linalg.norm(linear, dim=-1)
    angular_norm = torch.linalg.norm(angular, dim=-1)
    if torch.any(linear_norm <= torch.finfo(jacobian.dtype).eps):
        raise ValueError("signed opening-axis Jacobian linear column is degenerate.")
    if torch.any(angular_norm > float(angular_tolerance)):
        raise ValueError("signed opening-axis Jacobian column is not prismatic (angular component).")
    opening_delta = open_target - close_target
    if torch.any(opening_delta == 0.0):
        raise ValueError("signed opening-axis open-close displacement must be non-zero.")
    opening_sign = torch.sign(opening_delta)
    expected_opening_sign = torch.tensor(
        [1.0, -1.0], device=jacobian.device, dtype=jacobian.dtype
    )
    if not torch.equal(opening_sign, expected_opening_sign):
        raise ValueError(
            "signed opening-axis joint order requires arm_j7 positive and arm_j8 negative; "
            f"got {opening_sign.detach().cpu().tolist()}."
        )
    return linear / linear_norm.unsqueeze(-1) * opening_sign.view(1, 2, 1)


def a2_hold_project_finger_forces_along_opening_axes(
    normal_force_on_handle_w: torch.Tensor,
    friction_force_on_handle_w: torch.Tensor,
    opening_axes_w: torch.Tensor,
):
    """Project force on each finger, not force on the handle, onto its signed opening axis."""
    values = (normal_force_on_handle_w, friction_force_on_handle_w, opening_axes_w)
    if (
        any(not torch.is_tensor(value) or value.ndim != 3 for value in values)
        or normal_force_on_handle_w.shape != friction_force_on_handle_w.shape
        or normal_force_on_handle_w.shape != opening_axes_w.shape
        or normal_force_on_handle_w.shape[1:] != (2, 3)
        or not normal_force_on_handle_w.is_floating_point()
        or any(value.dtype != normal_force_on_handle_w.dtype for value in values[1:])
        or any(value.device != normal_force_on_handle_w.device for value in values[1:])
        or not all(torch.all(torch.isfinite(value)) for value in values)
    ):
        raise ValueError("opening-force projection inputs must be finite same-device (N,2,3) tensors.")
    axis_norm = torch.linalg.norm(opening_axes_w, dim=-1)
    if not torch.allclose(axis_norm, torch.ones_like(axis_norm), atol=1.0e-5, rtol=0.0):
        raise ValueError("opening-force projection axes must be unit length.")
    finger_normal = -normal_force_on_handle_w
    finger_friction = -friction_force_on_handle_w
    finger_total = finger_normal + finger_friction
    return {
        "finger_normal_force_w": finger_normal,
        "finger_friction_force_w": finger_friction,
        "finger_total_force_w": finger_total,
        "finger_normal_force_along_opening_axis": torch.sum(
            finger_normal * opening_axes_w, dim=-1
        ),
        "finger_friction_force_along_opening_axis": torch.sum(
            finger_friction * opening_axes_w, dim=-1
        ),
        "finger_total_force_along_opening_axis": torch.sum(
            finger_total * opening_axes_w, dim=-1
        ),
    }


def a2_hold_static_clamp_step_masks(
    enabled: bool,
    activate_mask: torch.Tensor,
    first_episode_active_mask: torch.Tensor,
    previous_active: torch.Tensor,
    previous_write_count: torch.Tensor,
    target_steps: int,
):
    """Advance static-clamp action writes; count==target completes before action 41."""
    masks = (activate_mask, first_episode_active_mask, previous_active)
    if (
        not isinstance(enabled, bool)
        or any(
            not torch.is_tensor(mask)
            or mask.shape != activate_mask.shape
            or mask.dtype != torch.bool
            or mask.device != activate_mask.device
            for mask in masks
        )
        or not torch.is_tensor(previous_write_count)
        or previous_write_count.shape != activate_mask.shape
        or previous_write_count.dtype != torch.long
        or previous_write_count.device != activate_mask.device
        or torch.any(previous_write_count < 0)
        or isinstance(target_steps, bool)
        or not isinstance(target_steps, int)
        or target_steps <= 0
    ):
        raise ValueError("static-clamp step-state inputs are invalid.")
    if not enabled:
        if torch.any(previous_active) or torch.any(previous_write_count != 0):
            raise ValueError("disabled static-clamp state must remain inactive and zero.")
        zero = torch.zeros_like(previous_active)
        return {
            "entering": zero,
            "override": zero,
            "complete": zero,
            "incomplete": zero,
            "active": previous_active,
            "write_count": previous_write_count,
        }
    if torch.any((previous_write_count != 0) & ~previous_active):
        raise ValueError("inactive static-clamp state cannot retain a live action count.")
    eligible_to_finish = previous_active & (
        (previous_write_count >= target_steps) | ~first_episode_active_mask
    )
    partition = a2_hold_static_clamp_terminal_partition(
        eligible_to_finish, previous_write_count, target_steps
    )
    complete = partition["complete"]
    incomplete = partition["incomplete"]
    entering = activate_mask & first_episode_active_mask & ~previous_active
    working = (previous_active | entering) & first_episode_active_mask
    override = working & ~complete & ~incomplete
    updated_count = previous_write_count.clone()
    updated_count[entering] = 0
    updated_count[override] += 1
    updated_active = override.clone()
    return {
        "entering": entering,
        "override": override,
        "complete": complete,
        "incomplete": incomplete,
        "active": updated_active,
        "write_count": updated_count,
    }


def a2_hold_static_clamp_terminal_partition(
    affected_mask: torch.Tensor,
    action_write_count: torch.Tensor,
    target_steps: int,
):
    """Partition an ending static clamp by completed physics-action count."""
    if (
        not torch.is_tensor(affected_mask)
        or affected_mask.ndim != 1
        or affected_mask.dtype != torch.bool
        or not torch.is_tensor(action_write_count)
        or action_write_count.shape != affected_mask.shape
        or action_write_count.dtype != torch.long
        or action_write_count.device != affected_mask.device
        or torch.any(action_write_count < 0)
        or isinstance(target_steps, bool)
        or not isinstance(target_steps, int)
        or target_steps <= 0
    ):
        raise ValueError("static-clamp terminal partition inputs are invalid.")
    exceeded = affected_mask & (action_write_count > target_steps)
    if torch.any(exceeded):
        raise ValueError(
            "static-clamp action count exceeded its exact target: "
            f"count={action_write_count[exceeded].detach().cpu().tolist()}, "
            f"target={target_steps}."
        )
    return {
        "complete": affected_mask & (action_write_count == target_steps),
        "incomplete": affected_mask & (action_write_count < target_steps),
    }


def a2_hold_offset_terminal_partition(
    affected_mask: torch.Tensor,
    placement_action_count: torch.Tensor,
    target_steps: int,
):
    """Partition terminal placement without treating a completed action 20 as incomplete."""
    if (
        not torch.is_tensor(affected_mask)
        or affected_mask.ndim != 1
        or affected_mask.dtype != torch.bool
        or not torch.is_tensor(placement_action_count)
        or placement_action_count.shape != affected_mask.shape
        or placement_action_count.dtype != torch.long
        or placement_action_count.device != affected_mask.device
        or torch.any(placement_action_count < 0)
        or isinstance(target_steps, bool)
        or not isinstance(target_steps, int)
        or target_steps <= 0
    ):
        raise ValueError("offset placement terminal partition inputs are invalid.")
    exceeded = affected_mask & (placement_action_count > target_steps)
    if torch.any(exceeded):
        raise ValueError(
            "offset placement action count exceeded its exact target: "
            f"count={placement_action_count[exceeded].detach().cpu().tolist()}, "
            f"target={target_steps}."
        )
    return {
        "incomplete": affected_mask & (placement_action_count < target_steps),
        "endpoint_check": affected_mask & (placement_action_count == target_steps),
    }


def a2_hold_target_orientation_semantic(
    offset_probe_enabled: bool,
    matched_clean_reacquisition_preflight_enabled: bool,
) -> str:
    if not isinstance(offset_probe_enabled, bool) or not isinstance(
        matched_clean_reacquisition_preflight_enabled, bool
    ):
        raise ValueError("orientation semantic mode flags must be bool.")
    if offset_probe_enabled and matched_clean_reacquisition_preflight_enabled:
        raise ValueError(
            "offset probe and matched-clean orientation semantics are mutually exclusive."
        )
    if matched_clean_reacquisition_preflight_enabled:
        return A2_HOLD_MATCHED_CLEAN_TARGET_ORIENTATION_SEMANTIC
    if offset_probe_enabled:
        return A2_HOLD_OFFSET_TARGET_ORIENTATION_SEMANTIC
    return A2_HOLD_TARGET_ORIENTATION_SEMANTIC


def a2_hold_apply_static_clamp_action(
    policy_action: torch.Tensor,
    override_mask: torch.Tensor,
):
    if (
        not torch.is_tensor(policy_action)
        or policy_action.ndim != 2
        or policy_action.shape[1] != 12
        or not policy_action.is_floating_point()
        or not torch.all(torch.isfinite(policy_action))
        or not torch.is_tensor(override_mask)
        or override_mask.shape != policy_action.shape[:1]
        or override_mask.dtype != torch.bool
        or override_mask.device != policy_action.device
    ):
        raise ValueError("static-clamp action inputs violate the canonical A2 action contract.")
    if not torch.any(override_mask):
        return policy_action
    action = policy_action.clone()
    action[override_mask, :11] = 0.0
    action[override_mask, 11] = -1.0
    return action


def a2_hold_offset_fixed_world_target(
    gate_source_pos_w: torch.Tensor,
    gate_source_quat_w: torch.Tensor,
    offset_m: float,
):
    """Build one non-accumulating world target along gate source-local +Y."""
    if (
        not torch.is_tensor(gate_source_pos_w)
        or gate_source_pos_w.ndim != 2
        or gate_source_pos_w.shape[1] != 3
        or not torch.is_tensor(gate_source_quat_w)
        or gate_source_quat_w.shape != (gate_source_pos_w.shape[0], 4)
        or not gate_source_pos_w.is_floating_point()
        or gate_source_quat_w.dtype != gate_source_pos_w.dtype
        or gate_source_quat_w.device != gate_source_pos_w.device
        or not torch.all(torch.isfinite(gate_source_pos_w))
        or not torch.all(torch.isfinite(gate_source_quat_w))
        or isinstance(offset_m, bool)
        or not isinstance(offset_m, (int, float))
        or not math.isfinite(float(offset_m))
    ):
        raise ValueError("offset fixed-target inputs must be finite same-dtype poses.")
    quat_norm = torch.linalg.norm(gate_source_quat_w, dim=-1)
    if not torch.allclose(
        quat_norm, torch.ones_like(quat_norm), atol=1.0e-5, rtol=0.0
    ):
        raise ValueError("offset fixed-target source quaternion must be unit length.")
    local_y = torch.zeros_like(gate_source_pos_w)
    local_y[:, 1] = 1.0
    axis_w = quat_apply(gate_source_quat_w, local_y)
    axis_norm = torch.linalg.norm(axis_w, dim=-1)
    if not torch.allclose(
        axis_norm, torch.ones_like(axis_norm), atol=1.0e-5, rtol=0.0
    ):
        raise ValueError("offset fixed-target source +Y axis must be unit length.")
    displacement_w = float(offset_m) * axis_w
    target_pos_w = gate_source_pos_w + displacement_w
    projection = torch.sum(displacement_w * axis_w, dim=-1)
    orthogonal = displacement_w - projection[:, None] * axis_w
    if not torch.allclose(
        projection,
        torch.full_like(projection, float(offset_m)),
        atol=1.0e-7,
        rtol=0.0,
    ) or torch.any(torch.linalg.norm(orthogonal, dim=-1) > 1.0e-7):
        raise ValueError("offset fixed-target displacement decomposition is inconsistent.")
    return axis_w, target_pos_w, gate_source_quat_w.clone()


def a2_hold_validate_offset_axis_opening_dots(
    source_local_y_axis_w: torch.Tensor,
    signed_opening_axes_w: torch.Tensor,
    *,
    alignment_tolerance: float = 1.0e-4,
):
    """Verify source +Y points toward body8 opening and opposite body7 opening."""
    if (
        not torch.is_tensor(source_local_y_axis_w)
        or source_local_y_axis_w.ndim != 2
        or source_local_y_axis_w.shape[1] != 3
        or not torch.is_tensor(signed_opening_axes_w)
        or signed_opening_axes_w.shape != (source_local_y_axis_w.shape[0], 2, 3)
        or not source_local_y_axis_w.is_floating_point()
        or signed_opening_axes_w.dtype != source_local_y_axis_w.dtype
        or signed_opening_axes_w.device != source_local_y_axis_w.device
        or not torch.all(torch.isfinite(source_local_y_axis_w))
        or not torch.all(torch.isfinite(signed_opening_axes_w))
        or isinstance(alignment_tolerance, bool)
        or not isinstance(alignment_tolerance, (int, float))
        or not math.isfinite(float(alignment_tolerance))
        or alignment_tolerance <= 0.0
        or alignment_tolerance >= 1.0
    ):
        raise ValueError("offset/opening-axis validation inputs are invalid.")
    source_norm = torch.linalg.norm(source_local_y_axis_w, dim=-1)
    opening_norm = torch.linalg.norm(signed_opening_axes_w, dim=-1)
    if not torch.allclose(source_norm, torch.ones_like(source_norm), atol=1.0e-5, rtol=0.0):
        raise ValueError("offset source +Y axis must be unit length.")
    if not torch.allclose(opening_norm, torch.ones_like(opening_norm), atol=1.0e-5, rtol=0.0):
        raise ValueError("offset signed opening axes must be unit length.")
    dots = torch.sum(signed_opening_axes_w * source_local_y_axis_w[:, None], dim=-1)
    valid = (dots[:, 0] <= -1.0 + float(alignment_tolerance)) & (
        dots[:, 1] >= 1.0 - float(alignment_tolerance)
    )
    if not torch.all(valid):
        raise ValueError(
            "offset source +Y must oppose body7 opening and align with body8 opening; "
            f"dots={dots[~valid].detach().cpu().tolist()}."
        )
    return dots


def a2_hold_offset_placement_step_masks(
    enabled: bool,
    activate_mask: torch.Tensor,
    first_episode_active_mask: torch.Tensor,
    previous_active: torch.Tensor,
    previous_action_count: torch.Tensor,
    target_steps: int,
):
    """Emit exactly target placement actions, then check on the next control call."""
    masks = (activate_mask, first_episode_active_mask, previous_active)
    if (
        not isinstance(enabled, bool)
        or any(
            not torch.is_tensor(mask)
            or mask.shape != activate_mask.shape
            or mask.dtype != torch.bool
            or mask.device != activate_mask.device
            for mask in masks
        )
        or not torch.is_tensor(previous_action_count)
        or previous_action_count.shape != activate_mask.shape
        or previous_action_count.dtype != torch.long
        or previous_action_count.device != activate_mask.device
        or torch.any(previous_action_count < 0)
        or isinstance(target_steps, bool)
        or not isinstance(target_steps, int)
        or target_steps <= 0
    ):
        raise ValueError("offset placement step-state inputs are invalid.")
    if not enabled:
        if torch.any(previous_active) or torch.any(previous_action_count != 0):
            raise ValueError("disabled offset placement state must remain inactive and zero.")
        zero = torch.zeros_like(previous_active)
        return {
            "entering": zero,
            "override": zero,
            "endpoint_check": zero,
            "incomplete": zero,
            "active": previous_active,
            "action_count": previous_action_count,
        }
    if torch.any((previous_action_count != 0) & ~previous_active):
        raise ValueError("inactive offset placement cannot retain a live action count.")
    overrun = previous_active & (previous_action_count > target_steps)
    if torch.any(overrun):
        raise ValueError(
            "offset placement action count exceeded its exact target: "
            f"{previous_action_count[overrun].detach().cpu().tolist()}."
        )
    endpoint_check = (
        previous_active
        & first_episode_active_mask
        & (previous_action_count == target_steps)
    )
    incomplete = previous_active & ~first_episode_active_mask
    entering = activate_mask & first_episode_active_mask & ~previous_active
    working = (previous_active | entering) & first_episode_active_mask
    override = working & ~endpoint_check
    updated_count = previous_action_count.clone()
    updated_count[entering] = 0
    updated_count[override] += 1
    return {
        "entering": entering,
        "override": override,
        "endpoint_check": endpoint_check,
        "incomplete": incomplete,
        "active": override.clone(),
        "action_count": updated_count,
    }


def a2_hold_apply_offset_placement_action(
    policy_action: torch.Tensor,
    placement_mask: torch.Tensor,
    arm_raw_action: torch.Tensor,
):
    if (
        not torch.is_tensor(policy_action)
        or policy_action.ndim != 2
        or policy_action.shape[1] != 12
        or not policy_action.is_floating_point()
        or not torch.all(torch.isfinite(policy_action))
        or not torch.is_tensor(placement_mask)
        or placement_mask.shape != policy_action.shape[:1]
        or placement_mask.dtype != torch.bool
        or placement_mask.device != policy_action.device
        or not torch.is_tensor(arm_raw_action)
        or arm_raw_action.shape != (policy_action.shape[0], 6)
        or arm_raw_action.dtype != policy_action.dtype
        or arm_raw_action.device != policy_action.device
        or not torch.all(torch.isfinite(arm_raw_action))
    ):
        raise ValueError("offset placement action inputs violate the A2 action contract.")
    if not torch.any(placement_mask):
        return policy_action
    action = policy_action.clone()
    action[placement_mask, :5] = 0.0
    action[placement_mask, 5:11] = arm_raw_action[placement_mask]
    action[placement_mask, 11] = 1.0
    return action


def a2_hold_offset_endpoint_metrics(
    current_source_pos_w: torch.Tensor,
    current_source_quat_w: torch.Tensor,
    gate_source_pos_w: torch.Tensor,
    fixed_target_pos_w: torch.Tensor,
    fixed_target_quat_w: torch.Tensor,
    source_local_y_axis_w: torch.Tensor,
    requested_offset_m: float,
    position_tolerance_m: float,
    orientation_tolerance_rad: float,
):
    values = (
        current_source_pos_w,
        current_source_quat_w,
        gate_source_pos_w,
        fixed_target_pos_w,
        fixed_target_quat_w,
        source_local_y_axis_w,
    )
    n = current_source_pos_w.shape[0] if torch.is_tensor(current_source_pos_w) else -1
    expected_shapes = ((n, 3), (n, 4), (n, 3), (n, 3), (n, 4), (n, 3))
    if (
        n < 0
        or any(
            not torch.is_tensor(value)
            or value.shape != shape
            or not value.is_floating_point()
            or value.dtype != current_source_pos_w.dtype
            or value.device != current_source_pos_w.device
            or not torch.all(torch.isfinite(value))
            for value, shape in zip(values, expected_shapes, strict=True)
        )
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in (
                requested_offset_m,
                position_tolerance_m,
                orientation_tolerance_rad,
            )
        )
        or position_tolerance_m <= 0.0
        or orientation_tolerance_rad <= 0.0
    ):
        raise ValueError("offset endpoint metric inputs are invalid.")
    axis_norm = torch.linalg.norm(source_local_y_axis_w, dim=-1)
    quat_norms = (
        torch.linalg.norm(current_source_quat_w, dim=-1),
        torch.linalg.norm(fixed_target_quat_w, dim=-1),
    )
    if not torch.allclose(axis_norm, torch.ones_like(axis_norm), atol=1.0e-5, rtol=0.0):
        raise ValueError("offset endpoint axis must be unit length.")
    if any(
        not torch.allclose(norm, torch.ones_like(norm), atol=1.0e-5, rtol=0.0)
        for norm in quat_norms
    ):
        raise ValueError("offset endpoint quaternions must be unit length.")
    achieved_delta = current_source_pos_w - gate_source_pos_w
    achieved_signed_offset = torch.sum(achieved_delta * source_local_y_axis_w, dim=-1)
    orthogonal = achieved_delta - achieved_signed_offset[:, None] * source_local_y_axis_w
    orthogonal_residual = torch.linalg.norm(orthogonal, dim=-1)
    position_residual = torch.linalg.norm(fixed_target_pos_w - current_source_pos_w, dim=-1)
    quat_dot = torch.abs(torch.sum(current_source_quat_w * fixed_target_quat_w, dim=-1))
    orientation_residual = 2.0 * torch.acos(quat_dot.clamp(max=1.0))
    signed_offset_error = torch.abs(achieved_signed_offset - float(requested_offset_m))
    converged = (
        (position_residual <= float(position_tolerance_m))
        & (orientation_residual <= float(orientation_tolerance_rad))
        & (signed_offset_error <= float(position_tolerance_m))
    )
    return {
        "achieved_signed_offset_m": achieved_signed_offset,
        "signed_offset_error_m": signed_offset_error,
        "orthogonal_residual_m": orthogonal_residual,
        "position_residual_m": position_residual,
        "orientation_residual_rad": orientation_residual,
        "converged": converged,
    }


def a2_hold_validate_friction_override(value):
    if value is None:
        return None
    raise ValueError(
        "a2_hold_diagnostic_friction_override is unsupported for the instanceable "
        "Piper collider; conditional friction implementation is deferred until the "
        "measured-midpoint diagnostic produces CONTACT_SLIP."
    )


def a2_hold_map_task_to_articulation_joint_ids(
    simulator_dof_ids,
    task_joint_indices: torch.Tensor,
    task_dof_names,
    articulation_joint_count: int,
    device,
):
    if (
        not isinstance(simulator_dof_ids, list)
        or len(simulator_dof_ids) != len(task_dof_names)
        or len(set(simulator_dof_ids)) != len(simulator_dof_ids)
        or any(not isinstance(joint_id, int) for joint_id in simulator_dof_ids)
    ):
        raise ValueError("simulator_dof_ids must be a unique list[int] matching task DOFs.")
    if (
        not torch.is_tensor(task_joint_indices)
        or tuple(task_joint_indices.shape) != (2,)
        or task_joint_indices.dtype != torch.long
    ):
        raise ValueError("gripper task indices must be a long tensor shape (2,).")
    indices = task_joint_indices.detach().cpu().tolist()
    if any(index < 0 or index >= len(task_dof_names) for index in indices):
        raise ValueError("gripper task indices are outside task DOF order.")
    names = [task_dof_names[index] for index in indices]
    if names != ["arm_j7", "arm_j8"]:
        raise ValueError(f"gripper task order must be arm_j7,arm_j8; got {names}.")
    articulation_ids = [simulator_dof_ids[index] for index in indices]
    if any(joint_id < 0 or joint_id >= articulation_joint_count for joint_id in articulation_ids):
        raise ValueError("mapped gripper articulation ids are out of range.")
    return torch.tensor(articulation_ids, dtype=torch.long, device=device)


def a2_hold_pd_effort_estimates(
    joint_pos: torch.Tensor,
    joint_vel: torch.Tensor,
    joint_pos_target: torch.Tensor,
    stiffness: torch.Tensor,
    damping: torch.Tensor,
    effort_limit: torch.Tensor,
):
    expected_shape = joint_pos.shape
    fields = (joint_vel, joint_pos_target, stiffness, damping, effort_limit)
    if not torch.is_tensor(joint_pos) or any(
        not torch.is_tensor(field) or field.shape != expected_shape for field in fields
    ):
        raise ValueError("PD effort estimate inputs must be tensors with identical shapes.")
    if torch.any(effort_limit <= 0.0):
        raise ValueError("PD effort limits must be positive.")
    unclipped = stiffness * (joint_pos_target - joint_pos) - damping * joint_vel
    clipped = torch.clamp(unclipped, min=-effort_limit, max=effort_limit)
    saturated = torch.abs(unclipped) > effort_limit
    return unclipped, clipped, saturated


def a2_hold_apply_source_offset_to_jacobian(
    jacobian_root: torch.Tensor, source_offset_pos: torch.Tensor
) -> torch.Tensor:
    """Apply the same body-offset correction as IsaacLab DifferentialIKAction."""
    if not torch.is_tensor(jacobian_root) or jacobian_root.ndim != 3 or jacobian_root.shape[1] != 6:
        raise ValueError("jacobian_root must have shape (N, 6, J).")
    if (
        not torch.is_tensor(source_offset_pos)
        or source_offset_pos.shape != (jacobian_root.shape[0], 3)
        or source_offset_pos.device != jacobian_root.device
    ):
        raise ValueError("source_offset_pos must have shape (N, 3) on the Jacobian device.")
    corrected = jacobian_root.clone()
    corrected[:, 0:3, :] += torch.bmm(
        -skew_symmetric_matrix(source_offset_pos), corrected[:, 3:, :]
    )
    return corrected


def a2_hold_rotate_jacobian_to_root(
    jacobian_w: torch.Tensor, root_quat_w: torch.Tensor
) -> torch.Tensor:
    if not torch.is_tensor(jacobian_w) or jacobian_w.ndim != 3 or jacobian_w.shape[1] != 6:
        raise ValueError("jacobian_w must have shape (N, 6, J).")
    if (
        not torch.is_tensor(root_quat_w)
        or root_quat_w.shape != (jacobian_w.shape[0], 4)
        or root_quat_w.device != jacobian_w.device
    ):
        raise ValueError("root_quat_w must have shape (N, 4) on the Jacobian device.")
    rotation = matrix_from_quat(quat_inv(root_quat_w))
    jacobian_root = jacobian_w.clone()
    jacobian_root[:, :3] = torch.bmm(rotation, jacobian_w[:, :3])
    jacobian_root[:, 3:] = torch.bmm(rotation, jacobian_w[:, 3:])
    return jacobian_root


def a2_hold_absolute_target_to_cumulative_action(
    q_des: torch.Tensor,
    q_default: torch.Tensor,
    d_prev: torch.Tensor,
    *,
    robot_action_scale: float = 0.25,
    delta_action_scale: float = 0.3,
):
    if not all(torch.is_tensor(value) for value in (q_des, q_default, d_prev)):
        raise ValueError("q_des, q_default and d_prev must be tensors.")
    if q_des.shape != q_default.shape or q_des.shape != d_prev.shape:
        raise ValueError("q_des, q_default and d_prev must have identical shapes.")
    if robot_action_scale != 0.25 or delta_action_scale != 0.3:
        raise ValueError(
            "A2 hold oracle cumulative conversion requires action_scale=0.25 and delta_scale=0.3."
        )
    d_des = (q_des - q_default) / robot_action_scale
    raw_action = (d_des - d_prev) / delta_action_scale
    return d_des, raw_action


def a2_hold_center_transition_masks(
    center_mask: torch.Tensor,
    bilateral_gate: torch.Tensor,
    phase_step: torch.Tensor,
    timeout_steps: int,
    single_body7: torch.Tensor,
    single_body8: torch.Tensor,
    converged: torch.Tensor,
):
    tensors = (bilateral_gate, phase_step, single_body7, single_body8, converged)
    if not torch.is_tensor(center_mask) or any(
        not torch.is_tensor(value) or value.shape != center_mask.shape for value in tensors
    ):
        raise ValueError("A2 hold center transition inputs must have identical shapes.")
    if center_mask.dtype != torch.bool or bilateral_gate.dtype != torch.bool:
        raise ValueError("A2 hold center masks must be bool.")
    if isinstance(timeout_steps, bool) or not isinstance(timeout_steps, int) or timeout_steps <= 0:
        raise ValueError("A2 hold center timeout must be a positive int.")
    ready = center_mask & bilateral_gate & converged
    timeout = center_mask & ~ready & (phase_step >= timeout_steps)
    tracking_failure = timeout & ~converged
    wedge = timeout & converged & (single_body7 | single_body8)
    return ready, tracking_failure, wedge, timeout & converged & ~wedge


def a2_hold_center_converged(
    position_residual: torch.Tensor,
    orientation_residual: torch.Tensor,
    position_tolerance: float,
    orientation_tolerance: float,
) -> torch.Tensor:
    if (
        not torch.is_tensor(position_residual)
        or not torch.is_tensor(orientation_residual)
        or position_residual.shape != orientation_residual.shape
    ):
        raise ValueError("center residual tensors must have identical shapes.")
    return (
        torch.isfinite(position_residual)
        & torch.isfinite(orientation_residual)
        & (position_residual <= position_tolerance)
        & (orientation_residual <= orientation_tolerance)
    )


def a2_hold_capture_handoff_relative_orientation(
    handle_pos_w: torch.Tensor,
    handle_quat_w: torch.Tensor,
    source_pos_w: torch.Tensor,
    source_quat_w: torch.Tensor,
    capture_mask: torch.Tensor,
    relative_quat_state: torch.Tensor,
    captured_mask: torch.Tensor,
):
    frame_tensors = (
        handle_pos_w,
        handle_quat_w,
        source_pos_w,
        source_quat_w,
        relative_quat_state,
    )
    if (
        not all(torch.is_tensor(value) for value in frame_tensors)
        or handle_pos_w.ndim != 2
        or handle_pos_w.shape[1] != 3
        or source_pos_w.shape != handle_pos_w.shape
        or handle_quat_w.shape != (handle_pos_w.shape[0], 4)
        or source_quat_w.shape != handle_quat_w.shape
        or relative_quat_state.shape != handle_quat_w.shape
        or not torch.is_tensor(capture_mask)
        or not torch.is_tensor(captured_mask)
        or capture_mask.shape != (handle_pos_w.shape[0],)
        or captured_mask.shape != capture_mask.shape
        or capture_mask.dtype != torch.bool
        or captured_mask.dtype != torch.bool
    ):
        raise ValueError("handoff capture inputs have incompatible shapes or mask dtypes.")
    if not handle_pos_w.is_floating_point() or any(
        value.dtype != handle_pos_w.dtype for value in frame_tensors[1:]
    ):
        raise ValueError("handoff capture frame inputs must have one common floating dtype.")
    if any(value.device != handle_pos_w.device for value in frame_tensors[1:]) or any(
        mask.device != handle_pos_w.device for mask in (capture_mask, captured_mask)
    ):
        raise ValueError("handoff capture inputs must be on one common device.")
    if not all(
        torch.all(torch.isfinite(value))
        for value in (handle_pos_w, handle_quat_w, source_pos_w, source_quat_w)
    ):
        raise ValueError("handoff capture frame inputs must be finite.")
    if torch.any(captured_mask & ~torch.all(torch.isfinite(relative_quat_state), dim=-1)):
        raise ValueError("captured handoff-relative quaternion state must be finite.")
    if torch.any(capture_mask & captured_mask):
        raise ValueError("handoff-relative orientation cannot be captured twice.")
    updated_relative_quat = relative_quat_state.clone()
    updated_captured_mask = captured_mask.clone()
    if torch.any(capture_mask):
        _, relative_quat = subtract_frame_transforms(
            handle_pos_w[capture_mask],
            handle_quat_w[capture_mask],
            source_pos_w[capture_mask],
            source_quat_w[capture_mask],
        )
        if not torch.all(torch.isfinite(relative_quat)):
            raise ValueError("captured handoff-relative quaternion must be finite.")
        updated_relative_quat[capture_mask] = relative_quat
        updated_captured_mask[capture_mask] = True
    return updated_relative_quat, updated_captured_mask


def a2_hold_compose_handoff_target_orientation(
    handle_pos_w: torch.Tensor,
    handle_quat_w: torch.Tensor,
    source_quat_w: torch.Tensor,
    relative_quat_state: torch.Tensor,
    active_mask: torch.Tensor,
    captured_mask: torch.Tensor,
):
    frame_tensors = (handle_pos_w, handle_quat_w, source_quat_w, relative_quat_state)
    if (
        not all(torch.is_tensor(value) for value in frame_tensors)
        or handle_pos_w.ndim != 2
        or handle_pos_w.shape[1] != 3
        or handle_quat_w.shape != (handle_pos_w.shape[0], 4)
        or source_quat_w.shape != handle_quat_w.shape
        or relative_quat_state.shape != handle_quat_w.shape
        or not torch.is_tensor(active_mask)
        or not torch.is_tensor(captured_mask)
        or active_mask.shape != (handle_pos_w.shape[0],)
        or captured_mask.shape != active_mask.shape
        or active_mask.dtype != torch.bool
        or captured_mask.dtype != torch.bool
    ):
        raise ValueError("handoff target inputs have incompatible shapes or mask dtypes.")
    if not handle_pos_w.is_floating_point() or any(
        value.dtype != handle_pos_w.dtype for value in frame_tensors[1:]
    ):
        raise ValueError("handoff target frame inputs must have one common floating dtype.")
    if any(value.device != handle_pos_w.device for value in frame_tensors[1:]) or any(
        mask.device != handle_pos_w.device for mask in (active_mask, captured_mask)
    ):
        raise ValueError("handoff target inputs must be on one common device.")
    if not all(
        torch.all(torch.isfinite(value))
        for value in (handle_pos_w, handle_quat_w, source_quat_w)
    ):
        raise ValueError("handoff target frame inputs must be finite.")
    if torch.any(active_mask & ~captured_mask):
        raise ValueError("active handoff target requested before relative orientation capture.")
    if torch.any(captured_mask & ~torch.all(torch.isfinite(relative_quat_state), dim=-1)):
        raise ValueError("captured handoff-relative quaternion state must be finite.")
    target_quat_w = source_quat_w.clone()
    if torch.any(active_mask):
        zero_relative_pos = torch.zeros_like(handle_pos_w[active_mask])
        _, active_target_quat_w = combine_frame_transforms(
            handle_pos_w[active_mask],
            handle_quat_w[active_mask],
            zero_relative_pos,
            relative_quat_state[active_mask],
        )
        if not torch.all(torch.isfinite(active_target_quat_w)):
            raise ValueError("composed handoff target quaternion must be finite.")
        target_quat_w[active_mask] = active_target_quat_w
    return target_quat_w


def a2_hold_bound_pose_command_step(
    current_pos: torch.Tensor,
    current_quat: torch.Tensor,
    final_pos: torch.Tensor,
    final_quat: torch.Tensor,
    max_position_step_m: float,
    max_orientation_step_rad: float,
):
    if (
        not all(torch.is_tensor(value) for value in (current_pos, current_quat, final_pos, final_quat))
        or current_pos.shape != final_pos.shape
        or current_quat.shape != final_quat.shape
        or current_pos.ndim != 2
        or current_pos.shape[1] != 3
        or current_quat.ndim != 2
        or current_quat.shape[1] != 4
        or current_pos.shape[0] != current_quat.shape[0]
    ):
        raise ValueError("pose-step inputs must be batched positions (N,3) and quaternions (N,4).")
    pose_tensors = (current_pos, current_quat, final_pos, final_quat)
    if not current_pos.is_floating_point() or any(
        value.dtype != current_pos.dtype for value in pose_tensors[1:]
    ):
        raise ValueError("pose-step inputs must have one common floating dtype.")
    if any(value.device != current_pos.device for value in pose_tensors[1:]):
        raise ValueError("pose-step inputs must be on one common device.")
    if not all(
        torch.all(torch.isfinite(value))
        for value in pose_tensors
    ):
        raise ValueError("pose-step inputs must be finite.")
    for name, value in (
        ("max_position_step_m", max_position_step_m),
        ("max_orientation_step_rad", max_orientation_step_rad),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0.0:
            raise ValueError(f"{name} must be a finite positive float.")
    position_error, orientation_error = compute_pose_error(
        current_pos,
        current_quat,
        final_pos,
        final_quat,
        rot_error_type="axis_angle",
    )
    position_norm = torch.linalg.norm(position_error, dim=-1)
    orientation_norm = torch.linalg.norm(orientation_error, dim=-1)
    eps = torch.finfo(current_pos.dtype).eps
    position_scale = torch.minimum(
        torch.ones_like(position_norm),
        float(max_position_step_m) / position_norm.clamp_min(eps),
    )
    orientation_scale = torch.minimum(
        torch.ones_like(orientation_norm),
        float(max_orientation_step_rad) / orientation_norm.clamp_min(eps),
    )
    bounded_delta = torch.cat(
        (
            position_error * position_scale.unsqueeze(-1),
            orientation_error * orientation_scale.unsqueeze(-1),
        ),
        dim=-1,
    )
    command_pos, command_quat = apply_delta_pose(current_pos, current_quat, bounded_delta)
    return command_pos, command_quat, position_norm, orientation_norm, bounded_delta


def a2_hold_progress_aware_joint_limit_masks(
    current_q: torch.Tensor,
    q_des: torch.Tensor,
    hard_limits: torch.Tensor,
    soft_limits: torch.Tensor,
    hard_margin: float,
    soft_margin: float,
    progress_tolerance: float,
):
    if (
        not all(torch.is_tensor(value) for value in (current_q, q_des, hard_limits, soft_limits))
        or current_q.shape != q_des.shape
        or hard_limits.shape != (*current_q.shape, 2)
        or soft_limits.shape != (*current_q.shape, 2)
    ):
        raise ValueError("joint-limit inputs have incompatible shapes.")
    limit_tensors = (current_q, q_des, hard_limits, soft_limits)
    if not current_q.is_floating_point() or any(
        value.dtype != current_q.dtype for value in limit_tensors[1:]
    ):
        raise ValueError("joint-limit inputs must have one common floating dtype.")
    if any(value.device != current_q.device for value in limit_tensors[1:]):
        raise ValueError("joint-limit inputs must be on one common device.")
    if not all(torch.all(torch.isfinite(value)) for value in limit_tensors):
        raise ValueError("joint-limit inputs must be finite.")
    for name, value in (
        ("hard_margin", hard_margin),
        ("soft_margin", soft_margin),
        ("progress_tolerance", progress_tolerance),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0.0:
            raise ValueError(f"{name} must be a finite non-negative float.")
    hard_lower = hard_limits[..., 0] + float(hard_margin)
    hard_upper = hard_limits[..., 1] - float(hard_margin)
    soft_lower = soft_limits[..., 0] + float(soft_margin)
    soft_upper = soft_limits[..., 1] - float(soft_margin)
    if torch.any(hard_lower >= hard_upper) or torch.any(soft_lower >= soft_upper):
        raise ValueError("joint-limit margins collapse a valid interval.")
    hard_valid_per_joint = (q_des > hard_lower) & (q_des < hard_upper)
    current_inside_soft = (current_q >= soft_lower) & (current_q <= soft_upper)
    desired_inside_soft = (q_des >= soft_lower) & (q_des <= soft_upper)
    current_below_soft = current_q < soft_lower
    current_above_soft = current_q > soft_upper
    moves_not_farther_below = q_des >= current_q - float(progress_tolerance)
    moves_not_farther_above = q_des <= current_q + float(progress_tolerance)
    soft_valid_per_joint = torch.where(
        current_inside_soft,
        desired_inside_soft,
        torch.where(
            current_below_soft,
            moves_not_farther_below & (q_des <= soft_upper),
            moves_not_farther_above & (q_des >= soft_lower),
        ),
    )
    hard_valid = torch.all(hard_valid_per_joint, dim=-1)
    soft_progress_valid = torch.all(soft_valid_per_joint, dim=-1)
    return hard_valid & soft_progress_valid, hard_valid, soft_progress_valid


def a2_hold_base_relief_branch_masks(
    active: torch.Tensor,
    ik_valid: torch.Tensor,
    limit_valid: torch.Tensor,
    delta_valid: torch.Tensor,
    raw_valid: torch.Tensor,
    horizontal_solvable: torch.Tensor,
):
    masks = (active, ik_valid, limit_valid, delta_valid, raw_valid, horizontal_solvable)
    if any(
        not torch.is_tensor(mask)
        or mask.shape != active.shape
        or mask.dtype != torch.bool
        or mask.device != active.device
        for mask in masks
    ):
        raise ValueError("base-relief branch inputs must be same-device bool masks of one shape.")
    ik_invalid = active & ~ik_valid
    limit_infeasible = active & ik_valid & ~limit_valid
    joint_limit = limit_infeasible & ~horizontal_solvable
    relief = limit_infeasible & horizontal_solvable
    action_invalid = active & ik_valid & limit_valid & ~(delta_valid & raw_valid)
    arm_dls = active & ik_valid & limit_valid & delta_valid & raw_valid
    return arm_dls, relief, ik_invalid, joint_limit, action_invalid


def a2_hold_base_relief_command(
    horizontal_error_w: torch.Tensor,
    root_quat_w: torch.Tensor,
    candidate_mask: torch.Tensor,
    physical_speed_mps: float,
    base_command_scale: float,
    min_solvable_horizontal_error_m: float,
):
    if (
        not torch.is_tensor(horizontal_error_w)
        or horizontal_error_w.ndim != 2
        or horizontal_error_w.shape[1] != 2
        or not torch.is_tensor(root_quat_w)
        or root_quat_w.shape != (horizontal_error_w.shape[0], 4)
        or not torch.is_tensor(candidate_mask)
        or candidate_mask.shape != (horizontal_error_w.shape[0],)
        or candidate_mask.dtype != torch.bool
    ):
        raise ValueError("base-relief command inputs have incompatible shapes or mask dtype.")
    if not horizontal_error_w.is_floating_point() or root_quat_w.dtype != horizontal_error_w.dtype:
        raise ValueError("base-relief frame inputs must have one common floating dtype.")
    if (
        root_quat_w.device != horizontal_error_w.device
        or candidate_mask.device != horizontal_error_w.device
    ):
        raise ValueError("base-relief command inputs must be on one common device.")
    if not torch.all(torch.isfinite(horizontal_error_w)) or not torch.all(
        torch.isfinite(root_quat_w)
    ):
        raise ValueError("base-relief frame inputs must be finite.")
    for name, value in (
        ("physical_speed_mps", physical_speed_mps),
        ("base_command_scale", base_command_scale),
        ("min_solvable_horizontal_error_m", min_solvable_horizontal_error_m),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value <= 0.0
        ):
            raise ValueError(f"{name} must be a finite positive float.")
    horizontal_residual = torch.linalg.norm(horizontal_error_w, dim=-1)
    horizontal_solvable = horizontal_residual >= float(min_solvable_horizontal_error_m)
    commanded_body_velocity = torch.zeros_like(horizontal_error_w)
    commanded_raw_base = torch.zeros(
        horizontal_error_w.shape[0],
        5,
        device=horizontal_error_w.device,
        dtype=horizontal_error_w.dtype,
    )
    command_mask = candidate_mask & horizontal_solvable
    if torch.any(command_mask):
        velocity_w = torch.zeros(
            horizontal_error_w.shape[0],
            3,
            device=horizontal_error_w.device,
            dtype=horizontal_error_w.dtype,
        )
        velocity_w[command_mask, :2] = (
            horizontal_error_w[command_mask]
            / horizontal_residual[command_mask].unsqueeze(-1)
            * float(physical_speed_mps)
        )
        velocity_body = quat_apply_inverse(
            yaw_quat(root_quat_w), velocity_w
        )
        commanded_body_velocity[command_mask] = velocity_body[command_mask, :2]
        commanded_raw_base[command_mask, :2] = (
            velocity_body[command_mask, :2] / float(base_command_scale)
        )
    return (
        horizontal_residual,
        horizontal_solvable,
        commanded_body_velocity,
        commanded_raw_base,
    )


def a2_hold_update_base_relief_state(
    relief_mask: torch.Tensor,
    previous_active: torch.Tensor,
    previous_steps: torch.Tensor,
    previous_initial_residual: torch.Tensor,
    previous_start_root_xy: torch.Tensor,
    current_residual: torch.Tensor,
    current_root_xy: torch.Tensor,
    sign_window_steps: int,
    min_residual_decrease_m: float,
    timeout_steps: int,
    max_displacement_m: float,
):
    num_envs = relief_mask.shape[0] if torch.is_tensor(relief_mask) and relief_mask.ndim == 1 else -1
    if (
        num_envs < 0
        or not torch.is_tensor(previous_active)
        or previous_active.shape != (num_envs,)
        or relief_mask.dtype != torch.bool
        or previous_active.dtype != torch.bool
        or not torch.is_tensor(previous_steps)
        or previous_steps.shape != (num_envs,)
        or previous_steps.dtype != torch.long
        or not torch.is_tensor(previous_initial_residual)
        or previous_initial_residual.shape != (num_envs,)
        or not torch.is_tensor(previous_start_root_xy)
        or previous_start_root_xy.shape != (num_envs, 2)
        or not torch.is_tensor(current_residual)
        or current_residual.shape != (num_envs,)
        or not torch.is_tensor(current_root_xy)
        or current_root_xy.shape != (num_envs, 2)
    ):
        raise ValueError("base-relief state inputs have incompatible shapes or dtypes.")
    floating = (previous_initial_residual, previous_start_root_xy, current_residual, current_root_xy)
    if not current_residual.is_floating_point() or any(
        value.dtype != current_residual.dtype for value in floating
    ):
        raise ValueError("base-relief state values must have one common floating dtype.")
    tensors = (previous_active, previous_steps, *floating)
    if any(value.device != relief_mask.device for value in tensors):
        raise ValueError("base-relief state inputs must be on one common device.")
    if not torch.all(torch.isfinite(current_residual)) or not torch.all(
        torch.isfinite(current_root_xy)
    ):
        raise ValueError("current base-relief state inputs must be finite.")
    if torch.any(previous_active & ~torch.isfinite(previous_initial_residual)) or torch.any(
        previous_active & ~torch.all(torch.isfinite(previous_start_root_xy), dim=-1)
    ):
        raise ValueError("active previous base-relief state must be finite.")
    if (
        isinstance(sign_window_steps, bool)
        or not isinstance(sign_window_steps, int)
        or sign_window_steps <= 0
        or isinstance(timeout_steps, bool)
        or not isinstance(timeout_steps, int)
        or timeout_steps <= sign_window_steps
    ):
        raise ValueError("base-relief timeout must be greater than its positive sign window.")
    for name, value in (
        ("min_residual_decrease_m", min_residual_decrease_m),
        ("max_displacement_m", max_displacement_m),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value <= 0.0
        ):
            raise ValueError(f"{name} must be a finite positive float.")

    entering = relief_mask & ~previous_active
    continuing = relief_mask & previous_active
    cleared = ~relief_mask & previous_active
    updated_active = relief_mask.clone()
    updated_steps = previous_steps.clone()
    updated_initial_residual = previous_initial_residual.clone()
    updated_start_root_xy = previous_start_root_xy.clone()
    updated_steps[entering] = 0
    updated_initial_residual[entering] = current_residual[entering]
    updated_start_root_xy[entering] = current_root_xy[entering]
    updated_steps[continuing] += 1
    updated_steps[cleared] = 0
    updated_initial_residual[cleared] = float("nan")
    updated_start_root_xy[cleared] = float("nan")
    decrease = updated_initial_residual - current_residual
    displacement = torch.linalg.norm(current_root_xy - updated_start_root_xy, dim=-1)
    wrong_sign = (
        continuing
        & (updated_steps == sign_window_steps)
        & (decrease < float(min_residual_decrease_m))
    )
    timeout = continuing & (updated_steps >= timeout_steps)
    displacement_limit = relief_mask & (displacement > float(max_displacement_m))
    return {
        "active": updated_active,
        "steps": updated_steps,
        "initial_residual": updated_initial_residual,
        "start_root_xy": updated_start_root_xy,
        "current_residual": torch.where(
            relief_mask, current_residual, torch.full_like(current_residual, float("nan"))
        ),
        "entered": entering,
        "cleared": cleared,
        "wrong_sign": wrong_sign,
        "timeout": timeout,
        "displacement_limit": displacement_limit,
    }


def a2_hold_clear_base_relief_state(
    clear_mask: torch.Tensor,
    active: torch.Tensor,
    branch_applied: torch.Tensor,
    steps: torch.Tensor,
    initial_residual: torch.Tensor,
    current_residual: torch.Tensor,
    start_root_xy: torch.Tensor,
    body_velocity_command: torch.Tensor,
    raw_command: torch.Tensor,
):
    num_envs = clear_mask.shape[0] if torch.is_tensor(clear_mask) and clear_mask.ndim == 1 else -1
    if (
        num_envs < 0
        or clear_mask.dtype != torch.bool
        or not torch.is_tensor(active)
        or active.shape != (num_envs,)
        or active.dtype != torch.bool
        or not torch.is_tensor(branch_applied)
        or branch_applied.shape != (num_envs,)
        or branch_applied.dtype != torch.bool
        or not torch.is_tensor(steps)
        or steps.shape != (num_envs,)
        or steps.dtype != torch.long
        or not torch.is_tensor(initial_residual)
        or initial_residual.shape != (num_envs,)
        or not torch.is_tensor(current_residual)
        or current_residual.shape != (num_envs,)
        or not torch.is_tensor(start_root_xy)
        or start_root_xy.shape != (num_envs, 2)
        or not torch.is_tensor(body_velocity_command)
        or body_velocity_command.shape != (num_envs, 2)
        or not torch.is_tensor(raw_command)
        or raw_command.shape != (num_envs, 5)
    ):
        raise ValueError("base-relief clear inputs have incompatible shapes or dtypes.")
    state_tensors = (
        active,
        branch_applied,
        steps,
        initial_residual,
        current_residual,
        start_root_xy,
        body_velocity_command,
        raw_command,
    )
    if any(value.device != clear_mask.device for value in state_tensors):
        raise ValueError("base-relief clear inputs must be on one common device.")
    floating = (
        initial_residual,
        current_residual,
        start_root_xy,
        body_velocity_command,
        raw_command,
    )
    if not initial_residual.is_floating_point() or any(
        value.dtype != initial_residual.dtype for value in floating[1:]
    ):
        raise ValueError("base-relief clear values must have one common floating dtype.")
    if torch.any(steps < 0) or not torch.all(torch.isfinite(body_velocity_command)) or not torch.all(
        torch.isfinite(raw_command)
    ):
        raise ValueError("base-relief clear steps and commands must be valid.")
    if torch.any(active & ~torch.isfinite(initial_residual)) or torch.any(
        active & ~torch.isfinite(current_residual)
    ) or torch.any(active & ~torch.all(torch.isfinite(start_root_xy), dim=-1)):
        raise ValueError("active base-relief state must be finite before clear.")
    result = {
        "active": active.clone(),
        "branch_applied": branch_applied.clone(),
        "steps": steps.clone(),
        "initial_residual": initial_residual.clone(),
        "current_residual": current_residual.clone(),
        "start_root_xy": start_root_xy.clone(),
        "body_velocity_command": body_velocity_command.clone(),
        "raw_command": raw_command.clone(),
    }
    result["active"][clear_mask] = False
    result["branch_applied"][clear_mask] = False
    result["steps"][clear_mask] = 0
    result["initial_residual"][clear_mask] = float("nan")
    result["current_residual"][clear_mask] = float("nan")
    result["start_root_xy"][clear_mask] = float("nan")
    result["body_velocity_command"][clear_mask] = 0.0
    result["raw_command"][clear_mask] = 0.0
    return result


def a2_hold_apply_oracle_branch_actions(
    action: torch.Tensor,
    arm_dls_mask: torch.Tensor,
    relief_mask: torch.Tensor,
    arm_action_raw: torch.Tensor,
    relief_base_action_raw: torch.Tensor,
    base_slice: tuple[int, int],
    arm_slice: tuple[int, int],
    gripper_index: int,
):
    num_envs = action.shape[0] if torch.is_tensor(action) and action.ndim == 2 else -1
    if (
        num_envs < 0
        or action.shape[1] != 12
        or not action.is_floating_point()
        or not torch.is_tensor(arm_dls_mask)
        or not torch.is_tensor(relief_mask)
        or arm_dls_mask.shape != (num_envs,)
        or relief_mask.shape != (num_envs,)
        or arm_dls_mask.dtype != torch.bool
        or relief_mask.dtype != torch.bool
        or not torch.is_tensor(arm_action_raw)
        or arm_action_raw.shape != (num_envs, 6)
        or not torch.is_tensor(relief_base_action_raw)
        or relief_base_action_raw.shape != (num_envs, 5)
        or base_slice != (0, 5)
        or arm_slice != (5, 11)
        or gripper_index != 11
    ):
        raise ValueError("oracle branch action contract mismatch.")
    tensors = (arm_dls_mask, relief_mask, arm_action_raw, relief_base_action_raw)
    if any(value.device != action.device for value in tensors):
        raise ValueError("oracle branch action inputs must be on one common device.")
    if arm_action_raw.dtype != action.dtype or relief_base_action_raw.dtype != action.dtype:
        raise ValueError("oracle branch action values must share the action floating dtype.")
    if not torch.all(torch.isfinite(action)) or not torch.all(
        torch.isfinite(arm_action_raw)
    ) or not torch.all(torch.isfinite(relief_base_action_raw)):
        raise ValueError("oracle branch action values must be finite.")
    if torch.any(arm_dls_mask & relief_mask):
        raise ValueError("arm-DLS and base-relief branches must be disjoint.")
    result = action.clone()
    override_mask = arm_dls_mask | relief_mask
    result[arm_dls_mask, base_slice[0] : base_slice[1]] = 0.0
    result[arm_dls_mask, arm_slice[0] : arm_slice[1]] = arm_action_raw[arm_dls_mask]
    result[relief_mask, base_slice[0] : base_slice[1]] = relief_base_action_raw[relief_mask]
    result[relief_mask, arm_slice[0] : arm_slice[1]] = 0.0
    result[override_mask, gripper_index] = -1.0
    return result, override_mask


def a2_hold_update_phase_arm_sign_check(
    phase_mask: torch.Tensor,
    arm_dls_write_mask: torch.Tensor,
    previous_arm_dls_count: torch.Tensor,
    previous_checked: torch.Tensor,
    phase_progress_delta: torch.Tensor,
    sign_window_steps: int,
    minimum_progress_delta: float,
):
    masks = (phase_mask, arm_dls_write_mask, previous_checked)
    if (
        any(
            not torch.is_tensor(mask)
            or mask.shape != phase_mask.shape
            or mask.dtype != torch.bool
            or mask.device != phase_mask.device
            for mask in masks
        )
        or not torch.is_tensor(previous_arm_dls_count)
        or previous_arm_dls_count.shape != phase_mask.shape
        or previous_arm_dls_count.dtype != torch.long
        or previous_arm_dls_count.device != phase_mask.device
        or not torch.is_tensor(phase_progress_delta)
        or phase_progress_delta.shape != phase_mask.shape
        or not phase_progress_delta.is_floating_point()
        or phase_progress_delta.device != phase_mask.device
    ):
        raise ValueError("phase arm-sign inputs have incompatible shapes, dtypes or devices.")
    if torch.any(previous_arm_dls_count < 0) or not torch.all(
        torch.isfinite(phase_progress_delta)
    ):
        raise ValueError("phase arm-sign counter must be non-negative and progress finite.")
    if (
        isinstance(sign_window_steps, bool)
        or not isinstance(sign_window_steps, int)
        or sign_window_steps <= 0
    ):
        raise ValueError("phase arm-sign window must be a positive int.")
    if (
        isinstance(minimum_progress_delta, bool)
        or not isinstance(minimum_progress_delta, (int, float))
        or not math.isfinite(float(minimum_progress_delta))
        or minimum_progress_delta <= 0.0
    ):
        raise ValueError("phase arm-sign minimum progress must be a finite positive float.")
    due = phase_mask & ~previous_checked & (
        previous_arm_dls_count >= sign_window_steps
    )
    wrong_sign = due & ~a2_hold_positive_sign_pass(
        phase_progress_delta, float(minimum_progress_delta)
    )
    updated_checked = previous_checked | due
    actual_arm_write = phase_mask & arm_dls_write_mask & ~wrong_sign
    updated_count = previous_arm_dls_count.clone()
    updated_count[actual_arm_write] += 1
    return {
        "count": updated_count,
        "checked": updated_checked,
        "due": due,
        "wrong_sign": wrong_sign,
        "actual_arm_write": actual_arm_write,
    }


def a2_hold_positive_sign_pass(delta: torch.Tensor, minimum_delta: float) -> torch.Tensor:
    if not torch.is_tensor(delta) or not math.isfinite(minimum_delta) or minimum_delta <= 0.0:
        raise ValueError("Sign smoke requires a tensor delta and finite positive minimum_delta.")
    return delta >= minimum_delta


def a2_hold_depress_timeout_mask(
    depress_mask: torch.Tensor,
    depress_done: torch.Tensor,
    phase_step: torch.Tensor,
    timeout_steps: int,
):
    if any(
        not torch.is_tensor(value) or value.shape != depress_mask.shape
        for value in (depress_done, phase_step)
    ):
        raise ValueError("depress timeout inputs must have identical shapes.")
    return depress_mask & ~depress_done & (phase_step >= timeout_steps)


def a2_hold_depress_transition_mask(
    depress_mask: torch.Tensor,
    depress_done: torch.Tensor,
    outcome_pending: torch.Tensor,
):
    if any(
        not torch.is_tensor(value) or value.shape != depress_mask.shape
        for value in (depress_done, outcome_pending)
    ):
        raise ValueError("depress transition inputs must have identical shapes.")
    if any(value.dtype != torch.bool for value in (depress_mask, depress_done, outcome_pending)):
        raise ValueError("depress transition inputs must be bool.")
    return depress_mask & depress_done & outcome_pending


def a2_hold_push_timeout_masks(
    push_mask: torch.Tensor,
    reached_progress: torch.Tensor,
    phase_step: torch.Tensor,
    timeout_steps: int,
    hinge_delta: torch.Tensor,
    minimum_delta: float,
):
    if any(
        not torch.is_tensor(value) or value.shape != push_mask.shape
        for value in (reached_progress, phase_step, hinge_delta)
    ):
        raise ValueError("push timeout inputs must have identical shapes.")
    timeout = push_mask & ~reached_progress & (phase_step >= timeout_steps)
    return timeout & (hinge_delta < minimum_delta), timeout & (hinge_delta >= minimum_delta)


def a2_hold_action_with_exact_disabled_equivalence(
    policy_action: torch.Tensor, active_mask: torch.Tensor
) -> torch.Tensor:
    if (
        not torch.is_tensor(active_mask)
        or active_mask.dtype != torch.bool
        or active_mask.shape != policy_action.shape[:1]
    ):
        raise ValueError("active_mask must be bool shape (N,).")
    return policy_action if not torch.any(active_mask) else policy_action.clone()


def a2_hold_summarize_outcomes(outcome_names):
    if any(name not in A2_HOLD_OUTCOME_TO_ID for name in outcome_names):
        raise ValueError(f"Unknown A2 hold outcome in {outcome_names!r}.")
    counts = Counter(outcome_names)
    return {name: int(counts.get(name, 0)) for name in A2_HOLD_OUTCOME_NAMES}


class OrderedTargetFrameTransformer(FrameTransformer):
    """FrameTransformer variant that preserves cfg.target_frames order for duplicate target bodies."""

    def _initialize_impl(self):
        super(FrameTransformer, self)._initialize_impl()

        source_frame_offset_pos = torch.tensor(self.cfg.source_frame_offset.pos, device=self.device)
        source_frame_offset_quat = torch.tensor(
            self.cfg.source_frame_offset.rot, device=self.device
        )
        self._apply_source_frame_offset = True
        if is_identity_pose(source_frame_offset_pos, source_frame_offset_quat):
            self._apply_source_frame_offset = False
        else:
            self._source_frame_offset_pos = source_frame_offset_pos.unsqueeze(0).repeat(
                self._num_envs, 1
            )
            self._source_frame_offset_quat = source_frame_offset_quat.unsqueeze(0).repeat(
                self._num_envs, 1
            )

        body_names_to_frames = {}
        target_offsets = {}
        self._apply_target_frame_offset = False
        self._source_is_also_target_frame = False

        target_frame_names = set()
        for target_frame in self.cfg.target_frames:
            frame_name = (
                target_frame.name
                if target_frame.name is not None
                else target_frame.prim_path.rsplit("/", 1)[-1]
            )
            if frame_name in target_frame_names:
                raise RuntimeError(
                    f"FrameTransformer target frame name {frame_name!r} is duplicated."
                )
            target_frame_names.add(frame_name)

            offset = target_frame.offset
            if offset is not None:
                offset_pos = torch.tensor(offset.pos, device=self.device)
                offset_quat = torch.tensor(offset.rot, device=self.device)
                if not is_identity_pose(offset_pos, offset_quat):
                    self._apply_target_frame_offset = True
                target_offsets[frame_name] = {"pos": offset_pos, "quat": offset_quat}

        frames = [None] + [target_frame.name for target_frame in self.cfg.target_frames]
        frame_prim_paths = [self.cfg.prim_path] + [
            target_frame.prim_path for target_frame in self.cfg.target_frames
        ]
        frame_types = ["source"] + ["target"] * len(self.cfg.target_frames)
        for frame, prim_path, frame_type in zip(frames, frame_prim_paths, frame_types):
            matching_prims = sim_utils.find_matching_prims(prim_path)
            if len(matching_prims) == 0:
                raise ValueError(
                    f"Failed to create frame transformer for frame '{frame}' with path "
                    f"'{prim_path}'. No matching prims were found."
                )
            for prim in matching_prims:
                matching_prim_path = prim.GetPath().pathString
                if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
                    raise ValueError(
                        f"While resolving expression '{prim_path}' found a prim "
                        f"'{matching_prim_path}' which is not a rigid body. The class only "
                        "supports transformations between rigid bodies."
                    )

                body_name = self._get_relative_body_path(matching_prim_path)
                frame_name = frame if frame is not None else matching_prim_path.rsplit("/", 1)[-1]

                if body_name in body_names_to_frames:
                    if frame_name not in body_names_to_frames[body_name]["frames"]:
                        body_names_to_frames[body_name]["frames"].append(frame_name)
                    if body_names_to_frames[body_name]["type"] == "source" and frame_type == "target":
                        self._source_is_also_target_frame = True
                else:
                    body_names_to_frames[body_name] = {
                        "frames": [frame_name],
                        "prim_path": matching_prim_path,
                        "type": frame_type,
                    }

        tracked_prim_paths = [
            body_names_to_frames[body_name]["prim_path"] for body_name in body_names_to_frames.keys()
        ]
        tracked_body_names = [body_name for body_name in body_names_to_frames.keys()]
        body_names_regex = [
            tracked_prim_path.replace("env_0", "env_*")
            for tracked_prim_path in tracked_prim_paths
        ]

        self._physics_sim_view = SimulationManager.get_physics_sim_view()
        self._frame_physx_view = self._physics_sim_view.create_rigid_body_view(body_names_regex)

        all_prim_paths = self._frame_physx_view.prim_paths
        if "env_" in all_prim_paths[0]:

            def extract_env_num_and_prim_path(item: str) -> tuple[int, str]:
                match = re.search(r"env_(\d+)(.*)", item)
                return (int(match.group(1)), match.group(2))

            self._per_env_indices = [
                index
                for index, _ in sorted(
                    list(enumerate(all_prim_paths)), key=lambda x: extract_env_num_and_prim_path(x[1])
                )
            ]
            sorted_prim_paths = [
                all_prim_paths[index]
                for index in self._per_env_indices
                if "env_0" in all_prim_paths[index]
            ]
        else:
            self._per_env_indices = [
                index for index, _ in sorted(enumerate(all_prim_paths), key=lambda x: x[1])
            ]
            sorted_prim_paths = [all_prim_paths[index] for index in self._per_env_indices]

        self._target_frame_body_names = [
            self._get_relative_body_path(prim_path) for prim_path in sorted_prim_paths
        ]
        self._source_frame_body_name = self._get_relative_body_path(self.cfg.prim_path)
        source_frame_index = self._target_frame_body_names.index(self._source_frame_body_name)

        if not self._source_is_also_target_frame:
            self._target_frame_body_names.remove(self._source_frame_body_name)

        all_ids = torch.arange(self._num_envs * len(tracked_body_names))
        self._source_frame_body_ids = (
            torch.arange(self._num_envs) * len(tracked_body_names) + source_frame_index
        )

        if self._source_is_also_target_frame:
            self._target_frame_body_ids = all_ids
        else:
            self._target_frame_body_ids = all_ids[~torch.isin(all_ids, self._source_frame_body_ids)]

        self._target_frame_names = []
        target_frame_offset_pos = []
        target_frame_offset_quat = []
        duplicate_frame_indices = []
        for i, body_name in enumerate(self._target_frame_body_names):
            for frame in body_names_to_frames[body_name]["frames"]:
                if frame in target_offsets:
                    target_frame_offset_pos.append(target_offsets[frame]["pos"])
                    target_frame_offset_quat.append(target_offsets[frame]["quat"])
                    self._target_frame_names.append(frame)
                    duplicate_frame_indices.append(i)

        duplicate_frame_indices = torch.tensor(duplicate_frame_indices, device=self.device)
        if self._source_is_also_target_frame:
            num_target_body_frames = len(tracked_body_names)
        else:
            num_target_body_frames = len(tracked_body_names) - 1

        self._duplicate_frame_indices = torch.cat(
            [
                duplicate_frame_indices + num_target_body_frames * env_num
                for env_num in range(self._num_envs)
            ]
        )

        if self._apply_target_frame_offset:
            self._target_frame_offset_pos = torch.stack(target_frame_offset_pos).repeat(
                self._num_envs, 1
            )
            self._target_frame_offset_quat = torch.stack(target_frame_offset_quat).repeat(
                self._num_envs, 1
            )

        self._data.target_frame_names = self._target_frame_names
        self._data.source_pos_w = torch.zeros(self._num_envs, 3, device=self._device)
        self._data.source_quat_w = torch.zeros(self._num_envs, 4, device=self._device)
        self._data.target_pos_w = torch.zeros(
            self._num_envs, len(duplicate_frame_indices), 3, device=self._device
        )
        self._data.target_quat_w = torch.zeros(
            self._num_envs, len(duplicate_frame_indices), 4, device=self._device
        )
        self._data.target_pos_source = torch.zeros_like(self._data.target_pos_w)
        self._data.target_quat_source = torch.zeros_like(self._data.target_quat_w)


class DoorPregrasp(
    StagedTaskBase,
    DeltaActionBase,
    WarpedActionBase,
    A2Base,
    FingerPrimitiveBase,
    ResetFromDataset,
):
    STAGE_WALK_TO_DOOR = 0
    STAGE_PREGRASP = 1
    STAGE_GRASP = 2
    STAGE_OPEN = 3
    STAGE_SWING = 4
    STAGE_THROUGH = 5
    A2_GRIPPER_HANDLE_FRAME_TRANSFORMER = "piper_gripper_handle_frame_transformer"
    A2_GRIPPER_HANDLE_CONTACT_SENSOR = "a2_gripper_handle_contact_sensor"
    A2_DOOR_BODY_PANEL_CONTACT_SENSOR = "a2_door_body_panel_contact_sensor"
    A2_DOOR_ARM_PANEL_CONTACT_SENSOR = "a2_door_arm_panel_contact_sensor"
    A2_DOOR_BODY_PANEL_FILTER_NAMES = (
        "trunk",
        "FL_hip",
        "FL_thigh",
        "FL_calf",
        "RL_hip",
        "RL_thigh",
        "RL_calf",
        "FR_hip",
        "FR_thigh",
        "FR_calf",
        "RR_hip",
        "RR_thigh",
        "RR_calf",
    )
    A2_DOOR_ARM_PANEL_FILTER_NAMES = (
        "arm_body0",
        "arm_body1",
        "arm_body2",
        "arm_body3",
        "arm_body4",
        "arm_body5",
        "arm_body6",
        "arm_body6_to_gripper",
        "arm_body7",
        "arm_body8",
    )
    A2_PENALIZED_CONTACT_BODY_NAMES = (
        *A2_DOOR_BODY_PANEL_FILTER_NAMES,
        *A2_DOOR_ARM_PANEL_FILTER_NAMES[:7],
    )
    A2_PREGRASP_OFFSET = (-0.10, 0.0, 0.0)  # in grasp_target body frame (= door root frame)
    A2_STAGE0_STAGING_X_MIN_CONFIG_KEY = "a2_stage0_staging_x_min"
    A2_STAGE0_STAGING_X_MAX_CONFIG_KEY = "a2_stage0_staging_x_max"
    A2_STAGE0_STAGING_Y_TOL_CONFIG_KEY = "a2_stage0_staging_y_tol"
    A2_STAGE3_TO4_DOOR_HINGE_THRESHOLD_CONFIG_KEY = (
        "a2_stage3_to4_door_hinge_threshold"
    )
    A2_STAGE3_BASE_UNLOCKED_CONFIG_KEY = "a2_stage3_base_unlocked"
    A2_STAGE4_RELEASE_HINGE_THRESHOLD_CONFIG_KEY = (
        "a2_stage4_release_hinge_threshold"
    )
    A2_STAGE4_TO5_DOOR_HINGE_THRESHOLD_CONFIG_KEY = (
        "a2_stage4_to5_door_hinge_threshold"
    )
    A2_STAGE5_HOLD_INCOME_CONTINUITY_ENABLED_CONFIG_KEY = (
        "a2_stage5_hold_income_continuity_enabled"
    )
    A2_DOOR_BODY_CONTACT_EVENT_FORCE_THRESHOLD_CONFIG_KEY = (
        "a2_door_body_contact_event_force_threshold"
    )
    A2_DOOR_BODY_CONTACT_EVENT_PEAK_FORCE_NORM_CONFIG_KEY = (
        "a2_door_body_contact_event_peak_force_norm"
    )
    A2_DOOR_BODY_CONTACT_EVENT_COMPONENT_CAP_CONFIG_KEY = (
        "a2_door_body_contact_event_component_cap"
    )
    A2_STAGE45_DOOR_FRAME_CONTACT_SCALE_CONFIG_KEY = (
        "a2_stage45_door_frame_contact_scale"
    )
    A2_STAGE35_DOOR_PANEL_CONTACT_SCALE_CONFIG_KEY = (
        "a2_stage35_door_panel_contact_scale"
    )
    A2_GRIPPER_SOURCE_TCP_OFFSET_Z_CONFIG_KEY = "a2_gripper_source_tcp_offset_z"
    A2_GRASP_GATE_MODE_CONFIG_KEY = "a2_grasp_gate_mode"
    A2_GRASP_STREAK_CONTROL_STEPS_CONFIG_KEY = "a2_grasp_streak_control_steps"
    A2_GRASP_GATE_MODE_CONTROL_STREAK = "control_streak"
    A2_GRASP_GATE_MODE_PHYSICS_HISTORY = "physics_history"
    A2_STAGE3_TO4_REQUIRES_GRASP_STREAK_CONFIG_KEY = (
        "a2_stage3_to4_requires_grasp_streak"
    )
    A2_STAGE3_TO4_STREAK_HIGHWATER_CONFIG_KEY = (
        "a2_stage3_to4_streak_highwater"
    )
    A2_STAGE3_UNLATCH_HANDLE_POSITION_NORM_CONFIG_KEY = (
        "a2_stage3_unlatch_handle_position_norm"
    )
    A2_STAGE3_UNLATCH_NEAR_CLOSED_HINGE_THRESHOLD_CONFIG_KEY = (
        "a2_stage3_unlatch_near_closed_hinge_threshold"
    )
    A2_STAGE3_STAGE4_HOLD_AND_DRIVE_VELOCITY_NORM_CONFIG_KEY = (
        "a2_stage3_stage4_hold_and_drive_velocity_norm"
    )
    A2_CORRIDOR_ENABLED_CONFIG_KEY = "a2_corridor_enabled"
    A2_DOOR_BODY_CONTACT_PENALTY_MODE_CONFIG_KEY = (
        "a2_door_body_contact_penalty_mode"
    )
    A2_STAGE3_STAGE4_HOLD_AND_DRIVE_CORRIDOR_VELOCITY_NORM_CONFIG_KEY = (
        "a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor"
    )
    A2_STAGE3_STAGE4_HOLD_AND_DRIVE_VELOCITY_THRESHOLD_CONFIG_KEY = (
        "a2_stage3_stage4_hold_and_drive_velocity_threshold"
    )
    A2_STAGE3_STAGE4_COASTING_VELOCITY_THRESHOLD_CONFIG_KEY = (
        "a2_stage3_stage4_coasting_velocity_threshold"
    )
    A2_STAGE3_HANDLE_HARD_LIMIT_POSITION_CONFIG_KEY = (
        "a2_stage3_handle_hard_limit_position"
    )
    A2_STAGE3_HANDLE_HARD_LIMIT_TOLERANCE_CONFIG_KEY = (
        "a2_stage3_handle_hard_limit_tolerance"
    )
    A2_HOLD_CONTACT_DETAIL_CONFIG_KEY = "a2_hold_diagnostic_contact_detail_enabled"
    A2_HOLD_CONTACT_CAPACITY_CONFIG_KEY = (
        "a2_hold_diagnostic_max_contact_data_count_per_prim"
    )
    A2_HOLD_FRICTION_OVERRIDE_CONFIG_KEY = "a2_hold_diagnostic_friction_override"
    A2_M39_GRIPPER_MATERIAL_CONFIG_KEY = "a2_m39_gripper_material_enabled"
    A2_M23_SELF_COLLISION_CONTACT_SENSORS_CONFIG_KEY = (
        "a2_m23_self_collision_contact_sensors_enabled"
    )
    A2_M23_SELF_COLLISION_SENSOR_KEY_PREFIX = "a2_m23_self_collision_"
    A2_M23_SELF_COLLISION_BODY_NAMES = (
        "FL_hip",
        "FL_thigh",
        "FL_calf",
        "FL_foot",
        "RL_hip",
        "RL_thigh",
        "RL_calf",
        "RL_foot",
        "FR_hip",
        "FR_thigh",
        "FR_calf",
        "FR_foot",
        "RR_hip",
        "RR_thigh",
        "RR_calf",
        "RR_foot",
        "arm_body0",
        "trunk",
        "arm_body1",
        "arm_body2",
        "arm_body3",
        "arm_body4",
        "arm_body5",
        "arm_body6",
        "arm_body6_to_gripper",
        "arm_body7",
        "arm_body8",
    )

    def _get_required_positive_float_config(self, key: str, context: str) -> float:
        if key not in self.config:
            raise RuntimeError(f"{context} requires env.config.{key}.")
        value = self.config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(
                f"{context} requires env.config.{key} to be a positive float; "
                f"got {value!r} ({type(value).__name__})."
            )
        value = float(value)
        if not math.isfinite(value) or value <= 0.0:
            raise RuntimeError(
                f"{context} requires env.config.{key} to be finite and > 0.0; "
                f"got {value}."
            )
        return value

    def _get_required_finite_float_config(self, key: str, context: str) -> float:
        if key not in self.config:
            raise RuntimeError(f"{context} requires env.config.{key}.")
        value = self.config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(
                f"{context} requires env.config.{key} to be a finite float; "
                f"got {value!r} ({type(value).__name__})."
            )
        value = float(value)
        if not math.isfinite(value):
            raise RuntimeError(
                f"{context} requires env.config.{key} to be finite; got {value}."
            )
        return value

    def _get_a2_gripper_source_tcp_offset_z(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_GRIPPER_SOURCE_TCP_OFFSET_Z_CONFIG_KEY,
            "A2 Piper gripper source TCP",
        )

    def _get_a2_grasp_gate_mode(self) -> str:
        key = self.A2_GRASP_GATE_MODE_CONFIG_KEY
        if key not in self.config:
            raise RuntimeError(f"A2 grasp gate requires env.config.{key}.")
        value = self.config[key]
        allowed = (
            self.A2_GRASP_GATE_MODE_CONTROL_STREAK,
            self.A2_GRASP_GATE_MODE_PHYSICS_HISTORY,
        )
        if not isinstance(value, str) or value not in allowed:
            raise RuntimeError(
                f"env.config.{key} must be one of {allowed}; got {value!r}."
            )
        return value

    def _get_a2_grasp_streak_control_steps(self) -> int:
        key = self.A2_GRASP_STREAK_CONTROL_STEPS_CONFIG_KEY
        if key not in self.config:
            raise RuntimeError(f"A2 grasp control streak requires env.config.{key}.")
        value = self.config[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RuntimeError(
                f"env.config.{key} must be a positive int; got {value!r}."
            )
        return value

    def _get_a2_stage3_to4_requires_grasp_streak(self) -> bool:
        key = self.A2_STAGE3_TO4_REQUIRES_GRASP_STREAK_CONFIG_KEY
        if key not in self.config:
            raise RuntimeError(f"A2 stage3->4 grasp gate requires env.config.{key}.")
        value = self.config[key]
        if not isinstance(value, bool):
            raise RuntimeError(f"env.config.{key} must be bool; got {value!r}.")
        return value

    def _get_a2_stage3_to4_streak_highwater(self) -> bool:
        key = self.A2_STAGE3_TO4_STREAK_HIGHWATER_CONFIG_KEY
        if key not in self.config:
            raise RuntimeError(f"A2 stage3->4 high-water gate requires env.config.{key}.")
        value = self.config[key]
        if not isinstance(value, bool):
            raise RuntimeError(f"env.config.{key} must be bool; got {value!r}.")
        return value

    def _get_a2_stage3_unlatch_handle_position_norm(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE3_UNLATCH_HANDLE_POSITION_NORM_CONFIG_KEY,
            "A2 stage3 unlatch reward",
        )

    def _get_a2_stage3_unlatch_near_closed_hinge_threshold(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE3_UNLATCH_NEAR_CLOSED_HINGE_THRESHOLD_CONFIG_KEY,
            "A2 stage3 unlatch near-closed gate",
        )

    def _get_a2_stage3_stage4_hold_and_drive_velocity_norm(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE3_STAGE4_HOLD_AND_DRIVE_VELOCITY_NORM_CONFIG_KEY,
            "A2 stage3/4 hold-and-drive reward",
        )

    def _get_a2_corridor_enabled(self) -> bool:
        key = self.A2_CORRIDOR_ENABLED_CONFIG_KEY
        if key not in self.config:
            raise RuntimeError(f"A2 corridor requires env.config.{key}.")
        value = self.config[key]
        if not isinstance(value, bool):
            raise RuntimeError(f"env.config.{key} must be bool; got {value!r}.")
        return value

    def _get_a2_door_body_contact_penalty_mode(self) -> str:
        key = self.A2_DOOR_BODY_CONTACT_PENALTY_MODE_CONFIG_KEY
        if key not in self.config:
            raise RuntimeError(f"A2 body contact penalty requires env.config.{key}.")
        value = self.config[key]
        allowed = ("linear_v15", "quadratic_v16", "event_v17")
        if not isinstance(value, str) or value not in allowed:
            raise RuntimeError(
                f"env.config.{key} must be one of {allowed}; got {value!r}."
            )
        return value

    def _get_a2_stage5_hold_income_continuity_enabled(self) -> bool:
        key = self.A2_STAGE5_HOLD_INCOME_CONTINUITY_ENABLED_CONFIG_KEY
        if key not in self.config:
            raise RuntimeError(f"A2 stage5 hold continuity requires env.config.{key}.")
        value = self.config[key]
        if not isinstance(value, bool):
            raise RuntimeError(f"env.config.{key} must be bool; got {value!r}.")
        return value

    def _get_a2_door_body_contact_event_config(self) -> tuple[float, float, float]:
        return (
            self._get_required_positive_float_config(
                self.A2_DOOR_BODY_CONTACT_EVENT_FORCE_THRESHOLD_CONFIG_KEY,
                "A2 v17 body-contact event threshold",
            ),
            self._get_required_positive_float_config(
                self.A2_DOOR_BODY_CONTACT_EVENT_PEAK_FORCE_NORM_CONFIG_KEY,
                "A2 v17 body-contact event peak normalization",
            ),
            self._get_required_positive_float_config(
                self.A2_DOOR_BODY_CONTACT_EVENT_COMPONENT_CAP_CONFIG_KEY,
                "A2 v17 body-contact event component cap",
            ),
        )

    def _get_a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE3_STAGE4_HOLD_AND_DRIVE_CORRIDOR_VELOCITY_NORM_CONFIG_KEY,
            "A2 corridor hold-and-drive reward",
        )

    def _get_a2_stage3_stage4_hold_and_drive_velocity_threshold(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE3_STAGE4_HOLD_AND_DRIVE_VELOCITY_THRESHOLD_CONFIG_KEY,
            "A2 stage3/4 hold-and-drive telemetry",
        )

    def _get_a2_stage3_stage4_coasting_velocity_threshold(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE3_STAGE4_COASTING_VELOCITY_THRESHOLD_CONFIG_KEY,
            "A2 stage3/4 coasting telemetry",
        )

    def _get_a2_stage3_handle_hard_limit_position(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE3_HANDLE_HARD_LIMIT_POSITION_CONFIG_KEY,
            "A2 stage3 handle-limit telemetry",
        )

    def _get_a2_stage3_handle_hard_limit_tolerance(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE3_HANDLE_HARD_LIMIT_TOLERANCE_CONFIG_KEY,
            "A2 stage3 handle-limit telemetry",
        )

    def _get_a2_stage4_release_hinge_threshold(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE4_RELEASE_HINGE_THRESHOLD_CONFIG_KEY,
            "A2 stage4 release gate",
        )

    def _get_a2_stage4_to5_door_hinge_threshold(self) -> float:
        return self._get_required_positive_float_config(
            self.A2_STAGE4_TO5_DOOR_HINGE_THRESHOLD_CONFIG_KEY,
            "A2 stage4 to stage5 door-hinge gate",
        )

    def _get_a2_stage45_door_frame_contact_scale(self) -> float:
        value = self._get_required_finite_float_config(
            self.A2_STAGE45_DOOR_FRAME_CONTACT_SCALE_CONFIG_KEY,
            "A2 stage4/5 door-frame contact penalty",
        )
        if not 0.0 <= value <= 1.0:
            raise RuntimeError(
                "A2 stage4/5 door-frame contact penalty scale must be finite in [0.0, 1.0]; "
                f"got {value}."
            )
        return value

    def _get_a2_stage35_door_panel_contact_scale(self) -> float:
        value = self._get_required_finite_float_config(
            self.A2_STAGE35_DOOR_PANEL_CONTACT_SCALE_CONFIG_KEY,
            "A2 stage3-5 door-panel contact penalty",
        )
        if not 0.0 <= value <= 1.0:
            raise RuntimeError(
                "A2 stage3-5 door-panel contact penalty scale must be finite in [0.0, 1.0]; "
                f"got {value}."
            )
        return value

    def _validate_a2_v13_door_semantics_config(self):
        unlatch_norm = self._get_a2_stage3_unlatch_handle_position_norm()
        handle_limit = self._get_a2_stage3_handle_hard_limit_position()
        handle_limit_tolerance = self._get_a2_stage3_handle_hard_limit_tolerance()
        drive_norm = self._get_a2_stage3_stage4_hold_and_drive_velocity_norm()
        drive_threshold = (
            self._get_a2_stage3_stage4_hold_and_drive_velocity_threshold()
        )
        corridor_enabled = self._get_a2_corridor_enabled()
        body_contact_mode = self._get_a2_door_body_contact_penalty_mode()
        stage5_continuity = self._get_a2_stage5_hold_income_continuity_enabled()
        self._get_a2_stage3_to4_requires_grasp_streak()
        self._get_a2_stage3_to4_streak_highwater()
        self._get_a2_stage3_unlatch_near_closed_hinge_threshold()
        self._get_a2_stage3_stage4_coasting_velocity_threshold()
        release_threshold = self._get_a2_stage4_release_hinge_threshold()
        advance_threshold = self._get_a2_stage4_to5_door_hinge_threshold()
        self._get_a2_stage45_door_frame_contact_scale()
        self._get_a2_stage35_door_panel_contact_scale()
        if body_contact_mode == "event_v17":
            self._get_a2_door_body_contact_event_config()
        if unlatch_norm >= handle_limit:
            raise RuntimeError(
                "A2 unlatch reward normalization must be below the handle hard limit; "
                f"got norm={unlatch_norm}, limit={handle_limit}."
            )
        if handle_limit_tolerance >= handle_limit:
            raise RuntimeError(
                "A2 handle-limit telemetry tolerance must be below the hard limit; "
                f"got tolerance={handle_limit_tolerance}, limit={handle_limit}."
            )
        if drive_threshold >= drive_norm:
            raise RuntimeError(
                "A2 hold-and-drive telemetry threshold must be below reward saturation; "
                f"got threshold={drive_threshold}, norm={drive_norm}."
            )
        corridor_drive_norm = (
            self._get_a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor()
        )
        if corridor_enabled and corridor_drive_norm <= drive_norm:
            raise RuntimeError(
                "A2 enabled corridor hold-and-drive velocity norm must exceed the historical norm; "
                f"got corridor={corridor_drive_norm}, pre_corridor={drive_norm}."
            )
        if not corridor_enabled and corridor_drive_norm != drive_norm:
            raise RuntimeError(
                "A2 disabled corridor must retain the historical hold-and-drive norm; "
                f"got corridor={corridor_drive_norm}, historical={drive_norm}."
            )
        if stage5_continuity and not corridor_enabled:
            raise RuntimeError(
                "A2 stage5 hold-income continuity requires the corridor selector enabled."
            )
        if stage5_continuity and release_threshold < advance_threshold:
            raise RuntimeError(
                "A2 stage5 hold-income continuity requires release threshold >= "
                "stage4->5 threshold; got "
                f"release={release_threshold}, advance={advance_threshold}."
            )

    def _get_a2_grasp_control_streak_buffer(
        self, attribute_name: str, context: str
    ) -> torch.Tensor:
        streak = getattr(self, attribute_name, None)
        if (
            streak is None
            or not torch.is_tensor(streak)
            or tuple(streak.shape) != (self.num_envs,)
            or streak.dtype != torch.long
            or streak.device != torch.device(self.device)
            or torch.any(streak < 0)
        ):
            shape = None if not torch.is_tensor(streak) else tuple(streak.shape)
            dtype = None if not torch.is_tensor(streak) else streak.dtype
            device = None if not torch.is_tensor(streak) else streak.device
            raise RuntimeError(
                f"{context} requires {attribute_name} non-negative long tensor shape "
                f"({self.num_envs},) on {self.device}; got "
                f"shape={shape}, dtype={dtype}, device={device}."
            )
        return streak

    def _get_a2_hold_contact_detail_enabled(self) -> bool:
        value = self.config.get(self.A2_HOLD_CONTACT_DETAIL_CONFIG_KEY, None)
        if not isinstance(value, bool):
            raise RuntimeError(
                f"env.config.{self.A2_HOLD_CONTACT_DETAIL_CONFIG_KEY} must be bool; got {value!r}."
            )
        return value
    def _get_a2_m39_gripper_material_enabled(self) -> bool:
        value = self.config.get(self.A2_M39_GRIPPER_MATERIAL_CONFIG_KEY, False)
        if not isinstance(value, bool):
            raise RuntimeError(
                f"env.config.{self.A2_M39_GRIPPER_MATERIAL_CONFIG_KEY} must be bool; got {value!r}."
            )
        return value

    def _get_a2_hold_contact_capacity(self) -> int:
        value = self.config.get(self.A2_HOLD_CONTACT_CAPACITY_CONFIG_KEY, None)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise RuntimeError(
                f"env.config.{self.A2_HOLD_CONTACT_CAPACITY_CONFIG_KEY} must be a positive int; "
                f"got {value!r}."
            )
        return value

    def _get_a2_hold_friction_override(self):
        value = self.config.get(self.A2_HOLD_FRICTION_OVERRIDE_CONFIG_KEY, None)
        try:
            return a2_hold_validate_friction_override(value)
        except ValueError as exc:
            raise RuntimeError(
                f"env.config.{self.A2_HOLD_FRICTION_OVERRIDE_CONFIG_KEY}: {exc}"
            ) from exc

    def _get_a2_m23_self_collision_contact_sensors_enabled(self) -> bool:
        key = self.A2_M23_SELF_COLLISION_CONTACT_SENSORS_CONFIG_KEY
        value = self.config.get(key, False)
        if not isinstance(value, bool):
            raise RuntimeError(f"env.config.{key} must be bool; got {value!r}.")
        return value

    def _get_a2_stage2_completion_close_gate_required(self) -> bool:
        key = "a2_stage2_completion_close_gate_required"
        context = "A2 stage2 completion close gate"
        if key not in self.config:
            raise RuntimeError(f"{context} requires env.config.{key}.")
        value = self.config[key]
        if not isinstance(value, bool):
            raise RuntimeError(
                f"{context} requires env.config.{key} to be a bool; "
                f"got {value!r} ({type(value).__name__})."
            )
        return value

    def _get_a2_stage3_base_unlocked(self) -> bool:
        key = self.A2_STAGE3_BASE_UNLOCKED_CONFIG_KEY
        context = "A2 stage3 base mobility"
        if key not in self.config:
            raise RuntimeError(f"{context} requires env.config.{key}.")
        value = self.config[key]
        if not isinstance(value, bool):
            raise RuntimeError(
                f"{context} requires env.config.{key} to be a bool; "
                f"got {value!r} ({type(value).__name__})."
            )
        return value

    def _get_a2_stage2_completion_close_command_threshold(self) -> float:
        return self._get_required_finite_float_config(
            "a2_stage2_completion_gripper_close_command_threshold",
            "A2 stage2 completion close command threshold",
        )

    def _get_a2_stage2_completion_close_progress_min_threshold(self) -> float:
        value = self._get_required_positive_float_config(
            "a2_stage2_completion_gripper_close_progress_min",
            "A2 stage2 completion close progress min",
        )
        if value > 1.0:
            raise RuntimeError(
                "A2 stage2 completion close progress min requires "
                "env.config.a2_stage2_completion_gripper_close_progress_min <= 1.0; "
                f"got {value}."
            )
        return value

    def _get_a2_stage2_contact_force_threshold(self) -> float:
        return self._get_required_positive_float_config(
            "a2_stage2_contact_force_threshold",
            "A2 stage2 contact force threshold",
        )

    def _get_a2_stage2_squeeze_force_min(self) -> float:
        return self._get_required_positive_float_config(
            "a2_stage2_squeeze_force_min",
            "A2 stage2 squeeze force min",
        )

    def _get_a2_stage2_squeeze_force_max(self) -> float:
        squeeze_min = self._get_a2_stage2_squeeze_force_min()
        squeeze_max = self._get_required_positive_float_config(
            "a2_stage2_squeeze_force_max",
            "A2 stage2 squeeze force max",
        )
        if squeeze_max <= squeeze_min:
            raise RuntimeError(
                "A2 stage2 squeeze force window requires "
                "env.config.a2_stage2_squeeze_force_max > "
                "env.config.a2_stage2_squeeze_force_min; "
                f"got min={squeeze_min}, max={squeeze_max}."
            )
        return squeeze_max

    def _get_a2_stage2_over_force_threshold(self) -> float:
        return self._get_required_positive_float_config(
            "a2_stage2_over_force_threshold",
            "A2 stage2 over-force threshold",
        )

    def _get_a2_stage0_staging_band(self) -> tuple[float, float, float]:
        return a2_validate_stage0_staging_band(
            self._get_required_positive_float_config(
                self.A2_STAGE0_STAGING_X_MIN_CONFIG_KEY,
                "A2 stage0 staging band minimum standoff",
            ),
            self._get_required_positive_float_config(
                self.A2_STAGE0_STAGING_X_MAX_CONFIG_KEY,
                "A2 stage0 staging band maximum standoff",
            ),
            self._get_required_positive_float_config(
                self.A2_STAGE0_STAGING_Y_TOL_CONFIG_KEY,
                "A2 stage0 staging band lateral tolerance",
            ),
        )

    def _get_a2_stage3_to4_door_hinge_threshold(self) -> float:
        threshold = getattr(self, "_a2_stage3_to4_door_hinge_threshold", None)
        if isinstance(threshold, bool) or not isinstance(threshold, float):
            raise RuntimeError(
                "A2 stage3->4 door hinge threshold was not initialized as a float; "
                f"got {threshold!r}."
            )
        if not math.isfinite(threshold) or threshold <= 0.0:
            raise RuntimeError(
                "A2 stage3->4 door hinge threshold must be finite and > 0.0; "
                f"got {threshold}."
            )
        return threshold

    def _get_a2_gripper_primitive_raw_column(self, context: str) -> torch.Tensor:
        gripper_primitive_raw = getattr(self, "_a2_gripper_primitive_raw", None)
        if (
            gripper_primitive_raw is None
            or not torch.is_tensor(gripper_primitive_raw)
            or tuple(gripper_primitive_raw.shape) != (self.num_envs, 1)
        ):
            shape = (
                None
                if gripper_primitive_raw is None
                else tuple(gripper_primitive_raw.shape)
            )
            raise RuntimeError(
                f"{context} requires _a2_gripper_primitive_raw shape "
                f"({self.num_envs}, 1); got {shape}."
            )
        return gripper_primitive_raw.squeeze(-1)

    def __init__(self, config, device):
        self._use_a2_base = bool(config.get("a2_base", {}).get("enabled", False))
        self._a2_eval_diagnostic_trace_enabled = False
        super().__init__(config, device)

        if self._use_a2_base:
            if self._reset_from_dataset_enabled():
                self._init_reset_from_dataset(config, device)
            self._init_a2_door_pregrasp_state()
            return

        # finger primitive related
        self._left_p0 = torch.tensor(
            self.config.robot.finger_primitive.primitive_action_map.left.pos_0,
            device=self.device,
            requires_grad=False,
        )
        self._left_p1 = torch.tensor(
            self.config.robot.finger_primitive.primitive_action_map.left.pos_1,
            device=self.device,
            requires_grad=False,
        )
        self._right_p0 = torch.tensor(
            self.config.robot.finger_primitive.primitive_action_map.right.pos_0,
            device=self.device,
            requires_grad=False,
        )
        self._right_p1 = torch.tensor(
            self.config.robot.finger_primitive.primitive_action_map.right.pos_1,
            device=self.device,
            requires_grad=False,
        )
        self._left_hand_dof_idx = [
            self.dof_names.index(name)
            for name in self.config.robot.finger_primitive.primitive_action_map.left.dof_names
        ]
        self._right_hand_dof_idx = [
            self.dof_names.index(name)
            for name in self.config.robot.finger_primitive.primitive_action_map.right.dof_names
        ]
        self._upper_non_finger_dof_idx = [
            i
            for i in self.upper_dof_indices
            if i not in self._left_hand_dof_idx and i not in self._right_hand_dof_idx
        ]
        self._upper_non_gripper_dof_idx = list(self._upper_non_finger_dof_idx)

        # read the door metadata
        stage: Usd.Stage = omni.usd.get_context().get_stage()
        self.door_width = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_height = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_handle_height = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self.door_handle_width = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_weight = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_open_lr = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_open_io = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)

        for env_id in range(self.num_envs):
            door_prim_path = f"/World/envs/env_{env_id}/door"
            door_prim = stage.GetPrimAtPath(door_prim_path)
            door_metadata = door_prim.GetPrim().GetMetadata("customData")
            self.door_width[env_id] = door_metadata["doorWidth"]
            self.door_height[env_id] = door_metadata["doorHeight"]
            self.door_handle_height[env_id] = door_metadata["doorHandleHeight"]
            self.door_handle_width[env_id] = door_metadata["doorHandleWidth"]
            self.door_weight[env_id] = door_metadata["doorWeight"]
            self.door_open_lr[env_id] = door_metadata["doorOpenLR"]

        # body indices
        self.left_palm_idx = self.simulator.body_names.index("left_hand_palm_link")
        self.right_palm_idx = self.simulator.body_names.index("right_hand_palm_link")
        self.root_idx = self.simulator.body_names.index("pelvis")
        self.left_hand_indices = [
            self.simulator.body_names.index(link)
            for link in self.simulator.robot_config.left_hand_body_names
        ]
        self.right_hand_indices = [
            self.simulator.body_names.index(link)
            for link in self.simulator.robot_config.right_hand_body_names
        ]
        g1_hand_links = [
            n
            for n in self.simulator.robot_config.body_names
            if ("left_hand" in n or "right_hand" in n)
        ]
        self.left_hand_indices_tgt_ct_sensor = [
            g1_hand_links.index(link) for link in g1_hand_links if "left_hand" in link
        ]
        self.left_hand_indices_convert = [
            self.left_hand_indices.index(self.simulator.body_names.index(g1_hand_links[i]))
            for i in self.left_hand_indices_tgt_ct_sensor
        ]
        self.right_hand_indices_tgt_ct_sensor = [
            g1_hand_links.index(link) for link in g1_hand_links if "right_hand" in link
        ]
        self.right_hand_indices_convert = [
            self.right_hand_indices.index(self.simulator.body_names.index(g1_hand_links[i]))
            for i in self.right_hand_indices_tgt_ct_sensor
        ]

        self.left_hand_palm_side_direction = self._parse_palm_side_direction(
            self.simulator.robot_config.left_hand_palm_side_direction
        )
        self.right_hand_palm_side_direction = self._parse_palm_side_direction(
            self.simulator.robot_config.right_hand_palm_side_direction
        )

        # dof indices
        finger_dof_names = [dof for dof in self.simulator.dof_names if "hand" in dof]
        self.finger_dof_idx = torch.tensor(
            [self.simulator.dof_names.index(dof) for dof in finger_dof_names],
            dtype=torch.long,
            device=self.device,
        )
        self.non_finger_dof_idx = [
            self.simulator.dof_names.index(dof)
            for dof in self.simulator.dof_names
            if dof not in finger_dof_names
        ]
        self.wrist_dof_idx = torch.tensor(
            [
                self.simulator.dof_names.index(dof)
                for dof in self.simulator.dof_names
                if "wrist" in dof
            ],
            dtype=torch.long,
            device=self.device,
        )
        self.dof_pos_humanly_lower_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_humanly_lower_limit_list, device=self.device
        )[None, :]
        self.dof_pos_humanly_upper_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_humanly_upper_limit_list, device=self.device
        )[None, :]

        self._left_arm_dof_idx = torch.tensor(self.left_arm_dof_indices, device=self.device)
        self._right_arm_dof_idx = torch.tensor(self.right_arm_dof_indices, device=self.device)

        self._register_task_state_to_track(self.simulator.scene.articulations["door"], "door")
        self._register_buffer_to_track(
            "delta_actions",
            self._get_delta_actions_buffer_shape(),
            self._store_delta_actions_buffer,
            self._load_delta_actions_buffer,
            dtype=torch.float32,
        )

        self.resting_dof_pos = torch.tensor([self.config.resting_dof_pos], device=self.device)

        self.target_root_pos = torch.tensor(self.config.target_root_pos, device=self.device)[
            None, :
        ]

    def _init_door_metadata(self):
        stage: Usd.Stage = omni.usd.get_context().get_stage()
        self.door_width = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_height = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_handle_height = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self.door_handle_width = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_weight = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_hinge_drive_max_force = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self.door_handle_drive_max_force = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self.door_open_lr = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_open_io = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)

        for env_id in range(self.num_envs):
            door_prim_path = f"/World/envs/env_{env_id}/door"
            door_prim = stage.GetPrimAtPath(door_prim_path)
            door_metadata = door_prim.GetPrim().GetMetadata("customData")
            self.door_width[env_id] = door_metadata["doorWidth"]
            self.door_height[env_id] = door_metadata["doorHeight"]
            self.door_handle_height[env_id] = door_metadata["doorHandleHeight"]
            self.door_handle_width[env_id] = door_metadata["doorHandleWidth"]
            self.door_weight[env_id] = door_metadata["doorWeight"]
            self.door_hinge_drive_max_force[env_id] = door_metadata[
                "hingeDriveMaxForce"
            ]
            self.door_handle_drive_max_force[env_id] = door_metadata[
                "handleDriveMaxForce"
            ]
            self.door_open_lr[env_id] = door_metadata["doorOpenLR"]

        for field_name in (
            "door_handle_height",
            "door_hinge_drive_max_force",
            "door_handle_drive_max_force",
        ):
            field_value = getattr(self, field_name)
            if (
                tuple(field_value.shape) != (self.num_envs,)
                or field_value.dtype != torch.float32
                or field_value.device != torch.device(self.device)
                or not torch.all(torch.isfinite(field_value))
            ):
                raise RuntimeError(
                    f"A2 door metadata requires {field_name} finite float32 tensor "
                    f"shape ({self.num_envs},) on {self.device}."
                )
        logger.info(
            "A2 runtime evidence: door metadata validated num_envs={} "
            "hinge_drive_max_force_min={} hinge_drive_max_force_max={} device={}",
            self.num_envs,
            self.door_hinge_drive_max_force.min().item(),
            self.door_hinge_drive_max_force.max().item(),
            self.door_hinge_drive_max_force.device,
        )

    def _init_a2_door_pregrasp_state(self):
        self._get_a2_grasp_gate_mode()
        self._get_a2_grasp_streak_control_steps()
        self._validate_a2_v13_door_semantics_config()
        if self._get_a2_m39_gripper_material_enabled():
            if getattr(self.simulator, "_m39_material_runtime_metadata", None) is None:
                raise RuntimeError("M39 gripper material runtime evidence is unavailable.")
        self._a2_stage3_to4_door_hinge_threshold = (
            self._get_required_positive_float_config(
                self.A2_STAGE3_TO4_DOOR_HINGE_THRESHOLD_CONFIG_KEY,
                "A2 stage3->4 door hinge transition",
            )
        )
        self._init_door_metadata()
        self.root_idx = self.simulator.body_names.index(self.config.robot.torso_name)
        a2_gripper_body_names = ("arm_body7", "arm_body8")
        missing_gripper_bodies = [
            body_name
            for body_name in a2_gripper_body_names
            if body_name not in self.simulator.body_names
        ]
        if missing_gripper_bodies:
            raise RuntimeError(
                "A2 hand_force requires gripper contact bodies "
                f"{a2_gripper_body_names}, missing {missing_gripper_bodies}"
            )
        self._a2_gripper_force_body_indices = [
            self.simulator.body_names.index(body_name) for body_name in a2_gripper_body_names
        ]
        self._upper_non_finger_dof_idx = list(self.upper_dof_indices)
        gripper_dof_indices = set(self._a2_gripper_dof_indices.tolist())
        self._upper_non_gripper_dof_idx = [
            int(dof_idx)
            for dof_idx in self.upper_dof_indices
            if int(dof_idx) not in gripper_dof_indices
        ]
        self._left_arm_dof_idx = torch.tensor(self.arm_dof_indices[:6], device=self.device)
        self._right_arm_dof_idx = torch.tensor(self.arm_dof_indices[:6], device=self.device)
        self.finger_dof_idx = torch.empty(0, dtype=torch.long, device=self.device)
        self.wrist_dof_idx = torch.empty(0, dtype=torch.long, device=self.device)
        self.left_hand_indices = []
        self.right_hand_indices = []
        self.left_hand_indices_tgt_ct_sensor = []
        self.right_hand_indices_tgt_ct_sensor = []
        self.left_hand_indices_convert = []
        self.right_hand_indices_convert = []
        self.left_palm_idx = self.end_effector_index
        self.right_palm_idx = self.end_effector_index
        self.left_hand_palm_side_direction = torch.tensor(
            [1.0, 0.0, 0.0, 0.0], device=self.device
        )
        self.right_hand_palm_side_direction = torch.tensor(
            [1.0, 0.0, 0.0, 0.0], device=self.device
        )
        self.dof_pos_humanly_lower_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_lower_limit_list, device=self.device
        )[None, :]
        self.dof_pos_humanly_upper_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_upper_limit_list, device=self.device
        )[None, :]

        self._register_task_state_to_track(self.simulator.scene.articulations["door"], "door")
        self._register_buffer_to_track(
            "delta_actions",
            self._get_delta_actions_buffer_shape(),
            self._store_delta_actions_buffer,
            self._load_delta_actions_buffer,
            dtype=torch.float32,
        )

        self.resting_dof_pos = torch.tensor([self.config.resting_dof_pos], device=self.device)
        self.target_root_pos = torch.tensor(self.config.target_root_pos, device=self.device)[
            None, :
        ]
        self._a2_stage2_single_contact_duration = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_stage2_prev_gripper_open_command = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_stage2_prev_gripper_raw_sign_valid = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_stage2_last_gripper_raw_sign_flip = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_stage3_stage4_prev_gripper_open_command = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_stage3_stage4_prev_gripper_raw_sign_valid = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_stage3_stage4_last_gripper_raw_sign_flip = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )

    def _get_a2_arm_default_dof_pos(self, env_ids=None):
        if not self._use_a2_base:
            raise RuntimeError("A2 arm default DOF target is only defined for A2 Piper configs.")
        num_arm_dof = len(self._upper_non_gripper_dof_idx)
        if num_arm_dof != 6:
            raise RuntimeError(
                "A2 arm default DOF target expects exactly arm_j1..arm_j6; "
                f"got {num_arm_dof} DOF indices: {self._upper_non_gripper_dof_idx}."
            )

        arm_default_pos = self.default_dof_pos[:, self._upper_non_gripper_dof_idx]
        if arm_default_pos.ndim != 2 or arm_default_pos.shape[1] != num_arm_dof:
            raise RuntimeError(
                "A2 arm default DOF target requires default_dof_pos[:, arm_j1..arm_j6] "
                f"shape (1 or {self.num_envs}, {num_arm_dof}); got "
                f"{tuple(arm_default_pos.shape)}."
            )

        if env_ids is None:
            target_batch = self.num_envs
        else:
            target_batch = len(env_ids)

        if arm_default_pos.shape[0] == 1:
            return arm_default_pos.repeat(target_batch, 1)
        if arm_default_pos.shape[0] == self.num_envs:
            if env_ids is None:
                return arm_default_pos
            return arm_default_pos[env_ids]
        raise RuntimeError(
            "A2 arm default DOF target requires default_dof_pos batch dim to be "
            f"1 or num_envs={self.num_envs}; got {arm_default_pos.shape[0]}."
        )

    @override
    def _apply_delta_action_overrides(self):
        if not self._use_a2_base:
            return

        expected_delta_action_indices = torch.tensor(
            [5, 6, 7, 8, 9, 10], dtype=self._delta_action_indices.dtype, device=self.device
        )
        if not torch.equal(self._delta_action_indices, expected_delta_action_indices):
            raise RuntimeError(
                "A2 stage0 arm default gate requires delta_action_indices "
                f"{expected_delta_action_indices.tolist()}; got "
                f"{self._delta_action_indices.tolist()}."
            )

        expected_shape = (self.num_envs, expected_delta_action_indices.numel())
        if tuple(self._delta_actions.shape) != expected_shape:
            raise RuntimeError(
                "A2 stage0 arm default gate requires _delta_actions shape "
                f"{expected_shape}; got {tuple(self._delta_actions.shape)}."
            )

        stage_buf = getattr(self, "stage_buf", None)
        stage_shape = None if not torch.is_tensor(stage_buf) else tuple(stage_buf.shape)
        if stage_shape != (self.num_envs,):
            raise RuntimeError(
                "A2 stage0 arm default gate requires stage_buf shape "
                f"({self.num_envs},); got {stage_shape}."
            )

        self._delta_actions[stage_buf == self.STAGE_WALK_TO_DOOR, :] = 0.0

    def _init_buffers(self):
        super()._init_buffers()
        if self._use_a2_base:
            self._a2_runtime_evidence_sensor_keys_logged = set()
            self._a2_stage2_squeeze_streak = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_stage3_stage4_both_contact_streak = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_stage3_grasp_streak_highwater = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_grasp_streak_last_full_update_step = -1
            self._a2_stage4_release_gate = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_root_x_ever_crossed = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_corridor_latched = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_stage5_hold_continuation = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_door_body_contact_event_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_door_body_contact_event_peak = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_door_body_contact_event_pending = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_door_body_contact_event_emitted = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_release_event_valid = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_hinge_at_release = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_root_x_at_release = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_post_release_body_contact = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_post_release_body_force_max = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_crossing_event_valid = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_crossing_while_holding = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_hinge_at_crossing = torch.full(
                (self.num_envs,),
                float("nan"),
                dtype=torch.float32,
                device=self.device,
            )
            self._a2_stage0_to1_staging_valid = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_stage0_to1_staging_standoff = torch.full(
                (self.num_envs,),
                float("nan"),
                dtype=torch.float32,
                device=self.device,
            )
            self._a2_stage0_root_height_sum = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_stage0_root_height_count = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_stage1_root_height_sum = torch.zeros(
                self.num_envs, dtype=torch.float32, device=self.device
            )
            self._a2_stage1_root_height_count = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_v14_root_height_last_update_step = -1
        self.relative_door_pos_buf = torch.zeros(
            self.num_envs, 3, device=self.device, requires_grad=False,
        )
        self.relative_door_rot_buf = torch.zeros(
            self.num_envs, 4, device=self.device, requires_grad=False
        )

        # door state buffer
        self.door_root_state_buf = torch.zeros(
            self.num_envs, 13, device=self.device, requires_grad=False
        )
        self.door_root_state_buf[:, 3] = 1.0  # w
        self.door_dof_state_buf = torch.zeros(
            self.num_envs, 3, device=self.device, requires_grad=False
        )
        self.door_root_state_buf[:, :3] += self.env_origins

    def _pre_compute_observations_callback(self, env_ids=None):
        super()._pre_compute_observations_callback(env_ids)
        if self._use_a2_base:
            self._update_a2_grasp_control_streaks(env_ids)
            self._update_a2_stage5_hold_continuation(env_ids)
            self._update_a2_door_body_contact_event(env_ids)
            self._update_a2_stage4_release_and_root_latches(env_ids)
            if env_ids is None:
                self._update_a2_v14_root_height_telemetry()
        env_ids = torch.arange(self.num_envs, device=self.device) if env_ids is None else env_ids

        current_root_pos = self.simulator.robot_root_states[env_ids, :3].clone()
        current_root_rot = self.simulator.robot_root_states[env_ids, 3:7].clone()
        current_root_rot_wxyz = xyzw_to_wxyz(current_root_rot)

        door_root_pos = self.simulator.get_task_root_state("door")[env_ids, :3].clone()
        door_root_pos[:, 2] = current_root_pos[:, 2]
        door_root_rot_wxyz = self.simulator.get_task_root_state("door")[env_ids, 3:7].clone()

        relative_door_pos, relative_door_rot = subtract_frame_transforms(
            current_root_pos, current_root_rot_wxyz, door_root_pos, door_root_rot_wxyz
        )
        self.relative_door_pos_buf[env_ids] = relative_door_pos
        self.relative_door_rot_buf[env_ids] = wxyz_to_xyzw(relative_door_rot)

    def _get_a2_door_body_contact_event_buffers(
        self, context: str
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        active = getattr(self, "_a2_door_body_contact_event_active", None)
        peak = getattr(self, "_a2_door_body_contact_event_peak", None)
        pending = getattr(self, "_a2_door_body_contact_event_pending", None)
        emitted = getattr(self, "_a2_door_body_contact_event_emitted", None)
        if (
            not torch.is_tensor(active)
            or tuple(active.shape) != (self.num_envs,)
            or active.dtype != torch.bool
            or active.device != torch.device(self.device)
        ):
            raise RuntimeError(
                f"{context} requires a device-local bool event-active buffer."
            )
        for name, value in (
            ("peak", peak),
            ("pending", pending),
            ("emitted", emitted),
        ):
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != (self.num_envs,)
                or not value.is_floating_point()
                or value.device != torch.device(self.device)
                or not torch.all(torch.isfinite(value))
                or torch.any(value < 0.0)
            ):
                raise RuntimeError(
                    f"{context} requires finite non-negative device-local event {name}."
                )
        if peak.dtype != pending.dtype or peak.dtype != emitted.dtype:
            raise RuntimeError(f"{context} requires matching event floating dtypes.")
        return active, peak, pending, emitted

    def _update_a2_door_body_contact_event(self, env_ids=None) -> None:
        if self._get_a2_door_body_contact_penalty_mode() != "event_v17":
            return
        if env_ids is not None:
            if (
                not torch.is_tensor(env_ids)
                or env_ids.ndim != 1
                or env_ids.dtype != torch.long
                or env_ids.device != torch.device(self.device)
                or torch.any(env_ids < 0)
                or torch.any(env_ids >= self.num_envs)
            ):
                raise RuntimeError(
                    "A2 body-contact event partial update requires valid device-local env ids."
                )
            return
        active, peak, pending, emitted = self._get_a2_door_body_contact_event_buffers(
            "A2 body-contact event update"
        )
        _per_filter, body_total = self._get_a2_door_body_panel_contact_forces()
        if body_total.dtype != peak.dtype:
            raise RuntimeError(
                "A2 body-contact event force and state buffers must share a dtype."
            )
        body_total = a2_scope_door_body_contact_force(
            self.stage_buf,
            body_total,
            self.STAGE_OPEN,
            self.STAGE_SWING,
        )
        force_threshold, peak_force_norm, component_cap = (
            self._get_a2_door_body_contact_event_config()
        )
        emitted.copy_(pending)
        pending.zero_()
        next_active, next_peak, ended_component = a2_update_door_body_contact_event(
            active,
            peak,
            body_total,
            force_threshold,
            peak_force_norm,
            component_cap,
        )
        active.copy_(next_active)
        peak.copy_(next_peak)
        emitted.add_(ended_component)

    def _finalize_a2_door_body_contact_event(self, env_ids: torch.Tensor) -> None:
        if self._get_a2_door_body_contact_penalty_mode() != "event_v17":
            return
        if (
            not torch.is_tensor(env_ids)
            or env_ids.ndim != 1
            or env_ids.dtype != torch.long
            or env_ids.device != torch.device(self.device)
            or torch.any(env_ids < 0)
            or torch.any(env_ids >= self.num_envs)
        ):
            raise RuntimeError(
                "A2 body-contact event stage finalization requires valid device-local env ids."
            )
        active, peak, pending, _emitted = self._get_a2_door_body_contact_event_buffers(
            "A2 body-contact event stage finalization"
        )
        finalize_mask = torch.zeros_like(active)
        finalize_mask[env_ids] = True
        _force_threshold, peak_force_norm, component_cap = (
            self._get_a2_door_body_contact_event_config()
        )
        next_active, next_peak, finalized_component = (
            a2_finalize_door_body_contact_event(
                active,
                peak,
                finalize_mask,
                peak_force_norm,
                component_cap,
            )
        )
        active.copy_(next_active)
        peak.copy_(next_peak)
        pending.add_(finalized_component)

    def _get_a2_stage5_hold_continuation(self) -> torch.Tensor:
        continuation = getattr(self, "_a2_stage5_hold_continuation", None)
        if (
            not torch.is_tensor(continuation)
            or tuple(continuation.shape) != (self.num_envs,)
            or continuation.dtype != torch.bool
            or continuation.device != torch.device(self.device)
        ):
            raise RuntimeError(
                "A2 stage5 hold continuation requires a device-local bool buffer."
            )
        return continuation

    def _update_a2_stage5_hold_continuation(self, env_ids=None) -> None:
        continuation = self._get_a2_stage5_hold_continuation()
        if env_ids is not None:
            if (
                not torch.is_tensor(env_ids)
                or env_ids.ndim != 1
                or env_ids.dtype != torch.long
                or env_ids.device != torch.device(self.device)
                or torch.any(env_ids < 0)
                or torch.any(env_ids >= self.num_envs)
            ):
                raise RuntimeError(
                    "A2 stage5 hold partial update requires valid device-local env ids."
                )
            return
        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "A2 stage5 hold continuation"
        )
        continuation.copy_(
            a2_update_stage5_hold_continuation(
                continuation,
                self.stage_buf,
                contact_masks["both_contact"],
                self.STAGE_THROUGH,
                self._get_a2_stage5_hold_income_continuity_enabled(),
            )
        )

    def _get_a2_door_income_hold_mask(self) -> torch.Tensor:
        historical_hold = self._get_a2_hold_streak_ok_mask()
        stage_buf = getattr(self, "stage_buf", None)
        if (
            not torch.is_tensor(stage_buf)
            or tuple(stage_buf.shape) != (self.num_envs,)
            or stage_buf.dtype != torch.long
            or stage_buf.device != torch.device(self.device)
        ):
            raise RuntimeError(
                "A2 door-income hold mask requires a device-local long stage buffer."
            )
        mask = historical_hold.clone()
        stage5 = stage_buf == self.STAGE_THROUGH
        if self._get_a2_stage5_hold_income_continuity_enabled():
            continuation = self._get_a2_stage5_hold_continuation()
            mask[stage5] = continuation[stage5]
        else:
            mask[stage5] = False
        return mask

    def _stage_3_to_4_advance_callback(self, env_ids: torch.Tensor) -> None:
        if self._use_a2_base:
            self._finalize_a2_door_body_contact_event(env_ids)

    def _stage_4_to_5_advance_callback(self, env_ids: torch.Tensor) -> None:
        if not self._use_a2_base:
            return
        self._finalize_a2_door_body_contact_event(env_ids)
        continuation = self._get_a2_stage5_hold_continuation()
        if self._get_a2_stage5_hold_income_continuity_enabled():
            hold_ok = self._get_a2_hold_streak_ok_mask()
            continuation[env_ids] = hold_ok[env_ids]
        else:
            continuation[env_ids] = False

    def _update_a2_grasp_control_streaks(self, env_ids=None):
        if not self._use_a2_base:
            raise RuntimeError(
                "A2 grasp control streaks are only defined for A2 Piper configs."
            )

        stage_buf = getattr(self, "stage_buf", None)
        actual_time_in_stage_buf = getattr(self, "actual_time_in_stage_buf", None)
        just_resetted_buf = getattr(self, "just_resetted_buf", None)
        for field_name, field_value, field_dtype in (
            ("stage_buf", stage_buf, torch.long),
            ("actual_time_in_stage_buf", actual_time_in_stage_buf, torch.long),
            ("just_resetted_buf", just_resetted_buf, torch.bool),
        ):
            if (
                field_value is None
                or not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
                or field_value.dtype != field_dtype
                or field_value.device != torch.device(self.device)
            ):
                shape = None if not torch.is_tensor(field_value) else tuple(field_value.shape)
                dtype = None if not torch.is_tensor(field_value) else field_value.dtype
                device = None if not torch.is_tensor(field_value) else field_value.device
                raise RuntimeError(
                    f"A2 grasp control streak update requires {field_name} "
                    f"{field_dtype} tensor shape ({self.num_envs},) on {self.device}; "
                    f"got shape={shape}, dtype={dtype}, device={device}."
                )

        stage2_streak = self._get_a2_grasp_control_streak_buffer(
            "_a2_stage2_squeeze_streak",
            "A2 stage2 squeeze streak update",
        )
        stage3_stage4_streak = self._get_a2_grasp_control_streak_buffer(
            "_a2_stage3_stage4_both_contact_streak",
            "A2 stage3/4 both-contact streak update",
        )
        stage3_highwater = getattr(self, "_a2_stage3_grasp_streak_highwater", None)
        if (
            stage3_highwater is None
            or not torch.is_tensor(stage3_highwater)
            or tuple(stage3_highwater.shape) != (self.num_envs,)
            or stage3_highwater.dtype != torch.bool
            or stage3_highwater.device != torch.device(self.device)
        ):
            shape = None if not torch.is_tensor(stage3_highwater) else tuple(stage3_highwater.shape)
            dtype = None if not torch.is_tensor(stage3_highwater) else stage3_highwater.dtype
            device = None if not torch.is_tensor(stage3_highwater) else stage3_highwater.device
            raise RuntimeError(
                "A2 stage3 high-water streak requires bool tensor shape "
                f"({self.num_envs},) on {self.device}; got shape={shape}, "
                f"dtype={dtype}, device={device}."
            )

        if env_ids is not None:
            if (
                not torch.is_tensor(env_ids)
                or env_ids.ndim != 1
                or env_ids.dtype != torch.long
                or env_ids.device != torch.device(self.device)
                or torch.any(env_ids < 0)
                or torch.any(env_ids >= self.num_envs)
            ):
                raise RuntimeError(
                    "A2 grasp control streak partial callback requires valid long env_ids "
                    f"on {self.device}; got {env_ids!r}."
                )
            reset_mask = just_resetted_buf[env_ids] | (
                actual_time_in_stage_buf[env_ids] == 0
            )
            if not torch.all(reset_mask):
                raise RuntimeError(
                    "A2 grasp control streak partial callback is only valid for reset "
                    "or stage-switch envs; refusing a duplicate control-step increment."
                )
            stage2_streak[env_ids] = 0
            stage3_stage4_streak[env_ids] = 0
            stage3_highwater[env_ids] = False
            return

        common_step_counter = getattr(self, "common_step_counter", None)
        if isinstance(common_step_counter, bool) or not isinstance(
            common_step_counter, int
        ):
            raise RuntimeError(
                "A2 grasp control streak update requires integer common_step_counter; "
                f"got {common_step_counter!r}."
            )
        last_update_step = getattr(
            self, "_a2_grasp_streak_last_full_update_step", None
        )
        if isinstance(last_update_step, bool) or not isinstance(last_update_step, int):
            raise RuntimeError(
                "A2 grasp control streak update requires integer "
                "_a2_grasp_streak_last_full_update_step; "
                f"got {last_update_step!r}."
            )
        if common_step_counter <= last_update_step:
            raise RuntimeError(
                "A2 grasp control streak full update must run exactly once per control "
                f"step; current={common_step_counter}, last={last_update_step}."
            )

        history_masks = self._get_a2_stage2_contact_squeeze_masks(
            self._get_a2_gripper_handle_contact_force_history(),
            "A2 grasp control streak update",
        )
        stage2_squeeze_current = (
            history_masks["both_contact"][:, 0]
            & history_masks["sufficient_squeeze"][:, 0]
            & history_masks["opposite_squeeze"][:, 0]
        )
        stage3_stage4_both_contact_current = history_masks["both_contact"][:, 0]
        reset_mask = just_resetted_buf | (actual_time_in_stage_buf == 0)
        stage2_condition = (
            (stage_buf == self.STAGE_GRASP) & stage2_squeeze_current
        )
        stage3_stage4_condition = (
            ((stage_buf == self.STAGE_OPEN) | (stage_buf == self.STAGE_SWING))
            & stage3_stage4_both_contact_current
        )
        self._a2_stage2_squeeze_streak[:] = a2_update_grasp_control_streak(
            stage2_streak,
            stage2_condition,
            reset_mask,
        )
        self._a2_stage3_stage4_both_contact_streak[:] = a2_update_grasp_control_streak(
            stage3_stage4_streak,
            stage3_stage4_condition,
            reset_mask,
        )
        stage3_highwater[reset_mask] = False
        stage3_reached_k = (
            (stage_buf == self.STAGE_OPEN)
            & (
                self._a2_stage3_stage4_both_contact_streak
                >= self._get_a2_grasp_streak_control_steps()
            )
        )
        stage3_highwater |= stage3_reached_k
        self._a2_grasp_streak_last_full_update_step = common_step_counter

    def _update_a2_v14_root_height_telemetry(self):
        stage_buf = getattr(self, "stage_buf", None)
        root_states = getattr(self.simulator, "robot_root_states", None)
        env_origins = getattr(self, "env_origins", None)
        common_step_counter = getattr(self, "common_step_counter", None)
        if (
            not torch.is_tensor(stage_buf)
            or tuple(stage_buf.shape) != (self.num_envs,)
            or stage_buf.dtype != torch.long
            or stage_buf.device != torch.device(self.device)
            or not torch.is_tensor(root_states)
            or root_states.ndim != 2
            or root_states.shape[0] != self.num_envs
            or root_states.shape[1] < 3
            or not root_states.is_floating_point()
            or root_states.device != torch.device(self.device)
            or not torch.is_tensor(env_origins)
            or tuple(env_origins.shape) != (self.num_envs, 3)
            or env_origins.dtype != root_states.dtype
            or env_origins.device != root_states.device
            or not torch.all(torch.isfinite(root_states[:, :3]))
            or not torch.all(torch.isfinite(env_origins))
            or isinstance(common_step_counter, bool)
            or not isinstance(common_step_counter, int)
        ):
            raise RuntimeError(
                "A2 v14 root-height telemetry requires finite device-local stage/root "
                "state and an integer common_step_counter."
            )
        last_step = self._a2_v14_root_height_last_update_step
        if common_step_counter < last_step:
            raise RuntimeError(
                "A2 v14 root-height telemetry common_step_counter moved backwards."
            )
        if common_step_counter == last_step:
            return

        root_height = root_states[:, 2] - env_origins[:, 2]
        stage0 = stage_buf == self.STAGE_WALK_TO_DOOR
        stage1 = stage_buf == self.STAGE_PREGRASP
        self._a2_stage0_root_height_sum += torch.where(
            stage0,
            root_height,
            torch.zeros_like(root_height),
        )
        self._a2_stage0_root_height_count += stage0.long()
        self._a2_stage1_root_height_sum += torch.where(
            stage1,
            root_height,
            torch.zeros_like(root_height),
        )
        self._a2_stage1_root_height_count += stage1.long()
        self._a2_v14_root_height_last_update_step = common_step_counter

    def _record_a2_stage0_to1_staging_standoff(
        self,
        advance_mask: torch.Tensor,
        grasp_target: torch.Tensor,
        root_pos: torch.Tensor,
    ) -> None:
        valid = self._a2_stage0_to1_staging_valid
        standoff_buffer = self._a2_stage0_to1_staging_standoff
        if (
            not torch.is_tensor(advance_mask)
            or tuple(advance_mask.shape) != (self.num_envs,)
            or advance_mask.dtype != torch.bool
            or advance_mask.device != torch.device(self.device)
            or not torch.is_tensor(valid)
            or tuple(valid.shape) != (self.num_envs,)
            or valid.dtype != torch.bool
            or valid.device != advance_mask.device
            or not torch.is_tensor(standoff_buffer)
            or tuple(standoff_buffer.shape) != (self.num_envs,)
            or not standoff_buffer.is_floating_point()
            or standoff_buffer.device != advance_mask.device
        ):
            raise RuntimeError(
                "A2 v14 staging telemetry requires matching device-local buffers."
            )
        _validate_a2_stage0_staging_tensors(root_pos, grasp_target)
        standoff = grasp_target[:, 0] - root_pos[:, 0]
        if not torch.all(torch.isfinite(standoff)):
            raise RuntimeError("A2 v14 staging standoff must be finite.")
        first_advance = advance_mask & ~valid
        standoff_buffer[first_advance] = standoff[first_advance]
        valid[first_advance] = True

    def _get_a2_v14_telemetry_fields(self, env_ids):
        env_ids = self._normalize_render_env_ids(env_ids)
        crossing_valid = self._a2_crossing_event_valid
        crossing_while_holding = self._a2_crossing_while_holding
        hinge_at_crossing = self._a2_hinge_at_crossing
        release_valid = self._a2_release_event_valid
        hinge_at_release = self._a2_hinge_at_release
        root_x_at_release = self._a2_root_x_at_release
        post_release_body_contact = self._a2_post_release_body_contact
        post_release_body_force_max = self._a2_post_release_body_force_max
        staging_valid = self._a2_stage0_to1_staging_valid
        staging_standoff = self._a2_stage0_to1_staging_standoff
        stage0_sum = self._a2_stage0_root_height_sum
        stage0_count = self._a2_stage0_root_height_count
        stage1_sum = self._a2_stage1_root_height_sum
        stage1_count = self._a2_stage1_root_height_count

        float_fields = {
            "door_hinge_drive_max_force": self.door_hinge_drive_max_force,
            "door_handle_drive_max_force": self.door_handle_drive_max_force,
            "door_handle_height": self.door_handle_height,
            "door_weight": self.door_weight,
            "_a2_hinge_at_crossing": hinge_at_crossing,
            "_a2_hinge_at_release": hinge_at_release,
            "_a2_root_x_at_release": root_x_at_release,
            "_a2_post_release_body_force_max": post_release_body_force_max,
            "_a2_stage0_to1_staging_standoff": staging_standoff,
            "_a2_stage0_root_height_sum": stage0_sum,
            "_a2_stage1_root_height_sum": stage1_sum,
        }
        bool_fields = {
            "_a2_crossing_event_valid": crossing_valid,
            "_a2_crossing_while_holding": crossing_while_holding,
            "_a2_release_event_valid": release_valid,
            "_a2_post_release_body_contact": post_release_body_contact,
            "_a2_stage0_to1_staging_valid": staging_valid,
        }
        long_fields = {
            "_a2_stage0_root_height_count": stage0_count,
            "_a2_stage1_root_height_count": stage1_count,
        }
        for field_name, field_value in float_fields.items():
            if (
                not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
                or not field_value.is_floating_point()
                or field_value.device != torch.device(self.device)
            ):
                raise RuntimeError(
                    f"A2 v14 telemetry requires {field_name} floating tensor "
                    f"shape ({self.num_envs},) on {self.device}."
                )
        for field_name, field_value in bool_fields.items():
            if (
                not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
                or field_value.dtype != torch.bool
                or field_value.device != torch.device(self.device)
            ):
                raise RuntimeError(
                    f"A2 v14 telemetry requires {field_name} bool tensor "
                    f"shape ({self.num_envs},) on {self.device}."
                )
        for field_name, field_value in long_fields.items():
            if (
                not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
                or field_value.dtype != torch.long
                or field_value.device != torch.device(self.device)
                or torch.any(field_value < 0)
            ):
                raise RuntimeError(
                    f"A2 v14 telemetry requires {field_name} non-negative long "
                    f"tensor shape ({self.num_envs},) on {self.device}."
                )
        if (
            not torch.all(torch.isfinite(self.door_hinge_drive_max_force))
            or not torch.all(torch.isfinite(self.door_handle_drive_max_force))
            or not torch.all(torch.isfinite(self.door_handle_height))
            or not torch.all(torch.isfinite(self.door_weight))
            or not torch.all(torch.isfinite(hinge_at_crossing[crossing_valid]))
            or not torch.all(torch.isfinite(hinge_at_release[release_valid]))
            or not torch.all(torch.isfinite(root_x_at_release[release_valid]))
            or not torch.all(torch.isfinite(post_release_body_force_max))
            or not torch.all(torch.isfinite(staging_standoff[staging_valid]))
            or not torch.all(torch.isfinite(stage0_sum))
            or not torch.all(torch.isfinite(stage1_sum))
        ):
            raise RuntimeError("A2 v14 telemetry contains non-finite recorded values.")

        selected = {
            name: value[env_ids].detach().cpu().tolist()
            for name, value in {
                **float_fields,
                **bool_fields,
                **long_fields,
            }.items()
        }
        records = []
        for index in range(env_ids.numel()):
            crossing_is_valid = bool(
                selected["_a2_crossing_event_valid"][index]
            )
            release_is_valid = bool(selected["_a2_release_event_valid"][index])
            staging_is_valid = bool(
                selected["_a2_stage0_to1_staging_valid"][index]
            )
            stage0_samples = int(
                selected["_a2_stage0_root_height_count"][index]
            )
            stage1_samples = int(
                selected["_a2_stage1_root_height_count"][index]
            )
            records.append(
                {
                    "door_hinge_drive_max_force": float(
                        selected["door_hinge_drive_max_force"][index]
                    ),
                    "door_handle_drive_max_force": float(
                        selected["door_handle_drive_max_force"][index]
                    ),
                    "door_handle_height": float(
                        selected["door_handle_height"][index]
                    ),
                    "door_weight": float(selected["door_weight"][index]),
                    "crossing_while_holding": (
                        bool(selected["_a2_crossing_while_holding"][index])
                        if crossing_is_valid
                        else None
                    ),
                    "hinge_at_crossing": (
                        float(selected["_a2_hinge_at_crossing"][index])
                        if crossing_is_valid
                        else None
                    ),
                    "hinge_at_release": (
                        float(selected["_a2_hinge_at_release"][index])
                        if release_is_valid
                        else None
                    ),
                    "root_x_at_release": (
                        float(selected["_a2_root_x_at_release"][index])
                        if release_is_valid
                        else None
                    ),
                    "post_release_body_contact": (
                        bool(selected["_a2_post_release_body_contact"][index])
                        if release_is_valid
                        else None
                    ),
                    "post_release_body_force_max": (
                        float(selected["_a2_post_release_body_force_max"][index])
                        if release_is_valid
                        else None
                    ),
                    "stage0_to1_staging_standoff": (
                        float(
                            selected[
                                "_a2_stage0_to1_staging_standoff"
                            ][index]
                        )
                        if staging_is_valid
                        else None
                    ),
                    "stage0_actual_root_height": (
                        float(
                            selected["_a2_stage0_root_height_sum"][index]
                            / stage0_samples
                        )
                        if stage0_samples > 0
                        else None
                    ),
                    "stage1_actual_root_height": (
                        float(
                            selected["_a2_stage1_root_height_sum"][index]
                            / stage1_samples
                        )
                        if stage1_samples > 0
                        else None
                    ),
                }
            )
        return records

    def _update_a2_stage4_release_and_root_latches(self, env_ids=None):
        if not self._use_a2_base:
            raise RuntimeError("A2 route latches are only defined for A2 Piper configs.")
        release_gate = getattr(self, "_a2_stage4_release_gate", None)
        root_x_ever_crossed = getattr(self, "_a2_root_x_ever_crossed", None)
        corridor_latched = getattr(self, "_a2_corridor_latched", None)
        release_event_valid = getattr(self, "_a2_release_event_valid", None)
        hinge_at_release = getattr(self, "_a2_hinge_at_release", None)
        root_x_at_release = getattr(self, "_a2_root_x_at_release", None)
        post_release_body_contact = getattr(self, "_a2_post_release_body_contact", None)
        post_release_body_force_max = getattr(self, "_a2_post_release_body_force_max", None)
        crossing_event_valid = getattr(self, "_a2_crossing_event_valid", None)
        crossing_while_holding = getattr(
            self, "_a2_crossing_while_holding", None
        )
        hinge_at_crossing = getattr(self, "_a2_hinge_at_crossing", None)
        stage_buf = getattr(self, "stage_buf", None)
        for field_name, field_value, expected_dtype in (
            ("_a2_stage4_release_gate", release_gate, torch.bool),
            ("_a2_root_x_ever_crossed", root_x_ever_crossed, torch.bool),
            ("_a2_corridor_latched", corridor_latched, torch.bool),
            ("_a2_release_event_valid", release_event_valid, torch.bool),
            ("_a2_post_release_body_contact", post_release_body_contact, torch.bool),
            ("_a2_crossing_event_valid", crossing_event_valid, torch.bool),
            ("_a2_crossing_while_holding", crossing_while_holding, torch.bool),
            ("stage_buf", stage_buf, torch.long),
        ):
            if (
                not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
                or field_value.dtype != expected_dtype
                or field_value.device != torch.device(self.device)
            ):
                shape = None if not torch.is_tensor(field_value) else tuple(field_value.shape)
                dtype = None if not torch.is_tensor(field_value) else field_value.dtype
                device = None if not torch.is_tensor(field_value) else field_value.device
                raise RuntimeError(
                    f"A2 route latch update requires {field_name} shape ({self.num_envs},), "
                    f"dtype={expected_dtype}, device={self.device}; got shape={shape}, "
                    f"dtype={dtype}, device={device}."
                )
        if (
            not torch.is_tensor(hinge_at_crossing)
            or tuple(hinge_at_crossing.shape) != (self.num_envs,)
            or not hinge_at_crossing.is_floating_point()
            or hinge_at_crossing.device != torch.device(self.device)
            or not torch.all(
                torch.isfinite(hinge_at_crossing[crossing_event_valid])
            )
        ):
            raise RuntimeError(
                "A2 crossing telemetry requires a finite hinge value for every "
                "recorded crossing."
            )
        for field_name, field_value in (
            ("_a2_hinge_at_release", hinge_at_release),
            ("_a2_root_x_at_release", root_x_at_release),
            ("_a2_post_release_body_force_max", post_release_body_force_max),
        ):
            if (
                not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
                or not field_value.is_floating_point()
                or field_value.device != torch.device(self.device)
            ):
                raise RuntimeError(
                    f"A2 release telemetry requires {field_name} floating tensor shape "
                    f"({self.num_envs},) on {self.device}."
                )
        if (
            not torch.all(torch.isfinite(hinge_at_release[release_event_valid]))
            or not torch.all(torch.isfinite(root_x_at_release[release_event_valid]))
            or not torch.all(torch.isfinite(post_release_body_force_max))
            or torch.any(post_release_body_force_max < 0.0)
        ):
            raise RuntimeError("A2 release telemetry contains invalid recorded values.")
        if env_ids is None:
            update_mask = None
        else:
            if (
                not torch.is_tensor(env_ids)
                or env_ids.ndim != 1
                or env_ids.dtype != torch.long
                or env_ids.device != torch.device(self.device)
                or torch.any(env_ids < 0)
                or torch.any(env_ids >= self.num_envs)
            ):
                raise RuntimeError(
                    "A2 route latch partial callback requires valid device-local long env_ids."
                )
            update_mask = torch.zeros_like(release_gate)
            update_mask[env_ids] = True
        root_states = getattr(self.simulator, "robot_root_states", None)
        env_origins = getattr(self, "env_origins", None)
        if (
            not torch.is_tensor(root_states)
            or root_states.ndim != 2
            or root_states.shape[0] != self.num_envs
            or root_states.shape[1] < 3
            or not root_states.is_floating_point()
            or root_states.device != torch.device(self.device)
        ):
            shape = None if not torch.is_tensor(root_states) else tuple(root_states.shape)
            raise RuntimeError(
                f"A2 route latch update requires robot_root_states shape ({self.num_envs}, >=3) "
                f"on {self.device}; got {shape}."
            )
        if (
            not torch.is_tensor(env_origins)
            or tuple(env_origins.shape) != (self.num_envs, 3)
            or not env_origins.is_floating_point()
            or env_origins.device != torch.device(self.device)
        ):
            shape = None if not torch.is_tensor(env_origins) else tuple(env_origins.shape)
            raise RuntimeError(
                f"A2 route latch update requires env_origins shape ({self.num_envs}, 3) "
                f"on {self.device}; got {shape}."
            )
        door_joint_pos = self._get_door_joint_pos("A2 route latch update", 1)
        root_x = root_states[:, 0] - env_origins[:, 0]
        effective_update_mask = (
            torch.ones_like(root_x_ever_crossed)
            if update_mask is None
            else update_mask
        )
        first_crossing = (
            effective_update_mask & ~root_x_ever_crossed & (root_x > 0.0)
        )
        if torch.any(first_crossing):
            contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
                "A2 root-X crossing telemetry"
            )
            both_contact = contact_masks["both_contact"]
            if (
                not torch.is_tensor(both_contact)
                or tuple(both_contact.shape) != (self.num_envs,)
                or both_contact.dtype != torch.bool
                or both_contact.device != torch.device(self.device)
            ):
                raise RuntimeError(
                    "A2 root-X crossing telemetry requires a device-local "
                    "both-contact mask."
                )
            crossing_while_holding[first_crossing] = both_contact[first_crossing]
            hinge_at_crossing[first_crossing] = door_joint_pos[first_crossing, 0]
            crossing_event_valid[first_crossing] = True

        updated_gate, updated_crossed = (
            a2_update_stage4_release_and_root_latches_through_stage5(
                release_gate,
                root_x_ever_crossed,
                stage_buf,
                door_joint_pos[:, 0],
                root_x,
                self._get_a2_stage4_release_hinge_threshold(),
                self.STAGE_SWING,
                self.STAGE_THROUGH,
                self._get_a2_stage5_hold_income_continuity_enabled(),
                update_mask,
            )
        )
        updated_corridor = a2_update_corridor_latch(
            corridor_latched,
            updated_crossed,
            stage_buf,
            door_joint_pos[:, 0],
            self.STAGE_SWING,
            self._get_a2_corridor_enabled(),
            update_mask,
        )
        release_event = ~release_gate & updated_gate
        hinge_at_release[release_event] = door_joint_pos[release_event, 0]
        root_x_at_release[release_event] = root_x[release_event]
        release_event_valid |= release_event
        post_release_active = updated_gate & (stage_buf >= self.STAGE_SWING)
        _body_force_per_filter, body_force_total = (
            self._get_a2_door_body_panel_contact_forces()
        )
        post_release_body_contact |= post_release_active & (body_force_total > 1.0)
        post_release_body_force_max[:] = torch.maximum(
            post_release_body_force_max,
            torch.where(
                post_release_active,
                body_force_total,
                torch.zeros_like(body_force_total),
            ),
        )
        release_gate[:] = updated_gate
        root_x_ever_crossed[:] = updated_crossed
        corridor_latched[:] = updated_corridor

    @StagedTaskBase.effective_in_stage(STAGE_WALK_TO_DOOR)
    def _reward_walk_to_door(self):
        # Track the nearest point in the handle-relative staging band. Inside the
        # band the target equals the root pose, so this reward has no standoff bias.
        current_root_pos = self.simulator.robot_root_states[:, :3].clone()
        grasp_target_pos = self._compute_grasp_target().clone()
        x_min, x_max, y_tol = self._get_a2_stage0_staging_band()
        stage0_target_pos = a2_stage0_nearest_staging_target(
            current_root_pos,
            grasp_target_pos,
            x_min,
            x_max,
            y_tol,
        )
        target_direction = stage0_target_pos - current_root_pos
        target_distance = torch.linalg.norm(target_direction, dim=-1, keepdim=True)
        nonzero_distance = target_distance > 0.0
        divisor = torch.where(
            nonzero_distance,
            target_distance,
            torch.ones_like(target_distance),
        )
        target_dir = torch.where(
            nonzero_distance,
            target_direction / divisor,
            torch.zeros_like(target_direction),
        )
        current_root_vel = self.simulator.robot_root_states[:, 7:10].clone()

        target_vel = self.config.get("target_root_vel", 0.3) * target_dir

        return self._tracking_reward_util(
            torch.linalg.norm(current_root_vel - target_vel, dim=-1),
            std=0.15,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

    @StagedTaskBase.effective_in_stage([STAGE_WALK_TO_DOOR, STAGE_THROUGH])
    def _reward_penalty_upper_body_non_gripper_deviation_l1(self):
        """A2 stage0 PASS: Piper arm_j1..j6 default-pose shaping."""
        # Exclude arm_j7/arm_j8 so gripper open/close does not affect arm pose shaping.
        if self._use_a2_base:
            target_pos = self._get_a2_arm_default_dof_pos()
        else:
            target_pos = self.default_dof_pos[:, self._upper_non_gripper_dof_idx]
        return torch.abs(
            self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx]
            - target_pos
        ).sum(dim=-1)

    @StagedTaskBase.effective_in_stage(STAGE_SWING)
    def _reward_penalty_a2_stage4_arm_default_pose_l1(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "penalty_a2_stage4_arm_default_pose_l1 is only defined for A2 Piper configs."
            )
        target_pos = self._get_a2_arm_default_dof_pos()
        dof_pos = getattr(self.simulator, "dof_pos", None)
        max_arm_dof_index = max(self._upper_non_gripper_dof_idx)
        if (
            dof_pos is None
            or not torch.is_tensor(dof_pos)
            or dof_pos.ndim != 2
            or dof_pos.shape[0] != self.num_envs
            or dof_pos.shape[1] <= max_arm_dof_index
        ):
            shape = None if dof_pos is None else tuple(dof_pos.shape)
            raise RuntimeError(
                "penalty_a2_stage4_arm_default_pose_l1 requires simulator.dof_pos "
                f"shape ({self.num_envs}, >{max_arm_dof_index}); got {shape}."
            )
        arm_pos = dof_pos[:, self._upper_non_gripper_dof_idx]
        if tuple(arm_pos.shape) != (self.num_envs, 6):
            raise RuntimeError(
                "penalty_a2_stage4_arm_default_pose_l1 expects arm_j1..arm_j6 "
                f"shape ({self.num_envs}, 6); got {tuple(arm_pos.shape)}."
            )
        return torch.abs(arm_pos - target_pos).sum(dim=-1)

    @StagedTaskBase.effective_in_stage([STAGE_WALK_TO_DOOR, STAGE_PREGRASP, STAGE_GRASP, STAGE_THROUGH])
    def _reward_pregrasp_gripper_dof_pos_l1(self):
        """A2 gripper shaping: stage0 and stage5 track close target (gripper
        stowed while walking); stage1 and stage2-gate-outside track open target
        (gripper opens to prepare grasp and stays open until close to handle);
        stage2 gate inside is excluded so a2_stage2_close_* rewards take over.
        """
        gripper_pos = self.simulator.dof_pos[:, self._a2_gripper_dof_indices]
        gripper_vel = self.simulator.dof_vel[:, self._a2_gripper_dof_indices]
        is_walk = self.stage_buf == self.STAGE_WALK_TO_DOOR
        is_through = self.stage_buf == self.STAGE_THROUGH
        track_close = is_walk | is_through
        # In stage2, only track open target when outside the close-reward gate
        # (i.e. gripper not yet close enough to handle). Inside the gate, return
        # zero so a2_stage2_close_command / a2_stage2_close_progress drive close.
        if self._use_a2_base:
            stage2_gate = self._get_a2_stage2_close_reward_gate()
            track_open = (~track_close) & (~stage2_gate)
            target = torch.where(
                track_close[:, None],
                self._a2_gripper_close_target,
                self._a2_gripper_open_target,
            )
            gate_mask = (track_close | track_open).float()
        else:
            target = torch.where(
                track_close[:, None],
                self._a2_gripper_close_target,
                self._a2_gripper_open_target,
            )
            gate_mask = torch.ones(self.num_envs, device=self.device)
        span = (self._a2_gripper_open_target - self._a2_gripper_close_target).abs().clamp_min(1.0e-4)
        pos_track = self._tracking_reward_util(
            (gripper_pos - target) / span[None, :],
            std=0.25,
            target=0.0,
            scale=1.0,
            offset=0.0,
        ).mean(dim=-1)
        vel_track = self._tracking_reward_util(
            gripper_vel / span[None, :],
            std=0.5,
            target=0.0,
            scale=1.0,
            offset=0.0,
        ).mean(dim=-1)
        return ((pos_track + 0.2 * vel_track).clamp(max=1.0)) * gate_mask

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_penalty_unused_dof_deviation_l1(self):
        """Penalize the deviation of the unused arm dof during door opening"""
        left_diff = (
            self.simulator.dof_pos[:, self._left_arm_dof_idx]
            - self.resting_dof_pos[:, self._left_arm_dof_idx]
        )
        right_diff = (
            self.simulator.dof_pos[:, self._right_arm_dof_idx]
            - self.resting_dof_pos[:, self._right_arm_dof_idx]
        )
        return torch.where(self.door_open_lr[:, None] < 0, right_diff, left_diff).abs().sum(dim=-1)

    def _get_a2_gripper_handle_orientation_metrics(self):
        if not self._use_a2_base:
            raise RuntimeError("gripper_handle_orientation is only defined for A2 Piper configs.")

        data = self._get_a2_gripper_handle_frame_transformer().data
        target_quat_source = getattr(data, "target_quat_source", None)
        if (
            target_quat_source is None
            or target_quat_source.ndim != 3
            or target_quat_source.shape[0] != self.num_envs
            or target_quat_source.shape[1] != 2
            or target_quat_source.shape[2] != 4
        ):
            shape = None if target_quat_source is None else tuple(target_quat_source.shape)
            raise RuntimeError(
                "A2 gripper_handle_orientation requires target_quat_source shape "
                f"({self.num_envs}, 2, 4); got {shape}."
            )

        q_target_source = target_quat_source[:, 1, :]
        source_y = q_target_source.new_tensor((0.0, 1.0, 0.0)).expand(self.num_envs, -1)
        source_z = q_target_source.new_tensor((0.0, 0.0, 1.0)).expand(self.num_envs, -1)

        target_y_source = quat_apply(q_target_source, source_y)
        target_z_source = quat_apply(q_target_source, source_z)
        opening_alignment = torch.abs(torch.sum(source_y * target_y_source, dim=-1)).clamp(
            0.0, 1.0
        )
        approach_alignment = torch.sum(source_z * target_z_source, dim=-1).clamp(-1.0, 1.0)
        return opening_alignment, approach_alignment

    def _get_a2_stage2_close_reward_gate(self):
        if not self._use_a2_base:
            raise RuntimeError("A2 stage2 close rewards are only defined for A2 Piper configs.")

        stage_buf = getattr(self, "stage_buf", None)
        if (
            stage_buf is None
            or not torch.is_tensor(stage_buf)
            or tuple(stage_buf.shape) != (self.num_envs,)
        ):
            shape = None if stage_buf is None else tuple(stage_buf.shape)
            raise RuntimeError(
                "A2 stage2 close rewards require stage_buf shape "
                f"({self.num_envs},); got {shape}."
            )

        data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = getattr(data, "target_pos_source", None)
        if (
            target_pos_source is None
            or target_pos_source.ndim != 3
            or tuple(target_pos_source.shape) != (self.num_envs, 2, 3)
        ):
            shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            raise RuntimeError(
                "A2 stage2 close rewards require target_pos_source shape "
                f"({self.num_envs}, 2, 3); got {shape}."
            )

        handle_pos_source = target_pos_source[:, 0, :]
        y_tol = self._get_required_positive_float_config(
            "stage2_close_gate_y_tol", "A2 stage2 close rewards"
        )
        z_tol = self._get_required_positive_float_config(
            "stage2_close_gate_z_tol", "A2 stage2 close rewards"
        )
        x_tol = self._get_required_positive_float_config(
            "stage2_close_gate_x_tol", "A2 stage2 close rewards"
        )
        opening_alignment, approach_alignment = self._get_a2_gripper_handle_orientation_metrics()
        return (
            (stage_buf == self.STAGE_GRASP)
            & (handle_pos_source[:, 1].abs() < y_tol)
            & (handle_pos_source[:, 2].abs() < z_tol)
            & (handle_pos_source[:, 0].abs() < x_tol)
            & (opening_alignment >= 0.9)
            & (approach_alignment >= 0.9)
        )

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_gripper_handle_orientation(self):
        opening_alignment, approach_alignment = self._get_a2_gripper_handle_orientation_metrics()
        opening_track = self._tracking_reward_util(
            1.0 - opening_alignment, std=0.25, target=0.0, scale=1.0, offset=0.0
        )
        approach_track = self._tracking_reward_util(
            1.0 - approach_alignment, std=0.25, target=0.0, scale=1.0, offset=0.0
        )
        return (opening_track * approach_track).clamp(0.0, 1.0)

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_hand_handle_orientation(self):
        if self._use_a2_base:
            raise RuntimeError(
                "A2 configs must use 'gripper_handle_orientation' instead of legacy "
                "'hand_handle_orientation'."
            )
        mask = (self.door_open_lr < 0)[:, None]
        rot_90 = quat_from_euler_xyz(
            torch.full((self.num_envs,), torch.pi / 2.0, device=self.device),
            torch.zeros(self.num_envs, device=self.device),
            torch.zeros(self.num_envs, device=self.device),
        )
        rot_neg_90 = quat_from_euler_xyz(
            torch.full((self.num_envs,), -torch.pi / 2.0, device=self.device),
            torch.zeros(self.num_envs, device=self.device),
            torch.zeros(self.num_envs, device=self.device),
        )
        left_target_rot = self.simulator.left_hand_transform_rot[:, 0, :]
        right_target_rot = self.simulator.right_hand_transform_rot[:, 0, :]
        current_hand_rot = torch.where(mask, left_target_rot, right_target_rot)
        relative_rot = quat_mul(current_hand_rot, torch.where(mask, rot_90, rot_neg_90))
        return self._tracking_reward_util(
            wrap_to_pi(axis_angle_from_quat(relative_rot).norm(dim=-1)),
            std=0.6,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN])
    def _reward_standing_still(self):
        norm = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1)
        return self._tracking_reward_util(norm, std=0.05, target=0.0, scale=1.0, offset=0.0)

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN])
    def _reward_penalty_not_standing_still(self):
        norm = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1)
        if self._use_a2_base and self._get_a2_stage3_base_unlocked():
            norm = torch.where(
                self.stage_buf == self.STAGE_OPEN,
                torch.zeros_like(norm),
                norm,
            )
        return norm

    @StagedTaskBase.effective_in_stage(STAGE_SWING)
    def _reward_penalty_standing_still(self):
        norm = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1)
        return self._tracking_reward_util(norm, std=0.05, target=0.0, scale=1.0, offset=0.0)

    @StagedTaskBase.effective_in_stage(STAGE_PREGRASP)
    def _reward_pregrasp_target_distance(self):
        if self._use_a2_base:
            data = self._get_a2_gripper_handle_frame_transformer().data

            target_pos_source = getattr(data, "target_pos_source", None)
            if (
                target_pos_source is None
                or target_pos_source.ndim != 3
                or target_pos_source.shape != (self.num_envs, 2, 3)
            ):
                shape = None if target_pos_source is None else tuple(target_pos_source.shape)
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires target_pos_source shape "
                    f"({self.num_envs}, 2, 3); got {shape}."
                )

            target_pos_w = getattr(data, "target_pos_w", None)
            if (
                target_pos_w is None
                or target_pos_w.ndim != 3
                or target_pos_w.shape != (self.num_envs, 2, 3)
            ):
                shape = None if target_pos_w is None else tuple(target_pos_w.shape)
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires target_pos_w shape "
                    f"({self.num_envs}, 2, 3); got {shape}."
                )

            source_pos_w = getattr(data, "source_pos_w", None)
            if (
                source_pos_w is None
                or source_pos_w.ndim != 2
                or source_pos_w.shape != (self.num_envs, 3)
            ):
                shape = None if source_pos_w is None else tuple(source_pos_w.shape)
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires source_pos_w shape "
                    f"({self.num_envs}, 3); got {shape}."
                )

            rigid_body_vel = getattr(self.simulator, "_rigid_body_vel", None)
            if (
                rigid_body_vel is None
                or rigid_body_vel.ndim != 3
                or rigid_body_vel.shape[0] != self.num_envs
                or rigid_body_vel.shape[1] <= self.end_effector_index
                or rigid_body_vel.shape[2] < 3
            ):
                shape = None if rigid_body_vel is None else tuple(rigid_body_vel.shape)
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires simulator._rigid_body_vel "
                    f"with shape ({self.num_envs}, >{self.end_effector_index}, >=3); "
                    f"got {shape}."
                )

            if "pregrasp_target_vel" not in self.config:
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires config key 'pregrasp_target_vel'."
                )
            pregrasp_target_vel = float(self.config.pregrasp_target_vel)
            if pregrasp_target_vel <= 0.0:
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires positive pregrasp_target_vel; "
                    f"got {pregrasp_target_vel}."
                )

            pregrasp_pos_source = target_pos_source[:, 1, :]
            distance = torch.linalg.norm(pregrasp_pos_source, dim=-1)
            pos_reward = self._tracking_reward_util(
                distance,
                std=0.2,
                target=0.0,
                scale=1.0,
                offset=0.0,
            )

            direction = F.normalize(target_pos_w[:, 1, :] - source_pos_w, dim=-1)
            current_vel = rigid_body_vel[:, self.end_effector_index, :3]
            target_vel = pregrasp_target_vel * direction
            vel_reward = self._tracking_reward_util(
                torch.linalg.norm(current_vel - target_vel, dim=-1),
                std=0.15,
                target=0.0,
                scale=1.0,
                offset=0.0,
            )
            return (pos_reward + vel_reward).clamp(max=1.0)
        pre_grasp_target = self._compute_pre_grasp_target()

        left_hand_pos = self.simulator._rigid_body_pos[:, self.left_palm_idx, :]
        right_hand_pos = self.simulator._rigid_body_pos[:, self.right_palm_idx, :]

        left_hand_pos_to_pre_grasp_target = pre_grasp_target - left_hand_pos
        right_hand_pos_to_pre_grasp_target = pre_grasp_target - right_hand_pos

        left_hand_pos_to_pre_grasp_target_norm = torch.norm(
            left_hand_pos_to_pre_grasp_target, dim=-1
        )
        right_hand_pos_to_pre_grasp_target_norm = torch.norm(
            right_hand_pos_to_pre_grasp_target, dim=-1
        )

        pos_reward = self._tracking_reward_util(
            torch.where(
                self.door_open_lr < 0,
                left_hand_pos_to_pre_grasp_target_norm,
                right_hand_pos_to_pre_grasp_target_norm,
            ),
            std=0.2,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

        left_current_direction = F.normalize(pre_grasp_target - left_hand_pos, dim=-1)
        right_current_direction = F.normalize(pre_grasp_target - right_hand_pos, dim=-1)

        left_palm_vel = self.simulator._rigid_body_vel[:, self.left_palm_idx, :]
        right_palm_vel = self.simulator._rigid_body_vel[:, self.right_palm_idx, :]

        pregrasp_target_vel = self.config.get("pregrasp_target_vel", 0.5)
        left_target_vel = pregrasp_target_vel * left_current_direction
        right_target_vel = pregrasp_target_vel * right_current_direction

        vel_reward = self._tracking_reward_util(
            torch.where(
                self.door_open_lr < 0,
                torch.linalg.norm(left_palm_vel - left_target_vel, dim=-1),
                torch.linalg.norm(right_palm_vel - right_target_vel, dim=-1),
            ),
            std=0.15,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )
        return (pos_reward + vel_reward).clamp(max=1.0)

    @StagedTaskBase.effective_in_stage([STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_grasp_finger_dof_pos_l1(self):
        if self._use_a2_base:
            return torch.zeros(self.num_envs, device=self.device)
        left_diff = self.simulator.dof_pos[:, self._left_hand_dof_idx] - self._left_p1
        right_diff = self.simulator.dof_pos[:, self._right_hand_dof_idx] - self._right_p1
        left_vel = self.simulator.dof_vel[:, self._left_hand_dof_idx] * torch.sign(left_diff)
        right_vel = self.simulator.dof_vel[:, self._right_hand_dof_idx] * torch.sign(right_diff)

        pos_diff = torch.where(self.door_open_lr[:, None] < 0, left_diff, right_diff)
        pos_track = self._tracking_reward_util(
            pos_diff, std=0.3, target=0.0, scale=1.0, offset=0.0
        ).mean(dim=-1)

        vel_diff = torch.where(self.door_open_lr[:, None] < 0, left_vel, right_vel)
        vel_track = self._tracking_reward_util(
            vel_diff, std=0.2, target=0.6, scale=1.0, offset=0.0
        ).mean(dim=-1)

        return (pos_track + vel_track).clamp(max=1.0)

    def _get_a2_grasp_target_distance_reward(self, context):
        data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = getattr(data, "target_pos_source", None)
        if (
            target_pos_source is None
            or target_pos_source.ndim != 3
            or target_pos_source.shape != (self.num_envs, 2, 3)
        ):
            shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            raise RuntimeError(
                f"{context} requires target_pos_source shape "
                f"({self.num_envs}, 2, 3); got {shape}."
            )

        handle_pos_source = target_pos_source[:, 0, :]
        distance = torch.linalg.norm(handle_pos_source, dim=-1)
        std = self._get_required_positive_float_config(
            "a2_grasp_target_distance_std", context
        )
        return self._tracking_reward_util(
            distance,
            std=std,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

    @StagedTaskBase.effective_in_stage([STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_grasp_target_distance(self):
        if self._use_a2_base:
            reward = self._get_a2_grasp_target_distance_reward("A2 grasp_target_distance")
            return torch.where(
                self.stage_buf == self.STAGE_SWING,
                torch.zeros_like(reward),
                reward,
            )
        grasp_target = self._compute_grasp_target()

        left_hand_pos = self.simulator._rigid_body_pos[:, self.left_palm_idx, :]
        right_hand_pos = self.simulator._rigid_body_pos[:, self.right_palm_idx, :]

        left_hand_pos_to_grasp_target = grasp_target - left_hand_pos
        right_hand_pos_to_grasp_target = grasp_target - right_hand_pos

        left_hand_pos_to_grasp_target_norm = torch.norm(left_hand_pos_to_grasp_target, dim=-1)
        right_hand_pos_to_grasp_target_norm = torch.norm(right_hand_pos_to_grasp_target, dim=-1)

        return self._tracking_reward_util(
            torch.where(
                self.door_open_lr < 0,
                left_hand_pos_to_grasp_target_norm,
                right_hand_pos_to_grasp_target_norm,
            ),
            std=0.1,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

    @StagedTaskBase.effective_in_stage(STAGE_SWING)
    def _reward_a2_stage4_grasp_target_distance_mild(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_stage4_grasp_target_distance_mild is only defined for A2 Piper configs."
            )
        reward = self._get_a2_grasp_target_distance_reward(
            "A2 stage4 mild grasp_target_distance"
        )
        return reward * self._get_a2_stage34_hold_income_mask().float()

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_close_command(self):
        if not self._use_a2_base:
            raise RuntimeError("a2_stage2_close_command is only defined for A2 Piper configs.")

        gate = self._get_a2_stage2_close_reward_gate()
        primitive = self._get_a2_gripper_primitive_raw_column("a2_stage2_close_command")
        reward = ((-primitive - 0.2) / 0.8).clamp(0.0, 1.0)
        return reward * gate.float()

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_penalty_a2_stage2_open_command_in_close_gate(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "penalty_a2_stage2_open_command_in_close_gate is only defined for A2 Piper configs."
            )

        gate = self._get_a2_stage2_close_reward_gate()
        primitive = self._get_a2_gripper_primitive_raw_column(
            "penalty_a2_stage2_open_command_in_close_gate"
        )
        reward = ((primitive - 0.2) / 0.8).clamp(0.0, 1.0)
        return reward * gate.float()

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_close_progress(self):
        if not self._use_a2_base:
            raise RuntimeError("a2_stage2_close_progress is only defined for A2 Piper configs.")

        gripper_dof_indices = getattr(self, "_a2_gripper_dof_indices", None)
        if (
            gripper_dof_indices is None
            or not torch.is_tensor(gripper_dof_indices)
            or tuple(gripper_dof_indices.shape) != (2,)
        ):
            shape = None if gripper_dof_indices is None else tuple(gripper_dof_indices.shape)
            raise RuntimeError(
                "a2_stage2_close_progress requires _a2_gripper_dof_indices shape "
                f"(2,); got {shape}."
            )
        if gripper_dof_indices.dtype not in (torch.int32, torch.int64):
            raise RuntimeError(
                "a2_stage2_close_progress requires integer _a2_gripper_dof_indices; "
                f"got dtype={gripper_dof_indices.dtype}."
            )
        if torch.any(gripper_dof_indices < 0) or torch.unique(gripper_dof_indices).numel() != 2:
            raise RuntimeError(
                "a2_stage2_close_progress requires two distinct non-negative "
                f"gripper DOF indices; got {gripper_dof_indices.tolist()}."
            )

        open_target = getattr(self, "_a2_gripper_open_target", None)
        if (
            open_target is None
            or not torch.is_tensor(open_target)
            or tuple(open_target.shape) != (2,)
        ):
            shape = None if open_target is None else tuple(open_target.shape)
            raise RuntimeError(
                "a2_stage2_close_progress requires _a2_gripper_open_target shape "
                f"(2,); got {shape}."
            )

        close_target = getattr(self, "_a2_gripper_close_target", None)
        if (
            close_target is None
            or not torch.is_tensor(close_target)
            or tuple(close_target.shape) != (2,)
        ):
            shape = None if close_target is None else tuple(close_target.shape)
            raise RuntimeError(
                "a2_stage2_close_progress requires _a2_gripper_close_target shape "
                f"(2,); got {shape}."
            )

        span = (open_target - close_target).abs()
        if torch.any(span <= 1.0e-4):
            raise RuntimeError(
                "a2_stage2_close_progress requires non-zero gripper open/close span; "
                f"open_target={open_target.tolist()}, close_target={close_target.tolist()}."
            )

        dof_pos = getattr(self.simulator, "dof_pos", None)
        max_gripper_dof_index = int(gripper_dof_indices.max().item())
        if (
            dof_pos is None
            or not torch.is_tensor(dof_pos)
            or dof_pos.ndim != 2
            or dof_pos.shape[0] != self.num_envs
            or dof_pos.shape[1] <= max_gripper_dof_index
        ):
            shape = None if dof_pos is None else tuple(dof_pos.shape)
            raise RuntimeError(
                "a2_stage2_close_progress requires simulator.dof_pos shape "
                f"({self.num_envs}, >{max_gripper_dof_index}); got {shape}."
            )

        gate = self._get_a2_stage2_close_reward_gate()
        gripper_pos = dof_pos[:, gripper_dof_indices]
        progress = (open_target[None, :] - gripper_pos).abs() / span[None, :]
        reward = (progress.mean(dim=-1) / 0.6).clamp(0.0, 1.0)
        return reward * gate.float()

    def _get_a2_stage2_gripper_close_progress_min(self) -> torch.Tensor:
        gripper_dof_indices = getattr(self, "_a2_gripper_dof_indices", None)
        if (
            gripper_dof_indices is None
            or not torch.is_tensor(gripper_dof_indices)
            or tuple(gripper_dof_indices.shape) != (2,)
        ):
            shape = None if gripper_dof_indices is None else tuple(gripper_dof_indices.shape)
            raise RuntimeError(
                "a2_stage2_completion_gripper_close_progress_min requires "
                f"_a2_gripper_dof_indices shape (2,); got {shape}."
            )
        if gripper_dof_indices.dtype not in (torch.int32, torch.int64):
            raise RuntimeError(
                "a2_stage2_completion_gripper_close_progress_min requires integer "
                f"_a2_gripper_dof_indices; got dtype={gripper_dof_indices.dtype}."
            )
        if torch.any(gripper_dof_indices < 0) or torch.unique(gripper_dof_indices).numel() != 2:
            raise RuntimeError(
                "a2_stage2_completion_gripper_close_progress_min requires two distinct "
                f"non-negative gripper DOF indices; got {gripper_dof_indices.tolist()}."
            )

        open_target = getattr(self, "_a2_gripper_open_target", None)
        if (
            open_target is None
            or not torch.is_tensor(open_target)
            or tuple(open_target.shape) != (2,)
        ):
            shape = None if open_target is None else tuple(open_target.shape)
            raise RuntimeError(
                "a2_stage2_completion_gripper_close_progress_min requires "
                f"_a2_gripper_open_target shape (2,); got {shape}."
            )

        close_target = getattr(self, "_a2_gripper_close_target", None)
        if (
            close_target is None
            or not torch.is_tensor(close_target)
            or tuple(close_target.shape) != (2,)
        ):
            shape = None if close_target is None else tuple(close_target.shape)
            raise RuntimeError(
                "a2_stage2_completion_gripper_close_progress_min requires "
                f"_a2_gripper_close_target shape (2,); got {shape}."
            )

        span = (open_target - close_target).abs()
        if torch.any(span <= 1.0e-4):
            raise RuntimeError(
                "a2_stage2_completion_gripper_close_progress_min requires non-zero "
                "gripper open/close span; "
                f"open_target={open_target.tolist()}, close_target={close_target.tolist()}."
            )

        dof_pos = getattr(self.simulator, "dof_pos", None)
        max_gripper_dof_index = int(gripper_dof_indices.max().item())
        if (
            dof_pos is None
            or not torch.is_tensor(dof_pos)
            or dof_pos.ndim != 2
            or dof_pos.shape[0] != self.num_envs
            or dof_pos.shape[1] <= max_gripper_dof_index
        ):
            shape = None if dof_pos is None else tuple(dof_pos.shape)
            raise RuntimeError(
                "a2_stage2_completion_gripper_close_progress_min requires "
                "simulator.dof_pos shape "
                f"({self.num_envs}, >{max_gripper_dof_index}); got {shape}."
            )

        gripper_pos = dof_pos[:, gripper_dof_indices]
        progress = (open_target[None, :] - gripper_pos).abs() / span[None, :]
        return progress.clamp(0.0, 1.0).min(dim=-1).values

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_handle_center_y(self):
        """Axis-aware centering: drive handle Y (opening axis) to 0 in gripper source frame.

        Active throughout stage2 so Y centering continues during close attempts.
        """
        if not self._use_a2_base:
            raise RuntimeError("a2_stage2_handle_center_y is only defined for A2 Piper configs.")
        data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = getattr(data, "target_pos_source", None)
        if (
            target_pos_source is None
            or target_pos_source.ndim != 3
            or tuple(target_pos_source.shape) != (self.num_envs, 2, 3)
        ):
            shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            raise RuntimeError(
                "a2_stage2_handle_center_y requires target_pos_source shape "
                f"({self.num_envs}, 2, 3); got {shape}."
            )
        std = self._get_required_positive_float_config(
            "a2_stage2_handle_center_y_std", "a2_stage2_handle_center_y"
        )
        handle_y = target_pos_source[:, 0, 1].abs()
        reward = self._tracking_reward_util(
            handle_y, std=std, target=0.0, scale=1.0, offset=0.0
        )
        return reward

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_handle_approach_xz(self):
        """Axis-aware approach: drive handle X (lateral) and Z (approach depth) to 0.

        Active throughout stage2 so approach alignment continues during close attempts.
        """
        if not self._use_a2_base:
            raise RuntimeError("a2_stage2_handle_approach_xz is only defined for A2 Piper configs.")
        data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = getattr(data, "target_pos_source", None)
        if (
            target_pos_source is None
            or target_pos_source.ndim != 3
            or tuple(target_pos_source.shape) != (self.num_envs, 2, 3)
        ):
            shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            raise RuntimeError(
                "a2_stage2_handle_approach_xz requires target_pos_source shape "
                f"({self.num_envs}, 2, 3); got {shape}."
            )
        std = self._get_required_positive_float_config(
            "a2_stage2_handle_approach_xz_std", "a2_stage2_handle_approach_xz"
        )
        handle_x = target_pos_source[:, 0, 0].abs()
        handle_z = target_pos_source[:, 0, 2].abs()
        x_reward = self._tracking_reward_util(
            handle_x, std=std, target=0.0, scale=1.0, offset=0.0
        )
        z_reward = self._tracking_reward_util(
            handle_z, std=std, target=0.0, scale=1.0, offset=0.0
        )
        return ((x_reward + z_reward) / 2.0).clamp(max=1.0)

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_penalty_a2_stage2_single_finger_contact(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "penalty_a2_stage2_single_finger_contact is only defined for A2 Piper configs."
            )
        forces_w = self._get_a2_gripper_handle_contact_forces()
        masks = self._get_a2_stage2_contact_squeeze_masks(
            forces_w, "penalty_a2_stage2_single_finger_contact"
        )
        return masks["single_contact"].float()

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_both_contact(self):
        if not self._use_a2_base:
            raise RuntimeError("a2_stage2_both_contact is only defined for A2 Piper configs.")
        masks = self._get_a2_stage2_contact_squeeze_masks(
            self._get_a2_gripper_handle_contact_forces(),
            "a2_stage2_both_contact",
        )
        return masks["both_contact"].float()

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_opposite_squeeze(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_stage2_opposite_squeeze is only defined for A2 Piper configs."
            )
        masks = self._get_a2_stage2_contact_squeeze_masks(
            self._get_a2_gripper_handle_contact_forces(),
            "a2_stage2_opposite_squeeze",
        )
        return (masks["both_contact"] & masks["opposite_squeeze"]).float()

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_squeeze_force_window(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_stage2_squeeze_force_window is only defined for A2 Piper configs."
            )
        masks = self._get_a2_stage2_contact_squeeze_masks(
            self._get_a2_gripper_handle_contact_forces(),
            "a2_stage2_squeeze_force_window",
        )
        return masks["squeeze_window"].float()

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_contact_stability(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_stage2_contact_stability is only defined for A2 Piper configs."
            )
        return self._get_a2_stage2_contact_stability_mask().float()

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_penalty_a2_stage2_over_force(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "penalty_a2_stage2_over_force is only defined for A2 Piper configs."
            )
        masks = self._get_a2_stage2_contact_squeeze_masks(
            self._get_a2_gripper_handle_contact_forces(),
            "penalty_a2_stage2_over_force",
        )
        return masks["over_force"].float()

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
    def _reward_a2_stage3_stage4_keep_close_command(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_stage3_stage4_keep_close_command is only defined for A2 Piper configs."
            )
        primitive = self._get_a2_gripper_primitive_raw_column(
            "a2_stage3_stage4_keep_close_command"
        )
        reward = ((-primitive - 0.2) / 0.8).clamp(0.0, 1.0)
        return reward * self._get_a2_stage34_hold_income_mask().float()

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
    def _reward_penalty_a2_stage3_stage4_open_command(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "penalty_a2_stage3_stage4_open_command is only defined for A2 Piper configs."
            )
        primitive = self._get_a2_gripper_primitive_raw_column(
            "penalty_a2_stage3_stage4_open_command"
        )
        reward = ((primitive - 0.2) / 0.8).clamp(0.0, 1.0)
        return reward * self._get_a2_stage34_hold_income_mask().float()

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
    def _reward_a2_stage3_stage4_both_contact(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_stage3_stage4_both_contact is only defined for A2 Piper configs."
            )
        masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "a2_stage3_stage4_both_contact"
        )
        return masks["both_contact"].float() * self._get_a2_stage34_hold_income_mask().float()

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
    def _reward_a2_stage3_stage4_opposite_squeeze(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_stage3_stage4_opposite_squeeze is only defined for A2 Piper configs."
            )
        masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "a2_stage3_stage4_opposite_squeeze"
        )
        return (masks["both_contact"] & masks["opposite_squeeze"]).float() * self._get_a2_stage34_hold_income_mask().float()

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
    def _reward_a2_stage3_stage4_squeeze_force_window(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_stage3_stage4_squeeze_force_window is only defined for A2 Piper configs."
            )
        masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "a2_stage3_stage4_squeeze_force_window"
        )
        return masks["squeeze_window"].float() * self._get_a2_stage34_hold_income_mask().float()

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
    def _reward_a2_stage3_stage4_contact_stability(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_stage3_stage4_contact_stability is only defined for A2 Piper configs."
            )
        return self._get_a2_stage3_stage4_contact_stability_mask().float() * self._get_a2_stage34_hold_income_mask().float()

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
    def _reward_penalty_a2_stage3_stage4_over_force(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "penalty_a2_stage3_stage4_over_force is only defined for A2 Piper configs."
            )
        masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "penalty_a2_stage3_stage4_over_force"
        )
        return masks["over_force"].float()

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_grasp(self):
        if self._use_a2_base:
            forces_w = self._get_a2_gripper_handle_contact_forces()
            data = self._get_a2_gripper_handle_frame_transformer().data
            source_quat_w = getattr(data, "source_quat_w", None)
            if (
                source_quat_w is None
                or source_quat_w.ndim != 2
                or source_quat_w.shape != (self.num_envs, 4)
            ):
                shape = None if source_quat_w is None else tuple(source_quat_w.shape)
                raise RuntimeError(
                    "A2 grasp reward requires source_quat_w shape "
                    f"({self.num_envs}, 4); got {shape}."
                )

            source_quat = source_quat_w[:, None, :].expand(-1, 2, -1).reshape(-1, 4)
            forces_source = quat_apply(
                quat_inv(source_quat), forces_w.reshape(-1, 3)
            ).reshape(self.num_envs, 2, 3)

            axis_force = torch.abs(forces_source[:, :, 1])
            off_axis_force = torch.abs(forces_source[:, :, 0]) + torch.abs(
                forces_source[:, :, 2]
            )
            per_body = (axis_force - off_axis_force).clamp(min=-10.0, max=10.0)
            raw_reward = per_body.min(dim=-1).values

            pregrasp_mask = self.stage_buf == DoorPregrasp.STAGE_PREGRASP
            contact_mag = torch.linalg.norm(forces_w, dim=-1).sum(dim=-1).clamp(max=10.0)
            raw_reward[pregrasp_mask] = -contact_mag[pregrasp_mask]
            return raw_reward
        left_contact_forces = self.simulator.object_to_hand_contact_forces[
            :, 0, self.left_hand_indices_tgt_ct_sensor, :
        ][:, self.left_hand_indices_convert, :]
        left_contact_forces_flattened = left_contact_forces.reshape(-1, 3)
        left_hand_rot = self.simulator._rigid_body_rot[:, self.left_hand_indices, :][
            :, :, [3, 0, 1, 2]
        ]  # flip xyzw to wxyz
        left_hand_rot_flattened = left_hand_rot.reshape(-1, 4)
        left_palm_side_repeat = torch.tile(
            self.left_hand_palm_side_direction, (left_contact_forces.shape[0], 1)
        )
        # rotate contact forces first to hand body frames, and then to palm-facing frames
        left_contact_forces_hand_frame = quat_apply(
            quat_inv(left_hand_rot_flattened), left_contact_forces_flattened
        )
        left_contact_forces_palm_frame = quat_apply(
            quat_inv(left_palm_side_repeat), left_contact_forces_hand_frame
        )

        right_contact_forces = self.simulator.object_to_hand_contact_forces[
            :, 0, self.right_hand_indices_tgt_ct_sensor, :
        ][:, self.right_hand_indices_convert, :]
        right_contact_forces_flattened = right_contact_forces.reshape(-1, 3)
        right_hand_rot = self.simulator._rigid_body_rot[:, self.right_hand_indices, :][
            :, :, [3, 0, 1, 2]
        ]  # flip xyzw to wxyz
        right_hand_rot_flattened = right_hand_rot.reshape(-1, 4)
        right_palm_side_repeat = torch.tile(
            self.right_hand_palm_side_direction, (right_contact_forces.shape[0], 1)
        )
        # rotate contact forces first to hand body frames, and then to palm-facing frames
        right_contact_forces_hand_frame = quat_apply(
            quat_inv(right_hand_rot_flattened), right_contact_forces_flattened
        )
        right_contact_forces_palm_frame = quat_apply(
            quat_inv(right_palm_side_repeat), right_contact_forces_hand_frame
        )

        # reward forces acting out of the palm (x) direction. penalize forces on other directions.
        left_reward = (
            (
                -1.0 * torch.abs(left_contact_forces_palm_frame[:, 1:]).sum(dim=-1)
                + left_contact_forces_palm_frame[:, 0]
            )
            .clamp(min=-10, max=10)
            .reshape(self.num_envs, -1)
            .mean(dim=-1)
        )
        right_reward = (
            (
                -1.0 * torch.abs(right_contact_forces_palm_frame[:, 1:]).sum(dim=-1)
                + right_contact_forces_palm_frame[:, 0]
            )
            .clamp(min=-10, max=10)
            .reshape(self.num_envs, -1)
            .mean(dim=-1)
        )
        reward = left_reward + right_reward

        reward[self.stage_buf == DoorPregrasp.STAGE_PREGRASP] = -1.0 * torch.abs(
            reward[self.stage_buf == DoorPregrasp.STAGE_PREGRASP]
        )

        return reward

    @StagedTaskBase.effective_in_stage(STAGE_OPEN)
    def _reward_push_door_force(self):
        if self._use_a2_base:
            return torch.zeros(self.num_envs, device=self.device)
        left_net_force = self.simulator.object_to_hand_contact_forces[
            :, 0, self.left_hand_indices_tgt_ct_sensor, :
        ].sum(dim=-2)
        right_net_force = self.simulator.object_to_hand_contact_forces[
            :, 0, self.right_hand_indices_tgt_ct_sensor, :
        ].sum(dim=-2)
        # reward -x direction force (pushing the door)
        return (
            torch.where(self.door_open_lr < 0, left_net_force[:, 0], right_net_force[:, 0])
        ).clamp(min=0.0, max=20.0)

    @StagedTaskBase.effective_in_stage(STAGE_OPEN)
    def _reward_push_door_handle(self):
        handle_vel_reward = self.simulator.scene.articulations["door"].data.joint_vel[:, 1]
        handle_pos_reward = (
            self.simulator.scene.articulations["door"]
            .data.joint_pos[:, 1]
            .clamp(min=0.0, max=0.785398)
            / 0.785398
        )
        return (handle_vel_reward + handle_pos_reward).clamp(max=1.0, min=-1.0)

    @StagedTaskBase.effective_in_stage(STAGE_OPEN)
    def _reward_a2_stage3_unlatch_hold(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "A2 stage3 unlatch-hold reward is only defined for A2 Piper."
            )
        return self._get_a2_grasp_gated_door_reward_components()["unlatch_hold"]

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING, STAGE_THROUGH])
    def _reward_a2_stage3_stage4_hold_and_drive(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "A2 hold-and-drive reward is only defined for A2 Piper."
            )
        return self._get_a2_grasp_gated_door_reward_components()["hold_and_drive"]

    @StagedTaskBase.effective_in_stage([STAGE_SWING, STAGE_THROUGH])
    def _reward_a2_corridor_door_wide(self):
        if not self._use_a2_base:
            raise RuntimeError("a2_corridor_door_wide is only defined for A2 Piper configs.")
        door_joint_pos = self._get_door_joint_pos("A2 corridor door-wide reward", 1)
        root_states = getattr(self.simulator, "robot_root_states", None)
        env_origins = getattr(self, "env_origins", None)
        if (
            not torch.is_tensor(root_states)
            or root_states.ndim != 2
            or root_states.shape[0] != self.num_envs
            or root_states.shape[1] < 1
            or not root_states.is_floating_point()
            or root_states.device != torch.device(self.device)
            or not torch.is_tensor(env_origins)
            or tuple(env_origins.shape) != (self.num_envs, 3)
            or env_origins.dtype != root_states.dtype
            or env_origins.device != root_states.device
            or not torch.all(torch.isfinite(root_states[:, 0]))
            or not torch.all(torch.isfinite(env_origins[:, 0]))
        ):
            raise RuntimeError(
                "A2 corridor door-wide reward requires finite device-local root state and origins."
            )
        root_x = root_states[:, 0] - env_origins[:, 0]
        wide = (door_joint_pos[:, 0] / 1.5).clamp(0.0, 1.0)
        reward = wide * self._get_a2_corridor_mask().float() * (root_x < 0.8).float()
        if self._get_a2_stage5_hold_income_continuity_enabled():
            reward *= self._get_a2_door_income_hold_mask().float()
        return reward

    @StagedTaskBase.effective_in_stage([STAGE_SWING, STAGE_THROUGH])
    def _reward_a2_corridor_clean_passage(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "a2_corridor_clean_passage is only defined for A2 Piper configs."
            )
        _per_filter_force, body_total = (
            self._get_a2_door_body_panel_contact_forces()
        )
        force_threshold, _peak_force_norm, _component_cap = (
            self._get_a2_door_body_contact_event_config()
        )
        return a2_corridor_clean_passage_component(
            self._get_a2_corridor_mask(), body_total, force_threshold
        )

    @StagedTaskBase.effective_in_stage([STAGE_SWING, STAGE_THROUGH])
    def _reward_dont_push_door_handle(self):
        handle_vel_reward = -1.0 * self.simulator.scene.articulations["door"].data.joint_vel[:, 1]
        handle_pos_reward = (
            0.785398 - self.simulator.scene.articulations["door"].data.joint_pos[:, 1]
        ).clamp(min=0.0, max=0.785398) / 0.785398
        return (handle_vel_reward + handle_pos_reward).clamp(max=1.0, min=-1.0)

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
    def _reward_push_door_hinge(self):
        hinge_vel_reward = self.simulator.scene.articulations["door"].data.joint_vel[:, 0] * 10
        hinge_pos_reward = (
            self.simulator.scene.articulations["door"]
            .data.joint_pos[:, 0]
            .clamp(min=0.0, max=1.5708)
            / 1.5708
        )
        if self._use_a2_base:
            hinge_pos_reward = hinge_pos_reward * self._get_a2_stage34_hold_income_mask().float()
        return (hinge_vel_reward + hinge_pos_reward).clamp(max=1.0, min=-1.0)

    @StagedTaskBase.effective_in_stage([STAGE_SWING, STAGE_THROUGH])
    def _reward_target_root_distance(self):
        target_direction = F.normalize(
            self.target_root_pos - (self.simulator.robot_root_states[:, :3] - self.env_origins),
            dim=-1,
        )
        root_vel = self.simulator._rigid_body_vel[:, self.root_idx, :]
        root_vel_along_target_direction = torch.sum(root_vel * target_direction, dim=-1)
        root_vel_target = self.config.get("target_root_vel", 0.3)
        root_vel_reward = self._tracking_reward_util(
            root_vel_along_target_direction, std=0.2, target=root_vel_target, scale=1.0, offset=0.0
        )

        root_pos_diff = torch.norm(
            self.simulator.robot_root_states[:, :3] - self.env_origins - self.target_root_pos,
            dim=-1,
        )
        root_pos_reward = self._tracking_reward_util(
            root_pos_diff, std=0.2, target=0.0, scale=1.0, offset=0.0
        )
        reward = (root_vel_reward + root_pos_reward).clamp(max=1.0)
        if self._use_a2_base:
            reward = a2_apply_stage4_target_root_distance_scale(
                reward, self.stage_buf, self._a2_stage4_release_gate, DoorPregrasp.STAGE_SWING
            )
        else:
            reward[self.stage_buf == DoorPregrasp.STAGE_SWING] *= 0.5
        return reward

    @override
    def _reward_limits_dof_pos(self):
        # A2 global PASS: use A2 arm body DOF / Piper arm_j1..j6 safety,
        # excluding arm_j7/arm_j8 gripper DOFs.
        # Penalize dof positions too close to the limit
        if self.use_reward_limits_dof_pos_curriculum:
            m = (
                self.simulator.hard_dof_pos_limits[:, 0] + self.simulator.hard_dof_pos_limits[:, 1]
            ) / 2
            r = self.simulator.hard_dof_pos_limits[:, 1] - self.simulator.hard_dof_pos_limits[:, 0]
            lower_soft_limit = m - 0.5 * r * self.soft_dof_pos_curriculum_value
            upper_soft_limit = m + 0.5 * r * self.soft_dof_pos_curriculum_value
        else:
            lower_soft_limit = self.simulator.dof_pos_limits[:, 0]
            upper_soft_limit = self.simulator.dof_pos_limits[:, 1]
        out_of_limits = -(self.simulator.dof_pos - lower_soft_limit).clip(max=0.0)  # lower limit
        out_of_limits += (self.simulator.dof_pos - upper_soft_limit).clip(min=0.0)
        return torch.sum(out_of_limits[:, self._upper_non_gripper_dof_idx], dim=1)

    def _reward_penalty_humanly_dof_limit(self):
        # A2 reward YAML no longer enables this G1 humanoid-specific posture limit;
        # A2 replaces it with the positive LMP-style ref_dof_legs prior.
        lower_limit_violations = -1.0 * (
            self.simulator.dof_pos - self.dof_pos_humanly_lower_limit
        ).clip(max=0.0).sum(dim=-1)
        upper_limit_violations = (
            (self.simulator.dof_pos - self.dof_pos_humanly_upper_limit).clip(min=0.0).sum(dim=-1)
        )
        return lower_limit_violations + upper_limit_violations

    def _reward_penalty_door_frame_contact(self):
        # A2 global PASS: A2 scene callback creates the same door frame contact sensor
        # before the A2 branch returns, so the G1 door-contact penalty is reusable.
        door_frame_unwanted_contact_forces = self.simulator.scene.sensors[
            "door_frame_unwanted_contact_sensor"
        ].data.net_forces_w
        contact_force = door_frame_unwanted_contact_forces.norm(dim=-1).sum(dim=-1)
        if self._use_a2_base:
            return a2_apply_stage45_doorframe_contact_scale(
                contact_force,
                self.stage_buf,
                self.STAGE_SWING,
                self.STAGE_THROUGH,
                self._get_a2_stage45_door_frame_contact_scale(),
            )
        return contact_force

    def _reward_penalty_door_panel_contact(self):
        # A2 global PASS: A2 scene callback creates the same door panel contact sensor
        # before the A2 branch returns, so the G1 door-contact penalty is reusable.
        door_panel_unwanted_contact_forces = self.simulator.scene.sensors[
            "door_panel_unwanted_contact_sensor"
        ].data.net_forces_w
        contact_force = door_panel_unwanted_contact_forces.norm(dim=-1).sum(dim=-1)
        if self._use_a2_base:
            stage35 = (self.stage_buf >= self.STAGE_OPEN) & (
                self.stage_buf <= self.STAGE_THROUGH
            )
            scale = self._get_a2_stage35_door_panel_contact_scale()
            return torch.where(stage35, contact_force * scale, contact_force)
        return contact_force

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING, STAGE_THROUGH])
    def _reward_penalty_a2_door_body_contact(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "penalty_a2_door_body_contact is only defined for A2 Piper configs."
            )
        penalty_mode = self._get_a2_door_body_contact_penalty_mode()
        if penalty_mode == "event_v17":
            active, peak, _pending, emitted = (
                self._get_a2_door_body_contact_event_buffers(
                    "A2 body-contact event reward"
                )
            )
            terminal_state = getattr(self, "reset_buf", None)
            if (
                not torch.is_tensor(terminal_state)
                or tuple(terminal_state.shape) != (self.num_envs,)
                or terminal_state.dtype != torch.long
                or terminal_state.device != torch.device(self.device)
                or torch.any((terminal_state != 0) & (terminal_state != 1))
            ):
                raise RuntimeError(
                    "A2 body-contact event reward requires a device-local long "
                    "reset buffer containing only 0/1 values."
                )
            terminal_mask = terminal_state.bool()
            _force_threshold, peak_force_norm, component_cap = (
                self._get_a2_door_body_contact_event_config()
            )
            _next_active, _next_peak, terminal_component = (
                a2_finalize_door_body_contact_event(
                    active, peak, terminal_mask, peak_force_norm, component_cap
                )
            )
            if (
                isinstance(self.dt, bool)
                or not isinstance(self.dt, (int, float))
                or not math.isfinite(float(self.dt))
                or float(self.dt) <= 0.0
            ):
                raise RuntimeError(
                    f"A2 body-contact event reward requires positive finite dt; got {self.dt!r}."
                )
            return (emitted + terminal_component) / float(self.dt)
        _per_filter_force, body_total = self._get_a2_door_body_panel_contact_forces()
        return a2_door_body_contact_penalty_component(
            body_total, penalty_mode
        )

    def _reward_penalty_a2_posture_command_l1(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "penalty_a2_posture_command_l1 is only defined for A2 Piper configs."
            )
        raw_base_command = getattr(self, "_a2_base_command_raw", None)
        if (
            not torch.is_tensor(raw_base_command)
            or tuple(raw_base_command.shape) != (self.num_envs, 5)
            or not raw_base_command.is_floating_point()
            or raw_base_command.device != torch.device(self.device)
            or not torch.all(torch.isfinite(raw_base_command))
        ):
            raise RuntimeError(
                "A2 posture command penalty requires finite raw base commands shape "
                f"({self.num_envs}, 5) on {self.device}."
            )
        return torch.abs(raw_base_command[:, 3:5].clamp(-1.0, 1.0)).sum(dim=-1)

    def _reward_penalty_upper_body_dof_vel(self):
        return torch.sum(self.simulator.dof_vel[:, self._upper_non_finger_dof_idx] ** 2, dim=-1)

    @StagedTaskBase.effective_in_stage(
        [STAGE_WALK_TO_DOOR, STAGE_PREGRASP, STAGE_GRASP]
    )
    def _reward_penalty_face_door(self):
        # A2 stage0 pass: keep the G1 Doorman full root-to-door orientation penalty
        # for the first reward smoke. Future option: switch to yaw-only heading
        # error or add a desired heading offset if A2 needs a non-square stance.
        # Stage5 (THROUGH) disabled: A2 穿门后自然转头看前方，不应继续惩罚 root-to-door
        # orientation deviation。G1 原版 stages [0,1,2,5] 含 stage5，A2 改为 [0,1,2]。
        return wrap_to_pi(
            axis_angle_from_quat(xyzw_to_wxyz(self.relative_door_rot_buf)).norm(dim=-1)
        )

    @StagedTaskBase.effective_in_stage(
        [STAGE_WALK_TO_DOOR, STAGE_PREGRASP, STAGE_SWING, STAGE_THROUGH]
    )
    def _reward_penalty_base_roll_pitch_l2(self):
        rpy = getattr(self, "rpy", None)
        if (
            rpy is None
            or not torch.is_tensor(rpy)
            or rpy.ndim != 2
            or rpy.shape[0] != self.num_envs
            or rpy.shape[1] < 2
        ):
            shape = None if rpy is None else tuple(rpy.shape)
            raise RuntimeError(
                "penalty_base_roll_pitch_l2 requires self.rpy shape "
                f"({self.num_envs}, >=2); got {shape}."
            )
        return torch.sum(torch.square(rpy[:, 0:2]), dim=-1)

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP])
    def _reward_penalty_a2_stage1_stage2_base_forward_creep(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "penalty_a2_stage1_stage2_base_forward_creep is only defined for A2 Piper configs."
            )

        deadband = self._get_required_positive_float_config(
            "a2_stage1_stage2_base_forward_creep_deadband",
            "penalty_a2_stage1_stage2_base_forward_creep",
        )
        scale = self._get_required_positive_float_config(
            "a2_stage1_stage2_base_forward_creep_scale",
            "penalty_a2_stage1_stage2_base_forward_creep",
        )
        grasp_target = self._compute_grasp_target()
        x_min, _x_max, _y_tol = self._get_a2_stage0_staging_band()
        stage0_near_boundary_x = grasp_target[:, 0] - x_min
        root_x = self.simulator.robot_root_states[:, 0]
        reward = (
            (root_x - stage0_near_boundary_x - deadband) / scale
        ).clamp(0.0, 1.0)
        return reward

    def _reward_penalty_upright(self):
        upright_vec = torch.repeat_interleave(
            torch.tensor([[0.0, 0.0, 1.0]], device=self.device), self.num_envs, dim=0
        )
        torso_quat_wxyz = xyzw_to_wxyz(self.simulator._rigid_body_rot[:, self.torso_index])
        rotated_vec = quat_apply(torso_quat_wxyz, upright_vec)
        return torch.sum(torch.square(rotated_vec - upright_vec), dim=-1)

    def _reward_orientation_control(self):
        # A2 global PASS: LMP-style body pitch/roll command tracking, reading the
        # physical base command buffer without advancing A2 observation history or gait phase.
        physical_base_command = self.get_physical_base_command()
        pitch_cmd = physical_base_command[:, 3]
        roll_cmd = physical_base_command[:, 4]
        desired_x = -torch.sin(pitch_cmd) * torch.cos(roll_cmd)
        desired_y = torch.sin(roll_cmd)
        desired_xy = torch.stack((desired_x, desired_y), dim=-1)
        actual_xy = self.projected_gravity[:, :2]
        return torch.sum(torch.square(actual_xy - desired_xy), dim=-1)

    @override
    def _reward_penalty_dof_acc(self):
        # A2 global PASS: use A2 arm body DOF / Piper arm_j1..j6 safety,
        # excluding arm_j7/arm_j8 gripper DOFs.
        return torch.sum(
            torch.square(self.simulator.dof_acc[:, self._upper_non_gripper_dof_idx]), dim=-1
        )

    @override
    def _reward_penalty_dof_vel(self):
        # A2 global PASS: use A2 arm body DOF / Piper arm_j1..j6 safety,
        # excluding arm_j7/arm_j8 gripper DOFs.
        return torch.sum(
            torch.square(self.simulator.dof_vel[:, self._upper_non_gripper_dof_idx]), dim=-1
        )

    @override
    def _reward_penalty_undesired_contact(self):
        # A2 global PASS: uses A2-specific penalize_contacts_on body set with
        # exact leg/base + non-gripper arm links, excluding gripper links.
        if self._use_a2_base:
            expected_names = self.A2_PENALIZED_CONTACT_BODY_NAMES
            actual_names = tuple(self.config.robot.penalize_contacts_on)
            if actual_names != expected_names:
                raise RuntimeError(
                    "A2 undesired-contact dedup requires penalize_contacts_on order "
                    f"{expected_names}; got {actual_names}."
                )
            global_mask = (
                self.simulator.contact_forces[:, self.penalised_contact_indices, :]
                .norm(dim=-1)
                > 1.0
            )
            body_force_per_filter, _body_total = self._get_a2_door_body_panel_contact_forces()
            arm_force_per_filter, _arm_total = self._get_a2_door_arm_panel_contact_forces()
            panel_mask = torch.cat(
                (body_force_per_filter > 1.0, arm_force_per_filter[:, :7] > 1.0),
                dim=1,
            )
            if tuple(global_mask.shape) != tuple(panel_mask.shape):
                raise RuntimeError(
                    "A2 undesired-contact dedup requires global and panel masks "
                    f"to align; got {tuple(global_mask.shape)} and {tuple(panel_mask.shape)}."
                )
            # Binary exclusion is intentional: if one body touches the panel and
            # another object in the same step, this also excludes that object's
            # contact.  Vector subtraction is not used because its source/sign
            # alignment is not established for this sensor pair.
            undesired_contact = (global_mask & ~panel_mask).sum(dim=1, dtype=torch.float)
        else:
            undesired_contact = torch.sum(
                torch.norm(self.simulator.contact_forces[:, self.penalised_contact_indices, :], dim=-1)
                > 1,
                dim=1,
                dtype=torch.float,
            )
        return undesired_contact

    def _reward_penalty_dof_overspeed(self):
        # A2 global PASS: use A2 arm body DOF / Piper arm_j1..j6 safety,
        # excluding arm_j7/arm_j8 gripper DOFs.
        return (
            torch.maximum(
                torch.abs(self.simulator.dof_vel[:, self._upper_non_gripper_dof_idx]) - 3.0,
                torch.zeros_like(self.simulator.dof_vel[:, self._upper_non_gripper_dof_idx]),
            )
            ** 2
        ).sum(dim=-1)

    def _get_obs_relative_to_door(self):
        relative_door_rot_6d = quat_to_tan_norm(self.relative_door_rot_buf, w_last=True)
        return torch.cat([self.relative_door_pos_buf, relative_door_rot_6d], dim=-1)

    def _get_obs_hand_handle_transform(self):
        if self._use_a2_base:
            raise RuntimeError(
                "A2 obs key 'hand_handle_transform' is legacy G1 compatibility. "
                "Use 'gripper_handle_transform' in A2 configs."
            )
        left_hand_pos = self.simulator.left_hand_transform_pos[:, 0, :]
        left_hand_rot_wxyz = self.simulator.left_hand_transform_rot[:, 0, :]
        left_hand_rot_6d = quat_to_tan_norm(wxyz_to_xyzw(left_hand_rot_wxyz), w_last=True)
        right_hand_pos = self.simulator.right_hand_transform_pos[:, 0, :]
        right_hand_rot_wxyz = self.simulator.right_hand_transform_rot[:, 0, :]
        right_hand_rot_6d = quat_to_tan_norm(wxyz_to_xyzw(right_hand_rot_wxyz), w_last=True)
        return torch.cat(
            [left_hand_pos, left_hand_rot_6d, right_hand_pos, right_hand_rot_6d], dim=-1
        )

    def _get_a2_gripper_handle_frame_transformer(self):
        sensor_name = self.A2_GRIPPER_HANDLE_FRAME_TRANSFORMER
        try:
            transformer = self.simulator.scene.sensors[sensor_name]
        except (AttributeError, KeyError) as exc:
            raise RuntimeError(
                f"A2 requires scene sensor '{sensor_name}' for gripper_handle_transform "
                "and grasp target helpers."
            ) from exc

        data = transformer.data
        target_pos_w = getattr(data, "target_pos_w", None)
        if target_pos_w is None or target_pos_w.ndim != 3 or target_pos_w.shape[1] != 2:
            shape = None if target_pos_w is None else tuple(target_pos_w.shape)
            raise RuntimeError(
                f"A2 sensor '{sensor_name}' must expose exactly 2 target frames; "
                f"target_pos_w shape is {shape}."
            )

        target_names = getattr(data, "target_frame_names", None)
        expected_names = ["handle", "pregrasp"]
        if target_names is not None and list(target_names) != expected_names:
            raise RuntimeError(
                f"A2 sensor '{sensor_name}' target order must be {expected_names}; "
                f"got {list(target_names)}."
            )
        return transformer

    def _get_a2_gripper_handle_contact_forces(self):
        sensor_name = self.A2_GRIPPER_HANDLE_CONTACT_SENSOR
        try:
            sensor = self.simulator.scene.sensors[sensor_name]
        except (AttributeError, KeyError) as exc:
            raise RuntimeError(
                f"A2 grasp reward requires scene sensor '{sensor_name}' for "
                "handle-specific gripper contact forces."
            ) from exc

        force_matrix_w = getattr(sensor.data, "force_matrix_w", None)
        expected_shape = (self.num_envs, 1, 2, 3)
        if (
            force_matrix_w is None
            or force_matrix_w.ndim != 4
            or tuple(force_matrix_w.shape) != expected_shape
        ):
            shape = None if force_matrix_w is None else tuple(force_matrix_w.shape)
            raise RuntimeError(
                f"A2 sensor '{sensor_name}' must expose force_matrix_w shape "
                f"{expected_shape}; got {shape}."
            )
        return force_matrix_w[:, 0, :, :]

    def _get_a2_door_panel_contact_force_components(
        self, sensor_key: str, filter_names: tuple[str, ...], context: str
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if not isinstance(sensor_key, str) or not sensor_key:
            raise RuntimeError(f"{context} requires a non-empty sensor key.")
        try:
            sensor = self.simulator.scene.sensors[sensor_key]
        except (AttributeError, KeyError) as exc:
            raise RuntimeError(f"{context} requires scene sensor {sensor_key!r}.") from exc

        cfg = getattr(sensor, "cfg", None)
        actual_filter_paths = getattr(cfg, "filter_prim_paths_expr", None)
        expected_filter_paths = tuple(
            f"/World/envs/env_.*/Robot/{body_name}" for body_name in filter_names
        )
        if actual_filter_paths is None or tuple(actual_filter_paths) != expected_filter_paths:
            raise RuntimeError(
                f"{context} sensor {sensor_key!r} filter order must be "
                f"{expected_filter_paths}; got {actual_filter_paths!r}."
            )

        force_matrix_w = getattr(getattr(sensor, "data", None), "force_matrix_w", None)
        expected_shape = (self.num_envs, 1, len(filter_names), 3)
        if (
            force_matrix_w is None
            or not torch.is_tensor(force_matrix_w)
            or tuple(force_matrix_w.shape) != expected_shape
            or not force_matrix_w.is_floating_point()
            or force_matrix_w.device != torch.device(self.device)
            or not torch.all(torch.isfinite(force_matrix_w))
        ):
            shape = None if not torch.is_tensor(force_matrix_w) else tuple(force_matrix_w.shape)
            dtype = None if not torch.is_tensor(force_matrix_w) else force_matrix_w.dtype
            device = None if not torch.is_tensor(force_matrix_w) else force_matrix_w.device
            raise RuntimeError(
                f"{context} sensor {sensor_key!r} requires finite floating "
                f"force_matrix_w shape {expected_shape} on {self.device}; got "
                f"shape={shape}, dtype={dtype}, device={device}."
            )
        per_filter_force = force_matrix_w[:, 0, :, :].norm(dim=-1)
        total_force = per_filter_force.sum(dim=-1)
        if not torch.all(torch.isfinite(total_force)) or torch.any(total_force < 0.0):
            raise RuntimeError(f"{context} sensor {sensor_key!r} produced invalid force norms.")
        logged_sensor_keys = getattr(
            self, "_a2_runtime_evidence_sensor_keys_logged", None
        )
        if not isinstance(logged_sensor_keys, set) or any(
            not isinstance(key, str) for key in logged_sensor_keys
        ):
            raise RuntimeError(
                "A2 runtime evidence requires _a2_runtime_evidence_sensor_keys_logged "
                "to be an initialized set of sensor keys."
            )
        if sensor_key not in logged_sensor_keys:
            logger.info(
                "A2 runtime evidence: filtered sensor key={} force_matrix_w_shape={} "
                "dtype={} device={}",
                sensor_key,
                tuple(force_matrix_w.shape),
                force_matrix_w.dtype,
                force_matrix_w.device,
            )
            logged_sensor_keys.add(sensor_key)
        return per_filter_force, total_force

    def _get_a2_door_body_panel_contact_forces(self) -> tuple[torch.Tensor, torch.Tensor]:
        return self._get_a2_door_panel_contact_force_components(
            self.A2_DOOR_BODY_PANEL_CONTACT_SENSOR,
            self.A2_DOOR_BODY_PANEL_FILTER_NAMES,
            "A2 door-body panel contact",
        )

    def _get_a2_door_arm_panel_contact_forces(self) -> tuple[torch.Tensor, torch.Tensor]:
        return self._get_a2_door_panel_contact_force_components(
            self.A2_DOOR_ARM_PANEL_CONTACT_SENSOR,
            self.A2_DOOR_ARM_PANEL_FILTER_NAMES,
            "A2 door-arm panel contact",
        )

    def _get_door_joint_pos(self, context, min_joints):
        joint_pos = self.simulator.scene.articulations["door"].data.joint_pos
        if (
            joint_pos is None
            or not torch.is_tensor(joint_pos)
            or joint_pos.ndim != 2
            or joint_pos.shape[0] != self.num_envs
            or joint_pos.shape[1] < min_joints
        ):
            shape = None if joint_pos is None else tuple(joint_pos.shape)
            raise RuntimeError(
                f"{context} requires door joint_pos shape "
                f"({self.num_envs}, >={min_joints}); got {shape}."
            )
        return joint_pos

    def _get_door_joint_vel(self, context, min_joints):
        joint_vel = self.simulator.scene.articulations["door"].data.joint_vel
        if (
            joint_vel is None
            or not torch.is_tensor(joint_vel)
            or joint_vel.ndim != 2
            or joint_vel.shape[0] != self.num_envs
            or joint_vel.shape[1] < min_joints
            or not torch.all(torch.isfinite(joint_vel))
        ):
            shape = None if joint_vel is None else tuple(joint_vel.shape)
            raise RuntimeError(
                f"{context} requires finite door joint_vel shape "
                f"({self.num_envs}, >={min_joints}); got {shape}."
            )
        return joint_vel

    def _get_a2_hold_streak_ok_mask(self) -> torch.Tensor:
        streak = self._get_a2_grasp_control_streak_buffer(
            "_a2_stage3_stage4_both_contact_streak",
            "A2 grasp-gated door semantics",
        )
        return streak >= self._get_a2_grasp_streak_control_steps()

    def _get_a2_stage34_hold_income_mask(self) -> torch.Tensor:
        if not self._use_a2_base:
            raise RuntimeError("A2 stage3/4 hold-income mask is only defined for A2 Piper configs.")
        stage_buf = getattr(self, "stage_buf", None)
        release_gate = getattr(self, "_a2_stage4_release_gate", None)
        return a2_stage34_hold_income_mask(
            stage_buf, release_gate, self.STAGE_OPEN, self.STAGE_SWING
        )

    def _get_a2_corridor_mask(self) -> torch.Tensor:
        if not self._use_a2_base:
            raise RuntimeError("A2 corridor is only defined for A2 Piper configs.")
        corridor_latched = getattr(self, "_a2_corridor_latched", None)
        if (
            not torch.is_tensor(corridor_latched)
            or tuple(corridor_latched.shape) != (self.num_envs,)
            or corridor_latched.dtype != torch.bool
            or corridor_latched.device != torch.device(self.device)
        ):
            raise RuntimeError(
                "A2 corridor requires a device-local bool latch buffer."
            )
        if not self._get_a2_corridor_enabled():
            return torch.zeros_like(corridor_latched)
        return corridor_latched

    def _get_a2_grasp_gated_door_reward_components(self):
        door_joint_pos = self._get_door_joint_pos(
            "A2 grasp-gated door rewards", 2
        )
        door_joint_vel = self._get_door_joint_vel(
            "A2 grasp-gated door rewards", 2
        )
        streak = self._get_a2_grasp_control_streak_buffer(
            "_a2_stage3_stage4_both_contact_streak",
            "A2 grasp-gated door rewards",
        )
        components = a2_grasp_gated_door_reward_components(
            streak=streak,
            required_streak_steps=self._get_a2_grasp_streak_control_steps(),
            handle_pos=door_joint_pos[:, 1],
            hinge_pos=door_joint_pos[:, 0],
            hinge_vel=door_joint_vel[:, 0],
            unlatch_handle_position_norm=(
                self._get_a2_stage3_unlatch_handle_position_norm()
            ),
            unlatch_near_closed_hinge_threshold=(
                self._get_a2_stage3_unlatch_near_closed_hinge_threshold()
            ),
            hold_and_drive_velocity_norm=(
                self._get_a2_stage3_stage4_hold_and_drive_velocity_norm()
            ),
        )
        components["hold_and_drive"] = a2_corridor_hold_and_drive_component(
            self._get_a2_door_income_hold_mask(),
            door_joint_vel[:, 0],
            self._get_a2_corridor_mask(),
            self._get_a2_stage3_stage4_hold_and_drive_velocity_norm(),
            self._get_a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor(),
            self._get_a2_corridor_enabled(),
        )
        return components

    def _get_door_frame_contact_force_per_env(self, context):
        sensor = self.simulator.scene.sensors["door_frame_unwanted_contact_sensor"]
        net_forces_w = getattr(sensor.data, "net_forces_w", None)
        if (
            net_forces_w is None
            or not torch.is_tensor(net_forces_w)
            or net_forces_w.ndim != 3
            or net_forces_w.shape[0] != self.num_envs
            or net_forces_w.shape[2] != 3
        ):
            shape = None if net_forces_w is None else tuple(net_forces_w.shape)
            raise RuntimeError(
                f"{context} requires door_frame_unwanted_contact_sensor.net_forces_w "
                f"shape ({self.num_envs}, B, 3); got {shape}."
            )
        return net_forces_w.norm(dim=-1).sum(dim=-1)

    def _get_a2_target_root_pos_for_all_envs(self, context):
        target_root_pos = getattr(self, "target_root_pos", None)
        if (
            target_root_pos is None
            or not torch.is_tensor(target_root_pos)
            or target_root_pos.ndim != 2
            or target_root_pos.shape[1] != 3
            or target_root_pos.shape[0] not in (1, self.num_envs)
        ):
            shape = None if target_root_pos is None else tuple(target_root_pos.shape)
            raise RuntimeError(
                f"{context} requires target_root_pos shape (1, 3) or "
                f"({self.num_envs}, 3); got {shape}."
            )
        if target_root_pos.shape[0] == 1:
            return target_root_pos.repeat(self.num_envs, 1)
        return target_root_pos

    def _get_a2_stage2_grasp_contact_history_length(self):
        history_length = self.config.get("stage2_grasp_contact_history_length", None)
        if (
            history_length is None
            or isinstance(history_length, bool)
            or not isinstance(history_length, int)
            or history_length <= 0
        ):
            raise RuntimeError(
                "A2 stage2 grasp completion requires env.config."
                "stage2_grasp_contact_history_length to be a positive int; "
                f"got {history_length!r}."
            )
        return history_length

    def _get_a2_gripper_handle_contact_force_history(self):
        sensor_name = self.A2_GRIPPER_HANDLE_CONTACT_SENSOR
        try:
            sensor = self.simulator.scene.sensors[sensor_name]
        except (AttributeError, KeyError) as exc:
            raise RuntimeError(
                f"A2 stage2 completion requires scene sensor '{sensor_name}' for "
                "handle-specific gripper contact force history."
            ) from exc

        history_length = self._get_a2_stage2_grasp_contact_history_length()
        force_matrix_w_history = getattr(sensor.data, "force_matrix_w_history", None)
        expected_shape = (self.num_envs, history_length, 1, 2, 3)
        if (
            force_matrix_w_history is None
            or force_matrix_w_history.ndim != 5
            or tuple(force_matrix_w_history.shape) != expected_shape
        ):
            shape = (
                None
                if force_matrix_w_history is None
                else tuple(force_matrix_w_history.shape)
            )
            raise RuntimeError(
                f"A2 sensor '{sensor_name}' must expose force_matrix_w_history shape "
                f"{expected_shape}; got {shape}."
            )
        return force_matrix_w_history[:, :, 0, :, :]

    def _get_a2_stage2_forces_source(self, forces_w, context):
        if not torch.is_tensor(forces_w):
            raise RuntimeError(f"{context} requires forces_w to be a torch.Tensor.")
        if forces_w.ndim == 3:
            expected_shape = (self.num_envs, 2, 3)
            if tuple(forces_w.shape) != expected_shape:
                raise RuntimeError(
                    f"{context} requires forces_w shape {expected_shape}; "
                    f"got {tuple(forces_w.shape)}."
                )
            expand_shape = (self.num_envs, 2, 4)
        elif forces_w.ndim == 4:
            if (
                forces_w.shape[0] != self.num_envs
                or forces_w.shape[2] != 2
                or forces_w.shape[3] != 3
            ):
                raise RuntimeError(
                    f"{context} requires forces_w shape ({self.num_envs}, H, 2, 3); "
                    f"got {tuple(forces_w.shape)}."
                )
            expand_shape = (self.num_envs, forces_w.shape[1], 2, 4)
        else:
            raise RuntimeError(
                f"{context} requires forces_w rank 3 or 4; got shape {tuple(forces_w.shape)}."
            )

        data = self._get_a2_gripper_handle_frame_transformer().data
        source_quat_w = getattr(data, "source_quat_w", None)
        if (
            source_quat_w is None
            or source_quat_w.ndim != 2
            or tuple(source_quat_w.shape) != (self.num_envs, 4)
        ):
            shape = None if source_quat_w is None else tuple(source_quat_w.shape)
            raise RuntimeError(
                f"{context} requires source_quat_w shape ({self.num_envs}, 4); "
                f"got {shape}."
            )
        source_quat = source_quat_w
        for _ in range(forces_w.ndim - 2):
            source_quat = source_quat[:, None, :]
        source_quat = source_quat.expand(expand_shape).reshape(-1, 4)
        return quat_apply(quat_inv(source_quat), forces_w.reshape(-1, 3)).reshape(
            forces_w.shape
        )

    def _get_a2_stage2_contact_squeeze_masks(self, forces_w, context):
        forces_source = self._get_a2_stage2_forces_source(forces_w, context)
        contact_force = torch.linalg.norm(forces_w, dim=-1)
        contact_threshold = self._get_a2_stage2_contact_force_threshold()
        squeeze_min = self._get_a2_stage2_squeeze_force_min()
        squeeze_max = self._get_a2_stage2_squeeze_force_max()
        over_force_threshold = self._get_a2_stage2_over_force_threshold()

        contacting = contact_force > contact_threshold
        squeeze_y = forces_source[..., :, 1]
        squeeze_abs = torch.abs(squeeze_y)
        squeeze_in_window = (squeeze_abs >= squeeze_min) & (squeeze_abs <= squeeze_max)
        both_contact = torch.all(contacting, dim=-1)
        single_contact = contacting.sum(dim=-1) == 1
        opposite_squeeze = squeeze_y[..., 0] * squeeze_y[..., 1] < 0.0
        sufficient_squeeze = torch.all(squeeze_abs > squeeze_min, dim=-1)
        squeeze_window = (
            both_contact
            & opposite_squeeze
            & torch.all(squeeze_in_window, dim=-1)
        )
        over_force = torch.any(contact_force > over_force_threshold, dim=-1)
        return {
            "contact_force": contact_force,
            "contacting": contacting,
            "single_contact": single_contact,
            "single_contact_arm_body7": contacting[..., 0] & ~contacting[..., 1],
            "single_contact_arm_body8": ~contacting[..., 0] & contacting[..., 1],
            "both_contact": both_contact,
            "squeeze_y": squeeze_y,
            "sufficient_squeeze": sufficient_squeeze,
            "opposite_squeeze": opposite_squeeze,
            "squeeze_window": squeeze_window,
            "over_force": over_force,
        }

    def _get_a2_stage2_contact_stability_mask(self):
        gate_mode = self._get_a2_grasp_gate_mode()
        if gate_mode == self.A2_GRASP_GATE_MODE_CONTROL_STREAK:
            streak = self._get_a2_grasp_control_streak_buffer(
                "_a2_stage2_squeeze_streak",
                "A2 stage2 contact stability",
            )
            return (self.stage_buf == self.STAGE_GRASP) & (
                streak >= self._get_a2_grasp_streak_control_steps()
            )

        history_length = self._get_a2_stage2_grasp_contact_history_length()
        masks = self._get_a2_stage2_contact_squeeze_masks(
            self._get_a2_gripper_handle_contact_force_history(),
            "A2 stage2 contact stability",
        )
        both_contact_history = masks["both_contact"]
        if tuple(both_contact_history.shape) != (self.num_envs, history_length):
            raise RuntimeError(
                "A2 stage2 contact stability requires both_contact history shape "
                f"({self.num_envs}, {history_length}); got "
                f"{tuple(both_contact_history.shape)}."
            )

        actual_time_in_stage_buf = getattr(self, "actual_time_in_stage_buf", None)
        if (
            actual_time_in_stage_buf is None
            or not torch.is_tensor(actual_time_in_stage_buf)
            or tuple(actual_time_in_stage_buf.shape) != (self.num_envs,)
        ):
            shape = (
                None
                if actual_time_in_stage_buf is None
                else tuple(actual_time_in_stage_buf.shape)
            )
            raise RuntimeError(
                "A2 stage2 contact stability requires actual_time_in_stage_buf shape "
                f"({self.num_envs},); got {shape}."
            )
        history_window_in_stage = actual_time_in_stage_buf >= history_length - 1
        return history_window_in_stage & torch.all(both_contact_history, dim=-1)

    def _get_a2_stage3_stage4_contact_squeeze_masks(self, context):
        return self._get_a2_stage2_contact_squeeze_masks(
            self._get_a2_gripper_handle_contact_forces(),
            context,
        )

    def _get_a2_stage3_stage4_contact_stability_mask(self):
        gate_mode = self._get_a2_grasp_gate_mode()
        if gate_mode == self.A2_GRASP_GATE_MODE_CONTROL_STREAK:
            streak = self._get_a2_grasp_control_streak_buffer(
                "_a2_stage3_stage4_both_contact_streak",
                "A2 stage3/4 contact stability",
            )
            stage3_stage4 = (self.stage_buf == self.STAGE_OPEN) | (
                self.stage_buf == self.STAGE_SWING
            )
            return stage3_stage4 & (
                streak >= self._get_a2_grasp_streak_control_steps()
            )

        history_length = self._get_a2_stage2_grasp_contact_history_length()
        masks = self._get_a2_stage2_contact_squeeze_masks(
            self._get_a2_gripper_handle_contact_force_history(),
            "A2 stage3/4 contact stability",
        )
        both_contact_history = masks["both_contact"]
        if tuple(both_contact_history.shape) != (self.num_envs, history_length):
            raise RuntimeError(
                "A2 stage3/4 contact stability requires both_contact history shape "
                f"({self.num_envs}, {history_length}); got "
                f"{tuple(both_contact_history.shape)}."
            )

        actual_time_in_stage_buf = getattr(self, "actual_time_in_stage_buf", None)
        if (
            actual_time_in_stage_buf is None
            or not torch.is_tensor(actual_time_in_stage_buf)
            or tuple(actual_time_in_stage_buf.shape) != (self.num_envs,)
        ):
            shape = (
                None
                if actual_time_in_stage_buf is None
                else tuple(actual_time_in_stage_buf.shape)
            )
            raise RuntimeError(
                "A2 stage3/4 contact stability requires actual_time_in_stage_buf shape "
                f"({self.num_envs},); got {shape}."
            )

        stage_buf = getattr(self, "stage_buf", None)
        if (
            stage_buf is None
            or not torch.is_tensor(stage_buf)
            or tuple(stage_buf.shape) != (self.num_envs,)
        ):
            shape = None if stage_buf is None else tuple(stage_buf.shape)
            raise RuntimeError(
                "A2 stage3/4 contact stability requires stage_buf shape "
                f"({self.num_envs},); got {shape}."
            )

        history_window_in_stage = actual_time_in_stage_buf >= history_length - 1
        stage3_stage4 = (stage_buf == self.STAGE_OPEN) | (stage_buf == self.STAGE_SWING)
        return stage3_stage4 & history_window_in_stage & torch.all(both_contact_history, dim=-1)

    def _get_a2_stage1_pregrasp_ready_mask(self):
        data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = getattr(data, "target_pos_source", None)
        if (
            target_pos_source is None
            or target_pos_source.ndim != 3
            or target_pos_source.shape != (self.num_envs, 2, 3)
        ):
            shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            raise RuntimeError(
                "A2 stage1 pregrasp readiness requires target_pos_source shape "
                f"({self.num_envs}, 2, 3); got {shape}."
            )

        pregrasp_distance = torch.linalg.norm(target_pos_source[:, 1, :], dim=-1)
        opening_alignment, approach_alignment = self._get_a2_gripper_handle_orientation_metrics()
        base_still = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1) <= 0.1

        gripper_pos = self.simulator.dof_pos[:, self._a2_gripper_dof_indices]
        close_target = self._a2_gripper_close_target
        open_target = self._a2_gripper_open_target
        span = (open_target - close_target).abs()
        if torch.any(span <= 1.0e-4):
            raise RuntimeError(
                "A2 stage1 pregrasp readiness requires non-zero gripper open/close span; "
                f"open_target={open_target.tolist()}, close_target={close_target.tolist()}."
            )
        lower = torch.minimum(close_target, open_target) - 0.25 * span
        upper = torch.maximum(close_target, open_target) + 0.25 * span
        gripper_ready = torch.all(
            (gripper_pos >= lower[None, :]) & (gripper_pos <= upper[None, :]),
            dim=-1,
        )

        return (
            (pregrasp_distance < 0.1)
            & (opening_alignment >= 0.8)
            & (approach_alignment >= 0.8)
            & base_still
            & gripper_ready
        )

    def _get_a2_door_open_bypass_mask(self):
        joint_pos = self._get_door_joint_pos("A2 door-open bypass diagnostics", 1)
        return joint_pos[:, 0] > self._get_a2_stage3_to4_door_hinge_threshold()

    def _get_a2_stage2_grasp_completion_masks(self):
        forces_w_history = self._get_a2_gripper_handle_contact_force_history()
        history_length = self._get_a2_stage2_grasp_contact_history_length()
        if tuple(forces_w_history.shape) != (self.num_envs, history_length, 2, 3):
            raise RuntimeError(
                "A2 stage2 completion requires contact force history shape "
                f"({self.num_envs}, {history_length}, 2, 3); "
                f"got {tuple(forces_w_history.shape)}."
            )

        masks = self._get_a2_stage2_contact_squeeze_masks(
            forces_w_history, "A2 stage2 completion"
        )
        both_contact = masks["both_contact"]
        sufficient_squeeze = masks["sufficient_squeeze"]
        opposite_squeeze = masks["opposite_squeeze"]
        gate_mode = self._get_a2_grasp_gate_mode()
        if gate_mode == self.A2_GRASP_GATE_MODE_CONTROL_STREAK:
            streak = self._get_a2_grasp_control_streak_buffer(
                "_a2_stage2_squeeze_streak",
                "A2 stage2 completion",
            )
            base_completion = (self.stage_buf == self.STAGE_GRASP) & (
                streak >= self._get_a2_grasp_streak_control_steps()
            )
        else:
            all_history_squeezed = torch.all(
                both_contact & sufficient_squeeze & opposite_squeeze, dim=-1
            )
            actual_time_in_stage_buf = getattr(self, "actual_time_in_stage_buf", None)
            if (
                actual_time_in_stage_buf is None
                or not torch.is_tensor(actual_time_in_stage_buf)
                or tuple(actual_time_in_stage_buf.shape) != (self.num_envs,)
            ):
                shape = (
                    None
                    if actual_time_in_stage_buf is None
                    else tuple(actual_time_in_stage_buf.shape)
                )
                raise RuntimeError(
                    "A2 stage2 completion requires actual_time_in_stage_buf shape "
                    f"({self.num_envs},); got {shape}."
                )
            history_window_in_stage = actual_time_in_stage_buf >= history_length - 1
            base_completion = (
                (self.stage_buf == self.STAGE_GRASP)
                & history_window_in_stage
                & all_history_squeezed
            )

        close_gate_required = self._get_a2_stage2_completion_close_gate_required()
        close_command_threshold = self._get_a2_stage2_completion_close_command_threshold()
        close_progress_threshold = (
            self._get_a2_stage2_completion_close_progress_min_threshold()
        )
        close_gate = self._get_a2_stage2_close_reward_gate()
        primitive = self._get_a2_gripper_primitive_raw_column(
            "a2_stage2 completion stable close"
        )
        stable_close = primitive < close_command_threshold
        close_progress_min = self._get_a2_stage2_gripper_close_progress_min()
        close_progress_complete = close_progress_min >= close_progress_threshold
        completion = base_completion
        if close_gate_required:
            completion = (
                completion & close_gate & stable_close & close_progress_complete
            )
        return {
            "completion": completion,
            "both_contact_current": both_contact[:, 0],
            "sufficient_squeeze_current": sufficient_squeeze[:, 0],
            "opposite_squeeze_current": opposite_squeeze[:, 0],
            "squeeze_window_current": masks["squeeze_window"][:, 0],
            "over_force_current": masks["over_force"][:, 0],
            "single_contact_current": masks["single_contact"][:, 0],
            "single_contact_arm_body7_current": masks["single_contact_arm_body7"][:, 0],
            "single_contact_arm_body8_current": masks["single_contact_arm_body8"][:, 0],
            "contact_stability": self._get_a2_stage2_contact_stability_mask(),
            "close_gate": close_gate,
            "stable_close": stable_close,
            "close_progress_min": close_progress_min,
        }

    def _update_a2_full_stage_route_diagnostics(self, stage2_completion_masks=None):
        if not self._use_a2_base:
            return
        stage_buf = getattr(self, "stage_buf", None)
        if (
            stage_buf is None
            or not torch.is_tensor(stage_buf)
            or tuple(stage_buf.shape) != (self.num_envs,)
        ):
            shape = None if stage_buf is None else tuple(stage_buf.shape)
            raise RuntimeError(
                "A2 full-stage route diagnostics require stage_buf shape "
                f"({self.num_envs},); got {shape}."
            )

        stage0_active = stage_buf == self.STAGE_WALK_TO_DOOR
        stage1_active = stage_buf == self.STAGE_PREGRASP
        stage1_pregrasp_ready = self._get_a2_stage1_pregrasp_ready_mask()
        door_open_bypass = self._get_a2_door_open_bypass_mask()
        stage1_to2_advance = stage1_active & stage1_pregrasp_ready
        stage1_to2_bypass_blocked = (
            stage1_active & door_open_bypass & ~stage1_pregrasp_ready
        )

        if stage2_completion_masks is None:
            stage2_completion_masks = self._get_a2_stage2_grasp_completion_masks()
        stage2_active = stage_buf == self.STAGE_GRASP
        stage2_grasp_complete = stage2_completion_masks["completion"]
        stage2_to3_advance = stage2_active & stage2_grasp_complete
        stage2_to3_bypass_blocked = (
            stage2_active & door_open_bypass & ~stage2_grasp_complete
        )
        stage2_negative_gripper_primitive = (
            stage2_active
            & (self._get_a2_gripper_primitive_raw_column("A2 route diagnostics") < 0.0)
        )
        close_progress_threshold = (
            self._get_a2_stage2_completion_close_progress_min_threshold()
        )
        stage2_completion_close_gate = stage2_active & stage2_completion_masks["close_gate"]
        stage2_stable_close = stage2_active & stage2_completion_masks["stable_close"]
        stage2_close_command = stage2_active & (
            self._get_a2_gripper_primitive_raw_column(
                "A2 route diagnostics close command"
            )
            < self._get_a2_stage2_completion_close_command_threshold()
        )
        stage2_close_progress = (
            stage2_active
            & (stage2_completion_masks["close_progress_min"] >= close_progress_threshold)
        )
        stage2_both_contact = (
            stage2_active & stage2_completion_masks["both_contact_current"]
        )
        stage2_sufficient_squeeze = (
            stage2_active & stage2_completion_masks["sufficient_squeeze_current"]
        )
        stage2_opposite_squeeze = (
            stage2_active & stage2_completion_masks["opposite_squeeze_current"]
        )
        stage2_single_contact = (
            stage2_active & stage2_completion_masks["single_contact_current"]
        )
        stage2_single_contact_arm_body7 = (
            stage2_active & stage2_completion_masks["single_contact_arm_body7_current"]
        )
        stage2_single_contact_arm_body8 = (
            stage2_active & stage2_completion_masks["single_contact_arm_body8_current"]
        )
        stage2_squeeze_window = (
            stage2_active & stage2_completion_masks["squeeze_window_current"]
        )
        stage2_contact_stability = (
            stage2_active & stage2_completion_masks["contact_stability"]
        )
        stage2_over_force = stage2_active & stage2_completion_masks["over_force_current"]
        stage3_active = stage_buf == self.STAGE_OPEN
        stage4_active = stage_buf == self.STAGE_SWING
        stage5_active = stage_buf == self.STAGE_THROUGH
        stage4_release_gate = stage4_active & ~self._get_a2_stage34_hold_income_mask()
        stage3_stage4_active = stage3_active | stage4_active
        pre_crossing_active = stage3_stage4_active & ~self._a2_root_x_ever_crossed
        stage3_stage4_primitive = self._get_a2_gripper_primitive_raw_column(
            "A2 stage3/4 route diagnostics"
        )
        stage3_stage4_raw_close = stage3_stage4_active & (stage3_stage4_primitive < -0.2)
        stage3_stage4_raw_open = stage3_stage4_active & (stage3_stage4_primitive > 0.2)
        stage3_stage4_contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "A2 stage3/4 route diagnostics"
        )
        stage3_stage4_both_contact = (
            stage3_stage4_active & stage3_stage4_contact_masks["both_contact"]
        )
        stage3_stage4_opposite_squeeze = (
            stage3_stage4_active
            & stage3_stage4_contact_masks["both_contact"]
            & stage3_stage4_contact_masks["opposite_squeeze"]
        )
        stage3_stage4_squeeze_window = (
            stage3_stage4_active & stage3_stage4_contact_masks["squeeze_window"]
        )
        stage3_stage4_contact_stability = self._get_a2_stage3_stage4_contact_stability_mask()
        grasp_streak_control_steps = self._get_a2_grasp_streak_control_steps()
        stage2_squeeze_streak = self._get_a2_grasp_control_streak_buffer(
            "_a2_stage2_squeeze_streak",
            "A2 route diagnostics stage2 squeeze streak",
        )
        stage3_stage4_both_contact_streak = (
            self._get_a2_grasp_control_streak_buffer(
                "_a2_stage3_stage4_both_contact_streak",
                "A2 route diagnostics stage3/4 both-contact streak",
            )
        )
        stage2_streak_ge_k = stage2_active & (
            stage2_squeeze_streak >= grasp_streak_control_steps
        )
        stage3_stage4_streak_ge_k = stage3_stage4_active & (
            stage3_stage4_both_contact_streak >= grasp_streak_control_steps
        )
        stage3_stage4_over_force = (
            pre_crossing_active & stage3_stage4_contact_masks["over_force"]
        )
        stage3_contact_stability = stage3_active & stage3_stage4_contact_stability
        stage4_contact_stability = stage4_active & stage3_stage4_contact_stability
        stage3_single_contact_arm_body8 = (
            stage3_active & stage3_stage4_contact_masks["single_contact_arm_body8"]
        )

        # M27 body/arm panel-contact telemetry is scoped to stage3-5 control
        # steps.  Each filtered force is a world-frame normal-force norm and is
        # summed per filter without cancellation.
        body_panel_force_per_filter, body_panel_force_total = (
            self._get_a2_door_body_panel_contact_forces()
        )
        arm_panel_force_per_filter, arm_panel_force_total = (
            self._get_a2_door_arm_panel_contact_forces()
        )
        stage35_active = stage3_active | stage4_active | stage5_active
        body_panel_contact = stage35_active & (body_panel_force_total > 1.0)
        body_panel_contact_positive = body_panel_contact
        body_panel_share_numerator = torch.sum(
            body_panel_force_total[stage35_active]
        )
        arm_panel_share_numerator = torch.sum(
            arm_panel_force_total[stage35_active]
        )
        panel_share_denominator = body_panel_share_numerator + arm_panel_share_numerator
        panel_share_valid = panel_share_denominator > 0.0
        self.log_dict["a2_stage35_door_body_contact_numerator"] = body_panel_contact.float().sum()
        self.log_dict["a2_stage35_door_body_contact_denominator"] = stage35_active.float().sum()
        self.log_dict["a2_stage35_door_body_contact_usage_frac"] = a2_masked_boolean_fraction(
            body_panel_contact, stage35_active
        )
        self.log_dict["a2_stage35_door_body_force_all_sample_p50"] = a2_masked_float_quantile(
            body_panel_force_total, stage35_active, 0.5
        )
        self.log_dict["a2_stage35_door_body_force_all_sample_p95"] = a2_masked_float_quantile(
            body_panel_force_total, stage35_active, 0.95
        )
        self.log_dict["a2_stage35_door_body_force_contact_positive_p50"] = a2_masked_float_quantile(
            body_panel_force_total, body_panel_contact_positive, 0.5
        )
        self.log_dict["a2_stage35_door_body_force_contact_positive_p95"] = a2_masked_float_quantile(
            body_panel_force_total, body_panel_contact_positive, 0.95
        )
        self.log_dict["a2_stage35_door_body_force_pooled_numerator"] = body_panel_share_numerator
        self.log_dict["a2_stage35_door_arm_force_pooled_numerator"] = arm_panel_share_numerator
        self.log_dict["a2_stage35_door_panel_force_pooled_denominator"] = panel_share_denominator
        self.log_dict["a2_stage35_door_panel_force_share_valid"] = panel_share_valid.float()

        door_joint_pos = self._get_door_joint_pos("A2 route diagnostics", 2)
        door_joint_vel = self._get_door_joint_vel("A2 route diagnostics", 2)
        handle_pos = door_joint_pos[:, 1]
        hinge_vel = door_joint_vel[:, 0]
        v13_reward_components = self._get_a2_grasp_gated_door_reward_components()
        hold_and_drive_event = (
            stage3_stage4_active
            & v13_reward_components["hold_streak_ok"]
            & (
                hinge_vel
                > self._get_a2_stage3_stage4_hold_and_drive_velocity_threshold()
            )
        )
        unlatch_hold_issued = stage3_active & (
            v13_reward_components["unlatch_hold"] > 0.0
        )
        coasting = (
            pre_crossing_active
            & (
                hinge_vel
                > self._get_a2_stage3_stage4_coasting_velocity_threshold()
            )
            & ~stage3_stage4_both_contact
        )
        handle_hard_limit = stage3_active & (
            handle_pos
            >= (
                self._get_a2_stage3_handle_hard_limit_position()
                - self._get_a2_stage3_handle_hard_limit_tolerance()
            )
        )

        single_contact_duration = getattr(
            self, "_a2_stage2_single_contact_duration", None
        )
        if (
            single_contact_duration is None
            or not torch.is_tensor(single_contact_duration)
            or tuple(single_contact_duration.shape) != (self.num_envs,)
        ):
            shape = (
                None
                if single_contact_duration is None
                else tuple(single_contact_duration.shape)
            )
            raise RuntimeError(
                "A2 stage2 diagnostics require _a2_stage2_single_contact_duration "
                f"shape ({self.num_envs},); got {shape}."
            )
        actual_time_in_stage_buf = getattr(self, "actual_time_in_stage_buf", None)
        if (
            actual_time_in_stage_buf is None
            or not torch.is_tensor(actual_time_in_stage_buf)
            or tuple(actual_time_in_stage_buf.shape) != (self.num_envs,)
        ):
            shape = (
                None
                if actual_time_in_stage_buf is None
                else tuple(actual_time_in_stage_buf.shape)
            )
            raise RuntimeError(
                "A2 stage2 diagnostics require actual_time_in_stage_buf shape "
                f"({self.num_envs},); got {shape}."
            )
        reset_single_contact_duration = (~stage2_active) | (actual_time_in_stage_buf <= 1)
        self._a2_stage2_single_contact_duration[:] = torch.where(
            reset_single_contact_duration,
            torch.zeros_like(single_contact_duration),
            torch.where(
                stage2_single_contact,
                single_contact_duration + 1,
                torch.zeros_like(single_contact_duration),
            ),
        )

        primitive_open = (
            self._get_a2_gripper_primitive_raw_column("A2 route diagnostics raw sign") > 0.0
        )
        prev_open = getattr(self, "_a2_stage2_prev_gripper_open_command", None)
        prev_valid = getattr(self, "_a2_stage2_prev_gripper_raw_sign_valid", None)
        last_flip = getattr(self, "_a2_stage2_last_gripper_raw_sign_flip", None)
        for field_name, field_value in (
            ("_a2_stage2_prev_gripper_open_command", prev_open),
            ("_a2_stage2_prev_gripper_raw_sign_valid", prev_valid),
            ("_a2_stage2_last_gripper_raw_sign_flip", last_flip),
        ):
            if (
                field_value is None
                or not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
                or field_value.dtype != torch.bool
            ):
                shape = None if field_value is None else tuple(field_value.shape)
                dtype = None if field_value is None else field_value.dtype
                raise RuntimeError(
                    f"A2 stage2 diagnostics require {field_name} bool tensor shape "
                    f"({self.num_envs},); got shape={shape}, dtype={dtype}."
                )
        raw_sign_flip = (
            stage2_active
            & (actual_time_in_stage_buf > 1)
            & prev_valid
            & (primitive_open != prev_open)
        )
        self._a2_stage2_last_gripper_raw_sign_flip[:] = raw_sign_flip
        self._a2_stage2_prev_gripper_open_command[:] = torch.where(
            stage2_active, primitive_open, torch.zeros_like(primitive_open)
        )
        self._a2_stage2_prev_gripper_raw_sign_valid[:] = stage2_active

        stage3_stage4_primitive_open = stage3_stage4_primitive > 0.0
        stage3_stage4_prev_open = getattr(
            self, "_a2_stage3_stage4_prev_gripper_open_command", None
        )
        stage3_stage4_prev_valid = getattr(
            self, "_a2_stage3_stage4_prev_gripper_raw_sign_valid", None
        )
        stage3_stage4_last_flip = getattr(
            self, "_a2_stage3_stage4_last_gripper_raw_sign_flip", None
        )
        for field_name, field_value in (
            (
                "_a2_stage3_stage4_prev_gripper_open_command",
                stage3_stage4_prev_open,
            ),
            (
                "_a2_stage3_stage4_prev_gripper_raw_sign_valid",
                stage3_stage4_prev_valid,
            ),
            (
                "_a2_stage3_stage4_last_gripper_raw_sign_flip",
                stage3_stage4_last_flip,
            ),
        ):
            if (
                field_value is None
                or not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
                or field_value.dtype != torch.bool
            ):
                shape = None if field_value is None else tuple(field_value.shape)
                dtype = None if field_value is None else field_value.dtype
                raise RuntimeError(
                    f"A2 stage3/4 diagnostics require {field_name} bool tensor shape "
                    f"({self.num_envs},); got shape={shape}, dtype={dtype}."
                )
        stage3_stage4_raw_sign_flip = (
            stage3_stage4_active
            & (actual_time_in_stage_buf > 1)
            & stage3_stage4_prev_valid
            & (stage3_stage4_primitive_open != stage3_stage4_prev_open)
        )
        self._a2_stage3_stage4_last_gripper_raw_sign_flip[:] = (
            stage3_stage4_raw_sign_flip
        )
        self._a2_stage3_stage4_prev_gripper_open_command[:] = torch.where(
            stage3_stage4_active,
            stage3_stage4_primitive_open,
            torch.zeros_like(stage3_stage4_primitive_open),
        )
        self._a2_stage3_stage4_prev_gripper_raw_sign_valid[:] = stage3_stage4_active

        data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = getattr(data, "target_pos_source", None)
        if (
            target_pos_source is None
            or target_pos_source.ndim != 3
            or tuple(target_pos_source.shape) != (self.num_envs, 2, 3)
        ):
            shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            raise RuntimeError(
                "A2 stage2 diagnostics require target_pos_source shape "
                f"({self.num_envs}, 2, 3); got {shape}."
            )
        target_offset = target_pos_source[:, 0, :]
        stage2_active_float = stage2_active.float()

        diagnostics = {
            "a2_stage1_active_frac": stage1_active,
            "a2_stage1_pregrasp_ready_frac": stage1_pregrasp_ready,
            "a2_stage1_door_open_bypass_frac": door_open_bypass,
            "a2_stage1_to2_advance_frac": stage1_to2_advance,
            "a2_stage1_to2_bypass_blocked_frac": stage1_to2_bypass_blocked,
            "a2_stage2_active_frac": stage2_active,
            "a2_stage2_grasp_complete_frac": stage2_grasp_complete,
            "a2_stage2_door_open_bypass_frac": door_open_bypass,
            "a2_stage2_to3_advance_frac": stage2_to3_advance,
            "a2_stage2_to3_bypass_blocked_frac": stage2_to3_bypass_blocked,
            "a2_stage2_close_gate_frac": self._get_a2_stage2_close_reward_gate(),
            "a2_stage2_completion_close_gate_frac": stage2_completion_close_gate,
            "a2_stage2_gripper_stable_close_frac": stage2_stable_close,
            "a2_stage2_gripper_close_command_frac": stage2_close_command,
            "a2_stage2_gripper_close_progress_frac": stage2_close_progress,
            "a2_stage2_negative_gripper_primitive_frac": stage2_negative_gripper_primitive,
            "a2_stage2_both_contact_frac": stage2_both_contact,
            "a2_stage2_sufficient_squeeze_frac": stage2_sufficient_squeeze,
            "a2_stage2_opposite_squeeze_frac": stage2_opposite_squeeze,
            "a2_stage2_single_contact_frac": stage2_single_contact,
            "a2_stage2_single_contact_arm_body7_frac": stage2_single_contact_arm_body7,
            "a2_stage2_single_contact_arm_body8_frac": stage2_single_contact_arm_body8,
            "a2_stage2_squeeze_window_frac": stage2_squeeze_window,
            "a2_stage2_contact_stability_frac": stage2_contact_stability,
            "a2_stage2_streak_ge_K_frac": stage2_streak_ge_k,
            "a2_stage2_over_force_frac": stage2_over_force,
            "a2_stage2_gripper_raw_sign_flip_frac": raw_sign_flip,
            "a2_stage3_active_frac": stage3_active,
            "a2_stage4_active_frac": stage4_active,
            "a2_stage4_release_gate_numerator_frac": stage4_release_gate,
            "a2_stage4_release_gate_denominator_frac": stage4_active,
            "a2_stage5_active_frac": stage5_active,
            "a2_stage3_stage4_raw_close_frac": stage3_stage4_raw_close,
            "a2_stage3_stage4_raw_open_frac": stage3_stage4_raw_open,
            "a2_stage3_stage4_raw_sign_flip_frac": stage3_stage4_raw_sign_flip,
            "a2_stage3_stage4_both_contact_frac": stage3_stage4_both_contact,
            "a2_stage3_stage4_opposite_squeeze_frac": stage3_stage4_opposite_squeeze,
            "a2_stage3_stage4_squeeze_window_frac": stage3_stage4_squeeze_window,
            "a2_stage3_stage4_contact_stability_frac": stage3_stage4_contact_stability,
            "a2_stage3_stage4_streak_ge_K_frac": stage3_stage4_streak_ge_k,
            "a2_stage3_stage4_over_force_frac": stage3_stage4_over_force,
            "a2_stage3_stage4_over_force_numerator_frac": stage3_stage4_over_force,
            "a2_stage3_stage4_over_force_denominator_frac": pre_crossing_active,
            "a2_stage3_contact_stability_numerator_frac": stage3_contact_stability,
            "a2_stage3_contact_stability_denominator_frac": stage3_active,
            "a2_stage4_contact_stability_numerator_frac": stage4_contact_stability,
            "a2_stage4_contact_stability_denominator_frac": stage4_active,
            "a2_stage3_single_contact_arm_body8_frac": (
                stage3_single_contact_arm_body8
            ),
            "a2_stage3_hold_and_drive_numerator_frac": (
                stage3_active & hold_and_drive_event
            ),
            "a2_stage3_hold_and_drive_denominator_frac": stage3_active,
            "a2_stage3_stage4_hold_and_drive_numerator_frac": hold_and_drive_event,
            "a2_stage3_stage4_hold_and_drive_denominator_frac": stage3_stage4_active,
            "a2_stage3_unlatch_hold_issued_numerator_frac": unlatch_hold_issued,
            "a2_stage3_unlatch_hold_issued_denominator_frac": stage3_active,
            "a2_stage3_stage4_coasting_numerator_frac": coasting,
            "a2_stage3_stage4_coasting_denominator_frac": pre_crossing_active,
            "a2_stage3_handle_hard_limit_numerator_frac": handle_hard_limit,
            "a2_stage3_handle_hard_limit_denominator_frac": stage3_active,
        }
        for name, mask in diagnostics.items():
            self.log_dict[name] = mask.float().mean()
        self.log_dict["a2_stage4_release_gate_frac"] = (
            a2_masked_boolean_fraction(stage4_release_gate, stage4_active)
        )
        self.log_dict["a2_stage2_single_contact_duration_mean"] = (
            self._a2_stage2_single_contact_duration.float().mean()
        )
        self.log_dict["a2_stage2_squeeze_streak_p50"] = (
            a2_masked_grasp_streak_quantile(
                stage2_squeeze_streak,
                stage2_active,
                0.5,
            )
        )
        self.log_dict["a2_stage2_squeeze_streak_p90"] = (
            a2_masked_grasp_streak_quantile(
                stage2_squeeze_streak,
                stage2_active,
                0.9,
            )
        )
        self.log_dict["a2_stage3_stage4_both_contact_streak_p50"] = (
            a2_masked_grasp_streak_quantile(
                stage3_stage4_both_contact_streak,
                stage3_stage4_active,
                0.5,
            )
        )
        self.log_dict["a2_stage3_stage4_both_contact_streak_p90"] = (
            a2_masked_grasp_streak_quantile(
                stage3_stage4_both_contact_streak,
                stage3_stage4_active,
                0.9,
            )
        )
        self.log_dict["a2_stage3_contact_stability_conditional_frac"] = (
            a2_masked_boolean_fraction(stage3_contact_stability, stage3_active)
        )
        self.log_dict["a2_stage4_contact_stability_conditional_frac"] = (
            a2_masked_boolean_fraction(stage4_contact_stability, stage4_active)
        )
        self.log_dict["a2_stage3_hold_and_drive_frac"] = (
            a2_masked_boolean_fraction(hold_and_drive_event, stage3_active)
        )
        self.log_dict["a2_stage3_stage4_hold_and_drive_frac"] = (
            a2_masked_boolean_fraction(hold_and_drive_event, stage3_stage4_active)
        )
        self.log_dict["a2_stage3_unlatch_hold_issued_frac"] = (
            a2_masked_boolean_fraction(unlatch_hold_issued, stage3_active)
        )
        self.log_dict["a2_stage3_stage4_coasting_frac"] = (
            a2_masked_boolean_fraction(coasting, pre_crossing_active)
        )
        self.log_dict["a2_stage3_handle_hard_limit_frac"] = (
            a2_masked_boolean_fraction(handle_hard_limit, stage3_active)
        )
        self.log_dict["a2_stage3_handle_joint_pos_p50"] = a2_masked_float_quantile(
            handle_pos,
            stage3_active,
            0.5,
        )
        self.log_dict["a2_stage3_handle_joint_pos_p95"] = a2_masked_float_quantile(
            handle_pos,
            stage3_active,
            0.95,
        )
        self.log_dict["a2_stage3_stage4_hinge_velocity_p95"] = (
            a2_masked_float_quantile(
                hinge_vel,
                pre_crossing_active,
                0.95,
            )
        )
        self.log_dict["_a2_stage3_stage4_hinge_velocity_samples"] = hinge_vel
        self.log_dict["_a2_stage3_stage4_hinge_velocity_sample_mask"] = (
            pre_crossing_active
        )
        self.log_dict["a2_corridor_latched_frac"] = self._get_a2_corridor_mask().float().mean()
        release_valid = self._a2_release_event_valid
        self.log_dict["a2_release_event_env_count"] = release_valid.float().sum()
        self.log_dict["a2_post_release_body_contact_env_count"] = (
            self._a2_post_release_body_contact & release_valid
        ).float().sum()
        self.log_dict["_a2_hinge_at_release_samples"] = torch.where(
            release_valid,
            self._a2_hinge_at_release,
            torch.zeros_like(self._a2_hinge_at_release),
        )
        self.log_dict["_a2_hinge_at_release_sample_mask"] = release_valid
        self.log_dict["_a2_root_x_at_release_samples"] = torch.where(
            release_valid,
            self._a2_root_x_at_release,
            torch.zeros_like(self._a2_root_x_at_release),
        )
        self.log_dict["_a2_root_x_at_release_sample_mask"] = release_valid
        self.log_dict["_a2_post_release_body_force_max_samples"] = (
            self._a2_post_release_body_force_max
        )
        self.log_dict["_a2_post_release_body_force_max_sample_mask"] = release_valid
        self.log_dict["a2_hinge_at_release_p50"] = a2_masked_float_quantile(
            self.log_dict["_a2_hinge_at_release_samples"], release_valid, 0.5
        )
        self.log_dict["a2_hinge_at_release_p95"] = a2_masked_float_quantile(
            self.log_dict["_a2_hinge_at_release_samples"], release_valid, 0.95
        )
        self.log_dict["a2_root_x_at_release_p50"] = a2_masked_float_quantile(
            self.log_dict["_a2_root_x_at_release_samples"], release_valid, 0.5
        )
        self.log_dict["a2_root_x_at_release_p95"] = a2_masked_float_quantile(
            self.log_dict["_a2_root_x_at_release_samples"], release_valid, 0.95
        )
        self.log_dict["a2_post_release_body_force_max_p95"] = (
            a2_masked_float_quantile(
                self.log_dict["_a2_post_release_body_force_max_samples"], release_valid, 0.95
            )
        )
        self.log_dict["a2_post_release_body_force_max_p50"] = (
            a2_masked_float_quantile(
                self.log_dict["_a2_post_release_body_force_max_samples"], release_valid, 0.5
            )
        )
        self.log_dict["a2_stage2_target_offset_x_abs_mean"] = (
            target_offset[:, 0].abs() * stage2_active_float
        ).mean()
        self.log_dict["a2_stage2_target_offset_y_abs_mean"] = (
            target_offset[:, 1].abs() * stage2_active_float
        ).mean()
        self.log_dict["a2_stage2_target_offset_z_abs_mean"] = (
            target_offset[:, 2].abs() * stage2_active_float
        ).mean()
        self.log_dict["a2_stage2_target_offset_norm_mean"] = (
            torch.linalg.norm(target_offset, dim=-1) * stage2_active_float
        ).mean()

        root_states = getattr(self.simulator, "robot_root_states", None)
        if (
            root_states is None
            or not torch.is_tensor(root_states)
            or root_states.ndim != 2
            or root_states.shape[0] != self.num_envs
            or root_states.shape[1] < 10
            or not root_states.is_floating_point()
            or root_states.device != torch.device(self.device)
        ):
            shape = None if root_states is None else tuple(root_states.shape)
            raise RuntimeError(
                "A2 route diagnostics require simulator.robot_root_states shape "
                f"({self.num_envs}, >=10) floating tensor on {self.device}; got {shape}."
            )
        env_origins = getattr(self, "env_origins", None)
        if (
            env_origins is None
            or not torch.is_tensor(env_origins)
            or env_origins.ndim != 2
            or tuple(env_origins.shape) != (self.num_envs, 3)
        ):
            shape = None if env_origins is None else tuple(env_origins.shape)
            raise RuntimeError(
                "A2 route diagnostics require env_origins shape "
                f"({self.num_envs}, 3); got {shape}."
            )
        rpy = getattr(self, "rpy", None)
        if (
            rpy is None
            or not torch.is_tensor(rpy)
            or rpy.ndim != 2
            or rpy.shape[0] != self.num_envs
            or rpy.shape[1] < 3
        ):
            shape = None if rpy is None else tuple(rpy.shape)
            raise RuntimeError(
                "A2 route diagnostics require self.rpy shape "
                f"({self.num_envs}, >=3); got {shape}."
            )
        root_pos_rel = root_states[:, :3] - env_origins
        target_root_pos = self._get_a2_target_root_pos_for_all_envs("A2 route diagnostics")
        target_root_distance = torch.linalg.norm(root_pos_rel - target_root_pos, dim=-1)
        door_frame_contact_force = self._get_door_frame_contact_force_per_env(
            "A2 route diagnostics"
        )

        self.log_dict["a2_door_hinge_joint_pos_mean"] = door_joint_pos[:, 0].mean()
        self.log_dict["a2_door_handle_joint_pos_mean"] = door_joint_pos[:, 1].mean()
        self.log_dict["a2_root_x_mean"] = root_pos_rel[:, 0].mean()
        self.log_dict["a2_root_y_mean"] = root_pos_rel[:, 1].mean()
        self.log_dict["a2_root_yaw_mean"] = rpy[:, 2].mean()
        self.log_dict["a2_root_roll_mean"] = rpy[:, 0].mean()
        self.log_dict["a2_root_pitch_mean"] = rpy[:, 1].mean()
        self.log_dict["a2_target_root_distance_mean"] = target_root_distance.mean()
        self.log_dict["a2_doorframe_contact_force_mean"] = door_frame_contact_force.mean()
        self.log_dict["a2_doorframe_contact_frac"] = (
            door_frame_contact_force > 1.0
        ).float().mean()

        crossing_valid = self._a2_crossing_event_valid
        crossing_while_holding = self._a2_crossing_while_holding
        hinge_at_crossing = torch.where(
            crossing_valid,
            self._a2_hinge_at_crossing,
            torch.zeros_like(self._a2_hinge_at_crossing),
        )
        staging_valid = self._a2_stage0_to1_staging_valid
        staging_standoff = torch.where(
            staging_valid,
            self._a2_stage0_to1_staging_standoff,
            torch.zeros_like(self._a2_stage0_to1_staging_standoff),
        )
        if (
            not torch.all(torch.isfinite(hinge_at_crossing))
            or not torch.all(torch.isfinite(staging_standoff))
        ):
            raise RuntimeError(
                "A2 v14 route diagnostics require finite masked event samples."
            )

        self.log_dict["a2_root_x_first_crossing_env_count"] = (
            a2_root_x_first_crossing_env_count(self._a2_root_x_ever_crossed)
        )
        self.log_dict["a2_crossing_while_holding_numerator_frac"] = (
            crossing_valid & crossing_while_holding
        ).float().mean()
        self.log_dict["a2_crossing_while_holding_denominator_frac"] = (
            crossing_valid.float().mean()
        )
        self.log_dict["a2_crossing_while_holding_frac"] = (
            a2_masked_boolean_fraction(
                crossing_while_holding,
                crossing_valid,
            )
        )
        self.log_dict["_a2_hinge_at_crossing_samples"] = hinge_at_crossing
        self.log_dict["_a2_hinge_at_crossing_sample_mask"] = crossing_valid
        self.log_dict["a2_hinge_at_crossing_p50"] = a2_masked_float_quantile(
            hinge_at_crossing,
            crossing_valid,
            0.5,
        )
        self.log_dict["a2_hinge_at_crossing_p95"] = a2_masked_float_quantile(
            hinge_at_crossing,
            crossing_valid,
            0.95,
        )
        self.log_dict["_a2_stage0_to1_staging_standoff_samples"] = (
            staging_standoff
        )
        self.log_dict["_a2_stage0_to1_staging_standoff_sample_mask"] = (
            staging_valid
        )
        self.log_dict["a2_stage0_to1_staging_standoff_p50"] = (
            a2_masked_float_quantile(
                staging_standoff,
                staging_valid,
                0.5,
            )
        )
        self.log_dict["a2_stage0_to1_staging_standoff_p95"] = (
            a2_masked_float_quantile(
                staging_standoff,
                staging_valid,
                0.95,
            )
        )
        self.log_dict["_a2_stage0_actual_root_height_samples"] = (
            root_pos_rel[:, 2]
        )
        self.log_dict["_a2_stage0_actual_root_height_sample_mask"] = (
            stage0_active
        )
        self.log_dict["a2_stage0_actual_root_height_p50"] = (
            a2_masked_float_quantile(
                root_pos_rel[:, 2],
                stage0_active,
                0.5,
            )
        )
        self.log_dict["a2_stage0_actual_root_height_p95"] = (
            a2_masked_float_quantile(
                root_pos_rel[:, 2],
                stage0_active,
                0.95,
            )
        )
        self.log_dict["_a2_stage1_actual_root_height_samples"] = (
            root_pos_rel[:, 2]
        )
        self.log_dict["_a2_stage1_actual_root_height_sample_mask"] = (
            stage1_active
        )
        self.log_dict["a2_stage1_actual_root_height_p50"] = (
            a2_masked_float_quantile(
                root_pos_rel[:, 2],
                stage1_active,
                0.5,
            )
        )
        self.log_dict["a2_stage1_actual_root_height_p95"] = (
            a2_masked_float_quantile(
                root_pos_rel[:, 2],
                stage1_active,
                0.95,
            )
        )
        self.log_dict["_a2_stage5_forward_velocity_samples"] = root_states[:, 7]
        self.log_dict["_a2_stage5_forward_velocity_sample_mask"] = stage5_active
        self.log_dict["_a2_stage45_doorframe_contact_force_samples"] = (
            door_frame_contact_force
        )
        self.log_dict["_a2_stage45_doorframe_contact_force_sample_mask"] = (
            stage4_active | stage5_active
        )
        self.log_dict["a2_stage5_forward_velocity_p50"] = a2_masked_float_quantile(
            root_states[:, 7],
            stage5_active,
            0.5,
        )
        self.log_dict["a2_stage45_doorframe_contact_force_p95"] = a2_masked_float_quantile(
            door_frame_contact_force,
            stage4_active | stage5_active,
            0.95,
        )

    def _get_a2_axes_from_quat(self, quat, context):
        expected_shape = (self.num_envs, 4)
        if (
            quat is None
            or not torch.is_tensor(quat)
            or quat.ndim != 2
            or tuple(quat.shape) != expected_shape
        ):
            shape = None if quat is None else tuple(quat.shape)
            raise RuntimeError(
                f"{context} requires quaternion shape {expected_shape}; got {shape}."
            )

        basis = quat.new_tensor(
            (
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
            )
        )
        basis = basis.unsqueeze(0).expand(self.num_envs, -1, -1)
        quat_expanded = quat[:, None, :].expand(-1, 3, -1).reshape(-1, 4)
        return quat_apply(quat_expanded, basis.reshape(-1, 3)).reshape(
            self.num_envs, 3, 3
        )

    def _get_a2_orientation_alignment_and_axes(self, target_quat_source, context):
        target_axes_source = self._get_a2_axes_from_quat(target_quat_source, context)
        source_y = target_quat_source.new_tensor((0.0, 1.0, 0.0)).expand(
            self.num_envs, -1
        )
        source_z = target_quat_source.new_tensor((0.0, 0.0, 1.0)).expand(
            self.num_envs, -1
        )

        opening_alignment = torch.abs(
            torch.sum(source_y * target_axes_source[:, 1, :], dim=-1)
        ).clamp(0.0, 1.0)
        approach_alignment = torch.sum(
            source_z * target_axes_source[:, 2, :], dim=-1
        ).clamp(-1.0, 1.0)
        return opening_alignment, approach_alignment, target_axes_source

    def _format_a2_axes_for_terminal_diagnostics(self, axes):
        return {
            "x": axes[0],
            "y": axes[1],
            "z": axes[2],
        }

    def _get_a2_reward_episode_sums_for_diagnostics(self, env_ids):
        control_dt = getattr(self, "dt", None)
        if (
            isinstance(control_dt, bool)
            or not isinstance(control_dt, (int, float))
            or not math.isfinite(float(control_dt))
            or float(control_dt) <= 0.0
        ):
            raise RuntimeError(
                "A2 diagnostics requires positive finite control dt; "
                f"got {control_dt!r}."
            )
        reward_scales = getattr(self, "reward_scales", None)
        episode_sums = getattr(self, "episode_sums", None)
        if (
            reward_scales is None
            or not hasattr(reward_scales, "keys")
            or not isinstance(episode_sums, dict)
        ):
            raise RuntimeError(
                "A2 diagnostics requires reward scales and an episode-sum dict."
            )
        reward_names = tuple(reward_scales.keys())
        if (
            not reward_names
            or any(not isinstance(name, str) or not name for name in reward_names)
            or len(set(reward_names)) != len(reward_names)
        ):
            raise RuntimeError(
                f"A2 diagnostics requires unique reward names; got {reward_names}."
            )
        if set(episode_sums) != set(reward_names):
            raise RuntimeError(
                "A2 diagnostics reward episode-sum keys must exactly match active "
                f"reward scales; sums={tuple(episode_sums)}, scales={reward_names}."
            )
        selected_episode_sums = {}
        for name in reward_names:
            values = episode_sums[name]
            if (
                not torch.is_tensor(values)
                or tuple(values.shape) != (self.num_envs,)
                or not values.is_floating_point()
                or values.device != torch.device(self.device)
                or not torch.all(torch.isfinite(values))
            ):
                raise RuntimeError(
                    "A2 diagnostics requires finite device-local episode sums "
                    f"shape ({self.num_envs},) for reward {name!r}."
                )
            selected_episode_sums[name] = values[env_ids].detach().cpu().tolist()
        return float(control_dt), selected_episode_sums

    def _get_a2_terminal_diagnostics(self, env_ids):
        env_ids = self._normalize_render_env_ids(env_ids)
        if not self._use_a2_base:
            return self._get_terminal_diagnostics(env_ids)

        expected_frame_names = ["handle", "pregrasp"]
        transformer = self._get_a2_gripper_handle_frame_transformer()
        data = transformer.data
        target_frame_names = getattr(data, "target_frame_names", None)
        if target_frame_names is None or list(target_frame_names) != expected_frame_names:
            raise RuntimeError(
                f"A2 terminal diagnostics requires target order {expected_frame_names}; "
                f"got {None if target_frame_names is None else list(target_frame_names)}."
            )

        target_pos_source = getattr(data, "target_pos_source", None)
        expected_target_pos_source_shape = (self.num_envs, 2, 3)
        if (
            target_pos_source is None
            or target_pos_source.ndim != 3
            or tuple(target_pos_source.shape) != expected_target_pos_source_shape
        ):
            shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires target_pos_source shape "
                f"{expected_target_pos_source_shape}; got {shape}."
            )

        target_quat_source = getattr(data, "target_quat_source", None)
        expected_target_quat_source_shape = (self.num_envs, 2, 4)
        if (
            target_quat_source is None
            or target_quat_source.ndim != 3
            or tuple(target_quat_source.shape) != expected_target_quat_source_shape
        ):
            shape = None if target_quat_source is None else tuple(target_quat_source.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires target_quat_source shape "
                f"{expected_target_quat_source_shape}; got {shape}."
            )

        source_quat_w = getattr(data, "source_quat_w", None)
        expected_source_quat_w_shape = (self.num_envs, 4)
        if (
            source_quat_w is None
            or source_quat_w.ndim != 2
            or tuple(source_quat_w.shape) != expected_source_quat_w_shape
        ):
            shape = None if source_quat_w is None else tuple(source_quat_w.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires source_quat_w shape "
                f"{expected_source_quat_w_shape}; got {shape}."
            )

        gripper_dof_names = ("arm_j7", "arm_j8")
        missing_gripper_dofs = [
            dof_name for dof_name in gripper_dof_names if dof_name not in self.dof_names
        ]
        if missing_gripper_dofs:
            raise RuntimeError(
                "A2 terminal diagnostics requires gripper DOFs "
                f"{gripper_dof_names}, missing {missing_gripper_dofs}."
            )
        expected_gripper_dof_indices = torch.tensor(
            [self.dof_names.index(dof_name) for dof_name in gripper_dof_names],
            device=self.device,
            dtype=torch.long,
        )
        gripper_dof_indices = getattr(self, "_a2_gripper_dof_indices", None)
        if (
            gripper_dof_indices is None
            or not torch.is_tensor(gripper_dof_indices)
            or tuple(gripper_dof_indices.shape) != (2,)
            or not torch.equal(gripper_dof_indices.to(self.device), expected_gripper_dof_indices)
        ):
            shape = None if gripper_dof_indices is None else tuple(gripper_dof_indices.shape)
            value = None if gripper_dof_indices is None else gripper_dof_indices.tolist()
            raise RuntimeError(
                "A2 terminal diagnostics requires arm_j7/arm_j8 DOF mapping "
                f"{expected_gripper_dof_indices.tolist()}; got shape={shape}, value={value}."
            )

        gripper_body_names = ("arm_body7", "arm_body8")
        missing_gripper_bodies = [
            body_name
            for body_name in gripper_body_names
            if body_name not in self.simulator.body_names
        ]
        if missing_gripper_bodies:
            raise RuntimeError(
                "A2 terminal diagnostics requires gripper contact bodies "
                f"{gripper_body_names}, missing {missing_gripper_bodies}."
            )
        expected_gripper_body_indices = [
            self.simulator.body_names.index(body_name) for body_name in gripper_body_names
        ]
        gripper_force_body_indices = getattr(self, "_a2_gripper_force_body_indices", None)
        if gripper_force_body_indices is None:
            raise RuntimeError(
                "A2 terminal diagnostics requires _a2_gripper_force_body_indices for "
                "arm_body7/arm_body8."
            )
        if list(gripper_force_body_indices) != expected_gripper_body_indices:
            raise RuntimeError(
                "A2 terminal diagnostics requires arm_body7/arm_body8 body mapping "
                f"{expected_gripper_body_indices}; got {list(gripper_force_body_indices)}."
            )

        contact_forces = getattr(self.simulator, "contact_forces", None)
        if (
            contact_forces is None
            or contact_forces.ndim != 3
            or contact_forces.shape[0] != self.num_envs
            or contact_forces.shape[2] != 3
            or contact_forces.shape[1] <= max(expected_gripper_body_indices)
        ):
            shape = None if contact_forces is None else tuple(contact_forces.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires simulator.contact_forces shape "
                f"({self.num_envs}, >= {max(expected_gripper_body_indices) + 1}, 3); "
                f"got {shape}."
            )
        contact_force_arm_body7_8_w = contact_forces[:, expected_gripper_body_indices, :]
        contact_force_arm_body7_8_norm = torch.linalg.norm(
            contact_force_arm_body7_8_w, dim=-1
        )

        handle_contact_force_w = self._get_a2_gripper_handle_contact_forces()
        if tuple(handle_contact_force_w.shape) != (self.num_envs, 2, 3):
            raise RuntimeError(
                "A2 terminal diagnostics requires handle contact force shape "
                f"({self.num_envs}, 2, 3); got {tuple(handle_contact_force_w.shape)}."
            )
        handle_contact_force_norm = torch.linalg.norm(handle_contact_force_w, dim=-1)

        door_body_panel_force_per_filter, door_body_panel_force_total = (
            self._get_a2_door_body_panel_contact_forces()
        )
        door_arm_panel_force_per_filter, door_arm_panel_force_total = (
            self._get_a2_door_arm_panel_contact_forces()
        )

        source_quat = source_quat_w[:, None, :].expand(-1, 2, -1).reshape(-1, 4)
        handle_contact_force_source = quat_apply(
            quat_inv(source_quat), handle_contact_force_w.reshape(-1, 3)
        ).reshape(self.num_envs, 2, 3)
        squeeze_y = handle_contact_force_source[:, :, 1]
        contact_masks = self._get_a2_stage2_contact_squeeze_masks(
            handle_contact_force_w, "A2 terminal diagnostics stage2 contact state"
        )
        stage2_contact_stability = self._get_a2_stage2_contact_stability_mask()
        stage3_stage4_contact_stability = (
            self._get_a2_stage3_stage4_contact_stability_mask()
        )
        contact_stability = (
            ((self.stage_buf == self.STAGE_GRASP) & stage2_contact_stability)
            | (
                (
                    (self.stage_buf == self.STAGE_OPEN)
                    | (self.stage_buf == self.STAGE_SWING)
                )
                & stage3_stage4_contact_stability
            )
        )
        gripper_raw_sign_flip = getattr(self, "_a2_stage2_last_gripper_raw_sign_flip", None)
        if (
            gripper_raw_sign_flip is None
            or not torch.is_tensor(gripper_raw_sign_flip)
            or tuple(gripper_raw_sign_flip.shape) != (self.num_envs,)
            or gripper_raw_sign_flip.dtype != torch.bool
        ):
            shape = None if gripper_raw_sign_flip is None else tuple(gripper_raw_sign_flip.shape)
            dtype = None if gripper_raw_sign_flip is None else gripper_raw_sign_flip.dtype
            raise RuntimeError(
                "A2 terminal diagnostics requires _a2_stage2_last_gripper_raw_sign_flip "
                f"bool tensor shape ({self.num_envs},); got shape={shape}, dtype={dtype}."
            )

        dof_pos = getattr(self.simulator, "dof_pos", None)
        if (
            dof_pos is None
            or dof_pos.ndim != 2
            or dof_pos.shape[0] != self.num_envs
            or dof_pos.shape[1] <= int(torch.max(expected_gripper_dof_indices).item())
        ):
            shape = None if dof_pos is None else tuple(dof_pos.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires simulator.dof_pos shape "
                f"({self.num_envs}, >= {int(torch.max(expected_gripper_dof_indices).item()) + 1}); "
                f"got {shape}."
            )
        arm_j7_j8_pos = dof_pos[:, expected_gripper_dof_indices]

        close_target = getattr(self, "_a2_gripper_close_target", None)
        if (
            close_target is None
            or not torch.is_tensor(close_target)
            or tuple(close_target.shape) != (2,)
        ):
            shape = None if close_target is None else tuple(close_target.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires _a2_gripper_close_target shape "
                f"(2,); got {shape}."
            )
        arm_j7_j8_close_error = arm_j7_j8_pos - close_target[None, :]

        gripper_primitive_raw = getattr(self, "_a2_gripper_primitive_raw", None)
        if (
            gripper_primitive_raw is None
            or not torch.is_tensor(gripper_primitive_raw)
            or tuple(gripper_primitive_raw.shape) != (self.num_envs, 1)
        ):
            shape = None if gripper_primitive_raw is None else tuple(gripper_primitive_raw.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires _a2_gripper_primitive_raw shape "
                f"({self.num_envs}, 1); got {shape}."
            )

        for field_name in (
            "stage_buf",
            "actual_time_in_stage_buf",
            "episode_length_buf",
        ):
            field_value = getattr(self, field_name, None)
            if (
                field_value is None
                or not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
            ):
                shape = None if field_value is None else tuple(field_value.shape)
                raise RuntimeError(
                    f"A2 terminal diagnostics requires {field_name} shape "
                    f"({self.num_envs},); got {shape}."
                )
        actual_time_in_stage_buf = self.actual_time_in_stage_buf
        if (
            actual_time_in_stage_buf.dtype != torch.long
            or actual_time_in_stage_buf.device != torch.device(self.device)
            or torch.any(actual_time_in_stage_buf < 0)
        ):
            raise RuntimeError(
                "A2 terminal diagnostics requires non-negative "
                "actual_time_in_stage_buf torch.long values on "
                f"{self.device}; got dtype={actual_time_in_stage_buf.dtype}, "
                f"device={actual_time_in_stage_buf.device}, "
                f"min={int(actual_time_in_stage_buf.min().item())}."
            )

        target_pos_source_handle_distance = torch.linalg.norm(
            target_pos_source[:, 0, :], dim=-1
        )
        target_pos_source_pregrasp_distance = torch.linalg.norm(
            target_pos_source[:, 1, :], dim=-1
        )
        handle_opening_alignment, handle_approach_alignment, target_axes_source_handle = (
            self._get_a2_orientation_alignment_and_axes(
                target_quat_source[:, 0, :],
                "A2 terminal diagnostics handle target orientation",
            )
        )
        (
            pregrasp_opening_alignment,
            pregrasp_approach_alignment,
            target_axes_source_pregrasp,
        ) = self._get_a2_orientation_alignment_and_axes(
            target_quat_source[:, 1, :],
            "A2 terminal diagnostics pregrasp target orientation",
        )
        gripper_source_axes_w = self._get_a2_axes_from_quat(
            source_quat_w, "A2 terminal diagnostics gripper source orientation"
        )
        terminal_reasons = self._terminal_reasons_for_env_ids(env_ids)
        v14_telemetry_fields = self._get_a2_v14_telemetry_fields(env_ids)
        control_dt, selected_reward_episode_sums = (
            self._get_a2_reward_episode_sums_for_diagnostics(env_ids)
        )

        selected_stage_buf = self.stage_buf[env_ids].detach().cpu().tolist()
        selected_time_in_stage_buf = (
            actual_time_in_stage_buf[env_ids].detach().cpu().tolist()
        )
        selected_episode_length_buf = self.episode_length_buf[env_ids].detach().cpu().tolist()
        selected_contact_force_arm_body7_8_w = (
            contact_force_arm_body7_8_w[env_ids].detach().cpu().tolist()
        )
        selected_contact_force_arm_body7_8_norm = (
            contact_force_arm_body7_8_norm[env_ids].detach().cpu().tolist()
        )
        selected_handle_contact_force_w = (
            handle_contact_force_w[env_ids].detach().cpu().tolist()
        )
        selected_handle_contact_force_norm = (
            handle_contact_force_norm[env_ids].detach().cpu().tolist()
        )
        selected_door_body_panel_force_per_filter = (
            door_body_panel_force_per_filter[env_ids].detach().cpu().tolist()
        )
        selected_door_body_panel_force_total = (
            door_body_panel_force_total[env_ids].detach().cpu().tolist()
        )
        selected_door_arm_panel_force_per_filter = (
            door_arm_panel_force_per_filter[env_ids].detach().cpu().tolist()
        )
        selected_door_arm_panel_force_total = (
            door_arm_panel_force_total[env_ids].detach().cpu().tolist()
        )
        selected_squeeze_y = squeeze_y[env_ids].detach().cpu().tolist()
        selected_single_contact = (
            contact_masks["single_contact"][env_ids].detach().cpu().tolist()
        )
        selected_single_contact_arm_body7 = (
            contact_masks["single_contact_arm_body7"][env_ids].detach().cpu().tolist()
        )
        selected_single_contact_arm_body8 = (
            contact_masks["single_contact_arm_body8"][env_ids].detach().cpu().tolist()
        )
        selected_both_contact = (
            contact_masks["both_contact"][env_ids].detach().cpu().tolist()
        )
        selected_squeeze_window = (
            contact_masks["squeeze_window"][env_ids].detach().cpu().tolist()
        )
        selected_over_force = (
            contact_masks["over_force"][env_ids].detach().cpu().tolist()
        )
        selected_contact_stability = contact_stability[env_ids].detach().cpu().tolist()
        stage2_squeeze_streak = self._get_a2_grasp_control_streak_buffer(
            "_a2_stage2_squeeze_streak",
            "A2 terminal diagnostics stage2 squeeze streak",
        )
        stage3_stage4_both_contact_streak = (
            self._get_a2_grasp_control_streak_buffer(
                "_a2_stage3_stage4_both_contact_streak",
                "A2 terminal diagnostics stage3/4 both-contact streak",
            )
        )
        selected_stage2_squeeze_streak = (
            stage2_squeeze_streak[env_ids].detach().cpu().tolist()
        )
        selected_stage3_stage4_both_contact_streak = (
            stage3_stage4_both_contact_streak[env_ids].detach().cpu().tolist()
        )
        selected_gripper_raw_sign_flip = (
            gripper_raw_sign_flip[env_ids].detach().cpu().tolist()
        )
        selected_arm_j7_j8_pos = arm_j7_j8_pos[env_ids].detach().cpu().tolist()
        selected_arm_j7_j8_close_error = (
            arm_j7_j8_close_error[env_ids].detach().cpu().tolist()
        )
        selected_gripper_primitive_raw = (
            gripper_primitive_raw[env_ids].detach().cpu().tolist()
        )
        selected_handle_distance = (
            target_pos_source_handle_distance[env_ids].detach().cpu().tolist()
        )
        selected_pregrasp_distance = (
            target_pos_source_pregrasp_distance[env_ids].detach().cpu().tolist()
        )
        selected_handle_opening_alignment = (
            handle_opening_alignment[env_ids].detach().cpu().tolist()
        )
        selected_handle_approach_alignment = (
            handle_approach_alignment[env_ids].detach().cpu().tolist()
        )
        selected_pregrasp_opening_alignment = (
            pregrasp_opening_alignment[env_ids].detach().cpu().tolist()
        )
        selected_pregrasp_approach_alignment = (
            pregrasp_approach_alignment[env_ids].detach().cpu().tolist()
        )
        selected_source_quat_w = source_quat_w[env_ids].detach().cpu().tolist()
        selected_source_axes_w = gripper_source_axes_w[env_ids].detach().cpu().tolist()
        selected_target_quat_source_handle = (
            target_quat_source[env_ids, 0, :].detach().cpu().tolist()
        )
        selected_target_quat_source_pregrasp = (
            target_quat_source[env_ids, 1, :].detach().cpu().tolist()
        )
        selected_target_axes_source_handle = (
            target_axes_source_handle[env_ids].detach().cpu().tolist()
        )
        selected_target_axes_source_pregrasp = (
            target_axes_source_pregrasp[env_ids].detach().cpu().tolist()
        )
        selected_target_pos_source_handle = (
            target_pos_source[env_ids, 0, :].detach().cpu().tolist()
        )
        selected_target_pos_source_pregrasp = (
            target_pos_source[env_ids, 1, :].detach().cpu().tolist()
        )
        door_joint_pos = self._get_door_joint_pos("A2 terminal diagnostics", 2)
        door_joint_vel = self._get_door_joint_vel("A2 terminal diagnostics", 2)
        selected_door_hinge_joint_pos = door_joint_pos[env_ids, 0].detach().cpu().tolist()
        selected_door_handle_joint_pos = door_joint_pos[env_ids, 1].detach().cpu().tolist()
        selected_door_hinge_joint_vel = door_joint_vel[env_ids, 0].detach().cpu().tolist()
        root_x_ever_crossed = getattr(self, "_a2_root_x_ever_crossed", None)
        if (
            not torch.is_tensor(root_x_ever_crossed)
            or tuple(root_x_ever_crossed.shape) != (self.num_envs,)
            or root_x_ever_crossed.dtype != torch.bool
            or root_x_ever_crossed.device != torch.device(self.device)
        ):
            shape = None if not torch.is_tensor(root_x_ever_crossed) else tuple(root_x_ever_crossed.shape)
            dtype = None if not torch.is_tensor(root_x_ever_crossed) else root_x_ever_crossed.dtype
            raise RuntimeError(
                "A2 terminal diagnostics requires _a2_root_x_ever_crossed bool "
                f"tensor shape ({self.num_envs},) on {self.device}; got shape={shape}, dtype={dtype}."
            )
        selected_root_x_ever_crossed = root_x_ever_crossed[env_ids].detach().cpu().tolist()

        root_states = getattr(self.simulator, "robot_root_states", None)
        if (
            root_states is None
            or not torch.is_tensor(root_states)
            or root_states.ndim != 2
            or root_states.shape[0] != self.num_envs
            or root_states.shape[1] < 7
        ):
            shape = None if root_states is None else tuple(root_states.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires simulator.robot_root_states shape "
                f"({self.num_envs}, >=7); got {shape}."
            )
        env_origins = getattr(self, "env_origins", None)
        if (
            env_origins is None
            or not torch.is_tensor(env_origins)
            or env_origins.ndim != 2
            or tuple(env_origins.shape) != (self.num_envs, 3)
        ):
            shape = None if env_origins is None else tuple(env_origins.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires env_origins shape "
                f"({self.num_envs}, 3); got {shape}."
            )
        rpy = getattr(self, "rpy", None)
        if (
            rpy is None
            or not torch.is_tensor(rpy)
            or rpy.ndim != 2
            or rpy.shape[0] != self.num_envs
            or rpy.shape[1] < 3
        ):
            shape = None if rpy is None else tuple(rpy.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires self.rpy shape "
                f"({self.num_envs}, >=3); got {shape}."
            )
        root_pos_rel = root_states[:, :3] - env_origins
        target_root_pos = self._get_a2_target_root_pos_for_all_envs(
            "A2 terminal diagnostics"
        )
        target_root_distance = torch.linalg.norm(root_pos_rel - target_root_pos, dim=-1)
        doorframe_contact_force = self._get_door_frame_contact_force_per_env(
            "A2 terminal diagnostics"
        )
        selected_root_pos_rel = root_pos_rel[env_ids].detach().cpu().tolist()
        selected_root_rpy = rpy[env_ids, :3].detach().cpu().tolist()
        selected_target_root_distance = target_root_distance[env_ids].detach().cpu().tolist()
        selected_doorframe_contact_force = (
            doorframe_contact_force[env_ids].detach().cpu().tolist()
        )

        stage3_stage4_gripper_raw_sign_flip = getattr(
            self, "_a2_stage3_stage4_last_gripper_raw_sign_flip", None
        )
        if (
            stage3_stage4_gripper_raw_sign_flip is None
            or not torch.is_tensor(stage3_stage4_gripper_raw_sign_flip)
            or tuple(stage3_stage4_gripper_raw_sign_flip.shape) != (self.num_envs,)
            or stage3_stage4_gripper_raw_sign_flip.dtype != torch.bool
        ):
            shape = (
                None
                if stage3_stage4_gripper_raw_sign_flip is None
                else tuple(stage3_stage4_gripper_raw_sign_flip.shape)
            )
            dtype = (
                None
                if stage3_stage4_gripper_raw_sign_flip is None
                else stage3_stage4_gripper_raw_sign_flip.dtype
            )
            raise RuntimeError(
                "A2 terminal diagnostics requires "
                "_a2_stage3_stage4_last_gripper_raw_sign_flip bool tensor shape "
                f"({self.num_envs},); got shape={shape}, dtype={dtype}."
            )
        selected_stage3_stage4_gripper_raw_sign_flip = (
            stage3_stage4_gripper_raw_sign_flip[env_ids].detach().cpu().tolist()
        )
        close_target_list = close_target.detach().cpu().tolist()
        open_target = getattr(self, "_a2_gripper_open_target", None)
        if (
            open_target is None
            or not torch.is_tensor(open_target)
            or tuple(open_target.shape) != (2,)
            or not open_target.is_floating_point()
            or open_target.device != torch.device(self.device)
            or not torch.all(torch.isfinite(open_target))
        ):
            shape = None if not torch.is_tensor(open_target) else tuple(open_target.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires finite _a2_gripper_open_target "
                f"shape (2,) on {self.device}; got {shape}."
            )
        open_target_list = open_target.detach().cpu().tolist()

        diagnostics = []
        for idx, env_id in enumerate(env_ids.tolist()):
            diagnostics.append(
                {
                    "env_id": int(env_id),
                    **v14_telemetry_fields[idx],
                    "stage_buf": int(selected_stage_buf[idx]),
                    "time_in_stage_buf": int(selected_time_in_stage_buf[idx]),
                    "episode_length_buf": int(selected_episode_length_buf[idx]),
                    "control_dt": control_dt,
                    "reward_episode_sums": {
                        name: float(values[idx])
                        for name, values in selected_reward_episode_sums.items()
                    },
                    "terminal_reasons": terminal_reasons[idx],
                    "door_hinge_joint_pos": float(selected_door_hinge_joint_pos[idx]),
                    "door_hinge_joint_vel": float(selected_door_hinge_joint_vel[idx]),
                    "door_handle_joint_pos": float(selected_door_handle_joint_pos[idx]),
                    "root_x_ever_crossed": bool(selected_root_x_ever_crossed[idx]),
                    "root_pos_rel": selected_root_pos_rel[idx],
                    "root_roll": float(selected_root_rpy[idx][0]),
                    "root_pitch": float(selected_root_rpy[idx][1]),
                    "root_yaw": float(selected_root_rpy[idx][2]),
                    "target_root_distance": float(selected_target_root_distance[idx]),
                    "doorframe_contact_force": float(selected_doorframe_contact_force[idx]),
                    "contact_force_arm_body7_8_w": selected_contact_force_arm_body7_8_w[
                        idx
                    ],
                    "contact_force_arm_body7_8_norm": selected_contact_force_arm_body7_8_norm[
                        idx
                    ],
                    "handle_contact_force_w": selected_handle_contact_force_w[idx],
                    "handle_contact_force_norm": selected_handle_contact_force_norm[idx],
                    "squeeze_y": selected_squeeze_y[idx],
                    "single_contact": bool(selected_single_contact[idx]),
                    "single_contact_arm_body7": bool(
                        selected_single_contact_arm_body7[idx]
                    ),
                    "single_contact_arm_body8": bool(
                        selected_single_contact_arm_body8[idx]
                    ),
                    "both_contact": bool(selected_both_contact[idx]),
                    "squeeze_window": bool(selected_squeeze_window[idx]),
                    "contact_stability": bool(selected_contact_stability[idx]),
                    "a2_grasp_gate_mode": self._get_a2_grasp_gate_mode(),
                    "a2_grasp_streak_control_steps": (
                        self._get_a2_grasp_streak_control_steps()
                    ),
                    "a2_stage2_squeeze_streak": int(
                        selected_stage2_squeeze_streak[idx]
                    ),
                    "a2_stage3_stage4_both_contact_streak": int(
                        selected_stage3_stage4_both_contact_streak[idx]
                    ),
                    "over_force": bool(selected_over_force[idx]),
                    "arm_j7_j8_pos": selected_arm_j7_j8_pos[idx],
                    "arm_j7_j8_close_target": close_target_list,
                    "arm_j7_j8_open_target": open_target_list,
                    "arm_j7_j8_close_error": selected_arm_j7_j8_close_error[idx],
                    "gripper_primitive_raw": selected_gripper_primitive_raw[idx],
                    "gripper_raw_sign_flip": bool(selected_gripper_raw_sign_flip[idx]),
                    "stage3_stage4_gripper_raw_sign_flip": bool(
                        selected_stage3_stage4_gripper_raw_sign_flip[idx]
                    ),
                    "target_offset_x_abs": abs(selected_target_pos_source_handle[idx][0]),
                    "target_offset_y_abs": abs(selected_target_pos_source_handle[idx][1]),
                    "target_offset_z_abs": abs(selected_target_pos_source_handle[idx][2]),
                    "target_pos_source_handle_distance": float(
                        selected_handle_distance[idx]
                    ),
                    "target_offset_norm": float(selected_handle_distance[idx]),
                    "target_pos_source_pregrasp_distance": float(
                        selected_pregrasp_distance[idx]
                    ),
                    "pregrasp_opening_alignment": float(
                        selected_pregrasp_opening_alignment[idx]
                    ),
                    "pregrasp_approach_alignment": float(
                        selected_pregrasp_approach_alignment[idx]
                    ),
                    "handle_opening_alignment": float(
                        selected_handle_opening_alignment[idx]
                    ),
                    "handle_approach_alignment": float(
                        selected_handle_approach_alignment[idx]
                    ),
                    "gripper_source_quat_w": selected_source_quat_w[idx],
                    "gripper_source_axes_w": self._format_a2_axes_for_terminal_diagnostics(
                        selected_source_axes_w[idx]
                    ),
                    "target_quat_source_handle": selected_target_quat_source_handle[
                        idx
                    ],
                    "target_quat_source_pregrasp": selected_target_quat_source_pregrasp[
                        idx
                    ],
                    "target_axes_source_handle": self._format_a2_axes_for_terminal_diagnostics(
                        selected_target_axes_source_handle[idx]
                    ),
                    "target_axes_source_pregrasp": self._format_a2_axes_for_terminal_diagnostics(
                        selected_target_axes_source_pregrasp[idx]
                    ),
                    "target_pos_source_handle": selected_target_pos_source_handle[idx],
                    "target_pos_source_pregrasp": selected_target_pos_source_pregrasp[
                        idx
                    ],
                    "door_body_panel_normal_force_per_filter": selected_door_body_panel_force_per_filter[idx],
                    "door_body_panel_normal_force_total": float(
                        selected_door_body_panel_force_total[idx]
                    ),
                    "door_arm_panel_normal_force_per_filter": selected_door_arm_panel_force_per_filter[idx],
                    "door_arm_panel_normal_force_total": float(
                        selected_door_arm_panel_force_total[idx]
                    ),
                }
            )
        return diagnostics

    def _begin_eval_reward_term_diagnostics(self, active_reward_names):
        if not self._a2_eval_diagnostic_trace_enabled:
            return
        if tuple(active_reward_names) != tuple(self.reward_names):
            raise RuntimeError(
                "A2 eval reward diagnostics active reward ordering changed within eval: "
                f"expected {tuple(self.reward_names)}, got {tuple(active_reward_names)}."
            )
        self._a2_eval_reward_raw_by_name = {}
        self._a2_eval_reward_scaled_by_name = {}

    def _capture_eval_reward_term_diagnostics(self, name, raw_reward, scaled_reward):
        if not self._a2_eval_diagnostic_trace_enabled:
            return
        if name not in self._a2_eval_diagnostic_reward_term_names:
            return
        for value_name, value in (
            ("raw_reward", raw_reward),
            ("scaled_reward", scaled_reward),
        ):
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != (self.num_envs,)
                or not torch.is_floating_point(value)
                or not torch.all(torch.isfinite(value))
            ):
                shape = None if not torch.is_tensor(value) else tuple(value.shape)
                dtype = None if not torch.is_tensor(value) else value.dtype
                raise RuntimeError(
                    "A2 eval reward diagnostics require finite floating tensors "
                    f"shape ({self.num_envs},); {name}.{value_name} got "
                    f"shape={shape}, dtype={dtype}."
                )
        if name in self._a2_eval_reward_raw_by_name:
            raise RuntimeError(
                f"A2 eval reward diagnostics captured reward term {name!r} twice in one step."
            )
        self._a2_eval_reward_raw_by_name[name] = raw_reward.detach().clone()
        self._a2_eval_reward_scaled_by_name[name] = scaled_reward.detach().clone()

    def init_a2_eval_stage2_step_trace(
        self,
        diagnostic_enabled: bool = False,
        diagnostic_reward_terms=(),
    ):
        if not self._use_a2_base:
            raise RuntimeError("A2 stage2-5 step trace can only be initialized for A2 envs.")
        if not getattr(self, "is_evaluating", False):
            raise RuntimeError("A2 stage2-5 step trace must be initialized in eval mode.")
        if not isinstance(diagnostic_enabled, bool):
            raise RuntimeError(
                "A2 eval diagnostic trace enabled flag must be bool; "
                f"got {diagnostic_enabled!r}."
            )
        if not isinstance(diagnostic_reward_terms, (list, tuple)):
            raise RuntimeError(
                "A2 eval diagnostic reward terms must be a list or tuple of names; "
                f"got {type(diagnostic_reward_terms).__name__}."
            )
        reward_terms = tuple(diagnostic_reward_terms)
        if diagnostic_enabled:
            if not reward_terms:
                raise RuntimeError(
                    "A2 eval diagnostic trace requires at least one reward term."
                )
            if any(not isinstance(name, str) or not name for name in reward_terms):
                raise RuntimeError(
                    "A2 eval diagnostic reward term names must be non-empty strings; "
                    f"got {reward_terms}."
                )
            if len(set(reward_terms)) != len(reward_terms):
                raise RuntimeError(
                    "A2 eval diagnostic reward term names must be unique; "
                    f"got {reward_terms}."
                )
            active_reward_names = tuple(self.reward_names)
            missing_reward_terms = [
                name for name in reward_terms if name not in active_reward_names
            ]
            if missing_reward_terms:
                raise RuntimeError(
                    "A2 eval diagnostic reward terms must be active non-zero reward terms; "
                    f"missing {missing_reward_terms}, active={active_reward_names}."
                )
        elif reward_terms:
            raise RuntimeError(
                "A2 eval diagnostic reward terms were provided while diagnostic trace is disabled."
            )

        self._a2_eval_diagnostic_trace_enabled = diagnostic_enabled
        self._a2_eval_diagnostic_reward_term_names = reward_terms
        self._a2_eval_policy_high_level_action_raw = None
        self._a2_eval_post_forced_override_pre_env_action = None
        self._a2_eval_post_delta_post_warp_env_action = None
        self._a2_eval_forced_gripper_close_mask = None
        self._a2_eval_first_episode_active_mask = None
        self._a2_eval_episode_indices = None
        self._a2_eval_reward_raw_by_name = None
        self._a2_eval_reward_scaled_by_name = None
        self._a2_stage2_step_trace_records = []
        self._a2_stage2_step_trace_step_index = 0

    def set_a2_eval_diagnostic_actions(
        self,
        policy_high_level_action_raw: torch.Tensor,
        post_forced_override_pre_env_action: torch.Tensor,
        forced_gripper_close_mask: torch.Tensor,
        first_episode_active_mask: torch.Tensor,
        episode_indices: torch.Tensor,
    ) -> None:
        if not self._use_a2_base or not getattr(self, "is_evaluating", False):
            raise RuntimeError("A2 eval diagnostic actions require an evaluating A2 env.")
        if not self._a2_eval_diagnostic_trace_enabled:
            raise RuntimeError(
                "A2 eval diagnostic actions require a2_diagnostic_trace_enabled=true."
            )
        layout = self.get_a2_high_level_action_layout()
        expected_action_shape = (self.num_envs, layout["dim"])
        for action_name, action in (
            ("policy_high_level_action_raw", policy_high_level_action_raw),
            (
                "post_forced_override_pre_env_action",
                post_forced_override_pre_env_action,
            ),
        ):
            if (
                not torch.is_tensor(action)
                or tuple(action.shape) != expected_action_shape
                or not torch.is_floating_point(action)
                or not torch.all(torch.isfinite(action))
            ):
                shape = None if not torch.is_tensor(action) else tuple(action.shape)
                dtype = None if not torch.is_tensor(action) else action.dtype
                raise RuntimeError(
                    f"A2 eval diagnostic {action_name} requires finite floating tensor "
                    f"shape {expected_action_shape}; got shape={shape}, dtype={dtype}."
                )
        for mask_name, mask in (
            ("forced_gripper_close_mask", forced_gripper_close_mask),
            ("first_episode_active_mask", first_episode_active_mask),
        ):
            if (
                not torch.is_tensor(mask)
                or tuple(mask.shape) != (self.num_envs,)
                or mask.dtype != torch.bool
            ):
                shape = None if not torch.is_tensor(mask) else tuple(mask.shape)
                dtype = None if not torch.is_tensor(mask) else mask.dtype
                raise RuntimeError(
                    f"A2 eval {mask_name} requires bool tensor shape "
                    f"({self.num_envs},); got shape={shape}, dtype={dtype}."
                )
        if torch.any(forced_gripper_close_mask & ~first_episode_active_mask):
            raise RuntimeError(
                "A2 eval forced gripper close mask must be a subset of the "
                "first-episode active mask."
            )
        if (
            not torch.is_tensor(episode_indices)
            or tuple(episode_indices.shape) != (self.num_envs,)
            or episode_indices.dtype != torch.long
            or torch.any(episode_indices < 0)
        ):
            shape = None if not torch.is_tensor(episode_indices) else tuple(
                episode_indices.shape
            )
            dtype = None if not torch.is_tensor(episode_indices) else episode_indices.dtype
            raise RuntimeError(
                "A2 eval episode indices require non-negative long tensor shape "
                f"({self.num_envs},); got shape={shape}, dtype={dtype}."
            )
        expected_device = torch.device(self.device)
        for tensor_name, tensor in (
            ("policy_high_level_action_raw", policy_high_level_action_raw),
            (
                "post_forced_override_pre_env_action",
                post_forced_override_pre_env_action,
            ),
            ("forced_gripper_close_mask", forced_gripper_close_mask),
            ("first_episode_active_mask", first_episode_active_mask),
            ("episode_indices", episode_indices),
        ):
            if tensor.device != expected_device:
                raise RuntimeError(
                    f"A2 eval diagnostic {tensor_name} must be on {expected_device}; "
                    f"got {tensor.device}."
                )

        self._a2_eval_policy_high_level_action_raw = (
            policy_high_level_action_raw.detach().clone()
        )
        self._a2_eval_post_forced_override_pre_env_action = (
            post_forced_override_pre_env_action.detach().clone()
        )
        self._a2_eval_forced_gripper_close_mask = (
            forced_gripper_close_mask.detach().clone()
        )
        self._a2_eval_first_episode_active_mask = (
            first_episode_active_mask.detach().clone()
        )
        self._a2_eval_episode_indices = episode_indices.detach().clone()

    def _capture_a2_eval_post_delta_post_warp_env_action(
        self, post_delta_post_warp_env_action: torch.Tensor
    ) -> None:
        if not self._a2_eval_diagnostic_trace_enabled:
            return
        layout = self.get_a2_high_level_action_layout()
        expected_shape = (self.num_envs, layout["dim"])
        if (
            not torch.is_tensor(post_delta_post_warp_env_action)
            or tuple(post_delta_post_warp_env_action.shape) != expected_shape
            or not torch.is_floating_point(post_delta_post_warp_env_action)
            or not torch.all(torch.isfinite(post_delta_post_warp_env_action))
            or post_delta_post_warp_env_action.device != torch.device(self.device)
        ):
            shape = (
                None
                if not torch.is_tensor(post_delta_post_warp_env_action)
                else tuple(post_delta_post_warp_env_action.shape)
            )
            dtype = (
                None
                if not torch.is_tensor(post_delta_post_warp_env_action)
                else post_delta_post_warp_env_action.dtype
            )
            device = (
                None
                if not torch.is_tensor(post_delta_post_warp_env_action)
                else post_delta_post_warp_env_action.device
            )
            raise RuntimeError(
                "A2 eval post-delta/post-warp env action requires finite floating "
                f"tensor shape {expected_shape} on {self.device}; got "
                f"shape={shape}, dtype={dtype}, device={device}."
            )
        self._a2_eval_post_delta_post_warp_env_action = (
            post_delta_post_warp_env_action.detach().clone()
        )

    @staticmethod
    def _parse_a2_hold_oracle_config(eval_config):
        enabled = eval_config.get("a2_hold_oracle_enabled", False)
        if not isinstance(enabled, bool):
            raise RuntimeError(f"eval.a2_hold_oracle_enabled must be bool; got {enabled!r}.")

        def positive_float(key):
            value = eval_config.get(key, None)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RuntimeError(f"eval.{key} must be a finite positive float; got {value!r}.")
            value = float(value)
            if not math.isfinite(value) or value <= 0.0:
                raise RuntimeError(f"eval.{key} must be a finite positive float; got {value!r}.")
            return value

        def positive_int(key):
            value = eval_config.get(key, None)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise RuntimeError(f"eval.{key} must be a positive int; got {value!r}.")
            return value

        def finite_float(key):
            value = eval_config.get(key, None)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RuntimeError(f"eval.{key} must be a finite float; got {value!r}.")
            value = float(value)
            if not math.isfinite(value):
                raise RuntimeError(f"eval.{key} must be a finite float; got {value!r}.")
            return value

        def required_bool(key):
            value = eval_config.get(key, None)
            if not isinstance(value, bool):
                raise RuntimeError(f"eval.{key} must be bool; got {value!r}.")
            return value

        config = {
            "enabled": enabled,
            "center_timeout_steps": positive_int("a2_hold_oracle_center_timeout_steps"),
            "center_position_tolerance_m": positive_float(
                "a2_hold_oracle_center_position_tolerance_m"
            ),
            "center_orientation_tolerance_rad": positive_float(
                "a2_hold_oracle_center_orientation_tolerance_rad"
            ),
            "depress_timeout_steps": positive_int("a2_hold_oracle_depress_timeout_steps"),
            "push_timeout_steps": positive_int("a2_hold_oracle_push_timeout_steps"),
            "depress_offset_m": positive_float("a2_hold_oracle_depress_offset_m"),
            "push_offset_m": positive_float("a2_hold_oracle_push_offset_m"),
            "offset_ramp_steps": positive_int("a2_hold_oracle_offset_ramp_steps"),
            "sign_smoke_steps": positive_int("a2_hold_oracle_sign_smoke_steps"),
            "sign_min_delta": positive_float("a2_hold_oracle_sign_min_delta"),
            "handle_target_rad": positive_float("a2_hold_oracle_handle_target_rad"),
            "hinge_progress_target_rad": positive_float(
                "a2_hold_oracle_hinge_progress_target_rad"
            ),
            "contact_slip_grace_steps": positive_int(
                "a2_hold_oracle_contact_slip_grace_steps"
            ),
            "dls_lambda": positive_float("a2_hold_oracle_dls_lambda"),
            "max_position_step_m": positive_float(
                "a2_hold_oracle_max_position_step_m"
            ),
            "max_orientation_step_rad": positive_float(
                "a2_hold_oracle_max_orientation_step_rad"
            ),
            "jacobian_condition_max": positive_float(
                "a2_hold_oracle_jacobian_condition_max"
            ),
            "joint_limit_margin": positive_float("a2_hold_oracle_joint_limit_margin"),
            "soft_limit_progress_tolerance": positive_float(
                "a2_hold_oracle_soft_limit_progress_tolerance"
            ),
            "raw_action_abs_max": positive_float("a2_hold_oracle_raw_action_abs_max"),
            "base_relief_speed_mps": positive_float(
                "a2_hold_oracle_base_relief_speed_mps"
            ),
            "base_relief_sign_window_steps": positive_int(
                "a2_hold_oracle_base_relief_sign_window_steps"
            ),
            "base_relief_min_residual_decrease_m": positive_float(
                "a2_hold_oracle_base_relief_min_residual_decrease_m"
            ),
            "base_relief_timeout_steps": positive_int(
                "a2_hold_oracle_base_relief_timeout_steps"
            ),
            "base_relief_max_displacement_m": positive_float(
                "a2_hold_oracle_base_relief_max_displacement_m"
            ),
            "base_relief_min_solvable_horizontal_error_m": positive_float(
                "a2_hold_oracle_base_relief_min_solvable_horizontal_error_m"
            ),
            "static_clamp_enabled": required_bool(
                "a2_hold_oracle_static_clamp_enabled"
            ),
            "static_clamp_steps": positive_int(
                "a2_hold_oracle_static_clamp_steps"
            ),
            "static_clamp_stiffness": positive_float(
                "a2_hold_oracle_static_clamp_stiffness"
            ),
            "static_clamp_damping": positive_float(
                "a2_hold_oracle_static_clamp_damping"
            ),
            "static_clamp_offset_probe_enabled": required_bool(
                "a2_hold_oracle_static_clamp_offset_probe_enabled"
            ),
            "static_clamp_offset_m": finite_float(
                "a2_hold_oracle_static_clamp_offset_m"
            ),
            "static_clamp_offset_placement_steps": positive_int(
                "a2_hold_oracle_static_clamp_offset_placement_steps"
            ),
            "static_clamp_offset_position_tolerance_m": positive_float(
                "a2_hold_oracle_static_clamp_offset_position_tolerance_m"
            ),
            "static_clamp_offset_orientation_tolerance_rad": positive_float(
                "a2_hold_oracle_static_clamp_offset_orientation_tolerance_rad"
            ),
            "open_stabilization_preflight_enabled": required_bool(
                "a2_hold_oracle_open_stabilization_preflight_enabled"
            ),
            "open_stabilization_steps": positive_int(
                "a2_hold_oracle_open_stabilization_steps"
            ),
            "open_stabilization_quiet_window_steps": positive_int(
                "a2_hold_oracle_open_stabilization_quiet_window_steps"
            ),
            "open_stabilization_root_linear_speed_max_mps": positive_float(
                "a2_hold_oracle_open_stabilization_root_linear_speed_max_mps"
            ),
            "open_stabilization_root_angular_speed_max_radps": positive_float(
                "a2_hold_oracle_open_stabilization_root_angular_speed_max_radps"
            ),
            "open_stabilization_pose_per_call_translation_max_m": positive_float(
                "a2_hold_oracle_open_stabilization_pose_per_call_translation_max_m"
            ),
            "open_stabilization_pose_per_call_rotation_max_rad": positive_float(
                "a2_hold_oracle_open_stabilization_pose_per_call_rotation_max_rad"
            ),
            "open_stabilization_pose_window_translation_max_m": positive_float(
                "a2_hold_oracle_open_stabilization_pose_window_translation_max_m"
            ),
            "open_stabilization_pose_window_rotation_max_rad": positive_float(
                "a2_hold_oracle_open_stabilization_pose_window_rotation_max_rad"
            ),
            "open_stabilization_contact_force_max_n": positive_float(
                "a2_hold_oracle_open_stabilization_contact_force_max_n"
            ),
            "matched_clean_reacquisition_preflight_enabled": required_bool(
                "a2_hold_oracle_matched_clean_reacquisition_preflight_enabled"
            ),
            "matched_clean_retreat_timeout_steps": positive_int(
                "a2_hold_oracle_matched_clean_retreat_timeout_steps"
            ),
            "matched_clean_release_qualification_steps": positive_int(
                "a2_hold_oracle_matched_clean_release_qualification_steps"
            ),
            "matched_clean_pregrasp_position_tolerance_m": positive_float(
                "a2_hold_oracle_matched_clean_pregrasp_position_tolerance_m"
            ),
            "matched_clean_pregrasp_orientation_tolerance_rad": positive_float(
                "a2_hold_oracle_matched_clean_pregrasp_orientation_tolerance_rad"
            ),
        }
        if config["sign_smoke_steps"] >= config["depress_timeout_steps"]:
            raise RuntimeError("A2 hold depress sign-smoke window must be shorter than its timeout.")
        if config["sign_smoke_steps"] >= config["push_timeout_steps"]:
            raise RuntimeError("A2 hold push sign-smoke window must be shorter than its timeout.")
        if config["base_relief_sign_window_steps"] >= config["base_relief_timeout_steps"]:
            raise RuntimeError(
                "A2 hold base-relief sign window must be shorter than its timeout."
            )
        if config["static_clamp_enabled"] and not config["enabled"]:
            raise RuntimeError("A2 static clamp requires a2_hold_oracle_enabled=true.")
        if config["static_clamp_enabled"]:
            if config["static_clamp_steps"] != 40:
                raise RuntimeError(
                    "A2 static clamp requires exactly 40 action steps; "
                    f"got {config['static_clamp_steps']}."
                )
            gain_pair = (
                config["static_clamp_stiffness"],
                config["static_clamp_damping"],
            )
            allowed_gain_pairs = ((80.0, 3.0), (160.0, 6.0), (320.0, 12.0))
            if gain_pair not in allowed_gain_pairs:
                raise RuntimeError(
                    "A2 static clamp requires an exact approved (Kp,Kd) pair in "
                    f"{allowed_gain_pairs}; got {gain_pair}."
                )
        if config["static_clamp_offset_probe_enabled"]:
            if not config["enabled"] or not config["static_clamp_enabled"]:
                raise RuntimeError(
                    "A2 offset probe requires hold oracle and static clamp enabled."
                )
            if config["static_clamp_offset_m"] not in (-0.003, 0.0, 0.003):
                raise RuntimeError(
                    "A2 offset probe requires exact offset in {-0.003,0,+0.003}; "
                    f"got {config['static_clamp_offset_m']}."
                )
            if config["static_clamp_offset_placement_steps"] != 20:
                raise RuntimeError("A2 offset probe requires exactly 20 placement actions.")
            if config["static_clamp_steps"] != 40:
                raise RuntimeError("A2 offset probe requires exactly 40 clamp actions.")
            if (
                config["static_clamp_stiffness"],
                config["static_clamp_damping"],
            ) != (160.0, 6.0):
                raise RuntimeError("A2 offset probe requires exact clamp Kp/Kd=(160,6).")
            formal_protocol = {
                "static_clamp_offset_position_tolerance_m": 0.0005,
                "static_clamp_offset_orientation_tolerance_rad": 0.02,
                "max_position_step_m": 0.002,
                "max_orientation_step_rad": 0.02,
                "dls_lambda": 0.01,
                "jacobian_condition_max": 1.0e6,
                "joint_limit_margin": 1.0e-4,
                "soft_limit_progress_tolerance": 1.0e-6,
                "raw_action_abs_max": 10.0,
            }
            mismatched = {
                key: (config[key], expected)
                for key, expected in formal_protocol.items()
                if config[key] != expected
            }
            if mismatched:
                raise RuntimeError(
                    "A2 offset probe requires the exact formal protocol tuple; "
                    f"mismatched={mismatched}."
                )
        if config["open_stabilization_preflight_enabled"]:
            if not config["enabled"]:
                raise RuntimeError(
                    "A2 open stabilization preflight requires a2_hold_oracle_enabled=true."
                )
            if config["static_clamp_enabled"] or config[
                "static_clamp_offset_probe_enabled"
            ]:
                raise RuntimeError(
                    "A2 open stabilization preflight is mutually exclusive with static clamp and offset probe."
                )
            formal_protocol = {
                "open_stabilization_steps": 40,
                "open_stabilization_quiet_window_steps": 5,
                "open_stabilization_root_linear_speed_max_mps": 0.01,
                "open_stabilization_root_angular_speed_max_radps": 0.02,
                "open_stabilization_pose_per_call_translation_max_m": 0.0005,
                "open_stabilization_pose_per_call_rotation_max_rad": 0.0005,
                "open_stabilization_pose_window_translation_max_m": 0.001,
                "open_stabilization_pose_window_rotation_max_rad": 0.002,
                "open_stabilization_contact_force_max_n": 1.0,
            }
            mismatched = {
                key: (config[key], expected)
                for key, expected in formal_protocol.items()
                if config[key] != expected
            }
            if mismatched:
                raise RuntimeError(
                    "A2 open stabilization preflight requires the exact formal protocol tuple; "
                    f"mismatched={mismatched}."
                )
        if config["matched_clean_reacquisition_preflight_enabled"]:
            if not config["enabled"]:
                raise RuntimeError(
                    "A2 matched-clean reacquisition requires a2_hold_oracle_enabled=true."
                )
            if (
                config["static_clamp_enabled"]
                or config["static_clamp_offset_probe_enabled"]
                or config["open_stabilization_preflight_enabled"]
            ):
                raise RuntimeError(
                    "A2 matched-clean reacquisition is mutually exclusive with static clamp, "
                    "offset probe, and open stabilization."
                )
            formal_protocol = {
                "matched_clean_retreat_timeout_steps": 80,
                "matched_clean_release_qualification_steps": 5,
                "matched_clean_pregrasp_position_tolerance_m": 0.005,
                "matched_clean_pregrasp_orientation_tolerance_rad": 0.10,
                "open_stabilization_steps": 40,
                "open_stabilization_quiet_window_steps": 5,
                "open_stabilization_root_linear_speed_max_mps": 0.01,
                "open_stabilization_root_angular_speed_max_radps": 0.02,
                "open_stabilization_pose_per_call_translation_max_m": 0.0005,
                "open_stabilization_pose_per_call_rotation_max_rad": 0.0005,
                "open_stabilization_pose_window_translation_max_m": 0.001,
                "open_stabilization_pose_window_rotation_max_rad": 0.002,
                "open_stabilization_contact_force_max_n": 1.0,
                "max_position_step_m": 0.002,
                "max_orientation_step_rad": 0.02,
                "dls_lambda": 0.01,
                "jacobian_condition_max": 1.0e6,
                "joint_limit_margin": 1.0e-4,
                "soft_limit_progress_tolerance": 1.0e-6,
                "raw_action_abs_max": 10.0,
            }
            mismatched = {
                key: (config[key], expected)
                for key, expected in formal_protocol.items()
                if config[key] != expected
            }
            if mismatched:
                raise RuntimeError(
                    "A2 matched-clean reacquisition requires the exact approved protocol tuple; "
                    f"mismatched={mismatched}."
                )
        return config

    def init_a2_eval_hold_oracle(self, eval_config, *, diagnostic_enabled: bool) -> dict:
        if not self._use_a2_base or not getattr(self, "is_evaluating", False):
            raise RuntimeError("A2 hold oracle can only initialize in an evaluating A2 env.")
        cfg = self._parse_a2_hold_oracle_config(eval_config)
        cfg["tcp_offset_z"] = self._get_a2_gripper_source_tcp_offset_z()
        if cfg["enabled"] and not diagnostic_enabled:
            raise RuntimeError("A2 hold oracle requires eval.a2_diagnostic_trace_enabled=true.")
        if cfg["static_clamp_enabled"] and not self._get_a2_hold_contact_detail_enabled():
            raise RuntimeError("A2 static clamp requires detailed hold diagnostics.")
        if cfg["static_clamp_offset_probe_enabled"]:
            if cfg["tcp_offset_z"] != 0.085:
                raise RuntimeError("A2 offset probe requires exact current TCP z=0.085.")
            if self._get_a2_hold_friction_override() is not None:
                raise RuntimeError("A2 offset probe requires friction override=null.")
        if cfg["open_stabilization_preflight_enabled"]:
            if cfg["tcp_offset_z"] != 0.085:
                raise RuntimeError("A2 open stabilization requires exact current TCP z=0.085.")
            if self._get_a2_hold_friction_override() is not None:
                raise RuntimeError("A2 open stabilization requires friction override=null.")
        if cfg["matched_clean_reacquisition_preflight_enabled"]:
            if cfg["tcp_offset_z"] != 0.085:
                raise RuntimeError(
                    "A2 matched-clean reacquisition requires exact current TCP z=0.085."
                )
            if self._get_a2_hold_friction_override() is not None:
                raise RuntimeError(
                    "A2 matched-clean reacquisition requires friction override=null."
                )
        if (cfg["enabled"] or self._get_a2_hold_friction_override() is not None) and not self._get_a2_hold_contact_detail_enabled():
            raise RuntimeError(
                "A2 hold oracle/material override requires env detailed contact diagnostics enabled."
            )
        if cfg["enabled"]:
            action_scale = float(self.config.robot.control.action_scale)
            delta_scale = float(self.config.delta_action_scale)
            delta_clip = float(self.config.delta_action_clip)
            if action_scale != 0.25 or delta_scale != 0.3 or delta_clip != 15.0:
                raise RuntimeError(
                    "A2 hold oracle cumulative semantics require robot action_scale=0.25, "
                    f"delta_action_scale=0.3 and delta_action_clip=15.0; got "
                    f"{action_scale}, {delta_scale}, {delta_clip}."
                )
            layout = self.get_a2_high_level_action_layout()
            expected_layout = {
                "dim": 12,
                "base_start": 0,
                "base_end": 5,
                "arm_start": 5,
                "arm_end": 11,
                "gripper_index": 11,
            }
            if layout != expected_layout:
                raise RuntimeError(
                    f"A2 hold base relief requires canonical action layout {expected_layout}; "
                    f"got {layout}."
                )
            if not cfg["matched_clean_reacquisition_preflight_enabled"]:
                if self._k != 0 or self._s != 0:
                    raise RuntimeError(
                        "A2 hold base relief requires warped_action k=0 and s=0; "
                        f"got k={self._k}, s={self._s}."
                    )
                if (
                    not math.isfinite(float(self._a2_base_command_scale))
                    or self._a2_base_command_scale <= 0.0
                ):
                    raise RuntimeError(
                        "A2 hold base relief requires a finite positive A2 base command scale; "
                        f"got {self._a2_base_command_scale}."
                    )
                if self._clip_homie_command:
                    clip_x = float(self.config.clip_homie_linvel_x_threshold)
                    clip_y = float(self.config.clip_homie_linvel_y_threshold)
                    if (
                        not math.isfinite(clip_x)
                        or not math.isfinite(clip_y)
                        or clip_x <= 0.0
                        or clip_y <= 0.0
                        or cfg["base_relief_speed_mps"] > clip_x
                        or cfg["base_relief_speed_mps"] > clip_y
                    ):
                        raise RuntimeError(
                            "A2 hold base-relief physical speed must fit both enabled XY "
                            "command clip thresholds without downstream clipping; "
                            f"speed={cfg['base_relief_speed_mps']}, x={clip_x}, y={clip_y}."
                        )
        self._a2_hold_oracle_cfg = cfg
        self._a2_hold_oracle_phase = torch.full(
            (self.num_envs,), A2_HOLD_PHASE_WAIT_GATE, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_phase_step = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_outcome = torch.full(
            (self.num_envs,), A2_HOLD_OUTCOME_TO_ID["PENDING"], device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_activated = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_slip_steps = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_last_single_body7 = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_last_single_body8 = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_handle_start = torch.zeros(self.num_envs, device=self.device)
        self._a2_hold_oracle_hinge_start = torch.zeros(self.num_envs, device=self.device)
        self._a2_hold_oracle_q_des = torch.full(
            (self.num_envs, 6), float("nan"), device=self.device
        )
        self._a2_hold_oracle_d_des = torch.full_like(self._a2_hold_oracle_q_des, float("nan"))
        self._a2_hold_oracle_d_prev = torch.full_like(self._a2_hold_oracle_q_des, float("nan"))
        self._a2_hold_oracle_a_raw = torch.full_like(self._a2_hold_oracle_q_des, float("nan"))
        self._a2_hold_oracle_target_pos_root = torch.full(
            (self.num_envs, 3), float("nan"), device=self.device
        )
        self._a2_hold_oracle_target_quat_root = torch.full(
            (self.num_envs, 4), float("nan"), device=self.device
        )
        self._a2_hold_oracle_bounded_command_pos_root = torch.full(
            (self.num_envs, 3), float("nan"), device=self.device
        )
        self._a2_hold_oracle_bounded_command_quat_root = torch.full(
            (self.num_envs, 4), float("nan"), device=self.device
        )
        self._a2_hold_oracle_bounded_position_step = torch.full(
            (self.num_envs,), float("nan"), device=self.device
        )
        self._a2_hold_oracle_bounded_orientation_step = torch.full(
            (self.num_envs,), float("nan"), device=self.device
        )
        self._a2_hold_oracle_position_residual = torch.full(
            (self.num_envs,), float("nan"), device=self.device
        )
        self._a2_hold_oracle_orientation_residual = torch.full(
            (self.num_envs,), float("nan"), device=self.device
        )
        self._a2_hold_oracle_singular_values = torch.full(
            (self.num_envs, 6), float("nan"), device=self.device
        )
        self._a2_hold_oracle_jacobian_condition = torch.full(
            (self.num_envs,), float("nan"), device=self.device
        )
        self._a2_hold_oracle_ik_valid = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_delta_ok = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_raw_ok = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_last_hinge_delta = torch.zeros(
            self.num_envs, device=self.device
        )
        self._a2_hold_oracle_last_override_mask = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_arm_dls_branch = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_phase_arm_dls_count = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_phase_sign_checked = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_phase_sign_check_due = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_base_relief_active = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_base_relief_branch_applied = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_base_relief_ever_entered = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_base_relief_steps = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_base_relief_initial_horizontal_residual = torch.full(
            (self.num_envs,), float("nan"), device=self.device
        )
        self._a2_hold_oracle_base_relief_start_root_xy = torch.full(
            (self.num_envs, 2), float("nan"), device=self.device
        )
        self._a2_hold_oracle_base_relief_current_horizontal_residual = torch.full(
            (self.num_envs,), float("nan"), device=self.device
        )
        self._a2_hold_oracle_horizontal_residual = torch.full(
            (self.num_envs,), float("nan"), device=self.device
        )
        self._a2_hold_oracle_base_relief_body_velocity_command = torch.zeros(
            self.num_envs, 2, device=self.device
        )
        self._a2_hold_oracle_base_relief_raw_command = torch.zeros(
            self.num_envs, 5, device=self.device
        )
        self._a2_hold_oracle_arm_candidate_action_raw = torch.full_like(
            self._a2_hold_oracle_q_des, float("nan")
        )
        self._a2_hold_oracle_limit_valid = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_static_clamp_active = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_static_clamp_gain_applied = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_static_clamp_ever_activated = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_static_clamp_restored = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_static_clamp_write_count = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_static_clamp_final_write_count = torch.full(
            (self.num_envs,), -1, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_static_clamp_original_stiffness = torch.full(
            (self.num_envs, 2), float("nan"), device=self.device
        )
        self._a2_hold_oracle_static_clamp_original_damping = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_original_effort_limit = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_requested_stiffness = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_requested_damping = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_applied_stiffness = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_applied_damping = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_applied_effort_limit = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_restored_stiffness = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_restored_damping = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_restored_effort_limit = torch.full_like(
            self._a2_hold_oracle_static_clamp_original_stiffness, float("nan")
        )
        self._a2_hold_oracle_static_clamp_step40_snapshot = [
            None for _ in range(self.num_envs)
        ]
        self._a2_hold_oracle_offset_placement_active = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_offset_placement_ever_activated = torch.zeros_like(
            self._a2_hold_oracle_offset_placement_active
        )
        self._a2_hold_oracle_offset_placement_validated = torch.zeros_like(
            self._a2_hold_oracle_offset_placement_active
        )
        self._a2_hold_oracle_offset_endpoint_checked = torch.zeros_like(
            self._a2_hold_oracle_offset_placement_active
        )
        self._a2_hold_oracle_offset_placement_branch = torch.zeros_like(
            self._a2_hold_oracle_offset_placement_active
        )
        self._a2_hold_oracle_offset_placement_action_count = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_offset_final_placement_action_count = torch.full(
            (self.num_envs,), -1, device=self.device, dtype=torch.long
        )
        offset_pose_shape = (self.num_envs, 3)
        offset_quat_shape = (self.num_envs, 4)
        self._a2_hold_oracle_offset_gate_source_pos_w = torch.full(
            offset_pose_shape, float("nan"), device=self.device
        )
        self._a2_hold_oracle_offset_gate_source_quat_w = torch.full(
            offset_quat_shape, float("nan"), device=self.device
        )
        self._a2_hold_oracle_offset_gate_handle_pos_w = torch.full_like(
            self._a2_hold_oracle_offset_gate_source_pos_w, float("nan")
        )
        self._a2_hold_oracle_offset_gate_handle_quat_w = torch.full_like(
            self._a2_hold_oracle_offset_gate_source_quat_w, float("nan")
        )
        self._a2_hold_oracle_offset_source_local_y_axis_w = torch.full_like(
            self._a2_hold_oracle_offset_gate_source_pos_w, float("nan")
        )
        self._a2_hold_oracle_offset_fixed_target_pos_w = torch.full_like(
            self._a2_hold_oracle_offset_gate_source_pos_w, float("nan")
        )
        self._a2_hold_oracle_offset_fixed_target_quat_w = torch.full_like(
            self._a2_hold_oracle_offset_gate_source_quat_w, float("nan")
        )
        self._a2_hold_oracle_offset_opening_axis_dots_body7_body8 = torch.full(
            (self.num_envs, 2), float("nan"), device=self.device
        )
        self._a2_hold_oracle_offset_achieved_signed_offset_m = torch.full(
            (self.num_envs,), float("nan"), device=self.device
        )
        self._a2_hold_oracle_offset_signed_offset_error_m = torch.full_like(
            self._a2_hold_oracle_offset_achieved_signed_offset_m, float("nan")
        )
        self._a2_hold_oracle_offset_orthogonal_residual_m = torch.full_like(
            self._a2_hold_oracle_offset_achieved_signed_offset_m, float("nan")
        )
        self._a2_hold_oracle_offset_position_residual_m = torch.full_like(
            self._a2_hold_oracle_offset_achieved_signed_offset_m, float("nan")
        )
        self._a2_hold_oracle_offset_orientation_residual_rad = torch.full_like(
            self._a2_hold_oracle_offset_achieved_signed_offset_m, float("nan")
        )
        self._a2_hold_oracle_offset_root_start_xy_w = torch.full(
            (self.num_envs, 2), float("nan"), device=self.device
        )
        self._a2_hold_oracle_offset_root_displacement_m = torch.full_like(
            self._a2_hold_oracle_offset_achieved_signed_offset_m, float("nan")
        )
        self._a2_hold_oracle_offset_handle_joint_start = torch.full_like(
            self._a2_hold_oracle_offset_achieved_signed_offset_m, float("nan")
        )
        self._a2_hold_oracle_offset_hinge_joint_start = torch.full_like(
            self._a2_hold_oracle_offset_achieved_signed_offset_m, float("nan")
        )
        self._a2_hold_oracle_offset_handle_joint_delta = torch.full_like(
            self._a2_hold_oracle_offset_achieved_signed_offset_m, float("nan")
        )
        self._a2_hold_oracle_offset_hinge_joint_delta = torch.full_like(
            self._a2_hold_oracle_offset_achieved_signed_offset_m, float("nan")
        )
        self._a2_hold_oracle_offset_preclamp_snapshot = [
            None for _ in range(self.num_envs)
        ]
        self._a2_hold_oracle_open_stabilization_active = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_open_stabilization_ever_activated = torch.zeros_like(
            self._a2_hold_oracle_open_stabilization_active
        )
        self._a2_hold_oracle_open_stabilization_action_count = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_open_stabilization_final_action_count = torch.full(
            (self.num_envs,), -1, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_open_stabilization_gate_captured = torch.zeros_like(
            self._a2_hold_oracle_open_stabilization_active
        )
        self._a2_hold_oracle_open_stabilization_gate_root_pos_w = torch.full(
            (self.num_envs, 3), float("nan"), device=self.device
        )
        self._a2_hold_oracle_open_stabilization_gate_root_quat_w = torch.full(
            (self.num_envs, 4), float("nan"), device=self.device
        )
        self._a2_hold_oracle_open_stabilization_gate_source_pos_w = torch.full_like(
            self._a2_hold_oracle_open_stabilization_gate_root_pos_w, float("nan")
        )
        self._a2_hold_oracle_open_stabilization_gate_source_quat_w = torch.full_like(
            self._a2_hold_oracle_open_stabilization_gate_root_quat_w, float("nan")
        )
        self._a2_hold_oracle_open_stabilization_gate_handle_pos_w = torch.full_like(
            self._a2_hold_oracle_open_stabilization_gate_root_pos_w, float("nan")
        )
        self._a2_hold_oracle_open_stabilization_gate_handle_quat_w = torch.full_like(
            self._a2_hold_oracle_open_stabilization_gate_root_quat_w, float("nan")
        )
        self._a2_hold_oracle_open_stabilization_arm_target_capture = torch.full(
            (self.num_envs, 6), float("nan"), device=self.device
        )
        self._a2_hold_oracle_open_stabilization_samples = [
            [] for _ in range(self.num_envs)
        ]
        self._a2_hold_oracle_open_stabilization_result = [
            None for _ in range(self.num_envs)
        ]
        self._a2_hold_oracle_open_stabilization_reason_contact = torch.zeros_like(
            self._a2_hold_oracle_open_stabilization_active
        )
        self._a2_hold_oracle_open_stabilization_reason_gate = torch.zeros_like(
            self._a2_hold_oracle_open_stabilization_active
        )
        self._a2_hold_oracle_open_stabilization_reason_incomplete = torch.zeros_like(
            self._a2_hold_oracle_open_stabilization_active
        )
        self._a2_hold_oracle_open_stabilization_reason_ready = torch.zeros_like(
            self._a2_hold_oracle_open_stabilization_active
        )
        self._a2_hold_oracle_open_stabilization_reason_not_settled = torch.zeros_like(
            self._a2_hold_oracle_open_stabilization_active
        )
        self._a2_hold_oracle_matched_clean_release_active = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_matched_clean_stabilize_active = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_ever_activated = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_release_action_count = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_matched_clean_release_final_action_count = torch.full(
            (self.num_envs,), -1, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_matched_clean_qualification_count = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_matched_clean_stabilize_action_count = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_matched_clean_stabilize_final_action_count = torch.full(
            (self.num_envs,), -1, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_matched_clean_gate_lost_ever = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_release_contact_reset_count = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._a2_hold_oracle_matched_clean_captured_arm_target = torch.full(
            (self.num_envs, 6), float("nan"), device=self.device
        )
        self._a2_hold_oracle_matched_clean_samples = [
            [] for _ in range(self.num_envs)
        ]
        self._a2_hold_oracle_matched_clean_quiet_samples = [
            [] for _ in range(self.num_envs)
        ]
        self._a2_hold_oracle_matched_clean_result = [
            None for _ in range(self.num_envs)
        ]
        self._a2_hold_oracle_matched_clean_release_qualification_evidence = [
            None for _ in range(self.num_envs)
        ]
        self._a2_hold_oracle_matched_clean_reason_contact = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_reason_timeout = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_reason_incomplete = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_reason_ready = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_reason_not_settled = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_actual_invariant_evidence = [
            [] for _ in range(self.num_envs)
        ]
        self._a2_hold_oracle_matched_clean_release_ik_invalid = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_release_joint_limit = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_release_action_invalid = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_release_override_mask = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_matched_clean_stabilize_override_mask = torch.zeros_like(
            self._a2_hold_oracle_matched_clean_release_active
        )
        self._a2_hold_oracle_finalized = False
        self._a2_hold_oracle_post_override_action = None
        if not cfg["enabled"]:
            return dict(cfg)
        robot = self.simulator.scene.articulations["robot"]
        handoff_dtype = robot.data.body_quat_w.dtype
        self._a2_hold_oracle_handoff_relative_quat = torch.full(
            (self.num_envs, 4),
            float("nan"),
            device=self.device,
            dtype=handoff_dtype,
        )
        self._a2_hold_oracle_handoff_orientation_captured = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        body_ids, body_names = robot.find_bodies("arm_body6_to_gripper", preserve_order=True)
        if len(body_ids) != 1 or body_names != ["arm_body6_to_gripper"]:
            raise RuntimeError(
                "A2 hold oracle requires exactly one arm_body6_to_gripper; "
                f"got {body_ids}, {body_names}."
            )
        joint_ids, joint_names = robot.find_joints(
            [f"arm_j{i}" for i in range(1, 7)], preserve_order=True
        )
        if joint_names != [f"arm_j{i}" for i in range(1, 7)]:
            raise RuntimeError(f"A2 hold oracle arm joint order mismatch: {joint_names}.")
        gripper_joint_ids, gripper_joint_names = robot.find_joints(
            ["arm_j7", "arm_j8"], preserve_order=True
        )
        if gripper_joint_names != ["arm_j7", "arm_j8"]:
            raise RuntimeError(
                f"A2 static clamp gripper joint order mismatch: {gripper_joint_names}."
            )
        self._a2_hold_oracle_body_id = body_ids[0]
        self._a2_hold_oracle_joint_ids = joint_ids
        self._a2_hold_oracle_gripper_joint_ids = gripper_joint_ids
        self._a2_hold_oracle_jacobian_body_id = body_ids[0]
        self._a2_hold_oracle_jacobian_joint_ids = [joint_id + 6 for joint_id in joint_ids]
        self._a2_hold_oracle_controller = DifferentialIKController(
            DifferentialIKControllerCfg(
                command_type="pose",
                use_relative_mode=False,
                ik_method="dls",
                ik_params={"lambda_val": cfg["dls_lambda"]},
            ),
            num_envs=self.num_envs,
            device=self.device,
        )
        return dict(cfg)

    def _set_a2_hold_outcome(self, mask: torch.Tensor, outcome: str) -> None:
        if outcome not in A2_HOLD_OUTCOME_TO_ID:
            raise RuntimeError(f"Unknown A2 hold oracle outcome {outcome!r}.")
        mask = mask & (
            self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
        )
        self._a2_hold_oracle_outcome[mask] = A2_HOLD_OUTCOME_TO_ID[outcome]
        self._a2_hold_oracle_phase[mask] = A2_HOLD_PHASE_DONE

    def _get_a2_offset_opening_axes_w(self) -> torch.Tensor:
        robot = self.simulator.scene.articulations["robot"]
        body_ids = []
        for body_name in ("arm_body7", "arm_body8"):
            ids, names = robot.find_bodies(body_name, preserve_order=True)
            if len(ids) != 1 or names != [body_name]:
                raise RuntimeError(
                    f"A2 offset probe requires exactly one {body_name}; got {ids}, {names}."
                )
            body_ids.append(ids[0])
        joint_ids = a2_hold_map_task_to_articulation_joint_ids(
            self.simulator.dof_ids,
            self._a2_gripper_dof_indices,
            self.dof_names,
            robot.data.joint_pos.shape[1],
            self.device,
        )
        joint_names = [robot.joint_names[index] for index in joint_ids.tolist()]
        if joint_names != ["arm_j7", "arm_j8"]:
            raise RuntimeError(
                "A2 offset probe requires mapped arm_j7,arm_j8 order; "
                f"got {joint_names}."
            )
        jacobian = robot.root_physx_view.get_jacobians()
        return a2_hold_signed_gripper_opening_axes_from_jacobian(
            jacobian,
            torch.tensor(body_ids, device=self.device, dtype=torch.long),
            joint_ids,
            self._a2_gripper_open_target.to(
                device=self.device, dtype=jacobian.dtype
            ),
            self._a2_gripper_close_target.to(
                device=self.device, dtype=jacobian.dtype
            ),
        )

    def _capture_a2_offset_gate(self, capture_mask: torch.Tensor) -> None:
        env_ids = torch.nonzero(capture_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return
        if torch.any(self._a2_hold_oracle_offset_placement_ever_activated[env_ids]):
            raise RuntimeError("A2 offset gate may only be captured once per env.")
        frames = self._get_a2_hold_oracle_world_frames()
        gate_pos = frames["source_pos_w"][env_ids]
        gate_quat = frames["source_quat_w"][env_ids]
        try:
            axis_w, target_pos_w, target_quat_w = a2_hold_offset_fixed_world_target(
                gate_pos,
                gate_quat,
                self._a2_hold_oracle_cfg["static_clamp_offset_m"],
            )
            dots = a2_hold_validate_offset_axis_opening_dots(
                axis_w, self._get_a2_offset_opening_axes_w()[env_ids]
            )
        except ValueError as exc:
            raise RuntimeError(f"A2 offset gate capture failed: {exc}") from exc
        _, _, gripper_state = self._get_a2_static_clamp_gripper_state(env_ids)
        expected_stiffness = torch.full_like(gripper_state["stiffness"], 80.0)
        expected_damping = torch.full_like(gripper_state["damping"], 3.0)
        expected_effort = torch.full_like(gripper_state["effort_limit"], 10.0)
        if (
            not torch.equal(gripper_state["stiffness"], expected_stiffness)
            or not torch.equal(gripper_state["damping"], expected_damping)
            or not torch.equal(gripper_state["effort_limit"], expected_effort)
        ):
            raise RuntimeError(
                "A2 offset placement requires initial gripper Kp/Kd=80/3 and effort=10/10."
            )
        door_joint_pos = self._get_door_joint_pos("A2 offset gate capture", 2)
        self._a2_hold_oracle_offset_gate_source_pos_w[env_ids] = gate_pos
        self._a2_hold_oracle_offset_gate_source_quat_w[env_ids] = gate_quat
        self._a2_hold_oracle_offset_gate_handle_pos_w[env_ids] = frames[
            "handle_pos_w"
        ][env_ids]
        self._a2_hold_oracle_offset_gate_handle_quat_w[env_ids] = frames[
            "handle_quat_w"
        ][env_ids]
        self._a2_hold_oracle_offset_source_local_y_axis_w[env_ids] = axis_w
        self._a2_hold_oracle_offset_fixed_target_pos_w[env_ids] = target_pos_w
        self._a2_hold_oracle_offset_fixed_target_quat_w[env_ids] = target_quat_w
        self._a2_hold_oracle_offset_opening_axis_dots_body7_body8[env_ids] = dots
        self._a2_hold_oracle_offset_root_start_xy_w[env_ids] = frames["root_pos_w"][
            env_ids, :2
        ]
        self._a2_hold_oracle_offset_hinge_joint_start[env_ids] = door_joint_pos[
            env_ids, 0
        ]
        self._a2_hold_oracle_offset_handle_joint_start[env_ids] = door_joint_pos[
            env_ids, 1
        ]
        self._a2_hold_oracle_offset_placement_ever_activated[env_ids] = True

    def _snapshot_a2_offset_placement_state(self, snapshot_mask: torch.Tensor) -> dict:
        env_ids = torch.nonzero(snapshot_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return {"converged": torch.zeros_like(snapshot_mask)}
        if torch.any(self._a2_hold_oracle_static_clamp_gain_applied[env_ids]):
            raise RuntimeError("A2 offset endpoint snapshot must precede clamp gains.")
        frames = self._get_a2_hold_oracle_world_frames()
        try:
            endpoint = a2_hold_offset_endpoint_metrics(
                frames["source_pos_w"][env_ids],
                frames["source_quat_w"][env_ids],
                self._a2_hold_oracle_offset_gate_source_pos_w[env_ids],
                self._a2_hold_oracle_offset_fixed_target_pos_w[env_ids],
                self._a2_hold_oracle_offset_fixed_target_quat_w[env_ids],
                self._a2_hold_oracle_offset_source_local_y_axis_w[env_ids],
                self._a2_hold_oracle_cfg["static_clamp_offset_m"],
                self._a2_hold_oracle_cfg[
                    "static_clamp_offset_position_tolerance_m"
                ],
                self._a2_hold_oracle_cfg[
                    "static_clamp_offset_orientation_tolerance_rad"
                ],
            )
        except ValueError as exc:
            raise RuntimeError(f"A2 offset placement endpoint failed: {exc}") from exc
        field_map = {
            "achieved_signed_offset_m": self._a2_hold_oracle_offset_achieved_signed_offset_m,
            "signed_offset_error_m": self._a2_hold_oracle_offset_signed_offset_error_m,
            "orthogonal_residual_m": self._a2_hold_oracle_offset_orthogonal_residual_m,
            "position_residual_m": self._a2_hold_oracle_offset_position_residual_m,
            "orientation_residual_rad": self._a2_hold_oracle_offset_orientation_residual_rad,
        }
        for name, destination in field_map.items():
            destination[env_ids] = endpoint[name]
        root_displacement = torch.linalg.norm(
            frames["root_pos_w"][env_ids, :2]
            - self._a2_hold_oracle_offset_root_start_xy_w[env_ids],
            dim=-1,
        )
        self._a2_hold_oracle_offset_root_displacement_m[env_ids] = root_displacement
        door_joint_pos = self._get_door_joint_pos("A2 offset placement snapshot", 2)
        self._a2_hold_oracle_offset_hinge_joint_delta[env_ids] = (
            door_joint_pos[env_ids, 0]
            - self._a2_hold_oracle_offset_hinge_joint_start[env_ids]
        )
        self._a2_hold_oracle_offset_handle_joint_delta[env_ids] = (
            door_joint_pos[env_ids, 1]
            - self._a2_hold_oracle_offset_handle_joint_start[env_ids]
        )
        details = self._get_a2_hold_detailed_step_fields(env_ids)
        robot = self.simulator.scene.articulations["robot"]
        gripper_ids = torch.tensor(
            self._a2_hold_oracle_gripper_joint_ids,
            device=self.device,
            dtype=torch.long,
        )
        for local_index, (env_id, detail) in enumerate(
            zip(env_ids.tolist(), details, strict=True)
        ):
            if self._a2_hold_oracle_offset_preclamp_snapshot[env_id] is not None:
                raise RuntimeError("A2 offset placement snapshot cannot be captured twice.")
            record = dict(detail)
            record.update(
                {
                    "offset_phase": "PLACEMENT_CHECK",
                    "static_clamp_gain_applied_at_snapshot": False,
                    "placement_action_count": int(
                        self._a2_hold_oracle_offset_placement_action_count[
                            env_id
                        ].item()
                    ),
                    "gripper_joint_pos": robot.data.joint_pos[
                        env_id, gripper_ids
                    ].detach().cpu().tolist(),
                    "achieved_signed_offset_m": float(
                        endpoint["achieved_signed_offset_m"][local_index].item()
                    ),
                    "signed_offset_error_m": float(
                        endpoint["signed_offset_error_m"][local_index].item()
                    ),
                    "orthogonal_residual_m": float(
                        endpoint["orthogonal_residual_m"][local_index].item()
                    ),
                    "position_residual_m": float(
                        endpoint["position_residual_m"][local_index].item()
                    ),
                    "orientation_residual_rad": float(
                        endpoint["orientation_residual_rad"][local_index].item()
                    ),
                    "root_displacement_m": float(root_displacement[local_index].item()),
                    "hinge_joint_delta": float(
                        self._a2_hold_oracle_offset_hinge_joint_delta[env_id].item()
                    ),
                    "handle_joint_delta": float(
                        self._a2_hold_oracle_offset_handle_joint_delta[env_id].item()
                    ),
                }
            )
            self._a2_hold_oracle_offset_preclamp_snapshot[env_id] = record
        converged = torch.zeros_like(snapshot_mask)
        converged[env_ids] = endpoint["converged"]
        return {"converged": converged}

    def _refresh_a2_offset_live_telemetry(self, refresh_mask: torch.Tensor) -> None:
        env_ids = torch.nonzero(refresh_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return
        frames = self._get_a2_hold_oracle_world_frames()
        try:
            metrics = a2_hold_offset_endpoint_metrics(
                frames["source_pos_w"][env_ids],
                frames["source_quat_w"][env_ids],
                self._a2_hold_oracle_offset_gate_source_pos_w[env_ids],
                self._a2_hold_oracle_offset_fixed_target_pos_w[env_ids],
                self._a2_hold_oracle_offset_fixed_target_quat_w[env_ids],
                self._a2_hold_oracle_offset_source_local_y_axis_w[env_ids],
                self._a2_hold_oracle_cfg["static_clamp_offset_m"],
                self._a2_hold_oracle_cfg[
                    "static_clamp_offset_position_tolerance_m"
                ],
                self._a2_hold_oracle_cfg[
                    "static_clamp_offset_orientation_tolerance_rad"
                ],
            )
        except ValueError as exc:
            raise RuntimeError(f"A2 offset live telemetry failed: {exc}") from exc
        field_map = {
            "achieved_signed_offset_m": self._a2_hold_oracle_offset_achieved_signed_offset_m,
            "signed_offset_error_m": self._a2_hold_oracle_offset_signed_offset_error_m,
            "orthogonal_residual_m": self._a2_hold_oracle_offset_orthogonal_residual_m,
            "position_residual_m": self._a2_hold_oracle_offset_position_residual_m,
            "orientation_residual_rad": self._a2_hold_oracle_offset_orientation_residual_rad,
        }
        for name, destination in field_map.items():
            destination[env_ids] = metrics[name]
        self._a2_hold_oracle_offset_root_displacement_m[env_ids] = torch.linalg.norm(
            frames["root_pos_w"][env_ids, :2]
            - self._a2_hold_oracle_offset_root_start_xy_w[env_ids],
            dim=-1,
        )
        door_joint_pos = self._get_door_joint_pos("A2 offset live telemetry", 2)
        self._a2_hold_oracle_offset_hinge_joint_delta[env_ids] = (
            door_joint_pos[env_ids, 0]
            - self._a2_hold_oracle_offset_hinge_joint_start[env_ids]
        )
        self._a2_hold_oracle_offset_handle_joint_delta[env_ids] = (
            door_joint_pos[env_ids, 1]
            - self._a2_hold_oracle_offset_handle_joint_start[env_ids]
        )

    def _finish_a2_offset_placement(self, affected_mask: torch.Tensor) -> None:
        if (
            not torch.is_tensor(affected_mask)
            or tuple(affected_mask.shape) != (self.num_envs,)
            or affected_mask.dtype != torch.bool
            or affected_mask.device != torch.device(self.device)
        ):
            raise RuntimeError("A2 offset placement finish mask contract mismatch.")
        affected = affected_mask
        if not torch.any(affected):
            return
        if torch.any(
            affected & ~self._a2_hold_oracle_offset_placement_ever_activated
        ) or torch.any(affected & self._a2_hold_oracle_static_clamp_gain_applied):
            raise RuntimeError("A2 offset placement finish state is inconsistent.")
        try:
            partition = a2_hold_offset_terminal_partition(
                affected,
                self._a2_hold_oracle_offset_placement_action_count,
                self._a2_hold_oracle_cfg["static_clamp_offset_placement_steps"],
            )
        except ValueError as exc:
            raise RuntimeError("A2 offset placement finish partition failed.") from exc
        endpoint = partition["endpoint_check"]
        endpoint_result = self._snapshot_a2_offset_placement_state(endpoint)
        converged = endpoint_result["converged"]
        self._a2_hold_oracle_offset_final_placement_action_count[affected] = (
            self._a2_hold_oracle_offset_placement_action_count[affected]
        )
        self._a2_hold_oracle_offset_endpoint_checked[endpoint] = True
        self._a2_hold_oracle_offset_placement_validated[converged] = True
        self._a2_hold_oracle_offset_placement_active[affected] = False
        self._a2_hold_oracle_offset_placement_action_count[affected] = 0
        self._set_a2_hold_outcome(
            partition["incomplete"], "PLACEMENT_INCOMPLETE"
        )
        self._set_a2_hold_outcome(
            endpoint & ~converged, "PLACEMENT_NOT_CONVERGED"
        )
        self._set_a2_hold_outcome(
            endpoint & converged, "OFFSET_PLACEMENT_COMPLETE_EPISODE_ENDED"
        )

    def _get_a2_static_clamp_gripper_state(self, env_ids: torch.Tensor):
        robot = self.simulator.scene.articulations["robot"]
        joint_ids = torch.tensor(
            self._a2_hold_oracle_gripper_joint_ids,
            device=self.device,
            dtype=torch.long,
        )
        if (
            not torch.is_tensor(env_ids)
            or env_ids.ndim != 1
            or env_ids.dtype != torch.long
            or env_ids.device != torch.device(self.device)
            or torch.any(env_ids < 0)
            or torch.any(env_ids >= self.num_envs)
        ):
            raise RuntimeError("A2 static clamp env ids must be valid device-local longs.")
        index = (env_ids[:, None], joint_ids[None, :])
        state = {
            "stiffness": robot.data.joint_stiffness[index].clone(),
            "damping": robot.data.joint_damping[index].clone(),
            "effort_limit": robot.data.joint_effort_limits[index].clone(),
        }
        if any(
            tuple(value.shape) != (env_ids.numel(), 2)
            or not torch.all(torch.isfinite(value))
            for value in state.values()
        ):
            raise RuntimeError("A2 static clamp gripper gain/effort state is invalid.")
        return robot, joint_ids, state

    def _apply_a2_static_clamp_gains(self, entering_mask: torch.Tensor) -> None:
        env_ids = torch.nonzero(entering_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return
        if torch.any(self._a2_hold_oracle_static_clamp_gain_applied[env_ids]) or torch.any(
            self._a2_hold_oracle_static_clamp_ever_activated[env_ids]
        ):
            raise RuntimeError("A2 static clamp gains may only be captured/applied once per env.")
        if torch.any(self._a2_hold_oracle_static_clamp_final_write_count[env_ids] != -1):
            raise RuntimeError("A2 static clamp final count must be unset before activation.")
        robot, joint_ids, original = self._get_a2_static_clamp_gripper_state(env_ids)
        expected_effort = torch.full_like(original["effort_limit"], 10.0)
        if not torch.equal(original["effort_limit"], expected_effort):
            raise RuntimeError(
                "A2 static clamp requires exact unchanged gripper effort_limit=10N; "
                f"got {original['effort_limit'].detach().cpu().tolist()}."
            )
        self._a2_hold_oracle_static_clamp_original_stiffness[env_ids] = original[
            "stiffness"
        ]
        self._a2_hold_oracle_static_clamp_original_damping[env_ids] = original["damping"]
        self._a2_hold_oracle_static_clamp_original_effort_limit[env_ids] = original[
            "effort_limit"
        ]
        self._a2_hold_oracle_static_clamp_gain_applied[env_ids] = True
        self._a2_hold_oracle_static_clamp_ever_activated[env_ids] = True
        self._a2_hold_oracle_static_clamp_restored[env_ids] = False
        target_stiffness = torch.full_like(
            original["stiffness"], self._a2_hold_oracle_cfg["static_clamp_stiffness"]
        )
        target_damping = torch.full_like(
            original["damping"], self._a2_hold_oracle_cfg["static_clamp_damping"]
        )
        self._a2_hold_oracle_static_clamp_requested_stiffness[env_ids] = (
            target_stiffness
        )
        self._a2_hold_oracle_static_clamp_requested_damping[env_ids] = target_damping
        robot.write_joint_stiffness_to_sim(
            target_stiffness, joint_ids=joint_ids, env_ids=env_ids
        )
        robot.write_joint_damping_to_sim(
            target_damping, joint_ids=joint_ids, env_ids=env_ids
        )
        _, _, written = self._get_a2_static_clamp_gripper_state(env_ids)
        if (
            not torch.equal(written["stiffness"], target_stiffness)
            or not torch.equal(written["damping"], target_damping)
            or not torch.equal(written["effort_limit"], original["effort_limit"])
        ):
            raise RuntimeError("A2 static clamp gain write or effort invariant verification failed.")
        self._a2_hold_oracle_static_clamp_applied_stiffness[env_ids] = written[
            "stiffness"
        ]
        self._a2_hold_oracle_static_clamp_applied_damping[env_ids] = written[
            "damping"
        ]
        self._a2_hold_oracle_static_clamp_applied_effort_limit[env_ids] = written[
            "effort_limit"
        ]

    def _restore_a2_static_clamp_gains(self, requested_mask: torch.Tensor) -> None:
        if (
            not torch.is_tensor(requested_mask)
            or tuple(requested_mask.shape) != (self.num_envs,)
            or requested_mask.dtype != torch.bool
            or requested_mask.device != torch.device(self.device)
        ):
            raise RuntimeError("A2 static clamp restore mask contract mismatch.")
        restore_mask = requested_mask & self._a2_hold_oracle_static_clamp_gain_applied
        env_ids = torch.nonzero(restore_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return
        original_stiffness = self._a2_hold_oracle_static_clamp_original_stiffness[
            env_ids
        ]
        original_damping = self._a2_hold_oracle_static_clamp_original_damping[env_ids]
        original_effort = self._a2_hold_oracle_static_clamp_original_effort_limit[
            env_ids
        ]
        if not all(
            torch.all(torch.isfinite(value))
            for value in (original_stiffness, original_damping, original_effort)
        ):
            raise RuntimeError("A2 static clamp cannot restore a non-finite original snapshot.")
        robot, joint_ids, current = self._get_a2_static_clamp_gripper_state(env_ids)
        if not torch.equal(current["effort_limit"], original_effort):
            raise RuntimeError("A2 static clamp effort limit changed before restore.")
        robot.write_joint_stiffness_to_sim(
            original_stiffness, joint_ids=joint_ids, env_ids=env_ids
        )
        robot.write_joint_damping_to_sim(
            original_damping, joint_ids=joint_ids, env_ids=env_ids
        )
        _, _, restored = self._get_a2_static_clamp_gripper_state(env_ids)
        if (
            not torch.equal(restored["stiffness"], original_stiffness)
            or not torch.equal(restored["damping"], original_damping)
            or not torch.equal(restored["effort_limit"], original_effort)
        ):
            raise RuntimeError("A2 static clamp exact gain restore verification failed.")
        self._a2_hold_oracle_static_clamp_restored_stiffness[env_ids] = restored[
            "stiffness"
        ]
        self._a2_hold_oracle_static_clamp_restored_damping[env_ids] = restored[
            "damping"
        ]
        self._a2_hold_oracle_static_clamp_restored_effort_limit[env_ids] = restored[
            "effort_limit"
        ]
        self._a2_hold_oracle_static_clamp_gain_applied[env_ids] = False
        self._a2_hold_oracle_static_clamp_active[env_ids] = False
        self._a2_hold_oracle_static_clamp_restored[env_ids] = True
        self._a2_hold_oracle_static_clamp_write_count[env_ids] = 0

    def _snapshot_a2_static_clamp_result(self, snapshot_mask: torch.Tensor) -> None:
        env_ids = torch.nonzero(snapshot_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return
        details = self._get_a2_hold_detailed_step_fields(env_ids)
        if len(details) != env_ids.numel():
            raise RuntimeError("A2 static clamp step-40 snapshot record count mismatch.")
        for env_id, detail in zip(env_ids.tolist(), details, strict=True):
            if self._a2_hold_oracle_static_clamp_step40_snapshot[env_id] is not None:
                raise RuntimeError("A2 static clamp step-40 result cannot be captured twice.")
            self._a2_hold_oracle_static_clamp_step40_snapshot[env_id] = detail

    def _finish_a2_static_clamp(self, affected_mask: torch.Tensor) -> None:
        cfg = self._a2_hold_oracle_cfg
        if not cfg["enabled"] or not cfg["static_clamp_enabled"]:
            raise RuntimeError("A2 static clamp finish requires the enabled static probe.")
        if (
            not torch.is_tensor(affected_mask)
            or tuple(affected_mask.shape) != (self.num_envs,)
            or affected_mask.dtype != torch.bool
            or affected_mask.device != torch.device(self.device)
        ):
            raise RuntimeError("A2 static clamp finish mask contract mismatch.")
        if torch.any(affected_mask & ~self._a2_hold_oracle_static_clamp_gain_applied):
            raise RuntimeError("A2 static clamp cannot finish without applied gains.")
        if not torch.any(affected_mask):
            return
        try:
            try:
                partition = a2_hold_static_clamp_terminal_partition(
                    affected_mask,
                    self._a2_hold_oracle_static_clamp_write_count,
                    cfg["static_clamp_steps"],
                )
            except ValueError as exc:
                raise RuntimeError(
                    f"A2 static clamp finish partition failed: {exc}"
                ) from exc
            self._a2_hold_oracle_static_clamp_final_write_count[affected_mask] = (
                self._a2_hold_oracle_static_clamp_write_count[affected_mask]
            )
            self._set_a2_hold_outcome(
                partition["complete"], "STATIC_CLAMP_COMPLETE"
            )
            self._set_a2_hold_outcome(
                partition["incomplete"], "STATIC_CLAMP_INCOMPLETE"
            )
            self._snapshot_a2_static_clamp_result(partition["complete"])
        finally:
            self._restore_a2_static_clamp_gains(affected_mask)

    def finalize_a2_eval_hold_oracle(self) -> None:
        cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if cfg is None or not cfg["enabled"]:
            return
        if self._a2_hold_oracle_finalized:
            if torch.any(self._a2_hold_oracle_static_clamp_gain_applied) or torch.any(
                self._a2_hold_oracle_static_clamp_active
            ) or torch.any(self._a2_hold_oracle_offset_placement_active) or torch.any(
                self._a2_hold_oracle_open_stabilization_active
            ) or torch.any(self._a2_hold_oracle_matched_clean_release_active) or torch.any(
                self._a2_hold_oracle_matched_clean_stabilize_active
            ):
                raise RuntimeError("Finalized A2 hold oracle retained active diagnostic state.")
            return
        if cfg.get("matched_clean_reacquisition_preflight_enabled", False):
            self._finish_a2_matched_clean_reacquisition(
                self._a2_hold_oracle_matched_clean_release_active.clone()
                | self._a2_hold_oracle_matched_clean_stabilize_active.clone()
            )
            self._a2_hold_oracle_finalized = True
            return
        if cfg["open_stabilization_preflight_enabled"]:
            self._finish_a2_open_stabilization(
                self._a2_hold_oracle_open_stabilization_active.clone()
            )
        if cfg["static_clamp_offset_probe_enabled"]:
            self._finish_a2_offset_placement(
                self._a2_hold_oracle_offset_placement_active.clone()
            )
        if cfg["static_clamp_enabled"]:
            self._finish_a2_static_clamp(
                self._a2_hold_oracle_static_clamp_gain_applied.clone()
            )
        self._a2_hold_oracle_finalized = True

    def _clear_a2_hold_base_relief_state(self, clear_mask: torch.Tensor) -> None:
        cleared = a2_hold_clear_base_relief_state(
            clear_mask,
            self._a2_hold_oracle_base_relief_active,
            self._a2_hold_oracle_base_relief_branch_applied,
            self._a2_hold_oracle_base_relief_steps,
            self._a2_hold_oracle_base_relief_initial_horizontal_residual,
            self._a2_hold_oracle_base_relief_current_horizontal_residual,
            self._a2_hold_oracle_base_relief_start_root_xy,
            self._a2_hold_oracle_base_relief_body_velocity_command,
            self._a2_hold_oracle_base_relief_raw_command,
        )
        self._a2_hold_oracle_base_relief_active[:] = cleared["active"]
        self._a2_hold_oracle_base_relief_branch_applied[:] = cleared[
            "branch_applied"
        ]
        self._a2_hold_oracle_base_relief_steps[:] = cleared["steps"]
        self._a2_hold_oracle_base_relief_initial_horizontal_residual[:] = cleared[
            "initial_residual"
        ]
        self._a2_hold_oracle_base_relief_current_horizontal_residual[:] = cleared[
            "current_residual"
        ]
        self._a2_hold_oracle_base_relief_start_root_xy[:] = cleared["start_root_xy"]
        self._a2_hold_oracle_base_relief_body_velocity_command[:] = cleared[
            "body_velocity_command"
        ]
        self._a2_hold_oracle_base_relief_raw_command[:] = cleared["raw_command"]

    def _a2_hold_bilateral_gate(self):
        masks = self._get_a2_stage2_grasp_completion_masks()
        return (
            masks["contact_stability"]
            & masks["squeeze_window_current"]
            & ~masks["over_force_current"]
        ), masks

    def _get_a2_hold_oracle_world_frames(self):
        robot = self.simulator.scene.articulations["robot"]
        data = robot.data
        body_id = self._a2_hold_oracle_body_id
        root_pos_w = data.root_pos_w
        root_quat_w = data.root_quat_w
        body_pos_w = data.body_pos_w[:, body_id]
        body_quat_w = data.body_quat_w[:, body_id]
        source_offset = torch.tensor(
            (0.0, 0.0, self._a2_hold_oracle_cfg["tcp_offset_z"]),
            device=self.device,
            dtype=body_pos_w.dtype,
        ).repeat(self.num_envs, 1)
        identity_quat = torch.zeros(
            self.num_envs, 4, device=self.device, dtype=body_quat_w.dtype
        )
        identity_quat[:, 0] = 1.0
        source_pos_w, source_quat_w = combine_frame_transforms(
            body_pos_w, body_quat_w, source_offset, identity_quat
        )
        transform = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_w = getattr(transform, "target_pos_w", None)
        target_quat_w = getattr(transform, "target_quat_w", None)
        expected_target_pos_shape = (self.num_envs, 2, 3)
        expected_target_quat_shape = (self.num_envs, 2, 4)
        if self._a2_hold_oracle_cfg["matched_clean_reacquisition_preflight_enabled"]:
            for name, value, expected_shape in (
                ("target_pos_w", target_pos_w, expected_target_pos_shape),
                ("target_quat_w", target_quat_w, expected_target_quat_shape),
            ):
                if (
                    not torch.is_tensor(value)
                    or tuple(value.shape) != expected_shape
                    or value.device != torch.device(self.device)
                    or not value.is_floating_point()
                    or value.dtype != root_pos_w.dtype
                    or not torch.all(torch.isfinite(value))
                ):
                    shape = None if not torch.is_tensor(value) else tuple(value.shape)
                    raise RuntimeError(
                        "A2 matched-clean live OrderedTargetFrameTransformer requires "
                        f"finite {name} shape {expected_shape} on {self.device}; got {shape}."
                    )
        handle_pos_w = target_pos_w[:, 0]
        handle_quat_w = target_quat_w[:, 0]
        if self._a2_hold_oracle_cfg["matched_clean_reacquisition_preflight_enabled"]:
            pregrasp_pos_w = target_pos_w[:, 1, :]
            pregrasp_quat_w = target_quat_w[:, 1, :]
        else:
            pregrasp_pos_w = handle_pos_w
            pregrasp_quat_w = handle_quat_w
        return {
            "robot": robot,
            "root_pos_w": root_pos_w,
            "root_quat_w": root_quat_w,
            "body_pos_w": body_pos_w,
            "body_quat_w": body_quat_w,
            "source_pos_w": source_pos_w,
            "source_quat_w": source_quat_w,
            "handle_pos_w": handle_pos_w,
            "handle_quat_w": handle_quat_w,
            "pregrasp_pos_w": pregrasp_pos_w,
            "pregrasp_quat_w": pregrasp_quat_w,
        }

    def _get_a2_open_stabilization_contact_force_norm(self) -> torch.Tensor:
        sensor = self.simulator.scene.sensors[
            self.A2_GRIPPER_HANDLE_CONTACT_SENSOR
        ]
        expected_filters = [
            "/World/envs/env_.*/Robot/arm_body7",
            "/World/envs/env_.*/Robot/arm_body8",
        ]
        if list(sensor.cfg.filter_prim_paths_expr) != expected_filters:
            raise RuntimeError(
                "A2 open stabilization filter pair order mismatch: "
                f"expected={expected_filters}, got={list(sensor.cfg.filter_prim_paths_expr)}."
            )
        force = getattr(sensor.data, "force_matrix_w", None)
        expected_shape = (self.num_envs, 1, 2, 3)
        if (
            not torch.is_tensor(force)
            or tuple(force.shape) != expected_shape
            or not force.is_floating_point()
            or force.device != torch.device(self.device)
            or not torch.all(torch.isfinite(force))
        ):
            shape = None if not torch.is_tensor(force) else tuple(force.shape)
            raise RuntimeError(
                "A2 open stabilization requires finite handle-filter force_matrix_w "
                f"shape {expected_shape} on {self.device}; got {shape}."
            )
        return torch.linalg.norm(force[:, 0], dim=-1)

    def _get_a2_open_stabilization_composite_gate(self) -> torch.Tensor:
        gate = (self.stage_buf == self.STAGE_GRASP) & self._get_a2_stage2_close_reward_gate()
        if (
            not torch.is_tensor(gate)
            or tuple(gate.shape) != (self.num_envs,)
            or gate.dtype != torch.bool
            or gate.device != torch.device(self.device)
        ):
            raise RuntimeError("A2 open stabilization composite gate contract mismatch.")
        return gate

    def _capture_a2_open_stabilization_gate(self, capture_mask: torch.Tensor) -> None:
        env_ids = torch.nonzero(capture_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return
        if torch.any(self._a2_hold_oracle_open_stabilization_ever_activated[env_ids]):
            raise RuntimeError("A2 open stabilization gate may only be captured once per env.")
        if (
            not torch.is_tensor(self._delta_actions)
            or tuple(self._delta_actions.shape) != (self.num_envs, 6)
            or not torch.all(torch.isfinite(self._delta_actions))
        ):
            raise RuntimeError(
                "A2 open stabilization requires finite accumulated arm target shape (N,6)."
            )
        frames = self._get_a2_hold_oracle_world_frames()
        for name, expected_shape in (
            ("root_pos_w", (self.num_envs, 3)),
            ("root_quat_w", (self.num_envs, 4)),
            ("source_pos_w", (self.num_envs, 3)),
            ("source_quat_w", (self.num_envs, 4)),
            ("handle_pos_w", (self.num_envs, 3)),
            ("handle_quat_w", (self.num_envs, 4)),
        ):
            value = frames[name]
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != expected_shape
                or value.device != torch.device(self.device)
                or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(
                    f"A2 open stabilization gate requires finite {name} shape {expected_shape}."
                )
        _, _, gripper = self._get_a2_static_clamp_gripper_state(env_ids)
        expected_stiffness = torch.full_like(gripper["stiffness"], 80.0)
        expected_damping = torch.full_like(gripper["damping"], 3.0)
        expected_effort = torch.full_like(gripper["effort_limit"], 10.0)
        if (
            not torch.equal(gripper["stiffness"], expected_stiffness)
            or not torch.equal(gripper["damping"], expected_damping)
            or not torch.equal(gripper["effort_limit"], expected_effort)
        ):
            raise RuntimeError(
                "A2 open stabilization requires actual gripper Kp/Kd/effort=80/3/10 at gate."
            )
        self._a2_hold_oracle_open_stabilization_gate_root_pos_w[env_ids] = frames[
            "root_pos_w"
        ][env_ids]
        self._a2_hold_oracle_open_stabilization_gate_root_quat_w[env_ids] = frames[
            "root_quat_w"
        ][env_ids]
        self._a2_hold_oracle_open_stabilization_gate_source_pos_w[env_ids] = frames[
            "source_pos_w"
        ][env_ids]
        self._a2_hold_oracle_open_stabilization_gate_source_quat_w[env_ids] = frames[
            "source_quat_w"
        ][env_ids]
        self._a2_hold_oracle_open_stabilization_gate_handle_pos_w[env_ids] = frames[
            "handle_pos_w"
        ][env_ids]
        self._a2_hold_oracle_open_stabilization_gate_handle_quat_w[env_ids] = frames[
            "handle_quat_w"
        ][env_ids]
        self._a2_hold_oracle_open_stabilization_arm_target_capture[env_ids] = (
            self._delta_actions[env_ids]
        )
        self._a2_hold_oracle_open_stabilization_gate_captured[env_ids] = True
        self._a2_hold_oracle_open_stabilization_ever_activated[env_ids] = True
        self._a2_hold_oracle_open_stabilization_active[env_ids] = True

    def _capture_a2_open_stabilization_post_action_samples(self) -> None:
        cfg = self._a2_hold_oracle_cfg
        sample_mask = (
            self._a2_hold_oracle_open_stabilization_active
            & self._a2_hold_oracle_last_override_mask
        )
        env_ids = torch.nonzero(sample_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return
        counts = self._a2_hold_oracle_open_stabilization_action_count[env_ids]
        if torch.any(counts < 1) or torch.any(
            counts > cfg["open_stabilization_steps"]
        ):
            raise RuntimeError("A2 open stabilization sample count is outside actions 1..40.")
        post_delta = getattr(self, "_a2_eval_post_delta_post_warp_env_action", None)
        if (
            not torch.is_tensor(post_delta)
            or tuple(post_delta.shape) != (self.num_envs, 12)
            or post_delta.device != torch.device(self.device)
            or not torch.all(torch.isfinite(post_delta))
        ):
            raise RuntimeError(
                "A2 open stabilization requires finite post-delta authoritative action shape (N,12)."
            )
        frames = self._get_a2_hold_oracle_world_frames()
        pose_shapes = {
            "root_pos_w": (self.num_envs, 3),
            "root_quat_w": (self.num_envs, 4),
            "source_pos_w": (self.num_envs, 3),
            "source_quat_w": (self.num_envs, 4),
            "handle_pos_w": (self.num_envs, 3),
            "handle_quat_w": (self.num_envs, 4),
        }
        for name, expected_shape in pose_shapes.items():
            value = frames[name]
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != expected_shape
                or value.device != torch.device(self.device)
                or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(
                    f"A2 open stabilization sample requires finite {name} shape {expected_shape}."
                )
        robot_data = frames["robot"].data
        for name, value in (
            ("root_lin_vel_w", robot_data.root_lin_vel_w),
            ("root_ang_vel_w", robot_data.root_ang_vel_w),
        ):
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != (self.num_envs, 3)
                or value.device != torch.device(self.device)
                or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(
                    f"A2 open stabilization sample requires finite {name} shape (N,3)."
                )
        if (
            not torch.is_tensor(self._delta_actions)
            or tuple(self._delta_actions.shape) != (self.num_envs, 6)
            or not torch.all(torch.isfinite(self._delta_actions))
        ):
            raise RuntimeError(
                "A2 open stabilization sample requires finite accumulated arm target shape (N,6)."
            )
        source_pos_root, source_quat_root = subtract_frame_transforms(
            frames["root_pos_w"],
            frames["root_quat_w"],
            frames["source_pos_w"],
            frames["source_quat_w"],
        )
        frozen_pos_root, frozen_quat_root = subtract_frame_transforms(
            frames["root_pos_w"],
            frames["root_quat_w"],
            self._a2_hold_oracle_open_stabilization_gate_source_pos_w,
            self._a2_hold_oracle_open_stabilization_gate_source_quat_w,
        )
        contact = self._get_a2_open_stabilization_contact_force_norm()
        gate = self._get_a2_open_stabilization_composite_gate()
        _, _, gripper = self._get_a2_static_clamp_gripper_state(env_ids)
        try:
            invariant = a2_hold_validate_open_stabilization_runtime_invariants(
                self._a2_hold_oracle_open_stabilization_arm_target_capture[
                    env_ids
                ],
                self._delta_actions[env_ids],
                post_delta[env_ids, 5:11],
                gripper["stiffness"],
                gripper["damping"],
                gripper["effort_limit"],
            )
        except ValueError as exc:
            raise RuntimeError(
                "A2 open stabilization post-action runtime invariant failed for "
                f"envs={env_ids.detach().cpu().tolist()}, "
                f"actions={counts.detach().cpu().tolist()}: {exc}"
            ) from exc
        applied_action = self._a2_hold_oracle_post_override_action
        if (
            not torch.is_tensor(applied_action)
            or tuple(applied_action.shape) != (self.num_envs, 12)
            or applied_action.device != torch.device(self.device)
            or not torch.all(torch.isfinite(applied_action))
        ):
            raise RuntimeError("A2 open stabilization applied-action telemetry is invalid.")
        for local, env_id in enumerate(env_ids.tolist()):
            action_number = int(counts[local].item())
            samples = self._a2_hold_oracle_open_stabilization_samples[env_id]
            if len(samples) != action_number - 1:
                raise RuntimeError(
                    "A2 open stabilization requires one pre-reset sample per action; "
                    f"env={env_id}, action={action_number}, existing={len(samples)}."
                )
            samples.append(
                {
                    "action": action_number,
                    "root_pos_w": frames["root_pos_w"][env_id].detach().cpu().tolist(),
                    "root_quat_w": frames["root_quat_w"][env_id].detach().cpu().tolist(),
                    "root_linear_speed_mps": float(
                        torch.linalg.norm(robot_data.root_lin_vel_w[env_id]).item()
                    ),
                    "root_angular_speed_radps": float(
                        torch.linalg.norm(robot_data.root_ang_vel_w[env_id]).item()
                    ),
                    "frozen_gate_source_pos_root": frozen_pos_root[env_id].detach().cpu().tolist(),
                    "frozen_gate_source_quat_root": frozen_quat_root[env_id].detach().cpu().tolist(),
                    "source_pos_root": source_pos_root[env_id].detach().cpu().tolist(),
                    "source_quat_root": source_quat_root[env_id].detach().cpu().tolist(),
                    "handle_pos_w": frames["handle_pos_w"][env_id].detach().cpu().tolist(),
                    "handle_quat_w": frames["handle_quat_w"][env_id].detach().cpu().tolist(),
                    "handle_filter_force_norm_body7_body8": contact[env_id].detach().cpu().tolist(),
                    "composite_gate": bool(gate[env_id].item()),
                    "gripper_stiffness": gripper["stiffness"][local].detach().cpu().tolist(),
                    "gripper_damping": gripper["damping"][local].detach().cpu().tolist(),
                    "gripper_effort_limit": gripper["effort_limit"][local].detach().cpu().tolist(),
                    "accumulated_arm_target": self._delta_actions[env_id].detach().cpu().tolist(),
                    "captured_accumulated_arm_target": self._a2_hold_oracle_open_stabilization_arm_target_capture[
                        env_id
                    ].detach().cpu().tolist(),
                    "post_delta_arm_target": post_delta[env_id, 5:11].detach().cpu().tolist(),
                    "accumulated_arm_target_invariant": bool(
                        invariant["accumulated_arm_target_invariant"][local].item()
                    ),
                    "post_delta_arm_target_invariant": bool(
                        invariant["post_delta_arm_target_invariant"][local].item()
                    ),
                    "runtime_gripper_gain_effort_exact": bool(
                        invariant["runtime_gripper_gain_effort_exact"][local].item()
                    ),
                    "applied_high_level_action": applied_action[env_id].detach().cpu().tolist(),
                    "control_branch": "ARM0_OPEN_STABILIZATION",
                }
            )

    def _evaluate_a2_open_stabilization_quiet_window(self, env_id: int) -> dict:
        cfg = self._a2_hold_oracle_cfg
        samples = self._a2_hold_oracle_open_stabilization_samples[env_id]
        target_steps = cfg["open_stabilization_steps"]
        quiet_steps = cfg["open_stabilization_quiet_window_steps"]
        quiet = samples[-quiet_steps:]
        pose_window = samples[-(quiet_steps + 1) :]
        if (
            len(samples) != target_steps
            or [sample["action"] for sample in quiet]
            != list(range(target_steps - quiet_steps + 1, target_steps + 1))
            or [sample["action"] for sample in pose_window]
            != list(range(target_steps - quiet_steps, target_steps + 1))
        ):
            raise RuntimeError(
                "A2 open stabilization READY evaluation requires instantaneous samples36..40 "
                "and pose samples35..40."
            )
        pose_fields = {
            "root_world": ("root_pos_w", "root_quat_w"),
            "frozen_gate_source_in_current_root": (
                "frozen_gate_source_pos_root",
                "frozen_gate_source_quat_root",
            ),
            "source_in_current_root": ("source_pos_root", "source_quat_root"),
            "handle_world": ("handle_pos_w", "handle_quat_w"),
        }
        pose_metrics = {}
        pose_ok = True
        for label, (position_key, quaternion_key) in pose_fields.items():
            position = torch.tensor(
                [[sample[position_key]] for sample in pose_window],
                device=self.device,
                dtype=self._a2_hold_oracle_open_stabilization_gate_root_pos_w.dtype,
            )
            quaternion = torch.tensor(
                [[sample[quaternion_key]] for sample in pose_window],
                device=self.device,
                dtype=self._a2_hold_oracle_open_stabilization_gate_root_quat_w.dtype,
            )
            try:
                metrics = a2_hold_pose_motion_metrics(position, quaternion)
            except ValueError as exc:
                raise RuntimeError(
                    f"A2 open stabilization {label} quiet-window pose math failed: {exc}"
                ) from exc
            json_metrics = {name: float(value.item()) for name, value in metrics.items()}
            json_metrics["within_threshold"] = (
                json_metrics["per_call_translation_max"]
                <= cfg["open_stabilization_pose_per_call_translation_max_m"]
                and json_metrics["per_call_rotation_max"]
                <= cfg["open_stabilization_pose_per_call_rotation_max_rad"]
                and json_metrics["window_translation"]
                <= cfg["open_stabilization_pose_window_translation_max_m"]
                and json_metrics["window_rotation"]
                <= cfg["open_stabilization_pose_window_rotation_max_rad"]
            )
            pose_ok = pose_ok and json_metrics["within_threshold"]
            pose_metrics[label] = json_metrics
        max_root_linear_speed = max(sample["root_linear_speed_mps"] for sample in quiet)
        max_root_angular_speed = max(sample["root_angular_speed_radps"] for sample in quiet)
        max_contact = max(
            max(sample["handle_filter_force_norm_body7_body8"]) for sample in quiet
        )
        reasons = {
            "root_linear_speed_ok": max_root_linear_speed
            <= cfg["open_stabilization_root_linear_speed_max_mps"],
            "root_angular_speed_ok": max_root_angular_speed
            <= cfg["open_stabilization_root_angular_speed_max_radps"],
            "pose_motion_ok": pose_ok,
            "contact_force_ok": max_contact
            < cfg["open_stabilization_contact_force_max_n"],
            "composite_gate_ok": all(sample["composite_gate"] for sample in quiet),
        }
        return {
            "ready": all(reasons.values()),
            "reason_booleans": reasons,
            "max_root_linear_speed_mps": max_root_linear_speed,
            "max_root_angular_speed_radps": max_root_angular_speed,
            "max_handle_filter_contact_force_n": max_contact,
            "pose_motion": pose_metrics,
            "quiet_window_actions": [sample["action"] for sample in quiet],
            "pose_window_actions": [sample["action"] for sample in pose_window],
            "pose_transition_actions": [
                [pose_window[index]["action"], pose_window[index + 1]["action"]]
                for index in range(len(pose_window) - 1)
            ],
            "quiet_window_samples": quiet,
            "pose_window_samples": pose_window,
        }

    def _finish_a2_open_stabilization(self, affected_mask: torch.Tensor) -> None:
        cfg = self._a2_hold_oracle_cfg
        if not cfg["enabled"] or not cfg["open_stabilization_preflight_enabled"]:
            raise RuntimeError("A2 open stabilization finish requires the enabled preflight.")
        if (
            not torch.is_tensor(affected_mask)
            or tuple(affected_mask.shape) != (self.num_envs,)
            or affected_mask.dtype != torch.bool
            or affected_mask.device != torch.device(self.device)
        ):
            raise RuntimeError("A2 open stabilization finish mask contract mismatch.")
        affected = affected_mask & self._a2_hold_oracle_open_stabilization_active
        if not torch.any(affected):
            return
        contact = self._get_a2_open_stabilization_contact_force_norm()
        gate = self._get_a2_open_stabilization_composite_gate()
        threshold = cfg["open_stabilization_contact_force_max_n"]
        try:
            partition = a2_hold_open_stabilization_terminal_partition(
                affected,
                self._a2_hold_oracle_open_stabilization_action_count,
                torch.any(contact >= threshold, dim=-1),
                gate,
                cfg["open_stabilization_steps"],
            )
        except ValueError as exc:
            raise RuntimeError(
                f"A2 open stabilization finish partition failed: {exc}"
            ) from exc
        for env_id in torch.nonzero(affected, as_tuple=False).flatten().tolist():
            count = int(
                self._a2_hold_oracle_open_stabilization_action_count[env_id].item()
            )
            if count < 0 or count > cfg["open_stabilization_steps"]:
                raise RuntimeError("A2 open stabilization final count is outside 0..40.")
            if len(self._a2_hold_oracle_open_stabilization_samples[env_id]) != count:
                raise RuntimeError(
                    "A2 open stabilization cannot finish without one pre-reset sample per action."
                )
            one = torch.zeros(self.num_envs, device=self.device, dtype=torch.bool)
            one[env_id] = True
            if partition["contact_contaminated"][env_id].item():
                outcome = "STABILIZATION_CONTACT_CONTAMINATED"
                self._a2_hold_oracle_open_stabilization_reason_contact[env_id] = True
                result = {
                    "ready": False,
                    "reason_booleans": {"contact_force_ok": False},
                    "final_handle_filter_force_norm_body7_body8": contact[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                }
            elif partition["gate_lost"][env_id].item():
                outcome = "STABILIZATION_GATE_LOST"
                self._a2_hold_oracle_open_stabilization_reason_gate[env_id] = True
                result = {"ready": False, "reason_booleans": {"composite_gate_ok": False}}
            elif partition["endpoint"][env_id].item():
                result = self._evaluate_a2_open_stabilization_quiet_window(env_id)
                if result["ready"]:
                    outcome = "STABILIZATION_READY"
                    self._a2_hold_oracle_open_stabilization_reason_ready[env_id] = True
                else:
                    outcome = "STABILIZATION_NOT_SETTLED"
                    self._a2_hold_oracle_open_stabilization_reason_not_settled[
                        env_id
                    ] = True
            elif partition["incomplete"][env_id].item():
                outcome = "STABILIZATION_INCOMPLETE"
                self._a2_hold_oracle_open_stabilization_reason_incomplete[env_id] = True
                result = {
                    "ready": False,
                    "reason_booleans": {"exact_40_actions_complete": False},
                }
            else:
                raise RuntimeError("A2 open stabilization terminal partition was not exhaustive.")
            result["final_action_count"] = count
            result["outcome"] = outcome
            self._a2_hold_oracle_open_stabilization_result[env_id] = result
            self._a2_hold_oracle_open_stabilization_final_action_count[env_id] = count
            self._a2_hold_oracle_open_stabilization_active[env_id] = False
            self._set_a2_hold_outcome(one, outcome)

    def _apply_a2_open_stabilization_action(
        self,
        policy_action: torch.Tensor,
        first_episode_active_mask: torch.Tensor,
        activate: torch.Tensor,
    ):
        cfg = self._a2_hold_oracle_cfg
        contact = self._get_a2_open_stabilization_contact_force_norm()
        gate = self._get_a2_open_stabilization_composite_gate()
        active = self._a2_hold_oracle_open_stabilization_active
        finish = active & (
            torch.any(
                contact >= cfg["open_stabilization_contact_force_max_n"], dim=-1
            )
            | ~gate
            | ~first_episode_active_mask
            | (
                self._a2_hold_oracle_open_stabilization_action_count
                >= cfg["open_stabilization_steps"]
            )
        )
        self._finish_a2_open_stabilization(finish)

        entering_contact = activate & torch.any(
            contact >= cfg["open_stabilization_contact_force_max_n"], dim=-1
        )
        if torch.any(entering_contact):
            self._a2_hold_oracle_open_stabilization_ever_activated[
                entering_contact
            ] = True
            self._a2_hold_oracle_open_stabilization_final_action_count[
                entering_contact
            ] = 0
            self._a2_hold_oracle_open_stabilization_reason_contact[
                entering_contact
            ] = True
            for env_id in torch.nonzero(
                entering_contact, as_tuple=False
            ).flatten().tolist():
                self._a2_hold_oracle_open_stabilization_result[env_id] = {
                    "ready": False,
                    "outcome": "STABILIZATION_CONTACT_CONTAMINATED",
                    "final_action_count": 0,
                    "reason_booleans": {"contact_force_ok": False},
                    "final_handle_filter_force_norm_body7_body8": contact[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                }
            self._set_a2_hold_outcome(
                entering_contact, "STABILIZATION_CONTACT_CONTAMINATED"
            )
        clean_entering = activate & ~entering_contact
        self._capture_a2_open_stabilization_gate(clean_entering)

        override = (
            self._a2_hold_oracle_open_stabilization_active
            & first_episode_active_mask
            & (
                self._a2_hold_oracle_outcome
                == A2_HOLD_OUTCOME_TO_ID["PENDING"]
            )
        )
        if torch.any(
            self._a2_hold_oracle_open_stabilization_action_count[override]
            >= cfg["open_stabilization_steps"]
        ):
            raise RuntimeError("A2 open stabilization refused action 41.")
        if torch.any(
            self._delta_actions[override]
            != self._a2_hold_oracle_open_stabilization_arm_target_capture[override]
        ):
            raise RuntimeError(
                "A2 open stabilization accumulated arm target changed before action write."
            )
        self._a2_hold_oracle_open_stabilization_action_count[override] += 1
        self._a2_hold_oracle_phase_step[override] = (
            self._a2_hold_oracle_open_stabilization_action_count[override]
        )
        try:
            action = a2_hold_open_stabilization_action(policy_action, override)
        except ValueError as exc:
            raise RuntimeError(f"A2 open stabilization action failed: {exc}") from exc
        self._a2_hold_oracle_a_raw.zero_()
        self._a2_hold_oracle_offset_placement_branch.zero_()
        self._a2_hold_oracle_arm_dls_branch.zero_()
        self._a2_hold_oracle_base_relief_branch_applied.zero_()
        self._a2_hold_oracle_phase_sign_check_due.zero_()
        self._a2_hold_oracle_last_override_mask = override.clone()
        self._a2_hold_oracle_post_override_action = action.detach().clone()
        return action, override

    def _get_a2_matched_clean_reacquisition_pose_state(self):
        frames = self._get_a2_hold_oracle_world_frames()
        source_pos_root, source_quat_root = subtract_frame_transforms(
            frames["root_pos_w"],
            frames["root_quat_w"],
            frames["source_pos_w"],
            frames["source_quat_w"],
        )
        target_pos_root, target_quat_root = subtract_frame_transforms(
            frames["root_pos_w"],
            frames["root_quat_w"],
            frames["pregrasp_pos_w"],
            frames["pregrasp_quat_w"],
        )
        for name, value, expected_shape in (
            ("source_pos_root", source_pos_root, (self.num_envs, 3)),
            ("source_quat_root", source_quat_root, (self.num_envs, 4)),
            ("target_pos_root", target_pos_root, (self.num_envs, 3)),
            ("target_quat_root", target_quat_root, (self.num_envs, 4)),
        ):
            if (
                tuple(value.shape) != expected_shape
                or value.device != torch.device(self.device)
                or not value.is_floating_point()
                or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(
                    "A2 matched-clean release pose state requires finite "
                    f"{name} shape {expected_shape} on {self.device}."
                )
        source_norm = torch.linalg.norm(source_quat_root, dim=-1)
        target_norm = torch.linalg.norm(target_quat_root, dim=-1)
        if not torch.allclose(source_norm, torch.ones_like(source_norm), atol=1.0e-5, rtol=0.0):
            raise RuntimeError("A2 matched-clean release source quaternion is not unit length.")
        if not torch.allclose(target_norm, torch.ones_like(target_norm), atol=1.0e-5, rtol=0.0):
            raise RuntimeError("A2 matched-clean release pregrasp quaternion is not unit length.")
        quat_error = quat_mul(target_quat_root, quat_inv(source_quat_root))
        return {
            "frames": frames,
            "source_pos_root": source_pos_root,
            "source_quat_root": source_quat_root,
            "target_pos_root": target_pos_root,
            "target_quat_root": target_quat_root,
            "position_residual": torch.linalg.norm(
                target_pos_root - source_pos_root, dim=-1
            ),
            "orientation_residual": torch.linalg.norm(
                axis_angle_from_quat(quat_error), dim=-1
            ),
            "source_handle_distance": torch.linalg.norm(
                frames["source_pos_w"] - frames["handle_pos_w"], dim=-1
            ),
        }

    def _compute_a2_matched_clean_retreat_arm_raw(
        self, active_mask: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if (
            not torch.is_tensor(active_mask)
            or tuple(active_mask.shape) != (self.num_envs,)
            or active_mask.dtype != torch.bool
            or active_mask.device != torch.device(self.device)
        ):
            raise RuntimeError("A2 matched-clean retreat active mask contract mismatch.")
        pose = self._get_a2_matched_clean_reacquisition_pose_state()
        robot = pose["frames"]["robot"]
        root_quat_w = pose["frames"]["root_quat_w"]
        body_pos_root, _ = subtract_frame_transforms(
            pose["frames"]["root_pos_w"],
            root_quat_w,
            pose["frames"]["body_pos_w"],
            pose["frames"]["body_quat_w"],
        )
        jacobian = robot.root_physx_view.get_jacobians()[:,
            self._a2_hold_oracle_jacobian_body_id,
            :,
            self._a2_hold_oracle_jacobian_joint_ids,
        ]
        expected_shape = (self.num_envs, 6, 6)
        if (
            tuple(jacobian.shape) != expected_shape
            or not jacobian.is_floating_point()
            or jacobian.device != torch.device(self.device)
            or not torch.all(torch.isfinite(jacobian))
        ):
            raise RuntimeError(
                "A2 matched-clean retreat requires finite raw Jacobian shape "
                f"{expected_shape}; got {tuple(jacobian.shape)}."
            )
        jacobian_root = a2_hold_rotate_jacobian_to_root(jacobian, root_quat_w)
        jacobian_root = a2_hold_apply_source_offset_to_jacobian(
            jacobian_root,
            pose["source_pos_root"] - body_pos_root,
        )
        ik_target_pos_root = torch.where(
            active_mask[:, None], pose["target_pos_root"], pose["source_pos_root"]
        )
        ik_target_quat_root = torch.where(
            active_mask[:, None], pose["target_quat_root"], pose["source_quat_root"]
        )
        singular_values = torch.linalg.svdvals(jacobian_root)
        condition = singular_values[:, 0] / singular_values[:, -1]
        ik_valid = torch.isfinite(condition) & (
            condition <= self._a2_hold_oracle_cfg["jacobian_condition_max"]
        )
        (
            bounded_command_pos,
            bounded_command_quat,
            _,
            _,
            bounded_delta,
        ) = a2_hold_bound_pose_command_step(
            pose["source_pos_root"],
            pose["source_quat_root"],
            ik_target_pos_root,
            ik_target_quat_root,
            self._a2_hold_oracle_cfg["max_position_step_m"],
            self._a2_hold_oracle_cfg["max_orientation_step_rad"],
        )
        self._a2_hold_oracle_controller.set_command(
            torch.cat((bounded_command_pos, bounded_command_quat), dim=-1)
        )
        q_des = self._a2_hold_oracle_controller.compute(
            pose["source_pos_root"],
            pose["source_quat_root"],
            jacobian_root,
            robot.data.joint_pos[:, self._a2_hold_oracle_joint_ids],
        )
        if not torch.all(torch.isfinite(q_des)):
            raise RuntimeError("A2 matched-clean retreat DLS returned non-finite q_des.")
        joint_ids = self._a2_hold_oracle_joint_ids
        hard_limits = robot.data.joint_pos_limits[:, joint_ids]
        soft_limits = robot.data.soft_joint_pos_limits[:, joint_ids]
        if not torch.all(torch.isfinite(hard_limits)) or not torch.all(
            torch.isfinite(soft_limits)
        ):
            raise RuntimeError("A2 matched-clean retreat requires finite arm joint limits.")
        limit_valid, _, _ = a2_hold_progress_aware_joint_limit_masks(
            robot.data.joint_pos[:, joint_ids],
            q_des,
            hard_limits,
            soft_limits,
            self._a2_hold_oracle_cfg["joint_limit_margin"],
            self._a2_hold_oracle_cfg["joint_limit_margin"],
            self._a2_hold_oracle_cfg["soft_limit_progress_tolerance"],
        )
        q_default = robot.data.default_joint_pos[:, joint_ids]
        if q_default.shape[0] == 1:
            q_default = q_default.repeat(self.num_envs, 1)
        if (
            not torch.is_tensor(self._delta_actions)
            or tuple(self._delta_actions.shape) != (self.num_envs, 6)
            or not torch.all(torch.isfinite(self._delta_actions))
            or not torch.all(torch.isfinite(q_default))
        ):
            raise RuntimeError(
                "A2 matched-clean retreat requires finite cumulative arm target shape (N,6)."
            )
        d_des, a_raw = a2_hold_absolute_target_to_cumulative_action(
            q_des, q_default, self._delta_actions.clone()
        )
        delta_ok = torch.all(torch.abs(d_des) <= 15.0, dim=-1)
        raw_ok = torch.all(
            torch.abs(a_raw) <= self._a2_hold_oracle_cfg["raw_action_abs_max"], dim=-1
        )
        active_ik_invalid = active_mask & ~ik_valid
        active_joint_limit = active_mask & ik_valid & ~limit_valid
        active_action_invalid = (
            active_mask & ik_valid & limit_valid & ~(delta_ok & raw_ok)
        )
        active_valid = active_mask & ik_valid & limit_valid & delta_ok & raw_ok
        self._a2_hold_oracle_q_des[active_mask] = q_des[active_mask]
        self._a2_hold_oracle_d_des[active_mask] = d_des[active_mask]
        self._a2_hold_oracle_d_prev[active_mask] = self._delta_actions[active_mask]
        self._a2_hold_oracle_a_raw[active_mask] = torch.where(
            active_valid[active_mask, None],
            a_raw[active_mask],
            torch.zeros_like(a_raw[active_mask]),
        )
        self._a2_hold_oracle_arm_candidate_action_raw[active_mask] = a_raw[active_mask]
        self._a2_hold_oracle_target_pos_root[active_mask] = pose["target_pos_root"][active_mask]
        self._a2_hold_oracle_target_quat_root[active_mask] = pose["target_quat_root"][active_mask]
        self._a2_hold_oracle_bounded_command_pos_root[active_mask] = bounded_command_pos[
            active_mask
        ]
        self._a2_hold_oracle_bounded_command_quat_root[active_mask] = bounded_command_quat[
            active_mask
        ]
        self._a2_hold_oracle_bounded_position_step[active_mask] = torch.linalg.norm(
            bounded_delta[active_mask, :3], dim=-1
        )
        self._a2_hold_oracle_bounded_orientation_step[active_mask] = torch.linalg.norm(
            bounded_delta[active_mask, 3:], dim=-1
        )
        self._a2_hold_oracle_position_residual[active_mask] = pose["position_residual"][
            active_mask
        ]
        self._a2_hold_oracle_orientation_residual[active_mask] = pose[
            "orientation_residual"
        ][active_mask]
        self._a2_hold_oracle_singular_values[active_mask] = singular_values[active_mask]
        self._a2_hold_oracle_jacobian_condition[active_mask] = condition[active_mask]
        self._a2_hold_oracle_ik_valid[active_mask] = ik_valid[active_mask]
        self._a2_hold_oracle_limit_valid[active_mask] = limit_valid[active_mask]
        self._a2_hold_oracle_delta_ok[active_mask] = delta_ok[active_mask]
        self._a2_hold_oracle_raw_ok[active_mask] = raw_ok[active_mask]
        self._a2_hold_oracle_matched_clean_release_ik_invalid[active_mask] = (
            active_ik_invalid[active_mask]
        )
        self._a2_hold_oracle_matched_clean_release_joint_limit[active_mask] = (
            active_joint_limit[active_mask]
        )
        self._a2_hold_oracle_matched_clean_release_action_invalid[active_mask] = (
            active_action_invalid[active_mask]
        )
        return a_raw, active_valid

    def _capture_a2_matched_clean_release_post_action_samples(self) -> None:
        cfg = self._a2_hold_oracle_cfg
        sample_mask = (
            self._a2_hold_oracle_matched_clean_release_active
            & self._a2_hold_oracle_matched_clean_release_override_mask
        )
        env_ids = torch.nonzero(sample_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return
        counts = self._a2_hold_oracle_matched_clean_release_action_count[env_ids]
        if torch.any(counts < 1) or torch.any(
            counts > cfg["matched_clean_retreat_timeout_steps"]
        ):
            raise RuntimeError("A2 matched-clean release sample count is outside actions 1..80.")
        pose = self._get_a2_matched_clean_reacquisition_pose_state()
        contact = self._get_a2_open_stabilization_contact_force_norm()
        gate = self._get_a2_open_stabilization_composite_gate()
        gate_lost = ~gate
        self._a2_hold_oracle_matched_clean_gate_lost_ever[env_ids] |= gate_lost[env_ids]
        qualified = a2_hold_matched_clean_release_qualification(
            pose["position_residual"][env_ids],
            pose["orientation_residual"][env_ids],
            contact[env_ids],
            pose["source_handle_distance"][env_ids],
            position_tolerance_m=cfg["matched_clean_pregrasp_position_tolerance_m"],
            orientation_tolerance_rad=cfg[
                "matched_clean_pregrasp_orientation_tolerance_rad"
            ],
        )
        contact_contaminated = torch.any(contact[env_ids] >= 1.0, dim=-1)
        qualified &= ~contact_contaminated
        step = a2_hold_matched_clean_release_step_masks(
            torch.ones(env_ids.shape, device=self.device, dtype=torch.bool),
            torch.ones(env_ids.shape, device=self.device, dtype=torch.bool),
            counts,
            self._a2_hold_oracle_matched_clean_qualification_count[env_ids],
            qualified,
            contact_contaminated,
            cfg["matched_clean_retreat_timeout_steps"],
            cfg["matched_clean_release_qualification_steps"],
        )
        self._a2_hold_oracle_matched_clean_qualification_count[env_ids] = step[
            "qualification_count"
        ]
        self._a2_hold_oracle_matched_clean_release_contact_reset_count[env_ids] += (
            step["contact_reset"].long()
        )
        post_delta = self._a2_eval_post_delta_post_warp_env_action
        if (
            not torch.is_tensor(post_delta)
            or tuple(post_delta.shape) != (self.num_envs, 12)
            or post_delta.device != torch.device(self.device)
            or not torch.all(torch.isfinite(post_delta))
        ):
            raise RuntimeError(
                "A2 matched-clean release requires finite post-delta authoritative action shape (N,12)."
            )
        applied_action = self._a2_hold_oracle_post_override_action
        if (
            not torch.is_tensor(applied_action)
            or tuple(applied_action.shape) != (self.num_envs, 12)
            or applied_action.device != torch.device(self.device)
            or not torch.all(torch.isfinite(applied_action))
        ):
            raise RuntimeError("A2 matched-clean release applied-action telemetry is invalid.")
        for local, env_id in enumerate(env_ids.tolist()):
            action_number = int(counts[local].item())
            samples = self._a2_hold_oracle_matched_clean_samples[env_id]
            if len(samples) != action_number - 1:
                raise RuntimeError(
                    "A2 matched-clean release requires one post-action sample per action; "
                    f"env={env_id}, action={action_number}, existing={len(samples)}."
                )
            samples.append(
                {
                    "phase": "RELEASE_RETREAT",
                    "action": action_number,
                    "pregrasp_position_residual_m": float(
                        pose["position_residual"][env_id].item()
                    ),
                    "pregrasp_orientation_residual_rad": float(
                        pose["orientation_residual"][env_id].item()
                    ),
                    "filtered_normal_force_magnitude_n": contact[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "source_handle_distance_m": float(
                        pose["source_handle_distance"][env_id].item()
                    ),
                    "qualification_sample": bool(qualified[local].item()),
                    "qualification_count": int(
                        step["qualification_count"][local].item()
                    ),
                    "contact_reset": bool(step["contact_reset"][local].item()),
                    "gate_lost": bool(gate_lost[env_id].item()),
                    "post_delta_arm_target": post_delta[env_id, 5:11]
                    .detach()
                    .cpu()
                    .tolist(),
                    "applied_high_level_action": applied_action[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "control_branch": "MATCHED_CLEAN_RELEASE_RETREAT",
                }
            )
            if step["qualified_now"][local].item():
                if not torch.all(torch.isfinite(self._delta_actions[env_id])):
                    raise RuntimeError(
                        "A2 matched-clean qualification captured a non-finite accumulated arm target."
                    )
                self._a2_hold_oracle_matched_clean_captured_arm_target[env_id] = (
                    self._delta_actions[env_id]
                )
                self._a2_hold_oracle_matched_clean_release_qualification_evidence[
                    env_id
                ] = {
                    "action": action_number,
                    "qualification_count": int(
                        step["qualification_count"][local].item()
                    ),
                    "pregrasp_position_residual_m": float(
                        pose["position_residual"][env_id].item()
                    ),
                    "pregrasp_orientation_residual_rad": float(
                        pose["orientation_residual"][env_id].item()
                    ),
                    "filtered_normal_force_magnitude_n": contact[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "source_handle_distance_m": float(
                        pose["source_handle_distance"][env_id].item()
                    ),
                    "captured_accumulated_arm_target": self._delta_actions[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                }
                self._a2_hold_oracle_matched_clean_release_final_action_count[
                    env_id
                ] = action_number
                self._a2_hold_oracle_matched_clean_release_active[env_id] = False
                self._a2_hold_oracle_matched_clean_stabilize_active[env_id] = True
                self._a2_hold_oracle_phase[env_id] = (
                    A2_HOLD_PHASE_MATCHED_CLEAN_STABILIZE
                )
                self._a2_hold_oracle_phase_step[env_id] = 0
                self._a2_hold_oracle_matched_clean_stabilize_action_count[env_id] = 0
                self._a2_hold_oracle_matched_clean_qualification_count[env_id] = (
                    cfg["matched_clean_release_qualification_steps"]
                )
            elif step["timeout"][local].item():
                outcome = "MATCHED_CLEAN_RETREAT_TIMEOUT"
                self._a2_hold_oracle_matched_clean_reason_timeout[env_id] = True
                self._a2_hold_oracle_matched_clean_release_final_action_count[env_id] = (
                    action_number
                )
                self._a2_hold_oracle_matched_clean_result[env_id] = {
                    "ready": False,
                    "outcome": outcome,
                    "final_release_action_count": action_number,
                    "qualification_count": int(
                        step["qualification_count"][local].item()
                    ),
                }
                self._a2_hold_oracle_matched_clean_release_active[env_id] = False
                self._a2_hold_oracle_phase[env_id] = A2_HOLD_PHASE_DONE
                one = torch.zeros(self.num_envs, device=self.device, dtype=torch.bool)
                one[env_id] = True
                self._set_a2_hold_outcome(one, outcome)

    def _evaluate_a2_matched_clean_stabilize_quiet_window(self, env_id: int) -> dict:
        cfg = self._a2_hold_oracle_cfg
        samples = self._a2_hold_oracle_matched_clean_quiet_samples[env_id]
        if len(samples) != 40 or [sample["action"] for sample in samples] != list(range(1, 41)):
            raise RuntimeError(
                "A2 matched-clean READY evaluation requires exactly clean-stabilize actions 1..40."
            )
        quiet = samples[-5:]
        pose_window = samples[-6:]
        pose_fields = {
            "root_world": ("root_pos_w", "root_quat_w"),
            "source_in_current_root": ("source_pos_root", "source_quat_root"),
            "pregrasp_in_current_root": (
                "pregrasp_pos_root",
                "pregrasp_quat_root",
            ),
            "handle_world": ("handle_pos_w", "handle_quat_w"),
        }
        pose_metrics = {}
        pose_ok = True
        dtype = self._a2_hold_oracle_matched_clean_captured_arm_target.dtype
        for label, (position_key, quaternion_key) in pose_fields.items():
            position = torch.tensor(
                [[sample[position_key]] for sample in pose_window],
                device=self.device,
                dtype=dtype,
            )
            quaternion = torch.tensor(
                [[sample[quaternion_key]] for sample in pose_window],
                device=self.device,
                dtype=dtype,
            )
            try:
                metrics = a2_hold_pose_motion_metrics(position, quaternion)
            except ValueError as exc:
                raise RuntimeError(
                    f"A2 matched-clean {label} quiet-window pose math failed: {exc}"
                ) from exc
            record = {name: float(value.item()) for name, value in metrics.items()}
            record["within_threshold"] = (
                record["per_call_translation_max"]
                <= cfg["open_stabilization_pose_per_call_translation_max_m"]
                and record["per_call_rotation_max"]
                <= cfg["open_stabilization_pose_per_call_rotation_max_rad"]
                and record["window_translation"]
                <= cfg["open_stabilization_pose_window_translation_max_m"]
                and record["window_rotation"]
                <= cfg["open_stabilization_pose_window_rotation_max_rad"]
            )
            pose_ok &= record["within_threshold"]
            pose_metrics[label] = record
        max_root_linear_speed = max(sample["root_linear_speed_mps"] for sample in quiet)
        max_root_angular_speed = max(sample["root_angular_speed_radps"] for sample in quiet)
        max_contact = max(
            max(sample["filtered_normal_force_magnitude_n"]) for sample in quiet
        )
        reasons = {
            "root_linear_speed_ok": max_root_linear_speed
            <= cfg["open_stabilization_root_linear_speed_max_mps"],
            "root_angular_speed_ok": max_root_angular_speed
            <= cfg["open_stabilization_root_angular_speed_max_radps"],
            "pose_motion_ok": pose_ok,
            "contact_force_ok": max_contact
            < cfg["open_stabilization_contact_force_max_n"],
        }
        return {
            "ready": all(reasons.values()),
            "reason_booleans": reasons,
            "max_root_linear_speed_mps": max_root_linear_speed,
            "max_root_angular_speed_radps": max_root_angular_speed,
            "max_filtered_normal_force_n": max_contact,
            "pose_motion": pose_metrics,
            "quiet_window_actions": [sample["action"] for sample in quiet],
            "pose_window_actions": [sample["action"] for sample in pose_window],
            "quiet_window_samples": quiet,
            "pose_window_samples": pose_window,
        }

    def _finish_a2_matched_clean_reacquisition(self, affected_mask: torch.Tensor) -> None:
        cfg = self._a2_hold_oracle_cfg
        if not cfg["enabled"] or not cfg["matched_clean_reacquisition_preflight_enabled"]:
            raise RuntimeError("A2 matched-clean finish requires the enabled preflight.")
        if (
            not torch.is_tensor(affected_mask)
            or tuple(affected_mask.shape) != (self.num_envs,)
            or affected_mask.dtype != torch.bool
            or affected_mask.device != torch.device(self.device)
        ):
            raise RuntimeError("A2 matched-clean finish mask contract mismatch.")
        release_affected = affected_mask & self._a2_hold_oracle_matched_clean_release_active
        for env_id in torch.nonzero(release_affected, as_tuple=False).flatten().tolist():
            count = int(self._a2_hold_oracle_matched_clean_release_action_count[env_id].item())
            if count > cfg["matched_clean_retreat_timeout_steps"]:
                raise RuntimeError("A2 matched-clean release count exceeded exact timeout.")
            if len(self._a2_hold_oracle_matched_clean_samples[env_id]) != count:
                raise RuntimeError(
                    "A2 matched-clean release cannot finish without one post-action sample per action."
                )
            outcome = (
                "MATCHED_CLEAN_RETREAT_TIMEOUT"
                if count >= cfg["matched_clean_retreat_timeout_steps"]
                else "MATCHED_CLEAN_RETREAT_INCOMPLETE"
            )
            self._a2_hold_oracle_matched_clean_reason_timeout[env_id] = outcome.endswith(
                "TIMEOUT"
            )
            self._a2_hold_oracle_matched_clean_reason_incomplete[env_id] = outcome.endswith(
                "INCOMPLETE"
            )
            self._a2_hold_oracle_matched_clean_result[env_id] = {
                "ready": False,
                "outcome": outcome,
                "final_release_action_count": count,
            }
            self._a2_hold_oracle_matched_clean_release_final_action_count[env_id] = count
            self._a2_hold_oracle_matched_clean_release_active[env_id] = False
            self._a2_hold_oracle_phase[env_id] = A2_HOLD_PHASE_DONE
            one = torch.zeros(self.num_envs, device=self.device, dtype=torch.bool)
            one[env_id] = True
            self._set_a2_hold_outcome(one, outcome)
        stabilize_affected = affected_mask & self._a2_hold_oracle_matched_clean_stabilize_active
        if not torch.any(stabilize_affected):
            return
        contact = self._get_a2_open_stabilization_contact_force_norm()
        contact_contaminated = torch.any(contact >= 1.0, dim=-1)
        counts = self._a2_hold_oracle_matched_clean_stabilize_action_count
        partition = a2_hold_matched_clean_stabilization_terminal_partition(
            stabilize_affected,
            counts,
            contact_contaminated,
            40,
        )
        for env_id in torch.nonzero(stabilize_affected, as_tuple=False).flatten().tolist():
            count = int(counts[env_id].item())
            if len(self._a2_hold_oracle_matched_clean_quiet_samples[env_id]) != count:
                raise RuntimeError(
                    "A2 matched-clean stabilization cannot finish without one sample per action."
                )
            one = torch.zeros(self.num_envs, device=self.device, dtype=torch.bool)
            one[env_id] = True
            if partition["contact_contaminated"][env_id].item():
                outcome = "MATCHED_CLEAN_STABILIZE_CONTACT_CONTAMINATED"
                result = {
                    "ready": False,
                    "outcome": outcome,
                    "final_stabilize_action_count": count,
                    "final_filtered_normal_force_magnitude_n": contact[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                }
                self._a2_hold_oracle_matched_clean_reason_contact[env_id] = True
            elif partition["endpoint"][env_id].item():
                result = self._evaluate_a2_matched_clean_stabilize_quiet_window(env_id)
                outcome = (
                    "MATCHED_CLEAN_READY"
                    if result["ready"]
                    else "MATCHED_CLEAN_NOT_SETTLED"
                )
                result["outcome"] = outcome
                result["final_stabilize_action_count"] = count
                self._a2_hold_oracle_matched_clean_reason_ready[env_id] = result["ready"]
                self._a2_hold_oracle_matched_clean_reason_not_settled[env_id] = not result[
                    "ready"
                ]
            elif partition["incomplete"][env_id].item():
                outcome = "MATCHED_CLEAN_STABILIZE_INCOMPLETE"
                result = {
                    "ready": False,
                    "outcome": outcome,
                    "final_stabilize_action_count": count,
                    "reason_booleans": {"exact_40_actions_complete": False},
                }
                self._a2_hold_oracle_matched_clean_reason_incomplete[env_id] = True
            else:
                raise RuntimeError("A2 matched-clean stabilization terminal partition was not exhaustive.")
            self._a2_hold_oracle_matched_clean_result[env_id] = result
            self._a2_hold_oracle_matched_clean_stabilize_final_action_count[env_id] = count
            self._a2_hold_oracle_matched_clean_stabilize_active[env_id] = False
            self._a2_hold_oracle_phase[env_id] = A2_HOLD_PHASE_DONE
            self._set_a2_hold_outcome(one, outcome)

    def _capture_a2_matched_clean_stabilize_post_action_samples(self) -> None:
        sample_mask = (
            self._a2_hold_oracle_matched_clean_stabilize_active
            & self._a2_hold_oracle_matched_clean_stabilize_override_mask
        )
        env_ids = torch.nonzero(sample_mask, as_tuple=False).flatten()
        if env_ids.numel() == 0:
            return
        cfg = self._a2_hold_oracle_cfg
        counts = self._a2_hold_oracle_matched_clean_stabilize_action_count[env_ids]
        if torch.any(counts < 1) or torch.any(counts > 40):
            raise RuntimeError("A2 matched-clean stabilization sample count is outside actions 1..40.")
        pose = self._get_a2_matched_clean_reacquisition_pose_state()
        contact = self._get_a2_open_stabilization_contact_force_norm()
        post_delta = self._a2_eval_post_delta_post_warp_env_action
        if (
            not torch.is_tensor(post_delta)
            or tuple(post_delta.shape) != (self.num_envs, 12)
            or post_delta.device != torch.device(self.device)
            or not torch.all(torch.isfinite(post_delta))
        ):
            raise RuntimeError(
                "A2 matched-clean stabilization requires finite post-delta authoritative action shape (N,12)."
            )
        frames = pose["frames"]
        robot_data = frames["robot"].data
        for name, value in (
            ("root_lin_vel_w", robot_data.root_lin_vel_w),
            ("root_ang_vel_w", robot_data.root_ang_vel_w),
        ):
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != (self.num_envs, 3)
                or value.device != torch.device(self.device)
                or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(
                    f"A2 matched-clean stabilization requires finite {name} shape (N,3)."
                )
        captured = self._a2_hold_oracle_matched_clean_captured_arm_target[env_ids]
        accumulated = self._delta_actions[env_ids]
        try:
            _, _, gripper = self._get_a2_static_clamp_gripper_state(env_ids)
            invariant = a2_hold_validate_open_stabilization_runtime_invariants(
                captured,
                accumulated,
                post_delta[env_ids, 5:11],
                gripper["stiffness"],
                gripper["damping"],
                gripper["effort_limit"],
            )
        except ValueError as exc:
            raise RuntimeError(
                "A2 matched-clean stabilization runtime invariant failed for "
                f"envs={env_ids.detach().cpu().tolist()}, actions={counts.detach().cpu().tolist()}: {exc}"
            ) from exc
        actual_target = robot_data.joint_pos_target[env_ids][
            :, self._a2_hold_oracle_joint_ids
        ]
        q_default = robot_data.default_joint_pos[env_ids][
            :, self._a2_hold_oracle_joint_ids
        ]
        expected_target_shape = (env_ids.numel(), 6)
        if (
            tuple(actual_target.shape) != expected_target_shape
            or tuple(q_default.shape) != expected_target_shape
            or actual_target.device != captured.device
            or q_default.device != captured.device
            or actual_target.dtype != captured.dtype
            or q_default.dtype != captured.dtype
            or not torch.all(torch.isfinite(actual_target))
            or not torch.all(torch.isfinite(q_default))
        ):
            raise RuntimeError(
                "A2 matched-clean stabilization requires finite selected actual/default "
                f"arm targets shape {expected_target_shape} with captured target dtype/device."
            )
        expected_actual_target = q_default + captured * float(
            self.config.robot.control.action_scale
        )
        actual_target_ok = torch.all(
            actual_target == expected_actual_target, dim=-1
        )
        if not torch.all(actual_target_ok):
            raise RuntimeError(
                "A2 matched-clean stabilization actual arm joint target differs from captured target."
            )
        gate = self._get_a2_open_stabilization_composite_gate()
        gate_lost = ~gate
        self._a2_hold_oracle_matched_clean_gate_lost_ever[env_ids] |= gate_lost[env_ids]
        applied_action = self._a2_hold_oracle_post_override_action
        source_pos_root, source_quat_root = subtract_frame_transforms(
            frames["root_pos_w"], frames["root_quat_w"], frames["source_pos_w"], frames["source_quat_w"]
        )
        pregrasp_pos_root, pregrasp_quat_root = subtract_frame_transforms(
            frames["root_pos_w"], frames["root_quat_w"], frames["pregrasp_pos_w"], frames["pregrasp_quat_w"]
        )
        for local, env_id in enumerate(env_ids.tolist()):
            action_number = int(counts[local].item())
            samples = self._a2_hold_oracle_matched_clean_quiet_samples[env_id]
            if len(samples) != action_number - 1:
                raise RuntimeError(
                    "A2 matched-clean stabilization requires one pre-reset sample per action; "
                    f"env={env_id}, action={action_number}, existing={len(samples)}."
                )
            record = {
                "phase": "CLEAN_STABILIZE",
                "action": action_number,
                "root_pos_w": frames["root_pos_w"][env_id].detach().cpu().tolist(),
                "root_quat_w": frames["root_quat_w"][env_id].detach().cpu().tolist(),
                "root_linear_speed_mps": float(torch.linalg.norm(robot_data.root_lin_vel_w[env_id]).item()),
                "root_angular_speed_radps": float(torch.linalg.norm(robot_data.root_ang_vel_w[env_id]).item()),
                "source_pos_root": source_pos_root[env_id].detach().cpu().tolist(),
                "source_quat_root": source_quat_root[env_id].detach().cpu().tolist(),
                "pregrasp_pos_root": pregrasp_pos_root[env_id].detach().cpu().tolist(),
                "pregrasp_quat_root": pregrasp_quat_root[env_id].detach().cpu().tolist(),
                "handle_pos_w": frames["handle_pos_w"][env_id].detach().cpu().tolist(),
                "handle_quat_w": frames["handle_quat_w"][env_id].detach().cpu().tolist(),
                "filtered_normal_force_magnitude_n": contact[env_id].detach().cpu().tolist(),
                "source_handle_distance_m": float(pose["source_handle_distance"][env_id].item()),
                "gate_lost": bool(gate_lost[env_id].item()),
                "accumulated_arm_target": accumulated[local].detach().cpu().tolist(),
                "captured_accumulated_arm_target": captured[local].detach().cpu().tolist(),
                "post_delta_arm_target": post_delta[env_id, 5:11].detach().cpu().tolist(),
                "actual_arm_joint_pos_target": actual_target[local].detach().cpu().tolist(),
                "expected_actual_arm_joint_pos_target": expected_actual_target[local].detach().cpu().tolist(),
                "accumulated_arm_target_invariant": bool(invariant["accumulated_arm_target_invariant"][local].item()),
                "post_delta_arm_target_invariant": bool(invariant["post_delta_arm_target_invariant"][local].item()),
                "actual_arm_joint_target_invariant": bool(actual_target_ok[local].item()),
                "runtime_gripper_gain_effort_exact": bool(invariant["runtime_gripper_gain_effort_exact"][local].item()),
                "gripper_stiffness": gripper["stiffness"][local].detach().cpu().tolist(),
                "gripper_damping": gripper["damping"][local].detach().cpu().tolist(),
                "gripper_effort_limit": gripper["effort_limit"][local].detach().cpu().tolist(),
                "applied_high_level_action": applied_action[env_id].detach().cpu().tolist(),
                "control_branch": "MATCHED_CLEAN_STABILIZE",
            }
            samples.append(record)
            self._a2_hold_oracle_matched_clean_actual_invariant_evidence[env_id].append(
                {
                    "action": action_number,
                    "accumulated_arm_target_invariant": record["accumulated_arm_target_invariant"],
                    "post_delta_arm_target_invariant": record["post_delta_arm_target_invariant"],
                    "actual_arm_joint_target_invariant": record["actual_arm_joint_target_invariant"],
                    "runtime_gripper_gain_effort_exact": record["runtime_gripper_gain_effort_exact"],
                }
            )
        contact_now = torch.any(contact >= 1.0, dim=-1)
        clean_finish = self._a2_hold_oracle_matched_clean_stabilize_active & (
            contact_now
            | (
                self._a2_hold_oracle_matched_clean_stabilize_action_count >= 40
            )
        )
        self._finish_a2_matched_clean_reacquisition(clean_finish)

    def _apply_a2_matched_clean_reacquisition_action(
        self,
        policy_action: torch.Tensor,
        first_episode_active_mask: torch.Tensor,
        activate: torch.Tensor,
    ):
        cfg = self._a2_hold_oracle_cfg
        if not cfg["matched_clean_reacquisition_preflight_enabled"]:
            raise RuntimeError("A2 matched-clean action requested while disabled.")
        self._a2_hold_oracle_matched_clean_last_override_mask = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._a2_hold_oracle_matched_clean_release_override_mask.zero_()
        self._a2_hold_oracle_matched_clean_stabilize_override_mask.zero_()
        self._a2_hold_oracle_a_raw.zero_()
        self._a2_hold_oracle_matched_clean_release_ik_invalid.zero_()
        self._a2_hold_oracle_matched_clean_release_joint_limit.zero_()
        self._a2_hold_oracle_matched_clean_release_action_invalid.zero_()
        wait_mask = self._a2_hold_oracle_phase == A2_HOLD_PHASE_WAIT_GATE
        entered = activate & wait_mask & first_episode_active_mask
        self._a2_hold_oracle_matched_clean_release_active[entered] = True
        self._a2_hold_oracle_matched_clean_ever_activated[entered] = True
        self._a2_hold_oracle_activated[entered] = True
        self._a2_hold_oracle_phase[entered] = A2_HOLD_PHASE_MATCHED_CLEAN_RELEASE_RETREAT
        self._a2_hold_oracle_phase_step[entered] = 0
        self._a2_hold_oracle_matched_clean_release_action_count[entered] = 0
        self._a2_hold_oracle_matched_clean_qualification_count[entered] = 0
        if torch.any(entered):
            entered_ids = torch.nonzero(entered, as_tuple=False).flatten()
            _, _, gripper = self._get_a2_static_clamp_gripper_state(entered_ids)
            if (
                not torch.equal(gripper["stiffness"], torch.full_like(gripper["stiffness"], 80.0))
                or not torch.equal(gripper["damping"], torch.full_like(gripper["damping"], 3.0))
                or not torch.equal(gripper["effort_limit"], torch.full_like(gripper["effort_limit"], 10.0))
            ):
                raise RuntimeError(
                    "A2 matched-clean reacquisition requires actual gripper Kp/Kd/effort=80/3/10 at release entry."
                )
        ended_without_gate = wait_mask & ~first_episode_active_mask
        self._set_a2_hold_outcome(ended_without_gate, "MATCHED_CLEAN_NO_GATE")
        release_finish = self._a2_hold_oracle_matched_clean_release_active & (
            ~first_episode_active_mask
            | (
                self._a2_hold_oracle_matched_clean_release_action_count
                >= cfg["matched_clean_retreat_timeout_steps"]
            )
        )
        self._finish_a2_matched_clean_reacquisition(release_finish)
        stabilize_finish = self._a2_hold_oracle_matched_clean_stabilize_active & ~first_episode_active_mask
        self._finish_a2_matched_clean_reacquisition(stabilize_finish)
        if torch.any(
            self._a2_hold_oracle_matched_clean_stabilize_active
            & (
                self._a2_hold_oracle_matched_clean_stabilize_action_count >= 40
            )
        ):
            raise RuntimeError("A2 matched-clean stabilization refused action 41.")
        release_active = self._a2_hold_oracle_matched_clean_release_active & first_episode_active_mask
        if torch.any(release_active):
            release_raw, release_valid = self._compute_a2_matched_clean_retreat_arm_raw(
                release_active
            )
            self._set_a2_hold_outcome(
                self._a2_hold_oracle_matched_clean_release_ik_invalid,
                "MATCHED_CLEAN_RETREAT_IK_INVALID",
            )
            self._set_a2_hold_outcome(
                self._a2_hold_oracle_matched_clean_release_joint_limit,
                "MATCHED_CLEAN_RETREAT_JOINT_LIMIT",
            )
            self._set_a2_hold_outcome(
                self._a2_hold_oracle_matched_clean_release_action_invalid,
                "MATCHED_CLEAN_RETREAT_ACTION_INVALID",
            )
            invalid_release = release_active & ~release_valid
            invalid_outcome_masks = (
                (
                    self._a2_hold_oracle_matched_clean_release_ik_invalid,
                    "MATCHED_CLEAN_RETREAT_IK_INVALID",
                ),
                (
                    self._a2_hold_oracle_matched_clean_release_joint_limit,
                    "MATCHED_CLEAN_RETREAT_JOINT_LIMIT",
                ),
                (
                    self._a2_hold_oracle_matched_clean_release_action_invalid,
                    "MATCHED_CLEAN_RETREAT_ACTION_INVALID",
                ),
            )
            for invalid_mask, invalid_outcome in invalid_outcome_masks:
                for env_id in torch.nonzero(invalid_mask, as_tuple=False).flatten().tolist():
                    if not release_active[env_id].item():
                        continue
                    count = int(
                        self._a2_hold_oracle_matched_clean_release_action_count[env_id].item()
                    )
                    self._a2_hold_oracle_matched_clean_release_final_action_count[env_id] = count
                    self._a2_hold_oracle_matched_clean_result[env_id] = {
                        "ready": False,
                        "outcome": invalid_outcome,
                        "final_release_action_count": count,
                    }
            self._a2_hold_oracle_matched_clean_release_active[invalid_release] = False
            release_active &= release_valid & (
                self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
            )
        else:
            release_raw = torch.zeros(
                self.num_envs, 6, device=self.device, dtype=policy_action.dtype
            )
        release_count = self._a2_hold_oracle_matched_clean_release_action_count
        release_count[release_active] += 1
        self._a2_hold_oracle_phase_step[release_active] = release_count[release_active]
        stabilize_active = self._a2_hold_oracle_matched_clean_stabilize_active & first_episode_active_mask
        action = a2_hold_matched_clean_release_action(policy_action, release_active, release_raw)
        if torch.any(stabilize_active):
            action[stabilize_active, :11] = 0.0
            action[stabilize_active, 11] = 1.0
            self._a2_hold_oracle_matched_clean_stabilize_action_count[stabilize_active] += 1
            self._a2_hold_oracle_phase_step[stabilize_active] = self._a2_hold_oracle_matched_clean_stabilize_action_count[stabilize_active]
        override = release_active | stabilize_active
        self._a2_hold_oracle_matched_clean_release_override_mask[:] = release_active
        self._a2_hold_oracle_matched_clean_stabilize_override_mask[:] = stabilize_active
        self._a2_hold_oracle_matched_clean_last_override_mask = override.clone()
        self._a2_hold_oracle_last_override_mask = override.clone()
        self._a2_hold_oracle_post_override_action = action.detach().clone()
        self._a2_hold_oracle_arm_dls_branch[:] = release_active
        self._a2_hold_oracle_base_relief_branch_applied.zero_()
        return action, override

    def _get_a2_hold_oracle_pose_state(
        self, target_local_offset: torch.Tensor, active_mask: torch.Tensor
    ):
        if (
            not torch.is_tensor(target_local_offset)
            or tuple(target_local_offset.shape) != (self.num_envs, 3)
            or target_local_offset.device != torch.device(self.device)
            or not torch.all(torch.isfinite(target_local_offset))
        ):
            raise RuntimeError(
                "A2 hold oracle target_local_offset must be finite shape "
                f"({self.num_envs},3) on {self.device}."
            )
        if (
            not torch.is_tensor(active_mask)
            or tuple(active_mask.shape) != (self.num_envs,)
            or active_mask.dtype != torch.bool
            or active_mask.device != target_local_offset.device
        ):
            raise RuntimeError("A2 hold oracle pose active mask contract mismatch.")
        frames = self._get_a2_hold_oracle_world_frames()
        robot = frames["robot"]
        root_pos_w = frames["root_pos_w"]
        root_quat_w = frames["root_quat_w"]
        body_pos_w = frames["body_pos_w"]
        body_quat_w = frames["body_quat_w"]
        source_pos_w = frames["source_pos_w"]
        source_quat_w = frames["source_quat_w"]
        handle_pos_w = frames["handle_pos_w"]
        handle_quat_w = frames["handle_quat_w"]
        target_pos_w = handle_pos_w + quat_apply(handle_quat_w, target_local_offset)
        target_quat_w = a2_hold_compose_handoff_target_orientation(
            handle_pos_w,
            handle_quat_w,
            source_quat_w,
            self._a2_hold_oracle_handoff_relative_quat,
            active_mask,
            self._a2_hold_oracle_handoff_orientation_captured,
        )
        source_pos_root, source_quat_root = subtract_frame_transforms(
            root_pos_w, root_quat_w, source_pos_w, source_quat_w
        )
        body_pos_root, _ = subtract_frame_transforms(
            root_pos_w, root_quat_w, body_pos_w, body_quat_w
        )
        target_pos_root, target_quat_root = subtract_frame_transforms(
            root_pos_w, root_quat_w, target_pos_w, target_quat_w
        )
        position_residual = torch.linalg.norm(target_pos_root - source_pos_root, dim=-1)
        quat_error = quat_mul(target_quat_root, quat_inv(source_quat_root))
        orientation_residual = torch.linalg.norm(axis_angle_from_quat(quat_error), dim=-1)
        return {
            "robot": robot,
            "root_pos_w": root_pos_w,
            "root_quat_w": root_quat_w,
            "source_pos_w": source_pos_w,
            "source_pos_root": source_pos_root,
            "source_quat_root": source_quat_root,
            "source_offset_root": source_pos_root - body_pos_root,
            "target_pos_root": target_pos_root,
            "target_quat_root": target_quat_root,
            "target_pos_w": target_pos_w,
            "position_residual": position_residual,
            "orientation_residual": orientation_residual,
        }

    def _compute_a2_hold_oracle_joint_target(
        self, target_local_offset: torch.Tensor, active_mask: torch.Tensor
    ):
        pose_state = self._get_a2_hold_oracle_pose_state(target_local_offset, active_mask)
        robot = pose_state["robot"]
        data = robot.data
        num_envs = self.num_envs
        joint_ids = self._a2_hold_oracle_joint_ids
        jacobian = robot.root_physx_view.get_jacobians()[
            :, self._a2_hold_oracle_jacobian_body_id, :, self._a2_hold_oracle_jacobian_joint_ids
        ]
        if tuple(jacobian.shape) != (num_envs, 6, 6) or not torch.all(torch.isfinite(jacobian)):
            raise RuntimeError(
                f"A2 hold oracle requires finite raw Jacobian shape ({num_envs},6,6); "
                f"got {tuple(jacobian.shape)}."
            )
        jacobian_root = a2_hold_rotate_jacobian_to_root(
            jacobian, pose_state["root_quat_w"]
        )
        jacobian_root = a2_hold_apply_source_offset_to_jacobian(
            jacobian_root, pose_state["source_offset_root"]
        )
        singular_values = torch.linalg.svdvals(jacobian_root)
        condition = singular_values[:, 0] / singular_values[:, -1]
        ik_valid = torch.isfinite(condition) & (
            condition <= self._a2_hold_oracle_cfg["jacobian_condition_max"]
        )
        (
            bounded_command_pos,
            bounded_command_quat,
            _,
            _,
            bounded_delta,
        ) = a2_hold_bound_pose_command_step(
            pose_state["source_pos_root"],
            pose_state["source_quat_root"],
            pose_state["target_pos_root"],
            pose_state["target_quat_root"],
            self._a2_hold_oracle_cfg["max_position_step_m"],
            self._a2_hold_oracle_cfg["max_orientation_step_rad"],
        )
        command = torch.cat((bounded_command_pos, bounded_command_quat), dim=-1)
        self._a2_hold_oracle_controller.set_command(command)
        q = data.joint_pos[:, joint_ids]
        q_des = self._a2_hold_oracle_controller.compute(
            pose_state["source_pos_root"],
            pose_state["source_quat_root"],
            jacobian_root,
            q,
        )
        if not torch.all(torch.isfinite(q_des)):
            raise RuntimeError("A2 hold oracle DLS returned non-finite q_des.")
        return (
            q_des,
            ik_valid,
            singular_values,
            condition,
            pose_state["target_pos_root"],
            pose_state["target_quat_root"],
            pose_state["position_residual"],
            pose_state["orientation_residual"],
            bounded_command_pos,
            bounded_command_quat,
            torch.linalg.norm(bounded_delta[:, :3], dim=-1),
            torch.linalg.norm(bounded_delta[:, 3:], dim=-1),
            pose_state["target_pos_w"][:, :2] - pose_state["source_pos_w"][:, :2],
            pose_state["root_pos_w"][:, :2],
            pose_state["root_quat_w"],
        )

    def _compute_a2_hold_offset_joint_target(self, active_mask: torch.Tensor):
        frames = self._get_a2_hold_oracle_world_frames()
        target_pos_w = frames["source_pos_w"].clone()
        target_quat_w = frames["source_quat_w"].clone()
        target_pos_w[active_mask] = self._a2_hold_oracle_offset_fixed_target_pos_w[
            active_mask
        ]
        target_quat_w[active_mask] = self._a2_hold_oracle_offset_fixed_target_quat_w[
            active_mask
        ]
        source_pos_root, source_quat_root = subtract_frame_transforms(
            frames["root_pos_w"],
            frames["root_quat_w"],
            frames["source_pos_w"],
            frames["source_quat_w"],
        )
        body_pos_root, _ = subtract_frame_transforms(
            frames["root_pos_w"],
            frames["root_quat_w"],
            frames["body_pos_w"],
            frames["body_quat_w"],
        )
        target_pos_root, target_quat_root = subtract_frame_transforms(
            frames["root_pos_w"],
            frames["root_quat_w"],
            target_pos_w,
            target_quat_w,
        )
        position_residual = torch.linalg.norm(
            target_pos_root - source_pos_root, dim=-1
        )
        quat_error = quat_mul(target_quat_root, quat_inv(source_quat_root))
        orientation_residual = torch.linalg.norm(
            axis_angle_from_quat(quat_error), dim=-1
        )
        robot = frames["robot"]
        joint_ids = self._a2_hold_oracle_joint_ids
        jacobian = robot.root_physx_view.get_jacobians()[
            :,
            self._a2_hold_oracle_jacobian_body_id,
            :,
            self._a2_hold_oracle_jacobian_joint_ids,
        ]
        if tuple(jacobian.shape) != (self.num_envs, 6, 6) or not torch.all(
            torch.isfinite(jacobian)
        ):
            raise RuntimeError(
                f"A2 offset placement requires finite Jacobian ({self.num_envs},6,6)."
            )
        jacobian_root = a2_hold_rotate_jacobian_to_root(
            jacobian, frames["root_quat_w"]
        )
        jacobian_root = a2_hold_apply_source_offset_to_jacobian(
            jacobian_root, source_pos_root - body_pos_root
        )
        singular_values = torch.linalg.svdvals(jacobian_root)
        condition = singular_values[:, 0] / singular_values[:, -1]
        ik_valid = torch.isfinite(condition) & (
            condition <= self._a2_hold_oracle_cfg["jacobian_condition_max"]
        )
        (
            bounded_command_pos,
            bounded_command_quat,
            _,
            _,
            bounded_delta,
        ) = a2_hold_bound_pose_command_step(
            source_pos_root,
            source_quat_root,
            target_pos_root,
            target_quat_root,
            self._a2_hold_oracle_cfg["max_position_step_m"],
            self._a2_hold_oracle_cfg["max_orientation_step_rad"],
        )
        self._a2_hold_oracle_controller.set_command(
            torch.cat((bounded_command_pos, bounded_command_quat), dim=-1)
        )
        # DifferentialIKController has a fixed num_envs batch and no masked set_command API.
        # Inactive rows target their current source pose, and their computed rows are neither
        # applied nor persisted; this controller buffer is only ephemeral batched IK workspace.
        q_des = self._a2_hold_oracle_controller.compute(
            source_pos_root,
            source_quat_root,
            jacobian_root,
            robot.data.joint_pos[:, joint_ids],
        )
        if not torch.all(torch.isfinite(q_des)):
            raise RuntimeError("A2 offset placement DLS returned non-finite q_des.")
        return (
            q_des,
            ik_valid,
            singular_values,
            condition,
            target_pos_root,
            target_quat_root,
            position_residual,
            orientation_residual,
            bounded_command_pos,
            bounded_command_quat,
            torch.linalg.norm(bounded_delta[:, :3], dim=-1),
            torch.linalg.norm(bounded_delta[:, 3:], dim=-1),
            frames["root_pos_w"][:, :2],
        )

    def _compute_a2_offset_placement_arm_raw(
        self, placement_mask: torch.Tensor
    ) -> torch.Tensor:
        placement_env_ids = torch.nonzero(
            placement_mask, as_tuple=False
        ).flatten()
        if torch.any(self._a2_hold_oracle_static_clamp_gain_applied[placement_env_ids]):
            raise RuntimeError("A2 offset placement cannot run with clamp gains applied.")
        _, _, gripper_state = self._get_a2_static_clamp_gripper_state(
            placement_env_ids
        )
        if (
            not torch.equal(
                gripper_state["stiffness"],
                torch.full_like(gripper_state["stiffness"], 80.0),
            )
            or not torch.equal(
                gripper_state["damping"],
                torch.full_like(gripper_state["damping"], 3.0),
            )
            or not torch.equal(
                gripper_state["effort_limit"],
                torch.full_like(gripper_state["effort_limit"], 10.0),
            )
        ):
            raise RuntimeError(
                "A2 offset placement must retain gripper Kp/Kd=80/3 and effort=10/10."
            )
        (
            q_des,
            ik_valid,
            singular_values,
            condition,
            target_pos_root,
            target_quat_root,
            pos_res,
            rot_res,
            bounded_command_pos_root,
            bounded_command_quat_root,
            bounded_position_step,
            bounded_orientation_step,
            root_xy_w,
        ) = self._compute_a2_hold_offset_joint_target(placement_mask)
        robot = self.simulator.scene.articulations["robot"]
        joint_ids = self._a2_hold_oracle_joint_ids
        hard_limits = robot.data.joint_pos_limits[:, joint_ids]
        soft_limits = robot.data.soft_joint_pos_limits[:, joint_ids]
        if not torch.all(torch.isfinite(hard_limits)) or not torch.all(
            torch.isfinite(soft_limits)
        ):
            raise RuntimeError("A2 offset placement requires finite arm joint limits.")
        limit_valid, _, _ = a2_hold_progress_aware_joint_limit_masks(
            robot.data.joint_pos[:, joint_ids],
            q_des,
            hard_limits,
            soft_limits,
            self._a2_hold_oracle_cfg["joint_limit_margin"],
            self._a2_hold_oracle_cfg["joint_limit_margin"],
            self._a2_hold_oracle_cfg["soft_limit_progress_tolerance"],
        )
        q_default = robot.data.default_joint_pos[:, joint_ids]
        if q_default.shape[0] == 1:
            q_default = q_default.repeat(self.num_envs, 1)
        d_prev = self._delta_actions.clone()
        if not torch.all(torch.isfinite(q_default)) or not torch.all(
            torch.isfinite(d_prev)
        ):
            raise RuntimeError("A2 offset placement requires finite cumulative action state.")
        d_des, a_raw = a2_hold_absolute_target_to_cumulative_action(
            q_des, q_default, d_prev
        )
        delta_ok = torch.all(torch.abs(d_des) <= 15.0, dim=-1)
        raw_ok = torch.all(
            torch.abs(a_raw) <= self._a2_hold_oracle_cfg["raw_action_abs_max"],
            dim=-1,
        )
        valid = ik_valid & limit_valid & delta_ok & raw_ok
        invalid = placement_mask & ~valid
        if torch.any(invalid):
            ids = torch.nonzero(invalid, as_tuple=False).flatten().detach().cpu().tolist()
            raise RuntimeError(
                "A2 offset placement DLS/limit/delta/raw validation failed for envs "
                f"{ids}; ik={ik_valid[invalid].detach().cpu().tolist()}, "
                f"limit={limit_valid[invalid].detach().cpu().tolist()}, "
                f"delta={delta_ok[invalid].detach().cpu().tolist()}, "
                f"raw={raw_ok[invalid].detach().cpu().tolist()}."
            )
        self._a2_hold_oracle_q_des[placement_mask] = q_des[placement_mask]
        self._a2_hold_oracle_d_des[placement_mask] = d_des[placement_mask]
        self._a2_hold_oracle_d_prev[placement_mask] = d_prev[placement_mask]
        self._a2_hold_oracle_arm_candidate_action_raw[placement_mask] = a_raw[
            placement_mask
        ]
        self._a2_hold_oracle_a_raw[placement_mask] = a_raw[placement_mask]
        self._a2_hold_oracle_target_pos_root[placement_mask] = target_pos_root[
            placement_mask
        ]
        self._a2_hold_oracle_target_quat_root[placement_mask] = target_quat_root[
            placement_mask
        ]
        self._a2_hold_oracle_bounded_command_pos_root[placement_mask] = (
            bounded_command_pos_root[placement_mask]
        )
        self._a2_hold_oracle_bounded_command_quat_root[placement_mask] = (
            bounded_command_quat_root[placement_mask]
        )
        self._a2_hold_oracle_bounded_position_step[placement_mask] = (
            bounded_position_step[placement_mask]
        )
        self._a2_hold_oracle_bounded_orientation_step[placement_mask] = (
            bounded_orientation_step[placement_mask]
        )
        self._a2_hold_oracle_position_residual[placement_mask] = pos_res[
            placement_mask
        ]
        self._a2_hold_oracle_orientation_residual[placement_mask] = rot_res[
            placement_mask
        ]
        self._a2_hold_oracle_singular_values[placement_mask] = singular_values[
            placement_mask
        ]
        self._a2_hold_oracle_jacobian_condition[placement_mask] = condition[
            placement_mask
        ]
        self._a2_hold_oracle_ik_valid[placement_mask] = ik_valid[placement_mask]
        self._a2_hold_oracle_limit_valid[placement_mask] = limit_valid[
            placement_mask
        ]
        self._a2_hold_oracle_delta_ok[placement_mask] = delta_ok[placement_mask]
        self._a2_hold_oracle_raw_ok[placement_mask] = raw_ok[placement_mask]
        root_displacement = torch.linalg.norm(
            root_xy_w - self._a2_hold_oracle_offset_root_start_xy_w, dim=-1
        )
        self._a2_hold_oracle_offset_root_displacement_m[placement_mask] = (
            root_displacement[placement_mask]
        )
        live_frames = self._get_a2_hold_oracle_world_frames()
        try:
            live_metrics = a2_hold_offset_endpoint_metrics(
                live_frames["source_pos_w"][placement_env_ids],
                live_frames["source_quat_w"][placement_env_ids],
                self._a2_hold_oracle_offset_gate_source_pos_w[placement_env_ids],
                self._a2_hold_oracle_offset_fixed_target_pos_w[placement_env_ids],
                self._a2_hold_oracle_offset_fixed_target_quat_w[placement_env_ids],
                self._a2_hold_oracle_offset_source_local_y_axis_w[placement_env_ids],
                self._a2_hold_oracle_cfg["static_clamp_offset_m"],
                self._a2_hold_oracle_cfg[
                    "static_clamp_offset_position_tolerance_m"
                ],
                self._a2_hold_oracle_cfg[
                    "static_clamp_offset_orientation_tolerance_rad"
                ],
            )
        except ValueError as exc:
            raise RuntimeError(f"A2 offset live placement telemetry failed: {exc}") from exc
        live_field_map = {
            "achieved_signed_offset_m": self._a2_hold_oracle_offset_achieved_signed_offset_m,
            "signed_offset_error_m": self._a2_hold_oracle_offset_signed_offset_error_m,
            "orthogonal_residual_m": self._a2_hold_oracle_offset_orthogonal_residual_m,
            "position_residual_m": self._a2_hold_oracle_offset_position_residual_m,
            "orientation_residual_rad": self._a2_hold_oracle_offset_orientation_residual_rad,
        }
        for name, destination in live_field_map.items():
            destination[placement_env_ids] = live_metrics[name]
        door_joint_pos = self._get_door_joint_pos("A2 offset placement", 2)
        self._a2_hold_oracle_offset_hinge_joint_delta[placement_mask] = (
            door_joint_pos[placement_mask, 0]
            - self._a2_hold_oracle_offset_hinge_joint_start[placement_mask]
        )
        self._a2_hold_oracle_offset_handle_joint_delta[placement_mask] = (
            door_joint_pos[placement_mask, 1]
            - self._a2_hold_oracle_offset_handle_joint_start[placement_mask]
        )
        return a_raw

    def _apply_a2_offset_probe_action(
        self,
        policy_action: torch.Tensor,
        first_episode_active_mask: torch.Tensor,
        activate: torch.Tensor,
    ):
        cfg = self._a2_hold_oracle_cfg
        self._a2_hold_oracle_a_raw.zero_()
        placement_state = a2_hold_offset_placement_step_masks(
            True,
            activate,
            first_episode_active_mask,
            self._a2_hold_oracle_offset_placement_active,
            self._a2_hold_oracle_offset_placement_action_count,
            cfg["static_clamp_offset_placement_steps"],
        )
        self._a2_hold_oracle_offset_placement_active[:] = placement_state["active"]
        self._a2_hold_oracle_offset_placement_action_count[:] = placement_state[
            "action_count"
        ]
        self._a2_hold_oracle_phase_step[placement_state["override"]] = placement_state[
            "action_count"
        ][placement_state["override"]]
        self._finish_a2_offset_placement(placement_state["incomplete"])
        endpoint_mask = placement_state["endpoint_check"]
        endpoint_result = self._snapshot_a2_offset_placement_state(endpoint_mask)
        converged = endpoint_result["converged"]
        if torch.any(endpoint_mask):
            self._a2_hold_oracle_offset_endpoint_checked[endpoint_mask] = True
            self._a2_hold_oracle_offset_final_placement_action_count[endpoint_mask] = (
                self._a2_hold_oracle_offset_placement_action_count[endpoint_mask]
            )
            self._a2_hold_oracle_offset_placement_active[endpoint_mask] = False
            self._a2_hold_oracle_offset_placement_action_count[endpoint_mask] = 0
            self._a2_hold_oracle_offset_placement_validated[converged] = True
            self._set_a2_hold_outcome(
                endpoint_mask & ~converged, "PLACEMENT_NOT_CONVERGED"
            )

        static_state = a2_hold_static_clamp_step_masks(
            True,
            converged,
            first_episode_active_mask,
            self._a2_hold_oracle_static_clamp_active,
            self._a2_hold_oracle_static_clamp_write_count,
            cfg["static_clamp_steps"],
        )
        self._apply_a2_static_clamp_gains(static_state["entering"])
        self._a2_hold_oracle_static_clamp_active[:] = static_state["active"]
        self._a2_hold_oracle_static_clamp_write_count[:] = static_state[
            "write_count"
        ]
        self._a2_hold_oracle_phase_step[static_state["override"]] = static_state[
            "write_count"
        ][static_state["override"]]
        self._finish_a2_static_clamp(
            static_state["complete"] | static_state["incomplete"]
        )

        action = policy_action
        placement_override = placement_state["override"]
        if torch.any(placement_override):
            arm_raw = self._compute_a2_offset_placement_arm_raw(placement_override)
            action = a2_hold_apply_offset_placement_action(
                action, placement_override, arm_raw
            )
        action = a2_hold_apply_static_clamp_action(action, static_state["override"])
        combined_override = placement_override | static_state["override"]
        if torch.any(placement_override & static_state["override"]):
            raise RuntimeError("A2 offset placement and clamp overrides cannot overlap.")
        if torch.any(self._a2_hold_oracle_a_raw[~placement_override] != 0.0):
            raise RuntimeError(
                "A2 offset applied-arm telemetry must be zero outside placement DLS."
            )
        if torch.any(combined_override) and not torch.equal(
            action[combined_override, 5:11],
            self._a2_hold_oracle_a_raw[combined_override],
        ):
            raise RuntimeError(
                "A2 offset controlled arm action disagrees with applied-arm telemetry."
            )
        self._a2_hold_oracle_offset_placement_branch[:] = placement_override
        self._a2_hold_oracle_arm_dls_branch[:] = placement_override
        self._a2_hold_oracle_base_relief_branch_applied.zero_()
        self._a2_hold_oracle_phase_sign_check_due.zero_()
        self._a2_hold_oracle_last_override_mask = combined_override.clone()
        self._a2_hold_oracle_post_override_action = action
        return action, combined_override

    def apply_a2_eval_hold_oracle_action_override(
        self, policy_action: torch.Tensor, first_episode_active_mask: torch.Tensor
    ):
        cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if cfg is None:
            raise RuntimeError("A2 hold oracle action requested before initialization.")
        if not cfg["enabled"]:
            self._a2_hold_oracle_last_override_mask.zero_()
            self._a2_hold_oracle_post_override_action = policy_action
            return policy_action, self._a2_hold_oracle_last_override_mask
        if not self._use_a2_base or not getattr(self, "is_evaluating", False):
            raise RuntimeError("A2 hold oracle action override requires an evaluating A2 env.")
        layout = self.get_a2_high_level_action_layout()
        if tuple(policy_action.shape) != (self.num_envs, layout["dim"]):
            raise RuntimeError("A2 hold oracle policy action shape mismatch.")
        if (
            not torch.is_tensor(first_episode_active_mask)
            or tuple(first_episode_active_mask.shape) != (self.num_envs,)
            or first_episode_active_mask.dtype != torch.bool
            or first_episode_active_mask.device != policy_action.device
        ):
            raise RuntimeError("A2 hold oracle first-episode mask contract mismatch.")

        close_gate = self._get_a2_stage2_close_reward_gate()
        wait_mask = self._a2_hold_oracle_phase == A2_HOLD_PHASE_WAIT_GATE
        activate = (
            wait_mask
            & first_episode_active_mask
            & (self.stage_buf == self.STAGE_GRASP)
            & close_gate
        )
        if cfg["matched_clean_reacquisition_preflight_enabled"]:
            return self._apply_a2_matched_clean_reacquisition_action(
                policy_action, first_episode_active_mask, activate
            )
        if torch.any(activate):
            handoff_frames = self._get_a2_hold_oracle_world_frames()
            (
                updated_relative_quat,
                updated_captured_mask,
            ) = a2_hold_capture_handoff_relative_orientation(
                handoff_frames["handle_pos_w"],
                handoff_frames["handle_quat_w"],
                handoff_frames["source_pos_w"],
                handoff_frames["source_quat_w"],
                activate,
                self._a2_hold_oracle_handoff_relative_quat,
                self._a2_hold_oracle_handoff_orientation_captured,
            )
            self._a2_hold_oracle_handoff_relative_quat = updated_relative_quat
            self._a2_hold_oracle_handoff_orientation_captured = updated_captured_mask
            if cfg["static_clamp_offset_probe_enabled"]:
                self._capture_a2_offset_gate(activate)
        self._a2_hold_oracle_phase[activate] = A2_HOLD_PHASE_CENTER_CLOSE
        self._a2_hold_oracle_phase_step[activate] = 0
        self._a2_hold_oracle_activated[activate] = True
        self._a2_hold_oracle_phase_arm_dls_count[activate] = 0
        self._a2_hold_oracle_phase_sign_checked[activate] = False
        self._a2_hold_oracle_phase_sign_check_due[activate] = False

        ended_without_gate = wait_mask & ~first_episode_active_mask
        self._set_a2_hold_outcome(ended_without_gate, "NO_GATE")
        if cfg["open_stabilization_preflight_enabled"]:
            return self._apply_a2_open_stabilization_action(
                policy_action, first_episode_active_mask, activate
            )
        if cfg["static_clamp_offset_probe_enabled"]:
            return self._apply_a2_offset_probe_action(
                policy_action, first_episode_active_mask, activate
            )
        if cfg["static_clamp_enabled"]:
            static_state = a2_hold_static_clamp_step_masks(
                True,
                activate,
                first_episode_active_mask,
                self._a2_hold_oracle_static_clamp_active,
                self._a2_hold_oracle_static_clamp_write_count,
                cfg["static_clamp_steps"],
            )
            self._apply_a2_static_clamp_gains(static_state["entering"])
            self._a2_hold_oracle_static_clamp_active[:] = static_state["active"]
            self._a2_hold_oracle_static_clamp_write_count[:] = static_state[
                "write_count"
            ]
            self._a2_hold_oracle_phase_step[static_state["override"]] = static_state[
                "write_count"
            ][static_state["override"]]
            finish_mask = static_state["complete"] | static_state["incomplete"]
            self._finish_a2_static_clamp(finish_mask)
            action = a2_hold_apply_static_clamp_action(
                policy_action, static_state["override"]
            )
            self._a2_hold_oracle_arm_dls_branch.zero_()
            self._a2_hold_oracle_base_relief_branch_applied.zero_()
            self._a2_hold_oracle_phase_sign_check_due.zero_()
            self._a2_hold_oracle_last_override_mask = static_state["override"].clone()
            self._a2_hold_oracle_post_override_action = action
            return action, self._a2_hold_oracle_last_override_mask
        active = (
            self._a2_hold_oracle_activated
            & first_episode_active_mask
            & (self._a2_hold_oracle_phase != A2_HOLD_PHASE_DONE)
            & (self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"])
        )
        action = a2_hold_action_with_exact_disabled_equivalence(policy_action, active)
        if not torch.any(active):
            self._clear_a2_hold_base_relief_state(torch.ones_like(active))
            self._a2_hold_oracle_arm_dls_branch.zero_()
            self._a2_hold_oracle_phase_sign_check_due.zero_()
            self._a2_hold_oracle_last_override_mask = active
            self._a2_hold_oracle_post_override_action = action
            return action, active

        bilateral_gate, contact_masks = self._a2_hold_bilateral_gate()
        self._a2_hold_oracle_last_single_body7[active] = contact_masks[
            "single_contact_arm_body7_current"
        ][active]
        self._a2_hold_oracle_last_single_body8[active] = contact_masks[
            "single_contact_arm_body8_current"
        ][active]
        center = active & (self._a2_hold_oracle_phase == A2_HOLD_PHASE_CENTER_CLOSE)
        current_center_pose_state = self._get_a2_hold_oracle_pose_state(
            torch.zeros(self.num_envs, 3, device=self.device),
            active,
        )
        center_converged = a2_hold_center_converged(
            current_center_pose_state["position_residual"],
            current_center_pose_state["orientation_residual"],
            cfg["center_position_tolerance_m"],
            cfg["center_orientation_tolerance_rad"],
        )
        center_ready, tracking_failure, wedge, center_no_bilateral = (
            a2_hold_center_transition_masks(
                center,
                bilateral_gate,
                self._a2_hold_oracle_phase_step,
                cfg["center_timeout_steps"],
                contact_masks["single_contact_arm_body7_current"],
                contact_masks["single_contact_arm_body8_current"],
                center_converged,
            )
        )
        door_joint_pos = self._get_door_joint_pos("A2 hold oracle", 2)
        self._a2_hold_oracle_phase[center_ready] = A2_HOLD_PHASE_DEPRESS
        self._a2_hold_oracle_phase_step[center_ready] = 0
        self._a2_hold_oracle_phase_arm_dls_count[center_ready] = 0
        self._a2_hold_oracle_phase_sign_checked[center_ready] = False
        self._a2_hold_oracle_phase_sign_check_due[center_ready] = False
        self._a2_hold_oracle_handle_start[center_ready] = door_joint_pos[center_ready, 1]
        self._set_a2_hold_outcome(tracking_failure, "IK_TRACKING_FAILURE")
        self._set_a2_hold_outcome(wedge, "UNILATERAL_WEDGE")
        self._set_a2_hold_outcome(center_no_bilateral, "CENTER_NO_BILATERAL")

        depress = active & (self._a2_hold_oracle_phase == A2_HOLD_PHASE_DEPRESS)
        depress_delta = door_joint_pos[:, 1] - self._a2_hold_oracle_handle_start
        self._a2_hold_oracle_slip_steps[depress] = torch.where(
            bilateral_gate[depress],
            torch.zeros_like(self._a2_hold_oracle_slip_steps[depress]),
            self._a2_hold_oracle_slip_steps[depress] + 1,
        )
        slipped = depress & (
            self._a2_hold_oracle_slip_steps >= cfg["contact_slip_grace_steps"]
        )
        self._set_a2_hold_outcome(slipped, "CONTACT_SLIP")
        depress_reached_target = depress & (
            door_joint_pos[:, 1] >= cfg["handle_target_rad"]
        )
        depress_done = a2_hold_depress_transition_mask(
            depress,
            depress_reached_target,
            self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"],
        )
        self._a2_hold_oracle_phase[depress_done] = A2_HOLD_PHASE_FOLLOW_PUSH
        self._a2_hold_oracle_phase_step[depress_done] = 0
        self._a2_hold_oracle_phase_arm_dls_count[depress_done] = 0
        self._a2_hold_oracle_phase_sign_checked[depress_done] = False
        self._a2_hold_oracle_phase_sign_check_due[depress_done] = False
        self._a2_hold_oracle_hinge_start[depress_done] = door_joint_pos[depress_done, 0]
        depress_timeout = a2_hold_depress_timeout_mask(
            depress,
            depress_reached_target,
            self._a2_hold_oracle_phase_step,
            cfg["depress_timeout_steps"],
        )
        self._set_a2_hold_outcome(depress_timeout, "DEPRESS_TIMEOUT")

        push = active & (self._a2_hold_oracle_phase == A2_HOLD_PHASE_FOLLOW_PUSH)
        hinge_delta = door_joint_pos[:, 0] - self._a2_hold_oracle_hinge_start
        self._a2_hold_oracle_last_hinge_delta[push] = hinge_delta[push]
        self._a2_hold_oracle_slip_steps[push] = torch.where(
            bilateral_gate[push],
            torch.zeros_like(self._a2_hold_oracle_slip_steps[push]),
            self._a2_hold_oracle_slip_steps[push] + 1,
        )
        push_slip = push & (
            self._a2_hold_oracle_slip_steps >= cfg["contact_slip_grace_steps"]
        )
        self._set_a2_hold_outcome(push_slip, "CONTACT_SLIP")
        push_progress = push & (hinge_delta >= cfg["hinge_progress_target_rad"])
        self._set_a2_hold_outcome(push_progress & bilateral_gate, "RETAINED")
        self._set_a2_hold_outcome(push_progress & ~bilateral_gate, "PUSH_PROGRESS")
        push_no_progress, push_timeout = a2_hold_push_timeout_masks(
            push,
            push_progress,
            self._a2_hold_oracle_phase_step,
            cfg["push_timeout_steps"],
            hinge_delta,
            cfg["sign_min_delta"],
        )
        self._set_a2_hold_outcome(
            push_no_progress,
            "PUSH_NO_PROGRESS",
        )
        self._set_a2_hold_outcome(
            push_timeout,
            "PUSH_TIMEOUT",
        )

        active = (
            self._a2_hold_oracle_activated
            & first_episode_active_mask
            & (self._a2_hold_oracle_phase != A2_HOLD_PHASE_DONE)
            & (self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"])
        )
        local_offset = torch.zeros(self.num_envs, 3, device=self.device)
        phase_fraction = (
            self._a2_hold_oracle_phase_step.to(torch.float)
            / float(cfg["offset_ramp_steps"])
        ).clamp(max=1.0)
        depress = active & (self._a2_hold_oracle_phase == A2_HOLD_PHASE_DEPRESS)
        push = active & (self._a2_hold_oracle_phase == A2_HOLD_PHASE_FOLLOW_PUSH)
        local_offset[depress, 1] = -cfg["depress_offset_m"] * phase_fraction[depress]
        local_offset[push, 1] = -cfg["depress_offset_m"]
        local_offset[push, 2] = cfg["push_offset_m"] * phase_fraction[push]
        (
            q_des,
            ik_valid,
            singular_values,
            jacobian_condition,
            target_pos_root,
            target_quat_root,
            pos_res,
            rot_res,
            bounded_command_pos_root,
            bounded_command_quat_root,
            bounded_position_step,
            bounded_orientation_step,
            horizontal_error_w,
            root_xy_w,
            root_quat_w,
        ) = self._compute_a2_hold_oracle_joint_target(local_offset, active)
        robot = self.simulator.scene.articulations["robot"]
        joint_ids = self._a2_hold_oracle_joint_ids
        hard_limits = robot.data.joint_pos_limits[:, joint_ids]
        soft_limits = robot.data.soft_joint_pos_limits[:, joint_ids]
        if not torch.all(torch.isfinite(hard_limits)) or not torch.all(torch.isfinite(soft_limits)):
            raise RuntimeError("A2 hold oracle requires finite hard and soft arm joint limits.")
        limit_valid, _, _ = a2_hold_progress_aware_joint_limit_masks(
            robot.data.joint_pos[:, joint_ids],
            q_des,
            hard_limits,
            soft_limits,
            cfg["joint_limit_margin"],
            cfg["joint_limit_margin"],
            cfg["soft_limit_progress_tolerance"],
        )
        q_default = robot.data.default_joint_pos[:, joint_ids]
        if q_default.shape[0] == 1:
            q_default = q_default.repeat(self.num_envs, 1)
        d_prev = self._delta_actions.clone()
        if not torch.all(torch.isfinite(q_default)) or not torch.all(torch.isfinite(d_prev)):
            raise RuntimeError("A2 hold oracle requires finite q_default and pre-step delta buffer.")
        d_des, a_raw = a2_hold_absolute_target_to_cumulative_action(
            q_des, q_default, d_prev
        )
        if not torch.all(torch.isfinite(d_des)) or not torch.all(torch.isfinite(a_raw)):
            raise RuntimeError("A2 hold oracle cumulative conversion returned non-finite values.")
        delta_ok = torch.all(torch.abs(d_des) <= 15.0, dim=-1)
        raw_ok = torch.all(torch.abs(a_raw) <= cfg["raw_action_abs_max"], dim=-1)
        relief_candidate = active & ik_valid & ~limit_valid
        (
            horizontal_residual,
            horizontal_solvable,
            relief_body_velocity,
            relief_base_raw,
        ) = a2_hold_base_relief_command(
            horizontal_error_w,
            root_quat_w,
            relief_candidate,
            cfg["base_relief_speed_mps"],
            self._a2_base_command_scale,
            cfg["base_relief_min_solvable_horizontal_error_m"],
        )
        (
            arm_dls_mask,
            relief_mask,
            ik_invalid_mask,
            joint_limit_mask,
            action_invalid_mask,
        ) = a2_hold_base_relief_branch_masks(
            active,
            ik_valid,
            limit_valid,
            delta_ok,
            raw_ok,
            horizontal_solvable,
        )
        relief_state = a2_hold_update_base_relief_state(
            relief_mask,
            self._a2_hold_oracle_base_relief_active,
            self._a2_hold_oracle_base_relief_steps,
            self._a2_hold_oracle_base_relief_initial_horizontal_residual,
            self._a2_hold_oracle_base_relief_start_root_xy,
            horizontal_residual,
            root_xy_w,
            cfg["base_relief_sign_window_steps"],
            cfg["base_relief_min_residual_decrease_m"],
            cfg["base_relief_timeout_steps"],
            cfg["base_relief_max_displacement_m"],
        )
        self._a2_hold_oracle_base_relief_active[:] = relief_state["active"]
        self._a2_hold_oracle_base_relief_steps[:] = relief_state["steps"]
        self._a2_hold_oracle_base_relief_initial_horizontal_residual[:] = relief_state[
            "initial_residual"
        ]
        self._a2_hold_oracle_base_relief_start_root_xy[:] = relief_state["start_root_xy"]
        self._a2_hold_oracle_base_relief_current_horizontal_residual[:] = relief_state[
            "current_residual"
        ]
        self._a2_hold_oracle_base_relief_ever_entered |= relief_state["entered"]
        self._set_a2_hold_outcome(ik_invalid_mask, "IK_INVALID")
        self._set_a2_hold_outcome(joint_limit_mask, "JOINT_LIMIT")
        self._set_a2_hold_outcome(action_invalid_mask, "IK_INVALID")
        self._set_a2_hold_outcome(
            relief_state["displacement_limit"], "BASE_RELIEF_DISPLACEMENT_LIMIT"
        )
        self._set_a2_hold_outcome(relief_state["wrong_sign"], "BASE_RELIEF_WRONG_SIGN")
        self._set_a2_hold_outcome(relief_state["timeout"], "BASE_RELIEF_TIMEOUT")
        relief_failure = (
            relief_state["displacement_limit"]
            | relief_state["wrong_sign"]
            | relief_state["timeout"]
        )
        self._clear_a2_hold_base_relief_state(relief_failure)
        pending = self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
        arm_dls_mask &= pending
        relief_mask &= pending
        sign_phase_mask = (depress | push) & pending
        sign_progress_delta = torch.where(depress, depress_delta, hinge_delta)
        phase_sign_state = a2_hold_update_phase_arm_sign_check(
            sign_phase_mask,
            arm_dls_mask,
            self._a2_hold_oracle_phase_arm_dls_count,
            self._a2_hold_oracle_phase_sign_checked,
            sign_progress_delta,
            cfg["sign_smoke_steps"],
            cfg["sign_min_delta"],
        )
        self._a2_hold_oracle_phase_arm_dls_count[:] = phase_sign_state["count"]
        self._a2_hold_oracle_phase_sign_checked[:] = phase_sign_state["checked"]
        self._a2_hold_oracle_phase_sign_check_due[:] = phase_sign_state["due"]
        self._set_a2_hold_outcome(
            phase_sign_state["wrong_sign"] & depress, "DEPRESS_WRONG_SIGN"
        )
        self._set_a2_hold_outcome(
            phase_sign_state["wrong_sign"] & push, "PUSH_WRONG_SIGN"
        )
        pending = self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
        arm_dls_mask &= pending
        relief_mask &= pending
        action, override_mask = a2_hold_apply_oracle_branch_actions(
            action,
            arm_dls_mask,
            relief_mask,
            a_raw,
            relief_base_raw,
            (layout["base_start"], layout["base_end"]),
            (layout["arm_start"], layout["arm_end"]),
            layout["gripper_index"],
        )
        applied_arm_raw = torch.zeros_like(a_raw)
        applied_arm_raw[arm_dls_mask] = a_raw[arm_dls_mask]
        applied_base_raw = torch.zeros_like(relief_base_raw)
        applied_base_raw[relief_mask] = relief_base_raw[relief_mask]
        applied_body_velocity = torch.zeros_like(relief_body_velocity)
        applied_body_velocity[relief_mask] = relief_body_velocity[relief_mask]
        self._a2_hold_oracle_q_des[:] = q_des
        self._a2_hold_oracle_d_des[:] = d_des
        self._a2_hold_oracle_d_prev[:] = d_prev
        self._a2_hold_oracle_arm_candidate_action_raw[:] = a_raw
        self._a2_hold_oracle_a_raw[:] = applied_arm_raw
        self._a2_hold_oracle_target_pos_root[:] = target_pos_root
        self._a2_hold_oracle_target_quat_root[:] = target_quat_root
        self._a2_hold_oracle_bounded_command_pos_root[:] = bounded_command_pos_root
        self._a2_hold_oracle_bounded_command_quat_root[:] = bounded_command_quat_root
        self._a2_hold_oracle_bounded_position_step[:] = bounded_position_step
        self._a2_hold_oracle_bounded_orientation_step[:] = bounded_orientation_step
        self._a2_hold_oracle_position_residual[:] = pos_res
        self._a2_hold_oracle_orientation_residual[:] = rot_res
        self._a2_hold_oracle_singular_values[:] = singular_values
        self._a2_hold_oracle_jacobian_condition[:] = jacobian_condition
        self._a2_hold_oracle_ik_valid[:] = ik_valid
        self._a2_hold_oracle_limit_valid[:] = limit_valid
        self._a2_hold_oracle_delta_ok[:] = delta_ok
        self._a2_hold_oracle_raw_ok[:] = raw_ok
        self._a2_hold_oracle_horizontal_residual[:] = horizontal_residual
        self._a2_hold_oracle_base_relief_body_velocity_command[:] = applied_body_velocity
        self._a2_hold_oracle_base_relief_raw_command[:] = applied_base_raw
        self._a2_hold_oracle_arm_dls_branch[:] = arm_dls_mask
        self._a2_hold_oracle_base_relief_branch_applied[:] = relief_mask
        self._a2_hold_oracle_phase_step[override_mask] += 1
        self._a2_hold_oracle_last_override_mask = override_mask.detach().clone()
        self._a2_hold_oracle_post_override_action = action.detach().clone()
        return action, override_mask

    def _get_a2_hold_oracle_trace_fields(self, env_ids: torch.Tensor):
        cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if cfg is None or not cfg["enabled"]:
            return [{} for _ in env_ids.tolist()]
        post_action = self._a2_hold_oracle_post_override_action
        if not torch.is_tensor(post_action):
            raise RuntimeError("A2 hold oracle trace requires post-oracle action.")
        if cfg["matched_clean_reacquisition_preflight_enabled"]:
            self._capture_a2_matched_clean_release_post_action_samples()
            self._capture_a2_matched_clean_stabilize_post_action_samples()
        if cfg["open_stabilization_preflight_enabled"]:
            self._capture_a2_open_stabilization_post_action_samples()
        if cfg["static_clamp_offset_probe_enabled"]:
            self._refresh_a2_offset_live_telemetry(
                self._a2_hold_oracle_offset_placement_branch
                | self._a2_hold_oracle_static_clamp_active
                | self._a2_hold_oracle_static_clamp_gain_applied
            )
        robot = self.simulator.scene.articulations["robot"]
        actual_target = robot.data.joint_pos_target[:, self._a2_hold_oracle_joint_ids]
        records = []
        for env_id in env_ids.tolist():
            outcome_id = int(self._a2_hold_oracle_outcome[env_id].item())
            phase_id = int(self._a2_hold_oracle_phase[env_id].item())
            if (
                cfg["matched_clean_reacquisition_preflight_enabled"]
                and self._a2_hold_oracle_matched_clean_release_override_mask[env_id].item()
            ):
                control_branch = "MATCHED_CLEAN_RELEASE_RETREAT"
            elif (
                cfg["matched_clean_reacquisition_preflight_enabled"]
                and self._a2_hold_oracle_matched_clean_stabilize_override_mask[env_id].item()
            ):
                control_branch = "MATCHED_CLEAN_STABILIZE"
            elif (
                cfg["open_stabilization_preflight_enabled"]
                and self._a2_hold_oracle_last_override_mask[env_id].item()
            ):
                control_branch = "ARM0_OPEN_STABILIZATION"
            elif self._a2_hold_oracle_offset_placement_branch[env_id].item():
                control_branch = "OFFSET_PLACE"
            elif (
                cfg["static_clamp_enabled"]
                and self._a2_hold_oracle_last_override_mask[env_id].item()
            ):
                control_branch = "STATIC_CLAMP"
            elif self._a2_hold_oracle_arm_dls_branch[env_id].item():
                control_branch = "ARM_DLS"
            elif self._a2_hold_oracle_base_relief_branch_applied[env_id].item():
                control_branch = "BASE_RELIEF"
            else:
                control_branch = "NONE"
            records.append(
                {
                    "hold_oracle_tcp_offset_z": cfg["tcp_offset_z"],
                    "hold_oracle_tcp_offset_label": (
                        "measured finger-collider longitudinal midpoint"
                        if cfg["tcp_offset_z"] == 0.09755
                        else "configured longitudinal TCP"
                    ),
                    "hold_oracle_target_orientation_semantic": (
                        a2_hold_target_orientation_semantic(
                            cfg["static_clamp_offset_probe_enabled"],
                            cfg["matched_clean_reacquisition_preflight_enabled"],
                        )
                    ),
                    "hold_oracle_handoff_orientation_captured": bool(
                        self._a2_hold_oracle_handoff_orientation_captured[env_id].item()
                    ),
                    "hold_oracle_handoff_handle_to_gripper_relative_quat_wxyz": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_handoff_relative_quat[env_id]
                        )
                    ),
                    "hold_oracle_phase": A2_HOLD_PHASE_NAMES[phase_id],
                    "hold_oracle_phase_step": int(self._a2_hold_oracle_phase_step[env_id].item()),
                    "hold_oracle_phase_arm_dls_actuation_count": int(
                        self._a2_hold_oracle_phase_arm_dls_count[env_id].item()
                    ),
                    "hold_oracle_phase_sign_checked": bool(
                        self._a2_hold_oracle_phase_sign_checked[env_id].item()
                    ),
                    "hold_oracle_phase_sign_check_due_this_step": bool(
                        self._a2_hold_oracle_phase_sign_check_due[env_id].item()
                    ),
                    "hold_oracle_phase_sign_counter_semantic": (
                        "completed_prior_arm_dls_writes_checked_before_current_write"
                    ),
                    "hold_oracle_outcome": A2_HOLD_OUTCOME_NAMES[outcome_id],
                    "hold_oracle_override_applied": bool(self._a2_hold_oracle_last_override_mask[env_id].item()),
                    "post_hold_oracle_override_pre_env_action": post_action[env_id].detach().cpu().tolist(),
                    "hold_oracle_q_des": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_q_des[env_id]
                    ),
                    "hold_oracle_d_des": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_d_des[env_id]
                    ),
                    "hold_oracle_d_prev": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_d_prev[env_id]
                    ),
                    "hold_oracle_arm_action_raw": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_a_raw[env_id]
                    ),
                    "hold_oracle_arm_candidate_action_raw": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_arm_candidate_action_raw[env_id]
                    ),
                    "hold_oracle_control_branch": control_branch,
                    "hold_oracle_open_stabilization_enabled": cfg[
                        "open_stabilization_preflight_enabled"
                    ],
                    "hold_oracle_open_stabilization_active": bool(
                        self._a2_hold_oracle_open_stabilization_active[env_id].item()
                    ),
                    "hold_oracle_open_stabilization_action_count": int(
                        self._a2_hold_oracle_open_stabilization_action_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_open_stabilization_final_action_count": int(
                        self._a2_hold_oracle_open_stabilization_final_action_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_open_stabilization_gate_captured": bool(
                        self._a2_hold_oracle_open_stabilization_gate_captured[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_open_stabilization_captured_arm_target": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_open_stabilization_arm_target_capture[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_open_stabilization_latest_sample": (
                        self._a2_hold_oracle_open_stabilization_samples[env_id][-1]
                        if self._a2_hold_oracle_open_stabilization_samples[env_id]
                        else None
                    ),
                    "hold_oracle_matched_clean_reacquisition_enabled": cfg[
                        "matched_clean_reacquisition_preflight_enabled"
                    ],
                    "hold_oracle_matched_clean_release_action_count": int(
                        self._a2_hold_oracle_matched_clean_release_action_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_matched_clean_release_final_action_count": int(
                        self._a2_hold_oracle_matched_clean_release_final_action_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_matched_clean_release_qualification_count": int(
                        self._a2_hold_oracle_matched_clean_qualification_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_matched_clean_stabilize_action_count": int(
                        self._a2_hold_oracle_matched_clean_stabilize_action_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_matched_clean_stabilize_final_action_count": int(
                        self._a2_hold_oracle_matched_clean_stabilize_final_action_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_matched_clean_gate_lost_ever": bool(
                        self._a2_hold_oracle_matched_clean_gate_lost_ever[env_id].item()
                    ),
                    "hold_oracle_matched_clean_captured_arm_target": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_matched_clean_captured_arm_target[env_id]
                    ),
                    "hold_oracle_matched_clean_release_latest_sample": (
                        self._a2_hold_oracle_matched_clean_samples[env_id][-1]
                        if self._a2_hold_oracle_matched_clean_samples[env_id]
                        else None
                    ),
                    "hold_oracle_matched_clean_stabilize_latest_sample": (
                        self._a2_hold_oracle_matched_clean_quiet_samples[env_id][-1]
                        if self._a2_hold_oracle_matched_clean_quiet_samples[env_id]
                        else None
                    ),
                    "hold_oracle_offset_probe_enabled": cfg[
                        "static_clamp_offset_probe_enabled"
                    ],
                    "hold_oracle_offset_factor_label": (
                        "O+"
                        if cfg["static_clamp_offset_m"] > 0.0
                        else ("O-" if cfg["static_clamp_offset_m"] < 0.0 else "O0")
                    ),
                    "hold_oracle_offset_factor_semantic": (
                        "O+ is source local +Y/body8 opening direction; "
                        "O- is source local -Y/body7 opening direction"
                    ),
                    "hold_oracle_offset_state_machine": (
                        "WAIT_GATE->OFFSET_PLACE(20 actions)->PLACEMENT_CHECK"
                        "->STATIC_CLAMP(40 actions)"
                    ),
                    "hold_oracle_offset_phase": (
                        "OFFSET_PLACE"
                        if self._a2_hold_oracle_offset_placement_branch[
                            env_id
                        ].item()
                        else (
                            "STATIC_CLAMP"
                            if self._a2_hold_oracle_static_clamp_gain_applied[
                                env_id
                            ].item()
                            else (
                                "PLACEMENT_CHECK"
                                if self._a2_hold_oracle_offset_endpoint_checked[
                                    env_id
                                ].item()
                                else "WAIT_GATE"
                            )
                        )
                    ),
                    "hold_oracle_offset_requested_m": cfg["static_clamp_offset_m"],
                    "hold_oracle_offset_placement_active": bool(
                        self._a2_hold_oracle_offset_placement_active[env_id].item()
                    ),
                    "hold_oracle_offset_placement_ever_activated": bool(
                        self._a2_hold_oracle_offset_placement_ever_activated[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_offset_placement_branch": bool(
                        self._a2_hold_oracle_offset_placement_branch[env_id].item()
                    ),
                    "hold_oracle_offset_placement_action_count": int(
                        self._a2_hold_oracle_offset_placement_action_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_offset_final_placement_action_count": int(
                        self._a2_hold_oracle_offset_final_placement_action_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_offset_endpoint_checked": bool(
                        self._a2_hold_oracle_offset_endpoint_checked[env_id].item()
                    ),
                    "hold_oracle_offset_placement_validated": bool(
                        self._a2_hold_oracle_offset_placement_validated[env_id].item()
                    ),
                    "hold_oracle_offset_gate_source_pos_w": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_gate_source_pos_w[env_id]
                    ),
                    "hold_oracle_offset_gate_source_quat_w": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_gate_source_quat_w[env_id]
                    ),
                    "hold_oracle_offset_gate_handle_pos_w": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_gate_handle_pos_w[env_id]
                    ),
                    "hold_oracle_offset_gate_handle_quat_w": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_gate_handle_quat_w[env_id]
                    ),
                    "hold_oracle_offset_source_local_y_axis_w": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_source_local_y_axis_w[env_id]
                    ),
                    "hold_oracle_offset_fixed_target_pos_w": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_fixed_target_pos_w[env_id]
                    ),
                    "hold_oracle_offset_fixed_target_quat_w": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_fixed_target_quat_w[env_id]
                    ),
                    "hold_oracle_offset_opening_axis_dots_body7_body8": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_offset_opening_axis_dots_body7_body8[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_offset_achieved_signed_offset_m": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_offset_achieved_signed_offset_m[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_offset_signed_offset_error_m": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_signed_offset_error_m[env_id]
                    ),
                    "hold_oracle_offset_orthogonal_residual_m": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_orthogonal_residual_m[env_id]
                    ),
                    "hold_oracle_offset_position_residual_m": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_position_residual_m[env_id]
                    ),
                    "hold_oracle_offset_orientation_residual_rad": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_offset_orientation_residual_rad[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_offset_root_displacement_m": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_root_displacement_m[env_id]
                    ),
                    "hold_oracle_offset_hinge_joint_delta": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_hinge_joint_delta[env_id]
                    ),
                    "hold_oracle_offset_handle_joint_delta": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_offset_handle_joint_delta[env_id]
                    ),
                    "hold_oracle_offset_base_raw_action": post_action[
                        env_id, :5
                    ].detach().cpu().tolist(),
                    "hold_oracle_static_clamp_enabled": cfg["static_clamp_enabled"],
                    "hold_oracle_static_clamp_active": bool(
                        self._a2_hold_oracle_static_clamp_active[env_id].item()
                    ),
                    "hold_oracle_static_clamp_gain_applied": bool(
                        self._a2_hold_oracle_static_clamp_gain_applied[env_id].item()
                    ),
                    "hold_oracle_static_clamp_ever_activated": bool(
                        self._a2_hold_oracle_static_clamp_ever_activated[env_id].item()
                    ),
                    "hold_oracle_static_clamp_restored": bool(
                        self._a2_hold_oracle_static_clamp_restored[env_id].item()
                    ),
                    "hold_oracle_static_clamp_action_write_count": int(
                        self._a2_hold_oracle_static_clamp_write_count[env_id].item()
                    ),
                    "hold_oracle_static_clamp_final_action_write_count": int(
                        self._a2_hold_oracle_static_clamp_final_write_count[
                            env_id
                        ].item()
                    ),
                    "hold_oracle_static_clamp_original_stiffness": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_original_stiffness[env_id]
                        )
                    ),
                    "hold_oracle_static_clamp_original_damping": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_original_damping[env_id]
                        )
                    ),
                    "hold_oracle_static_clamp_original_effort_limit": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_original_effort_limit[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_static_clamp_requested_stiffness": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_requested_stiffness[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_static_clamp_requested_damping": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_requested_damping[env_id]
                        )
                    ),
                    "hold_oracle_static_clamp_applied_stiffness": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_applied_stiffness[env_id]
                        )
                    ),
                    "hold_oracle_static_clamp_applied_damping": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_applied_damping[env_id]
                        )
                    ),
                    "hold_oracle_static_clamp_applied_effort_limit": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_applied_effort_limit[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_static_clamp_restored_stiffness": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_restored_stiffness[env_id]
                        )
                    ),
                    "hold_oracle_static_clamp_restored_damping": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_restored_damping[env_id]
                        )
                    ),
                    "hold_oracle_static_clamp_restored_effort_limit": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_static_clamp_restored_effort_limit[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_arm_limit_valid": bool(
                        self._a2_hold_oracle_limit_valid[env_id].item()
                    ),
                    "hold_oracle_horizontal_residual": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_horizontal_residual[env_id]
                    ),
                    "hold_oracle_base_relief_active": bool(
                        self._a2_hold_oracle_base_relief_active[env_id].item()
                    ),
                    "hold_oracle_base_relief_ever_entered": bool(
                        self._a2_hold_oracle_base_relief_ever_entered[env_id].item()
                    ),
                    "hold_oracle_base_relief_steps": int(
                        self._a2_hold_oracle_base_relief_steps[env_id].item()
                    ),
                    "hold_oracle_base_relief_initial_horizontal_residual": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_base_relief_initial_horizontal_residual[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_base_relief_current_horizontal_residual": (
                        a2_hold_nullable_tensor_list(
                            self._a2_hold_oracle_base_relief_current_horizontal_residual[
                                env_id
                            ]
                        )
                    ),
                    "hold_oracle_base_relief_start_root_xy": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_base_relief_start_root_xy[env_id]
                    ),
                    "hold_oracle_base_relief_body_velocity_command": (
                        self._a2_hold_oracle_base_relief_body_velocity_command[env_id]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "hold_oracle_base_relief_raw_command": (
                        self._a2_hold_oracle_base_relief_raw_command[env_id]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "hold_oracle_base_relief_phase_timeout_semantic": (
                        "relief_steps_consume_current_phase_timeout"
                    ),
                    "hold_oracle_actual_joint_pos_target": actual_target[env_id].detach().cpu().tolist(),
                    "hold_oracle_final_target_pos_root": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_target_pos_root[env_id]
                    ),
                    "hold_oracle_final_target_quat_root": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_target_quat_root[env_id]
                    ),
                    "hold_oracle_final_position_residual": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_position_residual[env_id]
                    ),
                    "hold_oracle_final_orientation_residual": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_orientation_residual[env_id]
                    ),
                    "hold_oracle_bounded_command_pos_root": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_bounded_command_pos_root[env_id]
                    ),
                    "hold_oracle_bounded_command_quat_root": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_bounded_command_quat_root[env_id]
                    ),
                    "hold_oracle_bounded_position_step": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_bounded_position_step[env_id]
                    ),
                    "hold_oracle_bounded_orientation_step": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_bounded_orientation_step[env_id]
                    ),
                    "hold_oracle_jacobian_singular_values": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_singular_values[env_id]
                    ),
                    "hold_oracle_jacobian_condition": a2_hold_nullable_tensor_list(
                        self._a2_hold_oracle_jacobian_condition[env_id]
                    ),
                    "hold_oracle_ik_valid": bool(
                        self._a2_hold_oracle_ik_valid[env_id].item()
                    ),
                    "hold_oracle_delta_ok": bool(
                        self._a2_hold_oracle_delta_ok[env_id].item()
                    ),
                    "hold_oracle_raw_ok": bool(
                        self._a2_hold_oracle_raw_ok[env_id].item()
                    ),
                }
            )
        return records

    def get_a2_hold_oracle_summary(self):
        cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if cfg is None or not cfg["enabled"]:
            raise RuntimeError("A2 hold oracle summary requested while oracle is disabled.")
        if cfg["matched_clean_reacquisition_preflight_enabled"]:
            if not self._a2_hold_oracle_finalized:
                raise RuntimeError(
                    "A2 matched-clean summary requires finalized lifecycle state."
                )
            if torch.any(
                self._a2_hold_oracle_matched_clean_release_active
                | self._a2_hold_oracle_matched_clean_stabilize_active
            ):
                raise RuntimeError(
                    "A2 matched-clean summary rejects active preflight state."
                )
            pending = self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
            never_activated_pending = (
                pending & ~self._a2_hold_oracle_matched_clean_ever_activated
            )
            self._a2_hold_oracle_outcome[never_activated_pending] = A2_HOLD_OUTCOME_TO_ID[
                "MATCHED_CLEAN_NO_GATE"
            ]
            pending = self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
            if torch.any(pending):
                raise RuntimeError(
                    "A2 matched-clean summary cannot retain PENDING outcomes for "
                    "activated or otherwise inconsistent environments; "
                    f"envs={torch.nonzero(pending, as_tuple=False).flatten().detach().cpu().tolist()}."
                )
            names = [
                A2_HOLD_OUTCOME_NAMES[int(value)]
                for value in self._a2_hold_oracle_outcome.detach().cpu().tolist()
            ]
            return {
                "config": dict(cfg),
                "preflight": "MATCHED_CLEAN_REACQUISITION",
                "state_machine": (
                    "WAIT_GATE->RELEASE_RETREAT->CLEAN_STABILIZE->READY/STOP"
                ),
                "retreat_action_limit": cfg["matched_clean_retreat_timeout_steps"],
                "release_qualification_consecutive_samples": cfg[
                    "matched_clean_release_qualification_steps"
                ],
                "release_qualification_contract": {
                    "pregrasp_position_residual_max_m": cfg[
                        "matched_clean_pregrasp_position_tolerance_m"
                    ],
                    "pregrasp_orientation_residual_max_rad": cfg[
                        "matched_clean_pregrasp_orientation_tolerance_rad"
                    ],
                    "filtered_normal_force_magnitude_strictly_less_than_n": 1.0,
                    "source_handle_distance_min_m": 0.095,
                },
                "clean_stabilize_actions": 40,
                "runtime_identity": {
                    "tcp_offset_z": cfg["tcp_offset_z"],
                    "friction_override": self._get_a2_hold_friction_override(),
                    "actual_gripper_stiffness": [80.0, 80.0],
                    "actual_gripper_damping": [3.0, 3.0],
                    "actual_gripper_effort_limit": [10.0, 10.0],
                    "dls_lambda": cfg["dls_lambda"],
                    "max_position_step_m": cfg["max_position_step_m"],
                    "max_orientation_step_rad": cfg["max_orientation_step_rad"],
                },
                "quiet_window_contract": {
                    "instantaneous_actions": list(range(36, 41)),
                    "pose_samples": list(range(35, 41)),
                    "gate_lost_is_telemetry_only": True,
                    "contact_terminal_priority": True,
                },
                "terminal_priority": (
                    "MATCHED_CLEAN_STABILIZE_CONTACT_CONTAMINATED>"
                    "MATCHED_CLEAN_READY_OR_NOT_SETTLED>"
                    "MATCHED_CLEAN_STABILIZE_INCOMPLETE"
                ),
                "per_env_outcome": names,
                "outcome_counts": a2_hold_summarize_outcomes(names),
                "per_env_ever_activated": self._a2_hold_oracle_matched_clean_ever_activated.detach()
                .cpu()
                .tolist(),
                "per_env_gate_lost_ever": self._a2_hold_oracle_matched_clean_gate_lost_ever.detach()
                .cpu()
                .tolist(),
                "per_env_release_action_count": self._a2_hold_oracle_matched_clean_release_final_action_count.detach()
                .cpu()
                .tolist(),
                "per_env_release_qualification_count": self._a2_hold_oracle_matched_clean_qualification_count.detach()
                .cpu()
                .tolist(),
                "per_env_release_contact_reset_count": self._a2_hold_oracle_matched_clean_release_contact_reset_count.detach()
                .cpu()
                .tolist(),
                "per_env_stabilize_action_count": self._a2_hold_oracle_matched_clean_stabilize_final_action_count.detach()
                .cpu()
                .tolist(),
                "per_env_captured_accumulated_arm_target": a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_matched_clean_captured_arm_target
                ),
                "per_env_release_qualification_evidence": list(
                    self._a2_hold_oracle_matched_clean_release_qualification_evidence
                ),
                "per_env_release_samples": list(
                    self._a2_hold_oracle_matched_clean_samples
                ),
                "per_env_quiet_samples": list(
                    self._a2_hold_oracle_matched_clean_quiet_samples
                ),
                "per_env_result": list(self._a2_hold_oracle_matched_clean_result),
                "per_env_actual_invariant_evidence": list(
                    self._a2_hold_oracle_matched_clean_actual_invariant_evidence
                ),
                "per_env_reason_contact_contaminated": self._a2_hold_oracle_matched_clean_reason_contact.detach()
                .cpu()
                .tolist(),
                "per_env_reason_timeout": self._a2_hold_oracle_matched_clean_reason_timeout.detach()
                .cpu()
                .tolist(),
                "per_env_reason_incomplete": self._a2_hold_oracle_matched_clean_reason_incomplete.detach()
                .cpu()
                .tolist(),
                "per_env_reason_ready": self._a2_hold_oracle_matched_clean_reason_ready.detach()
                .cpu()
                .tolist(),
                "per_env_reason_not_settled": self._a2_hold_oracle_matched_clean_reason_not_settled.detach()
                .cpu()
                .tolist(),
                "finalize_called": self._a2_hold_oracle_finalized,
            }
        if cfg["open_stabilization_preflight_enabled"]:
            if not self._a2_hold_oracle_finalized:
                raise RuntimeError(
                    "A2 open stabilization summary requires finalized lifecycle state."
                )
            if torch.any(self._a2_hold_oracle_open_stabilization_active):
                raise RuntimeError(
                    "A2 open stabilization summary rejects active preflight state."
                )
            ever = self._a2_hold_oracle_open_stabilization_ever_activated
            final_count = self._a2_hold_oracle_open_stabilization_final_action_count
            if torch.any(ever & ((final_count < 0) | (final_count > 40))):
                raise RuntimeError(
                    "A2 open stabilization summary rejects invalid durable action counts."
                )
            if any(
                ever[env_id].item()
                and self._a2_hold_oracle_open_stabilization_result[env_id] is None
                for env_id in range(self.num_envs)
            ):
                raise RuntimeError(
                    "A2 open stabilization summary requires a durable result for every activated env."
                )
        if cfg["static_clamp_enabled"]:
            if not self._a2_hold_oracle_finalized:
                raise RuntimeError("A2 static clamp summary requires finalized restore state.")
            if torch.any(self._a2_hold_oracle_static_clamp_active) or torch.any(
                self._a2_hold_oracle_static_clamp_gain_applied
            ):
                raise RuntimeError("A2 static clamp summary rejects active/unrestored gains.")
            unrestored = (
                self._a2_hold_oracle_static_clamp_ever_activated
                & ~self._a2_hold_oracle_static_clamp_restored
            )
            if torch.any(unrestored):
                raise RuntimeError("A2 static clamp summary rejects missing exact restore evidence.")
            activated = self._a2_hold_oracle_static_clamp_ever_activated
            final_count = self._a2_hold_oracle_static_clamp_final_write_count
            if torch.any(activated & ((final_count < 0) | (final_count > cfg["static_clamp_steps"]))):
                raise RuntimeError("A2 static clamp summary rejects invalid durable final counts.")
            durable_float_fields = (
                self._a2_hold_oracle_static_clamp_original_stiffness,
                self._a2_hold_oracle_static_clamp_original_damping,
                self._a2_hold_oracle_static_clamp_original_effort_limit,
                self._a2_hold_oracle_static_clamp_requested_stiffness,
                self._a2_hold_oracle_static_clamp_requested_damping,
                self._a2_hold_oracle_static_clamp_applied_stiffness,
                self._a2_hold_oracle_static_clamp_applied_damping,
                self._a2_hold_oracle_static_clamp_applied_effort_limit,
                self._a2_hold_oracle_static_clamp_restored_stiffness,
                self._a2_hold_oracle_static_clamp_restored_damping,
                self._a2_hold_oracle_static_clamp_restored_effort_limit,
            )
            if any(
                not torch.all(torch.isfinite(field[activated]))
                for field in durable_float_fields
            ):
                raise RuntimeError("A2 static clamp summary requires finite durable gain evidence.")
            expected_effort = torch.full_like(
                self._a2_hold_oracle_static_clamp_original_effort_limit[activated],
                10.0,
            )
            expected_requested_stiffness = torch.full_like(
                self._a2_hold_oracle_static_clamp_requested_stiffness[activated],
                cfg["static_clamp_stiffness"],
            )
            expected_requested_damping = torch.full_like(
                self._a2_hold_oracle_static_clamp_requested_damping[activated],
                cfg["static_clamp_damping"],
            )
            if (
                not torch.equal(
                    self._a2_hold_oracle_static_clamp_requested_stiffness[activated],
                    expected_requested_stiffness,
                )
                or not torch.equal(
                    self._a2_hold_oracle_static_clamp_requested_damping[activated],
                    expected_requested_damping,
                )
                or not torch.equal(
                    self._a2_hold_oracle_static_clamp_applied_stiffness[activated],
                    expected_requested_stiffness,
                )
                or not torch.equal(
                    self._a2_hold_oracle_static_clamp_applied_damping[activated],
                    expected_requested_damping,
                )
                or not torch.equal(
                    self._a2_hold_oracle_static_clamp_original_effort_limit[activated],
                    expected_effort,
                )
                or not torch.equal(
                    self._a2_hold_oracle_static_clamp_applied_effort_limit[activated],
                    expected_effort,
                )
                or not torch.equal(
                    self._a2_hold_oracle_static_clamp_restored_effort_limit[activated],
                    expected_effort,
                )
                or not torch.equal(
                    self._a2_hold_oracle_static_clamp_restored_stiffness[activated],
                    self._a2_hold_oracle_static_clamp_original_stiffness[activated],
                )
                or not torch.equal(
                    self._a2_hold_oracle_static_clamp_restored_damping[activated],
                    self._a2_hold_oracle_static_clamp_original_damping[activated],
                )
            ):
                raise RuntimeError("A2 static clamp summary rejects gain/effort restore mismatch.")
        if cfg["static_clamp_offset_probe_enabled"]:
            if torch.any(self._a2_hold_oracle_offset_placement_active) or torch.any(
                self._a2_hold_oracle_offset_placement_action_count != 0
            ):
                raise RuntimeError("A2 offset summary rejects active placement state.")
            placement_ever = self._a2_hold_oracle_offset_placement_ever_activated
            final_placement_count = (
                self._a2_hold_oracle_offset_final_placement_action_count
            )
            invalid_count = placement_ever & (
                (final_placement_count < 0)
                | (
                    final_placement_count
                    > cfg["static_clamp_offset_placement_steps"]
                )
            )
            if torch.any(invalid_count):
                raise RuntimeError("A2 offset summary rejects invalid final placement count.")
            snapshots_present = torch.tensor(
                [
                    value is not None
                    for value in self._a2_hold_oracle_offset_preclamp_snapshot
                ],
                device=self.device,
                dtype=torch.bool,
            )
            checked = self._a2_hold_oracle_offset_endpoint_checked
            validated = self._a2_hold_oracle_offset_placement_validated
            completed_placement = placement_ever & (
                final_placement_count
                == cfg["static_clamp_offset_placement_steps"]
            )
            if torch.any(checked != completed_placement) or torch.any(
                validated & ~checked
            ):
                raise RuntimeError("A2 offset summary rejects endpoint/count mismatch.")
            if torch.any(placement_ever & (snapshots_present != checked)):
                raise RuntimeError(
                    "A2 offset summary requires snapshots exactly for checked endpoints."
                )
            ended_after_placement = (
                self._a2_hold_oracle_outcome
                == A2_HOLD_OUTCOME_TO_ID[
                    "OFFSET_PLACEMENT_COMPLETE_EPISODE_ENDED"
                ]
            )
            clamp_activated = self._a2_hold_oracle_static_clamp_ever_activated
            if torch.any(
                validated & ~(clamp_activated | ended_after_placement)
            ) or torch.any(
                clamp_activated & ~validated
            ) or torch.any(
                ended_after_placement & (~validated | clamp_activated)
            ):
                raise RuntimeError("A2 offset summary rejects placement/gain routing mismatch.")
        pending = self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
        no_gate = pending & ~self._a2_hold_oracle_activated
        self._a2_hold_oracle_outcome[no_gate] = A2_HOLD_OUTCOME_TO_ID["NO_GATE"]
        pending = self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
        center = pending & (self._a2_hold_oracle_phase == A2_HOLD_PHASE_CENTER_CLOSE)
        if torch.any(center):
            converged = a2_hold_center_converged(
                self._a2_hold_oracle_position_residual,
                self._a2_hold_oracle_orientation_residual,
                cfg["center_position_tolerance_m"],
                cfg["center_orientation_tolerance_rad"],
            )
            tracking_failure = center & ~converged
            self._a2_hold_oracle_outcome[tracking_failure] = A2_HOLD_OUTCOME_TO_ID[
                "IK_TRACKING_FAILURE"
            ]
            wedge = center & converged & (
                self._a2_hold_oracle_last_single_body7
                | self._a2_hold_oracle_last_single_body8
            )
            self._a2_hold_oracle_outcome[wedge] = A2_HOLD_OUTCOME_TO_ID[
                "UNILATERAL_WEDGE"
            ]
            self._a2_hold_oracle_outcome[center & converged & ~wedge] = A2_HOLD_OUTCOME_TO_ID[
                "CENTER_NO_BILATERAL"
            ]
        pending = self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
        depress = pending & (self._a2_hold_oracle_phase == A2_HOLD_PHASE_DEPRESS)
        self._a2_hold_oracle_outcome[depress] = A2_HOLD_OUTCOME_TO_ID[
            "DEPRESS_TIMEOUT"
        ]
        pending = self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
        push = pending & (self._a2_hold_oracle_phase == A2_HOLD_PHASE_FOLLOW_PUSH)
        reached = push & (
            self._a2_hold_oracle_last_hinge_delta
            >= cfg["hinge_progress_target_rad"]
        )
        self._a2_hold_oracle_outcome[reached] = A2_HOLD_OUTCOME_TO_ID[
            "PUSH_PROGRESS"
        ]
        no_progress = push & (
            self._a2_hold_oracle_last_hinge_delta < cfg["sign_min_delta"]
        )
        self._a2_hold_oracle_outcome[no_progress] = A2_HOLD_OUTCOME_TO_ID[
            "PUSH_NO_PROGRESS"
        ]
        self._a2_hold_oracle_outcome[push & ~reached & ~no_progress] = (
            A2_HOLD_OUTCOME_TO_ID["PUSH_TIMEOUT"]
        )
        if torch.any(
            self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
        ):
            raise RuntimeError("A2 hold oracle summary cannot retain PENDING outcomes.")
        names = [A2_HOLD_OUTCOME_NAMES[int(value)] for value in self._a2_hold_oracle_outcome.cpu().tolist()]
        if cfg["open_stabilization_preflight_enabled"]:
            if "PENDING" in names:
                raise RuntimeError(
                    "A2 open stabilization summary cannot retain PENDING outcomes."
                )
            return {
                "config": dict(cfg),
                "preflight": "ARM0_OPEN_STABILIZATION_PREFLIGHT",
                "state_machine": (
                    "WAIT_GATE->CONTACT_PREFLIGHT->ACTIONS_1_TO_40"
                    "->INSTANTANEOUS_WINDOW_36_TO_40_AND_POSE_TRANSITIONS_35_TO_40->STOP"
                ),
                "terminal_priority": (
                    "CONTACT_CONTAMINATED>GATE_LOST>READY_OR_NOT_SETTLED>INCOMPLETE"
                ),
                "per_env_outcome": names,
                "outcome_counts": a2_hold_summarize_outcomes(names),
                "per_env_ever_activated": ever.detach().cpu().tolist(),
                "per_env_gate_captured": self._a2_hold_oracle_open_stabilization_gate_captured.detach()
                .cpu()
                .tolist(),
                "per_env_final_action_count": final_count.detach().cpu().tolist(),
                "per_env_gate_root_pos_w": a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_open_stabilization_gate_root_pos_w
                ),
                "per_env_gate_root_quat_w": a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_open_stabilization_gate_root_quat_w
                ),
                "per_env_gate_source_pos_w": a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_open_stabilization_gate_source_pos_w
                ),
                "per_env_gate_source_quat_w": a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_open_stabilization_gate_source_quat_w
                ),
                "per_env_gate_handle_pos_w": a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_open_stabilization_gate_handle_pos_w
                ),
                "per_env_gate_handle_quat_w": a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_open_stabilization_gate_handle_quat_w
                ),
                "per_env_captured_accumulated_arm_target": a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_open_stabilization_arm_target_capture
                ),
                "per_env_reason_contact_contaminated": self._a2_hold_oracle_open_stabilization_reason_contact.detach()
                .cpu()
                .tolist(),
                "per_env_reason_gate_lost": self._a2_hold_oracle_open_stabilization_reason_gate.detach()
                .cpu()
                .tolist(),
                "per_env_reason_incomplete": self._a2_hold_oracle_open_stabilization_reason_incomplete.detach()
                .cpu()
                .tolist(),
                "per_env_reason_ready": self._a2_hold_oracle_open_stabilization_reason_ready.detach()
                .cpu()
                .tolist(),
                "per_env_reason_not_settled": self._a2_hold_oracle_open_stabilization_reason_not_settled.detach()
                .cpu()
                .tolist(),
                "per_env_result": list(
                    self._a2_hold_oracle_open_stabilization_result
                ),
                "per_env_samples": list(
                    self._a2_hold_oracle_open_stabilization_samples
                ),
                "finalize_called": self._a2_hold_oracle_finalized,
            }
        return {
            "config": dict(cfg),
            "tcp_offset_label": (
                "measured finger-collider longitudinal midpoint"
                if cfg["tcp_offset_z"] == 0.09755
                else "configured longitudinal TCP"
            ),
            "per_env_outcome": names,
            "outcome_counts": a2_hold_summarize_outcomes(names),
            "activated_count": int(self._a2_hold_oracle_activated.sum().item()),
            "base_relief_ever_entered_count": int(
                self._a2_hold_oracle_base_relief_ever_entered.sum().item()
            ),
            "per_env_base_relief_ever_entered": (
                self._a2_hold_oracle_base_relief_ever_entered.detach().cpu().tolist()
            ),
            "base_relief_phase_timeout_semantic": (
                "relief_steps_consume_current_phase_timeout"
            ),
            "offset_probe_enabled": cfg["static_clamp_offset_probe_enabled"],
            "offset_factor_label": (
                "O+"
                if cfg["static_clamp_offset_m"] > 0.0
                else ("O-" if cfg["static_clamp_offset_m"] < 0.0 else "O0")
            ),
            "offset_factor_semantic": (
                "O+ source +Y/body8 opening direction; "
                "O- source -Y/body7 opening direction"
            ),
            "offset_state_machine": (
                "WAIT_GATE->OFFSET_PLACE(20 actions)->PLACEMENT_CHECK"
                "->STATIC_CLAMP(40 actions)"
            ),
            "per_env_offset_placement_ever_activated": (
                self._a2_hold_oracle_offset_placement_ever_activated.detach()
                .cpu()
                .tolist()
            ),
            "per_env_offset_final_placement_action_count": (
                self._a2_hold_oracle_offset_final_placement_action_count.detach()
                .cpu()
                .tolist()
            ),
            "per_env_offset_endpoint_checked": (
                self._a2_hold_oracle_offset_endpoint_checked.detach().cpu().tolist()
            ),
            "per_env_offset_placement_validated": (
                self._a2_hold_oracle_offset_placement_validated.detach()
                .cpu()
                .tolist()
            ),
            "per_env_offset_gate_source_pos_w": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_gate_source_pos_w
            ),
            "per_env_offset_gate_source_quat_w": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_gate_source_quat_w
            ),
            "per_env_offset_gate_handle_pos_w": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_gate_handle_pos_w
            ),
            "per_env_offset_gate_handle_quat_w": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_gate_handle_quat_w
            ),
            "per_env_offset_source_local_y_axis_w": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_source_local_y_axis_w
            ),
            "per_env_offset_fixed_target_pos_w": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_fixed_target_pos_w
            ),
            "per_env_offset_fixed_target_quat_w": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_fixed_target_quat_w
            ),
            "per_env_offset_opening_axis_dots_body7_body8": (
                a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_offset_opening_axis_dots_body7_body8
                )
            ),
            "per_env_offset_achieved_signed_offset_m": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_achieved_signed_offset_m
            ),
            "per_env_offset_signed_offset_error_m": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_signed_offset_error_m
            ),
            "per_env_offset_orthogonal_residual_m": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_orthogonal_residual_m
            ),
            "per_env_offset_position_residual_m": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_position_residual_m
            ),
            "per_env_offset_orientation_residual_rad": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_orientation_residual_rad
            ),
            "per_env_offset_root_displacement_m": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_root_displacement_m
            ),
            "per_env_offset_hinge_joint_delta": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_hinge_joint_delta
            ),
            "per_env_offset_handle_joint_delta": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_offset_handle_joint_delta
            ),
            "per_env_offset_preclamp_snapshot": list(
                self._a2_hold_oracle_offset_preclamp_snapshot
            ),
            "static_clamp_ever_activated_count": int(
                self._a2_hold_oracle_static_clamp_ever_activated.sum().item()
            ),
            "per_env_static_clamp_ever_activated": (
                self._a2_hold_oracle_static_clamp_ever_activated.detach().cpu().tolist()
            ),
            "per_env_static_clamp_restored": (
                self._a2_hold_oracle_static_clamp_restored.detach().cpu().tolist()
            ),
            "per_env_static_clamp_final_action_write_count": (
                self._a2_hold_oracle_static_clamp_final_write_count.detach()
                .cpu()
                .tolist()
            ),
            "per_env_static_clamp_original_stiffness": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_static_clamp_original_stiffness
            ),
            "per_env_static_clamp_original_damping": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_static_clamp_original_damping
            ),
            "per_env_static_clamp_original_effort_limit": (
                a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_static_clamp_original_effort_limit
                )
            ),
            "per_env_static_clamp_requested_stiffness": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_static_clamp_requested_stiffness
            ),
            "per_env_static_clamp_requested_damping": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_static_clamp_requested_damping
            ),
            "per_env_static_clamp_applied_stiffness": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_static_clamp_applied_stiffness
            ),
            "per_env_static_clamp_applied_damping": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_static_clamp_applied_damping
            ),
            "per_env_static_clamp_applied_effort_limit": (
                a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_static_clamp_applied_effort_limit
                )
            ),
            "per_env_static_clamp_restored_stiffness": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_static_clamp_restored_stiffness
            ),
            "per_env_static_clamp_restored_damping": a2_hold_nullable_tensor_list(
                self._a2_hold_oracle_static_clamp_restored_damping
            ),
            "per_env_static_clamp_restored_effort_limit": (
                a2_hold_nullable_tensor_list(
                    self._a2_hold_oracle_static_clamp_restored_effort_limit
                )
            ),
            "per_env_static_clamp_step40_snapshot": list(
                self._a2_hold_oracle_static_clamp_step40_snapshot
            ),
            "static_clamp_finalize_called": self._a2_hold_oracle_finalized,
        }

    def _get_a2_hold_detailed_step_fields(self, env_ids: torch.Tensor):
        if not self._get_a2_hold_contact_detail_enabled():
            return [{} for _ in env_ids.tolist()]
        sensor = self.simulator.scene.sensors[self.A2_GRIPPER_HANDLE_CONTACT_SENSOR]
        expected_filters = [
            "/World/envs/env_.*/Robot/arm_body7",
            "/World/envs/env_.*/Robot/arm_body8",
        ]
        if list(sensor.cfg.filter_prim_paths_expr) != expected_filters:
            raise RuntimeError(
                "A2 detailed hold diagnostic filter pair order mismatch: "
                f"expected={expected_filters}, got={list(sensor.cfg.filter_prim_paths_expr)}."
            )
        data = sensor.data
        expected = (self.num_envs, 1, 2, 3)
        contact_pos_w = getattr(data, "contact_pos_w", None)
        friction_w = getattr(data, "friction_forces_w", None)
        force_matrix_w = getattr(data, "force_matrix_w", None)
        for name, value in (
            ("contact_pos_w", contact_pos_w),
            ("friction_forces_w", friction_w),
            ("force_matrix_w", force_matrix_w),
        ):
            if not torch.is_tensor(value) or tuple(value.shape) != expected:
                shape = None if not torch.is_tensor(value) else tuple(value.shape)
                raise RuntimeError(
                    f"A2 detailed hold diagnostics require ContactSensorData.{name} "
                    f"shape {expected}; got {shape}."
                )
        sensor_pos_w = getattr(data, "pos_w", None)
        sensor_quat_w = getattr(data, "quat_w", None)
        if not torch.is_tensor(sensor_pos_w) or tuple(sensor_pos_w.shape) != (self.num_envs, 1, 3):
            raise RuntimeError("A2 detailed hold diagnostics require sensor pos_w shape (N,1,3).")
        if not torch.is_tensor(sensor_quat_w) or tuple(sensor_quat_w.shape) != (self.num_envs, 1, 4):
            raise RuntimeError("A2 detailed hold diagnostics require sensor quat_w shape (N,1,4).")

        normal_force_w = force_matrix_w[:, 0]
        normal_direction_w, normal_direction_valid = (
            a2_hold_aggregate_normal_force_direction(normal_force_w)
        )
        transform_data = self._get_a2_gripper_handle_frame_transformer().data
        source_pos_w = transform_data.source_pos_w
        source_quat_w = transform_data.source_quat_w
        target_pos_w = transform_data.target_pos_w
        target_quat_w = transform_data.target_quat_w
        contact_delta_w = contact_pos_w[:, 0] - source_pos_w[:, None, :]
        source_quat_expanded = source_quat_w[:, None, :].expand(-1, 2, -1).reshape(-1, 4)
        contact_pos_source = quat_apply(
            quat_inv(source_quat_expanded), contact_delta_w.reshape(-1, 3)
        ).reshape(self.num_envs, 2, 3)

        robot = self.simulator.scene.articulations["robot"]
        robot_data = robot.data
        gripper_body_ids = []
        for body_name in ("arm_body7", "arm_body8"):
            ids, names = robot.find_bodies(body_name, preserve_order=True)
            if len(ids) != 1 or names != [body_name]:
                raise RuntimeError(
                    f"A2 detailed hold diagnostics require exactly one {body_name}; got {ids}, {names}."
                )
            gripper_body_ids.append(ids[0])
        door = self.simulator.scene.articulations["door"]
        handle_ids, handle_names = door.find_bodies("door_handle", preserve_order=True)
        if len(handle_ids) != 1 or handle_names != ["door_handle"]:
            raise RuntimeError(
                "A2 detailed hold diagnostics require exactly one door_handle body; "
                f"got {handle_ids}, {handle_names}."
            )

        joint_ids = a2_hold_map_task_to_articulation_joint_ids(
            self.simulator.dof_ids,
            self._a2_gripper_dof_indices,
            self.dof_names,
            robot_data.joint_pos.shape[1],
            self.device,
        )
        mapped_joint_names = [robot.joint_names[index] for index in joint_ids.tolist()]
        if mapped_joint_names != ["arm_j7", "arm_j8"]:
            raise RuntimeError(
                "A2 detailed hold mapped articulation joint order must be arm_j7,arm_j8; "
                f"got ids={joint_ids.tolist()}, names={mapped_joint_names}."
            )
        jacobian = robot.root_physx_view.get_jacobians()
        body_ids_tensor = torch.tensor(
            gripper_body_ids, device=self.device, dtype=torch.long
        )
        open_target = self._a2_gripper_open_target.to(
            device=self.device, dtype=jacobian.dtype
        )
        close_target = self._a2_gripper_close_target.to(
            device=self.device, dtype=jacobian.dtype
        )
        opening_axes_w = a2_hold_signed_gripper_opening_axes_from_jacobian(
            jacobian,
            body_ids_tensor,
            joint_ids,
            open_target,
            close_target,
        )
        force_projection = a2_hold_project_finger_forces_along_opening_axes(
            normal_force_w,
            friction_w[:, 0],
            opening_axes_w,
        )
        q = robot_data.joint_pos[:, joint_ids]
        qdot = robot_data.joint_vel[:, joint_ids]
        qtarget = robot_data.joint_pos_target[:, joint_ids]
        kp = robot_data.joint_stiffness[:, joint_ids]
        kd = robot_data.joint_damping[:, joint_ids]
        limit = robot_data.joint_effort_limits[:, joint_ids]
        pd_unclipped, pd_clipped, pd_saturated = a2_hold_pd_effort_estimates(
            q, qdot, qtarget, kp, kd, limit
        )
        implicit_computed = robot_data.computed_torque[:, joint_ids]
        implicit_applied = robot_data.applied_torque[:, joint_ids]

        records = []
        for env_id in env_ids.tolist():
            records.append(
                {
                    "handle_filter_pair_order": ["arm_body7", "arm_body8"],
                    "handle_contact_pos_w_average": a2_hold_nullable_tensor_list(
                        contact_pos_w[env_id, 0]
                    ),
                    "handle_contact_pos_source_average": a2_hold_nullable_tensor_list(
                        contact_pos_source[env_id]
                    ),
                    "handle_normal_force_w_sum": normal_force_w[env_id].detach().cpu().tolist(),
                    "handle_normal_force_direction_w_aggregate": a2_hold_nullable_tensor_list(
                        normal_direction_w[env_id]
                    ),
                    "handle_normal_force_direction_valid": normal_direction_valid[env_id].detach().cpu().tolist(),
                    "handle_friction_force_w_sum": friction_w[env_id, 0].detach().cpu().tolist(),
                    "gripper_opening_axis_w_body7_body8": (
                        opening_axes_w[env_id].detach().cpu().tolist()
                    ),
                    "finger_normal_force_w_body7_body8": (
                        force_projection["finger_normal_force_w"][env_id]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "finger_friction_force_w_body7_body8": (
                        force_projection["finger_friction_force_w"][env_id]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "finger_total_force_w_body7_body8": (
                        force_projection["finger_total_force_w"][env_id]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "finger_normal_force_along_opening_axis_body7_body8": (
                        force_projection[
                            "finger_normal_force_along_opening_axis"
                        ][env_id]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "finger_friction_force_along_opening_axis_body7_body8": (
                        force_projection[
                            "finger_friction_force_along_opening_axis"
                        ][env_id]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "finger_total_force_along_opening_axis_body7_body8": (
                        force_projection["finger_total_force_along_opening_axis"][
                            env_id
                        ]
                        .detach()
                        .cpu()
                        .tolist()
                    ),
                    "opening_force_projection_positive_semantic": (
                        "positive_force_on_finger_drives_its_joint_toward_open_target; "
                        "arm_j7_positive, arm_j8_negative"
                    ),
                    "handle_contact_sensor_pos_w": sensor_pos_w[env_id, 0].detach().cpu().tolist(),
                    "handle_contact_sensor_quat_w": sensor_quat_w[env_id, 0].detach().cpu().tolist(),
                    "gripper_source_pos_w": source_pos_w[env_id].detach().cpu().tolist(),
                    "gripper_source_quat_w_detailed": source_quat_w[env_id].detach().cpu().tolist(),
                    "handle_target_pos_w": target_pos_w[env_id, 0].detach().cpu().tolist(),
                    "handle_target_quat_w": target_quat_w[env_id, 0].detach().cpu().tolist(),
                    "arm_body7_body8_pos_w": robot_data.body_pos_w[env_id, gripper_body_ids].detach().cpu().tolist(),
                    "arm_body7_body8_quat_w": robot_data.body_quat_w[env_id, gripper_body_ids].detach().cpu().tolist(),
                    "door_handle_body_pos_w": door.data.body_pos_w[env_id, handle_ids[0]].detach().cpu().tolist(),
                    "door_handle_body_quat_w": door.data.body_quat_w[env_id, handle_ids[0]].detach().cpu().tolist(),
                    "gripper_joint_vel": qdot[env_id].detach().cpu().tolist(),
                    "gripper_joint_stiffness": kp[env_id].detach().cpu().tolist(),
                    "gripper_joint_damping": kd[env_id].detach().cpu().tolist(),
                    "gripper_joint_effort_limit": limit[env_id].detach().cpu().tolist(),
                    "pd_effort_estimate_unclipped": pd_unclipped[env_id].detach().cpu().tolist(),
                    "pd_effort_estimate_clipped": pd_clipped[env_id].detach().cpu().tolist(),
                    "pd_effort_estimated_saturation": pd_saturated[env_id].detach().cpu().tolist(),
                    "runtime_gain_pd_effort_estimate_primary_unclipped": (
                        pd_unclipped[env_id].detach().cpu().tolist()
                    ),
                    "runtime_gain_pd_effort_estimate_primary_clipped": (
                        pd_clipped[env_id].detach().cpu().tolist()
                    ),
                    "runtime_gain_pd_effort_estimate_primary_saturation": (
                        pd_saturated[env_id].detach().cpu().tolist()
                    ),
                    "isaaclab_implicit_computed_effort_estimate": implicit_computed[env_id].detach().cpu().tolist(),
                    "isaaclab_implicit_applied_effort_estimate": implicit_applied[env_id].detach().cpu().tolist(),
                    "isaaclab_implicit_effort_estimate_crosscheck_error": (
                        implicit_computed[env_id] - pd_unclipped[env_id]
                    ).detach().cpu().tolist(),
                    "isaaclab_implicit_effort_estimate_authority": (
                        "NON_AUTHORITATIVE_AFTER_RUNTIME_GAIN_OVERRIDE"
                        if self._a2_hold_oracle_static_clamp_gain_applied[env_id].item()
                        else "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE"
                    ),
                }
            )
        return records

    @staticmethod
    def _a2_hold_read_material_binding(stage: Usd.Stage, prim: Usd.Prim):
        current = prim
        while current.IsValid():
            rel = current.GetRelationship("material:binding:physics")
            targets = rel.GetTargets() if rel.IsValid() else []
            if targets:
                material_path = str(targets[0])
                material_prim = stage.GetPrimAtPath(material_path)
                usd_api = UsdPhysics.MaterialAPI(material_prim)
                physx_api = PhysxSchema.PhysxMaterialAPI(material_prim)
                return {
                    "binding_source_prim": str(current.GetPath()),
                    "material_path": material_path,
                    "static_friction": usd_api.GetStaticFrictionAttr().Get(),
                    "dynamic_friction": usd_api.GetDynamicFrictionAttr().Get(),
                    "restitution": usd_api.GetRestitutionAttr().Get(),
                    "friction_combine_mode": physx_api.GetFrictionCombineModeAttr().Get(),
                    "restitution_combine_mode": physx_api.GetRestitutionCombineModeAttr().Get(),
                }
            current = current.GetParent()
        return None

    def get_a2_hold_diagnostic_runtime_metadata(self):
        if not self._use_a2_base or not getattr(self, "is_evaluating", False):
            raise RuntimeError("A2 hold runtime metadata requires an evaluating A2 env.")
        if not self._get_a2_hold_contact_detail_enabled():
            raise RuntimeError("A2 hold runtime metadata requires detailed contact diagnostics.")
        stage = omni.usd.get_context().get_stage()
        default_material = self.simulator.sim.cfg.physics_material
        collision_records = []
        handle_radii = []
        for env_id in range(self.num_envs):
            door_prim = stage.GetPrimAtPath(f"/World/envs/env_{env_id}/door")
            custom_data = door_prim.GetMetadata("customData")
            if not isinstance(custom_data, dict) or "handleRadius" not in custom_data:
                raise RuntimeError(f"A2 hold metadata env {env_id} is missing handleRadius customData.")
            handle_radii.append(float(custom_data["handleRadius"]))
            parents = [
                f"/World/envs/env_{env_id}/Robot/arm_body7",
                f"/World/envs/env_{env_id}/Robot/arm_body8",
            ]
            collision_paths = []
            for parent in parents:
                collision_paths.extend(self._a2_hold_collision_descendants(stage, parent))
            handle_path = f"/World/envs/env_{env_id}/door/door_handle/handle_inside"
            handle_prim = stage.GetPrimAtPath(handle_path)
            if not handle_prim.IsValid() or not handle_prim.HasAPI(UsdPhysics.CollisionAPI):
                raise RuntimeError(f"A2 hold metadata missing selected handle collider {handle_path}.")
            collision_paths.append(handle_path)
            for collision_path in collision_paths:
                prim = stage.GetPrimAtPath(collision_path)
                mesh_api = UsdPhysics.MeshCollisionAPI(prim)
                approximation = mesh_api.GetApproximationAttr().Get() if mesh_api else None
                collision_records.append(
                    {
                        "env_id": env_id,
                        "collision_prim_path": collision_path,
                        "prim_type": prim.GetTypeName(),
                        "collision_approximation": approximation,
                        "physics_material": self._a2_hold_read_material_binding(stage, prim),
                    }
                )
        m39_metadata = None
        if self._get_a2_m39_gripper_material_enabled():
            m39_metadata = getattr(self.simulator, "_m39_material_runtime_metadata", None)
            if not isinstance(m39_metadata, dict):
                raise RuntimeError("M39 gripper material runtime evidence is unavailable.")
            if m39_metadata.get("schema") != "a2_m39_gripper_material_v1":
                raise RuntimeError("M39 gripper material runtime evidence schema is invalid.")
        metadata = {
            "contact_sensor_body": "door_handle",
            "contact_filter_pair_order": ["arm_body7", "arm_body8"],
            "contact_pos_semantics": "average per sensor-body/filter pair",
            "normal_force_semantics": "summed normal contact force; direction is aggregate force direction, not raw geometric normal",
            "friction_force_semantics": "summed friction force per sensor-body/filter pair",
            "signed_opening_axis_semantics": (
                "runtime own-body Jacobian linear own-joint column with floating-base +6 "
                "mapping, multiplied by sign(open_target-close_target); arm_j7 positive, "
                "arm_j8 negative"
            ),
            "signed_force_projection_semantics": (
                "ContactSensor normal/friction act on handle, so finger force is their "
                "negative; positive projection drives that finger toward open target"
            ),
            "runtime_gain_pd_effort_estimate": (
                "PRIMARY diagnostic estimate from runtime ArticulationData stiffness, "
                "damping, position target, position and velocity"
            ),
            "actual_implicit_drive_force": "UNAVAILABLE/INCONCLUSIVE; logged torque fields are IsaacLab implicit PD estimates",
            "implicit_actuator_estimate_after_runtime_gain_override": (
                "NON_AUTHORITATIVE because high-level gain writers update ArticulationData "
                "and PhysX but do not update the ImplicitActuator model"
            ),
            "gripper_source_tcp_offset_z": self._get_a2_gripper_source_tcp_offset_z(),
            "oracle_tcp_offset_label": "measured finger-collider longitudinal midpoint when z=0.09755",
            "sampled_handle_radius": handle_radii,
            "collision_and_material": collision_records,
            "simulation_default_material": {
                "static_friction": float(default_material.static_friction),
                "dynamic_friction": float(default_material.dynamic_friction),
                "restitution": float(default_material.restitution),
                "friction_combine_mode": str(default_material.friction_combine_mode),
                "restitution_combine_mode": str(default_material.restitution_combine_mode),
            },
            "friction_override": None,
            "friction_override_support": (
                "unsupported for the instanceable Piper collider; conditional friction "
                "implementation is deferred until measured-midpoint CONTACT_SLIP"
            ),
        }

        if m39_metadata is not None:
            metadata["m39_gripper_material"] = m39_metadata
        return metadata
    def _get_a2_eval_diagnostic_step_fields(self, env_ids: torch.Tensor):
        if not self._a2_eval_diagnostic_trace_enabled:
            raise RuntimeError(
                "A2 expanded eval diagnostic fields requested while diagnostics are disabled."
            )
        if (
            not torch.is_tensor(env_ids)
            or env_ids.ndim != 1
            or env_ids.dtype != torch.long
            or env_ids.device != torch.device(self.device)
        ):
            shape = None if not torch.is_tensor(env_ids) else tuple(env_ids.shape)
            dtype = None if not torch.is_tensor(env_ids) else env_ids.dtype
            device = None if not torch.is_tensor(env_ids) else env_ids.device
            raise RuntimeError(
                "A2 expanded eval diagnostic env_ids require long tensor on env device; "
                f"got shape={shape}, dtype={dtype}, device={device}."
            )

        layout = self.get_a2_high_level_action_layout()
        expected_action_shape = (self.num_envs, layout["dim"])
        policy_action = self._a2_eval_policy_high_level_action_raw
        post_forced_action = self._a2_eval_post_forced_override_pre_env_action
        post_delta_post_warp_action = self._a2_eval_post_delta_post_warp_env_action
        forced_close_mask = self._a2_eval_forced_gripper_close_mask
        for action_name, action in (
            ("policy action", policy_action),
            ("post-forced-override pre-env action", post_forced_action),
            ("post-delta/post-warp env action", post_delta_post_warp_action),
        ):
            if (
                not torch.is_tensor(action)
                or tuple(action.shape) != expected_action_shape
                or not torch.is_floating_point(action)
                or not torch.all(torch.isfinite(action))
            ):
                shape = None if not torch.is_tensor(action) else tuple(action.shape)
                dtype = None if not torch.is_tensor(action) else action.dtype
                raise RuntimeError(
                    f"A2 expanded eval diagnostic {action_name} requires finite floating "
                    f"tensor shape {expected_action_shape}; got shape={shape}, dtype={dtype}."
                )
        if (
            not torch.is_tensor(forced_close_mask)
            or tuple(forced_close_mask.shape) != (self.num_envs,)
            or forced_close_mask.dtype != torch.bool
        ):
            shape = None if not torch.is_tensor(forced_close_mask) else tuple(
                forced_close_mask.shape
            )
            dtype = None if not torch.is_tensor(forced_close_mask) else forced_close_mask.dtype
            raise RuntimeError(
                "A2 expanded eval diagnostic forced-close mask requires bool tensor shape "
                f"({self.num_envs},); got shape={shape}, dtype={dtype}."
            )
        first_episode_active_mask = self._a2_eval_first_episode_active_mask
        if (
            not torch.is_tensor(first_episode_active_mask)
            or tuple(first_episode_active_mask.shape) != (self.num_envs,)
            or first_episode_active_mask.dtype != torch.bool
        ):
            shape = (
                None
                if not torch.is_tensor(first_episode_active_mask)
                else tuple(first_episode_active_mask.shape)
            )
            dtype = (
                None
                if not torch.is_tensor(first_episode_active_mask)
                else first_episode_active_mask.dtype
            )
            raise RuntimeError(
                "A2 expanded eval first-episode active mask requires bool tensor shape "
                f"({self.num_envs},); got shape={shape}, dtype={dtype}."
            )
        if torch.any(forced_close_mask & ~first_episode_active_mask):
            raise RuntimeError(
                "A2 expanded eval forced-close mask contains inactive completed envs."
            )
        episode_indices = self._a2_eval_episode_indices
        if (
            not torch.is_tensor(episode_indices)
            or tuple(episode_indices.shape) != (self.num_envs,)
            or episode_indices.dtype != torch.long
            or torch.any(episode_indices < 0)
        ):
            shape = None if not torch.is_tensor(episode_indices) else tuple(
                episode_indices.shape
            )
            dtype = None if not torch.is_tensor(episode_indices) else episode_indices.dtype
            raise RuntimeError(
                "A2 expanded eval episode indices require non-negative long tensor shape "
                f"({self.num_envs},); got shape={shape}, dtype={dtype}."
            )

        raw_rewards = self._a2_eval_reward_raw_by_name
        scaled_rewards = self._a2_eval_reward_scaled_by_name
        if not isinstance(raw_rewards, dict) or not isinstance(scaled_rewards, dict):
            raise RuntimeError(
                "A2 expanded eval diagnostics require cached reward maps from the current "
                "reward pipeline step."
            )
        expected_reward_names = set(self._a2_eval_diagnostic_reward_term_names)
        if set(raw_rewards) != expected_reward_names or set(scaled_rewards) != expected_reward_names:
            raise RuntimeError(
                "A2 expanded eval diagnostic reward cache mismatch: "
                f"expected={sorted(expected_reward_names)}, "
                f"raw={sorted(raw_rewards)}, scaled={sorted(scaled_rewards)}."
            )

        robot = self.simulator.scene.articulations["robot"]
        robot_data = robot.data
        simulator_dof_ids = getattr(self.simulator, "dof_ids", None)
        if (
            not isinstance(simulator_dof_ids, list)
            or len(simulator_dof_ids) != self.num_dof
            or len(set(simulator_dof_ids)) != self.num_dof
            or any(not isinstance(joint_id, int) for joint_id in simulator_dof_ids)
        ):
            raise RuntimeError(
                "A2 expanded eval diagnostics require simulator.dof_ids to be a unique "
                f"list[int] of length {self.num_dof}; got {simulator_dof_ids!r}."
            )
        ordered_joint_ids = torch.tensor(
            simulator_dof_ids, device=self.device, dtype=torch.long
        )
        required_joint_fields = {
            "joint_pos": robot_data.joint_pos,
            "joint_vel": robot_data.joint_vel,
            "joint_pos_target": robot_data.joint_pos_target,
        }
        articulation_joint_count = robot_data.joint_pos.shape[1]
        if torch.any(ordered_joint_ids < 0) or torch.any(
            ordered_joint_ids >= articulation_joint_count
        ):
            raise RuntimeError(
                "A2 expanded eval diagnostics simulator.dof_ids are outside the robot "
                f"Articulation joint range [0, {articulation_joint_count})."
            )
        for field_name, field_value in required_joint_fields.items():
            expected_shape = (self.num_envs, articulation_joint_count)
            if (
                not torch.is_tensor(field_value)
                or tuple(field_value.shape) != expected_shape
                or not torch.all(torch.isfinite(field_value))
            ):
                shape = None if not torch.is_tensor(field_value) else tuple(field_value.shape)
                raise RuntimeError(
                    f"A2 expanded eval diagnostics require Articulation.data.{field_name} "
                    f"finite shape {expected_shape}; got {shape}."
                )

        soft_joint_pos_limits = robot_data.soft_joint_pos_limits
        expected_limit_shape = (self.num_envs, articulation_joint_count, 2)
        if (
            not torch.is_tensor(soft_joint_pos_limits)
            or tuple(soft_joint_pos_limits.shape) != expected_limit_shape
            or not torch.all(torch.isfinite(soft_joint_pos_limits))
        ):
            shape = (
                None
                if not torch.is_tensor(soft_joint_pos_limits)
                else tuple(soft_joint_pos_limits.shape)
            )
            raise RuntimeError(
                "A2 expanded eval diagnostics require "
                f"Articulation.data.soft_joint_pos_limits finite shape "
                f"{expected_limit_shape}; got {shape}."
            )

        ordered_joint_pos = robot_data.joint_pos[:, ordered_joint_ids]
        ordered_joint_vel = robot_data.joint_vel[:, ordered_joint_ids]
        ordered_joint_target = robot_data.joint_pos_target[:, ordered_joint_ids]
        ordered_soft_limits = soft_joint_pos_limits[:, ordered_joint_ids, :]
        arm_indices = self._a2_arm_dof_indices
        gripper_indices = self._a2_gripper_dof_indices
        arm_pos = ordered_joint_pos[:, arm_indices]
        arm_vel = ordered_joint_vel[:, arm_indices]
        arm_target = ordered_joint_target[:, arm_indices]
        arm_soft_limits = ordered_soft_limits[:, arm_indices, :]
        arm_soft_span = arm_soft_limits[:, :, 1] - arm_soft_limits[:, :, 0]
        if torch.any(arm_soft_span <= 0.0) or not torch.all(torch.isfinite(arm_soft_span)):
            raise RuntimeError(
                "A2 expanded eval diagnostics require positive finite arm soft joint spans."
            )
        arm_soft_limit_normalized_margin = torch.minimum(
            arm_pos - arm_soft_limits[:, :, 0],
            arm_soft_limits[:, :, 1] - arm_pos,
        ) / arm_soft_span

        gripper_pos = ordered_joint_pos[:, gripper_indices]
        gripper_target = ordered_joint_target[:, gripper_indices]
        gripper_target_error = gripper_target - gripper_pos

        root_fields = {
            "root_pos_w": robot_data.root_pos_w,
            "root_quat_w": robot_data.root_quat_w,
            "root_lin_vel_w": robot_data.root_lin_vel_w,
            "root_ang_vel_w": robot_data.root_ang_vel_w,
        }
        expected_root_dims = {
            "root_pos_w": 3,
            "root_quat_w": 4,
            "root_lin_vel_w": 3,
            "root_ang_vel_w": 3,
        }
        for field_name, field_value in root_fields.items():
            expected_shape = (self.num_envs, expected_root_dims[field_name])
            if (
                not torch.is_tensor(field_value)
                or tuple(field_value.shape) != expected_shape
                or not torch.all(torch.isfinite(field_value))
            ):
                shape = None if not torch.is_tensor(field_value) else tuple(field_value.shape)
                raise RuntimeError(
                    f"A2 expanded eval diagnostics require Articulation.data.{field_name} "
                    f"finite shape {expected_shape}; got {shape}."
                )

        physical_base_command = self.get_physical_base_command()
        if (
            not torch.is_tensor(physical_base_command)
            or tuple(physical_base_command.shape) != (self.num_envs, 5)
            or not torch.all(torch.isfinite(physical_base_command))
        ):
            shape = (
                None
                if not torch.is_tensor(physical_base_command)
                else tuple(physical_base_command.shape)
            )
            raise RuntimeError(
                "A2 expanded eval diagnostics require physical base command finite shape "
                f"({self.num_envs}, 5); got {shape}."
            )

        transform_data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = transform_data.target_pos_source
        target_quat_source = transform_data.target_quat_source
        if (
            not torch.is_tensor(target_pos_source)
            or tuple(target_pos_source.shape) != (self.num_envs, 2, 3)
            or not torch.all(torch.isfinite(target_pos_source))
        ):
            shape = (
                None
                if not torch.is_tensor(target_pos_source)
                else tuple(target_pos_source.shape)
            )
            raise RuntimeError(
                "A2 expanded eval diagnostics require FrameTransformer target_pos_source "
                f"finite shape ({self.num_envs}, 2, 3); got {shape}."
            )
        if (
            not torch.is_tensor(target_quat_source)
            or tuple(target_quat_source.shape) != (self.num_envs, 2, 4)
            or not torch.all(torch.isfinite(target_quat_source))
        ):
            shape = (
                None
                if not torch.is_tensor(target_quat_source)
                else tuple(target_quat_source.shape)
            )
            raise RuntimeError(
                "A2 expanded eval diagnostics require FrameTransformer target_quat_source "
                f"finite shape ({self.num_envs}, 2, 4); got {shape}."
            )

        arm_joint_names = [f"arm_j{joint_index}" for joint_index in range(1, 7)]
        gripper_joint_names = ["arm_j7", "arm_j8"]
        records = []
        for env_id in env_ids.tolist():
            raw_reward_record = {
                name: float(raw_rewards[name][env_id].item())
                for name in self._a2_eval_diagnostic_reward_term_names
            }
            scaled_reward_record = {
                name: float(scaled_rewards[name][env_id].item())
                for name in self._a2_eval_diagnostic_reward_term_names
            }
            records.append(
                {
                    "policy_high_level_action_raw": policy_action[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "policy_base_action_raw": policy_action[
                        env_id, layout["base_start"] : layout["base_end"]
                    ]
                    .detach()
                    .cpu()
                    .tolist(),
                    "policy_arm_action_raw": policy_action[
                        env_id, layout["arm_start"] : layout["arm_end"]
                    ]
                    .detach()
                    .cpu()
                    .tolist(),
                    "policy_gripper_primitive_raw": float(
                        policy_action[env_id, layout["gripper_index"]].item()
                    ),
                    "post_forced_override_pre_env_action": post_forced_action[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "post_forced_override_pre_env_base_action": post_forced_action[
                        env_id, layout["base_start"] : layout["base_end"]
                    ]
                    .detach()
                    .cpu()
                    .tolist(),
                    "post_forced_override_pre_env_arm_action": post_forced_action[
                        env_id, layout["arm_start"] : layout["arm_end"]
                    ]
                    .detach()
                    .cpu()
                    .tolist(),
                    "post_forced_override_pre_env_gripper_primitive": float(
                        post_forced_action[env_id, layout["gripper_index"]].item()
                    ),
                    "post_delta_post_warp_env_action": post_delta_post_warp_action[
                        env_id
                    ]
                    .detach()
                    .cpu()
                    .tolist(),
                    "post_delta_post_warp_base_action": post_delta_post_warp_action[
                        env_id, layout["base_start"] : layout["base_end"]
                    ]
                    .detach()
                    .cpu()
                    .tolist(),
                    "actual_post_delta_post_warp_arm_action": post_delta_post_warp_action[
                        env_id, layout["arm_start"] : layout["arm_end"]
                    ]
                    .detach()
                    .cpu()
                    .tolist(),
                    "post_delta_post_warp_gripper_primitive": float(
                        post_delta_post_warp_action[
                            env_id, layout["gripper_index"]
                        ].item()
                    ),
                    "forced_gripper_close_applied": bool(forced_close_mask[env_id].item()),
                    "first_episode_active": bool(
                        first_episode_active_mask[env_id].item()
                    ),
                    "episode_index": int(episode_indices[env_id].item()),
                    "physical_base_command": physical_base_command[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "root_pos_w": robot_data.root_pos_w[env_id].detach().cpu().tolist(),
                    "root_quat_w": robot_data.root_quat_w[env_id].detach().cpu().tolist(),
                    "root_lin_vel_w": robot_data.root_lin_vel_w[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "root_ang_vel_w": robot_data.root_ang_vel_w[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "arm_joint_names": arm_joint_names,
                    "arm_joint_pos": arm_pos[env_id].detach().cpu().tolist(),
                    "arm_joint_vel": arm_vel[env_id].detach().cpu().tolist(),
                    "arm_joint_pos_target": arm_target[env_id].detach().cpu().tolist(),
                    "arm_soft_joint_pos_limits": arm_soft_limits[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "arm_soft_limit_normalized_margin": arm_soft_limit_normalized_margin[
                        env_id
                    ]
                    .detach()
                    .cpu()
                    .tolist(),
                    "gripper_joint_names": gripper_joint_names,
                    "gripper_joint_pos": gripper_pos[env_id].detach().cpu().tolist(),
                    "gripper_joint_pos_target": gripper_target[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "gripper_joint_target_error": gripper_target_error[env_id]
                    .detach()
                    .cpu()
                    .tolist(),
                    "tcp_to_handle_pos": target_pos_source[env_id, 0]
                    .detach()
                    .cpu()
                    .tolist(),
                    "tcp_to_handle_quat": target_quat_source[env_id, 0]
                    .detach()
                    .cpu()
                    .tolist(),
                    "reward_raw": raw_reward_record,
                    "reward_scaled": scaled_reward_record,
                }
            )
        detailed_records = self._get_a2_hold_detailed_step_fields(env_ids)
        oracle_records = self._get_a2_hold_oracle_trace_fields(env_ids)
        for record, detailed, oracle in zip(records, detailed_records, oracle_records):
            overlap = set(record).intersection(detailed) | set(record).intersection(oracle)
            overlap |= set(detailed).intersection(oracle)
            if overlap:
                raise RuntimeError(
                    f"A2 hold diagnostic trace field collision: {sorted(overlap)}."
                )
            record.update(detailed)
            record.update(oracle)
        return records

    def _capture_a2_eval_stage2_step_trace(self):
        if not self._use_a2_base:
            return
        if not getattr(self, "is_evaluating", False):
            return
        if "_a2_stage2_step_trace_records" not in self.__dict__:
            raise RuntimeError(
                "A2 stage2-5 step trace capture requested before "
                "init_a2_eval_stage2_step_trace()."
            )

        stage_buf = getattr(self, "stage_buf", None)
        if (
            stage_buf is None
            or not torch.is_tensor(stage_buf)
            or tuple(stage_buf.shape) != (self.num_envs,)
        ):
            shape = None if stage_buf is None else tuple(stage_buf.shape)
            raise RuntimeError(
                "A2 stage2-5 step trace requires stage_buf shape "
                f"({self.num_envs},); got {shape}."
            )

        step_index = getattr(self, "_a2_stage2_step_trace_step_index", None)
        if isinstance(step_index, bool) or not isinstance(step_index, int) or step_index < 0:
            raise RuntimeError(
                "A2 stage2-5 step trace requires non-negative integer step index; "
                f"got {step_index!r}."
            )

        trace_stage_mask = (
            (stage_buf == self.STAGE_GRASP)
            | (stage_buf == self.STAGE_OPEN)
            | (stage_buf == self.STAGE_SWING)
            | (stage_buf == self.STAGE_THROUGH)
        )
        if self._a2_eval_diagnostic_trace_enabled:
            first_episode_active_mask = self._a2_eval_first_episode_active_mask
            if (
                not torch.is_tensor(first_episode_active_mask)
                or tuple(first_episode_active_mask.shape) != (self.num_envs,)
                or first_episode_active_mask.dtype != torch.bool
            ):
                shape = (
                    None
                    if not torch.is_tensor(first_episode_active_mask)
                    else tuple(first_episode_active_mask.shape)
                )
                dtype = (
                    None
                    if not torch.is_tensor(first_episode_active_mask)
                    else first_episode_active_mask.dtype
                )
                raise RuntimeError(
                    "A2 expanded eval trace requires first-episode active bool mask "
                    f"shape ({self.num_envs},); got shape={shape}, dtype={dtype}."
                )
            trace_stage_mask &= first_episode_active_mask
        trace_env_ids = trace_stage_mask.nonzero(as_tuple=False).flatten()
        if trace_env_ids.numel() > 0:
            records = self._get_a2_terminal_diagnostics(trace_env_ids)
            if len(records) != trace_env_ids.numel():
                raise RuntimeError(
                    "A2 stage2-5 step trace diagnostics returned "
                    f"{len(records)} entries for {trace_env_ids.numel()} env ids."
                )
            if self._a2_eval_diagnostic_trace_enabled:
                diagnostic_fields = self._get_a2_eval_diagnostic_step_fields(
                    trace_env_ids
                )
                if len(diagnostic_fields) != len(records):
                    raise RuntimeError(
                        "A2 expanded eval diagnostics returned "
                        f"{len(diagnostic_fields)} entries for {len(records)} trace records."
                    )
            else:
                diagnostic_fields = [{} for _ in records]

            hinge_threshold = self._get_a2_stage3_to4_door_hinge_threshold()
            for record, extra_fields in zip(records, diagnostic_fields):
                if not isinstance(record, dict):
                    raise TypeError(
                        "A2 stage2-5 step trace records must be dicts, "
                        f"got {type(record).__name__}."
                    )
                overlap = set(record).intersection(extra_fields)
                if overlap:
                    raise RuntimeError(
                        "A2 expanded eval diagnostic fields overlap base trace fields: "
                        f"{sorted(overlap)}."
                    )
                record.update(extra_fields)
                record["stage3_to4_door_hinge_threshold"] = hinge_threshold
                record["stage3_to4_door_hinge_margin"] = (
                    record["door_hinge_joint_pos"] - hinge_threshold
                )
                record["step_index"] = step_index
            self._a2_stage2_step_trace_records.extend(records)

        self._a2_stage2_step_trace_step_index += 1

    def get_a2_eval_stage2_step_trace_records(self):
        if not self._use_a2_base:
            raise RuntimeError("A2 stage2-5 step trace is only available for A2 envs.")
        if "_a2_stage2_step_trace_records" not in self.__dict__:
            raise RuntimeError(
                "A2 stage2-5 step trace requested before init_a2_eval_stage2_step_trace()."
            )
        return [dict(record) for record in self._a2_stage2_step_trace_records]

    def _get_obs_gripper_handle_transform(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "gripper_handle_transform is only defined for A2 Piper gripper observations."
            )
        data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = getattr(data, "target_pos_source", None)
        target_quat_source = getattr(data, "target_quat_source", None)
        if (
            target_pos_source is None
            or target_quat_source is None
            or target_pos_source.ndim != 3
            or target_quat_source.ndim != 3
            or target_pos_source.shape[1] != 2
            or target_quat_source.shape[1] != 2
        ):
            pos_shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            quat_shape = None if target_quat_source is None else tuple(target_quat_source.shape)
            raise RuntimeError(
                "A2 gripper_handle_transform requires 2 source-relative target poses; "
                f"target_pos_source shape={pos_shape}, target_quat_source shape={quat_shape}."
            )

        handle_pos = target_pos_source[:, 0, :]
        handle_rot_6d = quat_to_tan_norm(
            wxyz_to_xyzw(target_quat_source[:, 0, :]), w_last=True
        )
        pregrasp_pos = target_pos_source[:, 1, :]
        pregrasp_rot_6d = quat_to_tan_norm(
            wxyz_to_xyzw(target_quat_source[:, 1, :]), w_last=True
        )
        return torch.cat([handle_pos, handle_rot_6d, pregrasp_pos, pregrasp_rot_6d], dim=-1)

    def _get_obs_hand_force(self):
        if self._use_a2_base:
            if not hasattr(self, "_a2_gripper_force_body_indices"):
                raise RuntimeError(
                    "A2 hand_force requires name-based gripper body indices for "
                    "arm_body7 and arm_body8."
                )
            hand_force = self.simulator.contact_forces[:, self._a2_gripper_force_body_indices, :]
            return hand_force.reshape(hand_force.shape[0], 6)
        left_hand_force = self.simulator.contact_forces[:, self.left_hand_indices, :]
        right_hand_force = self.simulator.contact_forces[:, self.right_hand_indices, :]
        return torch.cat(
            [
                left_hand_force.reshape(left_hand_force.shape[0], -1),
                right_hand_force.reshape(right_hand_force.shape[0], -1),
            ],
            dim=-1,
        )

    def _get_obs_privileged_door_info(self):
        return torch.stack(
            [
                self.door_width,
                self.door_height,
                self.door_handle_height,
                self.door_handle_width,
                self.door_weight / 100.0,
                self.door_open_lr,
                1.0 - self.door_open_lr,
                self.door_open_io,
            ],
            dim=1,
        )

    def _get_obs_door_dof_pos(self):
        return self.simulator.get_task_dof_pos("door")[:, :2]

    def _get_a2_student_dof_indices(self):
        """Resolve the deployable A2 DOF order from names and validate it."""
        configured = tuple(self.config.robot.dof_names)
        actual = tuple(self.simulator.dof_names)
        if len(configured) != 20 or len(set(configured)) != 20:
            raise RuntimeError(
                "A2 student DOF contract requires 20 unique configured names; "
                f"got {configured!r}"
            )
        if len(actual) != len(configured) or set(actual) != set(configured):
            raise RuntimeError(
                "A2 simulator DOF names do not match the configured student order: "
                f"configured={configured!r}, actual={actual!r}"
            )
        indices = [actual.index(name) for name in configured]
        if tuple(actual[index] for index in indices) != configured:
            raise RuntimeError("A2 simulator DOF name resolution changed the configured order")
        return torch.tensor(indices, device=self.device, dtype=torch.long)

    def _get_obs_a2_student_dof_pos(self):
        indices = self._get_a2_student_dof_indices()
        return self.simulator.dof_pos.index_select(1, indices) - self.default_dof_pos.index_select(
            1, indices
        )

    def _get_obs_a2_student_dof_vel(self):
        indices = self._get_a2_student_dof_indices()
        return self.simulator.dof_vel.index_select(1, indices)

    def _get_obs_dof_pos_non_finger(self):
        if self._use_a2_base:
            return self._get_obs_a2_student_dof_pos()
        return self.simulator.dof_pos[:, :-14]

    def _get_obs_dof_vel_non_finger(self):
        if self._use_a2_base:
            return self._get_obs_a2_student_dof_vel()
        return self.simulator.dof_vel[:, :-14]

    def _get_obs_target_obj_pos(self):
        return (
            self.simulator.scene.sensors["head_target_frame_transformer"]
            .data.target_pos_source[:, 0, :]
            .clone()
        )

    def _compute_grasp_target(self):
        if self._use_a2_base:
            return self._get_a2_gripper_handle_frame_transformer().data.target_pos_w[
                :, 0, :
            ].clone()
        grasp_target_pos_w = (
            self.simulator.scene.sensors["right_hand_frame_transformer"]
            .data.target_pos_w[:, 0, :]
            .clone()
        )
        return grasp_target_pos_w

    @override
    def _get_handle_anchor_pos(self):
        """Lever center (grasp_target world pos) for handle_* eval cameras.

        target_pos_w[:, 0, :] is the handle frame target (= lever center after
        the grasp_target fix). Shape: (num_envs, 3).
        """
        transformer = self._get_a2_gripper_handle_frame_transformer()
        target_pos_w = transformer.data.target_pos_w
        if target_pos_w.ndim != 3 or target_pos_w.shape[1] < 1:
            shape = None if target_pos_w is None else tuple(target_pos_w.shape)
            raise RuntimeError(
                f"A2 handle anchor requires target_pos_w[:, 0, :] with shape "
                f"(num_envs, >=1, 3); got {shape}."
            )
        return target_pos_w[:, 0, :].clone()

    def _compute_pre_grasp_target(self):
        if self._use_a2_base:
            return self._get_a2_gripper_handle_frame_transformer().data.target_pos_w[
                :, 1, :
            ].clone()
        grasp_target_pos_w = self._compute_grasp_target()
        grasp_target_pos_w[:, 2] += 0.1
        return grasp_target_pos_w

    def _finish_a2_offset_placement_before_reset(self, env_ids: torch.Tensor) -> None:
        if (
            not torch.is_tensor(env_ids)
            or env_ids.ndim != 1
            or env_ids.dtype != torch.long
            or env_ids.device != torch.device(self.device)
            or torch.any(env_ids < 0)
            or torch.any(env_ids >= self.num_envs)
        ):
            raise RuntimeError("A2 offset placement reset requires valid device-local env ids.")
        affected = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        affected[env_ids] = self._a2_hold_oracle_offset_placement_active[env_ids]
        self._finish_a2_offset_placement(affected)

    @override
    def _reset_buffers_callback(self, env_ids, target_buf=None):
        cfg = getattr(self, "_a2_hold_oracle_cfg", None)
        if (
            cfg is not None
            and cfg["enabled"]
            and cfg.get("matched_clean_reacquisition_preflight_enabled", False)
        ):
            if (
                not torch.is_tensor(env_ids)
                or env_ids.ndim != 1
                or env_ids.dtype != torch.long
                or env_ids.device != torch.device(self.device)
                or torch.any(env_ids < 0)
                or torch.any(env_ids >= self.num_envs)
            ):
                raise RuntimeError("A2 matched-clean reset requires valid device-local env ids.")
            affected = torch.zeros(self.num_envs, device=self.device, dtype=torch.bool)
            affected[env_ids] = (
                self._a2_hold_oracle_matched_clean_release_active[env_ids]
                | self._a2_hold_oracle_matched_clean_stabilize_active[env_ids]
            )
            self._finish_a2_matched_clean_reacquisition(affected)
        if (
            cfg is not None
            and cfg["enabled"]
            and cfg["open_stabilization_preflight_enabled"]
        ):
            if (
                not torch.is_tensor(env_ids)
                or env_ids.ndim != 1
                or env_ids.dtype != torch.long
                or env_ids.device != torch.device(self.device)
                or torch.any(env_ids < 0)
                or torch.any(env_ids >= self.num_envs)
            ):
                raise RuntimeError(
                    "A2 open stabilization reset requires valid device-local env ids."
                )
            affected = torch.zeros(
                self.num_envs, device=self.device, dtype=torch.bool
            )
            affected[env_ids] = self._a2_hold_oracle_open_stabilization_active[
                env_ids
            ]
            self._finish_a2_open_stabilization(affected)
        if cfg is not None and cfg["enabled"] and cfg["static_clamp_enabled"]:
            if (
                not torch.is_tensor(env_ids)
                or env_ids.ndim != 1
                or env_ids.dtype != torch.long
                or env_ids.device != torch.device(self.device)
                or torch.any(env_ids < 0)
                or torch.any(env_ids >= self.num_envs)
            ):
                raise RuntimeError("A2 static clamp reset requires valid device-local env ids.")
            if cfg["static_clamp_offset_probe_enabled"]:
                self._finish_a2_offset_placement_before_reset(env_ids)
            affected = torch.zeros(
                self.num_envs, device=self.device, dtype=torch.bool
            )
            affected[env_ids] = self._a2_hold_oracle_static_clamp_gain_applied[
                env_ids
            ]
            self._finish_a2_static_clamp(affected)
        if self._use_a2_base:
            self._a2_stage3_grasp_streak_highwater[env_ids] = False
            self._a2_stage5_hold_continuation[env_ids] = False
            self._a2_door_body_contact_event_active[env_ids] = False
            self._a2_door_body_contact_event_peak[env_ids] = 0.0
            self._a2_door_body_contact_event_pending[env_ids] = 0.0
            self._a2_door_body_contact_event_emitted[env_ids] = 0.0
            self._a2_stage4_release_gate[env_ids] = False
            self._a2_root_x_ever_crossed[env_ids] = False
            self._a2_corridor_latched[env_ids] = False
            self._a2_release_event_valid[env_ids] = False
            self._a2_hinge_at_release[env_ids] = float("nan")
            self._a2_root_x_at_release[env_ids] = float("nan")
            self._a2_post_release_body_contact[env_ids] = False
            self._a2_post_release_body_force_max[env_ids] = 0.0
            self._a2_crossing_event_valid[env_ids] = False
            self._a2_crossing_while_holding[env_ids] = False
            self._a2_hinge_at_crossing[env_ids] = float("nan")
            self._a2_stage0_to1_staging_valid[env_ids] = False
            self._a2_stage0_to1_staging_standoff[env_ids] = float("nan")
            self._a2_stage0_root_height_sum[env_ids] = 0.0
            self._a2_stage0_root_height_count[env_ids] = 0
            self._a2_stage1_root_height_sum[env_ids] = 0.0
            self._a2_stage1_root_height_count[env_ids] = 0
        return super()._reset_buffers_callback(env_ids, target_buf)

    @override
    def _reset_object_states_callback(self, env_ids):
        self._reset_door_states(env_ids)
        return super()._reset_object_states_callback(env_ids)

    @override
    def _reset_robot_states_callback(self, env_ids, target_states=None):
        if self._use_a2_base:
            return A2Base._reset_robot_states_callback(self, env_ids, target_states)
        return super()._reset_robot_states_callback(env_ids, target_states)

    @override
    def _reset_root_states(self, env_ids, target_root_states=None):
        if self._use_a2_base:
            if target_root_states is not None:
                return A2Base._reset_root_states(self, env_ids, target_root_states)

            self.target_robot_root_states[env_ids] = self.base_init_state
            self.target_robot_root_states[env_ids, :3] += self.env_origins[env_ids]
            self.target_robot_root_states[env_ids, 0:1] = (
                torch_rand_float(-1.5, -0.6, (len(env_ids), 1), device=str(self.device))
                + self.env_origins[env_ids, 0:1]
            )
            self.target_robot_root_states[env_ids, 1:2] = (
                torch_rand_float(-0.5, 0.5, (len(env_ids), 1), device=str(self.device))
                + self.env_origins[env_ids, 1:2]
            )
            r, p, _ = euler_xyz_from_quat(self.target_robot_root_states[env_ids, 3:7])
            random_yaw = torch_rand_float(
                -torch.pi / 4, torch.pi / 4, (len(env_ids), 1), device=str(self.device)
            )[:, 0]
            self.target_robot_root_states[env_ids, 3:7] = quat_from_euler_xyz(
                r, p, random_yaw
            )
            self.target_robot_root_states[env_ids, 7:13] = 0.0
            return

        self.target_robot_root_states[env_ids, 7:13] = torch_rand_float(
            -0.5, 0.5, (len(env_ids), 6), device=str(self.device)
        )  # [7:10]: lin vel, [10:13]: ang vel

        r, p, _ = euler_xyz_from_quat(self.target_robot_root_states[env_ids, 3:7])
        self.target_robot_root_states[env_ids, 0:1] = torch_rand_float(
            -1.5, -0.6, (len(env_ids), 1), device=str(self.device)
        )
        self.target_robot_root_states[env_ids, 1:2] = torch_rand_float(
            -0.5, 0.5, (len(env_ids), 1), device=str(self.device)
        )
        self.target_robot_root_states[env_ids, 0:2] += self.env_origins[env_ids, 0:2]
        random_yaw = torch_rand_float(
            -torch.pi / 4, torch.pi / 4, (len(env_ids), 1), device=str(self.device)
        )[:, 0]
        self.target_robot_root_states[env_ids, 3:7] = quat_from_euler_xyz(r, p, random_yaw)

    @override
    def _reset_dofs(self, env_ids, target_state=None):
        if self._use_a2_base:
            if target_state is not None:
                return A2Base._reset_dofs(self, env_ids, target_state)

            self.target_robot_dof_state[env_ids, :, 0] = (
                self.default_dof_pos
                * torch_rand_float(0.8, 1.2, (len(env_ids), self.num_dof), device=str(self.device))
            )
            self.target_robot_dof_state[
                env_ids[:, None], self._upper_non_gripper_dof_idx, 0
            ] = self._get_a2_arm_default_dof_pos(env_ids)
            self.target_robot_dof_state[env_ids, :, 1] = 0.0
            return

        # randomize wrist in +- 80 deg
        xx, yy = torch.meshgrid(env_ids, self.wrist_dof_idx)
        self.target_robot_dof_state[xx, yy, 0] = torch_rand_float(
            -1.39626, 1.39626, (len(env_ids), len(self.wrist_dof_idx)), device=str(self.device)
        )

        # completely randomize finger dofs
        xx, yy = torch.meshgrid(env_ids, self.finger_dof_idx)
        upper_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_upper_limit_list, device=str(self.device)
        )[None, self.finger_dof_idx]
        lower_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_lower_limit_list, device=str(self.device)
        )[None, self.finger_dof_idx]
        self.target_robot_dof_state[xx, yy, 0] = lower_limit + (
            upper_limit - lower_limit
        ) * torch_rand_float(
            0.0, 1.0, (len(env_ids), len(self.finger_dof_idx)), device=str(self.device)
        )

        # set velocities to 0
        self.target_robot_dof_state[env_ids, :, 1] = 0.0

    def _reset_door_states(self, env_ids):
        randomize_door_init_state = self.config.get("randomize_door_init_state", False)
        self.door_dof_state_buf[:] = 0.0
        if randomize_door_init_state:
            # 33% of the environments to have a different initial state
            rand_env_ids = env_ids[torch.randperm(len(env_ids))[: len(env_ids) // 3]]
            self.door_dof_state_buf[rand_env_ids, 0] = torch_rand_float(
                0.261799, 1.74533, (len(rand_env_ids), 1), device=self.device
            ).squeeze(-1)
        door_dof_state_dict = {
            "door": (
                self.door_dof_state_buf,
                torch.zeros_like(self.door_dof_state_buf),
                torch.tensor([0, 1, 2], device=self.device, dtype=torch.long),
            )
        }
        self.simulator.set_task_dof_state_tensor(env_ids, door_dof_state_dict)

        door_dof_target = torch.zeros(self.num_envs, 3, device=self.device, requires_grad=False)
        door_dof_target[:, 0] = 0.0
        door_dof_target[:, 1] = 15 * torch.pi / 180.0  # tension the door handle
        self.simulator.apply_torques_at_task_dof(env_ids, {"door": door_dof_target})

    @override
    def _check_termination(self):
        super()._check_termination()
        if self._use_a2_base:
            a2_config = self.config.get("a2_base", {})
            bad_orientation_limit_angle = float(
                a2_config.get("bad_orientation_limit_angle", 0.9)
            )
            tilt = torch.acos(torch.clamp(-self.projected_gravity[:, 2], -1.0, 1.0))
            bad_orientation = tilt > bad_orientation_limit_angle
            self._mark_terminal_reason("bad_orientation", bad_orientation)
            self.reset_buf |= bad_orientation

        door_distance = self.relative_door_pos_buf.norm(dim=-1) > 4.0
        self._mark_terminal_reason("door_distance", door_distance)
        self.reset_buf |= door_distance

        # A2 arm body DOF / Piper arm_j1..j6 overspeed termination; gripper excluded.
        upper_dof_overspeed_threshold = torch.clamp(self.termination_level * 20.0, min=3.0)
        dof_overspeed = torch.any(
            torch.abs(self.simulator.dof_vel[:, self._upper_non_gripper_dof_idx])
            > upper_dof_overspeed_threshold,
            dim=-1,
        )
        not_just_resetted = self.episode_length_buf > 20

        upper_dof_overspeed = dof_overspeed & not_just_resetted
        self._mark_terminal_reason("upper_dof_overspeed", upper_dof_overspeed)
        self.reset_buf |= upper_dof_overspeed

        # reset if the homie command is too large when grasping or opening the door
        # is_grasping_or_opening = (self.stage_buf == DoorPregrasp.STAGE_GRASP) | (self.stage_buf == DoorPregrasp.STAGE_OPEN)
        # homie_command_norm = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1)
        # self.reset_buf |= (homie_command_norm > self.termination_level) & is_grasping_or_opening

    @property
    def ground_height(self):
        return 0.0

    def _stage_0_reward_condition(self):
        # walk to the door
        return torch.ones(self.num_envs, dtype=torch.bool, device=self.device)

    def _stage_0_to_complete_condition(self):
        return self._stage_0_to_1_advance_condition()

    def _stage_0_to_1_advance_condition(self):
        # Enter stage1 anywhere inside the handle-relative staging band.
        grasp_target = self._compute_grasp_target()
        root_pos = self.simulator.robot_root_states[:, :3]
        x_min, x_max, y_tol = self._get_a2_stage0_staging_band()
        cond = a2_stage0_staging_band_mask(
            root_pos,
            grasp_target,
            x_min,
            x_max,
            y_tol,
        )

        # keep A2 arm body DOF / Piper arm_j1..j6 at robot default; gripper arm_j7/8 are excluded.
        if self._use_a2_base:
            arm_target_pos = self._get_a2_arm_default_dof_pos()
        else:
            arm_target_pos = self.default_dof_pos[:, self._upper_non_gripper_dof_idx]
        arm_max_deviation = self._get_required_positive_float_config(
            "a2_stage0_arm_default_max_deviation",
            "stage0->1 arm default transition",
        )
        max_deviation = (
            torch.abs(
                self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx]
                - arm_target_pos
            )
            .max(dim=-1)
            .values
        )
        cond &= max_deviation < arm_max_deviation
        if self._use_a2_base:
            base_command = self.get_physical_homie_commands()
            if (
                not torch.is_tensor(base_command)
                or tuple(base_command.shape) != (self.num_envs, 5)
                or not torch.all(torch.isfinite(base_command))
                or base_command.device != torch.device(self.device)
            ):
                shape = None if not torch.is_tensor(base_command) else tuple(base_command.shape)
                raise RuntimeError(
                    "A2 stage0->1 base-still gate requires finite physical homie "
                    f"commands shape ({self.num_envs}, 5) on {self.device}; got {shape}."
                )
            cond &= torch.norm(base_command[:, :3], dim=1) <= 0.1
        if self._use_a2_base:
            self._record_a2_stage0_to1_staging_standoff(
                cond,
                grasp_target,
                root_pos,
            )
        return cond

    def _stage_1_reward_condition(self):
        # small homie command
        cond = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1) <= 0.1
        # stay close to the door
        cond &= self._stage_0_to_1_advance_condition()
        return cond

    def _stage_1_to_complete_condition(self):
        return self._stage_1_to_2_advance_condition()

    def _stage_1_to_2_advance_condition(self):
        if self._use_a2_base:
            return self._get_a2_stage1_pregrasp_ready_mask()
        # raise hand to pre-grasp position
        pre_grasp_target = self._compute_pre_grasp_target()

        left_palm_body_pos = self.simulator._rigid_body_pos[:, self.left_palm_idx, :]
        left_hand_above_handle = left_palm_body_pos[:, 2] > self.door_handle_height + 0.05
        left_hand_close_to_pre_grasp_target = (left_palm_body_pos - pre_grasp_target).norm(
            dim=-1
        ) < 0.1
        left_hand_close_to_pre_grasp_dof_target = (
            torch.abs(self.simulator.dof_pos[:, self._left_hand_dof_idx] - self._left_p0).mean(
                dim=-1
            )
            < 0.174533
        )
        left_hand_cond = (
            left_hand_above_handle
            & left_hand_close_to_pre_grasp_target
            & left_hand_close_to_pre_grasp_dof_target
        )

        right_palm_body_pos = self.simulator._rigid_body_pos[:, self.right_palm_idx, :]
        right_hand_above_handle = right_palm_body_pos[:, 2] > self.door_handle_height + 0.05
        right_hand_close_to_pre_grasp_target = (right_palm_body_pos - pre_grasp_target).norm(
            dim=-1
        ) < 0.1
        right_hand_close_to_pre_grasp_dof_target = (
            torch.abs(self.simulator.dof_pos[:, self._right_hand_dof_idx] - self._right_p0).mean(
                dim=-1
            )
            < 0.174533
        )
        right_hand_cond = (
            right_hand_above_handle
            & right_hand_close_to_pre_grasp_target
            & right_hand_close_to_pre_grasp_dof_target
        )

        cond = torch.where(self.door_open_lr < 0, left_hand_cond, right_hand_cond)

        cond &= self._reward_hand_handle_orientation() > 0.2

        cond &= torch.norm(self.get_physical_homie_commands()[:, :3], dim=1) <= 0.1

        door_opened = self.simulator.scene.articulations["door"].data.joint_pos[:, 0] > 0.174533

        return cond | door_opened

    def _stage_2_reward_condition(self):
        return torch.norm(self.get_physical_homie_commands()[:, :3], dim=1) <= 0.1

    def _stage_2_to_complete_condition(self):
        if self._use_a2_base:
            return self._get_a2_stage2_grasp_completion_masks()["completion"]
        # TODO: check error
        # grasp the door handle
        left_hand_handle_contact_count = (
            self.simulator.object_to_hand_contact_forces[
                :, 0, self.left_hand_indices_tgt_ct_sensor, :
            ].norm(dim=-1)
            > 1
        ).sum(dim=-1)
        left_hand_grasped = left_hand_handle_contact_count >= 4

        right_hand_handle_contact_count = (
            self.simulator.object_to_hand_contact_forces[
                :, 0, self.right_hand_indices_tgt_ct_sensor, :
            ].norm(dim=-1)
            > 1
        ).sum(dim=-1)
        right_hand_grasped = right_hand_handle_contact_count >= 4
        return torch.where(self.door_open_lr < 0, left_hand_grasped, right_hand_grasped)

    def _stage_2_to_3_advance_condition(self):
        # grasp the door handle
        if self._use_a2_base:
            stage2_completion_masks = self._get_a2_stage2_grasp_completion_masks()
            self._update_a2_full_stage_route_diagnostics(stage2_completion_masks)
            return stage2_completion_masks["completion"]
        door_opened = self.simulator.scene.articulations["door"].data.joint_pos[:, 0] > 0.174533
        return self._stage_2_to_complete_condition() | door_opened

    def _stage_3_reward_condition(self):
        # keep grasping the door handle
        if self._use_a2_base:
            if self._get_a2_stage3_base_unlocked():
                return torch.ones(
                    self.num_envs,
                    dtype=torch.bool,
                    device=self.device,
                )
            return self._stage_2_reward_condition()
        return self._stage_2_to_3_advance_condition() & self._stage_2_reward_condition()

    def _stage_3_to_4_advance_condition(self):
        # rotate the door handle and open the door
        threshold = (
            self._get_a2_stage3_to4_door_hinge_threshold()
            if self._use_a2_base
            else 0.174533
        )
        door_opened = (
            self._get_door_joint_pos("stage3 to stage4 advance", 1)[:, 0]
            > threshold
        )
        if not self._use_a2_base:
            return door_opened
        hold_streak_ok = a2_stage3_to4_hold_streak_mask(
            current_streak_ok=self._get_a2_hold_streak_ok_mask(),
            stage3_highwater=self._a2_stage3_grasp_streak_highwater,
            requires_grasp_streak=self._get_a2_stage3_to4_requires_grasp_streak(),
            highwater_enabled=self._get_a2_stage3_to4_streak_highwater(),
        )
        return a2_stage3_to4_advance_mask(
            door_opened=door_opened,
            hold_streak_ok=hold_streak_ok,
            requires_grasp_streak=True,
        )

    def _stage_4_reward_condition(self):
        # keep grasping the door handle
        return self._stage_3_to_4_advance_condition()

    def _stage_4_to_5_advance_condition(self):
        # walk through the door and leave handle up
        walked_through_door = (
            self.simulator.robot_root_states[:, 0] - self.env_origins[:, 0]
        ) > 0.0
        door_joint_pos = self._get_door_joint_pos(
            "stage4 to stage5 advance", 2
        )
        hinge_threshold = (
            self._get_a2_stage4_to5_door_hinge_threshold()
            if self._use_a2_base
            else 1.0472
        )
        door_opened = door_joint_pos[:, 0] > hinge_threshold
        handle_up = door_joint_pos[:, 1] < 0.2
        return walked_through_door & handle_up & door_opened

    def _stage_5_reward_condition(self):
        # keep walking through the door
        return self._stage_4_to_5_advance_condition()

    def _stage_5_to_complete_condition(self):
        return (self.simulator.robot_root_states[:, 0] - self.env_origins[:, 0]) > 1.5

    @staticmethod
    def _a2_hold_collision_descendants(stage: Usd.Stage, parent_path: str):
        parent = stage.GetPrimAtPath(parent_path)
        if not parent.IsValid():
            raise RuntimeError(f"A2 hold diagnostic collision parent does not exist: {parent_path}")
        paths = [
            str(prim.GetPath())
            for prim in Usd.PrimRange(parent, Usd.TraverseInstanceProxies())
            if prim.HasAPI(UsdPhysics.CollisionAPI)
            and UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() is not False
        ]
        if len(paths) != 1:
            raise RuntimeError(
                "A2 hold diagnostic requires exactly one enabled collision prim below "
                f"{parent_path}; got {paths}."
            )
        return paths

    def _create_a2_m23_self_collision_contact_sensors(self, simulator) -> None:
        for body_name in self.A2_M23_SELF_COLLISION_BODY_NAMES:
            sensor_key = f"{self.A2_M23_SELF_COLLISION_SENSOR_KEY_PREFIX}{body_name}"
            if sensor_key in simulator.scene.sensors:
                raise RuntimeError(f"M23 self-collision sensor key already exists: {sensor_key}")
            source_path = f"/World/envs/env_.*/Robot/{body_name}"
            filter_paths = [
                f"/World/envs/env_.*/Robot/{other_body_name}"
                for other_body_name in self.A2_M23_SELF_COLLISION_BODY_NAMES
                if other_body_name != body_name
            ]
            simulator.scene.sensors[sensor_key] = ContactSensor(
                ContactSensorCfg(
                    prim_path=source_path,
                    filter_prim_paths_expr=filter_paths,
                    force_threshold=1.0,
                )
            )

    def scene_creation_callback(self, simulator):
        target_obj = simulator.task_config.get("target_obj", None)
        if target_obj is None:
            raise RuntimeError("DoorPregrasp scene creation requires task.target_obj.")
        door_frame_unwanted_contact_sensor_config: ContactSensorCfg = ContactSensorCfg(
            prim_path=f"/World/envs/env_.*/{target_obj}/root",
        )

        door_panel_unwanted_contact_sensor_config: ContactSensorCfg = ContactSensorCfg(
            prim_path=f"/World/envs/env_.*/{target_obj}/door_panel",
        )
        simulator.scene.sensors["door_frame_unwanted_contact_sensor"] = ContactSensor(
            door_frame_unwanted_contact_sensor_config
        )
        simulator.scene.sensors["door_panel_unwanted_contact_sensor"] = ContactSensor(
            door_panel_unwanted_contact_sensor_config
        )
        if self._get_a2_m23_self_collision_contact_sensors_enabled():
            self._create_a2_m23_self_collision_contact_sensors(simulator)

        if self._use_a2_base:
            target_sub_prim = simulator.task_config.get(
                "target_obj_transform_sub_prim_path", None
            )
            if target_sub_prim != "grasp_target":
                raise RuntimeError(
                    "A2 Piper gripper-handle transformer requires "
                    "task.target_obj_transform_sub_prim_path='grasp_target'; "
                    f"got {target_sub_prim!r}."
                )
            target_obj_transform_prim_path = (
                f"/World/envs/env_.*/{target_obj}/{target_sub_prim}"
            )
            piper_gripper_handle_frame_transformer_config: FrameTransformerCfg = (
                FrameTransformerCfg(
                    prim_path="/World/envs/env_.*/Robot/arm_body6_to_gripper",
                    source_frame_offset=OffsetCfg(
                        pos=(0.0, 0.0, self._get_a2_gripper_source_tcp_offset_z()),
                        rot=(1.0, 0.0, 0.0, 0.0),
                    ),
                    target_frames=[
                        FrameTransformerCfg.FrameCfg(
                            prim_path=target_obj_transform_prim_path,
                            name="handle",
                            offset=OffsetCfg(
                                pos=(0.0, 0.0, 0.0),
                                rot=(0.5, 0.5, 0.5, 0.5),
                            ),
                        ),
                        FrameTransformerCfg.FrameCfg(
                            prim_path=target_obj_transform_prim_path,
                            name="pregrasp",
                            offset=OffsetCfg(
                                pos=self.A2_PREGRASP_OFFSET,
                                rot=(0.5, 0.5, 0.5, 0.5),
                            ),
                        ),
                    ],
                )
            )
            simulator.scene.sensors[self.A2_GRIPPER_HANDLE_FRAME_TRANSFORMER] = (
                OrderedTargetFrameTransformer(piper_gripper_handle_frame_transformer_config)
            )
            target_contact_sub_prim = simulator.task_config.get(
                "target_obj_contact_sub_prim_path", None
            )
            if target_contact_sub_prim != "door_handle":
                raise RuntimeError(
                    "A2 Piper grasp reward requires "
                    "task.target_obj_contact_sub_prim_path='door_handle'; "
                    f"got {target_contact_sub_prim!r}."
                )
            contact_detail_enabled = self._get_a2_hold_contact_detail_enabled()
            contact_detail_kwargs = a2_hold_contact_sensor_detail_kwargs(
                contact_detail_enabled,
                self._get_a2_hold_contact_capacity() if contact_detail_enabled else None,
            )
            a2_gripper_handle_contact_sensor_config: ContactSensorCfg = ContactSensorCfg(
                prim_path=f"/World/envs/env_.*/{target_obj}/{target_contact_sub_prim}",
                history_length=self._get_a2_stage2_grasp_contact_history_length(),
                filter_prim_paths_expr=[
                    "/World/envs/env_.*/Robot/arm_body7",
                    "/World/envs/env_.*/Robot/arm_body8",
                ],
                **contact_detail_kwargs,
            )
            simulator.scene.sensors[self.A2_GRIPPER_HANDLE_CONTACT_SENSOR] = ContactSensor(
                a2_gripper_handle_contact_sensor_config
            )
            body_panel_filter_paths = [
                f"/World/envs/env_.*/Robot/{body_name}"
                for body_name in self.A2_DOOR_BODY_PANEL_FILTER_NAMES
            ]
            arm_panel_filter_paths = [
                f"/World/envs/env_.*/Robot/{body_name}"
                for body_name in self.A2_DOOR_ARM_PANEL_FILTER_NAMES
            ]
            body_panel_contact_sensor_config = ContactSensorCfg(
                prim_path=f"/World/envs/env_.*/{target_obj}/door_panel",
                filter_prim_paths_expr=body_panel_filter_paths,
                history_length=0,
                update_period=0.0,
            )
            arm_panel_contact_sensor_config = ContactSensorCfg(
                prim_path=f"/World/envs/env_.*/{target_obj}/door_panel",
                filter_prim_paths_expr=arm_panel_filter_paths,
                history_length=0,
                update_period=0.0,
            )
            simulator.scene.sensors[self.A2_DOOR_BODY_PANEL_CONTACT_SENSOR] = ContactSensor(
                body_panel_contact_sensor_config
            )
            simulator.scene.sensors[self.A2_DOOR_ARM_PANEL_CONTACT_SENSOR] = ContactSensor(
                arm_panel_contact_sensor_config
            )
            self._get_a2_hold_friction_override()

            # Visual debug spheres: green = grasp_target (handle), red = pregrasp target.
            # Both read offsets directly from FrameTransformer config so they auto-track
            # any config changes. Pure visual — no collision/mass/rigidbody.
            import isaaclab.sim as sim_utils_vis
            _vis_radius = 0.02
            vis_grasp_cfg = sim_utils_vis.SphereCfg(
                radius=_vis_radius,
                visual_material=sim_utils_vis.PreviewSurfaceCfg(diffuse_color=(0.0, 1.0, 0.0)),
                collision_props=None,
                mass_props=None,
                rigid_props=None,
            )
            sim_utils_vis.spawn_sphere(
                prim_path=f"/World/envs/env_.*/{target_obj}/grasp_target/vis_grasp_target",
                cfg=vis_grasp_cfg,
                translation=(0.0, 0.0, 0.0),  # handle target offset = (0,0,0)
            )
            vis_pregrasp_cfg = sim_utils_vis.SphereCfg(
                radius=_vis_radius,
                visual_material=sim_utils_vis.PreviewSurfaceCfg(diffuse_color=(1.0, 0.0, 0.0)),
                collision_props=None,
                mass_props=None,
                rigid_props=None,
            )
            sim_utils_vis.spawn_sphere(
                prim_path=f"/World/envs/env_.*/{target_obj}/grasp_target/vis_pregrasp_target",
                cfg=vis_pregrasp_cfg,
                translation=self.A2_PREGRASP_OFFSET,
            )
            vis_stage0_cfg = sim_utils_vis.SphereCfg(
                radius=_vis_radius,
                visual_material=sim_utils_vis.PreviewSurfaceCfg(diffuse_color=(0.0, 0.0, 1.0)),
                collision_props=None,
                mass_props=None,
                rigid_props=None,
            )
            stage0_x_min, stage0_x_max, _stage0_y_tol = (
                self._get_a2_stage0_staging_band()
            )
            sim_utils_vis.spawn_sphere(
                prim_path=(
                    f"/World/envs/env_.*/{target_obj}/grasp_target/"
                    "vis_stage0_near_boundary"
                ),
                cfg=vis_stage0_cfg,
                translation=(-stage0_x_min, 0.0, 0.0),
            )
            sim_utils_vis.spawn_sphere(
                prim_path=(
                    f"/World/envs/env_.*/{target_obj}/grasp_target/"
                    "vis_stage0_far_boundary"
                ),
                cfg=vis_stage0_cfg,
                translation=(-stage0_x_max, 0.0, 0.0),
            )

            # Handle coordinate axis visualizer: 3 cylinders (R=X, G=Y, B=Z) at grasp_target.
            # Length and diameter = visual sphere diameter (2 * _vis_radius = 0.04m).
            _axis_len = _vis_radius * 2  # 0.04m
            _axis_radius = _vis_radius * 0.15  # thin cylinders
            _axis_colors = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
            _axis_rots = [(0.0, 90.0, 0.0), (90.0, 0.0, 0.0), (0.0, 0.0, 0.0)]  # X/Y/Z oriented cylinders
            _axis_trans = [(_axis_len / 2, 0.0, 0.10), (0.0, _axis_len / 2, 0.10), (0.0, 0.0, 0.10 + _axis_len / 2)]
            _axis_names = ["x", "y", "z"]
            for color, rot, trans, name in zip(_axis_colors, _axis_rots, _axis_trans, _axis_names):
                import math
                # Convert RPY (deg) to quaternion (w, x, y, z)
                rx, ry, rz = [math.radians(a) for a in rot]
                cx, sx = math.cos(rx/2), math.sin(rx/2)
                cy, sy = math.cos(ry/2), math.sin(ry/2)
                cz, sz = math.cos(rz/2), math.sin(rz/2)
                qw = cx*cy*cz + sx*sy*sz
                qx = sx*cy*cz - cx*sy*sz
                qy = cx*sy*cz + sx*cy*sz
                qz = cx*cy*sz - sx*sy*cz
                axis_cfg = sim_utils_vis.CylinderCfg(
                    radius=_axis_radius,
                    height=_axis_len,
                    visual_material=sim_utils_vis.PreviewSurfaceCfg(diffuse_color=color),
                    collision_props=None,
                    mass_props=None,
                    rigid_props=None,
                )
                sim_utils_vis.spawn_cylinder(
                    prim_path=f"/World/envs/env_.*/{target_obj}/grasp_target/vis_handle_axis_{name}",
                    cfg=axis_cfg,
                    translation=trans,
                    orientation=(qw, qx, qy, qz),
                )

            return

        head_target_frame_transformer_config: FrameTransformerCfg = FrameTransformerCfg(
            prim_path="/World/envs/env_.*/Robot/head_link",
            target_frames=[
                FrameTransformerCfg.FrameCfg(
                    prim_path=simulator.scene.sensors["left_hand_frame_transformer"]
                    .cfg.target_frames[0]
                    .prim_path
                ),
            ],
        )
        simulator.scene.sensors["head_target_frame_transformer"] = FrameTransformer(
            head_target_frame_transformer_config
        )

    @override
    def _apply_force_in_physics_step(self):
        if self._use_a2_base:
            return A2Base._apply_force_in_physics_step(self)
        return super()._apply_force_in_physics_step()

    def _parse_palm_side_direction(self, palm_side_direction: list[str]) -> torch.Tensor:
        """
        Convert the palm side direction to a quaternion that rotates anything
        expressed in the finger frame to point into the palm.
        """
        output = torch.zeros(len(palm_side_direction), 4, device=self.device)  # wxyz
        for i, direction in enumerate(palm_side_direction):
            if direction == "+x":
                output[i] = torch.tensor([1.0, 0.0, 0.0, 0.0], device=self.device)
            elif direction == "-x":
                output[i] = torch.tensor([0.0, 0.0, 0.0, 1.0], device=self.device)
            elif direction == "+y":
                output[i] = torch.tensor([0.7071068, 0.0, 0.0, 0.7071068], device=self.device)
            elif direction == "-y":
                output[i] = torch.tensor([0.7071068, 0.0, 0.0, -0.7071068], device=self.device)
            elif direction == "+z":
                output[i] = torch.tensor([0.7071068, 0.0, -0.7071068, 0.0], device=self.device)
            elif direction == "-z":
                output[i] = torch.tensor([0.7071068, 0.0, 0.7071068, 0.0], device=self.device)
            else:
                raise ValueError(f"Invalid palm side direction: {direction}")
        return output
