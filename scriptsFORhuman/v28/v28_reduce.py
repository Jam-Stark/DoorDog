#!/usr/bin/env python3
"""Reduce exact-N v28 lanes with the v27 quality definition and v28 camera report."""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
from pathlib import Path
from typing import Any

from v28_contract import HERE, METRICS, SIDES, require


SCHEMA = "a2_piper_base_v28_reducer_v1"
MANIFEST_SCHEMA = "a2_piper_base_v28_eval_manifest_v1"


def module_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V27 = module_from(HERE.parent / "v27/v27_reduce.py", "v27_reduce_for_v28")
CAMERA = module_from(HERE / "v28_camera_metrics.py", "v28_camera_metrics_for_reducer")


class ReducerError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise ReducerError(f"missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def camera_report(lane: dict[str, Any], artifact_path: Path) -> dict[str, Any]:
    rig = lane.get("camera_rig")
    if not isinstance(rig, str) or not rig:
        raise ReducerError("lane camera_rig")
    trace = artifact_path / "stage2_5_step_trace.json"
    try:
        return CAMERA.reduce(trace, Path(rig))
    except (KeyError, TypeError, ValueError, OSError) as error:
        raise ReducerError(f"v28 camera telemetry: {error}") from error


def summary_for_lane(lane: dict[str, Any], expected_n: int) -> dict[str, Any]:
    artifact_path = Path(lane["artifact_path"])
    try:
        runtime_contract = V27.validate_runtime_contract(lane, artifact_path)
        metrics = V27.load_json(artifact_path / "metrics_eval.json")
        trace_counts = V27.trace_reach_counts(artifact_path / "stage2_5_step_trace.json", expected_n)
        terminals = V27.terminal_rows(metrics, expected_n, lane["side"])
    except V27.ReducerError as error:
        raise ReducerError(str(error)) from error
    if not all(trace_counts["trace_seen"][env_id] or row["max_stage"] < 2 for env_id, row in terminals.items()):
        raise ReducerError("missing trace for episode that reached Stage2")
    rows = list(terminals.values())
    for row in rows:
        V27.v26_integrity(row, require_both=True)
    complete_rows = [row for row in rows if row["terminal_reasons"] == "complete"]
    clean_complete = 0
    components = {
        "complete": len(complete_rows), "clean_complete": 0, "hinge_below_1p0472": 0,
        "body_contact_above_5N": 0,
        "low_height_or_overspeed": sum(row["terminal_reasons"] in {"low_height", "upper_dof_overspeed"} for row in rows),
    }
    crossing_hinges, hold_through = [], 0
    for env_id, row in terminals.items():
        hinge = trace_counts["first_crossing_hinge"][env_id]
        force = trace_counts["stage3_body_force_max"][env_id]
        holding = trace_counts["crossing_while_holding"][env_id]
        if hinge is not None:
            crossing_hinges.append(hinge)
        hold_through += int(holding is True)
        if row["terminal_reasons"] != "complete":
            continue
        if hinge is None or force is None:
            raise ReducerError(f"clean_complete trace telemetry env{env_id}")
        hinge_ok, force_ok = hinge >= V27.CROSSING_HINGE_RAD, force <= 5.0
        components["hinge_below_1p0472"] += int(not hinge_ok)
        components["body_contact_above_5N"] += int(not force_ok)
        clean_complete += int(hinge_ok and force_ok)
    components["clean_complete"] = clean_complete
    summary = {
        "episodes": expected_n,
        "D": trace_counts["D"],
        "S3+": sum(row["max_stage"] >= 3 for row in rows),
        "S4+": sum(row["max_stage"] >= 4 for row in rows),
        "open_hold": trace_counts["open_hold"],
        "S5+": sum(row["max_stage"] >= 5 for row in rows),
        "complete": len(complete_rows),
        "clean_complete": clean_complete,
        "hold_through": hold_through,
        "crossing_while_holding": hold_through,
        "post_release_body_force_p95": V27.percentile([
            V27.finite_number(row["post_release_body_force_max"], "post_release_body_force_max")
            for row in rows if row.get("post_release_body_force_max") is not None
        ], .95),
        "first_crossing_hinge_p50": V27.percentile(crossing_hinges, .5),
        "episode_length_p50": V27.percentile([V27.finite_number(row.get("episode_length_buf"), "episode_length_buf") for row in rows], .5),
        "arm_j4_limit_residence_step_share": trace_counts["arm_j4_limit_residence_step_share"],
        "terminal_reasons": dict(collections.Counter(row["terminal_reasons"] for row in rows)),
        "integrity_violations": sum(V27.v26_integrity(row, require_both=True) for row in rows),
        "runtime_contract": runtime_contract,
        "clean_complete_components": components,
    }
    if summary["integrity_violations"] != 0:
        raise ReducerError("integrity_violations")
    camera = camera_report(lane, artifact_path)
    plan_fields = camera.get("plan_fields")
    if not isinstance(plan_fields, dict):
        raise ReducerError("camera plan_fields")
    tower_episodes = plan_fields.get("wrist_tower_contact_episodes_gt_5N")
    if not isinstance(tower_episodes, int):
        raise ReducerError("wrist_tower_contact_episodes_gt_5N")
    summary["wrist_tower_contact_episodes_gt_5N"] = tower_episodes
    summary["wrist_tower_contact_step_share"] = plan_fields.get("wrist_tower_contact_step_share")
    summary["camera_telemetry"] = camera
    return summary


def terminal_failures(summary: dict[str, Any]) -> int:
    return sum(summary["terminal_reasons"].get(name, 0) for name in ("low_height", "upper_dof_overspeed"))


def reachability_gate(summary: dict[str, Any]) -> bool:
    if summary["episodes"] != 64:
        raise ReducerError(f"reachability gate requires 64 episodes, got {summary['episodes']}")
    return (summary["complete"] >= 60 and terminal_failures(summary) <= 2
            and summary["wrist_tower_contact_episodes_gt_5N"] <= 2
            and summary["post_release_body_force_p95"] is not None
            and summary["post_release_body_force_p95"] <= 5.0)


def passes_gate(summary: dict[str, Any]) -> bool:
    n = summary["episodes"]
    if n not in (64, 128):
        raise ReducerError(f"no preregistered v28 gate for N={n}")
    tower_limit = 2 if n == 64 else 4
    return V27.passes_gate(summary) and summary["wrist_tower_contact_episodes_gt_5N"] <= tower_limit


def cell_sides(cells: dict[str, Any], cell: str, stratum: str = "nominal") -> dict[str, Any] | None:
    sides = cells.get(cell, {}).get(stratum)
    return sides if isinstance(sides, dict) and set(sides) == set(SIDES) else None


def select_wave_a(history: list[dict[str, Any]]) -> dict[str, Any]:
    candidates: list[tuple[int, str, int]] = []
    for payload in sorted(history, key=lambda value: value["step"]):
        for seed in (281, 282, 283):
            cell = f"A_S{seed}"
            sides = cell_sides(payload["cells"], cell)
            if sides is not None and all(reachability_gate(sides[side]) for side in SIDES):
                candidates.append((payload["step"], cell, sum(sides[side]["clean_complete"] for side in SIDES)))
    if not candidates:
        return {"outcome": "REACH_NOT_ESTABLISHED", "selected_cell": None}
    earliest = min(value[0] for value in candidates)
    tied = [value for value in candidates if value[0] == earliest]
    chosen = sorted(tied, key=lambda value: (value[1], -value[2]))[0]
    return {"outcome": "REACH_3SEED" if len({value[1] for value in candidates if value[0] == max(row["step"] for row in history)}) == 3 else "REACH_SEED_UNSTABLE",
            "selected_cell": chosen[1], "selected_milestone": chosen[0], "clean_complete_sum": chosen[2]}


def k_reach_without_complete(history: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(history, key=lambda value: value["step"])
    triggers = []
    for previous, current in zip(ordered[:-1], ordered[1:], strict=True):
        for cell in ("A_S281", "A_S282", "A_S283"):
            previous_sides, current_sides = cell_sides(previous["cells"], cell), cell_sides(current["cells"], cell)
            if previous_sides is None or current_sides is None:
                continue
            if all(summary["S4+"] >= 56 and summary["complete"] <= 4
                   for sides in (previous_sides, current_sides) for summary in sides.values()):
                triggers.append({"cell": cell, "milestones": [previous["step"], current["step"]], "outcome": "K_REACH_WITHOUT_COMPLETE"})
    return {"outcome": "K_REACH_WITHOUT_COMPLETE" if triggers else "NOT_TRIGGERED", "triggers": triggers,
            "reserve_cell": "A_S284" if triggers else None}


def reduce_manifest(manifest: dict[str, Any], expected_n: int) -> dict[str, Any]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ReducerError("manifest schema")
    step, lanes = manifest.get("step"), manifest.get("lanes")
    if not isinstance(step, int) or step < 0 or not isinstance(lanes, list) or not lanes:
        raise ReducerError("manifest step or lanes")
    cells: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    invalid: dict[str, list[str]] = collections.defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    lane_outputs = []
    for lane in lanes:
        if not isinstance(lane, dict):
            raise ReducerError("lane mapping")
        cell = lane.get("cell")
        try:
            cell, stratum, side = V27.validate_lane_identity(lane, expected_n)
            identity = (cell, stratum, side)
            if identity in seen:
                raise ReducerError(f"duplicate lane: {identity}")
            seen.add(identity)
            summary = summary_for_lane(lane, expected_n)
        except (ReducerError, V27.ReducerError, ValueError, TypeError, KeyError) as error:
            invalid[str(cell)].append(f"{lane.get('stratum', '<missing>')}/{lane.get('side', '<missing>')}: {error}")
            lane_outputs.append({"cell": cell, "status": "V28_INVALID", "failure": str(error)})
            continue
        cells.setdefault(cell, {}).setdefault(stratum, {})[side] = summary
        lane_outputs.append({"cell": cell, "stratum": stratum, "side": side, "status": "COMPLETE"})
    for cell in invalid:
        cells.pop(cell, None)
    prior = manifest.get("wave_a_history", [])
    if not isinstance(prior, list) or not all(isinstance(item, dict) and {"step", "cells"} <= set(item) for item in prior):
        raise ReducerError("wave_a_history")
    history = [*prior, {"step": step, "cells": cells}]
    typed = None
    if manifest.get("endpoint") is True and not invalid:
        typed = {"selection": select_wave_a(history), "k_driver": k_reach_without_complete(history)}
    return {"schema": SCHEMA, "status": "V28_INVALID" if invalid else "V28_COMPLETE", "expected_n": expected_n,
            "step": step, "endpoint": manifest.get("endpoint", False), "cells": cells, "lanes": lane_outputs,
            "invalid_cells": dict(invalid), "typed_outcomes": typed,
            "route": "V28_INVALID" if invalid else "V28_REDUCED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-n", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(args.expected_n > 0, "expected-n positive")
    require(not args.output.exists(), f"refusing to overwrite reducer output: {args.output}")
    payload = reduce_manifest(load_json(args.manifest), args.expected_n)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"route": payload["route"], "invalid_cells": sorted(payload["invalid_cells"])}))
    return 2 if payload["status"] == "V28_INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
