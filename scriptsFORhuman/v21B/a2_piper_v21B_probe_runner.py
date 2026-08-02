"""One-shot process execution and immutable receipts for v21-B probes.

The runner is intentionally small and strict.  A consumed attempt is terminal:
spawn failures and non-zero children still produce a receipt and are never
retried.  Result files are admitted only when the child has actually exited.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._v21b_common import V21BError, canonical_json_bytes, sha256_file, write_json


PROCESS_RECEIPT_SCHEMA = "a2_piper_base_v21B_process_receipt_v1"
ATTEMPT_SCHEMA = "a2_piper_base_v21B_attempt_marker_v1"
COMPLETION_SEAL_SCHEMA = "a2_piper_base_v21B_process_completion_seal_v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def hash_command_env(argv: Sequence[str], env: Mapping[str, str]) -> str:
    if not isinstance(argv, Sequence) or isinstance(argv, (str, bytes)) or not argv:
        raise V21BError("v21-B process argv must be a non-empty sequence")
    if any(not isinstance(item, str) or not item for item in argv):
        raise V21BError("v21-B process argv entries must be non-empty strings")
    if not isinstance(env, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
        raise V21BError("v21-B process env must map strings to strings")
    return _digest({"argv": list(argv), "env": dict(sorted(env.items()))})


def _regular_file(path: Path, *, label: str) -> Path:
    target = Path(path)
    if not target.is_file() or target.is_symlink():
        raise V21BError(f"{label} must be a regular non-symlink file: {target}")
    return target


def _git_value(repo_root: Path, expression: str) -> str:
    try:
        value = subprocess.check_output(["git", "rev-parse", expression], cwd=repo_root, text=True, stderr=subprocess.PIPE).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise V21BError(f"cannot bind v21-B process receipt to git {expression}") from exc
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise V21BError(f"git {expression} is not a lowercase object id: {value!r}")
    return value


def observed_git_identity(repo_root: Path) -> dict[str, str]:
    root = Path(repo_root).absolute()
    return {"commit": _git_value(root, "HEAD"), "tree": _git_value(root, "HEAD^{tree}")}


def _identity(path: Path, *, label: str) -> dict[str, Any]:
    target = _regular_file(Path(path).absolute(), label=label)
    return {"path": str(target), "sha256": sha256_file(target), "size": target.stat().st_size}


def _process_identity(pid: int) -> dict[str, Any]:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise V21BError(f"invalid process id: {pid!r}")
    proc = Path(f"/proc/{pid}/stat")
    start_ticks: int | None = None
    parent_pid: int | None = None
    if proc.is_file() and not proc.is_symlink():
        fields = proc.read_text(encoding="utf-8").split()
        if len(fields) >= 22:
            parent_pid = int(fields[3])
            start_ticks = int(fields[21])
    return {"pid": pid, "ppid": parent_pid, "starttime_ticks": start_ticks}


def _validate_parent_paths(parents: Mapping[str, Path] | None) -> dict[str, str]:
    if parents is None:
        return {}
    if not isinstance(parents, Mapping):
        raise V21BError("v21-B process parents must be a mapping")
    result: dict[str, str] = {}
    for name, path in sorted(parents.items()):
        if not isinstance(name, str) or not name:
            raise V21BError("v21-B process parent names must be non-empty strings")
        result[name] = _identity(Path(path), label=f"parent {name}")["sha256"]
    return result


def _result_identities(paths: Sequence[Path]) -> list[dict[str, Any]]:
    identities: list[dict[str, Any]] = []
    for path in paths:
        identities.append(_identity(path, label="expected result"))
    return identities


def _contract_output_paths(contract: Mapping[str, Any]) -> tuple[Path, ...]:
    """Return producer-owned raw outputs whose identities must stay bound."""

    kind = contract.get("kind")
    if kind in ("census_frames", "zero_shot_terminal_records"):
        raw_paths = contract.get("raw_paths")
        if not isinstance(raw_paths, list):
            raise V21BError("v21-B result contract raw_paths are missing")
        return tuple(Path(item).absolute() for item in raw_paths)
    if kind == "pilot_metrics":
        raw_metrics_path = contract.get("raw_metrics_path")
        checkpoint_paths = contract.get("checkpoint_paths")
        if not isinstance(raw_metrics_path, str) or not isinstance(checkpoint_paths, list):
            raise V21BError("v21-B pilot result contract raw outputs are incomplete")
        return (Path(raw_metrics_path).absolute(), *(Path(item).absolute() for item in checkpoint_paths))
    if kind == "smoke_evidence":
        raw_metrics_path = contract.get("raw_metrics_path")
        checkpoint_path = contract.get("checkpoint_path")
        if not all(isinstance(item, str) and item for item in (raw_metrics_path, checkpoint_path)):
            raise V21BError("v21-B smoke result contract raw outputs are incomplete")
        return tuple(Path(item).absolute() for item in (raw_metrics_path, checkpoint_path))
    raise V21BError(f"unsupported v21-B result contract kind: {kind!r}")


def _write_json_exclusive_atomic(path: Path, value: Any) -> None:
    """Atomically publish a producer aggregate without allowing overwrite."""

    target = Path(path).absolute()
    if target.exists() or target.is_symlink():
        raise V21BError(f"v21-B aggregate result already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise V21BError(f"v21-B aggregate temporary path already exists: {temporary}")
    payload = canonical_json_bytes(value) + b"\n"
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # hard-link publication is atomic and fails instead of replacing a
        # concurrently-created destination.
        os.link(temporary, target)
    except FileExistsError as exc:
        raise V21BError(f"v21-B aggregate result publication collided: {target}") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_completion_seal(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    """Publish a no-overwrite seal for the already-written receipt.

    The receipt is immutable and names this sibling path.  The seal is written
    afterward and binds the final receipt identity plus all outcome identities,
    avoiding a circular receipt/seal hash.
    """

    unsigned = dict(value)
    unsigned.pop("seal_sha256", None)
    seal = dict(unsigned)
    seal["seal_sha256"] = _digest(unsigned)
    _write_json_exclusive_atomic(Path(path), seal)
    return seal


def _digest_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise V21BError(f"{label} must be a lowercase sha256 digest")
    return value


def _validate_materialization_identity(phase: Any, adaptation: Any, *, label: str) -> None:
    if phase not in ("POST_CENSUS", "FORMAL_PROMOTED"):
        raise V21BError(f"{label} materialization phase is invalid")
    if phase == "POST_CENSUS":
        if adaptation is not None:
            raise V21BError(f"{label} POST_CENSUS adaptation identity must be null")
    elif not isinstance(adaptation, str) or len(adaptation) != 64 or any(char not in "0123456789abcdef" for char in adaptation):
        raise V21BError(f"{label} FORMAL_PROMOTED adaptation identity must be a lowercase sha256 digest")


def _read_json(path: Path, *, label: str) -> Any:
    target = _regular_file(Path(path).absolute(), label=label)
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V21BError(f"{label} is not valid JSON: {target}") from exc


def _manifest_rows_from_contract(contract: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    manifest_json = contract.get("manifest_content")
    if not isinstance(manifest_json, str) or not manifest_json:
        raise V21BError("v21-B result contract requires the full signed manifest content")
    try:
        manifest = json.loads(manifest_json)
    except json.JSONDecodeError as exc:
        raise V21BError("v21-B result contract manifest content is not JSON") from exc
    if not isinstance(manifest, Mapping):
        raise V21BError("v21-B result contract manifest content must be a mapping")
    canonical = manifest.get("canonical_manifest_rows")
    heavy = manifest.get("manifest_rows")
    if not isinstance(canonical, list) or len(canonical) != 32 or not isinstance(heavy, list) or len(heavy) != 16:
        raise V21BError("v21-B result contract requires exact 32 canonical/16 heavy manifest rows")
    canonical_by_id = {row.get("scenario_id"): dict(row) for row in canonical if isinstance(row, Mapping)}
    heavy_by_id = {row.get("scenario_id"): dict(row) for row in heavy if isinstance(row, Mapping)}
    if len(canonical_by_id) != 32 or len(heavy_by_id) != 16 or not set(heavy_by_id) <= set(canonical_by_id):
        raise V21BError("v21-B result contract manifest ids are not exact")
    for key in ("manifest_sha256", "canonical_manifest_sha256", "manifest_file_sha256", "manifest_content_sha256"):
        _digest_string(contract.get(key), label=f"v21-B manifest {key}")
    if contract.get("manifest_sha256") != manifest.get("manifest_sha256") or contract.get("canonical_manifest_sha256") != manifest.get("canonical_manifest_sha256"):
        raise V21BError("v21-B result contract manifest hashes disagree with its content")
    if contract.get("manifest_content_sha256") != _digest_string(hashlib.sha256(manifest_json.encode("utf-8")).hexdigest(), label="v21-B manifest content"):
        raise V21BError("v21-B result contract manifest content hash disagrees with its content")
    bindings = contract.get("source_bindings")
    required_bindings = ("source_checkpoint_sha256", "source_lock_sha256", "source_config_sha256", "materialization_sha256", "materialized_config_sha256")
    if not isinstance(bindings, Mapping) or any(key not in bindings for key in required_bindings):
        raise V21BError("v21-B result contract source bindings are incomplete")
    for key in required_bindings:
        _digest_string(bindings[key], label=f"v21-B source binding {key}")
    return dict(manifest), canonical_by_id, heavy_by_id


def _validate_common_provenance(row: Mapping[str, Any], contract: Mapping[str, Any], *, label: str) -> None:
    expected = contract.get("source_bindings")
    if not isinstance(expected, Mapping):
        raise V21BError(f"{label} result contract source_bindings are missing")
    for key, value in expected.items():
        if row.get(key) != value:
            raise V21BError(f"{label} producer output {key} is not bound to the signed contract")


def _collect_census_result(contract: Mapping[str, Any], *, plan_sha256: str | None) -> dict[str, Any]:
    topology = contract.get("topology")
    run_uuid = contract.get("run_uuid")
    if topology not in ("canonical16", "heavy16") or not isinstance(run_uuid, str) or not run_uuid:
        raise V21BError("census result contract topology/run_uuid is invalid")
    manifest, canonical_by_id, heavy_by_id = _manifest_rows_from_contract(contract)
    raw_paths = contract.get("raw_paths")
    if not isinstance(raw_paths, list) or len(raw_paths) != 16:
        raise V21BError("census result contract requires exactly 16 per-env raw paths")
    expected_ids = list(heavy_by_id) if topology == "heavy16" else [item for item in manifest["canonical_manifest_rows"] if item["scenario_id"] not in heavy_by_id]
    expected_ids = [item["scenario_id"] if isinstance(item, Mapping) else item for item in expected_ids]
    if len(expected_ids) != 16:
        raise V21BError("census result contract topology does not contain exactly 16 scenarios")
    frames: list[dict[str, Any]] = []
    raw_identities: list[dict[str, Any]] = []
    seen_frame_ids: set[str] = set()
    for env_id, path_value in enumerate(raw_paths):
        path = _regular_file(Path(path_value).absolute(), label=f"census raw env{env_id}")
        raw_identities.append(_identity(path, label=f"census raw env{env_id}"))
        value = _read_json(path, label=f"census raw env{env_id}")
        if not isinstance(value, list) or not value:
            raise V21BError("census raw per-env export must be a non-empty frame list")
        env_rows = []
        for frame in value:
            if not isinstance(frame, Mapping):
                raise V21BError("census raw frame must be a mapping")
            frame = dict(frame)
            if frame.get("env_id") != env_id or frame.get("topology") != topology or frame.get("scenario_id") != expected_ids[env_id]:
                raise V21BError("census raw frame env/scenario/topology identity disagrees with the signed contract")
            if frame.get("episode_id") != f"{run_uuid}:env{env_id}" or frame.get("phase") != "CENSUS_PRE_K" or frame.get("materialization_phase") != "CENSUS_PRE_K" or frame.get("valid") is not True:
                raise V21BError("census raw frame phase/episode/valid identity is invalid")
            if frame.get("heavy_bucket") is not (topology == "heavy16"):
                raise V21BError("census raw frame heavy bucket disagrees with topology")
            row = canonical_by_id[expected_ids[env_id]]
            for frame_key, manifest_key in (("door_weight_kg", "door_weight_kg"), ("hinge_force_nm", "hinge_force_nm")):
                if not isinstance(frame.get(frame_key), (int, float)) or isinstance(frame.get(frame_key), bool) or not math.isclose(float(frame[frame_key]), float(row[manifest_key]), rel_tol=1e-6, abs_tol=1e-6):
                    raise V21BError("census raw frame runtime scenario values disagree with manifest")
            _validate_common_provenance(frame, contract, label="census")
            raw = frame.get("arm_pd_effort_estimate_unclipped_6d")
            if not isinstance(raw, list) or len(raw) != 6 or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) for item in raw):
                raise V21BError("census raw frame requires six finite unclipped effort values")
            frame_id = frame.get("frame_id")
            if not isinstance(frame_id, str) or not frame_id or frame_id in seen_frame_ids:
                raise V21BError("census raw frame ids must be globally unique")
            seen_frame_ids.add(frame_id)
            env_rows.append(frame)
        frames.extend(env_rows)
    aggregate = {
        "schema": "a2_piper_base_v21B_census_frame_export_aggregate_v1",
        "producer_state": "AGGREGATED_AFTER_CHILD_EXIT",
        "plan_sha256": plan_sha256,
        "topology": topology,
        "run_uuid": run_uuid,
        "manifest_sha256": contract["manifest_sha256"],
        "canonical_manifest_sha256": contract["canonical_manifest_sha256"],
        "manifest_content_sha256": contract["manifest_content_sha256"],
        "source_bindings": dict(contract["source_bindings"]),
        "raw_paths": raw_identities,
        "frames": frames,
    }
    return aggregate


def _record_id(record: Mapping[str, Any]) -> str:
    unsigned = dict(record)
    unsigned.pop("record_id", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def _collect_zero_result(contract: Mapping[str, Any], *, plan_sha256: str | None) -> dict[str, Any]:
    topology = contract.get("topology")
    if topology not in ("canonical16", "heavy16"):
        raise V21BError("zero-shot result contract topology is invalid")
    manifest, canonical_by_id, heavy_by_id = _manifest_rows_from_contract(contract)
    raw_paths = contract.get("raw_paths")
    if not isinstance(raw_paths, list) or len(raw_paths) != 16:
        raise V21BError("zero-shot result contract requires exactly 16 per-env raw paths")
    expected_rows = [manifest["manifest_rows"] if topology == "heavy16" else [item for item in manifest["canonical_manifest_rows"] if item["scenario_id"] not in heavy_by_id]][0]
    expected_ids = [item["scenario_id"] for item in expected_rows]
    records: list[dict[str, Any]] = []
    raw_identities: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for env_id, path_value in enumerate(raw_paths):
        path = _regular_file(Path(path_value).absolute(), label=f"zero-shot raw env{env_id}")
        raw_identities.append(_identity(path, label=f"zero-shot raw env{env_id}"))
        record = _read_json(path, label=f"zero-shot raw env{env_id}")
        if not isinstance(record, Mapping):
            raise V21BError("zero-shot raw terminal export must be one mapping per environment")
        record = dict(record)
        if record.get("schema") != "a2_piper_base_v21B_terminal_arm_record_v1" or record.get("authority") != "ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE":
            raise V21BError("zero-shot raw terminal export schema/authority is invalid")
        provenance = record.get("provenance")
        if not isinstance(provenance, Mapping):
            raise V21BError("zero-shot raw terminal export lacks provenance")
        if provenance.get("env_id") != env_id or provenance.get("scenario_id") != expected_ids[env_id] or provenance.get("topology") != topology or provenance.get("materialization_phase") != "POST_CENSUS":
            raise V21BError("zero-shot raw terminal export env/scenario/topology identity is invalid")
        if provenance.get("manifest_sha256") != contract["manifest_sha256"] or provenance.get("canonical_manifest_sha256") != contract["canonical_manifest_sha256"] or provenance.get("manifest_file_sha256") != contract["manifest_file_sha256"] or provenance.get("manifest_materialization_sha256") != contract["manifest_materialization_sha256"]:
            raise V21BError("zero-shot raw terminal export manifest binding is incomplete")
        for key, value in contract.get("source_bindings", {}).items():
            if provenance.get(key) != value:
                raise V21BError(f"zero-shot raw terminal export {key} is not bound")
        if provenance.get("selected_k_nm") != contract.get("selected_k_nm"):
            raise V21BError("zero-shot raw terminal export selected-k binding is invalid")
        task = record.get("task")
        if not isinstance(task, Mapping) or not isinstance(task.get("goal"), bool) or isinstance(task.get("max_stage"), bool) or not isinstance(task.get("max_stage"), int) or task["max_stage"] < 0:
            raise V21BError("zero-shot raw terminal export lacks strict producer task state")
        if _record_id(record) != record.get("record_id"):
            raise V21BError("zero-shot raw terminal export record_id is invalid")
        if record.get("record_id") in seen_ids:
            raise V21BError("zero-shot raw terminal exports contain duplicate records")
        seen_ids.add(record["record_id"])
        records.append(record)
    if seen_ids != {record["record_id"] for record in records} or len(records) != 16:
        raise V21BError("zero-shot raw terminal exports are not exactly one per environment")
    return {
        "schema": "a2_piper_base_v21B_zero_shot_result_v1",
        "producer_state": "AGGREGATED_AFTER_CHILD_EXIT",
        "plan_sha256": plan_sha256,
        "result_path": str(Path(contract["aggregate_path"]).absolute()),
        "topology": topology,
        "manifest_sha256": contract["manifest_sha256"],
        "canonical_manifest_sha256": contract["canonical_manifest_sha256"],
        "manifest_file_sha256": contract["manifest_file_sha256"],
        "manifest_materialization_sha256": contract["manifest_materialization_sha256"],
        "manifest_content_sha256": contract["manifest_content_sha256"],
        "source_bindings": dict(contract["source_bindings"]),
        "selected_k_nm": contract["selected_k_nm"],
        "record_count": 16,
        "raw_paths": raw_identities,
        "records": records,
    }


def _collect_pilot_result(contract: Mapping[str, Any], *, plan_sha256: str | None) -> dict[str, Any]:
    required_contract = (
        "raw_metrics_path", "source_lock_path", "source_lock_sha256", "source_lock_file_sha256",
        "source_config_sha256", "materialization_sha256", "materialized_config_sha256",
        "adaptation_bundle_sha256", "materialization_phase", "source_checkpoint_sha256", "cell", "seed",
        "repo_commit", "repo_tree",
    )
    if any(key not in contract for key in required_contract) or contract.get("cell") != "B4" or contract.get("seed") != 0:
        raise V21BError("pilot result contract is missing exact cell/seed/materialization identity")
    _validate_materialization_identity(contract.get("materialization_phase"), contract.get("adaptation_bundle_sha256"), label="pilot result contract")
    raw_path = _regular_file(Path(contract.get("raw_metrics_path", "")).absolute(), label="pilot raw metrics")
    source_lock_path = _regular_file(Path(contract.get("source_lock_path", "")).absolute(), label="pilot source lock")
    expected_source_lock = contract.get("source_lock_sha256")
    expected_source_lock_file = contract.get("source_lock_file_sha256")
    expected_commit = contract.get("repo_commit")
    expected_tree = contract.get("repo_tree")
    source_lock = _read_json(source_lock_path, label="pilot source lock")
    if not isinstance(source_lock, Mapping) or source_lock.get("schema") != "a2_piper_base_v21B_source_lock_v1" or source_lock.get("source_lock_sha256") != expected_source_lock or sha256_file(source_lock_path) != expected_source_lock_file:
        raise V21BError("pilot source-lock artifact digest disagrees with the signed contract")
    required_metrics = (
        "send_latch_fire_rate", "hinge_at_send_latch_rad", "hinge_at_crossing_rad", "send_to_cross_steps",
        "stage_overtime_rate", "upper_dof_overspeed_rate", "arm_clipped_utilization",
        "arm_clipped_utilization_valid_rate", "finite_data", "decomposition_sanity",
        "decomposition_sanity_valid_rate",
    )
    coverage_metrics = ("arm_clipped_utilization_valid_rate", "decomposition_sanity_valid_rate")
    expected_sources = {name: f"a2_v21B_{name}" for name in required_metrics}
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise V21BError("pilot raw metrics JSONL contains an empty line")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise V21BError(f"pilot raw metrics line {line_number} is invalid JSON") from exc
        if not isinstance(row, Mapping) or row.get("schema") != "a2_piper_base_v21B_training_metric_v1" or row.get("producer_state") != "PROCESS_COMPLETED" or row.get("scientific_plan_id") != "base_v21B_theta_arm_ablation_v1" or row.get("cell") != contract.get("cell") or row.get("seed") != contract.get("seed") or row.get("materialization_phase") != contract.get("materialization_phase") or row.get("source_config_sha256") != contract.get("source_config_sha256") or row.get("materialization_sha256") != contract.get("materialization_sha256") or row.get("materialized_config_sha256") != contract.get("materialized_config_sha256") or row.get("adaptation_bundle_sha256") != contract.get("adaptation_bundle_sha256") or row.get("source_lock_sha256") != expected_source_lock or row.get("source_lock_file_sha256") != expected_source_lock_file or row.get("git_commit") != expected_commit or row.get("git_tree") != expected_tree:
            raise V21BError("pilot raw metric schema/source-lock binding is invalid")
        if row.get("batch_index") != line_number or not isinstance(row.get("metrics"), Mapping) or not isinstance(row.get("metric_sources"), Mapping) or dict(row["metric_sources"]) != expected_sources or set(row["metrics"]) != set(required_metrics):
            raise V21BError("pilot raw metrics must contain contiguous batch indices")
        def finite(value: Any) -> None:
            if isinstance(value, float) and not math.isfinite(value):
                raise V21BError("pilot raw metrics contain non-finite values")
            if isinstance(value, Mapping):
                for child in value.values(): finite(child)
            elif isinstance(value, list):
                for child in value: finite(child)
        finite(row["metrics"])
        for key, value in row["metrics"].items():
            if isinstance(value, bool):
                if key not in ("finite_data", "decomposition_sanity") or value is not True:
                    raise V21BError("pilot raw boolean metric is not a passing sanity flag")
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise V21BError("pilot raw metric must be finite numeric data")
            elif key in ("finite_data", "decomposition_sanity") and float(value) != 1.0:
                raise V21BError("pilot raw sanity metric must equal one")
        for key in ("send_latch_fire_rate", "stage_overtime_rate", "upper_dof_overspeed_rate", "arm_clipped_utilization"):
            if not 0.0 <= float(row["metrics"][key]) <= 1.0:
                raise V21BError(f"pilot raw metric {key} must be in [0,1]")
        for key in coverage_metrics:
            value = row["metrics"].get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) != 1.0:
                raise V21BError(f"pilot raw coverage metric {key} must equal one")
        rows.append(dict(row))
    if len(rows) != 750 or [row["batch_index"] for row in rows] != list(range(1, 751)):
        raise V21BError("pilot raw metrics require exactly contiguous batches 1..750")
    checkpoints = []
    checkpoint_paths = contract.get("checkpoint_paths")
    if not isinstance(checkpoint_paths, list) or len(checkpoint_paths) != 3:
        raise V21BError("pilot result contract requires checkpoint paths 250/500/750")
    for step, path_value in zip((250, 500, 750), checkpoint_paths):
        identity = _identity(Path(path_value).absolute(), label=f"pilot checkpoint {step}")
        checkpoints.append({"step": step, **identity})
    aggregate = {
        "schema": "a2_piper_base_v21B_pilot_result_v1",
        "producer_state": "AGGREGATED_AFTER_CHILD_EXIT",
        "plan_sha256": plan_sha256,
        "result_path": str(Path(contract["aggregate_path"]).absolute()),
        "arm_realistic_limit_nm": contract.get("arm_realistic_limit_nm"),
        "cell": contract.get("cell"),
        "seed": contract.get("seed"),
        "materialization_phase": contract.get("materialization_phase"),
        "materialization_sha256": contract.get("materialization_sha256"),
        "materialized_config_sha256": contract.get("materialized_config_sha256"),
        "source_checkpoint_sha256": contract.get("source_checkpoint_sha256"),
        "source_lock_sha256": contract.get("source_lock_sha256"),
        "source_lock_file_sha256": contract.get("source_lock_file_sha256"),
        "source_config_sha256": contract.get("source_config_sha256"),
        "materialization_phase": contract.get("materialization_phase"),
        "adaptation_bundle_sha256": contract.get("adaptation_bundle_sha256"),
        "source_lock_path": str(source_lock_path),
        "raw_metrics_path": str(raw_path),
        "repo_commit": expected_commit,
        "repo_tree": expected_tree,
        "required_metrics": list(required_metrics),
        "metric_sources": expected_sources,
        "completed_batches": 750,
        "batch_indices": list(range(1, 751)),
        "batches": rows,
        "checkpoints": checkpoints,
    }
    return aggregate


_SMOKE_METRIC_KEYS = (
    "send_latch_fire_rate", "hinge_at_send_latch_rad", "hinge_at_crossing_rad",
    "send_to_cross_steps", "stage_overtime_rate", "upper_dof_overspeed_rate",
    "arm_clipped_utilization", "arm_clipped_utilization_valid_rate", "finite_data",
    "decomposition_sanity", "decomposition_sanity_valid_rate",
)
_SMOKE_METRIC_SOURCES = {name: f"a2_v21B_{name}" for name in _SMOKE_METRIC_KEYS}
_SMOKE_COVERAGE_KEYS = frozenset(("arm_clipped_utilization_valid_rate", "decomposition_sanity_valid_rate"))


def _validate_smoke_metric_row(
    row: Mapping[str, Any],
    *,
    batch_index: int,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        "schema": "a2_piper_base_v21B_training_metric_v1",
        "producer_state": "PROCESS_COMPLETED",
        "scientific_plan_id": "base_v21B_theta_arm_ablation_v1",
        "cell": contract.get("cell"),
        "seed": contract.get("seed"),
        "materialization_phase": contract.get("materialization_phase"),
        "source_config_sha256": contract.get("source_config_sha256"),
        "materialization_sha256": contract.get("materialization_sha256"),
        "materialized_config_sha256": contract.get("materialized_config_sha256"),
        "adaptation_bundle_sha256": contract.get("adaptation_bundle_sha256"),
        "source_lock_sha256": contract.get("source_lock_sha256"),
        "source_lock_file_sha256": contract.get("source_lock_file_sha256"),
        "git_commit": contract.get("repo_commit"),
        "git_tree": contract.get("repo_tree"),
        "source_checkpoint_sha256": contract.get("source_checkpoint_sha256"),
    }
    if not isinstance(row, Mapping) or any(row.get(key) != value for key, value in expected.items()):
        raise V21BError("smoke training metric schema/source/Git binding is invalid")
    if row.get("cell") not in {"B1", "B2", "B3", "B4", "B5", "B6", "B7"} or isinstance(row.get("seed"), bool) or row.get("seed") not in (0, 1):
        raise V21BError("smoke training metric cell/seed identity is invalid")
    if row.get("batch_index") != batch_index:
        raise V21BError("smoke training metrics must contain contiguous batch indices 1..10")
    metrics = row.get("metrics")
    sources = row.get("metric_sources")
    if not isinstance(metrics, Mapping) or set(metrics) != set(_SMOKE_METRIC_KEYS) or not isinstance(sources, Mapping) or dict(sources) != _SMOKE_METRIC_SOURCES:
        raise V21BError("smoke training metric normalized coverage/source map is incomplete")

    def finite(value: Any, *, label: str) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise V21BError(f"smoke training metric {label} is non-finite")
        if isinstance(value, Mapping):
            for key, child in value.items():
                finite(child, label=f"{label}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                finite(child, label=f"{label}[{index}]")

    finite(metrics, label=f"batch{batch_index}")
    for key, value in metrics.items():
        if isinstance(value, bool):
            if key not in ("finite_data", "decomposition_sanity") or value is not True:
                raise V21BError("smoke training boolean sanity metrics must be true")
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            if key in ("finite_data", "decomposition_sanity") and float(value) != 1.0:
                raise V21BError("smoke training numeric sanity metrics must equal one")
        else:
            raise V21BError("smoke training metric values must be finite scalars")
    for key in _SMOKE_COVERAGE_KEYS:
        if isinstance(metrics.get(key), bool) or metrics.get(key) != 1.0:
            raise V21BError(f"smoke training coverage metric {key} must equal one")
    for key in ("send_latch_fire_rate", "stage_overtime_rate", "upper_dof_overspeed_rate", "arm_clipped_utilization"):
        value = metrics[key]
        if isinstance(value, bool) or not 0.0 <= float(value) <= 1.0:
            raise V21BError(f"smoke training metric {key} must be in [0,1]")
    return dict(row)


def _collect_smoke_result(contract: Mapping[str, Any], *, plan_sha256: str | None) -> dict[str, Any]:
    """Admit the one producer-owned B4 smoke evidence bundle.

    This collector only consumes files emitted by the child process.  It does
    not synthesize rows or infer completion from stdout/W&B state.
    """

    required = (
        "aggregate_path", "raw_metrics_path", "checkpoint_path",
        "source_lock_path", "source_lock_sha256", "source_lock_file_sha256",
        "source_checkpoint_sha256", "source_bindings", "materialization_phase",
        "adaptation_bundle_sha256", "materialization_sha256", "materialized_config_sha256",
        "source_config_sha256", "repo_commit", "repo_tree", "cell", "seed", "artifact_root",
    )
    if any(key not in contract for key in required):
        raise V21BError("smoke result contract is missing an evidence binding")
    if any(key in contract for key in ("terminal_path", "terminal_record", "terminal_record_path", "run_uuid", "full_evidence", "terminal_export_root")):
        raise V21BError("smoke result contract must be scalar-only without terminal/full-trace identity")
    if contract.get("cell") != "B4" or isinstance(contract.get("seed"), bool) or contract.get("seed") != 0 or contract.get("materialization_phase") != "FORMAL_PROMOTED" or contract.get("batch_count") != 10 or contract.get("checkpoint_step") != 10:
        raise V21BError("smoke result contract cell/seed/phase is invalid")
    _validate_materialization_identity(contract.get("materialization_phase"), contract.get("adaptation_bundle_sha256"), label="smoke result contract")
    source_lock_path = _regular_file(Path(contract["source_lock_path"]).absolute(), label="smoke source lock")
    source_lock = _read_json(source_lock_path, label="smoke source lock")
    if not isinstance(source_lock, Mapping) or source_lock.get("schema") != "a2_piper_base_v21B_source_lock_v1" or source_lock.get("source_lock_sha256") != contract["source_lock_sha256"] or sha256_file(source_lock_path) != contract["source_lock_file_sha256"]:
        raise V21BError("smoke source-lock artifact digest disagrees with the signed contract")
    from .a2_piper_v21B_source_freeze import validate_source_lock

    repo_root = Path(contract.get("repo_root", Path.cwd())).absolute()
    validate_source_lock(dict(source_lock), repo_root, require_current=True)
    if contract.get("repo_commit") != _git_value(repo_root, "HEAD") or contract.get("repo_tree") != _git_value(repo_root, "HEAD^{tree}"):
        raise V21BError("smoke result contract Git identity is stale")
    source_bindings = contract.get("source_bindings")
    required_bindings = {
        "source_checkpoint_sha256": contract["source_checkpoint_sha256"],
        "source_lock_sha256": contract["source_lock_sha256"],
        "source_config_sha256": contract["source_config_sha256"],
        "materialization_sha256": contract["materialization_sha256"],
        "materialized_config_sha256": contract["materialized_config_sha256"],
    }
    if not isinstance(source_bindings, Mapping) or dict(source_bindings) != required_bindings:
        raise V21BError("smoke source bindings are incomplete")
    raw_path = _regular_file(Path(contract["raw_metrics_path"]).absolute(), label="smoke training metrics")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise V21BError("smoke training metrics JSONL contains an empty line")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise V21BError(f"smoke training metrics line {line_number} is invalid JSON") from exc
        rows.append(_validate_smoke_metric_row(row, batch_index=line_number, contract=contract))
    if len(rows) != 10:
        raise V21BError("smoke training metrics require exactly contiguous batches 1..10")
    checkpoint = _regular_file(Path(contract["checkpoint_path"]).absolute(), label="smoke step10 checkpoint")
    if checkpoint.name != "model_step_000010.pt":
        raise V21BError("smoke checkpoint must be model_step_000010.pt")
    checkpoint_identity = _identity(checkpoint, label="smoke step10 checkpoint")
    return {
        "schema": "a2_piper_base_v21B_smoke_result_v1",
        "producer_state": "AGGREGATED_AFTER_CHILD_EXIT",
        "plan_sha256": plan_sha256,
        "result_path": str(Path(contract["aggregate_path"]).absolute()),
        "cell": "B4",
        "seed": 0,
        "completed_batches": 10,
        "batch_indices": list(range(1, 11)),
        "training_metrics_path": str(raw_path),
        "raw_metrics_path": str(raw_path),
        "training_metrics_file_sha256": sha256_file(raw_path),
        "training_metrics": rows,
        "checkpoint": checkpoint_identity,
        "checkpoint_path": checkpoint_identity["path"],
        "checkpoint_sha256": checkpoint_identity["sha256"],
        "materialization_phase": contract["materialization_phase"],
        "adaptation_bundle_sha256": contract["adaptation_bundle_sha256"],
        "source_bindings": dict(source_bindings),
        "source_checkpoint_sha256": contract["source_checkpoint_sha256"],
        "source_lock_path": str(source_lock_path),
        "source_lock_sha256": contract["source_lock_sha256"],
        "source_lock_file_sha256": contract["source_lock_file_sha256"],
        "source_config_sha256": contract["source_config_sha256"],
        "materialization_sha256": contract["materialization_sha256"],
        "materialized_config_sha256": contract["materialized_config_sha256"],
        "repo_root": str(repo_root),
        "repo_commit": contract["repo_commit"],
        "repo_tree": contract["repo_tree"],
    }


def _collect_result_contract(contract: Mapping[str, Any], *, plan_sha256: str | None) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        raise V21BError("v21-B result_contract must be a mapping")
    kind = contract.get("kind")
    if kind == "census_frames":
        return _collect_census_result(contract, plan_sha256=plan_sha256)
    if kind == "zero_shot_terminal_records":
        return _collect_zero_result(contract, plan_sha256=plan_sha256)
    if kind == "pilot_metrics":
        return _collect_pilot_result(contract, plan_sha256=plan_sha256)
    if kind == "smoke_evidence":
        return _collect_smoke_result(contract, plan_sha256=plan_sha256)
    raise V21BError(f"unsupported v21-B result_contract kind: {kind!r}")


def run_process_once(
    *,
    argv: Sequence[str],
    repo_root: Path,
    output_root: Path,
    env: Mapping[str, str],
    name: str,
    expected_result_paths: Sequence[Path] = (),
    parents: Mapping[str, Path] | None = None,
    parent_hashes: Mapping[str, str] | None = None,
    source_bindings: Mapping[str, str] | None = None,
    physical_gpu: int | None = None,
    plan_sha256: str | None = None,
    result_contract: Mapping[str, Any] | None = None,
    plan_path: Path | None = None,
) -> dict[str, Any]:
    """Consume one attempt and emit a receipt even when the child fails."""

    root = Path(repo_root).absolute()
    if not root.is_dir() or root.is_symlink():
        raise V21BError(f"repo_root must be a regular directory: {repo_root}")
    if not isinstance(name, str) or not name:
        raise V21BError("v21-B process name is required")
    if not isinstance(argv, Sequence) or isinstance(argv, (str, bytes)) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise V21BError("v21-B process argv must contain non-empty strings")
    if not isinstance(env, Mapping) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in env.items()):
        raise V21BError("v21-B process env must map strings to strings")
    if physical_gpu is not None and (isinstance(physical_gpu, bool) or not isinstance(physical_gpu, int) or physical_gpu < 0 or physical_gpu > 6):
        raise V21BError("v21-B process physical_gpu must be an integer in [0,6]")
    result_paths = tuple(Path(path).absolute() for path in expected_result_paths)
    if any(path.exists() or path.is_symlink() for path in result_paths):
        raise V21BError("v21-B expected result paths must not exist before the one-shot child")
    output_root = Path(output_root).absolute()
    if output_root.exists() or output_root.is_symlink():
        raise V21BError(f"v21-B process output root already exists; retry is forbidden: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir()

    sorted_env = dict(sorted(env.items()))
    command_sha256 = hash_command_env(argv, sorted_env)
    parent_paths = dict(parents or {})
    if plan_path is not None:
        plan_target = _regular_file(Path(plan_path).absolute(), label="v21-B signed plan")
        if "plan" in parent_paths:
            raise V21BError("v21-B process parent name plan is reserved for the consumed plan")
        parent_paths["plan"] = plan_target
    parent_map = _validate_parent_paths(parent_paths)
    if parent_hashes is not None:
        expected_parents = dict(sorted(parent_hashes.items()))
        if plan_path is not None:
            expected_parents["plan"] = parent_map["plan"]
            expected_parents = dict(sorted(expected_parents.items()))
        if expected_parents != parent_map:
            raise V21BError("v21-B process caller parent hashes disagree with actual parent files")
        parent_map = expected_parents
    if source_bindings is not None:
        if not isinstance(source_bindings, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in source_bindings.items()):
            raise V21BError("v21-B source_bindings must map strings to digests")
        source_bindings = dict(sorted(source_bindings.items()))
    if plan_sha256 is not None and (not isinstance(plan_sha256, str) or len(plan_sha256) != 64 or any(c not in "0123456789abcdef" for c in plan_sha256)):
        raise V21BError("v21-B process plan_sha256 must be a lowercase sha256")
    if result_contract is not None:
        if not isinstance(result_contract, Mapping):
            raise V21BError("v21-B result_contract must be a mapping")
        if Path(result_contract.get("aggregate_path", "")).absolute() not in result_paths:
            raise V21BError("v21-B result_contract aggregate_path must be the expected result path")
        raw_paths = result_contract.get("raw_paths", [])
        if isinstance(raw_paths, list) and any(Path(item).exists() or Path(item).is_symlink() for item in raw_paths):
            raise V21BError("v21-B raw producer output paths must not exist before the one-shot child")
        for raw_path in _contract_output_paths(result_contract):
            if raw_path.exists() or raw_path.is_symlink():
                raise V21BError(f"v21-B raw producer output path must not exist before the one-shot child: {raw_path}")

    marker_path = output_root / "ATTEMPT_CONSUMED.json"
    marker = {
        "schema": ATTEMPT_SCHEMA,
        "producer_state": "ATTEMPT_CONSUMED",
        "name": name,
        "argv": list(argv),
        "env": sorted_env,
        "command_sha256": command_sha256,
        "launcher_pid": os.getpid(),
        "created_at_utc": _utc_now(),
        "physical_gpu": physical_gpu,
        "parents": parent_map,
        "source_bindings": source_bindings,
        "plan_sha256": plan_sha256,
        "plan_path": str(Path(plan_path).absolute()) if plan_path is not None else None,
    }
    marker["marker_sha256"] = _digest(marker)
    write_json(marker_path, marker)
    marker_identity = _identity(marker_path, label="v21-B attempt marker")

    stdout_path = output_root / f"{name}.stdout.log"
    stderr_path = output_root / f"{name}.stderr.log"
    child_pid: int | None = None
    child_identity: dict[str, Any] | None = None
    returncode: int | None = None
    launch_error: BaseException | None = None
    parent_pid = os.getpid()
    parent_identity = _process_identity(parent_pid)
    started_at = _utc_now()
    process_env = os.environ.copy()
    process_env.update(sorted_env)
    try:
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            try:
                child = subprocess.Popen(list(argv), cwd=root, env=process_env, stdout=stdout, stderr=stderr)
            except OSError as exc:
                launch_error = exc
            else:
                child_pid = int(child.pid)
                child_identity = _process_identity(child_pid)
                if child_identity.get("ppid") != parent_pid:
                    raise V21BError("v21-B child parent identity does not match launcher")
                returncode = child.wait()
    finally:
        if not stdout_path.exists():
            stdout_path.touch(mode=0o600, exist_ok=False)
        if not stderr_path.exists():
            stderr_path.touch(mode=0o600, exist_ok=False)
    ended_at = _utc_now()
    while ended_at == started_at:
        time.sleep(0.000001)
        ended_at = _utc_now()

    receipt: dict[str, Any] = {
        "schema": PROCESS_RECEIPT_SCHEMA,
        "producer_state": "PROCESS_COMPLETED",
        "name": name,
        "argv": list(argv),
        "env": sorted_env,
        "command_sha256": command_sha256,
        "env_sha256": _digest(sorted_env),
        "pid": child_pid or 0,
        "parent_pid": parent_pid,
        "parent_identity": parent_identity,
        "child_identity": child_identity,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "exit_code": returncode,
        "stdout_path": str(stdout_path.absolute()),
        "stderr_path": str(stderr_path.absolute()),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "stdout_size": stdout_path.stat().st_size,
        "stderr_size": stderr_path.stat().st_size,
        "observed_commit": _git_value(root, "HEAD"),
        "observed_tree": _git_value(root, "HEAD^{tree}"),
        "parent_hashes": parent_map,
        "source_bindings": source_bindings,
        "plan_sha256": plan_sha256,
        "plan_path": str(Path(plan_path).absolute()) if plan_path is not None else None,
        "physical_gpu": physical_gpu,
        "natural_exit": launch_error is None and returncode == 0,
        "marker_path": marker_identity["path"],
        "marker_sha256": marker_identity["sha256"],
        "marker_size": marker_identity["size"],
        "result_contract": dict(result_contract) if result_contract is not None else None,
        "completion_seal_path": str((output_root / "PROCESS_COMPLETED.seal.json").absolute()),
        "completion_seal_schema": COMPLETION_SEAL_SCHEMA,
    }
    # The result contract is intentionally recorded only after Popen has
    # returned a child.  A spawn failure has no producer result to bind.
    if child_pid is not None:
        receipt["expected_result_paths"] = [str(path) for path in result_paths]
        if returncode == 0:
            try:
                    if result_contract is not None:
                        aggregate = _collect_result_contract(result_contract, plan_sha256=plan_sha256)
                        if result_contract.get("kind") == "smoke_evidence":
                            aggregate["process_exit_code"] = returncode
                            aggregate["process_natural_exit"] = returncode == 0
                            aggregate["process_receipt_path"] = str((output_root / "process_receipt.json").absolute())
                            aggregate["process_pid"] = child_pid
                        aggregate_path = Path(result_contract["aggregate_path"]).absolute()
                        _write_json_exclusive_atomic(aggregate_path, aggregate)
                    receipt["result_identities"] = _result_identities(result_paths)
                    if result_contract is not None:
                        receipt["raw_result_identities"] = _result_identities(_contract_output_paths(result_contract))
            except V21BError as exc:
                receipt["result_error"] = str(exc)
    receipt_without_self = dict(receipt)
    receipt_without_self.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = _digest(receipt_without_self)
    receipt_path = output_root / "process_receipt.json"
    write_json(receipt_path, receipt)
    receipt_identity = _identity(receipt_path, label="v21-B process receipt")
    seal_payload = {
        "schema": COMPLETION_SEAL_SCHEMA,
        "producer_state": "PROCESS_COMPLETED_SEALED",
        "receipt_path": receipt_identity["path"],
        "receipt_sha256": receipt_identity["sha256"],
        "receipt_size": receipt_identity["size"],
        "marker_path": receipt["marker_path"],
        "marker_sha256": receipt["marker_sha256"],
        "marker_size": receipt["marker_size"],
        "name": receipt["name"],
        "argv": receipt["argv"],
        "env": receipt["env"],
        "command_sha256": receipt["command_sha256"],
        "pid": receipt["pid"],
        "parent_pid": receipt["parent_pid"],
        "parent_identity": receipt["parent_identity"],
        "child_identity": receipt["child_identity"],
        "started_at_utc": receipt["started_at_utc"],
        "ended_at_utc": receipt["ended_at_utc"],
        "exit_code": receipt["exit_code"],
        "natural_exit": receipt["natural_exit"],
        "stdout_path": receipt["stdout_path"],
        "stdout_sha256": receipt["stdout_sha256"],
        "stdout_size": receipt["stdout_size"],
        "stderr_path": receipt["stderr_path"],
        "stderr_sha256": receipt["stderr_sha256"],
        "stderr_size": receipt["stderr_size"],
        "observed_commit": receipt["observed_commit"],
        "observed_tree": receipt["observed_tree"],
        "parent_hashes": receipt["parent_hashes"],
        "source_bindings": receipt["source_bindings"],
        "plan_sha256": receipt["plan_sha256"],
        "plan_path": receipt["plan_path"],
        "physical_gpu": receipt["physical_gpu"],
        "expected_result_paths": receipt.get("expected_result_paths", []),
        "result_contract": receipt["result_contract"],
        "result_identities": receipt.get("result_identities", []),
        "raw_result_identities": receipt.get("raw_result_identities", []),
        "result_error": receipt.get("result_error"),
    }
    _write_completion_seal(output_root / "PROCESS_COMPLETED.seal.json", seal_payload)
    if launch_error is not None:
        raise V21BError(f"v21-B process {name} failed to spawn after attempt consumption") from launch_error
    if returncode != 0:
        raise V21BError(f"v21-B process {name} exited nonzero: {returncode}")
    if "result_error" in receipt:
        raise V21BError(f"v21-B process {name} exited successfully but result files are invalid: {receipt['result_error']}")
    return receipt


def read_process_receipt(
    path: Path,
    *,
    repo_root: Path | None = None,
    expected_command_sha256: str | None = None,
    expected_env: Mapping[str, str] | None = None,
    expected_result_paths: Sequence[Path] | None = None,
    expected_parent_hashes: Mapping[str, str] | None = None,
    expected_source_bindings: Mapping[str, str] | None = None,
    expected_plan_sha256: str | None = None,
    expected_git_commit: str | None = None,
    expected_git_tree: str | None = None,
    expected_physical_gpu: int | None = None,
    expected_result_contract: Mapping[str, Any] | None = None,
    require_natural_exit: bool = True,
) -> dict[str, Any]:
    target = _regular_file(path, label="v21-B process receipt")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V21BError(f"invalid v21-B process receipt JSON: {target}") from exc
    if not isinstance(payload, Mapping) or payload.get("schema") != PROCESS_RECEIPT_SCHEMA or payload.get("producer_state") != "PROCESS_COMPLETED":
        raise V21BError("v21-B process receipt schema/state is invalid")
    if repo_root is None:
        raise V21BError("v21-B process receipt admission requires repo_root")
    root = Path(repo_root).absolute()
    if not root.is_dir() or root.is_symlink():
        raise V21BError("v21-B process receipt repo_root is invalid")
    receipt_without_self = dict(payload)
    declared_receipt_sha = receipt_without_self.pop("receipt_sha256", None)
    if declared_receipt_sha != _digest(receipt_without_self):
        raise V21BError("v21-B process receipt self digest is invalid")
    seal_path = target.parent / "PROCESS_COMPLETED.seal.json"
    if payload.get("completion_seal_path") != str(seal_path.absolute()) or payload.get("completion_seal_schema") != COMPLETION_SEAL_SCHEMA:
        raise V21BError("v21-B process receipt completion seal path/schema is invalid")
    seal = _read_json(seal_path, label="v21-B process completion seal")
    if not isinstance(seal, Mapping) or seal.get("schema") != COMPLETION_SEAL_SCHEMA or seal.get("producer_state") != "PROCESS_COMPLETED_SEALED":
        raise V21BError("v21-B process completion seal schema/state is invalid")
    seal_without_self = dict(seal)
    declared_seal_sha = seal_without_self.pop("seal_sha256", None)
    if declared_seal_sha != _digest(seal_without_self):
        raise V21BError("v21-B process completion seal self digest is invalid")
    receipt_identity = _identity(target, label="v21-B process receipt")
    if (
        seal.get("receipt_path") != receipt_identity["path"]
        or seal.get("receipt_sha256") != receipt_identity["sha256"]
        or seal.get("receipt_size") != receipt_identity["size"]
    ):
        raise V21BError("v21-B process completion seal receipt identity is invalid")
    seal_receipt_keys = (
        "marker_path", "marker_sha256", "marker_size", "name", "argv", "env", "command_sha256",
        "pid", "parent_pid", "parent_identity", "child_identity", "started_at_utc", "ended_at_utc",
        "exit_code", "natural_exit", "stdout_path", "stdout_sha256", "stdout_size", "stderr_path",
        "stderr_sha256", "stderr_size", "observed_commit", "observed_tree", "parent_hashes",
        "source_bindings", "plan_sha256", "plan_path", "physical_gpu", "expected_result_paths",
        "result_contract", "result_identities", "raw_result_identities", "result_error",
    )
    for key in seal_receipt_keys:
        expected_value = payload.get(key, [] if key in {"expected_result_paths", "result_identities", "raw_result_identities"} else None)
        if seal.get(key) != expected_value:
            raise V21BError(f"v21-B process completion seal {key} disagrees with receipt")
    marker_path_value = payload.get("marker_path")
    marker_path = _regular_file(Path(marker_path_value).absolute(), label="v21-B attempt marker")
    marker = _read_json(marker_path, label="v21-B attempt marker")
    if not isinstance(marker, Mapping) or marker.get("schema") != ATTEMPT_SCHEMA or marker.get("producer_state") != "ATTEMPT_CONSUMED":
        raise V21BError("v21-B attempt marker schema/state is invalid")
    marker_without_self = dict(marker)
    marker_sha = marker_without_self.pop("marker_sha256", None)
    if marker_sha != _digest(marker_without_self):
        raise V21BError("v21-B attempt marker self digest is invalid")
    marker_identity = _identity(marker_path, label="v21-B attempt marker")
    if marker_identity["sha256"] != payload.get("marker_sha256") or marker_identity["size"] != payload.get("marker_size") or marker_identity["path"] != str(marker_path):
        raise V21BError("v21-B process receipt marker identity is invalid")
    marker_receipt_keys = {
        "argv": "argv",
        "env": "env",
        "command_sha256": "command_sha256",
        "physical_gpu": "physical_gpu",
        # The attempt marker deliberately calls this field ``parents`` while
        # the receipt calls the same immutable digest map ``parent_hashes``.
        "parents": "parent_hashes",
        "source_bindings": "source_bindings",
        "plan_sha256": "plan_sha256",
    }
    for marker_key, receipt_key in marker_receipt_keys.items():
        if marker.get(marker_key) != payload.get(receipt_key):
            raise V21BError(f"v21-B process receipt marker {marker_key} lineage disagrees")
    if marker.get("launcher_pid") != payload.get("parent_pid"):
        raise V21BError("v21-B process receipt marker launcher pid disagrees")
    argv = payload.get("argv")
    env = payload.get("env")
    if not isinstance(argv, list) or not isinstance(env, Mapping):
        raise V21BError("v21-B process receipt argv/env are missing")
    if payload.get("command_sha256") != hash_command_env(argv, env):
        raise V21BError("v21-B process receipt command hash is invalid")
    if expected_command_sha256 is not None and payload["command_sha256"] != expected_command_sha256:
        raise V21BError("v21-B process receipt command hash is not bound to the plan")
    if expected_env is not None and dict(env) != dict(sorted(expected_env.items())):
        raise V21BError("v21-B process receipt environment is not bound to the plan")
    if payload.get("env_sha256") != _digest(dict(sorted(env.items()))):
        raise V21BError("v21-B process receipt environment digest is invalid")
    if expected_parent_hashes is not None:
        expected_parents = dict(sorted(expected_parent_hashes.items()))
        if payload.get("plan_path") is not None:
            plan_target = _regular_file(Path(payload["plan_path"]).absolute(), label="v21-B signed plan")
            plan_digest = sha256_file(plan_target)
            if payload.get("parent_hashes", {}).get("plan") != plan_digest:
                raise V21BError("v21-B process receipt consumed-plan parent hash is invalid")
            expected_parents["plan"] = plan_digest
            expected_parents = dict(sorted(expected_parents.items()))
        if payload.get("parent_hashes") != expected_parents:
            raise V21BError("v21-B process receipt parent hashes are not bound")
    if expected_source_bindings is not None and payload.get("source_bindings") != dict(sorted(expected_source_bindings.items())):
        raise V21BError("v21-B process receipt source bindings are not bound")
    if payload.get("plan_path") is not None:
        plan_target = _regular_file(Path(payload["plan_path"]).absolute(), label="v21-B signed plan")
        if payload.get("parent_hashes", {}).get("plan") != sha256_file(plan_target):
            raise V21BError("v21-B process receipt signed-plan parent identity is invalid")
    if expected_plan_sha256 is not None and payload.get("plan_sha256") != expected_plan_sha256:
        raise V21BError("v21-B process receipt plan hash is not bound")
    for field, expected in (("observed_commit", expected_git_commit), ("observed_tree", expected_git_tree)):
        if expected is not None and payload.get(field) != expected:
            raise V21BError(f"v21-B process receipt {field} is not bound")
    if payload.get("observed_commit") != _git_value(root, "HEAD") or payload.get("observed_tree") != _git_value(root, "HEAD^{tree}"):
        raise V21BError("v21-B process receipt observed git identity is stale")
    if expected_physical_gpu is not None and payload.get("physical_gpu") != expected_physical_gpu:
        raise V21BError("v21-B process receipt physical GPU is not bound")
    if payload.get("parent_identity", {}).get("pid") != payload.get("parent_pid") or marker.get("launcher_pid") != payload.get("parent_pid"):
        raise V21BError("v21-B process receipt parent process lineage is invalid")
    child_identity = payload.get("child_identity")
    if payload.get("pid", 0) <= 0 or not isinstance(child_identity, Mapping) or child_identity.get("pid") != payload.get("pid") or child_identity.get("ppid") != payload.get("parent_pid"):
        raise V21BError("v21-B process receipt child process lineage is invalid")
    try:
        started = datetime.fromisoformat(str(payload.get("started_at_utc", "")).replace("Z", "+00:00"))
        ended = datetime.fromisoformat(str(payload.get("ended_at_utc", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise V21BError("v21-B process receipt timestamps are not parseable") from exc
    if ended <= started:
        raise V21BError("v21-B process receipt end time must follow start time")
    if require_natural_exit and (payload.get("natural_exit") is not True or payload.get("exit_code") != 0):
        raise V21BError("v21-B process receipt is not a natural exit-0 producer")
    for key in ("stdout_path", "stderr_path"):
        log = _regular_file(Path(payload[key]).absolute(), label=f"v21-B {key}")
        sha_key = key.replace("_path", "_sha256")
        size_key = key.replace("_path", "_size")
        if sha256_file(log) != payload.get(sha_key) or log.stat().st_size != payload.get(size_key):
            raise V21BError(f"v21-B process receipt {key} hash mismatch")
    expected = tuple(Path(item) for item in (expected_result_paths or payload.get("expected_result_paths", ())))
    actual = tuple(Path(item).absolute() for item in payload.get("expected_result_paths", ()))
    if expected and actual != expected:
        raise V21BError("v21-B process receipt expected result paths are not bound")
    if require_natural_exit:
        identities = payload.get("result_identities")
        if not isinstance(identities, list) or len(identities) != len(actual):
            raise V21BError("v21-B process receipt lacks complete result identities")
        for identity in identities:
            result = _regular_file(Path(identity["path"]).absolute(), label="v21-B result")
            if sha256_file(result) != identity.get("sha256") or result.stat().st_size != identity.get("size"):
                raise V21BError("v21-B process receipt result identity mismatch")
    if expected_result_contract is not None and payload.get("result_contract") != dict(expected_result_contract):
        raise V21BError("v21-B process receipt result contract is not bound")
    if expected_result_contract is not None:
        raw_identities = payload.get("raw_result_identities")
        raw_paths = _contract_output_paths(expected_result_contract)
        if not isinstance(raw_identities, list) or len(raw_identities) != len(raw_paths):
            raise V21BError("v21-B process receipt lacks complete raw result identities")
        for identity, expected_path in zip(raw_identities, raw_paths):
            if not isinstance(identity, Mapping) or identity.get("path") != str(expected_path):
                raise V21BError("v21-B process receipt raw result path is not bound")
            raw = _regular_file(expected_path, label="v21-B raw result")
            if sha256_file(raw) != identity.get("sha256") or raw.stat().st_size != identity.get("size"):
                raise V21BError("v21-B process receipt raw result identity mismatch")
    return dict(payload)


def _verify_signed_plan(plan_path: Path) -> tuple[dict[str, Any], str]:
    """Load one immutable STATIC_PASS plan and bind its canonical digest."""

    target = _regular_file(Path(plan_path).absolute(), label="v21-B signed plan")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V21BError("v21-B signed plan is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise V21BError("v21-B signed plan must be a mapping")
    from .a2_piper_v21B_schemas import schema, validate_artifact

    schema_to_kind = {schema("census"): "census", schema("zero_shot"): "zero_shot", schema("pilot"): "pilot"}
    kind = schema_to_kind.get(value.get("schema"))
    if kind is None:
        raise V21BError("v21-B production runner accepts only census, zero-shot, or pilot plans")
    validate_artifact(value, expected_schema=value["schema"])
    unsigned = dict(value)
    declared = unsigned.pop("plan_sha256", None)
    if value.get("status") != "STATIC_PASS" or not isinstance(declared, str) or declared != _digest(unsigned):
        raise V21BError("v21-B production plan status/digest is invalid")
    return dict(value), kind


def _plan_row(plan: Mapping[str, Any], kind: str, selector: str) -> dict[str, Any]:
    if kind == "pilot":
        if selector != "pilot":
            raise V21BError("pilot plan selector must be 'pilot'")
        row = dict(plan)
    else:
        if selector not in ("canonical16", "heavy16"):
            raise V21BError("census/zero-shot selector must be canonical16 or heavy16")
        commands = plan.get("commands")
        if not isinstance(commands, list):
            raise V21BError("production plan commands are missing")
        matches = [item for item in commands if isinstance(item, Mapping) and item.get("topology") == selector]
        if len(matches) != 1:
            raise V21BError("production plan must contain exactly one selected topology command")
        row = dict(matches[0])
    required = ("argv", "env", "command_sha256", "result_paths", "result_contract", "parent_hashes", "source_bindings", "process_root", "process_receipt_path", "physical_gpu")
    if any(key not in row for key in required):
        raise V21BError("selected production plan row is missing a runner binding")
    if not isinstance(row["argv"], list) or not row["argv"] or any(not isinstance(item, str) or not item for item in row["argv"]):
        raise V21BError("selected production plan argv is invalid")
    if not isinstance(row["env"], Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in row["env"].items()):
        raise V21BError("selected production plan env is invalid")
    if row["command_sha256"] != hash_command_env(row["argv"], row["env"]):
        raise V21BError("selected production plan command hash is invalid")
    if not isinstance(row["result_paths"], list) or not row["result_paths"] or any(not isinstance(item, str) for item in row["result_paths"]):
        raise V21BError("selected production plan result paths are invalid")
    if not isinstance(row["result_contract"], Mapping) or not isinstance(row["parent_hashes"], Mapping) or not isinstance(row["source_bindings"], Mapping):
        raise V21BError("selected production plan contract/parent/source bindings are invalid")
    if not isinstance(row["process_root"], str) or not isinstance(row["process_receipt_path"], str):
        raise V21BError("selected production plan process destinations are invalid")
    if row["process_receipt_path"] != str((Path(row["process_root"]) / "process_receipt.json").absolute()):
        raise V21BError("selected production plan receipt destination is not under its process root")
    if isinstance(row["physical_gpu"], bool) or not isinstance(row["physical_gpu"], int) or not 0 <= row["physical_gpu"] <= 6:
        raise V21BError("selected production plan physical GPU is invalid")
    contract = dict(row["result_contract"])
    aggregate = contract.get("aggregate_path")
    if not isinstance(aggregate, str) or str(Path(aggregate).absolute()) not in {str(Path(item).absolute()) for item in row["result_paths"]}:
        raise V21BError("selected production plan aggregate destination is not an expected result")
    return row


def _plan_parents(plan: Mapping[str, Any], row: Mapping[str, Any], kind: str) -> dict[str, Path]:
    materialized = plan.get("materialized_config_path")
    if not isinstance(materialized, str):
        raise V21BError("production plan materialized_config_path is missing")
    if kind == "pilot":
        source_lock = row.get("source_lock_path")
        if not isinstance(source_lock, str):
            raise V21BError("pilot plan source_lock_path is missing")
        return {"source_lock": Path(source_lock).absolute(), "materialized_config": Path(materialized).absolute()}
    manifest = row.get("manifest_path")
    if not isinstance(manifest, str):
        raise V21BError("probe plan manifest_path is missing")
    return {"manifest": Path(manifest).absolute(), "materialized_config": Path(materialized).absolute()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--selector", required=True, help="canonical16/heavy16 for probes, or pilot")
    args = parser.parse_args(argv)
    plan, kind = _verify_signed_plan(args.plan)
    row = _plan_row(plan, kind, args.selector)
    root = Path(args.repo_root).absolute()
    if not root.is_dir() or root.is_symlink():
        raise V21BError("--repo-root must be a regular directory")
    output_root = Path(row["process_root"]).absolute()
    result_paths = tuple(Path(item).absolute() for item in row["result_paths"])
    contract = dict(row["result_contract"])
    if contract.get("aggregate_path") is None:
        raise V21BError("selected production plan result contract lacks aggregate_path")
    parents = _plan_parents(plan, row, kind)
    receipt = run_process_once(
        argv=row["argv"], repo_root=root, output_root=output_root, env=row["env"],
        name=f"v21B_{kind}_{args.selector}", expected_result_paths=result_paths,
        parents=parents, parent_hashes=row["parent_hashes"], source_bindings=row["source_bindings"],
        physical_gpu=row["physical_gpu"], plan_sha256=plan["plan_sha256"], result_contract=contract,
        plan_path=Path(args.plan).absolute(),
    )
    admitted = read_process_receipt(
        Path(row["process_receipt_path"]), repo_root=root,
        expected_command_sha256=row["command_sha256"], expected_env=row["env"],
        expected_result_paths=result_paths, expected_parent_hashes=row["parent_hashes"],
        expected_source_bindings=row["source_bindings"], expected_plan_sha256=plan["plan_sha256"],
        expected_git_commit=row.get("repo_commit"), expected_git_tree=row.get("repo_tree"),
        expected_physical_gpu=row["physical_gpu"], expected_result_contract=contract,
        require_natural_exit=True,
    )
    receipt_path = Path(row["process_receipt_path"]).absolute()
    seal_path = receipt_path.parent / "PROCESS_COMPLETED.seal.json"
    seal_identity = _identity(seal_path, label="v21-B process completion seal")
    print(json.dumps({"receipt_path": str(receipt_path), "receipt_sha256": sha256_file(receipt_path), "seal_path": str(seal_path), "seal_sha256": seal_identity["sha256"], "plan_sha256": admitted["plan_sha256"], "natural_exit": admitted["natural_exit"]}, sort_keys=True))
    return 0


execute_once = run_process_once
spawn_once = run_process_once
run_process = run_process_once


__all__ = [
    "PROCESS_RECEIPT_SCHEMA", "ATTEMPT_SCHEMA", "COMPLETION_SEAL_SCHEMA", "hash_command_env", "observed_git_identity", "run_process_once",
    "execute_once", "spawn_once", "run_process", "read_process_receipt", "main",
]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V21BError as exc:
        raise SystemExit(f"v21-B production runner rejected plan: {exc}") from exc
