"""CPU-only P2 force-boundary plan and typed adjudication helpers.

The runtime producer is deliberately separate from this plan module.  Running
``--plan`` validates the frozen overlay and prints the exact parameter,
ladder, certificate, held-out, and append-only artifact contract; it never
starts IsaacSim, loads a checkpoint, or writes evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

try:
    import yaml
except ImportError as exc:  # pragma: no cover - explicit plan dependency
    raise RuntimeError("PyYAML is required for the v24 P2 CPU plan") from exc

try:
    from ._v24_common import REPO_ROOT, absolute, rel_path, require_file
except ImportError:  # direct ``python scriptsFORhuman/v24/p2_force_boundary.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v24._v24_common import REPO_ROOT, absolute, rel_path, require_file


PLAN_SCHEMA = "a2_piper_v24_p2_force_boundary_plan_v1"
PARAMETER_RANGE_SCHEMA = "a2_piper_v24_p2_parameter_range_freeze_v1"
LADDER_SCHEMA = "a2_piper_v24_p2_ladder_freeze_v1"
THRESHOLD_SCHEMA = "a2_piper_v24_p2_certificate_threshold_freeze_v1"
E_REGION_SCHEMA = "a2_piper_v24_p2_e_region_certificate_v1"
FINAL_SCHEMA = "a2_piper_v24_p2_final_adjudication_v1"
VITALS_RECEIPT_SCHEMA = "a2_piper_v24_p2_sham_vitals_receipt_v1"
RULE16_SCHEMA = "a2_piper_v24_rule16_admission_v1"
CONFIG_PATH = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v24_p2_force_boundary.yaml"
ARTIFACT_ROOT = "logs_eval/base_v24/p2/force_boundary/r12"
VITALS_RUNTIME_ARTIFACT = "vitals/runtime/P2_RUNTIME_ROWS.jsonl"
VITALS_SOURCE = f"{ARTIFACT_ROOT}/{VITALS_RUNTIME_ARTIFACT}"
OWNER_DECISION = "scriptsFORhuman/v24/DoorDog_v24_owner_decision_p2_invalid_measurement_20260817.md"
CHECKPOINT = "logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt"
PILOT_REGISTRATION_ID = "R12_R1_F3_MARGINAL_E1_PILOT_01"
PILOT_ARTIFACT_ROOT = "logs_eval/base_v24/p2/force_boundary/r12/marginal_e1"
PILOT_REQUIRED_STATUS = "MARGINAL_E1_PILOT_REQUIRED"
STAGE_REACH_REFERENCE_BAND = {
    "stage_ids": [3, 4],
    "window_transition_count": 25,
    "minimum_current_stable_grasp_rows": 20,
    "required_env_count": 16,
}
GRADIENT_ADMISSION = {
    "schema": "a2_piper_v24_p2_gradient_admission_v1",
    "status": "PASS_OWNER_PROXY_ADJUDICATED",
    "authorizes_marginal_e1_pilot": True,
    "strong_model_evidence": False,
    "all_window_medians": {"F00": 0.0828638, "F05": 0.0817359, "F10": 0.0799669},
    "matched_strict_triples": 78,
    "matched_strict_triples_total": 96,
    "model_valid_subset_medians": {"F00": 0.0988929, "F05": 0.1086381, "F10": 0.1030480},
    "directional_high_effort_count": 0,
    "directional_high_effort_total": 288,
}
PRIMARY_CAPS_NM = (100.0, 60.0, 40.0, 30.0, 25.0, 20.0)
CONTINGENCY_CAP_NM = 10.0
REGISTERED_CAPS_NM = (*PRIMARY_CAPS_NM, CONTINGENCY_CAP_NM)
CAP_ORDER_DESCENDING_NM = tuple(sorted(REGISTERED_CAPS_NM, reverse=True))
CONTROL_PERIOD_S = 0.02
FRICTION_PROFILES = {
    "F00": {"static_effort_nm": 0.0, "dynamic_effort_nm": 0.0, "viscous_coefficient_nm_s_per_rad": 0.0, "dynamic_to_static_ratio": "N/A"},
    "F05": {"static_effort_nm": 0.5, "dynamic_effort_nm": 0.375, "viscous_coefficient_nm_s_per_rad": 0.0, "dynamic_to_static_ratio": 0.75},
    "F10": {"static_effort_nm": 1.0, "dynamic_effort_nm": 0.75, "viscous_coefficient_nm_s_per_rad": 0.0, "dynamic_to_static_ratio": 0.75},
}
RUNTIME_MODES = ("HI_FULL", "BOUNDARY_FULL", "BOUNDARY_RP0", "RESCUE_FULL")
WINDOW_SELECTION_ADMITTED = "FIRST_STABLE_GRASP_OPENING_20_OF_25"
WINDOW_SELECTION_FALLBACK = "NO_QUALIFYING_STABLE_GRASP_OPENING_FALLBACK_FIRST_ALPHA_VALID"
WINDOW_SELECTION_ADMITTED_STATUS = "ADMITTED_FIRST_STABLE_GRASP_OPENING"
WINDOW_SELECTION_FALLBACK_STATUS = "NON_ADMISSIBLE_NO_QUALIFYING_STABLE_GRASP_OPENING"
EXCLUSIONS = ("GEOMETRY", "GRASP", "DIRECTION", "SLIP", "PATHOLOGY", "WINDOW_SELECTION")
SCENARIO_IDS = tuple(f"S{index:02d}" for index in range(16))
STAGE_ARTIFACTS = (
    "V24_P2_PARAMETER_RANGE_FREEZE.json",
    "smoke/P2_SMOKE_RECEIPT.json",
    "calibration/P2_CALIBRATION_ROWS.jsonl",
    "calibration/P2_CALIBRATION_RECEIPT.json",
    "V24_P2_LADDER_FREEZE.json",
    "V24_P2_CERTIFICATE_THRESHOLD_FREEZE.json",
    "heldout/P2_HELDOUT_ROWS.jsonl",
    "heldout/P2_HELDOUT_RECEIPT.json",
    "V24_P2_E_REGION_CERTIFICATE.json",
    "V24_P2_FINAL_ADJUDICATION.json",
    "QA_SEMANTIC_VALIDATION.json",
)
VITAL_ARTIFACTS = (
    "vitals/P2_SHAM_ROWS.jsonl",
    VITALS_RUNTIME_ARTIFACT,
    "vitals/P2_SHAM_VITALS_RECEIPT.json",
)
PILOT_ARTIFACTS = (
    "marginal_e1/P2_MARGINAL_E1_PILOT_REGISTRATION.json",
    "marginal_e1/P2_MARGINAL_E1_PILOT_COMMANDS.json",
    "marginal_e1/P2_MARGINAL_E1_PILOT_ADJUDICATION.json",
    "marginal_e1/P2_MARGINAL_E1_POST_PILOT_FINALIZATION.json",
    "marginal_e1/P2_MARGINAL_E1_PILOT_POPULATION.jsonl",
    "marginal_e1/P2_MARGINAL_E1_POST_TRAINING_EVAL_COMMANDS.json",
)
REGISTERED_ARTIFACTS = STAGE_ARTIFACTS + VITAL_ARTIFACTS + PILOT_ARTIFACTS
AUTHORITY_SET = {
    "capacity_lambda": "ESTIMATE_ONLY_DIRECTIONAL_MARGIN",
    "pd_command": "ESTIMATE_ONLY_IMPLICIT_PD_COMMAND",
    "gravity": "ISAACLAB_GRAVITY_COMPENSATION_ESTIMATE",
    "state": "HIGH_LEVEL_ARTICULATION_DATA",
    "actual_generalized_torque": "UNAVAILABLE_NOT_USED",
}
RUNTIME_AUTHORITY_SET = {
    **AUTHORITY_SET,
    "door_friction": "MODELED_FROM_PARAMS",
    "solver_applied": False,
}
TYPED_RESULTS = (
    "V24_E1_BOUNDARY_ESTABLISHED",
    "V24_E1_DENOMINATOR_INSUFFICIENT",
    "V24_E1_BOUNDARY_ESTABLISHED_POST_F3",
    "V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3",
    "V24_E2_BOUNDARY_ESTABLISHED",
    "V24_E2_BOUNDARY_NOT_ESTABLISHED",
    "V24_ARM_COMMAND_PATH_NOT_BINDING",
    "V24_DOOR_MODEL_REMAINS_INSUFFICIENT",
)
PREHELDOUT_TERMINAL_RESULTS = frozenset(
    (
        "V24_ARM_COMMAND_PATH_NOT_BINDING",
        "V24_DOOR_MODEL_REMAINS_INSUFFICIENT",
    )
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _read_overlay(path: str | Path) -> dict[str, Any]:
    target = require_file(path, label="v24 P2 overlay")
    payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("v24 P2 overlay root must be a mapping")
    return payload


def parameter_range_freeze(*, status: str = "PLANNED_NOT_EXECUTED") -> dict[str, Any]:
    return {
        "schema": PARAMETER_RANGE_SCHEMA,
        "status": status,
        "checkpoint": CHECKPOINT,
        "checkpoint_load_mode": "selected_policy_only",
        "calibration_seed": 24021,
        "heldout_seed": 24022,
        "topology": {"envs_per_run": 48, "envs_per_profile": 16, "paired_scenarios": 16},
        "control": {"max_control_steps": 1000, "dt_s": 0.005, "decimation": 4},
        "geometry": {
            "panel_mass_kg": 120.0,
            "panel_width_m": 0.95,
            "panel_height_m": 2.05,
            "handle_height_m": 0.975,
            "handle_width_m": 0.12,
            "handle_type": "lever",
            "opening_lr": "right",
            "opening_io": "out",
            "hinge_axis_local": [0.0, 0.0, 1.0],
        },
        "door_model": {
            "inertia_kg_m2": 36.1,
            "inertia_formula": "(1/3)*120*0.95^2=36.1 kg*m^2",
            "damping_nm_s_per_rad": 50.0,
            "stiffness_nm_per_rad": 6.0,
            "theta_ref_rad": 0.0,
            "alpha_source": "PER_ENV_PREVIOUS_HINGE_OMEGA_OVER_0.02_S;_FIRST_SAMPLE_UNAVAILABLE",
            "friction_profiles": FRICTION_PROFILES,
            "authority": "MODELED_FROM_PARAMS",
            "solver_applied": False,
        },
        "arm_caps_nm": list(PRIMARY_CAPS_NM),
        "contingency_cap_nm": CONTINGENCY_CAP_NM,
        "ratios": {"F00": "N/A", "F05": 0.75, "F10": 0.75},
        "velocity_epsilon_rad_s": 0.001,
        "foot_loading_fraction": 0.10,
        "foot_slip_source": "simulator.contact_forces[:, feet_indices, 2] + Articulation.data.body_lin_vel_w[:, foot_body_ids, :]",
        "authorities": {
            "capacity_lambda": "ESTIMATE_ONLY_DIRECTIONAL_MARGIN",
            "pd_command": "ESTIMATE_ONLY_IMPLICIT_PD_COMMAND",
            "gravity": "ISAACLAB_GRAVITY_COMPENSATION_ESTIMATE",
            "state": "HIGH_LEVEL_ARTICULATION_DATA",
            "actual_generalized_torque": "UNAVAILABLE_NOT_USED",
        },
    }


def ladder_freeze(
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    status: str = "PLANNED_NOT_EXECUTED",
    rule16_admission: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if rows is None:
        return {
        "schema": LADDER_SCHEMA,
        "status": status,
        "registered_primary_caps_nm": list(PRIMARY_CAPS_NM),
        "registered_contingency_cap_nm": CONTINGENCY_CAP_NM,
        "profiles": {
            "tau_hi": "highest numeric nonbinding cap selected from the primary ladder",
            "tau_boundary": "highest numeric qualifying cap with matched F05/F10 E1 evidence",
            "tau_rescue": "immediately preceding higher registered cap than tau_boundary",
        },
        "selection": {
            "denominator_per_profile": 8,
            "qualifying_episodes": 8,
            "progress_gain_rad": 0.02,
            "strict_tau_req_order": ["F00", "F05", "F10"],
            "nondecreasing_lambda": True,
            "common_boundary": True,
            "contingency_trigger": "all six primary caps valid/nonbinding",
            "contingency_nonbinding_result": "V24_ARM_COMMAND_PATH_NOT_BINDING",
        },
        }
    payload = _derive_ladder(rows, status=status)
    if rule16_admission is not None:
        payload["rule16_admission"] = dict(rule16_admission)
    return payload


def certificate_threshold_freeze(
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    status: str = "PLANNED_NOT_EXECUTED",
    tau_hi_nm: float | None = None,
    rule16_admission: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if rows is not None:
        payload = _derive_threshold(rows, status=status, tau_hi_nm=tau_hi_nm)
        if rule16_admission is not None:
            payload["rule16_admission"] = dict(rule16_admission)
        return payload
    payload = {
        "schema": THRESHOLD_SCHEMA,
        "status": status,
        "window_control_steps": 25,
        "stable_grasp_steps": 20,
        "low_progress_rad": 0.04,
        "meaningful_progress_rad": 0.10,
        "rescue_gain_rad": 0.02,
        "directional_utilization_min": 0.90,
        "directional_clip_fraction_min": 0.30,
        "denominator_min": 8,
        "qualifying_min": 8,
        "lambda_zones": {
            "E0": "lambda < 0.5",
            "E1": "0.5 <= lambda < 1.0",
            "NEAR_E2": "lambda >= 1.0 with incomplete rescue",
            "E2": "confirmed only in held-out with rescue",
        },
        "foot_loading": {
            "threshold_fraction_of_body_weight": 0.10,
            "source": "simulator.contact_forces[:, feet_indices, 2]",
            "body_order": ["FL_foot", "RL_foot", "FR_foot", "RR_foot"],
        },
        "slip": {
            "threshold": "Q99_from_valid_F00_100Nm_calibration_windows",
            "freeze_before_heldout": True,
            "source": "simulator.contact_forces[:, feet_indices, 2] + Articulation.data.body_lin_vel_w[:, foot_body_ids, :]",
        },
        "exclusions": list(EXCLUSIONS),
    }
    if rule16_admission is not None:
        payload["rule16_admission"] = dict(rule16_admission)
    return payload


def artifact_plan() -> dict[str, Any]:
    return {
        "root": ARTIFACT_ROOT,
        "append_only": True,
        "files": list(REGISTERED_ARTIFACTS),
        "vitals": {
            "source": VITALS_SOURCE,
            "rows": VITAL_ARTIFACTS[0],
            "runtime_rows": VITAL_ARTIFACTS[1],
            "receipt": VITAL_ARTIFACTS[2],
            "owner_decision": OWNER_DECISION,
            "grasp_threshold": "14/16",
            "stage_reach_reference_band": dict(STAGE_REACH_REFERENCE_BAND),
            "parameter_health": "16/16",
            "measurement_vital_status": "PASS_VALID_MEASUREMENT_ADMISSION",
            "rule16_schema": RULE16_SCHEMA,
        },
        "gradient_admission": dict(GRADIENT_ADMISSION),
        "marginal_e1_pilot": {
            "registration_id": PILOT_REGISTRATION_ID,
            "status_before_pilot": PILOT_REQUIRED_STATUS,
            "artifact_root": PILOT_ARTIFACT_ROOT,
            "cells": ["DF1_FULL_SEED0", "DF1_FULL_SEED1", "DF1_RP0_SEED0", "DF1_RP0_SEED1"],
            "batches": 500,
            "save_frequency": 250,
            "num_envs": 4096,
            "candidate_buckets": ["F00", "F05", "F10"],
            "rescue_cap_nm": 25.0,
            "confirmed_e2_share": 0.0,
        },
        "foot_loading": {
            "threshold_fraction_of_body_weight": 0.10,
            "source": "simulator.contact_forces[:, feet_indices, 2]",
            "body_order": ["FL_foot", "RL_foot", "FR_foot", "RR_foot"],
        },
        "foot_slip_source": "simulator.contact_forces[:, feet_indices, 2] + Articulation.data.body_lin_vel_w[:, foot_body_ids, :]",
        "smoke": {
            "envs": 3,
            "profiles": ["F00", "F05", "F10"],
            "modes": ["HI_FULL"],
            "control_steps": 64,
            "rows": 9,
            "evidentiary": False,
        },
        "heldout_modes": list(RUNTIME_MODES),
        "heldout_terminal_status": PILOT_REQUIRED_STATUS,
        "no_duplicate_rescue_when_same_as_hi": True,
    }


def _exact_float_list(value: Any, expected: Sequence[float], *, label: str) -> None:
    if not isinstance(value, (list, tuple)) or len(value) != len(expected):
        raise ValueError(f"{label} must contain exactly {len(expected)} values")
    actual = [_finite(item, label=f"{label}[{index}]") for index, item in enumerate(value)]
    if actual != [float(item) for item in expected]:
        raise ValueError(f"{label} does not match the frozen contract")


def _validate_parameter_vitals(
    row: Mapping[str, Any],
    *,
    expected_cap: float,
    expected_profile: str,
    label: str,
) -> None:
    vitals = row.get("parameter_vitals")
    if not isinstance(vitals, Mapping):
        raise ValueError(f"{label}.parameter_vitals must be a mapping")
    if (
        vitals.get("schema") != "a2_piper_v24_p2_parameter_vitals_v1"
        or vitals.get("authority") != "MODELED_FROM_PARAMS"
        or vitals.get("solver_applied") is not False
        or vitals.get("actual_generalized_torque") != "UNAVAILABLE_NOT_USED"
    ):
        raise ValueError(f"{label}.parameter_vitals top authority/schema contract mismatch")

    arm = vitals.get("arm")
    if not isinstance(arm, Mapping):
        raise ValueError(f"{label}.parameter_vitals.arm must be a mapping")
    if arm.get("joint_names") != [f"arm_j{index}" for index in range(1, 7)]:
        raise ValueError(f"{label}.parameter_vitals arm joint names mismatch")
    if arm.get("registered_cap_values_nm") != list(REGISTERED_CAPS_NM):
        raise ValueError(f"{label}.parameter_vitals registered arm caps mismatch")
    if _finite(arm.get("registered_active_cap_nm"), label=f"{label}.parameter_vitals.arm.registered_active_cap_nm") != expected_cap:
        raise ValueError(f"{label}.parameter_vitals active cap disagrees with row treatment")
    for field in ("requested_effort_limit_nm", "readback_effort_limit_nm", "contract_effort_limit_nm"):
        _exact_float_list(arm.get(field), [expected_cap] * 6, label=f"{label}.parameter_vitals.arm.{field}")

    gripper = vitals.get("gripper")
    if not isinstance(gripper, Mapping) or gripper.get("joint_names") != ["arm_j7", "arm_j8"]:
        raise ValueError(f"{label}.parameter_vitals gripper face mismatch")
    if gripper.get("swept_by_arm_cap") is not False or gripper.get("unchanged_by_arm_cap") is not True:
        raise ValueError(f"{label}.parameter_vitals gripper sweep/unchanged flags mismatch")
    for field, expected in (
        ("effort_limit_nm", (45.0, 45.0)),
        ("stiffness_nm_per_rad", (1300.0, 1300.0)),
        ("damping_nm_s_per_rad", (32.0, 32.0)),
    ):
        face = gripper.get(field)
        if not isinstance(face, Mapping):
            raise ValueError(f"{label}.parameter_vitals.gripper.{field} must be a mapping")
        _exact_float_list(face.get("readback"), expected, label=f"{label}.parameter_vitals.gripper.{field}.readback")
        _exact_float_list(face.get("contract"), expected, label=f"{label}.parameter_vitals.gripper.{field}.contract")

    profile = FRICTION_PROFILES.get(expected_profile)
    if profile is None:
        raise ValueError(f"unknown expected friction profile {expected_profile!r}")
    expected_friction = {
        "static_friction_nm": profile["static_effort_nm"],
        "dynamic_friction_nm": profile["dynamic_effort_nm"],
        "viscous_friction_nm_s_per_rad": profile["viscous_coefficient_nm_s_per_rad"],
    }
    door = vitals.get("door_friction")
    if not isinstance(door, Mapping):
        raise ValueError(f"{label}.parameter_vitals.door_friction must be a mapping")
    if (
        not isinstance(door.get("hinge_joint_name"), str)
        or isinstance(door.get("hinge_joint_id"), bool)
        or not isinstance(door.get("hinge_joint_id"), int)
        or door.get("non_hinge_unchanged") is not True
        or door.get("authority") != "MODELED_FROM_PARAMS"
        or door.get("solver_applied") is not False
        or door.get("actual_generalized_torque") != "UNAVAILABLE_NOT_USED"
        or door.get("units") != {
            "static_friction_nm": "N*m",
            "dynamic_friction_nm": "N*m",
            "viscous_friction_nm_s_per_rad": "N*m*s/rad",
        }
    ):
        raise ValueError(f"{label}.parameter_vitals door authority/identity/units mismatch")
    non_hinge_ids = door.get("non_hinge_joint_ids")
    if (
        not isinstance(non_hinge_ids, (list, tuple))
        or any(isinstance(item, bool) or not isinstance(item, int) for item in non_hinge_ids)
        or door["hinge_joint_id"] in non_hinge_ids
    ):
        raise ValueError(f"{label}.parameter_vitals non-hinge joint identity mismatch")
    for field in ("requested", "readback", "contract"):
        values = door.get(field)
        if not isinstance(values, Mapping) or dict(values) != expected_friction:
            raise ValueError(f"{label}.parameter_vitals.door_friction.{field} disagrees with {expected_profile}")
    if (
        not isinstance(door.get("non_hinge_before"), Mapping)
        or not isinstance(door.get("non_hinge_after"), Mapping)
        or door["non_hinge_before"] != door["non_hinge_after"]
    ):
        raise ValueError(f"{label}.parameter_vitals non-hinge before/after mismatch")

    unit_boundary = vitals.get("unit_boundary")
    if not isinstance(unit_boundary, Mapping) or (
        unit_boundary.get("analysis_surface") != "radian"
        or unit_boundary.get("degree_per_radian_boundary") != 57.3
        or unit_boundary.get("static_dynamic_effort_conversion_applied") is not False
        or unit_boundary.get("viscous_conversion_applied") is not False
    ):
        raise ValueError(f"{label}.parameter_vitals unit boundary mismatch")


def _validate_window_selection(row: Mapping[str, Any], *, label: str) -> None:
    selection = row.get("window_selection")
    status = row.get("window_selection_status")
    reason = row.get("window_selection_reason")
    admission_status = row.get("window_selection_admission_status")
    if selection not in {WINDOW_SELECTION_ADMITTED, WINDOW_SELECTION_FALLBACK}:
        raise ValueError(f"{label} window selection enum is unsupported")
    if status != selection or reason != selection:
        raise ValueError(f"{label} window selection enum/status/reason mismatch")
    if not isinstance(row.get("window_selection_valid"), bool) or not isinstance(row.get("excluded_window_selection"), bool):
        raise TypeError(f"{label} window selection flags must be bool")
    if row["window_selection_valid"] is not (not row["excluded_window_selection"]):
        raise ValueError(f"{label} window selection flags are not exact inverses")
    if not isinstance(row.get("model_valid"), bool):
        raise TypeError(f"{label}.model_valid must be bool")
    stable_count = row.get("window_stable_grasp_count")
    if stable_count is not None and (isinstance(stable_count, bool) or not isinstance(stable_count, int) or not 0 <= stable_count <= 25):
        raise ValueError(f"{label}.window_stable_grasp_count must be null or an integer in 0..25")
    stage_ids = row.get("window_stage_ids")
    if not isinstance(stage_ids, (list, tuple)) or any(isinstance(stage, bool) or not isinstance(stage, int) for stage in stage_ids):
        raise ValueError(f"{label}.window_stage_ids must be an integer sequence")
    if "window_stage_reach_valid" in row and row.get("window_stage_reach_valid") is not all(stage in {3, 4} for stage in stage_ids):
        raise ValueError(f"{label}.window_stage_reach_valid disagrees with the stage-id reference band")
    source_status = row.get("source_status")
    grasp_available = row.get("grasp_source_unavailable") is False and isinstance(source_status, Mapping) and source_status.get("grasp") == "AVAILABLE"
    if selection == WINDOW_SELECTION_ADMITTED:
        if (
            admission_status != WINDOW_SELECTION_ADMITTED_STATUS
            or row["window_selection_valid"] is not True
            or row["excluded_window_selection"] is not False
            or row.get("stable_grasp") is not True
            or stable_count is None
            or stable_count < 20
            or not stage_ids
            or any(stage not in {3, 4} for stage in stage_ids)
            or not grasp_available
            or row.get("valid") is not row.get("model_valid")
        ):
            raise ValueError(f"{label} admitted window selection contract failed")
    else:
        missing_grasp = (
            stable_count is None
            and row.get("stable_grasp") is None
            and row.get("grasp_source_unavailable") is True
            and isinstance(source_status, Mapping)
            and source_status.get("grasp") == "SOURCE_UNAVAILABLE"
        )
        available_grasp = (
            stable_count is not None
            and row.get("stable_grasp") is not None
            and row.get("grasp_source_unavailable") is False
            and isinstance(source_status, Mapping)
            and source_status.get("grasp") == "AVAILABLE"
        )
        if (
            admission_status != WINDOW_SELECTION_FALLBACK_STATUS
            or row["window_selection_valid"] is not False
            or row["excluded_window_selection"] is not True
            or row.get("valid") is not False
            or not (missing_grasp or available_grasp)
        ):
            raise ValueError(f"{label} fallback window selection must be explicitly non-admissible")


def _validate_raw_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    kind: str,
    heldout_mode_caps: Mapping[str, float] | None = None,
) -> list[dict[str, Any]]:
    if isinstance(rows, (str, bytes)) or not rows:
        raise ValueError(f"{kind} raw rows must be a non-empty sequence")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    has_contingency_rows = any(isinstance(row, Mapping) and row.get("cap_nm") == CONTINGENCY_CAP_NM for row in rows)
    expected_caps = (
        REGISTERED_CAPS_NM
        if kind == "calibration_with_contingency" or (kind == "heldout" and has_contingency_rows)
        else PRIMARY_CAPS_NM
    )
    if kind == "heldout" and heldout_mode_caps is not None:
        if set(heldout_mode_caps) != set(RUNTIME_MODES):
            raise ValueError("heldout mode-cap map must define every registered runtime mode")
        if any(float(cap) not in (*PRIMARY_CAPS_NM, CONTINGENCY_CAP_NM) for cap in heldout_mode_caps.values()):
            raise ValueError("heldout mode-cap map contains an unregistered cap")
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise TypeError(f"{kind} row {index} must be a mapping")
        profile = raw.get("profile")
        cap = _finite(raw.get("cap_nm"), label=f"{kind}[{index}].cap_nm")
        scenario = raw.get("scenario_id")
        if profile not in FRICTION_PROFILES:
            raise ValueError(f"{kind} row {index} has an unknown friction profile")
        if cap not in expected_caps:
            raise ValueError(f"{kind} row {index} has an unregistered cap")
        if scenario not in SCENARIO_IDS:
            raise ValueError(f"{kind} row {index} scenario_id must be one of {SCENARIO_IDS!r}")
        mode = raw.get("mode")
        expected_modes = RUNTIME_MODES if kind == "heldout" else ("HI_FULL",)
        if mode not in expected_modes:
            raise ValueError(f"{kind} row {index} mode must be one of {expected_modes!r}")
        if kind == "heldout" and heldout_mode_caps is not None and cap != float(heldout_mode_caps[mode]):
            raise ValueError(f"heldout row {index} cap does not match the registered {mode} treatment")
        expected_seed = 24022 if kind == "heldout" else 24021
        if raw.get("seed") != expected_seed:
            raise ValueError(f"{kind} rows must carry seed {expected_seed}")
        expected_continuities = {"HELDOUT"} if kind == "heldout" else {"CALIBRATION", "CALIBRATION_CONTINGENCY"}
        continuity = raw.get("continuity_id")
        if continuity not in expected_continuities:
            raise ValueError(f"{kind} row {index} has an invalid continuity_id")
        if cap == CONTINGENCY_CAP_NM and continuity != "CALIBRATION_CONTINGENCY":
            raise ValueError("10 Nm calibration rows require CALIBRATION_CONTINGENCY continuity")
        if cap != CONTINGENCY_CAP_NM and continuity == "CALIBRATION_CONTINGENCY":
            raise ValueError("primary calibration rows cannot use contingency continuity")
        if kind == "heldout" and raw.get("authority") != RUNTIME_AUTHORITY_SET:
            raise ValueError("heldout row authority set mismatch")
        if kind.startswith("calibration") and raw.get("authority") != RUNTIME_AUTHORITY_SET:
            raise ValueError("calibration row authority set mismatch")
        if raw.get("window_transition_count") != 25:
            raise ValueError(f"{kind}[{index}] must summarize exactly 25 transitions")
        start_step = raw.get("window_start_step")
        end_step = raw.get("window_end_step")
        if (
            isinstance(start_step, bool)
            or not isinstance(start_step, int)
            or isinstance(end_step, bool)
            or not isinstance(end_step, int)
            or end_step - start_step != 24
        ):
            raise ValueError(f"{kind}[{index}] has an invalid frozen 25-transition step range")
        for raw_field in ("tau_required_nm", "lambda_load", "directional_utilization", "directional_clipped", "foot_slip_m_s", "episode_step", "theta_pre_rad", "theta_post_rad", "theta_delta_rad"):
            if raw_field in raw:
                raise ValueError(f"{kind}[{index}] contains an unaggregated single-transition field {raw_field}")
        key = (profile, cap, scenario, continuity, mode)
        if key in seen:
            raise ValueError(f"{kind} rows contain duplicate identity {key!r}")
        seen.add(key)
        row = dict(raw)
        for field in ("theta_start_rad", "theta_end_rad", "progress_recovery_delta_rad", "directional_clip_fraction_median"):
            row[field] = _finite(row.get(field), label=f"{kind}[{index}].{field}")
        if not math.isclose(row["theta_end_rad"] - row["theta_start_rad"], row["progress_recovery_delta_rad"], rel_tol=1.0e-6, abs_tol=1.0e-6):
            raise ValueError(f"{kind}[{index}] progress does not match frozen pre/post theta endpoints")
        directional_high_effort = row.get("directional_high_effort")
        if not isinstance(directional_high_effort, bool):
            raise TypeError(f"{kind}[{index}].directional_high_effort must be bool")
        for field in ("valid", "model_valid", "nonbinding", "foot_slip_valid"):
            if not isinstance(row.get(field), bool):
                raise TypeError(f"{kind}[{index}].{field} must be bool")
        if row.get("alpha_valid") is not True:
            raise ValueError(f"{kind}[{index}] must contain a completed acceleration source")
        source_flags = ("grasp_source_unavailable", "model_source_unavailable")
        if any(not isinstance(row.get(field), bool) for field in source_flags):
            raise TypeError(f"{kind}[{index}] must type grasp and model source availability independently")
        grasp_source_unavailable = row["grasp_source_unavailable"]
        model_source_unavailable = row["model_source_unavailable"]
        source_unavailable = "SOURCE_UNAVAILABLE" if any((grasp_source_unavailable, model_source_unavailable)) else None
        if row.get("source_unavailable") != source_unavailable:
            raise ValueError(f"{kind}[{index}].source_unavailable is not derived from typed source fields")
        source_status = row.get("source_status")
        if not isinstance(source_status, Mapping) or set(source_status) != {"foot", "grasp", "model"}:
            raise ValueError(f"{kind}[{index}].source_status must contain complete typed source statuses")
        for source_name, unavailable in (("grasp", grasp_source_unavailable), ("model", model_source_unavailable)):
            expected_status = "SOURCE_UNAVAILABLE" if unavailable else "AVAILABLE"
            if source_status.get(source_name) != expected_status:
                raise ValueError(f"{kind}[{index}].source_status.{source_name} disagrees with typed source field")
        if source_status.get("foot") != "AVAILABLE":
            raise ValueError(f"{kind}[{index}].source_status.foot must be AVAILABLE")
        max_slip = row.get("max_loaded_foot_slip_m_s")
        if row["foot_slip_valid"]:
            row["max_loaded_foot_slip_m_s"] = _finite(max_slip, label=f"{kind}[{index}].max_loaded_foot_slip_m_s")
        else:
            if max_slip is not None:
                raise ValueError(f"{kind}[{index}] has an invalid foot-slip measurement")
        model_fields = ("tau_req_median_nm", "lambda_median", "lambda", "directional_utilization_median")
        model_values = {}
        for field in model_fields:
            value = row.get(field)
            model_values[field] = None if value is None else _finite(value, label=f"{kind}[{index}].{field}")
        if not model_source_unavailable and any(value is None for value in model_values.values()):
            raise ValueError(f"{kind}[{index}] has available model source but incomplete model medians")
        recomputed_high_effort = (
            not model_source_unavailable
            and model_values["directional_utilization_median"] >= 0.90
            and row["directional_clip_fraction_median"] >= 0.30
        )
        if directional_high_effort is not recomputed_high_effort:
            raise ValueError(f"{kind}[{index}].directional_high_effort disagrees with typed model source/utilization")
        source_api = row.get("source_api")
        if not isinstance(source_api, Mapping) or not source_api:
            raise ValueError(f"{kind}[{index}].source_api must identify the raw source tensors")
        row["cap_nm"] = cap
        row["profile"] = profile
        row["scenario_id"] = scenario
        row["continuity_id"] = continuity
        row["mode"] = mode
        row["stable_grasp"] = row.get("stable_grasp")
        if row["stable_grasp"] is not None and not isinstance(row["stable_grasp"], bool):
            raise TypeError(f"{kind}[{index}].stable_grasp must be bool or null")
        if row["stable_grasp"] is None and not grasp_source_unavailable:
            raise ValueError(f"{kind}[{index}] missing stable-grasp source must be typed unavailable")
        if row["stable_grasp"] is not None and grasp_source_unavailable:
            raise ValueError(f"{kind}[{index}] stable-grasp source availability flag mismatch")
        stable_fraction = row.get("stable_grasp_fraction")
        if row["stable_grasp"] is None:
            if stable_fraction is not None or not grasp_source_unavailable:
                raise ValueError(f"{kind}[{index}] missing stable-grasp window source")
        else:
            stable_fraction = _finite(stable_fraction, label=f"{kind}[{index}].stable_grasp_fraction")
            if not 0.0 <= stable_fraction <= 1.0 or row["stable_grasp"] is not (stable_fraction >= 20 / 25):
                raise ValueError(f"{kind}[{index}] stable-grasp fraction/boolean mismatch")
        for field in ("excluded_geometry", "excluded_grasp", "excluded_direction", "excluded_slip", "excluded_pathology"):
            if not isinstance(row.get(field), bool):
                raise TypeError(f"{kind}[{index}].{field} must be bool")
        if row["stable_grasp"] is None and row["excluded_grasp"]:
            raise ValueError(f"{kind}[{index}] cannot exclude grasp when the grasp source is unavailable")
        if row["stable_grasp"] is not None and row["excluded_grasp"] is not (not row["stable_grasp"]):
            raise ValueError(f"{kind}[{index}] grasp exclusion must reflect the frozen 20/25 window threshold")
        _validate_window_selection(row, label=f"{kind}[{index}]")
        _validate_parameter_vitals(row, expected_cap=cap, expected_profile=profile, label=f"{kind}[{index}]")
        if row.get("rescue_progress_rad") is not None or row.get("rescue_gain_rad") is not None:
            raise ValueError(f"{kind}[{index}] rescue progress/gain must be derived from matched cells, not a raw row")
        row["source_unavailable"] = source_unavailable
        row["excluded"] = tuple(name for name in EXCLUSIONS if row.get(f"excluded_{name.lower()}") is True)
        normalized.append(row)
    if kind == "heldout" and heldout_mode_caps is not None:
        expected_identity = {
            (profile, float(heldout_mode_caps[mode]), scenario, mode)
            for profile in FRICTION_PROFILES
            for scenario in SCENARIO_IDS
            for mode in RUNTIME_MODES
        }
    else:
        expected_identity = {
            (profile, float(cap), scenario, mode)
            for profile in FRICTION_PROFILES
            for cap in expected_caps
            for scenario in SCENARIO_IDS
            for mode in (RUNTIME_MODES if kind == "heldout" else ("HI_FULL",))
        }
    actual_identity = {(row["profile"], row["cap_nm"], row["scenario_id"], row["mode"]) for row in normalized}
    if actual_identity != expected_identity:
        missing = sorted(expected_identity - actual_identity)
        extra = sorted(actual_identity - expected_identity)
        raise ValueError(f"{kind} rows must contain exact registered identities; missing={missing[:3]!r} extra={extra[:3]!r}")
    return normalized


def _read_vital_source_rows() -> list[dict[str, Any]]:
    source = require_file(VITALS_SOURCE, label="P2 immutable sham vitals source")
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != len(SCENARIO_IDS) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("P2 immutable sham vitals source must contain exactly 16 mapping rows")
    return rows


def _validate_vital_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(rows, (str, bytes)) or len(rows) != len(SCENARIO_IDS):
        raise ValueError("P2 immutable sham vitals require exactly 16 rows")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise TypeError(f"vitals row {index} must be a mapping")
        label = f"vitals[{index}]"
        if (
            raw.get("env_id") != index
            or raw.get("scenario_id") != SCENARIO_IDS[index]
            or raw.get("seed") != 0
            or raw.get("profile") != "F00"
            or raw.get("cap_nm") != 40.0
            or raw.get("mode") != "HI_FULL"
            or raw.get("continuity_id") != "VITALS_R12_FIXED_SHAM"
        ):
            raise ValueError(f"{label} identity must be env{index}/S{index:02d}, seed0, F00, cap40, HI_FULL")
        if raw.get("authority") != RUNTIME_AUTHORITY_SET:
            raise ValueError(f"{label} authority set mismatch")
        if raw.get("window_transition_count") != 25:
            raise ValueError(f"{label} must summarize exactly 25 transitions")
        for field in ("valid", "model_valid", "foot_slip_valid", "grasp_source_unavailable", "model_source_unavailable"):
            if not isinstance(raw.get(field), bool):
                raise TypeError(f"{label}.{field} must be bool")
        if raw.get("source_unavailable") != ("SOURCE_UNAVAILABLE" if raw["grasp_source_unavailable"] or raw["model_source_unavailable"] else None):
            raise ValueError(f"{label}.source_unavailable disagrees with typed source fields")
        source_status = raw.get("source_status")
        if not isinstance(source_status, Mapping) or source_status.get("foot") != "AVAILABLE":
            raise ValueError(f"{label} foot source status must be AVAILABLE")
        expected_grasp_status = "SOURCE_UNAVAILABLE" if raw["grasp_source_unavailable"] else "AVAILABLE"
        if source_status.get("grasp") != expected_grasp_status:
            raise ValueError(f"{label}.source_status.grasp disagrees with typed grasp source flag")
        expected_model_status = "SOURCE_UNAVAILABLE" if raw["model_source_unavailable"] else "AVAILABLE"
        if source_status.get("model") != expected_model_status:
            raise ValueError(f"{label}.source_status.model disagrees with model source flag")
        stable_grasp = raw.get("stable_grasp")
        if stable_grasp is not None and not isinstance(stable_grasp, bool):
            raise TypeError(f"{label}.stable_grasp must be bool or null")
        if stable_grasp is None and raw["grasp_source_unavailable"] is not True:
            raise ValueError(f"{label} missing stable-grasp source must be typed unavailable")
        if stable_grasp is not None and raw["grasp_source_unavailable"] is not False:
            raise ValueError(f"{label} stable-grasp source availability flag mismatch")
        if not isinstance(raw.get("source_api"), Mapping) or not raw["source_api"]:
            raise ValueError(f"{label}.source_api must identify source tensors")
        key = (raw["env_id"], raw["scenario_id"], raw["seed"], raw["profile"], raw["cap_nm"], raw["mode"], raw["continuity_id"])
        if key in seen:
            raise ValueError(f"duplicate vital identity {key!r}")
        seen.add(key)
        _validate_window_selection(raw, label=label)
        _validate_parameter_vitals(raw, expected_cap=40.0, expected_profile="F00", label=label)
        item = dict(raw)
        item["excluded"] = tuple(name for name in EXCLUSIONS if item.get(f"excluded_{name.lower()}") is True)
        normalized.append(item)
    expected_keys = {
        (index, SCENARIO_IDS[index], 0, "F00", 40.0, "HI_FULL", "VITALS_R12_FIXED_SHAM")
        for index in range(len(SCENARIO_IDS))
    }
    if seen != expected_keys:
        raise ValueError("P2 immutable sham vitals identities are not exactly env0..15/S00..S15")
    return normalized


def _path_reference(path: str | Path, *, require_file_exists: bool = True) -> dict[str, str]:
    target = Path(path)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if require_file_exists:
        target = require_file(target, label="P2 referenced artifact").resolve()
    else:
        target = target.resolve()
    return {"relative": rel_path(target), "absolute": str(target)}


def _receipt_reference(relative: str) -> dict[str, str]:
    target = (REPO_ROOT / ARTIFACT_ROOT / relative).resolve()
    return {"relative": rel_path(target), "absolute": str(target)}


def _build_rule16_admission(
    *,
    grasp_count: int,
    stage_reach_count: int,
    parameter_count: int,
) -> dict[str, Any]:
    admission = {
        "schema": RULE16_SCHEMA,
        "admission_id": "RULE16_P2_R12",
        "status": "PASS",
        "owner_decision_artifact": _path_reference(OWNER_DECISION),
        "vitals_receipt_artifact": _receipt_reference(VITAL_ARTIFACTS[2]),
        "source_artifact": _path_reference(VITALS_SOURCE, require_file_exists=False),
        "grasp_vital": {"count": grasp_count, "required": 14, "pass": grasp_count >= 14},
        "stage_reach_vital": {
            "count": stage_reach_count,
            "required": STAGE_REACH_REFERENCE_BAND["required_env_count"],
            "pass": stage_reach_count == STAGE_REACH_REFERENCE_BAND["required_env_count"],
            "reference_band": dict(STAGE_REACH_REFERENCE_BAND),
        },
        "parameter_vital": {"count": parameter_count, "required": 16, "pass": parameter_count == 16},
        "gradient_admission": dict(GRADIENT_ADMISSION),
    }
    if not all(
        admission[key]["pass"] for key in ("grasp_vital", "stage_reach_vital", "parameter_vital")
    ):
        raise ValueError("Rule16 vitals did not pass grasp/stage-reach/parameter admission")
    return admission


def _validate_rule16_admission(payload: Mapping[str, Any], *, require_source_files: bool = False) -> None:
    if not isinstance(payload, Mapping) or payload.get("schema") != RULE16_SCHEMA:
        raise ValueError("Rule16 admission schema is missing or invalid")
    if payload.get("admission_id") != "RULE16_P2_R12" or payload.get("status") != "PASS":
        raise ValueError("Rule16 admission identity/status is invalid")
    if payload.get("owner_decision_artifact") != _path_reference(OWNER_DECISION):
        raise ValueError("Rule16 owner-decision provenance is not canonical")
    if payload.get("source_artifact") != _path_reference(VITALS_SOURCE, require_file_exists=False):
        raise ValueError("Rule16 source-vitals provenance is not canonical")
    expected_receipt = _receipt_reference(VITAL_ARTIFACTS[2])
    if payload.get("vitals_receipt_artifact") != expected_receipt:
        raise ValueError("Rule16 receipt provenance is not canonical")
    stage = payload.get("stage_reach_vital")
    if not isinstance(stage, Mapping) or stage.get("reference_band") != STAGE_REACH_REFERENCE_BAND:
        raise ValueError("Rule16 stage-reach reference band is missing or mutated")
    for key, required in (("grasp_vital", 14), ("stage_reach_vital", 16), ("parameter_vital", 16)):
        vital = payload.get(key)
        if not isinstance(vital, Mapping) or vital.get("required") != required or vital.get("pass") is not True:
            raise ValueError(f"Rule16 {key} is not admitted")
        if isinstance(vital.get("count"), bool) or not isinstance(vital.get("count"), int) or vital["count"] < required:
            raise ValueError(f"Rule16 {key} count is below its requirement")
    if payload.get("gradient_admission") != GRADIENT_ADMISSION:
        raise ValueError("Rule16 gradient-admission provenance is not canonical")
    if require_source_files:
        require_file(payload["owner_decision_artifact"]["absolute"], label="Rule16 owner decision")
        require_file(payload["source_artifact"]["absolute"], label="Rule16 vitals source")


def _build_vital_receipt(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = _validate_vital_rows(rows)
    grasp_count = sum(
        row.get("stable_grasp") is True
        and row.get("window_selection_valid") is True
        and row.get("excluded_window_selection") is False
        and row.get("grasp_source_unavailable") is False
        and isinstance(row.get("source_status"), Mapping)
        and row["source_status"].get("grasp") == "AVAILABLE"
        for row in normalized
    )
    parameter_count = len(normalized)
    stage_reach_count = sum(
        row.get("window_transition_count") == STAGE_REACH_REFERENCE_BAND["window_transition_count"]
        and row.get("window_stable_grasp_count", 0) >= STAGE_REACH_REFERENCE_BAND["minimum_current_stable_grasp_rows"]
        and row.get("window_selection_valid") is True
        and row.get("stable_grasp") is True
        and set(row.get("window_stage_ids", ())).issubset(set(STAGE_REACH_REFERENCE_BAND["stage_ids"]))
        and bool(row.get("window_stage_ids"))
        for row in normalized
    )
    model_valid_count = sum(row.get("model_valid") is True for row in normalized)
    model_unavailable_count = sum(row.get("model_source_unavailable") is True for row in normalized)
    foot_valid_count = sum(row.get("foot_slip_valid") is True for row in normalized)
    grasp_pass = grasp_count >= 14
    parameter_pass = parameter_count == 16
    rule16 = _build_rule16_admission(
        grasp_count=grasp_count,
        stage_reach_count=stage_reach_count,
        parameter_count=parameter_count,
    )
    return {
        "schema": VITALS_RECEIPT_SCHEMA,
        "status": "PASS",
        "measurement_vital_status": "PASS_VALID_MEASUREMENT_ADMISSION",
        "r10_terminal_result": "V24_E1_DENOMINATOR_INSUFFICIENT",
        "r10_scientific_reclassification": "SUSPECTED_INVALID_MEASUREMENT_PENDING_VITALS",
        "p2_scientific_verdict": None,
        "scientific_verdict": None,
        "owner_decision": "P2_TERMINAL_RECLASSIFIED + DIAGNOSE_THEN_RERUN",
        "owner_decision_artifact": _path_reference(OWNER_DECISION),
        "source_artifact": _path_reference(VITALS_SOURCE, require_file_exists=False),
        "grasp_vital": {"count": grasp_count, "required": 14, "pass": grasp_pass},
        "stage_reach_vital": rule16["stage_reach_vital"],
        "parameter_vitals": {"count": parameter_count, "required": 16, "pass": parameter_pass},
        "rule16_admission": rule16,
        "descriptive_counts": {
            "model_valid": model_valid_count,
            "model_source_unavailable": model_unavailable_count,
            "foot_slip_valid": foot_valid_count,
        },
        "row_count": len(normalized),
        "does_not_adjudicate": ["denominator", "ladder", "E_region", "physics"],
    }


def _require_completed_vital_receipt(payload: Mapping[str, Any], *, require_source_files: bool = True) -> None:
    if (
        payload.get("schema") != VITALS_RECEIPT_SCHEMA
        or payload.get("status") != "PASS"
        or payload.get("measurement_vital_status") != "PASS_VALID_MEASUREMENT_ADMISSION"
        or payload.get("r10_terminal_result") != "V24_E1_DENOMINATOR_INSUFFICIENT"
        or payload.get("r10_scientific_reclassification") != "SUSPECTED_INVALID_MEASUREMENT_PENDING_VITALS"
        or payload.get("p2_scientific_verdict") is not None
        or payload.get("grasp_vital", {}).get("pass") is not True
        or payload.get("parameter_vitals", {}).get("pass") is not True
    ):
        raise RuntimeError("P2 smoke/calibration and downstream stages require a completed PASS sham-vitals receipt")
    try:
        _validate_rule16_admission(payload.get("rule16_admission"), require_source_files=require_source_files)
    except (TypeError, ValueError, KeyError) as exc:
        raise RuntimeError("P2 downstream stages require a completed Rule16 vitals admission") from exc


def _derive_ladder(rows: Sequence[Mapping[str, Any]], *, status: str) -> dict[str, Any]:
    has_contingency = any(isinstance(row, Mapping) and row.get("cap_nm") == CONTINGENCY_CAP_NM for row in rows)
    normalized = _validate_raw_rows(rows, kind="calibration_with_contingency" if has_contingency else "calibration")
    primary_by_cap = {cap: [row for row in normalized if row["cap_nm"] == cap] for cap in REGISTERED_CAPS_NM}
    all_six_valid_nonbinding = all(
        row["valid"] and row["nonbinding"]
        for row in normalized
        if row["cap_nm"] in PRIMARY_CAPS_NM
    )
    nonbinding_caps = [cap for cap in PRIMARY_CAPS_NM if all(row["valid"] and row["nonbinding"] for row in primary_by_cap[cap])]
    tau_hi = max(nonbinding_caps) if nonbinding_caps else None
    qualifying_caps = [cap for cap in CAP_ORDER_DESCENDING_NM if qualifies_boundary_cap(normalized, cap)]
    tau_boundary = qualifying_caps[0] if qualifying_caps else None
    ordered = list(CAP_ORDER_DESCENDING_NM)
    rescue = ordered[ordered.index(tau_boundary) - 1] if tau_boundary is not None and ordered.index(tau_boundary) > 0 else None
    contingency_rows = [row for row in normalized if row["cap_nm"] == CONTINGENCY_CAP_NM]
    if contingency_rows and len(contingency_rows) != 48:
        raise ValueError("10 Nm contingency must contain exactly F00/F05/F10 x 16 rows")
    if all_six_valid_nonbinding and not contingency_rows:
        raise ValueError("10 Nm contingency is required exactly once when all six primary caps are valid/nonbinding")
    if not all_six_valid_nonbinding and contingency_rows:
        raise ValueError("10 Nm contingency is forbidden when the all-six-primary trigger is false")
    contingency_nonbinding = bool(contingency_rows) and all(row["valid"] and row["nonbinding"] for row in contingency_rows)
    command_path_binding = not (all_six_valid_nonbinding and contingency_nonbinding)
    return {
        "schema": LADDER_SCHEMA,
        "status": status,
        "registered_primary_caps_nm": list(PRIMARY_CAPS_NM),
        "registered_contingency_cap_nm": CONTINGENCY_CAP_NM,
        "candidate_order_descending_nm": list(ordered),
        "tau_hi_nm": tau_hi,
        "tau_boundary_nm": tau_boundary,
        "tau_rescue_nm": rescue,
        "qualifying_caps_nm": qualifying_caps,
        "all_six_primary_valid_nonbinding": all_six_valid_nonbinding,
        "contingency_triggered": all_six_valid_nonbinding,
        "contingency_one_shot_required": all_six_valid_nonbinding,
        "contingency_rows_present": bool(contingency_rows),
        "contingency_nonbinding": contingency_nonbinding,
        "contingency_result": (
            "V24_ARM_COMMAND_PATH_NOT_BINDING"
            if contingency_nonbinding
            else "V24_CONTINGENCY_BOUNDARY_BINDING"
            if contingency_rows
            else "NOT_TRIGGERED"
        ),
        "command_path_binding": command_path_binding,
        "selection": {
            "denominator_per_profile": 8,
            "qualifying_episodes": 8,
            "progress_gain_rad": 0.02,
            "strict_tau_req_order": ["F00", "F05", "F10"],
            "nondecreasing_lambda": True,
            "common_boundary": True,
        },
    }


def _derive_threshold(rows: Sequence[Mapping[str, Any]], *, status: str, tau_hi_nm: float | None = None) -> dict[str, Any]:
    has_contingency = any(isinstance(row, Mapping) and row.get("cap_nm") == CONTINGENCY_CAP_NM for row in rows)
    normalized = _validate_raw_rows(rows, kind="calibration_with_contingency" if has_contingency else "calibration")
    normalized = [row for row in normalized if row["cap_nm"] in PRIMARY_CAPS_NM]
    tau_hi = _finite(tau_hi_nm, label="tau_hi_nm") if tau_hi_nm is not None else 100.0
    valid_slip = [
        _finite(row.get("max_loaded_foot_slip_m_s"), label="max_loaded_foot_slip_m_s")
        for row in normalized
        if row["valid"] and row["cap_nm"] == tau_hi and row["profile"] == "F00" and _row_is_usable(row)
    ]
    if len(valid_slip) < 8:
        raise ValueError("certificate threshold freeze requires >=8 valid F00/tau_hi loaded-foot slip windows")
    ordered = sorted(valid_slip)
    q99_index = min(len(ordered) - 1, math.ceil(0.99 * len(ordered)) - 1)
    return {
        "schema": THRESHOLD_SCHEMA,
        "status": status,
        "window_control_steps": 25,
        "stable_grasp_steps": 20,
        "low_progress_rad": 0.04,
        "meaningful_progress_rad": 0.10,
        "rescue_gain_rad": 0.02,
        "directional_utilization_min": 0.90,
        "directional_clip_fraction_min": 0.30,
        "denominator_min": 8,
        "qualifying_min": 8,
        "foot_slip_q99_m_s": ordered[q99_index],
        "tau_hi_nm": tau_hi,
        "foot_slip_source": "simulator.contact_forces[:, feet_indices, 2] + Articulation.data.body_lin_vel_w[:, foot_body_ids, :]",
        "foot_slip_valid_windows": len(valid_slip),
        "freeze_before_heldout": True,
        "exclusions": list(EXCLUSIONS),
    }


def _terminal_threshold_freeze(
    terminal_result: str,
    *,
    rule16_admission: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if terminal_result not in PREHELDOUT_TERMINAL_RESULTS:
        raise ValueError(f"unsupported pre-heldout terminal result: {terminal_result!r}")
    payload = certificate_threshold_freeze(status="NOT_ADMITTED_BY_P2_TERMINAL")
    payload.update({"terminal": True, "terminal_result": terminal_result})
    if rule16_admission is not None:
        _validate_rule16_admission(rule16_admission)
        payload["rule16_admission"] = dict(rule16_admission)
    return payload


def _pilot_required_threshold_freeze(rule16_admission: Mapping[str, Any]) -> dict[str, Any]:
    _validate_rule16_admission(rule16_admission)
    return {
        "schema": THRESHOLD_SCHEMA,
        "status": PILOT_REQUIRED_STATUS,
        "pilot_required": True,
        "terminal": False,
        "terminal_result": None,
        "pilot_registration_id": PILOT_REGISTRATION_ID,
        "gradient_admission": dict(GRADIENT_ADMISSION),
        "rule16_admission": dict(rule16_admission),
        "window_control_steps": 25,
        "stable_grasp_steps": 20,
        "denominator_min": 8,
        "qualifying_min": 8,
        "candidate_buckets": ["F00", "F05", "F10"],
        "rescue_cap_nm": 25.0,
        "confirmed_e2_share": 0.0,
        "heldout_status": "BLOCKED_PENDING_MARGINAL_E1_PILOT",
    }


def _validate_terminal_heldout_receipt(payload: Mapping[str, Any] | None, *, terminal_result: str) -> bool:
    if terminal_result not in PREHELDOUT_TERMINAL_RESULTS or not isinstance(payload, Mapping):
        return False
    return dict(payload) == {
        "schema": "a2_piper_v24_p2_heldout_receipt_v1",
        "status": "NOT_ADMITTED_BY_P2_TERMINAL",
        "terminal_result": terminal_result,
        "heldout_status": "NOT_ADMITTED_BY_P2_TERMINAL",
        "rows": 0,
        "seed": 24022,
        "mode_caps_nm": None,
    }


def _preheldout_terminal_result(calibration: Sequence[Mapping[str, Any]], ladder: Mapping[str, Any]) -> str | None:
    # r12 deliberately does not convert a pre-pilot measurement shortfall into
    # a terminal result.  The owner-directed one-shot F3 pilot is the required
    # next measurement; only post-pilot adjudication may emit a typed terminal.
    return None


def validate_overlay(payload: Mapping[str, Any], *, source_path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    if Path(source_path).resolve() != CONFIG_PATH.resolve():
        raise ValueError("P2 runtime accepts only the canonical base_v24_p2_force_boundary.yaml overlay")
    p2 = payload.get("v24_p2")
    _require(isinstance(p2, Mapping), "overlay must define v24_p2")
    _require(payload.get("v24_schema") == "a2_piper_v24_p2_force_boundary_v1", "overlay schema mismatch")
    _require(payload.get("v24_plan_id") == "base_v24_force_boundary_R12", "overlay plan id must be the r12 candidate")
    _require(payload.get("v24_pilot_registration_id") == PILOT_REGISTRATION_ID, "overlay pilot registration id mismatch")
    _require(payload.get("v24_pilot_status_before_run") == PILOT_REQUIRED_STATUS, "overlay must gate pre-pilot execution")
    _require(payload.get("v24_gradient_admission_status") == GRADIENT_ADMISSION["status"], "overlay gradient-admission status mismatch")
    _require(p2.get("checkpoint") == CHECKPOINT, "overlay checkpoint mismatch")
    _require(p2.get("checkpoint_load_mode") == "selected_policy_only", "overlay load mode mismatch")
    _require(p2.get("calibration_seed") == 24021 and p2.get("heldout_seed") == 24022, "overlay seeds mismatch")
    _require(p2.get("envs_per_run") == 48 and p2.get("envs_per_profile") == 16, "overlay topology mismatch")
    _require(p2.get("control_steps_max") == 1000 and p2.get("dt_s") == 0.005 and p2.get("control_decimation") == 4, "overlay control contract mismatch")
    geometry = p2.get("geometry")
    _require(isinstance(geometry, Mapping), "overlay geometry is missing")
    for key, expected in (("panel_mass_kg", 120.0), ("panel_width_m", 0.95), ("panel_height_m", 2.05), ("handle_height_m", 0.975), ("handle_width_m", 0.12)):
        _require(geometry.get(key) == expected, f"overlay geometry {key} mismatch")
    _require(geometry.get("opening_lr") == "right" and geometry.get("opening_io") == "out", "overlay opening semantics mismatch")
    _require(tuple(geometry.get("hinge_axis_local", ())) == (0.0, 0.0, 1.0), "overlay hinge axis mismatch")
    _require(p2.get("arm_caps_nm") == list(PRIMARY_CAPS_NM), "overlay primary cap ladder mismatch")
    _require(p2.get("contingency_cap_nm") == CONTINGENCY_CAP_NM, "overlay contingency cap mismatch")
    _require(p2.get("paired_scenarios") == 16, "overlay paired scenario count mismatch")
    _require(tuple(p2.get("runtime_modes", ())) == RUNTIME_MODES, "overlay runtime modes mismatch")
    _require(tuple(p2.get("exclusions", ())) == EXCLUSIONS, "overlay exclusions mismatch")
    artifacts = p2.get("artifacts")
    _require(isinstance(artifacts, Mapping), "overlay artifact map is missing")
    _require(artifacts.get("root") == ARTIFACT_ROOT and artifacts.get("append_only") is True, "overlay artifact root/append-only contract mismatch")
    _require(tuple(artifacts.get("files", ())) == REGISTERED_ARTIFACTS, "overlay artifact file map mismatch")
    profiles = p2.get("friction_profiles")
    _require(profiles == FRICTION_PROFILES, "overlay friction profile set mismatch")
    door_model = p2.get("door_model")
    _require(isinstance(door_model, Mapping), "overlay door model is missing")
    _require(door_model.get("inertia_kg_m2") == 36.1 and door_model.get("damping_nm_s_per_rad") == 50.0 and door_model.get("stiffness_nm_per_rad") == 6.0, "overlay door model thresholds mismatch")
    _require(door_model.get("solver_applied") is False and door_model.get("friction_authority") == "MODELED_FROM_PARAMS" and door_model.get("required_torque_authority") == "MODELED_FROM_PARAMS", "overlay door authority mismatch")
    authorities = p2.get("authorities")
    _require(authorities == AUTHORITY_SET, "overlay authority set mismatch")
    env_config = payload.get("env", {}).get("config") if isinstance(payload.get("env"), Mapping) else None
    _require(isinstance(env_config, Mapping) and env_config.get("a2_v23_d1_sampler_enabled") is False, "overlay must explicitly disable the legacy v23 D1 sampler for P2")
    _require(isinstance(env_config, Mapping) and env_config.get("a2_v20_R2_evidence_enabled") is False, "overlay must explicitly disable legacy v20 R2 evidence for P2")
    _require(isinstance(env_config, Mapping) and env_config.get("a2_v24_force_boundary_enabled") is True, "overlay must explicitly enable the force-boundary hook")
    _require(env_config.get("a2_v24_force_boundary_mode") == "P2_TELEMETRY", "overlay runtime mode mismatch")
    for key, expected in {
        "a2_v24_force_boundary_checkpoint": CHECKPOINT,
        "a2_v24_force_boundary_checkpoint_load_mode": "selected_policy_only",
        "a2_v24_force_boundary_friction_profile": "F00",
        "a2_v24_force_boundary_runtime_mode": "HI_FULL",
        "a2_v24_force_boundary_seed": 24021,
        "a2_v24_force_boundary_continuity_id": "CALIBRATION",
        "a2_v24_force_boundary_scenario_ids": list(SCENARIO_IDS),
        "a2_v24_force_boundary_runtime_export_path": VITALS_SOURCE,
        "a2_v24_force_boundary_control_period_s": 0.02,
        "a2_v24_force_boundary_velocity_epsilon_rad_s": 0.001,
    }.items():
        _require(env_config.get(key) == expected, f"overlay env config {key} mismatch")
    for key, expected in {
        "a2_v24_force_boundary_static_friction_nm": 0.0,
        "a2_v24_force_boundary_dynamic_friction_nm": 0.0,
        "a2_v24_force_boundary_viscous_friction_nm_s_per_rad": 0.0,
    }.items():
        _require(env_config.get(key) == expected, f"overlay env config {key} mismatch")
    return {"config": rel_path(CONFIG_PATH), "schema": payload["v24_schema"], "validated": True}


def _row_is_usable(row: Mapping[str, Any], *, require_slip: bool = True) -> bool:
    if row.get("valid") is not True or row.get("source_unavailable") is not None:
        return False
    if any(row.get(field) is not False for field in ("grasp_source_unavailable", "model_source_unavailable")):
        return False
    if row.get("stable_grasp") is not True or row.get("window_selection_valid") is not True or row.get("excluded"):
        return False
    if require_slip and row.get("foot_slip_valid") is not True:
        return False
    return True


def _immediate_higher_cap(cap_nm: float) -> float | None:
    cap = _finite(cap_nm, label="cap_nm")
    if cap not in CAP_ORDER_DESCENDING_NM:
        raise ValueError(f"cap {cap} is not registered")
    index = CAP_ORDER_DESCENDING_NM.index(cap)
    return CAP_ORDER_DESCENDING_NM[index - 1] if index > 0 else None


def _paired_progress_gain(
    rows: Sequence[Mapping[str, Any]],
    row: Mapping[str, Any],
) -> float | None:
    cap = _finite(row.get("cap_nm"), label="cap_nm")
    higher = _immediate_higher_cap(cap)
    if higher is None:
        return None
    key = (row.get("profile"), row.get("scenario_id"))
    matches = [
        candidate
        for candidate in rows
        if candidate.get("profile") == key[0]
        and candidate.get("scenario_id") == key[1]
        and _finite(candidate.get("cap_nm"), label="cap_nm") == higher
    ]
    if len(matches) != 1:
        return None
    if not _row_is_usable(row) or not _row_is_usable(matches[0]):
        return None
    return _finite(matches[0].get("progress_recovery_delta_rad"), label="progress_recovery_delta_rad") - _finite(row.get("progress_recovery_delta_rad"), label="progress_recovery_delta_rad")


def qualifies_boundary_cap(rows: Sequence[Mapping[str, Any]], cap_nm: float) -> bool:
    """Apply the preregistered matched F05/F10 adjacent-cap progress rule."""
    cap = _finite(cap_nm, label="cap_nm")
    if cap not in REGISTERED_CAPS_NM:
        return False
    selected = [row for row in rows if _finite(row.get("cap_nm"), label="cap_nm") == cap]
    if len(selected) != 48:
        return False
    if _immediate_higher_cap(cap) is None:
        return False
    by_profile: dict[str, list[Mapping[str, Any]]] = {name: [] for name in FRICTION_PROFILES}
    for row in selected:
        profile = row.get("profile")
        if profile not in by_profile or row.get("scenario_id") not in SCENARIO_IDS:
            return False
        by_profile[profile].append(row)
    if any(len(by_profile[name]) != 16 for name in FRICTION_PROFILES):
        return False
    for name in ("F05", "F10"):
        usable = [row for row in by_profile[name] if _row_is_usable(row)]
        if len(usable) < 8 or any(row.get("directional_high_effort") is not True for row in usable):
            return False
        gains = [_paired_progress_gain(rows, row) for row in usable]
        gains = [gain for gain in gains if gain is not None]
        if len(gains) < 8 or median(gains) < 0.02:
            return False
    usable_by_profile = {name: [row for row in by_profile[name] if _row_is_usable(row)] for name in FRICTION_PROFILES}
    if any(len(values) == 0 for values in usable_by_profile.values()):
        return False
    medians = {name: median(float(row["tau_req_median_nm"]) for row in usable_by_profile[name]) for name in FRICTION_PROFILES}
    lambdas = {name: median(float(row["lambda_median"]) for row in usable_by_profile[name]) for name in FRICTION_PROFILES}
    return medians["F00"] < medians["F05"] < medians["F10"] and lambdas["F00"] <= lambdas["F05"] <= lambdas["F10"]


def select_boundary_cap(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Select one common boundary and its immediately higher rescue cap."""
    return _derive_ladder(rows, status="DERIVED")


