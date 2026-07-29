"""CPU-only tests for the v20 P1 live-grasp arc geometry and adjudicator."""

from __future__ import annotations

import ast
import importlib.util
import math
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[3]
ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
TRAINER_SOURCE = ROOT / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py"
SCRIPT = ROOT / "scriptsFORhuman/v20/a2_piper_v20_arc_feasibility.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("a2_piper_v20_arc_feasibility", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _quat_apply(q, v):
    qv = q[:, 1:]
    t = 2.0 * torch.cross(qv, v, dim=-1)
    return v + q[:, :1] * t + torch.cross(qv, t, dim=-1)


def _quat_mul(q, r):
    w1, x1, y1, z1 = q.unbind(-1)
    w2, x2, y2, z2 = r.unbind(-1)
    return torch.stack((w1*w2-x1*x2-y1*y2-z1*z2, w1*x2+x1*w2+y1*z2-z1*y2, w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2), dim=-1)


def _quat_apply_inverse(q, v):
    inverse = torch.cat((q[:, :1], -q[:, 1:]), dim=-1)
    return _quat_apply(inverse, v)


def _yaw_quat(q):
    yaw = torch.atan2(
        2.0 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]),
        1.0 - 2.0 * (q[:, 2].square() + q[:, 3].square()),
    )
    return _quat_from_euler_xyz(torch.zeros_like(yaw), torch.zeros_like(yaw), yaw)


def _wrap_to_pi(value):
    return torch.remainder(value + math.pi, 2.0 * math.pi) - math.pi


def _quat_from_euler_xyz(roll, pitch, yaw):
    cr, sr = torch.cos(roll / 2), torch.sin(roll / 2)
    cp, sp = torch.cos(pitch / 2), torch.sin(pitch / 2)
    cy, sy = torch.cos(yaw / 2), torch.sin(yaw / 2)
    return torch.stack((cr*cp*cy + sr*sp*sy, sr*cp*cy - cr*sp*sy, cr*sp*cy + sr*cp*sy, cr*cp*sy - sr*sp*cy), dim=-1)


def _combine(pos_a, quat_a, pos_b, quat_b):
    return pos_a + _quat_apply(quat_a, pos_b), _quat_mul(quat_a, quat_b)


def _subtract(pos_a, quat_a, pos_b, quat_b):
    inverse = torch.cat((quat_a[:, :1], -quat_a[:, 1:]), dim=-1)
    return _quat_apply_inverse(quat_a, pos_b - pos_a), _quat_mul(inverse, quat_b)


def _euler_xyz_from_quat(q):
    roll = torch.atan2(
        2.0 * (q[:, 0] * q[:, 1] + q[:, 2] * q[:, 3]),
        1.0 - 2.0 * (q[:, 1].square() + q[:, 2].square()),
    )
    pitch = torch.asin(
        torch.clamp(2.0 * (q[:, 0] * q[:, 2] - q[:, 3] * q[:, 1]), -1.0, 1.0)
    )
    yaw = torch.atan2(
        2.0 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]),
        1.0 - 2.0 * (q[:, 2].square() + q[:, 3].square()),
    )
    return roll, pitch, yaw


def _geometry_helpers():
    tree = ast.parse(ENV_SOURCE.read_text(encoding="utf-8"))
    wanted = {
        "_a2_v20_validate_vector",
        "a2_v20_mask_stage_overtime_for_arc_probe",
        "a2_v20_arc_probe_activation_mask",
        "a2_v20_update_stable_handoff_streak",
        "a2_v20_arm_settled_handoff_mask",
        "a2_v20_apply_arc_probe_settle_action",
        "a2_v20_f1_relief_command",
        "a2_v20_update_f1_hold_target",
        "a2_v20_arc_probe_target_pose",
        "a2_v20_handle_to_tcp_transform",
        "a2_v20_bound_joint_position_target_step",
        "a2_v20_arc_probe_arm_joint_tracking_residual",
        "a2_v20_arc_probe_dls_realization_telemetry",
        "a2_v20_sync_arc_probe_cumulative_target",
        "a2_v20_fixed_planar_root_state",
        "a2_v20_root_hold_raw_command",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {
        "torch": torch,
        "math": math,
        "quat_apply": _quat_apply,
        "quat_mul": _quat_mul,
        "quat_from_euler_xyz": _quat_from_euler_xyz,
        "quat_apply_inverse": _quat_apply_inverse,
        "yaw_quat": _yaw_quat,
        "wrap_to_pi": _wrap_to_pi,
        "combine_frame_transforms": _combine,
        "subtract_frame_transforms": _subtract,
        "euler_xyz_from_quat": _euler_xyz_from_quat,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ENV_SOURCE), "exec"), namespace)
    return namespace


def _samples(*, root_translation=0.0, root_yaw=0.0, root_x=-0.1):
    return [
        {
            "hinge_position_rad": 1.2,
            "hinge_speed_radps": 0.1,
            "bilateral_contact": True,
            "tcp_handle_position_error_m": 0.01,
            "tcp_handle_orientation_error_rad": 0.10,
            "jacobian_condition": 10.0,
            "joint_margin_rad": 0.10,
            "joint_limit_valid": True,
            "delta_action_valid": True,
            "raw_action_valid": True,
            "root_translation_m": root_translation,
            "root_yaw_rad": root_yaw,
            "root_x_door": root_x,
            "door_body_force_n": 0.0,
            "arm_speed_max_radps": 1.0,
        }
        for _ in range(12)
    ]


def _rows(module, *, f0_max=1.2, f1_max=1.2, failures=()):
    result = []
    for mode in module.MODES:
        mode_max = f0_max if mode == "F0" else f1_max
        for angle in module.ANGLES:
            for seed in module.SEEDS:
                for env_id in range(16):
                    fail = (mode, angle, seed, env_id) in failures or angle > mode_max
                    result.append(module.assess_episode(
                        mode=mode,
                        target_hinge_rad=angle,
                        seed=seed,
                        env_id=env_id,
                        outcome="ARC_PROBE_TIMEOUT" if fail else "ARC_PROBE_REACHED",
                        samples=_samples(),
                        runtime={"capture_valid": True},
                    ))
    return result


