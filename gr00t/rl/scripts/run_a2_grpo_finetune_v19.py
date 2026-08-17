#!/usr/bin/env python3
"""Launch and evaluate the C-B2H v19 two-GPU GRPO fine-tune."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
CONFIG = "wbmanip/door_open_a2_base_v19_b2h_toeout6_grpo"
BASE_CHECKPOINT = (
    REPO_ROOT
    / "logs_rl/by_batch/cb2h_v19_toeout6_pitch50_20260805/"
    "formal_4x64_8k_gpu4-7_timeoutfix_retry/model_step_008000.pt"
)
OUTPUT_BASE = (
    REPO_ROOT
    / "logs_rl/by_batch/cb2h_v19_toeout6_pitch50_grpo_20260811"
)
EVAL_RUNNER = REPO_ROOT / "gr00t/rl/scripts/run_a2_toeout6_student_eval.py"
GRPO_GPU_UUIDS = {
    2: "GPU-7bb5efaa-24d3-ea73-c1ee-9b3341a708be",
    3: "GPU-ffc02ac2-e15e-00e3-f842-6f501cb0b6e5",
}


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT),
            "HYDRA_FULL_ERROR": "1",
            "WANDB_MODE": "disabled",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def launch_training(args: argparse.Namespace) -> None:
    run_root = (OUTPUT_BASE / args.run_name).resolve()
    checkpoint = args.checkpoint.expanduser().resolve()
    command = [
        str(PYTHON),
        "gr00t/rl/train_agent_trl.py",
        f"+exp={CONFIG}",
        f"checkpoint={checkpoint}",
        f"checkpoint_load_mode={args.checkpoint_load_mode}",
        "auto_load_latest=false",
        f"experiment_dir={run_root}",
        f"experiment_name={args.run_name}",
        f"num_envs={args.num_envs}",
        "num_gpus=2",
        "multi_gpu=true",
        "headless=true",
        "use_wandb=false",
        "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=true",
        f"algo.trl.num_total_batches={args.target_iterations}",
        "algo.trl.num_ppo_epochs=1",
        f"algo.trl.num_mini_batches={args.num_mini_batches}",
        f"algo.config.num_mini_batches={args.num_mini_batches}",
        f"algo.trl.per_device_train_batch_size={args.per_device_train_batch_size}",
        f"algo.trl.learning_rate={args.learning_rate}",
        f"algo.config.actor_learning_rate={args.learning_rate}",
        f"algo.config.grpo_exploration_std={args.std}",
        f"algo.config.max_noise_std={args.std}",
        f"algo.config.grpo_action_rate_lambda={args.action_rate_lambda}",
        f"callbacks.model_save.save_frequency={args.save_frequency}",
        "callbacks.model_save.strict_mode=true",
    ]
    run_root.mkdir(parents=True, exist_ok=True)
    processes: dict[int, tuple[int, subprocess.Popen[bytes], object]] = {}
    for rank, gpu in enumerate((2, 3)):
        rank_root = run_root / "ranks" / f"rank{rank}"
        hydra_root = rank_root / ".hydra"
        rank_root.mkdir(parents=True, exist_ok=True)
        rank_command = [
            *command,
            f"seed={rank}",
            f"hydra.run.dir={hydra_root}",
            f"hydra.sweep.dir={hydra_root}",
        ]
        env = _base_env()
        for name in tuple(env):
            if name.startswith("A2_"):
                env.pop(name)
        for name in (
            "ACCELERATE_TORCH_DEVICE",
            "ACCELERATE_BYPASS_DEVICE_MAP",
            "ACCELERATE_USE_CPU",
            "A2_GPU_BINDING_MODE",
        ):
            env.pop(name, None)
        env.update(
            {
                "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                "CUDA_VISIBLE_DEVICES": str(gpu),
                "RANK": str(rank),
                "WORLD_SIZE": "2",
                "LOCAL_RANK": "0",
                "LOCAL_WORLD_SIZE": "1",
                "MASTER_ADDR": "127.0.0.1",
                "MASTER_PORT": str(args.master_port),
                "A2_GPU_BINDING_MODE": "accelerate-ddp-2rank-gpu23-grpo-v1",
                "A2_EXPECTED_WORLD_SIZE": "2",
                "A2_EXPECTED_RANK": str(rank),
                "A2_EXPECTED_HOST_GPU_INDEX": str(gpu),
                "A2_EXPECTED_LOGICAL_GPU_INDEX": "0",
                "A2_EXPECTED_GPU_UUID": GRPO_GPU_UUIDS[gpu],
                "A2_EXPECTED_PHYSICAL_GPU_SET": "2,3",
                "A2_EXPECTED_MASTER_ADDR": "127.0.0.1",
                "A2_EXPECTED_MASTER_PORT": str(args.master_port),
            }
        )
        log_handle = (rank_root / "stdout-stderr.log").open("wb")
        process = subprocess.Popen(
            rank_command,
            cwd=REPO_ROOT,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        processes[process.pid] = (rank, process, log_handle)

    try:
        while processes:
            pid, status = os.wait()
            if pid not in processes:
                continue
            rank, process, log_handle = processes.pop(pid)
            process.returncode = os.waitstatus_to_exitcode(status)
            log_handle.close()
            if process.returncode != 0:
                for _, peer, _ in processes.values():
                    os.killpg(peer.pid, signal.SIGTERM)
                for _, peer, peer_log in processes.values():
                    peer.wait()
                    peer_log.close()
                raise subprocess.CalledProcessError(process.returncode, process.args)
            print(f"GRPO DDP rank {rank} completed", flush=True)
    except BaseException:
        for _, process, log_handle in processes.values():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait()
            log_handle.close()
        raise


def run_eval(
    *,
    checkpoint: Path,
    step: int,
    seed: int,
    gpu: int,
    output_root: Path,
    mode: str = "formal",
) -> None:
    command = [
        str(PYTHON),
        str(EVAL_RUNNER),
        "--mode",
        mode,
        "--controller",
        "student",
        "--seed",
        str(seed),
        "--checkpoint",
        str(checkpoint.expanduser().resolve()),
        "--expected-global-step",
        str(step),
        "--output-root",
        str(output_root.expanduser().resolve()),
    ]
    env = _base_env()
    env.update(
        {
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_VISIBLE_DEVICES": str(gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
        }
    )
    subprocess.run(command, cwd=REPO_ROOT, env=env, check=True)


def formal_successes(output_root: Path) -> int:
    payload = json.loads((output_root / "formal_student_metrics.json").read_text())
    episodes = payload["episodes"]
    return sum(bool(episode["goal_reached"]) for episode in episodes)


def eval_command(args: argparse.Namespace) -> None:
    run_eval(
        checkpoint=args.checkpoint,
        step=args.step,
        seed=args.seed,
        gpu=args.gpu,
        output_root=args.output_root,
        mode=args.mode,
    )
    if args.mode == "formal":
        print(f"successes={formal_successes(args.output_root)}/16", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    train = subparsers.add_parser("train")
    train.add_argument("--run-name", required=True)
    train.add_argument("--checkpoint", type=Path, default=BASE_CHECKPOINT)
    train.add_argument("--checkpoint-load-mode", choices=("policy_only", "full"), default="policy_only")
    train.add_argument("--target-iterations", type=int, required=True)
    train.add_argument("--num-envs", type=int, default=64)
    train.add_argument("--num-mini-batches", type=int, default=4)
    train.add_argument("--per-device-train-batch-size", type=int, default=16)
    train.add_argument("--learning-rate", type=float, default=3.0e-5)
    train.add_argument("--std", type=float, default=0.05)
    train.add_argument("--action-rate-lambda", type=float, default=0.0)
    train.add_argument("--save-frequency", type=int, default=10)
    train.add_argument("--master-port", type=int, default=29623)
    train.set_defaults(func=launch_training)

    evaluate = subparsers.add_parser("eval")
    evaluate.add_argument("--checkpoint", type=Path, required=True)
    evaluate.add_argument("--step", type=int, required=True)
    evaluate.add_argument("--seed", type=int, required=True)
    evaluate.add_argument("--gpu", type=int, choices=(2, 3), required=True)
    evaluate.add_argument("--output-root", type=Path, required=True)
    evaluate.add_argument("--mode", choices=("formal", "diagnose"), default="formal")
    evaluate.set_defaults(func=eval_command)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
