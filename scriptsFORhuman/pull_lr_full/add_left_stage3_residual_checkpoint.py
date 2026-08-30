#!/usr/bin/env python3
"""Expand one Gate-A actor checkpoint with a zero LEFT Stage3 residual."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import torch


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
RNN_INPUT_KEY = "memory.rnn.weight_ih_l0"
EXISTING_HEAD_WEIGHT = "post_release_obs_override.weight"
EXISTING_HEAD_BIAS = "post_release_obs_override.bias"
RESIDUAL_WEIGHT = "left_stage3_obs_residual.weight"
RESIDUAL_BIAS = "left_stage3_obs_residual.bias"
OUTPUT_DIMS = {"arm": 6, "base_arm": 9}


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
    parser.add_argument("--variant", choices=tuple(OUTPUT_DIMS), required=True)
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
    rnn_weight = _require_tensor(actor_state, RNN_INPUT_KEY, (1024, 135))
    _require_tensor(actor_state, EXISTING_HEAD_WEIGHT, (9, 135))
    _require_tensor(actor_state, EXISTING_HEAD_BIAS, (9,))
    if RESIDUAL_WEIGHT in actor_state or RESIDUAL_BIAS in actor_state:
        raise ValueError("source already contains LEFT Stage3 residual weights")

    output_dim = OUTPUT_DIMS[args.variant]
    expanded = dict(actor_state)
    expanded[RESIDUAL_WEIGHT] = torch.zeros(
        output_dim, 135, dtype=rnn_weight.dtype
    )
    expanded[RESIDUAL_BIAS] = torch.zeros(output_dim, dtype=rnn_weight.dtype)
    with output.open("xb") as stream:
        torch.save({actor_key: expanded}, stream)
    print(f"expanded {source} -> {output} variant={args.variant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
