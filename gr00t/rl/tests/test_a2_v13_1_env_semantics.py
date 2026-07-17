"""No-simulation tests for the pure v13.1 environment helpers."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from gr00t.rl.utils.average_meters import TensorAverageMeterDict


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"


def _load_helper(name):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    namespace = {"math": math, "torch": torch}
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"),
        namespace,
    )
    return namespace[name]


HOLD_MASK = _load_helper("a2_stage34_hold_income_mask")
TARGET_SCALE = _load_helper("a2_apply_stage4_target_root_distance_scale")
FRAME_SCALE = _load_helper("a2_apply_stage45_doorframe_contact_scale")
ROOT_COUNT = _load_helper("a2_root_x_first_crossing_env_count")


def _class_method_source(name, occurrence=-1):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp")
    methods = [node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name]
    return ast.unparse(methods[occurrence])


UPDATE_LATCHES = _load_helper("a2_update_stage4_release_and_root_latches")


def _load_class_method(name):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    method = next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    method.decorator_list = []
    namespace = {"torch": torch}
    exec(
        compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), "exec"),
        namespace,
    )
    return namespace[name]


def test_release_and_root_latches_support_full_and_staged_partial_updates():
    gate = torch.tensor([False, False, False, False])
    crossed = torch.tensor([False, False, False, False])
    stage = torch.tensor([3, 4, 4, 5], dtype=torch.long)
    hinge = torch.tensor([1.3, 1.2, 1.1, 1.4])
    root_x = torch.tensor([-0.2, -0.1, 0.2, 0.1])
    staged = torch.tensor([False, True, True, False])

    gate, crossed = UPDATE_LATCHES(
        gate, crossed, stage, hinge, root_x, 1.2, 4, staged
    )
    assert gate.tolist() == [False, True, False, False]
    assert crossed.tolist() == [False, False, True, False]

    hinge[2] = 1.2
    gate, crossed = UPDATE_LATCHES(
        gate, crossed, stage, hinge, root_x, 1.2, 4
    )
    assert gate.tolist() == [False, True, True, False]
    assert crossed.tolist() == [False, False, True, True]

    stage[1] = 5
    hinge[1] = 0.0
    root_x[1] = -0.5
    gate, crossed = UPDATE_LATCHES(
        gate, crossed, stage, hinge, root_x, 1.2, 4
    )
    assert gate.tolist() == [False, True, True, False]
    assert crossed.tolist() == [False, False, True, True]


def test_release_and_root_latches_reject_invalid_contracts():
    gate = torch.zeros(2, dtype=torch.bool)
    crossed = torch.zeros(2, dtype=torch.bool)
    stage = torch.tensor([4, 4], dtype=torch.long)
    hinge = torch.ones(2)
    root_x = torch.zeros(2)

    with pytest.raises(ValueError):
        UPDATE_LATCHES(gate.float(), crossed, stage, hinge, root_x, 1.2, 4)
    with pytest.raises(ValueError):
        UPDATE_LATCHES(gate, crossed, stage, torch.tensor([float("nan"), 1.0]), root_x, 1.2, 4)

    with pytest.raises(ValueError):
        UPDATE_LATCHES(gate, crossed, stage, hinge, root_x, 0.0, 4)
    with pytest.raises(ValueError):
        UPDATE_LATCHES(gate, crossed, stage, hinge, root_x, 1.2, 4, torch.ones(2, dtype=torch.long))
    with pytest.raises(ValueError):
        UPDATE_LATCHES(gate, crossed, stage.to(torch.int32), hinge, root_x, 1.2, 4)


def test_stage34_hold_mask_m12_and_m13_helpers_are_exact():
    stage = torch.tensor([3, 4, 4, 5], dtype=torch.long)
    release_gate = torch.tensor([True, False, True, True])
    assert HOLD_MASK(stage, release_gate, 3, 4).tolist() == [True, True, False, False]

    reward = torch.ones(4)
    scaled = TARGET_SCALE(reward, stage, release_gate, 4)
    assert scaled.tolist() == [1.0, 0.5, 1.0, 1.0]

    contact_force = torch.ones(4)
    scaled_force = FRAME_SCALE(contact_force, stage, 4, 5, 0.2)
    torch.testing.assert_close(
        scaled_force,
        torch.tensor([1.0, 0.2, 0.2, 0.2]),
    )

    with pytest.raises(ValueError):
        FRAME_SCALE(contact_force, stage, 4, 5, 1.1)

    with pytest.raises(ValueError):
        TARGET_SCALE(reward, stage, release_gate, "4")


def test_root_crossing_count_is_episode_latch_count():
    count = ROOT_COUNT(torch.tensor([True, False, True]))
    assert count.ndim == 0
    assert count.is_floating_point()
    assert count.device == torch.device("cpu")
    meters = TensorAverageMeterDict()
    meters.add({"a2_root_x_first_crossing_env_count": count})
    result = meters.mean_and_clear()["a2_root_x_first_crossing_env_count"]
    torch.testing.assert_close(result, torch.tensor(2.0, dtype=count.dtype))


def test_route_diagnostics_own_raw_quantiles_and_hold_and_drive_ratio_sources():
    source = _class_method_source("_update_a2_full_stage_route_diagnostics")
    assert "_a2_stage5_forward_velocity_samples" in source
    assert "_a2_stage5_forward_velocity_sample_mask" in source
    assert "root_states[:, 7]" in source
    assert "_a2_stage45_doorframe_contact_force_samples" in source
    assert "_a2_stage45_doorframe_contact_force_sample_mask" in source
    assert "door_frame_contact_force" in source
    assert "a2_stage3_stage4_hold_and_drive_numerator_frac" in source
    assert "a2_stage3_stage4_hold_and_drive_denominator_frac" in source
    assert "hold_and_drive_event" in source
    assert "stage3_stage4_active" in source

def test_a2_latch_lifecycle_has_reset_and_single_callback_ownership():
    init_source = _class_method_source("_init_buffers")
    assert "if self._use_a2_base" in init_source
    assert init_source.count("_a2_stage4_release_gate = torch.zeros") == 1
    assert init_source.count("_a2_root_x_ever_crossed = torch.zeros") == 1
    reset_source = _class_method_source("_reset_buffers_callback")
    assert "self._a2_stage4_release_gate[env_ids] = False" in reset_source
    assert "self._a2_root_x_ever_crossed[env_ids] = False" in reset_source
    assert "_update_a2_stage4_release_and_root_latches(env_ids)" in _class_method_source("_pre_compute_observations_callback")

def test_reward_ownership_matches_m11_mask_boundary():
    masked_methods = ("_reward_a2_stage3_stage4_keep_close_command", "_reward_penalty_a2_stage3_stage4_open_command", "_reward_a2_stage3_stage4_both_contact", "_reward_a2_stage3_stage4_opposite_squeeze", "_reward_a2_stage3_stage4_squeeze_force_window", "_reward_a2_stage3_stage4_contact_stability")
    for method_name in masked_methods:
        assert "_get_a2_stage34_hold_income_mask" in _class_method_source(method_name)
    assert "_get_a2_stage34_hold_income_mask" in _class_method_source("_reward_a2_stage4_grasp_target_distance_mild")
    hinge_source = _class_method_source("_reward_push_door_hinge")
    assert "hinge_pos_reward = hinge_pos_reward * self._get_a2_stage34_hold_income_mask().float()" in hinge_source
    assert "if self._use_a2_base" in hinge_source
    assert "hinge_vel_reward = hinge_vel_reward *" not in hinge_source
    for method_name in (
        "_reward_penalty_a2_stage3_stage4_over_force",
        "_reward_a2_stage3_unlatch_hold",
        "_reward_a2_stage3_stage4_hold_and_drive",
        "_reward_dont_push_door_handle",
    ):
        assert "_get_a2_stage34_hold_income_mask" not in _class_method_source(method_name)
    target_source = _class_method_source("_reward_target_root_distance")
    assert "a2_apply_stage4_target_root_distance_scale" in target_source
    frame_source = _class_method_source("_reward_penalty_door_frame_contact")
    assert "a2_apply_stage45_doorframe_contact_scale" in frame_source
    assert "_get_a2_stage34_hold_income_mask" not in _class_method_source("_stage_3_to_4_advance_condition")


def test_push_door_hinge_non_a2_preserves_shared_velocity_and_position_behavior():
    joint_vel = torch.tensor([[0.01], [-0.02]])
    joint_pos = torch.tensor([[0.7854], [2.0]])
    door = SimpleNamespace(
        data=SimpleNamespace(joint_vel=joint_vel, joint_pos=joint_pos)
    )
    simulator = SimpleNamespace(
        scene=SimpleNamespace(articulations={"door": door})
    )
    hinge_reward = _load_class_method("_reward_push_door_hinge")

    def unexpected_a2_helper_call():
        raise AssertionError("non-A2 hinge reward called the A2-only helper")

    non_a2 = SimpleNamespace(_use_a2_base=False, simulator=simulator)
    non_a2._get_a2_stage34_hold_income_mask = unexpected_a2_helper_call
    expected_non_a2 = (
        joint_vel[:, 0] * 10
        + joint_pos[:, 0].clamp(min=0.0, max=1.5708) / 1.5708
    ).clamp(max=1.0, min=-1.0)
    torch.testing.assert_close(hinge_reward(non_a2), expected_non_a2)

    a2 = SimpleNamespace(_use_a2_base=True, simulator=simulator)
    a2._get_a2_stage34_hold_income_mask = lambda: torch.tensor([False, True])
    expected_a2 = (
        joint_vel[:, 0] * 10
        + (
            joint_pos[:, 0].clamp(min=0.0, max=1.5708) / 1.5708
        )
        * torch.tensor([0.0, 1.0])
    ).clamp(max=1.0, min=-1.0)
    torch.testing.assert_close(hinge_reward(a2), expected_a2)
