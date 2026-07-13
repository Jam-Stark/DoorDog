import ast
import json
import math
from collections import Counter
from pathlib import Path
import textwrap

import torch
import numpy as np
from omegaconf import OmegaConf


SOURCE_PATH = Path(__file__).parents[1] / "envs/door/door_open_a2_base.py"
EVAL_SOURCE_PATH = Path(__file__).parents[1] / "eval_agent_trl.py"
TRAINER_SOURCE_PATH = Path(__file__).parents[1] / "trl/trainer/ppo_trainer_a2_base_api.py"


def _quat_inv(quat):
    result = quat.clone()
    result[..., 1:] *= -1.0
    return result


def _matrix_from_quat(quat):
    # The tests only need identity rotation; fail instead of silently handling more.
    expected = torch.zeros_like(quat)
    expected[..., 0] = 1.0
    if not torch.equal(quat, expected):
        raise AssertionError("no-sim helper test expected identity quaternion")
    return torch.eye(3, dtype=quat.dtype).expand(quat.shape[0], -1, -1).clone()


def _skew(vector):
    result = torch.zeros(vector.shape[0], 3, 3, dtype=vector.dtype)
    x, y, z = vector.unbind(-1)
    result[:, 0, 1] = -z
    result[:, 0, 2] = y
    result[:, 1, 0] = z
    result[:, 1, 2] = -x
    result[:, 2, 0] = -y
    result[:, 2, 1] = x
    return result


def _quat_mul(q1, q2):
    w1, x1, y1, z1 = q1.unbind(-1)
    w2, x2, y2, z2 = q2.unbind(-1)
    return torch.stack(
        (
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ),
        dim=-1,
    )


def _quat_apply(quat, vector):
    quat_vector = quat[..., 1:]
    uv = torch.cross(quat_vector, vector, dim=-1)
    uuv = torch.cross(quat_vector, uv, dim=-1)
    return vector + 2.0 * (quat[..., :1] * uv + uuv)


def _quat_apply_inverse(quat, vector):
    return _quat_apply(_quat_inv(quat), vector)


def _yaw_quat(quat):
    yaw = torch.atan2(
        2.0 * (quat[:, 0] * quat[:, 3] + quat[:, 1] * quat[:, 2]),
        1.0 - 2.0 * (quat[:, 2].square() + quat[:, 3].square()),
    )
    result = torch.zeros_like(quat)
    result[:, 0] = torch.cos(0.5 * yaw)
    result[:, 3] = torch.sin(0.5 * yaw)
    return result


def _subtract_frame_transforms(pos_a, quat_a, pos_b, quat_b):
    quat_a_inverse = _quat_inv(quat_a)
    return (
        _quat_apply(quat_a_inverse, pos_b - pos_a),
        _quat_mul(quat_a_inverse, quat_b),
    )


def _combine_frame_transforms(pos_a, quat_a, pos_b, quat_b):
    return pos_a + _quat_apply(quat_a, pos_b), _quat_mul(quat_a, quat_b)


def _compute_pose_error(current_pos, current_quat, final_pos, final_quat, rot_error_type):
    assert rot_error_type == "axis_angle"
    relative = _quat_mul(final_quat, _quat_inv(current_quat))
    relative = torch.where(relative[:, :1] < 0.0, -relative, relative)
    angle = 2.0 * torch.acos(relative[:, 0].clamp(-1.0, 1.0))
    sin_half = torch.sin(0.5 * angle)
    axis = torch.zeros_like(relative[:, 1:])
    valid = sin_half.abs() > 1.0e-7
    axis[valid] = relative[valid, 1:] / sin_half[valid, None]
    return final_pos - current_pos, axis * angle[:, None]


def _apply_delta_pose(current_pos, current_quat, delta):
    rotation = delta[:, 3:]
    angle = torch.linalg.norm(rotation, dim=-1)
    axis = torch.zeros_like(rotation)
    valid = angle > 1.0e-7
    axis[valid] = rotation[valid] / angle[valid, None]
    delta_quat = torch.zeros(current_quat.shape, dtype=current_quat.dtype)
    delta_quat[:, 0] = torch.cos(0.5 * angle)
    delta_quat[:, 1:] = axis * torch.sin(0.5 * angle)[:, None]
    return current_pos + delta[:, :3], _quat_mul(delta_quat, current_quat)


def _load_no_sim_helpers():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    helper_names = {
        "a2_hold_absolute_target_to_cumulative_action",
        "a2_hold_bound_pose_command_step",
        "a2_hold_action_with_exact_disabled_equivalence",
        "a2_hold_aggregate_normal_force_direction",
        "a2_hold_apply_source_offset_to_jacobian",
        "a2_hold_apply_oracle_branch_actions",
        "a2_hold_base_relief_branch_masks",
        "a2_hold_base_relief_command",
        "a2_hold_capture_handoff_relative_orientation",
        "a2_hold_center_converged",
        "a2_hold_center_transition_masks",
        "a2_hold_clear_base_relief_state",
        "a2_hold_compose_handoff_target_orientation",
        "a2_hold_contact_sensor_detail_kwargs",
        "a2_hold_depress_timeout_mask",
        "a2_hold_depress_transition_mask",
        "a2_hold_nullable_tensor_list",
        "a2_hold_map_task_to_articulation_joint_ids",
        "a2_hold_pd_effort_estimates",
        "a2_hold_positive_sign_pass",
        "a2_hold_progress_aware_joint_limit_masks",
        "a2_hold_push_timeout_masks",
        "a2_hold_rotate_jacobian_to_root",
        "a2_hold_summarize_outcomes",
        "a2_hold_signed_gripper_opening_axes_from_jacobian",
        "a2_hold_project_finger_forces_along_opening_axes",
        "a2_hold_static_clamp_step_masks",
        "a2_hold_static_clamp_terminal_partition",
        "a2_hold_apply_static_clamp_action",
        "a2_hold_offset_fixed_world_target",
        "a2_hold_validate_offset_axis_opening_dots",
        "a2_hold_offset_placement_step_masks",
        "a2_hold_offset_terminal_partition",
        "a2_hold_apply_offset_placement_action",
        "a2_hold_offset_endpoint_metrics",
        "a2_hold_target_orientation_semantic",
        "a2_hold_update_base_relief_state",
        "a2_hold_update_phase_arm_sign_check",
        "a2_hold_validate_friction_override",
        "a2_hold_quaternion_geodesic_rad",
        "a2_hold_pose_motion_metrics",
        "a2_hold_open_stabilization_action",
        "a2_hold_open_stabilization_terminal_partition",
        "a2_hold_validate_open_stabilization_runtime_invariants",
        "a2_hold_matched_clean_release_action",
        "a2_hold_matched_clean_release_qualification",
        "a2_hold_matched_clean_release_step_masks",
        "a2_hold_matched_clean_stabilization_terminal_partition",
    }
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id.startswith("A2_HOLD_")
            for target in node.targets
        ):
            nodes.append(node)
        if isinstance(node, ast.FunctionDef) and node.name in helper_names:
            nodes.append(node)
    namespace = {
        "torch": torch,
        "math": math,
        "Counter": Counter,
        "quat_inv": _quat_inv,
        "matrix_from_quat": _matrix_from_quat,
        "skew_symmetric_matrix": _skew,
        "compute_pose_error": _compute_pose_error,
        "apply_delta_pose": _apply_delta_pose,
        "subtract_frame_transforms": _subtract_frame_transforms,
        "combine_frame_transforms": _combine_frame_transforms,
        "quat_apply_inverse": _quat_apply_inverse,
        "quat_apply": _quat_apply,
        "yaw_quat": _yaw_quat,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE_PATH), "exec"), namespace)
    door_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp")
    parse_method = next(
        node for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_parse_a2_hold_oracle_config"
    )
    parse_source = textwrap.dedent(ast.get_source_segment(source, parse_method))
    exec(parse_source, namespace)
    namespace["parse_a2_hold_oracle_config"] = namespace.pop("_parse_a2_hold_oracle_config")
    return namespace


globals().update(_load_no_sim_helpers())


def _load_eval_migration():
    source = EVAL_SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name)
            and target.id == "_A2_HOLD_DIAGNOSTIC_ENV_CONFIG_DEFAULTS"
            for target in node.targets
        ):
            nodes.append(node)
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "migrate_legacy_a2_hold_diagnostic_env_config"
        ):
            nodes.append(node)

    class _Logger:
        def info(self, *args, **kwargs):
            return None

    namespace = {"OmegaConf": OmegaConf, "logger": _Logger()}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(EVAL_SOURCE_PATH), "exec"), namespace)
    return namespace


EVAL_MIGRATION = _load_eval_migration()


def _load_json_sanitizer():
    source = TRAINER_SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_make_json_safe"
    )
    namespace = {"torch": torch, "np": np, "math": math}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(TRAINER_SOURCE_PATH), "exec"), namespace)
    return namespace["_make_json_safe"]


MAKE_JSON_SAFE = _load_json_sanitizer()


def _valid_oracle_config(enabled=True):
    return {
        "a2_hold_oracle_enabled": enabled,
        "a2_hold_oracle_center_timeout_steps": 80,
        "a2_hold_oracle_center_position_tolerance_m": 0.005,
        "a2_hold_oracle_center_orientation_tolerance_rad": 0.10,
        "a2_hold_oracle_depress_timeout_steps": 100,
        "a2_hold_oracle_push_timeout_steps": 150,
        "a2_hold_oracle_depress_offset_m": 0.012,
        "a2_hold_oracle_push_offset_m": 0.012,
        "a2_hold_oracle_offset_ramp_steps": 20,
        "a2_hold_oracle_sign_smoke_steps": 10,
        "a2_hold_oracle_sign_min_delta": 0.005,
        "a2_hold_oracle_handle_target_rad": 0.50,
        "a2_hold_oracle_hinge_progress_target_rad": 0.20,
        "a2_hold_oracle_contact_slip_grace_steps": 5,
        "a2_hold_oracle_dls_lambda": 0.01,
        "a2_hold_oracle_max_position_step_m": 0.002,
        "a2_hold_oracle_max_orientation_step_rad": 0.02,
        "a2_hold_oracle_jacobian_condition_max": 1.0e6,
        "a2_hold_oracle_joint_limit_margin": 1.0e-4,
        "a2_hold_oracle_soft_limit_progress_tolerance": 1.0e-6,
        "a2_hold_oracle_raw_action_abs_max": 10.0,
        "a2_hold_oracle_base_relief_speed_mps": 0.15,
        "a2_hold_oracle_base_relief_sign_window_steps": 20,
        "a2_hold_oracle_base_relief_min_residual_decrease_m": 0.001,
        "a2_hold_oracle_base_relief_timeout_steps": 60,
        "a2_hold_oracle_base_relief_max_displacement_m": 0.10,
        "a2_hold_oracle_base_relief_min_solvable_horizontal_error_m": 0.002,
        "a2_hold_oracle_static_clamp_enabled": False,
        "a2_hold_oracle_static_clamp_steps": 40,
        "a2_hold_oracle_static_clamp_stiffness": 80.0,
        "a2_hold_oracle_static_clamp_damping": 3.0,
        "a2_hold_oracle_static_clamp_offset_probe_enabled": False,
        "a2_hold_oracle_static_clamp_offset_m": 0.0,
        "a2_hold_oracle_static_clamp_offset_placement_steps": 20,
        "a2_hold_oracle_static_clamp_offset_position_tolerance_m": 0.0005,
        "a2_hold_oracle_static_clamp_offset_orientation_tolerance_rad": 0.02,
        "a2_hold_oracle_open_stabilization_preflight_enabled": False,
        "a2_hold_oracle_open_stabilization_steps": 40,
        "a2_hold_oracle_open_stabilization_quiet_window_steps": 5,
        "a2_hold_oracle_open_stabilization_root_linear_speed_max_mps": 0.01,
        "a2_hold_oracle_open_stabilization_root_angular_speed_max_radps": 0.02,
        "a2_hold_oracle_open_stabilization_pose_per_call_translation_max_m": 0.0005,
        "a2_hold_oracle_open_stabilization_pose_per_call_rotation_max_rad": 0.0005,
        "a2_hold_oracle_open_stabilization_pose_window_translation_max_m": 0.001,
        "a2_hold_oracle_open_stabilization_pose_window_rotation_max_rad": 0.002,
        "a2_hold_oracle_open_stabilization_contact_force_max_n": 1.0,
        "a2_hold_oracle_matched_clean_reacquisition_preflight_enabled": False,
        "a2_hold_oracle_matched_clean_retreat_timeout_steps": 80,
        "a2_hold_oracle_matched_clean_release_qualification_steps": 5,
        "a2_hold_oracle_matched_clean_pregrasp_position_tolerance_m": 0.005,
        "a2_hold_oracle_matched_clean_pregrasp_orientation_tolerance_rad": 0.10,
    }


def test_oracle_config_and_measured_midpoint_name():
    cfg = parse_a2_hold_oracle_config(_valid_oracle_config())
    assert cfg["enabled"] is True
    assert "tcp_offset_z" not in cfg
    env_yaml = (Path(__file__).parents[1] / "config/env/door_open_a2_base.yaml").read_text()
    assert "a2_gripper_source_tcp_offset_z: 0.085" in env_yaml
    assert "a2_hold_oracle_tcp_offset_z" not in (
        Path(__file__).parents[1] / "config/base_eval.yaml"
    ).read_text()
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert 'cfg["tcp_offset_z"] = self._get_a2_gripper_source_tcp_offset_z()' in source
    bad = _valid_oracle_config()
    bad["a2_hold_oracle_sign_smoke_steps"] = 100
    try:
        parse_a2_hold_oracle_config(bad)
    except RuntimeError as exc:
        assert "sign-smoke" in str(exc)
    else:
        raise AssertionError("invalid sign-smoke/timeout combination did not fail")
    for key in (
        "a2_hold_oracle_max_position_step_m",
        "a2_hold_oracle_max_orientation_step_rad",
        "a2_hold_oracle_soft_limit_progress_tolerance",
    ):
        invalid = _valid_oracle_config()
        invalid[key] = 0.0
        try:
            parse_a2_hold_oracle_config(invalid)
        except RuntimeError as exc:
            assert key in str(exc)
        else:
            raise AssertionError(f"invalid {key} did not fail")


def test_pose_step_clamp_position_rotation_zero_and_batch():
    current_pos = torch.zeros(3, 3)
    current_quat = torch.tensor([[1.0, 0.0, 0.0, 0.0]]).repeat(3, 1)
    final_pos = torch.tensor([[0.01, 0.0, 0.0], [0.001, 0.0, 0.0], [0.0, 0.0, 0.0]])
    half = 0.05
    final_quat = torch.stack(
        (
            torch.tensor([math.cos(half), 0.0, 0.0, math.sin(half)]),
            torch.tensor([1.0, 0.0, 0.0, 0.0]),
            torch.tensor([1.0, 0.0, 0.0, 0.0]),
        )
    )
    command_pos, command_quat, final_pos_res, final_rot_res, delta = (
        a2_hold_bound_pose_command_step(
            current_pos,
            current_quat,
            final_pos,
            final_quat,
            0.002,
            0.02,
        )
    )
    torch.testing.assert_close(command_pos[0], torch.tensor([0.002, 0.0, 0.0]))
    torch.testing.assert_close(command_pos[1], final_pos[1])
    torch.testing.assert_close(command_pos[2], current_pos[2])
    torch.testing.assert_close(torch.linalg.norm(delta[:, :3], dim=-1), torch.tensor([0.002, 0.001, 0.0]))
    torch.testing.assert_close(torch.linalg.norm(delta[:, 3:], dim=-1), torch.tensor([0.02, 0.0, 0.0]), atol=1.0e-6, rtol=0.0)
    torch.testing.assert_close(final_pos_res, torch.tensor([0.01, 0.001, 0.0]))
    torch.testing.assert_close(final_rot_res, torch.tensor([0.10, 0.0, 0.0]), atol=1.0e-6, rtol=0.0)
    assert command_quat.shape == (3, 4)


def test_handoff_orientation_capture_follow_and_batch_isolation():
    handle_pos = torch.zeros(3, 3)
    handle_quat = torch.tensor([[1.0, 0.0, 0.0, 0.0]]).repeat(3, 1)
    source_pos = torch.tensor([[0.1, 0.0, 0.0], [0.0, 0.1, 0.0], [0.0, 0.0, 0.1]])
    source_quat = torch.tensor(
        [
            [math.cos(0.15), 0.0, 0.0, math.sin(0.15)],
            [1.0, 0.0, 0.0, 0.0],
            [math.cos(0.10), math.sin(0.10), 0.0, 0.0],
        ]
    )
    capture = torch.tensor([True, False, True])
    relative_state = torch.full((3, 4), float("nan"))
    captured = torch.zeros(3, dtype=torch.bool)
    relative_state, captured = a2_hold_capture_handoff_relative_orientation(
        handle_pos,
        handle_quat,
        source_pos,
        source_quat,
        capture,
        relative_state,
        captured,
    )
    assert captured.tolist() == [True, False, True]
    assert torch.isnan(relative_state[1]).all()
    assert a2_hold_nullable_tensor_list(relative_state[1]) == [None, None, None, None]

    activation_target = a2_hold_compose_handoff_target_orientation(
        handle_pos,
        handle_quat,
        source_quat,
        relative_state,
        capture,
        captured,
    )
    torch.testing.assert_close(activation_target, source_quat)

    rotated_handle_quat = handle_quat.clone()
    rotated_handle_quat[0] = torch.tensor(
        [math.cos(0.20), 0.0, math.sin(0.20), 0.0]
    )
    followed_target = a2_hold_compose_handoff_target_orientation(
        handle_pos,
        rotated_handle_quat,
        source_quat,
        relative_state,
        capture,
        captured,
    )
    _, followed_relative = _subtract_frame_transforms(
        handle_pos[capture],
        rotated_handle_quat[capture],
        handle_pos[capture],
        followed_target[capture],
    )
    torch.testing.assert_close(followed_relative, relative_state[capture])
    torch.testing.assert_close(followed_target[1], source_quat[1])
    torch.testing.assert_close(followed_target[2], source_quat[2])


def test_handoff_orientation_contracts_fail_fast_and_are_wired():
    pos = torch.zeros(2, 3)
    quat = torch.tensor([[1.0, 0.0, 0.0, 0.0]]).repeat(2, 1)
    relative_state = torch.full((2, 4), float("nan"))
    inactive = torch.zeros(2, dtype=torch.bool)
    uncaptured_active = torch.tensor([True, False])
    try:
        a2_hold_compose_handoff_target_orientation(
            pos, quat, quat, relative_state, uncaptured_active, inactive
        )
    except ValueError as exc:
        assert "before relative orientation capture" in str(exc)
    else:
        raise AssertionError("active uncaptured handoff target did not fail")

    try:
        a2_hold_capture_handoff_relative_orientation(
            pos,
            quat.to(torch.float64),
            pos,
            quat,
            inactive,
            relative_state,
            inactive,
        )
    except ValueError as exc:
        assert "common floating dtype" in str(exc)
    else:
        raise AssertionError("handoff capture mixed dtype did not fail")

    try:
        a2_hold_compose_handoff_target_orientation(
            pos[:, :2], quat, quat, relative_state, inactive, inactive
        )
    except ValueError as exc:
        assert "incompatible shapes" in str(exc)
    else:
        raise AssertionError("handoff target invalid shape did not fail")

    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "handoff capture inputs must be on one common device" in source
    assert "handoff target inputs must be on one common device" in source
    assert "a2_hold_capture_handoff_relative_orientation(" in source
    assert "self._a2_hold_oracle_handoff_orientation_captured" in source
    assert '"hold_oracle_target_orientation_semantic"' in source
    assert '"hold_oracle_handoff_orientation_captured"' in source
    assert '"hold_oracle_handoff_handle_to_gripper_relative_quat_wxyz"' in source
    assert A2_HOLD_TARGET_ORIENTATION_SEMANTIC == (
        "handle_orientation_composed_with_handoff_handle_to_gripper_relative_orientation"
    )


