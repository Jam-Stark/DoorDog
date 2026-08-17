# A2+Piper Stage2 Grasp Reward 与 Completion

> 最后更新：2026-07-14 22:33 HKT —— 已同步当前 A2 code/YAML。

`STAGE_GRASP = 2` 只负责把 Piper 两指稳定地夹住 handle。开门、hinge
progress 和 swing 不属于 stage2 的 completion。以下是当前 source/config 的
静态说明，不是 runtime 成功声明。

## 读表口径

`reward_door_open_a2_base.yaml` 是 baseline。表中 scale 是 YAML 原始 scale，
尚未乘 `dt`；运行时 scale 为 `0.0` 的 key 会先被移除，非零 key 会准备并乘
`dt`，但 `termination` 会从普通 reward-function list 中显式跳过，在普通 loop
和 positive clipping 后单独加入。全局注册/非零 scale 不代表 raw reward 每一步都非零。
`reward_penalty_curriculum=false`，因此当前不会乘 penalty curriculum
scale；resolved experiment overrides 可能不同。`PASS (static)` 不等于训练或
接触效果已验证。

## 16 个 registered-global / conditional-global reward

| reward term | YAML scale（pre-dt） | 注册/当前计算 | 当前作用（大白话） |
|---|---:|---|---|
| `penalty_dof_acc` | `-1.0e-5` | 注册全局、非零；raw 随 arm 加速度变化 | 抓握时手臂不要突然猛加速。 |
| `penalty_dof_vel` | `-1.0e-3` | 注册全局、非零；raw 随 arm 速度变化 | 抓握时手臂不要高速甩动。 |
| `penalty_delta_action_rate` | `-0.01` | 注册全局、非零；只看 6D arm delta | 让手臂 action 连续，不要抖。 |
| `termination` | `-1000.0` | 注册全局、普通 reward loop 跳过，后置单独加入；raw=`reset_buf & ~time_out_buf` | raw 为真才罚：例如 StagedTaskBase 的 stage overtime 会设 reset、但不设 `time_out_buf`；普通 episode timeout 和 delayed completion 的 reset 有 `time_out_buf`，不收这项罚分。 |
| `limits_dof_pos` | `-5.0` | 注册全局、非零；A2 arm 位置 limit | 防止抓握时 `arm_j1..j6` 顶限位。 |
| `limits_gripper_primitive_action` | `-1.0` | 注册全局、raw primitive 超界才非零 | gripper raw command 越界要付代价。 |
| `stage` | `+1.0` | 注册全局、非零；`accumulate_stage_reward=false` | 当前 stage2 base-still 条件满足时给流程分，不是 grasp completion。 |
| `complete` | `+4.0` | 注册全局、最终完成后的 conditional signal | 最后完成后奖励；不会因为抓住 handle 就直接 final complete。 |
| `success_save_time` | `+0.5` | 注册全局、`reset_buf & time_out_buf` 条件式 | 完成/timeout reset 且 flags 同时为真时奖励省下的总时间；不是 stage2→3。 |
| `ref_dof_legs` | `+0.25` | 注册全局、非零；随 gait phase | 给四腿参考姿态，让抓握时脚步稳定。 |
| `penalty_door_frame_contact` | `-1.0` | 注册全局、接触力条件式 | 身体撞门框要罚。 |
| `penalty_door_panel_contact` | `-0.1` | 注册全局、接触力条件式 | 身体撞门板要罚。 |
| `penalty_base_command_limit` | `-1.0` | 注册全局、raw/clipped command 差异条件式 | base command 超限时罚。 |
| `penalty_undesired_contact` | `-0.2` | 注册全局、A2 非期望 body 接触条件式 | 腿、躯干、非 gripper arm 不要乱碰；gripper links 排除。 |
| `penalty_dof_overspeed` | `-0.1` | 注册全局、arm `>3 rad/s` 才非零 | 抓握时 arm 超过 **3 rad/s** 要罚；`arm_j7/j8` 不在此项。 |
| `orientation_control` | `-5.0` | 注册全局、physical pitch/roll command 条件式 | 让机身保持平稳，别为夹把手而侧翻。 |

## Stage2 current reward inventory

