#!/usr/bin/env python3
"""Add a zero base-planar residual to one H5 arm-residual actor."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import torch


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
ARM_WEIGHT = "left_stage3_obs_residual.weight"
ARM_BIAS = "left_stage3_obs_residual.bias"
BASE_WEIGHT = "left_stage3_base_residual.weight"
BASE_BIAS = "left_stage3_base_residual.bias"


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
    if BASE_WEIGHT in actor_state or BASE_BIAS in actor_state:
        raise ValueError("source already contains LEFT Stage3 base residual")

    expanded = dict(actor_state)
    expanded[BASE_WEIGHT] = torch.zeros(3, 135, dtype=arm_weight.dtype)
    expanded[BASE_BIAS] = torch.zeros(3, dtype=arm_weight.dtype)
    with output.open("xb") as stream:
        torch.save({actor_key: expanded}, stream)
    print(f"expanded {source} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
