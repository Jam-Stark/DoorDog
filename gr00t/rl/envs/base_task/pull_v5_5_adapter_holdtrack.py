"""Open-field terminal-hold task for the pull-v5.5 residual adapter.

The task deliberately has no door object.  It reuses the project A2 high-level
command executor, while the adapter owns only the three planar command axes
until the frozen A2_Base policy receives its normal 12-D carrier plus twelve
frozen leg actions.  All diagnostic telemetry is explicitly outside the
scientific denominator.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import torch
from isaaclab.utils.math import quat_from_euler_xyz
from typing_extensions import override

from gr00t.rl.envs.base_task.a2_base import A2Base


PLAN_ID = "a2_piper_pull_v5_5_residual_terminal_hold_adapter"
TRACE_SCHEMA = "a2_piper_pull_v5_5_adapter_holdtrack_trace_v1"
NUM_ADAPTER_AXES = 3
HIGH_LEVEL_ACTION_DIM = 12
FROZEN_LEG_ACTION_DIM = 12
ADAPTER_TRAINABLE_ACTION_DIM = 3
TERMINAL_HOLD_STEPS = 100
ENTRY_STEP_CAP = 250
ADAPTER_STEP_BUDGET = ENTRY_STEP_CAP + TERMINAL_HOLD_STEPS
WAYPOINT_TOLERANCE_M = 0.05
YAW_TOLERANCE_RAD = 0.15
NATURAL_RESET_YAW_RAD = math.pi

# Source-grounded primitive generator ranges.  These are deliberately kept in
# the new task namespace; no existing pull task constants are mutated.
REGISTERED_PRIMITIVE_COMMAND_RANGE = {
    "straight_minus_x": (-0.30, 0.0, 0.0),
    "side_step": (-0.18, 0.24, 0.0),
    "coarse_neg": (0.0, 0.0, -2.0),
    "coarse_pos": (0.0, 0.0, 2.0),
}
# The executable envelope is the registered primitive envelope, including its
# asymmetric XY signs.  The source values are copied into every receipt.
ADAPTER_RAW_ACTION_LOW = (-0.30, 0.0, -2.0)
ADAPTER_RAW_ACTION_HIGH = (0.0, 0.24, 2.0)

# The from-scratch 750x64 rollout reaches 16,000 and 32,000 global simulator
# steps at its 250- and 500-batch checkpoints.  These envelopes apply only to
# the training target sampler; gate/evaluation phases retain their registered
# full-range or explicit target mechanics below.
ADAPTER_TRAIN_CURRICULUM_STAGES = (
    ("small", 0, 16_000, 0.10, 0.15),
    ("medium", 16_000, 32_000, 0.25, 0.30),
    ("full", 32_000, None, 0.50, 0.60),
)


def adapter_train_curriculum(common_step_counter: int) -> tuple[str, float, float]:
    """Return the train-only target tier and its radius/yaw envelope."""

    if isinstance(common_step_counter, bool) or not isinstance(common_step_counter, int):
        raise TypeError("adapter curriculum step must be an integer")
    if common_step_counter < 0:
        raise ValueError("adapter curriculum step must be non-negative")
    for tier, start_step, end_step, radius_max_m, yaw_max_rad in ADAPTER_TRAIN_CURRICULUM_STAGES:
        if common_step_counter >= start_step and (
            end_step is None or common_step_counter < end_step
        ):
            return tier, radius_max_m, yaw_max_rad
    raise RuntimeError("adapter curriculum stages do not cover the requested step")

PRELUDE_FAMILIES = (
    "near_rest",
    "coarse_neg",
    "coarse_pos",
    "straight_minus_x",
    "side_step",
)
PRELUDE_COMMANDS = {
    "near_rest": (0.0, 0.0, 0.0),
    "coarse_neg": REGISTERED_PRIMITIVE_COMMAND_RANGE["coarse_neg"],
    "coarse_pos": REGISTERED_PRIMITIVE_COMMAND_RANGE["coarse_pos"],
    "straight_minus_x": REGISTERED_PRIMITIVE_COMMAND_RANGE["straight_minus_x"],
    "side_step": REGISTERED_PRIMITIVE_COMMAND_RANGE["side_step"],
}
PRELUDE_MAX_STEPS = {
    "near_rest": 0,
    "coarse_neg": 200,
    "coarse_pos": 200,
    "straight_minus_x": 150,
    "side_step": 150,
}

# These targets characterize this adapter task only.  They are not the
# authoritative S1-S4 mechanics used by the formal pull-v5 T3 admission.
ADAPTER_ANCHOR_SCOPE = "adapter_task_characterization_only"
FORMAL_T3_ANCHOR_ADMISSION = False
ADAPTER_ANCHOR_TARGETS = {
    "S1": (0.30, 0.00, -0.60),
    "S2": (0.30, 0.00, 0.60),
    "S3": (0.00, 0.30, -1.00),
    "S4": (0.00, 0.30, 1.00),
}


def adapter_phase_from_step(episode_step: int, prelude_steps: int) -> str:
    """Return the explicit scripted-prelude versus adapter-active FSM phase."""

    if isinstance(episode_step, bool) or isinstance(prelude_steps, bool):
        raise TypeError("adapter FSM steps must be integers")
    if not isinstance(episode_step, int) or not isinstance(prelude_steps, int):
        raise TypeError("adapter FSM steps must be integers")
    if episode_step < 0 or prelude_steps < 0:
        raise ValueError("adapter FSM steps must be non-negative")
    return "prelude" if episode_step < prelude_steps else "adapter"


def wrap_yaw_error(target_yaw: torch.Tensor, measured_yaw: torch.Tensor) -> torch.Tensor:
    """Return the signed shortest target-minus-measured yaw error."""

    return torch.atan2(
        torch.sin(target_yaw - measured_yaw), torch.cos(target_yaw - measured_yaw)
    )


def terminal_hold_update(
    xy_error_m: torch.Tensor,
    yaw_error_rad: torch.Tensor,
    hold_steps: torch.Tensor,
    done_latched: torch.Tensor,
    *,
    hold_length: int = TERMINAL_HOLD_STEPS,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Advance the terminal-current-state hold and return returned-done flags.

    ``done`` is produced from the same state sample that increments the hold;
    callers bind it directly to the ``env.step`` returned-dones tensor.
    """

    if xy_error_m.ndim != 1 or yaw_error_rad.ndim != 1:
        raise ValueError("terminal hold errors must be one-dimensional batch tensors")
    if xy_error_m.shape != yaw_error_rad.shape:
        raise ValueError("terminal hold XY and yaw errors must share a batch shape")
    if hold_steps.shape != xy_error_m.shape or done_latched.shape != xy_error_m.shape:
        raise ValueError("terminal hold state tensors must share the error batch shape")
    if hold_steps.dtype != torch.long or done_latched.dtype != torch.bool:
        raise TypeError("terminal hold state requires long hold_steps and bool done_latched")
    in_tolerance = (xy_error_m <= WAYPOINT_TOLERANCE_M) & (
        yaw_error_rad.abs() <= YAW_TOLERANCE_RAD
    )
    next_hold_steps = torch.where(
        in_tolerance, hold_steps + 1, torch.zeros_like(hold_steps)
    )
    done = in_tolerance & (next_hold_steps >= hold_length) & ~done_latched
    next_latched = done_latched | done
    return next_hold_steps, next_latched, done, in_tolerance


