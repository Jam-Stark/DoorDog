#!/usr/bin/env python3
"""Prepare and run the paired pull-v0 P0-F frozen-W zero-shot cells."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
LOG_ROOT = ROOT / "logs_eval" / "a2_piper_pull_v0" / "p0f_zero_shot"
PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P0F_ZERO_SHOT_PLAN_R3.json"
SOURCE_FREEZE_PATH = EVIDENCE_ROOT / "PULL_V0_SOURCE_FREEZE.json"
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
PHYSICAL_GPU = 4
CELL_ARTIFACT_NAMES = {"out": "out_runtime", "in": "in"}

CELL_CONFIG_SOURCES = {
    "out": ROOT
    / "logs_rl/a2_piper_full_stage_a2_pull/pull_v0_p0c/out_resolved/config.yaml",
    "in": ROOT
    / "logs_rl/a2_piper_full_stage_a2_pull/pull_v0_p0c/in_telemetry/config.yaml",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M:%S HKT")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _copy_exact(source: Path, destination: Path, expected_sha256: str) -> None:
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError(source)
    if _sha256(source) != expected_sha256:
        raise RuntimeError(f"Source hash mismatch: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_file() or destination.is_symlink():
            raise RuntimeError(f"Existing P0-F input is not a regular file: {destination}")
        if _sha256(destination) != expected_sha256:
            raise RuntimeError(f"Existing P0-F input hash mismatch: {destination}")
    else:
        shutil.copy2(source, destination)
    destination.chmod(0o444)


def _cell_argv(direction: str, checkpoint: Path) -> list[str]:
    cell_root = LOG_ROOT / CELL_ARTIFACT_NAMES[direction]
    eval_output = cell_root / "eval"
    hydra_root = cell_root / "hydra"
    return [
        str(PYTHON),
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=full",
        "+auto_load_latest=false",
        "+num_envs=16",
        "+seed=0",
        "+headless=true",
        "algo.config.eval.num_eval_episodes=16",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=true",
        "algo.config.eval.save_goal_reached_only=false",
        "algo.config.eval.save_trajectories=false",
        "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=16",
        "+simulator.config.render_results=false",
        "+simulator.config.cameras.enable_cameras=false",
        f"eval_output_dir={eval_output}",
        f"eval_log_dir={hydra_root}",
        f"env.config.save_rendering_dir={cell_root / 'renderings'}",
        f"+device=cuda:{PHYSICAL_GPU}",
        f"hydra.run.dir={hydra_root}",
    ]


def _load_existing_plan() -> dict | None:
    if not PLAN_PATH.exists():
        return None
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    declared_sha256 = plan.pop("plan_sha256", None)
    actual_sha256 = _canonical_sha256(plan)
    plan["plan_sha256"] = declared_sha256
    if declared_sha256 != actual_sha256:
        raise RuntimeError("Existing P0-F plan digest is invalid")
    if plan.get("status") != "READY" or set(plan.get("cells", {})) != {"out", "in"}:
        raise RuntimeError("Existing P0-F plan is not a READY paired plan")
    for direction, cell in plan["cells"].items():
        checkpoint = ROOT / cell["checkpoint_input"]["path"]
        config = ROOT / cell["config_input"]["path"]
        if _sha256(checkpoint) != cell["checkpoint_input"]["sha256"]:
            raise RuntimeError(f"{direction}: materialized checkpoint changed after plan freeze")
        if _sha256(config) != cell["config_input"]["sha256"]:
            raise RuntimeError(f"{direction}: materialized config changed after plan freeze")
        source_config = ROOT / cell["config_input"]["source_path"]
        if _sha256(source_config) != cell["config_input"]["sha256"]:
            raise RuntimeError(f"{direction}: source config changed after plan freeze")
    return plan


def prepare() -> dict:
    existing = _load_existing_plan()
    if existing is not None:
        return existing
    source_freeze = json.loads(SOURCE_FREEZE_PATH.read_text(encoding="utf-8"))
    frozen = source_freeze["warm_checkpoint"]
    frozen_source = Path(frozen["source_path_read_only"])
    if _sha256(frozen_source) != frozen["sha256"]:
        raise RuntimeError("Frozen W checkpoint no longer matches the source-freeze receipt")

    cells = {}
    for direction, config_source in CELL_CONFIG_SOURCES.items():
        input_root = LOG_ROOT / direction / "input"
        checkpoint = input_root / "model_step_002500.pt"
        config = input_root / "config.yaml"
        _copy_exact(frozen_source, checkpoint, frozen["sha256"])
        config_sha256 = _sha256(config_source)
        _copy_exact(config_source, config, config_sha256)
        config_value = yaml.safe_load(config.read_text(encoding="utf-8"))
        env_config = config_value["env"]["config"]
        expected_io = direction
        if env_config["a2_pull_door_open_io"] != expected_io:
            raise RuntimeError(f"{direction}: copied config IO does not match its cell")
        if env_config["a2_pull_door_open_lr"] != "right":
            raise RuntimeError(f"{direction}: P0-F requires right-hinged cells")
        if config_value["robot"]["dof_effort_limit_list"][-2:] != [45.0, 45.0]:
            raise RuntimeError(f"{direction}: P0-F finger effort is not the frozen 45 N profile")
        if [
            config_value["robot"]["control"]["stiffness"]["arm_j7"],
            config_value["robot"]["control"]["stiffness"]["arm_j8"],
        ] != [1300.0, 1300.0]:
            raise RuntimeError(f"{direction}: P0-F finger stiffness is not 1300")
        if [
            config_value["robot"]["control"]["damping"]["arm_j7"],
            config_value["robot"]["control"]["damping"]["arm_j8"],
        ] != [32.0, 32.0]:
            raise RuntimeError(f"{direction}: P0-F finger damping is not 32")
        argv = _cell_argv(direction, checkpoint)
        env_contract = {
            "ACCELERATE_TORCH_DEVICE": f"cuda:{PHYSICAL_GPU}",
            "WANDB_MODE": "offline",
            "HYDRA_FULL_ERROR": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(ROOT),
            "CUDA_VISIBLE_DEVICES": "UNSET",
        }
        cells[direction] = {
            "direction": direction,
            "seed": 0,
            "num_envs": 16,
            "episodes": 16,
            "first_episode_only": True,
            "checkpoint_input": {
                "path": str(checkpoint.relative_to(ROOT)),
                "sha256": _sha256(checkpoint),
                "source_path_read_only": str(frozen_source),
                "source_sha256": frozen["sha256"],
            },
            "config_input": {
                "path": str(config.relative_to(ROOT)),
                "sha256": _sha256(config),
                "source_path": str(config_source.relative_to(ROOT)),
            },
            "artifact_root": str(
                (LOG_ROOT / CELL_ARTIFACT_NAMES[direction]).relative_to(ROOT)
            ),
            "eval_output": str(
                (LOG_ROOT / CELL_ARTIFACT_NAMES[direction] / "eval").relative_to(ROOT)
            ),
            "hydra_output": str(
                (LOG_ROOT / CELL_ARTIFACT_NAMES[direction] / "hydra").relative_to(ROOT)
            ),
            "argv": argv,
            "env": env_contract,
            "command_sha256": _canonical_sha256({"argv": argv, "env": env_contract}),
            "threshold_mode": "report_only",
            "policy_update": False,
        }

    plan = {
        "schema_version": "pull_v0_p0f_zero_shot_plan_v1",
        "generated_at_hkt": _hkt_now(),
        "status": "READY",
        "base_sha": source_freeze["base_commit"],
        "warm_checkpoint_sha256": frozen["sha256"],
        "actuator_profile": {
            "finger_effort_n": [45.0, 45.0],
            "finger_stiffness": [1300.0, 1300.0],
            "finger_damping": [32.0, 32.0],
            "effort_provenance": "ESTIMATE_ONLY",
            "gripper_material": "RESOLVED_V20_G4",
        },
        "pairing_contract": {
            "same_seed": True,
            "same_num_envs": True,
            "same_frozen_policy": True,
            "same_actuator_and_material_profile": True,
            "only_direction_contract_differs": True,
            "runtime_scenario_rows_must_match_by_env_id": True,
        },
        "gpu_resource_lease": {
            "authorized_physical_devices": [4, 5, 6],
            "selected_physical_device": PHYSICAL_GPU,
            "gpu7_compute_authorized": False,
        },
        "cells": cells,
        "interpretation": "Report-only behavioral fingerprint; this plan cannot choose W versus S.",
    }
    plan["plan_sha256"] = _canonical_sha256(plan)
    _write_json(PLAN_PATH, plan)
    return plan


def run(direction: str) -> int:
    plan = prepare()
    cell = plan["cells"][direction]
    output_root = ROOT / cell["eval_output"]
    metrics_path = output_root / "metrics_eval.json"
    process_receipt_path = ROOT / cell["artifact_root"] / "process_receipt.json"
    if metrics_path.exists() or process_receipt_path.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing P0-F {direction} result; use a new evidence namespace"
        )
    environment = os.environ.copy()
    environment.pop("CUDA_VISIBLE_DEVICES", None)
    environment.update(
        {
            "ACCELERATE_TORCH_DEVICE": f"cuda:{PHYSICAL_GPU}",
            "WANDB_MODE": "offline",
            "HYDRA_FULL_ERROR": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(ROOT),
        }
    )
    started = _hkt_now()
    completed = subprocess.run(cell["argv"], cwd=ROOT, env=environment, check=False)
    ended = _hkt_now()
    receipt = {
        "schema_version": "pull_v0_p0f_process_receipt_v1",
        "direction": direction,
        "started_at_hkt": started,
        "ended_at_hkt": ended,
        "natural_exit": True,
        "exit_code": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "plan_sha256": plan["plan_sha256"],
        "command_sha256": cell["command_sha256"],
        "physical_gpu": PHYSICAL_GPU,
        "metrics_path": str(metrics_path.relative_to(ROOT)),
        "metrics_sha256": _sha256(metrics_path) if metrics_path.is_file() else None,
    }
    _write_json(process_receipt_path, receipt)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run-direction", choices=("out", "in"))
    args = parser.parse_args()
    if args.prepare == (args.run_direction is not None):
        parser.error("select exactly one of --prepare or --run-direction")
    if args.prepare:
        plan = prepare()
        print(json.dumps({"plan": str(PLAN_PATH), "plan_sha256": plan["plan_sha256"]}, indent=2))
        return 0
    return run(args.run_direction)


if __name__ == "__main__":
    raise SystemExit(main())
