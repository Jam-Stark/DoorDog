"""Qualitative Route-B render planner, one-shot runner, and reducer.

Route-B render evidence is a deterministic visual aid only.  It is never a
scientific success gate, formal admission record, or release receipt.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23Error, V23_CELL_FACTORS, read_json, write_json
    from .holdout64 import (
        CANDIDATE_FREEZE_PATH,
        CANDIDATE_FREEZE_SCHEMA,
        CANDIDATE_FREEZE_STATUS,
        HOLDOUT_RECEIPT_PATH,
        RECEIPT_SCHEMA as HOLDOUT_RECEIPT_SCHEMA,
        RECEIPT_STATUS as HOLDOUT_RECEIPT_STATUS,
        _absolute,
        _load_candidate_freeze,
        _validate_physical_gpu_manifest,
        _parse_physical_gpu_tokens,
    )
except ImportError:  # direct script invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23Error, V23_CELL_FACTORS, read_json, write_json
    from scriptsFORhuman.v23.holdout64 import (
        CANDIDATE_FREEZE_PATH,
        CANDIDATE_FREEZE_SCHEMA,
        CANDIDATE_FREEZE_STATUS,
        HOLDOUT_RECEIPT_PATH,
        RECEIPT_SCHEMA as HOLDOUT_RECEIPT_SCHEMA,
        RECEIPT_STATUS as HOLDOUT_RECEIPT_STATUS,
        _absolute,
        _load_candidate_freeze,
        _validate_physical_gpu_manifest,
        _parse_physical_gpu_tokens,
    )


PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
LEGAL_PHYSICAL_GPUS = tuple(range(8))
PHYSICAL_GPUS = LEGAL_PHYSICAL_GPUS
DEFAULT_PHYSICAL_GPUS = LEGAL_PHYSICAL_GPUS
PHYSICAL_GPU_MAPPING_POLICY = "CANONICAL_JOB_ORDINAL_MODULO_ORDERED_SELECTED_LIST"
LOGICAL_DEVICE = "cuda:0"
POLICY_ONLY_OVERRIDE = "++algo.config.eval.a2_v23_p06_policy_only=true"
D1_SAMPLER_DISABLE_OVERRIDE = "++env.config.a2_v23_d1_sampler_enabled=false"
RENDER_ROOT = REPO_ROOT / "logs_eval/base_v23/render"
PLAN_SCHEMA = "a2_piper_v23_render_plan_v1"
RECEIPT_SCHEMA = "a2_piper_v23_render_qa_receipt_v1"
RECEIPT_STATUS = "V23_RENDER_QA_COMPLETE"
SCENARIO_MANIFEST_SCHEMA = "a2_piper_v23_route_b_render_scenario_manifest_v1"
SCENARIO_MANIFEST_STATUS = "STATIC_RENDER"
SCENARIO_MANIFEST_TOPOLOGY = "render16"
CAMERAS = ("main", "handle_top", "handle_side")
EXPECTED_CANDIDATE_COUNT = 16
CANONICAL_HOLDOUT_EPISODES = 64
EXPECTED_SCENARIO_COUNT = 5
EXPECTED_ENV_COUNT = 16
EXPECTED_MEDIA_COUNT = EXPECTED_ENV_COUNT * len(CAMERAS)
SCENARIO_SCALAR_FIELDS = (
    "handle_height_m",
    "door_weight_kg",
    "hinge_max_force_nm",
    "hinge_damping_native",
    "hinge_stiffness_native",
)
_MEDIA_NAME_RE = re.compile(
    r"^(?P<session>.+)_env(?P<env>\d{4})_episode(?P<episode>\d{4})"
    r"(?P<camera>_handle_top|_handle_side)?_len\d+_reason-[^.]+\.mp4$"
)

SCENARIOS = (
    {
        "name": "ordinary_mid_handle",
        "label": "ordinary middle-height door",
        "handle_height_m": 0.975,
        "door_weight_kg": 120.0,
        "hinge_max_force_nm": 10.0,
        "hinge_damping_native": 50.0,
        "hinge_stiffness_native": 6.0,
        "bucket": "H0",
    },
    {
        "name": "low_handle",
        "label": "low handle",
        "handle_height_m": 0.85,
        "door_weight_kg": 120.0,
        "hinge_max_force_nm": 10.0,
        "hinge_damping_native": 50.0,
        "hinge_stiffness_native": 6.0,
        "bucket": "H0",
    },
    {
        "name": "high_handle",
        "label": "high handle",
        "handle_height_m": 1.10,
        "door_weight_kg": 120.0,
        "hinge_max_force_nm": 10.0,
        "hinge_damping_native": 50.0,
        "hinge_stiffness_native": 6.0,
        "bucket": "H0",
    },
    {
        "name": "fast_rebound",
        "label": "fast rebound",
        "handle_height_m": 0.975,
        "door_weight_kg": 120.0,
        "hinge_max_force_nm": 16.0,
        "hinge_damping_native": 25.0,
        "hinge_stiffness_native": 18.0,
        "bucket": "H2",
    },
    {
        "name": "high_damping",
        "label": "high damping/resistive",
        "handle_height_m": 0.975,
        "door_weight_kg": 120.0,
        "hinge_max_force_nm": 12.0,
        "hinge_damping_native": 120.0,
        "hinge_stiffness_native": 6.0,
        "bucket": "H1",
    },
)


class RenderError(V23Error):
    """A render topology or qualitative artifact is invalid."""


def _candidate_door_regime(candidate: Mapping[str, Any]) -> str:
    cell = candidate.get("cell")
    factors = V23_CELL_FACTORS.get(cell)
    if not isinstance(factors, Mapping) or factors.get("door_regime") not in {"D0", "D1"}:
        raise RenderError(f"candidate cell has no canonical door regime: {cell!r}")
    return str(factors["door_regime"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _finite_positive(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RenderError(f"{label} must be a finite positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise RenderError(f"{label} must be a finite positive number")
    return number


def _load_holdout(path: str | Path) -> dict[str, Any]:
    target = _absolute(path)
    return _validate_holdout_payload(read_json(target), source=str(target))


def _validate_holdout_payload(payload: Mapping[str, Any], *, source: str = "holdout receipt") -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise RenderError(f"holdout receipt must be an object: {source}")
    if payload.get("schema") != HOLDOUT_RECEIPT_SCHEMA:
        raise RenderError(f"holdout receipt schema must be {HOLDOUT_RECEIPT_SCHEMA}: {source}")
    if payload.get("status") != HOLDOUT_RECEIPT_STATUS:
        raise RenderError(f"holdout receipt status must be {HOLDOUT_RECEIPT_STATUS}: {source}")
    try:
        _validate_physical_gpu_manifest(payload.get("physical_gpus"), label="holdout receipt physical_gpus")
    except V23Error as exc:
        raise RenderError(str(exc)) from exc
    if payload.get("gpu_assignment") != "JOB_ORDINAL_MODULO_PHYSICAL_GPU_MANIFEST":
        raise RenderError("holdout receipt GPU assignment must be ordinal modulo its manifest")
    if payload.get("physical_gpu_domain") != list(LEGAL_PHYSICAL_GPUS) or payload.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise RenderError("holdout receipt physical GPU domain/mapping policy is invalid")
    if payload.get("logical_gpu") != LOGICAL_DEVICE:
        raise RenderError("holdout receipt GPU contract must use logical cuda:0")
    if payload.get("candidate_freeze_schema") != CANDIDATE_FREEZE_SCHEMA or payload.get("candidate_freeze_status") != CANDIDATE_FREEZE_STATUS:
        raise RenderError("holdout receipt candidate-freeze provenance is invalid")
    holdout_freeze_path = payload.get("candidate_freeze_path")
    if not isinstance(holdout_freeze_path, str) or not holdout_freeze_path or not Path(holdout_freeze_path).is_absolute():
        raise RenderError("holdout receipt must bind an absolute candidate-freeze receipt path")
    freeze_ids = payload.get("candidate_freeze_ids")
    if (
        not isinstance(freeze_ids, list)
        or len(freeze_ids) != EXPECTED_CANDIDATE_COUNT
        or any(not isinstance(item, str) or not item for item in freeze_ids)
        or len(set(freeze_ids)) != EXPECTED_CANDIDATE_COUNT
    ):
        raise RenderError("holdout receipt must bind exactly 16 unique candidate-freeze ids")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != EXPECTED_CANDIDATE_COUNT:
        raise RenderError("holdout receipt must contain exactly 16 candidates")
    identities: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or not isinstance(candidate.get("freeze_id"), str):
            raise RenderError("holdout receipt candidate identity is invalid")
        if candidate.get("episode_count") != 64:
            raise RenderError("holdout receipt candidate must contain canonical64 episodes")
        if candidate["freeze_id"] in identities:
            raise RenderError("holdout receipt candidate identities must be unique")
        identities.add(candidate["freeze_id"])
    if identities != set(freeze_ids):
        raise RenderError("holdout receipt candidate identities disagree with its freeze provenance")
    return dict(payload)


def _candidate_by_id(freeze: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if freeze.get("schema") != CANDIDATE_FREEZE_SCHEMA:
        raise RenderError(f"candidate freeze schema must be {CANDIDATE_FREEZE_SCHEMA}")
    if freeze.get("status") != CANDIDATE_FREEZE_STATUS:
        raise RenderError(f"candidate freeze status must be {CANDIDATE_FREEZE_STATUS}")
    if freeze.get("candidate_count") != EXPECTED_CANDIDATE_COUNT:
        raise RenderError("candidate freeze must contain exactly 16 candidates")
    rows = freeze.get("selected_candidates")
    if not isinstance(rows, list) or len(rows) != EXPECTED_CANDIDATE_COUNT:
        raise RenderError("candidate freeze selected_candidates must contain exactly 16 rows")
    result: dict[str, dict[str, Any]] = {}
    expected_fields = {
        "freeze_id",
        "evidence_status",
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
    }
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != expected_fields or not isinstance(row.get("freeze_id"), str) or not row["freeze_id"]:
            raise RenderError(f"candidate freeze selected_candidates[{index}] identity is invalid")
        if row["freeze_id"] in result:
            raise RenderError(f"candidate freeze contains duplicate freeze_id={row['freeze_id']}")
        result[row["freeze_id"]] = dict(row)
    return result


def _holdout_by_id(holdout: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = holdout.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != EXPECTED_CANDIDATE_COUNT:
        raise RenderError("holdout receipt must contain exactly 16 candidate rows")
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(candidates):
        if not isinstance(row, Mapping) or not isinstance(row.get("freeze_id"), str) or not row["freeze_id"]:
            raise RenderError(f"holdout candidate row {index} identity is invalid")
        freeze_id = str(row["freeze_id"])
        if freeze_id in result:
            raise RenderError(f"holdout receipt contains duplicate freeze_id={freeze_id}")
        if row.get("episode_count") != 64 or not isinstance(row.get("candidate"), Mapping):
            raise RenderError(f"holdout candidate row {index} is not a canonical64 provenance row")
        result[freeze_id] = dict(row)
    return result


def _normalize_candidate_ids(
    candidate_ids: Sequence[str] | None,
    *,
    freeze_candidates: Mapping[str, Mapping[str, Any]],
    holdout_candidates: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    if candidate_ids is None or isinstance(candidate_ids, (str, bytes)):
        raise RenderError("render PLAN requires explicit 1-3 candidate IDs")
    if any(not isinstance(item, str) for item in candidate_ids):
        raise RenderError("render candidate IDs must be strings")
    ids = list(candidate_ids)
    if len(ids) not in (1, 2, 3):
        raise RenderError("render PLAN requires exactly 1-3 explicit candidate IDs")
    if any(not item for item in ids):
        raise RenderError("render candidate IDs must be non-empty strings")
    if len(set(ids)) != len(ids):
        raise RenderError("render candidate IDs must be unique; duplicates are not permitted")
    freeze_ids = set(freeze_candidates)
    holdout_ids = set(holdout_candidates)
    for freeze_id in ids:
        if freeze_id not in freeze_ids:
            raise RenderError(f"render candidate ID is not present in the validated freeze: {freeze_id}")
        if freeze_id not in holdout_ids:
            raise RenderError(f"render candidate ID is not present in the validated holdout: {freeze_id}")
    return ids


def _parse_candidate_id_tokens(values: Sequence[str] | None) -> list[str] | None:
    if values is None:
        return None
    tokens: list[str] = []
    for value in values:
        tokens.extend(part.strip() for part in str(value).split(","))
    if not tokens or any(not token for token in tokens):
        raise RenderError("candidate-ID input must contain one or more non-empty IDs")
    return tokens


def _load_bound_candidate_freeze(path_value: Any) -> tuple[Path, dict[str, Any]]:
    if not isinstance(path_value, str) or not path_value or not Path(path_value).is_absolute():
        raise RenderError("render plan must bind an absolute candidate-freeze receipt path")
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise RenderError(f"bound candidate-freeze receipt is missing or non-regular: {path}")
    resolved = path.resolve()
    freeze = _load_candidate_freeze(resolved)
    _candidate_by_id(freeze)
    return resolved, freeze


def _scenario_parameters(scenario: Mapping[str, Any]) -> dict[str, float]:
    return {field: _finite_positive(scenario[field], f"scenario.{field}") for field in SCENARIO_SCALAR_FIELDS}


def build_scenario_manifest(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Build the exact static render16 manifest consumed by the task hook."""

    scenario_id = scenario.get("name")
    if not isinstance(scenario_id, str) or not scenario_id:
        raise RenderError("render scenario name must be a non-empty string")
    params = _scenario_parameters(scenario)
    rows = [
        {
            "env_id": env_id,
            "scenario_id": f"{scenario_id}_env{env_id:02d}",
            **params,
        }
        for env_id in range(EXPECTED_ENV_COUNT)
    ]
    manifest = {
        "schema": SCENARIO_MANIFEST_SCHEMA,
        "status": SCENARIO_MANIFEST_STATUS,
        "topology": SCENARIO_MANIFEST_TOPOLOGY,
        "scenario_id": scenario_id,
        "rows": rows,
    }
    _validate_scenario_manifest(manifest)
    return manifest


