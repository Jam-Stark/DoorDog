"""Historical D021 probe; D023 reverted its target changes. Not a current-source acceptance test."""

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import torch


SOURCE = Path("/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py")
MATH_SOURCE = Path("/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/utils/math.py")


def extract_function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            node = ast.fix_missing_locations(ast.parse(ast.unparse(node)).body[0])
            node.decorator_list = []
            return node
    raise RuntimeError(f"missing source function: {name}")


def load_functions():
    class DoorPregrasp:
        STAGE_PREGRASP = 1

    namespace = {"torch": torch, "math": math, "DoorPregrasp": DoorPregrasp}
    door_tree = ast.parse(SOURCE.read_text())
    math_tree = ast.parse(MATH_SOURCE.read_text())
    names = (
        "a2_grasp_gated_door_reward_components",
        "a2_stage34_hold_income_mask",
        "a2_update_stage4_release_and_root_latches",
        "a2_corridor_hold_and_drive_component",
        "_get_a2_stage34_hold_income_mask",
        "_get_a2_corridor_mask",
        "_get_a2_grasp_gated_door_reward_components",
        "_reward_push_door_hinge",
        "_reward_grasp",
    )
    for name in names:
        exec(compile(ast.Module(body=[extract_function(door_tree, name)], type_ignores=[]), str(SOURCE), "exec"), namespace)
    for name in ("quat_conjugate", "quat_inv", "quat_apply"):
        exec(compile(ast.Module(body=[extract_function(math_tree, name)], type_ignores=[]), str(MATH_SOURCE), "exec"), namespace)
    return namespace


class Probe:
    STAGE_OPEN = 3
    STAGE_SWING = 4
    STAGE_THROUGH = 5

    def __init__(self, ns):
        self.__dict__.update({name: value.__get__(self, Probe) for name, value in ns.items() if name.startswith("_get_") or name.startswith("_reward_")})
        self.num_envs = 5
        self.device = "cpu"
        self._use_a2_base = True
        self.stage_buf = torch.tensor([3, 4, 4, 4, 5], dtype=torch.long)
        self._a2_stage4_release_gate = torch.tensor([False, False, True, True, True])
        self._a2_corridor_latched = torch.zeros(5, dtype=torch.bool)
        self._streak = torch.full((5,), 5, dtype=torch.long)
        joint_pos = torch.tensor([[0.50, 0.02], [0.70, 0.02], [0.80, 0.02], [0.80, 0.02], [1.30, 0.02]])
        joint_vel = torch.tensor([[0.08, 0.0], [0.08, 0.0], [0.08, 0.0], [-0.08, 0.0], [0.08, 0.0]])
        self.simulator = SimpleNamespace(
            scene=SimpleNamespace(articulations={"door": SimpleNamespace(data=SimpleNamespace(joint_pos=joint_pos, joint_vel=joint_vel))})
        )
        forces = torch.tensor([
            [[0.0, 3.0, 0.0], [0.0, 3.0, 0.0]],
            [[0.0, 3.0, 0.0], [0.0, 3.0, 0.0]],
            [[0.0, 3.0, 0.0], [0.0, 3.0, 0.0]],
            [[2.0, 1.0, 0.0], [2.0, 1.0, 0.0]],
            [[0.0, 3.0, 0.0], [0.0, 3.0, 0.0]],
        ])
        self._forces = forces

    def _get_a2_gripper_handle_contact_forces(self):
        return self._forces

    def _get_a2_gripper_handle_frame_transformer(self):
        quat = torch.tensor([[1.0, 0.0, 0.0, 0.0]]).expand(self.num_envs, -1).clone()
        return SimpleNamespace(data=SimpleNamespace(source_quat_w=quat))

    def _get_door_joint_pos(self, _context, _minimum):
        return self.simulator.scene.articulations["door"].data.joint_pos

    def _get_door_joint_vel(self, _context, _minimum):
        return self.simulator.scene.articulations["door"].data.joint_vel

    def _get_a2_grasp_control_streak_buffer(self, _name, _context):
        return self._streak

    def _get_a2_grasp_streak_control_steps(self):
        return 5

    def _get_a2_stage3_unlatch_handle_position_norm(self):
        return 0.6

    def _get_a2_stage3_unlatch_near_closed_hinge_threshold(self):
        return 0.1

    def _get_a2_stage3_stage4_hold_and_drive_velocity_norm(self):
        return 0.1

    def _get_a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor(self):
        return 0.1

    def _get_a2_door_income_hold_mask(self):
        return torch.tensor([True, True, True, True, False])

    def _get_a2_corridor_enabled(self):
        return False


ns = load_functions()
probe = Probe(ns)
push = probe._reward_push_door_hinge()
components = probe._get_a2_grasp_gated_door_reward_components()
grasp = probe._reward_grasp()
latched, _ = ns["a2_update_stage4_release_and_root_latches"](
    torch.tensor([False, True]), torch.tensor([False, False]),
    torch.tensor([4, 4], dtype=torch.long), torch.tensor([1.2, 0.1]),
    torch.tensor([0.0, 0.0]), 1.2, 4,
)
expected_push = torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0])
expected_hold = torch.tensor([0.8, 0.8, 0.0, 0.0, 0.0])
expected_grasp = torch.tensor([3.0, 3.0, 0.0, -1.0, 3.0])
assert torch.equal(push, expected_push), (push, expected_push)
torch.testing.assert_close(components["hold_and_drive"], expected_hold)
assert torch.equal(grasp, expected_grasp), (grasp, expected_grasp)
assert torch.equal(latched, torch.tensor([True, True])), latched
print("CPU_PROBE_PASS")
print("cases=[stage3, stage4_pre_gate, stage4_post_gate_opening, stage4_post_gate_closing, stage5]")
print("push_door_hinge=", push.tolist())
print("hold_and_drive=", components["hold_and_drive"].tolist())
print("raw_unwrapped_grasp=", grasp.tolist())
print("stage5_grasp_note: excluded by production stage decorator; raw value above is not a stage5 reward")
print("release_latch_at_1.2=", latched.tolist())
print("config_static: corridor_enabled=false stage5_hold_income_continuity_enabled=false release_threshold=1.2")
