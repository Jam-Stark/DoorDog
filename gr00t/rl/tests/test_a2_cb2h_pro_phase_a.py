from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from gr00t.rl.scripts import run_a2_cb2h_pro_phase_a as phase_a
from gr00t.rl.scripts import run_a2_student_eval_v19 as eval_v19


def _write_checkpoint(root: Path, step: int, *, finite: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"model_step_{step:06d}.pt"
    tensor = torch.tensor([1.0 if finite else float("nan")])
    torch.save(
        {
            "policy_state_dict": {"policy.weight": tensor},
            "state": {"global_step": step},
        },
        path,
    )
    return path


def _write_required_checkpoints(root: Path) -> None:
    for step in phase_a.REQUIRED_STUDENT_STEPS:
        _write_checkpoint(root, step)
    (root / "config.yaml").write_text("checkpoint_load_mode: full\n", encoding="utf-8")


def _metrics(*, stage: int = 2, reward: float = -1.0) -> dict:
    episodes = []
    for env_id in range(16):
        case = {
            "door_hinge_drive_max_force": 10.0 + env_id,
            "door_handle_drive_max_force": 20.0 + env_id,
            "door_handle_height": 0.8 + env_id / 100.0,
            "door_weight": 100.0 + env_id,
        }
        episodes.append(
            {
                "env_id": env_id,
                "episode_index": 0,
                "goal_reached": stage >= 5,
                "max_stage": stage,
                "terminal_reason": "complete" if stage >= 5 else "timeout",
                "reward": reward + env_id,
                "randomized_case": case,
                "terminal_diagnostic": {
                    "env_id": env_id,
                    **case,
                    "root_yaw": 0.01 * env_id,
                    "root_pos_rel": [0.0, 0.02 * env_id, 0.0],
                    "doorframe_contact_force": 2.0 * env_id,
                },
            }
        )
    return {"episodes": episodes}


def _summary(step: int, mean_stage: float, stage0_count: int, reward: float = -1.0) -> dict:
    return {
        "step": step,
        "mean_max_stage": mean_stage,
        "stage0_count": stage0_count,
        "goal_count": 0,
        "mean_reward": reward,
    }


def test_controller_overrides_and_formal_contracts(tmp_path: Path):
    student = eval_v19.build_hydra_overrides("formal", tmp_path / "student", controller="student")
    teacher = eval_v19.build_hydra_overrides(
        "formal", tmp_path / "teacher", checkpoint=eval_v19.TEACHER_CHECKPOINT, controller="teacher"
    )
    assert "+algo.config.enforce_teacher_rollout=false" in student
    assert "+algo.config.ratio_teacher_rollout=0.0" in student
    assert "+algo.config.actor.view_contract.d435i_forward_mode=sequential" in student
    assert "+algo.config.enforce_teacher_rollout=true" in teacher
    assert "+algo.config.ratio_teacher_rollout=1.0" in teacher
    assert not any("d435i_forward_mode" in item for item in teacher)
    assert eval_v19.controller_contract("student")["pure_student"] is True
    assert eval_v19.controller_contract("teacher")["pure_student"] is False


def test_arbitrary_checkpoint_identity_global_step_load_and_finiteness(tmp_path: Path):
    checkpoint = _write_checkpoint(tmp_path, 7)
    config = checkpoint.with_name("config.yaml")
    config.write_text("checkpoint_load_mode: full\n", encoding="utf-8")
    info = eval_v19.validate_checkpoint_artifacts(
        checkpoint,
        config,
        controller="student",
        expected_global_step=7,
    )
    assert info["global_step"] == 7
    assert info["sha256"] == eval_v19.sha256_file(checkpoint)
    with pytest.raises(ValueError, match="filename/global_step"):
        eval_v19.validate_checkpoint_artifacts(
            checkpoint,
            config,
            controller="student",
            expected_global_step=8,
        )
    bad = _write_checkpoint(tmp_path, 8, finite=False)
    with pytest.raises(RuntimeError, match="non-finite"):
        eval_v19.validate_checkpoint_artifacts(
            bad,
            config,
            controller="student",
            expected_global_step=8,
        )
    broken = tmp_path / "model_step_000009.pt"
    broken.write_bytes(b"not a checkpoint")
    with pytest.raises(RuntimeError, match="failed to load"):
        eval_v19.validate_checkpoint_artifacts(
            broken,
            config,
            controller="student",
            expected_global_step=9,
        )


def test_case_identity_ignores_outcome_drift_but_rejects_case_drift():
    baseline = _metrics(stage=2)
    changed_outcome = copy.deepcopy(baseline)
    changed_outcome["episodes"][0]["goal_reached"] = True
    changed_outcome["episodes"][0]["reward"] = 999.0
    assert phase_a.case_identity_map(baseline) == phase_a.case_identity_map(changed_outcome)
    phase_a.assert_case_maps_equal(
        phase_a.case_identity_map(baseline), phase_a.case_identity_map(changed_outcome)
    )
    changed_case = copy.deepcopy(baseline)
    changed_case["episodes"][0]["randomized_case"]["door_weight"] += 1.0
    with pytest.raises(RuntimeError, match="identity mismatch"):
        phase_a.assert_case_maps_equal(
            phase_a.case_identity_map(baseline), phase_a.case_identity_map(changed_case)
        )


def test_n1_gate_classification_and_aggregate_metrics():
    aggregate = phase_a.aggregate_records(_metrics(stage=5)["episodes"])
    assert aggregate["goal_count"] == 16
    assert aggregate["stage0_count"] == 0
    assert "mean_root_yaw" in aggregate
    assert "mean_root_lateral" in aggregate
    assert phase_a.classify_n1(40, 2) == "PASS"
    assert phase_a.classify_n1(39, 2) == "INCONCLUSIVE"
    assert phase_a.classify_n1(31, 0) == "BLOCKER"
    assert phase_a.classify_n1(48, 7) == "BLOCKER"


def test_n2_paired_ranking_top2_h2_and_early_stop():
    summaries = {
        1000: _summary(1000, 1.0, 10),
        2500: _summary(2500, 1.1, 9),
        5000: _summary(5000, 1.2, 8),
        7500: _summary(7500, 1.25, 7),
        10000: _summary(10000, 1.5, 4),
    }
    ranked = phase_a.rank_n2_checkpoints(summaries)
    assert [item["step"] for item in ranked[:2]] == [10000, 7500]
    h2 = phase_a.h2_verdict(summaries)
    assert h2["verdict"] == "SUPPORT_H2"
    assert phase_a.three_checkpoint_early_stop(list(summaries.values())[:2]) is False
    flat = [
        _summary(1000, 1.0, 5),
        _summary(2500, 1.05, 5),
        _summary(5000, 1.09, 5),
    ]
    assert phase_a.three_checkpoint_early_stop(flat) is True
    deny = dict(summaries)
    deny[5000] = _summary(5000, 1.7, 2)
    assert phase_a.h2_verdict(deny)["verdict"] == "DENY_H2"


def test_missing_required_checkpoint_is_explicit_failure(tmp_path: Path):
    checkpoint_dir = tmp_path / "checkpoints"
    _write_checkpoint(checkpoint_dir, 1000)
    with pytest.raises(phase_a.MissingEvidenceError, match="MISSING_EVIDENCE"):
        phase_a.validate_required_student_checkpoints(checkpoint_dir)


def test_gpu7_command_environment_and_output_roots(tmp_path: Path):
    env = phase_a.build_gpu7_environment(
        {
            "CUDA_VISIBLE_DEVICES": "0",
            "WORLD_SIZE": "8",
            "A2_GPU_UNEXPECTED": "bad",
        }
    )
    assert env["CUDA_VISIBLE_DEVICES"] == "7"
    assert env["A2_EXPECTED_LOGICAL_GPU_INDEX"] == "0"
    assert env["A2_EXPECTED_WORLD_SIZE"] == "1"
    assert "WORLD_SIZE" not in env
    assert "A2_GPU_UNEXPECTED" not in env
    command = phase_a.build_eval_command(
        operation="n2",
        controller="student",
        checkpoint=tmp_path / "model_step_001000.pt",
        expected_global_step=1000,
        checkpoint_sha256="a" * 64,
        config_path=tmp_path / "config.yaml",
        config_sha256="b" * 64,
        experience_path=phase_a.REPO_ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit",
        experience_sha256="c" * 64,
        experience_camera_mode="cameras",
        replicate_id="n2_rep01",
        output_root=tmp_path / "out",
        overlay_repository=phase_a.REPO_ROOT,
        runtime_repository=phase_a.RUNTIME_REPOSITORY,
        python_executable="python",
    )
    assert "--controller" in command and "student" in command
    assert "--expected-global-step" in command and "1000" in command
    assert "--checkpoint-config" in command and "--checkpoint-config-sha256" in command
    assert "--experience-path" in command and "--experience-sha256" in command
    assert "--experience-camera-mode" in command and "cameras" in command
    assert str(phase_a.RUNTIME_REPOSITORY) in command


def test_n3_command_pins_teacher_control_triplet(tmp_path: Path):
    teacher_info = {
        "checkpoint": {
            "path": str(tmp_path / "teacher_step2000.pt"),
            "sha256": "a" * 64,
            "config_path": str(tmp_path / "teacher_config.yaml"),
            "config_sha256": "b" * 64,
        },
        "manifest": {"path": str(tmp_path / "teacher_manifest.json"), "sha256": "c" * 64},
    }
    command = phase_a.build_eval_command(
        operation="n3",
        controller="student",
        checkpoint=tmp_path / "model_step_010000.pt",
        expected_global_step=10000,
        checkpoint_sha256="d" * 64,
        config_path=tmp_path / "config.yaml",
        config_sha256="e" * 64,
        experience_path=phase_a.REPO_ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit",
        experience_sha256="f" * 64,
        experience_camera_mode="cameras",
        replicate_id="n3_rep01",
        output_root=tmp_path / "out",
        teacher_info=teacher_info,
        python_executable="python",
    )
    assert "--mode" in command and command[command.index("--mode") + 1] == "n3"
    assert "--n3-control-controller" in command
    assert "teacher" in command
    assert str(tmp_path / "teacher_manifest.json") in command
    with pytest.raises(ValueError, match="Teacher identity"):
        phase_a.build_eval_command(
            operation="n3",
            controller="student",
            checkpoint=tmp_path / "model_step_010000.pt",
            expected_global_step=10000,
            checkpoint_sha256="d" * 64,
            config_path=tmp_path / "config.yaml",
            config_sha256="e" * 64,
            experience_path=phase_a.REPO_ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit",
            experience_sha256="f" * 64,
            experience_camera_mode="cameras",
            replicate_id="n3_rep01",
            output_root=tmp_path / "out",
            python_executable="python",
        )


def test_n5_command_requires_and_pins_explicit_packed_mode(tmp_path: Path):
    command = phase_a.build_eval_command(
        operation="n5",
        controller="student",
        checkpoint=tmp_path / "model_step_010000.pt",
        expected_global_step=10000,
        checkpoint_sha256="a" * 64,
        config_path=tmp_path / "config.yaml",
        config_sha256="b" * 64,
        experience_path=phase_a.REPO_ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit",
        experience_sha256="c" * 64,
        experience_camera_mode="cameras",
        replicate_id="n5_rep01",
        output_root=tmp_path / "out",
        student_d435i_forward_mode="packed",
        python_executable="python",
    )
    assert "--student-d435i-forward-mode" in command
    assert command[command.index("--student-d435i-forward-mode") + 1] == "packed"
    with pytest.raises(ValueError, match="explicit packed"):
        phase_a.build_eval_command(
            operation="n5",
            controller="student",
            checkpoint=tmp_path / "model_step_010000.pt",
            expected_global_step=10000,
            checkpoint_sha256="a" * 64,
            config_path=tmp_path / "config.yaml",
            config_sha256="b" * 64,
            experience_path=phase_a.REPO_ROOT / "gr00t/rl/apps/phc.isaaclab.python.headless.rendering.kit",
            experience_sha256="c" * 64,
            experience_camera_mode="cameras",
            replicate_id="n5_rep01",
            output_root=tmp_path / "out",
            python_executable="python",
        )


def test_n5_classification_is_open_loop_only():
    baseline = _summary(10000, 1.0, 10)
    baseline["episodes"] = 48
    candidate = _summary(10000, 1.0, 5)
    candidate["episodes"] = 48
    verdict = phase_a.classify_n5(baseline, candidate)
    assert verdict["verdict"] == "SUPPORT_N5_STRONG_STAGE0"
    assert verdict["policy_quality_evidence"] is False


def _synthetic_n5_manifest(tmp_path: Path):
    output_root = tmp_path / "n5_output"
    output_root.mkdir()
    checkpoint = output_root / "model_step_010000.pt"
    config = output_root / "config.yaml"
    checkpoint.write_bytes(b"recalibrated checkpoint")
    config.write_bytes(b"d435i_forward_mode: historical\n")
    checkpoint_info = {
        "path": str(checkpoint.resolve()),
        "sha256": eval_v19.sha256_file(checkpoint),
        "config_path": str(config.resolve()),
        "config_sha256": eval_v19.sha256_file(config),
        "global_step": 10000,
        "controller": "student",
    }
    calibration = {
        "encoder": "d435i_vision_module",
        "batch_norm_type": "SyncBatchNorm",
        "forward_mode": "packed",
        "forward_call_count": phase_a.n5_runner.EXPECTED_PACKED_FORWARD_CALLS,
        "active_frame_count": phase_a.n5_runner.EXPECTED_ACTIVE_FRAMES,
        "packed_sample_count": phase_a.n5_runner.EXPECTED_PACKED_SAMPLES,
        "expected_forward_call_count": phase_a.n5_runner.EXPECTED_PACKED_FORWARD_CALLS,
        "expected_active_frame_count": phase_a.n5_runner.EXPECTED_ACTIVE_FRAMES,
        "expected_packed_sample_count": phase_a.n5_runner.EXPECTED_PACKED_SAMPLES,
        "head_fusion_lstm_mlp_calls": 0,
        "backward_call_count": 0,
        "optimizer_step_count": 0,
    }
    n3_replicates = [
        {
            "replicate_id": replicate_id,
            "h5_path": str(
                phase_a.n5_runner.N3_INPUT_ROOT
                / "n3_teacher_trajectories"
                / replicate_id
                / "teacher_trajectory.h5"
            ),
            "h5_sha256": identity["sha256"],
            "active_frame_count": 10206,
        }
        for replicate_id, identity in phase_a.EXPECTED_N3_H5_IDENTITIES.items()
    ]
    allowed = ["d435i_vision_module.layer.running_mean"]
    manifest = {
        "schema": phase_a.N5_MANIFEST_SCHEMA,
        "operation": "n5",
        "sealed": True,
        "d435i_forward_mode": "packed",
        "gpu_identity": dict(phase_a.n5_runner.EXPECTED_GPU_IDENTITY),
        "checkpoint_source": {
            "path": str(phase_a.n5_runner.CHECKPOINT),
            "sha256": phase_a.n5_runner.CHECKPOINT_SHA256,
            "config_path": str(phase_a.n5_runner.CHECKPOINT_CONFIG),
            "config_sha256": phase_a.n5_runner.CHECKPOINT_CONFIG_SHA256,
            "global_step": 10000,
            "controller": "student",
        },
        "checkpoint_output": {
            **checkpoint_info,
            "allowed_policy_state_keys": allowed,
            "changed_policy_state_keys": allowed,
            "non_bn_policy_state_unchanged": True,
            "top_level_fields_unchanged": True,
        },
        "config": {
            "path": checkpoint_info["config_path"],
            "sha256": checkpoint_info["config_sha256"],
            "d435i_forward_mode": "packed",
        },
        "n3_input": {
            "root": str(phase_a.n5_runner.N3_INPUT_ROOT),
            "phase_manifest_path": str(phase_a.n5_runner.N3_INPUT_ROOT / "phase_a_manifest.json"),
            "phase_manifest_sha256": phase_a.EXPECTED_N3_PHASE_MANIFEST_SHA256,
            "replicates": n3_replicates,
        },
        "n4_baseline": {
            "root": str(phase_a.n5_runner.N4_BASELINE_ROOT),
            "manifest_path": str(phase_a.n5_runner.N4_BASELINE_ROOT / phase_a.n5_runner.N4_MANIFEST_FILENAME),
            "manifest_sha256": phase_a.n5_runner.EXPECTED_N4_MANIFEST_SHA256,
            "metrics_path": str(phase_a.n5_runner.N4_BASELINE_ROOT / phase_a.n5_runner.N4_METRICS_FILENAME),
            "metrics_sha256": phase_a.n5_runner.EXPECTED_N4_METRICS_SHA256,
            "active_frames_path": str(phase_a.n5_runner.N4_BASELINE_ROOT / phase_a.n5_runner.N4_ACTIVE_FRAMES_FILENAME),
            "active_frames_sha256": phase_a.n5_runner.EXPECTED_N4_ACTIVE_FRAMES_SHA256,
            "d435i_forward_mode": "sequential",
        },
        "calibration": calibration,
        "training_performed": False,
        "calibration_performed": True,
        "backward_call_count": 0,
        "optimizer_step_count": 0,
        "outputs": {
            "checkpoint": checkpoint_info,
            "config": {"path": checkpoint_info["config_path"], "sha256": checkpoint_info["config_sha256"]},
        },
    }
    manifest_path = output_root / "n5_provenance_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path, checkpoint_info, manifest


def test_n5_manifest_identity_accepts_exact_and_rejects_tamper(tmp_path: Path):
    manifest_path, checkpoint_info, manifest = _synthetic_n5_manifest(tmp_path)
    manifest_sha = eval_v19.sha256_file(manifest_path)
    accepted = phase_a.validate_n5_manifest_identity(manifest_path, manifest_sha, checkpoint_info)
    assert accepted["sha256"] == manifest_sha
    assert accepted["gpu_identity"] == phase_a.n5_runner.EXPECTED_GPU_IDENTITY
    for field, value in (
        ("schema", "tampered"),
        ("d435i_forward_mode", "sequential"),
    ):
        tampered = copy.deepcopy(manifest)
        tampered[field] = value
        path = tmp_path / f"tampered_{field}.json"
        path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="drifted|packed"):
            phase_a.validate_n5_manifest_identity(path, eval_v19.sha256_file(path), checkpoint_info)
    tampered = copy.deepcopy(manifest)
    tampered["calibration"]["packed_sample_count"] -= 1
    path = tmp_path / "tampered_count.json"
    path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="calibration identity drift"):
        phase_a.validate_n5_manifest_identity(path, eval_v19.sha256_file(path), checkpoint_info)
    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        phase_a.validate_n5_manifest_identity(manifest_path, "0" * 64, checkpoint_info)
    tampered = copy.deepcopy(manifest)
    tampered["gpu_identity"]["physical_gpu_index"] = "6"
    path = tmp_path / "tampered_gpu_identity.json"
    path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="GPU identity drift"):
        phase_a.validate_n5_manifest_identity(path, eval_v19.sha256_file(path), checkpoint_info)