def classify_e_region(metrics: Mapping[str, Any]) -> str:
    """Classify a force window after typed exclusions have been checked."""

    for exclusion in EXCLUSIONS:
        if metrics.get(f"excluded_{exclusion.lower()}") is True:
            return exclusion
    if metrics.get("source_unavailable") == "SOURCE_UNAVAILABLE" or any(metrics.get(field) is True for field in ("grasp_source_unavailable", "model_source_unavailable")):
        return "SOURCE_UNAVAILABLE"
    required_keys = ("valid", "stable_grasp", "lambda", "progress_recovery_delta_rad", "rescue_progress_rad", "rescue_gain_rad")
    if any(key not in metrics for key in required_keys):
        return "SOURCE_UNAVAILABLE"
    if metrics.get("valid") is not True or metrics.get("stable_grasp") is not True:
        return "PATHOLOGY"
    lam = _finite(metrics.get("lambda"), label="lambda")
    if lam < 0.5:
        return "E0"
    if lam < 1.0:
        return "E1"
    if metrics.get("heldout") is True and metrics.get("e2_confirmed") is True:
        rescue_progress = _finite(metrics.get("rescue_progress_rad"), label="rescue_progress_rad")
        rescue_gain = _finite(metrics.get("rescue_gain_rad"), label="rescue_gain_rad")
        low_progress = _finite(metrics.get("progress_recovery_delta_rad"), label="progress_recovery_delta_rad") <= 0.04
        confirmed = (
            low_progress
            and metrics.get("directional_high_effort") is True
            and rescue_progress >= 0.10
            and rescue_gain >= 0.02
            and not any(metrics.get(f"excluded_{name.lower()}") is True for name in EXCLUSIONS)
        )
        if confirmed:
            return "E2"
    return "NEAR_E2"


