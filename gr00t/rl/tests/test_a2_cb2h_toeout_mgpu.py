"""CPU/static contract tests for the standalone C-B2H toe-out6 DDP route."""

from __future__ import annotations

import json
from pathlib import Path
import signal
import subprocess
import sys
from types import MethodType, SimpleNamespace

import pytest
import yaml
import torch

from gr00t.rl.scripts import run_a2_cb2h_pro_toeout_mgpu as runner


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_p2_b2h_toeout6_mgpu.yaml"


def test_geometry_contract_is_world_mirrored_and_outward():
    geometry = runner.validate_toeout6_geometry()
    assert geometry["architecture_id"] == "C-B2H-DUALRAW-SHAREDENC-TOEOUT6-V19-P2"
    assert geometry["convention"] == "world"
    assert geometry["left"]["position_m"] == [0.215, 0.065, 0.165]
    assert geometry["right"]["position_m"] == [0.215, -0.065, 0.165]
    assert geometry["outward_products"]["left_y_times_forward_y"] > 0.0
    assert geometry["outward_products"]["right_y_times_forward_y"] > 0.0
    with pytest.raises(ValueError, match="outward|mirrored"):
        runner.validate_toeout6_geometry(
            right_rot=runner.TOEOUT6_LEFT_ROT,
        )


def test_config_has_exact_geometry_topology_and_fresh_init_contract():
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert config["topology_id"] == runner.TOPOLOGY_ID
    assert config["gpu_binding_mode"] == runner.GPU_BINDING_MODE
    assert config["num_envs"] == 64
    assert config["algo"]["trl"]["num_total_batches"] == 8000
    assert config["algo"]["trl"]["per_device_train_batch_size"] == 16
    assert config["algo"]["config"]["num_steps_per_env"] == 8
    assert config["algo"]["config"]["num_mini_batches"] == 4
    assert config["algo"]["config"]["num_learning_epochs"] == 1
    assert config["algo"]["config"]["fresh_ddp_init"]["enabled"] is True
    assert config["algo"]["config"]["p2_common_init"]["enabled"] is False
    assert config["checkpoint"] is None
    assert config["auto_load_latest"] is False
    cameras = config["simulator"]["config"]["cameras"]
    assert cameras["architecture_id"] == runner.ARCHITECTURE_ID
    assert cameras["camera_pos"] == [0.215, 0.065, 0.165]
    assert cameras["camera_rot_wxyz"] == [0.905065723713, 0.022118130854, -0.422039078101, 0.047432484685]
    multiview = cameras["policy_multiview"]
    assert multiview["architecture_id"] == runner.ARCHITECTURE_ID
    assert multiview["right"]["rotation_wxyz"] == [0.905065723713, -0.022118130854, -0.422039078101, -0.047432484685]
    assert multiview["context"]["position_m"] == [0.3381, 0.0336, 0.0525]
    assert multiview["context"]["rotation_wxyz"] == [1.0, 0.0, 0.0, 0.0]
    assert multiview["context"]["resolution"] == [136, 384]
    assert "panorama" not in CONFIG.read_text(encoding="utf-8").lower()


def test_batch_schedule_and_provenance_are_exact():
    batch = runner.validate_batch_contract()
    assert batch["global_envs"] == 256
    assert batch["local_transitions_per_iteration"] == 512
    assert batch["global_transitions_per_iteration"] == 2048
    assert batch["local_transitions_per_minibatch"] == 128
    assert batch["global_transitions_per_minibatch"] == 512
    assert [entry["teacher_count"] for entry in runner.validate_rollout_schedule()] == [256, 192, 128, 64]
    provenance = runner.validate_provenance()
    assert provenance["checkpoint_load"]["checkpoint"] is None
    assert provenance["checkpoint_load"]["auto_load_latest"] is False
    assert provenance["checkpoint"]["sha256"] == "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d"
    assert provenance["runtime_commit"] == "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a"


def test_runner_seals_mode_specific_lifecycle_overrides():
    admission = runner._rank_command("admission", runner.MODE_OUTPUTS["admission"])
    formal = runner._rank_command("formal", runner.MODE_OUTPUTS["formal"])
    assert "algo.trl.num_total_batches=1" in admission
    assert "++algo.config.p2_lifecycle.target_global_step=1" in admission
    assert "++callbacks.model_save.save_frequency=1" in admission
    assert "algo.trl.num_total_batches=8000" in formal
    assert "++algo.config.p2_lifecycle.target_global_step=8000" in formal
    assert "++callbacks.model_save.save_frequency=500" in formal
    assert "++algo.config.mixed_rollout_schedule=[{phase:L0,start_step:0,end_step:1,ratio:1.0}]" in admission


