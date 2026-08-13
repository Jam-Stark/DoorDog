"""Route-B pooled48 evaluator for the selected Route-A checkpoints.

This module is intentionally a small, fail-fast orchestration layer.  It does
not select candidates, fill missing evidence, or infer a contact label.  The
only candidate identities it accepts are the four frozen Route-A selections;
the same canonical list is copied into every Route-B producer receipt.

``PLAN`` and ``BUILD`` are source/plan operations.  ``RUN`` launches one
foreground evaluator per selected checkpoint (48 environments, one episode
per environment).  ``REDUCE`` seals the 16 pooled job receipts.  Runtime work
is never retried or silently resumed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        REPO_ROOT,
        V23_GPU_SUBWAVES,
        V23_INTERVENTION_MODES,
        V23_PLAN_ID,
        V23_ROUTE_A_STEPS,
        V23Error,
        write_json,
    )
except ImportError:  # direct ``python scriptsFORhuman/v23/pooled48.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_GPU_SUBWAVES,
        V23_INTERVENTION_MODES,
        V23_PLAN_ID,
        V23_ROUTE_A_STEPS,
        V23Error,
        write_json,
    )


PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
EVAL_EXPERIMENT = "wbmanip/door_open_a2_base_lstm"

POOLED48_SCHEMA = "a2_piper_v23_pooled48_receipt_v1"
POOLED48_STATUS = "V23_POOLED48_COMPLETE"
POOLED48_JOB_SCHEMA = "a2_piper_v23_pooled48_job_receipt_v1"
POOLED48_JOB_STATUS = "V23_POOLED48_JOB_COMPLETE"
POOLED48_PLAN_SCHEMA = "a2_piper_v23_pooled48_plan_v1"
POOLED48_TOPOLOGY = "pooled48"
POOLED48_NUM_ENVS = 48
POOLED48_EPISODES = 48
POOLED48_ROOT = REPO_ROOT / "logs_eval/base_v23/pooled48"
POOLED48_RECEIPT_PATH = POOLED48_ROOT / "V23_POOLED48.json"
POOLED48_PLAN_PATH = POOLED48_ROOT / "V23_POOLED48_PLAN.json"

# Route-B may be scheduled on any local physical GPU in this workstation.  The
# common v23 formal-training map remains intentionally untouched; Route-B
# manifests own their ordered subset and bind every job from that subset.
PHYSICAL_GPU_DOMAIN = tuple(range(8))
DEFAULT_PHYSICAL_GPUS = (0, 1)
PHYSICAL_GPU_MAPPING_POLICY = "CANONICAL_JOB_ORDINAL_MODULO_ORDERED_SELECTED_LIST"

ROUTE_A_SELECTION_SCHEMA = "a2_piper_v23_route_a_selection_v1"
ROUTE_A_SELECTION_STATUS = "COMPLETE"
ROUTE_A_SELECTION_ROOT = REPO_ROOT / "logs_eval/base_v23/route_a"
ROUTE_A_TOPOLOGY = "canonical16"

# This is the exact downstream selection contract.  Do not add an alias,
# candidate id, digest, or derived score to this tuple.
SELECTED_CANDIDATE_KEYS = (
    "source_branch",
    "plan_id",
    "identity_policy",
    "subwave",
    "seed",
    "cell",
    "row_id",
    "step",
    "checkpoint_path",
    "config_path",
    "scenario_path",
    "evaluation_root",
    "goal_reached",
    "supported_crossing",
    "unsafe_contacts",
    "terminal_failures",
)
_SOURCE_SELECTION_KEYS = tuple(key for key in SELECTED_CANDIDATE_KEYS if key != "subwave")
SUBWAVE_ORDER = ("A1", "A2", "B1", "B2")

SELECTION_PATHS = {
    subwave: ROUTE_A_SELECTION_ROOT
    / f"seed{V23_GPU_SUBWAVES[subwave]['seed']}"
    / subwave
    / "V23_ROUTE_A_SELECTION.json"
    for subwave in SUBWAVE_ORDER
}


class Pooled48Error(V23Error):
    """A pooled48 source, command, or receipt contract is invalid."""


def validate_physical_gpus(values: Sequence[int] | str | None) -> tuple[int, ...]:
    """Validate an ordered, unique, non-empty local physical-GPU subset."""

    if values is None:
        values = DEFAULT_PHYSICAL_GPUS
    if isinstance(values, str):
        if not values.strip():
            raise Pooled48Error("physical GPU mapping must be a non-empty comma-separated list")
        raw_values: Sequence[Any] = values.split(",")
    elif isinstance(values, (bytes, bytearray)):
        raise Pooled48Error("physical GPU mapping must be an ordered integer sequence")
    else:
        raw_values = values
    try:
        normalized = tuple(int(item) if isinstance(item, str) and item.strip() else item for item in raw_values)
    except (TypeError, ValueError) as exc:
        raise Pooled48Error("physical GPU mapping must contain integer ids") from exc
    if not normalized:
        raise Pooled48Error("physical GPU mapping must be non-empty")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in normalized):
        raise Pooled48Error("physical GPU mapping must contain integer ids")
    if any(item not in PHYSICAL_GPU_DOMAIN for item in normalized):
        raise Pooled48Error(
            f"physical GPU mapping must be an ordered unique subset of {list(PHYSICAL_GPU_DOMAIN)}"
        )
    if len(set(normalized)) != len(normalized):
        raise Pooled48Error("physical GPU mapping must not contain duplicates")
    return normalized


def parse_physical_gpus(value: str) -> tuple[int, ...]:
    """Parse the CLI ``--physical-gpus`` value with the same strict contract."""

    return validate_physical_gpus(value)


def physical_gpu_for_ordinal(ordinal: int, physical_gpus: Sequence[int] | str | None) -> int:
    """Map a canonical job ordinal deterministically to a selected GPU."""

    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
        raise Pooled48Error("canonical job ordinal must be a non-negative integer")
    selected = validate_physical_gpus(physical_gpus)
    return selected[ordinal % len(selected)]


def canonical_candidate_ordinal(candidate: Mapping[str, Any]) -> int:
    """Return the stable pooled ordinal for one selected candidate."""

    try:
        subwave_index = SUBWAVE_ORDER.index(str(candidate["subwave"]))
        cell_index = V23_GPU_SUBWAVES[str(candidate["subwave"])]["cells"].index(str(candidate["cell"]))
    except (KeyError, ValueError) as exc:
        raise Pooled48Error("candidate is not in canonical Route-B order") from exc
    return subwave_index * 4 + cell_index


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _load_object(path: str | Path) -> dict[str, Any]:
    target = _absolute(path)
    if target.is_symlink() or not target.is_file():
        raise Pooled48Error(f"required pooled48 JSON is missing: {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Pooled48Error(f"pooled48 JSON is invalid: {target}") from exc
    if not isinstance(payload, dict):
        raise Pooled48Error(f"pooled48 JSON must be an object: {target}")
    return payload


def _require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Pooled48Error(f"selected candidate {field} must be a non-empty string")
    return value


def _require_count(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 16:
        raise Pooled48Error(f"selected candidate {field} must be an integer in [0,16]")
    return value


def _check_candidate_sources(candidate: Mapping[str, Any]) -> None:
    for field in ("checkpoint_path", "config_path", "scenario_path"):
        path = _absolute(candidate[field])
        if path.is_symlink() or not path.is_file():
            raise Pooled48Error(f"selected candidate {field} is not a regular file: {path}")
    output = _absolute(candidate["evaluation_root"])
    if output.is_symlink() or not output.is_dir():
        raise Pooled48Error(f"selected candidate evaluation_root is not a directory: {output}")


def _validate_candidate(
    item: Any,
    *,
    index: int,
    expected_subwave: str,
    expected_cell: str,
    require_sources: bool,
) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise Pooled48Error(f"selected_candidates[{index}] must be an object")
    if set(item) != set(SELECTED_CANDIDATE_KEYS):
        missing = sorted(set(SELECTED_CANDIDATE_KEYS) - set(item))
        extra = sorted(set(item) - set(SELECTED_CANDIDATE_KEYS))
        raise Pooled48Error(
            f"selected_candidates[{index}] key set mismatch; missing={missing}, extra={extra}"
        )
    candidate = dict(item)
    if candidate["source_branch"] != "A2_Piper":
        raise Pooled48Error(f"selected_candidates[{index}] source_branch must be A2_Piper")
    if candidate["plan_id"] != V23_PLAN_ID:
        raise Pooled48Error(f"selected_candidates[{index}] plan_id disagrees with v23 plan")
    if candidate["identity_policy"] != "OWNER_NO_HASH_PATH_IDENTITY":
        raise Pooled48Error(f"selected_candidates[{index}] identity_policy is unsupported")
    if candidate["subwave"] != expected_subwave:
        raise Pooled48Error(f"selected_candidates[{index}] subwave is not {expected_subwave}")
    spec = V23_GPU_SUBWAVES[expected_subwave]
    if candidate["seed"] != spec["seed"]:
        raise Pooled48Error(f"selected_candidates[{index}] seed disagrees with {expected_subwave}")
    if candidate["cell"] != expected_cell:
        raise Pooled48Error(f"selected_candidates[{index}] cell order disagrees with {expected_subwave}")
    _require_text(candidate["row_id"], field="row_id")
    if isinstance(candidate["step"], bool) or not isinstance(candidate["step"], int):
        raise Pooled48Error(f"selected candidate step must be an integer: index {index}")
    if candidate["step"] not in V23_ROUTE_A_STEPS:
        raise Pooled48Error(f"selected candidate step is outside Route-A steps: index {index}")
    for field in ("checkpoint_path", "config_path", "scenario_path", "evaluation_root"):
        _require_text(candidate[field], field=field)
    for field in ("goal_reached", "supported_crossing", "unsafe_contacts", "terminal_failures"):
        _require_count(candidate[field], field=field)
    if require_sources:
        _check_candidate_sources(candidate)
    return {key: candidate[key] for key in SELECTED_CANDIDATE_KEYS}


def validate_selected_candidates(
    selected_candidates: Any,
    *,
    require_sources: bool = False,
) -> list[dict[str, Any]]:
    """Validate and return the one canonical 16-item selection list.

    The function is public so CPU-only fixtures can validate topology and the
    exact field contract without touching a simulator or a GPU.
    """

    if not isinstance(selected_candidates, list) or len(selected_candidates) != 16:
        raise Pooled48Error("selected_candidates must contain exactly 16 items")
    canonical: list[dict[str, Any]] = []
    index = 0
    seen: set[tuple[int, str]] = set()
    for subwave in SUBWAVE_ORDER:
        for cell in V23_GPU_SUBWAVES[subwave]["cells"]:
            candidate = _validate_candidate(
                selected_candidates[index],
                index=index,
                expected_subwave=subwave,
                expected_cell=cell,
                require_sources=require_sources,
            )
            identity = (candidate["seed"], candidate["cell"])
            if identity in seen:
                raise Pooled48Error(f"duplicate selected checkpoint identity: {identity}")
            seen.add(identity)
            canonical.append(candidate)
            index += 1
    if len(seen) != 16:
        raise Pooled48Error("selected candidate coverage is not exactly four subwaves by four cells")
    return canonical


def _load_selection_payload(path: Path, *, subwave: str) -> dict[str, Any]:
    payload = _load_object(path)
    spec = V23_GPU_SUBWAVES[subwave]
    expected = {
        "schema": ROUTE_A_SELECTION_SCHEMA,
        "status": ROUTE_A_SELECTION_STATUS,
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "A",
        "subwave": subwave,
        "seed": spec["seed"],
        "cells": list(spec["cells"]),
        "topology": ROUTE_A_TOPOLOGY,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise Pooled48Error(f"Route-A selection {path} field {field} disagrees")
    selected = payload.get("selected")
    if not isinstance(selected, list) or len(selected) != len(spec["cells"]):
        raise Pooled48Error(f"Route-A selection {path} must contain one row per cell")
    converted: list[dict[str, Any]] = []
    for index, source_item in enumerate(selected):
        if not isinstance(source_item, Mapping) or set(source_item) != set(_SOURCE_SELECTION_KEYS):
            raise Pooled48Error(
                f"Route-A selection {path} item {index} must contain exactly the frozen source fields"
            )
        item = {"subwave": subwave, **dict(source_item)}
        converted.append(item)
    return {"payload": payload, "selected": converted}


def load_selected_candidates(
    selection_paths: Mapping[str, str | Path] | None = None,
    *,
    require_sources: bool = True,
) -> list[dict[str, Any]]:
    """Load all four Route-A selections in the frozen A1/A2/B1/B2 order."""

    selected: list[dict[str, Any]] = []
    for subwave in SUBWAVE_ORDER:
        path = _absolute(selection_paths[subwave]) if selection_paths and subwave in selection_paths else SELECTION_PATHS[subwave]
        loaded = _load_selection_payload(path, subwave=subwave)
        selected.extend(loaded["selected"])
    return validate_selected_candidates(selected, require_sources=require_sources)


def _candidate_root(candidate: Mapping[str, Any]) -> Path:
    return (
        POOLED48_ROOT
        / f"seed{candidate['seed']}"
        / str(candidate["cell"])
        / f"step{int(candidate['step']):04d}"
        / POOLED48_TOPOLOGY
    )


def _command(candidate: Mapping[str, Any], output: Path, *, physical_gpu: int) -> list[str]:
    config = Path(str(candidate["config_path"]))
    if physical_gpu not in PHYSICAL_GPU_DOMAIN:
        raise Pooled48Error(f"selected candidate maps to illegal physical GPU {physical_gpu}")
    return [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+exp={EVAL_EXPERIMENT}",
        f"+ablation=wbmanip/{config.stem}",
        f"++checkpoint={candidate['checkpoint_path']}",
        "++checkpoint_load_mode=policy_only",
        "++algo.config.eval.a2_v23_p06_policy_only=true",
        "++auto_load_latest=false",
        "++headless=true",
        f"++num_envs={POOLED48_NUM_ENVS}",
        "++num_gpus=1",
        "++multi_gpu=false",
        f"++seed={candidate['seed']}",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++algo.config.eval.num_eval_episodes={POOLED48_EPISODES}",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++algo.config.num_mini_batches=1",
        "++env.config.a2_v23_d1_sampler_enabled=false",
        "++env.config.a2_v23_route_a_unsafe_contact_enabled=false",
        "++algo.config.eval.a2_v23_route_a_unsafe_contact_export=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        f"++eval_output_dir={output}",
        "++v23_route_b_topology=pooled48",
        f"++v23_route_b_candidate_subwave={candidate['subwave']}",
        f"++v23_route_b_candidate_cell={candidate['cell']}",
        f"++v23_route_b_candidate_step={candidate['step']}",
        f"++v23_route_b_scenario_path={candidate['scenario_path']}",
        "++env.config.a2_v23_warm_head_reset_enabled=false",
        "++env.config.a2_v23_formal_launch=false",
    ]


def _job_plan(
    candidate: Mapping[str, Any],
    *,
    physical_gpus: Sequence[int] | str | None = None,
    job_ordinal: int | None = None,
    physical_gpu: int | None = None,
) -> dict[str, Any]:
    output = _candidate_root(candidate)
    selected_gpus = validate_physical_gpus(physical_gpus)
    ordinal = canonical_candidate_ordinal(candidate) if job_ordinal is None else job_ordinal
    mapped_gpu = physical_gpu_for_ordinal(ordinal, selected_gpus)
    if physical_gpu is not None:
        if isinstance(physical_gpu, bool) or not isinstance(physical_gpu, int):
            raise Pooled48Error("manifest physical_gpu must be an integer")
        if physical_gpu != mapped_gpu:
            raise Pooled48Error(
                f"manifest physical_gpu {physical_gpu} disagrees with canonical ordinal {ordinal} "
                f"and selected mapping {list(selected_gpus)}"
            )
        mapped_gpu = physical_gpu
    return {
        "job_id": f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}",
        "job_ordinal": ordinal,
        "schema": POOLED48_JOB_SCHEMA,
        "source_branch": candidate["source_branch"],
        "plan_id": candidate["plan_id"],
        "identity_policy": candidate["identity_policy"],
        "selected_candidate": dict(candidate),
        "topology": POOLED48_TOPOLOGY,
        "num_envs": POOLED48_NUM_ENVS,
        "episodes": POOLED48_EPISODES,
        "physical_gpu": mapped_gpu,
        "logical_gpu": "cuda:0",
        "num_gpus": 1,
        "multi_gpu": False,
        "num_mini_batches": 1,
        "retry_count": 0,
        "no_retry": True,
        "evaluation_root": str(output),
        "records_path": str(output / "a2_v14_per_env_records.json"),
        "raw_trace_path": str(output / "stage2_step_trace.json"),
        "metrics_path": str(output / "metrics_eval.json"),
        "run_receipt_path": str(output / "run_receipt.json"),
        "contact_evidence": "NOT_EXPORTED_UNSUPPORTED_FOR_POOLED48",
        "command": _command(candidate, output, physical_gpu=mapped_gpu),
        "environment": {
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_VISIBLE_DEVICES": str(mapped_gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "WANDB_MODE": "disabled",
        },
    }


def build_plan(
    *,
    selection_paths: Mapping[str, str | Path] | None = None,
    require_sources: bool = True,
    physical_gpus: Sequence[int] | str | None = None,
    output: str | Path | None = None,
) -> dict[str, Any]:
    selected = load_selected_candidates(selection_paths, require_sources=require_sources)
    selected_gpus = validate_physical_gpus(physical_gpus)
    jobs = [
        _job_plan(candidate, physical_gpus=selected_gpus, job_ordinal=ordinal)
        for ordinal, candidate in enumerate(selected)
    ]
    if len(jobs) != 16:
        raise Pooled48Error("pooled48 plan must contain exactly 16 jobs")
    payload = {
        "schema": POOLED48_PLAN_SCHEMA,
        "status": "BUILT",
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "stage": "POOLED48",
        "selected_candidates": selected,
        "selected_candidate_count": len(selected),
        "topology": POOLED48_TOPOLOGY,
        "num_envs": POOLED48_NUM_ENVS,
        "episodes_per_job": POOLED48_EPISODES,
        "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
        "physical_gpus": list(selected_gpus),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "logical_gpu": "cuda:0",
        "process_count_per_gpu": 1,
        "num_mini_batches": 1,
        "no_retry": True,
        "intervention_modes_reserved": list(V23_INTERVENTION_MODES),
        "jobs": jobs,
        "missing_evidence_policy": "TYPED_FAILURE_NO_ZERO_FILL",
    }
    if output is not None:
        write_json(_absolute(output), payload)
    return payload


def _validate_manifest_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a persisted pooled plan before RUN or REDUCE consumes it."""

    if payload.get("schema") != POOLED48_PLAN_SCHEMA or payload.get("status") != "BUILT":
        raise Pooled48Error("pooled48 manifest schema/status is not BUILT")
    if payload.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN):
        raise Pooled48Error("pooled48 manifest physical_gpu_domain is not exactly 0..7")
    selected_gpus = validate_physical_gpus(payload.get("physical_gpus"))
    if payload.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise Pooled48Error("pooled48 manifest physical GPU mapping policy is unsupported")
    selected = validate_selected_candidates(payload.get("selected_candidates"), require_sources=False)
    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != len(selected):
        raise Pooled48Error("pooled48 manifest must contain exactly 16 jobs")
    normalized_jobs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for ordinal, (candidate, raw_job) in enumerate(zip(selected, jobs)):
        if not isinstance(raw_job, Mapping):
            raise Pooled48Error(f"pooled48 manifest job {ordinal} must be an object")
        job = dict(raw_job)
        expected_id = f"{candidate['subwave']}:{candidate['cell']}:step{candidate['step']:04d}"
        if job.get("job_id") != expected_id or job.get("job_ordinal") != ordinal:
            raise Pooled48Error(f"pooled48 manifest job {ordinal} identity/order disagrees")
        if job.get("selected_candidate") != candidate:
            raise Pooled48Error(f"pooled48 manifest job {expected_id} candidate disagrees")
        expected_gpu = physical_gpu_for_ordinal(ordinal, selected_gpus)
        if job.get("physical_gpu") != expected_gpu:
            raise Pooled48Error(f"pooled48 manifest job {expected_id} physical_gpu disagrees")
        if job.get("logical_gpu") != "cuda:0":
            raise Pooled48Error(f"pooled48 manifest job {expected_id} logical_gpu must be cuda:0")
        environment = job.get("environment")
        if not isinstance(environment, Mapping) or environment.get("CUDA_VISIBLE_DEVICES") != str(expected_gpu):
            raise Pooled48Error(f"pooled48 manifest job {expected_id} CUDA mask disagrees")
        command = job.get("command")
        if not isinstance(command, list):
            raise Pooled48Error(f"pooled48 manifest job {expected_id} command must be a list")
        if "++checkpoint_load_mode=policy_only" not in command:
            raise Pooled48Error(
                f"pooled48 manifest job {expected_id} must use checkpoint_load_mode=policy_only"
            )
        if "++algo.config.eval.a2_v23_p06_policy_only=true" not in command:
            raise Pooled48Error(
                f"pooled48 manifest job {expected_id} must enable the P0.6 policy-only gate"
            )
        if "++env.config.a2_v23_d1_sampler_enabled=false" not in command:
            raise Pooled48Error(
                f"pooled48 manifest job {expected_id} must disable the D1 sampler explicitly"
            )
        if expected_id in seen_ids:
            raise Pooled48Error(f"pooled48 manifest contains duplicate job {expected_id}")
        seen_ids.add(expected_id)
        normalized_jobs.append(job)
    normalized = dict(payload)
    normalized["selected_candidates"] = selected
    normalized["physical_gpus"] = list(selected_gpus)
    normalized["jobs"] = normalized_jobs
    return normalized


