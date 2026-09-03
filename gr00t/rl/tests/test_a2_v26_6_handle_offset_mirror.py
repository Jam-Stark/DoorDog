"""Side-conditioned handle/pregrasp target offset for bilateral doors.

The authored ``FrameCfg`` offset ``(0.5, 0.5, 0.5, 0.5)`` was tuned on the
RIGHT-hinged door of the v19-v25 single-side lineage.  It is not mirror
invariant, so a LEFT-hinged clone that reuses it receives a grasp target rotated
180 degrees away from the correct pose.  These tests derive the mirror from the
rotation algebra rather than restating the shipped numbers.
"""

import numpy as np
import pytest

from gr00t.rl.envs.door.a2_v26_4_canonicalization import a2_v26_6_mirror_quat_wxyz

# The authored offset, as it appears in door_open_a2_base.scene_creation_callback.
AUTHORED_OFFSET_WXYZ = (0.5, 0.5, 0.5, 0.5)
MIRROR = np.diag([1.0, -1.0, 1.0])


def rot_from_wxyz(q):
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def angle_between(a, b):
    return np.degrees(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1)))


# arccos loses precision near +/-1, so a half-turn is only resolvable to about
# 1e-3 degrees.  That is still four orders of magnitude tighter than the defect
# this suite guards against.
HALF_TURN_TOL_DEG = 1e-3


def random_unit_quats(n, seed):
    rng = np.random.default_rng(seed)
    q = rng.normal(size=(n, 4))
    return q / np.linalg.norm(q, axis=1, keepdims=True)


def test_mirror_helper_matches_the_conjugated_rotation():
    """(w, -x, y, -z) must equal M R M for every rotation, not just the offset."""
    for q in random_unit_quats(512, seed=0):
        got = rot_from_wxyz(a2_v26_6_mirror_quat_wxyz(q))
        want = MIRROR @ rot_from_wxyz(q) @ MIRROR
        assert np.allclose(got, want, atol=1e-9)


def test_mirror_is_an_involution():
    for q in random_unit_quats(256, seed=1):
        twice = a2_v26_6_mirror_quat_wxyz(a2_v26_6_mirror_quat_wxyz(q))
        assert np.allclose(rot_from_wxyz(twice), rot_from_wxyz(q), atol=1e-9)


def test_authored_offset_is_not_mirror_invariant():
    """This is the defect: reusing the RIGHT offset on LEFT is a 180 degree error."""
    authored = rot_from_wxyz(AUTHORED_OFFSET_WXYZ)
    mirrored = rot_from_wxyz(a2_v26_6_mirror_quat_wxyz(AUTHORED_OFFSET_WXYZ))
    assert not np.allclose(authored, mirrored, atol=1e-6)
    assert angle_between(authored, mirrored) == pytest.approx(180.0, abs=HALF_TURN_TOL_DEG)


def test_mirrored_authored_offset_has_the_expected_value():
    assert a2_v26_6_mirror_quat_wxyz(AUTHORED_OFFSET_WXYZ) == (0.5, -0.5, 0.5, -0.5)


def test_mirroring_composes_with_the_grasp_target_pose():
    """mirror(R_grasp @ R_offset) == mirror(R_grasp) @ mirror(R_offset).

    The shipped code computes ``mirror(R_grasp) @ R_offset``.  This test pins the
    identity that makes that wrong whenever R_offset is not mirror invariant.
    """
    offset = rot_from_wxyz(AUTHORED_OFFSET_WXYZ)
    offset_mirrored = rot_from_wxyz(a2_v26_6_mirror_quat_wxyz(AUTHORED_OFFSET_WXYZ))
    for q in random_unit_quats(256, seed=2):
        grasp = rot_from_wxyz(q)
        grasp_mirrored = MIRROR @ grasp @ MIRROR

        correct = MIRROR @ (grasp @ offset) @ MIRROR
        assert np.allclose(grasp_mirrored @ offset_mirrored, correct, atol=1e-9)

        shipped = grasp_mirrored @ offset
        assert angle_between(shipped, correct) == pytest.approx(180.0, abs=HALF_TURN_TOL_DEG)
