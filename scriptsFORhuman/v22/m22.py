"""base_v22 Route A (plan §14) — canonical16 checkpoint evaluation.

The default ``wave1`` profile preserves the original G1/G2 evaluation.  The
``wave23`` profile evaluates G3/G4/G5/G6 on four GPU-serial lanes.  Every row is
a strict first-episode canonical16 run that
binds the signed v21-B scenario manifest selector (the canonical16 contract on
this codebase) with the v22 evidence exporter.  The controller fails fast: a
nonzero exit, a post-exit validation failure, or a stale admission chain stops
scheduling immediately; no row is retried or skipped silently.

Modes:
  build                     validate admission + checkpoints, write the immutable
                            manifest, queue, and runtime plan under ROUTE_A_ROOT.
  run [--only-row ROW_ID]   execute the lanes; rows with a sealed ROW_PASS
                            receipt are skipped, anything else in a row dir is
                            refused (no overwrite).
  validate-row ROW_ID       re-run post-exit validation for one completed row.
  index                     fold all sealed row receipts into
                            V22_ROUTE_A_EVIDENCE_INDEX.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._v22_common import (
    PYTHON_BIN,
    REPO_ROOT,
    V22_CELL_GPU,
    V22_CELL_SEED,
    V22_LOCK_ROOT,
    V22_PLAN_ID,
    V22_EXECUTION_ID,
    V22_THETA_SEND_RAD,
    V22_TRAINING_ROOT,
    V22Error,
    artifact_payload,
    canonical_json_bytes,
    digest,
    git_identity,
    quantile,
    read_json,
    read_yaml,
    require_gpu,
    sha256_file,
    write_json,
)
from .formal_launcher import REQUIRED_LOCKS, load_admission

# ---------------------------------------------------------------------------
# Route-A profiles (plan §14; physical GPU assignment is launch-time state)
# ---------------------------------------------------------------------------

ROUTE_A_ROOT = REPO_ROOT / "logs_eval/base_v22/postformal_20260806_route_a"
ROUTE_A_CELLS = ("G1", "G2")
ROUTE_A_GPU_BY_CELL = {"G1": 0, "G2": 1}
ROUTE_A_STEPS = tuple(range(250, 2501, 250))
ROUTE_A_TOPOLOGY = "canonical16"
ROUTE_A_NUM_ENVS = 16
ROUTE_A_EVAL_EPISODES = 16

SCENARIO_MANIFEST_PATH = (
    REPO_ROOT / "logs_eval/base_v21B/preformal_20260802_r10/V21B_HEAVY16_MANIFEST.json"
)
SCENARIO_MANIFEST_SCHEMA = "a2_piper_base_v21B_heavy16_manifest_v1"

MANIFEST_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_MANIFEST.json"
QUEUE_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_QUEUE.json"
RUNTIME_PLAN_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_RUNTIME_PLAN.json"
GPU_EVIDENCE_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_GPU_EVIDENCE.json"
FAILURE_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_FAILURE.json"
TERMINAL_STATUS_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_TERMINAL_STATUS.json"
EVIDENCE_INDEX_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_EVIDENCE_INDEX.json"

ROUTE_A_PROFILES = {
    "wave1": {
        "root": "logs_eval/base_v22/postformal_20260806_route_a",
        "cells": ("G1", "G2"),
        "gpu_by_cell": {"G1": 0, "G2": 1},
    },
    "wave23": {
        "root": "logs_eval/base_v22/postformal_20260808_route_a_wave23",
        "cells": ("G3", "G4", "G5", "G6"),
        "gpu_by_cell": {"G3": 0, "G4": 1, "G5": 2, "G6": 3},
    },
}


def configure_route_a(profile: str) -> None:
    global ROUTE_A_ROOT, ROUTE_A_CELLS, ROUTE_A_GPU_BY_CELL
    global MANIFEST_PATH, QUEUE_PATH, RUNTIME_PLAN_PATH, GPU_EVIDENCE_PATH
    global FAILURE_PATH, TERMINAL_STATUS_PATH, EVIDENCE_INDEX_PATH

    selected = ROUTE_A_PROFILES[profile]
    ROUTE_A_ROOT = REPO_ROOT / selected["root"]
    ROUTE_A_CELLS = selected["cells"]
    ROUTE_A_GPU_BY_CELL = selected["gpu_by_cell"]
    MANIFEST_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_MANIFEST.json"
    QUEUE_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_QUEUE.json"
    RUNTIME_PLAN_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_RUNTIME_PLAN.json"
    GPU_EVIDENCE_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_GPU_EVIDENCE.json"
    FAILURE_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_FAILURE.json"
    TERMINAL_STATUS_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_TERMINAL_STATUS.json"
    EVIDENCE_INDEX_PATH = ROUTE_A_ROOT / "V22_ROUTE_A_EVIDENCE_INDEX.json"

DIAGNOSTIC_REWARD_TERMS = (
    "push_door_hinge",
    "a2_stage3_unlatch_hold",
    "a2_stage3_stage4_hold_and_drive",
    "a2_corridor_door_wide",
    "a2_corridor_clean_passage",
    "penalty_a2_door_body_contact",
    "complete",
)

# Mirrors gr00t/rl/envs/door/a2_v22_evidence.py (importing it would drag torch
# into the controller for constants only; keep the names byte-identical).
V22_STEP_TRACE_SCHEMA = "a2_piper_base_v22_step_trace_v1"
V22_HINGE_BUCKETS = ("H0", "H1", "H2", "H3", "H4")
V22_CLEARANCE_STRATEGIES = (
    "NO_CLEARANCE_EVENT",
    "FLING_CLEARANCE",
    "HAND_HOLD_CLEARANCE",
    "BODY_HOLD_CLEARANCE",
    "UNSAFE_RELEASE",
)
V22_FREE_RETURN_CLASSES = (
    "CORE",
    "HIGH_DAMPING",
    "FAST_REBOUND",
    "HIGH_RESISTIVE",
    "COMPOUND",
    "UNCLASSIFIED",
)

# v22 fields every stage-2 step-trace row must carry (plan §14 dependent
# variables, command and achieved sides reported separately).
TRACE_REQUIRED_V22_FIELDS = (
    "v22_posture_command_pitch_rad",
    "v22_posture_command_roll_rad",
    "v22_posture_achieved_pitch_rad",
    "v22_posture_achieved_roll_rad",
    "v22_clearance_strategy",
    "v22_clearance_success",
    "v22_unsafe_release",
    "v22_release_hinge_velocity_radps",
    "registered_hinge_bucket",
    "measured_free_return_class",
)

EXPECTED_PRE_SEND_CROSSING_MODE = "penalty"
HANG_DIAGNOSTIC_FACTOR = 2.0
HANG_STOP_SCHEDULING_FACTOR = 6.0
GPU_SNAPSHOT_INTERVAL_SECONDS = 60.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise V22Error(f"{name} must be a finite number; got {value!r}")
    return float(value)


def _hydra_string(value: str) -> str:
    """Serialize a string as a Hydra override value (single-quote round-trip)."""
    from hydra.core.override_parser.overrides_parser import OverridesParser
    from hydra.core.override_parser.types import Quote, QuotedString

    serialized = QuotedString(value, Quote.single).with_quotes()
    parsed = OverridesParser.create().parse_overrides([f"++__v22_probe={serialized}"])
    if len(parsed) != 1 or parsed[0].value() != value:
        raise V22Error("Hydra string override failed the exact round-trip check")
    return serialized


def _hydra_bucket_table(table: Sequence[Mapping[str, Any]]) -> str:
    """Render the frozen bucket table as a Hydra flow-style list override."""
    entries = []
    for entry in table:
        entries.append(
            "{bucket: %s, damping: [%s, %s], stiffness: [%s, %s], max_force_nm: [%s, %s]}"
            % (
                entry["bucket"],
                repr(float(entry["damping"][0])),
                repr(float(entry["damping"][1])),
                repr(float(entry["stiffness"][0])),
                repr(float(entry["stiffness"][1])),
                repr(float(entry["max_force_nm"][0])),
                repr(float(entry["max_force_nm"][1])),
            )
        )
    rendered = "[" + ",".join(entries) + "]"
    from hydra.core.override_parser.overrides_parser import OverridesParser

    parsed = OverridesParser.create().parse_overrides([f"++__v22_probe={rendered}"])
    if len(parsed) != 1:
        raise V22Error("Hydra bucket-table override failed to parse")
    value = parsed[0].value()
    if not isinstance(value, list) or len(value) != len(table):
        raise V22Error("Hydra bucket-table override lost entries")
    for got, expected in zip(value, table):
        if got["bucket"] != expected["bucket"]:
            raise V22Error("Hydra bucket-table override reordered or relabelled buckets")
        for field in ("damping", "stiffness", "max_force_nm"):
            if [float(v) for v in got[field]] != [float(v) for v in expected[field]]:
                raise V22Error(f"Hydra bucket-table override changed {field} bounds")
    return rendered


# ---------------------------------------------------------------------------
# Signed canonical16 scenario manifest binding
# ---------------------------------------------------------------------------


def load_scenario_manifest() -> dict[str, Any]:
    path = SCENARIO_MANIFEST_PATH
    if path.is_symlink() or not path.is_file():
        raise V22Error(f"signed canonical16 scenario manifest is missing: {path}")
    manifest = read_json(path)
    if manifest.get("schema") != SCENARIO_MANIFEST_SCHEMA or manifest.get("status") != "STATIC_PASS":
        raise V22Error("signed scenario manifest schema/status is invalid")
    canonical = manifest.get("canonical_manifest_rows")
    heavy = manifest.get("manifest_rows")
    if not isinstance(canonical, list) or len(canonical) != 32 or not isinstance(heavy, list) or len(heavy) != 16:
        raise V22Error("signed scenario manifest must contain 32 canonical and 16 heavy rows")
    heavy_hash = hashlib.sha256(canonical_json_bytes(heavy)).hexdigest()
    canonical_hash = hashlib.sha256(canonical_json_bytes(canonical)).hexdigest()
    if manifest.get("manifest_sha256") != heavy_hash or manifest.get("heavy_manifest_sha256") != heavy_hash:
        raise V22Error("signed scenario heavy row hash is invalid")
    if manifest.get("canonical_manifest_sha256") != canonical_hash:
        raise V22Error("signed scenario canonical row hash is invalid")
    heavy_ids = {row["scenario_id"] for row in heavy}
    light_rows = [row for row in canonical if row["scenario_id"] not in heavy_ids]
    if len(light_rows) != ROUTE_A_NUM_ENVS:
        raise V22Error("canonical16 light row count is not 16")
    for row in light_rows:
        for key in ("handle_height_m", "door_weight_kg", "hinge_force_nm"):
            _finite(row.get(key), name=f"canonical16 row {row.get('scenario_id')} {key}")
    manifest_json = canonical_json_bytes(dict(manifest)).decode("utf-8")
    return {
        "path": str(path),
        "file_sha256": sha256_file(path),
        "manifest": dict(manifest),
        "manifest_json": manifest_json,
        "manifest_json_sha256": hashlib.sha256(manifest_json.encode("utf-8")).hexdigest(),
        "manifest_sha256": heavy_hash,
        "canonical_manifest_sha256": canonical_hash,
        "materialization_sha256": manifest["materialization_sha256"],
        "light_rows": light_rows,
    }


# ---------------------------------------------------------------------------
# Cell config validation against the frozen admission chain
# ---------------------------------------------------------------------------


def _close(a: Any, b: Any) -> bool:
    # formal_launcher injects the frozen tables with %.6g formatting, so the
    # resolved config carries 6-significant-digit images of the frozen floats;
    # rel 1e-5 accepts exactly that rounding and nothing larger.
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return math.isclose(float(a), float(b), rel_tol=1e-5, abs_tol=1e-9)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b):
        return all(_close(x, y) for x, y in zip(a, b))
    return a == b


def validate_cell_config(cell: str, config_path: Path, admission: Mapping[str, Any]) -> dict[str, Any]:
    """Bind the resolved training config to the frozen v22 constants; fail on drift."""
    config = read_yaml(config_path)
    env_config = config.get("env", {}).get("config")
    if not isinstance(env_config, Mapping):
        raise V22Error(f"{cell} resolved config lacks env.config")
    locks = admission["locks"]
    atlas = locks["V22_POSTURE_ATLAS.json"]["payload"]
    freeze = locks["V22_POSTURE_GATE_FREEZE.json"]["payload"]
    hinge = locks["V22_HINGE_RANGE_FREEZE.json"]["payload"]
    semantics = locks["V22_ACTION_SEMANTICS.json"]["payload"]

    if config.get("seed") != V22_CELL_SEED[cell]:
        raise V22Error(f"{cell} config seed {config.get('seed')!r} != {V22_CELL_SEED[cell]!r}")
    wave_by_cell = {"G1": 1, "G2": 1, "G3": 2, "G4": 2, "G5": 3, "G6": 3}
    body_assist_by_cell = {"G1": False, "G2": False, "G3": False, "G4": False, "G5": True, "G6": True}
    expected_env = {
        "a2_v20_R1_plan_id": V22_PLAN_ID,
        "a2_v20_send_hinge_threshold": V22_THETA_SEND_RAD,
        "a2_v20_pre_send_crossing_mode": EXPECTED_PRE_SEND_CROSSING_MODE,
        "a2_v22_cell": cell,
        "a2_v22_wave": wave_by_cell[cell],
        "a2_v22_evidence_enabled": True,
        "a2_v22_posture_enabled": True,
        "a2_v22_posture_telemetry_only": False,
        "a2_v22_clearance_enabled": True,
        "a2_v22_body_assist_enabled": body_assist_by_cell[cell],
        "a2_v22_nominal_heights_m": atlas["nominal_heights_m"],
        "a2_v22_nominal_pitch_rad": atlas["nominal_pitch_rad"],
        "a2_v22_nominal_roll_rad": atlas["nominal_roll_rad"],
        "a2_v22_directional_wrench_threshold_n": atlas["directional_wrench_threshold_n"],
        "a2_v22_arm_tracking_error_p90": atlas["arm_tracking_error_p90_rad"],
        "a2_v22_workspace_margin_threshold": atlas["workspace_margin_threshold"],
        "a2_v22_source_lock_sha256": admission["source_lock_sha256"],
        "a2_v22_action_semantics_sha256": semantics["action_semantics_sha256"],
        "a2_v22_posture_gate_freeze_sha256": freeze["posture_gate_freeze_sha256"],
        "a2_v22_hinge_range_freeze_sha256": hinge["hinge_range_freeze_sha256"],
        "a2_v22_posture_gate_state": freeze["posture_gate_state"],
    }
    for key, expected in expected_env.items():
        actual = env_config.get(key)
        if not _close(actual, expected):
            raise V22Error(
                f"{cell} resolved config env.config.{key} = {actual!r} does not match the frozen value {expected!r}"
            )
    if "a2_eval_door_handle_height_linspace" in env_config or "a2_eval_door_handle_height_weight_pairs" in env_config:
        raise V22Error(f"{cell} resolved config carries an eval linspace/pairs scenario hook; Route A forbids it")
    if env_config.get("a2_v21B_signed_probe_scenarios_enabled") is not None:
        raise V22Error(f"{cell} resolved config already carries the v21-B signed probe flag; refusing to dual-source it")
    return {
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "seed": V22_CELL_SEED[cell],
        "wave": wave_by_cell[cell],
        "body_assist_enabled": body_assist_by_cell[cell],
        "pre_send_crossing_mode": env_config["a2_v20_pre_send_crossing_mode"],
        "posture_gate_state": env_config["a2_v22_posture_gate_state"],
    }


def hinge_bucket_table(admission: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The frozen H0-H2 runtime-value bucket table injected for evidence labelling."""
    hinge = admission["locks"]["V22_HINGE_RANGE_FREEZE.json"]["payload"]
    table = []
    for entry in hinge["buckets"]:
        table.append(
            {
                "bucket": entry["bucket"],
                "damping": [float(v) for v in entry["damping"]],
                "stiffness": [float(v) for v in entry["stiffness"]],
                "max_force_nm": [float(v) for v in entry["max_force_nm"]],
            }
        )
    if not table:
        raise V22Error("hinge range freeze carries no realized buckets")
    for entry in table:
        if entry["bucket"] not in V22_HINGE_BUCKETS:
            raise V22Error(f"hinge freeze bucket {entry['bucket']!r} is not registered")
    return table


