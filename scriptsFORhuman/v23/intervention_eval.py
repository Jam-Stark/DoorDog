"""Selected-checkpoint Route-B P0.8-v2 forward-intervention evaluator.

Five modes use the real P0.8-v2 environment hooks on canonical16.  The
records explicitly remain forward-only: this module does not claim exact
PhysX state cloning, recurrent-state restoration, causal effects, or physical
torque changes.  A runtime job is complete only when its raw observed
canonical16 evidence is complete; outcome adjudication remains pending.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        REPO_ROOT,
        V23_INTERVENTION_MODES,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )
    from .pooled48 import (
        POOLED48_RECEIPT_PATH,
        POOLED48_SCHEMA,
        POOLED48_STATUS,
        POOLED48_DIAGNOSTIC_REWARD_TERMS,
        PHYSICAL_GPU_DOMAIN,
        PHYSICAL_GPU_MAPPING_POLICY,
        _absolute as _pooled_absolute,
        _job_plan as _pooled_job_plan,
        canonical_candidate_ordinal,
        physical_gpu_for_ordinal,
        validate_physical_gpus,
        validate_selected_candidates,
    )
    from .stratified_eval import STRATIFIED_RECEIPT_PATH, STRATIFIED_SCHEMA, STRATIFIED_STATUS
except ImportError:  # direct ``python scriptsFORhuman/v23/intervention_eval.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_INTERVENTION_MODES,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )
    from scriptsFORhuman.v23.pooled48 import (
        POOLED48_RECEIPT_PATH,
        POOLED48_SCHEMA,
        POOLED48_STATUS,
        POOLED48_DIAGNOSTIC_REWARD_TERMS,
        PHYSICAL_GPU_DOMAIN,
        PHYSICAL_GPU_MAPPING_POLICY,
        _absolute as _pooled_absolute,
        _job_plan as _pooled_job_plan,
        canonical_candidate_ordinal,
        physical_gpu_for_ordinal,
        validate_physical_gpus,
        validate_selected_candidates,
    )
    from scriptsFORhuman.v23.stratified_eval import STRATIFIED_RECEIPT_PATH, STRATIFIED_SCHEMA, STRATIFIED_STATUS


PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
INTERVENTION_SCHEMA = "a2_piper_v23_intervention_record_v1"
INTERVENTION_JOB_SCHEMA = "a2_piper_v23_intervention_job_receipt_v1"
INTERVENTION_JOB_STATUS = "V23_INTERVENTION_JOB_COMPLETE"
INTERVENTION_PLAN_SCHEMA = "a2_piper_v23_intervention_plan_v1"
INTERVENTION_RECEIPT_SCHEMA = "a2_piper_v23_intervention_eval_receipt_v1"
INTERVENTION_RECEIPT_STATUS = "V23_INTERVENTION_EVAL_COMPLETE"
INTERVENTION_ROOT = REPO_ROOT / "logs_eval/base_v23/interventions/R7_F8_NULL_LEGACY_MODE"
INTERVENTION_RECEIPT_PATH = INTERVENTION_ROOT / "V23_INTERVENTION_EVAL.json"
INTERVENTION_PLAN_PATH = INTERVENTION_ROOT / "V23_INTERVENTION_EVAL_PLAN.json"
INTERVENTION_TOPOLOGY = "canonical16"
INTERVENTION_NUM_ENVS = 16
INTERVENTION_EPISODES = 16
ROUTE_B_RAW_SCHEMA = "a2_piper_v23_route_b_p08_v2_raw_v1"

SWITCH_RULES = {
    "FULL": {"switch_event": "none", "posture_policy": "trained_policy"},
    "ACUTE_RP0": {"switch_event": "episode_start", "posture_policy": "rp0_distribution_mask"},
    "BASE0_AT_GRASP": {"switch_event": "stable_grasp_latch", "posture_policy": "base0_neutral"},
    "HIGHER_EFFORT_RESCUE": {"switch_event": "typed_failure_latch", "posture_policy": "higher_effort_forward_only"},
    "ORACLE_TANGENTIAL_ASSIST": {"switch_event": "typed_failure_latch", "posture_policy": "oracle_eval_only"},
}
ORACLE_DELTA_ROW = [0.0, 0.0, 0.0, 0.05, 0.05]


class InterventionEvalError(V23Error):
    """An intervention source, command, or receipt contract is invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    return _pooled_absolute(path)


def _load_any(path: str | Path) -> Any:
    target = _absolute(path)
    if target.is_symlink() or not target.is_file():
        raise InterventionEvalError(f"required intervention input is missing: {target}")
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InterventionEvalError(f"intervention input is not valid JSON: {target}") from exc


def _load_object(path: str | Path) -> dict[str, Any]:
    value = _load_any(path)
    if not isinstance(value, dict):
        raise InterventionEvalError(f"intervention input must be an object: {_absolute(path)}")
    return value


