# 本次Worker包源码定向节选

以下按原文件行号摘录；仅用来支撑本轮判断，不是Pro修改后的代码。完整文件仍以输入包与专用分支为准。

## reset中的数值与调用

`gr00t/rl/envs/door/door_open_a2_base.py` L29444–L29468

```text
29444:     def _reset_door_states(self, env_ids):
29445:         randomize_door_init_state = self.config.get("randomize_door_init_state", False)
29446:         self.door_dof_state_buf[:] = 0.0
29447:         if randomize_door_init_state:
29448:             # 33% of the environments to have a different initial state
29449:             rand_env_ids = env_ids[torch.randperm(len(env_ids))[: len(env_ids) // 3]]
29450:             self.door_dof_state_buf[rand_env_ids, 0] = torch_rand_float(
29451:                 0.261799, 1.74533, (len(rand_env_ids), 1), device=self.device
29452:             ).squeeze(-1)
29453:         door_dof_state_dict = {
29454:             "door": (
29455:                 self.door_dof_state_buf,
29456:                 torch.zeros_like(self.door_dof_state_buf),
29457:                 torch.tensor([0, 1, 2], device=self.device, dtype=torch.long),
29458:             )
29459:         }
29460:         self.simulator.set_task_dof_state_tensor(env_ids, door_dof_state_dict)
29461: 
29462:         door_dof_target = torch.zeros(self.num_envs, 3, device=self.device, requires_grad=False)
29463:         door_dof_target[:, 0] = 0.0
29464:         door_dof_target[:, 1] = 15 * torch.pi / 180.0  # tension the door handle
29465:         self.simulator.apply_torques_at_task_dof(env_ids, {"door": door_dof_target})
29466: 
29467:     @override
29468:     def _check_termination(self):
```

## 位置写入与effort目标接口

`gr00t/rl/simulator/isaacsim/isaacsim.py` L2824–L2840

```text
2824:     def set_task_dof_state_tensor(self, set_env_ids, dof_states):
2825:         for name, task_obj in self._task.items():
2826:             if name in dof_states.keys():
2827:                 dof_pos, dof_vel, dof_ids = dof_states[name]
2828:                 task_obj.write_joint_state_to_sim(
2829:                     dof_pos[set_env_ids, :], dof_vel[set_env_ids, :], dof_ids, set_env_ids
2830:                 )
2831: 
2832:     def apply_torques_at_task_dof(self, set_env_ids, torques):
2833:         for name, task_obj in self._task.items():
2834:             if name in torques.keys():
2835:                 if isinstance(task_obj, Articulation):
2836:                     task_obj.set_joint_effort_target(
2837:                         torques[name][set_env_ids, :], env_ids=set_env_ids
2838:                     )
2839:                 else:
2840:                     raise ValueError(f"Task {name} is not an articulation.")
```

## 固定45°和hinge速度项未mask

`gr00t/rl/envs/door/door_open_a2_base.py` L17563–L17581

```text
17563:     def _reward_dont_push_door_handle(self):
17564:         handle_vel_reward = -1.0 * self.simulator.scene.articulations["door"].data.joint_vel[:, 1]
17565:         handle_pos_reward = (
17566:             0.785398 - self.simulator.scene.articulations["door"].data.joint_pos[:, 1]
17567:         ).clamp(min=0.0, max=0.785398) / 0.785398
17568:         return (handle_vel_reward + handle_pos_reward).clamp(max=1.0, min=-1.0)
17569: 
17570:     @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
17571:     def _reward_push_door_hinge(self):
17572:         hinge_vel_reward = self.simulator.scene.articulations["door"].data.joint_vel[:, 0] * 10
17573:         hinge_pos_reward = (
17574:             self.simulator.scene.articulations["door"]
17575:             .data.joint_pos[:, 0]
17576:             .clamp(min=0.0, max=1.5708)
17577:             / 1.5708
17578:         )
17579:         if self._use_a2_base:
17580:             hinge_pos_reward = hinge_pos_reward * self._get_a2_stage34_hold_income_mask().float()
17581:         return (hinge_vel_reward + hinge_pos_reward).clamp(max=1.0, min=-1.0)
```

## hold_and_drive实际覆盖路径

`gr00t/rl/envs/door/door_open_a2_base.py` L18385–L18416