def _validate_scenario_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != SCENARIO_MANIFEST_SCHEMA:
        raise RenderError(f"scenario manifest schema must be {SCENARIO_MANIFEST_SCHEMA}")
    if payload.get("status") != SCENARIO_MANIFEST_STATUS:
        raise RenderError(f"scenario manifest status must be {SCENARIO_MANIFEST_STATUS}")
    if payload.get("topology") != SCENARIO_MANIFEST_TOPOLOGY:
        raise RenderError(f"scenario manifest topology must be {SCENARIO_MANIFEST_TOPOLOGY}")
    scenario_id = payload.get("scenario_id")
    if not isinstance(scenario_id, str) or not scenario_id:
        raise RenderError("scenario manifest scenario_id must be a non-empty string")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_ENV_COUNT:
        raise RenderError("scenario manifest must contain exactly 16 environment rows")
    expected_keys = {"env_id", "scenario_id", *SCENARIO_SCALAR_FIELDS}
    seen: set[str] = set()
    for env_id, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != expected_keys:
            raise RenderError(f"scenario manifest row {env_id} has an invalid key set")
        if row.get("env_id") != env_id:
            raise RenderError("scenario manifest env rows must be ordered env0 through env15")
        row_id = row.get("scenario_id")
        expected_row_id = f"{scenario_id}_env{env_id:02d}"
        if not isinstance(row_id, str) or row_id != expected_row_id or row_id in seen:
            raise RenderError("scenario manifest row scenario_ids must be ordered and unique")
        seen.add(row_id)
        for field in SCENARIO_SCALAR_FIELDS:
            _finite_positive(row[field], f"scenario manifest row {env_id}.{field}")
    return dict(payload)