def pack_adapter_action(
    adapter_action: torch.Tensor,
    frozen_leg_action: torch.Tensor,
) -> torch.Tensor:
    """Pack exactly three adapter axes into the canonical 24-D A2 executor input.

    The returned carrier is ``[base(5), arm(6), gripper(1), frozen legs(12)]``.
    Only ``base[:3]`` comes from the adapter; pitch/roll are zero, arm deltas
    are zero, and the gripper primitive is open.  Padded carrier dimensions are
    therefore deterministic and are not policy dimensions.
    """

    if not torch.is_tensor(adapter_action) or adapter_action.shape[-1] != NUM_ADAPTER_AXES:
        raise ValueError("adapter_action must have a final dimension of exactly three")
    if not adapter_action.is_floating_point() or not torch.all(torch.isfinite(adapter_action)):
        raise ValueError("adapter_action must be finite floating point")
    carrier = torch.zeros(
        *adapter_action.shape[:-1], HIGH_LEVEL_ACTION_DIM,
        dtype=adapter_action.dtype,
        device=adapter_action.device,
    )
    carrier[..., 0:3] = adapter_action
    carrier[..., 11] = 1.0
    if (
        not torch.is_tensor(frozen_leg_action)
        or frozen_leg_action.shape != (*adapter_action.shape[:-1], FROZEN_LEG_ACTION_DIM)
        or frozen_leg_action.dtype != adapter_action.dtype
        or frozen_leg_action.device != adapter_action.device
        or not torch.all(torch.isfinite(frozen_leg_action))
    ):
        raise ValueError("frozen_leg_action must match adapter leading shape and be finite")
    return torch.cat((carrier, frozen_leg_action), dim=-1)


