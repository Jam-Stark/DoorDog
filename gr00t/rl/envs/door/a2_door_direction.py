"""Pure direction contracts shared by the A2 push and pull door routes.

The helpers in this module intentionally have no Isaac Sim/IsaacLab imports.  They
are used by the environment for tensor geometry and by no-simulator tests for the
direction, target-mirroring, and signed-progress contracts.
"""

from __future__ import annotations

import math

import torch


DOOR_MODE_PUSH = "push"
DOOR_MODE_PULL = "pull"
DOOR_OPEN_IO_OUT = -1.0
DOOR_OPEN_IO_IN = 1.0

PUSH_PREGRASP_OFFSET = (-0.10, 0.0, 0.0)
PUSH_PREGRASP_ROTATION_WXYZ = (0.5, 0.5, 0.5, 0.5)
PULL_PREGRASP_OFFSET = (0.10, 0.0, 0.0)
# q_z(pi) ⊗ q_push, using the WXYZ convention.  The direct product is
# (-0.5, -0.5, 0.5, 0.5); this canonical positive-W form is sign-equivalent.
PULL_PREGRASP_ROTATION_WXYZ = (0.5, 0.5, -0.5, -0.5)


def validate_door_mode(mode: str) -> str:
    """Validate and return the explicit A2 task mode."""
    if not isinstance(mode, str) or mode not in (DOOR_MODE_PUSH, DOOR_MODE_PULL):
        raise ValueError(
            "A2 door task mode must be exactly 'push' or 'pull'; "
            f"got {mode!r}."
        )
    return mode


def expected_open_io_sign(mode: str) -> float:
    """Return the generator metadata sign required by ``mode``."""
    mode = validate_door_mode(mode)
    return DOOR_OPEN_IO_OUT if mode == DOOR_MODE_PUSH else DOOR_OPEN_IO_IN


def validate_open_io_metadata(mode: str, metadata_signs: torch.Tensor) -> torch.Tensor:
    """Fail-fast validate per-environment ``doorOpenIO`` metadata.

    ``door.py`` authors ``out`` as ``-1`` and ``in`` as ``+1``.  The returned
    tensor is the original tensor so callers can use it as the direction label.
    """
    expected = expected_open_io_sign(mode)
    if (
        not torch.is_tensor(metadata_signs)
        or metadata_signs.ndim != 1
        or not metadata_signs.is_floating_point()
        or not torch.all(torch.isfinite(metadata_signs))
        or not torch.all(torch.isclose(metadata_signs.abs(), torch.ones_like(metadata_signs)))
        or not torch.all(torch.isclose(metadata_signs, torch.full_like(metadata_signs, expected)))
    ):
        values = None if not torch.is_tensor(metadata_signs) else metadata_signs.detach().cpu().tolist()
        raise ValueError(
            "doorOpenIO metadata does not match the configured A2 task mode; "
            f"mode={mode!r}, expected={expected:+.0f}, values={values!r}."
        )
    return metadata_signs


def _validate_quaternion(quaternion_wxyz: torch.Tensor, context: str) -> None:
    if (
        not torch.is_tensor(quaternion_wxyz)
        or quaternion_wxyz.ndim < 1
        or quaternion_wxyz.shape[-1] != 4
        or not quaternion_wxyz.is_floating_point()
        or not torch.all(torch.isfinite(quaternion_wxyz))
    ):
        shape = None if not torch.is_tensor(quaternion_wxyz) else tuple(quaternion_wxyz.shape)
        raise ValueError(f"{context} requires finite floating (..., 4) WXYZ quaternions; got {shape}.")
    norms = torch.linalg.norm(quaternion_wxyz, dim=-1)
    if not torch.allclose(norms, torch.ones_like(norms), atol=1.0e-5, rtol=0.0):
        raise ValueError(f"{context} requires unit WXYZ quaternions; norms={norms.detach().cpu().tolist()}.")


def quat_mul_wxyz(quaternion_a: torch.Tensor, quaternion_b: torch.Tensor) -> torch.Tensor:
    """Multiply WXYZ quaternions with broadcast-compatible leading dimensions."""
    _validate_quaternion(quaternion_a, "quat_mul_wxyz quaternion_a")
    _validate_quaternion(quaternion_b, "quat_mul_wxyz quaternion_b")
    if quaternion_a.device != quaternion_b.device or quaternion_a.dtype != quaternion_b.dtype:
        raise ValueError("quat_mul_wxyz inputs must share dtype and device.")
    w_a, x_a, y_a, z_a = quaternion_a.unbind(-1)
    w_b, x_b, y_b, z_b = quaternion_b.unbind(-1)
    result = torch.stack(
        (
            w_a * w_b - x_a * x_b - y_a * y_b - z_a * z_b,
            w_a * x_b + x_a * w_b + y_a * z_b - z_a * y_b,
            w_a * y_b - x_a * z_b + y_a * w_b + z_a * x_b,
            w_a * z_b + x_a * y_b - y_a * x_b + z_a * w_b,
        ),
        dim=-1,
    )
    return result / torch.linalg.norm(result, dim=-1, keepdim=True)


