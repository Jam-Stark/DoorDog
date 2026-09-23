# R2源码证据摘录
这些是直接从冻结输入提取的相关行，不代表云端运行了原项目。原有注释中历史名称/状态不覆盖实际config。

## gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml：1–70

```text
1: # @package _global_
2: 
3: # Be careful when using _raw, history
4: obs:
5:   obs_dict:
6:     actor_obs: [
7:       dof_pos,
8:       relative_to_door,
9:       dof_vel,
10:       actions,
11:       projected_gravity,
12:       door_dof_pos,
13:       base_lin_vel,
14:       base_ang_vel,
15:       hand_force,
16:       stage,
17:       privileged_door_info,
18:       delta_actions,
19:       gripper_handle_transform,
20:       a2_base_command_raw,
21: 
22:       a2_base_command
23:     ]
24: 
25:     critic_obs: [
26:       dof_pos,
27:       relative_to_door,
28:       dof_vel,
29:       actions,
30:       projected_gravity,
31:       door_dof_pos,
32:       base_lin_vel,
33:       base_ang_vel,
34:       hand_force,
35:       stage,
36:       privileged_door_info,
37:       delta_actions,
38:       gripper_handle_transform,
39:       a2_base_command_raw,
40: 
41:       transition,
42:       complete,
43: 
44:       time_in_stage,
45:       actual_time_in_stage,
46:       total_time,
47: 
48:       a2_base_command
49:     ]
50: 
51:     homie_obs: [
52:       a_history_homie,
53:       a2_base_command,
54:       c_homie_base_ang_vel,
55:       d_homie_projected_gravity,
56:       # homie_torso_ang_vel,
57:       # homie_torso_projected_gravity,
58:       e_homie_dof_pos,
59:       f_homie_dof_vel,
60:       g_homie_body_actions,
61:       # homie_clock_inputs,
62:     ]
63: 
64:     a2_base_obs: [
65:       a2_base_obs
66:     ]
67: 
68:   # define those coumpounds in obs_dict, for example, you can define different long/short history with different length
69:   obs_auxiliary: 
70:     history_long: {
```

## gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml：1–70

```text
1: # @package _global_
2: 
3: # A2+Piper Phase 2 observation contract.  Lists are intentionally ordered;
4: # `pre_process_config` preserves this order when flattening each public view.
5: obs:
6:   obs_dict:
7:     # Deployable student actor: 3 + 3 + 20 + 20 + 19 + 6 + 5 + 5 = 81D.
8:     actor_obs:
9:       - base_ang_vel
10:       - projected_gravity
11:       - a2_student_dof_pos
12:       - a2_student_dof_vel
13:       - actions
14:       - delta_actions
15:       - a2_base_command
16:       - a2_base_command_raw
17: 
18:     vision_obs:
19:       - rgb_image
20: 
21:     # Privileged A2 Teacher PPO actor input: exact active A2 term order = 133D.
22:     teacher_obs:
23:       - dof_pos
24:       - relative_to_door
25:       - dof_vel
26:       - actions
27:       - projected_gravity
28:       - door_dof_pos
29:       - base_lin_vel
30:       - base_ang_vel
31:       - hand_force
32:       - stage
33:       - privileged_door_info
34:       - delta_actions
35:       - gripper_handle_transform
36:       - a2_base_command_raw
37:       - a2_base_command
38: 
39:     # The PPO machinery only needs critic_obs when a critic is instantiated.
40:     # It is deliberately kept privileged and separate from actor_obs.
41:     critic_obs:
42:       - dof_pos
43:       - relative_to_door
44:       - dof_vel
45:       - actions
46:       - projected_gravity
47:       - door_dof_pos
48:       - base_lin_vel
49:       - base_ang_vel
50:       - hand_force
51:       - stage
52:       - privileged_door_info
53:       - delta_actions
54:       - gripper_handle_transform
55:       - a2_base_command_raw
56:       - transition
57:       - complete
58:       - time_in_stage
59:       - actual_time_in_stage
60:       - total_time
61:       - a2_base_command
62: 
63:     # Frozen A2_Base consumes this 30-frame x 54D contract only.
64:     a2_base_obs:
65:       - a2_base_obs
66: 
67:   # Keep this key because A2_Base initializes its history buffers from the
68:   # canonical observation route; it is not exposed as a student observation.
69:   homie_history_length: 5
70: 
```

## gr00t/rl/envs/door/door_open_a2_base.py：2214–2245

```text
2214: def a2_stage34_hold_income_mask(
2215:     stage_buf: torch.Tensor,
2216:     release_gate: torch.Tensor,
2217:     stage_open: int,
2218:     stage_swing: int,
2219: ) -> torch.Tensor:
2220:     """Return the stage3/4 hold-income mask with an episode-latched release gate."""
2221:     if (
2222:         not torch.is_tensor(stage_buf)
2223:         or stage_buf.ndim != 1
2224:         or stage_buf.dtype != torch.long
2225:         or not torch.is_tensor(release_gate)
2226:         or release_gate.shape != stage_buf.shape
2227:         or release_gate.dtype != torch.bool
2228:         or release_gate.device != stage_buf.device
2229:         or isinstance(stage_open, bool)
2230:         or not isinstance(stage_open, int)
2231:         or isinstance(stage_swing, bool)
2232:         or not isinstance(stage_swing, int)
2233:         or stage_open == stage_swing
2234:     ):
2235:         raise ValueError(
2236:             "A2 stage3/4 hold-income mask requires a long stage vector, a matching "
2237:             "bool release-gate vector, and distinct integer stage values."
2238:         )
2239:     return (stage_buf == stage_open) | ((stage_buf == stage_swing) & ~release_gate)
2240: 
2241: def a2_update_stage4_release_and_root_latches(
2242:     release_gate: torch.Tensor,
2243:     root_x_ever_crossed: torch.Tensor,
2244:     stage_buf: torch.Tensor,
2245:     hinge_pos: torch.Tensor,
```

