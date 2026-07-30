"""Pure forced-semantic state writer for R2.

Only the high-level IsaacLab Articulation write methods are used.  This module
is deliberately not imported by normal policy/evaluation paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import torch


FORCED_CASES = (
    "S_SOFT_PRE_SEND_CROSS", "S_HARD_PRE_SEND_CROSS", "SEND_VALID_HOLD", "SEND_NO_HOLD",
    "POST_SEND_CROSS", "E_ROOT_CROSS_NO_CORRIDOR", "E_SEND_ACTIVATES_CORRIDOR",
    "A_PURE_BASE", "A_PURE_ARM", "A_EQUAL_CONTRIBUTION", "A_CLOSING_HINGE", "A_INVALID_REFERENCE",
    "SNAPSHOT_SWING_CLEAN", "SNAPSHOT_SWING_CONTAMINATED", "SNAPSHOT_THROUGH_SENT",
    "SNAPSHOT_THROUGH_UNSENT", "STAGED_LOAD_DERIVATIVE_WARMUP",
)


@dataclass(frozen=True)
class ForcedState:
    root_pose: torch.Tensor
    root_velocity: torch.Tensor
    joint_position: torch.Tensor
    joint_velocity: torch.Tensor

    def validate(self) -> None:
        if self.root_pose.shape != (1, 7) or self.root_velocity.shape != (1, 6):
            raise ValueError("forced root state must be [1,7] pose and [1,6] velocity")
        if self.joint_position.ndim != 2 or self.joint_velocity.shape != self.joint_position.shape:
            raise ValueError("forced joint state tensors must share [1,J] shape")
        if not all(torch.all(torch.isfinite(value)) for value in (self.root_pose, self.root_velocity, self.joint_position, self.joint_velocity)):
            raise ValueError("forced state contains non-finite values")


def write_forced_state(articulation: Any, state: ForcedState) -> None:
    """Write one forced state through the public Articulation API."""
    state.validate()
    articulation.write_root_pose_to_sim(state.root_pose)
    articulation.write_root_velocity_to_sim(state.root_velocity)
    articulation.write_joint_state_to_sim(state.joint_position, state.joint_velocity)


def validate_case_names(names: Iterable[str]) -> tuple[str, ...]:
    values = tuple(names)
    if values != FORCED_CASES:
        raise ValueError("forced semantic cases must use the exact ordered R2 case list")
    return values


def measured_trace_row(*, case: str, step_index: int, stage: int, root_x_rel_m: float,
                       hinge_position_rad: float, reward_components_scaled: Mapping[str, float],
                       terminal: bool, terminal_reason: str, send_ready: bool = False,
                       root_crossing_event: bool = False, release_event: bool = False) -> dict[str, Any]:
    if case not in FORCED_CASES:
        raise ValueError(f"unknown forced case: {case}")
    if step_index < 0 or stage < 0:
        raise ValueError("forced trace indices must be non-negative")
    values = dict(reward_components_scaled)
    if any(not isinstance(name, str) or not isinstance(value, (int, float)) or not torch.isfinite(torch.tensor(float(value))) for name, value in values.items()):
        raise ValueError("forced reward components must be finite numbers")
    return {
        "schema": "a2_piper_base_v20_R2_forced_trace_v1",
        "producer_state": "PROCESS_COMPLETED",
        "case": case,
        "run_uuid": f"forced-{case.lower()}",
        "env_id": 0,
        "step_index": step_index,
        "stage": stage,
        "root_x_rel_m": float(root_x_rel_m),
        "hinge_position_rad": float(hinge_position_rad),
        "reward_components_scaled": values,
        "terminal": bool(terminal),
        "terminal_reason": str(terminal_reason),
        "send_ready": bool(send_ready),
        "root_crossing_event": bool(root_crossing_event),
        "release_event": bool(release_event),
    }
