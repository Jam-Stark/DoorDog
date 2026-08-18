"""Owner-adjudicated r13 behavioral E-region freeze and F3-prime lifecycle."""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import sys
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

import yaml

try:
    from . import p2_force_boundary_r13 as r13
except ImportError:
    repo = Path(__file__).resolve().parents[2]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from scriptsFORhuman.v24 import p2_force_boundary_r13 as r13


REPO_ROOT = Path(__file__).resolve().parents[2]
OWNER_DECISION = REPO_ROOT / "scriptsFORhuman/v24/DoorDog_v24_owner_decision_r13_gradient_adjudication_20260818.md"
R13_ROOT = REPO_ROOT / "logs_eval/base_v24/p2/force_boundary/r13"
ROOT = R13_ROOT / "behavioral_reentry"
TRAIN_ROOT = "logs_rl/a2_piper_full_stage_a2_base/v24/r13/f3_prime_behavioral"
CONFIG = "gr00t/rl/config/ablation/wbmanip/base_v24_r13_f3_behavioral_pilot.yaml"
CHECKPOINT = "logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt"
CELLS = (
    {"cell": "DF1_FULL_SEED0", "posture": "FULL", "seed": 0, "gpu": 0},
    {"cell": "DF1_FULL_SEED1", "posture": "FULL", "seed": 1, "gpu": 1},
    {"cell": "DF1_RP0_SEED0", "posture": "RP0", "seed": 0, "gpu": 2},
    {"cell": "DF1_RP0_SEED1", "posture": "RP0", "seed": 1, "gpu": 3},
)
SCENARIOS = tuple(f"S{index:02d}" for index in range(16))
BOUNDARY_SCENARIOS = tuple(SCENARIOS) + tuple(SCENARIOS)

DELTA_LO_RAD = 0.020
DELTA_HI_RAD = 0.040
CLIP_FLOOR = 0.40
UTILIZATION_FLOOR = 0.50
TAU_HI_NM = 40.0
TAU_BOUNDARY_NM = 20.0
TAU_RESCUE_NM = 25.0
BOUNDARY_PROFILE = "P10"
NEAR_E2_PROFILE = "P20"

ARTIFACTS = {
    "gradient": "V24_P2_R13_BEHAVIORAL_GRADIENT_ADJUDICATION.json",
    "ladder": "V24_P2_R13_BEHAVIORAL_LADDER_FREEZE.json",
    "e_region": "V24_P2_R13_BEHAVIORAL_E_REGION_FREEZE.json",
    "registration": "V24_P2_R13_F3_PRIME_BEHAVIORAL_REGISTRATION.json",
    "training_commands": "P2_R13_F3_PRIME_TRAINING_COMMANDS.json",
    "checkpoints": "P2_R13_F3_PRIME_STEP500_CHECKPOINTS.json",
    "eval_commands": "P2_R13_F3_PRIME_POST_TRAINING_EVAL_COMMANDS.json",
    "population": "P2_R13_F3_PRIME_BEHAVIORAL_POPULATION.jsonl",
    "adjudication": "P2_R13_F3_PRIME_BEHAVIORAL_ADJUDICATION.json",
    "finalization": "P2_R13_F3_PRIME_FINALIZATION.json",
}


def _finite(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a mapping")
    return payload


def _rows(path: Path) -> list[dict[str, Any]]:
    result = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in result):
        raise ValueError(f"{path} contains a non-mapping row")
    return result


def _write_json(name: str, payload: Mapping[str, Any]) -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / name
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(dict(payload), stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"r13 behavioral artifact is append-only: {path}") from exc
    return path


def _write_rows(name: str, rows: Sequence[Mapping[str, Any]]) -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / name
    try:
        with path.open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"r13 behavioral artifact is append-only: {path}") from exc
    return path


def _hydra(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_hydra(item) for item in value) + "]"
    return str(value)