## gr00t/rl/envs/door/door_open_a2_base.py：3880–3953

```text
3880:     stiffness: torch.Tensor,
3881:     damping: torch.Tensor,
3882:     effort_limit: torch.Tensor,
3883: ):
3884:     expected_shape = joint_pos.shape
3885:     fields = (joint_vel, joint_pos_target, stiffness, damping, effort_limit)
3886:     if not torch.is_tensor(joint_pos) or any(
3887:         not torch.is_tensor(field) or field.shape != expected_shape for field in fields
3888:     ):
3889:         raise ValueError("PD effort estimate inputs must be tensors with identical shapes.")
3890:     if torch.any(effort_limit <= 0.0):
3891:         raise ValueError("PD effort limits must be positive.")
3892:     unclipped = stiffness * (joint_pos_target - joint_pos) - damping * joint_vel
3893:     clipped = torch.clamp(unclipped, min=-effort_limit, max=effort_limit)
3894:     saturated = torch.abs(unclipped) > effort_limit
3895:     return unclipped, clipped, saturated
3896: 
3897: 
3898: def a2_hold_apply_source_offset_to_jacobian(
3899:     jacobian_root: torch.Tensor, source_offset_pos: torch.Tensor
3900: ) -> torch.Tensor:
3901:     """Apply the same body-offset correction as IsaacLab DifferentialIKAction."""
3902:     if not torch.is_tensor(jacobian_root) or jacobian_root.ndim != 3 or jacobian_root.shape[1] != 6:
3903:         raise ValueError("jacobian_root must have shape (N, 6, J).")
3904:     if (
3905:         not torch.is_tensor(source_offset_pos)
3906:         or source_offset_pos.shape != (jacobian_root.shape[0], 3)
3907:         or source_offset_pos.device != jacobian_root.device
3908:     ):
3909:         raise ValueError("source_offset_pos must have shape (N, 3) on the Jacobian device.")
3910:     corrected = jacobian_root.clone()
3911:     corrected[:, 0:3, :] += torch.bmm(
3912:         -skew_symmetric_matrix(source_offset_pos), corrected[:, 3:, :]
3913:     )
3914:     return corrected
3915: 
3916: 
3917: def a2_hold_rotate_jacobian_to_root(
3918:     jacobian_w: torch.Tensor, root_quat_w: torch.Tensor
3919: ) -> torch.Tensor:
3920:     if not torch.is_tensor(jacobian_w) or jacobian_w.ndim != 3 or jacobian_w.shape[1] != 6:
3921:         raise ValueError("jacobian_w must have shape (N, 6, J).")
3922:     if (
3923:         not torch.is_tensor(root_quat_w)
3924:         or root_quat_w.shape != (jacobian_w.shape[0], 4)
3925:         or root_quat_w.device != jacobian_w.device
3926:     ):
3927:         raise ValueError("root_quat_w must have shape (N, 4) on the Jacobian device.")
3928:     rotation = matrix_from_quat(quat_inv(root_quat_w))
3929:     jacobian_root = jacobian_w.clone()
3930:     jacobian_root[:, :3] = torch.bmm(rotation, jacobian_w[:, :3])
3931:     jacobian_root[:, 3:] = torch.bmm(rotation, jacobian_w[:, 3:])
3932:     return jacobian_root
3933: 
3934: 
3935: def a2_hold_absolute_target_to_cumulative_action(
3936:     q_des: torch.Tensor,
3937:     q_default: torch.Tensor,
3938:     d_prev: torch.Tensor,
3939:     *,
3940:     robot_action_scale: float = 0.25,
3941:     delta_action_scale: float = 0.3,
3942: ):
3943:     if not all(torch.is_tensor(value) for value in (q_des, q_default, d_prev)):
3944:         raise ValueError("q_des, q_default and d_prev must be tensors.")
3945:     if q_des.shape != q_default.shape or q_des.shape != d_prev.shape:
3946:         raise ValueError("q_des, q_default and d_prev must have identical shapes.")
3947:     if robot_action_scale != 0.25 or delta_action_scale != 0.3:
3948:         raise ValueError(
3949:             "A2 hold oracle cumulative conversion requires action_scale=0.25 and delta_scale=0.3."
3950:         )
3951:     d_des = (q_des - q_default) / robot_action_scale
3952:     raw_action = (d_des - d_prev) / delta_action_scale
3953:     return d_des, raw_action
```

## gr00t/rl/envs/door/door_open_a2_base.py：15964–16011

```text
15964:     def _reward_penalty_upper_body_non_gripper_deviation_l1(self):
15965:         """A2 stage0 PASS: Piper arm_j1..j6 default-pose shaping."""
15966:         # Exclude arm_j7/arm_j8 so gripper open/close does not affect arm pose shaping.
15967:         if self._use_a2_base:
15968:             target_pos = self._get_a2_arm_default_dof_pos()
15969:         else:
15970:             target_pos = self.default_dof_pos[:, self._upper_non_gripper_dof_idx]
15971:         return torch.abs(
15972:             self.simulator.dof_pos[:, self._upper_non_gripper_dof_idx]
15973:             - target_pos
15974:         ).sum(dim=-1)
15975: 
15976:     @StagedTaskBase.effective_in_stage(STAGE_SWING)
15977:     def _reward_penalty_a2_stage4_arm_default_pose_l1(self):
15978:         if not self._use_a2_base:
15979:             raise RuntimeError(
15980:                 "penalty_a2_stage4_arm_default_pose_l1 is only defined for A2 Piper configs."
15981:             )
15982:         target_pos = self._get_a2_arm_default_dof_pos()
15983:         dof_pos = getattr(self.simulator, "dof_pos", None)
15984:         max_arm_dof_index = max(self._upper_non_gripper_dof_idx)
15985:         if (
15986:             dof_pos is None
15987:             or not torch.is_tensor(dof_pos)
15988:             or dof_pos.ndim != 2
15989:             or dof_pos.shape[0] != self.num_envs
15990:             or dof_pos.shape[1] <= max_arm_dof_index
15991:         ):
15992:             shape = None if dof_pos is None else tuple(dof_pos.shape)
15993:             raise RuntimeError(
15994:                 "penalty_a2_stage4_arm_default_pose_l1 requires simulator.dof_pos "
15995:                 f"shape ({self.num_envs}, >{max_arm_dof_index}); got {shape}."
15996:             )
15997:         arm_pos = dof_pos[:, self._upper_non_gripper_dof_idx]
15998:         if tuple(arm_pos.shape) != (self.num_envs, 6):
15999:             raise RuntimeError(
16000:                 "penalty_a2_stage4_arm_default_pose_l1 expects arm_j1..arm_j6 "
16001:                 f"shape ({self.num_envs}, 6); got {tuple(arm_pos.shape)}."
16002:             )
16003:         penalty = torch.abs(arm_pos - target_pos).sum(dim=-1)
16004:         if self.config.get("a2_stage4_arm_default_pose_release_gated", False):
16005:             masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
16006:                 "A2 stage4 post-release default pose"
16007:             )
16008:             penalty = penalty * (self._a2_stage4_release_gate & ~masks["both_contact"])
16009:         return penalty
16010: 
16011:     def _reward_penalty_a2_wrist_motion_l2(self):
```

