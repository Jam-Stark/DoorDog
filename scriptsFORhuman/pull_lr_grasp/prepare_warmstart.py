#!/usr/bin/env python3
"""Create the bilateral Stage0-2 warm-start by symmetrizing LR RMS features."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "logs_rl/a2_piper_pull_v6/pull_v6_F0_r6an_seed3/model_step_000025.pt"
)
SYMMETRIC_DESTINATION = (
    ROOT
    / "logs_rl/a2_piper_pull_lr_grasp/warmstarts"
    / "pull_v6_F0_r6an_seed3_lr_rms_rebased.pt"
)
FRESH_RMS_DESTINATION = (
    ROOT
    / "logs_rl/a2_piper_pull_lr_grasp/warmstarts"
    / "pull_v6_F0_r6an_seed3_fresh_rms.pt"
)
SIDE_INDICES = (112, 113)
SOURCE_RIGHT_RAW = (-1.0, 2.0)
TARGET_RIGHT_RAW = (0.0, 1.0)
TARGET_LEFT_RAW = (1.0, 0.0)
EXPECTED_OBS_DIM = 135


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument(
        "--mode", choices=("symmetric_lr", "fresh_rms"), default="symmetric_lr"
    )
    parser.add_argument("--destination", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    source = args.source.expanduser().resolve()
    default_destination = (
        SYMMETRIC_DESTINATION
        if args.mode == "symmetric_lr"
        else FRESH_RMS_DESTINATION
    )
    destination = (args.destination or default_destination).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite warm-start: {destination}")

    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    if "policy_state_dict" not in checkpoint:
        raise RuntimeError("source checkpoint has no policy_state_dict")
    policy = checkpoint["policy_state_dict"]
    mean = policy["running_mean_std.running_mean"]
    var = policy["running_mean_std.running_var"]
    if tuple(mean.shape) != (EXPECTED_OBS_DIM,) or tuple(var.shape) != (
        EXPECTED_OBS_DIM,
    ):
        raise RuntimeError(
            f"expected {EXPECTED_OBS_DIM}-D actor RMS; got {mean.shape=} {var.shape=}"
        )
    if policy["memory.rnn.weight_ih_l0"].shape[1] != EXPECTED_OBS_DIM:
        raise RuntimeError("source recurrent actor input is not 135-D")
    if tuple(policy["post_release_obs_override.weight"].shape) != (
        9,
        EXPECTED_OBS_DIM,
    ):
        raise RuntimeError("source post-release override does not use the 135-D contract")

    old_stats = []
    epsilon = 1.0e-5
    with torch.no_grad():
        if args.mode == "fresh_rms":
            mean.zero_()
            var.fill_(1.0)
            policy["running_mean_std.count"].fill_(1.0)
        else:
            for index, source_right_raw, target_right_raw, target_left_raw in zip(
                SIDE_INDICES,
                SOURCE_RIGHT_RAW,
                TARGET_RIGHT_RAW,
                TARGET_LEFT_RAW,
                strict=True,
            ):
                old_mean = float(mean[index].item())
                old_var = float(var[index].item())
                z_right = (source_right_raw - old_mean) / math.sqrt(old_var + epsilon)
                midpoint = (target_right_raw + target_left_raw) / 2.0
                new_var = ((target_right_raw - midpoint) / z_right) ** 2 - epsilon
                if not math.isfinite(new_var) or new_var <= 0.0:
                    raise RuntimeError(
                        f"invalid rebased variance at actor obs index {index}"
                    )
                old_stats.append((index, old_mean, old_var, z_right))
                mean[index] = midpoint
                var[index] = new_var

    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, destination)
    print(f"source={source}")
    print(f"destination={destination}")
    print(f"mode={args.mode}")
    for index, old_mean, old_var, z_right in old_stats:
        print(
            f"index={index} old_mean={old_mean:.9g} old_var={old_var:.9g} "
            f"right_z={z_right:.9g} new_mean={float(mean[index]):.9g} "
            f"new_var={float(var[index]):.9g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