def _candidate_identity(candidate: Mapping[str, Any]) -> dict[str, Any]:
    fields = ("freeze_id", "checkpoint_path", "config_path", "seed", "subwave", "cell")
    return {field: candidate[field] for field in fields if field in candidate}


def _build_command(
    candidate: Mapping[str, Any],
    scenario: Mapping[str, Any],
    *,
    physical_gpu: int,
    output_root: Path,
    manifest_path: Path,
) -> tuple[list[str], dict[str, str]]:
    if physical_gpu not in LEGAL_PHYSICAL_GPUS:
        raise RenderError(f"physical GPU must be one of {LEGAL_PHYSICAL_GPUS}")
    command = [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={candidate['checkpoint_path']}",
        "++checkpoint_load_mode=policy_only",
        POLICY_ONLY_OVERRIDE,
        "++auto_load_latest=false",
        "++headless=true",
        "++num_envs=16",
        "++num_gpus=1",
        "++multi_gpu=false",
        f"++seed={candidate['seed']}",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++algo.config.num_mini_batches=1",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.num_eval_episodes=16",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=true",
        f"++env.config.save_rendering_dir={output_root / 'renderings'}",
        "++env.config.a2_v23_route_b_render_enabled=true",
        f"++env.config.a2_v23_route_b_render_manifest_path={manifest_path}",
        "++env.config.a2_v23_warm_head_reset_enabled=false",
        f"++eval_output_dir={output_root}",
    ]
    if _candidate_door_regime(candidate) == "D1":
        command.append(D1_SAMPLER_DISABLE_OVERRIDE)
    environment = {
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        "CUDA_VISIBLE_DEVICES": str(physical_gpu),
        "ACCELERATE_TORCH_DEVICE": LOGICAL_DEVICE,
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }
    return command, environment


def build_render_plan(
    freeze: Mapping[str, Any],
    holdout: Mapping[str, Any] | None = None,
    *,
    output_root: str | Path = RENDER_ROOT,
    candidate_freeze_path: str | Path = CANDIDATE_FREEZE_PATH,
    holdout_path: str | Path = HOLDOUT_RECEIPT_PATH,
    candidate_ids: Sequence[str] | None = None,
    physical_gpus: Sequence[int] = DEFAULT_PHYSICAL_GPUS,
) -> dict[str, Any]:
    if not isinstance(freeze, Mapping):
        raise RenderError("candidate freeze must be a mapping")
    if not isinstance(holdout, Mapping):
        raise RenderError("render PLAN requires a validated holdout receipt")
    bound_freeze_path, bound_freeze = _load_bound_candidate_freeze(str(_absolute(candidate_freeze_path).resolve()))
    if dict(freeze) != dict(bound_freeze):
        raise RenderError("render plan candidate freeze rows do not match the bound receipt")
    freeze_candidates = _candidate_by_id(bound_freeze)
    validated_holdout = _validate_holdout_payload(holdout)
    holdout_candidates = _holdout_by_id(validated_holdout)
    if set(holdout_candidates) != set(freeze_candidates):
        raise RenderError("holdout/candidate freeze identities do not match")
    if Path(str(validated_holdout["candidate_freeze_path"])).resolve() != bound_freeze_path:
        raise RenderError("holdout receipt candidate-freeze path disagrees with the bound freeze receipt")
    if holdout.get("candidate_freeze_ids") != list(freeze_candidates):
        raise RenderError("holdout candidate-freeze ids are not in canonical freeze order")
    for freeze_id, holdout_row in holdout_candidates.items():
        if holdout_row.get("candidate") != freeze_candidates[freeze_id]:
            raise RenderError(f"holdout candidate {freeze_id} does not bind the freeze candidate")
    selected_ids = _normalize_candidate_ids(
        candidate_ids,
        freeze_candidates=freeze_candidates,
        holdout_candidates=holdout_candidates,
    )
    gpu_manifest = _validate_physical_gpu_manifest(physical_gpus, label="physical_gpus")
    bound_holdout_path = _absolute(holdout_path).resolve()
    root = _absolute(output_root)
    jobs: list[dict[str, Any]] = []
    seen_job_keys: set[tuple[str, str]] = set()
    seen_paths: set[str] = set()
    for freeze_id in selected_ids:
        candidate = freeze_candidates[freeze_id]
        holdout_row = holdout_candidates[freeze_id]
        for scenario in SCENARIOS:
            job_ordinal = len(jobs)
            gpu = gpu_manifest[job_ordinal % len(gpu_manifest)]
            job_root = _job_root(root, freeze_id, scenario["name"])
            manifest_path = job_root / "render_scenario_manifest.json"
            manifest = build_scenario_manifest(scenario)
            command, environment = _build_command(
                candidate,
                scenario,
                physical_gpu=gpu,
                output_root=job_root,
                manifest_path=manifest_path,
            )
            key = (freeze_id, scenario["name"])
            if key in seen_job_keys:
                raise RenderError(f"duplicate render job identity {key}")
            seen_job_keys.add(key)
            paths = (job_root, job_root / "render_qa.json", job_root / "renderings", manifest_path)
            for path in paths:
                absolute_path = str(path.resolve())
                if absolute_path in seen_paths:
                    raise RenderError(f"render evidence path is not globally unique: {path}")
                seen_paths.add(absolute_path)
            jobs.append(
                {
                    "freeze_id": freeze_id,
                    "selected_candidate": dict(candidate),
                    "candidate_identity": _candidate_identity(candidate),
                    "candidate_freeze_path": str(bound_freeze_path),
                    "candidate_freeze_schema": CANDIDATE_FREEZE_SCHEMA,
                    "candidate_freeze_status": CANDIDATE_FREEZE_STATUS,
                    "holdout_path": str(bound_holdout_path),
                    "holdout_schema": HOLDOUT_RECEIPT_SCHEMA,
                    "holdout_status": HOLDOUT_RECEIPT_STATUS,
                    "holdout_candidate_freeze_ids": list(holdout["candidate_freeze_ids"]),
                    "holdout_candidate_id": freeze_id,
                    "holdout_episode_count": holdout_row["episode_count"],
                    "scenario": dict(scenario),
                    "scenario_manifest": manifest,
                    "scenario_manifest_path": str(manifest_path.resolve()),
                    "physical_gpu": gpu,
                    "physical_gpus": list(gpu_manifest),
                    "physical_gpu_domain": list(LEGAL_PHYSICAL_GPUS),
                    "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
                    "job_ordinal": job_ordinal,
                    "logical_gpu": LOGICAL_DEVICE,
                    "render_root": str(root.resolve()),
                    "process_count": 1,
                    "num_envs": EXPECTED_ENV_COUNT,
                    "num_mini_batches": 1,
                    "output_root": str(job_root.resolve()),
                    "qa_path": str((job_root / "render_qa.json").resolve()),
                    "media_root": str((job_root / "renderings").resolve()),
                    "expected_cameras": list(CAMERAS),
                    "command": command,
                    "command_shell": shlex.join(command),
                    "environment": environment,
                    "retry_policy": "none",
                }
            )
    expected_job_count = len(selected_ids) * EXPECTED_SCENARIO_COUNT
    if len(jobs) != expected_job_count:
        raise RenderError("render plan job cardinality does not match the explicit candidate subset")
    payload = {
        "schema": PLAN_SCHEMA,
        "status": "PLAN_ONLY",
        "recorded_at_utc": _utc_now(),
        "source_branch": "A2_Piper",
        "candidate_freeze_path": str(bound_freeze_path),
        "candidate_freeze_schema": CANDIDATE_FREEZE_SCHEMA,
        "candidate_freeze_status": CANDIDATE_FREEZE_STATUS,
        "candidate_freeze_ids": list(freeze_candidates),
        "holdout_path": str(bound_holdout_path),
        "holdout_schema": HOLDOUT_RECEIPT_SCHEMA,
        "holdout_status": HOLDOUT_RECEIPT_STATUS,
        "holdout_candidate_freeze_ids": list(holdout["candidate_freeze_ids"]),
        "render_root": str(root.resolve()),
        "physical_gpus": list(gpu_manifest),
        "physical_gpu_domain": list(LEGAL_PHYSICAL_GPUS),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "gpu_assignment": "JOB_ORDINAL_MODULO_PHYSICAL_GPU_MANIFEST",
        "logical_gpu": LOGICAL_DEVICE,
        "process_count_per_gpu": 1,
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "selected_candidate_ids": selected_ids,
        "selected_candidate_count": len(selected_ids),
        "scenario_count_per_candidate": EXPECTED_SCENARIO_COUNT,
        "camera_count_per_scenario": len(CAMERAS),
        "scenarios": [dict(row) for row in SCENARIOS],
        "cameras": list(CAMERAS),
        "jobs": jobs,
        "qualitative_only": True,
        "success_gate": "NOT_APPLIED",
        "retry_policy": "none",
        "missing_evidence": [],
    }
    _validate_render_plan(payload)
    return payload


