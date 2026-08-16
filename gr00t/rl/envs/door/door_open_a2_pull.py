"""Pull-only A2+Piper environment with immutable signed door semantics."""

from __future__ import annotations

import math
import json
from collections.abc import Mapping
from collections import Counter
from pathlib import Path

import torch
from isaaclab.sensors import ContactSensor, ContactSensorCfg
from isaaclab.utils.math import (
    axis_angle_from_quat,
    euler_xyz_from_quat,
    quat_from_euler_xyz,
    quat_inv,
    quat_mul,
    wrap_to_pi,
)
from typing_extensions import override

from gr00t.rl.envs.base_task.a2_base import A2Base
from gr00t.rl.envs.base_task.staged_task_base import StagedTaskBase
from gr00t.rl.envs.door.a2_pull_direction import (
    A2DoorDirection,
    a2_pull_proof_world_offset_x,
    a2_signed_stage0_nearest_staging_target,
    a2_signed_stage0_staging_band_mask,
)
from gr00t.rl.envs.door.a2_pull_telemetry import (
    A2PullEvent,
    A2_PULL_ESTIMATE_ONLY,
    A2_PULL_EVENT_NAMES,
    A2_PULL_HARD_GATE_EVENT_PREDECESSORS,
    A2_PULL_NA,
    a2_pull_event_state_names,
    advance_a2_pull_events,
    a2_pull_v5_release_tuck_override,
    validate_a2_pull_control_step,
    validate_a2_pull_episode,
)
from gr00t.rl.envs.door.a2_pull_v0_guard import (
    A2_PULL_V0_TARGET_ORIENTATION_WXYZ,
    A2_PULL_V3_PLAN_ID,
    A2_PULL_V4_PLAN_ID,
    A2_PULL_V5_PLAN_ID,
    A2_PULL_V5_CLOSER_BUCKETS,
    A2_PULL_V5_RESET_SOURCES,
    A2_PULL_V5_STATE_BANK_SCHEMA,
    A2_PULL_V5_STATE_BANK_SOURCE_SCHEMA,
    A2_PULL_V5_RELEASE_STREAK_STEPS,
    A2_PULL_V5_START_OVERRIDE_STEPS,
)
from gr00t.rl.envs.door.door_open_a2_base import (
    DoorPregrasp,
    a2_hold_base_relief_command,
    a2_hold_pd_effort_estimates,
    a2_v20_mask_stage_overtime_for_arc_probe,
)
from gr00t.rl.isaac_utils.rotations import xyzw_to_wxyz
from gr00t.rl.utils.torch_utils import torch_rand_float


