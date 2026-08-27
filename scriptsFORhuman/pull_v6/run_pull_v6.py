#!/usr/bin/env python3
"""Build or execute pull-v6 F0 train/eval/render commands on GPU0-3."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
WINNER = (
    ROOT
    / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
    / "pull_v4_B_wave1_seed1/model_step_000750.pt"
)
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_pull_v6"
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v6"
ABLATION = "wbmanip/pull_v6_F0"
ALLOWED_GPUS = (0, 1, 2, 3)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    train = subparsers.add_parser("train")
    train.add_argument("--seed", type=int, choices=(0, 1, 2, 3), required=True)
    train.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    train.add_argument("--num-envs", type=int, default=256)
    train.add_argument("--batches", type=int, default=250)
    train.add_argument("--save-frequency", type=int, default=50)
    train.add_argument("--ablation", default=ABLATION)
    train.add_argument("--checkpoint", type=Path, default=WINNER)
    train.add_argument("--run-prefix", default="pull_v6_F0")
    train.add_argument("--run", action="store_true")

    evaluate = subparsers.add_parser("eval")
    evaluate.add_argument("--checkpoint", type=Path, required=True)
    evaluate.add_argument("--label", required=True)
    evaluate.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    evaluate.add_argument("--seed", type=int, default=0)
    evaluate.add_argument("--num-envs", type=int, default=16)
    evaluate.add_argument("--ablation", required=True)
    evaluate.add_argument("--near-c-lateral-micro-target-env", type=int)
    evaluate.add_argument("--run", action="store_true")

    render = subparsers.add_parser("render")
    render.add_argument("--checkpoint", type=Path, required=True)
    render.add_argument("--label", required=True)
    render.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    render.add_argument("--seed", type=int, default=0)
    render.add_argument("--num-envs", type=int, choices=(1, 2, 16), default=2)
    render.add_argument("--ablation", required=True)
    render.add_argument("--render-env-id", type=int)
    render.add_argument("--run", action="store_true")
    return parser.parse_args()


def _leaf(value: str, context: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{context} must be a leaf name; got {value!r}")
    return value


def _ablation(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("/")
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"pull-v6 ablation must be a non-empty Hydra group path; got {value!r}")
    config_path = ROOT / "gr00t/rl/config/ablation" / f"{value}.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"pull-v6 ablation config does not exist: {config_path}")
    return value


def _runtime_env(gpu: int, port: int) -> dict[str, str]:
    return {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "WANDB_MODE": "offline",
        "MASTER_PORT": str(port),
    }


def _train_command(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path]:
    checkpoint = args.checkpoint.expanduser().resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    run_prefix = _leaf(args.run_prefix, "pull-v6 train run prefix")
    run_name = f"{run_prefix}_seed{args.seed}"
    output = TRAIN_ROOT / run_name
    port = 31080 + args.seed
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
        "+exp=wbmanip/door_open_a2_pull_lstm",
        f"+ablation={args.ablation}",
        f"seed={args.seed}",
        f"num_envs={args.num_envs}",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=policy_only",
        "algo.config.load_optimizer=false",
        f"algo.trl.num_total_batches={args.batches}",
        f"callbacks.model_save.save_frequency={args.save_frequency}",
        "headless=true",
        "use_wandb=false",
        "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false",
        "auto_load_latest=false",
        "base_dir=logs_rl/a2_piper_pull_v6",
        "project_name=a2_piper_pull_v6",
        f"experiment_name={run_name}",
        f"experiment_dir={output}",
        "+device=cuda:0",
    ]
    return command, _runtime_env(args.gpu, port), output


def _eval_command(
    args: argparse.Namespace, *, render: bool
) -> tuple[list[str], dict[str, str], Path]:
    checkpoint = args.checkpoint.expanduser().resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    label = _leaf(args.label, "pull-v6 output label")
    ablation = _ablation(args.ablation)
    output = EVAL_ROOT / label
    port = (31280 if render else 31180) + args.gpu
    command = [
        str(PYTHON),
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        f"num_envs={args.num_envs}",
        "+algo.config.num_mini_batches=1",
        f"seed={args.seed}",
        "headless=true",
        "use_wandb=false",
        f"+ablation={ablation}",
        "env.config.staged_reset_ratios=[1.0,0.0,0.0,0.0,0.0,0.0]",
        "env.config.a2_pull_v6_stage4_bank_enabled=false",
        "env.config.a2_pull_v6_stage4_bank_row_label=uniform",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.dump_to_log_metrics=true",
        "algo.config.eval.save_trajectories=true",
        f"algo.config.eval.save_videos={'true' if render else 'false'}",
        f"algo.config.eval.num_save_episodes={args.num_envs}",
        "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "algo.config.eval.a2_diagnostic_reward_terms=[dont_push_door_handle,target_root_distance,pull_door_handle,pull_door_hinge,a2_corridor_clean_passage,a2_pull_frame_approach,a2_pull_v6_arm_tangent_progress,a2_pull_v6_handle_side_bonus,a2_pull_v6_arc_tracking,a2_pull_v6_pivot_excess_penalty,a2_pull_v6_hinge_momentum,a2_pull_v6_handoff_hinge_angle_deficit,a2_pull_v6_clean_release_quality,a2_pull_v6_premature_release_penalty]",
        f"simulator.config.render_results={'true' if render else 'false'}",
        f"simulator.config.cameras.enable_cameras={'true' if render else 'false'}",
        f"eval_output_dir={output / 'eval'}",
        f"hydra.run.dir={output / 'hydra'}",
        f"env.config.save_rendering_dir={output / 'videos'}",
        "+device=cuda:0",
        f"+main_process_port={port}",
    ]
    if render:
        command.append("+simulator.config.cameras.camera_parent=trunk")
    micro_target_env = getattr(args, "near_c_lateral_micro_target_env", None)
    if micro_target_env is not None:
        if render:
            raise ValueError("Pull-v6 near-C lateral micro-intervention is eval-only.")
        if micro_target_env < 0 or micro_target_env >= args.num_envs:
            raise ValueError(
                "Pull-v6 near-C lateral micro target env must be inside the eval batch; "
                f"got target={micro_target_env}, num_envs={args.num_envs}."
            )
        command.extend(
            [
                "+algo.config.eval.a2_pull_v6_passage_lateral_counterfactual_enabled=true",
                "+algo.config.eval.a2_pull_v6_passage_lateral_target_env_id="
                f"{micro_target_env}",
                "+algo.config.eval.a2_pull_v6_passage_lateral_gain_s_inv=4.0",
                "+algo.config.eval.a2_pull_v6_passage_lateral_max_world_y_speed_mps=0.20",
                "+algo.config.eval.a2_pull_v6_passage_lateral_trigger_max_deficit_m=0.10",
                "+algo.config.eval.a2_pull_v6_passage_lateral_pivot_guard_m=0.145",
            ]
        )
    render_env_id = getattr(args, "render_env_id", None)
    if render_env_id is not None:
        if render_env_id < 0 or render_env_id >= args.num_envs:
            raise ValueError(
                "Pull-v6 render env id must be inside the eval batch; "
                f"got env_id={render_env_id}, num_envs={args.num_envs}."
            )
        command.append(
            f"+env.config.eval_rendering.render_env_ids=[{render_env_id}]"
        )
    return command, _runtime_env(args.gpu, port), output


def _run(
    command: list[str], process_env: dict[str, str], output: Path, *, execute: bool
) -> int:
    print("[pull-v6] output:", output)
    print("[pull-v6] command:", " ".join(command))
    print("[pull-v6] environment:", process_env)
    if not execute:
        return 0
    if output.exists():
        raise FileExistsError(f"refusing to overwrite pull-v6 output: {output}")
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
