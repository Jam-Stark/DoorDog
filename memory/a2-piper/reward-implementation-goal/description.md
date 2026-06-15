---
name: reward-implementation-goal
scope: A2+Piper Doorman reward implementation, especially global and stage0-enabled rewards
status: active
last_updated: 2026-06-15 22:44 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/reward-implementation-goal/description.md
  - memory/a2-piper/reward-implementation-goal/TODO.md
  - memory/a2-piper/reward-implementation-goal/DONE.md
read_when:
  - 开始设计、实现、review 或 debug A2+Piper reward 前
  - 需要确认 global reward、stage0 reward、Doorman 原版 reward 迁移或 LMP manager-based reward 迁移约束时
---

# Reward Implementation Goal

## Purpose

记录 A2+Piper Doorman reward implementation 的近期目标、工程约束、source-of-truth 协作方式与安全边界。当前重点不是完整开门任务所有 stage reward，而是先实现 global rewards 和 stage0-enabled rewards。

## Current Small Goal

- 2026-06-14 21:48 HKT - 接下来的小目标：实现 A2+Piper Doorman training 中全局启用的 reward，以及 stage0 启用的 reward。
- Scope 第一阶段只覆盖 global reward 和 stage0 reward；stage1/pregrasp、grasp、open、swing、through 的完整 reward adaptation 暂不作为本小目标验收标准。
- Stage0 baseline reference: `scriptsFORhuman/g1_doorman_stage0_reward_transition.md` 已总结 G1 Doorman stage0 active rewards、global penalties 与 stage0 -> stage1 advance condition，可作为 A2+Piper stage0 reward adaptation 的对照表。
- 2026-06-15 22:33 HKT - A2 stage0/global reward adaptation 第一版完成：`penalty_delta_action_rate` 标记 PASS，`penalty_upright` 替换为 LMP-style `orientation_control`，termination 完成 A2/LMP height/orientation/arm overspeed 适配。
- 2026-06-15 22:44 HKT - 用户确认当前 stage0 reward 与大部分 global reward 已完成可复用审核和 A2_Piper adjustment，可作为后续训练 smoke 的 stage0/global reward baseline；下一步 reward work 转向 stage1+ 的 Piper EE/handle、gripper/contact、door progress 与 success shaping。

## Reward Term Decisions

