#!/usr/bin/env python3
"""Add a behavior-continuous 137D late head beside the frozen 135D immediate-D head."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

import torch


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
RNN_KEY = "memory.rnn.weight_ih_l0"
HEAD_KEY = "post_release_obs_override.weight"
HEAD_BIAS_KEY = "post_release_obs_override.bias"
LATE_HEAD_KEY = "post_release_late_override.weight"
LATE_BIAS_KEY = "post_release_late_override.bias"


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
    rnn = state.get(RNN_KEY)
    head = state.get(HEAD_KEY)
    head_bias = state.get(HEAD_BIAS_KEY)
    if not torch.is_tensor(rnn) or tuple(rnn.shape) != (1024, 135):
        raise ValueError(f"{RNN_KEY} must remain exact 135D carrier input")
    if not torch.is_tensor(head) or tuple(head.shape) != (9, 135):
        raise ValueError(f"{HEAD_KEY} must have exact shape (9, 135)")
    if not torch.is_tensor(head_bias) or tuple(head_bias.shape) != (9,):
        raise ValueError(f"{HEAD_BIAS_KEY} must have exact shape (9,)")
    if LATE_HEAD_KEY in state or LATE_BIAS_KEY in state:
        raise ValueError("checkpoint already contains the side-channel late head")
    expanded = dict(state)
    expanded[LATE_HEAD_KEY] = torch.cat((head, head.new_zeros((9, 2))), dim=1)
    expanded[LATE_BIAS_KEY] = head_bias.clone()
    with output.open("xb") as stream:
        torch.save({actor_key: expanded}, stream)
    print(f"added behavior-continuous late head {source} -> {output}; carrier/immediate head remain 135D")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