## gr00t/rl/envs/door/door_open_a2_base.py：16420–16460

```text
16420:     def _reward_grasp_target_distance(self):
16421:         if self._use_a2_base:
16422:             reward = self._get_a2_grasp_target_distance_reward("A2 grasp_target_distance")
16423:             return torch.where(
16424:                 self.stage_buf == self.STAGE_SWING,
16425:                 torch.zeros_like(reward),
16426:                 reward,
16427:             )
16428:         grasp_target = self._compute_grasp_target()
16429: 
16430:         left_hand_pos = self.simulator._rigid_body_pos[:, self.left_palm_idx, :]
16431:         right_hand_pos = self.simulator._rigid_body_pos[:, self.right_palm_idx, :]
16432: 
16433:         left_hand_pos_to_grasp_target = grasp_target - left_hand_pos
16434:         right_hand_pos_to_grasp_target = grasp_target - right_hand_pos
16435: 
16436:         left_hand_pos_to_grasp_target_norm = torch.norm(left_hand_pos_to_grasp_target, dim=-1)
16437:         right_hand_pos_to_grasp_target_norm = torch.norm(right_hand_pos_to_grasp_target, dim=-1)
16438: 
16439:         return self._tracking_reward_util(
16440:             torch.where(
16441:                 self.door_open_lr < 0,
16442:                 left_hand_pos_to_grasp_target_norm,
16443:                 right_hand_pos_to_grasp_target_norm,
16444:             ),
16445:             std=0.1,
16446:             target=0.0,
16447:             scale=1.0,
16448:             offset=0.0,
16449:         )
16450: 
16451:     @StagedTaskBase.effective_in_stage(STAGE_SWING)
16452:     def _reward_a2_stage4_grasp_target_distance_mild(self):
16453:         if not self._use_a2_base:
16454:             raise RuntimeError(
16455:                 "a2_stage4_grasp_target_distance_mild is only defined for A2 Piper configs."
16456:             )
16457:         reward = self._get_a2_grasp_target_distance_reward(
16458:             "A2 stage4 mild grasp_target_distance"
16459:         )
16460:         return reward * self._get_a2_stage34_hold_income_mask().float()
```

## gr00t/rl/envs/door/door_open_a2_base.py：17589–17609

```text
17589: 
17590:     @StagedTaskBase.effective_in_stage([STAGE_SWING, STAGE_THROUGH])
17591:     def _reward_dont_push_door_handle(self):
17592:         handle_vel_reward = -1.0 * self.simulator.scene.articulations["door"].data.joint_vel[:, 1]
17593:         handle_pos_reward = (
17594:             0.785398 - self.simulator.scene.articulations["door"].data.joint_pos[:, 1]
17595:         ).clamp(min=0.0, max=0.785398) / 0.785398
17596:         return (handle_vel_reward + handle_pos_reward).clamp(max=1.0, min=-1.0)
17597: 
17598:     @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
17599:     def _reward_push_door_hinge(self):
17600:         hinge_vel_reward = self.simulator.scene.articulations["door"].data.joint_vel[:, 0] * 10
17601:         hinge_pos_reward = (
17602:             self.simulator.scene.articulations["door"]
17603:             .data.joint_pos[:, 0]
17604:             .clamp(min=0.0, max=1.5708)
17605:             / 1.5708
17606:         )
17607:         if self._use_a2_base:
17608:             hinge_pos_reward = hinge_pos_reward * self._get_a2_stage34_hold_income_mask().float()
17609:         return (hinge_vel_reward + hinge_pos_reward).clamp(max=1.0, min=-1.0)
```

## gr00t/rl/envs/door/door_open_a2_base.py：18558–18639