def _load_upstream(
    *,
    pooled_receipt: str | Path = POOLED48_RECEIPT_PATH,
    stratified_receipt: str | Path = STRATIFIED_RECEIPT_PATH,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    pooled = _load_object(pooled_receipt)
    stratified = _load_object(stratified_receipt)
    if pooled.get("schema") != POOLED48_SCHEMA or pooled.get("status") != POOLED48_STATUS:
        raise InterventionEvalError(f"pooled48 upstream receipt is not complete: {_absolute(pooled_receipt)}")
    if stratified.get("schema") != STRATIFIED_SCHEMA or stratified.get("status") != STRATIFIED_STATUS:
        raise InterventionEvalError(f"stratified upstream receipt is not complete: {_absolute(stratified_receipt)}")
    if pooled.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN):
        raise InterventionEvalError("pooled48 upstream physical_gpu_domain is not exactly 0..7")
    pooled_gpus = validate_physical_gpus(pooled.get("physical_gpus"))
    if pooled.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise InterventionEvalError("pooled48 upstream physical GPU mapping policy is unsupported")
    if stratified.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN):
        raise InterventionEvalError("stratified upstream physical_gpu_domain is not exactly 0..7")
    if validate_physical_gpus(stratified.get("physical_gpus")) != pooled_gpus:
        raise InterventionEvalError("stratified GPU provenance does not match pooled48")
    pooled_selected = validate_selected_candidates(pooled.get("selected_candidates"), require_sources=False)
    stratified_selected = validate_selected_candidates(stratified.get("selected_candidates"), require_sources=False)
    if pooled_selected != stratified_selected:
        raise InterventionEvalError("stratified selected_candidates do not exactly match pooled48")
    return pooled, stratified, pooled_selected


def _candidate_root(candidate: Mapping[str, Any], mode: str) -> Path:
    return (
        INTERVENTION_ROOT
        / f"seed{candidate['seed']}"
        / str(candidate["cell"])
        / f"step{int(candidate['step']):04d}"
        / mode
        / INTERVENTION_TOPOLOGY
    )


def _oracle_matrix() -> list[list[float]]:
    return [list(ORACLE_DELTA_ROW) for _ in range(INTERVENTION_NUM_ENVS)]


def _command(candidate: Mapping[str, Any], mode: str, output: Path, *, physical_gpu: int) -> list[str]:
    if mode not in V23_INTERVENTION_MODES:
        raise InterventionEvalError(f"unsupported v23 intervention mode: {mode!r}")
    if physical_gpu not in PHYSICAL_GPU_DOMAIN:
        raise InterventionEvalError(f"selected candidate maps to illegal physical GPU {physical_gpu}")
    command = [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={candidate['checkpoint_path']}",
        "++checkpoint_load_mode=policy_only",
        "++algo.config.eval.a2_v23_p06_policy_only=true",
        "++auto_load_latest=false",
        "++headless=true",
        f"++num_envs={INTERVENTION_NUM_ENVS}",
        "++num_gpus=1",
        "++multi_gpu=false",
        f"++seed={candidate['seed']}",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++algo.config.eval.num_eval_episodes={INTERVENTION_EPISODES}",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++algo.config.eval.a2_diagnostic_reward_terms=["
        + ",".join(POOLED48_DIAGNOSTIC_REWARD_TERMS)
        + "]",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++algo.config.num_mini_batches=1",
        "++env.config.a2_v23_route_a_unsafe_contact_enabled=false",
        "++algo.config.eval.a2_v23_route_a_unsafe_contact_export=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++algo.config.eval.a2_v23_p05_runtime_export=false",
        "++algo.config.eval.a2_v23_p08_state_bank_export=false",
        "++algo.config.eval.a2_v23_p08_v2_export=true",
        "++env.config.a2_v23_d1_sampler_enabled=false",
        "++env.config.a2_v23_p05_runtime_enabled=false",
        "++env.config.a2_v23_forward_intervention_mode=null",
        "++env.config.a2_v23_p08_v2_enabled=true",
        "++env.config.a2_v23_route_b_p08_v2_enabled=true",
        f"++env.config.a2_v23_p08_v2_mode={mode}",
        f"++env.config.a2_v23_p08_v2_checkpoint={candidate['checkpoint_path']}",
        f"++env.config.a2_v23_p08_v2_config_id={candidate['config_path']}",
        f"++env.config.a2_v23_p08_v2_scenario_id={candidate['scenario_path']}",
        f"++env.config.a2_v23_p08_v2_seed={candidate['seed']}",
        "++env.config.a2_v23_p08_v2_low_progress_min_rad=0.02",
        "++env.config.a2_v23_p08_v2_low_progress_max_rad=0.04",
        "++env.config.a2_v23_p08_v2_low_progress_window_min_steps=25",
        "++env.config.a2_v23_p08_v2_low_progress_window_max_steps=40",
        "++env.config.a2_v23_p08_v2_stable_grasp_min_steps=20",
        "++env.config.a2_v23_p08_v2_clipped_utilization_min=0.9",
        "++env.config.a2_v23_p08_v2_clipped_fraction_min=0.3",
        "++env.config.a2_v23_p08_v2_rescue_effort_limit_nm=100.0",
        f"++eval_output_dir={output}",
        "++v23_route_b_topology=canonical16_intervention",
        f"++v23_route_b_candidate_subwave={candidate['subwave']}",
        f"++v23_route_b_candidate_cell={candidate['cell']}",
        f"++v23_route_b_candidate_step={candidate['step']}",
        f"++v23_route_b_intervention_mode={mode}",
        f"++v23_route_b_scenario_path={candidate['scenario_path']}",
        "++env.config.a2_v23_warm_head_reset_enabled=false",
        "++env.config.a2_v23_formal_launch=false",
    ]
    if mode == "ORACLE_TANGENTIAL_ASSIST":
        command.append(
            "++env.config.a2_v23_p08_v2_oracle_tangential_delta_raw="
            + json.dumps(_oracle_matrix(), separators=(",", ":"))
        )
    else:
        command.append("++env.config.a2_v23_p08_v2_oracle_tangential_delta_raw=null")
    return command