def make_diagnostic_row(
    *,
    family: str,
    env_id: int,
    episode_index: int,
    xy_error_m: float,
    yaw_error_rad: float,
    hold_steps: int,
    done: bool,
    adapter_active: bool,
    adapter_checkpoint: str | None,
    adapter_checkpoint_step: int | None = None,
    terminal_after_step: bool,
) -> dict[str, object]:
    """Create one denominator-isolated interface-characterization row."""

    if family not in PRELUDE_FAMILIES:
        raise ValueError(f"unknown prelude family: {family!r}")
    if env_id < 0 or episode_index < 0:
        raise ValueError("diagnostic row ids must be non-negative")
    if not all(math.isfinite(float(value)) for value in (xy_error_m, yaw_error_rad)):
        raise ValueError("diagnostic errors must be finite")
    if hold_steps < 0:
        raise ValueError("diagnostic hold_steps must be non-negative")
    if not isinstance(done, bool) or not isinstance(adapter_active, bool):
        raise TypeError("diagnostic done and adapter_active fields must be bool")
    if adapter_checkpoint_step is not None and (
        isinstance(adapter_checkpoint_step, bool)
        or not isinstance(adapter_checkpoint_step, int)
        or adapter_checkpoint_step < 0
    ):
        raise TypeError("adapter_checkpoint_step must be a non-negative integer or None")
    if adapter_active and (not isinstance(adapter_checkpoint, str) or not adapter_checkpoint):
        raise ValueError("active adapter diagnostics require an adapter checkpoint path")
    if adapter_active and adapter_checkpoint_step is None:
        raise ValueError("active adapter diagnostics require an adapter checkpoint step")
    if not adapter_active and adapter_checkpoint not in (None, ""):
        raise ValueError("inactive adapter diagnostics must not carry a checkpoint path")
    if not adapter_active and adapter_checkpoint_step not in (None, ""):
        raise ValueError("inactive adapter diagnostics must not carry a checkpoint step")
    if not isinstance(terminal_after_step, bool):
        raise TypeError("terminal_after_step must be the returned-dones bool")
    return {
        "schema": TRACE_SCHEMA,
        "record_class": "interface_characterization",
        "scientific_denominator_included": False,
        "denominator_scope": "none",
        "family": family,
        "env_id": int(env_id),
        "episode_index": int(episode_index),
        "xy_error_m": float(xy_error_m),
        "yaw_error_rad": float(yaw_error_rad),
        "terminal_hold_steps": int(hold_steps),
        "terminal_current_state": bool(done),
        "done": bool(done),
        "adapter_active": bool(adapter_active),
        "adapter_checkpoint": adapter_checkpoint,
        "adapter_checkpoint_step": adapter_checkpoint_step,
        "adapter_provenance": {"phase": "terminal_hold" if adapter_active else "prelude"},
        "terminal_after_step": bool(terminal_after_step),
        "returned_dones_binding": "env.step returned dones",
    }