def _calibration_e1_scenarios(rows: Sequence[Mapping[str, Any]], boundary_nm: float) -> set[str]:
    higher = _immediate_higher_cap(boundary_nm)
    if higher is None:
        return set()
    matched: set[str] = set()
    for scenario in SCENARIO_IDS:
        for profile in ("F05", "F10"):
            boundary_rows = [
                row for row in rows
                if row.get("profile") == profile
                and row.get("scenario_id") == scenario
                and row.get("cap_nm") == boundary_nm
            ]
            higher_rows = [
                row for row in rows
                if row.get("profile") == profile
                and row.get("scenario_id") == scenario
                and row.get("cap_nm") == higher
            ]
            if len(boundary_rows) != 1 or len(higher_rows) != 1:
                continue
            boundary = boundary_rows[0]
            gain = _paired_progress_gain(rows, boundary)
            if (
                _row_is_usable(boundary)
                and gain is not None
                and gain >= 0.02
                and 0.5 <= _finite(boundary.get("lambda_median"), label="lambda_median") < 1.0
            ):
                matched.add(scenario)
                break
    return matched


def _calibration_e0_anchor_scenarios(rows: Sequence[Mapping[str, Any]], tau_hi_nm: float) -> set[str]:
    return {
        scenario
        for scenario in SCENARIO_IDS
        if any(
            row.get("profile") == "F00"
            and row.get("scenario_id") == scenario
            and row.get("cap_nm") == tau_hi_nm
            and _row_is_usable(row)
            and _finite(row.get("lambda_median"), label="lambda_median") < 0.5
            for row in rows
        )
    }