```text
18558:     def _get_a2_stage2_contact_squeeze_masks(self, forces_w, context):
18559:         forces_source = self._get_a2_stage2_forces_source(forces_w, context)
18560:         contact_force = torch.linalg.norm(forces_w, dim=-1)
18561:         contact_threshold = self._get_a2_stage2_contact_force_threshold()
18562:         squeeze_min = self._get_a2_stage2_squeeze_force_min()
18563:         squeeze_max = self._get_a2_stage2_squeeze_force_max()
18564:         over_force_threshold = self._get_a2_stage2_over_force_threshold()
18565: 
18566:         contacting = contact_force > contact_threshold
18567:         squeeze_y = forces_source[..., :, 1]
18568:         squeeze_abs = torch.abs(squeeze_y)
18569:         squeeze_in_window = (squeeze_abs >= squeeze_min) & (squeeze_abs <= squeeze_max)
18570:         both_contact = torch.all(contacting, dim=-1)
18571:         single_contact = contacting.sum(dim=-1) == 1
18572:         opposite_squeeze = squeeze_y[..., 0] * squeeze_y[..., 1] < 0.0
18573:         sufficient_squeeze = torch.all(squeeze_abs > squeeze_min, dim=-1)
18574:         squeeze_window = (
18575:             both_contact
18576:             & opposite_squeeze
18577:             & torch.all(squeeze_in_window, dim=-1)
18578:         )
18579:         over_force = torch.any(contact_force > over_force_threshold, dim=-1)
18580:         return {
18581:             "contact_force": contact_force,
18582:             "contacting": contacting,
18583:             "single_contact": single_contact,
18584:             "single_contact_arm_body7": contacting[..., 0] & ~contacting[..., 1],
18585:             "single_contact_arm_body8": ~contacting[..., 0] & contacting[..., 1],
18586:             "both_contact": both_contact,
18587:             "squeeze_y": squeeze_y,
18588:             "sufficient_squeeze": sufficient_squeeze,
18589:             "opposite_squeeze": opposite_squeeze,
18590:             "squeeze_window": squeeze_window,
18591:             "over_force": over_force,
18592:         }
18593: 
18594:     def _get_a2_stage2_contact_stability_mask(self):
18595:         gate_mode = self._get_a2_grasp_gate_mode()
18596:         if gate_mode == self.A2_GRASP_GATE_MODE_CONTROL_STREAK:
18597:             streak = self._get_a2_grasp_control_streak_buffer(
18598:                 "_a2_stage2_squeeze_streak",
18599:                 "A2 stage2 contact stability",
18600:             )
18601:             return (self.stage_buf == self.STAGE_GRASP) & (
18602:                 streak >= self._get_a2_grasp_streak_control_steps()
18603:             )
18604: 
18605:         history_length = self._get_a2_stage2_grasp_contact_history_length()
18606:         masks = self._get_a2_stage2_contact_squeeze_masks(
18607:             self._get_a2_gripper_handle_contact_force_history(),
18608:             "A2 stage2 contact stability",
18609:         )
18610:         both_contact_history = masks["both_contact"]
18611:         if tuple(both_contact_history.shape) != (self.num_envs, history_length):
18612:             raise RuntimeError(
18613:                 "A2 stage2 contact stability requires both_contact history shape "
18614:                 f"({self.num_envs}, {history_length}); got "
18615:                 f"{tuple(both_contact_history.shape)}."
18616:             )
18617: 
18618:         actual_time_in_stage_buf = getattr(self, "actual_time_in_stage_buf", None)
18619:         if (
18620:             actual_time_in_stage_buf is None
18621:             or not torch.is_tensor(actual_time_in_stage_buf)
18622:             or tuple(actual_time_in_stage_buf.shape) != (self.num_envs,)
18623:         ):
18624:             shape = (
18625:                 None
18626:                 if actual_time_in_stage_buf is None
18627:                 else tuple(actual_time_in_stage_buf.shape)
18628:             )
18629:             raise RuntimeError(
18630:                 "A2 stage2 contact stability requires actual_time_in_stage_buf shape "
18631:                 f"({self.num_envs},); got {shape}."
18632:             )
18633:         history_window_in_stage = actual_time_in_stage_buf >= history_length - 1
18634:         return history_window_in_stage & torch.all(both_contact_history, dim=-1)
18635: 
18636:     def _get_a2_stage3_stage4_contact_squeeze_masks(self, context):
18637:         return self._get_a2_stage2_contact_squeeze_masks(
18638:             self._get_a2_gripper_handle_contact_forces(),
18639:             context,
```

## gr00t/rl/envs/door/door_open_a2_base.py：28498–28545

```text
28498:     def _get_obs_hand_force(self):
28499:         if self._use_a2_base:
28500:             if not hasattr(self, "_a2_gripper_force_body_indices"):
28501:                 raise RuntimeError(
28502:                     "A2 hand_force requires name-based gripper body indices for "
28503:                     "arm_body7 and arm_body8."
28504:                 )
28505:             hand_force = self.simulator.contact_forces[:, self._a2_gripper_force_body_indices, :]
28506:             result = hand_force.reshape(hand_force.shape[0], 6)
28507:             if not self._a2_v26_4_side_canonicalization_enabled():
28508:                 return result
28509:             return a2_v26_4_canonicalize_hand_force(result, self._a2_v26_4_right_mask())
28510:         left_hand_force = self.simulator.contact_forces[:, self.left_hand_indices, :]
28511:         right_hand_force = self.simulator.contact_forces[:, self.right_hand_indices, :]
28512:         return torch.cat(
28513:             [
28514:                 left_hand_force.reshape(left_hand_force.shape[0], -1),
28515:                 right_hand_force.reshape(right_hand_force.shape[0], -1),
28516:             ],
28517:             dim=-1,
28518:         )
28519: 
28520:     def _get_obs_privileged_door_info(self):
28521:         left = (self.door_open_lr == 1.0).to(dtype=self.door_width.dtype)
28522:         right = (self.door_open_lr == -1.0).to(dtype=self.door_width.dtype)
28523:         return torch.stack(
28524:             [
28525:                 self.door_width,
28526:                 self.door_height,
28527:                 self.door_handle_height,
28528:                 self.door_handle_width,
28529:                 self.door_weight / 100.0,
28530:                 left,
28531:                 right,
28532:                 self.door_open_io,
28533:             ],
28534:             dim=1,
28535:         )
28536: 
28537:     def _get_obs_door_dof_pos(self):
28538:         return self.simulator.get_task_dof_pos("door")[:, :2]
28539: 
28540:     def _get_a2_student_dof_indices(self):
28541:         """Resolve the deployable A2 DOF order from names and validate it."""
28542:         configured = tuple(self.config.robot.dof_names)
28543:         actual = tuple(self.simulator.dof_names)
28544:         if len(configured) != 20 or len(set(configured)) != 20:
28545:             raise RuntimeError(
```

## gr00t/rl/envs/base_task/a2_base.py：1174–1220

