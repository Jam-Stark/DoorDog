#!/usr/bin/env python3
"""Plan, launch, and gate the pull-v5.5 adapter ladder."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

try:
    from .pull_v5_5_adapter_gates import (
        DEFAULT_ANCHOR,
        DEFAULT_PLANNER,
        DEFAULT_REHEARSAL,
        DEFAULT_TRAINING,
        GateRejected,
        PLAN_ID,
        require_chain,
        validate_invariant12,
    )
except ImportError:
    from pull_v5_5_adapter_gates import (
        DEFAULT_ANCHOR,
        DEFAULT_PLANNER,
        DEFAULT_REHEARSAL,
        DEFAULT_TRAINING,
        GateRejected,
        PLAN_ID,
        require_chain,
        validate_invariant12,
    )


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ALLOWED_GPUS = (4, 5, 6, 7)
NUM_ENVS = 256
CHECKPOINT_INTERVAL = 250
DEFAULT_TRAIN_OUTPUT = ROOT / "logs_rl/a2_piper_pull_v5_5_adapter"
DEFAULT_GATE_OUTPUT = ROOT / "logs_eval/a2_piper_pull_v5/v5_5_adapter_gate"
DEFAULT_REHEARSAL_OUTPUT = ROOT / "logs_eval/a2_piper_pull_v5/v5_5_adapter_rehearsal"
DEFAULT_ANCHOR_OUTPUT = ROOT / "logs_eval/a2_piper_pull_v5/v5_5_adapter_anchor"
DEFAULT_CHECKPOINT = DEFAULT_TRAIN_OUTPUT / "model_step_000750.pt"


def planner_artifact(*, path: Path = DEFAULT_PLANNER) -> dict[str, Any]:
    """Return the immutable T0 planner decision payload."""

    return {
        "schema": "a2_piper_pull_v5_5_planner_architecture_decision_v1",
        "plan_id": PLAN_ID,
        "status": "PLANNER_ACCEPTED",
        "decision": "ACTIVATE_RESIDUAL_TERMINAL_HOLD_ADAPTER",
        "rung": 2,
        "basis": {
            "v5_4_stage_a": "GO",
            "v5_4_stage_b": "FAIL",
            "terminal_hold_steps": 100,
            "waypoint_tolerance_m": 0.05,
            "yaw_tolerance_rad": 0.15,
        },
        "adapter": {
            "observation_dim": 12,
            "trainable_action_dim": 3,
            "high_level_carrier_dim": 12,
            "frozen_leg_action_dim": 12,
            "active_phase": "terminal_probe",
            "padded_axes_stochastic": False,
        },
        "scientific_denominator_included": False,
        "denominator_scope": "none",
        "fine_tune_deferred": True,
        "fail_closed_chain": ["planner", "training", "rehearsal", "anchor"],
        "immutable_references": [
            "scriptsFORhuman/pull_v5/PULL_V5_4_ROUND_REPORT.md",
            "scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json",
        ],
        "path": str(path.expanduser().resolve()),
    }


def write_planner_artifact(path: Path = DEFAULT_PLANNER) -> Path:
    path = path.expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"refusing to overwrite planner artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(planner_artifact(path=path), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _command(*parts: str) -> str:
    return shlex.join(parts)


def build_t1_training_command(*, output_dir: Path, gpu: int = 4) -> tuple[str, dict[str, str]]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"T1 is restricted to GPU4-7; got GPU{gpu}")
    command = _command(
        str(PYTHON), "-B", "-m", "gr00t.rl.train_agent_trl",
        "+exp=wbmanip/pull_v5_5_adapter_holdtrack",
        "seed=0", f"num_envs={NUM_ENVS}", "headless=true", "use_wandb=false",
        "checkpoint=null", "checkpoint_load_mode=full", "algo.config.load_optimizer=false",
        "algo.config.num_learning_iterations=750", f"algo.config.save_interval={CHECKPOINT_INTERVAL}",
        "algo.trl.num_total_batches=750", "callbacks.model_save.save_frequency=250",
        "algo.config.use_a2_base=true", "env.config.adapter_probe_phase=train",
        f"experiment_dir={output_dir}", "+device=cuda:0",
    )
    return command, {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "WANDB_MODE": "offline",
    }


def build_gate_command(*, training_path: Path = DEFAULT_TRAINING, planner_path: Path = DEFAULT_PLANNER) -> str:
    return _command(
        str(PYTHON), "-B", str(ROOT / "scriptsFORhuman/pull_v5/pull_v5_5_adapter_gates.py"),
        "--level", "training", "--planner", str(planner_path), "--training", str(training_path),
    )


def build_t1_gate_eval_command(
    *, checkpoint: Path, output_dir: Path, gpu: int = 4,
) -> tuple[str, dict[str, str]]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"T1 gate is restricted to GPU4-7; got GPU{gpu}")
    if not checkpoint:
        raise ValueError("T1 gate requires the frozen T1 checkpoint")
    command = _command(
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}", "checkpoint_load_mode=full", "auto_load_latest=false",
        "num_envs=80", "seed=0", "headless=true", "use_wandb=false",
        "+exp=wbmanip/pull_v5_5_adapter_holdtrack_eval",
        "+env.config.adapter_active=true", "+env.config.adapter_probe_phase=training_gate",
        f"eval_output_dir={output_dir}", f"hydra.run.dir={output_dir / 'hydra'}",
        "+device=cuda:0",
    )
    return command, {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "WANDB_MODE": "offline",
    }


def build_t2_rehearsal_commands(*, checkpoint: Path, output_root: Path, gpu: int = 4) -> list[str]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"T2 is restricted to GPU4-7; got GPU{gpu}")
    if not checkpoint:
        raise ValueError("T2 requires the frozen T1 gate checkpoint")
    commands = []
    for yaw_delta in (-2.5, 1.0):
        commands.append(
            _command(
                str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
                f"checkpoint={checkpoint}", "checkpoint_load_mode=full", "auto_load_latest=false",
                "num_envs=8", "seed=0", "headless=true", "use_wandb=false",
                "+exp=wbmanip/pull_v5_5_adapter_holdtrack_eval",
                "+env.config.adapter_active=true", "+env.config.adapter_probe_phase=rehearsal",
                f"+env.config.adapter_rehearsal_yaw_delta_rad={yaw_delta}",
                "+env.config.adapter_rehearsal_xy_delta_m=0.3",
                f"eval_output_dir={output_root / f'cell_{yaw_delta:g}' / 'eval'}",
                f"hydra.run.dir={output_root / f'cell_{yaw_delta:g}' / 'hydra'}",
                "+device=cuda:0",
            )
        )
    return commands


def build_t3_anchor_commands(*, checkpoint: Path, output_root: Path, attempt: int, gpu: int = 4) -> list[str]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"T3 is restricted to GPU4-7; got GPU{gpu}")
    if attempt not in (0, 1, 2):
        raise ValueError("T3 anchor attempt must be 0, 1, or 2")
    return [
        _command(
            str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
            f"checkpoint={checkpoint}", "checkpoint_load_mode=full", "auto_load_latest=false",
            "num_envs=16", "seed=0", "headless=true", "use_wandb=false",
            "+exp=wbmanip/pull_v5_5_adapter_holdtrack_eval",
            "+env.config.adapter_active=true", "+env.config.adapter_probe_phase=anchor",
            f"+env.config.adapter_anchor_attempt={attempt}", f"+env.config.adapter_anchor_sequence={sequence}",
            "+env.config.adapter_waypoint_tolerance_m=0.05", "+env.config.adapter_yaw_tolerance_rad=0.15",
            f"eval_output_dir={output_root / f'attempt{attempt}' / sequence / 'eval'}",
            f"hydra.run.dir={output_root / f'attempt{attempt}' / sequence / 'hydra'}",
            "+device=cuda:0",
        )
        for sequence in ("S1", "S2", "S3", "S4")
    ]


def _run_command(command: str, environment: dict[str, str]) -> None:
    """Launch one approved phase command and propagate a non-zero exit."""

    env = os.environ.copy()
    env.update(environment)
    subprocess.run(shlex.split(command), cwd=ROOT, env=env, check=True)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if path.is_symlink() or not path.is_file():
        raise GateRejected(f"{label} is missing or not a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateRejected(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise GateRejected(f"{label} must be a JSON object")
    return payload


def _write_json_once(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    if path.exists():
        raise GateRejected(f"refusing to overwrite existing phase receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _resolve_checkpoint(value: Path | None) -> Path:
    checkpoint = (value or DEFAULT_CHECKPOINT).expanduser().resolve()
    if checkpoint.is_symlink() or not checkpoint.is_file():
        raise GateRejected(f"frozen T1 checkpoint is missing: {checkpoint}")
    return checkpoint


def _rehearsal_receipt_paths(output_root: Path) -> list[Path]:
    return [output_root / f"cell_{yaw:g}" / "eval" / "REHEARSAL.json" for yaw in (-2.5, 1.0)]


def _aggregate_rehearsal(output_root: Path, target: Path) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for path in _rehearsal_receipt_paths(output_root):
        payload = _read_json_object(path, "rehearsal cell receipt")
        if payload.get("schema") != "a2_piper_pull_v5_5_adapter_rehearsal_v1":
            raise GateRejected(f"rehearsal cell schema mismatch: {path}")
        payload_cells = payload.get("cells")
        if payload.get("status") != "PASS" or not isinstance(payload_cells, list) or len(payload_cells) != 1:
            raise GateRejected(f"rehearsal cell did not PASS: {path}")
        cells.append(dict(payload_cells[0]))
    aggregate = {
        "schema": "a2_piper_pull_v5_5_adapter_rehearsal_v1",
        "plan_id": PLAN_ID,
        "status": "PASS",
        "cells": cells,
    }
    _write_json_once(target, aggregate)
    return aggregate


def _anchor_receipt_paths(output_root: Path, attempt: int) -> list[tuple[str, Path]]:
    return [
        (sequence, output_root / f"attempt{attempt}" / sequence / "eval" / "ANCHOR.json")
        for sequence in ("S1", "S2", "S3", "S4")
    ]


def _aggregate_anchor(output_root: Path, target: Path, attempt: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    admitted: list[str] = []
    for sequence, path in _anchor_receipt_paths(output_root, attempt):
        payload = _read_json_object(path, "anchor sequence receipt")
        if payload.get("schema") != "a2_piper_pull_v5_5_adapter_anchor_v1":
            raise GateRejected(f"anchor sequence schema mismatch: {path}")
        attempts = payload.get("attempts")
        if not isinstance(attempts, list) or len(attempts) != 1 or not isinstance(attempts[0], dict):
            raise GateRejected(f"anchor sequence receipt has invalid attempts: {path}")
        attempt_payload = attempts[0]
        if payload.get("status") == "PASS" and attempt_payload.get("status") == "PASS":
            sequence_rows = attempt_payload.get("rows")
            if not isinstance(sequence_rows, list) or len(sequence_rows) != 16:
                raise GateRejected(f"anchor sequence PASS must contain sixteen rows: {path}")
            admitted.append(sequence)
            if any(not isinstance(row, dict) for row in sequence_rows):
                raise GateRejected(f"anchor sequence rows must be objects: {path}")
            rows.extend(dict(row) for row in sequence_rows)
    aggregate_status = "PASS" if admitted else "FAIL"
    aggregate = {
        "schema": "a2_piper_pull_v5_5_adapter_anchor_v1",
        "plan_id": PLAN_ID,
        "status": aggregate_status,
        "attempts": [{
            "attempt": attempt,
            "status": aggregate_status,
            "admitted_sequences": admitted,
            "rows": rows,
        }],
    }
    _write_json_once(target, aggregate)
    return aggregate


def _validate_invariant12_boundary(path: Path | None, expected_rows: int | None) -> None:
    if path is None:
        return
    payload = _read_json_object(path, "invariant 12 receipt")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise GateRejected("invariant 12 receipt must expose a rows list")
    validate_invariant12(rows, expected_rows=expected_rows)


def _run_training_phase(args: argparse.Namespace) -> dict[str, Any]:
    require_chain("planner", planner_path=args.planner)
    train_output = args.train_output.expanduser().resolve()
    train_command, train_env = build_t1_training_command(output_dir=train_output, gpu=args.gpu)
    _run_command(train_command, train_env)
    checkpoint = _resolve_checkpoint(args.checkpoint)
    gate_output = args.training.expanduser().resolve().parent
    gate_eval_command, gate_eval_env = build_t1_gate_eval_command(
        checkpoint=checkpoint, output_dir=gate_output, gpu=args.gpu
    )
    _run_command(gate_eval_command, gate_eval_env)
    validator = build_gate_command(training_path=args.training, planner_path=args.planner)
    _run_command(validator, {})
    return require_chain("training", planner_path=args.planner, training_path=args.training)


def _run_rehearsal_phase(args: argparse.Namespace) -> dict[str, Any]:
    training = require_chain("training", planner_path=args.planner, training_path=args.training)
    if training.get("training", {}).get("status") != "PASS":
        raise GateRejected("rehearsal launch requires a PASS training gate")
    checkpoint = _resolve_checkpoint(args.checkpoint)
    output_root = args.rehearsal.expanduser().resolve().parent
    for command in build_t2_rehearsal_commands(checkpoint=checkpoint, output_root=output_root, gpu=args.gpu):
        _run_command(command, {
            "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(args.gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1", "WANDB_MODE": "offline",
        })
    _aggregate_rehearsal(output_root, args.rehearsal)
    return require_chain(
        "rehearsal", planner_path=args.planner, training_path=args.training, rehearsal_path=args.rehearsal
    )


def _run_anchor_phase(args: argparse.Namespace) -> dict[str, Any]:
    require_chain(
        "rehearsal", planner_path=args.planner, training_path=args.training, rehearsal_path=args.rehearsal
    )
    checkpoint = _resolve_checkpoint(args.checkpoint)
    output_root = args.anchor.expanduser().resolve().parent
    for command in build_t3_anchor_commands(
        checkpoint=checkpoint, output_root=output_root, attempt=args.attempt, gpu=args.gpu
    ):
        _run_command(command, {
            "PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": str(args.gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0", "HYDRA_FULL_ERROR": "1", "WANDB_MODE": "offline",
        })
    _aggregate_anchor(output_root, args.anchor, args.attempt)
    return require_chain(
        "anchor", planner_path=args.planner, training_path=args.training,
        rehearsal_path=args.rehearsal, anchor_path=args.anchor,
    )


def dry_run_payload(*, planner_path: Path = DEFAULT_PLANNER) -> dict[str, Any]:
    t1, t1_env = build_t1_training_command(
        output_dir=DEFAULT_TRAIN_OUTPUT, gpu=4
    )
    checkpoint = DEFAULT_CHECKPOINT
    gate_eval, gate_eval_env = build_t1_gate_eval_command(
        checkpoint=checkpoint, output_dir=DEFAULT_GATE_OUTPUT, gpu=4
    )
    return {
        "schema": "a2_piper_pull_v5_5_adapter_dry_run_v1",
        "status": "NOT_RUN",
        "plan_id": PLAN_ID,
        "planner_artifact": planner_artifact(path=planner_path),
        "commands": {
            "T1_train": {"command": t1, "env": t1_env},
            "T1_gate_eval": {"command": gate_eval, "env": gate_eval_env},
            "T1_gate": build_gate_command(planner_path=planner_path),
            "T2_rehearsal": build_t2_rehearsal_commands(
                checkpoint=checkpoint,
                output_root=DEFAULT_REHEARSAL_OUTPUT,
                gpu=4,
            ),
            "T3_anchor_attempt0": build_t3_anchor_commands(
                checkpoint=checkpoint,
                output_root=DEFAULT_ANCHOR_OUTPUT,
                attempt=0,
                gpu=4,
            ),
        },
        "launch_policy": "dry-run is read-only; --run is the explicit executable boundary",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print planner and T1-T3 commands")
    parser.add_argument("--run", action="store_true", help="execute the selected phase subprocesses")
    parser.add_argument("--write-planner", action="store_true", help="write the planner artifact")
    parser.add_argument("--planner", type=Path, default=DEFAULT_PLANNER)
    parser.add_argument("--level", choices=("planner", "training", "rehearsal", "anchor"))
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--rehearsal", type=Path, default=DEFAULT_REHEARSAL)
    parser.add_argument("--anchor", type=Path, default=DEFAULT_ANCHOR)
    parser.add_argument("--train-output", type=Path, default=DEFAULT_TRAIN_OUTPUT)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--attempt", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--invariant12", type=Path, default=None)
    parser.add_argument("--invariant12-expected-rows", type=int, default=None)
    args = parser.parse_args()
    try:
        if args.write_planner:
            print(json.dumps({"planner_path": str(write_planner_artifact(args.planner))}, indent=2))
        if args.dry_run:
            print(json.dumps(dry_run_payload(planner_path=args.planner), indent=2, sort_keys=True))
            return 0
        if args.level is None:
            parser.error("runner requires --dry-run, --level, or --run --level")
        if args.run:
            _validate_invariant12_boundary(args.invariant12, args.invariant12_expected_rows)
            if args.level == "planner":
                if not args.planner.exists():
                    write_planner_artifact(args.planner)
                result = require_chain("planner", planner_path=args.planner)
            elif args.level == "training":
                result = _run_training_phase(args)
            elif args.level == "rehearsal":
                result = _run_rehearsal_phase(args)
            else:
                result = _run_anchor_phase(args)
            _validate_invariant12_boundary(args.invariant12, args.invariant12_expected_rows)
        else:
            result = require_chain(
                args.level,
                planner_path=args.planner,
                training_path=args.training,
                rehearsal_path=args.rehearsal,
                anchor_path=args.anchor,
            )
            if args.level == "training" and result.get("training", {}).get("status") == "NOT_RUN":
                print(json.dumps(result, indent=2, sort_keys=True))
                return 3
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (GateRejected, FileExistsError, OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.exit(2, f"REJECTED: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
