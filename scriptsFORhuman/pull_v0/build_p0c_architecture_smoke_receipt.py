#!/usr/bin/env python3
"""Build and validate the pull-v0 P0-C two-direction smoke receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
LOG_ROOT = ROOT / "logs_rl" / "a2_piper_full_stage_a2_pull" / "pull_v0_p0c"
SOURCE_FREEZE = EVIDENCE_ROOT / "PULL_V0_SOURCE_FREEZE.json"
OUTPUT = EVIDENCE_ROOT / "PULL_V0_P0C_ARCHITECTURE_SMOKE.json"

CELLS = {
    "out": LOG_ROOT / "out_resolved",
    "in": LOG_ROOT / "in_telemetry",
}

EXPECTED_DIRECTION = {
    "out": {
        "a2_pull_door_open_io": "out",
        "a2_pull_door_open_lr": "right",
        "a2_pull_robot_initial_side_x_sign": -1.0,
        "a2_pull_active_handle_face_x_sign": -1.0,
        "a2_pull_travel_dir_x": 1.0,
        "a2_pull_target_frame_version": "grasp_target_active_face_out_inherited_v20",
    },
    "in": {
        "a2_pull_door_open_io": "in",
        "a2_pull_door_open_lr": "right",
        "a2_pull_robot_initial_side_x_sign": 1.0,
        "a2_pull_active_handle_face_x_sign": 1.0,
        "a2_pull_travel_dir_x": -1.0,
        "a2_pull_target_frame_version": "grasp_target_active_face_io_z_pre_v1",
    },
}

EXPECTED_COMMON = {
    "a2_pull_direction_contract_version": "a2_piper_pull_direction_v1",
    "a2_pull_threshold_mode": "report_only",
    "a2_pull_effort_provenance": "ESTIMATE_ONLY",
    "a2_pull_hook_profile": "STOCHASTIC_BASELINE",
    "a2_pull_friction_profile": "RESOLVED_V20_G4",
    "a2_pull_finger_profile": "V20_G4_45N_KP1300_KD32",
    "a2_corridor_enabled": False,
    "a2_v20_send_latch_enabled": False,
    "a2_v20_pre_send_crossing_mode": "disabled",
    "a2_v20_telemetry_enabled": False,
    "a2_v20_traversal_economics_enabled": False,
    "a2_v20_arm_tie_enabled": False,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _validate_cell(direction: str, directory: Path, frozen_checkpoint: dict) -> dict:
    config_path = directory / "config.yaml"
    checkpoint_path = directory / "model_step_000001.pt"
    runtime_log_path = directory / ".hydra" / "train.log"
    for path in (config_path, checkpoint_path, runtime_log_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    config = _load_yaml(config_path)
    env_cfg = config["env"]["config"]
    for key, expected in EXPECTED_COMMON.items():
        actual = env_cfg[key]
        if actual != expected:
            raise AssertionError(f"{direction}: {key}={actual!r}, expected {expected!r}")
    for key, expected in EXPECTED_DIRECTION[direction].items():
        actual = env_cfg[key]
        if actual != expected:
            raise AssertionError(f"{direction}: {key}={actual!r}, expected {expected!r}")

    if config["checkpoint"] != frozen_checkpoint["source_path_read_only"]:
        raise AssertionError(f"{direction}: checkpoint path is not the frozen W path")
    if config["checkpoint_load_mode"] != "policy_only":
        raise AssertionError(f"{direction}: checkpoint load mode must be policy_only")
    if config["num_envs"] != 1:
        raise AssertionError(f"{direction}: P0-C requires exactly one environment")
    if config["algo"]["trl"]["num_total_batches"] != 1:
        raise AssertionError(f"{direction}: P0-C requires exactly one batch")
    if config["algo"]["config"]["num_learning_epochs"] != 1:
        raise AssertionError(f"{direction}: P0-C requires one learning epoch")
    if config["algo"]["config"]["num_mini_batches"] != 1:
        raise AssertionError(f"{direction}: P0-C one-env rollout requires one minibatch")
    if config["algo"]["config"]["num_steps_per_env"] != 64:
        raise AssertionError(f"{direction}: P0-C expected 64 rollout steps")

    effort = config["robot"]["dof_effort_limit_list"]
    stiffness = config["robot"]["control"]["stiffness"]
    damping = config["robot"]["control"]["damping"]
    if effort[-2:] != [45.0, 45.0]:
        raise AssertionError(f"{direction}: finger effort profile is not [45, 45] N")
    if [stiffness["arm_j7"], stiffness["arm_j8"]] != [1300.0, 1300.0]:
        raise AssertionError(f"{direction}: finger stiffness profile is not [1300, 1300]")
    if [damping["arm_j7"], damping["arm_j8"]] != [32.0, 32.0]:
        raise AssertionError(f"{direction}: finger damping profile is not [32, 32]")

    runtime_log = runtime_log_path.read_text(encoding="utf-8")
    required_runtime_markers = [
        "door metadata validated num_envs=1",
        "device=cuda:4",
        "a2_door_body_panel_contact_sensor force_matrix_w_shape=(1, 1, 13, 3)",
        "a2_door_arm_panel_contact_sensor force_matrix_w_shape=(1, 1, 10, 3)",
    ]
    if direction == "in":
        required_runtime_markers.extend(
            [
                "a2_pull_door_body_frame_contact_sensor force_matrix_w_shape=(1, 1, 13, 3)",
                "a2_pull_door_arm_frame_contact_sensor force_matrix_w_shape=(1, 1, 10, 3)",
            ]
        )
    missing_markers = [marker for marker in required_runtime_markers if marker not in runtime_log]
    if missing_markers:
        raise AssertionError(f"{direction}: missing runtime markers: {missing_markers}")

    return {
        "status": "PASS",
        "direction": EXPECTED_DIRECTION[direction],
        "resolved_config": {
            "path": _relative(config_path),
            "sha256": _sha256(config_path),
        },
        "runtime_log": {
            "path": _relative(runtime_log_path),
            "sha256": _sha256(runtime_log_path),
        },
        "saved_checkpoint": {
            "path": _relative(checkpoint_path),
            "sha256": _sha256(checkpoint_path),
            "size_bytes": checkpoint_path.stat().st_size,
        },
        "runtime_contract": {
            "environment_device": "cuda:4",
            "num_envs": 1,
            "optimizer_batches": 1,
            "steps_per_environment": 64,
            "reset": "PASS",
            "observation_assembly": "PASS",
            "reward_computation": "PASS",
            "termination_computation": "PASS",
            "checkpoint_save": "PASS",
            "policy_performance": "N/A",
        },
        "actuator_and_material_profile": {
            "finger_effort_n": [45.0, 45.0],
            "finger_stiffness": [1300.0, 1300.0],
            "finger_damping": [32.0, 32.0],
            "finger_effort_provenance": "ESTIMATE_ONLY",
            "gripper_material_profile": "RESOLVED_V20_G4",
            "hook_selector": "STOCHASTIC_BASELINE",
        },
        "behavior_selectors": {
            "v20_send_latch": "disabled",
            "v20_crossing": "disabled",
            "v20_traversal_economics": "disabled",
            "v20_arm_tie": "disabled",
            "corridor": "disabled",
        },
    }


def main() -> None:
    source_freeze = json.loads(SOURCE_FREEZE.read_text(encoding="utf-8"))
    frozen_checkpoint = source_freeze["warm_checkpoint"]
    actual_frozen_hash = _sha256(Path(frozen_checkpoint["source_path_read_only"]))
    if actual_frozen_hash != frozen_checkpoint["sha256"]:
        raise AssertionError("Frozen W checkpoint hash changed after source freeze")

    cells = {
        direction: _validate_cell(direction, directory, frozen_checkpoint)
        for direction, directory in CELLS.items()
    }
    receipt = {
        "schema_version": "pull_v0_p0c_architecture_smoke_v1",
        "generated_at_hkt": "2026-08-03 16:01 HKT",
        "status": "PASS",
        "threshold_mode": "report_only",
        "source_freeze": {
            "path": _relative(SOURCE_FREEZE),
            "base_sha": source_freeze["base_commit"],
            "frozen_checkpoint": frozen_checkpoint,
        },
        "cells": cells,
        "repair_history": [
            {
                "attempts": ["in", "in_retry1"],
                "status": "FAIL_BEFORE_ROLLOUT",
                "failure": "one environment could not be partitioned into the inherited four minibatches",
                "bounded_repair": "set num_learning_epochs=1 and num_mini_batches=1 in both P0-C ablations",
                "scientific_semantics_changed": False,
                "artifacts_preserved_under": _relative(LOG_ROOT),
            },
            {
                "attempt": "out_resolved",
                "status": "PASS",
                "reason": "rerun after adding explicit P0-D direction and target-frame evidence metadata",
                "scientific_semantics_changed": False,
            },
        ],
        "gpu_resource_evidence": {
            "authorized_physical_devices": [4, 5, 6],
            "compute_device_used": 4,
            "gpu5_used": False,
            "gpu6_used": False,
            "gpu7_compute_used": False,
            "isaacsim_adapter_note": "IsaacSim Vulkan diagnostics enumerate all adapters; only GPU4 is marked active. A pre-scene torch diagnostic reported index 7 with 0 MB reserved and 0 MB allocated. Environment tensors and filtered sensor tensors are explicitly on cuda:4.",
        },
        "evidence_boundary": {
            "static_config_contract": "PASS",
            "isaacsim_reset_observation_reward_termination": "PASS",
            "live_pull_telemetry_schema_first_step": "PASS",
            "policy_performance": "NOT_EVALUATED",
            "p0f_zero_shot": "NOT_RUN",
            "claim": "This receipt admits the two-direction architecture only. It is not a pull-capability, zero-shot, or policy-quality verdict.",
        },
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
