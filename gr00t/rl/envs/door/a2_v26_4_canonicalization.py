"""Pure-Torch coordinate seam for R2 bilateral A2 canonicalization."""

from __future__ import annotations

import torch


def a2_v26_4_canonicalize_dof_values(values: torch.Tensor, right_mask: torch.Tensor) -> torch.Tensor:
    indices = torch.tensor(
        [6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 19, 18],
        device=values.device,
        dtype=torch.long,
    )
    signs = values.new_tensor(
        [-1.0, 1.0, 1.0, -1.0, 1.0, 1.0, -1.0, 1.0, 1.0, -1.0, 1.0, 1.0,
         -1.0, 1.0, 1.0, -1.0, 1.0, -1.0, -1.0, -1.0]
    )
    return torch.where(right_mask[:, None], values.index_select(1, indices) * signs, values)


def a2_v26_4_canonicalize_vector(
    values: torch.Tensor, right_mask: torch.Tensor, signs
) -> torch.Tensor:
    return torch.where(right_mask[:, None], values * values.new_tensor(signs), values)


def a2_v26_4_canonicalize_hand_force(values: torch.Tensor, right_mask: torch.Tensor) -> torch.Tensor:
    indices = torch.tensor([3, 4, 5, 0, 1, 2], device=values.device, dtype=torch.long)
    mirrored = values.index_select(1, indices) * values.new_tensor([1.0, -1.0, 1.0] * 2)
    return torch.where(right_mask[:, None], mirrored, values)


def a2_v26_4_map_action_coordinates(
    actions: torch.Tensor,
    right_mask: torch.Tensor,
    arm_default: torch.Tensor,
    action_scale: float,
    *,
    canonical_to_physical: bool,
) -> torch.Tensor:
    """Map full A2 actions between canonical actor and physical plant coordinates."""
    result = actions.clone()
    arm_signs = actions.new_tensor([-1.0, 1.0, 1.0, -1.0, 1.0, -1.0])
    arm_offset = (arm_default * arm_signs - arm_default) / action_scale
    leg_indices = torch.tensor(
        [1, 0, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10],
        device=actions.device,
        dtype=torch.long,
    )
    leg_signs = actions.new_tensor(
        [-1.0, -1.0, -1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    )
    result[:, :5] = torch.where(
        right_mask[:, None],
        actions[:, :5] * actions.new_tensor([1.0, -1.0, -1.0, 1.0, -1.0]),
        actions[:, :5],
    )
    if canonical_to_physical:
        result[:, 5:11] = torch.where(
            right_mask[:, None], actions[:, 5:11] * arm_signs + arm_offset, actions[:, 5:11]
        )
        result[:, 12:] = torch.where(
            right_mask[:, None], actions[:, 12:].index_select(1, leg_indices) * leg_signs, actions[:, 12:]
        )
    else:
        result[:, 5:11] = torch.where(
            right_mask[:, None], (actions[:, 5:11] - arm_offset) * arm_signs, actions[:, 5:11]
        )
        result[:, 12:] = torch.where(
            right_mask[:, None], actions[:, 12:].index_select(1, leg_indices) * leg_signs, actions[:, 12:]
        )
    return result


def a2_v26_4_physical_delta_origin(
    canonical_actions: torch.Tensor,
    right_mask: torch.Tensor,
    arm_default: torch.Tensor,
    action_scale: float,
) -> torch.Tensor:
    return a2_v26_4_map_action_coordinates(
        torch.zeros_like(canonical_actions),
        right_mask,
        arm_default,
        action_scale,
        canonical_to_physical=True,
    )[:, 5:11]


def a2_v26_4_accumulate_physical_delta(
    physical_delta: torch.Tensor,
    canonical_delta_increment: torch.Tensor,
    canonical_actions: torch.Tensor,
    right_mask: torch.Tensor,
    arm_default: torch.Tensor,
    action_scale: float,
    delta_action_scale: float,
    delta_action_clip: float,
    stage0_mask: torch.Tensor,
) -> torch.Tensor:
    increment_actions = torch.zeros_like(canonical_actions)
    increment_actions[:, 5:11] = canonical_delta_increment
    origin = a2_v26_4_physical_delta_origin(
        canonical_actions, right_mask, arm_default, action_scale
    )
    mapped_increment = a2_v26_4_map_action_coordinates(
        increment_actions,
        right_mask,
        arm_default,
        action_scale,
        canonical_to_physical=True,
    )[:, 5:11] - origin
    updated = torch.clamp(
        physical_delta + mapped_increment * delta_action_scale,
        -delta_action_clip,
        delta_action_clip,
    )
    updated[stage0_mask] = origin[stage0_mask]
    return updated