def _job_plan(
    candidate: Mapping[str, Any],
    mode: str,
    *,
    physical_gpus: Sequence[int] | str | None = None,
    job_ordinal: int | None = None,
    physical_gpu: int | None = None,
) -> dict[str, Any]:
    output = _candidate_root(candidate, mode)
    selected_gpus = validate_physical_gpus(physical_gpus)
    candidate_ordinal = canonical_candidate_ordinal(candidate)
    mode_ordinal = V23_INTERVENTION_MODES.index(mode)
    ordinal = candidate_ordinal * len(V23_INTERVENTION_MODES) + mode_ordinal if job_ordinal is None else job_ordinal
    mapped_gpu = physical_gpu_for_ordinal(ordinal, selected_gpus)
    if physical_gpu is not None:
        if isinstance(physical_gpu, bool) or not isinstance(physical_gpu, int):
            raise InterventionEvalError("manifest physical_gpu must be an integer")
        if physical_gpu != mapped_gpu:
            raise InterventionEvalError(
                f"manifest physical_gpu {physical_gpu} disagrees with canonical ordinal {ordinal}"
            )
        mapped_gpu = physical_gpu
    return {
        "job_id": f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}:{mode}",
        "job_ordinal": ordinal,
        "schema": INTERVENTION_JOB_SCHEMA,
        "source_branch": candidate["source_branch"],
        "plan_id": candidate["plan_id"],
        "identity_policy": candidate["identity_policy"],
        "selected_candidate": dict(candidate),
        "mode": mode,
        "switch_rule": dict(SWITCH_RULES[mode]),
        "topology": INTERVENTION_TOPOLOGY,
        "num_envs": INTERVENTION_NUM_ENVS,
        "episodes": INTERVENTION_EPISODES,
        "physical_gpu": mapped_gpu,
        "logical_gpu": "cuda:0",
        "checkpoint_load_mode": "policy_only",
        "num_mini_batches": 1,
        "retry_count": 0,
        "no_retry": True,
        "forward_only": True,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "actual_torque_claim": False,
        "evaluation_root": str(output),
        "records_path": str(output / "a2_v23_p08_v2_raw.json"),
        "raw_trace_path": str(output / "stage2_step_trace.json"),
        "metrics_path": str(output / "metrics_eval.json"),
        "run_receipt_path": str(output / "run_receipt.json"),
        "intervention_records_path": str(output / "intervention_records.json"),
        "contact_evidence": "NOT_EXPORTED_UNSUPPORTED_FOR_ROUTE_B_INTERVENTION",
        "command": _command(candidate, mode, output, physical_gpu=mapped_gpu),
        "environment": {
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_VISIBLE_DEVICES": str(mapped_gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "WANDB_MODE": "disabled",
        },
    }


def build_plan(
    *,
    pooled_receipt: str | Path = POOLED48_RECEIPT_PATH,
    stratified_receipt: str | Path = STRATIFIED_RECEIPT_PATH,
    physical_gpus: Sequence[int] | str | None = None,
    output: str | Path | None = None,
) -> dict[str, Any]:
    _pooled, _stratified, selected = _load_upstream(
        pooled_receipt=pooled_receipt,
        stratified_receipt=stratified_receipt,
    )
    upstream_gpus = validate_physical_gpus(_pooled["physical_gpus"])
    selected_gpus = validate_physical_gpus(physical_gpus) if physical_gpus is not None else upstream_gpus
    if selected_gpus != upstream_gpus:
        raise InterventionEvalError("intervention physical GPU mapping must match pooled48 provenance exactly")
    jobs: list[dict[str, Any]] = []
    for candidate in selected:
        for mode in V23_INTERVENTION_MODES:
            ordinal = len(jobs)
            jobs.append(
                _job_plan(
                    candidate,
                    mode,
                    physical_gpus=selected_gpus,
                    job_ordinal=ordinal,
                )
            )
    if len(jobs) != 80:
        raise InterventionEvalError("intervention plan must contain exactly 16*5=80 jobs")
    payload = {
        "schema": INTERVENTION_PLAN_SCHEMA,
        "status": "BUILT",
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "stage": "INTERVENTIONS",
        "selected_candidates": selected,
        "selected_candidate_count": len(selected),
        "modes": list(V23_INTERVENTION_MODES),
        "topology": INTERVENTION_TOPOLOGY,
        "num_envs": INTERVENTION_NUM_ENVS,
        "episodes_per_job": INTERVENTION_EPISODES,
        "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
        "physical_gpus": list(selected_gpus),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "logical_gpu": "cuda:0",
        "num_mini_batches": 1,
        "jobs": jobs,
        "pooled_receipt_path": str(_absolute(pooled_receipt)),
        "stratified_receipt_path": str(_absolute(stratified_receipt)),
        "forward_only": True,
        "state_clone_supported": False,
        "actual_torque_claim": False,
        "outcome_status": "PENDING_RUNTIME_FORWARD_ADJUDICATION",
        "no_retry": True,
    }
    if output is not None:
        write_json(_absolute(output), payload)
    return payload


