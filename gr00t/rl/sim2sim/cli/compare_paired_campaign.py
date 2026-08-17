#!/usr/bin/env python3
"""Compare schema-aligned Isaac and MuJoCo paired campaign traces."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import jsonschema


SCALAR_FIELDS = {
    "time_s": ("time_s",),
    "base_height_m": ("base", "position_m", 2),
    "door_hinge_rad": ("door", "hinge_rad"),
    "door_hinge_velocity_radps": ("door", "hinge_velocity_radps"),
    "handle_rad": ("door", "handle_rad"),
    "handle_velocity_radps": ("door", "handle_velocity_radps"),
    "hinge_drive_force_nm": ("door", "hinge_drive_force_nm"),
    "handle_drive_force_nm": ("door", "handle_drive_force_nm"),
}
VECTOR_FIELDS = {
    "student_action_mean": ("student_action_mean",),
    "applied_action": ("applied_action",),
    "position_target_sim_units": ("position_target_sim_units",),
    "robot_qpos": ("robot_qpos",),
    "robot_qvel": ("robot_qvel",),
    "robot_ctrl_effort": ("robot_ctrl_effort",),
    "camera_age_normalized": ("camera_input", "age_normalized"),
}


def _value(row: dict[str, Any], path: tuple[Any, ...]) -> Any:
    current: Any = row
    for part in path:
        current = current[part]
    return current


def _finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(_finite_tree(item) for item in value.values())
    return True


def _trace_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first_unlatch = next((row["time_s"] for row in rows if row["door"]["unlatched"]), None)
    first_open = next(
        (row["time_s"] for row in rows if row["door"]["open_threshold_crossed"]), None
    )
    return {
        "rows": len(rows),
        "final_time_s": rows[-1]["time_s"],
        "termination_reason": rows[-1]["termination_reason"],
        "max_hinge_rad": max(row["door"]["hinge_rad"] for row in rows),
        "max_handle_rad": max(row["door"]["handle_rad"] for row in rows),
        "first_unlatch_time_s": first_unlatch,
        "first_open_time_s": first_open,
    }


def _load_trace(
    path: Path,
    *,
    validator: jsonschema.protocols.Validator,
    manifest_id: str,
    case: dict[str, Any],
    backend: str,
) -> tuple[list[dict[str, Any]], str | None]:
    rows = [json.loads(line) for line in path.resolve(strict=True).read_text(encoding="utf-8").splitlines()]
    if not rows:
        raise ValueError(f"empty paired trace: {path}")
    for index, row in enumerate(rows):
        validator.validate(row)
        if not _finite_tree(row):
            return rows, f"non-finite numeric value at row {index}"
        expected = {
            "manifest_id": manifest_id,
            "case_id": case["case_id"],
            "door_instance_id": case["door_instance_id"],
            "episode_index": case["episode_index"],
            "seed": case["seed"],
            "backend": backend,
            "physics_step": index,
            "policy_step": index // 4,
            "substep": index % 4,
            "policy_update": index % 4 == 0,
        }
        for field, expected_value in expected.items():
            if row[field] != expected_value:
                raise ValueError(
                    f"trace contract mismatch {path} row={index} field={field}: "
                    f"{row[field]!r} != {expected_value!r}"
                )
        if row["done"] != (index == len(rows) - 1):
            raise ValueError(f"done must be true only on final row: {path} row={index}")
    if rows[-1]["termination_reason"] == "NONE":
        raise ValueError(f"terminal row lacks termination reason: {path}")
    return rows, None


def _difference_stats(
    reference: list[dict[str, Any]], candidate: list[dict[str, Any]], path: tuple[Any, ...]
) -> dict[str, Any]:
    count = min(len(reference), len(candidate))
    sum_square = 0.0
    maximum = 0.0
    element_count = 0
    for expected, actual in zip(reference[:count], candidate[:count], strict=True):
        expected_value = _value(expected, path)
        actual_value = _value(actual, path)
        expected_items = expected_value if isinstance(expected_value, list) else [expected_value]
        actual_items = actual_value if isinstance(actual_value, list) else [actual_value]
        if len(expected_items) != len(actual_items):
            raise ValueError(f"paired vector width mismatch for {path}")
        for left, right in zip(expected_items, actual_items, strict=True):
            difference = abs(float(left) - float(right))
            maximum = max(maximum, difference)
            sum_square += difference * difference
            element_count += 1
    return {
        "aligned_rows": count,
        "elements": element_count,
        "max_abs_diff": maximum,
        "rmse": math.sqrt(sum_square / element_count),
    }


def _event_delta(reference: Any, candidate: Any) -> dict[str, Any]:
    if reference is None and candidate is None:
        return {"status": "ABSENT_BOTH", "isaac_s": None, "mujoco_s": None, "delta_s": None}
    if reference is None or candidate is None:
        return {
            "status": "ONE_SIDED_EVENT",
            "isaac_s": reference,
            "mujoco_s": candidate,
            "delta_s": None,
        }
    return {
        "status": "OBSERVED_BOTH",
        "isaac_s": reference,
        "mujoco_s": candidate,
        "delta_s": float(candidate) - float(reference),
    }


def _compare_case(
    isaac_rows: list[dict[str, Any]], mujoco_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    isaac_summary = _trace_summary(isaac_rows)
    mujoco_summary = _trace_summary(mujoco_rows)
    return {
        "aligned_rows": min(len(isaac_rows), len(mujoco_rows)),
        "isaac_only_terminal_rows": max(0, len(isaac_rows) - len(mujoco_rows)),
        "mujoco_only_terminal_rows": max(0, len(mujoco_rows) - len(isaac_rows)),
        "scalar_differences": {
            name: _difference_stats(isaac_rows, mujoco_rows, path)
            for name, path in SCALAR_FIELDS.items()
        },
        "vector_differences": {
            name: _difference_stats(isaac_rows, mujoco_rows, path)
            for name, path in VECTOR_FIELDS.items()
        },
        "discrete_schedule": {
            "camera_frame_id_mismatch_rows": sum(
                left["camera_input"]["frame_ids"] != right["camera_input"]["frame_ids"]
                for left, right in zip(isaac_rows, mujoco_rows)
            ),
            "camera_valid_mismatch_rows": sum(
                left["camera_input"]["valid"] != right["camera_input"]["valid"]
                for left, right in zip(isaac_rows, mujoco_rows)
            ),
            "latch_state_mismatch_rows": sum(
                left["door"]["latch_state"] != right["door"]["latch_state"]
                for left, right in zip(isaac_rows, mujoco_rows)
            ),
        },
        "events": {
            "unlatch": _event_delta(
                isaac_summary["first_unlatch_time_s"], mujoco_summary["first_unlatch_time_s"]
            ),
            "open_crossing": _event_delta(
                isaac_summary["first_open_time_s"], mujoco_summary["first_open_time_s"]
            ),
        },
        "isaac_summary": isaac_summary,
        "mujoco_summary": mujoco_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--mujoco-root", required=True, type=Path)
    parser.add_argument("--isaac-root", type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema_path = args.schema.resolve(strict=True)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_class = jsonschema.validators.validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema)
    mujoco_root = args.mujoco_root.resolve(strict=True)
    case_material = []
    numeric_error = None
    for case in manifest["cases"]:
        trace = mujoco_root / "cases" / case["case_id"] / "trace.jsonl"
        rows, error = _load_trace(
            trace,
            validator=validator,
            manifest_id=manifest["manifest_id"],
            case=case,
            backend="mujoco_cpu",
        )
        numeric_error = numeric_error or error
        case_material.append((case, rows))

    comparisons = None
    isaac_identity = None
    if numeric_error is not None:
        classification = "INVALID_NUMERICS"
        input_status = "INVALID_NUMERICS_MUJOCO_TRACE"
    elif args.isaac_root is None:
        classification = "EXPLORATORY_NON_COMPARABLE"
        input_status = "BLOCKED_INPUT_ISAAC_PAIRED_TRACE"
    else:
        isaac_root = args.isaac_root.resolve(strict=True)
        isaac_identity = str(isaac_root)
        comparisons = []
        for case, mujoco_rows in case_material:
            trace = isaac_root / "isaac_physx" / case["case_id"] / "trace.jsonl"
            isaac_rows, error = _load_trace(
                trace,
                validator=validator,
                manifest_id=manifest["manifest_id"],
                case=case,
                backend="isaac_physx",
            )
            if error is not None:
                numeric_error = error
                break
            comparisons.append(
                {"case_id": case["case_id"], **_compare_case(isaac_rows, mujoco_rows)}
            )
        if numeric_error is not None:
            classification = "INVALID_NUMERICS"
            input_status = "INVALID_NUMERICS_ISAAC_TRACE"
            comparisons = None
        else:
            classification = "VALID_WITH_WARNINGS"
            input_status = "PAIRED_CAMPAIGN_COMPARED"

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    report = {
        "schema": "doordog.sim2sim.e5_paired_campaign_report.v1",
        "evidence_level": "E5",
        "result_classification": classification,
        "input_status": input_status,
        "manifest": str(manifest_path),
        "manifest_id": manifest["manifest_id"],
        "trace_schema": {
            "path": str(schema_path),
            "source_commit": manifest["paired_trace_schema"]["source_commit"],
        },
        "mujoco_root": str(mujoco_root),
        "isaac_root": isaac_identity,
        "mujoco_cases": [
            {"case_id": case["case_id"], **_trace_summary(rows)} for case, rows in case_material
        ],
        "comparison": comparisons,
        "numeric_error": numeric_error,
        "comparison_policy": {
            "alignment": "physics_step from the same fixed case/initial-state/seed",
            "trajectory_metrics": "raw max-absolute difference and RMSE; no universal hard threshold",
            "event_metrics": "direct handle unlatch and hinge open-threshold crossing",
            "success_rate_role": "RECORDED_NOT_A_PARITY_VERDICT",
            "pixel_role": "DOMAIN_GAP_DATA_NOT_POLICY_REGRESSION"
        },
        "comparator_identity": {
            "git_commit": commit,
            "path": "gr00t/rl/sim2sim/cli/compare_paired_campaign.py"
        },
        "warnings": (
            ["Isaac paired campaign input has not been transferred; no formal comparison is claimed."]
            if args.isaac_root is None
            else [
                "No universal physics-difference threshold is imposed; interpret per-field/event evidence.",
                "RGB renderer differences remain domain-gap evidence."
            ]
        )
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"classification": classification, "input_status": input_status}, sort_keys=True))


if __name__ == "__main__":
    main()
