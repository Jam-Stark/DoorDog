# A2+Piper Stage5 Through Reward 与 Final Completion

> 最后更新：2026-07-14 22:33 HKT —— 已同步当前 A2 code/YAML。

`STAGE_THROUGH = 5` 是 robot 已满足 stage4→5 条件后，继续走到任务终点的
最后一段。当前 stage5 **不继续推 hinge，也不启用 face-door penalty**；它
主要做 root locomotion、手臂收回和 gripper 收起。本文只给静态 source/config
事实，不能把 `root_x>1.5` 或 200-step timer 写成 runtime 已验证/一定足够。

## 读表口径

`reward_door_open_a2_base.yaml` 是 baseline，表中 scale 是 YAML 原始值（乘
`dt` 前）。绑定前 zero scale 会删除，剩下的 nonzero key 会准备并乘 `dt`；但
`termination` 会从普通 reward-function list 中显式跳过，在普通 loop 和 positive
clipping 后单独加入。全局注册/非零 scale 不代表 raw reward 每一步都非零。当前
`reward_penalty_curriculum=false`，没有 penalty curriculum 乘法。resolved
experiment override 可能改变 scale 或 stage gate。`PASS (static)` 只代表
代码/config 一致，不代表 through 行为或训练成功。

## 16 个 registered-global / conditional-global reward

| reward term | YAML scale（pre-dt） | 注册/当前计算 | 当前作用（大白话） |
|---|---:|---|---|
| `penalty_dof_acc` | `-1.0e-5` | 注册全局、非零；raw 随 arm 加速度变化 | 收尾走路时手臂别突然猛加速。 |
| `penalty_dof_vel` | `-1.0e-3` | 注册全局、非零；raw 随 arm 速度变化 | 手臂别高速甩动。 |
| `penalty_delta_action_rate` | `-0.01` | 注册全局、非零；只看 6D arm delta | 降低动作抖动。 |
| `termination` | `-1000.0` | 注册全局、普通 reward loop 跳过，后置单独加入；raw=`reset_buf & ~time_out_buf` | raw 为真才罚：例如 StagedTaskBase 的 stage overtime 会设 reset、但不设 `time_out_buf`；普通 episode timeout 和 delayed completion 的 reset 有 `time_out_buf`，不收这项罚分。 |
| `limits_dof_pos` | `-5.0` | 注册全局、非零；A2 arm position limit | 防止 arm 顶到软限位。 |
| `limits_gripper_primitive_action` | `-1.0` | 注册全局、raw primitive 超界才非零 | gripper raw command 越界要罚。 |
| `stage` | `+1.0` | 注册全局、非零；只看 stage5 condition | stage5 条件仍成立时给流程分，不是 final complete。 |
| `complete` | `+4.0` | 注册全局、最终完成后的 conditional signal | root 到 final threshold 后给完成奖励。 |
| `success_save_time` | `+0.5` | 注册全局、`reset_buf & time_out_buf` 条件式 | 完成/timeout reset 同时满足 flags 时按剩余总时长给早完成奖励；不是 stage4→5。 |
| `ref_dof_legs` | `+0.25` | 注册全局、非零；A2 gait reference | 继续给四腿走路一个参考节奏。 |
| `penalty_door_frame_contact` | `-1.0` | 注册全局、接触力条件式 | 穿门时撞门框要重罚。 |
| `penalty_door_panel_contact` | `-0.1` | 注册全局、接触力条件式 | 撞门板要小罚。 |
| `penalty_base_command_limit` | `-1.0` | 注册全局、raw/clipped command 差异条件式 | base command 超限要罚。 |
| `penalty_undesired_contact` | `-0.2` | 注册全局、A2 非期望 body 接触条件式 | 腿、躯干、非 gripper arm 别碰环境。 |
| `penalty_dof_overspeed` | `-0.1` | 注册全局、arm `>3 rad/s` 才非零 | arm 超 **3 rad/s** 要罚；gripper DOF 排除。 |
| `orientation_control` | `-5.0` | 注册全局、physical pitch/roll command 条件式 | 走出门时保持机身稳定。 |

## Stage5 current reward inventory

