#!/usr/bin/env python3
"""Expand one strict pull-v6 recurrent actor checkpoint from 133D to 135D input."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import torch


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
RUNNING_MEAN_KEY = "running_mean_std.running_mean"
RUNNING_VAR_KEY = "running_mean_std.running_var"
RNN_INPUT_KEY = "memory.rnn.weight_ih_l0"


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

    running_mean = _require_tensor(actor_state, RUNNING_MEAN_KEY, (133,))
    running_var = _require_tensor(actor_state, RUNNING_VAR_KEY, (133,))
    rnn_weight = _require_tensor(actor_state, RNN_INPUT_KEY, (1024, 133))

    expanded_state = dict(actor_state)
    expanded_state[RUNNING_MEAN_KEY] = torch.cat((running_mean, torch.zeros_like(running_mean[:2])))
    expanded_state[RUNNING_VAR_KEY] = torch.cat((running_var, torch.ones_like(running_var[:2])))
    expanded_state[RNN_INPUT_KEY] = torch.cat((rnn_weight, torch.zeros_like(rnn_weight[:, :2])), dim=1)

    with output.open("xb") as stream:
        torch.save({actor_key: expanded_state}, stream)
    print(f"expanded {source} -> {output} using actor key {actor_key!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
