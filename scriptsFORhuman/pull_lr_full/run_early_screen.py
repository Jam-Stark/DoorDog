#!/usr/bin/env python3
"""Run fixed LEFT then RIGHT early screen for one full-pull checkpoint."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
RUNNER = ROOT / "scriptsFORhuman/pull_lr_full/run_pull_lr_full.py"
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_pull_lr_full_stage"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=("a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"), required=True)
    parser.add_argument("--train-seed", type=int, choices=(0, 1, 2, 3), required=True)
    parser.add_argument("--gpu", type=int, choices=(0, 1, 2, 3), required=True)
    parser.add_argument("--eval-seed", type=int, default=1001)
    parser.add_argument("--num-envs", type=int, default=16)
    parser.add_argument("--step", type=int, default=25)
    parser.add_argument("--train-prefix", default="pull_lr_full_n1024_rebase")
    parser.add_argument("--label-prefix", default="r2c_screen")
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.num_envs <= 0 or args.step <= 0:
        raise ValueError("--num-envs and --step must be positive")
    run_name = f"{args.train_prefix}_gate_{args.gate}_seed{args.train_seed}"
    checkpoint = TRAIN_ROOT / run_name / f"model_step_{args.step:06d}.pt"
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    label = (
        f"{args.label_prefix}_gate_{args.gate}_s{args.train_seed}_"
        f"step{args.step:03d}_evalseed{args.eval_seed}"
    )
    for side in ("left", "right"):
        command = [
            str(PYTHON),
            str(RUNNER),
            "eval",
            "--gate",
            args.gate,
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
            str(args.num_envs),
            "--actor-contract",
            (
                "left_post_e3"
                if args.gate == "k"
                else
                "left_nonlinear"
                if args.gate in {"h", "i", "j"}
                else "left_base_residual"
                if args.gate == "g"
                else "left_residual"
                if args.gate in {"d", "e", "f"}
                else "output"
            ),
        ]
        print("[pull-lr-full-screen]", " ".join(command), flush=True)
        if args.run:
            subprocess.run(command + ["--run"], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
