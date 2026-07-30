"""Strict, one-shot adjudication for the R1 G4 learnability pilot.

The pilot has one fixed endpoint (step 750); this module only adjudicates an
already-produced evidence object and never chooses a checkpoint or retries a
run. Missing fields are errors rather than implicit zeros.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    PLAN_ID,
    NO_RELEASE,
    POLICY_LEARNABILITY_PASS,
    R1Error,
    exact_digest,
    load_json,
    write_json_no_overwrite,
)


SCHEMA = "a2_piper_v20_R1_pilot_adjudication_v1"


def _required(evidence: Mapping[str, Any], key: str) -> Any:
    if key not in evidence:
        raise R1Error(f"pilot evidence missing required field: {key}")
    return evidence[key]


def _number(evidence: Mapping[str, Any], key: str) -> float:
    value = _required(evidence, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise R1Error(f"pilot evidence field {key} must be a finite number")
    return float(value)


def _integer(evidence: Mapping[str, Any], key: str) -> int:
    value = _required(evidence, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise R1Error(f"pilot evidence field {key} must be an integer")
    return value


def _boolean(evidence: Mapping[str, Any], key: str) -> bool:
    value = _required(evidence, key)
    if not isinstance(value, bool):
        raise R1Error(f"pilot evidence field {key} must be boolean")
    return value


def evaluate_pilot(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate every frozen pilot gate against a flat strict evidence mapping."""
    if not isinstance(evidence, Mapping):
        raise R1Error("pilot evidence must be a mapping")
    checkpoints = _required(evidence, "finite_checkpoints")
    if not isinstance(checkpoints, Mapping):
        raise R1Error("finite_checkpoints must map 250/500/750 to booleans")
    checkpoint_ok = all(checkpoints.get(str(step), checkpoints.get(step)) is True for step in (250, 500, 750))
    transition_steps = _required(evidence, "schedule_transition_steps")
    if not isinstance(transition_steps, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in transition_steps):
        raise R1Error("schedule_transition_steps must be an integer list")
    gates: dict[str, bool] = {
        "natural_exit0": _integer(evidence, "exit_code") == 0,
        "exact_750_batches": (_integer(evidence, "batches_completed") == 750 and _integer(evidence, "batches_expected") == 750),
        "finite_step250_500_750": checkpoint_ok and _boolean(evidence, "optimizer_state_finite"),
        "schedule_transition_once_at_500": transition_steps == [500],
        "snapshot_audit_ok": _boolean(evidence, "snapshot_audit_ok"),
        "strict_valid_canonical16": (_integer(evidence, "strict_valid_count") == 16 and _integer(evidence, "strict_total_count") == 16),
        "telemetry_finite_and_well_formed": (_integer(evidence, "nonfinite_telemetry_count") == 0 and _integer(evidence, "malformed_telemetry_count") == 0),
        "exact_hash_binding": _boolean(evidence, "exact_hash_binding"),
        "goal_minimum": _integer(evidence, "goal_count") >= 8,
        "crossing_while_holding_minimum": _integer(evidence, "crossing_while_holding_count") >= 8,
        "stage4_occupancy_nonzero": _integer(evidence, "stage4_occupancy_count") > 0,
        "last50_hard_goal_rate_positive": _number(evidence, "last50_hard_goal_rate") > 0.0,
        "terminal_reason_concentration": _number(evidence, "max_terminal_reason_share") <= 0.95,
        "crossing_hinge_p50": _number(evidence, "crossing_hinge_p50") >= 0.82,
        "high_hinge_valid_hold_count": _integer(evidence, "valid_hold_crossing_at_or_above_090_count") >= 4,
        "send_ready_minimum": _integer(evidence, "send_ready_count") >= 4,
        "pre_send_arm_tangent_share_p50": _number(evidence, "pre_send_arm_tangent_share_p50") >= 0.30,
        "hard_send_ready_rate": _number(evidence, "hard_send_ready_rate_700_749") >= 0.10,
        "hard_terminal_rate_reduction": _number(evidence, "hard_terminal_rate_700_749") <= 0.80 * _number(evidence, "hard_terminal_rate_500_549"),
        "upper_dof_overspeed_zero": _integer(evidence, "upper_dof_overspeed_count") == 0,
        "goal_body_collision_before_crossing_zero": _integer(evidence, "goal_body_collision_before_crossing_count") == 0,
        "arc_position_error": _number(evidence, "arc_position_error_p95_m") <= 0.050,
        "arc_orientation_error": _number(evidence, "arc_orientation_error_p95_rad") <= 0.90,
        "positive_hinge_velocity": _number(evidence, "positive_hinge_velocity_p95") <= 0.45,
        "hinge_acceleration": _number(evidence, "hinge_acceleration_p95") <= 1.25,
        "hinge_jerk": _number(evidence, "hinge_jerk_p95") <= 35.0,
        "arm_action_rate": _number(evidence, "arm_raw_action_rate_p95") <= 2.75,
        "arm_action_jerk": _number(evidence, "arm_raw_action_jerk_p95") <= 4.50,
    }
    failed = [name for name, passed in gates.items() if not passed]
    return {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": POLICY_LEARNABILITY_PASS if not failed else NO_RELEASE,
        # Pilot adjudication can only release a blocker verdict; it never
        # grants formal-training readiness.  Admission is a separate chain gate.
        "formal_training_ready": False,
        "gates": gates,
        "failed_gates": failed,
    }


