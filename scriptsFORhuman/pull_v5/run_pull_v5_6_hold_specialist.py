#!/usr/bin/env python3
"""Plan, launch, and fail-closed gate the v5.6 terminal hold specialist."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
from types import SimpleNamespace
from pathlib import Path
from typing import Any

import torch

from gr00t.rl.trl.modules.pull_v5_6_hold_specialist_actor import (
    FRESH_DOG_STD,
    SPECIALIST_ACTION_DIM,
    SPECIALIST_ACTOR_INPUT_DIM,
    SPECIALIST_LATENT_DIM,
    SPECIALIST_OBS_DIM,
    PullV56HoldSpecialistActor,
    PullV56HoldSpecialistCritic,
)

try:
    from .pull_v5_6_hold_specialist_gates import (
        DEFAULT_ANCHOR,
        DEFAULT_PLANNER,
        DEFAULT_REHEARSAL,
        DEFAULT_STEP0,
        DEFAULT_TRAINING,
        DEFAULT_WARM_START,
        GateRejected,
        ANCHOR_SCHEMA,
        PRELUDE_FAMILIES,
        REHEARSAL_SCHEMA,
        TRAINING_SCHEMA,
        PLAN_ID,
        require_chain,
        training_gate_pass,
    )
except ImportError:
    from pull_v5_6_hold_specialist_gates import (
        DEFAULT_ANCHOR,
        DEFAULT_PLANNER,
        DEFAULT_REHEARSAL,
        DEFAULT_STEP0,
        DEFAULT_TRAINING,
        DEFAULT_WARM_START,
        GateRejected,
        ANCHOR_SCHEMA,
        PRELUDE_FAMILIES,
        REHEARSAL_SCHEMA,
        TRAINING_SCHEMA,
        PLAN_ID,
        require_chain,
        training_gate_pass,
    )


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
ALLOWED_GPUS = (4, 5, 6, 7)
NUM_ENVS = 256
CHECKPOINT_INTERVAL = 250
DEFAULT_TRAIN_OUTPUT = ROOT / "logs_rl/a2_piper_pull_v5_6_hold_specialist"
DEFAULT_GATE_OUTPUT = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_specialist_gate"
DEFAULT_REHEARSAL_OUTPUT = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_specialist_rehearsal"
DEFAULT_ANCHOR_OUTPUT = ROOT / "logs_eval/a2_piper_pull_v5/v5_6_specialist_anchor"
DEFAULT_CHECKPOINT = DEFAULT_TRAIN_OUTPUT / "model_step_000750.pt"
WARM_START_CHECKPOINT = ROOT / "logs_rl/a2_piper_pull_v5_6_hold_specialist/warm_start/model_step_000000.pt"
RAW_DOG_CHECKPOINT = Path("/home/baoquanc/workspace/LMP/logs/manager_dual_rl/lmp_dual_policy/stage1_locomotion_a2_piper/2026-06-05_16-12-09/checkpoints_dog/ac_weights_last.pt")
ORIGINAL_JIT = ROOT / "gr00t/rl/data/policies/A2_Base/policy.pt"


def planner_artifact(*, path: Path = DEFAULT_PLANNER) -> dict[str, Any]:
    return {
        "schema": "a2_piper_pull_v5_6_planner_architecture_decision_v1",
        "plan_id": PLAN_ID,
        "status": "PLANNER_ACCEPTED",
        "decision": "ACTIVATE_TERMINAL_HOLD_SPECIALIST_FINETUNE",
        "rung": 3,
        "ladder_final_rung": True,
        "original_homie_immutable": True,
        "fine_tune_deferred": False,
        "v5_5_reference": "logs_eval/a2_piper_pull_v5/v5_5_adapter_gate/TRAINING_GATE.json",
        "v5_5_round_report": "scriptsFORhuman/pull_v5/PULL_V5_5_ROUND_REPORT.md",
        "specialist": {
            "observation_dim": 1620,
            "adaptation_dims": [256, 128, 25],
            "actor_dims": [512, 256, 128, 12],
            "terminal_only": True,
            "active_phases": ["holdtrack", "terminal_hold", "anchor", "door_positioning"],
            "carrier_dim": 12,
            "frozen_leg_action_dim": 12,
        },
        "warm_start": {
            "raw_checkpoint": str(RAW_DOG_CHECKPOINT),
            "critic": "fresh_incompatible_privileged_25d_semantics",
            "optimizer": "fresh",
            "scheduler": "fresh",
            "std": 1.0,
        },
        "step0_baseline_required": True,
        "scientific_denominator_included": False,
        "denominator_scope": "none",
        "fail_closed_chain": ["planner", "warm", "step0", "training", "rehearsal", "anchor"],
        "immutable_references": [
            "scriptsFORhuman/pull_task/a2_piper_pull_v5_6_worker_prompt_20260817.md",
            "scriptsFORhuman/pull_task/a2_piper_pull_v5_6_hold_specialist_finetune_addendum_20260817.md",
        ],
        "path": str(path.expanduser().resolve()),
    }


def _warm_start_payload(*, checkpoint_path: Path, receipt_path: Path) -> dict[str, Any]:
    checkpoint_ref = checkpoint_path.expanduser()
    if checkpoint_ref.is_symlink() or not checkpoint_ref.is_file():
        raise GateRejected(f"warm-start checkpoint is missing: {checkpoint_path}")
    checkpoint_path = checkpoint_ref.resolve()
    loaded = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    required_keys = {
        "policy_state_dict",
        "value_state_dict",
        "optimizer_state_dict",
        "lr_scheduler_state_dict",
        "state",
        "args",
        "env_state_dict",
    }
    if not isinstance(loaded, dict) or set(loaded) != required_keys:
        raise GateRejected(f"warm-start checkpoint keys do not match gr00t eval-load format: {sorted(loaded) if isinstance(loaded, dict) else type(loaded).__name__}")
    actor = PullV56HoldSpecialistActor(raw_checkpoint_path=str(RAW_DOG_CHECKPOINT), init_noise_std=FRESH_DOG_STD, max_noise_std=1.0)
    critic = PullV56HoldSpecialistCritic()
    actor.load_state_dict(loaded["policy_state_dict"], strict=True)
    critic.load_state_dict(loaded["value_state_dict"], strict=True)
    actor_shapes = {name: list(value.shape) for name, value in loaded["policy_state_dict"].items()}
    critic_shapes = {name: list(value.shape) for name, value in loaded["value_state_dict"].items()}
    return {
        "schema": "a2_piper_pull_v5_6_specialist_warm_start_v1",
        "plan_id": PLAN_ID,
        "status": "PASS",
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_format": {
            "keys": sorted(required_keys),
            "optimizer_state_dict": None,
            "lr_scheduler_state_dict": None,
            "state_global_step": int(loaded["state"].global_step),
            "env_state_dict_keys": sorted(loaded["env_state_dict"]),
        },
        "raw_checkpoint": str(RAW_DOG_CHECKPOINT),
        "original_homie_jit": str(ORIGINAL_JIT),
        "actor_loaded_from_raw_checkpoint": True,
        "source_std_ignored": True,
        "resolved_std": float(actor.fresh_std.mean().item()),
        "critic_init": "fresh_incompatible_privileged_25d_semantics",
        "optimizer_init": "fresh",
        "scheduler_init": "fresh",
        "roundtrip": {
            "actor_state_dict_strict": True,
            "critic_state_dict_strict": True,
            "actor_state_key_count": len(actor_shapes),
            "critic_state_key_count": len(critic_shapes),
            "actor_state_shapes": actor_shapes,
            "critic_state_shapes": critic_shapes,
        },
        "architecture": {
            "obs_dim": 1620,
            "adaptation_hidden_dims": [256, 128],
            "latent_dim": 25,
            "actor_input_dim": 1645,
            "actor_hidden_dims": [512, 256, 128],
            "action_dim": 12,
        },
        "path": str(receipt_path.expanduser().resolve()),
    }


def _write_json_once(path: Path, payload: dict[str, Any]) -> Path:
    path = path.expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return path


def write_planner_artifact(path: Path = DEFAULT_PLANNER) -> Path:
    return _write_json_once(path, planner_artifact(path=path))


def write_warm_start_receipt(path: Path = DEFAULT_WARM_START) -> Path:
    checkpoint_path = WARM_START_CHECKPOINT
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    actor = PullV56HoldSpecialistActor(raw_checkpoint_path=str(RAW_DOG_CHECKPOINT), init_noise_std=FRESH_DOG_STD, max_noise_std=1.0)
    critic = PullV56HoldSpecialistCritic()
    checkpoint = {
        "policy_state_dict": {key: value.detach().cpu() for key, value in actor.state_dict().items()},
        "value_state_dict": {key: value.detach().cpu() for key, value in critic.state_dict().items()},
        "optimizer_state_dict": None,
        "lr_scheduler_state_dict": None,
        "state": SimpleNamespace(global_step=0),
        "args": None,
        "env_state_dict": {},
    }
    torch.save(checkpoint, checkpoint_path)
    payload = _warm_start_payload(checkpoint_path=checkpoint_path, receipt_path=path)
    receipt_path = path.expanduser().resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return receipt_path


def warm_start_receipt(*, path: Path = DEFAULT_WARM_START) -> dict[str, Any]:
    return _warm_start_payload(checkpoint_path=WARM_START_CHECKPOINT, receipt_path=path)


def _command(*parts: str) -> str:
    return shlex.join(parts)


def _cuda_env(gpu: int) -> dict[str, str]:
    if gpu not in ALLOWED_GPUS:
        raise ValueError(f"phase is restricted to GPU4-7; got GPU{gpu}")
    return {
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "HYDRA_FULL_ERROR": "1",
        "WANDB_MODE": "offline",
    }


def build_train_command(*, output_dir: Path, gpu: int = 4) -> tuple[str, dict[str, str]]:
    command = _command(
        str(PYTHON), "-B", "-m", "gr00t.rl.train_agent_trl",
        "+exp=wbmanip/pull_v5_6_hold_specialist", "seed=0", f"num_envs={NUM_ENVS}",
        "headless=true", "use_wandb=false", "checkpoint=null", "checkpoint_load_mode=full",
        "algo.config.load_optimizer=false", "algo.config.num_learning_iterations=750",
        f"algo.config.save_interval={CHECKPOINT_INTERVAL}", "algo.trl.num_total_batches=750",
        "callbacks.model_save.save_frequency=250", "algo.config.use_a2_base=true",
        "env.config.adapter_probe_phase=train", "env.config.hold_specialist_active=true",
        f"env.config.original_homie_checkpoint={ORIGINAL_JIT}",
        f"experiment_dir={output_dir}", "+device=cuda:0",
    )
    return command, _cuda_env(gpu)


def build_step0_command(*, output_dir: Path, gpu: int = 4) -> tuple[str, dict[str, str]]:
    command = _command(
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl",
        f"checkpoint={WARM_START_CHECKPOINT}", "checkpoint_load_mode=full", "auto_load_latest=false",
        "num_envs=80", "seed=0", "headless=true", "use_wandb=false",
        "+exp=wbmanip/pull_v5_6_hold_specialist_eval", "env.config.adapter_active=true",
        "env.config.adapter_probe_phase=step0", "env.config.hold_specialist_active=false",
        "env.config.original_homie_checkpoint=" + str(ORIGINAL_JIT),
        "env.config.specialist_checkpoint=null", f"eval_output_dir={output_dir}",
        f"hydra.run.dir={output_dir / 'hydra'}", "+device=cuda:0",
    )
    return command, _cuda_env(gpu)


def build_training_gate_command(*, checkpoint: Path, output_dir: Path, gpu: int = 4) -> tuple[str, dict[str, str]]:
    if not checkpoint:
        raise ValueError("training gate requires the frozen specialist checkpoint")
    command = _command(
        str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl", f"checkpoint={checkpoint}",
        "checkpoint_load_mode=full", "auto_load_latest=false", "num_envs=80", "seed=0",
        "headless=true", "use_wandb=false", "+exp=wbmanip/pull_v5_6_hold_specialist_eval",
        "env.config.adapter_active=true", "env.config.adapter_probe_phase=training_gate",
        "env.config.hold_specialist_active=true", f"env.config.specialist_checkpoint={checkpoint}",
        f"env.config.original_homie_checkpoint={ORIGINAL_JIT}",
        f"eval_output_dir={output_dir}",
        f"hydra.run.dir={output_dir / 'hydra'}", "+device=cuda:0",
    )
    return command, _cuda_env(gpu)


def build_rehearsal_commands(*, checkpoint: Path, output_root: Path, gpu: int = 4) -> list[tuple[str, dict[str, str]]]:
    if not checkpoint:
        raise ValueError("rehearsal requires the frozen specialist checkpoint")
    commands: list[tuple[str, dict[str, str]]] = []
    for yaw_delta in (-2.5, 1.0):
        cell = output_root / f"cell_{yaw_delta:g}"
        command = _command(
            str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl", f"checkpoint={checkpoint}",
            "checkpoint_load_mode=full", "auto_load_latest=false", "num_envs=8", "seed=0",
            "headless=true", "use_wandb=false", "+exp=wbmanip/pull_v5_6_hold_specialist_eval",
            "env.config.adapter_active=true", "env.config.adapter_probe_phase=rehearsal",
            "env.config.hold_specialist_active=true", f"env.config.specialist_checkpoint={checkpoint}",
            f"env.config.original_homie_checkpoint={ORIGINAL_JIT}",
            f"env.config.adapter_rehearsal_yaw_delta_rad={yaw_delta}",
            "env.config.adapter_rehearsal_xy_delta_m=0.3", f"eval_output_dir={cell / 'eval'}",
            f"hydra.run.dir={cell / 'hydra'}", "+device=cuda:0",
        )
        commands.append((command, _cuda_env(gpu)))
    return commands


def build_anchor_commands(*, checkpoint: Path, output_root: Path, attempt: int, gpu: int = 4) -> list[tuple[str, dict[str, str]]]:
    if attempt not in (0, 1, 2):
        raise ValueError("anchor attempt must be 0, 1, or 2")
    if not checkpoint:
        raise ValueError("anchor requires the frozen specialist checkpoint")
    commands: list[tuple[str, dict[str, str]]] = []
    for sequence in ("S1", "S2", "S3", "S4"):
        target = output_root / f"attempt{attempt}" / sequence
        command = _command(
            str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl", f"checkpoint={checkpoint}",
            "checkpoint_load_mode=full", "auto_load_latest=false", "num_envs=16", "seed=0",
            "headless=true", "use_wandb=false", "+exp=wbmanip/pull_v5_6_hold_specialist_eval",
            "env.config.adapter_active=true", "env.config.adapter_probe_phase=anchor",
            "env.config.hold_specialist_active=true", f"env.config.specialist_checkpoint={checkpoint}",
            f"env.config.original_homie_checkpoint={ORIGINAL_JIT}",
            f"env.config.adapter_anchor_attempt={attempt}",
            f"env.config.adapter_anchor_sequence={sequence}", "env.config.adapter_waypoint_tolerance_m=0.05",
            "env.config.adapter_yaw_tolerance_rad=0.15", f"eval_output_dir={target / 'eval'}",
            f"hydra.run.dir={target / 'hydra'}", "+device=cuda:0",
        )
        commands.append((command, _cuda_env(gpu)))
    return commands


def formal_door_side_wrapper(*, checkpoint: Path) -> None:
    """Keep the formal door-side T3 wrapper explicit until T0 passes."""
    raise GateRejected(
        f"formal door-side T3 wrapper is required after the v5.6 anchor gate; T0 does not admit {checkpoint}"
    )


def _run(command: str, environment: dict[str, str]) -> None:
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


def _checkpoint_step(checkpoint: Path) -> int:
    match = re.search(r"model_step_(\d+)\.pt$", checkpoint.name)
    if match is None:
        raise GateRejected(f"checkpoint filename must encode model_step_NNN: {checkpoint}")
    return int(match.group(1))


def _discover_checkpoints(train_output: Path, explicit: Path | None) -> list[Path]:
    candidates = {
        path.expanduser().resolve()
        for path in train_output.expanduser().resolve().glob("model_step_*.pt")
        if path.is_file() and not path.is_symlink()
    }
    if explicit is not None:
        checkpoint = explicit.expanduser().resolve()
        if checkpoint.is_symlink() or not checkpoint.is_file():
            raise GateRejected(f"explicit specialist checkpoint is missing: {checkpoint}")
        candidates.add(checkpoint)
    if not candidates:
        raise GateRejected(f"no versioned specialist checkpoints found under {train_output}")
    return sorted(candidates, key=lambda path: (_checkpoint_step(path), str(path)))


def _aggregate_training_gate(receipts: list[dict[str, Any]], target: Path) -> dict[str, Any]:
    if not receipts:
        raise GateRejected("training gate aggregation requires at least one checkpoint receipt")
    entries: list[dict[str, Any]] = []
    for index, payload in enumerate(receipts):
        if payload.get("schema") != TRAINING_SCHEMA or payload.get("plan_id") != PLAN_ID:
            raise GateRejected(f"training checkpoint receipt {index} schema/plan mismatch")
        checkpoint = payload.get("specialist_checkpoint")
        step = payload.get("specialist_checkpoint_step")
        if not isinstance(checkpoint, str) or not checkpoint:
            raise GateRejected(f"training checkpoint receipt {index} lacks specialist checkpoint")
        if isinstance(step, bool) or not isinstance(step, int) or step < 0:
            raise GateRejected(f"training checkpoint receipt {index} lacks specialist checkpoint step")
        rows = payload.get("rows")
        if not isinstance(rows, list) or len(rows) != 80:
            raise GateRejected(f"training checkpoint receipt {index} must expose 80 rows")
        done_counts = payload.get("family_done_counts")
        is_pass = payload.get("status") == "PASS" and isinstance(done_counts, dict) and set(done_counts) == set(PRELUDE_FAMILIES) and training_gate_pass(done_counts)
        entries.append({
            "schema": TRAINING_SCHEMA,
            "plan_id": PLAN_ID,
            "status": "PASS" if is_pass else "FAIL",
            "checkpoint": checkpoint,
            "checkpoint_step": step,
            "path": checkpoint,
            "step": step,
            "specialist_checkpoint": checkpoint,
            "specialist_checkpoint_step": step,
            "rows": rows,
            "family_row_counts": payload.get("family_row_counts"),
            "family_done_counts": done_counts,
            "training_gate_registered_full": payload.get("training_gate_registered_full") is True,
            "full_source": payload.get("full_source") is True,
            "invariant12_prime": payload.get("invariant12_prime"),
            "original_homie_checkpoint": payload.get("original_homie_checkpoint"),
        })
    passing = [entry for entry in entries if entry["status"] == "PASS"]
    selected = max(passing, key=lambda entry: entry["checkpoint_step"]) if passing else None
    aggregate = {
        "schema": TRAINING_SCHEMA,
        "plan_id": PLAN_ID,
        "status": "PASS" if selected is not None else "FAIL",
        "checkpoints": entries,
        "selected_checkpoint": selected["checkpoint"] if selected else None,
        "selected_checkpoint_step": selected["checkpoint_step"] if selected else None,
        "rows": selected["rows"] if selected else [],
        "family_row_counts": selected["family_row_counts"] if selected else {family: 0 for family in PRELUDE_FAMILIES},
        "family_done_counts": selected["family_done_counts"] if selected else {family: 0 for family in PRELUDE_FAMILIES},
        "training_gate_registered_full": selected["training_gate_registered_full"] if selected else False,
        "full_source": selected["full_source"] if selected else False,
        "invariant12_prime": selected["invariant12_prime"] if selected else {"status": "FAIL", "checked_rows": 0},
        "original_homie_checkpoint": selected["original_homie_checkpoint"] if selected else None,
    }
    _write_json_once(target, aggregate)
    return aggregate


def _aggregate_rehearsal(output_root: Path, target: Path) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    for yaw_delta in (-2.5, 1.0):
        path = output_root.expanduser().resolve() / f"cell_{yaw_delta:g}" / "eval" / "REHEARSAL.json"
        payload = _read_json_object(path, "rehearsal cell receipt")
        if payload.get("schema") != "a2_piper_pull_v5_6_specialist_rehearsal_cell_v1" or payload.get("plan_id") != PLAN_ID:
            raise GateRejected(f"rehearsal cell schema/plan mismatch: {path}")
        rows = payload.get("rows")
        if not isinstance(rows, list) or len(rows) != 8:
            raise GateRejected(f"rehearsal cell must expose eight rows: {path}")
        target_payload = payload.get("rehearsal_target")
        if not isinstance(target_payload, dict):
            raise GateRejected(f"rehearsal cell lacks target provenance: {path}")
        cells.append({
            "yaw_delta_rad": target_payload.get("yaw_delta_rad"),
            "xy_delta_m": target_payload.get("xy_delta_m"),
            "status": payload.get("status"),
            "rows": rows,
            "specialist_checkpoint": payload.get("specialist_checkpoint"),
            "specialist_checkpoint_step": payload.get("specialist_checkpoint_step"),
        })
        all_rows.extend(dict(row) for row in rows)
    status = "PASS" if all(cell["status"] == "PASS" for cell in cells) else "FAIL"
    aggregate = {
        "schema": REHEARSAL_SCHEMA,
        "plan_id": PLAN_ID,
        "status": status,
        "cells": cells,
        "rows": all_rows,
        "invariant12_prime": {"status": "PASS" if status == "PASS" else "FAIL", "phase": "rehearsal", "checked_rows": len(all_rows)},
    }
    _write_json_once(target, aggregate)
    return aggregate


def _aggregate_anchor(output_root: Path, target: Path, attempt: int) -> dict[str, Any]:
    admitted: list[str] = []
    rows: list[dict[str, Any]] = []
    for sequence in ("S1", "S2", "S3", "S4"):
        path = output_root.expanduser().resolve() / f"attempt{attempt}" / sequence / "eval" / "ANCHOR.json"
        payload = _read_json_object(path, "anchor sequence receipt")
        if payload.get("schema") != "a2_piper_pull_v5_6_specialist_anchor_cell_v1" or payload.get("plan_id") != PLAN_ID:
            raise GateRejected(f"anchor sequence schema/plan mismatch: {path}")
        sequence_rows = payload.get("rows")
        if not isinstance(sequence_rows, list) or len(sequence_rows) != 16:
            raise GateRejected(f"anchor sequence must expose sixteen rows: {path}")
        if payload.get("anchor_sequence") != sequence:
            raise GateRejected(f"anchor sequence provenance mismatch: {path}")
        if payload.get("status") == "PASS":
            admitted.append(sequence)
            rows.extend(dict(row) for row in sequence_rows)
    status = "PASS" if admitted else "FAIL"
    aggregate = {
        "schema": ANCHOR_SCHEMA,
        "plan_id": PLAN_ID,
        "status": status,
        "attempts": [{
            "attempt": attempt,
            "status": status,
            "admitted_sequences": admitted,
            "rows": rows,
        }],
        "invariant12_prime": {"status": "PASS" if status == "PASS" else "FAIL", "phase": "anchor", "checked_rows": len(rows)},
    }
    _write_json_once(target, aggregate)
    return aggregate


def dry_run_payload(*, planner_path: Path = DEFAULT_PLANNER) -> dict[str, Any]:
    train, train_env = build_train_command(output_dir=DEFAULT_TRAIN_OUTPUT, gpu=4)
    step0, step0_env = build_step0_command(output_dir=DEFAULT_STEP0.parent, gpu=4)
    gate, gate_env = build_training_gate_command(checkpoint=DEFAULT_CHECKPOINT, output_dir=DEFAULT_GATE_OUTPUT, gpu=4)
    rehearsal = build_rehearsal_commands(checkpoint=DEFAULT_CHECKPOINT, output_root=DEFAULT_REHEARSAL_OUTPUT, gpu=4)
    anchor = build_anchor_commands(checkpoint=DEFAULT_CHECKPOINT, output_root=DEFAULT_ANCHOR_OUTPUT, attempt=0, gpu=4)
    for command in (train, step0, gate, *(item[0] for item in rehearsal), *(item[0] for item in anchor)):
        if str(PYTHON) not in command or "+device=cuda:0" not in command:
            raise AssertionError("every launch command must use the IsaacLab Python and explicit cuda:0")
    return {
        "schema": "a2_piper_pull_v5_6_hold_specialist_dry_run_v1",
        "status": "NOT_RUN",
        "plan_id": PLAN_ID,
        "planner_artifact": planner_artifact(path=planner_path),
        "warm_start_receipt": warm_start_receipt(path=DEFAULT_WARM_START),
        "commands": {
            "train": {"command": train, "env": train_env},
            "step0": {"command": step0, "env": step0_env},
            "training_gate": {"command": gate, "env": gate_env},
            "rehearsal": [{"command": command, "env": env} for command, env in rehearsal],
            "anchor_attempt0": [{"command": command, "env": env} for command, env in anchor],
        },
        "launch_policy": "dry-run is read-only; --run is the explicit executable boundary",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--write-planner", action="store_true")
    parser.add_argument("--write-warm-start", action="store_true")
    parser.add_argument("--planner", type=Path, default=DEFAULT_PLANNER)
    parser.add_argument("--warm-start", type=Path, default=DEFAULT_WARM_START)
    parser.add_argument("--step0", type=Path, default=DEFAULT_STEP0)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--rehearsal", type=Path, default=DEFAULT_REHEARSAL)
    parser.add_argument("--anchor", type=Path, default=DEFAULT_ANCHOR)
    parser.add_argument("--train-output", type=Path, default=DEFAULT_TRAIN_OUTPUT)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--gpu", type=int, choices=ALLOWED_GPUS, default=4)
    parser.add_argument("--attempt", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--level", choices=("planner", "warm", "step0", "training", "rehearsal", "anchor"))
    args = parser.parse_args()
    try:
        if args.write_planner:
            print(json.dumps({"planner_path": str(write_planner_artifact(args.planner))}, indent=2))
        if args.write_warm_start:
            print(json.dumps({"warm_start_path": str(write_warm_start_receipt(args.warm_start))}, indent=2))
        if args.dry_run:
            print(json.dumps(dry_run_payload(planner_path=args.planner), indent=2, sort_keys=True))
            return 0
        if args.level is None:
            if args.write_planner or args.write_warm_start:
                return 0
            parser.error("runner requires --dry-run, --level, or --run --level")
        if args.run:
            if args.level == "planner":
                if not args.planner.exists():
                    write_planner_artifact(args.planner)
                write_warm_start_receipt(args.warm_start)
                result = require_chain("planner", planner_path=args.planner)
            elif args.level == "warm":
                result = require_chain("warm", planner_path=args.planner, warm_start_path=args.warm_start)
            elif args.level == "step0":
                require_chain("warm", planner_path=args.planner, warm_start_path=args.warm_start)
                command, env = build_step0_command(output_dir=args.step0.expanduser().resolve().parent, gpu=args.gpu)
                _run(command, env)
                result = require_chain("step0", planner_path=args.planner, warm_start_path=args.warm_start, step0_path=args.step0)
            elif args.level == "training":
                require_chain("step0", planner_path=args.planner, warm_start_path=args.warm_start, step0_path=args.step0)
                command, env = build_train_command(output_dir=args.train_output, gpu=args.gpu)
                _run(command, env)
                checkpoints = _discover_checkpoints(args.train_output, args.checkpoint)
                receipts: list[dict[str, Any]] = []
                for checkpoint in checkpoints:
                    step = _checkpoint_step(checkpoint)
                    gate_output = DEFAULT_GATE_OUTPUT / f"step{step}"
                    gate_command, gate_env = build_training_gate_command(checkpoint=checkpoint, output_dir=gate_output, gpu=args.gpu)
                    _run(gate_command, gate_env)
                    receipts.append(_read_json_object(gate_output / "TRAINING_GATE.json", "training checkpoint gate receipt"))
                _aggregate_training_gate(receipts, args.training)
                result = require_chain("training", planner_path=args.planner, warm_start_path=args.warm_start, step0_path=args.step0, training_path=args.training)
            elif args.level == "rehearsal":
                training_result = require_chain("training", planner_path=args.planner, warm_start_path=args.warm_start, step0_path=args.step0, training_path=args.training)
                checkpoint = (args.checkpoint or Path(training_result["training"]["selected_checkpoint"])).expanduser().resolve()
                for command, env in build_rehearsal_commands(checkpoint=checkpoint, output_root=DEFAULT_REHEARSAL_OUTPUT, gpu=args.gpu):
                    _run(command, env)
                _aggregate_rehearsal(DEFAULT_REHEARSAL_OUTPUT, args.rehearsal)
                result = require_chain("rehearsal", planner_path=args.planner, warm_start_path=args.warm_start, training_path=args.training, rehearsal_path=args.rehearsal)
            else:
                rehearsal_result = require_chain("rehearsal", planner_path=args.planner, warm_start_path=args.warm_start, training_path=args.training, rehearsal_path=args.rehearsal)
                training_result = rehearsal_result["training"]
                checkpoint = (args.checkpoint or Path(training_result["selected_checkpoint"])).expanduser().resolve()
                for command, env in build_anchor_commands(checkpoint=checkpoint, output_root=DEFAULT_ANCHOR_OUTPUT, attempt=args.attempt, gpu=args.gpu):
                    _run(command, env)
                _aggregate_anchor(DEFAULT_ANCHOR_OUTPUT, args.anchor, args.attempt)
                result = require_chain("anchor", planner_path=args.planner, warm_start_path=args.warm_start, training_path=args.training, rehearsal_path=args.rehearsal, anchor_path=args.anchor)
        else:
            result = require_chain(args.level, planner_path=args.planner, warm_start_path=args.warm_start, step0_path=args.step0, training_path=args.training, rehearsal_path=args.rehearsal, anchor_path=args.anchor)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (GateRejected, FileExistsError, OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.exit(2, f"REJECTED: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
