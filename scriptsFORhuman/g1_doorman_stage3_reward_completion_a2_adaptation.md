# A2+Piper Stage3 Open Reward 与 Stage3→4 Gate

> 最后更新：2026-07-14 22:33 HKT —— 已同步当前 A2 code/YAML。

`STAGE_OPEN = 3` 的工作是保持已经完成的 grasp，同时压下 handle、推动
hinge。stage2 才负责严格 grasp completion；stage3→4 是 hinge progress，
不是 final task completion。

## 读表口径

`reward_door_open_a2_base.yaml` 是 baseline；下表 scale 均是乘 `dt` 前的
YAML 值。运行时 zero scale 会在 reward binding 前移除，nonzero key 会准备并
乘 `dt`，但 `termination` 会从普通 reward-function list 中显式跳过，在普通
loop 和 positive clipping 后单独加入。全局注册/非零 scale 不代表 raw reward 每一步都非零。
`reward_penalty_curriculum=false`，当前不乘 penalty curriculum
scale；resolved experiment override 可能改变值。`PASS (static)` 仅代表
source/config 静态语义，不能替代 PPO/IsaacSim evidence。

## 16 个 registered-global / conditional-global reward

| reward term | YAML scale（pre-dt） | 注册/当前计算 | 当前作用（大白话） |
|---|---:|---|---|
| `penalty_dof_acc` | `-1.0e-5` | 注册全局、非零；raw 随 arm 加速度变化 | 开门时手臂别突然猛加速。 |
| `penalty_dof_vel` | `-1.0e-3` | 注册全局、非零；raw 随 arm 速度变化 | 手臂别高速甩动。 |
| `penalty_delta_action_rate` | `-0.01` | 注册全局、非零；只看 6D arm delta | 减少 arm action 抖动。 |
| `termination` | `-1000.0` | 注册全局、普通 reward loop 跳过，后置单独加入；raw=`reset_buf & ~time_out_buf` | raw 为真才罚：例如 StagedTaskBase 的 stage overtime 会设 reset、但不设 `time_out_buf`；普通 episode timeout 和 delayed completion 的 reset 有 `time_out_buf`，不收这项罚分。 |
| `limits_dof_pos` | `-5.0` | 注册全局、非零；A2 arm 位置 limit | 防止 arm 关节撞软限位。 |
| `limits_gripper_primitive_action` | `-1.0` | 注册全局、raw primitive 超界才非零 | 防止 gripper command 越界。 |
| `stage` | `+1.0` | 注册全局、非零；只看当前 stage condition | stage3 条件成立时给流程分，不表示 hinge 已过阈值。 |
| `complete` | `+4.0` | 注册全局、最终完成后的 conditional signal | 只有最后任务完成才给完成奖励，不是 stage3→4。 |
| `success_save_time` | `+0.5` | 注册全局、`reset_buf & time_out_buf` 条件式 | 完成/timeout reset 同时满足两 flag 时奖励省时，不是 stage transition。 |
| `ref_dof_legs` | `+0.25` | 注册全局、非零；A2 gait reference | 给四腿保持稳定参考步态。 |
| `penalty_door_frame_contact` | `-1.0` | 注册全局、接触力条件式 | 机身撞门框要罚。 |
| `penalty_door_panel_contact` | `-0.1` | 注册全局、接触力条件式 | 机身撞门板要罚。 |
| `penalty_base_command_limit` | `-1.0` | 注册全局、raw/clipped command 差异条件式 | base command 超限要罚。 |
| `penalty_undesired_contact` | `-0.2` | 注册全局、A2 非期望 body 接触条件式 | 腿、躯干、非 gripper arm 不该碰就别碰。 |
| `penalty_dof_overspeed` | `-0.1` | 注册全局、arm `>3 rad/s` 才非零 | arm 超 **3 rad/s** 会掉分；gripper DOF 排除。 |
| `orientation_control` | `-5.0` | 注册全局、physical pitch/roll command 条件式 | 推门时保持机身姿态，不要侧翻。 |

## Stage3 current reward inventory