def _apply_slip_exclusion(rows: Sequence[Mapping[str, Any]], q99_m_s: float) -> list[dict[str, Any]]:
    threshold = _finite(q99_m_s, label="foot_slip_q99_m_s")
    updated: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if item.get("foot_slip_valid") is True:
            slip = _finite(item.get("max_loaded_foot_slip_m_s"), label="max_loaded_foot_slip_m_s")
            item["excluded_slip"] = slip > threshold
        else:
            raise ValueError("heldout foot-slip measurement is invalid")
        updated.append(item)
    return updated


def _derive_heldout_pairs(
    rows: Sequence[Mapping[str, Any]],
    *,
    mode_caps: Mapping[str, float],
) -> tuple[list[dict[str, Any]], bool]:
    expected_modes = set(RUNTIME_MODES)
    if set(mode_caps) != expected_modes:
        raise ValueError("heldout mode-cap map must define all runtime treatments")
    by_key = {
        (row["profile"], row["scenario_id"], row["mode"]): row
        for row in rows
    }
    joined: list[dict[str, Any]] = []
    complete = True
    for profile in FRICTION_PROFILES:
        for scenario in SCENARIO_IDS:
            cells = {
                mode: by_key.get((profile, scenario, mode))
                for mode in RUNTIME_MODES
            }
            if any(cell is None for cell in cells.values()):
                complete = False
                continue
            if any(cell["cap_nm"] != float(mode_caps[mode]) for mode, cell in cells.items()):
                raise ValueError("heldout row cap does not match frozen treatment map")
            boundary_full = cells["BOUNDARY_FULL"]
            boundary_rp0 = cells["BOUNDARY_RP0"]
            rescue = cells["RESCUE_FULL"]
            hi_anchor = cells["HI_FULL"]
            hi_anchor_usable = _row_is_usable(hi_anchor)
            boundary_usable = all(
                _row_is_usable(cell)
                and cell["directional_high_effort"] is True
                and _finite(cell["progress_recovery_delta_rad"], label="progress_recovery_delta_rad") <= 0.04
                for cell in (boundary_full, boundary_rp0)
            )
            rescue_usable = _row_is_usable(rescue)
            rescue_progress = _finite(rescue["progress_recovery_delta_rad"], label="progress_recovery_delta_rad") if rescue_usable else None
            boundary_progress = _finite(boundary_full["progress_recovery_delta_rad"], label="progress_recovery_delta_rad")
            rescue_gain = rescue_progress - boundary_progress if rescue_progress is not None else None
            e2_confirmed = bool(hi_anchor_usable and boundary_usable and rescue_progress is not None and rescue_progress >= 0.10 and rescue_gain is not None and rescue_gain >= 0.02)
            joined.append(
                {
                    "profile": profile,
                    "scenario_id": scenario,
                    "mode": "BOUNDARY_FULL",
                    "cap_nm": float(mode_caps["BOUNDARY_FULL"]),
                    "boundary_full": boundary_full,
                    "boundary_rp0": boundary_rp0,
                    "rescue": rescue,
                    "rescue_progress_rad": rescue_progress,
                    "rescue_gain_rad": rescue_gain,
                    "e2_confirmed": e2_confirmed,
                }
            )
    return joined, complete


def _validate_parameter_range_payload(payload: Mapping[str, Any], *, require_executed: bool) -> bool:
    if not isinstance(payload, Mapping) or payload.get("schema") != PARAMETER_RANGE_SCHEMA:
        return False
    if require_executed and payload.get("status") != "EXECUTED":
        return False
    return (
        payload.get("checkpoint") == CHECKPOINT
        and payload.get("checkpoint_load_mode") == "selected_policy_only"
        and payload.get("calibration_seed") == 24021
        and payload.get("heldout_seed") == 24022
        and payload.get("topology", {}).get("envs_per_run") == 48
        and payload.get("topology", {}).get("envs_per_profile") == 16
        and payload.get("topology", {}).get("paired_scenarios") == 16
        and payload.get("control", {}).get("max_control_steps") == 1000
        and payload.get("arm_caps_nm") == list(PRIMARY_CAPS_NM)
        and payload.get("contingency_cap_nm") == CONTINGENCY_CAP_NM
        and payload.get("authorities") == AUTHORITY_SET
    )


