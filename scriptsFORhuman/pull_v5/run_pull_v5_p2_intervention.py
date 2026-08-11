#!/usr/bin/env python3
"""Prepare paired frozen-actor control and release+tuck intervention runs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gr00t.rl.envs.door.a2_pull_telemetry import a2_pull_v5_release_tuck_override


PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
CHECKPOINT = ROOT / (
    "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v4_B_wave1_seed1/model_step_000750.pt"
)
OUTPUT_ROOT = ROOT / "logs_eval/a2_piper_pull_v5/p2_intervention"
ALLOWED_GPUS = (4, 5, 6, 7)


def audit_override_contract() -> None:
    policy = torch.arange(24, dtype=torch.float32).reshape(2, 12)
    hinge = torch.tensor([1.6, 1.2])
    aperture = torch.tensor([True, True])
    elapsed = torch.tensor([0, 0], dtype=torch.long)
    arm_target = torch.tensor(
        [[0.4, -0.2, 0.1, 0.0, -0.1, 0.2], [-0.3, 0.1, 0.2, 0.0, 0.2, -0.2]],
        dtype=torch.float32,
    )
    applied, active = a2_pull_v5_release_tuck_override(
        policy, hinge, aperture, elapsed, dt=0.02, enabled=True, arm_action=arm_target
    )
    if not torch.equal(applied[:, :5], policy[:, :5]):
        raise RuntimeError("P2 override changed the base command slice")
    if not torch.equal(applied[0, 5:11], arm_target[0]) or applied[0, 11].item() != 1.0:
        raise RuntimeError("P2 override did not set the default-pose arm and gripper-open slices")
    if not torch.equal(applied[1], policy[1]) or bool(active[1]):
        raise RuntimeError("P2 override activated outside the hinge threshold")


def build_command(*, checkpoint: Path, gpu: int, intervention: bool, output_dir: Path, allow_missing_checkpoint: bool = False) -> tuple[list[str], dict[str, str]]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"P2 only permits physical GPU4-7; got GPU{gpu}")
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    if not output_dir.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"P2 output must remain inside repository: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite P2 output: {output_dir}")
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}", "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        "num_envs=16", "seed=0", "headless=true", "use_wandb=false",
        "+ablation=wbmanip/pull_v5_M_s0", "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.eval_num_envs_episodes=true", "+algo.config.eval.dump_to_log_metrics=true",
        "algo.config.eval.save_videos=false", "algo.config.eval.num_save_episodes=16",
        f"env.config.a2_pull_v5_intervention_enabled={'true' if intervention else 'false'}",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=true",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/p2_{output_dir.name}.json",
        f"eval_output_dir={output_dir / 'eval'}", f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}", "+device=cuda:0",
    ]
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }


def _terminal_rows(output_dir: Path) -> list[dict]:
    path = output_dir / "eval" / "metrics_eval.json"
    if not path.is_file():
        raise RuntimeError(f"P2 output is missing terminal metrics: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("episode_terminal_diagnostics") if isinstance(document, dict) else None
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("P2 metrics_eval.json requires explicit episode_terminal_diagnostics")
    return rows


def _summarize(rows: list[dict]) -> dict[str, object]:
    pull_v5_rows = [row.get("pull_v5") for row in rows if isinstance(row.get("pull_v5"), dict)]
    if len(pull_v5_rows) != len(rows):
        raise ValueError("P2 terminal rows must all contain pull_v5 telemetry")
    required_steps = {item.get("release_streak_required_steps") for item in pull_v5_rows}
    if required_steps != {25}:
        raise ValueError(f"P2 terminal rows must report K=25; got {required_steps}")
    return {
        "episodes": len(rows),
        "persistent_release_count": sum(item.get("persistent_release") is True for item in pull_v5_rows),
        "persistent_release_required_steps": 25,
        "frame_passage_count": sum(bool((row.get("pull_v3_traversal") or {}).get("frame_passage")) for row in rows),
        "intervention_active_records": sum(item.get("intervention_active") is True for item in pull_v5_rows),
    }


def _write_receipt(path: Path, control: dict[str, object], intervention: dict[str, object], output_root: Path) -> dict[str, object]:
    receipt = {
        "schema": "a2_piper_pull_v5_p2_receipt_v2",
        "status": "PASS",
        "plan_id": "a2_piper_pull_v5_bridge_occupancy_and_release_persistence",
        "trigger": "aperture_ready_and_hinge_ge_1.60_rad",
        "duration_s": 1.0,
        "one_shot_per_episode": True,
        "base_action_slice_preserved": True,
        "arm_target": "actual_default_pose_via_cumulative_delta",
        "gripper_command": 1.0,
        "control": control,
        "intervention": intervention,
        "paired_output_root": str(output_root),
        "paired_binding": {
            "same_checkpoint": True,
            "same_seed": 0,
            "control_output": str(output_root / "control"),
            "intervention_output": str(output_root / "intervention"),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    audit_override_contract()
    summaries: dict[str, dict[str, object]] = {}
    for intervention in (False, True):
        label = "intervention" if intervention else "control"
        output_dir = (args.output_root / label).resolve()
        command, process_env = build_command(
            checkpoint=args.checkpoint.resolve(), gpu=args.gpu, intervention=intervention, output_dir=output_dir,
            allow_missing_checkpoint=args.dry_run,
        )
        print(f"[pull-v5 P2 {label}] command:", " ".join(command))
        print(f"[pull-v5 P2 {label}] environment:", process_env)
        if not args.run:
            continue
        output_dir.mkdir(parents=True, exist_ok=False)
        run_env = os.environ.copy()
        run_env.update(process_env)
        with (output_dir / "runner.log").open("x", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
        if result.returncode != 0:
            return result.returncode
        summaries[label] = _summarize(_terminal_rows(output_dir))
    if not args.run:
        return 0
    receipt_path = (args.receipt or args.output_root / "P2_INTERVENTION_RECEIPT.json").resolve()
    receipt = _write_receipt(receipt_path, summaries["control"], summaries["intervention"], args.output_root.resolve())
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