- 2026-06-15 14:32 HKT - `walk_to_door` stage0 reward 第一版标记 pass：Ava 与 main review 判断该 term 不是 G1/HOMIE-specific，当前可沿用 G1 Doorman 的 door-root velocity shaping。代码中已注释记录未来改法：target 可参数化为 `door_root`、`grasp_target` 或 Piper-specific `approach_anchor`。
- 2026-06-15 14:32 HKT - `penalty_face_door` reward 第一版标记 pass：当前可沿用 G1 Doorman 的 full root-to-door orientation penalty。代码中已注释记录未来改法：如果 A2 trunk roll/pitch 或非正对站姿被过度惩罚，则改为 yaw-only heading error 或增加 desired heading offset。
- 2026-06-15 14:55 HKT - `pregrasp_finger_dof_pos_l1` 已迁移为 `pregrasp_gripper_dof_pos_l1`：A2 第一版使用 actual Piper gripper DOF (`arm_j7/arm_j8`) close target tracking，close target 为 `[0.0, 0.0]`，span 来自 open-close 行程，不使用 G1 finger raw velocity target `0.6`。
- 2026-06-15 14:55 HKT - `penalty_upper_body_non_finger_deviation_l1` 已迁移为 `penalty_upper_body_non_gripper_deviation_l1`：A2 使用 `_upper_non_gripper_dof_idx` 只约束 `arm_j1..arm_j6` 相对 `resting_dof_pos` 的 L1 deviation；stage0 -> stage1 的 arm stability `max_deviation` 同步排除 `arm_j7/arm_j8`，gripper 开闭不阻塞 stage transition。
- 2026-06-15 14:59 HKT - Reviewer 二轮修正：`penalty_upper_body_non_gripper_deviation_l1` 不加入 `reward_penalty_reward_names`，保持 origin G1 中 upper-body penalty 不受 `reward_penalty_scale` curriculum 影响的行为；`pregrasp_gripper_dof_pos_l1` 继续保留在该 list 中，对齐 origin `pregrasp_finger_dof_pos_l1` 的 positive shaping curriculum 行为。
- 2026-06-15 15:16 HKT - `door_open_a2_base.py` 已删除旧 `finger` / `non_finger` reward legacy aliases 和 `pregrasp_gripper_dof_pos_l1` 内的 G1 finger fallback；A2 文件中该 reward 现在只保留 Piper gripper actual DOF close tracking。
- 2026-06-15 16:59 HKT - A2 global DOF safety 第一批标记 PASS：`penalty_dof_acc`、`penalty_dof_vel`、`limits_dof_pos`、`penalty_dof_overspeed` 以及 `_check_termination()` upper-body overspeed 均改用 `_upper_non_gripper_dof_idx`，只覆盖 Piper `arm_j1..arm_j6`，排除 `arm_j7/arm_j8` gripper。
- 2026-06-15 16:59 HKT - `stage` 标记 PASS：沿用 `StagedTaskBase._reward_stage()` flow reward；它不是 pure alive bonus，而是依赖当前 stage reward condition。`penalty_door_frame_contact` / `penalty_door_panel_contact` 标记 PASS：A2 scene callback 在 A2 branch return 前创建同名 door contact sensors。
- 2026-06-15 16:59 HKT - `penalty_homie_action_limit` 已迁移为 reward-facing `penalty_base_command_limit`：比较 scaled raw base command 与 clipped scaled base command 的 squared diff；A2 env 和 trainer 的 A2_Base command obs 均使用 clipped scaled command。`_homie_commands`、`get_physical_homie_commands`、`b_homie_commands` 等 compatibility naming 暂保留，后续单独 cleanup。
- 2026-06-15 16:59 HKT - Deferred reward terms：`limits_primitive_action` 保持 `0.0`，因为旧 `FingerPrimitiveBase` over-limit buffer 不适用于 A2 gripper primitive；`penalty_humanly_dof_limit` 保持 `0.0`，等待 A2-specific limit semantics 审核。
- 2026-06-15 20:21 HKT - `penalty_undesired_contact` 标记 A2 global PASS：A2-specific `penalize_contacts_on` 使用用户给定的 trunk、leg links 与 non-gripper Piper arm links，A2 开启 exact match 避免 `arm_body6` 误匹配 `arm_body6_to_gripper`；reward scale 对齐 G1 原版 `-0.2`。
- 2026-06-15 21:05 HKT - Deferred reward terms 已完成替换：`limits_primitive_action` 迁移为 A2 `limits_gripper_primitive_action`，只惩罚 raw high-level gripper primitive 超过 `limit * tolerance`，不混用 actual gripper joint pose；`penalty_humanly_dof_limit` 不复用 G1 humanoid-specific posture limit，替换为 LMP-style positive `ref_dof_legs` gait ref prior，A2 weight 使用 `0.25`。
- 2026-06-15 21:24 HKT - Future gripper/reward design：当前 1D binary gripper primitive 会在 close target 为 `[0.0, 0.0]` 且 handle 挡在中间时持续用 position actuator 追完全闭合，可能造成过大接触力、抖动或真实机器人不舒适的夹紧目标。后续 grasp reward 不应奖励“完全闭合”，而应奖励合适 aperture/contact/handle constraint，例如两侧 gripper 接触 handle、接触力不过大、handle 相对 gripper 稳定；actual close tracking 只适合作为 pregrasp/close-default shaping，不应在 grasp 阶段强推完全闭合。
- 2026-06-15 21:29 HKT - Future continuous gripper primitive design 修正：下一版不采用单纯 `alpha = clamp(raw, 0, 1)`，而采用更接近原版 primitive 的三步链路：`raw` 先用于记录越界量 `over_limit = relu(abs(raw) - 1.1)`；runtime 使用 `clipped = raw.clamp(-1.0, 1.0)`；aperture 用 `alpha = (clipped + 1.0) * 0.5` 映射，`target = close_target + alpha * (open_target - close_target)`。这样 `limits_gripper_primitive_action` 与 actual gripper target 解耦，越界惩罚看 raw action，控制目标看 clipped action。
- 2026-06-15 22:33 HKT - `penalty_delta_action_rate` 标记 A2 PASS：不改 `DeltaActionBase` runtime，当前 A2 语义由 `delta_action_indices=[3..8]` 决定，只平滑 Piper `arm_j1..arm_j6` 的 6D delta action，不覆盖 base command 或 gripper primitive。
- 2026-06-15 22:33 HKT - `penalty_upright` 替换为 LMP-style `orientation_control`：读取 `_a2_body_pitch_roll_raw[:,0/1]` 作为 pitch/roll raw command，乘 `body_pitch_roll_scale` 后构造 desired XY `[-sin(pitch)*cos(roll), sin(roll)]`，再对 `projected_gravity[:,:2]` 做 squared error；reward scale 使用 LMP `-5.0`，不加入 `reward_penalty_reward_names`。当前 A2 high-level action 仍是 10D，暂未输出 pitch/roll，`_a2_body_pitch_roll_raw` 默认 zero。
- 2026-06-15 22:33 HKT - Termination 完成 A2/LMP adjustment：`termination_min_base_height` 改为 `0.3`，A2 config 新增 `bad_orientation_limit_angle=0.9`，`DoorPregrasp._check_termination()` 在 `super()._check_termination()` 后显式检查 `acos(-projected_gravity[:,2]) > 0.9`；不启用 `terminate_by_gravity`，不改变 shared `LeggedRobotBase` termination 语义。arm overspeed termination 继续使用 `_upper_non_gripper_dof_idx`，只覆盖 Piper `arm_j1..arm_j6`，排除 gripper `arm_j7/arm_j8`。
- 2026-06-15 22:44 HKT - Stage0/global reward baseline status：`scriptsFORhuman/g1_doorman_stage0_reward_transition.md` 中 stage0 active terms 与主要 global terms 已标记 PASS 或 A2 replacement；仍需后续在 train/env smoke 中验证 reward magnitude、stage transition cadence、termination frequency 与 A2_Piper behavior。