def _validate_ladder_payload(payload: Mapping[str, Any], *, require_executed: bool) -> bool:
    if not isinstance(payload, Mapping) or payload.get("schema") != LADDER_SCHEMA:
        return False
    if require_executed and payload.get("status") != "EXECUTED":
        return False
    tau_hi = payload.get("tau_hi_nm")
    boundary = payload.get("tau_boundary_nm")
    rescue = payload.get("tau_rescue_nm")
    if tau_hi is not None and tau_hi not in PRIMARY_CAPS_NM:
        return False
    if boundary is not None and boundary not in REGISTERED_CAPS_NM:
        return False
    if boundary is None:
        if rescue is not None:
            return False
    elif rescue != _immediate_higher_cap(boundary):
        return False
    if payload.get("registered_primary_caps_nm") != list(PRIMARY_CAPS_NM) or payload.get("registered_contingency_cap_nm") != CONTINGENCY_CAP_NM:
        return False
    if require_executed:
        try:
            _validate_rule16_admission(payload.get("rule16_admission"))
        except (TypeError, ValueError):
            return False
    return True


def _validate_threshold_payload(payload: Mapping[str, Any], *, require_executed: bool) -> bool:
    if not isinstance(payload, Mapping) or payload.get("schema") != THRESHOLD_SCHEMA:
        return False
    if payload.get("status") == "NOT_ADMITTED_BY_P2_TERMINAL":
        if payload.get("terminal") is not True or payload.get("terminal_result") not in PREHELDOUT_TERMINAL_RESULTS:
            return False
        if "foot_slip_q99_m_s" in payload or "tau_hi_nm" in payload:
            return False
        expected = _terminal_threshold_freeze(str(payload["terminal_result"]), rule16_admission=payload.get("rule16_admission"))
        if payload.get("rule16_admission") is not None:
            try:
                _validate_rule16_admission(payload["rule16_admission"])
            except (TypeError, ValueError):
                return False
        return dict(payload) == expected
    if payload.get("status") == PILOT_REQUIRED_STATUS:
        if payload.get("terminal") is not False or payload.get("pilot_required") is not True:
            return False
        if payload.get("pilot_registration_id") != PILOT_REGISTRATION_ID:
            return False
        if payload.get("gradient_admission") != GRADIENT_ADMISSION:
            return False
        try:
            _validate_rule16_admission(payload.get("rule16_admission"))
        except (TypeError, ValueError):
            return False
        return (
            payload.get("window_control_steps") == 25
            and payload.get("stable_grasp_steps") == 20
            and payload.get("denominator_min") == 8
            and payload.get("qualifying_min") == 8
            and payload.get("candidate_buckets") == ["F00", "F05", "F10"]
            and payload.get("rescue_cap_nm") == 25.0
            and payload.get("confirmed_e2_share") == 0.0
            and payload.get("heldout_status") == "BLOCKED_PENDING_MARGINAL_E1_PILOT"
        )
    if payload.get("status") != "EXECUTED":
        return False
    if "terminal" in payload or "terminal_result" in payload:
        return False
    try:
        q99 = _finite(payload.get("foot_slip_q99_m_s"), label="foot_slip_q99_m_s")
        tau_hi = _finite(payload.get("tau_hi_nm"), label="tau_hi_nm")
    except (TypeError, ValueError):
        return False
    if require_executed:
        try:
            _validate_rule16_admission(payload.get("rule16_admission"))
        except (TypeError, ValueError):
            return False
    return (
        tau_hi in PRIMARY_CAPS_NM
        and payload.get("window_control_steps") == 25
        and payload.get("denominator_min") == 8
        and payload.get("qualifying_min") == 8
        and payload.get("foot_slip_valid_windows", 0) >= 8
        and q99 >= 0.0
    )


def _authority_source_gate(rows: Sequence[Mapping[str, Any]]) -> bool:
    if not rows:
        return False
    for row in rows:
        if row.get("authority") != RUNTIME_AUTHORITY_SET:
            return False
        if row.get("source_unavailable") is not None or row.get("foot_slip_valid") is not True:
            return False
        if any(row.get(field) is not False for field in ("grasp_source_unavailable", "model_source_unavailable")):
            return False
        if row.get("stable_grasp") is not True or row.get("grasp_source_unavailable") is not False:
            return False
        if row.get("window_selection_valid") is not True or row.get("excluded_window_selection") is not False:
            return False
    return True


def _require_completed_smoke_receipt(payload: Mapping[str, Any]) -> None:
    if (
        payload.get("status") != "EXECUTED"
        or payload.get("evidentiary") is not False
        or payload.get("rows") != 9
        or payload.get("envs") != 3
        or payload.get("profiles") != ["F00", "F05", "F10"]
        or payload.get("modes") != ["HI_FULL"]
        or payload.get("control_steps") != 64
    ):
        raise RuntimeError("P2 calibration requires a completed non-evidentiary smoke receipt")


def adjudicate_p2(
    *,
    calibration_rows: Sequence[Mapping[str, Any]],
    heldout_rows: Sequence[Mapping[str, Any]] | None,
    parameter_range_valid: bool,
    ladder_valid: bool,
    threshold_valid: bool,
    authority_gates_pass: bool,
    authority_set: Mapping[str, Any] | None = None,
    heldout_mode_caps: Mapping[str, float] | None = None,
    parameter_range_payload: Mapping[str, Any] | None = None,
    ladder_payload: Mapping[str, Any] | None = None,
    threshold_payload: Mapping[str, Any] | None = None,
    vitals_receipt: Mapping[str, Any] | None = None,
    pilot_adjudication: Mapping[str, Any] | None = None,
    require_vitals_source_files: bool = True,
) -> dict[str, Any]:
    """Recompute P2/E1/E2 from immutable raw rows and typed source gates."""

    _require(parameter_range_payload is not None and _validate_parameter_range_payload(parameter_range_payload, require_executed=True), "P2 parameter freeze artifact is invalid")
    _require(ladder_payload is not None and _validate_ladder_payload(ladder_payload, require_executed=True), "P2 ladder freeze artifact is invalid")
    _require(threshold_payload is not None and _validate_threshold_payload(threshold_payload, require_executed=True), "P2 threshold freeze artifact is invalid")
    _require(vitals_receipt is not None, "P2 Rule16 vitals receipt is required for adjudication")
    _require_completed_vital_receipt(vitals_receipt, require_source_files=require_vitals_source_files)
    _require(parameter_range_valid and ladder_valid and threshold_valid, "P2 freeze gates are incomplete")
    _require(authority_set is not None and dict(authority_set) == AUTHORITY_SET, "P2 authority set is missing or mutated")
    calibration_has_contingency = any(isinstance(row, Mapping) and row.get("cap_nm") == CONTINGENCY_CAP_NM for row in calibration_rows)
    calibration = _validate_raw_rows(calibration_rows, kind="calibration_with_contingency" if calibration_has_contingency else "calibration")
    ladder = select_boundary_cap(calibration)
    if ladder_payload.get("rule16_admission") != vitals_receipt.get("rule16_admission"):
        raise ValueError("P2 ladder artifact does not carry the completed Rule16 admission")
    if threshold_payload.get("rule16_admission") != vitals_receipt.get("rule16_admission"):
        raise ValueError("P2 threshold artifact does not carry the completed Rule16 admission")
    if threshold_payload.get("status") == PILOT_REQUIRED_STATUS:
        raise ValueError("P2 marginal-E1 pilot is required before final adjudication")
    for key in ("tau_hi_nm", "tau_boundary_nm", "tau_rescue_nm", "command_path_binding", "contingency_result"):
        if ladder_payload.get(key) != ladder.get(key):
            raise ValueError(f"P2 ladder artifact disagrees with raw calibration for {key}")
    terminal_result = _preheldout_terminal_result(calibration, ladder)
    terminal_threshold = threshold_payload.get("status") == "NOT_ADMITTED_BY_P2_TERMINAL"
    if terminal_threshold:
        if terminal_result is None or threshold_payload.get("terminal_result") != terminal_result:
            raise ValueError("P2 terminal threshold artifact disagrees with raw calibration/ladder")
    elif terminal_result is not None:
        raise ValueError("P2 regular threshold artifact is invalid for a preregistered calibration terminal")
    boundary = ladder.get("tau_boundary_nm")
    tau_hi = ladder.get("tau_hi_nm")
    anchor = _calibration_e0_anchor_scenarios(calibration, float(tau_hi)) if tau_hi is not None else set()
    matched = _calibration_e1_scenarios(calibration, float(boundary)) if boundary is not None else set()
    denominator_sufficient = len(matched) >= 8
    anchor_sufficient = len(anchor) >= 8
    if not denominator_sufficient:
        if not isinstance(pilot_adjudication, Mapping) or pilot_adjudication.get("schema") != "a2_piper_v24_r12_f3_marginal_e1_adjudication_v1" or pilot_adjudication.get("status") not in {"PILOT_COMPLETE_VALID", "V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3"}:
            raise ValueError("P2 denominator insufficiency is admissible only after the registered marginal-E1 pilot")
    sensitivity = boundary is not None and qualifies_boundary_cap(calibration, float(boundary))
    e1_established = anchor_sufficient and denominator_sufficient and sensitivity
    command_path_binding = bool(ladder.get("command_path_binding"))
    preheldout_terminal = terminal_result is not None
    supplied_heldout = bool(heldout_rows)
    if supplied_heldout and preheldout_terminal:
        raise ValueError("P2 heldout evidence is not admitted after a preregistered calibration terminal")
    if not supplied_heldout and not preheldout_terminal:
        raise ValueError("P2 heldout evidence is required after a successful calibration/freeze path")
    heldout: list[dict[str, Any]] = []
    if supplied_heldout:
        if heldout_mode_caps is None:
            raise ValueError("heldout mode-cap treatment map is required")
        heldout = _validate_raw_rows(heldout_rows or [], kind="heldout", heldout_mode_caps=heldout_mode_caps)
        heldout = _apply_slip_exclusion(heldout, float(threshold_payload["foot_slip_q99_m_s"]))
        heldout = _validate_raw_rows(heldout, kind="heldout", heldout_mode_caps=heldout_mode_caps)
    calibration_authority_gate = bool(authority_gates_pass) and _authority_source_gate(calibration)
    heldout_source_gate = _authority_source_gate(heldout) if supplied_heldout else None
    authority_gate = calibration_authority_gate and (heldout_source_gate if supplied_heldout else True)
    pairs: list[dict[str, Any]] = []
    pairing_complete = False
    if supplied_heldout:
        pairs, pairing_complete = _derive_heldout_pairs(heldout, mode_caps=heldout_mode_caps)
    e2_count = sum(1 for pair in pairs if pair["e2_confirmed"])
    results: list[str] = []
    if not command_path_binding:
        results.append("V24_ARM_COMMAND_PATH_NOT_BINDING")
    if not anchor_sufficient or not denominator_sufficient:
        results.append("V24_E1_DENOMINATOR_INSUFFICIENT")
    elif not sensitivity:
        results.append("V24_DOOR_MODEL_REMAINS_INSUFFICIENT")
    else:
        results.append("V24_E1_BOUNDARY_ESTABLISHED")
        if supplied_heldout:
            e2_established = pairing_complete and authority_gate and e2_count >= 8
            results.append("V24_E2_BOUNDARY_ESTABLISHED" if e2_established else "V24_E2_BOUNDARY_NOT_ESTABLISHED")
    if not results:
        results.append("V24_E1_DENOMINATOR_INSUFFICIENT")
    p3_admitted = bool(e1_established and command_path_binding and supplied_heldout and authority_gate and pairing_complete)
    return {
        "schema": FINAL_SCHEMA,
        "typed_results": results,
        "allowed_typed_results": list(TYPED_RESULTS),
        "e1_denominator_count": len(matched),
        "e1_denominator_sufficient": denominator_sufficient,
        "e0_anchor_count": len(anchor),
        "e0_anchor_sufficient": anchor_sufficient,
        "e1_established": e1_established,
        "command_path_binding": command_path_binding,
        "authority_gates_pass": authority_gate,
        "source_gates_pass": authority_gate,
        "heldout_source_gates_pass": heldout_source_gate,
        "heldout_pairing_complete": pairing_complete,
        "e2_confirmed_count": e2_count,
        "p3_admitted": p3_admitted,
        "terminal": preheldout_terminal,
        "heldout_status": "EXECUTED" if supplied_heldout else "NOT_ADMITTED_BY_P2_TERMINAL",
        "heldout_required": not preheldout_terminal,
        "raw_recomputation": True,
        "owner_decision_required": False,
        "rule16_admission": dict(vitals_receipt["rule16_admission"]),
        "owner_decision_artifact": dict(vitals_receipt["owner_decision_artifact"]),
        "vitals_receipt_artifact": _receipt_reference(VITAL_ARTIFACTS[2]),
        "pilot_adjudication": dict(pilot_adjudication) if pilot_adjudication is not None else None,
    }


def build_plan(config_path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    target = absolute(config_path)
    payload = _read_overlay(target)
    return {
        "schema": PLAN_SCHEMA,
        "status": "PLAN_ONLY_NO_RUNTIME_NO_ARTIFACT",
        "overlay": validate_overlay(payload, source_path=target),
        "parameter_range_freeze": parameter_range_freeze(),
        "ladder_freeze": ladder_freeze(),
        "certificate_threshold_freeze": certificate_threshold_freeze(),
        "runtime": {
            "modes": list(RUNTIME_MODES),
            "exclusions": list(EXCLUSIONS),
            "evaluator": {
                "module": "gr00t.rl.eval_agent_trl",
                "checkpoint": CHECKPOINT,
                "checkpoint_load_mode": "policy_only",
                "algo.config.eval.a2_v23_p06_policy_only": True,
                "overlay_composition": "++env.config.<a2_v24_force_boundary_*>",
                "runtime_fields": [
                    "enabled",
                    "mode",
                    "checkpoint",
                    "checkpoint_load_mode",
                    "friction_profile",
                    "runtime_mode",
                    "seed",
                    "scenario_ids",
                    "continuity_id",
                    "active_cap_nm",
                    "runtime_export_path",
                    "panel_mass_kg",
                    "panel_width_m",
                    "panel_height_m",
                    "handle_height_m",
                    "handle_width_m",
                    "opening_lr",
                    "opening_io",
                    "hinge_axis_local",
                    "theta_ref_rad",
                    "inertia_kg_m2",
                    "damping_nm_s_per_rad",
                    "stiffness_nm_per_rad",
                    "static_friction_nm",
                    "dynamic_friction_nm",
                    "viscous_friction_nm_s_per_rad",
                    "primary_caps_nm",
                    "contingency_cap_nm",
                    "epsilon_g_m",
                    "control_period_s",
                    "velocity_epsilon_rad_s",
                ],
                "posture_intervention": {
                    "HI_FULL": "none",
                    "BOUNDARY_FULL": "none",
                    "BOUNDARY_RP0": "rp0_distribution_mask_indices_3_4",
                    "RESCUE_FULL": "none",
                },
            },
            "directional_formulas": {
                "handle_jacobian": "J_handle,v = J_body,v - [r_bh]_x J_body,w",
                "floating_base_columns": "+6 exactly once",
                "capacity": "g=J_handle,v^T t_hat; Fmax=min_i(m_i/|g_i|); tau_avail=r_handle*Fmax",
                "load_margin": "m_i=L_i-sign(g_i)*b_i; b_i=tau_gravity+Kp(q_target-q)-Kd*qdot",
                "lambda": "tau_req/(tau_avail+1e-6 Nm)",
            },
            "articulation_api": [
                "Articulation.root_physx_view.get_jacobians()",
                "Articulation.root_physx_view.get_gravity_compensation_forces()",
                "Articulation.data.joint_effort_limits",
                "Articulation.data.body_com_pos_w/body_lin_vel_w",
            ],
            "actual_generalized_torque": "UNAVAILABLE_NOT_USED",
            "window_contract": {
                "selection": WINDOW_SELECTION_ADMITTED,
                "fallback": WINDOW_SELECTION_FALLBACK,
                "fallback_admission": "non-admissible; WINDOW_SELECTION exclusion",
                "transitions": 25,
                "progress": "sum(theta_delta_rad) across all 25 transitions",
                "stable_grasp_threshold": "20_of_25",
                "post_window_samples": "ignored_for_first_episode_evidence",
            },
            "terminal_outcomes": [
                "V24_ARM_COMMAND_PATH_NOT_BINDING",
                "V24_DOOR_MODEL_REMAINS_INSUFFICIENT",
            ],
            "pre_pilot_gate": PILOT_REQUIRED_STATUS,
            "post_pilot_terminal_outcomes": ["V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3"],
        },
        "artifacts": artifact_plan(),
        "typed_results": list(TYPED_RESULTS),
    }


def _artifact_root(path: str | Path) -> Path:
    target = Path(path).resolve()
    expected = (REPO_ROOT / ARTIFACT_ROOT).resolve()
    if target != expected:
        raise ValueError(f"P2 runtime artifacts must use the canonical root {rel_path(expected)}")
    return target


def _artifact_path(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError("artifact path escaped canonical P2 root")
    return target


def _write_json(root: Path, relative: str, payload: Mapping[str, Any]) -> Path:
    target = _artifact_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"P2 artifact is append-only and already exists: {target}") from exc
    return target


def _write_jsonl(root: Path, relative: str, rows: Sequence[Mapping[str, Any]]) -> Path:
    target = _artifact_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"P2 artifact is append-only and already exists: {target}") from exc
    return target


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    target = _artifact_path(root, relative)
    if not target.is_file():
        raise RuntimeError(f"P2 stage prerequisite is missing: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"P2 artifact {target} must contain a mapping")
    return payload


def _read_jsonl(root: Path, relative: str) -> list[dict[str, Any]]:
    target = _artifact_path(root, relative)
    if not target.is_file():
        raise RuntimeError(f"P2 stage prerequisite is missing: {target}")
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"P2 raw artifact {target} contains a non-mapping row")
    return rows


