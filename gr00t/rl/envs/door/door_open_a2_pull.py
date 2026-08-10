"""Pull-only A2+Piper environment with immutable signed door semantics."""

from __future__ import annotations

import math
from collections.abc import Mapping

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
    validate_a2_pull_control_step,
    validate_a2_pull_episode,
)
from gr00t.rl.envs.door.a2_pull_v0_guard import (
    A2_PULL_V0_TARGET_ORIENTATION_WXYZ,
    A2_PULL_V3_PLAN_ID,
)
from gr00t.rl.envs.door.door_open_a2_base import (
    DoorPregrasp,
    a2_hold_pd_effort_estimates,
)
from gr00t.rl.isaac_utils.rotations import xyzw_to_wxyz
from gr00t.rl.utils.torch_utils import torch_rand_float


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

    def __init__(self, config, device):
        config_mapping = config.get("config", config)
        if not isinstance(config_mapping, Mapping):
            raise RuntimeError("Pull-v0 config must expose a mapping for env.config.")
        self._pull_direction = A2DoorDirection(
            door_open_io=config_mapping["a2_pull_door_open_io"],
            door_open_lr=config_mapping["a2_pull_door_open_lr"],
        )
        super().__init__(config, device)

    def _is_a2_pull_v3(self) -> bool:
        return self.config.get("a2_v20_R1_plan_id") == A2_PULL_V3_PLAN_ID

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
        self._a2_pull_last_raw_reward_components: dict[str, torch.Tensor] = {}
        self._a2_pull_runtime_telemetry_contract_checked = False
        self._a2_pull_runtime_telemetry_contract_sample: list[dict] = []

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
        self._a2_pull_deliberate_release[env_ids] = False
        self._a2_pull_deliberate_release_step[env_ids] = -1
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
        root_y = root_states[:, 1]
        door_y = door_states[:, 1]
        frame_approach_now = torch.abs(root_x - door_x) < 0.3
        in_frame_opening_now = torch.abs(root_y - door_y) <= 0.5 * self.door_width
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
        if self._is_a2_pull_v3():
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
        signed_crossing = self._pull_direction.signed_crossing_progress(root_x, door_x)
        planar_crossing_now = signed_crossing > 0.0
        new_planar_crossing = planar_crossing_now & ~self._a2_pull_planar_crossing
        self._a2_pull_planar_crossing |= planar_crossing_now
        self._a2_pull_planar_crossing_step[new_planar_crossing] = control_step[
            new_planar_crossing
        ]
        detour_now = self._is_a2_pull_v3() & planar_crossing_now & ~self._a2_pull_frame_passage
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
            self._is_a2_pull_v3()
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
            if self._is_a2_pull_v3()
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
        if self._is_a2_pull_v3():
            for reward_name in (
                "a2_corridor_door_wide",
                "a2_corridor_clean_passage",
            ):
                raw_value = captured.get(reward_name)
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
            if self._is_a2_pull_v3():
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
                    "corridor_clean_passage_pre_aperture_steps": int(
                        self._a2_pull_corridor_clean_passage_pre_aperture_steps[env_id].item()
                    ),
                    "complete_without_frame_passage": bool(
                        reached[A2PullEvent.E7_WHOLE_BODY_CLEAR.name]
                        and not self._a2_pull_frame_passage[env_id].item()
                    ),
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
            if self._is_a2_pull_v3():
                frame_approach_current = bool(
                    (abs(float(root_x[env_id].item()) - float(door_x[env_id].item())) < 0.3)
                    and (
                        abs(float(root_states[env_id, 1].item()) - float(door_states[env_id, 1].item()))
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
                ][env_id]
                corridor_clean_raw = self._a2_pull_last_raw_reward_components[
                    "a2_corridor_clean_passage"
                ][env_id]
                current_step = int(self.episode_length_buf[env_id].item())
                release_step = int(self._a2_pull_deliberate_release_step[env_id].item())
                record["pull_v3_traversal"] = {
                    "aperture_ready": bool(self._a2_pull_aperture_ready[env_id].item()),
                    "aperture_ready_current": bool(aperture_ready_current[env_id].item()),
                    "frame_approach": bool(self._a2_pull_frame_approach[env_id].item()),
                    "frame_approach_current": frame_approach_current,
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
        if not self._is_a2_pull_v3():
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
        if not self._is_a2_pull_v3():
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
    @override
    def _reward_a2_corridor_clean_passage(self):
        if not self._is_a2_pull_v3():
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
            if self._is_a2_pull_v3()
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
            if self._is_a2_pull_v3()
            else torch.ones_like(self._a2_pull_event_reached[:, 0])
        )
        return (
            self._a2_pull_event_reached[:, A2PullEvent.E7_WHOLE_BODY_CLEAR]
            & self._get_a2_pull_whole_body_clear_mask(door_states[:, 0])
            & frame_requirement
        )


__all__ = ["DoorOpenA2Pull"]
