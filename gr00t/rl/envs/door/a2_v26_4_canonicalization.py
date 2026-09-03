"""Pure-Torch coordinate seam for R2 bilateral A2 canonicalization."""

from __future__ import annotations

import torch

# Mirror signs for a (position3, tan_norm6) pose expressed in a source frame,
# reflected about the robot xz plane (M = diag(1, -1, 1)).
#
# ``quat_to_tan_norm`` returns [R @ e_x, R @ e_z].  The conjugated rotation
# M R M leaves both reference axes fixed (M e_x = e_x, M e_z = e_z), so the
# mirrored columns are M @ (R @ e_x) and M @ (R @ e_z).  Position mirrors the
# same way.  Every one of the three vectors therefore flips its y component
# only.  Any pose term that reuses this layout must use these signs; see
# ``gr00t/rl/tests/test_a2_v26_4_mirror_signs.py``.
A2_V26_4_MIRROR_POSE9_SIGNS = (1.0, -1.0, 1.0, 1.0, -1.0, 1.0, 1.0, -1.0, 1.0)

# Handle pose followed by pregrasp pose, as built by gripper_handle_transform.
A2_V26_4_MIRROR_POSE18_SIGNS = A2_V26_4_MIRROR_POSE9_SIGNS * 2


def a2_v26_6_mirror_quat_wxyz(quat_wxyz):
    """Mirror a rotation about the robot xz plane: R -> M R M with M = diag(1, -1, 1).

    M is improper, so the conjugated rotation negates the mirrored axis components
    while keeping the angle.  In wxyz terms that is (w, -x, y, -z).

    The handle/pregrasp ``FrameCfg`` offsets are authored for a RIGHT-hinged door.
    That offset is *not* mirror-invariant -- ``M R M`` differs from ``R`` by 180
    degrees -- so a LEFT-hinged clone must use the mirrored offset instead of
    reusing the authored one.  See
    ``gr00t/rl/tests/test_a2_v26_6_handle_offset_mirror.py``.
    """
    w, x, y, z = (float(v) for v in quat_wxyz)
    return (w, -x, y, -z)


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
