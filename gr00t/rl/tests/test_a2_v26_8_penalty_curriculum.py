from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from omegaconf import OmegaConf

ROOT = Path(__file__).parents[3]
DOOR_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
LEGGED_SOURCE = ROOT / "gr00t/rl/envs/legged_base_task/legged_robot_base.py"


def _extract_function(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    function.decorator_list = []
    namespace = {"math": math, "Path": Path, "torch": torch}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


UPDATE_DRIVER = _extract_function(DOOR_SOURCE, "_update_reward_penalty_curriculum")
INIT_DRIVER = _extract_function(DOOR_SOURCE, "_init_a2_v26_8_penalty_curriculum")
RECORD_EPISODES = _extract_function(DOOR_SOURCE, "_record_a2_v26_8_last_episodes")
COMPUTE_REWARD = _extract_function(LEGGED_SOURCE, "_compute_reward")


def _driver_state(*, scale: float = 1.0):
    state = SimpleNamespace()
    state.config = OmegaConf.create(
        {
            "a2_v26_8_penalty_driver": "side_min_natural_stage_reach_rate",
            "rewards": {
                "reward_penalty_degree": -0.0001,
                "reward_min_penalty_scale": 0.2,
                "reward_max_penalty_scale": 1.0,
            },
        }
    )
    state._a2_v26_8_penalty_driver_enabled = True
    state._a2_v26_8_penalty_driver_target_stage = 4
    state._a2_v26_8_penalty_driver_level_down_rate = 0.5
    state._a2_v26_8_penalty_driver_level_up_rate = 0.7
    state._a2_v26_8_last_episode_start_stage = torch.zeros(4, dtype=torch.long)
    state._a2_v26_8_last_episode_max_stage = torch.zeros(4, dtype=torch.long)
    state._a2_v26_8_last_episode_valid = torch.ones(4, dtype=torch.bool)
    state._a2_v26_8_pending_natural_count_by_side = torch.tensor([2, 2])
    state._a2_v26_8_pending_natural_reached_by_side = torch.tensor([2, 2])
    state.door_open_lr = torch.tensor([1.0, 1.0, -1.0, -1.0])
    state.reward_penalty_scale = torch.tensor(scale)
    state.log_dict = {}
    state._a2_v26_8_penalty_curriculum_trace_path = None
    state._a2_v26_8_penalty_curriculum_update_index = 0
    state._a2_v26_8_penalty_curriculum_skipped_updates = 0
    state._update_reward_penalty_curriculum = UPDATE_DRIVER.__get__(state)
    state._record_a2_v26_8_last_episodes = RECORD_EPISODES.__get__(state)
    return state


def test_v26_8_hysteresis_decay_restore_hold_and_clip():
    state = _driver_state()
    state._update_reward_penalty_curriculum()
    assert state.reward_penalty_scale.item() == pytest.approx(0.9999)

    state.reward_penalty_scale.fill_(0.20001)
    state._a2_v26_8_pending_natural_count_by_side[:] = 2
    state._a2_v26_8_pending_natural_reached_by_side[:] = 2
    state._update_reward_penalty_curriculum()
    assert state.reward_penalty_scale.item() == pytest.approx(0.2)

    state.reward_penalty_scale.fill_(0.99999)
    state._a2_v26_8_pending_natural_count_by_side[:] = 2
    state._a2_v26_8_pending_natural_reached_by_side.zero_()
    state._update_reward_penalty_curriculum()
    assert state.reward_penalty_scale.item() == 1.0
    assert state.log_dict["reward_penalty_scale"].item() == 1.0

    state.reward_penalty_scale.fill_(0.6)
    state._a2_v26_8_pending_natural_count_by_side[:] = 2
    state._a2_v26_8_pending_natural_reached_by_side[:] = 1
    state._update_reward_penalty_curriculum()
    assert state.log_dict["a2_v26_8_penalty_driver_min"].item() == 0.5
    assert state.reward_penalty_scale.item() == pytest.approx(0.6)


def test_v26_8_start_and_max_stage_are_captured_from_the_same_episode():
    state = _driver_state(scale=0.6)
    state._a2_v26_8_pending_natural_count_by_side.zero_()
    state._a2_v26_8_pending_natural_reached_by_side.zero_()
    state.door_open_lr = torch.tensor([1.0, -1.0, 1.0, -1.0])
    state._a2_v26_episode_started = torch.tensor([True, True, False, False])
    state._a2_v26_episode_start_stage = torch.tensor([0, 0, 3, 0])
    state.current_max_stage_buf = torch.tensor([4, 3, 5, 0])
    state._a2_v26_8_last_episode_valid.zero_()
    state._record_a2_v26_8_last_episodes(torch.tensor([0, 1, 2]))

    state._a2_v26_episode_start_stage[:] = torch.tensor([3, 3, 0, 0])
    state.current_max_stage_buf[:] = torch.tensor([0, 5, 4, 4])
    state._update_reward_penalty_curriculum()

    assert state._a2_v26_8_last_episode_valid.tolist() == [True, True, False, False]
    assert state._a2_v26_8_last_episode_start_stage.tolist() == [0, 0, 0, 0]
    assert state._a2_v26_8_last_episode_max_stage.tolist() == [4, 3, 0, 0]
    assert state.log_dict["a2_v26_8_penalty_driver_left"].item() == 1.0
    assert state.log_dict["a2_v26_8_penalty_driver_right"].item() == 0.0


def test_v26_8_cross_side_pending_window_is_retained_then_consumed_once():
    state = _driver_state(scale=0.6)
    state._a2_v26_8_pending_natural_count_by_side.zero_()
    state._a2_v26_8_pending_natural_reached_by_side.zero_()
    state.door_open_lr = torch.tensor([1.0, -1.0, 1.0, -1.0])
    state._a2_v26_episode_started = torch.ones(4, dtype=torch.bool)
    state._a2_v26_episode_start_stage = torch.zeros(4, dtype=torch.long)
    state.current_max_stage_buf = torch.tensor([4, 4, 0, 0])

    state._record_a2_v26_8_last_episodes(torch.tensor([0]))
    state._update_reward_penalty_curriculum()
    assert state._a2_v26_8_pending_natural_count_by_side.tolist() == [1, 0]
    assert state._a2_v26_8_pending_natural_reached_by_side.tolist() == [1, 0]
    assert state.reward_penalty_scale.item() == pytest.approx(0.6)

    state._record_a2_v26_8_last_episodes(torch.tensor([2]))
    state._update_reward_penalty_curriculum()
    assert state._a2_v26_8_pending_natural_count_by_side.tolist() == [2, 0]
    assert state._a2_v26_8_pending_natural_reached_by_side.tolist() == [1, 0]

    state._record_a2_v26_8_last_episodes(torch.tensor([1]))
    state._update_reward_penalty_curriculum()
    assert state.log_dict["a2_v26_8_penalty_driver_left"].item() == 0.5
    assert state.log_dict["a2_v26_8_penalty_driver_right"].item() == 1.0
    assert state.reward_penalty_scale.item() == pytest.approx(0.6)
    assert state._a2_v26_8_pending_natural_count_by_side.tolist() == [0, 0]
    assert state._a2_v26_8_pending_natural_reached_by_side.tolist() == [0, 0]

    state._update_reward_penalty_curriculum()
    assert state.reward_penalty_scale.item() == pytest.approx(0.6)
    assert state._a2_v26_8_penalty_curriculum_skipped_updates == 3


@pytest.mark.parametrize("penalty_names", [["active", "zero"], ["active", "unknown"]])
def test_v26_8_penalty_name_validation_rejects_zero_or_unknown_terms(penalty_names):
    state = SimpleNamespace()
    state.config = OmegaConf.create(
        {
            "a2_v26_8_penalty_driver": "side_min_natural_stage_reach_rate",
            "a2_v26_door_open_lr": "bilateral",
            "a2_v26_8_penalty_driver_target_stage": 4,
            "a2_v26_8_penalty_driver_level_down_rate": 0.5,
            "a2_v26_8_penalty_driver_level_up_rate": 0.7,
            "a2_v26_8_penalty_curriculum_trace_enabled": False,
            "rewards": {
                "reward_penalty_curriculum": True,
                "reward_penalty_reward_names": penalty_names,
            },
        }
    )
    state.num_envs = 4
    state.num_stages = 6
    state.device = torch.device("cpu")
    state.use_reward_penalty_curriculum = torch.tensor(True)
    state.reward_scales = {"active": 0.02}
    with pytest.raises(RuntimeError, match="remain non-zero"):
        INIT_DRIVER(state)


def test_v26_8_missing_driver_delegates_to_the_unchanged_legacy_path(monkeypatch):
    del monkeypatch
    tree = ast.parse(DOOR_SOURCE.read_text(encoding="utf-8"))
    door_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DoorPregrasp"
    )
    method = next(
        node
        for node in door_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_update_reward_penalty_curriculum"
    )
    method.decorator_list = []

    class Legacy:
        def _update_reward_penalty_curriculum(self):
            self.legacy_value = "unchanged"

    extracted = ast.ClassDef(
        name="ExtractedDoor",
        bases=[ast.Name(id="Legacy", ctx=ast.Load())],
        keywords=[],
        body=[method],
        decorator_list=[],
    )
    ast.fix_missing_locations(extracted)
    namespace = {"Legacy": Legacy, "torch": torch, "math": math, "Path": Path}
    exec(
        compile(ast.Module(body=[extracted], type_ignores=[]), str(DOOR_SOURCE), "exec"),
        namespace,
    )
    state = namespace["ExtractedDoor"]()
    state.config = {}
    state._update_reward_penalty_curriculum()
    assert state.__dict__ == {"config": {}, "legacy_value": "unchanged"}


