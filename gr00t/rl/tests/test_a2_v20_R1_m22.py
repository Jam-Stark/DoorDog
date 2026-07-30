"""CPU tests for exact M22 checkpoint queueing and mechanical gates."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _passing_metrics():
    return {
        "goal_count": 16,
        "crossing_while_holding_count": 16,
        "upper_dof_overspeed_count": 0,
        "pre_crossing_bilateral_rate": 1.0,
        "pre_crossing_coasting_rate": 0.0,
        "pre_crossing_over_force_rate": 0.0,
        "goal_with_pre_send_crossing_count": 0,
        "send_ready_count": 16,
        "hinge_at_first_crossing_p50": 0.90,
        "hinge_at_first_crossing_p10": 0.85,
        "pre_send_forward_displacement_p95": 0.20,
        "pre_send_lateral_displacement_p95": 0.15,
        "pre_send_planar_displacement_p95": 0.25,
        "pre_send_yaw_change_p95": 0.30,
        "arm_tangent_share_p50": 0.60,
        "arm_tangent_share_p10": 0.45,
        "arc_position_error_p95_m": 0.03,
        "arc_orientation_error_p95_rad": 0.25,
        "along_handle_slip_p95_m": 0.03,
        "a_positive_income_ratio_p95": 0.10,
        "positive_hinge_velocity_p95": 0.40,
        "hinge_acceleration_p95": 1.00,
        "hinge_jerk_p95": 28.0,
        "arm_action_rate_p95": 2.20,
        "arm_action_jerk_p95": 3.60,
        "median_task_time_s": 15.0,
    }


def test_m22_queue_contains_exact_ten_checkpoints_and_rejects_gpu7(tmp_path):
    queue = _module("r1_m22_queue_test", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_m22_queue.py")
    run = tmp_path / "G1"
    run.mkdir()
    for step in queue.STEPS:
        (run / f"model_step_{step:06d}.pt").write_bytes(f"step={step}".encode())
    (run / "last.pt").write_bytes(b"alias")
    manifest = queue.build_manifest(
        run,
        group="G1",
        run_id="formal-G1-001",
        config_sha256="d" * 64,
    )
    assert manifest["steps"] == list(range(250, 2501, 250))
    assert len(manifest["candidates"]) == 10
    assert manifest["last_pt_present_but_excluded"] is True
    with pytest.raises(queue.R1Error):
        queue.build_eval_command(run / "model_step_000250.pt", tmp_path / "eval", gpu=7)


def test_m22_adjudicator_requires_all_frozen_gates(tmp_path):
    adjudicator = _module("r1_m22_adjudicator_test", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_m22_adjudicator.py")
    passing = adjudicator.evaluate_gates(_passing_metrics())
    assert passing["status"] == "STRICT_VALID"
    failed_metrics = _passing_metrics()
    failed_metrics["upper_dof_overspeed_count"] = 1
    assert adjudicator.evaluate_gates(failed_metrics)["status"] == "STRICT_INVALID"
    config_sha = "d" * 64
    candidates = [
        {
            "candidate_id": f"G1:step{step}",
            "step": step,
            "path": f"logs_rl/a2_piper_full_stage_a2_base/base_v20_R1/G1/model_step_{step:06d}.pt",
            "sha256": f"{step:064x}"[-64:],
            "group": "G1",
            "run_id": "formal-G1-001",
            "config_sha256": config_sha,
        }
        for step in adjudicator.STEPS
    ]
    rows = []
    for candidate in candidates:
        rows.append(
            {
                "strict_status": "STRICT_VALID",
                "candidate": candidate,
                "metrics": _passing_metrics(),
                "binding": {
                    "checkpoint_sha256": candidate["sha256"],
                    "config_sha256": config_sha,
                    "group": "G1",
                    "run_id": candidate["run_id"],
                },
                "output": {
                    "group": "G1",
                    "step": candidate["step"],
                    "path": "logs_eval/base_v20_R1/m22/G1/step" + str(candidate["step"]),
                },
                "eval_command": {"command": ["eval"], "exit_code": 0},
            }
        )
    report = adjudicator.adjudicate(
        {"plan_id": adjudicator.PLAN_ID, "group": "G1", "steps": list(adjudicator.STEPS), "candidates": candidates},
        {"rows": rows},
        group="G1",
    )
    assert report["selection_status"] == "POLICY PASS"
    assert report["selected_checkpoint"]["candidate"]["step"] == 250
