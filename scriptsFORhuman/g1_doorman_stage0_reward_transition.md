# G1 Doorman Stage0 Reward 与 Stage Transition 摘要

本文只总结原版 G1/HOMIE Doorman 的 stage0 逻辑，用于后续 A2+Piper stage0 training 设计参考。source-of-truth 来自只读 baseline worktree：

- Env: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- Reward config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- Stage base: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/base_task/staged_task_base.py`
- Env config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/env/door_open_homie.yaml`

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
| `walk_to_door` | `+5.0` | 是，`STAGE_WALK_TO_DOOR` only | 计算 robot root 指向 door root 的方向，目标速度为 `target_root_vel * target_dir`，默认 `target_root_vel=0.3`；对 `norm(current_root_vel - target_vel)` 做 Gaussian tracking reward，`std=0.15` | 主任务 shaping：鼓励 G1 沿门方向移动，而不是原地摆手或乱走 | PASS |
| `penalty_upper_body_non_finger_deviation_l1` | `-1.0` | 是，stage0 与 stage5 | 上身非手指 DOF 相对 `resting_dof_pos` 的 L1 deviation sum | 行走阶段保持上身/手臂收敛在 resting pose，避免还没到门前就提前抬手干扰 locomotion | PASS -> `penalty_upper_body_non_gripper_deviation_l1` |
| `pregrasp_finger_dof_pos_l1` | `+1.5` | 是，stage0、stage1、stage5 | 根据 `door_open_lr` 选择操作侧手指，跟踪 finger primitive `pos_0` 及对应 finger velocity shaping，最后 clamp 到 `<=1.0` | 虽然名字带 `pregrasp`，stage0 也在用：让操作侧手指保持 pregrasp/open-like 初始姿态，为后续靠近把手做准备 | PASS -> `pregrasp_gripper_dof_pos_l1` |
| `penalty_face_door` | `-1.0` | 是，stage0、stage1、stage2、stage5 | 使用 robot root 到 door frame 的 relative rotation，惩罚 `axis_angle` norm | 鼓励 base 朝向门，减少侧身或背对门走到目标点导致下一阶段 pregrasp 困难 | PASS |
| `stage` | `+1.0` | 是 | `_reward_stage()` 对当前 stage 的 reward condition 给常数 stage reward；stage0 condition 恒 True，且 `stage_reward_scale[0]=1.0` | flow reward，不是 pure alive bonus；在 stage0 中只要处于合法 stage，就给小正奖励 | PASS |
| `penalty_dof_acc` | `-1.0e-5` | 是，全局 | 上身非手指 DOF acceleration squared sum | 平滑上身动作，降低抖动 | PASS -> A2 non-gripper `arm_j1..arm_j6` |
| `penalty_dof_vel` | `-1.0e-3` | 是，全局 | 上身非手指 DOF velocity squared sum | 抑制上身非手指关节高速运动 | PASS -> A2 non-gripper `arm_j1..arm_j6` |
| `penalty_delta_action_rate` | `-0.01` | 是，全局 | delta action buffer 的 squared sum | 抑制 high-level delta action 大幅跳变 | PASS：当前 A2 `delta_action_indices=[3..8]`，仅做 Piper `arm_j1..arm_j6` 的 6D delta action smoothing，不覆盖 base/gripper |
| `limits_dof_pos` | `-5.0` | 是，全局 | 上身非手指 DOF 超出 soft joint position limit 的 violation sum | 防止上身关节靠近/越过 limit | PASS -> A2 non-gripper `arm_j1..arm_j6` |
| `limits_primitive_action` | `-1.0` | 是，全局 | finger primitive action over-limit buffer sum | 防止手指 primitive action 超界 | PASS -> `limits_gripper_primitive_action`：raw A2 gripper primitive over-limit，不混用 actual gripper joint pose |
| `penalty_humanly_dof_limit` | `-1.0` | 是，全局 | 全身 DOF 相对 humanly lower/upper limit 的 violation sum | 限制 G1 姿态在人形可接受范围内 | PASS -> `ref_dof_legs`：LMP gait ref prior，A2 weight `0.25` |
| `penalty_door_frame_contact` | `-0.1` | 是，全局 | door frame unwanted contact sensor force norm sum | stage0 靠近门时避免撞门框 | PASS |
| `penalty_door_panel_contact` | `-0.1` | 是，全局 | door panel unwanted contact sensor force norm sum | stage0 靠近门时避免撞门板 | PASS |
| `penalty_homie_action_limit` | `-1.0` | 是，全局 | unclipped HOMIE command 与 clipped command 的 squared difference | 惩罚超出 HOMIE command clip range 的 base command | PASS -> `penalty_base_command_limit` |
| `penalty_undesired_contact` | `-0.2` | 是，全局 | penalised contact bodies force norm `>1` 的计数 | 避免非期望身体部位接触环境 | PASS -> A2-specific `penalize_contacts_on` + exact match，覆盖 trunk、leg links 与 non-gripper arm links，排除 feet/gripper links |
| `penalty_dof_overspeed` | `-0.1` | 是，全局 | 上身非手指 DOF velocity 超过 `2.0` 后的 squared excess | 防止上身关节过速 | PASS -> A2 non-gripper `arm_j1..arm_j6` |
| `penalty_upright` | `-1.0` | 是，全局 | torso up vector 与 world up `[0,0,1]` 的 squared error | 保持躯干直立，避免摔倒或倾斜走到门前 | PASS -> `orientation_control`：LMP-style pitch/roll command tracking，scale `-5.0` |
| `termination` | `-1000.0` | 条件式，全局 | `reset_buf` 触发时加 termination penalty；在 reward clipping 后单独加入 | 对失败 reset 给强负反馈 | PASS with A2/LMP adjustments：base min height `0.3`、bad_orientation angle `0.9`、overspeed 只检查 Piper `arm_j1..arm_j6` |

## A2 当前迁移摘要

- `penalty_delta_action_rate` 不改运行逻辑：A2 stage0/global 语义是对 `delta_action_indices=[3..8]` 的 6D arm delta action smoothing，也就是 Piper `arm_j1..arm_j6`，不覆盖 base command 或 gripper primitive。
- `penalty_upright` 不再 active；A2 使用 LMP-style `orientation_control`，从 `_a2_body_pitch_roll_raw` 读取 pitch/roll command，经 `body_pitch_roll_scale` 缩放后构造 desired gravity XY，当前 10D high-level action 暂未输出 pitch/roll，因此该 buffer 默认 zero。
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
| root 与 grasp target 距离 | 取 robot root position，并把 `root_pos.z` 替换为 `grasp_target.z` 后计算 3D norm | `(root_pos - grasp_target).norm() < 0.3`；因为 z 被替换，本质是水平/平面距离阈值 | 判断 base 是否已经走到把手附近，可以开始 pregrasp |
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
