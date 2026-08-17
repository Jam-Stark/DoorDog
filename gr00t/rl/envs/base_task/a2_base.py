# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import json
from pathlib import Path

import torch
from typing_extensions import override

from gr00t.rl.envs.base_task.finger_primitive_base import FingerPrimitiveBase
from gr00t.rl.envs.legged_base_task.legged_robot_base import LeggedRobotBase
from gr00t.rl.utils.torch_utils import quat_rotate


def _load_a2_base_metadata(metadata_path):
    path = Path(metadata_path).expanduser()
    with path.open("r", encoding="utf-8") as f:
        metadata = json.load(f)
    obs_contract = metadata["contracts"]["obs"]
    action_contract = metadata["contracts"]["action"]
    contract = {
        "obs_dim": int(obs_contract["flattened_dim"]),
        "history_length": int(obs_contract["history_length"]),
        "frame_dim": int(obs_contract["dog_frame_dim"]),
        "action_dim": int(action_contract["dim"]),
        "leg_joint_names": list(action_contract["leg_joint_names"]),
        "leg_action_scale": float(action_contract["leg_action_scale"]),
        "use_default_offset": bool(action_contract["use_default_offset"]),
    }
    if contract["obs_dim"] != contract["history_length"] * contract["frame_dim"]:
        raise ValueError(f"A2_Base metadata obs contract is inconsistent: {contract}")
    return contract


def _validate_optional_a2_config_value(config, key, metadata_value):
    if key in config and config.get(key) != metadata_value:
        raise ValueError(
            f"A2_Base config {key}={config.get(key)} disagrees with metadata {metadata_value}"
        )


