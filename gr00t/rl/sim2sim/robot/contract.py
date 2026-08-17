"""Resolved A2+Piper MuJoCo robot-control contract.

This module intentionally emits no MJCF. The builder phase owns asset generation;
the contract here anchors name order, position defaults, and external PD parameters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from gr00t.rl.sim2sim.mujoco.names import POLICY_LEG_JOINT_NAMES, SIM_JOINT_NAMES


@dataclass(frozen=True)
class A2PiperRobotContract:
    schema: str
    sim_joint_names: tuple[str, ...]
    policy_leg_joint_names: tuple[str, ...]
    default_dof_pos: tuple[float, ...]
    stiffness: tuple[float, ...]
    damping: tuple[float, ...]
    torque_limit: tuple[float, ...]
    action_scale: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def resolved_a2_piper_contract() -> A2PiperRobotContract:
    """Return the v24-evaluated A2+Piper resolved PD/control surface."""
    return A2PiperRobotContract(
        schema="a2_piper_mujoco_robot_contract_v1",
        sim_joint_names=SIM_JOINT_NAMES,
        policy_leg_joint_names=POLICY_LEG_JOINT_NAMES,
        default_dof_pos=(
            0.0, 0.5, -1.0,
            0.0, 0.5, -1.0,
            0.0, 0.5, -1.0,
            0.0, 0.5, -1.0,
            0.0, 0.0, 0.0, 0.25, 0.5, 1.57, 0.0, 0.0,
        ),
        stiffness=(
            140.0, 140.0, 220.0,
            140.0, 140.0, 220.0,
            140.0, 140.0, 220.0,
            140.0, 140.0, 220.0,
            64.0, 128.0, 64.0, 64.0, 64.0, 64.0, 1300.0, 1300.0,
        ),
        damping=(
            4.5, 4.5, 9.0,
            4.5, 4.5, 9.0,
            4.5, 4.5, 9.0,
            4.5, 4.5, 9.0,
            3.0, 4.5, 3.0, 3.0, 3.0, 3.0, 32.0, 32.0,
        ),
        torque_limit=(
            120.0, 120.0, 180.0,
            120.0, 120.0, 180.0,
            120.0, 120.0, 180.0,
            120.0, 120.0, 180.0,
            40.0, 40.0, 40.0, 40.0, 40.0, 40.0, 45.0, 45.0,
        ),
        action_scale=0.25,
    )
