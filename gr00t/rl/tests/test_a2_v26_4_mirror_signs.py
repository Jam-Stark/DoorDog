"""Mirror-sign contract for v26-4 bilateral side canonicalization.

The A2 pose observations (`relative_to_door`, `gripper_handle_transform`, and the
v26-5 gauge variant) all carry the same `[position3, tan_norm6]` layout and are
mirrored about the robot xz plane when a RIGHT-handed door is canonicalized onto
the LEFT frame.  These tests derive the correct per-component signs from the
`quat_to_tan_norm` definition instead of restating the constant, so a future edit
to either side of the seam has to stay consistent with the geometry.
"""

import torch

from gr00t.rl.envs.door.a2_v26_4_canonicalization import (
    A2_V26_4_MIRROR_POSE9_SIGNS,
    A2_V26_4_MIRROR_POSE18_SIGNS,
    a2_v26_4_canonicalize_vector,
)
from gr00t.rl.isaac_utils.rotations import quat_to_tan_norm

# Reflection about the xz plane: the y axis flips.
_MIRROR_POS = torch.tensor([1.0, -1.0, 1.0])
# For an improper M = diag(1, -1, 1), the conjugated rotation M R M keeps the
# rotation angle and negates the mirrored axis, which in xyzw quaternion terms
# is (-x, y, -z, w).
_MIRROR_QUAT = torch.tensor([-1.0, 1.0, -1.0, 1.0])


def _pose_pairs(n=512, seed=0):
    """Return (pose9, mirrored_pose9) for n random source-frame poses."""
    generator = torch.Generator().manual_seed(seed)
    quat = torch.randn(n, 4, generator=generator)
    quat = quat / quat.norm(dim=-1, keepdim=True)
    pos = torch.randn(n, 3, generator=generator)

    pose = torch.cat([pos, quat_to_tan_norm(quat, w_last=True)], dim=-1)
    mirrored = torch.cat(
        [pos * _MIRROR_POS, quat_to_tan_norm(quat * _MIRROR_QUAT, w_last=True)], dim=-1
    )
    return pose, mirrored


def test_pose9_mirror_is_a_pure_per_component_sign_flip():
    """The mirror acts as a fixed elementwise sign on [pos3, tan3, norm3]."""
    pose, mirrored = _pose_pairs()
    ratio = mirrored / pose
    # A constant elementwise sign means every sample agrees with the median.
    assert torch.allclose(ratio, ratio.median(dim=0).values.expand_as(ratio), atol=1e-5)


def test_pose9_signs_match_the_geometry_not_a_hand_written_list():
    """The published constant equals the sign derived from quat_to_tan_norm."""
    pose, mirrored = _pose_pairs()
    derived = (mirrored / pose).median(dim=0).values
    assert torch.allclose(derived, torch.tensor(A2_V26_4_MIRROR_POSE9_SIGNS), atol=1e-5)
    # All three vectors flip y only; nothing flips wholesale.
    assert tuple(A2_V26_4_MIRROR_POSE9_SIGNS) == (1.0, -1.0, 1.0) * 3


def test_canonicalizing_a_right_pose_reproduces_the_left_pose():
    """Applying the seam to a RIGHT env yields the mirrored (LEFT) observation."""
    pose, mirrored = _pose_pairs()
    right_mask = torch.ones(pose.shape[0], dtype=torch.bool)
    canonical = a2_v26_4_canonicalize_vector(pose, right_mask, A2_V26_4_MIRROR_POSE9_SIGNS)
    assert torch.allclose(canonical, mirrored, atol=1e-5)


def test_left_envs_pass_through_untouched():
    pose, _ = _pose_pairs()
    left_mask = torch.zeros(pose.shape[0], dtype=torch.bool)
    canonical = a2_v26_4_canonicalize_vector(pose, left_mask, A2_V26_4_MIRROR_POSE9_SIGNS)
    assert torch.equal(canonical, pose)


def test_pose18_is_the_pose9_contract_applied_to_handle_then_pregrasp():
    """gripper_handle_transform concatenates two poses and must not diverge."""
    assert A2_V26_4_MIRROR_POSE18_SIGNS == A2_V26_4_MIRROR_POSE9_SIGNS * 2

    handle, handle_mirrored = _pose_pairs(seed=1)
    pregrasp, pregrasp_mirrored = _pose_pairs(seed=2)
    pose18 = torch.cat([handle, pregrasp], dim=-1)
    mirrored18 = torch.cat([handle_mirrored, pregrasp_mirrored], dim=-1)

    right_mask = torch.ones(pose18.shape[0], dtype=torch.bool)
    canonical = a2_v26_4_canonicalize_vector(pose18, right_mask, A2_V26_4_MIRROR_POSE18_SIGNS)
    assert torch.allclose(canonical, mirrored18, atol=1e-5)


def test_canonicalization_is_an_involution():
    """Mirroring twice returns the original pose, so the seam cannot drift."""
    pose, _ = _pose_pairs()
    right_mask = torch.ones(pose.shape[0], dtype=torch.bool)
    once = a2_v26_4_canonicalize_vector(pose, right_mask, A2_V26_4_MIRROR_POSE9_SIGNS)
    twice = a2_v26_4_canonicalize_vector(once, right_mask, A2_V26_4_MIRROR_POSE9_SIGNS)
    assert torch.allclose(twice, pose, atol=1e-6)


def test_superseded_signs_are_rejected_by_the_geometry():
    """Regression guard: the two shipped variants this contract replaced.

    ``gripper_handle_transform`` negated the tangent wholesale (treating it as
    rotation column 2 rather than column 1) and the v26-5 gauge left position
    unmirrored.  Both must stay rejected.
    """
    pose, mirrored = _pose_pairs()
    right_mask = torch.ones(pose.shape[0], dtype=torch.bool)
    superseded = {
        "gripper_handle_transform_tangent_negated": (1, -1, 1, -1, 1, -1, 1, -1, 1),
        "v26_5_gauge_position_unmirrored": (1, 1, 1, -1, -1, -1, 1, 1, 1),
    }
    for name, signs in superseded.items():
        wrong = a2_v26_4_canonicalize_vector(pose, right_mask, [float(s) for s in signs])
        assert not torch.allclose(wrong, mirrored, atol=1e-3), name
