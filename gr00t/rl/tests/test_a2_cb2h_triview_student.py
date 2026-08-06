"""CPU/static contracts for the C-B2H tri-view v19 Student route."""

from __future__ import annotations

import ast
from hashlib import sha256
import importlib.util
from pathlib import Path
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest
import torch
import yaml
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

from gr00t.rl.scripts.run_a2_student_distillation_v19 import (
    EXPECTED_CUDA_DEVICE_ORDER,
    EXPECTED_GPU_INDEX,
    EXPECTED_GPU_UUID,
    EXPECTED_GPU_BINDING_MODE,
    EXPECTED_LOGICAL_GPU_INDEX,
    EXPECTED_NUM_ENVS,
    EXPECTED_RUNTIME_COMMIT,
    EXPECTED_TEACHER_CHECKPOINT,
    EXPECTED_TOTAL_BATCHES,
    WANDB_ORIGINAL_COMMIT,
    V19_RUNTIME_SCENARIO_MODULE,
    V19_RUNTIME_SCENARIO_RELATIVE_PATH,
    _exact_hydra_override,
    install_v19_runtime_scenario_file_pin,
    prepare_overlay_import,
    validate_overlay_repository,
    validate_gpu7_environment,
)
from gr00t.rl.utils.a2_policy_camera import (
    compose_channel_stacked_dual_rgb,
    normalize_head_context_rgb,
)
from gr00t.rl.utils.helpers import pre_process_config
from gr00t.rl.train_agent_trl import process_output_dim_in_config


ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "gr00t/rl/config/exp/wbmanip/door_open_a2_base_v19_cb2h_dualraw_dagger-lstm.yaml"
SAVED_G2_CONFIG = Path(
    "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/"
    "a2_piper_full_stage_a2_base/base_v19/"
    "base_v19_G2_norm_control-20260727_012027/config.yaml"
)
OBS = ROOT / "gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger_triview.yaml"
ACTOR = ROOT / "gr00t/rl/trl/modules/vision_actor_critic_modules_triview_recurrent.py"
SIMULATOR = ROOT / "gr00t/rl/simulator/isaacsim/isaacsim.py"
TRAINER = ROOT / "gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py"
RUNNER = ROOT / "gr00t/rl/scripts/run_a2_student_distillation_v19.py"
EXTERNAL_EDITABLE_REPOSITORY = Path("/home/baoquanc/workspace/DoorDog-A2_Piper")


