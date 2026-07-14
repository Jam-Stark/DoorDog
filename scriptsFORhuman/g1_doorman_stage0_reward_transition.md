# A2+Piper Stage0 Reward 与 Stage Transition

> 最后更新：2026-07-14 22:33 HKT —— 已同步当前 A2 code/YAML。

本文只描述当前 A2+Piper 的静态 source/config 语义。主配置是
`gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`；当前实验若有
Hydra override，resolved 值可以不同。这里的 scale 都是 YAML 原始值（乘
`dt` 之前）。

## 读表口径

`LeggedRobotBase._prepare_reward_function()` 会在绑定前删除 scale 为 `0.0`
的 key；非零 key 会准备并乘以 `dt`，但 `termination` 是例外：它会从普通 reward-function list
中显式跳过，在普通 loop 和 positive clipping 之后单独加入。
因此表中的 `0.0` 是“注册在 YAML、但当前不绑定”的 placeholder；全局注册/非零 scale 不代表 raw reward 每一步都非零。当前
`reward_penalty_curriculum=false`，所以不会再乘 reward penalty curriculum scale。
`PASS (static)` 只表示代码和配置静态一致，不表示训练效果或 runtime success 已验证。

## 16 个 registered-global / conditional-global reward

这些 key 在六个 stage 文档中都列出，方便把全局安全、步态和任务信号与
stage-specific shaping 分开看。

| reward term | YAML scale（pre-dt） | 注册/当前计算 | 当前作用（大白话） |
|---|---:|---|---|
| `penalty_dof_acc` | `-1.0e-5` | 注册全局、非零；raw 随 arm 加速度变化 | 手臂关节不要突然猛加速，动作更平滑。 |
| `penalty_dof_vel` | `-1.0e-3` | 注册全局、非零；raw 随 arm 速度变化 | 手臂 `arm_j1..j6` 不要转得太快。 |
| `penalty_delta_action_rate` | `-0.01` | 注册全局、非零；只看 6D arm delta action | 不要让 Piper 手臂的相邻 action 大跳变。 |
| `termination` | `-1000.0` | 注册全局、普通 reward loop 跳过，后置单独加入；raw=`reset_buf & ~time_out_buf` | raw 为真才罚：例如 StagedTaskBase 的 stage overtime 会设 reset、但不设 `time_out_buf`；普通 episode timeout 和 delayed completion 的 reset 有 `time_out_buf`，不收这项罚分。 |
| `limits_dof_pos` | `-5.0` | 注册全局、非零；A2 检查 `arm_j1..j6` | 手臂不要顶到关节位置软限位。 |
| `limits_gripper_primitive_action` | `-1.0` | 注册全局、非零；raw primitive 超界才有值 | gripper primitive 不要输出超出允许范围的 raw command。 |
| `stage` | `+1.0` | 注册全局、非零；`accumulate_stage_reward=false`，只看当前 stage condition | 当前 stage 的基本条件满足时给一格流程分；不是 stage transition 本身。 |
| `complete` | `+4.0` | 注册全局、最终完成条件后的 conditional signal | 最后一 stage 完成后保持完成状态时给任务完成奖励；不触发 stage0→1 等中间跳转。 |
| `success_save_time` | `+0.5` | 注册全局、`reset_buf & time_out_buf` 条件式 | 完成/timeout reset 且两类 flag 同时为真时，按剩余总时长奖励早完成；不是 stage transition 奖励。 |
| `ref_dof_legs` | `+0.25` | 注册全局、非零；raw 随 A2 gait phase 变化 | 给四条腿一个 LMP 风格参考步态，别乱抬腿。 |
| `penalty_door_frame_contact` | `-1.0` | 注册全局、接触力条件式 | 身体撞门框要付代价。 |
| `penalty_door_panel_contact` | `-0.1` | 注册全局、接触力条件式 | 身体撞门板也要付小代价。 |
| `penalty_base_command_limit` | `-1.0` | 注册全局、raw/clipped base command 差异条件式 | base command 超过可执行范围时要罚，避免硬顶限幅。 |
| `penalty_undesired_contact` | `-0.2` | 注册全局、A2 非期望 body 接触条件式（排除 gripper links） | 腿、躯干、非 gripper 手臂不该碰的东西不要碰。 |
| `penalty_dof_overspeed` | `-0.1` | 注册全局、仅 `arm_j1..j6` 超过 **3 rad/s** 才有值 | 手臂速度超过 3 rad/s 时增加惩罚；gripper `arm_j7/j8` 不在此项。 |
| `orientation_control` | `-5.0` | 注册全局、按 physical base pitch/roll command 条件式 | 让机身实际重力方向跟 base 的俯仰/横滚指令一致，别侧翻。 |

