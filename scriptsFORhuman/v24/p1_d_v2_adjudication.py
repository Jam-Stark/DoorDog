"""CPU adjudicator for the Owner D-v2 P1 revision.

The adjudicator keeps the historical R1 final receipt immutable and requires
the actual A--G and H/I schema fields that support the historical passing
facts.  It emits one append-only D-v2 adjudication receipt only after the
new producer receipt and its caller-supplied tolerance freeze are complete.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v24_common import (
        REPO_ROOT,
        V24_P1_FRICTION_ROOT,
        absolute,
        read_json,
        rel_path,
        require_file,
        write_json,
    )
except ImportError:  # direct ``python scriptsFORhuman/v24/...py`` invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v24._v24_common import (
        REPO_ROOT,
        V24_P1_FRICTION_ROOT,
        absolute,
        read_json,
        rel_path,
        require_file,
        write_json,
    )


D_V2_PRODUCER_SCHEMA = "a2_piper_v24_p1_d_v2_energy_v1"
D_V2_TOLERANCE_SCHEMA = "a2_piper_v24_p1_d_v2_tolerance_freeze_v1"
D_V2_ADJUDICATION_SCHEMA = "a2_piper_base_v24_p1_d_v2_owner_revision_adjudication_v1"
D_V2_MODE = "D_V2_ENERGY"
OLD_FINAL_SCHEMA = "a2_piper_base_v24_p1_final_adjudication_v1"
AG_SCHEMA = "a2_piper_v24_p1_native_friction_probe_v1"
HI_SCHEMA = "a2_piper_v24_p0_p1_runtime_compatibility_receipt_v1"
OWNER_DECISION = REPO_ROOT / "scriptsFORhuman/v24/DoorDog_v24_owner_decision_d_gate_revision_20260817.md"
OLD_FINAL = REPO_ROOT / "logs_eval/base_v24/p1/final_adjudication/r1/V24_P1_FINAL_ADJUDICATION.json"
AG_RECEIPT = REPO_ROOT / "logs_eval/base_v24/p1/friction_backend/a_g_acceptance_r9_gpu0/P1_A_G_RECEIPT.json"
HI_RECEIPT = REPO_ROOT / "logs_eval/base_v24/p0/runtime_compatibility/r6/P0_P1_RUNTIME_COMPATIBILITY_RECEIPT.json"
D_V2_ROOT = V24_P1_FRICTION_ROOT / "d_v2_energy_r1_gpu0"
D_V2_RECEIPT = D_V2_ROOT / "D_V2_ENERGY_RECEIPT.json"
D_V2_TOLERANCE = D_V2_ROOT / "D_V2_TOLERANCE_FREEZE.json"
OUTPUT_ROOT = REPO_ROOT / "logs_eval/base_v24/p1/final_adjudication/d_v2_r1"
OUTPUT = OUTPUT_ROOT / "V24_P1_D_V2_FINAL_ADJUDICATION.json"


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _validate_historical(old: Mapping[str, Any], ag: Mapping[str, Any], hi: Mapping[str, Any]) -> dict[str, Any]:
    _require(old.get("schema") == OLD_FINAL_SCHEMA, "historical final receipt schema mismatch")
    _require(old.get("typed_result") == "V24_FRICTION_AUTHORITY_INSUFFICIENT", "historical typed result changed")
    _require(old.get("status") == "FINAL_STOP_AT_P1", "historical final status changed")
    old_acceptance = _mapping(old.get("acceptance"), label="historical acceptance")
    expected_acceptance = {
        "A_breakaway": "PASS",
        "B_kinetic_plateau": "PASS",
        "C_distinct_from_damping": "PASS",
        "E_chatter": "PASS",
        "F_timestep": "PASS_QUALITATIVE_ONLY",
        "G_orthogonality": "PASS",
        "H_reset_persistence": "PASS",
        "I_legacy_default_off_parity": "PASS",
    }
    for field, expected in expected_acceptance.items():
        _require(old_acceptance.get(field) == expected, f"historical acceptance {field} is not passing")
    old_authority = _mapping(old.get("authority_boundary"), label="historical authority")
    _require(old_authority.get("actual_generalized_torque_claim") is False, "historical receipt claims generalized torque")
    _require(
        old_authority.get("solver_friction_torque_component") == "UNAVAILABLE_FROM_PERMITTED_HIGH_LEVEL_API",
        "historical solver-torque authority field changed",
    )

    _require(ag.get("schema") == AG_SCHEMA, "A-G receipt schema mismatch")
    _require(ag.get("mode") == "A_I_ACCEPTANCE", "A-G receipt mode mismatch")
    ag_a = _mapping(_mapping(ag.get("A"), label="A receipt").get("summary"), label="A summary")
    ag_b = _mapping(_mapping(ag.get("B"), label="B receipt").get("summary"), label="B summary")
    ag_c = _mapping(_mapping(ag.get("C"), label="C receipt").get("summary"), label="C summary")
    ag_e = _mapping(_mapping(ag.get("E"), label="E receipt").get("summary"), label="E summary")
    ag_f = _mapping(ag.get("F"), label="F summary")
    ag_g = _mapping(_mapping(ag.get("G"), label="G receipt").get("summary"), label="G summary")
    for label, value in (("A", ag_a), ("B", ag_b), ("C", ag_c), ("G", ag_g)):
        _require(value.get("passed") is True, f"A-G {label} summary is not PASS")
    _require(ag_e.get("status") == "PASS" and ag_e.get("passed") is True, "A-G E summary is not PASS")
    _require(ag_f.get("passed") is True, "A-G F summary is not PASS")

    _require(hi.get("schema") == HI_SCHEMA, "H/I receipt schema mismatch")
    _require(hi.get("status") == "RUNTIME_VERIFIED", "H/I receipt is not runtime verified")
    p0 = _mapping(hi.get("p0_default_off"), label="p0 default-off receipt")
    p1 = _mapping(hi.get("p1_h_production_reset"), label="p1 H receipt")
    _require(p0.get("status") == "PASS", "historical I default-off parity is not PASS")
    _require(p1.get("status") == "PASS", "historical H reset persistence is not PASS")
    return {
        "old_final": rel_path(OLD_FINAL),
        "a_g": rel_path(AG_RECEIPT),
        "h_i": rel_path(HI_RECEIPT),
        "acceptance": {field: old_acceptance[field] for field in expected_acceptance},
        "facts": {
            "A": ag_a["passed"],
            "B": ag_b["passed"],
            "C": ag_c["passed"],
            "E": ag_e["passed"],
            "F": ag_f["passed"],
            "G": ag_g["passed"],
            "H": p1["status"] == "PASS",
            "I": p0["status"] == "PASS",
        },
    }


def _validate_owner() -> dict[str, str]:
    owner_path = require_file(OWNER_DECISION, label="Owner D-v2 decision")
    text = owner_path.read_text(encoding="utf-8")
    _require("OWNER_GATE_REVISION_D_V2" in text, "Owner decision does not authorize D-v2")
    _require("V24_FRICTION_MODEL_VALID_BEHAVIORAL" in text, "Owner decision lacks behavioral typed result")
    _require("V24_FRICTION_ENERGY_ACCOUNTING_FAIL" in text, "Owner decision lacks D-v2 fail typed result")
    return {"path": rel_path(owner_path), "decision": "OWNER_GATE_REVISION_D_V2 + CONTINUE_FROM_P2"}


_D_V2_READBACK_FIELDS = {
    "static_effort_nm",
    "dynamic_effort_nm",
    "viscous_coefficient_nm_s_per_rad",
    "stiffness_nm_per_rad",
    "damping_nm_s_per_rad",
    "theta_ref_rad",
    "velocity_target_rad_s",
}
_D_V2_CLEANUP_MATCH_FIELDS = {
    "joint_pos",
    "joint_vel",
    "joint_effort_target",
    "joint_pos_target",
    "joint_vel_target",
    "joint_stiffness",
    "joint_damping",
    "joint_effort_limits",
    "joint_friction_coeff",
    "joint_dynamic_friction_coeff",
    "joint_viscous_friction_coeff",
}
_D_V2_CHECK_FIELDS = {
    "finite",
    "readbacks_match",
    "motion_angle",
    "motion_velocity",
    "D_nonnegative_within_tol",
    "dD_nonnegative_within_tol",
    "D_final_above_tol",
}


def _same_number(actual: Any, expected: float, *, label: str) -> None:
    # D-v2 readback/state continuity is a configured exact-value contract.
    value = _finite(actual, label=label)
    _require(value == expected, f"{label} disagrees with raw-row recomputation")


def _readback_scalar(value: Any, *, label: str) -> float:
    _require(isinstance(value, list) and len(value) == 1, f"{label} must be a one-row readback")
    row = value[0]
    _require(isinstance(row, list) and len(row) == 1, f"{label} must be a one-column readback")
    return _finite(row[0], label=label)


def _validate_trajectory_setup(
    trajectory: Mapping[str, Any], *, profile_name: str, sign: int, expected_profile: Mapping[str, float]
) -> bool:
    _require(trajectory.get("profile") == profile_name, "D-v2 trajectory profile mismatch")
    _require(trajectory.get("sign") == sign, "D-v2 trajectory sign mismatch")
    stationarity = _mapping(trajectory.get("stationarity"), label="D-v2 stationarity")
    _require(stationarity.get("steps") == 20, "D-v2 stationarity step count mismatch")
    stationarity_rows = stationarity.get("rows")
    _require(isinstance(stationarity_rows, list) and len(stationarity_rows) == 20, "D-v2 stationarity rows incomplete")
    for index, row in enumerate(stationarity_rows):
        row_map = _mapping(row, label="D-v2 stationarity row")
        _require(row_map.get("step") == index, "D-v2 stationarity step ordering mismatch")
        _finite(row_map.get("theta_rad"), label="D-v2 stationarity theta")
        _finite(row_map.get("omega_rad_s"), label="D-v2 stationarity omega")
    rewrite = _mapping(trajectory.get("exact_state_rewrite"), label="D-v2 exact state rewrite")
    _require(rewrite.get("theta_initial_rad") == 0.5, "D-v2 exact theta initial mismatch")
    _require(rewrite.get("omega_initial_rad_s") == 0.0, "D-v2 exact omega initial mismatch")
    _require(rewrite.get("matches") is True, "D-v2 exact state rewrite did not match")
    _same_number(rewrite.get("readback_theta_rad"), 0.5, label="D-v2 rewrite theta readback")
    _same_number(rewrite.get("readback_omega_rad_s"), 0.0, label="D-v2 rewrite omega readback")
    readbacks = _mapping(trajectory.get("readbacks"), label="D-v2 trajectory readbacks")
    matches = _mapping(readbacks.get("matches"), label="D-v2 readback matches")
    _require(set(matches) == _D_V2_READBACK_FIELDS, "D-v2 readback match fields are incomplete or expanded")
    _require(all(isinstance(value, bool) for value in matches.values()), "D-v2 readback matches must be boolean")
    requested = _mapping(readbacks.get("requested"), label="D-v2 requested readbacks")
    requested_profile = _mapping(requested.get("profile"), label="D-v2 requested friction profile")
    requested_expected = dict(expected_profile)
    requested_expected.update(
        {
            "stiffness_nm_per_rad": 6.0,
            "damping_nm_s_per_rad": 0.0,
            "theta_ref_rad": 0.5,
            "velocity_target_rad_s": 0.0,
        }
    )
    for field, expected in expected_profile.items():
        _same_number(requested_profile.get(field), expected, label=f"D-v2 requested {field}")
    _same_number(requested.get("stiffness_nm_per_rad"), 6.0, label="D-v2 requested stiffness")
    _same_number(requested.get("damping_nm_s_per_rad"), 0.0, label="D-v2 requested damping")
    _same_number(requested.get("theta_ref_rad"), 0.5, label="D-v2 requested theta_ref")
    _same_number(requested.get("velocity_target_rad_s"), 0.0, label="D-v2 requested velocity target")
    actual = _mapping(readbacks.get("readback"), label="D-v2 actual readbacks")
    _require(set(actual) == _D_V2_READBACK_FIELDS, "D-v2 actual readback fields are incomplete or expanded")
    actual_values = {
        field: _readback_scalar(actual.get(field), label=f"D-v2 actual {field}")
        for field in _D_V2_READBACK_FIELDS
    }
    recomputed_matches = {
        field: actual_values[field] == expected
        for field, expected in requested_expected.items()
    }
    _require(dict(matches) == recomputed_matches, "D-v2 supplied readback matches contradict numeric evidence")
    return all(recomputed_matches.values())


def _recompute_rows(
    trajectory: Mapping[str, Any], *, profile_name: str, sign: int, expected_profile: Mapping[str, float]
) -> dict[str, Any]:
    readbacks_match = _validate_trajectory_setup(
        trajectory, profile_name=profile_name, sign=sign, expected_profile=expected_profile
    )
    rows = trajectory.get("rows")
    _require(isinstance(rows, list) and len(rows) == 200, "D-v2 trajectory must contain exactly 200 raw intervals")
    previous_d = 0.0
    max_signed_angle = -math.inf
    max_signed_velocity = -math.inf
    noise_step = 0.0
    noise_cumulative = 0.0
    previous_theta_next: float | None = None
    previous_omega_next: float | None = None
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row, label="D-v2 raw accounting row")
        _require(row.get("step") == index, "D-v2 raw accounting step ordering mismatch")
        phase = "command" if index < 100 else "coast"
        phase_step = index if index < 100 else index - 100
        expected_tau = sign * 2.0 if phase == "command" else 0.0
        _require(row.get("phase") == phase, "D-v2 raw accounting phase mismatch")
        _require(row.get("phase_step") == phase_step, "D-v2 raw accounting phase-step mismatch")
        _same_number(row.get("tau_cmd_nm"), expected_tau, label="D-v2 raw command effort")
        theta = _finite(row.get("theta_rad"), label="D-v2 raw theta")
        omega = _finite(row.get("omega_rad_s"), label="D-v2 raw omega")
        theta_next = _finite(row.get("theta_next_rad"), label="D-v2 raw theta_next")
        omega_next = _finite(row.get("omega_next_rad_s"), label="D-v2 raw omega_next")
        if index == 0:
            _same_number(theta, 0.5, label="D-v2 first raw theta")
            _same_number(omega, 0.0, label="D-v2 first raw omega")
        else:
            _require(theta == previous_theta_next, "D-v2 raw rows contain an omitted theta state jump")
            _require(omega == previous_omega_next, "D-v2 raw rows contain an omitted omega state jump")
        energy = 0.5 * 36.1 * omega**2 + 0.5 * 6.0 * (theta - 0.5) ** 2
        energy_next = 0.5 * 36.1 * omega_next**2 + 0.5 * 6.0 * (theta_next - 0.5) ** 2
        work = expected_tau * (theta_next - theta)
        delta_energy = energy_next - energy
        delta_dissipation = work - delta_energy
        cumulative_dissipation = previous_d + delta_dissipation
        _same_number(row.get("E_j"), energy, label="D-v2 raw E_j")
        _same_number(row.get("E_next_j"), energy_next, label="D-v2 raw E_next_j")
        _same_number(row.get("dW_j"), work, label="D-v2 raw dW_j")
        _same_number(row.get("delta_E_j"), delta_energy, label="D-v2 raw delta_E_j")
        _same_number(row.get("dD_j"), delta_dissipation, label="D-v2 raw dD_j")
        _same_number(row.get("D_j"), cumulative_dissipation, label="D-v2 raw D_j")
        previous_d = cumulative_dissipation
        previous_theta_next = theta_next
        previous_omega_next = omega_next
        noise_step = max(noise_step, abs(delta_dissipation))
        noise_cumulative = max(noise_cumulative, abs(cumulative_dissipation))
        max_signed_angle = max(max_signed_angle, sign * (theta_next - 0.5))
        max_signed_velocity = max(max_signed_velocity, sign * omega_next)
    _same_number(trajectory.get("noise_step_j"), noise_step, label="D-v2 trajectory noise_step_j")
    _same_number(trajectory.get("noise_cumulative_j"), noise_cumulative, label="D-v2 trajectory noise_cumulative_j")
    _same_number(trajectory.get("D_final_j"), previous_d, label="D-v2 trajectory D_final_j")
    motion = _mapping(trajectory.get("motion"), label="D-v2 trajectory motion")
    _same_number(motion.get("theta0_rad"), 0.5, label="D-v2 trajectory theta0")
    _same_number(motion.get("max_signed_angle_rad"), max_signed_angle, label="D-v2 trajectory signed angle")
    _same_number(motion.get("max_signed_velocity_rad_s"), max_signed_velocity, label="D-v2 trajectory signed velocity")
    _require(trajectory.get("finite") is True, "D-v2 trajectory finite metadata contradicts raw rows")
    return {
        "readbacks_match": readbacks_match,
        "noise_step_j": noise_step,
        "noise_cumulative_j": noise_cumulative,
        "D_final_j": previous_d,
        "max_signed_angle_rad": max_signed_angle,
        "max_signed_velocity_rad_s": max_signed_velocity,
        "rows": rows,
    }


def _validate_d_v2(d_v2: Mapping[str, Any]) -> dict[str, Any]:
    _require(d_v2.get("schema") == D_V2_PRODUCER_SCHEMA, "D-v2 producer schema mismatch")
    _require(d_v2.get("mode") == D_V2_MODE, "D-v2 producer mode mismatch")
    _require(d_v2.get("device") == "cuda:0", "D-v2 device must be cuda:0")
    _require(d_v2.get("probe_seed") == 24017, "D-v2 seed must be 24017")
    model = _mapping(d_v2.get("model"), label="D-v2 model")
    _require(model.get("inertia_formula") == "(1/3)*120*0.95^2=36.1 kg*m^2", "D-v2 inertia formula mismatch")
    _require(model.get("inertia_authority") == "MODELED_FROM_PARAMS_UNIFORM_PANEL_EDGE", "D-v2 inertia authority mismatch")
    _require("default_inertia" not in model and model.get("inertia_kg_m2") == 36.1, "D-v2 inertia model mismatch")
    spring = _mapping(d_v2.get("spring_and_targets"), label="D-v2 spring")
    for field, expected in (("stiffness_nm_per_rad", 6.0), ("damping_nm_s_per_rad", 0.0), ("theta_ref_rad", 0.5), ("theta_initial_rad", 0.5), ("velocity_target_rad_s", 0.0)):
        _require(spring.get(field) == expected, f"D-v2 spring field {field} mismatch")
    _require(spring.get("surface") == "HIGH_LEVEL_RAD_SURFACE" and spring.get("target_dependency") == "NONE", "D-v2 target surface mismatch")
    trajectory_contract = _mapping(d_v2.get("trajectory_contract"), label="D-v2 trajectory contract")
    _require(tuple(trajectory_contract.get("signs", ())) == (-1, 1), "D-v2 signs mismatch")
    for field, expected in (("stationarity_steps", 20), ("command_steps", 100), ("coast_steps", 100), ("command_effort_nm", 2.0), ("dt_s", 0.005)):
        _require(trajectory_contract.get(field) == expected, f"D-v2 trajectory field {field} mismatch")
    expected_authorities = {
        "solver_friction_torque_component": "UNAVAILABLE_NOT_USED",
        "actual_generalized_torque_claim": False,
        "friction_params": "MODELED_FROM_PARAMS",
        "modeled_torque": "MODELED_FROM_PARAMS",
        "command_work": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
        "state": "HIGH_LEVEL_ARTICULATION_DATA",
        "stiffness": "CONFIGURED_HIGH_LEVEL_RAD_SURFACE_READBACK",
    }
    _require(dict(_mapping(d_v2.get("authority_labels"), label="D-v2 authority labels")) == expected_authorities, "D-v2 authority labels mismatch")
    formula = _mapping(d_v2.get("accounting_formula"), label="D-v2 accounting formula")
    _require(formula.get("dW") == "tau_cmd*(theta_next-theta)", "D-v2 work formula mismatch")
    _require(formula.get("E") == "0.5*I_model*omega^2+0.5*k*(theta-theta_ref)^2", "D-v2 energy formula mismatch")
    _require(formula.get("dD") == "dW-(E_next-E)", "D-v2 dissipation formula mismatch")

    calibration = _mapping(d_v2.get("calibration"), label="D-v2 calibration")
    _require(calibration.get("profile") == "F00" and calibration.get("completed_before_tolerance") is True, "D-v2 calibration metadata mismatch")
    _require(calibration.get("trajectory_signs") == [-1, 1], "D-v2 calibration trajectory metadata mismatch")
    calibration_trajectories = calibration.get("trajectories")
    _require(isinstance(calibration_trajectories, list) and len(calibration_trajectories) == 2, "D-v2 calibration trajectories incomplete")
    calibration_signs = [trajectory.get("sign") for trajectory in calibration_trajectories if isinstance(trajectory, Mapping)]
    _require(calibration_signs == [-1, 1] and set(calibration_signs) == {-1, 1}, "D-v2 calibration signs are not exactly distinct")
    calibration_truth = []
    for sign, trajectory in zip(calibration_signs, calibration_trajectories):
        calibration_truth.append(
            _recompute_rows(
                _mapping(trajectory, label="D-v2 calibration trajectory"),
                profile_name="F00",
                sign=sign,
                expected_profile={"static_effort_nm": 0.0, "dynamic_effort_nm": 0.0, "viscous_coefficient_nm_s_per_rad": 0.0},
            )
        )
    noise_step = max(item["noise_step_j"] for item in calibration_truth)
    noise_cumulative = max(item["noise_cumulative_j"] for item in calibration_truth)
    tol_step = 2.0 * noise_step + 1.0e-12
    tol_cumulative = 2.0 * noise_cumulative + 1.0e-12
    tolerance = _mapping(d_v2.get("tolerance_freeze"), label="D-v2 tolerance freeze")
    tolerance_path = absolute(str(tolerance.get("tolerance_path", ""))).resolve()
    _require(tolerance_path == D_V2_TOLERANCE.resolve(), "D-v2 tolerance path is not canonical")
    standalone = _mapping(read_json(tolerance_path, label="D-v2 tolerance freeze"), label="D-v2 tolerance freeze file")
    _require(dict(standalone) == dict(tolerance), "standalone and embedded tolerance freeze differ")
    for source in (tolerance, standalone):
        _require(source.get("schema") == D_V2_TOLERANCE_SCHEMA and source.get("status") == "FROZEN", "D-v2 tolerance metadata mismatch")
        _require(source.get("mode") == D_V2_MODE and source.get("device") == "cuda:0" and source.get("probe_seed") == 24017, "D-v2 tolerance identity metadata mismatch")
        _require(source.get("profile") == "F00" and source.get("trajectory_signs") == [-1, 1], "D-v2 tolerance trajectory metadata mismatch")
        _require(source.get("calibration_trajectory_count") == 2, "D-v2 tolerance trajectory count mismatch")
        _require(source.get("calibration_trajectories") == calibration_trajectories, "D-v2 tolerance calibration rows differ")
        _same_number(source.get("noise_step_j"), noise_step, label="D-v2 tolerance noise_step_j")
        _same_number(source.get("noise_cumulative_j"), noise_cumulative, label="D-v2 tolerance noise_cumulative_j")
        _same_number(source.get("tol_step_j"), tol_step, label="D-v2 tolerance tol_step_j")
        _same_number(source.get("tol_cumulative_j"), tol_cumulative, label="D-v2 tolerance tol_cumulative_j")
        _require(source.get("multiplier") == 2.0 and source.get("floor_j") == 1.0e-12, "D-v2 tolerance constants mismatch")
        _require(source.get("freeze_formula") == "tol_step=2*noise_step+floor; tol_cum=2*noise_cumulative+floor", "D-v2 tolerance formula mismatch")
        _require(source.get("source") == "both fresh F00 calibration trajectories only" and source.get("f10_recompute_forbidden") is True, "D-v2 tolerance source metadata mismatch")

    f10 = _mapping(d_v2.get("f10"), label="D-v2 F10")
    _require(f10.get("profile") == "F10" and f10.get("trajectory_signs") == [-1, 1], "D-v2 F10 metadata mismatch")
    per_sign = f10.get("per_sign")
    _require(isinstance(per_sign, list) and len(per_sign) == 2, "D-v2 F10 per-sign evidence incomplete")
    f10_signs = [item.get("sign") for item in per_sign if isinstance(item, Mapping)]
    _require(f10_signs == [-1, 1] and set(f10_signs) == {-1, 1}, "D-v2 F10 signs are not exactly distinct")
    expected_profile = {"static_effort_nm": 1.0, "dynamic_effort_nm": 0.75, "viscous_coefficient_nm_s_per_rad": 0.0}
    expected_results = []
    for sign, item in zip(f10_signs, per_sign):
        row = _mapping(item, label="D-v2 F10 per-sign row")
        trajectory = _mapping(row.get("trajectory"), label="D-v2 F10 trajectory")
        truth = _recompute_rows(trajectory, profile_name="F10", sign=sign, expected_profile=expected_profile)
        checks = {
            "finite": True,
            "readbacks_match": truth["readbacks_match"],
            "motion_angle": truth["max_signed_angle_rad"] >= 1.0e-4,
            "motion_velocity": truth["max_signed_velocity_rad_s"] >= 1.0e-3,
            "D_nonnegative_within_tol": all(row_data["D_j"] >= -tol_cumulative for row_data in truth["rows"]),
            "dD_nonnegative_within_tol": all(row_data["dD_j"] >= -tol_step for row_data in truth["rows"]),
            "D_final_above_tol": truth["D_final_j"] > tol_cumulative,
        }
        _require(set(_mapping(row.get("checks"), label="D-v2 F10 checks")) == _D_V2_CHECK_FIELDS, "D-v2 F10 checks incomplete")
        _require(all(isinstance(value, bool) for value in _mapping(row.get("checks"), label="D-v2 F10 checks").values()), "D-v2 F10 checks must be boolean")
        _require(dict(row["checks"]) == checks, "D-v2 F10 check map contradicts raw rows")
        verdict = "PASS" if all(checks.values()) else "FAIL"
        _require(row.get("scientific_verdict") == verdict, "D-v2 per-sign verdict contradicts raw rows")
        expected_results.append({"sign": sign, "scientific_verdict": verdict, "checks": checks})
    overall_pass = all(item["scientific_verdict"] == "PASS" for item in expected_results)
    _require(f10.get("overall_pass") is overall_pass, "D-v2 overall_pass contradicts raw rows")
    _require(f10.get("tolerance_recomputed_from_f10") is False, "D-v2 tolerance was recomputed from F10")
    expected_status = "PASS" if overall_pass else "FAIL"
    _require(d_v2.get("status") == expected_status and d_v2.get("overall_status") == expected_status, "D-v2 top-level status contradicts raw rows")
    _require(d_v2.get("scientific_verdict") == expected_status, "D-v2 scientific verdict contradicts raw rows")
    cleanup = _mapping(d_v2.get("cleanup"), label="D-v2 cleanup")
    cleanup_matches = _mapping(cleanup.get("matches"), label="D-v2 cleanup matches")
    _require(set(cleanup_matches) == _D_V2_CLEANUP_MATCH_FIELDS, "D-v2 cleanup match-field set is incomplete or expanded")
    _require(all(value is True for value in cleanup_matches.values()), "D-v2 cleanup readback did not pass")
    friction_cleanup = _mapping(cleanup.get("friction"), label="D-v2 friction cleanup")
    friction_matches = _mapping(friction_cleanup.get("matches"), label="D-v2 friction cleanup matches")
    _require(set(friction_matches) == {"joint_friction_coeff", "joint_dynamic_friction_coeff", "joint_viscous_friction_coeff"}, "D-v2 friction cleanup match fields mismatch")
    _require(all(value is True for value in friction_matches.values()), "D-v2 friction cleanup did not pass")
    return {"receipt": rel_path(D_V2_RECEIPT), "tolerance": rel_path(D_V2_TOLERANCE), "overall_pass": overall_pass, "per_sign": expected_results}


def adjudicate(
    *,
    historical_final: Path = OLD_FINAL,
    d_v2_receipt: Path = D_V2_RECEIPT,
    output: Path = OUTPUT,
) -> Path:
    historical_final = absolute(historical_final).resolve()
    d_v2_receipt = absolute(d_v2_receipt).resolve()
    output = absolute(output).resolve()
    _require(historical_final == OLD_FINAL.resolve(), "historical final path must remain the immutable R1 receipt")
    _require(d_v2_receipt == D_V2_RECEIPT.resolve(), "D-v2 receipt path must remain canonical")
    _require(output.parent == OUTPUT_ROOT.resolve() and output.name == OUTPUT.name, "D-v2 adjudication output path is not canonical")
    old = _mapping(read_json(historical_final, label="historical final receipt"), label="historical final receipt")
    ag = _mapping(read_json(AG_RECEIPT, label="A-G receipt"), label="A-G receipt")
    hi = _mapping(read_json(HI_RECEIPT, label="H/I receipt"), label="H/I receipt")
    d_v2 = _mapping(read_json(d_v2_receipt, label="D-v2 receipt"), label="D-v2 receipt")
    historical = _validate_historical(old, ag, hi)
    owner = _validate_owner()
    d_v2_summary = _validate_d_v2(d_v2)
    d_pass = d_v2_summary["overall_pass"]
    typed_result = "V24_FRICTION_MODEL_VALID_BEHAVIORAL" if d_pass else "V24_FRICTION_ENERGY_ACCOUNTING_FAIL"
    payload = {
        "schema": D_V2_ADJUDICATION_SCHEMA,
        "status": "FINAL_ADJUDICATION",
        "typed_result": typed_result,
        "owner_authority": owner,
        "historical": historical,
        "d_v2": d_v2_summary,
        "authority_boundary": {
            "solver_friction_torque_component": "UNAVAILABLE_NOT_USED",
            "actual_generalized_torque_claim": False,
            "friction_params": "MODELED_FROM_PARAMS",
            "modeled_torque": "MODELED_FROM_PARAMS",
            "command_work": "COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE",
            "state": "HIGH_LEVEL_ARTICULATION_DATA",
            "stiffness": "CONFIGURED_HIGH_LEVEL_RAD_SURFACE_READBACK",
        },
        "acceptance": {
            "A_breakaway": "PASS",
            "B_kinetic_plateau": "PASS",
            "C_distinct_from_damping": "PASS",
            "D_v2_energy_accounting": "PASS" if d_pass else "FAIL",
            "E_chatter": "PASS",
            "F_timestep": "PASS_QUALITATIVE_ONLY",
            "G_orthogonality": "PASS",
            "H_reset_persistence": "PASS",
            "I_legacy_default_off_parity": "PASS",
        },
        "admission": {
            "P2": bool(d_pass),
            "P3": bool(d_pass),
            "owner_decision_required": False,
            "reason": "D-v2 behavioral energy accounting is the Owner-revised P1 gate",
        },
    }
    return write_json(output, payload)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-final", type=Path, default=OLD_FINAL)
    parser.add_argument("--d-v2-receipt", type=Path, default=D_V2_RECEIPT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    adjudicate(historical_final=args.historical_final, d_v2_receipt=args.d_v2_receipt, output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
