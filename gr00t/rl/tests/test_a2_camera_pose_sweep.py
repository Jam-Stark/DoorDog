from pathlib import Path

import pytest
import yaml

from gr00t.rl.scripts.sweep_a2_student_camera_pose import (
    build_eval_command,
    prepare_writable_eval_input,
    nominal_gemini_335l_crop_intrinsics,
    verify_base_v13_a_checkpoint,
)
from gr00t.rl.utils.a2_camera_pose_sweep import (
    STAGE_NAMES,
    derive_center_crop_intrinsics,
    instance_target_ids_by_env,
    rank_camera_candidates,
    validate_pose_candidates,
)


ROOT = Path(__file__).resolve().parents[3]
SWEEP_CONFIG = ROOT / "gr00t/rl/config/camera_pose_sweep/gemini_335l_centerline.yaml"
SWEEP_ENV = ROOT / "gr00t/rl/envs/door/door_open_a2_camera_pose_sweep.py"
SWEEP_ENTRYPOINT = ROOT / "gr00t/rl/scripts/sweep_a2_student_camera_pose.py"
SIMULATOR = ROOT / "gr00t/rl/simulator/isaacsim/isaacsim.py"


def test_gemini_335l_center_crop_intrinsics_are_spec_derived_and_aspect_preserving():
    intrinsics = nominal_gemini_335l_crop_intrinsics()
    output = intrinsics["output"]
    assert output["width"] == 384
    assert output["height"] == 216
    assert output["fx"] == pytest.approx(179.04289653843105)
    assert output["fy"] == pytest.approx(177.90731622152882)
    assert output["cx"] == pytest.approx(192.0)
    assert output["cy"] == pytest.approx(108.0)
    assert intrinsics["effective_fov_deg"]["horizontal"] == pytest.approx(94.0)
    assert intrinsics["effective_fov_deg"]["vertical"] == pytest.approx(62.520330193409286)
    assert intrinsics["spec_derived_not_calibrated"] is True


def test_intrinsics_reject_non_uniform_resize():
    with pytest.raises(ValueError, match="preserve aspect ratio"):
        derive_center_crop_intrinsics(
            native_width=1280,
            native_height=800,
            horizontal_fov_deg=94.0,
            vertical_fov_deg=68.0,
            crop_width=1280,
            crop_height=720,
            output_width=384,
            output_height=200,
        )


def test_centerline_config_has_one_control_and_seven_unbiased_search_candidates():
    config = yaml.safe_load(SWEEP_CONFIG.read_text())
    sweep = config["env"]["config"]["a2_camera_pose_sweep"]
    assert config["env"]["config"]["a2_stage4_release_hinge_threshold"] == 1.2
    assert config["env"]["config"]["a2_stage45_door_frame_contact_scale"] == 0.2
    candidates = validate_pose_candidates(sweep["candidates"])
    assert len(candidates) == 8
    assert [candidate["role"] for candidate in candidates].count("control") == 1
    for candidate in candidates:
        if candidate["role"] == "search":
            assert candidate["position_m"][1] == 0.0
            assert candidate["rpy_deg"][0] == 0.0
            assert candidate["rpy_deg"][2] == 0.0
    cameras = config["simulator"]["config"]["cameras"]
    assert cameras["camera_resolutions"] == [216, 384]
    assert cameras["colorize_instance_id_segmentation"] is False
    assert cameras["camera_types"] == [
        {"rgb": True},
        {"instance_id_segmentation_fast": True},
    ]


def test_raw_instance_mapping_is_split_by_environment_and_target():
    info = {
        "idToLabels": {
            "10": "/World/envs/env_0/door/door_handle/handle_inside",
            "11": "/World/envs/env_0/Robot/arm_body7/visuals/mesh",
            "12": "/World/envs/env_0/Robot/arm_body8/visuals/mesh",
            "13": "/World/envs/env_0/door/door_panel/geom",
            "20": "/World/envs/env_1/door/door_handle/handle_inside",
        }
    }
    targets = instance_target_ids_by_env(
        info,
        num_envs=2,
        target_path_tokens={
            "handle": "/door/door_handle",
            "finger7": "/Robot/arm_body7",
            "finger8": "/Robot/arm_body8",
            "door_panel": "/door/door_panel",
        },
    )
    assert targets["handle"] == [[10], [20]]
    assert targets["finger7"] == [[11], []]
    assert targets["finger8"] == [[12], []]
    assert targets["door_panel"] == [[13], []]


def _candidate_summary(name, handle, trio, panel, centered):
    stages = {}
    for stage_index, stage_name in STAGE_NAMES.items():
        sampled = 10 if stage_index in (1, 2, 3, 4, 6) else 0
        stages[stage_name] = {
            "sampled_frames": sampled,
            "handle_visible_frames": round(sampled * handle),
            "handle_and_both_fingers_visible_frames": round(sampled * trio),
            "door_panel_visible_frames": round(sampled * panel),
            "handle_centered_frames": round(sampled * centered),
        }
    return {"name": name, "stages": stages}