class A2Base(LeggedRobotBase):
    A2_BASE_COMMAND_ACTION_DIM = 5
    A2_ARM_ACTION_DIM = 6
    A2_GRIPPER_PRIMITIVE_ACTION_DIM = 1

    def __init__(self, config, device):
        self._use_a2_base = bool(config.get("a2_base", {}).get("enabled", False))
        if self._use_a2_base:
            LeggedRobotBase.__init__(self, config, device)
            self._init_a2_base_action_chain()
            return
        super().__init__(config, device)
        self._homie_history_length = self.config.obs.homie_history_length
        self._num_body_dof = self.config.robot.homie_dof_obs_size
        self._num_lower_dof = self.config.robot.lower_body_actions_dim
        self._num_upper_dof = self.config.robot.upper_body_actions_dim
        self._num_homie_commands = self.config.obs.obs_dims.b_homie_commands
        if self.config.robot.get("use_primitive", False):
            self._num_non_homie_command_actions = 14 + 2
        else:
            self._num_non_homie_command_actions = (
                self.config.robot.actions_dim - self._num_lower_dof
            )  # 14 + 14
        self._homie_commands = torch.zeros(
            self.num_envs, self._num_homie_commands, device=self.device, requires_grad=False
        )  # active homie command
        self._homie_commands_unclipped = torch.zeros(
            self.num_envs, self._num_homie_commands, device=self.device, requires_grad=False
        )
        self._last_homie_commands = torch.zeros(
            self.num_envs, self._num_homie_commands, device=self.device, requires_grad=False
        )
        self._homie_actions = torch.zeros(
            self.num_envs, self._num_lower_dof, device=self.device, requires_grad=False
        )  # lower body dof actions outputed by homie
        self._default_policy_actions = torch.zeros(
            self.num_envs,
            self._num_homie_commands + self._num_non_homie_command_actions,
            device=self.device,
            requires_grad=False,
        )  # full 7 homie commad + non-homie dof actions
        index = []
        for key, value in self.config.obs.homie_command_default.items():
            if key not in self.config.obs.homie_command_keys:
                self._default_policy_actions[:, self.config.obs.homie_command_index[key]] = (
                    torch.tensor(value, device=self.device)
                )
            else:
                index += self.config.obs.homie_command_index[key]
        self._homie_active_command_index = torch.tensor(index, device=self.device, dtype=torch.long)
        self._num_homie_active_commands = len(self._homie_active_command_index)

        # self.last_processed_commands = torch.zeros(self.num_envs, self._num_homie_commands + self._num_non_homie_command_actions, device=self.device, requires_grad=False)

        self._clip_homie_command = self.config.get("clip_homie_command", False)
        self._clip_upper_actions = self.config.get("clip_upper_actions", False)
        if self._clip_homie_command:
            self._homie_command_low_thres = torch.tensor(
                [
                    [
                        -self.config.clip_homie_linvel_x_threshold,
                        -self.config.clip_homie_linvel_y_threshold,
                        -self.config.clip_homie_angvel_threshold,
                        self.config.clip_homie_lower_height_threshold,
                        self.config.clip_homie_torso_roll_lower_threshold,
                        self.config.clip_homie_torso_pitch_lower_threshold,
                        self.config.clip_homie_torso_yaw_lower_threshold,
                    ]
                ],
                device=self.device,
            )
            self._homie_command_high_thres = torch.tensor(
                [
                    [
                        self.config.clip_homie_linvel_x_threshold,
                        self.config.clip_homie_linvel_y_threshold,
                        self.config.clip_homie_angvel_threshold,
                        self.config.clip_homie_upper_height_threshold,
                        self.config.clip_homie_torso_roll_upper_threshold,
                        self.config.clip_homie_torso_pitch_upper_threshold,
                        self.config.clip_homie_torso_yaw_upper_threshold,
                    ]
                ],
                device=self.device,
            )
        if self._clip_upper_actions:
            self.arm_vel_threshold = self.config.get("arm_vel_threshold", 0.2)
            self._clip_upper_actions_threshold = self.config.get(
                "clip_upper_actions_threshold", 0.5
            )

    def _init_a2_base_action_chain(self):
        a2_config = self.config.get("a2_base", {})
        a2_base_metadata_path = a2_config.get(
            "metadata_path", "./gr00t/rl/data/policies/A2_Base/policy_metadata.json"
        )
        a2_base_contract = _load_a2_base_metadata(a2_base_metadata_path)
        _validate_optional_a2_config_value(
            a2_config, "leg_action_dim", a2_base_contract["action_dim"]
        )
        _validate_optional_a2_config_value(
            a2_config, "obs_history_length", a2_base_contract["history_length"]
        )
        _validate_optional_a2_config_value(
            a2_config, "obs_frame_dim", a2_base_contract["frame_dim"]
        )
        if "policy_leg_order" in a2_config:
            configured_leg_order = list(a2_config.get("policy_leg_order"))
            if configured_leg_order != a2_base_contract["leg_joint_names"]:
                raise ValueError(
                    "A2_Base config policy_leg_order disagrees with metadata "
                    f"{a2_base_contract['leg_joint_names']}"
                )
        if not a2_base_contract["use_default_offset"]:
            raise ValueError("A2_Base metadata requires use_default_offset=true")
        robot_action_scale = float(self.config.robot.control.action_scale)
        if abs(a2_base_contract["leg_action_scale"] - robot_action_scale) > 1e-6:
            raise ValueError(
                "A2_Base leg_action_scale must match robot.control.action_scale: "
                f"{a2_base_contract['leg_action_scale']} vs {robot_action_scale}"
            )

        self._a2_high_level_action_dim = int(a2_config.get("high_level_action_dim", 12))
        self._a2_leg_action_dim = a2_base_contract["action_dim"]
        self._a2_obs_history_length = a2_base_contract["history_length"]
        self._a2_obs_frame_dim = a2_base_contract["frame_dim"]
        self._a2_obs_dim = a2_base_contract["obs_dim"]
        self._a2_leg_action_scale = a2_base_contract["leg_action_scale"]
        if "homie_history_length" not in self.config.obs:
            raise ValueError("A2_Base mode requires obs.homie_history_length.")
        self._homie_history_length = int(self.config.obs.homie_history_length)
        if self._homie_history_length <= 0:
            raise ValueError(
                "A2_Base obs.homie_history_length must be positive, got "
                f"{self._homie_history_length}"
            )
        self._a2_gait_frequency = float(a2_config.get("gait_frequency", 2.0))
        self._a2_gait_initial_phase = float(a2_config.get("gait_initial_phase", 0.0)) % 1.0
        self._a2_gait_standing_command_thresholds = torch.tensor(
            a2_config.get("gait_standing_command_thresholds", [0.1, 0.1, 0.2]),
            device=self.device,
            dtype=torch.float,
            requires_grad=False,
        )
        if self._a2_gait_standing_command_thresholds.numel() != 3:
            raise ValueError(
                "A2_Base gait_standing_command_thresholds must have 3 values, got "
                f"{self._a2_gait_standing_command_thresholds.numel()}"
            )
        self._a2_gait_standing_command_thresholds = (
            self._a2_gait_standing_command_thresholds.reshape(3)
        )
        self._a2_ref_dof_legs_sigma = float(a2_config.get("ref_dof_legs_sigma", 0.1))
        if self._a2_ref_dof_legs_sigma <= 0.0:
            raise ValueError(
                f"A2_Base ref_dof_legs_sigma must be positive, got {self._a2_ref_dof_legs_sigma}"
            )
        self._a2_ref_dof_legs_phase_offset = float(
            a2_config.get("ref_dof_legs_phase_offset", 0.5)
        )
        self._a2_ref_dof_legs_target_joint_pos_thd = float(
            a2_config.get("ref_dof_legs_target_joint_pos_thd", 0.1)
        )
        self._a2_ref_dof_legs_target_joint_pos_scale = float(
            a2_config.get("ref_dof_legs_target_joint_pos_scale", 0.35)
        )
        if self._a2_ref_dof_legs_target_joint_pos_scale < 0.0:
            raise ValueError(
                "A2_Base ref_dof_legs_target_joint_pos_scale must be non-negative, got "
                f"{self._a2_ref_dof_legs_target_joint_pos_scale}"
            )
        self._a2_ref_dof_legs_calf_scale_factor = float(
            a2_config.get("ref_dof_legs_calf_scale_factor", 2.0)
        )
        if self._a2_ref_dof_legs_calf_scale_factor < 0.0:
            raise ValueError(
                "A2_Base ref_dof_legs_calf_scale_factor must be non-negative, got "
                f"{self._a2_ref_dof_legs_calf_scale_factor}"
            )
        if (
            "command_scale" in a2_config
            and "base_command_scale" in a2_config
            and float(a2_config.get("command_scale")) != float(a2_config.get("base_command_scale"))
        ):
            raise ValueError(
                "A2_Base config command_scale disagrees with base_command_scale: "
                f"{a2_config.get('command_scale')} vs {a2_config.get('base_command_scale')}"
            )
        self._a2_base_command_scale = float(
            a2_config.get("command_scale", a2_config.get("base_command_scale", 0.25))
        )
        self._a2_body_pitch_roll_scale = float(a2_config.get("body_pitch_roll_scale", 0.4))
        if self._a2_body_pitch_roll_scale <= 0.0:
            raise ValueError(
                "A2_Base body_pitch_roll_scale must be positive, got "
                f"{self._a2_body_pitch_roll_scale}"
            )
        self._clip_homie_command = bool(self.config.get("clip_homie_command", False))
        if self._clip_homie_command:
            a2_base_command_low_thres = [
                -self.config.clip_homie_linvel_x_threshold,
                -self.config.clip_homie_linvel_y_threshold,
                -self.config.clip_homie_angvel_threshold,
                -self._a2_body_pitch_roll_scale,
                -self._a2_body_pitch_roll_scale,
            ]
            a2_base_command_high_thres = [
                self.config.clip_homie_linvel_x_threshold,
                self.config.clip_homie_linvel_y_threshold,
                self.config.clip_homie_angvel_threshold,
                self._a2_body_pitch_roll_scale,
                self._a2_body_pitch_roll_scale,
            ]
        else:
            a2_base_command_low_thres = [
                -float("inf"),
                -float("inf"),
                -float("inf"),
                -float("inf"),
                -float("inf"),
            ]
            a2_base_command_high_thres = [
                float("inf"),
                float("inf"),
                float("inf"),
                float("inf"),
                float("inf"),
            ]
        self._a2_base_command_low_thres = torch.tensor(
            a2_base_command_low_thres,
            device=self.device,
            dtype=torch.float,
            requires_grad=False,
        )
        self._a2_base_command_high_thres = torch.tensor(
            a2_base_command_high_thres,
            device=self.device,
            dtype=torch.float,
            requires_grad=False,
        )
        self._a2_dog_joint_vel_scale = float(a2_config.get("dog_joint_vel_scale", 0.05))
        if self._a2_dog_joint_vel_scale <= 0.0:
            raise ValueError(
                f"A2_Base dog_joint_vel_scale must be positive, got {self._a2_dog_joint_vel_scale}"
            )
        if (
            "command_obs_multipliers" in a2_config
            and "base_command_obs_multipliers" in a2_config
            and list(a2_config.get("command_obs_multipliers"))
            != list(a2_config.get("base_command_obs_multipliers"))
        ):
            raise ValueError(
                "A2_Base config command_obs_multipliers disagrees with "
                "base_command_obs_multipliers"
            )
        self._a2_base_command_obs_multipliers = torch.tensor(
            a2_config.get(
                "command_obs_multipliers",
                a2_config.get(
                    "base_command_obs_multipliers", [2.0, 2.0, 0.25, 1.0, 1.0]
                ),
            ),
            device=self.device,
            dtype=torch.float,
            requires_grad=False,
        )
        if self._a2_base_command_obs_multipliers.numel() != 5:
            raise ValueError(
                "A2_Base command_obs_multipliers must have 5 values, got "
                f"{self._a2_base_command_obs_multipliers.numel()}"
            )
        self._a2_policy_leg_order = a2_base_contract["leg_joint_names"]
        self._a2_leg_sim_indices = torch.tensor(
            [self.dof_names.index(name) for name in self._a2_policy_leg_order],
            device=self.device,
            dtype=torch.long,
        )
        self._a2_arm_dof_indices = torch.tensor(
            [self.dof_names.index(f"arm_j{i}") for i in range(1, 7)],
            device=self.device,
            dtype=torch.long,
        )
        self._a2_gripper_dof_indices = torch.tensor(
            [self.dof_names.index("arm_j7"), self.dof_names.index("arm_j8")],
            device=self.device,
            dtype=torch.long,
        )
        self._a2_gripper_open_target = torch.tensor(
            a2_config.get("gripper_open_target", [0.035, -0.035]),
            device=self.device,
            dtype=torch.float,
            requires_grad=False,
        )
        self._a2_gripper_close_target = torch.tensor(
            a2_config.get("gripper_close_target", [0.0, 0.0]),
            device=self.device,
            dtype=torch.float,
            requires_grad=False,
        )
        self._a2_gripper_primitive_limit = float(
            a2_config.get("gripper_primitive_limit", 1.0)
        )
        if self._a2_gripper_primitive_limit <= 0.0:
            raise ValueError(
                "A2_Base gripper_primitive_limit must be positive, got "
                f"{self._a2_gripper_primitive_limit}"
            )
        self._a2_gripper_primitive_limit_tolerance = float(
            a2_config.get("gripper_primitive_limit_tolerance", 1.1)
        )
        if self._a2_gripper_primitive_limit_tolerance <= 0.0:
            raise ValueError(
                "A2_Base gripper_primitive_limit_tolerance must be positive, got "
                f"{self._a2_gripper_primitive_limit_tolerance}"
            )
        self._last_a2_leg_actions = torch.zeros(
            self.num_envs, self._a2_leg_action_dim, device=self.device, requires_grad=False
        )
        self._last_a2_arm_actions = torch.zeros(
            self.num_envs, 6, device=self.device, requires_grad=False
        )
        self._a2_base_command_raw = torch.zeros(
            self.num_envs, 5, device=self.device, requires_grad=False
        )
        self._a2_gripper_primitive_raw = torch.zeros(
            self.num_envs, 1, device=self.device, requires_grad=False
        )
        self._a2_gait_phase = torch.zeros(
            self.num_envs, device=self.device, requires_grad=False
        )
        self._a2_gait_last_update_step = torch.full(
            (self.num_envs,),
            self._get_a2_gait_current_step(),
            device=self.device,
            dtype=torch.long,
            requires_grad=False,
        )
        self._a2_base_obs_history = torch.zeros(
            self.num_envs,
            self._a2_obs_history_length,
            self._a2_obs_frame_dim,
            device=self.device,
            requires_grad=False,
        )
        self._a2_base_obs_history_initialized = torch.zeros(
            self.num_envs, device=self.device, dtype=torch.bool, requires_grad=False
        )
        if "a2_base_command" not in self.config.obs.obs_dims:
            raise ValueError(
                "A2_Base mode requires obs_dims.a2_base_command; old public "
                "base_command/b_homie_commands obs keys are not accepted"
            )
        self._num_homie_commands = int(self.config.obs.obs_dims.a2_base_command)
        if self._num_homie_commands != 5:
            raise ValueError(
                "A2_Base mode expects obs_dims.a2_base_command == 5 for "
                f"[x,y,yaw,pitch,roll], got {self._num_homie_commands}"
            )
        self._num_lower_dof = self._a2_leg_action_dim
        self._num_body_dof = self._a2_leg_action_dim
        self._homie_commands = torch.zeros(
            self.num_envs, self._num_homie_commands, device=self.device, requires_grad=False
        )
        self._homie_commands_unclipped = torch.zeros_like(self._homie_commands)
        self._last_homie_commands = torch.zeros_like(self._homie_commands)
        self._homie_actions = torch.zeros(
            self.num_envs, self._a2_leg_action_dim, device=self.device, requires_grad=False
        )

        # Validate the configured high-level action contract against the canonical
        # base + Piper arm + gripper layout consumed by _step_a2_base().
        self.get_a2_high_level_action_layout()

    def get_a2_high_level_action_layout(self) -> dict[str, int]:
        if not self._use_a2_base:
            raise RuntimeError("A2 high-level action layout is only defined in A2_Base mode.")
        expected_dim = (
            self.A2_BASE_COMMAND_ACTION_DIM
            + self.A2_ARM_ACTION_DIM
            + self.A2_GRIPPER_PRIMITIVE_ACTION_DIM
        )
        if self._a2_high_level_action_dim != expected_dim:
            raise RuntimeError(
                "A2 high-level action layout requires "
                f"high_level_action_dim={expected_dim}; got {self._a2_high_level_action_dim}."
            )
        if tuple(self._a2_arm_dof_indices.shape) != (self.A2_ARM_ACTION_DIM,):
            raise RuntimeError(
                "A2 high-level action layout requires six arm DOF indices; "
                f"got shape {tuple(self._a2_arm_dof_indices.shape)}."
            )
        if tuple(self._a2_gripper_dof_indices.shape) != (2,):
            raise RuntimeError(
                "A2 high-level action layout requires arm_j7/arm_j8 DOF indices; "
                f"got shape {tuple(self._a2_gripper_dof_indices.shape)}."
            )

        base_start = 0
        base_end = base_start + self.A2_BASE_COMMAND_ACTION_DIM
        arm_start = base_end
        arm_end = arm_start + self.A2_ARM_ACTION_DIM
        gripper_index = arm_end
        return {
            "dim": expected_dim,
            "base_start": base_start,
            "base_end": base_end,
            "arm_start": arm_start,
            "arm_end": arm_end,
            "gripper_index": gripper_index,
        }

    @override
    def _reset_buffers_callback(self, env_ids, target_buf):
        if self._use_a2_base:
            LeggedRobotBase._reset_buffers_callback(self, env_ids, target_buf)
            self._last_a2_leg_actions[env_ids, :] = 0.0
            self._last_a2_arm_actions[env_ids, :] = 0.0
            self._a2_base_command_raw[env_ids, :] = 0.0
            self._a2_gripper_primitive_raw[env_ids, :] = 0.0
            self._a2_gait_phase[env_ids] = self._a2_gait_initial_phase
            self._a2_gait_last_update_step[env_ids] = self._get_a2_gait_current_step()
            self._a2_base_obs_history[env_ids, :, :] = 0.0
            self._a2_base_obs_history_initialized[env_ids] = False
            self._homie_actions[env_ids, :] = 0.0
            self._homie_commands[env_ids, :] = 0.0
            self._homie_commands_unclipped[env_ids, :] = 0.0
            self._last_homie_commands[env_ids, :] = 0.0
            return
        super()._reset_buffers_callback(env_ids, target_buf)
        self._homie_actions[env_ids, :] = 0.0

    @override
    def step(self, actor_state):
        if self._use_a2_base:
            return self._step_a2_base(actor_state)

        actions = actor_state["actions"]
        self.processed_commands = (
            self._default_policy_actions.clone()
        )  # [num_envs, num_homie_commands + upper_body_actions (7 + 28)]
        self.processed_commands[:, self._homie_active_command_index] = actions[
            :, : self._num_homie_active_commands
        ]
        # if actions.shape[1] == self._num_homie_active_commands + self._num_lower_dof:
        #     # in case the policy only outputs homie commands
        #     self.processed_commands[:, self._num_homie_commands:] = 0.0
        # else:
        #     # non-homie actions
        #     self.processed_commands[:, self._num_homie_commands:] = actions[:, self._num_homie_active_commands:-self._num_lower_dof]

        self._homie_commands = (
            self.processed_commands[:, : self._num_homie_commands] * self.config.homie_command_scale
        )
        self._homie_commands[:, 3] += self.config.obs.homie_default_height  # height
        self._homie_commands_unclipped[:] = self._homie_commands

        if self._clip_homie_command:
            self._homie_commands = torch.clamp(
                self._homie_commands, self._homie_command_low_thres, self._homie_command_high_thres
            )

        self._homie_actions = actions[:, -self._num_lower_dof :]

        if self._clip_upper_actions:
            raw_arm_commands = self.processed_commands[:, self._num_homie_commands : -2]
            num_lower_dof = self._homie_actions.shape[-1]
            arm_default_pos = self.default_dof_pos[:, num_lower_dof : num_lower_dof + 14]
            dof_pos = self.simulator.dof_pos[:, num_lower_dof : num_lower_dof + 14]
            # dof_vel = self.simulator.dof_vel[:, num_lower_dof:num_lower_dof + 14]
            target_raw = raw_arm_commands * self.config.robot.control.action_scale + arm_default_pos
            target_clipped = torch.clamp(
                target_raw,
                -self._clip_upper_actions_threshold + dof_pos,
                self._clip_upper_actions_threshold + dof_pos,
            )
            self.processed_commands[:, self._num_homie_commands : -2] = (
                target_clipped - arm_default_pos
            ) / self.config.robot.control.action_scale
            # clip_condition = ((dof_vel > self.arm_vel_threshold) | (dof_vel < -self.arm_vel_threshold))
            # clip_value = torch.where(clip_condition, dof_pos, target_raw)
            # self.processed_commands[:, self._num_homie_commands:-2] = (clip_value - arm_default_pos) / self.config.robot.control.action_scale
            # alpha = 0.8
            # self.processed_commands[:, self._num_homie_commands:-2] = alpha * self.processed_commands[:, self._num_homie_commands:-2] + (1 - alpha) * self.last_processed_commands[:, self._num_homie_commands:-2]
            # self.last_processed_commands[:, self._num_homie_commands:-2] = self.processed_commands[:, self._num_homie_commands:-2].clone()
        whole_body_actions = torch.cat(
            [
                self._homie_actions,  # lower-body actions
                self.processed_commands[
                    :, self._num_homie_commands :
                ],  # non-homie upper body actions
            ],
            dim=-1,
        )

        self._pre_physics_step(whole_body_actions)
        self._physics_step()
        self._post_physics_step()

        self._last_homie_commands[:] = self._homie_commands

        return self.obs_buf_dict, self.rew_buf, self.reset_buf, self.extras

    def _step_a2_base(self, actor_state):
        actions = actor_state["actions"]
        if actions.shape[-1] != self._a2_high_level_action_dim + self._a2_leg_action_dim:
            raise ValueError(
                "A2_Base mode expects trainer action dim "
                f"{self._a2_high_level_action_dim + self._a2_leg_action_dim}, got {actions.shape[-1]}"
            )

        layout = self.get_a2_high_level_action_layout()
        high_level_actions = actions[:, : layout["dim"]]
        capture_eval_env_action = getattr(
            self, "_capture_a2_eval_post_delta_post_warp_env_action", None
        )
        if capture_eval_env_action is not None:
            capture_eval_env_action(high_level_actions)
        raw_base_action = high_level_actions[:, layout["base_start"] : layout["base_end"]]
        arm_actions = high_level_actions[:, layout["arm_start"] : layout["arm_end"]]
        gripper_primitive = high_level_actions[
            :, layout["gripper_index"] : layout["gripper_index"] + 1
        ]
        self._a2_gripper_primitive_raw[:] = gripper_primitive
        leg_actions = actions[:, -self._a2_leg_action_dim :]

        final_actions = torch.zeros(
            self.num_envs, self.num_dof, device=self.device, dtype=actions.dtype
        )
        final_actions[:, self._a2_leg_sim_indices] = leg_actions
        final_actions[:, self._a2_arm_dof_indices] = arm_actions

        gripper_target = torch.where(
            gripper_primitive > 0.0,
            self._a2_gripper_open_target[None, :],
            self._a2_gripper_close_target[None, :],
        )
        gripper_raw = (
            gripper_target - self.default_dof_pos[:, self._a2_gripper_dof_indices]
        ) / self.config.robot.control.action_scale
        final_actions[:, self._a2_gripper_dof_indices] = gripper_raw

        scaled_base_command_raw = torch.cat(
            [
                raw_base_action[:, :3] * self._a2_base_command_scale,
                raw_base_action[:, 3:5] * self._a2_body_pitch_roll_scale,
            ],
            dim=-1,
        )
        scaled_base_command = torch.cat(
            [
                scaled_base_command_raw[:, :3],
                raw_base_action[:, 3:5].clamp(-1.0, 1.0) * self._a2_body_pitch_roll_scale,
            ],
            dim=-1,
        )
        if self._clip_homie_command:
            scaled_base_command = torch.clamp(
                scaled_base_command,
                self._a2_base_command_low_thres.to(dtype=actions.dtype),
                self._a2_base_command_high_thres.to(dtype=actions.dtype),
            )

        self._a2_base_command_raw[:] = raw_base_action
        self._homie_commands[:, :] = 0.0
        self._homie_commands_unclipped[:, :] = 0.0
        self._homie_commands_unclipped[:, :5] = scaled_base_command_raw
        self._homie_commands[:, :5] = scaled_base_command
        self._homie_actions[:] = leg_actions
        self._last_a2_leg_actions[:] = leg_actions
        self._last_a2_arm_actions[:] = arm_actions

        self._pre_physics_step(final_actions)
        self._physics_step()
        self._post_physics_step()

        self._last_homie_commands[:] = self._homie_commands

        return self.obs_buf_dict, self.rew_buf, self.reset_buf, self.extras

    @override
    def _action_backmap(self):
        if self._use_a2_base:
            action = torch.zeros(
                self.num_envs,
                self._a2_high_level_action_dim + self._a2_leg_action_dim,
                device=self.device,
            )
            whole_body_action_backmap = LeggedRobotBase._action_backmap(self)
            action[:, 5:11] = whole_body_action_backmap[:, self._a2_arm_dof_indices]
            action[:, 11:12] = torch.where(
                self.simulator.dof_pos[:, self._a2_gripper_dof_indices[0:1]]
                > 0.5 * self._a2_gripper_open_target[0],
                torch.ones(self.num_envs, 1, device=self.device),
                torch.zeros(self.num_envs, 1, device=self.device),
            )
            action[:, -self._a2_leg_action_dim :] = whole_body_action_backmap[
                :, self._a2_leg_sim_indices
            ]
            return action

        whole_body_action_backmap = super()._action_backmap()

        return torch.cat(
            [
                torch.zeros(self.num_envs, self._num_homie_active_commands, device=self.device),
                whole_body_action_backmap[:, self._homie_actions.shape[1] :],
            ],
            dim=-1,
        )

    def _reward_penalty_homie_action_rate(self):
        return torch.sum(torch.square(self._last_homie_commands - self._homie_commands), dim=1)

    def _reward_penalty_base_command_limit(self):
        return torch.sum(
            torch.square(self._homie_commands_unclipped[:, :5] - self._homie_commands[:, :5]),
            dim=1,
        )

    def _reward_penalty_homie_action_limit(self):
        if self._use_a2_base:
            return self._reward_penalty_base_command_limit()
        return torch.sum(torch.square(self._homie_commands_unclipped - self._homie_commands), dim=1)

    def _reward_limits_gripper_primitive_action(self):
        limit = (
            self._a2_gripper_primitive_limit
            * self._a2_gripper_primitive_limit_tolerance
        )
        return torch.relu(torch.abs(self._a2_gripper_primitive_raw) - limit).squeeze(-1)

    def get_physical_homie_commands(self):
        commands = self._homie_commands.clone()
        return commands

    def get_physical_base_command(self):
        return self._homie_commands[:, :5].clone()

    @property
    def ground_height(self):
        return 0.0

    def _get_obs_a2_base_command_raw(self):
        return self._unwarped_actions

    def _get_obs_a2_base_command(self):
        commands = self._homie_commands[:, :5].clone()
        commands[:, :] *= self._a2_base_command_obs_multipliers[None, :]
        commands[self._homie_commands[:, :3].norm(dim=-1) < 0.1, :3] = 0.0
        return commands

    def _get_obs_b_homie_commands(self):
        return self._get_obs_a2_base_command()

    def _get_obs_base_command(self):
        return self._get_obs_a2_base_command()

    def _get_obs_e_homie_dof_pos(self):
        return (
            self.simulator.dof_pos[:, : self._num_body_dof]
            - self.default_dof_pos[:, : self._num_body_dof]
        )

    def _get_obs_f_homie_dof_vel(self):
        return self.simulator.dof_vel[:, : self._num_body_dof]

    def _get_obs_c_homie_base_ang_vel(self):
        return self.base_ang_vel

    def _get_obs_d_homie_projected_gravity(self):
        return self.projected_gravity

    def _get_obs_g_homie_body_actions(self):
        return self._homie_actions

    @override
    def _get_obs_actions(self):
        if self._use_a2_base:
            return torch.cat(
                [
                    self._last_a2_leg_actions,
                    self._last_a2_arm_actions,
                    self._a2_gripper_primitive_raw,
                ],
                dim=-1,
            )
        return LeggedRobotBase._get_obs_actions(self)

    def _get_a2_projected_gravity_b(self):
        return self.projected_gravity

    def _get_a2_dog_joint_pos_rel(self):
        return (
            self.simulator.dof_pos[:, self._a2_leg_sim_indices]
            - self.default_dof_pos[:, self._a2_leg_sim_indices]
        )

    def _get_a2_dog_joint_vel_scaled(self):
        return (
            self.simulator.dof_vel[:, self._a2_leg_sim_indices]
            * self._a2_dog_joint_vel_scale
        )

    def _get_a2_dog_actions(self):
        return self._last_a2_leg_actions

    def _get_a2_commands_dog_scaled(self):
        commands = torch.zeros(
            self.num_envs,
            5,
            device=self.device,
            dtype=self._a2_base_command_raw.dtype,
            requires_grad=False,
        )
        commands[:, :] = (
            self._homie_commands[:, :5] * self._a2_base_command_obs_multipliers[None, :]
        )
        return commands

    def _get_a2_arm_command_obs(self):
        return torch.zeros(
            self.num_envs,
            6,
            device=self.device,
            dtype=self._a2_base_command_raw.dtype,
            requires_grad=False,
        )

    def _get_a2_base_roll_pitch(self):
        return self.rpy[:, 0:2]

    def _get_a2_gait_current_step(self):
        return int(getattr(self, "common_step_counter", 0))

    def _get_a2_gait_standing_mask(self):
        physical_command = self._homie_commands[:, :3]
        thresholds = self._a2_gait_standing_command_thresholds.to(
            dtype=physical_command.dtype
        )
        return (torch.abs(physical_command) < thresholds[None, :]).all(dim=1)

    def _update_a2_gait_phase_once(self):
        current_step = self._get_a2_gait_current_step()
        standing_mask = self._get_a2_gait_standing_mask()
        update_mask = self._a2_gait_last_update_step < current_step

        if update_mask.any():
            moving_update_mask = update_mask & ~standing_mask
            if moving_update_mask.any():
                phase_inc = float(self.dt) * self._a2_gait_frequency
                self._a2_gait_phase[moving_update_mask] = torch.remainder(
                    self._a2_gait_phase[moving_update_mask] + phase_inc,
                    1.0,
                )
            standing_update_mask = update_mask & standing_mask
            if standing_update_mask.any():
                self._a2_gait_phase[standing_update_mask] = 0.0
            self._a2_gait_last_update_step[update_mask] = current_step

        if standing_mask.any():
            self._a2_gait_phase[standing_mask] = 0.0

    def _get_a2_gait_clock_signal(self):
        self._update_a2_gait_phase_once()
        return torch.stack(
            [
                torch.sin(2.0 * torch.pi * self._a2_gait_phase),
                torch.cos(2.0 * torch.pi * self._a2_gait_phase),
            ],
            dim=1,
        )

    def _get_a2_ref_dof_legs(self):
        ref_dof = self.default_dof_pos[:, self._a2_leg_sim_indices]
        if ref_dof.shape[0] == 1:
            ref_dof = ref_dof.repeat(self.num_envs, 1)
        elif ref_dof.shape[0] == self.num_envs:
            ref_dof = ref_dof.clone()
        else:
            raise ValueError(
                "A2_Base default_dof_pos batch dim must be 1 or num_envs, got "
                f"{ref_dof.shape[0]} for num_envs={self.num_envs}"
            )
        # Use the cached gait phase; gait clock observation owns phase advancement.
        phase = self._a2_gait_phase.to(dtype=ref_dof.dtype)
        foot_phase = torch.remainder(
            torch.stack(
                [
                    phase + self._a2_ref_dof_legs_phase_offset,
                    phase,
                    phase,
                    phase + self._a2_ref_dof_legs_phase_offset,
                ],
                dim=1,
            ),
            1.0,
        )
        sin_wave = torch.sin(2.0 * torch.pi * foot_phase)
        swing_mask = sin_wave > 0.0
        threshold = torch.tensor(
            self._a2_ref_dof_legs_target_joint_pos_thd,
            device=self.device,
            dtype=ref_dof.dtype,
        ).clamp(-0.99, 0.99)
        lift = torch.clamp(sin_wave - threshold, min=0.0) / (1.0 - threshold)
        lift = torch.where(swing_mask, lift, torch.zeros_like(lift))
        standing_mask = self._get_a2_gait_standing_mask()
        lift = torch.where(standing_mask[:, None], torch.zeros_like(lift), lift)

        ref_dof[:, 4:8] += lift * self._a2_ref_dof_legs_target_joint_pos_scale
        ref_dof[:, 8:12] -= (
            lift
            * self._a2_ref_dof_legs_target_joint_pos_scale
            * self._a2_ref_dof_legs_calf_scale_factor
        )
        return ref_dof

    def _reward_ref_dof_legs(self):
        current_dof = self.simulator.dof_pos[:, self._a2_leg_sim_indices]
        ref_dof = self._get_a2_ref_dof_legs()
        return torch.exp(
            -torch.sum(torch.square(current_dof - ref_dof), dim=1)
            / self._a2_ref_dof_legs_sigma
        )

    def _get_a2_base_obs_frame(self):
        frame = torch.zeros(
            self.num_envs, self._a2_obs_frame_dim, device=self.device, requires_grad=False
        )
        frame[:, 0:3] = self._get_a2_projected_gravity_b()
        frame[:, 3:15] = self._get_a2_dog_joint_pos_rel()
        frame[:, 15:27] = self._get_a2_dog_joint_vel_scaled()
        frame[:, 27:39] = self._get_a2_dog_actions()
        frame[:, 39:44] = self._get_a2_commands_dog_scaled()
        frame[:, 44:50] = self._get_a2_arm_command_obs()
        frame[:, 50:52] = self._get_a2_base_roll_pitch()
        frame[:, 52:54] = self._get_a2_gait_clock_signal()
        return frame

    def _get_obs_a2_base_obs(self):
        current_frame = self._get_a2_base_obs_frame()
        initialized_envs = self._a2_base_obs_history_initialized
        uninitialized_envs = ~initialized_envs

        if initialized_envs.any():
            self._a2_base_obs_history[initialized_envs, :-1, :] = self._a2_base_obs_history[
                initialized_envs, 1:, :
            ].clone()
            self._a2_base_obs_history[initialized_envs, -1, :] = current_frame[initialized_envs]
        if uninitialized_envs.any():
            self._a2_base_obs_history[uninitialized_envs, :, :] = current_frame[
                uninitialized_envs
            ].unsqueeze(1).expand(-1, self._a2_obs_history_length, -1)
            self._a2_base_obs_history_initialized[uninitialized_envs] = True
        obs = self._a2_base_obs_history.reshape(self.num_envs, -1)
        if obs.shape[-1] != self._a2_obs_dim:
            raise ValueError(
                f"A2_Base obs dim mismatch: got {obs.shape[-1]}, expected {self._a2_obs_dim}"
            )
        return obs

    def _get_obs_a_history_homie(self):
        assert "a_history_homie" in self.config.obs.obs_auxiliary.keys()
        history_config = self.config.obs.obs_auxiliary["a_history_homie"]
        history_tensors = []
        for item in range(self._homie_history_length):
            for key in history_config.keys():
                history_tensor = self.history_handler.query(key)[:, item]
                history_tensors.append(history_tensor)
        return torch.cat(history_tensors, dim=-1)