def _synthetic_n2_phase_manifest(tmp_path: Path):
    source_root = phase_a.REPO_ROOT / "logs_eval/cb2h_pro_phase_a_n2_student_sweep_gpu7-20260802"
    source_manifest = json.loads((source_root / "phase_a_manifest.json").read_text(encoding="utf-8"))
    output_root = tmp_path / "n2_phase"
    output_root.mkdir()
    artifact_records = []
    for index in range(1, 4):
        relative = Path("n2_student") / "step_10000" / f"replicate_{index:02d}" / "formal_student_metrics.json"
        source_path = source_root / relative
        destination = output_root / relative
        destination.parent.mkdir(parents=True)
        destination.write_bytes(source_path.read_bytes())
        artifact_records.append(
            {
                "path": relative.as_posix(),
                "size_bytes": destination.stat().st_size,
                "sha256": eval_v19.sha256_file(destination),
            }
        )
    source_manifest["artifacts"] = artifact_records
    manifest_path = output_root / "phase_a_manifest.json"
    manifest_path.write_text(json.dumps(source_manifest, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path, source_manifest, artifact_records


def test_n2_case_mapping_requires_three_hash_valid_confined_artifacts(
    tmp_path: Path, monkeypatch
):
    manifest_path, source_manifest, artifact_records = _synthetic_n2_phase_manifest(tmp_path)
    manifest_sha = eval_v19.sha256_file(manifest_path)
    monkeypatch.setattr(phase_a, "EXPECTED_N2_PHASE_MANIFEST_SHA256", manifest_sha)
    baseline, identity = phase_a.load_n2_step10000_baseline(manifest_path, manifest_sha)
    assert baseline["episodes"] == 48
    assert len(identity["case_artifacts"]) == 3
    assert len(identity["case_identity_map_sha256"]) == 64
    for mutation, expected in (
        (lambda records: records.pop(), "exactly one declared"),
        (lambda records: records.append(copy.deepcopy(records[0])), "exactly one declared"),
        (lambda records: records.__setitem__(0, {**records[0], "sha256": "0" * 64}), "SHA256 mismatch"),
        (lambda records: records.__setitem__(0, {**records[0], "path": "../escape.json"}), "exactly one declared"),
    ):
        tampered = copy.deepcopy(source_manifest)
        records = tampered["artifacts"]
        mutation(records)
        path = tmp_path / "n2_phase" / f"tampered_n2_{len(list((tmp_path / 'n2_phase').iterdir()))}.json"
        path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
        tampered_sha = eval_v19.sha256_file(path)
        monkeypatch.setattr(phase_a, "EXPECTED_N2_PHASE_MANIFEST_SHA256", tampered_sha)
        with pytest.raises(RuntimeError, match=expected):
            phase_a.load_n2_step10000_baseline(path, tampered_sha)


def test_n2_case_mapping_rejects_case_drift_even_when_artifact_hash_is_updated(
    tmp_path: Path, monkeypatch
):
    manifest_path, source_manifest, artifact_records = _synthetic_n2_phase_manifest(tmp_path)
    target = tmp_path / "n2_phase" / artifact_records[1]["path"]
    metrics = json.loads(target.read_text(encoding="utf-8"))
    metrics["episodes"][0]["randomized_case"]["door_weight"] += 0.5
    target.write_text(json.dumps(metrics, sort_keys=True) + "\n", encoding="utf-8")
    tampered = copy.deepcopy(source_manifest)
    tampered["artifacts"][1]["size_bytes"] = target.stat().st_size
    tampered["artifacts"][1]["sha256"] = eval_v19.sha256_file(target)
    path = tmp_path / "n2_phase" / "tampered_case_map.json"
    path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = eval_v19.sha256_file(path)
    monkeypatch.setattr(phase_a, "EXPECTED_N2_PHASE_MANIFEST_SHA256", manifest_sha)
    with pytest.raises(RuntimeError, match="identity mismatch"):
        phase_a.load_n2_step10000_baseline(path, manifest_sha)


def test_n2_baseline_requires_pinned_manifest_hash_and_recomputes_aggregate():
    manifest_path = (
        phase_a.REPO_ROOT
        / "logs_eval/cb2h_pro_phase_a_n2_student_sweep_gpu7-20260802/phase_a_manifest.json"
    )
    with pytest.raises(TypeError):
        phase_a.load_n2_step10000_baseline(manifest_path)
    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        phase_a.load_n2_step10000_baseline(manifest_path, "0" * 64)
    baseline, identity = phase_a.load_n2_step10000_baseline(
        manifest_path, phase_a.EXPECTED_N2_PHASE_MANIFEST_SHA256
    )
    assert baseline == {
        "episodes": 48,
        "goal_count": 1,
        "stage0_count": 35,
        "mean_max_stage": 0.5416666666666666,
        "mean_reward": -184.50176366170248,
        "mean_doorframe_contact_force": 37.004758854707084,
        "doorframe_contact_force_samples": 48,
        "mean_root_yaw": -0.45946762959162396,
        "root_yaw_samples": 48,
        "mean_root_lateral": -0.46393662691116333,
        "root_lateral_samples": 48,
    }
    assert identity["case_identity_map_sha256"] == (
        "5fa0ae8b22ad883dbc9e5bfc0b7f11b3b1c9ecd6b9fc8e24cd957cb50b0af32a"
    )


def test_n2_loader_rejects_combined_summary_drift(tmp_path: Path, monkeypatch):
    _, source_manifest, _ = _synthetic_n2_phase_manifest(tmp_path)
    tampered = copy.deepcopy(source_manifest)
    summary = next(
        item for item in tampered["combined_ranked"] if item["step"] == eval_v19.STUDENT_GLOBAL_STEP
    )
    summary["mean_reward"] += 1.0
    path = tmp_path / "n2_phase" / "tampered_summary.json"
    path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = eval_v19.sha256_file(path)
    monkeypatch.setattr(phase_a, "EXPECTED_N2_PHASE_MANIFEST_SHA256", manifest_sha)
    with pytest.raises(RuntimeError, match="aggregate summary drifted"):
        phase_a.load_n2_step10000_baseline(path, manifest_sha)


@pytest.mark.parametrize("identity_field", ["checkpoint", "experience"])
def test_n2_loader_rejects_checkpoint_or_experience_identity_drift(
    tmp_path: Path, monkeypatch, identity_field: str
):
    _, source_manifest, artifact_records = _synthetic_n2_phase_manifest(tmp_path)
    target = tmp_path / "n2_phase" / artifact_records[0]["path"]
    metrics = json.loads(target.read_text(encoding="utf-8"))
    if identity_field == "checkpoint":
        metrics["checkpoint"]["global_step"] = 9999
        metrics["contract"]["checkpoint_identity"]["global_step"] = 9999
    else:
        metrics["experience"]["sha256"] = "0" * 64
        metrics["contract"]["experience_identity"]["sha256"] = "0" * 64
    target.write_text(json.dumps(metrics, sort_keys=True) + "\n", encoding="utf-8")
    tampered = copy.deepcopy(source_manifest)
    tampered["artifacts"][0]["size_bytes"] = target.stat().st_size
    tampered["artifacts"][0]["sha256"] = eval_v19.sha256_file(target)
    path = tmp_path / "n2_phase" / f"tampered_{identity_field}.json"
    path.write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = eval_v19.sha256_file(path)
    monkeypatch.setattr(phase_a, "EXPECTED_N2_PHASE_MANIFEST_SHA256", manifest_sha)
    expected = "checkpoint" if identity_field == "checkpoint" else "experience identity drifted"
    with pytest.raises(RuntimeError, match=expected):
        phase_a.load_n2_step10000_baseline(path, manifest_sha)


def test_n2_loader_and_execute_reject_mapping_bypass(tmp_path: Path):
    with pytest.raises(TypeError, match="filesystem Path"):
        phase_a.load_n2_step10000_baseline({}, "a" * 64)
    plans = [
        SimpleNamespace(
            operation="n5",
            controller="student",
            student_d435i_forward_mode="packed",
        )
    ] * phase_a.N5_REPLICATE_COUNT
    with pytest.raises(TypeError, match="filesystem Path"):
        phase_a.execute_n5(plans, {}, tmp_path / "phase_n5", "a" * 64)


def test_n5_cli_requires_n2_manifest_sha256(tmp_path: Path):
    common = [
        "--operation",
        "n5",
        "--output-root",
        str(tmp_path / "out"),
        "--n5-checkpoint",
        str(tmp_path / "checkpoint.pt"),
        "--n5-config",
        str(tmp_path / "config.yaml"),
        "--n5-checkpoint-sha256",
        "a" * 64,
        "--n5-config-sha256",
        "b" * 64,
        "--n5-manifest",
        str(tmp_path / "n5.json"),
        "--n5-manifest-sha256",
        "c" * 64,
        "--n2-baseline-manifest",
        str(tmp_path / "n2.json"),
    ]
    with pytest.raises(SystemExit):
        phase_a.parse_args(common)
    args = phase_a.parse_args(common + ["--n2-baseline-manifest-sha256", "d" * 64])
    assert args.n2_baseline_manifest_sha256 == "d" * 64


def test_n5_candidate_case_map_must_match_explicit_n2_reference(tmp_path: Path, monkeypatch):
    manifest_path, _, _ = _synthetic_n2_phase_manifest(tmp_path)
    manifest_sha = eval_v19.sha256_file(manifest_path)
    monkeypatch.setattr(phase_a, "EXPECTED_N2_PHASE_MANIFEST_SHA256", manifest_sha)
    reference_metrics = _metrics(stage=2)
    plans = [
        SimpleNamespace(
            operation="n5",
            controller="student",
            student_d435i_forward_mode="packed",
            replicate_id="n5_rep01",
            output_root=tmp_path / "n5" / "replicate_01",
            n5_manifest_path=tmp_path / "n5_manifest.json",
            n5_manifest_sha256="a" * 64,
        )
    ] * phase_a.N5_REPLICATE_COUNT
    mismatched = copy.deepcopy(reference_metrics)
    mismatched["episodes"][0]["randomized_case"]["door_weight"] += 1.0
    monkeypatch.setattr(phase_a, "_execute_plan", lambda _plan: ({}, mismatched))
    with pytest.raises(RuntimeError, match="identity mismatch"):
        phase_a.execute_n5(plans, manifest_path, tmp_path / "phase_n5", manifest_sha)


def _fake_n3_plan_inputs(tmp_path: Path, monkeypatch):
    student_checkpoint = _write_checkpoint(tmp_path, 10000)
    student_config = student_checkpoint.with_name("config.yaml")
    student_config.write_text("teacher_actor_path: teacher/model_step_002000.pt\n", encoding="utf-8")
    teacher_checkpoint = tmp_path / "teacher" / "model_step_002000.pt"
    teacher_checkpoint.parent.mkdir()
    teacher_checkpoint.write_bytes(b"teacher")
    teacher_config = teacher_checkpoint.with_name("config.yaml")
    teacher_config.write_text("trainer: {}\n", encoding="utf-8")
    teacher_manifest = tmp_path / "teacher_manifest.json"
    teacher_manifest.write_text("{}\n", encoding="utf-8")
    student_info = {
        "path": str(student_checkpoint),
        "sha256": "d" * 64,
        "config_path": str(student_config),
        "config_sha256": phase_a.eval_v19.sha256_file(student_config),
        "global_step": 10000,
        "controller": "student",
    }
    teacher_info = {
        "checkpoint": {
            "path": str(teacher_checkpoint),
            "sha256": "a" * 64,
            "config_path": str(teacher_config),
            "config_sha256": "b" * 64,
            "global_step": 2000,
            "controller": "teacher",
        },
        "manifest": {"path": str(teacher_manifest), "sha256": "c" * 64},
        "runtime_commit": phase_a.eval_v19.EXPECTED_RUNTIME_COMMIT,
    }
    monkeypatch.setattr(phase_a, "validate_runtime_and_overlay_paths", lambda *args, **kwargs: {})
    monkeypatch.setattr(phase_a.eval_v19, "validate_checkpoint_artifacts", lambda *args, **kwargs: student_info)
    monkeypatch.setattr(phase_a.eval_v19, "validate_teacher_identity", lambda *args, **kwargs: teacher_info)
    return student_info, teacher_info


def test_n3_plan_has_exact_three_sequential_replicates(tmp_path: Path, monkeypatch):
    _fake_n3_plan_inputs(tmp_path, monkeypatch)
    plans = phase_a.build_n3_plan(
        tmp_path / "phase_n3",
        overlay_repository=phase_a.REPO_ROOT,
        runtime_repository=phase_a.RUNTIME_REPOSITORY,
        python_executable="python",
    )
    assert len(plans) == phase_a.N3_REPLICATE_COUNT == 3
    assert [plan.replicate_id for plan in plans] == ["n3_rep01", "n3_rep02", "n3_rep03"]
    assert len({plan.output_root for plan in plans}) == 3
    assert all(plan.operation == "n3" and plan.capture_controller == "teacher" for plan in plans)
    assert all(plan.command[plan.command.index("--mode") + 1] == "n3" for plan in plans)


def test_n3_dry_run_does_not_claim_output_root(tmp_path: Path, monkeypatch):
    _fake_n3_plan_inputs(tmp_path, monkeypatch)
    output_root = tmp_path / "phase_n3"
    result = phase_a.main(
        [
            "--operation",
            "n3",
            "--output-root",
            str(output_root),
            "--overlay-repository",
            str(phase_a.REPO_ROOT),
            "--runtime-repository",
            str(phase_a.RUNTIME_REPOSITORY),
            "--dry-run",
        ]
    )
    assert result == 0
    assert not output_root.exists()


def test_execute_n3_seals_three_mocked_replicates_and_case_map(tmp_path: Path, monkeypatch):
    output_root = tmp_path / "phase_n3"
    shared_case_table = [
        {
            "env_id": env_id,
            "case_id": f"{env_id:064d}",
            "randomized_case": {
                key: float(env_id)
                for key in eval_v19.RANDOMIZED_CASE_KEYS
            },
        }
        for env_id in range(16)
    ]
    shared_provenance = {
        "passive_student": {"controller": "student", "global_step": 10000},
        "teacher": {"checkpoint": {"controller": "teacher", "global_step": 2000}},
        "experience": {"controller": "student", "camera_mode": "cameras"},
        "runtime": {"commit": eval_v19.EXPECTED_RUNTIME_COMMIT},
        "case_table": shared_case_table,
        "control_identity": {
            "controller": "teacher",
            "high_level_action_dim": 12,
            "high_level_action_source": "Teacher12D",
            "teacher_rollout_enforced": True,
            "teacher_rollout_ratio": 1.0,
            "policy_quality_evidence": False,
        },
    }
    plans = [
        SimpleNamespace(
            operation="n3",
            replicate_id=f"n3_rep{index:02d}",
            output_root=output_root / "n3_teacher_trajectories" / f"replicate_{index:02d}",
        )
        for index in range(1, 4)
    ]

    def fake_execute(plan):
        manifest = {
            "schema": eval_v19.N3_MANIFEST_SCHEMA,
            "controller": "teacher",
            "replicate_id": plan.replicate_id,
            **shared_provenance,
            "dataset": {"episode_count": 16, "row_count": 16},
        }
        return manifest, _metrics(stage=2)

    monkeypatch.setattr(phase_a, "_execute_plan", fake_execute)
    result = phase_a.execute_n3(plans, output_root)
    assert result["episode_count"] == 48
    assert result["replicate_count"] == 3
    assert result["case_identity_mapping_equal"] is True
    assert len(result["replicates"]) == 3
    assert (output_root / "phase_a_manifest.json").is_file()


def test_n2_dry_run_has_no_side_effects(tmp_path: Path, monkeypatch):
    checkpoint_dir = tmp_path / "checkpoints"
    _write_required_checkpoints(checkpoint_dir)
    output_root = tmp_path / "phase_a_output"
    result = phase_a.main(
        [
            "--operation",
            "n2",
            "--output-root",
            str(output_root),
            "--student-checkpoint-dir",
            str(checkpoint_dir),
            "--overlay-repository",
            str(phase_a.REPO_ROOT),
            "--runtime-repository",
            str(phase_a.RUNTIME_REPOSITORY),
            "--dry-run",
        ]
    )
    assert result == 0
    assert not output_root.exists()


def test_phase_output_root_refuses_stale_empty_or_nonempty_root(tmp_path: Path):
    checkpoint_dir = tmp_path / "checkpoints"
    _write_required_checkpoints(checkpoint_dir)
    output_root = tmp_path / "phase_a_output"
    output_root.mkdir()
    with pytest.raises(FileExistsError, match="must be absent"):
        phase_a.build_n2_plan(
            output_root,
            checkpoint_dir,
            overlay_repository=phase_a.REPO_ROOT,
            runtime_repository=phase_a.RUNTIME_REPOSITORY,
        )
    (output_root / "stale.txt").write_text("stale\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="must be absent"):
        phase_a.build_n2_plan(
            output_root,
            checkpoint_dir,
            overlay_repository=phase_a.REPO_ROOT,
            runtime_repository=phase_a.RUNTIME_REPOSITORY,
        )


def test_planned_adjacent_config_toc_tou_is_rejected(tmp_path: Path):
    checkpoint_dir = tmp_path / "checkpoints"
    _write_required_checkpoints(checkpoint_dir)
    output_root = tmp_path / "phase_a_output"
    plans, _ = phase_a.build_n2_plan(
        output_root,
        checkpoint_dir,
        overlay_repository=phase_a.REPO_ROOT,
        runtime_repository=phase_a.RUNTIME_REPOSITORY,
    )
    plans[0].config_path.write_text("mutated: true\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="config SHA256 drifted"):
        phase_a.validate_planned_run_inputs(plans[0])
    assert not output_root.exists()


def test_planned_experience_identity_toc_tou_is_rejected_without_kit_mutation(tmp_path: Path):
    checkpoint_dir = tmp_path / "checkpoints"
    _write_required_checkpoints(checkpoint_dir)
    plans, _ = phase_a.build_n2_plan(
        tmp_path / "phase_a_output",
        checkpoint_dir,
        overlay_repository=phase_a.REPO_ROOT,
        runtime_repository=phase_a.RUNTIME_REPOSITORY,
    )
    stale = replace(plans[0], experience_sha256="0" * 64)
    with pytest.raises(RuntimeError, match="experience identity mismatch"):
        phase_a.validate_planned_run_inputs(stale)


def test_phase_artifact_validator_rejects_experience_identity_mismatch(tmp_path: Path):
    checkpoint_dir = tmp_path / "checkpoints"
    _write_required_checkpoints(checkpoint_dir)
    plans, _ = phase_a.build_n2_plan(
        tmp_path / "phase_a_output",
        checkpoint_dir,
        overlay_repository=phase_a.REPO_ROOT,
        runtime_repository=phase_a.RUNTIME_REPOSITORY,
    )
    plan = plans[0]
    checkpoint_identity = {
        "path": str(plan.checkpoint),
        "sha256": plan.checkpoint_sha256,
        "config_path": str(plan.config_path),
        "config_sha256": plan.config_sha256,
        "global_step": plan.expected_global_step,
        "controller": plan.controller,
    }
    experience_identity = {
        "controller": plan.controller,
        "camera_mode": plan.experience_camera_mode,
        "path": str(plan.experience_path),
        "sha256": plan.experience_sha256,
    }
    selection = {
        "checkpoint": checkpoint_identity,
        "experience": {**experience_identity, "sha256": "1" * 64},
    }
    metrics = {"checkpoint": checkpoint_identity, "experience": experience_identity}
    with pytest.raises(RuntimeError, match="experience identity drift"):
        phase_a.validate_plan_artifact_identity(plan, selection, metrics)


def test_teacher_config_target_and_wrapped_eval_seal_teacher_filename(tmp_path: Path):
    assert eval_v19.resolve_trainer_target(eval_v19.TEACHER_CONFIG) == eval_v19.TEACHER_TRAINER_TARGET
    formal_metrics = _metrics(stage=5)
    runtime_metrics = {
        "episode_rewards": [record["reward"] for record in formal_metrics["episodes"]],
        "episode_goal_reached": [record["goal_reached"] for record in formal_metrics["episodes"]],
        "episode_max_stage_reached": [record["max_stage"] for record in formal_metrics["episodes"]],
        "episode_terminal_reasons": [record["terminal_reason"] for record in formal_metrics["episodes"]],
        "episode_terminal_diagnostics": [record["terminal_diagnostic"] for record in formal_metrics["episodes"]],
    }
    checkpoint_info = {
        "path": "teacher/model_step_002000.pt",
        "sha256": "a" * 64,
        "config_path": "teacher/config.yaml",
        "config_sha256": "b" * 64,
        "global_step": 2000,
        "controller": "teacher",
    }
    teacher_info = {
        "checkpoint": checkpoint_info,
        "manifest": {"path": "teacher_manifest.json", "sha256": "c" * 64},
        "runtime_commit": eval_v19.EXPECTED_RUNTIME_COMMIT,
        "runtime_label": "USER_APPROVED_C18_RECONSTRUCTION",
    }
    trainer = SimpleNamespace(
        config={
            "enforce_teacher_rollout": True,
            "ratio_teacher_rollout": 1.0,
            "use_a2_base": True,
            "eval": {"eval_num_envs_episodes": True, "num_eval_episodes": 16},
        },
        env=SimpleNamespace(num_envs=16),
    )
    output_root = tmp_path / "teacher_formal"
    wrapped = eval_v19._make_formal_eval(
        lambda _self: runtime_metrics,
        output_root,
        checkpoint_info,
        controller="teacher",
        teacher_info=teacher_info,
        case_seed=0,
        replicate_id="n1_rep01",
    )
    wrapped(trainer)
    teacher_path = output_root / "teacher_selection.json"
    assert teacher_path.is_file()
    assert not (output_root / "student_selection.json").exists()
    loaded, _ = eval_v19.load_sealed_selection(teacher_path)
    assert loaded["controller"] == "teacher"
    assert loaded["experience"] == eval_v19.resolve_experience_source(
        eval_v19.REPO_ROOT, "teacher"
    )


def test_n2_required_set_cannot_be_ranked_with_a_missing_step():
    incomplete = {
        step: _summary(step, 1.0, 1)
        for step in phase_a.REQUIRED_STUDENT_STEPS
        if step != 7500
    }
    with pytest.raises(phase_a.MissingEvidenceError, match="all five"):
        phase_a.rank_n2_checkpoints(incomplete)