def test_pose_and_joint_limit_helpers_reject_mixed_dtypes():
    pos = torch.zeros(1, 3)
    quat = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    try:
        a2_hold_bound_pose_command_step(
            pos,
            quat.to(torch.float64),
            pos,
            quat,
            0.002,
            0.02,
        )
    except ValueError as exc:
        assert "common floating dtype" in str(exc)
    else:
        raise AssertionError("pose-step mixed dtype did not fail")

    current = torch.zeros(1, 1)
    desired = torch.zeros(1, 1, dtype=torch.float64)
    limits = torch.tensor([[[-1.0, 1.0]]])
    try:
        a2_hold_progress_aware_joint_limit_masks(
            current, desired, limits, limits, 1.0e-4, 1.0e-4, 1.0e-6
        )
    except ValueError as exc:
        assert "common floating dtype" in str(exc)
    else:
        raise AssertionError("joint-limit mixed dtype did not fail")


def test_progress_aware_soft_limits_and_hard_violation():
    current = torch.tensor(
        [
            [0.0],    # inside
            [1.01],   # above soft, moves inward
            [1.01],   # above soft, moves outward
            [1.01],   # above soft, outward only within tolerance
            [-1.01],  # below soft, moves inward
            [-1.01],  # below soft, moves outward
            [-1.01],  # below soft, outward only within tolerance
            [-1.01],  # below soft, overshoots beyond upper soft bound
            [1.01],   # above soft, overshoots beyond lower soft bound
            [0.0],    # desired is inside raw hard range but violates its margin
        ]
    )
    desired = torch.tensor(
        [
            [0.5],
            [1.00],
            [1.02],
            [1.0100005],
            [-1.00],
            [-1.02],
            [-1.0100005],
            [1.10],
            [-1.10],
            [1.99995],
        ]
    )
    hard = torch.tensor([[[-2.0, 2.0]]]).repeat(10, 1, 1)
    soft = torch.tensor([[[-1.0, 1.0]]]).repeat(10, 1, 1)
    valid, hard_valid, soft_valid = a2_hold_progress_aware_joint_limit_masks(
        current, desired, hard, soft, 1.0e-4, 1.0e-4, 1.0e-6
    )
    assert valid.tolist() == [True, True, False, True, True, False, True, False, False, False]
    assert hard_valid.tolist() == [True, True, True, True, True, True, True, True, True, False]
    assert soft_valid.tolist() == [True, True, False, True, True, False, True, False, False, False]


def test_base_relief_world_to_yaw_body_speed_backmap_and_zero_rejection():
    horizontal_error_w = torch.tensor([[3.0, 4.0], [1.0, 0.0], [0.0, 0.0]])
    root_quat_w = torch.tensor(
        [
            [1.0, 0.0, 0.0, 0.0],
            [math.cos(math.pi / 4.0), 0.0, 0.0, math.sin(math.pi / 4.0)],
            [1.0, 0.0, 0.0, 0.0],
        ]
    )
    candidate = torch.ones(3, dtype=torch.bool)
    residual, solvable, body_velocity, raw = a2_hold_base_relief_command(
        horizontal_error_w,
        root_quat_w,
        candidate,
        0.15,
        0.25,
        0.002,
    )
    torch.testing.assert_close(residual, torch.tensor([5.0, 1.0, 0.0]))
    assert solvable.tolist() == [True, True, False]
    torch.testing.assert_close(body_velocity[0], torch.tensor([0.09, 0.12]), atol=1e-6, rtol=0.0)
    torch.testing.assert_close(body_velocity[1], torch.tensor([0.0, -0.15]), atol=1e-6, rtol=0.0)
    torch.testing.assert_close(raw[0], torch.tensor([0.36, 0.48, 0.0, 0.0, 0.0]), atol=1e-6, rtol=0.0)
    torch.testing.assert_close(raw[1], torch.tensor([0.0, -0.6, 0.0, 0.0, 0.0]), atol=1e-6, rtol=0.0)
    torch.testing.assert_close(raw[2], torch.zeros(5))


def test_base_relief_branch_masks_and_exact_action_chain():
    active = torch.ones(5, dtype=torch.bool)
    ik = torch.tensor([True, True, False, True, True])
    limit = torch.tensor([True, False, True, False, True])
    delta = torch.tensor([True, True, True, True, False])
    raw_valid = torch.ones(5, dtype=torch.bool)
    solvable = torch.tensor([True, True, True, False, True])
    arm, relief, ik_invalid, joint_limit, action_invalid = a2_hold_base_relief_branch_masks(
        active, ik, limit, delta, raw_valid, solvable
    )
    assert arm.tolist() == [True, False, False, False, False]
    assert relief.tolist() == [False, True, False, False, False]
    assert ik_invalid.tolist() == [False, False, True, False, False]
    assert joint_limit.tolist() == [False, False, False, True, False]
    assert action_invalid.tolist() == [False, False, False, False, True]

    action = torch.arange(60, dtype=torch.float32).reshape(5, 12)
    arm_raw = torch.full((5, 6), 0.3)
    base_raw = torch.zeros(5, 5)
    base_raw[:, :2] = torch.tensor([0.6, -0.2])
    result, override = a2_hold_apply_oracle_branch_actions(
        action, arm, relief, arm_raw, base_raw, (0, 5), (5, 11), 11
    )
    assert override.tolist() == [True, True, False, False, False]
    torch.testing.assert_close(result[0, :5], torch.zeros(5))
    torch.testing.assert_close(result[0, 5:11], arm_raw[0])
    torch.testing.assert_close(result[1, :5], base_raw[1])
    torch.testing.assert_close(result[1, 5:11], torch.zeros(6))
    assert result[0, 11].item() == -1.0 and result[1, 11].item() == -1.0
    torch.testing.assert_close(result[2:], action[2:])


def test_base_relief_state_start_clear_and_failure_masks():
    relief = torch.tensor([True, False])
    previous_active = torch.zeros(2, dtype=torch.bool)
    previous_steps = torch.zeros(2, dtype=torch.long)
    previous_initial = torch.full((2,), float("nan"))
    previous_start = torch.full((2, 2), float("nan"))
    current_residual = torch.tensor([0.10, 0.20])
    current_root = torch.tensor([[0.0, 0.0], [1.0, 1.0]])
    entered = a2_hold_update_base_relief_state(
        relief,
        previous_active,
        previous_steps,
        previous_initial,
        previous_start,
        current_residual,
        current_root,
        20,
        0.001,
        60,
        0.10,
    )
    assert entered["entered"].tolist() == [True, False]
    assert entered["active"].tolist() == [True, False]
    assert entered["steps"].tolist() == [0, 0]
    assert torch.isnan(entered["initial_residual"][1])

    wrong_sign = a2_hold_update_base_relief_state(
        relief,
        entered["active"],
        torch.tensor([19, 0]),
        entered["initial_residual"],
        entered["start_root_xy"],
        torch.tensor([0.10, 0.20]),
        current_root,
        20,
        0.001,
        60,
        0.10,
    )
    assert wrong_sign["wrong_sign"].tolist() == [True, False]

    timeout = a2_hold_update_base_relief_state(
        relief,
        entered["active"],
        torch.tensor([59, 0]),
        entered["initial_residual"],
        entered["start_root_xy"],
        torch.tensor([0.08, 0.20]),
        current_root,
        20,
        0.001,
        60,
        0.10,
    )
    assert timeout["timeout"].tolist() == [True, False]

    displacement = a2_hold_update_base_relief_state(
        relief,
        entered["active"],
        entered["steps"],
        entered["initial_residual"],
        entered["start_root_xy"],
        torch.tensor([0.08, 0.20]),
        torch.tensor([[0.11, 0.0], [1.0, 1.0]]),
        20,
        0.001,
        60,
        0.10,
    )
    assert displacement["displacement_limit"].tolist() == [True, False]

    cleared = a2_hold_update_base_relief_state(
        torch.zeros(2, dtype=torch.bool),
        entered["active"],
        entered["steps"],
        entered["initial_residual"],
        entered["start_root_xy"],
        current_residual,
        current_root,
        20,
        0.001,
        60,
        0.10,
    )
    assert cleared["cleared"].tolist() == [True, False]
    assert not cleared["active"].any()
    assert torch.isnan(cleared["initial_residual"]).all()


def test_base_relief_terminal_clear_single_mixed_batch_parity_and_next_call():
    single = a2_hold_clear_base_relief_state(
        torch.tensor([True]),
        torch.tensor([True]),
        torch.tensor([True]),
        torch.tensor([20]),
        torch.tensor([0.10]),
        torch.tensor([0.11]),
        torch.tensor([[0.0, 0.0]]),
        torch.tensor([[0.15, 0.0]]),
        torch.tensor([[0.6, 0.0, 0.0, 0.0, 0.0]]),
    )
    assert single["active"].tolist() == [False]
    assert single["branch_applied"].tolist() == [False]
    assert single["steps"].tolist() == [0]
    assert torch.isnan(single["initial_residual"]).all()
    assert torch.isnan(single["current_residual"]).all()
    assert torch.isnan(single["start_root_xy"]).all()
    torch.testing.assert_close(single["body_velocity_command"], torch.zeros(1, 2))
    torch.testing.assert_close(single["raw_command"], torch.zeros(1, 5))

    next_call = a2_hold_clear_base_relief_state(
        torch.tensor([True]),
        single["active"],
        single["branch_applied"],
        single["steps"],
        single["initial_residual"],
        single["current_residual"],
        single["start_root_xy"],
        single["body_velocity_command"],
        single["raw_command"],
    )
    assert next_call["active"].tolist() == [False]
    assert torch.isnan(next_call["initial_residual"]).all()

    mixed = a2_hold_clear_base_relief_state(
        torch.tensor([True, False]),
        torch.tensor([True, True]),
        torch.tensor([True, True]),
        torch.tensor([20, 3]),
        torch.tensor([0.10, 0.20]),
        torch.tensor([0.11, 0.18]),
        torch.tensor([[0.0, 0.0], [1.0, 1.0]]),
        torch.tensor([[0.15, 0.0], [0.0, 0.15]]),
        torch.tensor([[0.6, 0.0, 0.0, 0.0, 0.0], [0.0, 0.6, 0.0, 0.0, 0.0]]),
    )
    for key in (
        "active",
        "branch_applied",
        "steps",
        "initial_residual",
        "current_residual",
        "start_root_xy",
        "body_velocity_command",
        "raw_command",
    ):
        torch.testing.assert_close(mixed[key][0], single[key][0], equal_nan=True)
    assert mixed["active"][1].item()
    assert mixed["steps"][1].item() == 3
    torch.testing.assert_close(mixed["raw_command"][1], torch.tensor([0.0, 0.6, 0.0, 0.0, 0.0]))


def test_base_relief_clear_and_clip_contract_runtime_source_wiring():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "self._clear_a2_hold_base_relief_state(relief_failure)" in source
    assert "self._clear_a2_hold_base_relief_state(torch.ones_like(active))" in source
    assert 'result["active"][clear_mask] = False' in source
    assert 'result["steps"][clear_mask] = 0' in source
    assert 'result["current_residual"][clear_mask] = float("nan")' in source
    assert 'result["raw_command"][clear_mask] = 0.0' in source
    assert "if self._clip_homie_command:" in source
    assert 'cfg["base_relief_speed_mps"] > clip_x' in source
    assert 'cfg["base_relief_speed_mps"] > clip_y' in source
    eval_yaml = (Path(__file__).parents[1] / "config/base_eval.yaml").read_text()
    env_yaml = (
        Path(__file__).parents[1] / "config/env/door_open_a2_base.yaml"
    ).read_text()
    assert "a2_hold_oracle_base_relief_speed_mps: 0.15" in eval_yaml
    assert "clip_homie_linvel_x_threshold: 0.5" in env_yaml
    assert "clip_homie_linvel_y_threshold: 0.5" in env_yaml


def test_base_relief_config_and_trace_wiring():
    cfg = parse_a2_hold_oracle_config(_valid_oracle_config())
    assert cfg["base_relief_speed_mps"] == 0.15
    assert cfg["base_relief_sign_window_steps"] == 20
    assert cfg["base_relief_timeout_steps"] == 60
    invalid = _valid_oracle_config()
    invalid["a2_hold_oracle_base_relief_timeout_steps"] = 20
    try:
        parse_a2_hold_oracle_config(invalid)
    except RuntimeError as exc:
        assert "base-relief sign window" in str(exc)
    else:
        raise AssertionError("invalid base-relief sign/timeout ordering did not fail")
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "self._k != 0 or self._s != 0" in source
    assert "self._a2_base_command_scale" in source
    assert "a2_hold_base_relief_branch_masks(" in source
    assert "a2_hold_update_base_relief_state(" in source
    assert '"hold_oracle_base_relief_raw_command"' in source
    assert '"hold_oracle_base_relief_body_velocity_command"' in source
    assert '"hold_oracle_base_relief_phase_timeout_semantic"' in source


def test_signed_gripper_opening_axes_and_force_on_finger_projection():
    jacobian = torch.zeros(2, 2, 6, 10)
    # arm_j7 and arm_j8 articulation ids 1/2 map to floating columns 7/8.
    jacobian[:, 0, 1, 7] = 2.0
    jacobian[:, 1, 1, 8] = 3.0
    axes = a2_hold_signed_gripper_opening_axes_from_jacobian(
        jacobian,
        torch.tensor([0, 1]),
        torch.tensor([1, 2]),
        torch.tensor([0.035, -0.035]),
        torch.tensor([0.0, 0.0]),
    )
    expected = torch.tensor([[[0.0, 1.0, 0.0], [0.0, -1.0, 0.0]]]).repeat(2, 1, 1)
    torch.testing.assert_close(axes, expected)

    # Sensor force acts on the handle. Negating it gives force on the finger.
    normal_on_handle = torch.tensor(
        [[[-0.0, -4.0, 0.0], [0.0, 5.0, 0.0]]] * 2
    )
    friction_on_handle = torch.tensor(
        [[[0.0, -1.0, 0.0], [0.0, 2.0, 0.0]]] * 2
    )
    projection = a2_hold_project_finger_forces_along_opening_axes(
        normal_on_handle, friction_on_handle, axes
    )
    torch.testing.assert_close(
        projection["finger_normal_force_along_opening_axis"],
        torch.tensor([[4.0, 5.0], [4.0, 5.0]]),
    )
    torch.testing.assert_close(
        projection["finger_friction_force_along_opening_axis"],
        torch.tensor([[1.0, 2.0], [1.0, 2.0]]),
    )
    torch.testing.assert_close(
        projection["finger_total_force_along_opening_axis"],
        torch.tensor([[5.0, 7.0], [5.0, 7.0]]),
    )


def test_signed_gripper_opening_axes_fail_fast_degenerate_angular_and_sign():
    base = torch.zeros(1, 2, 6, 10)
    body_ids = torch.tensor([0, 1])
    joint_ids = torch.tensor([1, 2])
    open_target = torch.tensor([0.035, -0.035])
    close_target = torch.zeros(2)
    for expected_message, mutation in (
        ("degenerate", lambda value: value),
        (
            "not prismatic",
            lambda value: value.index_put_((torch.tensor([0]), torch.tensor([0]), torch.tensor([0]), torch.tensor([7])), torch.tensor([1.0])).index_put_((torch.tensor([0]), torch.tensor([1]), torch.tensor([0]), torch.tensor([8])), torch.tensor([1.0])).index_put_((torch.tensor([0]), torch.tensor([1]), torch.tensor([3]), torch.tensor([8])), torch.tensor([0.01])),
        ),
    ):
        jacobian = mutation(base.clone())
        try:
            a2_hold_signed_gripper_opening_axes_from_jacobian(
                jacobian, body_ids, joint_ids, open_target, close_target
            )
        except ValueError as exc:
            assert expected_message in str(exc)
        else:
            raise AssertionError(f"opening-axis {expected_message} input did not fail")

    valid = base.clone()
    valid[:, 0, 0, 7] = 1.0
    valid[:, 1, 0, 8] = 1.0
    try:
        a2_hold_signed_gripper_opening_axes_from_jacobian(
            valid, body_ids, joint_ids, torch.tensor([0.0, -0.035]), close_target
        )
    except ValueError as exc:
        assert "non-zero" in str(exc)
    else:
        raise AssertionError("zero open-close displacement did not fail")
    for reversed_target in (
        torch.tensor([-0.035, -0.035]),
        torch.tensor([0.035, 0.035]),
        torch.tensor([-0.035, 0.035]),
    ):
        try:
            a2_hold_signed_gripper_opening_axes_from_jacobian(
                valid, body_ids, joint_ids, reversed_target, close_target
            )
        except ValueError as exc:
            assert "arm_j7 positive and arm_j8 negative" in str(exc)
        else:
            raise AssertionError("reversed opening-axis signs did not fail")


def test_static_clamp_exact_40_action_writes_and_41st_restore_boundary():
    active = torch.zeros(1, dtype=torch.bool)
    count = torch.zeros(1, dtype=torch.long)
    first_active = torch.ones(1, dtype=torch.bool)
    states = []
    for call_index in range(41):
        state = a2_hold_static_clamp_step_masks(
            True,
            torch.tensor([call_index == 0]),
            first_active,
            active,
            count,
            40,
        )
        states.append(state)
        active = state["active"]
        count = state["write_count"]
    assert sum(state["override"].item() for state in states) == 40
    assert states[0]["entering"].item()
    assert states[39]["override"].item()
    assert states[39]["write_count"].item() == 40
    assert not states[40]["override"].item()
    assert states[40]["complete"].item()
    assert not states[40]["active"].item()
    assert states[40]["write_count"].item() == 40

    policy = torch.arange(24, dtype=torch.float32).reshape(2, 12)
    overridden = a2_hold_apply_static_clamp_action(
        policy, torch.tensor([True, False])
    )
    torch.testing.assert_close(overridden[0, :11], torch.zeros(11))
    assert overridden[0, 11].item() == -1.0
    torch.testing.assert_close(overridden[1], policy[1])
    disabled = a2_hold_apply_static_clamp_action(
        policy, torch.zeros(2, dtype=torch.bool)
    )
    assert disabled is policy


