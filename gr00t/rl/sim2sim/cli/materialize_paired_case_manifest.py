#!/usr/bin/env python3
"""Materialize the fixed legacy-door paired campaign cases."""

from __future__ import annotations

import argparse
import copy
import json
import math
import subprocess
from pathlib import Path

from gr00t.rl.sim2sim.doors.spec import DoorInstanceSpec
from gr00t.rl.sim2sim.robot.contract import resolved_a2_piper_contract


DISTILLATION_COMMIT = "a197255212fa65dd9e02337b7971daac71c944fe"
DISTILLATION_DOOR_PATH = "gr00t/rl/isaac_utils/playground/env_rand/door.py"
MANIFEST_ID = "a2_piper_grpo_step10_legacy_door_subset_r1"
INITIAL_STATE_ID = "scene_home_fixed_v1"
CHECKPOINT_GLOBAL_STEP = 10


CASES = (
    ("p00_baseline", 41001, {}),
    ("p01_mass80", 41002, {"mass_kg": 80.0}),
    ("p02_mass120", 41003, {"mass_kg": 120.0}),
    ("p03_width080", 41004, {"width_m": 0.8}),
    ("p04_width110", 41005, {"width_m": 1.1}),
    ("p05_height190", 41006, {"height_m": 1.9, "handle_height_m": 0.85}),
    ("p06_height220", 41007, {"height_m": 2.2, "handle_height_m": 1.0}),
    ("p07_drive_k10_cap25", 41008, {"hinge_stiffness": 10.0, "hinge_effort": 2.5}),
)


def _inertia(mass: float, width: float, height: float, thickness: float) -> list[float]:
    return [
        mass * (width * width + height * height) / 12.0,
        mass * (thickness * thickness + height * height) / 12.0,
        mass * (thickness * thickness + width * width) / 12.0,
    ]


