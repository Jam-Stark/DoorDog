"""Strict M22 checkpoint gate and mechanical selection."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    GROUPS,
    NO_RELEASE,
    PLAN_ID,
    POLICY_PASS,
    R1Error,
    RUNTIME_PASS,
    canonical_topology,
    exact_digest,
    load_json,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_m22_adjudication_v3"
STEPS = tuple(range(250, 2501, 250))


def _metric(metrics: Mapping[str, Any], key: str) -> float:
    value = metrics.get(key)
    if isinstance(value, Mapping) or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise R1Error(f"strict R1 metrics missing/non-finite {key}")
    return float(value)


def evaluate_gates(metrics: Mapping[str, Any], *, topology: str = "canonical16") -> dict[str, Any]:
    topo = canonical_topology(topology)
    gates = {
        "goal": _metric(metrics, "goal_count") >= topo["minimum"],
        "crossing_while_holding": _metric(metrics, "crossing_while_holding_count") >= topo["minimum"],
        "upper_dof_overspeed": _metric(metrics, "upper_dof_overspeed_count") == 0,
        "pre_crossing_bilateral": _metric(metrics, "pre_crossing_bilateral_rate") >= 0.99,
        "pre_crossing_coasting": _metric(metrics, "pre_crossing_coasting_rate") < 0.02,
        "pre_crossing_over_force": _metric(metrics, "pre_crossing_over_force_rate") < 0.02,
        "goal_pre_send_crossing": _metric(metrics, "goal_with_pre_send_crossing_count") == 0,
        "send_before_cross": _metric(metrics, "send_ready_count") >= topo["minimum"],
        "hinge_first_cross_p50": _metric(metrics, "hinge_at_first_crossing_p50") >= 0.90,
        "hinge_first_cross_p10": _metric(metrics, "hinge_at_first_crossing_p10") >= 0.85,
        "pre_send_forward": _metric(metrics, "pre_send_forward_displacement_p95") <= 0.20,
        "pre_send_lateral": _metric(metrics, "pre_send_lateral_displacement_p95") <= 0.15,
        "pre_send_planar": _metric(metrics, "pre_send_planar_displacement_p95") <= 0.25,
        "pre_send_yaw": _metric(metrics, "pre_send_yaw_change_p95") <= 0.30,
        "arm_tangent_share_p50": _metric(metrics, "arm_tangent_share_p50") >= 0.60,
        "arm_tangent_share_p10": _metric(metrics, "arm_tangent_share_p10") >= 0.45,
        "arc_position_error": _metric(metrics, "arc_position_error_p95_m") <= 0.03,
        "arc_orientation_error": _metric(metrics, "arc_orientation_error_p95_rad") <= 0.25,
        "along_handle_slip": _metric(metrics, "along_handle_slip_p95_m") <= 0.03,
        "positive_income_ratio": _metric(metrics, "a_positive_income_ratio_p95") <= 0.10,
        "positive_hinge_velocity": _metric(metrics, "positive_hinge_velocity_p95") <= 0.40,
        "hinge_acceleration": _metric(metrics, "hinge_acceleration_p95") <= 1.00,
        "hinge_jerk": _metric(metrics, "hinge_jerk_p95") <= 28.0,
        "arm_action_rate": _metric(metrics, "arm_action_rate_p95") <= 2.20,
        "arm_action_jerk": _metric(metrics, "arm_action_jerk_p95") <= 3.60,
        "task_time": _metric(metrics, "median_task_time_s") <= 15.0,
    }
    if topology != "canonical16":
        gates.update(
            {
                "held_hinge_p50": _metric(metrics, "held_hinge_p50") >= 1.45,
                "held_hinge_p95": _metric(metrics, "held_hinge_p95") >= 1.50,
                "post_release_contact": _metric(metrics, "post_release_body_contact_count")
                <= (2 if topology == "pooled48" else 3),
                "post_release_force": _metric(metrics, "post_release_body_force_p95_n") < 80.0,
                "opening_slip": _metric(metrics, "opening_slip_p95_m") <= 0.03,
                "stage4_overtime": _metric(metrics, "stage4_overtime_count") <= 2,
            }
        )
    failed = [name for name, passed in gates.items() if not passed]
    return {
        "status": "STRICT_VALID" if not failed else "STRICT_INVALID",
        "gates": gates,
        "failed_gates": failed,
    }


def _validate_row(
    row: Mapping[str, Any],
    *,
    group: str,
    expected_steps: set[int] | None = None,
) -> None:
    candidate = row.get("candidate")
    if not isinstance(candidate, Mapping) or candidate.get("group") != group:
        raise R1Error(f"M22 row is not bound to group {group}")
    step = candidate.get("step")
    if isinstance(step, bool) or not isinstance(step, int) or step not in STEPS:
        raise R1Error("M22 row checkpoint step is invalid")
    if expected_steps is not None and step not in expected_steps:
        raise R1Error("M22 row is not in the frozen candidate manifest")
    for key in ("path", "sha256", "run_id", "config_sha256"):
        value = candidate.get(key)
        if not isinstance(value, str) or not value:
            raise R1Error(f"M22 candidate {key} must be concrete")
    exact_digest(candidate["sha256"], name="M22 candidate.sha256", length=64)
    exact_digest(candidate["config_sha256"], name="M22 candidate.config_sha256", length=64)
    binding = row.get("binding")
    if not isinstance(binding, Mapping):
        raise R1Error("M22 row binding is required")
    for key in ("checkpoint_sha256", "config_sha256", "group", "run_id"):
        if key not in binding:
            raise R1Error("M22 row binding is incomplete")
    exact_digest(binding["checkpoint_sha256"], name="M22 binding.checkpoint_sha256", length=64)
    exact_digest(binding["config_sha256"], name="M22 binding.config_sha256", length=64)
    if binding["checkpoint_sha256"] != candidate["sha256"] or binding["config_sha256"] != candidate["config_sha256"]:
        raise R1Error("M22 row candidate/binding hash mismatch")
    if binding["group"] != group or binding["run_id"] != candidate["run_id"]:
        raise R1Error("M22 row group/run binding mismatch")
    output = row.get("output")
    if not isinstance(output, Mapping) or output.get("group") != group or output.get("step") != step:
        raise R1Error("M22 row output binding is incomplete")
    if not isinstance(output.get("path"), str) or "logs_eval/base_v20_R1/m22/" + group not in output["path"].replace("\\", "/"):
        raise R1Error("M22 row output path is not canonical")
    command = row.get("eval_command")
    if not isinstance(command, Mapping) or not isinstance(command.get("command"), list) or command.get("exit_code") != 0:
        raise R1Error("M22 row requires strict completed eval command evidence")
    if row.get("strict_status") != "STRICT_VALID":
        raise R1Error("M22 row must be STRICT_VALID before gate evaluation")


def _selection_key(row: Mapping[str, Any]) -> tuple[float, int]:
    metrics = row.get("metrics")
    if not isinstance(metrics, Mapping):
        raise R1Error("M22 selected row metrics are required")
    # Every common/send/arm/arc/safety gate is already passed. Selection is
    # task time first, then earlier checkpoint step exactly as specified.
    return (float(_metric(metrics, "median_task_time_s")), int(row["candidate"]["step"]))


def adjudicate(
    manifest: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    group: str,
    topology: str = "canonical16",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    if manifest.get("plan_id") != PLAN_ID or manifest.get("group") != group:
        raise R1Error("M22 manifest provenance mismatch")
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != len(STEPS):
        raise R1Error("M22 manifest must contain exactly ten candidates")
    expected_steps = {int(candidate["step"]) for candidate in candidates}
    rows = evidence.get("rows")
    if not isinstance(rows, list) or len(rows) != len(STEPS):
        raise R1Error("R1 M22 evidence requires exactly ten rows")
    adjudicated = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise R1Error("M22 evidence row must be a mapping")
        _validate_row(row, group=group, expected_steps=expected_steps)
        result = evaluate_gates(row["metrics"], topology=topology)
        adjudicated.append(
            {
                "candidate": row["candidate"],
                "metrics": row["metrics"],
                "binding": row["binding"],
                "output": row["output"],
                "eval_command": row["eval_command"],
                **result,
            }
        )
    passing = [row for row in adjudicated if row["status"] == "STRICT_VALID"]
    selected = min(passing, key=_selection_key) if passing else None
    report = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "group": group,
        "status": RUNTIME_PASS,
        "selection_status": POLICY_PASS if selected else NO_RELEASE,
        "selected_checkpoint": selected,
        "rows": adjudicated,
        "exact_rows": len(rows),
    }
    if output_dir is not None:
        write_json_no_overwrite(output_dir / "m22_adjudication.json", report)
    return report


def adjudicate_all(
    *,
    manifests: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    topology: str = "canonical16",
) -> dict[str, Any]:
    expected = {row["group"] for row in GROUPS}
    if set(manifests) != expected or set(evidence) != expected:
        raise R1Error("strict M22 requires manifests and evidence for exactly G1-G7")
    reports = {}
    for group in sorted(expected):
        report = adjudicate(manifests[group], evidence[group], group=group, topology=topology)
        if report["exact_rows"] != len(STEPS):
            raise R1Error(f"strict M22 requires ten rows for {group}")
        reports[group] = report
    return {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": RUNTIME_PASS,
        "groups": reports,
        "seven_by_ten": True,
        "total_rows": len(GROUPS) * len(STEPS),
    }


def _require_blocked_r1_cli_opt_in() -> None:
    if "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" not in __import__("os").environ:
        print(
            "R1 execution is blocked by default; set BASE_V20_ALLOW_BLOCKED_R1_EXECUTION explicitly to run historical tooling",
            file=__import__("sys").stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _require_blocked_r1_cli_opt_in()
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--group", required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    adjudicate(
        load_json(args.manifest),
        load_json(args.evidence),
        group=args.group,
        output_dir=args.output_dir,
    )