def test_geometry_plan_command_is_exact_single_gpu_c18_evaluator():
    plan = runner.build_plan("geometry")
    output_root = runner.MODE_OUTPUTS["geometry"]
    expected = runner._geometry_command(
        output_root,
        output_root / "_geometry_overlay",
        output_root / "_eval_input" / runner.TEACHER_CHECKPOINT.name,
    )
    assert tuple(plan["command"]) == expected
    assert plan["batch"]["training_performed"] is False
    assert plan["command"][1].endswith("gr00t/rl/scripts/run_a2_camera_pose_eval.py")
    assert "accelerate" not in plan["command"]
    assert "--multi_gpu" not in plan["command"]
    assert "--bootstrap-profile" in plan["command"]
    assert plan["command"][plan["command"].index("--bootstrap-profile") + 1] == runner.TOEOUT_BOOTSTRAP_PROFILE
    assert output_root.name == "geometry_gpu4_g3"
    assert output_root != runner.OUTPUT_ROOT / "geometry_gpu4"
    assert runner.MODE_OUTPUTS["admission"].name == "admission_4x64_gpu4-7"
    assert runner.MODE_OUTPUTS["formal"].name == "formal_4x64_8k_gpu4-7"


def test_generated_geometry_overlay_is_camera_only_and_teacher_merge_preserves_thresholds(
    tmp_path, monkeypatch
):
    from omegaconf import OmegaConf

    output_root = tmp_path / "geometry"
    source_config = runner.REPO_ROOT / "gr00t/rl/config/camera_pose_sweep" / (
        f"{runner.GEOMETRY_CAMERA_CONFIG}.yaml"
    )
    legacy_source_before = source_config.read_bytes()
    test_checkpoint = tmp_path / "teacher.pt"
    test_checkpoint.write_bytes(b"test-only immutable Teacher placeholder")
    provenance = dict(runner.TEACHER_PROVENANCE)
    provenance["checkpoint"] = dict(provenance["checkpoint"])
    provenance["checkpoint"]["sha256"] = runner.sha256_bytes(test_checkpoint.read_bytes())
    monkeypatch.setattr(runner, "TEACHER_CHECKPOINT", test_checkpoint)
    monkeypatch.setattr(runner, "TEACHER_PROVENANCE", provenance)
    overlay_root, config_path, runtime_checkpoint = runner._prepare_geometry_overlay(
        output_root
    )
    assert runtime_checkpoint.is_file()
    assert source_config.read_bytes() == legacy_source_before
    generated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert set(generated["env"]["config"]) == runner.GEOMETRY_ENV_CONFIG_ALLOWLIST
    assert generated["env"]["_target_"].endswith("DoorPregraspCameraSchemeToeOut20Geometry")
    generated_text = config_path.read_text(encoding="utf-8")
    assert "a2_stage4_release_hinge_threshold" not in generated_text
    assert "a2_stage45_door_frame_contact_scale" not in generated_text
    assert "panorama" not in generated_text.lower()

    teacher = OmegaConf.load(str(runner.TEACHER_CONFIG))
    overlay = OmegaConf.load(str(config_path))
    merged = OmegaConf.merge(teacher, overlay)
    assert merged.env.config.a2_stage4_release_hinge_threshold == 1.6
    assert merged.env.config.a2_stage4_to5_door_hinge_threshold == 1.25
    assert merged.env.config.a2_stage45_door_frame_contact_scale == 0.2
    teacher_env_config = OmegaConf.to_container(teacher.env.config, resolve=False)
    merged_env_config = OmegaConf.to_container(merged.env.config, resolve=False)
    assert isinstance(teacher_env_config, dict)
    assert isinstance(merged_env_config, dict)
    for key, value in teacher_env_config.items():
        if key not in runner.GEOMETRY_ENV_CONFIG_ALLOWLIST:
            assert merged_env_config[key] == value

    generated_module = overlay_root / "gr00t/rl/envs/door/door_open_a2_camera_pose_sweep.py"
    compile(generated_module.read_text(encoding="utf-8"), str(generated_module), "exec")
    generated_module_text = generated_module.read_text(encoding="utf-8")
    assert "a2_dual_portrait_panorama" not in generated_module_text
    assert "depth_aware_cylindrical_panorama" not in generated_module_text


