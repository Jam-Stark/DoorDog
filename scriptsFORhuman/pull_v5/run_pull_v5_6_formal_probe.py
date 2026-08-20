#!/usr/bin/env python3
"""Generate the v5.6 formal anchor, door-bucket, and G2 probe commands."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ALLOWED_GPUS = (4, 5, 6, 7)
PRIMARY_CHECKPOINT = ROOT / "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_B_wave1_seed1/model_step_000750.pt"
SPECIALIST_CHECKPOINT = ROOT / "logs_rl/a2_piper_pull_v5_6_hold_specialist/model_step_000750.pt"
ORIGINAL_HOMIE = ROOT / "gr00t/rl/data/policies/A2_Base/policy.pt"
OUTPUT_ROOT = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_formal_probe"
SEQUENCES = ("S1", "S2", "S3", "S4")
BUCKETS = ("2.5-5", "5-9", "9-12")


def _cuda_env(gpu: int) -> dict[str, str]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"formal probe is restricted to GPU4-7; got GPU{gpu}")
    env = dict(os.environ)
    env.update({"CUDA_VISIBLE_DEVICES": str(gpu), "HYDRA_FULL_ERROR": "1", "WANDB_MODE": "offline"})
    return env


def _command(*parts: str) -> list[str]:
    return [str(part) for part in parts]


def _common_command(*, output_dir: Path, gpu: int, phase: str, num_envs: int) -> list[str]:
    return _command(
        PYTHON,
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+ablation=wbmanip/pull_v5_6_formal_probe",
        f"checkpoint={PRIMARY_CHECKPOINT}",
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        f"num_envs={num_envs}",
        "seed=0",
        "headless=true",
        "use_wandb=false",
        "algo.config.load_optimizer=false",
        "algo.config.act_inference=true",
        "algo.config.action_layout=carrier12_legs12",
        "algo.config.specialist_terminal_only=true",
        f"env.config.formal_probe_phase={phase}",
        f"env.config.formal_primary_checkpoint={PRIMARY_CHECKPOINT}",
        f"env.config.formal_specialist_checkpoint={SPECIALIST_CHECKPOINT}",
        f"env.config.original_homie_checkpoint={ORIGINAL_HOMIE}",
        "env.config.formal_terminal_hold_steps=100",
        "env.config.formal_waypoint_tolerance_m=0.05",
        "env.config.formal_yaw_tolerance_rad=0.15",
        "env.config.formal_g3_attempt_cap=3",
        "env.config.formal_scientific_denominator_included=false",
        f"eval_output_dir={output_dir}",
        f"hydra.run.dir={output_dir / 'hydra'}",
        "+device=cuda:0",
    )


def _assert_command(command: Sequence[str], *, num_envs: int, phase: str) -> None:
    text = " ".join(command)
    required = (
        str(PRIMARY_CHECKPOINT),
        str(SPECIALIST_CHECKPOINT),
        "algo.config.act_inference=true",
        "algo.config.action_layout=carrier12_legs12",
        "algo.config.load_optimizer=false",
        f"num_envs={num_envs}",
        f"env.config.formal_probe_phase={phase}",
        "env.config.formal_terminal_hold_steps=100",
        "env.config.formal_waypoint_tolerance_m=0.05",
        "env.config.formal_yaw_tolerance_rad=0.15",
        "env.config.formal_g3_attempt_cap=3",
    )
    for item in required:
        if item not in text:
            raise AssertionError(f"formal command is missing {item!r}")
    if str(PRIMARY_CHECKPOINT) == str(SPECIALIST_CHECKPOINT):
        raise AssertionError("primary and specialist checkpoint paths must remain distinct")
    if "scheduler" in text.lower():
        raise AssertionError("formal probe must not compose a scheduler")


def build_anchor_command(*, sequence: str, attempt: int, gpu: int = 4, output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    if sequence not in SEQUENCES:
        raise ValueError(f"unknown formal sequence {sequence!r}")
    if isinstance(attempt, bool) or attempt not in range(3):
        raise ValueError("formal anchor attempt must be 0, 1, or 2")
    output_dir = output_root / f"anchor_attempt{attempt}" / sequence
    command = _common_command(output_dir=output_dir, gpu=gpu, phase="anchor", num_envs=16)
    command.extend((f"env.config.formal_sequence={sequence}", "env.config.formal_closer_bucket=null"))
    _assert_command(command, num_envs=16, phase="anchor")
    return {
        "kind": "anchor",
        "sequence": sequence,
        "attempt": attempt,
        "gpu": gpu,
        "output_dir": str(output_dir),
        "command": command,
        "shell": shlex.join(command),
        "g3_attempt_cap": 3,
        "rows_per_sequence": 16,
    }


def build_door_command(*, bucket: str, sequence: str, gpu: int = 4, output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    if bucket not in BUCKETS:
        raise ValueError(f"unknown closer bucket {bucket!r}")
    if sequence not in SEQUENCES:
        raise ValueError(f"unknown formal sequence {sequence!r}")
    output_dir = output_root / "door" / bucket.replace("-", "_") / sequence
    command = _common_command(output_dir=output_dir, gpu=gpu, phase="door_positioning", num_envs=16)
    command.extend((f"env.config.formal_sequence={sequence}", f"env.config.formal_closer_bucket={bucket}"))
    _assert_command(command, num_envs=16, phase="door_positioning")
    return {
        "kind": "door_positioning",
        "bucket": bucket,
        "sequence": sequence,
        "gpu": gpu,
        "output_dir": str(output_dir),
        "command": command,
        "shell": shlex.join(command),
        "rows_per_bucket": 16,
    }


def build_g2_command(*, gpu: int = 4, output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    output_dir = output_root / "g2_lattice"
    command = _common_command(output_dir=output_dir, gpu=gpu, phase="anchor", num_envs=36)
    command.extend(
        (
            "env.config.formal_sequence=G2",
            "env.config.formal_closer_bucket=null",
            "env.config.formal_g2_lattice=true",
        )
    )
    _assert_command(command, num_envs=36, phase="anchor")
    return {
        "kind": "G2_lattice",
        "gpu": gpu,
        "output_dir": str(output_dir),
        "command": command,
        "shell": shlex.join(command),
        "representative_states": 36,
    }


def command_matrix(*, gpu: int = 4) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for attempt in range(3):
        records.extend(build_anchor_command(sequence=sequence, attempt=attempt, gpu=gpu) for sequence in SEQUENCES)
    records.extend(
        build_door_command(bucket=bucket, sequence=sequence, gpu=gpu)
        for bucket in BUCKETS
        for sequence in SEQUENCES
    )
    records.append(build_g2_command(gpu=gpu))
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("anchor", "door", "g2", "matrix"), default="matrix")
    parser.add_argument("--sequence", choices=SEQUENCES, default="S1")
    parser.add_argument("--bucket", choices=BUCKETS, default="2.5-5")
    parser.add_argument("--attempt", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.phase == "anchor":
        records = [build_anchor_command(sequence=args.sequence, attempt=args.attempt, gpu=args.gpu)]
    elif args.phase == "door":
        records = [build_door_command(bucket=args.bucket, sequence=args.sequence, gpu=args.gpu)]
    elif args.phase == "g2":
        records = [build_g2_command(gpu=args.gpu)]
    else:
        records = command_matrix(gpu=args.gpu)
    if args.run:
        if len(records) != 1:
            raise ValueError("--run requires one selected command")
        record = records[0]
        result = subprocess.run(record["command"], env=_cuda_env(args.gpu), check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    print(json.dumps(records, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