def test_arc_target_rotates_about_signed_hinge_and_preserves_relative_tcp_pose():
    fn = _geometry_helpers()["a2_v20_arc_probe_target_pose"]
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    handle = torch.tensor([[1.02, -0.5, 0.0]])
    target_pos, target_quat, step, next_reference = fn(
        torch.zeros(1, 3), identity, handle, identity,
        torch.zeros(1, 3), identity, torch.tensor([1.0]), torch.tensor([1.0]),
        torch.tensor([0.0]), torch.tensor([0.0]), torch.tensor([True]), 0.9, 0.1,
    )
    assert step.item() == pytest.approx(0.1)
    assert next_reference.item() == pytest.approx(0.0)
    assert target_pos[0, 0].item() == pytest.approx(0.02 + math.cos(0.1), abs=1.0e-6)
    assert target_pos[0, 1].item() == pytest.approx(-0.5 - math.sin(0.1), abs=1.0e-6)
    torch.testing.assert_close(target_quat, _quat_from_euler_xyz(torch.zeros(1), torch.zeros(1), torch.tensor([-0.1])))


def test_arc_target_lead_does_not_accumulate_when_physical_hinge_stalls():
    fn = _geometry_helpers()["a2_v20_arc_probe_target_pose"]
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    handle = torch.tensor([[1.02, -0.5, 0.0]])
    _, target_quat, command_delta, next_reference = fn(
        torch.zeros(1, 3), identity, handle, identity,
        torch.zeros(1, 3), identity, torch.tensor([1.0]), torch.tensor([1.0]),
        torch.tensor([0.02]), torch.tensor([0.30]), torch.tensor([True]), 0.9, 0.1,
    )
    assert command_delta.item() == pytest.approx(0.1)
    assert next_reference.item() == pytest.approx(0.30)
    torch.testing.assert_close(
        target_quat,
        _quat_from_euler_xyz(torch.zeros(1), torch.zeros(1), torch.tensor([-0.1])),
    )


def test_arc_target_non_advancing_dls_hold_has_zero_lead_and_frozen_reference():
    fn = _geometry_helpers()["a2_v20_arc_probe_target_pose"]
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    handle = torch.tensor([[1.02, -0.5, 0.0]])
    target_pos, target_quat, command_delta, next_reference = fn(
        torch.zeros(1, 3),
        identity,
        handle,
        identity,
        torch.zeros(1, 3),
        identity,
        torch.tensor([1.0]),
        torch.tensor([1.0]),
        torch.tensor([0.2]),
        torch.tensor([0.1]),
        torch.tensor([False]),
        0.9,
        0.1,
    )
    torch.testing.assert_close(target_pos, handle)
    torch.testing.assert_close(target_quat, identity)
    torch.testing.assert_close(command_delta, torch.zeros(1))
    torch.testing.assert_close(next_reference, torch.tensor([0.1]))


def test_arc_target_zero_lead_composes_canonical_handle_to_tcp_pose():
    ns = _geometry_helpers()
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    handle_source = torch.tensor([[1.02, -0.5, 0.0]])
    handle_to_tcp_pos = torch.tensor([[0.0, 0.20, 0.0]])
    handle_to_tcp_quat = _quat_from_euler_xyz(
        torch.zeros(1), torch.zeros(1), torch.tensor([0.25])
    )
    expected_pos, expected_quat = _combine(
        handle_source, identity, handle_to_tcp_pos, handle_to_tcp_quat
    )
    target_pos, target_quat, command_delta, next_reference = ns[
        "a2_v20_arc_probe_target_pose"
    ](
        torch.zeros(1, 3),
        identity,
        handle_source,
        identity,
        handle_to_tcp_pos,
        handle_to_tcp_quat,
        torch.tensor([1.0]),
        torch.tensor([1.0]),
        torch.tensor([0.9]),
        torch.tensor([0.9]),
        torch.tensor([True]),
        0.9,
        0.1,
    )
    torch.testing.assert_close(target_pos, expected_pos)
    torch.testing.assert_close(target_quat, expected_quat)
    torch.testing.assert_close(command_delta, torch.zeros(1))
    torch.testing.assert_close(next_reference, torch.tensor([0.9]))


def test_canonical_handle_to_tcp_transform_recovers_composed_world_pose():
    ns = _geometry_helpers()
    handle_pos = torch.tensor([[0.8, -0.2, 1.1]])
    handle_quat = _quat_from_euler_xyz(
        torch.tensor([0.1]), torch.tensor([-0.2]), torch.tensor([0.3])
    )
    relative_pos = torch.tensor([[0.0, 0.2, 0.05]])
    relative_quat = _quat_from_euler_xyz(
        torch.tensor([0.0]), torch.tensor([0.0]), torch.tensor([0.25])
    )
    tcp_pos, tcp_quat = _combine(handle_pos, handle_quat, relative_pos, relative_quat)
    recovered_pos, recovered_quat = ns["a2_v20_handle_to_tcp_transform"](
        handle_pos, handle_quat, tcp_pos, tcp_quat
    )
    torch.testing.assert_close(recovered_pos, relative_pos)
    torch.testing.assert_close(recovered_quat, relative_quat)


def test_stable_handoff_streak_requires_exactly_five_qualifying_steps_and_resets():
    fn = _geometry_helpers()["a2_v20_update_stable_handoff_streak"]
    streak = torch.zeros(2, dtype=torch.long)
    qualifying = torch.tensor([True, True])
    for expected in range(1, 5):
        streak, capture = fn(streak, qualifying, 5)
        torch.testing.assert_close(streak, torch.tensor([expected, expected]))
        assert not torch.any(capture)
    streak, capture = fn(streak, qualifying, 5)
    torch.testing.assert_close(streak, torch.tensor([5, 5]))
    torch.testing.assert_close(capture, torch.tensor([True, True]))
    streak, capture = fn(streak, qualifying, 5)
    torch.testing.assert_close(streak, torch.tensor([5, 5]))
    assert not torch.any(capture)
    streak, capture = fn(streak, torch.tensor([False, True]), 5)
    torch.testing.assert_close(streak, torch.tensor([0, 5]))
    assert not torch.any(capture)
    with pytest.raises(ValueError, match="required_steps"):
        fn(torch.zeros(1, dtype=torch.long), torch.ones(1, dtype=torch.bool), 0)


