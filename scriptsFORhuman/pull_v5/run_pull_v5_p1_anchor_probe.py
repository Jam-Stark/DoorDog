#!/usr/bin/env python3
"""Prepare the P1 canonical post-release anchor and door probe.

All scripted commands are high-level A2 commands.  The first five entries are
the base command and are never replaced by this probe; arm and gripper entries
remain policy-owned for P1.  The anchor is intentionally evaluated in an
open-field fixture before any door result is accepted.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
CHECKPOINT = ROOT / (
    "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/"
    "pull_v4_B_wave1_seed1/model_step_000750.pt"
)
OUTPUT_ROOT = ROOT / "logs_eval/a2_piper_pull_v5/p1_anchor_probe"
ALLOWED_GPUS = (4, 5, 6, 7)
CLOSER_BUCKETS = ("2.5-5", "5-9", "9-12")

# base vx, base vy, base wz, base aux-0, base aux-1, followed by arm[6] and gripper.
# These command vectors are passed through the existing high-level HOMIE interface.
ANCHOR_COMMAND_LIBRARY = {
    "straight_minus_x": ([-0.30, 0.0, 0.0, 0.0, 0.0], "policy_owned_arm", "policy_owned_gripper"),
    "turn_then_forward": ([0.0, 0.0, -0.55, 0.0, 0.0], "policy_owned_arm", "policy_owned_gripper"),
    "side_step": ([-0.18, 0.24, 0.0, 0.0, 0.0], "policy_owned_arm", "policy_owned_gripper"),
    "arc": ([-0.22, 0.0, 0.35, 0.0, 0.0], "policy_owned_arm", "policy_owned_gripper"),
}
LATTICE_COMMANDS = tuple(
    (name, scale)
    for name in ANCHOR_COMMAND_LIBRARY
    for scale in (0.5, 0.75, 1.0, 1.25, 1.5, 1.75)
)


def build_command(*, checkpoint: Path, gpu: int, source: str, output_dir: Path, fixture: str, command_name: str, allow_missing_checkpoint: bool = False) -> tuple[list[str], dict[str, str]]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"P1 only permits physical GPU4-7; got GPU{gpu}")
    if source not in {"canonical", "natural"}:
        raise ValueError(f"unknown P1 source: {source!r}")
    if fixture not in {"anchor", "door"}:
        raise ValueError(f"unknown P1 fixture: {fixture!r}")
    if command_name not in ANCHOR_COMMAND_LIBRARY:
        raise ValueError(f"unknown P1 command: {command_name!r}")
    if not checkpoint.is_file() and not allow_missing_checkpoint:
        raise FileNotFoundError(checkpoint)
    if not output_dir.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"P1 output must remain inside repository: {output_dir}")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite P1 output: {output_dir}")
    ratio = 1.0 if source == "canonical" else 0.0
    command = [
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}", "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        "num_envs=16", "seed=0", "headless=true", "use_wandb=false",
        "+ablation=wbmanip/pull_v5_M_s0", "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.eval_num_envs_episodes=true", "+algo.config.eval.dump_to_log_metrics=true",
        "algo.config.eval.save_videos=false", "algo.config.eval.num_save_episodes=16",
        f"env.config.a2_pull_v5_stage4_bank_injection_ratio={ratio}",
        "env.config.a2_pull_v5_stage4_bank_injection_enabled=true",
        "env.config.a2_pull_v5_state_bank_min_samples=64",
        "env.config.a2_pull_v5_state_bank_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt",
        f"env.config.a2_pull_v5_load_receipt_path=logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/p1_{output_dir.name}.json",
        "env.config.a2_pull_v5_snapshot_freeze_enabled=true",
        "+env.config.a2_pull_v5_probe_enabled=true",
        f"+env.config.a2_pull_v5_probe_fixture={fixture}",
        f"+env.config.a2_pull_v5_probe_command={command_name}",
        f"eval_output_dir={output_dir / 'eval'}", f"hydra.run.dir={output_dir / 'hydra'}",
        f"env.config.save_rendering_dir={output_dir / 'renderings'}", "+device=cuda:0",
    ]
    return command, {
        "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1", "WANDB_MODE": "offline",
    }


def _terminal_rows(output_dir: Path) -> list[dict]:
    metrics_path = output_dir / "eval" / "metrics_eval.json"
    if not metrics_path.is_file():
        raise RuntimeError(f"P1 runtime output is missing terminal metrics: {metrics_path}")
    document = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("P1 metrics_eval.json must be a mapping")
    rows = document.get("episode_terminal_diagnostics")
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("P1 metrics_eval.json requires explicit episode_terminal_diagnostics")
    return rows


def _write_receipt(path: Path, *, source: str, fixture: str, attempt: int, rows: list[dict], lattice: bool = False, lattice_state_count: int | None = None) -> dict:
    probes = [row.get("pull_v5_probe") for row in rows if isinstance(row.get("pull_v5_probe"), dict)]
    if not probes:
        raise ValueError("P1 terminal rows contain no pull_v5_probe diagnostics")
    anchor_pass = all(item.get("anchor_pass") is True for item in probes) if fixture == "anchor" else None
    frame_passage = sum(
        bool((row.get("pull_v3_traversal") or {}).get("frame_passage"))
        for row in rows
    )
    bucket_summary = {bucket: {"episodes": 0, "frame_passage": 0} for bucket in CLOSER_BUCKETS}
    for row in rows:
        force = row.get("hinge_drive_max_force_nm")
        if isinstance(force, bool) or not isinstance(force, (int, float)) or not math.isfinite(float(force)):
            raise ValueError("P1 terminal row requires finite hinge_drive_max_force_nm for closer stratification")
        force = float(force)
        bucket = "2.5-5" if 2.5 <= force < 5.0 else "5-9" if 5.0 <= force < 9.0 else "9-12" if 9.0 <= force <= 12.0 else None
        if bucket is not None:
            bucket_summary[bucket]["episodes"] += 1
            bucket_summary[bucket]["frame_passage"] += int(bool((row.get("pull_v3_traversal") or {}).get("frame_passage")))
    receipt = {
        "schema": "a2_piper_pull_v5_p1_receipt_v2",
        "status": "PASS" if (anchor_pass is not False) else "FAIL",
        "source": source,
        "fixture": fixture,
        "anchor_attempt": attempt,
        "lattice": lattice,
        "terminal_records": len(rows),
        "probe_records": len(probes),
        "anchor_pass": anchor_pass,
        "interface_feasible": all(item.get("command_solvable") is True for item in probes),
        "frame_passage_count": frame_passage,
        "closer_buckets": list(CLOSER_BUCKETS),
        "closer_bucket_records": bucket_summary,
        "command_library": sorted(ANCHOR_COMMAND_LIBRARY),
    }
    if lattice_state_count is not None:
        receipt["lattice_state_count"] = lattice_state_count
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--source", choices=("canonical", "natural"), default="canonical")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--anchor-attempt", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--mode", choices=("anchor", "probe", "lattice"), default="probe")
    parser.add_argument("--command", choices=tuple(ANCHOR_COMMAND_LIBRARY), default="straight_minus_x")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.anchor_attempt > 3:
        raise ValueError("P1 anchor retries are capped at three attempts")
    fixture = "anchor" if args.mode == "anchor" else "door"
    output_dir = (args.output_dir or OUTPUT_ROOT / f"{args.mode}_{args.source}_attempt{args.anchor_attempt}").resolve()
    command, process_env = build_command(
        checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
        output_dir=output_dir, fixture=fixture, command_name=args.command,
        allow_missing_checkpoint=args.dry_run,
    )
    print("[pull-v5 P1] anchor command library:", ANCHOR_COMMAND_LIBRARY)
    print("[pull-v5 P1] closer buckets:", CLOSER_BUCKETS)
    print("[pull-v5 P1] command:", " ".join(command))
    print("[pull-v5 P1] environment:", process_env)
    if not args.run:
        return 0
    if args.mode == "lattice":
        output_dir.mkdir(parents=True, exist_ok=False)
        all_rows: list[dict] = []
        for index, (lattice_command, _scale) in enumerate(LATTICE_COMMANDS):
            state_dir = output_dir / f"state_{index:02d}_{lattice_command}"
            state_command, state_env = build_command(
                checkpoint=args.checkpoint.resolve(), gpu=args.gpu, source=args.source,
                output_dir=state_dir, fixture="door", command_name=lattice_command,
                allow_missing_checkpoint=False,
            )
            state_dir.mkdir(parents=False, exist_ok=False)
            run_env = os.environ.copy()
            run_env.update(state_env)
            with (state_dir / "runner.log").open("x", encoding="utf-8") as stream:
                result = subprocess.run(
                    state_command, cwd=ROOT, env=run_env,
                    stdout=stream, stderr=subprocess.STDOUT, check=False,
                )
            if result.returncode != 0:
                return result.returncode
            all_rows.extend(_terminal_rows(state_dir))
        receipt_path = (args.receipt or output_dir / f"P1_lattice_{args.source}_attempt{args.anchor_attempt}_RECEIPT.json").resolve()
        receipt = _write_receipt(
            receipt_path, source=args.source, fixture="door", attempt=args.anchor_attempt,
            rows=all_rows, lattice=True, lattice_state_count=len(LATTICE_COMMANDS),
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    output_dir.mkdir(parents=True, exist_ok=False)
    run_env = os.environ.copy()
    run_env.update(process_env)
    with (output_dir / "runner.log").open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=ROOT, env=run_env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        return result.returncode
    rows = _terminal_rows(output_dir)
    receipt_path = (args.receipt or output_dir / f"P1_{args.mode}_{args.source}_attempt{args.anchor_attempt}_RECEIPT.json").resolve()
    receipt = _write_receipt(
        receipt_path, source=args.source, fixture=fixture, attempt=args.anchor_attempt,
        rows=rows, lattice=args.mode == "lattice",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if args.mode == "anchor" and receipt["anchor_pass"] is not True:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
