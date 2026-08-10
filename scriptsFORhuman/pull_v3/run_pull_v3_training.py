#!/usr/bin/env python3
"""Prepare or run the pull-v3 traversal training contract on physical GPU2/3."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
V3_DIR = Path(__file__).resolve().parent
ABLATION = "wbmanip/pull_v3_T_traversal"
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
ALLOWED_PHYSICAL_GPUS = (2, 3)
DEFAULT_GPU_BY_SEED = {0: 2, 1: 3, 2: 2}
WARM_CHECKPOINT = (
    ROOT
    / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v2_W_wave2_relay_seed1/model_step_000750.pt"
)
V3_PLAN_ID = "a2_piper_pull_v3_release_then_cross_traversal"
V3_STAGE_TIME = "[250,100,100,100,250,300]"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "formal"), required=True)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_PHYSICAL_GPUS, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--experiment-dir", type=Path)
    parser.add_argument("--run-name", help="unique leaf name under the pull-v3 train root")
    parser.add_argument("--run", action="store_true", help="execute the prepared command")
    return parser.parse_args()


def _topology(mode: str) -> tuple[int, int, int]:
    if mode == "smoke":
        return 64, 50, 50
    return 256, 750, 250


def _leaf_name(value: str, option: str) -> str:
    if not value or "/" in value or "\\" in value or value in {".", ".."}:
        raise ValueError(f"{option} must be a non-empty leaf name; got {value!r}")
    return value


def _validate_train_destination(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.parent != TRAIN_ROOT.resolve():
        raise ValueError(
            "pull-v3 training outputs must be direct children of "
            f"{TRAIN_ROOT}; got {resolved}"
        )
    if not resolved.name.startswith("pull_v3_T_"):
        raise ValueError(
            "pull-v3 training output name must start with 'pull_v3_T_'; "
            f"got {resolved.name!r}"
        )
    return resolved


def build_command(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path, Path]:
    if args.gpu not in ALLOWED_PHYSICAL_GPUS:
        raise ValueError(f"pull-v3 training only permits physical GPU2/3; got GPU{args.gpu}.")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    checkpoint = WARM_CHECKPOINT if args.checkpoint is None else args.checkpoint.resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"required pull-v3 warm/relay checkpoint is missing: {checkpoint}")

    num_envs, batches, save_frequency = _topology(args.mode)
    default_name = f"pull_v3_T_{args.mode}_seed{args.seed}"
    run_name = default_name if args.run_name is None else _leaf_name(args.run_name, "--run-name")
    experiment_dir = (
        TRAIN_ROOT / run_name
        if args.experiment_dir is None
        else _validate_train_destination(args.experiment_dir)
    )
    experiment_dir = _validate_train_destination(experiment_dir)
    if experiment_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing pull-v3 output: {experiment_dir}")

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
        str(29960 + args.seed + (0 if args.mode == "smoke" else 10)),
        "gr00t/rl/train_agent_trl.py",
        "+exp=wbmanip/door_open_a2_pull_lstm",
        f"+ablation={ABLATION}",
        f"seed={args.seed}",
        f"checkpoint={checkpoint}",
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
        "env.config.a2_v20_R1_plan_id=" + V3_PLAN_ID,
        "env.config.max_episode_length_s=24",
        "env.config.max_stage_time=" + V3_STAGE_TIME,
        "env.config.a2_pull_threshold_mode=hard_gate",
        "env.config.a2_pull_e3_latch_threshold_m=0.02292371541261673",
        "rewards.reward_scales.a2_corridor_door_wide=4.2666667",
        "rewards.reward_scales.a2_corridor_clean_passage=1.0",
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
    return argv, process_env, experiment_dir, checkpoint


def _expected_checkpoint(experiment_dir: Path, mode: str) -> Path:
    step = 50 if mode == "smoke" else 750
    return experiment_dir / f"model_step_{step:06d}.pt"


def main() -> int:
    args = _parse_args()
    argv, process_env, experiment_dir, checkpoint = build_command(args)
    expected = _expected_checkpoint(experiment_dir, args.mode)
    runner_log = experiment_dir / "runner.log"
    print("[pull-v3] training artifact:", experiment_dir)
    print("[pull-v3] source checkpoint:", checkpoint)
    print("[pull-v3] expected checkpoint:", expected)
    print("[pull-v3] runner log:", runner_log)
    print("[pull-v3] command:", " ".join(argv))
    print("[pull-v3] environment:", process_env)
    if not args.run:
        return 0

    experiment_dir.mkdir(parents=True, exist_ok=False)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with runner_log.open("x", encoding="utf-8") as log_stream:
        process = subprocess.Popen(
            argv,
            cwd=ROOT,
            env=run_env,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            text=True,
        )
        print("[pull-v3] training pid:", process.pid)
        returncode = process.wait()
    if returncode != 0:
        raise SystemExit(returncode)
    if not expected.is_file():
        raise RuntimeError(f"training exited without required checkpoint: {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