def test_static_clamp_early_end_disabled_noop_and_config_fail_fast():
    active = torch.tensor([True, False])
    count = torch.tensor([7, 0], dtype=torch.long)
    state = a2_hold_static_clamp_step_masks(
        True,
        torch.zeros(2, dtype=torch.bool),
        torch.tensor([False, True]),
        active,
        count,
        40,
    )
    assert state["incomplete"].tolist() == [True, False]
    assert not state["override"].any()
    assert state["write_count"].tolist() == [7, 0]

    disabled = a2_hold_static_clamp_step_masks(
        False,
        torch.ones(2, dtype=torch.bool),
        torch.ones(2, dtype=torch.bool),
        torch.zeros(2, dtype=torch.bool),
        torch.zeros(2, dtype=torch.long),
        40,
    )
    assert not any(disabled[key].any() for key in ("entering", "override", "complete", "incomplete"))

    configured = _valid_oracle_config()
    configured["a2_hold_oracle_static_clamp_enabled"] = True
    parsed = parse_a2_hold_oracle_config(configured)
    assert parsed["static_clamp_enabled"] is True
    assert parsed["static_clamp_steps"] == 40
    assert parsed["static_clamp_stiffness"] == 80.0
    assert parsed["static_clamp_damping"] == 3.0

    bad = _valid_oracle_config(enabled=False)
    bad["a2_hold_oracle_static_clamp_enabled"] = True
    try:
        parse_a2_hold_oracle_config(bad)
    except RuntimeError as exc:
        assert "requires a2_hold_oracle_enabled" in str(exc)
    else:
        raise AssertionError("static clamp without hold oracle did not fail")


def test_static_clamp_terminal_partition_39_40_mixed_and_overrun_fail_fast():
    affected = torch.tensor([True, True, False])
    count = torch.tensor([39, 40, 40], dtype=torch.long)
    partition = a2_hold_static_clamp_terminal_partition(affected, count, 40)
    assert partition["complete"].tolist() == [False, True, False]
    assert partition["incomplete"].tolist() == [True, False, False]

    terminal_step40 = a2_hold_static_clamp_step_masks(
        True,
        torch.zeros(2, dtype=torch.bool),
        torch.zeros(2, dtype=torch.bool),
        torch.ones(2, dtype=torch.bool),
        torch.tensor([39, 40], dtype=torch.long),
        40,
    )
    assert terminal_step40["complete"].tolist() == [False, True]
    assert terminal_step40["incomplete"].tolist() == [True, False]
    assert not terminal_step40["override"].any()

    try:
        a2_hold_static_clamp_terminal_partition(
            torch.tensor([True]), torch.tensor([41], dtype=torch.long), 40
        )
    except ValueError as exc:
        assert "exceeded its exact target" in str(exc)
    else:
        raise AssertionError("static-clamp count > target did not fail")

    try:
        a2_hold_static_clamp_step_masks(
            True,
            torch.tensor([False]),
            torch.tensor([True]),
            torch.tensor([True]),
            torch.tensor([41], dtype=torch.long),
            40,
        )
    except ValueError as exc:
        assert "exceeded its exact target" in str(exc)
    else:
        raise AssertionError("live active count41 attempted another override")


def test_static_clamp_finish_overrun_restores_and_propagates_original_error():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    finish_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_finish_a2_static_clamp"
    )
    namespace = {
        "torch": torch,
        "a2_hold_static_clamp_terminal_partition": (
            a2_hold_static_clamp_terminal_partition
        ),
    }
    exec(textwrap.dedent(ast.get_source_segment(source, finish_node)), namespace)

    class Dummy:
        _finish_a2_static_clamp = namespace["_finish_a2_static_clamp"]

        def __init__(self):
            self.num_envs = 1
            self.device = "cpu"
            self._a2_hold_oracle_cfg = {
                "enabled": True,
                "static_clamp_enabled": True,
                "static_clamp_steps": 40,
            }
            self._a2_hold_oracle_static_clamp_gain_applied = torch.tensor([True])
            self._a2_hold_oracle_static_clamp_write_count = torch.tensor(
                [41], dtype=torch.long
            )
            self._a2_hold_oracle_static_clamp_final_write_count = torch.tensor(
                [-1], dtype=torch.long
            )
            self.restore_calls = 0
            self.snapshot_calls = 0
            self.outcome_calls = 0

        def _restore_a2_static_clamp_gains(self, mask):
            self.restore_calls += 1
            self._a2_hold_oracle_static_clamp_gain_applied[mask] = False

        def _snapshot_a2_static_clamp_result(self, mask):
            self.snapshot_calls += 1

        def _set_a2_hold_outcome(self, mask, outcome):
            self.outcome_calls += 1

    dummy = Dummy()
    try:
        dummy._finish_a2_static_clamp(torch.tensor([True]))
    except RuntimeError as exc:
        assert "finish partition failed" in str(exc)
        assert isinstance(exc.__cause__, ValueError)
        assert "exceeded its exact target" in str(exc.__cause__)
    else:
        raise AssertionError("finish count41 did not propagate its partition failure")
    assert dummy.restore_calls == 1
    assert not dummy._a2_hold_oracle_static_clamp_gain_applied.any()
    assert dummy.snapshot_calls == 0
    assert dummy.outcome_calls == 0
    assert dummy._a2_hold_oracle_static_clamp_final_write_count.tolist() == [-1]


def test_static_clamp_parser_accepts_only_exact_40_step_s0_s1_s2():
    for stiffness, damping in ((80.0, 3.0), (160.0, 6.0), (320.0, 12.0)):
        config = _valid_oracle_config()
        config["a2_hold_oracle_static_clamp_enabled"] = True
        config["a2_hold_oracle_static_clamp_stiffness"] = stiffness
        config["a2_hold_oracle_static_clamp_damping"] = damping
        parsed = parse_a2_hold_oracle_config(config)
        assert (
            parsed["static_clamp_steps"],
            parsed["static_clamp_stiffness"],
            parsed["static_clamp_damping"],
        ) == (40, stiffness, damping)

    invalid_cases = (
        (41, 80.0, 3.0, "exactly 40"),
        (40, 123.0, 7.0, "exact approved"),
        (40, 160.0, 12.0, "exact approved"),
    )
    for steps, stiffness, damping, expected in invalid_cases:
        config = _valid_oracle_config()
        config["a2_hold_oracle_static_clamp_enabled"] = True
        config["a2_hold_oracle_static_clamp_steps"] = steps
        config["a2_hold_oracle_static_clamp_stiffness"] = stiffness
        config["a2_hold_oracle_static_clamp_damping"] = damping
        try:
            parse_a2_hold_oracle_config(config)
        except RuntimeError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(
                f"invalid static-clamp config {(steps, stiffness, damping)} parsed"
            )


def test_offset_fixed_target_identity_rotated_q_sign_and_nonaccumulation():
    gate_pos = torch.tensor([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]])
    half = math.pi / 4.0
    quat = torch.tensor(
        [
            [1.0, 0.0, 0.0, 0.0],
            [math.cos(half), 0.0, 0.0, math.sin(half)],
        ]
    )
    axis, target, target_quat = a2_hold_offset_fixed_world_target(
        gate_pos, quat, 0.003
    )
    torch.testing.assert_close(axis[0], torch.tensor([0.0, 1.0, 0.0]))
    torch.testing.assert_close(axis[1], torch.tensor([-1.0, 0.0, 0.0]), atol=1e-6, rtol=0.0)
    torch.testing.assert_close(target, gate_pos + 0.003 * axis)
    torch.testing.assert_close(target_quat, quat)

    axis_neg_q, target_neg_q, target_quat_neg_q = a2_hold_offset_fixed_world_target(
        gate_pos, -quat, 0.003
    )
    torch.testing.assert_close(axis_neg_q, axis)
    torch.testing.assert_close(target_neg_q, target)
    torch.testing.assert_close(target_quat_neg_q, -quat)
    _, repeated_target, _ = a2_hold_offset_fixed_world_target(gate_pos, quat, 0.003)
    torch.testing.assert_close(repeated_target, target)

    _, minus_target, _ = a2_hold_offset_fixed_world_target(gate_pos, quat, -0.003)
    torch.testing.assert_close(minus_target, gate_pos - 0.003 * axis)
    _, zero_target, _ = a2_hold_offset_fixed_world_target(gate_pos, quat, 0.0)
    torch.testing.assert_close(zero_target, gate_pos)


def test_offset_opening_dot_validation_and_wrong_degenerate_rejection():
    axis = torch.tensor([[0.0, 1.0, 0.0]])
    opening = torch.tensor([[[0.0, -1.0, 0.0], [0.0, 1.0, 0.0]]])
    dots = a2_hold_validate_offset_axis_opening_dots(axis, opening)
    torch.testing.assert_close(dots, torch.tensor([[-1.0, 1.0]]))
    for invalid in (
        opening.flip(1),
        torch.tensor([[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]]),
        torch.zeros_like(opening),
    ):
        try:
            a2_hold_validate_offset_axis_opening_dots(axis, invalid)
        except ValueError as exc:
            assert "opening" in str(exc) or "unit length" in str(exc)
        else:
            raise AssertionError("invalid offset/opening-axis relationship did not fail")


def test_offset_placement_exact_20_then_check_no_action21_and_mixed_terminal():
    active = torch.zeros(1, dtype=torch.bool)
    count = torch.zeros(1, dtype=torch.long)
    states = []
    for call in range(21):
        state = a2_hold_offset_placement_step_masks(
            True,
            torch.tensor([call == 0]),
            torch.tensor([True]),
            active,
            count,
            20,
        )
        states.append(state)
        active = state["active"]
        count = state["action_count"]
    assert sum(state["override"].item() for state in states) == 20
    assert [state["action_count"].item() for state in states[:20]] == list(
        range(1, 21)
    )
    assert not states[20]["override"].item()
    assert states[20]["endpoint_check"].item()
    assert not states[20]["active"].item()

    mixed = a2_hold_offset_placement_step_masks(
        True,
        torch.zeros(2, dtype=torch.bool),
        torch.tensor([False, True]),
        torch.ones(2, dtype=torch.bool),
        torch.tensor([19, 20], dtype=torch.long),
        20,
    )
    assert mixed["incomplete"].tolist() == [True, False]
    assert mixed["endpoint_check"].tolist() == [False, True]
    assert not mixed["override"].any()

    terminal_after_action20 = a2_hold_offset_placement_step_masks(
        True,
        torch.tensor([False]),
        torch.tensor([False]),
        torch.tensor([True]),
        torch.tensor([20], dtype=torch.long),
        20,
    )
    assert terminal_after_action20["incomplete"].item()
    assert not terminal_after_action20["endpoint_check"].item()
    assert not terminal_after_action20["override"].item()

    clamp_action1 = a2_hold_static_clamp_step_masks(
        True,
        torch.tensor([True]),
        torch.tensor([True]),
        torch.tensor([False]),
        torch.tensor([0], dtype=torch.long),
        40,
    )
    assert clamp_action1["entering"].item()
    assert clamp_action1["override"].item()
    assert clamp_action1["write_count"].item() == 1
    terminal_partition = a2_hold_offset_terminal_partition(
        torch.tensor([True, True]),
        torch.tensor([19, 20], dtype=torch.long),
        20,
    )
    assert terminal_partition["incomplete"].tolist() == [True, False]
    assert terminal_partition["endpoint_check"].tolist() == [False, True]
    try:
        a2_hold_offset_terminal_partition(
            torch.tensor([True]), torch.tensor([21], dtype=torch.long), 20
        )
    except ValueError as exc:
        assert "exceeded" in str(exc)
    else:
        raise AssertionError("offset terminal count21 did not fail fast")


def test_offset_terminal_finish_reset_helper_and_finalizer_mixed_19_20():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    finish_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_finish_a2_offset_placement"
    )
    reset_finish_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_finish_a2_offset_placement_before_reset"
    )
    finalizer_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "finalize_a2_eval_hold_oracle"
    )
    namespace = {
        "torch": torch,
        "a2_hold_offset_terminal_partition": a2_hold_offset_terminal_partition,
    }
    exec(textwrap.dedent(ast.get_source_segment(source, finish_node)), namespace)
    exec(textwrap.dedent(ast.get_source_segment(source, reset_finish_node)), namespace)
    exec(textwrap.dedent(ast.get_source_segment(source, finalizer_node)), namespace)

    class Dummy:
        _finish_a2_offset_placement = namespace["_finish_a2_offset_placement"]
        _finish_a2_offset_placement_before_reset = namespace[
            "_finish_a2_offset_placement_before_reset"
        ]
        finalize_a2_eval_hold_oracle = namespace["finalize_a2_eval_hold_oracle"]

        def __init__(self):
            self.num_envs = 3
            self.device = "cpu"
            self._a2_hold_oracle_cfg = {
                "enabled": True,
                "static_clamp_enabled": True,
                "static_clamp_offset_probe_enabled": True,
                "static_clamp_offset_placement_steps": 20,
                "open_stabilization_preflight_enabled": False,
            }
            self._a2_hold_oracle_offset_placement_ever_activated = torch.ones(
                3, dtype=torch.bool
            )
            self._a2_hold_oracle_static_clamp_gain_applied = torch.zeros(
                3, dtype=torch.bool
            )
            self._a2_hold_oracle_static_clamp_active = torch.zeros(3, dtype=torch.bool)
            self._a2_hold_oracle_offset_final_placement_action_count = torch.full(
                (3,), -1, dtype=torch.long
            )
            self._a2_hold_oracle_offset_placement_action_count = torch.tensor(
                [19, 20, 20], dtype=torch.long
            )
            self._a2_hold_oracle_offset_placement_active = torch.ones(
                3, dtype=torch.bool
            )
            self._a2_hold_oracle_offset_endpoint_checked = torch.zeros(
                3, dtype=torch.bool
            )
            self._a2_hold_oracle_offset_placement_validated = torch.zeros(
                3, dtype=torch.bool
            )
            self._a2_hold_oracle_finalized = False
            self.snapshot_masks = []
            self.outcomes = []
            self.static_finish_masks = []

        def _snapshot_a2_offset_placement_state(self, mask):
            self.snapshot_masks.append(mask.clone())
            converged = torch.zeros_like(mask)
            converged[1] = mask[1]
            return {"converged": converged}

        def _set_a2_hold_outcome(self, mask, outcome):
            self.outcomes.append((mask.clone(), outcome))

        def _finish_a2_static_clamp(self, mask):
            self.static_finish_masks.append(mask.clone())

    dummy = Dummy()
    dummy._finish_a2_offset_placement_before_reset(torch.tensor([0, 1, 2]))
    assert [mask.tolist() for mask in dummy.snapshot_masks] == [[False, True, True]]
    assert dummy._a2_hold_oracle_offset_final_placement_action_count.tolist() == [19, 20, 20]
    assert dummy._a2_hold_oracle_offset_placement_action_count.tolist() == [0, 0, 0]
    assert not dummy._a2_hold_oracle_offset_placement_active.any()
    assert dummy._a2_hold_oracle_offset_endpoint_checked.tolist() == [False, True, True]
    assert dummy._a2_hold_oracle_offset_placement_validated.tolist() == [False, True, False]
    outcome_masks = {name: mask.tolist() for mask, name in dummy.outcomes}
    assert outcome_masks == {
        "PLACEMENT_INCOMPLETE": [True, False, False],
        "PLACEMENT_NOT_CONVERGED": [False, False, True],
        "OFFSET_PLACEMENT_COMPLETE_EPISODE_ENDED": [False, True, False],
    }
    assert not dummy._a2_hold_oracle_static_clamp_gain_applied.any()

    finalizer = Dummy()
    finalizer.finalize_a2_eval_hold_oracle()
    assert finalizer._a2_hold_oracle_finalized
    assert finalizer._a2_hold_oracle_offset_endpoint_checked.tolist() == [False, True, True]
    assert len(finalizer.static_finish_masks) == 1
    assert torch.equal(
        finalizer.static_finish_masks[0], torch.zeros(3, dtype=torch.bool)
    )


def test_offset_apply_handoff_exact20_then_clamp1_or_nonconverged_no_gain():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    apply_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_apply_a2_offset_probe_action"
    )
    namespace = {
        "torch": torch,
        "a2_hold_offset_placement_step_masks": a2_hold_offset_placement_step_masks,
        "a2_hold_static_clamp_step_masks": a2_hold_static_clamp_step_masks,
        "a2_hold_apply_offset_placement_action": a2_hold_apply_offset_placement_action,
        "a2_hold_apply_static_clamp_action": a2_hold_apply_static_clamp_action,
    }
    exec(textwrap.dedent(ast.get_source_segment(source, apply_node)), namespace)

    class Dummy:
        _apply_a2_offset_probe_action = namespace["_apply_a2_offset_probe_action"]

        def __init__(self, converged):
            self.num_envs = 1
            self._a2_hold_oracle_cfg = {
                "static_clamp_offset_placement_steps": 20,
                "static_clamp_steps": 40,
            }
            self._a2_hold_oracle_offset_placement_active = torch.zeros(
                1, dtype=torch.bool
            )
            self._a2_hold_oracle_offset_placement_action_count = torch.zeros(
                1, dtype=torch.long
            )
            self._a2_hold_oracle_offset_endpoint_checked = torch.zeros(
                1, dtype=torch.bool
            )
            self._a2_hold_oracle_offset_final_placement_action_count = torch.full(
                (1,), -1, dtype=torch.long
            )
            self._a2_hold_oracle_offset_placement_validated = torch.zeros(
                1, dtype=torch.bool
            )
            self._a2_hold_oracle_static_clamp_active = torch.zeros(
                1, dtype=torch.bool
            )
            self._a2_hold_oracle_static_clamp_write_count = torch.zeros(
                1, dtype=torch.long
            )
            self._a2_hold_oracle_static_clamp_gain_applied = torch.zeros(
                1, dtype=torch.bool
            )
            self._a2_hold_oracle_phase_step = torch.zeros(1, dtype=torch.long)
            self._a2_hold_oracle_a_raw = torch.full((1, 6), 9.0)
            self._a2_hold_oracle_offset_placement_branch = torch.zeros(
                1, dtype=torch.bool
            )
            self._a2_hold_oracle_arm_dls_branch = torch.zeros(1, dtype=torch.bool)
            self._a2_hold_oracle_base_relief_branch_applied = torch.zeros(
                1, dtype=torch.bool
            )
            self._a2_hold_oracle_phase_sign_check_due = torch.zeros(
                1, dtype=torch.bool
            )
            self._a2_hold_oracle_last_override_mask = torch.zeros(
                1, dtype=torch.bool
            )
            self._a2_hold_oracle_post_override_action = None
            self.endpoint_converged = converged
            self.gains = (80.0, 3.0)
            self.events = []
            self.preclamp_snapshot = None
            self.outcomes = []

        def _finish_a2_offset_placement(self, mask):
            self._a2_hold_oracle_offset_placement_active[mask] = False
            self._a2_hold_oracle_offset_placement_action_count[mask] = 0

        def _snapshot_a2_offset_placement_state(self, mask):
            result = torch.zeros_like(mask)
            if torch.any(mask):
                self.events.append(("snapshot", self.gains))
                self.preclamp_snapshot = {"gains": self.gains}
                result[mask] = self.endpoint_converged
            return {"converged": result}

        def _set_a2_hold_outcome(self, mask, outcome):
            if torch.any(mask):
                self.outcomes.append(outcome)

        def _apply_a2_static_clamp_gains(self, mask):
            if torch.any(mask):
                assert self.preclamp_snapshot == {"gains": (80.0, 3.0)}
                self.events.append(("gains", (160.0, 6.0)))
                self.gains = (160.0, 6.0)
                self._a2_hold_oracle_static_clamp_gain_applied[mask] = True

        def _finish_a2_static_clamp(self, mask):
            assert not torch.any(mask)

        def _compute_a2_offset_placement_arm_raw(self, mask):
            assert self.gains == (80.0, 3.0)
            result = torch.zeros(1, 6)
            result[mask] = 0.25
            self._a2_hold_oracle_a_raw[mask] = result[mask]
            return result

    policy = torch.arange(12, dtype=torch.float32).reshape(1, 12)
    active = torch.ones(1, dtype=torch.bool)
    passing = Dummy(True)
    for index in range(20):
        action, override = passing._apply_a2_offset_probe_action(
            policy, active, torch.tensor([index == 0])
        )
        assert override.item()
        torch.testing.assert_close(action[0, :5], torch.zeros(5))
        torch.testing.assert_close(action[0, 5:11], torch.full((6,), 0.25))
        torch.testing.assert_close(
            passing._a2_hold_oracle_a_raw[0], action[0, 5:11]
        )
        assert action[0, 11].item() == 1.0
        assert passing.gains == (80.0, 3.0)
    assert passing._a2_hold_oracle_offset_placement_action_count.item() == 20
    action, override = passing._apply_a2_offset_probe_action(
        policy, active, torch.tensor([False])
    )
    assert override.item()
    torch.testing.assert_close(action[0, :11], torch.zeros(11))
    torch.testing.assert_close(
        passing._a2_hold_oracle_a_raw[0], torch.zeros(6)
    )
    assert action[0, 11].item() == -1.0
    assert passing.events == [
        ("snapshot", (80.0, 3.0)),
        ("gains", (160.0, 6.0)),
    ]
    assert passing._a2_hold_oracle_offset_final_placement_action_count.item() == 20
    assert passing._a2_hold_oracle_offset_endpoint_checked.item()
    assert passing._a2_hold_oracle_offset_placement_validated.item()
    assert passing._a2_hold_oracle_static_clamp_write_count.item() == 1
    for _ in range(39):
        action, override = passing._apply_a2_offset_probe_action(
            policy, active, torch.tensor([False])
        )
        assert override.item()
        torch.testing.assert_close(action[0, 5:11], torch.zeros(6))
        torch.testing.assert_close(
            passing._a2_hold_oracle_a_raw[0], torch.zeros(6)
        )
    assert passing._a2_hold_oracle_static_clamp_write_count.item() == 40

    failing = Dummy(False)
    for index in range(20):
        failing._apply_a2_offset_probe_action(
            policy, active, torch.tensor([index == 0])
        )
    action, override = failing._apply_a2_offset_probe_action(
        policy, active, torch.tensor([False])
    )
    assert not override.item()
    torch.testing.assert_close(action, policy)
    assert failing.events == [("snapshot", (80.0, 3.0))]
    assert failing.gains == (80.0, 3.0)
    assert failing.outcomes == ["PLACEMENT_NOT_CONVERGED"]
    assert not failing._a2_hold_oracle_static_clamp_gain_applied.item()
    assert failing._a2_hold_oracle_static_clamp_write_count.item() == 0
    torch.testing.assert_close(failing._a2_hold_oracle_a_raw[0], torch.zeros(6))

    terminal = Dummy(True)
    for index in range(20):
        terminal._apply_a2_offset_probe_action(
            policy, active, torch.tensor([index == 0])
        )
    terminal._a2_hold_oracle_a_raw.fill_(7.0)
    action, override = terminal._apply_a2_offset_probe_action(
        policy, torch.tensor([False]), torch.tensor([False])
    )
    assert not override.item()
    torch.testing.assert_close(action, policy)
    torch.testing.assert_close(terminal._a2_hold_oracle_a_raw[0], torch.zeros(6))


