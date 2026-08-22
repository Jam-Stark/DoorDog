# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import logging
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from typing import Any

logging.getLogger("asyncio").setLevel(logging.WARNING)

import isaaclab.sim as sim_utils
import numpy as np
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg

from gr00t.rl.isaac_utils.playground.env_rand.door import DoorSpawnerCfg, spawn_door


_V21B_MANIFEST_SCHEMA = "a2_piper_base_v21B_heavy16_manifest_v1"
_V21B_SIGNED_PROBE_FLAG = "a2_v21B_signed_probe_scenarios_enabled"

# v23 P0 deliberately owns a plain, readable selector contract.  It is not a
# compatibility alias for the signed v21-B selector: no legacy integrity
# fields are accepted or forwarded on this branch.
_V23_P0_PLAIN_MANIFEST_SCHEMA = "a2_piper_base_v23_p0_plain_scenario_manifest_v1"
_V23_P0_PLAIN_MANIFEST_FLAG = "a2_v23_p0_plain_scenario_enabled"
_V23_P0_PLAIN_MANIFEST_PATH_KEY = "a2_v23_p0_scenario_manifest_path"
_V23_P0_PLAIN_TOPOLOGY_KEY = "a2_v23_p0_scenario_topology"
_V23_P0_PLAIN_SOURCE_FIELDS = {
    "scenario_id",
    "handle_height_m",
    "door_weight_kg",
    "hinge_force_nm",
}
_V23_P0_PLAIN_TOPOLOGIES = ("canonical16", "heavy16")

# Route-B visual evidence owns a separate, deliberately unambiguous static
# manifest.  The simulator selector consumes this exact schema only when the
# render flag is explicitly enabled; historical selectors remain unchanged.
_V23_ROUTE_B_RENDER_MANIFEST_SCHEMA = "a2_piper_v23_route_b_render_scenario_manifest_v1"
_V23_ROUTE_B_RENDER_MANIFEST_STATUS = "STATIC_RENDER"
_V23_ROUTE_B_RENDER_MANIFEST_TOPOLOGY = "render16"
_V23_ROUTE_B_RENDER_ENABLED_KEY = "a2_v23_route_b_render_enabled"
_V23_ROUTE_B_RENDER_MANIFEST_PATH_KEY = "a2_v23_route_b_render_manifest_path"
_V23_ROUTE_B_RENDER_SCALAR_FIELDS = (
    "handle_height_m",
    "door_weight_kg",
    "hinge_max_force_nm",
    "hinge_damping_native",
    "hinge_stiffness_native",
)

# v23 P0 bound mode is a separate, strict high-level selector.  The historical
# plain selector above remains unchanged when this mode is disabled.
_V23_P0_BOUND_MANIFEST_SCHEMA = "a2_piper_base_v23_p0_bound_plain16_manifest_v1"
_V23_P0_BOUND_MANIFEST_FLAG = "a2_v23_p0_bound_plain_scenario_enabled"
_V23_P0_BOUND_MANIFEST_PATH_KEY = "a2_v23_p0_bound_plain_scenario_manifest_path"
_V23_P0_BOUND_SELECTOR_MODE = "v23_bound_plain16"
_V23_P0_BOUND_CANONICAL_SCHEMA = "a2_piper_v23_canonical_geometry_v1"
_V23_D1_BOUND_MANIFEST_SCHEMA = "a2_piper_base_v23_d1_capability_bound_plain16_manifest_v1"
_V23_D1_BOUND_SELECTOR_MODE = "v23_d1_capability_source_plain16"
_V23_D1_BOUND_STATUS = "BOUND_D1_CAPABILITY_SOURCE"
_V23_D1_BOUND_PURPOSE = "D1_CAPABILITY_SOURCE"
_V23_D1_SAMPLER_ENABLED_KEY = "a2_v23_d1_sampler_enabled"
_V23_D1_MANIFEST_PATH_KEY = "a2_v23_d1_manifest_path"
_V23_D1_VARIANT_KEY = "a2_v23_d1_variant"
_V23_D1_BUCKET_SEED_KEY = "a2_v23_d1_bucket_seed"
_V23_D1_TOTAL_STEPS_KEY = "a2_v23_d1_total_steps"
_V23_D1_RECEIPT_PATH_KEY = "a2_v23_d1_receipt_path"
_V23_D1_GLOBAL_STEP_KEY = "a2_v23_d1_global_step"
_V23_D1_SOURCE_FREEZE_SCHEMA = "a2_piper_v23_capability_source_freeze_v1"
_V23_D1_SOURCE_FREEZE_STATUS = "CAPABILITY_SOURCE_FROZEN"
_V23_D1_SOURCE_CELL_ID = "A0"
_V23_D1_SOURCE_BASIS = "CURRENT_EASY_A0_STABLE_REFERENCE"
_V23_D1_REQUESTED_PARAMS = {
    "hinge_damping_native": 50.0,
    "hinge_stiffness_native": 2.0,
    "hinge_max_force_nm": 4.5,
    "door_weight_kg": 120.0,
}
_V23_D1_NATIVE_PARAMS = {
    "hinge_damping_native": 2864.7890625,
    "hinge_stiffness_native": 114.59156036376953,
    "hinge_effort_limit_nm": 4.5,
    "door_weight_kg": 119.99999237060547,
}
_V23_P0_BOUND_LOCAL_FACTS = {
    "door_width_m": 0.95,
    "door_height_m": 2.05,
    "handle_height_m": 0.975,
    "handle_width_m": 0.12,
    "handle_type": "lever",
    "door_open_lr": "right",
    "door_open_io": "out",
    "door_open_lr_sign": -1,
    "door_open_io_sign": -1,
    "hinge_axis_local": [0.0, 0.0, 1.0],
    "hinge_anchor_local": [0.02, 0.475, 0.0],
}
_V23_P0_BOUND_SOURCE_IDENTITY_FIELDS = {
    "source_manifest_path",
    "source_role",
    "source_row",
}
_V23_P0_BOUND_REQUESTED_PARAMS = {
    "hinge_damping_native": 200.0,
    "hinge_stiffness_native": 30.0,
    "hinge_max_force_nm": 24.0,
    "door_weight_kg": 160.0,
}
_V23_P0_BOUND_NATIVE_PARAMS = {
    "hinge_damping_native": 11459.15625,
    "hinge_stiffness_native": 1718.8734130859375,
    "hinge_effort_limit_nm": 24.0,
    "door_weight_kg": 160.0,
}
_V23_P0_BOUND_ROW_FIELDS = {
    "source_identity",
    "scenario_id",
    "env_id",
    "episode_index",
    "plain_prefix_id",
    "checkpoint",
    "config",
    "seed",
    "topology",
    "cell_id",
    "geometry_id",
    "canonical_geometry",
    "requested_params",
    "realized_params",
    "door_width_m",
    "door_height_m",
    "handle_height_m",
    "handle_width_m",
    "handle_type",
    "door_open_lr",
    "door_open_io",
    "hinge_axis_local",
    "hinge_anchor_local",
}


def _v21b_scenario_digest(row: dict) -> str:
    body = {
        "scenario_id": row.get("scenario_id"),
        "door_weight_kg": row.get("door_weight_kg"),
        "hinge_force_nm": row.get("hinge_force_nm"),
        "handle_height_m": row.get("handle_height_m"),
        "source": row.get("source"),
    }
    return hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _v21b_digest(value, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"v21-B {label} must be a lowercase sha256 digest")
    return value