def _source_valid(row: Mapping[str, Any]) -> bool:
    source_status = row.get("source_status")
    return (
        row.get("stable_grasp") is True
        and row.get("window_stable_grasp_count", 0) >= 20
        and row.get("window_stage_reach_valid") is True
        and row.get("window_selection_valid") is True
        and row.get("foot_slip_valid") is True
        and row.get("source_unavailable") is None
        and row.get("grasp_source_unavailable") is False
        and row.get("model_source_unavailable") is False
        and isinstance(source_status, Mapping)
        and all(value == "AVAILABLE" for value in source_status.values())
    )


def _classify(*, deficit: float, clip_fraction: float, utilization: float, valid: bool) -> str:
    if not valid:
        return "INVALID_MEASUREMENT"
    high_load = clip_fraction >= CLIP_FLOOR and utilization >= UTILIZATION_FLOOR
    if deficit < DELTA_LO_RAD and not high_load:
        return "E0"
    if DELTA_LO_RAD <= deficit <= DELTA_HI_RAD and high_load:
        return "E1"
    if deficit > DELTA_HI_RAD and high_load:
        return "NEAR_E2_CANDIDATE"
    return "UNCLASSIFIED_BEHAVIOR_LOAD_MISMATCH"


def _calibration_evidence() -> tuple[list[dict[str, Any]], dict[str, float]]:
    rows = _rows(R13_ROOT / "calibration/P2_CALIBRATION_ROWS.jsonl")
    sham = _rows(R13_ROOT / "vitals/P2_SHAM_ROWS.jsonl")
    if len(rows) != 384 or len(sham) != 16:
        raise ValueError("r13 behavioral freeze requires 384 calibration and 16 sham rows")
    sham_progress = {row["scenario_id"]: _finite(row["progress_recovery_delta_rad"], name="sham progress") for row in sham}
    if set(sham_progress) != set(SCENARIOS):
        raise ValueError("r13 sham topology must be canonical16")
    return rows, sham_progress


