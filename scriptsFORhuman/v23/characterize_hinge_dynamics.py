"""P0.4 source-locked door resistance atlas.

The atlas keeps the A0--A8 labels from the approved v23 discussion and uses
free-return/fixed-effort evidence as its primary classification input.  A3 is
explicitly a near-closed high-stiffness/max-force proxy; the current door
implementation has no independent friction knob.  This module is pure data
and never creates an IsaacLab scene.  Torque fields are actuator-model
estimates with no actual drive-force readback; position tracking follows
``joint_pos_target - joint_pos`` with velocity context.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from ._v23_common import (
    V23_D0_SOURCE_CONFIG,
    V23_EFFORT_RUNGS,
    V23Error,
    artifact_payload,
    emit_payload,
    finite_number,
    read_json,
)


ATLAS_CELLS = (
    ("A0", "current easy", "historical_v22_g1_winner"),
    ("A1", "high stiffness", "hinge_stiffness_native"),
    ("A2", "high sustained resistive torque", "hinge_max_force_nm"),
    ("A3", "high breakaway/friction proxy", "near_closed_stiffness_plus_max_force_proxy"),
    ("A4", "high damping", "hinge_damping_native"),
    ("A5", "high inertia", "door_weight_kg"),
    ("A6", "stiffness + calibrated effort", "hinge_stiffness_native+effort_profile"),
    ("A7", "resistive torque + calibrated effort", "hinge_max_force_nm+effort_profile"),
    ("A8", "compound near-boundary", "near_boundary_compound"),
)

ATLAS_BOUNDS = {
    "hinge_damping_native": {"max": 200.0, "units": "native"},
    "hinge_stiffness_native": {"max": 30.0, "units": "native"},
    "hinge_max_force_nm": {"max": 24.0, "units": "N*m"},
}

D1_CURRICULUM = (
    {"progress": "0-20%", "E0": 1.0, "E1": 0.0, "near_E2": 0.0, "confirmed_E2": 0.0},
    {"progress": "20-50%", "E0": 0.6, "E1": 0.4, "near_E2": 0.0, "confirmed_E2": 0.0},
    {"progress": "50-100%", "E0": 0.3, "E1": 0.6, "near_E2": 0.1, "confirmed_E2": 0.0},
)


def _rows(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    values = payload.get("rows", payload.get("cells", []))
    if not isinstance(values, list):
        raise V23Error("atlas observations must contain rows or cells as a list")
    result: dict[str, Mapping[str, Any]] = {}
    for row in values:
        if not isinstance(row, Mapping):
            raise V23Error("each atlas observation must be an object")
        cell_id = row.get("cell_id", row.get("atlas_cell"))
        if cell_id not in {item[0] for item in ATLAS_CELLS}:
            raise V23Error(f"unknown atlas cell: {cell_id!r}")
        if cell_id in result:
            raise V23Error(f"duplicate atlas observation: {cell_id}")
        result[str(cell_id)] = row
    return result


def _measurement_summary(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "status": "NOT_RUN",
            "free_return": "PENDING",
            "fixed_effort_responses": "PENDING",
            "nominal_actuator_model_torque_estimate": "PENDING",
            "applied_actuator_model_torque_estimate": "PENDING",
            "estimated_clipping_residual": "PENDING",
            "tracking_error_rad": "PENDING",
            "joint_velocity_rad_s": "PENDING",
        }
    summary: dict[str, Any] = {"status": "MEASURED_INPUT"}
    for key in (
        "free_return",
        "fixed_effort_responses",
        "nominal_actuator_model_torque_estimate",
        "applied_actuator_model_torque_estimate",
        "estimated_clipping_residual",
        "tracking_error_rad",
        "joint_velocity_rad_s",
    ):
        value = row.get(key, "PENDING")
        if isinstance(value, (int, float)):
            finite_number(value, name=key)
        summary[key] = value
    return summary


def build_atlas(observations: Mapping[str, Any] | None = None) -> dict[str, Any]:
    observed = _rows(observations) if observations is not None else {}
    cells = []
    for cell_id, label, axis in ATLAS_CELLS:
        row = observed.get(cell_id)
        physics_class = row.get("physics_class", "PENDING") if row else "PENDING"
        if physics_class not in ("E0", "E1", "NEAR_E2", "CONFIRMED_E2", "PENDING"):
            raise V23Error(f"{cell_id} physics_class is not a v23 class: {physics_class!r}")
        cells.append(
            {
                "cell_id": cell_id,
                "label": label,
                "axis": axis,
                "a3_semantics": "FRICTION_PROXY" if cell_id == "A3" else None,
                "parameter_bounds": ATLAS_BOUNDS,
                "classification_basis": "physics_first_free_return_and_fixed_effort_response",
                "realized_dynamics_required": True,
                "intended_bucket_role": "sampling_only",
                "physics_class": physics_class,
                "measurements": _measurement_summary(row),
            }
        )
    return artifact_payload(
        "door_atlas",
        status="NOT_RUN_PENDING" if observations is None else "MEASURED_INPUT_REQUIRES_REVIEW",
        source_config_path=V23_D0_SOURCE_CONFIG,
        cells=cells,
        d1_curriculum=list(D1_CURRICULUM),
        d1_lite={
            "state": "PRE_REGISTERED_BACKUP",
            "near_E2_fraction": "half_of_the_measured_D1_fraction",
            "E1_upper_bound": "narrowed_within_planner_bounds",
            "confirmed_E2_in_training": False,
        },
        effort_profile={
            "shared_across_cells": True,
            "selected_effort_nm": None,
            "source": "P0.2_effort_ladder",
            "state": "PENDING",
            "registered_rungs_nm": list(V23_EFFORT_RUNGS),
        },
        classification_note=(
            "E0/E1/near-E2/confirmed-E2 are provisional until P0 calibration and "
            "chronic FULL/RP0 evidence; acute posture contrast is auxiliary only."
        ),
        p0_numeric_state="PENDING_UNTIL_MEASURED",
    )


build_door_atlas = build_atlas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    observations = read_json(args.observations) if args.observations is not None else None
    emit_payload(build_atlas(observations), args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 DOOR ATLAS FAIL: {exc}")
