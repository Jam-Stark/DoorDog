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
