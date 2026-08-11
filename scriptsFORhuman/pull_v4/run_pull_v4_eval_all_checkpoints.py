#!/usr/bin/env python3
"""Prepare or run canonical pull-v4 D0 and checkpoint-eval cells."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v4"
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
STEPS = (250, 500, 750)
ALLOWED_PHYSICAL_GPUS = (4, 5, 6, 7)
WARM_CHECKPOINT = TRAIN_ROOT / "pull_v2_W_wave2_relay_seed1/model_step_000750.pt"


class PreparedEval(NamedTuple):
    argv: list[str]
    process_env: dict[str, str]
    output_dir: Path
    checkpoint: Path
    d0_lite: bool
    g6_budget: bool
    port: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("A", "B"))
    parser.add_argument("--seed", type=int, choices=(0, 1, 2))
    parser.add_argument("--gpu", type=int, choices=ALLOWED_PHYSICAL_GPUS)
    parser.add_argument("--train-dir", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--step", type=int, choices=STEPS)
    parser.add_argument("--d0-lite", action="store_true")
    parser.add_argument(
        "--g6-budget",
        action="store_true",
        help="prepare one formal B Wave1 checkpoint with the diagnostic-neutral G6 time budget",
    )
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def _variant_config(variant: str) -> str:
    return "wbmanip/pull_v4_A_annuity_removal" if variant == "A" else "wbmanip/pull_v4_B_frame_approach"


def _diagnostic_terms(variant: str) -> str:
    terms = ["dont_push_door_handle", "target_root_distance", "pull_door_handle", "pull_door_hinge", "a2_corridor_clean_passage"]
    if variant == "B":
        terms.append("a2_pull_frame_approach")
    return "[" + ",".join(terms) + "]"


def _eval_port(*, variant: str, seed: int, step: int, d0_lite: bool, g6_budget: bool = False) -> int:
    # No two permitted cells share a port, including D0.
    if g6_budget:
        # Keep the extended diagnostics outside both the formal Wave1 range
        # and the D0 offset range.
        return 30300 + seed * 10 + STEPS.index(step)
    return 30100 + (80 if d0_lite else 0) + (0 if variant == "A" else 20) + seed * 10 + STEPS.index(step)


def _prepare_one(
    *,
    variant: str,
    seed: int,
    gpu: int,
    checkpoint: Path,
    output_dir: Path,
    d0_lite: bool,
    g6_budget: bool,
    step: int,
    port: int,
) -> PreparedEval:
    if gpu not in ALLOWED_PHYSICAL_GPUS:
        raise ValueError(f"pull-v4 eval only permits physical GPU4-7; got GPU{gpu}.")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if output_dir.parent.resolve() != EVAL_ROOT.resolve():
        raise ValueError(f"pull-v4 eval output must be directly under {EVAL_ROOT}: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing pull-v4 eval output: {output_dir}")
    eval_output = output_dir / "eval"
    hydra_root = output_dir / "hydra"
    argv = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl", f"checkpoint={checkpoint}",
        "checkpoint_load_mode=full", "auto_load_latest=false", "num_envs=16",
        "+algo.config.num_mini_batches=1", f"seed={seed}", "headless=true", "use_wandb=false",
        "algo.config.eval.num_eval_episodes=1", "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=true", "algo.config.eval.save_goal_reached_only=false",
        "algo.config.eval.save_trajectories=true", "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=16", "algo.config.eval.a2_diagnostic_trace_enabled=true",
        f"algo.config.eval.a2_diagnostic_reward_terms={_diagnostic_terms(variant)}",
        f"+ablation={_variant_config(variant)}",
        f"eval_output_dir={eval_output}", f"eval_log_dir={hydra_root}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}", "+device=cuda:0",
        f"hydra.run.dir={hydra_root}", f"+main_process_port={port}",
    ]
    if g6_budget:
        argv[argv.index(f"eval_output_dir={eval_output}"):argv.index(f"eval_output_dir={eval_output}")] = [
            "env.config.max_stage_time=[250,100,100,100,1750,300]",
            "env.config.max_episode_length_s=54",
            "env.config.a2_pull_v4_g6_budget_eval=true",
        ]
    process_env = {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline", "MASTER_PORT": str(port),
    }
    return PreparedEval(argv, process_env, output_dir, checkpoint, d0_lite, g6_budget, port)


def build_commands(args: argparse.Namespace) -> list[PreparedEval]:
    if args.d0_lite:
        if args.g6_budget:
            raise ValueError("--g6-budget is valid only for formal B Wave1 evaluations.")
        if args.train_dir is not None or args.variant not in (None, "B") or args.seed not in (None, 1) or args.step not in (None, 750):
            raise ValueError("D0-lite is fixed to pull-v4 B, seed1, step750.")
        gpu = 4 if args.gpu is None else args.gpu
        checkpoint = WARM_CHECKPOINT if args.checkpoint is None else args.checkpoint.resolve()
        if checkpoint != WARM_CHECKPOINT.resolve():
            raise ValueError(f"D0-lite must use the canonical warm checkpoint: {WARM_CHECKPOINT}")
        return [_prepare_one(variant="B", seed=1, gpu=gpu, checkpoint=checkpoint, output_dir=EVAL_ROOT / "D0_lite_B_seed1_step750", d0_lite=True, step=750, port=_eval_port(variant="B", seed=1, step=750, d0_lite=True))]
    if args.g6_budget:
        if args.variant != "B" or args.seed not in (0, 1) or args.gpu is None or args.step not in STEPS:
            raise ValueError("--g6-budget requires formal variant B, seed 0/1, GPU4-7, and one step 250/500/750.")
        if args.checkpoint is not None:
            raise ValueError("G6 eval derives checkpoint identity from the canonical Wave1 --train-dir and --step")
        if args.train_dir is None:
            raise ValueError("G6 eval requires the canonical B Wave1 --train-dir")
        train_dir = args.train_dir.resolve()
        expected_family = f"pull_v4_B_wave1_seed{args.seed}"
        if train_dir.parent.resolve() != TRAIN_ROOT.resolve() or train_dir.name != expected_family:
            raise ValueError(f"G6 eval train-dir identity is not canonical B Wave1: {train_dir}")
        if not train_dir.is_dir():
            raise FileNotFoundError(train_dir)
        checkpoint = train_dir / f"model_step_{args.step:06d}.pt"
        output_dir = EVAL_ROOT / f"{expected_family}_step{args.step}_g6_budget"
        return [
            _prepare_one(
                variant="B",
                seed=args.seed,
                gpu=args.gpu,
                checkpoint=checkpoint,
                output_dir=output_dir,
                d0_lite=False,
                g6_budget=True,
                step=args.step,
                port=_eval_port(variant="B", seed=args.seed, step=args.step, d0_lite=False, g6_budget=True),
            )
        ]
    if args.variant is None or args.seed is None or args.gpu is None or args.train_dir is None:
        raise ValueError("formal eval requires --variant, --seed, --gpu, and --train-dir")
    if args.checkpoint is not None:
        raise ValueError("formal eval derives checkpoint identity from --train-dir and --step")
    train_dir = args.train_dir.resolve()
    allowed_families = {
        (f"pull_v4_{args.variant}_seed2" if args.seed == 2 else f"pull_v4_{args.variant}_wave1_seed{args.seed}"),
    }
    if args.seed in (0, 1):
        allowed_families.add(f"pull_v4_{args.variant}_relay_seed{args.seed}")
    if train_dir.parent.resolve() != TRAIN_ROOT.resolve() or train_dir.name not in allowed_families:
        raise ValueError(f"formal eval train-dir identity is not canonical: {train_dir}")
    if not train_dir.is_dir():
        raise FileNotFoundError(train_dir)
    steps = (args.step,) if args.step is not None else STEPS
    prepared = []
    for step in steps:
        checkpoint = train_dir / f"model_step_{step:06d}.pt"
        prepared.append(_prepare_one(variant=args.variant, seed=args.seed, gpu=args.gpu, checkpoint=checkpoint, output_dir=EVAL_ROOT / f"{train_dir.name}_step{step}", d0_lite=False, g6_budget=False, step=step, port=_eval_port(variant=args.variant, seed=args.seed, step=step, d0_lite=False)))
    return prepared


def _require_eval_artifacts(output_dir: Path) -> None:
    metrics_path = output_dir / "eval/metrics_eval.json"
    trace_path = output_dir / "eval/stage2_5_step_trace.json"
    if not metrics_path.is_file() or not trace_path.is_file():
        raise RuntimeError(f"pull-v4 eval requires metrics and stage2_5 trace: {output_dir}")
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    terminals = payload.get("episode_terminal_diagnostics")
    if not isinstance(terminals, list) or len(terminals) != 16:
        raise RuntimeError(f"pull-v4 eval terminal diagnostics must contain exactly 16 records: {metrics_path}")
    if any(
        not isinstance(record, dict)
        or not isinstance(record.get("pull_v0_episode"), dict)
        or not isinstance(record.get("pull_v3_traversal"), dict)
        for record in terminals
    ):
        raise RuntimeError(f"pull-v4 terminal diagnostics are missing pull_v0_episode/pull_v3_traversal: {metrics_path}")
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(trace, list) or not trace:
        raise RuntimeError(f"pull-v4 eval stage2_5 trace must be non-empty: {trace_path}")


def main() -> int:
    args = _parse_args()
    prepared = build_commands(args)
    for item in prepared:
        print("[pull-v4] output:", item.output_dir)
        print("[pull-v4] checkpoint:", item.checkpoint)
        print("[pull-v4] port:", item.port)
        print("[pull-v4] command:", " ".join(item.argv))
        if not args.run:
            continue
        item.output_dir.parent.mkdir(parents=True, exist_ok=True)
        item.output_dir.mkdir(parents=False, exist_ok=False)
        run_env = os.environ.copy()
        run_env.update(item.process_env)
        with (item.output_dir / "runner.log").open("x", encoding="utf-8") as log_stream:
            process = subprocess.Popen(item.argv, cwd=ROOT, env=run_env, stdout=log_stream, stderr=subprocess.STDOUT)
            returncode = process.wait()
        if returncode != 0:
            raise SystemExit(returncode)
        _require_eval_artifacts(item.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
