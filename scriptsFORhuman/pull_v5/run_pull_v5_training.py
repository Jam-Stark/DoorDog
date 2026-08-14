#!/usr/bin/env python3
"""Prepare or run one Pull-v5.1 2×2 short training cell."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
WARM_CHECKPOINT = TRAIN_ROOT / "pull_v4_B_wave1_seed1/model_step_000750.pt"
LOAD_RECEIPT_EXPERIMENT_NAME = "pull_v5_1_policy_only_load_attempt2"
LOAD_RECEIPT_EXPERIMENT = TRAIN_ROOT / LOAD_RECEIPT_EXPERIMENT_NAME
LOAD_RECEIPT_PATH = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_1_policy_only.json"
ALLOWED_GPUS = (4, 5, 6, 7)
CELLS = {
    "M_s0": ("pull_v5_M_s0", 0, 0.5),
    "M_s1": ("pull_v5_M_s1", 1, 0.5),
    "C_s0": ("pull_v5_C_s0", 0, 0.9),
    "C_s1": ("pull_v5_C_s1", 1, 0.9),
}


def build_command(*, cell: str, gpu: int, checkpoint: Path, allow_missing_checkpoint: bool = False, allow_g8_pure_a: bool = False) -> tuple[list[str], dict[str, str], Path]:
    if cell not in CELLS:
        raise ValueError(f"unknown Pull-v5 cell: {cell!r}")
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"Pull-v5 training only permits physical GPU4-7; got GPU{gpu}")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    config_name, seed, ratio = CELLS[cell]
    experiment_dir = TRAIN_ROOT / f"pull_v5_1_{cell}"
    if experiment_dir.exists():
        raise FileExistsError(f"refusing to overwrite Pull-v5 output: {experiment_dir}")
    command = [
        str(PYTHON), "-B", "-m", "accelerate.commands.launch",
        "--num_processes", "1", "--num_machines", "1", "--mixed_precision", "no",
        "--dynamo_backend", "no", "--main_process_port", str(29940 + gpu * 10 + seed),
        "--module", "gr00t.rl.train_agent_trl", "+exp=wbmanip/door_open_a2_pull_lstm",
        f"+ablation=wbmanip/{config_name}", f"seed={seed}", "num_envs=256",
        "algo.trl.num_total_batches=250", "callbacks.model_save.save_frequency=50",
        "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true",
        "use_wandb=false", "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false", "algo.config.load_optimizer=false",
        f"checkpoint={checkpoint}", f"base_dir={TRAIN_ROOT}",
        "project_name=a2_piper_full_stage_a2_pull", f"experiment_name=pull_v5_1_{cell}",
        f"experiment_dir={experiment_dir}",
        "env.config.a2_v20_R1_plan_id=a2_piper_pull_v5_bridge_occupancy_and_release_persistence",
        "env.config.max_episode_length_s=24", "env.config.max_stage_time=[250,100,100,100,250,300]",
        "env.config.enable_staged_reset=true", "env.config.staged_reset_max_samples_per_stage=200",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=true",
        f"env.config.a2_pull_v5_stage4_bank_injection_ratio={ratio}",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_intervention_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        f"env.config.a2_pull_v5_state_bank_allow_g8_pure_a={'true' if allow_g8_pure_a else 'false'}",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_1_{cell}.json",
        "env.config.a2_pull_v5_reset_source=natural",
        "+device=cuda:0",
    ]
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }, experiment_dir


def build_load_receipt_command(
    *, gpu: int, checkpoint: Path, receipt_path: Path, allow_missing_checkpoint: bool = False
) -> tuple[list[str], dict[str, str], Path]:
    """Build the train-module policy-only initialization route without updates."""

    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"Pull-v5 training only permits physical GPU4-7; got GPU{gpu}")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    receipt_path = receipt_path.resolve()
    if not receipt_path.is_relative_to(ROOT.resolve()):
        raise ValueError(f"Pull-v5 load receipt must remain inside the repository: {receipt_path}")
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite Pull-v5 load receipt: {receipt_path}")
    if LOAD_RECEIPT_EXPERIMENT.exists():
        raise FileExistsError(
            f"refusing to overwrite Pull-v5 load-receipt output: {LOAD_RECEIPT_EXPERIMENT}"
        )
    receipt_relative = receipt_path.relative_to(ROOT.resolve())
    experiment_dir = LOAD_RECEIPT_EXPERIMENT
    command = [
        str(PYTHON), "-B", "-m", "accelerate.commands.launch",
        "--num_processes", "1", "--num_machines", "1", "--mixed_precision", "no",
        "--dynamo_backend", "no", "--main_process_port", str(29940 + gpu * 10 + 9),
        "--module", "gr00t.rl.train_agent_trl", "+exp=wbmanip/door_open_a2_pull_lstm",
        "+ablation=wbmanip/pull_v5_M_s0", "seed=0", "num_envs=4",
        "algo.trl.num_total_batches=1", "checkpoint_load_mode=policy_only",
        "auto_load_latest=false", "headless=true", "use_wandb=false",
        "simulator.config.render_results=false", "simulator.config.cameras.enable_cameras=false",
        "algo.config.load_optimizer=false", f"checkpoint={checkpoint}", f"base_dir={TRAIN_ROOT}",
        "project_name=a2_piper_full_stage_a2_pull", f"experiment_name={LOAD_RECEIPT_EXPERIMENT_NAME}",
        f"experiment_dir={experiment_dir}",
        "env.config.a2_v20_R1_plan_id=a2_piper_pull_v5_bridge_occupancy_and_release_persistence",
        "env.config.max_episode_length_s=24", "env.config.enable_staged_reset=true",
        "env.config.staged_reset_max_samples_per_stage=200",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        "env.config.a2_pull_v5_state_bank_allow_g8_pure_a=false",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path={receipt_relative}",
        "+env.config.a2_pull_v5_load_receipt_only=true", "env.config.a2_pull_v5_reset_source=natural", "+device=cuda:0",
    ]
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }, experiment_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell", choices=tuple(CELLS))
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    parser.add_argument("--checkpoint", type=Path, default=WARM_CHECKPOINT)
    parser.add_argument("--load-receipt-only", action="store_true")
    parser.add_argument("--receipt-path", type=Path, default=LOAD_RECEIPT_PATH)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-g8-pure-a", action="store_true")
    args = parser.parse_args()
    checkpoint = args.checkpoint.resolve()
    if args.load_receipt_only:
        command, process_env, experiment_dir = build_load_receipt_command(
            gpu=args.gpu,
            checkpoint=checkpoint,
            receipt_path=args.receipt_path,
            allow_missing_checkpoint=args.dry_run,
        )
        expected = args.receipt_path.resolve()
    else:
        if args.cell is None:
            parser.error("--cell is required unless --load-receipt-only is selected")
        command, process_env, experiment_dir = build_command(
            cell=args.cell, gpu=args.gpu, checkpoint=checkpoint, allow_missing_checkpoint=args.dry_run,
            allow_g8_pure_a=args.allow_g8_pure_a,
        )
        expected = experiment_dir / "model_step_000250.pt"
    print("[pull-v5 training] command:", " ".join(command))
    print("[pull-v5 training] environment:", process_env)
    if args.load_receipt_only:
        print("[pull-v5 training] expected policy-only load receipt:", expected)
    else:
        print("[pull-v5 training] expected final checkpoint:", expected)
    if not args.run:
        return 0
    experiment_dir.mkdir(parents=True, exist_ok=False)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with (experiment_dir / "runner.log").open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        return result.returncode
    if args.load_receipt_only:
        if not expected.is_file():
            raise RuntimeError(f"load-receipt route exited without required receipt: {expected}")
    elif not expected.is_file():
        raise RuntimeError(f"training exited without required checkpoint: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
