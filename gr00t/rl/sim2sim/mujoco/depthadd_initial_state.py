"""DepthADD v3 single-environment realization of the Isaac A2 reset state.

The Isaac authority resets DOFs before the root state: it multiplies every
default DOF position by U(0.8, 1.2), restores arm_j1..arm_j6 to their default
values, and zeros all DOF/root velocities.  It then samples the root position
and yaw relative to the environment origin.  This module makes that state
explicit for the single MuJoCo environment and records every realized value.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import pi
from typing import Any

import numpy as np


_SCHEMA = "a2_depthadd_v3_mujoco_initial_state_v1"
_SIM_JOINT_NAMES = (
    "FL_hip_joint",
    "FL_thigh_joint",
    "FL_calf_joint",
    "RL_hip_joint",
    "RL_thigh_joint",
    "RL_calf_joint",
    "FR_hip_joint",
    "FR_thigh_joint",
    "FR_calf_joint",
    "RR_hip_joint",
    "RR_thigh_joint",
    "RR_calf_joint",
    "arm_j1",
    "arm_j2",
    "arm_j3",
    "arm_j4",
    "arm_j5",
    "arm_j6",
    "arm_j7",
    "arm_j8",
)
_UPPER_NON_GRIPPER_JOINTS = (
    "arm_j1",
    "arm_j2",
    "arm_j3",
    "arm_j4",
    "arm_j5",
    "arm_j6",
)


@dataclass(frozen=True)
class DepthADDInitialState:
    """Exact single-environment reset realization consumed by the runner."""

    initial_state_seed: int
    root_qpos_wxyz: np.ndarray
    root_qvel: np.ndarray
    joint_qpos: np.ndarray
    joint_qvel: np.ndarray
    joint_position_multipliers: np.ndarray

    def receipt(self, sim_joint_names: Sequence[str]) -> dict[str, Any]:
        """Return a JSON-serializable record of every reset value."""
        return {
            "schema": _SCHEMA,
            "source_reset": {
                "implementation": "gr00t/rl/envs/door/door_open_a2_base.py",
                "robot_reset_order": "dofs_then_root",
                "root_position_relative_to_env_origin_m": {
                    "x": [-1.5, -0.6],
                    "y": [-0.5, 0.5],
                },
                "root_yaw_rad": [-pi / 4.0, pi / 4.0],
                "joint_position": "default_dof_pos * U(0.8, 1.2), then arm_j1..arm_j6 restored to default",
                "velocity": "root and all DOFs zero",
            },
            "initial_state_seed": self.initial_state_seed,
            "rng": "numpy.default_rng(PCG64); draw order: 20 joint multipliers, root_x, root_y, root_yaw",
            "root_qpos_mujoco_wxyz": self.root_qpos_wxyz.tolist(),
            "root_qvel": self.root_qvel.tolist(),
            "joint_names": list(sim_joint_names),
            "joint_position_multipliers": self.joint_position_multipliers.tolist(),
            "joint_qpos": self.joint_qpos.tolist(),
            "joint_qvel": self.joint_qvel.tolist(),
        }


def _initial_state_seed(row: Mapping[str, Any]) -> int:
    common = row.get("common_across_lanes")
    if not isinstance(common, Mapping):
        raise TypeError("row.common_across_lanes must be a mapping")
    seed = common.get("initial_state_seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("row.common_across_lanes.initial_state_seed must be an integer")
    if not 0 <= seed < 2**32:
        raise ValueError("row.common_across_lanes.initial_state_seed must fit uint32")
    return seed


def _contract_joint_defaults(robot_contract: Mapping[str, Any]) -> tuple[tuple[str, ...], np.ndarray]:
    joint_names = tuple(robot_contract["sim_joint_names"])
    if joint_names != _SIM_JOINT_NAMES:
        raise ValueError("robot contract sim_joint_names do not match the DepthADD A2 authority order")
    defaults = np.asarray(robot_contract["default_dof_pos"], dtype=np.float64)
    if defaults.shape != (len(_SIM_JOINT_NAMES),) or not np.isfinite(defaults).all():
        raise ValueError("robot contract default_dof_pos must be 20 finite entries")
    return joint_names, defaults


def _identity_root_qpos(robot_contract: Mapping[str, Any]) -> np.ndarray:
    initial_state = robot_contract["initial_state"]
    if not isinstance(initial_state, Mapping):
        raise TypeError("robot contract initial_state must be a mapping")
    root_qpos = np.asarray(initial_state["root_qpos_mujoco_wxyz"], dtype=np.float64)
    if root_qpos.shape != (7,) or not np.isfinite(root_qpos).all():
        raise ValueError("robot contract initial_state.root_qpos_mujoco_wxyz must be seven finite entries")
    if not np.array_equal(root_qpos[3:], np.array([1.0, 0.0, 0.0, 0.0])):
        raise ValueError("DepthADD A2 authority reset requires the resolved identity roll/pitch base rotation")
    return root_qpos


def realize_depthadd_initial_state(
    row: Mapping[str, Any], robot_contract: Mapping[str, Any]
) -> DepthADDInitialState:
    """Materialize the A2 reset distribution from a row's ``initial_state_seed``.

    The seed stream is deliberately local to the reset.  It does not share an
    RNG with visual, door, or command realization, so fixed/visual/door/
    combined lanes receive exactly the same initial robot state for a base row.
    """
    seed = _initial_state_seed(row)
    _, defaults = _contract_joint_defaults(robot_contract)
    base_root_qpos = _identity_root_qpos(robot_contract)
    rng = np.random.default_rng(seed)

    # legged_robot_base._reset_robot_states_callback calls _reset_dofs first.
    multipliers = rng.uniform(0.8, 1.2, size=len(_SIM_JOINT_NAMES))
    joint_qpos = defaults * multipliers
    for name in _UPPER_NON_GRIPPER_JOINTS:
        joint_qpos[_SIM_JOINT_NAMES.index(name)] = defaults[_SIM_JOINT_NAMES.index(name)]

    root_qpos = base_root_qpos.copy()
    root_qpos[0] = rng.uniform(-1.5, -0.6)
    root_qpos[1] = rng.uniform(-0.5, 0.5)
    yaw = rng.uniform(-pi / 4.0, pi / 4.0)
    root_qpos[3:] = (np.cos(yaw / 2.0), 0.0, 0.0, np.sin(yaw / 2.0))
    return DepthADDInitialState(
        initial_state_seed=seed,
        root_qpos_wxyz=root_qpos,
        root_qvel=np.zeros(6, dtype=np.float64),
        joint_qpos=joint_qpos,
        joint_qvel=np.zeros(len(_SIM_JOINT_NAMES), dtype=np.float64),
        joint_position_multipliers=multipliers,
    )


def apply_depthadd_initial_state(
    data: Any,
    state: DepthADDInitialState,
    *,
    robot_contract: Mapping[str, Any],
) -> None:
    """Write a realization to MuJoCo qpos/qvel using the robot contract layout.

    Call this after ``mj_resetDataKeyframe`` and before ``mj_forward``.
    """
    qpos_layout = robot_contract["qpos_layout"]
    qvel_layout = robot_contract["qvel_layout"]
    if not isinstance(qpos_layout, Mapping) or not isinstance(qvel_layout, Mapping):
        raise TypeError("robot contract qpos_layout and qvel_layout must be mappings")
    if qpos_layout.get("floating_base") != [0, 7] or qpos_layout.get("actuated") != [7, 27]:
        raise ValueError("robot contract qpos layout does not match the DepthADD A2 robot")
    if qvel_layout.get("floating_base") != [0, 6] or qvel_layout.get("actuated") != [6, 26]:
        raise ValueError("robot contract qvel layout does not match the DepthADD A2 robot")
    if data.qpos.shape[0] < 27 or data.qvel.shape[0] < 26:
        raise ValueError("MuJoCo data does not contain the required A2 root and actuated state spans")

    data.qpos[0:7] = state.root_qpos_wxyz
    data.qpos[7:27] = state.joint_qpos
    data.qvel[0:6] = state.root_qvel
    data.qvel[6:26] = state.joint_qvel