def test_arm_settled_handoff_requires_velocity_and_residual_envelopes():
    fn = _geometry_helpers()["a2_v20_arm_settled_handoff_mask"]
    arm_speed = torch.tensor([0.049, 0.050, 0.051, 0.050, 0.050])
    residual = torch.tensor([0.0009, 0.0010, 0.0009, 0.0011, 0.0010])
    settled = fn(arm_speed, residual, 0.001, 0.02)
    torch.testing.assert_close(
        settled,
        torch.tensor([True, True, False, False, True]),
    )
    assert settled.dtype == torch.bool

    with pytest.raises(ValueError, match="one-dimensional floating vectors"):
        fn(arm_speed[:, None], residual, 0.001, 0.02)
    with pytest.raises(ValueError, match="one-dimensional floating vectors"):
        fn(arm_speed.to(torch.long), residual, 0.001, 0.02)
    with pytest.raises(ValueError, match="share dtype and device"):
        fn(arm_speed, residual.double(), 0.001, 0.02)
    with pytest.raises(ValueError, match="finite values"):
        fn(torch.tensor([float("nan")]), torch.tensor([0.0]), 0.001, 0.02)
    with pytest.raises(ValueError, match="non-negative magnitudes"):
        fn(torch.tensor([-0.001]), torch.tensor([0.0]), 0.001, 0.02)
    with pytest.raises(ValueError, match="share dtype and device"):
        fn(
            arm_speed,
            torch.empty_like(residual, device="meta"),
            0.001,
            0.02,
        )
    with pytest.raises(ValueError, match="joint_target_step_max_rad"):
        fn(arm_speed, residual, 0.0, 0.02)
    with pytest.raises(ValueError, match="joint_target_step_max_rad"):
        fn(arm_speed, residual, float("nan"), 0.02)
    with pytest.raises(ValueError, match="joint_target_step_max_rad"):
        fn(arm_speed, residual, True, 0.02)
    with pytest.raises(ValueError, match="control_dt_s"):
        fn(arm_speed, residual, 0.001, 0.0)
    with pytest.raises(ValueError, match="control_dt_s"):
        fn(arm_speed, residual, 0.001, float("nan"))
    with pytest.raises(ValueError, match="control_dt_s"):
        fn(arm_speed, residual, 0.001, False)


def test_arc_probe_settle_action_freezes_base_and_arm_preserves_gripper_and_inactive_rows():
    fn = _geometry_helpers()["a2_v20_apply_arc_probe_settle_action"]
    action = torch.arange(36.0).reshape(3, 12)
    settle_mask = torch.tensor([True, False, True])
    result = fn(action, settle_mask)
    expected = action.clone()
    expected[settle_mask, :11] = 0.0
    torch.testing.assert_close(result, expected)
    assert torch.equal(result[settle_mask, 11], action[settle_mask, 11])
    assert torch.equal(result[1], action[1])
    assert torch.equal(fn(action, torch.zeros(3, dtype=torch.bool)), action)

    with pytest.raises(ValueError, match=r"shape \(N,12\)"):
        fn(action[:, :11], settle_mask)
    with pytest.raises(ValueError, match=r"shape \(N,\)"):
        fn(action, settle_mask[:2])
    with pytest.raises(ValueError, match="bool vector"):
        fn(action, settle_mask.to(torch.int32))
    with pytest.raises(ValueError, match="bool vector"):
        fn(action, torch.empty_like(settle_mask, device="meta"))
    with pytest.raises(ValueError, match=r"shape \(N,12\)"):
        fn(action.to(torch.long), settle_mask)
    non_finite = action.clone()
    non_finite[0, 0] = float("nan")
    with pytest.raises(ValueError, match="finite policy values"):
        fn(non_finite, settle_mask)


def test_f1_relief_yaw_sign_clamp_scale_and_solvability_masks():
    fn = _geometry_helpers()["a2_v20_f1_relief_command"]
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]]).repeat(5, 1)
    target = torch.tensor([
        [0.01, 0.0, 0.0],      # horizontal-only
        [0.0, 0.0, 0.03],       # positive yaw, clamped
        [0.0, 0.0, -0.01],      # negative yaw, signed
        [0.003, 0.0, 0.004],    # combined
        [0.001, 0.0, 0.001],    # below both deadbands
    ])
    horizontal = target[:, :2]
    bounded_delta = torch.zeros(5, 6)
    bounded_delta[:, 5] = target[:, 2]
    result = fn(
        horizontal, bounded_delta, identity, torch.ones(5, dtype=torch.bool),
        0.15, 0.25, 0.002, 0.002, 5.0, 0.10,
    )
    torch.testing.assert_close(
        result["solvable"], torch.tensor([True, True, True, True, False])
    )
    torch.testing.assert_close(
        result["physical_yaw_command_radps"],
        torch.tensor([0.0, 0.10, -0.05, 0.02, 0.0]),
    )
    torch.testing.assert_close(
        result["raw_yaw_command"],
        torch.tensor([0.0, 0.40, -0.20, 0.08, 0.0]),
    )
    torch.testing.assert_close(result["raw_command"][0, 2], torch.tensor(0.0))
    torch.testing.assert_close(result["raw_command"][0, 0], torch.tensor(0.60))
    torch.testing.assert_close(result["raw_command"][3, 0], torch.tensor(0.60))
    with pytest.raises(ValueError, match="base_command_scale"):
        fn(horizontal[:1], bounded_delta[:1], identity[:1], torch.ones(1, dtype=torch.bool), 0.15, 0.0)


def test_f1_mutable_target_updates_only_on_legal_next_call_inside_immutable_bounds():
    fn = _geometry_helpers()["a2_v20_update_f1_hold_target"]
    capture = torch.zeros(4, 3)
    target = capture.clone()
    current = torch.tensor([
        [-0.05, 0.02, 0.03],
        [-0.05, 0.02, 0.03],
        [0.01, 0.02, 0.03],
        [-0.05, 0.02, 0.03],
    ])
    pending = torch.ones(4, dtype=torch.bool)
    outcome_pending = torch.tensor([True, False, True, True])
    translation = torch.tensor([0.06, 0.06, 0.06, 0.10])
    yaw = torch.tensor([0.03, 0.03, 0.03, 0.03])
    updated, applied = fn(
        target, capture, current, pending, outcome_pending, translation, yaw, 0.10, 0.15
    )
    torch.testing.assert_close(applied, torch.tensor([True, False, False, False]))
    torch.testing.assert_close(updated[0], current[0])
    torch.testing.assert_close(updated[1:], target[1:])
    torch.testing.assert_close(capture, torch.zeros_like(capture))


