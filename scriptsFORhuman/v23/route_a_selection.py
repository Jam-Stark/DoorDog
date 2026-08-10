"""Mechanical v23 Route-A checkpoint selection.

For each ``(seed, cell)`` the rule is fixed before training:

1. highest ``goal_reached`` count;
2. highest supported crossing count;
3. lowest unsafe-contact count;
4. lowest terminal-failure count;
5. earliest checkpoint step.

No weighted score, manual rationale, or missing-to-zero conversion is allowed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import REPO_ROOT, V23_GPU_SUBWAVES, V23_PLAN_ID, V23_ROUTE_A_STEPS, V23Error, write_json
    from .m22 import _load_object, _route_root
    from .route_a_analysis import ANALYSIS_SCHEMA
except ImportError:  # direct ``python scriptsFORhuman/v23/route_a_selection.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import REPO_ROOT, V23_GPU_SUBWAVES, V23_PLAN_ID, V23_ROUTE_A_STEPS, V23Error, write_json
    from scriptsFORhuman.v23.m22 import _load_object, _route_root
    from scriptsFORhuman.v23.route_a_analysis import ANALYSIS_SCHEMA


SELECTION_SCHEMA = "a2_piper_v23_route_a_selection_v1"


class RouteASelectionError(V23Error):
    """A Route-A analysis cannot support mechanical selection."""


def select(subwave: str, *, analysis_path: Path | None = None) -> dict[str, Any]:
    if subwave not in V23_GPU_SUBWAVES:
        raise RouteASelectionError(f"unknown scientific sub-wave: {subwave}")
    root = _route_root(subwave)
    source = analysis_path or (root / "V23_ROUTE_A_ANALYSIS.json")
    analysis = _load_object(source)
    if analysis.get("schema") != ANALYSIS_SCHEMA or analysis.get("status") != "COMPLETE":
        raise RouteASelectionError(f"Route-A analysis is not complete: {source}")
    rows = analysis.get("rows")
    if not isinstance(rows, list) or len(rows) != 40:
        raise RouteASelectionError("Route-A analysis must contain exactly 40 rows")
    cells = list(V23_GPU_SUBWAVES[subwave]["cells"])
    expected_seed = V23_GPU_SUBWAVES[subwave]["seed"]
    if (
        analysis.get("subwave") != subwave
        or analysis.get("seed") != expected_seed
        or analysis.get("cells") != cells
        or analysis.get("steps") != list(V23_ROUTE_A_STEPS)
        or analysis.get("topology") != "canonical16"
        or analysis.get("source_branch") != "A2_Piper"
        or analysis.get("plan_id") != V23_PLAN_ID
        or analysis.get("identity_policy") != "OWNER_NO_HASH_PATH_IDENTITY"
    ):
        raise RouteASelectionError("Route-A analysis identity does not match the requested sub-wave")
    grouped: dict[str, list[Mapping[str, Any]]] = {cell: [] for cell in cells}
    for row in rows:
        if not isinstance(row, Mapping):
            raise RouteASelectionError("Route-A analysis contains a non-object row")
        if row.get("evidence_status") != "SUPPORTED" or row.get("missing_evidence") != []:
            raise RouteASelectionError(f"Route-A row {row.get('row_id')!r} is not supported evidence")
        cell = row.get("cell")
        if cell not in grouped:
            raise RouteASelectionError(f"Route-A analysis contains unexpected cell {cell!r}")
        if (
            row.get("subwave") != subwave
            or row.get("seed") != expected_seed
            or row.get("topology") != "canonical16"
            or row.get("source_branch") != "A2_Piper"
            or row.get("plan_id") != V23_PLAN_ID
            or row.get("identity_policy") != "OWNER_NO_HASH_PATH_IDENTITY"
        ):
            raise RouteASelectionError(f"Route-A row {row.get('row_id')!r} identity disagrees")
        for field in ("goal_reached", "supported_crossing", "unsafe_contacts", "terminal_failures", "step"):
            if field not in row or isinstance(row[field], bool) or not isinstance(row[field], int):
                raise RouteASelectionError(f"Route-A row {row.get('row_id')!r} lacks integer field {field}")
            if field != "step" and row[field] < 0:
                raise RouteASelectionError(f"Route-A row {row.get('row_id')!r} has negative {field}")
            if field in {"goal_reached", "supported_crossing", "unsafe_contacts", "terminal_failures"} and row[field] > 16:
                raise RouteASelectionError(f"Route-A row {row.get('row_id')!r} has {field} above 16")
        grouped[cell].append(row)
    if any(len(grouped[cell]) != 10 for cell in cells):
        raise RouteASelectionError("Route-A analysis must contain ten checkpoints per cell")
    expected_steps = list(V23_ROUTE_A_STEPS)
    for cell in cells:
        observed_steps = [row["step"] for row in grouped[cell]]
        if sorted(observed_steps) != expected_steps or len(set(observed_steps)) != len(expected_steps):
            raise RouteASelectionError(f"{cell} does not contain the unique ordered Route-A step set 250..2500")

    selected: list[dict[str, Any]] = []
    for cell in cells:
        ordered = sorted(
            grouped[cell],
            key=lambda row: (
                -row["goal_reached"],
                -row["supported_crossing"],
                row["unsafe_contacts"],
                row["terminal_failures"],
                row["step"],
            ),
        )
        winner = ordered[0]
        selected.append(
            {
                "source_branch": winner["source_branch"],
                "plan_id": winner["plan_id"],
                "identity_policy": winner["identity_policy"],
                "seed": winner["seed"],
                "cell": cell,
                "row_id": winner["row_id"],
                "step": winner["step"],
                "checkpoint_path": winner["checkpoint_path"],
                "config_path": winner["config_path"],
                "scenario_path": winner["scenario_path"],
                "evaluation_root": winner["evaluation_root"],
                "goal_reached": winner["goal_reached"],
                "supported_crossing": winner["supported_crossing"],
                "unsafe_contacts": winner["unsafe_contacts"],
                "terminal_failures": winner["terminal_failures"],
            }
        )
    payload = {
        "schema": SELECTION_SCHEMA,
        "status": "COMPLETE",
        "recorded_at_utc": datetime_now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "A",
        "subwave": subwave,
        "seed": V23_GPU_SUBWAVES[subwave]["seed"],
        "cells": cells,
        "selection_method": "mechanical",
        "topology": "canonical16",
        "steps": list(V23_ROUTE_A_STEPS),
        "selection_rule": [
            "highest goal_reached",
            "highest supported_crossing",
            "lowest unsafe_contacts",
            "lowest terminal_failures",
            "earliest step",
        ],
        "analysis_path": str(source),
        "selected": selected,
    }
    write_json(root / "V23_ROUTE_A_SELECTION.json", payload)
    return payload


def datetime_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subwave", required=True, choices=tuple(V23_GPU_SUBWAVES))
    parser.add_argument("--analysis")
    args = parser.parse_args(argv)
    try:
        payload = select(args.subwave, analysis_path=Path(args.analysis) if args.analysis else None)
    except V23Error as exc:
        print(f"V23 ROUTE_A_SELECTION FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