def validate_pilot_provenance(evidence: Mapping[str, Any]) -> None:
    provenance = evidence.get("provenance")
    if not isinstance(provenance, Mapping):
        raise R1Error("pilot evidence requires a provenance mapping")
    if provenance.get("plan_id") != PLAN_ID:
        raise R1Error("pilot evidence provenance plan_id mismatch")
    for key, length in (
        ("plan_sha256", 64),
        ("checkpoint_sha256", 64),
        ("config_sha256", 64),
        ("urdf_sha256", 64),
        ("git_commit", 40),
    ):
        exact_digest(provenance.get(key), name="pilot provenance." + key, length=length)
    for key in ("exit_code", "batches_completed", "strict_valid_count", "strict_total_count"):
        value = evidence.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise R1Error(f"pilot evidence {key} must be an integer")
    if evidence["strict_valid_count"] != evidence["strict_total_count"] or evidence["strict_total_count"] != 16:
        raise R1Error("pilot canonical16 denominator must be exactly 16 strict-valid records")
    denominators = evidence.get("denominators", {})
    if denominators is not None:
        if not isinstance(denominators, Mapping):
            raise R1Error("pilot denominators must be a mapping")
        for key, value in denominators.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise R1Error(f"pilot denominator {key} must be a positive integer")


def strict_adjudicate(
    *,
    evidence: Mapping[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    validate_pilot_provenance(evidence)
    command = evidence.get("command")
    if not isinstance(command, list) or not command:
        raise R1Error("pilot evidence requires the exact executed command")
    if evidence.get("exit_code") != 0:
        raise R1Error("pilot evidence command must exit zero before gate evaluation")
    result = evaluate_pilot(evidence)
    result["formal_training_ready"] = False
    result["provenance_validated"] = True
    result["status"] = (
        POLICY_LEARNABILITY_PASS if not result["failed_gates"] else NO_RELEASE
    )
    if output_dir is not None:
        write_json_no_overwrite(output_dir / "pilot_adjudication.json", result)
    return result


def adjudicate(*, evidence: Mapping[str, Any], output_dir: Path | None = None) -> dict[str, Any]:
    # Compatibility name intentionally retains the strict provenance gate.
    return strict_adjudicate(evidence=evidence, output_dir=output_dir)


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
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    strict_adjudicate(evidence=load_json(args.evidence), output_dir=args.output_dir)
