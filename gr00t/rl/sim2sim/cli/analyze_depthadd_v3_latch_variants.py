#!/usr/bin/env python3
"""Compare fixed16 DepthADD v3 latch-mechanics variant receipts.

This analyzer consumes only completed fixed receipts.  The three input roots
must contain the same immutable case ids (base000--base015), so every delta is
matched by case rather than compared through aggregate success rates alone.
The report is diagnostic: ``no_latch`` is an upper bound, while
``physical_collision`` is a MuJoCo candidate and is not an Isaac PhysX claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


_VARIANTS = ("constraint_gate", "physical_collision", "no_latch")
_CASE_IDS = tuple(f"seed41001_base{index:03d}__fixed" for index in range(16))


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _number(value: Any, *, field: str, path: Path) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{path}: {field} must be numeric or null")
    return float(value)


def _int(value: Any, *, field: str, path: Path) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{path}: {field} must be an integer")
    return int(value)


def _optional_delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return right - left


def _entry_number(
    entry: Mapping[str, Any] | None,
    names: tuple[str, ...],
    *,
    field: str,
    path: Path,
) -> float | None:
    if entry is None:
        return None
    for name in names:
        if name in entry:
            return _number(entry[name], field=f"stage3_entry.{name}", path=path)
    return None


def _receipt_row(path: Path, expected_case: str, variant: str) -> dict[str, Any]:
    receipt = _read_json(path)
    if receipt.get("case_id") != expected_case:
        raise RuntimeError(f"{path}: case_id does not match directory/expected id {expected_case!r}")
    if receipt.get("lane") != "fixed" or receipt.get("suite") != "primary":
        raise RuntimeError(f"{path}: only primary fixed receipts are accepted")
    if receipt.get("result") != "COMPLETE":
        raise RuntimeError(f"{path}: result is not COMPLETE")

    mechanics = receipt.get("mechanics_diagnostic")
    if not isinstance(mechanics, Mapping):
        raise TypeError(f"{path}: mechanics_diagnostic must be a mapping")
    telemetry = receipt.get("stage2_telemetry_summary")
    if not isinstance(telemetry, Mapping):
        raise TypeError(f"{path}: stage2_telemetry_summary must be a mapping")
    stage = receipt.get("stage")
    if not isinstance(stage, Mapping):
        raise TypeError(f"{path}: stage must be a mapping")

    first_close = telemetry.get("first_close")
    if first_close is not None and not isinstance(first_close, Mapping):
        raise TypeError(f"{path}: stage2_telemetry_summary.first_close must be a mapping or null")
    max_stage = _int(receipt.get("max_stage"), field="max_stage", path=path)
    gate_released = mechanics.get("constraint_gate_released")
    if not isinstance(gate_released, bool):
        raise TypeError(f"{path}: mechanics_diagnostic.constraint_gate_released must be bool")
    stage3_entry = mechanics.get("stage3_entry")
    if stage3_entry is not None and not isinstance(stage3_entry, Mapping):
        raise TypeError(f"{path}: mechanics_diagnostic.stage3_entry must be a mapping or null")

    latch_slide = mechanics.get("max_abs_latch_slide_qpos_m")
    if latch_slide is None:
        latch_slide = mechanics.get("max_latch_slide_qpos_m")
    row = {
        "variant": variant,
        "case_id": expected_case,
        "max_stage": max_stage,
        "goal_reached": bool(receipt.get("goal_reached")),
        "terminal_reason": str(receipt.get("terminal_reason")),
        "stage_control_steps": list(stage.get("stage_control_steps", [])),
        "stage_transition_steps": list(stage.get("transition_steps", [])),
        "both_handle_contact_control_steps": _int(
            telemetry.get("both_handle_contact_control_steps", 0),
            field="both_handle_contact_control_steps",
            path=path,
        ),
        "valid_squeeze_control_steps": _int(
            telemetry.get("valid_squeeze_control_steps", 0),
            field="valid_squeeze_control_steps",
            path=path,
        ),
        "max_squeeze_streak_control_steps": _int(
            telemetry.get("max_squeeze_streak_control_steps", 0),
            field="max_squeeze_streak_control_steps",
            path=path,
        ),
        "first_close": dict(first_close) if first_close is not None else None,
        "first_close_control_step": (
            _int(first_close["control_step"], field="first_close.control_step", path=path)
            if first_close is not None and first_close.get("control_step") is not None
            else None
        ),
        "first_close_tcp_to_grasp_distance_m": (
            _number(first_close.get("tcp_to_grasp_distance_m"), field="first_close.tcp_to_grasp_distance_m", path=path)
            if first_close is not None
            else None
        ),
        "min_tcp_to_grasp_distance_m": _number(
            telemetry.get("min_tcp_to_grasp_distance_m"),
            field="min_tcp_to_grasp_distance_m",
            path=path,
        ),
        "min_tcp_to_pregrasp_distance_m": _number(
            telemetry.get("min_tcp_to_pregrasp_distance_m"),
            field="min_tcp_to_pregrasp_distance_m",
            path=path,
        ),
        "stage3_entry": dict(stage3_entry) if stage3_entry is not None else None,
        "stage3_entry_control_step": (
            _int(stage3_entry["control_step"], field="stage3_entry.control_step", path=path)
            if stage3_entry is not None and stage3_entry.get("control_step") is not None
            else None
        ),
        "stage3_entry_handle_hinge_rad": _entry_number(
            stage3_entry,
            ("handle_hinge_rad", "handle_hinge_qpos_rad", "handle_qpos_rad"),
            field="stage3_entry_handle_hinge_rad",
            path=path,
        ),
        "stage3_entry_door_hinge_rad": _entry_number(
            stage3_entry,
            ("door_hinge_rad", "door_hinge_qpos_rad", "door_qpos_rad"),
            field="stage3_entry_door_hinge_rad",
            path=path,
        ),
        "stage3_entry_latch_slide_qpos_m": _entry_number(
            stage3_entry,
            ("latch_slide_qpos_m", "latch_slide_m", "latch_slide"),
            field="stage3_entry_latch_slide_qpos_m",
            path=path,
        ),
        "constraint_gate_initial_active": mechanics.get("constraint_gate_initial_active"),
        "constraint_gate_final_active": mechanics.get("constraint_gate_final_active"),
        "constraint_gate_released": gate_released,
        "constraint_gate_release_control_step": mechanics.get("constraint_gate_release_control_step"),
        "constraint_gate_release_physics_substep": mechanics.get("constraint_gate_release_physics_substep"),
        "max_handle_hinge_rad": _number(mechanics.get("max_handle_hinge_rad"), field="max_handle_hinge_rad", path=path),
        "max_door_hinge_rad": _number(mechanics.get("max_door_hinge_rad"), field="max_door_hinge_rad", path=path),
        "max_abs_latch_slide_qpos_m": _number(latch_slide, field="max_abs_latch_slide_qpos_m", path=path),
        "mechanics_mode": str(mechanics.get("mode")),
        "receipt_path": str(path),
    }
    if row["mechanics_mode"] != variant:
        raise RuntimeError(f"{path}: mechanics mode {row['mechanics_mode']!r} does not match variant {variant!r}")
    return row


def _load_variant(root: Path, variant: str) -> dict[str, Any]:
    root = root.resolve(strict=True)
    paths = sorted(root.glob("episodes/*/receipt.json"))
    selected = {path.parent.name: path for path in paths if path.parent.name in _CASE_IDS}
    missing = sorted(set(_CASE_IDS) - set(selected))
    if missing:
        raise RuntimeError(f"{variant}: fixed16 receipts incomplete under {root}: {missing}")
    unexpected = sorted(set(selected) - set(_CASE_IDS))
    if unexpected:
        raise RuntimeError(f"{variant}: unexpected selected case ids: {unexpected}")
    rows = {
        case_id: _receipt_row(selected[case_id], case_id, variant)
        for case_id in _CASE_IDS
    }
    return {"variant": variant, "root": str(root), "status": "AVAILABLE", "case_rows": rows}


def _delta(baseline: Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    numeric_fields = (
        "max_stage",
        "both_handle_contact_control_steps",
        "valid_squeeze_control_steps",
        "max_squeeze_streak_control_steps",
        "first_close_control_step",
        "first_close_tcp_to_grasp_distance_m",
        "min_tcp_to_grasp_distance_m",
        "min_tcp_to_pregrasp_distance_m",
        "max_handle_hinge_rad",
        "max_door_hinge_rad",
        "max_abs_latch_slide_qpos_m",
        "stage3_entry_control_step",
        "stage3_entry_handle_hinge_rad",
        "stage3_entry_door_hinge_rad",
        "stage3_entry_latch_slide_qpos_m",
    )
    return {
        "max_stage_delta": observed["max_stage"] - baseline["max_stage"],
        "goal_reached_changed": bool(observed["goal_reached"]) != bool(baseline["goal_reached"]),
        "terminal_reason_changed": observed["terminal_reason"] != baseline["terminal_reason"],
        "constraint_gate_released_changed": bool(observed["constraint_gate_released"]) != bool(baseline["constraint_gate_released"]),
        "numeric_delta_observed_minus_constraint_gate": {
            field: _optional_delta(baseline[field], observed[field])
            for field in numeric_fields
        },
        "terminal_reason": {
            "constraint_gate": baseline["terminal_reason"],
            "observed": observed["terminal_reason"],
        },
        "gate_release": {
            "constraint_gate": baseline["constraint_gate_release_control_step"],
            "observed": observed["constraint_gate_release_control_step"],
        },
        "latch_slide_m": {
            "constraint_gate": baseline["max_abs_latch_slide_qpos_m"],
            "observed": observed["max_abs_latch_slide_qpos_m"],
        },
    }


def _aggregate(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    values = list(rows.values())
    stage_counts = Counter(int(row["max_stage"]) for row in values)
    terminal_counts = Counter(str(row["terminal_reason"]) for row in values)

    def total(field: str) -> int:
        return sum(int(row[field]) for row in values)

    def numeric(field: str) -> dict[str, float | None]:
        available = [float(row[field]) for row in values if row[field] is not None]
        if not available:
            return {"available_count": 0, "min": None, "mean": None, "max": None}
        return {
            "available_count": len(available),
            "min": min(available),
            "mean": sum(available) / len(available),
            "max": max(available),
        }

    return {
        "n_cases": len(values),
        "goal_count": sum(bool(row["goal_reached"]) for row in values),
        "stage_exact_counts": {str(key): value for key, value in sorted(stage_counts.items())},
        "reached_stage3_count": sum(int(row["max_stage"]) >= 3 for row in values),
        "reached_stage4_count": sum(int(row["max_stage"]) >= 4 for row in values),
        "reached_stage5_count": sum(int(row["max_stage"]) >= 5 for row in values),
        "terminal_reason_counts": dict(sorted(terminal_counts.items())),
        "both_handle_contact_control_steps_total": total("both_handle_contact_control_steps"),
        "valid_squeeze_control_steps_total": total("valid_squeeze_control_steps"),
        "max_squeeze_streak_control_steps_max": max(int(row["max_squeeze_streak_control_steps"]) for row in values),
        "first_close_count": sum(row["first_close"] is not None for row in values),
        "stage3_entry_count": sum(row["stage3_entry"] is not None for row in values),
        "stage3_entry_numeric_ranges": {
            field: numeric(field)
            for field in (
                "stage3_entry_control_step",
                "stage3_entry_handle_hinge_rad",
                "stage3_entry_door_hinge_rad",
                "stage3_entry_latch_slide_qpos_m",
            )
        },
        "numeric_ranges": {
            field: numeric(field)
            for field in (
                "first_close_tcp_to_grasp_distance_m",
                "min_tcp_to_grasp_distance_m",
                "min_tcp_to_pregrasp_distance_m",
                "max_handle_hinge_rad",
                "max_door_hinge_rad",
                "max_abs_latch_slide_qpos_m",
            )
        },
        "gate_release_count": sum(bool(row["constraint_gate_released"]) for row in values),
        "gate_release_control_steps": [
            row["constraint_gate_release_control_step"]
            for row in values
            if row["constraint_gate_release_control_step"] is not None
        ],
    }


def _human_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# DepthADD v3 latch mechanics fixed16 comparison",
        "",
        "This report is a matched receipt comparison over seed41001 base000-base015, fixed lane only.",
        "",
        "| Variant | Stage3+ | Stage4+ | Stage5 | Stage3 entries | Goal | Gate release | Both-contact steps | Valid squeeze steps | Max squeeze streak |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in _VARIANTS:
        aggregate = report["variants"][variant]["aggregate"]
        lines.append(
            f"| {variant} | {aggregate['reached_stage3_count']} | {aggregate['reached_stage4_count']} | "
            f"{aggregate['reached_stage5_count']} | {aggregate['stage3_entry_count']} | {aggregate['goal_count']} | "
            f"{aggregate['gate_release_count']} | {aggregate['both_handle_contact_control_steps_total']} | "
            f"{aggregate['valid_squeeze_control_steps_total']} | "
            f"{aggregate['max_squeeze_streak_control_steps_max']} |"
        )
    lines += ["", "## Matched deltas vs constraint_gate", ""]
    for variant in ("physical_collision", "no_latch"):
        lines.append(f"### {variant}")
        lines.append("")
        lines.append("| Case | ΔStage | Goal changed | Terminal changed | Δmin TCP→grasp (m) | ΔStage3 handle (rad) | ΔStage3 door (rad) | ΔStage3 latch slide (m) |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for case_id in _CASE_IDS:
            delta = report["matched_deltas"][variant][case_id]
            numeric = delta["numeric_delta_observed_minus_constraint_gate"]
            fmt = lambda value: "—" if value is None else f"{value:.6g}"
            lines.append(
                f"| {case_id.replace('seed41001_', '')} | {delta['max_stage_delta']:+d} | "
                f"{str(delta['goal_reached_changed']).lower()} | {str(delta['terminal_reason_changed']).lower()} | "
                f"{fmt(numeric['min_tcp_to_grasp_distance_m'])} | "
                f"{fmt(numeric['stage3_entry_handle_hinge_rad'])} | "
                f"{fmt(numeric['stage3_entry_door_hinge_rad'])} | "
                f"{fmt(numeric['stage3_entry_latch_slide_qpos_m'])} |"
            )
    lines += [
        "",
        "## Typed conclusion",
        "",
        "- `no_latch` is a diagnostic upper bound on behavior without the latch gate; it is not a training-equivalent mechanics result.",
        "- `constraint_gate` is not an arbitrary-collision-open model: while the gate remains active, the door hinge is constrained; release requires the configured handle threshold.",
        "- `physical_collision` is a MuJoCo candidate realization only. No Isaac PhysX exact-equivalence claim is made.",
        "- This artifact contains policy eval receipts only; no policy rerun, wall probe, or cross-engine mechanics proof is included.",
    ]
    return "\n".join(lines) + "\n"


def analyze(args: argparse.Namespace) -> None:
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    roots = {
        "constraint_gate": args.constraint_gate_dir,
        "physical_collision": args.physical_collision_dir,
        "no_latch": args.no_latch_dir,
    }
    variants = {name: _load_variant(path, name) for name, path in roots.items()}
    baseline = variants["constraint_gate"]["case_rows"]
    matched_deltas: dict[str, dict[str, Any]] = {}
    for variant in ("physical_collision", "no_latch"):
        matched_deltas[variant] = {
            case_id: _delta(baseline[case_id], variants[variant]["case_rows"][case_id])
            for case_id in _CASE_IDS
        }
    report = {
        "schema": "doordog.sim2sim.depthadd_v3.latch_mechanics_fixed16_analysis.v1",
        "result": "LATCH_MECHANICS_FIXED16_ANALYSIS_COMPLETE",
        "evidence_level": "RUNTIME_RECEIPT_ANALYSIS",
        "scope": "matched seed41001 base000-base015 primary fixed receipts",
        "case_ids": list(_CASE_IDS),
        "variants": {
            name: {
                "root": value["root"],
                "status": value["status"],
                "case_rows": value["case_rows"],
                "aggregate": _aggregate(value["case_rows"]),
            }
            for name, value in variants.items()
        },
        "matched_deltas": matched_deltas,
        "typed_conclusion": {
            "no_latch": "DIAGNOSTIC_UPPER_BOUND_NOT_TRAINING_SEMANTICS",
            "constraint_gate": "NOT_ARBITRARY_COLLISION_OPEN;_HANDLE_THRESHOLD_GATE",
            "physical_collision": "MUJOCO_CANDIDATE_NO_PHYSX_EXACT_CLAIM",
            "policy_rerun": "NOT_RUN_BY_ANALYZER",
            "wall_probe_20m": "NOT_RUN",
        },
    }
    output.mkdir(parents=True)
    (output / "latch_mechanics_fixed16_analysis.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "LATCH_MECHANICS_FIXED16_ANALYSIS.md").write_text(
        _human_report(report), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--constraint-gate-dir", type=Path, required=True)
    parser.add_argument("--physical-collision-dir", type=Path, required=True)
    parser.add_argument("--no-latch-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    analyze(parser.parse_args())


if __name__ == "__main__":
    main()
