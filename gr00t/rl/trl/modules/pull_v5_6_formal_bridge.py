"""CPU-safe action/provenance bridge for the Pull-v5.6 formal probe.

The formal probe keeps the v4-B pull actor as the primary policy and exposes
the newly trained specialist as a secondary, terminal-positioning-only leg
source.  This module contains only tensor layout and receipt mechanics; it
does not create an IsaacLab scene or alter the task/reward contract.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import torch


PLAN_ID = "a2_piper_pull_v5_6_formal_bridge"
TRACE_SCHEMA = "a2_piper_pull_v5_6_formal_trace_v1"
HIGH_LEVEL_ACTION_DIM = 12
FROZEN_LEG_ACTION_DIM = 12
PACKED_ACTION_DIM = HIGH_LEVEL_ACTION_DIM + FROZEN_LEG_ACTION_DIM
SPECIALIST_OBS_DIM = 1620
TERMINAL_HOLD_STEPS = 100
WAYPOINT_TOLERANCE_M = 0.05
YAW_TOLERANCE_RAD = 0.15
FORMAL_PHASES = frozenset(("anchor", "door_positioning"))

# These are the registered v5.5/v5.6 carrier limits.  They are deliberately
# kept here as a pure tensor helper so the trainer and formal evaluator share
# one layout implementation.
REGISTERED_ADAPTER_RAW_ACTION_LOW = (-0.30, 0.0, -2.0)
REGISTERED_ADAPTER_RAW_ACTION_HIGH = (0.0, 0.24, 2.0)


def validate_carrier(carrier: torch.Tensor) -> None:
    """Validate the canonical 12-D carrier without changing it."""

    if (
        not torch.is_tensor(carrier)
        or carrier.shape[-1] != HIGH_LEVEL_ACTION_DIM
        or not carrier.is_floating_point()
        or not torch.all(torch.isfinite(carrier))
    ):
        raise ValueError("v5.6 carrier must be a finite floating 12-D tensor")
    if not torch.all(carrier[..., 3:11] == 0.0) or not torch.all(carrier[..., 11] == 1.0):
        raise ValueError("v5.6 carrier padding must be zeros/open gripper")


def carrier_from_goal_error(goal_error: torch.Tensor) -> torch.Tensor:
    """Encode ``[x, y, yaw]`` error into the registered 12-D carrier."""

    if (
        not torch.is_tensor(goal_error)
        or goal_error.shape[-1] != 3
        or not goal_error.is_floating_point()
        or not torch.all(torch.isfinite(goal_error))
    ):
        raise ValueError("v5.6 goal error must be finite floating (ex, ey, wrapped eyaw)")
    low = goal_error.new_tensor(REGISTERED_ADAPTER_RAW_ACTION_LOW)
    high = goal_error.new_tensor(REGISTERED_ADAPTER_RAW_ACTION_HIGH)
    command = torch.clamp(goal_error, min=low, max=high)
    carrier = torch.zeros(
        *command.shape[:-1], HIGH_LEVEL_ACTION_DIM,
        dtype=command.dtype,
        device=command.device,
    )
    carrier[..., :3] = command
    carrier[..., 11] = 1.0
    validate_carrier(carrier)
    return carrier


def inject_carrier_into_a2_obs(
    a2_base_obs: torch.Tensor, applied_carrier: torch.Tensor
) -> torch.Tensor:
    """Inject the applied carrier into the final 54-D A2 observation frame."""

    if (
        not torch.is_tensor(a2_base_obs)
        or a2_base_obs.shape[-1] != SPECIALIST_OBS_DIM
        or a2_base_obs.shape[:-1] != applied_carrier.shape[:-1]
    ):
        raise ValueError("v5.6 A2 observation/carrier leading shapes must match")
    validate_carrier(applied_carrier)
    injected = a2_base_obs.clone()
    frame_start = SPECIALIST_OBS_DIM - 54
    multipliers = applied_carrier.new_tensor((2.0, 2.0, 0.25, 1.0, 1.0))
    physical_command = torch.cat(
        (
            applied_carrier[..., :3] * 0.25,
            applied_carrier[..., 3:5].clamp(-1.0, 1.0) * 0.4,
        ),
        dim=-1,
    ) * multipliers
    injected[..., frame_start + 39 : frame_start + 44] = physical_command
    return injected


def _validate_leg_action(leg_action: torch.Tensor, label: str) -> None:
    if (
        not torch.is_tensor(leg_action)
        or leg_action.shape[-1] != FROZEN_LEG_ACTION_DIM
        or not leg_action.is_floating_point()
        or not torch.all(torch.isfinite(leg_action))
    ):
        raise ValueError(f"{label} must be a finite floating 12-D leg action")


def compose_formal_action(
    carrier: torch.Tensor,
    specialist_legs: torch.Tensor,
    original_homie_legs: torch.Tensor,
    specialist_active: torch.Tensor,
    *,
    phase: str,
    primary_checkpoint: str,
    specialist_checkpoint: str,
    original_homie_checkpoint: str,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Pack carrier plus selected legs and return immutable provenance.

    A specialist leg may be selected only during the two formal positioning
    phases.  Inactive legs are always the original HOMIE result.  The base
    carrier slice is never rewritten by this helper.
    """

    validate_carrier(carrier)
    _validate_leg_action(specialist_legs, "specialist leg action")
    _validate_leg_action(original_homie_legs, "original HOMIE leg action")
    if specialist_legs.shape[:-1] != carrier.shape[:-1] or original_homie_legs.shape[:-1] != carrier.shape[:-1]:
        raise ValueError("formal bridge carrier and leg leading shapes must match")
    if (
        not torch.is_tensor(specialist_active)
        or specialist_active.dtype != torch.bool
        or specialist_active.shape != carrier.shape[:-1]
        or specialist_active.device != carrier.device
    ):
        raise ValueError("formal specialist_active must be a device-local bool mask")
    if phase not in FORMAL_PHASES and bool(torch.any(specialist_active)):
        raise RuntimeError(
            "v5.6 specialist is terminal-positioning-only; active selection outside "
            f"{sorted(FORMAL_PHASES)} is invalid: {phase!r}"
        )
    for name, value in (
        ("primary_checkpoint", primary_checkpoint),
        ("specialist_checkpoint", specialist_checkpoint),
        ("original_homie_checkpoint", original_homie_checkpoint),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(f"formal bridge requires a non-empty {name}")
    if primary_checkpoint == specialist_checkpoint or specialist_checkpoint == original_homie_checkpoint:
        raise ValueError("formal primary, specialist, and original checkpoints must be distinct")
    selected_legs = torch.where(specialist_active.unsqueeze(-1), specialist_legs, original_homie_legs)
    packed = torch.cat((carrier, selected_legs), dim=-1)
    if packed.shape[-1] != PACKED_ACTION_DIM:
        raise RuntimeError("formal bridge packed action lost the 12+12 action layout")
    return packed, {
        "plan_id": PLAN_ID,
        "phase": phase,
        "carrier_slice": [0, HIGH_LEVEL_ACTION_DIM],
        "legs_slice": [HIGH_LEVEL_ACTION_DIM, PACKED_ACTION_DIM],
        "specialist_active": specialist_active.detach().clone(),
        "primary_actor": "v4-B",
        "primary_checkpoint": primary_checkpoint,
        "specialist_checkpoint": specialist_checkpoint,
        "original_homie_checkpoint": original_homie_checkpoint,
        "scientific_denominator_included": False,
        "denominator_scope": "none",
        "invariant12_prime": "specialist_terminal_positioning_only",
    }


class PullV56FormalBridge:
    """Deterministic secondary specialist bridge for evaluator-owned actions."""

    def __init__(
        self,
        primary_actor: Callable[[torch.Tensor], torch.Tensor],
        original_homie_actor: Callable[[torch.Tensor], torch.Tensor],
        *,
        primary_checkpoint: str,
        specialist_checkpoint: str,
        original_homie_checkpoint: str,
    ) -> None:
        if not callable(primary_actor) or not callable(original_homie_actor):
            raise TypeError("formal bridge requires callable primary and original actors")
        self.primary_actor = primary_actor
        self.original_homie_actor = original_homie_actor
        self.primary_checkpoint = primary_checkpoint
        self.specialist_checkpoint = specialist_checkpoint
        self.original_homie_checkpoint = original_homie_checkpoint

    def __call__(
        self,
        a2_base_obs: torch.Tensor,
        carrier: torch.Tensor,
        specialist_active: torch.Tensor,
        *,
        phase: str,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        injected = inject_carrier_into_a2_obs(a2_base_obs, carrier)
        specialist_legs = self.primary_actor(injected)
        original_legs = self.original_homie_actor(injected)
        return compose_formal_action(
            carrier,
            specialist_legs,
            original_legs,
            specialist_active,
            phase=phase,
            primary_checkpoint=self.primary_checkpoint,
            specialist_checkpoint=self.specialist_checkpoint,
            original_homie_checkpoint=self.original_homie_checkpoint,
        )


def build_formal_terminal_row(
    *,
    sequence: str,
    bucket: str | None,
    env_id: int,
    episode_index: int,
    xy_error_m: float,
    yaw_error_rad: float,
    terminal_after_step: bool,
    specialist_checkpoint: str,
    original_homie_checkpoint: str,
    phase: str,
    primary_checkpoint: str,
    specialist_active: bool = True,
) -> dict[str, Any]:
    """Create one terminal-only, denominator-excluded formal receipt row."""

    if phase not in FORMAL_PHASES:
        raise ValueError(f"formal terminal row phase must be one of {sorted(FORMAL_PHASES)}")
    if isinstance(env_id, bool) or env_id < 0 or isinstance(episode_index, bool) or episode_index < 0:
        raise ValueError("formal terminal row ids must be non-negative integers")
    if not isinstance(terminal_after_step, bool) or not terminal_after_step:
        raise ValueError("formal terminal rows must bind to returned env.step dones")
    if not isinstance(xy_error_m, (int, float)) or not isinstance(yaw_error_rad, (int, float)):
        raise TypeError("formal terminal errors must be numeric")
    if not torch.isfinite(torch.tensor(float(xy_error_m))) or not torch.isfinite(torch.tensor(float(yaw_error_rad))):
        raise ValueError("formal terminal errors must be finite")
    if float(xy_error_m) > WAYPOINT_TOLERANCE_M or abs(float(yaw_error_rad)) > YAW_TOLERANCE_RAD:
        raise ValueError("formal terminal row exceeds the 0.05 m/0.15 rad admission tolerance")
    if not specialist_active:
        raise ValueError("formal anchor/door terminal receipt requires specialist_active=true")
    return {
        "schema": TRACE_SCHEMA,
        "plan_id": PLAN_ID,
        "record_class": "interface_characterization",
        "sequence": sequence,
        "closer_bucket": bucket,
        "env_id": int(env_id),
        "episode_index": int(episode_index),
        "episode_id": f"formal:{phase}:{sequence}:env{env_id}:episode{episode_index}",
        "phase": phase,
        "terminal_after_step": True,
        "returned_dones_binding": "env.step returned dones",
        "terminal_current_state": True,
        "done": True,
        "terminal_hold_steps": TERMINAL_HOLD_STEPS,
        "xy_error_m": float(xy_error_m),
        "yaw_error_rad": float(yaw_error_rad),
        "specialist_active": True,
        "specialist_checkpoint": specialist_checkpoint,
        "primary_checkpoint": primary_checkpoint,
        "original_homie_checkpoint": original_homie_checkpoint,
        "scientific_denominator_included": False,
        "denominator_scope": "none",
        "invariant12_prime": {
            "status": "PASS",
            "specialist_terminal_positioning_only": True,
            "checked_rows": 1,
        },
    }


__all__ = [
    "FORMAL_PHASES",
    "FROZEN_LEG_ACTION_DIM",
    "HIGH_LEVEL_ACTION_DIM",
    "PACKED_ACTION_DIM",
    "PLAN_ID",
    "PullV56FormalBridge",
    "SPECIALIST_OBS_DIM",
    "TERMINAL_HOLD_STEPS",
    "TRACE_SCHEMA",
    "WAYPOINT_TOLERANCE_M",
    "YAW_TOLERANCE_RAD",
    "build_formal_terminal_row",
    "carrier_from_goal_error",
    "compose_formal_action",
    "inject_carrier_into_a2_obs",
    "validate_carrier",
]
