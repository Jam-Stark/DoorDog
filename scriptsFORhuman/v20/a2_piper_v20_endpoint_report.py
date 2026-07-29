"""Build seven pooled48 v20 endpoint judgements and freeze one release candidate."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v20_endpoint_report_v1"
EVIDENCE_SCHEMA = "a2_piper_v20_m22_evidence_v1"
GROUPS = tuple(f"G{index}" for index in range(1, 8))
ELIGIBLE_GROUPS = ("G3", "G4", "G5", "G6", "G7")


class V20EndpointError(ValueError):
    pass


def _load_adjudicator():
    path = Path(__file__).with_name("a2_piper_v20_m22_adjudicator.py")
    spec = importlib.util.spec_from_file_location("a2_piper_v20_adjudicator_for_endpoint", path)
    if spec is None or spec.loader is None:
        raise V20EndpointError(f"cannot import adjudicator {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADJ = _load_adjudicator()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V20EndpointError(f"cannot read {path}: {exc}") from exc


def _single_pooled_row(path: Path, group: str) -> Mapping[str, Any]:
    payload = _load_json(path)
    if payload.get("schema") != EVIDENCE_SCHEMA:
        raise V20EndpointError(f"{group} pooled evidence schema mismatch")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise V20EndpointError(f"{group} pooled evidence must contain exactly one selected row")
    row = rows[0]
    if row.get("evaluation_topology") != "pooled48":
        raise V20EndpointError(f"{group} selected evidence must be pooled48")
    if row.get("strict_status") not in {"STRICT_VALID", "STRICT_INVALID"}:
        raise V20EndpointError(f"{group} strict status is malformed")
    return row


def _a_claim(groups: Mapping[str, Mapping[str, Any]]) -> bool:
    if any(groups[group]["numeric_gate_status"] != "PASS" for group in ("G6", "G7")):
        return False
    if groups["G4"]["numeric_gate_status"] != "PASS":
        return False
    g4 = groups["G4"]["metrics"]
    for group in ("G6", "G7"):
        metrics = groups[group]["metrics"]
        if metrics["arm_tangent_share_p50"] < g4["arm_tangent_share_p50"] + 0.10:
            return False
        if metrics["goal_count"] < g4["goal_count"] - 2:
            return False
        if metrics["opening_slip_p95_m"] is None or metrics["opening_slip_p95_m"] > 0.03:
            return False
    return True


def build_endpoint_report(
    pooled_sources: Mapping[str, Path],
    frozen_values: Mapping[str, Any],
) -> dict[str, Any]:
    if set(pooled_sources) != set(GROUPS):
        raise V20EndpointError("pooled sources must contain exactly G1..G7")
    groups: dict[str, dict[str, Any]] = {}
    for group in GROUPS:
        row = _single_pooled_row(Path(pooled_sources[group]), group)
        if row["strict_status"] == "STRICT_INVALID":
            if not isinstance(row.get("reason"), str) or not row["reason"]:
                raise V20EndpointError(f"{group} STRICT_INVALID requires reason")
            groups[group] = {
                "strict_status": "STRICT_INVALID",
                "numeric_gate_status": "INELIGIBLE",
                "failed_gates": ["STRICT_INVALID"],
                "reason": row["reason"],
                "checkpoint": None,
                "metrics": None,
            }
            continue
        if not isinstance(row.get("metrics"), Mapping):
            raise V20EndpointError(f"{group} strict-valid row lacks metrics")
        gate = ADJ.evaluate_gates(
            row["metrics"],
            topology="pooled48",
            theta_send=frozen_values["theta_send"],
            relief_limit_m=frozen_values["relief_limit_m"],
            arm_share_baseline=frozen_values["arm_share_baseline"],
            orientation_tolerance_rad=frozen_values["orientation_tolerance_rad"],
            smoothness_baseline=frozen_values["smoothness_baseline"],
        )
        checkpoint = {
            "path": row.get("checkpoint_path"),
            "sha256": row.get("checkpoint_sha256"),
            "candidate_id": row.get("candidate_id"),
        }
        if any(not isinstance(checkpoint[key], str) or not checkpoint[key] for key in checkpoint):
            raise V20EndpointError(f"{group} selected checkpoint provenance is incomplete")
        groups[group] = {
            "strict_status": "STRICT_VALID",
            "numeric_gate_status": gate["status"],
            "failed_gates": gate["failed_gates"],
            "checkpoint": checkpoint,
            "metrics": dict(row["metrics"]),
        }
    passing = [group for group in ELIGIBLE_GROUPS if groups[group]["numeric_gate_status"] == "PASS"]
    full_claim = _a_claim(groups)
    selected_group = None
    if full_claim:
        selected_group = min(
            ("G6", "G7"),
            key=lambda group: (
                groups[group]["metrics"]["median_task_time_s"],
                groups[group]["checkpoint"]["candidate_id"],
            ),
        )
    else:
        for group in ("G3", "G4", "G5"):
            if group in passing:
                selected_group = group
                break
    if selected_group is None and not full_claim:
        for group in ("G6", "G7"):
            if group in passing:
                selected_group = group
                break
    release = None if selected_group is None else {
        "group": selected_group,
        **groups[selected_group]["checkpoint"],
    }
    return {
        "schema": SCHEMA,
        "groups": groups,
        "eligible_groups": list(ELIGIBLE_GROUPS),
        "a_factor_claim_status": "PASS" if full_claim else "FAIL",
        "release_status": "RELEASE_CANDIDATE_FROZEN" if release else "NO_V20_RELEASE",
        "release_candidate": release,
        "fallback": None,
        "sample_size_statement": "Pooled48 is descriptive evidence and is not statistical proof.",
    }


def _parse_group_paths(values: Sequence[str]) -> dict[str, Path]:
    result = {}
    for value in values:
        if "=" not in value:
            raise V20EndpointError("--pooled must be GROUP=PATH")
        group, path = value.split("=", 1)
        if group in result:
            raise V20EndpointError(f"duplicate pooled group {group}")
        result[group] = Path(path)
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pooled", action="append", required=True)
    parser.add_argument("--frozen-values", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.output.exists():
        raise V20EndpointError(f"refusing to overwrite {args.output}")
    report = build_endpoint_report(
        _parse_group_paths(args.pooled), _load_json(args.frozen_values)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{report['release_status']}: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (V20EndpointError, ADJ.V20AdjudicationError) as exc:
        print(f"v20 ENDPOINT FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
