# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import re

import isaaclab.sim as sim_utils
import omni.usd
import torch
import torch.nn.functional as F
from isaacsim.core.simulation_manager import SimulationManager
from isaaclab.sensors import ContactSensor, ContactSensorCfg, FrameTransformer, FrameTransformerCfg
from isaaclab.sensors.frame_transformer import OffsetCfg
from isaaclab.utils.math import (
    axis_angle_from_quat,
    euler_xyz_from_quat,
    is_identity_pose,
    quat_apply,
    quat_from_euler_xyz,
    quat_inv,
    quat_mul,
    subtract_frame_transforms,
    wrap_to_pi,
)
from pxr import Usd, UsdPhysics
from typing_extensions import override

from gr00t.rl.envs.base_task.delta_action_base import DeltaActionBase
from gr00t.rl.envs.base_task.a2_base import A2Base
from gr00t.rl.envs.base_task.finger_primitive_base import FingerPrimitiveBase
from gr00t.rl.envs.base_task.staged_task_base import StagedTaskBase
from gr00t.rl.envs.base_task.warped_action_base import WarpedActionBase
from gr00t.rl.envs.door.reset_from_dataset import ResetFromDataset
from gr00t.rl.isaac_utils.rotations import quat_to_tan_norm, wxyz_to_xyzw, xyzw_to_wxyz
from gr00t.rl.utils.torch_utils import torch_rand_float


class OrderedTargetFrameTransformer(FrameTransformer):
    """FrameTransformer variant that preserves cfg.target_frames order for duplicate target bodies."""

    def _initialize_impl(self):
        super(FrameTransformer, self)._initialize_impl()

        source_frame_offset_pos = torch.tensor(self.cfg.source_frame_offset.pos, device=self.device)
        source_frame_offset_quat = torch.tensor(
            self.cfg.source_frame_offset.rot, device=self.device
        )
        self._apply_source_frame_offset = True
        if is_identity_pose(source_frame_offset_pos, source_frame_offset_quat):
            self._apply_source_frame_offset = False
        else:
            self._source_frame_offset_pos = source_frame_offset_pos.unsqueeze(0).repeat(
                self._num_envs, 1
            )
            self._source_frame_offset_quat = source_frame_offset_quat.unsqueeze(0).repeat(
                self._num_envs, 1
            )

        body_names_to_frames = {}
        target_offsets = {}
        self._apply_target_frame_offset = False
        self._source_is_also_target_frame = False

        target_frame_names = set()
        for target_frame in self.cfg.target_frames:
            frame_name = (
                target_frame.name
                if target_frame.name is not None
                else target_frame.prim_path.rsplit("/", 1)[-1]
            )
            if frame_name in target_frame_names:
                raise RuntimeError(
                    f"FrameTransformer target frame name {frame_name!r} is duplicated."
                )
            target_frame_names.add(frame_name)

            offset = target_frame.offset
            if offset is not None:
                offset_pos = torch.tensor(offset.pos, device=self.device)
                offset_quat = torch.tensor(offset.rot, device=self.device)
                if not is_identity_pose(offset_pos, offset_quat):
                    self._apply_target_frame_offset = True
                target_offsets[frame_name] = {"pos": offset_pos, "quat": offset_quat}

        frames = [None] + [target_frame.name for target_frame in self.cfg.target_frames]
        frame_prim_paths = [self.cfg.prim_path] + [
            target_frame.prim_path for target_frame in self.cfg.target_frames
        ]
        frame_types = ["source"] + ["target"] * len(self.cfg.target_frames)
        for frame, prim_path, frame_type in zip(frames, frame_prim_paths, frame_types):
            matching_prims = sim_utils.find_matching_prims(prim_path)
            if len(matching_prims) == 0:
                raise ValueError(
                    f"Failed to create frame transformer for frame '{frame}' with path "
                    f"'{prim_path}'. No matching prims were found."
                )
            for prim in matching_prims:
                matching_prim_path = prim.GetPath().pathString
                if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
                    raise ValueError(
                        f"While resolving expression '{prim_path}' found a prim "
                        f"'{matching_prim_path}' which is not a rigid body. The class only "
                        "supports transformations between rigid bodies."
                    )

                body_name = self._get_relative_body_path(matching_prim_path)
                frame_name = frame if frame is not None else matching_prim_path.rsplit("/", 1)[-1]

                if body_name in body_names_to_frames:
                    if frame_name not in body_names_to_frames[body_name]["frames"]:
                        body_names_to_frames[body_name]["frames"].append(frame_name)
                    if body_names_to_frames[body_name]["type"] == "source" and frame_type == "target":
                        self._source_is_also_target_frame = True
                else:
                    body_names_to_frames[body_name] = {
                        "frames": [frame_name],
                        "prim_path": matching_prim_path,
                        "type": frame_type,
                    }

        tracked_prim_paths = [
            body_names_to_frames[body_name]["prim_path"] for body_name in body_names_to_frames.keys()
        ]
        tracked_body_names = [body_name for body_name in body_names_to_frames.keys()]
        body_names_regex = [
            tracked_prim_path.replace("env_0", "env_*")
            for tracked_prim_path in tracked_prim_paths
        ]

        self._physics_sim_view = SimulationManager.get_physics_sim_view()
        self._frame_physx_view = self._physics_sim_view.create_rigid_body_view(body_names_regex)

        all_prim_paths = self._frame_physx_view.prim_paths
        if "env_" in all_prim_paths[0]:

            def extract_env_num_and_prim_path(item: str) -> tuple[int, str]:
                match = re.search(r"env_(\d+)(.*)", item)
                return (int(match.group(1)), match.group(2))

            self._per_env_indices = [
                index
                for index, _ in sorted(
                    list(enumerate(all_prim_paths)), key=lambda x: extract_env_num_and_prim_path(x[1])
                )
            ]
            sorted_prim_paths = [
                all_prim_paths[index]
                for index in self._per_env_indices
                if "env_0" in all_prim_paths[index]
            ]
        else:
            self._per_env_indices = [
                index for index, _ in sorted(enumerate(all_prim_paths), key=lambda x: x[1])
            ]
            sorted_prim_paths = [all_prim_paths[index] for index in self._per_env_indices]

        self._target_frame_body_names = [
            self._get_relative_body_path(prim_path) for prim_path in sorted_prim_paths
        ]
        self._source_frame_body_name = self._get_relative_body_path(self.cfg.prim_path)
        source_frame_index = self._target_frame_body_names.index(self._source_frame_body_name)

        if not self._source_is_also_target_frame:
            self._target_frame_body_names.remove(self._source_frame_body_name)

        all_ids = torch.arange(self._num_envs * len(tracked_body_names))
        self._source_frame_body_ids = (
            torch.arange(self._num_envs) * len(tracked_body_names) + source_frame_index
        )

        if self._source_is_also_target_frame:
            self._target_frame_body_ids = all_ids
        else:
            self._target_frame_body_ids = all_ids[~torch.isin(all_ids, self._source_frame_body_ids)]

        self._target_frame_names = []
        target_frame_offset_pos = []
        target_frame_offset_quat = []
        duplicate_frame_indices = []
        for i, body_name in enumerate(self._target_frame_body_names):
            for frame in body_names_to_frames[body_name]["frames"]:
                if frame in target_offsets:
                    target_frame_offset_pos.append(target_offsets[frame]["pos"])
                    target_frame_offset_quat.append(target_offsets[frame]["quat"])
                    self._target_frame_names.append(frame)
                    duplicate_frame_indices.append(i)

        duplicate_frame_indices = torch.tensor(duplicate_frame_indices, device=self.device)
        if self._source_is_also_target_frame:
            num_target_body_frames = len(tracked_body_names)
        else:
            num_target_body_frames = len(tracked_body_names) - 1

        self._duplicate_frame_indices = torch.cat(
            [
                duplicate_frame_indices + num_target_body_frames * env_num
                for env_num in range(self._num_envs)
            ]
        )

        if self._apply_target_frame_offset:
            self._target_frame_offset_pos = torch.stack(target_frame_offset_pos).repeat(
                self._num_envs, 1
            )
            self._target_frame_offset_quat = torch.stack(target_frame_offset_quat).repeat(
                self._num_envs, 1
            )

        self._data.target_frame_names = self._target_frame_names
        self._data.source_pos_w = torch.zeros(self._num_envs, 3, device=self._device)
        self._data.source_quat_w = torch.zeros(self._num_envs, 4, device=self._device)
        self._data.target_pos_w = torch.zeros(
            self._num_envs, len(duplicate_frame_indices), 3, device=self._device
        )
        self._data.target_quat_w = torch.zeros(
            self._num_envs, len(duplicate_frame_indices), 4, device=self._device
        )
        self._data.target_pos_source = torch.zeros_like(self._data.target_pos_w)
        self._data.target_quat_source = torch.zeros_like(self._data.target_quat_w)