def _policy_only_eval_command(
    *,
    config_path: Path,
    device: str,
    output_dir: Path,
    seed: int,
    profile: str,
    cap_nm: float,
    mode: str,
    num_envs: int = 16,
    scenario_ids: Sequence[str] | None = None,
    continuity_id: str = "HELDOUT",
    control_steps: int | None = None,
) -> tuple[list[str], dict[str, str]]:
    checkpoint = require_file(REPO_ROOT / CHECKPOINT, label="v24 P2 selected checkpoint")
    overlay = _read_overlay(config_path)
    overlay_env = overlay.get("env", {}).get("config") if isinstance(overlay.get("env"), Mapping) else None
    if not isinstance(overlay_env, Mapping):
        raise ValueError("v24 P2 canonical overlay must contain env.config")
    if profile not in FRICTION_PROFILES:
        raise ValueError(f"unknown P2 friction profile {profile!r}")
    if mode not in RUNTIME_MODES:
        raise ValueError(f"unknown P2 runtime mode {mode!r}")
    cap = _finite(cap_nm, label="cap_nm")
    if cap not in REGISTERED_CAPS_NM:
        raise ValueError("P2 command cap is not registered")
    if isinstance(num_envs, bool) or not isinstance(num_envs, int) or num_envs <= 0:
        raise ValueError("P2 command num_envs must be a positive integer")
    scenarios = tuple(scenario_ids or SCENARIO_IDS[:num_envs])
    if len(scenarios) != num_envs or any(not isinstance(item, str) or not item for item in scenarios):
        raise ValueError("P2 command scenario_ids must exactly match num_envs")
    if not isinstance(continuity_id, str) or not continuity_id:
        raise ValueError("P2 command continuity_id must be non-empty")
    if control_steps is not None and (
        isinstance(control_steps, bool) or not isinstance(control_steps, int) or control_steps <= 0
    ):
        raise ValueError("P2 command control_steps must be a positive integer when supplied")

    def hydra_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return "[" + ",".join(hydra_value(item) for item in value) + "]"
        return str(value)

    profile_params = FRICTION_PROFILES[profile]
    runtime_env = {
        key: value
        for key, value in overlay_env.items()
        if key.startswith("a2_v24_force_boundary_")
    }
    runtime_env.update(
        {
            "a2_v23_d1_sampler_enabled": False,
            "a2_v20_R2_evidence_enabled": False,
            "a2_v24_force_boundary_enabled": True,
            "a2_v24_force_boundary_mode": "P2_TELEMETRY",
            "a2_v24_force_boundary_friction_profile": profile,
            "a2_v24_force_boundary_runtime_mode": mode,
            "a2_v24_force_boundary_seed": seed,
            "a2_v24_force_boundary_scenario_ids": list(scenarios),
            "a2_v24_force_boundary_continuity_id": continuity_id,
            "a2_v24_force_boundary_active_cap_nm": cap,
            "a2_v24_force_boundary_static_friction_nm": profile_params["static_effort_nm"],
            "a2_v24_force_boundary_dynamic_friction_nm": profile_params["dynamic_effort_nm"],
            "a2_v24_force_boundary_viscous_friction_nm_s_per_rad": profile_params["viscous_coefficient_nm_s_per_rad"],
            "a2_v24_force_boundary_runtime_export_path": str(output_dir / "P2_RUNTIME_ROWS.jsonl"),
        }
    )
    command = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++headless=true",
        f"++num_envs={num_envs}",
        f"++seed={seed}",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++algo.config.eval.a2_v23_p06_policy_only=true",
        "++algo.config.eval.eval_num_envs_episodes=true",
        f"++algo.config.eval.num_eval_episodes={num_envs}",
        f"++algo.config.eval.a2_eval_p2_posture_axis={'rp0' if mode == 'BOUNDARY_RP0' else 'none'}",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        "++env.config.a2_base.enabled=true",
        "++algo.config.num_mini_batches=1",
        f"++eval_output_dir={output_dir}",
    ]
    # Compose the canonical P2 overlay into the evaluator's resolved config.
    # The runtime must consume these keys; passing an unused YAML path would not
    # bind the treatment to the instantiated environment.
    command.extend(
        f"++env.config.{key}={hydra_value(value)}"
        for key, value in sorted(runtime_env.items())
    )
    command.extend(
        [
            "++v24_schema=a2_piper_v24_p2_force_boundary_v1",
            "++v24_plan_id=base_v24_force_boundary_R12",
            "++v24_runtime_mode=P2_TELEMETRY",
            f"++v24_checkpoint_provenance={checkpoint}",
            "++v24_checkpoint_load_mode=selected_policy_only",
            f"++v24_p2.checkpoint={checkpoint}",
            "++v24_p2.checkpoint_load_mode=selected_policy_only",
            f"++v24_p2.calibration_seed=24021",
            f"++v24_p2.heldout_seed=24022",
            "++v24_p2.runtime_modes=[HI_FULL,BOUNDARY_FULL,BOUNDARY_RP0,RESCUE_FULL]",
        ]
    )
    if control_steps is not None:
        command.append(f"++env.config.max_episode_length_s={control_steps * CONTROL_PERIOD_S:g}")
    env = dict(os.environ)
    env.update({"PYTHONPATH": str(REPO_ROOT), "WANDB_MODE": "disabled", "ACCELERATE_TORCH_DEVICE": device})
    if device.startswith("cuda:"):
        env["CUDA_VISIBLE_DEVICES"] = device.split(":", 1)[1]
    return command, env


def _run_policy_only_first_episode(
    *,
    config_path: Path,
    device: str,
    seed: int,
    profile: str,
    cap_nm: float,
    mode: str,
    num_envs: int = 16,
    scenario_ids: Sequence[str] | None = None,
    continuity_id: str = "HELDOUT",
    control_steps: int | None = None,
) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="v24_p2_runtime_", dir=str(REPO_ROOT / ARTIFACT_ROOT)) as temp_dir:
        output_dir = Path(temp_dir)
        command, env = _policy_only_eval_command(
            config_path=config_path,
            device=device,
            output_dir=output_dir,
            seed=seed,
            profile=profile,
            cap_nm=cap_nm,
            mode=mode,
            num_envs=num_envs,
            scenario_ids=scenario_ids,
            continuity_id=continuity_id,
            control_steps=control_steps,
        )
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if completed.returncode != 0:
            output_lines = (completed.stdout or "").splitlines()
            tail = "\n".join(output_lines[-400:]) or "<no evaluator output>"
            raise RuntimeError(
                "P2 policy-only evaluator failed "
                f"(return code {completed.returncode}); trailing evaluator output (up to 400 lines):\n{tail}"
            )
        rows_path = output_dir / "P2_RUNTIME_ROWS.jsonl"
        if not rows_path.is_file():
            raise RuntimeError("policy-only P2 runtime completed without first-episode P2 hook rows")
        rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(rows) != num_envs or any(not isinstance(row, dict) for row in rows):
            raise RuntimeError("policy-only P2 runtime produced no valid first-episode rows")
        expected_scenarios = tuple(scenario_ids or SCENARIO_IDS[:num_envs])
        expected_identity = {
            (seed, profile, float(cap_nm), scenario, mode, continuity_id)
            for scenario in expected_scenarios
        }
        actual_identity = {
            (
                row.get("seed"),
                row.get("profile"),
                row.get("cap_nm"),
                row.get("scenario_id"),
                row.get("mode"),
                row.get("continuity_id"),
            )
            for row in rows
        }
        if actual_identity != expected_identity:
            raise RuntimeError(
                "policy-only P2 runtime identity mismatch; "
                f"missing={sorted(expected_identity - actual_identity)!r} "
                f"extra={sorted(actual_identity - expected_identity)!r}"
            )
        return rows


def run_stage(
    mode: str,
    *,
    config_path: str | Path = CONFIG_PATH,
    artifact_root: str | Path = REPO_ROOT / ARTIFACT_ROOT,
    device: str = "cuda:0",
) -> dict[str, Any]:
    target_config = Path(config_path).resolve()
    payload = _read_overlay(target_config)
    validate_overlay(payload, source_path=target_config)
    root = _artifact_root(artifact_root)
    if mode == "prepare":
        return {"stage": mode, "artifact": str(_write_json(root, STAGE_ARTIFACTS[0], parameter_range_freeze(status="EXECUTED")))}
    parameter = _read_json(root, STAGE_ARTIFACTS[0])
    if not _validate_parameter_range_payload(parameter, require_executed=True):
        raise RuntimeError("P2 parameter-range freeze is not executable/complete")
    if mode == "vitals":
        root.mkdir(parents=True, exist_ok=True)
        source_rows = _run_policy_only_first_episode(
            config_path=target_config,
            device=device,
            seed=0,
            profile="F00",
            cap_nm=40.0,
            mode="HI_FULL",
            num_envs=16,
            scenario_ids=SCENARIO_IDS,
            continuity_id="VITALS_R12_FIXED_SHAM",
            control_steps=1000,
        )
        normalized = _validate_vital_rows(source_rows)
        raw_path = _write_jsonl(root, VITAL_ARTIFACTS[1], source_rows)
        receipt = _build_vital_receipt(normalized)
        rows_path = _write_jsonl(root, VITAL_ARTIFACTS[0], normalized)
        receipt["normalized_rows_artifact"] = {"relative": VITAL_ARTIFACTS[0], "absolute": str(rows_path)}
        receipt["runtime_source_artifact"] = {"relative": VITAL_ARTIFACTS[1], "absolute": str(raw_path)}
        receipt_path = _write_json(root, VITAL_ARTIFACTS[2], receipt)
        return {"stage": mode, "artifacts": [str(rows_path), str(receipt_path)]}
    if mode in {"smoke", "calibrate", "freeze", "freeze_or_register", "heldout", "adjudicate", "qa"}:
        _require_completed_vital_receipt(_read_json(root, VITAL_ARTIFACTS[2]))
    if mode == "smoke":
        rows: list[dict[str, Any]] = []
        for profile in ("F00", "F05", "F10"):
            rows.extend(
                _run_policy_only_first_episode(
                    config_path=target_config,
                    device=device,
                    seed=0,
                    profile=profile,
                    cap_nm=40.0,
                    mode="HI_FULL",
                    num_envs=3,
                    scenario_ids=SCENARIO_IDS[:3],
                    continuity_id="SMOKE",
                    control_steps=64,
                )
            )
        if (
            len(rows) != 9
            or {row.get("profile") for row in rows} != {"F00", "F05", "F10"}
            or {row.get("mode") for row in rows} != {"HI_FULL"}
            or any(row.get("window_transition_count") != 25 for row in rows)
        ):
            raise RuntimeError("P2 smoke must produce exactly 3 env rows at 64 control steps for each F00/F05/F10 profile")
        receipt = {
            "schema": "a2_piper_v24_p2_smoke_receipt_v1",
            "status": "EXECUTED",
            "evidentiary": False,
            "rows": len(rows),
            "envs": 3,
            "profiles": ["F00", "F05", "F10"],
            "modes": ["HI_FULL"],
            "control_steps": 64,
        }
        return {"stage": mode, "artifact": str(_write_json(root, STAGE_ARTIFACTS[1], receipt))}
    if mode == "calibrate":
        smoke = _read_json(root, STAGE_ARTIFACTS[1])
        _require_completed_smoke_receipt(smoke)
        rows: list[dict[str, Any]] = []
        for profile in FRICTION_PROFILES:
            for cap in PRIMARY_CAPS_NM:
                rows.extend(
                    _run_policy_only_first_episode(
                        config_path=target_config,
                        device=device,
                        seed=24021,
                        profile=profile,
                        cap_nm=cap,
                        mode="HI_FULL",
                        num_envs=16,
                        scenario_ids=SCENARIO_IDS,
                        continuity_id="CALIBRATION",
                    )
                )
        normalized = _validate_raw_rows(rows, kind="calibration")
        all_six_primary_valid_nonbinding = all(
            row["valid"] and row["nonbinding"]
            for row in normalized
        )
        if all_six_primary_valid_nonbinding:
            for profile in FRICTION_PROFILES:
                rows.extend(
                    _run_policy_only_first_episode(
                        config_path=target_config,
                        device=device,
                        seed=24021,
                        profile=profile,
                        cap_nm=CONTINGENCY_CAP_NM,
                        mode="HI_FULL",
                        num_envs=16,
                        scenario_ids=SCENARIO_IDS,
                        continuity_id="CALIBRATION_CONTINGENCY",
                    )
                )
            normalized = _validate_raw_rows(rows, kind="calibration_with_contingency")
        _write_jsonl(root, STAGE_ARTIFACTS[2], normalized)
        return {"stage": mode, "artifact": str(_write_json(root, STAGE_ARTIFACTS[3], {"schema": "a2_piper_v24_p2_calibration_receipt_v1", "status": "EXECUTED", "rows": len(normalized), "seed": 24021}))}
    if mode in {"freeze", "freeze_or_register"}:
        smoke = _read_json(root, STAGE_ARTIFACTS[1])
        if smoke.get("status") != "EXECUTED":
            raise RuntimeError("P2 smoke receipt is incomplete")
        calibration_rows = _read_jsonl(root, STAGE_ARTIFACTS[2])
        calibration_has_contingency = any(row.get("cap_nm") == CONTINGENCY_CAP_NM for row in calibration_rows)
        calibration = _validate_raw_rows(calibration_rows, kind="calibration_with_contingency" if calibration_has_contingency else "calibration")
        receipt = _read_json(root, STAGE_ARTIFACTS[3])
        if receipt.get("status") != "EXECUTED":
            raise RuntimeError("P2 calibration receipt is incomplete")
        vitals_receipt = _read_json(root, VITAL_ARTIFACTS[2])
        _require_completed_vital_receipt(vitals_receipt)
        rule16 = vitals_receipt["rule16_admission"]
        ladder = ladder_freeze(calibration, status="EXECUTED", rule16_admission=rule16)
        if not _validate_ladder_payload(ladder, require_executed=True):
            raise RuntimeError("P2 ladder freeze is invalid")
        # The r12 pre-pilot path is intentionally one-shot gated.  Even if a
        # future calibration happens to look sufficient, it must first pass the
        # registered marginal-E1 pilot before any heldout/final artifact.
        threshold = _pilot_required_threshold_freeze(rule16)
        _write_json(root, STAGE_ARTIFACTS[4], ladder)
        threshold_path = _write_json(root, STAGE_ARTIFACTS[5], threshold)
        if threshold["status"] == PILOT_REQUIRED_STATUS:
            from scriptsFORhuman.v24 import p2_marginal_e1_pilot

            registration_path = p2_marginal_e1_pilot.write_registration(
                vitals_receipt=vitals_receipt,
                gradient_admission=GRADIENT_ADMISSION,
            )
            return {
                "stage": "freeze_or_register",
                "status": PILOT_REQUIRED_STATUS,
                "artifacts": [str(_artifact_path(root, STAGE_ARTIFACTS[4])), str(threshold_path), str(registration_path)],
            }
        return {"stage": mode, "status": "EXECUTED", "artifacts": [str(threshold_path)]}
    if mode == "heldout":
        ladder = _read_json(root, STAGE_ARTIFACTS[4])
        threshold = _read_json(root, STAGE_ARTIFACTS[5])
        if not _validate_ladder_payload(ladder, require_executed=True) or not _validate_threshold_payload(threshold, require_executed=True):
            raise RuntimeError("P2 ladder and threshold freezes are incomplete")
        calibration_rows = _read_jsonl(root, STAGE_ARTIFACTS[2])
        calibration_has_contingency = any(row.get("cap_nm") == CONTINGENCY_CAP_NM for row in calibration_rows)
        calibration = _validate_raw_rows(calibration_rows, kind="calibration_with_contingency" if calibration_has_contingency else "calibration")
        terminal_result = _preheldout_terminal_result(calibration, ladder)
        if threshold.get("status") == PILOT_REQUIRED_STATUS:
            raise RuntimeError("MARGINAL_E1_PILOT_REQUIRED: generate and adjudicate the one-shot F3 pilot before heldout")
        threshold_is_terminal = threshold.get("status") == "NOT_ADMITTED_BY_P2_TERMINAL"
        if threshold_is_terminal:
            if terminal_result is None or threshold.get("terminal_result") != terminal_result:
                raise RuntimeError("P2 terminal threshold artifact disagrees with raw calibration/ladder")
            receipt = {
                "schema": "a2_piper_v24_p2_heldout_receipt_v1",
                "status": "NOT_ADMITTED_BY_P2_TERMINAL",
                "terminal_result": terminal_result,
                "heldout_status": "NOT_ADMITTED_BY_P2_TERMINAL",
                "rows": 0,
                "seed": 24022,
                "mode_caps_nm": None,
            }
            return {"stage": mode, "artifact": str(_write_json(root, STAGE_ARTIFACTS[7], receipt))}
        if terminal_result is not None:
            raise RuntimeError("P2 regular threshold artifact is invalid for a preregistered calibration terminal")
        rows = []
        tau_hi = ladder.get("tau_hi_nm")
        tau_boundary = ladder.get("tau_boundary_nm")
        tau_rescue = ladder.get("tau_rescue_nm")
        if tau_hi is None or tau_boundary is None or tau_rescue is None:
            raise RuntimeError("P2 heldout treatments require a selected boundary and immediately higher rescue cap")
        mode_caps = {
            "HI_FULL": float(tau_hi),
            "BOUNDARY_FULL": float(tau_boundary),
            "BOUNDARY_RP0": float(tau_boundary),
            "RESCUE_FULL": float(tau_rescue),
        }
        for runtime_mode in RUNTIME_MODES:
            for profile in FRICTION_PROFILES:
                rows.extend(
                    _run_policy_only_first_episode(
                        config_path=target_config,
                        device=device,
                        seed=24022,
                        profile=profile,
                        cap_nm=mode_caps[runtime_mode],
                        mode=runtime_mode,
                        num_envs=16,
                        scenario_ids=SCENARIO_IDS,
                        continuity_id="HELDOUT",
                    )
                )
        normalized = _validate_raw_rows(rows, kind="heldout", heldout_mode_caps=mode_caps)
        normalized = _apply_slip_exclusion(normalized, float(threshold["foot_slip_q99_m_s"]))
        normalized = _validate_raw_rows(normalized, kind="heldout", heldout_mode_caps=mode_caps)
        _write_jsonl(root, STAGE_ARTIFACTS[6], normalized)
        return {"stage": mode, "artifact": str(_write_json(root, STAGE_ARTIFACTS[7], {"schema": "a2_piper_v24_p2_heldout_receipt_v1", "status": "EXECUTED", "rows": len(normalized), "seed": 24022, "mode_caps_nm": mode_caps}))}
    if mode == "adjudicate":
        ladder = _read_json(root, STAGE_ARTIFACTS[4])
        threshold = _read_json(root, STAGE_ARTIFACTS[5])
        vitals_receipt = _read_json(root, VITAL_ARTIFACTS[2])
        _require_completed_vital_receipt(vitals_receipt)
        if threshold.get("status") == PILOT_REQUIRED_STATUS:
            raise RuntimeError("MARGINAL_E1_PILOT_REQUIRED: post-pilot finalization is required before P2 adjudication")
        parameter = _read_json(root, STAGE_ARTIFACTS[0])
        calibration_receipt = _read_json(root, STAGE_ARTIFACTS[3])
        heldout_receipt_path = _artifact_path(root, STAGE_ARTIFACTS[7])
        heldout_receipt = _read_json(root, STAGE_ARTIFACTS[7]) if heldout_receipt_path.is_file() else None
        if calibration_receipt.get("status") != "EXECUTED":
            raise RuntimeError("P2 calibration receipt is incomplete")
        if not _validate_parameter_range_payload(parameter, require_executed=True) or not _validate_ladder_payload(ladder, require_executed=True) or not _validate_threshold_payload(threshold, require_executed=True):
            raise RuntimeError("P2 final adjudication freeze artifacts are invalid")
        calibration_rows = _read_jsonl(root, STAGE_ARTIFACTS[2])
        calibration_has_contingency = any(row.get("cap_nm") == CONTINGENCY_CAP_NM for row in calibration_rows)
        calibration = _validate_raw_rows(calibration_rows, kind="calibration_with_contingency" if calibration_has_contingency else "calibration")
        terminal_result = _preheldout_terminal_result(calibration, ladder)
        threshold_is_terminal = threshold.get("status") == "NOT_ADMITTED_BY_P2_TERMINAL"
        if threshold_is_terminal:
            if terminal_result is None or threshold.get("terminal_result") != terminal_result:
                raise RuntimeError("P2 terminal threshold artifact disagrees with raw calibration/ladder")
            if not _validate_terminal_heldout_receipt(heldout_receipt, terminal_result=terminal_result):
                raise RuntimeError("P2 terminal heldout receipt is not the canonical NOT_ADMITTED_BY_P2_TERMINAL payload")
        elif terminal_result is not None:
            raise RuntimeError("P2 regular threshold artifact is invalid for a preregistered calibration terminal")
        if threshold_is_terminal:
            heldout_mode_caps = None
            heldout = []
        elif heldout_receipt is not None and heldout_receipt.get("status") == "EXECUTED":
            heldout_mode_caps = heldout_receipt.get("mode_caps_nm")
            if not isinstance(heldout_mode_caps, Mapping):
                raise RuntimeError("P2 heldout receipt is missing the executed mode-cap treatment map")
            heldout = _validate_raw_rows(_read_jsonl(root, STAGE_ARTIFACTS[6]), kind="heldout", heldout_mode_caps=heldout_mode_caps)
            heldout = _apply_slip_exclusion(heldout, float(threshold["foot_slip_q99_m_s"]))
            heldout = _validate_raw_rows(heldout, kind="heldout", heldout_mode_caps=heldout_mode_caps)
        elif heldout_receipt is None or heldout_receipt.get("status") == "NOT_ADMITTED_BY_P2_TERMINAL":
            if terminal_result is None:
                raise RuntimeError("P2 heldout evidence is missing before a non-terminal adjudication")
            heldout_mode_caps = None
            heldout = []
        else:
            raise RuntimeError("P2 heldout receipt has an unsupported status")
        pairs, pairing_complete = _derive_heldout_pairs(heldout, mode_caps=heldout_mode_caps) if heldout else ([], False)
        e_certificate = {
            "schema": E_REGION_SCHEMA,
            "status": "TERMINAL" if not heldout else "EXECUTED",
            "terminal_result": terminal_result,
            "heldout_status": "NOT_ADMITTED_BY_P2_TERMINAL" if not heldout else "EXECUTED",
            "rows": len(pairs),
            "pairing_complete": pairing_complete,
            "e2_confirmed_count": sum(1 for pair in pairs if pair["e2_confirmed"]),
            "raw_recomputation": True,
            "rule16_admission": vitals_receipt["rule16_admission"],
            "owner_decision_artifact": vitals_receipt["owner_decision_artifact"],
            "vitals_receipt_artifact": _receipt_reference(VITAL_ARTIFACTS[2]),
        }
        _write_json(root, STAGE_ARTIFACTS[8], e_certificate)
        final = adjudicate_p2(calibration_rows=calibration, heldout_rows=heldout, parameter_range_valid=_validate_parameter_range_payload(parameter, require_executed=True), ladder_valid=_validate_ladder_payload(ladder, require_executed=True), threshold_valid=_validate_threshold_payload(threshold, require_executed=True), authority_gates_pass=_authority_source_gate(calibration) and (not heldout or _authority_source_gate(heldout)), authority_set=AUTHORITY_SET, heldout_mode_caps=heldout_mode_caps, parameter_range_payload=parameter, ladder_payload=ladder, threshold_payload=threshold, vitals_receipt=vitals_receipt)
        final["rule16_admission"] = vitals_receipt["rule16_admission"]
        final["owner_decision_artifact"] = vitals_receipt["owner_decision_artifact"]
        final["vitals_receipt_artifact"] = _receipt_reference(VITAL_ARTIFACTS[2])
        return {"stage": mode, "artifact": str(_write_json(root, STAGE_ARTIFACTS[9], final))}
    if mode == "qa":
        final = _read_json(root, STAGE_ARTIFACTS[9])
        e_certificate = _read_json(root, STAGE_ARTIFACTS[8])
        vitals_receipt = _read_json(root, VITAL_ARTIFACTS[2])
        _require_completed_vital_receipt(vitals_receipt)
        if final.get("schema") != FINAL_SCHEMA:
            raise RuntimeError("P2 final adjudication prerequisite is incomplete")
        if final.get("raw_recomputation") is not True:
            raise RuntimeError("P2 QA requires actual raw recomputation")
        _validate_rule16_admission(final.get("rule16_admission"), require_source_files=True)
        if final.get("rule16_admission") != vitals_receipt.get("rule16_admission"):
            raise RuntimeError("P2 QA Rule16 admission does not match the vitals receipt")
        if final.get("owner_decision_artifact") != vitals_receipt.get("owner_decision_artifact"):
            raise RuntimeError("P2 QA owner-decision provenance is not bound to the final result")
        if final.get("terminal"):
            if final.get("p3_admitted") is not False or final.get("heldout_status") != "NOT_ADMITTED_BY_P2_TERMINAL" or e_certificate.get("status") != "TERMINAL":
                raise RuntimeError("P2 terminal QA receipt is inconsistent")
        elif e_certificate.get("status") != "EXECUTED":
            raise RuntimeError("P2 full-heldout QA receipt is incomplete")
        qa = {"schema": "a2_piper_v24_p2_qa_semantic_validation_v1", "status": "EXECUTED", "final_schema": final.get("schema"), "typed_results": final.get("typed_results"), "terminal": final.get("terminal") is True, "heldout_status": final.get("heldout_status"), "raw_recomputation": True, "rule16_admission": final["rule16_admission"], "owner_decision_artifact": final["owner_decision_artifact"], "vitals_receipt_artifact": final["vitals_receipt_artifact"], "artifact_order": list(STAGE_ARTIFACTS)}
        return {"stage": mode, "artifact": str(_write_json(root, STAGE_ARTIFACTS[10], qa))}
    if mode in {"pilot_commands", "pilot_adjudicate", "post_pilot_finalize"}:
        from scriptsFORhuman.v24 import p2_marginal_e1_pilot

        if mode == "pilot_commands":
            registration = p2_marginal_e1_pilot.build_registration(
                vitals_receipt=_read_json(root, VITAL_ARTIFACTS[2]),
                gradient_admission=GRADIENT_ADMISSION,
            )
            return {"stage": mode, "artifact": str(p2_marginal_e1_pilot.write_commands(registration=registration))}
        raise RuntimeError(
            f"{mode} requires explicit pilot input; use p2_marginal_e1_pilot.py to avoid implicit runtime/evidence reads"
        )
    raise ValueError(f"unsupported P2 stage {mode!r}")


