#!/usr/bin/env python3
"""Evaluate all saved checkpoints for one pull-v6 P2 seed."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scriptsFORhuman/pull_v6/run_pull_v6.py"
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_pull_v6"
STEPS = (50, 100, 150, 200, 250)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2, 3), required=True)
    parser.add_argument("--gpu", type=int, choices=(0, 1, 2, 3), required=True)
    parser.add_argument("--num-envs", type=int, default=16)
    parser.add_argument("--run-prefix", default="pull_v6_F0")
    parser.add_argument("--label-prefix", default="p2_F0")
    parser.add_argument("--ablation", required=True)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    for value, name in (
        (args.run_prefix, "run-prefix"),
        (args.label_prefix, "label-prefix"),
    ):
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(f"{name} must be a leaf name; got {value!r}")
    run_dir = TRAIN_ROOT / f"{args.run_prefix}_seed{args.seed}"
    for step in STEPS:
        checkpoint = run_dir / f"model_step_{step:06d}.pt"
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        command = [
            sys.executable,
            str(RUNNER),
            "eval",
            "--checkpoint",
            str(checkpoint),
            "--label",
            f"{args.label_prefix}_seed{args.seed}_step{step:03d}",
            "--gpu",
            str(args.gpu),
            "--seed",
            str(args.seed),
            "--num-envs",
            str(args.num_envs),
            "--ablation",
            args.ablation,
        ]
        if args.run:
            command.append("--run")
        print("[pull-v6 P2 gate]", " ".join(command), flush=True)
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
