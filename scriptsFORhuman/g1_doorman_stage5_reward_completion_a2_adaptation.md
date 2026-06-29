# G1 Doorman Stage5 Reward / Completion A2 Adaptation Checklist

本文给 human 快速看懂：A2+Piper 进入 `STAGE_THROUGH = 5` 以后，原版 G1 到底在奖励什么、stage5 怎么 complete、当前 A2 哪些可以先保留、哪些必须重新设计。

一句话结论：stage5/through 的主目标是 robot 已经穿过门（root_x > 0.0）后，继续走向目标位置（root_x > 1.5）完成任务。G1 的 stage5 reward 是 stage4 的延续——继续推门 hinge、继续走向 target_root_pos、松开 handle 让它回弹，同时恢复行走姿态。大部分 terms 与 stage4 共享（`effective_in_stage` 包含 `[4,5]`），加上 stage0 行走相关 terms 在 stage5 重新激活（`effective_in_stage` 包含 `[0,...,5]`）。`target_root_pos` z 已调整为 0.5 匹配 A2 trunk 高度。

## 优先级清单

- DONE 2026-06-29: stage3-4 reward completion / A2 adaptation 已确认 `static PASS`，stage3-5 transition conditions 与 G1 origin 逐字节一致不需要改 code。
- DONE 2026-06-29: `target_root_pos` z 从 G1 的 `0.72` 调整为 A2 的 `0.5`（匹配 trunk 高度）。
- DONE 2026-06-29: `pregrasp_gripper_dof_pos_l1` stage5 修正为 track close target（gripper 行走时收起）。修复 gate_mask 逻辑：`track_close` 和 `track_open` 都为 False 时 gate_mask=0（stage2 inside gate），否则 gate_mask=1。stage0 和 stage5 现在都真正主动奖励 gripper 收起。
- DONE 2026-06-29: `penalty_face_door` stage5 改为 disabled。`effective_in_stage` 从 `[0,1,2,5]` 改为 `[0,1,2]`，A2 穿门后不再惩罚 root-to-door orientation deviation。
- P1: bounded smoke 仍要统计 stage4→5 route、stage5 dwell、root locomotion、complete timing。

## Source of Truth

