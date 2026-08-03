from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load(name: str):
    path = ROOT / "scriptsFORhuman/v20" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


QUEUE = _load("a2_piper_v20_m22_queue")
EVIDENCE = _load("a2_piper_v20_m22_evidence")
ADJ = _load("a2_piper_v20_m22_adjudicator")


def _pass_metrics(episodes: int, minimum: int) -> dict:
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
        "pre_crossing_bilateral_rate": 0.995,
        "pre_crossing_coasting_rate": 0.0,
        "pre_crossing_over_force_rate": 0.0,
        "hinge_at_first_crossing_p10": 0.96,
        "hinge_at_first_crossing_p50": 1.02,
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
        "relief_limit_m": 0.10,
        "arm_share_baseline": 0.50,
        "orientation_tolerance_rad": 0.20,
        "smoothness_baseline": {
            "hinge_acceleration_p95": 1.0,
            "hinge_jerk_p95": 1.0,
            "arm_action_rate_p95": 1.0,
            "arm_action_jerk_p95": 1.0,
            "median_task_time_s": 10.0,
        },
    }


def test_queue_discovers_only_exact_ten_numeric_checkpoints(tmp_path: Path) -> None:
    run = tmp_path / "base_v20_G1"
    run.mkdir()
    for step in range(250, 2501, 250):
        (run / f"model_step_{step:06d}.pt").write_bytes(str(step).encode())
    (run / "last.pt").write_bytes(b"mutable")
    (run / "model_step_002750.pt").write_bytes(b"outside")

    manifest = QUEUE.build_manifest(run, group="G1")
    assert [row["step"] for row in manifest["candidates"]] == list(range(250, 2501, 250))
    assert manifest["last_pt_present_but_excluded"] is True

    (run / "model_step_001000.pt").unlink()
    with pytest.raises(QUEUE.M22QueueError, match="exactly numeric steps"):
        QUEUE.build_manifest(run, group="G1")


