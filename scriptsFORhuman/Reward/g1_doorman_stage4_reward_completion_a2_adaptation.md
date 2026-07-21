# A2+Piper Stage4 Swing Reward 与 Stage4→5 Gate

> 最后更新：2026-07-14 22:33 HKT —— 已同步当前 A2 code/YAML。

`STAGE_SWING = 4` 是门已开始打开后，停止继续下压 handle、让 handle joint
回弹并带着 robot 穿过门的阶段；这不等于打开 gripper。这里必须区分“当前 frame 的 stage reward 条件”和
“曾经达到过 hinge 阈值”：当前 source 每一帧重新检查 hinge，**不是历史
latch**。

## 读表口径

基准为 `reward_door_open_a2_base.yaml`；表中都是 YAML scale（pre-`dt`）。
reward binding 会删除 zero scale，再准备 nonzero key 并乘 `dt`；但
`termination` 会从普通 reward-function list 中显式跳过，在普通 loop 和
positive clipping 后单独加入。全局注册/非零 scale 不代表 raw reward 每一步都非零。
当前 `reward_penalty_curriculum=false`，不乘 penalty curriculum；resolved
experiment override 可能不同。`PASS (static)` 仅表示静态 source/config 事实，
不表示 swing runtime 已成功。

## 16 个 registered-global / conditional-global reward

| reward term | YAML scale（pre-dt） | 注册/当前计算 | 当前作用（大白话） |
|---|---:|---|---|
| `penalty_dof_acc` | `-1.0e-5` | 注册全局、非零；raw 随 arm 加速度变化 | 穿门时手臂不要猛加速。 |
| `penalty_dof_vel` | `-1.0e-3` | 注册全局、非零；raw 随 arm 速度变化 | 手臂不要高速甩动。 |
| `penalty_delta_action_rate` | `-0.01` | 注册全局、非零；6D arm delta | 减少手臂动作抖动。 |
| `termination` | `-1000.0` | 注册全局、普通 reward loop 跳过，后置单独加入；raw=`reset_buf & ~time_out_buf` | raw 为真才罚：例如 StagedTaskBase 的 stage overtime 会设 reset、但不设 `time_out_buf`；普通 episode timeout 和 delayed completion 的 reset 有 `time_out_buf`，不收这项罚分。 |
| `limits_dof_pos` | `-5.0` | 注册全局、非零；A2 arm 位置 limit | 防止 arm 关节顶软限位。 |
| `limits_gripper_primitive_action` | `-1.0` | 注册全局、raw primitive 超界才非零 | 防止 gripper command 越界。 |
| `stage` | `+1.0` | 注册全局、非零；只看当前 stage4 condition | 当前 frame hinge 条件成立才给流程分。 |
| `complete` | `+4.0` | 注册全局、最终完成后的 conditional signal | 只有 stage5 final complete 才给完成分。 |
| `success_save_time` | `+0.5` | 注册全局、`reset_buf & time_out_buf` 条件式 | 完成/timeout reset 且 flags 同时真时奖励省时；不是 stage4→5。 |
| `ref_dof_legs` | `+0.25` | 注册全局、非零；A2 gait reference | 给穿门行走保持参考步态。 |
| `penalty_door_frame_contact` | `-1.0` | 注册全局、接触力条件式 | 撞门框要明显扣分。 |
| `penalty_door_panel_contact` | `-0.1` | 注册全局、接触力条件式 | 撞门板要小幅扣分。 |
| `penalty_base_command_limit` | `-1.0` | 注册全局、raw/clipped command 差异条件式 | base command 超限要罚。 |
| `penalty_undesired_contact` | `-0.2` | 注册全局、A2 非期望 body 接触条件式 | 腿、躯干、非 gripper arm 不要撞环境。 |
| `penalty_dof_overspeed` | `-0.1` | 注册全局、arm `>3 rad/s` 才非零 | arm 超 **3 rad/s** 要罚；gripper DOF 排除。 |
| `orientation_control` | `-5.0` | 注册全局、physical pitch/roll command 条件式 | 穿门时保持机身别侧翻。 |

## Stage4 current reward inventory