```text
1174:         self._a2_gripper_primitive_raw[:] = gripper_primitive
1175:         leg_actions = actions[:, -self._a2_leg_action_dim :]
1176: 
1177:         final_actions = torch.zeros(
1178:             self.num_envs, self.num_dof, device=self.device, dtype=actions.dtype
1179:         )
1180:         final_actions[:, self._a2_leg_sim_indices] = leg_actions
1181:         final_actions[:, self._a2_arm_dof_indices] = arm_actions
1182: 
1183:         gripper_target = torch.where(
1184:             gripper_primitive > 0.0,
1185:             self._a2_gripper_open_target[None, :],
1186:             self._a2_gripper_close_target[None, :],
1187:         )
1188:         gripper_raw = (
1189:             gripper_target - self.default_dof_pos[:, self._a2_gripper_dof_indices]
1190:         ) / self.config.robot.control.action_scale
1191:         final_actions[:, self._a2_gripper_dof_indices] = gripper_raw
1192: 
1193:         scaled_base_command_raw = torch.cat(
1194:             [
1195:                 raw_base_action[:, :3] * self._a2_base_command_scale,
1196:                 raw_base_action[:, 3:5] * self._a2_body_pitch_roll_scale,
1197:             ],
1198:             dim=-1,
1199:         )
1200:         scaled_base_command = torch.cat(
1201:             [
1202:                 scaled_base_command_raw[:, :3],
1203:                 raw_base_action[:, 3:5].clamp(-1.0, 1.0) * self._a2_body_pitch_roll_scale,
1204:             ],
1205:             dim=-1,
1206:         )
1207:         if self._clip_homie_command:
1208:             scaled_base_command = torch.clamp(
1209:                 scaled_base_command,
1210:                 self._a2_base_command_low_thres.to(dtype=actions.dtype),
1211:                 self._a2_base_command_high_thres.to(dtype=actions.dtype),
1212:             )
1213: 
1214:         self._a2_base_command_raw[:] = raw_base_action
1215:         self._homie_commands[:, :] = 0.0
1216:         self._homie_commands_unclipped[:, :] = 0.0
1217:         self._homie_commands_unclipped[:, :5] = scaled_base_command_raw
1218:         self._homie_commands[:, :5] = scaled_base_command
1219:         self._homie_actions[:] = leg_actions
1220:         self._last_a2_leg_actions[:] = leg_actions
```

## gr00t/rl/envs/legged_base_task/legged_robot_base.py：1142–1159

```text
1142:     def _apply_force_in_physics_step(self):
1143:         if self.config.simulator.config.name == "isaacgym":
1144:             self.torques = self._compute_torques(self.actions_after_delay).view(self.torques.shape)
1145:             self.simulator.apply_torques_at_dof(self.torques)
1146:         elif self.config.simulator.config.name == "isaacsim":
1147:             self.torques = self._compute_torques(self.actions_after_delay).view(
1148:                 self.torques.shape
1149:             )  # When using implicit PD
1150:             actions_scaled = self.actions_after_delay * self.config.robot.control.action_scale
1151:             jpos_target = actions_scaled + self.default_dof_pos
1152:             # jpos_target *= 0.
1153:             self.simulator._robot.set_joint_position_target(
1154:                 jpos_target, joint_ids=self.simulator.dof_ids
1155:             )
1156:         else:
1157:             raise NotImplementedError(
1158:                 f"Simulator {self.config.simulator.config.name} not implemented"
1159:             )
```

## gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py：340–450

