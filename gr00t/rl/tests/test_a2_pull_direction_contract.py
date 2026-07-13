"""No-simulator checks for the A2 push/pull door direction contract."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest
import torch
from omegaconf import OmegaConf

from gr00t.rl.envs.door.a2_door_direction import (
    DOOR_MODE_PULL,
    DOOR_MODE_PUSH,
    DOOR_OPEN_IO_IN,
    DOOR_OPEN_IO_OUT,
    PULL_PREGRASP_OFFSET,
    PULL_PREGRASP_ROTATION_WXYZ,
    PUSH_PREGRASP_OFFSET,
    PUSH_PREGRASP_ROTATION_WXYZ,
    a2_stage5_reward_gate,
    configured_pregrasp_spec,
    heading_error_rad,
    horizontal_door_directions,
    pregrasp_rotation_for_pull,
    select_pull_stage4_target_root_pos,
    signed_progress,
    validate_door_mode,
    validate_open_io_metadata,
)


ROOT = Path(__file__).parents[3]
ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
PUSH_SCENARIO = ROOT / "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py"
PULL_SCENARIO = ROOT / "gr00t/rl/data/tasks/door_pull/scenario_cfg/isaacsim.py"
FACTORY_SOURCE = ROOT / "gr00t/rl/data/tasks/door/scenario_cfg/factory.py"
PUSH_ENV = ROOT / "gr00t/rl/config/env/door_open_a2_base.yaml"
PULL_ENV = ROOT / "gr00t/rl/config/env/door_pull_a2_base.yaml"
PULL_EXP = ROOT / "gr00t/rl/config/exp/wbmanip/door_pull_a2_base_lstm.yaml"
PUSH_EXP = ROOT / "gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml"
REWARD_YAML = ROOT / "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml"
OBS_YAML = ROOT / "gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml"


def _load_env_method(name: str):
    """Compile one environment method without importing Isaac Sim dependencies."""
    source = ENV_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    method.decorator_list = []
    namespace = {
        "torch": torch,
        "horizontal_door_directions": horizontal_door_directions,
    }
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(ENV_SOURCE), "exec"), namespace)
    return namespace[name]


def _quat_z(yaw: float) -> torch.Tensor:
    return torch.tensor(
        [math.cos(yaw / 2.0), 0.0, 0.0, math.sin(yaw / 2.0)], dtype=torch.float32
    )


def test_mode_and_metadata_sign_mapping_is_fail_fast():
    assert validate_door_mode(DOOR_MODE_PUSH) == DOOR_MODE_PUSH
    assert validate_door_mode(DOOR_MODE_PULL) == DOOR_MODE_PULL
    assert torch.equal(
        validate_open_io_metadata(DOOR_MODE_PUSH, torch.tensor([-1.0, -1.0])),
        torch.tensor([-1.0, -1.0]),
    )
    assert torch.equal(
        validate_open_io_metadata(DOOR_MODE_PULL, torch.tensor([1.0, 1.0])),
        torch.tensor([1.0, 1.0]),
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_open_io_metadata(DOOR_MODE_PULL, torch.tensor([-1.0]))
    with pytest.raises(ValueError, match="exactly 'push' or 'pull'"):
        validate_door_mode("mixed")


def test_identity_door_signs_drive_approach_and_through_directions():
    identity = torch.tensor([[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]])
    approach, through, lateral = horizontal_door_directions(
        identity, torch.tensor([DOOR_OPEN_IO_OUT, DOOR_OPEN_IO_IN])
    )
    assert torch.allclose(approach, torch.tensor([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]))
    assert torch.allclose(through, torch.tensor([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]))
    assert torch.allclose(lateral, torch.tensor([[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]]))


def test_rotated_door_frame_is_used_in_world_geometry():
    q = torch.stack([_quat_z(math.pi / 2.0)])
    approach, through, lateral = horizontal_door_directions(q, torch.tensor([-1.0]))
    assert torch.allclose(approach, torch.tensor([[0.0, -1.0, 0.0]]), atol=1.0e-6)
    assert torch.allclose(through, torch.tensor([[0.0, 1.0, 0.0]]), atol=1.0e-6)
    assert torch.allclose(lateral, torch.tensor([[-1.0, 0.0, 0.0]]), atol=1.0e-6)


def test_signed_crossing_and_pull_clearance_progress():
    door = torch.zeros(2, 3)
    root = torch.tensor([[-0.2, 0.0, 0.5], [0.4, 0.0, 0.5]])
    through = torch.tensor([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
    progress = signed_progress(root, door, through)
    assert torch.allclose(progress, torch.tensor([-0.2, -0.4]))
    # Pull starts on +X: approach-side clearance is +0.3, then crossing is -X.
    pull_clearance = signed_progress(torch.tensor([[0.35, 0.0, 0.5]]), door[:1], -through[1:])
    pull_crossing = signed_progress(torch.tensor([[-1.6, 0.0, 0.5]]), door[:1], through[1:])
    assert bool(pull_clearance[0] >= 0.3)
    assert bool(pull_crossing[0] >= 1.5)


def test_pull_stage4_target_state_table_ignores_clearance_predicate():
    clearance_target = torch.tensor(
        [[0.35, 0.0, 0.5], [0.35, 0.0, 0.5], [0.35, 0.0, 0.5]], dtype=torch.float32
    )
    through_target = torch.tensor(
        [[-2.0, 0.0, 0.5], [-2.0, 0.0, 0.5], [-2.0, 0.0, 0.5]], dtype=torch.float32
    )
    # The second row has already reached clearance but remains in stage4: it
    # must still use the clearance target.  Only stage5 switches to through.
    state_table = (
        (False, 4, clearance_target[0]),
        (True, 4, clearance_target[1]),
        (True, 5, through_target[2]),
    )
    stage_buf = torch.tensor([stage for _, stage, _ in state_table], dtype=torch.long)
    selected = select_pull_stage4_target_root_pos(
        stage_buf,
        4,
        clearance_target,
        through_target,
    )
    for index, (_, _, expected) in enumerate(state_table):
        assert torch.allclose(selected[index], expected)


def test_a2_stage5_reward_persists_through_plane_until_completion():
    through_progress = torch.tensor([0.0, 0.4, 1.5, 1.6], dtype=torch.float32)
    door_opened = torch.ones(through_progress.shape, dtype=torch.bool)
    handle_up = torch.ones(through_progress.shape, dtype=torch.bool)
    reward_active = a2_stage5_reward_gate(door_opened, handle_up)
    assert torch.equal(reward_active, torch.ones_like(reward_active))
    # Completion is a separate strict signed-progress threshold.
    completion = through_progress > 1.5
    assert torch.equal(completion, torch.tensor([False, False, False, True]))
    handle_up[1] = False
    assert not bool(a2_stage5_reward_gate(door_opened, handle_up)[1])


def test_env_door_pose_validates_runner_string_device_without_moving_tensors():
    root_method = _load_env_method("_get_a2_door_root_pose")
    frame_method = _load_env_method("_get_a2_door_frame_directions")
    data = SimpleNamespace(
        root_pos_w=torch.zeros((2, 3), dtype=torch.float32),
        root_quat_w=torch.tensor([[1.0, 0.0, 0.0, 0.0]] * 2),
    )
    door = SimpleNamespace(data=data)
    obj = SimpleNamespace(
        simulator=SimpleNamespace(
            scene=SimpleNamespace(articulations={"door": door}),
        ),
        num_envs=2,
        device="cpu",
        approach_sign=torch.tensor([-1.0, -1.0]),
    )
    obj._get_a2_door_root_pose = MethodType(root_method, obj)
    obj._get_a2_door_frame_directions = MethodType(frame_method, obj)
    root_pos, root_quat = obj._get_a2_door_root_pose("string-device test")
    assert root_pos.device == torch.device("cpu")
    assert root_quat.device == torch.device("cpu")
    _, _, approach, through, _ = obj._get_a2_door_frame_directions("string-device test")
    assert torch.allclose(approach, torch.tensor([[-1.0, 0.0, 0.0]] * 2))
    assert torch.allclose(through, torch.tensor([[1.0, 0.0, 0.0]] * 2))

    # A normalized runner string is compared as a torch.device; invalid tensor
    # placement fails fast instead of being silently moved to self.device.
    obj.device = "cuda:0"
    with pytest.raises(RuntimeError, match="requires door.data"):
        obj._get_a2_door_root_pose("device mismatch test")


def test_face_door_penalty_is_heading_based_not_absolute_yaw():
    push_error = heading_error_rad(torch.stack([_quat_z(0.0)]), torch.tensor([[1.0, 0.0, 0.0]]))
    pull_error = heading_error_rad(torch.stack([_quat_z(math.pi)]), torch.tensor([[-1.0, 0.0, 0.0]]))
    assert torch.allclose(push_error, torch.zeros(1), atol=1.0e-6)
    assert torch.allclose(pull_error, torch.zeros(1), atol=1.0e-6)


def test_pregrasp_offset_and_quaternion_mirroring_contract():
    assert configured_pregrasp_spec(DOOR_MODE_PUSH) == (
        PUSH_PREGRASP_OFFSET,
        PUSH_PREGRASP_ROTATION_WXYZ,
    )
    assert configured_pregrasp_spec(DOOR_MODE_PULL) == (
        PULL_PREGRASP_OFFSET,
        PULL_PREGRASP_ROTATION_WXYZ,
    )
    q_push = torch.tensor(PUSH_PREGRASP_ROTATION_WXYZ)
    q_pull = pregrasp_rotation_for_pull(q_push)
    assert torch.allclose(q_pull, torch.tensor(PULL_PREGRASP_ROTATION_WXYZ), atol=1.0e-6)
    assert torch.allclose(q_pull, torch.tensor((0.5, 0.5, -0.5, -0.5)), atol=1.0e-6)


def test_scenario_factory_and_task_wiring_are_explicit():
    push_source = PUSH_SCENARIO.read_text(encoding="utf-8")
    pull_source = PULL_SCENARIO.read_text(encoding="utf-8")
    factory_source = FACTORY_SOURCE.read_text(encoding="utf-8")
    assert "build_task_obj_cfg_dict([\"out\"])" in push_source
    assert "build_task_obj_cfg_dict([\"in\"])" in pull_source
    assert "door_open_lr=[\"right\"]" in factory_source
    assert "door_open_io=values" in factory_source

    push_env = OmegaConf.load(PUSH_ENV)
    pull_env = OmegaConf.load(PULL_ENV)
    assert push_env.env.config.task.name == "door"
    assert push_env.env.config.task.mode == "push"
    assert pull_env.env.config.task.name == "door_pull"
    assert pull_env.env.config.task.mode == "pull"
    assert tuple(push_env.env.config.a2_pregrasp_target_offset) == PUSH_PREGRASP_OFFSET
    assert tuple(pull_env.env.config.a2_pregrasp_target_offset) == PULL_PREGRASP_OFFSET
    assert tuple(pull_env.env.config.target_root_pos) == (-2.0, 0.0, 0.5)


def test_pull_experiment_reuses_shared_interfaces_and_namespace():
    push_exp = PUSH_EXP.read_text(encoding="utf-8")
    pull_exp = PULL_EXP.read_text(encoding="utf-8")
    for shared in (
        "/rewards: wbmanip/reward_door_open_a2_base",
        "/obs: wbmanip/door_open_a2_base",
        "override /trainer: trl_a2_base_api",
    ):
        assert shared in push_exp
        assert shared in pull_exp
    assert "/env: door_pull_a2_base" in pull_exp
    assert "project_name: a2_piper_pull_door_a2_base" in pull_exp
    assert "project_name: a2_piper_open_door_a2_base" in push_exp
    assert "privileged_door_info: 8" in OBS_YAML.read_text(encoding="utf-8")
    assert "push_door_hinge: 6.0" in REWARD_YAML.read_text(encoding="utf-8")


def test_positive_hinge_semantics_and_no_pull_world_x_force():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    hinge_source = ast.get_source_segment(source, methods["_reward_push_door_hinge"])
    assert ".clamp(min=0.0, max=1.5708)" in hinge_source
    assert "joint_pos[:, 0]" in hinge_source
    force_source = ast.get_source_segment(source, methods["_reward_push_door_force"])
    assert "if self._use_a2_base" in force_source
    assert "return torch.zeros" in force_source
    assert "left_net_force[:, 0]" in force_source  # legacy non-A2 push route only


def test_active_a2_route_has_no_fixed_world_x_direction_comparisons():
    source = ENV_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {
        node.name: ast.get_source_segment(source, node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in (
        "_reward_walk_to_door",
        "_reward_penalty_a2_stage1_stage2_base_forward_creep",
        "_reward_target_root_distance",
        "_stage_0_to_1_advance_condition",
    ):
        assert "robot_root_states[:, 0]" not in methods[name]
        assert "stage0_target[:, 0]" not in methods[name]
    # Stage4/5 retain the legacy non-A2 branch; their A2 branch is the signed
    # through/clearance path and therefore contains no fixed world-X compare.
    assert "signed_progress" in methods["_stage_4_to_5_advance_condition"]
    assert "signed_progress" in methods["_stage_5_to_complete_condition"]
    face_source = methods["_reward_penalty_face_door"]
    assert "heading_error_rad" in face_source
    assert "axis_angle_from_quat" not in face_source.split("if self._use_a2_base", 1)[0]