def load_plan(path: str | Path = POOLED48_PLAN_PATH) -> dict[str, Any]:
    """Load and validate the persisted manifest used by RUN/REDUCE."""

    return _validate_manifest_plan(_load_object(path))


def _validate_runtime_files(job: Mapping[str, Any]) -> tuple[list[Any], list[Any], dict[str, Any]]:
    root = _absolute(job["evaluation_root"])
    records_value = json.loads(_absolute(job["records_path"]).read_text(encoding="utf-8"))
    trace_value = json.loads(_absolute(job["raw_trace_path"]).read_text(encoding="utf-8"))
    metrics_value = json.loads(_absolute(job["metrics_path"]).read_text(encoding="utf-8"))
    if not isinstance(records_value, list) or len(records_value) != POOLED48_NUM_ENVS:
        raise Pooled48Error(f"pooled48 records must contain exactly 48 rows: {root}")
    ids = sorted(row.get("env_id") for row in records_value if isinstance(row, Mapping))
    if ids != list(range(POOLED48_NUM_ENVS)):
        raise Pooled48Error(f"pooled48 records must cover env ids 0..47: {root}")
    if not isinstance(trace_value, list) or not trace_value:
        raise Pooled48Error(f"pooled48 raw trace is empty: {root}")
    trace_ids = {row.get("env_id") for row in trace_value if isinstance(row, Mapping)}
    if trace_ids != set(range(POOLED48_NUM_ENVS)):
        raise Pooled48Error(f"pooled48 raw trace must cover env ids 0..47: {root}")
    if not isinstance(metrics_value, Mapping) or metrics_value.get("completed_episodes") != POOLED48_EPISODES:
        raise Pooled48Error(f"pooled48 metrics must report completed_episodes=48: {root}")
    return records_value, trace_value, dict(metrics_value)