def _case_spec(base: dict[str, object], case_id: str, changes: dict[str, float]) -> dict[str, object]:
    spec = copy.deepcopy(base)
    geometry = spec["geometry"]
    kinematics = spec["kinematics"]
    dynamics = spec["dynamics"]
    hinge = dynamics["hinge"]
    handle = dynamics["handle"]

    width = changes.get("width_m", 0.9)
    height = changes.get("height_m", 2.0)
    mass = changes.get("mass_kg", 100.0)
    hinge_stiffness = changes.get("hinge_stiffness", 2.0)
    hinge_effort = changes.get("hinge_effort", 4.5)
    geometry["panel_width_m"] = width
    geometry["panel_height_m"] = height
    geometry["handle_height_m"] = changes.get("handle_height_m", 0.9)
    dynamics["panel_mass_kg"] = mass
    dynamics["panel_diagonal_inertia_kgm2"] = _inertia(
        mass, width, height, float(geometry["panel_thickness_m"])
    )
    hinge["stiffness_nm_per_rad"] = hinge_stiffness
    hinge["damping_nms_per_rad"] = 50.0
    hinge["effort_cap_nm"] = hinge_effort
    hinge["static_friction_effort"] = 0.0
    hinge["dynamic_friction_effort"] = 0.0
    hinge["viscous_friction_coefficient"] = 0.0
    handle["static_friction_effort"] = 0.0
    handle["dynamic_friction_effort"] = 0.0
    handle["viscous_friction_coefficient"] = 0.0
    kinematics["hinge_side"] = "right"
    kinematics["open_direction"] = "out"
    kinematics["latch_mode"] = "no_latch"
    spec["named_sites"]["door_passage_center"]["position_m"] = [0.0, 0.0, height / 2.0]
    spec["identity"] = {
        "family_id": "a2_piper_legacy_lever_paired_subdomain",
        "instance_id": case_id,
        "source_commit": DISTILLATION_COMMIT,
        "source_path": DISTILLATION_DOOR_PATH,
        "materialization": "EXPLICIT_VALUES_NO_RNG",
    }
    requested = {
        "door_weight_kg": mass,
        "hinge_damping_native": 50.0,
        "hinge_stiffness_native": hinge_stiffness,
        "hinge_effort_limit_nm": hinge_effort,
    }
    spec["backend_overrides"]["isaac_physx"]["mechanics_faces"] = {
        "requested_trace_config_rad": requested,
        "usd_degree_readback": {
            "door_weight_kg": mass,
            "hinge_damping_native": 50.0 * 180.0 / math.pi,
            "hinge_stiffness_native": hinge_stiffness * 180.0 / math.pi,
            "hinge_effort_limit_nm": hinge_effort,
        },
    }
    spec["backend_overrides"]["mujoco"] = {
        "door_resistance_mode": "capped_position_actuator",
        "frictionloss_source": "dynamic_friction_effort",
        "calibration_status": "paired_legacy_subdomain",
    }
    DoorInstanceSpec(spec).validate()
    if DoorInstanceSpec(spec).friction_classification != "FRICTION_SEMANTICS_ALIGNED":
        raise ValueError(f"paired case {case_id} leaves the aligned-friction subdomain")
    return spec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-instance", required=True, type=Path)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--trace-schema-source-commit", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    base = json.loads(args.base_instance.resolve(strict=True).read_text(encoding="utf-8"))
    bundle_dir = args.bundle_dir.resolve(strict=True)
    bundle = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    output = args.output_dir.resolve()
    instance_dir = output / "door_instances"
    instance_dir.mkdir(parents=True, exist_ok=True)
    contract = resolved_a2_piper_contract()
    case_entries = []
    for episode_index, (case_id, seed, changes) in enumerate(CASES):
        spec = _case_spec(base, case_id, changes)
        instance_path = instance_dir / f"{case_id}.json"
        instance_path.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        case_entries.append(
            {
                "episode_index": episode_index,
                "case_id": case_id,
                "seed": seed,
                "door_instance_id": case_id,
                "door_instance_path": str(instance_path.relative_to(output)),
            }
        )

    current_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    manifest = {
        "schema_version": "doordog.sim2sim.paired_case_manifest.v1",
        "manifest_id": MANIFEST_ID,
        "case_count": len(case_entries),
        "cases": case_entries,
        "policy_bundle": {
            "bundle_id": bundle["bundle_id"],
            "artifact_status": bundle["artifact_status"],
            "path": str(bundle_dir),
            "source_commit": bundle["native_loader"]["source_commit"],
            "checkpoint_global_step": CHECKPOINT_GLOBAL_STEP,
        },
        "paired_trace_schema": {
            "schema_version": "doordog.sim2sim.paired_trace_row.v1",
            "source_commit": args.trace_schema_source_commit,
            "source_path": "gr00t/rl/sim2sim/schemas/paired_trace_row.schema.json",
            "transport": "UTF-8 JSON Lines; one row after every 200 Hz physics step",
        },
        "legacy_isaac_consumer": {
            "source_commit": DISTILLATION_COMMIT,
            "source_path": DISTILLATION_DOOR_PATH,
            "additive_only": True,
            "exact_cfg_fields": [
                "rand_door_width",
                "rand_door_height",
                "rand_door_handle_height",
                "rand_door_handle_width",
                "rand_door_weight",
                "rand_door_handle_type",
                "rand_door_open_lr",
                "rand_door_open_io",
                "rand_axle_length",
                "rand_handle_length",
                "rand_handle_radius",
                "rand_hinge_drive_max_force",
                "rand_hinge_drive_stiffness",
                "rand_handle_drive_max_force"
            ],
            "fixed_old_builder_semantics": {
                "build_latch": False,
                "hinge_damping_nms_per_rad": 50.0,
                "handle_damping_nms_per_rad": 0.5,
                "handle_stiffness_nm_per_rad": 50.0,
                "handle_type": "lever"
            }
        },
        "subdomain_constraints": {
            "description": "Only fields realizable by the distillation branch legacy door.py are varied.",
            "hinge_side": "right",
            "open_direction": "out",
            "latch_mode": "no_latch",
            "static_friction_effort": 0.0,
            "dynamic_friction_effort": 0.0,
            "viscous_friction_coefficient": 0.0,
            "friction_rule": "tau_static == tau_dynamic; FRICTION_SEMANTIC_GAP excluded",
            "material_randomization": False,
            "rng_materialization": "EXPLICIT_VALUES_NO_RNG"
        },
        "fixed_initial_state": {
            "initial_state_id": INITIAL_STATE_ID,
            "root_position_m": [0.0, 0.0, 0.62],
            "root_quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
            "robot_joint_names": list(contract.sim_joint_names),
            "robot_qpos": list(contract.default_dof_pos),
            "robot_qvel": [0.0] * len(contract.sim_joint_names),
            "door_hinge_rad": 0.0,
            "door_handle_rad": 0.0,
            "door_qvel_radps": [0.0, 0.0],
            "student_lstm": "RESET_ZERO",
            "previous_applied_action": [0.0] * 19,
            "previous_raw_delta_action": [0.0] * 6,
            "a2_base_history": "FIRST_54D_FRAME_REPLICATED_30_TIMES",
            "camera_cache": "CAPTURE_AT_TIME_ZERO_VALID"
        },
        "episode_contract": {
            "physics_hz": bundle["timebase"]["physics_hz"],
            "policy_hz": bundle["timebase"]["control_hz"],
            "control_decimation": bundle["timebase"]["control_decimation"],
            "horizon_s": 20.0,
            "horizon_policy_steps": 1000,
            "base_height_termination_m": 0.3,
            "arm_delta_enable": "FIXED_STAGE_ONE; production stage machine is not migrated",
            "unlatch_threshold_handle_rad": math.pi / 6.0,
            "open_crossing_threshold_hinge_rad": 0.174533,
            "task_metric_source": "DIRECT_DOOR_JOINT_STATE"
        },
        "expectation": {
            "student_level": "PILOT_GRPO_STEP10",
            "claim": "PIPELINE_AND_PHYSICS_EVIDENCE_ONLY",
            "failed_episode_policy": "KEEP_COMPLETE_TRACE_AND_TYPED_TERMINATION",
            "paired_purpose": "TRAJECTORY_AND_MECHANICS_COMPARISON_NOT_SUCCESS_RATE"
        },
        "provenance": {
            "identity_policy": "git_commit_plus_path",
            "materializer_commit_at_execution": current_commit,
            "materializer_path": "gr00t/rl/sim2sim/cli/materialize_paired_case_manifest.py",
            "strict_exact_hash": False
        }
    }
    (output / "paired_case_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"manifest_id": MANIFEST_ID, "case_count": len(case_entries)}, sort_keys=True))


if __name__ == "__main__":
    main()