def test_ranking_is_diagnostic_and_prefers_matched_visibility():
    ranking = rank_camera_candidates(
        [
            _candidate_summary("weak", 0.8, 0.5, 1.0, 0.9),
            _candidate_summary("strong", 1.0, 0.9, 1.0, 1.0),
        ]
    )
    assert ranking["recommended_candidate"] == "strong"
    assert "diagnostic-only" in ranking["score_contract"]
    assert ranking["ranking"][0]["score"] > ranking["ranking"][1]["score"]


def test_ranking_rejects_identical_diagnostics_instead_of_using_name_order():
    tied = _candidate_summary("a", 1.0, 1.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="arbitrary recommendation"):
        rank_camera_candidates([tied, {**tied, "name": "b"}])


def test_checkpoint_identity_gate_rejects_non_base_v13_a(tmp_path):
    checkpoint = tmp_path / "model_step_003000.pt"
    checkpoint.write_bytes(b"not-base-v13-A")
    with pytest.raises(RuntimeError, match="not the sealed base_v13_A Teacher"):
        verify_base_v13_a_checkpoint(checkpoint)
    actual_sha256 = verify_base_v13_a_checkpoint(
        checkpoint,
        expected_sha256=(
            "7c252e156936d1f63bf0854c1631d616b6a395717216b0126b4c3ac9c9138497"
        ),
    )
    assert actual_sha256 == "7c252e156936d1f63bf0854c1631d616b6a395717216b0126b4c3ac9c9138497"


def test_eval_command_uses_teacher_eval_and_never_training_entrypoint(tmp_path):
    command = build_eval_command(
        python_path=Path("/isaac/python"),
        checkpoint=Path("/checkpoint.pt"),
        num_envs=16,
        output_dir=tmp_path / "sweep",
    )
    assert command[1] == "gr00t/rl/eval_agent_trl.py"
    assert not any("train_agent" in token for token in command)
    assert "+camera_pose_sweep=gemini_335l_centerline" in command
    assert "+num_envs=16" in command
    assert "+headless=true" in command
    assert "+use_wandb=false" in command
    assert "+multi_gpu=false" in command
    assert "++algo.config.num_mini_batches=1" in command


def test_eval_command_rejects_single_env_onnx_side_effect(tmp_path):
    with pytest.raises(ValueError, match="ONNX export"):
        build_eval_command(
            python_path=Path("/isaac/python"),
            checkpoint=Path("/checkpoint.pt"),
            num_envs=1,
            output_dir=tmp_path / "sweep",
        )


def test_prepare_writable_eval_input_copies_checkpoint_and_config(tmp_path):
    source_dir = tmp_path / "sealed"
    source_dir.mkdir()
    checkpoint = source_dir / "model_step_003000.pt"
    checkpoint.write_bytes(b"checkpoint")
    config_path = source_dir / "config.yaml"
    config_path.write_text("seed: 0\n")
    output_dir = tmp_path / "sweep"

    runtime_checkpoint = prepare_writable_eval_input(
        output_dir=output_dir,
        checkpoint=checkpoint,
    )
    assert runtime_checkpoint.read_bytes() == b"checkpoint"
    assert (runtime_checkpoint.parent / "config.yaml").read_text() == "seed: 0\n"
    assert runtime_checkpoint.parent == output_dir / "_eval_input"


def test_wrapper_prepends_dedicated_worktree_to_child_pythonpath():
    source = SWEEP_ENTRYPOINT.read_text()
    assert 'environment["PYTHONPATH"] = str(repository_root)' in source
    assert 'environment["PYTHONPATH"] += os.pathsep + existing_pythonpath' in source


def test_runtime_source_reuses_one_camera_and_guards_same_physics_step():
    source = SWEEP_ENV.read_text()
    assert "camera_view = camera._view" in source
    assert "camera_view.set_local_poses" in source
    assert "camera_view.set_world_poses" not in source
    assert "simulator.sim.render()" in source
    assert "camera.update(dt=0.0, force_recompute=True)" in source
    assert "physics step counter" in source
    assert "pose readback mismatch" in source
    assert "rendered identical RGB and instance segmentation" in source
    assert "finally:" in source
    assert "camera_view.get_local_poses" in source
    assert "camera_view.get_world_poses" not in source
    assert "XformPrimView(" not in source


def test_simulator_forwards_raw_instance_id_mode_fail_fast():
    source = SIMULATOR.read_text()
    assert 'cameras_cfg.get(\n                "colorize_instance_id_segmentation", True' in source
    assert "if type(colorize_instance_ids) is not bool:" in source
    assert "colorize_instance_id_segmentation=colorize_instance_ids" in source
