"""Mechanically adjudicate v20 checkpoints against the preregistered gates."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "a2_piper_v20_m22_adjudication_v1"
MANIFEST_SCHEMA = "a2_piper_v20_m22_candidate_manifest_v1"
EVIDENCE_SCHEMA = "a2_piper_v20_m22_evidence_v1"
TOPOLOGY = {
    "canonical16": {"episodes": 16, "minimum": 15},
    "pooled48": {"episodes": 48, "minimum": 46},
    "holdout64": {"episodes": 64, "minimum": 60},
}

_COMMON_SAFETY_GATES = frozenset(
    {
        "goal",
        "crossing_while_holding",
        "upper_dof_overspeed",
        "pre_crossing_bilateral",
        "pre_crossing_coasting",
        "pre_crossing_over_force",
        "opening_slip",
        "held_hinge_p50",
        "held_hinge_p95",
        "post_release_body_contact",
        "post_release_body_force",
    }
)
_SEND_FIRST_GATES = frozenset(
    {
        "goal_pre_send_crossing",
        "send_before_cross",
        "hinge_first_cross_p50",
        "hinge_first_cross_p10",
        "pre_send_forward_relief",
        "stage4_overtime",
    }
)
_CARRY_ARC_GATES = frozenset(
    {
        "arm_tangent_share_p50",
        "arm_tangent_share_p10",
        "arc_position_error",
        "arc_orientation_error",
        "along_handle_slip",
        "orthogonal_arc_residual",
    }
)
_SMOOTHNESS_GATES = frozenset(
    {
        "positive_hinge_velocity",
        "hinge_acceleration_p95",
        "hinge_jerk_p95",
        "arm_action_rate_p95",
        "arm_action_jerk_p95",
        "median_task_time",
    }
)


class V20AdjudicationError(ValueError):
    pass


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V20AdjudicationError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise V20AdjudicationError(f"{name} must be finite")
    return value


def _metric(metrics: Mapping[str, Any], key: str) -> float:
    if key not in metrics or metrics[key] is None:
        raise V20AdjudicationError(f"strict-valid metrics missing {key}")
    return _finite(metrics[key], key)


def _baseline(baselines: Mapping[str, Any], key: str) -> float:
    if key not in baselines:
        raise V20AdjudicationError(f"baseline missing {key}")
    return _finite(baselines[key], f"baseline.{key}")


def _failure_category_counts(failed_gates: Sequence[str]) -> tuple[int, int, int, int]:
    """Return preregistered common/send/carry/smoothness failure counts."""
    failed = set(failed_gates)
    return (
        len(failed & _COMMON_SAFETY_GATES),
        len(failed & _SEND_FIRST_GATES),
        len(failed & _CARRY_ARC_GATES),
        len(failed & _SMOOTHNESS_GATES),
    )


def evaluate_gates(
    metrics: Mapping[str, Any],
    *,
    topology: str,
    theta_send: float,
    relief_limit_m: float,
    arm_share_baseline: float,
    orientation_tolerance_rad: float,
    smoothness_baseline: Mapping[str, Any],
) -> dict[str, Any]:
    if topology not in TOPOLOGY:
        raise V20AdjudicationError(f"unsupported topology {topology!r}")
    theta_send = _finite(theta_send, "theta_send")
    relief_limit_m = _finite(relief_limit_m, "relief_limit_m")
    arm_share_baseline = _finite(arm_share_baseline, "arm_share_baseline")
    orientation_tolerance_rad = _finite(
        orientation_tolerance_rad, "orientation_tolerance_rad"
    )
    if theta_send < 0.90 or relief_limit_m < 0 or not 0 <= arm_share_baseline <= 1:
        raise V20AdjudicationError("frozen v20 gate values are outside their domain")
    expected = TOPOLOGY[topology]
    if int(_metric(metrics, "episode_count")) != expected["episodes"]:
        raise V20AdjudicationError(
            f"{topology} episode_count must equal {expected['episodes']}"
        )
    gates: dict[str, bool] = {}

    def gate(name: str, passed: bool) -> None:
        gates[name] = bool(passed)

    gate("goal", _metric(metrics, "goal_count") >= expected["minimum"])
    gate(
        "crossing_while_holding",
        _metric(metrics, "crossing_while_holding_count") >= expected["minimum"],
    )
    gate("upper_dof_overspeed", _metric(metrics, "upper_dof_overspeed_count") == 0)
    gate("pre_crossing_bilateral", _metric(metrics, "pre_crossing_bilateral_rate") >= 0.99)
    gate("pre_crossing_coasting", _metric(metrics, "pre_crossing_coasting_rate") < 0.02)
    gate("pre_crossing_over_force", _metric(metrics, "pre_crossing_over_force_rate") < 0.02)
    if metrics.get("opening_slip_p95_m") is not None:
        gate("opening_slip", _metric(metrics, "opening_slip_p95_m") <= 0.03)
    else:
        gate("opening_slip", topology == "canonical16")
    if topology != "canonical16":
        gate("held_hinge_p50", _metric(metrics, "held_hinge_p50") >= 1.45)
        gate("held_hinge_p95", _metric(metrics, "held_hinge_p95") >= 1.50)
        contact_limit = 2 if topology == "pooled48" else 3
        gate(
            "post_release_body_contact",
            _metric(metrics, "post_release_body_contact_count") <= contact_limit,
        )
    force_metric = metrics.get("post_release_body_force_max_p95_n")
    gate(
        "post_release_body_force",
        force_metric is not None and _finite(force_metric, "post_release_body_force_max_p95_n") < 80.0,
    )
    gate(
        "goal_pre_send_crossing",
        _metric(metrics, "goal_with_pre_send_crossing_count") == 0,
    )
    gate("send_before_cross", _metric(metrics, "send_ready_count") >= expected["minimum"])
    gate(
        "hinge_first_cross_p50",
        _metric(metrics, "hinge_at_first_crossing_p50") >= theta_send,
    )
    gate(
        "hinge_first_cross_p10",
        _metric(metrics, "hinge_at_first_crossing_p10") >= theta_send - 0.05,
    )
    gate(
        "pre_send_forward_relief",
        _metric(metrics, "pre_send_forward_displacement_p95") <= relief_limit_m + 0.02,
    )
    if topology != "canonical16":
        gate("stage4_overtime", _metric(metrics, "stage4_overtime_count") <= 2)
    gate(
        "arm_tangent_share_p50",
        _metric(metrics, "arm_tangent_share_p50")
        >= max(0.60, arm_share_baseline + 0.15),
    )
    gate("arm_tangent_share_p10", _metric(metrics, "arm_tangent_share_p10") >= 0.45)
    gate("arc_position_error", _metric(metrics, "arc_position_error_p95_m") <= 0.03)
    gate(
        "arc_orientation_error",
        _metric(metrics, "arc_orientation_error_p95_rad") <= orientation_tolerance_rad,
    )
    gate("along_handle_slip", _metric(metrics, "along_handle_slip_p95_m") <= 0.03)
    gate(
        "orthogonal_arc_residual",
        _metric(metrics, "orthogonal_arc_residual_p95_m") <= 0.03,
    )
    gate(
        "positive_hinge_velocity",
        _metric(metrics, "positive_hinge_velocity_p95") <= 0.40,
    )
    for key in (
        "hinge_acceleration_p95",
        "hinge_jerk_p95",
        "arm_action_rate_p95",
        "arm_action_jerk_p95",
    ):
        gate(key, _metric(metrics, key) <= 1.25 * _baseline(smoothness_baseline, key))
    gate(
        "median_task_time",
        _metric(metrics, "median_task_time_s")
        <= 1.20 * _baseline(smoothness_baseline, "median_task_time_s"),
    )
    failed = [name for name, passed in gates.items() if not passed]
    return {"status": "PASS" if not failed else "FAIL", "gates": gates, "failed_gates": failed}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V20AdjudicationError(f"cannot read {path}: {exc}") from exc


def adjudicate(
    manifest: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    group: str,
    topology: str,
    frozen_values: Mapping[str, Any],
) -> dict[str, Any]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise V20AdjudicationError("manifest schema mismatch")
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise V20AdjudicationError("evidence schema mismatch")
    candidates = manifest.get("candidates")
    rows = evidence.get("rows")
    if not isinstance(candidates, list) or not isinstance(rows, list):
        raise V20AdjudicationError("manifest/evidence rows must be lists")
    candidate_index = {row["candidate_id"]: row for row in candidates}
    row_index = {row["candidate_id"]: row for row in rows}
    if len(candidate_index) != len(candidates) or set(candidate_index) != set(row_index):
        raise V20AdjudicationError("manifest/evidence candidate identity mismatch")
    results = []
    for candidate in candidates:
        row = row_index[candidate["candidate_id"]]
        for key in ("checkpoint_path", "checkpoint_sha256"):
            expected = candidate["path"] if key == "checkpoint_path" else candidate["sha256"]
            if row.get(key) != expected:
                raise V20AdjudicationError(
                    f"{candidate['candidate_id']} evidence {key} mismatch"
                )
        status = row.get("strict_status")
        if status == "STRICT_INVALID":
            if not isinstance(row.get("reason"), str) or not row["reason"]:
                raise V20AdjudicationError("STRICT_INVALID requires reason")
            results.append(
                {
                    "candidate": dict(candidate),
                    "strict_status": status,
                    "gate_status": "INELIGIBLE",
                    "failed_gates": ["STRICT_INVALID"],
                    "reason": row["reason"],
                }
            )
            continue
        if status != "STRICT_VALID" or not isinstance(row.get("metrics"), Mapping):
            raise V20AdjudicationError("evidence status/metrics are malformed")
        gate_result = evaluate_gates(
            row["metrics"],
            topology=topology,
            theta_send=frozen_values["theta_send"],
            relief_limit_m=frozen_values["relief_limit_m"],
            arm_share_baseline=frozen_values["arm_share_baseline"],
            orientation_tolerance_rad=frozen_values["orientation_tolerance_rad"],
            smoothness_baseline=frozen_values["smoothness_baseline"],
        )
        results.append(
            {
                "candidate": dict(candidate),
                "strict_status": status,
                "metrics": dict(row["metrics"]),
                "gate_status": gate_result["status"],
                "gates": gate_result["gates"],
                "failed_gates": gate_result["failed_gates"],
            }
        )
    promotable = [row for row in results if row["gate_status"] == "PASS"]
    selected = None
    if promotable:
        selected = min(
            promotable,
            key=lambda row: (
                _metric(row["metrics"], "median_task_time_s"),
                int(row["candidate"]["step"]),
            ),
        )
        selection_status = "PROMOTABLE_CHECKPOINT"
    else:
        strict_valid = [row for row in results if row["strict_status"] == "STRICT_VALID"]
        if strict_valid:
            selected = min(
                strict_valid,
                key=lambda row: (
                    *_failure_category_counts(row["failed_gates"]),
                    _metric(row["metrics"], "median_task_time_s"),
                    int(row["candidate"]["step"]),
                ),
            )
        selection_status = "NO_PROMOTABLE_CHECKPOINT"
    return {
        "schema": SCHEMA,
        "group": group,
        "topology": topology,
        "frozen_values": dict(frozen_values),
        "rows": results,
        "selection_status": selection_status,
        "selected_checkpoint": None if selected is None else selected["candidate"],
        "selected_failed_gates": [] if selected is None else selected["failed_gates"],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--frozen-values", type=Path, required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--topology", choices=tuple(TOPOLOGY), default="canonical16")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.output.exists():
        raise V20AdjudicationError(f"refusing to overwrite {args.output}")
    result = adjudicate(
        _load_json(args.manifest),
        _load_json(args.evidence),
        group=args.group,
        topology=args.topology,
        frozen_values=_load_json(args.frozen_values),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise V20AdjudicationError(f"refusing to overwrite {args.output}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.unlink(args.output)
        except FileNotFoundError:
            pass
        raise
    print(f"{result['selection_status']}: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V20AdjudicationError as exc:
        print(f"v20 M22 ADJUDICATION FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
