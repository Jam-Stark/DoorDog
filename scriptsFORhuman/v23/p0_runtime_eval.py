"""Source-locked base_v23 P0 runtime-evaluation command builder.

The runner mirrors the v22 Route-B lifecycle (BUILD, RUN, ANALYZE) while
keeping the P0 artifact JSON free of content digests.  BUILD is deterministic
and CPU-only; RUN executes only when ``--execute`` is explicit; ANALYZE emits
effort-ladder observations and deliberately leaves rung selection to
``effort_ladder.py``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._v23_common import (
    REPO_ROOT,
    V23_EFFORT_RUNGS,
    V23_LEGAL_PHYSICAL_GPUS,
    V23_WARM_START_PATH,
    V23Error,
    emit_payload,
    finite_number,
    read_json,
    require_file,
)


P0_OUTPUT_ROOT = REPO_ROOT / "logs_eval/base_v23/p0"
CANONICAL_SOURCE = REPO_ROOT / (
    "logs_eval/base_v21B/preformal_20260802_r10/V21B_HEAVY16_MANIFEST.json"
)
HEAVY_SOURCE = CANONICAL_SOURCE
CENSUS_PRIOR = REPO_ROOT / (
    "logs_eval/base_v21B/preformal_20260802_r10/V21B_CENSUS_PLAN.json"
)
CURRENT_SELECTOR_TOPOLOGIES = ("canonical16", "heavy16")
HEAVY20_SOURCE_ORDER = (4, 0, 1)
TEMPORAL_COMBINED_SCHEMA = "a2_piper_base_v23_p0_temporal_combined_v1"
ARM_JOINT_COUNT = 6
TOTAL_DOF_COUNT = 20
FROZEN_LEG_EFFORTS = (120.0, 120.0, 180.0) * 4
FROZEN_GRIPPER_EFFORTS = (45.0, 45.0)

# The measured launcher contract is fixed: four children per wave, with each
# physical GPU exposed as the child's logical ``cuda:0``.  Keep this table
# explicit so the source/provenance record cannot drift with effort ordering.
P0_RUNTIME_WAVES = (
    (
        (100.0, "canonical16", 0),
        (100.0, "heavy16", 1),
        (60.0, "canonical16", 2),
        (60.0, "heavy16", 3),
    ),
    (
        (40.0, "canonical16", 0),
        (40.0, "heavy16", 1),
        (30.0, "canonical16", 2),
        (30.0, "heavy16", 3),
    ),
    (
        (25.0, "canonical16", 0),
        (25.0, "heavy16", 1),
        (20.0, "canonical16", 2),
        (20.0, "heavy16", 3),
    ),
)


def _validate_effort_rung(value: Any) -> float:
    effort = finite_number(value, name="effort_nm")
    if effort not in V23_EFFORT_RUNGS:
        raise V23Error(
            f"effort_nm must be one of the registered rungs {V23_EFFORT_RUNGS}; got {effort}"
        )
    return effort


def build_effort_limit_list(effort_nm: float) -> list[float]:
    """Expand one registered rung into the simulator's exact 20-DOF order."""

    effort = _validate_effort_rung(effort_nm)
    values = list(FROZEN_LEG_EFFORTS) + [effort] * ARM_JOINT_COUNT + list(FROZEN_GRIPPER_EFFORTS)
    validate_effort_limit_list(values, effort)
    return values


def validate_effort_limit_list(values: Sequence[Any], effort_nm: float) -> None:
    """Validate the frozen leg/arm/gripper ordering before a launch."""

    effort = _validate_effort_rung(effort_nm)
    if isinstance(values, (str, bytes)) or len(values) != TOTAL_DOF_COUNT:
        raise V23Error(
            "robot.dof_effort_limit_list must contain exactly 20 values in the source DOF order"
        )
    normalized = [finite_number(value, name=f"dof_effort_limit_list[{index}]") for index, value in enumerate(values)]
    expected = list(FROZEN_LEG_EFFORTS) + [effort] * ARM_JOINT_COUNT + list(FROZEN_GRIPPER_EFFORTS)
    if normalized != expected:
        raise V23Error(
            "robot.dof_effort_limit_list does not match the frozen 12-leg/6-arm/j7-j8 order"
        )


