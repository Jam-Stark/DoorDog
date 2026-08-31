#!/usr/bin/env python3
"""Fit the H18-B0 absolute Stage3 head from the H14 teacher trace."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import torch
from torch import nn


ACTOR_KEYS = ("policy_state_dict", "actor_model_state_dict")
HEAD_PREFIX = "bilateral_stage3_absolute_head."
HEAD_KEYS = (
    "bilateral_stage3_absolute_head.0.weight",
    "bilateral_stage3_absolute_head.0.bias",
    "bilateral_stage3_absolute_head.2.weight",
    "bilateral_stage3_absolute_head.2.bias",
    "bilateral_stage3_absolute_head.4.weight",
    "bilateral_stage3_absolute_head.4.bias",
)
E4_KEY = "E4_POSITIVE_HINGE_RETAINED"


def _load_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _require_tensor(state, key: str, shape: tuple[int, ...]) -> torch.Tensor:
    value = state.get(key)
    if not torch.is_tensor(value) or tuple(value.shape) != shape:
        actual = None if not torch.is_tensor(value) else tuple(value.shape)
        raise ValueError(f"{key} must have shape {shape}; got {actual}")
    return value


def _terminal_e4_env_ids(terminal_records: object) -> set[int]:
    if not isinstance(terminal_records, Mapping):
        raise ValueError("terminal records must be a metrics_eval mapping")
    diagnostics = terminal_records.get("episode_terminal_diagnostics")
    if not isinstance(diagnostics, Sequence):
        raise ValueError("terminal records must contain episode_terminal_diagnostics")
    e4_env_ids: set[int] = set()
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, Mapping):
            raise ValueError("terminal diagnostic must be a mapping")
        env_id = diagnostic.get("env_id")
        episode = diagnostic.get("pull_v0_episode")
        if not isinstance(env_id, int) or not isinstance(episode, Mapping):
            raise ValueError("terminal diagnostic must expose env_id and pull_v0_episode")
        events = episode.get("event_reached")
        if not isinstance(events, Mapping) or E4_KEY not in events:
            raise ValueError(f"terminal diagnostic must expose event_reached[{E4_KEY!r}]")
        if events[E4_KEY] is True:
            e4_env_ids.add(env_id)
        elif events[E4_KEY] is not False:
            raise ValueError(f"{E4_KEY} must be bool; got {events[E4_KEY]!r}")
    if not e4_env_ids:
        raise ValueError("terminal records contain no E4-positive environment")
    return e4_env_ids


def _teacher_rows(
    trace: object, e4_env_ids: set[int]
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    if not isinstance(trace, Sequence):
        raise ValueError("stage trace must be a JSON list")
    features: list[list[float]] = []
    targets: list[list[float]] = []
    pre_e3: list[bool] = []
    env_ids: list[int] = []
    for row in trace:
        if not isinstance(row, Mapping):
            raise ValueError("stage trace row must be a mapping")
        env_id = row.get("env_id")
        if not isinstance(env_id, int) or env_id not in e4_env_ids:
            continue
        pull_v0 = row.get("pull_v0")
        if not isinstance(pull_v0, Mapping):
            raise ValueError("stage trace row must expose pull_v0")
        teacher = pull_v0.get("pull_lr_h14_teacher")
        if not isinstance(teacher, Mapping):
            raise ValueError("stage trace row must expose pull_v0.pull_lr_h14_teacher")
        if teacher.get("valid") is not True:
            continue
        row_features = teacher.get("canonical_features")
        canonical_target = teacher.get("canonical_target")
        absolute_arm = teacher.get("absolute_arm_delta_target_normalized")
        row_pre_e3 = teacher.get("pre_e3")
        if (
            not isinstance(row_features, list)
            or len(row_features) != 58
            or not isinstance(canonical_target, list)
            or len(canonical_target) != 9
            or not isinstance(absolute_arm, list)
            or len(absolute_arm) != 6
            or not isinstance(row_pre_e3, bool)
        ):
            raise ValueError(
                "valid H14 absolute teacher row requires canonical_features(58), "
                "canonical_target(9), absolute_arm_delta_target_normalized(6), and pre_e3"
            )
        features.append(row_features)
        targets.append([*canonical_target[:3], *absolute_arm])
        pre_e3.append(row_pre_e3)
        env_ids.append(env_id)
    if not features:
        raise ValueError("no valid H14 absolute teacher rows from E4-positive terminal environments")
    features_tensor = torch.tensor(features, dtype=torch.float32)
    targets_tensor = torch.tensor(targets, dtype=torch.float32)
    if not torch.all(torch.isfinite(features_tensor)) or not torch.all(torch.isfinite(targets_tensor)):
        raise ValueError("H14 absolute teacher features and targets must be finite")
    return (
        features_tensor,
        targets_tensor,
        torch.tensor(pre_e3, dtype=torch.bool),
        torch.tensor(env_ids, dtype=torch.long),
    )


def _load_head(warm_checkpoint: Path) -> tuple[str, dict[str, torch.Tensor], nn.Sequential]:
    checkpoint = torch.load(warm_checkpoint, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, Mapping):
        raise ValueError("warm checkpoint must be a mapping")
    actor_keys = [key for key in ACTOR_KEYS if key in checkpoint]
    if len(actor_keys) != 1:
        raise ValueError(f"warm checkpoint must contain one actor key; got {actor_keys!r}")
    actor_key = actor_keys[0]
    actor_state = checkpoint[actor_key]
    if not isinstance(actor_state, Mapping) or len(actor_state) != 29:
        raise ValueError("warm checkpoint must contain the exact 29-key H18 actor mapping")
    _require_tensor(actor_state, HEAD_KEYS[0], (256, 58))
    _require_tensor(actor_state, HEAD_KEYS[1], (256,))
    _require_tensor(actor_state, HEAD_KEYS[2], (256, 256))
    _require_tensor(actor_state, HEAD_KEYS[3], (256,))
    _require_tensor(actor_state, HEAD_KEYS[4], (9, 256))
    _require_tensor(actor_state, HEAD_KEYS[5], (9,))
    parent = {key: value for key, value in actor_state.items() if key not in HEAD_KEYS}
    if len(parent) != 23:
        raise ValueError("H18 warm actor must retain exactly 23 frozen parent tensors")
    head = nn.Sequential(
        nn.Linear(58, 256),
        nn.SiLU(),
        nn.Linear(256, 256),
        nn.SiLU(),
        nn.Linear(256, 9),
    )
    head.load_state_dict(
        {key.removeprefix(HEAD_PREFIX): actor_state[key] for key in HEAD_KEYS},
        strict=True,
    )
    return actor_key, dict(actor_state), head


def _phase_weighted_mse(
    prediction: torch.Tensor, target: torch.Tensor, pre_e3: torch.Tensor
) -> torch.Tensor:
    if not torch.any(pre_e3) or not torch.any(~pre_e3):
        raise ValueError("training rows must contain both pre-E3 and post-E3 phases")
    per_row = torch.mean(torch.square(prediction - target), dim=-1)
    weights = torch.empty_like(per_row)
    weights[pre_e3] = 1.0 / pre_e3.sum()
    weights[~pre_e3] = 1.0 / (~pre_e3).sum()
    return torch.sum(per_row * weights) / weights.sum()


def _predict(head: nn.Module, features: torch.Tensor) -> torch.Tensor:
    raw = head(features)
    return torch.cat((raw[:, :3], torch.tanh(raw[:, 3:])), dim=-1)


def _mse_report(
    name: str, prediction: torch.Tensor, target: torch.Tensor, pre_e3: torch.Tensor
) -> str:
    total = torch.mean(torch.square(prediction - target)).item()
    pre = torch.mean(torch.square(prediction[pre_e3] - target[pre_e3])).item()
    post = torch.mean(torch.square(prediction[~pre_e3] - target[~pre_e3])).item()
    return f"{name}_total_mse={total:.9g} {name}_pre_e3_mse={pre:.9g} {name}_post_e3_mse={post:.9g}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("terminal_records", type=Path)
    parser.add_argument("warm_checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--epochs", type=int, default=2000)
    parser.add_argument("--lr", type=float, default=1.0e-3)
    args = parser.parse_args()
    if args.epochs <= 0 or args.lr <= 0.0:
        raise ValueError("--epochs and --lr must be positive")
    trace_path = args.trace.resolve()
    terminal_path = args.terminal_records.resolve()
    warm_path = args.warm_checkpoint.resolve()
    output = args.output.resolve()
    if not warm_path.is_file():
        raise FileNotFoundError(warm_path)
    if not output.parent.is_dir():
        raise NotADirectoryError(output.parent)
    if output.exists() or output == warm_path:
        raise ValueError("output must be a new path distinct from warm checkpoint")

    torch.manual_seed(0)
    e4_env_ids = _terminal_e4_env_ids(_load_json(terminal_path))
    features, targets, pre_e3, env_ids = _teacher_rows(_load_json(trace_path), e4_env_ids)
    support = torch.mean(torch.all(torch.abs(targets[:, 3:]) <= 1.0, dim=-1).float()).item()
    train = env_ids <= 11
    heldout = (env_ids >= 12) & (env_ids <= 15)
    if not torch.any(train) or not torch.any(heldout):
        raise ValueError("teacher rows must populate env0-11 train and env12-15 heldout")
    for name, mask in (("train", train), ("heldout", heldout)):
        if not torch.any(pre_e3[mask]) or not torch.any(~pre_e3[mask]):
            raise ValueError(f"{name} split must contain both pre-E3 and post-E3 rows")

    actor_key, warm_state, head = _load_head(warm_path)
    optimizer = torch.optim.Adam(head.parameters(), lr=args.lr)
    head.train()
    train_features = features[train]
    train_targets = targets[train]
    train_pre_e3 = pre_e3[train]
    for _ in range(args.epochs):
        optimizer.zero_grad(set_to_none=True)
        loss = _phase_weighted_mse(
            _predict(head, train_features), train_targets, train_pre_e3
        )
        loss.backward()
        optimizer.step()

    head.eval()
    with torch.no_grad():
        prediction = _predict(head, features)
    head_state = head.state_dict()
    fitted_state = dict(warm_state)
    for key in HEAD_KEYS:
        fitted_state[key] = head_state[key.removeprefix(HEAD_PREFIX)].detach().clone()
    parent_exact = all(
        torch.equal(warm_state[key], fitted_state[key])
        for key in warm_state
        if key not in HEAD_KEYS
    )
    if not parent_exact or len(fitted_state) != 29:
        raise RuntimeError("fitted actor must retain exact parent23 and actor mapping29")
    with output.open("xb") as stream:
        torch.save({actor_key: fitted_state}, stream)

    print(f"e4_env_ids={sorted(e4_env_ids)}")
    print(
        f"train_rows={int(train.sum())} train_pre_e3={int(pre_e3[train].sum())} "
        f"train_post_e3={int((~pre_e3[train]).sum())}"
    )
    print(
        f"heldout_rows={int(heldout.sum())} heldout_pre_e3={int(pre_e3[heldout].sum())} "
        f"heldout_post_e3={int((~pre_e3[heldout]).sum())}"
    )
    print(f"absolute_arm_target_row_within1={support:.9g}")
    print(_mse_report("train", prediction[train], targets[train], pre_e3[train]))
    print(_mse_report("heldout", prediction[heldout], targets[heldout], pre_e3[heldout]))
    print(f"parent23_exact={parent_exact} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
