#!/usr/bin/env python3
"""Build (or explicitly launch) V6.1 counterfactual, train, eval, render, and capture commands."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_pull_v6_1"
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v6_1"
WINNER = ROOT / "logs_rl/a2_piper_pull_v6/pull_v6_F0_r6an_seed3/model_step_000025.pt"
GPUS = (0, 1, 2, 3)


def _leaf(value: str, label: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{label} must be a leaf name; got {value!r}.")
    return value


def _config(value: str) -> str:
    path = ROOT / "gr00t/rl/config/ablation" / f"{value}.yaml"
    if not path.is_file():
        raise FileNotFoundError(path)
    return value


def _checkpoint(value: Path) -> Path:
    path = value.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _runtime(gpu: int, port: int) -> dict[str, str]:
    return {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline", "MASTER_PORT": str(port),
    }


def _train(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path]:
    if args.ablation in {
        "wbmanip/pull_v6_1_P_integrated",
        "wbmanip/pull_v6_1_P_output_grouped",
        "wbmanip/pull_v6_1_P_output_b_focus",
    } and args.checkpoint is None:
        raise ValueError("V6.1P training requires an explicit selected Q winner --checkpoint.")
    checkpoint = _checkpoint(WINNER if args.checkpoint is None else args.checkpoint)
    if args.resume_full and args.checkpoint is None:
        raise ValueError("full training resume requires an explicit --checkpoint")
    name = f"{_leaf(args.run_name, 'run-name')}_seed{args.seed}"
    output = TRAIN_ROOT / name
    port = 33080 + args.gpu
    command = [
        str(PYTHON), "-B", "-m", "accelerate.commands.launch", "--num_processes", "1",
        "--num_machines", "1", "--mixed_precision", "no", "--dynamo_backend", "no",
        "--main_process_port", str(port), "gr00t/rl/train_agent_trl.py",
        "+exp=wbmanip/door_open_a2_pull_lstm", f"+ablation={_config(args.ablation)}",
        f"seed={args.seed}", f"num_envs={args.num_envs}", f"checkpoint={checkpoint}",
        f"checkpoint_load_mode={'full' if args.resume_full else 'policy_only'}",
        f"algo.config.load_optimizer={'true' if args.resume_full else 'false'}",
        f"algo.trl.num_total_batches={args.batches}", f"callbacks.model_save.save_frequency={args.save_frequency}",
        "headless=true", "use_wandb=false", "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false", "auto_load_latest=false",
        "base_dir=logs_rl/a2_piper_pull_v6_1", "project_name=a2_piper_pull_v6_1",
        f"experiment_name={name}", f"experiment_dir={output}", "+device=cuda:0",
    ]
    return command, _runtime(args.gpu, port), output


def _eval(args: argparse.Namespace, render: bool, capture: bool = False) -> tuple[list[str], dict[str, str], Path]:
    if args.ablation == "wbmanip/pull_v6_1_P_eval" and args.checkpoint is None:
        raise ValueError("V6.1P evaluation requires an explicit candidate --checkpoint.")
    checkpoint = _checkpoint(WINNER if args.checkpoint is None else args.checkpoint)
    label = _leaf(args.label, "label")
    output = EVAL_ROOT / label
    port = (33280 if render else 33180) + args.gpu
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl", f"checkpoint={checkpoint}",
        "checkpoint_load_mode=policy_only", "auto_load_latest=false", f"num_envs={args.num_envs}",
        "+algo.config.num_mini_batches=1", f"seed={args.seed}", "headless=true", "use_wandb=false",
        f"+ablation={_config(args.ablation)}", "+algo.config.eval.eval_num_envs_episodes=true",
        "algo.config.eval.num_eval_episodes=1", "+algo.config.eval.dump_to_log_metrics=true",
        "algo.config.eval.save_trajectories=true", f"algo.config.eval.save_videos={'true' if render else 'false'}",
        f"algo.config.eval.num_save_episodes={args.num_envs}", "algo.config.eval.a2_diagnostic_trace_enabled=true",
        f"simulator.config.render_results={'true' if render else 'false'}",
        f"simulator.config.cameras.enable_cameras={'true' if render else 'false'}",
        f"eval_output_dir={output / 'eval'}", f"hydra.run.dir={output / 'hydra'}",
        f"env.config.save_rendering_dir={output / 'videos'}", "+device=cuda:0", f"+main_process_port={port}",
    ]
    if render:
        command.append("+simulator.config.cameras.camera_parent=trunk")
        if args.render_env_id is not None:
            if not 0 <= args.render_env_id < args.num_envs:
                raise ValueError("render-env-id must belong to the evaluation batch.")
            command.append(f"+env.config.eval_rendering.render_env_ids=[{args.render_env_id}]")
    if args.stage4_steps is not None:
        command.append(f"env.config.max_stage_time=[250,100,100,100,{args.stage4_steps},800]")
    if args.max_episode_length_s is not None:
        command.append(f"env.config.max_episode_length_s={args.max_episode_length_s}")
    if capture:
        bank_path = args.bank_path.expanduser().resolve()
        try:
            bank_path = bank_path.relative_to(ROOT)
        except ValueError as error:
            raise ValueError("late-state bank path must be inside the repository root") from error
        command.extend([
            f"+env.config.a2_pull_v61_late_state_bank_capture_path={bank_path}",
            f"+env.config.a2_pull_v61_late_state_bank_capture_target_env_id={args.capture_target_env_id}",
            f"+env.config.a2_pull_v61_late_state_bank_capture_source_checkpoint={checkpoint}",
            f"+env.config.a2_pull_v61_late_state_bank_capture_source_config={args.ablation}",
        ])
        if args.overlay_base_bank is not None:
            overlay_base = args.overlay_base_bank.expanduser().resolve()
            try:
                overlay_base = overlay_base.relative_to(ROOT)
            except ValueError as error:
                raise ValueError("late-state overlay base bank must be inside the repository root") from error
            command.append(f"+env.config.a2_pull_v61_late_state_bank_overlay_base_path={overlay_base}")
    return command, _runtime(args.gpu, port), output


def _counterfactual(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path]:
    command, runtime, output = _eval(args, render=False)
    command.extend([
        "algo.config.eval.a2_pull_v61_post_release_intervention_enabled=true",
        f"algo.config.eval.a2_pull_v61_post_release_intervention_mode={args.mode}",
        f"algo.config.eval.a2_pull_v61_post_release_intervention_target_env_id={args.target_env_id}",
        "algo.config.eval.a2_pull_v61_post_release_intervention_arm_rate_rad_per_step=0.01",
        "algo.config.eval.a2_pull_v61_post_release_intervention_base_waypoint_progress_m=2.2",
        "algo.config.eval.a2_pull_v61_post_release_intervention_base_xy_gain_s_inv=1.0",
        "algo.config.eval.a2_pull_v61_post_release_intervention_base_max_world_speed_mps=0.25",
    ])
    return command, runtime, output


def _restore_smoke(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path]:
    command, runtime, output = _eval(args, render=False)
    late_bank_path = args.late_bank_path.expanduser().resolve()
    try:
        late_bank_path = late_bank_path.relative_to(ROOT)
    except ValueError as error:
        raise ValueError("late-state restore bank must be inside the repository root") from error
    if not (ROOT / late_bank_path).is_file():
        raise FileNotFoundError(ROOT / late_bank_path)
    stage = 5 if args.row_label == "e6_stage5_entry" else 4
    ratios = (
        "[0.000001,0.0,0.0,0.0,0.0,0.999999]"
        if stage == 5
        else "[0.000001,0.0,0.0,0.0,0.999999,0.0]"
    )
    command.extend([
        f"env.config.staged_reset_ratios={ratios}",
        "env.config.a2_pull_v61_late_state_bank_enabled=true",
        "env.config.a2_pull_v6_stage4_bank_enabled=false",
        f"++env.config.a2_pull_v61_late_state_bank_path={late_bank_path}",
        "++env.config.a2_pull_v61_stage5_row_weights={e6_stage5_entry:1.0}",
        f"env.config.max_stage_time=[250,100,100,100,{args.smoke_stage_steps},{args.smoke_stage_steps}]",
    ])
    stage4_weights = (
        "{post_release_d25:0.0,frame_passage:1.0}"
        if args.row_label == "frame_passage"
        else "{post_release_d25:1.0,frame_passage:0.0}"
    )
    command.append(f"++env.config.a2_pull_v61_stage4_row_weights={stage4_weights}")
    return command, runtime, output


def _emit(command: list[str], runtime: dict[str, str], output: Path, execute: bool) -> int:
    print("[pull-v6.1] output:", output)
    print("[pull-v6.1] command:", " ".join(command))
    print("[pull-v6.1] environment:", runtime)
    if not execute:
        return 0
    if output.exists():
        raise FileExistsError(f"refusing to overwrite output: {output}")
    output.mkdir(parents=True)
    process_env = os.environ.copy()
    process_env.update(runtime)
    with (output / "runner.log").open("x", encoding="utf-8") as stream:
        return subprocess.run(command, cwd=ROOT, env=process_env, stdout=stream, stderr=subprocess.STDOUT, check=False).returncode


def _common_eval(parser: argparse.ArgumentParser, *, default_ablation: str) -> None:
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--gpu", type=int, choices=GPUS, required=True)
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--num-envs", type=int, default=16)
    parser.add_argument("--stage4-steps", type=int)
    parser.add_argument("--max-episode-length-s", type=float)
    parser.add_argument("--ablation", default=default_ablation)
    parser.add_argument("--run", action="store_true")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    train = sub.add_parser("train")
    train.add_argument("--seed", type=int, choices=GPUS, required=True)
    train.add_argument("--gpu", type=int, choices=GPUS, required=True)
    train.add_argument("--run-name", required=True)
    train.add_argument(
        "--ablation",
        choices=(
            "wbmanip/pull_v6_1_Q_specialist",
            "wbmanip/pull_v6_1_Q_integrated_specialist",
            "wbmanip/pull_v6_1_Q_reward_repair_specialist",
            "wbmanip/pull_v6_1_Q_reward_repair_frozen_specialist",
            "wbmanip/pull_v6_1_Q_reward_repair_frozen_natural_specialist",
            "wbmanip/pull_v6_1_Q_onpolicy_d25_frozen_specialist",
            "wbmanip/pull_v6_1_Q_dynamics_obs_onpolicy_frozen_specialist",
            "wbmanip/pull_v6_1_Q_d25_gated_dynamics_specialist",
            "wbmanip/pull_v6_1_Q_d25_gated_refresh_specialist",
            "wbmanip/pull_v6_1_Q_sidechannel_d25_specialist",
            "wbmanip/pull_v6_1_Q_sidechannel_heading_specialist",
            "wbmanip/pull_v6_1_P_integrated",
            "wbmanip/pull_v6_1_P_output_grouped",
            "wbmanip/pull_v6_1_P_output_b_focus",
        ),
        required=True,
    )
    train.add_argument("--checkpoint", type=Path)
    train.add_argument("--num-envs", type=int, default=256)
    train.add_argument("--batches", type=int, default=50)
    train.add_argument("--save-frequency", type=int, default=25)
    train.add_argument("--resume-full", action="store_true")
    train.add_argument("--run", action="store_true")
    counter = sub.add_parser("counterfactual")
    _common_eval(counter, default_ablation="wbmanip/pull_v6_1_Q_counterfactual")
    counter.add_argument("--mode", choices=("policy", "arm_reset", "base_corridor", "both"), required=True)
    counter.add_argument("--target-env-id", type=int, default=14)
    evaluate = sub.add_parser("eval")
    _common_eval(evaluate, default_ablation="wbmanip/pull_v6_1_Q_eval")
    render = sub.add_parser("render")
    _common_eval(render, default_ablation="wbmanip/pull_v6_1_Q_eval")
    render.add_argument("--render-env-id", type=int)
    capture = sub.add_parser("capture")
    _common_eval(capture, default_ablation="wbmanip/pull_v6_1_Q_eval")
    capture.add_argument("--bank-path", type=Path, required=True)
    capture.add_argument("--capture-target-env-id", type=int, default=14)
    capture.add_argument("--overlay-base-bank", type=Path)
    restore = sub.add_parser("restore-smoke")
    _common_eval(restore, default_ablation="wbmanip/pull_v6_1_Q_eval")
    restore.add_argument(
        "--row-label",
        choices=("post_release_d25", "frame_passage", "e6_stage5_entry"),
        required=True,
    )
    restore.add_argument("--smoke-stage-steps", type=int, default=50)
    restore.add_argument(
        "--late-bank-path",
        type=Path,
        default=Path("logs_rl/a2_piper_pull_v6_1/late_state_bank/pull_v6_1_late_state_bank.pt"),
    )
    args = parser.parse_args()
    if args.command == "train":
        command, runtime, output = _train(args)
    elif args.command == "counterfactual":
        command, runtime, output = _counterfactual(args)
    elif args.command == "capture":
        command, runtime, output = _eval(args, render=False, capture=True)
    elif args.command == "restore-smoke":
        command, runtime, output = _restore_smoke(args)
    else:
        command, runtime, output = _eval(args, render=args.command == "render")
    return _emit(command, runtime, output, args.run)


if __name__ == "__main__":
    raise SystemExit(main())
