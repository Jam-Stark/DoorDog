"""CPU-only registration and adjudication for the r12 marginal-E1 pilot.

This module deliberately stops at additive evidence contracts.  It generates
the four exact training commands but never launches IsaacLab, CUDA, or W&B.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import p2_force_boundary as p2
except ImportError:  # direct script invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v24 import p2_force_boundary as p2


PILOT_SCHEMA = "a2_piper_v24_r12_f3_marginal_e1_pilot_v1"
PILOT_ADJUDICATION_SCHEMA = "a2_piper_v24_r12_f3_marginal_e1_adjudication_v1"
PILOT_FINAL_SCHEMA = "a2_piper_v24_r12_post_pilot_finalization_v1"
PILOT_CONFIG = "gr00t/rl/config/ablation/wbmanip/base_v24_r1_f3_marginal_e1_pilot.yaml"
PILOT_CELLS = (
    {"cell": "DF1_FULL_SEED0", "posture": "FULL", "seed": 0},
    {"cell": "DF1_FULL_SEED1", "posture": "FULL", "seed": 1},
    {"cell": "DF1_RP0_SEED0", "posture": "RP0", "seed": 0},
    {"cell": "DF1_RP0_SEED1", "posture": "RP0", "seed": 1},
)
PILOT_BUCKETS = ("F00", "F05", "F10")
PILOT_SCHEDULE = (
    {"step_fraction": 0.0, "F00": 100, "F05": 0, "F10": 0},
    {"step_fraction": 0.2, "F00": 60, "F05": 40, "F10": 0},
    {"step_fraction": 0.5, "F00": 30, "F05": 60, "F10": 10},
)
PILOT_REQUIRED_WINDOWS = 8
PILOT_BATCHES = 500
PILOT_SAVE_FREQUENCY = 250
PILOT_NUM_ENVS = 4096
PILOT_RESCUE_CAP_NM = 25.0
PILOT_CONFIRMED_E2_SHARE = 0.0
PILOT_ARTIFACTS = p2.PILOT_ARTIFACTS


def _hydra_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_hydra_value(item) for item in value) + "]"
    return str(value)


def _root(root: str | Path = p2.PILOT_ARTIFACT_ROOT) -> Path:
    target = Path(root)
    if not target.is_absolute():
        target = p2.REPO_ROOT / target
    target = target.resolve()
    expected = (p2.REPO_ROOT / p2.PILOT_ARTIFACT_ROOT).resolve()
    if target != expected:
        raise ValueError(f"r12 pilot accepts only the canonical artifact root: {expected}")
    return target


def _write_json(root: Path, relative: str, payload: Mapping[str, Any]) -> Path:
    relative_path = Path(relative)
    if root.name == "marginal_e1" and relative_path.parts[:1] == ("marginal_e1",):
        relative_path = Path(*relative_path.parts[1:])
    target = (root / relative_path).resolve()
    if root not in target.parents:
        raise ValueError(f"pilot artifact escapes its canonical root: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"pilot artifact is append-only and already exists: {target}") from exc
    return target


def _path_reference(relative: str) -> dict[str, str]:
    target = (p2.REPO_ROOT / relative).resolve()
    return {"relative": p2.rel_path(target), "absolute": str(target)}


def _rule16(vitals_receipt: Mapping[str, Any], *, require_source_files: bool = True) -> dict[str, Any]:
    p2._require_completed_vital_receipt(vitals_receipt, require_source_files=require_source_files)
    admission = vitals_receipt.get("rule16_admission")
    p2._validate_rule16_admission(admission, require_source_files=require_source_files)
    return dict(admission)


def build_registration(
    *,
    vitals_receipt: Mapping[str, Any],
    gradient_admission: Mapping[str, Any] | None = None,
    require_source_files: bool = True,
) -> dict[str, Any]:
    rule16 = _rule16(vitals_receipt, require_source_files=require_source_files)
    gradient = dict(p2.GRADIENT_ADMISSION if gradient_admission is None else gradient_admission)
    if gradient != p2.GRADIENT_ADMISSION:
        raise ValueError("r12 pilot requires the canonical gradient admission")
    return {
        "schema": PILOT_SCHEMA,
        "status": p2.PILOT_REQUIRED_STATUS,
        "registration_id": p2.PILOT_REGISTRATION_ID,
        "owner_decision_artifact": dict(vitals_receipt["owner_decision_artifact"]),
        "vitals_receipt_artifact": dict(vitals_receipt["rule16_admission"]["vitals_receipt_artifact"]),
        "rule16_admission": rule16,
        "gradient_admission": gradient,
        "checkpoint": p2.CHECKPOINT,
        "checkpoint_load_mode": "selected_policy_only",
        "warm_start": "v23_G7_step1500_policy_only_warm_head_reset",
        "cells": [dict(cell) for cell in PILOT_CELLS],
        "num_envs": PILOT_NUM_ENVS,
        "batches": PILOT_BATCHES,
        "save_frequency": PILOT_SAVE_FREQUENCY,
        "schedule": [dict(item) for item in PILOT_SCHEDULE],
        "candidate_buckets": list(PILOT_BUCKETS),
        "rescue_cap_nm": PILOT_RESCUE_CAP_NM,
        "confirmed_e2_share": PILOT_CONFIRMED_E2_SHARE,
        "rp0_contract": {
            "distribution_level": True,
            "mask_indices": [3, 4],
            "neutral_value": 0.0,
            "post_sample_clamp": False,
            "source": "gr00t.rl.trl.modules.actor_critic_modules.Actor",
        },
    }


def write_registration(
    *,
    vitals_receipt: Mapping[str, Any],
    gradient_admission: Mapping[str, Any] | None = None,
    root: str | Path = p2.PILOT_ARTIFACT_ROOT,
) -> Path:
    payload = build_registration(vitals_receipt=vitals_receipt, gradient_admission=gradient_admission)
    return _write_json(_root(root), PILOT_ARTIFACTS[0], payload)


def _cell_command(
    cell: Mapping[str, Any],
    *,
    registration: Mapping[str, Any],
    num_envs: int = PILOT_NUM_ENVS,
    batches: int = PILOT_BATCHES,
    save_frequency: int = PILOT_SAVE_FREQUENCY,
    label: str = "production",
) -> dict[str, Any]:
    posture = cell["posture"]
    seed = int(cell["seed"])
    rp0 = posture == "RP0"
    experiment = f"{registration['registration_id']}_{cell['cell']}"
    output_dir = f"logs_rl/a2_piper_full_stage_a2_base/v24/r12/f3_marginal_e1/{label}/{cell['cell']}"
    command = [
        "/home/baoquanc/anaconda3/envs/isaaclab/bin/python",
        "-m",
        "gr00t.rl.train_agent_trl",
        "+exp=wbmanip/door_open_a2_base_lstm",
        "+ablation=wbmanip/base_v24_r1_f3_marginal_e1_pilot",
        "project_name=a2_piper_full_stage_a2_base",
        f"experiment_name={experiment}",
        f"experiment_dir={output_dir}",
        f"checkpoint={p2.CHECKPOINT}",
        "checkpoint_load_mode=policy_only",
        "auto_load_latest=false",
        "max_retries=0",
        "headless=true",
        "use_wandb=false",
        f"num_envs={num_envs}",
        "num_gpus=1",
        "multi_gpu=false",
        f"seed={seed}",
        f"++algo.trl.num_total_batches={batches}",
        "++algo.trl.report_to=none",
        f"++callbacks.model_save.save_frequency={save_frequency}",
        f"++algo.config.rp0_enabled={'true' if rp0 else 'false'}",
        "++algo.config.rp0_mask_indices=[3,4]",
        "++algo.config.rp0_neutral_value=0.0",
        f"++env.config.a2_v23_rp0_enabled={'true' if rp0 else 'false'}",
        "++env.config.a2_v23_rp0_mask_indices=[3,4]",
        "++env.config.a2_v23_rp0_neutral_value=0.0",
        "++env.config.a2_v23_d1_variant=normal",
        "++env.config.a2_v23_d1_sampler_enabled=false",
        "++env.config.a2_v23_d1_confirmed_e2_enabled=false",
        "++env.config.a2_v24_f3_marginal_e1_enabled=true",
        f"++env.config.a2_v24_f3_marginal_e1_training_seed={seed}",
        f"++env.config.a2_v24_f3_marginal_e1_bucket_seed={24030 + seed}",
        f"++env.config.a2_v24_f3_marginal_e1_total_batches={batches}",
        f"++env.config.a2_v24_f3_marginal_e1_num_envs={num_envs}",
        "++env.config.a2_v24_f3_marginal_e1_confirmed_e2_enabled=false",
        "++v23_formal_launch=true",
        "++v23_initialization=warm_head_reset",
        "++v23_door_regime=D1",
        f"++v23_posture_mode={posture}",
        "++v24_f3_door_regime=DF1",
        "++v24_f3_candidate_buckets=[F00,F05,F10]",
        "++v24_f3_rescue_cap_nm=25.0",
        "++v24_f3_confirmed_e2_share=0.0",
    ]
    return {
        "cell": cell["cell"],
        "posture": posture,
        "seed": seed,
        "label": label,
        "num_envs": num_envs,
        "batches": batches,
        "save_frequency": save_frequency,
        "candidate_buckets": list(PILOT_BUCKETS),
        "command": command,
        "environment": {
            "CUDA_VISIBLE_DEVICES": "0",
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "WANDB_MODE": "disabled",
        },
        "rp0_distribution_contract": {
            "enabled": rp0,
            "indices": [3, 4],
            "neutral_value": 0.0,
            "post_sample_clamp": False,
            "source": "gr00t.rl.trl.modules.actor_critic_modules.Actor",
        },
    }


def build_pilot_commands(*, registration: Mapping[str, Any], require_source_files: bool = True) -> dict[str, Any]:
    if registration.get("schema") != PILOT_SCHEMA or registration.get("registration_id") != p2.PILOT_REGISTRATION_ID:
        raise ValueError("r12 pilot registration is invalid")
    _rule16_from_registration(registration, require_source_files=require_source_files)
    rows = [_cell_command(cell, registration=registration) for cell in PILOT_CELLS]
    smoke_cells = [PILOT_CELLS[0], PILOT_CELLS[2]]
    smoke_rows = [
        _cell_command(
            cell,
            registration=registration,
            num_envs=64,
            batches=10,
            save_frequency=10,
            label="smoke",
        )
        for cell in smoke_cells
    ]
    return {
        "schema": "a2_piper_v24_r12_f3_marginal_e1_commands_v1",
        "status": "REGISTERED_NOT_EXECUTED",
        "registration_id": registration["registration_id"],
        "commands": rows,
        "training_smoke": smoke_rows,
        "num_envs": PILOT_NUM_ENVS,
        "batches": PILOT_BATCHES,
        "save_frequency": PILOT_SAVE_FREQUENCY,
        "seeds": [0, 1],
        "postures": ["FULL", "RP0"],
        "gpu": {"physical": "0", "logical": "cuda:0"},
        "execution": "NOT_RUN_BY_CPU_PLAN",
    }


def write_commands(
    *,
    registration: Mapping[str, Any],
    root: str | Path = p2.PILOT_ARTIFACT_ROOT,
) -> Path:
    return _write_json(_root(root), PILOT_ARTIFACTS[1], build_pilot_commands(registration=registration))


def _write_jsonl(root: Path, relative: str, rows: Sequence[Mapping[str, Any]]) -> Path:
    relative_path = Path(relative)
    if root.name == "marginal_e1" and relative_path.parts[:1] == ("marginal_e1",):
        relative_path = Path(*relative_path.parts[1:])
    target = (root / relative_path).resolve()
    if root not in target.parents:
        raise ValueError(f"pilot artifact escapes its canonical root: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"pilot artifact is append-only and already exists: {target}") from exc
    return target


def write_population_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    registration: Mapping[str, Any],
    root: str | Path = p2.PILOT_ARTIFACT_ROOT,
    require_source_files: bool = True,
) -> Path:
    summary = validate_pilot_rows(rows, registration=registration, require_source_files=require_source_files)
    return _write_jsonl(_root(root), PILOT_ARTIFACTS[4], summary["rows"])


def build_post_training_eval_commands(
    *,
    registration: Mapping[str, Any],
    checkpoints: Mapping[str, str | Path],
    output_root: str = "logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/post_training_eval",
    require_source_files: bool = True,
) -> dict[str, Any]:
    _rule16_from_registration(registration, require_source_files=require_source_files)
    expected_cells = {cell["cell"] for cell in PILOT_CELLS}
    if set(checkpoints) != expected_cells:
        raise ValueError("post-training eval checkpoints must cover exactly the four registered pilot cells")
    checkpoint_values = [str(checkpoints[cell["cell"]]) for cell in PILOT_CELLS]
    if len(set(checkpoint_values)) != len(checkpoint_values):
        raise ValueError("post-training eval checkpoints must be unique per pilot cell")
    output_root = output_root.rstrip("/")
    if not output_root.startswith(f"{p2.PILOT_ARTIFACT_ROOT}/"):
        raise ValueError("post-training eval output root must remain under the canonical marginal-E1 artifact root")
    overlay = p2._read_overlay(p2.CONFIG_PATH)
    overlay_env = overlay.get("env", {}).get("config") if isinstance(overlay.get("env"), Mapping) else None
    if not isinstance(overlay_env, Mapping):
        raise ValueError("v24 P2 canonical overlay must contain env.config")
    runtime_base = {
        key: value
        for key, value in overlay_env.items()
        if key.startswith("a2_v24_force_boundary_")
    }
    commands: list[dict[str, Any]] = []
    for cell in PILOT_CELLS:
        checkpoint = str(checkpoints[cell["cell"]])
        if not checkpoint.endswith("model_step_000500.pt"):
            raise ValueError(f"{cell['cell']} checkpoint must be the unique final model_step_000500.pt")
        rp0 = cell["posture"] == "RP0"
        mode = "BOUNDARY_RP0" if rp0 else "BOUNDARY_FULL"
        output_dir = f"{output_root.rstrip('/')}/{cell['cell']}"
        profile_params = p2.FRICTION_PROFILES["F05"]
        runtime_env = dict(runtime_base)
        runtime_env.update(
            {
                "a2_v20_R2_evidence_enabled": False,
                "a2_v23_d1_sampler_enabled": False,
                "a2_v24_force_boundary_enabled": True,
                "a2_v24_force_boundary_mode": "P2_TELEMETRY",
                "a2_v24_force_boundary_friction_profile": "F05",
                "a2_v24_force_boundary_runtime_mode": mode,
                "a2_v24_force_boundary_active_cap_nm": 20.0,
                "a2_v24_force_boundary_seed": cell["seed"],
                "a2_v24_force_boundary_scenario_ids": list(p2.SCENARIO_IDS),
                "a2_v24_force_boundary_continuity_id": "F3_POST_TRAIN_EVAL",
                "a2_v24_force_boundary_runtime_export_path": f"{output_dir}/P2_RUNTIME_ROWS.jsonl",
                "a2_v24_force_boundary_static_friction_nm": profile_params["static_effort_nm"],
                "a2_v24_force_boundary_dynamic_friction_nm": profile_params["dynamic_effort_nm"],
                "a2_v24_force_boundary_viscous_friction_nm_s_per_rad": profile_params["viscous_coefficient_nm_s_per_rad"],
                "a2_v24_f3_marginal_e1_evidence_enabled": True,
                "a2_v24_f3_marginal_e1_enabled": False,
                "a2_v24_f3_marginal_e1_condition": "R12_PILOT_CELL",
                "a2_v24_f3_marginal_e1_cell": cell["cell"],
                "a2_v24_f3_marginal_e1_posture": cell["posture"],
                "a2_v24_f3_marginal_e1_training_seed": cell["seed"],
                "a2_v24_f3_marginal_e1_checkpoint_path": checkpoint,
                "a2_v24_f3_marginal_e1_checkpoint_id": "model_step_000500",
                "a2_v24_f3_marginal_e1_global_step": 500,
                "a2_v24_f3_marginal_e1_evidence_path": f"{output_dir}/F3_EVIDENCE.json",
            }
        )
        command = [
            "/home/baoquanc/anaconda3/envs/isaaclab/bin/python",
            "-m",
            "gr00t.rl.eval_agent_trl",
            f"++checkpoint={checkpoint}",
            "++checkpoint_load_mode=policy_only",
            "++auto_load_latest=false",
            "++headless=true",
            "++num_envs=16",
            f"++seed={cell['seed']}",
            "++use_wandb=false",
            "++algo.trl.report_to=none",
            "++algo.config.eval.a2_v23_p06_policy_only=true",
            "++algo.config.eval.eval_num_envs_episodes=true",
            "++algo.config.eval.num_eval_episodes=16",
            f"++algo.config.eval.a2_eval_p2_posture_axis={'rp0' if rp0 else 'none'}",
            "++simulator.config.cameras.enable_cameras=false",
            "++simulator.config.render_results=false",
            "++env.config.a2_base.enabled=true",
            "++algo.config.num_mini_batches=1",
            f"++eval_output_dir={output_dir}",
        ]
        command.extend(
            f"++env.config.{key}={_hydra_value(value)}"
            for key, value in sorted(runtime_env.items())
        )
        command.extend(
            [
            "++v24_schema=a2_piper_v24_p2_force_boundary_v1",
            "++v24_plan_id=base_v24_force_boundary_R12",
            "++v24_runtime_mode=P2_TELEMETRY",
            f"++v24_checkpoint_provenance={checkpoint}",
            "++v24_checkpoint_load_mode=selected_policy_only",
            f"++v24_p2.checkpoint={checkpoint}",
            "++v24_p2.checkpoint_load_mode=selected_policy_only",
            "++v24_p2.runtime_modes=[HI_FULL,BOUNDARY_FULL,BOUNDARY_RP0,RESCUE_FULL]",
            ]
        )
        commands.append(
            {
                "cell": cell["cell"],
                "posture": cell["posture"],
                "seed": cell["seed"],
                "profile": "F05",
                "cap_nm": 20.0,
                "mode": mode,
                "num_envs": 16,
                "scenario_ids": list(p2.SCENARIO_IDS),
                "continuity_id": "F3_POST_TRAIN_EVAL",
                "checkpoint": checkpoint,
                "command": command,
                "rp0_distribution_contract": {
                    "enabled": rp0,
                    "indices": [3, 4],
                    "neutral_value": 0.0,
                    "post_sample_clamp": False,
                },
            }
        )
    return {
        "schema": "a2_piper_v24_r12_f3_post_training_eval_commands_v1",
        "status": "REGISTERED_NOT_EXECUTED",
        "registration_id": registration["registration_id"],
        "commands": commands,
        "profile": "F05",
        "cap_nm": 20.0,
        "num_envs": 16,
        "scenario_ids": list(p2.SCENARIO_IDS),
        "continuity_id": "F3_POST_TRAIN_EVAL",
        "execution": "NOT_RUN_BY_CPU_PLAN",
    }


def write_post_training_eval_commands(
    *,
    registration: Mapping[str, Any],
    checkpoints: Mapping[str, str | Path],
    output_root: str = "logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/post_training_eval",
    root: str | Path = p2.PILOT_ARTIFACT_ROOT,
    require_source_files: bool = True,
) -> Path:
    payload = build_post_training_eval_commands(
        registration=registration,
        checkpoints=checkpoints,
        output_root=output_root,
        require_source_files=require_source_files,
    )
    return _write_json(_root(root), PILOT_ARTIFACTS[5], payload)


def _rule16_from_registration(registration: Mapping[str, Any], *, require_source_files: bool = True) -> dict[str, Any]:
    rule16 = registration.get("rule16_admission")
    p2._validate_rule16_admission(rule16, require_source_files=require_source_files)
    if registration.get("owner_decision_artifact") != rule16.get("owner_decision_artifact"):
        raise ValueError("pilot registration owner-decision provenance is not Rule16-bound")
    return dict(rule16)


def validate_pilot_rows(rows: Sequence[Mapping[str, Any]], *, registration: Mapping[str, Any], require_source_files: bool = True) -> dict[str, Any]:
    _rule16_from_registration(registration, require_source_files=require_source_files)
    if isinstance(rows, (str, bytes)) or len(rows) != len(PILOT_CELLS) * 16:
        raise ValueError("pilot population requires exactly 64 completed rows")
    allowed_cells = {cell["cell"]: cell for cell in PILOT_CELLS}
    identities: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    admitted: dict[str, int] = {cell["cell"]: 0 for cell in PILOT_CELLS}
    completed: dict[str, int] = {cell["cell"]: 0 for cell in PILOT_CELLS}
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise TypeError(f"pilot row {index} must be a mapping")
        cell_name = raw.get("cell")
        cell = allowed_cells.get(cell_name)
        if cell is None or raw.get("posture") != cell["posture"] or raw.get("seed") != cell["seed"]:
            raise ValueError(f"pilot row {index} has an unregistered cell identity")
        if raw.get("candidate_bucket") != "F05" or raw.get("profile") != "F05" or raw.get("cap_nm") != 20.0:
            raise ValueError(f"pilot row {index} is not from the registered F05/cap20 evaluation face")
        checkpoint_path = raw.get("checkpoint_path")
        if not isinstance(checkpoint_path, str) or not checkpoint_path.endswith(f"/{cell_name}/model_step_000500.pt"):
            raise ValueError(f"pilot row {index} does not identify its cell final step500 checkpoint")
        if raw.get("checkpoint_id") != "model_step_000500" or raw.get("global_step") != 500:
            raise ValueError(f"pilot row {index} has invalid final-checkpoint provenance")
        env_id = raw.get("env_id")
        scenario_id = raw.get("scenario_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < 16 or scenario_id != f"S{env_id:02d}":
            raise ValueError(f"pilot row {index} has invalid env/scenario provenance")
        if raw.get("condition") != "R12_PILOT_CELL" or raw.get("continuity_id") != "F3_POST_TRAIN_EVAL":
            raise ValueError(f"pilot row {index} has invalid r12 evaluation continuity")
        if raw.get("runtime_generated") is not True or raw.get("runtime_producer") != "R12F3EvidenceExporter":
            raise ValueError(f"pilot row {index} lacks runtime evidence provenance")
        window_rows = raw.get("window_rows")
        if not isinstance(window_rows, list) or len(window_rows) != 25:
            raise ValueError(f"pilot row {index} lacks its exact runtime 25-transition window")
        if any(row.get("env_id") != env_id or row.get("scenario_id") != scenario_id for row in window_rows):
            raise ValueError(f"pilot row {index} window provenance differs from its population row")
        authority = raw.get("authority")
        if not isinstance(authority, Mapping) or authority.get("door_friction") != "MODELED_FROM_PARAMS" or authority.get("solver_applied") is not False:
            raise ValueError(f"pilot row {index} has invalid modeled-friction authority")
        if raw.get("confirmed_e2") is not False:
            raise ValueError("r12 marginal-E1 pilot must not confirm E2")
        window_id = raw.get("window_id")
        if not isinstance(window_id, str) or not window_id:
            raise ValueError(f"pilot row {index} requires a stable window_id")
        if raw.get("completed") is False or raw.get("episode_complete") is False:
            raise ValueError(f"pilot row {index} is nonterminal")
        if raw.get("completed") is not True and raw.get("episode_complete") is not True:
            raise ValueError(f"pilot row {index} must carry completed=true or episode_complete=true")
        if raw.get("window_transition_count") != 25:
            raise ValueError(f"pilot row {index} must carry exactly 25 transitions")
        source_status = raw.get("source_status")
        if raw.get("source_unavailable") is not None or raw.get("source_valid") is False:
            raise ValueError(f"pilot row {index} has unavailable source data")
        if any(raw.get(field) is True for field in ("grasp_source_unavailable", "model_source_unavailable")):
            raise ValueError(f"pilot row {index} has unavailable typed source data")
        if isinstance(source_status, Mapping) and any(value != "AVAILABLE" for value in source_status.values()):
            raise ValueError(f"pilot row {index} has non-available source status")
        if raw.get("foot_slip_valid") is False or raw.get("model_valid") is False:
            raise ValueError(f"pilot row {index} has invalid source vitals")
        lam = raw.get("lambda", raw.get("lambda_median"))
        if isinstance(lam, bool) or not isinstance(lam, (int, float)) or not math.isfinite(float(lam)):
            raise ValueError(f"pilot row {index} requires a finite lambda")
        key = (cell_name, window_id)
        if key in identities:
            raise ValueError(f"pilot row {index} duplicates window identity {key!r}")
        identities.add(key)
        completed[cell_name] += 1
        stage_ids = raw.get("window_stage_ids")
        stage_valid = isinstance(stage_ids, (list, tuple)) and bool(stage_ids) and all(stage in (3, 4) for stage in stage_ids)
        grasp_valid = raw.get("stable_grasp") is True and raw.get("window_stable_grasp_count", 0) >= 20
        typed_excluded = any(raw.get(field) is True for field in ("excluded_geometry", "excluded_grasp", "excluded_direction", "excluded_slip", "excluded_pathology", "excluded_window_selection"))
        excluded = raw.get("excluded") not in (None, [], (), False) or typed_excluded
        is_admitted = (
            grasp_valid
            and stage_valid
            and raw.get("window_stage_reach_valid", True) is True
            and raw.get("window_selection_valid", True) is True
            and not excluded
            and 0.5 <= float(lam) < 1.0
        )
        if is_admitted:
            admitted[cell_name] += 1
        item = dict(raw)
        item["admitted_sustained_e1"] = is_admitted
        normalized.append(item)
    counts = dict(completed)
    if any(count != 16 for count in counts.values()):
        raise ValueError(f"pilot population requires exactly 16 completed rows per cell: {counts!r}")
    return {
        "rows": normalized,
        "population_valid": True,
        "population_rows": len(normalized),
        "unique_completed_windows": len(identities),
        "unique_admitted_windows": sum(admitted.values()),
        "windows_per_cell": dict(admitted),
        "admitted_per_cell": dict(admitted),
        "completed_rows_per_cell": counts,
        "all_cells_present": all(count == 16 for count in counts.values()),
        "minimum_unique_windows_per_cell": PILOT_REQUIRED_WINDOWS,
        "candidate_buckets": list(PILOT_BUCKETS),
        "rescue_cap_nm": PILOT_RESCUE_CAP_NM,
        "confirmed_e2_share": PILOT_CONFIRMED_E2_SHARE,
    }


def adjudicate_pilot(*, rows: Sequence[Mapping[str, Any]], registration: Mapping[str, Any], require_source_files: bool = True) -> dict[str, Any]:
    rule16 = _rule16_from_registration(registration, require_source_files=require_source_files)
    try:
        summary = validate_pilot_rows(rows, registration=registration, require_source_files=require_source_files)
    except (TypeError, ValueError) as exc:
        return {
            "schema": PILOT_ADJUDICATION_SCHEMA,
            "status": "INCONCLUSIVE_PILOT_ROWS",
            "terminal": False,
            "p3_admitted": False,
            "typed_results": [],
            "reason": str(exc),
            "registration_id": registration["registration_id"],
            "rule16_admission": rule16,
            "owner_decision_artifact": registration["owner_decision_artifact"],
        }
    sufficient = all(
        summary["windows_per_cell"][cell["cell"]] >= PILOT_REQUIRED_WINDOWS for cell in PILOT_CELLS
    )
    if not summary["all_cells_present"]:
        return {
            "schema": PILOT_ADJUDICATION_SCHEMA,
            "status": "INCONCLUSIVE_PILOT_ROWS",
            "terminal": False,
            "p3_admitted": False,
            "typed_results": [],
            "reason": "pilot rows do not cover all four registered cells",
            "registration_id": registration["registration_id"],
            "rule16_admission": rule16,
            "owner_decision_artifact": registration["owner_decision_artifact"],
        }
    if sufficient:
        status = "PILOT_COMPLETE_VALID"
        typed = ["V24_E1_BOUNDARY_ESTABLISHED_POST_F3"]
        terminal = False
    else:
        status = "V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3"
        typed = [status]
        terminal = True
    return {
        "schema": PILOT_ADJUDICATION_SCHEMA,
        "status": status,
        "terminal": terminal,
        "p3_admitted": False,
        "typed_results": typed,
        "registration_id": registration["registration_id"],
        "rule16_admission": rule16,
        "owner_decision_artifact": registration["owner_decision_artifact"],
        "vitals_receipt_artifact": registration["vitals_receipt_artifact"],
        "gradient_admission": dict(registration["gradient_admission"]),
        "summary": {key: value for key, value in summary.items() if key != "rows"},
    }


def write_adjudication(
    *,
    rows: Sequence[Mapping[str, Any]],
    registration: Mapping[str, Any],
    root: str | Path = p2.PILOT_ARTIFACT_ROOT,
) -> Path:
    return _write_json(_root(root), PILOT_ARTIFACTS[2], adjudicate_pilot(rows=rows, registration=registration))


def post_pilot_finalize(*, adjudication: Mapping[str, Any], registration: Mapping[str, Any], require_source_files: bool = True) -> dict[str, Any]:
    rule16 = _rule16_from_registration(registration, require_source_files=require_source_files)
    if adjudication.get("schema") != PILOT_ADJUDICATION_SCHEMA or adjudication.get("registration_id") != registration.get("registration_id"):
        raise ValueError("pilot adjudication artifact is invalid")
    if adjudication.get("status") == "INCONCLUSIVE_PILOT_ROWS":
        raise RuntimeError("post-pilot finalization is blocked by INCONCLUSIVE_PILOT_ROWS")
    if adjudication.get("rule16_admission") != rule16:
        raise ValueError("post-pilot finalization Rule16 admission is not carried through")
    terminal = adjudication.get("status") == "V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3"
    return {
        "schema": PILOT_FINAL_SCHEMA,
        "status": "POST_PILOT_FINALIZED",
        "pilot_status": adjudication["status"],
        "typed_results": list(adjudication["typed_results"]),
        "terminal": terminal,
        "p3_admitted": False,
        "heldout_status": "NOT_ADMITTED_BY_POST_F3_TERMINAL" if terminal else "P2_HELDOUT_PENDING_POST_F3",
        "registration_id": registration["registration_id"],
        "rule16_admission": rule16,
        "owner_decision_artifact": registration["owner_decision_artifact"],
        "vitals_receipt_artifact": registration["vitals_receipt_artifact"],
        "pilot_adjudication_artifact": _path_reference(f"{p2.ARTIFACT_ROOT}/{PILOT_ARTIFACTS[2]}"),
        "raw_recomputation": False,
    }


def write_finalization(
    *,
    adjudication: Mapping[str, Any],
    registration: Mapping[str, Any],
    root: str | Path = p2.PILOT_ARTIFACT_ROOT,
) -> Path:
    payload = post_pilot_finalize(adjudication=adjudication, registration=registration)
    return _write_json(_root(root), PILOT_ARTIFACTS[3], payload)


def _synthetic_rows(*, admitted_per_cell: Mapping[str, int] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in PILOT_CELLS:
        admitted_count = 8 if admitted_per_cell is None else int(admitted_per_cell.get(cell["cell"], 8))
        if not 0 <= admitted_count <= 16:
            raise ValueError("synthetic admitted count must be in 0..16")
        for index in range(16):
            admitted = index < admitted_count
            rows.append(
                {
                    **cell,
                    "candidate_bucket": "F05",
                    "profile": "F05",
                    "cap_nm": 20.0,
                    "checkpoint_path": f"logs_rl/v24/{cell['cell']}/model_step_000500.pt",
                    "checkpoint_id": "model_step_000500",
                    "global_step": 500,
                    "env_id": index,
                    "scenario_id": f"S{index:02d}",
                    "condition": "R12_PILOT_CELL",
                    "continuity_id": "F3_POST_TRAIN_EVAL",
                    "runtime_generated": True,
                    "runtime_producer": "R12F3EvidenceExporter",
                    "window_rows": [
                        {"env_id": index, "scenario_id": f"S{index:02d}"}
                        for _ in range(25)
                    ],
                    "authority": {"door_friction": "MODELED_FROM_PARAMS", "solver_applied": False},
                    "window_id": f"{cell['cell']}-W{index:02d}",
                    "completed": True,
                    "episode_complete": True,
                    "window_transition_count": 25,
                    "window_stable_grasp_count": 20 if admitted else 19,
                    "window_stage_ids": [3] if admitted else [2],
                    "window_stage_reach_valid": admitted,
                    "window_selection_valid": admitted,
                    "stable_grasp": admitted,
                    "lambda": 0.7 if admitted else 0.3,
                    "source_unavailable": None,
                    "source_valid": True,
                    "source_status": {"foot": "AVAILABLE", "grasp": "AVAILABLE", "model": "AVAILABLE"},
                    "foot_slip_valid": True,
                    "model_valid": True,
                    "grasp_source_unavailable": False,
                    "model_source_unavailable": False,
                    "excluded": [],
                    "excluded_geometry": False,
                    "excluded_grasp": not admitted,
                    "excluded_direction": False,
                    "excluded_slip": False,
                    "excluded_pathology": False,
                    "excluded_window_selection": not admitted,
                    "confirmed_e2": False,
                }
            )
    return rows


def self_check() -> dict[str, Any]:
    source_rows = p2._validate_vital_rows(p2._synthetic_vital_rows())
    vitals = p2._build_vital_receipt(source_rows)
    registration = build_registration(vitals_receipt=vitals, require_source_files=False)
    commands = build_pilot_commands(registration=registration, require_source_files=False)
    adjudication = adjudicate_pilot(rows=_synthetic_rows(), registration=registration, require_source_files=False)
    if adjudication["status"] != "PILOT_COMPLETE_VALID":
        raise AssertionError("synthetic complete pilot did not pass")
    insufficient_rows = _synthetic_rows(admitted_per_cell={PILOT_CELLS[0]["cell"]: 7})
    insufficient = adjudicate_pilot(rows=insufficient_rows, registration=registration, require_source_files=False)
    if insufficient["status"] != "V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3":
        raise AssertionError("seven-admitted-cell pilot did not produce valid post-F3 insufficiency")
    duplicate = _synthetic_rows()[:-1] + [_synthetic_rows()[0]]
    duplicate_result = adjudicate_pilot(rows=duplicate, registration=registration, require_source_files=False)
    if duplicate_result["status"] != "INCONCLUSIVE_PILOT_ROWS":
        raise AssertionError("duplicate pilot population was not inconclusive")
    missing = _synthetic_rows()[:-1]
    missing_result = adjudicate_pilot(rows=missing, registration=registration, require_source_files=False)
    if missing_result["status"] != "INCONCLUSIVE_PILOT_ROWS":
        raise AssertionError("missing pilot population was not inconclusive")
    source_invalid = _synthetic_rows()
    source_invalid[0] = {**source_invalid[0], "source_unavailable": "SOURCE_UNAVAILABLE"}
    source_invalid_result = adjudicate_pilot(rows=source_invalid, registration=registration, require_source_files=False)
    if source_invalid_result["status"] != "INCONCLUSIVE_PILOT_ROWS":
        raise AssertionError("source-invalid pilot population was not inconclusive")
    bad_rule16 = dict(registration["rule16_admission"])
    bad_rule16["stage_reach_vital"] = {**bad_rule16["stage_reach_vital"], "pass": False}
    try:
        p2._validate_rule16_admission(bad_rule16)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid stage-reach Rule16 admission was accepted")
    bad_grasp = dict(source_rows[0])
    bad_grasp["stable_grasp"] = None
    bad_grasp["stable_grasp_fraction"] = None
    bad_grasp["grasp_source_unavailable"] = True
    bad_grasp["source_unavailable"] = "SOURCE_UNAVAILABLE"
    bad_grasp["source_status"] = {"foot": "AVAILABLE", "grasp": "SOURCE_UNAVAILABLE", "model": "AVAILABLE"}
    try:
        p2._validate_vital_rows([bad_grasp] + source_rows[1:])
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("missing grasp vital was accepted")
    bad_parameter = dict(source_rows[0])
    bad_parameter.pop("parameter_vitals", None)
    try:
        p2._validate_vital_rows([bad_parameter] + source_rows[1:])
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("missing parameter vital was accepted")
    post_eval = build_post_training_eval_commands(
        registration=registration,
        checkpoints={cell["cell"]: f"logs_rl/v24/{cell['cell']}/model_step_000500.pt" for cell in PILOT_CELLS},
        require_source_files=False,
    )
    return {
        "status": "SELF_CHECK_PASS",
        "registration_id": registration["registration_id"],
        "command_cells": len(commands["commands"]),
        "smoke_command_cells": len(commands["training_smoke"]),
        "post_eval_command_cells": len(post_eval["commands"]),
        "adjudication_status": adjudication["status"],
        "insufficient_status": insufficient["status"],
        "duplicate_status": duplicate_result["status"],
        "missing_status": missing_result["status"],
        "source_invalid_status": source_invalid_result["status"],
        "rule16_stage_reach": registration["rule16_admission"]["stage_reach_vital"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CPU-only r12 marginal-E1 pilot contracts")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--mode", choices=("register", "commands", "population", "adjudicate", "finalize", "post_eval_commands"))
    parser.add_argument("--root", default=p2.PILOT_ARTIFACT_ROOT)
    parser.add_argument("--rows", help="JSONL pilot rows for --mode adjudicate")
    parser.add_argument("--registration", help="registration JSON for --mode commands/adjudicate/finalize")
    parser.add_argument("--adjudication", help="adjudication JSON for --mode finalize")
    parser.add_argument("--checkpoints", help="JSON mapping cell names to model_step_000500.pt paths for --mode post_eval_commands")
    parser.add_argument("--post-eval-output-root", default="logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/post_training_eval")
    args = parser.parse_args(argv)
    if args.self_check:
        print(json.dumps(self_check(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0
    if args.mode is None:
        parser.error("pass --self-check or one pilot --mode")
    root = _root(args.root)
    if args.mode == "register":
        vitals = p2._build_vital_receipt(p2._read_vital_source_rows())
        print(str(write_registration(vitals_receipt=vitals, root=root)))
        return 0
    if not args.registration:
        parser.error("--registration is required for this mode")
    registration = json.loads(Path(args.registration).read_text(encoding="utf-8"))
    if args.mode == "commands":
        print(str(write_commands(registration=registration, root=root)))
        return 0
    if args.mode == "post_eval_commands":
        if not args.checkpoints:
            parser.error("--checkpoints is required for post_eval_commands")
        checkpoints = json.loads(Path(args.checkpoints).read_text(encoding="utf-8"))
        print(str(write_post_training_eval_commands(registration=registration, checkpoints=checkpoints, output_root=args.post_eval_output_root, root=root)))
        return 0
    if not args.rows:
        parser.error("--rows is required for population or adjudicate")
    rows = [json.loads(line) for line in Path(args.rows).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.mode == "population":
        print(str(write_population_rows(rows=rows, registration=registration, root=root)))
        return 0
    if args.mode == "adjudicate":
        print(str(write_adjudication(rows=rows, registration=registration, root=root)))
        return 0
    if not args.adjudication:
        parser.error("--adjudication is required for finalize")
    adjudication = json.loads(Path(args.adjudication).read_text(encoding="utf-8"))
    print(str(write_finalization(adjudication=adjudication, registration=registration, root=root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PILOT_ARTIFACTS",
    "PILOT_CELLS",
    "PILOT_CONFIG",
    "PILOT_REQUIRED_WINDOWS",
    "adjudicate_pilot",
    "build_pilot_commands",
    "build_post_training_eval_commands",
    "build_registration",
    "post_pilot_finalize",
    "self_check",
    "validate_pilot_rows",
    "write_adjudication",
    "write_commands",
    "write_finalization",
    "write_population_rows",
    "write_post_training_eval_commands",
    "write_registration",
]
