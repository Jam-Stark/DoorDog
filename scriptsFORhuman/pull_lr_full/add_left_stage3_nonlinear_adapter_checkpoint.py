#!/usr/bin/env python3
"""Add one deterministic zero-final nonlinear adapter to an H5 actor."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import torch
from torch import nn


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
ARM_WEIGHT = "left_stage3_obs_residual.weight"
ARM_BIAS = "left_stage3_obs_residual.bias"
ADAPTER_KEYS = (
    "left_stage3_nonlinear_adapter.0.weight",
    "left_stage3_nonlinear_adapter.0.bias",
    "left_stage3_nonlinear_adapter.2.weight",
    "left_stage3_nonlinear_adapter.2.bias",
)


def _require_tensor(state, key: str, shape: tuple[int, ...]) -> torch.Tensor:
    value = state.get(key)
    if not torch.is_tensor(value) or tuple(value.shape) != shape:
        actual = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{key} must have shape {shape}; got {actual}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if not output.parent.is_dir():
        raise NotADirectoryError(output.parent)
    if source == output or output.exists():
        raise ValueError("output must be a new path distinct from source")

    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, Mapping):
        raise ValueError("checkpoint must be a mapping")
    actor_keys = [key for key in ACTOR_KEYS if key in checkpoint]
    if len(actor_keys) != 1:
        raise ValueError(f"checkpoint must contain one actor key; got {actor_keys!r}")
    actor_key = actor_keys[0]
    actor_state = checkpoint[actor_key]
    if not isinstance(actor_state, Mapping):
        raise ValueError(f"{actor_key} must be a mapping")
    arm_weight = _require_tensor(actor_state, ARM_WEIGHT, (6, 135))
    _require_tensor(actor_state, ARM_BIAS, (6,))
    if any(key in actor_state for key in ADAPTER_KEYS):
        raise ValueError("source already contains nonlinear adapter weights")

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        first = nn.Linear(391, 16)
    expanded = dict(actor_state)
    expanded[ADAPTER_KEYS[0]] = first.weight.detach().to(dtype=arm_weight.dtype)
    expanded[ADAPTER_KEYS[1]] = first.bias.detach().to(dtype=arm_weight.dtype)
    expanded[ADAPTER_KEYS[2]] = torch.zeros(9, 16, dtype=arm_weight.dtype)
    expanded[ADAPTER_KEYS[3]] = torch.zeros(9, dtype=arm_weight.dtype)
    with output.open("xb") as stream:
        torch.save({actor_key: expanded}, stream)
    print(f"expanded {source} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