def test_geometry_overlay_rejects_unexpected_legacy_task_key(tmp_path):
    source_config = runner.REPO_ROOT / "gr00t/rl/config/camera_pose_sweep" / (
        f"{runner.GEOMETRY_CAMERA_CONFIG}.yaml"
    )
    fixture = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    fixture["env"]["config"]["unexpected_task_semantic_key"] = 7
    fixture_path = tmp_path / "legacy_with_unexpected_task_key.yaml"
    fixture_path.write_text(yaml.safe_dump(fixture, sort_keys=False), encoding="utf-8")
    with pytest.raises(RuntimeError, match="unexpected env.config keys"):
        runner._sanitize_geometry_overlay_config(
            fixture_path.read_text(encoding="utf-8"), fixture_path
        )


def test_geometry_plan_does_not_enter_training_batch_validation(monkeypatch):
    def forbidden_batch_validation(**kwargs):
        raise AssertionError(f"geometry entered training batch validation: {kwargs}")

    monkeypatch.setattr(runner, "validate_batch_contract", forbidden_batch_validation)
    plan = runner.build_plan("geometry")
    assert plan["batch"] == {
        "mode": "geometry",
        "training_performed": False,
        "envs": 16,
        "iterations": 0,
        "save_frequency": None,
    }
    assert plan["rollout_schedule"] == []


def test_admission_schedule_resolves_through_actual_trainer_phase_validator():
    from gr00t.rl.trl.trainer.distill_trainer_a2_base_api import (
        TRLDistillTrainerA2BaseAPI,
        build_cyclic_teacher_mask,
        validate_mixed_rollout_schedule,
    )

    admission = object.__new__(TRLDistillTrainerA2BaseAPI)
    admission.config = {
        "p2_lifecycle": {"enabled": True, "target_global_step": 1},
        "mixed_rollout_schedule": [
            {"phase": "L0", "start_step": 0, "end_step": 1, "ratio": 1.0}
        ],
    }
    phase = admission._resolve_cb2h_rollout_phase(0)
    assert phase == {"phase": "L0", "start_step": 0, "end_step": 1, "ratio": 1.0}
    mask = build_cyclic_teacher_mask(256, phase["ratio"], 0, enforce_teacher_rollout=True)
    assert int(mask.sum().item()) == 256
    validate_mixed_rollout_schedule(admission.config["mixed_rollout_schedule"], target_global_step=1)

    formal = object.__new__(TRLDistillTrainerA2BaseAPI)
    formal.config = {
        "p2_lifecycle": {"enabled": True, "target_global_step": 8000},
        "mixed_rollout_schedule": [
            {"phase": "L0", "start_step": 0, "end_step": 1000, "ratio": 1.0},
            {"phase": "L1", "start_step": 1000, "end_step": 2000, "ratio": 0.75},
            {"phase": "L2", "start_step": 2000, "end_step": 4000, "ratio": 0.5},
            {"phase": "L3", "start_step": 4000, "end_step": 8000, "ratio": 0.25},
        ],
    }
    assert formal._resolve_cb2h_rollout_phase(0)["ratio"] == 1.0
    assert formal._resolve_cb2h_rollout_phase(7999)["ratio"] == 0.25
    with pytest.raises(ValueError, match="target_global_step"):
        validate_mixed_rollout_schedule(formal.config["mixed_rollout_schedule"], target_global_step=1)


def test_rank_hydra_paths_are_unique_and_rank_scoped(tmp_path):
    root = tmp_path / "run"
    expected = runner.rank_hydra_output_dirs(root)
    assert runner.validate_rank_hydra_output_dirs(root, expected) == expected
    with pytest.raises(RuntimeError, match="pairwise unique"):
        runner.validate_rank_hydra_output_dirs(root, [expected[0], expected[0], expected[2], expected[3]])
    with pytest.raises(RuntimeError, match="escaped"):
        runner.validate_rank_hydra_output_dirs(root, [root / ".hydra", expected[1], expected[2], expected[3]])


