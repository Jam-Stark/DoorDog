"""Deployable Student observation and raw-RGB normalization surface."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import torch


def normalize_rgb_nhwc(
    rgb: torch.Tensor, *, image_mean: Sequence[float], image_std: Sequence[float]
) -> torch.Tensor:
    if rgb.ndim != 4 or rgb.shape[-1] != 3 or rgb.dtype != torch.uint8:
        raise ValueError(f"RGB input must be uint8 NHWC, got {rgb.dtype} {tuple(rgb.shape)}")
    if bool((rgb.flatten(start_dim=1).amax(dim=1) <= rgb.flatten(start_dim=1).amin(dim=1)).any()):
        raise ValueError("RGB input contains a constant frame")
    mean = torch.tensor(image_mean, dtype=torch.float32, device=rgb.device)
    std = torch.tensor(image_std, dtype=torch.float32, device=rgb.device)
    return (rgb.float() / 255.0 - mean) / std


def compose_dual_rgb(
    left: torch.Tensor,
    right: torch.Tensor,
    *,
    image_mean: Sequence[float],
    image_std: Sequence[float],
) -> torch.Tensor:
    if tuple(left.shape) != tuple(right.shape):
        raise ValueError("left/right RGB shapes differ")
    return torch.cat(
        (
            normalize_rgb_nhwc(left, image_mean=image_mean, image_std=image_std),
            normalize_rgb_nhwc(right, image_mean=image_mean, image_std=image_std),
        ),
        dim=-1,
    )


def normalize_metric_depth_nhwc(depth_m: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Normalize metric image-plane depth and return its source-validity mask.

    This is the DepthADD source contract in NHWC form: only finite values in
    the inclusive metric interval ``[0.1, 4.0]`` are valid.  Every other pixel
    is the zero invalid/missing representation.  The returned mask lets an
    augmentation caller retain that representation after operating on the
    normalized channel.
    """
    if depth_m.ndim != 4 or depth_m.shape[-1] != 1 or not depth_m.is_floating_point():
        raise ValueError(
            "metric depth must be floating-point NHWC1 distance_to_image_plane values, "
            f"got {depth_m.dtype} {tuple(depth_m.shape)}"
        )
    valid = torch.isfinite(depth_m) & (depth_m >= 0.1) & (depth_m <= 4.0)
    normalized = (depth_m - 0.1) / 3.9
    return torch.where(valid, normalized, torch.zeros_like(normalized)), valid


def compose_dual_rgbd_from_normalized_depth(
    left_rgb: torch.Tensor,
    right_rgb: torch.Tensor,
    left_depth: torch.Tensor,
    right_depth: torch.Tensor,
    *,
    image_mean: Sequence[float],
    image_std: Sequence[float],
    left_depth_valid: torch.Tensor | None = None,
    right_depth_valid: torch.Tensor | None = None,
) -> torch.Tensor:
    """Pack RGB plus normalized D435 depth, optionally restoring invalid pixels.

    ``left_depth_valid`` and ``right_depth_valid`` are the masks returned by
    :func:`normalize_metric_depth_nhwc`.  Passing them after depth augmentation
    preserves the source zero-invalid semantic without changing RGB or the
    ``[L-RGB, R-RGB, L-D, R-D]`` layout.
    """
    if tuple(left_rgb.shape) != tuple(right_rgb.shape):
        raise ValueError("left/right RGB shapes differ")
    if left_rgb.ndim != 4 or left_rgb.shape[-1] != 3 or left_rgb.dtype != torch.uint8:
        raise ValueError(f"left RGB input must be uint8 NHWC, got {left_rgb.dtype} {tuple(left_rgb.shape)}")
    if right_rgb.dtype != torch.uint8:
        raise ValueError(f"right RGB input must be uint8 NHWC, got {right_rgb.dtype} {tuple(right_rgb.shape)}")
    if tuple(left_depth.shape) != tuple(right_depth.shape):
        raise ValueError("left/right depth shapes differ")
    expected_depth_shape = (*left_rgb.shape[:-1], 1)
    if tuple(left_depth.shape) != expected_depth_shape:
        raise ValueError(
            f"left depth must have NHWC shape {expected_depth_shape}, got {tuple(left_depth.shape)}"
        )
    if not left_depth.is_floating_point() or not right_depth.is_floating_point():
        raise ValueError("normalized depth inputs must be floating-point")
    if left_rgb.device != right_rgb.device or left_rgb.device != left_depth.device or left_rgb.device != right_depth.device:
        raise ValueError("RGB-D inputs must share one device")

    def restore_invalid(depth: torch.Tensor, valid: torch.Tensor | None, name: str) -> torch.Tensor:
        if valid is None:
            return depth
        if valid.dtype != torch.bool or tuple(valid.shape) != tuple(depth.shape):
            raise ValueError(f"{name} validity mask must be bool with shape {tuple(depth.shape)}")
        if valid.device != depth.device:
            raise ValueError(f"{name} validity mask must share the depth device")
        return torch.where(valid, depth, torch.zeros_like(depth))

    return torch.cat(
        (
            normalize_rgb_nhwc(left_rgb, image_mean=image_mean, image_std=image_std),
            normalize_rgb_nhwc(right_rgb, image_mean=image_mean, image_std=image_std),
            restore_invalid(left_depth, left_depth_valid, "left depth"),
            restore_invalid(right_depth, right_depth_valid, "right depth"),
        ),
        dim=-1,
    )


def compose_dual_rgbd(
    left_rgb: torch.Tensor,
    right_rgb: torch.Tensor,
    left_depth: torch.Tensor,
    right_depth: torch.Tensor,
    *,
    image_mean: Sequence[float],
    image_std: Sequence[float],
) -> torch.Tensor:
    """Pack normalized dual-D435 RGB-D as ``[L-RGB, R-RGB, L-D, R-D]``.

    Depth must be ``distance_to_image_plane`` in metres.  Only finite values
    in inclusive ``[0.1, 4.0]`` are valid; every other pixel maps to zero.
    """
    left_depth_normalized, left_valid = normalize_metric_depth_nhwc(left_depth)
    right_depth_normalized, right_valid = normalize_metric_depth_nhwc(right_depth)
    return compose_dual_rgbd_from_normalized_depth(
        left_rgb,
        right_rgb,
        left_depth_normalized,
        right_depth_normalized,
        image_mean=image_mean,
        image_std=image_std,
        left_depth_valid=left_valid,
        right_depth_valid=right_valid,
    )


def build_actor_obs(
    components: Sequence[Mapping[str, object]], values: Mapping[str, torch.Tensor]
) -> torch.Tensor:
    ordered = []
    batch = None
    for component in components:
        name = str(component["name"])
        value = values[name]
        expected_dim = int(component["dim"])
        if value.ndim != 2 or value.shape[1] != expected_dim:
            raise ValueError(f"actor component {name} has shape {tuple(value.shape)}, expected (*,{expected_dim})")
        if batch is None:
            batch = value.shape[0]
        elif value.shape[0] != batch:
            raise ValueError("actor observation component batches differ")
        ordered.append(value * float(component["scale"]))
    return torch.cat(ordered, dim=1)