def build_freezes() -> dict[str, dict[str, Any]]:
    if not OWNER_DECISION.is_file():
        raise FileNotFoundError(OWNER_DECISION)
    old_gradient = _json(R13_ROOT / "V24_P2_R13_GRADIENT_ADMISSION.json")
    old_ladder = _json(R13_ROOT / "V24_P2_R13_LADDER_FREEZE.json")
    old_e = _json(R13_ROOT / "V24_P2_R13_E_REGION_FREEZE.json")
    old_registration = _json(R13_ROOT / "V24_P2_R13_F3_PRIME_REGISTRATION.json")
    if old_gradient.get("status") != "V24_FRICTION_AXIS_NONDISCRIMINATIVE" or old_gradient.get("matched_tau_strict") != 47:
        raise ValueError("historical r13 gradient artifact is not the immutable Owner-adjudicated input")
    rows, sham_progress = _calibration_evidence()
    progress = {profile: median(_finite(row["progress_recovery_delta_rad"], name="progress") for row in rows if row["profile"] == profile) for profile in r13.PROFILES}
    low_high = sum(
        _finite(next(row for row in rows if row["profile"] == "P02" and row["cap_nm"] == cap and row["scenario_id"] == scenario)["progress_recovery_delta_rad"], name="P02 progress")
        > _finite(next(row for row in rows if row["profile"] == "P20" and row["cap_nm"] == cap and row["scenario_id"] == scenario)["progress_recovery_delta_rad"], name="P20 progress")
        for cap in r13.CAPS for scenario in r13.SCENARIOS
    )
    if not all(progress[left] > progress[right] for left, right in zip(r13.PROFILES, r13.PROFILES[1:])) or low_high != 96:
        raise ValueError("r13 behavioral gradient evidence no longer matches the Owner decision")

    face_counts: dict[str, dict[str, int]] = {}
    for profile in r13.PROFILES:
        for cap in r13.CAPS:
            key = f"{profile}_CAP{int(cap)}"
            counts = {name: 0 for name in ("E0", "E1", "NEAR_E2_CANDIDATE", "UNCLASSIFIED_BEHAVIOR_LOAD_MISMATCH", "INVALID_MEASUREMENT")}
            for row in rows:
                if row["profile"] != profile or row["cap_nm"] != cap:
                    continue
                deficit = sham_progress[row["scenario_id"]] - _finite(row["progress_recovery_delta_rad"], name="calibration progress")
                zone = _classify(
                    deficit=deficit,
                    clip_fraction=_finite(row["directional_clip_fraction_median"], name="clip fraction"),
                    utilization=_finite(row["directional_utilization_median"], name="utilization"),
                    valid=_source_valid(row),
                )
                counts[zone] += 1
            face_counts[key] = counts

    if face_counts["P02_CAP40"]["E0"] != 8 or face_counts["P10_CAP20"]["E1"] != 7 or face_counts["P20_CAP20"]["NEAR_E2_CANDIDATE"] != 8:
        raise ValueError("r13 behavioral ladder anchor counts changed")

    authority = {
        "door_friction": "MODELED_FROM_PARAMS",
        "solver_applied": False,
        "capacity_lambda": "ESTIMATE_ONLY_REPORT_ONLY",
        "behavior": "HIGH_LEVEL_ARTICULATION_DATA",
    }
    classifier = {
        "revision": "R13_BEHAVIORAL_OWNER_ADJUDICATED",
        "deficit_definition": "same-checkpoint same-scenario F00/cap40 progress minus evaluated progress",
        "delta_lo_rad": DELTA_LO_RAD,
        "delta_hi_rad": DELTA_HI_RAD,
        "directional_clip_fraction_floor": CLIP_FLOOR,
        "directional_utilization_floor": UTILIZATION_FLOOR,
        "load_bearing_high_rule": "clip_fraction>=0.40 AND utilization>=0.50",
        "E0": "valid grasp/source + deficit<delta_lo + no load-bearing high load",
        "E1": "valid grasp/source + delta_lo<=deficit<=delta_hi + load-bearing high load",
        "near_E2_candidate": "valid grasp/source + deficit>delta_hi + load-bearing high load",
        "confirmed_E2": "requires registered rescue counterfactual; never inferred by this classifier",
        "lambda_capacity_role": "ESTIMATE_ONLY_REPORT_ONLY",
        "capacity_collapse_role": "RQ3_MEDIATOR_ONLY",
    }
    gradient = {
        "schema": "a2_piper_v24_p2_r13_behavioral_gradient_adjudication_v1",
        "status": "V24_FRICTION_AXIS_DISCRIMINATIVE_BEHAVIORAL",
        "terminal": False,
        "owner_decision": str(OWNER_DECISION.relative_to(REPO_ROOT)),
        "historical_artifact": str((R13_ROOT / "V24_P2_R13_GRADIENT_ADMISSION.json").relative_to(REPO_ROOT)),
        "historical_artifact_status_preserved": old_gradient["status"],
        "modeled_tau_diagnostic": "MODELED_TAU_MATCHED_ORDERING_CONFOUNDED_BY_SPEED_ADAPTATION",
        "modeled_tau_diagnostic_role": "REPORT_ONLY",
        "progress_medians_rad": progress,
        "strict_profile_median_order": True,
        "matched_P02_progress_gt_P20": low_high,
        "matched_total": 96,
        "low_high_progress_span_rad": progress["P02"] - progress["P20"],
        "p1_lite_input_output_authority": "BREAKAWAY_LITERAL_CONTAINMENT_ALL_FOUR_PROFILES",
        "authority": authority,
    }
    ladder = {
        "schema": "a2_piper_v24_p2_r13_behavioral_ladder_freeze_v1",
        "status": "EXECUTED_NON_NULL",
        "owner_decision": str(OWNER_DECISION.relative_to(REPO_ROOT)),
        "historical_ladder_status_preserved": old_ladder["status"],
        "tau_hi_nm": TAU_HI_NM,
        "tau_boundary_nm": TAU_BOUNDARY_NM,
        "tau_rescue_nm": TAU_RESCUE_NM,
        "tau_hi_face": {"profile": "P02", "cap_nm": TAU_HI_NM, "E0_count": 8},
        "boundary_face": {"profile": BOUNDARY_PROFILE, "cap_nm": TAU_BOUNDARY_NM, "E1_count": 7},
        "rescue_face": {"profile": BOUNDARY_PROFILE, "cap_nm": TAU_RESCUE_NM, "E1_count": face_counts["P10_CAP25"]["E1"]},
        "near_e2_face": {"profile": NEAR_E2_PROFILE, "cap_nm": TAU_BOUNDARY_NM, "near_E2_candidate_count": 8},
        "selection_basis": "maximum calibration E1 density at P10/cap20; immediate higher registered cap25 rescue; P02/cap40 E0 anchor",
        "face_counts": face_counts,
    }
    e_region = {
        "schema": "a2_piper_v24_p2_r13_behavioral_e_region_freeze_v1",
        "status": "EXECUTED_BEFORE_F3_PRIME_POPULATION",
        "owner_decision": str(OWNER_DECISION.relative_to(REPO_ROOT)),
        "historical_e_region_status_preserved": old_e["status"],
        "typed_finding": "CAPACITY_ESTIMATOR_LOWER_BOUND_DEGENERATE",
        "capacity_collapsed_windows": 358,
        "classifier": classifier,
        "ladder": {"tau_hi_nm": TAU_HI_NM, "tau_boundary_nm": TAU_BOUNDARY_NM, "tau_rescue_nm": TAU_RESCUE_NM},
        "calibration_face_counts": face_counts,
        "authority": authority,
    }
    registration = {
        "schema": "a2_piper_v24_p2_r13_f3_prime_behavioral_registration_v1",
        "status": "REGISTERED_BEFORE_F3_PRIME_POPULATION",
        "owner_decision": str(OWNER_DECISION.relative_to(REPO_ROOT)),
        "historical_registration_preserved": str((R13_ROOT / "V24_P2_R13_F3_PRIME_REGISTRATION.json").relative_to(REPO_ROOT)),
        "historical_registration_status": old_registration["status"],
        "cells": [cell["cell"] for cell in CELLS],
        "episodes_per_cell": 32,
        "sustained_e1_min_per_cell": 8,
        "terminal_if_insufficient": "V24_E1_DENOMINATOR_INSUFFICIENT_FINAL",
        "classifier": classifier,
        "boundary_evaluation_face": {"profile": BOUNDARY_PROFILE, "cap_nm": TAU_BOUNDARY_NM},
        "rule16_per_checkpoint_sham": {"profile": "F00", "cap_nm": TAU_HI_NM, "episodes": 16, "stable_grasp_min": 14},
        "training_distribution": {
            "buckets": {
                "E0_SHAM": {"profile": "F00", "cap_nm": 40.0},
                "E1_BOUNDARY": {"profile": "P10", "cap_nm": 20.0},
                "NEAR_E2": {"profile": "P20", "cap_nm": 20.0},
            },
            "phase_counts_4096": [[4096, 0, 0], [2458, 1638, 0], [1229, 2458, 409]],
            "confirmed_e2_share": 0.0,
        },
        "authority": authority,
    }
    return {"gradient": gradient, "ladder": ladder, "e_region": e_region, "registration": registration}


