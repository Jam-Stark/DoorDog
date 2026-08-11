#!/usr/bin/env python3
"""Prepare the 64-env × 50-batch staged-reset census smoke.

The command is read-only by default.  Its output contract is a JSON census
with per-stage sample counts, reset sources, hinge/root/contact summaries, and
arm-state summaries; a producer may write that contract after the smoke run.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
TRAIN_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull"
CHECKPOINT = TRAIN_ROOT / "pull_v4_B_wave1_seed1/model_step_000750.pt"
OUTPUT_ROOT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/pull_v5_census"
ALLOWED_GPUS = (4, 5, 6, 7)


def build_command(*, variant: str, seed: int, gpu: int, output_dir: Path) -> tuple[list[str], dict[str, str]]:
    if variant not in {"v4_B", "v5"}:
        raise ValueError(f"unsupported census variant: {variant!r}")
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"census only permits physical GPU4-7; got GPU{gpu}")
    if not PYTHON.is_file():
        raise FileNotFoundError(PYTHON)
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite census output: {output_dir}")
    if not output_dir.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"census output must remain inside repository: {output_dir}")
    ablation = "wbmanip/pull_v4_B_frame_approach" if variant == "v4_B" else "wbmanip/pull_v5_M_s0"
    plan_id = (
        "a2_piper_pull_v4_annuity_removal_and_frame_approach"
        if variant == "v4_B"
        else "a2_piper_pull_v5_bridge_occupancy_and_release_persistence"
    )
    command = [
        str(PYTHON), "-B", "-m", "accelerate.commands.launch",
        "--num_processes", "1", "--num_machines", "1", "--mixed_precision", "no",
        "--dynamo_backend", "no", "--main_process_port", str(29800 + gpu),
        "--module", "gr00t.rl.eval_agent_trl",
        f"checkpoint={CHECKPOINT}", "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        f"+ablation={ablation}", f"seed={seed}", "num_envs=64",
        "algo.config.eval.num_eval_episodes=1", "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=true", "algo.config.eval.num_save_episodes=64",
        "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true",
        "use_wandb=false", "simulator.config.render_results=false",
        "simulator.config.cameras.enable_cameras=false", f"env.config.a2_v20_R1_plan_id={plan_id}",
        "env.config.max_episode_length_s=24",
        f"eval_output_dir={output_dir / 'eval'}", f"hydra.run.dir={output_dir / 'hydra'}",
        "+env.config.a2_pull_v5_census_enabled=true",
        f"+env.config.a2_pull_v5_census_variant={variant}",
        f"+env.config.a2_pull_v5_census_seed={seed}",
        f"+env.config.a2_pull_v5_census_output_path={output_dir.relative_to(ROOT) / 'pull_v5_census.json'}",
        f"+device=cuda:0",
    ]
    if variant == "v5":
        command.extend((
            "algo.config.load_optimizer=false",
            "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        ))
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }


def summarize_census(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("census payload must be a mapping")
    stages = payload.get("stages")
    if not isinstance(stages, Mapping):
        raise ValueError("census payload requires a stages mapping")
    if not stages:
        raise ValueError("census stages mapping must be non-empty")
    result = {"schema": "a2_piper_pull_v5_census_v2", "status": "PASS", "stages": {}}
    for stage, value in stages.items():
        if not isinstance(value, Mapping):
            raise ValueError(f"stage {stage!r} census row must be a mapping")
        required = ("snapshot_count", "reset_source_counts", "hinge_rad", "root_state", "contact", "arm_state")
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"stage {stage!r} census row is missing {missing}")
        if isinstance(value["snapshot_count"], bool) or not isinstance(value["snapshot_count"], int) or value["snapshot_count"] < 0:
            raise ValueError(f"stage {stage!r} snapshot_count must be a non-negative integer")
        if not isinstance(value["reset_source_counts"], Mapping):
            raise ValueError(f"stage {stage!r} reset_source_counts must be a mapping")
        if any(source not in {"natural", "canonical_bank"} for source in value["reset_source_counts"]):
            raise ValueError(f"stage {stage!r} reset sources must be natural/canonical_bank")
        result["stages"][str(stage)] = {
            "snapshot_count": value["snapshot_count"],
            "reset_source_counts": dict(value["reset_source_counts"]),
            "hinge_rad": dict(value["hinge_rad"]),
            "root_state": dict(value["root_state"]),
            "contact": dict(value["contact"]),
            "arm_state": dict(value["arm_state"]),
        }
    return result


def _produce_census_from_run(output_dir: Path) -> dict[str, Any]:
    """Read the explicit producer payload emitted by the runtime worker."""

    candidates = sorted(output_dir.rglob("pull_v5_census.json")) + sorted(output_dir.rglob("census.json"))
    if len(candidates) != 1:
        raise RuntimeError(
            f"census run must emit exactly one pull_v5_census.json/census.json producer payload; found {candidates}"
        )
    payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    summary = summarize_census(payload)
    receipt = {
        "schema": "a2_piper_pull_v5_census_receipt_v2",
        "status": summary["status"],
        "variant": payload.get("variant"),
        "seed": payload.get("seed"),
        "producer_payload": str(candidates[0]),
        "stages": summary["stages"],
    }
    receipt_path = output_dir / "CENSUS_RECEIPT.json"
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("v4_B", "v5"), default="v4_B")
    parser.add_argument("--seed", type=int, choices=(0, 1), default=0)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--input", type=Path, help="validate a producer census JSON")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.input is not None:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        print(json.dumps(summarize_census(payload), indent=2, sort_keys=True))
        return 0
    output_dir = (args.output_dir or OUTPUT_ROOT / f"{args.variant}_seed{args.seed}").resolve()
    command, process_env = build_command(variant=args.variant, seed=args.seed, gpu=args.gpu, output_dir=output_dir)
    print("[pull-v5 census] command:", " ".join(command))
    print("[pull-v5 census] environment:", process_env)
    if not args.run:
        return 0
    output_dir.mkdir(parents=True, exist_ok=False)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with (output_dir / "runner.log").open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        return result.returncode
    receipt = _produce_census_from_run(output_dir)
    if args.receipt is not None:
        target = args.receipt.resolve()
        with target.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