def test_queue_maps_physical_gpu_to_isolated_logical_cuda0(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model_step_000250.pt"
    checkpoint.write_bytes(b"checkpoint")
    command = QUEUE.build_eval_command(checkpoint, tmp_path / "eval", gpu="6")
    assert command["env"] == {
        "CUDA_VISIBLE_DEVICES": "6",
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
    }
    with pytest.raises(QUEUE.M22QueueError, match="GPU7 is reserved"):
        QUEUE.build_eval_command(checkpoint, tmp_path / "forbidden", gpu="7")


def _typed_row(env_id: int, checkpoint: Path, digest: str) -> dict:
    na = {"status": "N/A", "reason": "no release", "denominator": 0, "value": None}
    topology = {"name": "canonical16", "episode_count": 16}
    return {
        "env_id": env_id,
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": digest,
        "config_hash": "cfg",
        "seed": 0,
        "topology": topology,
        "goal_reached": True,
        "terminal_reason": "complete",
        "groups": {
            "send": {
                "send_ready": True,
                "first_send_ready_step": 100,
                "pre_send_root_crossing": False,
                "first_pre_send_crossing_step": na,
                "hinge_at_first_root_crossing": 1.02,
                "root_x_at_first_crossing": 0.04,
                "root_displacement_se2": [0.05, 0.0, 0.0],
            },
            "crossing": {
                "valid": True,
                "crossing_while_holding": True,
                "hinge_at_crossing": 1.02,
                "root_x_at_crossing": 0.04,
            },
            "release": {
                "valid": False,
                "hinge_at_release": na,
                "root_x_at_release": na,
                "post_release_body_contact": na,
                "post_release_body_force_max": na,
            },
            "carry": {
                "valid_hold": True,
                "arm_tangent_share": 0.70,
                "handle_arc_position_error_m": 0.02,
                "handle_arc_orientation_error_rad": 0.10,
                "along_handle_slip_m": 0.01,
                "orthogonal_arc_residual_m": 0.01,
                "arc_tracking_quality": 0.80,
            },
            "smoothness": {
                "hinge_acceleration_p95": 1.0,
                "hinge_jerk_p95": 1.0,
                "arm_action_rate_p95": 1.0,
                "arm_action_jerk_p95": 1.0,
            },
        },
        "episode_metrics": {
            "pre_crossing_bilateral": 0.995,
            "pre_crossing_coasting": 0.0,
            "pre_crossing_over_force": 0.0,
            "held_hinge": 1.50,
            "opening_slip_m": 0.02,
            "positive_hinge_velocity_p95": 0.30,
            "task_time_s": 10.0,
        },
        "reward_units": {"total": "episode-sum"},
        "trace_topology": {
            "schema": "a2_piper_v20_trace_topology_v2",
            "mode": "stage_window",
            "first_episode_identity": True,
            "ordered_unique_contiguous": True,
            "terminal_consistent": True,
            "episode_length_buf_equals_step_index_plus_one": True,
            "captured_span_matches_trace_count": True,
        },
    }


def test_typed_evidence_preserves_invalid_and_aggregates(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model_step_000250.pt"
    checkpoint.write_bytes(b"checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "eval_exit_code.txt").write_text("0", encoding="utf-8")
    records = [_typed_row(env_id, checkpoint, digest) for env_id in range(16)]
    (artifact / "a2_v20_strict_telemetry.json").write_text(
        json.dumps(
            {
                "schema": "a2_piper_v20_strict_telemetry_v1",
                "config_hash": "cfg",
                "topology": {"name": "canonical16", "episode_count": 16},
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema": QUEUE.SCHEMA,
        "candidates": [
            {"candidate_id": checkpoint.name, "step": 250, "path": str(checkpoint), "sha256": digest}
        ]
        * 10,
    }
    queue = {
        "schema": QUEUE.QUEUE_SCHEMA,
        "rows": [{"candidate": manifest["candidates"][0], "artifact": str(artifact)}] * 10,
    }
    with pytest.raises(EVIDENCE.V20EvidenceError, match="exact ten candidate"):
        EVIDENCE.build_evidence(manifest, queue)

    loaded = EVIDENCE.load_typed_records(
        artifact,
        expected_count=16,
        checkpoint_path=str(checkpoint),
        checkpoint_sha256=digest,
        expected_seed=0,
        expected_topology_name="canonical16",
    )
    metrics = EVIDENCE.aggregate_records(loaded)
    assert metrics["goal_count"] == 16
    assert metrics["arm_tangent_share_p50"] == pytest.approx(0.70)
    assert metrics["along_handle_slip_p95_m"] == pytest.approx(0.01)
    assert metrics["orthogonal_arc_residual_p95_m"] == pytest.approx(0.01)
    records[0]["groups"]["send"]["hinge_at_first_root_crossing"] = None
    (artifact / "a2_v20_strict_telemetry.json").write_text(
        json.dumps(
            {
                "schema": "a2_piper_v20_strict_telemetry_v1",
                "config_hash": "cfg",
                "topology": {"name": "canonical16", "episode_count": 16},
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(EVIDENCE.V20EvidenceError, match="typed scalar"):
        EVIDENCE.load_typed_records(
            artifact,
            expected_count=16,
            checkpoint_path=str(checkpoint),
            checkpoint_sha256=digest,
            expected_seed=0,
            expected_topology_name="canonical16",
        )


def test_typed_evidence_rejects_missing_or_false_trace_topology_contract(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model_step_000250.pt"
    checkpoint.write_bytes(b"checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    for field, value in (("schema", None), ("captured_span_matches_trace_count", False)):
        records = [_typed_row(env_id, checkpoint, digest) for env_id in range(16)]
        if value is None:
            for record in records:
                record["trace_topology"].pop(field)
        else:
            for record in records:
                record["trace_topology"][field] = value
        (artifact / "a2_v20_strict_telemetry.json").write_text(
            json.dumps(
                {
                    "schema": "a2_piper_v20_strict_telemetry_v1",
                    "config_hash": "cfg",
                    "topology": {"name": "canonical16", "episode_count": 16},
                    "records": records,
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(EVIDENCE.V20EvidenceError, match="trace topology is invalid"):
            EVIDENCE.load_typed_records(
                artifact,
                expected_count=16,
                checkpoint_path=str(checkpoint),
                checkpoint_sha256=digest,
                expected_seed=0,
                expected_topology_name="canonical16",
            )


def test_gate_order_fails_missing_send_and_passes_complete_candidate() -> None:
    metrics = _pass_metrics(16, 15)
    result = ADJ.evaluate_gates(metrics, topology="canonical16", **{
        "theta_send": _frozen()["theta_send"],
        "relief_limit_m": _frozen()["relief_limit_m"],
        "arm_share_baseline": _frozen()["arm_share_baseline"],
        "orientation_tolerance_rad": _frozen()["orientation_tolerance_rad"],
        "smoothness_baseline": _frozen()["smoothness_baseline"],
    })
    assert result["status"] == "PASS"
    metrics["send_ready_count"] = 14
    result = ADJ.evaluate_gates(metrics, topology="canonical16", **{
        "theta_send": _frozen()["theta_send"],
        "relief_limit_m": _frozen()["relief_limit_m"],
        "arm_share_baseline": _frozen()["arm_share_baseline"],
        "orientation_tolerance_rad": _frozen()["orientation_tolerance_rad"],
        "smoothness_baseline": _frozen()["smoothness_baseline"],
    })
    assert result["status"] == "FAIL"
    assert "send_before_cross" in result["failed_gates"]


def test_non_promotable_selection_prioritizes_common_safety_category():
    metrics_common_fail = _pass_metrics(16, 15)
    metrics_common_fail["post_release_body_force_max_p95_n"] = 80.0
    metrics_smooth_fail = _pass_metrics(16, 15)
    metrics_smooth_fail["hinge_acceleration_p95"] = 2.0
    metrics_smooth_fail["hinge_jerk_p95"] = 2.0
    manifest = {
        "schema": ADJ.MANIFEST_SCHEMA,
        "candidates": [
            {"candidate_id": "candidate-a", "step": 250, "path": "/tmp/a.pt", "sha256": "a" * 64},
            {"candidate_id": "candidate-b", "step": 500, "path": "/tmp/b.pt", "sha256": "b" * 64},
        ],
    }
    evidence = {
        "schema": ADJ.EVIDENCE_SCHEMA,
        "rows": [
            {"candidate_id": "candidate-a", "checkpoint_path": "/tmp/a.pt", "checkpoint_sha256": "a" * 64, "strict_status": "STRICT_VALID", "metrics": metrics_common_fail},
            {"candidate_id": "candidate-b", "checkpoint_path": "/tmp/b.pt", "checkpoint_sha256": "b" * 64, "strict_status": "STRICT_VALID", "metrics": metrics_smooth_fail},
        ],
    }
    result = ADJ.adjudicate(
        manifest,
        evidence,
        group="G1",
        topology="canonical16",
        frozen_values=_frozen(),
    )
    assert result["selection_status"] == "NO_PROMOTABLE_CHECKPOINT"
    assert result["selected_checkpoint"]["candidate_id"] == "candidate-b"
    selected = next(row for row in result["rows"] if row["candidate"]["candidate_id"] == "candidate-b")
    assert "hinge_acceleration_p95" in selected["failed_gates"]
    assert "hinge_jerk_p95" in selected["failed_gates"]


def _non_promotable_rows() -> tuple[dict, dict]:
    first = _pass_metrics(16, 15)
    second = _pass_metrics(16, 15)
    first["hinge_acceleration_p95"] = 2.0
    second["hinge_acceleration_p95"] = 2.0
    return first, second


def test_non_promotable_selection_uses_task_time_after_category_counts():
    first, second = _non_promotable_rows()
    first.update({"goal_count": 16, "send_ready_count": 16, "arm_tangent_share_p50": 0.90, "median_task_time_s": 20.0})
    second.update({"goal_count": 15, "send_ready_count": 15, "arm_tangent_share_p50": 0.70, "median_task_time_s": 15.0})
    manifest = {
        "schema": ADJ.MANIFEST_SCHEMA,
        "candidates": [
            {"candidate_id": "candidate-a", "step": 250, "path": "/tmp/a.pt", "sha256": "a" * 64},
            {"candidate_id": "candidate-b", "step": 500, "path": "/tmp/b.pt", "sha256": "b" * 64},
        ],
    }
    evidence = {
        "schema": ADJ.EVIDENCE_SCHEMA,
        "rows": [
            {"candidate_id": "candidate-a", "checkpoint_path": "/tmp/a.pt", "checkpoint_sha256": "a" * 64, "strict_status": "STRICT_VALID", "metrics": first},
            {"candidate_id": "candidate-b", "checkpoint_path": "/tmp/b.pt", "checkpoint_sha256": "b" * 64, "strict_status": "STRICT_VALID", "metrics": second},
        ],
    }
    result = ADJ.adjudicate(manifest, evidence, group="G1", topology="canonical16", frozen_values=_frozen())
    assert result["selected_checkpoint"]["candidate_id"] == "candidate-b"


def test_non_promotable_selection_uses_earlier_step_after_equal_time():
    first, second = _non_promotable_rows()
    first.update({"goal_count": 15, "send_ready_count": 15, "arm_tangent_share_p50": 0.70, "median_task_time_s": 10.0})
    second.update({"goal_count": 16, "send_ready_count": 16, "arm_tangent_share_p50": 0.90, "median_task_time_s": 10.0})
    manifest = {
        "schema": ADJ.MANIFEST_SCHEMA,
        "candidates": [
            {"candidate_id": "candidate-a", "step": 250, "path": "/tmp/a.pt", "sha256": "a" * 64},
            {"candidate_id": "candidate-b", "step": 500, "path": "/tmp/b.pt", "sha256": "b" * 64},
        ],
    }
    evidence = {
        "schema": ADJ.EVIDENCE_SCHEMA,
        "rows": [
            {"candidate_id": "candidate-a", "checkpoint_path": "/tmp/a.pt", "checkpoint_sha256": "a" * 64, "strict_status": "STRICT_VALID", "metrics": first},
            {"candidate_id": "candidate-b", "checkpoint_path": "/tmp/b.pt", "checkpoint_sha256": "b" * 64, "strict_status": "STRICT_VALID", "metrics": second},
        ],
    }
    result = ADJ.adjudicate(manifest, evidence, group="G1", topology="canonical16", frozen_values=_frozen())
    assert result["selected_checkpoint"]["candidate_id"] == "candidate-a"
