from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scriptsFORhuman/v20/a2_piper_v20_final_analysis.py"
SPEC = importlib.util.spec_from_file_location("a2_piper_v20_final_analysis_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
FINAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINAL)


def _metrics(episodes: int, minimum: int) -> dict:
    return {
        "episode_count": episodes,
        "goal_count": minimum,
        "crossing_while_holding_count": minimum,
        "send_ready_count": minimum,
        "pre_send_root_crossing_count": 0,
        "goal_with_pre_send_crossing_count": 0,
        "upper_dof_overspeed_count": 0,
        "stage4_overtime_count": 0,
        "post_release_body_contact_count": 0,
        "post_release_body_force_max_p95_n": 40.0,
        "pre_crossing_bilateral_rate": 1.0,
        "pre_crossing_coasting_rate": 0.0,
        "pre_crossing_over_force_rate": 0.0,
        "hinge_at_first_crossing_p10": 1.0,
        "hinge_at_first_crossing_p50": 1.05,
        "pre_send_forward_displacement_p95": 0.05,
        "held_hinge_p50": 1.50,
        "held_hinge_p95": 1.55,
        "opening_slip_p95_m": 0.02,
        "arm_tangent_share_p10": 0.50,
        "arm_tangent_share_p50": 0.70,
        "arc_position_error_p95_m": 0.02,
        "arc_orientation_error_p95_rad": 0.10,
        "along_handle_slip_p95_m": 0.01,
        "orthogonal_arc_residual_p95_m": 0.01,
        "positive_hinge_velocity_p95": 0.30,
        "hinge_acceleration_p95": 1.0,
        "hinge_jerk_p95": 1.0,
        "arm_action_rate_p95": 1.0,
        "arm_action_jerk_p95": 1.0,
        "median_task_time_s": 10.0,
    }


def _frozen() -> dict:
    return {
        "theta_send": 1.0,
        "relief_limit_m": 0.1,
        "arm_share_baseline": 0.5,
        "orientation_tolerance_rad": 0.2,
        "smoothness_baseline": {
            "hinge_acceleration_p95": 1.0,
            "hinge_jerk_p95": 1.0,
            "arm_action_rate_p95": 1.0,
            "arm_action_jerk_p95": 1.0,
            "median_task_time_s": 10.0,
        },
    }


def _m22_rows() -> list[dict]:
    return [
        {
            "group": f"G{group}",
            "candidate_id": f"model_step_{step * 250:06d}.pt",
            "strict_status": "STRICT_VALID",
        }
        for group in range(1, 8)
        for step in range(1, 11)
    ]


def _endpoint() -> dict:
    checkpoint = {
        "group": "G3",
        "path": "/G3/model_step_001000.pt",
        "sha256": "3" * 64,
        "candidate_id": "model_step_001000.pt",
    }
    return {
        "schema": FINAL.ENDPOINT.SCHEMA,
        "release_status": "RELEASE_CANDIDATE_FROZEN",
        "release_candidate": checkpoint,
        "groups": {f"G{i}": {} for i in range(1, 8)},
    }


def test_final_release_requires_same_frozen_holdout_and_render() -> None:
    endpoint = _endpoint()
    holdout = {
        "schema": "a2_piper_v20_holdout64_v1",
        "group": "G3",
        "checkpoint_path": endpoint["release_candidate"]["path"],
        "checkpoint_sha256": endpoint["release_candidate"]["sha256"],
        "strict_status": "STRICT_VALID",
        "metrics": _metrics(64, 60),
    }
    render = {
        "schema": "a2_piper_v20_render_qa_v1",
        "media_status": "PASS",
        "groups": {
            "G3": {
                "checkpoint": endpoint["release_candidate"]["path"],
                "checkpoint_sha256": endpoint["release_candidate"]["sha256"],
                "behavior_status": "PASS",
            }
        },
    }
    paired = {"schema": "a2_piper_v20_paired_analysis_v1"}
    report = FINAL.build_final_analysis(
        endpoint=endpoint,
        m22_rows=_m22_rows(),
        paired=paired,
        holdout=holdout,
        render_qa=render,
        frozen_values=_frozen(),
    )
    assert report["final_status"] == "RELEASE"
    assert report["fallback"] is None

    for force_value in (None, 80.0):
        invalid_metrics = _metrics(64, 60)
        if force_value is None:
            invalid_metrics.pop("post_release_body_force_max_p95_n")
        else:
            invalid_metrics["post_release_body_force_max_p95_n"] = force_value
        holdout["checkpoint_sha256"] = endpoint["release_candidate"]["sha256"]
        holdout["metrics"] = invalid_metrics
        rejected = FINAL.build_final_analysis(
            endpoint=endpoint,
            m22_rows=_m22_rows(),
            paired=paired,
            holdout=holdout,
            render_qa=render,
            frozen_values=_frozen(),
        )
        assert rejected["final_status"] == "NO_RELEASE"
        assert "holdout64:post_release_body_force" in rejected["failed_gates"]

    holdout["checkpoint_sha256"] = "4" * 64
    with pytest.raises(FINAL.V20FinalError, match="does not bind"):
        FINAL.build_final_analysis(
            endpoint=endpoint,
            m22_rows=_m22_rows(),
            paired=paired,
            holdout=holdout,
            render_qa=render,
            frozen_values=_frozen(),
        )


def test_no_pooled_candidate_is_explicit_no_release() -> None:
    endpoint = _endpoint()
    endpoint["release_status"] = "NO_V20_RELEASE"
    endpoint["release_candidate"] = None
    report = FINAL.build_final_analysis(
        endpoint=endpoint,
        m22_rows=_m22_rows(),
        paired={"schema": "a2_piper_v20_paired_analysis_v1"},
        holdout=None,
        render_qa=None,
        frozen_values=_frozen(),
    )
    assert report["final_status"] == "NO_RELEASE"
    assert report["fallback"] is None
    assert "no_pooled_release_candidate" in report["failed_gates"]
