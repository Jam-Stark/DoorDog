#!/usr/bin/env python3
"""Build or run bilateral pull Stage0-2 train/eval/render commands on GPU0-3."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EXP = "wbmanip/door_open_a2_pull_lr_grasp_terminal_lstm"
WARMSTART = (
    ROOT
    / "logs_rl/a2_piper_pull_lr_grasp/warmstarts"
    / "pull_v6_F0_r6an_seed3_lr_rms_rebased.pt"
)
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_pull_lr_grasp"
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_lr_grasp"
ALLOWED_GPUS = (0, 1, 2, 3)
SIDES = ("left", "right")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    train = commands.add_parser("train")
    train.add_argument("--seed", type=int, choices=(0, 1, 2, 3), required=True)
    train.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    train.add_argument("--num-envs", type=int, default=4096)
    train.add_argument("--batches", type=int, default=250)
    train.add_argument("--save-frequency", type=int, default=25)
    train.add_argument("--checkpoint", type=Path, default=WARMSTART)
    train.add_argument("--run-prefix", default="pull_lr_grasp")
    train.add_argument("--port", type=int)
    train.add_argument(
        "--adaptive-rms",
        action="store_true",
        help="Allow actor observation RMS to update from the fresh checkpoint stats.",
    )
    train.add_argument(
        "--resume-full",
        action="store_true",
        help="Resume actor, critic, optimizer, scheduler, and trainer step from a full checkpoint.",
    )
    train.add_argument("--run", action="store_true")

    evaluate = commands.add_parser("eval")
    evaluate.add_argument("--side", choices=SIDES, required=True)
    evaluate.add_argument("--checkpoint", type=Path, required=True)
    evaluate.add_argument("--label", required=True)
    evaluate.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    evaluate.add_argument("--seed", type=int, default=0)
    evaluate.add_argument("--num-envs", type=int, default=64)
    evaluate.add_argument("--run", action="store_true")

    render = commands.add_parser("render")
    render.add_argument("--side", choices=SIDES, required=True)
    render.add_argument("--checkpoint", type=Path, required=True)
    render.add_argument("--label", required=True)
    render.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    render.add_argument("--seed", type=int, default=0)
    render.add_argument("--num-envs", type=int, default=1)
    render.add_argument("--render-env-id", type=int, default=0)
    render.add_argument("--run", action="store_true")
    return parser.parse_args()


def _leaf(value: str, label: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{label} must be a leaf name; got {value!r}")
    return value


def _runtime_env(
    gpu: int, port: int, *, expandable_segments: bool = False
) -> dict[str, str]:
    result = {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "WANDB_MODE": "offline",
        "MASTER_PORT": str(port),
    }
    if expandable_segments:
        result["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    return result


def _train_command(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path]:
    checkpoint = args.checkpoint.expanduser().resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if args.num_envs <= 0 or args.num_envs % 2 != 0:
        raise ValueError("bilateral training requires a positive even --num-envs")
    if args.batches <= 0 or args.save_frequency <= 0:
        raise ValueError("--batches and --save-frequency must be positive")
    run_name = f"{_leaf(args.run_prefix, 'run prefix')}_seed{args.seed}"
    output = TRAIN_ROOT / run_name
    port = args.port if args.port is not None else 32080 + args.seed
    if port <= 0 or port > 65535:
        raise ValueError("--port must be in [1, 65535]")
    checkpoint_load_mode = "full" if args.resume_full else "policy_only"
    command = [
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
        str(port),
        "gr00t/rl/train_agent_trl.py",
        f"+exp={EXP}",
        f"seed={args.seed}",
        f"num_envs={args.num_envs}",
        f"checkpoint={checkpoint}",
        f"checkpoint_load_mode={checkpoint_load_mode}",
        f"algo.config.load_optimizer={'true' if args.resume_full else 'false'}",
        "algo.config.actor.freeze_running_mean_std="
        f"{'false' if args.adaptive_rms else 'true'}",
        f"algo.trl.num_total_batches={args.batches}",
        f"callbacks.model_save.save_frequency={args.save_frequency}",
        f"env.config.a2_door_open_lr_permutation_seed={args.seed}",
        "headless=true",
        "use_wandb=false",
        "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false",
        "auto_load_latest=false",
        "base_dir=logs_rl/a2_piper_pull_lr_grasp",
        "project_name=a2_piper_pull_lr_grasp",
        f"experiment_name={run_name}",
        f"experiment_dir={output}",
        "+device=cuda:0",
    ]
    return command, _runtime_env(
        args.gpu, port, expandable_segments=args.resume_full
    ), output


def _eval_command(
    args: argparse.Namespace, *, render: bool
) -> tuple[list[str], dict[str, str], Path]:
    checkpoint = args.checkpoint.expanduser().resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    label = _leaf(args.label, "evaluation label")
    side = args.side
    num_envs = args.num_envs
    if num_envs <= 0:
        raise ValueError("--num-envs must be positive")
    if render and not 0 <= args.render_env_id < num_envs:
        raise ValueError("--render-env-id must be inside [0, --num-envs)")
    output = EVAL_ROOT / label / side
    port = (32280 if render else 32180) + args.gpu
    command = [
        str(PYTHON),
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=full",
        "+auto_load_latest=false",
        f"+num_envs={num_envs}",
        "+algo.config.num_mini_batches=1",
        f"+seed={args.seed}",
        "+headless=true",
        "+use_wandb=false",
        f"+env.config.a2_door_open_lr_distribution={side}",
        f"+env.config.a2_door_open_lr_permutation_seed={args.seed}",
        "+env.config.enable_staged_reset=false",
        "+env.config.staged_reset_ratios=[1.0,0.0,0.0,0.0,0.0,0.0]",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.dump_to_log_metrics=false",
        "algo.config.eval.save_trajectories=false",
        f"algo.config.eval.save_videos={'true' if render else 'false'}",
        f"algo.config.eval.num_save_episodes={num_envs}",
        "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "algo.config.eval.a2_diagnostic_reward_terms=[walk_to_door,gripper_handle_orientation,pregrasp_target_distance,grasp_target_distance,grasp,a2_stage2_close_command,a2_stage2_close_progress,a2_stage2_handle_center_y,a2_stage2_handle_approach_xz,a2_stage2_both_contact,a2_stage2_opposite_squeeze,a2_stage2_squeeze_force_window,a2_stage2_contact_stability,penalty_a2_stage2_over_force]",
        f"+simulator.config.render_results={'true' if render else 'false'}",
        f"+simulator.config.cameras.enable_cameras={'true' if render else 'false'}",
        f"eval_output_dir={output / 'eval'}",
        f"hydra.run.dir={output / 'hydra'}",
        f"env.config.save_rendering_dir={output / 'videos'}",
        "+device=cuda:0",
        f"+main_process_port={port}",
    ]
    if render:
        command.append("+simulator.config.cameras.camera_parent=trunk")
        command.append(
            f"+env.config.eval_rendering.render_env_ids=[{args.render_env_id}]"
        )
    return command, _runtime_env(args.gpu, port), output


def _run(
    command: list[str], process_env: dict[str, str], output: Path, *, execute: bool
) -> int:
    print("[pull-lr-grasp] output:", output)
    print("[pull-lr-grasp] command:", " ".join(command))
    print("[pull-lr-grasp] environment:", process_env)
    if not execute:
        return 0
    if output.exists():
        raise FileExistsError(f"refusing to overwrite output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=False, exist_ok=False)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with (output / "runner.log").open("x", encoding="utf-8") as log_stream:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=run_env,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return completed.returncode


def main() -> int:
    args = _parse_args()
    if args.command == "train":
        command, process_env, output = _train_command(args)
    else:
        command, process_env, output = _eval_command(
            args, render=args.command == "render"
        )
    return _run(command, process_env, output, execute=args.run)


if __name__ == "__main__":
    raise SystemExit(main())