| reward term | YAML scale（pre-dt） | 当前 stage gate / function branch | 当前作用（大白话） | 静态状态 |
|---|---:|---|---|---|
| `penalty_upper_body_non_gripper_deviation_l1` | `-5.0` | `effective_in_stage([0,5])`；stage5 比较 `arm_j1..j6` 与 A2 default pose | 穿门后把上臂收回默认姿态，别继续乱挥。 | PASS (static) |
| `pregrasp_gripper_dof_pos_l1` | `+0.5` | `effective_in_stage([0,1,2,5])`；stage5 track **close target** | 走出门时把 gripper 收起来，避免挂住门。 | PASS (static) |
| `penalty_base_roll_pitch_l2` | `-2.0` | `effective_in_stage([0,1,4,5])`；stage5 active | 走路穿门时压住机身 roll/pitch。 | PASS (static) |
| `dont_push_door_handle` | `+3.0` | `effective_in_stage([4,5])`；handle 回弹方向 | 保持把手松开，不要又把门把手压下去。 | PASS (static) |
| `target_root_distance` | `+12.0` | `effective_in_stage([4,5])`；stage5 full reward（仅 stage4 ×0.5） | 让 root 朝 `[2.0,0.0,0.5]` 走；stage5 不再减半。 | PASS (static) |

### Stage5 inert / zero terms（避免把旧语义带回来）

| reward term | YAML scale | 当前 stage5 现状 |
|---|---:|---|
| `penalty_face_door` | `-1.0` | source gate 只有 `[0,1,2]`，**stage5 inert**；穿门后不会继续要求面向门。 |
| `push_door_hinge` | `+6.0` | source gate 只有 `[3,4]`，**stage5 inactive**；stage5 不继续推 hinge。 |
| `push_door_handle` | `+6.0` | 只在 stage3，stage5 inactive。 |
| `grasp`、`grasp_target_distance`、`gripper_handle_orientation` | `+0.2`、`+3.0`（A2 std=.05）、`+3.0` | source gates 到 stage4 为止；stage5 不再保持抓握/贴把手。 |
| `a2_stage4_grasp_target_distance_mild`、`penalty_standing_still` | `+1.0`、`-1.0` | 只在 stage4，stage5 inactive。 |
| `a2_stage3_stage4_keep_close_command`、open penalty、both/opposite/squeeze/stability/over-force | `.5`、`-1.0`、`.5/.5/.5/.5/-1.0` | 只在 stage3/4；stage5 不继续要求 hold bundle。 |
| `grasp_finger_dof_pos_l1`、`penalty_unused_dof_deviation_l1`、`penalty_a2_stage4_arm_default_pose_l1` | `0.0` | A2 zero placeholders；绑定前移除，stage5 不产生 raw reward。 |
| `push_door_force` | `0.0` | A2 disabled placeholder；不会在 stage5 产生 force reward。 |

## Stage4→5 与 final completion（和 reward 分开）

| 事件 | 当前 source 条件 | 说明 |
|---|---|---|
| Stage4→5 | `root_x - env_origin_x > 0.0` **且** hinge `joint_pos[:,0] > 1.0472 rad`（60°）**且** handle `joint_pos[:,1] <0.2` | 必须已经穿过门平面、门足够开、把手已回弹，才进入 stage5。 |
| Stage5 reward condition | `_stage_5_reward_condition()` 复用上述 Stage4→5 条件 | 这只维持 stage5 flow reward；不等于 final complete。 |
| Stage5 final complete | `_stage_5_to_complete_condition()`：`robot_root_states[:,0] - env_origins[:,0] > **1.5m**` | 当前代码的 final threshold；本文不声称 A2 runtime 已达到或该距离已调优。 |
| Stage5 overtime | config `max_stage_time[5]=200`，`reset_on_overtime=True` | 这是静态 timer 上限；是否对 A2 步态足够仍未证明。 |

`complete=+4.0` 和 `success_save_time=+0.5` 是最终/timeout-reset 条件信号，
不是 stage4→5 transition reward。当前 source/config 已静态核对；through dwell、
root locomotion、1.5 m completion timing、door contact 和 runtime success 需要
独立 eval，不能从本表推断。