def _run_one(job: Mapping[str, Any]) -> dict[str, Any]:
    physical_gpu = job.get("physical_gpu")
    if isinstance(physical_gpu, bool) or not isinstance(physical_gpu, int) or physical_gpu not in PHYSICAL_GPU_DOMAIN:
        raise Pooled48Error(f"pooled48 job {job.get('job_id')} has an invalid manifest physical_gpu")
    environment = job.get("environment")
    if not isinstance(environment, Mapping) or environment.get("CUDA_VISIBLE_DEVICES") != str(physical_gpu):
        raise Pooled48Error(f"pooled48 job {job.get('job_id')} CUDA mask is not manifest-assigned")
    root = _absolute(job["evaluation_root"])
    receipt_path = root / "run_receipt.json"
    if root.exists():
        if receipt_path.is_file() and not receipt_path.is_symlink():
            raise Pooled48Error(f"pooled48 job output already exists; refusing resume: {root}")
        raise Pooled48Error(f"pooled48 job output exists without a sealed receipt: {root}")
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
        raise Pooled48Error(f"pooled48 job {job['job_id']} exited {return_code}; no retry")
    records, trace, metrics = _validate_runtime_files(job)
    receipt = {
        "schema": POOLED48_JOB_SCHEMA,
        "status": POOLED48_JOB_STATUS,
        "recorded_at_utc": _now(),
        "job_id": job["job_id"],
        "job_ordinal": job["job_ordinal"],
        "source_branch": job["source_branch"],
        "plan_id": job["plan_id"],
        "identity_policy": job["identity_policy"],
        "selected_candidate": dict(job["selected_candidate"]),
        "topology": POOLED48_TOPOLOGY,
        "num_envs": POOLED48_NUM_ENVS,
        "episode_record_count": len(records),
        "trace_row_count": len(trace),
        "trace_env_ids": sorted({row["env_id"] for row in trace if isinstance(row, Mapping)}),
        "metrics_completed_episodes": metrics["completed_episodes"],
        "physical_gpu": physical_gpu,
        "logical_gpu": "cuda:0",
        "num_mini_batches": 1,
        "process_count": 1,
        "retry_count": 0,
        "natural_completion": True,
        "contact_evidence": "NOT_EXPORTED_UNSUPPORTED_FOR_POOLED48",
        "missing_evidence": ["unsafe_contacts_not_exported_for_pooled48"],
        "process": {
            "pid": process.pid,
            "started_at_utc": started,
            "ended_at_utc": ended,
            "return_code": return_code,
        },
        "records_path": job["records_path"],
        "raw_trace_path": job["raw_trace_path"],
        "metrics_path": job["metrics_path"],
    }
    write_json(receipt_path, receipt)
    return receipt