class PullV55AdapterHoldTrack(A2Base):
    """No-door open-field task with a bounded residual terminal-hold phase."""

    OPEN_FIELD = True
    SCENE_OBJECTS: tuple[str, ...] = ()
    ADAPTER_ACTIVE_PHASE = "terminal_probe"

    def __init__(self, config, device):
        config_mapping = config.get("config", config)
        if not isinstance(config_mapping, Mapping):
            raise TypeError("pull-v5.5 adapter config must expose a mapping")
        self._adapter_config = config_mapping
        self._adapter_checkpoint = config_mapping.get("adapter_checkpoint")
        self._adapter_checkpoint_step = config_mapping.get("adapter_checkpoint_step")
        self._adapter_active_config = bool(config_mapping.get("adapter_active", True))
        self._adapter_probe_phase = str(config_mapping.get("adapter_probe_phase", "train"))
        self._adapter_rehearsal_yaw_delta = config_mapping.get("adapter_rehearsal_yaw_delta_rad")
        self._adapter_rehearsal_xy_delta = config_mapping.get("adapter_rehearsal_xy_delta_m")
        self._adapter_anchor_sequence = config_mapping.get("adapter_anchor_sequence")
        self._adapter_anchor_attempt = config_mapping.get("adapter_anchor_attempt")
        self._adapter_eval_output_dir = config_mapping.get("adapter_eval_output_dir")
        super().__init__(config, device)

    @override
    def _init_buffers(self):
        super()._init_buffers()
        self._adapter_goal_world_xy = torch.zeros(
            self.num_envs, 2, device=self.device, dtype=torch.float
        )
        self._adapter_goal_yaw = torch.full(
            (self.num_envs,), NATURAL_RESET_YAW_RAD, device=self.device, dtype=torch.float
        )
        self._adapter_last_action = torch.zeros(
            self.num_envs, NUM_ADAPTER_AXES, device=self.device, dtype=torch.float
        )
        self._adapter_current_action = torch.zeros_like(self._adapter_last_action)
        self._adapter_hold_steps = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._adapter_active_steps = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._adapter_entry_latched = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._adapter_done_latched = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._adapter_terminal_current_state = torch.zeros_like(self._adapter_done_latched)
        self._adapter_active = torch.zeros_like(self._adapter_done_latched)
        self._handoff_latched = torch.zeros_like(self._adapter_done_latched)
        self._prepared_high_level_action = torch.zeros(
            self.num_envs, HIGH_LEVEL_ACTION_DIM, device=self.device, dtype=torch.float
        )
        self._step_prepared = torch.zeros_like(self._adapter_done_latched)
        self._adapter_terminal_rows: list[dict[str, object]] = []
        self._prelude_steps = torch.zeros(self.num_envs, device=self.device, dtype=torch.long)
        self._prelude_family = ["near_rest"] * self.num_envs
        self._adapter_target_source = ["uninitialized"] * self.num_envs
        self._adapter_target_curriculum_tier = ["uninitialized"] * self.num_envs
        self._adapter_target_radius_max_m = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.float
        )
        self._adapter_target_yaw_max_rad = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.float
        )

    @override
    def _reset_buffers_callback(self, env_ids, target_buf=None):
        super()._reset_buffers_callback(env_ids, target_buf)
        self._adapter_last_action[env_ids] = 0.0
        self._adapter_current_action[env_ids] = 0.0
        self._adapter_hold_steps[env_ids] = 0
        self._adapter_active_steps[env_ids] = 0
        self._adapter_entry_latched[env_ids] = False
        self._adapter_done_latched[env_ids] = False
        self._adapter_terminal_current_state[env_ids] = False
        self._adapter_active[env_ids] = False
        self._handoff_latched[env_ids] = False
        self._step_prepared[env_ids] = False
        self._adapter_target_radius_max_m[env_ids] = 0.0
        self._adapter_target_yaw_max_rad[env_ids] = 0.0
        for env_id in env_ids.tolist():
            self._adapter_target_source[int(env_id)] = "uninitialized"
            self._adapter_target_curriculum_tier[int(env_id)] = "uninitialized"

    @override
    def _reset_tasks_callback(self, env_ids):
        super()._reset_tasks_callback(env_ids)
        self._prelude_steps[env_ids] = 0
        for local_index, env_id in enumerate(env_ids.tolist()):
            if self._adapter_probe_phase == "training_gate":
                family = PRELUDE_FAMILIES[int(env_id) % len(PRELUDE_FAMILIES)]
            elif self._adapter_probe_phase in {"rehearsal", "anchor"}:
                configured_family = self._adapter_config.get("adapter_family", "near_rest")
                if configured_family not in PRELUDE_FAMILIES:
                    raise ValueError(f"unknown configured adapter family: {configured_family!r}")
                family = str(configured_family)
            else:
                family = PRELUDE_FAMILIES[
                    int(torch.randint(0, len(PRELUDE_FAMILIES), (), device=self.device).item())
                ]
            self._prelude_family[env_id] = family
            max_steps = PRELUDE_MAX_STEPS[family]
            self._prelude_steps[env_id] = (
                torch.randint(0, max_steps + 1, (), device=self.device)
                if max_steps
                else 0
            )

    @override
    def _reset_root_states(self, env_ids, target_root_states=None):
        super()._reset_root_states(env_ids, target_root_states)
        zeros = torch.zeros(len(env_ids), device=self.device)
        self.target_robot_root_states[env_ids, 3:7] = quat_from_euler_xyz(
            zeros, zeros, torch.full_like(zeros, NATURAL_RESET_YAW_RAD)
        )
        self._sample_handoff_goal(env_ids)

    def _sample_handoff_goal(self, env_ids: torch.Tensor, *, from_current_state: bool = False) -> None:
        if from_current_state:
            root = self.simulator.robot_root_states[env_ids]
            yaw = self.rpy[env_ids, 2]
        else:
            root = self.target_robot_root_states[env_ids]
            yaw = torch.full((len(env_ids),), NATURAL_RESET_YAW_RAD, device=self.device)

        if self._adapter_probe_phase == "rehearsal":
            xy_delta = float(self._adapter_rehearsal_xy_delta)
            yaw_delta = float(self._adapter_rehearsal_yaw_delta)
            offset_body = torch.zeros(len(env_ids), 2, device=self.device)
            offset_body[:, 0] = xy_delta
            target_yaw = yaw + yaw_delta
            target_source = "explicit_rehearsal"
            target_tier = "explicit"
            target_radius_max_m = abs(xy_delta)
            target_yaw_max_rad = abs(yaw_delta)
        elif self._adapter_probe_phase == "anchor":
            sequence = str(self._adapter_anchor_sequence)
            if sequence not in ADAPTER_ANCHOR_TARGETS:
                raise ValueError(f"unknown adapter anchor sequence: {sequence!r}")
            offset_x, offset_y, yaw_delta = ADAPTER_ANCHOR_TARGETS[sequence]
            offset_body = torch.tensor(
                (offset_x, offset_y), device=self.device, dtype=torch.float
            ).expand(len(env_ids), -1)
            target_yaw = yaw + yaw_delta
            target_source = "explicit_anchor"
            target_tier = "explicit"
            target_radius_max_m = math.hypot(offset_x, offset_y)
            target_yaw_max_rad = abs(yaw_delta)
        else:
            if self._adapter_probe_phase == "train":
                target_tier, radius_max_m, yaw_max_rad = adapter_train_curriculum(
                    self.common_step_counter
                )
                target_source = "train_curriculum"
            elif self._adapter_probe_phase == "training_gate":
                target_tier = "full"
                radius_max_m = 0.50
                yaw_max_rad = 0.60
                target_source = "training_gate_registered_full"
            else:
                raise ValueError(
                    "pull-v5.5 adapter target sampling requires train, training_gate, "
                    "rehearsal, or anchor phase"
                )
            target_radius_max_m = radius_max_m
            target_yaw_max_rad = yaw_max_rad
            radius = torch.sqrt(torch.rand(len(env_ids), device=self.device)) * radius_max_m
            angle = torch.rand(len(env_ids), device=self.device) * (2.0 * math.pi)
            offset_body = torch.stack(
                (radius * torch.cos(angle), radius * torch.sin(angle)), dim=-1
            )
            target_yaw = yaw + (
                torch.rand(len(env_ids), device=self.device) * (2.0 * yaw_max_rad)
                - yaw_max_rad
            )

        self._adapter_target_radius_max_m[env_ids] = target_radius_max_m
        self._adapter_target_yaw_max_rad[env_ids] = target_yaw_max_rad
        for env_id in env_ids.tolist():
            self._adapter_target_source[int(env_id)] = target_source
            self._adapter_target_curriculum_tier[int(env_id)] = target_tier

        cos_yaw, sin_yaw = torch.cos(yaw), torch.sin(yaw)
        offset_world = torch.stack(
            (
                cos_yaw * offset_body[:, 0] - sin_yaw * offset_body[:, 1],
                sin_yaw * offset_body[:, 0] + cos_yaw * offset_body[:, 1],
            ),
            dim=-1,
        )
        self._adapter_goal_world_xy[env_ids] = root[:, :2] + offset_world
        self._adapter_goal_yaw[env_ids] = target_yaw

    def _prelude_command_tensor(self) -> torch.Tensor:
        command = torch.zeros(self.num_envs, 3, device=self.device, dtype=torch.float)
        for family in PRELUDE_FAMILIES:
            env_ids = [i for i, value in enumerate(self._prelude_family) if value == family]
            if env_ids:
                command[env_ids] = torch.tensor(
                    PRELUDE_COMMANDS[family], device=self.device, dtype=command.dtype
                )
        return command

    def _adapter_active_mask(self) -> torch.Tensor:
        return (
            self._adapter_active_config
            & (self.episode_length_buf >= self._prelude_steps)
        )

    def prepare_high_level_action(self, high_level_action: torch.Tensor) -> torch.Tensor:
        """Apply the prelude/FSM override before frozen A2 leg inference."""

        expected = (self.num_envs, HIGH_LEVEL_ACTION_DIM)
        if tuple(high_level_action.shape) != expected:
            raise ValueError(f"high-level adapter carrier must have shape {expected}")
        if high_level_action.device != torch.device(self.device) or not high_level_action.is_floating_point():
            raise TypeError("high-level adapter carrier must be a device-local floating tensor")
        if not torch.all(torch.isfinite(high_level_action)):
            raise ValueError("high-level adapter carrier must be finite")
        if not torch.all(high_level_action[:, 3:11] == 0.0) or not torch.all(
            high_level_action[:, 11] == 1.0
        ):
            raise ValueError("high-level adapter carrier padded axes must be deterministic")

        active_phase = self._adapter_active_mask()
        new_handoff = active_phase & ~self._handoff_latched
        if torch.any(new_handoff):
            handoff_ids = torch.where(new_handoff)[0]
            self._sample_handoff_goal(handoff_ids, from_current_state=True)
            self._adapter_hold_steps[handoff_ids] = 0
            self._adapter_active_steps[handoff_ids] = 0
            self._adapter_entry_latched[handoff_ids] = False
        self._handoff_latched |= new_handoff

        applied = high_level_action.clone()
        prelude = self._prelude_command_tensor()
        # The handoff transition is scripted.  The newly sampled goal is now
        # present in the returned transition observation; learned control starts
        # on the following step.
        adapter_active = active_phase & ~new_handoff
        scripted_transition = ~adapter_active
        if torch.any(scripted_transition):
            applied[scripted_transition, :3] = prelude[scripted_transition]
        self._adapter_active[:] = adapter_active
        self._adapter_current_action[:] = applied[:, :3]
        self._prepared_high_level_action[:] = applied
        self._step_prepared[:] = True
        self._adapter_active_steps[adapter_active] += 1
        return applied

    @override
    def step(self, actor_state):
        actions = actor_state["actions"]
        expected_dim = HIGH_LEVEL_ACTION_DIM + FROZEN_LEG_ACTION_DIM
        if tuple(actions.shape) != (self.num_envs, expected_dim):
            raise ValueError(
                f"pull-v5.5 executor expects packed shape ({self.num_envs}, {expected_dim}); "
                f"got {tuple(actions.shape)}"
            )
        if not torch.all(self._step_prepared):
            raise RuntimeError("pull-v5.5 env.step requires prepare_high_level_action before A2 inference")
        if not torch.equal(actions[:, :HIGH_LEVEL_ACTION_DIM], self._prepared_high_level_action):
            raise RuntimeError("A2 leg inference used a carrier different from the applied FSM command")
        # The observation builder runs inside ``super().step``.  Latch the
        # applied adapter command before that build so the returned next-state
        # observation exposes this step's action as the previous-action input.
        self._adapter_last_action[:] = self._adapter_current_action
        next_state = dict(actor_state)
        next_state["actions"] = actions
        result = super().step(next_state)
        self._step_prepared[:] = False
        return result

    def _get_a2_terminal_diagnostics(self, env_ids) -> list[dict[str, object]]:
        if not torch.is_tensor(env_ids) or env_ids.ndim != 1:
            raise TypeError("adapter terminal diagnostics require one-dimensional env_ids")
        requested = [int(value) for value in env_ids.detach().cpu().tolist()]
        if len(set(requested)) != len(requested):
            raise RuntimeError("adapter terminal diagnostics received duplicate env ids")
        selected: list[dict[str, object]] = []
        for env_id in requested:
            matches = [row for row in self._adapter_terminal_rows if row.get("env_id") == env_id]
            if len(matches) != 1:
                raise RuntimeError(
                    f"adapter terminal diagnostics require exactly one row for env {env_id}; "
                    f"found {len(matches)}"
                )
            selected.append(dict(matches[0]))
        return selected

    def consume_a2_terminal_diagnostics(self) -> list[dict[str, object]]:
        rows = [dict(row) for row in self._adapter_terminal_rows]
        seen: set[int] = set()
        for row in rows:
            env_id = row.get("env_id")
            if isinstance(env_id, bool) or not isinstance(env_id, int):
                raise RuntimeError("adapter terminal diagnostic env_id must be an integer")
            if env_id in seen:
                raise RuntimeError(f"duplicate adapter terminal diagnostic env {env_id}")
            seen.add(env_id)
        self._adapter_terminal_rows.clear()
        return rows

    @override
    def _check_termination(self):
        super()._check_termination()
        goal_error = self._get_obs_adapter_goal_error()
        xy_error = torch.linalg.vector_norm(goal_error[:, :2], dim=-1)
        yaw_error = goal_error[:, 2].abs()
        active = self._adapter_active
        (
            self._adapter_hold_steps[:],
            self._adapter_done_latched[:],
            done,
            in_tolerance,
        ) = terminal_hold_update(
            xy_error,
            yaw_error,
            self._adapter_hold_steps,
            self._adapter_done_latched,
        )
        done &= active
        in_tolerance &= active
        self._adapter_hold_steps[~active] = 0
        self._adapter_done_latched[~active] = False
        self._adapter_entry_latched |= in_tolerance
        self._adapter_terminal_current_state[:] = in_tolerance
        entry_timeout = active & ~self._adapter_entry_latched & (
            self._adapter_active_steps >= ENTRY_STEP_CAP
        )
        budget_timeout = active & (self._adapter_active_steps >= ADAPTER_STEP_BUDGET) & ~done
        overtime = entry_timeout | budget_timeout
        self._mark_terminal_reason("complete", done)
        self._mark_terminal_reason("stage_overtime", overtime)
        self.reset_buf |= (done | overtime).to(dtype=self.reset_buf.dtype)
        self.time_out_buf |= overtime
        for env_id in torch.where(done | overtime)[0].tolist():
            self._adapter_terminal_rows.append(
                {
                    "schema": TRACE_SCHEMA,
                    "record_class": "interface_characterization",
                    "scientific_denominator_included": False,
                    "denominator_scope": "none",
                    "family": self._prelude_family[env_id],
                    "sequence": self._adapter_anchor_sequence if self._adapter_probe_phase == "anchor" else None,
                    "env_id": int(env_id),
                    "episode_index": 0,
                    "episode_id": f"{self._adapter_probe_phase}:env{env_id}:episode0",
                    "xy_error_m": float(xy_error[env_id].detach().cpu()),
                    "yaw_error_rad": float(yaw_error[env_id].detach().cpu()),
                    "terminal_hold_steps": int(self._adapter_hold_steps[env_id].item()),
                    "terminal_current_state": bool(in_tolerance[env_id].item()),
                    "done": bool(done[env_id].item()),
                    "adapter_active": bool(active[env_id].item()),
                    "adapter_checkpoint": self._adapter_checkpoint,
                    "adapter_checkpoint_step": self._adapter_checkpoint_step,
                    "adapter_target_source": self._adapter_target_source[env_id],
                    "adapter_target_curriculum_tier": self._adapter_target_curriculum_tier[env_id],
                    "adapter_target_radius_max_m": float(
                        self._adapter_target_radius_max_m[env_id].detach().cpu()
                    ),
                    "adapter_target_yaw_max_rad": float(
                        self._adapter_target_yaw_max_rad[env_id].detach().cpu()
                    ),
                    "adapter_target_common_step_counter": int(self.common_step_counter),
                    "adapter_provenance": {
                        "phase": self._adapter_probe_phase,
                        "anchor_scope": (
                            ADAPTER_ANCHOR_SCOPE
                            if self._adapter_probe_phase == "anchor"
                            else None
                        ),
                        "formal_t3_anchor_admission": FORMAL_T3_ANCHOR_ADMISSION,
                    },
                    "terminal_after_step": False,
                    "returned_dones_binding": "env.step returned dones",
                }
            )
        self.extras["pull_v5_5_terminal"] = {
            "schema": TRACE_SCHEMA,
            "record_class": "interface_characterization",
            "scientific_denominator_included": False,
            "denominator_scope": "none",
            "terminal_current_state": self._adapter_terminal_current_state.clone(),
            "terminal_hold_steps": self._adapter_hold_steps.clone(),
            "adapter_active": self._adapter_active.clone(),
            "adapter_checkpoint": self._adapter_checkpoint,
            "adapter_checkpoint_step": self._adapter_checkpoint_step,
            "terminal_after_step_source": "env.step returned dones",
        }

    def _get_obs_adapter_goal_error(self) -> torch.Tensor:
        root = self.simulator.robot_root_states
        yaw = self.rpy[:, 2]
        delta_world = self._adapter_goal_world_xy - root[:, :2]
        cos_yaw, sin_yaw = torch.cos(yaw), torch.sin(yaw)
        delta_body = torch.stack(
            (
                cos_yaw * delta_world[:, 0] + sin_yaw * delta_world[:, 1],
                -sin_yaw * delta_world[:, 0] + cos_yaw * delta_world[:, 1],
            ),
            dim=-1,
        )
        delta_yaw = wrap_yaw_error(self._adapter_goal_yaw, yaw).unsqueeze(-1)
        return torch.cat((delta_body, delta_yaw), dim=-1)

    def _get_obs_adapter_root_planar_vel(self) -> torch.Tensor:
        return self.base_lin_vel[:, :2]

    def _get_obs_adapter_yaw_rate(self) -> torch.Tensor:
        return self.base_ang_vel[:, 2:3]

    def _get_obs_adapter_projected_gravity(self) -> torch.Tensor:
        return self.projected_gravity

    def _get_obs_adapter_last_action(self) -> torch.Tensor:
        return self._adapter_last_action

    # Short aliases make the 12-D observation contract readable in YAML.
    _get_obs_adapter_goal = _get_obs_adapter_goal_error
    _get_obs_adapter_planar_vel = _get_obs_adapter_root_planar_vel
    _get_obs_adapter_yaw_rate = _get_obs_adapter_yaw_rate
    _get_obs_adapter_gravity = _get_obs_adapter_projected_gravity
    _get_obs_adapter_action = _get_obs_adapter_last_action

    def _reward_adapter_dense_error(self) -> torch.Tensor:
        error = self._get_obs_adapter_goal_error()
        dense = -(
            torch.linalg.vector_norm(error[:, :2], dim=-1) / WAYPOINT_TOLERANCE_M
            + error[:, 2].abs() / YAW_TOLERANCE_RAD
        )
        return torch.where(self._adapter_active, dense, torch.zeros_like(dense))

    def _reward_adapter_in_tolerance(self) -> torch.Tensor:
        error = self._get_obs_adapter_goal_error()
        return (
            (torch.linalg.vector_norm(error[:, :2], dim=-1) <= WAYPOINT_TOLERANCE_M)
            & (error[:, 2].abs() <= YAW_TOLERANCE_RAD)
            & self._adapter_active
        ).float()

    def _reward_adapter_hold_progress(self) -> torch.Tensor:
        return torch.where(
            self._adapter_active,
            self._adapter_hold_steps.float() / TERMINAL_HOLD_STEPS,
            torch.zeros_like(self._adapter_hold_steps, dtype=torch.float),
        )

    def _reward_adapter_done(self) -> torch.Tensor:
        return self._adapter_done_latched.float() * self._adapter_active.float()

    def _reward_penalty_adapter_action_delta(self) -> torch.Tensor:
        penalty = torch.sum(
            torch.square(self._adapter_current_action - self._adapter_last_action), dim=-1
        )
        return torch.where(self._adapter_active, penalty, torch.zeros_like(penalty))


# Descriptive aliases used by Hydra and external static checks.
PullV5_5AdapterHoldTrack = PullV55AdapterHoldTrack
PullV55AdapterHoldTrackEnv = PullV55AdapterHoldTrack


__all__ = [
    "PLAN_ID",
    "TRACE_SCHEMA",
    "PRELUDE_FAMILIES",
    "ADAPTER_ANCHOR_SCOPE",
    "FORMAL_T3_ANCHOR_ADMISSION",
    "REGISTERED_PRIMITIVE_COMMAND_RANGE",
    "ADAPTER_RAW_ACTION_LOW",
    "ADAPTER_RAW_ACTION_HIGH",
    "ADAPTER_TRAIN_CURRICULUM_STAGES",
    "adapter_train_curriculum",
    "pack_adapter_action",
    "terminal_hold_update",
    "make_diagnostic_row",
    "PullV55AdapterHoldTrack",
    "PullV5_5AdapterHoldTrack",
    "PullV55AdapterHoldTrackEnv",
]