def _cpu_utilization(load_bearing: Sequence[bool], pd_command: Sequence[float], limits: Sequence[float]) -> float | None:
    values = [abs(float(command)) / float(limit) for flag, command, limit in zip(load_bearing, pd_command, limits) if flag]
    return max(values) if values else None


def _synthetic_parameter_vitals(cap: float, profile_name: str) -> dict[str, Any]:
    profile = FRICTION_PROFILES[profile_name]
    friction = {
        "static_friction_nm": profile["static_effort_nm"],
        "dynamic_friction_nm": profile["dynamic_effort_nm"],
        "viscous_friction_nm_s_per_rad": profile["viscous_coefficient_nm_s_per_rad"],
    }
    return {
        "schema": "a2_piper_v24_p2_parameter_vitals_v1",
        "authority": "MODELED_FROM_PARAMS",
        "solver_applied": False,
        "actual_generalized_torque": "UNAVAILABLE_NOT_USED",
        "arm": {
            "joint_names": [f"arm_j{index}" for index in range(1, 7)],
            "joint_ids": list(range(6)),
            "registered_active_cap_nm": cap,
            "registered_cap_values_nm": list(REGISTERED_CAPS_NM),
            "requested_effort_limit_nm": [cap] * 6,
            "readback_effort_limit_nm": [cap] * 6,
            "contract_effort_limit_nm": [cap] * 6,
        },
        "gripper": {
            "joint_names": ["arm_j7", "arm_j8"],
            "joint_ids": [6, 7],
            "effort_limit_nm": {"readback": [45.0, 45.0], "contract": [45.0, 45.0]},
            "stiffness_nm_per_rad": {"readback": [1300.0, 1300.0], "contract": [1300.0, 1300.0]},
            "damping_nm_s_per_rad": {"readback": [32.0, 32.0], "contract": [32.0, 32.0]},
            "swept_by_arm_cap": False,
            "unchanged_by_arm_cap": True,
        },
        "door_friction": {
            "hinge_joint_name": "hinge_joint",
            "hinge_joint_id": 0,
            "requested": dict(friction),
            "readback": dict(friction),
            "contract": dict(friction),
            "units": {
                "static_friction_nm": "N*m",
                "dynamic_friction_nm": "N*m",
                "viscous_friction_nm_s_per_rad": "N*m*s/rad",
            },
            "authority": "MODELED_FROM_PARAMS",
            "solver_applied": False,
            "actual_generalized_torque": "UNAVAILABLE_NOT_USED",
            "non_hinge_joint_ids": [1],
            "non_hinge_unchanged": True,
            "non_hinge_before": {"joint_friction_coeff": [0.0], "joint_dynamic_friction_coeff": [0.0], "joint_viscous_friction_coeff": [0.0]},
            "non_hinge_after": {"joint_friction_coeff": [0.0], "joint_dynamic_friction_coeff": [0.0], "joint_viscous_friction_coeff": [0.0]},
        },
        "unit_boundary": {
            "analysis_surface": "radian",
            "degree_per_radian_boundary": 57.3,
            "static_dynamic_effort_conversion_applied": False,
            "viscous_conversion_applied": False,
        },
    }


def _synthetic_vital_rows() -> list[dict[str, Any]]:
    """Build deterministic CPU-only rows for contract self-checks."""

    rows: list[dict[str, Any]] = []
    for env_id, scenario_id in enumerate(SCENARIO_IDS):
        rows.append(
            {
                "env_id": env_id,
                "scenario_id": scenario_id,
                "seed": 0,
                "profile": "F00",
                "cap_nm": 40.0,
                "mode": "HI_FULL",
                "continuity_id": "VITALS_R12_FIXED_SHAM",
                "authority": RUNTIME_AUTHORITY_SET,
                "window_transition_count": 25,
                "window_start_step": 0,
                "window_end_step": 24,
                "window_stable_grasp_count": 20,
                "window_stage_ids": [3],
                "window_stage_reach_valid": True,
                "window_selection": WINDOW_SELECTION_ADMITTED,
                "window_selection_status": WINDOW_SELECTION_ADMITTED,
                "window_selection_reason": WINDOW_SELECTION_ADMITTED,
                "window_selection_admission_status": WINDOW_SELECTION_ADMITTED_STATUS,
                "window_selection_valid": True,
                "excluded_window_selection": False,
                "stable_grasp": True,
                "stable_grasp_fraction": 0.8,
                "grasp_source_unavailable": False,
                "model_source_unavailable": False,
                "source_unavailable": None,
                "source_status": {"foot": "AVAILABLE", "grasp": "AVAILABLE", "model": "AVAILABLE"},
                "source_api": {"state": "IsaacLab.Articulation.data", "foot": "simulator.contact_forces"},
                "valid": True,
                "model_valid": True,
                "foot_slip_valid": True,
                "max_loaded_foot_slip_m_s": 0.01,
                "alpha_valid": True,
                "theta_start_rad": 0.0,
                "theta_end_rad": 0.1,
                "progress_recovery_delta_rad": 0.1,
                "tau_req_median_nm": 12.0,
                "lambda_median": 0.7,
                "lambda": 0.7,
                "directional_utilization_median": 0.95,
                "directional_clip_fraction_median": 0.4,
                "directional_high_effort": True,
                "nonbinding": False,
                "excluded_geometry": False,
                "excluded_grasp": False,
                "excluded_direction": False,
                "excluded_slip": False,
                "excluded_pathology": False,
                "parameter_vitals": _synthetic_parameter_vitals(40.0, "F00"),
            }
        )
    return rows