def run(
    *,
    selection_paths: Mapping[str, str | Path] | None = None,
    only_job: str | None = None,
    plan_path: str | Path | None = None,
    physical_gpus: Sequence[int] | str | None = None,
) -> dict[str, Any]:
    if plan_path is None:
        raise Pooled48Error("RUN requires a persisted plan_path")
    if physical_gpus is not None:
        raise Pooled48Error("RUN rejects live physical_gpus; use the persisted plan mapping")
    plan = load_plan(plan_path)
    if selection_paths is not None:
        expected = load_selected_candidates(selection_paths, require_sources=True)
        if expected != plan["selected_candidates"]:
            raise Pooled48Error("pooled48 manifest selected_candidates disagree with selection overrides")
    jobs = plan["jobs"]
    if only_job is not None:
        jobs = [job for job in jobs if job["job_id"] == only_job]
        if not jobs:
            raise Pooled48Error(f"unknown pooled48 job: {only_job}")
    receipts = [_run_one(job) for job in jobs]
    return {
        "schema": "a2_piper_v23_pooled48_run_result_v1",
        "status": "PASS",
        "recorded_at_utc": _now(),
        "job_count": len(receipts),
        "completed_jobs": [receipt["job_id"] for receipt in receipts],
        "no_retry": True,
    }


