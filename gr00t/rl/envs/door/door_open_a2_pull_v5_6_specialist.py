"""Formal Pull-v5.6 bridge environment for anchor and door positioning.

This subclass keeps the original DoorOpenA2Pull reset/step implementation and
adds only the explicit carrier/leg seam needed by the formal evaluator.  The
specialist is terminal-positioning-only; training, P4, and dual-source DV use
the ordinary environment and never instantiate this class.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import torch

from gr00t.rl.envs.door.door_open_a2_pull import DoorOpenA2Pull
from gr00t.rl.trl.modules.pull_v5_6_formal_bridge import (
    FORMAL_PHASES,
    FROZEN_LEG_ACTION_DIM,
    HIGH_LEVEL_ACTION_DIM,
    PLAN_ID,
    TRACE_SCHEMA,
    TERMINAL_HOLD_STEPS,
    WAYPOINT_TOLERANCE_M,
    YAW_TOLERANCE_RAD,
    build_formal_terminal_row,
    compose_formal_action,
    validate_carrier,
)


class DoorOpenA2PullV56Specialist(DoorOpenA2Pull):
    """Door pull task with a bound secondary specialist for formal positioning."""

    FORMAL_PHASES = FORMAL_PHASES

    def __init__(self, config, device):
        config_mapping = config.get("config", config)
        if not isinstance(config_mapping, Mapping):
            raise TypeError("v5.6 formal pull config must expose a mapping")
        self._formal_config = config_mapping
        self._formal_phase = str(config_mapping.get("formal_probe_phase", "anchor"))
        if self._formal_phase not in self.FORMAL_PHASES:
            raise ValueError(f"formal_probe_phase must be one of {sorted(self.FORMAL_PHASES)}")
        self._formal_primary_checkpoint = config_mapping.get("formal_primary_checkpoint")
        self._formal_specialist_checkpoint = config_mapping.get("formal_specialist_checkpoint")
        self._formal_original_homie_checkpoint = config_mapping.get("original_homie_checkpoint")
        for name, value in (
            ("formal_primary_checkpoint", self._formal_primary_checkpoint),
            ("formal_specialist_checkpoint", self._formal_specialist_checkpoint),
            ("original_homie_checkpoint", self._formal_original_homie_checkpoint),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty formal bridge checkpoint")
        self._formal_positioning_enabled = config_mapping.get("formal_positioning_enabled", True)
        if not isinstance(self._formal_positioning_enabled, bool):
            raise TypeError("formal_positioning_enabled must be bool")
        self._formal_specialist_actor: Callable[..., torch.Tensor] | None = None
        self._formal_specialist_leg_action = None
        self._formal_specialist_leg_bound = None
        self._formal_step_prepared = None
        self._formal_xy_error_m = None
        self._formal_yaw_error_rad = None
        self._formal_hold_steps = None
        self._formal_done_latched = None
        self._formal_terminal_rows: list[dict[str, Any]] = []
        super().__init__(config, device)

    def _init_buffers(self):
        super()._init_buffers()
        self._formal_specialist_leg_action = torch.zeros(
            self.num_envs,
            FROZEN_LEG_ACTION_DIM,
            device=self.device,
            dtype=torch.float,
        )
        self._formal_specialist_leg_bound = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._formal_step_prepared = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )
        self._formal_xy_error_m = torch.full(
            (self.num_envs,), float("inf"), device=self.device, dtype=torch.float
        )
        self._formal_yaw_error_rad = torch.full(
            (self.num_envs,), float("inf"), device=self.device, dtype=torch.float
        )
        self._formal_hold_steps = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.long
        )
        self._formal_done_latched = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool
        )

    def _reset_buffers_callback(self, env_ids, target_buf=None):
        super()._reset_buffers_callback(env_ids, target_buf)
        self._formal_specialist_leg_action[env_ids] = 0.0
        self._formal_specialist_leg_bound[env_ids] = False
        self._formal_step_prepared[env_ids] = False
        self._formal_xy_error_m[env_ids] = float("inf")
        self._formal_yaw_error_rad[env_ids] = float("inf")
        self._formal_hold_steps[env_ids] = 0
        self._formal_done_latched[env_ids] = False

    def prepare_high_level_action(self, high_level_action: torch.Tensor) -> torch.Tensor:
        """Bind the evaluator's final carrier before original-leg inference."""

        expected = (self.num_envs, HIGH_LEVEL_ACTION_DIM)
        if tuple(high_level_action.shape) != expected:
            raise ValueError(f"formal carrier must have shape {expected}")
        if high_level_action.device != torch.device(self.device):
            raise TypeError("formal carrier must be device-local")
        validate_carrier(high_level_action)
        self.get_a2_high_level_action_layout()
        self._formal_step_prepared[:] = True
        return high_level_action.clone()

    def bind_specialist_leg_action(
        self, selected_leg_action: torch.Tensor, specialist_active: torch.Tensor
    ) -> None:
        expected = (self.num_envs, FROZEN_LEG_ACTION_DIM)
        if tuple(selected_leg_action.shape) != expected:
            raise ValueError(f"formal selected leg action must have shape {expected}")
        if (
            not torch.is_tensor(specialist_active)
            or specialist_active.dtype != torch.bool
            or tuple(specialist_active.shape) != (self.num_envs,)
        ):
            raise TypeError("formal specialist_active must be a [num_envs] bool tensor")
        if not torch.all(torch.isfinite(selected_leg_action)):
            raise ValueError("formal selected leg action must be finite")
        if torch.any(specialist_active & ~self._formal_positioning_mask()):
            raise RuntimeError("formal specialist cannot bind outside anchor/door positioning")
        self._formal_specialist_leg_action[:] = selected_leg_action
        self._formal_specialist_leg_bound[:] = True

    def bind_formal_specialist_actor(self, actor: Callable[..., torch.Tensor]) -> None:
        """Bind ``(a2_obs, carrier, active_mask) -> specialist_legs``."""

        if not callable(actor):
            raise TypeError("formal specialist actor must be callable")
        self._formal_specialist_actor = actor

    def _formal_positioning_mask(self) -> torch.Tensor:
        active = torch.full(
            (self.num_envs,),
            self._formal_positioning_enabled and self._formal_phase in self.FORMAL_PHASES,
            device=self.device,
            dtype=torch.bool,
        )
        return active

    def apply_v5_6_formal_bridge(
        self,
        *,
        carrier_action: torch.Tensor,
        original_leg_actions: torch.Tensor,
        first_episode_active_mask: torch.Tensor,
        episode_indices: torch.Tensor,
        a2_base_obs: torch.Tensor | None = None,
    ) -> Mapping[str, Any]:
        """Select secondary legs for the first formal positioning episode."""

        del episode_indices
        applied_carrier = self.prepare_high_level_action(carrier_action)
        if (
            not torch.is_tensor(first_episode_active_mask)
            or first_episode_active_mask.dtype != torch.bool
            or tuple(first_episode_active_mask.shape) != (self.num_envs,)
        ):
            raise TypeError("formal first_episode_active_mask must be a [num_envs] bool tensor")
        specialist_active = self._formal_positioning_mask() & first_episode_active_mask
        if self._formal_specialist_actor is not None:
            if a2_base_obs is None:
                raise RuntimeError("formal specialist actor requires the 1620-D A2 observation")
            specialist_legs = self._formal_specialist_actor(
                a2_base_obs, applied_carrier, specialist_active
            )
            if not torch.is_tensor(specialist_legs):
                raise TypeError("formal specialist actor must return a tensor")
            self.bind_specialist_leg_action(specialist_legs, specialist_active)
        elif torch.any(specialist_active) and not torch.all(self._formal_specialist_leg_bound):
            raise RuntimeError(
                "formal specialist legs are active but no evaluator-owned actor or bound leg action exists"
            )
        specialist_legs = self._formal_specialist_leg_action
        packed, provenance = compose_formal_action(
            applied_carrier,
            specialist_legs,
            original_leg_actions,
            specialist_active,
            phase=self._formal_phase,
            primary_checkpoint=self._formal_primary_checkpoint,
            specialist_checkpoint=self._formal_specialist_checkpoint,
            original_homie_checkpoint=self._formal_original_homie_checkpoint,
        )
        return {
            "actions": packed,
            "carrier_slice": provenance["carrier_slice"],
            "legs_slice": provenance["legs_slice"],
            "provenance": provenance,
            "specialist_active": specialist_active.clone(),
            "invariant12_prime": provenance["invariant12_prime"],
        }

    def set_formal_terminal_errors(
        self, xy_error_m: torch.Tensor, yaw_error_rad: torch.Tensor
    ) -> None:
        """Supply measured terminal errors before the inherited step returns dones."""

        expected = (self.num_envs,)
        if tuple(xy_error_m.shape) != expected or tuple(yaw_error_rad.shape) != expected:
            raise ValueError(f"formal terminal errors must have shape {expected}")
        if xy_error_m.device != torch.device(self.device) or yaw_error_rad.device != torch.device(self.device):
            raise TypeError("formal terminal errors must be device-local")
        if not torch.all(torch.isfinite(xy_error_m)) or not torch.all(torch.isfinite(yaw_error_rad)):
            raise ValueError("formal terminal errors must be finite")
        self._formal_xy_error_m[:] = xy_error_m
        self._formal_yaw_error_rad[:] = yaw_error_rad

    def _record_formal_terminal_rows(self, returned_dones: torch.Tensor) -> None:
        if returned_dones.dtype != torch.bool or tuple(returned_dones.shape) != (self.num_envs,):
            raise TypeError("formal returned dones must be a [num_envs] bool tensor")
        within = (self._formal_xy_error_m <= WAYPOINT_TOLERANCE_M) & (
            self._formal_yaw_error_rad.abs() <= YAW_TOLERANCE_RAD
        )
        self._formal_hold_steps[:] = torch.where(
            within, self._formal_hold_steps + 1, torch.zeros_like(self._formal_hold_steps)
        )
        terminal = returned_dones & within & (self._formal_hold_steps >= TERMINAL_HOLD_STEPS)
        terminal &= ~self._formal_done_latched
        self._formal_done_latched |= terminal
        for env_id in torch.where(terminal)[0].tolist():
            self._formal_terminal_rows.append(
                build_formal_terminal_row(
                    sequence=str(self._formal_config.get("formal_sequence", "S1"))
                    if hasattr(self, "_formal_config")
                    else "S1",
                    bucket=self._formal_config.get("formal_closer_bucket")
                    if hasattr(self, "_formal_config")
                    else None,
                    env_id=int(env_id),
                    episode_index=0,
                    xy_error_m=float(self._formal_xy_error_m[env_id].item()),
                    yaw_error_rad=float(self._formal_yaw_error_rad[env_id].item()),
                    terminal_after_step=True,
                    specialist_checkpoint=self._formal_specialist_checkpoint,
                    original_homie_checkpoint=self._formal_original_homie_checkpoint,
                    phase=self._formal_phase,
                    primary_checkpoint=self._formal_primary_checkpoint,
                )
            )

    def step(self, actor_state):
        actions = actor_state["actions"]
        expected = (self.num_envs, HIGH_LEVEL_ACTION_DIM + FROZEN_LEG_ACTION_DIM)
        if tuple(actions.shape) != expected:
            raise ValueError(f"formal packed action must have shape {expected}")
        if not torch.all(self._formal_step_prepared):
            raise RuntimeError("formal step requires prepare_high_level_action")
        if not torch.all(self._formal_specialist_leg_bound):
            raise RuntimeError("formal step requires specialist provenance binding")
        result = super().step(actor_state)
        returned_dones = result[2]
        self._record_formal_terminal_rows(returned_dones.to(dtype=torch.bool))
        self._formal_step_prepared[:] = False
        self._formal_specialist_leg_bound[:] = False
        return result

    def consume_formal_terminal_receipts(self) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self._formal_terminal_rows]
        self._formal_terminal_rows.clear()
        return rows


DoorOpenA2PullV5_6Specialist = DoorOpenA2PullV56Specialist

__all__ = ["DoorOpenA2PullV56Specialist", "DoorOpenA2PullV5_6Specialist"]