def test_c18_runtime_validator_rejects_wrong_head_dirty_and_substituted_module(tmp_path, monkeypatch):
    runtime = tmp_path / "c18"
    for relative_path in runner.RUNTIME_MODULES.values():
        path = runtime / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# test source\n", encoding="utf-8")
    entrypoint = runtime / "gr00t/rl/eval_agent_trl.py"
    entrypoint.parent.mkdir(parents=True, exist_ok=True)
    entrypoint.write_text("# test entrypoint\n", encoding="utf-8")

    monkeypatch.setattr(runner, "_git", lambda repository, *args: "wrong-head" if args == ("rev-parse", "HEAD") else "")
    with pytest.raises(RuntimeError, match="commit mismatch"):
        runner.validate_runtime_repository(runtime)

    def clean_head_then_dirty(repository, *args):
        return runner.EXPECTED_RUNTIME_COMMIT if args == ("rev-parse", "HEAD") else " M gr00t/rl/envs/door/door_open_a2_base.py"

    monkeypatch.setattr(runner, "_git", clean_head_then_dirty)
    with pytest.raises(RuntimeError, match="must be clean"):
        runner.validate_runtime_repository(runtime)

    monkeypatch.setattr(runner, "_git", lambda repository, *args: runner.EXPECTED_RUNTIME_COMMIT if args == ("rev-parse", "HEAD") else "")
    original_modules = runner.RUNTIME_MODULES
    monkeypatch.setattr(
        runner,
        "RUNTIME_MODULES",
        {"substituted": "../outside_runtime_module.py"},
    )
    with pytest.raises(FileNotFoundError, match="escaped"):
        runner.validate_runtime_repository(runtime)
    monkeypatch.setattr(runner, "RUNTIME_MODULES", original_modules)


def test_owned_process_group_survivor_is_killed_and_recorded(tmp_path, monkeypatch):
    alive = True
    signals = []

    def fake_killpg(pgid, value):
        nonlocal alive
        signals.append(value)
        if value == signal.SIGKILL:
            alive = False
        elif value == 0 and not alive:
            raise ProcessLookupError

    monkeypatch.setattr(runner.os, "killpg", fake_killpg)
    process = SimpleNamespace(pid=4242, returncode=-signal.SIGTERM, wait=lambda timeout: None)
    runner._terminate_owned_process(process, root=tmp_path, reason="TEST_SURVIVOR")
    record = json.loads((tmp_path / "teardown_record.json").read_text(encoding="utf-8"))
    assert signals == [signal.SIGTERM, 0, signal.SIGKILL, 0]
    assert record["group_alive_after_term"] is True
    assert record["kill_sent"] is True
    assert record["group_alive_after_kill"] is False
    assert record["unresolved"] is False


def test_owned_process_captures_stdout_stderr_and_seals_failure_log(tmp_path):
    child_code = (
        "import sys\n"
        "print('child stdout marker', flush=True)\n"
        "print('child stderr marker', file=sys.stderr, flush=True)\n"
        "raise SystemExit(7)\n"
    )
    with pytest.raises(RuntimeError, match="rc=7"):
        runner._run_owned_process(
            (sys.executable, "-u", "-c", child_code),
            root=tmp_path,
            environment={},
            seal_path=None,
            timeout_s=10,
        )
    log_path = tmp_path / runner.CHILD_LOG_FILENAME
    assert log_path.is_file()
    log_text = log_path.read_text(encoding="utf-8")
    assert "child stdout marker" in log_text
    assert "child stderr marker" in log_text
    record = json.loads((tmp_path / "teardown_record.json").read_text(encoding="utf-8"))
    assert record["status"] == "CHILD_FAILURE"
    assert record["child_log"] == {
        "path": str(log_path),
        "sha256": runner.sha256_file(log_path),
        "size": log_path.stat().st_size,
    }