def test_offset_two_env_async_applied_arm_telemetry_matches_controlled_rows():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    apply_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_apply_a2_offset_probe_action"
    )
    namespace = {
        "torch": torch,
        "a2_hold_offset_placement_step_masks": a2_hold_offset_placement_step_masks,
        "a2_hold_static_clamp_step_masks": a2_hold_static_clamp_step_masks,
        "a2_hold_apply_offset_placement_action": a2_hold_apply_offset_placement_action,
        "a2_hold_apply_static_clamp_action": a2_hold_apply_static_clamp_action,
    }
    exec(textwrap.dedent(ast.get_source_segment(source, apply_node)), namespace)

    class Dummy:
        _apply_a2_offset_probe_action = namespace["_apply_a2_offset_probe_action"]

        def __init__(self):
            self.num_envs = 2
            self._a2_hold_oracle_cfg = {
                "static_clamp_offset_placement_steps": 20,
                "static_clamp_steps": 40,
            }
            self._a2_hold_oracle_a_raw = torch.full((2, 6), 9.0)
            self._a2_hold_oracle_offset_placement_active = torch.tensor(
                [False, True]
            )
            self._a2_hold_oracle_offset_placement_action_count = torch.tensor(
                [0, 1], dtype=torch.long
            )
            self._a2_hold_oracle_offset_endpoint_checked = torch.zeros(
                2, dtype=torch.bool
            )
            self._a2_hold_oracle_offset_final_placement_action_count = torch.full(
                (2,), -1, dtype=torch.long
            )
            self._a2_hold_oracle_offset_placement_validated = torch.zeros(
                2, dtype=torch.bool
            )
            self._a2_hold_oracle_static_clamp_active = torch.tensor([True, False])
            self._a2_hold_oracle_static_clamp_write_count = torch.tensor(
                [5, 0], dtype=torch.long
            )
            self._a2_hold_oracle_phase_step = torch.zeros(2, dtype=torch.long)
            self._a2_hold_oracle_offset_placement_branch = torch.zeros(
                2, dtype=torch.bool
            )
            self._a2_hold_oracle_arm_dls_branch = torch.zeros(2, dtype=torch.bool)
            self._a2_hold_oracle_base_relief_branch_applied = torch.zeros(
                2, dtype=torch.bool
            )
            self._a2_hold_oracle_phase_sign_check_due = torch.zeros(
                2, dtype=torch.bool
            )
            self._a2_hold_oracle_last_override_mask = torch.zeros(
                2, dtype=torch.bool
            )
            self._a2_hold_oracle_post_override_action = None

        def _finish_a2_offset_placement(self, mask):
            assert not torch.any(mask)

        def _snapshot_a2_offset_placement_state(self, mask):
            assert not torch.any(mask)
            return {"converged": torch.zeros_like(mask)}

        def _set_a2_hold_outcome(self, mask, outcome):
            assert not torch.any(mask), outcome

        def _apply_a2_static_clamp_gains(self, mask):
            assert not torch.any(mask)

        def _finish_a2_static_clamp(self, mask):
            assert not torch.any(mask)

        def _compute_a2_offset_placement_arm_raw(self, mask):
            assert mask.tolist() == [False, True]
            result = torch.zeros(2, 6)
            result[mask] = 0.25
            self._a2_hold_oracle_a_raw[mask] = result[mask]
            return result

    dummy = Dummy()
    policy = torch.arange(24, dtype=torch.float32).reshape(2, 12)
    action, override = dummy._apply_a2_offset_probe_action(
        policy,
        torch.ones(2, dtype=torch.bool),
        torch.zeros(2, dtype=torch.bool),
    )
    assert override.tolist() == [True, True]
    torch.testing.assert_close(action[0, 5:11], torch.zeros(6))
    torch.testing.assert_close(dummy._a2_hold_oracle_a_raw[0], torch.zeros(6))
    torch.testing.assert_close(action[1, 5:11], torch.full((6,), 0.25))
    torch.testing.assert_close(
        dummy._a2_hold_oracle_a_raw[1], action[1, 5:11]
    )
    torch.testing.assert_close(
        action[override, 5:11], dummy._a2_hold_oracle_a_raw[override]
    )


def test_offset_static_clamp_live_refresh_moves_without_mutating_preclamp_snapshot():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    refresh_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_refresh_a2_offset_live_telemetry"
    )
    namespace = {
        "torch": torch,
        "a2_hold_offset_endpoint_metrics": a2_hold_offset_endpoint_metrics,
    }
    exec(textwrap.dedent(ast.get_source_segment(source, refresh_node)), namespace)

    class Dummy:
        _refresh_a2_offset_live_telemetry = namespace[
            "_refresh_a2_offset_live_telemetry"
        ]

        def __init__(self):
            self.source_pos = torch.tensor([[0.0, 0.003, 0.0]])
            self.root_pos = torch.zeros(1, 3)
            self.door_joint_pos = torch.zeros(1, 2)
            self._a2_hold_oracle_cfg = {
                "static_clamp_offset_m": 0.003,
                "static_clamp_offset_position_tolerance_m": 0.0005,
                "static_clamp_offset_orientation_tolerance_rad": 0.02,
            }
            self._a2_hold_oracle_offset_gate_source_pos_w = torch.zeros(1, 3)
            self._a2_hold_oracle_offset_fixed_target_pos_w = torch.tensor(
                [[0.0, 0.003, 0.0]]
            )
            self._a2_hold_oracle_offset_fixed_target_quat_w = torch.tensor(
                [[1.0, 0.0, 0.0, 0.0]]
            )
            self._a2_hold_oracle_offset_source_local_y_axis_w = torch.tensor(
                [[0.0, 1.0, 0.0]]
            )
            self._a2_hold_oracle_offset_achieved_signed_offset_m = torch.full(
                (1,), float("nan")
            )
            self._a2_hold_oracle_offset_signed_offset_error_m = torch.full(
                (1,), float("nan")
            )
            self._a2_hold_oracle_offset_orthogonal_residual_m = torch.full(
                (1,), float("nan")
            )
            self._a2_hold_oracle_offset_position_residual_m = torch.full(
                (1,), float("nan")
            )
            self._a2_hold_oracle_offset_orientation_residual_rad = torch.full(
                (1,), float("nan")
            )
            self._a2_hold_oracle_offset_root_start_xy_w = torch.zeros(1, 2)
            self._a2_hold_oracle_offset_root_displacement_m = torch.full(
                (1,), float("nan")
            )
            self._a2_hold_oracle_offset_hinge_joint_start = torch.zeros(1)
            self._a2_hold_oracle_offset_handle_joint_start = torch.zeros(1)
            self._a2_hold_oracle_offset_hinge_joint_delta = torch.full(
                (1,), float("nan")
            )
            self._a2_hold_oracle_offset_handle_joint_delta = torch.full(
                (1,), float("nan")
            )
            self._a2_hold_oracle_offset_preclamp_snapshot = [
                {"position_residual_m": 0.0, "immutable": True}
            ]

        def _get_a2_hold_oracle_world_frames(self):
            return {
                "source_pos_w": self.source_pos.clone(),
                "source_quat_w": torch.tensor([[1.0, 0.0, 0.0, 0.0]]),
                "root_pos_w": self.root_pos.clone(),
            }

        def _get_door_joint_pos(self, _context, expected):
            assert expected == 2
            return self.door_joint_pos.clone()

    dummy = Dummy()
    immutable_before = json.dumps(dummy._a2_hold_oracle_offset_preclamp_snapshot)
    clamp_refresh_mask = torch.tensor([True])
    dummy._refresh_a2_offset_live_telemetry(clamp_refresh_mask)
    assert dummy._a2_hold_oracle_offset_position_residual_m.item() == 0.0
    dummy.source_pos[:] = torch.tensor([[0.001, 0.005, 0.0]])
    dummy.root_pos[:, 0] = 0.1
    dummy.door_joint_pos[:] = torch.tensor([[0.2, -0.1]])
    dummy._refresh_a2_offset_live_telemetry(clamp_refresh_mask)
    assert math.isclose(
        dummy._a2_hold_oracle_offset_achieved_signed_offset_m.item(),
        0.005,
        abs_tol=1.0e-7,
    )
    assert dummy._a2_hold_oracle_offset_position_residual_m.item() > 0.002
    assert math.isclose(
        dummy._a2_hold_oracle_offset_orthogonal_residual_m.item(),
        0.001,
        abs_tol=1.0e-7,
    )
    assert math.isclose(
        dummy._a2_hold_oracle_offset_root_displacement_m.item(),
        0.1,
        abs_tol=1.0e-7,
    )
    assert math.isclose(
        dummy._a2_hold_oracle_offset_hinge_joint_delta.item(),
        0.2,
        abs_tol=1.0e-7,
    )
    assert math.isclose(
        dummy._a2_hold_oracle_offset_handle_joint_delta.item(),
        -0.1,
        abs_tol=1.0e-7,
    )
    assert json.dumps(dummy._a2_hold_oracle_offset_preclamp_snapshot) == immutable_before

    trace_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_get_a2_hold_oracle_trace_fields"
    )
    trace_source = ast.get_source_segment(source, trace_node)
    assert "self._a2_hold_oracle_static_clamp_active" in trace_source
    assert "self._a2_hold_oracle_static_clamp_gain_applied" in trace_source


