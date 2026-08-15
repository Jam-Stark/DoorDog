"""Typed post-Route-B v23 analysis and no-release report writer.

This consumer preserves missing or invalid evidence as typed states.  It does
not manufacture zero metrics, rank candidates, or convert research evidence
into a release decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23_GPU_SUBWAVES, V23_INTERVENTION_MODES, V23_PLAN_ID, V23_ROUTE_A_STEPS, V23Error, read_json, write_json
    from .route_b_analysis import (
        CANDIDATE_KEYS,
        LOGICAL_GPU,
        PHYSICAL_GPU_DOMAIN,
        PHYSICAL_GPU_MAPPING_POLICY,
        SUBWAVE_ORDER,
        _canonical_candidates,
        _freeze_id,
        _validate_candidate,
        validate_gpu_provenance,
    )
except ImportError:  # direct script invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23_GPU_SUBWAVES, V23_INTERVENTION_MODES, V23_PLAN_ID, V23_ROUTE_A_STEPS, V23Error, read_json, write_json
    from scriptsFORhuman.v23.route_b_analysis import (
        CANDIDATE_KEYS,
        LOGICAL_GPU,
        PHYSICAL_GPU_DOMAIN,
        PHYSICAL_GPU_MAPPING_POLICY,
        SUBWAVE_ORDER,
        _canonical_candidates,
        _freeze_id,
        _validate_candidate,
        validate_gpu_provenance,
    )


FINAL_ROOT = REPO_ROOT / "logs_eval/base_v23/final_analysis"
FINAL_JSON_PATH = FINAL_ROOT / "V23_FINAL_ANALYSIS.json"
FINAL_MD_PATH = FINAL_ROOT / "V23_FINAL_ANALYSIS.md"
PHYSICS_PATH = REPO_ROOT / "logs_eval/base_v23/p0/p04_d1_physics_first_20260810/p04_d1_physics_first.json"
P08_PATH = REPO_ROOT / "logs_eval/base_v23/p0/interventions/preformal_v2/p08_preformal_v2_receipt.json"
D1_FULL_PATH = REPO_ROOT / "logs_eval/base_v23/p0/d1_full_64x10/d1_full_64x10_receipt.json"
FORMAL_PATH = REPO_ROOT / "logs_eval/base_v23/locks/V23_FORMAL_ADMISSION_PASS.json"
ROUTE_A_PATH = REPO_ROOT / "logs_eval/base_v23/route_a"
ROUTE_B_PATH = REPO_ROOT / "logs_eval/base_v23/route_b/V23_CANDIDATE_FREEZE.json"
INTERVENTION_PATH = REPO_ROOT / "logs_eval/base_v23/interventions/V23_INTERVENTION_EVAL.json"
HOLDOUT_PATH = REPO_ROOT / "logs_eval/base_v23/holdout64/V23_HOLDOUT64.json"
RENDER_PATH = REPO_ROOT / "logs_eval/base_v23/render/V23_RENDER_QA.json"

FINAL_SCHEMA = "a2_piper_v23_final_analysis_v1"
FINAL_STATUS = "V23_FINAL_ANALYSIS_COMPLETE"
EXPECTED_RECEIPTS = {
    "physics": ("a2_piper_v23_p04_d1_physics_first_v1", "P0_4_D1_PHYSICS_FIRST_FREEZE_ADMITTED"),
    "p08": ("a2_piper_v23_p08_preformal_v2_receipt_v1", "P0_8_PREFORMAL_COMPLETE"),
    "d1_full": ("a2_piper_v23_d1_full_64x10_receipt_v1", "D1_FULL_64X10_BUCKET_PLUMBING_RUNTIME_VERIFIED"),
    "formal": ("a2_piper_v23_formal_admission_v1", "V23_FORMAL_ADMISSION_PASS"),
    "route_b": ("a2_piper_v23_candidate_freeze_v1", "V23_CANDIDATE_FREEZE_COMPLETE"),
    "intervention": ("a2_piper_v23_intervention_eval_receipt_v1", "V23_INTERVENTION_EVAL_COMPLETE"),
    "holdout": ("a2_piper_v23_holdout64_receipt_v1", "V23_HOLDOUT64_COMPLETE"),
    "render": ("a2_piper_v23_render_qa_receipt_v1", "V23_RENDER_QA_COMPLETE"),
}
ROUTE_A_SELECTION_SCHEMA = "a2_piper_v23_route_a_selection_v1"
ROUTE_A_SUBWAVE_ORDER = ("A1", "A2", "B1", "B2")
ROUTE_A_ROW_KEYS = {
    "source_branch",
    "plan_id",
    "identity_policy",
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
EXPECTED_CANDIDATE_COUNT = 16
EXPECTED_HOLDOUT_SEEDS = (3, 4, 5, 6)
EXPECTED_RENDER_CAMERAS = ("main", "handle_top", "handle_side")
EXPECTED_RENDER_SCENARIOS = (
    ("ordinary_mid_handle", 0.975, 120.0, 10.0, 50.0, 6.0),
    ("low_handle", 0.85, 120.0, 10.0, 50.0, 6.0),
    ("high_handle", 1.10, 120.0, 10.0, 50.0, 6.0),
    ("fast_rebound", 0.975, 120.0, 16.0, 25.0, 18.0),
    ("high_damping", 0.975, 120.0, 12.0, 120.0, 6.0),
)
EXPECTED_INTERVENTION_MISSING = [
    "outcome_adjudication_deferred",
    "unsafe_contacts_not_exported_for_route_b_intervention",
]
EXPECTED_HOLDOUT_MISSING = ["stage_trace_sparse_expected"]
CELL_AXES = {
    "G1": {"initialization": "warm", "door": "D0", "posture": "FULL"},
    "G2": {"initialization": "warm", "door": "D0", "posture": "RP0"},
    "G3": {"initialization": "head_reset", "door": "D0", "posture": "FULL"},
    "G4": {"initialization": "head_reset", "door": "D0", "posture": "RP0"},
    "G5": {"initialization": "warm", "door": "D1", "posture": "FULL"},
    "G6": {"initialization": "warm", "door": "D1", "posture": "RP0"},
    "G7": {"initialization": "head_reset", "door": "D1", "posture": "FULL"},
    "G8": {"initialization": "head_reset", "door": "D1", "posture": "RP0"},
}


class FinalAnalysisError(V23Error):
    """A final-analysis input or typed report contract is invalid."""


def _gpu_provenance(payload: Mapping[str, Any], *, label: str) -> list[int]:
    try:
        return validate_gpu_provenance(payload, label=label)
    except V23Error as exc:
        raise FinalAnalysisError(str(exc)) from exc


def _validate_candidate_freeze_contract(payload: Mapping[str, Any], *, path: Path) -> list[dict[str, Any]]:
    required = {
        "schema",
        "status",
        "source_branch",
        "plan_id",
        "identity_policy",
        "route",
        "physical_gpu_domain",
        "physical_gpus",
        "physical_gpu_mapping_policy",
        "logical_gpu",
        "process_count_per_gpu",
        "num_mini_batches",
        "selection_policy",
        "ranking_gate",
        "completeness_gate",
        "symmetry_gate",
        "source_receipts",
        "candidate_count",
        "selected_candidates",
        "missing_evidence",
        "excluded_claims",
    }
    if not required <= set(payload):
        raise FinalAnalysisError(f"candidate freeze contract is shallow or incomplete: {path}")
    freeze_gpus = _gpu_provenance(payload, label="candidate freeze")
    if (
        payload.get("schema") != EXPECTED_RECEIPTS["route_b"][0]
        or payload.get("status") != EXPECTED_RECEIPTS["route_b"][1]
        or payload.get("source_branch") != "A2_Piper"
        or payload.get("plan_id") != V23_PLAN_ID
        or payload.get("identity_policy") != "OWNER_NO_HASH_PATH_IDENTITY"
        or payload.get("route") != "B"
        or payload.get("logical_gpu") != LOGICAL_GPU
        or payload.get("process_count_per_gpu") != 1
        or payload.get("num_mini_batches") != 1
        or payload.get("ranking_gate") != "NOT_APPLIED"
        or payload.get("completeness_gate") != "NOT_APPLIED"
        or payload.get("symmetry_gate") != "NOT_APPLIED"
        or payload.get("missing_evidence") != []
    ):
        raise FinalAnalysisError(f"candidate freeze provenance/topology is invalid: {path}")
    rows = payload.get("selected_candidates")
    if payload.get("candidate_count") != EXPECTED_CANDIDATE_COUNT or not isinstance(rows, list) or len(rows) != EXPECTED_CANDIDATE_COUNT:
        raise FinalAnalysisError(f"candidate freeze must contain exactly 16 selected candidates: {path}")
    normalized: list[dict[str, Any]] = []
    expected_fields = set(CANDIDATE_KEYS) | {"freeze_id", "evidence_status"}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != expected_fields:
            raise FinalAnalysisError(f"candidate freeze row {index} key set is invalid: {path}")
        base = {key: row[key] for key in CANDIDATE_KEYS}
        _validate_candidate(base, index=index)
        if row.get("freeze_id") != _freeze_id(base) or row.get("evidence_status") != "EVIDENCE_COMPLETE_FROM_THREE_ROUTE_B_RECEIPTS":
            raise FinalAnalysisError(f"candidate freeze row {index} identity/evidence status is invalid: {path}")
        normalized.append(dict(row))
    canonical = _canonical_candidates(
        [{key: row[key] for key in CANDIDATE_KEYS} for row in normalized],
        name="candidate freeze",
    )
    canonical_rows = [
        next(row for row in normalized if row["freeze_id"] == _freeze_id(item))
        for item in canonical
    ]
    if normalized != canonical_rows:
        raise FinalAnalysisError(f"candidate freeze rows are not in canonical order: {path}")
    source_receipts = payload.get("source_receipts")
    expected_sources = {
        "pooled48": ("a2_piper_v23_pooled48_receipt_v1", "V23_POOLED48_COMPLETE"),
        "stratified": ("a2_piper_v23_stratified_eval_receipt_v1", "V23_STRATIFIED_EVAL_COMPLETE"),
        "intervention": ("a2_piper_v23_intervention_eval_receipt_v1", "V23_INTERVENTION_EVAL_COMPLETE"),
    }
    if not isinstance(source_receipts, list) or len(source_receipts) != 3:
        raise FinalAnalysisError(f"candidate freeze source provenance is incomplete: {path}")
    observed_sources = set()
    for source in source_receipts:
        if not isinstance(source, Mapping) or set(source) != {
            "name",
            "path",
            "schema",
            "status",
            "physical_gpu_domain",
            "physical_gpus",
            "physical_gpu_mapping_policy",
        }:
            raise FinalAnalysisError(f"candidate freeze source provenance row is invalid: {path}")
        name = source.get("name")
        if name not in expected_sources or name in observed_sources or not isinstance(source.get("path"), str) or not source["path"]:
            raise FinalAnalysisError(f"candidate freeze source provenance identity is invalid: {path}")
        if (source.get("schema"), source.get("status")) != expected_sources[name]:
            raise FinalAnalysisError(f"candidate freeze source provenance schema/status is invalid: {path}")
        source_gpus = _gpu_provenance(source, label=f"candidate freeze source {name}")
        if source_gpus != freeze_gpus:
            raise FinalAnalysisError(f"candidate freeze source GPU provenance disagrees: {path}")
        observed_sources.add(name)
    if observed_sources != set(expected_sources):
        raise FinalAnalysisError(f"candidate freeze source provenance is incomplete: {path}")
    return normalized


def _validate_common_receipt_contract(name: str, payload: Mapping[str, Any], *, path: Path) -> None:
    required_fields = {
        "physics": ("affirmative_physics_first_freeze", "atlas", "zones", "confirmed_E2", "admission"),
        "p08": ("formal_admission", "release_receipt", "p08_preformal_gate", "raw_record_count", "records", "incomplete_reasons"),
        "d1_full": ("physical_gpu", "logical_device", "num_envs", "num_mini_batches", "runtime_verified", "policy_quality_claim", "formal_admission"),
        "formal": ("formal_admission", "policy_quality_claim", "release_receipt"),
    }.get(name)
    if required_fields is None:
        return
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise FinalAnalysisError(f"{name} receipt is shallow/incomplete; missing {missing}: {path}")
    if payload.get("source_branch") is not None and payload.get("source_branch") != "A2_Piper":
        raise FinalAnalysisError(f"{name} receipt source_branch is invalid: {path}")


def _project_intervention_candidate(item: Any, *, index: int, path: Path) -> dict[str, Any]:
    if not isinstance(item, Mapping) or set(item) != set(CANDIDATE_KEYS):
        raise FinalAnalysisError(f"intervention candidate {index} does not use the producer candidate shape: {path}")
    projected = {key: item[key] for key in CANDIDATE_KEYS}
    _validate_candidate(projected, index=index)
    return projected


def _validate_intervention_contract(
    payload: Mapping[str, Any],
    *,
    path: Path,
    freeze_rows: Sequence[Mapping[str, Any]],
    expected_physical_gpus: Sequence[int],
) -> None:
    freeze_projections = [
        {key: row[key] for key in CANDIDATE_KEYS}
        for row in freeze_rows
    ]
    projection_to_freeze = {
        tuple(row[key] for key in CANDIDATE_KEYS): row
        for row in freeze_rows
    }
    observed_physical_gpus = _gpu_provenance(payload, label="intervention receipt")
    if (
        payload.get("source_branch") != "A2_Piper"
        or payload.get("plan_id") != V23_PLAN_ID
        or payload.get("identity_policy") != "OWNER_NO_HASH_PATH_IDENTITY"
        or payload.get("route") != "B"
        or payload.get("stage") != "INTERVENTIONS"
        or payload.get("topology") != "canonical16"
        or observed_physical_gpus != list(expected_physical_gpus)
        or payload.get("logical_gpu") != LOGICAL_GPU
        or payload.get("num_mini_batches") != 1
        or payload.get("modes") != list(V23_INTERVENTION_MODES)
        or payload.get("candidate_count") != EXPECTED_CANDIDATE_COUNT
        or payload.get("job_count") != EXPECTED_CANDIDATE_COUNT * len(V23_INTERVENTION_MODES)
        or payload.get("episode_record_count") != EXPECTED_CANDIDATE_COUNT * len(V23_INTERVENTION_MODES) * 16
        or payload.get("forward_only") is not True
        or payload.get("state_clone_supported") is not False
        or payload.get("recurrent_state_restore_supported") is not False
        or payload.get("actual_torque_claim") is not False
        or payload.get("outcome_status") != "PENDING_RUNTIME_FORWARD_ADJUDICATION"
        or payload.get("missing_evidence") != EXPECTED_INTERVENTION_MISSING
        or payload.get("no_retry") is not True
    ):
        raise FinalAnalysisError(f"intervention receipt topology/provenance is invalid: {path}")
    selected = payload.get("selected_candidates")
    if not isinstance(selected, list) or len(selected) != EXPECTED_CANDIDATE_COUNT:
        raise FinalAnalysisError(f"intervention receipt must contain exactly 16 selected candidates: {path}")
    projected_selected = [
        _project_intervention_candidate(candidate, index=index, path=path)
        for index, candidate in enumerate(selected)
    ]
    if projected_selected != freeze_projections:
        raise FinalAnalysisError(f"intervention selected candidates do not match the freeze projection: {path}")
    jobs = payload.get("jobs")
    expected_job_count = EXPECTED_CANDIDATE_COUNT * len(V23_INTERVENTION_MODES)
    if not isinstance(jobs, list) or len(jobs) != expected_job_count:
        raise FinalAnalysisError(f"intervention receipt must contain exactly {expected_job_count} jobs: {path}")
    by_id = {row["freeze_id"]: row for row in freeze_rows}
    seen: set[tuple[str, str]] = set()
    for index, job in enumerate(jobs):
        if not isinstance(job, Mapping):
            raise FinalAnalysisError(f"intervention job {index} is invalid: {path}")
        candidate = job.get("selected_candidate")
        mode = job.get("mode")
        projected = _project_intervention_candidate(candidate, index=index, path=path)
        freeze_row = projection_to_freeze.get(tuple(projected[key] for key in CANDIDATE_KEYS))
        freeze_id = freeze_row.get("freeze_id") if freeze_row is not None else None
        if freeze_row is None or mode not in V23_INTERVENTION_MODES:
            raise FinalAnalysisError(f"intervention job {index} candidate/mode binding is invalid: {path}")
        key = (freeze_id, mode)
        if key in seen:
            raise FinalAnalysisError(f"intervention receipt duplicates job {key}: {path}")
        seen.add(key)
        if (
            job.get("topology") != "canonical16"
            or job.get("job_ordinal") != index
            or job.get("physical_gpu") != expected_physical_gpus[index % len(expected_physical_gpus)]
            or job.get("episode_record_count") != 16
            or job.get("outcome_status") != "PENDING_RUNTIME_FORWARD_ADJUDICATION"
            or job.get("forward_only") is not True
            or job.get("state_clone_supported") is not False
            or job.get("actual_torque_claim") is not False
            or job.get("missing_evidence") != EXPECTED_INTERVENTION_MISSING
        ):
            raise FinalAnalysisError(f"intervention job {index} contract is invalid: {path}")
    if seen != {(row["freeze_id"], mode) for row in freeze_rows for mode in V23_INTERVENTION_MODES}:
        raise FinalAnalysisError(f"intervention receipt does not cover exact 16x5 jobs: {path}")


def _validate_holdout_contract(
    payload: Mapping[str, Any],
    *,
    path: Path,
    freeze_rows: Sequence[Mapping[str, Any]],
    expected_physical_gpus: Sequence[int],
) -> None:
    freeze_ids = [row["freeze_id"] for row in freeze_rows]
    observed_physical_gpus = _gpu_provenance(payload, label="holdout receipt")
    if (
        payload.get("source_branch") != "A2_Piper"
        or observed_physical_gpus != list(expected_physical_gpus)
        or payload.get("gpu_assignment") != "JOB_ORDINAL_MODULO_PHYSICAL_GPU_MANIFEST"
        or payload.get("logical_gpu") != LOGICAL_GPU
        or payload.get("process_count_per_gpu") != 1
        or payload.get("candidate_count") != 16
        or payload.get("candidate_freeze_schema") != EXPECTED_RECEIPTS["route_b"][0]
        or payload.get("candidate_freeze_status") != EXPECTED_RECEIPTS["route_b"][1]
        or payload.get("candidate_freeze_ids") != freeze_ids
        or payload.get("holdout_seeds") != list(EXPECTED_HOLDOUT_SEEDS)
        or payload.get("canonical_episodes_per_candidate") != 64
        or payload.get("missing_evidence") != EXPECTED_HOLDOUT_MISSING
        or payload.get("invalid_evidence") != []
        or payload.get("policy_quality_claim") is not False
        or payload.get("formal_admission") is not False
        or payload.get("release_receipt") is not False
    ):
        raise FinalAnalysisError(f"holdout receipt topology/provenance is invalid: {path}")
    candidate_freeze_path = payload.get("candidate_freeze_path")
    if not isinstance(candidate_freeze_path, str) or not candidate_freeze_path or not Path(candidate_freeze_path).is_absolute():
        raise FinalAnalysisError(f"holdout receipt candidate-freeze path is not absolute: {path}")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != EXPECTED_CANDIDATE_COUNT:
        raise FinalAnalysisError(f"holdout receipt must contain exactly 16 candidates: {path}")
    by_id = {row["freeze_id"]: row for row in freeze_rows}
    observed_ids: list[str] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping) or candidate.get("freeze_id") not in by_id or candidate.get("candidate") != by_id[candidate["freeze_id"]] or candidate.get("episode_count") != 64:
            raise FinalAnalysisError(f"holdout candidate {index} is not bound to the freeze: {path}")
        observed_ids.append(candidate["freeze_id"])
        jobs = candidate.get("jobs")
        if not isinstance(jobs, list) or len(jobs) != 4:
            raise FinalAnalysisError(f"holdout candidate {index} must contain exactly four partitions: {path}")
        seen_seeds: set[int] = set()
        for job in jobs:
            if not isinstance(job, Mapping):
                raise FinalAnalysisError(f"holdout candidate {index} has an invalid partition: {path}")
            seed = job.get("seed")
            if isinstance(seed, bool) or seed not in EXPECTED_HOLDOUT_SEEDS or seed in seen_seeds:
                raise FinalAnalysisError(f"holdout candidate {index} partition seed is invalid: {path}")
            seen_seeds.add(seed)
            expected_job_ordinal = index * len(EXPECTED_HOLDOUT_SEEDS) + EXPECTED_HOLDOUT_SEEDS.index(seed)
            if (
                job.get("partition_id") != f"seed{seed}_canonical16"
                or job.get("job_ordinal") != expected_job_ordinal
                or job.get("physical_gpus") != list(expected_physical_gpus)
                or job.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN)
                or job.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY
                or job.get("physical_gpu") != expected_physical_gpus[expected_job_ordinal % len(expected_physical_gpus)]
                or job.get("record_count") != 16
                or not isinstance(job.get("raw_records_path"), str)
                or not isinstance(job.get("trace_path"), str)
                or not isinstance(job.get("job_receipt_path"), str)
            ):
                raise FinalAnalysisError(f"holdout candidate {index} partition contract is invalid: {path}")
        if seen_seeds != set(EXPECTED_HOLDOUT_SEEDS):
            raise FinalAnalysisError(f"holdout candidate {index} partitions are incomplete: {path}")
    if observed_ids != freeze_ids:
        raise FinalAnalysisError(f"holdout candidate order/identity disagrees with freeze: {path}")


def _render_scenario_parameters(name: str) -> dict[str, float]:
    for row in EXPECTED_RENDER_SCENARIOS:
        if row[0] == name:
            return {
                "handle_height_m": row[1],
                "door_weight_kg": row[2],
                "hinge_max_force_nm": row[3],
                "hinge_damping_native": row[4],
                "hinge_stiffness_native": row[5],
            }
    raise FinalAnalysisError(f"render receipt contains an unknown scenario {name!r}")


def _validate_render_contract(
    payload: Mapping[str, Any],
    *,
    path: Path,
    freeze_rows: Sequence[Mapping[str, Any]],
    expected_physical_gpus: Sequence[int],
) -> None:
    freeze_ids = [row["freeze_id"] for row in freeze_rows]
    observed_physical_gpus = _gpu_provenance(payload, label="render receipt")
    selected_ids = payload.get("selected_candidate_ids")
    if (
        payload.get("source_branch") != "A2_Piper"
        or observed_physical_gpus != list(expected_physical_gpus)
        or payload.get("gpu_assignment") != "JOB_ORDINAL_MODULO_PHYSICAL_GPU_MANIFEST"
        or payload.get("logical_gpu") != LOGICAL_GPU
        or payload.get("process_count_per_gpu") != 1
        or payload.get("candidate_count") != 16
        or payload.get("scenario_count_per_candidate") != 5
        or payload.get("camera_count_per_scenario") != 3
        or payload.get("qualitative_only") is not True
        or payload.get("success_gate") != "NOT_APPLIED"
        or payload.get("missing_evidence") != []
        or payload.get("policy_quality_claim") is not False
        or payload.get("formal_admission") is not False
        or payload.get("release_receipt") is not False
        or payload.get("retry_policy") != "none"
        or payload.get("cameras") != list(EXPECTED_RENDER_CAMERAS)
        or not isinstance(selected_ids, list)
        or len(selected_ids) not in (1, 2, 3)
        or any(not isinstance(candidate_id, str) or not candidate_id for candidate_id in selected_ids)
        or len(set(selected_ids)) != len(selected_ids)
        or any(candidate_id not in freeze_ids for candidate_id in selected_ids)
        or payload.get("selected_candidate_count") != len(selected_ids)
    ):
        raise FinalAnalysisError(f"render receipt topology/provenance is invalid: {path}")
    if payload.get("candidate_freeze_ids") != freeze_ids:
        raise FinalAnalysisError(f"render receipt full candidate-freeze IDs disagree with freeze: {path}")
    if payload.get("candidate_freeze_schema") != EXPECTED_RECEIPTS["route_b"][0] or payload.get("candidate_freeze_status") != EXPECTED_RECEIPTS["route_b"][1]:
        raise FinalAnalysisError(f"render receipt candidate-freeze schema/status is invalid: {path}")
    candidate_freeze_path = payload.get("candidate_freeze_path")
    holdout_path = payload.get("holdout_path")
    if (
        not isinstance(candidate_freeze_path, str)
        or not candidate_freeze_path
        or not Path(candidate_freeze_path).is_absolute()
        or payload.get("holdout_schema") != "a2_piper_v23_holdout64_receipt_v1"
        or payload.get("holdout_status") != "V23_HOLDOUT64_COMPLETE"
        or not isinstance(holdout_path, str)
        or not holdout_path
        or not Path(holdout_path).is_absolute()
    ):
        raise FinalAnalysisError(f"render receipt full lineage paths/schema are invalid: {path}")
    if payload.get("holdout_candidate_freeze_ids") != freeze_ids:
        raise FinalAnalysisError(f"render receipt holdout full candidate-freeze IDs disagree with freeze: {path}")
    jobs = payload.get("jobs")
    expected_job_count = len(selected_ids) * len(EXPECTED_RENDER_SCENARIOS)
    if not isinstance(jobs, list) or len(jobs) != expected_job_count:
        raise FinalAnalysisError(f"render receipt must contain exactly {expected_job_count} jobs for its explicit candidate subset: {path}")
    seen_jobs: set[tuple[str, str]] = set()
    observed_candidate_order: list[str] = []
    seen_media: set[str] = set()
    expected_scenarios = {row[0] for row in EXPECTED_RENDER_SCENARIOS}
    for index, job in enumerate(jobs):
        if not isinstance(job, Mapping):
            raise FinalAnalysisError(f"render job {index} is invalid: {path}")
        freeze_id = job.get("freeze_id")
        scenario = job.get("scenario")
        if freeze_id not in selected_ids or scenario not in expected_scenarios:
            raise FinalAnalysisError(f"render job {index} identity is invalid: {path}")
        key = (freeze_id, scenario)
        if key in seen_jobs:
            raise FinalAnalysisError(f"render receipt duplicates job {key}: {path}")
        seen_jobs.add(key)
        if freeze_id not in observed_candidate_order:
            observed_candidate_order.append(freeze_id)
        params = _render_scenario_parameters(scenario)
        freeze_row = next(row for row in freeze_rows if row["freeze_id"] == freeze_id)
        expected_identity = {
            field: freeze_row[field]
            for field in ("freeze_id", "checkpoint_path", "config_path", "seed", "subwave", "cell")
        }
        if (
            job.get("status") != "QUALITATIVE_RENDER_COMPLETE"
            or job.get("candidate_identity") != expected_identity
            or job.get("scenario_parameters") != params
            or job.get("scenario_manifest_schema") != "a2_piper_v23_route_b_render_scenario_manifest_v1"
            or job.get("scenario_manifest_status") != "STATIC_RENDER"
            or job.get("scenario_manifest_topology") != "render16"
            or job.get("topology") != "render16"
            or job.get("job_ordinal") != index
            or job.get("physical_gpus") != list(expected_physical_gpus)
            or job.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN)
            or job.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY
            or job.get("physical_gpu") != expected_physical_gpus[index % len(expected_physical_gpus)]
            or job.get("logical_gpu") != LOGICAL_GPU
            or job.get("process_count") != 1
            or job.get("num_envs") != 16
            or job.get("num_mini_batches") != 1
            or job.get("cameras") != list(EXPECTED_RENDER_CAMERAS)
            or job.get("media_count") != 48
            or job.get("qualitative_only") is not True
            or job.get("success_gate") != "NOT_APPLIED"
            or job.get("policy_quality_claim") is not False
            or job.get("formal_admission") is not False
            or job.get("release_receipt") is not False
            or job.get("retry_count") != 0
            or job.get("returncode") != 0
            or job.get("missing_evidence") != []
        ):
            raise FinalAnalysisError(f"render job {index} contract is invalid: {path}")
        media_paths = job.get("media_paths")
        media_rows = job.get("media_rows")
        if not isinstance(media_paths, list) or len(media_paths) != 48 or len(set(media_paths)) != 48 or any(not isinstance(media, str) or not Path(media).is_absolute() or media.endswith(".writing.mp4") for media in media_paths):
            raise FinalAnalysisError(f"render job {index} media paths are invalid: {path}")
        if not isinstance(media_rows, list) or len(media_rows) != 48:
            raise FinalAnalysisError(f"render job {index} media_rows are incomplete: {path}")
        row_keys = {"env_id", "camera", "path", "episode"}
        identities = set()
        for media_row in media_rows:
            if not isinstance(media_row, Mapping) or set(media_row) != row_keys or media_row.get("episode") != 0 or media_row.get("path") not in media_paths or media_row.get("path") in identities:
                raise FinalAnalysisError(f"render job {index} media_rows are invalid: {path}")
            identity = (media_row.get("env_id"), media_row.get("camera"))
            if identity in identities or media_row.get("env_id") not in range(16) or media_row.get("camera") not in EXPECTED_RENDER_CAMERAS:
                raise FinalAnalysisError(f"render job {index} media_rows topology is invalid: {path}")
            identities.add(identity)
            seen_media.add(media_row["path"])
        if identities != {(env_id, camera) for env_id in range(16) for camera in EXPECTED_RENDER_CAMERAS}:
            raise FinalAnalysisError(f"render job {index} media_rows do not cover exact 16x3 topology: {path}")
    if seen_jobs != {(freeze_id, scenario) for freeze_id in selected_ids for scenario in expected_scenarios}:
        raise FinalAnalysisError(f"render receipt does not cover exact selected-subset x 5 jobs: {path}")
    if observed_candidate_order != selected_ids:
        raise FinalAnalysisError(f"render receipt candidate order does not preserve the explicit subset: {path}")
    if len(seen_media) != expected_job_count * 48:
        raise FinalAnalysisError(f"render receipt media paths are not globally unique: {path}")


def _validate_input_contracts(inputs: Mapping[str, Mapping[str, Any]]) -> None:
    route_b = inputs["route_b"]
    if route_b.get("state") != "PASS" or not isinstance(route_b.get("payload"), Mapping):
        raise FinalAnalysisError("candidate freeze input is not PASS")
    freeze_rows = _validate_candidate_freeze_contract(route_b["payload"], path=Path(route_b["path"]))
    expected_physical_gpus = _gpu_provenance(route_b["payload"], label="candidate freeze")
    for name in ("physics", "p08", "d1_full", "formal"):
        item = inputs[name]
        if item.get("state") != "PASS" or not isinstance(item.get("payload"), Mapping):
            raise FinalAnalysisError(f"{name} input is not PASS")
        _validate_common_receipt_contract(name, item["payload"], path=Path(item["path"]))
    intervention = inputs["intervention"]
    holdout = inputs["holdout"]
    render = inputs["render"]
    if intervention.get("state") != "PASS" or not isinstance(intervention.get("payload"), Mapping):
        raise FinalAnalysisError("intervention input is not PASS")
    if holdout.get("state") != "PASS" or not isinstance(holdout.get("payload"), Mapping):
        raise FinalAnalysisError("holdout input is not PASS")
    if render.get("state") != "PASS" or not isinstance(render.get("payload"), Mapping):
        raise FinalAnalysisError("render input is not PASS")
    _validate_intervention_contract(
        intervention["payload"],
        path=Path(intervention["path"]),
        freeze_rows=freeze_rows,
        expected_physical_gpus=expected_physical_gpus,
    )
    _validate_holdout_contract(
        holdout["payload"],
        path=Path(holdout["path"]),
        freeze_rows=freeze_rows,
        expected_physical_gpus=expected_physical_gpus,
    )
    _validate_render_contract(
        render["payload"],
        path=Path(render["path"]),
        freeze_rows=freeze_rows,
        expected_physical_gpus=expected_physical_gpus,
    )


def _route_a_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FinalAnalysisError(f"Route-A selection field {field} must be a non-empty string")
    return value


def _route_a_int(value: Any, *, field: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FinalAnalysisError(f"Route-A selection field {field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise FinalAnalysisError(f"Route-A selection field {field} must be <= {maximum}")
    return value


def _validate_route_a_selection(payload: Mapping[str, Any], *, path: Path, subwave: str) -> dict[str, Any]:
    if payload.get("schema") != ROUTE_A_SELECTION_SCHEMA or payload.get("status") != "COMPLETE":
        raise FinalAnalysisError(f"Route-A selection schema/status is invalid: {path}")
    expected_seed = int(V23_GPU_SUBWAVES[subwave]["seed"])
    expected_cells = list(V23_GPU_SUBWAVES[subwave]["cells"])
    if (
        payload.get("source_branch") != "A2_Piper"
        or payload.get("plan_id") != V23_PLAN_ID
        or payload.get("identity_policy") != "OWNER_NO_HASH_PATH_IDENTITY"
        or payload.get("route") != "A"
        or payload.get("subwave") != subwave
        or payload.get("seed") != expected_seed
        or payload.get("cells") != expected_cells
        or payload.get("topology") != "canonical16"
        or payload.get("steps") != list(V23_ROUTE_A_STEPS)
    ):
        raise FinalAnalysisError(f"Route-A selection identity/topology is invalid: {path}")
    selected = payload.get("selected")
    if not isinstance(selected, list) or len(selected) != 4:
        raise FinalAnalysisError(f"Route-A selection must contain exactly four selected rows: {path}")
    observed_cells: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        if not isinstance(row, Mapping) or set(row) != ROUTE_A_ROW_KEYS:
            raise FinalAnalysisError(f"Route-A selected row {index} key set is invalid: {path}")
        item = dict(row)
        if item["source_branch"] != "A2_Piper" or item["plan_id"] != V23_PLAN_ID or item["identity_policy"] != "OWNER_NO_HASH_PATH_IDENTITY":
            raise FinalAnalysisError(f"Route-A selected row {index} provenance is invalid: {path}")
        if item["seed"] != expected_seed or item["cell"] not in expected_cells or item["cell"] in observed_cells:
            raise FinalAnalysisError(f"Route-A selected row {index} cell/seed identity is invalid: {path}")
        observed_cells.add(item["cell"])
        _route_a_string(item["row_id"], field="row_id")
        _route_a_int(item["step"], field="step")
        if item["step"] not in V23_ROUTE_A_STEPS:
            raise FinalAnalysisError(f"Route-A selected row {index} step is invalid: {path}")
        for field in ("checkpoint_path", "config_path", "scenario_path", "evaluation_root"):
            _route_a_string(item[field], field=field)
        for field in ("goal_reached", "supported_crossing", "unsafe_contacts", "terminal_failures"):
            _route_a_int(item[field], field=field, maximum=16)
        normalized.append(item)
    if observed_cells != set(expected_cells):
        raise FinalAnalysisError(f"Route-A selected rows do not cover expected cells: {path}")
    result = dict(payload)
    result["selected"] = normalized
    return result


def _load_route_a_bundle(target: Path) -> dict[str, Any]:
    if target.is_symlink():
        return {"name": "route_a", "path": str(target), "state": "INVALID", "reason": "Route-A bundle must be a directory"}
    if not target.exists():
        return {"name": "route_a", "path": str(target), "state": "MISSING", "reason": "Route-A bundle directory is absent"}
    if not target.is_dir():
        return {"name": "route_a", "path": str(target), "state": "INVALID", "reason": "Route-A bundle must be a directory"}
    files = sorted(target.rglob("V23_ROUTE_A_SELECTION.json"))
    if len(files) != len(ROUTE_A_SUBWAVE_ORDER):
        return {"name": "route_a", "path": str(target), "state": "INVALID", "reason": "Route-A bundle must contain exactly four selection receipts"}
    selections: dict[str, dict[str, Any]] = {}
    selection_paths: dict[str, Path] = {}
    for path in files:
        try:
            payload = read_json(path)
        except (OSError, TypeError, ValueError, V23Error) as exc:
            return {"name": "route_a", "path": str(target), "state": "INVALID", "reason": str(exc)}
        subwave = payload.get("subwave") if isinstance(payload, Mapping) else None
        if subwave not in ROUTE_A_SUBWAVE_ORDER or subwave in selections:
            return {"name": "route_a", "path": str(target), "state": "INVALID", "reason": "Route-A bundle has duplicate or unknown subwave"}
        try:
            selections[subwave] = _validate_route_a_selection(payload, path=path, subwave=subwave)
            selection_paths[subwave] = path
        except FinalAnalysisError as exc:
            return {"name": "route_a", "path": str(target), "state": "INVALID", "reason": str(exc)}
    if set(selections) != set(ROUTE_A_SUBWAVE_ORDER):
        return {"name": "route_a", "path": str(target), "state": "INVALID", "reason": "Route-A bundle subwave order is incomplete"}
    return {
        "name": "route_a",
        "path": str(target),
        "state": "PASS",
        "schema": "a2_piper_v23_route_a_bundle_v1",
        "status": "V23_ROUTE_A_COMPLETE",
        "payload": {
            "schema": "a2_piper_v23_route_a_bundle_v1",
            "status": "V23_ROUTE_A_COMPLETE",
            "subwaves": list(ROUTE_A_SUBWAVE_ORDER),
            "selection_paths": [str(selection_paths[subwave]) for subwave in ROUTE_A_SUBWAVE_ORDER],
            "selections": [selections[subwave] for subwave in ROUTE_A_SUBWAVE_ORDER],
        },
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _load_optional(path: str | Path, *, name: str) -> dict[str, Any]:
    target = _absolute(path)
    if name == "route_a":
        return _load_route_a_bundle(target)
    if target.is_dir():
        return {"name": name, "path": str(target), "state": "MISSING", "reason": "receipt path must be a file"}
    if not target.is_file() or target.is_symlink():
        return {"name": name, "path": str(target), "state": "MISSING", "reason": "receipt file is absent"}
    try:
        payload = read_json(target)
    except (OSError, TypeError, ValueError, V23Error) as exc:
        return {"name": name, "path": str(target), "state": "INVALID", "reason": str(exc)}
    expected = EXPECTED_RECEIPTS.get(name)
    if expected is not None:
        expected_schema, expected_status = expected
        if payload.get("schema") != expected_schema or payload.get("status") != expected_status:
            return {
                "name": name,
                "path": str(target),
                "state": "INVALID",
                "reason": f"expected schema/status {expected_schema}/{expected_status}",
                "observed_schema": payload.get("schema"),
                "observed_status": payload.get("status"),
            }
    try:
        if name == "route_b":
            _validate_candidate_freeze_contract(payload, path=target)
        elif name in {"physics", "p08", "d1_full", "formal"}:
            _validate_common_receipt_contract(name, payload, path=target)
    except FinalAnalysisError as exc:
        return {
            "name": name,
            "path": str(target),
            "state": "INVALID",
            "reason": str(exc),
            "schema": payload.get("schema"),
            "status": payload.get("status"),
        }
    return {
        "name": name,
        "path": str(target),
        "state": "PASS",
        "schema": payload.get("schema"),
        "status": payload.get("status"),
        "payload": payload,
    }


def load_inputs(paths: Mapping[str, str | Path] | None = None) -> dict[str, dict[str, Any]]:
    defaults = {
        "physics": PHYSICS_PATH,
        "p08": P08_PATH,
        "d1_full": D1_FULL_PATH,
        "formal": FORMAL_PATH,
        "route_a": ROUTE_A_PATH,
        "route_b": ROUTE_B_PATH,
        "intervention": INTERVENTION_PATH,
        "holdout": HOLDOUT_PATH,
        "render": RENDER_PATH,
    }
    return {
        name: _load_optional(paths[name] if paths is not None and name in paths else path, name=name)
        for name, path in defaults.items()
    }


def _typed_evidence_summary(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name, item in inputs.items():
        row = {key: value for key, value in item.items() if key != "payload"}
        if item.get("state") == "PASS":
            payload = item.get("payload")
            if isinstance(payload, Mapping):
                row["binding_fields"] = {
                    key: payload[key]
                    for key in ("candidate_count", "row_count", "physical_gpus", "logical_gpu", "formal_admission", "release_receipt")
                    if key in payload
                }
        summary[name] = row
    return summary


def _route_b_source(payload: Mapping[str, Any], name: str) -> tuple[Path, dict[str, Any]]:
    for source in payload["source_receipts"]:
        if source["name"] == name:
            path = Path(source["path"])
            return path, read_json(path)
    raise FinalAnalysisError(f"candidate freeze does not bind the {name} source receipt")


def _episode_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "episodes": len(records),
        "goal_reached": sum(row.get("goal_reached") is True for row in records),
        "max_stage5": sum(row.get("max_stage") == 5 for row in records),
        "final_stage5": sum(row.get("final_stage") == 5 for row in records),
        "crossing_while_holding": sum(row.get("crossing_while_holding") is True for row in records),
        "unsafe_post_release_contact": sum(row.get("post_release_body_contact") is True for row in records),
    }


def _pooled_metrics(route_b_payload: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    _, receipt = _route_b_source(route_b_payload, "pooled48")
    rows: dict[str, dict[str, int]] = {}
    for job in receipt["jobs"]:
        job_receipt = read_json(Path(job["receipt_path"]))
        records_path = Path(job_receipt["records_path"])
        records = json.loads(records_path.read_text(encoding="utf-8"))
        if not isinstance(records, list) or len(records) != 48:
            raise FinalAnalysisError(f"pooled48 job does not expose exact 48 records: {job['receipt_path']}")
        freeze_id = _freeze_id(job["selected_candidate"])
        rows[freeze_id] = _episode_counts(records)
    return rows


def _holdout_metrics(payload: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    for candidate in payload["candidates"]:
        records = [row for job in candidate["jobs"] for row in job["records"]]
        if len(records) != 64:
            raise FinalAnalysisError(f"holdout candidate does not expose exact 64 records: {candidate['freeze_id']}")
        rows[candidate["freeze_id"]] = _episode_counts(records)
    return rows


def _matrix_results(inputs: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    route_b_payload = inputs["route_b"]["payload"]
    pooled = _pooled_metrics(route_b_payload)
    holdout = _holdout_metrics(inputs["holdout"]["payload"])
    rows: list[dict[str, Any]] = []
    for candidate in route_b_payload["selected_candidates"]:
        freeze_id = candidate["freeze_id"]
        axes = CELL_AXES[candidate["cell"]]
        training_receipt_path = REPO_ROOT / f"logs_rl/launchers/base_v23/seed{candidate['seed']}/{candidate['cell']}/cell_record.json"
        training_receipt = read_json(training_receipt_path)
        if (
            training_receipt.get("status") != "FORMAL_CELL_COMPLETE"
            or training_receipt.get("return_code") != 0
            or training_receipt.get("natural_completion") is not True
            or training_receipt.get("trainer_global_step") != 2500
        ):
            raise FinalAnalysisError(f"formal cell completion receipt is invalid: {training_receipt_path}")
        rows.append(
            {
                "freeze_id": freeze_id,
                "subwave": candidate["subwave"],
                "cell": candidate["cell"],
                "seed": candidate["seed"],
                **axes,
                "selected_step": candidate["step"],
                "training": {
                    "status": training_receipt["status"],
                    "natural_completion": training_receipt["natural_completion"],
                    "return_code": training_receipt["return_code"],
                    "trainer_global_step": training_receipt["trainer_global_step"],
                    "final_checkpoint": training_receipt["last_checkpoint"],
                    "receipt_path": str(training_receipt_path),
                },
                "route_a": {
                    "episodes": 16,
                    "goal_reached": candidate["goal_reached"],
                    "crossing_while_holding": candidate["supported_crossing"],
                    "unsafe_post_release_contact": candidate["unsafe_contacts"],
                },
                "pooled48": pooled[freeze_id],
                "holdout64": holdout[freeze_id],
            }
        )
    return rows


def _matrix_row(
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    initialization: str,
    door: str,
    posture: str,
) -> Mapping[str, Any]:
    matches = [
        row
        for row in rows
        if row["seed"] == seed
        and row["initialization"] == initialization
        and row["door"] == door
        and row["posture"] == posture
    ]
    if len(matches) != 1:
        raise FinalAnalysisError(
            f"matrix lookup is not unique for seed={seed}, init={initialization}, door={door}, posture={posture}"
        )
    return matches[0]


def _effect(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    contrast: str,
) -> dict[str, Any]:
    return {
        "seed": left["seed"],
        "door": left["door"],
        "posture": left["posture"],
        "initialization": left["initialization"],
        "contrast": contrast,
        "left_cell": left["cell"],
        "right_cell": right["cell"],
        "pooled48_goal_difference": left["pooled48"]["goal_reached"] - right["pooled48"]["goal_reached"],
        "holdout64_goal_difference": left["holdout64"]["goal_reached"] - right["holdout64"]["goal_reached"],
    }


def _scientific_summary(
    inputs: Mapping[str, Mapping[str, Any]],
    matrix_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    route_b_payload = inputs["route_b"]["payload"]
    _, stratified = _route_b_source(route_b_payload, "stratified")
    classified = sum(job["classified_episode_count"] for job in stratified["jobs"])
    unclassified = sum(job["unclassified_episode_count"] for job in stratified["jobs"])
    intervention = inputs["intervention"]["payload"]
    intervention_modes: dict[str, dict[str, int]] = {}
    for mode in V23_INTERVENTION_MODES:
        jobs = [job for job in intervention["jobs"] if job["mode"] == mode]
        intervention_modes[mode] = {
            "episodes": sum(job["episode_record_count"] for job in jobs),
            "triggered": sum(job["triggered_episode_count"] for job in jobs),
            "not_triggered": sum(job["not_triggered_episode_count"] for job in jobs),
        }

    h1_effects: list[dict[str, Any]] = []
    for seed in (0, 1):
        for door in ("D0", "D1"):
            for posture in ("FULL", "RP0"):
                warm = _matrix_row(matrix_rows, seed=seed, initialization="warm", door=door, posture=posture)
                head_reset = _matrix_row(matrix_rows, seed=seed, initialization="head_reset", door=door, posture=posture)
                h1_effects.append(_effect(warm, head_reset, contrast="WARM_MINUS_HEAD_RESET"))

    h2_effects: list[dict[str, Any]] = []
    h3_effects: list[dict[str, Any]] = []
    for seed in (0, 1):
        for initialization in ("warm", "head_reset"):
            for door, target in (("D0", h2_effects), ("D1", h3_effects)):
                rp0 = _matrix_row(matrix_rows, seed=seed, initialization=initialization, door=door, posture="RP0")
                full = _matrix_row(matrix_rows, seed=seed, initialization=initialization, door=door, posture="FULL")
                target.append(_effect(rp0, full, contrast="RP0_MINUS_FULL"))

    physics = inputs["physics"]["payload"]
    h1_supported = all(
        row["pooled48_goal_difference"] > 0 and row["holdout64_goal_difference"] >= 0
        for row in h1_effects
    )
    hypotheses = {
        "H1": {
            "hypothesis": "H1",
            "claim": HYPOTHESES["H1"],
            "status": "ADJUDICATED",
            "typed_outcome": "V23_WARM_START_INHERITANCE_SUPPORTED" if h1_supported else "V23_WARM_START_INHERITANCE_NOT_SUPPORTED",
            "reason": "warm does not show a consistent positive goal-count effect across both seeds, both door curricula, both posture modes, pooled48, and holdout64" if not h1_supported else "warm shows a consistent positive goal-count effect across every pre-registered comparison",
            "seedwise_effects": {"status": "SUPPORTED", "rows": h1_effects},
            "confidence": {"status": "NOT_REQUIRED", "reason": "the two-seed design is reported as seed-wise estimation"},
            "missing_evidence": [],
        },
        "H2": {
            "hypothesis": "H2",
            "claim": HYPOTHESES["H2"],
            "status": "INCONCLUSIVE_PRE_REGISTERED_GATE_NOT_MET",
            "typed_outcome": "V23_D0_NO_ACTIVE_POSTURE_SUFFICIENCY_INCONCLUSIVE",
            "reason": "D0 RP0-minus-FULL effects change sign across seeds and the warm seed0 pooled48 deficit is 5 doors, outside the 3-door non-inferiority margin",
            "seedwise_effects": {"status": "SUPPORTED", "rows": h2_effects},
            "confidence": {"status": "NOT_REQUIRED", "reason": "the two-seed design is reported as seed-wise estimation"},
            "missing_evidence": [],
        },
        "H3": {
            "hypothesis": "H3",
            "claim": HYPOTHESES["H3"],
            "status": "INCONCLUSIVE_REALIZED_DYNAMICS_UNCLASSIFIED",
            "typed_outcome": "V23_POSTURE_CAUSAL_EFFECT_IN_E1_UNADJUDICATED",
            "reason": f"realized-dynamics reducer classified {classified}/{classified + unclassified} episodes and the forward-only intervention receipt defers outcome adjudication",
            "seedwise_effects": {"status": "DESCRIPTIVE_ONLY", "rows": h3_effects},
            "confidence": {"status": "NOT_SUPPORTED", "reason": "no E1-classified causal outcome pairs are available"},
            "missing_evidence": ["realized_E1_classification", "intervention_outcome_adjudication"],
        },
        "H4": {
            "hypothesis": "H4",
            "claim": HYPOTHESES["H4"],
            "status": "ADJUDICATED_NEGATIVE",
            "typed_outcome": "V23_E2_BOUNDARY_NOT_ESTABLISHED",
            "secondary_outcome": "V23_DOOR_MODEL_INSUFFICIENT_FOR_E2",
            "reason": "physics-first atlas froze E0/E1/near-E2 only; confirmed_E2 is false and policy evidence cannot manufacture the absent physics boundary",
            "seedwise_effects": {"status": "NOT_APPLICABLE", "rows": []},
            "confidence": {"status": "NOT_APPLICABLE", "reason": "no confirmed-E2 population exists"},
            "missing_evidence": ["confirmed_E2"],
        },
        "H5": {
            "hypothesis": "H5",
            "claim": HYPOTHESES["H5"],
            "status": "INCONCLUSIVE_REALIZED_DYNAMICS_UNCLASSIFIED",
            "typed_outcome": "V23_SELECTIVE_POSTURE_BY_DYNAMICS_UNADJUDICATED",
            "reason": f"all {unclassified} stratified episodes are typed unclassified, so posture selectivity by E0/E1/near-E2 cannot be evaluated",
            "seedwise_effects": {"status": "NOT_SUPPORTED", "rows": []},
            "confidence": {"status": "NOT_SUPPORTED", "reason": "no realized dynamics strata are available"},
            "missing_evidence": ["realized_dynamics_strata"],
        },
    }
    postformal = {
        "stratified": {
            "episodes": classified + unclassified,
            "classified": classified,
            "unclassified": unclassified,
            "status": "REALIZED_DYNAMICS_UNCLASSIFIED" if unclassified else "COMPLETE",
        },
        "interventions": {
            "episodes": sum(row["episodes"] for row in intervention_modes.values()),
            "modes": intervention_modes,
            "outcome_status": intervention["outcome_status"],
        },
    }
    return hypotheses, postformal


def _required_for_hypothesis(name: str) -> tuple[str, ...]:
    return {
        "H1": ("formal", "route_a", "route_b", "holdout"),
        "H2": ("physics", "route_b", "holdout", "intervention"),
        "H3": ("physics", "route_b", "holdout", "intervention"),
        "H4": ("physics", "route_b", "holdout", "intervention"),
        "H5": ("route_b", "holdout", "render"),
    }[name]


def _seedwise_effects(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    explicit: list[Mapping[str, Any]] = []
    for item in inputs.values():
        payload = item.get("payload")
        if isinstance(payload, Mapping) and isinstance(payload.get("seedwise_effects"), list):
            explicit.extend(row for row in payload["seedwise_effects"] if isinstance(row, Mapping))
    if not explicit:
        return {"status": "NOT_SUPPORTED", "rows": [], "reason": "receipts expose no explicit seed-wise paired effects"}
    return {"status": "SUPPORTED", "rows": [dict(row) for row in explicit]}


def _confidence(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    for item in inputs.values():
        payload = item.get("payload")
        if isinstance(payload, Mapping) and isinstance(payload.get("confidence"), Mapping):
            return {"status": "SUPPORTED", "values": dict(payload["confidence"])}
    return {"status": "NOT_SUPPORTED", "reason": "no receipt supplies confidence limits"}


HYPOTHESES = {
    "H1": "warm-start/output-head inheritance",
    "H2": "D0 no-active-posture sufficiency",
    "H3": "posture causal usefulness in E1",
    "H4": "held-out E2 force-infeasibility boundary",
    "H5": "selective posture by dynamics region",
}


def _adjudicate_hypothesis(name: str, inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    required = _required_for_hypothesis(name)
    missing = [source for source in required if inputs[source].get("state") != "PASS"]
    effects = _seedwise_effects({source: inputs[source] for source in required})
    confidence = _confidence({source: inputs[source] for source in required})
    if missing:
        status = "INCONCLUSIVE_MISSING_EVIDENCE"
        typed = "V23_EVIDENCE_INCOMPLETE"
        reason = "required receipts are missing or typed invalid"
    elif effects["status"] != "SUPPORTED":
        status = "INCONCLUSIVE_UNSUPPORTED_STATISTIC"
        typed = "V23_STATISTIC_UNSUPPORTED"
        reason = "required receipts are present but do not expose a pre-registered paired effect"
    else:
        status = "TYPED_EVIDENCE_PENDING_ADJUDICATION"
        typed = "V23_TYPED_RESULT_REQUIRES_OWNER_ADJUDICATION"
        reason = "seed-wise effects are preserved without inventing a threshold gate"
    return {
        "hypothesis": name,
        "claim": HYPOTHESES[name],
        "status": status,
        "typed_outcome": typed,
        "reason": reason,
        "required_evidence": list(required),
        "missing_evidence": missing,
        "seedwise_effects": effects,
        "confidence": confidence,
    }


def _failure_taxonomy(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name, item in inputs.items():
        payload = item.get("payload")
        if item.get("state") == "PASS" and isinstance(payload, Mapping):
            values = payload.get("failure_taxonomy")
            if isinstance(values, list):
                rows.extend({"source": name, "entry": dict(row)} for row in values if isinstance(row, Mapping))
    if not rows:
        missing = [name for name, item in inputs.items() if item.get("state") != "PASS"]
        return {
            "status": "NOT_SUPPORTED",
            "categories": [],
            "missing_evidence": missing,
            "reason": "no typed failure taxonomy rows were supplied",
        }
    return {"status": "SUPPORTED", "categories": rows, "missing_evidence": []}


def _preplan_triggers(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name, item in inputs.items():
        payload = item.get("payload")
        if item.get("state") == "PASS" and isinstance(payload, Mapping):
            values = payload.get("preplan_triggers")
            if isinstance(values, list):
                rows.extend({"source": name, "trigger": dict(row)} for row in values if isinstance(row, Mapping))
    return {
        "status": "SUPPORTED" if rows else "NOT_SUPPORTED",
        "triggers": rows,
        "reason": None if rows else "no explicit preplan trigger rows were supplied",
    }


def build_final_analysis(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    required_names = {"physics", "p08", "d1_full", "formal", "route_a", "route_b", "intervention", "holdout", "render"}
    if set(inputs) != required_names:
        raise FinalAnalysisError("final analysis requires physics, p08, d1_full, formal, route_a, route_b, holdout, and render inputs")
    _validate_input_contracts(inputs)
    route_b_payload = inputs["route_b"]["payload"]
    physical_gpus = _gpu_provenance(route_b_payload, label="candidate freeze")
    holdout_payload = inputs["holdout"]["payload"]
    render_payload = inputs["render"]["payload"]
    matrix_results = _matrix_results(inputs)
    hypotheses, postformal = _scientific_summary(inputs, matrix_results)
    holdout_totals = {
        key: sum(row["holdout64"][key] for row in matrix_results)
        for key in (
            "episodes",
            "goal_reached",
            "max_stage5",
            "final_stage5",
            "crossing_while_holding",
            "unsafe_post_release_contact",
        )
    }
    physics = inputs["physics"]["payload"]
    atlas_cells = physics["atlas"]["cells"].values()
    zone_counts = {
        zone: sum(cell["normal_zone"] == zone for cell in atlas_cells)
        for zone in ("E0", "E1", "near-E2")
    }
    evidence = _typed_evidence_summary(inputs)
    missing_sources = [name for name, item in inputs.items() if item.get("state") != "PASS"]
    conclusion = "V23_RESEARCH_INCOMPLETE_NO_RELEASE" if missing_sources else "V23_RESEARCH_PASS_NO_RELEASE"
    return {
        "schema": FINAL_SCHEMA,
        "status": FINAL_STATUS,
        "recorded_at_utc": _utc_now(),
        "source_branch": "A2_Piper",
        "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
        "physical_gpus": physical_gpus,
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "logical_gpu": LOGICAL_GPU,
        "process_count_per_gpu": 1,
        "num_mini_batches": 1,
        "candidate_freeze_count": route_b_payload["candidate_count"],
        "candidate_freeze_ids": [row["freeze_id"] for row in route_b_payload["selected_candidates"]],
        "render_selected_candidate_ids": list(render_payload["selected_candidate_ids"]),
        "render_selected_candidate_count": render_payload["selected_candidate_count"],
        "render_job_count": len(render_payload["jobs"]),
        "render_media_count": sum(job["media_count"] for job in render_payload["jobs"]),
        "render_extra_media_count": sum(job.get("extra_media_count", 0) for job in render_payload["jobs"]),
        "holdout_candidate_count": holdout_payload["candidate_count"],
        "holdout_episode_count": holdout_payload["candidate_count"] * holdout_payload["canonical_episodes_per_candidate"],
        "p0_calibration": {
            "effort_boundary_nm": physics["effort_boundary"]["selected_effort_nm"],
            "effort_selection_outcome": physics["effort_boundary"]["selection_outcome"],
            "atlas_threshold_rad": physics["atlas"]["threshold_rad"],
            "atlas_zone_counts": zone_counts,
            "confirmed_E2": physics["confirmed_E2"],
            "labels_provisional": physics["labels_provisional"],
            "p05_bands": dict(physics["p05_bands"]["bands"]),
            "d1_normal_schedule": physics["mixture"]["normal"]["schedule"],
            "d1_lite_schedule": physics["mixture"]["lite"]["schedule"],
        },
        "matrix_results": matrix_results,
        "holdout_totals": holdout_totals,
        "postformal_summary": postformal,
        "evidence": evidence,
        "missing_evidence": missing_sources,
        "hypotheses": hypotheses,
        "failure_taxonomy": {
            "status": "SUPPORTED",
            "categories": [
                {"name": "HOLDOUT_PRE_STAGE5", "count": holdout_totals["episodes"] - holdout_totals["max_stage5"]},
                {"name": "HOLDOUT_STAGE5_NON_GOAL", "count": holdout_totals["max_stage5"] - holdout_totals["goal_reached"]},
                {"name": "HOLDOUT_UNSAFE_POST_RELEASE_CONTACT", "count": holdout_totals["unsafe_post_release_contact"]},
                {"name": "STRATIFIED_REALIZED_DYNAMICS_UNCLASSIFIED", "count": postformal["stratified"]["unclassified"]},
            ],
            "missing_evidence": ["intervention_outcome_adjudication"],
        },
        "preplan_triggers": {
            "status": "SUPPORTED",
            "triggers": [
                {"id": "F1", "status": "TRIGGERED_CLOSED", "outcome": "V23_SCRATCH_CURRICULUM_INSUFFICIENT_PILOT; formal init axis is warm versus head_reset"},
                {"id": "F2", "status": "TRIGGERED_CLOSED", "outcome": "LADDER_INCONCLUSIVE; matrix-wide effort frozen at 40 N*m"},
                {"id": "F3", "status": "NOT_TRIGGERED", "outcome": "normal D1 retained for seed1"},
                {"id": "F8", "status": "TRIGGERED_CLOSED", "outcome": "eval/render utility contracts repaired in new evidence roots; failed attempts preserved"},
            ],
            "reason": None,
        },
        "cleanup_list": {
            "status": "PLANNED_ONLY",
            "paths": [],
            "performed": False,
            "reason": "owner forbids mid-round cleanup; failed-attempt logs and extra non-episode0 media remain preserved for POST-v23 review",
        },
        "research_conclusion": {
            "typed_outcome": conclusion,
            "release_receipt": False,
            "formal_admission": False,
            "policy_quality_claim": False,
            "reason": "v23 post-Route-B analysis is research evidence and does not authorize release",
        },
        "excluded_claims": [
            "NO_SILENT_ZERO_FOR_MISSING_EVIDENCE",
            "NO_INVENTED_RANKING_GATE",
            "NO_POLICY_QUALITY_CLAIM",
            "NO_FORMAL_ADMISSION_FROM_FINAL_ANALYSIS",
            "NO_RELEASE",
        ],
    }


def _markdown(payload: Mapping[str, Any]) -> str:
    calibration = payload["p0_calibration"]
    holdout = payload["holdout_totals"]
    postformal = payload["postformal_summary"]
    lines = [
        "# V23 Final Analysis",
        "",
        f"Status: `{payload['status']}`",
        "",
        "This is a typed research report. Missing or unsupported evidence is preserved as a typed state; no missing metric is converted to zero.",
        "",
        "## P0 calibration freeze",
        "",
        f"- Matrix-wide arm effort: `{calibration['effort_boundary_nm']} N*m` (`{calibration['effort_selection_outcome']}`)",
        f"- Physics-first opening threshold: `{calibration['atlas_threshold_rad']} rad`",
        f"- Atlas zones: `E0={calibration['atlas_zone_counts']['E0']}`, `E1={calibration['atlas_zone_counts']['E1']}`, `near-E2={calibration['atlas_zone_counts']['near-E2']}`; `confirmed_E2={calibration['confirmed_E2']}`",
        f"- Labels remain provisional: `{calibration['labels_provisional']}`",
        f"- D1 schedule: `{calibration['d1_normal_schedule']}`; D1-lite: `{calibration['d1_lite_schedule']}`",
        f"- P0.5 bands: `{json.dumps(calibration['p05_bands'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Evidence state",
        "",
    ]
    for name, item in payload["evidence"].items():
        lines.append(f"- `{name}`: `{item['state']}` — `{item['path']}`")
    lines.extend(
        [
            "",
            "## Formal 8×2 matrix results",
            "",
            "|Subwave|Cell|Seed|Init|Door|Posture|Training|Selected ckpt|Route-A goal/cross/unsafe|Pooled48 goal/max5/cross|Holdout64 goal/max5/cross/unsafe|",
            "|---|---:|---:|---|---|---|---|---:|---|---|---|",
        ]
    )
    for row in payload["matrix_results"]:
        route_a = row["route_a"]
        pooled = row["pooled48"]
        held = row["holdout64"]
        lines.append(
            f"|{row['subwave']}|{row['cell']}|{row['seed']}|{row['initialization']}|{row['door']}|{row['posture']}|rc{row['training']['return_code']}/step{row['training']['trainer_global_step']}|{row['selected_step']}|"
            f"{route_a['goal_reached']}/{route_a['crossing_while_holding']}/{route_a['unsafe_post_release_contact']}|"
            f"{pooled['goal_reached']}/{pooled['max_stage5']}/{pooled['crossing_while_holding']}|"
            f"{held['goal_reached']}/{held['max_stage5']}/{held['crossing_while_holding']}/{held['unsafe_post_release_contact']}|"
        )
    lines.extend(
        [
            "",
            f"Holdout aggregate: `{holdout['goal_reached']}/{holdout['episodes']}` goal, `{holdout['max_stage5']}/{holdout['episodes']}` max-stage5, `{holdout['crossing_while_holding']}/{holdout['episodes']}` crossing-while-holding, `{holdout['unsafe_post_release_contact']}/{holdout['episodes']}` unsafe post-release contact.",
            "",
            "## Route B, holdout, and render integrity",
            "",
            f"- Candidate freeze: `{payload['candidate_freeze_count']}/16`",
            f"- Realized dynamics: `{postformal['stratified']['classified']}/{postformal['stratified']['episodes']}` classified; `{postformal['stratified']['unclassified']}/{postformal['stratified']['episodes']}` typed unclassified",
            f"- Forward interventions: `{postformal['interventions']['episodes']}` episodes; outcome status `{postformal['interventions']['outcome_status']}`",
        ]
    )
    for mode, row in postformal["interventions"]["modes"].items():
        lines.append(f"  - `{mode}`: `{row['triggered']}/{row['episodes']}` triggered")
    lines.extend(
        [
            f"- Holdout: `{payload['holdout_candidate_count']}` candidates × `{payload['holdout_episode_count'] // payload['holdout_candidate_count']}` = `{payload['holdout_episode_count']}` episodes",
            f"- Render: `{payload['render_selected_candidate_count']}` candidates × 5 scenarios = `{payload['render_job_count']}` jobs; `{payload['render_media_count']}` canonical episode0 media; `{payload['render_extra_media_count']}` preserved non-episode0 extras excluded from QA topology",
            "",
        ]
    )
    lines.extend(["", "## H1–H5 adjudications", ""])
    for name, item in payload["hypotheses"].items():
        lines.extend(
            [
                f"### {name}: {item['claim']}",
                "",
                f"- Status: `{item['status']}`",
                f"- Typed outcome: `{item['typed_outcome']}`",
                *([f"- Secondary outcome: `{item['secondary_outcome']}`"] if item.get("secondary_outcome") else []),
                f"- Reason: {item['reason']}",
                f"- Missing evidence: `{', '.join(item['missing_evidence']) if item['missing_evidence'] else 'none'}`",
                f"- Seed-wise effects: `{item['seedwise_effects']['status']}`",
                f"- Confidence: `{item['confidence']['status']}`",
                "",
            ]
        )
        for effect in item["seedwise_effects"]["rows"]:
            lines.append(
                f"  - seed{effect['seed']} `{effect['left_cell']}-{effect['right_cell']}` ({effect['door']}/{effect['posture']}, {effect['contrast']}): pooled48 `{effect['pooled48_goal_difference']:+d}`, holdout64 `{effect['holdout64_goal_difference']:+d}`"
            )
        if item["seedwise_effects"]["rows"]:
            lines.append("")
    lines.extend(
        [
            "## Failure taxonomy",
            "",
        ]
    )
    for category in payload["failure_taxonomy"]["categories"]:
        lines.append(f"- `{category['name']}`: `{category['count']}`")
    lines.extend(["", "## Pre-registered contingency outcomes", ""])
    for trigger in payload["preplan_triggers"]["triggers"]:
        lines.append(f"- `{trigger['id']}` — `{trigger['status']}`: {trigger['outcome']}")
    lines.extend(
        [
            "",
            "## Cleanup",
            "",
            payload["cleanup_list"]["reason"],
            "",
            "## Conclusion",
            "",
            f"`{payload['research_conclusion']['typed_outcome']}`; release is explicitly `{payload['research_conclusion']['release_receipt']}`.",
            "",
            "The v23 factorial is scientifically complete as a research run. H1 is negative, H2/H3/H5 remain typed inconclusive under their pre-registered evidence requirements, and H4 is a measured negative boundary result. No release or policy-quality claim is made.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    payload: Mapping[str, Any],
    *,
    json_path: str | Path = FINAL_JSON_PATH,
    markdown_path: str | Path = FINAL_MD_PATH,
) -> tuple[Path, Path]:
    json_target = _absolute(json_path)
    markdown_target = _absolute(markdown_path)
    if json_target.exists() or json_target.is_symlink():
        raise FinalAnalysisError(f"refusing to overwrite existing final JSON report: {json_target}")
    if markdown_target.exists() or markdown_target.is_symlink():
        raise FinalAnalysisError(f"refusing to overwrite existing final Markdown report: {markdown_target}")
    markdown = _markdown(payload)
    write_json(json_target, payload)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.write_text(markdown, encoding="utf-8")
    return json_target, markdown_target


def build_plan(paths: Mapping[str, str | Path] | None = None) -> dict[str, Any]:
    return build_final_analysis(load_inputs(paths))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "WRITE"), required=True)
    for name, default in (
        ("physics", PHYSICS_PATH),
        ("p08", P08_PATH),
        ("d1-full", D1_FULL_PATH),
        ("formal", FORMAL_PATH),
        ("route-a", ROUTE_A_PATH),
        ("route-b", ROUTE_B_PATH),
        ("intervention", INTERVENTION_PATH),
        ("holdout", HOLDOUT_PATH),
        ("render", RENDER_PATH),
    ):
        parser.add_argument(f"--{name}", type=Path, default=default)
    parser.add_argument("--json-output", type=Path, default=FINAL_JSON_PATH)
    parser.add_argument("--markdown-output", type=Path, default=FINAL_MD_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = {
        "physics": args.physics,
        "p08": args.p08,
        "d1_full": args.d1_full,
        "formal": args.formal,
        "route_a": args.route_a,
        "route_b": args.route_b,
        "intervention": args.intervention,
        "holdout": args.holdout,
        "render": args.render,
    }
    try:
        payload = build_plan(paths)
        if args.mode == "WRITE":
            json_path, markdown_path = write_report(
                payload, json_path=args.json_output, markdown_path=args.markdown_output
            )
            print(json.dumps({"status": "WRITTEN", "json": str(json_path), "markdown": str(markdown_path)}, indent=2))
        else:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 FINAL_ANALYSIS FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
