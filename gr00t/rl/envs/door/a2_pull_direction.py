"""Immutable direction semantics shared by push/out and pull/in door tasks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any

import torch


A2_PULL_V0_DIRECTION_CONTRACT_VERSION = "a2_piper_pull_direction_v1"

_IO_SIGN = {"in": 1, "out": -1}
_LR_SIGN = {"left": 1, "right": -1}


def _positive_finite_distance(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number; got {value!r}.")
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{field_name} must be positive and finite; got {value!r}.")
    return value


@dataclass(frozen=True, slots=True)
class A2DoorDirection:
    """Direction contract for a door task without changing hinge-angle semantics."""

    door_open_io: str
    door_open_lr: str = "right"

    def __post_init__(self) -> None:
        if self.door_open_io not in _IO_SIGN:
            raise ValueError(
                f"door_open_io must be one of {sorted(_IO_SIGN)}; got {self.door_open_io!r}."
            )
        if self.door_open_lr not in _LR_SIGN:
            raise ValueError(
                f"door_open_lr must be one of {sorted(_LR_SIGN)}; got {self.door_open_lr!r}."
            )

    @property
    def io_sign(self) -> int:
        return _IO_SIGN[self.door_open_io]

    @property
    def door_open_lr_sign(self) -> int:
        return _LR_SIGN[self.door_open_lr]

    @property
    def approach_side_x(self) -> int:
        return self.io_sign

    @property
    def travel_dir_x(self) -> int:
        return -self.io_sign

    @property
    def active_handle_face_x(self) -> int:
        return self.io_sign

    def signed_distance_to_door(self, root_x: Any, door_x: Any = 0.0) -> Any:
        """Return positive distance while the root is on the intended approach side."""

        return self.travel_dir_x * (door_x - root_x)

    def signed_crossing_progress(self, root_x: Any, door_x: Any = 0.0) -> Any:
        """Return negative progress before the frame and positive progress after crossing."""

        return self.travel_dir_x * (root_x - door_x)

    def signed_velocity_toward_door(self, root_velocity_x: Any) -> Any:
        return self.travel_dir_x * root_velocity_x

    def signed_velocity_yield_outward(self, root_velocity_x: Any) -> Any:
        return self.approach_side_x * root_velocity_x

    def active_face_position_x(self, axle_length: float) -> float:
        axle_length = _positive_finite_distance(axle_length, "axle_length")
        return self.active_handle_face_x * axle_length / 2.0

    def pregrasp_target_x(self, active_target_x: Any, offset_distance: float) -> Any:
        offset_distance = _positive_finite_distance(offset_distance, "offset_distance")
        return active_target_x + self.approach_side_x * offset_distance

    def final_target_x(self, door_x: Any, target_distance: float) -> Any:
        target_distance = _positive_finite_distance(target_distance, "target_distance")
        return door_x + self.travel_dir_x * target_distance


def _validate_stage0_tensors(root_pos: torch.Tensor, grasp_target: torch.Tensor) -> None:
    if (
        not torch.is_tensor(root_pos)
        or not torch.is_tensor(grasp_target)
        or root_pos.ndim != 2
        or root_pos.shape != grasp_target.shape
        or root_pos.shape[1] != 3
        or not root_pos.is_floating_point()
        or grasp_target.dtype != root_pos.dtype
        or grasp_target.device != root_pos.device
        or not torch.all(torch.isfinite(root_pos))
        or not torch.all(torch.isfinite(grasp_target))
    ):
        raise ValueError(
            "Signed stage0 geometry requires matching finite floating (N, 3) root/target tensors."
        )


def _validate_stage0_band(x_min: float, x_max: float, y_tol: float) -> tuple[float, float, float]:
    x_min = _positive_finite_distance(x_min, "x_min")
    x_max = _positive_finite_distance(x_max, "x_max")
    y_tol = _positive_finite_distance(y_tol, "y_tol")
    if x_max < x_min:
        raise ValueError(f"x_max must be >= x_min; got x_min={x_min}, x_max={x_max}.")
    return x_min, x_max, y_tol


def a2_signed_stage0_staging_band_mask(
    root_pos: torch.Tensor,
    grasp_target: torch.Tensor,
    x_min: float,
    x_max: float,
    y_tol: float,
    direction: A2DoorDirection,
) -> torch.Tensor:
    """Return paired-direction membership in the handle-relative stage0 band."""

    _validate_stage0_tensors(root_pos, grasp_target)
    x_min, x_max, y_tol = _validate_stage0_band(x_min, x_max, y_tol)
    signed_standoff = direction.approach_side_x * (root_pos[:, 0] - grasp_target[:, 0])
    lateral_error = root_pos[:, 1] - grasp_target[:, 1]
    return (
        (signed_standoff >= x_min)
        & (signed_standoff <= x_max)
        & (lateral_error.abs() < y_tol)
    )


def a2_signed_stage0_nearest_staging_target(
    root_pos: torch.Tensor,
    grasp_target: torch.Tensor,
    x_min: float,
    x_max: float,
    y_tol: float,
    direction: A2DoorDirection,
) -> torch.Tensor:
    """Return the nearest stage0-band point for either approach side."""

    _validate_stage0_tensors(root_pos, grasp_target)
    x_min, x_max, y_tol = _validate_stage0_band(x_min, x_max, y_tol)
    signed_standoff = direction.approach_side_x * (root_pos[:, 0] - grasp_target[:, 0])
    lateral_delta = grasp_target[:, 1] - root_pos[:, 1]
    target = grasp_target.clone()
    target[:, 0] = grasp_target[:, 0] + direction.approach_side_x * signed_standoff.clamp(
        x_min, x_max
    )
    y_boundary = torch.full_like(lateral_delta, y_tol)
    interior_y_boundary = torch.nextafter(y_boundary, torch.zeros_like(y_boundary))
    clamped_lateral_delta = torch.maximum(
        torch.minimum(lateral_delta, interior_y_boundary),
        -interior_y_boundary,
    )
    target[:, 1] = grasp_target[:, 1] - clamped_lateral_delta
    target[:, 2] = root_pos[:, 2]
    return target


def a2_pull_proof_world_offset_x(
    distance: float,
    *,
    batch_size: int,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    """Return the proof command in the shared world +X convention.

    The pull-v0 and push-anchor consumers both map this world-space command into
    the handle frame before using the high-level arm target API.  Keeping the
    direction here makes the physical sign explicit instead of inheriting a
    mode-specific local-axis assumption.
    """

    distance = _positive_finite_distance(distance, "distance")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError(f"batch_size must be a positive integer; got {batch_size!r}.")
    if not isinstance(device, torch.device):
        raise TypeError(f"device must be torch.device; got {type(device).__name__}.")
    if not isinstance(dtype, torch.dtype) or not dtype.is_floating_point:
        raise TypeError(f"dtype must be a floating torch.dtype; got {dtype!r}.")
    offset = torch.zeros((batch_size, 3), device=device, dtype=dtype)
    offset[:, 0] = distance
    return offset


__all__ = [
    "A2DoorDirection",
    "A2_PULL_V0_DIRECTION_CONTRACT_VERSION",
    "a2_signed_stage0_nearest_staging_target",
    "a2_signed_stage0_staging_band_mask",
    "a2_pull_proof_world_offset_x",
]
