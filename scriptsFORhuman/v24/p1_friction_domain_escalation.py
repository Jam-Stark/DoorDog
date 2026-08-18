"""Run the Owner-approved v24 P1-lite friction magnitude escalation on GPU0."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

try:
    from ._v24_common import REPO_ROOT, V24_P1_FRICTION_ROOT, absolute, rel_path, require_file, write_json
    from .p1_friction_probe import (
        AI_SPEED_ORDER,
        AI_SURFACE_TAGS,
        DOOR_FIXED_CONFIG,
        SELECTED_CHECKPOINT,
        _build_door_only_scene,
        _profile_friction,
        _probe_config_values,
        _read_g_fixture_gate,
        _run_behavioral_decay_trials,
        _run_chatter_trial,
        _single_env_ids,
        _summarize_control_ratios,
        _summarize_g_cell,
        _summarize_plateau,
        run_torque_ramp,
    )
except ImportError:
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v24._v24_common import REPO_ROOT, V24_P1_FRICTION_ROOT, absolute, rel_path, require_file, write_json
    from scriptsFORhuman.v24.p1_friction_probe import (
        AI_SPEED_ORDER,
        AI_SURFACE_TAGS,
        DOOR_FIXED_CONFIG,
        SELECTED_CHECKPOINT,
        _build_door_only_scene,
        _profile_friction,
        _probe_config_values,
        _read_g_fixture_gate,
        _run_behavioral_decay_trials,
        _run_chatter_trial,
        _single_env_ids,
        _summarize_control_ratios,
        _summarize_g_cell,
        _summarize_plateau,
        run_torque_ramp,
    )


SCHEMA = "a2_piper_v24_p1_lite_friction_domain_escalation_v1"
MODE = "P1_LITE_DOMAIN_ESCALATION"
PROFILE_ORDER = ("P02", "P05", "P10", "P20")
EXPECTED_PROFILES = {
    "P02": (2.0, 1.5, 0.0),
    "P05": (5.0, 3.75, 0.0),
    "P10": (10.0, 7.5, 0.0),
    "P20": (20.0, 15.0, 0.0),
}
CONFIG = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v24_p1_friction_domain_escalation.yaml"
OWNER_DECISION = REPO_ROOT / "scriptsFORhuman/v24/DoorDog_v24_owner_decision_friction_domain_escalation_20260818.md"
ARTIFACT_ROOT = V24_P1_FRICTION_ROOT / "p1_lite_domain_escalation_r13_gpu0"


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _read_contract(config_path: Path) -> dict[str, Any]:
    target = absolute(config_path).resolve()
    if target != CONFIG.resolve():
        raise ValueError("P1-lite requires the dedicated r13 domain-escalation config")
    payload = yaml.safe_load(require_file(target, label="P1-lite config").read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("v24_schema") != SCHEMA or payload.get("v24_runtime_mode") != MODE:
        raise ValueError("P1-lite schema/runtime mode mismatch")
    require_file(OWNER_DECISION, label="P1-lite Owner decision")
    if payload.get("v24_owner_decision") != rel_path(OWNER_DECISION):
        raise ValueError("P1-lite config must cite the controlling Owner decision")
    for key in ("checkpoint", "v24_checkpoint_provenance"):
        if absolute(str(payload.get(key))).resolve() != SELECTED_CHECKPOINT.resolve():
            raise ValueError(f"P1-lite {key} does not match the selected v23 checkpoint")

    raw = payload.get("v24_p1_lite")
    if not isinstance(raw, Mapping) or raw.get("enabled") is not True or raw.get("device") != "cuda:0":
        raise ValueError("P1-lite must be enabled on cuda:0")
    anchor = raw.get("magnitude_anchor")
    if not isinstance(anchor, Mapping):
        raise TypeError("P1-lite magnitude anchor is required")
    anchor_source = require_file(REPO_ROOT / str(anchor.get("source")), label="P1-lite magnitude anchor")
    if _finite(anchor.get("established_solvable_drive_resistance_nm"), label="magnitude anchor") != 24.0:
        raise ValueError("P1-lite magnitude anchor must remain 24 N*m")
    if anchor.get("interpretation") != "REPOSITORY_EVIDENCE_MAGNITUDE_ANCHOR_NOT_FRICTION_EQUIVALENCE":
        raise ValueError("P1-lite magnitude-anchor interpretation mismatch")

    raw_profiles = raw.get("friction_profiles")
    if not isinstance(raw_profiles, Mapping) or tuple(raw_profiles) != PROFILE_ORDER:
        raise ValueError("P1-lite profiles must be ordered P02/P05/P10/P20")
    profiles: dict[str, dict[str, float]] = {}
    for name in PROFILE_ORDER:
        item = raw_profiles[name]
        if not isinstance(item, Mapping):
            raise TypeError(f"P1-lite profile {name} must be a mapping")
        values = (
            _finite(item.get("static_effort_nm"), label=f"{name}.static"),
            _finite(item.get("dynamic_effort_nm"), label=f"{name}.dynamic"),
            _finite(item.get("viscous_coefficient_nm_s_per_rad"), label=f"{name}.viscous"),
        )
        if values != EXPECTED_PROFILES[name]:
            raise ValueError(f"P1-lite profile {name} must remain {EXPECTED_PROFILES[name]!r}")
        profiles[name] = dict(zip(("static_effort_nm", "dynamic_effort_nm", "viscous_coefficient_nm_s_per_rad"), values))

    kinetic = raw.get("kinetic_trials")
    control = raw.get("damping_control")
    chatter = raw.get("chatter")
    orthogonality = raw.get("orthogonality")
    if not all(isinstance(item, Mapping) for item in (kinetic, control, chatter, orthogonality)):
        raise TypeError("P1-lite kinetic/control/chatter/orthogonality blocks are required")
    speeds = tuple(float(value) for value in kinetic.get("speeds_rad_s", ()))
    if speeds != AI_SPEED_ORDER or kinetic.get("frames") != 20:
        raise ValueError("P1-lite kinetic trials require the registered speeds and 20-frame window")
    cells = orthogonality.get("cells")
    expected_cells = {"A0": (120.0, 50.0, 2.0), "A8": (160.0, 200.0, 30.0)}
    if not isinstance(cells, list) or tuple(item.get("id") for item in cells if isinstance(item, Mapping)) != tuple(expected_cells):
        raise ValueError("P1-lite G cells must be ordered A0/A8")
    parsed_cells = []
    for item in cells:
        cell_id = item["id"]
        values = tuple(_finite(item.get(key), label=f"{cell_id}.{key}") for key in ("door_weight_kg", "damping_native", "stiffness_native"))
        if values != expected_cells[cell_id]:
            raise ValueError(f"P1-lite G cell {cell_id} mismatch")
        parsed_cells.append({"id": cell_id, "door_weight_kg": values[0], "damping_native": values[1], "stiffness_native": values[2]})

    return {
        "config_path": target,
        "friction": _probe_config_values(target),
        "device": "cuda:0",
        "profiles": profiles,
        "anchor": {"source": rel_path(anchor_source), "established_solvable_drive_resistance_nm": 24.0, "interpretation": anchor["interpretation"]},
        "kinetic": {
            "initial_angle_rad": _finite(kinetic.get("initial_angle_rad"), label="kinetic.initial_angle"),
            "interior_margin_rad": _finite(kinetic.get("interior_margin_rad"), label="kinetic.interior_margin"),
            "speeds_rad_s": speeds,
            "frames": 20,
            "relative_spread_max": _finite(kinetic.get("relative_spread_max"), label="kinetic.relative_spread_max"),
            "direction_asymmetry_max": _finite(kinetic.get("direction_asymmetry_max"), label="kinetic.direction_asymmetry_max"),
            "max_positive_abs_speed_increment_rad_s": _finite(kinetic.get("max_positive_abs_speed_increment_rad_s"), label="kinetic.max_increment"),
        },
        "control": {key: _finite(control.get(key), label=f"control.{key}") for key in ("damping_native", "stiffness_native", "friction_ratio_low", "friction_ratio_high", "damping_ratio_min")},
        "chatter": {
            "slip_velocity_threshold_rad_s": _finite(chatter.get("slip_velocity_threshold_rad_s"), label="chatter.threshold"),
            "max_slip_reentries": int(chatter.get("max_slip_reentries")),
            "frames": int(chatter.get("frames")),
        },
        "orthogonality": {
            "realized_scaled_distance_max": _finite(orthogonality.get("realized_scaled_distance_max"), label="orthogonality.scaled_distance_max"),
            "cells": parsed_cells,
        },
    }


def build_plan(config_path: Path = CONFIG) -> dict[str, Any]:
    contract = _read_contract(config_path)
    return {
        "schema": SCHEMA,
        "status": "REGISTERED_BEFORE_RUNTIME",
        "mode": MODE,
        "owner_decision": rel_path(OWNER_DECISION),
        "config": rel_path(contract["config_path"]),
        "device": contract["device"],
        "magnitude_anchor": contract["anchor"],
        "profiles": contract["profiles"],
        "checks": ["A_BREAKAWAY_CONTAINMENT", "B_KINETIC_PLATEAU", "C_DAMPING_DISTINCTION", "E_CHATTER", "G_A0_A8_HIGHEST_STABLE"],
        "domain_rule": "select the highest ascending profile whose A/B/C/E gates and highest-profile G gate pass",
        "unstable_rule": "shrink once to the highest stable profile without an Owner round trip",
        "runtime_output": rel_path(ARTIFACT_ROOT / "P1_LITE_DOMAIN_ESCALATION_RECEIPT.json"),
        "authority": {"friction_torque": "MODELED_FROM_PARAMS", "solver_applied": False, "command_effort": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE"},
    }


def _run_runtime(contract: Mapping[str, Any], *, output: Path) -> None:
    import torch

    friction = contract["friction"]
    source_configs = [dict(DOOR_FIXED_CONFIG)]
    for cell in contract["orthogonality"]["cells"]:
        item = dict(DOOR_FIXED_CONFIG)
        item.update(rand_door_weight=cell["door_weight_kg"], rand_hinge_drive_damping=cell["damping_native"], rand_hinge_drive_stiffness=cell["stiffness_native"])
        source_configs.append(item)
    sim = None
    try:
        sim, scene, door, fixtures = _build_door_only_scene(device=contract["device"], dt=friction["dt_s"], probe_seed=friction["probe_seed"], door_configs=source_configs)
        base_fixture = fixtures[0]
        base_ids = _single_env_ids(door, selected_env_index=0, device=contract["device"])
        baseline_position = door.data.joint_pos[base_ids].clone()
        baseline_velocity = torch.zeros_like(door.data.joint_vel[base_ids])
        zero_profile = {"static_effort_nm": 0.0, "dynamic_effort_nm": 0.0, "viscous_coefficient_nm_s_per_rad": 0.0}
        kinetic = contract["kinetic"]
        control_cfg = contract["control"]
        damping_control = _run_behavioral_decay_trials(
            sim=sim, scene=scene, friction=friction, door_fixture=base_fixture, profile=zero_profile,
            device=contract["device"], dt=friction["dt_s"], initial_angle_rad=kinetic["initial_angle_rad"],
            interior_margin_rad=kinetic["interior_margin_rad"], speeds_rad_s=kinetic["speeds_rad_s"], frames=kinetic["frames"],
            damping_native=control_cfg["damping_native"], stiffness_native=control_cfg["stiffness_native"],
            max_positive_abs_speed_increment=kinetic["max_positive_abs_speed_increment_rad_s"],
            trial_frame_authority="V24_R13_ESCALATED_DAMPING_CONTROL_20_FRAME_TRIAL", selected_env_index=0,
        )

        profiles: dict[str, Any] = {}
        upper_brackets: list[float] = []
        prefix_stable: list[str] = []
        prefix_open = True
        for name in PROFILE_ORDER:
            profile = contract["profiles"][name]
            profile_friction = _profile_friction(friction, profile)
            a_receipt = run_torque_ramp(
                sim=sim, scene=scene, friction=profile_friction, door_fixture=base_fixture,
                device=contract["device"], dt=friction["dt_s"], record_raw_traces=True,
                trial_baseline_position=baseline_position, trial_baseline_velocity=baseline_velocity, selected_env_index=0,
            )
            bracket = a_receipt["breakaway"]["measured_bracket_nm"]
            a_pass = a_receipt["status"] == "PASS" and a_receipt["breakaway"]["requested_static_in_bracket"] is True
            if isinstance(bracket, list) and len(bracket) == 2:
                upper_brackets.append(float(bracket[1]))
            else:
                upper_brackets.append(float("nan"))
            b_receipt = _run_behavioral_decay_trials(
                sim=sim, scene=scene, friction=friction, door_fixture=base_fixture, profile=profile,
                device=contract["device"], dt=friction["dt_s"], initial_angle_rad=kinetic["initial_angle_rad"],
                interior_margin_rad=kinetic["interior_margin_rad"], speeds_rad_s=kinetic["speeds_rad_s"], frames=kinetic["frames"],
                damping_native=0.0, stiffness_native=0.0, max_positive_abs_speed_increment=kinetic["max_positive_abs_speed_increment_rad_s"],
                trial_frame_authority="V24_R13_ESCALATED_KINETIC_20_FRAME_TRIAL", selected_env_index=0,
            )
            b_summary = _summarize_plateau(b_receipt["trials"], kinetic["relative_spread_max"], kinetic["direction_asymmetry_max"])
            c_summary = _summarize_control_ratios(
                b_receipt["trials"], damping_control["trials"], control_cfg["friction_ratio_low"],
                control_cfg["friction_ratio_high"], control_cfg["damping_ratio_min"],
            )
            threshold = a_receipt["breakaway"]["measured_threshold_nm"]
            if threshold is None:
                e_receipt = {"status": "BREAKAWAY_NOT_OBSERVED", "chatter_passed": False}
                e_summary = {"passed": False, "status": "BREAKAWAY_NOT_OBSERVED"}
            else:
                e_receipt = _run_chatter_trial(
                    sim=sim, scene=scene, friction=friction, door_fixture=base_fixture, profile=profile,
                    command_effort_nm=float(threshold), device=contract["device"], dt=friction["dt_s"],
                    frames=contract["chatter"]["frames"], slip_threshold=contract["chatter"]["slip_velocity_threshold_rad_s"],
                    trial_frame_authority="V24_R13_ESCALATED_CHATTER_100_FRAME_TRIAL", selected_env_index=0,
                )
                e_summary = {
                    "passed": e_receipt["chatter_passed"], "status": "PASS" if e_receipt["chatter_passed"] else "FAIL_CHATTER",
                    "first_breakaway_command_nm": threshold,
                    "slip_reentries_after_first": e_receipt["quality"]["slip_reentries_after_first"],
                    "sign_reversals": e_receipt["quality"]["sign_reversals"],
                }
            gate_pass = a_pass and b_summary["passed"] and c_summary["passed"] and e_summary["passed"]
            prefix_open = prefix_open and gate_pass
            if prefix_open:
                prefix_stable.append(name)
            profiles[name] = {
                "profile": profile,
                "A": {"passed": a_pass, "receipt": a_receipt},
                "B": {"summary": b_summary, "receipt": b_receipt},
                "C": {"summary": c_summary, "damping_control_receipt": damping_control},
                "E": {"summary": e_summary, "receipt": e_receipt},
                "pre_g_passed": gate_pass,
            }

        a_monotonic = all(math.isfinite(value) for value in upper_brackets) and all(left <= right for left, right in zip(upper_brackets, upper_brackets[1:]))
        if not a_monotonic:
            prefix_stable = []
        g_attempts: dict[str, Any] = {}
        stable_max: str | None = None
        for candidate in reversed(prefix_stable):
            cell_rows: dict[str, Any] = {}
            for offset, cell in enumerate(contract["orthogonality"]["cells"], start=1):
                fixture_gate = _read_g_fixture_gate(
                    door, fixtures[offset], device=contract["device"], selected_env_index=offset,
                    realized_scaled_distance_max=contract["orthogonality"]["realized_scaled_distance_max"],
                )
                receipt = run_torque_ramp(
                    sim=sim, scene=scene, friction=_profile_friction(friction, contract["profiles"][candidate]),
                    door_fixture=fixtures[offset], device=contract["device"], dt=friction["dt_s"],
                    record_raw_traces=True, neutralize_damping_stiffness=False, selected_env_index=offset,
                )
                cell_rows[cell["id"]] = {"fixture_gate": fixture_gate, "receipt": receipt, "summary": _summarize_g_cell(receipt, contract["chatter"]["slip_velocity_threshold_rad_s"], fixture_gate)}
            g_pass = all(item["summary"]["passed"] for item in cell_rows.values())
            g_attempts[candidate] = {"passed": g_pass, "cells": cell_rows}
            if g_pass:
                stable_max = candidate
                break

        stable_profiles = PROFILE_ORDER[: PROFILE_ORDER.index(stable_max) + 1] if stable_max is not None else ()
        typed = "V24_FRICTION_ESCALATED_DOMAIN_STABLE" if stable_max is not None else "V24_FRICTION_NUMERICALLY_UNSTABLE_ESCALATED_DOMAIN"
        payload = {
            "schema": SCHEMA, "status": "PASS" if stable_max is not None else "FAIL", "typed_outcome": typed,
            "owner_decision": rel_path(OWNER_DECISION), "device": contract["device"], "config": rel_path(contract["config_path"]),
            "magnitude_anchor": contract["anchor"], "profile_order": list(PROFILE_ORDER), "profiles": profiles,
            "A": {"upper_brackets_nm": dict(zip(PROFILE_ORDER, upper_brackets)), "upper_brackets_nondecreasing": a_monotonic},
            "G": {"rule": "A0/A8 at the highest pre-G stable profile, shrinking downward once if required", "attempts": g_attempts},
            "stable_profiles": list(stable_profiles),
            "stable_max_profile": stable_max,
            "stable_max_static_effort_nm": contract["profiles"][stable_max]["static_effort_nm"] if stable_max else None,
            "stable_max_dynamic_effort_nm": contract["profiles"][stable_max]["dynamic_effort_nm"] if stable_max else None,
            "D": "NOT_RERUN_P1_LITE_SCOPE", "F": "NOT_RERUN_P1_LITE_SCOPE",
            "authority": {"friction_torque": "MODELED_FROM_PARAMS", "solver_applied": False, "command_effort": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE"},
        }
        write_json(output, payload)
    finally:
        if sim is not None:
            sim.clear_instance()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", default="cuda:0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    contract = _read_contract(args.config)
    if args.plan:
        payload = build_plan(args.config)
        if args.output is None:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            write_json(absolute(args.output), payload)
        return 0
    if args.device != contract["device"]:
        raise ValueError("P1-lite requires GPU0/cuda:0")
    if args.output is None:
        raise ValueError("P1-lite runtime requires --output")
    output = absolute(args.output)
    if ARTIFACT_ROOT not in output.parents:
        raise ValueError(f"P1-lite output must be under {ARTIFACT_ROOT}")
    from isaaclab.app import AppLauncher

    launcher = AppLauncher({"headless": True, "device": args.device, "enable_cameras": False})
    _run_runtime(contract, output=output)
    launcher.app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
