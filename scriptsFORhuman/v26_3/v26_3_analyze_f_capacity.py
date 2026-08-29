#!/usr/bin/env python3
"""Reduce bounded v26-3 F10/F20/F40 natural capacity evaluations."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from v26_3_analyze_mechanism import SIDES, load_json, longest_true_run, number, require


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--diagnostic-decision", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def reduce_side(path: Path, reference: float) -> dict[str, Any]:
    metrics = load_json(path / "metrics_eval.json")
    trace = load_json(path / "stage2_5_step_trace.json")
    terminal = metrics.get("episode_terminal_diagnostics")
    require(isinstance(terminal, list) and len(terminal) == 16, f"{path} must contain exact16 terminals")
    by_env: dict[int, list[dict[str, Any]]] = defaultdict(list)
    detailed = []
    for row in trace:
        if row.get("first_episode_active") is not True:
            continue
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < 16, f"{path} trace env invalid")
        by_env[env_id].append(row)
        if row.get("stage_buf") == 3 and row.get("v26_2", {}).get("strict_k5") is True:
            detailed.append(row)
    durable = 0
    max_highwater = 0.0
    fall_or_bad = 0
    for row in terminal:
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < 16, f"{path} terminal env invalid")
        values = [number(item.get("door_handle_joint_pos"), "F handle") for item in by_env[env_id]]
        durable += longest_true_run([value > reference for value in values]) >= 5
        max_highwater = max(max_highwater, number(row["v26_3"].get("handle_highwater"), "F highwater"))
        fall_or_bad += str(row.get("terminal_reasons")) in {"fall", "over_force", "dof_overspeed"}
    errors = []
    saturation = []
    external_opening = []
    over_force_steps = 0
    for row in detailed:
        err = row.get("gripper_joint_target_error")
        sat = row.get("pd_effort_estimated_saturation")
        force = row.get("finger_total_force_along_opening_axis_body7_body8")
        require(isinstance(err, list) and isinstance(sat, list) and isinstance(force, list) and len(err) == len(sat) == len(force) == 2, f"{path} detailed shape mismatch")
        errors.extend(abs(number(value, "F error")) for value in err)
        saturation.extend(bool(value) for value in sat)
        external_opening.append(all(number(value, "F opening force") > 0.0 for value in force))
        over_force_steps += bool(row.get("over_force", False))
    require(detailed, f"{path} has no Stage3+K5 detailed samples")
    return {
        "episodes": 16,
        "durable_creation_episodes": durable,
        "max_handle_highwater_rad": max_highwater,
        "stage3_k5_detailed_steps": len(detailed),
        "mean_abs_gripper_target_error_rad": sum(errors) / len(errors),
        "estimated_saturation_fraction": sum(saturation) / len(saturation),
        "external_opening_force_both_fingers_fraction": sum(external_opening) / len(external_opening),
        "over_force_steps": over_force_steps,
        "fall_overforce_overspeed_terminal_count": fall_or_bad,
        "actual_drive_force": "INCONCLUSIVE_UNAVAILABLE",
    }


def main() -> None:
    args = parse_args()
    diagnostic = load_json(args.diagnostic_decision)
    branch = diagnostic.get("effort_capacity_branch")
    require(isinstance(branch, dict) and branch.get("status") == "INITIAL_F_EVAL_REQUIRED", "D3 did not admit F initial eval")
    references = diagnostic.get("handle_creation_reference_side_rad")
    require(isinstance(references, dict), "diagnostic references missing")
    cells = {
        str(cap): {
            side: reduce_side(args.eval_root / f"F{cap}" / side, number(references.get(side), f"reference {side}"))
            for side in SIDES
        }
        for cap in (10, 20, 40)
    }
    empirical_candidate = None
    for cap in (20, 40):
        improves = all(
            cells[str(cap)][side]["mean_abs_gripper_target_error_rad"]
            < cells["10"][side]["mean_abs_gripper_target_error_rad"]
            and cells[str(cap)][side]["estimated_saturation_fraction"]
            < cells["10"][side]["estimated_saturation_fraction"]
            and cells[str(cap)][side]["durable_creation_episodes"]
            > cells["10"][side]["durable_creation_episodes"]
            and cells[str(cap)][side]["external_opening_force_both_fingers_fraction"] > 0.5
            and cells[str(cap)][side]["fall_overforce_overspeed_terminal_count"]
            <= cells["10"][side]["fall_overforce_overspeed_terminal_count"]
            for side in SIDES
        )
        if improves:
            empirical_candidate = cap
            break
    # The installed implicit actuator exposes estimates, and the detailed contact
    # lane exposes finger-opening projections, but neither provides a proven
    # per-contact handle-axis moment with an authoritative anchor/axis/frame.
    # Therefore the bounded 16/side F readout cannot promote a common actuator.
    selected = 10
    payload = {
        "schema": "a2_piper_base_v26_3_f_capacity_v1",
        "status": "INITIAL_COMPLETE",
        "cells": cells,
        "selected_effort_limit_nm": selected,
        "empirical_candidate_before_axis_authority_gate": empirical_candidate,
        "exact64_expansion_required": False,
        "typed_outcome": (
            "ACTUATOR_CAPACITY_AXIS_EFFECT_INCONCLUSIVE"
            if empirical_candidate is not None
            else "ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE"
        ),
        "common_j7_j8_effort_limit": [float(selected), float(selected)],
        "actual_drive_force": "INCONCLUSIVE_UNAVAILABLE",
        "handle_axis_effect": "INCONCLUSIVE_NO_PER_CONTACT_AXIS_MOMENT",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
