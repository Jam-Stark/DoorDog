#!/usr/bin/env python3
"""Prepare or run the pull-v2 smoke, Wave1, Wave2, G4, eval, and analysis stages."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PULL_V2 = Path(__file__).resolve().parent
TRAIN = PULL_V2 / "run_pull_v2_training.py"
EVAL = PULL_V2 / "run_pull_v2_eval_all_checkpoints.py"
ANALYSIS = PULL_V2 / "analyze_pull_v2.py"
UPROBE = PULL_V2 / "run_u_probe_unlatch_calibration.py"
ALLOWED_PHYSICAL_GPUS = (6, 7)
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("u_probe", "smoke", "wave1", "wave2", "g4", "eval", "analyze"),
        required=True,
    )
    parser.add_argument("--gpu0", type=int, choices=ALLOWED_PHYSICAL_GPUS, default=6)
    parser.add_argument("--gpu1", type=int, choices=ALLOWED_PHYSICAL_GPUS, default=7)
    parser.add_argument(
        "--gpu2",
        type=int,
        choices=ALLOWED_PHYSICAL_GPUS,
        default=6,
        help="physical GPU lease for the sequential G4 seed2 run",
    )
    parser.add_argument("--seed", type=int, choices=(0, 1, 2))
    parser.add_argument("--train-dir", type=Path)
    parser.add_argument("--checkpoint", type=Path, help="selected Wave1 checkpoint for relay/G4")
    parser.add_argument("--include-seed2", action="store_true")
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def _worker_command(argv: list[str]) -> bool:
    return len(argv) > 1 and argv[1] in {str(TRAIN), str(EVAL)}


def _prepared_argv(argv: list[str]) -> list[str]:
    return [*argv, "--run"] if _worker_command(argv) else list(argv)


def _run(argv: list[str], process_env: dict[str, str] | None = None) -> None:
    prepared = _prepared_argv(argv)
    print("[pull-v2]", " ".join(prepared))
    run_env = os.environ.copy()
    if process_env is not None:
        run_env.update(process_env)
    result = subprocess.run(prepared, cwd=ROOT, env=run_env, check=False)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, prepared)


def _run_wave1_concurrently(commands: list[list[str]]) -> None:
    if len(commands) != 2:
        raise ValueError(f"Wave1 requires exactly two seed commands; got {len(commands)}")
    processes = []
    for command in commands:
        prepared = _prepared_argv(command)
        print("[pull-v2] Wave1 concurrent:", " ".join(prepared))
        processes.append(subprocess.Popen(prepared, cwd=ROOT))
    failures = []
    for process in processes:
        returncode = process.wait()
        if returncode != 0:
            failures.append((process.pid, returncode))
    if failures:
        raise RuntimeError(f"Wave1 concurrent training failed: {failures}")


def _probe_env(gpu: int) -> dict[str, str]:
    if gpu not in ALLOWED_PHYSICAL_GPUS:
        raise ValueError(f"U-probe only permits physical GPU6/7; got GPU{gpu}.")
    return {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "PYTHONUNBUFFERED": "1",
    }


def _training_dir(run_name: str) -> Path:
    return TRAIN_ROOT / run_name


def main() -> int:
    args = _parse_args()
    if args.phase == "wave1" and args.gpu0 == args.gpu1:
        raise ValueError("Wave1 requires disjoint physical GPU6 and GPU7 leases.")

    commands: list[list[str]] = []
    command_envs: list[dict[str, str] | None] = []
    if args.phase == "u_probe":
        commands = [[sys.executable, str(UPROBE), "--headless", "--device", "cuda:0"]]
        command_envs = [_probe_env(args.gpu0)]
    elif args.phase == "smoke":
        commands = [
            [
                sys.executable,
                str(TRAIN),
                "--mode",
                "smoke",
                "--seed",
                "0",
                "--gpu",
                str(args.gpu0),
                "--run-name",
                "pull_v2_W_smoke_seed0",
            ]
        ]
        command_envs = [None]
    elif args.phase == "wave1":
        commands = [
            [
                sys.executable,
                str(TRAIN),
                "--mode",
                "formal",
                "--seed",
                "0",
                "--gpu",
                str(args.gpu0),
                "--run-name",
                "pull_v2_W_wave1_seed0",
            ],
            [
                sys.executable,
                str(TRAIN),
                "--mode",
                "formal",
                "--seed",
                "1",
                "--gpu",
                str(args.gpu1),
                "--run-name",
                "pull_v2_W_wave1_seed1",
            ],
        ]
        command_envs = [None, None]
    elif args.phase == "wave2":
        if args.checkpoint is None:
            raise ValueError("Wave2 requires --checkpoint from the selected best Wave1 cell.")
        checkpoint = args.checkpoint.resolve()
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        commands = [
            [
                sys.executable,
                str(TRAIN),
                "--mode",
                "formal",
                "--seed",
                "0",
                "--gpu",
                str(args.gpu0),
                "--checkpoint",
                str(checkpoint),
                "--run-name",
                "pull_v2_W_wave2_relay_seed0",
            ],
            [
                sys.executable,
                str(TRAIN),
                "--mode",
                "formal",
                "--seed",
                "1",
                "--gpu",
                str(args.gpu1),
                "--checkpoint",
                str(checkpoint),
                "--run-name",
                "pull_v2_W_wave2_relay_seed1",
            ],
        ]
        command_envs = [None, None]
    elif args.phase == "g4":
        if args.checkpoint is None:
            raise ValueError("G4 requires --checkpoint from the selected Wave1 cell.")
        checkpoint = args.checkpoint.resolve()
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        train_name = "pull_v2_W_g4_seed2"
        train_dir = _training_dir(train_name)
        commands = [
            [
                sys.executable,
                str(TRAIN),
                "--mode",
                "formal",
                "--seed",
                "2",
                "--gpu",
                str(args.gpu2),
                "--checkpoint",
                str(checkpoint),
                "--run-name",
                train_name,
            ],
            [
                sys.executable,
                str(EVAL),
                "--seed",
                "2",
                "--gpu",
                str(args.gpu2),
                "--train-dir",
                str(train_dir),
                "--run-name",
                "W_g4_seed2",
            ],
        ]
        command_envs = [None, None]
    elif args.phase == "eval":
        if args.seed is None or args.train_dir is None:
            raise ValueError("eval requires --seed and --train-dir.")
        gpu = {0: args.gpu0, 1: args.gpu1, 2: args.gpu2}[args.seed]
        commands = [
            [
                sys.executable,
                str(EVAL),
                "--seed",
                str(args.seed),
                "--gpu",
                str(gpu),
                "--train-dir",
                str(args.train_dir),
                "--run-name",
                f"W_seed{args.seed}",
            ]
        ]
        command_envs = [None]
    else:
        commands = [[sys.executable, str(ANALYSIS), *(["--include-seed2"] if args.include_seed2 else [])]]
        command_envs = [None]

    if not args.run:
        for command in commands:
            print("[pull-v2] prepared:", " ".join(command))
        return 0

    if args.phase == "wave1":
        _run_wave1_concurrently(commands)
        return 0
    for command, process_env in zip(commands, command_envs, strict=True):
        _run(command, process_env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