```text
340:     def _teacher_actions(self, obs_dict):
341:         actions = self.ref_model.act_inference(obs_dict=deepcopy(obs_dict))
342:         _validate_floating_tensor("teacher_actions", actions, A2_STUDENT_ACTION_DIM)
343:         if actions.shape[:-1] != obs_dict["teacher_obs"].shape[:-1]:
344:             raise ValueError("Teacher action leading shape does not match teacher_obs")
345:         if actions.device != obs_dict["teacher_obs"].device:
346:             raise ValueError("Teacher actions device must match teacher_obs")
347:         return actions
348: 
349:     def policy_step(
350:         self,
351:         policy_model,
352:         auxiliary_model_a,
353:         auxiliary_model_b,
354:         obs_dict,
355:         cur_dones=None,
356:         store_hidden_states=True,
357:     ):
358:         if auxiliary_model_a is not None or auxiliary_model_b is not None:
359:             raise ValueError("A2 Student trainer does not support auxiliary policy models")
360:         self._validate_rollout_obs(obs_dict, require_teacher=True)
361:         teacher_actions = self._teacher_actions(obs_dict)
362:         actor_obs_dict = {"actor_obs": obs_dict["actor_obs"], "vision_obs": obs_dict["vision_obs"]}
363:         if cur_dones is None:
364:             dones = self.storage.query_key("dones").to(self.accelerator.device)[: self.storage.step + 1]
365:             episode_attnmask = compute_episode_attnmask(dones.squeeze(-1).transpose(0, 1))
366:         else:
367:             episode_attnmask = None
368:         actor_hidden_states = (
369:             policy_model.get_hidden_states()
370:             if store_hidden_states and getattr(policy_model, "is_recurrent", False)
371:             else None
372:         )
373:         student_state = policy_model.rollout(
374:             obs_dict=actor_obs_dict, episode_attnmask=episode_attnmask, cur_dones=cur_dones
375:         )
376:         high_level_actions = student_state["actions"]
377:         high_level_mean = student_state["action_mean"]
378:         high_level_sigma = student_state["action_sigma"]
379:         _validate_floating_tensor("student_actions", high_level_actions, A2_STUDENT_ACTION_DIM)
380:         _validate_floating_tensor("student_action_mean", high_level_mean, A2_STUDENT_ACTION_DIM)
381:         _validate_floating_tensor("student_action_sigma", high_level_sigma, A2_STUDENT_ACTION_DIM)
382:         if any(
383:             tensor.device != obs_dict["actor_obs"].device
384:             for tensor in (high_level_actions, high_level_mean, high_level_sigma, teacher_actions)
385:         ):
386:             raise ValueError("Teacher/student action tensors must match observation device")
387:         if high_level_actions.shape != teacher_actions.shape:
388:             raise ValueError("Student and Teacher high-level action shapes differ")
389:         selected_high = high_level_actions
390:         selected_mean = high_level_mean
391:         if self.config.get("enforce_teacher_rollout", False):
392:             ratio = float(self.config.get("ratio_teacher_rollout", 1.0))
393:             if not 0.0 <= ratio <= 1.0:
394:                 raise ValueError(f"ratio_teacher_rollout must be within [0,1], got {ratio}")
395:             count = int(selected_high.shape[0] * ratio)
396:             selected_high = selected_high.clone()
397:             selected_mean = selected_mean.clone()
398:             selected_high[:count] = teacher_actions[:count]
399:             selected_mean[:count] = teacher_actions[:count]
400:         leg_actions = self.unwrapped_model._a2_base_actions(obs_dict, selected_high)
401:         if not torch.is_tensor(leg_actions) or leg_actions.device != obs_dict["actor_obs"].device:
402:             raise ValueError("A2_Base leg actions must be a tensor on the observation device")
403:         actions = compose_a2_rollout_action(selected_high, leg_actions)
404:         action_mean = compose_a2_rollout_action(selected_mean, leg_actions)
405:         action_sigma = compose_a2_rollout_action(high_level_sigma, torch.zeros_like(leg_actions))
406:         result = {
407:             "actions": actions,
408:             "action_mean": action_mean,
409:             "action_sigma": action_sigma,
410:             "actions_log_prob": policy_model.get_actions_log_prob(high_level_actions).unsqueeze(1),
411:             "gt_actions": teacher_actions,
412:         }
413:         if actor_hidden_states is not None:
414:             result["hidden_states"] = (actor_hidden_states, None)
415:         return result
416: 
417:     def _process_env_step(self, rewards, dones, infos):
418:         # Invoke only the A2 PPO student/value reset and bookkeeping path.  The
419:         # generic DAgger helper also resets Teacher state with a swallowed
420:         # exception, so it must not be called here.
421:         A2TRLPPOTrainer._process_env_step(self, rewards, dones, infos)
422:         if self.ref_model is None or not hasattr(self.ref_model, "reset"):
423:             raise RuntimeError("A2 recurrent Teacher must expose reset(dones)")
424:         self.ref_model.reset(dones)
425: 
426:     def _rollout_step(self, model, obs_dict):
427:         if self.ref_model is None or not hasattr(self.ref_model, "init_rollout"):
428:             raise RuntimeError("A2 recurrent Teacher must expose init_rollout()")
429:         if not hasattr(self.ref_model, "clear_rollout"):
430:             raise RuntimeError("A2 recurrent Teacher must expose clear_rollout()")
431:         self.ref_model.init_rollout()
432:         try:
433:             return A2TRLPPOTrainer._rollout_step(self, model, obs_dict)
434:         finally:
435:             self.ref_model.clear_rollout()
436: 
437:     def _compute_dagger_bc_loss(self, forward_results, mb_rollout_data):
438:         policy_results = forward_results["policy_results"]
439:         predicted = policy_results.get("action_mean")
440:         target = mb_rollout_data["mb_gt_actions"]
441:         _validate_floating_tensor("student BC prediction", predicted, A2_STUDENT_ACTION_DIM)
442:         _validate_floating_tensor("teacher BC target", target, A2_STUDENT_ACTION_DIM)
443:         if predicted.shape != target.shape:
444:             raise ValueError(f"A2 12D BC shape mismatch: {predicted.shape} vs {target.shape}")
445:         masks = mb_rollout_data.get("mb_masks")
446:         if masks is None:
447:             if predicted.ndim != 2:
448:                 raise ValueError("A2 recurrent DAgger BC requires mb_masks for [B,T,12] batches")
449:             return {"dagger_bc_loss": self.bc_loss_fn(predicted.to(target.dtype), target)}
450:         if not torch.is_tensor(masks) or masks.dtype != torch.bool:
```

## gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml：55–72

```text
55:     use_padding_mask: False
56:     ppo_shuffle_every_epoch: True
57:     sync_advantage_normalization: True
58:     actor_learning_rate: 1.0e-4
59:     critic_learning_rate: 1.0e-4
60:     dagger_bc_loss_type: l2
61:     dagger_bc_loss_coef: 1.0
62:     compute_dagger_bc_loss_w_imgaug: False
63:     train_with_evaluating_env: False
64:     enforce_teacher_rollout: True
65:     ratio_teacher_rollout: 1.0
66: 
67:     # Exactly 12 learned high-level actions.  The A2_Base leg policy is frozen
68:     # and appended only at the environment boundary by the A2 distill trainer.
69:     student_action_dim: 12
70:     teacher_action_dim: 12
71:     rollout_action_dim: 24
72:     teacher_obs_dim: 133
```

## gr00t/rl/isaac_utils/playground/env_rand/door_v29_parameters.py：1–51