def build_plan(
    *,
    freeze_path: str | Path = CANDIDATE_FREEZE_PATH,
    holdout_path: str | Path = HOLDOUT_RECEIPT_PATH,
    output_root: str | Path = RENDER_ROOT,
    candidate_ids: Sequence[str] | None = None,
    physical_gpus: Sequence[int] = DEFAULT_PHYSICAL_GPUS,
) -> dict[str, Any]:
    freeze = _load_candidate_freeze(freeze_path)
    holdout = _load_holdout(holdout_path)
    return build_render_plan(
        freeze,
        holdout,
        output_root=output_root,
        candidate_freeze_path=freeze_path,
        holdout_path=holdout_path,
        candidate_ids=candidate_ids,
        physical_gpus=physical_gpus,
    )


def _job_root(root: Path, freeze_id: str, scenario: str) -> Path:
    return root / freeze_id / scenario


def _media_record(path: Path, media_root: Path) -> tuple[int, str, int, Path]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise RenderError(f"render media must be a regular finalized file: {path}")
    resolved_root = media_root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise RenderError(f"render media path escapes media_root: {path}") from exc
    match = _MEDIA_NAME_RE.fullmatch(path.name)
    if match is None:
        raise RenderError(f"render media filename is not a finalized episode0 camera artifact: {path.name}")
    env_id = int(match.group("env"))
    episode = int(match.group("episode"))
    camera_suffix = match.group("camera")
    camera = "main" if camera_suffix is None else camera_suffix[1:]
    if env_id not in range(EXPECTED_ENV_COUNT) or camera not in CAMERAS:
        raise RenderError(f"render media topology is invalid: {path.name}")
    return env_id, camera, episode, resolved_path


def _classify_render_media(media_root: str | Path) -> dict[str, Any]:
    root = _absolute(media_root)
    if root.is_symlink() or not root.is_dir():
        raise RenderError(f"render media_root must be a regular directory: {root}")
    writing = sorted(path for path in root.rglob("*.writing.mp4") if path.is_file() or path.is_symlink())
    if writing:
        raise RenderError(f"unfinished .writing.mp4 render media remains: {writing[0]}")
    media = sorted(path for path in root.rglob("*.mp4") if path.is_file() or path.is_symlink())
    rows: list[dict[str, Any]] = []
    identities: set[tuple[int, str]] = set()
    paths: list[str] = []
    extra_paths: list[str] = []
    for path in media:
        env_id, camera, episode, resolved_path = _media_record(path, root)
        if episode != 0:
            extra_paths.append(str(resolved_path))
            continue
        identity = (env_id, camera)
        if identity in identities:
            raise RenderError(f"duplicate render media identity env{env_id:04d}/{camera}")
        identities.add(identity)
        paths.append(str(resolved_path))
        rows.append({"env_id": env_id, "camera": camera, "path": str(resolved_path), "episode": 0})
    expected = {(env_id, camera) for env_id in range(EXPECTED_ENV_COUNT) for camera in CAMERAS}
    if identities != expected:
        raise RenderError("render media must contain one episode0 MP4 for every env0..15 and camera")
    rows.sort(key=lambda row: (row["env_id"], CAMERAS.index(row["camera"])))
    paths.sort()
    extra_paths.sort()
    return {
        "media_paths": paths,
        "media_rows": rows,
        "media_count": len(paths),
        "extra_media_paths": extra_paths,
        "extra_media_count": len(extra_paths),
        "extra_media_policy": "PRESERVED_EXCLUDED_NON_EPISODE0",
    }


def _scenario_manifest_for_job(job: Mapping[str, Any]) -> dict[str, Any]:
    manifest = job.get("scenario_manifest")
    if not isinstance(manifest, Mapping):
        raise RenderError("render job must carry its STATIC_RENDER scenario manifest")
    validated = _validate_scenario_manifest(manifest)
    scenario = job.get("scenario")
    if not isinstance(scenario, Mapping) or validated["scenario_id"] != scenario.get("name"):
        raise RenderError("render job scenario and manifest identity disagree")
    params = _scenario_parameters(scenario)
    for row_index, row in enumerate(validated["rows"]):
        for field, expected in params.items():
            if not math.isclose(float(row[field]), expected, rel_tol=0.0, abs_tol=0.0):
                raise RenderError(
                    f"render job manifest scenario parameter disagrees for row {row_index}.{field}"
                )
    return validated


def _canonical_scenario(name: Any) -> dict[str, Any]:
    if not isinstance(name, str):
        raise RenderError("render scenario name must be a string")
    for scenario in SCENARIOS:
        if scenario["name"] == name:
            return dict(scenario)
    raise RenderError(f"unknown render scenario: {name}")