def test_offset_async_placement_masks_all_generic_telemetry_and_action_rows():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    compute_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_compute_a2_offset_placement_arm_raw"
    )
    namespace = {
        "torch": torch,
        "a2_hold_progress_aware_joint_limit_masks": (
            a2_hold_progress_aware_joint_limit_masks
        ),
        "a2_hold_absolute_target_to_cumulative_action": (
            a2_hold_absolute_target_to_cumulative_action
        ),
        "a2_hold_offset_endpoint_metrics": a2_hold_offset_endpoint_metrics,
    }
    exec(textwrap.dedent(ast.get_source_segment(source, compute_node)), namespace)

    class Data:
        pass

    class Robot:
        pass

    class Scene:
        pass

    class Simulator:
        pass

    class Dummy:
        _compute_a2_offset_placement_arm_raw = namespace[
            "_compute_a2_offset_placement_arm_raw"
        ]

        def __init__(self):
            self.num_envs = 2
            self.device = "cpu"
            self._a2_hold_oracle_cfg = {
                "joint_limit_margin": 0.0001,
                "soft_limit_progress_tolerance": 0.000001,
                "raw_action_abs_max": 10.0,
                "static_clamp_offset_m": 0.003,
                "static_clamp_offset_position_tolerance_m": 0.0005,
                "static_clamp_offset_orientation_tolerance_rad": 0.02,
            }
            self._a2_hold_oracle_joint_ids = list(range(6))
            self._a2_hold_oracle_static_clamp_gain_applied = torch.tensor(
                [True, False]
            )
            robot = Robot()
            robot.data = Data()
            robot.data.joint_pos_limits = torch.tensor(
                [[[-2.0, 2.0]] * 6, [[-2.0, 2.0]] * 6]
            )
            robot.data.soft_joint_pos_limits = robot.data.joint_pos_limits.clone()
            robot.data.joint_pos = torch.zeros(2, 6)
            robot.data.default_joint_pos = torch.zeros(2, 6)
            scene = Scene()
            scene.articulations = {"robot": robot}
            self.simulator = Simulator()
            self.simulator.scene = scene
            self._delta_actions = torch.zeros(2, 6)

            float_specs = {
                "_a2_hold_oracle_q_des": (2, 6),
                "_a2_hold_oracle_d_des": (2, 6),
                "_a2_hold_oracle_d_prev": (2, 6),
                "_a2_hold_oracle_arm_candidate_action_raw": (2, 6),
                "_a2_hold_oracle_a_raw": (2, 6),
                "_a2_hold_oracle_target_pos_root": (2, 3),
                "_a2_hold_oracle_target_quat_root": (2, 4),
                "_a2_hold_oracle_bounded_command_pos_root": (2, 3),
                "_a2_hold_oracle_bounded_command_quat_root": (2, 4),
                "_a2_hold_oracle_bounded_position_step": (2,),
                "_a2_hold_oracle_bounded_orientation_step": (2,),
                "_a2_hold_oracle_position_residual": (2,),
                "_a2_hold_oracle_orientation_residual": (2,),
                "_a2_hold_oracle_singular_values": (2, 6),
                "_a2_hold_oracle_jacobian_condition": (2,),
                "_a2_hold_oracle_offset_achieved_signed_offset_m": (2,),
                "_a2_hold_oracle_offset_signed_offset_error_m": (2,),
                "_a2_hold_oracle_offset_orthogonal_residual_m": (2,),
                "_a2_hold_oracle_offset_position_residual_m": (2,),
                "_a2_hold_oracle_offset_orientation_residual_rad": (2,),
                "_a2_hold_oracle_offset_root_displacement_m": (2,),
                "_a2_hold_oracle_offset_hinge_joint_delta": (2,),
                "_a2_hold_oracle_offset_handle_joint_delta": (2,),
            }
            for name, shape in float_specs.items():
                setattr(self, name, torch.full(shape, 71.0))
            for name in (
                "_a2_hold_oracle_ik_valid",
                "_a2_hold_oracle_limit_valid",
                "_a2_hold_oracle_delta_ok",
                "_a2_hold_oracle_raw_ok",
            ):
                setattr(self, name, torch.zeros(2, dtype=torch.bool))

            self._a2_hold_oracle_offset_root_start_xy_w = torch.zeros(2, 2)
            self._a2_hold_oracle_offset_gate_source_pos_w = torch.zeros(2, 3)
            self._a2_hold_oracle_offset_fixed_target_pos_w = torch.tensor(
                [[0.0, 0.003, 0.0], [0.0, 0.003, 0.0]]
            )
            self._a2_hold_oracle_offset_fixed_target_quat_w = torch.tensor(
                [[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]]
            )
            self._a2_hold_oracle_offset_source_local_y_axis_w = torch.tensor(
                [[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
            )
            self._a2_hold_oracle_offset_hinge_joint_start = torch.zeros(2)
            self._a2_hold_oracle_offset_handle_joint_start = torch.zeros(2)
            self.audited_names = tuple(float_specs) + (
                "_a2_hold_oracle_ik_valid",
                "_a2_hold_oracle_limit_valid",
                "_a2_hold_oracle_delta_ok",
                "_a2_hold_oracle_raw_ok",
            )

        def _get_a2_static_clamp_gripper_state(self, env_ids):
            assert env_ids.tolist() == [1]
            return None, None, {
                "stiffness": torch.full((1, 2), 80.0),
                "damping": torch.full((1, 2), 3.0),
                "effort_limit": torch.full((1, 2), 10.0),
            }

        def _compute_a2_hold_offset_joint_target(self, placement_mask):
            assert placement_mask.tolist() == [False, True]
            q_des = torch.tensor([[0.2] * 6, [0.3] * 6])
            identity = torch.tensor(
                [[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]]
            )
            return (
                q_des,
                torch.ones(2, dtype=torch.bool),
                torch.tensor([[9.0] * 6, [1.0] * 6]),
                torch.tensor([9.0, 1.0]),
                torch.tensor([[9.0] * 3, [0.0, 0.003, 0.0]]),
                identity,
                torch.tensor([9.0, 0.003]),
                torch.tensor([9.0, 0.0]),
                torch.tensor([[9.0] * 3, [0.0, 0.002, 0.0]]),
                identity,
                torch.tensor([9.0, 0.002]),
                torch.tensor([9.0, 0.0]),
                torch.tensor([[9.0, 9.0], [0.0, 0.0]]),
            )

        def _get_a2_hold_oracle_world_frames(self):
            return {
                "source_pos_w": torch.tensor(
                    [[9.0, 9.0, 9.0], [0.0, 0.003, 0.0]]
                ),
                "source_quat_w": torch.tensor(
                    [[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]]
                ),
            }

        def _get_door_joint_pos(self, _context, expected):
            assert expected == 2
            return torch.tensor([[9.0, 9.0], [0.2, -0.1]])

    dummy = Dummy()
    env0_before = {
        name: getattr(dummy, name)[0].clone() for name in dummy.audited_names
    }
    placement_mask = torch.tensor([False, True])
    arm_raw = dummy._compute_a2_offset_placement_arm_raw(placement_mask)
    for name, expected in env0_before.items():
        assert torch.equal(getattr(dummy, name)[0], expected), name
    assert torch.all(dummy._a2_hold_oracle_q_des[1] == 0.3)
    assert dummy._a2_hold_oracle_ik_valid.tolist() == [False, True]
    policy = torch.arange(24, dtype=torch.float32).reshape(2, 12)
    action = a2_hold_apply_offset_placement_action(
        policy, placement_mask, arm_raw
    )
    torch.testing.assert_close(action[0], policy[0])
    torch.testing.assert_close(action[1, :5], torch.zeros(5))
    torch.testing.assert_close(action[1, 5:11], arm_raw[1])
    assert action[1, 11].item() == 1.0


def test_offset_orientation_semantic_is_conditional_and_default_is_unchanged():
    assert a2_hold_target_orientation_semantic(False, False) == (
        "handle_orientation_composed_with_handoff_handle_to_gripper_relative_orientation"
    )
    assert a2_hold_target_orientation_semantic(True, False) == (
        "captured gate source quaternion is fixed-world residual reference; placement uses "
        "Cartesian DLS; static clamp uses accumulated joint-target hold with arm raw zero"
    )


def test_matched_clean_orientation_semantic_is_exact_and_modes_fail_fast():
    assert a2_hold_target_orientation_semantic(False, True) == (
        "RELEASE_RETREAT uses live OrderedTargetFrameTransformer pregrasp "
        "target_quat_w[:,1,:]; CLEAN_STABILIZE uses captured accumulated joint-target "
        "hold with arm raw zero"
    )
    for flags in ((1, False), (False, 1)):
        try:
            a2_hold_target_orientation_semantic(*flags)
        except ValueError as exc:
            assert "mode flags must be bool" in str(exc)
        else:
            raise AssertionError(f"non-bool orientation semantic flags parsed: {flags}")
    try:
        a2_hold_target_orientation_semantic(True, True)
    except ValueError as exc:
        assert "mutually exclusive" in str(exc)
    else:
        raise AssertionError("conflicting orientation semantic modes parsed")

    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    trace_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_get_a2_hold_oracle_trace_fields"
    )
    semantic_calls = [
        node
        for node in ast.walk(trace_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "a2_hold_target_orientation_semantic"
    ]
    assert len(semantic_calls) == 1
    assert [ast.unparse(arg) for arg in semantic_calls[0].args] == [
        "cfg['static_clamp_offset_probe_enabled']",
        "cfg['matched_clean_reacquisition_preflight_enabled']",
    ]


def test_offset_placement_action_and_endpoint_metrics_o0_and_off_axis():
    policy = torch.arange(24, dtype=torch.float32).reshape(2, 12)
    arm = torch.full((2, 6), 0.25)
    action = a2_hold_apply_offset_placement_action(
        policy, torch.tensor([True, False]), arm
    )
    torch.testing.assert_close(action[0, :5], torch.zeros(5))
    torch.testing.assert_close(action[0, 5:11], arm[0])
    assert action[0, 11].item() == 1.0
    torch.testing.assert_close(action[1], policy[1])

    gate = torch.zeros(2, 3)
    axis = torch.tensor([[0.0, 1.0, 0.0]]).repeat(2, 1)
    target = torch.tensor([[0.0, 0.003, 0.0], [0.0, 0.0, 0.0]])
    quat = torch.tensor([[1.0, 0.0, 0.0, 0.0]]).repeat(2, 1)
    current = target.clone()
    current_quat = quat.clone()
    current_quat[0] *= -1.0
    metrics_plus = a2_hold_offset_endpoint_metrics(
        current[:1],
        current_quat[:1],
        gate[:1],
        target[:1],
        quat[:1],
        axis[:1],
        0.003,
        0.0005,
        0.02,
    )
    assert metrics_plus["converged"].item()
    torch.testing.assert_close(
        metrics_plus["achieved_signed_offset_m"], torch.tensor([0.003])
    )
    assert metrics_plus["orthogonal_residual_m"].item() == 0.0

    metrics_zero = a2_hold_offset_endpoint_metrics(
        current[1:], quat[1:], gate[1:], target[1:], quat[1:], axis[1:], 0.0, 0.0005, 0.02
    )
    assert metrics_zero["converged"].item()
    off_axis = current[:1].clone()
    off_axis[:, 0] = 0.001
    failed = a2_hold_offset_endpoint_metrics(
        off_axis, quat[:1], gate[:1], target[:1], quat[:1], axis[:1], 0.003, 0.0005, 0.02
    )
    assert not failed["converged"].item()
    assert failed["orthogonal_residual_m"].item() > 0.0005


def test_offset_parser_accepts_only_fresh_o_minus_o0_o_plus_contract():
    for offset in (-0.003, 0.0, 0.003):
        cfg = _valid_oracle_config()
        cfg["a2_hold_oracle_static_clamp_enabled"] = True
        cfg["a2_hold_oracle_static_clamp_stiffness"] = 160.0
        cfg["a2_hold_oracle_static_clamp_damping"] = 6.0
        cfg["a2_hold_oracle_static_clamp_offset_probe_enabled"] = True
        cfg["a2_hold_oracle_static_clamp_offset_m"] = offset
        parsed = parse_a2_hold_oracle_config(cfg)
        assert parsed["static_clamp_offset_m"] == offset
        assert parsed["static_clamp_offset_placement_steps"] == 20

    invalid_updates = (
        {"a2_hold_oracle_static_clamp_offset_m": 0.001},
        {"a2_hold_oracle_static_clamp_offset_placement_steps": 19},
        {"a2_hold_oracle_static_clamp_steps": 41},
        {"a2_hold_oracle_static_clamp_stiffness": 80.0},
        {"a2_hold_oracle_static_clamp_damping": 12.0},
    )
    for update in invalid_updates:
        cfg = _valid_oracle_config()
        cfg.update(
            {
                "a2_hold_oracle_static_clamp_enabled": True,
                "a2_hold_oracle_static_clamp_stiffness": 160.0,
                "a2_hold_oracle_static_clamp_damping": 6.0,
                "a2_hold_oracle_static_clamp_offset_probe_enabled": True,
            }
        )
        cfg.update(update)
        try:
            parse_a2_hold_oracle_config(cfg)
        except RuntimeError as exc:
            assert "offset probe" in str(exc) or "static clamp" in str(exc)
        else:
            raise AssertionError(f"invalid offset config parsed: {update}")

    formal_protocol_deviations = (
        {"a2_hold_oracle_static_clamp_offset_position_tolerance_m": 0.0006},
        {"a2_hold_oracle_static_clamp_offset_orientation_tolerance_rad": 0.03},
        {"a2_hold_oracle_max_position_step_m": 0.003},
        {"a2_hold_oracle_max_orientation_step_rad": 0.03},
        {"a2_hold_oracle_dls_lambda": 0.02},
        {"a2_hold_oracle_jacobian_condition_max": 999999.0},
        {"a2_hold_oracle_joint_limit_margin": 0.0002},
        {"a2_hold_oracle_soft_limit_progress_tolerance": 0.000002},
        {"a2_hold_oracle_raw_action_abs_max": 9.0},
    )
    for update in formal_protocol_deviations:
        cfg = _valid_oracle_config()
        cfg.update(
            {
                "a2_hold_oracle_static_clamp_enabled": True,
                "a2_hold_oracle_static_clamp_stiffness": 160.0,
                "a2_hold_oracle_static_clamp_damping": 6.0,
                "a2_hold_oracle_static_clamp_offset_probe_enabled": True,
            }
        )
        cfg.update(update)
        try:
            parse_a2_hold_oracle_config(cfg)
        except RuntimeError as exc:
            assert "exact formal protocol tuple" in str(exc)
        else:
            raise AssertionError(f"offset formal protocol deviation parsed: {update}")


def test_offset_runtime_state_machine_reset_summary_and_no_relief_wiring():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    eval_yaml = (Path(__file__).parents[1] / "config/base_eval.yaml").read_text()
    tree = ast.parse(source)
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    apply_method = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_apply_a2_offset_probe_action"
    )
    apply_source = ast.get_source_segment(source, apply_method)
    assert apply_source.index("_snapshot_a2_offset_placement_state") < apply_source.index(
        "_apply_a2_static_clamp_gains"
    )
    assert "a2_hold_apply_offset_placement_action" in apply_source
    assert "a2_hold_base_relief" not in apply_source
    assert "placement_override & static_state" in apply_source

    reset_method = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_reset_buffers_callback"
    )
    reset_source = ast.get_source_segment(source, reset_method)
    assert reset_source.index("_finish_a2_offset_placement") < reset_source.index(
        "_finish_a2_static_clamp"
    ) < reset_source.index("super()._reset_buffers_callback")
    finalize_method = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "finalize_a2_eval_hold_oracle"
    )
    finalize_source = ast.get_source_segment(source, finalize_method)
    assert finalize_source.index("_finish_a2_offset_placement") < finalize_source.index(
        "_finish_a2_static_clamp"
    )
    for required in (
        '"PLACEMENT_INCOMPLETE"',
        '"PLACEMENT_NOT_CONVERGED"',
        '"hold_oracle_offset_gate_source_pos_w"',
        '"hold_oracle_offset_fixed_target_pos_w"',
        '"hold_oracle_offset_opening_axis_dots_body7_body8"',
        '"per_env_offset_preclamp_snapshot"',
        "summary cannot retain PENDING",
        "initial gripper Kp/Kd=80/3 and effort=10/10",
        "A2 offset probe requires exact current TCP z=0.085",
        "A2 offset probe requires friction override=null",
        "_refresh_a2_offset_live_telemetry",
    ):
        assert required in source
    for required in (
        "a2_hold_oracle_static_clamp_offset_probe_enabled: false",
        "a2_hold_oracle_static_clamp_offset_m: 0.0",
        "a2_hold_oracle_static_clamp_offset_placement_steps: 20",
        "a2_hold_oracle_static_clamp_offset_position_tolerance_m: 0.0005",
        "a2_hold_oracle_static_clamp_offset_orientation_tolerance_rad: 0.02",
    ):
        assert required in eval_yaml


def test_static_clamp_reset_finalize_order_and_durable_summary_wiring():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    reset_method = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_reset_buffers_callback"
    )
    reset_source = ast.get_source_segment(source, reset_method)
    assert reset_source.index("self._finish_a2_static_clamp(affected)") < reset_source.index(
        "super()._reset_buffers_callback(env_ids, target_buf)"
    )
    finish_method = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_finish_a2_static_clamp"
    )
    finish_source = ast.get_source_segment(source, finish_method)
    assert finish_source.index("_snapshot_a2_static_clamp_result") < finish_source.index(
        "_restore_a2_static_clamp_gains"
    )
    assert "finally:" in finish_source
    assert "a2_hold_static_clamp_terminal_partition(" in finish_source
    finalize_method = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "finalize_a2_eval_hold_oracle"
    )
    finalize_source = ast.get_source_segment(source, finalize_method)
    assert "if self._a2_hold_oracle_finalized:" in finalize_source
    assert "self._finish_a2_static_clamp(" in finalize_source
    for durable_field in (
        "per_env_static_clamp_final_action_write_count",
        "per_env_static_clamp_requested_stiffness",
        "per_env_static_clamp_requested_damping",
        "per_env_static_clamp_applied_stiffness",
        "per_env_static_clamp_applied_damping",
        "per_env_static_clamp_applied_effort_limit",
        "per_env_static_clamp_restored_stiffness",
        "per_env_static_clamp_restored_damping",
        "per_env_static_clamp_restored_effort_limit",
    ):
        assert f'"{durable_field}"' in source
    assert "A2 static clamp summary rejects active/unrestored gains" in source
    assert "A2 static clamp summary rejects gain/effort restore mismatch" in source


def test_static_clamp_gain_restore_finally_and_trace_wiring():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    trainer = TRAINER_SOURCE_PATH.read_text(encoding="utf-8")
    eval_yaml = (Path(__file__).parents[1] / "config/base_eval.yaml").read_text()
    for expected in (
        "a2_hold_oracle_static_clamp_enabled: false",
        "a2_hold_oracle_static_clamp_steps: 40",
        "a2_hold_oracle_static_clamp_stiffness: 80.0",
        "a2_hold_oracle_static_clamp_damping: 3.0",
    ):
        assert expected in eval_yaml
    for expected in (
        "write_joint_stiffness_to_sim",
        "write_joint_damping_to_sim",
        "A2 static clamp requires exact unchanged gripper effort_limit=10N",
        "A2 static clamp exact gain restore verification failed",
        "STATIC_CLAMP_COMPLETE",
        "STATIC_CLAMP_INCOMPLETE",
        "_snapshot_a2_static_clamp_result",
        "finalize_a2_eval_hold_oracle",
        '"hold_oracle_static_clamp_action_write_count"',
        '"finger_normal_force_along_opening_axis_body7_body8"',
        '"finger_friction_force_along_opening_axis_body7_body8"',
        '"finger_total_force_along_opening_axis_body7_body8"',
        '"runtime_gain_pd_effort_estimate_primary_unclipped"',
        "NON_AUTHORITATIVE_AFTER_RUNTIME_GAIN_OVERRIDE",
    ):
        assert expected in source
    assert "@contextmanager\ndef _a2_hold_oracle_finalize_guard" in trainer
    assert "finally:\n        if enabled:" in trainer
    assert "with _a2_hold_oracle_finalize_guard(" in trainer
    assert '"relief_steps_consume_current_phase_timeout"' in source
    for outcome in (
        "BASE_RELIEF_WRONG_SIGN",
        "BASE_RELIEF_TIMEOUT",
        "BASE_RELIEF_DISPLACEMENT_LIMIT",
    ):
        assert outcome in A2_HOLD_OUTCOME_NAMES


def test_phase_arm_sign_counter_relief_boundaries_and_no_relief_baseline():
    phase = torch.tensor([True])
    unchecked = torch.tensor([False])

    relief_before = a2_hold_update_phase_arm_sign_check(
        phase,
        torch.tensor([False]),
        torch.tensor([9]),
        unchecked,
        torch.tensor([0.0]),
        10,
        0.005,
    )
    assert relief_before["count"].tolist() == [9]
    assert relief_before["due"].tolist() == [False]

    relief_starts_on_boundary_pass = a2_hold_update_phase_arm_sign_check(
        phase,
        torch.tensor([False]),
        torch.tensor([10]),
        unchecked,
        torch.tensor([0.006]),
        10,
        0.005,
    )
    assert relief_starts_on_boundary_pass["due"].tolist() == [True]
    assert relief_starts_on_boundary_pass["wrong_sign"].tolist() == [False]
    assert relief_starts_on_boundary_pass["checked"].tolist() == [True]

    relief_starts_on_boundary_fail = a2_hold_update_phase_arm_sign_check(
        phase,
        torch.tensor([False]),
        torch.tensor([10]),
        unchecked,
        torch.tensor([0.0]),
        10,
        0.005,
    )
    assert relief_starts_on_boundary_fail["wrong_sign"].tolist() == [True]
    assert relief_starts_on_boundary_fail["actual_arm_write"].tolist() == [False]

    count = torch.tensor([9])
    checked = unchecked
    for _ in range(4):
        spanning_relief = a2_hold_update_phase_arm_sign_check(
            phase,
            torch.tensor([False]),
            count,
            checked,
            torch.tensor([0.0]),
            10,
            0.005,
        )
        count = spanning_relief["count"]
        checked = spanning_relief["checked"]
        assert not spanning_relief["due"].item()
    assert count.item() == 9 and not checked.item()

    clears_at_boundary = a2_hold_update_phase_arm_sign_check(
        phase,
        torch.tensor([True]),
        count,
        checked,
        torch.tensor([0.0]),
        10,
        0.005,
    )
    assert clears_at_boundary["count"].item() == 10
    assert not clears_at_boundary["due"].item()
    check_after_boundary_action = a2_hold_update_phase_arm_sign_check(
        phase,
        torch.tensor([False]),
        clears_at_boundary["count"],
        clears_at_boundary["checked"],
        torch.tensor([0.0]),
        10,
        0.005,
    )
    assert check_after_boundary_action["due"].item()
    assert check_after_boundary_action["wrong_sign"].item()

    count = torch.zeros(1, dtype=torch.long)
    checked = torch.zeros(1, dtype=torch.bool)
    for _ in range(10):
        baseline = a2_hold_update_phase_arm_sign_check(
            phase,
            torch.tensor([True]),
            count,
            checked,
            torch.tensor([0.006]),
            10,
            0.005,
        )
        assert not baseline["due"].item()
        count, checked = baseline["count"], baseline["checked"]
    assert count.item() == 10
    baseline_check = a2_hold_update_phase_arm_sign_check(
        phase,
        torch.tensor([True]),
        count,
        checked,
        torch.tensor([0.006]),
        10,
        0.005,
    )
    assert baseline_check["due"].item()
    assert not baseline_check["wrong_sign"].item()
    assert baseline_check["count"].item() == 11
    no_second_check = a2_hold_update_phase_arm_sign_check(
        phase,
        torch.tensor([True]),
        baseline_check["count"],
        baseline_check["checked"],
        torch.tensor([0.006]),
        10,
        0.005,
    )
    assert not no_second_check["due"].item()


def test_phase_arm_sign_counter_runtime_wiring_and_trace():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert 'self._a2_hold_oracle_phase_step == cfg["sign_smoke_steps"]' not in source
    assert "a2_hold_update_phase_arm_sign_check(" in source
    assert "self._a2_hold_oracle_phase_arm_dls_count[center_ready] = 0" in source
    assert "self._a2_hold_oracle_phase_arm_dls_count[depress_done] = 0" in source
    assert '"hold_oracle_phase_arm_dls_actuation_count"' in source
    assert '"hold_oracle_phase_sign_checked"' in source
    assert '"hold_oracle_phase_sign_check_due_this_step"' in source
    assert "completed_prior_arm_dls_writes_checked_before_current_write" in source


def test_bounded_command_telemetry_is_written_and_exported_distinctly():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    for assignment in (
        "self._a2_hold_oracle_bounded_command_pos_root[:] = bounded_command_pos_root",
        "self._a2_hold_oracle_bounded_command_quat_root[:] = bounded_command_quat_root",
        "self._a2_hold_oracle_bounded_position_step[:] = bounded_position_step",
        "self._a2_hold_oracle_bounded_orientation_step[:] = bounded_orientation_step",
    ):
        assert assignment in source
    trace_keys = (
        '"hold_oracle_final_target_pos_root"',
        '"hold_oracle_final_target_quat_root"',
        '"hold_oracle_final_position_residual"',
        '"hold_oracle_final_orientation_residual"',
        '"hold_oracle_bounded_command_pos_root"',
        '"hold_oracle_bounded_command_quat_root"',
        '"hold_oracle_bounded_position_step"',
        '"hold_oracle_bounded_orientation_step"',
    )
    assert all(source.count(key) == 1 for key in trace_keys)