class TestA2Base(A2Base):
    def _reward_test_homie(self):
        root_vel = self.simulator.robot_root_states[:, 7:10]
        ref_root_vel = torch.tensor([[0.2, 0.3, 0.0]], device=self.device).repeat(self.num_envs, 1)
        base_quat = self.simulator.base_quat
        ref_root_vel = quat_rotate(base_quat, ref_root_vel)
        root_height = self.simulator.robot_root_states[:, 2]
        ref_root_height = self.config.ref_height
        return self._tracking_reward_util(
            root_vel - ref_root_vel, std=0.1, target=0.0, scale=1.0, offset=0.0
        ).mean(dim=-1) + self._tracking_reward_util(
            root_height - ref_root_height, std=0.1, target=0.0, scale=1.0, offset=0.0
        )

    def _reward_penalty_upper_body_deviation_l1(self):
        return torch.abs(
            self.simulator.dof_pos[:, self.upper_dof_indices]
            - self.default_dof_pos[:, self.upper_dof_indices]
        ).sum(dim=-1)


class TestA2WithFingerPrimitive(TestA2Base, FingerPrimitiveBase):
    def __init__(self, config, device):
        super().__init__(config, device)
        self._left_p0 = torch.tensor(
            self.config.robot.finger_primitive.primitive_action_map.left.pos_0,
            device=self.device,
            requires_grad=False,
        )
        self._left_p1 = torch.tensor(
            self.config.robot.finger_primitive.primitive_action_map.left.pos_1,
            device=self.device,
            requires_grad=False,
        )
        self._right_p0 = torch.tensor(
            self.config.robot.finger_primitive.primitive_action_map.right.pos_0,
            device=self.device,
            requires_grad=False,
        )
        self._right_p1 = torch.tensor(
            self.config.robot.finger_primitive.primitive_action_map.right.pos_1,
            device=self.device,
            requires_grad=False,
        )

        self._left_dof_idx = [
            self.dof_names.index(name)
            for name in self.config.robot.finger_primitive.primitive_action_map.left.dof_names
        ]
        self._right_dof_idx = [
            self.dof_names.index(name)
            for name in self.config.robot.finger_primitive.primitive_action_map.right.dof_names
        ]
        self._upper_non_finger_dof_idx = [
            i
            for i in self.upper_dof_indices
            if i not in self._left_dof_idx and i not in self._right_dof_idx
        ]

        self._target_period = self.config.target_period

    def _reward_penalty_upper_body_non_finger_deviation_l1(self):
        return torch.abs(
            self.simulator.dof_pos[:, self._upper_non_finger_dof_idx]
            - self.default_dof_pos[:, self._upper_non_finger_dof_idx]
        ).sum(dim=-1)

    def _reward_finger_sine_wave(self):
        phase = (
            torch.sin(self.episode_length_buf * 2 * torch.pi * self.dt / self._target_period) + 1.0
        ) / 2
        left_target = torch.lerp(self._left_p0[None, :], self._left_p1[None, :], phase[:, None])
        right_target = torch.lerp(self._right_p0[None, :], self._right_p1[None, :], phase[:, None])

        left_current = self.simulator.dof_pos[:, self._left_dof_idx]
        right_current = self.simulator.dof_pos[:, self._right_dof_idx]

        left_reward = self._tracking_reward_util(
            left_current - left_target, std=0.1, target=0.0, scale=1.0, offset=0.0
        )
        right_reward = self._tracking_reward_util(
            right_current - right_target, std=0.1, target=0.0, scale=1.0, offset=0.0
        )

        return left_reward.mean(dim=-1) + right_reward.mean(dim=-1)

    def _get_obs_phase(self):
        return torch.sin(self.episode_length_buf * 2 * torch.pi * self.dt / self._target_period)[
            :, None
        ]


# Compatibility aliases for legacy callers that import these symbols from this
# module. Current A2 action path imports A2Base directly.
HomieBase = A2Base
TestHomieBase = TestA2Base
TestHomieWithFingerPrimitive = TestA2WithFingerPrimitive
