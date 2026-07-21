"""No-simulation M24-M27 environment contract tests."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
TRAIN_SOURCE = ROOT / "gr00t/rl/train_agent_trl.py"
ENV_CONFIG = ROOT / "gr00t/rl/config/env/door_open_a2_base.yaml"
V15_CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v15_main.yaml"
REWARD_CONFIG = ROOT / "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml"


def _tree() -> ast.Module:
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


def _train_tree() -> ast.Module:
    return ast.parse(TRAIN_SOURCE.read_text(encoding="utf-8"))


def _load_helper(name: str):
    node = next(node for node in _tree().body if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {"torch": torch, "math": math}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace[name]


def _load_train_helper(name: str):
    node = next(
        node
        for node in _train_tree().body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(TRAIN_SOURCE), "exec"),
        namespace,
    )
    return namespace[name]


def _class_method_source(name: str) -> str:
    class_node = next(node for node in _tree().body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp")
    method = next(node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.unparse(method)


def test_stage0_base_still_gate_precedes_standoff_recording():
    source = _class_method_source("_stage_0_to_1_advance_condition")
    assert "get_physical_homie_commands" in source
    assert "torch.norm(base_command[:, :3], dim=1) <= 0.1" in source
    assert source.index("torch.norm(base_command[:, :3], dim=1) <= 0.1") < source.index("_record_a2_stage0_to1_staging_standoff")


def test_staging_band_is_v15_only_overlay_and_base_still_is_explicit():
    base = OmegaConf.load(ENV_CONFIG).env.config
    v15 = OmegaConf.load(V15_CONFIG).env.config
    assert (base.a2_stage0_staging_x_min, base.a2_stage0_staging_x_max) == (0.55, 0.60)
    assert (v15.a2_stage0_staging_x_min, v15.a2_stage0_staging_x_max, v15.a2_stage0_staging_y_tol) == (0.50, 0.80, 0.15)


def test_contact_filter_membership_and_order_are_exact():
    source = SOURCE.read_text(encoding="utf-8")
    expected_body = (
        "trunk", "FL_hip", "FL_thigh", "FL_calf", "RL_hip", "RL_thigh", "RL_calf",
        "FR_hip", "FR_thigh", "FR_calf", "RR_hip", "RR_thigh", "RR_calf",
    )
    expected_arm = (
        "arm_body0", "arm_body1", "arm_body2", "arm_body3", "arm_body4", "arm_body5",
        "arm_body6", "arm_body6_to_gripper", "arm_body7", "arm_body8",
    )
    assert "A2_DOOR_BODY_PANEL_CONTACT_SENSOR" in source
    assert "A2_DOOR_ARM_PANEL_CONTACT_SENSOR" in source
    for name in (*expected_body, *expected_arm):
        assert f'"{name}"' in source
    assert "feet" not in source[source.index("A2_DOOR_BODY_PANEL_FILTER_NAMES"):source.index("A2_PENALIZED_CONTACT_BODY_NAMES")]
    assert "history_length=0" in source and "update_period=0.0" in source


def test_filtered_force_contract_is_fail_fast_and_non_cancelling():
    source = _class_method_source("_get_a2_door_panel_contact_force_components")
    assert "filter_prim_paths_expr" in source
    assert "force_matrix_w" in source
    assert "torch.all(torch.isfinite(force_matrix_w))" in source
    assert "force_matrix_w[:, 0, :, :].norm(dim=-1)" in source
    assert "per_filter_force.sum(dim=-1)" in source
    assert "not force_matrix_w.is_floating_point()" in source
    assert "force_matrix_w.device != torch.device(self.device)" in source


def test_shutdown_helper_closes_simulation_app_once_with_immediate_exit():
    class FakeSimulationApp:
        def __init__(self):
            self.calls = []

        def close(self, **kwargs):
            self.calls.append(kwargs)

    app = FakeSimulationApp()
    close_after_training = _load_train_helper("_close_simulation_app_after_training")
    close_after_training(app)
    assert app.calls == [{"skip_cleanup": True}]

    source = TRAIN_SOURCE.read_text(encoding="utf-8")
    assert "simulation_app.close(skip_cleanup=True)" in source
    assert source.index("trainer.train()") < source.rindex(
        "_close_simulation_app_after_training(simulation_app)"
    )
    assert "simulation_app.close()" not in source


def test_runtime_evidence_logs_follow_strict_metadata_and_sensor_validation():
    metadata = _class_method_source("_init_door_metadata")
    metadata_validation = metadata.index("torch.all(torch.isfinite(field_value))")
    metadata_log = metadata.index("logger.info(")
    assert metadata_validation < metadata_log
    assert "self.num_envs" in metadata[metadata_log:]
    assert "hinge_drive_max_force_min" in metadata[metadata_log:]
    assert "hinge_drive_max_force_max" in metadata[metadata_log:]
    assert "self.door_hinge_drive_max_force.device" in metadata[metadata_log:]

    panel = _class_method_source("_get_a2_door_panel_contact_force_components")
    force_validation = panel.index("torch.all(torch.isfinite(force_matrix_w))")
    total_validation = panel.index("torch.any(total_force < 0.0)")
    panel_log = panel.index("logger.info(")
    assert force_validation < panel_log
    assert total_validation < panel_log
    assert "_a2_runtime_evidence_sensor_keys_logged" in panel
    assert "force_matrix_w.shape" in panel[panel_log:]
    assert "force_matrix_w.dtype" in panel[panel_log:]
    assert "force_matrix_w.device" in panel[panel_log:]


def test_filtered_sensor_runtime_evidence_logs_each_sensor_once():
    messages = []

    class FakeLogger:
        def info(self, message, *args):
            messages.append((message, args))

    panel_namespace = {"torch": torch, "logger": FakeLogger()}
    exec(_class_method_source("_get_a2_door_panel_contact_force_components"), panel_namespace)
    panel_method = panel_namespace["_get_a2_door_panel_contact_force_components"]

    def sensor(filter_count):
        force_matrix_w = torch.zeros((64, 1, filter_count, 3), dtype=torch.float32)
        return SimpleNamespace(
            cfg=SimpleNamespace(
                filter_prim_paths_expr=tuple(
                    f"/World/envs/env_.*/Robot/body_{index}"
                    for index in range(filter_count)
                )
            ),
            data=SimpleNamespace(force_matrix_w=force_matrix_w),
        )

    fake_self = SimpleNamespace(
        num_envs=64,
        device=torch.device("cpu"),
        _a2_runtime_evidence_sensor_keys_logged=set(),
        simulator=SimpleNamespace(
            scene=SimpleNamespace(
                sensors={
                    "a2_door_body_panel_contact_sensor": sensor(13),
                    "a2_door_arm_panel_contact_sensor": sensor(10),
                },
            )
        ),
    )
    body_filters = tuple(f"body_{index}" for index in range(13))
    arm_filters = tuple(f"body_{index}" for index in range(10))
    panel_method(
        fake_self,
        "a2_door_body_panel_contact_sensor",
        body_filters,
        "body context",
    )
    panel_method(
        fake_self,
        "a2_door_body_panel_contact_sensor",
        body_filters,
        "body context",
    )
    panel_method(
        fake_self,
        "a2_door_arm_panel_contact_sensor",
        arm_filters,
        "arm context",
    )
    panel_method(
        fake_self,
        "a2_door_arm_panel_contact_sensor",
        arm_filters,
        "arm context",
    )

    assert [args[0] for _, args in messages] == [
        "a2_door_body_panel_contact_sensor",
        "a2_door_arm_panel_contact_sensor",
    ]
    assert messages[0][1][1] == (64, 1, 13, 3)
    assert messages[1][1][1] == (64, 1, 10, 3)
    assert messages[0][1][2:] == (torch.float32, torch.device("cpu"))
    assert messages[1][1][2:] == (torch.float32, torch.device("cpu"))


def test_body_penalty_dispatch_preserves_v15_linear_and_v16_quadratic_modes():
    helper = _load_helper("a2_door_body_contact_penalty_component")
    body_total = torch.tensor([0.0, 10.0, 20.0, 40.0, 80.0])
    torch.testing.assert_close(
        helper(body_total, "linear_v15"),
        torch.tensor([0.0, 0.5, 1.0, 1.0, 1.0]),
    )
    torch.testing.assert_close(
        helper(body_total, "quadratic_v16"),
        torch.tensor([0.0, 0.0625, 0.25, 1.0, 1.0]),
    )
    with pytest.raises(ValueError):
        helper(body_total, "quadratic")


def test_posture_command_l1_clamps_raw_to_unit_domain():
    source = _class_method_source("_reward_penalty_a2_posture_command_l1")
    assert "raw_base_command[:, 3:5].clamp(-1.0, 1.0)" in source
    raw = torch.tensor(
        [
            [0.0, 0.0, 0.0, 0.4, -0.4],
            [0.0, 0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 2.0, -3.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ]
    )
    torch.testing.assert_close(
        torch.abs(raw[:, 3:5].clamp(-1.0, 1.0)).sum(dim=-1),
        torch.tensor([0.8, 2.0, 2.0, 0.0]),
    )


def test_generic_panel_scale_and_binary_dedup_limitation_are_explicit():
    panel_source = _class_method_source("_reward_penalty_door_panel_contact")
    undesired_source = _class_method_source("_reward_penalty_undesired_contact")
    assert "a2_stage35_door_panel_contact_scale" in panel_source
    assert "stage35" in panel_source
    assert "torch.cat" in undesired_source
    assert "global_mask & ~panel_mask" in undesired_source
    source = SOURCE.read_text(encoding="utf-8")
    assert "same step" in source
    assert "Vector subtraction" in source


def test_highwater_helper_false_matches_current_and_true_latches_previous_success():
    helper = _load_helper("a2_stage3_to4_hold_streak_mask")
    current = torch.tensor([False, True, False])
    latched = torch.tensor([True, False, False])
    assert helper(current, latched, True, False).tolist() == current.tolist()
    assert helper(current, latched, True, True).tolist() == [True, True, False]
    assert helper(current, latched, False, True).tolist() == [True, True, True]
    with pytest.raises(ValueError):
        helper(current, latched, True, 1)


def test_highwater_buffer_lifecycle_and_stage3_only_latch_are_explicit():
    init_source = _class_method_source("_init_buffers")
    update_source = _class_method_source("_update_a2_grasp_control_streaks")
    reset_source = _class_method_source("_reset_buffers_callback")
    transition_source = _class_method_source("_stage_3_to_4_advance_condition")
    assert "_a2_stage3_grasp_streak_highwater = torch.zeros" in init_source
    assert "dtype=torch.bool" in init_source
    assert "stage3_reached_k" in update_source
    assert "stage_buf == self.STAGE_OPEN" in update_source
    assert "stage3_highwater[reset_mask] = False" in update_source
    assert update_source.index("stage3_highwater[reset_mask] = False") < update_source.index(
        "stage3_reached_k"
    )
    assert "_a2_stage3_grasp_streak_highwater[env_ids] = False" in reset_source
    assert "a2_stage3_to4_hold_streak_mask" in transition_source
    assert "a2_stage3_to4_streak_highwater" in transition_source

    stage3_highwater = torch.tensor([True, True, False])
    reset_mask = torch.tensor([False, True, True])
    stage_buf = torch.tensor([3, 4, 3])
    updated_streak = torch.tensor([5, 0, 5])
    stage3_highwater[reset_mask] = False
    stage3_reached_k = (stage_buf == 3) & (updated_streak >= 5)
    stage3_highwater |= stage3_reached_k
    assert stage3_highwater.tolist() == [True, False, True]


def test_invalid_bool_scale_and_sensor_contracts_raise_in_source():
    source = SOURCE.read_text(encoding="utf-8")
    assert "must be bool" in source
    assert "must be finite in [0.0, 1.0]" in source
    assert "requires finite floating" in source
    assert "A2 terminal diagnostics requires finite _a2_gripper_open_target" in source


def test_m27_telemetry_and_trace_fields_are_present():
    source = SOURCE.read_text(encoding="utf-8")
    for field in (
        "a2_stage35_door_body_contact_numerator",
        "a2_stage35_door_body_force_all_sample_p50",
        "a2_stage35_door_body_force_contact_positive_p95",
        "a2_stage35_door_body_force_pooled_numerator",
        "a2_stage35_door_arm_force_pooled_numerator",
        "a2_stage35_door_panel_force_pooled_denominator",
        "a2_stage35_door_panel_force_share_valid",
        "door_body_panel_normal_force_per_filter",
        "door_body_panel_normal_force_total",
        "door_arm_panel_normal_force_per_filter",
        "door_arm_panel_normal_force_total",
        "arm_j7_j8_open_target",
    ):
        assert field in source


def test_v15_config_and_reward_values_are_exact():
    config = OmegaConf.load(V15_CONFIG)
    assert config.checkpoint.endswith("base_v14_main-20260719_103629/model_step_002000.pt")
    assert config.checkpoint_load_mode == "policy_only"
    assert config.auto_load_latest is False
    assert config.seed == 0 and config.num_envs == 1024 and config.headless is True
    assert config.algo.trl.num_total_batches == 3000
    assert config.callbacks.model_save.save_frequency == 250
    assert config.env.config.a2_stage3_to4_door_hinge_threshold == 0.25
    assert config.env.config.a2_stage3_to4_requires_grasp_streak is True
    assert config.env.config.a2_stage3_to4_streak_highwater is False
    assert config.env.config.a2_stage35_door_panel_contact_scale == 0.0
    assert config.rewards.reward_scales.penalty_a2_door_body_contact == -0.3
    assert config.robot.control.stiffness.arm_j7 == 800.0
    assert config.robot.control.damping.arm_j8 == 25.0
    assert config.simulator.config.sim.physx.num_velocity_iterations == 2
    reward = OmegaConf.load(REWARD_CONFIG)
    assert reward.rewards.reward_scales.penalty_a2_door_body_contact == 0.0
