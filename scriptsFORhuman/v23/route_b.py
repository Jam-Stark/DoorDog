"""Strict Route-B orchestrator for selected v23 checkpoints.

The pipeline is intentionally linear:

``selected Route-A receipts -> pooled48 -> realized-dynamics stratification ->
five forward intervention modes``.

Each downstream stage is blocked when its upstream receipt is missing or
non-complete.  This controller does not rank candidates, invent a symmetry
gate, or claim holdout/render/final-report completion.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        REPO_ROOT,
        V23_INTERVENTION_MODES,
        V23_LEGAL_PHYSICAL_GPUS,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )
    from . import intervention_eval, pooled48, stratified_eval
except ImportError:  # direct ``python scriptsFORhuman/v23/route_b.py``
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_INTERVENTION_MODES,
        V23_LEGAL_PHYSICAL_GPUS,
        V23_PLAN_ID,
        V23Error,
        write_json,
    )
    from scriptsFORhuman.v23 import intervention_eval, pooled48, stratified_eval


ROUTE_B_PLAN_SCHEMA = "a2_piper_v23_route_b_plan_v1"
ROUTE_B_SCHEMA = "a2_piper_v23_route_b_receipt_v1"
ROUTE_B_STATUS = "V23_ROUTE_B_COMPLETE"
ROUTE_B_ROOT = REPO_ROOT / "logs_eval/base_v23/route_b"
ROUTE_B_PLAN_PATH = ROUTE_B_ROOT / "V23_ROUTE_B_PLAN.json"
ROUTE_B_RECEIPT_PATH = ROUTE_B_ROOT / "V23_ROUTE_B.json"
SUBWAVE_ORDER = ("A1", "A2", "B1", "B2")


class RouteBError(V23Error):
    """A Route-B dependency, order, or receipt contract is invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _load_object(path: str | Path) -> dict[str, Any]:
    target = _absolute(path)
    if target.is_symlink() or not target.is_file():
        raise RouteBError(f"required Route-B receipt is missing: {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RouteBError(f"Route-B receipt is not valid JSON: {target}") from exc
    if not isinstance(payload, dict):
        raise RouteBError(f"Route-B receipt must be an object: {target}")
    return payload


def _selection_overrides(selection_paths: Mapping[str, str | Path] | None) -> dict[str, str | Path] | None:
    if selection_paths is None:
        return None
    if set(selection_paths) != set(SUBWAVE_ORDER):
        raise RouteBError("Route-B selection overrides must cover A1, A2, B1, and B2 exactly")
    return dict(selection_paths)


def build_plan(
    *,
    selection_paths: Mapping[str, str | Path] | None = None,
    require_sources: bool = True,
    output: str | Path | None = None,
) -> dict[str, Any]:
    """Build the strict selected -> pooled -> stratified -> intervention plan."""

    overrides = _selection_overrides(selection_paths)
    selected = pooled48.load_selected_candidates(overrides, require_sources=require_sources)
    pooled_jobs = 16
    stratified_jobs = 16
    intervention_jobs = 16 * len(V23_INTERVENTION_MODES)
    payload = {
        "schema": ROUTE_B_PLAN_SCHEMA,
        "status": "BUILT",
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "selected_candidates": selected,
        "selected_candidate_count": len(selected),
        "pipeline_order": [
            "ROUTE_A_SELECTED_CHECKPOINTS",
            "POOLED48",
            "STRATIFIED_REALIZED_DYNAMICS",
            "INTERVENTIONS_FULL_AND_FOUR_FORWARD_MODES",
        ],
        "upstream_bindings": [
            {
                "name": "Route-A selections",
                "paths": [str(pooled48.SELECTION_PATHS[subwave]) for subwave in SUBWAVE_ORDER],
                "status": "REQUIRED_COMPLETE",
            },
            {
                "name": "R190 physics-first labels",
                "path": str(stratified_eval.R190_RECEIPT_PATH),
                "schema": stratified_eval.R190_SCHEMA,
                "status": stratified_eval.R190_STATUS,
            },
        ],
        "producer_receipts": [
            {
                "stage": "POOLED48",
                "path": str(pooled48.POOLED48_RECEIPT_PATH),
                "schema": pooled48.POOLED48_SCHEMA,
                "status": pooled48.POOLED48_STATUS,
                "expected_jobs": pooled_jobs,
                "topology": "pooled48",
            },
            {
                "stage": "STRATIFIED_EVAL",
                "path": str(stratified_eval.STRATIFIED_RECEIPT_PATH),
                "schema": stratified_eval.STRATIFIED_SCHEMA,
                "status": stratified_eval.STRATIFIED_STATUS,
                "expected_jobs": stratified_jobs,
                "topology": "pooled48_posthoc_realized_dynamics",
            },
            {
                "stage": "INTERVENTIONS",
                "path": str(intervention_eval.INTERVENTION_RECEIPT_PATH),
                "schema": intervention_eval.INTERVENTION_RECEIPT_SCHEMA,
                "status": intervention_eval.INTERVENTION_RECEIPT_STATUS,
                "expected_jobs": intervention_jobs,
                "topology": "canonical16",
                "modes": list(V23_INTERVENTION_MODES),
            },
        ],
        "physical_gpus": list(V23_LEGAL_PHYSICAL_GPUS),
        "logical_gpu": "cuda:0",
        "process_count_per_gpu": 1,
        "num_mini_batches": 1,
        "no_retry": True,
        "symmetry_gate": "NOT_APPLIED",
        "deferred_outputs": {
            "holdout": "DEFERRED",
            "render": "DEFERRED",
            "final_analysis_report": "DEFERRED",
        },
        "missing_evidence_policy": "TYPED_FAILURE_NO_ZERO_FILL",
    }
    if output is not None:
        write_json(_absolute(output), payload)
    return payload


def run(
    *,
    selection_paths: Mapping[str, str | Path] | None = None,
) -> dict[str, Any]:
    """Execute Route-B stages in strict order, with no downstream fallback."""

    overrides = _selection_overrides(selection_paths)
    pooled_result = pooled48.run(selection_paths=overrides)
    pooled_receipt = pooled48.reduce(selection_paths=overrides)
    if pooled_receipt.get("status") != pooled48.POOLED48_STATUS:
        raise RouteBError("pooled48 reducer did not return a complete receipt")
    stratified_result = stratified_eval.run()
    stratified_receipt = stratified_eval.reduce()
    if stratified_receipt.get("status") != stratified_eval.STRATIFIED_STATUS:
        raise RouteBError("stratified reducer did not return a complete receipt")
    intervention_result = intervention_eval.run()
    intervention_receipt = intervention_eval.reduce()
    if intervention_receipt.get("status") != intervention_eval.INTERVENTION_RECEIPT_STATUS:
        raise RouteBError("intervention reducer did not return a complete receipt")
    return {
        "schema": "a2_piper_v23_route_b_run_result_v1",
        "status": "PASS",
        "recorded_at_utc": _now(),
        "pipeline_order": ["POOLED48", "POOLED48_REDUCE", "STRATIFIED_EVAL", "STRATIFIED_REDUCE", "INTERVENTIONS", "INTERVENTIONS_REDUCE"],
        "pooled48": pooled_result,
        "pooled48_receipt_status": pooled_receipt["status"],
        "stratified": stratified_result,
        "stratified_receipt_status": stratified_receipt["status"],
        "interventions": intervention_result,
        "intervention_receipt_status": intervention_receipt["status"],
        "no_retry": True,
    }


def _validate_producer_receipt(
    path: str | Path,
    *,
    schema: str,
    status: str,
    name: str,
) -> dict[str, Any]:
    payload = _load_object(path)
    if payload.get("schema") != schema or payload.get("status") != status:
        raise RouteBError(f"{name} receipt schema/status is not complete: {_absolute(path)}")
    selected = pooled48.validate_selected_candidates(payload.get("selected_candidates"), require_sources=False)
    payload["selected_candidates"] = selected
    return payload


def reduce(
    *,
    pooled_receipt: str | Path = pooled48.POOLED48_RECEIPT_PATH,
    stratified_receipt: str | Path = stratified_eval.STRATIFIED_RECEIPT_PATH,
    intervention_receipt: str | Path = intervention_eval.INTERVENTION_RECEIPT_PATH,
    output: str | Path = ROUTE_B_RECEIPT_PATH,
) -> dict[str, Any]:
    """Validate the three complete producer receipts and seal Route-B order."""

    pooled = _validate_producer_receipt(
        pooled_receipt,
        schema=pooled48.POOLED48_SCHEMA,
        status=pooled48.POOLED48_STATUS,
        name="pooled48",
    )
    stratified = _validate_producer_receipt(
        stratified_receipt,
        schema=stratified_eval.STRATIFIED_SCHEMA,
        status=stratified_eval.STRATIFIED_STATUS,
        name="stratified",
    )
    intervention = _validate_producer_receipt(
        intervention_receipt,
        schema=intervention_eval.INTERVENTION_RECEIPT_SCHEMA,
        status=intervention_eval.INTERVENTION_RECEIPT_STATUS,
        name="intervention",
    )
    selected = pooled["selected_candidates"]
    if stratified["selected_candidates"] != selected or intervention["selected_candidates"] != selected:
        raise RouteBError("all three Route-B producer receipts must contain exactly the same selected_candidates")
    if pooled.get("topology") != "pooled48":
        raise RouteBError("pooled48 receipt topology is not pooled48")
    if stratified.get("topology") != "pooled48_posthoc_realized_dynamics":
        raise RouteBError("stratified receipt topology is not realized-dynamics posthoc")
    if intervention.get("topology") != "canonical16":
        raise RouteBError("intervention receipt topology is not canonical16")
    if intervention.get("modes") != list(V23_INTERVENTION_MODES):
        raise RouteBError("intervention receipt mode order does not cover all five modes")
    payload = {
        "schema": ROUTE_B_SCHEMA,
        "status": ROUTE_B_STATUS,
        "recorded_at_utc": _now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "pipeline_order": ["POOLED48", "STRATIFIED_EVAL", "INTERVENTIONS"],
        "selected_candidates": selected,
        "selected_candidate_count": len(selected),
        "physical_gpus": list(V23_LEGAL_PHYSICAL_GPUS),
        "logical_gpu": "cuda:0",
        "process_count_per_gpu": 1,
        "num_mini_batches": 1,
        "producer_receipts": [
            {
                "name": "pooled48",
                "path": str(_absolute(pooled_receipt)),
                "schema": pooled48.POOLED48_SCHEMA,
                "status": pooled48.POOLED48_STATUS,
                "topology": pooled["topology"],
                "job_count": pooled.get("job_count"),
            },
            {
                "name": "stratified",
                "path": str(_absolute(stratified_receipt)),
                "schema": stratified_eval.STRATIFIED_SCHEMA,
                "status": stratified_eval.STRATIFIED_STATUS,
                "topology": stratified["topology"],
                "job_count": stratified.get("job_count"),
            },
            {
                "name": "intervention",
                "path": str(_absolute(intervention_receipt)),
                "schema": intervention_eval.INTERVENTION_RECEIPT_SCHEMA,
                "status": intervention_eval.INTERVENTION_RECEIPT_STATUS,
                "topology": intervention["topology"],
                "job_count": intervention.get("job_count"),
                "modes": list(V23_INTERVENTION_MODES),
            },
        ],
        "symmetry_gate": "NOT_APPLIED",
        "holdout_status": "DEFERRED",
        "render_status": "DEFERRED",
        "final_analysis_status": "DEFERRED",
        "missing_evidence": [],
        "no_retry": True,
    }
    write_json(_absolute(output), payload)
    return payload


def _selection_args(parser: argparse.ArgumentParser) -> None:
    for subwave in SUBWAVE_ORDER:
        parser.add_argument(f"--{subwave.lower()}-selection", type=Path, default=None)


def _selection_paths_from_args(args: argparse.Namespace) -> dict[str, Path] | None:
    values = {
        subwave: getattr(args, f"{subwave.lower()}_selection")
        for subwave in SUBWAVE_ORDER
        if getattr(args, f"{subwave.lower()}_selection") is not None
    }
    if not values:
        return None
    if set(values) != set(SUBWAVE_ORDER):
        raise RouteBError("selection overrides must provide all four subwaves")
    return values


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "BUILD", "RUN", "REDUCE"), required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help="CPU fixture only for PLAN/BUILD; never permits RUN",
    )
    parser.add_argument("--pooled48", type=Path, default=pooled48.POOLED48_RECEIPT_PATH)
    parser.add_argument("--stratified", type=Path, default=stratified_eval.STRATIFIED_RECEIPT_PATH)
    parser.add_argument("--intervention", type=Path, default=intervention_eval.INTERVENTION_RECEIPT_PATH)
    _selection_args(parser)
    args = parser.parse_args(argv)
    try:
        selection_paths = _selection_paths_from_args(args)
        if args.mode in {"PLAN", "BUILD"}:
            payload = build_plan(
                selection_paths=selection_paths,
                require_sources=not args.allow_missing_sources,
                output=(args.output or ROUTE_B_PLAN_PATH) if args.mode == "BUILD" else None,
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        elif args.mode == "RUN":
            if args.allow_missing_sources:
                raise RouteBError("--allow-missing-sources is not valid for RUN")
            payload = run(selection_paths=selection_paths)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            payload = reduce(
                pooled_receipt=args.pooled48,
                stratified_receipt=args.stratified,
                intervention_receipt=args.intervention,
                output=args.output or ROUTE_B_RECEIPT_PATH,
            )
            print(json.dumps({"status": "WRITTEN", "path": str(_absolute(args.output or ROUTE_B_RECEIPT_PATH))}, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 ROUTE_B {args.mode} FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
