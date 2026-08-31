#!/usr/bin/env python3
"""Build or run full bilateral pull train/eval commands on GPU0-3."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
WINNER = (
    ROOT
    / "logs_rl/a2_piper_pull_lr_grasp"
    / "pull_lr_grasp_h450_xseg_resume_seed2/model_step_000250.pt"
)
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_pull_lr_full_stage"
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_lr_full_stage"
ABLATIONS = {
    "a": "wbmanip/pull_lr_full_gate_a",
    "b": "wbmanip/pull_lr_full_gate_b",
    "c": "wbmanip/pull_lr_full_handle_creation",
    "d": "wbmanip/pull_lr_full_left_stage3_residual_arm",
    "e": "wbmanip/pull_lr_full_left_stage3_residual_base_arm",
    "f": "wbmanip/pull_lr_full_left_stage3_hinge_creation",
    "g": "wbmanip/pull_lr_full_left_stage3_base_recovery",
    "h": "wbmanip/pull_lr_full_left_stage3_nonlinear_adapter",
    "i": "wbmanip/pull_lr_full_left_stage3_tangent_creation",
    "j": "wbmanip/pull_lr_full_left_stage3_e3_snapshot",
    "k": "wbmanip/pull_lr_full_left_stage3_post_e3_adapter",
    "l": "wbmanip/pull_lr_full_h10m_pose_probe",
    "m": "wbmanip/pull_lr_full_left_stage3_pose_quality",
    "n": "wbmanip/pull_lr_full_left_stage3_taskspace",
    "o": "wbmanip/pull_lr_full_bilateral_stage3_canonical",
    "p": "wbmanip/pull_lr_full_h14_teacher_capture",
    "q": "wbmanip/pull_lr_full_native_bilateral",
    "r": "wbmanip/pull_lr_full_native_bilateral_long_acq",
    "s": "wbmanip/pull_lr_full_native_bilateral_stage1_focus",
    "t": "wbmanip/pull_lr_full_h18d_base_lateral_probe",
    "u": "wbmanip/pull_lr_full_bilateral_stage3_absolute_b0",
}
ALLOWED_GPUS = (0, 1, 2, 3)
SIDES = ("left", "right", "bilateral")
ACTOR_CONTRACTS = {
    "source": "gr00t.rl.trl.modules.pull_v6_post_release_obs_override_actor.PullV6PostReleaseObsOverrideActor",
    "integrated": "gr00t.rl.trl.modules.pull_v6_post_release_integrated_actor.PullV6PostReleaseIntegratedActor",
    "output": "gr00t.rl.trl.modules.pull_v6_population_output_actor.PullV6PopulationOutputActor",
    "left_residual": "gr00t.rl.trl.modules.pull_v6_left_stage3_obs_residual_actor.PullV6LeftStage3ObsResidualActor",
    "left_base_residual": "gr00t.rl.trl.modules.pull_v6_left_stage3_base_residual_actor.PullV6LeftStage3BaseResidualActor",
    "left_nonlinear": "gr00t.rl.trl.modules.pull_v6_left_stage3_nonlinear_adapter_actor.PullV6LeftStage3NonlinearAdapterActor",
    "left_post_e3": "gr00t.rl.trl.modules.pull_v6_left_stage3_post_e3_adapter_actor.PullV6LeftStage3PostE3AdapterActor",
    "left_taskspace": "gr00t.rl.trl.modules.pull_v6_left_stage3_taskspace_actor.PullV6LeftStage3TaskspaceActor",
    "bilateral_taskspace": "gr00t.rl.trl.modules.pull_v6_bilateral_stage3_canonical_actor.PullV6BilateralStage3CanonicalActor",
    "native_bilateral": "gr00t.rl.trl.modules.pull_v6_native_bilateral_actor.PullV6NativeBilateralActor",
    "bilateral_absolute": "gr00t.rl.trl.modules.pull_v6_bilateral_stage3_absolute_actor.PullV6BilateralStage3AbsoluteActor",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    train = commands.add_parser("train")
    train.add_argument("--gate", choices=tuple(ABLATIONS), required=True)
    train.add_argument("--seed", type=int, choices=(0, 1, 2, 3), required=True)
    train.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    train.add_argument("--num-envs", type=int, default=4096)
    train.add_argument("--batches", type=int, default=25)
    train.add_argument("--save-frequency", type=int, default=25)
    train.add_argument("--checkpoint", type=Path, default=WINNER)
    train.add_argument("--run-prefix", default="pull_lr_full")
    train.add_argument("--port", type=int)
    train.add_argument("--resume-full", action="store_true")
    train.add_argument("--from-scratch", action="store_true")
    train.add_argument("--run", action="store_true")

    evaluate = commands.add_parser("eval")
    evaluate.add_argument("--gate", choices=tuple(ABLATIONS), required=True)
    evaluate.add_argument("--side", choices=SIDES, required=True)
    evaluate.add_argument("--checkpoint", type=Path, required=True)
    evaluate.add_argument("--label", required=True)
    evaluate.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    evaluate.add_argument("--seed", type=int, default=1001)
    evaluate.add_argument("--num-envs", type=int, default=16)
    evaluate.add_argument("--completion-stage", type=int, choices=(2, 5))
    evaluate.add_argument(
        "--actor-contract", choices=tuple(ACTOR_CONTRACTS), default="output"
    )
    evaluate.add_argument("--run", action="store_true")
    return parser.parse_args()


def _leaf(value: str, label: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{label} must be a leaf name; got {value!r}")
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
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    }


def _train_command(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path]:
    if args.from_scratch and args.resume_full:
        raise ValueError("--from-scratch and --resume-full are mutually exclusive")
    if args.gate in {"q", "r", "s"}:
        if not args.from_scratch and not args.resume_full:
            raise ValueError(
                "native bilateral gates require --from-scratch or an explicit native --resume-full checkpoint"
            )
        if args.resume_full and args.checkpoint.expanduser().resolve() == WINNER.resolve():
            raise ValueError("native bilateral gates cannot resume from the Stage0-2 winner")
    elif args.from_scratch:
        raise ValueError("--from-scratch is reserved for native bilateral training")
    checkpoint = None if args.from_scratch else args.checkpoint.expanduser().resolve()
    if checkpoint is not None and not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if args.num_envs <= 0 or args.num_envs % 2 != 0:
        raise ValueError("bilateral training requires a positive even --num-envs")
    if args.batches <= 0 or args.save_frequency <= 0:
        raise ValueError("--batches and --save-frequency must be positive")
    run_prefix = _leaf(args.run_prefix, "run prefix")
    run_name = f"{run_prefix}_gate_{args.gate}_seed{args.seed}"
    output = TRAIN_ROOT / run_name
    port = args.port if args.port is not None else 35080 + 100 * (args.gate == "b") + args.seed
    if port <= 0 or port > 65535:
        raise ValueError("--port must be in [1, 65535]")
    checkpoint_load_mode = (
        "full" if args.resume_full or args.from_scratch else "policy_only"
    )
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
        f"+ablation={ABLATIONS[args.gate]}",
        f"seed={args.seed}",
        f"num_envs={args.num_envs}",
        f"checkpoint={checkpoint if checkpoint is not None else 'null'}",
        f"checkpoint_load_mode={checkpoint_load_mode}",
        f"algo.config.load_optimizer={'true' if args.resume_full else 'false'}",
        f"algo.trl.num_total_batches={args.batches}",
        f"callbacks.model_save.save_frequency={args.save_frequency}",
        f"env.config.a2_door_open_lr_permutation_seed={args.seed}",
        "headless=true",
        "use_wandb=false",
        "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false",
        "auto_load_latest=false",
        "base_dir=logs_rl/a2_piper_pull_lr_full_stage",
        "project_name=a2_piper_pull_lr_full_stage",
        f"experiment_name={run_name}",
        f"experiment_dir={output}",
        "+device=cuda:0",
    ]
    return command, _runtime_env(args.gpu, port), output


def _eval_command(args: argparse.Namespace) -> tuple[list[str], dict[str, str], Path]:
    checkpoint = args.checkpoint.expanduser().resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if args.num_envs <= 0 or (args.side == "bilateral" and args.num_envs % 2 != 0):
        raise ValueError("evaluation requires positive envs and even envs for bilateral")
    label = _leaf(args.label, "evaluation label")
    output = EVAL_ROOT / label / args.side
    port = 35280 + args.gpu
    diagnostic_reward_terms = [
        "dont_push_door_handle",
        "target_root_distance",
        "pull_door_handle",
        "pull_door_hinge",
    ]
    if args.gate in {"m", "n"}:
        diagnostic_reward_terms.append("a2_pull_stage3_pose_quality")
    if args.gate == "o":
        diagnostic_reward_terms.append("a2_pull_stage3_bilateral_pose_quality")
    diagnostic_reward_terms.extend(
        [
            "a2_corridor_clean_passage",
            "a2_pull_frame_approach",
            "a2_pull_v6_arm_tangent_progress",
            "a2_pull_v6_handle_side_bonus",
            "a2_pull_v6_arc_tracking",
            "a2_pull_v6_pivot_excess_penalty",
            "a2_pull_v6_hinge_momentum",
            "a2_pull_v6_handoff_hinge_angle_deficit",
            "a2_pull_v6_clean_release_quality",
            "a2_pull_v6_premature_release_penalty",
        ]
    )
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
        f"+ablation={ABLATIONS[args.gate]}",
        f"algo.config.actor._target_={ACTOR_CONTRACTS[args.actor_contract]}",
        f"env.config.a2_door_open_lr_distribution={args.side}",
        f"env.config.a2_door_open_lr_permutation_seed={args.seed}",
        "env.config.staged_reset_ratios=[1.0,0.0,0.0,0.0,0.0,0.0]",
        "env.config.a2_pull_v6_stage4_bank_enabled=false",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.dump_to_log_metrics=true",
        "algo.config.eval.save_trajectories=true",
        "algo.config.eval.save_videos=false",
        f"algo.config.eval.num_save_episodes={args.num_envs}",
        "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "algo.config.eval.a2_diagnostic_reward_terms=["
        + ",".join(diagnostic_reward_terms)
        + "]",
        "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false",
        f"eval_output_dir={output / 'eval'}",
        f"hydra.run.dir={output / 'hydra'}",
        f"env.config.save_rendering_dir={output / 'videos'}",
        "+device=cuda:0",
        f"+main_process_port={port}",
    ]
    if args.completion_stage is not None:
        command.append(f"env.config.completion_stage={args.completion_stage}")
    return command, _runtime_env(args.gpu, port), output


def _run(
    command: list[str], process_env: dict[str, str], output: Path, *, execute: bool
) -> int:
    print("[pull-lr-full] output:", output)
    print("[pull-lr-full] command:", " ".join(command))
    print("[pull-lr-full] environment:", process_env)
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
    if completed.returncode == 0 and "eval_agent_trl" in command:
        required = (
            output / "eval/a2_v14_per_env_records.json",
            output / "eval/stage2_5_step_trace.json",
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(
                "evaluation returned zero without required artifacts: " + ", ".join(missing)
            )
    return completed.returncode


def main() -> int:
    args = _parse_args()
    if args.command == "train":
        command, process_env, output = _train_command(args)
    else:
        command, process_env, output = _eval_command(args)
    return _run(command, process_env, output, execute=args.run)


if __name__ == "__main__":
    raise SystemExit(main())