def test_root_hold_commands_bounded_capture_pose_correction_and_zeros_inactive():
    fn = _geometry_helpers()["a2_v20_root_hold_raw_command"]
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]]).repeat(2, 1)
    command = fn(
        torch.tensor([[0.10, 0.0, 0.20], [0.10, 0.0, 0.20]]),
        torch.zeros(2, 3),
        identity,
        identity,
        torch.zeros(2, 3),
        torch.zeros(2, 3),
        torch.tensor([True, False]),
        0.25,
        2.0,
        2.0,
        0.15,
        2.0,
        2.0,
        0.30,
    )
    torch.testing.assert_close(command[0], torch.tensor([-0.60, 0.0, -1.20, 0.0, 0.0]))
    torch.testing.assert_close(command[1], torch.zeros(5))


def test_root_hold_pd_damping_opposes_measured_root_velocity():
    fn = _geometry_helpers()["a2_v20_root_hold_raw_command"]
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    command = fn(
        torch.zeros(1, 3),
        torch.zeros(1, 3),
        identity,
        identity,
        torch.tensor([[0.10, 0.0, 0.0]]),
        torch.tensor([[0.0, 0.0, 0.20]]),
        torch.tensor([True]),
        0.25,
        2.0,
        2.0,
        0.15,
        2.0,
        2.0,
        0.30,
    )
    torch.testing.assert_close(command[0], torch.tensor([-0.60, 0.0, -1.20, 0.0, 0.0]))


def test_f0_fixed_planar_root_state_preserves_vertical_roll_pitch_and_inactive_state():
    fn = _geometry_helpers()["a2_v20_fixed_planar_root_state"]
    root_pos = torch.tensor([[0.20, -0.10, 0.55], [0.30, 0.40, 0.65]])
    root_quat = _quat_from_euler_xyz(
        torch.tensor([0.10, -0.20]),
        torch.tensor([-0.05, 0.15]),
        torch.tensor([0.30, -0.40]),
    )
    lin_vel = torch.tensor([[0.70, -0.80, 0.90], [0.10, 0.20, 0.30]])
    ang_vel = torch.tensor([[0.40, -0.50, 0.60], [0.70, 0.80, 0.90]])
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]]).repeat(2, 1)
    pose, velocity = fn(
        root_pos,
        root_quat,
        lin_vel,
        ang_vel,
        torch.zeros(2, 3),
        identity,
        torch.tensor([[0.01, 0.02, -0.25], [9.0, 9.0, 9.0]]),
        torch.tensor([True, False]),
    )
    torch.testing.assert_close(pose[0, :3], torch.tensor([0.01, 0.02, 0.55]))
    expected_active_quat = _quat_from_euler_xyz(
        torch.tensor([0.10]), torch.tensor([-0.05]), torch.tensor([-0.25])
    )[0]
    torch.testing.assert_close(pose[0, 3:], expected_active_quat)
    torch.testing.assert_close(
        velocity[0], torch.tensor([0.0, 0.0, 0.90, 0.40, -0.50, 0.0])
    )
    torch.testing.assert_close(pose[1], torch.cat((root_pos[1], root_quat[1])))
    torch.testing.assert_close(velocity[1], torch.cat((lin_vel[1], ang_vel[1])))


def test_arc_activation_requires_canonical_stage2_grasp_completion():
    fn = _geometry_helpers()["a2_v20_arc_probe_activation_mask"]
    result = fn(
        torch.tensor([True, True, True, False]),
        torch.tensor([True, True, True, True]),
        torch.tensor([True, False, False, True]),
    )
    torch.testing.assert_close(result, torch.tensor([True, False, False, False]))
    with pytest.raises(ValueError, match="stage2_grasp_completion"):
        fn(
            torch.ones(1, dtype=torch.bool),
            torch.ones(1, dtype=torch.bool),
            torch.ones(1, dtype=torch.int32),
        )


def test_arc_probe_stage_overtime_mask_preserves_other_reasons():
    fn = _geometry_helpers()["a2_v20_mask_stage_overtime_for_arc_probe"]
    reset_after_super = torch.tensor(
        [1, 1, 1, 1, 1, 0], dtype=torch.long
    )
    stage_overtime_reason = torch.tensor(
        [True, True, True, False, True, True], dtype=torch.bool
    )
    other_terminal_reason = torch.tensor(
        [False, False, True, False, False, False], dtype=torch.bool
    )
    probe_pending_mask = torch.tensor(
        [True, True, True, True, False, True], dtype=torch.bool
    )
    updated_reset, updated_reason, suppressed = fn(
        reset_after_super,
        stage_overtime_reason,
        other_terminal_reason,
        probe_pending_mask,
    )
    torch.testing.assert_close(
        updated_reset,
        torch.tensor([0, 0, 1, 1, 1, 0], dtype=torch.long),
    )
    assert updated_reset.dtype == torch.long
    torch.testing.assert_close(
        updated_reason,
        torch.tensor([False, False, False, False, True, False], dtype=torch.bool),
    )
    assert updated_reason.dtype == torch.bool
    torch.testing.assert_close(
        suppressed,
        torch.tensor([True, True, True, False, False, True], dtype=torch.bool),
    )

    with pytest.raises(ValueError, match="torch.long"):
        fn(
            reset_after_super[:, None],
            stage_overtime_reason,
            other_terminal_reason,
            probe_pending_mask,
        )
    with pytest.raises(ValueError, match="shape"):
        fn(
            reset_after_super[:-1],
            stage_overtime_reason,
            other_terminal_reason,
            probe_pending_mask,
        )
    with pytest.raises(ValueError, match="torch.long"):
        fn(
            reset_after_super.to(torch.bool),
            stage_overtime_reason,
            other_terminal_reason,
            probe_pending_mask,
        )
    with pytest.raises(ValueError, match="torch.long"):
        fn(
            reset_after_super.to(torch.float32),
            stage_overtime_reason,
            other_terminal_reason,
            probe_pending_mask,
        )
    non_binary_reset = reset_after_super.clone()
    non_binary_reset[0] = 2
    with pytest.raises(ValueError, match="binary torch.long values"):
        fn(
            non_binary_reset,
            stage_overtime_reason,
            other_terminal_reason,
            probe_pending_mask,
        )
    with pytest.raises(ValueError, match="reason and pending vectors"):
        fn(
            reset_after_super,
            stage_overtime_reason.to(torch.int8),
            other_terminal_reason,
            probe_pending_mask,
        )
    with pytest.raises(ValueError, match="reason and pending vectors"):
        fn(
            reset_after_super,
            stage_overtime_reason,
            other_terminal_reason.to(torch.int8),
            probe_pending_mask,
        )
    with pytest.raises(ValueError, match="reason and pending vectors"):
        fn(
            reset_after_super,
            stage_overtime_reason,
            other_terminal_reason,
            probe_pending_mask.to(torch.int8),
        )
    with pytest.raises(ValueError, match="device"):
        fn(
            torch.empty_like(reset_after_super, device="meta"),
            stage_overtime_reason,
            other_terminal_reason,
            probe_pending_mask,
        )


