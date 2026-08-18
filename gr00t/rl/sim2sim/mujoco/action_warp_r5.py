"""Resolved production action warp used by the r5 MuJoCo Student path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
import yaml

from gr00t.rl.sim2sim.mujoco.names import A2PiperJointMap
from gr00t.rl.sim2sim.mujoco.stage_contract_minimal import (
    StageActionResult,
    StageContractMinimal,
)


@dataclass(frozen=True)
class ResolvedActionWarpContractR5:
    config_path: str
    base_command_scale: float
    body_pitch_roll_scale: float
    base_clip_thresholds_xyz: tuple[float, float, float]
    command_obs_multipliers: tuple[float, float, float, float, float]
    command_deadband_norm: float
    delta_action_scale: float
    delta_action_clip: float
    gripper_open_target: tuple[float, float]
    gripper_close_target: tuple[float, float]
    robot_action_scale: float
    robot_action_clip: float

    @classmethod
    def from_config(cls, config_path: Path) -> "ResolvedActionWarpContractR5":
        path = config_path.resolve(strict=True)
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        env = config["env"]["config"]
        a2 = env["a2_base"]
        control = config["robot"]["control"]
        if env["clip_homie_command"] is not True:
            raise ValueError("r5 requires resolved clip_homie_command=true")
        if env["delta_action_indices"] != [5, 6, 7, 8, 9, 10]:
            raise ValueError("r5 requires the production six-arm delta indices")
        if env["warped_action"] != {
            "indices": [0, 1, 2, 3, 4],
            "k": 0.0,
            "s": 0.0,
        }:
            raise ValueError("READY Student base warped_action must be the resolved identity")
        if config["env"]["config"]["domain_rand"]["randomize_ctrl_delay"] is not False:
            raise ValueError("READY Student action contract requires no randomized control delay")
        if float(a2["command_scale"]) != float(a2["base_command_scale"]):
            raise ValueError("resolved A2 command_scale and base_command_scale disagree")
        return cls(
            config_path=str(path),
            base_command_scale=float(a2["command_scale"]),
            body_pitch_roll_scale=float(a2["body_pitch_roll_scale"]),
            base_clip_thresholds_xyz=(
                float(env["clip_homie_linvel_x_threshold"]),
                float(env["clip_homie_linvel_y_threshold"]),
                float(env["clip_homie_angvel_threshold"]),
            ),
            command_obs_multipliers=tuple(
                map(float, a2["command_obs_multipliers"])
            ),
            command_deadband_norm=0.1,
            delta_action_scale=float(env["delta_action_scale"]),
            delta_action_clip=float(env["delta_action_clip"]),
            gripper_open_target=tuple(map(float, a2["gripper_open_target"])),
            gripper_close_target=tuple(map(float, a2["gripper_close_target"])),
            robot_action_scale=float(control["action_scale"]),
            robot_action_clip=float(control["action_clip_value"]),
        )

    @property
    def base_low(self) -> tuple[float, float, float, float, float]:
        x, y, yaw = self.base_clip_thresholds_xyz
        posture = self.body_pitch_roll_scale
        return (-x, -y, -yaw, -posture, -posture)

    @property
    def base_high(self) -> tuple[float, float, float, float, float]:
        x, y, yaw = self.base_clip_thresholds_xyz
        posture = self.body_pitch_roll_scale
        return (x, y, yaw, posture, posture)


@dataclass(frozen=True)
class BaseCommandWarpResultR5:
    raw: torch.Tensor
    warped: torch.Tensor
    scaled_unclipped: torch.Tensor
    pre_final_clip: torch.Tensor
    physical: torch.Tensor
    axis_clipped: torch.Tensor
    axis_at_cap: torch.Tensor


@dataclass(frozen=True)
class FullActionWarpResultR5:
    stage_action: StageActionResult
    base: BaseCommandWarpResultR5
    logical_action: torch.Tensor
    simulator_raw_action_before_clip: torch.Tensor
    simulator_raw_action: torch.Tensor
    simulator_action_clipped: torch.Tensor
    position_target: torch.Tensor


class FullActionWarpR5:
    """Map raw Student+leg actions through every resolved production transform."""

    def __init__(
        self,
        *,
        contract: ResolvedActionWarpContractR5,
        joint_map: A2PiperJointMap,
        stage_tracker: StageContractMinimal,
    ):
        self.contract = contract
        self.joint_map = joint_map
        self.stage_tracker = stage_tracker

    def warp_base_command(self, raw_base_action: torch.Tensor) -> BaseCommandWarpResultR5:
        if tuple(raw_base_action.shape) != (1, 5):
            raise ValueError("r5 raw base action must have shape (1, 5)")
        # Resolved WarpedActionBase has k=0,s=0 and explicitly returns identity.
        warped = raw_base_action.clone()
        scaled_unclipped = torch.cat(
            (
                warped[:, :3] * self.contract.base_command_scale,
                warped[:, 3:5] * self.contract.body_pitch_roll_scale,
            ),
            dim=1,
        )
        pre_final_clip = torch.cat(
            (
                scaled_unclipped[:, :3],
                warped[:, 3:5].clamp(-1.0, 1.0)
                * self.contract.body_pitch_roll_scale,
            ),
            dim=1,
        )
        low = torch.tensor(
            self.contract.base_low,
            dtype=raw_base_action.dtype,
            device=raw_base_action.device,
        ).unsqueeze(0)
        high = torch.tensor(
            self.contract.base_high,
            dtype=raw_base_action.dtype,
            device=raw_base_action.device,
        ).unsqueeze(0)
        physical = torch.clamp(pre_final_clip, low, high)
        return BaseCommandWarpResultR5(
            raw=raw_base_action.clone(),
            warped=warped,
            scaled_unclipped=scaled_unclipped,
            pre_final_clip=pre_final_clip,
            physical=physical,
            axis_clipped=physical != pre_final_clip,
            axis_at_cap=(physical == low) | (physical == high),
        )

    def observation_command_echo(self, physical: torch.Tensor) -> torch.Tensor:
        multipliers = torch.tensor(
            self.contract.command_obs_multipliers,
            dtype=physical.dtype,
            device=physical.device,
        ).unsqueeze(0)
        echo = physical * multipliers
        if float(torch.linalg.vector_norm(physical[:, :3])) < self.contract.command_deadband_norm:
            echo[:, :3] = 0.0
        return echo

    def apply(
        self,
        *,
        raw_high_level_action: torch.Tensor,
        policy_leg_action: torch.Tensor,
        default_dof_pos: torch.Tensor,
    ) -> FullActionWarpResultR5:
        if tuple(raw_high_level_action.shape) != (1, 12):
            raise ValueError("r5 raw high-level action must have shape (1, 12)")
        if tuple(policy_leg_action.shape) != (1, 12):
            raise ValueError("r5 low-level leg action must have shape (1, 12)")
        if tuple(default_dof_pos.shape) != (1, len(self.joint_map.sim_joint_names)):
            raise ValueError("r5 default joint position width mismatch")
        stage_action = self.stage_tracker.apply_high_level_action(raw_high_level_action)
        effective = stage_action.effective_high_level_action
        base = self.warp_base_command(effective[:, :5])
        logical_action = torch.cat(
            (policy_leg_action, effective[:, 5:11], effective[:, 11:12]), dim=1
        )
        simulator_raw = torch.zeros_like(default_dof_pos)
        simulator_raw[:, self.joint_map.policy_leg_indices] = policy_leg_action
        simulator_raw[:, self.joint_map.arm_indices] = effective[:, 5:11]
        open_target = torch.tensor(
            self.contract.gripper_open_target,
            dtype=effective.dtype,
            device=effective.device,
        ).unsqueeze(0)
        close_target = torch.tensor(
            self.contract.gripper_close_target,
            dtype=effective.dtype,
            device=effective.device,
        ).unsqueeze(0)
        gripper_target = torch.where(effective[:, 11:12] > 0.0, open_target, close_target)
        simulator_raw[:, self.joint_map.gripper_indices] = (
            gripper_target - default_dof_pos[:, self.joint_map.gripper_indices]
        ) / self.contract.robot_action_scale
        simulator_action = simulator_raw.clamp(
            -self.contract.robot_action_clip, self.contract.robot_action_clip
        )
        position_target = (
            default_dof_pos + self.contract.robot_action_scale * simulator_action
        )
        return FullActionWarpResultR5(
            stage_action=stage_action,
            base=base,
            logical_action=logical_action,
            simulator_raw_action_before_clip=simulator_raw,
            simulator_raw_action=simulator_action,
            simulator_action_clipped=simulator_action != simulator_raw,
            position_target=position_target,
        )


ACTION_WARP_AUDIT_R5 = [
    {
        "node": "DELTA_ACTION_ACCUMULATE_CLIP_STAGE_GATE",
        "production": [
            "gr00t/rl/envs/base_task/delta_action_base.py:59-90",
            "gr00t/rl/envs/door/door_open_a2_base.py:7390-7419",
        ],
        "resolved_config": "config_snapshot.yaml:1510-1519",
        "r5": "StageContractMinimal from config scale=0.3, clip=15, stage0 zero",
        "status": "MATCH",
    },
    {
        "node": "BASE_WARP",
        "production": "gr00t/rl/envs/base_task/warped_action_base.py:32-43",
        "resolved_config": "config_snapshot.yaml:1520-1528 k=0,s=0",
        "r5": "explicit identity",
        "status": "MATCH",
    },
    {
        "node": "V22_V23_BASE_INTERVENTIONS",
        "production": "gr00t/rl/envs/base_task/a2_base.py:610-685,1137-1139",
        "resolved_config": "keys absent",
        "r5": "disabled; raw base unchanged",
        "status": "MATCH_DISABLED",
    },
    {
        "node": "BASE_SCALE_POSTURE_CLAMP_FINAL_5D_CLAMP",
        "production": "gr00t/rl/envs/base_task/a2_base.py:1163-1188",
        "resolved_config": "config_snapshot.yaml:1401-1416,1564-1567",
        "r5": "scale raw; pitch/roll clamp; final clamp from resolved thresholds",
        "status": "MATCH",
    },
    {
        "node": "BASE_ECHO_AND_DEADBAND",
        "production": "gr00t/rl/envs/base_task/a2_base.py:1264-1271",
        "resolved_config": "config_snapshot.yaml:1404-1415",
        "r5": "clipped physical command * multipliers; xyz zero below norm 0.1",
        "status": "MATCH",
    },
    {
        "node": "GRIPPER_PRIMITIVE",
        "production": "gr00t/rl/envs/base_task/a2_base.py:1140-1161",
        "resolved_config": "config_snapshot.yaml:1429-1435,498",
        "r5": "raw >0 open else close; target-to-raw by action_scale",
        "status": "MATCH",
    },
    {
        "node": "LEG_POLICY_NAME_MAP",
        "production": "gr00t/rl/envs/base_task/a2_base.py:325-340,1145-1151",
        "resolved_config": "config_snapshot.yaml:1437-1448",
        "r5": "A2PiperJointMap policy order to sim order",
        "status": "MATCH",
    },
    {
        "node": "FINAL_20D_ACTION_CLIP",
        "production": "gr00t/rl/envs/legged_base_task/legged_robot_base.py:651-674",
        "resolved_config": "config_snapshot.yaml:498-502 action_clip_value=100",
        "r5": "clip raw simulator action before default+0.25*action target",
        "status": "MATCH",
    },
    {
        "node": "CONTROL_DELAY",
        "production": "gr00t/rl/envs/legged_base_task/legged_robot_base.py:667-674",
        "resolved_config": "config_snapshot.yaml:823-826 randomize_ctrl_delay=false",
        "r5": "no delay",
        "status": "MATCH_DISABLED",
    },
    {
        "node": "POSITION_TARGET_AND_MUJOCO_WRITE",
        "production": "gr00t/rl/envs/legged_base_task/legged_robot_base.py:1142-1155",
        "resolved_config": "config_snapshot.yaml:498 action_scale=0.25",
        "r5": "default + clipped raw*0.25; name-resolved native position write",
        "status": "MATCH_WITH_D5_DECLARED_NATIVE_ACTUATOR_DEVIATION",
    },
    {
        "node": "ACTION_AND_DELTA_OBSERVATION_ECHO",
        "production": [
            "gr00t/rl/envs/base_task/a2_base.py:1298-1307",
            "gr00t/rl/envs/base_task/delta_action_base.py:61-63,132-133",
        ],
        "resolved_config": "config_snapshot.yaml:1519 reset backmap=true but production callback is pass",
        "r5": "previous leg+effective arm+raw gripper; previous raw delta; reset zero",
        "status": "MATCH",
    },
]