def _validate_render_job(
    job: Mapping[str, Any],
    *,
    render_root: Path,
    selected_candidate: Mapping[str, Any] | None = None,
    physical_gpus: Sequence[int] | None = None,
) -> dict[str, Any]:
    if not isinstance(job, Mapping):
        raise RenderError("render plan job must be an object")
    bound_freeze_path, bound_freeze = _load_bound_candidate_freeze(job.get("candidate_freeze_path"))
    if (
        job.get("candidate_freeze_path") != str(bound_freeze_path)
        or job.get("candidate_freeze_schema") != CANDIDATE_FREEZE_SCHEMA
        or job.get("candidate_freeze_status") != CANDIDATE_FREEZE_STATUS
    ):
        raise RenderError("render job candidate-freeze binding is invalid")
    frozen_candidates = _candidate_by_id(bound_freeze)
    scenario = job.get("scenario")
    if not isinstance(scenario, Mapping):
        raise RenderError("render job must bind one scenario")
    canonical_scenario = _canonical_scenario(scenario.get("name"))
    for field in SCENARIO_SCALAR_FIELDS:
        if scenario.get(field) != canonical_scenario[field]:
            raise RenderError(f"render scenario {scenario.get('name')} has non-canonical {field}")
    manifest = _validate_physical_gpu_manifest(
        physical_gpus if physical_gpus is not None else job.get("physical_gpus"),
        label="render physical_gpus",
    )
    if job.get("physical_gpus") != manifest:
        raise RenderError("render job physical GPU manifest disagrees with plan")
    if job.get("physical_gpu_domain") != list(LEGAL_PHYSICAL_GPUS) or job.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise RenderError("render job physical GPU domain/mapping policy is invalid")
    job_ordinal = job.get("job_ordinal")
    if isinstance(job_ordinal, bool) or not isinstance(job_ordinal, int) or job_ordinal < 0:
        raise RenderError("render job job_ordinal is invalid")
    expected_gpu = manifest[job_ordinal % len(manifest)]
    if isinstance(job.get("physical_gpu"), bool) or job.get("physical_gpu") != expected_gpu:
        raise RenderError("render job physical_gpu does not follow its ordinal/modulo manifest binding")
    if job.get("logical_gpu") != LOGICAL_DEVICE:
        raise RenderError("render job logical_gpu must be cuda:0")
    if job.get("process_count") != 1 or job.get("num_envs") != EXPECTED_ENV_COUNT or job.get("num_mini_batches") != 1:
        raise RenderError("render job process/env/mini-batch topology is invalid")
    if job.get("retry_policy") != "none" or job.get("expected_cameras") != list(CAMERAS):
        raise RenderError("render job retry/camera contract is invalid")
    freeze_id = job.get("freeze_id")
    if not isinstance(freeze_id, str) or not freeze_id:
        raise RenderError("render job freeze_id must be a non-empty string")
    frozen_candidate = frozen_candidates.get(freeze_id)
    if frozen_candidate is None:
        raise RenderError("render job references an unknown candidate-freeze identity")
    bound_candidate = job.get("selected_candidate")
    if not isinstance(bound_candidate, Mapping) or dict(bound_candidate) != dict(frozen_candidate):
        raise RenderError("render job selected_candidate does not match the bound freeze receipt")
    if selected_candidate is not None:
        if dict(bound_candidate) != dict(selected_candidate):
            raise RenderError("render job selected_candidate disagrees with the frozen candidate")
        expected_identity = _candidate_identity(selected_candidate)
    else:
        expected_identity = _candidate_identity(bound_candidate)
    if expected_identity.get("freeze_id", freeze_id) != freeze_id:
        raise RenderError("render job candidate identity disagrees with freeze_id")
    if job.get("candidate_identity") != expected_identity:
        raise RenderError("render job candidate_identity is not canonically bound")
    if job.get("holdout_schema") != HOLDOUT_RECEIPT_SCHEMA or job.get("holdout_status") != HOLDOUT_RECEIPT_STATUS:
        raise RenderError("render job holdout provenance schema/status is invalid")
    holdout_path = job.get("holdout_path")
    if not isinstance(holdout_path, str) or not holdout_path or not Path(holdout_path).is_absolute():
        raise RenderError("render job must bind an absolute holdout receipt path")
    holdout_ids = job.get("holdout_candidate_freeze_ids")
    if (
        not isinstance(holdout_ids, list)
        or len(holdout_ids) != EXPECTED_CANDIDATE_COUNT
        or holdout_ids != list(frozen_candidates)
    ):
        raise RenderError("render job holdout provenance ids are invalid")
    if job.get("holdout_candidate_id") != freeze_id or job.get("holdout_episode_count") != CANONICAL_HOLDOUT_EPISODES:
        raise RenderError("render job holdout candidate binding is invalid")
    holdout = _load_holdout(holdout_path)
    if holdout.get("candidate_freeze_ids") != holdout_ids:
        raise RenderError("render job holdout provenance ids disagree with the bound receipt")
    holdout_row = _holdout_by_id(holdout).get(freeze_id)
    if holdout_row is None or holdout_row.get("candidate") != bound_candidate or holdout_row.get("episode_count") != CANONICAL_HOLDOUT_EPISODES:
        raise RenderError("render job holdout candidate does not bind the selected freeze candidate")
    root = _absolute(str(render_root)).resolve()
    expected_root = _job_root(root, freeze_id, canonical_scenario["name"]).resolve()
    expected_paths = {
        "render_root": str(root),
        "output_root": str(expected_root),
        "scenario_manifest_path": str(expected_root / "render_scenario_manifest.json"),
        "qa_path": str(expected_root / "render_qa.json"),
        "media_root": str(expected_root / "renderings"),
    }
    for field, expected in expected_paths.items():
        if field in job and job[field] != expected:
            raise RenderError(f"render job {field} is not canonically bound")
    if "render_root" not in job:
        raise RenderError("render job must bind render_root")
    _scenario_manifest_for_job(job)
    command = job.get("command")
    if not isinstance(command, list):
        raise RenderError("render job command must be a list")
    command_text = " ".join(str(value) for value in command)
    required_command_fields = (
        "++checkpoint_load_mode=policy_only",
        POLICY_ONLY_OVERRIDE,
        "++algo.config.num_mini_batches=1",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=true",
        "++env.config.a2_v23_route_b_render_enabled=true",
        "++env.config.a2_v23_warm_head_reset_enabled=false",
    )
    if any(field not in command_text for field in required_command_fields):
        raise RenderError("render job command is missing a required qualitative-render override")
    command_values = {str(value) for value in command}
    if _candidate_door_regime(bound_candidate) == "D1":
        if D1_SAMPLER_DISABLE_OVERRIDE not in command_values:
            raise RenderError("render D1 job must disable the training-only sampler")
    elif D1_SAMPLER_DISABLE_OVERRIDE in command_values:
        raise RenderError("render D0 job must not carry the D1 sampler override")
    legacy_fields = (
        "a2_v23_route_b_render_candidate_id",
        "a2_v23_route_b_render_scenario",
        "a2_v23_route_b_render_handle_height_m",
        "a2_v23_route_b_render_door_weight_kg",
        "a2_v23_route_b_render_hinge_max_force_nm",
        "a2_v23_route_b_render_hinge_damping_native",
        "a2_v23_route_b_render_hinge_stiffness_native",
        "++save_rendering_dir=",
    )
    if any(field in command_text for field in legacy_fields):
        raise RenderError("render job command contains an unconsumed legacy override")
    if f"++env.config.a2_v23_route_b_render_manifest_path={expected_paths['scenario_manifest_path']}" not in command_text:
        raise RenderError("render job command manifest path is not canonically bound")
    if f"++env.config.save_rendering_dir={expected_paths['media_root']}" not in command_text:
        raise RenderError("render job command media path is not canonically bound")
    environment = job.get("environment")
    if not isinstance(environment, Mapping) or environment.get("CUDA_VISIBLE_DEVICES") != str(job["physical_gpu"]):
        raise RenderError("render job environment physical GPU binding is invalid")
    if environment.get("ACCELERATE_TORCH_DEVICE") != LOGICAL_DEVICE:
        raise RenderError("render job environment logical GPU binding is invalid")
    return dict(job)


