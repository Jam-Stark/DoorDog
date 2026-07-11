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
        "a2_hold_update_base_relief_state",
        "a2_hold_update_phase_arm_sign_check",
        "a2_hold_validate_friction_override",
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