```text
1: """Fixed per-door B01/B04 parameters. All dynamics values use SI units."""
2: 
3: import math
4: from collections.abc import Sequence
5: 
6: import numpy as np
7: 
8: 
9: MASS_RANGES_KG = ((30.0, 80.0), (80.0, 120.0), (120.0, 160.0))
10: 
11: 
12: def sample_door_parameters(
13:     sides: Sequence[str], rng: np.random.Generator
14: ) -> list[dict]:
15:     """Balance the six mass/closer cells within each side, then shuffle.
16: 
17:     Integer remainders also balance the mass and closer marginals (difference
18:     at most one). Geometry and the physics engine determine inertia; this
19:     sampler never substitutes a plate approximation for the actual inertia.
20:     """
21:     result = [{} for _ in sides]
22:     for side in ("left", "right"):
23:         indices = [i for i, value in enumerate(sides) if value == side]
24:         mass_order = rng.permutation(3)
25:         closer_flip = int(rng.integers(2))
26:         cells = [
27:             (int(mass_order[i % 3]), bool((i % 2) ^ closer_flip))
28:             for i in range(len(indices))
29:         ]
30:         rng.shuffle(cells)
31:         for index, (mass_bucket, closer_enabled) in zip(indices, cells):
32:             torque = float(rng.uniform(2.5, 12.0)) if closer_enabled else 0.0
33:             omega = float(rng.uniform(0.15, 0.40)) if closer_enabled else 0.0
34:             static = float(rng.uniform(0.0, 1.0))
35:             result[index] = {
36:                 "mass_bucket": mass_bucket,
37:                 "mass_kg": float(rng.uniform(*MASS_RANGES_KG[mass_bucket])),
38:                 "closer_enabled": closer_enabled,
39:                 "torque_cap_nm": torque,
40:                 "omega_ref_rad_s": omega,
41:                 "stiffness_nm_rad": torque / (math.pi / 2.0 + math.pi / 18.0),
42:                 "damping_nm_s_rad": torque / omega if closer_enabled else 0.0,
43:                 "target_position_rad": -math.pi / 18.0,
44:                 "static_friction_nm": static,
45:                 "dynamic_friction_nm": static * float(rng.uniform(0.5, 1.0)),
46:                 "viscous_friction_nm_s_rad": float(rng.uniform(0.0, 0.5)),
47:                 "max_opening_deg": float(rng.uniform(90.0, 150.0)),
48:             }
49:     if any(not parameters for parameters in result):
50:         raise ValueError("v29 door sides must be left or right")
51:     return result
```

## gr00t/rl/isaac_utils/playground/env_rand/door.py：535–568

```text
535: 
536:     hinge_joint_prim_path = os.path.join(root_prim_path, "hinge_joint")
537:     hinge_joint = UsdPhysics.RevoluteJoint.Define(stage, hinge_joint_prim_path)
538:     hinge_joint.CreateBody0Rel().SetTargets([root_prim_path])
539:     hinge_joint.CreateBody1Rel().SetTargets([panel_prim_path])
540:     hinge_joint.GetAxisAttr().Set("Z")
541:     hinge_joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.02, -half_door_width * door_open_lr, 0))
542:     if door_open_lr == 1:
543:         hinge_joint.CreateLocalRot0Attr().Set(Gf.Quatf(real=0.0, imaginary=(Gf.Vec3f(1, 0, 0))))
544:     hinge_joint.GetLowerLimitAttr().Set(0.0)
545:     if cfg.v29_dynamics is not None:
546:         dynamics = cfg.v29_dynamics
547:         if door_weight != dynamics["mass_kg"]:
548:             raise ValueError("v29 dynamics and authored panel mass disagree")
549:         hinge_joint.GetUpperLimitAttr().Set(dynamics["max_opening_deg"])
550:         hinge_drive = UsdPhysics.DriveAPI.Apply(hinge_joint.GetPrim(), "angular")
551:         hinge_drive.CreateTypeAttr("force")
552:         hinge_drive.CreateTargetPositionAttr(np.degrees(dynamics["target_position_rad"]))
553:         hinge_drive.CreateTargetVelocityAttr(0.)
554:         hinge_drive.CreateMaxForceAttr(dynamics["torque_cap_nm"])
555:         hinge_drive.CreateStiffnessAttr(dynamics["stiffness_nm_rad"]*np.pi/180.)
556:         hinge_drive.CreateDampingAttr(dynamics["damping_nm_s_rad"]*np.pi/180.)
557:         friction_prim = hinge_joint.GetPrim()
558:         friction_prim.ApplyAPI("PhysxJointAxisAPI", "angular")
559:         for name, value in (
560:             ("staticFrictionEffort", dynamics["static_friction_nm"]),
561:             ("dynamicFrictionEffort", dynamics["dynamic_friction_nm"]),
562:             ("viscousFrictionCoefficient", dynamics["viscous_friction_nm_s_rad"]*np.pi/180.),
563:         ):
564:             friction_prim.GetAttribute(f"physxJointAxis:angular:{name}").Set(value)
565:     else:
566:         hinge_joint.GetUpperLimitAttr().Set(150)
567:         hinge_drive = UsdPhysics.DriveAPI.Apply(hinge_joint.GetPrim(), "angular")
568:         hinge_drive.GetTargetPositionAttr().Set(-10.0)
```

## gr00t/rl/isaac_utils/playground/env_rand/handle_v29.py：196–226

```text
196: 
197: def build_handle_geometry(parameters, door_open_lr):
198:     """Return local convex cells, explicit mass properties and the unique inside G."""
199:     p = normalize_handle_metadata(parameters)
200:     family, scale = p["family"], p["plane_scale"]
201:     if p["version"] != 29 or door_open_lr not in (-1, 1):
202:         raise ValueError("B05 requires v29 parameters and a signed door side")
203:     interval = _free_interval(family)*scale
204:     centre_interval = interval + np.array([.031, -.031])
205:     if centre_interval[1] <= centre_interval[0]:
206:         raise ValueError("B05 grasp-centre interval is empty")
207:     sg = centre_interval.mean()
208:     qg = brentq(lambda q: _arc(family, q)*scale-sg, 0., 1.)
209:     pg2, tg2 = _curve(family, qg)
210:     tg2 /= np.linalg.norm(tg2)
211:     pg = np.array([-(.020+p["face_standoff_m"]), -door_open_lr*pg2[0]*scale, pg2[1]*scale])
212:     e = np.array([0., -door_open_lr*tg2[0], tg2[1]])
213:     approach = np.array([1., 0., 0.])
214:     rotation = np.column_stack((e, np.cross(-e, approach), approach))
215:     quat = Rotation.from_matrix(rotation).as_quat()[[3, 0, 1, 2]]
216:     ph = p["section_roll_rad"]
217:     a, b, r = p["section_normal_diameter_m"]/2, p["section_closing_diameter_m"]/2, p["corner_radius_m"]
218:     normal_support = (a-r)*abs(np.cos(ph))+(b-r)*abs(np.sin(ph))+r if family == "F2" else np.hypot(a*np.cos(ph), b*np.sin(ph))
219:     closing_support = (a-r)*abs(np.sin(ph))+(b-r)*abs(np.cos(ph))+r if family == "F2" else np.hypot(a*np.sin(ph), b*np.cos(ph))
220:     p.update(free_interval_m=interval.tolist(), centre_interval_m=centre_interval.tolist(), grasp_arc_m=float(sg),
221:              grasp_position_local_m=pg.tolist(), grasp_quaternion_wxyz=quat.tolist(),
222:              grasp_normal_half_extent_m=float(normal_support), grasp_closing_half_extent_m=float(closing_support),
223:              main_arc_length_m=float(_arc(family, 1.)*scale), axle_length_m=.040+2*p["face_standoff_m"])
224:     steps = 1 if family in ("F0", "F1", "F2") else 8 if family in ("F3", "X1", "F6") else 16
225:     qs = np.linspace(0., 1., steps+1)
226:     if family == "F5":
```