def _compute_reward(curriculum_enabled: bool):
    state = SimpleNamespace()
    state.num_envs = 3
    state.rew_buf = torch.zeros(3)
    state.reward_names = ["shaping"]
    state.reward_functions = [lambda: torch.tensor([1.5, -2.0, 3.0])]
    state.reward_scales = {"shaping": 0.125}
    state.config = OmegaConf.create(
        {
            "rewards": {
                "reward_penalty_reward_names": ["shaping"],
                "reward_penalty_curriculum": curriculum_enabled,
                "only_positive_rewards": False,
            },
            "live_reward_analysis": False,
        }
    )
    state.reward_penalty_scale = torch.tensor(1.0)
    state.episode_sums = {"shaping": torch.zeros(3)}
    state.dt = 0.02
    state._after_reward_components = lambda raw, scaled: None
    state.log_dict = {}
    state.average_episode_length = torch.tensor(1.0)
    state.use_reward_penalty_curriculum = curriculum_enabled
    state.use_reward_limits_dof_pos_curriculum = False
    state.use_reward_limits_dof_vel_curriculum = False
    state.use_reward_limits_torque_curriculum = False
    state.add_noise_currculum = False
    state.device = torch.device("cpu")
    COMPUTE_REWARD.__globals__["to_torch"] = lambda value, **_: torch.as_tensor(value)
    COMPUTE_REWARD(state)
    return state.rew_buf, state.episode_sums["shaping"]


def test_v26_8_scale_one_reward_is_bit_identical_to_curriculum_disabled():
    enabled_reward, enabled_sum = _compute_reward(True)
    disabled_reward, disabled_sum = _compute_reward(False)
    assert torch.equal(enabled_reward, disabled_reward)
    assert torch.equal(enabled_sum, disabled_sum)