def _source_manifest(path: Path, *, topology: str) -> dict[str, Any]:
    if topology not in CURRENT_SELECTOR_TOPOLOGIES:
        raise V23Error(f"unsupported current v21B selector topology: {topology!r}")
    target = require_file(path, label=f"v21B {topology} source manifest")
    payload = read_json(target)
    if payload.get("schema") != "a2_piper_base_v21B_heavy16_manifest_v1":
        raise V23Error(f"v21B {topology} manifest schema is not the registered heavy16 schema")
    if payload.get("status") != "STATIC_PASS":
        raise V23Error(f"v21B {topology} manifest is not STATIC_PASS")
    canonical_rows = payload.get("canonical_manifest_rows")
    heavy_rows = payload.get("manifest_rows")
    if not isinstance(canonical_rows, list) or len(canonical_rows) != 32:
        raise V23Error(f"v21B {topology} manifest is not bound to 32 canonical rows")
    if not isinstance(heavy_rows, list) or len(heavy_rows) != 16:
        raise V23Error(f"v21B {topology} manifest is not bound to 16 heavy rows")
    canonical_ids = [row.get("scenario_id") if isinstance(row, Mapping) else None for row in canonical_rows]
    heavy_ids = [row.get("scenario_id") if isinstance(row, Mapping) else None for row in heavy_rows]
    if (
        any(not isinstance(item, str) or not item for item in canonical_ids + heavy_ids)
        or len(set(canonical_ids)) != 32
        or len(set(heavy_ids)) != 16
        or not set(heavy_ids).issubset(canonical_ids)
        or len(set(canonical_ids) - set(heavy_ids)) != 16
    ):
        raise V23Error(f"v21B {topology} manifest identity/cardinality is unbound")
    selected_rows = heavy_rows if topology == "heavy16" else [
        row for row in canonical_rows if row.get("scenario_id") not in set(heavy_ids)
    ]
    if len(selected_rows) != 16:
        raise V23Error(f"v21B {topology} selector does not resolve to exactly 16 rows")
    plain_rows = []
    for index, row in enumerate(selected_rows):
        if not isinstance(row, Mapping):
            raise V23Error(f"v21B {topology} selected row {index} is not a mapping")
        scenario_id = row.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise V23Error(f"v21B {topology} selected row {index} has no readable scenario_id")
        plain_row = {"scenario_id": scenario_id}
        for field in ("handle_height_m", "door_weight_kg", "hinge_force_nm"):
            value = finite_number(row.get(field), name=f"{topology}[{index}].{field}")
            if value <= 0.0:
                raise V23Error(f"v21B {topology} selected row {index} {field} must be positive")
            plain_row[field] = value
        plain_rows.append(plain_row)
    plain_manifest = {
        "schema": "a2_piper_base_v23_p0_plain_scenario_manifest_v1",
        "status": "STATIC_PLAIN",
        "topology": topology,
        "source_manifest_path": str(target.resolve()),
        "source_role": "historical_prior_only",
        "rows": plain_rows,
    }
    return {
        "topology": topology,
        "path": str(target),
        "schema": payload["schema"],
        "status": payload["status"],
        "selected_row_count": len(selected_rows),
        "binding_state": "HISTORICAL_SOURCE_VALIDATED",
        "source_role": "historical_prior_only",
        "plain_manifest": plain_manifest,
    }


def build_source_lock() -> dict[str, Any]:
    """Validate and describe the shared canonical16/heavy16 source inputs."""

    canonical = _source_manifest(CANONICAL_SOURCE, topology="canonical16")
    heavy = _source_manifest(HEAVY_SOURCE, topology="heavy16")
    census_prior = require_file(CENSUS_PRIOR, label="historical v21B census prior")
    census_payload = read_json(census_prior)
    if census_payload.get("schema") != "a2_piper_base_v21B_torque_census_v1":
        raise V23Error("historical v21B census prior schema is not recognized")
    return {
        "schema": "a2_piper_base_v23_p0_source_lock_v1",
        "source_binding": "historical_v21B_manifest_path_schema_status_cardinality",
        "current_selector_support": list(CURRENT_SELECTOR_TOPOLOGIES),
        "current_topology_basis": "selector_support",
        "selectors": {"canonical16": canonical, "heavy16": heavy},
        "historical_census_prior": {
            "path": str(census_prior),
            "role": "prior_only",
            "status": census_payload.get("status"),
        },
        "same_inputs_across_effort_rungs": True,
        "heavy20_source_order": list(HEAVY20_SOURCE_ORDER),
        "manifest_unbound_policy": "fail_fast",
    }


def _render_override_list(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{float(value):.6g}" for value in values) + "]"


