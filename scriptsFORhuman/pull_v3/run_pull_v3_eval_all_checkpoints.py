#!/usr/bin/env python3
"""Prepare or run pull-v3 D0-lite and complete 250/500/750 checkpoint evaluation."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
V3_DIR = Path(__file__).resolve().parent
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v3"
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
STEPS = (250, 500, 750)
ALLOWED_PHYSICAL_GPUS = (2, 3)
V3_PLAN_ID = "a2_piper_pull_v3_release_then_cross_traversal"
V3_STAGE_TIME = "[250,100,100,100,250,300]"
WARM_CHECKPOINT = (
    ROOT
    / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v2_W_wave2_relay_seed1/model_step_000750.pt"
)


class PreparedEval(NamedTuple):
    argv: list[str]
    process_env: dict[str, str]
    output_dir: Path
    checkpoint: Path
    d0_lite: bool


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2))
    parser.add_argument("--gpu", type=int, choices=ALLOWED_PHYSICAL_GPUS)
    parser.add_argument("--train-dir", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--run-name", help="unique eval output prefix")
    parser.add_argument(
        "--d0-lite",
        action="store_true",
        help="evaluate the frozen v2 seed1 step750 actor under explicit v3 overrides",
    )
    parser.add_argument("--run", action="store_true", help="execute the prepared commands")
    return parser.parse_args()


def _leaf_name(value: str, option: str) -> str:
    if not value or "/" in value or "\\" in value or value in {".", ".."}:
        raise ValueError(f"{option} must be a non-empty leaf name; got {value!r}")
    return value


def _validate_train_dir(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.parent != TRAIN_ROOT.resolve() or not resolved.name.startswith("pull_v3_T_"):
        raise ValueError(
            "pull-v3 eval --train-dir must be a direct pull_v3_T_* training output; "
            f"got {resolved}"
        )
    if not resolved.is_dir():
        raise FileNotFoundError(resolved)
    return resolved


def _checkpoint(train_dir: Path, step: int) -> Path:
    checkpoint = train_dir / f"model_step_{step:06d}.pt"
    if not checkpoint.is_file():
        raise FileNotFoundError(f"required pull-v3 checkpoint is missing: {checkpoint}")
    return checkpoint


def _v3_overrides() -> list[str]:
    """Explicitly overlay v3 semantics after eval loads a checkpoint config.

    The evaluator merges CLI overrides over the saved training config.  Keeping
    this list in one place makes D0-lite and formal evals use the same guard
    contract and prevents an accidental v2-config replay.
    """

    # The evaluation entrypoint starts from config/base_eval.yaml, whose
    # env.config struct contains only save_rendering_dir.  Every v3 env/reward
    # key therefore uses Hydra's create (`+`) syntax here.  After checkpoint
    # loading, OmegaConf.merge(train_config, override_config) applies these
    # created values over the saved v2 values.
    env = lambda key, value: f"+env.config.{key}={value}"
    reward = lambda key, value: f"+rewards.reward_scales.{key}={value}"
    return [
        env("a2_v20_R1_plan_id", V3_PLAN_ID),
        env("max_episode_length_s", "24"),
        env("max_stage_time", V3_STAGE_TIME),
        env("a2_pull_direction_contract_version", "a2_piper_pull_direction_v1"),
        env("a2_pull_target_frame_version", "grasp_target_active_face_io_z_pre_v1"),
        env("a2_pull_target_orientation_wxyz", "[-0.5,-0.5,0.5,0.5]"),
        env("a2_pull_door_open_io", "in"),
        env("a2_pull_door_open_lr", "right"),
        env("a2_pull_robot_initial_side_x_sign", "1.0"),
        env("a2_pull_robot_initial_yaw_rad", "3.141592653589793"),
        env("a2_pull_active_handle_face_x_sign", "1.0"),
        env("a2_pull_travel_dir_x", "-1.0"),
        env("target_root_pos", "[-2.0,0.0,0.5]"),
        env("a2_pull_threshold_mode", "hard_gate"),
        env("a2_pull_effort_provenance", "ESTIMATE_ONLY"),
        env("a2_pull_add_walls", "false"),
        env("a2_stage3_to4_door_hinge_threshold", "0.25"),
        env("a2_stage3_unlatch_near_closed_hinge_threshold", "0.25"),
        env("a2_pull_e3_latch_threshold_m", "0.02292371541261673"),
        env("a2_stage3_to4_requires_grasp_streak", "true"),
        env("a2_stage4_release_hinge_threshold", "1.60"),
        env("a2_stage4_to5_door_hinge_threshold", "1.25"),
        env("a2_v20_send_hinge_threshold", "1.0"),
        env("a2_v20_R1_send_curriculum_enabled", "false"),
        env("a2_v20_R1_snapshot_guard_enabled", "false"),
        env("a2_v20_send_latch_enabled", "false"),
        env("a2_v20_pre_send_crossing_mode", "disabled"),
        env("a2_v20_telemetry_enabled", "false"),
        env("a2_v20_traversal_economics_enabled", "false"),
        env("a2_v20_arm_tie_enabled", "false"),
        env("a2_v20_arm_tangent_carry_scale", "0.0"),
        env("a2_v20_handle_arc_tracking_scale", "0.0"),
        env("a2_corridor_enabled", "false"),
        env("a2_corridor_latch_mode", "legacy_root_or_hinge"),
        env("a2_v20_R2_evidence_enabled", "false"),
        env("a2_v20_formal_launch", "false"),
        reward("a2_corridor_door_wide", "4.2666667"),
        reward("a2_corridor_clean_passage", "1.0"),
    ]


def _prepare_one(
    *,
    seed: int,
    gpu: int,
    checkpoint: Path,
    output_dir: Path,
    d0_lite: bool,
) -> PreparedEval:
    if gpu not in ALLOWED_PHYSICAL_GPUS:
        raise ValueError(f"pull-v3 eval only permits physical GPU2/3; got GPU{gpu}.")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if output_dir.parent.resolve() != EVAL_ROOT.resolve():
        raise ValueError(f"pull-v3 eval output must be directly under {EVAL_ROOT}: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing pull-v3 eval output: {output_dir}")
    eval_output = output_dir / "eval"
    hydra_root = output_dir / "hydra"
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
        f"+seed={seed}",
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
        "algo.config.eval.a2_diagnostic_reward_terms=[gripper_handle_orientation,grasp_target_distance,grasp,dont_push_door_handle,target_root_distance,a2_stage3_unlatch_hold,pull_door_handle,pull_door_hinge,a2_corridor_door_wide,a2_corridor_clean_passage]",
        *(_v3_overrides()),
        f"eval_output_dir={eval_output}",
        f"eval_log_dir={hydra_root}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}",
        "+device=cuda:0",
        f"hydra.run.dir={hydra_root}",
    ]
    process_env = {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "WANDB_MODE": "offline",
    }
    return PreparedEval(argv, process_env, output_dir, checkpoint, d0_lite)


def build_commands(args: argparse.Namespace) -> list[PreparedEval]:
    if args.d0_lite:
        if args.seed not in (None, 1):
            raise ValueError("D0-lite is fixed to seed1 so the v2 Wave2 relay baseline is explicit.")
        if args.gpu not in (None, 2, 3):
            raise ValueError("D0-lite accepts only a physical GPU2/3 lease.")
        checkpoint = WARM_CHECKPOINT if args.checkpoint is None else args.checkpoint.resolve()
        if checkpoint != WARM_CHECKPOINT.resolve():
            raise ValueError(f"D0-lite checkpoint must be the frozen warm actor: {WARM_CHECKPOINT}")
        output_dir = EVAL_ROOT / "D0_lite_seed1_step750"
        return [_prepare_one(seed=1, gpu=2 if args.gpu is None else args.gpu, checkpoint=checkpoint, output_dir=output_dir, d0_lite=True)]

    if args.seed is None or args.gpu is None or args.train_dir is None:
        raise ValueError("all-checkpoint eval requires --seed, --gpu, and --train-dir")
    train_dir = _validate_train_dir(args.train_dir)
    if not train_dir.name.endswith(f"seed{args.seed}"):
        raise ValueError(f"train directory seed suffix does not match --seed={args.seed}: {train_dir}")
    run_name = train_dir.name if args.run_name is None else _leaf_name(args.run_name, "--run-name")
    prepared = []
    for step in STEPS:
        checkpoint = _checkpoint(train_dir, step)
        output_dir = EVAL_ROOT / f"{run_name}_step{step}"
        prepared.append(
            _prepare_one(
                seed=args.seed,
                gpu=args.gpu,
                checkpoint=checkpoint,
                output_dir=output_dir,
                d0_lite=False,
            )
        )
    return prepared


def _required_artifacts(output_dir: Path) -> tuple[Path, Path]:
    metrics = output_dir / "eval/metrics_eval.json"
    trace = output_dir / "eval/stage2_5_step_trace.json"
    if not metrics.is_file() or not trace.is_file():
        raise RuntimeError(
            "pull-v3 eval exited without required metrics and diagnostic trace: "
            f"{metrics}, {trace}"
        )
    return metrics, trace


def _write_d0_receipt(prepared: PreparedEval, metrics_path: Path, trace_path: Path) -> None:
    if not prepared.d0_lite:
        return
    from analyze_pull_v3 import validate_d0_metrics

    acceptance = validate_d0_metrics(metrics_path, trace_path)
    receipt = {
        "schema": "pull_v3_d0_lite_receipt_v1",
        "status": "PASS",
        "plan_id": V3_PLAN_ID,
        "checkpoint": str(prepared.checkpoint.relative_to(ROOT)),
        "output_dir": str(prepared.output_dir.relative_to(ROOT)),
        "metrics": str(metrics_path.relative_to(ROOT)),
        "trace": str(trace_path.relative_to(ROOT)),
        "acceptance": acceptance,
    }
    receipt_path = V3_DIR / "D0_LITE_RECEIPT.json"
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite existing D0 receipt: {receipt_path}")
    receipt_path.write_text(
        __import__("json").dumps(receipt, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = _parse_args()
    prepared = build_commands(args)
    for item in prepared:
        runner_log = item.output_dir / "runner.log"
        expected = [
            item.output_dir / "eval/metrics_eval.json",
            item.output_dir / "eval/stage2_5_step_trace.json",
        ]
        print("[pull-v3] eval artifact:", item.output_dir)
        print("[pull-v3] checkpoint:", item.checkpoint)
        print("[pull-v3] expected artifacts:", *expected)
        print("[pull-v3] runner log:", runner_log)
        print("[pull-v3] command:", " ".join(item.argv))
        print("[pull-v3] environment:", item.process_env)
    if not args.run:
        return 0

    for item in prepared:
        item.output_dir.mkdir(parents=True, exist_ok=False)
        run_env = os.environ.copy()
        run_env.update(item.process_env)
        runner_log = item.output_dir / "runner.log"
        with runner_log.open("x", encoding="utf-8") as log_stream:
            process = subprocess.Popen(
                item.argv,
                cwd=ROOT,
                env=run_env,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                text=True,
            )
            print("[pull-v3] eval pid:", process.pid)
            returncode = process.wait()
        if returncode != 0:
            raise SystemExit(returncode)
        metrics, trace = _required_artifacts(item.output_dir)
        _write_d0_receipt(item, metrics, trace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