def _yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _run_overlay_import_probe(overlay: Path, mode: str) -> subprocess.CompletedProcess[str]:
    probe = textwrap.dedent(
        """
        import importlib
        import runpy
        import sys
        from pathlib import Path

        runner, requested_overlay, external_repository, probe_mode = sys.argv[1:]
        sys.path.insert(0, external_repository)
        if probe_mode == "legacy":
            import gr00t
            print(f"LEGACY_ROOT={Path(gr00t.__file__).resolve()}", flush=True)
            raise SystemExit(0)
        if probe_mode == "preloaded":
            import gr00t
            print(f"PRELOADED_ROOT={Path(gr00t.__file__).resolve()}", flush=True)
        namespace = runpy.run_path(runner, run_name="a2_overlay_probe")
        namespace["prepare_overlay_import"](Path(requested_overlay))
        package = importlib.import_module("gr00t")
        validator = importlib.import_module(
            "gr00t.rl.scripts.validate_a2_teacher_checkpoint"
        )
        print(f"ROOT={Path(package.__file__).resolve()}", flush=True)
        print(f"VALIDATOR={Path(validator.__file__).resolve()}", flush=True)
        """
    )
    return subprocess.run(
        [
            sys.executable,
            "-c",
            probe,
            str(RUNNER),
            str(overlay),
            str(EXTERNAL_EDITABLE_REPOSITORY),
            mode,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_channel_stacked_helpers_preserve_view_order_and_fail_on_constant_frames():
    left = torch.zeros((1, 384, 216, 3), dtype=torch.uint8)
    right = torch.zeros_like(left)
    left[..., 0] = 255
    right[..., 1] = 255
    dual = compose_channel_stacked_dual_rgb(
        left,
        right,
        resolution=[384, 216],
        image_mean=[0.0, 0.0, 0.0],
        image_std=[1.0, 1.0, 1.0],
    )
    assert tuple(dual.shape) == (1, 384, 216, 6)
    assert torch.allclose(dual[..., 0], torch.ones_like(dual[..., 0]))
    assert torch.allclose(dual[..., 3], torch.zeros_like(dual[..., 3]))
    assert torch.allclose(dual[..., 4], torch.ones_like(dual[..., 4]))
    head = torch.zeros((1, 136, 384, 3), dtype=torch.uint8)
    head[..., 2] = 127
    normalized_head = normalize_head_context_rgb(
        head,
        resolution=[136, 384],
        image_mean=[0.0, 0.0, 0.0],
        image_std=[1.0, 1.0, 1.0],
    )
    assert tuple(normalized_head.shape) == (1, 136, 384, 3)
    with pytest.raises(ValueError, match="constant"):
        compose_channel_stacked_dual_rgb(
            torch.zeros_like(left),
            right,
            resolution=[384, 216],
            image_mean=[0.0, 0.0, 0.0],
            image_std=[1.0, 1.0, 1.0],
        )


def test_v19_config_binds_exact_tri_view_geometry_and_training_dimensions():
    exp = _yaml(EXP)
    obs = _yaml(OBS)["obs"]
    cameras = exp["simulator"]["config"]["cameras"]
    multiview = cameras["policy_multiview"]
    assert exp["num_envs"] == EXPECTED_NUM_ENVS
    assert exp["algo"]["trl"]["num_total_batches"] == EXPECTED_TOTAL_BATCHES
    assert cameras["architecture_id"] == "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19"
    assert cameras["camera_pos"] == [0.215, 0.095, 0.165]
    assert cameras["camera_rot_wxyz"] == [
        0.852868532,
        -0.086824089,
        -0.492403877,
        -0.150383733,
    ]
    assert cameras["camera_resolutions"] == [384, 216]
    assert cameras["camera_update_period"] == pytest.approx(1.0 / 30.0)
    assert cameras["camera_types"] == [{"rgb": True}]
    assert multiview["layout"] == "channel_stacked_raw_rgb"
    assert multiview["output_shape"] == [384, 216, 6]
    assert multiview["view_order"] == ["left", "right"]
    assert multiview["right"]["position_m"] == [0.215, -0.095, 0.165]
    assert multiview["right"]["rotation_wxyz"] == [
        0.852868532,
        0.086824089,
        -0.492403877,
        0.150383733,
    ]
    assert multiview["right"]["update_period"] == pytest.approx(1.0 / 30.0)
    assert multiview["context"]["position_m"] == [0.3381, 0.0336, 0.0525]
    assert multiview["context"]["rotation_wxyz"] == [1.0, 0.0, 0.0, 0.0]
    assert multiview["context"]["resolution"] == [136, 384]
    assert multiview["context"]["update_period"] == pytest.approx(1.0 / 15.0)
    assert exp["algo"]["config"]["actor"]["view_contract"]["d435i_forward_mode"] == "sequential"
    assert exp["domain_rand"]["image_augmentation"]["enabled"] is False
    assert obs["obs_dims"][8]["rgb_image"] == 497664
    assert obs["obs_dims"][9]["context_rgb_image"] == 156672
    assert obs["obs_dims"][10]["camera_meta"] == 6
    assert "panorama" not in EXP.read_text(encoding="utf-8").lower()


def test_v19_hydra_composition_exposes_tri_view_observation_dimensions():
    config_dir = (ROOT / "gr00t/rl/config").resolve()
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        composed = compose(
            config_name="base",
            overrides=["+exp=wbmanip/door_open_a2_base_v19_cb2h_dualraw_dagger-lstm"],
        )
    pre_process_config(composed)
    process_output_dim_in_config(composed)
    assert composed.num_envs == EXPECTED_NUM_ENVS
    assert composed.robot.algo_obs_dim_dict["actor_obs"] == 81
    assert composed.robot.algo_obs_dim_dict["vision_obs"] == 384 * 216 * 6
    assert composed.robot.algo_obs_dim_dict["context_vision_obs"] == 136 * 384 * 3
    assert composed.robot.algo_obs_dim_dict["camera_meta"] == 6
    assert composed.algo.config.teacher_actor.input_key == "teacher_obs"
    assert composed.algo.config.teacher_actor.backbone.module_config_dict.input_dim == [
        "teacher_obs"
    ]
    assert composed.algo.config.teacher_actor.backbone.module_config_dict.output_dim == [12]
    assert composed.algo.config.critic.backbone.module_config_dict.input_dim == ["critic_obs"]
    assert composed.algo.config.critic.backbone.module_config_dict.output_dim == [1]
    assert composed.algo.config.network_load_dict.teacher_actor.path == composed.teacher_actor_path
    assert composed.algo.config.teacher_artifact.config_path == composed.teacher_config_path
    assert composed.algo.config.teacher_artifact.manifest_path == composed.teacher_manifest_path


def test_v19_hydra_resolves_complete_c18_g2_contract_and_student_exceptions():
    config_dir = (ROOT / "gr00t/rl/config").resolve()
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        composed = compose(
            config_name="base",
            overrides=["+exp=wbmanip/door_open_a2_base_v19_cb2h_dualraw_dagger-lstm"],
        )

    env_config = OmegaConf.to_container(composed.env.config, resolve=True)
    expected_env = {
        "a2_m39_gripper_material_enabled": True,
        "a2_door_weight_range": [80.0, 160.0],
        "a2_corridor_enabled": True,
        "a2_corridor_door_wide_hinge_norm": 1.5,
        "a2_arm_dof_overspeed_soft_margin_enabled": True,
        "a2_arm_dof_overspeed_soft_margin_width": 0.5,
        "a2_door_body_contact_penalty_mode": "event_v17",
        "a2_stage5_hold_income_continuity_enabled": True,
        "a2_door_body_contact_event_force_threshold": 5.0,
        "a2_door_body_contact_event_peak_force_norm": 200.0,
        "a2_door_body_contact_event_component_cap": 2.0,
        "a2_stage2_contact_force_threshold": 1.0,
        "a2_stage2_squeeze_force_min": 2.0,
        "a2_stage2_squeeze_force_max": 30.0,
        "a2_stage2_over_force_threshold": 55.0,
        "a2_grasp_gate_mode": "control_streak",
        "a2_grasp_streak_control_steps": 5,
        "a2_stage3_to4_door_hinge_threshold": 0.25,
        "a2_stage3_to4_requires_grasp_streak": True,
        "a2_stage3_to4_streak_highwater": False,
        "a2_stage3_base_unlocked": True,
        "a2_stage3_unlatch_handle_position_norm": 0.6,
        "a2_stage3_unlatch_near_closed_hinge_threshold": 0.1,
        "a2_stage3_stage4_hold_and_drive_velocity_norm": 0.1,
        "a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor": 0.4,
        "a2_stage3_stage4_hold_and_drive_velocity_threshold": 0.05,
        "a2_stage3_stage4_coasting_velocity_threshold": 0.1,
        "a2_stage3_handle_hard_limit_position": 0.785398,
        "a2_stage3_handle_hard_limit_tolerance": 0.005,
        "a2_stage4_release_hinge_threshold": 1.60,
        "a2_stage4_to5_door_hinge_threshold": 1.25,
        "a2_stage45_door_frame_contact_scale": 0.2,
        "a2_stage35_door_panel_contact_scale": 0.0,
        "a2_stage0_staging_x_min": 0.50,
        "a2_stage0_staging_x_max": 0.80,
        "a2_stage0_staging_y_tol": 0.15,
    }
    for key, expected in expected_env.items():
        assert env_config[key] == expected, key

    saved_g2 = _yaml(SAVED_G2_CONFIG)
    actual_sections = {
        "env.config": env_config,
        "rewards.reward_scales": OmegaConf.to_container(
            composed.rewards.reward_scales, resolve=True
        ),
        "robot": OmegaConf.to_container(composed.robot, resolve=True),
        "simulator.config.sim.physx": OmegaConf.to_container(
            composed.simulator.config.sim.physx, resolve=True
        ),
    }
    reference_sections = {
        "env.config": saved_g2["env"]["config"],
        "rewards.reward_scales": saved_g2["rewards"]["reward_scales"],
        "robot": saved_g2["robot"],
        "simulator.config.sim.physx": saved_g2["simulator"]["config"]["sim"]["physx"],
    }
    core_paths = [
        ("env.config", key)
        for key in (*expected_env, "reset_from_dataset.enabled")
    ]
    core_paths.extend(
        ("rewards.reward_scales", key)
        for key in sorted(saved_g2["rewards"]["reward_scales"])
    )
    core_paths.extend(
        ("robot", key)
        for key in (
            "dof_effort_limit_list",
            "control.stiffness.arm_j7",
            "control.stiffness.arm_j8",
            "control.damping.arm_j7",
            "control.damping.arm_j8",
        )
    )
    core_paths.append(("simulator.config.sim.physx", "num_velocity_iterations"))
    assert len(core_paths) == 104

    def _lookup(section, key):
        value = section
        for component in key.split("."):
            value = value[component]
        return value

    differences = [
        (f"{section}.{key}", _lookup(actual_sections[section], key), _lookup(reference_sections[section], key))
        for section, key in core_paths
        if _lookup(actual_sections[section], key) != _lookup(reference_sections[section], key)
    ]
    assert differences == []

    rewards = OmegaConf.to_container(composed.rewards, resolve=True)
    assert rewards["reward_penalty_curriculum"] is False
    assert rewards["reward_initial_penalty_scale"] == 1.0
    assert rewards["reward_min_penalty_scale"] == 1.0
    assert rewards["reward_max_penalty_scale"] == 1.0
    assert rewards["reward_penalty_degree"] == 0.0
    expected_reward_scales = {
        "push_door_handle": 0.0,
        "push_door_hinge": 6.0,
        "push_door_force": 0.0,
        "a2_stage3_unlatch_hold": 3.0,
        "a2_stage3_stage4_hold_and_drive": 8.0,
        "a2_corridor_door_wide": 4.0,
        "a2_corridor_clean_passage": 1.0,
        "a2_stage3_stage4_keep_close_command": 0.5,
        "penalty_a2_stage3_stage4_open_command": -1.0,
        "a2_stage3_stage4_both_contact": 0.5,
        "a2_stage3_stage4_opposite_squeeze": 0.5,
        "a2_stage3_stage4_squeeze_force_window": 0.5,
        "a2_stage3_stage4_contact_stability": 0.5,
        "penalty_a2_stage3_stage4_over_force": -1.0,
        "penalty_a2_door_body_contact": -3.0,
        "penalty_a2_posture_command_l1": -0.3,
    }
    for key, expected in expected_reward_scales.items():
        assert rewards["reward_scales"][key] == expected, key

    robot = OmegaConf.to_container(composed.robot, resolve=True)
    assert robot["dof_effort_limit_list"] == [
        120.0, 120.0, 180.0,
        120.0, 120.0, 180.0,
        120.0, 120.0, 180.0,
        120.0, 120.0, 180.0,
        100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 45.0, 45.0,
    ]
    assert robot["control"]["stiffness"]["arm_j7"] == 1300.0
    assert robot["control"]["stiffness"]["arm_j8"] == 1300.0
    assert robot["control"]["damping"]["arm_j7"] == 32.0
    assert robot["control"]["damping"]["arm_j8"] == 32.0

    assert composed.simulator.config.sim.physx.num_position_iterations == 4
    assert composed.simulator.config.sim.physx.num_velocity_iterations == 2
    assert composed.simulator.config.cameras.enable_cameras is True
    assert composed.enable_cameras is True
    assert composed.simulator.config.render_results is False

    assert composed.num_envs == 64
    assert composed.seed == 0
    assert composed.algo.trl.num_total_batches == 10000
    assert composed.callbacks.model_save.save_frequency == 500
    assert composed.algo.config.num_steps_per_env == 8
    assert composed.algo.config.init_at_random_ep_len is False
    assert composed.domain_rand.image_augmentation.enabled is False
    assert composed.teacher_actor_path == "REQUIRED_A2_V19_TEACHER_CHECKPOINT.pt"
    assert composed.teacher_config_path == "REQUIRED_A2_V19_TEACHER_CONFIG.yaml"
    assert composed.teacher_manifest_path == "REQUIRED_A2_V19_TEACHER_MANIFEST.json"
    exp_text = EXP.read_text(encoding="utf-8")
    assert "base_v18_main-20260724_063738" not in exp_text
    assert "checkpoint_load_mode:" not in exp_text


def _current_m39_harness():
    tree = ast.parse(SIMULATOR.read_text(encoding="utf-8"))
    isaac_sim_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "IsaacSim"
    )
    wanted = {
        "_m39_material_summary",
        "_m39_asset_material_slices",
        "_capture_m39_material_evidence",
    }
    methods = [
        node for node in isaac_sim_class.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    assert {node.name for node in methods} == wanted
    harness = ast.ClassDef(
        name="M39Harness", bases=[], keywords=[], body=methods, decorator_list=[]
    )
    module = ast.fix_missing_locations(ast.Module(body=[harness], type_ignores=[]))
    namespace = {"sha256": sha256, "torch": torch}
    exec(compile(module, str(SIMULATOR), "exec"), namespace)
    return namespace["M39Harness"]


def test_c18_m39_material_evidence_coexists_with_cb2h_simulator_contract():
    source = SIMULATOR.read_text(encoding="utf-8")
    assert 'A2_M39_GRIPPER_BODY_NAMES = ("arm_body7", "arm_body8")' in source
    assert "self.events_cfg.m39_gripper_material = EventTerm(" in source
    assert "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19" in source
    assert source.count(
        "self._m39_material_runtime_metadata = self._capture_m39_material_evidence("
    ) == 1

    harness = _current_m39_harness()
    probe = harness()
    probe.A2_M39_GRIPPER_BODY_NAMES = ("arm_body7", "arm_body8")
    probe.A2_M39_GRIPPER_MATERIAL_SCHEMA = "a2_m39_gripper_material_v1"
    probe.A2_M39_HANDLE_BODY_NAME = "door_handle"
    probe.A2_M39_EXPECTED_POST_MATERIAL = (1.1, 0.9, 0.0)

    robot_paths = (
        "/World/envs/env_0/Robot/arm_body7",
        "/World/envs/env_0/Robot/arm_body8",
        "/World/envs/env_0/Robot/chassis",
    )
    robot_counts = dict(zip(robot_paths, (2, 3, 1)))

    def robot_asset(materials):
        class Root:
            link_paths = [list(robot_paths)]

            def get_material_properties(self):
                return materials

        class Physics:
            def create_rigid_body_view(self, path):
                return SimpleNamespace(max_shapes=robot_counts[path])

        return SimpleNamespace(root_physx_view=Root(), _physics_sim_view=Physics())

    def door_asset(materials):
        root_paths = (
            "/World/envs/env_0/Door/door_handle",
            "/World/envs/env_0/Door/panel",
        )
        target_paths = (
            "/World/envs/env_0/Door/door_handle",
            "/World/envs/env_1/Door/door_handle",
        )

        class Root:
            link_paths = [list(root_paths)]

            def get_material_properties(self):
                raise AssertionError("exact door evidence must use target rigid-body view")

        class Target:
            count = 2
            max_shapes = 2
            prim_paths = list(target_paths)

            def get_material_properties(self):
                return materials

        class Physics:
            def create_rigid_body_view(self, path):
                assert path == "/World/envs/env_*/Door/door_handle"
                return Target()

        return SimpleNamespace(root_physx_view=Root(), _physics_sim_view=Physics())

    pre_robot = torch.zeros((2, 6, 3), dtype=torch.float32)
    post_robot = pre_robot.clone()
    post_robot[:, :5, :] = torch.tensor((1.1, 0.9, 0.0))
    handle = torch.tensor(
        [
            [[0.6, 0.5, 0.0], [0.7, 0.55, 0.0]],
            [[0.6, 0.5, 0.0], [0.7, 0.55, 0.0]],
        ],
        dtype=torch.float32,
    )

    def slices(robot, door):
        return {
            "robot": probe._m39_asset_material_slices(
                robot_asset(robot), probe.A2_M39_GRIPPER_BODY_NAMES, "robot", 2
            ),
            "door": probe._m39_asset_material_slices(
                door_asset(door), ("door_handle",), "door", 2,
                require_exact_body_view=True,
            ),
        }

    metadata = probe._capture_m39_material_evidence(
        slices(pre_robot, handle), slices(post_robot, handle.clone())
    )
    assert metadata["schema"] == "a2_m39_gripper_material_v1"
    assert metadata["event_term"]["static_friction_range"] == [1.1, 1.1]
    assert metadata["event_term"]["dynamic_friction_range"] == [0.9, 0.9]
    assert metadata["handle"]["scope"] == "exact_target_rigid_body_view_all_envs"
    assert metadata["handle"]["unchanged"] is True
    assert metadata["all_envs"] is True


def test_c18_door_selector_dispatch_coexists_with_cb2h_camera_markers():
    tree = ast.parse(SIMULATOR.read_text(encoding="utf-8"))
    selector_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_get_task_obj_cfg_dict_for_door_eval"
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[selector_node], type_ignores=[]), str(SIMULATOR), "exec"),
        namespace,
    )

    class TaskModule:
        TaskObjCfgDict = {"default": object()}

        @staticmethod
        def get_TaskObjCfgDict_for_door_config(num_envs, env_config):
            return {"door": (num_envs, tuple(env_config["a2_door_weight_range"]))}

        @staticmethod
        def get_TaskObjCfgDict_for_eval_door_handle_height_linspace(num_envs, values):
            return {"door": (num_envs, tuple(values))}

    selector = namespace["_get_task_obj_cfg_dict_for_door_eval"]
    assert selector(TaskModule, {"a2_door_weight_range": [80.0, 160.0]}, 8) == {
        "door": (8, (80.0, 160.0))
    }
    assert selector(TaskModule, {"a2_eval_door_handle_height_linspace": [0.2, 0.4]}, 8) == {
        "door": (8, (0.2, 0.4))
    }
    assert selector(TaskModule, {}, 8) is TaskModule.TaskObjCfgDict


