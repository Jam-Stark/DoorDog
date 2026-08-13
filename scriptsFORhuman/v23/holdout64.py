"""Strict holdout64 planner/runner/reducer for frozen Route-B candidates.

Each frozen candidate receives four fresh canonical16 jobs (seeds 3--6), for
exactly 64 episode records.  The runner is one-shot per job, uses an explicit
ordered physical-GPU manifest from 0--7 with logical ``cuda:0``, and never
retries or silently fills evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23Error, V23_CELL_FACTORS, V23_GPU_SUBWAVES, read_json, write_json
    from .route_b_analysis import (
        CANDIDATE_FREEZE_SCHEMA,
        CANDIDATE_FREEZE_STATUS,
        CANDIDATE_KEYS,
        CANDIDATE_FREEZE_PATH,
        SUBWAVE_ORDER,
        _canonical_candidates,
        _freeze_id,
        _validate_candidate,
    )
except ImportError:  # direct script invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23Error, V23_CELL_FACTORS, V23_GPU_SUBWAVES, read_json, write_json
    from scriptsFORhuman.v23.route_b_analysis import (
        CANDIDATE_FREEZE_SCHEMA,
        CANDIDATE_FREEZE_STATUS,
        CANDIDATE_KEYS,
        CANDIDATE_FREEZE_PATH,
        SUBWAVE_ORDER,
        _canonical_candidates,
        _freeze_id,
        _validate_candidate,
    )


PROJECT_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
LEGAL_PHYSICAL_GPUS = tuple(range(8))
PHYSICAL_GPUS = LEGAL_PHYSICAL_GPUS
DEFAULT_PHYSICAL_GPUS = LEGAL_PHYSICAL_GPUS
PHYSICAL_GPU_MAPPING_POLICY = "CANONICAL_JOB_ORDINAL_MODULO_ORDERED_SELECTED_LIST"
LOGICAL_DEVICE = "cuda:0"
D1_SAMPLER_DISABLE_OVERRIDE = "++env.config.a2_v23_d1_sampler_enabled=false"
HOLDOUT_SEEDS = (3, 4, 5, 6)
EPISODES_PER_SEED = 16
CANONICAL_EPISODES = 64
HOLDOUT_ROOT = REPO_ROOT / "logs_eval/base_v23/holdout64"
HOLDOUT_RECEIPT_PATH = HOLDOUT_ROOT / "V23_HOLDOUT64.json"
PLAN_SCHEMA = "a2_piper_v23_holdout64_plan_v1"
RAW_SCHEMA = "a2_piper_v23_holdout64_raw_v1"
RAW_STATUS = "RUNTIME_VERIFIED"
RECEIPT_SCHEMA = "a2_piper_v23_holdout64_receipt_v1"
RECEIPT_STATUS = "V23_HOLDOUT64_COMPLETE"
EXPECTED_CANDIDATE_COUNT = 16


class Holdout64Error(V23Error):
    """A holdout candidate, raw record, or topology is invalid."""


def _candidate_door_regime(candidate: Mapping[str, Any]) -> str:
    cell = candidate.get("cell")
    factors = V23_CELL_FACTORS.get(cell)
    if not isinstance(factors, Mapping) or factors.get("door_regime") not in {"D0", "D1"}:
        raise Holdout64Error(f"candidate cell has no canonical door regime: {cell!r}")
    return str(factors["door_regime"])


def _validate_physical_gpu_manifest(value: Any, *, label: str = "physical_gpus") -> list[int]:
    """Validate an ordered, unique physical-GPU manifest for this run."""

    if not isinstance(value, (list, tuple)) or not value:
        raise Holdout64Error(f"{label} must be a non-empty ordered list")
    manifest: list[int] = []
    seen: set[int] = set()
    for index, gpu in enumerate(value):
        if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu not in LEGAL_PHYSICAL_GPUS:
            raise Holdout64Error(f"{label}[{index}] must be a physical GPU in 0..7")
        if gpu in seen:
            raise Holdout64Error(f"{label} must contain unique physical GPUs")
        seen.add(gpu)
        manifest.append(gpu)
    return manifest


def _parse_physical_gpu_tokens(values: Sequence[str] | None) -> list[int]:
    """Parse CLI GPU tokens while preserving the explicit user order."""

    if values is None:
        return list(DEFAULT_PHYSICAL_GPUS)
    tokens: list[str] = []
    for value in values:
        tokens.extend(part.strip() for part in str(value).split(","))
    if not tokens or any(not token for token in tokens):
        raise Holdout64Error("--physical-gpus requires one or more GPU ids in 0..7")
    try:
        parsed = [int(token) for token in tokens]
    except ValueError as exc:
        raise Holdout64Error("--physical-gpus values must be integer GPU ids in 0..7") from exc
    return _validate_physical_gpu_manifest(parsed, label="--physical-gpus")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _read_json_any(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise Holdout64Error(f"holdout evidence is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Holdout64Error(f"holdout evidence is not valid JSON: {path}") from exc


def _expected_candidate_identity_set() -> set[tuple[str, int, str]]:
    return {
        (subwave, int(V23_GPU_SUBWAVES[subwave]["seed"]), cell)
        for subwave in SUBWAVE_ORDER
        for cell in V23_GPU_SUBWAVES[subwave]["cells"]
    }


def _validate_candidate_freeze_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != CANDIDATE_FREEZE_SCHEMA:
        raise Holdout64Error(f"candidate freeze schema must be {CANDIDATE_FREEZE_SCHEMA}")
    if payload.get("status") != CANDIDATE_FREEZE_STATUS:
        raise Holdout64Error(f"candidate freeze status must be {CANDIDATE_FREEZE_STATUS}")
    _validate_physical_gpu_manifest(payload.get("physical_gpus"), label="candidate freeze physical_gpus")
    if payload.get("logical_gpu") != LOGICAL_DEVICE:
        raise Holdout64Error("candidate freeze GPU contract must use logical cuda:0")
    if payload.get("candidate_count") != EXPECTED_CANDIDATE_COUNT:
        raise Holdout64Error("candidate freeze must contain exactly 16 candidates")
    candidates = payload.get("selected_candidates")
    if not isinstance(candidates, list) or len(candidates) != EXPECTED_CANDIDATE_COUNT:
        raise Holdout64Error("candidate freeze selected_candidates must contain exactly 16 rows")
    normalized: list[dict[str, Any]] = []
    identities: set[tuple[str, int, str]] = set()
    for index, item in enumerate(candidates):
        if not isinstance(item, Mapping):
            raise Holdout64Error(f"candidate freeze selected_candidates[{index}] must be an object")
        expected = set(CANDIDATE_KEYS) | {"freeze_id", "evidence_status"}
        if set(item) != expected:
            raise Holdout64Error(f"candidate freeze selected_candidates[{index}] key set is invalid")
        base = {key: item[key] for key in CANDIDATE_KEYS}
        _validate_candidate(base, index=index)
        identity = (base["subwave"], base["seed"], base["cell"])
        if identity in identities:
            raise Holdout64Error(f"candidate freeze duplicates identity {identity}")
        identities.add(identity)
        if item["freeze_id"] != _freeze_id(base):
            raise Holdout64Error(f"candidate freeze selected_candidates[{index}] freeze_id is invalid")
        if item["evidence_status"] != "EVIDENCE_COMPLETE_FROM_THREE_ROUTE_B_RECEIPTS":
            raise Holdout64Error(f"candidate freeze selected_candidates[{index}] evidence status is invalid")
        normalized.append(dict(item))
    if identities != _expected_candidate_identity_set():
        raise Holdout64Error("candidate freeze identities are not exactly the 16 canonical Route-B candidates")
    canonical = _canonical_candidates(
        [{key: item[key] for key in CANDIDATE_KEYS} for item in normalized],
        name="candidate freeze",
    )
    by_id = {item["freeze_id"]: item for item in normalized}
    if normalized != [by_id[_freeze_id(item)] for item in canonical]:
        raise Holdout64Error("candidate freeze selected_candidates are not in canonical order")
    return dict(payload)


def _load_candidate_freeze(path: str | Path) -> dict[str, Any]:
    target = _absolute(path)
    payload = read_json(target)
    return _validate_candidate_freeze_payload(payload)


def _candidate_rows(freeze: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = _validate_candidate_freeze_payload(freeze)
    return [dict(item) for item in payload["selected_candidates"]]


def _job_root(output_root: Path, freeze_id: str, seed: int) -> Path:
    return output_root / freeze_id / f"seed{seed}" / "canonical16"


def _raw_paths(job_root: Path) -> tuple[Path, Path]:
    return job_root / "a2_v14_per_env_records.json", job_root / "stage2_step_trace.json"


def _load_bound_candidate_freeze(path_value: Any) -> dict[str, Any]:
    if not isinstance(path_value, str) or not path_value or not Path(path_value).is_absolute():
        raise Holdout64Error("holdout plan must bind an absolute candidate-freeze receipt path")
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise Holdout64Error(f"bound candidate-freeze receipt is missing or non-regular: {path}")
    return _load_candidate_freeze(path)


def _validate_holdout_job(
    job: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    candidate_freeze_path: Path,
    holdout_root: Path,
    index: int,
    physical_gpus: Sequence[int],
) -> tuple[str, int, tuple[str, int, str]]:
    expected_candidate_fields = set(CANDIDATE_KEYS) | {"freeze_id", "evidence_status"}
    if not isinstance(job, Mapping):
        raise Holdout64Error(f"holdout job {index} is not an object")
    bound_candidate = job.get("candidate")
    if not isinstance(bound_candidate, Mapping) or set(bound_candidate) != expected_candidate_fields:
        raise Holdout64Error(f"holdout job {index} does not bind one strict candidate identity")
    if dict(bound_candidate) != dict(candidate):
        raise Holdout64Error(f"holdout job {index} candidate does not match the bound freeze receipt")
    base = {key: bound_candidate[key] for key in CANDIDATE_KEYS}
    _validate_candidate(base, index=index)
    freeze_id = bound_candidate.get("freeze_id")
    if freeze_id != _freeze_id(base) or bound_candidate.get("evidence_status") != "EVIDENCE_COMPLETE_FROM_THREE_ROUTE_B_RECEIPTS":
        raise Holdout64Error(f"holdout job {index} candidate freeze identity is invalid")
    if job.get("freeze_id") != freeze_id:
        raise Holdout64Error(f"holdout job {index} top-level freeze_id disagrees with candidate")
    if job.get("candidate_freeze_path") != str(candidate_freeze_path):
        raise Holdout64Error(f"holdout job {index} candidate-freeze path binding is invalid")
    if job.get("holdout_root") != str(holdout_root):
        raise Holdout64Error(f"holdout job {index} holdout root binding is invalid")
    seed = job.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed not in HOLDOUT_SEEDS:
        raise Holdout64Error(f"holdout job {index} has invalid partition seed")
    if job.get("partition_id") != f"seed{seed}_canonical16":
        raise Holdout64Error(f"holdout job {index} partition identity is invalid")
    manifest = _validate_physical_gpu_manifest(physical_gpus)
    job_ordinal = job.get("job_ordinal")
    if isinstance(job_ordinal, bool) or not isinstance(job_ordinal, int) or job_ordinal < 0:
        raise Holdout64Error(f"holdout job {index} job_ordinal is invalid")
    if job.get("physical_gpus") != manifest:
        raise Holdout64Error(f"holdout job {index} physical GPU manifest disagrees with plan")
    if job.get("physical_gpu_domain") != list(LEGAL_PHYSICAL_GPUS) or job.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise Holdout64Error(f"holdout job {index} physical GPU domain/mapping policy is invalid")
    expected_gpu = manifest[job_ordinal % len(manifest)]
    if job.get("physical_gpu") != expected_gpu or job.get("logical_gpu") != LOGICAL_DEVICE:
        raise Holdout64Error(f"holdout job {index} GPU binding is invalid")
    environment = job.get("environment")
    if not isinstance(environment, Mapping) or environment.get("CUDA_VISIBLE_DEVICES") != str(expected_gpu) or environment.get("ACCELERATE_TORCH_DEVICE") != LOGICAL_DEVICE:
        raise Holdout64Error(f"holdout job {index} environment GPU binding is invalid")
    command = job.get("command")
    if not isinstance(command, list) or "++algo.config.num_mini_batches=1" not in {str(value) for value in command}:
        raise Holdout64Error(f"holdout job {index} command mini-batch contract is invalid")
    command_values = {str(value) for value in command}
    if _candidate_door_regime(bound_candidate) == "D1":
        if D1_SAMPLER_DISABLE_OVERRIDE not in command_values:
            raise Holdout64Error(f"holdout D1 job {index} must disable the training-only sampler")
    elif D1_SAMPLER_DISABLE_OVERRIDE in command_values:
        raise Holdout64Error(f"holdout D0 job {index} must not carry the D1 sampler override")
    if job.get("process_count") != 1 or job.get("num_envs") != EPISODES_PER_SEED or job.get("episode_count") != EPISODES_PER_SEED:
        raise Holdout64Error(f"holdout job {index} topology is not canonical16")
    if job.get("num_mini_batches") != 1 or job.get("retry_policy") != "none":
        raise Holdout64Error(f"holdout job {index} retry/mini-batch contract is invalid")
    if job.get("job_id") != f"{freeze_id}:{job['partition_id']}":
        raise Holdout64Error(f"holdout job {index} job_id binding is invalid")
    expected_root = _job_root(holdout_root, str(freeze_id), seed).resolve()
    expected_raw, expected_trace = _raw_paths(expected_root)
    expected_receipt = expected_root / "run_receipt.json"
    expected_bindings = {
        "checkpoint_path": str(bound_candidate["checkpoint_path"]),
        "config_path": str(bound_candidate["config_path"]),
        "scenario_path": str(bound_candidate["scenario_path"]),
        "output_root": str(expected_root),
        "raw_records_path": str(expected_raw),
        "trace_path": str(expected_trace),
        "job_receipt_path": str(expected_receipt),
    }
    for field, expected in expected_bindings.items():
        observed = job.get(field)
        if not isinstance(observed, str) or observed != expected:
            raise Holdout64Error(f"holdout job {index} {field} is not canonically bound")
    return str(freeze_id), seed, (base["subwave"], base["seed"], base["cell"])


def _validate_plan_topology(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA or plan.get("status") != "PLAN_ONLY":
        raise Holdout64Error("holdout topology requires a PLAN_ONLY plan")
    if plan.get("source_branch") != "A2_Piper":
        raise Holdout64Error("holdout plan source_branch must be A2_Piper")
    if plan.get("candidate_freeze_schema") != CANDIDATE_FREEZE_SCHEMA:
        raise Holdout64Error("holdout plan is not bound to the candidate freeze schema")
    if plan.get("candidate_freeze_status") != CANDIDATE_FREEZE_STATUS:
        raise Holdout64Error("holdout plan is not bound to the complete candidate freeze status")
    candidate_freeze_path = Path(plan.get("candidate_freeze_path", "")).resolve()
    freeze = _load_bound_candidate_freeze(plan.get("candidate_freeze_path"))
    frozen_candidates = _candidate_rows(freeze)
    frozen_ids = [row["freeze_id"] for row in frozen_candidates]
    if plan.get("candidate_freeze_ids") != frozen_ids:
        raise Holdout64Error("holdout plan candidate ids do not match the validated freeze receipt")
    holdout_root_value = plan.get("holdout_root")
    if not isinstance(holdout_root_value, str) or not holdout_root_value or not Path(holdout_root_value).is_absolute():
        raise Holdout64Error("holdout plan must bind an absolute canonical holdout_root")
    holdout_root = Path(holdout_root_value).resolve()
    physical_gpus = _validate_physical_gpu_manifest(plan.get("physical_gpus"), label="holdout plan physical_gpus")
    if plan.get("logical_gpu") != LOGICAL_DEVICE:
        raise Holdout64Error("holdout plan GPU contract must use logical cuda:0")
    if plan.get("gpu_assignment") != "JOB_ORDINAL_MODULO_PHYSICAL_GPU_MANIFEST":
        raise Holdout64Error("holdout plan GPU assignment must be ordinal modulo its manifest")
    if plan.get("physical_gpu_domain") != list(LEGAL_PHYSICAL_GPUS) or plan.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise Holdout64Error("holdout plan physical GPU domain/mapping policy is invalid")
    if plan.get("process_count_per_gpu") != 1:
        raise Holdout64Error("holdout plan process count must be one per physical GPU")
    if plan.get("holdout_seeds") != list(HOLDOUT_SEEDS):
        raise Holdout64Error("holdout plan partitions must be seeds 3,4,5,6")
    if plan.get("episodes_per_seed") != EPISODES_PER_SEED or plan.get("canonical_episodes_per_candidate") != CANONICAL_EPISODES:
        raise Holdout64Error("holdout plan episode topology must be canonical16 and canonical64")
    if plan.get("retry_policy") != "none":
        raise Holdout64Error("holdout plan retry policy must be none")
    if plan.get("candidate_count") != EXPECTED_CANDIDATE_COUNT:
        raise Holdout64Error("holdout plan must bind exactly 16 candidates")
    jobs = plan.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != EXPECTED_CANDIDATE_COUNT * len(HOLDOUT_SEEDS):
        raise Holdout64Error("holdout plan must contain exactly 16 candidates x 4 partitions")
    candidate_by_id = {row["freeze_id"]: row for row in frozen_candidates}
    candidate_ids: set[str] = set()
    candidate_identity_keys: set[tuple[str, int, str]] = set()
    combinations: set[tuple[str, int]] = set()
    raw_paths: set[str] = set()
    trace_paths: set[str] = set()
    evidence_paths: set[str] = set()
    for index, job in enumerate(jobs):
        if not isinstance(job, Mapping):
            raise Holdout64Error(f"holdout job {index} is not an object")
        freeze_id = job.get("freeze_id")
        candidate = candidate_by_id.get(freeze_id)
        if candidate is None:
            raise Holdout64Error(f"holdout job {index} references an unknown frozen candidate")
        freeze_id, seed, identity = _validate_holdout_job(
            job,
            candidate=candidate,
            candidate_freeze_path=candidate_freeze_path,
            holdout_root=holdout_root,
            index=index,
            physical_gpus=physical_gpus,
        )
        if job.get("job_ordinal") != index:
            raise Holdout64Error(f"holdout job {index} job_ordinal must equal its ordered plan index")
        candidate_identity_keys.add(identity)
        candidate_ids.add(str(freeze_id))
        combination = (str(freeze_id), seed)
        if combination in combinations:
            raise Holdout64Error(f"holdout plan duplicates partition {combination}")
        combinations.add(combination)
        raw_path = str(_absolute(job["raw_records_path"]).resolve())
        trace_path = str(_absolute(job["trace_path"]).resolve())
        receipt_path = str(_absolute(job["job_receipt_path"]).resolve())
        if raw_path in evidence_paths:
            raise Holdout64Error(f"holdout plan aliases raw record path: {raw_path}")
        if trace_path in evidence_paths:
            raise Holdout64Error(f"holdout plan aliases trace path: {trace_path}")
        raw_paths.add(raw_path)
        trace_paths.add(trace_path)
        if receipt_path in evidence_paths:
            raise Holdout64Error(f"holdout plan aliases job receipt path: {receipt_path}")
        evidence_paths.update((raw_path, trace_path, receipt_path))
    if len(candidate_ids) != EXPECTED_CANDIDATE_COUNT:
        raise Holdout64Error("holdout plan does not bind exactly 16 unique candidate identities")
    if candidate_identity_keys != _expected_candidate_identity_set():
        raise Holdout64Error("holdout plan candidate identities are not the exact 16 frozen identities")
    if combinations != {(candidate_id, seed) for candidate_id in candidate_ids for seed in HOLDOUT_SEEDS}:
        raise Holdout64Error("holdout plan partitions are not exactly candidates x seeds3..6")
    if len(raw_paths) != len(jobs) or len(trace_paths) != len(jobs) or len(evidence_paths) != len(jobs) * 3:
        raise Holdout64Error("holdout plan raw/trace paths are not globally unique")
    return freeze


def _build_command(candidate: Mapping[str, Any], *, seed: int, physical_gpu: int, output_root: Path) -> tuple[list[str], dict[str, str]]:
    if physical_gpu not in LEGAL_PHYSICAL_GPUS:
        raise Holdout64Error(f"physical GPU must be one of {LEGAL_PHYSICAL_GPUS}")
    freeze_id = str(candidate["freeze_id"])
    config_stem = Path(str(candidate["config_path"])).stem
    command = [
        str(PROJECT_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+ablation=wbmanip/{config_stem}",
        f"++checkpoint={candidate['checkpoint_path']}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++num_envs=16",
        "++num_gpus=1",
        "++multi_gpu=false",
        f"++seed={seed}",
        "++headless=true",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++algo.config.num_mini_batches=1",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.num_eval_episodes=16",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++env.config.a2_v23_route_b_candidate_id={freeze_id}",
        f"++env.config.a2_v23_route_b_candidate_config={candidate['config_path']}",
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


def build_holdout_plan(
    freeze: Mapping[str, Any],
    *,
    output_root: str | Path = HOLDOUT_ROOT,
    candidate_freeze_path: str | Path = CANDIDATE_FREEZE_PATH,
    physical_gpus: Sequence[int] = DEFAULT_PHYSICAL_GPUS,
) -> dict[str, Any]:
    """Build all one-shot canonical16 jobs without launching Isaac Sim."""

    if freeze.get("schema") != CANDIDATE_FREEZE_SCHEMA or freeze.get("status") != CANDIDATE_FREEZE_STATUS:
        raise Holdout64Error("holdout requires a complete candidate freeze")
    root = _absolute(output_root).resolve()
    freeze_path = _absolute(candidate_freeze_path).resolve()
    gpu_manifest = _validate_physical_gpu_manifest(physical_gpus, label="physical_gpus")
    frozen_candidates = _candidate_rows(freeze)
    candidate_freeze_ids = [candidate["freeze_id"] for candidate in frozen_candidates]
    jobs: list[dict[str, Any]] = []
    for candidate in frozen_candidates:
        freeze_id = str(candidate["freeze_id"])
        for seed in HOLDOUT_SEEDS:
            job_ordinal = len(jobs)
            gpu = gpu_manifest[job_ordinal % len(gpu_manifest)]
            job_root = _job_root(root, freeze_id, seed)
            command, environment = _build_command(candidate, seed=seed, physical_gpu=gpu, output_root=job_root)
            raw_path, trace_path = _raw_paths(job_root)
            jobs.append(
                {
                    "freeze_id": freeze_id,
                    "candidate": dict(candidate),
                    "candidate_freeze_path": str(freeze_path),
                    "holdout_root": str(root),
                    "physical_gpus": list(gpu_manifest),
                    "physical_gpu_domain": list(LEGAL_PHYSICAL_GPUS),
                    "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
                    "job_ordinal": job_ordinal,
                    "job_id": f"{freeze_id}:seed{seed}_canonical16",
                    "checkpoint_path": str(candidate["checkpoint_path"]),
                    "config_path": str(candidate["config_path"]),
                    "scenario_path": str(candidate["scenario_path"]),
                    "seed": seed,
                    "partition_id": f"seed{seed}_canonical16",
                    "physical_gpu": gpu,
                    "logical_gpu": LOGICAL_DEVICE,
                    "process_count": 1,
                    "num_envs": EPISODES_PER_SEED,
                    "num_eval_episodes": EPISODES_PER_SEED,
                    "num_mini_batches": 1,
                    "episode_count": EPISODES_PER_SEED,
                    "output_root": str(job_root),
                    "raw_records_path": str(raw_path),
                    "trace_path": str(trace_path),
                    "job_receipt_path": str(job_root / "run_receipt.json"),
                    "command": command,
                    "command_shell": shlex.join(command),
                    "environment": environment,
                    "retry_policy": "none",
                }
            )
    expected = len(frozen_candidates) * len(HOLDOUT_SEEDS)
    if len(jobs) != expected:
        raise Holdout64Error("holdout job cardinality is inconsistent")
    return {
        "schema": PLAN_SCHEMA,
        "status": "PLAN_ONLY",
        "recorded_at_utc": _utc_now(),
        "source_branch": "A2_Piper",
        "candidate_freeze_schema": CANDIDATE_FREEZE_SCHEMA,
        "candidate_freeze_status": CANDIDATE_FREEZE_STATUS,
        "candidate_freeze_path": str(freeze_path),
        "candidate_freeze_ids": candidate_freeze_ids,
        "holdout_root": str(root),
        "physical_gpus": list(gpu_manifest),
        "physical_gpu_domain": list(LEGAL_PHYSICAL_GPUS),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "gpu_assignment": "JOB_ORDINAL_MODULO_PHYSICAL_GPU_MANIFEST",
        "logical_gpu": LOGICAL_DEVICE,
        "process_count_per_gpu": 1,
        "holdout_seeds": list(HOLDOUT_SEEDS),
        "episodes_per_seed": EPISODES_PER_SEED,
        "canonical_episodes_per_candidate": CANONICAL_EPISODES,
        "candidate_count": len(frozen_candidates),
        "jobs": jobs,
        "retry_policy": "none",
        "missing_evidence": [],
        "qualitative_only": False,
    }


def build_plan(
    *,
    freeze_path: str | Path = CANDIDATE_FREEZE_PATH,
    output_root: str | Path = HOLDOUT_ROOT,
    physical_gpus: Sequence[int] = DEFAULT_PHYSICAL_GPUS,
) -> dict[str, Any]:
    payload = build_holdout_plan(
        _load_candidate_freeze(freeze_path),
        output_root=output_root,
        candidate_freeze_path=freeze_path,
        physical_gpus=physical_gpus,
    )
    _validate_plan_topology(payload)
    return payload


def run_once(job: Mapping[str, Any]) -> dict[str, Any]:
    """Execute exactly one fresh holdout job; no retry or resume."""

    candidate_freeze_path = Path(job.get("candidate_freeze_path", "")).resolve()
    freeze = _load_bound_candidate_freeze(job.get("candidate_freeze_path"))
    candidates = {row["freeze_id"]: row for row in _candidate_rows(freeze)}
    freeze_id = job.get("freeze_id")
    if freeze_id not in candidates:
        raise Holdout64Error("holdout job references an unknown candidate-freeze identity")
    holdout_root = Path(job.get("holdout_root", ""))
    _validate_holdout_job(
        job,
        candidate=candidates[freeze_id],
        candidate_freeze_path=candidate_freeze_path,
        holdout_root=holdout_root.resolve(),
        index=0,
        physical_gpus=_validate_physical_gpu_manifest(job.get("physical_gpus"), label="holdout job physical_gpus"),
    )
    root = _absolute(str(job["output_root"]))
    if root.exists():
        raise Holdout64Error(f"holdout job root must be fresh: {root}")
    target_python = PROJECT_PYTHON.resolve()
    if not target_python.is_file():
        raise Holdout64Error(f"approved IsaacLab Python is missing: {PROJECT_PYTHON}")
    root.mkdir(parents=True, exist_ok=False)
    command = [str(value) for value in job["command"]]
    environment = {str(key): str(value) for key, value in job["environment"].items()}
    result = subprocess.run(command, cwd=REPO_ROOT, env={**os.environ, **environment}, check=False)
    raw_path = _absolute(str(job["raw_records_path"]))
    trace_path = _absolute(str(job["trace_path"]))
    receipt_path = _absolute(str(job["job_receipt_path"]))
    if result.returncode != 0:
        raise Holdout64Error(f"holdout job exited with returncode={result.returncode}; no retry is permitted")
    if not raw_path.is_file() or not trace_path.is_file():
        raise Holdout64Error("holdout job exited without both raw records and trace")
    receipt = {
        "schema": RAW_SCHEMA,
        "status": RAW_STATUS,
        "job_id": job["job_id"],
        "freeze_id": job["freeze_id"],
        "candidate": dict(job["candidate"]),
        "partition_id": job["partition_id"],
        "job_ordinal": job["job_ordinal"],
        "checkpoint_path": job["checkpoint_path"],
        "config_path": job["config_path"],
        "scenario_path": job["scenario_path"],
        "seed": job["seed"],
        "physical_gpu": job["physical_gpu"],
        "physical_gpus": list(job["physical_gpus"]),
        "physical_gpu_domain": list(LEGAL_PHYSICAL_GPUS),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "logical_gpu": LOGICAL_DEVICE,
        "process_count": 1,
        "num_envs": EPISODES_PER_SEED,
        "num_mini_batches": 1,
        "episode_count": EPISODES_PER_SEED,
        "returncode": int(result.returncode),
        "output_root": str(root),
        "raw_records_path": str(raw_path),
        "trace_path": str(trace_path),
        "retry_count": 0,
        "missing_evidence": [],
    }
    write_json(receipt_path, receipt)
    return receipt


def _load_records(path: Path, *, job: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = _read_json_any(path)
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, Mapping) and payload.get("records") is not None:
        if payload.get("schema") != RAW_SCHEMA:
            raise Holdout64Error(f"holdout raw record schema is invalid: {path}")
        records = payload["records"]
    else:
        raise Holdout64Error(f"holdout raw records must be a list or records object: {path}")
    if not isinstance(records, list) or len(records) != EPISODES_PER_SEED:
        raise Holdout64Error(f"holdout raw records must contain exactly {EPISODES_PER_SEED} rows: {path}")
    observed: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise Holdout64Error(f"holdout raw record {index} is not an object: {path}")
        env_id = record.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in range(EPISODES_PER_SEED):
            raise Holdout64Error(f"holdout raw record {index} has invalid env_id: {path}")
        if env_id in observed:
            raise Holdout64Error(f"holdout raw records duplicate env_id={env_id}: {path}")
        observed.add(env_id)
        if "seed" in record and record["seed"] != job["seed"]:
            raise Holdout64Error(f"holdout raw record seed disagrees with job: {path}")
        normalized.append(dict(record))
    if observed != set(range(EPISODES_PER_SEED)):
        raise Holdout64Error(f"holdout raw records do not cover env ids 0..15: {path}")
    return normalized


def _validate_trace(path: Path) -> None:
    payload = _read_json_any(path)
    if not isinstance(payload, list) or not payload:
        raise Holdout64Error(f"holdout trace must be a non-empty list: {path}")
    env_ids = set()
    for index, row in enumerate(payload):
        if not isinstance(row, Mapping):
            raise Holdout64Error(f"holdout trace row {index} is not an object: {path}")
        env_id = row.get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id not in range(EPISODES_PER_SEED):
            raise Holdout64Error(f"holdout trace row {index} has invalid env_id: {path}")
        env_ids.add(env_id)
    if env_ids != set(range(EPISODES_PER_SEED)):
        raise Holdout64Error(f"holdout trace does not cover env ids 0..15: {path}")


def _validate_job_receipt(receipt: Mapping[str, Any], job: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(str(job["job_receipt_path"]))
    if receipt.get("schema") != RAW_SCHEMA or receipt.get("status") != RAW_STATUS:
        raise Holdout64Error(f"holdout job receipt schema/status is incomplete: {path}")
    for field in ("job_id", "freeze_id", "partition_id", "job_ordinal", "checkpoint_path", "config_path", "scenario_path", "seed", "physical_gpu", "physical_gpus", "physical_gpu_domain", "physical_gpu_mapping_policy", "logical_gpu", "process_count", "num_envs", "num_mini_batches", "episode_count", "returncode", "output_root", "raw_records_path", "trace_path", "retry_count", "candidate"):
        if field not in receipt:
            raise Holdout64Error(f"holdout job receipt is missing {field}: {path}")
    for field in ("job_id", "freeze_id", "partition_id", "job_ordinal", "checkpoint_path", "config_path", "scenario_path", "seed", "physical_gpu", "physical_gpus", "physical_gpu_domain", "physical_gpu_mapping_policy", "logical_gpu", "process_count", "num_envs", "num_mini_batches", "episode_count", "output_root", "raw_records_path", "trace_path"):
        if receipt[field] != job[field]:
            raise Holdout64Error(f"holdout job receipt {path} field {field} disagrees with plan")
    if receipt["candidate"] != job["candidate"]:
        raise Holdout64Error(f"holdout job receipt candidate disagrees with plan: {path}")
    if receipt["returncode"] != 0 or receipt["retry_count"] != 0 or receipt.get("missing_evidence") != []:
        raise Holdout64Error(f"holdout job receipt is not a strict successful no-retry record: {path}")
    return dict(receipt)


def reduce_receipt(
    plan: Mapping[str, Any],
    *,
    output: str | Path = HOLDOUT_RECEIPT_PATH,
) -> dict[str, Any]:
    freeze = _validate_plan_topology(plan)
    jobs = plan["jobs"]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        receipt_path = _absolute(str(job["job_receipt_path"]))
        receipt = _validate_job_receipt(_read_json_any(receipt_path), job)
        freeze_id = str(job["freeze_id"])
        records_path = _absolute(str(job["raw_records_path"]))
        trace_path = _absolute(str(job["trace_path"]))
        records = _load_records(records_path, job=job)
        _validate_trace(trace_path)
        grouped.setdefault(freeze_id, []).append(
            {
                "job_ordinal": job["job_ordinal"],
                "seed": job["seed"],
                "partition_id": job["partition_id"],
                "physical_gpu": job["physical_gpu"],
                "physical_gpus": list(job["physical_gpus"]),
                "physical_gpu_domain": list(LEGAL_PHYSICAL_GPUS),
                "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
                "record_count": len(records),
                "raw_records_path": str(records_path),
                "trace_path": str(trace_path),
                "job_receipt_path": str(receipt_path),
                "records": records,
            }
        )
    frozen_candidates = _candidate_rows(freeze)
    candidates = []
    for candidate in frozen_candidates:
        freeze_id = candidate["freeze_id"]
        rows = grouped.get(freeze_id, [])
        if {row["seed"] for row in rows} != set(HOLDOUT_SEEDS) or len(rows) != len(HOLDOUT_SEEDS) or sum(row["record_count"] for row in rows) != CANONICAL_EPISODES:
            raise Holdout64Error(f"holdout candidate {freeze_id} does not have exact canonical64 coverage")
        candidates.append({"freeze_id": freeze_id, "candidate": dict(candidate), "episode_count": CANONICAL_EPISODES, "jobs": rows})
    if len(candidates) != EXPECTED_CANDIDATE_COUNT or sum(item["episode_count"] for item in candidates) != EXPECTED_CANDIDATE_COUNT * CANONICAL_EPISODES:
        raise Holdout64Error("holdout reduction did not cover exactly 16 candidates x 64 episodes")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": RECEIPT_STATUS,
        "recorded_at_utc": _utc_now(),
        "source_branch": "A2_Piper",
        "physical_gpus": list(plan["physical_gpus"]),
        "physical_gpu_domain": list(LEGAL_PHYSICAL_GPUS),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "gpu_assignment": "JOB_ORDINAL_MODULO_PHYSICAL_GPU_MANIFEST",
        "logical_gpu": LOGICAL_DEVICE,
        "process_count_per_gpu": 1,
        "candidate_freeze_path": plan["candidate_freeze_path"],
        "candidate_freeze_schema": CANDIDATE_FREEZE_SCHEMA,
        "candidate_freeze_status": CANDIDATE_FREEZE_STATUS,
        "candidate_freeze_ids": [candidate["freeze_id"] for candidate in frozen_candidates],
        "canonical_episodes_per_candidate": CANONICAL_EPISODES,
        "holdout_seeds": list(HOLDOUT_SEEDS),
        "candidate_count": EXPECTED_CANDIDATE_COUNT,
        "candidates": candidates,
        "missing_evidence": [],
        "invalid_evidence": [],
        "policy_quality_claim": False,
        "formal_admission": False,
        "release_receipt": False,
    }
    write_json(_absolute(output), receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "RUN", "REDUCE"), required=True)
    parser.add_argument("--freeze", type=Path, default=CANDIDATE_FREEZE_PATH)
    parser.add_argument("--output-root", type=Path, default=HOLDOUT_ROOT)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--job-index", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
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
            raise Holdout64Error("--physical-gpus is valid only for PLAN")
        if args.mode != "PLAN" and args.plan is None:
            raise Holdout64Error(f"{args.mode} requires an existing persisted --plan")
        physical_gpus = _parse_physical_gpu_tokens(args.physical_gpus) if args.mode == "PLAN" else None
        if args.mode == "PLAN":
            payload = build_plan(
                freeze_path=args.freeze,
                output_root=args.output_root,
                physical_gpus=physical_gpus,
            )
            if args.output is not None:
                write_json(_absolute(args.output), payload)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        elif args.mode == "RUN":
            plan = read_json(_absolute(args.plan))
            _validate_plan_topology(plan)
            if args.job_index is None or args.job_index not in range(len(plan["jobs"])):
                raise Holdout64Error("RUN requires a valid --job-index")
            print(json.dumps(run_once(plan["jobs"][args.job_index]), ensure_ascii=False, indent=2, sort_keys=True))
        else:
            plan = read_json(_absolute(args.plan))
            receipt = reduce_receipt(plan, output=args.output or HOLDOUT_RECEIPT_PATH)
            print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 HOLDOUT64 FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