def test_normal_force_direction_zero_is_invalid_nan():
    force = torch.tensor([[[0.0, 0.0, 0.0], [0.0, 3.0, 4.0]]])
    direction, valid = a2_hold_aggregate_normal_force_direction(force)
    assert valid.tolist() == [[False, True]]
    assert torch.isnan(direction[0, 0]).all()
    torch.testing.assert_close(direction[0, 1], torch.tensor([0.0, 0.6, 0.8]))


def test_effort_estimate_and_saturation_semantics():
    q = torch.tensor([[0.0, -0.035]])
    qdot = torch.tensor([[0.0, 1.0]])
    target = torch.zeros_like(q)
    kp = torch.full_like(q, 80.0)
    kd = torch.full_like(q, 3.0)
    limit = torch.tensor([[10.0, 1.0]])
    raw, clipped, saturated = a2_hold_pd_effort_estimates(q, qdot, target, kp, kd, limit)
    torch.testing.assert_close(raw, torch.tensor([[0.0, -0.2]]), atol=1e-6, rtol=0.0)
    torch.testing.assert_close(clipped, raw)
    assert saturated.tolist() == [[False, False]]


def test_root_rotation_and_source_offset_jacobian():
    jacobian = torch.zeros(1, 6, 2)
    jacobian[0, 3, 0] = 1.0
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    root = a2_hold_rotate_jacobian_to_root(jacobian, identity)
    torch.testing.assert_close(root, jacobian)
    corrected = a2_hold_apply_source_offset_to_jacobian(
        root, torch.tensor([[0.0, 0.0, 0.1]])
    )
    torch.testing.assert_close(corrected[0, :3, 0], torch.tensor([0.0, -0.1, 0.0]))
    # A wrist rotated +90 degrees around local Y maps local +Z TCP offset to root +X.
    r_root = torch.tensor([[0.1, 0.0, 0.0]])
    rotated_wrist_corrected = a2_hold_apply_source_offset_to_jacobian(root, r_root)
    torch.testing.assert_close(
        rotated_wrist_corrected[0, :3, 0], torch.tensor([0.0, 0.0, 0.0])
    )
    jacobian_z_rotation = torch.zeros(1, 6, 1)
    jacobian_z_rotation[0, 5, 0] = 1.0
    rotated_wrist_corrected = a2_hold_apply_source_offset_to_jacobian(
        jacobian_z_rotation, r_root
    )
    torch.testing.assert_close(
        rotated_wrist_corrected[0, :3, 0], torch.tensor([0.0, 0.1, 0.0])
    )


def test_exact_cumulative_conversion_and_disabled_action_equivalence():
    q_default = torch.zeros(1, 6)
    q_des = torch.full((1, 6), 0.075)
    d_prev = torch.full((1, 6), 0.1)
    d_des, raw = a2_hold_absolute_target_to_cumulative_action(q_des, q_default, d_prev)
    torch.testing.assert_close(d_des, torch.full((1, 6), 0.3))
    torch.testing.assert_close(raw, torch.full((1, 6), 2.0 / 3.0))
    action = torch.randn(1, 12)
    disabled = a2_hold_action_with_exact_disabled_equivalence(
        action, torch.tensor([False])
    )
    assert disabled is action
    enabled = a2_hold_action_with_exact_disabled_equivalence(action, torch.tensor([True]))
    assert enabled is not action
    torch.testing.assert_close(enabled, action)


def test_center_transition_sign_and_outcome_summary():
    center = torch.tensor([True, True, True])
    bilateral = torch.tensor([True, False, False])
    steps = torch.tensor([3, 80, 80])
    single7 = torch.tensor([False, True, False])
    single8 = torch.tensor([False, False, False])
    converged = torch.tensor([True, True, False])
    ready, tracking_failure, wedge, no_bilateral = a2_hold_center_transition_masks(
        center, bilateral, steps, 80, single7, single8, converged
    )
    assert ready.tolist() == [True, False, False]
    assert tracking_failure.tolist() == [False, False, True]
    assert wedge.tolist() == [False, True, False]
    assert no_bilateral.tolist() == [False, False, False]
    assert A2_HOLD_PHASE_CENTER_CLOSE != A2_HOLD_PHASE_DEPRESS
    assert a2_hold_positive_sign_pass(torch.tensor([0.01, -0.01]), 0.005).tolist() == [True, False]
    summary = a2_hold_summarize_outcomes(["RETAINED", "CONTACT_SLIP", "RETAINED"])
    assert summary["RETAINED"] == 2
    assert summary["CONTACT_SLIP"] == 1


def test_center_transition_uses_current_not_cached_residual():
    cached_position = torch.tensor([0.001])
    cached_orientation = torch.tensor([0.01])
    current_position = torch.tensor([0.02])
    current_orientation = torch.tensor([0.20])
    assert a2_hold_center_converged(
        cached_position, cached_orientation, 0.005, 0.10
    ).item()
    current_converged = a2_hold_center_converged(
        current_position, current_orientation, 0.005, 0.10
    )
    ready, tracking_failure, wedge, no_bilateral = a2_hold_center_transition_masks(
        torch.tensor([True]),
        torch.tensor([False]),
        torch.tensor([80]),
        80,
        torch.tensor([True]),
        torch.tensor([False]),
        current_converged,
    )
    assert ready.tolist() == [False]
    assert tracking_failure.tolist() == [True]
    assert wedge.tolist() == [False]
    assert no_bilateral.tolist() == [False]
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert 'current_center_pose_state = self._get_a2_hold_oracle_pose_state(' in source
    assert 'current_center_pose_state["position_residual"]' in source


def test_fixed_oracle_offset_signs_are_negative_y_positive_z():
    depress_distance = 0.012
    push_distance = 0.009
    local_depress = torch.tensor([0.0, -depress_distance, 0.0])
    local_push = torch.tensor([0.0, -depress_distance, push_distance])
    assert local_depress[1] < 0.0 and local_depress[2] == 0.0
    assert local_push[1] < 0.0 and local_push[2] > 0.0
    assert math.isclose(float(local_push[2]), push_distance, rel_tol=1.0e-6)


def test_disabled_contact_sensor_equivalence_and_detailed_capacity():
    assert a2_hold_contact_sensor_detail_kwargs(False, None) == {}
    assert a2_hold_contact_sensor_detail_kwargs(True, 8) == {
        "track_pose": True,
        "track_contact_points": True,
        "track_friction_forces": True,
        "max_contact_data_count_per_prim": 8,
    }


def test_non_identity_gripper_task_to_articulation_mapping():
    simulator_dof_ids = [2, 0, 3, 1]
    mapped = a2_hold_map_task_to_articulation_joint_ids(
        simulator_dof_ids,
        torch.tensor([1, 3], dtype=torch.long),
        ["leg", "arm_j7", "arm_j6", "arm_j8"],
        4,
        "cpu",
    )
    assert mapped.tolist() == [0, 1]


def test_friction_override_is_read_only_null_or_explicitly_unsupported():
    assert a2_hold_validate_friction_override(None) is None
    for value in (1.0, 0.5, "1.0"):
        try:
            a2_hold_validate_friction_override(value)
        except ValueError as exc:
            assert "unsupported for the instanceable Piper collider" in str(exc)
            assert "CONTACT_SLIP" in str(exc)
        else:
            raise AssertionError("non-null friction override was not rejected")
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "Usd.TraverseInstanceProxies()" in source
    assert "bind_physics_material" not in source


def test_depress_success_wins_at_timeout_boundary_and_push_timeout_is_causal():
    depress = torch.tensor([True, True])
    done = torch.tensor([True, False])
    step = torch.tensor([100, 100])
    assert a2_hold_depress_timeout_mask(depress, done, step, 100).tolist() == [False, True]
    # CONTACT_SLIP/WRONG_SIGN set outcome non-pending before the same-tick target check.
    pending = torch.tensor([False, False, True])
    reached = torch.tensor([True, True, True])
    transition = a2_hold_depress_transition_mask(
        torch.tensor([True, True, True]), reached, pending
    )
    assert transition.tolist() == [False, False, True]
    timeout = a2_hold_depress_timeout_mask(
        torch.tensor([True, True, True]), reached, torch.tensor([100, 100, 100]), 100
    )
    assert timeout.tolist() == [False, False, False]
    push = torch.tensor([True, True, True])
    reached = torch.tensor([True, False, False])
    step = torch.tensor([150, 150, 150])
    delta = torch.tensor([0.20, 0.001, 0.05])
    no_progress, timeout = a2_hold_push_timeout_masks(
        push, reached, step, 150, delta, 0.005
    )
    assert no_progress.tolist() == [False, True, False]
    assert timeout.tolist() == [False, False, True]


def test_open_stabilization_quaternion_pose_math_and_exact_action():
    identity = torch.tensor([[[1.0, 0.0, 0.0, 0.0]], [[-1.0, 0.0, 0.0, 0.0]]])
    zero_angle = a2_hold_quaternion_geodesic_rad(identity[0], identity[1])
    torch.testing.assert_close(zero_angle, torch.zeros_like(zero_angle))
    positions = torch.zeros(5, 1, 3)
    positions[:, 0, 0] = torch.tensor([0.0, 0.0001, 0.0002, 0.0003, 0.0004])
    quaternions = torch.zeros(5, 1, 4)
    quaternions[:, :, 0] = 1.0
    quaternions[1::2] *= -1.0
    metrics = a2_hold_pose_motion_metrics(positions, quaternions)
    torch.testing.assert_close(
        metrics["per_call_translation_max"], torch.tensor([0.0001])
    )
    torch.testing.assert_close(metrics["window_translation"], torch.tensor([0.0004]))
    torch.testing.assert_close(metrics["per_call_rotation_max"], torch.tensor([0.0]))
    action = torch.arange(24, dtype=torch.float32).reshape(2, 12)
    applied = a2_hold_open_stabilization_action(
        action, torch.tensor([True, False])
    )
    torch.testing.assert_close(applied[0, :11], torch.zeros(11))
    assert applied[0, 11].item() == 1.0
    torch.testing.assert_close(applied[1], action[1])


def test_open_stabilization_pose_window_includes_35_to_36_and_q_sign_is_invariant():
    positions = torch.zeros(6, 1, 3)
    positions[1:, 0, 0] = 0.0006
    quaternions = torch.zeros(6, 1, 4)
    quaternions[:, :, 0] = 1.0
    quaternions[1::2] *= -1.0
    metrics = a2_hold_pose_motion_metrics(positions, quaternions)
    assert metrics["per_call_translation_max"].item() > 0.0005
    assert not bool(
        (metrics["per_call_translation_max"] <= 0.0005).item()
        and (metrics["per_call_rotation_max"] <= 0.0005).item()
        and (metrics["window_translation"] <= 0.001).item()
        and (metrics["window_rotation"] <= 0.002).item()
    )
    torch.testing.assert_close(metrics["per_call_rotation_max"], torch.tensor([0.0]))


def test_open_stabilization_runtime_invariants_fail_immediately_by_class():
    captured = torch.zeros(2, 6)
    accumulated = captured.clone()
    post_delta = captured.clone()
    stiffness = torch.full((2, 2), 80.0)
    damping = torch.full((2, 2), 3.0)
    effort = torch.full((2, 2), 10.0)
    result = a2_hold_validate_open_stabilization_runtime_invariants(
        captured, accumulated, post_delta, stiffness, damping, effort
    )
    assert all(torch.all(value).item() for value in result.values())
    cases = (
        ("accumulated arm target", {"accumulated": accumulated.clone()}),
        ("post-delta arm target", {"post_delta": post_delta.clone()}),
        ("Kp/Kd/effort", {"stiffness": stiffness.clone()}),
    )
    cases[0][1]["accumulated"][1, 0] = 0.1
    cases[1][1]["post_delta"][1, 0] = 0.1
    cases[2][1]["stiffness"][1, 0] = 81.0
    for expected, override in cases:
        args = {
            "captured_arm_target": captured,
            "accumulated_arm_target": accumulated,
            "post_delta_arm_target": post_delta,
            "stiffness": stiffness,
            "damping": damping,
            "effort_limit": effort,
        }
        key_map = {
            "accumulated": "accumulated_arm_target",
            "post_delta": "post_delta_arm_target",
            "stiffness": "stiffness",
        }
        for key, value in override.items():
            args[key_map[key]] = value
        try:
            a2_hold_validate_open_stabilization_runtime_invariants(**args)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"{expected} mismatch did not fail immediately")


def test_open_stabilization_terminal_priority_mixed_async_and_overrun():
    affected = torch.tensor([True, True, True, True, False])
    count = torch.tensor([0, 39, 40, 39, 40])
    contact = torch.tensor([True, True, False, False, True])
    gate = torch.tensor([False, True, False, True, False])
    result = a2_hold_open_stabilization_terminal_partition(
        affected, count, contact, gate, 40
    )
    assert result["contact_contaminated"].tolist() == [True, True, False, False, False]
    assert result["gate_lost"].tolist() == [False, False, True, False, False]
    assert result["endpoint"].tolist() == [False, False, False, False, False]
    assert result["incomplete"].tolist() == [False, False, False, True, False]
    endpoint = a2_hold_open_stabilization_terminal_partition(
        torch.tensor([True]),
        torch.tensor([40]),
        torch.tensor([False]),
        torch.tensor([True]),
        40,
    )
    assert endpoint["endpoint"].item()
    try:
        a2_hold_open_stabilization_terminal_partition(
            torch.tensor([True]),
            torch.tensor([41]),
            torch.tensor([False]),
            torch.tensor([True]),
            40,
        )
    except ValueError as exc:
        assert "exceeded" in str(exc)
    else:
        raise AssertionError("action41 did not fail fast")


def test_open_stabilization_parser_locked_tuple_and_mutual_exclusion():
    cfg = _valid_oracle_config()
    cfg["a2_hold_oracle_open_stabilization_preflight_enabled"] = True
    parsed = parse_a2_hold_oracle_config(cfg)
    assert parsed["open_stabilization_steps"] == 40
    assert parsed["open_stabilization_quiet_window_steps"] == 5
    for mutation in (
        {"a2_hold_oracle_open_stabilization_steps": 41},
        {"a2_hold_oracle_open_stabilization_quiet_window_steps": 4},
        {"a2_hold_oracle_open_stabilization_contact_force_max_n": 1.1},
        {"a2_hold_oracle_static_clamp_enabled": True},
        {"a2_hold_oracle_static_clamp_offset_probe_enabled": True},
    ):
        invalid = dict(cfg)
        invalid.update(mutation)
        try:
            parse_a2_hold_oracle_config(invalid)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"invalid stabilization tuple accepted: {mutation}")


def test_open_stabilization_lifecycle_wiring_no_dls_gain_or_relief():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    methods = {
        node.name: ast.get_source_segment(source, node)
        for node in door.body
        if isinstance(node, ast.FunctionDef)
    }
    apply_source = methods["_apply_a2_open_stabilization_action"]
    assert "a2_hold_open_stabilization_action" in apply_source
    assert "_compute_a2_offset_placement_arm_raw" not in apply_source
    assert "_apply_a2_static_clamp_gains" not in apply_source
    assert "base_relief_command" not in apply_source
    assert "action_count[override] += 1" in apply_source
    trace_source = methods["_get_a2_hold_oracle_trace_fields"]
    assert "_capture_a2_open_stabilization_post_action_samples" in trace_source
    reset_source = methods["_reset_buffers_callback"]
    assert reset_source.index("_finish_a2_open_stabilization") < reset_source.index(
        "super()._reset_buffers_callback"
    )
    finalize_source = methods["finalize_a2_eval_hold_oracle"]
    assert "_finish_a2_open_stabilization" in finalize_source
    summary_source = methods["get_a2_hold_oracle_summary"]
    assert "ARM0_OPEN_STABILIZATION_PREFLIGHT" in summary_source
    preflight_return = summary_source.split(
        '"preflight": "ARM0_OPEN_STABILIZATION_PREFLIGHT"', 1
    )[1].split("return {", 1)[0]
    assert "static_clamp_restored" not in preflight_return


def test_open_stabilization_behavioral_quiet_window_rejects_only_35_to_36_spike():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    method = next(
        node for node in door.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_evaluate_a2_open_stabilization_quiet_window"
    )
    namespace = {
        "torch": torch,
        "a2_hold_pose_motion_metrics": a2_hold_pose_motion_metrics,
    }
    exec(textwrap.dedent(ast.get_source_segment(source, method)), namespace)

    class Dummy:
        _evaluate_a2_open_stabilization_quiet_window = namespace[
            "_evaluate_a2_open_stabilization_quiet_window"
        ]

        def __init__(self):
            self.device = "cpu"
            self._a2_hold_oracle_cfg = {
                "open_stabilization_steps": 40,
                "open_stabilization_quiet_window_steps": 5,
                "open_stabilization_root_linear_speed_max_mps": 0.01,
                "open_stabilization_root_angular_speed_max_radps": 0.02,
                "open_stabilization_pose_per_call_translation_max_m": 0.0005,
                "open_stabilization_pose_per_call_rotation_max_rad": 0.0005,
                "open_stabilization_pose_window_translation_max_m": 0.001,
                "open_stabilization_pose_window_rotation_max_rad": 0.002,
                "open_stabilization_contact_force_max_n": 1.0,
            }
            self._a2_hold_oracle_open_stabilization_gate_root_pos_w = torch.zeros(1, 3)
            self._a2_hold_oracle_open_stabilization_gate_root_quat_w = torch.tensor(
                [[1.0, 0.0, 0.0, 0.0]]
            )
            samples = []
            for action in range(1, 41):
                position = [0.0, 0.0, 0.0]
                if action >= 36:
                    position[0] = 0.0006
                quat = [1.0, 0.0, 0.0, 0.0]
                if action % 2:
                    quat[0] = -1.0
                sample = {
                    "action": action,
                    "root_linear_speed_mps": 0.0,
                    "root_angular_speed_radps": 0.0,
                    "handle_filter_force_norm_body7_body8": [0.0, 0.0],
                    "composite_gate": True,
                }
                for position_key, quaternion_key in (
                    ("root_pos_w", "root_quat_w"),
                    (
                        "frozen_gate_source_pos_root",
                        "frozen_gate_source_quat_root",
                    ),
                    ("source_pos_root", "source_quat_root"),
                    ("handle_pos_w", "handle_quat_w"),
                ):
                    sample[position_key] = list(position)
                    sample[quaternion_key] = list(quat)
                samples.append(sample)
            self._a2_hold_oracle_open_stabilization_samples = [samples]

    result = Dummy()._evaluate_a2_open_stabilization_quiet_window(0)
    assert result["quiet_window_actions"] == [36, 37, 38, 39, 40]
    assert result["pose_window_actions"] == [35, 36, 37, 38, 39, 40]
    assert result["pose_transition_actions"][0] == [35, 36]
    assert not result["ready"]
    assert not result["reason_booleans"]["pose_motion_ok"]
    assert all(
        metrics["per_call_rotation_max"] == 0.0
        for metrics in result["pose_motion"].values()
    )