def quat_apply_wxyz(quaternion_wxyz: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
    """Rotate vectors by unit WXYZ quaternions."""
    _validate_quaternion(quaternion_wxyz, "quat_apply_wxyz quaternion")
    if (
        not torch.is_tensor(vector)
        or vector.shape[-1] != 3
        or vector.device != quaternion_wxyz.device
        or vector.dtype != quaternion_wxyz.dtype
        or not torch.all(torch.isfinite(vector))
    ):
        shape = None if not torch.is_tensor(vector) else tuple(vector.shape)
        raise ValueError(
            "quat_apply_wxyz vector must be finite (..., 3) with matching dtype/device; "
            f"got {shape}."
        )
    q_vector = quaternion_wxyz[..., 1:]
    uv = torch.cross(q_vector, vector, dim=-1)
    uuv = torch.cross(q_vector, uv, dim=-1)
    return vector + 2.0 * (quaternion_wxyz[..., :1] * uv + uuv)


def horizontal_door_directions(
    door_root_quat_wxyz: torch.Tensor, approach_sign: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return approach, through, and lateral world directions from door-frame X/Y.

    The door's local +X is the closed-door normal.  ``approach_sign`` is the
    authored ``doorOpenIO`` value, so out/push approaches along local -X and
    in/pull approaches along local +X.  All outputs are horizontal unit vectors.
    """
    _validate_quaternion(door_root_quat_wxyz, "horizontal_door_directions door_root_quat_wxyz")
    if (
        not torch.is_tensor(approach_sign)
        or approach_sign.shape != door_root_quat_wxyz.shape[:-1]
        or approach_sign.device != door_root_quat_wxyz.device
        or approach_sign.dtype != door_root_quat_wxyz.dtype
        or not torch.all(torch.isfinite(approach_sign))
        or not torch.all(torch.isclose(approach_sign.abs(), torch.ones_like(approach_sign)))
    ):
        shape = None if not torch.is_tensor(approach_sign) else tuple(approach_sign.shape)
        raise ValueError(
            "horizontal_door_directions requires ±1 approach_sign matching quaternion batch; "
            f"got {shape}."
        )
    local_x = door_root_quat_wxyz.new_tensor((1.0, 0.0, 0.0)).expand_as(door_root_quat_wxyz[..., :3])
    local_y = door_root_quat_wxyz.new_tensor((0.0, 1.0, 0.0)).expand_as(door_root_quat_wxyz[..., :3])
    door_x_w = quat_apply_wxyz(door_root_quat_wxyz, local_x)
    door_y_w = quat_apply_wxyz(door_root_quat_wxyz, local_y)
    door_x_w = door_x_w.clone()
    door_y_w = door_y_w.clone()
    door_x_w[..., 2] = 0.0
    door_y_w[..., 2] = 0.0
    x_norm = torch.linalg.norm(door_x_w, dim=-1, keepdim=True)
    y_norm = torch.linalg.norm(door_y_w, dim=-1, keepdim=True)
    if torch.any(x_norm <= 0.0) or torch.any(y_norm <= 0.0):
        raise ValueError("horizontal_door_directions requires a non-degenerate horizontal door frame.")
    door_x_w = door_x_w / x_norm
    door_y_w = door_y_w / y_norm
    approach_w = approach_sign[..., None] * door_x_w
    through_w = -approach_w
    return approach_w, through_w, door_y_w


def signed_progress(
    root_pos_w: torch.Tensor, door_root_pos_w: torch.Tensor, direction_w: torch.Tensor
) -> torch.Tensor:
    """Project root displacement onto a signed horizontal direction."""
    if (
        not torch.is_tensor(root_pos_w)
        or not torch.is_tensor(door_root_pos_w)
        or not torch.is_tensor(direction_w)
    ):
        raise ValueError("signed_progress requires matching finite (...,3) tensors.")
    if (
        root_pos_w.ndim < 1
        or root_pos_w.shape[-1] != 3
        or door_root_pos_w.shape != root_pos_w.shape
        or direction_w.shape != root_pos_w.shape
        or root_pos_w.dtype != door_root_pos_w.dtype
        or root_pos_w.dtype != direction_w.dtype
        or root_pos_w.device != door_root_pos_w.device
        or root_pos_w.device != direction_w.device
        or not torch.all(torch.isfinite(root_pos_w))
        or not torch.all(torch.isfinite(door_root_pos_w))
        or not torch.all(torch.isfinite(direction_w))
    ):
        raise ValueError("signed_progress requires matching finite (...,3) tensors.")
    return torch.sum((root_pos_w - door_root_pos_w) * direction_w, dim=-1)


def select_pull_stage4_target_root_pos(
    stage_buf: torch.Tensor,
    stage_swing: int,
    clearance_target_root_pos: torch.Tensor,
    through_target_root_pos: torch.Tensor,
) -> torch.Tensor:
    """Keep pull stage4 on the approach-side clearance target.

    The clearance predicate controls stage4 -> stage5 transition, but it must
    not switch the stage4 distance reward to the through-door target.  This
    selector therefore depends only on the stage state: every pull stage4
    environment uses ``clearance_target_root_pos`` until the stage advances.
    """
    if (
        not torch.is_tensor(stage_buf)
        or stage_buf.ndim != 1
        or not torch.is_tensor(clearance_target_root_pos)
        or not torch.is_tensor(through_target_root_pos)
        or clearance_target_root_pos.shape != (stage_buf.shape[0], 3)
        or through_target_root_pos.shape != clearance_target_root_pos.shape
        or clearance_target_root_pos.device != stage_buf.device
        or through_target_root_pos.device != stage_buf.device
        or clearance_target_root_pos.dtype != through_target_root_pos.dtype
        or not torch.all(torch.isfinite(clearance_target_root_pos))
        or not torch.all(torch.isfinite(through_target_root_pos))
    ):
        raise ValueError(
            "select_pull_stage4_target_root_pos requires stage (N,) and finite "
            "matching target (N,3) tensors."
        )
    use_clearance_target = (stage_buf == stage_swing)[:, None]
    return torch.where(use_clearance_target, clearance_target_root_pos, through_target_root_pos)


def a2_stage5_reward_gate(door_opened: torch.Tensor, handle_up: torch.Tensor) -> torch.Tensor:
    """Return the persistent A2 stage5 reward invariant.

    Once stage5 is entered, reward remains active while the door stays open and
    the handle stays up; transit/clearance geometry is intentionally absent.
    """
    if (
        not torch.is_tensor(door_opened)
        or not torch.is_tensor(handle_up)
        or door_opened.ndim != 1
        or handle_up.shape != door_opened.shape
        or door_opened.dtype != torch.bool
        or handle_up.dtype != torch.bool
        or handle_up.device != door_opened.device
    ):
        raise ValueError(
            "a2_stage5_reward_gate requires matching one-dimensional boolean tensors."
        )
    return door_opened & handle_up


def heading_error_rad(robot_root_quat_wxyz: torch.Tensor, desired_heading_w: torch.Tensor) -> torch.Tensor:
    """Return absolute horizontal yaw error between robot +X and desired heading."""
    _validate_quaternion(robot_root_quat_wxyz, "heading_error_rad robot_root_quat_wxyz")
    if desired_heading_w.shape != robot_root_quat_wxyz.shape[:-1] + (3,):
        raise ValueError("heading_error_rad desired heading shape must match quaternion batch.")
    robot_forward = quat_apply_wxyz(
        robot_root_quat_wxyz,
        robot_root_quat_wxyz.new_tensor((1.0, 0.0, 0.0)).expand_as(desired_heading_w),
    )
    robot_forward = robot_forward.clone()
    desired_heading = desired_heading_w.clone()
    robot_forward[..., 2] = 0.0
    desired_heading[..., 2] = 0.0
    robot_norm = torch.linalg.norm(robot_forward, dim=-1, keepdim=True)
    desired_norm = torch.linalg.norm(desired_heading, dim=-1, keepdim=True)
    if torch.any(robot_norm <= 0.0) or torch.any(desired_norm <= 0.0):
        raise ValueError("heading_error_rad requires non-degenerate horizontal headings.")
    robot_forward = robot_forward / robot_norm
    desired_heading = desired_heading / desired_norm
    dot = torch.sum(robot_forward * desired_heading, dim=-1).clamp(-1.0, 1.0)
    cross_z = robot_forward[..., 0] * desired_heading[..., 1] - robot_forward[..., 1] * desired_heading[..., 0]
    return torch.atan2(cross_z.abs(), dot)


def pregrasp_rotation_for_pull(push_rotation_wxyz: torch.Tensor) -> torch.Tensor:
    """Compose a closed-door-local +Z half-turn on the push target rotation."""
    if tuple(push_rotation_wxyz.shape) != (4,):
        raise ValueError("pregrasp_rotation_for_pull requires one WXYZ quaternion of shape (4,).")
    q_pi = push_rotation_wxyz.new_tensor((0.0, 0.0, 0.0, 1.0))
    result = quat_mul_wxyz(q_pi, push_rotation_wxyz)
    return torch.where(result[0] < 0.0, -result, result)


def configured_pregrasp_spec(mode: str) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    """Return canonical static specs used by the push/pull config files."""
    mode = validate_door_mode(mode)
    if mode == DOOR_MODE_PUSH:
        return PUSH_PREGRASP_OFFSET, PUSH_PREGRASP_ROTATION_WXYZ
    return PULL_PREGRASP_OFFSET, PULL_PREGRASP_ROTATION_WXYZ


def finite_positive(value: float, context: str) -> float:
    """Small scalar validator used by no-sim tests and environment config readers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{context} must be finite; got {value!r}.")
    value = float(value)
    if value <= 0.0:
        raise ValueError(f"{context} must be > 0.0; got {value}.")
    return value