def test_arc_probe_stage_overtime_mask_is_post_super_and_fail_fast():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    helper_start = source.index("def a2_v20_mask_stage_overtime_for_arc_probe(")
    helper_end = source.index("\ndef ", helper_start + 1)
    helper_source = source[helper_start:helper_end]
    assert "reset_before_super" not in helper_source
    start = source.rindex("    @override\n    def _check_termination(self):")
    end = source.index("    @property\n    def ground_height", start)
    termination = source[start:end]
    assert "reset_before_super" not in termination
    assert termination.index("super()._check_termination()") < termination.index(
        "a2_v20_mask_stage_overtime_for_arc_probe("
    )
    for required in (
        'cfg["enabled"]',
        'cfg["v20_arc_probe_enabled"]',
        'terminal_reason_bufs["stage_overtime"]',
        "other_terminal_reason",
        "_a2_v20_arc_probe_capture_valid",
        "_a2_hold_oracle_activated",
        "_a2_eval_first_episode_active_mask",
        'A2_HOLD_OUTCOME_TO_ID["PENDING"]',
        "a2_v20_mask_stage_overtime_for_arc_probe(",
    ):
        assert required in termination


def test_arc_probe_joint_target_slew_preserves_direction_and_inactive_identity():
    fn = _geometry_helpers()["a2_v20_bound_joint_position_target_step"]
    current = torch.tensor(
        [
            [0.10, -0.20, 0.30, -0.40, 0.50, -0.60],
            [0.0] * 6,
            [0.20] * 6,
            [-0.10] * 6,
        ]
    )
    delta = torch.tensor(
        [
            [0.02, -0.04, 0.01, 0.00, -0.02, 0.03],
            [0.005, -0.004, 0.00, 0.00, 0.001, -0.002],
            [0.0] * 6,
            [0.50, -0.40, 0.30, -0.20, 0.10, -0.05],
        ]
    )
    desired = current + delta
    active = torch.tensor([True, True, True, False])
    result = fn(current, desired, active, 0.01)
    expected_scaled = current[0] + delta[0] * 0.25
    torch.testing.assert_close(
        result[0], expected_scaled
    )
    torch.testing.assert_close(result[0] - current[0], delta[0] * 0.25)
    assert torch.equal(result[1], desired[1])
    assert torch.equal(result[2], desired[2])
    assert torch.equal(result[3], current[3])
    assert torch.max(torch.abs(result - current)).item() <= 0.01 + 1.0e-7
    assert torch.all(torch.isfinite(result))
    with pytest.raises(ValueError, match="finite aligned"):
        fn(current, desired[:, :5], active, 0.01)
    with pytest.raises(ValueError, match="finite aligned"):
        fn(current, desired, active.to(torch.int32), 0.01)
    with pytest.raises(ValueError, match="finite aligned"):
        fn(current, desired.to(torch.float64), active, 0.01)
    non_finite_current = current.clone()
    non_finite_current[0, 0] = float("nan")
    with pytest.raises(ValueError, match="finite aligned"):
        fn(non_finite_current, desired, active, 0.01)
    with pytest.raises(ValueError, match="max_step_rad"):
        fn(current, desired, active, 0.0)
    with pytest.raises(ValueError, match="max_step_rad"):
        fn(current, desired, active, float("nan"))
    with pytest.raises(ValueError, match="finite aligned"):
        fn(
            current,
            torch.empty_like(desired, device="meta"),
            active,
            0.01,
        )


def test_arc_probe_tracking_residual_is_post_physics_target_minus_actual_arm_j1_to_j6():
    fn = _geometry_helpers()["a2_v20_arc_probe_arm_joint_tracking_residual"]
    joint_names = [f"arm_j{index}" for index in range(1, 7)]
    target = torch.tensor(
        [[0.10, -0.20, 0.30, -0.40, 0.50, -0.60], [0.0] * 6]
    )
    actual = torch.tensor(
        [[0.04, -0.25, 0.20, -0.35, 0.55, -0.80], [0.0] * 6]
    )
    residual = fn(joint_names, target, actual)
    torch.testing.assert_close(residual, target - actual)
    assert tuple(residual.shape) == (2, 6)
    with pytest.raises(ValueError, match="arm_j1..arm_j6 order"):
        fn(list(reversed(joint_names)), target, actual)
    with pytest.raises(ValueError, match=r"shape \(N,6\)"):
        fn(joint_names, target[:, :5], actual[:, :5])
    non_finite = target.clone()
    non_finite[0, 0] = float("nan")
    with pytest.raises(ValueError, match="finite values"):
        fn(joint_names, non_finite, actual)

    source = ENV_SOURCE.read_text(encoding="utf-8")
    arc_start = source.index("def _apply_a2_v20_arc_probe_action(")
    arc_end = source.index("def _compute_a2_hold_oracle_joint_target(", arc_start)
    arc_source = source[arc_start:arc_end]
    assert "robot.data.joint_pos_target[:, joint_ids]" in arc_source
    assert "robot.data.joint_pos[:, joint_ids]" in arc_source
    assert (
        '"v20_arc_probe_arm_joint_tracking_residual_target_minus_actual_rad"'
        in arc_source
    )


