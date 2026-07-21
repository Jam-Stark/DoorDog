# A2+Piper Stage1 Reward 与严格 Pregrasp Transition

> 最后更新：2026-07-14 22:33 HKT —— 已同步当前 A2 code/YAML。

`STAGE_PREGRASP = 1` 的目标是把 Piper gripper/TCP 对到门把手前的
pregrasp pose；这里不把“已经接触”或“门已经打开”当作 stage1 成功。
本文描述 source/config 的静态事实，不宣称 reward efficacy 或 runtime success。

## 读表口径

基准文件是 `reward_door_open_a2_base.yaml`。表中 scale 是 YAML 原始值，
尚未乘 `dt`。绑定时 scale 为 `0.0` 的 key 会被删除；非零 key 会准备并乘
`dt`，但 `termination` 会从普通 reward-function list 中显式跳过，在普通
loop 和 positive clipping 后单独加入。全局注册/非零 scale 不代表 raw reward 每一步都非零。
当前 `reward_penalty_curriculum=false`，不会额外乘 curriculum
scale。resolved 实验 override 可能改变这些 baseline 值。`PASS (static)` 只代表
静态代码/配置核对通过。

## 16 个 registered-global / conditional-global reward

| reward term | YAML scale（pre-dt） | 注册/当前计算 | 当前作用（大白话） |
|---|---:|---|---|
| `penalty_dof_acc` | `-1.0e-5` | 注册全局、非零；raw 随 arm 加速度变化 | 手臂不要突然猛加速。 |
| `penalty_dof_vel` | `-1.0e-3` | 注册全局、非零；raw 随 arm 速度变化 | 手臂 `arm_j1..j6` 不要高速甩动。 |
| `penalty_delta_action_rate` | `-0.01` | 注册全局、非零；只看 6D arm delta | 相邻手臂 action 不要大跳变。 |
| `termination` | `-1000.0` | 注册全局、普通 reward loop 跳过，后置单独加入；raw=`reset_buf & ~time_out_buf` | raw 为真才罚：例如 StagedTaskBase 的 stage overtime 会设 reset、但不设 `time_out_buf`；普通 episode timeout 和 delayed completion 的 reset 有 `time_out_buf`，不收这项罚分。 |
| `limits_dof_pos` | `-5.0` | 注册全局、非零；A2 手臂位置 limit | 防止 `arm_j1..j6` 顶到软限位。 |
| `limits_gripper_primitive_action` | `-1.0` | 注册全局、raw primitive 超界才非零 | 不让 gripper primitive raw command 越界。 |
| `stage` | `+1.0` | 注册全局、非零；只看当前 stage condition（不累计） | stage1 当前基本条件满足时给流程分；不是 pregrasp-ready 判定。 |
| `complete` | `+4.0` | 注册全局、最终完成后的 conditional signal | 只在最后任务完成后给完成奖励，不推进 stage1→2。 |
| `success_save_time` | `+0.5` | 注册全局、`reset_buf & time_out_buf` 条件式 | 完成/timeout reset 且两个 flag 同时真时按剩余总时长奖励早结束；不是 stage transition。 |
| `ref_dof_legs` | `+0.25` | 注册全局、非零；随 A2 gait phase | 给四腿保持参考步态，手臂预抓时脚不要乱抬。 |
| `penalty_door_frame_contact` | `-1.0` | 注册全局、接触力条件式 | 靠近把手时身体撞门框要罚。 |
| `penalty_door_panel_contact` | `-0.1` | 注册全局、接触力条件式 | 撞门板也要付小代价。 |
| `penalty_base_command_limit` | `-1.0` | 注册全局、raw/clipped 差异条件式 | base command 超过可执行范围时罚。 |
| `penalty_undesired_contact` | `-0.2` | 注册全局、A2 非期望 body 接触条件式 | 腿、躯干和非 gripper arm 不要碰环境；gripper links 排除。 |
| `penalty_dof_overspeed` | `-0.1` | 注册全局、`arm_j1..j6` 超 **3 rad/s** 才有值 | 预抓动作太快会被罚，gripper DOF 不在此项。 |
| `orientation_control` | `-5.0` | 注册全局、按 physical pitch/roll command 条件式 | 预抓时保持机身 roll/pitch 跟随指令，别侧翻。 |