def run_once(job: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one fresh qualitative render scenario with no retry."""

    _validate_render_job(
        job,
        render_root=Path(str(job["render_root"])),
        selected_candidate=job.get("selected_candidate"),
    )
    root = _absolute(str(job["output_root"]))
    if root.exists():
        raise RenderError(f"render scenario root must be fresh: {root}")
    target_python = PROJECT_PYTHON.resolve()
    if not target_python.is_file():
        raise RenderError(f"approved IsaacLab Python is missing: {PROJECT_PYTHON}")
    manifest = _scenario_manifest_for_job(job)
    manifest_path = _absolute(str(job["scenario_manifest_path"]))
    root.mkdir(parents=True, exist_ok=False)
    write_json(manifest_path, manifest)
    command = [str(value) for value in job["command"]]
    environment = {str(key): str(value) for key, value in job["environment"].items()}
    result = subprocess.run(command, cwd=REPO_ROOT, env={**os.environ, **environment}, check=False)
    if result.returncode != 0:
        raise RenderError(f"render scenario exited with returncode={result.returncode}; no retry is permitted")
    media = _classify_render_media(_absolute(str(job["media_root"])))
    scenario = job["scenario"]
    qa_path = _absolute(str(job["qa_path"]))
    qa_payload = {
        "schema": RECEIPT_SCHEMA,
        "status": "QUALITATIVE_RENDER_COMPLETE",
        "recorded_at_utc": _utc_now(),
        "freeze_id": job["freeze_id"],
        "candidate_identity": dict(job["candidate_identity"]),
        "candidate_freeze_path": job["candidate_freeze_path"],
        "candidate_freeze_schema": CANDIDATE_FREEZE_SCHEMA,
        "candidate_freeze_status": CANDIDATE_FREEZE_STATUS,
        "holdout_path": job["holdout_path"],
        "holdout_schema": HOLDOUT_RECEIPT_SCHEMA,
        "holdout_status": HOLDOUT_RECEIPT_STATUS,
        "holdout_candidate_freeze_ids": list(job["holdout_candidate_freeze_ids"]),
        "holdout_candidate_id": job["holdout_candidate_id"],
        "holdout_episode_count": job["holdout_episode_count"],
        "job_ordinal": job["job_ordinal"],
        "scenario": scenario["name"],
        "scenario_parameters": _scenario_parameters(scenario),
        "scenario_manifest_schema": SCENARIO_MANIFEST_SCHEMA,
        "scenario_manifest_status": SCENARIO_MANIFEST_STATUS,
        "scenario_manifest_topology": SCENARIO_MANIFEST_TOPOLOGY,
        "physical_gpu": job["physical_gpu"],
        "physical_gpus": list(job["physical_gpus"]),
        "physical_gpu_domain": list(job["physical_gpu_domain"]),
        "physical_gpu_mapping_policy": job["physical_gpu_mapping_policy"],
        "logical_gpu": LOGICAL_DEVICE,
        "process_count": 1,
        "num_envs": EXPECTED_ENV_COUNT,
        "num_mini_batches": 1,
        "returncode": int(result.returncode),
        "topology": SCENARIO_MANIFEST_TOPOLOGY,
        "cameras": list(CAMERAS),
        "media_paths": media["media_paths"],
        "media_rows": media["media_rows"],
        "media_count": EXPECTED_MEDIA_COUNT,
        "extra_media_paths": media["extra_media_paths"],
        "extra_media_count": media["extra_media_count"],
        "extra_media_policy": media["extra_media_policy"],
        "qa_path": str(qa_path),
        "qualitative_only": True,
        "success_gate": "NOT_APPLIED",
        "policy_quality_claim": False,
        "formal_admission": False,
        "release_receipt": False,
        "retry_count": 0,
        "missing_evidence": [],
    }
    write_json(qa_path, qa_payload)
    return qa_payload


def _validate_qa(job: Mapping[str, Any]) -> dict[str, Any]:
    _validate_render_job(
        job,
        render_root=Path(str(job["render_root"])),
        selected_candidate=job.get("selected_candidate"),
    )
    path = _absolute(str(job["qa_path"]))
    payload = read_json(path)
    if payload.get("schema") != RECEIPT_SCHEMA:
        raise RenderError(f"render QA schema is invalid: {path}")
    if payload.get("status") != "QUALITATIVE_RENDER_COMPLETE":
        raise RenderError(f"render QA status must be QUALITATIVE_RENDER_COMPLETE: {path}")
    if payload.get("freeze_id") != job["freeze_id"] or payload.get("scenario") != job["scenario"]["name"]:
        raise RenderError(f"render QA identity disagrees with plan: {path}")
    expected_identity = job.get("candidate_identity")
    if expected_identity is not None and payload.get("candidate_identity") != expected_identity:
        raise RenderError(f"render QA candidate identity disagrees with plan: {path}")
    if (
        payload.get("physical_gpu") != job["physical_gpu"]
        or payload.get("physical_gpus") != job["physical_gpus"]
        or payload.get("physical_gpu_domain") != job["physical_gpu_domain"]
        or payload.get("physical_gpu_mapping_policy") != job["physical_gpu_mapping_policy"]
        or payload.get("job_ordinal") != job["job_ordinal"]
        or payload.get("logical_gpu") != LOGICAL_DEVICE
    ):
        raise RenderError(f"render QA GPU identity disagrees with plan: {path}")
    for field in (
        "candidate_freeze_path",
        "candidate_freeze_schema",
        "candidate_freeze_status",
        "holdout_path",
        "holdout_schema",
        "holdout_status",
        "holdout_candidate_freeze_ids",
        "holdout_candidate_id",
        "holdout_episode_count",
    ):
        if payload.get(field) != job.get(field):
            raise RenderError(f"render QA provenance field {field} disagrees with plan: {path}")
    if (
        payload.get("topology") != SCENARIO_MANIFEST_TOPOLOGY
        or payload.get("scenario_manifest_schema") != SCENARIO_MANIFEST_SCHEMA
        or payload.get("scenario_manifest_status") != SCENARIO_MANIFEST_STATUS
        or payload.get("scenario_manifest_topology") != SCENARIO_MANIFEST_TOPOLOGY
        or payload.get("num_envs") != EXPECTED_ENV_COUNT
        or payload.get("process_count") != 1
        or payload.get("num_mini_batches") != 1
    ):
        raise RenderError(f"render QA topology is invalid: {path}")
    if payload.get("cameras") != list(CAMERAS):
        raise RenderError(f"render QA cameras must be exactly {list(CAMERAS)}: {path}")
    if payload.get("qualitative_only") is not True or payload.get("success_gate") != "NOT_APPLIED":
        raise RenderError(f"render QA must remain qualitative-only: {path}")
    if payload.get("policy_quality_claim") is not False or payload.get("formal_admission") is not False or payload.get("release_receipt") is not False:
        raise RenderError(f"render QA cannot make a policy, admission, or release claim: {path}")
    if payload.get("retry_count") != 0 or payload.get("returncode") != 0:
        raise RenderError(f"render QA retry/returncode contract is invalid: {path}")
    if payload.get("missing_evidence") != []:
        raise RenderError(f"render QA missing_evidence must be empty: {path}")
    expected_params = _scenario_parameters(job["scenario"])
    if payload.get("scenario_parameters") != expected_params:
        raise RenderError(f"render QA scenario parameters disagree with plan: {path}")
    media_paths = payload.get("media_paths")
    if not isinstance(media_paths, list) or len(media_paths) != EXPECTED_MEDIA_COUNT:
        raise RenderError(f"render QA must contain exactly {EXPECTED_MEDIA_COUNT} media paths: {path}")
    if payload.get("media_count") != EXPECTED_MEDIA_COUNT:
        raise RenderError(f"render QA media_count must be {EXPECTED_MEDIA_COUNT}: {path}")
    actual = _classify_render_media(_absolute(str(job["media_root"])))
    if (
        payload.get("extra_media_paths") != actual["extra_media_paths"]
        or payload.get("extra_media_count") != actual["extra_media_count"]
        or payload.get("extra_media_policy") != actual["extra_media_policy"]
    ):
        raise RenderError(f"render QA extra-media preservation record is invalid: {path}")
    if any(not isinstance(item, str) or not Path(item).is_absolute() for item in media_paths):
        raise RenderError(f"render QA media paths must be absolute paths: {path}")
    expected_paths = [str(Path(item).resolve()) for item in media_paths]
    if len(expected_paths) != EXPECTED_MEDIA_COUNT or len(set(expected_paths)) != EXPECTED_MEDIA_COUNT:
        raise RenderError(f"render QA media paths must be unique absolute paths: {path}")
    if expected_paths != actual["media_paths"] and set(expected_paths) != set(actual["media_paths"]):
        raise RenderError(f"render QA media paths do not match finalized media: {path}")
    media_rows = payload.get("media_rows")
    if media_rows != actual["media_rows"]:
        raise RenderError(f"render QA media_rows do not match recomputed finalized media: {path}")
    return dict(payload)


def _validate_render_plan(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if plan.get("schema") != PLAN_SCHEMA or plan.get("status") != "PLAN_ONLY":
        raise RenderError("render reduction requires a PLAN_ONLY render plan")
    physical_gpus = _validate_physical_gpu_manifest(plan.get("physical_gpus"), label="render plan physical_gpus")
    if plan.get("gpu_assignment") != "JOB_ORDINAL_MODULO_PHYSICAL_GPU_MANIFEST":
        raise RenderError("render plan GPU assignment must be ordinal modulo its manifest")
    if plan.get("physical_gpu_domain") != list(LEGAL_PHYSICAL_GPUS) or plan.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise RenderError("render plan physical GPU domain/mapping policy is invalid")
    if plan.get("logical_gpu") != LOGICAL_DEVICE:
        raise RenderError("render plan GPU contract must use logical cuda:0")
    bound_freeze_path, bound_freeze = _load_bound_candidate_freeze(plan.get("candidate_freeze_path"))
    if (
        plan.get("candidate_freeze_path") != str(bound_freeze_path)
        or plan.get("candidate_freeze_schema") != CANDIDATE_FREEZE_SCHEMA
        or plan.get("candidate_freeze_status") != CANDIDATE_FREEZE_STATUS
    ):
        raise RenderError("render plan candidate-freeze binding is invalid")
    frozen_candidates = _candidate_by_id(bound_freeze)
    frozen_ids = list(frozen_candidates)
    if plan.get("candidate_count") != EXPECTED_CANDIDATE_COUNT:
        raise RenderError("render plan must bind exactly 16 candidates")
    freeze_ids = plan.get("candidate_freeze_ids")
    if (
        not isinstance(freeze_ids, list)
        or len(freeze_ids) != EXPECTED_CANDIDATE_COUNT
        or any(not isinstance(item, str) or not item for item in freeze_ids)
        or len(set(freeze_ids)) != EXPECTED_CANDIDATE_COUNT
        or freeze_ids != frozen_ids
    ):
        raise RenderError("render plan candidate freeze must bind the exact 16 receipt identities")
    holdout_path_value = plan.get("holdout_path")
    if not isinstance(holdout_path_value, str) or not holdout_path_value or not Path(holdout_path_value).is_absolute():
        raise RenderError("render plan must bind an absolute holdout receipt path")
    if plan.get("holdout_schema") != HOLDOUT_RECEIPT_SCHEMA or plan.get("holdout_status") != HOLDOUT_RECEIPT_STATUS:
        raise RenderError("render plan holdout provenance schema/status is invalid")
    holdout = _load_holdout(holdout_path_value)
    if plan.get("holdout_candidate_freeze_ids") != freeze_ids:
        raise RenderError("render plan holdout provenance ids disagree with the freeze")
    if holdout.get("candidate_freeze_ids") != freeze_ids:
        raise RenderError("render plan holdout receipt ids disagree with the freeze")
    if Path(str(holdout["candidate_freeze_path"])).resolve() != bound_freeze_path:
        raise RenderError("render plan holdout candidate-freeze path disagrees with the freeze")
    holdout_candidates = _holdout_by_id(holdout)
    frozen_candidate_rows = _candidate_by_id(bound_freeze)
    if set(holdout_candidates) != set(frozen_candidate_rows):
        raise RenderError("render plan holdout receipt does not cover the full freeze")
    for freeze_id, row in holdout_candidates.items():
        if row.get("candidate") != frozen_candidate_rows[freeze_id] or row.get("episode_count") != CANONICAL_HOLDOUT_EPISODES:
            raise RenderError(f"render plan holdout provenance row is invalid for {freeze_id}")
    selected_ids = plan.get("selected_candidate_ids")
    if (
        not isinstance(selected_ids, list)
        or len(selected_ids) not in (1, 2, 3)
        or any(not isinstance(item, str) or not item for item in selected_ids)
        or len(set(selected_ids)) != len(selected_ids)
        or any(item not in freeze_ids for item in selected_ids)
        or plan.get("selected_candidate_count") != len(selected_ids)
    ):
        raise RenderError("render plan selected_candidate_ids must be an explicit unique 1-3 subset of the freeze")
    render_root_value = plan.get("render_root")
    if not isinstance(render_root_value, str) or not render_root_value or not Path(render_root_value).is_absolute():
        raise RenderError("render plan must bind an absolute render_root")
    if plan.get("qualitative_only") is not True or plan.get("success_gate") != "NOT_APPLIED":
        raise RenderError("render plan must remain qualitative-only")
    if plan.get("scenario_count_per_candidate") != EXPECTED_SCENARIO_COUNT or plan.get("camera_count_per_scenario") != len(CAMERAS):
        raise RenderError("render plan scenario/camera topology is invalid")
    if plan.get("cameras") != list(CAMERAS) or plan.get("retry_policy") != "none":
        raise RenderError("render plan camera/retry contract is invalid")
    scenarios = plan.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != EXPECTED_SCENARIO_COUNT:
        raise RenderError("render plan must bind exactly five scenarios")
    for observed, canonical in zip(scenarios, SCENARIOS):
        if not isinstance(observed, Mapping) or observed.get("name") != canonical["name"]:
            raise RenderError("render plan scenario order is not canonical")
        for field in SCENARIO_SCALAR_FIELDS:
            if observed.get(field) != canonical[field]:
                raise RenderError(f"render plan scenario {canonical['name']} has non-canonical {field}")
    jobs = plan.get("jobs")
    expected_job_count = len(selected_ids) * EXPECTED_SCENARIO_COUNT
    if not isinstance(jobs, list) or len(jobs) != expected_job_count:
        raise RenderError("render plan job count must equal selected candidates × five scenarios")
    expected_scenarios = {row["name"] for row in SCENARIOS}
    selected_candidates: dict[str, Mapping[str, Any]] = {}
    observed_candidate_order: list[str] = []
    seen: set[tuple[str, str]] = set()
    seen_paths: set[str] = set()
    for job_index, job in enumerate(jobs):
        if not isinstance(job, Mapping):
            raise RenderError("render plan job must be an object")
        scenario = job.get("scenario")
        if not isinstance(scenario, Mapping) or scenario.get("name") not in expected_scenarios:
            raise RenderError("render plan job scenario is invalid")
        freeze_id = job.get("freeze_id")
        if freeze_id not in set(selected_ids):
            raise RenderError("render plan job references a candidate outside the explicit subset")
        selected_candidate = job.get("selected_candidate")
        if job.get("candidate_freeze_path") != str(bound_freeze_path):
            raise RenderError("render plan job candidate-freeze path disagrees with the bound receipt")
        if job.get("candidate_freeze_schema") != CANDIDATE_FREEZE_SCHEMA or job.get("candidate_freeze_status") != CANDIDATE_FREEZE_STATUS:
            raise RenderError("render plan job candidate-freeze schema/status is invalid")
        frozen_candidate = frozen_candidates.get(str(freeze_id))
        if frozen_candidate is None or not isinstance(selected_candidate, Mapping) or dict(selected_candidate) != dict(frozen_candidate):
            raise RenderError("render plan job selected_candidate does not match the bound freeze receipt")
        previous = selected_candidates.get(freeze_id)
        if previous is None:
            selected_candidates[freeze_id] = dict(selected_candidate)
            observed_candidate_order.append(str(freeze_id))
        elif dict(previous) != dict(selected_candidate):
            raise RenderError("render plan rebinds one freeze_id to multiple candidates")
        key = (str(freeze_id), str(scenario["name"]))
        if key in seen:
            raise RenderError(f"render plan contains duplicate job {key}")
        seen.add(key)
        _validate_render_job(
            job,
            render_root=Path(render_root_value),
            selected_candidate=selected_candidates[freeze_id],
            physical_gpus=physical_gpus,
        )
        if job.get("job_ordinal") != job_index:
            raise RenderError("render plan job_ordinal must follow ordered job position")
        if job.get("holdout_path") != holdout_path_value or job.get("holdout_candidate_freeze_ids") != freeze_ids:
            raise RenderError("render plan job holdout provenance disagrees with the plan")
        if job.get("holdout_candidate_id") != freeze_id or job.get("holdout_episode_count") != CANONICAL_HOLDOUT_EPISODES:
            raise RenderError("render plan job holdout candidate binding is invalid")
        for field in ("output_root", "scenario_manifest_path", "qa_path", "media_root"):
            path = str(Path(job[field]).resolve())
            if path in seen_paths:
                raise RenderError("render plan contains aliased job/path bindings")
            seen_paths.add(path)
    expected = {(str(job["freeze_id"]), str(job["scenario"]["name"])) for job in jobs}
    if {freeze_id for freeze_id, _ in expected} != set(selected_ids) or len(expected) != expected_job_count:
        raise RenderError("render plan must cover exactly the explicit candidates × five scenarios")
    if set(selected_candidates) != set(selected_ids):
        raise RenderError("render plan selected candidates do not cover the explicit candidate IDs")
    if observed_candidate_order != selected_ids:
        raise RenderError("render plan candidate order does not preserve the explicit candidate-ID input")
    return jobs


def _validate_plan_for_reduction(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return _validate_render_plan(plan)


def reduce_receipt(
    plan: Mapping[str, Any],
    *,
    output: str | Path = RENDER_ROOT / "V23_RENDER_QA.json",
) -> dict[str, Any]:
    jobs = _validate_plan_for_reduction(plan)
    qa_rows = [_validate_qa(job) for job in jobs]
    all_media: list[str] = []
    all_extra_media: list[str] = []
    for row in qa_rows:
        paths = row["media_paths"]
        if len(paths) != EXPECTED_MEDIA_COUNT:
            raise RenderError("each reduced job must contain exactly 48 finalized media paths")
        all_media.extend(str(Path(path).resolve()) for path in paths)
        all_extra_media.extend(str(Path(path).resolve()) for path in row["extra_media_paths"])
    if len(all_media) != len(set(all_media)):
        raise RenderError("reduced render receipt contains duplicate media paths across jobs")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": RECEIPT_STATUS,
        "recorded_at_utc": _utc_now(),
        "source_branch": "A2_Piper",
        "candidate_freeze_path": plan["candidate_freeze_path"],
        "candidate_freeze_schema": CANDIDATE_FREEZE_SCHEMA,
        "candidate_freeze_status": CANDIDATE_FREEZE_STATUS,
        "candidate_freeze_ids": list(plan["candidate_freeze_ids"]),
        "holdout_path": plan["holdout_path"],
        "holdout_schema": HOLDOUT_RECEIPT_SCHEMA,
        "holdout_status": HOLDOUT_RECEIPT_STATUS,
        "holdout_candidate_freeze_ids": list(plan["holdout_candidate_freeze_ids"]),
        "physical_gpus": list(plan["physical_gpus"]),
        "physical_gpu_domain": list(LEGAL_PHYSICAL_GPUS),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "gpu_assignment": "JOB_ORDINAL_MODULO_PHYSICAL_GPU_MANIFEST",
        "logical_gpu": LOGICAL_DEVICE,
        "process_count_per_gpu": 1,
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "selected_candidate_ids": list(plan["selected_candidate_ids"]),
        "selected_candidate_count": plan["selected_candidate_count"],
        "scenario_count_per_candidate": EXPECTED_SCENARIO_COUNT,
        "camera_count_per_scenario": len(CAMERAS),
        "cameras": list(CAMERAS),
        "qualitative_only": True,
        "success_gate": "NOT_APPLIED",
        "jobs": qa_rows,
        "extra_media_paths": all_extra_media,
        "extra_media_count": len(all_extra_media),
        "extra_media_policy": "PRESERVED_EXCLUDED_NON_EPISODE0",
        "missing_evidence": [],
        "invalid_evidence": [],
        "policy_quality_claim": False,
        "formal_admission": False,
        "release_receipt": False,
        "retry_policy": "none",
    }
    write_json(_absolute(output), receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "RUN", "REDUCE"), required=True)
    parser.add_argument("--freeze", type=Path, default=CANDIDATE_FREEZE_PATH)
    parser.add_argument("--holdout", type=Path, default=HOLDOUT_RECEIPT_PATH)
    parser.add_argument("--output-root", type=Path, default=RENDER_ROOT)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--job-index", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--candidate-id",
        dest="candidate_ids_single",
        action="append",
        default=None,
        help="explicit candidate freeze_id (repeat 1-3 times)",
    )
    parser.add_argument(
        "--candidate-ids",
        dest="candidate_ids_multi",
        nargs="+",
        default=None,
        help="explicit candidate freeze_ids (1-3 ids; comma-separated values are accepted)",
    )
    parser.add_argument(
        "--physical-gpus",
        nargs="+",
        default=None,
        help="ordered physical GPU ids (0..7), e.g. --physical-gpus 0 1 2 3",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode != "PLAN" and args.physical_gpus is not None:
            raise RenderError("--physical-gpus is valid only for PLAN")
        if args.mode != "PLAN" and args.plan is None:
            raise RenderError(f"{args.mode} requires an existing persisted --plan")
        candidate_values = []
        if args.candidate_ids_single:
            candidate_values.extend(args.candidate_ids_single)
        if args.candidate_ids_multi:
            candidate_values.extend(args.candidate_ids_multi)
        candidate_ids = _parse_candidate_id_tokens(candidate_values or None)
        physical_gpus = _parse_physical_gpu_tokens(args.physical_gpus) if args.mode == "PLAN" else None
        if args.mode == "PLAN":
            payload = build_plan(
                freeze_path=args.freeze,
                holdout_path=args.holdout,
                output_root=args.output_root,
                candidate_ids=candidate_ids,
                physical_gpus=physical_gpus,
            )
            if args.output is not None:
                write_json(_absolute(args.output), payload)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        elif args.mode == "RUN":
            plan = read_json(_absolute(args.plan))
            if args.job_index is None or args.job_index not in range(len(plan["jobs"])):
                raise RenderError("RUN requires a valid --job-index")
            print(json.dumps(run_once(plan["jobs"][args.job_index]), ensure_ascii=False, sort_keys=True, indent=2))
        else:
            plan = read_json(_absolute(args.plan))
            receipt = reduce_receipt(plan, output=args.output or RENDER_ROOT / "V23_RENDER_QA.json")
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 RENDER FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