## 实际runtime config选择字段

```json
{
  "reward_scales": {
    "penalty_upper_body_non_gripper_deviation_l1": -5.0,
    "penalty_base_roll_pitch_l2": -2.0,
    "a2_v22_controlled_fling": 0.0,
    "penalty_a2_stage4_arm_default_pose_l1": -0.5,
    "penalty_a2_stage5_upright_l2": -8.0,
    "grasp_target_distance": 3.0,
    "a2_stage4_grasp_target_distance_mild": 1.0,
    "dont_push_door_handle": 3.0
  },
  "control": {
    "control_type": "P",
    "stiffness": {
      "hip": 140.0,
      "thigh": 140.0,
      "calf": 220.0,
      "arm_j1": 64.0,
      "arm_j2": 128.0,
      "arm_j3": 64.0,
      "arm_j4": 64.0,
      "arm_j5": 64.0,
      "arm_j6": 64.0,
      "arm_j7": 1300.0,
      "arm_j8": 1300.0
    },
    "damping": {
      "hip": 4.5,
      "thigh": 4.5,
      "calf": 9.0,
      "arm_j1": 3.0,
      "arm_j2": 4.5,
      "arm_j3": 3.0,
      "arm_j4": 3.0,
      "arm_j5": 3.0,
      "arm_j6": 3.0,
      "arm_j7": 32.0,
      "arm_j8": 32.0
    },
    "action_scale": 0.25,
    "isaac_pd_scale": false,
    "clamp_actions": 1.0,
    "clip_torques": true,
    "action_clip_value": 100.0
  },
  "delta_parameters": {
    "delta_action_indices": [
      5,
      6,
      7,
      8,
      9,
      10
    ],
    "delta_action_scale": 0.3,
    "delta_action_clip": 15.0,
    "reset_delta_actions_with_backmap": true,
    "delta_action_clamp_to_dof_limits": true
  }
}
```

## 已存A3000记录；不是自然episode率

```json
{
  "console_comparison": {
    "Mean rewards": {
      "batch1000_console": "61.54958",
      "batch3000_console": "109.80628"
    },
    "Mean entropy": {
      "batch1000_console": "8.93851",
      "batch3000_console": "10.64041"
    },
    "Env/a2_stage2_active_frac": {
      "batch1000_console": "0.6629",
      "batch3000_console": "0.7057"
    },
    "Env/a2_stage2_both_contact_frac": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.4098"
    },
    "Env/a2_stage2_grasp_complete_frac": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0001"
    },
    "Env/a2_stage2_to3_advance_frac": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0001"
    },
    "Env/a2_stage3_active_frac": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0462"
    },
    "Env/a2_stage4_active_frac": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0000"
    },
    "Env/a2_stage5_active_frac": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0000"
    },
    "Env/a2_v26_left_max_stage_reached": {
      "batch1000_console": "3.0000",
      "batch3000_console": "3.0000"
    },
    "Env/a2_v26_right_max_stage_reached": {
      "batch1000_console": "2.0000",
      "batch3000_console": "3.0000"
    },
    "Env/a2_v26_left_stage3_snapshot_sample_count": {
      "batch1000_console": "1.0000",
      "batch3000_console": "8688.0156"
    },
    "Env/a2_v26_right_stage3_snapshot_sample_count": {
      "batch1000_console": "0.0000",
      "batch3000_console": "9810.0469"
    },
    "Env/a2_v26_left_stage4_snapshot_sample_count": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0000"
    },
    "Env/a2_v26_right_stage4_snapshot_sample_count": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0000"
    },
    "Env/a2_v26_left_stage5_snapshot_sample_count": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0000"
    },
    "Env/a2_v26_right_stage5_snapshot_sample_count": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0000"
    },
    "Env/a2_v26_left_goal_count": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0000"
    },
    "Env/a2_v26_right_goal_count": {
      "batch1000_console": "0.0000",
      "batch3000_console": "0.0000"
    }
  },
  "interpretation": {
    "progress": "Stage2 both-contact telemetry increased from rounded0.0000 to0.4098; both sides now show historical Stage3 and thousands-scale logged Stage3 snapshot counts. Stage3 active telemetry is0.0462.",
    "remaining_gap": "Stage2 grasp-completion/advance still logs0.0001; neither side logs Stage4/5 snapshot samples or goal completion. Reliable whole-task success is not established.",
    "measurement_limits": [
      "These are staged-training logs, not first-natural-episode evaluation rates",
      "Both-contact field is not a grasp-success or episode-success rate",
      "Snapshot sample-count fields are training-log aggregates with fractional printed values, not independently counted natural successful episodes",
      "Rounded0.0000 does not prove an event never occurred",
      "Mean reward/entropy changes do not independently establish policy quality or loss finiteness"
    ],
    "loss": "NOT_OBSERVED under D061",
    "penalty_driver_nan": "Same three known empty-natural-sample telemetry fields as D063; no new loss observation or trigger for source changes",
    "policy_acceptance": "UNASSESSED"
  }
}
```
