#!/usr/bin/env python3
"""Run one GPU lane of the bilateral Stage0-2 checkpoint screen."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
RUNNER = ROOT / "scriptsFORhuman/pull_lr_grasp/run_pull_lr_grasp.py"
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_pull_lr_grasp"
DEFAULT_STEPS = (50, 100, 150, 200, 250)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-seed", type=int, choices=(0, 1, 2, 3), required=True)
    parser.add_argument("--gpu", type=int, choices=(0, 1, 2, 3), required=True)
    parser.add_argument("--eval-seed", type=int, default=0)
    parser.add_argument("--steps", type=int, nargs="+", default=DEFAULT_STEPS)
    parser.add_argument("--train-run-prefix", default="pull_lr_grasp_h450")
    parser.add_argument("--label-prefix", default="h450")
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if any(step <= 0 for step in args.steps):
        raise ValueError("all --steps must be positive")
    run_root = TRAIN_ROOT / f"{args.train_run_prefix}_seed{args.train_seed}"
    for step in args.steps:
        checkpoint = run_root / f"model_step_{step:06d}.pt"
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        label = (
            f"{args.label_prefix}_s{args.train_seed}_step{step:03d}_"
            f"evalseed{args.eval_seed}"
        )
        for side in ("left", "right"):
            command = [
                str(PYTHON),
                "-B",
                str(RUNNER),
                "eval",
                "--side",
                side,
                "--checkpoint",
                str(checkpoint),
                "--label",
                label,
                "--gpu",
                str(args.gpu),
                "--seed",
                str(args.eval_seed),
                "--num-envs",
                "64",
            ]
            print("[pull-lr-screen]", " ".join(command), flush=True)
            if args.run:
                subprocess.run(command + ["--run"], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
