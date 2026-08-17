"""Open-field terminal-hold task for the v5.6 HOMIE specialist."""

from __future__ import annotations

from collections.abc import Mapping

import torch
from typing_extensions import override

from gr00t.rl.envs.base_task.pull_v5_5_adapter_holdtrack import (
    HIGH_LEVEL_ACTION_DIM,
    FROZEN_LEG_ACTION_DIM,
    PullV55AdapterHoldTrack,
)


PLAN_ID = "a2_piper_pull_v5_6_terminal_hold_specialist_finetune"
TRACE_SCHEMA = "a2_piper_pull_v5_6_hold_specialist_trace_v1"
SPECIALIST_ACTION_DIM = FROZEN_LEG_ACTION_DIM


class PullV56HoldSpecialist(PullV55AdapterHoldTrack):
    """Reuse the v5.5 FSM while splitting task and specialist provenance."""

    OPEN_FIELD = True
    SCENE_OBJECTS: tuple[str, ...] = ()
    ADAPTER_ACTIVE_PHASE = "terminal_hold_specialist"

    def __init__(self, config, device):
        config_mapping = config.get("config", config)
        if not isinstance(config_mapping, Mapping):
            raise TypeError("pull-v5.6 specialist config must expose a mapping")
        self._specialist_config = config_mapping
        self._original_homie_checkpoint = config_mapping.get("original_homie_checkpoint")
        self._specialist_checkpoint = config_mapping.get("specialist_checkpoint")
        self._specialist_checkpoint_step = config_mapping.get("specialist_checkpoint_step")
        self._hold_specialist_enabled = config_mapping.get("hold_specialist_active", True)
        if not isinstance(self._hold_specialist_enabled, bool):
            raise TypeError("v5.6 hold_specialist_active must be a boolean")
        self._step0_baseline = str(config_mapping.get("adapter_probe_phase", "train")) == "step0"
        super().__init__(config, device)

    @override
    def _init_buffers(self):
        super()._init_buffers()
        self._holdtrack_phase_active = torch.zeros_like(self._adapter_active)
        self._hold_specialist_active = torch.zeros_like(self._adapter_active)
        self._specialist_current_leg_action = torch.zeros(
            self.num_envs, SPECIALIST_ACTION_DIM, device=self.device, dtype=torch.float
        )
        self._specialist_last_leg_action = torch.zeros_like(self._specialist_current_leg_action)
        self._specialist_leg_bound = torch.zeros_like(self._adapter_active)

    @override
    def _reset_buffers_callback(self, env_ids, target_buf=None):
        super()._reset_buffers_callback(env_ids, target_buf)
        self._holdtrack_phase_active[env_ids] = False
        self._hold_specialist_active[env_ids] = False
        self._specialist_current_leg_action[env_ids] = 0.0
        self._specialist_last_leg_action[env_ids] = 0.0
        self._specialist_leg_bound[env_ids] = False

    def _specialist_active_for_phase(self, adapter_active: torch.Tensor) -> torch.Tensor:
        if self._step0_baseline or not self._hold_specialist_enabled:
            return torch.zeros_like(adapter_active)
        return adapter_active.clone()

    @override
    def _reset_tasks_callback(self, env_ids):
        if self._adapter_probe_phase != "step0":
            return super()._reset_tasks_callback(env_ids)
        original_phase = self._adapter_probe_phase
        self._adapter_probe_phase = "training_gate"
        try:
            return super()._reset_tasks_callback(env_ids)
        finally:
            self._adapter_probe_phase = original_phase

    @override
    def _sample_handoff_goal(self, env_ids: torch.Tensor, *, from_current_state: bool = False) -> None:
        if self._adapter_probe_phase != "step0":
            return super()._sample_handoff_goal(env_ids, from_current_state=from_current_state)
        original_phase = self._adapter_probe_phase
        self._adapter_probe_phase = "training_gate"
        try:
            return super()._sample_handoff_goal(env_ids, from_current_state=from_current_state)
        finally:
            self._adapter_probe_phase = original_phase

    @override
    def prepare_high_level_action(self, high_level_action: torch.Tensor) -> torch.Tensor:
        holdtrack_phase_active = self._adapter_active_mask().clone()
        applied = super().prepare_high_level_action(high_level_action)
        self._holdtrack_phase_active[:] = holdtrack_phase_active
        self._hold_specialist_active[:] = self._specialist_active_for_phase(self._adapter_active)
        return applied

    def bind_specialist_leg_action(
        self, selected_leg_action: torch.Tensor, specialist_active: torch.Tensor
    ) -> None:
        expected = (self.num_envs, SPECIALIST_ACTION_DIM)
        if tuple(selected_leg_action.shape) != expected:
            raise ValueError(f"specialist leg action must have shape {expected}")
        if tuple(specialist_active.shape) != (self.num_envs,):
            raise ValueError("specialist active provenance must have shape [num_envs]")
        if specialist_active.dtype != torch.bool or not torch.equal(
            specialist_active, self._hold_specialist_active
        ):
            raise ValueError("specialist active provenance does not match the prepared FSM phase")
        if not selected_leg_action.is_floating_point() or not torch.all(
            torch.isfinite(selected_leg_action)
        ):
            raise ValueError("specialist leg action must be finite floating point")
        self._specialist_current_leg_action[:] = selected_leg_action
        self._specialist_leg_bound[:] = True

    @override
    def step(self, actor_state):
        if not torch.all(self._specialist_leg_bound):
            raise RuntimeError("v5.6 env.step requires specialist leg provenance before execution")
        actions = actor_state["actions"]
        expected = (self.num_envs, HIGH_LEVEL_ACTION_DIM + FROZEN_LEG_ACTION_DIM)
        if tuple(actions.shape) != expected:
            raise ValueError(f"v5.6 packed action must have shape {expected}")
        if not torch.equal(actions[:, HIGH_LEVEL_ACTION_DIM:], self._specialist_current_leg_action):
            raise RuntimeError("v5.6 env.step received legs different from specialist provenance")
        result = super().step(actor_state)
        self._specialist_last_leg_action[:] = self._specialist_current_leg_action
        self._specialist_leg_bound[:] = False
        return result

    @override
    def _check_termination(self):
        super()._check_termination()
        for row in self._adapter_terminal_rows:
            row.update(
                {
                    "schema": TRACE_SCHEMA,
                    "plan_id": PLAN_ID,
                    "holdtrack_phase_active": bool(row.get("adapter_active", False)),
                    "hold_specialist_active": bool(row.get("adapter_active", False))
                    and self._hold_specialist_enabled
                    and not self._step0_baseline,
                    "specialist_checkpoint": self._specialist_checkpoint,
                    "specialist_checkpoint_step": self._specialist_checkpoint_step,
                    "original_homie_checkpoint": self._original_homie_checkpoint,
                    "adapter_provenance": {
                        "phase": self._adapter_probe_phase,
                        "specialist_phase": self._adapter_probe_phase,
                        "holdtrack_phase_active": bool(row.get("adapter_active", False)),
                        "hold_specialist_active": bool(row.get("adapter_active", False))
                        and self._hold_specialist_enabled
                        and not self._step0_baseline,
                        "specialist_checkpoint": self._specialist_checkpoint
                        if bool(row.get("adapter_active", False)) and self._hold_specialist_enabled and not self._step0_baseline else None,
                        "specialist_checkpoint_step": self._specialist_checkpoint_step
                        if bool(row.get("adapter_active", False)) and self._hold_specialist_enabled and not self._step0_baseline else None,
                        "original_homie_checkpoint": self._original_homie_checkpoint,
                    },
                }
            )
        self.extras["pull_v5_6_terminal"] = {
            "schema": TRACE_SCHEMA,
            "plan_id": PLAN_ID,
            "record_class": "interface_characterization",
            "scientific_denominator_included": False,
            "denominator_scope": "none",
            "holdtrack_phase_active": self._holdtrack_phase_active.clone(),
            "hold_specialist_active": self._hold_specialist_active.clone(),
            "specialist_phase": self._adapter_probe_phase,
            "specialist_checkpoint": self._specialist_checkpoint,
            "specialist_checkpoint_step": self._specialist_checkpoint_step,
            "original_homie_checkpoint": self._original_homie_checkpoint,
        }

    @override
    def _reward_penalty_adapter_action_delta(self) -> torch.Tensor:
        delta = torch.sum(
            torch.square(self._specialist_current_leg_action - self._specialist_last_leg_action),
            dim=-1,
        )
        return torch.where(
            self._hold_specialist_active, delta, torch.zeros_like(delta)
        )


PullV5_6HoldSpecialist = PullV56HoldSpecialist
PullV56HoldSpecialistEnv = PullV56HoldSpecialist


__all__ = [
    "PLAN_ID",
    "TRACE_SCHEMA",
    "SPECIALIST_ACTION_DIM",
    "PullV56HoldSpecialist",
    "PullV5_6HoldSpecialist",
    "PullV56HoldSpecialistEnv",
]