```text
18385:                 self._get_a2_stage3_unlatch_handle_position_norm()
18386:             ),
18387:             unlatch_near_closed_hinge_threshold=(
18388:                 self._get_a2_stage3_unlatch_near_closed_hinge_threshold()
18389:             ),
18390:             hold_and_drive_velocity_norm=(
18391:                 self._get_a2_stage3_stage4_hold_and_drive_velocity_norm()
18392:             ),
18393:         )
18394:         components["hold_and_drive"] = a2_corridor_hold_and_drive_component(
18395:             self._get_a2_door_income_hold_mask(),
18396:             door_joint_vel[:, 0],
18397:             self._get_a2_corridor_mask(),
18398:             self._get_a2_stage3_stage4_hold_and_drive_velocity_norm(),
18399:             self._get_a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor(),
18400:             self._get_a2_corridor_enabled(),
18401:         )
18402:         return components
18403: 
18404:     def _get_door_frame_contact_force_per_env(self, context):
18405:         sensor = self.simulator.scene.sensors["door_frame_unwanted_contact_sensor"]
18406:         net_forces_w = getattr(sensor.data, "net_forces_w", None)
18407:         if (
18408:             net_forces_w is None
18409:             or not torch.is_tensor(net_forces_w)
18410:             or net_forces_w.ndim != 3
18411:             or net_forces_w.shape[0] != self.num_envs
18412:             or net_forces_w.shape[2] != 3
18413:         ):
18414:             shape = None if net_forces_w is None else tuple(net_forces_w.shape)
18415:             raise RuntimeError(
18416:                 f"{context} requires door_frame_unwanted_contact_sensor.net_forces_w "
```

## Stage4正挤压力残余

`gr00t/rl/envs/door/door_open_a2_base.py` L16816–L16854

```text
16816:     @StagedTaskBase.effective_in_stage([STAGE_PREGRASP, STAGE_GRASP, STAGE_OPEN, STAGE_SWING])
16817:     def _reward_grasp(self):
16818:         if self._use_a2_base:
16819:             forces_w = self._get_a2_gripper_handle_contact_forces()
16820:             data = self._get_a2_gripper_handle_frame_transformer().data
16821:             source_quat_w = getattr(data, "source_quat_w", None)
16822:             if (
16823:                 source_quat_w is None
16824:                 or source_quat_w.ndim != 2
16825:                 or source_quat_w.shape != (self.num_envs, 4)
16826:             ):
16827:                 shape = None if source_quat_w is None else tuple(source_quat_w.shape)
16828:                 raise RuntimeError(
16829:                     "A2 grasp reward requires source_quat_w shape "
16830:                     f"({self.num_envs}, 4); got {shape}."
16831:                 )
16832: 
16833:             source_quat = source_quat_w[:, None, :].expand(-1, 2, -1).reshape(-1, 4)
16834:             forces_source = quat_apply(
16835:                 quat_inv(source_quat), forces_w.reshape(-1, 3)
16836:             ).reshape(self.num_envs, 2, 3)
16837: 
16838:             axis_force = torch.abs(forces_source[:, :, 1])
16839:             off_axis_force = torch.abs(forces_source[:, :, 0]) + torch.abs(
16840:                 forces_source[:, :, 2]
16841:             )
16842:             per_body = (axis_force - off_axis_force).clamp(min=-10.0, max=10.0)
16843:             raw_reward = per_body.min(dim=-1).values
16844: 
16845:             pregrasp_mask = self.stage_buf == DoorPregrasp.STAGE_PREGRASP
16846:             contact_mag = torch.linalg.norm(forces_w, dim=-1).sum(dim=-1).clamp(max=10.0)
16847:             raw_reward[pregrasp_mask] = -contact_mag[pregrasp_mask]
16848:             return raw_reward
16849:         left_contact_forces = self.simulator.object_to_hand_contact_forces[
16850:             :, 0, self.left_hand_indices_tgt_ct_sensor, :
16851:         ][:, self.left_hand_indices_convert, :]
16852:         left_contact_forces_flattened = left_contact_forces.reshape(-1, 3)
16853:         left_hand_rot = self.simulator._rigid_body_rot[:, self.left_hand_indices, :][
16854:             :, :, [3, 0, 1, 2]
```

## POST hook及early return

`gr00t/rl/envs/door/door_open_a2_base.py` L9534–L9543

```text
9534:     def _post_physics_substep(self, sim_sub_t: int) -> None:
9535:         """Capture one GPU-local frame after each real IsaacLab physics step."""
9536:         super()._post_physics_substep(sim_sub_t)
9537:         if not getattr(self, "_a2_v23_temporal_evidence_enabled", False):
9538:             return
9539:         decimation = int(self.config.simulator.config.sim.control_decimation)
9540:         if isinstance(sim_sub_t, bool) or not isinstance(sim_sub_t, int) or not 0 <= sim_sub_t < decimation:
9541:             raise RuntimeError(f"temporal physics substep index must be within 0..{decimation - 1}.")
9542:         if sim_sub_t == 0:
9543:             if any(self._a2_v23_temporal_substep_frames):
```

