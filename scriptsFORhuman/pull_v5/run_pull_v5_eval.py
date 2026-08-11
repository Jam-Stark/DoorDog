#!/usr/bin/env python3
"""Prepare dual-source Pull-v5 evaluation for one checkpoint."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EVAL_ROOT = ROOT / "logs_eval/a2_piper_pull_v5"
ALLOWED_GPUS = (4, 5, 6, 7)
WARM_CHECKPOINT = ROOT / (
    "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v4_B_wave1_seed1/model_step_000750.pt"
)


def build_command(*, checkpoint: Path, cell: str, step: int, source: str, gpu: int, output_dir: Path, allow_missing_checkpoint: bool = False) -> tuple[list[str], dict[str, str]]:
    if source not in {"canonical", "natural"}:
        raise ValueError(f"unknown evaluation source: {source!r}")
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"Pull-v5 eval only permits physical GPU4-7; got GPU{gpu}")
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    if output_dir.parent.resolve() != EVAL_ROOT.resolve():
        raise ValueError(f"Pull-v5 eval output must be directly under {EVAL_ROOT}: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite Pull-v5 eval output: {output_dir}")
    ratio = 1.0 if source == "canonical" else 0.0
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}", "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        "num_envs=16", "seed=0", "headless=true", "use_wandb=false",
        "+ablation=wbmanip/pull_v5_M_s0", "algo.config.load_optimizer=false",
        "algo.config.eval.num_eval_episodes=1", "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=true", "algo.config.eval.save_goal_reached_only=false",
        "algo.config.eval.save_trajectories=true", "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=16", "algo.config.eval.a2_diagnostic_trace_enabled=true",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=true",
        f"env.config.a2_pull_v5_stage4_bank_injection_ratio={ratio}",
        "env.config.a2_pull_v5_release_streak_steps=25",
        "env.config.a2_pull_v5_intervention_enabled=false",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "env.config.a2_pull_v5_reset_source_telemetry_enabled=true",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/eval_{cell}_step{step}_{source}.json",
        f"eval_output_dir={output_dir / 'eval'}", f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}", "+device=cuda:0",
        f"+main_process_port={30100 + gpu * 10 + (0 if source == 'canonical' else 1)}",
    ]
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, required=True)
    parser.add_argument("--output-root", type=Path, default=EVAL_ROOT)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for source in ("canonical", "natural"):
        output_dir = (args.output_root / f"{args.cell}_step{args.step}_{source}").resolve()
        command, process_env = build_command(
            checkpoint=args.checkpoint.resolve(), cell=args.cell, step=args.step,
            source=source, gpu=args.gpu, output_dir=output_dir,
            allow_missing_checkpoint=args.dry_run,
        )
        print(f"[pull-v5 eval {source}] command:", " ".join(command))
        print(f"[pull-v5 eval {source}] environment:", process_env)
        if not args.run:
            continue
        output_dir.mkdir(parents=True, exist_ok=False)
        run_env = os.environ.copy()
        run_env.update(process_env)
        with (output_dir / "runner.log").open("x", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
        if result.returncode != 0:
            return result.returncode
        metrics_path = output_dir / "eval" / "metrics_eval.json"
        if not metrics_path.is_file():
            raise RuntimeError(f"Pull-v5 eval exited without terminal metrics: {metrics_path}")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        terminal = metrics.get("episode_terminal_diagnostics") if isinstance(metrics, dict) else None
        if not isinstance(terminal, list) or not terminal:
            raise ValueError("Pull-v5 eval requires a non-empty episode_terminal_diagnostics list")
        receipt = {
            "schema": "a2_piper_pull_v5_eval_receipt_v2",
            "status": "PASS",
            "cell": args.cell,
            "checkpoint": str(args.checkpoint.resolve()),
            "step": args.step,
            "source": "canonical_bank" if source == "canonical" else "natural",
            "terminal_records": len(terminal),
            "output_dir": str(output_dir),
            "load_receipt_path": str(
                (ROOT / f"logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/eval_{args.cell}_step{args.step}_{source}.json").resolve()
            ),
        }
        with (output_dir / "eval_receipt.json").open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