def _training_command(cell: Mapping[str, Any], *, smoke: bool) -> dict[str, Any]:
    envs, batches, save = (64, 10, 10) if smoke else (4096, 500, 250)
    label = "smoke" if smoke else "production"
    output = f"{TRAIN_ROOT}/{label}/{cell['cell']}"
    rp0 = cell["posture"] == "RP0"
    command = [
        "/home/baoquanc/anaconda3/envs/isaaclab/bin/python", "-m", "gr00t.rl.train_agent_trl",
        "+exp=wbmanip/door_open_a2_base_lstm", "+ablation=wbmanip/base_v24_r13_f3_behavioral_pilot",
        "project_name=a2_piper_full_stage_a2_base", f"experiment_name=R13_F3_PRIME_{cell['cell']}_{label.upper()}",
        f"experiment_dir={output}", f"checkpoint={CHECKPOINT}", "checkpoint_load_mode=policy_only",
        "auto_load_latest=false", "max_retries=0", "headless=true", "use_wandb=false",
        f"num_envs={envs}", "num_gpus=1", "multi_gpu=false", f"seed={cell['seed']}",
        f"++algo.trl.num_total_batches={batches}", "++algo.trl.report_to=none", f"++callbacks.model_save.save_frequency={save}",
        f"++algo.config.rp0_enabled={'true' if rp0 else 'false'}", "++algo.config.rp0_mask_indices=[3,4]", "++algo.config.rp0_neutral_value=0.0",
        f"++env.config.a2_v23_rp0_enabled={'true' if rp0 else 'false'}", "++env.config.a2_v23_rp0_mask_indices=[3,4]", "++env.config.a2_v23_rp0_neutral_value=0.0",
        "++env.config.a2_v23_d1_sampler_enabled=false", "++env.config.a2_v24_f3_marginal_e1_enabled=true",
        "++env.config.a2_v24_f3_semantics_revision=R13_BEHAVIORAL",
        f"++env.config.a2_v24_f3_marginal_e1_training_seed={cell['seed']}", f"++env.config.a2_v24_f3_marginal_e1_bucket_seed={24050 + int(cell['seed'])}",
        f"++env.config.a2_v24_f3_marginal_e1_total_batches={batches}", f"++env.config.a2_v24_f3_marginal_e1_num_envs={envs}",
        "++env.config.a2_v24_f3_marginal_e1_confirmed_e2_enabled=false",
        "++v23_formal_launch=true", "++v23_initialization=warm_head_reset", "++v23_door_regime=D1", f"++v23_posture_mode={cell['posture']}",
        "++v24_f3_door_regime=DF1", "++v24_f3_candidate_buckets=[E0_SHAM,E1_BOUNDARY,NEAR_E2]", "++v24_f3_rescue_cap_nm=25.0", "++v24_f3_confirmed_e2_share=0.0",
    ]
    return {**dict(cell), "label": label, "num_envs": envs, "batches": batches, "output_dir": output, "command": command, "command_shell": shlex.join(command)}


