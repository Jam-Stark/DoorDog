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
PHYSICAL_GPU_DOMAIN = pooled48.PHYSICAL_GPU_DOMAIN
PHYSICAL_GPU_MAPPING_POLICY = pooled48.PHYSICAL_GPU_MAPPING_POLICY
ROUTE_B_PHYSICAL_GPUS = PHYSICAL_GPU_DOMAIN


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


def _require_route_physical_gpus(values: Sequence[int] | str | None) -> tuple[int, ...]:
    selected = ROUTE_B_PHYSICAL_GPUS if values is None else pooled48.validate_physical_gpus(values)
    if selected != ROUTE_B_PHYSICAL_GPUS:
        raise RouteBError(
            "Route-B requires the persisted exact eight-GPU map "
            f"{list(ROUTE_B_PHYSICAL_GPUS)}; subsets are not accepted"
        )
    return selected


def _execution_paths(route_plan_path: str | Path) -> dict[str, dict[str, str]]:
    """Return deterministic child plan/receipt paths bound to one Route-B plan."""

    root = _absolute(route_plan_path).parent
    return {
        "plan": {
            "pooled48": str(root / "V23_POOLED48_PLAN.json"),
            "stratified": str(root / "V23_STRATIFIED_EVAL_PLAN.json"),
            "intervention": str(root / "V23_INTERVENTION_EVAL_PLAN.json"),
        },
        "receipt": {
            "pooled48": str(root / "V23_POOLED48.json"),
            "stratified": str(root / "V23_STRATIFIED_EVAL.json"),
            "intervention": str(root / "V23_INTERVENTION_EVAL.json"),
        },
    }


def build_plan(
    *,
    selection_paths: Mapping[str, str | Path] | None = None,
    require_sources: bool = True,
    physical_gpus: Sequence[int] | str | None = None,
    output: str | Path | None = None,
) -> dict[str, Any]:
    """Build the strict selected -> pooled -> stratified -> intervention plan."""

    overrides = _selection_overrides(selection_paths)
    selected = pooled48.load_selected_candidates(overrides, require_sources=require_sources)
    selected_gpus = _require_route_physical_gpus(physical_gpus)
    route_plan_path = _absolute(output or ROUTE_B_PLAN_PATH)
    execution_paths = _execution_paths(route_plan_path)
    if output is not None:
        pooled48.build_plan(
            selection_paths=overrides,
            require_sources=require_sources,
            physical_gpus=selected_gpus,
            output=execution_paths["plan"]["pooled48"],
        )
    pooled_job_plan = [
        pooled48._job_plan(candidate, physical_gpus=selected_gpus, job_ordinal=ordinal)
        for ordinal, candidate in enumerate(selected)
    ]
    intervention_job_plan: list[dict[str, Any]] = []
    for candidate in selected:
        for mode in V23_INTERVENTION_MODES:
            intervention_job_plan.append(
                intervention_eval._job_plan(
                    candidate,
                    mode,
                    physical_gpus=selected_gpus,
                    job_ordinal=len(intervention_job_plan),
                )
            )
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
                "path": execution_paths["receipt"]["pooled48"],
                "schema": pooled48.POOLED48_SCHEMA,
                "status": pooled48.POOLED48_STATUS,
                "expected_jobs": pooled_jobs,
                "topology": "pooled48",
            },
            {
                "stage": "STRATIFIED_EVAL",
                "path": execution_paths["receipt"]["stratified"],
                "schema": stratified_eval.STRATIFIED_SCHEMA,
                "status": stratified_eval.STRATIFIED_STATUS,
                "expected_jobs": stratified_jobs,
                "topology": "pooled48_posthoc_realized_dynamics",
            },
            {
                "stage": "INTERVENTIONS",
                "path": execution_paths["receipt"]["intervention"],
                "schema": intervention_eval.INTERVENTION_RECEIPT_SCHEMA,
                "status": intervention_eval.INTERVENTION_RECEIPT_STATUS,
                "expected_jobs": intervention_jobs,
                "topology": "canonical16",
                "modes": list(V23_INTERVENTION_MODES),
            },
        ],
        "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
        "physical_gpus": list(selected_gpus),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
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
        "job_plan": {
            "pooled48": pooled_job_plan,
            "stratified": {
                "job_count": stratified_jobs,
                "runtime_mode": "POOLED_TRACE_REALIZED_DYNAMICS_REDUCE",
                "physical_gpus": list(selected_gpus),
                "physical_gpu_provenance": "POOLED48_MANIFEST",
            },
            "interventions": intervention_job_plan,
        },
        "execution_plan": {
            "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
            "physical_gpus": list(selected_gpus),
            "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
            "pooled48_plan_path": execution_paths["plan"]["pooled48"],
            "stratified_plan_path": execution_paths["plan"]["stratified"],
            "intervention_plan_path": execution_paths["plan"]["intervention"],
            "pooled48_receipt_path": execution_paths["receipt"]["pooled48"],
            "stratified_receipt_path": execution_paths["receipt"]["stratified"],
            "intervention_receipt_path": execution_paths["receipt"]["intervention"],
        },
    }
    if output is not None:
        write_json(_absolute(output), payload)
    return payload


