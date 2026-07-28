"""Fail-fast composition helpers for A2 Student policy cameras."""

from __future__ import annotations

from collections.abc import Sequence

import torch
import torch.nn.functional as F


def _resolution(value: Sequence[int], name: str) -> tuple[int, int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be an explicit [height, width] sequence")
    values = tuple(value)
    if len(values) != 2 or any(
        isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in values
    ):
        raise ValueError(f"{name} must contain positive integer [height, width]; got {value!r}")
    return values


def _raw_rgb(name: str, value: torch.Tensor, shape: tuple[int, int, int, int]) -> torch.Tensor:
    if not torch.is_tensor(value) or value.dtype != torch.uint8 or tuple(value.shape) != shape:
        raise ValueError(
            f"{name} must be raw uint8 NHWC with shape {shape}; "
            f"got dtype={getattr(value, 'dtype', None)} shape={getattr(value, 'shape', None)}"
        )
    flat = value.flatten(start_dim=1)
    invalid = flat.amax(dim=1) <= flat.amin(dim=1)
    if bool(invalid.any().item()):
        first = int(torch.nonzero(invalid, as_tuple=False)[0].item())
        raise ValueError(f"{name} contains a constant/uninitialized frame at environment {first}")
    return value


def _normalization_vector(value: Sequence[float], name: str, device) -> torch.Tensor:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be an explicit three-value sequence")
    values = tuple(value)
    if len(values) != 3 or any(isinstance(item, bool) for item in values):
        raise ValueError(f"{name} must contain exactly three numeric values; got {value!r}")
    tensor = torch.tensor(values, device=device, dtype=torch.float32)
    if not bool(torch.all(torch.isfinite(tensor)).item()):
        raise ValueError(f"{name} must contain finite values")
    return tensor


def compose_horizontal_letterboxed_rgb(
    primary_rgb: torch.Tensor,
    secondary_rgb: torch.Tensor,
    *,
    primary_resolution: Sequence[int],
    secondary_resolution: Sequence[int],
    output_resolution: Sequence[int],
    image_mean: Sequence[float],
    image_std: Sequence[float],
) -> torch.Tensor:
    """Normalize and join two synchronized raw RGB views into one NHWC policy tensor."""
    primary_height, primary_width = _resolution(primary_resolution, "primary_resolution")
    secondary_height, secondary_width = _resolution(
        secondary_resolution, "secondary_resolution"
    )
    output_height, output_width = _resolution(output_resolution, "output_resolution")
    if output_height != primary_height or output_width != primary_width + secondary_width:
        raise ValueError(
            "output_resolution must be [primary_height, primary_width + secondary_width]; "
            f"got output={(output_height, output_width)} primary={(primary_height, primary_width)} "
            f"secondary={(secondary_height, secondary_width)}"
        )
    if secondary_height > output_height:
        raise ValueError("secondary camera height cannot exceed the policy output height")
    if primary_rgb.device != secondary_rgb.device:
        raise ValueError(
            f"policy camera tensors must share one device: {primary_rgb.device} vs {secondary_rgb.device}"
        )
    batch_size = int(primary_rgb.shape[0]) if torch.is_tensor(primary_rgb) and primary_rgb.ndim else 0
    _raw_rgb(
        "primary policy camera",
        primary_rgb,
        (batch_size, primary_height, primary_width, 3),
    )
    _raw_rgb(
        "secondary policy camera",
        secondary_rgb,
        (batch_size, secondary_height, secondary_width, 3),
    )
    mean = _normalization_vector(image_mean, "image_mean", primary_rgb.device)
    std = _normalization_vector(image_std, "image_std", primary_rgb.device)
    if bool(torch.any(std <= 0.0).item()):
        raise ValueError("image_std must contain strictly positive values")

    primary = (primary_rgb.float() / 255.0 - mean) / std
    secondary = (secondary_rgb.float() / 255.0 - mean) / std
    padding = output_height - secondary_height
    pad_top = padding // 2
    pad_bottom = padding - pad_top
    secondary = F.pad(secondary, (0, 0, 0, 0, pad_top, pad_bottom), value=0.0)
    output = torch.cat((primary, secondary), dim=2)
    expected_shape = (batch_size, output_height, output_width, 3)
    if tuple(output.shape) != expected_shape or not bool(torch.all(torch.isfinite(output)).item()):
        raise RuntimeError(
            f"composed policy RGB must be finite NHWC {expected_shape}; got {tuple(output.shape)}"
        )
    return output