def test_open_stabilization_yaml_defaults_are_locked_and_default_off():
    eval_yaml = (Path(__file__).parents[1] / "config/base_eval.yaml").read_text()
    for exact in (
        "a2_hold_oracle_open_stabilization_preflight_enabled: false",
        "a2_hold_oracle_open_stabilization_steps: 40",
        "a2_hold_oracle_open_stabilization_quiet_window_steps: 5",
        "a2_hold_oracle_open_stabilization_root_linear_speed_max_mps: 0.01",
        "a2_hold_oracle_open_stabilization_root_angular_speed_max_radps: 0.02",
        "a2_hold_oracle_open_stabilization_pose_per_call_translation_max_m: 0.0005",
        "a2_hold_oracle_open_stabilization_pose_per_call_rotation_max_rad: 0.0005",
        "a2_hold_oracle_open_stabilization_pose_window_translation_max_m: 0.001",
        "a2_hold_oracle_open_stabilization_pose_window_rotation_max_rad: 0.002",
        "a2_hold_oracle_open_stabilization_contact_force_max_n: 1.0",
    ):
        assert exact in eval_yaml


def test_nullable_diagnostic_record_is_strict_json():
    record = {
        "contact": a2_hold_nullable_tensor_list(
            torch.tensor([[float("nan"), 1.0, float("nan")]])
        ),
        "valid": [False],
        "condition": a2_hold_nullable_tensor_list(torch.tensor(float("inf"))),
    }
    encoded = json.dumps(record, allow_nan=False)
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert json.loads(encoded)["contact"] == [[None, 1.0, None]]
    try:
        MAKE_JSON_SAFE({"unexpected": float("nan")})
    except ValueError as exc:
        assert "Non-finite" in str(exc)
    else:
        raise AssertionError("generic unexpected non-finite value did not fail")


def test_legacy_a2_hold_config_migration_complete_present_partial_and_non_a2():
    migrate = EVAL_MIGRATION["migrate_legacy_a2_hold_diagnostic_env_config"]
    defaults = EVAL_MIGRATION["_A2_HOLD_DIAGNOSTIC_ENV_CONFIG_DEFAULTS"]
    legacy = OmegaConf.create(
        {
            "algo": {"config": {"use_a2_base": True}},
            "robot": {"asset": {"robot_type": "a2_piper"}},
            "env": {"config": {}},
        }
    )
    migrate(legacy, "base_v9/config.yaml")
    assert OmegaConf.to_container(legacy.env.config, resolve=True) == defaults
    migrate(legacy, "base_v9/config.yaml")
    partial = OmegaConf.create(
        {
            "algo": {"config": {"use_a2_base": True}},
            "robot": {"asset": {"robot_type": "a2_piper"}},
            "env": {"config": {"a2_gripper_source_tcp_offset_z": 0.085}},
        }
    )
    try:
        migrate(partial, "partial/config.yaml")
    except RuntimeError as exc:
        assert "Partial legacy" in str(exc) and "missing=" in str(exc)
    else:
        raise AssertionError("partial legacy diagnostic group did not fail")
    non_a2 = OmegaConf.create(
        {
            "algo": {"config": {"use_a2_base": False}},
            "robot": {"asset": {"robot_type": "g1"}},
            "env": {"config": {}},
        }
    )
    migrate(non_a2, "g1/config.yaml")
    assert len(non_a2.env.config) == 0


def test_matched_clean_reacquisition_parser_default_tuple_and_mutual_exclusion():
    config = _valid_oracle_config(enabled=False)
    parsed = parse_a2_hold_oracle_config(config)
    assert parsed["matched_clean_reacquisition_preflight_enabled"] is False

    config = _valid_oracle_config(enabled=True)
    config["a2_hold_oracle_matched_clean_reacquisition_preflight_enabled"] = True
    parsed = parse_a2_hold_oracle_config(config)
    assert parsed["matched_clean_retreat_timeout_steps"] == 80
    assert parsed["matched_clean_release_qualification_steps"] == 5
    assert parsed["matched_clean_pregrasp_position_tolerance_m"] == 0.005
    assert parsed["matched_clean_pregrasp_orientation_tolerance_rad"] == 0.10

    conflicts = (
        {"a2_hold_oracle_static_clamp_enabled": True},
        {
            "a2_hold_oracle_static_clamp_enabled": True,
            "a2_hold_oracle_static_clamp_offset_probe_enabled": True,
            "a2_hold_oracle_static_clamp_stiffness": 160.0,
            "a2_hold_oracle_static_clamp_damping": 6.0,
        },
        {"a2_hold_oracle_open_stabilization_preflight_enabled": True},
    )
    for conflict_values in conflicts:
        conflict = dict(config)
        conflict.update(conflict_values)
        try:
            parse_a2_hold_oracle_config(conflict)
        except RuntimeError as exc:
            assert "mutually exclusive" in str(exc) or "mutually exclusive" in str(exc)
        else:
            raise AssertionError(f"matched-clean conflict {conflict_values} did not fail")

    disabled = _valid_oracle_config(enabled=False)
    disabled["a2_hold_oracle_matched_clean_reacquisition_preflight_enabled"] = True
    try:
        parse_a2_hold_oracle_config(disabled)
    except RuntimeError as exc:
        assert "requires a2_hold_oracle_enabled" in str(exc)
    else:
        raise AssertionError("matched-clean preflight without hold oracle did not fail")

    bad_timeout = dict(config)
    bad_timeout["a2_hold_oracle_matched_clean_retreat_timeout_steps"] = 79
    try:
        parse_a2_hold_oracle_config(bad_timeout)
    except RuntimeError as exc:
        assert "retreat_timeout_steps" in str(exc)
    else:
        raise AssertionError("matched-clean timeout 79 did not fail")

    inherited_exact = {
        "a2_hold_oracle_open_stabilization_steps": 40,
        "a2_hold_oracle_open_stabilization_quiet_window_steps": 5,
        "a2_hold_oracle_open_stabilization_root_linear_speed_max_mps": 0.01,
        "a2_hold_oracle_open_stabilization_root_angular_speed_max_radps": 0.02,
        "a2_hold_oracle_open_stabilization_pose_per_call_translation_max_m": 0.0005,
        "a2_hold_oracle_open_stabilization_pose_per_call_rotation_max_rad": 0.0005,
        "a2_hold_oracle_open_stabilization_pose_window_translation_max_m": 0.001,
        "a2_hold_oracle_open_stabilization_pose_window_rotation_max_rad": 0.002,
        "a2_hold_oracle_open_stabilization_contact_force_max_n": 1.0,
    }
    for key, exact in inherited_exact.items():
        mutated = dict(config)
        mutated[key] = exact + 1
        try:
            parse_a2_hold_oracle_config(mutated)
        except RuntimeError as exc:
            assert key.removeprefix("a2_hold_oracle_") in str(exc)
        else:
            raise AssertionError(f"matched-clean inherited tuple mutation {key} parsed")


def test_matched_clean_release_action_qualification_and_rotated_pregrasp_wiring():
    policy = torch.arange(24, dtype=torch.float32).reshape(2, 12)
    arm_raw = torch.tensor([[0.1, 0.2, 0.3, 0.4, 0.5, 0.6], [-1.0] * 6])
    applied = a2_hold_matched_clean_release_action(
        policy, torch.tensor([True, False]), arm_raw
    )
    torch.testing.assert_close(applied[0, :5], torch.zeros(5))
    torch.testing.assert_close(applied[0, 5:11], arm_raw[0])
    assert applied[0, 11].item() == 1.0
    torch.testing.assert_close(applied[1], policy[1])

    qualified = a2_hold_matched_clean_release_qualification(
        torch.tensor([0.005, 0.005]),
        torch.tensor([0.10, 0.10]),
        torch.tensor([[0.999, 0.999], [1.0, 0.0]]),
        torch.tensor([0.095, 0.095]),
    )
    assert qualified.tolist() == [True, False]
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "target_pos_w[:, 1, :]" in source
    assert "target_quat_w[:, 1, :]" in source
    assert "pregrasp_pos_w" in source
    assert "A2 matched-clean live OrderedTargetFrameTransformer" in source
    assert "target_frames[1]" not in source


def test_matched_clean_release_async_contact_reset_and_action80_priority():
    state = a2_hold_matched_clean_release_step_masks(
        torch.tensor([True, True, True]),
        torch.tensor([True, True, True]),
        torch.tensor([80, 79, 79], dtype=torch.long),
        torch.tensor([4, 4, 4], dtype=torch.long),
        torch.tensor([False, True, False]),
        torch.tensor([False, False, True]),
        80,
        5,
    )
    assert state["qualified_now"].tolist() == [False, True, False]
    assert state["timeout"].tolist() == [True, False, False]
    assert state["contact_reset"].tolist() == [False, False, True]
    assert state["qualification_count"].tolist() == [0, 5, 0]
    assert state["active"].tolist() == [False, False, True]

    boundary = a2_hold_matched_clean_release_step_masks(
        torch.tensor([True]),
        torch.tensor([True]),
        torch.tensor([80], dtype=torch.long),
        torch.tensor([4], dtype=torch.long),
        torch.tensor([True]),
        torch.tensor([False]),
        80,
        5,
    )
    assert boundary["qualified_now"].item()
    assert not boundary["timeout"].item()


def test_matched_clean_stabilization_contact_priority_action40_and_action41_fail_fast():
    partition = a2_hold_matched_clean_stabilization_terminal_partition(
        torch.tensor([True, True, True, False]),
        torch.tensor([40, 39, 40, 41], dtype=torch.long),
        torch.tensor([True, False, False, False]),
        40,
    )
    assert partition["contact_contaminated"].tolist() == [True, False, False, False]
    assert partition["endpoint"].tolist() == [False, False, True, False]
    assert partition["incomplete"].tolist() == [False, True, False, False]
    try:
        a2_hold_matched_clean_stabilization_terminal_partition(
            torch.tensor([True]),
            torch.tensor([41], dtype=torch.long),
            torch.tensor([False]),
            40,
        )
    except ValueError as exc:
        assert "exceeded exact target" in str(exc)
    else:
        raise AssertionError("matched-clean action41 did not fail fast")

    eval_yaml = (Path(__file__).parents[1] / "config/base_eval.yaml").read_text()
    assert "a2_hold_oracle_matched_clean_reacquisition_preflight_enabled: false" in eval_yaml
    assert "a2_hold_oracle_matched_clean_retreat_timeout_steps: 80" in eval_yaml
    assert "a2_hold_oracle_matched_clean_release_qualification_steps: 5" in eval_yaml