# ---------------------------------------------------------------------------
# Row / manifest construction
# ---------------------------------------------------------------------------


def row_output_root(cell: str, step: int, seed: int) -> Path:
    return ROUTE_A_ROOT / cell / f"step{step:04d}" / ROUTE_A_TOPOLOGY / f"seed{seed}"


def build_row(
    cell: str,
    step: int,
    *,
    scenario: Mapping[str, Any],
    admission: Mapping[str, Any],
    cell_info: Mapping[str, Any],
    bucket_table: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    seed = V22_CELL_SEED[cell]
    gpu = ROUTE_A_GPU_BY_CELL[cell]
    checkpoint = REPO_ROOT / V22_TRAINING_ROOT / cell / f"model_step_{step:06d}.pt"
    if checkpoint.is_symlink() or not checkpoint.is_file():
        raise V22Error(f"{cell} checkpoint is missing: {checkpoint}")
    checkpoint_sha = sha256_file(checkpoint)
    output_root = row_output_root(cell, step, seed)
    row_id = f"{cell}:step{step:04d}"
    run_uuid = f"v22-routeA-{cell}-step{step:04d}-seed{seed}-{ROUTE_A_TOPOLOGY}"
    manifest = scenario["manifest"]
    eval_name = f"v22_routeA_{cell}_step{step:04d}_{ROUTE_A_TOPOLOGY}_seed{seed}"

    argv = [
        PYTHON_BIN,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++headless=true",
        f"++num_envs={ROUTE_A_NUM_ENVS}",
        f"++seed={seed}",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++algo.config.eval.num_eval_episodes={ROUTE_A_EVAL_EPISODES}",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        "++algo.config.eval.a2_diagnostic_reward_terms=[" + ",".join(DIAGNOSTIC_REWARD_TERMS) + "]",
        "++algo.config.eval.a2_eval_v20_strict_telemetry=false",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        f"++env.config.a2_v20_R1_plan_id={V22_PLAN_ID}",
        f"++env.config.a2_v20_send_hinge_threshold={V22_THETA_SEND_RAD}",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v21B_evidence_enabled=false",
        "++env.config.a2_v22_evidence_enabled=true",
        "++env.config.a2_v21B_signed_probe_scenarios_enabled=true",
        f"++env.config.a2_v21B_census_topology={ROUTE_A_TOPOLOGY}",
        f"++env.config.a2_v21B_scenario_manifest_path={_hydra_string(scenario['path'])}",
        f"++env.config.a2_v21B_scenario_manifest_sha256={scenario['manifest_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_file_sha256={scenario['file_sha256']}",
        f"++env.config.a2_v21B_canonical_manifest_sha256={scenario['canonical_manifest_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_source_checkpoint_sha256={manifest['source_checkpoint_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_source_lock_sha256={manifest['source_lock_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_source_config_sha256={manifest['source_config_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_materialization_sha256={scenario['materialization_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_json_sha256={scenario['manifest_json_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_json={_hydra_string(scenario['manifest_json'])}",
        f"++env.config.a2_v22_hinge_bucket_table={_hydra_bucket_table(bucket_table)}",
        f"++eval_name={eval_name}",
        f"++eval_output_dir={output_root}",
    ]
    env = {
        "CUDA_VISIBLE_DEVICES": "<unset>",
        "ACCELERATE_TORCH_DEVICE": f"cuda:{gpu}",
        "WANDB_MODE": "disabled",
    }
    command_sha = digest({"argv": argv, "env": env})
    return {
        "row_id": row_id,
        "cell": cell,
        "step": step,
        "seed": seed,
        "physical_gpu": gpu,
        "topology": ROUTE_A_TOPOLOGY,
        "run_uuid": run_uuid,
        "eval_name": eval_name,
        "plan_id": V22_PLAN_ID,
        "execution_id": V22_EXECUTION_ID,
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha,
        "config_path": cell_info["config_path"],
        "config_sha256": cell_info["config_sha256"],
        "pre_send_crossing_mode": cell_info["pre_send_crossing_mode"],
        "source_lock_sha256": admission["source_lock_sha256"],
        "scenario_manifest_path": scenario["path"],
        "scenario_manifest_sha256": scenario["manifest_sha256"],
        "scenario_manifest_file_sha256": scenario["file_sha256"],
        "canonical_manifest_sha256": scenario["canonical_manifest_sha256"],
        "scenario_manifest_json_sha256": scenario["manifest_json_sha256"],
        "scenario_manifest_materialization_sha256": scenario["materialization_sha256"],
        "hinge_bucket_table_sha256": digest(bucket_table),
        "expected_env_ids": list(range(ROUTE_A_NUM_ENVS)),
        "expected_light_rows": [
            {
                "env_id": index,
                "scenario_id": row["scenario_id"],
                "handle_height_m": row["handle_height_m"],
                "door_weight_kg": row["door_weight_kg"],
                "hinge_force_nm": row["hinge_force_nm"],
            }
            for index, row in enumerate(scenario["light_rows"])
        ],
        "evaluation_root": str(output_root),
        "argv": argv,
        "env": env,
        "command_sha256": command_sha,
    }


def build_manifest() -> dict[str, Any]:
    admission = load_admission(REPO_ROOT)
    scenario = load_scenario_manifest()
    identity = git_identity(REPO_ROOT)
    bucket_table = hinge_bucket_table(admission)
    rows = []
    cells = {}
    for cell in ROUTE_A_CELLS:
        config_path = REPO_ROOT / V22_TRAINING_ROOT / cell / "config.yaml"
        cell_info = validate_cell_config(cell, config_path, admission)
        cells[cell] = cell_info
        for step in ROUTE_A_STEPS:
            rows.append(
                build_row(
                    cell,
                    step,
                    scenario=scenario,
                    admission=admission,
                    cell_info=cell_info,
                    bucket_table=bucket_table,
                )
            )
    if len(rows) != len(ROUTE_A_CELLS) * len(ROUTE_A_STEPS):
        raise V22Error("Route-A manifest row cardinality is not cells x steps")
    crossing_modes = {row["pre_send_crossing_mode"] for row in rows}
    if crossing_modes != {EXPECTED_PRE_SEND_CROSSING_MODE}:
        raise V22Error(f"Route-A rows do not share one pre-send crossing mode: {crossing_modes}")
    manifest = artifact_payload(
        "route_a_manifest",
        status="BUILT",
        created_utc=_now(),
        git=identity,
        route="A",
        plan_section="§14",
        topology=ROUTE_A_TOPOLOGY,
        num_envs=ROUTE_A_NUM_ENVS,
        eval_episodes_per_row=ROUTE_A_EVAL_EPISODES,
        first_episode_only=True,
        cells=list(ROUTE_A_CELLS),
        steps=list(ROUTE_A_STEPS),
        cell_factors={cell: {"seed": V22_CELL_SEED[cell], "physical_gpu": ROUTE_A_GPU_BY_CELL[cell]} for cell in ROUTE_A_CELLS},
        cell_config_validation=cells,
        admission_locks={
            name: {"path": str(locks["path"]), "file_sha256": locks["file_sha256"]}
            for name, locks in admission["locks"].items()
        },
        posture_waiver=admission["posture_waiver"],
        source_lock_sha256=admission["source_lock_sha256"],
        scenario_manifest={key: scenario[key] for key in (
            "path", "file_sha256", "manifest_sha256", "canonical_manifest_sha256",
            "manifest_json_sha256", "materialization_sha256",
        )},
        hinge_bucket_table=bucket_table,
        hinge_bucket_table_sha256=digest(bucket_table),
        pre_send_crossing_mode=EXPECTED_PRE_SEND_CROSSING_MODE,
        rows=rows,
    )
    manifest["manifest_sha256"] = digest(manifest)
    return manifest


def build_queue(manifest: Mapping[str, Any]) -> dict[str, Any]:
    rows = manifest["rows"]
    lane_cells = {
        str(gpu): sorted({row["cell"] for row in rows if row["physical_gpu"] == gpu})
        for gpu in sorted({row["physical_gpu"] for row in rows})
    }
    lanes = {
        str(gpu): [
            {
                "row_id": row["row_id"],
                "cell": row["cell"],
                "step": row["step"],
                "physical_gpu": row["physical_gpu"],
                "evaluation_root": row["evaluation_root"],
                "command_sha256": row["command_sha256"],
            }
            for row in sorted((r for r in rows if r["physical_gpu"] == gpu), key=lambda r: r["step"])
        ]
        for gpu in sorted({row["physical_gpu"] for row in rows})
    }
    for gpu, lane in lanes.items():
        for row in lane:
            if row["physical_gpu"] != int(gpu):
                raise V22Error("queue lane does not bind the row physical GPU")
    queue = artifact_payload(
        "route_a_queue",
        status="BUILT",
        created_utc=_now(),
        manifest_sha256=manifest["manifest_sha256"],
        lane_cells=lane_cells,
        lanes=lanes,
        row_count=len(rows),
        scheduling="gpu-serial; stop scheduling on first nonzero exit or post-exit validation failure; no retries",
    )
    queue["queue_sha256"] = digest(queue)
    return queue


# ---------------------------------------------------------------------------
# Post-exit row validation
# ---------------------------------------------------------------------------


def _load_row_artifact(root: Path, name: str) -> Any:
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise V22Error(f"row artifact is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V22Error(f"row artifact {path} is not valid JSON: {exc}") from exc


def _check_finite_tree(value: Any, *, path: str) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise V22Error(f"non-finite metric at {path}")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _check_finite_tree(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check_finite_tree(item, path=f"{path}[{index}]")
        return
    raise V22Error(f"unexpected metric value type at {path}: {type(value).__name__}")


def validate_row_completion(row: Mapping[str, Any]) -> dict[str, Any]:
    """Strict post-exit validation; returns the sealed receipt payload."""
    root = Path(row["evaluation_root"])
    if not root.is_dir():
        raise V22Error(f"row output root is missing: {root}")

    metrics = _load_row_artifact(root, "metrics_eval.json")
    trace = _load_row_artifact(root, "stage2_step_trace.json")
    records = _load_row_artifact(root, "a2_v14_per_env_records.json")
    diagnostic = _load_row_artifact(root, "a2_eval_diagnostic_metadata.json")
    trace_25_path = root / "stage2_5_step_trace.json"
    trace_25 = _load_row_artifact(root, "stage2_5_step_trace.json") if trace_25_path.is_file() else None
    runtime_config_path = root / ".hydra" / "runtime_config.yaml"
    if runtime_config_path.is_symlink() or not runtime_config_path.is_file():
        raise V22Error(f"row runtime config is missing: {runtime_config_path}")
    # OmegaConf.save serializes config.experiment_dir as a pathlib tag, which
    # yaml.safe_load cannot construct; load with OmegaConf itself.
    from omegaconf import OmegaConf

    # resolve=False: the dump still carries ${now:...} timestamp interpolations
    # that only Hydra can resolve; every key Route A validates is a literal.
    runtime_config = OmegaConf.to_container(OmegaConf.load(runtime_config_path), resolve=False)
    if not isinstance(runtime_config, dict):
        raise V22Error(f"row runtime config did not decode to a mapping: {runtime_config_path}")
    eval_log = root / "eval.log"
    if not eval_log.is_file():
        raise V22Error(f"row eval log is missing: {eval_log}")

    # --- first-episode cardinality and finiteness --------------------------
    if metrics.get("completed_episodes") != ROUTE_A_EVAL_EPISODES:
        raise V22Error(f"row completed_episodes is not {ROUTE_A_EVAL_EPISODES}")
    for key in ("episode_lengths", "episode_rewards", "episode_goal_reached", "episode_max_stage_reached", "episode_terminal_reasons"):
        values = metrics.get(key)
        if not isinstance(values, list) or len(values) != ROUTE_A_EVAL_EPISODES:
            raise V22Error(f"metrics_eval.{key} must be a length-{ROUTE_A_EVAL_EPISODES} list")
    goals = metrics["episode_goal_reached"]
    if any(not isinstance(value, bool) for value in goals):
        raise V22Error("episode_goal_reached must be bool per env")
    for key in ("episode_lengths", "episode_rewards"):
        for value in metrics[key]:
            _finite(value, name=f"metrics_eval.{key}")
    _check_finite_tree(metrics["episode_max_stage_reached"], path="metrics_eval.episode_max_stage_reached")

    if not isinstance(records, list) or len(records) != ROUTE_A_NUM_ENVS:
        raise V22Error("a2_v14_per_env_records.json must contain exactly 16 first-episode records")
    record_env_ids = sorted(record.get("env_id") for record in records)
    if record_env_ids != list(range(ROUTE_A_NUM_ENVS)):
        raise V22Error(f"per-env record env ids are not exactly 0..15: {record_env_ids}")
    for record in records:
        if record.get("seed") != row["seed"]:
            raise V22Error(f"per-env record seed {record.get('seed')!r} != row seed {row['seed']!r}")
        _check_finite_tree(record, path=f"a2_v14_per_env_records[env{record['env_id']}]")

    terminal = metrics.get("episode_terminal_diagnostics")
    if not isinstance(terminal, list) or len(terminal) != ROUTE_A_NUM_ENVS:
        raise V22Error("episode_terminal_diagnostics must be a length-16 list")
    terminal_by_env = {}
    for entry in terminal:
        env_id = entry.get("env_id")
        if env_id in terminal_by_env or env_id not in range(ROUTE_A_NUM_ENVS):
            raise V22Error("terminal diagnostics env ids are duplicated or out of range")
        terminal_by_env[env_id] = entry
    if sorted(terminal_by_env) != list(range(ROUTE_A_NUM_ENVS)):
        raise V22Error("terminal diagnostics do not cover all 16 envs")

    # --- runtime config binds the canonical16 signed selector --------------
    env_cfg = runtime_config.get("env", {}).get("config")
    if not isinstance(env_cfg, Mapping):
        raise V22Error("runtime config lacks env.config")
    wave_by_cell = {"G1": 1, "G2": 1, "G3": 2, "G4": 2, "G5": 3, "G6": 3}
    body_assist_by_cell = {"G1": False, "G2": False, "G3": False, "G4": False, "G5": True, "G6": True}
    runtime_expect = {
        "a2_v21B_signed_probe_scenarios_enabled": True,
        "a2_v21B_census_topology": ROUTE_A_TOPOLOGY,
        "a2_v21B_scenario_manifest_path": row["scenario_manifest_path"],
        "a2_v21B_scenario_manifest_sha256": row["scenario_manifest_sha256"],
        "a2_v21B_scenario_manifest_file_sha256": row["scenario_manifest_file_sha256"],
        "a2_v21B_canonical_manifest_sha256": row["canonical_manifest_sha256"],
        "a2_v21B_scenario_manifest_json_sha256": row["scenario_manifest_json_sha256"],
        "a2_v21B_scenario_manifest_materialization_sha256": row["scenario_manifest_materialization_sha256"],
        "a2_v21B_evidence_enabled": False,
        "a2_v20_R2_evidence_enabled": False,
        "a2_v22_evidence_enabled": True,
        "a2_v20_R1_plan_id": V22_PLAN_ID,
        "a2_v20_send_hinge_threshold": V22_THETA_SEND_RAD,
        "a2_v20_pre_send_crossing_mode": EXPECTED_PRE_SEND_CROSSING_MODE,
        "a2_v22_posture_telemetry_only": False,
        "a2_v22_cell": row["cell"],
        "a2_v22_wave": wave_by_cell[row["cell"]],
        "a2_v22_body_assist_enabled": body_assist_by_cell[row["cell"]],
    }
    for key, expected in runtime_expect.items():
        actual = env_cfg.get(key)
        if not _close(actual, expected):
            raise V22Error(f"runtime env.config.{key} = {actual!r} does not bind the Route-A row ({expected!r})")
    if "a2_eval_door_handle_height_linspace" in env_cfg or "a2_eval_door_handle_height_weight_pairs" in env_cfg:
        raise V22Error("runtime config carries a linspace/pairs scenario hook; Route A requires the signed selector")
    if runtime_config.get("num_envs") != ROUTE_A_NUM_ENVS or runtime_config.get("seed") != row["seed"]:
        raise V22Error("runtime num_envs/seed does not match the row")
    if runtime_config.get("headless") is not True or runtime_config.get("use_wandb") is not False:
        raise V22Error("runtime headless/use_wandb contract is violated")
    if runtime_config.get("checkpoint") != row["checkpoint_path"]:
        raise V22Error("runtime checkpoint does not match the row checkpoint")

    # --- per-env scenario triples match the signed canonical16 light rows --
    scenario_binding = []
    for expected in row["expected_light_rows"]:
        env_id = expected["env_id"]
        record = next(r for r in records if r["env_id"] == env_id)
        actual = (
            _finite(record.get("door_handle_height"), name=f"env{env_id} handle height"),
            _finite(record.get("door_weight"), name=f"env{env_id} door weight"),
            _finite(record.get("door_hinge_drive_max_force"), name=f"env{env_id} hinge max force"),
        )
        wanted = (
            float(expected["handle_height_m"]),
            float(expected["door_weight_kg"]),
            float(expected["hinge_force_nm"]),
        )
        if any(not math.isclose(a, w, rel_tol=1e-6, abs_tol=1e-6) for a, w in zip(actual, wanted)):
            raise V22Error(
                f"env{env_id} runtime scenario triple {actual} does not match signed canonical16 row "
                f"{expected['scenario_id']} {wanted}"
            )
        scenario_binding.append({"env_id": env_id, "scenario_id": expected["scenario_id"], "runtime_triple": list(actual)})

    # --- step trace ---------------------------------------------------------
    if not isinstance(trace, list) or not trace:
        raise V22Error("stage2_step_trace.json must be a non-empty list")
    trace_env_ids = set()
    for index, entry in enumerate(trace):
        if not isinstance(entry, Mapping):
            raise V22Error(f"trace row {index} is not a mapping")
        env_id = entry.get("env_id")
        if env_id not in range(ROUTE_A_NUM_ENVS):
            raise V22Error(f"trace row {index} env_id is invalid: {env_id!r}")
        trace_env_ids.add(env_id)
        if entry.get("v22_schema") != V22_STEP_TRACE_SCHEMA:
            raise V22Error(f"trace row {index} lacks the v22 step trace schema")
        for field in TRACE_REQUIRED_V22_FIELDS:
            if field not in entry:
                raise V22Error(f"trace row {index} is missing v22 field {field}")
        for field in (
            "v22_posture_command_pitch_rad",
            "v22_posture_command_roll_rad",
            "v22_posture_achieved_pitch_rad",
            "v22_posture_achieved_roll_rad",
        ):
            _finite(entry[field], name=f"trace[{index}].{field}")
        if entry["v22_release_hinge_velocity_radps"] is not None:
            _finite(entry["v22_release_hinge_velocity_radps"], name=f"trace[{index}].v22_release_hinge_velocity_radps")
        if entry["v22_clearance_strategy"] not in V22_CLEARANCE_STRATEGIES:
            raise V22Error(f"trace row {index} clearance strategy is unregistered: {entry['v22_clearance_strategy']!r}")
        if entry["registered_hinge_bucket"] is not None and entry["registered_hinge_bucket"] not in V22_HINGE_BUCKETS:
            raise V22Error(f"trace row {index} hinge bucket is unregistered: {entry['registered_hinge_bucket']!r}")
        if entry["measured_free_return_class"] not in V22_FREE_RETURN_CLASSES:
            raise V22Error(f"trace row {index} free-return class is unregistered: {entry['measured_free_return_class']!r}")
    if trace_25 is not None:
        if not isinstance(trace_25, list):
            raise V22Error("stage2_5_step_trace.json must be a list")
        for index, entry in enumerate(trace_25):
            if not isinstance(entry, Mapping) or entry.get("env_id") not in range(ROUTE_A_NUM_ENVS):
                raise V22Error(f"stage2_5 trace row {index} is malformed")
            _check_finite_tree(entry, path=f"stage2_5_step_trace[{index}]")

    if diagnostic.get("diagnostic_trace_enabled") is not True:
        raise V22Error("diagnostic metadata does not confirm the trace contract")
    if list(diagnostic.get("reward_terms", [])) != list(DIAGNOSTIC_REWARD_TERMS):
        raise V22Error("diagnostic metadata reward terms do not match the Route-A set")

    # --- headline numbers ----------------------------------------------------
    headline = extract_headline(row, metrics, records, terminal_by_env, trace)

    artifacts = {}
    for name in (
        "metrics_eval.json",
        "stage2_step_trace.json",
        "stage2_5_step_trace.json",
        "a2_v14_per_env_records.json",
        "a2_eval_diagnostic_metadata.json",
        "eval.log",
        "runtime_stdout.log",
        "runtime_stderr.log",
    ):
        path = root / name
        if path.is_file() and not path.is_symlink():
            artifacts[name] = {"path": str(path), "sha256": sha256_file(path)}
    artifacts[".hydra/runtime_config.yaml"] = {
        "path": str(runtime_config_path),
        "sha256": sha256_file(runtime_config_path),
    }
    receipt = artifact_payload(
        "route_a_row_receipt",
        status="ROW_PASS",
        validated_utc=_now(),
        row_id=row["row_id"],
        cell=row["cell"],
        step=row["step"],
        seed=row["seed"],
        physical_gpu=row["physical_gpu"],
        run_uuid=row["run_uuid"],
        checkpoint_path=row["checkpoint_path"],
        checkpoint_sha256=row["checkpoint_sha256"],
        command_sha256=row["command_sha256"],
        evaluation_root=str(root),
        first_episode_count=ROUTE_A_EVAL_EPISODES,
        trace_env_coverage=sorted(trace_env_ids),
        trace_row_count=len(trace),
        stage2_5_present=trace_25 is not None,
        canonical16_binding=scenario_binding,
        pre_send_crossing_mode=EXPECTED_PRE_SEND_CROSSING_MODE,
        headline=headline,
        artifacts=artifacts,
    )
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def extract_headline(
    row: Mapping[str, Any],
    metrics: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    terminal_by_env: Mapping[int, Mapping[str, Any]],
    trace: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    goals = sum(1 for value in metrics["episode_goal_reached"] if value)
    supported = sum(1 for record in records if record.get("crossing_while_holding") is True)
    raw_crossing = sum(1 for entry in terminal_by_env.values() if entry.get("root_x_ever_crossed") is True)
    unsafe = sum(1 for entry in terminal_by_env.values() if entry.get("v22_unsafe_release") is True)
    clearance_success = sum(1 for entry in terminal_by_env.values() if entry.get("v22_clearance_success") is True)
    post_release_contact = sum(1 for record in records if record.get("post_release_body_contact") is True)

    release_velocities = [
        float(entry["v22_release_hinge_velocity_radps"])
        for entry in terminal_by_env.values()
        if entry.get("v22_release_hinge_velocity_radps") is not None
    ]
    for value in release_velocities:
        _finite(value, name="release velocity")

    command_pitch = [abs(_finite(entry["v22_posture_command_pitch_rad"], name="cmd pitch")) for entry in trace]
    command_roll = [abs(_finite(entry["v22_posture_command_roll_rad"], name="cmd roll")) for entry in trace]
    achieved_pitch = [abs(_finite(entry["v22_posture_achieved_pitch_rad"], name="ach pitch")) for entry in trace]
    achieved_roll = [abs(_finite(entry["v22_posture_achieved_roll_rad"], name="ach roll")) for entry in trace]

    strategy_counts: dict[str, int] = {}
    bucket_counts: dict[str, int] = {}
    free_return_counts: dict[str, int] = {}
    for entry in terminal_by_env.values():
        strategy = entry.get("v22_clearance_strategy")
        if strategy is not None:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        bucket = entry.get("registered_hinge_bucket")
        bucket_counts[bucket if bucket is not None else "UNMATCHED"] = bucket_counts.get(bucket if bucket is not None else "UNMATCHED", 0) + 1
        free_return = entry.get("measured_free_return_class")
        if free_return is not None:
            free_return_counts[free_return] = free_return_counts.get(free_return, 0) + 1

    def q(values: Sequence[float], quantile_q: float) -> float | None:
        return quantile(values, quantile_q) if values else None

    hinge_at_crossing = [
        float(record["hinge_at_crossing"]) for record in records if record.get("hinge_at_crossing") is not None
    ]
    return {
        "goal_count": goals,
        "goal_denominator": ROUTE_A_NUM_ENVS,
        "raw_crossing_count": raw_crossing,
        "supported_crossing_count": supported,
        "supported_crossing_definition": "a2_v14_per_env_records.crossing_while_holding == true",
        "unsafe_release_count": unsafe,
        "clearance_success_count": clearance_success,
        "post_release_body_contact_count": post_release_contact,
        "release_velocity_sample": len(release_velocities),
        "release_velocity_p50_radps": q(release_velocities, 0.50),
        "release_velocity_p95_radps": q(release_velocities, 0.95),
        "hinge_at_crossing_p50_rad": q(hinge_at_crossing, 0.50),
        "command_abs_pitch_p50_rad": q(command_pitch, 0.50),
        "command_abs_pitch_p95_rad": q(command_pitch, 0.95),
        "command_abs_roll_p50_rad": q(command_roll, 0.50),
        "command_abs_roll_p95_rad": q(command_roll, 0.95),
        "achieved_abs_pitch_p50_rad": q(achieved_pitch, 0.50),
        "achieved_abs_pitch_p95_rad": q(achieved_pitch, 0.95),
        "achieved_abs_roll_p50_rad": q(achieved_roll, 0.50),
        "achieved_abs_roll_p95_rad": q(achieved_roll, 0.95),
        "posture_frame_count": len(trace),
        "clearance_strategy_counts": strategy_counts,
        "hinge_bucket_counts": bucket_counts,
        "free_return_class_counts": free_return_counts,
    }


def seal_row(row: Mapping[str, Any], process: Mapping[str, Any]) -> dict[str, Any]:
    receipt = validate_row_completion(row)
    receipt["process"] = dict(process)
    receipt["receipt_sha256"] = digest({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    root = Path(row["evaluation_root"])
    receipt_path = root / "row_receipt.json"
    write_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    receipt["receipt_file_sha256"] = sha256_file(receipt_path)
    return receipt


def load_sealed_receipt(row: Mapping[str, Any]) -> dict[str, Any] | None:
    receipt_path = Path(row["evaluation_root"]) / "row_receipt.json"
    if not receipt_path.is_file():
        return None
    receipt = read_json(receipt_path)
    if receipt.get("status") != "ROW_PASS" or receipt.get("row_id") != row["row_id"]:
        raise V22Error(f"row receipt at {receipt_path} is not a sealed ROW_PASS for {row['row_id']}")
    if receipt.get("command_sha256") != row["command_sha256"] or receipt.get("checkpoint_sha256") != row["checkpoint_sha256"]:
        raise V22Error(f"row receipt at {receipt_path} is not bound to the manifest row identity")
    return receipt


# ---------------------------------------------------------------------------
# GPU evidence + scheduler
# ---------------------------------------------------------------------------


def gpu_snapshot(label: str) -> dict[str, Any]:
    gpus = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,uuid,pstate,utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout.splitlines()
    apps = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name,used_memory", "--format=csv,noheader"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return {
        "timestamp_utc": _now(),
        "label": label,
        "gpu_query": gpus,
        "compute_apps": apps.stdout.splitlines(),
        "compute_apps_exit_code": apps.returncode,
    }


def assert_eval_gpus_idle(snapshot: Mapping[str, Any]) -> None:
    uuid_to_index = {}
    for line in snapshot["gpu_query"]:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 2:
            uuid_to_index[parts[1]] = parts[0]
    for app in snapshot["compute_apps"]:
        parts = [part.strip() for part in app.split(",")]
        if parts and parts[0] in uuid_to_index and int(uuid_to_index[parts[0]]) in set(ROUTE_A_GPU_BY_CELL.values()):
            raise V22Error(
                f"physical GPU {uuid_to_index[parts[0]]} already runs a compute app ({app}); "
                "Route A refuses to share its leased GPUs"
            )


def _row_env(row: Mapping[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env["ACCELERATE_TORCH_DEVICE"] = f"cuda:{row['physical_gpu']}"
    env["WANDB_MODE"] = "disabled"
    return env


def _hang_diagnostics(item: Mapping[str, Any], durations: Sequence[float], reason: str) -> dict[str, Any]:
    row = item["row"]
    root = Path(row["evaluation_root"])
    diagnostics = {
        "timestamp_utc": _now(),
        "reason": reason,
        "row_id": row["row_id"],
        "pid": item["proc"].pid,
        "physical_gpu": row["physical_gpu"],
        "elapsed_seconds": time.monotonic() - item["monotonic"],
        "median_completed_seconds": statistics.median(durations) if durations else None,
        "gpu_snapshot": gpu_snapshot("hang-diagnostic"),
        "stdout_tail": [],
        "stderr_tail": [],
    }
    for name, key in (("runtime_stdout.log", "stdout_tail"), ("runtime_stderr.log", "stderr_tail")):
        path = root / name
        if path.is_file():
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            diagnostics[key] = lines[-50:]
    path = ROUTE_A_ROOT / f"V22_ROUTE_A_HANG_DIAGNOSTIC_{row['row_id'].replace(':', '_')}.json"
    write_json(path, diagnostics)
    diagnostics["diagnostic_path"] = str(path)
    return diagnostics


def run_lanes(manifest: Mapping[str, Any], *, only_row: str | None = None) -> int:
    rows = {row["row_id"]: row for row in manifest["rows"]}
    if only_row is not None and only_row not in rows:
        raise V22Error(f"unknown row_id {only_row!r}")
    selected = [rows[only_row]] if only_row else list(manifest["rows"])
    lanes: dict[int, list[dict[str, Any]]] = {}
    for row in selected:
        lanes.setdefault(row["physical_gpu"], []).append(row)
    for gpu in lanes:
        lanes[gpu].sort(key=lambda r: r["step"])

    preflight = gpu_snapshot("preflight")
    assert_eval_gpus_idle(preflight)
    snapshots = [preflight]

    positions = {gpu: 0 for gpu in lanes}
    live: dict[int, dict[str, Any]] = {}
    completed: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    durations: list[float] = []
    hang_events: list[dict[str, Any]] = []
    started = _now()
    stop_scheduling = False
    last_snapshot = 0.0

    # Skip rows already sealed by an earlier invocation (e.g. the smoke row).
    for gpu, lane in lanes.items():
        while positions[gpu] < len(lane):
            row = lane[positions[gpu]]
            receipt = load_sealed_receipt(row)
            if receipt is None:
                if Path(row["evaluation_root"]).exists():
                    raise V22Error(
                        f"row output dir exists without a sealed receipt: {row['evaluation_root']}; refusing to overwrite"
                    )
                break
            completed.append({"row_id": row["row_id"], "receipt": receipt, "skipped_presealed": True})
            durations.append(float(receipt["process"]["duration_seconds"]))
            positions[gpu] += 1
            print(f"SKIP {row['row_id']} (sealed ROW_PASS receipt)", flush=True)

    while live or (not stop_scheduling and any(positions[gpu] < len(lanes[gpu]) for gpu in lanes)):
        if not stop_scheduling:
            for gpu in sorted(lanes):
                if gpu in live or positions[gpu] >= len(lanes[gpu]):
                    continue
                row = lanes[gpu][positions[gpu]]
                root = Path(row["evaluation_root"])
                root.mkdir(parents=True, exist_ok=False)
                stdout_path, stderr_path = root / "runtime_stdout.log", root / "runtime_stderr.log"
                env = _row_env(row)
                out_handle = stdout_path.open("xb")
                err_handle = stderr_path.open("xb")
                launch_start = _now()
                proc = subprocess.Popen(row["argv"], cwd=REPO_ROOT, env=env, stdout=out_handle, stderr=err_handle)
                live[gpu] = {
                    "row": row,
                    "proc": proc,
                    "stdout": out_handle,
                    "stderr": err_handle,
                    "started": launch_start,
                    "monotonic": time.monotonic(),
                    "hang_reported": False,
                }
                print(f"LAUNCHED {row['row_id']} GPU{gpu} PID{proc.pid}", flush=True)
        now_mono = time.monotonic()
        if now_mono - last_snapshot >= GPU_SNAPSHOT_INTERVAL_SECONDS:
            snapshots.append(gpu_snapshot("monitor"))
            write_json(GPU_EVIDENCE_PATH, artifact_payload(
                "route_a_gpu_evidence",
                snapshots=snapshots,
                live=[{"row_id": item["row"]["row_id"], "physical_gpu": gpu, "pid": item["proc"].pid} for gpu, item in sorted(live.items())],
            ))
            last_snapshot = now_mono
        for gpu, item in list(live.items()):
            code = item["proc"].poll()
            if code is None:
                elapsed = now_mono - item["monotonic"]
                if durations:
                    median = statistics.median(durations)
                    if elapsed > HANG_DIAGNOSTIC_FACTOR * median and not item["hang_reported"]:
                        item["hang_reported"] = True
                        diagnostics = _hang_diagnostics(item, durations, "row exceeded 2x median completed duration")
                        hang_events.append(diagnostics)
                        print(
                            f"HANG-WATCH {item['row']['row_id']} elapsed={elapsed:.0f}s median={median:.0f}s; "
                            f"diagnostics at {diagnostics['diagnostic_path']} (process left running)",
                            flush=True,
                        )
                    if elapsed > HANG_STOP_SCHEDULING_FACTOR * median and not stop_scheduling:
                        stop_scheduling = True
                        diagnostics = _hang_diagnostics(item, durations, "row exceeded 6x median; scheduling stopped, process left running")
                        hang_events.append(diagnostics)
                        print(
                            f"HANG-STOP {item['row']['row_id']}: scheduling stopped; process PID{item['proc'].pid} left running for operator inspection",
                            flush=True,
                        )
                continue
            ended = _now()
            item["stdout"].close()
            item["stderr"].close()
            duration = now_mono - item["monotonic"]
            row = item["row"]
            del live[gpu]
            process = {
                "pid": item["proc"].pid,
                "started_utc": item["started"],
                "ended_utc": ended,
                "natural_exit": code == 0,
                "exit_code": code,
                "duration_seconds": duration,
            }
            if code != 0:
                failures.append({"row_id": row["row_id"], "reason": "NONZERO_EXIT", "process": process})
                stop_scheduling = True
                print(f"FAIL {row['row_id']} exit={code}; scheduling stopped", flush=True)
                continue
            try:
                receipt = seal_row(row, process)
            except Exception as exc:
                failures.append({"row_id": row["row_id"], "reason": "POSTEXIT_VALIDATION", "error": repr(exc), "process": process})
                stop_scheduling = True
                print(f"FAIL {row['row_id']} post-exit validation; scheduling stopped: {exc!r}", flush=True)
                continue
            durations.append(duration)
            positions[gpu] += 1
            completed.append({"row_id": row["row_id"], "receipt": receipt, "skipped_presealed": False})
            total = len(selected)
            print(
                f"COMPLETED {len(completed)}/{total} {row['row_id']} GPU{gpu} duration={duration:.1f}s "
                f"goal={receipt['headline']['goal_count']}/16",
                flush=True,
            )
        if live:
            time.sleep(2.0)

    snapshots.append(gpu_snapshot("terminal"))
    write_json(GPU_EVIDENCE_PATH, artifact_payload("route_a_gpu_evidence", snapshots=snapshots, live=[
        {"row_id": item["row"]["row_id"], "physical_gpu": gpu, "pid": item["proc"].pid} for gpu, item in sorted(live.items())
    ]))

    pending = [row["row_id"] for gpu, lane in lanes.items() for row in lane[positions[gpu]:]]
    ended = _now()
    if failures or stop_scheduling or live:
        write_json(FAILURE_PATH, artifact_payload(
            "route_a_failure",
            status="FAIL",
            started_utc=started,
            ended_utc=ended,
            completed=[{"row_id": item["row_id"], "receipt_path": item["receipt"].get("receipt_path")} for item in completed],
            failures=failures,
            hang_events=hang_events,
            pending=pending,
            live=[{"row_id": item["row"]["row_id"], "pid": item["proc"].pid, "physical_gpu": gpu} for gpu, item in sorted(live.items())],
        ))
        return 2
    write_json(TERMINAL_STATUS_PATH, artifact_payload(
        "route_a_terminal_status",
        status="PASS",
        started_utc=started,
        ended_utc=ended,
        row_count=len(selected),
        completed_rows=[item["row_id"] for item in completed],
        duration_seconds_total=sum(durations),
        hang_events=hang_events,
    ))
    print(f"PASS route-a rows={len(selected)}", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Evidence index
# ---------------------------------------------------------------------------


def build_index(manifest: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    missing = []
    for row in manifest["rows"]:
        receipt = load_sealed_receipt(row)
        if receipt is None:
            missing.append(row["row_id"])
            continue
        process = receipt.get("process", {})
        rows.append({
            "row_id": row["row_id"],
            "cell": row["cell"],
            "step": row["step"],
            "seed": row["seed"],
            "physical_gpu": row["physical_gpu"],
            "run_uuid": row["run_uuid"],
            "checkpoint_path": row["checkpoint_path"],
            "checkpoint_sha256": row["checkpoint_sha256"],
            "command_sha256": row["command_sha256"],
            "exit_code": process.get("exit_code"),
            "duration_seconds": process.get("duration_seconds"),
            "started_utc": process.get("started_utc"),
            "ended_utc": process.get("ended_utc"),
            "evaluation_root": row["evaluation_root"],
            "receipt_path": receipt["receipt_path"],
            "receipt_file_sha256": receipt["receipt_file_sha256"],
            "artifact_hashes": {name: info["sha256"] for name, info in receipt["artifacts"].items()},
            "evidence_validation": "ROW_PASS",
            "first_episode_count": receipt["first_episode_count"],
            "trace_env_coverage": receipt["trace_env_coverage"],
            "trace_row_count": receipt["trace_row_count"],
            "pre_send_crossing_mode": receipt["pre_send_crossing_mode"],
            "headline": receipt["headline"],
        })
    index = artifact_payload(
        "route_a_evidence_index",
        status="COMPLETE" if not missing else "INCOMPLETE",
        created_utc=_now(),
        manifest_sha256=manifest["manifest_sha256"],
        topology=ROUTE_A_TOPOLOGY,
        row_count=len(rows),
        missing_rows=missing,
        pre_send_crossing_mode=EXPECTED_PRE_SEND_CROSSING_MODE,
        scenario_manifest_sha256=manifest["scenario_manifest"]["manifest_sha256"],
        canonical_manifest_sha256=manifest["scenario_manifest"]["canonical_manifest_sha256"],
        source_lock_sha256=manifest["source_lock_sha256"],
        hinge_bucket_table_sha256=manifest["hinge_bucket_table_sha256"],
        rows=rows,
    )
    index["index_sha256"] = digest(index)
    write_json(EVIDENCE_INDEX_PATH, index)
    return index


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_manifest() -> dict[str, Any]:
    manifest = read_json(MANIFEST_PATH)
    if manifest.get("schema") != artifact_payload("route_a_manifest")["schema"]:
        raise V22Error(f"{MANIFEST_PATH} is not a v22 Route-A manifest")
    declared = manifest.get("manifest_sha256")
    if declared != digest({key: value for key, value in manifest.items() if key != "manifest_sha256"}):
        raise V22Error("Route-A manifest self-hash does not verify")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="base_v22 Route A canonical16 controller")
    parser.add_argument("--profile", choices=tuple(ROUTE_A_PROFILES), default="wave1")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--only-row", default=None)
    validate_parser = sub.add_parser("validate-row")
    validate_parser.add_argument("row_id")
    seal_parser = sub.add_parser("seal-row")
    seal_parser.add_argument("row_id")
    sub.add_parser("index")
    args = parser.parse_args(argv)
    configure_route_a(args.profile)

    if args.command == "build":
        if ROUTE_A_ROOT.exists() and any(ROUTE_A_ROOT.iterdir()):
            raise V22Error(f"Route-A root is not empty: {ROUTE_A_ROOT}; refusing to overwrite evidence")
        ROUTE_A_ROOT.mkdir(parents=True, exist_ok=True)
        manifest = build_manifest()
        queue = build_queue(manifest)
        write_json(MANIFEST_PATH, manifest)
        write_json(QUEUE_PATH, queue)
        lane_cells = {
            str(gpu): sorted(cell for cell, assigned in ROUTE_A_GPU_BY_CELL.items() if assigned == gpu)
            for gpu in sorted(set(ROUTE_A_GPU_BY_CELL.values()))
        }
        rows_by_gpu = {
            str(gpu): sum(1 for row in manifest["rows"] if row["physical_gpu"] == gpu)
            for gpu in sorted(set(ROUTE_A_GPU_BY_CELL.values()))
        }
        write_json(RUNTIME_PLAN_PATH, artifact_payload(
            "route_a_runtime_plan",
            status="READY",
            created_utc=_now(),
            manifest_sha256=manifest["manifest_sha256"],
            queue_sha256=queue["queue_sha256"],
            lane_cells=lane_cells,
            rows_by_gpu=rows_by_gpu,
            device_contract=(
                "no CUDA_VISIBLE_DEVICES; ACCELERATE_TORCH_DEVICE=cuda:N; "
                f"N in {sorted(set(ROUTE_A_GPU_BY_CELL.values()))}"
            ),
            wandb_mode="disabled",
            max_live_processes=len(ROUTE_A_GPU_BY_CELL),
            stop_rule="stop scheduling on first nonzero exit or post-exit validation failure; no retries",
        ))
        print(f"BUILT manifest={MANIFEST_PATH} rows={len(manifest['rows'])}", flush=True)
        return 0

    if args.command == "run":
        manifest = _load_manifest()
        return run_lanes(manifest, only_row=args.only_row)

    if args.command == "validate-row":
        manifest = _load_manifest()
        rows = {row["row_id"]: row for row in manifest["rows"]}
        if args.row_id not in rows:
            raise V22Error(f"unknown row_id {args.row_id!r}")
        receipt = validate_row_completion(rows[args.row_id])
        print(json.dumps({"status": receipt["status"], "row_id": receipt["row_id"], "headline": receipt["headline"]}, indent=2))
        return 0

    if args.command == "seal-row":
        # Retroactively seal a row whose eval process exited 0 but whose receipt
        # was not written (e.g. a controller-side validation bug).  The process
        # record is taken from the controller-written FAILURE artifact, never
        # reconstructed by hand.
        manifest = _load_manifest()
        rows = {row["row_id"]: row for row in manifest["rows"]}
        if args.row_id not in rows:
            raise V22Error(f"unknown row_id {args.row_id!r}")
        row = rows[args.row_id]
        if load_sealed_receipt(row) is not None:
            raise V22Error(f"row {args.row_id} already has a sealed receipt; refusing to re-seal")
        failure = read_json(FAILURE_PATH)
        record = next(
            (item for item in failure.get("failures", []) if item.get("row_id") == args.row_id),
            None,
        )
        if record is None or record.get("reason") != "POSTEXIT_VALIDATION":
            raise V22Error(f"no POSTEXIT_VALIDATION failure record for {args.row_id}; refusing to seal")
        process = record.get("process")
        if not isinstance(process, Mapping) or process.get("exit_code") != 0:
            raise V22Error(f"failure record for {args.row_id} does not show a clean exit-0 process")
        receipt = seal_row(row, process)
        print(json.dumps({"status": receipt["status"], "row_id": receipt["row_id"], "receipt_path": receipt["receipt_path"]}, indent=2))
        return 0

    if args.command == "index":
        manifest = _load_manifest()
        index = build_index(manifest)
        print(f"INDEX {EVIDENCE_INDEX_PATH} rows={index['row_count']} missing={index['missing_rows']}", flush=True)
        return 0 if not index["missing_rows"] else 3

    raise V22Error(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V22Error as exc:
        print(f"M22 FAIL: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2)
