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
    from ._v23_common import REPO_ROOT, V23Error, read_json, write_json
    from .holdout64 import (
        CANDIDATE_FREEZE_PATH,
        CANDIDATE_FREEZE_SCHEMA,
        CANDIDATE_FREEZE_STATUS,
        HOLDOUT_RECEIPT_PATH,
        RECEIPT_SCHEMA as HOLDOUT_RECEIPT_SCHEMA,
        RECEIPT_STATUS as HOLDOUT_RECEIPT_STATUS,
        _absolute,
        _load_candidate_freeze,
    )
except ImportError:  # direct script invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23Error, read_json, write_json
    from scriptsFORhuman.v23.holdout64 import (
        CANDIDATE_FREEZE_PATH,
        CANDIDATE_FREEZE_SCHEMA,
        CANDIDATE_FREEZE_STATUS,
        HOLDOUT_RECEIPT_PATH,
        RECEIPT_SCHEMA as HOLDOUT_RECEIPT_SCHEMA,
        RECEIPT_STATUS as HOLDOUT_RECEIPT_STATUS,
        _absolute,
        _load_candidate_freeze,
    )


PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
PHYSICAL_GPUS = (0, 1)
LOGICAL_DEVICE = "cuda:0"
RENDER_ROOT = REPO_ROOT / "logs_eval/base_v23/render"
PLAN_SCHEMA = "a2_piper_v23_render_plan_v1"
RECEIPT_SCHEMA = "a2_piper_v23_render_qa_receipt_v1"
RECEIPT_STATUS = "V23_RENDER_QA_COMPLETE"
SCENARIO_MANIFEST_SCHEMA = "a2_piper_v23_route_b_render_scenario_manifest_v1"
SCENARIO_MANIFEST_STATUS = "STATIC_RENDER"
SCENARIO_MANIFEST_TOPOLOGY = "render16"
CAMERAS = ("main", "handle_top", "handle_side")
EXPECTED_CANDIDATE_COUNT = 16
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
    payload = read_json(target)
    if payload.get("schema") != HOLDOUT_RECEIPT_SCHEMA:
        raise RenderError(f"holdout receipt schema must be {HOLDOUT_RECEIPT_SCHEMA}: {target}")
    if payload.get("status") != HOLDOUT_RECEIPT_STATUS:
        raise RenderError(f"holdout receipt status must be {HOLDOUT_RECEIPT_STATUS}: {target}")
    if payload.get("physical_gpus") != [0, 1] or payload.get("logical_gpu") != LOGICAL_DEVICE:
        raise RenderError("holdout receipt GPU contract must be physical [0,1] and logical cuda:0")
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
    return payload


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
    if physical_gpu not in PHYSICAL_GPUS:
        raise RenderError(f"physical GPU must be one of {PHYSICAL_GPUS}")
    config_stem = Path(str(candidate["config_path"])).stem
    command = [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+ablation=wbmanip/{config_stem}",
        f"++checkpoint={candidate['checkpoint_path']}",
        "++checkpoint_load_mode=policy_only",
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
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=true",
        f"++env.config.save_rendering_dir={output_root / 'renderings'}",
        "++env.config.a2_v23_route_b_render_enabled=true",
        f"++env.config.a2_v23_route_b_render_manifest_path={manifest_path}",
        "++env.config.a2_v23_warm_head_reset_enabled=false",
        f"++eval_output_dir={output_root}",
    ]
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
) -> dict[str, Any]:
    if not isinstance(freeze, Mapping):
        raise RenderError("candidate freeze must be a mapping")
    bound_freeze_path, bound_freeze = _load_bound_candidate_freeze(str(_absolute(candidate_freeze_path).resolve()))
    if dict(freeze) != dict(bound_freeze):
        raise RenderError("render plan candidate freeze rows do not match the bound receipt")
    freeze_candidates = _candidate_by_id(bound_freeze)
    if holdout is not None:
        holdout_candidates = holdout.get("candidates")
        if not isinstance(holdout_candidates, list) or len(holdout_candidates) != EXPECTED_CANDIDATE_COUNT:
            raise RenderError("holdout candidates must contain exactly 16 rows")
        holdout_ids = {
            item["freeze_id"]
            for item in holdout_candidates
            if isinstance(item, Mapping) and isinstance(item.get("freeze_id"), str)
        }
        if holdout_ids != set(freeze_candidates):
            raise RenderError("holdout/candidate freeze identities do not match")
    root = _absolute(output_root)
    jobs: list[dict[str, Any]] = []
    seen_job_keys: set[tuple[str, str]] = set()
    seen_paths: set[str] = set()
    for candidate_index, (freeze_id, candidate) in enumerate(freeze_candidates.items()):
        for scenario_index, scenario in enumerate(SCENARIOS):
            gpu = PHYSICAL_GPUS[(candidate_index * EXPECTED_SCENARIO_COUNT + scenario_index) % len(PHYSICAL_GPUS)]
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
                    "scenario": dict(scenario),
                    "scenario_manifest": manifest,
                    "scenario_manifest_path": str(manifest_path.resolve()),
                    "physical_gpu": gpu,
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
    if len(jobs) != EXPECTED_CANDIDATE_COUNT * EXPECTED_SCENARIO_COUNT:
        raise RenderError("render plan must contain exactly 80 candidate×scenario jobs")
    payload = {
        "schema": PLAN_SCHEMA,
        "status": "PLAN_ONLY",
        "recorded_at_utc": _utc_now(),
        "source_branch": "A2_Piper",
        "candidate_freeze_path": str(bound_freeze_path),
        "candidate_freeze_schema": CANDIDATE_FREEZE_SCHEMA,
        "candidate_freeze_status": CANDIDATE_FREEZE_STATUS,
        "candidate_freeze_ids": list(freeze_candidates),
        "render_root": str(root.resolve()),
        "physical_gpus": [0, 1],
        "logical_gpu": LOGICAL_DEVICE,
        "process_count_per_gpu": 1,
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
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
) -> dict[str, Any]:
    freeze = _load_candidate_freeze(freeze_path)
    holdout = _load_holdout(holdout_path)
    return build_render_plan(
        freeze,
        holdout,
        output_root=output_root,
        candidate_freeze_path=freeze_path,
    )