def test_matched_clean_method_handoff_skips_same_step_stabilize_and_next_action_is_one():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    method_nodes = {
        node.name: node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "_capture_a2_matched_clean_release_post_action_samples",
            "_capture_a2_matched_clean_stabilize_post_action_samples",
            "_apply_a2_matched_clean_reacquisition_action",
        }
    }
    namespace = {
        "torch": torch,
        "a2_hold_matched_clean_release_qualification": a2_hold_matched_clean_release_qualification,
        "a2_hold_matched_clean_release_step_masks": a2_hold_matched_clean_release_step_masks,
        "a2_hold_matched_clean_release_action": a2_hold_matched_clean_release_action,
        "A2_HOLD_PHASE_WAIT_GATE": A2_HOLD_PHASE_WAIT_GATE,
        "A2_HOLD_PHASE_MATCHED_CLEAN_RELEASE_RETREAT": A2_HOLD_PHASE_MATCHED_CLEAN_RELEASE_RETREAT,
        "A2_HOLD_PHASE_MATCHED_CLEAN_STABILIZE": A2_HOLD_PHASE_MATCHED_CLEAN_STABILIZE,
        "A2_HOLD_PHASE_DONE": A2_HOLD_PHASE_DONE,
        "A2_HOLD_OUTCOME_TO_ID": A2_HOLD_OUTCOME_TO_ID,
    }
    for node in method_nodes.values():
        exec(textwrap.dedent(ast.get_source_segment(source, node)), namespace)

    class Dummy:
        _capture_a2_matched_clean_release_post_action_samples = namespace[
            "_capture_a2_matched_clean_release_post_action_samples"
        ]
        _capture_a2_matched_clean_stabilize_post_action_samples = namespace[
            "_capture_a2_matched_clean_stabilize_post_action_samples"
        ]
        _apply_a2_matched_clean_reacquisition_action = namespace[
            "_apply_a2_matched_clean_reacquisition_action"
        ]

        def __init__(self):
            self.num_envs = 1
            self.device = torch.device("cpu")
            self._a2_hold_oracle_cfg = {
                "enabled": True,
                "matched_clean_reacquisition_preflight_enabled": True,
                "matched_clean_retreat_timeout_steps": 80,
                "matched_clean_release_qualification_steps": 5,
                "matched_clean_pregrasp_position_tolerance_m": 0.005,
                "matched_clean_pregrasp_orientation_tolerance_rad": 0.10,
            }
            self._a2_hold_oracle_matched_clean_release_active = torch.tensor([True])
            self._a2_hold_oracle_matched_clean_stabilize_active = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_stabilize_action_count = torch.tensor(
                [0], dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_release_override_mask = torch.tensor([True])
            self._a2_hold_oracle_matched_clean_stabilize_override_mask = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_release_action_count = torch.tensor([1], dtype=torch.long)
            self._a2_hold_oracle_matched_clean_qualification_count = torch.tensor([0], dtype=torch.long)
            self._a2_hold_oracle_matched_clean_release_contact_reset_count = torch.tensor([0], dtype=torch.long)
            self._a2_hold_oracle_matched_clean_gate_lost_ever = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_samples = [[]]
            self._a2_hold_oracle_matched_clean_quiet_samples = [[]]
            self._a2_hold_oracle_matched_clean_captured_arm_target = torch.full((1, 6), float("nan"))
            self._a2_hold_oracle_matched_clean_release_qualification_evidence = [None]
            self._a2_hold_oracle_matched_clean_release_final_action_count = torch.tensor([-1], dtype=torch.long)
            self._a2_hold_oracle_matched_clean_reason_timeout = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_reason_incomplete = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_result = [None]
            self._a2_hold_oracle_matched_clean_ever_activated = torch.tensor([True])
            self._a2_hold_oracle_activated = torch.tensor([True])
            self._a2_hold_oracle_phase = torch.tensor(
                [A2_HOLD_PHASE_MATCHED_CLEAN_RELEASE_RETREAT], dtype=torch.long
            )
            self._a2_hold_oracle_phase_step = torch.tensor([1], dtype=torch.long)
            self._a2_hold_oracle_outcome = torch.tensor([A2_HOLD_OUTCOME_TO_ID["PENDING"]], dtype=torch.long)
            self._a2_hold_oracle_last_override_mask = torch.tensor([True])
            self._a2_hold_oracle_matched_clean_last_override_mask = torch.tensor([True])
            self._a2_hold_oracle_a_raw = torch.zeros(1, 6)
            self._a2_hold_oracle_arm_dls_branch = torch.tensor([True])
            self._a2_hold_oracle_base_relief_branch_applied = torch.tensor([False])
            self._a2_hold_oracle_phase_sign_check_due = torch.tensor([False])
            self._a2_hold_oracle_post_override_action = torch.ones(1, 12)
            self._a2_eval_post_delta_post_warp_env_action = torch.zeros(1, 12)
            self._delta_actions = torch.arange(6, dtype=torch.float32).reshape(1, 6)

            self._a2_hold_oracle_matched_clean_release_ik_invalid = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_release_joint_limit = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_release_action_invalid = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_release_override_mask = torch.tensor([True])
            self._a2_hold_oracle_matched_clean_stabilize_override_mask = torch.tensor([False])

        def _get_a2_matched_clean_reacquisition_pose_state(self):
            return {
                "frames": {},
                "position_residual": torch.tensor([0.001]),
                "orientation_residual": torch.tensor([0.01]),
                "source_handle_distance": torch.tensor([0.10]),
            }

        def _get_a2_open_stabilization_contact_force_norm(self):
            return torch.tensor([[0.2, 0.3]])

        def _get_a2_open_stabilization_composite_gate(self):
            return torch.tensor([True])

        def _set_a2_hold_outcome(self, mask, outcome):
            self._a2_hold_oracle_outcome[mask] = A2_HOLD_OUTCOME_TO_ID[outcome]
            self._a2_hold_oracle_phase[mask] = A2_HOLD_PHASE_DONE

        def _finish_a2_matched_clean_reacquisition(self, mask):
            if torch.any(mask):
                raise AssertionError("handoff test unexpectedly finished active state")

        def _compute_a2_matched_clean_retreat_arm_raw(self, active):
            return torch.zeros(1, 6), active.clone()

    dummy = Dummy()
    for action in range(1, 6):
        dummy._a2_hold_oracle_matched_clean_release_action_count[:] = action
        dummy._a2_hold_oracle_matched_clean_release_override_mask[:] = True
        dummy._capture_a2_matched_clean_release_post_action_samples()
    assert not dummy._a2_hold_oracle_matched_clean_release_active.item()
    assert dummy._a2_hold_oracle_matched_clean_stabilize_active.item()
    assert dummy._a2_hold_oracle_matched_clean_stabilize_action_count.item() == 0
    dummy._capture_a2_matched_clean_stabilize_post_action_samples()
    assert dummy._a2_hold_oracle_matched_clean_quiet_samples == [[]]

    action, override = dummy._apply_a2_matched_clean_reacquisition_action(
        torch.full((1, 12), 7.0),
        torch.tensor([True]),
        torch.tensor([False]),
    )
    assert override.tolist() == [True]
    assert dummy._a2_hold_oracle_matched_clean_stabilize_action_count.item() == 1
    torch.testing.assert_close(action[0, :11], torch.zeros(11))
    assert action[0, 11].item() == 1.0
    assert dummy._a2_hold_oracle_matched_clean_stabilize_override_mask.tolist() == [True]


def test_matched_clean_invalid_retreat_is_done_and_result_populated():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    apply_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_apply_a2_matched_clean_reacquisition_action"
    )
    namespace = dict(globals())
    exec(textwrap.dedent(ast.get_source_segment(source, apply_node)), namespace)

    class Dummy:
        _apply_a2_matched_clean_reacquisition_action = namespace[
            "_apply_a2_matched_clean_reacquisition_action"
        ]

        def __init__(self):
            self.num_envs = 1
            self.device = torch.device("cpu")
            self._a2_hold_oracle_cfg = {
                "matched_clean_reacquisition_preflight_enabled": True,
                "matched_clean_retreat_timeout_steps": 80,
            }
            self._a2_hold_oracle_phase = torch.tensor(
                [A2_HOLD_PHASE_MATCHED_CLEAN_RELEASE_RETREAT], dtype=torch.long
            )
            self._a2_hold_oracle_phase_step = torch.tensor([4], dtype=torch.long)
            self._a2_hold_oracle_outcome = torch.tensor(
                [A2_HOLD_OUTCOME_TO_ID["PENDING"]], dtype=torch.long
            )
            self._a2_hold_oracle_activated = torch.tensor([True])
            self._a2_hold_oracle_a_raw = torch.zeros(1, 6)
            self._a2_hold_oracle_arm_dls_branch = torch.tensor([True])
            self._a2_hold_oracle_base_relief_branch_applied = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_release_active = torch.tensor([True])
            self._a2_hold_oracle_matched_clean_stabilize_active = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_stabilize_action_count = torch.tensor(
                [0], dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_ever_activated = torch.tensor([True])
            self._a2_hold_oracle_matched_clean_release_action_count = torch.tensor(
                [4], dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_qualification_count = torch.tensor(
                [0], dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_release_override_mask = torch.tensor([True])
            self._a2_hold_oracle_matched_clean_stabilize_override_mask = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_release_ik_invalid = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_release_joint_limit = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_release_action_invalid = torch.tensor([False])
            self._a2_hold_oracle_matched_clean_release_final_action_count = torch.tensor(
                [-1], dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_result = [None]

        def _compute_a2_matched_clean_retreat_arm_raw(self, active_mask):
            self._a2_hold_oracle_matched_clean_release_ik_invalid[active_mask] = True
            return torch.zeros(1, 6), torch.zeros(1, dtype=torch.bool)

        def _finish_a2_matched_clean_reacquisition(self, mask):
            if torch.any(mask):
                raise AssertionError("invalid retreat should terminalize before finalization")

        def _set_a2_hold_outcome(self, mask, outcome):
            pending = mask & (
                self._a2_hold_oracle_outcome == A2_HOLD_OUTCOME_TO_ID["PENDING"]
            )
            self._a2_hold_oracle_outcome[pending] = A2_HOLD_OUTCOME_TO_ID[outcome]
            self._a2_hold_oracle_phase[pending] = A2_HOLD_PHASE_DONE

    dummy = Dummy()
    action, override = dummy._apply_a2_matched_clean_reacquisition_action(
        torch.full((1, 12), 3.0),
        torch.tensor([True]),
        torch.tensor([False]),
    )
    assert not override.item()
    assert not dummy._a2_hold_oracle_matched_clean_release_active.item()
    assert dummy._a2_hold_oracle_phase.item() == A2_HOLD_PHASE_DONE
    assert (
        dummy._a2_hold_oracle_outcome.item()
        == A2_HOLD_OUTCOME_TO_ID["MATCHED_CLEAN_RETREAT_IK_INVALID"]
    )
    assert dummy._a2_hold_oracle_matched_clean_result[0] == {
        "ready": False,
        "outcome": "MATCHED_CLEAN_RETREAT_IK_INVALID",
        "final_release_action_count": 4,
    }
    assert dummy._a2_hold_oracle_matched_clean_release_final_action_count.item() == 4
    torch.testing.assert_close(action, torch.full((1, 12), 3.0))


def test_matched_clean_dls_keeps_inactive_rows_at_current_pose_and_telemetry():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    compute_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_compute_a2_matched_clean_retreat_arm_raw"
    )
    namespace = dict(globals())
    exec(textwrap.dedent(ast.get_source_segment(source, compute_node)), namespace)

    class _View:
        def __init__(self, jacobian):
            self._jacobian = jacobian

        def get_jacobians(self):
            return self._jacobian

    class _Robot:
        def __init__(self, jacobian):
            self.root_physx_view = _View(jacobian)

            class _Data:
                pass

            self.data = _Data()
            self.data.joint_pos = torch.zeros(2, 6)
            self.data.joint_pos_limits = torch.tensor(
                [[[-3.0, 3.0]] * 6, [[-3.0, 3.0]] * 6], dtype=torch.float32
            )
            self.data.soft_joint_pos_limits = self.data.joint_pos_limits.clone()
            self.data.default_joint_pos = torch.zeros(2, 6)

    class _Controller:
        def __init__(self):
            self.command = None

        def set_command(self, command):
            self.command = command.clone()

        def compute(self, current_pos, current_quat, jacobian, joint_pos):
            return joint_pos.clone()

    class Dummy:
        _compute_a2_matched_clean_retreat_arm_raw = namespace[
            "_compute_a2_matched_clean_retreat_arm_raw"
        ]

        def __init__(self):
            self.num_envs = 2
            self.device = torch.device("cpu")
            self._a2_hold_oracle_cfg = {
                "jacobian_condition_max": 1.0e6,
                "max_position_step_m": 0.002,
                "max_orientation_step_rad": 0.02,
                "dls_lambda": 0.01,
                "joint_limit_margin": 1.0e-4,
                "soft_limit_progress_tolerance": 1.0e-6,
                "raw_action_abs_max": 10.0,
            }
            self._a2_hold_oracle_jacobian_body_id = 0
            self._a2_hold_oracle_jacobian_joint_ids = list(range(6))
            self._a2_hold_oracle_joint_ids = list(range(6))
            self._delta_actions = torch.zeros(2, 6)
            self._a2_hold_oracle_controller = _Controller()
            identity_jacobian = torch.eye(6).expand(2, 1, 6, 6).clone()
            robot = _Robot(identity_jacobian)
            identity_quat = torch.zeros(2, 4)
            identity_quat[:, 0] = 1.0
            root_pos = torch.zeros(2, 3)
            source_pos = torch.tensor([[0.0, 0.0, 0.0], [0.25, 0.0, 0.0]])
            target_pos = torch.tensor([[0.1, 0.0, 0.0], [0.9, 0.0, 0.0]])
            self._pose = {
                "frames": {
                    "robot": robot,
                    "root_pos_w": root_pos,
                    "root_quat_w": identity_quat,
                    "body_pos_w": root_pos.clone(),
                    "body_quat_w": identity_quat.clone(),
                },
                "source_pos_root": source_pos,
                "source_quat_root": identity_quat.clone(),
                "target_pos_root": target_pos,
                "target_quat_root": identity_quat.clone(),
                "position_residual": torch.tensor([0.1, 0.9]),
                "orientation_residual": torch.zeros(2),
            }
            telemetry = {
                "q_des": (2, 6),
                "d_des": (2, 6),
                "d_prev": (2, 6),
                "a_raw": (2, 6),
                "arm_candidate_action_raw": (2, 6),
                "target_pos_root": (2, 3),
                "target_quat_root": (2, 4),
                "bounded_command_pos_root": (2, 3),
                "bounded_command_quat_root": (2, 4),
                "bounded_position_step": (2,),
                "bounded_orientation_step": (2,),
                "position_residual": (2,),
                "orientation_residual": (2,),
                "singular_values": (2, 6),
                "jacobian_condition": (2,),
            }
            for name, shape in telemetry.items():
                setattr(self, f"_a2_hold_oracle_{name}", torch.full(shape, 9.0))
            for name in ("ik_valid", "limit_valid", "delta_ok", "raw_ok"):
                setattr(self, f"_a2_hold_oracle_{name}", torch.tensor([False, True]))
            for name in (
                "matched_clean_release_ik_invalid",
                "matched_clean_release_joint_limit",
                "matched_clean_release_action_invalid",
            ):
                setattr(self, f"_a2_hold_oracle_{name}", torch.tensor([False, True]))
            self._robot = robot

        def _get_a2_matched_clean_reacquisition_pose_state(self):
            return self._pose

    dummy = Dummy()
    active = torch.tensor([True, False])
    arm_raw, active_valid = dummy._compute_a2_matched_clean_retreat_arm_raw(active)
    assert active_valid.tolist() == [True, False]
    assert dummy._a2_hold_oracle_controller.command[1, :3].tolist() == [0.25, 0.0, 0.0]
    torch.testing.assert_close(
        dummy._a2_hold_oracle_controller.command[0, 0], torch.tensor(0.002), rtol=1.0e-5, atol=1.0e-6
    )
    torch.testing.assert_close(arm_raw[1], torch.zeros(6))
    for name in (
        "q_des",
        "d_des",
        "d_prev",
        "a_raw",
        "arm_candidate_action_raw",
        "target_pos_root",
        "target_quat_root",
        "bounded_command_pos_root",
        "bounded_command_quat_root",
        "bounded_position_step",
        "bounded_orientation_step",
        "position_residual",
        "orientation_residual",
        "singular_values",
        "jacobian_condition",
    ):
        value = getattr(dummy, f"_a2_hold_oracle_{name}")
        assert torch.all(value[1] == 9.0), name
    for name in ("ik_valid", "limit_valid", "delta_ok", "raw_ok"):
        value = getattr(dummy, f"_a2_hold_oracle_{name}")
        assert value.tolist() == [True, True], name
    for name in (
        "matched_clean_release_ik_invalid",
        "matched_clean_release_joint_limit",
        "matched_clean_release_action_invalid",
    ):
        value = getattr(dummy, f"_a2_hold_oracle_{name}")
        assert value.tolist() == [False, True], name


def test_matched_clean_reset_finalize_and_summary_wiring_is_terminal_first():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    methods = {
        node.name: ast.get_source_segment(source, node)
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "_reset_buffers_callback",
            "finalize_a2_eval_hold_oracle",
            "get_a2_hold_oracle_summary",
        }
    }
    reset_source = methods["_reset_buffers_callback"]
    assert reset_source.index("_finish_a2_matched_clean_reacquisition(affected)") < reset_source.index(
        "super()._reset_buffers_callback"
    )
    finalize_source = methods["finalize_a2_eval_hold_oracle"]
    assert finalize_source.index(
        "_finish_a2_matched_clean_reacquisition"
    ) < finalize_source.index("self._a2_hold_oracle_finalized = True")
    summary_source = methods["get_a2_hold_oracle_summary"]
    for required in (
        'cfg["matched_clean_reacquisition_preflight_enabled"]',
        "summary requires finalized lifecycle state",
        "summary rejects active preflight state",
        '"per_env_result"',
        '"per_env_release_samples"',
        '"per_env_quiet_samples"',
        '"per_env_actual_invariant_evidence"',
        '"outcome_counts"',
        '"finalize_called"',
        "MATCHED_CLEAN_STABILIZE_CONTACT_CONTAMINATED>",
        "gate_lost_is_telemetry_only",
        "contact_terminal_priority",
    ):
        assert required in summary_source, required


def test_matched_clean_stabilize_actual_method_selects_two_of_eight_targets():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    capture_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_capture_a2_matched_clean_stabilize_post_action_samples"
    )
    namespace = dict(globals())
    exec(textwrap.dedent(ast.get_source_segment(source, capture_node)), namespace)

    class _Node:
        pass

    class _Robot:
        def __init__(self, default_target, actual_target):
            self.data = _Node()
            self.data.root_lin_vel_w = torch.zeros(8, 3)
            self.data.root_ang_vel_w = torch.zeros(8, 3)
            self.data.default_joint_pos = default_target
            self.data.joint_pos_target = actual_target

    class Dummy:
        _capture_a2_matched_clean_stabilize_post_action_samples = namespace[
            "_capture_a2_matched_clean_stabilize_post_action_samples"
        ]

        def __init__(self):
            self.num_envs = 8
            self.device = torch.device("cpu")
            self._a2_hold_oracle_cfg = {}
            active_ids = torch.tensor([2, 6], dtype=torch.long)
            self._active_ids = active_ids
            active = torch.zeros(8, dtype=torch.bool)
            active[active_ids] = True
            self._a2_hold_oracle_matched_clean_stabilize_active = active.clone()
            self._a2_hold_oracle_matched_clean_stabilize_override_mask = active.clone()
            self._a2_hold_oracle_matched_clean_stabilize_action_count = torch.zeros(
                8, dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_stabilize_action_count[active_ids] = 1
            captured = torch.full((8, 6), float("nan"))
            captured[2] = torch.arange(6, dtype=torch.float32) + 0.25
            captured[6] = torch.arange(6, dtype=torch.float32) + 1.25
            self._a2_hold_oracle_matched_clean_captured_arm_target = captured
            self._delta_actions = torch.full((8, 6), 77.0)
            self._delta_actions[active_ids] = captured[active_ids]
            self._a2_eval_post_delta_post_warp_env_action = torch.full((8, 12), 55.0)
            self._a2_eval_post_delta_post_warp_env_action[active_ids, 5:11] = captured[
                active_ids
            ]
            self._a2_hold_oracle_post_override_action = torch.zeros(8, 12)
            self._a2_hold_oracle_joint_ids = list(range(6))
            default_target = torch.arange(48, dtype=torch.float32).reshape(8, 6) / 10.0
            actual_target = torch.full((8, 6), -123.0)
            actual_target[active_ids] = default_target[active_ids] + 0.25 * captured[
                active_ids
            ]
            self._expected_selected_target = actual_target[active_ids].clone()
            self._actual_target_before = actual_target.clone()
            identity_quat = torch.zeros(8, 4)
            identity_quat[:, 0] = 1.0
            root_pos = torch.zeros(8, 3)
            source_pos = torch.arange(24, dtype=torch.float32).reshape(8, 3) / 100.0
            pregrasp_pos = source_pos + 0.01
            self._robot = _Robot(default_target, actual_target)
            self._pose = {
                "frames": {
                    "robot": self._robot,
                    "root_pos_w": root_pos,
                    "root_quat_w": identity_quat,
                    "source_pos_w": source_pos,
                    "source_quat_w": identity_quat.clone(),
                    "pregrasp_pos_w": pregrasp_pos,
                    "pregrasp_quat_w": identity_quat.clone(),
                    "handle_pos_w": source_pos + 0.02,
                    "handle_quat_w": identity_quat.clone(),
                },
                "source_handle_distance": torch.full((8,), 0.10),
            }
            self.config = _Node()
            self.config.robot = _Node()
            self.config.robot.control = _Node()
            self.config.robot.control.action_scale = 0.25
            self._a2_hold_oracle_matched_clean_gate_lost_ever = torch.zeros(
                8, dtype=torch.bool
            )
            self._a2_hold_oracle_matched_clean_quiet_samples = [
                [] if index in active_ids.tolist() else [{"sentinel": index}]
                for index in range(8)
            ]
            self._a2_hold_oracle_matched_clean_actual_invariant_evidence = [
                [] if index in active_ids.tolist() else [{"sentinel": index}]
                for index in range(8)
            ]

        def _get_a2_matched_clean_reacquisition_pose_state(self):
            return self._pose

        def _get_a2_open_stabilization_contact_force_norm(self):
            return torch.zeros(8, 2)

        def _get_a2_static_clamp_gripper_state(self, env_ids):
            shape = (env_ids.numel(), 2)
            return None, None, {
                "stiffness": torch.full(shape, 80.0),
                "damping": torch.full(shape, 3.0),
                "effort_limit": torch.full(shape, 10.0),
            }

        def _get_a2_open_stabilization_composite_gate(self):
            return torch.ones(8, dtype=torch.bool)

        def _finish_a2_matched_clean_reacquisition(self, mask):
            assert not torch.any(mask)

    dummy = Dummy()
    inactive_quiet_before = [
        list(dummy._a2_hold_oracle_matched_clean_quiet_samples[index])
        for index in range(8)
        if index not in dummy._active_ids.tolist()
    ]
    dummy._capture_a2_matched_clean_stabilize_post_action_samples()
    for local, env_id in enumerate(dummy._active_ids.tolist()):
        record = dummy._a2_hold_oracle_matched_clean_quiet_samples[env_id][0]
        torch.testing.assert_close(
            torch.tensor(record["actual_arm_joint_pos_target"]),
            dummy._expected_selected_target[local],
        )
        torch.testing.assert_close(
            torch.tensor(record["expected_actual_arm_joint_pos_target"]),
            dummy._expected_selected_target[local],
        )
        assert record["actual_arm_joint_target_invariant"] is True
    inactive_quiet_after = [
        dummy._a2_hold_oracle_matched_clean_quiet_samples[index]
        for index in range(8)
        if index not in dummy._active_ids.tolist()
    ]
    assert inactive_quiet_after == inactive_quiet_before
    torch.testing.assert_close(
        dummy._robot.data.joint_pos_target, dummy._actual_target_before
    )


def test_matched_clean_summary_only_maps_never_activated_pending_to_no_gate():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    summary_node = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_a2_hold_oracle_summary"
    )
    namespace = dict(globals())
    exec(textwrap.dedent(ast.get_source_segment(source, summary_node)), namespace)

    class Dummy:
        get_a2_hold_oracle_summary = namespace["get_a2_hold_oracle_summary"]

        def __init__(self, ever_activated, outcomes):
            self.num_envs = len(outcomes)
            self._a2_hold_oracle_cfg = {
                "enabled": True,
                "matched_clean_reacquisition_preflight_enabled": True,
                "matched_clean_retreat_timeout_steps": 80,
                "matched_clean_release_qualification_steps": 5,
                "matched_clean_pregrasp_position_tolerance_m": 0.005,
                "matched_clean_pregrasp_orientation_tolerance_rad": 0.10,
                "tcp_offset_z": 0.085,
                "dls_lambda": 0.01,
                "max_position_step_m": 0.002,
                "max_orientation_step_rad": 0.02,
            }
            self._a2_hold_oracle_finalized = True
            self._a2_hold_oracle_matched_clean_release_active = torch.zeros(
                self.num_envs, dtype=torch.bool
            )
            self._a2_hold_oracle_matched_clean_stabilize_active = torch.zeros(
                self.num_envs, dtype=torch.bool
            )
            self._a2_hold_oracle_outcome = torch.tensor(outcomes, dtype=torch.long)
            self._a2_hold_oracle_matched_clean_ever_activated = torch.tensor(
                ever_activated, dtype=torch.bool
            )
            self._a2_hold_oracle_matched_clean_gate_lost_ever = torch.zeros(
                self.num_envs, dtype=torch.bool
            )
            self._a2_hold_oracle_matched_clean_release_final_action_count = torch.full(
                (self.num_envs,), -1, dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_qualification_count = torch.zeros(
                self.num_envs, dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_release_contact_reset_count = torch.zeros(
                self.num_envs, dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_stabilize_final_action_count = torch.full(
                (self.num_envs,), -1, dtype=torch.long
            )
            self._a2_hold_oracle_matched_clean_captured_arm_target = torch.full(
                (self.num_envs, 6), float("nan")
            )
            self._a2_hold_oracle_matched_clean_release_qualification_evidence = [
                None for _ in range(self.num_envs)
            ]
            self._a2_hold_oracle_matched_clean_samples = [
                [] for _ in range(self.num_envs)
            ]
            self._a2_hold_oracle_matched_clean_quiet_samples = [
                [] for _ in range(self.num_envs)
            ]
            self._a2_hold_oracle_matched_clean_result = [
                None for _ in range(self.num_envs)
            ]
            self._a2_hold_oracle_matched_clean_actual_invariant_evidence = [
                [] for _ in range(self.num_envs)
            ]
            for name in (
                "reason_contact",
                "reason_timeout",
                "reason_incomplete",
                "reason_ready",
                "reason_not_settled",
            ):
                setattr(
                    self,
                    f"_a2_hold_oracle_matched_clean_{name}",
                    torch.zeros(self.num_envs, dtype=torch.bool),
                )

        def _get_a2_hold_friction_override(self):
            return None

    valid = Dummy(
        [False, True],
        [
            A2_HOLD_OUTCOME_TO_ID["PENDING"],
            A2_HOLD_OUTCOME_TO_ID["MATCHED_CLEAN_READY"],
        ],
    )
    summary = valid.get_a2_hold_oracle_summary()
    assert summary["per_env_outcome"] == [
        "MATCHED_CLEAN_NO_GATE",
        "MATCHED_CLEAN_READY",
    ]

    inconsistent = Dummy(
        [True],
        [A2_HOLD_OUTCOME_TO_ID["PENDING"]],
    )
    try:
        inconsistent.get_a2_hold_oracle_summary()
    except RuntimeError as exc:
        assert "activated or otherwise inconsistent" in str(exc)
        assert "envs=[0]" in str(exc)
    else:
        raise AssertionError("activated inactive PENDING outcome did not fail fast")
    assert inconsistent._a2_hold_oracle_outcome.item() == A2_HOLD_OUTCOME_TO_ID[
        "PENDING"
    ]