| reward term | YAML scale（pre-dt） | 当前 stage gate / function branch | 当前作用（大白话） | 静态状态 |
|---|---:|---|---|---|
| `dont_push_door_handle` | `+3.0` | `effective_in_stage([4,5])`；handle joint pos/vel 回弹方向 | 奖励停止继续下压 handle，并让 handle joint 回到回弹方向；它不等于打开 gripper。 | PASS (static) |
| `push_door_hinge` | `+6.0` | `effective_in_stage([3,4])`；hinge joint pos/vel | 即使 gripper 继续保持 close/contact，门 hinge 仍继续打开时给 progress；停止继续下压 handle 只让 handle joint 回弹。 | PASS (static) |
| `target_root_distance` | `+12.0` | `effective_in_stage([4,5])`；stage4 source 最后乘 **0.5** | 带着 base 朝 `[2.0,0.0,0.5]` 走；stage4 只给半权重，避免压过同时存在的夹紧与 handle-return shaping。 | PASS (static) |
| `penalty_standing_still` | `-1.0` | `effective_in_stage(4)`；base command norm tracking | 惩罚 stage4 站着不走，促使开始穿门。 | PASS (static) |
| `grasp` | `+0.2` | `effective_in_stage([1,2,3,4])`；A2 handle contact shaping | 刚进 swing 时仍保留夹持信号，避免过早掉手。 | PASS (static) |
| `grasp_target_distance` | `+3.0`，A2 std=`0.05` | `effective_in_stage([2,3,4])`，但 A2 **stage4 分支显式返回 zero** | 旧的强 TCP→handle 距离 shaping 在 stage4 不再施加；不要把 YAML `+3` 写成实际 stage4 reward。 | PASS (static, zero branch) |
| `a2_stage4_grasp_target_distance_mild` | `+1.0` | `effective_in_stage(4)`；A2 TCP→handle distance 的 mild replacement | 只留一个较轻的距离牵引，帮助 handle-return 初期别让 TCP 瞬间离 handle 太远。 | PASS (static) |
| `gripper_handle_orientation` | `+3.0` | `effective_in_stage([1,2,3,4])`；stage4 active | handle joint 回弹前仍保持夹爪方向不过分偏离 handle。 | PASS (static) |
| `penalty_base_roll_pitch_l2` | `-2.0` | `effective_in_stage([0,1,4,5])`；stage4 active | 开始走时仍压住机身 roll/pitch。 | PASS (static) |
| `a2_stage3_stage4_keep_close_command` | `+0.5` | `effective_in_stage([3,4])`；raw close command | handle joint 尚未回弹时仍鼓励先保持夹紧。 | PASS (static) |
| `penalty_a2_stage3_stage4_open_command` | `-1.0` | `effective_in_stage([3,4])`；raw open command | 防止还没稳住门就突然张开。 | PASS (static) |
| `a2_stage3_stage4_both_contact` | `+0.5` | `effective_in_stage([3,4])`；both-contact mask | 鼓励两侧接触继续存在。 | PASS (static) |
| `a2_stage3_stage4_opposite_squeeze` | `+0.5` | `effective_in_stage([3,4])`；opposite-squeeze mask | 鼓励两指保持相向夹持。 | PASS (static) |
| `a2_stage3_stage4_squeeze_force_window` | `+0.5` | `effective_in_stage([3,4])`；squeeze force window | 鼓励适中的夹持力。 | PASS (static) |
| `a2_stage3_stage4_contact_stability` | `+0.5` | `effective_in_stage([3,4])`；连续接触历史 | 防止接触一闪就掉。 | PASS (static) |
| `penalty_a2_stage3_stage4_over_force` | `-1.0` | `effective_in_stage([3,4])`；over-force mask | 暴力夹门/撞门会扣分。 | PASS (static) |
| `penalty_unused_dof_deviation_l1` | `0.0` | YAML placeholder，binding 前删除 | Piper 没有 unused arm。 | PASS disabled |
| `grasp_finger_dof_pos_l1` | `0.0` | YAML placeholder，A2 branch zeros | 不追 fully-closed finger pose。 | PASS disabled |
| `penalty_a2_stage4_arm_default_pose_l1` | `0.0` | `effective_in_stage(4)` 但 zero scale，binding 前删除 | 不把 arm 拉回 default pose，避免和开门/穿门动作冲突。 | PASS disabled |

另外，`push_door_handle=+6.0` 只在 stage3；`penalty_face_door=-1.0`
只在 `[0,1,2]`；`penalty_not_standing_still=-15.0` 只在 `[1,2,3]`；
`push_door_force=0.0` 在 A2 disabled。它们不是当前 stage4 active terms。

## Stage4 condition 与 Stage4→5（和 reward 分开）

| 事件 | 当前 source 条件 | 说明 |
|---|---|---|
| Stage3→4 | stage2 strict completion 后，stage3 hinge `joint_pos[:,0] > a2_stage3_to4_door_hinge_threshold` | 默认阈值 `0.174533 rad`，可由 env config override。 |
| Stage4 reward condition | `_stage_4_reward_condition()` **每个 frame 直接调用** `_stage_3_to_4_advance_condition()` | hinge 角低于阈值的 frame 不满足 stage reward；没有“曾经超过阈值就永久 latch”的逻辑。 |
| Stage4→5 | root x（减 env origin）`>0.0`，hinge `>1.0472 rad`（60°），handle joint ` <0.2` | 三个条件同时满足才进入 `STAGE_THROUGH=5`；需要走过门、门足够开、handle joint 已回弹；这不是 gripper open gate。 |
| Stage5 final complete | stage5 root x `>1.5` | 这是 final task condition，另见 stage5 文档；不是 stage4 reward。 |

`target_root_pos=[2.0,0.0,0.5]` 是当前 config 静态值，stage4
`target_root_distance` 的 ×0.5 是 source branch；是否能在保持 gripper close/contact 的同时停止继续下压 handle、让 handle joint 回弹并穿门，
仍需 runtime 验证。frame/panel contact 是两个独立 global penalty，scale
分别 **`-1.0`** 与 **`-0.1`**，不能合写成一个门碰撞项。