def build_training_commands() -> dict[str, Any]:
    production = [_training_command(cell, smoke=False) for cell in CELLS]
    smoke = [_training_command(CELLS[index], smoke=True) for index in (0, 2)]
    return {
        "schema": "a2_piper_v24_r13_f3_prime_training_commands_v1",
        "status": "REGISTERED_NOT_EXECUTED",
        "production": production,
        "smoke": smoke,
        "gpu_assignment": {cell["cell"]: cell["gpu"] for cell in CELLS},
        "parallel_gpu_authority": "OWNER_AUTHORIZED_GPU0_3",
    }


def _eval_command(cell: Mapping[str, Any], checkpoint: str, *, sham: bool) -> dict[str, Any]:
    overlay = yaml.safe_load((REPO_ROOT / r13.CONFIG).read_text(encoding="utf-8"))
    base = {key: value for key, value in overlay["env"]["config"].items() if key.startswith("a2_v24_force_boundary_")}
    profile, cap, envs = ("F00", 40.0, 16) if sham else (BOUNDARY_PROFILE, TAU_BOUNDARY_NM, 32)
    scenarios = list(SCENARIOS if sham else BOUNDARY_SCENARIOS)
    kind = "sham" if sham else "boundary"
    output = f"{ROOT.relative_to(REPO_ROOT)}/post_training_eval/{cell['cell']}/{kind}"
    params = {"F00": (0.0, 0.0, 0.0), "P10": (10.0, 7.5, 0.0)}[profile]
    continuity = f"R13_F3_{kind.upper()}_EVAL"
    runtime = dict(base)
    runtime.update({
        "a2_v20_R2_evidence_enabled": False,
        "a2_v23_d1_sampler_enabled": False,
        "a2_v24_force_boundary_enabled": True,
        "a2_v24_force_boundary_mode": "P2_TELEMETRY",
        "a2_v24_force_boundary_friction_profile": profile,
        "a2_v24_force_boundary_runtime_mode": "BOUNDARY_RP0" if cell["posture"] == "RP0" else "BOUNDARY_FULL",
        "a2_v24_force_boundary_active_cap_nm": cap,
        "a2_v24_force_boundary_seed": cell["seed"],
        "a2_v24_force_boundary_scenario_ids": scenarios,
        "a2_v24_force_boundary_continuity_id": continuity if sham else "R13_F3_POST_TRAIN_BOUNDARY_EVAL",
        "a2_v24_force_boundary_runtime_export_path": f"{output}/P2_RUNTIME_ROWS.jsonl",
        "a2_v24_force_boundary_static_friction_nm": params[0],
        "a2_v24_force_boundary_dynamic_friction_nm": params[1],
        "a2_v24_force_boundary_viscous_friction_nm_s_per_rad": params[2],
        "a2_v24_force_boundary_e1_semantics_revision": "R13_DOMAIN_ESCALATION",
        "a2_v24_force_boundary_demand_floor_nm": 2.0,
        "a2_v24_force_boundary_capacity_floor_nm": 2.0,
        "a2_v24_f3_marginal_e1_enabled": False,
        "a2_v24_f3_marginal_e1_evidence_enabled": not sham,
    })
    if not sham:
        runtime.update({
            "a2_v24_f3_marginal_e1_condition": "R13_F3_PRIME_BEHAVIORAL",
            "a2_v24_f3_marginal_e1_cell": cell["cell"],
            "a2_v24_f3_marginal_e1_posture": cell["posture"],
            "a2_v24_f3_marginal_e1_training_seed": cell["seed"],
            "a2_v24_f3_marginal_e1_checkpoint_path": checkpoint,
            "a2_v24_f3_marginal_e1_checkpoint_id": "model_step_000500",
            "a2_v24_f3_marginal_e1_global_step": 500,
            "a2_v24_f3_marginal_e1_evidence_path": f"{output}/F3_EVIDENCE.json",
        })
    rp0 = cell["posture"] == "RP0"
    command = [
        "/home/baoquanc/anaconda3/envs/isaaclab/bin/python", "-m", "gr00t.rl.eval_agent_trl",
        f"++checkpoint={checkpoint}", "++checkpoint_load_mode=policy_only", "++auto_load_latest=false", "++headless=true",
        f"++num_envs={envs}", f"++seed={cell['seed']}", "++use_wandb=false", "++algo.trl.report_to=none",
        "++algo.config.eval.a2_v23_p06_policy_only=true", "++algo.config.eval.eval_num_envs_episodes=true", f"++algo.config.eval.num_eval_episodes={envs}",
        f"++algo.config.eval.a2_eval_p2_posture_axis={'rp0' if rp0 else 'none'}", "++simulator.config.cameras.enable_cameras=false", "++simulator.config.render_results=false",
        "++env.config.a2_base.enabled=true", "++algo.config.num_mini_batches=1", f"++eval_output_dir={output}",
    ]
    command.extend(f"++env.config.{key}={_hydra(value)}" for key, value in sorted(runtime.items()))
    command.extend([
        "++v24_schema=a2_piper_v24_p2_force_boundary_r13_behavioral_eval_v1", "++v24_plan_id=base_v24_r13_f3_behavioral_reentry",
        "++v24_runtime_mode=P2_TELEMETRY", f"++v24_checkpoint_provenance={checkpoint}", "++v24_checkpoint_load_mode=selected_policy_only",
        f"++v24_p2.checkpoint={checkpoint}", "++v24_p2.checkpoint_load_mode=selected_policy_only",
    ])
    return {**dict(cell), "kind": kind, "profile": profile, "cap_nm": cap, "num_envs": envs, "checkpoint": checkpoint, "output_dir": output, "command": command, "command_shell": shlex.join(command)}


