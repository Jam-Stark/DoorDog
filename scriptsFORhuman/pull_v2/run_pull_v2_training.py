#!/usr/bin/env python3
"""Launch pull-v2 W smoke or formal training on physical GPU6/7 only."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ABLLATION = "wbmanip/pull_v2_W_wall_removal"
BASE_DIR = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
ALLOWED_PHYSICAL_GPUS = (6, 7)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "formal"), required=True)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_PHYSICAL_GPUS, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--experiment-dir", type=Path)
    parser.add_argument("--run-name", help="unique Hydra/output name; defaults to the seed-qualified W name")
    parser.add_argument("--run", action="store_true", help="execute the prepared command")
    return parser.parse_args()


def _topology(mode: str) -> tuple[int, int, int]:
    if mode == "smoke":
        return 64, 50, 25
    return 256, 750, 250


def build_command(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path]:
    if args.gpu not in ALLOWED_PHYSICAL_GPUS:
        raise ValueError(f"pull-v2 training only permits physical GPU6/7; got GPU{args.gpu}.")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if args.checkpoint is not None and not args.checkpoint.resolve().is_file():
        raise FileNotFoundError(args.checkpoint)
    num_envs, batches, save_frequency = _topology(args.mode)
    default_name = f"pull_v2_W_{args.mode}_seed{args.seed}"
    run_name = default_name if args.run_name is None else args.run_name
    if not run_name or "/" in run_name or "\\" in run_name:
        raise ValueError(f"--run-name must be a non-empty leaf name; got {run_name!r}")
    experiment_dir = (
        ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull" / run_name
        if args.experiment_dir is None
        else args.experiment_dir.resolve()
    )
    if experiment_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing pull-v2 output: {experiment_dir}")
    checkpoint_override = (
        [f"checkpoint={args.checkpoint.resolve()}"] if args.checkpoint is not None else []
    )
    argv = [
        str(PYTHON),
        "-B",
        "-m",
        "accelerate.commands.launch",
        "--num_processes",
        "1",
        "--num_machines",
        "1",
        "--mixed_precision",
        "no",
        "--dynamo_backend",
        "no",
        "--main_process_port",
        str(29860 + args.seed + (0 if args.mode == "smoke" else 10)),
        "gr00t/rl/train_agent_trl.py",
        "+exp=wbmanip/door_open_a2_pull_lstm",
        f"+ablation={ABLLATION}",
        f"seed={args.seed}",
        *checkpoint_override,
        f"num_envs={num_envs}",
        f"algo.trl.num_total_batches={batches}",
        f"callbacks.model_save.save_frequency={save_frequency}",
        "headless=true",
        "use_wandb=false",
        "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false",
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        "base_dir=logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull",
        "project_name=a2_piper_full_stage_a2_pull",
        f"experiment_name={run_name}",
        f"experiment_dir={experiment_dir}",
        "+device=cuda:0",
    ]
    process_env = {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(args.gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "WANDB_MODE": "offline",
    }
    return argv, process_env, experiment_dir


def main() -> int:
    args = _parse_args()
    argv, process_env, experiment_dir = build_command(args)
    print("[pull-v2] training artifact:", experiment_dir)
    print("[pull-v2] command:", " ".join(argv))
    print("[pull-v2] environment:", process_env)
    if not args.run:
        return 0
    run_env = os.environ.copy()
    run_env.update(process_env)
    result = subprocess.run(argv, cwd=ROOT, env=run_env, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    expected = experiment_dir / "model_step_000050.pt" if args.mode == "smoke" else experiment_dir / "model_step_000750.pt"
    if not expected.is_file():
        raise RuntimeError(f"training exited without required checkpoint: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