## Engineering Constraints

- Reward implementation 必须符合 IsaacLab `direct workflow` 规范；不要把 manager-based `RewardManager` / `ObservationManager` runtime 结构直接硬塞进当前 direct env，除非经过明确设计与 review。
- IsaacLab 文档获取方式：优先使用 Context7 查询 IsaacLab official docs；也可以对照本机源码 `/home/baoquanc/workspace/IsaacLab`。
- 若 reward term 需要从 LMP `manager-based` 项目迁移，必须先和 Bella/Galileo 讨论并提取训练时 source logic、scale、timing、manager semantics，再设计 DoorDog direct path 的等价实现。
- 若 reward term 来自 Doorman 原版 G1/HOMIE chain，必须让 Ava 做 origin-code 逻辑核查/解释。Ava 的回答必须带 source code path、函数名与关键 code/line 方便核查。
- Doorman 原版实现链路如需破坏性修改、移除或改变语义，必须先获得 Ava 的风险核查，以及 user 审核/同意；不要在未确认的情况下直接破坏 Doorman-derived stage/reward/control routing。

## Subagent Roles

- Bella/Galileo: 长期保留的 LMP manager-based source tracing agent，负责帮助提取和总结 LMP 项目中 reward/observation/action 的训练时计算逻辑。
- Ava: 长期保留的 Doorman origin-code logic reviewer/explainer。当前 agent id: `019ec664-05f2-78c3-9a99-29fdd11723fd`；tool nickname 为 `Lagrange`，项目内按用户命名记为 Ava。

## TODO Summary

- 2026-06-15 22:33 HKT - Stage0/global reward adaptation 第一版已完成；后续进入 stage1/pregrasp、grasp、open、swing、through reward adaptation 时，继续沿用 mapping 表方式记录 G1 term、A2 replacement、数据源、scale、stage gating、direct workflow update timing 与验证方式。
- 2026-06-15 22:33 HKT - 后续若新增来自 LMP manager-based 的 reward term，仍需先提取原始计算逻辑，再决定 direct path 迁移方案；本轮 `orientation_control` 已按 LMP source logic 完成 direct buffer 实现。
- 2026-06-14 21:48 HKT - 对来自 G1 Doorman 的 reward/stage semantics，先让 Ava 给出带 code reference 的核查意见；破坏性修改必须经 Ava 和 user 同意。
- 2026-06-15 14:32 HKT - `walk_to_door` 未来如 stage0 target 与 A2/Piper reach envelope 不匹配，将 reward target 参数化为 `door_root` / `grasp_target` / `approach_anchor`。
- 2026-06-15 14:32 HKT - `penalty_face_door` 未来如 full-quat penalty 对 A2 trunk roll/pitch 或必要侧向站姿过强，将改为 yaw-only heading error 或加入 desired heading offset。
- 2026-06-15 22:33 HKT - 后续若新增 stage0/global reward 或进入 stage1+ reward adaptation，同步更新 `scriptsFORhuman/g1_doorman_stage0_reward_transition.md` 或新增对应 transition doc 的 `A2适配状态` 列。
- 2026-06-15 14:59 HKT - 后续迁移 reward scale 时同步核对 origin `reward_penalty_reward_names` membership；不要仅根据 reward scale 正负决定是否加入 penalty curriculum。
- 2026-06-15 16:59 HKT - 后续单独做 homie compatibility naming cleanup：`_homie_commands`、`get_physical_homie_commands`、`b_homie_commands` 等仍是历史兼容名，本轮只完成 reward-facing `penalty_base_command_limit` rename。
- 2026-06-15 21:29 HKT - 后续若 gripper action 改为 continuous aperture primitive，同步更新 `limits_gripper_primitive_action` 为 raw range penalty：`relu(abs(raw) - 1.1)`；runtime control 先 clamp raw 到 `[-1, 1]`，再用 `alpha = (clipped + 1) * 0.5` 映射 aperture。该 term 只约束 policy raw action 幅度，不根据 actual gripper joint pose/contact 判定。
- 2026-06-15 21:24 HKT - 后续 grasp-stage reward 设计应从“完全闭合 target”转向 aperture/contact/force/stability：避免奖励 gripper 把 handle 硬夹到 fully closed target，改为奖励合适开合度、双侧接触、不过大的 contact force、handle 与 gripper 相对稳定。