def test_owned_process_success_seals_log_after_child_exit(tmp_path):
    child_code = (
        "import sys\n"
        "print('natural stdout marker', flush=True)\n"
        "print('natural stderr marker', file=sys.stderr, flush=True)\n"
    )
    seal_path = tmp_path / "metrics_eval.json"
    seal_path.write_text("{}\n", encoding="utf-8")
    assert (
        runner._run_owned_process(
            (sys.executable, "-u", "-c", child_code),
            root=tmp_path,
            environment={},
            seal_path=seal_path,
            timeout_s=10,
        )
        == 0
    )
    log_path = tmp_path / runner.CHILD_LOG_FILENAME
    record = json.loads((tmp_path / "teardown_record.json").read_text(encoding="utf-8"))
    assert record["status"] == "NATURAL"
    assert "natural stdout marker" in log_path.read_text(encoding="utf-8")
    assert "natural stderr marker" in log_path.read_text(encoding="utf-8")
    assert record["child_log"]["sha256"] == runner.sha256_file(log_path)


def test_owned_process_spawn_failure_seals_empty_log(monkeypatch, tmp_path):
    def fail_spawn(*args, **kwargs):
        raise OSError("synthetic spawn failure")

    monkeypatch.setattr(runner.subprocess, "Popen", fail_spawn)
    with pytest.raises(OSError, match="synthetic spawn failure"):
        runner._run_owned_process(
            ("missing-child",),
            root=tmp_path,
            environment={},
            seal_path=None,
            timeout_s=10,
        )
    log_path = tmp_path / runner.CHILD_LOG_FILENAME
    record = json.loads((tmp_path / "teardown_record.json").read_text(encoding="utf-8"))
    assert record["status"] == "SPAWN_FAILURE"
    assert record["pgid"] is None
    assert record["child_log"]["path"] == str(log_path)
    assert record["child_log"]["sha256"] == runner.sha256_file(log_path)


def test_owned_process_duplicate_log_path_fails_before_spawn(monkeypatch, tmp_path):
    log_path = tmp_path / runner.CHILD_LOG_FILENAME
    log_path.write_text("sealed prior evidence\n", encoding="utf-8")
    spawned = False

    def forbidden_spawn(*args, **kwargs):
        nonlocal spawned
        spawned = True
        raise AssertionError("Popen must not run when the exclusive log already exists")

    monkeypatch.setattr(runner.subprocess, "Popen", forbidden_spawn)
    with pytest.raises(FileExistsError, match=runner.CHILD_LOG_FILENAME):
        runner._run_owned_process(
            ("must-not-spawn",),
            root=tmp_path,
            environment={},
            seal_path=None,
            timeout_s=10,
        )
    assert spawned is False
    assert log_path.read_text(encoding="utf-8") == "sealed prior evidence\n"


def _run_rc0_owned_launcher_with_survivor(tmp_path, monkeypatch, *, sealed):
    alive = True
    signals = []
    pid = 5151

    def fake_killpg(pgid, value):
        nonlocal alive
        assert pgid == pid
        signals.append(value)
        if value == signal.SIGKILL:
            alive = False
        elif value == 0 and not alive:
            raise ProcessLookupError

    process = SimpleNamespace(pid=pid, returncode=0, poll=lambda: 0, wait=lambda timeout: None)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(runner.os, "killpg", fake_killpg)
    seal_path = tmp_path / "metrics_eval.json"
    if sealed:
        seal_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="survivors"):
        runner._run_owned_process(
            ("sealed-c18-evaluator",),
            root=tmp_path,
            environment={},
            seal_path=seal_path,
            timeout_s=1,
        )
    record = json.loads((tmp_path / "teardown_record.json").read_text(encoding="utf-8"))
    assert record["status"] == "SURVIVING_PEER"
    assert record["status"] != "NATURAL"
    assert record["unresolved"] is False
    assert record["term_sent"] is True
    assert record["kill_sent"] is True
    assert signals == [0, signal.SIGTERM, 0, signal.SIGKILL, 0]


def test_rc0_sealed_launcher_with_surviving_peer_is_not_natural(tmp_path, monkeypatch):
    _run_rc0_owned_launcher_with_survivor(tmp_path, monkeypatch, sealed=True)


def test_rc0_unsealed_launcher_with_surviving_peer_is_not_natural_unsealed(tmp_path, monkeypatch):
    _run_rc0_owned_launcher_with_survivor(tmp_path, monkeypatch, sealed=False)


