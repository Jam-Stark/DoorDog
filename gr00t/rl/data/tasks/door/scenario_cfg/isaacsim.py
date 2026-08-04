# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import logging
import hashlib
import json
import math
from collections.abc import Sequence
from numbers import Real
from pathlib import Path

logging.getLogger("asyncio").setLevel(logging.WARNING)

import isaaclab.sim as sim_utils
import numpy as np
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg

from gr00t.rl.isaac_utils.playground.env_rand.door import DoorSpawnerCfg, spawn_door


_V21B_MANIFEST_SCHEMA = "a2_piper_base_v21B_heavy16_manifest_v1"
_V21B_SIGNED_PROBE_FLAG = "a2_v21B_signed_probe_scenarios_enabled"
_PULL_P1_CENTRAL_FIXTURE_FLAG = "a2_pull_p1_central_fixture_enabled"
_PULL_P1_CENTRAL_FIXTURE = {
    "rand_door_width": 0.95,
    "rand_door_height": 2.05,
    "rand_door_handle_height": 0.95,
    "rand_door_handle_width": 0.115,
    "rand_door_weight": 120.0,
    "rand_axle_length": 0.195,
    "rand_handle_length": 0.125,
    "rand_hook_length": 0.050,
    "rand_handle_radius": 0.013,
    "rand_spawn_hook": True,
    "rand_hinge_drive_max_force": 7.25,
    "rand_hinge_drive_stiffness": 5.5,
    "rand_handle_drive_max_force": 2.0,
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


def _apply_door_open_io(base_task_obj_cfg_dict: dict, door_open_io: str) -> dict:
    """Return a deterministic IO-selected door spawner without mutating shared push assets."""

    if door_open_io not in ("in", "out"):
        raise ValueError(f"a2_pull_door_open_io must be 'in' or 'out'; got {door_open_io!r}")
    door_cfg = base_task_obj_cfg_dict.get("door")
    if not isinstance(door_cfg, ArticulationCfg):
        raise TypeError("base task-object door config must be ArticulationCfg")
    spawn_cfg = door_cfg.spawn
    if not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg):
        raise TypeError("base door spawn config must be MultiAssetSpawnerCfg")
    variants = []
    for asset_cfg in spawn_cfg.assets_cfg:
        if not isinstance(asset_cfg, DoorSpawnerCfg):
            raise TypeError("base door assets must be DoorSpawnerCfg")
        variants.append(
            asset_cfg.replace(
                door_open_io=[door_open_io],
                rand_door_open_io=door_open_io,
            )
        )
    result = dict(base_task_obj_cfg_dict)
    result["door"] = door_cfg.replace(
        spawn=spawn_cfg.replace(assets_cfg=variants, random_choice=False)
    )
    return result


def _apply_pull_p1_central_fixture(
    base_task_obj_cfg_dict: dict,
    *,
    num_envs: int,
) -> dict:
    """Materialize the amended P1 central fixture through high-level cfg replacement."""

    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs != 1:
        raise ValueError("pull P1 central fixture requires exactly one environment")
    door_cfg = base_task_obj_cfg_dict.get("door")
    if not isinstance(door_cfg, ArticulationCfg):
        raise TypeError("pull P1 central fixture requires an ArticulationCfg door")
    spawn_cfg = door_cfg.spawn
    if (
        not isinstance(spawn_cfg, sim_utils.MultiAssetSpawnerCfg)
        or not isinstance(spawn_cfg.assets_cfg, list)
        or not spawn_cfg.assets_cfg
    ):
        raise TypeError("pull P1 central fixture requires non-empty MultiAssetSpawnerCfg assets")
    base_asset = spawn_cfg.assets_cfg[0]
    if not isinstance(base_asset, DoorSpawnerCfg):
        raise TypeError("pull P1 central fixture base asset must be DoorSpawnerCfg")
    central_asset = base_asset.replace(**_PULL_P1_CENTRAL_FIXTURE)
    result = dict(base_task_obj_cfg_dict)
    result["door"] = door_cfg.replace(
        spawn=spawn_cfg.replace(assets_cfg=[central_asset], random_choice=False)
    )
    return result


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
    if env_config.get(_V21B_SIGNED_PROBE_FLAG) is True:
        return get_TaskObjCfgDict_for_v21B_scenario_manifest(num_envs, env_config)
    height_grid_key = "a2_eval_door_handle_height_linspace"
    height_weight_pairs_key = "a2_eval_door_handle_height_weight_pairs"
    if height_grid_key in env_config and height_weight_pairs_key in env_config:
        raise ValueError(
            f"{height_grid_key} and {height_weight_pairs_key} are mutually exclusive"
        )
    result = TaskObjCfgDict
    if "a2_pull_door_open_io" in env_config:
        result = _apply_door_open_io(result, env_config["a2_pull_door_open_io"])
    if "a2_door_weight_range" in env_config:
        result = _apply_door_weight_range(result, env_config["a2_door_weight_range"])
    central_fixture = env_config.get(_PULL_P1_CENTRAL_FIXTURE_FLAG, False)
    if not isinstance(central_fixture, bool):
        raise TypeError(f"{_PULL_P1_CENTRAL_FIXTURE_FLAG} must be bool")
    if central_fixture:
        result = _apply_pull_p1_central_fixture(result, num_envs=num_envs)
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