## Stage0 当前 reward inventory

`STAGE_WALK_TO_DOOR = 0` 的 stage reward condition
`_stage_0_reward_condition()` 恒为 True；下表是当前真正影响 stage0 的
stage-specific terms。

| reward term | YAML scale（pre-dt） | 当前 stage gate / source branch | 当前作用（大白话） | 静态状态 |
|---|---:|---|---|---|
| `walk_to_door` | `+5.0` | `effective_in_stage(0)`；A2 目标为 `grasp_target.x - 0.70`，z 取当前 root z，做 root velocity tracking | 把四足 base 走到把手前方约 70 cm 的 staging 点，给手臂留够伸展空间。 | PASS (static) |
| `penalty_upper_body_non_gripper_deviation_l1` | `-5.0` | `effective_in_stage([0,5])`；stage0 比较 `arm_j1..j6` 与 robot `default_dof_pos` | 走路时手臂六个关节收在默认姿态，不要边走边乱抬手。 | PASS (static) |
| `pregrasp_gripper_dof_pos_l1` | `+0.5` | `effective_in_stage([0,1,2,5])`；stage0 走 close target 分支 | 走向门时把两指收起，避免 gripper 先伸出去碰门。 | PASS (static) |
| `penalty_face_door` | `-1.0` | `effective_in_stage([0,1,2])`；stage0 active | 让 base 大致朝向门，不要横着靠近。 | PASS (static) |
| `penalty_base_roll_pitch_l2` | `-2.0` | `effective_in_stage([0,1,4,5])`；stage0 active | 走路时抑制机身 roll/pitch，避免身体歪着撞门。 | PASS (static) |

下列项虽在 YAML 中有记录，但 stage0 当前不提供对应 raw signal：

| 项目 | scale | Stage0 现状 |
|---|---:|---|
| `gripper_handle_orientation`、`pregrasp_target_distance`、`penalty_not_standing_still` | `+3.0`、`+6.0`、`-15.0` | 分别从 stage1、stage1、stage1 开始，stage0 不调用。 |
| `penalty_a2_stage1_stage2_base_forward_creep` | `-1.5` | 只在 stage1/2，stage0 不罚 base 前爬。 |
| `grasp`、`grasp_target_distance`、`a2_stage2_*` | `+0.2`、`+3.0`、见 stage2 文档 | 抓握与 close gate 尚未开始。 |
| `push_door_handle`、`push_door_hinge`、`a2_stage3_stage4_*`、`push_door_force` | `+6.0`、`+6.0`、见 stage3、`0.0` | 开门项尚未开始；`push_door_force` 当前是零 scale。 |
| `dont_push_door_handle`、`target_root_distance`、`penalty_standing_still`、`a2_stage4_grasp_target_distance_mild` | `+3.0`、`+12.0`、`-1.0`、`+1.0` | swing/through 项，stage0 不调用。 |
| `penalty_unused_dof_deviation_l1`、`grasp_finger_dof_pos_l1`、`penalty_a2_stage2_single_finger_contact`、`penalty_a2_stage4_arm_default_pose_l1` | `0.0` | A2 one-arm 或当前策略不需要；绑定前被移除，函数不会运行。 |

## Transition 与 completion（和 reward 分开）

| 事件 | 当前 source 条件 | 说明 |
|---|---|---|
| Stage0 reward | `_stage_0_reward_condition()` 恒真 | 只要当前 `stage_buf==0` 就有 stage reward；不代表已经到门。 |
| Stage0 → Stage1 | `_stage_0_to_1_advance_condition()`：root（先把 z 换成 target z）到 `grasp_target` 前方 `x-0.70` 的距离 **`<0.10 m`**，并且 `arm_j1..j6` 相对 A2 `default_dof_pos` 的最大绝对偏差 **`<0.10 rad`**。 | 这是当前 staging gate；不再使用旧的 raw-target `0.6 m` 或 arm `0.25 rad` 说法，也不检查 gripper 是否抓住。 |
| Stage0 overtime | `max_stage_time[0]=250`，`reset_on_overtime=True` | 未到 staging gate 会在 stage0 超时 reset。 |
| 全任务 complete | 由 stage5 的 `_stage_5_to_complete_condition()` 决定 | stage0→1 是 stage transition，不是 `complete` 或 `success_save_time`。 |

Stage transition 的静态 source/config 已核对；PPO/IsaacSim reward efficacy、stage0 dwell 分布和最终成功率仍未由本文验证。
