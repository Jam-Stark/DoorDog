#!/usr/bin/env python3
"""Build the deterministic pull-v0 P0-E schema finite-data proof."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from gr00t.rl.envs.door.a2_pull_telemetry import (
    A2_PULL_CONTROL_STEP_UNITS,
    A2_PULL_EPISODE_UNITS,
    A2_PULL_ESTIMATE_ONLY,
    A2_PULL_EVENT_NAMES,
    A2_PULL_NA,
    A2_PULL_PRE_E0,
    A2_PULL_TELEMETRY_SCHEMA_VERSION,
    a2_pull_event_funnel,
    validate_a2_pull_control_step,
    validate_a2_pull_episode,
)


TERMINAL_REASON_MAX_EVENT = {
    "complete": 7,
    "stage_overtime": 3,
    "episode_timeout": 2,
    "low_height": 1,
    "bad_orientation": -1,
    "door_distance": 0,
    "upper_dof_overspeed": 4,
    "unknown_reset": 0,
}


def _control_step(step: int, event_index: int) -> dict:
    root_x = 1.0 - 0.02 * step
    return {
        "door_open_io_sign": 1,
        "door_open_lr_sign": -1,
        "active_handle_face_x_sign": 1,
        "travel_dir_x": -1,
        "stage": min(max(event_index, 0), 5),
        "event_state": A2_PULL_PRE_E0 if event_index < 0 else A2_PULL_EVENT_NAMES[event_index],
        "root_x_rel_door_m": root_x,
        "signed_crossing_progress_m": -root_x,
        "root_velocity_toward_door_mps": 0.1,
        "root_velocity_yield_outward_mps": -0.1,
        "root_velocity_final_travel_mps": 0.1,
        "root_yaw_error_rad": 0.02,
        "handle_position_rad": max(event_index - 1, 0) * 0.05,
        "handle_velocity_radps": 0.1,
        "latch_position_m": max(event_index - 2, 0) * 0.001,
        "hinge_position_rad": max(event_index - 3, 0) * 0.05,
        "hinge_velocity_radps": 0.02,
        "target_tcp_position_error_m": 0.01,
        "target_tcp_orientation_error_rad": 0.03,
        "bilateral_handle_contact": event_index >= 2,
        "hook_contact": A2_PULL_NA,
        "handle_local_slip_xyz_mps": [0.001, -0.002, 0.0],
        "gripper_handle_separation_m": 0.02,
        "finger_pd_effort_estimate_N": {
            "value": [12.0, 12.5],
            "provenance": A2_PULL_ESTIMATE_ONLY,
        },
        "finger_effort_utilization_estimate": {
            "value": [0.267, 0.278],
            "provenance": A2_PULL_ESTIMATE_ONLY,
        },
        "arm_pd_effort_utilization_estimate": {
            "value": [0.1, 0.12, 0.15, 0.2, 0.18, 0.14],
            "provenance": A2_PULL_ESTIMATE_ONLY,
        },
        "panel_contact_force_by_body_N": {
            "pelvis": 0.0,
            "arm_body7": 0.0,
            "arm_body8": 0.0,
        },
        "frame_contact_force_by_body_N": {
            "pelvis": 0.0,
            "arm_body7": 0.0,
            "arm_body8": 0.0,
        },
        "minimum_panel_robot_clearance_m": A2_PULL_NA,
        "reward_component_raw": {
            "pull_door_handle": 0.1,
            "pull_door_hinge": 0.05,
        },
    }


def _episode(max_event: int, terminal_reason: str) -> dict:
    reached = {
        event_name: event_index <= max_event
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES)
    }
    steps = {
        event_name: event_index * 10 if event_index <= max_event else A2_PULL_NA
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES)
    }
    times = {
        event_name: event_index * 0.2 if event_index <= max_event else A2_PULL_NA
        for event_index, event_name in enumerate(A2_PULL_EVENT_NAMES)
    }
    e2 = max_event >= 2
    e4 = max_event >= 4
    e5 = max_event >= 5
    e6 = max_event >= 6
    e7 = max_event >= 7
    return {
        "event_reached": reached,
        "first_event_step": steps,
        "first_event_time_s": times,
        "proof_hold_duration_s": 0.2 if e2 else A2_PULL_NA,
        "proof_retreat_displacement_m": 0.01 if e2 else A2_PULL_NA,
        "max_tensile_retreat_before_loss_m": 0.02 if e2 else A2_PULL_NA,
        "hinge_at_first_positive_progress_rad": 0.01 if e4 else A2_PULL_NA,
        "hinge_at_first_grip_loss_rad": A2_PULL_NA,
        "held_hinge_max_rad": 0.2 if e4 else A2_PULL_NA,
        "hinge_at_release_or_hold_decision_rad": 0.2 if e5 else A2_PULL_NA,
        "root_outward_excursion_before_clear_m": 0.1 if e5 else A2_PULL_NA,
        "first_path_reversal_step": 60 if e6 else A2_PULL_NA,
        "release_to_whole_body_clear_s": 0.4 if e7 else A2_PULL_NA,
        "hinge_reclosure_after_release_rad": A2_PULL_NA,
        "body_panel_contact_steps_per_20s": 0,
        "body_panel_contact_impulse_Ns": 0.0,
        "crossing_while_valid_capture": e6,
        "whole_body_clear": e7,
        "terminal_reason": terminal_reason,
    }


def main() -> None:
    episodes = []
    control_steps = []
    for terminal_reason, max_event in TERMINAL_REASON_MAX_EVENT.items():
        episode = _episode(max_event, terminal_reason)
        validate_a2_pull_episode(episode)
        episodes.append(episode)
        for event_index in range(-1 if max_event < 0 else 0, max_event + 1):
            record = _control_step(max(event_index, 0) * 10, event_index)
            validate_a2_pull_control_step(record)
            control_steps.append(
                {
                    "terminal_reason": terminal_reason,
                    "control_step": max(event_index, 0) * 10,
                    "record": record,
                }
            )
    output = {
        "schema_version": A2_PULL_TELEMETRY_SCHEMA_VERSION,
        "proof_scope": "P0-E deterministic schema harness",
        "evidence_boundary": {
            "static_schema_harness": "PASS",
            "IsaacSim_runtime": "NOT_RUN",
            "policy_behavior": "NOT_RUN",
        },
        "harness_input": "Synthetic finite values exercise every terminal reason registered by the pull smoke harness; they are not runtime measurements.",
        "control_step_units": A2_PULL_CONTROL_STEP_UNITS,
        "episode_units": A2_PULL_EPISODE_UNITS,
        "implicit_actuator_provenance": A2_PULL_ESTIMATE_ONLY,
        "terminal_reason_coverage": list(TERMINAL_REASON_MAX_EVENT),
        "control_step_records": control_steps,
        "episode_records": episodes,
        "event_funnel_example": a2_pull_event_funnel(episodes),
        "validation": {
            "schema_completeness": "PASS",
            "finite_numeric_fields": "PASS",
            "unit_registry": "PASS",
            "N/A_handling": "PASS",
            "event_ordering": "PASS",
            "impossible_event_rejection": "PASS_BY_UNIT_TEST",
            "estimate_only_stamps": "PASS",
        },
    }
    output_path = Path(__file__).with_name("PULL_V0_TELEMETRY_FINITE_PROOF.json")
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
