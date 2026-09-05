"""Quaternion mirror for the bilateral handle/pregrasp target offset."""

from __future__ import annotations


def a2_v26_6_mirror_quat_wxyz(quat_wxyz):
    """Mirror a wxyz rotation about the robot xz plane.

    For ``R -> M R M`` with ``M = diag(1, -1, 1)``, the equivalent
    quaternion transform is ``(w, x, y, z) -> (w, -x, y, -z)``.
    """
    w, x, y, z = (float(value) for value in quat_wxyz)
    return (w, -x, y, -z)
