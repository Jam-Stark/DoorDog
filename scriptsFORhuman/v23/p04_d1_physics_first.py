"""Reduce the owner-approved physics-first v23 D1/D1-lite boundary.

This reducer is deliberately pure-data.  The door-side positive atlas brackets
are the classifier input; historical FULL/ACUTE policy records are retained as
auxiliary archive evidence and never select a zone.  The old capability-source
reducer is intentionally not imported or called here.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v23_p04_d1_physics_first_v1"
TASK_ID = "V23-R190-D1-PHYSICS-FIRST"
REVISION = "R190"
PLAN_ID = "base_v23_force_feasibility_initialization_posture_R1"
EFFORT_NM = 40.0
OPENING_PASS_THRESHOLD_RAD = 0.02
EXPECTED_CELLS = ("A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8")
EXPECTED_NORMAL = {
    "E0": ("A0", "A1"),
    "E1": ("A4", "A5", "A6", "A2", "A3", "A7"),
    "near-E2": ("A8",),
    "confirmed-E2": (),
}
EXPECTED_LITE = {
    "E0": ("A0", "A1"),
    "E1": ("A4", "A5", "A6"),
    "near-E2": ("A8",),
    "confirmed-E2": (),
}
NORMAL_SCHEDULE = "100/0/0 -> 60/40/0 -> 30/60/10"
LITE_SCHEDULE = "100/0/0 -> 65/35/0 -> 40/55/5"
FAILURE_KEYS = ("FALL", "LOST_GRASP", "DOOR_FRAME_COLLISION", "TIMEOUT_WRONG_STAGE")


class PhysicsFirstError(ValueError):
    """Raised when an authoritative source violates its typed contract."""


def _finite(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PhysicsFirstError(f"{name} must be a finite number; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise PhysicsFirstError(f"{name} must be a finite number; got {value!r}")
    return result


def _require_file(raw_path: str, *, label: str) -> Path:
    path = Path(raw_path)
    if path.is_symlink() or not path.is_file():
        raise PhysicsFirstError(f"{label} is not a regular file: {path}")
    return path


def _read_object(raw_path: str, *, label: str) -> tuple[Path, dict[str, Any]]:
    path = _require_file(raw_path, label=label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PhysicsFirstError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PhysicsFirstError(f"{label} must contain a JSON object: {path}")
    return path, value


def _path_text(path: Path) -> str:
    """Keep provenance stable for both relative and absolute CLI paths."""

    return path.as_posix()


def _read_effort_freeze(raw_path: str) -> tuple[Path, dict[str, Any]]:
    path, source = _read_object(raw_path, label="effort freeze")
    if source.get("schema") != "a2_piper_v23_effort_freeze_v1":
        raise PhysicsFirstError("effort freeze schema is not a2_piper_v23_effort_freeze_v1")
    if source.get("status") != "MEASURED_FREEZE" or source.get("selection_state") != "MEASURED_FREEZE":
        raise PhysicsFirstError("effort freeze is not a MEASURED_FREEZE")
    if source.get("selection_outcome") != "LADDER_INCONCLUSIVE" or source.get("outcome") != "LADDER_INCONCLUSIVE":
        raise PhysicsFirstError("effort freeze does not record the required F2-40 LADDER_INCONCLUSIVE outcome")
    selected = _finite(source.get("selected_effort_nm"), name="effort_freeze.selected_effort_nm")
    profile = source.get("effort_profile")
    if not isinstance(profile, Mapping):
        raise PhysicsFirstError("effort freeze is missing effort_profile")
    profile_effort = _finite(profile.get("effort_nm"), name="effort_freeze.effort_profile.effort_nm")
    if selected != EFFORT_NM or profile_effort != EFFORT_NM:
        raise PhysicsFirstError(
            f"effort freeze must bind the matrix-wide {EFFORT_NM:g} N*m profile; "
            f"selected={selected:g}, profile={profile_effort:g}"
        )
    rows = source.get("rows")
    if not isinstance(rows, list) or not rows:
        raise PhysicsFirstError("effort freeze must contain measured rung rows")
    selected_rows = 0
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise PhysicsFirstError(f"effort freeze row {index} is not an object")
        row_effort = _finite(row.get("effort_nm"), name=f"effort_freeze.rows[{index}].effort_nm")
        if row_effort == EFFORT_NM:
            selected_rows += 1
    if selected_rows == 0:
        raise PhysicsFirstError("effort freeze has no measured 40.0 N*m row")
    return path, {
        "schema": source["schema"],
        "status": source["status"],
        "selection_state": source["selection_state"],
        "selected_effort_nm": EFFORT_NM,
        "selection_outcome": source["selection_outcome"],
        "matrix_wide": True,
        "f2_close": True,
        "ladder_selection_success": False,
        "selected_row_count": selected_rows,
    }


def _read_atlas(raw_path: str) -> tuple[Path, dict[str, Any]]:
    path, source = _read_object(raw_path, label="external torque threshold")
    if source.get("schema") != "a2_piper_v23_door_external_torque_threshold_v1":
        raise PhysicsFirstError("external threshold schema is not a2_piper_v23_door_external_torque_threshold_v1")
    if source.get("status") != "MEASURED_RAW" or source.get("plan_id") != PLAN_ID:
        raise PhysicsFirstError("external threshold is not the measured R1 atlas producer output")
    if source.get("interpolation") != "FORBIDDEN":
        raise PhysicsFirstError("external threshold must forbid interpolation")
    bracket = source.get("bracket")
    if not isinstance(bracket, Mapping):
        raise PhysicsFirstError("external threshold is missing bracket")
    threshold = _finite(bracket.get("threshold_rad"), name="external_threshold.bracket.threshold_rad")
    if threshold != OPENING_PASS_THRESHOLD_RAD:
        raise PhysicsFirstError(
            f"atlas opening-pass threshold must be {OPENING_PASS_THRESHOLD_RAD:g} rad; got {threshold:g}"
        )
    cells = bracket.get("cells")
    if not isinstance(cells, Mapping) or set(cells) != set(EXPECTED_CELLS):
        raise PhysicsFirstError("external threshold bracket cells must be exactly A0-A8")

    positive: dict[str, dict[str, Any]] = {}
    negative_statuses: dict[str, str] = {}
    for cell_id in EXPECTED_CELLS:
        cell = cells[cell_id]
        if not isinstance(cell, Mapping) or cell.get("status") != "RIGHT_CENSORED":
            raise PhysicsFirstError(f"atlas cell {cell_id} has an unsupported bracket status")
        by_sign = cell.get("by_sign")
        if not isinstance(by_sign, Mapping) or "1" not in by_sign or "-1" not in by_sign:
            raise PhysicsFirstError(f"atlas cell {cell_id} must provide both signed bracket records")
        pos = by_sign["1"]
        neg = by_sign["-1"]
        if not isinstance(pos, Mapping) or pos.get("status") != "VALID_BRACKET":
            raise PhysicsFirstError(f"atlas cell {cell_id} positive direction is not a VALID_BRACKET")
        if not isinstance(neg, Mapping) or neg.get("status") != "RIGHT_CENSORED":
            raise PhysicsFirstError(f"atlas cell {cell_id} negative direction is not RIGHT_CENSORED")
        lower = _finite(pos.get("last_fail_nm"), name=f"atlas.{cell_id}.positive.last_fail_nm")
        upper = _finite(pos.get("first_pass_nm"), name=f"atlas.{cell_id}.positive.first_pass_nm")
        if not lower < upper:
            raise PhysicsFirstError(f"atlas cell {cell_id} positive bracket must satisfy last_fail < first_pass")
        negative_statuses[cell_id] = str(neg["status"])
        positive[cell_id] = {
            "cell_id": cell_id,
            "last_fail_nm": lower,
            "first_pass_nm": upper,
            "lower_nm": lower,
            "upper_nm": upper,
            "interval": f"({lower:g},{upper:g}]",
            "status": pos["status"],
            "opening_pass_threshold_rad": threshold,
            "opening_pass_provenance": "measured external atlas bracket at bracket.threshold_rad",
            "negative_direction_status": neg["status"],
        }

    rows = source.get("rows")
    if not isinstance(rows, list) or not rows:
        raise PhysicsFirstError("external threshold must retain measured atlas rows")
    return path, {
        "schema": source["schema"],
        "status": source["status"],
        "plan_id": source["plan_id"],
        "interpolation": source["interpolation"],
        "opening_pass_threshold_rad": threshold,
        "opening_pass_provenance": "external measured atlas threshold_rad=0.02 rad",
        "positive_brackets": positive,
        "negative_direction_status": negative_statuses,
        "measured_row_count": len(rows),
        "selected_direction": "+1",
        "selected_direction_semantics": "POSITIVE_OPENING",
    }


def _read_p05_bands(raw_path: str) -> tuple[Path, dict[str, Any]]:
    path, source = _read_object(raw_path, label="P0.5 bands")
    expected = (
        "stable_grasp_min_steps",
        "low_progress_min_rad",
        "low_progress_max_rad",
        "low_progress_window_min_steps",
        "low_progress_window_max_steps",
        "clipped_utilization_min",
        "clipped_fraction_min",
        "rescue_progress_min_rad",
        "rescue_progress_max_rad",
    )
    if set(source) != set(expected):
        raise PhysicsFirstError("P0.5 bands fields differ from the frozen R35 contract")
    bands: dict[str, Any] = {}
    for key in expected:
        value = _finite(source[key], name=f"p05_bands.{key}")
        bands[key] = int(value) if key.endswith("steps") and value.is_integer() else value
    return path, bands


def _failure_free(row: Mapping[str, Any], *, name: str) -> bool:
    failure_flags = row.get("failure_flags")
    if not isinstance(failure_flags, Mapping) or set(failure_flags) != set(FAILURE_KEYS):
        raise PhysicsFirstError(f"{name}.failure_flags does not match the registered P0.5 fields")
    for key in FAILURE_KEYS:
        if not isinstance(failure_flags[key], bool):
            raise PhysicsFirstError(f"{name}.failure_flags.{key} must be boolean")
    return not any(failure_flags.values())


def _valid_policy_window(record: Mapping[str, Any], *, mode: str, index: int) -> dict[str, Any] | None:
    rows = record.get("step_rows")
    if not isinstance(rows, list) or not rows:
        raise PhysicsFirstError(f"{mode} archive record {index} has no step_rows")
    previous_step = None
    eligible: list[bool] = []
    hinge: list[float] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise PhysicsFirstError(f"{mode} archive record {index} step row {row_index} is not an object")
        if row.get("mode") != mode or row.get("topology") != "canonical16":
            raise PhysicsFirstError(f"{mode} archive record {index} has mismatched mode/topology")
        step = row.get("control_step")
        if isinstance(step, bool) or not isinstance(step, int):
            raise PhysicsFirstError(f"{mode} archive record {index} has a non-integer control_step")
        if previous_step is not None and step != previous_step + 1:
            raise PhysicsFirstError(f"{mode} archive record {index} control_step sequence is not contiguous")
        previous_step = step
        stable = row.get("stable_grasp")
        predicates = row.get("stable_grasp_predicates")
        if not isinstance(stable, bool) or not isinstance(predicates, Mapping):
            raise PhysicsFirstError(f"{mode} archive record {index} has malformed stable-grasp evidence")
        opening_stage = predicates.get("opening_stage")
        if not isinstance(opening_stage, bool):
            raise PhysicsFirstError(f"{mode} archive record {index} has malformed opening-stage evidence")
        hinge.append(_finite(row.get("hinge_position_rad"), name=f"{mode}[{index}].hinge_position_rad"))
        eligible.append(stable and opening_stage and _failure_free(row, name=f"{mode}[{index}]"))

    for start in range(0, len(eligible) - 25 + 1):
        if all(eligible[start : start + 25]):
            end = start + 24
            return {
                "start_control_step": rows[start]["control_step"],
                "end_control_step": rows[end]["control_step"],
                "window_steps": 25,
                "progress_rad": hinge[end] - hinge[start],
            }
    return None


def _read_policy_archive(raw_path: str, *, mode: str) -> tuple[Path, dict[str, Any]]:
    path, source = _read_object(raw_path, label=f"{mode} policy archive")
    if source.get("schema") != "a2_piper_v23_episode_records_export_v1":
        raise PhysicsFirstError(f"{mode} policy archive schema is not the registered episode export")
    records = source.get("records")
    if not isinstance(records, list) or not records:
        raise PhysicsFirstError(f"{mode} policy archive must contain at least one record")

    valid_windows: list[dict[str, Any]] = []
    invalid_env_ids: list[int] = []
    seen_env_ids: set[int] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise PhysicsFirstError(f"{mode} policy archive record {index} is not an object")
        if record.get("mode") != mode or record.get("purpose") != "D1_CAPABILITY_SOURCE":
            raise PhysicsFirstError(f"{mode} policy archive record {index} has mismatched mode/purpose")
        rows = record.get("step_rows")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
            raise PhysicsFirstError(f"{mode} policy archive record {index} has malformed step_rows")
        env_id = rows[0].get("env_id")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < 16:
            raise PhysicsFirstError(f"{mode} policy archive record {index} has invalid env_id")
        if env_id in seen_env_ids:
            raise PhysicsFirstError(f"{mode} policy archive duplicates env_id={env_id}")
        seen_env_ids.add(env_id)
        window = _valid_policy_window(record, mode=mode, index=index)
        if window is None:
            invalid_env_ids.append(env_id)
        else:
            valid_windows.append({"env_id": env_id, **window})

    valid_count = len(valid_windows)
    expected_count = 16
    if mode == "FULL":
        archive_admitted = valid_count >= 12
        status = "FULL_ARCHIVE_ADMITTED" if archive_admitted else "FULL_ARCHIVE_BELOW_ADMISSION_THRESHOLD"
    else:
        archive_admitted = None
        status = "ACUTE_WINDOWS_SPARSE_EXPECTED"
    return path, {
        "schema": source["schema"],
        "mode": mode,
        "status": status,
        "record_count": len(records),
        "expected_window_count": expected_count,
        "valid_window_count": valid_count,
        "valid_window_fraction": f"{valid_count}/{expected_count}",
        "archive_admitted": archive_admitted,
        "invalid_or_missing_window_env_ids": invalid_env_ids,
        "env5_gap_nonblocking": mode == "FULL" and 5 in invalid_env_ids,
        "valid_window_rule": (
            "first contiguous 25-control-step window with stable_grasp, opening_stage, "
            "finite hinge position, and all four failure flags false"
        ),
        "valid_windows": valid_windows,
        "raw_action_dimensions_3_4": "not adjudicated by this auxiliary archive reducer",
    }


def _classify(brackets: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, dict[str, Any]]]:
    normal = {key: [] for key in ("E0", "E1", "near-E2", "confirmed-E2")}
    lite = {key: [] for key in ("E0", "E1", "near-E2", "confirmed-E2")}
    cell_rows: dict[str, dict[str, Any]] = {}
    for cell_id in EXPECTED_CELLS:
        row = dict(brackets[cell_id])
        upper = _finite(row["upper_nm"], name=f"atlas.{cell_id}.upper_nm")
        if upper <= 15.0:
            normal_zone = "E0"
        elif upper <= 30.0:
            normal_zone = "E1"
        elif upper <= EFFORT_NM:
            normal_zone = "near-E2"
        else:
            raise PhysicsFirstError(f"atlas cell {cell_id} exceeds the frozen effort40 boundary")
        normal[normal_zone].append(cell_id)

        if upper <= 15.0:
            lite_zone = "E0"
        elif upper <= 20.0:
            lite_zone = "E1"
        elif cell_id == "A8" and 30.0 < upper <= EFFORT_NM:
            lite_zone = "near-E2"
        else:
            lite_zone = None
        if lite_zone is not None:
            lite[lite_zone].append(cell_id)
        row["normal_zone"] = normal_zone
        row["lite_zone"] = lite_zone
        cell_rows[cell_id] = row

    normal = {
        key: [cell_id for cell_id in EXPECTED_NORMAL[key] if cell_id in normal[key]]
        for key in normal
    }
    lite = {
        key: [cell_id for cell_id in EXPECTED_LITE[key] if cell_id in lite[key]]
        for key in lite
    }
    if {key: tuple(value) for key, value in normal.items()} != EXPECTED_NORMAL:
        raise PhysicsFirstError(f"measured atlas does not produce the Plan R1 normal zones: {normal!r}")
    if {key: tuple(value) for key, value in lite.items()} != EXPECTED_LITE:
        raise PhysicsFirstError(f"measured atlas does not produce the Plan R1 D1-lite zones: {lite!r}")
    return normal, lite, cell_rows


def _mixture(schedule: str, stages: Sequence[tuple[str, int, int, int]]) -> dict[str, Any]:
    return {
        "schedule": schedule,
        "axes": ["E0", "E1", "near-E2"],
        "stages": [
            {"interval": interval, "E0": e0, "E1": e1, "near-E2": near_e2, "confirmed-E2": 0}
            for interval, e0, e1, near_e2 in stages
        ],
        "confirmed_E2_share": 0,
    }


def build_receipt(
    *,
    effort_path: str,
    atlas_path: str,
    bands_path: str,
    full_archive_path: str | None,
    acute_archive_path: str | None,
) -> dict[str, Any]:
    effort_file, effort = _read_effort_freeze(effort_path)
    atlas_file, atlas = _read_atlas(atlas_path)
    bands_file, bands = _read_p05_bands(bands_path)
    normal, lite, cell_rows = _classify(atlas["positive_brackets"])

    policy_auxiliary: dict[str, Any] = {
        "role": "AUXILIARY_POLICY_EVIDENCE_ONLY",
        "full_admission_rule": "FULL >=12/16 valid windows is archive admission",
        "acute_rule": "ACUTE completeness is not required; record ACUTE_WINDOWS_SPARSE_EXPECTED",
        "env5_gap_rule": "known FULL env5 gap is nonblocking",
        "fresh_raw_action_dimensions_3_4": {
            "required": False,
            "status": "OPTIONAL_NOT_REQUIRED_FOR_PHYSICS_FIRST_FREEZE",
        },
    }
    if full_archive_path is not None:
        full_file, full = _read_policy_archive(full_archive_path, mode="FULL")
        policy_auxiliary["full"] = {"source": _path_text(full_file), **full}
    else:
        policy_auxiliary["full"] = {"source": None, "status": "NOT_PROVIDED"}
    if acute_archive_path is not None:
        acute_file, acute = _read_policy_archive(acute_archive_path, mode="ACUTE_RP0")
        policy_auxiliary["acute_rp0"] = {"source": _path_text(acute_file), **acute}
    else:
        policy_auxiliary["acute_rp0"] = {"source": None, "status": "NOT_PROVIDED"}

    return {
        "schema": SCHEMA,
        "task_id": TASK_ID,
        "revision": REVISION,
        "plan_id": PLAN_ID,
        "status": "P0_4_D1_PHYSICS_FIRST_FREEZE_ADMITTED",
        "freeze_status": "PHYSICS_FIRST_PROVISIONAL_FREEZE",
        "affirmative_physics_first_freeze": True,
        "old_r54_no_go": False,
        "old_r54_receipt_untouched": True,
        "decision_basis": {
            "owner_decision": "OPTION_2_PLUS_3_COMBINED",
            "owner_decision_path": "scriptsFORhuman/v23/DoorDog_v23_owner_decision_p0_unblock_20260810.md",
            "active_plan_section": "15.1",
            "classifier": "SCRIPTED_DOOR_SIDE_PHYSICS_POSITIVE_ATLAS_BRACKET",
            "policy_records_are_auxiliary": True,
            "no_historical_capability_binding_reducer": True,
        },
        "effort_boundary": {
            "source": _path_text(effort_file),
            **effort,
            "units": "N*m",
            "comparison_boundary_nm": EFFORT_NM,
            "selection_semantics": "F2 close at 40.0 N*m; no normal ladder-selection success claim",
        },
        "atlas_provenance": {
            "source": _path_text(atlas_file),
            "schema": atlas["schema"],
            "status": atlas["status"],
            "plan_id": atlas["plan_id"],
            "interpolation": atlas["interpolation"],
            "opening_pass_threshold_rad": atlas["opening_pass_threshold_rad"],
            "opening_pass_provenance": atlas["opening_pass_provenance"],
            "selected_direction": atlas["selected_direction"],
            "selected_direction_semantics": atlas["selected_direction_semantics"],
            "negative_direction_status": atlas["negative_direction_status"],
            "measured_row_count": atlas["measured_row_count"],
        },
        "atlas": {
            "cells": cell_rows,
            "positive_brackets": [cell_rows[cell_id] for cell_id in EXPECTED_CELLS],
            "threshold_rad": OPENING_PASS_THRESHOLD_RAD,
            "negative_direction": "RIGHT_CENSORED",
        },
        "zones": {
            "normal": normal,
            "lite": lite,
            "lite_not_in_curriculum": ["A2", "A3", "A7"],
            "confirmed_E2": [],
        },
        "mixture": {
            "normal": _mixture(
                NORMAL_SCHEDULE,
                (("0-20%", 100, 0, 0), ("20-50%", 60, 40, 0), ("50-100%", 30, 60, 10)),
            ),
            "lite": _mixture(
                LITE_SCHEDULE,
                (("0-20%", 100, 0, 0), ("20-50%", 65, 35, 0), ("50-100%", 40, 55, 5)),
            ),
        },
        "schedules": {"normal": NORMAL_SCHEDULE, "lite": LITE_SCHEDULE},
        "confirmed_E2": False,
        "labels_provisional": True,
        "post_training_hr_rp0_re_adjudication_required": True,
        "post_training_re_adjudication": {
            "required": True,
            "targets": ["G4'", "G8'"],
            "basis": "re-adjudicate provisional physics-first labels after HR-RP0 training",
            "confirmed_E2_remains_false_until_re_adjudication": True,
        },
        "p05_bands": {
            "source": _path_text(bands_file),
            "provenance": "R35 P0.5 bands unchanged",
            "bands": bands,
        },
        "policy_auxiliary": policy_auxiliary,
        "admission": {
            "node": "P0.4_D1_D1_LITE",
            "status": "AFFIRMATIVE_PHYSICS_FIRST_FREEZE_ADMISSION",
            "physics_first_inputs_validated": True,
            "policy_completeness_gate": False,
            "formal_training_authorized_after_remaining_gates": True,
            "remaining_gate": "P0.8_PREFORMAL_V2_RECEIPT_PLUS_D1_FULL_64x10_SMOKE",
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effort-freeze", required=True)
    parser.add_argument("--external-threshold", required=True)
    parser.add_argument("--p05-bands", required=True)
    parser.add_argument("--full-archive")
    parser.add_argument("--acute-archive")
    parser.add_argument("--out", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = build_receipt(
            effort_path=args.effort_freeze,
            atlas_path=args.external_threshold,
            bands_path=args.p05_bands,
            full_archive_path=args.full_archive,
            acute_archive_path=args.acute_archive,
        )
        output = Path(args.out)
        if output.exists():
            raise PhysicsFirstError(f"refusing to overwrite existing receipt: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, PhysicsFirstError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "WRITTEN", "path": output.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
