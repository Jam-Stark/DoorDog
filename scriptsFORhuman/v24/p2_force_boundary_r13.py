"""Owner-directed r13 force-boundary calibration with Rule16 and typed E1 floors."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

import yaml

try:
    from ._v24_common import REPO_ROOT, absolute, rel_path, require_file
    from .p2_force_boundary import _run_policy_only_first_episode
except ImportError:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v24._v24_common import REPO_ROOT, absolute, rel_path, require_file
    from scriptsFORhuman.v24.p2_force_boundary import _run_policy_only_first_episode


SCHEMA = "a2_piper_v24_p2_force_boundary_r13_v1"
CONFIG = REPO_ROOT / "gr00t/rl/config/ablation/wbmanip/base_v24_p2_force_boundary_r13.yaml"
OWNER_DECISION = REPO_ROOT / "scriptsFORhuman/v24/DoorDog_v24_owner_decision_friction_domain_escalation_20260818.md"
P1_RECEIPT = REPO_ROOT / "logs_eval/base_v24/p1/friction_backend/p1_lite_domain_escalation_r13_gpu0/P1_LITE_DOMAIN_ESCALATION_RECEIPT.json"
ARTIFACT_ROOT = REPO_ROOT / "logs_eval/base_v24/p2/force_boundary/r13"
CHECKPOINT = "logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt"
PROFILES = ("P02", "P05", "P10", "P20")
PROFILE_PARAMETERS = {
    "P02": (2.0, 1.5, 0.0),
    "P05": (5.0, 3.75, 0.0),
    "P10": (10.0, 7.5, 0.0),
    "P20": (20.0, 15.0, 0.0),
}
CAPS = (100.0, 60.0, 40.0, 30.0, 25.0, 20.0)
SCENARIOS = tuple(f"S{index:02d}" for index in range(16))
DEMAND_FLOOR_NM = 2.0
CAPACITY_FLOOR_NM = 2.0

FREEZE_ARTIFACT = "V24_P2_R13_PARAMETER_AND_E1_FREEZE.json"
F3_REGISTRATION_ARTIFACT = "V24_P2_R13_F3_PRIME_REGISTRATION.json"
VITAL_ROWS_ARTIFACT = "vitals/P2_SHAM_ROWS.jsonl"
VITAL_RECEIPT_ARTIFACT = "vitals/P2_SHAM_VITALS_RECEIPT.json"
SMOKE_ROWS_ARTIFACT = "smoke/P2_SMOKE_ROWS.jsonl"
SMOKE_RECEIPT_ARTIFACT = "smoke/P2_SMOKE_RECEIPT.json"
CALIBRATION_ROWS_ARTIFACT = "calibration/P2_CALIBRATION_ROWS.jsonl"
CALIBRATION_RECEIPT_ARTIFACT = "calibration/P2_CALIBRATION_RECEIPT.json"
GRADIENT_ARTIFACT = "V24_P2_R13_GRADIENT_ADMISSION.json"
LADDER_ARTIFACT = "V24_P2_R13_LADDER_FREEZE.json"
E_REGION_ARTIFACT = "V24_P2_R13_E_REGION_FREEZE.json"


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(require_file(path, label="r13 prerequisite").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a mapping")
    return payload


def _read_rows(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in require_file(path, label="r13 rows").read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{path} contains a non-mapping row")
    return rows


def _write_json(root: Path, relative: str, payload: Mapping[str, Any]) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"r13 artifact is append-only and already exists: {target}") from exc
    return target


def _write_rows(root: Path, relative: str, rows: Sequence[Mapping[str, Any]]) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeError(f"r13 artifact is append-only and already exists: {target}") from exc
    return target


def _load_contract(path: Path = CONFIG) -> dict[str, Any]:
    target = absolute(path).resolve()
    if target != CONFIG.resolve():
        raise ValueError("r13 P2 requires the dedicated canonical overlay")
    payload = yaml.safe_load(require_file(target, label="r13 P2 overlay").read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("v24_schema") != SCHEMA:
        raise ValueError("r13 P2 overlay schema mismatch")
    if payload.get("v24_plan_id") != "base_v24_force_boundary_R13_DOMAIN_ESCALATION":
        raise ValueError("r13 P2 plan id mismatch")
    if payload.get("v24_owner_decision") != rel_path(OWNER_DECISION):
        raise ValueError("r13 P2 overlay must cite the controlling Owner decision")
    require_file(OWNER_DECISION, label="r13 Owner decision")
    p2 = payload.get("v24_p2")
    if not isinstance(p2, Mapping) or p2.get("checkpoint") != CHECKPOINT or p2.get("checkpoint_load_mode") != "selected_policy_only":
        raise ValueError("r13 P2 checkpoint contract mismatch")
    if p2.get("calibration_seed") != 24041 or p2.get("heldout_seed") != 24042:
        raise ValueError("r13 P2 seeds mismatch")
    profiles = p2.get("friction_profiles")
    if not isinstance(profiles, Mapping) or tuple(profiles) != ("F00", *PROFILES):
        raise ValueError("r13 P2 friction profile order mismatch")
    for name, expected in PROFILE_PARAMETERS.items():
        item = profiles[name]
        actual = tuple(_finite(item.get(key), label=f"{name}.{key}") for key in ("static_effort_nm", "dynamic_effort_nm", "viscous_coefficient_nm_s_per_rad"))
        if actual != expected:
            raise ValueError(f"r13 P2 profile {name} mismatch")
    if tuple(p2.get("calibration_profiles", ())) != PROFILES or tuple(float(value) for value in p2.get("arm_caps_nm", ())) != CAPS:
        raise ValueError("r13 P2 calibration grid mismatch")
    semantics = p2.get("e1_semantics")
    if not isinstance(semantics, Mapping) or semantics.get("revision") != "R13_DOMAIN_ESCALATION" or semantics.get("demand_floor_nm") != DEMAND_FLOOR_NM or semantics.get("capacity_floor_nm") != CAPACITY_FLOOR_NM or semantics.get("lambda_denominator_rule") != "INVALIDATE_BELOW_FLOOR_NO_NUMERIC_CLAMP":
        raise ValueError("r13 E1 semantics mismatch")
    f3 = p2.get("f3_prime")
    if not isinstance(f3, Mapping) or f3.get("registered_before_calibration") is not True or f3.get("episodes_per_cell") != 32 or f3.get("sustained_e1_min_per_cell") != 8:
        raise ValueError("r13 F3-prime registration mismatch")
    artifacts = p2.get("artifacts")
    if not isinstance(artifacts, Mapping) or artifacts.get("root") != rel_path(ARTIFACT_ROOT) or artifacts.get("append_only") is not True:
        raise ValueError("r13 artifact contract mismatch")
    return {"path": target, "payload": payload, "p2": p2}


def build_plan(path: Path = CONFIG) -> dict[str, Any]:
    contract = _load_contract(path)
    return {
        "schema": SCHEMA,
        "status": "REGISTERED_BEFORE_R13_DATA",
        "owner_decision": rel_path(OWNER_DECISION),
        "p1_magnitude_receipt": rel_path(P1_RECEIPT),
        "artifact_root": rel_path(ARTIFACT_ROOT),
        "runtime_order": ["prepare", "vitals", "smoke", "calibrate", "gradient"],
        "calibration_topology": {"profiles": list(PROFILES), "caps_nm": list(CAPS), "scenarios": 16, "rows": 384},
        "e1_semantics": dict(contract["p2"]["e1_semantics"]),
        "gradient_gate": dict(contract["p2"]["gradient_gate"]),
        "ladder_gate": dict(contract["p2"]["ladder_gate"]),
        "f3_prime": dict(contract["p2"]["f3_prime"]),
        "axis_terminal": "V24_FRICTION_AXIS_NONDISCRIMINATIVE",
        "authority": {"door_friction": "MODELED_FROM_PARAMS", "solver_applied": False, "capacity_lambda": "ESTIMATE_ONLY_DIRECTIONAL_MARGIN"},
    }


def _runtime_rows(
    contract: Mapping[str, Any], root: Path, *, seed: int, profile: str, cap_nm: float,
    num_envs: int, scenarios: Sequence[str], continuity_id: str, control_steps: int | None = None,
) -> list[dict[str, Any]]:
    return _run_policy_only_first_episode(
        config_path=contract["path"], device="cuda:0", seed=seed, profile=profile, cap_nm=cap_nm,
        mode="HI_FULL", num_envs=num_envs, scenario_ids=scenarios, continuity_id=continuity_id,
        control_steps=control_steps, temp_root=root / "runtime_scratch",
    )


def _validate_rows(
    rows: Sequence[Mapping[str, Any]], *, profiles: Sequence[str], caps: Sequence[float],
    scenarios: Sequence[str], seed: int, continuity: str,
) -> list[dict[str, Any]]:
    expected = {(profile, float(cap), scenario) for profile in profiles for cap in caps for scenario in scenarios}
    actual: set[tuple[str, float, str]] = set()
    normalized: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        if not isinstance(source, Mapping):
            raise TypeError(f"r13 row {index} must be a mapping")
        row = dict(source)
        profile = row.get("profile")
        cap = _finite(row.get("cap_nm"), label=f"row{index}.cap")
        scenario = row.get("scenario_id")
        identity = (profile, cap, scenario)
        if identity not in expected or identity in actual or row.get("seed") != seed or row.get("continuity_id") != continuity or row.get("mode") != "HI_FULL":
            raise ValueError(f"r13 row {index} identity mismatch or duplicate: {identity!r}")
        actual.add(identity)
        if row.get("window_transition_count") != 25 or row.get("e1_semantics_revision") != "R13_DOMAIN_ESCALATION":
            raise ValueError(f"r13 row {index} window/semantics mismatch")
        if row.get("demand_floor_nm") != DEMAND_FLOOR_NM or row.get("capacity_floor_nm") != CAPACITY_FLOOR_NM:
            raise ValueError(f"r13 row {index} floor mismatch")
        if not isinstance(row.get("capacity_collapsed_window"), bool) or row.get("capacity_window_status") not in {"CAPACITY_COLLAPSED_WINDOW", "CAPACITY_VALID_WINDOW"}:
            raise ValueError(f"r13 row {index} capacity status missing")
        if row["capacity_collapsed_window"] is not (row["capacity_window_status"] == "CAPACITY_COLLAPSED_WINDOW"):
            raise ValueError(f"r13 row {index} capacity status contradiction")
        if row["capacity_collapsed_window"]:
            if row.get("lambda_median") is not None or row.get("lambda") is not None or row.get("e1_admission_status") != "CAPACITY_COLLAPSED_WINDOW":
                raise ValueError(f"r13 row {index} collapsed capacity entered lambda admission")
        elif row.get("model_source_unavailable") is False and row.get("model_valid") is True:
            if _finite(row.get("tau_available_directional_median_nm"), label=f"row{index}.tau_available") < CAPACITY_FLOOR_NM:
                raise ValueError(f"r13 row {index} admitted capacity is below floor")
            _finite(row.get("lambda_median"), label=f"row{index}.lambda")
        vitals = row.get("parameter_vitals")
        if not isinstance(vitals, Mapping) or vitals.get("solver_applied") is not False:
            raise ValueError(f"r13 row {index} parameter vitals missing")
        door = vitals.get("door_friction")
        if not isinstance(door, Mapping) or door.get("authority") != "MODELED_FROM_PARAMS" or door.get("solver_applied") is not False:
            raise ValueError(f"r13 row {index} door authority mismatch")
        expected_profile = (0.0, 0.0, 0.0) if profile == "F00" else PROFILE_PARAMETERS[profile]
        expected_map = dict(zip(("static_friction_nm", "dynamic_friction_nm", "viscous_friction_nm_s_per_rad"), expected_profile))
        if door.get("requested") != expected_map or door.get("readback") != expected_map or door.get("contract") != expected_map:
            raise ValueError(f"r13 row {index} friction requested/readback/contract mismatch")
        normalized.append(row)
    if actual != expected:
        raise ValueError(f"r13 rows are incomplete: missing={sorted(expected - actual)[:3]!r}")
    return normalized


def _vitals_receipt(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    stable = sum(row.get("stable_grasp") is True for row in rows)
    stage = sum(row.get("window_stage_reach_valid") is True for row in rows)
    parameters = sum(isinstance(row.get("parameter_vitals"), Mapping) for row in rows)
    passed = stable >= 14 and stage == 16 and parameters == 16
    return {
        "schema": "a2_piper_v24_p2_r13_rule16_vitals_v1", "status": "PASS_VALID_MEASUREMENT_ADMISSION" if passed else "FAIL_INVALID_MEASUREMENT",
        "rule16": True, "sham_profile": "F00", "stable_grasp": stable, "stable_grasp_required": 14,
        "stage_reach": stage, "parameter_vitals": parameters, "envs": 16,
        "continuity_id": "VITALS_R13_FIXED_SHAM", "owner_decision": rel_path(OWNER_DECISION),
    }


def _eligible(row: Mapping[str, Any]) -> bool:
    return (
        row.get("valid") is True
        and row.get("model_valid") is True
        and row.get("stable_grasp") is True
        and row.get("window_selection_valid") is True
        and row.get("model_source_unavailable") is False
        and row.get("grasp_source_unavailable") is False
        and row.get("capacity_collapsed_window") is False
        and row.get("demand_floor_pass") is True
        and _finite(row.get("tau_req_median_nm"), label="tau_req") >= DEMAND_FLOOR_NM
        and _finite(row.get("tau_available_directional_median_nm"), label="tau_available") >= CAPACITY_FLOOR_NM
        and isinstance(row.get("lambda_median"), (int, float))
        and math.isfinite(float(row["lambda_median"]))
    )


def _adjudicate(rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    progress_medians = {profile: median(float(row["progress_recovery_delta_rad"]) for row in rows if row["profile"] == profile) for profile in PROFILES}
    tau_medians = {profile: median(float(row["tau_req_median_nm"]) for row in rows if row["profile"] == profile) for profile in PROFILES}
    by_identity = {(row["cap_nm"], row["scenario_id"], row["profile"]): row for row in rows}
    tau_strict = 0
    progress_low_gt_high = 0
    for cap in CAPS:
        for scenario in SCENARIOS:
            matched = [by_identity[(cap, scenario, profile)] for profile in PROFILES]
            taus = [float(row["tau_req_median_nm"]) for row in matched]
            tau_strict += int(all(left < right for left, right in zip(taus, taus[1:])))
            progress_low_gt_high += int(float(matched[0]["progress_recovery_delta_rad"]) > float(matched[-1]["progress_recovery_delta_rad"]))
    gate = contract["p2"]["gradient_gate"]
    tau_medians_strict = all(tau_medians[left] < tau_medians[right] for left, right in zip(PROFILES, PROFILES[1:]))
    progress_nonincreasing = all(progress_medians[left] >= progress_medians[right] for left, right in zip(PROFILES, PROFILES[1:]))
    progress_span = progress_medians["P02"] - progress_medians["P20"]
    passed = (
        tau_medians_strict
        and tau_strict >= int(gate["matched_tau_strict_min"])
        and progress_nonincreasing
        and progress_span >= float(gate["low_high_progress_span_min_rad"])
        and progress_low_gt_high >= int(gate["matched_low_progress_gt_high_min"])
    )
    gradient = {
        "schema": "a2_piper_v24_p2_r13_gradient_admission_v1",
        "status": "PASS_TRUE_ESCALATED_GRADIENT" if passed else "V24_FRICTION_AXIS_NONDISCRIMINATIVE",
        "terminal": not passed, "owner_decision_required": not passed,
        "tau_required_medians_nm": tau_medians, "tau_required_medians_strictly_increasing": tau_medians_strict,
        "matched_tau_strict": tau_strict, "matched_tau_total": 96,
        "progress_medians_rad": progress_medians, "progress_medians_nonincreasing": progress_nonincreasing,
        "low_high_progress_span_rad": progress_span, "matched_low_progress_gt_high": progress_low_gt_high,
        "matched_low_high_total": 96, "registered_gate": dict(gate),
    }
    zone_counts: dict[str, dict[str, int]] = {profile: {"E0": 0, "E1": 0, "NEAR_E2": 0, "CAPACITY_COLLAPSED_WINDOW": 0, "INVALID": 0} for profile in PROFILES}
    cap_profile_e1: dict[str, dict[str, int]] = {str(int(cap)): {profile: 0 for profile in PROFILES} for cap in CAPS}
    cap_p02_e0: dict[str, int] = {str(int(cap)): 0 for cap in CAPS}
    for row in rows:
        profile = row["profile"]
        if row.get("capacity_collapsed_window") is True:
            zone_counts[profile]["CAPACITY_COLLAPSED_WINDOW"] += 1
            continue
        if not _eligible(row):
            zone_counts[profile]["INVALID"] += 1
            continue
        lam = float(row["lambda_median"])
        zone = "E0" if lam < 0.5 else "E1" if lam < 1.0 else "NEAR_E2"
        zone_counts[profile][zone] += 1
        if zone == "E1":
            cap_profile_e1[str(int(row["cap_nm"]))][profile] += 1
        if profile == "P02" and zone == "E0" and row.get("nonbinding") is True:
            cap_p02_e0[str(int(row["cap_nm"]))] += 1

    tau_hi = next((cap for cap in CAPS if cap_p02_e0[str(int(cap))] >= 8), None)
    primary_candidates = [cap for cap in CAPS if tau_hi is not None and cap < tau_hi and max(cap_profile_e1[str(int(cap))].values()) >= 8]
    marginal_candidates = [cap for cap in CAPS if tau_hi is not None and cap < tau_hi and max(cap_profile_e1[str(int(cap))].values()) >= 1]
    if primary_candidates:
        boundary = max(primary_candidates)
        basis = "CALIBRATION_E1_MIN8"
    elif marginal_candidates:
        boundary = max(marginal_candidates)
        basis = "MARGINAL_E1_PRESENT_FOR_F3_PRIME"
    else:
        boundary = None
        basis = "NO_E1_WINDOW"
    rescue = CAPS[CAPS.index(boundary) - 1] if boundary is not None and CAPS.index(boundary) > 0 else None
    ladder_valid = passed and tau_hi is not None and boundary is not None and rescue is not None
    ladder = {
        "schema": "a2_piper_v24_p2_r13_ladder_freeze_v1",
        "status": "EXECUTED" if ladder_valid else "NOT_ADMITTED",
        "tau_hi_nm": tau_hi, "tau_boundary_nm": boundary, "tau_rescue_nm": rescue,
        "selection_basis": basis, "cap_profile_e1_counts": cap_profile_e1, "cap_p02_nonbinding_e0_counts": cap_p02_e0,
        "f3_prime_required": ladder_valid, "registered_gate": dict(contract["p2"]["ladder_gate"]),
    }
    e_region = {
        "schema": "a2_piper_v24_p2_r13_e_region_freeze_v1",
        "status": "EXECUTED" if ladder_valid else "NOT_ADMITTED",
        "demand_floor_nm": DEMAND_FLOOR_NM, "capacity_floor_nm": CAPACITY_FLOOR_NM,
        "lambda_zones": {"E0": "lambda < 0.5", "E1": "0.5 <= lambda < 1.0", "NEAR_E2": "lambda >= 1.0"},
        "capacity_collapse": "CAPACITY_COLLAPSED_WINDOW; excluded from E1 and counted as RQ3 reach mediator",
        "zone_counts": zone_counts, "ladder": {"tau_hi_nm": tau_hi, "tau_boundary_nm": boundary, "tau_rescue_nm": rescue},
        "f3_prime": dict(contract["p2"]["f3_prime"]),
    }
    return gradient, ladder, e_region


def run_stage(mode: str, *, config_path: Path = CONFIG, root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    contract = _load_contract(config_path)
    root = absolute(root)
    if root.resolve() != ARTIFACT_ROOT.resolve():
        raise ValueError("r13 stages require the canonical artifact root")
    if mode == "prepare":
        p1 = _load_json(P1_RECEIPT)
        if p1.get("typed_outcome") != "V24_FRICTION_ESCALATED_DOMAIN_STABLE" or p1.get("stable_max_static_effort_nm") != 20.0:
            raise RuntimeError("r13 prepare requires the complete stable 20 N*m P1-lite domain")
        freeze = {
            "schema": "a2_piper_v24_p2_r13_parameter_e1_freeze_v1", "status": "EXECUTED_BEFORE_R13_DATA",
            "owner_decision": rel_path(OWNER_DECISION), "p1_receipt": rel_path(P1_RECEIPT),
            "magnitude_anchor": dict(contract["p2"]["magnitude_anchor"]),
            "calibration_grid": {"profiles": list(PROFILES), "caps_nm": list(CAPS), "scenarios": 16, "rows": 384},
            "e1_semantics": dict(contract["p2"]["e1_semantics"]), "gradient_gate": dict(contract["p2"]["gradient_gate"]),
            "ladder_gate": dict(contract["p2"]["ladder_gate"]),
            "authority": {"door_friction": "MODELED_FROM_PARAMS", "solver_applied": False, "capacity_lambda": "ESTIMATE_ONLY_DIRECTIONAL_MARGIN"},
        }
        f3 = {
            "schema": "a2_piper_v24_p2_r13_f3_prime_registration_v1", "status": "REGISTERED_BEFORE_R13_CALIBRATION",
            "owner_decision": rel_path(OWNER_DECISION), **dict(contract["p2"]["f3_prime"]),
            "admission": "sustained E1 requires demand>=2 N*m, capacity>=2 N*m, 0.5<=lambda<1.0, stable grasp and valid sources",
            "capacity_collapse": "CAPACITY_COLLAPSED_WINDOW is excluded and separately counted",
        }
        return {"stage": mode, "artifacts": [str(_write_json(root, FREEZE_ARTIFACT, freeze)), str(_write_json(root, F3_REGISTRATION_ARTIFACT, f3))]}
    _load_json(root / FREEZE_ARTIFACT)
    _load_json(root / F3_REGISTRATION_ARTIFACT)
    if mode == "vitals":
        rows = _runtime_rows(contract, root, seed=0, profile="F00", cap_nm=40.0, num_envs=16, scenarios=SCENARIOS, continuity_id="VITALS_R13_FIXED_SHAM")
        normalized = _validate_rows(rows, profiles=("F00",), caps=(40.0,), scenarios=SCENARIOS, seed=0, continuity="VITALS_R13_FIXED_SHAM")
        receipt = _vitals_receipt(normalized)
        if receipt["status"] != "PASS_VALID_MEASUREMENT_ADMISSION":
            raise RuntimeError(f"r13 Rule16 vitals failed: {receipt!r}")
        return {"stage": mode, "artifacts": [str(_write_rows(root, VITAL_ROWS_ARTIFACT, normalized)), str(_write_json(root, VITAL_RECEIPT_ARTIFACT, receipt))]}
    vitals = _load_json(root / VITAL_RECEIPT_ARTIFACT)
    if vitals.get("status") != "PASS_VALID_MEASUREMENT_ADMISSION":
        raise RuntimeError("r13 Rule16 vitals are not admitted")
    if mode == "smoke":
        rows: list[dict[str, Any]] = []
        for profile in ("P02", "P10", "P20"):
            rows.extend(_runtime_rows(contract, root, seed=24041, profile=profile, cap_nm=40.0, num_envs=3, scenarios=SCENARIOS[:3], continuity_id="SMOKE_R13", control_steps=64))
        normalized = _validate_rows(rows, profiles=("P02", "P10", "P20"), caps=(40.0,), scenarios=SCENARIOS[:3], seed=24041, continuity="SMOKE_R13")
        receipt = {"schema": "a2_piper_v24_p2_r13_smoke_v1", "status": "EXECUTED", "evidentiary": False, "rows": 9, "profiles": ["P02", "P10", "P20"], "control_steps": 64}
        return {"stage": mode, "artifacts": [str(_write_rows(root, SMOKE_ROWS_ARTIFACT, normalized)), str(_write_json(root, SMOKE_RECEIPT_ARTIFACT, receipt))]}
    smoke = _load_json(root / SMOKE_RECEIPT_ARTIFACT)
    if smoke.get("status") != "EXECUTED":
        raise RuntimeError("r13 smoke is incomplete")
    if mode == "calibrate":
        rows: list[dict[str, Any]] = []
        for profile in PROFILES:
            for cap in CAPS:
                print(json.dumps({"stage": "calibrate", "profile": profile, "cap_nm": cap, "status": "START"}), flush=True)
                cell = _runtime_rows(contract, root, seed=24041, profile=profile, cap_nm=cap, num_envs=16, scenarios=SCENARIOS, continuity_id="CALIBRATION_R13")
                rows.extend(cell)
                print(json.dumps({"stage": "calibrate", "profile": profile, "cap_nm": cap, "status": "COMPLETE", "rows": len(cell)}), flush=True)
        normalized = _validate_rows(rows, profiles=PROFILES, caps=CAPS, scenarios=SCENARIOS, seed=24041, continuity="CALIBRATION_R13")
        receipt = {"schema": "a2_piper_v24_p2_r13_calibration_v1", "status": "EXECUTED", "rows": 384, "profiles": list(PROFILES), "caps_nm": list(CAPS), "scenarios": 16, "seed": 24041, "rule16_status": vitals["status"]}
        return {"stage": mode, "artifacts": [str(_write_rows(root, CALIBRATION_ROWS_ARTIFACT, normalized)), str(_write_json(root, CALIBRATION_RECEIPT_ARTIFACT, receipt))]}
    if mode == "gradient":
        receipt = _load_json(root / CALIBRATION_RECEIPT_ARTIFACT)
        if receipt.get("status") != "EXECUTED" or receipt.get("rows") != 384:
            raise RuntimeError("r13 calibration receipt is incomplete")
        rows = _validate_rows(_read_rows(root / CALIBRATION_ROWS_ARTIFACT), profiles=PROFILES, caps=CAPS, scenarios=SCENARIOS, seed=24041, continuity="CALIBRATION_R13")
        gradient, ladder, e_region = _adjudicate(rows, contract)
        return {"stage": mode, "status": gradient["status"], "artifacts": [str(_write_json(root, GRADIENT_ARTIFACT, gradient)), str(_write_json(root, LADDER_ARTIFACT, ladder)), str(_write_json(root, E_REGION_ARTIFACT, e_region))]}
    raise ValueError(f"unknown r13 stage {mode!r}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--mode", choices=("prepare", "vitals", "smoke", "calibrate", "gradient"))
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=ARTIFACT_ROOT)
    args = parser.parse_args(argv)
    if args.plan:
        print(json.dumps(build_plan(args.config), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0
    if args.mode is None:
        parser.error("pass --plan or --mode")
    print(json.dumps(run_stage(args.mode, config_path=args.config, root=args.output), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