def _a2_pull_v5_characterization_termination(
    reset_after_super: torch.Tensor,
    terminal_reason_bufs: Mapping[str, torch.Tensor],
    characterization_active: torch.Tensor,
    episode_length_buf: torch.Tensor,
    window_steps: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Mask only stage overtime until the diagnostic first-episode window ends."""

    if (
        not torch.is_tensor(reset_after_super)
        or reset_after_super.ndim != 1
        or reset_after_super.dtype != torch.long
        or not torch.is_tensor(characterization_active)
        or characterization_active.shape != reset_after_super.shape
        or characterization_active.dtype != torch.bool
        or not torch.is_tensor(episode_length_buf)
        or episode_length_buf.shape != reset_after_super.shape
        or episode_length_buf.dtype not in (torch.int32, torch.int64)
        or isinstance(window_steps, bool)
        or not isinstance(window_steps, int)
        or window_steps <= 0
    ):
        raise RuntimeError("HOMIE characterization termination tensors have invalid contracts.")
    expected_device = reset_after_super.device
    if (
        characterization_active.device != expected_device
        or episode_length_buf.device != expected_device
    ):
        raise RuntimeError("HOMIE characterization termination tensors must share a device.")
    if not isinstance(terminal_reason_bufs, Mapping) or "stage_overtime" not in terminal_reason_bufs:
        raise RuntimeError("HOMIE characterization requires the stage_overtime terminal reason buffer.")
    stage_overtime_reason = terminal_reason_bufs["stage_overtime"]
    if (
        not torch.is_tensor(stage_overtime_reason)
        or stage_overtime_reason.shape != reset_after_super.shape
        or stage_overtime_reason.dtype != torch.bool
        or stage_overtime_reason.device != expected_device
    ):
        raise RuntimeError("HOMIE characterization stage_overtime reason has an invalid contract.")
    other_terminal_reason = torch.zeros_like(stage_overtime_reason)
    for reason_name, reason_buf in terminal_reason_bufs.items():
        if reason_name == "stage_overtime":
            continue
        if (
            not torch.is_tensor(reason_buf)
            or reason_buf.shape != reset_after_super.shape
            or reason_buf.dtype != torch.bool
            or reason_buf.device != expected_device
        ):
            raise RuntimeError(
                "HOMIE characterization terminal reason buffers must share the reset contract."
            )
        other_terminal_reason |= reason_buf
    if torch.any(characterization_active & (episode_length_buf > window_steps)):
        raise RuntimeError("HOMIE characterization overran its exact first-episode window.")
    pending_window = characterization_active & (episode_length_buf < window_steps)
    updated_reset, updated_stage_overtime, _ = a2_v20_mask_stage_overtime_for_arc_probe(
        reset_after_super,
        stage_overtime_reason,
        other_terminal_reason,
        pending_window,
    )
    diagnostic_done = characterization_active & (episode_length_buf == window_steps)
    updated_stage_overtime &= ~diagnostic_done
    return updated_reset, updated_stage_overtime, diagnostic_done


class DoorOpenA2Pull(DoorPregrasp):
    """Pull-v0 specialization that leaves the push environment namespace unchanged."""

    A2_PREGRASP_OFFSET = (0.10, 0.0, 0.0)
    A2_PUSH_ANCHOR_TARGET_ORIENTATION_WXYZ = (0.5, 0.5, 0.5, 0.5)
    A2_PULL_DOOR_BODY_FRAME_CONTACT_SENSOR = "a2_pull_door_body_frame_contact_sensor"
    A2_PULL_DOOR_ARM_FRAME_CONTACT_SENSOR = "a2_pull_door_arm_frame_contact_sensor"
    # Source-grounded panel geometry from door.py: the panel cube has a 0.02 m
    # half-thickness and the builder's end gap is gap_width=0.002 m.
    _A2_PULL_PANEL_HALF_THICKNESS_M = 0.02
    _A2_PULL_PANEL_END_GAP_M = 0.002
    _A2_PULL_DOOR_HINGE_LOCAL_X_M = 0.02
    # The A2_Piper trunk URDF (data/robots/A2_Piper/a2_piper.urdf) horizontal
    # envelope is approximately 0.398 m;
    # use the source-grounded 0.40 m circular footprint for report-only clearance.
    _A2_PULL_TRUNK_FOOTPRINT_RADIUS_M = 0.40
    _A2_PULL_V5_PROBE_WAYPOINT_TOLERANCE_M = 0.20
    _A2_PULL_V5_PROBE_YAW_TOLERANCE_RAD = 0.25
    _A2_PULL_V5_PROBE_SEQUENCES = {
        "S1": ("straight_minus_x",),
        "S2": ("side_step",),
        "S3": ("side_step", "straight_minus_x"),
        "S4": ("straight_minus_x", "side_step"),
    }
    _A2_PULL_V5_PROBE_PRIMITIVES = {
        "straight_minus_x": (-0.30, 0.0, 0.0),
        "turn_then_forward": (0.0, 0.0, -0.55),
        "side_step": (-0.18, 0.24, 0.0),
        "arc": (-0.22, 0.0, 0.35),
    }
    _A2_PULL_V5_CHARACTERIZATION_RAW_YAW_LIMIT = 2.0
    _A2_PULL_V5_CHARACTERIZATION_YAW_MAGNITUDES = (0.05, 0.1, 0.2, 0.4, 0.8, 2.0)
    _A2_PULL_V5_CHARACTERIZATION_DURATIONS_S = (1.0, 2.0, 4.0)
    _A2_PULL_V5_CHARACTERIZATION_PRIMITIVES = ("none", "straight_minus_x", "side_step")
    _A2_PULL_V5_CHARACTERIZATION_TRACE_SCHEMA = (
        "a2_piper_pull_v5_interface_characterization_trace_v1"
    )
    _A2_PULL_V5_CHARACTERIZATION_PLAN_ID = (
        "a2_piper_pull_v5_3_locomotion_interface_probe"
    )

    def __init__(self, config, device):
        config_mapping = config.get("config", config)
        if not isinstance(config_mapping, Mapping):
            raise RuntimeError("Pull-v0 config must expose a mapping for env.config.")
        self._pull_direction = A2DoorDirection(
            door_open_io=config_mapping["a2_pull_door_open_io"],
            door_open_lr=config_mapping["a2_pull_door_open_lr"],
        )
        super().__init__(config, device)

    @override
    def step(self, actor_state):
        """Apply the canonical bank-start arm release before DeltaActionBase accumulation."""

        if not self._is_a2_pull_v5():
            return super().step(actor_state)
        enabled = self.config.get("a2_pull_v5_start_override_enabled", False)
        if not isinstance(enabled, bool):
            raise RuntimeError("a2_pull_v5_start_override_enabled must be bool.")
        steps = self.config.get("a2_pull_v5_start_override_steps", A2_PULL_V5_START_OVERRIDE_STEPS)
        if isinstance(steps, bool) or not isinstance(steps, int):
            raise RuntimeError("a2_pull_v5_start_override_steps must be an integer.")
        if enabled and steps != A2_PULL_V5_START_OVERRIDE_STEPS:
            raise RuntimeError(
                "a2_pull_v5_start_override_steps must be exactly 50 when enabled; "
                f"got {steps!r}."
            )
        if not enabled:
            self._a2_pull_v5_start_override_active[:] = False
            return super().step(actor_state)

        actions = actor_state["actions"]
        expected_dim = self._a2_high_level_action_dim + self._a2_leg_action_dim
        if (
            not torch.is_tensor(actions)
            or tuple(actions.shape) != (self.num_envs, expected_dim)
            or actions.device != torch.device(self.device)
            or not actions.is_floating_point()
            or not torch.all(torch.isfinite(actions))
        ):
            raise RuntimeError(
                "Pull-v5 start override requires a finite device-local trainer action with "
                f"shape ({self.num_envs}, {expected_dim})."
            )
        if tuple(self._delta_actions.shape) != (self.num_envs, 6):
            raise RuntimeError(
                "Pull-v5 start override requires cumulative arm state shape "
                f"({self.num_envs}, 6); got {tuple(self._delta_actions.shape)}."
            )
        if not isinstance(self._delta_action_scale, (int, float)) or self._delta_action_scale <= 0.0:
            raise RuntimeError("Pull-v5 start override requires a positive delta_action_scale.")

        reset_source = torch.tensor(
            [source == "bank_natural_e5_override" for source in self._a2_pull_v5_reset_source],
            dtype=torch.bool,
            device=self.device,
        )
        episode_step = self.episode_length_buf.to(dtype=torch.long)
        in_window = (episode_step >= 0) & (episode_step < steps)
        requested = torch.full_like(reset_source, enabled) & reset_source
        active = requested & in_window
        self._a2_pull_v5_start_override_active[:] = active
        self._a2_pull_v5_start_override_active_steps += active.long()
        self._a2_pull_v5_start_override_outside_window |= active & ~in_window

        applied_actions = actions.clone()
        if torch.any(active):
            applied_actions[active, 5:11] = (
                -self._delta_actions[active] / float(self._delta_action_scale)
            )
            applied_actions[active, 11] = 1.0
            base_equal = torch.all(applied_actions[:, :5] == actions[:, :5], dim=-1)
            self._a2_pull_v5_start_override_base_slice_equal &= torch.where(
                active, base_equal, torch.ones_like(base_equal)
            )

        next_actor_state = dict(actor_state)
        next_actor_state["actions"] = applied_actions
        return super().step(next_actor_state)

    @override
    def _check_termination(self):
        super()._check_termination()
        if not self._a2_pull_v5_characterization_enabled:
            return
        contract = self._get_a2_pull_v5_characterization_contract()
        updated_reset, updated_stage_overtime, diagnostic_done = (
            _a2_pull_v5_characterization_termination(
                self.reset_buf,
                self._terminal_reason_bufs,
                self._a2_pull_v5_characterization_active,
                self.episode_length_buf,
                int(contract["window_steps"]),
            )
        )
        self.reset_buf[:] = updated_reset
        self._terminal_reason_bufs["stage_overtime"][:] = updated_stage_overtime
        self._mark_terminal_reason("complete", diagnostic_done)
        self.reset_buf |= diagnostic_done.to(dtype=self.reset_buf.dtype)

    def _is_a2_pull_v5(self) -> bool:
        return self.config.get("a2_v20_R1_plan_id") == A2_PULL_V5_PLAN_ID

    def _is_a2_pull_v3(self) -> bool:
        return self.config.get("a2_v20_R1_plan_id") == A2_PULL_V3_PLAN_ID

    def _is_a2_pull_v4(self) -> bool:
        return self.config.get("a2_v20_R1_plan_id") == A2_PULL_V4_PLAN_ID

    def _is_a2_pull_traversal(self) -> bool:
        return self._is_a2_pull_v3() or self._is_a2_pull_v4() or self._is_a2_pull_v5()

    def _get_a2_pull_threshold_mode(self) -> str:
        mode = self.config.get("a2_pull_threshold_mode")
        if mode not in ("report_only", "hard_gate"):
            raise RuntimeError(
                "Pull threshold mode must be exactly 'report_only' or 'hard_gate'; "
                f"got {mode!r}."
            )
        return mode

    def _get_a2_pull_e3_latch_threshold_m(self) -> float:
        return self._get_required_positive_float_config(
            "a2_pull_e3_latch_threshold_m",
            "pull E3 latch release telemetry",
        )

    @override
    def _get_a2_grasp_target_orientation_wxyz(self) -> tuple[float, float, float, float]:
        configured = self.config.get("a2_pull_target_orientation_wxyz")
        expected = (
            A2_PULL_V0_TARGET_ORIENTATION_WXYZ
            if self._pull_direction.door_open_io == "in"
            else self.A2_PUSH_ANCHOR_TARGET_ORIENTATION_WXYZ
        )
        if configured is None or tuple(float(value) for value in configured) != expected:
            raise RuntimeError(
                "Pull-v0 target orientation must match the direction-selected overlay "
                f"{expected}; got {configured!r}."
            )
        return expected

    @override
    def _init_door_metadata(self):
        super()._init_door_metadata()
        self.door_open_io.fill_(float(self._pull_direction.io_sign))

    @override
    def _init_buffers(self):
        super()._init_buffers()
        door_articulation = self.simulator.scene.articulations["door"]
        door_panel_body_ids, door_panel_body_names = door_articulation.find_bodies(
            "door_panel", preserve_order=True
        )
        if door_panel_body_names != ["door_panel"] or len(door_panel_body_ids) != 1:
            raise RuntimeError(
                "Pull clearance requires exactly one door_panel articulation body; "
                f"got ids={door_panel_body_ids!r}, names={door_panel_body_names!r}."
            )
        robot_articulation = self.simulator.scene.articulations["robot"]
        trunk_body_ids, trunk_body_names = robot_articulation.find_bodies(
            "trunk", preserve_order=True
        )
        if trunk_body_names != ["trunk"] or len(trunk_body_ids) != 1:
            raise RuntimeError(
                "Pull clearance requires exactly one trunk articulation body; "
                f"got ids={trunk_body_ids!r}, names={trunk_body_names!r}."
            )
        self._a2_pull_door_panel_body_id = door_panel_body_ids[0]
        self._a2_pull_trunk_body_id = trunk_body_ids[0]
        self._a2_pull_event_reached = torch.zeros(
            self.num_envs,
            len(A2PullEvent),
            dtype=torch.bool,
            device=self.device,
        )
        self._a2_pull_stable_unlatch_handle_ever = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_stable_unlatch_latch_ever = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_relock_handle_ever = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_relock_latch_ever = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_prev_handle_unlatched = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_prev_latch_unlatched = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_first_event_step = torch.full(
            (self.num_envs, len(A2PullEvent)),
            -1,
            dtype=torch.long,
            device=self.device,
        )
        self._a2_pull_first_event_time_s = torch.full(
            (self.num_envs, len(A2PullEvent)),
            float("nan"),
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_capture_root_x = torch.full(
            (self.num_envs,),
            float("nan"),
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_capture_valid = torch.zeros(
            self.num_envs,
            dtype=torch.bool,
            device=self.device,
        )
        self._a2_pull_max_tensile_retreat_m = torch.zeros(
            self.num_envs,
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_release_or_hold_decision = torch.zeros(
            self.num_envs,
            dtype=torch.bool,
            device=self.device,
        )
        self._a2_pull_proof_active = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_proof_start_root_x = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_proof_last_root_x = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_proof_duration_s = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_proof_displacement_m = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_proof_streak = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_proof_valid = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_minimum_panel_robot_clearance_m = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_clearance_ready = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_aperture_ready = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_passage = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_passage_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_planar_crossing = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_planar_crossing_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_detour = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_approach = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_approach_active = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_frame_approach_pre_aperture_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_frame_approach_post_frame_passage_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_frame_midpoint_distance_min_m = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_deliberate_release = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_deliberate_release_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_first_negative_x_motion_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_prev_stable_contact = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_prev_panel_contact = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_post_release_recontact_count = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_base_path_length_m = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_prev_base_pos_xy = torch.full(
            (self.num_envs, 2), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_base_reversal_count = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_prev_travel_velocity = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_swept_arc_clearance_margin_current_m = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_swept_arc_clearance_margin_min_m = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_corridor_door_wide_pre_aperture_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_corridor_clean_passage_pre_aperture_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_stage0_staging_band = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_stage0_arm_default = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_stage0_base_still = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_first_scripted_activation_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_hinge_at_first_positive_progress_rad = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_held_hinge_max_rad = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_hinge_at_decision_rad = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_root_outward_excursion_m = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_first_path_reversal_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_body_panel_contact_steps = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_body_panel_contact_impulse_ns = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_prev_handle_to_tcp_pos = torch.full(
            (self.num_envs, 3),
            float("nan"),
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_handle_local_slip_xyz_mps = torch.full(
            (self.num_envs, 3),
            float("nan"),
            dtype=torch.float32,
            device=self.device,
        )
        self._a2_pull_handle_local_slip_valid = torch.zeros(
            self.num_envs,
            dtype=torch.bool,
            device=self.device,
        )
        self._a2_pull_passage_attempt_hinge_rad = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_last_raw_reward_components: dict[str, torch.Tensor] = {}
        self._a2_pull_runtime_telemetry_contract_checked = False
        self._a2_pull_runtime_telemetry_contract_sample: list[dict] = []
        if self._is_a2_pull_v5():
            self._a2_pull_v5_persistent_release_streak = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_persistent_release = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_intervention_elapsed_steps = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_intervention_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_intervention_fired = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_start_override_active = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_start_override_active_steps = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_start_override_base_slice_equal = torch.ones(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_start_override_outside_window = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_solvable = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_anchor_initialized = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_waypoint_target_xy = torch.full(
                (self.num_envs, 2), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_probe_yaw_target = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_probe_waypoint_error_m = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_probe_yaw_error_rad = torch.full(
                (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
            )
            self._a2_pull_v5_probe_waypoint_arrived = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_yaw_arrived = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_anchor_pass = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_phase_index = torch.zeros(
                self.num_envs, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_probe_phase_initialized = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_phase_waypoint_arrived = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_phase_yaw_arrived = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_sequence_complete = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_probe_sequence_id: str | None = None
            self._a2_pull_v5_probe_sequence_phases: tuple[str, ...] = ()
            self._a2_pull_v5_capture_e5_seen = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_capture_pending = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_capture_recorded = torch.zeros(
                self.num_envs, dtype=torch.bool, device=self.device
            )
            self._a2_pull_v5_capture_target_step = torch.full(
                (self.num_envs,), -1, dtype=torch.long, device=self.device
            )
            self._a2_pull_v5_source_b_capture_frozen = False
            declared_reset_source = self.config.get("a2_pull_v5_reset_source", "natural")
            if declared_reset_source not in A2_PULL_V5_RESET_SOURCES:
                raise RuntimeError(
                    "Pull-v5 declared reset_source must be one of "
                    f"{A2_PULL_V5_RESET_SOURCES!r}; got {declared_reset_source!r}."
                )
            self._a2_pull_v5_declared_reset_source = [
                str(declared_reset_source) for _ in range(self.num_envs)
            ]
            self._a2_pull_v5_reset_source = ["natural" for _ in range(self.num_envs)]
            self._a2_pull_v5_pending_reset_source = ["natural" for _ in range(self.num_envs)]
            self._a2_pull_v5_bank_slot_sources: list[str] = []
            self._a2_pull_v5_bank_slot_indices: list[int] = []
            self._a2_pull_v5_bank_metadata: dict[str, object] = {}
            self._a2_pull_v5_bank_eval_indices: list[int] = []
            self._a2_pull_v5_bank_cursor = 0
            self._a2_pull_v5_bank_loaded = False

        characterization_enabled = self.config.get(
            "a2_pull_v5_characterization_enabled", False
        )
        if not isinstance(characterization_enabled, bool):
            raise RuntimeError("a2_pull_v5_characterization_enabled must be bool.")
        if characterization_enabled and not self._is_a2_pull_v5():
            raise RuntimeError("HOMIE characterization requires the v5 plan guard.")
        self._a2_pull_v5_characterization_enabled = characterization_enabled
        self._a2_pull_v5_characterization_pending = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v5_characterization_active = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v5_characterization_xy_target_initialized = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._a2_pull_v5_characterization_xy_target = torch.full(
            (self.num_envs, 2), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_episode_indices = torch.zeros(
            self.num_envs, dtype=torch.long, device=self.device
        )
        self._a2_pull_v5_characterization_step = torch.full(
            (self.num_envs,), -1, dtype=torch.long, device=self.device
        )
        self._a2_pull_v5_characterization_requested_u = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_phase_u = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_raw_base = torch.zeros(
            self.num_envs, 5, dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_physical_base = torch.zeros(
            self.num_envs, 5, dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_pre_root_pos = torch.full(
            (self.num_envs, 3), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_pre_root_yaw = torch.full(
            (self.num_envs,), float("nan"), dtype=torch.float32, device=self.device
        )
        self._a2_pull_v5_characterization_phase = ["inactive" for _ in range(self.num_envs)]
        self._a2_pull_v5_characterization_trace_rows: list[dict[str, object]] = []

    @override
    def _init_a2_door_pregrasp_state(self):
        super()._init_a2_door_pregrasp_state()
        if self.config.get("a2_pull_v5_census_enabled", False) and "a2_pull_prev_stable_contact" not in self.staged_reset_buf:
            self._register_buffer_to_track(
                "a2_pull_prev_stable_contact",
                tuple(self._a2_pull_prev_stable_contact.shape),
                lambda env_ids: self._a2_pull_prev_stable_contact[env_ids].clone(),
                lambda env_ids, data: self._load_a2_pull_v5_named_buffer(
                    "a2_pull_prev_stable_contact", env_ids, data
                ),
                dtype=self._a2_pull_prev_stable_contact.dtype,
            )
        if self._is_a2_pull_v5():
            self._register_a2_pull_v5_staged_reset_buffers()
            injection_enabled = self.config["a2_pull_v5_stage4_bank_injection_enabled"]
            if not isinstance(injection_enabled, bool):
                raise RuntimeError("Pull-v5 stage4 bank injection must be an explicit bool.")
            if injection_enabled:
                self._load_a2_pull_v5_state_bank()
            elif self.config.get("a2_pull_v5_reset_source", "natural") != "natural":
                self._load_a2_pull_v5_eval_state_bank()

    def _register_a2_pull_v5_staged_reset_buffers(self) -> None:
        """Track every pull telemetry tensor restored with a Stage-4 bank state."""

        if not self.enable_staged_reset:
            raise RuntimeError("Pull-v5 state-bank injection requires enable_staged_reset=true.")
        names = (
            "a2_pull_event_reached",
            "a2_pull_stable_unlatch_handle_ever",
            "a2_pull_stable_unlatch_latch_ever",
            "a2_pull_relock_handle_ever",
            "a2_pull_relock_latch_ever",
            "a2_pull_prev_handle_unlatched",
            "a2_pull_prev_latch_unlatched",
            "a2_pull_first_event_step",
            "a2_pull_first_event_time_s",
            "a2_pull_capture_root_x",
            "a2_pull_capture_valid",
            "a2_pull_max_tensile_retreat_m",
            "a2_pull_release_or_hold_decision",
            "a2_pull_proof_active",
            "a2_pull_proof_start_root_x",
            "a2_pull_proof_last_root_x",
            "a2_pull_proof_duration_s",
            "a2_pull_proof_displacement_m",
            "a2_pull_proof_streak",
            "a2_pull_proof_valid",
            "a2_pull_minimum_panel_robot_clearance_m",
            "a2_pull_clearance_ready",
            "a2_pull_aperture_ready",
            "a2_pull_frame_passage",
            "a2_pull_frame_passage_step",
            "a2_pull_planar_crossing",
            "a2_pull_planar_crossing_step",
            "a2_pull_detour",
            "a2_pull_frame_approach",
            "a2_pull_frame_approach_active",
            "a2_pull_frame_approach_pre_aperture_steps",
            "a2_pull_frame_approach_post_frame_passage_steps",
            "a2_pull_frame_midpoint_distance_min_m",
            "a2_pull_deliberate_release",
            "a2_pull_deliberate_release_step",
            "a2_pull_first_negative_x_motion_step",
            "a2_pull_prev_stable_contact",
            "a2_pull_prev_panel_contact",
            "a2_pull_post_release_recontact_count",
            "a2_pull_base_path_length_m",
            "a2_pull_prev_base_pos_xy",
            "a2_pull_base_reversal_count",
            "a2_pull_prev_travel_velocity",
            "a2_pull_swept_arc_clearance_margin_current_m",
            "a2_pull_swept_arc_clearance_margin_min_m",
            "a2_pull_corridor_door_wide_pre_aperture_steps",
            "a2_pull_corridor_clean_passage_pre_aperture_steps",
            "a2_pull_stage0_staging_band",
            "a2_pull_stage0_arm_default",
            "a2_pull_stage0_base_still",
            "a2_pull_first_scripted_activation_step",
            "a2_pull_hinge_at_first_positive_progress_rad",
            "a2_pull_held_hinge_max_rad",
            "a2_pull_hinge_at_decision_rad",
            "a2_pull_root_outward_excursion_m",
            "a2_pull_first_path_reversal_step",
            "a2_pull_body_panel_contact_steps",
            "a2_pull_body_panel_contact_impulse_ns",
            "a2_pull_prev_handle_to_tcp_pos",
            "a2_pull_handle_local_slip_xyz_mps",
            "a2_pull_handle_local_slip_valid",
            "a2_pull_v5_persistent_release_streak",
            "a2_pull_v5_persistent_release",
            "a2_pull_v5_intervention_elapsed_steps",
            "a2_pull_v5_intervention_active",
        )
        for name in names:
            tensor = getattr(self, f"_{name}")
            if not torch.is_tensor(tensor) or tensor.shape[0] != self.num_envs:
                raise RuntimeError(
                    f"Pull-v5 staged buffer {name} must be a tensor with leading env axis; "
                    f"got {getattr(tensor, 'shape', None)}."
                )
            if name in self.staged_reset_buf:
                raise RuntimeError(f"Pull-v5 staged buffer name collides with existing entry: {name}")
            self._register_buffer_to_track(
                name,
                tuple(tensor.shape),
                lambda env_ids, name=name: self._store_a2_pull_v5_named_buffer(name, env_ids),
                lambda env_ids, data, name=name: self._load_a2_pull_v5_named_buffer(name, env_ids, data),
                dtype=tensor.dtype,
            )

    def _store_a2_pull_v5_named_buffer(self, name: str, env_ids: torch.Tensor) -> torch.Tensor:
        value = getattr(self, f"_{name}")
        return value[env_ids].clone()

    def _load_a2_pull_v5_named_buffer(self, name: str, env_ids: torch.Tensor, data: torch.Tensor) -> None:
        value = getattr(self, f"_{name}")
        expected = (len(env_ids), *value.shape[1:])
        if tuple(data.shape) != expected or data.dtype != value.dtype or data.device != value.device:
            raise RuntimeError(
                f"Pull-v5 staged buffer {name} shape/dtype/device mismatch: "
                f"expected={expected}/{value.dtype}/{value.device}, got={tuple(data.shape)}/{data.dtype}/{data.device}."
            )
        value[env_ids] = data

    def apply_a2_pull_v5_intervention(self, policy_action: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Apply the paired P2 one-second arm/gripper override to a high-level action."""

        if not self._is_a2_pull_v5():
            raise RuntimeError("Pull-v5 intervention is only available under the v5 plan guard.")
        enabled = self.config["a2_pull_v5_intervention_enabled"]
        if not isinstance(enabled, bool):
            raise RuntimeError("a2_pull_v5_intervention_enabled must be bool.")
        hinge = self._get_door_joint_pos("pull-v5 intervention", 3)[:, 0]
        aperture = self._a2_pull_aperture_ready
        trigger = aperture & (hinge >= 1.60)
        newly_active = enabled & trigger & ~self._a2_pull_v5_intervention_fired
        self._a2_pull_v5_intervention_fired |= newly_active
        self._a2_pull_v5_intervention_elapsed_steps[newly_active] = 0
        self._a2_pull_v5_intervention_active |= newly_active
        # Keep the one-second window latched after the trigger even if the
        # instantaneous aperture predicate flickers on the next control step.
        latched_hinge = torch.where(
            self._a2_pull_v5_intervention_active,
            torch.full_like(hinge, 1.60),
            hinge,
        )
        latched_aperture = aperture | self._a2_pull_v5_intervention_active
        if (
            not torch.is_tensor(self._delta_actions)
            or tuple(self._delta_actions.shape) != (self.num_envs, 6)
            or self._delta_actions.device != torch.device(self.device)
            or not torch.all(torch.isfinite(self._delta_actions))
        ):
            raise RuntimeError(
                "Pull-v5 intervention requires finite cumulative arm targets with shape (N,6)."
            )
        if not isinstance(self._delta_action_scale, (int, float)) or self._delta_action_scale <= 0:
            raise RuntimeError("Pull-v5 intervention requires a positive delta_action_scale.")
        # DeltaActionBase applies this raw arm command before writing the
        # cumulative target.  Driving by -d_prev/scale lands at the actual
        # Piper default pose (d_des=0), rather than holding the current target.
        default_arm_action = -self._delta_actions / float(self._delta_action_scale)
        applied, active = a2_pull_v5_release_tuck_override(
            policy_action,
            latched_hinge,
            latched_aperture,
            self._a2_pull_v5_intervention_elapsed_steps,
            dt=float(self.dt),
            enabled=enabled,
            arm_action=default_arm_action,
        )
        self._a2_pull_v5_intervention_elapsed_steps[active] += 1
        self._a2_pull_v5_intervention_active &= active
        return applied, active

    def apply_a2_pull_v5_probe_command(
        self,
        policy_action: torch.Tensor,
        command_name: str,
        fixture: str,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Apply one registered P1 sequence through the A2 action path."""

        if not self._is_a2_pull_v5():
            raise RuntimeError("Pull-v5 probe commands require the v5 plan guard.")
        if fixture not in {"anchor", "door"}:
            raise RuntimeError(f"Pull-v5 probe fixture must be anchor or door; got {fixture!r}.")
        if command_name in self._A2_PULL_V5_PROBE_SEQUENCES:
            sequence_id = command_name
            sequence_phases = self._A2_PULL_V5_PROBE_SEQUENCES[command_name]
        elif command_name in self._A2_PULL_V5_PROBE_PRIMITIVES:
            sequence_id = command_name
            sequence_phases = (command_name,)
        else:
            raise RuntimeError(f"Pull-v5 probe command is not registered: {command_name!r}.")
        if self._a2_pull_v5_probe_sequence_id not in (None, sequence_id):
            raise RuntimeError(
                "Pull-v5 probe sequence cannot change while phase state is live; "
                f"got {self._a2_pull_v5_probe_sequence_id!r} then {sequence_id!r}."
            )
        self._a2_pull_v5_probe_sequence_id = sequence_id
        self._a2_pull_v5_probe_sequence_phases = tuple(sequence_phases)
        if (
            not torch.is_tensor(policy_action)
            or tuple(policy_action.shape) != (self.num_envs, 12)
            or not policy_action.is_floating_point()
            or policy_action.device != torch.device(self.device)
            or not torch.all(torch.isfinite(policy_action))
        ):
            raise RuntimeError("Pull-v5 probe requires a finite device-local high-level action (N,12).")
        lattice_scale = self.config.get("a2_pull_v5_lattice_scale", 1.0)
        if (
            isinstance(lattice_scale, bool)
            or not isinstance(lattice_scale, (int, float))
            or not math.isfinite(float(lattice_scale))
            or float(lattice_scale) <= 0.0
        ):
            raise RuntimeError("Pull-v5 probe lattice scale must be a finite positive number.")
        lattice_scale = float(lattice_scale)
        waypoint_tolerance = self.config.get(
            "a2_pull_v5_probe_waypoint_tolerance_m",
            self._A2_PULL_V5_PROBE_WAYPOINT_TOLERANCE_M,
        )
        if (
            isinstance(waypoint_tolerance, bool)
            or not isinstance(waypoint_tolerance, (int, float))
            or not math.isfinite(float(waypoint_tolerance))
            or float(waypoint_tolerance) <= 0.0
        ):
            raise RuntimeError("Pull-v5 probe waypoint tolerance must be a finite positive number.")
        waypoint_tolerance = float(waypoint_tolerance)
        yaw_tolerance = self.config.get(
            "a2_pull_v5_probe_yaw_tolerance_rad",
            self._A2_PULL_V5_PROBE_YAW_TOLERANCE_RAD,
        )
        if (
            isinstance(yaw_tolerance, bool)
            or not isinstance(yaw_tolerance, (int, float))
            or not math.isfinite(float(yaw_tolerance))
            or float(yaw_tolerance) <= 0.0
        ):
            raise RuntimeError("Pull-v5 probe yaw tolerance must be a finite positive number.")
        yaw_tolerance = float(yaw_tolerance)
        phase_commands = torch.tensor(
            [self._A2_PULL_V5_PROBE_PRIMITIVES[name] for name in sequence_phases],
            device=self.device,
            dtype=policy_action.dtype,
        ) * lattice_scale
        phase_xy_commands = phase_commands[:, :2]
        phase_yaw_commands = phase_commands[:, 2]
        phase_index = self._a2_pull_v5_probe_phase_index
        if torch.any(phase_index >= len(sequence_phases)):
            raise RuntimeError("Pull-v5 probe phase index exceeded the configured sequence.")
        robot = self.simulator.scene.articulations["robot"]
        if fixture == "anchor":
            uninitialized = ~self._a2_pull_v5_probe_anchor_initialized
            if torch.any(uninitialized):
                env_ids = torch.where(uninitialized)[0]
                anchor_root = robot.data.default_root_state[env_ids].clone()
                anchor_root[:, :3] += self.env_origins[env_ids]
                anchor_root[:, 0] = self.env_origins[env_ids, 0] + (
                    float(self._pull_direction.approach_side_x) * 1.0
                )
                anchor_root[:, 1] = self.env_origins[env_ids, 1]
                anchor_roll, anchor_pitch, _ = euler_xyz_from_quat(anchor_root[:, 3:7])
                anchor_root[:, 3:7] = quat_from_euler_xyz(
                    anchor_roll,
                    anchor_pitch,
                    torch.full_like(anchor_roll, math.pi),
                )
                anchor_root[:, 7:13] = 0.0
                robot.write_root_state_to_sim(anchor_root, env_ids)
                anchor_dof_pos = self.default_dof_pos.to(self.device).expand(len(env_ids), -1).clone()
                anchor_dof_pos[:, self._upper_non_gripper_dof_idx] = self._get_a2_arm_default_dof_pos(
                    env_ids
                )
                anchor_dof_pos[:, self._a2_gripper_dof_indices] = self._a2_gripper_open_target
                robot.write_joint_state_to_sim(
                    anchor_dof_pos,
                    torch.zeros_like(anchor_dof_pos),
                    env_ids=env_ids,
                )
                robot.reset(env_ids)
                self._refresh_sim_tensors()
                _, _, anchor_root_yaw = euler_xyz_from_quat(anchor_root[:, 3:7])
                self._a2_pull_v5_probe_waypoint_target_xy[env_ids] = (
                    anchor_root[:, :2] + phase_xy_commands[0]
                )
                self._a2_pull_v5_probe_yaw_target[env_ids] = (
                    anchor_root_yaw + phase_yaw_commands[0]
                )
                self._a2_pull_v5_probe_anchor_initialized[env_ids] = True
        root_pos = self.simulator.scene.articulations["robot"].data.root_pos_w
        root_quat_w = self.simulator.scene.articulations["robot"].data.root_quat_w
        if (
            tuple(root_pos.shape) != (self.num_envs, 3)
            or tuple(root_quat_w.shape) != (self.num_envs, 4)
            or root_pos.device != policy_action.device
            or root_quat_w.device != policy_action.device
            or root_quat_w.dtype != policy_action.dtype
            or not torch.all(torch.isfinite(root_pos))
            or not torch.all(torch.isfinite(root_quat_w))
        ):
            raise RuntimeError("Pull-v5 probe requires finite robot root state tensors on the action device.")
        _, _, root_yaw = euler_xyz_from_quat(root_quat_w)
        phase_xy = phase_xy_commands[phase_index]
        phase_yaw = phase_yaw_commands[phase_index]
        initialize_target = ~self._a2_pull_v5_probe_phase_initialized
        self._a2_pull_v5_probe_waypoint_target_xy[initialize_target] = (
            root_pos[initialize_target, :2] + phase_xy[initialize_target]
        )
        self._a2_pull_v5_probe_yaw_target[initialize_target] = (
            root_yaw[initialize_target] + phase_yaw[initialize_target]
        )
        self._a2_pull_v5_probe_phase_initialized[initialize_target] = True
        waypoint_error = self._a2_pull_v5_probe_waypoint_target_xy - root_pos[:, :2]
        waypoint_error_m = torch.linalg.norm(waypoint_error, dim=-1)
        yaw_error = wrap_to_pi(self._a2_pull_v5_probe_yaw_target - root_yaw)
        phase_complete = (
            self._a2_pull_v5_probe_phase_initialized
            & (waypoint_error_m <= waypoint_tolerance)
            & (torch.abs(yaw_error) <= yaw_tolerance)
            & ~self._a2_pull_v5_probe_sequence_complete
        )
        next_phase = phase_index + 1
        advance_phase = phase_complete & (next_phase < len(sequence_phases))
        if torch.any(advance_phase):
            next_phase_index = next_phase[advance_phase]
            self._a2_pull_v5_probe_phase_index[advance_phase] = next_phase_index
            self._a2_pull_v5_probe_phase_waypoint_arrived[advance_phase] = False
            self._a2_pull_v5_probe_phase_yaw_arrived[advance_phase] = False
            self._a2_pull_v5_probe_waypoint_target_xy[advance_phase] = (
                root_pos[advance_phase, :2] + phase_xy_commands[next_phase_index]
            )
            self._a2_pull_v5_probe_yaw_target[advance_phase] = (
                root_yaw[advance_phase] + phase_yaw_commands[next_phase_index]
            )
            phase_index = self._a2_pull_v5_probe_phase_index
            phase_xy = phase_xy_commands[phase_index]
            phase_yaw = phase_yaw_commands[phase_index]
            waypoint_error = self._a2_pull_v5_probe_waypoint_target_xy - root_pos[:, :2]
            waypoint_error_m = torch.linalg.norm(waypoint_error, dim=-1)
            yaw_error = wrap_to_pi(self._a2_pull_v5_probe_yaw_target - root_yaw)
        _residual, solvable, _body_velocity, raw_base = a2_hold_base_relief_command(
            waypoint_error,
            root_quat_w,
            torch.ones(self.num_envs, dtype=torch.bool, device=self.device),
            physical_speed_mps=0.30,
            base_command_scale=self._a2_base_command_scale,
            min_solvable_horizontal_error_m=1.0e-3,
        )
        registered_yaw_limit = max(
            abs(command[2]) for command in self._A2_PULL_V5_PROBE_PRIMITIVES.values()
        )
        yaw_command_limit = torch.where(
            torch.abs(phase_yaw) > 0.0,
            torch.abs(phase_yaw),
            torch.full_like(phase_yaw, registered_yaw_limit),
        )
        yaw_command = -torch.sign(yaw_error) * torch.minimum(
            torch.abs(yaw_error), yaw_command_limit
        )
        solvable |= torch.abs(yaw_error) >= 1.0e-3
        applied = policy_action.clone()
        applied[:, :5] = raw_base
        applied[:, 2] = yaw_command / float(self._a2_base_command_scale)
        waypoint_arrived = waypoint_error_m <= waypoint_tolerance
        yaw_arrived = torch.abs(yaw_error) <= yaw_tolerance
        final_phase_arrived = (
            waypoint_arrived
            & yaw_arrived
            & (phase_index == len(sequence_phases) - 1)
            & self._a2_pull_v5_probe_phase_initialized
        )
        self._a2_pull_v5_probe_phase_waypoint_arrived[:] = waypoint_arrived
        self._a2_pull_v5_probe_phase_yaw_arrived[:] = yaw_arrived
        self._a2_pull_v5_probe_sequence_complete |= final_phase_arrived
        self._a2_pull_v5_probe_waypoint_error_m[:] = waypoint_error_m
        self._a2_pull_v5_probe_yaw_error_rad[:] = torch.abs(yaw_error)
        self._a2_pull_v5_probe_waypoint_arrived[:] = waypoint_arrived
        self._a2_pull_v5_probe_yaw_arrived[:] = yaw_arrived
        if fixture == "anchor":
            self._a2_pull_v5_probe_anchor_pass[:] = (
                self._a2_pull_v5_probe_sequence_complete
                & waypoint_arrived
                & yaw_arrived
                & (phase_index == len(sequence_phases) - 1)
            )
        self._a2_pull_v5_probe_solvable |= solvable
        return applied, solvable

    def _get_a2_pull_v5_characterization_contract(self) -> dict[str, object]:
        """Resolve the preregistered open-field characterization cell contract."""

        if not self._a2_pull_v5_characterization_enabled:
            raise RuntimeError("HOMIE characterization is not enabled for this evaluator.")
        if not self._is_a2_pull_v5():
            raise RuntimeError("HOMIE characterization requires the v5 plan guard.")
        characterization_plan_id = self.config.get("a2_pull_v5_characterization_plan_id")
        if characterization_plan_id != self._A2_PULL_V5_CHARACTERIZATION_PLAN_ID:
            raise RuntimeError(
                "HOMIE characterization requires characterization_plan_id="
                f"{self._A2_PULL_V5_CHARACTERIZATION_PLAN_ID!r}; "
                f"got {characterization_plan_id!r}."
            )
        fixture = self.config.get("a2_pull_v5_characterization_fixture")
        if fixture != "open_field":
            raise RuntimeError(
                "HOMIE characterization fixture must be exactly 'open_field'; "
                f"got {fixture!r}."
            )
        cell_id = self.config.get("a2_pull_v5_characterization_cell_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise RuntimeError("HOMIE characterization requires a non-empty cell_id.")
        requested_u = self.config.get("a2_pull_v5_characterization_requested_u")
        if (
            isinstance(requested_u, bool)
            or not isinstance(requested_u, (int, float))
            or not math.isfinite(float(requested_u))
            or abs(float(requested_u)) > self._A2_PULL_V5_CHARACTERIZATION_RAW_YAW_LIMIT
            or abs(float(requested_u)) < 0.05
        ):
            raise RuntimeError(
                "HOMIE characterization requested_u must be finite and within the "
                f"registered raw range +/-{self._A2_PULL_V5_CHARACTERIZATION_RAW_YAW_LIMIT}; "
                f"got {requested_u!r}."
            )
        requested_u = float(requested_u)
        if not any(
            math.isclose(abs(requested_u), magnitude, rel_tol=0.0, abs_tol=1.0e-9)
            for magnitude in self._A2_PULL_V5_CHARACTERIZATION_YAW_MAGNITUDES
        ):
            raise RuntimeError(
                "HOMIE characterization requested_u is outside the preregistered grid; "
                f"got {requested_u!r}."
            )
        duration_s = self.config.get("a2_pull_v5_characterization_duration_s")
        if (
            isinstance(duration_s, bool)
            or not isinstance(duration_s, (int, float))
            or not math.isfinite(float(duration_s))
            or not any(
                math.isclose(float(duration_s), value, rel_tol=0.0, abs_tol=1.0e-9)
                for value in self._A2_PULL_V5_CHARACTERIZATION_DURATIONS_S
            )
        ):
            raise RuntimeError(
                "HOMIE characterization duration_s must be one of "
                f"{self._A2_PULL_V5_CHARACTERIZATION_DURATIONS_S}; got {duration_s!r}."
            )
        duration_s = float(duration_s)
        hold_s = self.config.get("a2_pull_v5_characterization_hold_s", 2.0)
        if (
            isinstance(hold_s, bool)
            or not isinstance(hold_s, (int, float))
            or not math.isfinite(float(hold_s))
            or float(hold_s) < 2.0
        ):
            raise RuntimeError(
                "HOMIE characterization hold_s must be a finite duration >= 2.0s; "
                f"got {hold_s!r}."
            )
        hold_s = float(hold_s)
        primitive = self.config.get("a2_pull_v5_characterization_xy_primitive", "none")
        if primitive not in self._A2_PULL_V5_CHARACTERIZATION_PRIMITIVES:
            raise RuntimeError(
                "HOMIE characterization XY primitive is not registered; "
                f"got {primitive!r}."
            )
        if primitive != "none" and not any(
            math.isclose(abs(requested_u), magnitude, rel_tol=0.0, abs_tol=1.0e-9)
            for magnitude in (0.2, 0.8)
        ):
            raise RuntimeError(
                "HOMIE characterization coupling cells only permit |u| in {0.2, 0.8}; "
                f"got u={requested_u!r}, primitive={primitive!r}."
            )
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError(f"HOMIE characterization requires finite positive dt; got {dt!r}.")
        command_steps = max(1, math.ceil(duration_s / dt))
        hold_steps = max(1, math.ceil(hold_s / dt))
        window_steps = command_steps + hold_steps
        return {
            "schema": self._A2_PULL_V5_CHARACTERIZATION_TRACE_SCHEMA,
            "record_class": "interface_characterization",
            "fixture": fixture,
            "cell_id": cell_id,
            "requested_u": requested_u,
            "duration_s": duration_s,
            "hold_s": hold_s,
            "command_steps": command_steps,
            "hold_steps": hold_steps,
            "window_steps": window_steps,
            "xy_primitive": primitive,
            "dt": dt,
            "num_envs": self.num_envs,
            "plan_id": characterization_plan_id,
        }

    def get_a2_pull_v5_characterization_contract(self) -> dict[str, object]:
        """Return the evaluator-facing characterization schema and timing contract."""

        return dict(self._get_a2_pull_v5_characterization_contract())

    def apply_a2_pull_v5_characterization_command(
        self,
        policy_action: torch.Tensor,
        first_episode_active_mask: torch.Tensor,
        episode_indices: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Write the open-loop yaw command at the final high-level action mapping."""

        contract = self._get_a2_pull_v5_characterization_contract()
        expected_action_shape = (self.num_envs, 12)
        if (
            not torch.is_tensor(policy_action)
            or tuple(policy_action.shape) != expected_action_shape
            or not policy_action.is_floating_point()
            or policy_action.device != torch.device(self.device)
            or not torch.all(torch.isfinite(policy_action))
        ):
            raise RuntimeError(
                "HOMIE characterization requires a finite device-local high-level action "
                f"shape {expected_action_shape}."
            )
        for name, value in (
            ("first_episode_active_mask", first_episode_active_mask),
            ("episode_indices", episode_indices),
        ):
            expected_dtype = torch.bool if name == "first_episode_active_mask" else torch.long
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != (self.num_envs,)
                or value.dtype != expected_dtype
                or value.device != policy_action.device
            ):
                raise RuntimeError(
                    f"HOMIE characterization {name} requires shape ({self.num_envs},) "
                    f"with dtype {expected_dtype} on {policy_action.device}."
                )
        if not self._use_a2_base:
            raise RuntimeError("HOMIE characterization requires the A2_Base high-level action path.")

        robot_data = self.simulator.scene.articulations["robot"].data
        root_pos = robot_data.root_pos_w
        root_quat_w = robot_data.root_quat_w
        if (
            tuple(root_pos.shape) != (self.num_envs, 3)
            or tuple(root_quat_w.shape) != (self.num_envs, 4)
            or root_pos.device != policy_action.device
            or root_quat_w.device != policy_action.device
            or root_quat_w.dtype != policy_action.dtype
            or not torch.all(torch.isfinite(root_pos))
            or not torch.all(torch.isfinite(root_quat_w))
        ):
            raise RuntimeError(
                "HOMIE characterization requires finite WXYZ robot root tensors on the action device."
            )
        _, _, root_yaw = euler_xyz_from_quat(root_quat_w)
        episode_step = self.episode_length_buf.to(dtype=torch.long)
        command_active = first_episode_active_mask & (
            episode_step < int(contract["command_steps"])
        )
        window_active = first_episode_active_mask & (
            episode_step < int(contract["window_steps"])
        )
        phase_u = torch.where(
            command_active,
            torch.full_like(episode_step, float(contract["requested_u"]), dtype=policy_action.dtype),
            torch.zeros_like(episode_step, dtype=policy_action.dtype),
        )
        raw_base = torch.zeros(
            self.num_envs, 5, dtype=policy_action.dtype, device=policy_action.device
        )
        primitive = str(contract["xy_primitive"])
        if primitive != "none":
            primitive_xy = torch.tensor(
                self._A2_PULL_V5_PROBE_PRIMITIVES[primitive][:2],
                dtype=policy_action.dtype,
                device=policy_action.device,
            )
            initialize_target = command_active & ~self._a2_pull_v5_characterization_xy_target_initialized
            if torch.any(initialize_target):
                self._a2_pull_v5_characterization_xy_target[initialize_target] = (
                    root_pos[initialize_target, :2] + primitive_xy
                )
                self._a2_pull_v5_characterization_xy_target_initialized[initialize_target] = True
            waypoint_target = torch.where(
                command_active[:, None],
                self._a2_pull_v5_characterization_xy_target,
                root_pos[:, :2],
            )
            waypoint_error = waypoint_target - root_pos[:, :2]
            _, _, _, raw_base = a2_hold_base_relief_command(
                waypoint_error,
                root_quat_w,
                command_active,
                physical_speed_mps=0.30,
                base_command_scale=self._a2_base_command_scale,
                min_solvable_horizontal_error_m=1.0e-3,
            )
        raw_base = torch.where(window_active[:, None], raw_base, torch.zeros_like(raw_base))
        raw_base[:, 2] = phase_u
        applied = policy_action.clone()
        applied[:, :5] = raw_base
        # This is deliberately a direct raw high-level write.  No waypoint/yaw
        # error, sign, or closed-loop assignment is used in characterization.

        self._a2_pull_v5_characterization_pending[:] = window_active
        self._a2_pull_v5_characterization_active[:] = window_active
        self._a2_pull_v5_characterization_episode_indices[:] = episode_indices
        self._a2_pull_v5_characterization_step[:] = episode_step
        self._a2_pull_v5_characterization_requested_u[:] = float(contract["requested_u"])
        self._a2_pull_v5_characterization_phase_u[:] = phase_u
        self._a2_pull_v5_characterization_pre_root_pos[:] = root_pos
        self._a2_pull_v5_characterization_pre_root_yaw[:] = root_yaw
        self._a2_pull_v5_characterization_raw_base[:] = raw_base
        for env_id in range(self.num_envs):
            if not window_active[env_id]:
                self._a2_pull_v5_characterization_phase[env_id] = "inactive"
            elif command_active[env_id]:
                self._a2_pull_v5_characterization_phase[env_id] = "command"
            else:
                self._a2_pull_v5_characterization_phase[env_id] = "zero_hold"
        return applied, window_active

    @override
    def _a2_base_pre_physics_command_callback(
        self,
        raw_base_action: torch.Tensor,
        physical_base_command: torch.Tensor,
        lower_body_action: torch.Tensor,
    ) -> None:
        super()._a2_base_pre_physics_command_callback(
            raw_base_action, physical_base_command, lower_body_action
        )
        if not self._a2_pull_v5_characterization_enabled:
            return
        active = self._a2_pull_v5_characterization_pending
        self._a2_pull_v5_characterization_physical_base[active] = physical_base_command[active]

    def _finalize_a2_pull_v5_characterization_step(self) -> None:
        if not self._a2_pull_v5_characterization_enabled:
            return
        pending = self._a2_pull_v5_characterization_pending
        if not torch.any(pending):
            return
        robot_data = self.simulator.scene.articulations["robot"].data
        post_root_pos = robot_data.root_pos_w
        post_root_quat_w = robot_data.root_quat_w
        if (
            tuple(post_root_pos.shape) != (self.num_envs, 3)
            or tuple(post_root_quat_w.shape) != (self.num_envs, 4)
            or not torch.all(torch.isfinite(post_root_pos))
            or not torch.all(torch.isfinite(post_root_quat_w))
        ):
            raise RuntimeError("HOMIE characterization post-physics root tensors must be finite.")
        _, _, post_root_yaw = euler_xyz_from_quat(post_root_quat_w)
        dt = float(self.dt)
        for env_id in torch.where(pending)[0].tolist():
            pre_pos = self._a2_pull_v5_characterization_pre_root_pos[env_id]
            post_pos = post_root_pos[env_id]
            yaw_delta = wrap_to_pi(
                post_root_yaw[env_id] - self._a2_pull_v5_characterization_pre_root_yaw[env_id]
            )
            xy_delta = post_pos[:2] - pre_pos[:2]
            phase = self._a2_pull_v5_characterization_phase[env_id]
            row = {
                "record_class": "interface_characterization",
                "schema": self._A2_PULL_V5_CHARACTERIZATION_TRACE_SCHEMA,
                "cell_id": self.config["a2_pull_v5_characterization_cell_id"],
                "fixture": self.config["a2_pull_v5_characterization_fixture"],
                "env_id": int(env_id),
                "episode_index": int(self._a2_pull_v5_characterization_episode_indices[env_id].item()),
                "episode_id": (
                    f"{self.config['a2_pull_v5_characterization_cell_id']}:env{env_id}:"
                    f"episode{int(self._a2_pull_v5_characterization_episode_indices[env_id].item())}"
                ),
                "step_index": int(self._a2_pull_v5_characterization_step[env_id].item()),
                "command_phase": phase == "command",
                "zero_hold_phase": phase == "zero_hold",
                "phase": phase,
                "requested_u": float(self._a2_pull_v5_characterization_phase_u[env_id].item()),
                "cell_requested_u": float(self._a2_pull_v5_characterization_requested_u[env_id].item()),
                "xy_primitive": self.config.get(
                    "a2_pull_v5_characterization_xy_primitive", "none"
                ),
                "applied_raw_base_slice": self._a2_pull_v5_characterization_raw_base[
                    env_id
                ].detach().cpu().tolist(),
                "scaled_clipped_physical_base_command": self._a2_pull_v5_characterization_physical_base[
                    env_id
                ].detach().cpu().tolist(),
                "realized_world_yaw_pre": float(
                    self._a2_pull_v5_characterization_pre_root_yaw[env_id].item()
                ),
                "realized_world_yaw_post": float(post_root_yaw[env_id].item()),
                "yaw_delta_rad": float(yaw_delta.item()),
                "yaw_velocity_rad_s": float(yaw_delta.item() / dt),
                "root_pos_pre_world": pre_pos.detach().cpu().tolist(),
                "root_pos_post_world": post_pos.detach().cpu().tolist(),
                "root_motion_xy_world": xy_delta.detach().cpu().tolist(),
                "root_motion_m": float(torch.linalg.norm(xy_delta).item()),
                "control_dt": dt,
            }
            self._a2_pull_v5_characterization_trace_rows.append(row)
        self._a2_pull_v5_characterization_pending[:] = False

    def consume_a2_pull_v5_characterization_trace_rows(self) -> list[dict[str, object]]:
        """Transfer evaluator rows without writing any artifact from the environment."""

        if not self._a2_pull_v5_characterization_enabled:
            raise RuntimeError("HOMIE characterization is not enabled for this evaluator.")
        rows = list(self._a2_pull_v5_characterization_trace_rows)
        self._a2_pull_v5_characterization_trace_rows.clear()
        return rows

    @override
    def _reset_robot_states_callback(self, env_ids, target_states=None):
        super()._reset_robot_states_callback(env_ids, target_states)
        if not self._a2_pull_v5_characterization_enabled:
            return
        root_state = self.target_robot_root_states[env_ids].clone()
        roll, pitch, _ = euler_xyz_from_quat(root_state[:, 3:7])
        root_state[:, 3:7] = quat_from_euler_xyz(
            roll, pitch, torch.full_like(roll, math.pi)
        )
        root_state[:, 7:13] = 0.0
        self.target_robot_root_states[env_ids] = root_state

    @staticmethod
    def _pull_v5_repo_path(raw_path: str, label: str) -> Path:
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
            raise RuntimeError(f"Pull-v5 {label} must be a non-empty repository-relative path.")
        root = Path(__file__).resolve().parents[4]
        path = (root / raw_path).resolve()
        if not path.is_relative_to(root):
            raise RuntimeError(f"Pull-v5 {label} escapes the repository: {raw_path!r}.")
        return path

    def _load_a2_pull_v5_state_bank(self) -> None:
        enabled = self.config["a2_pull_v5_stage4_bank_injection_enabled"]
        if not isinstance(enabled, bool):
            raise RuntimeError("Pull-v5 stage4 bank injection must be an explicit bool.")
        if enabled is False:
            return
        self._load_a2_pull_v5_bank_payload(eval_mode=False)

    def _load_a2_pull_v5_eval_state_bank(self) -> None:
        """Load canonical evaluation rows without enabling training injection."""

        enabled = self.config["a2_pull_v5_stage4_bank_injection_enabled"]
        if enabled is not False:
            raise RuntimeError("Canonical evaluation bank provider requires injection=false.")
        reset_source = self.config.get("a2_pull_v5_reset_source")
        if reset_source not in {
            "bank_natural_e5",
            "bank_natural_e5_plus",
            "bank_constructed",
            "bank_natural_e5_override",
        }:
            raise RuntimeError(
                "Canonical evaluation requires reset_source bank_natural_e5, "
                f"bank_natural_e5_plus, bank_constructed, or bank_natural_e5_override; got {reset_source!r}."
            )
        self._load_a2_pull_v5_bank_payload(eval_mode=True)

    @staticmethod
    def _pull_v5_metadata_sequence(payload: Mapping[str, object], key: str, count: int) -> list[object]:
        value = payload.get(key)
        if not isinstance(value, (list, tuple)) or len(value) != count:
            raise RuntimeError(f"Pull-v5 state bank metadata {key!r} must have one entry per row.")
        return list(value)

    def _select_a2_pull_v5_eval_bank_indices(
        self,
        provenance: list[str],
        closer_buckets: list[str],
    ) -> list[int]:
        requested_bucket = self.config.get("a2_pull_v5_eval_closer_bucket", "all")
        if requested_bucket != "all" and requested_bucket not in A2_PULL_V5_CLOSER_BUCKETS:
            raise RuntimeError(
                "Pull-v5 eval closer bucket must be 'all' or one of "
                f"{A2_PULL_V5_CLOSER_BUCKETS!r}; got {requested_bucket!r}."
            )
        count = self.config.get("a2_pull_v5_eval_state_count", 16)
        if isinstance(count, bool) or not isinstance(count, int) or count != 16:
            raise RuntimeError("Pull-v5 canonical evaluation requires exactly 16 bank rows.")
        candidates = [
            index
            for index, bucket in enumerate(closer_buckets)
            if requested_bucket == "all" or bucket == requested_bucket
        ]
        if len(candidates) < count:
            raise RuntimeError(
                f"Pull-v5 canonical evaluation requires 16 rows for bucket {requested_bucket!r}; "
                f"got {len(candidates)}."
            )
        by_group: dict[tuple[str, str], list[int]] = {}
        for index in candidates:
            by_group.setdefault((provenance[index], closer_buckets[index]), []).append(index)
        selected: list[int] = []
        group_order = tuple(sorted(by_group))
        while len(selected) < count:
            progressed = False
            for group in group_order:
                rows = by_group[group]
                if rows:
                    selected.append(rows.pop(0))
                    progressed = True
                    if len(selected) == count:
                        break
            if not progressed:
                raise RuntimeError("Pull-v5 canonical evaluation bank selection exhausted rows.")
        return selected

    @staticmethod
    def _select_a2_pull_v5_training_bank_indices(
        provenance: list[str], closer_buckets: list[str], count: int
    ) -> list[int]:
        if count <= 0:
            raise RuntimeError("Pull-v5 training bank selection requires a positive count.")
        groups: dict[tuple[str, str], list[int]] = {}
        for index, key in enumerate(zip(provenance, closer_buckets)):
            groups.setdefault(key, []).append(index)
        selected: list[int] = []
        for rows in groups.values():
            rows.sort()
        while len(selected) < count:
            progressed = False
            for key in sorted(groups):
                rows = groups[key]
                if rows:
                    selected.append(rows.pop(0))
                    progressed = True
                    if len(selected) == count:
                        break
            if not progressed:
                raise RuntimeError("Pull-v5 training bank selection exhausted rows.")
        return selected

    def _load_a2_pull_v5_bank_payload(self, *, eval_mode: bool) -> None:
        bank_path = self._pull_v5_repo_path(
            self.config["a2_pull_v5_state_bank_path"], "state bank path"
        )
        if not bank_path.is_file():
            raise FileNotFoundError(f"Pull-v5 state bank is required before v5 construction: {bank_path}")
        payload = torch.load(bank_path, map_location=self.device, weights_only=False)
        if not isinstance(payload, Mapping) or payload.get("schema") != A2_PULL_V5_STATE_BANK_SCHEMA:
            raise RuntimeError(f"Pull-v5 state bank schema must be {A2_PULL_V5_STATE_BANK_SCHEMA}.")
        required = (
            "robot_root_state",
            "robot_dof_pos",
            "robot_dof_vel",
            "door_root_state",
            "door_dof_pos",
            "door_dof_vel",
            "source_env_origin",
            "provenance",
            "buffers",
            "hinge_drive_max_force_nm",
            "closer_bucket",
            "capture_tier",
            "capture_delay_steps",
            "settle_valid",
            "settle_steps",
            "source_row",
        )
        missing = [name for name in required if name not in payload]
        if missing:
            raise RuntimeError(f"Pull-v5 state bank is missing required fields: {missing}")
        bank_size = len(payload["provenance"])
        minimum = int(self.config["a2_pull_v5_state_bank_min_samples"])
        if bank_size < minimum:
            raise RuntimeError(f"Pull-v5 state bank has {bank_size} samples; minimum is {minimum}.")
        if bank_size < 1 or not isinstance(payload["provenance"], (list, tuple)):
            raise RuntimeError("Pull-v5 state bank provenance must be a non-empty sequence.")
        provenance = [str(item) for item in payload["provenance"]]
        if provenance[0] != "bank_natural_e5":
            raise RuntimeError("Pull-v5 state bank must prioritize source A bank_natural_e5 entries first.")
        if any(item not in {"bank_natural_e5", "bank_natural_e5_plus", "bank_constructed"} for item in provenance):
            raise RuntimeError(
                "Pull-v5 state bank provenance must use only bank_natural_e5, "
                "bank_natural_e5_plus, or bank_constructed."
            )
        force_values = self._pull_v5_metadata_sequence(payload, "hinge_drive_max_force_nm", bank_size)
        bucket_values = [str(item) for item in self._pull_v5_metadata_sequence(payload, "closer_bucket", bank_size)]
        capture_tiers = [str(item) for item in self._pull_v5_metadata_sequence(payload, "capture_tier", bank_size)]
        capture_delay_steps = self._pull_v5_metadata_sequence(payload, "capture_delay_steps", bank_size)
        settle_valid = self._pull_v5_metadata_sequence(payload, "settle_valid", bank_size)
        settle_steps = self._pull_v5_metadata_sequence(payload, "settle_steps", bank_size)
        source_rows = self._pull_v5_metadata_sequence(payload, "source_row", bank_size)
        if any(bucket not in A2_PULL_V5_CLOSER_BUCKETS for bucket in bucket_values):
            raise RuntimeError("Pull-v5 state bank closer_bucket metadata contains an unsupported bucket.")
        if any(tier not in {"e5", "e5_plus_2s", "e5_plus_4s", "constructed"} for tier in capture_tiers):
            raise RuntimeError("Pull-v5 state bank capture_tier metadata contains an unsupported tier.")
        for index, (source, tier) in enumerate(zip(provenance, capture_tiers)):
            expected_tiers = {
                "bank_natural_e5": {"e5"},
                "bank_natural_e5_plus": {"e5_plus_2s", "e5_plus_4s"},
                "bank_constructed": {"constructed"},
            }[source]
            if tier not in expected_tiers:
                raise RuntimeError(
                    f"Pull-v5 bank row {index} capture tier {tier!r} contradicts provenance {source!r}."
                )
        for index, (force, valid, steps, capture_delay, source_row) in enumerate(
            zip(force_values, settle_valid, settle_steps, capture_delay_steps, source_rows)
        ):
            if isinstance(force, bool) or not isinstance(force, (int, float)) or not math.isfinite(float(force)):
                raise RuntimeError(f"Pull-v5 bank closer force row {index} must be finite numeric.")
            if not isinstance(valid, bool) or not valid:
                raise RuntimeError(f"Pull-v5 bank row {index} is not settle-valid.")
            if isinstance(steps, bool) or not isinstance(steps, int) or steps < 50:
                raise RuntimeError(f"Pull-v5 bank settle_steps row {index} must be >=50.")
            if isinstance(capture_delay, bool) or not isinstance(capture_delay, int) or capture_delay < 0:
                raise RuntimeError(
                    f"Pull-v5 bank capture_delay_steps row {index} must be a non-negative integer."
                )
            if isinstance(source_row, bool) or not isinstance(source_row, int) or source_row < 0:
                raise RuntimeError(f"Pull-v5 bank source_row {index} must be a non-negative integer.")
        counts = Counter(provenance)
        allow_g8_pure_a = self.config["a2_pull_v5_state_bank_allow_g8_pure_a"]
        if not isinstance(allow_g8_pure_a, bool):
            raise RuntimeError("Pull-v5 G8 pure-Source-A allowance must be an explicit bool.")
        if counts["bank_natural_e5_plus"] < 8 and not allow_g8_pure_a:
            raise RuntimeError("Pull-v5 state bank does not satisfy G13 natural_e5_plus count.")
        if counts["bank_constructed"] < 16 and not allow_g8_pure_a:
            raise RuntimeError("Pull-v5 state bank does not satisfy G13 provenance counts.")
        if set(bucket_values) != set(A2_PULL_V5_CLOSER_BUCKETS):
            raise RuntimeError("Pull-v5 state bank must populate all closer buckets.")
        source_origin = payload["source_env_origin"]
        if (
            not torch.is_tensor(source_origin)
            or tuple(source_origin.shape) != (bank_size, 3)
            or source_origin.device != torch.device(self.device)
            or not torch.is_floating_point(source_origin)
            or not torch.all(torch.isfinite(source_origin))
        ):
            raise RuntimeError("Pull-v5 source_env_origin must have shape [bank, 3].")
        tensors: dict[str, torch.Tensor] = {}
        expected_shapes = {
            "robot_root_state": (bank_size, 13),
            "robot_dof_pos": (bank_size, self.simulator.scene.articulations["robot"].num_joints),
            "robot_dof_vel": (bank_size, self.simulator.scene.articulations["robot"].num_joints),
            "door_root_state": (bank_size, 13),
            "door_dof_pos": (bank_size, self.simulator.scene.articulations["door"].num_joints),
            "door_dof_vel": (bank_size, self.simulator.scene.articulations["door"].num_joints),
        }
        for name, shape in expected_shapes.items():
            value = payload[name]
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != shape
                or value.device != torch.device(self.device)
                or not torch.all(torch.isfinite(value))
            ):
                raise RuntimeError(
                    f"Pull-v5 bank {name} must match shape/device {shape}/{self.device}; "
                    f"got {getattr(value, 'shape', None)}/{getattr(value, 'device', None)}."
                )
            tensors[name] = value
        buffers = payload["buffers"]
        if not isinstance(buffers, Mapping):
            raise RuntimeError("Pull-v5 state bank buffers must be a mapping keyed by every registered buffer.")
        for name, state_case in self.staged_reset_buf.items():
            if state_case["type"] != "buffer":
                continue
            if name not in buffers:
                raise RuntimeError(f"Pull-v5 state bank is missing registered buffer {name!r}.")
            value = buffers[name]
            expected = (bank_size, *state_case["data"].shape[3:])
            if (
                not torch.is_tensor(value)
                or tuple(value.shape) != expected
                or value.dtype != state_case["data"].dtype
                or value.device != torch.device(self.device)
            ):
                raise RuntimeError(
                    f"Pull-v5 bank buffer {name} must match {expected}/{state_case['data'].dtype}; "
                    f"got {getattr(value, 'shape', None)}/{getattr(value, 'dtype', None)}."
                )
            tensors[f"buffer:{name}"] = value
        if eval_mode:
            selected_indices = self._select_a2_pull_v5_eval_bank_indices(provenance, bucket_values)
        else:
            selected_indices = self._select_a2_pull_v5_training_bank_indices(
                provenance,
                bucket_values,
                min(int(self.staged_reset_max_samples_per_stage), bank_size),
            )
        self._a2_pull_v5_bank = {**tensors, "source_env_origin": source_origin}
        self._a2_pull_v5_bank_metadata = {
            "hinge_drive_max_force_nm": [float(value) for value in force_values],
            "closer_bucket": bucket_values,
            "capture_tier": capture_tiers,
            "capture_delay_steps": [int(value) for value in capture_delay_steps],
            "settle_valid": settle_valid,
            "settle_steps": settle_steps,
            "source_row": source_rows,
        }
        self._a2_pull_v5_bank_slot_indices = selected_indices
        self._a2_pull_v5_bank_slot_sources = [provenance[index] for index in selected_indices]
        self._a2_pull_v5_bank_eval_indices = selected_indices if eval_mode else []
        self._inject_a2_pull_v5_stage4_bank()
        self._a2_pull_v5_bank_loaded = True

    def _inject_a2_pull_v5_stage4_bank(self) -> None:
        bank = getattr(self, "_a2_pull_v5_bank", None)
        if bank is None:
            raise RuntimeError("Pull-v5 stage4 bank injection requires a loaded state bank.")
        capacity = int(self.staged_reset_max_samples_per_stage)
        bank_size = len(self._a2_pull_v5_bank_slot_indices)
        eval_selected_count = len(self._a2_pull_v5_bank_eval_indices)
        if eval_selected_count:
            if eval_selected_count != 16:
                raise RuntimeError(
                    "Pull-v5 canonical evaluation injection requires exactly 16 selected rows; "
                    f"got {eval_selected_count}."
                )
            if bank_size != eval_selected_count:
                raise RuntimeError(
                    "Pull-v5 canonical evaluation bank slot count must match selected rows; "
                    f"got {bank_size} for {eval_selected_count} selected rows."
                )
            if capacity < eval_selected_count:
                raise RuntimeError(
                    "Pull-v5 canonical evaluation staged-reset capacity is smaller than the "
                    f"selected row count: capacity={capacity}, selected={eval_selected_count}."
                )
            count = eval_selected_count
        else:
            count = min(capacity, bank_size)
            if count < int(self.config["a2_pull_v5_state_bank_min_samples"]):
                raise RuntimeError("Pull-v5 staged-reset capacity is smaller than the required bank minimum.")
        stage = self.STAGE_SWING
        source_origin = bank["source_env_origin"]
        for env_id in range(self.num_envs):
            target_origin = self.env_origins[env_id]
            for slot in range(count):
                bank_index = self._a2_pull_v5_bank_slot_indices[slot]
                robot_root = bank["robot_root_state"][bank_index].clone()
                door_root = bank["door_root_state"][bank_index].clone()
                robot_root[:3] = robot_root[:3] - source_origin[bank_index] + target_origin
                door_root[:3] = door_root[:3] - source_origin[bank_index] + target_origin
                robot_case = self.staged_reset_buf["robot"]
                robot_case["root_state"][stage, slot, env_id] = robot_root
                robot_case["dof_state"][stage, slot, env_id, :, 0] = bank["robot_dof_pos"][bank_index]
                robot_case["dof_state"][stage, slot, env_id, :, 1] = bank["robot_dof_vel"][bank_index]
                door_case = self.staged_reset_buf["door"]
                door_case["root_state"][stage, slot, env_id] = door_root
                door_case["dof_state"][stage, slot, env_id, :, 0] = bank["door_dof_pos"][bank_index]
                door_case["dof_state"][stage, slot, env_id, :, 1] = bank["door_dof_vel"][bank_index]
                for name, state_case in self.staged_reset_buf.items():
                    if state_case["type"] == "buffer":
                        value = bank[f"buffer:{name}"][bank_index].clone()
                        origin_delta = target_origin - source_origin[bank_index]
                        if name == "a2_pull_prev_base_pos_xy":
                            if tuple(value.shape) != (2,) or not value.is_floating_point():
                                raise RuntimeError(
                                    "Pull-v5 a2_pull_prev_base_pos_xy bank payload must be finite floating [2]."
                                )
                            value = value + origin_delta[:2]
                        elif name in {
                            "a2_pull_proof_start_root_x",
                            "a2_pull_proof_last_root_x",
                            "a2_pull_capture_root_x",
                        }:
                            if tuple(value.shape) != () or not value.is_floating_point():
                                raise RuntimeError(
                                    f"Pull-v5 {name} bank payload must be a finite floating scalar."
                                )
                            value = value + origin_delta[0]
                        state_case["data"][stage, slot, env_id] = value
        self.staged_reset_num_samples[stage, :] = count
        ratio = float(self.config["a2_pull_v5_stage4_bank_injection_ratio"])
        if not 0.0 <= ratio <= 1.0:
            raise RuntimeError(f"Pull-v5 Stage-4 bank ratio must be in [0,1]; got {ratio}.")
        if self.config.get("a2_pull_v5_reset_source", "natural") != "natural" and not self.config.get(
            "a2_pull_v5_stage4_bank_injection_enabled", False
        ):
            ratio = 1.0
        # Training uses [1-p, 0, 0, 0, p, 0]; canonical evaluation uses bank-only
        # Stage-4 rows while the training injection flag remains false.
        self.staged_reset_ratios.zero_()
        self.staged_reset_ratios[0] = 1.0 - ratio
        self.staged_reset_ratios[stage] = ratio

    def export_a2_pull_v5_state_bank(
        self,
        output_path: str,
        *,
        provenance: str,
        settle_valid: bool,
        settle_steps: int,
        capture_tier: str | None = None,
        source_row: int | None = None,
    ) -> dict[str, object]:
        """Export stage-4 snapshots through the existing high-level state writers.

        The source runner calls this after its settle window; no USD prim edits
        or synthetic state construction are permitted here.  ``provenance`` is
        deliberately explicit so source-A and source-B payloads cannot be
        silently mixed.
        """

        if provenance not in {"bank_natural_e5", "bank_natural_e5_plus", "bank_constructed"}:
            raise RuntimeError(f"Pull-v5 bank export provenance is unsupported: {provenance!r}.")
        if not isinstance(settle_valid, bool) or not settle_valid:
            raise RuntimeError("Pull-v5 bank export requires an explicitly valid settle window.")
        if isinstance(settle_steps, bool) or not isinstance(settle_steps, int) or settle_steps < 50:
            raise RuntimeError("Pull-v5 bank export requires settle_steps >= 50.")
        if capture_tier is None:
            capture_tier = {
                "bank_natural_e5": "e5",
                "bank_natural_e5_plus": "e5_plus_2s",
                "bank_constructed": "constructed",
            }[provenance]
        if capture_tier not in {"e5", "e5_plus_2s", "e5_plus_4s", "constructed"}:
            raise RuntimeError(f"Pull-v5 bank capture tier is unsupported: {capture_tier!r}.")
        if source_row is None:
            source_row = int(self.config.get("a2_pull_v5_bank_capture_source_row", 0))
        if isinstance(source_row, bool) or not isinstance(source_row, int) or source_row < 0:
            raise RuntimeError("Pull-v5 bank export source_row must be a non-negative integer.")
        if not self.enable_staged_reset or self.staged_reset_num_samples is None:
            raise RuntimeError("Pull-v5 bank export requires staged reset snapshots.")
        stage = self.STAGE_SWING
        counts = self.staged_reset_num_samples[stage]
        if torch.any(counts < 0) or torch.any(counts > self.staged_reset_max_samples_per_stage):
            raise RuntimeError("Pull-v5 bank export encountered invalid per-environment snapshot counts.")
        valid_env_ids = torch.where(counts > 0)[0]
        if len(valid_env_ids) == 0:
            raise RuntimeError("Pull-v5 bank export has no Stage-4 snapshots after settle.")
        robot_case = self.staged_reset_buf.get("robot")
        door_case = self.staged_reset_buf.get("door")
        if not isinstance(robot_case, Mapping) or not isinstance(door_case, Mapping):
            raise RuntimeError("Pull-v5 bank export requires tracked robot and door states.")
        robot_root_chunks: list[torch.Tensor] = []
        robot_dof_pos_chunks: list[torch.Tensor] = []
        robot_dof_vel_chunks: list[torch.Tensor] = []
        door_root_chunks: list[torch.Tensor] = []
        door_dof_pos_chunks: list[torch.Tensor] = []
        door_dof_vel_chunks: list[torch.Tensor] = []
        origin_chunks: list[torch.Tensor] = []
        force_chunks: list[torch.Tensor] = []
        rows = 0
        for env_id in valid_env_ids.tolist():
            count = int(counts[env_id].item())
            robot_root_chunks.append(robot_case["root_state"][stage, :count, env_id])
            robot_dof_pos_chunks.append(robot_case["dof_state"][stage, :count, env_id, :, 0])
            robot_dof_vel_chunks.append(robot_case["dof_state"][stage, :count, env_id, :, 1])
            door_root_chunks.append(door_case["root_state"][stage, :count, env_id])
            door_dof_pos_chunks.append(door_case["dof_state"][stage, :count, env_id, :, 0])
            door_dof_vel_chunks.append(door_case["dof_state"][stage, :count, env_id, :, 1])
            origin_chunks.append(self.env_origins[env_id].expand(count, 3))
            force_chunks.append(self.door_hinge_drive_max_force[env_id].expand(count))
            rows += count
        robot_root = torch.cat(robot_root_chunks, dim=0)
        robot_dof_pos = torch.cat(robot_dof_pos_chunks, dim=0)
        robot_dof_vel = torch.cat(robot_dof_vel_chunks, dim=0)
        door_root = torch.cat(door_root_chunks, dim=0)
        door_dof_pos = torch.cat(door_dof_pos_chunks, dim=0)
        door_dof_vel = torch.cat(door_dof_vel_chunks, dim=0)
        source_origins = torch.cat(origin_chunks, dim=0)
        force_values = torch.cat(force_chunks, dim=0)
        delay_seconds = {
            "e5": 0.0,
            "e5_plus_2s": 2.0,
            "e5_plus_4s": 4.0,
            "constructed": 0.0,
        }[capture_tier]
        capture_delay_steps = int(round(delay_seconds / float(self.dt))) if delay_seconds else 0
        payload: dict[str, object] = {
            "schema": A2_PULL_V5_STATE_BANK_SOURCE_SCHEMA,
            "robot_root_state": robot_root.detach().cpu(),
            "robot_dof_pos": robot_dof_pos.detach().cpu(),
            "robot_dof_vel": robot_dof_vel.detach().cpu(),
            "door_root_state": door_root.detach().cpu(),
            "door_dof_pos": door_dof_pos.detach().cpu(),
            "door_dof_vel": door_dof_vel.detach().cpu(),
            "source_env_origin": source_origins.detach().cpu(),
            "provenance": [provenance] * rows,
            "settle_valid": torch.ones(rows, dtype=torch.bool),
            "settle_steps": torch.full((rows,), settle_steps, dtype=torch.long),
            "capture_delay_steps": torch.full((rows,), capture_delay_steps, dtype=torch.long),
            "hinge_drive_max_force_nm": force_values.detach().cpu(),
            "closer_bucket": [],
            "capture_tier": [capture_tier] * rows,
            "source_row": [source_row] * rows,
            "buffers": {},
        }
        force_values = payload["hinge_drive_max_force_nm"]
        if not torch.is_tensor(force_values) or tuple(force_values.shape) != (rows,):
            raise RuntimeError("Pull-v5 bank export closer-force metadata shape mismatch.")
        closer_buckets: list[str] = []
        for force in force_values.tolist():
            value = float(force)
            if 2.5 <= value < 5.0:
                closer_buckets.append("2.5-5")
            elif 5.0 <= value < 9.0:
                closer_buckets.append("5-9")
            elif 9.0 <= value <= 12.0:
                closer_buckets.append("9-12")
            else:
                raise RuntimeError(f"Pull-v5 closer force outside planned buckets: {value!r}")
        payload["closer_bucket"] = closer_buckets
        buffers = payload["buffers"]
        assert isinstance(buffers, dict)
        for name, state_case in self.staged_reset_buf.items():
            if state_case["type"] != "buffer":
                continue
            chunks = [
                state_case["data"][stage, : int(counts[env_id].item()), env_id]
                for env_id in valid_env_ids.tolist()
            ]
            buffers[name] = torch.cat(chunks, dim=0).detach().cpu()
        path = self._pull_v5_repo_path(output_path, "bank capture path")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Pull-v5 bank capture refuses to overwrite {path}.")
        torch.save(payload, path)
        return {"schema": payload["schema"], "status": "PASS", "samples": rows, "output": str(path)}

    def capture_a2_pull_v5_source_snapshot(self, output_path: str) -> dict[str, object]:
        """Capture one configured E5/holding/constructed source tier.

        Source-A replay uses the same 86-buffer payload for E5, E5+2 s, and
        E5+4 s windows; only provenance/capture metadata changes.
        """

        tier = self.config.get("a2_pull_v5_bank_capture_tier", "e5")
        provenance = {
            "e5": "bank_natural_e5",
            "e5_plus_2s": "bank_natural_e5_plus",
            "e5_plus_4s": "bank_natural_e5_plus",
            "constructed": "bank_constructed",
        }.get(tier)
        if provenance is None:
            raise RuntimeError(f"Pull-v5 bank capture tier is unsupported: {tier!r}.")
        return self.export_a2_pull_v5_state_bank(
            output_path,
            provenance=provenance,
            settle_valid=True,
            settle_steps=int(self.config.get("a2_pull_v5_bank_capture_settle_steps", 50)),
            capture_tier=tier,
            source_row=int(self.config.get("a2_pull_v5_bank_capture_source_row", 0)),
        )

    def update_a2_pull_v5_capture_window(self) -> None:
        """Capture natural Source-A rows at E5 or the configured delayed hold tier."""

        if not self._is_a2_pull_v5():
            raise RuntimeError("Pull-v5 source capture requires the v5 plan guard.")
        if self.config.get("a2_pull_v5_bank_capture_provenance") == "bank_constructed":
            raise RuntimeError("Natural capture-window updates cannot run for Source-B.")
        if self.config.get("a2_pull_v5_bank_capture_only") is not True:
            raise RuntimeError("Pull-v5 capture-window updates require capture_only=true.")
        tier = self.config.get("a2_pull_v5_bank_capture_tier", "e5")
        delay_seconds = {
            "e5": 0.0,
            "e5_plus_2s": 2.0,
            "e5_plus_4s": 4.0,
        }.get(tier)
        if delay_seconds is None:
            raise RuntimeError(f"Pull-v5 natural capture tier is unsupported: {tier!r}.")
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError("Pull-v5 capture-window updates require a positive finite dt.")
        delay_steps = int(round(delay_seconds / dt)) if delay_seconds else 0
        e5 = self._a2_pull_event_reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
        new_e5 = e5 & ~self._a2_pull_v5_capture_e5_seen
        self._a2_pull_v5_capture_e5_seen |= e5
        self._a2_pull_v5_capture_pending[new_e5] = True
        self._a2_pull_v5_capture_target_step[new_e5] = (
            self.episode_length_buf[new_e5] + delay_steps
        )
        due = self._a2_pull_v5_capture_pending & (
            self.episode_length_buf >= self._a2_pull_v5_capture_target_step
        )
        due &= ~self._a2_pull_v5_capture_recorded
        if torch.any(due):
            if torch.any(self.stage_buf[due] != self.STAGE_SWING):
                raise RuntimeError("Pull-v5 Source-A capture reached its tier outside Stage-4 swing.")
            self._take_snapshot_of_buffered_states(due)
            self._a2_pull_v5_capture_pending[due] = False
            self._a2_pull_v5_capture_recorded[due] = True

    def construct_a2_pull_v5_source_b_states(self) -> None:
        """Capture Source-B states with direct IsaacLab articulation writers.

        This route intentionally bypasses staged-reset sampling.  It writes a
        world-frame robot/door template, settles the articulations, and only
        then snapshots valid rows.  ``staged_reset_ratios`` is never touched.
        """

        if not self._is_a2_pull_v5():
            raise RuntimeError("Source-B construction requires the v5 plan guard.")

        settle_steps = self.config.get("a2_pull_v5_bank_capture_settle_steps")
        if (
            isinstance(settle_steps, bool)
            or not isinstance(settle_steps, int)
            or settle_steps < 50
        ):
            raise RuntimeError(
                "Source-B construction requires a2_pull_v5_bank_capture_settle_steps >= 50."
            )

        if not self.enable_staged_reset or self.staged_reset_num_samples is None:
            raise RuntimeError("Source-B capture requires staged reset buffers for snapshot export.")
        if self.config.get("a2_pull_v5_bank_capture_only") is not True:
            raise RuntimeError("Source-B capture requires bank_capture_only=true.")
        env_ids = torch.arange(self.num_envs, device=self.device, dtype=torch.long)
        robot = self.simulator.scene.articulations["robot"]
        door = self.simulator.scene.articulations["door"]
        robot.reset(env_ids)
        door.reset(env_ids)

        # Build a local template, translate roots by each environment origin,
        # and zero every velocity before the high-level writes.
        robot_root = self.base_init_state.to(device=self.device).expand(self.num_envs, -1).clone()
        robot_root[:, 3:7] = xyzw_to_wxyz(robot_root[:, 3:7])
        robot_root[:, :3] += self.env_origins
        robot_root[:, 0] = self.env_origins[:, 0] + self._pull_direction.approach_side_x * 0.9
        robot_root[:, 1] = self.env_origins[:, 1]
        robot_root[:, 7:13] = 0.0
        robot.write_root_state_to_sim(robot_root, env_ids)

        robot_dof_pos = self.default_dof_pos.to(device=self.device).expand(self.num_envs, -1).clone()
        robot_dof_pos[:, self._upper_non_gripper_dof_idx] = self._get_a2_arm_default_dof_pos(env_ids)
        robot_dof_pos[:, self._a2_gripper_dof_indices] = self._a2_gripper_open_target
        robot_dof_vel = torch.zeros_like(robot_dof_pos)
        robot.write_joint_state_to_sim(robot_dof_pos, robot_dof_vel, env_ids=env_ids)

        door_root = door.data.default_root_state[env_ids].clone()
        door_root[:, :3] += self.env_origins
        door_root[:, 7:13] = 0.0
        door.write_root_state_to_sim(door_root, env_ids)
        door_joint_pos = torch.zeros(
            (self.num_envs, door.num_joints), device=self.device, dtype=door.data.joint_pos.dtype
        )
        door_joint_pos[:, 0] = torch.linspace(1.6, 2.1, self.num_envs, device=self.device)
        door_joint_vel = torch.zeros_like(door_joint_pos)
        door.write_joint_state_to_sim(door_joint_pos, door_joint_vel, env_ids=env_ids)
        robot.reset(env_ids)
        door.reset(env_ids)
        self._refresh_sim_tensors()
        self._reset_buffers_callback(env_ids, None)
        self.set_to_stage(env_ids, torch.full_like(env_ids, self.STAGE_SWING))
        self.staged_reset_num_samples[self.STAGE_SWING, :] = 0
        self.reset_buf[:] = 0
        self.need_to_refresh_envs[env_ids] = False

        gravity_x_limit = float(self.config.termination_scales.termination_gravity_x)
        gravity_y_limit = float(self.config.termination_scales.termination_gravity_y)
        minimum_base_height = float(self.config.termination_scales.termination_min_base_height)
        settle_valid_mask = torch.ones(self.num_envs, dtype=torch.bool, device=self.device)
        for _ in range(settle_steps):
            hold_action = self._action_backmap()
            expected_action_dim = self._a2_high_level_action_dim + self._a2_leg_action_dim
            if (
                not torch.is_tensor(hold_action)
                or tuple(hold_action.shape) != (self.num_envs, expected_action_dim)
                or hold_action.device != torch.device(self.device)
                or not hold_action.is_floating_point()
                or not torch.all(torch.isfinite(hold_action))
            ):
                shape = None if not torch.is_tensor(hold_action) else tuple(hold_action.shape)
                raise RuntimeError(
                    "Source-B settle requires a finite high-level A2 hold action with "
                    f"shape ({self.num_envs}, {expected_action_dim}); got {shape}."
                )
            desired_arm_action = hold_action[:, self._delta_action_indices].clone()
            hold_action[:, self._delta_action_indices] = (
                desired_arm_action - self._delta_actions
            ) / self._delta_action_scale
            self.step({"actions": hold_action})

            root_state = self.simulator.robot_root_states
            robot_dof_pos = self.simulator.dof_pos
            robot_dof_vel = self.simulator.dof_vel
            door_state = self.simulator.get_task_root_state("door")
            door_data = self.simulator.scene.articulations["door"].data
            door_dof_pos = door_data.joint_pos
            door_dof_vel = door_data.joint_vel
            finite_state = all(
                torch.all(torch.isfinite(value))
                for value in (
                    root_state,
                    robot_dof_pos,
                    robot_dof_vel,
                    door_state,
                    door_dof_pos,
                    door_dof_vel,
                )
            )
            root_height = root_state[:, 2] - self.ground_height
            root_speed = torch.linalg.norm(root_state[:, 7:10], dim=-1)
            root_ang_speed = torch.linalg.norm(root_state[:, 10:13], dim=-1)
            gravity = self.projected_gravity
            unstable = (
                torch.full((self.num_envs,), not finite_state, dtype=torch.bool, device=self.device)
                | (root_height < minimum_base_height)
                | (torch.abs(gravity[:, 0]) > gravity_x_limit)
                | (torch.abs(gravity[:, 1]) > gravity_y_limit)
                | (root_speed > 1.0)
                | (root_ang_speed > 1.0)
                | (self.reset_buf != 0)
            )
            clearance = self._get_a2_pull_minimum_panel_robot_clearance()
            frame_contact = self._get_door_frame_contact_force_per_env("Pull-v5 Source-B settle")
            unstable |= (clearance < 0.0) | (frame_contact > 0.0)
            settle_valid_mask &= ~unstable

        final_door_data = self.simulator.scene.articulations["door"].data
        final_hinge = final_door_data.joint_pos[:, 0]
        arm_default = self._get_a2_arm_default_dof_pos()
        arm_tolerance = self._get_required_positive_float_config(
            "a2_stage0_arm_default_max_deviation", "Pull-v5 Source-B final admission"
        )
        arm_near_default = torch.abs(
            self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx] - arm_default
        ).amax(dim=-1) <= arm_tolerance
        gripper_near_open = torch.abs(
            self.simulator.dof_pos[:, self._a2_gripper_dof_indices] - self._a2_gripper_open_target
        ).amax(dim=-1) <= arm_tolerance
        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "Pull-v5 Source-B final admission"
        )
        no_handle_contact = ~torch.any(contact_masks["contacting"], dim=-1)
        settle_valid_mask &= (
            (final_hinge >= 1.6)
            & (final_hinge <= 2.1)
            & (torch.abs(final_door_data.joint_vel) <= 0.05).all(dim=-1)
            & (torch.abs(self.simulator.dof_vel) <= 0.05).all(dim=-1)
            & (torch.linalg.norm(self.simulator.robot_root_states[:, 7:10], dim=-1) <= 0.05)
            & (torch.linalg.norm(self.simulator.robot_root_states[:, 10:13], dim=-1) <= 0.05)
            & arm_near_default
            & gripper_near_open
            & no_handle_contact
        )
        if not bool(torch.any(settle_valid_mask).item()):
            raise RuntimeError("Source-B settle rejected every constructed row.")
        self.staged_reset_num_samples[self.STAGE_SWING, :] = 0
        self._take_snapshot_of_buffered_states(settle_valid_mask)
        stage_counts = self.staged_reset_num_samples[self.STAGE_SWING, env_ids]
        if torch.any(stage_counts[settle_valid_mask] < 1):
            raise RuntimeError("Source-B settle did not produce a Stage-4 snapshot for every valid row.")
        self._a2_pull_v5_source_b_capture_frozen = True

    def export_a2_pull_v5_census(self, output_path: str, *, variant: str, seed: int) -> dict[str, object]:
        """Export staged-reset occupancy and state summaries for the census runner."""

        if variant not in {"v4_B", "v5"}:
            raise RuntimeError(f"Pull-v5 census variant is unsupported: {variant!r}.")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise RuntimeError("Pull-v5 census seed must be an integer.")
        if not self.enable_staged_reset or self.staged_reset_num_samples is None:
            raise RuntimeError("Pull-v5 census requires staged reset state snapshots.")
        stages: dict[str, object] = {}
        for stage in range(self.num_stages):
            count_by_env = self.staged_reset_num_samples[stage]
            sample_count = int(count_by_env.sum().item())
            source_counts: dict[str, int] = {"natural": sample_count}
            if variant == "v5" and stage == self.STAGE_SWING and self._a2_pull_v5_bank_slot_sources:
                source_counts = dict(Counter(self._a2_pull_v5_bank_slot_sources[: int(count_by_env.max().item())]))
            row: dict[str, object] = {
                "snapshot_count": sample_count,
                "reset_source_counts": source_counts,
                "hinge_rad": {},
                "root_state": {},
                "contact": {},
                "arm_state": {},
            }
            if sample_count:
                door_case = self.staged_reset_buf.get("door")
                robot_case = self.staged_reset_buf.get("robot")
                if not isinstance(door_case, Mapping) or not isinstance(robot_case, Mapping):
                    raise RuntimeError("Pull-v5 census requires tracked robot and door states.")
                hinge = door_case["dof_state"][stage, : int(count_by_env.max().item()), :, 0, 0]
                root = robot_case["root_state"][stage, : int(count_by_env.max().item()), :, :3]
                arm = robot_case["dof_state"][stage, : int(count_by_env.max().item()), :, :, 0]
                finite_hinge = hinge[torch.isfinite(hinge)]
                finite_root = root[torch.isfinite(root).all(dim=-1)]
                finite_arm = arm[torch.isfinite(arm).all(dim=-1)]
                if finite_hinge.numel() == 0 or finite_root.numel() == 0 or finite_arm.numel() == 0:
                    raise RuntimeError(f"Pull-v5 census stage {stage} has no finite state samples.")
                row["hinge_rad"] = {
                    "min": float(finite_hinge.min().item()),
                    "max": float(finite_hinge.max().item()),
                    "mean": float(finite_hinge.mean().item()),
                }
                row["root_state"] = {"mean_xyz": finite_root.mean(dim=0).detach().cpu().tolist()}
                row["arm_state"] = {"mean": finite_arm.mean(dim=0).detach().cpu().tolist()}
                contact_case = self.staged_reset_buf.get("a2_pull_prev_stable_contact")
                if isinstance(contact_case, Mapping):
                    contact = contact_case["data"][stage, : int(count_by_env.max().item())]
                    row["contact"] = {"stable_contact_count": int(contact.bool().sum().item())}
                else:
                    raise RuntimeError("Pull-v5 census requires tracked stable-contact snapshots.")
            stages[str(stage)] = row
        payload = {
            "schema": "a2_piper_pull_v5_census_v2",
            "variant": variant,
            "seed": seed,
            "stages": stages,
        }
        path = self._pull_v5_repo_path(output_path, "census output path")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Pull-v5 census refuses to overwrite {path}.")
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"schema": payload["schema"], "status": "PASS", "output": str(path), "stages": stages}

    @override
    def _filter_staged_reset_snapshot_mask(self, advance_mask: torch.Tensor) -> torch.Tensor:
        filtered = super()._filter_staged_reset_snapshot_mask(advance_mask)
        capture_only = self.config.get("a2_pull_v5_bank_capture_only", False)
        if not isinstance(capture_only, bool):
            raise RuntimeError("a2_pull_v5_bank_capture_only must be a boolean.")
        if self._is_a2_pull_v5() and capture_only:
            return torch.zeros_like(filtered)
        if (
            self._is_a2_pull_v5()
            and self.config["a2_pull_v5_snapshot_freeze_enabled"]
            and not capture_only
        ):
            filtered &= self.stage_buf != self.STAGE_SWING
        return filtered

    @override
    def _sample_reset_sample_indices(self, env_ids: torch.Tensor, selected_stages: torch.Tensor) -> torch.Tensor:
        selected = super()._sample_reset_sample_indices(env_ids, selected_stages)
        if self._is_a2_pull_v5():
            for env_id, stage, sample in zip(env_ids.tolist(), selected_stages.tolist(), selected.tolist()):
                if stage == self.STAGE_SWING:
                    if sample < 0 or sample >= len(self._a2_pull_v5_bank_slot_sources):
                        raise RuntimeError(
                            f"Pull-v5 canonical bank sample index is out of range: {sample}."
                        )
                    self._a2_pull_v5_pending_reset_source[env_id] = self._a2_pull_v5_bank_slot_sources[sample]
                else:
                    self._a2_pull_v5_pending_reset_source[env_id] = "natural"
        return selected

    @override
    def _reset_buffers_callback(self, env_ids, target_buf=None):
        result = super()._reset_buffers_callback(env_ids, target_buf)
        self._a2_pull_event_reached[env_ids] = False
        self._a2_pull_stable_unlatch_handle_ever[env_ids] = False
        self._a2_pull_stable_unlatch_latch_ever[env_ids] = False
        self._a2_pull_relock_handle_ever[env_ids] = False
        self._a2_pull_relock_latch_ever[env_ids] = False
        self._a2_pull_prev_handle_unlatched[env_ids] = False
        self._a2_pull_prev_latch_unlatched[env_ids] = False
        self._a2_pull_first_event_step[env_ids] = -1
        self._a2_pull_first_event_time_s[env_ids] = float("nan")
        self._a2_pull_capture_root_x[env_ids] = float("nan")
        self._a2_pull_capture_valid[env_ids] = False
        self._a2_pull_max_tensile_retreat_m[env_ids] = 0.0
        self._a2_pull_release_or_hold_decision[env_ids] = False
        self._a2_pull_proof_active[env_ids] = False
        self._a2_pull_proof_start_root_x[env_ids] = float("nan")
        self._a2_pull_proof_last_root_x[env_ids] = float("nan")
        self._a2_pull_proof_duration_s[env_ids] = 0.0
        self._a2_pull_proof_displacement_m[env_ids] = 0.0
        self._a2_pull_proof_streak[env_ids] = 0
        self._a2_pull_proof_valid[env_ids] = False
        self._a2_pull_minimum_panel_robot_clearance_m[env_ids] = float("nan")
        self._a2_pull_clearance_ready[env_ids] = False
        self._a2_pull_aperture_ready[env_ids] = False
        self._a2_pull_frame_passage[env_ids] = False
        self._a2_pull_frame_passage_step[env_ids] = -1
        self._a2_pull_planar_crossing[env_ids] = False
        self._a2_pull_planar_crossing_step[env_ids] = -1
        self._a2_pull_detour[env_ids] = False
        self._a2_pull_frame_approach[env_ids] = False
        self._a2_pull_frame_approach_active[env_ids] = False
        self._a2_pull_frame_approach_pre_aperture_steps[env_ids] = 0
        self._a2_pull_frame_approach_post_frame_passage_steps[env_ids] = 0
        self._a2_pull_frame_midpoint_distance_min_m[env_ids] = float("nan")
        self._a2_pull_deliberate_release[env_ids] = False
        self._a2_pull_deliberate_release_step[env_ids] = -1
        if self._is_a2_pull_v5():
            self._a2_pull_v5_persistent_release_streak[env_ids] = 0
            self._a2_pull_v5_persistent_release[env_ids] = False
            self._a2_pull_v5_intervention_elapsed_steps[env_ids] = 0
            self._a2_pull_v5_intervention_active[env_ids] = False
            self._a2_pull_v5_intervention_fired[env_ids] = False
            self._a2_pull_v5_probe_solvable[env_ids] = False
            self._a2_pull_v5_probe_anchor_initialized[env_ids] = False
            self._a2_pull_v5_probe_waypoint_target_xy[env_ids] = float("nan")
            self._a2_pull_v5_probe_yaw_target[env_ids] = float("nan")
            self._a2_pull_v5_probe_waypoint_error_m[env_ids] = float("nan")
            self._a2_pull_v5_probe_yaw_error_rad[env_ids] = float("nan")
            self._a2_pull_v5_probe_waypoint_arrived[env_ids] = False
            self._a2_pull_v5_probe_yaw_arrived[env_ids] = False
            self._a2_pull_v5_probe_anchor_pass[env_ids] = False
            self._a2_pull_v5_capture_e5_seen[env_ids] = False
            self._a2_pull_v5_capture_pending[env_ids] = False
            self._a2_pull_v5_capture_recorded[env_ids] = False
            self._a2_pull_v5_capture_target_step[env_ids] = -1
            for env_id in env_ids.tolist():
                source = self._a2_pull_v5_pending_reset_source[env_id]
                if self.config.get("a2_pull_v5_start_override_enabled", False) and source.startswith(
                    "bank_"
                ):
                    source = "bank_natural_e5_override"
                self._a2_pull_v5_reset_source[env_id] = source
                if self._a2_pull_v5_reset_source[env_id] not in A2_PULL_V5_RESET_SOURCES:
                    raise RuntimeError(
                        "Pull-v5 reset_source must be exactly natural, bank_natural_e5, "
                        "bank_natural_e5_plus, or bank_constructed."
                    )
        self._a2_pull_first_negative_x_motion_step[env_ids] = -1
        self._a2_pull_prev_stable_contact[env_ids] = False
        self._a2_pull_prev_panel_contact[env_ids] = False
        self._a2_pull_post_release_recontact_count[env_ids] = 0
        self._a2_pull_base_path_length_m[env_ids] = 0.0
        self._a2_pull_prev_base_pos_xy[env_ids] = float("nan")
        self._a2_pull_base_reversal_count[env_ids] = 0
        self._a2_pull_prev_travel_velocity[env_ids] = float("nan")
        self._a2_pull_swept_arc_clearance_margin_current_m[env_ids] = float("nan")
        self._a2_pull_swept_arc_clearance_margin_min_m[env_ids] = float("nan")
        self._a2_pull_corridor_door_wide_pre_aperture_steps[env_ids] = 0
        self._a2_pull_corridor_clean_passage_pre_aperture_steps[env_ids] = 0
        self._a2_pull_stage0_staging_band[env_ids] = False
        self._a2_pull_stage0_arm_default[env_ids] = False
        self._a2_pull_stage0_base_still[env_ids] = False
        self._a2_pull_first_scripted_activation_step[env_ids] = -1
        self._a2_pull_hinge_at_first_positive_progress_rad[env_ids] = float("nan")
        self._a2_pull_held_hinge_max_rad[env_ids] = float("nan")
        self._a2_pull_hinge_at_decision_rad[env_ids] = float("nan")
        self._a2_pull_root_outward_excursion_m[env_ids] = 0.0
        self._a2_pull_first_path_reversal_step[env_ids] = -1
        self._a2_pull_body_panel_contact_steps[env_ids] = 0
        self._a2_pull_body_panel_contact_impulse_ns[env_ids] = 0.0
        self._a2_pull_prev_handle_to_tcp_pos[env_ids] = float("nan")
        self._a2_pull_handle_local_slip_xyz_mps[env_ids] = float("nan")
        self._a2_pull_handle_local_slip_valid[env_ids] = False
        self._a2_pull_passage_attempt_hinge_rad[env_ids] = float("nan")
        if self._is_a2_pull_v5():
            self._a2_pull_v5_start_override_active[env_ids] = False
            self._a2_pull_v5_start_override_active_steps[env_ids] = 0
            self._a2_pull_v5_start_override_base_slice_equal[env_ids] = True
            self._a2_pull_v5_start_override_outside_window[env_ids] = False
            self._a2_pull_v5_probe_phase_index[env_ids] = 0
            self._a2_pull_v5_probe_phase_initialized[env_ids] = False
            self._a2_pull_v5_probe_phase_waypoint_arrived[env_ids] = False
            self._a2_pull_v5_probe_phase_yaw_arrived[env_ids] = False
            self._a2_pull_v5_probe_sequence_complete[env_ids] = False
        if self._a2_pull_v5_characterization_enabled:
            self._a2_pull_v5_characterization_pending[env_ids] = False
            self._a2_pull_v5_characterization_active[env_ids] = False
            self._a2_pull_v5_characterization_xy_target_initialized[env_ids] = False
            self._a2_pull_v5_characterization_xy_target[env_ids] = float("nan")
            self._a2_pull_v5_characterization_episode_indices[env_ids] = 0
            self._a2_pull_v5_characterization_step[env_ids] = -1
            self._a2_pull_v5_characterization_requested_u[env_ids] = 0.0
            self._a2_pull_v5_characterization_phase_u[env_ids] = 0.0
            self._a2_pull_v5_characterization_raw_base[env_ids] = 0.0
            self._a2_pull_v5_characterization_physical_base[env_ids] = 0.0
            self._a2_pull_v5_characterization_pre_root_pos[env_ids] = float("nan")
            self._a2_pull_v5_characterization_pre_root_yaw[env_ids] = float("nan")
            for env_id in env_ids.tolist():
                self._a2_pull_v5_characterization_phase[env_id] = "inactive"
        return result

    def record_a2_pull_release_or_hold_decision(self, decision_mask: torch.Tensor) -> None:
        """Latch an explicit E5 decision supplied by a probe or policy evaluator."""

        if (
            not torch.is_tensor(decision_mask)
            or decision_mask.shape != (self.num_envs,)
            or decision_mask.dtype != torch.bool
            or decision_mask.device != torch.device(self.device)
        ):
            raise RuntimeError(
                "Pull E5 decision requires a device-local bool vector with one value per env."
            )
        before_e4 = decision_mask & ~self._a2_pull_event_reached[
            :, A2PullEvent.E4_POSITIVE_HINGE_RETAINED
        ]
        if torch.any(before_e4):
            raise RuntimeError("Pull E5 decision cannot be recorded before E4.")
        if self._get_a2_pull_threshold_mode() == "report_only":
            before_clearance = decision_mask & ~self._a2_pull_clearance_ready
            if torch.any(before_clearance):
                raise RuntimeError("Pull E5 decision cannot be recorded before measured clearance.")
        self._a2_pull_release_or_hold_decision |= decision_mask

    def _get_a2_pull_whole_body_clear_mask(self, door_x: torch.Tensor) -> torch.Tensor:
        """Use every robot body position for the single E7 completion predicate."""

        robot_body_pos_w = self.simulator.scene.articulations["robot"].data.body_pos_w
        if (
            not torch.is_tensor(robot_body_pos_w)
            or robot_body_pos_w.ndim != 3
            or robot_body_pos_w.shape[0] != self.num_envs
            or robot_body_pos_w.shape[2] != 3
            or not torch.all(torch.isfinite(robot_body_pos_w))
            or tuple(door_x.shape) != (self.num_envs,)
            or door_x.device != robot_body_pos_w.device
        ):
            raise RuntimeError("Pull E7 requires finite high-level robot body_pos_w and door_x.")
        signed_body_progress = self._pull_direction.signed_crossing_progress(
            robot_body_pos_w[:, :, 0], door_x[:, None]
        )
        return torch.all(signed_body_progress > 1.5, dim=-1)

    def _get_a2_pull_door_frame_midpoint(self, door_states: torch.Tensor) -> torch.Tensor:
        """Return the shared world XY midpoint used by frame-passage predicates."""

        return door_states[:, 0:2]

    def _get_a2_pull_frame_approach_active_mask(self) -> torch.Tensor:
        """Return the exact v4 frame-approach reward activation mask."""

        return (
            self._make_mask([self.STAGE_SWING, self.STAGE_THROUGH])
            & self._a2_pull_aperture_ready
            & ~self._a2_pull_frame_passage
        )

    def _get_a2_pull_minimum_panel_robot_clearance(self) -> torch.Tensor:
        """Return the signed trunk-footprint clearance to the current door-panel slab."""

        door_states = self.simulator.get_task_root_state("door")
        door_data = self.simulator.scene.articulations["door"].data
        robot_data = self.simulator.scene.articulations["robot"].data
        panel_body_quat_w = door_data.body_quat_w[:, self._a2_pull_door_panel_body_id]
        trunk_body_pos_w = robot_data.body_pos_w[:, self._a2_pull_trunk_body_id]
        if (
            not torch.is_tensor(door_states)
            or door_states.ndim != 2
            or door_states.shape[0] != self.num_envs
            or door_states.shape[1] < 7
            or not door_states.is_floating_point()
            or door_states.device != torch.device(self.device)
            or not torch.all(torch.isfinite(door_states))
            or not torch.is_tensor(panel_body_quat_w)
            or tuple(panel_body_quat_w.shape) != (self.num_envs, 4)
            or panel_body_quat_w.dtype != door_states.dtype
            or panel_body_quat_w.device != door_states.device
            or not torch.all(torch.isfinite(panel_body_quat_w))
            or not torch.is_tensor(trunk_body_pos_w)
            or tuple(trunk_body_pos_w.shape) != (self.num_envs, 3)
            or trunk_body_pos_w.dtype != door_states.dtype
            or trunk_body_pos_w.device != door_states.device
            or not torch.all(torch.isfinite(trunk_body_pos_w))
            or tuple(self.door_width.shape) != (self.num_envs,)
            or self.door_width.dtype != door_states.dtype
            or self.door_width.device != door_states.device
            or not torch.all(torch.isfinite(self.door_width))
            or tuple(self.door_open_lr.shape) != (self.num_envs,)
            or self.door_open_lr.dtype != door_states.dtype
            or self.door_open_lr.device != door_states.device
            or not torch.all(torch.isfinite(self.door_open_lr))
        ):
            raise RuntimeError(
                "Pull E5 signed clearance requires finite floating root, panel, trunk, "
                "and door metadata tensors on the simulation device."
            )
        if torch.any(self.door_width <= 2.0 * self._A2_PULL_PANEL_END_GAP_M):
            raise RuntimeError(
                "Pull E5 signed clearance requires door width greater than both panel "
                "gaps."
            )
        if torch.any(torch.abs(self.door_open_lr) != 1.0):
            raise RuntimeError("Pull E5 signed clearance requires door_open_lr exactly +/-1.")

        _, _, door_root_yaw = euler_xyz_from_quat(door_states[:, 3:7])
        _, _, panel_yaw = euler_xyz_from_quat(panel_body_quat_w)
        root_cos = torch.cos(door_root_yaw)
        root_sin = torch.sin(door_root_yaw)
        hinge_local_x = torch.full_like(self.door_width, self._A2_PULL_DOOR_HINGE_LOCAL_X_M)
        hinge_local_y = -0.5 * self.door_width * self.door_open_lr
        hinge_world_xy = door_states[:, :2] + torch.stack(
            (
                root_cos * hinge_local_x - root_sin * hinge_local_y,
                root_sin * hinge_local_x + root_cos * hinge_local_y,
            ),
            dim=-1,
        )
        panel_axis_world = self.door_open_lr[:, None] * torch.stack(
            (-torch.sin(panel_yaw), torch.cos(panel_yaw)), dim=-1
        )
        panel_end_gap = torch.full_like(self.door_width, self._A2_PULL_PANEL_END_GAP_M)
        panel_end_distance = self.door_width - panel_end_gap
        panel_p0 = hinge_world_xy + panel_axis_world * panel_end_gap[:, None]
        panel_p1 = hinge_world_xy + panel_axis_world * panel_end_distance[:, None]
        panel_segment = panel_p1 - panel_p0
        segment_length_sq = torch.sum(panel_segment * panel_segment, dim=-1)
        if torch.any(segment_length_sq <= torch.finfo(door_states.dtype).eps):
            raise RuntimeError("Pull E5 signed clearance requires a non-degenerate panel segment.")

        trunk_center_xy = trunk_body_pos_w[:, :2]
        segment_projection = torch.sum(
            (trunk_center_xy - panel_p0) * panel_segment, dim=-1
        ) / segment_length_sq
        closest_panel_xy = panel_p0 + segment_projection.clamp(0.0, 1.0)[:, None] * panel_segment
        raw_signed = (
            torch.linalg.norm(trunk_center_xy - closest_panel_xy, dim=-1)
            - self._A2_PULL_PANEL_HALF_THICKNESS_M
            - self._A2_PULL_TRUNK_FOOTPRINT_RADIUS_M
        )
        body_panel_per_filter, _ = self._get_a2_door_body_panel_contact_forces()
        contact_with_ordered_trunk = body_panel_per_filter[:, 0] > 0.0
        minimum_clearance = torch.where(
            contact_with_ordered_trunk,
            torch.minimum(raw_signed, torch.zeros_like(raw_signed)),
            raw_signed,
        )
        if not torch.all(torch.isfinite(minimum_clearance)):
            raise RuntimeError("Pull E5 signed clearance must be finite.")
        return minimum_clearance

    def _get_a2_pull_control_proof_thresholds(self) -> tuple[float, float, float, int]:
        duration = self._get_required_positive_float_config(
            "a2_pull_control_proof_min_duration_s", "pull E2 proof duration"
        )
        retreat = self._get_required_positive_float_config(
            "a2_pull_control_proof_min_retreat_m", "pull E2 proof retreat"
        )
        tolerance = self._get_required_positive_float_config(
            "a2_pull_control_proof_monotone_tolerance_m", "pull E2 proof monotone tolerance"
        )
        steps_value = self.config.get("a2_pull_control_proof_min_streak_steps")
        if isinstance(steps_value, bool) or not isinstance(steps_value, int) or steps_value <= 0:
            raise RuntimeError(
                "a2_pull_control_proof_min_streak_steps must be a positive integer."
            )
        return duration, retreat, tolerance, steps_value

    def _get_a2_pull_load_bearing_income_mask(self) -> torch.Tensor:
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
            & self._a2_pull_capture_valid
            & self._a2_pull_proof_active
            & self._a2_pull_proof_valid
        )

    @override
    def _pre_compute_observations_callback(self, env_ids=None, *, post_physics=False):
        super()._pre_compute_observations_callback(env_ids, post_physics=post_physics)
        if post_physics:
            self._update_a2_pull_event_telemetry(env_ids)
            self._finalize_a2_pull_v5_characterization_step()

    @override
    def _get_a2_route_crossing_coordinate(self, root_x: torch.Tensor) -> torch.Tensor:
        return self._pull_direction.signed_crossing_progress(root_x)

    @override
    def _update_a2_v20_state(self, env_ids=None) -> None:
        selectors = {
            "a2_v20_R1_send_curriculum_enabled": self._get_a2_v20_r1_send_curriculum_enabled(),
            "a2_v20_send_latch_enabled": self._get_a2_v20_send_latch_enabled(),
            "a2_v20_telemetry_enabled": self._get_a2_v20_telemetry_enabled(),
            "a2_v20_traversal_economics_enabled": self._get_a2_v20_traversal_economics_enabled(),
            "a2_v20_arm_tie_enabled": self._get_a2_v20_arm_tie_enabled(),
            "a2_corridor_enabled": self._get_a2_corridor_enabled(),
        }
        active = {name: value for name, value in selectors.items() if value}
        crossing_mode = self._get_a2_v20_pre_send_crossing_mode()
        if active or crossing_mode != "disabled":
            raise RuntimeError(
                "Pull-v0 keeps v20 send/crossing/corridor behavior disabled; "
                f"active={active}, crossing_mode={crossing_mode!r}."
            )
        return None

    def _update_a2_pull_event_telemetry(self, env_ids=None) -> None:
        selected = (
            torch.arange(self.num_envs, dtype=torch.long, device=self.device)
            if env_ids is None
            else env_ids
        )
        if (
            not torch.is_tensor(selected)
            or selected.ndim != 1
            or selected.dtype != torch.long
            or selected.device != torch.device(self.device)
            or torch.any(selected < 0)
            or torch.any(selected >= self.num_envs)
        ):
            raise RuntimeError("Pull event telemetry requires valid device-local env ids.")

        root_states = self.simulator.robot_root_states
        door_states = self.simulator.get_task_root_state("door")
        if (
            not torch.is_tensor(root_states)
            or root_states.ndim != 2
            or root_states.shape[0] != self.num_envs
            or root_states.shape[1] < 13
            or not torch.all(torch.isfinite(root_states))
            or not torch.is_tensor(door_states)
            or door_states.ndim != 2
            or door_states.shape[0] != self.num_envs
            or door_states.shape[1] < 7
            or not torch.all(torch.isfinite(door_states))
        ):
            raise RuntimeError("Pull event telemetry requires finite robot and door root states.")
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError(f"Pull event telemetry requires positive finite dt; got {dt!r}.")
        control_step = self.episode_length_buf.to(dtype=torch.long)
        root_x = root_states[:, 0]
        door_x = door_states[:, 0]
        frame_midpoint_xy = self._get_a2_pull_door_frame_midpoint(door_states)
        frame_delta_xy = frame_midpoint_xy - root_states[:, 0:2]
        frame_midpoint_distance = torch.linalg.vector_norm(frame_delta_xy, dim=-1)
        frame_approach_now = torch.abs(frame_delta_xy[:, 0]) < 0.3
        in_frame_opening_now = torch.abs(frame_delta_xy[:, 1]) <= 0.5 * self.door_width
        self._a2_pull_frame_midpoint_distance_min_m[:] = torch.where(
            torch.isfinite(self._a2_pull_frame_midpoint_distance_min_m),
            torch.minimum(
                self._a2_pull_frame_midpoint_distance_min_m,
                frame_midpoint_distance,
            ),
            frame_midpoint_distance,
        )
        _, _, root_yaw = euler_xyz_from_quat(root_states[:, 3:7])
        _, _, door_yaw = euler_xyz_from_quat(door_states[:, 3:7])
        expected_approach_yaw = (1.0 + self._pull_direction.io_sign) * 0.5 * math.pi
        yaw_error = torch.abs(wrap_to_pi(root_yaw - door_yaw - expected_approach_yaw))

        # Stage-0 predicates are report-only telemetry and intentionally remain
        # separate from the oracle admission gate.
        grasp_target = self._compute_grasp_target()
        x_min, x_max, y_tol = self._get_a2_stage0_staging_band()
        self._a2_pull_stage0_staging_band[:] = a2_signed_stage0_staging_band_mask(
            root_states[:, :3], grasp_target, x_min, x_max, y_tol, self._pull_direction
        )
        arm_default = self._get_a2_arm_default_dof_pos()
        arm_deviation = torch.abs(
            self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx] - arm_default
        ).amax(dim=-1)
        arm_tolerance = self._get_required_positive_float_config(
            "a2_stage0_arm_default_max_deviation", "pull stage0 predicate telemetry"
        )
        self._a2_pull_stage0_arm_default[:] = arm_deviation < arm_tolerance
        base_command = self.get_physical_homie_commands()
        if (
            not torch.is_tensor(base_command)
            or tuple(base_command.shape) != (self.num_envs, 5)
            or base_command.device != torch.device(self.device)
            or not torch.all(torch.isfinite(base_command))
        ):
            raise RuntimeError("Pull stage0 predicate telemetry requires finite physical commands.")
        self._a2_pull_stage0_base_still[:] = torch.linalg.norm(
            base_command[:, :3], dim=-1
        ) <= 0.1

        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "pull event telemetry"
        )
        bilateral_contact = contact_masks["both_contact"]
        no_handle_contact = ~torch.any(contact_masks["contacting"], dim=-1)
        stable_contact = bilateral_contact & (
            self._get_a2_stage2_contact_stability_mask()
            | self._get_a2_hold_streak_ok_mask()
        )
        body_panel_per_filter, body_panel_total = self._get_a2_door_body_panel_contact_forces()
        arm_panel_per_filter, arm_panel_total = self._get_a2_door_arm_panel_contact_forces()
        del body_panel_per_filter, arm_panel_per_filter
        panel_clear = (body_panel_total + arm_panel_total) == 0.0

        # v3 traversal telemetry is pull-local and does not alter v0/v1/v2
        # predicates.  A frame passage is latched only inside the measured
        # door opening and while the panel-contact gate is clear.
        if self._is_a2_pull_traversal():
            frame_passage_now = (
                frame_approach_now & in_frame_opening_now & panel_clear
            )
            new_frame_passage = frame_passage_now & ~self._a2_pull_frame_passage
            self._a2_pull_frame_passage |= frame_passage_now
            self._a2_pull_frame_passage_step[new_frame_passage] = control_step[
                new_frame_passage
            ]
            self._a2_pull_frame_approach |= frame_approach_now & in_frame_opening_now
        else:
            frame_passage_now = torch.zeros_like(panel_clear)

        # Report-only base path/reversal metrics use high-level root state and
        # the pull travel direction; they are never reward or stage inputs.
        base_pos_xy = root_states[:, :2]
        previous_base_valid = torch.all(
            torch.isfinite(self._a2_pull_prev_base_pos_xy), dim=-1
        )
        self._a2_pull_base_path_length_m += torch.where(
            previous_base_valid,
            torch.linalg.norm(base_pos_xy - self._a2_pull_prev_base_pos_xy, dim=-1),
            torch.zeros_like(self._a2_pull_base_path_length_m),
        )
        self._a2_pull_prev_base_pos_xy[:] = base_pos_xy
        travel_velocity = self._pull_direction.travel_dir_x * root_states[:, 7]
        previous_velocity_valid = torch.isfinite(self._a2_pull_prev_travel_velocity)
        velocity_reversal = (
            previous_velocity_valid
            & ((self._a2_pull_prev_travel_velocity > 0.0) != (travel_velocity > 0.0))
            & (travel_velocity != 0.0)
            & (self._a2_pull_prev_travel_velocity != 0.0)
        )
        self._a2_pull_base_reversal_count += velocity_reversal.long()
        self._a2_pull_prev_travel_velocity[:] = travel_velocity
        proof_duration_min, proof_retreat_min, monotone_tolerance, proof_steps_min = (
            self._get_a2_pull_control_proof_thresholds()
        )
        previous_root_valid = torch.isfinite(self._a2_pull_proof_last_root_x)
        root_outward_step = self._pull_direction.approach_side_x * (
            root_x - self._a2_pull_proof_last_root_x
        )
        monotone_break = (
            self._a2_pull_proof_active
            & previous_root_valid
            & (root_outward_step < -monotone_tolerance)
        )
        contact_loss = ~stable_contact
        reset_proof = contact_loss | monotone_break
        self._a2_pull_proof_active[reset_proof] = False
        self._a2_pull_proof_start_root_x[reset_proof] = float("nan")
        self._a2_pull_proof_duration_s[reset_proof] = 0.0
        self._a2_pull_proof_displacement_m[reset_proof] = 0.0
        self._a2_pull_proof_streak[reset_proof] = 0
        self._a2_pull_proof_valid[reset_proof] = False
        self._a2_pull_capture_valid[reset_proof] = False
        self._a2_pull_capture_root_x[reset_proof] = float("nan")
        self._a2_pull_max_tensile_retreat_m[reset_proof] = 0.0
        proof_start = stable_contact & ~self._a2_pull_proof_active & ~monotone_break
        self._a2_pull_proof_active[proof_start] = True
        self._a2_pull_proof_start_root_x[proof_start] = root_x[proof_start]
        self._a2_pull_capture_root_x[proof_start] = root_x[proof_start]
        self._a2_pull_capture_valid[proof_start] = True
        proof_live = self._a2_pull_proof_active & stable_contact
        self._a2_pull_proof_duration_s[proof_live] += dt
        proof_displacement = self._pull_direction.approach_side_x * (
            root_x - self._a2_pull_proof_start_root_x
        )
        finite_displacement = torch.isfinite(proof_displacement) & self._a2_pull_proof_active
        self._a2_pull_proof_displacement_m[:] = torch.where(
            finite_displacement,
            torch.clamp_min(proof_displacement, 0.0),
            torch.zeros_like(proof_displacement),
        )
        self._a2_pull_proof_streak[:] = torch.where(
            proof_live & (root_outward_step >= -monotone_tolerance),
            self._a2_pull_proof_streak + 1,
            torch.zeros_like(self._a2_pull_proof_streak),
        )
        self._a2_pull_proof_valid[:] = (
            proof_live
            & (self._a2_pull_proof_duration_s >= proof_duration_min)
            & (self._a2_pull_proof_displacement_m >= proof_retreat_min)
            & (self._a2_pull_proof_streak >= proof_steps_min)
        )
        self._a2_pull_proof_last_root_x[:] = root_x
        self._a2_pull_max_tensile_retreat_m[:] = torch.maximum(
            self._a2_pull_max_tensile_retreat_m,
            self._a2_pull_proof_displacement_m,
        )
        self._a2_pull_root_outward_excursion_m[:] = torch.maximum(
            self._a2_pull_root_outward_excursion_m,
            self._a2_pull_proof_displacement_m,
        )
        tensile_capture = self._a2_pull_proof_valid

        door_joint_pos = self._get_door_joint_pos("pull event telemetry", 3)
        threshold_mode = self._get_a2_pull_threshold_mode()
        latch_threshold_m = self._get_a2_pull_e3_latch_threshold_m()
        self._a2_pull_passage_attempt_hinge_rad[new_frame_passage] = door_joint_pos[
            new_frame_passage, 0
        ]
        handle_unlatched = door_joint_pos[:, 1] >= 0.3
        latch_released = door_joint_pos[:, 2] >= latch_threshold_m
        stable_unlatch_handle_now = stable_contact & handle_unlatched
        stable_unlatch_latch_now = stable_contact & latch_released
        stage3_to4_hinge_threshold = self._get_a2_stage3_to4_door_hinge_threshold()
        relock_handle_now = (
            self._a2_pull_prev_handle_unlatched
            & ~handle_unlatched
            & (door_joint_pos[:, 0] < stage3_to4_hinge_threshold)
        )
        relock_latch_now = (
            self._a2_pull_prev_latch_unlatched
            & ~latch_released
            & (door_joint_pos[:, 0] < stage3_to4_hinge_threshold)
        )
        self._a2_pull_stable_unlatch_handle_ever |= stable_unlatch_handle_now
        self._a2_pull_stable_unlatch_latch_ever |= stable_unlatch_latch_now
        self._a2_pull_relock_handle_ever |= relock_handle_now
        self._a2_pull_relock_latch_ever |= relock_latch_now
        self._a2_pull_prev_handle_unlatched[:] = handle_unlatched
        self._a2_pull_prev_latch_unlatched[:] = latch_released
        positive_hinge = door_joint_pos[:, 0] > 0.0
        first_positive = positive_hinge & torch.isnan(
            self._a2_pull_hinge_at_first_positive_progress_rad
        )
        self._a2_pull_hinge_at_first_positive_progress_rad[first_positive] = door_joint_pos[
            first_positive, 0
        ]
        held_hinge = stable_contact & positive_hinge
        self._a2_pull_held_hinge_max_rad[held_hinge] = torch.where(
            torch.isnan(self._a2_pull_held_hinge_max_rad[held_hinge]),
            door_joint_pos[held_hinge, 0],
            torch.maximum(
                self._a2_pull_held_hinge_max_rad[held_hinge], door_joint_pos[held_hinge, 0]
            ),
        )
        send_hinge_threshold = self._get_a2_v20_send_hinge_threshold()
        aperture_ready_now = stable_contact & (door_joint_pos[:, 0] >= send_hinge_threshold)
        self._a2_pull_aperture_ready |= aperture_ready_now
        if self._is_a2_pull_v5():
            # Persistent release is a K-step no-handle-contact latch after
            # aperture; panel-clear remains a separate diagnostic and must not
            # gate this release predicate.
            persistent_candidate = self._a2_pull_aperture_ready & no_handle_contact
            self._a2_pull_v5_persistent_release_streak[:] = torch.where(
                persistent_candidate,
                self._a2_pull_v5_persistent_release_streak + 1,
                torch.zeros_like(self._a2_pull_v5_persistent_release_streak),
            )
            self._a2_pull_v5_persistent_release |= (
                self._a2_pull_v5_persistent_release_streak
                >= A2_PULL_V5_RELEASE_STREAK_STEPS
            )
        signed_crossing = self._pull_direction.signed_crossing_progress(root_x, door_x)
        planar_crossing_now = signed_crossing > 0.0
        new_planar_crossing = planar_crossing_now & ~self._a2_pull_planar_crossing
        self._a2_pull_planar_crossing |= planar_crossing_now
        self._a2_pull_planar_crossing_step[new_planar_crossing] = control_step[
            new_planar_crossing
        ]
        detour_now = self._is_a2_pull_traversal() & planar_crossing_now & ~self._a2_pull_frame_passage
        self._a2_pull_detour |= detour_now
        whole_body_crossing = self._get_a2_pull_whole_body_clear_mask(door_x)
        minimum_clearance = self._get_a2_pull_minimum_panel_robot_clearance()
        clearance_min = self._get_required_positive_float_config(
            "a2_pull_control_clearance_min_m", "pull E5 measured clearance"
        )
        self._a2_pull_minimum_panel_robot_clearance_m[:] = minimum_clearance
        self._a2_pull_clearance_ready[:] = minimum_clearance >= clearance_min
        self._a2_pull_swept_arc_clearance_margin_current_m[:] = minimum_clearance
        margin_valid = torch.isfinite(minimum_clearance)
        self._a2_pull_swept_arc_clearance_margin_min_m[:] = torch.where(
            torch.isfinite(self._a2_pull_swept_arc_clearance_margin_min_m),
            torch.minimum(
                self._a2_pull_swept_arc_clearance_margin_min_m,
                minimum_clearance,
            ),
            torch.where(
                margin_valid,
                minimum_clearance,
                self._a2_pull_swept_arc_clearance_margin_min_m,
            ),
        )
        body_contact_now = body_panel_total + arm_panel_total > 0.0
        self._a2_pull_body_panel_contact_steps[:] += body_contact_now.long()
        self._a2_pull_body_panel_contact_impulse_ns[:] += (
            (body_panel_total + arm_panel_total) * dt
        )
        deliberate_release_now = (
            self._is_a2_pull_traversal()
            & self._a2_pull_aperture_ready
            & self._a2_pull_prev_stable_contact
            & no_handle_contact
            & self._a2_pull_release_or_hold_decision
            & panel_clear
        )
        new_deliberate_release = deliberate_release_now & ~self._a2_pull_deliberate_release
        self._a2_pull_deliberate_release |= deliberate_release_now
        self._a2_pull_deliberate_release_step[new_deliberate_release] = control_step[
            new_deliberate_release
        ]
        post_release_recontact = (
            self._a2_pull_deliberate_release
            & body_contact_now
            & ~self._a2_pull_prev_panel_contact
        )
        self._a2_pull_post_release_recontact_count += post_release_recontact.long()
        self._a2_pull_prev_panel_contact[:] = body_contact_now
        self._a2_pull_prev_stable_contact[:] = stable_contact
        first_negative_x_motion = (
            (self._a2_pull_first_negative_x_motion_step < 0)
            & self._a2_pull_deliberate_release
            & (root_states[:, 7] < 0.0)
        )
        self._a2_pull_first_negative_x_motion_step[first_negative_x_motion] = control_step[
            first_negative_x_motion
        ]

        reached = self._a2_pull_event_reached
        if threshold_mode == "report_only":
            decision_mask = (
                reached[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED]
                & stable_contact
                & panel_clear
                & self._a2_pull_clearance_ready
            )
            self.record_a2_pull_release_or_hold_decision(decision_mask)
            decision_latched = decision_mask & ~torch.isfinite(
                self._a2_pull_hinge_at_decision_rad
            )
            self._a2_pull_hinge_at_decision_rad[decision_latched] = door_joint_pos[
                decision_latched, 0
            ]

        evidence = torch.zeros_like(reached)
        evidence[:, A2PullEvent.E0_RESET_VALID] = (
            (self._pull_direction.signed_distance_to_door(root_x, door_x) > 0.0)
            & (yaw_error < math.pi / 2.0)
            & panel_clear
        )
        evidence[:, A2PullEvent.E1_OUTSIDE_FACE_PREGRASP] = (
            (self.stage_buf >= self.STAGE_PREGRASP) & panel_clear
        )
        evidence[:, A2PullEvent.E2_TENSILE_CAPTURE] = tensile_capture
        if threshold_mode == "hard_gate":
            evidence[:, A2PullEvent.E3_LATCH_RELEASE] = (
                latch_released
                & stable_contact
            )
            evidence[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED] = (
                reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
                & (door_joint_pos[:, 0] > self._get_a2_stage3_to4_door_hinge_threshold())
                & stable_contact
                & panel_clear
            )
            evidence[:, A2PullEvent.E5_CLEARANCE_DECISION] = (
                self._a2_pull_aperture_ready & panel_clear
            )
        else:
            evidence[:, A2PullEvent.E3_LATCH_RELEASE] = (
                reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
                & latch_released
                & stable_contact
                & panel_clear
            )
            evidence[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED] = (
                reached[:, A2PullEvent.E3_LATCH_RELEASE]
                & positive_hinge
                & stable_contact
                & panel_clear
            )
            evidence[:, A2PullEvent.E5_CLEARANCE_DECISION] = (
                reached[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED]
                & self._a2_pull_release_or_hold_decision
                & self._a2_pull_clearance_ready
                & panel_clear
            )
        frame_requirement = (
            self._a2_pull_frame_passage
            if self._is_a2_pull_traversal()
            else torch.ones_like(self._a2_pull_event_reached[:, 0])
        )
        evidence[:, A2PullEvent.E6_PATH_REVERSAL_ENTRY] = (
            reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
            & (signed_crossing > 0.0)
            & (self._pull_direction.travel_dir_x * root_states[:, 7] > 0.0)
            & panel_clear
            & frame_requirement
        )
        evidence[:, A2PullEvent.E7_WHOLE_BODY_CLEAR] = (
            reached[:, A2PullEvent.E6_PATH_REVERSAL_ENTRY]
            & whole_body_crossing
            & panel_clear
            & frame_requirement
        )
        old_reached = reached[selected].clone()
        updated_reached, updated_first = advance_a2_pull_events(
            old_reached,
            evidence[selected],
            self._a2_pull_first_event_step[selected],
            control_step[selected],
            event_predecessors=(
                A2_PULL_HARD_GATE_EVENT_PREDECESSORS
                if threshold_mode == "hard_gate"
                else None
            ),
        )
        newly_reached = updated_reached & ~old_reached
        self._a2_pull_event_reached[selected] = updated_reached
        self._a2_pull_first_event_step[selected] = updated_first
        selected_time = control_step[selected].to(dtype=torch.float32) * dt
        self._a2_pull_first_event_time_s[selected] = torch.where(
            newly_reached,
            selected_time[:, None].expand_as(newly_reached).to(dtype=torch.float32),
            self._a2_pull_first_event_time_s[selected],
        )
        if threshold_mode == "hard_gate":
            decision_mask = torch.zeros_like(self._a2_pull_release_or_hold_decision)
            decision_mask[selected] = (
                updated_reached[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED]
                & self._a2_pull_aperture_ready[selected]
                & panel_clear[selected]
            )
            self.record_a2_pull_release_or_hold_decision(decision_mask)
            decision_latched = decision_mask & ~torch.isfinite(
                self._a2_pull_hinge_at_decision_rad
            )
            self._a2_pull_hinge_at_decision_rad[decision_latched] = door_joint_pos[
                decision_latched, 0
            ]
        new_reversal = (
            (self._a2_pull_first_path_reversal_step[selected] < 0)
            & updated_reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
            & (signed_crossing[selected] > 0.0)
        )
        self._a2_pull_first_path_reversal_step[selected[new_reversal]] = control_step[
            selected[new_reversal]
        ]

        frame_data = self._get_a2_gripper_handle_frame_transformer().data
        handle_to_tcp_pos = frame_data.target_pos_source[:, 0, :]
        if (
            not torch.is_tensor(handle_to_tcp_pos)
            or handle_to_tcp_pos.shape != (self.num_envs, 3)
            or not torch.all(torch.isfinite(handle_to_tcp_pos))
        ):
            raise RuntimeError("Pull slip telemetry requires finite handle-local TCP position.")
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError(f"Pull slip telemetry requires positive finite dt; got {dt!r}.")
        derivative_valid = torch.all(
            torch.isfinite(self._a2_pull_prev_handle_to_tcp_pos), dim=-1
        )
        self._a2_pull_handle_local_slip_xyz_mps[:] = torch.where(
            derivative_valid[:, None],
            (handle_to_tcp_pos - self._a2_pull_prev_handle_to_tcp_pos) / dt,
            torch.full_like(handle_to_tcp_pos, float("nan")),
        )
        self._a2_pull_handle_local_slip_valid[:] = derivative_valid
        self._a2_pull_prev_handle_to_tcp_pos[:] = handle_to_tcp_pos

    @override
    def _after_reward_components(self, raw_components, scaled_components):
        result = super()._after_reward_components(raw_components, scaled_components)
        if set(raw_components) != set(scaled_components) or not raw_components:
            raise RuntimeError("Pull telemetry requires complete non-empty reward component maps.")
        captured = {}
        for name, raw_value in raw_components.items():
            if (
                not torch.is_tensor(raw_value)
                or raw_value.shape != (self.num_envs,)
                or raw_value.device != torch.device(self.device)
            ):
                raise RuntimeError(
                    f"Pull raw reward component {name!r} must be a device-local env vector."
                )
            value = raw_value.float() if raw_value.dtype == torch.bool else raw_value
            if not value.is_floating_point() or not torch.all(torch.isfinite(value)):
                raise RuntimeError(f"Pull raw reward component {name!r} must be finite.")
            captured[name] = value.detach().clone()
        self._a2_pull_last_raw_reward_components = captured
        if (self._is_a2_pull_v4() or self._is_a2_pull_v5()) and "a2_pull_frame_approach" not in self.reward_scales:
            self._a2_pull_frame_approach_active[:] = False
        if self._is_a2_pull_v4() or self._is_a2_pull_v5():
            self._a2_pull_frame_approach_pre_aperture_steps += (
                self._a2_pull_frame_approach_active & ~self._a2_pull_aperture_ready
            ).long()
            self._a2_pull_frame_approach_post_frame_passage_steps += (
                self._a2_pull_frame_approach_active & self._a2_pull_frame_passage
            ).long()
        if self._is_a2_pull_traversal():
            for reward_name in (
                "a2_corridor_door_wide",
                "a2_corridor_clean_passage",
            ):
                raw_value = captured.get(reward_name)
                if (
                    raw_value is None
                    and reward_name == "a2_corridor_door_wide"
                    and (self._is_a2_pull_v4() or self._is_a2_pull_v5())
                    and reward_name not in self.reward_scales
                ):
                    raw_value = torch.zeros(self.num_envs, device=self.device)
                if (
                    not torch.is_tensor(raw_value)
                    or tuple(raw_value.shape) != (self.num_envs,)
                    or raw_value.device != torch.device(self.device)
                    or not raw_value.is_floating_point()
                    or not torch.all(torch.isfinite(raw_value))
                ):
                    raise RuntimeError(
                        f"Pull-v3 telemetry requires finite raw reward component {reward_name!r}."
                    )
                pre_aperture = raw_value > 0.0
                if reward_name == "a2_corridor_door_wide":
                    self._a2_pull_corridor_door_wide_pre_aperture_steps += (
                        pre_aperture & ~self._a2_pull_aperture_ready
                    ).long()
                else:
                    self._a2_pull_corridor_clean_passage_pre_aperture_steps += (
                        pre_aperture & ~self._a2_pull_aperture_ready
                    ).long()
        if not self._a2_pull_runtime_telemetry_contract_checked:
            self._a2_pull_runtime_telemetry_contract_sample = (
                self.get_a2_pull_control_step_telemetry()
            )
            self._a2_pull_runtime_telemetry_contract_checked = True
        return result

    def _get_a2_pull_v5_terminal_invariants(
        self, env_id: int, reached: Mapping[str, bool]
    ) -> dict[str, bool]:
        source = self._a2_pull_v5_reset_source[env_id]
        declared_source = self._a2_pull_v5_declared_reset_source[env_id]
        declared_group = "bank" if declared_source.startswith("bank_") else "natural"
        actual_group = "bank" if source.startswith("bank_") else "natural"
        e2 = bool(reached[A2PullEvent.E2_TENSILE_CAPTURE.name])
        e4 = bool(reached[A2PullEvent.E4_POSITIVE_HINGE_RETAINED.name])
        e7 = bool(reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name])
        first_e4_step = int(self._a2_pull_first_event_step[env_id, A2PullEvent.E4_POSITIVE_HINGE_RETAINED].item())
        first_activation_step = int(self._a2_pull_first_scripted_activation_step[env_id].item())
        hinge_at_decision = self._a2_pull_hinge_at_decision_rad[env_id]
        override_steps = self.config.get(
            "a2_pull_v5_start_override_steps", A2_PULL_V5_START_OVERRIDE_STEPS
        )
        episode_step = int(self.episode_length_buf[env_id].item())
        override_active_now = bool(self._a2_pull_v5_start_override_active[env_id].item())
        override_active_outside_window = override_active_now and not (
            0 <= episode_step < int(override_steps)
        )
        stage4_below_gate = source != "natural" and (
            not torch.isfinite(hinge_at_decision) or hinge_at_decision < 1.60
        )
        return {
            "fake_e4": e4 and not e2,
            "stage4_snapshot_below_hinge_gate": bool(stage4_below_gate),
            "dont_push_before_true_stage3_to4": bool(
                e4 and first_activation_step >= 0 and first_e4_step >= 0 and first_activation_step < first_e4_step
            ),
            "target_root_before_aperture_ready": bool(
                not self._a2_pull_aperture_ready[env_id].item()
                and self._a2_pull_frame_approach_active[env_id].item()
            ),
            "corridor_active_before_aperture_ready": bool(
                self._a2_pull_corridor_door_wide_pre_aperture_steps[env_id].item() > 0
                or self._a2_pull_corridor_clean_passage_pre_aperture_steps[env_id].item() > 0
            ),
            "complete_without_frame_passage": bool(
                e7 and not self._a2_pull_frame_passage[env_id].item()
            ),
            "frame_approach_active_before_aperture_ready": bool(
                self._a2_pull_frame_approach_pre_aperture_steps[env_id].item() > 0
            ),
            "frame_approach_active_after_frame_passage": bool(
                self._a2_pull_frame_approach_post_frame_passage_steps[env_id].item() > 0
            ),
            "canonical_not_counted_as_natural_start": bool(
                declared_group != actual_group
            ),
            "failed_settle_not_in_bank": bool(
                source != "natural" and self._get_a2_pull_v5_bank_settle_valid(env_id) is not True
            ),
            "override_active_outside_canonical_start": bool(
                (
                    source != "bank_natural_e5_override"
                    and self._a2_pull_v5_start_override_active_steps[env_id].item() > 0
                )
                or (
                    source != "bank_natural_e5_override" and override_active_now
                )
                or override_active_outside_window
                or self._a2_pull_v5_start_override_outside_window[env_id].item()
                or not self._a2_pull_v5_start_override_base_slice_equal[env_id].item()
            ),
        }

    def _get_a2_pull_v5_bank_settle_valid(self, env_id: int) -> bool | None:
        return True if self._a2_pull_v5_reset_source[env_id] != "natural" else None

    @override
    def _get_a2_terminal_diagnostics(self, env_ids):
        records = super()._get_a2_terminal_diagnostics(env_ids)
        pull_records = self.get_a2_pull_control_step_telemetry(env_ids)
        episode_records = self.get_a2_pull_episode_records(env_ids, records)
        if len(records) != len(pull_records):
            raise RuntimeError(
                "Pull terminal diagnostics requires one E0-E7 telemetry record per env."
            )
        selected = (
            torch.arange(self.num_envs, dtype=torch.long, device=self.device)
            if env_ids is None
            else env_ids
        )
        for env_id, record, pull_record, episode_record in zip(
            selected.tolist(), records, pull_records, episode_records
        ):
            if "pull_v0" in record:
                raise RuntimeError("Pull terminal diagnostic field pull_v0 already exists.")
            record["pull_v0"] = pull_record
            record["pull_v0_episode"] = episode_record
            record["pull_v0_stage0_predicates"] = {
                "staging_band": bool(self._a2_pull_stage0_staging_band[env_id].item()),
                "arm_default": bool(self._a2_pull_stage0_arm_default[env_id].item()),
                "base_still": bool(self._a2_pull_stage0_base_still[env_id].item()),
                "event_admission": "report_only",
            }
            record["pull_v0_scripted_activation"] = {
                "first_control_step": (
                    int(self._a2_pull_first_scripted_activation_step[env_id].item())
                    if int(self._a2_pull_first_scripted_activation_step[env_id].item()) >= 0
                    else A2_PULL_NA
                ),
                "admission_stage2_grasp_gate": False,
                "proof_world_direction": "+X",
            }
            record["pull_v2_unlatch"] = {
                "stable_unlatch_handle_based": bool(
                    self._a2_pull_stable_unlatch_handle_ever[env_id].item()
                ),
                "stable_unlatch_latch_based": bool(
                    self._a2_pull_stable_unlatch_latch_ever[env_id].item()
                ),
                "relock_handle_based": bool(self._a2_pull_relock_handle_ever[env_id].item()),
                "relock_latch_based": bool(self._a2_pull_relock_latch_ever[env_id].item()),
                "handle_unlatch_threshold_rad": 0.3,
                "latch_unlatch_threshold_m": self._get_a2_pull_e3_latch_threshold_m(),
                "relock_definition": (
                    "prior stable threshold crossing, then threshold loss while "
                    "hinge remains below the Stage3-to4 gate"
                ),
            }
            if self._is_a2_pull_traversal():
                reached = episode_record["event_reached"]
                first_steps = episode_record["first_event_step"]
                e5_to_e7_steps = (
                    int(first_steps[A2PullEvent.E7_WHOLE_BODY_CLEAR.name])
                    - int(first_steps[A2PullEvent.E5_CLEARANCE_DECISION.name])
                    if reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]
                    and reached[A2PullEvent.E5_CLEARANCE_DECISION.name]
                    else None
                )
                release_step = int(self._a2_pull_deliberate_release_step[env_id].item())
                first_negative_step = int(
                    self._a2_pull_first_negative_x_motion_step[env_id].item()
                )
                record["pull_v3_traversal"] = {
                    "frame_passage": bool(self._a2_pull_frame_passage[env_id].item()),
                    "frame_passage_step": (
                        int(self._a2_pull_frame_passage_step[env_id].item())
                        if int(self._a2_pull_frame_passage_step[env_id].item()) >= 0
                        else None
                    ),
                    "planar_crossing": bool(self._a2_pull_planar_crossing[env_id].item()),
                    "detour": bool(self._a2_pull_detour[env_id].item()),
                    "deliberate_release": bool(
                        self._a2_pull_deliberate_release[env_id].item()
                    ),
                    "deliberate_release_step": (
                        int(self._a2_pull_deliberate_release_step[env_id].item())
                        if int(self._a2_pull_deliberate_release_step[env_id].item()) >= 0
                        else None
                    ),
                    "first_negative_x_motion_step": (
                        first_negative_step
                        if first_negative_step >= 0
                        else None
                    ),
                    "release_to_first_negative_x_motion_steps": (
                        first_negative_step - release_step
                        if release_step >= 0 and first_negative_step >= release_step
                        else None
                    ),
                    "frame_approach": bool(self._a2_pull_frame_approach[env_id].item()),
                    "frame_approach_active": bool(
                        self._a2_pull_frame_approach_active[env_id].item()
                    ),
                    "frame_approach_reward_executed": (
                        "a2_pull_frame_approach" in self.reward_scales
                    ),
                    "frame_approach_raw_last": float(
                        self._a2_pull_last_raw_reward_components.get(
                            "a2_pull_frame_approach",
                            torch.zeros(self.num_envs, device=self.device),
                        )[env_id].item()
                    ),
                    "frame_midpoint_distance_min_m": float(
                        self._a2_pull_frame_midpoint_distance_min_m[env_id].item()
                    ),
                    "panel_clear": bool(not self._a2_pull_prev_panel_contact[env_id].item()),
                    "e5_to_e7_steps": e5_to_e7_steps,
                    "swept_arc_clearance_margin_min_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_min_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_min_m[env_id]
                        )
                        else None
                    ),
                    "swept_arc_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "signed_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "base_path_length_m": float(
                        self._a2_pull_base_path_length_m[env_id].item()
                    ),
                    "base_reversal_count": int(
                        self._a2_pull_base_reversal_count[env_id].item()
                    ),
                    "post_release_recontact_count": int(
                        self._a2_pull_post_release_recontact_count[env_id].item()
                    ),
                    "corridor_door_wide_pre_aperture_steps": int(
                        self._a2_pull_corridor_door_wide_pre_aperture_steps[env_id].item()
                    ),
                    "corridor_door_wide_reward_executed": (
                        "a2_corridor_door_wide" in self.reward_scales
                    ),
                    "corridor_door_wide_raw_last": float(
                        self._a2_pull_last_raw_reward_components.get(
                            "a2_corridor_door_wide",
                            torch.zeros(self.num_envs, device=self.device),
                        )[env_id].item()
                    ),
                    "corridor_clean_passage_pre_aperture_steps": int(
                        self._a2_pull_corridor_clean_passage_pre_aperture_steps[env_id].item()
                    ),
                    "frame_approach_active_before_aperture_steps": int(
                        self._a2_pull_frame_approach_pre_aperture_steps[env_id].item()
                    ),
                    "frame_approach_active_after_frame_passage_steps": int(
                        self._a2_pull_frame_approach_post_frame_passage_steps[env_id].item()
                    ),
                    "complete_without_frame_passage": bool(
                        reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]
                        and not self._a2_pull_frame_passage[env_id].item()
                    ),
                }
                if self._is_a2_pull_v5():
                    record["pull_v5"] = {
                        "reset_source": self._a2_pull_v5_reset_source[env_id],
                        "declared_reset_source": self._a2_pull_v5_declared_reset_source[env_id],
                        "settle_valid": True,
                        "bank_settle_valid": self._get_a2_pull_v5_bank_settle_valid(env_id),
                        "hinge_drive_max_force_nm": float(
                            self.door_hinge_drive_max_force[env_id].item()
                        ),
                        "invariants": self._get_a2_pull_v5_terminal_invariants(
                            env_id, episode_record["event_reached"]
                        ),
                        "persistent_release": bool(
                            self._a2_pull_v5_persistent_release[env_id].item()
                        ),
                        "persistent_release_streak_steps": int(
                            self._a2_pull_v5_persistent_release_streak[env_id].item()
                        ),
                        "release_streak_required_steps": A2_PULL_V5_RELEASE_STREAK_STEPS,
                        "start_override_active": bool(
                            self._a2_pull_v5_start_override_active_steps[env_id].item() > 0
                        ),
                        "start_override_active_steps": int(
                            self._a2_pull_v5_start_override_active_steps[env_id].item()
                        ),
                        "start_override_base_slice_equal": bool(
                            self._a2_pull_v5_start_override_base_slice_equal[env_id].item()
                        ),
                        "passage_attempt_hinge_rad": (
                            float(self._a2_pull_passage_attempt_hinge_rad[env_id].item())
                            if torch.isfinite(self._a2_pull_passage_attempt_hinge_rad[env_id])
                            else None
                        ),
                        "intervention_active": bool(
                            self._a2_pull_v5_intervention_active[env_id].item()
                        ),
                        "intervention_fired": bool(
                            self._a2_pull_v5_intervention_fired[env_id].item()
                        ),
                        "intervention_elapsed_steps": int(
                            self._a2_pull_v5_intervention_elapsed_steps[env_id].item()
                        ),
                        "deliberate_release_semantics": "report_only_one_step_contact_transition",
                    }
                    if self.config.get("a2_pull_v5_probe_enabled", False):
                        probe_root_xy = self.simulator.robot_root_states[env_id, :2]
                        probe_root_quat_w = xyzw_to_wxyz(
                            self.simulator.robot_root_states[env_id, 3:7].unsqueeze(0)
                        )
                        _, _, probe_root_yaw = euler_xyz_from_quat(probe_root_quat_w)
                        if (
                            not torch.isfinite(self._a2_pull_v5_probe_waypoint_target_xy[env_id]).all()
                            or not torch.isfinite(self._a2_pull_v5_probe_yaw_target[env_id])
                            or not torch.isfinite(probe_root_xy).all()
                            or not torch.isfinite(probe_root_yaw).all()
                        ):
                            raise RuntimeError("Pull-v5 probe terminal telemetry requires a measured target and root pose.")
                        record["pull_v5_probe"] = {
                            "fixture": self.config["a2_pull_v5_probe_fixture"],
                            "command": self.config["a2_pull_v5_probe_command"],
                            "command_primitive": self.config["a2_pull_v5_probe_command"],
                            "sequence": self._a2_pull_v5_probe_sequence_id
                            or self.config["a2_pull_v5_probe_command"],
                            "sequence_phases": list(self._a2_pull_v5_probe_sequence_phases),
                            "sequence_phase_index": int(
                                self._a2_pull_v5_probe_phase_index[env_id].item()
                            ),
                            "sequence_complete": bool(
                                self._a2_pull_v5_probe_sequence_complete[env_id].item()
                            ),
                            "command_solvable": bool(self._a2_pull_v5_probe_solvable[env_id].item()),
                            "waypoint_arrived": bool(self._a2_pull_v5_probe_waypoint_arrived[env_id].item()),
                            "yaw_arrived": bool(self._a2_pull_v5_probe_yaw_arrived[env_id].item()),
                            "waypoint_position_error_m": float(
                                self._a2_pull_v5_probe_waypoint_error_m[env_id].item()
                            ),
                            "yaw_error_rad": float(self._a2_pull_v5_probe_yaw_error_rad[env_id].item()),
                            "anchor_pass": bool(
                                self.config["a2_pull_v5_probe_fixture"] == "anchor"
                                and self._a2_pull_v5_probe_anchor_pass[env_id].item()
                            ),
                            "requested_waypoint_xy": self._a2_pull_v5_probe_waypoint_target_xy[
                                env_id
                            ].detach().cpu().tolist(),
                            "realized_waypoint_xy": probe_root_xy.detach().cpu().tolist(),
                            "requested_base_motion_xy": self._a2_pull_v5_probe_waypoint_target_xy[
                                env_id
                            ].detach().cpu().tolist(),
                            "realized_base_motion_xy": probe_root_xy.detach().cpu().tolist(),
                            "requested_yaw_rad": float(self._a2_pull_v5_probe_yaw_target[env_id].item()),
                            "realized_yaw_rad": float(probe_root_yaw.item()),
                            "lattice_scale": float(self.config.get("a2_pull_v5_lattice_scale", 1.0)),
                        }
        return records

    def get_a2_pull_episode_records(self, env_ids, terminal_records=None) -> list[dict]:
        """Build complete E0-E7 episode summaries for terminal funnel consumers."""

        selected = (
            torch.arange(self.num_envs, dtype=torch.long, device=self.device)
            if env_ids is None
            else env_ids
        )
        if (
            not torch.is_tensor(selected)
            or selected.ndim != 1
            or selected.dtype != torch.long
            or selected.device != torch.device(self.device)
            or torch.any(selected < 0)
            or torch.any(selected >= self.num_envs)
        ):
            raise RuntimeError("Pull episode diagnostics requires valid device-local env ids.")
        if terminal_records is not None and len(terminal_records) != len(selected):
            raise RuntimeError("Pull terminal records and episode ids must have equal length.")
        dt = float(self.dt)
        if not math.isfinite(dt) or dt <= 0.0:
            raise RuntimeError(f"Pull episode diagnostics requires positive finite dt; got {dt!r}.")
        threshold_mode = self._get_a2_pull_threshold_mode()
        records: list[dict] = []
        for record_index, env_id in enumerate(selected.tolist()):
            reached = {
                event.name: bool(self._a2_pull_event_reached[env_id, event].item())
                for event in A2PullEvent
            }
            first_steps = {
                event.name: (
                    int(self._a2_pull_first_event_step[env_id, event].item())
                    if reached[event.name]
                    else A2_PULL_NA
                )
                for event in A2PullEvent
            }
            first_times = {
                event.name: (
                    float(self._a2_pull_first_event_time_s[env_id, event].item())
                    if reached[event.name]
                    else A2_PULL_NA
                )
                for event in A2PullEvent
            }
            terminal_reason = (
                terminal_records[record_index].get("terminal_reason", "UNKNOWN")
                if terminal_records is not None
                else "UNKNOWN"
            )
            if not isinstance(terminal_reason, str) or not terminal_reason:
                raise RuntimeError("Pull terminal reason must be a non-empty string.")
            e2 = reached[A2PullEvent.E2_TENSILE_CAPTURE.name]
            e4 = reached[A2PullEvent.E4_POSITIVE_HINGE_RETAINED.name]
            e5 = reached[A2PullEvent.E5_CLEARANCE_DECISION.name]
            e6 = reached[A2PullEvent.E6_PATH_REVERSAL_ENTRY.name]
            record = {
                "event_reached": reached,
                "first_event_step": first_steps,
                "first_event_time_s": first_times,
                "proof_hold_duration_s": float(self._a2_pull_proof_duration_s[env_id].item())
                if e2
                else A2_PULL_NA,
                "proof_retreat_displacement_m": float(
                    self._a2_pull_proof_displacement_m[env_id].item()
                )
                if e2
                else A2_PULL_NA,
                "max_tensile_retreat_before_loss_m": float(
                    self._a2_pull_max_tensile_retreat_m[env_id].item()
                )
                if e2
                else A2_PULL_NA,
                "hinge_at_first_positive_progress_rad": float(
                    self._a2_pull_hinge_at_first_positive_progress_rad[env_id].item()
                )
                if torch.isfinite(
                    self._a2_pull_hinge_at_first_positive_progress_rad[env_id]
                )
                else A2_PULL_NA,
                "hinge_at_first_grip_loss_rad": A2_PULL_NA,
                "held_hinge_max_rad": float(self._a2_pull_held_hinge_max_rad[env_id].item())
                if torch.isfinite(self._a2_pull_held_hinge_max_rad[env_id])
                else A2_PULL_NA,
                "hinge_at_release_or_hold_decision_rad": float(
                    self._a2_pull_hinge_at_decision_rad[env_id].item()
                )
                if e4 and torch.isfinite(self._a2_pull_hinge_at_decision_rad[env_id])
                else A2_PULL_NA,
                "root_outward_excursion_before_clear_m": float(
                    self._a2_pull_root_outward_excursion_m[env_id].item()
                )
                if e5
                else A2_PULL_NA,
                "first_path_reversal_step": int(
                    self._a2_pull_first_path_reversal_step[env_id].item()
                )
                if e6 and int(self._a2_pull_first_path_reversal_step[env_id].item()) >= 0
                else A2_PULL_NA,
                "release_to_whole_body_clear_s": (
                    float(
                        self._a2_pull_first_event_time_s[
                            env_id, A2PullEvent.E7_WHOLE_BODY_CLEAR
                        ].item()
                        - self._a2_pull_first_event_time_s[
                            env_id, A2PullEvent.E5_CLEARANCE_DECISION
                        ].item()
                    )
                    if reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name] and e5
                    else A2_PULL_NA
                ),
                "hinge_reclosure_after_release_rad": A2_PULL_NA,
                "body_panel_contact_steps_per_20s": int(
                    self._a2_pull_body_panel_contact_steps[env_id].item()
                ),
                "body_panel_contact_impulse_Ns": float(
                    self._a2_pull_body_panel_contact_impulse_ns[env_id].item()
                ),
                "crossing_while_valid_capture": bool(
                    e5
                    and self._a2_pull_capture_valid[env_id].item()
                    and self._a2_pull_event_reached[
                        env_id, A2PullEvent.E6_PATH_REVERSAL_ENTRY
                    ].item()
                ),
                "whole_body_clear": reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name],
                "terminal_reason": terminal_reason,
                "spawn_hook": bool(self.door_spawn_hook[env_id].item()),
                "hinge_drive_max_force_nm": float(self.door_hinge_drive_max_force[env_id].item()),
            }
            validate_a2_pull_episode(
                record,
                event_predecessors=(
                    A2_PULL_HARD_GATE_EVENT_PREDECESSORS
                    if threshold_mode == "hard_gate"
                    else None
                ),
            )
            if self._is_a2_pull_v5():
                record["pull_v5"] = {
                    "reset_source": self._a2_pull_v5_reset_source[env_id],
                    "declared_reset_source": self._a2_pull_v5_declared_reset_source[env_id],
                    "settle_valid": True,
                    "bank_settle_valid": self._get_a2_pull_v5_bank_settle_valid(env_id),
                    "hinge_drive_max_force_nm": float(
                        self.door_hinge_drive_max_force[env_id].item()
                    ),
                    "invariants": self._get_a2_pull_v5_terminal_invariants(env_id, reached),
                    "persistent_release": bool(
                        self._a2_pull_v5_persistent_release[env_id].item()
                    ),
                    "persistent_release_streak_steps": int(
                        self._a2_pull_v5_persistent_release_streak[env_id].item()
                    ),
                    "release_streak_required_steps": A2_PULL_V5_RELEASE_STREAK_STEPS,
                    "start_override_active": bool(
                        self._a2_pull_v5_start_override_active_steps[env_id].item() > 0
                    ),
                    "start_override_active_steps": int(
                        self._a2_pull_v5_start_override_active_steps[env_id].item()
                    ),
                    "start_override_base_slice_equal": bool(
                        self._a2_pull_v5_start_override_base_slice_equal[env_id].item()
                    ),
                    "passage_attempt_hinge_rad": (
                        float(self._a2_pull_passage_attempt_hinge_rad[env_id].item())
                        if torch.isfinite(self._a2_pull_passage_attempt_hinge_rad[env_id])
                        else None
                    ),
                    "deliberate_release_semantics": "report_only_one_step_contact_transition",
                }
            records.append(record)
        return records

    def _get_a2_pull_pd_effort_telemetry(self) -> dict[str, torch.Tensor]:
        robot = self.simulator.scene.articulations["robot"]
        data = robot.data
        ordered_joint_ids = torch.tensor(
            self.simulator.dof_ids,
            dtype=torch.long,
            device=self.device,
        )
        field_values = {
            "joint_pos": data.joint_pos,
            "joint_vel": data.joint_vel,
            "joint_pos_target": data.joint_pos_target,
            "joint_stiffness": data.joint_stiffness,
            "joint_damping": data.joint_damping,
            "joint_effort_limits": data.joint_effort_limits,
        }
        articulation_joint_count = data.joint_pos.shape[1]
        for field_name, value in field_values.items():
            if (
                not torch.is_tensor(value)
                or value.shape != (self.num_envs, articulation_joint_count)
                or not torch.all(torch.isfinite(value))
            ):
                shape = None if not torch.is_tensor(value) else tuple(value.shape)
                raise RuntimeError(
                    f"Pull PD telemetry requires finite Articulation.data.{field_name} "
                    f"shape ({self.num_envs}, {articulation_joint_count}); got {shape}."
                )
        ordered = {
            name: value[:, ordered_joint_ids]
            for name, value in field_values.items()
        }

        def estimate(indices: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            unclipped, clipped, _saturated = a2_hold_pd_effort_estimates(
                ordered["joint_pos"][:, indices],
                ordered["joint_vel"][:, indices],
                ordered["joint_pos_target"][:, indices],
                ordered["joint_stiffness"][:, indices],
                ordered["joint_damping"][:, indices],
                ordered["joint_effort_limits"][:, indices],
            )
            utilization = torch.abs(clipped) / ordered["joint_effort_limits"][:, indices]
            if not torch.all(torch.isfinite(unclipped)) or not torch.all(torch.isfinite(utilization)):
                raise RuntimeError("Pull PD effort telemetry produced non-finite estimates.")
            return clipped, utilization

        finger_effort, finger_utilization = estimate(self._a2_gripper_dof_indices)
        _arm_effort, arm_utilization = estimate(self._a2_arm_dof_indices)
        return {
            "finger_effort": finger_effort,
            "finger_utilization": finger_utilization,
            "arm_utilization": arm_utilization,
        }

    def get_a2_pull_control_step_telemetry(self, env_ids=None) -> list[dict]:
        """Return schema-validated records after the current reward step."""

        selected = (
            torch.arange(self.num_envs, dtype=torch.long, device=self.device)
            if env_ids is None
            else env_ids
        )
        if (
            not torch.is_tensor(selected)
            or selected.ndim != 1
            or selected.dtype != torch.long
            or selected.device != torch.device(self.device)
            or torch.any(selected < 0)
            or torch.any(selected >= self.num_envs)
        ):
            raise RuntimeError("Pull control-step telemetry requires valid env ids.")
        if not self._a2_pull_last_raw_reward_components:
            raise RuntimeError("Pull control-step telemetry must be collected after reward computation.")

        root_states = self.simulator.robot_root_states
        door_states = self.simulator.get_task_root_state("door")
        root_x = root_states[:, 0]
        door_x = door_states[:, 0]
        root_x_rel = root_x - door_x
        root_velocity_x = root_states[:, 7]
        frame_midpoint_xy = self._get_a2_pull_door_frame_midpoint(door_states)
        frame_delta_xy = frame_midpoint_xy - root_states[:, 0:2]
        frame_midpoint_distance = torch.linalg.vector_norm(frame_delta_xy, dim=-1)
        _, _, root_yaw = euler_xyz_from_quat(root_states[:, 3:7])
        _, _, door_yaw = euler_xyz_from_quat(door_states[:, 3:7])
        expected_approach_yaw = (1.0 + self._pull_direction.io_sign) * 0.5 * math.pi
        root_yaw_error = torch.abs(wrap_to_pi(root_yaw - door_yaw - expected_approach_yaw))
        door_joint_pos = self._get_door_joint_pos("pull control-step telemetry", 3)
        door_joint_vel = self._get_door_joint_vel("pull control-step telemetry", 3)
        frame_data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = frame_data.target_pos_source[:, 0, :]
        target_quat_source = frame_data.target_quat_source[:, 0, :]
        target_position_error = torch.linalg.norm(target_pos_source, dim=-1)
        target_orientation_error = torch.linalg.norm(
            axis_angle_from_quat(target_quat_source), dim=-1
        )
        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "pull control-step telemetry"
        )
        stable_contact_current = contact_masks["both_contact"] & (
            self._get_a2_stage2_contact_stability_mask()
            | self._get_a2_hold_streak_ok_mask()
        )
        aperture_ready_current = stable_contact_current & (
            door_joint_pos[:, 0] >= self._get_a2_v20_send_hinge_threshold()
        )
        body_panel_forces, body_panel_total = self._get_a2_door_body_panel_contact_forces()
        arm_panel_forces, arm_panel_total = self._get_a2_door_arm_panel_contact_forces()
        body_frame_forces, _ = self._get_a2_door_panel_contact_force_components(
            self.A2_PULL_DOOR_BODY_FRAME_CONTACT_SENSOR,
            self.A2_DOOR_BODY_PANEL_FILTER_NAMES,
            "pull door-body frame contact",
        )
        arm_frame_forces, _ = self._get_a2_door_panel_contact_force_components(
            self.A2_PULL_DOOR_ARM_FRAME_CONTACT_SENSOR,
            self.A2_DOOR_ARM_PANEL_FILTER_NAMES,
            "pull door-arm frame contact",
        )
        effort = self._get_a2_pull_pd_effort_telemetry()
        event_states = a2_pull_event_state_names(
            self._a2_pull_event_reached,
            event_predecessors=(
                A2_PULL_HARD_GATE_EVENT_PREDECESSORS
                if self._get_a2_pull_threshold_mode() == "hard_gate"
                else None
            ),
        )
        panel_names = (
            *self.A2_DOOR_BODY_PANEL_FILTER_NAMES,
            *self.A2_DOOR_ARM_PANEL_FILTER_NAMES,
        )
        corridor_wide_raw_component = self._a2_pull_last_raw_reward_components.get(
            "a2_corridor_door_wide",
            torch.zeros(self.num_envs, device=self.device),
        )
        frame_approach_raw_component = self._a2_pull_last_raw_reward_components.get(
            "a2_pull_frame_approach",
            torch.zeros(self.num_envs, device=self.device),
        )
        records = []
        for env_id in selected.tolist():
            panel_values = torch.cat(
                (body_panel_forces[env_id], arm_panel_forces[env_id])
            ).detach().cpu().tolist()
            frame_values = torch.cat(
                (body_frame_forces[env_id], arm_frame_forces[env_id])
            ).detach().cpu().tolist()
            slip = (
                self._a2_pull_handle_local_slip_xyz_mps[env_id].detach().cpu().tolist()
                if bool(self._a2_pull_handle_local_slip_valid[env_id].item())
                else A2_PULL_NA
            )
            record = {
                "door_open_io_sign": self._pull_direction.io_sign,
                "door_open_lr_sign": self._pull_direction.door_open_lr_sign,
                "active_handle_face_x_sign": self._pull_direction.active_handle_face_x,
                "travel_dir_x": self._pull_direction.travel_dir_x,
                "stage": int(self.stage_buf[env_id].item()),
                "event_state": event_states[env_id],
                "root_x_rel_door_m": float(root_x_rel[env_id].item()),
                "signed_crossing_progress_m": float(
                    self._pull_direction.signed_crossing_progress(
                        root_x[env_id], door_x[env_id]
                    ).item()
                ),
                "root_velocity_toward_door_mps": float(
                    self._pull_direction.signed_velocity_toward_door(
                        root_velocity_x[env_id]
                    ).item()
                ),
                "root_velocity_yield_outward_mps": float(
                    self._pull_direction.signed_velocity_yield_outward(
                        root_velocity_x[env_id]
                    ).item()
                ),
                "root_velocity_final_travel_mps": float(
                    (self._pull_direction.travel_dir_x * root_velocity_x[env_id]).item()
                ),
                "root_yaw_error_rad": float(root_yaw_error[env_id].item()),
                "handle_position_rad": float(door_joint_pos[env_id, 1].item()),
                "handle_velocity_radps": float(door_joint_vel[env_id, 1].item()),
                "latch_position_m": float(door_joint_pos[env_id, 2].item()),
                "hinge_position_rad": float(door_joint_pos[env_id, 0].item()),
                "hinge_velocity_radps": float(door_joint_vel[env_id, 0].item()),
                "target_tcp_position_error_m": float(target_position_error[env_id].item()),
                "target_tcp_orientation_error_rad": float(
                    target_orientation_error[env_id].item()
                ),
                "bilateral_handle_contact": bool(
                    contact_masks["both_contact"][env_id].item()
                ),
                "hook_contact": A2_PULL_NA,
                "handle_local_slip_xyz_mps": slip,
                "gripper_handle_separation_m": float(target_position_error[env_id].item()),
                "finger_pd_effort_estimate_N": {
                    "value": effort["finger_effort"][env_id].detach().cpu().tolist(),
                    "provenance": A2_PULL_ESTIMATE_ONLY,
                },
                "finger_effort_utilization_estimate": {
                    "value": effort["finger_utilization"][env_id].detach().cpu().tolist(),
                    "provenance": A2_PULL_ESTIMATE_ONLY,
                },
                "arm_pd_effort_utilization_estimate": {
                    "value": effort["arm_utilization"][env_id].detach().cpu().tolist(),
                    "provenance": A2_PULL_ESTIMATE_ONLY,
                },
                "panel_contact_force_by_body_N": dict(zip(panel_names, panel_values)),
                "frame_contact_force_by_body_N": dict(zip(panel_names, frame_values)),
                "minimum_panel_robot_clearance_m": (
                    float(self._a2_pull_minimum_panel_robot_clearance_m[env_id].item())
                    if bool(
                        torch.isfinite(
                            self._a2_pull_minimum_panel_robot_clearance_m[env_id]
                        ).item()
                    )
                    else A2_PULL_NA
                ),
                "reward_component_raw": {
                    name: float(value[env_id].item())
                    for name, value in self._a2_pull_last_raw_reward_components.items()
                },
            }
            validate_a2_pull_control_step(record)
            if self._is_a2_pull_v5():
                record["pull_v5"] = {
                    "reset_source": self._a2_pull_v5_reset_source[env_id],
                    "declared_reset_source": self._a2_pull_v5_declared_reset_source[env_id],
                    "persistent_release": bool(
                        self._a2_pull_v5_persistent_release[env_id].item()
                    ),
                    "persistent_release_streak_steps": int(
                        self._a2_pull_v5_persistent_release_streak[env_id].item()
                    ),
                    "release_streak_required_steps": A2_PULL_V5_RELEASE_STREAK_STEPS,
                    "start_override_active": bool(
                        self._a2_pull_v5_start_override_active[env_id].item()
                    ),
                    "start_override_active_steps": int(
                        self._a2_pull_v5_start_override_active_steps[env_id].item()
                    ),
                    "start_override_base_slice_equal": bool(
                        self._a2_pull_v5_start_override_base_slice_equal[env_id].item()
                    ),
                    "passage_attempt_hinge_rad": (
                        float(self._a2_pull_passage_attempt_hinge_rad[env_id].item())
                        if torch.isfinite(self._a2_pull_passage_attempt_hinge_rad[env_id])
                        else None
                    ),
                    "intervention_active": bool(
                        self._a2_pull_v5_intervention_active[env_id].item()
                    ),
                    "intervention_elapsed_steps": int(
                        self._a2_pull_v5_intervention_elapsed_steps[env_id].item()
                    ),
                }
                if self.config.get("a2_pull_v5_probe_enabled", False):
                    record["pull_v5_probe"] = {
                        "fixture": self.config["a2_pull_v5_probe_fixture"],
                        "command": self.config["a2_pull_v5_probe_command"],
                        "command_primitive": self.config["a2_pull_v5_probe_command"],
                        "sequence": self._a2_pull_v5_probe_sequence_id
                        or self.config["a2_pull_v5_probe_command"],
                        "sequence_phases": list(self._a2_pull_v5_probe_sequence_phases),
                        "sequence_phase_index": int(
                            self._a2_pull_v5_probe_phase_index[env_id].item()
                        ),
                        "sequence_complete": bool(
                            self._a2_pull_v5_probe_sequence_complete[env_id].item()
                        ),
                    }
            record["pull_v2_unlatch"] = {
                "stable_unlatch_handle_based": bool(
                    self._a2_pull_stable_unlatch_handle_ever[env_id].item()
                ),
                "stable_unlatch_latch_based": bool(
                    self._a2_pull_stable_unlatch_latch_ever[env_id].item()
                ),
                "relock_handle_based": bool(self._a2_pull_relock_handle_ever[env_id].item()),
                "relock_latch_based": bool(self._a2_pull_relock_latch_ever[env_id].item()),
                "handle_unlatch_threshold_rad": 0.3,
                "latch_unlatch_threshold_m": self._get_a2_pull_e3_latch_threshold_m(),
                "relock_definition": (
                    "prior stable threshold crossing, then threshold loss while "
                    "hinge remains below the Stage3-to4 gate"
                ),
            }
            if self._is_a2_pull_traversal():
                frame_approach_current = bool(
                    (abs(float(frame_delta_xy[env_id, 0].item())) < 0.3)
                    and (
                        abs(float(frame_delta_xy[env_id, 1].item()))
                        <= 0.5 * float(self.door_width[env_id].item())
                    )
                )
                panel_clear_current = bool(
                    (body_panel_total[env_id] + arm_panel_total[env_id]).item() == 0.0
                )
                frame_passage_current = bool(
                    frame_approach_current and panel_clear_current
                )
                planar_crossing_current = bool(
                    self._pull_direction.signed_crossing_progress(
                        root_x[env_id], door_x[env_id]
                    ).item()
                    > 0.0
                )
                corridor_wide_raw = self._a2_pull_last_raw_reward_components[
                    "a2_corridor_door_wide"
                ][env_id] if "a2_corridor_door_wide" in self._a2_pull_last_raw_reward_components else corridor_wide_raw_component[env_id]
                corridor_clean_raw = self._a2_pull_last_raw_reward_components[
                    "a2_corridor_clean_passage"
                ][env_id]
                frame_approach_raw = frame_approach_raw_component[env_id]
                current_step = int(self.episode_length_buf[env_id].item())
                release_step = int(self._a2_pull_deliberate_release_step[env_id].item())
                record["pull_v3_traversal"] = {
                    "aperture_ready": bool(self._a2_pull_aperture_ready[env_id].item()),
                    "aperture_ready_current": bool(aperture_ready_current[env_id].item()),
                    "frame_approach": bool(self._a2_pull_frame_approach[env_id].item()),
                    "frame_approach_current": frame_approach_current,
                    "frame_approach_active": bool(
                        self._a2_pull_frame_approach_active[env_id].item()
                    ),
                    "frame_approach_reward_executed": (
                        "a2_pull_frame_approach" in self.reward_scales
                    ),
                    "frame_approach_raw": float(frame_approach_raw.item()),
                    "frame_midpoint_distance_m": float(
                        frame_midpoint_distance[env_id].item()
                    ),
                    "frame_midpoint_distance_min_m": float(
                        self._a2_pull_frame_midpoint_distance_min_m[env_id].item()
                    ),
                    "frame_passage": bool(self._a2_pull_frame_passage[env_id].item()),
                    "frame_passage_current": frame_passage_current,
                    "planar_crossing": bool(self._a2_pull_planar_crossing[env_id].item()),
                    "planar_crossing_current": planar_crossing_current,
                    "detour": bool(self._a2_pull_detour[env_id].item()),
                    "detour_current": planar_crossing_current
                    and not bool(self._a2_pull_frame_passage[env_id].item()),
                    "deliberate_release": bool(
                        self._a2_pull_deliberate_release[env_id].item()
                    ),
                    "deliberate_release_current": release_step == current_step,
                    "panel_clear": panel_clear_current,
                    "panel_contact_ever": bool(
                        self._a2_pull_body_panel_contact_steps[env_id].item() > 0
                    ),
                    "bilateral_handle_contact": bool(
                        contact_masks["both_contact"][env_id].item()
                    ),
                    "no_handle_contact": bool(
                        (~torch.any(contact_masks["contacting"][env_id])).item()
                    ),
                    "minimum_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "swept_arc_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "signed_clearance_margin_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_current_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_current_m[env_id]
                        )
                        else None
                    ),
                    "swept_arc_clearance_margin_min_m": (
                        float(self._a2_pull_swept_arc_clearance_margin_min_m[env_id].item())
                        if torch.isfinite(
                            self._a2_pull_swept_arc_clearance_margin_min_m[env_id]
                        )
                        else None
                    ),
                    "base_path_length_m": float(
                        self._a2_pull_base_path_length_m[env_id].item()
                    ),
                    "base_reversal_count": int(
                        self._a2_pull_base_reversal_count[env_id].item()
                    ),
                    "post_release_recontact_count": int(
                        self._a2_pull_post_release_recontact_count[env_id].item()
                    ),
                    "corridor_door_wide_raw": float(corridor_wide_raw.item()),
                    "corridor_clean_passage_raw": float(corridor_clean_raw.item()),
                    "corridor_door_wide_raw_component": float(corridor_wide_raw.item()),
                    "corridor_door_wide_reward_executed": (
                        "a2_corridor_door_wide" in self.reward_scales
                    ),
                    "corridor_clean_passage_raw_component": float(corridor_clean_raw.item()),
                    "corridor_door_wide_pre_aperture_steps": int(
                        self._a2_pull_corridor_door_wide_pre_aperture_steps[env_id].item()
                    ),
                    "corridor_clean_passage_pre_aperture_steps": int(
                        self._a2_pull_corridor_clean_passage_pre_aperture_steps[env_id].item()
                    ),
                }
            records.append(record)
        return records

    @override
    def scene_creation_callback(self, simulator):
        result = super().scene_creation_callback(simulator)
        target_obj = simulator.task_config.get("target_obj")
        if not isinstance(target_obj, str) or not target_obj:
            raise RuntimeError("Pull frame telemetry requires task.target_obj.")
        body_filters = tuple(
            f"/World/envs/env_.*/Robot/{body_name}"
            for body_name in self.A2_DOOR_BODY_PANEL_FILTER_NAMES
        )
        arm_filters = tuple(
            f"/World/envs/env_.*/Robot/{body_name}"
            for body_name in self.A2_DOOR_ARM_PANEL_FILTER_NAMES
        )
        simulator.scene.sensors[self.A2_PULL_DOOR_BODY_FRAME_CONTACT_SENSOR] = ContactSensor(
            ContactSensorCfg(
                prim_path=f"/World/envs/env_.*/{target_obj}/root",
                filter_prim_paths_expr=body_filters,
            )
        )
        simulator.scene.sensors[self.A2_PULL_DOOR_ARM_FRAME_CONTACT_SENSOR] = ContactSensor(
            ContactSensorCfg(
                prim_path=f"/World/envs/env_.*/{target_obj}/root",
                filter_prim_paths_expr=arm_filters,
            )
        )
        return result

    @override
    def _reset_root_states(self, env_ids, target_root_states=None):
        if not self._use_a2_base:
            raise RuntimeError("DoorOpenA2Pull requires env.config.a2_base.enabled=true.")
        if target_root_states is not None:
            return A2Base._reset_root_states(self, env_ids, target_root_states)

        self.target_robot_root_states[env_ids] = self.base_init_state
        self.target_robot_root_states[env_ids, :3] += self.env_origins[env_ids]
        self.target_robot_root_states[env_ids, 0:1] = (
            self._pull_direction.approach_side_x
            * torch_rand_float(0.6, 1.5, (len(env_ids), 1), device=str(self.device))
            + self.env_origins[env_ids, 0:1]
        )
        self.target_robot_root_states[env_ids, 1:2] = (
            torch_rand_float(-0.5, 0.5, (len(env_ids), 1), device=str(self.device))
            + self.env_origins[env_ids, 1:2]
        )
        roll, pitch, _yaw = euler_xyz_from_quat(self.target_robot_root_states[env_ids, 3:7])
        initial_yaw = self.config.get("a2_pull_robot_initial_yaw_rad")
        if (
            isinstance(initial_yaw, bool)
            or not isinstance(initial_yaw, (int, float))
            or not math.isfinite(float(initial_yaw))
        ):
            raise RuntimeError(
                "a2_pull_robot_initial_yaw_rad must be a finite configured float."
            )
        random_yaw = torch.full(
            (len(env_ids),), float(initial_yaw), device=self.device, dtype=roll.dtype
        )
        self.target_robot_root_states[env_ids, 3:7] = quat_from_euler_xyz(
            roll,
            pitch,
            random_yaw,
        )
        self.target_robot_root_states[env_ids, 7:13] = 0.0

    @override
    def _record_a2_stage0_to1_staging_standoff(
        self,
        advance_mask: torch.Tensor,
        grasp_target: torch.Tensor,
        root_pos: torch.Tensor,
    ) -> None:
        valid = self._a2_stage0_to1_staging_valid
        standoff_buffer = self._a2_stage0_to1_staging_standoff
        expected_shape = (self.num_envs,)
        if (
            advance_mask.shape != expected_shape
            or advance_mask.dtype != torch.bool
            or valid.shape != expected_shape
            or valid.dtype != torch.bool
            or standoff_buffer.shape != expected_shape
            or advance_mask.device != torch.device(self.device)
            or valid.device != advance_mask.device
            or standoff_buffer.device != advance_mask.device
        ):
            raise RuntimeError("Pull-v0 staging telemetry requires device-local vector buffers.")
        signed_standoff = self._pull_direction.approach_side_x * (
            root_pos[:, 0] - grasp_target[:, 0]
        )
        if not torch.all(torch.isfinite(signed_standoff)):
            raise RuntimeError("Pull-v0 signed staging standoff must be finite.")
        first_advance = advance_mask & ~valid
        standoff_buffer[first_advance] = signed_standoff[first_advance]
        valid[first_advance] = True

    @StagedTaskBase.effective_in_stage(DoorPregrasp.STAGE_WALK_TO_DOOR)
    def _reward_walk_to_door(self):
        current_root_pos = self.simulator.robot_root_states[:, :3].clone()
        grasp_target_pos = self._compute_grasp_target().clone()
        x_min, x_max, y_tol = self._get_a2_stage0_staging_band()
        stage0_target_pos = a2_signed_stage0_nearest_staging_target(
            current_root_pos,
            grasp_target_pos,
            x_min,
            x_max,
            y_tol,
            self._pull_direction,
        )
        target_direction = stage0_target_pos - current_root_pos
        target_distance = torch.linalg.norm(target_direction, dim=-1, keepdim=True)
        nonzero_distance = target_distance > 0.0
        target_dir = torch.where(
            nonzero_distance,
            target_direction / torch.where(
                nonzero_distance,
                target_distance,
                torch.ones_like(target_distance),
            ),
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

    @override
    def _stage_0_to_1_advance_condition(self):
        grasp_target = self._compute_grasp_target()
        root_pos = self.simulator.robot_root_states[:, :3]
        x_min, x_max, y_tol = self._get_a2_stage0_staging_band()
        condition = a2_signed_stage0_staging_band_mask(
            root_pos,
            grasp_target,
            x_min,
            x_max,
            y_tol,
            self._pull_direction,
        )
        arm_target_pos = self._get_a2_arm_default_dof_pos()
        arm_max_deviation = self._get_required_positive_float_config(
            "a2_stage0_arm_default_max_deviation",
            "pull stage0->1 arm default transition",
        )
        max_deviation = (
            torch.abs(
                self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx] - arm_target_pos
            )
            .max(dim=-1)
            .values
        )
        condition &= max_deviation < arm_max_deviation
        base_command = self.get_physical_homie_commands()
        if (
            not torch.is_tensor(base_command)
            or base_command.shape != (self.num_envs, 5)
            or base_command.device != torch.device(self.device)
            or not torch.all(torch.isfinite(base_command))
        ):
            raise RuntimeError(
                "Pull stage0->1 base-still gate requires finite physical commands "
                f"shape ({self.num_envs}, 5) on {self.device}."
            )
        condition &= torch.norm(base_command[:, :3], dim=1) <= 0.1
        self._record_a2_stage0_to1_staging_standoff(condition, grasp_target, root_pos)
        return condition

    @StagedTaskBase.effective_in_stage(
        [DoorPregrasp.STAGE_PREGRASP, DoorPregrasp.STAGE_GRASP]
    )
    def _reward_penalty_a2_stage1_stage2_base_forward_creep(self):
        deadband = self._get_required_positive_float_config(
            "a2_stage1_stage2_base_forward_creep_deadband",
            "pull stage1/stage2 base creep",
        )
        scale = self._get_required_positive_float_config(
            "a2_stage1_stage2_base_forward_creep_scale",
            "pull stage1/stage2 base creep",
        )
        grasp_target = self._compute_grasp_target()
        x_min, _x_max, _y_tol = self._get_a2_stage0_staging_band()
        near_boundary_x = (
            grasp_target[:, 0] + self._pull_direction.approach_side_x * x_min
        )
        root_x = self.simulator.robot_root_states[:, 0]
        penetration_toward_door = self._pull_direction.travel_dir_x * (
            root_x - near_boundary_x
        )
        return ((penetration_toward_door - deadband) / scale).clamp(0.0, 1.0)

    @StagedTaskBase.effective_in_stage(
        [
            DoorPregrasp.STAGE_WALK_TO_DOOR,
            DoorPregrasp.STAGE_PREGRASP,
            DoorPregrasp.STAGE_GRASP,
        ]
    )
    def _reward_penalty_face_door(self):
        relative_door_quat = xyzw_to_wxyz(self.relative_door_rot_buf)
        zeros = torch.zeros(self.num_envs, device=self.device)
        desired_relative_quat = quat_from_euler_xyz(
            zeros,
            zeros,
            torch.full_like(zeros, math.pi),
        )
        orientation_error = quat_mul(quat_inv(desired_relative_quat), relative_door_quat)
        return wrap_to_pi(axis_angle_from_quat(orientation_error).norm(dim=-1))

    @StagedTaskBase.effective_in_stage(
        [DoorPregrasp.STAGE_OPEN, DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH]
    )
    def _reward_pull_door_handle(self):
        handle_velocity = self.simulator.scene.articulations["door"].data.joint_vel[:, 1]
        handle_position = (
            self.simulator.scene.articulations["door"]
            .data.joint_pos[:, 1]
            .clamp(min=0.0, max=0.785398)
            / 0.785398
        )
        reward = (handle_velocity + handle_position).clamp(max=1.0, min=-1.0)
        return reward * self._get_a2_pull_load_bearing_income_mask().float()

    @StagedTaskBase.effective_in_stage(
        [DoorPregrasp.STAGE_OPEN, DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH]
    )
    def _reward_pull_door_hinge(self):
        hinge_velocity = self.simulator.scene.articulations["door"].data.joint_vel[:, 0] * 10.0
        hinge_position = (
            self.simulator.scene.articulations["door"]
            .data.joint_pos[:, 0]
            .clamp(min=0.0, max=1.5708)
            / 1.5708
        )
        income_mask = (
            self._get_a2_stage34_hold_income_mask()
            & self._get_a2_pull_load_bearing_income_mask()
        )
        reward = (hinge_velocity + hinge_position).clamp(max=1.0, min=-1.0)
        return reward * income_mask.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_OPEN, DoorPregrasp.STAGE_SWING])
    @override
    def _reward_penalty_a2_stage3_stage4_open_command(self):
        if not self._is_a2_pull_traversal():
            return super()._reward_penalty_a2_stage3_stage4_open_command()
        primitive = self._get_a2_gripper_primitive_raw_column(
            "pull-v3 penalty_a2_stage3_stage4_open_command"
        )
        reward = ((primitive - 0.2) / 0.8).clamp(0.0, 1.0)
        pull_v3_hold_mask = (self.stage_buf == self.STAGE_OPEN) | (
            (self.stage_buf == self.STAGE_SWING) & ~self._a2_pull_aperture_ready
        )
        return reward * pull_v3_hold_mask.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    @override
    def _reward_a2_corridor_door_wide(self):
        if not self._is_a2_pull_traversal():
            return super()._reward_a2_corridor_door_wide()
        door_joint_pos = self._get_door_joint_pos("pull-v3 corridor door-wide reward", 1)
        door_states = self.simulator.get_task_root_state("door")
        whole_body_clear = self._get_a2_pull_whole_body_clear_mask(door_states[:, 0])
        return (
            (door_joint_pos[:, 0] / 1.5).clamp(0.0, 1.0)
            * self._a2_pull_aperture_ready.float()
            * (~whole_body_clear).float()
        )

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    def _reward_a2_pull_frame_approach(self):
        frame_midpoint_xy = self._get_a2_pull_door_frame_midpoint(
            self.simulator.get_task_root_state("door")
        )
        root_states = self.simulator.robot_root_states
        delta_xy = frame_midpoint_xy - root_states[:, 0:2]
        distance = torch.linalg.vector_norm(delta_xy, dim=-1, keepdim=True)
        if not torch.all(torch.isfinite(distance)) or torch.any(distance <= 0.0):
            raise RuntimeError(
                "Pull v4 frame-approach reward requires a finite nonzero root-to-frame-midpoint distance."
            )
        toward = delta_xy / distance
        v_toward = torch.sum(root_states[:, 7:9] * toward, dim=-1)
        raw = (v_toward / 0.3).clamp(-1.0, 1.0)
        active = self._get_a2_pull_frame_approach_active_mask()
        self._a2_pull_frame_approach_active[:] = active
        return raw * active.float()

    @StagedTaskBase.effective_in_stage([DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH])
    @override
    def _reward_a2_corridor_clean_passage(self):
        if not self._is_a2_pull_traversal():
            return super()._reward_a2_corridor_clean_passage()
        _body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
        _arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
        no_panel_contact = (body_total + arm_total) == 0.0
        return self._a2_pull_aperture_ready.float() * no_panel_contact.float()

    @override
    def _stage_2_to_3_advance_condition(self):
        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "pull stage2 to stage3 advance"
        )
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E2_TENSILE_CAPTURE]
            & self._a2_pull_proof_valid
            & contact_masks["both_contact"]
        )

    @override
    def _stage_3_to_4_advance_condition(self):
        threshold_mode = self._get_a2_pull_threshold_mode()
        if threshold_mode == "hard_gate":
            body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
            arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
            del body_forces, arm_forces
            panel_clear = (body_total + arm_total) == 0.0
            return super()._stage_3_to_4_advance_condition() & panel_clear
        contact_masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
            "pull stage3 to stage4 advance"
        )
        body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
        arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
        del body_forces, arm_forces
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E4_POSITIVE_HINGE_RETAINED]
            & contact_masks["both_contact"]
            & ((body_total + arm_total) == 0.0)
        )

    @StagedTaskBase.effective_in_stage(
        [DoorPregrasp.STAGE_SWING, DoorPregrasp.STAGE_THROUGH]
    )
    @override
    def _reward_target_root_distance(self):
        reward = super()._reward_target_root_distance()
        if self._get_a2_pull_threshold_mode() == "hard_gate":
            return torch.where(
                self._a2_pull_aperture_ready,
                reward,
                torch.zeros_like(reward),
            )
        measured_e5 = (
            self._a2_pull_event_reached[:, A2PullEvent.E5_CLEARANCE_DECISION]
            & self._a2_pull_clearance_ready
        )
        return torch.where(measured_e5, reward, torch.zeros_like(reward))

    @override
    def _stage_4_to_5_advance_condition(self):
        door_states = self.simulator.get_task_root_state("door")
        root_states = self.simulator.robot_root_states
        signed_crossing = self._pull_direction.signed_crossing_progress(
            root_states[:, 0], door_states[:, 0]
        )
        body_forces, body_total = self._get_a2_door_body_panel_contact_forces()
        arm_forces, arm_total = self._get_a2_door_arm_panel_contact_forces()
        del body_forces, arm_forces
        frame_requirement = (
            self._a2_pull_frame_passage
            if self._is_a2_pull_traversal()
            else torch.ones_like(self._a2_pull_event_reached[:, 0])
        )
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E6_PATH_REVERSAL_ENTRY]
            & (signed_crossing > 0.0)
            & (self._pull_direction.travel_dir_x * root_states[:, 7] > 0.0)
            & ((body_total + arm_total) == 0.0)
            & frame_requirement
        )

    @override
    def _stage_5_to_complete_condition(self):
        door_states = self.simulator.get_task_root_state("door")
        frame_requirement = (
            self._a2_pull_frame_passage
            if self._is_a2_pull_traversal()
            else torch.ones_like(self._a2_pull_event_reached[:, 0])
        )
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E7_WHOLE_BODY_CLEAR]
            & self._get_a2_pull_whole_body_clear_mask(door_states[:, 0])
            & frame_requirement
        )


__all__ = ["DoorOpenA2Pull"]
