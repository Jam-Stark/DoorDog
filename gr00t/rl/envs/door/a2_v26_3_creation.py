"""Control-interval handle creation state for base_v26-3."""

from __future__ import annotations

import math

import torch


A2_V26_3_HANDLE_NORM_RAD = 0.785398


def a2_v26_3_update_handle_creation(
    handle_position: torch.Tensor,
    handle_position_prev: torch.Tensor,
    handle_highwater: torch.Tensor,
    active: torch.Tensor,
    *,
    control_dt: float,
) -> dict[str, torch.Tensor]:
    """Advance the monotone state once and return the authoritative step cache."""

    if (
        not torch.is_tensor(handle_position)
        or handle_position.ndim != 1
        or not handle_position.is_floating_point()
        or not torch.is_tensor(handle_position_prev)
        or handle_position_prev.shape != handle_position.shape
        or handle_position_prev.dtype != handle_position.dtype
        or handle_position_prev.device != handle_position.device
        or not torch.is_tensor(handle_highwater)
        or handle_highwater.shape != handle_position.shape
        or handle_highwater.dtype != handle_position.dtype
        or handle_highwater.device != handle_position.device
        or not torch.is_tensor(active)
        or active.shape != handle_position.shape
        or active.dtype != torch.bool
        or active.device != handle_position.device
    ):
        raise RuntimeError("v26-3 handle creation tensors have incompatible contracts.")
    if (
        not torch.all(torch.isfinite(handle_position))
        or not torch.all(torch.isfinite(handle_position_prev))
        or not torch.all(torch.isfinite(handle_highwater))
    ):
        raise RuntimeError("v26-3 handle creation tensors must be finite.")
    if (
        isinstance(control_dt, bool)
        or not isinstance(control_dt, (int, float))
        or not math.isfinite(float(control_dt))
        or float(control_dt) <= 0.0
    ):
        raise RuntimeError("v26-3 handle creation requires a finite positive control_dt.")

    handle_position_current = handle_position.clamp(
        min=0.0, max=A2_V26_3_HANDLE_NORM_RAD
    )
    highwater_prev = handle_highwater.clone()
    highwater_current = torch.maximum(highwater_prev, handle_position_current)
    delta_net = handle_position_current - handle_position_prev
    delta_highwater = highwater_current - highwater_prev
    creation_raw = (
        delta_highwater
        / (A2_V26_3_HANDLE_NORM_RAD * float(control_dt))
        * active.to(dtype=handle_position.dtype)
    )
    if torch.any(delta_highwater < 0.0) or not torch.all(torch.isfinite(creation_raw)):
        raise RuntimeError("v26-3 handle creation state violated monotonicity or finiteness.")
    return {
        "handle_position_current": handle_position_current,
        "handle_highwater_prev": highwater_prev,
        "handle_highwater_current": highwater_current,
        "handle_delta_net": delta_net,
        "handle_delta_highwater": delta_highwater,
        "creation_raw": creation_raw,
        "creation_active": active,
    }


__all__ = [
    "A2_V26_3_HANDLE_NORM_RAD",
    "a2_v26_3_update_handle_creation",
]
