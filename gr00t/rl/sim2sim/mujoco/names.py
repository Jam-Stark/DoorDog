"""Named joint contracts shared by the Isaac and MuJoCo A2+Piper paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch


POLICY_LEG_JOINT_NAMES = (
    "FL_hip_joint",
    "FR_hip_joint",
    "RL_hip_joint",
    "RR_hip_joint",
    "FL_thigh_joint",
    "FR_thigh_joint",
    "RL_thigh_joint",
    "RR_thigh_joint",
    "FL_calf_joint",
    "FR_calf_joint",
    "RL_calf_joint",
    "RR_calf_joint",
)
ARM_JOINT_NAMES = tuple(f"arm_j{i}" for i in range(1, 7))
GRIPPER_JOINT_NAMES = ("arm_j7", "arm_j8")
LOGICAL_JOINT_NAMES = POLICY_LEG_JOINT_NAMES + ARM_JOINT_NAMES + ("gripper_primitive",)
SIM_JOINT_NAMES = (
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
) + ARM_JOINT_NAMES + GRIPPER_JOINT_NAMES


@dataclass(frozen=True)
class A2PiperJointMap:
    """Name-derived A2 policy to simulator joint indexing."""

    sim_joint_names: tuple[str, ...]
    policy_leg_indices: torch.Tensor
    arm_indices: torch.Tensor
    gripper_indices: torch.Tensor

    @classmethod
    def from_sim_joint_names(
        cls, sim_joint_names: Sequence[str], *, device: torch.device | str
    ) -> "A2PiperJointMap":
        names = tuple(sim_joint_names)
        if len(set(names)) != len(names):
            raise ValueError("Simulator joint names must be unique.")
        required = POLICY_LEG_JOINT_NAMES + ARM_JOINT_NAMES + GRIPPER_JOINT_NAMES
        missing = tuple(name for name in required if name not in names)
        if missing:
            raise ValueError(f"Simulator joint contract is missing {missing}.")
        return cls(
            sim_joint_names=names,
            policy_leg_indices=torch.tensor(
                [names.index(name) for name in POLICY_LEG_JOINT_NAMES],
                dtype=torch.long,
                device=device,
            ),
            arm_indices=torch.tensor(
                [names.index(name) for name in ARM_JOINT_NAMES], dtype=torch.long, device=device
            ),
            gripper_indices=torch.tensor(
                [names.index(name) for name in GRIPPER_JOINT_NAMES],
                dtype=torch.long,
                device=device,
            ),
        )

    def gather_policy_legs(self, values: torch.Tensor) -> torch.Tensor:
        if values.ndim != 2 or values.shape[1] != len(self.sim_joint_names):
            raise ValueError(
                "Simulator joint tensor must have shape "
                f"(batch, {len(self.sim_joint_names)}); got {tuple(values.shape)}."
            )
        if values.device != self.policy_leg_indices.device:
            raise ValueError("Simulator joint tensor and joint map must share a device.")
        return values.index_select(1, self.policy_leg_indices)