| reward term | YAML scale（pre-dt） | 当前 stage gate / function branch | 当前作用（大白话） | 静态状态 |
|---|---:|---|---|---|
| `pregrasp_gripper_dof_pos_l1` | `+0.5` | `effective_in_stage([0,1,2,5])`；stage2 **close gate 外** track open，gate 内返回 0 | 还没对准把手时保持张开；一旦进 close gate 就让 close 专项接管。 | PASS (static) |
| `gripper_handle_orientation` | `+3.0` | `effective_in_stage([1,2,3,4])`；stage2 active | 继续把 gripper opening/approach 方向对准 handle。 | PASS (static) |
| `grasp_target_distance` | `+3.0`，A2 std=`0.05` | `effective_in_stage([2,3,4])`；A2 用 handle `target_pos_source[:,0,:]` 距离，stage4 branch 显式归零 | 把 Piper TCP/source 拉到 handle 中心；不是 G1 palm 距离。 | PASS (static) |
| `grasp` | `+0.2` | `effective_in_stage([1,2,3,4])`；stage2 用 source local `+Y` 两侧接触 shaping | 接触要像夹住，而不是侧撞；两侧 force 越合理越有利。 | PASS (static) |
| `a2_stage2_close_command` | `+1.0` | `effective_in_stage(2)` 且 close gate；raw primitive 越 close reward 越高 | 对准后明确要求 gripper 发 close command。 | PASS (static) |
| `penalty_a2_stage2_open_command_in_close_gate` | `-0.4` | `effective_in_stage(2)` 且 close gate；gate 内 open raw 才受罚 | 已经对准却继续张开会掉分。 | PASS (static) |
| `a2_stage2_close_progress` | `+0.5` | `effective_in_stage(2)` 且 close gate；按 actual DOF close progress | 不只发口令，还要让两指真的收拢。 | PASS (static) |
| `a2_stage2_handle_center_y` | `+6.0`，std=`0.015` | `effective_in_stage(2)` 全程 active | 把 handle 的 source-local Y 偏差压到中心，避免只碰一边。 | PASS (static) |
| `a2_stage2_handle_approach_xz` | `+3.0`，std=`0.05` | `effective_in_stage(2)` 全程 active | 同时把 handle 的 X/Z approach 偏差压小。 | PASS (static) |
| `a2_stage2_both_contact` | `+1.0` | `effective_in_stage(2)`；两侧 force norm `>1.0` 才给 | 鼓励 `arm_body7` 和 `arm_body8` 都碰到 handle。 | PASS (static) |
| `a2_stage2_opposite_squeeze` | `+1.0` | `effective_in_stage(2)`；两侧 local-Y force sign 相反 | 鼓励两指从相反方向夹，而不是同向顶。 | PASS (static) |
| `a2_stage2_squeeze_force_window` | `+1.0` | `effective_in_stage(2)`；每侧 local-Y force magnitude 在 `0.5..20.0` | 鼓励有用但不过大的夹持力。 | PASS (static) |
| `a2_stage2_contact_stability` | `+1.0` | `effective_in_stage(2)`；历史窗口满后检查连续双侧接触 | 鼓励接触持续，不要只闪一帧。 | PASS (static) |
| `penalty_a2_stage2_over_force` | `-1.0` | `effective_in_stage(2)`；force 超过 `40.0` 阈值才罚 | 防止用暴力挤压伪装成 grasp。 | PASS (static) |
| `penalty_a2_stage1_stage2_base_forward_creep` | `-1.5` | `effective_in_stage([1,2])`；deadband=`0.05`、normalizer=`0.10` | 不让 base 在 close 阶段继续向门蹭。 | PASS (static) |
| `penalty_not_standing_still` | `-15.0` | `effective_in_stage([1,2,3])`；stage2 base command norm | 抓握时 base 尽量稳住。 | PASS (static) |
| `penalty_face_door` | `-1.0` | `effective_in_stage([0,1,2])`；stage2 active | 保持身体朝门，减少 TCP 偏航。 | PASS (static) |
| `grasp_finger_dof_pos_l1` | `0.0` | YAML placeholder；A2 branch 返回 zeros，绑定前移除 | 当前 binary gripper 不追 fully-closed finger target。 | PASS disabled |
| `penalty_a2_stage2_single_finger_contact` | `0.0` | YAML placeholder；函数可算 single-contact mask 但不绑定 | 单指接触只保留 diagnostics，不直接扣 reward。 | PASS disabled |
| `penalty_unused_dof_deviation_l1` | `0.0` | YAML placeholder；one-arm Piper 不适用 | 没有另一只 arm 可约束，当前不产生 reward。 | PASS disabled |

### Close gate 的精确静态定义

`_get_a2_stage2_close_reward_gate()` 只在 `stage_buf==2` 且同时满足：

- handle target 在 Piper source frame 中 `abs(Y) < 0.022`、`abs(Z) < 0.015`、
  `abs(X) < 0.020`；
- `opening_alignment >= 0.9` 且 `approach_alignment >= 0.9`。

因此 `pregrasp_gripper_dof_pos_l1` 在 gate 外仍鼓励 open，在 gate 内为零；
`a2_stage2_close_command`、open-command penalty 和 close-progress 共用这个 gate。

## Stage2 completion 与 Stage2→3（和 reward 分开）

| 事件 | 当前 source 条件 | 说明 |
|---|---|---|
| Stage2 reward condition | `_stage_2_reward_condition()`：physical base command `norm[:3] <=0.1` | 只限制 base 不乱走，不等于已经 grasp。 |
| Stage2 completion base gate | `stage_buf==STAGE_GRASP`，`actual_time_in_stage_buf >= H-1`，当前 `H=5` | 至少在 stage2 实际停留到第 5 个 history sample（dwell `>=4`）。 |
| Stage2 completion contact history | 最近 **5 个连续 sample** 每一个都同时满足：两侧 contact force norm `>1.0`、两侧 `abs(local-Y)>0.5`、两侧 local-Y sign opposite | 这是 `both_contact & sufficient_squeeze & opposite_squeeze` 的全 history AND；一帧 spike 不能过关。 |
| Optional close gate | `a2_stage2_completion_close_gate_required=false`（当前默认） | 默认 completion **不要求** close gate；只有显式 override 为 true 时，才额外要求当前 close gate、raw primitive `<-0.2`、两指最小 close progress `>=0.45`。 |
| Stage2→3 | A2 `_stage_2_to_3_advance_condition()` **只返回 strict completion** | 不再使用 door-open OR bypass。`_get_a2_door_open_bypass_mask()` 只写 diagnostics，不能推进 stage。 |

`complete` / `success_save_time` 仍是最终任务信号；stage2 grasp completion
不是 final complete。当前 source/config 的 gate 已静态核对，接触力效果、stage2
dwell 分布和训练成功率需要另行 runtime 验证。