def _load_job_receipt(
    path: Path,
    *,
    candidate: Mapping[str, Any],
    expected_physical_gpu: int,
    expected_job_ordinal: int,
) -> dict[str, Any]:
    receipt = _load_object(path)
    if receipt.get("schema") != POOLED48_JOB_SCHEMA or receipt.get("status") != POOLED48_JOB_STATUS:
        raise Pooled48Error(f"pooled48 job receipt is not complete: {path}")
    if receipt.get("selected_candidate") != dict(candidate):
        raise Pooled48Error(f"pooled48 job receipt identity disagrees: {path}")
    for field, expected in (
        ("topology", POOLED48_TOPOLOGY),
        ("num_envs", POOLED48_NUM_ENVS),
        ("episode_record_count", POOLED48_NUM_ENVS),
        ("metrics_completed_episodes", POOLED48_EPISODES),
        ("physical_gpu", expected_physical_gpu),
        ("job_ordinal", expected_job_ordinal),
        ("logical_gpu", "cuda:0"),
        ("num_mini_batches", 1),
        ("retry_count", 0),
        ("natural_completion", True),
    ):
        if receipt.get(field) != expected:
            raise Pooled48Error(f"pooled48 job receipt {path} field {field} disagrees")
    return receipt


def reduce(
    *,
    selection_paths: Mapping[str, str | Path] | None = None,
    output: str | Path = POOLED48_RECEIPT_PATH,
    plan_path: str | Path | None = None,
    physical_gpus: Sequence[int] | str | None = None,
) -> dict[str, Any]:
    if plan_path is None:
        raise Pooled48Error("REDUCE requires a persisted plan_path")
    if physical_gpus is not None:
        raise Pooled48Error("REDUCE rejects live physical_gpus; use the persisted plan mapping")
    plan = load_plan(plan_path)
    selected = plan["selected_candidates"]
    if selection_paths is not None:
        expected = load_selected_candidates(selection_paths, require_sources=False)
        if expected != selected:
            raise Pooled48Error("pooled48 manifest selected_candidates disagree with selection overrides")
    jobs: list[dict[str, Any]] = []
    for ordinal, (candidate, manifest_job) in enumerate(zip(selected, plan["jobs"])):
        receipt_path = _absolute(manifest_job["run_receipt_path"])
        receipt = _load_job_receipt(
            receipt_path,
            candidate=candidate,
            expected_physical_gpu=manifest_job["physical_gpu"],
            expected_job_ordinal=ordinal,
        )
        jobs.append(
            {
                "job_id": receipt["job_id"],
                "job_ordinal": ordinal,
                "selected_candidate": dict(candidate),
                "receipt_path": str(receipt_path),
                "topology": receipt["topology"],
                "episode_record_count": receipt["episode_record_count"],
                "metrics_completed_episodes": receipt["metrics_completed_episodes"],
                "physical_gpu": receipt["physical_gpu"],
                "contact_evidence": receipt["contact_evidence"],
                "missing_evidence": list(receipt["missing_evidence"]),
            }
        )
    if len(jobs) != 16:
        raise Pooled48Error("pooled48 reduction requires exactly 16 complete jobs")
    payload = {
        "schema": POOLED48_SCHEMA,
        "status": POOLED48_STATUS,
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "stage": "POOLED48",
        "topology": POOLED48_TOPOLOGY,
        "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
        "physical_gpus": list(plan["physical_gpus"]),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "logical_gpu": "cuda:0",
        "process_count_per_gpu": 1,
        "num_mini_batches": 1,
        "candidate_count": len(selected),
        "selected_candidates": selected,
        "job_count": len(jobs),
        "episode_record_count": len(jobs) * POOLED48_NUM_ENVS,
        "contact_evidence": "NOT_EXPORTED_UNSUPPORTED_FOR_POOLED48",
        "missing_evidence": ["unsafe_contacts_not_exported_for_pooled48"],
        "jobs": jobs,
        "no_retry": True,
    }
    write_json(_absolute(output), payload)
    return payload


