from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scriptsFORhuman/v20/a2_piper_v20_endpoint_report.py"
SPEC = importlib.util.spec_from_file_location("a2_piper_v20_endpoint_report", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ENDPOINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENDPOINT)


def _metrics(passing: bool) -> dict:
    count = 46 if passing else 0
    return {
        "episode_count": 48,
        "goal_count": count,
        "crossing_while_holding_count": count,
        "send_ready_count": count,
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


def _sources(tmp_path: Path, passing_groups: set[str]) -> dict[str, Path]:
    result = {}
    for index in range(1, 8):
        group = f"G{index}"
        path = tmp_path / f"{group}.json"
        path.write_text(
            json.dumps(
                {
                    "schema": ENDPOINT.EVIDENCE_SCHEMA,
                    "rows": [
                        {
                            "candidate_id": "model_step_001000.pt",
                            "checkpoint_path": f"/{group}/model_step_001000.pt",
                            "checkpoint_sha256": str(index) * 64,
                            "evaluation_topology": "pooled48",
                            "strict_status": "STRICT_VALID",
                            "metrics": _metrics(group in passing_groups),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        result[group] = path
    return result


def test_endpoint_selects_simplest_passing_i_cell_and_has_no_fallback(tmp_path: Path) -> None:
    report = ENDPOINT.build_endpoint_report(_sources(tmp_path, {"G1", "G2", "G3"}), _frozen())
    assert report["release_status"] == "RELEASE_CANDIDATE_FROZEN"
    assert report["release_candidate"]["group"] == "G3"
    assert report["fallback"] is None

    report = ENDPOINT.build_endpoint_report(_sources(tmp_path, {"G1", "G2"}), _frozen())
    assert report["release_status"] == "NO_V20_RELEASE"
    assert report["release_candidate"] is None
    assert report["fallback"] is None


def test_endpoint_rejects_missing_handle_slip_metric(tmp_path: Path) -> None:
    sources = _sources(tmp_path, {"G3"})
    payload = json.loads(sources["G3"].read_text(encoding="utf-8"))
    payload["rows"][0]["metrics"].pop("along_handle_slip_p95_m")
    sources["G3"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="strict-valid metrics missing along_handle_slip_p95_m"):
        ENDPOINT.build_endpoint_report(sources, _frozen())
