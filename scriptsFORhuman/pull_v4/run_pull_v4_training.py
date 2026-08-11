#!/usr/bin/env python3
"""Prepare or run pull-v4 A/B training on the authorized physical GPUs 4-7."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
ALLOWED_PHYSICAL_GPUS = (4, 5, 6, 7)
WARM_CHECKPOINT = (
    TRAIN_ROOT / "pull_v2_W_wave2_relay_seed1/model_step_000750.pt"
)
PLAN_ID = "a2_piper_pull_v4_annuity_removal_and_frame_approach"
STAGE_TIME = "[250,100,100,100,250,300]"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("A", "B"), required=True)
    parser.add_argument("--mode", choices=("smoke", "formal"), required=True)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_PHYSICAL_GPUS, required=True)
    parser.add_argument("--run-name")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--relay", action="store_true")
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def _variant_config(variant: str) -> str:
    if variant == "A":
        return "wbmanip/pull_v4_A_annuity_removal"
    if variant == "B":
        return "wbmanip/pull_v4_B_frame_approach"
    raise ValueError(f"unknown pull-v4 variant: {variant!r}")


def _topology(mode: str) -> tuple[int, int, int]:
    return (64, 50, 50) if mode == "smoke" else (256, 750, 250)


def _main_process_port(*, variant: str, seed: int, mode: str, relay: bool) -> int:
    """Return a disjoint port for every permitted training family."""

    family = 40 if relay else (0 if mode == "smoke" else 20)
    return 29980 + family + (0 if variant == "A" else 10) + seed


def build_command(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path, Path]:
    if args.gpu not in ALLOWED_PHYSICAL_GPUS:
        raise ValueError(f"pull-v4 training only permits physical GPU4-7; got GPU{args.gpu}.")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if args.mode == "smoke" and (args.variant, args.seed, args.relay) != ("B", 0, False):
        raise ValueError("smoke is fixed to the distinct pull_v4_B_smoke_seed0 family")
    if args.relay and args.mode != "formal":
        raise ValueError("relay is only valid for a formal 750-batch run")
    checkpoint = WARM_CHECKPOINT if args.checkpoint is None else args.checkpoint.resolve()
    if not args.relay and checkpoint != WARM_CHECKPOINT.resolve():
        raise ValueError(
            "pull-v4 training must bind the canonical v2 warm checkpoint unless --relay is explicit: "
            f"expected={WARM_CHECKPOINT}, got={checkpoint}"
        )
    if args.relay and args.checkpoint is None:
        raise ValueError("--relay requires an explicit selected checkpoint")
    if not checkpoint.is_file():
        raise FileNotFoundError(f"required pull-v4 warm checkpoint is missing: {checkpoint}")
    num_envs, batches, save_frequency = _topology(args.mode)
    if args.relay and args.seed in (0, 1):
        expected_run_name = f"pull_v4_{args.variant}_relay_seed{args.seed}"
    elif args.relay:
        expected_run_name = f"pull_v4_{args.variant}_seed2"
    elif args.mode == "smoke":
        expected_run_name = "pull_v4_B_smoke_seed0"
    elif args.seed == 2:
        expected_run_name = f"pull_v4_{args.variant}_seed2"
    else:
        expected_run_name = f"pull_v4_{args.variant}_wave1_seed{args.seed}"
    run_name = expected_run_name if args.run_name is None else args.run_name
    if run_name != expected_run_name:
        raise ValueError(
            f"run family identity mismatch: expected {expected_run_name!r}, got {run_name!r}"
        )
    if "/" in run_name or "\\" in run_name or run_name in {"", ".", ".."}:
        raise ValueError(f"--run-name must be a leaf name; got {run_name!r}")
    experiment_dir = TRAIN_ROOT / run_name
    if experiment_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing pull-v4 output: {experiment_dir}")
    argv = [
        str(PYTHON), "-B", "-m", "accelerate.commands.launch",
        "--num_processes", "1", "--num_machines", "1", "--mixed_precision", "no",
        "--dynamo_backend", "no", "--main_process_port", str(
            _main_process_port(variant=args.variant, seed=args.seed, mode=args.mode, relay=args.relay)
        ),
        "gr00t/rl/train_agent_trl.py", "+exp=wbmanip/door_open_a2_pull_lstm",
        f"+ablation={_variant_config(args.variant)}", f"seed={args.seed}",
        f"checkpoint={checkpoint}", f"num_envs={num_envs}",
        f"algo.trl.num_total_batches={batches}",
        f"callbacks.model_save.save_frequency={save_frequency}",
        "headless=true", "use_wandb=false", "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false", "checkpoint_load_mode=policy_only",
        "auto_load_latest=false", "base_dir=logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull",
        "project_name=a2_piper_full_stage_a2_pull", f"experiment_name={run_name}",
        f"experiment_dir={experiment_dir}", f"env.config.a2_v20_R1_plan_id={PLAN_ID}",
        f"env.config.max_stage_time={STAGE_TIME}", "env.config.max_episode_length_s=24",
        "rewards.reward_scales.a2_corridor_door_wide=0.0",
        "rewards.reward_scales.a2_corridor_clean_passage=1.0",
        f"+device=cuda:0",
    ]
    if args.variant == "B":
        argv.append("rewards.reward_scales.a2_pull_frame_approach=6.0")
    process_env = {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(args.gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }
    return argv, process_env, experiment_dir, checkpoint


def main() -> int:
    args = _parse_args()
    argv, process_env, experiment_dir, checkpoint = build_command(args)
    expected_step = 50 if args.mode == "smoke" else 750
    expected = experiment_dir / f"model_step_{expected_step:06d}.pt"
    print("[pull-v4] variant:", args.variant)
    print("[pull-v4] source checkpoint:", checkpoint)
    print("[pull-v4] expected checkpoint:", expected)
    print("[pull-v4] command:", " ".join(argv))
    print("[pull-v4] environment:", process_env)
    if not args.run:
        return 0
    experiment_dir.mkdir(parents=False, exist_ok=False)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with (experiment_dir / "runner.log").open("x", encoding="utf-8") as log_stream:
        process = subprocess.Popen(argv, cwd=ROOT, env=run_env, stdout=log_stream, stderr=subprocess.STDOUT)
        returncode = process.wait()
    if returncode != 0:
        raise SystemExit(returncode)
    if not expected.is_file():
        raise RuntimeError(f"training exited without required checkpoint: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
