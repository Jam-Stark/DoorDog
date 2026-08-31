#!/usr/bin/env python3
"""Add one deterministic zero-final absolute Stage3 head to an H16 parent."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import torch
from torch import nn


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
RNN_INPUT_KEY = "memory.rnn.weight_ih_l0"
HEAD_KEYS = (
    "bilateral_stage3_absolute_head.0.weight",
    "bilateral_stage3_absolute_head.0.bias",
    "bilateral_stage3_absolute_head.2.weight",
    "bilateral_stage3_absolute_head.2.bias",
    "bilateral_stage3_absolute_head.4.weight",
    "bilateral_stage3_absolute_head.4.bias",
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
    if not isinstance(actor_state, Mapping) or len(actor_state) != 23:
        raise ValueError("H16 parent must be an exact 23-key actor mapping")
    parent_weight = _require_tensor(actor_state, RNN_INPUT_KEY, (1024, 135))
    if any(key in actor_state for key in HEAD_KEYS):
        raise ValueError("source already contains bilateral absolute head weights")
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        head = nn.Sequential(
            nn.Linear(58, 256),
            nn.SiLU(),
            nn.Linear(256, 256),
            nn.SiLU(),
            nn.Linear(256, 9),
        )
    expanded = dict(actor_state)
    expanded[HEAD_KEYS[0]] = head[0].weight.detach().to(dtype=parent_weight.dtype)
    expanded[HEAD_KEYS[1]] = head[0].bias.detach().to(dtype=parent_weight.dtype)
    expanded[HEAD_KEYS[2]] = head[2].weight.detach().to(dtype=parent_weight.dtype)
    expanded[HEAD_KEYS[3]] = head[2].bias.detach().to(dtype=parent_weight.dtype)
    expanded[HEAD_KEYS[4]] = torch.zeros(9, 256, dtype=parent_weight.dtype)
    expanded[HEAD_KEYS[5]] = torch.zeros(9, dtype=parent_weight.dtype)
    if len(expanded) != 29:
        raise RuntimeError("H16 parent must expand exactly from 23 to 29 actor keys")
    with output.open("xb") as stream:
        torch.save({actor_key: expanded}, stream)
    print(f"expanded {source} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
