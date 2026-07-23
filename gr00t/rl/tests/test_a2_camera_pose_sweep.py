import hashlib
from pathlib import Path

import pytest
import yaml

from gr00t.rl.scripts.sweep_a2_student_camera_pose import (
    TeacherProfile,
    build_eval_command,
    nominal_gemini_335l_crop_intrinsics,
    prepare_writable_eval_input,
    verify_teacher_artifacts,
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
SCHEME_C_CONFIG = ROOT / "gr00t/rl/config/camera_pose_sweep/d435i_portrait_a2_head.yaml"
SWEEP_ENV = ROOT / "gr00t/rl/envs/door/door_open_a2_camera_pose_sweep.py"
SWEEP_ENTRYPOINT = ROOT / "gr00t/rl/scripts/sweep_a2_student_camera_pose.py"
SWEEP_RUNNER = ROOT / "gr00t/rl/scripts/run_a2_camera_pose_eval.py"
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
    assert intrinsics["effective_fov_deg"]["vertical"] == pytest.approx(
        62.520330193409286
    )
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
    assert sweep["ranking_stage_indices"] == [1, 2, 3, 4, 5]
    assert sweep["video"] == {
        "enabled": True,
        "env_id": 1,
        "fps": 10,
        "output_dir": "${eval_output_dir}/camera_pose_videos",
    }
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


def test_scheme_c_config_seals_portrait_d435i_and_provisional_head_geometry():
    config = yaml.safe_load(SCHEME_C_CONFIG.read_text())
    assert config["env"]["_target_"].endswith(".DoorPregraspCameraSchemeC")
    cameras = config["simulator"]["config"]["cameras"]
    assert cameras["camera_parent"] == "trunk"
    assert cameras["camera_prim_suffix"] == "d435i_portrait_camera"
    assert cameras["camera_pos"] == [0.28, 0.0, 0.25]
    assert cameras["camera_resolutions"] == [384, 216]
    assert cameras["camera_rot_wxyz"] == pytest.approx(
        [0.9945218953682733, 0.0, -0.10452846326765347, 0.0]
    )
    assert cameras["camera_horizontal_aperture"] == pytest.approx(
        0.7731910784268148
    )
    assert cameras["camera_vertical_aperture"] == pytest.approx(
        1.3745619172032262
    )

    env_config = config["env"]["config"]
    sweep = env_config["a2_camera_pose_sweep"]
    assert [candidate["name"] for candidate in sweep["candidates"]] == [
        "d435i_portrait_up12",
        "a2_head_context",
    ]
    assert sweep["ranking_stage_indices"] == [1, 2, 3, 4, 5]
    assert sweep["video"]["env_id"] == 1
    assert sweep["video"]["fps"] == 10
    scheme = env_config["a2_camera_scheme_c"]
    assert scheme["view_order"] == ["d435i_portrait_up12", "a2_head_context"]
    assert scheme["d435i_mount"] == {
        "parent": "trunk",
        "physical_housing_orientation": "portrait_90_deg",
        "software_uprighted_optical_frame": True,
        "position_m": [0.28, 0.0, 0.25],
        "effective_optical_rpy_deg": [0.0, -12.0, 0.0],
        "mechanical_clearance_status": "unverified",
        "lateral_symmetry_contract": "centerline_y0_yaw0",
    }
    head = scheme["head_camera"]
    assert head["extrinsic_status"] == "provisional_not_cad_or_calibrated"
    assert [head["height"], head["width"]] == [136, 384]
    assert head["position_m"] == [0.32, 0.0, 0.25]
    assert head["rotation_wxyz"] == pytest.approx(
        [0.9945218953682733, 0.0, -0.10452846326765347, 0.0]
    )
    assert head["rpy_deg"] == [0.0, -12.0, 0.0]
    assert head["nominal_intrinsics"]["sim_fx_fy_cx_cy"] == pytest.approx(
        [85.48390757923893, 85.48390757923893, 192.0, 68.0]
    )
    assert scheme["combined_video"] == {
        "enabled": True,
        "env_id": 1,
        "fps": 10,
        "output_path": (
            "${eval_output_dir}/"
            "scheme_c_d435i_portrait_plus_a2_head_env0001.mp4"
        ),
    }


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
        sampled = 10 if stage_index in (1, 2, 3, 4, 5, 6) else 0
        stages[stage_name] = {
            "sampled_frames": sampled,
            "handle_visible_frames": round(sampled * handle),
            "handle_and_both_fingers_visible_frames": round(sampled * trio),
            "door_panel_visible_frames": round(sampled * panel),
            "handle_centered_frames": round(sampled * centered),
        }
    return {"name": name, "stages": stages}


def test_ranking_is_diagnostic_and_prefers_matched_stage1_to_stage5_visibility():
    ranking = rank_camera_candidates(
        [
            _candidate_summary("weak", 0.8, 0.5, 1.0, 0.9),
            _candidate_summary("strong", 1.0, 0.9, 1.0, 1.0),
        ],
        ranking_stage_indices=[1, 2, 3, 4, 5],
    )
    assert ranking["recommended_candidate"] == "strong"
    assert ranking["ranking_stage_indices"] == [1, 2, 3, 4, 5]
    assert ranking["ranking_stage_label"] == "stage1-2-3-4-5"
    assert "diagnostic-only" in ranking["score_contract"]
    assert ranking["ranking"][0]["score"] > ranking["ranking"][1]["score"]


def test_ranking_requires_a_sample_from_every_selected_stage():
    candidate = _candidate_summary("missing-stage5", 1.0, 1.0, 1.0, 1.0)
    candidate["stages"][STAGE_NAMES[5]]["sampled_frames"] = 0
    with pytest.raises(ValueError, match=r"ranking stages \[5\]"):
        rank_camera_candidates(
            [candidate],
            ranking_stage_indices=[1, 2, 3, 4, 5],
        )


def test_ranking_rejects_identical_diagnostics_instead_of_using_name_order():
    tied = _candidate_summary("a", 1.0, 1.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="arbitrary recommendation"):
        rank_camera_candidates(
            [tied, {**tied, "name": "b"}],
            ranking_stage_indices=[1, 2, 3, 4, 5],
        )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unit_profile(checkpoint: Path, config_path: Path) -> TeacherProfile:
    return TeacherProfile(
        name="unit_teacher",
        checkpoint=checkpoint,
        checkpoint_sha256=_sha256(checkpoint.read_bytes()),
        config_sha256=_sha256(config_path.read_bytes()),
        runtime_repository=checkpoint.parent,
        expected_runtime_commit=None,
    )


def test_teacher_identity_gate_verifies_checkpoint_and_adjacent_config(tmp_path):
    checkpoint = tmp_path / "model_step.pt"
    checkpoint.write_bytes(b"sealed-checkpoint")
    config_path = tmp_path / "config.yaml"
    config_path.write_bytes(b"seed: 0\n")
    profile = _unit_profile(checkpoint, config_path)
    identity = verify_teacher_artifacts(profile=profile, checkpoint=checkpoint)
    assert identity["checkpoint_sha256"] == profile.checkpoint_sha256
    assert identity["config_sha256"] == profile.config_sha256

    wrong_profile = TeacherProfile(
        name="wrong",
        checkpoint=checkpoint,
        checkpoint_sha256="0" * 64,
        config_sha256=profile.config_sha256,
        runtime_repository=tmp_path,
        expected_runtime_commit=None,
    )
    with pytest.raises(RuntimeError, match="not the sealed wrong Teacher"):
        verify_teacher_artifacts(profile=wrong_profile, checkpoint=checkpoint)


def test_eval_command_uses_runtime_overlay_and_never_training_entrypoint(tmp_path):
    command = build_eval_command(
        python_path=Path("/isaac/python"),
        checkpoint=Path("/checkpoint.pt"),
        num_envs=16,
        output_dir=tmp_path / "sweep",
        runtime_repository=Path("/runtime"),
        overlay_repository=Path("/overlay"),
    )
    assert command[1] == "/overlay/gr00t/rl/scripts/run_a2_camera_pose_eval.py"
    assert command[2:6] == [
        "--runtime-repository",
        "/runtime",
        "--overlay-repository",
        "/overlay",
    ]
    assert not any("train_agent" in token for token in command)
    assert "+camera_pose_sweep=gemini_335l_centerline" in command
    assert "+num_envs=16" in command
    assert "+headless=true" in command
    assert "+use_wandb=false" in command
    assert "+multi_gpu=false" in command
    assert "++seed=0" in command
    assert "++algo.config.num_mini_batches=1" in command
    assert "++algo.config.eval.save_videos=false" in command
    assert "hydra.searchpath=[file:///overlay/gr00t/rl/config]" in command


def test_eval_command_selects_scheme_c_without_changing_teacher_or_training(tmp_path):
    command = build_eval_command(
        python_path=Path("/isaac/python"),
        checkpoint=Path("/checkpoint.pt"),
        num_envs=16,
        output_dir=tmp_path / "scheme_c",
        runtime_repository=Path("/runtime"),
        overlay_repository=Path("/overlay"),
        camera_config="d435i_portrait_a2_head",
    )
    assert "+camera_pose_sweep=d435i_portrait_a2_head" in command
    assert not any("train_agent" in token for token in command)
    with pytest.raises(ValueError, match="unsupported camera config"):
        build_eval_command(
            python_path=Path("/isaac/python"),
            checkpoint=Path("/checkpoint.pt"),
            num_envs=16,
            output_dir=tmp_path / "bad",
            runtime_repository=Path("/runtime"),
            overlay_repository=Path("/overlay"),
            camera_config="unreviewed_camera",
        )


def test_eval_command_rejects_single_env_onnx_side_effect(tmp_path):
    with pytest.raises(ValueError, match="ONNX export"):
        build_eval_command(
            python_path=Path("/isaac/python"),
            checkpoint=Path("/checkpoint.pt"),
            num_envs=1,
            output_dir=tmp_path / "sweep",
            runtime_repository=Path("/runtime"),
            overlay_repository=Path("/overlay"),
        )


def test_prepare_writable_eval_input_copies_verified_checkpoint_and_config(tmp_path):
    source_dir = tmp_path / "sealed"
    source_dir.mkdir()
    checkpoint = source_dir / "model_step.pt"
    checkpoint.write_bytes(b"checkpoint")
    config_path = source_dir / "config.yaml"
    config_path.write_text("seed: 0\n")
    profile = _unit_profile(checkpoint, config_path)
    output_dir = tmp_path / "sweep"

    runtime_checkpoint, runtime_config = prepare_writable_eval_input(
        output_dir=output_dir,
        checkpoint=checkpoint,
        profile=profile,
    )
    assert runtime_checkpoint.read_bytes() == b"checkpoint"
    assert runtime_config.read_text() == "seed: 0\n"
    assert runtime_checkpoint.parent == output_dir / "_eval_input"


def test_wrapper_points_child_pythonpath_at_selected_runtime_repository():
    source = SWEEP_ENTRYPOINT.read_text()
    assert (
        'environment["PYTHONPATH"] = str(profile.runtime_repository.resolve())'
        in source
    )
    assert 'environment["PYTHONPATH"] += os.pathsep + existing_pythonpath' in source
    assert "candidate video trajectory does not cover stages 1-5" in source


def test_runtime_overlay_bootstrap_loads_only_camera_modules_from_worktree():
    source = SWEEP_RUNNER.read_text()
    assert "sys.path.insert(0, str(runtime_repository))" in source
    assert "OVERLAY_MODULES" in source
    assert "a2_camera_pose_sweep" in source
    assert "door_open_a2_camera_pose_sweep" in source
    assert "runpy.run_path(str(eval_entrypoint), run_name=\"__main__\")" in source
    assert '"d435i_portrait_a2_head"' in source
    assert "camera pose bootstrap requires exactly one" in source
    assert 'f"{camera_config}.yaml"' in source


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


def test_scheme_c_runtime_uses_two_fixed_sensors_one_render_and_three_videos():
    source = SWEEP_ENV.read_text()
    assert "class DoorPregraspCameraSchemeC" in source
    assert "head_camera = TiledCamera(head_cfg)" in source
    assert "simulator.scene.sensors[sensor_name] = head_camera" in source
    scheme_source = source[source.index("class DoorPregraspCameraSchemeC") :]
    assert scheme_source.count("simulator.sim.render()") == 1
    assert "camera.update(dt=0.0, force_recompute=True)" in scheme_source
    assert "scheme C camera update advanced physics" in scheme_source
    assert "_append_a2_scheme_c_combined_frame" in scheme_source
    assert "left 384x216 pillarboxed portrait D435i" in scheme_source
    assert "right 384x216 letterboxed A2 Head" in scheme_source
    assert "SCHEME_C_COMPLETE" in scheme_source
    assert "provisional_not_cad_or_calibrated" in scheme_source
    assert "production Student observation and model are unchanged" in scheme_source


def test_runtime_source_writes_and_seals_one_video_per_candidate():
    source = SWEEP_ENV.read_text()
    assert "imageio.get_writer" in source
    assert "_append_a2_camera_candidate_video_frame" in source
    assert "_seal_a2_camera_candidate_videos" in source
    assert "_a2_camera_sweep_videos_sealed = False" in source
    assert "_a2_camera_sweep_video_stage_frame_counts" in source
    assert "candidate videos have no sampled frames for stages" in source
    assert '"candidate_videos": candidate_videos' in source
    assert '"recommended_candidate_video": recommended_video' in source


def test_runtime_source_adapts_mainline_tiled_camera_to_raw_instance_ids():
    source = SWEEP_ENV.read_text()
    assert "TiledCameraCfg.__init__" in source
    assert 'kwargs["colorize_instance_id_segmentation"] = False' in source
    assert "TiledCameraCfg.__init__ = original_init" in source


def test_simulator_forwards_raw_instance_id_mode_fail_fast():
    source = SIMULATOR.read_text()
    assert 'cameras_cfg.get(\n                "colorize_instance_id_segmentation", True' in source
    assert "if type(colorize_instance_ids) is not bool:" in source
    assert "colorize_instance_id_segmentation=colorize_instance_ids" in source