def build_eval_commands(checkpoints: Mapping[str, str]) -> dict[str, Any]:
    if set(checkpoints) != {cell["cell"] for cell in CELLS}:
        raise ValueError("checkpoint mapping must cover exactly four F3-prime cells")
    commands = []
    for cell in CELLS:
        checkpoint = str(checkpoints[cell["cell"]])
        if not checkpoint.endswith(f"/{cell['cell']}/model_step_000500.pt") or not (REPO_ROOT / checkpoint).is_file():
            raise ValueError(f"invalid final checkpoint for {cell['cell']}: {checkpoint}")
        commands.extend((_eval_command(cell, checkpoint, sham=True), _eval_command(cell, checkpoint, sham=False)))
    return {
        "schema": "a2_piper_v24_r13_f3_prime_post_training_eval_commands_v1",
        "status": "REGISTERED_NOT_EXECUTED",
        "commands": commands,
        "rule16": "each final checkpoint runs F00/cap40 canonical16 before its P10/cap20 32-episode population",
    }


def _validate_sham(cell: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, float]]:
    if len(rows) != 16:
        raise ValueError(f"{cell['cell']} sham requires 16 rows")
    by_scenario = {row.get("scenario_id"): row for row in rows}
    if set(by_scenario) != set(SCENARIOS):
        raise ValueError(f"{cell['cell']} sham topology is not canonical16")
    stable = sum(row.get("stable_grasp") is True and row.get("window_stage_reach_valid") is True and row.get("window_selection_valid") is True for row in rows)
    parameters = sum(isinstance(row.get("parameter_vitals"), Mapping) for row in rows)
    if stable < 14 or parameters != 16 or any(row.get("profile") != "F00" or row.get("cap_nm") != 40.0 for row in rows):
        raise ValueError(f"{cell['cell']} Rule16 sham vital failed")
    progress = {scenario: _finite(row["progress_recovery_delta_rad"], name="sham progress") for scenario, row in by_scenario.items()}
    return {
        "schema": "a2_piper_v24_r13_f3_rule16_checkpoint_vital_v1",
        "status": "PASS_VALID_MEASUREMENT_ADMISSION",
        "cell": cell["cell"],
        "checkpoint": f"{TRAIN_ROOT}/production/{cell['cell']}/model_step_000500.pt",
        "stable_grasp_stage_valid": stable,
        "required": 14,
        "parameter_vitals": parameters,
        "episodes": 16,
    }, progress