def _validate_gpu(gpu: int) -> int:
    if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu not in V23_LEGAL_PHYSICAL_GPUS:
        raise V23Error(f"physical GPU must be one of {V23_LEGAL_PHYSICAL_GPUS}; got {gpu!r}")
    return gpu


def build_eval_argv(
    effort_nm: float,
    *,
    topology: str,
    output_dir: Path,
    plain_manifest_path: Path,
    gpu: int,
    source_lock: Mapping[str, Any],
) -> tuple[list[str], dict[str, str]]:
    """Build one source-locked module-eval argv/env pair."""

    effort = _validate_effort_rung(effort_nm)
    _validate_gpu(gpu)
    if topology not in CURRENT_SELECTOR_TOPOLOGIES:
        raise V23Error(f"unsupported v21B selector topology: {topology!r}")
    selectors = source_lock.get("selectors")
    if not isinstance(selectors, Mapping) or topology not in selectors:
        raise V23Error(f"source lock has no bound selector for {topology}")
    selector = selectors[topology]
    if not isinstance(selector, Mapping) or selector.get("binding_state") != "HISTORICAL_SOURCE_VALIDATED":
        raise V23Error(f"source lock selector {topology} is unbound")
    plain_manifest = selector.get("plain_manifest")
    if not isinstance(plain_manifest, Mapping):
        raise V23Error(f"source lock selector {topology} has no plain v23 manifest")
    if plain_manifest.get("topology") != topology:
        raise V23Error(f"source lock selector {topology} plain manifest topology disagrees")
    plain_manifest_path = Path(plain_manifest_path)
    if not plain_manifest_path.is_absolute():
        raise V23Error(f"v23 plain scenario manifest path must be absolute: {plain_manifest_path}")
    limits = build_effort_limit_list(effort)
    checkpoint = require_file(REPO_ROOT / V23_WARM_START_PATH, label="G1 step1250 warm checkpoint")
    output_dir = Path(output_dir)
    argv = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++headless=true",
        "++num_envs=16",
        "++seed=0",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        "++algo.config.eval.num_eval_episodes=16",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_v23_p0_runtime_export=true",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v23_evidence_enabled=true",
        "++env.config.a2_v23_torque_telemetry_enabled=true",
        "++env.config.a2_v23_p0_temporal_evidence_enabled=true",
        "++env.config.a2_v23_p0_checkpoint_load_mode=policy_only",
        f"++env.config.a2_v23_effort_profile_nm={effort:.6g}",
        f"++env.config.a2_v23_p0_checkpoint={checkpoint}",
        f"++env.config.a2_v23_p0_config_id=base_v23_p0_G1_effort_{effort:g}_{topology}",
        f"++env.config.a2_v23_p0_scenario_id={topology}_plain16",
        "++env.config.a2_v23_p0_seed=0",
        f"++env.config.a2_v23_p0_plain_prefix_id=G1_{topology}_plain16",
        f"++robot.dof_effort_limit_list={_render_override_list(limits)}",
        "++env.config.a2_v23_p0_plain_scenario_enabled=true",
        f"++env.config.a2_v23_p0_scenario_topology={topology}",
        f"++env.config.a2_v23_p0_scenario_manifest_path={plain_manifest_path}",
        f"++eval_output_dir={output_dir}",
    ]
    env = {
        "CUDA_VISIBLE_DEVICES": str(gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }
    return argv, env


def build_runtime_plan(
    *,
    efforts: Sequence[float] = V23_EFFORT_RUNGS,
    topologies: Sequence[str] = CURRENT_SELECTOR_TOPOLOGIES,
    output_root: Path = P0_OUTPUT_ROOT / "torque",
) -> dict[str, Any]:
    """Build all requested rung/topology commands with one shared source lock."""

    source_lock = build_source_lock()
    normalized_efforts = [_validate_effort_rung(value) for value in efforts]
    if not normalized_efforts:
        raise V23Error("runtime plan requires at least one effort rung")
    if len(set(normalized_efforts)) != len(normalized_efforts):
        raise V23Error("runtime plan effort rungs must be unique")
    normalized_topologies = list(topologies)
    if not normalized_topologies or any(item not in CURRENT_SELECTOR_TOPOLOGIES for item in normalized_topologies):
        raise V23Error("runtime plan requires canonical16 and/or heavy16 selector support")
    if len(set(normalized_topologies)) != len(normalized_topologies):
        raise V23Error("runtime plan topologies must be unique")
    runs = []
    requested_efforts = set(normalized_efforts)
    requested_topologies = set(normalized_topologies)
    for wave_index, wave in enumerate(P0_RUNTIME_WAVES, start=1):
        for wave_slot, (effort, topology, gpu) in enumerate(wave):
            if effort not in requested_efforts or topology not in requested_topologies:
                continue
            run_dir = (Path(output_root) / f"effort_{effort:g}" / topology).resolve()
            plain_manifest_path = run_dir / "v23_p0_plain_scenario_manifest.json"
            selector = source_lock["selectors"][topology]
            argv, env = build_eval_argv(
                effort,
                topology=topology,
                output_dir=run_dir,
                plain_manifest_path=plain_manifest_path,
                gpu=gpu,
                source_lock=source_lock,
            )
            runs.append(
                {
                    "rung_index": V23_EFFORT_RUNGS.index(effort),
                    "effort_nm": effort,
                    "topology": topology,
                    "current_topology": topology,
                    "current_topology_authority": "CURRENT_SELECTOR_SUPPORTED",
                    "gpu": gpu,
                    "physical_gpu": gpu,
                    "wave_index": wave_index,
                    "wave_slot": wave_slot,
                    "wave_size": len(wave),
                    "logical_device": "cuda:0",
                    "output_dir": str(run_dir),
                    "plain_manifest_path": str(plain_manifest_path),
                    "plain_manifest": selector["plain_manifest"],
                    "checkpoint_load_mode_requested": "policy_only",
                    "checkpoint_load_mode_effective": "policy_only",
                    "argv": argv,
                    "env": env,
                    "retry_policy": "none",
                }
            )
    return {
        "schema": "a2_piper_base_v23_p0_runtime_plan_v1",
        "cell": "G1",
        "checkpoint_step": 1250,
        "checkpoint_load_mode": "policy_only",
        "checkpoint_load_mode_requested": "policy_only",
        "checkpoint_load_mode_effective": "policy_only",
        "module_eval": "gr00t.rl.eval_agent_trl",
        "source_lock": source_lock,
        "effort_rungs_nm": list(normalized_efforts),
        "topologies": normalized_topologies,
        "runs": runs,
        "wave_count": len(P0_RUNTIME_WAVES),
        "wave_size": len(P0_RUNTIME_WAVES[0]),
        "wave_layout": [
            [
                {
                    "effort_nm": effort,
                    "topology": topology,
                    "physical_gpu": gpu,
                    "logical_device": "cuda:0",
                }
                for effort, topology, gpu in wave
            ]
            for wave in P0_RUNTIME_WAVES
        ],
        "wandb": "disabled",
        "physical_gpus": list(V23_LEGAL_PHYSICAL_GPUS),
        "selection_state": "DEFERRED_TO_EFFORT_LADDER",
    }


def _numeric_observation(value: Any, *, name: str) -> float | None:
    if value == "PENDING":
        return None
    return finite_number(value, name=name)


def combine_temporal_runs(named_paths: Mapping[tuple[float, str], Path]) -> dict[str, Any]:
    """Combine exactly the twelve registered raw rung/topology exports."""

    expected_keys = {(effort, topology) for effort in V23_EFFORT_RUNGS for topology in CURRENT_SELECTOR_TOPOLOGIES}
    if set(named_paths) != expected_keys:
        missing = sorted(expected_keys - set(named_paths))
        extra = sorted(set(named_paths) - expected_keys)
        raise V23Error(f"temporal combiner requires exactly twelve named paths; missing={missing}, extra={extra}")
    combined_records = []
    runs = []
    for effort in V23_EFFORT_RUNGS:
        for topology in CURRENT_SELECTOR_TOPOLOGIES:
            path = Path(named_paths[(effort, topology)])
            payload = read_json(path)
            if payload.get("schema") != "a2_piper_base_v23_p0_temporal_records_v1":
                raise V23Error(f"{path} is not the registered raw temporal export schema")
            if payload.get("temporary_label") != "A0_CANONICAL16_P0_REFERENCE":
                raise V23Error(f"{path} does not preserve the A0 temporary label")
            records = payload.get("records")
            if not isinstance(records, list) or len(records) != 16:
                raise V23Error(f"{path} must contain exactly sixteen temporal episode records")
            env_ids = []
            for index, episode in enumerate(records):
                if not isinstance(episode, Mapping) or episode.get("schema") != "a2_piper_base_v23_p0_temporal_episode_v1":
                    raise V23Error(f"{path}.records[{index}] does not preserve the exact episode schema")
                if episode.get("effort_nm") != effort or episode.get("topology") != topology:
                    raise V23Error(f"{path}.records[{index}] rung/topology disagrees with its registered path")
                if episode.get("temporary_label") != "A0_CANONICAL16_P0_REFERENCE" or episode.get("raw_temporal") is not True:
                    raise V23Error(f"{path}.records[{index}] must preserve the raw A0 temporal markers")
                env_id = episode.get("env_id")
                if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id in env_ids:
                    raise V23Error(f"{path}.records env_id values must be unique integers 0..15")
                if not 0 <= env_id < 16:
                    raise V23Error(f"{path}.records env_id values must be within 0..15")
                env_ids.append(env_id)
                episode_index = episode.get("episode_index")
                if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
                    raise V23Error(f"{path}.records[{index}] episode_index must be a non-negative integer")
                episode_id = episode.get("episode_id")
                if episode_id != f"a2-v23-temporal-env{env_id}-episode{episode_index}":
                    raise V23Error(f"{path}.records[{index}] episode_id does not match env/episode identity")
                provenance = episode.get("source_provenance")
                if not isinstance(provenance, Mapping):
                    raise V23Error(f"{path}.records[{index}] is missing registered source_provenance")
                required = ("checkpoint", "config", "scenario", "topology", "seed", "plain_prefix_id", "env_id", "episode_index", "episode_id", "effort_nm", "checkpoint_load_mode")
                if any(key not in provenance for key in required):
                    raise V23Error(f"{path}.records[{index}] source_provenance schema is incomplete")
                for key in ("checkpoint", "config", "scenario", "plain_prefix_id"):
                    if not isinstance(provenance.get(key), str) or not provenance[key]:
                        raise V23Error(f"{path}.records[{index}] source_provenance.{key} must be non-empty")
                if provenance.get("checkpoint_load_mode") != "policy_only":
                    raise V23Error(f"{path}.records[{index}] source_provenance.checkpoint_load_mode must be policy_only")
                if (
                    isinstance(provenance.get("seed"), bool)
                    or not isinstance(provenance.get("seed"), int)
                    or provenance.get("topology") != topology
                    or provenance.get("env_id") != env_id
                    or provenance.get("episode_index") != episode_index
                    or provenance.get("episode_id") != episode_id
                    or provenance.get("effort_nm") != effort
                ):
                    raise V23Error(f"{path}.records[{index}] source_provenance identity disagrees")
                step_rows = episode.get("step_rows")
                if not isinstance(step_rows, list) or not step_rows:
                    raise V23Error(f"{path}.records[{index}] must preserve non-empty raw step_rows")
                for step_index, step in enumerate(step_rows):
                    if (
                        not isinstance(step, Mapping)
                        or step.get("schema") != "a2_piper_base_v23_p0_temporal_step_v1"
                        or step.get("effort_nm") != effort
                        or step.get("topology") != topology
                        or step.get("env_id") != env_id
                        or step.get("episode_index") != episode_index
                        or step.get("episode_id") != episode_id
                    ):
                        raise V23Error(f"{path}.records[{index}].step_rows[{step_index}] identity/schema disagrees")
            if set(env_ids) != set(range(16)):
                raise V23Error(f"{path}.records env_id values must cover 0..15 exactly")
            runs.append({"effort_nm": effort, "topology": topology, "source_path": str(path.resolve()), "record_count": len(records)})
            combined_records.extend(dict(record) for record in records)
    return {
        "schema": TEMPORAL_COMBINED_SCHEMA,
        "temporary_label": "A0_CANONICAL16_P0_REFERENCE",
        "registered_rungs_nm": list(V23_EFFORT_RUNGS),
        "topologies": list(CURRENT_SELECTOR_TOPOLOGIES),
        "run_count": len(runs),
        "runs": runs,
        "records": combined_records,
        "selection_authority": "TEMPORAL_REDUCER_REQUIRED",
    }


def analyze_observations_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Reduce one canonical combined raw temporal payload."""

    if not isinstance(payload, Mapping) or payload.get("schema") not in (
        "a2_piper_base_v23_p0_temporal_records_v1",
        TEMPORAL_COMBINED_SCHEMA,
    ):
        raise V23Error("analysis payload must be one registered raw temporal export or canonical combined payload")
    from .effort_ladder import reduce_temporal_ladder

    return reduce_temporal_ladder(payload)


def analyze_observations(paths: Sequence[Path]) -> dict[str, Any]:
    """Aggregate measured rows without choosing the boundary rung."""

    if not paths:
        raise V23Error("ANALYZE requires at least one evaluator observation JSON")
    raw_payloads = [read_json(path) for path in paths]
    if any(
        isinstance(payload, Mapping)
        and (
            payload.get("schema") == "a2_piper_base_v23_p0_temporal_records_v1"
            or payload.get("schema") == TEMPORAL_COMBINED_SCHEMA
            or "raw_temporal_records" in payload
            or "episodes" in payload
        )
        for payload in raw_payloads
    ):
        if len(raw_payloads) != 1:
            raise V23Error("temporal ANALYZE requires one canonical combined raw temporal export")
        return analyze_observations_payload(raw_payloads[0])
    by_effort: dict[float, dict[str, Any]] = {}
    for path, payload in zip(paths, raw_payloads):
        rows = payload.get("rows")
        if not isinstance(rows, list):
            raise V23Error(f"observation input has no rows list: {path}")
        for row in rows:
            if not isinstance(row, Mapping):
                raise V23Error(f"observation row is not an object: {path}")
            effort = _validate_effort_rung(row.get("effort_nm"))
            evidence = row.get("nominal_clipped_tracking")
            if not isinstance(evidence, Mapping):
                raise V23Error(f"observation row {effort} has no nominal_clipped_tracking mapping")
            target = by_effort.setdefault(
                effort,
                {
                    "effort_nm": effort,
                    "status": "OBSERVED",
                    "decision_flags": {
                        "meaningful_clipped_saturation": "PENDING",
                        "e0_not_collapsed": "PENDING",
                        "heavy_door_deteriorates_first": "PENDING",
                        "pd_oscillation_absent": "PENDING",
                    },
                    "nominal_clipped_tracking": {
                        "nominal_pd_torque": "PENDING",
                        "clipped_command_torque": "PENDING",
                        "tracking_error": "PENDING",
                        "authority": "ESTIMATE_ONLY; aggregate=max_over_terminal_envs_and_arm_joints",
                    },
                },
            )
            for field in ("nominal_pd_torque", "clipped_command_torque", "tracking_error"):
                measured = _numeric_observation(evidence.get(field, "PENDING"), name=field)
                current = _numeric_observation(target["nominal_clipped_tracking"][field], name=field)
                if measured is not None:
                    target["nominal_clipped_tracking"][field] = measured if current is None else max(current, measured)
    return {
        "schema": "a2_piper_base_v23_p0_effort_observations_v1",
        "rows": [by_effort[effort] for effort in V23_EFFORT_RUNGS if effort in by_effort],
        "registered_rungs_nm": list(V23_EFFORT_RUNGS),
        "selection_state": "DEFERRED_TO_EFFORT_LADDER",
        "selected_effort_nm": None,
        "prior_use": "historical_v21B_census_is_prior_only",
    }


def _validate_launch_run(run: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one launch without creating output or log files."""

    output_dir = Path(str(run.get("output_dir", "")))
    if output_dir.exists() and any(output_dir.iterdir()):
        raise V23Error(f"refusing to overwrite non-empty runtime output: {output_dir}")
    plain_manifest = run.get("plain_manifest")
    plain_manifest_path = Path(str(run.get("plain_manifest_path", "")))
    if not isinstance(plain_manifest, Mapping):
        raise V23Error("runtime plan run has no plain v23 scenario manifest")
    if not plain_manifest_path.is_absolute() or plain_manifest_path.parent != output_dir:
        raise V23Error("runtime plan plain v23 scenario manifest path must be under output_dir")
    argv = run.get("argv")
    env_spec = run.get("env")
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(item, str) or not item for item in argv)
        or not isinstance(env_spec, Mapping)
    ):
        raise V23Error("runtime plan run has invalid argv/env")
    selected_env = {str(key): str(value) for key, value in env_spec.items()}
    physical_gpu = run.get("physical_gpu", run.get("gpu"))
    if selected_env.get("CUDA_VISIBLE_DEVICES") != str(physical_gpu):
        raise V23Error("runtime plan child must expose its assigned physical GPU explicitly")
    if selected_env.get("ACCELERATE_TORCH_DEVICE") != "cuda:0":
        raise V23Error("runtime plan child accelerator device must be logical cuda:0")
    if any(token.startswith("cuda:") and token != "cuda:0" for token in argv):
        raise V23Error("runtime plan argv must use logical cuda:0, never a physical cuda:N override")
    return {
        "run": run,
        "output_dir": output_dir,
        "plain_manifest_path": plain_manifest_path,
        "argv": argv,
        "env_spec": selected_env,
        "physical_gpu": physical_gpu,
    }