def _seed_formal_admission_artifacts(tmp_path, monkeypatch, *, teardown):
    geometry_root = tmp_path / "geometry"
    admission_root = tmp_path / "admission"
    geometry_root.mkdir()
    admission_root.mkdir()
    (geometry_root / "geometry_admission.json").write_text(
        json.dumps({"status": "GEOMETRY_COMPLETE", "diagnostic_only": True}),
        encoding="utf-8",
    )
    checkpoint_path = admission_root / "model_step_000001.pt"
    checkpoint_path.write_bytes(b"admission-step-1")
    rank_entries = []
    for rank in range(4):
        proof_path = admission_root / "ranks" / f"rank{rank}" / "rank_proof.json"
        proof_path.parent.mkdir(parents=True)
        proof_path.write_text(
            json.dumps({"loss_finite": True, "gradient_finite": True}),
            encoding="utf-8",
        )
        rank_entries.append({"path": str(proof_path)})
    aggregate = {
        "status": "ADMISSION_COMPLETE",
        "final_checkpoint": {
            "global_step": 1,
            "path": str(checkpoint_path),
            "sha256": runner.sha256_bytes(checkpoint_path.read_bytes()),
        },
        "ranks": rank_entries,
    }
    (admission_root / "aggregate_proof.json").write_text(json.dumps(aggregate), encoding="utf-8")
    if teardown is not None:
        (admission_root / "teardown_record.json").write_text(json.dumps(teardown), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "MODE_OUTPUTS",
        {"geometry": geometry_root, "admission": admission_root, "formal": tmp_path / "formal"},
    )
    return aggregate


def test_formal_prerequisite_accepts_only_fully_sealed_natural_admission(tmp_path, monkeypatch):
    aggregate = _seed_formal_admission_artifacts(
        tmp_path,
        monkeypatch,
        teardown={"status": "NATURAL", "unresolved": False},
    )
    assert runner._validate_formal_prerequisite() == aggregate


def test_formal_prerequisite_rejects_missing_teardown(tmp_path, monkeypatch):
    _seed_formal_admission_artifacts(tmp_path, monkeypatch, teardown=None)
    with pytest.raises(FileNotFoundError, match="teardown_record"):
        runner._validate_formal_prerequisite()


@pytest.mark.parametrize(
    "status",
    ("POST_SEAL_TIMEOUT", "CHILD_FAILURE", "NATURAL_UNSEALED", "INTERRUPTED", "PROCESS_TIMEOUT", "SURVIVING_PEER"),
)
def test_formal_prerequisite_rejects_every_non_natural_teardown_status(tmp_path, monkeypatch, status):
    _seed_formal_admission_artifacts(
        tmp_path,
        monkeypatch,
        teardown={"status": status, "unresolved": False},
    )
    with pytest.raises(RuntimeError, match="not naturally sealed"):
        runner._validate_formal_prerequisite()


def test_formal_prerequisite_rejects_natural_unresolved_teardown(tmp_path, monkeypatch):
    _seed_formal_admission_artifacts(
        tmp_path,
        monkeypatch,
        teardown={"status": "NATURAL", "unresolved": True},
    )
    with pytest.raises(RuntimeError, match="not naturally sealed"):
        runner._validate_formal_prerequisite()


def test_mgpu_completion_evidence_is_sealed_before_kit_close():
    source = Path(runner.REPO_ROOT / "gr00t/rl/train_agent_trl.py").read_text(encoding="utf-8")
    main_source = source[source.index("@hydra.main") : source.index('if __name__ == "__main__"')]
    seal_index = main_source.index("_seal_a2_mgpu_rank_evidence(")
    close_index = main_source.index("_close_simulation_app(")
    assert seal_index < close_index


def _geometry_frame(step, stage, pixels=16, *, semantics=True):
    views = {
        view: {
            "handle_pixels": pixels,
            "semantic_targets": ["handle", "finger7", "finger8", "door_panel"] if semantics else [],
        }
        for view in (runner.GEOMETRY_LEFT_VIEW, runner.GEOMETRY_RIGHT_VIEW, runner.GEOMETRY_HEAD_VIEW)
    }
    coverage = {
        "control_step": step,
        "stage": stage,
        "union_handle_pixels": pixels,
        "per_view": views,
    }
    return {
        "control_step": step,
        "stage": stage,
        "coverage_control_step": step,
        "coverage": coverage,
    }