def _self_check() -> dict[str, Any]:
    def expect_error(fn, label: str) -> None:
        try:
            fn()
        except (AssertionError, AttributeError, RuntimeError, TypeError, ValueError):
            return
        raise AssertionError(f"self-check expected rejection: {label}")

    def make_row(*, seed: int, profile: str, cap: float, scenario: str, mode: str, continuity: str, progress: float, lam: float, nonbinding: bool, high: bool, stable: bool = True, slip: float = 0.01) -> dict[str, Any]:
        return {
            "seed": seed,
            "profile": profile,
            "cap_nm": cap,
            "scenario_id": scenario,
            "mode": mode,
            "continuity_id": continuity,
            "window_transition_count": 25,
            "window_start_step": 0,
            "window_end_step": 24,
            "authority": RUNTIME_AUTHORITY_SET,
            "theta_start_rad": 0.0,
            "theta_end_rad": progress,
            "valid": True,
            "model_valid": True,
            "nonbinding": nonbinding,
            "stable_grasp": stable,
            "stable_grasp_fraction": 1.0 if stable else 0.0,
            "grasp_source_unavailable": False,
            "model_source_unavailable": False,
            "directional_high_effort": high,
            "progress_recovery_delta_rad": progress,
            "rescue_progress_rad": None,
            "rescue_gain_rad": None,
            "tau_req_median_nm": 1.0 + list(FRICTION_PROFILES).index(profile),
            "lambda_median": lam,
            "lambda": lam,
            "directional_utilization_median": 0.95 if high else 0.80,
            "directional_clip_fraction_median": 0.40 if high else 0.10,
            "foot_slip_valid": True,
            "max_loaded_foot_slip_m_s": slip,
            "source_unavailable": None,
            "source_status": {"foot": "AVAILABLE", "grasp": "AVAILABLE", "model": "AVAILABLE"},
            "alpha_valid": True,
            "excluded_geometry": False,
            "excluded_grasp": False,
            "excluded_direction": False,
            "excluded_slip": False,
            "excluded_pathology": False,
            "excluded_window_selection": False,
            "window_selection": WINDOW_SELECTION_ADMITTED,
            "window_selection_status": WINDOW_SELECTION_ADMITTED,
            "window_selection_reason": WINDOW_SELECTION_ADMITTED,
            "window_selection_admission_status": WINDOW_SELECTION_ADMITTED_STATUS,
            "window_selection_valid": True,
            "window_stable_grasp_count": 20 if stable else 19,
            "window_stage_ids": [3],
            "window_opening_stages": [3, 4],
            "parameter_vitals": _synthetic_parameter_vitals(cap, profile),
            "source_api": {"state": "synthetic-self-check"},
        }

    calibration: list[dict[str, Any]] = []
    for cap in PRIMARY_CAPS_NM:
        for profile in FRICTION_PROFILES:
            for scenario in SCENARIO_IDS:
                if cap == 100.0:
                    progress = 0.10
                    nonbinding = True
                elif cap == 60.0:
                    progress = 0.05 if profile != "F00" else 0.04
                    nonbinding = False
                else:
                    progress = 0.01
                    nonbinding = False
                lam = 0.30 if profile == "F00" else 0.60 + 0.10 * list(FRICTION_PROFILES).index(profile)
                calibration.append(
                    make_row(
                        seed=24021,
                        profile=profile,
                        cap=cap,
                        scenario=scenario,
                        mode="HI_FULL",
                        continuity="CALIBRATION",
                        progress=progress,
                        lam=lam,
                        nonbinding=nonbinding,
                        high=True,
                    )
                )
    calibration = _validate_raw_rows(calibration, kind="calibration")
    vitals_receipt = _build_vital_receipt(_synthetic_vital_rows())
    ladder = ladder_freeze(calibration, status="EXECUTED", rule16_admission=vitals_receipt["rule16_admission"])
    _require(ladder["tau_hi_nm"] == 100.0 and ladder["tau_boundary_nm"] == 60.0 and ladder["tau_rescue_nm"] == 100.0, "self-check calibration ladder pairing failed")
    threshold = certificate_threshold_freeze(calibration, status="EXECUTED", tau_hi_nm=ladder["tau_hi_nm"], rule16_admission=vitals_receipt["rule16_admission"])

    mode_caps = {"HI_FULL": 100.0, "BOUNDARY_FULL": 60.0, "BOUNDARY_RP0": 60.0, "RESCUE_FULL": 100.0}
    heldout: list[dict[str, Any]] = []
    for mode, cap in mode_caps.items():
        for profile in FRICTION_PROFILES:
            for scenario in SCENARIO_IDS:
                progress = 0.01 if mode in {"BOUNDARY_FULL", "BOUNDARY_RP0"} else 0.10
                heldout.append(
                    make_row(
                        seed=24022,
                        profile=profile,
                        cap=cap,
                        scenario=scenario,
                        mode=mode,
                        continuity="HELDOUT",
                        progress=progress,
                        lam=0.70,
                        nonbinding=False,
                        high=True,
                    )
                )
    heldout = _validate_raw_rows(heldout, kind="heldout", heldout_mode_caps=mode_caps)
    final = adjudicate_p2(
        calibration_rows=calibration,
        heldout_rows=heldout,
        parameter_range_valid=True,
        ladder_valid=True,
        threshold_valid=True,
        authority_gates_pass=True,
        authority_set=AUTHORITY_SET,
        heldout_mode_caps=mode_caps,
        parameter_range_payload=parameter_range_freeze(status="EXECUTED"),
        ladder_payload=ladder,
        threshold_payload=threshold,
        vitals_receipt=vitals_receipt,
        require_vitals_source_files=False,
    )
    _require(final["e1_established"] is True and final["p3_admitted"] is True and "V24_E2_BOUNDARY_ESTABLISHED" in final["typed_results"], "self-check adjudication truth failed")

    raw_window = []
    for step in range(25):
        raw_window.append(
            {
                "authority": RUNTIME_AUTHORITY_SET,
                "theta_rad": float(step + 1) * 0.01,
                "theta_pre_rad": float(step) * 0.01,
                "theta_post_rad": float(step + 1) * 0.01,
                "theta_delta_rad": 0.01,
                "episode_step": step + 1,
                "tau_required_nm": float(step + 1),
                "lambda_load": float(step) / 100.0,
                "directional_utilization": 0.95,
                "directional_clipped": step < 12,
                "valid": True,
                "stable_grasp": True,
                "foot_slip_m_s": float(step) / 1000.0,
                "foot_slip_valid": True,
                "source_unavailable": None,
                "grasp_source_unavailable": False,
                "model_source_unavailable": False,
                "source_status": {"foot": "AVAILABLE", "grasp": "AVAILABLE", "model": "AVAILABLE"},
                "excluded_geometry": False,
                "excluded_grasp": False,
                "excluded_direction": False,
                "excluded_pathology": False,
                "alpha_valid": True,
                "source_api": {"state": "synthetic-self-check"},
            }
        )
    def cpu_window_aggregate(window: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Dependency-free oracle for the runtime's 25-transition reduction contract."""
        if len(window) != 25:
            raise RuntimeError("self-check window oracle requires exactly 25 transitions")
        authority = window[0].get("authority")
        if authority != RUNTIME_AUTHORITY_SET or any(row.get("authority") != authority for row in window):
            raise RuntimeError("self-check window oracle requires stable runtime authority")

        def values(field: str) -> list[float]:
            raw = [row.get(field) for row in window]
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in raw):
                return []
            return [float(value) for value in raw]

        theta_pre = values("theta_pre_rad")
        theta_post = values("theta_post_rad")
        theta_delta = values("theta_delta_rad")
        tau = values("tau_required_nm")
        loads = values("lambda_load")
        utilization = values("directional_utilization")
        foot_ok = all(row.get("foot_slip_valid") is True for row in window)
        foot = values("foot_slip_m_s") if foot_ok else []
        stable = [row.get("stable_grasp") for row in window]
        stable_ok = all(isinstance(value, bool) for value in stable)
        stable_count = sum(bool(value) for value in stable) if stable_ok else None
        stable_fraction = stable_count / 25 if stable_count is not None else None
        clip_count = sum(bool(row.get("directional_clipped")) for row in window)
        required = len(tau) == len(loads) == len(utilization) == 25
        grasp_source_unavailable = any(row.get("grasp_source_unavailable") is True for row in window)
        model_source_unavailable = any(row.get("model_source_unavailable") is True for row in window) or not required
        final = dict(window[0])
        for raw_field in ("episode_step", "theta_rad", "theta_pre_rad", "theta_post_rad", "theta_delta_rad", "tau_required_nm", "lambda_load", "directional_utilization", "directional_clipped", "foot_slip_m_s"):
            final.pop(raw_field, None)
        final.update(
            {
                "window_transition_count": 25,
                "window_start_step": int(window[0]["episode_step"]),
                "window_end_step": int(window[-1]["episode_step"]),
                "theta_start_rad": theta_pre[0],
                "theta_end_rad": theta_post[-1],
                "progress_recovery_delta_rad": sum(theta_delta),
                "rescue_progress_rad": None,
                "rescue_gain_rad": None,
                "tau_req_median_nm": median(tau) if required else None,
                "lambda_median": median(loads) if required else None,
                "lambda": median(loads) if required else None,
                "directional_utilization_median": median(utilization) if required else None,
                "directional_clip_fraction_median": clip_count / 25,
                "stable_grasp_fraction": stable_fraction,
                "stable_grasp": stable_count >= 20 if stable_count is not None else None,
                "max_loaded_foot_slip_m_s": max(foot) if len(foot) == 25 else None,
                "foot_slip_valid": len(foot) == 25,
                "source_unavailable": "SOURCE_UNAVAILABLE" if (grasp_source_unavailable or model_source_unavailable) else None,
                "grasp_source_unavailable": grasp_source_unavailable,
                "model_source_unavailable": model_source_unavailable,
                "source_status": {
                    "foot": "AVAILABLE",
                    "grasp": "SOURCE_UNAVAILABLE" if grasp_source_unavailable else "AVAILABLE",
                    "model": "SOURCE_UNAVAILABLE" if model_source_unavailable else "AVAILABLE",
                },
                "directional_high_effort": len(utilization) == 25 and median(utilization) >= 0.90 and clip_count / 25 >= 0.30,
                "valid": all(row.get("valid") is True for row in window) and required,
                "nonbinding": clip_count == 0,
                "excluded_geometry": any(row.get("excluded_geometry") is True for row in window),
                "excluded_grasp": stable_count is not None and stable_count < 20,
                "excluded_direction": any(row.get("excluded_direction") is True for row in window),
                "excluded_slip": False,
                "excluded_pathology": any(row.get("excluded_pathology") is True for row in window),
                "alpha_valid": True,
                "source_api": window[0]["source_api"],
                "authority": authority,
            }
        )
        return final

    aggregate = cpu_window_aggregate(raw_window)
    _require(aggregate["window_transition_count"] == 25 and aggregate["tau_req_median_nm"] == 13.0 and aggregate["directional_clip_fraction_median"] == 12 / 25 and aggregate["max_loaded_foot_slip_m_s"] == 0.024 and aggregate["theta_start_rad"] == 0.0 and aggregate["theta_end_rad"] == 0.25 and math.isclose(aggregate["progress_recovery_delta_rad"], 0.25, rel_tol=0.0, abs_tol=1.0e-12), "self-check 25-transition aggregation failed")
    _require(aggregate["rescue_progress_rad"] is None and aggregate["rescue_gain_rad"] is None, "self-check rejected within-row causal rescue values")

    runtime_source = (REPO_ROOT / "gr00t/rl/envs/door/a2_v24_force_boundary.py").read_text(encoding="utf-8")
    door_source = (REPO_ROOT / "gr00t/rl/envs/door/door_open_a2_base.py").read_text(encoding="utf-8")
    force_update_start = door_source.index("    def _update_a2_v24_force_boundary")
    force_update_end = door_source.index("    def get_a2_v24_force_boundary", force_update_start)
    force_update_source = door_source[force_update_start:force_update_end]
    _require("_get_a2_stage3_stage4_contact_squeeze_masks" in force_update_source and "_get_a2_stage3_stage4_contact_stability_mask" in force_update_source, "self-check current stable-grasp diagnostic predicate missing")
    _require("_a2_stage3_grasp_streak_highwater" not in force_update_source, "self-check exporter must not use grasp highwater as current stable-grasp telemetry")
    _require("self._aggregate_window(" in runtime_source and "self._fallback_windows" in runtime_source, "self-check runtime window-selection hook missing")
    _require("len(fallback) != FORCE_WINDOW_TRANSITIONS" in runtime_source, "self-check runtime fallback completion gate missing")
    _require("if not bool(torch.all(self._completed).item())" in runtime_source, "self-check runtime publish gate missing")

    def cpu_publish(path: Path, rows: Sequence[Mapping[str, Any]], completed: Sequence[bool]) -> None:
        if not all(completed):
            raise RuntimeError("self-check publish oracle rejects incomplete environments")
        if path.exists():
            raise RuntimeError("self-check publish oracle refuses overwrite")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")

    with tempfile.TemporaryDirectory(prefix="v24_p2_self_check_") as temp_dir:
        path = Path(temp_dir) / "P2_RUNTIME_ROWS.jsonl"
        expect_error(lambda: cpu_publish(path, [aggregate], [False]), "publish incomplete env")
        cpu_publish(path, [aggregate], [True])
        _require(len(path.read_text(encoding="utf-8").splitlines()) == 1, "self-check exporter must publish exactly one row")

    for stream_length in (25, 64, 1000):
        stream = list(raw_window)
        for step in range(25, stream_length):
            stream.append(dict(raw_window[-1], episode_step=step + 1, theta_pre_rad=0.25, theta_post_rad=0.25, theta_delta_rad=0.0))
        _require(cpu_window_aggregate(stream[:25]) == aggregate, f"self-check first-window freeze changed for {stream_length}-sample stream")
    _require("self._completed[env_id] or self._rows[env_id] is not None" in runtime_source, "self-check runtime must ignore post-window samples")

    grasp_20 = cpu_window_aggregate([dict(row, stable_grasp=True, grasp_source_unavailable=False) for row in raw_window[:20]] + [dict(row, stable_grasp=False, grasp_source_unavailable=False) for row in raw_window[20:]])
    grasp_19 = cpu_window_aggregate([dict(row, stable_grasp=True, grasp_source_unavailable=False) for row in raw_window[:19]] + [dict(row, stable_grasp=False, grasp_source_unavailable=False) for row in raw_window[19:]])
    _require(grasp_20["stable_grasp"] is True and grasp_20["excluded_grasp"] is False, "self-check 20/25 grasp threshold failed")
    _require(grasp_19["stable_grasp"] is False and grasp_19["excluded_grasp"] is True, "self-check 19/25 grasp exclusion failed")

    grasp_missing = [
        dict(
            row,
            stable_grasp=None,
            stable_grasp_fraction=None,
            grasp_source_unavailable=True,
            source_unavailable="SOURCE_UNAVAILABLE",
            source_status={"foot": "AVAILABLE", "grasp": "SOURCE_UNAVAILABLE", "model": "AVAILABLE"},
        )
        for row in raw_window
    ]
    model_missing = [
        dict(
            row,
            tau_required_nm=None,
            lambda_load=None,
            directional_utilization=None,
            model_source_unavailable=True,
            source_unavailable="SOURCE_UNAVAILABLE",
            source_status={"foot": "AVAILABLE", "grasp": "AVAILABLE", "model": "SOURCE_UNAVAILABLE"},
        )
        for row in raw_window
    ]
    grasp_missing_aggregate = cpu_window_aggregate(grasp_missing)
    model_missing_aggregate = cpu_window_aggregate(model_missing)
    _require(grasp_missing_aggregate["grasp_source_unavailable"] is True and grasp_missing_aggregate["model_source_unavailable"] is False, "self-check grasp source typing failed")
    _require(model_missing_aggregate["grasp_source_unavailable"] is False and model_missing_aggregate["model_source_unavailable"] is True, "self-check model source typing failed")

    _require(_apply_slip_exclusion([heldout[0]], 0.005)[0]["excluded_slip"] is True, "self-check heldout Q99 slip exclusion failed")
    bad_authority = dict(calibration[0])
    bad_authority.pop("authority")
    expect_error(lambda: _validate_raw_rows([bad_authority] + calibration[1:], kind="calibration"), "missing authority")
    bad_source = dict(heldout[0])
    bad_source["source_unavailable"] = None
    bad_source["foot_slip_valid"] = False
    bad_source["max_loaded_foot_slip_m_s"] = 0.01
    expect_error(lambda: _validate_raw_rows([bad_source] + heldout[1:], kind="heldout", heldout_mode_caps=mode_caps), "missing source")
    expect_error(lambda: _require_completed_smoke_receipt({}), "calibrate before smoke")
    expect_error(lambda: adjudicate_p2(calibration_rows=calibration, heldout_rows=heldout, parameter_range_valid=True, ladder_valid=True, threshold_valid=True, authority_gates_pass=True, authority_set=AUTHORITY_SET, heldout_mode_caps=mode_caps), "missing freeze artifacts")

    contingency_binding = [dict(row, nonbinding=True) for row in calibration]
    contingency_rows = [make_row(seed=24021, profile=profile, cap=10.0, scenario=scenario, mode="HI_FULL", continuity="CALIBRATION_CONTINGENCY", progress=0.0, lam=0.7, nonbinding=False, high=True) for profile in FRICTION_PROFILES for scenario in SCENARIO_IDS]
    binding_ladder = _derive_ladder(contingency_binding + contingency_rows, status="EXECUTED")
    nonbinding_ladder = _derive_ladder(contingency_binding + [dict(row, nonbinding=True) for row in contingency_rows], status="EXECUTED")
    _require(binding_ladder["command_path_binding"] is True and nonbinding_ladder["command_path_binding"] is False, "self-check contingency binding/nonbinding distinction failed")
    expect_error(
        lambda: adjudicate_p2(
            calibration_rows=contingency_binding + [dict(row, nonbinding=True) for row in contingency_rows],
            heldout_rows=[],
            parameter_range_valid=True,
            ladder_valid=True,
            threshold_valid=True,
            authority_gates_pass=True,
            authority_set=AUTHORITY_SET,
            parameter_range_payload=parameter_range_freeze(status="EXECUTED"),
            ladder_payload=nonbinding_ladder,
            threshold_payload=_terminal_threshold_freeze("V24_ARM_COMMAND_PATH_NOT_BINDING", rule16_admission=vitals_receipt["rule16_admission"]),
            vitals_receipt=vitals_receipt,
        ),
        "pre-pilot command-path terminal",
    )
    no_boundary = [dict(row, directional_utilization_median=0.80, directional_clip_fraction_median=0.10, directional_high_effort=False) for row in calibration]
    no_boundary_ladder = _derive_ladder(no_boundary, status="EXECUTED")
    no_boundary_ladder["rule16_admission"] = vitals_receipt["rule16_admission"]
    no_boundary_threshold = _pilot_required_threshold_freeze(vitals_receipt["rule16_admission"])
    expect_error(
        lambda: adjudicate_p2(
            calibration_rows=no_boundary,
            heldout_rows=[],
            parameter_range_valid=True,
            ladder_valid=True,
            threshold_valid=True,
            authority_gates_pass=True,
            authority_set=AUTHORITY_SET,
            parameter_range_payload=parameter_range_freeze(status="EXECUTED"),
            ladder_payload=no_boundary_ladder,
            threshold_payload=no_boundary_threshold,
            vitals_receipt=vitals_receipt,
        ),
        "pre-pilot denominator terminal",
    )
    _require(mode_caps["HI_FULL"] == ladder["tau_hi_nm"], "self-check HI_FULL must read tau_hi artifact")
    reset_source = runtime_source[runtime_source.index("    def reset_envs("):runtime_source.index("    def close(", runtime_source.index("    def reset_envs("))]
    _require(reset_source.index("self.door.write_joint_friction_coefficient_to_sim") < reset_source.index("self.apply_friction"), "self-check friction reset order failed")
    _require(_cpu_utilization([True, False, False], [1.0, 999.0, 999.0], [10.0, 1.0, 1.0]) == 0.1, "self-check utilization finite reduction failed")
    _require(_cpu_utilization([False, False, False], [1.0, 999.0, 999.0], [10.0, 1.0, 1.0]) is None, "self-check no-load-bearing status failed")
    return {
        "status": "SELF_CHECK_PASS",
        "calibration_rows": len(calibration),
        "heldout_rows": len(heldout),
        "typed_results": final["typed_results"],
        "window_transition_count": aggregate["window_transition_count"],
        "progress_recovery_delta_rad": aggregate["progress_recovery_delta_rad"],
        "stream_lengths": [25, 64, 1000],
        "stable_grasp_threshold": "20/25",
        "source_typing": ["foot", "grasp", "model"],
        "terminal_results": ["PRE_PILOT_TERMINAL_FORBIDDEN"],
        "e2_confirmed_count": final["e2_confirmed_count"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v24 P2 force-boundary plan and canonical runtime stages")
    parser.add_argument("--plan", action="store_true", help="validate and print the CPU-only frozen P2 plan")
    parser.add_argument("--self-check", action="store_true", help="run bounded CPU pure-function and append-only self-check")
    parser.add_argument("--mode", choices=("prepare", "vitals", "smoke", "calibrate", "freeze", "freeze_or_register", "heldout", "adjudicate", "qa", "pilot_commands", "pilot_adjudicate", "post_pilot_finalize"), help="execute one canonical P2 stage")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="canonical P2 overlay path")
    parser.add_argument("--output", default=str(REPO_ROOT / ARTIFACT_ROOT), help="canonical P2 artifact root")
    parser.add_argument("--device", default="cuda:0", help="IsaacLab device for runtime stages")
    args = parser.parse_args(argv)
    if args.plan:
        print(json.dumps(build_plan(args.config), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0
    if args.self_check:
        print(json.dumps(_self_check(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0
    if args.mode is None:
        parser.error("pass --plan, --self-check, or one canonical --mode")
    result = run_stage(args.mode, config_path=args.config, artifact_root=args.output, device=args.device)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ARTIFACT_ROOT",
    "CONFIG_PATH",
    "FINAL_SCHEMA",
    "GRADIENT_ADMISSION",
    "OWNER_DECISION",
    "PILOT_ARTIFACT_ROOT",
    "PILOT_REGISTRATION_ID",
    "REGISTERED_ARTIFACTS",
    "RULE16_SCHEMA",
    "STAGE_REACH_REFERENCE_BAND",
    "TYPED_RESULTS",
    "VITALS_RECEIPT_SCHEMA",
    "VITALS_RUNTIME_ARTIFACT",
    "VITALS_SOURCE",
    "VITAL_ARTIFACTS",
    "WINDOW_SELECTION_ADMITTED",
    "WINDOW_SELECTION_FALLBACK",
    "adjudicate_p2",
    "artifact_plan",
    "build_plan",
    "certificate_threshold_freeze",
    "classify_e_region",
    "ladder_freeze",
    "parameter_range_freeze",
    "qualifies_boundary_cap",
    "run_stage",
    "select_boundary_cap",
    "validate_overlay",
    "_build_vital_receipt",
    "_synthetic_vital_rows",
    "_validate_parameter_vitals",
    "_validate_vital_rows",
    "_validate_window_selection",
]