def _v21b_manifest_payload(env_config) -> tuple[dict, Path]:
    path_value = env_config.get("a2_v21B_scenario_manifest_path")
    if not isinstance(path_value, (str, Path)) or not str(path_value):
        raise ValueError("v21-B scenario selection requires a2_v21B_scenario_manifest_path")
    path = Path(path_value)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"v21-B scenario manifest must be a regular non-symlink file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"v21-B scenario manifest is not valid JSON: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != _V21B_MANIFEST_SCHEMA or payload.get("status") != "STATIC_PASS":
        raise ValueError("v21-B scenario manifest schema/status is invalid")
    canonical = payload.get("canonical_manifest_rows")
    heavy = payload.get("manifest_rows")
    if not isinstance(canonical, list) or len(canonical) != 32 or not isinstance(heavy, list) or len(heavy) != 16:
        raise ValueError("v21-B scenario manifest requires exactly 16 canonical/light and 16 heavy rows")
    canonical_ids = [row.get("scenario_id") if isinstance(row, dict) else None for row in canonical]
    heavy_ids = [row.get("scenario_id") if isinstance(row, dict) else None for row in heavy]
    if any(not isinstance(item, str) or not item for item in canonical_ids + heavy_ids) or len(set(canonical_ids)) != 32 or len(set(heavy_ids)) != 16 or len(set(heavy_ids) - set(canonical_ids)):
        raise ValueError("v21-B scenario manifest ids must be unique and heavy ids must be canonical ids")
    if len(set(canonical_ids) - set(heavy_ids)) != 16:
        raise ValueError("v21-B scenario manifest must contain exactly 16 light ids")
    if hashlib.sha256(json.dumps(heavy, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest() != payload.get("manifest_sha256"):
        raise ValueError("v21-B scenario manifest heavy hash is invalid")
    if payload.get("heavy_manifest_sha256") != payload.get("manifest_sha256"):
        raise ValueError("v21-B scenario manifest heavy hash alias is invalid")
    if hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest() != payload.get("canonical_manifest_sha256"):
        raise ValueError("v21-B scenario manifest canonical hash is invalid")
    row_hashes = set()
    canonical_by_id = {row["scenario_id"]: row for row in canonical}
    for row in canonical:
        if not isinstance(row, dict) or any(key not in row for key in ("scenario_id", "door_weight_kg", "hinge_force_nm", "handle_height_m", "source", "scenario_sha256")):
            raise ValueError("v21-B scenario manifest rows require immutable identity and scenario_sha256")
        values = tuple(float(row[key]) for key in ("door_weight_kg", "hinge_force_nm", "handle_height_m"))
        if any(not math.isfinite(value) or value <= 0.0 for value in values) or row["scenario_sha256"] != _v21b_scenario_digest(row):
            raise ValueError(f"v21-B scenario row is invalid: {row.get('scenario_id')!r}")
        row_hashes.add(row["scenario_sha256"])
    if len(row_hashes) != 32:
        raise ValueError("v21-B scenario row hashes must be unique")
    for row in heavy:
        if row.get("scenario_sha256") != canonical_by_id[row["scenario_id"]].get("scenario_sha256"):
            raise ValueError("v21-B heavy row is not byte-bound to canonical row")
        if float(row["door_weight_kg"]) < 140.0 and float(row["hinge_force_nm"]) < 10.0:
            raise ValueError("v21-B heavy row fails the registered eligibility rule")
    expected_hash = env_config.get("a2_v21B_scenario_manifest_sha256")
    if expected_hash is None:
        raise ValueError("v21-B scenario selection requires a2_v21B_scenario_manifest_sha256")
    _v21b_digest(expected_hash, "scenario manifest hash")
    if expected_hash != payload["manifest_sha256"]:
        raise ValueError("v21-B scenario manifest hash disagrees with env.config")
    expected_file_hash = env_config.get("a2_v21B_scenario_manifest_file_sha256")
    _v21b_digest(expected_file_hash, "scenario manifest file hash")
    actual_file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_file_hash != actual_file_hash:
        raise ValueError("v21-B scenario manifest file hash disagrees with env.config")
    expected_canonical_hash = env_config.get("a2_v21B_canonical_manifest_sha256")
    _v21b_digest(expected_canonical_hash, "canonical manifest hash")
    if expected_canonical_hash != payload.get("canonical_manifest_sha256"):
        raise ValueError("v21-B canonical manifest hash disagrees with env.config")
    expected_manifest_source_checkpoint = env_config.get("a2_v21B_scenario_manifest_source_checkpoint_sha256")
    expected_manifest_source_lock = env_config.get("a2_v21B_scenario_manifest_source_lock_sha256")
    expected_manifest_source_config = env_config.get("a2_v21B_scenario_manifest_source_config_sha256")
    expected_materialization = env_config.get("a2_v21B_scenario_manifest_materialization_sha256")
    for value, label in ((expected_manifest_source_checkpoint, "manifest source checkpoint hash"), (expected_manifest_source_lock, "manifest source lock hash"), (expected_manifest_source_config, "manifest source config hash"), (expected_materialization, "scenario manifest materialization hash")):
        _v21b_digest(value, label)
    for value, key in ((expected_manifest_source_checkpoint, "source_checkpoint_sha256"), (expected_manifest_source_lock, "source_lock_sha256"), (expected_manifest_source_config, "source_config_sha256"), (expected_materialization, "materialization_sha256")):
        if value != payload.get(key):
            raise ValueError(f"v21-B manifest {key} disagrees with env.config")
    expected_json_hash = env_config.get("a2_v21B_scenario_manifest_json_sha256")
    _v21b_digest(expected_json_hash, "scenario manifest JSON hash")
    manifest_json = env_config.get("a2_v21B_scenario_manifest_json")
    if not isinstance(manifest_json, str) or hashlib.sha256(manifest_json.encode("utf-8")).hexdigest() != expected_json_hash:
        raise ValueError("v21-B scenario manifest JSON binding is invalid")
    try:
        declared_json = json.loads(manifest_json)
    except json.JSONDecodeError as exc:
        raise ValueError("v21-B scenario manifest JSON binding is not JSON") from exc
    expected_json = {key: value for key, value in payload.items() if key not in {"path", "file_sha256"}}
    if declared_json != expected_json:
        raise ValueError("v21-B scenario manifest JSON does not match the consumed file")
    return payload, path


def _validate_v21b_ordered_task_cfg(task_obj_cfg_dict: dict, rows: Sequence[dict], topology: str) -> dict:
    if not isinstance(task_obj_cfg_dict, dict) or "door" not in task_obj_cfg_dict:
        raise ValueError("v21-B ordered task config must contain door")
    spawn_cfg = task_obj_cfg_dict["door"].spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg) or spawn_cfg.random_choice is not False:
        raise ValueError("v21-B ordered door config must use deterministic MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or len(spawn_cfg.assets_cfg) != 16:
        raise ValueError(f"v21-B {topology} ordered config requires exactly 16 assets")
    for index, (asset_cfg, row) in enumerate(zip(spawn_cfg.assets_cfg, rows)):
        if not isinstance(asset_cfg, DoorSpawnerCfg):
            raise TypeError(f"v21-B ordered asset {index} must be DoorSpawnerCfg")
        expected = (float(row["handle_height_m"]), float(row["door_weight_kg"]), float(row["hinge_force_nm"]))
        actual = (asset_cfg.rand_door_handle_height, asset_cfg.rand_door_weight, asset_cfg.rand_hinge_drive_max_force)
        if any(value is None or not math.isclose(float(value), exp, rel_tol=1e-9, abs_tol=1e-9) for value, exp in zip(actual, expected)):
            raise ValueError(f"v21-B {topology} ordered scenario value mismatch at env {index}")
    return task_obj_cfg_dict


def get_TaskObjCfgDict_for_v21B_scenario_manifest(
    num_envs: int,
    env_config,
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Select canonical16/light or heavy16 rows via immutable high-level cfg replacement."""

    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs != 16:
        raise ValueError("v21-B canonical16/heavy16 scenario topology requires num_envs=16")
    if env_config.get(_V21B_SIGNED_PROBE_FLAG) is not True:
        raise ValueError("v21-B signed scenario selector requires a2_v21B_signed_probe_scenarios_enabled=true")
    topology = env_config.get("a2_v21B_census_topology")
    if topology not in ("canonical16", "heavy16"):
        raise ValueError("v21-B scenario selector requires canonical16 or heavy16 topology")
    manifest, _ = _v21b_manifest_payload(env_config)
    heavy_ids = {row["scenario_id"] for row in manifest["manifest_rows"]}
    rows = manifest["manifest_rows"] if topology == "heavy16" else [row for row in manifest["canonical_manifest_rows"] if row["scenario_id"] not in heavy_ids]
    if len(rows) != num_envs:
        raise ValueError(f"v21-B {topology} manifest row count mismatch: expected {num_envs}, got {len(rows)}")
    base = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    if not isinstance(base, dict) or "door" not in base:
        raise ValueError("v21-B scenario selector requires a door TaskObjCfgDict")
    spawn_cfg = base["door"].spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg) or not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("v21-B scenario selector requires non-empty MultiAssetSpawnerCfg")
    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("v21-B scenario selector base asset must be DoorSpawnerCfg")
    upper, lower = float(base_door_cfg.door_handle_tblr[0]), float(base_door_cfg.door_handle_tblr[1])
    if not math.isfinite(upper) or not math.isfinite(lower) or lower >= upper:
        raise ValueError("v21-B base DoorSpawnerCfg handle bounds are invalid")
    variants = []
    for row in rows:
        height = float(row["handle_height_m"])
        if not lower <= height <= upper:
            raise ValueError(f"v21-B scenario {row['scenario_id']} handle height is outside DoorSpawnerCfg bounds")
        weight = float(row["door_weight_kg"])
        hinge = float(row["hinge_force_nm"])
        if not all(math.isfinite(value) and value > 0.0 for value in (height, weight, hinge)):
            raise ValueError(f"v21-B scenario {row['scenario_id']} values must be finite and positive")
        variants.append(base_door_cfg.replace(rand_door_handle_height=height, rand_door_weight=weight, rand_hinge_drive_max_force=hinge))
    ordered_spawn_cfg = spawn_cfg.replace(assets_cfg=variants, random_choice=False)
    result = dict(base)
    result["door"] = base["door"].replace(spawn=ordered_spawn_cfg)
    return _validate_v21b_ordered_task_cfg(result, rows, topology)


def _v23_p0_reject_integrity_fields(value, *, path: str = "manifest") -> None:
    """Reject legacy digest/hash ceremony from the plain v23 manifest."""

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"v23 P0 plain manifest key at {path} must be a string")
            lowered = key.lower()
            if "sha" in lowered or "hash" in lowered or "digest" in lowered:
                raise ValueError(
                    f"v23 P0 plain manifest forbids integrity field {path}.{key}"
                )
            _v23_p0_reject_integrity_fields(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _v23_p0_reject_integrity_fields(item, path=f"{path}[{index}]")


def _v23_p0_plain_manifest_payload(env_config) -> tuple[dict, Path]:
    """Read and validate one v23 P0 plain canonical16/heavy16 manifest."""

    if env_config.get(_V23_P0_PLAIN_MANIFEST_FLAG) is not True:
        raise ValueError(
            f"v23 P0 plain selector requires env.config.{_V23_P0_PLAIN_MANIFEST_FLAG}=true"
        )
    path_value = env_config.get(_V23_P0_PLAIN_MANIFEST_PATH_KEY)
    if not isinstance(path_value, (str, Path)) or not str(path_value):
        raise ValueError(
            f"v23 P0 plain selector requires {_V23_P0_PLAIN_MANIFEST_PATH_KEY}"
        )
    path = Path(path_value)
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError(
            "v23 P0 plain scenario manifest must be an absolute regular non-symlink file: "
            f"{path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"v23 P0 plain scenario manifest is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("v23 P0 plain scenario manifest root must be an object")
    _v23_p0_reject_integrity_fields(payload)
    expected_keys = {
        "schema",
        "status",
        "topology",
        "source_manifest_path",
        "source_role",
        "rows",
    }
    if set(payload) != expected_keys:
        raise ValueError(
            "v23 P0 plain scenario manifest fields must be exactly "
            f"{sorted(expected_keys)}; got {sorted(payload)}"
        )
    if payload.get("schema") != _V23_P0_PLAIN_MANIFEST_SCHEMA:
        raise ValueError("v23 P0 plain scenario manifest schema is invalid")
    if payload.get("status") != "STATIC_PLAIN":
        raise ValueError("v23 P0 plain scenario manifest status must be STATIC_PLAIN")
    topology = payload.get("topology")
    if topology not in _V23_P0_PLAIN_TOPOLOGIES:
        raise ValueError(
            "v23 P0 plain scenario manifest topology must be canonical16 or heavy16"
        )
    configured_topology = env_config.get(_V23_P0_PLAIN_TOPOLOGY_KEY)
    if configured_topology != topology:
        raise ValueError(
            "v23 P0 plain scenario topology disagrees with env.config: "
            f"manifest={topology!r}, config={configured_topology!r}"
        )
    source_path_value = payload.get("source_manifest_path")
    if not isinstance(source_path_value, str) or not source_path_value:
        raise ValueError("v23 P0 plain scenario manifest requires source_manifest_path")
    source_path = Path(source_path_value)
    if not source_path.is_absolute() or not source_path.is_file() or source_path.is_symlink():
        raise ValueError(
            "v23 P0 plain scenario source_manifest_path must be an absolute regular file: "
            f"{source_path}"
        )
    if payload.get("source_role") != "historical_prior_only":
        raise ValueError(
            "v23 P0 plain scenario source_role must be historical_prior_only"
        )
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 16:
        raise ValueError("v23 P0 plain scenario manifest requires exactly 16 rows")
    scenario_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != _V23_P0_PLAIN_SOURCE_FIELDS:
            raise ValueError(
                f"v23 P0 plain scenario row {index} fields must be exactly "
                f"{sorted(_V23_P0_PLAIN_SOURCE_FIELDS)}"
            )
        scenario_id = row["scenario_id"]
        if not isinstance(scenario_id, str) or not scenario_id or scenario_id in scenario_ids:
            raise ValueError(
                f"v23 P0 plain scenario row {index} has a missing or duplicate scenario_id"
            )
        scenario_ids.add(scenario_id)
        for field in ("handle_height_m", "door_weight_kg", "hinge_force_nm"):
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError(f"v23 P0 plain scenario row {index} {field} must be real")
            numeric = float(value)
            if not math.isfinite(numeric) or numeric <= 0.0:
                raise ValueError(
                    f"v23 P0 plain scenario row {index} {field} must be finite and positive"
                )
    return payload, path


def _v23_p0_bound_float(value, expected: float, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"v23 P0 bound {label} must be real")
    numeric = float(value)
    if not math.isfinite(numeric) or not math.isclose(
        numeric, float(expected), rel_tol=0.0, abs_tol=1.0e-9
    ):
        raise ValueError(f"v23 P0 bound {label} disagrees with canonical geometry")


def _v23_p0_bound_vector(value, expected: Sequence[Real], label: str) -> None:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or len(value) != len(expected)
    ):
        raise ValueError(f"v23 P0 bound {label} must have exactly {len(expected)} values")
    for index, (actual, target) in enumerate(zip(value, expected)):
        _v23_p0_bound_float(actual, float(target), f"{label}[{index}]")


def _v23_d1_bound_manifest_payload(
    payload: dict,
    path: Path,
    env_config,
) -> tuple[dict, Path]:
    expected_keys = {
        "schema",
        "status",
        "purpose",
        "selector_mode",
        "topology",
        "source_manifest_path",
        "source_role",
        "capability_source_freeze_schema",
        "capability_source_freeze_path",
        "canonical_geometry_schema",
        "rows",
    }
    if set(payload) != expected_keys:
        raise ValueError("v23 D1 bound manifest fields do not match the exact capability-source schema")
    if (
        payload.get("schema") != _V23_D1_BOUND_MANIFEST_SCHEMA
        or payload.get("status") != _V23_D1_BOUND_STATUS
        or payload.get("purpose") != _V23_D1_BOUND_PURPOSE
        or payload.get("selector_mode") != _V23_D1_BOUND_SELECTOR_MODE
        or payload.get("capability_source_freeze_schema") != _V23_D1_SOURCE_FREEZE_SCHEMA
        or payload.get("canonical_geometry_schema") != _V23_P0_BOUND_CANONICAL_SCHEMA
    ):
        raise ValueError("v23 D1 bound manifest schema/status/purpose is invalid")
    topology = payload.get("topology")
    if topology not in _V23_P0_PLAIN_TOPOLOGIES:
        raise ValueError("v23 D1 bound topology must be canonical16 or heavy16")
    if env_config.get(_V23_P0_PLAIN_TOPOLOGY_KEY) != topology:
        raise ValueError("v23 D1 bound topology disagrees with env.config")
    source_path_value = payload.get("source_manifest_path")
    source_path = Path(source_path_value) if isinstance(source_path_value, str) else None
    if source_path is None or not source_path.is_absolute() or source_path.is_symlink() or not source_path.is_file():
        raise ValueError("v23 D1 source_manifest_path must be an absolute regular file")
    if payload.get("source_role") != "historical_prior_only":
        raise ValueError("v23 D1 source_role must be historical_prior_only")
    freeze_path_value = payload.get("capability_source_freeze_path")
    freeze_path = Path(freeze_path_value) if isinstance(freeze_path_value, str) else None
    if freeze_path is None or not freeze_path.is_absolute() or freeze_path.is_symlink() or not freeze_path.is_file():
        raise ValueError("v23 D1 capability_source_freeze_path must be an absolute regular file")
    try:
        source_freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("v23 D1 capability source freeze is not valid JSON") from exc
    if not isinstance(source_freeze, dict):
        raise ValueError("v23 D1 capability source freeze root must be an object")
    if (
        set(source_freeze)
        != {
            "schema", "status", "purpose", "source_cell_id", "source_geometry_id", "selection_basis",
            "selected_effort_nm", "effort_profile", "confirmed_E2", "requested_params", "native_params",
            "canonical_geometry", "shared_local_kinematic_facts", "source_paths", "source_provenance",
        }
        or source_freeze.get("schema") != _V23_D1_SOURCE_FREEZE_SCHEMA
        or source_freeze.get("status") != _V23_D1_SOURCE_FREEZE_STATUS
        or source_freeze.get("purpose") != _V23_D1_BOUND_PURPOSE
        or source_freeze.get("source_cell_id") != _V23_D1_SOURCE_CELL_ID
        or source_freeze.get("selection_basis") != _V23_D1_SOURCE_BASIS
        or source_freeze.get("selected_effort_nm") != 40.0
        or source_freeze.get("effort_profile") != {"effort_nm": 40.0, "name": "base_v23_p0_effort_40"}
        or source_freeze.get("confirmed_E2") is not False
        or source_freeze.get("requested_params") != _V23_D1_REQUESTED_PARAMS
        or source_freeze.get("native_params") != _V23_D1_NATIVE_PARAMS
    ):
        raise ValueError("v23 D1 capability source freeze identity/parameters are invalid")
    source_paths = source_freeze.get("source_paths")
    if (
        not isinstance(source_paths, dict)
        or set(source_paths) != {"atlas", "external_threshold", "effort_freeze"}
        or any(not isinstance(value, str) or not value for value in source_paths.values())
    ):
        raise ValueError("v23 D1 capability source freeze source paths are invalid")
    source_provenance = source_freeze.get("source_provenance")
    external_provenance = source_provenance.get("external_threshold") if isinstance(source_provenance, dict) else None
    if (
        not isinstance(source_provenance, dict)
        or set(source_provenance) != {"atlas", "external_threshold", "effort_freeze"}
        or not isinstance(external_provenance, dict)
        or external_provenance.get("schema") != "a2_piper_v23_door_external_torque_threshold_v1"
        or external_provenance.get("status") != "MEASURED_RAW"
        or external_provenance.get("row_count") != 180
    ):
        raise ValueError("v23 D1 capability source freeze external provenance is invalid")
    source_geometry = source_freeze.get("canonical_geometry")
    if (
        not isinstance(source_geometry, dict)
        or source_geometry.get("schema") != _V23_P0_BOUND_CANONICAL_SCHEMA
        or source_geometry.get("cell_id") != _V23_D1_SOURCE_CELL_ID
        or source_geometry.get("geometry_id") != source_freeze.get("source_geometry_id")
        or source_geometry.get("realized_params")
        != {
            "hinge_damping_native": _V23_D1_NATIVE_PARAMS["hinge_damping_native"],
            "hinge_stiffness_native": _V23_D1_NATIVE_PARAMS["hinge_stiffness_native"],
            "hinge_effort_limit_nm": _V23_D1_NATIVE_PARAMS["hinge_effort_limit_nm"],
            "door_weight_kg": _V23_D1_NATIVE_PARAMS["door_weight_kg"],
        }
    ):
        raise ValueError("v23 D1 source canonical geometry is invalid")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 16:
        raise ValueError("v23 D1 bound manifest requires exactly 16 rows")
    row_fields = _V23_P0_BOUND_ROW_FIELDS | {"purpose"}
    scenario_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != row_fields:
            raise ValueError(f"v23 D1 bound row {index} fields are invalid")
        if row.get("purpose") != _V23_D1_BOUND_PURPOSE or row.get("env_id") != index or row.get("episode_index") != 0:
            raise ValueError(f"v23 D1 bound row {index} purpose/env identity is invalid")
        scenario_id = row.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id or scenario_id in scenario_ids:
            raise ValueError(f"v23 D1 bound row {index} scenario identity is invalid")
        scenario_ids.add(scenario_id)
        if row.get("plain_prefix_id") != f"{scenario_id}:{topology}:env{index}:episode0":
            raise ValueError(f"v23 D1 bound row {index} plain_prefix_id is invalid")
        if row.get("topology") != topology or row.get("seed") != 0:
            raise ValueError(f"v23 D1 bound row {index} policy identity is invalid")
        source_identity = row.get("source_identity")
        if (
            not isinstance(source_identity, dict)
            or set(source_identity) != _V23_P0_BOUND_SOURCE_IDENTITY_FIELDS
            or source_identity.get("source_manifest_path") != source_path_value
            or source_identity.get("source_role") != "historical_prior_only"
            or not isinstance(source_identity.get("source_row"), dict)
            or set(source_identity["source_row"]) != _V23_P0_PLAIN_SOURCE_FIELDS
            or source_identity["source_row"].get("scenario_id") != scenario_id
        ):
            raise ValueError(f"v23 D1 bound row {index} source identity is invalid")
        if (
            row.get("cell_id") != _V23_D1_SOURCE_CELL_ID
            or row.get("geometry_id") != source_freeze["source_geometry_id"]
            or row.get("canonical_geometry") != source_geometry
            or row.get("requested_params") != _V23_D1_REQUESTED_PARAMS
            or row.get("realized_params") != source_geometry["realized_params"]
        ):
            raise ValueError(f"v23 D1 bound row {index} A0 geometry/dynamics are invalid")
        facts = source_geometry.get("local_facts")
        if not isinstance(facts, dict):
            raise ValueError("v23 D1 source canonical geometry local_facts are missing")
        for field in ("door_width_m", "door_height_m", "handle_height_m", "handle_width_m", "handle_type", "door_open_lr", "door_open_io"):
            if row.get(field) != facts[field]:
                raise ValueError(f"v23 D1 bound row {index}.{field} disagrees with A0 geometry")
        for field in ("hinge_axis_local", "hinge_anchor_local"):
            if row.get(field) != facts[field]:
                raise ValueError(f"v23 D1 bound row {index}.{field} disagrees with A0 geometry")
    if len(scenario_ids) != 16:
        raise ValueError("v23 D1 bound scenarios must cover plain16 exactly")
    return payload, path


def _v23_p0_bound_manifest_payload(env_config) -> tuple[dict, Path]:
    """Read one strict bound plain16 manifest for high-level spawn replacement."""

    if env_config.get(_V23_P0_BOUND_MANIFEST_FLAG) is not True:
        raise ValueError(
            f"v23 P0 bound selector requires env.config.{_V23_P0_BOUND_MANIFEST_FLAG}=true"
        )
    path_value = env_config.get(_V23_P0_BOUND_MANIFEST_PATH_KEY)
    if not isinstance(path_value, (str, Path)) or not str(path_value):
        raise ValueError(
            f"v23 P0 bound selector requires {_V23_P0_BOUND_MANIFEST_PATH_KEY}"
        )
    path = Path(path_value)
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError(
            "v23 P0 bound plain16 manifest must be an absolute regular non-symlink file: "
            f"{path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"v23 P0 bound plain16 manifest is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("v23 P0 bound plain16 manifest root must be an object")
    if payload.get("schema") == _V23_D1_BOUND_MANIFEST_SCHEMA:
        return _v23_d1_bound_manifest_payload(payload, path, env_config)
    _v23_p0_reject_integrity_fields(payload)
    expected_keys = {
        "schema",
        "status",
        "selector_mode",
        "topology",
        "source_manifest_path",
        "source_role",
        "canonical_geometry_schema",
        "rows",
    }
    if set(payload) != expected_keys:
        raise ValueError(
            "v23 P0 bound plain16 manifest fields must be exactly "
            f"{sorted(expected_keys)}; got {sorted(payload)}"
        )
    if (
        payload.get("schema") != _V23_P0_BOUND_MANIFEST_SCHEMA
        or payload.get("status") != "BOUND_PLAIN16"
        or payload.get("selector_mode") != _V23_P0_BOUND_SELECTOR_MODE
        or payload.get("canonical_geometry_schema") != _V23_P0_BOUND_CANONICAL_SCHEMA
    ):
        raise ValueError("v23 P0 bound plain16 manifest schema/status/mode is invalid")
    topology = payload.get("topology")
    if topology not in _V23_P0_PLAIN_TOPOLOGIES:
        raise ValueError("v23 P0 bound plain16 topology must be canonical16 or heavy16")
    if env_config.get(_V23_P0_PLAIN_TOPOLOGY_KEY) != topology:
        raise ValueError("v23 P0 bound plain16 topology disagrees with env.config")
    source_path_value = payload.get("source_manifest_path")
    if not isinstance(source_path_value, str) or not source_path_value:
        raise ValueError("v23 P0 bound plain16 manifest requires source_manifest_path")
    source_path = Path(source_path_value)
    if not source_path.is_absolute() or not source_path.is_file() or source_path.is_symlink():
        raise ValueError("v23 P0 bound source_manifest_path must be an absolute regular file")
    if payload.get("source_role") != "historical_prior_only":
        raise ValueError("v23 P0 bound source_role must be historical_prior_only")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 16:
        raise ValueError("v23 P0 bound plain16 manifest requires exactly 16 rows")
    selected_cell = None
    selected_geometry_id = None
    scenario_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != _V23_P0_BOUND_ROW_FIELDS:
            raise ValueError(
                f"v23 P0 bound row {index} fields must be exactly "
                f"{sorted(_V23_P0_BOUND_ROW_FIELDS)}"
            )
        scenario_id = row["scenario_id"]
        if not isinstance(scenario_id, str) or not scenario_id or scenario_id in scenario_ids:
            raise ValueError(f"v23 P0 bound row {index} has a missing or duplicate scenario_id")
        scenario_ids.add(scenario_id)
        if row["env_id"] != index or row["episode_index"] != 0:
            raise ValueError(f"v23 P0 bound row {index} env/episode identity is not plain16 ordered")
        if row["plain_prefix_id"] != f"{scenario_id}:{topology}:env{index}:episode0":
            raise ValueError(f"v23 P0 bound row {index} plain_prefix_id is not immutable CRN identity")
        if any(not isinstance(row[key], str) or not row[key] for key in ("checkpoint", "config")):
            raise ValueError(f"v23 P0 bound row {index} checkpoint/config identity is invalid")
        if isinstance(row["seed"], bool) or not isinstance(row["seed"], int) or row["seed"] != 0:
            raise ValueError(f"v23 P0 bound row {index} seed must be the fixed integer 0")
        if row["topology"] != topology:
            raise ValueError(f"v23 P0 bound row {index} topology disagrees with the manifest")
        source_identity = row["source_identity"]
        if (
            not isinstance(source_identity, dict)
            or set(source_identity) != _V23_P0_BOUND_SOURCE_IDENTITY_FIELDS
        ):
            raise ValueError(f"v23 P0 bound row {index} source identity fields are invalid")
        source_row = source_identity.get("source_row")
        if (
            source_identity.get("source_manifest_path") != source_path_value
            or source_identity.get("source_role") != "historical_prior_only"
            or not isinstance(source_row, dict)
            or set(source_row) != _V23_P0_PLAIN_SOURCE_FIELDS
            or source_row.get("scenario_id") != scenario_id
        ):
            raise ValueError(f"v23 P0 bound row {index} source identity is not immutable")
        for field in ("handle_height_m", "door_weight_kg", "hinge_force_nm"):
            value = source_row[field]
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(float(value))
                or float(value) <= 0.0
            ):
                raise ValueError(f"v23 P0 bound row {index} source value {field} is invalid")
        canonical = row["canonical_geometry"]
        if (
            not isinstance(canonical, dict)
            or set(canonical)
            != {
                "schema",
                "geometry_id",
                "cell_id",
                "realized_params",
                "local_facts",
                "world_origin_excluded",
                "authority",
            }
        ):
            raise ValueError(f"v23 P0 bound row {index} canonical geometry fields are invalid")
        if (
            canonical["schema"] != _V23_P0_BOUND_CANONICAL_SCHEMA
            or canonical["cell_id"] != row["cell_id"]
            or canonical["geometry_id"] != row["geometry_id"]
            or canonical["world_origin_excluded"] is not True
            or not isinstance(canonical["authority"], str)
            or not canonical["authority"]
        ):
            raise ValueError(f"v23 P0 bound row {index} canonical geometry identity is invalid")
        realized = row["realized_params"]
        if (
            not isinstance(realized, dict)
            or set(realized)
            != {
                "hinge_damping_native",
                "hinge_stiffness_native",
                "hinge_effort_limit_nm",
                "door_weight_kg",
            }
            or realized != canonical["realized_params"]
            or realized != _V23_P0_BOUND_NATIVE_PARAMS
        ):
            raise ValueError(f"v23 P0 bound row {index} realized dynamics are invalid")
        requested = row["requested_params"]
        if (
            not isinstance(requested, dict)
            or set(requested) != set(_V23_P0_BOUND_REQUESTED_PARAMS)
            or requested != _V23_P0_BOUND_REQUESTED_PARAMS
        ):
            raise ValueError(f"v23 P0 bound row {index} requested spawn parameters are invalid")
        damping = realized["hinge_damping_native"]
        if (
            isinstance(damping, bool)
            or not isinstance(damping, Real)
            or not math.isfinite(float(damping))
            or float(damping) < 0.0
        ):
            raise ValueError(f"v23 P0 bound row {index} hinge damping is invalid")
        for field in ("hinge_stiffness_native", "hinge_effort_limit_nm", "door_weight_kg"):
            if (
                isinstance(realized[field], bool)
                or not isinstance(realized[field], Real)
                or not math.isfinite(float(realized[field]))
                or float(realized[field]) <= 0.0
            ):
                raise ValueError(f"v23 P0 bound row {index} realized {field} is invalid")
        local_facts = canonical["local_facts"]
        if not isinstance(local_facts, dict) or set(local_facts) != set(_V23_P0_BOUND_LOCAL_FACTS):
            raise ValueError(f"v23 P0 bound row {index} local facts are incomplete")
        for field in (
            "door_width_m",
            "door_height_m",
            "handle_height_m",
            "handle_width_m",
            "door_open_lr_sign",
            "door_open_io_sign",
        ):
            _v23_p0_bound_float(local_facts[field], _V23_P0_BOUND_LOCAL_FACTS[field], f"row {index}.{field}")
        for field in ("hinge_axis_local", "hinge_anchor_local"):
            _v23_p0_bound_vector(
                local_facts[field], _V23_P0_BOUND_LOCAL_FACTS[field], f"row {index}.{field}"
            )
        for field in ("handle_type", "door_open_lr", "door_open_io"):
            if local_facts[field] != _V23_P0_BOUND_LOCAL_FACTS[field]:
                raise ValueError(f"v23 P0 bound row {index}.{field} disagrees with canonical geometry")
        for field in (
            "door_width_m",
            "door_height_m",
            "handle_height_m",
            "handle_width_m",
            "handle_type",
            "door_open_lr",
            "door_open_io",
        ):
            if row[field] != local_facts[field]:
                raise ValueError(f"v23 P0 bound row {index}.{field} disagrees with canonical geometry")
        for field in ("hinge_axis_local", "hinge_anchor_local"):
            _v23_p0_bound_vector(row[field], local_facts[field], f"row {index}.{field}")
        if selected_cell is None:
            selected_cell = row["cell_id"]
            selected_geometry_id = row["geometry_id"]
        elif row["cell_id"] != selected_cell or row["geometry_id"] != selected_geometry_id:
            raise ValueError("v23 P0 bound plain16 rows must select one canonical atlas cell")
    return payload, path


def _apply_v23_p0_bound_plain16_spawn_config(
    num_envs: int,
    payload: Mapping[str, Any],
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Apply every registered bound geometry/dynamics field via high-level cfg replacement."""

    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs != 16:
        raise ValueError("v23 P0 bound plain16 topology requires num_envs=16")
    rows = payload.get("rows") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list) or len(rows) != num_envs:
        raise ValueError("v23 P0 bound plain16 spawn config requires exactly 16 rows")
    base = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    if not isinstance(base, dict) or "door" not in base:
        raise ValueError("v23 P0 bound plain16 selector requires a door TaskObjCfgDict")
    door_cfg = base["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("v23 P0 bound plain16 selector requires MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("v23 P0 bound plain16 selector requires non-empty assets_cfg")
    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("v23 P0 bound plain16 selector base asset must be DoorSpawnerCfg")
    variants = []
    for row in rows:
        requested = row["requested_params"]
        variants.append(
            base_door_cfg.replace(
                rand_door_width=float(row["door_width_m"]),
                rand_door_height=float(row["door_height_m"]),
                rand_door_handle_height=float(row["handle_height_m"]),
                rand_door_handle_width=float(row["handle_width_m"]),
                rand_door_handle_type=row["handle_type"],
                rand_door_open_lr=row["door_open_lr"],
                rand_door_open_io=row["door_open_io"],
                rand_door_weight=float(requested["door_weight_kg"]),
                rand_hinge_drive_max_force=float(requested["hinge_max_force_nm"]),
                rand_hinge_drive_damping=float(requested["hinge_damping_native"]),
                rand_hinge_drive_stiffness=float(requested["hinge_stiffness_native"]),
            )
        )
    return {
        **base,
        "door": door_cfg.replace(
            spawn=spawn_cfg.replace(assets_cfg=variants, random_choice=False)
        ),
    }


def _apply_v23_d1_capability_bound_plain16_spawn_config(
    num_envs: int,
    payload: Mapping[str, Any],
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    if payload.get("schema") != _V23_D1_BOUND_MANIFEST_SCHEMA:
        raise ValueError("v23 D1 spawn helper requires the exact D1 capability-source schema")
    return _apply_v23_p0_bound_plain16_spawn_config(num_envs, payload, task_obj_cfg_dict)


def get_TaskObjCfgDict_for_v23_p0_bound_plain16_manifest(
    num_envs: int,
    env_config,
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    payload, _ = _v23_p0_bound_manifest_payload(env_config)
    if payload.get("schema") == _V23_D1_BOUND_MANIFEST_SCHEMA:
        return _apply_v23_d1_capability_bound_plain16_spawn_config(num_envs, payload, task_obj_cfg_dict)
    return _apply_v23_p0_bound_plain16_spawn_config(num_envs, payload, task_obj_cfg_dict)


def get_TaskObjCfgDict_for_v23_p0_plain_scenario_manifest(
    num_envs: int,
    env_config,
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Select deterministic v23 P0 door variants through high-level replacement."""

    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs != 16:
        raise ValueError("v23 P0 plain scenario topology requires num_envs=16")
    payload, _ = _v23_p0_plain_manifest_payload(env_config)
    base = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    if not isinstance(base, dict) or "door" not in base:
        raise ValueError("v23 P0 plain selector requires a door TaskObjCfgDict")
    door_cfg = base["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("v23 P0 plain selector requires MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("v23 P0 plain selector requires non-empty assets_cfg")
    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("v23 P0 plain selector base asset must be DoorSpawnerCfg")
    bounds = base_door_cfg.door_handle_tblr
    if (
        isinstance(bounds, (str, bytes))
        or not isinstance(bounds, Sequence)
        or len(bounds) != 4
    ):
        raise ValueError("v23 P0 plain selector base door_handle_tblr must have four values")
    upper, lower = float(bounds[0]), float(bounds[1])
    if not math.isfinite(upper) or not math.isfinite(lower) or lower >= upper:
        raise ValueError("v23 P0 plain selector base handle-height bounds are invalid")
    variants = []
    for index, row in enumerate(payload["rows"]):
        height = float(row["handle_height_m"])
        if not lower <= height <= upper:
            raise ValueError(
                f"v23 P0 plain scenario row {index} handle height {height} is outside [{lower}, {upper}]"
            )
        variants.append(
            base_door_cfg.replace(
                rand_door_handle_height=height,
                rand_door_weight=float(row["door_weight_kg"]),
                rand_hinge_drive_max_force=float(row["hinge_force_nm"]),
            )
        )
    result = dict(base)
    result["door"] = door_cfg.replace(
        spawn=spawn_cfg.replace(assets_cfg=variants, random_choice=False)
    )
    return result


def _v23_route_b_render_manifest_payload(env_config) -> tuple[dict, Path]:
    """Read and validate one exact static render16 manifest."""

    if env_config.get(_V23_ROUTE_B_RENDER_ENABLED_KEY) is not True:
        raise ValueError(
            "v23 Route-B render selector requires "
            f"{_V23_ROUTE_B_RENDER_ENABLED_KEY}=true"
        )
    path_value = env_config.get(_V23_ROUTE_B_RENDER_MANIFEST_PATH_KEY)
    if not isinstance(path_value, (str, Path)) or not str(path_value):
        raise ValueError(
            "v23 Route-B render selector requires "
            f"{_V23_ROUTE_B_RENDER_MANIFEST_PATH_KEY}"
        )
    path = Path(path_value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(
            "v23 Route-B render manifest must be an absolute regular non-symlink file: "
            f"{path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"v23 Route-B render manifest is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("v23 Route-B render manifest must be a JSON object")
    if payload.get("schema") != _V23_ROUTE_B_RENDER_MANIFEST_SCHEMA:
        raise ValueError("v23 Route-B render manifest schema is invalid")
    if payload.get("status") != _V23_ROUTE_B_RENDER_MANIFEST_STATUS:
        raise ValueError("v23 Route-B render manifest status must be STATIC_RENDER")
    if payload.get("topology") != _V23_ROUTE_B_RENDER_MANIFEST_TOPOLOGY:
        raise ValueError("v23 Route-B render manifest topology must be render16")
    scenario_id = payload.get("scenario_id")
    if not isinstance(scenario_id, str) or not scenario_id:
        raise ValueError("v23 Route-B render manifest scenario_id must be non-empty")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 16:
        raise ValueError("v23 Route-B render manifest requires exactly 16 rows")
    expected_fields = {"env_id", "scenario_id", *_V23_ROUTE_B_RENDER_SCALAR_FIELDS}
    row_ids = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != expected_fields:
            raise ValueError(f"v23 Route-B render manifest row {index} has invalid fields")
        if row.get("env_id") != index:
            raise ValueError("v23 Route-B render manifest rows must be ordered env0 through env15")
        expected_id = f"{scenario_id}_env{index:02d}"
        if row.get("scenario_id") != expected_id or expected_id in row_ids:
            raise ValueError("v23 Route-B render manifest scenario_ids must be ordered and unique")
        row_ids.add(expected_id)
        for field in _V23_ROUTE_B_RENDER_SCALAR_FIELDS:
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"v23 Route-B render row {index}.{field} must be numeric")
            number = float(value)
            if not math.isfinite(number) or number <= 0.0:
                raise ValueError(f"v23 Route-B render row {index}.{field} must be finite and positive")
    return payload, path


def get_TaskObjCfgDict_for_v23_route_b_render_manifest(
    num_envs: int,
    env_config,
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Bind one static DoorSpawnerCfg variant to each render environment."""

    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs != 16:
        raise ValueError("v23 Route-B render16 topology requires num_envs=16")
    payload, _ = _v23_route_b_render_manifest_payload(env_config)
    base = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    if not isinstance(base, dict) or "door" not in base:
        raise ValueError("v23 Route-B render selector requires a door TaskObjCfgDict")
    door_cfg = base["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("v23 Route-B render selector requires MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("v23 Route-B render selector requires non-empty assets_cfg")
    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("v23 Route-B render selector base asset must be DoorSpawnerCfg")
    bounds = base_door_cfg.door_handle_tblr
    if isinstance(bounds, (str, bytes)) or not isinstance(bounds, Sequence) or len(bounds) != 4:
        raise ValueError("v23 Route-B render selector base door_handle_tblr must have four values")
    upper, lower = float(bounds[0]), float(bounds[1])
    if not math.isfinite(upper) or not math.isfinite(lower) or lower >= upper:
        raise ValueError("v23 Route-B render selector base handle-height bounds are invalid")
    variants = []
    for index, row in enumerate(payload["rows"]):
        height = float(row["handle_height_m"])
        if not lower <= height <= upper:
            raise ValueError(
                f"v23 Route-B render row {index} handle height {height} is outside [{lower}, {upper}]"
            )
        variants.append(
            base_door_cfg.replace(
                rand_door_handle_height=height,
                rand_door_weight=float(row["door_weight_kg"]),
                rand_hinge_drive_max_force=float(row["hinge_max_force_nm"]),
                rand_hinge_drive_damping=float(row["hinge_damping_native"]),
                rand_hinge_drive_stiffness=float(row["hinge_stiffness_native"]),
            )
        )
    if len(variants) != num_envs:
        raise ValueError("v23 Route-B render selector variant count must be exactly 16")
    ordered_spawn_cfg = spawn_cfg.replace(assets_cfg=variants, random_choice=False)
    return {**base, "door": door_cfg.replace(spawn=ordered_spawn_cfg)}


def _v23_d1_sampler_env_config(env_config) -> dict:
    """Validate the additive D1 sampler selector without touching old paths."""

    if env_config.get(_V23_D1_SAMPLER_ENABLED_KEY) is not True:
        raise ValueError(
            f"v23 D1 selector requires env.config.{_V23_D1_SAMPLER_ENABLED_KEY}=true"
        )
    required = (
        _V23_D1_MANIFEST_PATH_KEY,
        _V23_D1_VARIANT_KEY,
        _V23_D1_BUCKET_SEED_KEY,
        _V23_D1_TOTAL_STEPS_KEY,
        _V23_D1_RECEIPT_PATH_KEY,
    )
    missing = [key for key in required if key not in env_config]
    if missing:
        raise ValueError(f"v23 D1 selector requires all explicit fields; missing {missing}")
    manifest_path = env_config[_V23_D1_MANIFEST_PATH_KEY]
    receipt_path = env_config[_V23_D1_RECEIPT_PATH_KEY]
    if not isinstance(manifest_path, (str, Path)) or not str(manifest_path):
        raise ValueError("v23 D1 manifest path must be a non-empty path")
    if not isinstance(receipt_path, (str, Path)) or not str(receipt_path):
        raise ValueError("v23 D1 physics receipt path must be a non-empty path")
    variant = env_config[_V23_D1_VARIANT_KEY]
    if variant not in ("normal", "lite"):
        raise ValueError("v23 D1 variant must be 'normal' or 'lite'")
    seed = env_config[_V23_D1_BUCKET_SEED_KEY]
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("v23 D1 bucket seed must be a non-negative integer")
    total_steps = env_config[_V23_D1_TOTAL_STEPS_KEY]
    if isinstance(total_steps, bool) or not isinstance(total_steps, int) or total_steps not in (10, 2500):
        raise ValueError("v23 D1 total steps must be 10 or 2500")
    global_step = env_config.get(_V23_D1_GLOBAL_STEP_KEY, 0)
    if isinstance(global_step, bool) or not isinstance(global_step, int) or not 0 <= global_step < total_steps:
        raise ValueError("v23 D1 global step must be an absolute step in the configured run")
    return dict(env_config)


def get_TaskObjCfgDict_for_v23_d1_sampler(
    num_envs: int,
    env_config,
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Bind one immutable physics-first D1 row per environment.

    This is an IsaacLab high-level config replacement: every variant is
    materialized through ``DoorSpawnerCfg.replace`` and no USD prim is touched.
    ``rand_door_weight`` is an absolute panel mass at spawn; the optional
    startup event helper below uses IsaacLab's absolute-mass operation with
    inertia recomputation for paths that apply mass after scene creation.
    """

    _v23_d1_sampler_env_config(env_config)
    from gr00t.rl.envs.door.a2_v23_d1_sampler import D1Sampler

    sampler = D1Sampler.from_config(env_config)
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs != sampler.total_envs:
        raise ValueError(
            f"v23 D1 {sampler.total_steps}-step topology requires num_envs={sampler.total_envs}"
        )
    global_step = env_config.get(_V23_D1_GLOBAL_STEP_KEY, 0)
    assignments = sampler.assignments(global_step)
    base = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    if not isinstance(base, dict) or "door" not in base:
        raise ValueError("v23 D1 selector requires a door TaskObjCfgDict")
    door_cfg = base["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("v23 D1 selector requires MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("v23 D1 selector requires non-empty assets_cfg")
    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("v23 D1 selector base asset must be DoorSpawnerCfg")
    variants = []
    for assignment in assignments:
        row = assignment.realized_row
        params = row.realized_params
        variants.append(
            base_door_cfg.replace(
                rand_door_width=row.door_width_m,
                rand_door_height=row.door_height_m,
                rand_door_handle_height=row.handle_height_m,
                rand_door_handle_width=row.handle_width_m,
                rand_door_handle_type=row.handle_type,
                rand_door_open_lr=row.door_open_lr,
                rand_door_open_io=row.door_open_io,
                rand_door_weight=params.door_weight_kg,
                rand_hinge_drive_max_force=params.hinge_effort_limit_nm,
                rand_hinge_drive_damping=params.hinge_damping_native,
                rand_hinge_drive_stiffness=params.hinge_stiffness_native,
            )
        )
    return {
        **base,
        "door": door_cfg.replace(
            spawn=spawn_cfg.replace(assets_cfg=variants, random_choice=False)
        ),
    }


def get_v23_d1_mass_event_cfg(cell_id: str, env_config):
    """Build a high-level startup mass event for absolute mass + inertia recompute.

    The returned ``EventTermCfg`` is intentionally a standalone composition
    helper.  It is not wired into the shared trainer in this revision.
    """

    _v23_d1_sampler_env_config(env_config)
    import isaaclab.envs.mdp as mdp
    from isaaclab.managers import EventTermCfg, SceneEntityCfg
    from gr00t.rl.envs.door.a2_v23_d1_sampler import D1Sampler

    sampler = D1Sampler.from_config(env_config)
    row = sampler.catalog.row(cell_id)
    mass = row.realized_params.door_weight_kg
    return EventTermCfg(
        func=mdp.randomize_rigid_body_mass,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("door", body_names=["door_panel"]),
            "mass_distribution_params": (mass, mass),
            "operation": "abs",
            "distribution": "uniform",
            "recompute_inertia": True,
        },
    )


_V22_MANIFEST_SCHEMA = "a2_piper_base_v22_scenario_manifest_v1"
_V22_MANIFEST_FLAG = "a2_v22_scenario_manifest_enabled"
_V22_MANIFEST_PATH_KEY = "a2_v22_scenario_manifest_path"
_V22_MANIFEST_SHA_KEY = "a2_v22_scenario_manifest_sha256"
_V22_MANIFEST_NAME_KEY = "a2_v22_scenario_manifest_name"
_V22_BUCKET_MIXTURE_KEY = "a2_v22_hinge_bucket_mixture"
_V22_BUCKET_SEED_KEY = "a2_v22_hinge_bucket_seed"
_V22_ROW_FIELDS = (
    "scenario_id",
    "handle_height_m",
    "door_weight_kg",
    "hinge_max_force_nm",
    "hinge_damping_native",
    "hinge_stiffness_native",
    "bucket",
)
_V22_BUCKET_NAMES = ("H0", "H1", "H2", "H3", "H4")
_V22_BUCKET_RANGE_FIELDS = ("damping", "stiffness", "max_force_nm", "mass_kg", "handle_height_m")


def _v22_base_door_cfg(task_obj_cfg_dict: dict):
    if not isinstance(task_obj_cfg_dict, dict) or "door" not in task_obj_cfg_dict:
        raise ValueError("v22 selector requires a door TaskObjCfgDict")
    spawn_cfg = task_obj_cfg_dict["door"].spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg) or not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("v22 selector requires a non-empty MultiAssetSpawnerCfg")
    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("v22 selector base asset must be DoorSpawnerCfg")
    return spawn_cfg, base_door_cfg


def _v22_finite_positive(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"v22 {label} must be a real number, got {value!r}")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"v22 {label} must be finite and positive, got {number!r}")
    return number


def load_v22_scenario_manifest(env_config) -> dict:
    """Load and hash-verify a v22 deterministic scenario manifest."""
    path_value = env_config.get(_V22_MANIFEST_PATH_KEY)
    if not isinstance(path_value, (str, Path)) or not str(path_value):
        raise ValueError(f"v22 scenario selection requires {_V22_MANIFEST_PATH_KEY}")
    path = Path(path_value)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"v22 scenario manifest must be a regular non-symlink file: {path}")
    raw = path.read_bytes()
    expected_sha = env_config.get(_V22_MANIFEST_SHA_KEY)
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise ValueError(f"v22 scenario selection requires {_V22_MANIFEST_SHA_KEY}")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError(f"v22 scenario manifest hash mismatch: {actual_sha} != {expected_sha}")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != _V22_MANIFEST_SCHEMA:
        raise ValueError("v22 scenario manifest schema is invalid")
    expected_name = env_config.get(_V22_MANIFEST_NAME_KEY)
    if expected_name is not None and payload.get("manifest_name") != expected_name:
        raise ValueError(
            f"v22 scenario manifest name mismatch: {payload.get('manifest_name')!r} != {expected_name!r}"
        )
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("v22 scenario manifest requires a non-empty rows list")
    ids = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or any(field not in row for field in _V22_ROW_FIELDS):
            raise ValueError(f"v22 scenario manifest row {index} is missing required fields")
        if not isinstance(row["scenario_id"], str) or not row["scenario_id"]:
            raise ValueError(f"v22 scenario manifest row {index} has an invalid scenario_id")
        if row["scenario_id"] in ids:
            raise ValueError(f"v22 scenario manifest duplicate scenario_id {row['scenario_id']!r}")
        ids.add(row["scenario_id"])
        for field in ("handle_height_m", "door_weight_kg", "hinge_max_force_nm", "hinge_stiffness_native"):
            _v22_finite_positive(row[field], f"{field} in row {index}")
        damping = row["hinge_damping_native"]
        if isinstance(damping, bool) or not isinstance(damping, Real) or not math.isfinite(float(damping)) or float(damping) < 0.0:
            raise ValueError(f"v22 hinge_damping_native in row {index} must be finite and non-negative")
        if row["bucket"] not in _V22_BUCKET_NAMES:
            raise ValueError(f"v22 scenario manifest row {index} bucket {row['bucket']!r} is not registered")
    return payload


def get_TaskObjCfgDict_for_v22_scenario_manifest(
    num_envs: int,
    env_config,
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Bind one deterministic hinge tuple per environment from a signed v22 manifest."""
    payload = load_v22_scenario_manifest(env_config)
    rows = payload["rows"]
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs != len(rows):
        raise ValueError(
            f"v22 scenario manifest requires num_envs={len(rows)}, got {num_envs!r}"
        )
    base = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    spawn_cfg, base_door_cfg = _v22_base_door_cfg(base)
    upper, lower = float(base_door_cfg.door_handle_tblr[0]), float(base_door_cfg.door_handle_tblr[1])
    variants = []
    for row in rows:
        height = float(row["handle_height_m"])
        if not lower <= height <= upper:
            raise ValueError(
                f"v22 scenario {row['scenario_id']} handle height {height} is outside [{lower}, {upper}]"
            )
        variants.append(
            base_door_cfg.replace(
                rand_door_handle_height=height,
                rand_door_weight=float(row["door_weight_kg"]),
                rand_hinge_drive_max_force=float(row["hinge_max_force_nm"]),
                rand_hinge_drive_damping=float(row["hinge_damping_native"]),
                rand_hinge_drive_stiffness=float(row["hinge_stiffness_native"]),
            )
        )
    result = dict(base)
    result["door"] = base["door"].replace(
        spawn=spawn_cfg.replace(assets_cfg=variants, random_choice=False)
    )
    return result


def _validate_v22_bucket_mixture(mixture) -> list[dict]:
    if isinstance(mixture, (str, bytes)) or not isinstance(mixture, Sequence) or not mixture:
        raise TypeError(f"{_V22_BUCKET_MIXTURE_KEY} must be a non-empty sequence of bucket entries")
    validated = []
    total_weight = 0.0
    seen = set()
    for index, entry in enumerate(mixture):
        if not hasattr(entry, "get"):
            raise TypeError(f"{_V22_BUCKET_MIXTURE_KEY}[{index}] must be a mapping")
        name = entry.get("bucket")
        if name not in _V22_BUCKET_NAMES:
            raise ValueError(f"{_V22_BUCKET_MIXTURE_KEY}[{index}] bucket {name!r} is not registered")
        if name in seen:
            raise ValueError(f"{_V22_BUCKET_MIXTURE_KEY} repeats bucket {name!r}")
        seen.add(name)
        weight = entry.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, Real) or not math.isfinite(float(weight)) or float(weight) <= 0.0:
            raise ValueError(f"{_V22_BUCKET_MIXTURE_KEY}[{index}] weight must be finite and positive")
        ranges = {}
        for field in _V22_BUCKET_RANGE_FIELDS:
            bounds = entry.get(field)
            if isinstance(bounds, (str, bytes)) or not isinstance(bounds, Sequence) or len(bounds) != 2:
                raise ValueError(f"{_V22_BUCKET_MIXTURE_KEY}[{index}].{field} must be a two-bound sequence")
            low, high = (float(bound) for bound in bounds)
            if not math.isfinite(low) or not math.isfinite(high) or low > high or low < 0.0:
                raise ValueError(f"{_V22_BUCKET_MIXTURE_KEY}[{index}].{field} bounds are invalid: {bounds!r}")
            ranges[field] = (low, high)
        total_weight += float(weight)
        validated.append({"bucket": name, "weight": float(weight), **ranges})
    if not math.isfinite(total_weight) or total_weight <= 0.0:
        raise ValueError(f"{_V22_BUCKET_MIXTURE_KEY} total weight must be positive")
    for entry in validated:
        entry["normalized_weight"] = entry["weight"] / total_weight
    return validated


def get_TaskObjCfgDict_for_v22_hinge_bucket_mixture(
    num_envs: int,
    env_config,
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Assign each training environment to a frozen H0-H4 bucket with its own hinge ranges."""
    mixture = _validate_v22_bucket_mixture(env_config[_V22_BUCKET_MIXTURE_KEY])
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs < 1:
        raise ValueError(f"v22 bucket mixture requires a positive num_envs, got {num_envs!r}")
    seed = env_config.get(_V22_BUCKET_SEED_KEY)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError(f"{_V22_BUCKET_SEED_KEY} must be a non-negative integer")
    base = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    spawn_cfg, base_door_cfg = _v22_base_door_cfg(base)
    # Deterministic largest-remainder allocation so the realized mixture matches the
    # frozen weights exactly rather than only in expectation.
    exact = [entry["normalized_weight"] * num_envs for entry in mixture]
    counts = [int(math.floor(value)) for value in exact]
    remainder = num_envs - sum(counts)
    order = sorted(range(len(mixture)), key=lambda i: (-(exact[i] - counts[i]), i))
    for position in range(remainder):
        counts[order[position % len(mixture)]] += 1
    assignment = []
    for entry, count in zip(mixture, counts):
        assignment.extend([entry] * count)
    if len(assignment) != num_envs:
        raise ValueError("v22 bucket allocation did not cover every environment")
    np.random.default_rng(seed).shuffle(assignment)
    variants = []
    for entry in assignment:
        height_low, height_high = entry["handle_height_m"]
        base_upper, base_lower = float(base_door_cfg.door_handle_tblr[0]), float(base_door_cfg.door_handle_tblr[1])
        if height_low < base_lower or height_high > base_upper:
            raise ValueError(
                f"v22 bucket {entry['bucket']} handle height range [{height_low}, {height_high}] "
                f"is outside the asset bounds [{base_lower}, {base_upper}]"
            )
        variants.append(
            base_door_cfg.replace(
                door_handle_tblr=(
                    height_high,
                    height_low,
                    base_door_cfg.door_handle_tblr[2],
                    base_door_cfg.door_handle_tblr[3],
                ),
                door_weight=entry["mass_kg"],
                hinge_drive_max_force_range=entry["max_force_nm"],
                hinge_drive_damping_range=entry["damping"],
                hinge_drive_stiffness_range=entry["stiffness"],
            )
        )
    result = dict(base)
    result["door"] = base["door"].replace(
        spawn=spawn_cfg.replace(assets_cfg=variants, random_choice=False)
    )
    return result


def _build_eval_door_handle_height_grid(
    bounds: Sequence[Real], num_envs: int, door_handle_tblr: Sequence[Real]
) -> tuple[float, ...]:
    """Validate eval handle-height bounds and return an inclusive env-ordered grid."""
    if isinstance(bounds, (str, bytes)) or not isinstance(bounds, Sequence):
        raise TypeError(
            "a2_eval_door_handle_height_linspace must be a two-bound numeric sequence"
        )
    if len(bounds) != 2:
        raise ValueError(
            "a2_eval_door_handle_height_linspace must contain exactly two bounds"
        )
    if isinstance(num_envs, bool) or not isinstance(num_envs, int):
        raise TypeError(f"num_envs must be an integer, got {num_envs!r}")
    if num_envs < 2:
        raise ValueError(f"num_envs must be >= 2 for an endpoint grid, got {num_envs}")
    if any(isinstance(bound, bool) or not isinstance(bound, Real) for bound in bounds):
        raise TypeError(
            "a2_eval_door_handle_height_linspace bounds must be real numbers"
        )

    low, high = (float(bound) for bound in bounds)
    if not math.isfinite(low) or not math.isfinite(high):
        raise ValueError(
            "a2_eval_door_handle_height_linspace bounds must be finite"
        )
    if low >= high:
        raise ValueError(
            "a2_eval_door_handle_height_linspace requires low < high"
        )

    if (
        isinstance(door_handle_tblr, (str, bytes))
        or not isinstance(door_handle_tblr, Sequence)
        or len(door_handle_tblr) != 4
    ):
        raise ValueError(
            "door_handle_tblr must contain four values, "
            f"got {door_handle_tblr!r}"
        )
    if any(
        isinstance(bound, bool) or not isinstance(bound, Real)
        for bound in door_handle_tblr[:2]
    ):
        raise TypeError("door_handle_tblr height bounds must be real numbers")
    upper, lower = (float(bound) for bound in door_handle_tblr[:2])
    if not math.isfinite(upper) or not math.isfinite(lower) or lower >= upper:
        raise ValueError(
            "door_handle_tblr height bounds are invalid: "
            f"{door_handle_tblr!r}"
        )
    if low < lower or high > upper:
        raise ValueError(
            "a2_eval_door_handle_height_linspace must stay within "
            f"door_handle_tblr height bounds [{lower}, {upper}], got [{low}, {high}]"
        )

    grid = tuple(float(value) for value in np.linspace(low, high, num_envs))
    if (
        len(grid) != num_envs
        or grid[0] != low
        or grid[-1] != high
        or any(grid[index] >= grid[index + 1] for index in range(len(grid) - 1))
    ):
        raise ValueError(
            "a2_eval_door_handle_height_linspace produced an invalid count/order grid"
        )
    return grid


def _validate_door_weight_range(value: Sequence[Real]) -> tuple[float, float]:
    """Validate an explicit per-version door-weight range before spawning."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(
            "a2_door_weight_range must be a two-bound numeric sequence"
        )
    if len(value) != 2:
        raise ValueError("a2_door_weight_range must contain exactly two bounds")
    if any(isinstance(bound, bool) or not isinstance(bound, Real) for bound in value):
        raise TypeError("a2_door_weight_range bounds must be real numbers")
    low, high = (float(bound) for bound in value)
    if not math.isfinite(low) or not math.isfinite(high):
        raise ValueError("a2_door_weight_range bounds must be finite")
    if low <= 0.0 or high <= 0.0 or low >= high:
        raise ValueError(
            "a2_door_weight_range requires positive bounds with low < high"
        )
    return low, high


def _validate_eval_door_handle_height_weight_pairs(
    pairs: Sequence[Sequence[Real]],
    num_envs: int,
    door_handle_tblr: Sequence[Real],
    door_weight_range: Sequence[Real],
) -> tuple[tuple[float, float], ...]:
    """Validate one explicit handle-height and door-weight pair per eval env."""
    if isinstance(num_envs, bool) or not isinstance(num_envs, int):
        raise TypeError(f"num_envs must be an integer, got {num_envs!r}")
    if num_envs < 1:
        raise ValueError(f"num_envs must be positive, got {num_envs}")
    if isinstance(pairs, (str, bytes)) or not isinstance(pairs, Sequence):
        raise TypeError(
            "a2_eval_door_handle_height_weight_pairs must be a sequence of pairs"
        )
    if len(pairs) != num_envs:
        raise ValueError(
            "a2_eval_door_handle_height_weight_pairs must contain exactly one "
            f"pair per environment: expected {num_envs}, got {len(pairs)}"
        )

    if (
        isinstance(door_handle_tblr, (str, bytes))
        or not isinstance(door_handle_tblr, Sequence)
        or len(door_handle_tblr) != 4
    ):
        raise ValueError(
            "door_handle_tblr must contain four values, "
            f"got {door_handle_tblr!r}"
        )
    if any(
        isinstance(bound, bool) or not isinstance(bound, Real)
        for bound in door_handle_tblr[:2]
    ):
        raise TypeError("door_handle_tblr height bounds must be real numbers")
    height_upper, height_lower = (
        float(bound) for bound in door_handle_tblr[:2]
    )
    if (
        not math.isfinite(height_upper)
        or not math.isfinite(height_lower)
        or height_lower >= height_upper
    ):
        raise ValueError(
            "door_handle_tblr height bounds are invalid: "
            f"{door_handle_tblr!r}"
        )
    weight_lower, weight_upper = _validate_door_weight_range(door_weight_range)

    validated = []
    for index, pair in enumerate(pairs):
        if isinstance(pair, (str, bytes)) or not isinstance(pair, Sequence):
            raise TypeError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] must be a two-value sequence"
            )
        if len(pair) != 2:
            raise ValueError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] must contain exactly two values"
            )
        if any(
            isinstance(value, bool) or not isinstance(value, Real) for value in pair
        ):
            raise TypeError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] values must be real numbers"
            )
        height, weight = (float(value) for value in pair)
        if not math.isfinite(height) or not math.isfinite(weight):
            raise ValueError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] values must be finite"
            )
        if not height_lower <= height <= height_upper:
            raise ValueError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] height must stay within [{height_lower}, {height_upper}], "
                f"got {height}"
            )
        if not weight_lower <= weight <= weight_upper:
            raise ValueError(
                "a2_eval_door_handle_height_weight_pairs"
                f"[{index}] weight must stay within [{weight_lower}, {weight_upper}], "
                f"got {weight}"
            )
        validated.append((height, weight))
    return tuple(validated)


