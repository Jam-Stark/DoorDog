#!/usr/bin/env python3
"""Replace a strict pull-v6 additive release residual with a mode override."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import torch


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
RNN_INPUT_KEY = "memory.rnn.weight_ih_l0"
RESIDUAL_KEY = "release_mode_gripper_mean_residual"
OVERRIDE_KEY = "release_mode_gripper_mean_override"


def _require_tensor(state_dict: Mapping[str, object], key: str, shape: tuple[int, ...]) -> torch.Tensor:
    value = state_dict.get(key)
    if not torch.is_tensor(value) or tuple(value.shape) != shape:
        actual_shape = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{key} must have exact shape {shape}; got {actual_shape}")
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
    if source == output:
        raise ValueError("source and output must be different paths")

    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, Mapping):
        raise ValueError(f"checkpoint must be a mapping; got {type(checkpoint).__name__}")
    actor_keys = [key for key in ACTOR_KEYS if key in checkpoint]
    if len(actor_keys) != 1:
        raise ValueError(f"checkpoint must contain exactly one actor key; found {actor_keys!r}")
    actor_key = actor_keys[0]
    actor_state = checkpoint[actor_key]
    if not isinstance(actor_state, Mapping):
        raise ValueError(f"{actor_key} must be a mapping; got {type(actor_state).__name__}")
    _require_tensor(actor_state, RNN_INPUT_KEY, (1024, 135))
    residual = _require_tensor(actor_state, RESIDUAL_KEY, (2,))
    if OVERRIDE_KEY in actor_state:
        raise ValueError(f"{source} already contains {OVERRIDE_KEY}")

    override_state = dict(actor_state)
    del override_state[RESIDUAL_KEY]
    override_state[OVERRIDE_KEY] = torch.zeros_like(residual)

    with output.open("xb") as stream:
        torch.save({actor_key: override_state}, stream)
    print(f"replaced {RESIDUAL_KEY} with {OVERRIDE_KEY} in {source} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