def _job_root(root: Path, freeze_id: str, scenario: str) -> Path:
    return root / freeze_id / scenario


def _media_record(path: Path, media_root: Path) -> tuple[int, str, Path]:
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
    if env_id not in range(EXPECTED_ENV_COUNT) or episode != 0 or camera not in CAMERAS:
        raise RenderError(f"render media topology is invalid: {path.name}")
    return env_id, camera, resolved_path


def _classify_render_media(media_root: str | Path) -> dict[str, Any]:
    root = _absolute(media_root)
    if root.is_symlink() or not root.is_dir():
        raise RenderError(f"render media_root must be a regular directory: {root}")
    writing = sorted(path for path in root.rglob("*.writing.mp4") if path.is_file() or path.is_symlink())
    if writing:
        raise RenderError(f"unfinished .writing.mp4 render media remains: {writing[0]}")
    media = sorted(path for path in root.rglob("*.mp4") if path.is_file() or path.is_symlink())
    if len(media) != EXPECTED_MEDIA_COUNT:
        raise RenderError(f"render media must contain exactly {EXPECTED_MEDIA_COUNT} finalized MP4s; got {len(media)}")
    rows: list[dict[str, Any]] = []
    identities: set[tuple[int, str]] = set()
    paths: list[str] = []
    for path in media:
        env_id, camera, resolved_path = _media_record(path, root)
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
    return {"media_paths": paths, "media_rows": rows, "media_count": len(paths)}


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
    if isinstance(job.get("physical_gpu"), bool) or job.get("physical_gpu") not in PHYSICAL_GPUS:
        raise RenderError("render job physical_gpu must be 0 or 1")
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
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=true",
        "++env.config.a2_v23_route_b_render_enabled=true",
        "++env.config.a2_v23_warm_head_reset_enabled=false",
    )
    if any(field not in command_text for field in required_command_fields):
        raise RenderError("render job command is missing a required qualitative-render override")
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
        "scenario": scenario["name"],
        "scenario_parameters": _scenario_parameters(scenario),
        "scenario_manifest_schema": SCENARIO_MANIFEST_SCHEMA,
        "scenario_manifest_status": SCENARIO_MANIFEST_STATUS,
        "scenario_manifest_topology": SCENARIO_MANIFEST_TOPOLOGY,
        "physical_gpu": job["physical_gpu"],
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
    if payload.get("physical_gpu") != job["physical_gpu"] or payload.get("logical_gpu") != LOGICAL_DEVICE:
        raise RenderError(f"render QA GPU identity disagrees with plan: {path}")
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
    if plan.get("physical_gpus") != [0, 1] or plan.get("logical_gpu") != LOGICAL_DEVICE:
        raise RenderError("render plan GPU contract must be physical [0,1] and logical cuda:0")
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
    if not isinstance(jobs, list) or len(jobs) != EXPECTED_CANDIDATE_COUNT * EXPECTED_SCENARIO_COUNT:
        raise RenderError("render plan must contain exactly 80 jobs")
    expected_scenarios = {row["name"] for row in SCENARIOS}
    selected_candidates: dict[str, Mapping[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    seen_paths: set[str] = set()
    for job in jobs:
        if not isinstance(job, Mapping):
            raise RenderError("render plan job must be an object")
        scenario = job.get("scenario")
        if not isinstance(scenario, Mapping) or scenario.get("name") not in expected_scenarios:
            raise RenderError("render plan job scenario is invalid")
        freeze_id = job.get("freeze_id")
        if freeze_id not in set(freeze_ids):
            raise RenderError("render plan job references an unknown frozen candidate")
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
        )
        for field in ("output_root", "scenario_manifest_path", "qa_path", "media_root"):
            path = str(Path(job[field]).resolve())
            if path in seen_paths:
                raise RenderError("render plan contains aliased job/path bindings")
            seen_paths.add(path)
    expected = {(str(job["freeze_id"]), str(job["scenario"]["name"])) for job in jobs}
    if {freeze_id for freeze_id, _ in expected} != set(freeze_ids) or len(expected) != 80:
        raise RenderError("render plan must cover exactly 16 candidates × 5 scenarios")
    if set(selected_candidates) != set(freeze_ids):
        raise RenderError("render plan selected candidates do not cover the exact 16 freeze ids")
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
    for row in qa_rows:
        paths = row["media_paths"]
        if len(paths) != EXPECTED_MEDIA_COUNT:
            raise RenderError("each reduced job must contain exactly 48 finalized media paths")
        all_media.extend(str(Path(path).resolve()) for path in paths)
    if len(all_media) != len(set(all_media)):
        raise RenderError("reduced render receipt contains duplicate media paths across jobs")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": RECEIPT_STATUS,
        "recorded_at_utc": _utc_now(),
        "source_branch": "A2_Piper",
        "physical_gpus": [0, 1],
        "logical_gpu": LOGICAL_DEVICE,
        "process_count_per_gpu": 1,
        "candidate_freeze_ids": list(plan["candidate_freeze_ids"]),
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "scenario_count_per_candidate": EXPECTED_SCENARIO_COUNT,
        "camera_count_per_scenario": len(CAMERAS),
        "cameras": list(CAMERAS),
        "qualitative_only": True,
        "success_gate": "NOT_APPLIED",
        "jobs": qa_rows,
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "PLAN":
            payload = build_plan(freeze_path=args.freeze, holdout_path=args.holdout, output_root=args.output_root)
            if args.output is not None:
                write_json(_absolute(args.output), payload)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        elif args.mode == "RUN":
            plan = read_json(_absolute(args.plan)) if args.plan is not None else build_plan(freeze_path=args.freeze, holdout_path=args.holdout, output_root=args.output_root)
            if args.job_index is None or args.job_index not in range(len(plan["jobs"])):
                raise RenderError("RUN requires a valid --job-index")
            print(json.dumps(run_once(plan["jobs"][args.job_index]), ensure_ascii=False, sort_keys=True, indent=2))
        else:
            plan = read_json(_absolute(args.plan)) if args.plan is not None else build_plan(freeze_path=args.freeze, holdout_path=args.holdout, output_root=args.output_root)
            receipt = reduce_receipt(plan, output=args.output or RENDER_ROOT / "V23_RENDER_QA.json")
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 RENDER FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