def _apply_door_weight_range(
    task_obj_cfg_dict: dict, door_weight_range: Sequence[Real]
) -> dict:
    """Apply a validated mass range through high-level immutable config replacement."""
    weight_range = _validate_door_weight_range(door_weight_range)
    if not isinstance(task_obj_cfg_dict, dict) or "door" not in task_obj_cfg_dict:
        raise ValueError("task-object configuration must contain the 'door' object")
    door_cfg = task_obj_cfg_dict["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("door spawn configuration must be MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("door MultiAssetSpawnerCfg.assets_cfg must be non-empty")
    variants = []
    for index, asset_cfg in enumerate(spawn_cfg.assets_cfg):
        if not isinstance(asset_cfg, DoorSpawnerCfg):
            raise TypeError(
                f"door assets_cfg[{index}] must be DoorSpawnerCfg, "
                f"got {type(asset_cfg).__name__}"
            )
        variants.append(asset_cfg.replace(door_weight=weight_range))
    ordered_spawn_cfg = spawn_cfg.replace(assets_cfg=variants)
    result = dict(task_obj_cfg_dict)
    result["door"] = door_cfg.replace(spawn=ordered_spawn_cfg)
    return result


def _validate_eval_door_handle_height_task_obj_cfg(
    task_obj_cfg_dict: dict, expected_heights: Sequence[Real]
) -> dict:
    """Validate the ordered multi-asset task config produced for deterministic eval."""
    if not isinstance(task_obj_cfg_dict, dict):
        raise TypeError(
            f"eval task-object configuration must be a dict, got {type(task_obj_cfg_dict).__name__}"
        )
    if "door" not in task_obj_cfg_dict:
        raise ValueError("eval task-object configuration must contain the 'door' object")

    door_cfg = task_obj_cfg_dict["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("eval door spawn configuration must be MultiAssetSpawnerCfg")
    if spawn_cfg.random_choice is not False:
        raise ValueError("eval door MultiAssetSpawnerCfg.random_choice must be False")
    if not isinstance(spawn_cfg.assets_cfg, list):
        raise TypeError("eval door assets_cfg must be a list")
    if len(spawn_cfg.assets_cfg) != len(expected_heights):
        raise ValueError(
            "eval door grid count mismatch: "
            f"expected {len(expected_heights)}, got {len(spawn_cfg.assets_cfg)}"
        )

    actual_heights = []
    for index, asset_cfg in enumerate(spawn_cfg.assets_cfg):
        if not isinstance(asset_cfg, DoorSpawnerCfg):
            raise TypeError(
                f"eval door assets_cfg[{index}] must be DoorSpawnerCfg, "
                f"got {type(asset_cfg).__name__}"
            )
        height = asset_cfg.rand_door_handle_height
        if isinstance(height, bool) or not isinstance(height, Real):
            raise TypeError(
                f"eval door assets_cfg[{index}].rand_door_handle_height must be real"
            )
        height = float(height)
        if not math.isfinite(height):
            raise ValueError(
                f"eval door assets_cfg[{index}].rand_door_handle_height must be finite"
            )
        actual_heights.append(height)

    expected = tuple(float(height) for height in expected_heights)
    if tuple(actual_heights) != expected:
        raise ValueError(
            "eval door grid order/value mismatch: "
            f"expected {expected!r}, got {tuple(actual_heights)!r}"
        )
    return task_obj_cfg_dict


def get_TaskObjCfgDict_for_eval_door_handle_height_linspace(
    num_envs: int,
    bounds: Sequence[Real],
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Return an ordered per-environment door config for an explicit eval height grid."""
    base_task_obj_cfg_dict = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    if not isinstance(base_task_obj_cfg_dict, dict):
        raise TypeError(
            "TaskObjCfgDict must be a dict, "
            f"got {type(base_task_obj_cfg_dict).__name__}"
        )
    if "door" not in base_task_obj_cfg_dict:
        raise ValueError("TaskObjCfgDict must contain the 'door' object")

    door_cfg = base_task_obj_cfg_dict["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("base door spawn configuration must be MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("base door MultiAssetSpawnerCfg.assets_cfg must be non-empty")

    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("base door assets_cfg[0] must be DoorSpawnerCfg")
    heights = _build_eval_door_handle_height_grid(
        bounds, num_envs, base_door_cfg.door_handle_tblr
    )
    variants = [
        base_door_cfg.replace(rand_door_handle_height=height) for height in heights
    ]
    if len(variants) != num_envs:
        raise ValueError(
            f"eval door variant count mismatch: expected {num_envs}, got {len(variants)}"
        )

    ordered_spawn_cfg = spawn_cfg.replace(assets_cfg=variants, random_choice=False)
    result = dict(base_task_obj_cfg_dict)
    result["door"] = door_cfg.replace(spawn=ordered_spawn_cfg)
    return _validate_eval_door_handle_height_task_obj_cfg(result, heights)


def get_TaskObjCfgDict_for_eval_door_handle_height_weight_pairs(
    num_envs: int,
    pairs: Sequence[Sequence[Real]],
    task_obj_cfg_dict: dict | None = None,
) -> dict:
    """Return ordered deterministic door configs for explicit eval extrema pairs."""
    base_task_obj_cfg_dict = TaskObjCfgDict if task_obj_cfg_dict is None else task_obj_cfg_dict
    if not isinstance(base_task_obj_cfg_dict, dict):
        raise TypeError(
            "TaskObjCfgDict must be a dict, "
            f"got {type(base_task_obj_cfg_dict).__name__}"
        )
    if "door" not in base_task_obj_cfg_dict:
        raise ValueError("TaskObjCfgDict must contain the 'door' object")

    door_cfg = base_task_obj_cfg_dict["door"]
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("base door spawn configuration must be MultiAssetSpawnerCfg")
    if not isinstance(spawn_cfg.assets_cfg, list) or not spawn_cfg.assets_cfg:
        raise ValueError("base door MultiAssetSpawnerCfg.assets_cfg must be non-empty")
    base_door_cfg = spawn_cfg.assets_cfg[0]
    if not isinstance(base_door_cfg, DoorSpawnerCfg):
        raise TypeError("base door assets_cfg[0] must be DoorSpawnerCfg")

    validated_pairs = _validate_eval_door_handle_height_weight_pairs(
        pairs,
        num_envs,
        base_door_cfg.door_handle_tblr,
        base_door_cfg.door_weight,
    )
    variants = [
        base_door_cfg.replace(
            rand_door_handle_height=height,
            rand_door_weight=weight,
        )
        for height, weight in validated_pairs
    ]
    ordered_spawn_cfg = spawn_cfg.replace(
        assets_cfg=variants,
        random_choice=False,
    )
    result = dict(base_task_obj_cfg_dict)
    result["door"] = door_cfg.replace(spawn=ordered_spawn_cfg)
    return result


def get_TaskObjCfgDict_for_door_config(num_envs: int, env_config) -> dict:
    """Compose explicit version selectors with the deterministic eval height hook."""
    if isinstance(env_config, (str, bytes)) or not hasattr(env_config, "__contains__"):
        raise TypeError("env_config must be a mapping-like configuration")
    v26_handedness_key = "a2_v26_door_open_lr"
    v26_handedness = env_config.get(v26_handedness_key)
    if v26_handedness is not None:
        if v26_handedness not in ("bilateral", "left", "right"):
            raise ValueError(
                f"env.config.{v26_handedness_key} must be 'bilateral', 'left', or 'right'"
            )
        if env_config.get("a2_v25_door_open_lr") is not None:
            raise ValueError("v26 and v25 handedness selectors are mutually exclusive")
        if any(
            env_config.get(key) is True
            for key in (
                "a2_v23_d1_sampler_enabled",
                _V23_P0_PLAIN_MANIFEST_FLAG,
                _V23_P0_BOUND_MANIFEST_FLAG,
                _V21B_SIGNED_PROBE_FLAG,
                _V22_MANIFEST_FLAG,
            )
        ) or env_config.get(_V22_BUCKET_MIXTURE_KEY) is not None:
            raise ValueError("v26 door distribution cannot be combined with a historical scenario selector")
        if "a2_eval_door_handle_height_linspace" in env_config or "a2_eval_door_handle_height_weight_pairs" in env_config:
            raise ValueError("v26 training distribution cannot be combined with an eval geometry selector")

        permutation_seed = env_config.get("a2_v26_side_permutation_seed")
        if isinstance(permutation_seed, bool) or not isinstance(permutation_seed, int):
            raise TypeError("env.config.a2_v26_side_permutation_seed must be an integer")
        if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs <= 0:
            raise ValueError("v26 door distribution requires a positive integer num_envs")
        if v26_handedness == "bilateral" and num_envs % 2 != 0:
            raise ValueError("v26 bilateral door distribution requires an even num_envs")

        def _range_pair(key: str, *, positive: bool) -> tuple[float, float]:
            value = env_config.get(key)
            if (
                isinstance(value, (str, bytes))
                or not isinstance(value, Sequence)
                or len(value) != 2
                or any(isinstance(bound, bool) or not isinstance(bound, Real) for bound in value)
            ):
                raise TypeError(f"env.config.{key} must contain two real bounds")
            low, high = float(value[0]), float(value[1])
            if not math.isfinite(low) or not math.isfinite(high) or low >= high:
                raise ValueError(f"env.config.{key} must be finite and strictly ordered")
            if positive and low <= 0.0:
                raise ValueError(f"env.config.{key} must stay positive")
            return low, high

        handle_height_low, handle_height_high = _range_pair(
            "a2_v26_door_handle_height_range", positive=True
        )
        door_weight_low, door_weight_high = _range_pair(
            "a2_v26_door_weight_range", positive=True
        )

        if v26_handedness == "bilateral":
            sides = np.asarray(
                ["left"] * (num_envs // 2) + ["right"] * (num_envs // 2),
                dtype=object,
            )
            sides = sides[np.random.default_rng(permutation_seed).permutation(num_envs)].tolist()
        else:
            sides = [v26_handedness] * num_envs

        door_cfg = TaskObjCfgDict["door"]
        spawn_cfg = door_cfg.spawn
        base_door_cfg = spawn_cfg.assets_cfg[0]
        if not isinstance(base_door_cfg, DoorSpawnerCfg):
            raise TypeError("v26 base door asset must be DoorSpawnerCfg")
        variants = [
            base_door_cfg.replace(
                door_open_lr=[side],
                door_open_io=["out"],
                door_handle_tblr=(
                    handle_height_high,
                    handle_height_low,
                    base_door_cfg.door_handle_tblr[2],
                    base_door_cfg.door_handle_tblr[3],
                ),
                door_weight=(door_weight_low, door_weight_high),
                rand_door_open_lr=side,
                rand_door_open_io="out",
            )
            for side in sides
        ]
        return {
            **TaskObjCfgDict,
            "door": door_cfg.replace(
                spawn=spawn_cfg.replace(assets_cfg=variants, random_choice=False)
            ),
        }
    v25_handedness_key = "a2_v25_door_open_lr"
    v25_handedness = env_config.get(v25_handedness_key)
    if v25_handedness is not None:
        if isinstance(v25_handedness, str):
            if v25_handedness not in ("left", "right"):
                raise ValueError(
                    f"env.config.{v25_handedness_key} must be 'left', 'right', "
                    "or [left, right]"
                )
            v25_handedness_options = [v25_handedness]
            v25_fixed_handedness = v25_handedness
        elif isinstance(v25_handedness, Sequence):
            v25_handedness_options = list(v25_handedness)
            if v25_handedness_options != ["left", "right"]:
                raise ValueError(
                    f"env.config.{v25_handedness_key} mixed mode must be exactly "
                    "[left, right]"
                )
            v25_fixed_handedness = None
        else:
            raise ValueError(
                f"env.config.{v25_handedness_key} must be 'left', 'right', "
                "or [left, right]"
            )
        if any(
            env_config.get(key) is True
            for key in (
                "a2_v23_d1_sampler_enabled",
                _V23_P0_PLAIN_MANIFEST_FLAG,
                _V23_P0_BOUND_MANIFEST_FLAG,
                _V21B_SIGNED_PROBE_FLAG,
                _V22_MANIFEST_FLAG,
            )
        ) or env_config.get(_V22_BUCKET_MIXTURE_KEY) is not None:
            raise ValueError(
                "v25 deterministic handedness cannot be combined with an inherited "
                "scenario selector"
            )
    if env_config.get("a2_v23_d1_sampler_enabled") is True:
        if any(
            env_config.get(key) is True
            for key in (
                _V23_P0_PLAIN_MANIFEST_FLAG,
                _V23_P0_BOUND_MANIFEST_FLAG,
                _V21B_SIGNED_PROBE_FLAG,
                _V22_MANIFEST_FLAG,
            )
        ):
            raise ValueError("v23 D1 sampler selector cannot be combined with another scenario selector")
        return get_TaskObjCfgDict_for_v23_d1_sampler(num_envs, env_config)
    v23_bound_fields_present = any(
        key in env_config
        for key in (
            _V23_P0_BOUND_MANIFEST_FLAG,
            _V23_P0_BOUND_MANIFEST_PATH_KEY,
        )
    )
    if v23_bound_fields_present:
        if env_config.get(_V23_P0_BOUND_MANIFEST_FLAG) is not True:
            raise ValueError(
                "v23 P0 bound selector fields require "
                f"env.config.{_V23_P0_BOUND_MANIFEST_FLAG}=true"
            )
        if env_config.get(_V21B_SIGNED_PROBE_FLAG) is True:
            raise ValueError(
                "v23 P0 bound selector and signed v21-B selector are mutually exclusive"
            )
        return get_TaskObjCfgDict_for_v23_p0_bound_plain16_manifest(num_envs, env_config)
    v23_plain_fields_present = any(
        key in env_config
        for key in (
            _V23_P0_PLAIN_MANIFEST_FLAG,
            _V23_P0_PLAIN_MANIFEST_PATH_KEY,
            _V23_P0_PLAIN_TOPOLOGY_KEY,
        )
    )
    if v23_plain_fields_present:
        if env_config.get(_V23_P0_PLAIN_MANIFEST_FLAG) is not True:
            raise ValueError(
                "v23 P0 plain selector fields require "
                f"env.config.{_V23_P0_PLAIN_MANIFEST_FLAG}=true"
            )
        if env_config.get(_V21B_SIGNED_PROBE_FLAG) is True:
            raise ValueError(
                "v23 P0 plain selector and signed v21-B selector are mutually exclusive"
            )
        return get_TaskObjCfgDict_for_v23_p0_plain_scenario_manifest(num_envs, env_config)
    if env_config.get(_V21B_SIGNED_PROBE_FLAG) is True:
        return get_TaskObjCfgDict_for_v21B_scenario_manifest(num_envs, env_config)
    if env_config.get(_V22_MANIFEST_FLAG) is True:
        if env_config.get(_V22_BUCKET_MIXTURE_KEY) is not None:
            raise ValueError(
                f"{_V22_MANIFEST_FLAG} and {_V22_BUCKET_MIXTURE_KEY} are mutually exclusive"
            )
        return get_TaskObjCfgDict_for_v22_scenario_manifest(num_envs, env_config)
    if env_config.get(_V22_BUCKET_MIXTURE_KEY) is not None:
        return get_TaskObjCfgDict_for_v22_hinge_bucket_mixture(num_envs, env_config)
    height_grid_key = "a2_eval_door_handle_height_linspace"
    height_weight_pairs_key = "a2_eval_door_handle_height_weight_pairs"
    if height_grid_key in env_config and height_weight_pairs_key in env_config:
        raise ValueError(
            f"{height_grid_key} and {height_weight_pairs_key} are mutually exclusive"
        )
    result = TaskObjCfgDict
    if "a2_door_weight_range" in env_config:
        result = _apply_door_weight_range(result, env_config["a2_door_weight_range"])
    if height_weight_pairs_key in env_config:
        result = get_TaskObjCfgDict_for_eval_door_handle_height_weight_pairs(
            num_envs,
            env_config[height_weight_pairs_key],
            task_obj_cfg_dict=result,
        )
    elif height_grid_key in env_config:
        result = get_TaskObjCfgDict_for_eval_door_handle_height_linspace(
            num_envs,
            env_config[height_grid_key],
            task_obj_cfg_dict=result,
        )
    if v25_handedness is not None:
        door_cfg = result["door"]
        spawn_cfg = door_cfg.spawn
        assets_cfg = [
            asset_cfg.replace(
                door_open_lr=v25_handedness_options,
                door_open_io=["out"],
                rand_door_open_lr=v25_fixed_handedness,
                rand_door_open_io="out",
            )
            for asset_cfg in spawn_cfg.assets_cfg
        ]
        result = {
            **result,
            "door": door_cfg.replace(
                spawn=spawn_cfg.replace(assets_cfg=assets_cfg, random_choice=False)
            ),
        }
    return result
door_spawner_cfg = DoorSpawnerCfg(
    func=spawn_door,
    articulation_props=sim_utils.ArticulationRootPropertiesCfg(
        enabled_self_collisions=True,
        solver_position_iteration_count=4,
        solver_velocity_iteration_count=4,
        fix_root_link=True,
    ),
    activate_contact_sensors=True,
    build_latch=True,
    add_floors=True,
    door_open_lr=["right"],
    door_open_io=["out"],
    door_handle_tblr=(1.10, 0.80, 0.08, 0.15),
    door_weight=(80.0, 120.0),
    hinge_drive_max_force_range=(2.5, 12.0),
    handle_drive_max_force_range=(1.0, 3.0),
    randomize_material=True,
    use_preloaded_materials=True,
    preloaded_materials_num_transform=20,
    preloaded_materials_num_color=100,
    dynamic_material_randomization=False,
    dynamic_material_randomization_interval=1.0,
)

multi_spawner_cfg = sim_utils.MultiAssetSpawnerCfg(
    assets_cfg=[door_spawner_cfg] * 4096,
    random_choice=False,
    activate_contact_sensors=True,
    rigid_props=sim_utils.RigidBodyPropertiesCfg(
        disable_gravity=False,
        retain_accelerations=False,
        linear_damping=0.0,
        angular_damping=0.0,
        max_linear_velocity=1000.0,
        max_angular_velocity=1000.0,
        max_depenetration_velocity=1.0,
    ),
)

TaskObjCfgDict = {
    "door": ArticulationCfg(
        spawn=multi_spawner_cfg,
        init_state=ArticulationCfg.InitialStateCfg(
            pos=(0.0, 0.0, 0.0),
            rot=(1.0, 0.0, 0.0, 0.0),
            joint_pos={
                ".*hinge.*": 0.0,
                ".*handle.*": 0.0,
                ".*latch.*": 0.0,
            },
            joint_vel={".*": 0.0},
        ),
        soft_joint_pos_limit_factor=0.9,
        actuators={
            "hinge": ImplicitActuatorCfg(
                joint_names_expr=[".*hinge.*"],
                velocity_limit_sim=100.0,
                stiffness=None,
                damping=None,
            ),
            "handle": ImplicitActuatorCfg(
                joint_names_expr=[".*handle.*"],
                velocity_limit_sim=100.0,
                stiffness=None,
                damping=None,
            ),
        },
    )
}