def _selection_args(parser: argparse.ArgumentParser) -> None:
    for subwave in SUBWAVE_ORDER:
        parser.add_argument(f"--{subwave.lower()}-selection", type=Path, default=None)


def _selection_paths_from_args(args: argparse.Namespace) -> dict[str, Path] | None:
    paths = {
        subwave: getattr(args, f"{subwave.lower()}_selection")
        for subwave in SUBWAVE_ORDER
        if getattr(args, f"{subwave.lower()}_selection") is not None
    }
    if not paths:
        return None
    if set(paths) != set(SUBWAVE_ORDER):
        raise Pooled48Error("selection overrides must provide all four subwaves")
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "BUILD", "RUN", "REDUCE"), required=True)
    parser.add_argument("--job", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--plan", type=Path, default=POOLED48_PLAN_PATH)
    parser.add_argument(
        "--physical-gpus",
        type=parse_physical_gpus,
        default=None,
        help="ordered unique local physical GPU ids, subset of 0..7; PLAN/BUILD only",
    )
    parser.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help="CPU fixture only; never permits RUN and never changes runtime validation",
    )
    _selection_args(parser)
    args = parser.parse_args(argv)
    try:
        if args.mode not in {"PLAN", "BUILD"} and args.physical_gpus is not None:
            raise Pooled48Error("--physical-gpus is valid only for PLAN and BUILD")
        selection_paths = _selection_paths_from_args(args)
        if args.mode in {"PLAN", "BUILD"}:
            payload = build_plan(
                selection_paths=selection_paths,
                require_sources=not args.allow_missing_sources,
                physical_gpus=args.physical_gpus,
                output=(args.output if args.mode == "BUILD" else None),
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        elif args.mode == "RUN":
            if args.allow_missing_sources:
                raise Pooled48Error("--allow-missing-sources is not valid for RUN")
            payload = run(selection_paths=selection_paths, only_job=args.job, plan_path=args.plan)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            payload = reduce(
                selection_paths=selection_paths,
                plan_path=args.plan,
                output=args.output or POOLED48_RECEIPT_PATH,
            )
            print(json.dumps({"status": "WRITTEN", "path": str(_absolute(args.output or POOLED48_RECEIPT_PATH))}, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 POOLED48 {args.mode} FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