class DoorPregrasp(
    StagedTaskBase,
    DeltaActionBase,
    WarpedActionBase,
    A2Base,
    FingerPrimitiveBase,
    ResetFromDataset,
):
    STAGE_WALK_TO_DOOR = 0
    STAGE_PREGRASP = 1
    STAGE_GRASP = 2
    STAGE_OPEN = 3
    STAGE_SWING = 4
    STAGE_THROUGH = 5
    A2_GRIPPER_HANDLE_FRAME_TRANSFORMER = "piper_gripper_handle_frame_transformer"
    A2_GRIPPER_HANDLE_CONTACT_SENSOR = "a2_gripper_handle_contact_sensor"

    def __init__(self, config, device):
        self._use_a2_base = bool(config.get("a2_base", {}).get("enabled", False))
        super().__init__(config, device)

        if self._use_a2_base:
            if self._reset_from_dataset_enabled():
                self._init_reset_from_dataset(config, device)
            self._init_a2_door_pregrasp_state()
            return

        # finger primitive related
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
        self._left_hand_dof_idx = [
            self.dof_names.index(name)
            for name in self.config.robot.finger_primitive.primitive_action_map.left.dof_names
        ]
        self._right_hand_dof_idx = [
            self.dof_names.index(name)
            for name in self.config.robot.finger_primitive.primitive_action_map.right.dof_names
        ]
        self._upper_non_finger_dof_idx = [
            i
            for i in self.upper_dof_indices
            if i not in self._left_hand_dof_idx and i not in self._right_hand_dof_idx
        ]
        self._upper_non_gripper_dof_idx = list(self._upper_non_finger_dof_idx)

        # read the door metadata
        stage: Usd.Stage = omni.usd.get_context().get_stage()
        self.door_width = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_height = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_handle_height = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self.door_handle_width = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_weight = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_open_lr = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_open_io = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)

        for env_id in range(self.num_envs):
            door_prim_path = f"/World/envs/env_{env_id}/door"
            door_prim = stage.GetPrimAtPath(door_prim_path)
            door_metadata = door_prim.GetPrim().GetMetadata("customData")
            self.door_width[env_id] = door_metadata["doorWidth"]
            self.door_height[env_id] = door_metadata["doorHeight"]
            self.door_handle_height[env_id] = door_metadata["doorHandleHeight"]
            self.door_handle_width[env_id] = door_metadata["doorHandleWidth"]
            self.door_weight[env_id] = door_metadata["doorWeight"]
            self.door_open_lr[env_id] = door_metadata["doorOpenLR"]

        # body indices
        self.left_palm_idx = self.simulator.body_names.index("left_hand_palm_link")
        self.right_palm_idx = self.simulator.body_names.index("right_hand_palm_link")
        self.root_idx = self.simulator.body_names.index("pelvis")
        self.left_hand_indices = [
            self.simulator.body_names.index(link)
            for link in self.simulator.robot_config.left_hand_body_names
        ]
        self.right_hand_indices = [
            self.simulator.body_names.index(link)
            for link in self.simulator.robot_config.right_hand_body_names
        ]
        g1_hand_links = [
            n
            for n in self.simulator.robot_config.body_names
            if ("left_hand" in n or "right_hand" in n)
        ]
        self.left_hand_indices_tgt_ct_sensor = [
            g1_hand_links.index(link) for link in g1_hand_links if "left_hand" in link
        ]
        self.left_hand_indices_convert = [
            self.left_hand_indices.index(self.simulator.body_names.index(g1_hand_links[i]))
            for i in self.left_hand_indices_tgt_ct_sensor
        ]
        self.right_hand_indices_tgt_ct_sensor = [
            g1_hand_links.index(link) for link in g1_hand_links if "right_hand" in link
        ]
        self.right_hand_indices_convert = [
            self.right_hand_indices.index(self.simulator.body_names.index(g1_hand_links[i]))
            for i in self.right_hand_indices_tgt_ct_sensor
        ]

        self.left_hand_palm_side_direction = self._parse_palm_side_direction(
            self.simulator.robot_config.left_hand_palm_side_direction
        )
        self.right_hand_palm_side_direction = self._parse_palm_side_direction(
            self.simulator.robot_config.right_hand_palm_side_direction
        )

        # dof indices
        finger_dof_names = [dof for dof in self.simulator.dof_names if "hand" in dof]
        self.finger_dof_idx = torch.tensor(
            [self.simulator.dof_names.index(dof) for dof in finger_dof_names],
            dtype=torch.long,
            device=self.device,
        )
        self.non_finger_dof_idx = [
            self.simulator.dof_names.index(dof)
            for dof in self.simulator.dof_names
            if dof not in finger_dof_names
        ]
        self.wrist_dof_idx = torch.tensor(
            [
                self.simulator.dof_names.index(dof)
                for dof in self.simulator.dof_names
                if "wrist" in dof
            ],
            dtype=torch.long,
            device=self.device,
        )
        self.dof_pos_humanly_lower_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_humanly_lower_limit_list, device=self.device
        )[None, :]
        self.dof_pos_humanly_upper_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_humanly_upper_limit_list, device=self.device
        )[None, :]

        self._left_arm_dof_idx = torch.tensor(self.left_arm_dof_indices, device=self.device)
        self._right_arm_dof_idx = torch.tensor(self.right_arm_dof_indices, device=self.device)

        self._register_task_state_to_track(self.simulator.scene.articulations["door"], "door")
        self._register_buffer_to_track(
            "delta_actions",
            self._get_delta_actions_buffer_shape(),
            self._store_delta_actions_buffer,
            self._load_delta_actions_buffer,
            dtype=torch.float32,
        )

        self.resting_dof_pos = torch.tensor([self.config.resting_dof_pos], device=self.device)

        self.target_root_pos = torch.tensor(self.config.target_root_pos, device=self.device)[
            None, :
        ]

    def _init_door_metadata(self):
        stage: Usd.Stage = omni.usd.get_context().get_stage()
        self.door_width = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_height = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_handle_height = torch.zeros(
            self.num_envs, dtype=torch.float32, device=self.device
        )
        self.door_handle_width = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_weight = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_open_lr = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)
        self.door_open_io = torch.zeros(self.num_envs, dtype=torch.float32, device=self.device)

        for env_id in range(self.num_envs):
            door_prim_path = f"/World/envs/env_{env_id}/door"
            door_prim = stage.GetPrimAtPath(door_prim_path)
            door_metadata = door_prim.GetPrim().GetMetadata("customData")
            self.door_width[env_id] = door_metadata["doorWidth"]
            self.door_height[env_id] = door_metadata["doorHeight"]
            self.door_handle_height[env_id] = door_metadata["doorHandleHeight"]
            self.door_handle_width[env_id] = door_metadata["doorHandleWidth"]
            self.door_weight[env_id] = door_metadata["doorWeight"]
            self.door_open_lr[env_id] = door_metadata["doorOpenLR"]

    def _init_a2_door_pregrasp_state(self):
        self._init_door_metadata()
        self.root_idx = self.simulator.body_names.index(self.config.robot.torso_name)
        a2_gripper_body_names = ("arm_body7", "arm_body8")
        missing_gripper_bodies = [
            body_name
            for body_name in a2_gripper_body_names
            if body_name not in self.simulator.body_names
        ]
        if missing_gripper_bodies:
            raise RuntimeError(
                "A2 hand_force requires gripper contact bodies "
                f"{a2_gripper_body_names}, missing {missing_gripper_bodies}"
            )
        self._a2_gripper_force_body_indices = [
            self.simulator.body_names.index(body_name) for body_name in a2_gripper_body_names
        ]
        self._upper_non_finger_dof_idx = list(self.upper_dof_indices)
        gripper_dof_indices = set(self._a2_gripper_dof_indices.tolist())
        self._upper_non_gripper_dof_idx = [
            int(dof_idx)
            for dof_idx in self.upper_dof_indices
            if int(dof_idx) not in gripper_dof_indices
        ]
        self._left_arm_dof_idx = torch.tensor(self.arm_dof_indices[:6], device=self.device)
        self._right_arm_dof_idx = torch.tensor(self.arm_dof_indices[:6], device=self.device)
        self.finger_dof_idx = torch.empty(0, dtype=torch.long, device=self.device)
        self.wrist_dof_idx = torch.empty(0, dtype=torch.long, device=self.device)
        self.left_hand_indices = []
        self.right_hand_indices = []
        self.left_hand_indices_tgt_ct_sensor = []
        self.right_hand_indices_tgt_ct_sensor = []
        self.left_hand_indices_convert = []
        self.right_hand_indices_convert = []
        self.left_palm_idx = self.end_effector_index
        self.right_palm_idx = self.end_effector_index
        self.left_hand_palm_side_direction = torch.tensor(
            [1.0, 0.0, 0.0, 0.0], device=self.device
        )
        self.right_hand_palm_side_direction = torch.tensor(
            [1.0, 0.0, 0.0, 0.0], device=self.device
        )
        self.dof_pos_humanly_lower_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_lower_limit_list, device=self.device
        )[None, :]
        self.dof_pos_humanly_upper_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_upper_limit_list, device=self.device
        )[None, :]

        self._register_task_state_to_track(self.simulator.scene.articulations["door"], "door")
        self._register_buffer_to_track(
            "delta_actions",
            self._get_delta_actions_buffer_shape(),
            self._store_delta_actions_buffer,
            self._load_delta_actions_buffer,
            dtype=torch.float32,
        )

        self.resting_dof_pos = torch.tensor([self.config.resting_dof_pos], device=self.device)
        self.target_root_pos = torch.tensor(self.config.target_root_pos, device=self.device)[
            None, :
        ]

    def _init_buffers(self):
        super()._init_buffers()
        self.relative_door_pos_buf = torch.zeros(
            self.num_envs, 3, device=self.device, requires_grad=False
        )
        self.relative_door_rot_buf = torch.zeros(
            self.num_envs, 4, device=self.device, requires_grad=False
        )

        # door state buffer
        self.door_root_state_buf = torch.zeros(
            self.num_envs, 13, device=self.device, requires_grad=False
        )
        self.door_root_state_buf[:, 3] = 1.0  # w
        self.door_dof_state_buf = torch.zeros(
            self.num_envs, 3, device=self.device, requires_grad=False
        )
        self.door_root_state_buf[:, :3] += self.env_origins

    def _pre_compute_observations_callback(self, env_ids=None):
        super()._pre_compute_observations_callback(env_ids)
        env_ids = torch.arange(self.num_envs, device=self.device) if env_ids is None else env_ids

        current_root_pos = self.simulator.robot_root_states[env_ids, :3].clone()
        current_root_rot = self.simulator.robot_root_states[env_ids, 3:7].clone()
        current_root_rot_wxyz = xyzw_to_wxyz(current_root_rot)

        door_root_pos = self.simulator.get_task_root_state("door")[env_ids, :3].clone()
        door_root_pos[:, 2] = current_root_pos[:, 2]
        door_root_rot_wxyz = self.simulator.get_task_root_state("door")[env_ids, 3:7].clone()

        relative_door_pos, relative_door_rot = subtract_frame_transforms(
            current_root_pos, current_root_rot_wxyz, door_root_pos, door_root_rot_wxyz
        )
        self.relative_door_pos_buf[env_ids] = relative_door_pos
        self.relative_door_rot_buf[env_ids] = wxyz_to_xyzw(relative_door_rot)

    @StagedTaskBase.effective_in_stage(STAGE_WALK_TO_DOOR)
    def _reward_walk_to_door(self):
        # A2 stage0 pass: keep the G1 Doorman door-root velocity shaping for the first
        # reward smoke. Future option: parameterize this target as door_root,
        # grasp_target, or a Piper-specific approach_anchor.
        current_root_pos = self.simulator.robot_root_states[:, :3].clone()
        door_root_pos = self.simulator.get_task_root_state("door")[:, :3].clone()
        door_root_pos[:, 2] = current_root_pos[:, 2]
        door_direction = door_root_pos - current_root_pos
        target_dir = F.normalize(door_direction, dim=-1)
        current_root_vel = self.simulator.robot_root_states[:, 7:10].clone()

        target_vel = self.config.get("target_root_vel", 0.3) * target_dir

        return self._tracking_reward_util(
            torch.linalg.norm(current_root_vel - target_vel, dim=-1),
            std=0.15,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

    @StagedTaskBase.effective_in_stage([STAGE_WALK_TO_DOOR, STAGE_THROUGH])
    def _reward_penalty_upper_body_non_gripper_deviation_l1(self):
        """A2 stage0 PASS: replace G1 non-finger penalty with Piper arm_j1..j6 shaping."""
        # Exclude arm_j7/arm_j8 so gripper open/close does not affect arm pose shaping.
        return torch.abs(
            self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx]
            - self.resting_dof_pos[:, self._upper_non_gripper_dof_idx]
        ).sum(dim=-1)

    @StagedTaskBase.effective_in_stage([STAGE_WALK_TO_DOOR, STAGE_PREGRASP, STAGE_GRASP, STAGE_THROUGH])
    def _reward_pregrasp_gripper_dof_pos_l1(self):
        """A2 gripper shaping: stage0 tracks close target (gripper stowed while
        walking); stage1 and stage2-gate-outside track open target (gripper opens
        to prepare grasp and stays open until close to handle); stage2 gate inside
        is excluded so a2_stage2_close_* rewards take over.
        """
        gripper_pos = self.simulator.dof_pos[:, self._a2_gripper_dof_indices]
        gripper_vel = self.simulator.dof_vel[:, self._a2_gripper_dof_indices]
        is_walk = self.stage_buf == self.STAGE_WALK_TO_DOOR
        # In stage2, only track open target when outside the close-reward gate
        # (i.e. gripper not yet close enough to handle). Inside the gate, return
        # zero so a2_stage2_close_command / a2_stage2_close_progress drive close.
        if self._use_a2_base:
            stage2_gate = self._get_a2_stage2_close_reward_gate()
            track_open = (~is_walk) & (~stage2_gate)
            target = torch.where(
                is_walk[:, None],
                self._a2_gripper_close_target,
                self._a2_gripper_open_target,
            )
            gate_mask = track_open.float()
        else:
            target = torch.where(
                is_walk[:, None],
                self._a2_gripper_close_target,
                self._a2_gripper_open_target,
            )
            gate_mask = (~is_walk).float()
        span = (self._a2_gripper_open_target - self._a2_gripper_close_target).abs().clamp_min(1.0e-4)
        pos_track = self._tracking_reward_util(
            (gripper_pos - target) / span[None, :],
            std=0.25,
            target=0.0,
            scale=1.0,
            offset=0.0,
        ).mean(dim=-1)
        vel_track = self._tracking_reward_util(
            gripper_vel / span[None, :],
            std=0.5,
            target=0.0,
            scale=1.0,
            offset=0.0,
        ).mean(dim=-1)
        return ((pos_track + 0.2 * vel_track).clamp(max=1.0)) * gate_mask

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_penalty_unused_dof_deviation_l1(self):
        """Penalize the deviation of the unused arm dof during door opening"""
        left_diff = (
            self.simulator.dof_pos[:, self._left_arm_dof_idx]
            - self.resting_dof_pos[:, self._left_arm_dof_idx]
        )
        right_diff = (
            self.simulator.dof_pos[:, self._right_arm_dof_idx]
            - self.resting_dof_pos[:, self._right_arm_dof_idx]
        )
        return torch.where(self.door_open_lr[:, None] < 0, right_diff, left_diff).abs().sum(dim=-1)

    def _get_a2_gripper_handle_orientation_metrics(self):
        if not self._use_a2_base:
            raise RuntimeError("gripper_handle_orientation is only defined for A2 Piper configs.")

        data = self._get_a2_gripper_handle_frame_transformer().data
        target_quat_source = getattr(data, "target_quat_source", None)
        if (
            target_quat_source is None
            or target_quat_source.ndim != 3
            or target_quat_source.shape[0] != self.num_envs
            or target_quat_source.shape[1] != 2
            or target_quat_source.shape[2] != 4
        ):
            shape = None if target_quat_source is None else tuple(target_quat_source.shape)
            raise RuntimeError(
                "A2 gripper_handle_orientation requires target_quat_source shape "
                f"({self.num_envs}, 2, 4); got {shape}."
            )

        q_target_source = target_quat_source[:, 1, :]
        source_y = q_target_source.new_tensor((0.0, 1.0, 0.0)).expand(self.num_envs, -1)
        source_z = q_target_source.new_tensor((0.0, 0.0, 1.0)).expand(self.num_envs, -1)

        target_y_source = quat_apply(q_target_source, source_y)
        target_z_source = quat_apply(q_target_source, source_z)
        opening_alignment = torch.abs(torch.sum(source_y * target_y_source, dim=-1)).clamp(
            0.0, 1.0
        )
        approach_alignment = torch.sum(source_z * target_z_source, dim=-1).clamp(-1.0, 1.0)
        return opening_alignment, approach_alignment

    def _get_a2_stage2_close_reward_gate(self):
        if not self._use_a2_base:
            raise RuntimeError("A2 stage2 close rewards are only defined for A2 Piper configs.")

        stage_buf = getattr(self, "stage_buf", None)
        if (
            stage_buf is None
            or not torch.is_tensor(stage_buf)
            or tuple(stage_buf.shape) != (self.num_envs,)
        ):
            shape = None if stage_buf is None else tuple(stage_buf.shape)
            raise RuntimeError(
                "A2 stage2 close rewards require stage_buf shape "
                f"({self.num_envs},); got {shape}."
            )

        data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = getattr(data, "target_pos_source", None)
        if (
            target_pos_source is None
            or target_pos_source.ndim != 3
            or tuple(target_pos_source.shape) != (self.num_envs, 2, 3)
        ):
            shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            raise RuntimeError(
                "A2 stage2 close rewards require target_pos_source shape "
                f"({self.num_envs}, 2, 3); got {shape}."
            )

        handle_distance = torch.linalg.norm(target_pos_source[:, 0, :], dim=-1)
        opening_alignment, approach_alignment = self._get_a2_gripper_handle_orientation_metrics()
        return (
            (stage_buf == self.STAGE_GRASP)
            & (handle_distance < 0.015)
            & (opening_alignment >= 0.9)
            & (approach_alignment >= 0.9)
        )

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_gripper_handle_orientation(self):
        opening_alignment, approach_alignment = self._get_a2_gripper_handle_orientation_metrics()
        opening_track = self._tracking_reward_util(
            1.0 - opening_alignment, std=0.25, target=0.0, scale=1.0, offset=0.0
        )
        approach_track = self._tracking_reward_util(
            1.0 - approach_alignment, std=0.25, target=0.0, scale=1.0, offset=0.0
        )
        return (opening_track * approach_track).clamp(0.0, 1.0)

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_hand_handle_orientation(self):
        if self._use_a2_base:
            raise RuntimeError(
                "A2 configs must use 'gripper_handle_orientation' instead of legacy "
                "'hand_handle_orientation'."
            )
        mask = (self.door_open_lr < 0)[:, None]
        rot_90 = quat_from_euler_xyz(
            torch.full((self.num_envs,), torch.pi / 2.0, device=self.device),
            torch.zeros(self.num_envs, device=self.device),
            torch.zeros(self.num_envs, device=self.device),
        )
        rot_neg_90 = quat_from_euler_xyz(
            torch.full((self.num_envs,), -torch.pi / 2.0, device=self.device),
            torch.zeros(self.num_envs, device=self.device),
            torch.zeros(self.num_envs, device=self.device),
        )
        left_target_rot = self.simulator.left_hand_transform_rot[:, 0, :]
        right_target_rot = self.simulator.right_hand_transform_rot[:, 0, :]
        current_hand_rot = torch.where(mask, left_target_rot, right_target_rot)
        relative_rot = quat_mul(current_hand_rot, torch.where(mask, rot_90, rot_neg_90))
        return self._tracking_reward_util(
            wrap_to_pi(axis_angle_from_quat(relative_rot).norm(dim=-1)),
            std=0.6,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN])
    def _reward_standing_still(self):
        norm = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1)
        return self._tracking_reward_util(norm, std=0.05, target=0.0, scale=1.0, offset=0.0)

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN])
    def _reward_penalty_not_standing_still(self):
        norm = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1)
        return norm

    @StagedTaskBase.effective_in_stage(STAGE_SWING)
    def _reward_penalty_standing_still(self):
        norm = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1)
        return self._tracking_reward_util(norm, std=0.05, target=0.0, scale=1.0, offset=0.0)

    @StagedTaskBase.effective_in_stage(STAGE_PREGRASP)
    def _reward_pregrasp_target_distance(self):
        if self._use_a2_base:
            data = self._get_a2_gripper_handle_frame_transformer().data

            target_pos_source = getattr(data, "target_pos_source", None)
            if (
                target_pos_source is None
                or target_pos_source.ndim != 3
                or target_pos_source.shape != (self.num_envs, 2, 3)
            ):
                shape = None if target_pos_source is None else tuple(target_pos_source.shape)
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires target_pos_source shape "
                    f"({self.num_envs}, 2, 3); got {shape}."
                )

            target_pos_w = getattr(data, "target_pos_w", None)
            if (
                target_pos_w is None
                or target_pos_w.ndim != 3
                or target_pos_w.shape != (self.num_envs, 2, 3)
            ):
                shape = None if target_pos_w is None else tuple(target_pos_w.shape)
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires target_pos_w shape "
                    f"({self.num_envs}, 2, 3); got {shape}."
                )

            source_pos_w = getattr(data, "source_pos_w", None)
            if (
                source_pos_w is None
                or source_pos_w.ndim != 2
                or source_pos_w.shape != (self.num_envs, 3)
            ):
                shape = None if source_pos_w is None else tuple(source_pos_w.shape)
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires source_pos_w shape "
                    f"({self.num_envs}, 3); got {shape}."
                )

            rigid_body_vel = getattr(self.simulator, "_rigid_body_vel", None)
            if (
                rigid_body_vel is None
                or rigid_body_vel.ndim != 3
                or rigid_body_vel.shape[0] != self.num_envs
                or rigid_body_vel.shape[1] <= self.end_effector_index
                or rigid_body_vel.shape[2] < 3
            ):
                shape = None if rigid_body_vel is None else tuple(rigid_body_vel.shape)
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires simulator._rigid_body_vel "
                    f"with shape ({self.num_envs}, >{self.end_effector_index}, >=3); "
                    f"got {shape}."
                )

            if "pregrasp_target_vel" not in self.config:
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires config key 'pregrasp_target_vel'."
                )
            pregrasp_target_vel = float(self.config.pregrasp_target_vel)
            if pregrasp_target_vel <= 0.0:
                raise RuntimeError(
                    "A2 pregrasp_target_distance requires positive pregrasp_target_vel; "
                    f"got {pregrasp_target_vel}."
                )

            pregrasp_pos_source = target_pos_source[:, 1, :]
            distance = torch.linalg.norm(pregrasp_pos_source, dim=-1)
            pos_reward = self._tracking_reward_util(
                distance,
                std=0.2,
                target=0.0,
                scale=1.0,
                offset=0.0,
            )

            direction = F.normalize(target_pos_w[:, 1, :] - source_pos_w, dim=-1)
            current_vel = rigid_body_vel[:, self.end_effector_index, :3]
            target_vel = pregrasp_target_vel * direction
            vel_reward = self._tracking_reward_util(
                torch.linalg.norm(current_vel - target_vel, dim=-1),
                std=0.15,
                target=0.0,
                scale=1.0,
                offset=0.0,
            )
            return (pos_reward + vel_reward).clamp(max=1.0)
        pre_grasp_target = self._compute_pre_grasp_target()

        left_hand_pos = self.simulator._rigid_body_pos[:, self.left_palm_idx, :]
        right_hand_pos = self.simulator._rigid_body_pos[:, self.right_palm_idx, :]

        left_hand_pos_to_pre_grasp_target = pre_grasp_target - left_hand_pos
        right_hand_pos_to_pre_grasp_target = pre_grasp_target - right_hand_pos

        left_hand_pos_to_pre_grasp_target_norm = torch.norm(
            left_hand_pos_to_pre_grasp_target, dim=-1
        )
        right_hand_pos_to_pre_grasp_target_norm = torch.norm(
            right_hand_pos_to_pre_grasp_target, dim=-1
        )

        pos_reward = self._tracking_reward_util(
            torch.where(
                self.door_open_lr < 0,
                left_hand_pos_to_pre_grasp_target_norm,
                right_hand_pos_to_pre_grasp_target_norm,
            ),
            std=0.2,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

        left_current_direction = F.normalize(pre_grasp_target - left_hand_pos, dim=-1)
        right_current_direction = F.normalize(pre_grasp_target - right_hand_pos, dim=-1)

        left_palm_vel = self.simulator._rigid_body_vel[:, self.left_palm_idx, :]
        right_palm_vel = self.simulator._rigid_body_vel[:, self.right_palm_idx, :]

        pregrasp_target_vel = self.config.get("pregrasp_target_vel", 0.5)
        left_target_vel = pregrasp_target_vel * left_current_direction
        right_target_vel = pregrasp_target_vel * right_current_direction

        vel_reward = self._tracking_reward_util(
            torch.where(
                self.door_open_lr < 0,
                torch.linalg.norm(left_palm_vel - left_target_vel, dim=-1),
                torch.linalg.norm(right_palm_vel - right_target_vel, dim=-1),
            ),
            std=0.15,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )
        return (pos_reward + vel_reward).clamp(max=1.0)

    @StagedTaskBase.effective_in_stage([STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_grasp_finger_dof_pos_l1(self):
        if self._use_a2_base:
            return torch.zeros(self.num_envs, device=self.device)
        left_diff = self.simulator.dof_pos[:, self._left_hand_dof_idx] - self._left_p1
        right_diff = self.simulator.dof_pos[:, self._right_hand_dof_idx] - self._right_p1
        left_vel = self.simulator.dof_vel[:, self._left_hand_dof_idx] * torch.sign(left_diff)
        right_vel = self.simulator.dof_vel[:, self._right_hand_dof_idx] * torch.sign(right_diff)

        pos_diff = torch.where(self.door_open_lr[:, None] < 0, left_diff, right_diff)
        pos_track = self._tracking_reward_util(
            pos_diff, std=0.3, target=0.0, scale=1.0, offset=0.0
        ).mean(dim=-1)

        vel_diff = torch.where(self.door_open_lr[:, None] < 0, left_vel, right_vel)
        vel_track = self._tracking_reward_util(
            vel_diff, std=0.2, target=0.6, scale=1.0, offset=0.0
        ).mean(dim=-1)

        return (pos_track + vel_track).clamp(max=1.0)

    @StagedTaskBase.effective_in_stage([STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_grasp_target_distance(self):
        if self._use_a2_base:
            data = self._get_a2_gripper_handle_frame_transformer().data
            target_pos_source = getattr(data, "target_pos_source", None)
            if (
                target_pos_source is None
                or target_pos_source.ndim != 3
                or target_pos_source.shape != (self.num_envs, 2, 3)
            ):
                shape = None if target_pos_source is None else tuple(target_pos_source.shape)
                raise RuntimeError(
                    "A2 grasp_target_distance requires target_pos_source shape "
                    f"({self.num_envs}, 2, 3); got {shape}."
                )

            handle_pos_source = target_pos_source[:, 0, :]
            distance = torch.linalg.norm(handle_pos_source, dim=-1)
            return self._tracking_reward_util(
                distance,
                std=0.1,
                target=0.0,
                scale=1.0,
                offset=0.0,
            )
        grasp_target = self._compute_grasp_target()

        left_hand_pos = self.simulator._rigid_body_pos[:, self.left_palm_idx, :]
        right_hand_pos = self.simulator._rigid_body_pos[:, self.right_palm_idx, :]

        left_hand_pos_to_grasp_target = grasp_target - left_hand_pos
        right_hand_pos_to_grasp_target = grasp_target - right_hand_pos

        left_hand_pos_to_grasp_target_norm = torch.norm(left_hand_pos_to_grasp_target, dim=-1)
        right_hand_pos_to_grasp_target_norm = torch.norm(right_hand_pos_to_grasp_target, dim=-1)

        return self._tracking_reward_util(
            torch.where(
                self.door_open_lr < 0,
                left_hand_pos_to_grasp_target_norm,
                right_hand_pos_to_grasp_target_norm,
            ),
            std=0.1,
            target=0.0,
            scale=1.0,
            offset=0.0,
        )

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_close_command(self):
        if not self._use_a2_base:
            raise RuntimeError("a2_stage2_close_command is only defined for A2 Piper configs.")

        gripper_primitive_raw = getattr(self, "_a2_gripper_primitive_raw", None)
        if (
            gripper_primitive_raw is None
            or not torch.is_tensor(gripper_primitive_raw)
            or tuple(gripper_primitive_raw.shape) != (self.num_envs, 1)
        ):
            shape = (
                None
                if gripper_primitive_raw is None
                else tuple(gripper_primitive_raw.shape)
            )
            raise RuntimeError(
                "a2_stage2_close_command requires _a2_gripper_primitive_raw shape "
                f"({self.num_envs}, 1); got {shape}."
            )

        gate = self._get_a2_stage2_close_reward_gate()
        primitive = gripper_primitive_raw.squeeze(-1)
        reward = ((-primitive - 0.2) / 0.8).clamp(0.0, 1.0)
        return reward * gate.float()

    @StagedTaskBase.effective_in_stage(STAGE_GRASP)
    def _reward_a2_stage2_close_progress(self):
        if not self._use_a2_base:
            raise RuntimeError("a2_stage2_close_progress is only defined for A2 Piper configs.")

        gripper_dof_indices = getattr(self, "_a2_gripper_dof_indices", None)
        if (
            gripper_dof_indices is None
            or not torch.is_tensor(gripper_dof_indices)
            or tuple(gripper_dof_indices.shape) != (2,)
        ):
            shape = None if gripper_dof_indices is None else tuple(gripper_dof_indices.shape)
            raise RuntimeError(
                "a2_stage2_close_progress requires _a2_gripper_dof_indices shape "
                f"(2,); got {shape}."
            )
        if gripper_dof_indices.dtype not in (torch.int32, torch.int64):
            raise RuntimeError(
                "a2_stage2_close_progress requires integer _a2_gripper_dof_indices; "
                f"got dtype={gripper_dof_indices.dtype}."
            )
        if torch.any(gripper_dof_indices < 0) or torch.unique(gripper_dof_indices).numel() != 2:
            raise RuntimeError(
                "a2_stage2_close_progress requires two distinct non-negative "
                f"gripper DOF indices; got {gripper_dof_indices.tolist()}."
            )

        open_target = getattr(self, "_a2_gripper_open_target", None)
        if (
            open_target is None
            or not torch.is_tensor(open_target)
            or tuple(open_target.shape) != (2,)
        ):
            shape = None if open_target is None else tuple(open_target.shape)
            raise RuntimeError(
                "a2_stage2_close_progress requires _a2_gripper_open_target shape "
                f"(2,); got {shape}."
            )

        close_target = getattr(self, "_a2_gripper_close_target", None)
        if (
            close_target is None
            or not torch.is_tensor(close_target)
            or tuple(close_target.shape) != (2,)
        ):
            shape = None if close_target is None else tuple(close_target.shape)
            raise RuntimeError(
                "a2_stage2_close_progress requires _a2_gripper_close_target shape "
                f"(2,); got {shape}."
            )

        span = (open_target - close_target).abs()
        if torch.any(span <= 1.0e-4):
            raise RuntimeError(
                "a2_stage2_close_progress requires non-zero gripper open/close span; "
                f"open_target={open_target.tolist()}, close_target={close_target.tolist()}."
            )

        dof_pos = getattr(self.simulator, "dof_pos", None)
        max_gripper_dof_index = int(gripper_dof_indices.max().item())
        if (
            dof_pos is None
            or not torch.is_tensor(dof_pos)
            or dof_pos.ndim != 2
            or dof_pos.shape[0] != self.num_envs
            or dof_pos.shape[1] <= max_gripper_dof_index
        ):
            shape = None if dof_pos is None else tuple(dof_pos.shape)
            raise RuntimeError(
                "a2_stage2_close_progress requires simulator.dof_pos shape "
                f"({self.num_envs}, >{max_gripper_dof_index}); got {shape}."
            )

        gate = self._get_a2_stage2_close_reward_gate()
        gripper_pos = dof_pos[:, gripper_dof_indices]
        progress = (open_target[None, :] - gripper_pos).abs() / span[None, :]
        reward = (progress.mean(dim=-1) / 0.6).clamp(0.0, 1.0)
        return reward * gate.float()

    @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
    def _reward_grasp(self):
        if self._use_a2_base:
            forces_w = self._get_a2_gripper_handle_contact_forces()
            data = self._get_a2_gripper_handle_frame_transformer().data
            source_quat_w = getattr(data, "source_quat_w", None)
            if (
                source_quat_w is None
                or source_quat_w.ndim != 2
                or source_quat_w.shape != (self.num_envs, 4)
            ):
                shape = None if source_quat_w is None else tuple(source_quat_w.shape)
                raise RuntimeError(
                    "A2 grasp reward requires source_quat_w shape "
                    f"({self.num_envs}, 4); got {shape}."
                )

            source_quat = source_quat_w[:, None, :].expand(-1, 2, -1).reshape(-1, 4)
            forces_source = quat_apply(
                quat_inv(source_quat), forces_w.reshape(-1, 3)
            ).reshape(self.num_envs, 2, 3)

            axis_force = torch.abs(forces_source[:, :, 1])
            off_axis_force = torch.abs(forces_source[:, :, 0]) + torch.abs(
                forces_source[:, :, 2]
            )
            per_body = (axis_force - off_axis_force).clamp(min=-10.0, max=10.0)
            raw_reward = per_body.min(dim=-1).values

            pregrasp_mask = self.stage_buf == DoorPregrasp.STAGE_PREGRASP
            contact_mag = torch.linalg.norm(forces_w, dim=-1).sum(dim=-1).clamp(max=10.0)
            raw_reward[pregrasp_mask] = -contact_mag[pregrasp_mask]
            return raw_reward
        left_contact_forces = self.simulator.object_to_hand_contact_forces[
            :, 0, self.left_hand_indices_tgt_ct_sensor, :
        ][:, self.left_hand_indices_convert, :]
        left_contact_forces_flattened = left_contact_forces.reshape(-1, 3)
        left_hand_rot = self.simulator._rigid_body_rot[:, self.left_hand_indices, :][
            :, :, [3, 0, 1, 2]
        ]  # flip xyzw to wxyz
        left_hand_rot_flattened = left_hand_rot.reshape(-1, 4)
        left_palm_side_repeat = torch.tile(
            self.left_hand_palm_side_direction, (left_contact_forces.shape[0], 1)
        )
        # rotate contact forces first to hand body frames, and then to palm-facing frames
        left_contact_forces_hand_frame = quat_apply(
            quat_inv(left_hand_rot_flattened), left_contact_forces_flattened
        )
        left_contact_forces_palm_frame = quat_apply(
            quat_inv(left_palm_side_repeat), left_contact_forces_hand_frame
        )

        right_contact_forces = self.simulator.object_to_hand_contact_forces[
            :, 0, self.right_hand_indices_tgt_ct_sensor, :
        ][:, self.right_hand_indices_convert, :]
        right_contact_forces_flattened = right_contact_forces.reshape(-1, 3)
        right_hand_rot = self.simulator._rigid_body_rot[:, self.right_hand_indices, :][
            :, :, [3, 0, 1, 2]
        ]  # flip xyzw to wxyz
        right_hand_rot_flattened = right_hand_rot.reshape(-1, 4)
        right_palm_side_repeat = torch.tile(
            self.right_hand_palm_side_direction, (right_contact_forces.shape[0], 1)
        )
        # rotate contact forces first to hand body frames, and then to palm-facing frames
        right_contact_forces_hand_frame = quat_apply(
            quat_inv(right_hand_rot_flattened), right_contact_forces_flattened
        )
        right_contact_forces_palm_frame = quat_apply(
            quat_inv(right_palm_side_repeat), right_contact_forces_hand_frame
        )

        # reward forces acting out of the palm (x) direction. penalize forces on other directions.
        left_reward = (
            (
                -1.0 * torch.abs(left_contact_forces_palm_frame[:, 1:]).sum(dim=-1)
                + left_contact_forces_palm_frame[:, 0]
            )
            .clamp(min=-10, max=10)
            .reshape(self.num_envs, -1)
            .mean(dim=-1)
        )
        right_reward = (
            (
                -1.0 * torch.abs(right_contact_forces_palm_frame[:, 1:]).sum(dim=-1)
                + right_contact_forces_palm_frame[:, 0]
            )
            .clamp(min=-10, max=10)
            .reshape(self.num_envs, -1)
            .mean(dim=-1)
        )
        reward = left_reward + right_reward

        reward[self.stage_buf == DoorPregrasp.STAGE_PREGRASP] = -1.0 * torch.abs(
            reward[self.stage_buf == DoorPregrasp.STAGE_PREGRASP]
        )

        return reward

    @StagedTaskBase.effective_in_stage(STAGE_OPEN)
    def _reward_push_door_force(self):
        if self._use_a2_base:
            return torch.zeros(self.num_envs, device=self.device)
        left_net_force = self.simulator.object_to_hand_contact_forces[
            :, 0, self.left_hand_indices_tgt_ct_sensor, :
        ].sum(dim=-2)
        right_net_force = self.simulator.object_to_hand_contact_forces[
            :, 0, self.right_hand_indices_tgt_ct_sensor, :
        ].sum(dim=-2)
        # reward -x direction force (pushing the door)
        return (
            torch.where(self.door_open_lr < 0, left_net_force[:, 0], right_net_force[:, 0])
        ).clamp(min=0.0, max=20.0)

    @StagedTaskBase.effective_in_stage(STAGE_OPEN)
    def _reward_push_door_handle(self):
        handle_vel_reward = self.simulator.scene.articulations["door"].data.joint_vel[:, 1]
        handle_pos_reward = (
            self.simulator.scene.articulations["door"]
            .data.joint_pos[:, 1]
            .clamp(min=0.0, max=0.785398)
            / 0.785398
        )
        return (handle_vel_reward + handle_pos_reward).clamp(max=1.0, min=-1.0)

    @StagedTaskBase.effective_in_stage([STAGE_SWING, STAGE_THROUGH])
    def _reward_dont_push_door_handle(self):
        handle_vel_reward = -1.0 * self.simulator.scene.articulations["door"].data.joint_vel[:, 1]
        handle_pos_reward = (
            0.785398 - self.simulator.scene.articulations["door"].data.joint_pos[:, 1]
        ).clamp(min=0.0, max=0.785398) / 0.785398
        return (handle_vel_reward + handle_pos_reward).clamp(max=1.0, min=-1.0)

    @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
    def _reward_push_door_hinge(self):
        hinge_vel_reward = self.simulator.scene.articulations["door"].data.joint_vel[:, 0] * 10
        hinge_pos_reward = (
            self.simulator.scene.articulations["door"]
            .data.joint_pos[:, 0]
            .clamp(min=0.0, max=1.5708)
            / 1.5708
        )
        return (hinge_vel_reward + hinge_pos_reward).clamp(max=1.0, min=-1.0)

    @StagedTaskBase.effective_in_stage([STAGE_SWING, STAGE_THROUGH])
    def _reward_target_root_distance(self):
        target_direction = F.normalize(
            self.target_root_pos - (self.simulator.robot_root_states[:, :3] - self.env_origins),
            dim=-1,
        )
        root_vel = self.simulator._rigid_body_vel[:, self.root_idx, :]
        root_vel_along_target_direction = torch.sum(root_vel * target_direction, dim=-1)
        root_vel_target = self.config.get("target_root_vel", 0.3)
        root_vel_reward = self._tracking_reward_util(
            root_vel_along_target_direction, std=0.2, target=root_vel_target, scale=1.0, offset=0.0
        )

        root_pos_diff = torch.norm(
            self.simulator.robot_root_states[:, :3] - self.env_origins - self.target_root_pos,
            dim=-1,
        )
        root_pos_reward = self._tracking_reward_util(
            root_pos_diff, std=0.2, target=0.0, scale=1.0, offset=0.0
        )
        reward = (root_vel_reward + root_pos_reward).clamp(max=1.0)
        reward[self.stage_buf == DoorPregrasp.STAGE_SWING] *= 0.5
        return reward

    @override
    def _reward_limits_dof_pos(self):
        # A2 global PASS: use A2 arm body DOF / Piper arm_j1..j6 safety,
        # excluding arm_j7/arm_j8 gripper DOFs.
        # Penalize dof positions too close to the limit
        if self.use_reward_limits_dof_pos_curriculum:
            m = (
                self.simulator.hard_dof_pos_limits[:, 0] + self.simulator.hard_dof_pos_limits[:, 1]
            ) / 2
            r = self.simulator.hard_dof_pos_limits[:, 1] - self.simulator.hard_dof_pos_limits[:, 0]
            lower_soft_limit = m - 0.5 * r * self.soft_dof_pos_curriculum_value
            upper_soft_limit = m + 0.5 * r * self.soft_dof_pos_curriculum_value
        else:
            lower_soft_limit = self.simulator.dof_pos_limits[:, 0]
            upper_soft_limit = self.simulator.dof_pos_limits[:, 1]
        out_of_limits = -(self.simulator.dof_pos - lower_soft_limit).clip(max=0.0)  # lower limit
        out_of_limits += (self.simulator.dof_pos - upper_soft_limit).clip(min=0.0)
        return torch.sum(out_of_limits[:, self._upper_non_gripper_dof_idx], dim=1)

    def _reward_penalty_humanly_dof_limit(self):
        # A2 reward YAML no longer enables this G1 humanoid-specific posture limit;
        # A2 replaces it with the positive LMP-style ref_dof_legs prior.
        lower_limit_violations = -1.0 * (
            self.simulator.dof_pos - self.dof_pos_humanly_lower_limit
        ).clip(max=0.0).sum(dim=-1)
        upper_limit_violations = (
            (self.simulator.dof_pos - self.dof_pos_humanly_upper_limit).clip(min=0.0).sum(dim=-1)
        )
        return lower_limit_violations + upper_limit_violations

    def _reward_penalty_door_frame_contact(self):
        # A2 global PASS: A2 scene callback creates the same door frame contact sensor
        # before the A2 branch returns, so the G1 door-contact penalty is reusable.
        door_frame_unwanted_contact_forces = self.simulator.scene.sensors[
            "door_frame_unwanted_contact_sensor"
        ].data.net_forces_w
        return door_frame_unwanted_contact_forces.norm(dim=-1).sum(dim=-1)

    def _reward_penalty_door_panel_contact(self):
        # A2 global PASS: A2 scene callback creates the same door panel contact sensor
        # before the A2 branch returns, so the G1 door-contact penalty is reusable.
        door_panel_unwanted_contact_forces = self.simulator.scene.sensors[
            "door_panel_unwanted_contact_sensor"
        ].data.net_forces_w
        return door_panel_unwanted_contact_forces.norm(dim=-1).sum(dim=-1)

    def _reward_penalty_upper_body_dof_vel(self):
        return torch.sum(self.simulator.dof_vel[:, self._upper_non_finger_dof_idx] ** 2, dim=-1)

    @StagedTaskBase.effective_in_stage(
        [STAGE_WALK_TO_DOOR, STAGE_PREGRASP, STAGE_GRASP, STAGE_THROUGH]
    )
    def _reward_penalty_face_door(self):
        # A2 stage0 pass: keep the G1 Doorman full root-to-door orientation penalty
        # for the first reward smoke. Future option: switch to yaw-only heading
        # error or add a desired heading offset if A2 needs a non-square stance.
        return wrap_to_pi(
            axis_angle_from_quat(xyzw_to_wxyz(self.relative_door_rot_buf)).norm(dim=-1)
        )

    @StagedTaskBase.effective_in_stage([STAGE_WALK_TO_DOOR, STAGE_PREGRASP])
    def _reward_penalty_base_roll_pitch_l2(self):
        rpy = getattr(self, "rpy", None)
        if (
            rpy is None
            or not torch.is_tensor(rpy)
            or rpy.ndim != 2
            or rpy.shape[0] != self.num_envs
            or rpy.shape[1] < 2
        ):
            shape = None if rpy is None else tuple(rpy.shape)
            raise RuntimeError(
                "penalty_base_roll_pitch_l2 requires self.rpy shape "
                f"({self.num_envs}, >=2); got {shape}."
            )
        return torch.sum(torch.square(rpy[:, 0:2]), dim=-1)

    def _reward_penalty_upright(self):
        upright_vec = torch.repeat_interleave(
            torch.tensor([[0.0, 0.0, 1.0]], device=self.device), self.num_envs, dim=0
        )
        torso_quat_wxyz = xyzw_to_wxyz(self.simulator._rigid_body_rot[:, self.torso_index])
        rotated_vec = quat_apply(torso_quat_wxyz, upright_vec)
        return torch.sum(torch.square(rotated_vec - upright_vec), dim=-1)

    def _reward_orientation_control(self):
        # A2 global PASS: LMP-style body pitch/roll command tracking, reading the
        # physical base command buffer without advancing A2 observation history or gait phase.
        physical_base_command = self.get_physical_base_command()
        pitch_cmd = physical_base_command[:, 3]
        roll_cmd = physical_base_command[:, 4]
        desired_x = -torch.sin(pitch_cmd) * torch.cos(roll_cmd)
        desired_y = torch.sin(roll_cmd)
        desired_xy = torch.stack((desired_x, desired_y), dim=-1)
        actual_xy = self.projected_gravity[:, :2]
        return torch.sum(torch.square(actual_xy - desired_xy), dim=-1)

    @override
    def _reward_penalty_dof_acc(self):
        # A2 global PASS: use A2 arm body DOF / Piper arm_j1..j6 safety,
        # excluding arm_j7/arm_j8 gripper DOFs.
        return torch.sum(
            torch.square(self.simulator.dof_acc[:, self._upper_non_gripper_dof_idx]), dim=-1
        )

    @override
    def _reward_penalty_dof_vel(self):
        # A2 global PASS: use A2 arm body DOF / Piper arm_j1..j6 safety,
        # excluding arm_j7/arm_j8 gripper DOFs.
        return torch.sum(
            torch.square(self.simulator.dof_vel[:, self._upper_non_gripper_dof_idx]), dim=-1
        )

    @override
    def _reward_penalty_undesired_contact(self):
        # A2 global PASS: uses A2-specific penalize_contacts_on body set with
        # exact leg/base + non-gripper arm links, excluding gripper links.
        undesired_contact = torch.sum(
            torch.norm(self.simulator.contact_forces[:, self.penalised_contact_indices, :], dim=-1)
            > 1,
            dim=1,
            dtype=torch.float,
        )
        return undesired_contact

    def _reward_penalty_dof_overspeed(self):
        # A2 global PASS: use A2 arm body DOF / Piper arm_j1..j6 safety,
        # excluding arm_j7/arm_j8 gripper DOFs.
        return (
            torch.maximum(
                torch.abs(self.simulator.dof_vel[:, self._upper_non_gripper_dof_idx]) - 2.0,
                torch.zeros_like(self.simulator.dof_vel[:, self._upper_non_gripper_dof_idx]),
            )
            ** 2
        ).sum(dim=-1)

    def _get_obs_relative_to_door(self):
        relative_door_rot_6d = quat_to_tan_norm(self.relative_door_rot_buf, w_last=True)
        return torch.cat([self.relative_door_pos_buf, relative_door_rot_6d], dim=-1)

    def _get_obs_hand_handle_transform(self):
        if self._use_a2_base:
            raise RuntimeError(
                "A2 obs key 'hand_handle_transform' is legacy G1 compatibility. "
                "Use 'gripper_handle_transform' in A2 configs."
            )
        left_hand_pos = self.simulator.left_hand_transform_pos[:, 0, :]
        left_hand_rot_wxyz = self.simulator.left_hand_transform_rot[:, 0, :]
        left_hand_rot_6d = quat_to_tan_norm(wxyz_to_xyzw(left_hand_rot_wxyz), w_last=True)
        right_hand_pos = self.simulator.right_hand_transform_pos[:, 0, :]
        right_hand_rot_wxyz = self.simulator.right_hand_transform_rot[:, 0, :]
        right_hand_rot_6d = quat_to_tan_norm(wxyz_to_xyzw(right_hand_rot_wxyz), w_last=True)
        return torch.cat(
            [left_hand_pos, left_hand_rot_6d, right_hand_pos, right_hand_rot_6d], dim=-1
        )

    def _get_a2_gripper_handle_frame_transformer(self):
        sensor_name = self.A2_GRIPPER_HANDLE_FRAME_TRANSFORMER
        try:
            transformer = self.simulator.scene.sensors[sensor_name]
        except (AttributeError, KeyError) as exc:
            raise RuntimeError(
                f"A2 requires scene sensor '{sensor_name}' for gripper_handle_transform "
                "and grasp target helpers."
            ) from exc

        data = transformer.data
        target_pos_w = getattr(data, "target_pos_w", None)
        if target_pos_w is None or target_pos_w.ndim != 3 or target_pos_w.shape[1] != 2:
            shape = None if target_pos_w is None else tuple(target_pos_w.shape)
            raise RuntimeError(
                f"A2 sensor '{sensor_name}' must expose exactly 2 target frames; "
                f"target_pos_w shape is {shape}."
            )

        target_names = getattr(data, "target_frame_names", None)
        expected_names = ["handle", "pregrasp"]
        if target_names is not None and list(target_names) != expected_names:
            raise RuntimeError(
                f"A2 sensor '{sensor_name}' target order must be {expected_names}; "
                f"got {list(target_names)}."
            )
        return transformer

    def _get_a2_gripper_handle_contact_forces(self):
        sensor_name = self.A2_GRIPPER_HANDLE_CONTACT_SENSOR
        try:
            sensor = self.simulator.scene.sensors[sensor_name]
        except (AttributeError, KeyError) as exc:
            raise RuntimeError(
                f"A2 grasp reward requires scene sensor '{sensor_name}' for "
                "handle-specific gripper contact forces."
            ) from exc

        force_matrix_w = getattr(sensor.data, "force_matrix_w", None)
        expected_shape = (self.num_envs, 1, 2, 3)
        if (
            force_matrix_w is None
            or force_matrix_w.ndim != 4
            or tuple(force_matrix_w.shape) != expected_shape
        ):
            shape = None if force_matrix_w is None else tuple(force_matrix_w.shape)
            raise RuntimeError(
                f"A2 sensor '{sensor_name}' must expose force_matrix_w shape "
                f"{expected_shape}; got {shape}."
            )
        return force_matrix_w[:, 0, :, :]

    def _get_a2_stage2_grasp_contact_history_length(self):
        history_length = self.config.get("stage2_grasp_contact_history_length", None)
        if (
            history_length is None
            or isinstance(history_length, bool)
            or not isinstance(history_length, int)
            or history_length <= 0
        ):
            raise RuntimeError(
                "A2 stage2 grasp completion requires env.config."
                "stage2_grasp_contact_history_length to be a positive int; "
                f"got {history_length!r}."
            )
        return history_length

    def _get_a2_gripper_handle_contact_force_history(self):
        sensor_name = self.A2_GRIPPER_HANDLE_CONTACT_SENSOR
        try:
            sensor = self.simulator.scene.sensors[sensor_name]
        except (AttributeError, KeyError) as exc:
            raise RuntimeError(
                f"A2 stage2 completion requires scene sensor '{sensor_name}' for "
                "handle-specific gripper contact force history."
            ) from exc

        history_length = self._get_a2_stage2_grasp_contact_history_length()
        force_matrix_w_history = getattr(sensor.data, "force_matrix_w_history", None)
        expected_shape = (self.num_envs, history_length, 1, 2, 3)
        if (
            force_matrix_w_history is None
            or force_matrix_w_history.ndim != 5
            or tuple(force_matrix_w_history.shape) != expected_shape
        ):
            shape = (
                None
                if force_matrix_w_history is None
                else tuple(force_matrix_w_history.shape)
            )
            raise RuntimeError(
                f"A2 sensor '{sensor_name}' must expose force_matrix_w_history shape "
                f"{expected_shape}; got {shape}."
            )
        return force_matrix_w_history[:, :, 0, :, :]

    def _get_a2_axes_from_quat(self, quat, context):
        expected_shape = (self.num_envs, 4)
        if (
            quat is None
            or not torch.is_tensor(quat)
            or quat.ndim != 2
            or tuple(quat.shape) != expected_shape
        ):
            shape = None if quat is None else tuple(quat.shape)
            raise RuntimeError(
                f"{context} requires quaternion shape {expected_shape}; got {shape}."
            )

        basis = quat.new_tensor(
            (
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
            )
        )
        basis = basis.unsqueeze(0).expand(self.num_envs, -1, -1)
        quat_expanded = quat[:, None, :].expand(-1, 3, -1).reshape(-1, 4)
        return quat_apply(quat_expanded, basis.reshape(-1, 3)).reshape(
            self.num_envs, 3, 3
        )

    def _get_a2_orientation_alignment_and_axes(self, target_quat_source, context):
        target_axes_source = self._get_a2_axes_from_quat(target_quat_source, context)
        source_y = target_quat_source.new_tensor((0.0, 1.0, 0.0)).expand(
            self.num_envs, -1
        )
        source_z = target_quat_source.new_tensor((0.0, 0.0, 1.0)).expand(
            self.num_envs, -1
        )

        opening_alignment = torch.abs(
            torch.sum(source_y * target_axes_source[:, 1, :], dim=-1)
        ).clamp(0.0, 1.0)
        approach_alignment = torch.sum(
            source_z * target_axes_source[:, 2, :], dim=-1
        ).clamp(-1.0, 1.0)
        return opening_alignment, approach_alignment, target_axes_source

    def _format_a2_axes_for_terminal_diagnostics(self, axes):
        return {
            "x": axes[0],
            "y": axes[1],
            "z": axes[2],
        }

    def _get_a2_terminal_diagnostics(self, env_ids):
        env_ids = self._normalize_render_env_ids(env_ids)
        if not self._use_a2_base:
            return self._get_terminal_diagnostics(env_ids)

        expected_frame_names = ["handle", "pregrasp"]
        transformer = self._get_a2_gripper_handle_frame_transformer()
        data = transformer.data
        target_frame_names = getattr(data, "target_frame_names", None)
        if target_frame_names is None or list(target_frame_names) != expected_frame_names:
            raise RuntimeError(
                f"A2 terminal diagnostics requires target order {expected_frame_names}; "
                f"got {None if target_frame_names is None else list(target_frame_names)}."
            )

        target_pos_source = getattr(data, "target_pos_source", None)
        expected_target_pos_source_shape = (self.num_envs, 2, 3)
        if (
            target_pos_source is None
            or target_pos_source.ndim != 3
            or tuple(target_pos_source.shape) != expected_target_pos_source_shape
        ):
            shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires target_pos_source shape "
                f"{expected_target_pos_source_shape}; got {shape}."
            )

        target_quat_source = getattr(data, "target_quat_source", None)
        expected_target_quat_source_shape = (self.num_envs, 2, 4)
        if (
            target_quat_source is None
            or target_quat_source.ndim != 3
            or tuple(target_quat_source.shape) != expected_target_quat_source_shape
        ):
            shape = None if target_quat_source is None else tuple(target_quat_source.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires target_quat_source shape "
                f"{expected_target_quat_source_shape}; got {shape}."
            )

        source_quat_w = getattr(data, "source_quat_w", None)
        expected_source_quat_w_shape = (self.num_envs, 4)
        if (
            source_quat_w is None
            or source_quat_w.ndim != 2
            or tuple(source_quat_w.shape) != expected_source_quat_w_shape
        ):
            shape = None if source_quat_w is None else tuple(source_quat_w.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires source_quat_w shape "
                f"{expected_source_quat_w_shape}; got {shape}."
            )

        gripper_dof_names = ("arm_j7", "arm_j8")
        missing_gripper_dofs = [
            dof_name for dof_name in gripper_dof_names if dof_name not in self.dof_names
        ]
        if missing_gripper_dofs:
            raise RuntimeError(
                "A2 terminal diagnostics requires gripper DOFs "
                f"{gripper_dof_names}, missing {missing_gripper_dofs}."
            )
        expected_gripper_dof_indices = torch.tensor(
            [self.dof_names.index(dof_name) for dof_name in gripper_dof_names],
            device=self.device,
            dtype=torch.long,
        )
        gripper_dof_indices = getattr(self, "_a2_gripper_dof_indices", None)
        if (
            gripper_dof_indices is None
            or not torch.is_tensor(gripper_dof_indices)
            or tuple(gripper_dof_indices.shape) != (2,)
            or not torch.equal(gripper_dof_indices.to(self.device), expected_gripper_dof_indices)
        ):
            shape = None if gripper_dof_indices is None else tuple(gripper_dof_indices.shape)
            value = None if gripper_dof_indices is None else gripper_dof_indices.tolist()
            raise RuntimeError(
                "A2 terminal diagnostics requires arm_j7/arm_j8 DOF mapping "
                f"{expected_gripper_dof_indices.tolist()}; got shape={shape}, value={value}."
            )

        gripper_body_names = ("arm_body7", "arm_body8")
        missing_gripper_bodies = [
            body_name
            for body_name in gripper_body_names
            if body_name not in self.simulator.body_names
        ]
        if missing_gripper_bodies:
            raise RuntimeError(
                "A2 terminal diagnostics requires gripper contact bodies "
                f"{gripper_body_names}, missing {missing_gripper_bodies}."
            )
        expected_gripper_body_indices = [
            self.simulator.body_names.index(body_name) for body_name in gripper_body_names
        ]
        gripper_force_body_indices = getattr(self, "_a2_gripper_force_body_indices", None)
        if gripper_force_body_indices is None:
            raise RuntimeError(
                "A2 terminal diagnostics requires _a2_gripper_force_body_indices for "
                "arm_body7/arm_body8."
            )
        if list(gripper_force_body_indices) != expected_gripper_body_indices:
            raise RuntimeError(
                "A2 terminal diagnostics requires arm_body7/arm_body8 body mapping "
                f"{expected_gripper_body_indices}; got {list(gripper_force_body_indices)}."
            )

        contact_forces = getattr(self.simulator, "contact_forces", None)
        if (
            contact_forces is None
            or contact_forces.ndim != 3
            or contact_forces.shape[0] != self.num_envs
            or contact_forces.shape[2] != 3
            or contact_forces.shape[1] <= max(expected_gripper_body_indices)
        ):
            shape = None if contact_forces is None else tuple(contact_forces.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires simulator.contact_forces shape "
                f"({self.num_envs}, >= {max(expected_gripper_body_indices) + 1}, 3); "
                f"got {shape}."
            )
        contact_force_arm_body7_8_w = contact_forces[:, expected_gripper_body_indices, :]
        contact_force_arm_body7_8_norm = torch.linalg.norm(
            contact_force_arm_body7_8_w, dim=-1
        )

        handle_contact_force_w = self._get_a2_gripper_handle_contact_forces()
        if tuple(handle_contact_force_w.shape) != (self.num_envs, 2, 3):
            raise RuntimeError(
                "A2 terminal diagnostics requires handle contact force shape "
                f"({self.num_envs}, 2, 3); got {tuple(handle_contact_force_w.shape)}."
            )
        handle_contact_force_norm = torch.linalg.norm(handle_contact_force_w, dim=-1)

        source_quat = source_quat_w[:, None, :].expand(-1, 2, -1).reshape(-1, 4)
        handle_contact_force_source = quat_apply(
            quat_inv(source_quat), handle_contact_force_w.reshape(-1, 3)
        ).reshape(self.num_envs, 2, 3)
        squeeze_y = handle_contact_force_source[:, :, 1]

        dof_pos = getattr(self.simulator, "dof_pos", None)
        if (
            dof_pos is None
            or dof_pos.ndim != 2
            or dof_pos.shape[0] != self.num_envs
            or dof_pos.shape[1] <= int(torch.max(expected_gripper_dof_indices).item())
        ):
            shape = None if dof_pos is None else tuple(dof_pos.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires simulator.dof_pos shape "
                f"({self.num_envs}, >= {int(torch.max(expected_gripper_dof_indices).item()) + 1}); "
                f"got {shape}."
            )
        arm_j7_j8_pos = dof_pos[:, expected_gripper_dof_indices]

        close_target = getattr(self, "_a2_gripper_close_target", None)
        if (
            close_target is None
            or not torch.is_tensor(close_target)
            or tuple(close_target.shape) != (2,)
        ):
            shape = None if close_target is None else tuple(close_target.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires _a2_gripper_close_target shape "
                f"(2,); got {shape}."
            )
        arm_j7_j8_close_error = arm_j7_j8_pos - close_target[None, :]

        gripper_primitive_raw = getattr(self, "_a2_gripper_primitive_raw", None)
        if (
            gripper_primitive_raw is None
            or not torch.is_tensor(gripper_primitive_raw)
            or tuple(gripper_primitive_raw.shape) != (self.num_envs, 1)
        ):
            shape = None if gripper_primitive_raw is None else tuple(gripper_primitive_raw.shape)
            raise RuntimeError(
                "A2 terminal diagnostics requires _a2_gripper_primitive_raw shape "
                f"({self.num_envs}, 1); got {shape}."
            )

        for field_name in ("stage_buf", "time_in_stage_buf", "episode_length_buf"):
            field_value = getattr(self, field_name, None)
            if (
                field_value is None
                or not torch.is_tensor(field_value)
                or tuple(field_value.shape) != (self.num_envs,)
            ):
                shape = None if field_value is None else tuple(field_value.shape)
                raise RuntimeError(
                    f"A2 terminal diagnostics requires {field_name} shape "
                    f"({self.num_envs},); got {shape}."
                )

        target_pos_source_handle_distance = torch.linalg.norm(
            target_pos_source[:, 0, :], dim=-1
        )
        target_pos_source_pregrasp_distance = torch.linalg.norm(
            target_pos_source[:, 1, :], dim=-1
        )
        handle_opening_alignment, handle_approach_alignment, target_axes_source_handle = (
            self._get_a2_orientation_alignment_and_axes(
                target_quat_source[:, 0, :],
                "A2 terminal diagnostics handle target orientation",
            )
        )
        (
            pregrasp_opening_alignment,
            pregrasp_approach_alignment,
            target_axes_source_pregrasp,
        ) = self._get_a2_orientation_alignment_and_axes(
            target_quat_source[:, 1, :],
            "A2 terminal diagnostics pregrasp target orientation",
        )
        gripper_source_axes_w = self._get_a2_axes_from_quat(
            source_quat_w, "A2 terminal diagnostics gripper source orientation"
        )
        terminal_reasons = self._terminal_reasons_for_env_ids(env_ids)

        selected_stage_buf = self.stage_buf[env_ids].detach().cpu().tolist()
        selected_time_in_stage_buf = self.time_in_stage_buf[env_ids].detach().cpu().tolist()
        selected_episode_length_buf = self.episode_length_buf[env_ids].detach().cpu().tolist()
        selected_contact_force_arm_body7_8_w = (
            contact_force_arm_body7_8_w[env_ids].detach().cpu().tolist()
        )
        selected_contact_force_arm_body7_8_norm = (
            contact_force_arm_body7_8_norm[env_ids].detach().cpu().tolist()
        )
        selected_handle_contact_force_w = (
            handle_contact_force_w[env_ids].detach().cpu().tolist()
        )
        selected_handle_contact_force_norm = (
            handle_contact_force_norm[env_ids].detach().cpu().tolist()
        )
        selected_squeeze_y = squeeze_y[env_ids].detach().cpu().tolist()
        selected_arm_j7_j8_pos = arm_j7_j8_pos[env_ids].detach().cpu().tolist()
        selected_arm_j7_j8_close_error = (
            arm_j7_j8_close_error[env_ids].detach().cpu().tolist()
        )
        selected_gripper_primitive_raw = (
            gripper_primitive_raw[env_ids].detach().cpu().tolist()
        )
        selected_handle_distance = (
            target_pos_source_handle_distance[env_ids].detach().cpu().tolist()
        )
        selected_pregrasp_distance = (
            target_pos_source_pregrasp_distance[env_ids].detach().cpu().tolist()
        )
        selected_handle_opening_alignment = (
            handle_opening_alignment[env_ids].detach().cpu().tolist()
        )
        selected_handle_approach_alignment = (
            handle_approach_alignment[env_ids].detach().cpu().tolist()
        )
        selected_pregrasp_opening_alignment = (
            pregrasp_opening_alignment[env_ids].detach().cpu().tolist()
        )
        selected_pregrasp_approach_alignment = (
            pregrasp_approach_alignment[env_ids].detach().cpu().tolist()
        )
        selected_source_quat_w = source_quat_w[env_ids].detach().cpu().tolist()
        selected_source_axes_w = gripper_source_axes_w[env_ids].detach().cpu().tolist()
        selected_target_quat_source_handle = (
            target_quat_source[env_ids, 0, :].detach().cpu().tolist()
        )
        selected_target_quat_source_pregrasp = (
            target_quat_source[env_ids, 1, :].detach().cpu().tolist()
        )
        selected_target_axes_source_handle = (
            target_axes_source_handle[env_ids].detach().cpu().tolist()
        )
        selected_target_axes_source_pregrasp = (
            target_axes_source_pregrasp[env_ids].detach().cpu().tolist()
        )
        selected_target_pos_source_handle = (
            target_pos_source[env_ids, 0, :].detach().cpu().tolist()
        )
        selected_target_pos_source_pregrasp = (
            target_pos_source[env_ids, 1, :].detach().cpu().tolist()
        )
        close_target_list = close_target.detach().cpu().tolist()

        diagnostics = []
        for idx, env_id in enumerate(env_ids.tolist()):
            diagnostics.append(
                {
                    "env_id": int(env_id),
                    "stage_buf": int(selected_stage_buf[idx]),
                    "time_in_stage_buf": int(selected_time_in_stage_buf[idx]),
                    "episode_length_buf": int(selected_episode_length_buf[idx]),
                    "terminal_reasons": terminal_reasons[idx],
                    "contact_force_arm_body7_8_w": selected_contact_force_arm_body7_8_w[
                        idx
                    ],
                    "contact_force_arm_body7_8_norm": selected_contact_force_arm_body7_8_norm[
                        idx
                    ],
                    "handle_contact_force_w": selected_handle_contact_force_w[idx],
                    "handle_contact_force_norm": selected_handle_contact_force_norm[idx],
                    "squeeze_y": selected_squeeze_y[idx],
                    "arm_j7_j8_pos": selected_arm_j7_j8_pos[idx],
                    "arm_j7_j8_close_target": close_target_list,
                    "arm_j7_j8_close_error": selected_arm_j7_j8_close_error[idx],
                    "gripper_primitive_raw": selected_gripper_primitive_raw[idx],
                    "target_pos_source_handle_distance": float(
                        selected_handle_distance[idx]
                    ),
                    "target_pos_source_pregrasp_distance": float(
                        selected_pregrasp_distance[idx]
                    ),
                    "pregrasp_opening_alignment": float(
                        selected_pregrasp_opening_alignment[idx]
                    ),
                    "pregrasp_approach_alignment": float(
                        selected_pregrasp_approach_alignment[idx]
                    ),
                    "handle_opening_alignment": float(
                        selected_handle_opening_alignment[idx]
                    ),
                    "handle_approach_alignment": float(
                        selected_handle_approach_alignment[idx]
                    ),
                    "gripper_source_quat_w": selected_source_quat_w[idx],
                    "gripper_source_axes_w": self._format_a2_axes_for_terminal_diagnostics(
                        selected_source_axes_w[idx]
                    ),
                    "target_quat_source_handle": selected_target_quat_source_handle[
                        idx
                    ],
                    "target_quat_source_pregrasp": selected_target_quat_source_pregrasp[
                        idx
                    ],
                    "target_axes_source_handle": self._format_a2_axes_for_terminal_diagnostics(
                        selected_target_axes_source_handle[idx]
                    ),
                    "target_axes_source_pregrasp": self._format_a2_axes_for_terminal_diagnostics(
                        selected_target_axes_source_pregrasp[idx]
                    ),
                    "target_pos_source_handle": selected_target_pos_source_handle[idx],
                    "target_pos_source_pregrasp": selected_target_pos_source_pregrasp[
                        idx
                    ],
                }
            )
        return diagnostics

    def init_a2_eval_stage2_step_trace(self):
        if not self._use_a2_base:
            raise RuntimeError("A2 stage2 step trace can only be initialized for A2 envs.")
        if not getattr(self, "is_evaluating", False):
            raise RuntimeError("A2 stage2 step trace must be initialized in eval mode.")
        self._a2_stage2_step_trace_records = []
        self._a2_stage2_step_trace_step_index = 0

    def _capture_a2_eval_stage2_step_trace(self):
        if not self._use_a2_base:
            return
        if not getattr(self, "is_evaluating", False):
            return
        if "_a2_stage2_step_trace_records" not in self.__dict__:
            raise RuntimeError(
                "A2 stage2 step trace capture requested before "
                "init_a2_eval_stage2_step_trace()."
            )

        stage_buf = getattr(self, "stage_buf", None)
        if (
            stage_buf is None
            or not torch.is_tensor(stage_buf)
            or tuple(stage_buf.shape) != (self.num_envs,)
        ):
            shape = None if stage_buf is None else tuple(stage_buf.shape)
            raise RuntimeError(
                "A2 stage2 step trace requires stage_buf shape "
                f"({self.num_envs},); got {shape}."
            )

        step_index = getattr(self, "_a2_stage2_step_trace_step_index", None)
        if isinstance(step_index, bool) or not isinstance(step_index, int) or step_index < 0:
            raise RuntimeError(
                "A2 stage2 step trace requires non-negative integer step index; "
                f"got {step_index!r}."
            )

        stage2_env_ids = (stage_buf == self.STAGE_GRASP).nonzero(as_tuple=False).flatten()
        if stage2_env_ids.numel() > 0:
            records = self._get_a2_terminal_diagnostics(stage2_env_ids)
            if len(records) != stage2_env_ids.numel():
                raise RuntimeError(
                    "A2 stage2 step trace diagnostics returned "
                    f"{len(records)} entries for {stage2_env_ids.numel()} env ids."
                )
            for record in records:
                if not isinstance(record, dict):
                    raise TypeError(
                        "A2 stage2 step trace records must be dicts, "
                        f"got {type(record).__name__}."
                    )
                record["step_index"] = step_index
            self._a2_stage2_step_trace_records.extend(records)

        self._a2_stage2_step_trace_step_index += 1

    def get_a2_eval_stage2_step_trace_records(self):
        if not self._use_a2_base:
            raise RuntimeError("A2 stage2 step trace is only available for A2 envs.")
        if "_a2_stage2_step_trace_records" not in self.__dict__:
            raise RuntimeError(
                "A2 stage2 step trace requested before init_a2_eval_stage2_step_trace()."
            )
        return [dict(record) for record in self._a2_stage2_step_trace_records]

    def _get_obs_gripper_handle_transform(self):
        if not self._use_a2_base:
            raise RuntimeError(
                "gripper_handle_transform is only defined for A2 Piper gripper observations."
            )
        data = self._get_a2_gripper_handle_frame_transformer().data
        target_pos_source = getattr(data, "target_pos_source", None)
        target_quat_source = getattr(data, "target_quat_source", None)
        if (
            target_pos_source is None
            or target_quat_source is None
            or target_pos_source.ndim != 3
            or target_quat_source.ndim != 3
            or target_pos_source.shape[1] != 2
            or target_quat_source.shape[1] != 2
        ):
            pos_shape = None if target_pos_source is None else tuple(target_pos_source.shape)
            quat_shape = None if target_quat_source is None else tuple(target_quat_source.shape)
            raise RuntimeError(
                "A2 gripper_handle_transform requires 2 source-relative target poses; "
                f"target_pos_source shape={pos_shape}, target_quat_source shape={quat_shape}."
            )

        handle_pos = target_pos_source[:, 0, :]
        handle_rot_6d = quat_to_tan_norm(
            wxyz_to_xyzw(target_quat_source[:, 0, :]), w_last=True
        )
        pregrasp_pos = target_pos_source[:, 1, :]
        pregrasp_rot_6d = quat_to_tan_norm(
            wxyz_to_xyzw(target_quat_source[:, 1, :]), w_last=True
        )
        return torch.cat([handle_pos, handle_rot_6d, pregrasp_pos, pregrasp_rot_6d], dim=-1)

    def _get_obs_hand_force(self):
        if self._use_a2_base:
            if not hasattr(self, "_a2_gripper_force_body_indices"):
                raise RuntimeError(
                    "A2 hand_force requires name-based gripper body indices for "
                    "arm_body7 and arm_body8."
                )
            hand_force = self.simulator.contact_forces[:, self._a2_gripper_force_body_indices, :]
            return hand_force.reshape(hand_force.shape[0], 6)
        left_hand_force = self.simulator.contact_forces[:, self.left_hand_indices, :]
        right_hand_force = self.simulator.contact_forces[:, self.right_hand_indices, :]
        return torch.cat(
            [
                left_hand_force.reshape(left_hand_force.shape[0], -1),
                right_hand_force.reshape(right_hand_force.shape[0], -1),
            ],
            dim=-1,
        )

    def _get_obs_privileged_door_info(self):
        return torch.stack(
            [
                self.door_width,
                self.door_height,
                self.door_handle_height,
                self.door_handle_width,
                self.door_weight / 100.0,
                self.door_open_lr,
                1.0 - self.door_open_lr,
                self.door_open_io,
            ],
            dim=1,
        )

    def _get_obs_door_dof_pos(self):
        return self.simulator.get_task_dof_pos("door")[:, :2]

    def _get_obs_dof_pos_non_finger(self):
        return self.simulator.dof_pos[:, :-14]

    def _get_obs_dof_vel_non_finger(self):
        return self.simulator.dof_vel[:, :-14]

    def _get_obs_target_obj_pos(self):
        return (
            self.simulator.scene.sensors["head_target_frame_transformer"]
            .data.target_pos_source[:, 0, :]
            .clone()
        )

    def _compute_grasp_target(self):
        if self._use_a2_base:
            return self._get_a2_gripper_handle_frame_transformer().data.target_pos_w[
                :, 0, :
            ].clone()
        grasp_target_pos_w = (
            self.simulator.scene.sensors["right_hand_frame_transformer"]
            .data.target_pos_w[:, 0, :]
            .clone()
        )
        return grasp_target_pos_w

    @override
    def _get_handle_anchor_pos(self):
        """Lever center (grasp_target world pos) for handle_* eval cameras.

        target_pos_w[:, 0, :] is the handle frame target (= lever center after
        the grasp_target fix). Shape: (num_envs, 3).
        """
        transformer = self._get_a2_gripper_handle_frame_transformer()
        target_pos_w = transformer.data.target_pos_w
        if target_pos_w.ndim != 3 or target_pos_w.shape[1] < 1:
            shape = None if target_pos_w is None else tuple(target_pos_w.shape)
            raise RuntimeError(
                f"A2 handle anchor requires target_pos_w[:, 0, :] with shape "
                f"(num_envs, >=1, 3); got {shape}."
            )
        return target_pos_w[:, 0, :].clone()

    def _compute_pre_grasp_target(self):
        if self._use_a2_base:
            return self._get_a2_gripper_handle_frame_transformer().data.target_pos_w[
                :, 1, :
            ].clone()
        grasp_target_pos_w = self._compute_grasp_target()
        grasp_target_pos_w[:, 2] += 0.1
        return grasp_target_pos_w

    @override
    def _reset_object_states_callback(self, env_ids):
        self._reset_door_states(env_ids)
        return super()._reset_object_states_callback(env_ids)

    @override
    def _reset_robot_states_callback(self, env_ids, target_states=None):
        if self._use_a2_base:
            return A2Base._reset_robot_states_callback(self, env_ids, target_states)
        return super()._reset_robot_states_callback(env_ids, target_states)

    @override
    def _reset_root_states(self, env_ids, target_root_states=None):
        if self._use_a2_base:
            if target_root_states is not None:
                return A2Base._reset_root_states(self, env_ids, target_root_states)

            self.target_robot_root_states[env_ids] = self.base_init_state
            self.target_robot_root_states[env_ids, :3] += self.env_origins[env_ids]
            self.target_robot_root_states[env_ids, 0:1] = (
                torch_rand_float(-1.5, -0.6, (len(env_ids), 1), device=str(self.device))
                + self.env_origins[env_ids, 0:1]
            )
            self.target_robot_root_states[env_ids, 1:2] = (
                torch_rand_float(-0.5, 0.5, (len(env_ids), 1), device=str(self.device))
                + self.env_origins[env_ids, 1:2]
            )
            r, p, _ = euler_xyz_from_quat(self.target_robot_root_states[env_ids, 3:7])
            random_yaw = torch_rand_float(
                -torch.pi / 4, torch.pi / 4, (len(env_ids), 1), device=str(self.device)
            )[:, 0]
            self.target_robot_root_states[env_ids, 3:7] = quat_from_euler_xyz(
                r, p, random_yaw
            )
            self.target_robot_root_states[env_ids, 7:13] = 0.0
            return

        self.target_robot_root_states[env_ids, 7:13] = torch_rand_float(
            -0.5, 0.5, (len(env_ids), 6), device=str(self.device)
        )  # [7:10]: lin vel, [10:13]: ang vel

        r, p, _ = euler_xyz_from_quat(self.target_robot_root_states[env_ids, 3:7])
        self.target_robot_root_states[env_ids, 0:1] = torch_rand_float(
            -1.5, -0.6, (len(env_ids), 1), device=str(self.device)
        )
        self.target_robot_root_states[env_ids, 1:2] = torch_rand_float(
            -0.5, 0.5, (len(env_ids), 1), device=str(self.device)
        )
        self.target_robot_root_states[env_ids, 0:2] += self.env_origins[env_ids, 0:2]
        random_yaw = torch_rand_float(
            -torch.pi / 4, torch.pi / 4, (len(env_ids), 1), device=str(self.device)
        )[:, 0]
        self.target_robot_root_states[env_ids, 3:7] = quat_from_euler_xyz(r, p, random_yaw)

    @override
    def _reset_dofs(self, env_ids, target_state=None):
        if self._use_a2_base:
            if target_state is not None:
                return A2Base._reset_dofs(self, env_ids, target_state)

            self.target_robot_dof_state[env_ids, :, 0] = (
                self.default_dof_pos
                * torch_rand_float(0.8, 1.2, (len(env_ids), self.num_dof), device=str(self.device))
            )
            self.target_robot_dof_state[env_ids, :, 1] = 0.0
            return

        # randomize wrist in +- 80 deg
        xx, yy = torch.meshgrid(env_ids, self.wrist_dof_idx)
        self.target_robot_dof_state[xx, yy, 0] = torch_rand_float(
            -1.39626, 1.39626, (len(env_ids), len(self.wrist_dof_idx)), device=str(self.device)
        )

        # completely randomize finger dofs
        xx, yy = torch.meshgrid(env_ids, self.finger_dof_idx)
        upper_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_upper_limit_list, device=str(self.device)
        )[None, self.finger_dof_idx]
        lower_limit = torch.tensor(
            self.simulator.robot_config.dof_pos_lower_limit_list, device=str(self.device)
        )[None, self.finger_dof_idx]
        self.target_robot_dof_state[xx, yy, 0] = lower_limit + (
            upper_limit - lower_limit
        ) * torch_rand_float(
            0.0, 1.0, (len(env_ids), len(self.finger_dof_idx)), device=str(self.device)
        )

        # set velocities to 0
        self.target_robot_dof_state[env_ids, :, 1] = 0.0

    def _reset_door_states(self, env_ids):
        randomize_door_init_state = self.config.get("randomize_door_init_state", False)
        self.door_dof_state_buf[:] = 0.0
        if randomize_door_init_state:
            # 33% of the environments to have a different initial state
            rand_env_ids = env_ids[torch.randperm(len(env_ids))[: len(env_ids) // 3]]
            self.door_dof_state_buf[rand_env_ids, 0] = torch_rand_float(
                0.261799, 1.74533, (len(rand_env_ids), 1), device=self.device
            ).squeeze(-1)
        door_dof_state_dict = {
            "door": (
                self.door_dof_state_buf,
                torch.zeros_like(self.door_dof_state_buf),
                torch.tensor([0, 1, 2], device=self.device, dtype=torch.long),
            )
        }
        self.simulator.set_task_dof_state_tensor(env_ids, door_dof_state_dict)

        door_dof_target = torch.zeros(self.num_envs, 3, device=self.device, requires_grad=False)
        door_dof_target[:, 0] = 0.0
        door_dof_target[:, 1] = 15 * torch.pi / 180.0  # tension the door handle
        self.simulator.apply_torques_at_task_dof(env_ids, {"door": door_dof_target})

    @override
    def _check_termination(self):
        super()._check_termination()
        if self._use_a2_base:
            a2_config = self.config.get("a2_base", {})
            bad_orientation_limit_angle = float(
                a2_config.get("bad_orientation_limit_angle", 0.9)
            )
            tilt = torch.acos(torch.clamp(-self.projected_gravity[:, 2], -1.0, 1.0))
            bad_orientation = tilt > bad_orientation_limit_angle
            self._mark_terminal_reason("bad_orientation", bad_orientation)
            self.reset_buf |= bad_orientation

        door_distance = self.relative_door_pos_buf.norm(dim=-1) > 4.0
        self._mark_terminal_reason("door_distance", door_distance)
        self.reset_buf |= door_distance

        # A2 arm body DOF / Piper arm_j1..j6 overspeed termination; gripper excluded.
        dof_overspeed = torch.any(
            torch.abs(self.simulator.dof_vel[:, self._upper_non_gripper_dof_idx])
            > self.termination_level * 20.0,
            dim=-1,
        )
        not_just_resetted = self.episode_length_buf > 20

        upper_dof_overspeed = dof_overspeed & not_just_resetted
        self._mark_terminal_reason("upper_dof_overspeed", upper_dof_overspeed)
        self.reset_buf |= upper_dof_overspeed

        # reset if the homie command is too large when grasping or opening the door
        # is_grasping_or_opening = (self.stage_buf == DoorPregrasp.STAGE_GRASP) | (self.stage_buf == DoorPregrasp.STAGE_OPEN)
        # homie_command_norm = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1)
        # self.reset_buf |= (homie_command_norm > self.termination_level) & is_grasping_or_opening

    @property
    def ground_height(self):
        return 0.0

    def _stage_0_reward_condition(self):
        # walk to the door
        return torch.ones(self.num_envs, dtype=torch.bool, device=self.device)

    def _stage_0_to_complete_condition(self):
        return self._stage_0_to_1_advance_condition()

    def _stage_0_to_1_advance_condition(self):
        # get close enough to the door
        grasp_target = self._compute_grasp_target()
        root_pos = self.simulator.robot_root_states[:, :3].clone()
        root_pos[:, 2] = grasp_target[:, 2]
        # A2 is a quadruped with a longer trunk/base footprint than upright G1.
        # Keep the root farther from the handle target to avoid trunk-door collisions.
        cond = (root_pos - grasp_target).norm(dim=-1) < 0.6

        # keep A2 arm body DOF / Piper arm_j1..j6 down; gripper arm_j7/8 are excluded.
        max_deviation = (
            torch.abs(
                self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx]
                - self.resting_dof_pos[:, self._upper_non_gripper_dof_idx]
            )
            .max(dim=-1)
            .values
        )
        cond &= max_deviation < 0.25
        return cond

    def _stage_1_reward_condition(self):
        # small homie command
        cond = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1) <= 0.1
        # stay close to the door
        cond &= self._stage_0_to_1_advance_condition()
        return cond

    def _stage_1_to_complete_condition(self):
        return self._stage_1_to_2_advance_condition()

    def _stage_1_to_2_advance_condition(self):
        if self._use_a2_base:
            data = self._get_a2_gripper_handle_frame_transformer().data
            target_pos_source = getattr(data, "target_pos_source", None)
            if (
                target_pos_source is None
                or target_pos_source.ndim != 3
                or target_pos_source.shape != (self.num_envs, 2, 3)
            ):
                shape = None if target_pos_source is None else tuple(target_pos_source.shape)
                raise RuntimeError(
                    "A2 stage1->2 transition requires target_pos_source shape "
                    f"({self.num_envs}, 2, 3); got {shape}."
                )

            pregrasp_distance = torch.linalg.norm(target_pos_source[:, 1, :], dim=-1)
            opening_alignment, approach_alignment = (
                self._get_a2_gripper_handle_orientation_metrics()
            )
            base_still = torch.norm(self.get_physical_homie_commands()[:, :3], dim=1) <= 0.1

            gripper_pos = self.simulator.dof_pos[:, self._a2_gripper_dof_indices]
            close_target = self._a2_gripper_close_target
            open_target = self._a2_gripper_open_target
            span = (open_target - close_target).abs()
            if torch.any(span <= 1.0e-4):
                raise RuntimeError(
                    "A2 stage1->2 transition requires non-zero gripper open/close span; "
                    f"open_target={open_target.tolist()}, close_target={close_target.tolist()}."
                )
            lower = torch.minimum(close_target, open_target) - 0.25 * span
            upper = torch.maximum(close_target, open_target) + 0.25 * span
            gripper_ready = torch.all(
                (gripper_pos >= lower[None, :]) & (gripper_pos <= upper[None, :]),
                dim=-1,
            )

            pregrasp_ready = (
                (pregrasp_distance < 0.1)
                & (opening_alignment >= 0.8)
                & (approach_alignment >= 0.8)
                & base_still
                & gripper_ready
            )
            door_open_bypass = (
                self.simulator.scene.articulations["door"].data.joint_pos[:, 0] > 0.174533
            )
            return pregrasp_ready | door_open_bypass
        # raise hand to pre-grasp position
        pre_grasp_target = self._compute_pre_grasp_target()

        left_palm_body_pos = self.simulator._rigid_body_pos[:, self.left_palm_idx, :]
        left_hand_above_handle = left_palm_body_pos[:, 2] > self.door_handle_height + 0.05
        left_hand_close_to_pre_grasp_target = (left_palm_body_pos - pre_grasp_target).norm(
            dim=-1
        ) < 0.1
        left_hand_close_to_pre_grasp_dof_target = (
            torch.abs(self.simulator.dof_pos[:, self._left_hand_dof_idx] - self._left_p0).mean(
                dim=-1
            )
            < 0.174533
        )
        left_hand_cond = (
            left_hand_above_handle
            & left_hand_close_to_pre_grasp_target
            & left_hand_close_to_pre_grasp_dof_target
        )

        right_palm_body_pos = self.simulator._rigid_body_pos[:, self.right_palm_idx, :]
        right_hand_above_handle = right_palm_body_pos[:, 2] > self.door_handle_height + 0.05
        right_hand_close_to_pre_grasp_target = (right_palm_body_pos - pre_grasp_target).norm(
            dim=-1
        ) < 0.1
        right_hand_close_to_pre_grasp_dof_target = (
            torch.abs(self.simulator.dof_pos[:, self._right_hand_dof_idx] - self._right_p0).mean(
                dim=-1
            )
            < 0.174533
        )
        right_hand_cond = (
            right_hand_above_handle
            & right_hand_close_to_pre_grasp_target
            & right_hand_close_to_pre_grasp_dof_target
        )

        cond = torch.where(self.door_open_lr < 0, left_hand_cond, right_hand_cond)

        cond &= self._reward_hand_handle_orientation() > 0.2

        cond &= torch.norm(self.get_physical_homie_commands()[:, :3], dim=1) <= 0.1

        door_opened = self.simulator.scene.articulations["door"].data.joint_pos[:, 0] > 0.174533

        return cond | door_opened

    def _stage_2_reward_condition(self):
        return torch.norm(self.get_physical_homie_commands()[:, :3], dim=1) <= 0.1

    def _stage_2_to_complete_condition(self):
        if self._use_a2_base:
            forces_w_history = self._get_a2_gripper_handle_contact_force_history()
            data = self._get_a2_gripper_handle_frame_transformer().data
            source_quat_w = getattr(data, "source_quat_w", None)
            if (
                source_quat_w is None
                or source_quat_w.ndim != 2
                or source_quat_w.shape != (self.num_envs, 4)
            ):
                shape = None if source_quat_w is None else tuple(source_quat_w.shape)
                raise RuntimeError(
                    "A2 stage2 completion requires source_quat_w shape "
                    f"({self.num_envs}, 4); got {shape}."
                )

            history_length = self._get_a2_stage2_grasp_contact_history_length()
            if tuple(forces_w_history.shape) != (self.num_envs, history_length, 2, 3):
                raise RuntimeError(
                    "A2 stage2 completion requires contact force history shape "
                    f"({self.num_envs}, {history_length}, 2, 3); "
                    f"got {tuple(forces_w_history.shape)}."
                )

            source_quat = (
                source_quat_w[:, None, None, :]
                .expand(-1, history_length, 2, -1)
                .reshape(-1, 4)
            )
            forces_source = quat_apply(
                quat_inv(source_quat), forces_w_history.reshape(-1, 3)
            ).reshape(self.num_envs, history_length, 2, 3)

            contact_force = torch.linalg.norm(forces_w_history, dim=-1)
            both_contact = torch.all(contact_force > 1.0, dim=-1)
            squeeze_y = forces_source[:, :, :, 1]
            sufficient_squeeze = torch.all(torch.abs(squeeze_y) > 0.5, dim=-1)
            opposite_squeeze = squeeze_y[:, :, 0] * squeeze_y[:, :, 1] < 0.0
            all_history_squeezed = torch.all(
                both_contact & sufficient_squeeze & opposite_squeeze, dim=-1
            )
            actual_time_in_stage_buf = getattr(self, "actual_time_in_stage_buf", None)
            if (
                actual_time_in_stage_buf is None
                or not torch.is_tensor(actual_time_in_stage_buf)
                or tuple(actual_time_in_stage_buf.shape) != (self.num_envs,)
            ):
                shape = (
                    None
                    if actual_time_in_stage_buf is None
                    else tuple(actual_time_in_stage_buf.shape)
                )
                raise RuntimeError(
                    "A2 stage2 completion requires actual_time_in_stage_buf shape "
                    f"({self.num_envs},); got {shape}."
                )
            history_window_in_stage = actual_time_in_stage_buf >= history_length - 1
            return (
                (self.stage_buf == self.STAGE_GRASP)
                & history_window_in_stage
                & all_history_squeezed
            )
        # TODO: check error
        # grasp the door handle
        left_hand_handle_contact_count = (
            self.simulator.object_to_hand_contact_forces[
                :, 0, self.left_hand_indices_tgt_ct_sensor, :
            ].norm(dim=-1)
            > 1
        ).sum(dim=-1)
        left_hand_grasped = left_hand_handle_contact_count >= 4

        right_hand_handle_contact_count = (
            self.simulator.object_to_hand_contact_forces[
                :, 0, self.right_hand_indices_tgt_ct_sensor, :
            ].norm(dim=-1)
            > 1
        ).sum(dim=-1)
        right_hand_grasped = right_hand_handle_contact_count >= 4
        return torch.where(self.door_open_lr < 0, left_hand_grasped, right_hand_grasped)

    def _stage_2_to_3_advance_condition(self):
        # grasp the door handle
        door_opened = self.simulator.scene.articulations["door"].data.joint_pos[:, 0] > 0.174533
        return self._stage_2_to_complete_condition() | door_opened

    def _stage_3_reward_condition(self):
        # keep grasping the door handle
        return self._stage_2_to_3_advance_condition() & self._stage_2_reward_condition()

    def _stage_3_to_4_advance_condition(self):
        # rotate the door handle and open the door
        door_opened = self.simulator.scene.articulations["door"].data.joint_pos[:, 0] > 0.174533
        return door_opened

    def _stage_4_reward_condition(self):
        # keep grasping the door handle
        return self._stage_3_to_4_advance_condition()

    def _stage_4_to_5_advance_condition(self):
        # walk through the door and leave handle up
        walked_through_door = (
            self.simulator.robot_root_states[:, 0] - self.env_origins[:, 0]
        ) > 0.0
        door_opened = self.simulator.scene.articulations["door"].data.joint_pos[:, 0] > 1.0472
        handle_up = self.simulator.scene.articulations["door"].data.joint_pos[:, 1] < 0.2
        return walked_through_door & handle_up & door_opened

    def _stage_5_reward_condition(self):
        # keep walking through the door
        return self._stage_4_to_5_advance_condition()

    def _stage_5_to_complete_condition(self):
        return (self.simulator.robot_root_states[:, 0] - self.env_origins[:, 0]) > 1.5

    def scene_creation_callback(self, simulator):
        target_obj = simulator.task_config.get("target_obj", None)
        if target_obj is None:
            raise RuntimeError("DoorPregrasp scene creation requires task.target_obj.")
        door_frame_unwanted_contact_sensor_config: ContactSensorCfg = ContactSensorCfg(
            prim_path=f"/World/envs/env_.*/{target_obj}/root",
        )

        door_panel_unwanted_contact_sensor_config: ContactSensorCfg = ContactSensorCfg(
            prim_path=f"/World/envs/env_.*/{target_obj}/door_panel",
        )
        simulator.scene.sensors["door_frame_unwanted_contact_sensor"] = ContactSensor(
            door_frame_unwanted_contact_sensor_config
        )
        simulator.scene.sensors["door_panel_unwanted_contact_sensor"] = ContactSensor(
            door_panel_unwanted_contact_sensor_config
        )

        if self._use_a2_base:
            target_sub_prim = simulator.task_config.get(
                "target_obj_transform_sub_prim_path", None
            )
            if target_sub_prim != "grasp_target":
                raise RuntimeError(
                    "A2 Piper gripper-handle transformer requires "
                    "task.target_obj_transform_sub_prim_path='grasp_target'; "
                    f"got {target_sub_prim!r}."
                )
            target_obj_transform_prim_path = (
                f"/World/envs/env_.*/{target_obj}/{target_sub_prim}"
            )
            piper_gripper_handle_frame_transformer_config: FrameTransformerCfg = (
                FrameTransformerCfg(
                    prim_path="/World/envs/env_.*/Robot/arm_body6_to_gripper",
                    source_frame_offset=OffsetCfg(
                        pos=(0.0, 0.0, 0.105),
                        rot=(1.0, 0.0, 0.0, 0.0),
                    ),
                    target_frames=[
                        FrameTransformerCfg.FrameCfg(
                            prim_path=target_obj_transform_prim_path,
                            name="handle",
                            offset=OffsetCfg(
                                pos=(0.0, 0.0, 0.0),
                                rot=(0.5, 0.5, 0.5, 0.5),
                            ),
                        ),
                        FrameTransformerCfg.FrameCfg(
                            prim_path=target_obj_transform_prim_path,
                            name="pregrasp",
                            offset=OffsetCfg(
                                pos=(0.10, 0.0, 0.0),
                                rot=(0.5, 0.5, 0.5, 0.5),
                            ),
                        ),
                    ],
                )
            )
            simulator.scene.sensors[self.A2_GRIPPER_HANDLE_FRAME_TRANSFORMER] = (
                OrderedTargetFrameTransformer(piper_gripper_handle_frame_transformer_config)
            )
            target_contact_sub_prim = simulator.task_config.get(
                "target_obj_contact_sub_prim_path", None
            )
            if target_contact_sub_prim != "door_handle":
                raise RuntimeError(
                    "A2 Piper grasp reward requires "
                    "task.target_obj_contact_sub_prim_path='door_handle'; "
                    f"got {target_contact_sub_prim!r}."
                )
            a2_gripper_handle_contact_sensor_config: ContactSensorCfg = ContactSensorCfg(
                prim_path=f"/World/envs/env_.*/{target_obj}/{target_contact_sub_prim}",
                history_length=self._get_a2_stage2_grasp_contact_history_length(),
                filter_prim_paths_expr=[
                    "/World/envs/env_.*/Robot/arm_body7",
                    "/World/envs/env_.*/Robot/arm_body8",
                ],
            )
            simulator.scene.sensors[self.A2_GRIPPER_HANDLE_CONTACT_SENSOR] = ContactSensor(
                a2_gripper_handle_contact_sensor_config
            )
            return

        head_target_frame_transformer_config: FrameTransformerCfg = FrameTransformerCfg(
            prim_path="/World/envs/env_.*/Robot/head_link",
            target_frames=[
                FrameTransformerCfg.FrameCfg(
                    prim_path=simulator.scene.sensors["left_hand_frame_transformer"]
                    .cfg.target_frames[0]
                    .prim_path
                ),
            ],
        )
        simulator.scene.sensors["head_target_frame_transformer"] = FrameTransformer(
            head_target_frame_transformer_config
        )

    @override
    def _apply_force_in_physics_step(self):
        if self._use_a2_base:
            return A2Base._apply_force_in_physics_step(self)
        return super()._apply_force_in_physics_step()

    def _parse_palm_side_direction(self, palm_side_direction: list[str]) -> torch.Tensor:
        """
        Convert the palm side direction to a quaternion that rotates anything
        expressed in the finger frame to point into the palm.
        """
        output = torch.zeros(len(palm_side_direction), 4, device=self.device)  # wxyz
        for i, direction in enumerate(palm_side_direction):
            if direction == "+x":
                output[i] = torch.tensor([1.0, 0.0, 0.0, 0.0], device=self.device)
            elif direction == "-x":
                output[i] = torch.tensor([0.0, 0.0, 0.0, 1.0], device=self.device)
            elif direction == "+y":
                output[i] = torch.tensor([0.7071068, 0.0, 0.0, 0.7071068], device=self.device)
            elif direction == "-y":
                output[i] = torch.tensor([0.7071068, 0.0, 0.0, -0.7071068], device=self.device)
            elif direction == "+z":
                output[i] = torch.tensor([0.7071068, 0.0, -0.7071068, 0.0], device=self.device)
            elif direction == "-z":
                output[i] = torch.tensor([0.7071068, 0.0, 0.7071068, 0.0], device=self.device)
            else:
                raise ValueError(f"Invalid palm side direction: {direction}")
        return output
