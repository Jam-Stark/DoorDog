"""Plan G0 CPU evidence for the v28 action and camera reward changes."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[3]
ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
DELTA_SOURCE = ROOT / "gr00t/rl/envs/base_task/delta_action_base.py"
ROBOT_CONFIG = ROOT / "gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml"


def test_a2_v28_config_contract_default_posture():
    config = OmegaConf.load(ROBOT_CONFIG)
    robot = config.robot
    posture = robot.init_state.default_joint_angles
    expected = {
        "arm_j1": 0.0,
        "arm_j2": 0.10,
        "arm_j3": -0.10,
        "arm_j4": 0.0,
        "arm_j5": -0.415,
        "arm_j6": 1.57,
    }
    assert {name: posture[name] for name in expected} == expected
    names = list(robot.dof_names)
    lower = list(robot.dof_pos_lower_limit_list)
    upper = list(robot.dof_pos_upper_limit_list)
    assert len(names) == len(lower) == len(upper)
    for name, value in expected.items():
        index = names.index(name)
        assert lower[index] <= value <= upper[index]


def extract_function(name):
    tree = ast.parse(ENV_SOURCE.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {"torch":torch}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ENV_SOURCE), "exec"), namespace)
    return namespace[name]


def extract_method(name):
    tree = ast.parse(ENV_SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DoorPregrasp")
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    namespace = {"torch":torch}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ENV_SOURCE), "exec"), namespace)
    return namespace[name]


def test_a2_v28_wrist_motion_raw_penalty_formula():
    function = extract_function("a2_wrist_motion_raw_penalty")
    velocity = torch.tensor([[2.,-3.,4.],[0.,0.,3.]])
    previous = torch.tensor([[-1.,-2.,-3.],[0.,0.,3.]])
    vel_weights = torch.ones(6,3)
    vel_weights[3,2] = 0.
    reversal_weights = torch.full((6,3),.5)
    reversal_weights[3,2] = .25
    result = function(velocity,previous,torch.tensor([2,3]),vel_weights,reversal_weights)
    torch.testing.assert_close(result,torch.tensor([36.,0.]))
    previous[1,2] = -3.
    assert function(velocity,previous,torch.tensor([2,3]),vel_weights,reversal_weights)[1] == 2.25
    with pytest.raises(ValueError, match="shape"):
        function(velocity,previous,torch.tensor([2,3]),torch.ones(3),reversal_weights)


def test_a2_v28_tower_contact_raw_formula():
    method = extract_method("_reward_penalty_a2_wrist_tower_contact")
    env = SimpleNamespace(config=OmegaConf.create({"robot":{"body_names":["trunk","wrist_camera_tower"]}}),
                          simulator=SimpleNamespace(contact_forces=torch.tensor([
                              [[100.,0.,0.],[0.,0.,0.]], [[0.,0.,0.],[1.,0.,0.]],
                              [[0.,0.,0.],[0.,.8,.8]],
                          ])))
    torch.testing.assert_close(method(env),torch.tensor([0.,0.,1.]))


def test_a2_v28_stage4_post_release_mask():
    method = extract_method("_reward_penalty_a2_stage4_arm_default_pose_l1")
    env = SimpleNamespace(_use_a2_base=True,num_envs=4,_upper_non_gripper_dof_idx=list(range(6)),
                          simulator=SimpleNamespace(dof_pos=torch.ones(4,6)),
                          config=OmegaConf.create({"a2_stage4_arm_default_pose_release_gated":True}),
                          _a2_stage4_release_gate=torch.tensor([False,True,True,False]),
                          _get_a2_arm_default_dof_pos=lambda:torch.zeros(1,6),
                          _get_a2_stage3_stage4_contact_squeeze_masks=lambda _: {
                              "both_contact":torch.tensor([False,True,False,True])})
    torch.testing.assert_close(method(env),torch.tensor([0.,0.,6.,0.]))
    env.config.a2_stage4_arm_default_pose_release_gated = False
    torch.testing.assert_close(method(env),torch.full((4,),6.))


def delta_class():
    tree = ast.parse(DELTA_SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name == "DeltaActionBase")
    cls.body = [n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name == "step"]
    cls.body[0].decorator_list = []
    class Base:
        def step(self, actor_state):
            return actor_state
    namespace = {"torch":torch,"LeggedRobotBase":Base}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(DELTA_SOURCE),"exec"),namespace)
    return namespace["DeltaActionBase"]


@pytest.mark.parametrize("enabled",[None,False,True])
def test_a2_v28_delta_action_clamp_to_limits(enabled):
    env = delta_class()()
    config = {"delta_action_clip":15.,"robot":{
        "dof_names":[f"arm_j{i}" for i in range(1,7)],"control":{"action_scale":.25}}}
    if enabled is not None:
        config["delta_action_clamp_to_dof_limits"] = enabled
    env.config = OmegaConf.create(config)
    env._delta_actions = torch.zeros(2,6)
    env._last_delta_actions = torch.zeros(2,6)
    env._delta_action_indices = torch.arange(5,11)
    env._upper_non_gripper_dof_idx = list(range(6))
    env._delta_action_scale = .3
    env.default_dof_pos = torch.tensor([[0.,.1,-.1,0.,-.415,1.57]])
    limits = torch.tensor([[-2.6,2.6],[0.,3.14],[-2.97,0.],[-1.83,1.83],[-1.22,1.22],[-3.14,3.14]])
    env.simulator = SimpleNamespace(hard_dof_pos_limits=limits)
    env._apply_delta_action_overrides = lambda:None
    old = torch.zeros(2,6)
    for sign in [1.]*60 + [-1.]*60:
        state = {"actions":torch.full((2,12),sign)}
        old = (old + sign*.3).clamp(-15.,15.)
        result = env.step(state)
        if enabled:
            target = env.default_dof_pos + .25*env._delta_actions
            assert torch.all(target >= limits[:,0]-1e-6)
            assert torch.all(target <= limits[:,1]+1e-6)
            torch.testing.assert_close(result["actions"][:,5:11],env._delta_actions,rtol=0,atol=0)
        else:
            torch.testing.assert_close(env._delta_actions,old,rtol=0,atol=0)