def _load_route_plan(path: str | Path = ROUTE_B_PLAN_PATH) -> dict[str, Any]:
    payload = _load_object(path)
    if payload.get("schema") != ROUTE_B_PLAN_SCHEMA or payload.get("status") != "BUILT":
        raise RouteBError("Route-B manifest schema/status is not BUILT")
    if payload.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN):
        raise RouteBError("Route-B manifest physical_gpu_domain is not exactly 0..7")
    if payload.get("physical_gpus") != list(ROUTE_B_PHYSICAL_GPUS):
        raise RouteBError("Route-B manifest must persist the exact eight-GPU map")
    if payload.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise RouteBError("Route-B manifest physical GPU mapping policy is unsupported")
    execution = payload.get("execution_plan")
    if not isinstance(execution, Mapping):
        raise RouteBError("Route-B manifest has no persisted execution_plan")
    if execution.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN):
        raise RouteBError("Route-B execution plan physical_gpu_domain is not exactly 0..7")
    if execution.get("physical_gpus") != list(ROUTE_B_PHYSICAL_GPUS):
        raise RouteBError("Route-B execution plan must persist the exact eight-GPU map")
    if execution.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
        raise RouteBError("Route-B execution plan physical GPU mapping policy is unsupported")
    expected_paths = _execution_paths(path)
    for stage in ("pooled48", "stratified", "intervention"):
        for kind in ("plan", "receipt"):
            field = f"{stage}_{kind}_path"
            if execution.get(field) != expected_paths[kind][stage]:
                raise RouteBError(f"Route-B execution plan {field} is not bound to the Route-B plan")
    producers = payload.get("producer_receipts")
    if not isinstance(producers, list) or len(producers) != 3:
        raise RouteBError("Route-B manifest must contain exactly three producer receipt bindings")
    expected_receipts = {
        "POOLED48": execution["pooled48_receipt_path"],
        "STRATIFIED_EVAL": execution["stratified_receipt_path"],
        "INTERVENTIONS": execution["intervention_receipt_path"],
    }
    for producer in producers:
        if not isinstance(producer, Mapping) or producer.get("stage") not in expected_receipts:
            raise RouteBError("Route-B producer receipt binding is malformed")
        stage = producer["stage"]
        if producer.get("path") != expected_receipts[stage]:
            raise RouteBError(f"Route-B producer receipt path for {stage} disagrees with execution_plan")
    selected = pooled48.validate_selected_candidates(payload.get("selected_candidates"), require_sources=False)
    payload["selected_candidates"] = selected
    pooled_plan = pooled48.load_plan(execution["pooled48_plan_path"])
    if pooled_plan["selected_candidates"] != selected or tuple(pooled_plan["physical_gpus"]) != ROUTE_B_PHYSICAL_GPUS:
        raise RouteBError("persisted pooled48 child plan disagrees with Route-B execution plan")
    payload["execution_plan"] = dict(execution)
    return payload