def test_arc_probe_dls_realization_logs_raw_and_slew_twists_with_strict_contracts():
    fn = _geometry_helpers()["a2_v20_arc_probe_dls_realization_telemetry"]
    n = 2
    jacobian = torch.diag(torch.arange(1.0, 7.0)).expand(n, -1, -1).clone()
    q_pre = torch.tensor(
        [[0.10, -0.20, 0.30, -0.40, 0.50, -0.60], [0.0] * 6]
    )
    q_raw = q_pre + torch.tensor(
        [[0.20, -0.10, 0.05, 0.04, -0.03, 0.02], [0.1] * 6]
    )
    q_executed = q_pre + torch.tensor(
        [[0.02, -0.01, 0.01, 0.01, -0.01, 0.01], [0.05] * 6]
    )
    source_pos = torch.zeros(n, 3)
    source_quat = torch.zeros(n, 4)
    source_quat[:, 0] = 1.0
    bounded_delta = torch.tensor([[0.01, -0.02, 0.03, 0.04, -0.05, 0.06], [0.0] * 6])
    handle_to_tcp_pos = torch.tensor([[0.0, 0.10, 0.0], [0.01, 0.11, 0.02]])
    handle_to_tcp_quat = source_quat.clone()
    result = fn(
        [f"arm_j{index}" for index in range(1, 7)],
        jacobian,
        q_pre,
        q_raw,
        q_executed,
        source_pos,
        source_quat,
        bounded_delta,
        handle_to_tcp_pos,
        handle_to_tcp_quat,
    )
    expected_raw = torch.bmm(jacobian, (q_raw - q_pre).unsqueeze(-1)).squeeze(-1)
    expected_executed = torch.bmm(
        jacobian, (q_executed - q_pre).unsqueeze(-1)
    ).squeeze(-1)
    torch.testing.assert_close(result["raw_predicted_twist_root"], expected_raw)
    torch.testing.assert_close(
        result["executed_predicted_twist_root"], expected_executed
    )
    torch.testing.assert_close(result["q_raw_dls"], q_raw)
    torch.testing.assert_close(result["q_executed"], q_executed)
    assert not torch.equal(result["q_raw_dls"], result["q_executed"])
    assert tuple(result["raw_predicted_twist_root"].shape) == (n, 6)
    with pytest.raises(ValueError, match="arm_j1..arm_j6 order"):
        fn(
            list(reversed([f"arm_j{index}" for index in range(1, 7)])),
            jacobian,
            q_pre,
            q_raw,
            q_executed,
            source_pos,
            source_quat,
            bounded_delta,
            handle_to_tcp_pos,
            handle_to_tcp_quat,
        )
    with pytest.raises(ValueError, match="requires tensor shape"):
        fn(
            [f"arm_j{index}" for index in range(1, 7)],
            jacobian,
            q_pre[:, :5],
            q_raw[:, :5],
            q_executed[:, :5],
            source_pos,
            source_quat,
            bounded_delta,
            handle_to_tcp_pos,
            handle_to_tcp_quat,
        )
    with pytest.raises(ValueError, match="share dtype and device"):
        fn(
            [f"arm_j{index}" for index in range(1, 7)],
            jacobian,
            q_pre,
            q_raw.double(),
            q_executed,
            source_pos,
            source_quat,
            bounded_delta,
            handle_to_tcp_pos,
            handle_to_tcp_quat,
        )
    invalid_jacobian = jacobian.clone()
    invalid_jacobian[0, 0, 0] = float("nan")
    with pytest.raises(ValueError, match="finite values"):
        fn(
            [f"arm_j{index}" for index in range(1, 7)],
            invalid_jacobian,
            q_pre,
            q_raw,
            q_executed,
            source_pos,
            source_quat,
            bounded_delta,
            handle_to_tcp_pos,
            handle_to_tcp_quat,
        )
    zero_quat = handle_to_tcp_quat.clone()
    zero_quat[0] = 0.0
    with pytest.raises(ValueError, match="non-degenerate"):
        fn(
            [f"arm_j{index}" for index in range(1, 7)],
            jacobian,
            q_pre,
            q_raw,
            q_executed,
            source_pos,
            source_quat,
            bounded_delta,
            handle_to_tcp_pos,
            zero_quat,
        )

    source = ENV_SOURCE.read_text(encoding="utf-8")
    arc_start = source.index("def _apply_a2_v20_arc_probe_action(")
    arc_end = source.index("def _compute_a2_hold_oracle_joint_target(", arc_start)
    arc_source = source[arc_start:arc_end]
    for required in (
        "current_q = robot.data.joint_pos[:, joint_ids]",
        'current_target = robot.data.joint_pos_target[:, joint_ids].clone()',
        "current_target[active] = current_q[active]",
        'cfg["v20_arc_probe_joint_target_step_max_rad"]',
        "q_raw_dls = q_des.clone()",
        "q_executed = q_des.clone()",
        "a2_v20_arc_probe_dls_realization_telemetry(",
        "self._a2_v20_arc_probe_command_sequence[active] += 1",
        '"v20_arc_probe_command_sequence"',
        '"v20_arc_probe_pre_command_q_rad"',
        '"v20_arc_probe_jacobian_predicted_twist_raw_root"',
        '"v20_arc_probe_jacobian_predicted_twist_executed_root"',
        '"v20_arc_probe_current_t_handle_tcp_pos"',
        '"v20_arc_probe_current_t_handle_tcp_quat_wxyz"',
    ):
        assert required in arc_source
    assert "current_target[activate] = current_q[activate]" not in arc_source
    active_target_index = arc_source.index(
        "current_target[active] = current_q[active]"
    )
    assert active_target_index < arc_source.index(
        "a2_v20_bound_joint_position_target_step(",
        active_target_index,
    )


def test_arc_probe_handoff_syncs_accumulator_to_realized_joint_pose_once():
    fn = _geometry_helpers()["a2_v20_sync_arc_probe_cumulative_target"]
    current = torch.tensor([[0.25, -0.50], [0.75, 1.00]])
    default = torch.tensor([[0.0, -0.25], [0.50, 0.50]])
    previous = torch.tensor([[9.0, 9.0], [3.0, 4.0]])
    result = fn(current, default, previous, torch.tensor([True, False]))
    torch.testing.assert_close(result[0], torch.tensor([1.0, -1.0]))
    torch.testing.assert_close(result[1], previous[1])
    with pytest.raises(ValueError, match="handoff sync"):
        fn(current, default, previous, torch.ones(2, dtype=torch.int32))


