"""Route-B producer receipt reducer and candidate-freeze writer.

The three Route-B producers expose the same selected Route-A identities.  This
consumer performs only strict schema/provenance validation and preserves every
unique selected identity.  It deliberately does not rank candidates or apply
scientific completeness, symmetry, or success gates.
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
        V23_GPU_SUBWAVES,
        V23_PLAN_ID,
        V23_ROUTE_A_STEPS,
        V23Error,
        read_json,
        write_json,
    )
except ImportError:  # direct script invocation
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_GPU_SUBWAVES,
        V23_PLAN_ID,
        V23_ROUTE_A_STEPS,
        V23Error,
        read_json,
        write_json,
    )


POOLED48_PATH = REPO_ROOT / "logs_eval/base_v23/pooled48/V23_POOLED48.json"
STRATIFIED_PATH = REPO_ROOT / "logs_eval/base_v23/stratified/V23_STRATIFIED_EVAL.json"
INTERVENTION_PATH = REPO_ROOT / "logs_eval/base_v23/interventions/V23_INTERVENTION_EVAL.json"
CANDIDATE_FREEZE_PATH = REPO_ROOT / "logs_eval/base_v23/route_b/V23_CANDIDATE_FREEZE.json"

POOLED48_SCHEMA = "a2_piper_v23_pooled48_receipt_v1"
STRATIFIED_SCHEMA = "a2_piper_v23_stratified_eval_receipt_v1"
INTERVENTION_SCHEMA = "a2_piper_v23_intervention_eval_receipt_v1"
POOLED48_STATUS = "V23_POOLED48_COMPLETE"
STRATIFIED_STATUS = "V23_STRATIFIED_EVAL_COMPLETE"
INTERVENTION_STATUS = "V23_INTERVENTION_EVAL_COMPLETE"
CANDIDATE_FREEZE_SCHEMA = "a2_piper_v23_candidate_freeze_v1"
CANDIDATE_FREEZE_STATUS = "V23_CANDIDATE_FREEZE_COMPLETE"

SOURCE_SPECS = {
    "pooled48": (POOLED48_PATH, POOLED48_SCHEMA, POOLED48_STATUS),
    "stratified": (STRATIFIED_PATH, STRATIFIED_SCHEMA, STRATIFIED_STATUS),
    "intervention": (INTERVENTION_PATH, INTERVENTION_SCHEMA, INTERVENTION_STATUS),
}
SUBWAVE_ORDER = ("A1", "A2", "B1", "B2")
CANDIDATE_KEYS = (
    "source_branch",
    "plan_id",
    "identity_policy",
    "subwave",
    "seed",
    "cell",
    "row_id",
    "step",
    "checkpoint_path",
    "config_path",
    "scenario_path",
    "evaluation_root",
    "goal_reached",
    "supported_crossing",
    "unsafe_contacts",
    "terminal_failures",
)


class RouteBAnalysisError(V23Error):
    """A fixed Route-B producer interface is missing or inconsistent."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _absolute(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _load_receipt(path: Path, *, schema: str, status: str, name: str) -> dict[str, Any]:
    target = _absolute(path)
    payload = read_json(target)
    if payload.get("schema") != schema:
        raise RouteBAnalysisError(f"{name} schema must be {schema}: {target}")
    if payload.get("status") != status:
        raise RouteBAnalysisError(f"{name} status must be {status}: {target}")
    selected = payload.get("selected_candidates")
    if not isinstance(selected, list) or not selected:
        raise RouteBAnalysisError(
            f"{name} must contain a non-empty top-level selected_candidates list: {target}"
        )
    return payload