def _preflight_plan_runs(runs: Sequence[Mapping[str, Any]]) -> None:
    """Validate every registered output collision before any wave side effect."""

    seen_output_dirs: set[Path] = set()
    for run in runs:
        item = _validate_launch_run(run)
        output_dir = item["output_dir"]
        if output_dir in seen_output_dirs:
            raise V23Error(f"runtime plan contains duplicate output directory: {output_dir}")
        seen_output_dirs.add(output_dir)


def _prepare_wave_runs(wave_runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and materialize one wave after whole-plan preflight."""

    prepared = [_validate_launch_run(run) for run in wave_runs]

    try:
        for item in prepared:
            item["output_dir"].mkdir(parents=True, exist_ok=True)
            item["plain_manifest_path"].write_text(
                json.dumps(
                    dict(item["run"]["plain_manifest"]),
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )
            item["stdout_path"] = item["output_dir"] / "runtime_stdout.log"
            item["stderr_path"] = item["output_dir"] / "runtime_stderr.log"
            item["stdout"] = item["stdout_path"].open("x", encoding="utf-8")
            item["stderr"] = item["stderr_path"].open("x", encoding="utf-8")
    except BaseException:
        close_error = _close_wave_handles(prepared)
        if close_error is not None and sys.exc_info()[0] is None:
            raise close_error
        raise
    return prepared


def _write_runtime_process_receipt(
    item: Mapping[str, Any],
    *,
    pid: int,
    returncode: int | None,
    producer_state: str,
    spawn_error: str | None = None,
) -> dict[str, Any]:
    run = item["run"]
    receipt = {
        "schema": "a2_piper_base_v23_p0_runtime_process_receipt_v1",
        "producer_state": producer_state,
        "effort_nm": run.get("effort_nm"),
        "topology": run.get("topology"),
        "wave_index": run.get("wave_index"),
        "wave_slot": run.get("wave_slot"),
        "physical_gpu": item["physical_gpu"],
        "logical_device": "cuda:0",
        "argv": list(item["argv"]),
        "env": dict(sorted(item["env_spec"].items())),
        "pid": pid,
        "returncode": returncode,
        "natural_exit": producer_state == "PROCESS_COMPLETED" and returncode == 0,
        "stdout_path": str(item["stdout_path"]),
        "stderr_path": str(item["stderr_path"]),
    }
    if spawn_error is not None:
        receipt["spawn_error"] = spawn_error
    receipt_path = item["output_dir"] / "process_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def _close_wave_handles(prepared: Sequence[Mapping[str, Any]]) -> BaseException | None:
    """Close every opened wave handle while preserving the first close error."""

    first_error: BaseException | None = None
    for item in prepared:
        for key in ("stdout", "stderr"):
            handle = item.get(key)
            if handle is None or handle.closed:
                continue
            try:
                handle.flush()
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
            try:
                handle.close()
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
    return first_error


def _cleanup_spawned_children(live: Sequence[Mapping[str, Any]]) -> None:
    """Terminate still-running children, reap every child, and never mask the original error."""

    for live_item in live:
        if live_item.get("waited"):
            continue
        process = live_item["process"]
        try:
            if process.poll() is None:
                process.terminate()
        except BaseException:
            pass
    for live_item in live:
        if live_item.get("waited"):
            continue
        process = live_item["process"]
        try:
            process.wait()
        except BaseException:
            pass


def _run_wave(wave_runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Spawn one wave concurrently, then wait for every child at the barrier."""

    if not wave_runs or len(wave_runs) > len(V23_LEGAL_PHYSICAL_GPUS):
        raise V23Error("runtime wave must contain between one and four children")
    prepared = _prepare_wave_runs(wave_runs)
    live: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    try:
        for item in prepared:
            process_env = os.environ.copy()
            process_env.update(item["env_spec"])
            process = subprocess.Popen(
                list(item["argv"]),
                cwd=REPO_ROOT,
                env=process_env,
                stdout=item["stdout"],
                stderr=item["stderr"],
            )
            live.append({"item": item, "process": process, "waited": False})

        for live_item in live:
            item = live_item["item"]
            process = live_item["process"]
            raw_returncode = process.wait()
            live_item["waited"] = True
            returncode = int(raw_returncode)
            receipts.append(
                _write_runtime_process_receipt(
                    item,
                    pid=int(process.pid),
                    returncode=returncode,
                    producer_state="PROCESS_COMPLETED",
                )
            )
        receipts.sort(key=lambda receipt: int(receipt.get("wave_slot", 0)))
        return receipts
    except BaseException:
        _cleanup_spawned_children(live)
        raise
    finally:
        close_error = _close_wave_handles(prepared)
        if close_error is not None and sys.exc_info()[0] is None:
            raise close_error


def _run_plan(plan: Mapping[str, Any], *, execute: bool) -> dict[str, Any]:
    if not execute:
        return {**dict(plan), "execution_state": "NOT_EXECUTED_EXPLICIT_EXECUTE_REQUIRED"}
    runs = plan.get("runs")
    if not isinstance(runs, list) or not runs:
        raise V23Error("runtime plan has no runs")
    if any(not isinstance(run, Mapping) for run in runs):
        raise V23Error("runtime plan contains a malformed run")
    _preflight_plan_runs(runs)
    waves: dict[int, list[Mapping[str, Any]]] = {}
    for run in runs:
        if not isinstance(run, Mapping):
            raise V23Error("runtime plan contains a malformed run")
        wave_index = run.get("wave_index")
        if isinstance(wave_index, bool) or not isinstance(wave_index, int) or wave_index < 1:
            raise V23Error("runtime plan run has an invalid wave_index")
        waves.setdefault(wave_index, []).append(run)
    completed: list[dict[str, Any]] = []
    process_receipts: list[dict[str, Any]] = []
    for wave_index in sorted(waves):
        wave_runs = sorted(waves[wave_index], key=lambda run: int(run.get("wave_slot", 0)))
        receipts = _run_wave(wave_runs)
        process_receipts.extend(receipts)
        failures = [receipt for receipt in receipts if not receipt["natural_exit"]]
        if failures:
            details = "; ".join(
                f"{receipt['topology']}@{receipt['effort_nm']} returncode={receipt['returncode']} "
                f"stdout={receipt['stdout_path']} stderr={receipt['stderr_path']}"
                for receipt in failures
            )
            raise V23Error(
                f"runtime wave {wave_index} failed; later waves were not started; no retry: {details}"
            )
        completed.extend(
            {
                "effort_nm": receipt["effort_nm"],
                "topology": receipt["topology"],
                "wave_index": receipt["wave_index"],
                "physical_gpu": receipt["physical_gpu"],
                "returncode": receipt["returncode"],
                "stdout_path": receipt["stdout_path"],
                "stderr_path": receipt["stderr_path"],
            }
            for receipt in receipts
        )
    return {
        **dict(plan),
        "execution_state": "COMPLETED",
        "completed": completed,
        "process_receipts": process_receipts,
        "completed_wave_count": len(waves),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("BUILD", "RUN", "ANALYZE"), required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--effort-nm", type=float, action="append", default=None)
    parser.add_argument("--topology", choices=("canonical16", "heavy16", "both"), default="both")
    parser.add_argument("--output-root", type=Path, default=P0_OUTPUT_ROOT / "torque")
    parser.add_argument("--observations", type=Path, action="append", default=None)
    parser.add_argument("--temporal-combined", type=Path, default=None)
    temporal_arg_names: dict[tuple[float, str], str] = {}
    for effort in V23_EFFORT_RUNGS:
        for topology in CURRENT_SELECTOR_TOPOLOGIES:
            name = f"--temporal-{int(effort)}-{topology}"
            dest = f"temporal_{int(effort)}_{topology}"
            temporal_arg_names[(effort, topology)] = dest
            parser.add_argument(name, dest=dest, type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    if args.mode == "ANALYZE":
        named = {
            key: getattr(args, dest)
            for key, dest in temporal_arg_names.items()
            if getattr(args, dest) is not None
        }
        if args.temporal_combined is not None and named:
            raise V23Error("--temporal-combined cannot be combined with named raw temporal paths")
        if named:
            if args.observations:
                raise V23Error("named raw temporal paths cannot be combined with --observations")
            combined = combine_temporal_runs(named)
            payload = analyze_observations_payload(combined)
        elif args.temporal_combined is not None:
            payload = analyze_observations([args.temporal_combined])
        else:
            payload = analyze_observations(args.observations or [])
    else:
        efforts = args.effort_nm or list(V23_EFFORT_RUNGS)
        topologies = CURRENT_SELECTOR_TOPOLOGIES if args.topology == "both" else (args.topology,)
        plan = build_runtime_plan(efforts=efforts, topologies=topologies, output_root=args.output_root)
        payload = _run_plan(plan, execute=args.execute) if args.mode == "RUN" else plan
    emit_payload(payload, args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 P0 RUNTIME EVAL FAIL: {exc}")