def test_arc_probe_reference_buffers_use_finite_identity_with_explicit_validity():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    start = source.index("self._a2_v20_arc_probe_handle_to_tcp_pos =")
    end = source.index("self._a2_v20_arc_probe_root_translation_max =", start)
    initialization = source[start:end]
    assert "torch.zeros" in initialization
    assert "_a2_v20_arc_probe_handle_to_tcp_quat[:, 0] = 1.0" in initialization
    assert "float(\"nan\")" not in initialization
    assert "_a2_v20_arc_probe_capture_valid = torch.zeros" in initialization
    assert "_a2_v20_arc_probe_reference_hinge = torch.zeros" in initialization


def test_arc_probe_handoff_latches_post_physics_stable_stage3_grasp():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    trainer_source = TRAINER_SOURCE.read_text(encoding="utf-8")
    hook_start = source.index("def update_a2_eval_hold_oracle_after_step(")
    hook_end = source.index("def apply_a2_eval_hold_oracle_action_override(", hook_start)
    hook_source = source[hook_start:hook_end]
    assert "self.stage_buf == self.STAGE_OPEN" in hook_source
    assert "self._get_a2_hold_streak_ok_mask()" in hook_source
    assert "_a2_v20_arc_probe_bilateral_gate()" in hook_source
    assert "settle_eligible = (" in hook_source
    assert "settle_candidate = (" in hook_source
    assert "self._a2_v20_arc_probe_settle_active.zero_()" in hook_source
    assert "self._a2_v20_arc_probe_settle_target_synced.zero_()" in hook_source
    assert "settle_candidate\n            & stable_root" in hook_source
    assert "root_speed <= cfg[\"v20_arc_probe_handoff_root_speed_max_mps\"]" in hook_source
    assert "root_yaw_rate <= cfg[\"v20_arc_probe_handoff_root_yaw_rate_max_radps\"]" in hook_source
    assert "& stable_root" in hook_source
    assert "a2_v20_arm_settled_handoff_mask(" in hook_source
    assert "robot.data.joint_pos_target" in hook_source
    assert "robot.data.joint_pos" in hook_source
    assert "self._a2_hold_oracle_joint_ids" in hook_source
    assert 'cfg["v20_arc_probe_joint_target_step_max_rad"]' in hook_source
    assert "self.dt" in hook_source
    assert "& arm_settled" not in hook_source
    assert "first_episode_active_mask & ~done_mask" in hook_source
    assert "self._a2_v20_arc_probe_handoff_ready |= handoff" in hook_source
    assert 'terminal_reason_bufs["upper_dof_overspeed"]' in hook_source
    assert '"ARC_PROBE_OVERSPEED"' in hook_source
    step_index = trainer_source.index("obs_dict, rewards, dones, infos = self.env.step")
    hook_call_index = trainer_source.index("update_hold_oracle_after_step(")
    reset_index = trainer_source.index("self.env.reset_eval_episode_tracking", step_index)
    assert step_index < hook_call_index < reset_index
    apply_start = source.index("def apply_a2_eval_hold_oracle_action_override(")
    apply_end = source.index("def _get_a2_hold_oracle_trace_fields(", apply_start)
    apply_source = source[apply_start:apply_end]
    assert "self._a2_v20_arc_probe_handoff_ready" in apply_source
    assert "_get_a2_stage2_grasp_completion_masks()" not in apply_source
    arc_start = source.index("def _apply_a2_v20_arc_probe_action(")
    arc_end = source.index("def _compute_a2_hold_oracle_joint_target(", arc_start)
    arc_source = source[arc_start:arc_end]
    assert "_a2_v20_arc_probe_bilateral_gate()" in arc_source
    assert "a2_v20_apply_arc_probe_settle_action(" in arc_source
    assert "settle_mask = torch.zeros_like(activate)" in arc_source
    assert "settle and capture masks must be disjoint" in arc_source
    assert "settle and active masks must be disjoint" in arc_source
    assert (
        "settle_sync_mask = (\n                settle_mask "
        "& ~self._a2_v20_arc_probe_settle_target_synced"
        in arc_source
    )
    assert "synchronized_settle_target = a2_v20_sync_arc_probe_cumulative_target(" in arc_source
    assert (
        "self._delta_actions[settle_sync_mask] = synchronized_settle_target[settle_sync_mask]"
        in arc_source
    )
    assert "self._a2_v20_arc_probe_settle_target_synced[settle_sync_mask] = True" in arc_source
    assert "self._capture_a2_v20_arc_probe_gate(settle_sync_mask)" in arc_source
    assert "settle_target_data = self._compute_a2_v20_arc_probe_joint_target(" in arc_source
    assert "torch.zeros_like(settle_mask)" in arc_source
    assert "action[settle_arm_mask, 5:11] = settle_a_raw[settle_arm_mask]" in arc_source
    assert "self._capture_a2_v20_arc_probe_gate(activate)" in arc_source
    assert "self._compute_a2_v20_arc_probe_joint_target(active, active)" in arc_source
    assert "self._a2_v20_arc_probe_settle_target_synced[activate] = False" in arc_source
    assert "self._a2_v20_arc_probe_settle_action_count[settle_mask] += 1" in arc_source
    assert "self._delta_actions[active] = d_prev[active]" in arc_source
    assert "self._delta_actions[:] = d_prev" not in arc_source
    assert "combined_override_mask = override_mask | settle_mask" in arc_source
    assert "return action, combined_override_mask" in arc_source
    assert "a2_v20_sync_arc_probe_cumulative_target(" in arc_source
    assert arc_source.index(
        "self._delta_actions[settle_sync_mask] = synchronized_settle_target[settle_sync_mask]"
    ) < arc_source.index("a2_v20_apply_arc_probe_settle_action(")
    assert '"CONTACT_SLIP"' not in arc_source
    assert "v20_arc_probe_terminal_window_count" in arc_source
    assert 'if cfg["v20_arc_probe_mode"] == "F0"' in arc_source
    assert "_apply_a2_v20_f0_planar_root_clamp(active, frame_data)" in arc_source
    assert "probe_base_raw = torch.zeros_like(root_hold_raw)" in arc_source
    assert 'root_hold_raw * cfg["v20_arc_probe_f1_root_hold_scale"]' in arc_source
    assert "action[arm_mask, :5] = probe_base_raw[arm_mask]" in arc_source
    assert "self._a2_hold_oracle_phase_step[override_mask] += 1" in arc_source

    init_start = source.index("self._a2_v20_arc_probe_handoff_streak =")
    init_end = source.index("self._a2_v20_arc_probe_f1_hold_target_se2 =", init_start)
    init_source = source[init_start:init_end]
    assert "self._a2_v20_arc_probe_settle_active = torch.zeros" in init_source
    assert "self._a2_v20_arc_probe_settle_action_count = torch.zeros" in init_source
    reset_start = source.index("self._a2_v20_arc_probe_handoff_streak[env_ids] = 0")
    reset_end = source.index("self._a2_v20_arc_probe_command_sequence[env_ids] = 0", reset_start)
    reset_source = source[reset_start:reset_end]
    assert "self._a2_v20_arc_probe_settle_active[env_ids] = False" in reset_source
    assert "self._a2_v20_arc_probe_settle_action_count[env_ids] = 0" in reset_source
    assert '"v20_arc_probe_settle_active":' in source
    assert '"v20_arc_probe_settle_action_count":' in source
    assert '"per_env_settle_active":' in source
    assert '"per_env_settle_action_count":' in source


