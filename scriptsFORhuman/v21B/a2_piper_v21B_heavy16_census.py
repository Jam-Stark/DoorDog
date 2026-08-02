"""Deterministic heavy16 manifest and unclipped arm-effort census."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

import torch

from gr00t.rl.envs.door.a2_v21b_evidence import V21B_AUTHORITY_LABEL, a2_v21b_census_from_unclipped

from ._v21b_common import V21BError, canonical_json_bytes, hydra_string_value, sha256_file, write_json
from .a2_piper_v21B_adaptation import validate_materialized_config_receipt
from .a2_piper_v21B_probe_runner import observed_git_identity, read_process_receipt
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact


def _scenario_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        float(row["handle_height_m"]) if row.get("handle_height_m") is not None else float("inf"),
        float(row["door_weight_kg"]),
        float(row["hinge_force_nm"]),
        str(row["scenario_id"]),
    )


def _scenario_digest(row: Mapping[str, Any]) -> str:
    """Hash only immutable scenario identity fields, never insertion order."""

    body = {
        "scenario_id": row.get("scenario_id"),
        "door_weight_kg": row.get("door_weight_kg"),
        "hinge_force_nm": row.get("hinge_force_nm"),
        "handle_height_m": row.get("handle_height_m"),
        "source": row.get("source"),
    }
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _digest(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise V21BError(f"{label} must be a lowercase sha256 digest")
    return value


def validate_heavy16_manifest(
    path: Path,
    *,
    expected_manifest_sha256: str | None = None,
    expected_phase: str | None = None,
    expected_source_checkpoint_sha256: str | None = None,
    expected_source_lock_sha256: str | None = None,
    expected_source_config_sha256: str | None = None,
    expected_materialization_sha256: str | None = None,
    expected_materialized_config_sha256: str | None = None,
) -> dict[str, Any]:
    """Load and verify the exact immutable 16+16 scenario manifest file."""

    target = Path(path)
    if not target.is_file() or target.is_symlink():
        raise V21BError(f"scenario manifest must be a regular non-symlink file: {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V21BError(f"scenario manifest is not valid JSON: {target}") from exc
    validate_artifact(payload, expected_schema=schema("heavy_manifest"))
    canonical_rows = payload.get("canonical_manifest_rows")
    heavy_rows = payload.get("manifest_rows")
    if not isinstance(canonical_rows, list) or len(canonical_rows) != 32:
        raise V21BError("scenario manifest requires exactly 16 canonical/light and 16 heavy rows")
    if not isinstance(heavy_rows, list) or len(heavy_rows) != 16:
        raise V21BError("scenario manifest requires exactly 16 heavy rows")
    ids = [row.get("scenario_id") if isinstance(row, Mapping) else None for row in canonical_rows]
    heavy_ids = [row.get("scenario_id") if isinstance(row, Mapping) else None for row in heavy_rows]
    if any(not isinstance(value, str) or not value for value in ids + heavy_ids) or len(set(ids)) != 32 or len(set(heavy_ids)) != 16:
        raise V21BError("scenario manifest scenario ids must be unique non-empty strings")
    if not set(heavy_ids) <= set(ids):
        raise V21BError("heavy16 rows must be a subset of canonical rows")
    if len(set(ids) - set(heavy_ids)) != 16:
        raise V21BError("scenario manifest must contain exactly 16 light rows")
    if hashlib.sha256(canonical_json_bytes(heavy_rows)).hexdigest() != payload.get("manifest_sha256"):
        raise V21BError("scenario manifest heavy-row hash is invalid")
    if payload.get("heavy_manifest_sha256") != payload.get("manifest_sha256"):
        raise V21BError("scenario manifest heavy hash alias is invalid")
    if hashlib.sha256(canonical_json_bytes(canonical_rows)).hexdigest() != payload.get("canonical_manifest_sha256"):
        raise V21BError("scenario manifest canonical-row hash is invalid")
    row_hashes: set[str] = set()
    canonical_by_id = {row["scenario_id"]: row for row in canonical_rows}
    for row in canonical_rows:
        if not isinstance(row, Mapping):
            raise V21BError("scenario manifest rows must be mappings")
        for key in ("scenario_id", "door_weight_kg", "hinge_force_nm", "handle_height_m", "source", "scenario_sha256"):
            if key not in row:
                raise V21BError(f"scenario manifest row requires {key}")
        try:
            values = (float(row["door_weight_kg"]), float(row["hinge_force_nm"]), float(row["handle_height_m"]))
        except (TypeError, ValueError) as exc:
            raise V21BError("scenario manifest row values must be numeric") from exc
        if any(not math.isfinite(value) or value <= 0.0 for value in values):
            raise V21BError("scenario manifest row values must be finite and positive")
        expected_row_hash = _scenario_digest(row)
        if row.get("scenario_sha256") != expected_row_hash:
            raise V21BError(f"scenario manifest row hash mismatch for {row['scenario_id']}")
        row_hashes.add(expected_row_hash)
    if len(row_hashes) != 32:
        raise V21BError("scenario manifest row hashes must be deterministic and unique")
    for row in heavy_rows:
        if canonical_by_id[row["scenario_id"]].get("scenario_sha256") != row.get("scenario_sha256"):
            raise V21BError("heavy16 row is not byte-bound to its canonical row")
        if float(row["door_weight_kg"]) < 140.0 and float(row["hinge_force_nm"]) < 10.0:
            raise V21BError("heavy16 row fails the pre-registered weight/hinge eligibility rule")
    for row in canonical_rows:
        if row["scenario_id"] not in set(heavy_ids) and (float(row["door_weight_kg"]) >= 140.0 or float(row["hinge_force_nm"]) >= 10.0):
            raise V21BError("canonical light row satisfies the heavy eligibility rule")
    for key in ("manifest_sha256", "canonical_manifest_sha256", "source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256"):
        _digest(payload.get(key), label=f"scenario manifest {key}")
    if expected_manifest_sha256 is not None and payload["manifest_sha256"] != expected_manifest_sha256:
        raise V21BError("scenario manifest hash is not bound to the plan")
    if expected_phase is not None and payload.get("materialization_phase") != expected_phase:
        raise V21BError("scenario manifest materialization phase is not bound")
    for key, expected in (("source_checkpoint_sha256", expected_source_checkpoint_sha256), ("source_lock_sha256", expected_source_lock_sha256), ("source_config_sha256", expected_source_config_sha256), ("materialization_sha256", expected_materialization_sha256), ("materialized_config_sha256", expected_materialized_config_sha256)):
        if expected is not None and payload.get(key) != expected:
            raise V21BError(f"scenario manifest {key} is not bound to the parent receipt")
    payload["path"] = str(target.absolute())
    payload["file_sha256"] = sha256_file(target)
    return payload


def build_heavy16_manifest(
    scenarios: Iterable[Mapping[str, Any]],
    *,
    materialization: Mapping[str, Any],
    materialized_config: Path,
    source_checkpoint_sha256: str | None = None,
    source_lock_sha256: str | None = None,
    source_config_sha256: str | None = None,
) -> dict[str, Any]:
    receipt = validate_materialized_config_receipt(materialization, materialized_config, cell="B1", phase="CENSUS_PRE_K")
    if source_checkpoint_sha256 is not None and source_checkpoint_sha256 != materialization.get("source_checkpoint_sha256"):
        raise V21BError("heavy16 manifest source checkpoint override disagrees with the receipt")
    if source_lock_sha256 is not None and source_lock_sha256 != materialization.get("source_lock_sha256"):
        raise V21BError("heavy16 manifest source lock override disagrees with the receipt")
    if source_config_sha256 is not None and source_config_sha256 != receipt["source_config_sha256"]:
        raise V21BError("heavy16 manifest source config override disagrees with the B1 receipt")
    rows = []
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            raise V21BError("heavy16 scenarios must be mappings")
        if "scenario_id" not in scenario or "door_weight_kg" not in scenario or "hinge_force_nm" not in scenario:
            raise V21BError("heavy16 scenario requires scenario_id, door_weight_kg, hinge_force_nm")
        try:
            heavy = float(scenario["door_weight_kg"]) >= 140.0 or float(scenario["hinge_force_nm"]) >= 10.0
        except (TypeError, ValueError) as exc:
            raise V21BError("heavy16 scenario weight/hinge force must be numeric") from exc
        handle_height = scenario.get("handle_height_m")
        if isinstance(handle_height, bool) or not isinstance(handle_height, (int, float)) or not math.isfinite(float(handle_height)) or float(handle_height) <= 0.0:
            raise V21BError("heavy16 scenario handle_height_m must be finite and positive")
        rows.append({"scenario_id": scenario["scenario_id"], "door_weight_kg": float(scenario["door_weight_kg"]), "hinge_force_nm": float(scenario["hinge_force_nm"]), "handle_height_m": float(handle_height), "source": scenario.get("source", "pre_registered_input"), "heavy": heavy})
    rows.sort(key=_scenario_key)
    heavy_rows = [row for row in rows if row["heavy"]]
    if len(rows) != 32 or len(heavy_rows) != 16:
        raise V21BError(f"heavy16 manifest requires exactly 16 eligible scenarios; got {len(heavy_rows)}")
    if len({row["scenario_id"] for row in rows}) != len(rows):
        raise V21BError("heavy16 scenario ids must be unique")
    canonical_rows = [dict(row) for row in rows]
    for row in canonical_rows:
        row.pop("heavy", None)
        row["scenario_sha256"] = _scenario_digest(row)
    heavy_rows = [dict(row) for row in heavy_rows]
    for row in heavy_rows:
        row.pop("heavy", None)
        row["scenario_sha256"] = _scenario_digest(row)
    payload = artifact_payload(
        "heavy_manifest",
        status="STATIC_PASS",
        manifest_rows=heavy_rows,
        canonical_manifest_rows=canonical_rows,
        selection_rule="exactly 16 heavy + 16 canonical light rows; heavy iff door_weight_kg >= 140 OR hinge_force_nm >= 10; deterministic sorted order; right censoring is measured on raw valid heavy frames",
        right_censoring_rule="fraction of raw valid heavy frames with max(abs(unclipped_effort_6d)) >= 100 N*m; episode grouping is only for peak candidate selection",
        manifest_cardinality={"canonical16": 16, "heavy16": 16, "total": 32},
        reused_across_theta=True,
        seed_fishing=False,
        materialization_phase=receipt["phase"],
        materialization_sha256=receipt["materialization_sha256"],
        materialized_config_sha256=receipt["materialized_config_sha256"],
        source_checkpoint_sha256=materialization["source_checkpoint_sha256"],
        source_lock_sha256=materialization["source_lock_sha256"],
        source_config_sha256=receipt["source_config_sha256"],
    )
    payload["manifest_sha256"] = hashlib.sha256(canonical_json_bytes(payload["manifest_rows"])).hexdigest()
    payload["heavy_manifest_sha256"] = payload["manifest_sha256"]
    payload["canonical_manifest_sha256"] = hashlib.sha256(canonical_json_bytes(payload["canonical_manifest_rows"])).hexdigest()
    return validate_artifact(payload, expected_schema=schema("heavy_manifest"))


def write_heavy16_manifest(path: Path, scenarios: Iterable[Mapping[str, Any]], *, materialization: Mapping[str, Any], materialized_config: Path) -> dict[str, Any]:
    payload = build_heavy16_manifest(scenarios, materialization=materialization, materialized_config=materialized_config)
    write_json(path, payload)
    return payload


def build_census_plan(
    repo_root: Path,
    *,
    manifest_path: Path,
    output_root: Path,
    materialization: Mapping[str, Any],
    materialized_config: Path,
    source_checkpoint_sha256: str | None = None,
    source_lock_sha256: str | None = None,
    source_config_sha256: str | None = None,
) -> dict[str, Any]:
    """Create the signed CENSUS_PRE_K canonical16/heavy16 command pair."""

    root = Path(repo_root).resolve()
    receipt = validate_materialized_config_receipt(materialization, materialized_config, cell="B1", phase="CENSUS_PRE_K")
    manifest = validate_heavy16_manifest(
        manifest_path,
        expected_phase="CENSUS_PRE_K",
        expected_source_checkpoint_sha256=materialization.get("source_checkpoint_sha256"),
        expected_source_lock_sha256=materialization.get("source_lock_sha256"),
        expected_source_config_sha256=receipt["source_config_sha256"],
        expected_materialization_sha256=receipt["materialization_sha256"],
        expected_materialized_config_sha256=receipt["materialized_config_sha256"],
    )
    for key, expected in (("source_checkpoint_sha256", source_checkpoint_sha256), ("source_lock_sha256", source_lock_sha256), ("source_config_sha256", source_config_sha256)):
        if expected is not None and manifest[key] != expected:
            raise V21BError(f"census plan {key} disagrees with the signed manifest")
    config = Path(receipt["path"])
    output = Path(output_root).absolute()
    manifest_json = canonical_json_bytes({key: value for key, value in manifest.items() if key not in {"path", "file_sha256"}}).decode("utf-8")
    manifest_content_sha256 = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
    source_bindings = {
        "source_checkpoint_sha256": manifest["source_checkpoint_sha256"],
        "source_lock_sha256": manifest["source_lock_sha256"],
        "source_config_sha256": manifest["source_config_sha256"],
        "materialization_sha256": manifest["materialization_sha256"],
        "materialized_config_sha256": manifest["materialized_config_sha256"],
    }
    git_identity = observed_git_identity(root)
    common = [
        sys.executable, "-m", "gr00t.rl.eval_agent_trl",
        f"--config-dir={config.parent}", f"--config-name={config.stem}",
        "checkpoint=logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G4-20260731_004712/model_step_002500.pt",
        "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true", "num_envs=16", "seed=0",
        "algo.config.eval.num_eval_episodes=16", "+algo.config.eval.eval_num_envs_episodes=true",
        "env.config.a2_v21B_materialization_phase=CENSUS_PRE_K", "env.config.a2_v21B_formal_launch=false",
        "+env.config.a2_v21B_signed_probe_scenarios_enabled=true", "env.config.a2_v21B_cell=B1",
        f"+env.config.a2_v21B_scenario_manifest_path={Path(manifest_path).absolute()}",
        f"+env.config.a2_v21B_scenario_manifest_sha256={manifest['manifest_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_file_sha256={manifest['file_sha256']}",
        f"+env.config.a2_v21B_canonical_manifest_sha256={manifest['canonical_manifest_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_source_checkpoint_sha256={manifest['source_checkpoint_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_source_lock_sha256={manifest['source_lock_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_source_config_sha256={manifest['source_config_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_materialization_sha256={manifest['materialization_sha256']}",
        f"+env.config.a2_v21B_scenario_manifest_json_sha256={manifest_content_sha256}",
        f"+env.config.a2_v21B_scenario_manifest_json={hydra_string_value(manifest_json)}",
        f"+env.config.a2_v21B_materialization_sha256={receipt['materialization_sha256']}",
        f"+env.config.a2_v21B_materialized_config_sha256={receipt['materialized_config_sha256']}",
        f"env.config.a2_v21B_source_checkpoint_sha256={materialization['source_checkpoint_sha256']}",
        f"env.config.a2_v21B_source_lock_sha256={materialization['source_lock_sha256']}",
        f"env.config.a2_v21B_source_config_sha256={receipt['source_config_sha256']}",
    ]
    rows = []
    for topology in ("canonical16", "heavy16"):
        run_uuid = f"v21B-census-{topology}"
        result_path = output / topology / "census_frames.json"
        raw_root = output / topology / "terminal_exports"
        raw_paths = [raw_root / f"B1_{run_uuid}_env{env_id}.json" for env_id in range(16)]
        argv = [*common, f"+env.config.a2_v21B_census_topology={topology}", f"+env.config.a2_v21B_run_uuid={run_uuid}", f"env.config.a2_v21B_terminal_export_root={raw_root}", f"+env.config.a2_v21B_output_root={output / topology}"]
        env = {"CUDA_VISIBLE_DEVICES": "0", "WANDB_MODE": "offline"}
        parent_hashes = {"manifest": manifest["file_sha256"], "materialized_config": receipt["materialized_config_sha256"]}
        result_contract = {
            "kind": "census_frames", "aggregate_path": str(result_path.absolute()), "raw_paths": [str(path.absolute()) for path in raw_paths],
            "topology": topology, "run_uuid": run_uuid, "manifest_content": manifest_json,
            "manifest_content_sha256": manifest_content_sha256,
            "manifest_sha256": manifest["manifest_sha256"], "canonical_manifest_sha256": manifest["canonical_manifest_sha256"],
            "manifest_file_sha256": manifest["file_sha256"], "manifest_materialization_sha256": manifest["materialization_sha256"],
            "source_bindings": source_bindings,
        }
        process_root = output / topology / "process"
        rows.append({"topology": topology, "run_uuid": run_uuid, "argv": argv, "env": env, "manifest_path": str(Path(manifest_path).absolute()), "manifest_sha256": manifest["manifest_sha256"], "canonical_manifest_sha256": manifest["canonical_manifest_sha256"], "manifest_content": manifest_json, "manifest_content_sha256": manifest_content_sha256, "manifest_file_sha256": manifest["file_sha256"], "manifest_materialization_sha256": manifest["materialization_sha256"], "num_envs": 16, "result_paths": [str(result_path.absolute())], "raw_paths": [str(path.absolute()) for path in raw_paths], "process_root": str(process_root.absolute()), "process_receipt_path": str((process_root / "process_receipt.json").absolute()), "result_contract": result_contract, "source_bindings": source_bindings, "parent_hashes": parent_hashes, "repo_commit": git_identity["commit"], "repo_tree": git_identity["tree"], "physical_gpu": 0})
    from .a2_piper_v21B_probe_runner import hash_command_env
    for row in rows:
        row["command_sha256"] = hash_command_env(row["argv"], row["env"])
    payload = artifact_payload(
        "census", status="STATIC_PASS", cell="B1", plan_type="CENSUS_PRE_K", num_envs=16,
        manifest_path=str(Path(manifest_path).absolute()), manifest_sha256=manifest["manifest_sha256"],
        manifest_file_sha256=manifest["file_sha256"], canonical_manifest_sha256=manifest["canonical_manifest_sha256"], manifest_materialization_sha256=manifest["materialization_sha256"], manifest_content_sha256=manifest_content_sha256,
        manifest_content=manifest_json, commands=rows, output_root=str(output), materialization_phase=receipt["phase"],
        materialization_sha256=receipt["materialization_sha256"], materialized_config_sha256=receipt["materialized_config_sha256"],
        source_checkpoint_sha256=materialization["source_checkpoint_sha256"], source_lock_sha256=materialization["source_lock_sha256"], source_config_sha256=receipt["source_config_sha256"], materialized_config_path=str(config), repo_commit=git_identity["commit"], repo_tree=git_identity["tree"],
    )
    payload["plan_sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return validate_artifact(payload, expected_schema=schema("census"), expected_cell="B1")


def run_torque_census(frames: Iterable[Mapping[str, Any]], *, manifest: Mapping[str, Any], candidate_limits_nm: tuple[float, ...] = (40.0, 30.0, 25.0, 20.0)) -> dict[str, Any]:
    validate_artifact(manifest, expected_schema=schema("heavy_manifest"))
    if manifest.get("materialization_phase") != "CENSUS_PRE_K":
        raise V21BError("torque census requires a CENSUS_PRE_K materialization")
    for key in ("materialization_sha256", "materialized_config_sha256", "source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256"):
        value = manifest.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise V21BError(f"torque census manifest lacks a lowercase {key} digest")
    manifest_rows = manifest["manifest_rows"]
    manifest_ids = {row["scenario_id"] for row in manifest_rows}
    canonical_rows = manifest.get("canonical_manifest_rows")
    if not isinstance(canonical_rows, list) or not canonical_rows:
        raise V21BError("census requires an immutable canonical16/light manifest alongside heavy16")
    expected_canonical_hash = hashlib.sha256(canonical_json_bytes(canonical_rows)).hexdigest()
    if expected_canonical_hash != manifest.get("canonical_manifest_sha256"):
        raise V21BError("canonical16/light manifest hash does not match the signed census manifest")
    canonical_ids = {row.get("scenario_id") for row in canonical_rows}
    if not canonical_ids or not manifest_ids <= canonical_ids:
        raise V21BError("heavy16 ids are not a subset of the signed canonical manifest")
    manifest_by_id = {row["scenario_id"]: row for row in canonical_rows}
    heavy_by_id = {row["scenario_id"] for row in manifest_rows}
    episode_rows: dict[tuple[str, str, bool], dict[str, Any]] = {}
    episode_identity_by_id: dict[str, tuple[str, str, bool]] = {}
    seen_topologies: set[str] = set()
    seen_frame_ids: set[str] = set()
    seen_episode_steps: set[tuple[str, int]] = set()
    raw_heavy_valid_frame_count = 0
    raw_right_censored_heavy_frame_count_at_100Nm = 0
    for frame in frames:
        if not isinstance(frame, Mapping) or frame.get("scenario_id") not in canonical_ids:
            raise V21BError("census frame must bind to the signed canonical16/heavy16 manifests")
        frame_id = frame.get("frame_id")
        if not isinstance(frame_id, str) or not frame_id or frame_id in seen_frame_ids:
            raise V21BError("census frames require unique non-empty frame_id values")
        seen_frame_ids.add(frame_id)
        if frame.get("valid") is not True or frame.get("phase") != "CENSUS_PRE_K" or frame.get("materialization_phase") != "CENSUS_PRE_K" or frame.get("authority") != V21B_AUTHORITY_LABEL:
            raise V21BError("census frame validity/phase/authority is not bound to the raw producer contract")
        for key in ("episode_id", "env_id", "step_index", "scenario_id", "topology", "heavy_bucket", "door_weight_kg", "hinge_force_nm"):
            if key not in frame:
                raise V21BError(f"census frame requires {key}")
        if not isinstance(frame["episode_id"], str) or not frame["episode_id"]:
            raise V21BError("census frame episode_id must be a non-empty string")
        if isinstance(frame["env_id"], bool) or not isinstance(frame["env_id"], int) or frame["env_id"] < 0:
            raise V21BError("census frame env_id must be a non-negative integer")
        if isinstance(frame["step_index"], bool) or not isinstance(frame["step_index"], int) or frame["step_index"] < 0:
            raise V21BError("census frame step_index must be a non-negative integer")
        step_key = (frame["episode_id"], frame["step_index"])
        if step_key in seen_episode_steps:
            raise V21BError("census frames contain duplicate episode_id/step_index rows")
        seen_episode_steps.add(step_key)
        for key in ("source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256"):
            if frame.get(key) != manifest.get(key):
                raise V21BError(f"census frame {key} is not bound to the signed manifest")
        for key in ("materialization_sha256", "materialized_config_sha256"):
            if frame.get(key) != manifest.get(key):
                raise V21BError(f"census frame {key} is not bound to the signed manifest")
        topology = frame.get("topology")
        if topology not in ("canonical16", "heavy16"):
            raise V21BError("census frame topology must be canonical16 or heavy16")
        scenario_is_heavy = frame["scenario_id"] in manifest_ids
        if (topology == "heavy16") != scenario_is_heavy:
            raise V21BError("census frame topology disagrees with the immutable heavy16 membership")
        if frame.get("heavy_bucket") is not (topology == "heavy16"):
            raise V21BError("census frame heavy_bucket does not match its topology")
        scenario = manifest_by_id.get(frame["scenario_id"])
        if not isinstance(scenario, Mapping):
            raise V21BError("census frame scenario is absent from the signed canonical manifest")
        try:
            weight = float(frame["door_weight_kg"])
            hinge = float(frame["hinge_force_nm"])
        except (TypeError, ValueError) as exc:
            raise V21BError("census frame door weight/hinge force must be numeric") from exc
        if not math.isfinite(weight) or not math.isfinite(hinge) or weight <= 0.0 or hinge <= 0.0:
            raise V21BError("census frame door weight/hinge force must be finite and positive")
        if weight != float(scenario["door_weight_kg"]) or hinge != float(scenario["hinge_force_nm"]):
            raise V21BError("census frame runtime scenario identity does not match the signed manifest")
        expected_heavy = frame["scenario_id"] in heavy_by_id
        if expected_heavy != (topology == "heavy16") or bool(frame["heavy_bucket"]) != expected_heavy:
            raise V21BError("census frame heavy bucket disagrees with the signed manifest membership")
        seen_topologies.add(topology)
        raw = frame.get("arm_pd_effort_estimate_unclipped_6d")
        if not isinstance(raw, list) or len(raw) != 6:
            raise V21BError("census frame requires six unclipped arm effort estimates")
        parsed = [float(item) for item in raw]
        if any(not math.isfinite(item) for item in parsed):
            raise V21BError("census frame unclipped effort must be finite")
        if scenario_is_heavy:
            raw_heavy_valid_frame_count += 1
            if max(abs(item) for item in parsed) >= 100.0:
                raw_right_censored_heavy_frame_count_at_100Nm += 1
        episode_key = (frame["episode_id"], topology, bool(frame["heavy_bucket"]))
        prior_key = episode_identity_by_id.get(frame["episode_id"])
        if prior_key is not None and prior_key != episode_key:
            raise V21BError("census episode_id is reused across topology or heavy-bucket identities")
        episode_identity_by_id[frame["episode_id"]] = episode_key
        existing = episode_rows.get(episode_key)
        identity = (frame["scenario_id"], weight, hinge, frame["source_checkpoint_sha256"], frame["source_lock_sha256"], frame["source_config_sha256"], frame["materialization_sha256"], frame["materialized_config_sha256"])
        if existing is None:
            episode_rows[episode_key] = {"identity": identity, "peak": parsed, "frame_count": 1}
        else:
            if existing["identity"] != identity:
                raise V21BError("census episode mixes scenario identity, topology bucket, or provenance")
            existing["peak"] = [max(abs(a), abs(b)) for a, b in zip(existing["peak"], parsed)]
            existing["frame_count"] += 1
    if not episode_rows:
        raise V21BError("torque census requires canonical16/light and heavy16 frames")
    if seen_topologies != {"canonical16", "heavy16"}:
        raise V21BError("torque census requires both canonical16/light and heavy16 telemetry")
    values = [row["peak"] for row in episode_rows.values()]
    heavy_flags = [bool(row["identity"][0] in heavy_by_id) for row in episode_rows.values()]
    efforts = torch.tensor(values, dtype=torch.float32)
    heavy = torch.tensor(heavy_flags, dtype=torch.bool)
    result = a2_v21b_census_from_unclipped(
        efforts,
        heavy,
        candidate_limits_nm=candidate_limits_nm,
        raw_heavy_valid_frame_count=raw_heavy_valid_frame_count,
        right_censored_heavy_frame_count_at_100Nm=raw_right_censored_heavy_frame_count_at_100Nm,
    )
    if result.get("heavy_episode_count") != int(heavy.sum().item()) or result.get("light_episode_count") != int((~heavy).sum().item()):
        raise V21BError("census episode counts are inconsistent with the grouped candidate input")
    result["episode_count"] = len(episode_rows)
    result["episode_frame_counts"] = {key[0]: row["frame_count"] for key, row in episode_rows.items()}
    result.update({
        "schema": schema("census"),
        "plan_id": manifest["plan_id"],
        "execution_id": manifest["execution_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "authority": "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE",
        "census_basis": "arm_pd_effort_estimate_unclipped",
        "materialization_phase": manifest["materialization_phase"],
        "materialization_sha256": manifest["materialization_sha256"],
        "materialized_config_sha256": manifest["materialized_config_sha256"],
    })
    for key in ("source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256"):
        if key in manifest:
            result[key] = manifest[key]
    return validate_artifact(result, expected_schema=schema("census"))


def run_torque_census_from_receipts(
    *,
    plan: Mapping[str, Any],
    manifest_path: Path,
    process_receipt_paths: Mapping[str, Path],
    result_paths: Mapping[str, Path],
    candidate_limits_nm: tuple[float, ...] = (40.0, 30.0, 25.0, 20.0),
) -> dict[str, Any]:
    """Adjudicate only exported frame files bound to completed producer receipts."""

    validate_artifact(plan, expected_schema=schema("census"), expected_cell="B1")
    unsigned = dict(plan)
    unsigned.pop("plan_sha256", None)
    if plan.get("status") != "STATIC_PASS" or plan.get("plan_sha256") != hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest():
        raise V21BError("census plan digest/status is invalid")
    if set(process_receipt_paths) != {"canonical16", "heavy16"} or set(result_paths) != {"canonical16", "heavy16"}:
        raise V21BError("census adjudication requires exactly canonical16/heavy16 receipt and result paths")
    manifest = validate_heavy16_manifest(
        manifest_path,
        expected_manifest_sha256=plan.get("manifest_sha256"),
        expected_phase="CENSUS_PRE_K",
        expected_source_checkpoint_sha256=plan.get("source_checkpoint_sha256"),
        expected_source_lock_sha256=plan.get("source_lock_sha256"),
        expected_source_config_sha256=plan.get("source_config_sha256"),
        expected_materialization_sha256=plan.get("materialization_sha256"),
        expected_materialized_config_sha256=plan.get("materialized_config_sha256"),
    )
    frames: list[Mapping[str, Any]] = []
    receipt_hashes: dict[str, str] = {}
    for row in plan["commands"]:
        topology = row.get("topology")
        if topology not in ("canonical16", "heavy16"):
            raise V21BError("census plan command topology is invalid")
        receipt_path = Path(process_receipt_paths[topology])
        result_path = Path(result_paths[topology])
        receipt = read_process_receipt(
            receipt_path,
            repo_root=Path(__file__).resolve().parents[2],
            expected_command_sha256=row["command_sha256"],
            expected_env=row["env"],
            expected_result_paths=(result_path,),
            expected_parent_hashes=row.get("parent_hashes"),
            expected_source_bindings=row.get("source_bindings"),
            expected_plan_sha256=plan["plan_sha256"],
            expected_git_commit=plan.get("repo_commit"),
            expected_git_tree=plan.get("repo_tree"),
            expected_physical_gpu=row.get("physical_gpu"),
            expected_result_contract=row.get("result_contract"),
            require_natural_exit=True,
        )
        if receipt.get("plan_sha256") != plan["plan_sha256"]:
            raise V21BError("census process receipt is not bound to this plan")
        receipt_hashes[topology] = sha256_file(receipt_path)
        try:
            value = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise V21BError(f"census result is not valid JSON: {result_path}") from exc
        if isinstance(value, Mapping):
            if value.get("schema") != "a2_piper_base_v21B_census_frame_export_aggregate_v1" or value.get("producer_state") != "AGGREGATED_AFTER_CHILD_EXIT":
                raise V21BError("census result must be the runner-produced aggregate schema")
            if value.get("plan_sha256") != plan["plan_sha256"] or value.get("topology") != topology or value.get("run_uuid") != row.get("run_uuid"):
                raise V21BError("census aggregate is not bound to the producer plan")
            if value.get("manifest_sha256") != plan["manifest_sha256"] or value.get("canonical_manifest_sha256") != plan["canonical_manifest_sha256"]:
                raise V21BError("census aggregate manifest binding is invalid")
            value = value.get("frames")
        if not isinstance(value, list) or not value:
            raise V21BError("census result must be a non-empty exported frame list")
        for frame in value:
            if not isinstance(frame, Mapping) or frame.get("topology") != topology:
                raise V21BError("census frame result topology is not bound to its producer command")
        frames.extend(value)
    result = run_torque_census(frames, manifest=manifest, candidate_limits_nm=candidate_limits_nm)
    result.update({"plan_sha256": plan["plan_sha256"], "manifest_file_sha256": manifest["file_sha256"], "process_receipt_sha256": receipt_hashes})
    return validate_artifact(result, expected_schema=schema("census"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--frames", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    frames = json.loads(args.frames.read_text(encoding="utf-8"))
    print(json.dumps(run_torque_census(frames, manifest=manifest), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


build_heavy16 = build_heavy16_manifest
census_arm_effort = run_torque_census
load_heavy16_manifest = validate_heavy16_manifest
build_census_execution_plan = build_census_plan
adjudicate_census = run_torque_census_from_receipts

__all__ = ["build_heavy16_manifest", "build_heavy16", "write_heavy16_manifest", "validate_heavy16_manifest", "load_heavy16_manifest", "build_census_plan", "build_census_execution_plan", "run_torque_census", "run_torque_census_from_receipts", "adjudicate_census", "census_arm_effort"]
