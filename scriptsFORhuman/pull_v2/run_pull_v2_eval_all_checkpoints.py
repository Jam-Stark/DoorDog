#!/usr/bin/env python3
"""Evaluate pull-v2 W checkpoints 250/500/750 with diagnostic step traces."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v2"
STEPS = (250, 500, 750)
ALLOWED_PHYSICAL_GPUS = (6, 7)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_PHYSICAL_GPUS, required=True)
    parser.add_argument("--train-dir", type=Path, required=True)
    parser.add_argument("--run-name", help="unique eval output prefix; defaults to W_seed{seed}")
    parser.add_argument("--run", action="store_true", help="execute the prepared commands")
    return parser.parse_args()


def _checkpoint(train_dir: Path, step: int) -> Path:
    checkpoint = train_dir.resolve() / f"model_step_{step:06d}.pt"
    if not checkpoint.is_file():
        raise FileNotFoundError(f"required pull-v2 checkpoint is missing: {checkpoint}")
    return checkpoint


def build_commands(args: argparse.Namespace) -> list[tuple[list[str], dict[str, str], Path]]:
    if args.gpu not in ALLOWED_PHYSICAL_GPUS:
        raise ValueError(f"pull-v2 eval only permits physical GPU6/7; got GPU{args.gpu}.")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    train_dir = args.train_dir.resolve()
    if not train_dir.is_dir():
        raise FileNotFoundError(train_dir)
    default_name = f"W_seed{args.seed}"
    run_name = default_name if args.run_name is None else args.run_name
    if not run_name or "/" in run_name or "\\" in run_name:
        raise ValueError(f"--run-name must be a non-empty leaf name; got {run_name!r}")
    commands = []
    for step in STEPS:
        checkpoint = _checkpoint(train_dir, step)
        outdir = EVAL_ROOT / f"{run_name}_step{step}"
        if outdir.exists():
            raise FileExistsError(f"refusing to overwrite existing pull-v2 eval output: {outdir}")
        eval_output = outdir / "eval"
        hydra_root = outdir / "hydra"
        argv = [
            str(PYTHON),
            "-B",
            "-m",
            "gr00t.rl.eval_agent_trl",
            f"checkpoint={checkpoint}",
            "checkpoint_load_mode=full",
            "+auto_load_latest=false",
            "+num_envs=16",
            "+algo.config.num_mini_batches=1",
            f"+seed={args.seed}",
            "+headless=true",
            "+use_wandb=false",
            "algo.config.eval.num_eval_episodes=1",
            "+algo.config.eval.eval_num_envs_episodes=true",
            "+algo.config.eval.dump_to_log_metrics=true",
            "algo.config.eval.save_goal_reached_only=false",
            "algo.config.eval.save_trajectories=true",
            "algo.config.eval.save_videos=false",
            "algo.config.eval.num_save_episodes=16",
            "algo.config.eval.a2_diagnostic_trace_enabled=true",
            "algo.config.eval.a2_diagnostic_reward_terms=[gripper_handle_orientation,grasp_target_distance,grasp,dont_push_door_handle,target_root_distance,a2_stage3_unlatch_hold,pull_door_handle,pull_door_hinge]",
            f"eval_output_dir={eval_output}",
            f"eval_log_dir={hydra_root}",
            f"env.config.save_rendering_dir={outdir / 'renderings'}",
            "+device=cuda:0",
            f"hydra.run.dir={hydra_root}",
        ]
        process_env = {
            "PYTHONPATH": str(ROOT),
            "CUDA_VISIBLE_DEVICES": str(args.gpu),
            "HYDRA_FULL_ERROR": "1",
            "PYTHONUNBUFFERED": "1",
            "WANDB_MODE": "offline",
        }
        commands.append((argv, process_env, outdir))
    return commands


def main() -> int:
    args = _parse_args()
    commands = build_commands(args)
    for argv, process_env, outdir in commands:
        print("[pull-v2] eval artifact:", outdir)
        print("[pull-v2] command:", " ".join(argv))
        print("[pull-v2] environment:", process_env)
        if not args.run:
            continue
        run_env = os.environ.copy()
        run_env.update(process_env)
        result = subprocess.run(argv, cwd=ROOT, env=run_env, check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
        metrics = outdir / "eval/metrics_eval.json"
        trace = outdir / "eval/stage2_5_step_trace.json"
        if not metrics.is_file() or not trace.is_file():
            raise RuntimeError(
                f"eval exited without required metrics and diagnostic trace: {metrics}, {trace}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