def test_arc_probe_defaults_use_low_speed_closed_loop_protocol():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    eval_config = (ROOT / "gr00t/rl/config/base_eval.yaml").read_text(encoding="utf-8")
    assert 'positive_float("a2_v20_arc_probe_lead_rad", 0.008)' in source
    assert '"a2_v20_arc_probe_timeout_steps", 1200' in source
    assert '"a2_v20_arc_probe_max_orientation_step_rad", 0.02' in source
    assert '"a2_v20_arc_probe_joint_target_step_max_rad", 0.001' in source
    assert '"v20_arc_probe_max_orientation_step_rad": 0.02' in source
    assert '"v20_arc_probe_joint_target_step_max_rad": 0.001' in source
    assert '"v20_arc_probe_root_hold_translation_damping_gain": 2.0' in source
    assert '"v20_arc_probe_root_hold_yaw_gain": 40.0' in source
    assert '"v20_arc_probe_root_hold_yaw_damping_gain": 2.0' in source
    assert '"v20_arc_probe_f1_root_hold_scale": 1.0' in source
    assert '"v20_arc_probe_max_orientation_step_rad": 0.004' not in source
    assert '"v20_arc_probe_joint_target_step_max_rad": 0.01' not in source
    assert "a2_v20_arc_probe_lead_rad: 0.008" in eval_config
    assert "a2_v20_arc_probe_timeout_steps: 1200" in eval_config
    assert "a2_v20_arc_probe_max_orientation_step_rad: 0.02" in eval_config
    assert "a2_v20_arc_probe_joint_target_step_max_rad: 0.001" in eval_config
    assert "a2_v20_arc_probe_root_hold_translation_damping_gain: 2.0" in eval_config
    assert "a2_v20_arc_probe_root_hold_yaw_gain: 40.0" in eval_config
    assert "a2_v20_arc_probe_root_hold_yaw_damping_gain: 2.0" in eval_config
    assert "a2_v20_arc_probe_f1_root_hold_scale: 1.00" in eval_config
    assert 0.008 / 0.02 == pytest.approx(0.4)
    script_source = SCRIPT.read_text(encoding="utf-8")
    assert 'env["CUDA_VISIBLE_DEVICES"] = gpus[index]' in script_source
    assert 'env["ACCELERATE_TORCH_DEVICE"] = "cuda:0"' in script_source
    assert 'env.pop("CUDA_VISIBLE_DEVICES"' not in script_source


def test_selection_prefers_highest_passing_f0_before_f1():
    module = _load_script()
    assert module.PROBE_EPISODE_LENGTH_S == 120
    assert module.PROBE_EPISODE_LENGTH_S >= 40 + module.PROBE_TIMEOUT_STEPS * 0.064
    selection = module.select_threshold(_rows(module, f0_max=1.0, f1_max=1.2))
    assert selection["pass"] is True
    assert selection["selected"] == {
        "mode": "F0", "target_hinge_rad": 1.0, "episodes": 48,
        "feasible_episodes": 48, "pass": True,
    }
    assert selection["frozen_values"]["pre_send_relief_translation_max_m"] == 0.02


def test_exact_46_of_48_passes_and_f1_bounds_are_enforced():
    module = _load_script()
    failures = {("F0", 0.9, 0, 0), ("F0", 0.9, 0, 1)}
    selection = module.select_threshold(_rows(module, f0_max=0.9, f1_max=1.2, failures=failures))
    cell = next(cell for cell in selection["cells"] if cell["mode"] == "F0" and cell["target_hinge_rad"] == 0.9)
    assert cell["feasible_episodes"] == 46 and cell["pass"] is True
    bounded = module.assess_episode(mode="F1", target_hinge_rad=0.9, seed=0, env_id=0, outcome="ARC_PROBE_REACHED", samples=_samples(root_translation=0.10001), runtime={"capture_valid": True})
    assert bounded["feasible"] is False
    assert "root_relief_bound" in bounded["failure_reasons"]


def test_missing_terminal_contact_or_crossing_fails_fast_semantics():
    module = _load_script()
    samples = _samples(root_x=0.01)
    samples[-1]["bilateral_contact"] = False
    row = module.assess_episode(mode="F0", target_hinge_rad=0.9, seed=0, env_id=0, outcome="ARC_PROBE_REACHED", samples=samples, runtime={"capture_valid": True})
    assert row["feasible"] is False
    assert {"terminal_bilateral_window", "root_plane_crossing"}.issubset(row["failure_reasons"])


def test_selection_rejects_incomplete_grid():
    module = _load_script()
    with pytest.raises(module.ArcFeasibilityError, match="exactly 384"):
        module.select_threshold(_rows(module)[:-1])


def test_runtime_gpu_contract_excludes_reserved_gpu7():
    module = _load_script()
    assert module.ALLOWED_GPUS == ("0", "1", "2", "3", "4", "5", "6")
    assert module.parse_args(["--output-dir", "unused"]).gpus == "0,1,2,3,4,5,6"
    with pytest.raises(module.ArcFeasibilityError, match="invalid P1 eval command identity"):
        module.build_eval_command(
            Path("checkpoint.pt"), Path("output"), mode="F1", angle=0.9, seed=0, gpu="7"
        )
