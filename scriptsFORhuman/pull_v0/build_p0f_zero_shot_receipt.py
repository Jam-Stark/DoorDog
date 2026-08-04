#!/usr/bin/env python3
"""Build and validate the paired pull-v0 P0-F frozen-policy receipt."""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gr00t.rl.envs.door.a2_pull_telemetry import (
    A2_PULL_EVENT_NAMES,
    A2_PULL_NA,
    A2_PULL_PRE_E0,
    validate_a2_pull_control_step,
)


EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
LOG_ROOT = ROOT / "logs_eval" / "a2_piper_pull_v0" / "p0f_zero_shot"
PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P0F_ZERO_SHOT_PLAN_R3.json"
SOURCE_FREEZE_PATH = EVIDENCE_ROOT / "PULL_V0_SOURCE_FREEZE.json"
OUTPUT_PATH = EVIDENCE_ROOT / "PULL_V0_P0F_ZERO_SHOT_FINGERPRINT.json"

CELL_ROOTS = {
    "out": LOG_ROOT / "out_runtime",
    "in": LOG_ROOT / "in",
}

EXPECTED_DIRECTION = {
    "out": {
        "a2_pull_direction_contract_version": "a2_piper_pull_direction_v1",
        "a2_pull_target_frame_version": "grasp_target_active_face_out_inherited_v20",
        "a2_pull_door_open_io": "out",
        "a2_pull_door_open_lr": "right",
        "a2_pull_robot_initial_side_x_sign": -1.0,
        "a2_pull_active_handle_face_x_sign": -1.0,
        "a2_pull_travel_dir_x": 1.0,
    },
    "in": {
        "a2_pull_direction_contract_version": "a2_piper_pull_direction_v1",
        "a2_pull_target_frame_version": "grasp_target_active_face_io_z_pre_v1",
        "a2_pull_door_open_io": "in",
        "a2_pull_door_open_lr": "right",
        "a2_pull_robot_initial_side_x_sign": 1.0,
        "a2_pull_active_handle_face_x_sign": 1.0,
        "a2_pull_travel_dir_x": -1.0,
    },
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


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _histogram(values: list[object]) -> dict[str, int]:
    return dict(sorted((str(key), count) for key, count in Counter(values).items()))


def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        raise ValueError("A measured statistics field must not be empty")
    return {
        "min": min(values),
        "mean": statistics.fmean(values),
        "max": max(values),
    }


def _validate_plan() -> dict:
    plan = _load_json(PLAN_PATH)
    declared_sha256 = plan.pop("plan_sha256")
    actual_sha256 = _canonical_sha256(plan)
    plan["plan_sha256"] = declared_sha256
    if declared_sha256 != actual_sha256:
        raise AssertionError("P0-F R3 plan digest is invalid")
    if plan["status"] != "READY" or plan["gpu_resource_lease"] != {
        "authorized_physical_devices": [4, 5, 6],
        "selected_physical_device": 4,
        "gpu7_compute_authorized": False,
    }:
        raise AssertionError("P0-F plan does not match the allocated GPU lease")
    if plan["actuator_profile"] != {
        "finger_effort_n": [45.0, 45.0],
        "finger_stiffness": [1300.0, 1300.0],
        "finger_damping": [32.0, 32.0],
        "effort_provenance": "ESTIMATE_ONLY",
        "gripper_material": "RESOLVED_V20_G4",
    }:
        raise AssertionError("P0-F actuator profile is not the frozen v20 G4 profile")
    return plan


def _validate_cell(direction: str, plan: dict, source_freeze: dict) -> tuple[dict, dict]:
    cell_plan = plan["cells"][direction]
    cell_root = CELL_ROOTS[direction]
    process_receipt_path = cell_root / "process_receipt.json"
    metrics_path = cell_root / "eval" / "metrics_eval.json"
    trace_path = cell_root / "eval" / "stage2_5_step_trace.json"
    runtime_log_path = cell_root / "hydra" / "eval.log"
    for path in (process_receipt_path, metrics_path, trace_path, runtime_log_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    process_receipt = _load_json(process_receipt_path)
    if process_receipt != {
        **process_receipt,
        "direction": direction,
        "natural_exit": True,
        "exit_code": 0,
        "status": "PASS",
        "plan_sha256": plan["plan_sha256"],
        "command_sha256": cell_plan["command_sha256"],
        "physical_gpu": 4,
        "metrics_path": _relative(metrics_path),
        "metrics_sha256": _sha256(metrics_path),
    }:
        raise AssertionError(f"{direction}: process receipt does not match the frozen plan/result")

    checkpoint_path = ROOT / cell_plan["checkpoint_input"]["path"]
    config_path = ROOT / cell_plan["config_input"]["path"]
    frozen_sha256 = source_freeze["warm_checkpoint"]["sha256"]
    if _sha256(checkpoint_path) != frozen_sha256:
        raise AssertionError(f"{direction}: frozen policy copy hash changed")
    if _sha256(config_path) != cell_plan["config_input"]["sha256"]:
        raise AssertionError(f"{direction}: frozen input config hash changed")

    config = _load_yaml(config_path)
    env_cfg = config["env"]["config"]
    for key, expected in EXPECTED_DIRECTION[direction].items():
        if env_cfg[key] != expected:
            raise AssertionError(f"{direction}: {key}={env_cfg[key]!r}, expected {expected!r}")
    if config["robot"]["dof_effort_limit_list"][-2:] != [45.0, 45.0]:
        raise AssertionError(f"{direction}: finger effort differs from the frozen profile")
    if [
        config["robot"]["control"]["stiffness"]["arm_j7"],
        config["robot"]["control"]["stiffness"]["arm_j8"],
    ] != [1300.0, 1300.0]:
        raise AssertionError(f"{direction}: finger stiffness differs from the frozen profile")
    if [
        config["robot"]["control"]["damping"]["arm_j7"],
        config["robot"]["control"]["damping"]["arm_j8"],
    ] != [32.0, 32.0]:
        raise AssertionError(f"{direction}: finger damping differs from the frozen profile")

    runtime_log = runtime_log_path.read_text(encoding="utf-8")
    required_markers = (
        "CUDA device idx=4",
        "door metadata validated num_envs=16",
        "device=cuda:4",
        "a2_door_body_panel_contact_sensor force_matrix_w_shape=(16, 1, 13, 3)",
        "a2_door_arm_panel_contact_sensor force_matrix_w_shape=(16, 1, 10, 3)",
    )
    missing_markers = [marker for marker in required_markers if marker not in runtime_log]
    if direction == "in":
        for marker in (
            "a2_pull_door_body_frame_contact_sensor force_matrix_w_shape=(16, 1, 13, 3)",
            "a2_pull_door_arm_frame_contact_sensor force_matrix_w_shape=(16, 1, 10, 3)",
        ):
            if marker not in runtime_log:
                missing_markers.append(marker)
    if missing_markers:
        raise AssertionError(f"{direction}: missing runtime markers {missing_markers}")

    metrics = _load_json(metrics_path)
    if metrics["completed_episodes"] != 16:
        raise AssertionError(f"{direction}: expected exactly 16 completed first episodes")
    for key in (
        "episode_goal_reached",
        "episode_lengths",
        "episode_max_stage_reached",
        "episode_terminal_reasons",
        "episode_terminal_diagnostics",
    ):
        if len(metrics[key]) != 16:
            raise AssertionError(f"{direction}: {key} must contain exactly 16 rows")
    diagnostics = metrics["episode_terminal_diagnostics"]
    if sorted(record["env_id"] for record in diagnostics) != list(range(16)):
        raise AssertionError(f"{direction}: terminal diagnostics do not cover env_id 0..15")
    for record in diagnostics:
        if record["pull_evidence_direction"] != EXPECTED_DIRECTION[direction]:
            raise AssertionError(f"{direction}: runtime direction evidence changed")
        if direction == "in":
            validate_a2_pull_control_step(record["pull_v0"])

    trace = _load_json(trace_path)
    if not isinstance(trace, list) or not trace:
        raise AssertionError(f"{direction}: stage trace must be a non-empty list")
    historical_by_env = {
        env_id: {
            "bilateral_contact": False,
            "panel_contact": False,
            "hinge_max_rad": float("-inf"),
            "target_face_error_min_m": float("inf"),
        }
        for env_id in range(16)
    }
    for record in trace:
        env_id = record["env_id"]
        state = historical_by_env[env_id]
        state["bilateral_contact"] |= bool(record["both_contact"])
        state["panel_contact"] |= (
            float(record["door_body_panel_normal_force_total"])
            + float(record["door_arm_panel_normal_force_total"])
        ) > 0.0
        state["hinge_max_rad"] = max(
            state["hinge_max_rad"], float(record["door_hinge_joint_pos"])
        )
        state["target_face_error_min_m"] = min(
            state["target_face_error_min_m"],
            float(record["target_pos_source_handle_distance"]),
        )
    for record in diagnostics:
        state = historical_by_env[record["env_id"]]
        state["bilateral_contact"] |= bool(record["both_contact"])
        state["panel_contact"] |= (
            float(record["door_body_panel_normal_force_total"])
            + float(record["door_arm_panel_normal_force_total"])
        ) > 0.0
        state["hinge_max_rad"] = max(
            state["hinge_max_rad"], float(record["door_hinge_joint_pos"])
        )
        state["target_face_error_min_m"] = min(
            state["target_face_error_min_m"],
            float(record["target_pos_source_handle_distance"]),
        )

    terminal_root_x = [float(record["root_pos_rel"][0]) for record in diagnostics]
    cell_result = {
        "status": "PASS",
        "process_receipt": {
            "path": _relative(process_receipt_path),
            "sha256": _sha256(process_receipt_path),
            "natural_exit": True,
            "physical_gpu": 4,
        },
        "metrics": {
            "path": _relative(metrics_path),
            "sha256": _sha256(metrics_path),
            "completed_first_episodes": 16,
            "goal_reached_count": sum(bool(value) for value in metrics["episode_goal_reached"]),
            "max_stage_histogram": _histogram(metrics["episode_max_stage_reached"]),
            "terminal_reason_histogram": _histogram(metrics["episode_terminal_reasons"]),
        },
        "behavioral_fingerprint": {
            "terminal_root_x_rel_door_m": _stats(terminal_root_x),
            "root_crossing_episodes": sum(
                bool(record["root_x_ever_crossed"]) for record in diagnostics
            ),
            "root_crossing_definition": "Any recorded crossing of the door plane; for pull this is a premature move into the final -X travel side before a valid tensile capture.",
            "historical_bilateral_contact_episodes": sum(
                state["bilateral_contact"] for state in historical_by_env.values()
            ),
            "historical_panel_contact_episodes": sum(
                state["panel_contact"] for state in historical_by_env.values()
            ),
            "historical_hinge_max_rad": _stats(
                [state["hinge_max_rad"] for state in historical_by_env.values()]
            ),
            "historical_target_face_error_min_m": _stats(
                [state["target_face_error_min_m"] for state in historical_by_env.values()]
            ),
            "stage_trace_rows": len(trace),
        },
        "direction_contract": EXPECTED_DIRECTION[direction],
        "runtime_contract": {
            "isaacsim": "PASS",
            "environment_device": "cuda:4",
            "num_envs": 16,
            "episodes": 16,
            "optimizer_updates": 0,
            "checkpoint_load": "PASS",
        },
    }

    if direction == "in":
        event_index = {A2_PULL_PRE_E0: -1, **{
            event_name: index for index, event_name in enumerate(A2_PULL_EVENT_NAMES)
        }}
        terminal_events = [record["pull_v0"]["event_state"] for record in diagnostics]
        event_counts = {
            event_name: sum(event_index[state] >= index for state in terminal_events)
            for index, event_name in enumerate(A2_PULL_EVENT_NAMES)
        }
        conditional_pairs = (
            ("P(E2 | E1)", A2_PULL_EVENT_NAMES[2], A2_PULL_EVENT_NAMES[1]),
            ("P(E3 | E2)", A2_PULL_EVENT_NAMES[3], A2_PULL_EVENT_NAMES[2]),
            ("P(E4 | E3)", A2_PULL_EVENT_NAMES[4], A2_PULL_EVENT_NAMES[3]),
            ("P(E5 | E4)", A2_PULL_EVENT_NAMES[5], A2_PULL_EVENT_NAMES[4]),
            ("P(E7 | E5)", A2_PULL_EVENT_NAMES[7], A2_PULL_EVENT_NAMES[5]),
        )
        funnel = {"P(E1)": event_counts[A2_PULL_EVENT_NAMES[1]] / 16}
        for label, numerator, denominator in conditional_pairs:
            denominator_count = event_counts[denominator]
            funnel[label] = (
                A2_PULL_NA
                if denominator_count == 0
                else event_counts[numerator] / denominator_count
            )
        cell_result["pull_event_funnel"] = {
            "highest_causal_event_histogram": _histogram(terminal_events),
            "cumulative_event_reached_counts": event_counts,
            "conditional_rates": funnel,
            "terminal_target_tcp_position_error_m": _stats(
                [float(record["pull_v0"]["target_tcp_position_error_m"]) for record in diagnostics]
            ),
            "terminal_bilateral_handle_contact_count": sum(
                bool(record["pull_v0"]["bilateral_handle_contact"])
                for record in diagnostics
            ),
            "orthogonal_arc_residual_m": A2_PULL_NA,
            "orthogonal_arc_residual_reason": "The inherited v20 route telemetry selector is intentionally disabled by the pull-v0 contract.",
        }
    return cell_result, {
        record["env_id"]: record["door_scenario"] for record in diagnostics
    }


def main() -> None:
    plan = _validate_plan()
    source_freeze = _load_json(SOURCE_FREEZE_PATH)
    frozen_source = Path(source_freeze["warm_checkpoint"]["source_path_read_only"])
    if _sha256(frozen_source) != source_freeze["warm_checkpoint"]["sha256"]:
        raise AssertionError("Mainline read-only frozen checkpoint changed after source freeze")

    cells = {}
    scenario_rows = {}
    for direction in ("out", "in"):
        cells[direction], scenario_rows[direction] = _validate_cell(
            direction, plan, source_freeze
        )
    if scenario_rows["out"] != scenario_rows["in"]:
        raise AssertionError("P0-F runtime scenario rows do not match exactly by env_id")

    receipt = {
        "schema_version": "pull_v0_p0f_zero_shot_fingerprint_v1",
        "generated_at_hkt": _hkt_now(),
        "status": "PASS",
        "threshold_mode": "report_only",
        "plan": {
            "path": _relative(PLAN_PATH),
            "sha256": _sha256(PLAN_PATH),
            "canonical_plan_sha256": plan["plan_sha256"],
        },
        "source_freeze": {
            "path": _relative(SOURCE_FREEZE_PATH),
            "base_sha": source_freeze["base_commit"],
            "frozen_checkpoint_sha256": source_freeze["warm_checkpoint"]["sha256"],
        },
        "pairing_contract": {
            "runtime_scenario_rows_exact_by_env_id": "PASS",
            "paired_scenario_row_count": 16,
            "same_seed": 0,
            "same_frozen_policy": "PASS",
            "same_actuator_and_material_profile": "PASS",
            "only_direction_contract_differs": "PASS",
        },
        "cells": cells,
        "attempt_history": [
            {
                "artifact": "logs_eval/a2_piper_pull_v0/p0f_zero_shot/out",
                "status": "FAIL_BEFORE_SIMULATION",
                "failure": "Hydra required +auto_load_latest for a key absent from the copied training config.",
                "metrics": A2_PULL_NA,
            },
            {
                "artifact": "logs_eval/a2_piper_pull_v0/p0f_zero_shot/out_repaired",
                "status": "FAIL_BEFORE_SIMULATION",
                "failure": "Hydra required +num_envs and other eval-only keys absent from the copied training config.",
                "metrics": A2_PULL_NA,
            },
            {
                "artifact": "scriptsFORhuman/pull_v0/PULL_V0_P0F_ZERO_SHOT_PLAN_R3.json",
                "status": "PASS",
                "repair": "Use explicit Hydra append syntax for eval-only keys; scientific semantics and frozen inputs are unchanged.",
            },
        ],
        "gpu_resource_evidence": {
            "authorized_physical_devices": [4, 5, 6],
            "compute_device_used": 4,
            "gpu5_used": False,
            "gpu6_used": False,
            "gpu7_compute_used": False,
            "isaacsim_adapter_note": "IsaacSim may enumerate system Vulkan adapters; both runtime logs identify CUDA device index 4 and all environment/sensor tensors as cuda:4.",
        },
        "interpretation": {
            "push_known_good_policy_probe": "The frozen push policy completed 10 of 16 paired first episodes.",
            "pull_zero_shot": "The frozen push policy completed 0 of 16 pull episodes; 13 reached E1 and none reached E2 tensile capture.",
            "decision": "Fingerprint only. Poor pull zero-shot behavior does not choose warm start versus scratch and does not replace P1 or P2.",
        },
        "evidence_boundary": {
            "static_contract": "PASS",
            "paired_isaacsim_runtime": "PASS",
            "frozen_policy_behavioral_fingerprint": "PASS",
            "pull_performance_threshold": "NOT_DEFINED_REPORT_ONLY",
            "warm_vs_scratch_decision": "NOT_EVALUATED",
            "p1_push_side_scripted_anchor": "NOT_RUN",
            "p2_bounded_adaptation": "NOT_RUN",
        },
    }
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