def test_geometry_transition_gate_requires_exact_21_frame_union_coverage():
    def window(center, stage):
        return {
            "center_control_step": center,
            "sampled_frames": [_geometry_frame(step, stage) for step in range(center - 10, center + 11)],
        }

    scheme = {
        "transition_windows": {
            "stage1_to_stage2": window(100, 1),
            "stage2_to_stage3": window(200, 2),
            "stage3_to_stage4": window(300, 3),
        }
    }
    result = runner._validate_geometry_transition_windows(scheme)
    assert all(item["sampled_frame_count"] == 21 for item in result.values())

    for mutation, match in (
        (lambda frames: frames[:10] + frames[11:], "every contiguous"),
        (lambda frames: [*frames[:20], _geometry_frame(109, 1)], "duplicate frame"),
        (lambda frames: [*frames[:5], _geometry_frame(95, 1, pixels=15), *frames[6:]], "below 16"),
        (lambda frames: [*frames[:5], _geometry_frame(95, 1, semantics=False), *frames[6:]], "semantic"),
    ):
        broken = json.loads(json.dumps(scheme))
        frames = broken["transition_windows"]["stage1_to_stage2"]["sampled_frames"]
        broken["transition_windows"]["stage1_to_stage2"]["sampled_frames"] = mutation(frames)
        with pytest.raises(RuntimeError, match=match):
            runner._validate_geometry_transition_windows(broken)


def test_topology_rejects_substitution_and_accepts_exact_rank():
    env = {
        "CUDA_VISIBLE_DEVICES": "4,5,6,7",
        "WORLD_SIZE": "4",
        "LOCAL_WORLD_SIZE": "4",
        "RANK": "2",
        "LOCAL_RANK": "2",
        "MASTER_PORT": "29640",
    }
    identity = runner.validate_topology_environment(env)
    assert identity["physical_gpu_index"] == 6
    assert identity["physical_gpu_uuid"] == runner.PHYSICAL_GPU_UUIDS[6]
    env["CUDA_VISIBLE_DEVICES"] = "0,1,2,3"
    with pytest.raises(RuntimeError, match="exactly"):
        runner.validate_topology_environment(env)


def test_geometry_transition_validation_requires_real_sampled_frames():
    def window(center, stage):
        return {
            "center_control_step": center,
            "sampled_frames": [_geometry_frame(step, stage) for step in range(center - 10, center + 11)],
        }

    scheme = {
        "transition_windows": {
            "stage1_to_stage2": window(20, 1),
            "stage2_to_stage3": window(40, 2),
            "stage3_to_stage4": window(60, 3),
        }
    }
    evidence = runner._validate_geometry_transition_windows(scheme)
    assert evidence["stage1_to_stage2"]["sampled_frame_count"] == 21
    bad = dict(scheme)
    bad["transition_windows"] = dict(scheme["transition_windows"])
    bad["transition_windows"]["stage1_to_stage2"] = {
        "center_control_step": 20,
        "sampled_frames": [],
    }
    with pytest.raises(RuntimeError, match="sampled frame"):
        runner._validate_geometry_transition_windows(bad)


def test_dry_run_is_output_free_and_emits_exact_plan(tmp_path):
    output_root = runner.MODE_OUTPUTS["geometry"]
    assert not output_root.exists()
    completed = subprocess.run(
        [sys.executable, str(ROOT / "gr00t/rl/scripts/run_a2_cb2h_pro_toeout_mgpu.py"), "--mode", "dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["dry_run"] is True
    assert plan["architecture_id"] == runner.ARCHITECTURE_ID
    assert plan["topology_id"] == runner.TOPOLOGY_ID
    assert plan["batch"]["global_transitions_per_iteration"] == 2048
    assert plan["output_roots"]["geometry"].endswith("geometry_gpu4_g3")
    assert plan["output_roots"]["formal"].endswith("formal_4x64_8k_gpu4-7")
    assert plan["command"] is None
    assert not output_root.exists()


def test_head_actor_update_distribution_builds_default_sequence_distribution():
    from gr00t.rl.trl.modules.vision_actor_critic_modules_p2_recurrent import (
        DualD435HeadVisionRecurrentActor,
    )

    actor = object.__new__(DualD435HeadVisionRecurrentActor)
    calls = []
    actor.forward = MethodType(lambda self, *args, **kwargs: torch.zeros((2, 3, 12)), actor)
    actor._distribution_from_mean = MethodType(
        lambda self, mean: calls.append(tuple(mean.shape)), actor
    )
    actor.update_distribution({"actor_obs": torch.zeros(2, 3, 1)})
    assert calls == [(2, 3, 12)]