def load_fixed_receipts(
    paths: Mapping[str, str | Path] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    """Load exactly the three frozen producer receipts."""

    requested = {
        name: _absolute(paths[name]) if paths is not None and name in paths else spec[0]
        for name, spec in SOURCE_SPECS.items()
    }
    payloads: dict[str, dict[str, Any]] = {}
    resolved: dict[str, Path] = {}
    for name, (default_path, schema, status) in SOURCE_SPECS.items():
        path = requested[name]
        payloads[name] = _load_receipt(path, schema=schema, status=status, name=name)
        resolved[name] = path
    return payloads, resolved


def _require_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RouteBAnalysisError(f"selected candidate field {field} must be a non-empty string")
    return value


def _require_int(value: Any, *, field: str, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RouteBAnalysisError(f"selected candidate field {field} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        raise RouteBAnalysisError(f"selected candidate field {field} must be <= {maximum}")
    return value


def _validate_candidate(item: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise RouteBAnalysisError(f"selected_candidates[{index}] must be an object")
    if set(item) != set(CANDIDATE_KEYS):
        missing = sorted(set(CANDIDATE_KEYS) - set(item))
        extra = sorted(set(item) - set(CANDIDATE_KEYS))
        raise RouteBAnalysisError(
            f"selected_candidates[{index}] key set mismatch; missing={missing}, extra={extra}"
        )
    candidate = dict(item)
    if candidate["source_branch"] != "A2_Piper":
        raise RouteBAnalysisError(f"selected_candidates[{index}] source_branch must be A2_Piper")
    if candidate["plan_id"] != V23_PLAN_ID:
        raise RouteBAnalysisError(f"selected_candidates[{index}] plan_id disagrees with v23 plan")
    if candidate["identity_policy"] != "OWNER_NO_HASH_PATH_IDENTITY":
        raise RouteBAnalysisError(f"selected_candidates[{index}] identity_policy is unsupported")
    subwave = candidate["subwave"]
    if subwave not in SUBWAVE_ORDER:
        raise RouteBAnalysisError(f"selected_candidates[{index}] has unknown subwave {subwave!r}")
    spec = V23_GPU_SUBWAVES.get(subwave)
    if spec is None:
        raise RouteBAnalysisError(f"v23 subwave definition is inconsistent: {subwave}")
    if candidate["seed"] != spec["seed"]:
        raise RouteBAnalysisError(f"selected_candidates[{index}] seed disagrees with {subwave}")
    if candidate["cell"] not in spec["cells"]:
        raise RouteBAnalysisError(f"selected_candidates[{index}] cell is not in {subwave}")
    _require_string(candidate["row_id"], field="row_id")
    _require_int(candidate["step"], field="step", minimum=0)
    if candidate["step"] not in V23_ROUTE_A_STEPS:
        raise RouteBAnalysisError(f"selected_candidates[{index}] step is outside Route-A steps")
    for field in ("checkpoint_path", "config_path", "scenario_path", "evaluation_root"):
        _require_string(candidate[field], field=field)
    for field in ("goal_reached", "supported_crossing", "unsafe_contacts", "terminal_failures"):
        _require_int(candidate[field], field=field, maximum=16)
    return candidate


def _canonical_candidates(items: Any, *, name: str) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise RouteBAnalysisError(f"{name}.selected_candidates must be a non-empty list")
    rows = [_validate_candidate(item, index=index) for index, item in enumerate(items)]
    order = {name: index for index, name in enumerate(SUBWAVE_ORDER)}
    cell_order = {
        subwave: {cell: index for index, cell in enumerate(V23_GPU_SUBWAVES[subwave]["cells"])}
        for subwave in SUBWAVE_ORDER
    }
    rows.sort(key=lambda row: (order[row["subwave"]], cell_order[row["subwave"]][row["cell"]]))
    identities = {
        (row["subwave"], row["cell"], row["seed"], row["step"], row["checkpoint_path"])
        for row in rows
    }
    if len(identities) != len(rows):
        raise RouteBAnalysisError(f"{name}.selected_candidates contains duplicate checkpoint identities")
    return rows


def _freeze_id(candidate: Mapping[str, Any]) -> str:
    return (
        f"{candidate['subwave']}_{candidate['cell']}_seed{candidate['seed']}_step{candidate['step']}"
    )


def build_candidate_freeze(
    receipts: Mapping[str, Mapping[str, Any]],
    *,
    source_paths: Mapping[str, str | Path] | None = None,
) -> dict[str, Any]:
    """Validate fixed producer receipts and preserve all selected identities."""

    if set(receipts) != set(SOURCE_SPECS):
        raise RouteBAnalysisError("candidate freeze requires exactly pooled48, stratified, and intervention receipts")
    canonical_by_source = {
        name: _canonical_candidates(receipts[name].get("selected_candidates"), name=name)
        for name in SOURCE_SPECS
    }
    reference = canonical_by_source["pooled48"]
    reference_json = json.dumps(reference, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    for name in ("stratified", "intervention"):
        observed_json = json.dumps(
            canonical_by_source[name], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        if observed_json != reference_json:
            raise RouteBAnalysisError(
                f"{name}.selected_candidates does not exactly match pooled48 after canonical ordering"
            )
    paths = {
        name: str(_absolute(source_paths[name]))
        if source_paths is not None and name in source_paths
        else str(SOURCE_SPECS[name][0])
        for name in SOURCE_SPECS
    }
    selected = []
    for row in reference:
        item = dict(row)
        item["freeze_id"] = _freeze_id(row)
        item["evidence_status"] = "EVIDENCE_COMPLETE_FROM_THREE_ROUTE_B_RECEIPTS"
        selected.append(item)
    return {
        "schema": CANDIDATE_FREEZE_SCHEMA,
        "status": CANDIDATE_FREEZE_STATUS,
        "recorded_at_utc": _utc_now(),
        "source_branch": "A2_Piper",
        "plan_id": V23_PLAN_ID,
        "identity_policy": "OWNER_NO_HASH_PATH_IDENTITY",
        "route": "B",
        "physical_gpus": [0, 1],
        "logical_gpu": "cuda:0",
        "process_count_per_gpu": 1,
        "num_mini_batches": 1,
        "selection_policy": "PRESERVE_ALL_UNIQUE_EVIDENCE_COMPLETE_SELECTED_IDENTITIES",
        "ranking_gate": "NOT_APPLIED",
        "completeness_gate": "NOT_APPLIED",
        "symmetry_gate": "NOT_APPLIED",
        "source_receipts": [
            {
                "name": name,
                "path": paths[name],
                "schema": SOURCE_SPECS[name][1],
                "status": SOURCE_SPECS[name][2],
            }
            for name in SOURCE_SPECS
        ],
        "candidate_count": len(selected),
        "selected_candidates": selected,
        "missing_evidence": [],
        "excluded_claims": [
            "NO_ROUTE_B_RANKING_GATE",
            "NO_ROUTE_B_SYMMETRY_GATE",
            "NO_POLICY_QUALITY_CLAIM",
            "NO_RELEASE_CLAIM",
        ],
    }


def build_plan(
    *,
    paths: Mapping[str, str | Path] | None = None,
) -> dict[str, Any]:
    receipts, resolved = load_fixed_receipts(paths)
    return build_candidate_freeze(receipts, source_paths=resolved)


def reduce_to_receipt(
    *,
    output: str | Path = CANDIDATE_FREEZE_PATH,
    paths: Mapping[str, str | Path] | None = None,
) -> dict[str, Any]:
    payload = build_plan(paths=paths)
    write_json(_absolute(output), payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "REDUCE"), required=True)
    parser.add_argument("--pooled48", type=Path, default=POOLED48_PATH)
    parser.add_argument("--stratified", type=Path, default=STRATIFIED_PATH)
    parser.add_argument("--intervention", type=Path, default=INTERVENTION_PATH)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = {
        "pooled48": args.pooled48,
        "stratified": args.stratified,
        "intervention": args.intervention,
    }
    try:
        if args.mode == "PLAN":
            payload = build_plan(paths=paths)
            if args.output is not None:
                write_json(_absolute(args.output), payload)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            payload = reduce_to_receipt(output=args.output or CANDIDATE_FREEZE_PATH, paths=paths)
            print(json.dumps({"status": "WRITTEN", "path": str(_absolute(args.output or CANDIDATE_FREEZE_PATH))}, indent=2))
    except (OSError, TypeError, ValueError, V23Error) as exc:
        print(f"V23 ROUTE_B_ANALYSIS FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