## DONE Summary

- 2026-06-14 21:48 HKT - 新建 reward implementation memory entry，记录 global/stage0 reward 小目标、IsaacLab direct workflow 约束、Bella/Galileo 与 Ava 协作职责，以及 Doorman-derived 破坏性修改审核门槛。
- 2026-06-15 14:32 HKT - 在 `door_open_a2_base.py` 中给 `walk_to_door` 与 `penalty_face_door` 加注释，标记这两个 G1-derived reward 第一版 stage0 pass，并记录 target parameterization 与 yaw-only/heading-offset 两种未来改法。
- 2026-06-15 14:55 HKT - 实现 A2 `pregrasp_gripper_dof_pos_l1` 与 `penalty_upper_body_non_gripper_deviation_l1`：reward config 启用 G1-equivalent scales，A2 reward 使用 actual gripper close tracking，upper-body non-gripper index 与 stage0 transition 均排除 gripper DOF。
- 2026-06-15 14:59 HKT - 按 reviewer 二轮意见修正 reward curriculum membership：upper-body non-gripper penalty 从 `reward_penalty_reward_names` 移除，pregrasp gripper positive shaping 继续保留，保持 G1-equivalent curriculum 行为。
- 2026-06-15 15:16 HKT - 删除旧 `pregrasp_finger_dof_pos_l1` / `penalty_upper_body_non_finger_deviation_l1` legacy reward methods 与 G1 finger fallback；在 A2 gripper/non-gripper reward 函数中标记 stage0 `PASS`，并在 `scriptsFORhuman/g1_doorman_stage0_reward_transition.md` 表格中新增 `A2适配状态` 列，将 4 个已适配 reward 标记为 `PASS`。
- 2026-06-15 16:59 HKT - 完成 A2 global/stage0 reward PASS 第二批：DOF safety 使用 non-gripper arm index，door frame/panel contact 与 stage flow reward 标记 PASS，`penalty_homie_action_limit` 迁移为 `penalty_base_command_limit`，并将 `penalty_undesired_contact` 调整为 deferred/disabled。
- 2026-06-15 20:21 HKT - 启用 A2 `penalty_undesired_contact`：`penalize_contacts_on` 使用用户给定的 trunk、leg links 与 non-gripper Piper arm links，并通过 A2-only exact match flag 避免包含 gripper links；reward scale 对齐 G1 原版 `-0.2`，并在 transition 表格标记 PASS。
- 2026-06-15 21:05 HKT - 完成两项 deferred reward 替换：新增 A2 raw `limits_gripper_primitive_action` reward 与 LMP-style `ref_dof_legs` reward/config，reward YAML 启用 `-1.0` / `0.25`，transition 表格标记 PASS，且两者不加入 `reward_penalty_reward_names`。
- 2026-06-15 21:24 HKT - 记录 gripper primitive/reward future work：当前 1D binary primitive 不改代码；下一版优先 continuous aperture primitive，并在 grasp reward 中避免奖励 fully closed target，改用 aperture/contact/force/handle stability 约束。
- 2026-06-15 21:29 HKT - 修正 continuous gripper primitive future design：采用“raw 越界记录 -> runtime clamp -> clipped 映射 aperture”的原版 primitive 思路，`limits_gripper_primitive_action` 后续应惩罚 raw 越界量，控制目标只使用 clipped action。
- 2026-06-15 22:33 HKT - 完成 A2 stage0/global 剩余 reward/termination 适配：`penalty_delta_action_rate` 标记 PASS 并说明 6D Piper `arm_j1..arm_j6` delta smoothing；active `penalty_upright` 替换为 LMP-style `orientation_control: -5.0`；termination 对齐 LMP `root_height_below_minimum=0.30` 与 `bad_orientation=0.9`，并保持 arm overspeed 只检查 `_upper_non_gripper_dof_idx`。
- 2026-06-15 22:44 HKT - 用户确认 stage0 reward 与大部分 global reward 已完成可复用审核和 A2_Piper adjustment；该状态已记录为 stage0/global reward baseline，后续 reward 重点转向 stage1+ interaction/progress/success terms 与 smoke 后的权重调参。
