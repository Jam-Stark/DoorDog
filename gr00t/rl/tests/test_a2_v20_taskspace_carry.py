"""CPU-only v20 M47 task-space decomposition and tangent geometry tests."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"


def _quat_apply(q, v):
    qv = q[:, 1:]
    t = 2.0 * torch.cross(qv, v, dim=-1)
    return v + q[:, :1] * t + torch.cross(qv, t, dim=-1)


def _quat_inv(q):
    return q * q.new_tensor([1.0, -1.0, -1.0, -1.0])


def _quat_mul(q, r):
    w1, x1, y1, z1 = q.unbind(-1)
    w2, x2, y2, z2 = r.unbind(-1)
    return torch.stack((w1*w2-x1*x2-y1*y2-z1*z2, w1*x2+x1*w2+y1*z2-z1*y2, w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2), dim=-1)


def _combine(pos_a, quat_a, pos_b, quat_b):
    return pos_a + _quat_apply(quat_a, pos_b), _quat_mul(quat_a, quat_b)


def _subtract(pos_a, quat_a, pos_b, quat_b):
    return _quat_apply(_quat_inv(quat_a), pos_b - pos_a), _quat_mul(_quat_inv(quat_a), quat_b)


def _helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted = {"_a2_v20_validate_vector", "a2_v20_handle_opening_tangent", "a2_v20_taskspace_arm_carry", "a2_v20_arc_tracking_quality", "a2_v20_handle_to_tcp_transform", "a2_v20_handle_local_slip_metrics"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    ns = {"torch": torch, "math": math, "quat_apply": _quat_apply, "quat_mul": _quat_mul, "quat_inv": _quat_inv, "subtract_frame_transforms": _subtract}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns


def test_pure_base_and_arm_contributions_have_expected_shares():
    ns = _helpers()
    z = torch.zeros(1, 3)
    tangent = torch.tensor([[1.0, 0.0, 0.0]])
    pure_base = ns["a2_v20_taskspace_arm_carry"](z, torch.tensor([[1.0, 0.0, 0.0]]), z, z, torch.tensor([[1.0, 0.0, 0.0]]), tangent, activity_floor_mps=0.001)
    assert pure_base["arm_tangent_share"].item() == 0.0
    pure_arm = ns["a2_v20_taskspace_arm_carry"](z, z, z, z, torch.tensor([[1.0, 0.0, 0.0]]), tangent, activity_floor_mps=0.001)
    assert pure_arm["arm_tangent_share"].item() == 1.0
    equal = ns["a2_v20_taskspace_arm_carry"](z, torch.tensor([[0.5, 0.0, 0.0]]), z, z, torch.tensor([[1.0, 0.0, 0.0]]), tangent, activity_floor_mps=0.001)
    assert equal["arm_tangent_share"].item() == pytest.approx(0.5)


def test_rotational_base_velocity_and_wrong_direction_are_not_hidden():
    ns = _helpers()
    root = torch.tensor([[0.0, 0.0, 0.0]])
    omega = torch.tensor([[0.0, 0.0, 1.0]])
    tcp = torch.tensor([[0.0, 1.0, 0.0]])
    tangent = torch.tensor([[-1.0, 0.0, 0.0]])
    result = ns["a2_v20_taskspace_arm_carry"](root, torch.zeros(1, 3), omega, tcp, torch.zeros(1, 3), tangent, activity_floor_mps=0.001)
    assert result["positive_base_tangent"].item() == pytest.approx(1.0)
    wrong = ns["a2_v20_taskspace_arm_carry"](root, torch.zeros(1, 3), torch.zeros(1, 3), tcp, torch.tensor([[1.0, 0.0, 0.0]]), torch.tensor([[-1.0, 0.0, 0.0]]), activity_floor_mps=0.001)
    assert wrong["active"].item() is False


def test_tangent_uses_lr_not_io_and_arc_reference_is_explicit():
    ns = _helpers()
    source_pos = torch.zeros(1, 3)
    source_quat = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    grasp = torch.tensor([[0.0, 0.0, 1.0]])
    tangent = ns["a2_v20_handle_opening_tangent"](source_pos, source_quat, grasp, torch.tensor([1.0]), torch.tensor([1.0]))
    assert tangent.shape == (1, 3)
    assert tangent[0, 1].item() > 0.0
    ref = ns["a2_v20_arc_tracking_quality"](grasp, source_quat, grasp, source_quat, torch.tensor([True]), position_tolerance_m=0.03, orientation_tolerance_rad=0.2)
    assert ref["quality"].item() == pytest.approx(1.0)
    invalid = ns["a2_v20_arc_tracking_quality"](grasp, source_quat, grasp + 1.0, source_quat, torch.tensor([False]), position_tolerance_m=0.03, orientation_tolerance_rad=0.2)
    assert invalid["quality"].item() == 0.0


def test_handle_local_slip_splits_canonical_handle_axis_and_orthogonal_residual():
    ns = _helpers()
    captured_pos = torch.zeros(2, 3)
    captured_quat = torch.tensor([[1.0, 0.0, 0.0, 0.0]] * 2)
    current_pos = torch.tensor([[0.03, 0.04, 0.12], [0.0, -0.02, 0.0]])
    result = ns["a2_v20_handle_local_slip_metrics"](
        captured_pos,
        captured_quat,
        current_pos,
        captured_quat,
        torch.tensor([True, False]),
    )
    assert result["along_handle_slip_m"].tolist() == pytest.approx([0.04, 0.02])
    assert result["orthogonal_arc_residual_m"].tolist() == pytest.approx([math.sqrt(0.03**2 + 0.12**2), 0.0])
    assert result["total_position_error_m"].tolist() == pytest.approx([math.sqrt(0.03**2 + 0.04**2 + 0.12**2), 0.02])
    assert result["orientation_error_rad"].tolist() == pytest.approx([0.0, 0.0], abs=1e-6)
    assert result["valid"].tolist() == [True, False]

    half_turn = math.sqrt(0.5)
    historical_quat = torch.tensor([[half_turn, 0.0, 0.0, half_turn]])
    local_delta = torch.tensor([[0.0, 0.2, 0.0]])
    rotated_delta = _quat_apply(historical_quat, local_delta)
    rotated = ns["a2_v20_handle_local_slip_metrics"](
        torch.zeros(1, 3),
        historical_quat,
        rotated_delta,
        historical_quat,
        torch.tensor([True]),
    )
    assert rotated["along_handle_slip_m"].item() == pytest.approx(0.0)
    assert rotated["orthogonal_arc_residual_m"].item() == pytest.approx(0.2, abs=1e-6)
    assert rotated["total_position_error_m"].item() == pytest.approx(0.2, abs=1e-6)
    with pytest.raises(ValueError, match="non-degenerate"):
        ns["a2_v20_handle_local_slip_metrics"](
            torch.zeros(1, 3),
            torch.zeros(1, 4),
            torch.zeros(1, 3),
            torch.tensor([[1.0, 0.0, 0.0, 0.0]]),
            torch.tensor([True]),
        )


def test_handle_local_slip_uses_same_direction_quaternions_without_frame_reprojection():
    ns = _helpers()
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    quarter_turn = torch.tensor([[math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)]])
    result = ns["a2_v20_handle_local_slip_metrics"](
        torch.tensor([[0.0, 0.20, 0.0]]),
        identity,
        torch.tensor([[0.0, 0.20, 0.0]]),
        quarter_turn,
        torch.tensor([True]),
    )
    assert result["along_handle_slip_m"].item() == pytest.approx(0.0)
    assert result["orthogonal_arc_residual_m"].item() == pytest.approx(0.0)
    assert result["total_position_error_m"].item() == pytest.approx(0.0)
    assert result["orientation_error_rad"].item() == pytest.approx(math.pi / 2, abs=1e-6)


def test_handle_to_tcp_transform_composes_world_poses_and_rejects_bad_inputs():
    ns = _helpers()
    handle_pos = torch.tensor([[1.0, 2.0, 3.0]])
    handle_quat = torch.tensor([[math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)]])
    relative_pos = torch.tensor([[0.0, 0.20, 0.0]])
    relative_quat = torch.tensor([[1.0, 0.0, 0.0, 0.0]])
    tcp_pos, tcp_quat = _combine(handle_pos, handle_quat, relative_pos, relative_quat)
    recovered_pos, recovered_quat = ns["a2_v20_handle_to_tcp_transform"](
        handle_pos, handle_quat, tcp_pos, tcp_quat
    )
    torch.testing.assert_close(recovered_pos, relative_pos)
    torch.testing.assert_close(recovered_quat, relative_quat)
    with pytest.raises(ValueError, match="non-degenerate"):
        ns["a2_v20_handle_to_tcp_transform"](
            handle_pos,
            torch.zeros(1, 4),
            tcp_pos,
            tcp_quat,
        )
    with pytest.raises(ValueError, match="finite values"):
        ns["a2_v20_handle_to_tcp_transform"](
            handle_pos,
            handle_quat,
            torch.tensor([[float("nan"), 0.0, 0.0]]),
            tcp_quat,
        )


def test_m47_separates_door_root_tangent_from_piper_tcp_source():
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("    def _update_a2_v20_state")
    end = source.index("    def _update_a2_stage5_hold_continuation", start)
    method = source[start:end]
    tangent_start = method.index("tangent_w = a2_v20_handle_opening_tangent")
    tangent_end = method.index("root_link_pos_w =", tangent_start)
    tangent_call = method[tangent_start:tangent_end]
    assert 'frame_data["source_pos_w"]' in tangent_call
    assert 'frame_data["source_quat_w"]' in tangent_call
    assert 'door_target_pos_source[:, int(frame_data["grasp_target_idx"]), :]' in tangent_call
    assert 'target_pos_source[:, 0, :]' not in tangent_call
    assert 'source_pos_w = piper_frame["source_pos_w"]' in method
    assert 'piper_frame["handle_to_tcp_pos"]' in method
    piper_method_start = source.index("    def _get_a2_v20_piper_frame_data")
    piper_method_end = source.index("    def _get_a2_gripper_handle_contact_forces", piper_method_start)
    piper_method = source[piper_method_start:piper_method_end]
    assert "a2_v20_handle_to_tcp_transform(" in piper_method
    assert 'values["target_pos_w"][:, 0, :]' in piper_method
    assert 'values["target_pos_source"][:, 0, :]' not in piper_method
    assert 'values["handle_to_tcp_pos"] = handle_to_tcp_pos' in piper_method


def test_f1_observes_root_without_invoking_f0_root_writer():
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("    def _apply_a2_v20_arc_probe_action")
    end = source.index("    def _compute_a2_hold_oracle_joint_target", start)
    method = source[start:end]
    assert 'if cfg["v20_arc_probe_mode"] == "F0":' in method
    assert "root_se2 = self._apply_a2_v20_f0_planar_root_clamp" in method
    assert "root_se2 = self._a2_v20_current_root_se2(frame_data)" in method
