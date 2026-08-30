#!/usr/bin/env python3
"""Add one deterministic zero-final task-space head to an H9 actor."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import torch
from torch import nn


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
PARENT_ADAPTER_KEYS = (
    "left_stage3_nonlinear_adapter.0.weight",
    "left_stage3_nonlinear_adapter.0.bias",
    "left_stage3_nonlinear_adapter.2.weight",
    "left_stage3_nonlinear_adapter.2.bias",
)
TASKSPACE_HEAD_KEYS = (
    "left_stage3_taskspace_head.0.weight",
    "left_stage3_taskspace_head.0.bias",
    "left_stage3_taskspace_head.2.weight",
    "left_stage3_taskspace_head.2.bias",
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
    parent_weight = _require_tensor(actor_state, PARENT_ADAPTER_KEYS[0], (16, 391))
    _require_tensor(actor_state, PARENT_ADAPTER_KEYS[1], (16,))
    _require_tensor(actor_state, PARENT_ADAPTER_KEYS[2], (9, 16))
    _require_tensor(actor_state, PARENT_ADAPTER_KEYS[3], (9,))
    if any(key in actor_state for key in TASKSPACE_HEAD_KEYS):
        raise ValueError("source already contains task-space head weights")

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        first = nn.Linear(391, 16)
    expanded = dict(actor_state)
    expanded[TASKSPACE_HEAD_KEYS[0]] = first.weight.detach().to(
        dtype=parent_weight.dtype
    )
    expanded[TASKSPACE_HEAD_KEYS[1]] = first.bias.detach().to(
        dtype=parent_weight.dtype
    )
    expanded[TASKSPACE_HEAD_KEYS[2]] = torch.zeros(
        6, 16, dtype=parent_weight.dtype
    )
    expanded[TASKSPACE_HEAD_KEYS[3]] = torch.zeros(6, dtype=parent_weight.dtype)
    if len(expanded) != 33:
        raise ValueError(f"H9 actor must expand from 29 to 33 keys; got {len(expanded)}")
    with output.open("xb") as stream:
        torch.save({actor_key: expanded}, stream)
    print(f"expanded {source} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