| reward term | YAML scale（pre-dt） | 当前 stage gate / function branch | 当前作用（大白话） | 静态状态 |
|---|---:|---|---|---|
| `push_door_handle` | `+6.0` | `effective_in_stage(3)`；读 door handle joint index 1 的 pos/vel | 奖励把手被压下/转动，给开门动作方向。 | PASS (static) |
| `push_door_hinge` | `+6.0` | `effective_in_stage([3,4])`；读 hinge joint index 0 的 pos/vel | 奖励门铰链角度和打开速度增加。 | PASS (static) |
| `grasp` | `+0.2` | `effective_in_stage([1,2,3,4])`；A2 handle-specific source local `+Y` contact reward | 继续夹住把手，别一推门就松手。 | PASS (static) |
| `grasp_target_distance` | `+3.0`，A2 std=`0.05` | `effective_in_stage([2,3,4])`；stage3 active，TCP/source→handle distance | 让夹爪别离把手太远。 | PASS (static) |
| `gripper_handle_orientation` | `+3.0` | `effective_in_stage([1,2,3,4])`；stage3 active | 保持夹爪 opening/approach 方向跟着转动中的 handle。 | PASS (static) |
| `penalty_not_standing_still` | `-15.0` | `effective_in_stage([1,2,3])`；locked 时为 base command norm，unlocked stage3 raw 被置零 | 默认锁定时鼓励 base 不乱走；显式解锁时不再罚 stage3 base movement。 | PASS (static, conditional) |
| `a2_stage3_stage4_keep_close_command` | `+0.5` | `effective_in_stage([3,4])`；raw primitive close 越强越高 | 开门过程中保持夹紧 command。 | PASS (static) |
| `penalty_a2_stage3_stage4_open_command` | `-1.0` | `effective_in_stage([3,4])`；raw open command 才罚 | 防止刚抓住就重新张开。 | PASS (static) |
| `a2_stage3_stage4_both_contact` | `+0.5` | `effective_in_stage([3,4])`；两侧接触 mask | 鼓励两指持续同时碰把手。 | PASS (static) |
| `a2_stage3_stage4_opposite_squeeze` | `+0.5` | `effective_in_stage([3,4])`；相反 local-Y squeeze mask | 鼓励两指继续相向夹。 | PASS (static) |
| `a2_stage3_stage4_squeeze_force_window` | `+0.5` | `effective_in_stage([3,4])`；force 在有效窗口 | 有夹持力但不要暴力顶。 | PASS (static) |
| `a2_stage3_stage4_contact_stability` | `+0.5` | `effective_in_stage([3,4])`；连续历史双侧接触 | 奖励 grip 不要一帧有、一帧丢。 | PASS (static) |
| `penalty_a2_stage3_stage4_over_force` | `-1.0` | `effective_in_stage([3,4])`；过大 force mask | 防止用撞击/暴力接触换 hinge progress。 | PASS (static) |
| `push_door_force` | `0.0` | YAML placeholder；A2 branch 返回 zeros，绑定前移除 | 不用 G1 world-X hand force 假装是 Piper 推门力。 | PASS disabled |
| `grasp_finger_dof_pos_l1` | `0.0` | YAML placeholder；A2 branch zeros | 当前 binary gripper 不追 fully-closed finger pose。 | PASS disabled |
| `penalty_unused_dof_deviation_l1` | `0.0` | YAML placeholder；绑定前移除 | Piper one-arm，没有另一只 arm 可约束。 | PASS disabled |

`penalty_face_door=-1.0` 虽在 YAML 中，但 source gate 是
`effective_in_stage([0,1,2])`，**stage3 不 active**；`penalty_base_roll_pitch_l2`
也只在 `[0,1,4,5]`，不要把它们误写成 stage3 reward。

## Stage3 condition 与 Stage3→4（和 reward 分开）

| 事件 | 当前 source 条件 | 说明 |
|---|---|---|
| Stage2→3 入口 | A2 只接受 stage2 strict completion（H=5 双侧 contact/squeeze/opposite history） | door-open mask 仅 diagnostics，不再 bypass grasp。 |
| Stage3 reward condition（默认锁定） | `a2_stage3_base_unlocked=false` 时 `_stage_3_reward_condition()` 返回 `_stage_2_reward_condition()`，即 physical base command `norm[:3] <=0.1` | 默认要求 base stillness；这不是新的 grasp completion。 |
| Stage3 reward condition（显式解锁 override） | `a2_stage3_base_unlocked=true` 时返回全 env `True` | stage condition 变成 unconditional；同一 override 还让 `penalty_not_standing_still` 在 stage3 raw 为零。默认仍是 locked。 |
| Stage3→4 | `_stage_3_to_4_advance_condition()` 每个 stage3 frame 检查 `door joint_pos[:,0] > a2_stage3_to4_door_hinge_threshold` | 当前配置默认 threshold **`0.174533 rad`**，但它是可 override 的单一 source of truth；不是写死且不是 final completion。 |
| Stage4/任务完成 | stage4→5 与 stage5→complete 另见 stage4/5 文档 | 通过 hinge 阈值只表示进入 swing。 |

当前文档只确认 static branch、joint index（0=hinge、1=handle）和默认阈值；
handle/hinge reward 的实际量级、stage3 dwell、grasp retention、runtime 开门成功
率仍需单独验证。
