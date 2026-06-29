# G1 Doorman Stage0 Reward 与 Stage Transition 摘要

本文总结原版 G1/HOMIE Doorman 的 stage0 逻辑及 A2+Piper 的当前适配状态。source-of-truth 来自只读 baseline worktree 与 A2_Piper worktree：

- G1 Env: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- G1 Reward config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- G1 Stage base: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/base_task/staged_task_base.py`
- G1 Env config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/env/door_open_homie.yaml`
- A2 Env: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`
- A2 Reward config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`
- A2 Env config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/env/door_open_a2_base.yaml`

> **最后更新：2026-06-29 21:30 HKT** — 已根据当前 A2 code/YAML 同步。

## Stage0 定义

| 项目 | G1 Doorman 原始设计 |
|---|---|
| stage index | `STAGE_WALK_TO_DOOR = 0` |
| stage 语义 | walk to the door，即 robot base 走到 door/handle 的 grasp target 附近 |
| stage0 max time | `max_stage_time[0] = 250` sim/control steps；`reset_on_overtime=True` |
| stage0 reward condition | `_stage_0_reward_condition()` 恒为 True，所以只要 env 处于 stage0，stage reward 条件一直满足 |
| stage transition source | `_stage_0_to_1_advance_condition()`，由 `StagedTaskBase._post_compute_observations_callback()` 统一检查并推进 `stage_buf += 1` |

## Stage0 实际生效 Reward 表

> 备注：YAML 中非零 reward scale 在 runtime 会先乘以 `dt`；`reward_penalty_reward_names` 中的部分 shaping reward 还会乘 `reward_penalty_scale` curriculum。表中 scale 是 YAML 原始值，便于和 config 对照。

| Reward term | YAML scale | Stage0 是否生效 | 计算逻辑摘要 | 作用 | A2适配状态 |
|---|---:|---|---|---|---|
| `walk_to_door` | `+5.0` | 是，`STAGE_WALK_TO_DOOR` only | G1: root → door root 方向 velocity tracking。A2: root → `grasp_target` 前方 0.5m staging position 方向 velocity tracking，`std=0.15` | 主任务 shaping：鼓励 robot 走到 handle 前方 | PASS baseline：A2 改为指向 staging position 而非 door root，给 arm 留 reach 空间 |
| `penalty_upper_body_non_gripper_deviation_l1` | `-1.0` | 是，stage0 与 stage5 | A2: `_upper_non_gripper_dof_idx`（arm_j1..j6）相对 `resting_dof_pos` 的 L1 deviation sum | 行走时手臂保持 resting pose | PASS：A2 排除 arm_j7/arm_j8 gripper |
| `pregrasp_gripper_dof_pos_l1` | `+0.5` | 是，stages `[0,1,2,5]` | A2: stage0/5 track close target（gripper 收起），stage1/2-gate-outside track open target；`gate_mask=(track_close\|track_open).float()`，stage0/5 gate_mask=1 真正主动给 reward | stage0 gripper 收起 shaping | PASS baseline：scale 从 G1 `1.5` 降为 `0.5`；stages 从 G1 `[0,1,5]` 扩展为 `[0,1,2,5]`；gate_mask 已修复 |
| `penalty_face_door` | `-1.0` | 是，stages `[0,1,2]` | A2: `relative_door_rot_buf` full rotation penalty | 鼓励 base 朝向门 | PASS baseline：stage5 已移除（从 `[0,1,2,5]` 改为 `[0,1,2]`） |
| `penalty_base_roll_pitch_l2` | `-2.0` | 是，stages `[0,1]` | A2 新增项：`self.rpy[:, 0:2]`（actual base roll/pitch）L2 norm | 防止 A2 行走/接近门时 trunk 过度倾斜 | PASS baseline：A2-specific，无 G1 对应项 |
| `stage` | `+1.0` | 是 | StagedTaskBase flow reward | flow reward | PASS carrier |
| `penalty_dof_acc` | `-1.0e-5` | 是，全局 | DOF acceleration squared sum | 平滑动作 | PASS → A2 non-gripper `arm_j1..arm_j6` |
| `penalty_dof_vel` | `-1.0e-3` | 是，全局 | DOF velocity squared sum | 抑制高速运动 | PASS → A2 non-gripper `arm_j1..arm_j6` |
| `penalty_delta_action_rate` | `-0.01` | 是，全局 | delta action squared sum | 抑制 action 跳变 | PASS：A2 `delta_action_indices=[5..10]`，仅 Piper `arm_j1..arm_j6` |
| `limits_dof_pos` | `-5.0` | 是，全局 | DOF soft limit violation sum | 防止关节超限 | PASS → A2 non-gripper `arm_j1..arm_j6` |
| `limits_gripper_primitive_action` | `-1.0` | 是，全局 | A2 raw gripper primitive over-limit | 防止 primitive action 超界 | PASS：A2 replacement for G1 `limits_primitive_action` |
| `ref_dof_legs` | `+0.25` | 是，全局 | LMP-style gait ref prior | 保持步态参考 | PASS：A2 replacement for G1 `penalty_humanly_dof_limit` |
| `penalty_door_frame_contact` | `-0.1` | 是，全局 | door frame contact sensor force norm sum | 避免撞门框 | PASS |
| `penalty_door_panel_contact` | `-0.1` | 是，全局 | door panel contact sensor force norm sum | 避免撞门板 | PASS |
| `penalty_base_command_limit` | `-1.0` | 是，全局 | unclipped vs clipped base command squared diff | 惩罚 base command 超限 | PASS：A2 replacement for G1 `penalty_homie_action_limit` |
| `penalty_undesired_contact` | `-0.2` | 是，全局 | A2-specific contact bodies force norm `>1` count | 避免非期望接触 | PASS：A2 exact-match，覆盖 trunk/leg/non-gripper arm，排除 feet/gripper |
| `penalty_dof_overspeed` | `-0.1` | 是，全局 | DOF velocity 超过 2.0 的 squared excess | 防止过速 | PASS → A2 non-gripper `arm_j1..arm_j6` |
| `orientation_control` | `-5.0` | 是，全局 | LMP-style pitch/roll command tracking | 保持躯干稳定 | PASS：A2 replacement for G1 `penalty_upright` |
| `termination` | `-1000.0` | 条件式，全局 | reset 时 termination penalty | 失败惩罚 | PASS：A2 height `0.3`、bad orientation `0.9`、arm overspeed 只检查 `arm_j1..j6` |

## A2 当前迁移摘要

- `penalty_delta_action_rate` 不改运行逻辑：A2 stage0/global 语义是对 `delta_action_indices=[5..10]` 的 6D arm delta action smoothing，也就是 Piper `arm_j1..arm_j6`，不覆盖 5D base command 或 gripper primitive。
- `penalty_upright` 不再 active；A2 使用 LMP-style `orientation_control`，从 5D physical base command tensor 的 `[pitch, roll]` 读取姿态命令；对应 Teacher obs public term 为 `a2_base_command`，经 `body_pitch_roll_scale=0.4` 缩放语义构造 desired gravity XY。当前 12D high-level action 已输出 pitch/roll raw dims `[3:5]`。
- `termination` 对齐 A2/LMP：`termination_min_base_height=0.3`，显式 bad orientation check 使用 `acos(-projected_gravity[:,2]) > 0.9`，arm DOF overspeed 继续只覆盖 `_upper_non_gripper_dof_idx` / Piper `arm_j1..arm_j6`，排除 gripper `arm_j7/arm_j8`。

## Stage0 配置了但通常不是 Stage0 驱动信号的项

| Reward term | 原因 |
|---|---|
| `hand_handle_orientation`、`pregrasp_target_distance`、`penalty_not_standing_still` | 这些是 stage1/pregrasp 或之后的 reward，decorator 不包含 stage0 |
| `grasp_*`、`push_door_*`、`dont_push_door_handle`、`target_root_distance`、`penalty_standing_still` | 对应 grasp/open/swing/through 阶段，stage0 decorator 不生效 |
| `complete`、`success_save_time` | 这是全任务 complete 之后的奖励，不是 stage0 -> stage1 的判定奖励；stage0 transition 不靠它触发 |
| `transition`、`penalty_overtime`、`penalty_upper_body_dof_vel`、`penalty_homie_action_rate` | 在 YAML 中被注释掉，当前 reward config 不启用 |

## Stage0 如何判断任务完成并进入 Stage1

| 判断项 | 原版逻辑 | 阈值/细节 | 作用 |
|---|---|---|---|
| grasp target 来源 | `_compute_grasp_target()` 读取 `right_hand_frame_transformer.data.target_pos_w[:, 0, :]`，对应 door `grasp_target` frame | Env config 中 `target_obj_transform_sub_prim_path: "grasp_target"` | stage0 不是对 door root 终点判定，而是对 handle/grasp target 附近的位置判定 |
| root 与 grasp target 距离 | 取 robot root position，并把 `root_pos.z` 替换为 `grasp_target.z` 后计算 3D norm | G1 origin 为 `<0.3m`；A2 当前改为 `<0.6m`，因为 A2 四足 base/trunk footprint 比 G1 直立人形更长，`0.3m` 会诱导 trunk 贴门/撞门；因为 z 被替换，本质是水平/平面距离阈值 | 判断 base 是否已经走到把手附近，可以开始 pregrasp；A2 还需 smoke 检查 Piper reach envelope 与 false-positive |
| 上身保持 resting pose | 对 `_upper_non_finger_dof_idx` 计算 `abs(dof_pos - resting_dof_pos).max()` | `max_deviation < 0.25` rad | 防止靠近过程中提前抬手或上身偏离太大；只有“走到门前且手还收着”才进入下一阶段 |
| reset 后不立刻 advance | `StagedTaskBase` 会执行 `advance_mask &= ~just_resetted_buf` | reset 当步即使条件满足也不会推进 stage | 避免 staged reset 或初始状态导致误触发 advance |
| advance 行为 | 条件满足且当前 `stage_buf == 0` 时，`stage_buf += 1`，`actual_time_in_stage_buf=0`；因为 `award_remaining_time_on_advance=True`，`time_in_stage_buf` 会扣掉当前 stage 最大时长 | stage0 -> stage1，即进入 `STAGE_PREGRASP` | stage0 的“完成”在训练 runtime 中就是 transition 到 stage1，不等于全任务 complete |
| overtime 行为 | 若一直未满足 advance，`time_in_stage_buf >= max_stage_time[stage_buf]` 且 `reset_on_overtime=True` | stage0 最多 `250` step | 超时 reset，避免 episode 卡在无法到达门前的状态 |

## 对 A2+Piper 迁移的直接启发

| G1 stage0 设计点 | A2+Piper 迁移含义 |
|---|---|
| 主 reward 是 base velocity tracking toward door/target | A2 stage0 仍可保留“base command/velocity 朝 door handle target”的 shaping，但需要用 A2 base/root 与 Piper handle target frame 重算 |
| 上身非手指保持 resting pose 是 transition 的硬条件 | A2+Piper 应替换为 Piper arm 接近初始 folded/rest pose 或 safe carry pose 的条件，不能沿用 G1 upper body index |
| finger pregrasp 姿态在 stage0 已被轻微 shaping | Piper gripper 可对应为 stage0 open/default primitive 或安全 open pose，后续再决定是否作为 reward 或 action prior |
| face door penalty 是 stage0 的关键姿态约束 | A2 base yaw/heading 与 door frame 的对齐应保留，否则 quadruped 可能平移到目标点但身体朝向不利于机械臂操作 |
| stage0 transition 用 grasp target planar distance + arm rest condition | A2 版本建议先保留“base 到 handle/grasp target 的 planar distance”思想，再把 arm rest condition 改成 Piper-specific joint/EE readiness |