class _Config(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


def _build_fake_actor(monkeypatch, d435i_forward_mode="sequential"):
    import gr00t.rl.trl.modules.vision_actor_critic_modules_triview_recurrent as actor_impl

    calls = {"d435": 0, "head": 0}

    class FakeEncoder(torch.nn.Module):
        def __init__(self, name):
            super().__init__()
            self.name = name
            self.output_dim = 128
            self.module_config_dict = _Config(
                layer_config=_Config(type="ResNet")
            )
            self.projection = torch.nn.Linear(1, 128, bias=False)

        def forward(self, value):
            calls[self.name] += 1
            pooled = value.mean(dim=(1, 2, 3), keepdim=False).unsqueeze(-1)
            return self.projection(pooled)

    class FakeMlp(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.output_dim = 12
            self.linear = torch.nn.Linear(256, 12)

        def forward(self, value):
            return self.linear(value)

    d435_cfg = _Config(
        name="d435",
        module_config_dict=_Config(layer_config=_Config(type="ResNet")),
    )
    head_cfg = _Config(
        name="head",
        module_config_dict=_Config(layer_config=_Config(type="ResNet")),
    )
    mlp_cfg = _Config(name="mlp")
    backbone = _Config(
        d435i_vision_module=d435_cfg,
        head_vision_module=head_cfg,
        mlp_module=mlp_cfg,
    )

    def fake_instantiate(config, **kwargs):
        del kwargs
        if config.name == "d435":
            return FakeEncoder("d435")
        if config.name == "head":
            return FakeEncoder("head")
        if config.name == "mlp":
            return FakeMlp()
        raise AssertionError(f"unexpected fake instantiate config: {config!r}")

    monkeypatch.setattr(actor_impl, "instantiate", fake_instantiate)
    env_config = _Config(robot=_Config(algo_obs_dim_dict={
        "actor_obs": 81,
        "vision_obs": 384 * 216 * 6,
        "context_vision_obs": 136 * 384 * 3,
        "camera_meta": 6,
    }))
    algo_config = _Config(
        init_noise_std=0.001,
        freeze_noise_std=False,
        clamp_noise_std=True,
        max_noise_std=0.001,
    )
    actor = actor_impl.TriViewContextSharedEncoderVisionRecurrentActor(
        env_config=env_config,
        algo_config=algo_config,
        backbone=backbone,
        module_dim_dict={},
        running_mean_std=False,
        view_contract=(
            {} if d435i_forward_mode is None else {"d435i_forward_mode": d435i_forward_mode}
        ),
    )
    return actor, calls


def test_triview_actor_exposes_standard_normalized_action_interface(monkeypatch):
    actor, _ = _build_fake_actor(monkeypatch)
    assert actor.has_normalized_actions is False


def test_triview_actor_exposes_standard_mode_interface_and_peer_consistency(monkeypatch):
    actor, _ = _build_fake_actor(monkeypatch)
    state_keys = set(actor.state_dict())
    assert actor.is_eval_mode is False
    actor.eval_mode()
    assert actor.is_eval_mode is True
    actor.train_mode()
    assert actor.is_eval_mode is False
    assert set(actor.state_dict()) == state_keys

    def mode_method(source_path: Path, class_name: str, method_name: str):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
        return next(
            node
            for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == method_name
        )

    actor_method_path = ACTOR
    peer_paths = (
        (ROOT / "gr00t/rl/trl/modules/vision_actor_critic_modules.py", "VisionActor"),
        (ROOT / "gr00t/rl/trl/modules/actor_critic_modules.py", "Actor"),
    )
    for method_name in ("eval_mode", "train_mode"):
        actor_method = mode_method(
            actor_method_path,
            "TriViewContextSharedEncoderVisionRecurrentActor",
            method_name,
        )
        assert [argument.arg for argument in actor_method.args.args] == ["self"]
        for peer_path, peer_class in peer_paths:
            peer_method = mode_method(peer_path, peer_class, method_name)
            assert [ast.dump(statement) for statement in actor_method.body] == [
                ast.dump(statement) for statement in peer_method.body
            ]


def _make_actor_obs(batch=1, sequence=None):
    shape = (batch,) if sequence is None else (batch, sequence)
    actor_obs = torch.ones((*shape, 81), dtype=torch.float32)
    dual = torch.full((*shape, 384, 216, 6), 0.25, dtype=torch.float32)
    dual[..., 3:] = 0.5
    head = torch.full((*shape, 136, 384, 3), 0.75, dtype=torch.float32)
    meta = torch.zeros((*shape, 6), dtype=torch.float32)
    meta[..., 3:] = 1.0
    return {
        "actor_obs": actor_obs,
        "vision_obs": dual,
        "context_vision_obs": head,
        "camera_meta": meta,
    }


def test_actor_executes_rollout_sequence_backward_and_strict_rank_contract(monkeypatch):
    actor, calls = _build_fake_actor(monkeypatch)
    rollout_obs = _make_actor_obs()
    actor.init_rollout()
    rollout = actor.rollout(rollout_obs)
    assert rollout["actions"].shape == (1, 12)
    assert calls == {"d435": 2, "head": 1}
    actor.clear_rollout()
    assert actor.obs_dict_buffer == {}
    sequence_obs = _make_actor_obs(batch=1, sequence=2)
    masks = torch.tensor([[True, False]])
    sequence_output = actor.forward(sequence_obs, masks=masks)
    assert sequence_output.shape == (1, 2, 12)
    sequence_output[:, 0].sum().backward()
    assert any(parameter.grad is not None for parameter in actor.parameters())
    optimizer = torch.optim.Adam(actor.parameters(), lr=1.0e-3)
    optimized_ids = {id(parameter) for group in optimizer.param_groups for parameter in group["params"]}
    assert id(actor.d435i_vision_module) not in optimized_ids
    assert all(id(parameter) in optimized_ids for parameter in actor.d435i_vision_module.parameters())
    assert all(id(parameter) in optimized_ids for parameter in actor.head_vision_module.parameters())
    assert actor.d435i_vision_module is not actor.head_vision_module
    state = actor.state_dict()
    actor_reloaded, _ = _build_fake_actor(monkeypatch)
    actor_reloaded.load_state_dict(state, strict=True)
    actor_reloaded.memory.reset()
    with pytest.raises(ValueError, match="ranks"):
        actor_reloaded.forward(
            {
                **_make_actor_obs(),
                "vision_obs": _make_actor_obs(batch=1, sequence=1)["vision_obs"],
            }
        )


def test_actor_packed_d435_calls_shared_encoder_once_and_preserves_split_order(monkeypatch):
    actor, calls = _build_fake_actor(monkeypatch, d435i_forward_mode="packed")
    output = actor.forward(_make_actor_obs(batch=2))
    assert output.shape == (2, 12)
    assert calls == {"d435": 1, "head": 1}
    state_keys = set(actor.state_dict())
    assert any(key.startswith("d435i_vision_module.") for key in state_keys)
    assert not any("left_encoder" in key or "right_encoder" in key for key in state_keys)
    assert actor.d435i_vision_module is not actor.head_vision_module


def test_actor_observability_snapshot_is_finite_and_named(monkeypatch):
    actor, _ = _build_fake_actor(monkeypatch, d435i_forward_mode="packed")
    actor.forward(_make_actor_obs(batch=2))
    snapshot = actor.get_observability_snapshot()
    expected = {
        "feature/d435_left_norm",
        "feature/d435_right_norm",
        "feature/d435_norm",
        "feature/head_norm",
        "feature/head_gate_mean",
        "feature/head_gate_p95",
    }
    assert expected.issubset(snapshot)
    assert all(value.ndim == 0 and torch.isfinite(value) for value in snapshot.values())


def test_actor_rejects_missing_or_invalid_d435_forward_mode(monkeypatch):
    with pytest.raises(ValueError, match="d435i_forward_mode"):
        _build_fake_actor(monkeypatch, d435i_forward_mode=None)
    with pytest.raises(ValueError, match="d435i_forward_mode"):
        _build_fake_actor(monkeypatch, d435i_forward_mode="unsupported")


def test_actor_packed_mode_fails_fast_on_invalid_input_without_sequential_fallback(monkeypatch):
    actor, calls = _build_fake_actor(monkeypatch, d435i_forward_mode="packed")
    invalid = _make_actor_obs(batch=1)
    invalid["vision_obs"] = invalid["vision_obs"][:, :, :-1]
    with pytest.raises(ValueError, match="shapes must be|image shapes"):
        actor.forward(invalid)
    assert calls == {"d435": 0, "head": 0}

    actor, calls = _build_fake_actor(monkeypatch, d435i_forward_mode="packed")
    actor.d435i_forward_mode = "invalid-after-init"
    with pytest.raises(RuntimeError, match="d435i_forward_mode"):
        actor.forward(_make_actor_obs(batch=1))
    assert calls == {"d435": 0, "head": 0}


def test_actor_packed_preserves_left_right_order_for_rollout_and_masked_sequence(monkeypatch):
    actor, _ = _build_fake_actor(monkeypatch, d435i_forward_mode="packed")
    captured = []

    class RecordingEncoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.output_dim = 128
            self.module_config_dict = _Config(layer_config=_Config(type="ResNet"))

        def forward(self, value):
            captured.append(value.detach().clone())
            output = torch.zeros(value.shape[0], 128, dtype=value.dtype, device=value.device)
            output[:, 0] = value.mean(dim=(1, 2, 3))
            return output

    actor.d435i_vision_module = RecordingEncoder()
    monkeypatch.setattr(
        actor,
        "_fuse",
        lambda f_left, f_right, f_head, camera_meta: f_left + f_right + f_head,
    )
    rank4 = _make_actor_obs(batch=2)
    actor._encode_views(rank4["vision_obs"], rank4["context_vision_obs"], rank4["camera_meta"], None)
    assert len(captured) == 1
    assert tuple(captured[0].shape) == (4, 3, 384, 216)
    assert torch.allclose(captured[0][:2].mean(dim=(1, 2, 3)), torch.full((2,), 0.25))
    assert torch.allclose(captured[0][2:].mean(dim=(1, 2, 3)), torch.full((2,), 0.5))

    sequence = _make_actor_obs(batch=2, sequence=2)
    masks = torch.tensor([[True, False], [True, True]])
    actor._encode_views(
        sequence["vision_obs"], sequence["context_vision_obs"], sequence["camera_meta"], masks
    )
    assert len(captured) == 2
    assert tuple(captured[1].shape) == (6, 3, 384, 216)


def test_actor_syncbn_batch_count_delta_is_mode_specific(monkeypatch):
    class CountingEncoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.output_dim = 128
            self.module_config_dict = _Config(layer_config=_Config(type="ResNet"))
            self.register_buffer("num_batches_tracked", torch.zeros((), dtype=torch.long))

        def forward(self, value):
            self.num_batches_tracked.add_(1)
            return torch.zeros(value.shape[0], 128, dtype=value.dtype, device=value.device)

    for mode, expected_d435_count in (("packed", 1), ("sequential", 2)):
        actor, _ = _build_fake_actor(monkeypatch, d435i_forward_mode=mode)
        actor.d435i_vision_module = CountingEncoder()
        actor.head_vision_module = CountingEncoder()
        actor.forward(_make_actor_obs(batch=2))
        assert int(actor.d435i_vision_module.num_batches_tracked.item()) == expected_d435_count
        assert int(actor.head_vision_module.num_batches_tracked.item()) == 1


def test_actor_accepts_rank4_meta2_and_rank5_meta3_without_downloads(monkeypatch):
    actor, _ = _build_fake_actor(monkeypatch)
    rank4 = _make_actor_obs()
    assert actor.forward(rank4).shape == (1, 12)
    rank5 = _make_actor_obs(batch=1, sequence=2)
    assert actor.forward(rank5, masks=torch.tensor([[True, True]])).shape == (1, 2, 12)


def test_simulator_capture_validates_batched_frames_reset_prime_and_head_cadence():
    simulator_tree = ast.parse(SIMULATOR.read_text(encoding="utf-8"))
    simulator_namespace = {
        "torch": torch,
    }
    simulator_namespace["compose_channel_stacked_dual_rgb"] = compose_channel_stacked_dual_rgb
    simulator_namespace["normalize_head_context_rgb"] = normalize_head_context_rgb
    validator_node = next(
        node
        for node in ast.walk(simulator_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "validate_camera_rgb_output"
    )
    exec(
        compile(
            ast.Module(body=[validator_node], type_ignores=[]),
            filename=str(SIMULATOR),
            mode="exec",
        ),
        simulator_namespace,
    )
    method_names = (
        "get_rgb_image",
        "_require_c_b2h_camera_cache_ready",
        "invalidate_c_b2h_camera_cache",
        "_refresh_c_b2h_camera_meta_cache",
        "_capture_c_b2h_camera_cache",
        "prime_c_b2h_camera_cache",
    )
    for method_name in method_names:
        method_node = next(
            node
            for node in ast.walk(simulator_tree)
            if isinstance(node, ast.FunctionDef) and node.name == method_name
        )
        compiled = compile(
            ast.Module(body=[method_node], type_ignores=[]),
            filename=str(SIMULATOR),
            mode="exec",
        )
        exec(compiled, simulator_namespace)

    sim_dt = 1.0 / 200.0
    d435_period = 1.0 / 30.0
    head_period = 1.0 / 15.0

    class Sensor:
        def __init__(self, shape, value, update_period):
            self.value = value
            self.update_period = update_period
            self.frame = torch.zeros(2, dtype=torch.int64)
            rgb = torch.full((2, *shape, 3), value, dtype=torch.uint8)
            rgb[..., 1] = value + 1
            self._rgb = rgb
            self._outdated = torch.ones(2, dtype=torch.bool)
            self._timestamp = torch.zeros(2, dtype=torch.float64)
            self._timestamp_last_update = torch.zeros(2, dtype=torch.float64)
            self._requires_public_reset = torch.zeros(2, dtype=torch.bool)
            self._rewrite_generation = 0
            self.reset_calls = []
            self.update_calls = []

        def _refresh_outdated_buffers(self, refresh_ids):
            self.frame[refresh_ids] += 1
            self._timestamp_last_update[refresh_ids] = self._timestamp[refresh_ids]
            self._outdated[refresh_ids] = False
            self._rewrite_generation += 1
            current = self.frame.to(dtype=torch.uint8)
            self._rgb[..., 0] = self.value + current[:, None, None] + self._rewrite_generation
            self._rgb[..., 1] = self.value + current[:, None, None] + self._rewrite_generation + 1

        def update(self, dt):
            self.update_calls.append(float(dt))
            if bool(torch.any(self._requires_public_reset & ~self._outdated).item()):
                raise RuntimeError("lazy camera data requires public reset before refresh")
            self._timestamp += dt
            self._outdated |= (
                self._timestamp - self._timestamp_last_update + 1.0e-6 >= self.update_period
            )

        @property
        def data(self):
            if bool(torch.any(self._requires_public_reset & ~self._outdated).item()):
                raise RuntimeError("lazy camera data requires public reset before refresh")
            refresh_ids = self._outdated.nonzero(as_tuple=False).flatten()
            if refresh_ids.numel() > 0:
                self._refresh_outdated_buffers(refresh_ids)
            return SimpleNamespace(output={"rgb": self._rgb})

        def reset(self, env_ids):
            env_ids = env_ids.to(dtype=torch.long)
            self.reset_calls.append(env_ids.clone())
            self._timestamp[env_ids] = 0.0
            self._timestamp_last_update[env_ids] = 0.0
            self._outdated[env_ids] = True
            self.frame[env_ids] = 0
            self._requires_public_reset[env_ids] = False

        def require_public_reset(self, env_ids):
            self._requires_public_reset[env_ids.to(dtype=torch.long)] = True

        def place_one_tick_from_due(self, env_id):
            self._timestamp[env_id] = self.update_period - sim_dt
            self._timestamp_last_update[env_id] = 0.0
            self._outdated[env_id] = False

    class FakePhysics:
        def __init__(self, sensors):
            self.sensors = sensors
            self.render_calls = 0

        def render(self):
            before = [sensor.frame.clone() for sensor in self.sensors]
            self.render_calls += 1
            assert all(torch.equal(previous, sensor.frame) for previous, sensor in zip(before, self.sensors))

    class FakeScene:
        def __init__(self):
            self.update_calls = 0
            self.update_dts = []
            self.sensors = []

        def update(self, dt):
            self.update_calls += 1
            self.update_dts.append(float(dt))
            for sensor in self.sensors:
                sensor.update(dt)

    sim = SimpleNamespace()
    sim.sim_device = "cpu"
    sim.num_envs = 2
    sim.simulator_config = SimpleNamespace(
        cameras=SimpleNamespace(image_mean=[0.0, 0.0, 0.0], image_std=[1.0, 1.0, 1.0]),
        sim=SimpleNamespace(fps=200),
    )
    sim._policy_multiview = {
        "architecture_id": "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19",
        "fast_period_s": 1.0 / 30.0,
        "context_period_s": 1.0 / 15.0,
    }
    sim.ego_camera = Sensor((384, 216), 1, d435_period)
    sim.policy_secondary_camera = Sensor((384, 216), 2, d435_period)
    sim.policy_context_camera = Sensor((136, 384), 3, head_period)
    sim.sim = FakePhysics([sim.ego_camera, sim.policy_secondary_camera, sim.policy_context_camera])
    sim.scene = FakeScene()
    sim.scene.sensors = [sim.ego_camera, sim.policy_secondary_camera, sim.policy_context_camera]
    sim._cb2h_vision_obs_cache = None
    sim._cb2h_context_vision_obs_cache = None
    sim._cb2h_camera_meta_cache = None
    sim._cb2h_elapsed_s = 0.0
    sim._cb2h_last_capture_s = {"left": None, "right": None, "head": None}
    sim._cb2h_last_frame_s = {
        name: torch.full((2,), -1.0) for name in ("left", "right", "head")
    }
    sim._cb2h_last_frame_id = {
        name: torch.full((2,), -1, dtype=torch.int64) for name in ("left", "right", "head")
    }
    sim._cb2h_ever_captured = {
        name: torch.zeros(2, dtype=torch.bool) for name in ("left", "right", "head")
    }
    sim._cb2h_cache_valid = torch.zeros(2, dtype=torch.bool)
    for method_name in method_names:
        setattr(sim, method_name, simulator_namespace[method_name].__get__(sim, type(sim)))
    prime_node = next(
        node
        for node in ast.walk(simulator_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "prime_c_b2h_camera_cache"
    )
    prime_source = ast.get_source_segment(SIMULATOR.read_text(encoding="utf-8"), prime_node)
    assert prime_source is not None
    assert prime_source.count("self.invalidate_c_b2h_camera_cache(env_ids)") == 1
    assert prime_source.index("self.invalidate_c_b2h_camera_cache(env_ids)") < prime_source.index(
        "self.ego_camera.reset(env_ids)"
    )
    sim._capture_c_b2h_camera_cache()
    assert torch.equal(sim._cb2h_camera_meta_cache[:, 3:], torch.ones(2, 3))
    held_frame = sim._cb2h_last_frame_id["head"].clone()
    sim._capture_c_b2h_camera_cache(advance_time=False)
    assert torch.all(sim._cb2h_camera_meta_cache[:, 0] >= 0.0)
    assert torch.equal(sim._cb2h_last_frame_id["head"], held_frame)
    initial_capture_schedule = dict(sim._cb2h_last_capture_s)
    all_env_ids = torch.tensor([0, 1])
    sim._cb2h_last_capture_s["left"] = sim._cb2h_elapsed_s - 1.0
    sim.ego_camera.frame = torch.tensor([4, 1])
    sim.policy_secondary_camera.frame = torch.tensor([4, 1])
    with pytest.raises(RuntimeError, match="did not advance"):
        sim._capture_c_b2h_camera_cache(
            advance_time=False,
            required_env_ids=all_env_ids,
        )
    sim.ego_camera.frame = torch.tensor([5, 5])
    sim.policy_secondary_camera.frame = torch.tensor([5, 6])
    with pytest.raises(RuntimeError, match="synchronized"):
        sim._capture_c_b2h_camera_cache(
            force=True,
            advance_time=False,
            required_env_ids=all_env_ids,
        )
    sim.ego_camera.frame = torch.tensor([5, 5])
    sim.policy_secondary_camera.frame = torch.tensor([5, 5])
    sim.policy_context_camera.frame = torch.tensor([5, 5])
    for sensor in (sim.ego_camera, sim.policy_secondary_camera, sim.policy_context_camera):
        sensor.frame[:] = 1
    sim._cb2h_last_capture_s = initial_capture_schedule.copy()
    sim.invalidate_c_b2h_camera_cache(torch.tensor([1]))
    assert not bool(sim._cb2h_cache_valid[1].item())
    with pytest.raises(RuntimeError, match="awaiting"):
        sim.get_rgb_image()

    stale_vision = sim._cb2h_vision_obs_cache.clone()
    stale_context = sim._cb2h_context_vision_obs_cache.clone()
    reset_env_ids = torch.tensor([1])
    for sensor in (sim.ego_camera, sim.policy_secondary_camera, sim.policy_context_camera):
        sensor.require_public_reset(reset_env_ids)

    def stale_prime_without_public_reset():
        sim.sim.render()
        sim.scene.update(dt=sim_dt)
        sim._capture_c_b2h_camera_cache(
            force=True,
            advance_time=False,
            required_env_ids=reset_env_ids,
        )

    with pytest.raises(RuntimeError, match="public reset"):
        stale_prime_without_public_reset()
    sim.prime_c_b2h_camera_cache(torch.tensor([1]))
    assert bool(torch.all(sim._cb2h_cache_valid).item())
    assert sim.sim.render_calls == 2
    assert sim.scene.update_calls == 2
    assert all(
        len(sensor.reset_calls) == 1
        and torch.equal(sensor.reset_calls[0], reset_env_ids)
        for sensor in (sim.ego_camera, sim.policy_secondary_camera, sim.policy_context_camera)
    )
    assert sim.scene.update_dts[-1] == pytest.approx(0.0)
    assert sim.ego_camera.frame.tolist() == [1, 1]
    assert sim.policy_secondary_camera.frame.tolist() == [1, 1]
    assert sim.policy_context_camera.frame.tolist() == [1, 1]
    assert torch.equal(sim._cb2h_vision_obs_cache[0], stale_vision[0])
    assert torch.equal(sim._cb2h_context_vision_obs_cache[0], stale_context[0])
    assert not torch.equal(sim._cb2h_vision_obs_cache[1], stale_vision[1])
    assert not torch.equal(sim._cb2h_context_vision_obs_cache[1], stale_context[1])
    unaffected_vision = sim._cb2h_vision_obs_cache[0].clone()
    unaffected_context = sim._cb2h_context_vision_obs_cache[0].clone()
    unaffected_meta = sim._cb2h_camera_meta_cache[0].clone()
    unaffected_cache_valid = sim._cb2h_cache_valid[0].clone()
    unaffected_frame_id = {
        name: sim._cb2h_last_frame_id[name][0].clone() for name in ("left", "right", "head")
    }
    unaffected_frame_s = {
        name: sim._cb2h_last_frame_s[name][0].clone() for name in ("left", "right", "head")
    }
    unaffected_ever_captured = {
        name: sim._cb2h_ever_captured[name][0].clone() for name in ("left", "right", "head")
    }
    unaffected_raw = sim.ego_camera._rgb[0].clone()
    schedule_before_second_prime = dict(sim._cb2h_last_capture_s)
    elapsed_before_second_prime = sim._cb2h_elapsed_s
    for sensor in (sim.ego_camera, sim.policy_secondary_camera, sim.policy_context_camera):
        sensor.place_one_tick_from_due(0)
        sensor._outdated[0] = True
    sim.prime_c_b2h_camera_cache(reset_env_ids)
    assert bool(torch.all(sim._cb2h_cache_valid).item())
    assert sim.sim.render_calls == 3
    assert sim.scene.update_calls == 3
    assert all(
        len(sensor.reset_calls) == 2
        and torch.equal(sensor.reset_calls[1], reset_env_ids)
        for sensor in (sim.ego_camera, sim.policy_secondary_camera, sim.policy_context_camera)
    )
    assert sim.scene.update_dts[-2:] == [pytest.approx(0.0), pytest.approx(0.0)]
    assert sim.ego_camera.frame.tolist() == [2, 1]
    assert sim.policy_secondary_camera.frame.tolist() == [2, 1]
    assert sim.policy_context_camera.frame.tolist() == [2, 1]
    assert sim._cb2h_elapsed_s == pytest.approx(elapsed_before_second_prime)
    assert sim._cb2h_last_capture_s == schedule_before_second_prime
    assert not torch.equal(sim.ego_camera._rgb[0], unaffected_raw)
    assert torch.equal(sim._cb2h_vision_obs_cache[0], unaffected_vision)
    assert torch.equal(sim._cb2h_context_vision_obs_cache[0], unaffected_context)
    assert torch.equal(sim._cb2h_camera_meta_cache[0], unaffected_meta)
    assert torch.equal(sim._cb2h_cache_valid[0], unaffected_cache_valid)
    for name in ("left", "right", "head"):
        assert torch.equal(sim._cb2h_last_frame_id[name][0], unaffected_frame_id[name])
        assert torch.equal(sim._cb2h_last_frame_s[name][0], unaffected_frame_s[name])
        assert torch.equal(sim._cb2h_ever_captured[name][0], unaffected_ever_captured[name])
        assert bool(sim._cb2h_ever_captured[name][1].item())
        assert int(sim._cb2h_last_frame_id[name][1].item()) > 0
    saved_context_cache = sim._cb2h_context_vision_obs_cache
    sim._cb2h_context_vision_obs_cache = None
    with pytest.raises(RuntimeError, match="fully initialized"):
        sim._capture_c_b2h_camera_cache(
            force=True,
            advance_time=False,
            required_env_ids=reset_env_ids,
        )
    sim._cb2h_context_vision_obs_cache = saved_context_cache
    non_target_history_by_step = []
    for _ in range(7):
        sim.scene.update(dt=sim_dt)
        sim._capture_c_b2h_camera_cache()
        non_target_history_by_step.append(int(sim._cb2h_last_frame_id["left"][0].item()))
    assert non_target_history_by_step[:6] == [1] * 6
    assert non_target_history_by_step[6] == 3
    assert torch.equal(sim._cb2h_last_frame_id["left"], sim._cb2h_last_frame_id["right"])
    assert sim._cb2h_last_capture_s["left"] == pytest.approx(
        elapsed_before_second_prime + 7.0 * sim_dt
    )
    assert sim._cb2h_last_capture_s["right"] == pytest.approx(
        elapsed_before_second_prime + 7.0 * sim_dt
    )
    assert sim._cb2h_last_capture_s["head"] == schedule_before_second_prime["head"]

    phase = SimpleNamespace()
    phase.sim_device = "cpu"
    phase.num_envs = 2
    phase.simulator_config = SimpleNamespace(
        cameras=SimpleNamespace(image_mean=[0.0, 0.0, 0.0], image_std=[1.0, 1.0, 1.0]),
        sim=SimpleNamespace(fps=200),
    )
    phase._policy_multiview = {
        "architecture_id": "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19",
        "fast_period_s": 1.0 / 30.0,
        "context_period_s": 1.0 / 15.0,
    }
    phase.ego_camera = Sensor((384, 216), 1, d435_period)
    phase.policy_secondary_camera = Sensor((384, 216), 2, d435_period)
    phase.policy_context_camera = Sensor((136, 384), 3, head_period)
    phase.sim = FakePhysics(
        [phase.ego_camera, phase.policy_secondary_camera, phase.policy_context_camera]
    )
    phase.scene = FakeScene()
    phase.scene.sensors = [
        phase.ego_camera,
        phase.policy_secondary_camera,
        phase.policy_context_camera,
    ]
    phase._cb2h_vision_obs_cache = None
    phase._cb2h_context_vision_obs_cache = None
    phase._cb2h_camera_meta_cache = None
    phase._cb2h_elapsed_s = -sim_dt
    phase._cb2h_last_capture_s = {"left": None, "right": None, "head": None}
    phase._cb2h_last_frame_s = {
        name: torch.full((2,), -1.0) for name in ("left", "right", "head")
    }
    phase._cb2h_last_frame_id = {
        name: torch.full((2,), -1, dtype=torch.int64) for name in ("left", "right", "head")
    }
    phase._cb2h_ever_captured = {
        name: torch.zeros(2, dtype=torch.bool) for name in ("left", "right", "head")
    }
    phase._cb2h_cache_valid = torch.zeros(2, dtype=torch.bool)
    for method_name in method_names:
        setattr(phase, method_name, simulator_namespace[method_name].__get__(phase, type(phase)))

    phase._capture_c_b2h_camera_cache()
    assert phase._cb2h_elapsed_s == pytest.approx(0.0)
    assert phase._cb2h_last_capture_s == {"left": 0.0, "right": 0.0, "head": 0.0}
    for _ in range(4):
        phase.scene.update(sim_dt)
        phase._capture_c_b2h_camera_cache()
    assert phase._cb2h_elapsed_s == pytest.approx(4.0 * sim_dt)
    assert phase._cb2h_last_capture_s["left"] == pytest.approx(0.0)
    phase_non_target_vision = phase._cb2h_vision_obs_cache[0].clone()
    phase_non_target_context = phase._cb2h_context_vision_obs_cache[0].clone()
    phase_non_target_meta = phase._cb2h_camera_meta_cache[0].clone()
    phase_non_target_frame_id = {
        name: phase._cb2h_last_frame_id[name][0].clone() for name in ("left", "right", "head")
    }
    phase_non_target_frame_s = {
        name: phase._cb2h_last_frame_s[name][0].clone() for name in ("left", "right", "head")
    }
    phase_target_frame_id = {
        name: phase._cb2h_last_frame_id[name][1].clone() for name in ("left", "right", "head")
    }
    phase_target_frame_s = {
        name: phase._cb2h_last_frame_s[name][1].clone() for name in ("left", "right", "head")
    }
    phase_target_ever_captured = {
        name: phase._cb2h_ever_captured[name][1].clone() for name in ("left", "right", "head")
    }

    target_env_ids = torch.tensor([1])
    phase.prime_c_b2h_camera_cache(target_env_ids)
    assert phase._cb2h_elapsed_s == pytest.approx(4.0 * sim_dt)
    assert phase._cb2h_last_capture_s["left"] == pytest.approx(0.0)
    assert torch.equal(phase._cb2h_vision_obs_cache[0], phase_non_target_vision)
    assert torch.equal(phase._cb2h_context_vision_obs_cache[0], phase_non_target_context)
    assert torch.equal(phase._cb2h_camera_meta_cache[0], phase_non_target_meta)
    for name in ("left", "right", "head"):
        assert torch.equal(phase._cb2h_last_frame_id[name][0], phase_non_target_frame_id[name])
        assert torch.equal(phase._cb2h_last_frame_s[name][0], phase_non_target_frame_s[name])
    phase_target_vision_after_prime = phase._cb2h_vision_obs_cache[1].clone()
    phase_target_context_after_prime = phase._cb2h_context_vision_obs_cache[1].clone()
    phase_target_meta_after_prime = phase._cb2h_camera_meta_cache[1].clone()
    phase_target_raw_before_due = phase.ego_camera._rgb[1].clone()
    phase_target_frame_id_after_prime = {
        name: phase._cb2h_last_frame_id[name][1].clone() for name in ("left", "right", "head")
    }
    phase_target_frame_s_after_prime = {
        name: phase._cb2h_last_frame_s[name][1].clone() for name in ("left", "right", "head")
    }
    phase_target_ever_after_prime = {
        name: phase._cb2h_ever_captured[name][1].clone() for name in ("left", "right", "head")
    }
    phase_target_valid_after_prime = phase._cb2h_cache_valid[1].clone()

    for _ in range(3):
        phase.scene.update(sim_dt)
        phase._capture_c_b2h_camera_cache()
    assert phase._cb2h_elapsed_s == pytest.approx(7.0 * sim_dt)
    assert phase._cb2h_last_capture_s["left"] == pytest.approx(7.0 * sim_dt)
    assert phase._cb2h_last_capture_s["right"] == pytest.approx(7.0 * sim_dt)
    assert phase._cb2h_last_capture_s["head"] == pytest.approx(0.0)
    assert not torch.equal(phase.ego_camera._rgb[1], phase_target_raw_before_due)
    assert torch.equal(phase._cb2h_vision_obs_cache[1], phase_target_vision_after_prime)
    assert torch.equal(phase._cb2h_context_vision_obs_cache[1], phase_target_context_after_prime)
    assert torch.equal(phase._cb2h_cache_valid[1], phase_target_valid_after_prime)
    assert torch.equal(phase._cb2h_camera_meta_cache[1, 3:], phase_target_meta_after_prime[3:])
    assert torch.all(phase._cb2h_camera_meta_cache[1, :3] > phase_target_meta_after_prime[:3])
    for name in ("left", "right", "head"):
        assert torch.equal(
            phase._cb2h_last_frame_id[name][1], phase_target_frame_id_after_prime[name]
        )
        assert torch.equal(
            phase._cb2h_last_frame_s[name][1], phase_target_frame_s_after_prime[name]
        )
        assert torch.equal(
            phase._cb2h_ever_captured[name][1], phase_target_ever_after_prime[name]
        )

    for _ in range(7):
        phase.scene.update(sim_dt)
        phase._capture_c_b2h_camera_cache()
    assert phase._cb2h_elapsed_s == pytest.approx(14.0 * sim_dt)
    assert phase._cb2h_last_capture_s["left"] == pytest.approx(14.0 * sim_dt)
    assert phase._cb2h_last_capture_s["right"] == pytest.approx(14.0 * sim_dt)
    assert phase._cb2h_last_capture_s["head"] == pytest.approx(14.0 * sim_dt)
    assert torch.equal(phase._cb2h_last_frame_id["left"], phase._cb2h_last_frame_id["right"])
    assert int(phase._cb2h_last_frame_id["left"][1].item()) > int(
        phase_target_frame_id_after_prime["left"].item()
    )
    assert torch.equal(
        phase._cb2h_last_frame_id["head"][1], phase_target_frame_id_after_prime["head"]
    )
    assert int(phase._cb2h_last_frame_id["head"][0].item()) > int(
        phase_non_target_frame_id["head"].item()
    )
    assert not torch.equal(phase._cb2h_vision_obs_cache[1], phase_target_vision_after_prime)
    assert torch.equal(phase._cb2h_context_vision_obs_cache[1], phase_target_context_after_prime)

    for _ in range(7):
        phase.scene.update(sim_dt)
        phase._capture_c_b2h_camera_cache()
    assert phase._cb2h_elapsed_s == pytest.approx(21.0 * sim_dt)
    assert phase._cb2h_last_capture_s["left"] == pytest.approx(21.0 * sim_dt)
    assert phase._cb2h_last_capture_s["right"] == pytest.approx(21.0 * sim_dt)
    assert phase._cb2h_last_capture_s["head"] == pytest.approx(14.0 * sim_dt)
    assert torch.equal(
        phase._cb2h_last_frame_id["head"][1], phase_target_frame_id_after_prime["head"]
    )
    assert torch.equal(phase._cb2h_context_vision_obs_cache[1], phase_target_context_after_prime)

    for _ in range(7):
        phase.scene.update(sim_dt)
        phase._capture_c_b2h_camera_cache()
    assert phase._cb2h_elapsed_s == pytest.approx(28.0 * sim_dt)
    assert phase._cb2h_last_capture_s["left"] == pytest.approx(28.0 * sim_dt)
    assert phase._cb2h_last_capture_s["right"] == pytest.approx(28.0 * sim_dt)
    assert phase._cb2h_last_capture_s["head"] == pytest.approx(28.0 * sim_dt)
    assert int(phase._cb2h_last_frame_id["head"][1].item()) > int(
        phase_target_frame_id_after_prime["head"].item()
    )
    assert not torch.equal(phase._cb2h_context_vision_obs_cache[1], phase_target_context_after_prime)

    right_frame_history = phase._cb2h_last_frame_id["right"].clone()
    phase._cb2h_last_frame_id["right"][0] -= 1
    with pytest.raises(RuntimeError, match="advance masks"):
        phase._capture_c_b2h_camera_cache(force=True, advance_time=False)
    phase._cb2h_last_frame_id["right"] = right_frame_history

    phase._cb2h_vision_obs_cache = None
    phase._cb2h_context_vision_obs_cache = None
    phase._cb2h_camera_meta_cache = None
    phase._cb2h_cache_valid.zero_()
    for name in ("left", "right", "head"):
        phase._cb2h_ever_captured[name].zero_()
        phase._cb2h_last_frame_id[name].fill_(-1)
        phase._cb2h_last_frame_s[name].fill_(-1.0)
    phase.ego_camera.frame[1] = 0
    phase.policy_secondary_camera.frame[1] = 0
    with pytest.raises(RuntimeError, match="unavailable before first render"):
        phase._capture_c_b2h_camera_cache(force=True, advance_time=False)


def test_v19_runner_requires_c18_provenance_gpu7_and_exact_dimensions():
    assert EXPECTED_RUNTIME_COMMIT == "c18aea8bdc1c76ce850b5223663d0ad8a7474c0a"
    assert WANDB_ORIGINAL_COMMIT != EXPECTED_RUNTIME_COMMIT
    assert EXPECTED_TEACHER_CHECKPOINT.name == "model_step_002000.pt"
    assert "CUDA_VISIBLE_DEVICES" in RUNNER.read_text(encoding="utf-8")
    binding = {
        "A2_GPU_BINDING_MODE": EXPECTED_GPU_BINDING_MODE,
        "CUDA_VISIBLE_DEVICES": EXPECTED_GPU_INDEX,
        "CUDA_DEVICE_ORDER": EXPECTED_CUDA_DEVICE_ORDER,
        "A2_EXPECTED_WORLD_SIZE": "1",
        "A2_EXPECTED_HOST_GPU_INDEX": EXPECTED_GPU_INDEX,
        "A2_EXPECTED_LOGICAL_GPU_INDEX": EXPECTED_LOGICAL_GPU_INDEX,
        "A2_EXPECTED_GPU_UUID": EXPECTED_GPU_UUID,
    }
    identity = validate_gpu7_environment(binding)
    assert identity["world_size"] == 1
    assert identity["logical_gpu_index"] == 0
    with pytest.raises(RuntimeError, match="complete"):
        validate_gpu7_environment({"CUDA_VISIBLE_DEVICES": "7"})
    with pytest.raises(RuntimeError, match="GPU7"):
        validate_gpu7_environment({**binding, "CUDA_VISIBLE_DEVICES": "0"})
    with pytest.raises(RuntimeError, match="distributed"):
        validate_gpu7_environment({**binding, "WORLD_SIZE": "1"})
    with pytest.raises(RuntimeError, match="Accelerate"):
        validate_gpu7_environment({**binding, "ACCELERATE_TORCH_DEVICE": "cuda:0"})
    _exact_hydra_override(
        ["num_envs=64", "algo.trl.num_total_batches=10000"],
        "num_envs",
        EXPECTED_NUM_ENVS,
    )
    with pytest.raises(ValueError, match="num_envs"):
        _exact_hydra_override(["num_envs=63"], "num_envs", EXPECTED_NUM_ENVS)


def test_v19_runner_pins_c18_scenario_file_and_keeps_overlay_cwd(tmp_path, monkeypatch):
    overlay = tmp_path / "overlay"
    runtime = tmp_path / "runtime"
    overlay.mkdir()
    runtime_scenario = runtime / V19_RUNTIME_SCENARIO_RELATIVE_PATH
    runtime_scenario.parent.mkdir(parents=True)
    runtime_scenario.write_text(
        "def get_TaskObjCfgDict_for_door_config(num_envs, env_config):\n"
        "    return num_envs, env_config\n",
        encoding="utf-8",
    )
    overlay_scenario = overlay / V19_RUNTIME_SCENARIO_RELATIVE_PATH
    overlay_scenario.parent.mkdir(parents=True)
    overlay_scenario.write_text("TaskObjCfgDict = {}\n", encoding="utf-8")

    monkeypatch.chdir(runtime)
    original_loader = importlib.util.spec_from_file_location
    try:
        pinned = install_v19_runtime_scenario_file_pin(
            {V19_RUNTIME_SCENARIO_MODULE: runtime_scenario}
        )
        assert pinned == runtime_scenario.resolve()
        with pytest.raises(RuntimeError, match="already installed"):
            install_v19_runtime_scenario_file_pin(
                {V19_RUNTIME_SCENARIO_MODULE: runtime_scenario}
            )
        monkeypatch.chdir(overlay)
        spec = importlib.util.spec_from_file_location(
            "door", str(V19_RUNTIME_SCENARIO_RELATIVE_PATH)
        )
        assert spec is not None and spec.loader is not None
        assert Path(spec.origin).resolve() == runtime_scenario.resolve()
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert callable(module.get_TaskObjCfgDict_for_door_config)
        wrong_name_spec = importlib.util.spec_from_file_location(
            "other", str(V19_RUNTIME_SCENARIO_RELATIVE_PATH)
        )
        assert wrong_name_spec is not None
        assert Path(wrong_name_spec.origin).resolve() == overlay_scenario.resolve()
        wrong_path_spec = importlib.util.spec_from_file_location("door", overlay_scenario)
        assert wrong_path_spec is not None
        assert Path(wrong_path_spec.origin).resolve() == overlay_scenario.resolve()
        assert importlib.util.spec_from_file_location("probe", None) is None
    finally:
        importlib.util.spec_from_file_location = original_loader

    runner_source = RUNNER.read_text(encoding="utf-8")
    assert "os.chdir(overlay_repository)" in runner_source
    assert "scenario_file_pin=" in runner_source


def test_v19_overlay_import_precedence_isolated_and_fail_fast(tmp_path):
    assert EXTERNAL_EDITABLE_REPOSITORY.is_dir()
    legacy = _run_overlay_import_probe(ROOT, "legacy")
    assert legacy.returncode == 0, legacy.stderr
    assert str(EXTERNAL_EDITABLE_REPOSITORY / "gr00t") in legacy.stdout
    assert str(ROOT / "gr00t") not in legacy.stdout

    fixed = _run_overlay_import_probe(ROOT, "fixed")
    assert fixed.returncode == 0, fixed.stderr
    assert f"ROOT={ROOT / 'gr00t/__init__.py'}" in fixed.stdout
    assert (
        f"VALIDATOR={ROOT / 'gr00t/rl/scripts/validate_a2_teacher_checkpoint.py'}"
        in fixed.stdout
    )
    assert str(EXTERNAL_EDITABLE_REPOSITORY / "gr00t") not in fixed.stdout

    preloaded = _run_overlay_import_probe(ROOT, "preloaded")
    assert preloaded.returncode != 0
    assert "A2 overlay source identity mismatch" in preloaded.stderr
    assert str(EXTERNAL_EDITABLE_REPOSITORY / "gr00t") in preloaded.stderr

    missing = _run_overlay_import_probe(tmp_path / "missing-overlay", "fixed")
    assert missing.returncode != 0
    assert "v19 overlay repository is unavailable" in missing.stderr

    with pytest.raises(FileNotFoundError, match="required branch-local files"):
        validate_overlay_repository(tmp_path)
