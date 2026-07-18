"""Headless, eval-only static reachability map for A2_Piper v14.

The module deliberately keeps IsaacLab imports inside :func:`_run_isaaclab`.  The
pure grid, feasibility, and summary functions are therefore usable by tests and
``python ... --help`` without starting Isaac Sim.

This map is a diagnostic of static placements.  ``root_height_m`` is a placed
root pose used by the diagnostic; it is not an action or a command dimension.
The requested handle/standoff/root grids are fixed by the v14 plan and are not
configurable from this CLI.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_USD_PATH = REPO_ROOT / "gr00t/rl/data/robots/A2_Piper/a2_piper.usd"

HANDLE_HEIGHTS_M = tuple(round(0.80 + 0.05 * index, 2) for index in range(7))
STANDOFFS_M = tuple(round(0.40 + 0.05 * index, 2) for index in range(10))
ROOT_HEIGHTS_M = (0.55, 0.65, 0.75)
TCP_ERROR_TOLERANCE_M = 0.03
JOINT_MARGIN_THRESHOLD_RAD = 0.10
HIGH_HANDLE_HEIGHT_THRESHOLD_M = 1.00
HIGH_ROOT_HEIGHT_THRESHOLD_M = 0.70
GRID_DECIMAL_PLACES = 2
STATIC_DOOR_GEOMETRY = {
    "door_width_m": 0.95,
    "door_height_m": 2.05,
    "handle_width_m": 0.115,
    "door_weight_kg": 100.0,
    "axle_length_m": 0.195,
    "handle_length_m": 0.125,
    "hook_length_m": 0.05,
    "handle_radius_m": 0.013,
    "spawn_hook": False,
    "hinge_drive_max_force": 4.75,
    "hinge_drive_stiffness": 5.5,
    "handle_drive_max_force": 2.0,
    "collision_enabled_for_m18": False,
}
M18_ROBOT_BODY_NAMES = (
    "trunk",
    "FL_hip",
    "FL_thigh",
    "FL_calf",
    "FL_foot",
    "FR_hip",
    "FR_thigh",
    "FR_calf",
    "FR_foot",
    "RL_hip",
    "RL_thigh",
    "RL_calf",
    "RL_foot",
    "RR_hip",
    "RR_thigh",
    "RR_calf",
    "RR_foot",
    "arm_body0",
    "arm_body1",
    "arm_body2",
    "arm_body3",
    "arm_body4",
    "arm_body5",
    "arm_body6",
    "arm_body6_to_gripper",
    "arm_body7",
    "arm_body8",
)
M18_ARM_BODY_NAMES = (
    "arm_body0",
    "arm_body1",
    "arm_body2",
    "arm_body3",
    "arm_body4",
    "arm_body5",
    "arm_body6",
    "arm_body6_to_gripper",
    "arm_body7",
    "arm_body8",
)
SUMMARY_TIE_RULE = (
    "Choose the highest handle-height cap with a non-empty band; within that cap "
    "choose the longest continuous standoff band; ties choose the lowest band start."
)
CELL_CSV_FIELDNAMES = (
    "handle_height_m",
    "standoff_m",
    "root_height_m",
    "tcp_error_m",
    "self_collision",
    "self_collision_evidence",
    "min_joint_limit_margin_rad",
    "arm_j6_margin_rad",
    "feasible",
    "failure_reason",
)


@dataclass(frozen=True)
class GridCell:
    """One requested static placement and its measured evidence."""

    handle_height_m: float
    standoff_m: float
    root_height_m: float
    tcp_error_m: float | None
    self_collision: bool | None
    self_collision_evidence: str | None
    min_joint_limit_margin_rad: float | None
    arm_j6_margin_rad: float | None


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _canonical_grid_value(value: float) -> float:
    return round(float(value), GRID_DECIMAL_PLACES)


def build_grid_cells() -> list[tuple[float, float, float]]:
    """Return the exact v14 M18 Cartesian product in deterministic order."""

    return [
        (handle_height, standoff, root_height)
        for handle_height in HANDLE_HEIGHTS_M
        for standoff in STANDOFFS_M
        for root_height in ROOT_HEIGHTS_M
    ]


def select_grid_cells(
    handle_height_m: float | None,
    root_height_m: float | None = None,
    standoff_m: float | None = None,
) -> list[tuple[float, float, float]]:
    """Select a handle, root-height, or exact single-cell shard."""

    cells = build_grid_cells()
    if handle_height_m is None:
        if root_height_m is not None or standoff_m is not None:
            raise ValueError("M18 root-height/standoff shards require --handle-height.")
        return cells
    if not _is_finite_number(handle_height_m):
        raise ValueError("M18 shard handle height must be finite.")
    selected_handle_height = _canonical_grid_value(handle_height_m)
    if selected_handle_height not in HANDLE_HEIGHTS_M:
        raise ValueError(
            f"M18 shard handle height must be one of {list(HANDLE_HEIGHTS_M)}; "
            f"got {handle_height_m}."
        )
    selected = [cell for cell in cells if cell[0] == selected_handle_height]
    if root_height_m is None:
        if standoff_m is not None:
            raise ValueError("M18 standoff shards require --root-height.")
        return selected
    if not _is_finite_number(root_height_m):
        raise ValueError("M18 shard root height must be finite.")
    selected_root_height = _canonical_grid_value(root_height_m)
    if selected_root_height not in ROOT_HEIGHTS_M:
        raise ValueError(
            f"M18 shard root height must be one of {list(ROOT_HEIGHTS_M)}; "
            f"got {root_height_m}."
        )
    selected = [cell for cell in selected if cell[2] == selected_root_height]
    if standoff_m is None:
        return selected
    if not _is_finite_number(standoff_m):
        raise ValueError("M18 shard standoff must be finite.")
    selected_standoff = _canonical_grid_value(standoff_m)
    if selected_standoff not in STANDOFFS_M:
        raise ValueError(
            f"M18 shard standoff must be one of {list(STANDOFFS_M)}; got {standoff_m}."
        )
    return [cell for cell in selected if cell[1] == selected_standoff]


def assess_cell(
    cell: GridCell,
    *,
    tcp_error_tolerance_m: float = TCP_ERROR_TOLERANCE_M,
    joint_margin_threshold_rad: float = JOINT_MARGIN_THRESHOLD_RAD,
) -> tuple[bool, tuple[str, ...]]:
    """Apply the strict M18 feasibility rule without fabricating missing evidence."""

    reasons: list[str] = []
    for name, value in (
        ("handle_height_m", cell.handle_height_m),
        ("standoff_m", cell.standoff_m),
        ("root_height_m", cell.root_height_m),
        ("tcp_error_m", cell.tcp_error_m),
        ("min_joint_limit_margin_rad", cell.min_joint_limit_margin_rad),
        ("arm_j6_margin_rad", cell.arm_j6_margin_rad),
    ):
        if not _is_finite_number(value):
            reasons.append(f"missing_or_nonfinite:{name}")

    if not isinstance(cell.self_collision, bool):
        reasons.append("missing_or_invalid:self_collision")
    if not isinstance(cell.self_collision_evidence, str) or not cell.self_collision_evidence.strip():
        reasons.append("missing_or_invalid:self_collision_evidence")

    if not _is_finite_number(tcp_error_tolerance_m) or float(tcp_error_tolerance_m) <= 0.0:
        raise ValueError("tcp_error_tolerance_m must be finite and positive.")
    if not _is_finite_number(joint_margin_threshold_rad):
        raise ValueError("joint_margin_threshold_rad must be finite.")

    if not reasons:
        if float(cell.tcp_error_m) >= float(tcp_error_tolerance_m):
            reasons.append("tcp_error_not_below_tolerance")
        if cell.self_collision:
            reasons.append("self_collision_detected")
        if float(cell.min_joint_limit_margin_rad) <= float(joint_margin_threshold_rad):
            reasons.append("joint_limit_margin_not_above_threshold")

    return not reasons, tuple(reasons)


def _validate_cell_set(cells: Sequence[GridCell]) -> tuple[list[float], list[float], list[float]]:
    if not cells:
        raise ValueError("Reachability evidence is empty.")
    keys: set[tuple[float, float, float]] = set()
    handles: set[float] = set()
    standoffs: set[float] = set()
    roots: set[float] = set()
    for cell in cells:
        key = (
            _canonical_grid_value(cell.handle_height_m),
            _canonical_grid_value(cell.standoff_m),
            _canonical_grid_value(cell.root_height_m),
        )
        if key in keys:
            raise ValueError(f"Duplicate reachability cell: {key}.")
        keys.add(key)
        handles.add(key[0])
        standoffs.add(key[1])
        roots.add(key[2])
    return sorted(handles), sorted(standoffs), sorted(roots)


def _continuous_runs(values: Sequence[float], allowed: Sequence[bool]) -> list[tuple[float, float, tuple[float, ...]]]:
    if len(values) != len(allowed):
        raise ValueError("Continuous-run values and masks must have equal length.")
    runs: list[tuple[float, float, tuple[float, ...]]] = []
    start: int | None = None
    for index, is_allowed in enumerate(allowed + [False]):
        if is_allowed and start is None:
            start = index
        if not is_allowed and start is not None:
            run_values = tuple(values[start:index])
            runs.append((run_values[0], run_values[-1], run_values))
            start = None
    return runs


def summarize_reachability(cells: Sequence[GridCell]) -> dict[str, Any]:
    """Summarize a complete or test-sized grid with deterministic cap/band selection.

    A handle/standoff cell is usable when *any* requested static root height is
    feasible.  For each candidate handle cap, all handle heights at or below the
    cap must be usable at every standoff in the selected continuous band.
    """

    handles, standoffs, roots = _validate_cell_set(cells)
    evidence: dict[tuple[float, float, float], tuple[bool, tuple[str, ...]]] = {}
    for cell in cells:
        key = (
            _canonical_grid_value(cell.handle_height_m),
            _canonical_grid_value(cell.standoff_m),
            _canonical_grid_value(cell.root_height_m),
        )
        evidence[key] = assess_cell(cell)

    expected_keys = {
        (handle, standoff, root)
        for handle in handles
        for standoff in standoffs
        for root in roots
    }
    missing = sorted(expected_keys - set(evidence))
    if missing:
        raise ValueError(f"Reachability evidence is incomplete; missing cells: {missing}.")

    any_root_feasible: dict[tuple[float, float], bool] = {}
    for handle in handles:
        for standoff in standoffs:
            any_root_feasible[(handle, standoff)] = any(
                evidence[(handle, standoff, root)][0] for root in roots
            )

    selected_cap: float | None = None
    selected_band: tuple[float, float, tuple[float, ...]] | None = None
    for candidate_cap in handles:
        retained_handles = [handle for handle in handles if handle <= candidate_cap + 1.0e-9]
        allowed_standoffs = [
            all(any_root_feasible[(handle, standoff)] for handle in retained_handles)
            for standoff in standoffs
        ]
        runs = _continuous_runs(standoffs, allowed_standoffs)
        if not runs:
            continue
        best_for_cap = sorted(runs, key=lambda run: (-len(run[2]), run[0], run[1]))[0]
        if selected_cap is None:
            selected_cap = candidate_cap
            selected_band = best_for_cap
            continue
        if candidate_cap > selected_cap + 1.0e-9:
            selected_cap = candidate_cap
            selected_band = best_for_cap
        elif candidate_cap == selected_cap and selected_band is not None:
            selected_band = sorted(
                (selected_band, best_for_cap),
                key=lambda run: (-len(run[2]), run[0], run[1]),
            )[0]

    max_grid_handle = max(HANDLE_HEIGHTS_M)
    one_ten_allowed = any(
        any_root_feasible.get((max_grid_handle, standoff), False) for standoff in standoffs
    )
    feasible_cell_count = sum(decision[0] for decision in evidence.values())
    handle_any_feasible = {
        str(handle): any(any_root_feasible[(handle, standoff)] for standoff in standoffs)
        for handle in handles
    }
    minimum_feasible_root_height_by_handle = {}
    for handle in handles:
        feasible_roots = [
            root
            for root in roots
            if any(evidence[(handle, standoff, root)][0] for standoff in standoffs)
        ]
        minimum_feasible_root_height_by_handle[str(handle)] = (
            min(feasible_roots) if feasible_roots else None
        )

    if selected_cap is None or selected_band is None:
        band_start = None
        band_end = None
        band_values: tuple[float, ...] = ()
        retained_handles: list[float] = []
    else:
        band_start, band_end, band_values = selected_band
        retained_handles = [handle for handle in handles if handle <= selected_cap + 1.0e-9]

    retained_high_handles = [
        handle
        for handle in retained_handles
        if handle >= HIGH_HANDLE_HEIGHT_THRESHOLD_M - 1.0e-9
    ]
    if retained_high_handles:
        retained_high_handles_require_high_root = all(
            minimum_feasible_root_height_by_handle[str(handle)] is not None
            and minimum_feasible_root_height_by_handle[str(handle)]
            >= HIGH_ROOT_HEIGHT_THRESHOLD_M - 1.0e-9
            for handle in retained_high_handles
        )
    else:
        retained_high_handles_require_high_root = None

    return {
        "schema": "a2_piper_v14_reachability_summary_v1",
        "option_a": {
            "root_height_semantics": "static diagnostic placement; not an action or command dimension",
            "actor_action_dimensions_unchanged": "12D actor / 5D [vx, vy, yaw, pitch, roll]",
        },
        "grid": {
            "handle_heights_m": handles,
            "standoffs_m": standoffs,
            "root_heights_m": roots,
            "cells": len(cells),
            "static_door_geometry": dict(STATIC_DOOR_GEOMETRY),
        },
        "feasibility_rule": {
            "tcp_error_strict_less_than_m": TCP_ERROR_TOLERANCE_M,
            "self_collision": "false",
            "min_joint_limit_margin_strict_greater_than_rad": JOINT_MARGIN_THRESHOLD_RAD,
            "missing_or_nonfinite_evidence": "infeasible",
        },
        "feasible_cell_count": feasible_cell_count,
        "infeasible_cell_count": len(cells) - feasible_cell_count,
        "handle_height_any_feasible": handle_any_feasible,
        "minimum_feasible_root_height_by_handle_m": minimum_feasible_root_height_by_handle,
        "selection": {
            "highest_feasible_handle_cap_m": selected_cap,
            "one_point_ten_m_allowed": one_ten_allowed,
            "retained_handle_heights_m": retained_handles,
            "retained_high_handle_threshold_m": HIGH_HANDLE_HEIGHT_THRESHOLD_M,
            "retained_high_handles_m": retained_high_handles,
            "retained_high_handles_require_root_height_ge_0_7": (
                retained_high_handles_require_high_root
            ),
            "maximal_continuous_standoff_band_m": {
                "start": band_start,
                "end": band_end,
                "values": list(band_values),
                "count": len(band_values),
            },
            "tie_rule": SUMMARY_TIE_RULE,
        },
    }


def _cell_record(cell: GridCell) -> dict[str, Any]:
    feasible, reasons = assess_cell(cell)
    record = asdict(cell)
    record["feasible"] = feasible
    record["failure_reason"] = ";".join(reasons) if reasons else ""
    return record


def read_reachability_csvs(csv_paths: Sequence[Path]) -> list[GridCell]:
    """Read strict per-height evidence and require the exact complete M18 grid."""

    if not csv_paths:
        raise ValueError("M18 merge requires at least one CSV path.")

    cells: list[GridCell] = []
    for csv_path_value in csv_paths:
        csv_path = Path(csv_path_value)
        if not csv_path.is_file():
            raise FileNotFoundError(f"M18 shard CSV not found: {csv_path}")
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(CELL_CSV_FIELDNAMES):
                raise ValueError(
                    f"M18 shard CSV header mismatch for {csv_path}: "
                    f"expected={list(CELL_CSV_FIELDNAMES)}, actual={reader.fieldnames}."
                )
            for row in reader:
                collision_text = row["self_collision"]
                if collision_text not in ("True", "False"):
                    raise ValueError(
                        f"M18 shard CSV has invalid self_collision at "
                        f"{csv_path}:{reader.line_num}: {collision_text!r}."
                    )
                try:
                    cell = GridCell(
                        handle_height_m=float(row["handle_height_m"]),
                        standoff_m=float(row["standoff_m"]),
                        root_height_m=float(row["root_height_m"]),
                        tcp_error_m=float(row["tcp_error_m"]),
                        self_collision=collision_text == "True",
                        self_collision_evidence=row["self_collision_evidence"],
                        min_joint_limit_margin_rad=float(row["min_joint_limit_margin_rad"]),
                        arm_j6_margin_rad=float(row["arm_j6_margin_rad"]),
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"M18 shard CSV has invalid numeric evidence at "
                        f"{csv_path}:{reader.line_num}."
                    ) from exc
                derived = _cell_record(cell)
                if (
                    row["feasible"] != str(derived["feasible"])
                    or row["failure_reason"] != derived["failure_reason"]
                ):
                    raise ValueError(
                        f"M18 shard CSV derived decision mismatch at "
                        f"{csv_path}:{reader.line_num}."
                    )
                cells.append(cell)

    _validate_cell_set(cells)
    expected_specs = build_grid_cells()
    expected_keys = set(expected_specs)
    actual_by_key = {
        (
            cell.handle_height_m,
            cell.standoff_m,
            cell.root_height_m,
        ): cell
        for cell in cells
    }
    actual_keys = set(actual_by_key)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        unexpected = sorted(actual_keys - expected_keys)
        raise ValueError(
            "M18 merged evidence does not match the exact 210-cell grid: "
            f"missing={missing}, unexpected={unexpected}."
        )
    return [actual_by_key[spec] for spec in expected_specs]


def write_reachability_outputs(
    output_dir: Path,
    cells: Sequence[GridCell],
    summary: dict[str, Any],
    *,
    stem: str = "a2_piper_v14_reachability_map",
) -> tuple[Path, Path, Path]:
    """Write cell CSV plus JSON/Markdown summary to the explicit output directory."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{stem}.csv"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"

    records = [_cell_record(cell) for cell in cells]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CELL_CSV_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)

    json_payload = dict(summary)
    json_payload["csv_evidence_path"] = csv_path.name
    json_path.write_text(json.dumps(json_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    selection = summary["selection"]
    band = selection["maximal_continuous_standoff_band_m"]
    minimum_roots = summary["minimum_feasible_root_height_by_handle_m"]
    markdown = "\n".join(
        [
            "# A2_Piper v14 M18 static reachability map",
            "",
            "Option A: root/body heights are static diagnostic placements, not action/command dimensions.",
            "",
            f"- Cell evidence: `{csv_path.name}`",
            f"- Cells: `{summary['grid']['cells']}`; feasible: `{summary['feasible_cell_count']}`",
            f"- Highest feasible handle cap: `{selection['highest_feasible_handle_cap_m']}` m",
            f"- 1.10 m allowed: `{selection['one_point_ten_m_allowed']}`",
            f"- Selected standoff band: `{band['start']}`–`{band['end']}` m ({band['count']} grid points)",
            "- Retained high handles (>=1.00 m) require root height >=0.70 m: "
            f"`{selection['retained_high_handles_require_root_height_ge_0_7']}`",
            "",
            "## Per-handle summary",
            "",
            "| Handle height (m) | Any feasible cell | Minimum feasible root height (m) |",
            "| ---: | :---: | ---: |",
            *[
                f"| `{handle}` | `{summary['handle_height_any_feasible'][str(handle)]}` | "
                f"`{minimum_roots[str(handle)]}` |"
                for handle in summary["grid"]["handle_heights_m"]
            ],
            "",
            "## Feasibility rule",
            "",
            "`tcp_error_m < 0.03` and `self_collision == false` and `min_joint_limit_margin_rad > 0.1`; missing/nonfinite evidence is infeasible.",
            "",
            "## Deterministic selection",
            "",
            SUMMARY_TIE_RULE,
            "",
        ]
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    return csv_path, json_path, markdown_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the headless A2_Piper v14 M18 static reachability grid. "
            "The root heights are diagnostic placements only."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Explicit directory for CSV evidence and JSON/Markdown summary outputs.",
    )
    run_mode = parser.add_mutually_exclusive_group()
    run_mode.add_argument(
        "--handle-height",
        type=float,
        choices=HANDLE_HEIGHTS_M,
        help="Run one exact 30-cell handle-height shard instead of all 210 cells.",
    )
    run_mode.add_argument(
        "--merge-csv",
        type=Path,
        nargs="+",
        help="Merge shard CSVs into the exact 210-cell final evidence without Isaac Sim.",
    )
    parser.add_argument(
        "--root-height",
        type=float,
        choices=ROOT_HEIGHTS_M,
        help="Further split a handle-height run into one exact 10-cell root-height shard.",
    )
    parser.add_argument(
        "--standoff",
        type=float,
        choices=STANDOFFS_M,
        help="Further split a handle/root run into one exact diagnostic cell.",
    )
    parser.add_argument(
        "--usd-file",
        type=Path,
        default=DEFAULT_USD_PATH,
        help="A2_Piper USD used by the high-level Articulation scene.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="IsaacLab SimulationContext device (default: cpu).",
    )
    parser.add_argument(
        "--ik-steps",
        type=int,
        default=120,
        help="Number of bounded DLS placement steps per grid cell (default: 120).",
    )
    parser.add_argument(
        "--dls-lambda",
        type=float,
        default=0.01,
        help="DifferentialIKController DLS lambda (default: 0.01).",
    )
    parser.add_argument(
        "--max-position-step-m",
        type=float,
        default=0.002,
        help="Per-step Cartesian position bound used by existing A2 placement machinery.",
    )
    parser.add_argument(
        "--max-orientation-step-rad",
        type=float,
        default=0.02,
        help="Per-step orientation bound used by existing A2 placement machinery.",
    )
    parser.add_argument(
        "--self-collision-force-threshold-n",
        type=float,
        default=1.0,
        help="Final-state robot self-contact force threshold for the self-collision boolean.",
    )
    parser.add_argument(
        "--output-stem",
        default="a2_piper_v14_reachability_map",
        help="Stem for the three output files.",
    )
    return parser.parse_args(argv)


def _require_runtime_finite(name: str, value: Any) -> None:
    if not hasattr(value, "is_floating_point") or not value.is_floating_point():
        raise RuntimeError(f"M18 runtime evidence {name} must be a floating tensor.")
    if not bool(value.isfinite().all().item()):
        raise RuntimeError(f"M18 runtime evidence {name} contains nonfinite values.")


def _build_reachability_door_cfg(specs: Sequence[tuple[float, float, float]]):
    """Build heterogeneous high-level door configs with exact requested heights."""

    import copy

    from isaaclab.sim import CollisionPropertiesCfg, MultiAssetSpawnerCfg

    from gr00t.rl.envs.door.a2_piper_door_scene_preview import build_doorman_door_cfg

    door_cfg = build_doorman_door_cfg(len(specs))
    if not isinstance(door_cfg.spawn, MultiAssetSpawnerCfg):
        raise RuntimeError("M18 requires the repository MultiAssetSpawnerCfg door route.")
    if not door_cfg.spawn.assets_cfg:
        raise RuntimeError("M18 door config has no asset configs.")
    template = copy.deepcopy(door_cfg.spawn.assets_cfg[0])
    handle_heights = {_canonical_grid_value(spec[0]) for spec in specs}
    asset_specs = specs[:1] if len(handle_heights) == 1 else specs
    assets = []
    for handle_height, _standoff, _root_height in asset_specs:
        asset_cfg = copy.deepcopy(template)
        asset_cfg.rand_door_width = STATIC_DOOR_GEOMETRY["door_width_m"]
        asset_cfg.rand_door_height = STATIC_DOOR_GEOMETRY["door_height_m"]
        asset_cfg.rand_door_handle_height = handle_height
        asset_cfg.rand_door_handle_width = STATIC_DOOR_GEOMETRY["handle_width_m"]
        asset_cfg.rand_door_weight = STATIC_DOOR_GEOMETRY["door_weight_kg"]
        asset_cfg.rand_door_handle_type = "lever"
        asset_cfg.rand_door_open_lr = "right"
        asset_cfg.rand_door_open_io = "out"
        asset_cfg.rand_total_wall_height = 2.70
        asset_cfg.rand_axle_length = STATIC_DOOR_GEOMETRY["axle_length_m"]
        asset_cfg.rand_handle_length = STATIC_DOOR_GEOMETRY["handle_length_m"]
        asset_cfg.rand_hook_length = STATIC_DOOR_GEOMETRY["hook_length_m"]
        asset_cfg.rand_handle_radius = STATIC_DOOR_GEOMETRY["handle_radius_m"]
        asset_cfg.rand_spawn_hook = STATIC_DOOR_GEOMETRY["spawn_hook"]
        asset_cfg.rand_hinge_drive_max_force = STATIC_DOOR_GEOMETRY["hinge_drive_max_force"]
        asset_cfg.rand_hinge_drive_stiffness = STATIC_DOOR_GEOMETRY["hinge_drive_stiffness"]
        asset_cfg.rand_handle_drive_max_force = STATIC_DOOR_GEOMETRY["handle_drive_max_force"]
        asset_cfg.randomize_material = False
        asset_cfg.use_preloaded_materials = False
        asset_cfg.dynamic_material_randomization = False
        asset_cfg.collision_props = CollisionPropertiesCfg(collision_enabled=False)
        asset_cfg.activate_contact_sensors = False
        assets.append(asset_cfg)
    door_cfg.spawn.assets_cfg = assets
    door_cfg.spawn.random_choice = False
    door_cfg.spawn.activate_contact_sensors = False
    return door_cfg


def _make_runtime_scene(*, usd_path: Path, specs: Sequence[tuple[float, float, float]], device: str):
    """Create the high-level scene and ordered target frame sensor."""

    import isaaclab.sim as sim_utils
    import torch
    from isaaclab.assets import ArticulationCfg
    from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
    from isaaclab.sensors import FrameTransformerCfg
    from isaaclab.sensors.frame_transformer import OffsetCfg
    from isaaclab.sim import SimulationContext
    from isaaclab.utils import configclass

    from gr00t.rl.envs.door.a2_piper_door_scene_preview import build_a2_piper_robot_cfg
    from gr00t.rl.envs.door.door_open_a2_base import OrderedTargetFrameTransformer

    robot_cfg = build_a2_piper_robot_cfg(
        usd_path=usd_path,
        root_x=0.0,
        root_y=0.0,
        root_z=ROOT_HEIGHTS_M[0],
        root_yaw=0.0,
    )
    robot_cfg.spawn.activate_contact_sensors = True
    door_cfg = _build_reachability_door_cfg(specs)

    target_path = "/World/envs/env_.*/door/grasp_target"
    tcp_frame_cfg = FrameTransformerCfg(
        prim_path="/World/envs/env_.*/Robot/arm_body6_to_gripper",
        source_frame_offset=OffsetCfg(pos=(0.0, 0.0, 0.085)),
        target_frames=[
            FrameTransformerCfg.FrameCfg(
                prim_path=target_path,
                name="handle",
                offset=OffsetCfg(rot=(0.5, 0.5, 0.5, 0.5)),
            ),
            FrameTransformerCfg.FrameCfg(
                prim_path=target_path,
                name="pregrasp",
                offset=OffsetCfg(pos=(-0.10, 0.0, 0.0), rot=(0.5, 0.5, 0.5, 0.5)),
            ),
        ],
    )
    tcp_frame_cfg.class_type = OrderedTargetFrameTransformer

    @configclass
    class ReachabilitySceneCfg(InteractiveSceneCfg):
        robot: ArticulationCfg = robot_cfg.replace(prim_path="{ENV_REGEX_NS}/Robot")
        door: ArticulationCfg = door_cfg.replace(prim_path="{ENV_REGEX_NS}/door")
        tcp_handle_frames = tcp_frame_cfg

    sim = SimulationContext(sim_utils.SimulationCfg(dt=0.005, device=device))
    scene = InteractiveScene(
        ReachabilitySceneCfg(
            num_envs=len(specs),
            env_spacing=3.0,
            replicate_physics=False,
        )
    )
    return sim, scene, torch


def _write_static_root_poses(robot, root_state_local, env_origins) -> None:
    root_state_world = root_state_local.clone()
    root_state_world[:, :3] += env_origins
    robot.write_root_pose_to_sim(root_state_world[:, :7])
    robot.write_root_velocity_to_sim(torch_zeros_like(root_state_world[:, 7:]))


def torch_zeros_like(value):
    """Resolve torch lazily for the runtime-only root writer."""

    import torch

    return torch.zeros_like(value)


def _runtime_tensor_contract(name: str, value, shape: tuple[int, ...]) -> None:
    if tuple(value.shape) != shape or not value.is_floating_point():
        raise RuntimeError(f"M18 runtime {name} shape/dtype mismatch: expected {shape}, got {tuple(value.shape)}.")
    _require_runtime_finite(name, value)


def _soft_joint_margins(robot, joint_ids):
    q = robot.data.joint_pos[:, joint_ids]
    limits = robot.data.soft_joint_pos_limits[:, joint_ids]
    if tuple(limits.shape) != (q.shape[0], q.shape[1], 2):
        raise RuntimeError(f"M18 soft joint-limit shape mismatch: got {tuple(limits.shape)}.")
    _require_runtime_finite("joint_pos", q)
    _require_runtime_finite("soft_joint_pos_limits", limits)
    margins = torch_minimum(q - limits[..., 0], limits[..., 1] - q)
    _require_runtime_finite("joint_limit_margins", margins)
    return margins


def torch_minimum(left, right):
    import torch

    return torch.minimum(left, right)


def _parse_m18_robot_actor_path(actor_path: str) -> tuple[int, str] | None:
    """Parse one exact M18 robot rigid-body actor path."""

    if not isinstance(actor_path, str) or not actor_path:
        raise RuntimeError(f"M18 contact actor path must be a non-empty string; got {actor_path!r}.")
    parts = actor_path.strip("/").split("/")
    if len(parts) < 4 or parts[:2] != ["World", "envs"] or parts[3] != "Robot":
        return None
    if len(parts) != 5:
        raise RuntimeError(f"M18 robot contact actor path has unexpected structure: {actor_path}.")
    env_token = parts[2]
    if not env_token.startswith("env_") or not env_token[4:].isdigit():
        raise RuntimeError(f"M18 robot contact actor path has invalid env token: {actor_path}.")
    body_name = parts[4]
    if body_name not in M18_ROBOT_BODY_NAMES:
        raise RuntimeError(f"M18 contact actor has unknown robot body: {actor_path}.")
    return int(env_token[4:]), body_name


def _collect_physx_self_collision(
    *, num_envs: int, sim_dt: float, threshold_n: float
) -> tuple[list[bool], list[float], list[str]]:
    """Read the just-completed final step from PhysX contact reports.

    IsaacLab's high-level ContactSensor view is intentionally not instantiated
    here: on this Isaac Sim 5.1 runtime, even one exact body in one environment
    does not finish view initialization.  The robot is still spawned with the
    high-level ``activate_contact_sensors`` contract.  After a normal final
    physics step, this function synchronously reads those existing reports via
    the PhysX API used by the installed official contact-report utility.
    """

    if num_envs <= 0:
        raise ValueError("M18 contact collection requires at least one environment.")
    if not _is_finite_number(sim_dt) or float(sim_dt) <= 0.0:
        raise ValueError("M18 contact collection sim_dt must be finite and positive.")
    if not _is_finite_number(threshold_n) or float(threshold_n) <= 0.0:
        raise ValueError("self-collision force threshold must be finite and positive.")

    from omni.physx import get_physx_simulation_interface
    from omni.physx.bindings._physx import ContactEventType
    from pxr import PhysicsSchemaTools

    print("[M18] reading final PhysX contact report", flush=True)
    contact_headers, contact_data = get_physx_simulation_interface().get_contact_report()
    print(f"[M18] contact report read: {len(contact_headers)} header(s)", flush=True)
    max_force_n = [0.0] * num_envs
    source_pair = ["none"] * num_envs
    for header in contact_headers:
        if header.type == ContactEventType.CONTACT_LOST:
            continue
        if header.type not in (ContactEventType.CONTACT_FOUND, ContactEventType.CONTACT_PERSIST):
            raise RuntimeError(f"M18 received unknown contact event type: {header.type}.")

        actor_path_0 = str(PhysicsSchemaTools.intToSdfPath(header.actor0))
        actor_path_1 = str(PhysicsSchemaTools.intToSdfPath(header.actor1))
        actor_0 = _parse_m18_robot_actor_path(actor_path_0)
        actor_1 = _parse_m18_robot_actor_path(actor_path_1)
        if actor_0 is None and actor_1 is None:
            continue
        if actor_0 is None or actor_1 is None:
            raise RuntimeError(
                "M18 isolated scene reported a robot-to-nonrobot contact: "
                f"actor0={actor_path_0}, actor1={actor_path_1}."
            )
        if actor_0[0] != actor_1[0]:
            raise RuntimeError(
                "M18 isolated scene reported a cross-environment robot contact: "
                f"actor0={actor_path_0}, actor1={actor_path_1}."
            )
        env_id = actor_0[0]
        if env_id < 0 or env_id >= num_envs:
            raise RuntimeError(f"M18 contact env id {env_id} is outside [0, {num_envs}).")
        body_0, body_1 = actor_0[1], actor_1[1]
        if body_0 not in M18_ARM_BODY_NAMES and body_1 not in M18_ARM_BODY_NAMES:
            continue

        offset = int(header.contact_data_offset)
        count = int(header.num_contact_data)
        if offset < 0 or count <= 0 or offset + count > len(contact_data):
            raise RuntimeError(
                "M18 active contact header has invalid contact-data bounds: "
                f"offset={offset}, count={count}, available={len(contact_data)}."
            )
        impulse = [0.0, 0.0, 0.0]
        for contact_index in range(offset, offset + count):
            contact_impulse = contact_data[contact_index].impulse
            components = [float(contact_impulse[axis]) for axis in range(3)]
            if not all(math.isfinite(component) for component in components):
                raise RuntimeError(f"M18 contact impulse contains nonfinite values: {components}.")
            for axis, component in enumerate(components):
                impulse[axis] += component
        force_n = math.sqrt(sum(component * component for component in impulse)) / float(sim_dt)
        if not math.isfinite(force_n):
            raise RuntimeError(f"M18 contact force is nonfinite: {force_n}.")
        if force_n > max_force_n[env_id]:
            max_force_n[env_id] = force_n
            source_pair[env_id] = "<->".join(sorted((body_0, body_1)))

    collision = [force >= float(threshold_n) for force in max_force_n]
    return collision, max_force_n, source_pair

def _run_ik_runtime(args: argparse.Namespace, specs: Sequence[tuple[float, float, float]]) -> list[GridCell]:
    """Run the IsaacLab-only portion after the SimulationApp has been created."""

    import torch
    from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
    from isaaclab.utils.math import subtract_frame_transforms

    from gr00t.rl.envs.door.door_open_a2_base import (
        a2_hold_apply_source_offset_to_jacobian,
        a2_hold_bound_pose_command_step,
        a2_hold_rotate_jacobian_to_root,
    )

    print(f"[M18] building scene for {len(specs)} cell(s)", flush=True)
    sim, scene, _torch_module = _make_runtime_scene(
        usd_path=args.usd_file,
        specs=specs,
        device=args.device,
    )
    print("[M18] scene built; initializing simulation views", flush=True)
    robot = scene.articulations["robot"]
    frame_sensor = scene.sensors["tcp_handle_frames"]
    sim.reset()
    print("[M18] simulation views initialized", flush=True)
    scene.reset()
    sim_dt = sim.get_physics_dt()
    scene.update(sim_dt)
    print("[M18] scene reset complete", flush=True)

    actual_body_names = list(robot.body_names)
    if (
        len(actual_body_names) != len(M18_ROBOT_BODY_NAMES)
        or len(set(actual_body_names)) != len(actual_body_names)
        or set(actual_body_names) != set(M18_ROBOT_BODY_NAMES)
    ):
        raise RuntimeError(
            "M18 robot rigid-body contract mismatch: "
            f"expected={list(M18_ROBOT_BODY_NAMES)}, actual={actual_body_names}."
        )

    body_ids, body_names = robot.find_bodies("arm_body6_to_gripper", preserve_order=True)
    if body_names != ["arm_body6_to_gripper"] or len(body_ids) != 1:
        raise RuntimeError(f"M18 source body mapping mismatch: {body_ids}, {body_names}.")
    arm_joint_ids, arm_joint_names = robot.find_joints(
        [f"arm_j{index}" for index in range(1, 7)], preserve_order=True
    )
    if arm_joint_names != [f"arm_j{index}" for index in range(1, 7)]:
        raise RuntimeError(f"M18 arm joint mapping mismatch: {arm_joint_names}.")
    j6_index = arm_joint_names.index("arm_j6")
    jacobian_columns = [joint_id + 6 for joint_id in arm_joint_ids]
    controller = DifferentialIKController(
        DifferentialIKControllerCfg(
            command_type="pose",
            use_relative_mode=False,
            ik_method="dls",
            ik_params={"lambda_val": args.dls_lambda},
        ),
        num_envs=len(specs),
        device=args.device,
    )

    frames = frame_sensor.data
    target_pos_w = getattr(frames, "target_pos_w", None)
    target_quat_w = getattr(frames, "target_quat_w", None)
    source_pos_w = getattr(frames, "source_pos_w", None)
    source_quat_w = getattr(frames, "source_quat_w", None)
    expected_pos_shape = (len(specs), 2, 3)
    expected_quat_shape = (len(specs), 2, 4)
    if not torch.is_tensor(target_pos_w) or tuple(target_pos_w.shape) != expected_pos_shape:
        raise RuntimeError(f"M18 FrameTransformer target_pos_w contract mismatch: {getattr(target_pos_w, 'shape', None)}.")
    if not torch.is_tensor(target_quat_w) or tuple(target_quat_w.shape) != expected_quat_shape:
        raise RuntimeError(f"M18 FrameTransformer target_quat_w contract mismatch: {getattr(target_quat_w, 'shape', None)}.")
    if not torch.is_tensor(source_pos_w) or tuple(source_pos_w.shape) != (len(specs), 3):
        raise RuntimeError(f"M18 FrameTransformer source_pos_w contract mismatch: {getattr(source_pos_w, 'shape', None)}.")
    if not torch.is_tensor(source_quat_w) or tuple(source_quat_w.shape) != (len(specs), 4):
        raise RuntimeError(f"M18 FrameTransformer source_quat_w contract mismatch: {getattr(source_quat_w, 'shape', None)}.")
    if list(getattr(frames, "target_frame_names", [])) != ["handle", "pregrasp"]:
        raise RuntimeError(f"M18 FrameTransformer target order must be handle=0, pregrasp=1; got {frames.target_frame_names}.")
    for name, value in (
        ("target_pos_w", target_pos_w),
        ("target_quat_w", target_quat_w),
        ("source_pos_w", source_pos_w),
        ("source_quat_w", source_quat_w),
    ):
        _require_runtime_finite(name, value)
    expected_handle_heights = torch.tensor(
        [spec[0] for spec in specs], device=target_pos_w.device, dtype=target_pos_w.dtype
    )
    actual_handle_heights = target_pos_w[:, 0, 2] - scene.env_origins[:, 2]
    _require_runtime_finite("actual_handle_heights", actual_handle_heights)
    if not torch.allclose(actual_handle_heights, expected_handle_heights, rtol=0.0, atol=1.0e-5):
        max_error = torch.max(torch.abs(actual_handle_heights - expected_handle_heights)).item()
        raise RuntimeError(
            "M18 door prototype-to-env mapping mismatch: "
            f"max handle-height error={max_error:.9g} m."
        )

    root_state_local = robot.data.default_root_state.clone()
    env_origins = scene.env_origins
    root_state_local[:, 0] = target_pos_w[:, 0, 0] - env_origins[:, 0]
    root_state_local[:, 1] = target_pos_w[:, 0, 1] - env_origins[:, 1]
    root_state_local[:, 3:7] = torch.tensor(
        (1.0, 0.0, 0.0, 0.0), device=root_state_local.device, dtype=root_state_local.dtype
    )
    for index, (_handle_height, standoff, root_height) in enumerate(specs):
        root_state_local[index, 0] = target_pos_w[index, 0, 0] - env_origins[index, 0] - standoff
        root_state_local[index, 1] = target_pos_w[index, 0, 1] - env_origins[index, 1]
        root_state_local[index, 2] = root_height
    _require_runtime_finite("static_root_state", root_state_local)

    default_joint_pos = robot.data.default_joint_pos.clone()
    default_joint_vel = torch.zeros_like(robot.data.default_joint_vel)
    robot.write_joint_state_to_sim(default_joint_pos, default_joint_vel)
    robot.set_joint_position_target(default_joint_pos)
    _write_static_root_poses(robot, root_state_local, env_origins)
    scene.reset()
    scene.write_data_to_sim()
    sim.step()
    scene.update(sim_dt)

    for _step in range(args.ik_steps):
        if _step % 30 == 0:
            print(f"[M18] IK step {_step}/{args.ik_steps}", flush=True)
        frames = frame_sensor.data
        source_pos_w = frames.source_pos_w
        source_quat_w = frames.source_quat_w
        target_pos_w = frames.target_pos_w[:, 1, :]
        target_quat_w = frames.target_quat_w[:, 1, :]
        root_pos_w = robot.data.root_pos_w
        root_quat_w = robot.data.root_quat_w
        body_pos_w = robot.data.body_pos_w[:, body_ids[0]]
        for name, value in (
            ("source_pos_w", source_pos_w),
            ("source_quat_w", source_quat_w),
            ("pregrasp_target_pos_w", target_pos_w),
            ("pregrasp_target_quat_w", target_quat_w),
            ("root_pos_w", root_pos_w),
            ("root_quat_w", root_quat_w),
            ("body_pos_w", body_pos_w),
        ):
            _require_runtime_finite(name, value)
        source_pos_root, source_quat_root = subtract_frame_transforms(
            root_pos_w, root_quat_w, source_pos_w, source_quat_w
        )
        target_pos_root, target_quat_root = subtract_frame_transforms(
            root_pos_w, root_quat_w, target_pos_w, target_quat_w
        )
        jacobian_all = robot.root_physx_view.get_jacobians()
        jacobian = jacobian_all[:, body_ids[0], :, jacobian_columns]
        expected_jacobian_shape = (len(specs), 6, 6)
        if tuple(jacobian.shape) != expected_jacobian_shape:
            raise RuntimeError(f"M18 Jacobian shape mismatch: expected {expected_jacobian_shape}, got {tuple(jacobian.shape)}.")
        _require_runtime_finite("arm_jacobian", jacobian)
        jacobian_root = a2_hold_rotate_jacobian_to_root(jacobian, root_quat_w)
        body_pos_root, _ = subtract_frame_transforms(root_pos_w, root_quat_w, body_pos_w, robot.data.body_quat_w[:, body_ids[0]])
        jacobian_root = a2_hold_apply_source_offset_to_jacobian(
            jacobian_root, source_pos_root - body_pos_root
        )
        command_pos, command_quat, *_ = a2_hold_bound_pose_command_step(
            source_pos_root,
            source_quat_root,
            target_pos_root,
            target_quat_root,
            args.max_position_step_m,
            args.max_orientation_step_rad,
        )
        controller.set_command(torch.cat((command_pos, command_quat), dim=-1))
        q_des = controller.compute(
            source_pos_root,
            source_quat_root,
            jacobian_root,
            robot.data.joint_pos[:, arm_joint_ids],
        )
        _require_runtime_finite("q_des", q_des)
        joint_target = robot.data.joint_pos.clone()
        joint_target[:, arm_joint_ids] = q_des
        robot.set_joint_position_target(joint_target)
        _write_static_root_poses(robot, root_state_local, env_origins)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim_dt)

    print(f"[M18] IK step {args.ik_steps}/{args.ik_steps}; collecting final contact frame", flush=True)
    _write_static_root_poses(robot, root_state_local, env_origins)
    scene.write_data_to_sim()
    sim.step()
    scene.update(sim_dt)
    print("[M18] final physics step complete", flush=True)
    collision, collision_max_force, collision_source_pair = _collect_physx_self_collision(
        num_envs=len(specs),
        sim_dt=sim_dt,
        threshold_n=args.self_collision_force_threshold_n,
    )

    frames = frame_sensor.data
    final_tcp_error = torch.linalg.norm(frames.source_pos_w - frames.target_pos_w[:, 1, :], dim=-1)
    _require_runtime_finite("final_tcp_error", final_tcp_error)
    final_joint_margins = _soft_joint_margins(robot, arm_joint_ids)
    _require_runtime_finite("final_joint_limit_margins", final_joint_margins)
    final_arm_margin = final_joint_margins.min(dim=1).values
    final_arm_j6_margin = final_joint_margins[:, j6_index]
    collision_source = [
        f"{source_pair}@final" if collision[env_id] else "none"
        for env_id, source_pair in enumerate(collision_source_pair)
    ]

    cells = []
    for index, (handle_height, standoff, root_height) in enumerate(specs):
        collision_evidence = (
            f"threshold_n={args.self_collision_force_threshold_n};"
            f"max_robot_self_contact_n={collision_max_force[index]:.9g};"
            f"source={collision_source[index]}"
        )
        cells.append(
            GridCell(
                handle_height_m=handle_height,
                standoff_m=standoff,
                root_height_m=root_height,
                tcp_error_m=float(final_tcp_error[index].item()),
                self_collision=collision[index],
                self_collision_evidence=collision_evidence,
                min_joint_limit_margin_rad=float(final_arm_margin[index].item()),
                arm_j6_margin_rad=float(final_arm_j6_margin[index].item()),
            )
        )

    import gc

    controller = None
    frame_sensor = None
    robot = None
    scene = None
    gc.collect()
    sim.clear_all_callbacks()
    sim.clear_instance()
    print("[M18] runtime evidence complete; SimulationContext callbacks released", flush=True)
    return cells


def _write_reachability_result(args: argparse.Namespace, cells: Sequence[GridCell]) -> int:
    summary = summarize_reachability(cells)
    csv_path, json_path, markdown_path = write_reachability_outputs(
        args.output_dir,
        cells,
        summary,
        stem=args.output_stem,
    )
    print(f"M18 reachability evidence: {csv_path}", flush=True)
    print(f"M18 reachability summary JSON: {json_path}", flush=True)
    print(f"M18 reachability summary Markdown: {markdown_path}", flush=True)
    print(json.dumps(summary["selection"], sort_keys=True), flush=True)
    return 0


def _run_isaaclab(args: argparse.Namespace, specs: Sequence[tuple[float, float, float]]) -> int:
    """Launch headless Isaac Sim only after argument parsing and help handling."""

    if args.ik_steps <= 0:
        raise ValueError("--ik-steps must be positive.")
    if not args.usd_file.is_file():
        raise FileNotFoundError(f"A2_Piper USD not found: {args.usd_file}")
    from isaacsim import SimulationApp

    simulation_app = SimulationApp({"headless": True, "fast_shutdown": True})
    try:
        cells = _run_ik_runtime(args, specs)
        return _write_reachability_result(args, cells)
    finally:
        print("[M18] result handling complete; fast-closing SimulationApp", flush=True)
        sys.stdout.flush()
        sys.stderr.flush()
        simulation_app.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.merge_csv is None:
        specs = select_grid_cells(args.handle_height, args.root_height, args.standoff)
        return _run_isaaclab(args, specs)
    if args.root_height is not None or args.standoff is not None:
        raise ValueError("--root-height/--standoff cannot be combined with --merge-csv.")
    cells = read_reachability_csvs(args.merge_csv)
    return _write_reachability_result(args, cells)


if __name__ == "__main__":
    sys.exit(main())