def run(
    *,
    selection_paths: Mapping[str, str | Path] | None = None,
    plan_path: str | Path = ROUTE_B_PLAN_PATH,
    physical_gpus: Sequence[int] | str | None = None,
) -> dict[str, Any]:
    """Execute Route-B stages in strict order, with no downstream fallback."""

    if physical_gpus is not None:
        raise RouteBError("Route-B RUN consumes the persisted plan and rejects live physical_gpus")
    overrides = _selection_overrides(selection_paths)
    route_plan = _load_route_plan(plan_path)
    execution = route_plan["execution_plan"]
    if overrides is not None:
        expected = pooled48.load_selected_candidates(overrides, require_sources=True)
        if expected != route_plan["selected_candidates"]:
            raise RouteBError("Route-B manifest selected_candidates disagree with selection overrides")
    pooled_plan_path = execution["pooled48_plan_path"]
    pooled_receipt_path = execution["pooled48_receipt_path"]
    pooled_result = pooled48.run(selection_paths=overrides, plan_path=pooled_plan_path)
    pooled_receipt = pooled48.reduce(
        selection_paths=overrides,
        plan_path=pooled_plan_path,
        output=pooled_receipt_path,
    )
    if pooled_receipt.get("status") != pooled48.POOLED48_STATUS:
        raise RouteBError("pooled48 reducer did not return a complete receipt")
    stratified_eval.build_plan(
        pooled_receipt=pooled_receipt_path,
        output=execution["stratified_plan_path"],
    )
    stratified_result = stratified_eval.run(plan_path=execution["stratified_plan_path"])
    stratified_receipt = stratified_eval.reduce(
        plan_path=execution["stratified_plan_path"],
        output=execution["stratified_receipt_path"],
    )
    if stratified_receipt.get("status") != stratified_eval.STRATIFIED_STATUS:
        raise RouteBError("stratified reducer did not return a complete receipt")
    intervention_eval.build_plan(
        pooled_receipt=pooled_receipt_path,
        stratified_receipt=execution["stratified_receipt_path"],
        output=execution["intervention_plan_path"],
    )
    intervention_result = intervention_eval.run(plan_path=execution["intervention_plan_path"])
    intervention_receipt = intervention_eval.reduce(
        plan_path=execution["intervention_plan_path"],
        output=execution["intervention_receipt_path"],
    )
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
        "route_b_plan_path": str(_absolute(plan_path)),
        "physical_gpus": list(ROUTE_B_PHYSICAL_GPUS),
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
    pooled_receipt: str | Path | None = None,
    stratified_receipt: str | Path | None = None,
    intervention_receipt: str | Path | None = None,
    plan_path: str | Path = ROUTE_B_PLAN_PATH,
    output: str | Path = ROUTE_B_RECEIPT_PATH,
) -> dict[str, Any]:
    """Validate the three complete producer receipts and seal Route-B order."""

    route_plan = _load_route_plan(plan_path)
    execution = route_plan["execution_plan"]
    persisted_receipts = {
        "pooled48": execution["pooled48_receipt_path"],
        "stratified": execution["stratified_receipt_path"],
        "intervention": execution["intervention_receipt_path"],
    }
    supplied_receipts = {
        "pooled48": pooled_receipt,
        "stratified": stratified_receipt,
        "intervention": intervention_receipt,
    }
    resolved_receipts: dict[str, str] = {}
    for name, supplied in supplied_receipts.items():
        if supplied is not None and _absolute(supplied) != _absolute(persisted_receipts[name]):
            raise RouteBError(
                f"Route-B {name} receipt path disagrees with the persisted execution plan: "
                f"{_absolute(supplied)} != {_absolute(persisted_receipts[name])}"
            )
        resolved_receipts[name] = persisted_receipts[name]

    pooled = _validate_producer_receipt(
        resolved_receipts["pooled48"],
        schema=pooled48.POOLED48_SCHEMA,
        status=pooled48.POOLED48_STATUS,
        name="pooled48",
    )
    stratified = _validate_producer_receipt(
        resolved_receipts["stratified"],
        schema=stratified_eval.STRATIFIED_SCHEMA,
        status=stratified_eval.STRATIFIED_STATUS,
        name="stratified",
    )
    intervention = _validate_producer_receipt(
        resolved_receipts["intervention"],
        schema=intervention_eval.INTERVENTION_RECEIPT_SCHEMA,
        status=intervention_eval.INTERVENTION_RECEIPT_STATUS,
        name="intervention",
    )
    selected = pooled["selected_candidates"]
    if route_plan["selected_candidates"] != selected:
        raise RouteBError("Route-B producer receipts disagree with the persisted Route-B selection")
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
    producer_gpu_sets = []
    for name, producer in (("pooled48", pooled), ("stratified", stratified), ("intervention", intervention)):
        if producer.get("physical_gpu_domain") != list(PHYSICAL_GPU_DOMAIN):
            raise RouteBError(f"{name} receipt physical_gpu_domain is not exactly 0..7")
        if producer.get("physical_gpu_mapping_policy") != PHYSICAL_GPU_MAPPING_POLICY:
            raise RouteBError(f"{name} receipt physical GPU mapping policy is unsupported")
        producer_gpus = pooled48.validate_physical_gpus(producer.get("physical_gpus"))
        if producer_gpus != ROUTE_B_PHYSICAL_GPUS:
            raise RouteBError(f"{name} receipt must use the exact persisted eight-GPU map")
        producer_gpu_sets.append(producer_gpus)
    if any(gpu_set != producer_gpu_sets[0] for gpu_set in producer_gpu_sets[1:]):
        raise RouteBError("Route-B producer receipts disagree on manifest-authoritative physical_gpus")
    selected_gpus = producer_gpu_sets[0]
    if selected_gpus != ROUTE_B_PHYSICAL_GPUS:
        raise RouteBError("Route-B producer receipts must use the exact persisted eight-GPU map")
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
        "physical_gpu_domain": list(PHYSICAL_GPU_DOMAIN),
        "physical_gpus": list(selected_gpus),
        "physical_gpu_mapping_policy": PHYSICAL_GPU_MAPPING_POLICY,
        "logical_gpu": "cuda:0",
        "process_count_per_gpu": 1,
        "num_mini_batches": 1,
        "producer_receipts": [
            {
                "name": "pooled48",
                "path": resolved_receipts["pooled48"],
                "schema": pooled48.POOLED48_SCHEMA,
                "status": pooled48.POOLED48_STATUS,
                "topology": pooled["topology"],
                "job_count": pooled.get("job_count"),
            },
            {
                "name": "stratified",
                "path": resolved_receipts["stratified"],
                "schema": stratified_eval.STRATIFIED_SCHEMA,
                "status": stratified_eval.STRATIFIED_STATUS,
                "topology": stratified["topology"],
                "job_count": stratified.get("job_count"),
            },
            {
                "name": "intervention",
                "path": resolved_receipts["intervention"],
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
        "route_b_plan_path": str(_absolute(plan_path)),
        "execution_plan": dict(execution),
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
    parser.add_argument("--plan", type=Path, default=ROUTE_B_PLAN_PATH)
    parser.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help="CPU fixture only for PLAN/BUILD; never permits RUN",
    )
    parser.add_argument("--pooled48", type=Path, default=None)
    parser.add_argument("--stratified", type=Path, default=None)
    parser.add_argument("--intervention", type=Path, default=None)
    parser.add_argument(
        "--physical-gpus",
        type=pooled48.parse_physical_gpus,
        default=None,
        help="exact ordered local physical GPU ids 0,1,2,3,4,5,6,7; PLAN/BUILD only",
    )
    _selection_args(parser)
    args = parser.parse_args(argv)
    try:
        if args.mode not in {"PLAN", "BUILD"} and args.physical_gpus is not None:
            raise RouteBError("--physical-gpus is valid only for PLAN and BUILD")
        selection_paths = _selection_paths_from_args(args)
        if args.mode in {"PLAN", "BUILD"}:
            payload = build_plan(
                selection_paths=selection_paths,
                require_sources=not args.allow_missing_sources,
                physical_gpus=args.physical_gpus,
                output=(args.output or ROUTE_B_PLAN_PATH) if args.mode == "BUILD" else None,
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        elif args.mode == "RUN":
            if args.allow_missing_sources:
                raise RouteBError("--allow-missing-sources is not valid for RUN")
            payload = run(selection_paths=selection_paths, plan_path=args.plan)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            payload = reduce(
                pooled_receipt=args.pooled48,
                stratified_receipt=args.stratified,
                intervention_receipt=args.intervention,
                plan_path=args.plan,
                output=args.output or ROUTE_B_RECEIPT_PATH,
            )
            print(json.dumps({"status": "WRITTEN", "path": str(_absolute(args.output or ROUTE_B_RECEIPT_PATH))}, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 ROUTE_B {args.mode} FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