def _validate_manifest_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a persisted intervention plan before RUN or REDUCE."""

    if payload.get("schema") != INTERVENTION_PLAN_SCHEMA or payload.get("status") != "BUILT":
        raise InterventionEvalError("intervention manifest schema/status is not BUILT")
    for field in ("pooled_receipt_path", "stratified_receipt_path"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise InterventionEvalError(f"intervention manifest is missing {field} binding")
    if payload.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN):
        raise InterventionEvalError("intervention manifest physical_gpu_domain is not exactly 0..7")
    selected_gpus = validate_physical_gpus(payload.get("physical_gpus"))
    if payload.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise InterventionEvalError("intervention manifest physical GPU mapping policy is unsupported")
    if payload.get("modes") != list(V23_INTERVENTION_MODES):
        raise InterventionEvalError("intervention manifest mode order is not the exact five-mode suite")
    selected = validate_selected_candidates(payload.get("selected_candidates"), require_sources=False)
    jobs = payload.get("jobs")
    expected_count = len(selected) * len(V23_INTERVENTION_MODES)
    if not isinstance(jobs, list) or len(jobs) != expected_count:
        raise InterventionEvalError(f"intervention manifest must contain exactly {expected_count} jobs")
    normalized_jobs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    expected_pairs = [
        (candidate, mode)
        for candidate in selected
        for mode in V23_INTERVENTION_MODES
    ]
    for ordinal, (candidate, mode) in enumerate(expected_pairs):
        raw_job = jobs[ordinal]
        if not isinstance(raw_job, Mapping):
            raise InterventionEvalError(f"intervention manifest job {ordinal} must be an object")
        job = dict(raw_job)
        expected_id = f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}:{mode}"
        if job.get("job_id") != expected_id or job.get("job_ordinal") != ordinal:
            raise InterventionEvalError(f"intervention manifest job {ordinal} identity/order disagrees")
        if job.get("selected_candidate") != candidate or job.get("mode") != mode:
            raise InterventionEvalError(f"intervention manifest job {expected_id} identity disagrees")
        expected_gpu = physical_gpu_for_ordinal(ordinal, selected_gpus)
        if job.get("physical_gpu") != expected_gpu:
            raise InterventionEvalError(f"intervention manifest job {expected_id} physical_gpu disagrees")
        if job.get("logical_gpu") != "cuda:0":
            raise InterventionEvalError(f"intervention manifest job {expected_id} logical_gpu must be cuda:0")
        if job.get("checkpoint_load_mode") != "policy_only":
            raise InterventionEvalError(
                f"intervention manifest job {expected_id} checkpoint_load_mode must be policy_only"
            )
        environment = job.get("environment")
        if not isinstance(environment, Mapping) or environment.get("CUDA_VISIBLE_DEVICES") != str(expected_gpu):
            raise InterventionEvalError(f"intervention manifest job {expected_id} CUDA mask disagrees")
        command = job.get("command")
        required_command_flags = {
            "++checkpoint_load_mode=policy_only",
            "++algo.config.eval.a2_v23_p06_policy_only=true",
            "++algo.config.eval.a2_v23_p05_runtime_export=false",
            "++algo.config.eval.a2_v23_p08_state_bank_export=false",
            "++algo.config.eval.a2_v23_p08_v2_export=true",
            "++env.config.a2_v23_d1_sampler_enabled=false",
            "++env.config.a2_v23_p05_runtime_enabled=false",
            "++env.config.a2_v23_forward_intervention_mode=null",
            "++env.config.a2_v23_p08_v2_enabled=true",
            "++env.config.a2_v23_route_b_p08_v2_enabled=true",
            f"++env.config.a2_v23_p08_v2_mode={mode}",
        }
        if not isinstance(command, list) or not required_command_flags.issubset(command):
            raise InterventionEvalError(f"intervention manifest job {expected_id} does not use Route-B P0.8-v2 flags")
        if any(
            str(flag).startswith("++env.config.a2_v23_forward_intervention_mode=")
            and flag != "++env.config.a2_v23_forward_intervention_mode=null"
            for flag in command
        ):
            raise InterventionEvalError(f"intervention manifest job {expected_id} uses the legacy forward mode")
        if any("a2_v23_oracle_active_mask" in str(flag) for flag in command):
            raise InterventionEvalError(f"intervention manifest job {expected_id} uses a configured oracle active mask")
        if expected_id in seen_ids:
            raise InterventionEvalError(f"intervention manifest contains duplicate job {expected_id}")
        seen_ids.add(expected_id)
        normalized_jobs.append(job)
    normalized = dict(payload)
    normalized["selected_candidates"] = selected
    normalized["physical_gpus"] = list(selected_gpus)
    normalized["jobs"] = normalized_jobs
    return normalized


def load_plan(path: str | Path = INTERVENTION_PLAN_PATH) -> dict[str, Any]:
    return _validate_manifest_plan(_load_object(path))


def _resolve_persisted_upstream_bindings(
    plan_payload: Mapping[str, Any],
    *,
    pooled_receipt: str | Path | None,
    stratified_receipt: str | Path | None,
) -> tuple[str, str]:
    persisted_pooled = plan_payload.get("pooled_receipt_path")
    persisted_stratified = plan_payload.get("stratified_receipt_path")
    if not isinstance(persisted_pooled, str) or not persisted_pooled:
        raise InterventionEvalError("intervention manifest is missing pooled_receipt_path binding")
    if not isinstance(persisted_stratified, str) or not persisted_stratified:
        raise InterventionEvalError("intervention manifest is missing stratified_receipt_path binding")
    for name, supplied, persisted in (
        ("pooled48", pooled_receipt, persisted_pooled),
        ("stratified", stratified_receipt, persisted_stratified),
    ):
        if supplied is not None and _absolute(supplied) != _absolute(persisted):
            raise InterventionEvalError(
                f"intervention {name} path disagrees with the persisted plan binding: "
                f"{_absolute(supplied)} != {_absolute(persisted)}"
            )
    return persisted_pooled, persisted_stratified


def _validate_route_b_observed_record(
    row: Mapping[str, Any], *, mode: str, env_id: int
) -> None:
    if row.get("schema") != "a2_piper_v23_p08_preformal_v2_raw_v1":
        raise InterventionEvalError(f"Route-B env {env_id} has an unsupported observed-record schema")
    if row.get("route") != "B" or row.get("topology") != INTERVENTION_TOPOLOGY:
        raise InterventionEvalError(f"Route-B env {env_id} is missing canonical16 route provenance")
    if row.get("mode") != mode or row.get("env_id") != env_id or row.get("env_count") != INTERVENTION_NUM_ENVS:
        raise InterventionEvalError(f"Route-B env {env_id} identity/mode/topology evidence disagrees")
    if row.get("checkpoint_load_mode") != "policy_only":
        raise InterventionEvalError(f"Route-B env {env_id} checkpoint load mode is not policy_only")
    for field in ("checkpoint", "config", "scenario"):
        if not isinstance(row.get(field), str) or not row[field]:
            raise InterventionEvalError(f"Route-B env {env_id} is missing {field} provenance")
    if isinstance(row.get("seed"), bool) or not isinstance(row.get("seed"), int):
        raise InterventionEvalError(f"Route-B env {env_id} seed provenance is invalid")
    if row.get("state_clone_supported") is not False or row.get("recurrent_state_restore_supported") is not False:
        raise InterventionEvalError(f"Route-B env {env_id} cannot claim state restoration")
    if row.get("forward_only") is not True:
        raise InterventionEvalError(f"Route-B env {env_id} is not marked forward-only")
    excluded_claims = row.get("excluded_claims")
    if not isinstance(excluded_claims, list) or "NO_ROUTE_B_SUITE_EXECUTION" in excluded_claims:
        raise InterventionEvalError(f"Route-B env {env_id} has invalid exclusion claims")
    status = row.get("status")
    if status not in {"TRIGGERED", "NOT_TRIGGERED"}:
        raise InterventionEvalError(f"Route-B env {env_id} has an invalid trigger status")
    switch_step = row.get("switch_step")
    if isinstance(switch_step, bool) or not isinstance(switch_step, int):
        raise InterventionEvalError(f"Route-B env {env_id} switch_step must be an integer")
    if (status == "TRIGGERED") != (switch_step >= 0):
        raise InterventionEvalError(f"Route-B env {env_id} status/switch_step evidence disagrees")
    latch = row.get("observed_latch")
    if not isinstance(latch, Mapping) or not isinstance(latch.get("observed"), bool):
        raise InterventionEvalError(f"Route-B env {env_id} observed latch evidence is incomplete")
    if latch["observed"] != (status == "TRIGGERED"):
        raise InterventionEvalError(f"Route-B env {env_id} latch/status evidence disagrees")
    expected_events = {
        "FULL": "NO_SWITCH_BASELINE",
        "ACUTE_RP0": "EPISODE_START",
        "BASE0_AT_GRASP": "STABLE_GRASP_LATCH",
        "HIGHER_EFFORT_RESCUE": "TYPED_FAILURE_LATCH",
        "ORACLE_TANGENTIAL_ASSIST": "TYPED_FAILURE_LATCH",
    }
    if latch.get("event") != expected_events[mode]:
        raise InterventionEvalError(f"Route-B env {env_id} latch event disagrees with mode")
    if mode == "FULL" and (status != "NOT_TRIGGERED" or latch.get("step") != -1):
        raise InterventionEvalError(f"Route-B env {env_id} FULL must remain a no-switch baseline")
    action = row.get("action_proof")
    if not isinstance(action, Mapping):
        raise InterventionEvalError(f"Route-B env {env_id} action proof is missing")
    if action.get("switch_step") != switch_step or action.get("active") != (status == "TRIGGERED"):
        raise InterventionEvalError(f"Route-B env {env_id} action/switch evidence disagrees")
    for field, width in (("pre_action_5d", 5), ("post_action_5d", 5), ("post_indices_3_4", 2)):
        values = action.get(field)
        if (
            not isinstance(values, list)
            or len(values) != width
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values)
        ):
            raise InterventionEvalError(f"Route-B env {env_id} action proof field {field} is invalid")
    readback = row.get("mode_readback")
    if not isinstance(readback, Mapping):
        raise InterventionEvalError(f"Route-B env {env_id} mode readback is missing")
    if mode == "FULL":
        if readback.get("no_switch") is not True or readback.get("active_mask") != [False]:
            raise InterventionEvalError(f"Route-B env {env_id} FULL readback is not no-switch")
    elif mode in {"ACUTE_RP0", "BASE0_AT_GRASP"}:
        if not isinstance(readback.get("post_indices_3_4_zero"), bool):
            raise InterventionEvalError(f"Route-B env {env_id} neutral-action readback is missing")
        if status == "TRIGGERED" and readback.get("post_indices_3_4_zero") is not True:
            raise InterventionEvalError(f"Route-B env {env_id} trigger lacks neutral-action proof")
    elif mode == "HIGHER_EFFORT_RESCUE":
        if status == "TRIGGERED":
            applied = readback.get("applied_profile")
            readback_values = applied.get("readback_effort_limit_nm") if isinstance(applied, Mapping) else None
            if (
                readback.get("effort_readback_status") != "APPLIED"
                or not isinstance(readback_values, list)
                or len(readback_values) != 6
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in readback_values)
            ):
                raise InterventionEvalError(f"Route-B env {env_id} lacks high-level effort-limit readback")
    else:
        active_mask = readback.get("active_mask")
        delta = readback.get("delta_raw")
        if not isinstance(active_mask, list) or active_mask != [status == "TRIGGERED"]:
            raise InterventionEvalError(f"Route-B env {env_id} oracle active-mask evidence is invalid")
        if (
            not isinstance(delta, list)
            or len(delta) != INTERVENTION_NUM_ENVS
            or any(
                not isinstance(values, list)
                or len(values) != 5
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values)
                for values in delta
            )
        ):
            raise InterventionEvalError(f"Route-B env {env_id} oracle delta evidence is invalid")
        if status == "TRIGGERED" and readback.get("post_equals_pre_plus_delta") is not True:
            raise InterventionEvalError(f"Route-B env {env_id} oracle action proof is missing")


def _validate_runtime_files(job: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[Any], dict[str, Any]]:
    root = _absolute(job["evaluation_root"])
    payload = _load_object(job["records_path"])
    if payload.get("schema") != ROUTE_B_RAW_SCHEMA or payload.get("status") != "RUNTIME_VERIFIED":
        raise InterventionEvalError(f"Route-B raw observed payload is not runtime-verified: {root}")
    if (
        payload.get("route") != "B"
        or payload.get("topology") != INTERVENTION_TOPOLOGY
        or payload.get("num_envs") != INTERVENTION_NUM_ENVS
        or payload.get("process_count") != 1
        or payload.get("logical_gpu") != "cuda:0"
        or payload.get("physical_gpu") != str(job["physical_gpu"])
        or job.get("checkpoint_load_mode") != "policy_only"
    ):
        raise InterventionEvalError(f"Route-B raw observed payload provenance disagrees: {root}")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != INTERVENTION_NUM_ENVS:
        raise InterventionEvalError(f"Route-B raw observed payload must contain exactly 16 rows: {root}")
    mode = job["mode"]
    for expected_env_id, row in enumerate(records):
        if not isinstance(row, Mapping):
            raise InterventionEvalError(f"Route-B raw observed env {expected_env_id} is not an object: {root}")
        _validate_route_b_observed_record(row, mode=mode, env_id=expected_env_id)
        if row.get("checkpoint_load_mode") != job["checkpoint_load_mode"]:
            raise InterventionEvalError(
                f"Route-B raw observed env {expected_env_id} checkpoint load mode disagrees: {root}"
            )
    if payload.get("excluded_claims") and "NO_ROUTE_B_SUITE_EXECUTION" in payload["excluded_claims"]:
        raise InterventionEvalError(f"Route-B raw observed payload carries an invalid exclusion claim: {root}")
    trace_path = _absolute(job["raw_trace_path"])
    trace = _load_any(trace_path) if trace_path.is_file() and not trace_path.is_symlink() else []
    if trace and not isinstance(trace, list):
        raise InterventionEvalError(f"intervention raw trace must be a list when present: {root}")
    metrics = _load_any(job["metrics_path"])
    if not isinstance(metrics, Mapping) or metrics.get("completed_episodes") != INTERVENTION_EPISODES:
        raise InterventionEvalError(f"intervention metrics must report completed_episodes=16: {root}")
    return [dict(row) for row in records], trace, dict(metrics)


def _records_for_job(job: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "schema": INTERVENTION_SCHEMA,
            "source_branch": job["source_branch"],
            "plan_id": job["plan_id"],
            "identity_policy": job["identity_policy"],
            "selected_candidate": dict(job["selected_candidate"]),
            "mode": job["mode"],
            "switch_rule": dict(job["switch_rule"]),
            "env_id": row["env_id"],
            "checkpoint_load_mode": row["checkpoint_load_mode"],
            "observed_record": dict(row),
            "status": row["status"],
            "switch_step": row["switch_step"],
            "observed_latch": dict(row["observed_latch"]),
            "action_proof": dict(row["action_proof"]),
            "mode_readback": dict(row["mode_readback"]),
            "forward_only": row["forward_only"],
            "state_clone_supported": row["state_clone_supported"],
            "recurrent_state_restore_supported": row["recurrent_state_restore_supported"],
            "actual_torque_claim": False,
            "outcome": "PENDING_RUNTIME_FORWARD_ADJUDICATION",
            "missing_evidence": ["outcome_adjudication_deferred"],
        }
        for row in records
    ]


def _run_one(job: Mapping[str, Any]) -> dict[str, Any]:
    physical_gpu = job.get("physical_gpu")
    if isinstance(physical_gpu, bool) or not isinstance(physical_gpu, int) or physical_gpu not in PHYSICAL_GPU_DOMAIN:
        raise InterventionEvalError(f"intervention job {job.get('job_id')} has an invalid manifest physical_gpu")
    environment = job.get("environment")
    if not isinstance(environment, Mapping) or environment.get("CUDA_VISIBLE_DEVICES") != str(physical_gpu):
        raise InterventionEvalError(f"intervention job {job.get('job_id')} CUDA mask is not manifest-assigned")
    root = _absolute(job["evaluation_root"])
    receipt_path = root / "run_receipt.json"
    if root.exists():
        if receipt_path.is_file() and not receipt_path.is_symlink():
            raise InterventionEvalError(f"intervention output already exists; refusing resume: {root}")
        raise InterventionEvalError(f"intervention output exists without sealed receipt: {root}")
    root.mkdir(parents=True, exist_ok=False)
    stdout_path = root / "runtime_stdout.log"
    stderr_path = root / "runtime_stderr.log"
    env = os.environ.copy()
    env.update(job["environment"])
    started = _now()
    with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen(job["command"], cwd=REPO_ROOT, env=env, stdout=stdout, stderr=stderr)
        return_code = process.wait()
    ended = _now()
    if return_code != 0:
        raise InterventionEvalError(f"intervention job {job['job_id']} exited {return_code}; no retry")
    records, trace, metrics = _validate_runtime_files(job)
    intervention_records = _records_for_job(job, records)
    write_json(_absolute(job["intervention_records_path"]), {"schema": INTERVENTION_SCHEMA, "records": intervention_records})
    receipt = {
        "schema": INTERVENTION_JOB_SCHEMA,
        "status": INTERVENTION_JOB_STATUS,
        "recorded_at_utc": _now(),
        "job_id": job["job_id"],
        "job_ordinal": job["job_ordinal"],
        "source_branch": job["source_branch"],
        "plan_id": job["plan_id"],
        "identity_policy": job["identity_policy"],
        "selected_candidate": dict(job["selected_candidate"]),
        "mode": job["mode"],
        "switch_rule": dict(job["switch_rule"]),
        "topology": INTERVENTION_TOPOLOGY,
        "num_envs": INTERVENTION_NUM_ENVS,
        "episode_record_count": len(records),
        "trace_row_count": len(trace),
        "trace_env_ids": sorted({row["env_id"] for row in trace if isinstance(row, Mapping)}),
        "metrics_completed_episodes": metrics["completed_episodes"],
        "physical_gpu": job["physical_gpu"],
        "logical_gpu": "cuda:0",
        "checkpoint_load_mode": job["checkpoint_load_mode"],
        "num_mini_batches": 1,
        "retry_count": 0,
        "natural_completion": True,
        "forward_only": True,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "actual_torque_claim": False,
        "contact_evidence": job["contact_evidence"],
        "outcome_status": "PENDING_RUNTIME_FORWARD_ADJUDICATION",
        "missing_evidence": ["outcome_adjudication_deferred", "unsafe_contacts_not_exported_for_route_b_intervention"],
        "process": {
            "pid": process.pid,
            "started_at_utc": started,
            "ended_at_utc": ended,
            "return_code": return_code,
        },
        "records_path": job["records_path"],
        "raw_trace_path": job["raw_trace_path"],
        "metrics_path": job["metrics_path"],
        "intervention_records_path": job["intervention_records_path"],
    }
    write_json(receipt_path, receipt)
    return receipt


def run(
    *,
    pooled_receipt: str | Path | None = None,
    stratified_receipt: str | Path | None = None,
    only_job: str | None = None,
    plan_path: str | Path | None = None,
    physical_gpus: Sequence[int] | str | None = None,
) -> dict[str, Any]:
    if physical_gpus is not None:
        raise InterventionEvalError("RUN consumes the persisted plan and rejects physical_gpus")
    if plan_path is None:
        raise InterventionEvalError("RUN requires a persisted plan_path")
    plan = load_plan(plan_path)
    _resolve_persisted_upstream_bindings(
        plan,
        pooled_receipt=pooled_receipt,
        stratified_receipt=stratified_receipt,
    )
    jobs = []
    for job in plan["jobs"]:
        if only_job is not None and job["job_id"] != only_job:
            continue
        _run_one(job)
        jobs.append(job["job_id"])
    if only_job is not None and not jobs:
        raise InterventionEvalError(f"unknown intervention job: {only_job}")
    return {
        "schema": "a2_piper_v23_intervention_run_result_v1",
        "status": "PASS",
        "recorded_at_utc": _now(),
        "job_count": len(jobs),
        "completed_jobs": jobs,
        "modes": list(V23_INTERVENTION_MODES),
        "no_retry": True,
    }


def _load_job_receipt(
    path: Path,
    *,
    candidate: Mapping[str, Any],
    mode: str,
    expected_physical_gpu: int,
    expected_job_ordinal: int,
) -> dict[str, Any]:
    receipt = _load_object(path)
    if receipt.get("schema") != INTERVENTION_JOB_SCHEMA or receipt.get("status") != INTERVENTION_JOB_STATUS:
        raise InterventionEvalError(f"intervention job receipt is incomplete: {path}")
    if receipt.get("selected_candidate") != dict(candidate) or receipt.get("mode") != mode:
        raise InterventionEvalError(f"intervention job identity disagrees: {path}")
    for field, expected in (
        ("topology", INTERVENTION_TOPOLOGY),
        ("num_envs", INTERVENTION_NUM_ENVS),
        ("episode_record_count", INTERVENTION_NUM_ENVS),
        ("metrics_completed_episodes", INTERVENTION_EPISODES),
        ("physical_gpu", expected_physical_gpu),
        ("checkpoint_load_mode", "policy_only"),
        ("job_ordinal", expected_job_ordinal),
        ("logical_gpu", "cuda:0"),
        ("num_mini_batches", 1),
        ("retry_count", 0),
        ("natural_completion", True),
        ("forward_only", True),
        ("state_clone_supported", False),
        ("recurrent_state_restore_supported", False),
        ("actual_torque_claim", False),
    ):
        if receipt.get(field) != expected:
            raise InterventionEvalError(f"intervention job receipt {path} field {field} disagrees")
    return receipt


def reduce(
    *,
    pooled_receipt: str | Path | None = None,
    stratified_receipt: str | Path | None = None,
    output: str | Path = INTERVENTION_RECEIPT_PATH,
    plan_path: str | Path | None = None,
    physical_gpus: Sequence[int] | str | None = None,
) -> dict[str, Any]:
    if physical_gpus is not None:
        raise InterventionEvalError("REDUCE consumes the persisted plan and rejects physical_gpus")
    if plan_path is None:
        raise InterventionEvalError("REDUCE requires a persisted plan_path")
    plan_payload = load_plan(plan_path)
    persisted_pooled, persisted_stratified = _resolve_persisted_upstream_bindings(
        plan_payload,
        pooled_receipt=pooled_receipt,
        stratified_receipt=stratified_receipt,
    )
    _pooled, _stratified, selected = _load_upstream(
        pooled_receipt=persisted_pooled,
        stratified_receipt=persisted_stratified,
    )
    if _pooled.get("selected_candidates") != selected or _stratified.get("selected_candidates") != selected:
        raise InterventionEvalError("intervention manifest selected_candidates disagree with upstream")
    jobs: list[dict[str, Any]] = []
    for ordinal, manifest_job in enumerate(plan_payload["jobs"]):
        candidate = manifest_job["selected_candidate"]
        mode = manifest_job["mode"]
        receipt_path = _absolute(manifest_job["run_receipt_path"])
        receipt = _load_job_receipt(
            receipt_path,
            candidate=candidate,
            mode=mode,
            expected_physical_gpu=manifest_job["physical_gpu"],
            expected_job_ordinal=ordinal,
        )
        raw_records, _trace, _metrics = _validate_runtime_files(manifest_job)
        observed_records = _records_for_job(manifest_job, raw_records)
        jobs.append(
            {
                "job_id": receipt["job_id"],
                "job_ordinal": ordinal,
                "selected_candidate": dict(candidate),
                "mode": mode,
                "receipt_path": str(receipt_path),
                "topology": receipt["topology"],
                "episode_record_count": receipt["episode_record_count"],
                "triggered_episode_count": sum(
                    record["status"] == "TRIGGERED" for record in observed_records
                ),
                "not_triggered_episode_count": sum(
                    record["status"] == "NOT_TRIGGERED" for record in observed_records
                ),
                "outcome_status": receipt["outcome_status"],
                "forward_only": receipt["forward_only"],
                "state_clone_supported": receipt["state_clone_supported"],
                "actual_torque_claim": receipt["actual_torque_claim"],
                "physical_gpu": receipt["physical_gpu"],
                "missing_evidence": list(receipt["missing_evidence"]),
            }
        )
    if len(jobs) != 80:
        raise InterventionEvalError("intervention reduction requires exactly 80 complete jobs")
    if {job["mode"] for job in jobs} != set(V23_INTERVENTION_MODES):
        raise InterventionEvalError("intervention reduction did not cover all five modes")
    payload = {
        "schema": INTERVENTION_RECEIPT_SCHEMA,
        "status": INTERVENTION_RECEIPT_STATUS,
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "stage": "INTERVENTIONS",
        "topology": INTERVENTION_TOPOLOGY,
        "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
        "physical_gpus": list(plan_payload["physical_gpus"]),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "logical_gpu": "cuda:0",
        "num_mini_batches": 1,
        "modes": list(V23_INTERVENTION_MODES),
        "selected_candidates": selected,
        "candidate_count": len(selected),
        "job_count": len(jobs),
        "episode_record_count": len(jobs) * INTERVENTION_NUM_ENVS,
        "forward_only": True,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "actual_torque_claim": False,
        "outcome_status": "PENDING_RUNTIME_FORWARD_ADJUDICATION",
        "jobs": jobs,
        "missing_evidence": ["outcome_adjudication_deferred", "unsafe_contacts_not_exported_for_route_b_intervention"],
        "no_retry": True,
    }
    write_json(_absolute(output), payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "BUILD", "RUN", "REDUCE"), required=True)
    parser.add_argument("--pooled48", type=Path, default=None)
    parser.add_argument("--stratified", type=Path, default=None)
    parser.add_argument("--job", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--plan", type=Path, default=INTERVENTION_PLAN_PATH)
    parser.add_argument(
        "--physical-gpus",
        type=lambda value: validate_physical_gpus(value),
        default=None,
        help="ordered unique local physical GPU ids, subset of 0..7; PLAN/BUILD only",
    )
    args = parser.parse_args(argv)
    try:
        if args.mode not in {"PLAN", "BUILD"} and args.physical_gpus is not None:
            raise InterventionEvalError("--physical-gpus is valid only for PLAN and BUILD")
        if args.mode in {"PLAN", "BUILD"}:
            payload = build_plan(
                pooled_receipt=args.pooled48 or POOLED48_RECEIPT_PATH,
                stratified_receipt=args.stratified or STRATIFIED_RECEIPT_PATH,
                physical_gpus=args.physical_gpus,
                output=args.output if args.mode == "BUILD" else None,
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        elif args.mode == "RUN":
            payload = run(
                pooled_receipt=args.pooled48,
                stratified_receipt=args.stratified,
                only_job=args.job,
                plan_path=args.plan,
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            payload = reduce(
                pooled_receipt=args.pooled48,
                stratified_receipt=args.stratified,
                plan_path=args.plan,
                output=args.output or INTERVENTION_RECEIPT_PATH,
            )
            print(json.dumps({"status": "WRITTEN", "path": str(_absolute(args.output or INTERVENTION_RECEIPT_PATH))}, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 INTERVENTION_EVAL {args.mode} FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