## Stage1 current reward inventory

| reward term | YAML scale（pre-dt） | 当前 stage gate / function branch | 当前作用（大白话） | 静态状态 |
|---|---:|---|---|---|
| `pregrasp_gripper_dof_pos_l1` | `+0.5` | `effective_in_stage([0,1,2,5])`；stage1 track **open target** | 把两指张开，为接近把手留出入口。 | PASS (static) |
| `gripper_handle_orientation` | `+3.0` | `effective_in_stage([1,2,3,4])`；raw `opening_alignment`/`approach_alignment` tracking | 让 gripper opening 轴和把手方向对齐，别歪着靠近。 | PASS (static) |
| `pregrasp_target_distance` | `+6.0` | `effective_in_stage(1)`；Piper TCP 到 `target_pos_source[:,1,:]` 的距离 + 速度 tracking | 把 TCP 移到 pregrasp target，且朝它移动。 | PASS (static) |
| `penalty_not_standing_still` | `-15.0` | `effective_in_stage([1,2,3])`；base command norm | 预抓时 base 尽量停住，不要边伸手边乱走。 | PASS (static) |
| `grasp` | `+0.2` | `effective_in_stage([1,2,3,4])`；stage1 分支返回 contact reward 的负绝对值 | 还没到抓握阶段就碰到把手会被罚，防止提前撞。 | PASS (static) |
| `penalty_face_door` | `-1.0` | `effective_in_stage([0,1,2])`；stage1 active | 保持身体朝门，方便 TCP 对准。 | PASS (static) |
| `penalty_base_roll_pitch_l2` | `-2.0` | `effective_in_stage([0,1,4,5])`；stage1 active | 防止预抓时机身前后/左右倾倒。 | PASS (static) |
| `penalty_a2_stage1_stage2_base_forward_creep` | `-1.5` | `effective_in_stage([1,2])`；deadband `0.05`、scale config `0.10` | stage1/2 不要用 base 向门继续蹭近，逼着 arm 完成 reach。 | PASS (static) |
| `penalty_unused_dof_deviation_l1` | `0.0` | YAML placeholder；绑定前删除 | Piper 只有一只 arm，没有“另一只手”可约束；当前不产生 reward。 | PASS disabled |

stage1 不调用的相关项也保持明确：`grasp_finger_dof_pos_l1=0.0`（A2
返回 zeros）、`penalty_a2_stage2_single_finger_contact=0.0`（只给 stage2
placeholder）、`push_door_force=0.0`（A2 force branch disabled）；close、
hinge、swing、through 项在本 stage 没有 stage gate。

## Stage1 condition 与 Stage1→2 transition（不是 reward）

| 事件 | 当前 source 条件 | 说明 |
|---|---|---|
| Stage1 reward condition | `_stage_1_reward_condition()` = physical base command `norm[:3] <= 0.1` 且继续满足 Stage0→1 staging boundary | 只表示 base 在安全 pregrasp 窗口，不等于 TCP 已到位。 |
| Stage0→1 前置 boundary | root（z 换成 target z）到 `grasp_target.x - 0.70` 的 staging 点 `<0.10m`，`arm_j1..j6` 相对 default pose 最大偏差 `<0.10rad` | 这是进入 stage1 的前置 gate；不要使用旧 raw-target `0.6m`/arm `0.25rad` 描述。 |
| Stage1→2 | `_get_a2_stage1_pregrasp_ready_mask()`：TCP→pregrasp distance **`<0.10m`**；raw `opening_alignment >= 0.8`；raw `approach_alignment >= 0.8`；physical base command `norm[:3] <=0.1`；actual `arm_j7/arm_j8` 都在 open/close target span 外扩 25% 内。 | **严格只走 pregrasp-ready**。当前没有 door-open bypass；门铰链角只保留为 diagnostics mask，不能把 stage1 绕进 stage2。 |
| Stage2 completion | 由 stage2 的 H=5 contact/squeeze history 决定 | stage1→2 不检查 handle contact 或 grasp completion；进入 stage2 后才开始 close/contact gate。 |

`actual_time_in_stage_buf` 的 stage1→2 检查由 staged framework 在 reset 防护后
调用。上表和当前 source/config 是静态事实；stage1 dwell、route 比例、reward
magnitude 和训练成功率仍需独立 runtime 验证。