def adjudicate() -> dict[str, Any]:
    registration = _json(ROOT / ARTIFACTS["registration"])
    all_rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    sham_receipts: dict[str, dict[str, Any]] = {}
    for cell in CELLS:
        base = ROOT / "post_training_eval" / cell["cell"]
        sham_rows = _rows(base / "sham/P2_RUNTIME_ROWS.jsonl")
        sham_receipt, sham_progress = _validate_sham(cell, sham_rows)
        sham_receipts[cell["cell"]] = sham_receipt
        evidence = _json(base / "boundary/F3_EVIDENCE.json")
        records = evidence.get("records")
        if evidence.get("schema") != "a2_piper_v24_r13_f3_behavioral_evidence_v1" or not isinstance(records, list) or len(records) != 32:
            raise ValueError(f"{cell['cell']} boundary evidence is not a complete 32-row population")
        identities: set[tuple[str, int]] = set()
        admitted = 0
        for raw in records:
            if raw.get("cell") != cell["cell"] or raw.get("posture") != cell["posture"] or raw.get("seed") != cell["seed"]:
                raise ValueError(f"{cell['cell']} evidence identity mismatch")
            if raw.get("profile") != BOUNDARY_PROFILE or raw.get("cap_nm") != TAU_BOUNDARY_NM or raw.get("candidate_bucket") != "E1_BOUNDARY":
                raise ValueError(f"{cell['cell']} evidence face mismatch")
            scenario, ordinal = raw.get("scenario_id"), raw.get("episode_ordinal")
            identity = (scenario, ordinal)
            if scenario not in SCENARIOS or ordinal not in (0, 1) or identity in identities:
                raise ValueError(f"{cell['cell']} evidence scenario/ordinal mismatch")
            identities.add(identity)
            expected_checkpoint = f"{TRAIN_ROOT}/production/{cell['cell']}/model_step_000500.pt"
            if raw.get("checkpoint_path") != expected_checkpoint or raw.get("checkpoint_id") != "model_step_000500" or raw.get("global_step") != 500:
                raise ValueError(f"{cell['cell']} evidence checkpoint provenance mismatch")
            if raw.get("runtime_generated") is not True or raw.get("runtime_producer") != "R13F3EvidenceExporter" or raw.get("confirmed_e2") is not False:
                raise ValueError(f"{cell['cell']} runtime provenance mismatch")
            deficit = sham_progress[scenario] - _finite(raw["progress_recovery_delta_rad"], name="boundary progress")
            clip = _finite(raw["directional_clip_fraction_median"], name="clip fraction")
            utilization = _finite(raw["directional_utilization_median"], name="utilization")
            zone = _classify(deficit=deficit, clip_fraction=clip, utilization=utilization, valid=_source_valid(raw))
            admitted += zone == "E1"
            item = dict(raw)
            item.update({"behavioral_deficit_rad": deficit, "behavioral_zone": zone, "admitted_sustained_e1": zone == "E1", "capacity_lambda_admission_used": False})
            all_rows.append(item)
        if identities != {(scenario, ordinal) for ordinal in (0, 1) for scenario in SCENARIOS}:
            raise ValueError(f"{cell['cell']} boundary topology incomplete")
        counts[cell["cell"]] = admitted
    sufficient = all(value >= 8 for value in counts.values())
    status = "PILOT_COMPLETE_VALID" if sufficient else "V24_E1_DENOMINATOR_INSUFFICIENT_FINAL"
    payload = {
        "schema": "a2_piper_v24_r13_f3_prime_behavioral_adjudication_v1",
        "status": status,
        "terminal": not sufficient,
        "p3_admitted": sufficient,
        "typed_results": ["V24_E1_BOUNDARY_ESTABLISHED_BEHAVIORAL"] if sufficient else [status],
        "admitted_sustained_e1_per_cell": counts,
        "required_per_cell": 8,
        "episodes_per_cell": 32,
        "rule16_checkpoint_vitals": sham_receipts,
        "classifier": registration["classifier"],
        "owner_decision": registration["owner_decision"],
    }
    _write_rows(ARTIFACTS["population"], all_rows)
    _write_json(ARTIFACTS["adjudication"], payload)
    _write_json(ARTIFACTS["finalization"], {
        "schema": "a2_piper_v24_r13_f3_prime_finalization_v1",
        "status": "POST_F3_PRIME_FINALIZED",
        "pilot_status": status,
        "terminal": not sufficient,
        "p3_admitted": sufficient,
        "next_stage": "P3_HISTORICAL_ZERO_SAMPLE_SCAN" if sufficient else "OWNER_ESCALATION_FINAL_E1_DENOMINATOR",
        "no_further_gate_revision": not sufficient,
    })
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("self_check", "freeze", "post_eval_commands", "adjudicate"))
    parser.add_argument("--checkpoints")
    args = parser.parse_args(argv)
    if args.mode == "self_check":
        freezes = build_freezes()
        commands = build_training_commands()
        print(json.dumps({"status": "PASS", "typed": freezes["gradient"]["status"], "boundary": freezes["ladder"]["boundary_face"], "production_cells": len(commands["production"])}))
    elif args.mode == "freeze":
        freezes = build_freezes()
        for key in ("gradient", "ladder", "e_region", "registration"):
            _write_json(ARTIFACTS[key], freezes[key])
        _write_json(ARTIFACTS["training_commands"], build_training_commands())
        print(ROOT)
    elif args.mode == "post_eval_commands":
        if not args.checkpoints:
            parser.error("--checkpoints is required")
        checkpoints = _json(Path(args.checkpoints))
        _write_json(ARTIFACTS["checkpoints"], checkpoints)
        _write_json(ARTIFACTS["eval_commands"], build_eval_commands(checkpoints))
        print(ROOT / ARTIFACTS["eval_commands"])
    else:
        print(json.dumps(adjudicate(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