- Origin env: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- Origin reward config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- Current A2 env: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`
- Current A2 reward config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`
- A2 env config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/env/door_open_a2_base.yaml`
- Stage4 checklist: `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/g1_doorman_stage4_reward_completion_a2_adaptation.md`

## 状态词约定

| 状态 | 含义 |
|---|---|
| `PASS carrier` | stage/routing 条件可沿用，但不代表 through 行为已经 smoke 通过。 |
| `PASS baseline` | 第一版可以保留训练，后续看 reward magnitude、方向和副作用。 |
| `PASS reward metric` | reward 侧 metric 已有 A2 实现，可继续作为 shaping。 |
| `PASS disabled` | 当前 A2 明确不启用，或者启用会引入错误语义。 |
| `TODO design` | 需要单独设计 A2/Piper 语义，不能直接照搬 G1。 |
| `TODO smoke` | 静态代码可以先过，但 runtime 需要验证。 |

## Stage5 Boundary Facts

| 项目 | G1/HOMIE 原始语义 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| Stage name | `STAGE_THROUGH = 5`，已穿过门，继续走到完成位置 | stage index 沿用 | PASS carrier | stage5 是最后一个 stage，complete 后 task done。 |
| Stage5 reward condition | `_stage_5_reward_condition()` = `_stage_4_to_5_advance_condition()` | A2 同 G1 | PASS carrier | stage5 只要保持 stage4→5 的条件（已穿过门 + 门开 60° + handle 回弹）就持续给 stage reward。 |
| Stage5 complete | `_stage_5_to_complete_condition()` = `robot_root_states[:, 0] - env_origins[:, 0] > 1.5` | A2 同 G1 | PASS baseline / verify | A2 trunk body x 语义与 G1 pelvis 相同。1.5m 阈值是否匹配 A2 步态速度需 smoke。 |
| `target_root_pos` | G1 config `[2.0, 0.0, 0.72]` | A2 config `[2.0, 0.0, 0.5]`——z 已改为 A2 trunk 高度 | DONE | stage5 继续用 `target_root_distance` 引导 root 走向 [2.0, 0.0, 0.5]。 |

## Stage5 Reward Term Mapping

仅列出在 stage5 (`STAGE_THROUGH = 5`) 生效的 reward terms。

### Stage5 与 Stage4 共享的 terms（`effective_in_stage` 包含 [4,5]）

| Reward term | G1 scale / stage | G1 大白话 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---:|---|---|---|---|
| `stage` | `+1.0`, all stages | 当前 stage condition 满足时给 flow reward | A2 沿用 `StagedTaskBase` | PASS carrier | stage5 条件 = stage4→5 advance 条件。 |
| `dont_push_door_handle` | `+3.0`, stages `[4,5]` | 继续奖励 handle 回弹（保持松开状态） | A2 scale `3.0`，与 G1 完全一致 | PASS baseline | stage5 handle 应已回弹到 0，reward 保持满值。door-joint progress。 |
| `target_root_distance` | `+12.0`, stages `[4,5]` | 继续走向 target_root_pos | A2 scale `12.0`，`target_root_pos` z=0.5 | PASS baseline | stage5 `reward *= 1.0`（full reward，不再 ×0.5）。 |

### Stage5 与 Stage0 共享的 terms（`effective_in_stage` 包含 [0,...,5]）

这些是行走相关 terms，在 stage0（走向门）和 stage5（穿过门后继续走）都激活。

| Reward term | G1 scale / stage | G1 大白话 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---:|---|---|---|---|
| `penalty_upper_body_non_gripper_deviation_l1` | `-1.0`, stages `[0,5]` | 行走时上半身保持 resting pose，不要乱动 | A2 scale `-1.0`，使用 `_upper_non_gripper_dof_idx`（arm_j1..j6）替代 G1 finger index | PASS baseline | stage5 穿门后恢复行走姿态。A2 已排除 arm_j7/arm_j8 gripper DOF。 |
| `pregrasp_gripper_dof_pos_l1` | G1 `+1.5`, stages `[0,1,2,5]`；A2 `+0.5` | stage5 收起 gripper（回到 close target） | A2 scale `0.5`，stage-aware target：stage0 close / stage1 open / stage2-gate-outside open / stage5 close | PASS baseline / verify stage5 target | A2 `pregrasp_gripper_dof_pos_l1` 在 stage5 应 track close target（行走时收起）。需确认 stage5 走的是 close target 分支。 |
| `penalty_face_door` | `-1.0`, stages `[0,1,2,5]` | stage5 穿门后要面向前方（不要回头看门） | A2 scale `-1.0`，使用 `relative_door_rot_buf` 的 full rotation penalty | PASS baseline | stage5 穿门后继续 penalize root-to-door orientation deviation。A2 可能不需要正对门后方——smoke 看是否过强。 |

### Always-on terms

| Reward term | G1 scale / stage | G1 大白话 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---:|---|---|---|---|
| `penalty_door_frame_contact` | `-0.1`, always-on | 撞门框要罚 | A2 已有 sensors 和 scale | PASS baseline | stage5 穿门时可能碰到门框边缘。 |
| `penalty_door_panel_contact` | `-0.1`, always-on | 撞门板要罚 | A2 已有 sensors 和 scale | PASS baseline | stage5 穿门时可能碰到门板。 |
| `penalty_undesired_contact` | `-0.2`, always-on | 不该碰的 body 碰到东西要罚 | A2 已有 A2-specific `penalize_contacts_on` | PASS baseline | stage5 穿门时 legs/trunk 可能误碰。 |
| `penalty_dof_acc` | `-1.0e-5`, always-on | DOF 加速度惩罚 | A2 沿用 | PASS carrier | 全局 safety。 |
| `penalty_dof_vel` | `-1.0e-3`, always-on | DOF 速度惩罚 | A2 沿用 | PASS carrier | 全局 safety。 |
| `penalty_delta_action_rate` | `-0.01`, always-on | action 抖动惩罚 | A2 沿用，覆盖 arm_j1..j6 | PASS carrier | 全局 safety。 |
| `penalty_base_command_limit` | `-1.0`, always-on | base command 超限惩罚 | A2 沿用 | PASS carrier | 全局 safety。 |
| `penalty_dof_overspeed` | `-0.1`, always-on | DOF 超速惩罚 | A2 沿用，使用 `_upper_non_gripper_dof_idx` | PASS carrier | 全局 safety。 |
| `orientation_control` | `-5.0`, always-on | LMP-style base pitch/roll control | A2 replacement | PASS baseline | 全局 posture safety。 |
| `limits_dof_pos` | `-5.0`, always-on | DOF 位置接近 limit 惩罚 | A2 沿用 | PASS carrier | 全局 safety。 |
| `limits_gripper_primitive_action` | `-1.0`, always-on | gripper primitive raw action 超限惩罚 | A2 replacement | PASS carrier | 全局 safety。 |
| `ref_dof_legs` | `+0.25`, always-on | LMP-style leg gait ref prior | A2 replacement | PASS baseline | 全局 gait shaping。 |
| `termination` | `-1000.0`, always-on | 终止惩罚 | A2 沿用 | PASS carrier | 全局。 |

### Stage5 不生效但曾在 stage4 生效的 terms（仅供对比，不在 stage5 检查范围）

| Reward term | 为何 stage5 不生效 |
|---|---|
| `push_door_hinge` | `effective_in_stage` = [3,4]，stage5 不含 |
| `penalty_standing_still` | `effective_in_stage` = [4]，stage5 不含 |
| `grasp` | `effective_in_stage` = [1,2,3,4]，stage5 不含 |
| `grasp_target_distance` | `effective_in_stage` = [2,3,4]，stage5 不含 |
| `gripper_handle_orientation` | `effective_in_stage` = [1,2,3,4]，stage5 不含 |
| `penalty_unused_dof_deviation_l1` | `effective_in_stage` = [1,2,3,4]，stage5 不含；且 A2 scale 0.0 disabled |
| `grasp_finger_dof_pos_l1` | `effective_in_stage` = [2,3,4]，stage5 不含；且 A2 scale 0.0 disabled |

## Stage5 Through Design Checklist

| 设计输入 | 当前可用 source | 为什么需要 | A2适配状态 | 第一版建议 |
|---|---|---|---|---|
| Root locomotion | `robot_root_states[:, :3]`, `target_root_pos`, `_rigid_body_vel[:, root_idx, :]` | stage5 继续走向 target_root_pos [2.0, 0.0, 0.5] | DONE | z 已从 0.72 改为 0.5。 |
| Handle 保持松开 | `door.data.joint_pos[:, 1]`, `joint_vel[:, 1]` | stage5 handle 应已回弹到 0 | PASS baseline | `dont_push_door_handle` 继续引导。 |
| 上半身恢复 resting pose | `_upper_non_gripper_dof_idx` dof_pos vs `resting_dof_pos` | stage5 行走时 arm 回到默认位置 | PASS baseline | `penalty_upper_body_non_gripper_deviation_l1` 在 stage5 重新激活。 |
| Gripper 收起 | `_a2_gripper_dof_indices` close target tracking | stage5 行走时 gripper 收起 | PASS baseline / verify | `pregrasp_gripper_dof_pos_l1` stage5 应 track close target。需确认 stage-aware target 逻辑覆盖 stage5。 |
| Complete 阈值 | `robot_root_states[:, 0] - env_origins[:, 0] > 1.5` | robot 走到门后方 1.5m 处完成 | PASS baseline / verify | A2 步态速度可能影响 timing，但 `max_stage_time[5]=200` 给了足够时间。 |
| Door contact safety | door frame/panel contact sensors | 穿门时撞门框/门板 | PASS baseline / smoke | 统计 frame/panel penalty frequency。 |

## 不要做的事

| 不要做 | 原因 |
|---|---|
| 不要在 stage5 继续保持 grasp/contact reward | stage5 已经穿过门，不需要保持抓握。`grasp` / `grasp_target_distance` / `gripper_handle_orientation` 的 `effective_in_stage` 都不含 5，这是正确的。 |
| 不要把 complete 阈值 `root_x > 1.5` 改小 | 1.5m 是 G1 经过验证的距离。A2 如果步态慢，应该调 timer 而不是缩短距离。 |
| 不要在 stage5 重新启用 `push_door_hinge` | stage5 门应该已经开够了，不需要继续推。`push_door_hinge` 的 `effective_in_stage` = [3,4] 不含 5。 |
| 不要忽略 `penalty_face_door` 在 stage5 的影响 | G1 stage5 仍 penalize root-to-door orientation deviation。A2 穿门后可能自然转头看前方，这个 penalty 可能过强。smoke 看是否需要改为 stage5 不启用或放宽。 |

## 建议施工顺序

| 顺序 | 工作 | 验收标准 |
|---:|---|---|
| 1 | user 审核本 stage5/through checklist | 明确哪些 term 先 PASS baseline，哪些进入 TODO design。 |
| 2 | 确认 `pregrasp_gripper_dof_pos_l1` stage5 走 close target 分支 | 读取 `effective_in_stage` 和 stage-aware target 逻辑，确认 stage5 track close target。 |
| 3 | 确认 `penalty_face_door` stage5 是否合理 | A2 穿门后是否需要继续 penalize root-to-door orientation。smoke 后决定是否放宽。 |
| 4 | 确认 `complete: root_x > 1.5` 是否匹配 A2 | smoke 看 stage5 complete timing。 |
| 5 | bounded smoke | 记录 stage4→5 route、stage5 dwell、root locomotion、complete timing、door contact penalties、reset/overtime。 |

## Human 验收建议

| 验收项 | 当前状态 | 看什么 |
|---|---|---|
| Static source review | TODO after user review | 与 stage4 共享的 terms 是否可作为 A2 baseline；stage0 共享的 terms 在 stage5 重新激活是否合理。 |
| `pregrasp_gripper_dof_pos_l1` stage5 target | TODO verify | stage5 是否 track close target（行走时收起）。 |
| `penalty_face_door` stage5 | TODO smoke | A2 穿门后是否被过度惩罚 root-to-door orientation deviation。 |
| Stage routing review | PASS static from stage4 | `_stage_4_to_5_advance_condition()` 和 `_stage_5_to_complete_condition()` 与 G1 一致。 |
| Runtime smoke | TODO | stage5 是否真的走向 target_root_pos 并 complete，而不是卡住或 reset。 |
