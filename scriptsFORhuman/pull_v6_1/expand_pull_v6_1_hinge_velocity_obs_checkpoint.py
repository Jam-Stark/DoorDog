#!/usr/bin/env python3
"""Insert one hinge-velocity actor column before the existing 2D release mode."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import torch


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
MEAN_KEY = "running_mean_std.running_mean"
VAR_KEY = "running_mean_std.running_var"
RNN_KEY = "memory.rnn.weight_ih_l0"
HEAD_KEY = "post_release_obs_override.weight"


def _require(state: Mapping[str, object], key: str, shape: tuple[int, ...]) -> torch.Tensor:
    value = state.get(key)
    if not torch.is_tensor(value) or tuple(value.shape) != shape:
        actual = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{key} must have exact shape {shape}; got {actual}")
    return value


def _insert_vector(value: torch.Tensor, fill: float) -> torch.Tensor:
    return torch.cat((value[:133], value.new_full((1,), fill), value[133:]))


def _insert_column(value: torch.Tensor) -> torch.Tensor:
    return torch.cat((value[:, :133], value.new_zeros((value.shape[0], 1)), value[:, 133:]), dim=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(output)
    if not output.parent.is_dir():
        raise NotADirectoryError(output.parent)

    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, Mapping):
        raise ValueError("checkpoint must be a mapping")
    actor_keys = [key for key in ACTOR_KEYS if key in checkpoint]
    if len(actor_keys) != 1:
        raise ValueError(f"checkpoint must contain exactly one actor key; found {actor_keys!r}")
    actor_key = actor_keys[0]
    state = checkpoint[actor_key]
    if not isinstance(state, Mapping):
        raise ValueError(f"{actor_key} must be a mapping")

    mean = _require(state, MEAN_KEY, (135,))
    var = _require(state, VAR_KEY, (135,))
    rnn = _require(state, RNN_KEY, (1024, 135))
    head = _require(state, HEAD_KEY, (9, 135))
    expanded = dict(state)
    expanded[MEAN_KEY] = _insert_vector(mean, 0.0)
    expanded[VAR_KEY] = _insert_vector(var, 1.0)
    expanded[RNN_KEY] = _insert_column(rnn)
    expanded[HEAD_KEY] = _insert_column(head)
    with output.open("xb") as stream:
        torch.save({actor_key: expanded}, stream)
    print(f"expanded {source} -> {output} with hinge velocity at actor column 133")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
