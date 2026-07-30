"""CPU tests for the one-shot R1 pilot adjudicator and consumption guard."""

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


def _passing_evidence():
    return {
        "exit_code": 0,
        "batches_completed": 750,
        "batches_expected": 750,
        "finite_checkpoints": {"250": True, "500": True, "750": True},
        "optimizer_state_finite": True,
        "schedule_transition_steps": [500],
        "snapshot_audit_ok": True,
        "strict_valid_count": 16,
        "strict_total_count": 16,
        "nonfinite_telemetry_count": 0,
        "malformed_telemetry_count": 0,
        "exact_hash_binding": True,
        "goal_count": 8,
        "crossing_while_holding_count": 8,
        "stage4_occupancy_count": 1,
        "last50_hard_goal_rate": 0.1,
        "max_terminal_reason_share": 0.5,
        "crossing_hinge_p50": 0.82,
        "valid_hold_crossing_at_or_above_090_count": 4,
        "send_ready_count": 4,
        "pre_send_arm_tangent_share_p50": 0.30,
        "hard_send_ready_rate_700_749": 0.10,
        "hard_terminal_rate_700_749": 0.1,
        "hard_terminal_rate_500_549": 0.2,
        "upper_dof_overspeed_count": 0,
        "goal_body_collision_before_crossing_count": 0,
        "arc_position_error_p95_m": 0.05,
        "arc_orientation_error_p95_rad": 0.90,
        "positive_hinge_velocity_p95": 0.45,
        "hinge_acceleration_p95": 1.25,
        "hinge_jerk_p95": 35.0,
        "arm_raw_action_rate_p95": 2.75,
        "arm_raw_action_jerk_p95": 4.50,
    }


def test_pilot_adjudicator_requires_all_gates_and_closes_on_failure():
    module = _module("r1_pilot_adjudicator_test", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_pilot_adjudicator.py")
    result = module.evaluate_pilot(_passing_evidence())
    assert result["status"] == "POLICY LEARNABILITY PASS"
    failed = _passing_evidence()
    failed["goal_count"] = 7
    result = module.evaluate_pilot(failed)
    assert result["status"] == "NO RELEASE"
    assert "goal_minimum" in result["failed_gates"]
    with pytest.raises(module.R1Error):
        module.evaluate_pilot({"exit_code": 0})


def test_pilot_attempt_is_consumed_once_without_retry(tmp_path, monkeypatch):
    module = _module("r1_pilot_launcher_test", "scriptsFORhuman/v20_R1/a2_piper_v20_R1_pilot_launcher.py")
    repo = tmp_path / "repo"
    source = repo / "gr00t/rl/config/ablation/wbmanip" / module.PILOT_CONFIG
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes((ROOT / "gr00t/rl/config/ablation/wbmanip" / module.PILOT_CONFIG).read_bytes())
    checkpoint = repo / module.CHECKPOINT_PATH
    urdf = repo / module.URDF_PATH
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    urdf.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_bytes(b"checkpoint")
    urdf.write_bytes(b"urdf")
    gate_payloads = {
        "preflight": {"plan_id": module.PLAN_ID, "status": "STATIC PASS", "plan_sha256": module.PLAN_SHA256},
        "semantic": {"plan_id": module.PLAN_ID, "status": "RUNTIME SEMANTIC PASS"},
    }
    gate_paths = {
        "preflight": repo / "logs_eval/base_v20_R1/preflight/R1_SCIENTIFIC_MANIFEST.json",
        "semantic": repo / "logs_eval/base_v20_R1/semantic/semantic_admission.json",
    }
    for name, path in gate_paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(__import__("json").dumps(gate_payloads[name]) + chr(10), encoding="utf-8")
    monkeypatch.setattr(module, "git_identity", lambda repo_root: {"commit": "a" * 40, "branch": "A2_Piper", "dirty": False})
    timestamp = "20260729T000000Z"
    artifact_root = repo / module.PILOT_ROOT / timestamp
    module.consume_attempt(
        artifact_root=artifact_root,
        gpu=0,
        command=["pilot"],
        source_config=source,
        repo_root=repo,
        timestamp=timestamp,
    )
    with pytest.raises(module.R1Error):
        module.consume_attempt(
            artifact_root=artifact_root,
            gpu=0,
            command=["pilot"],
            source_config=source,
            repo_root=repo,
            timestamp=timestamp,
        )
    with pytest.raises(module.R1Error):
        module.consume_attempt(
            artifact_root=repo / module.PILOT_ROOT / "gpu7",
            gpu=7,
            command=["pilot"],
            source_config=source,
            repo_root=repo,
            timestamp="20260729T000001Z",
        )
