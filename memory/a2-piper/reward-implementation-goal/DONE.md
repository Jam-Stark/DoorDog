# DONE

- 2026-07-02 18:41 HKT - 完成 gripper effort `30N` single-variable ablation config。

  (1) 用户已重新训练/eval `restrictPre-Grasp_v2` reproduction control config，并确认行为与原 `restrictPre-Grasp_v2` 一致。

  (2) 本次只将 A2 Piper gripper `arm_j7/j8` effort limit 从 `10.0` 改为 `30.0`；Kp/Kd 保持 v2 actual-equivalent（`arm_j1..j5=80/4`、`arm_j6=60/3`、`arm_j7/j8=40/1`）。

  (3) Stage0 staging offset 仍为 config `0.70`，online handle height 仍为 `0.85~0.95m`；reward、gate、stage transition、gripper primitive 与 complete predicate 均未改变。

  (4) PPO smoke 未跑；该 change 只服务下一轮 `30N` ablation retrain/eval。

- 2026-07-02 16:17 HKT - 完成 `restrictPre-Grasp_v2` reproduction control config rollback 记录。

  (1) Stage0 staging offset 通过 config 回到 `0.70`，不是 hardcode。

  (2) Online door handle height range 通过 `DoorSpawnerCfg.door_handle_tblr=(0.95, 0.85, 0.08, 0.15)` 恢复为 `0.85~0.95m`。

  (3) A2 Piper yaml actuator 数值回到 v2 actual-equivalent，同时保留 yaml-driven routing：`arm_j1..j5=80/4`、`arm_j6=60/3`、`arm_j7/j8=40/1`、gripper effort `10.0`。

  (4) Reward、gate、stage transition、gripper primitive 与 complete predicate 均未改变；PPO smoke 未跑。

- 2026-07-01 21:55 HKT - 完成 Stage0 Staging Offset + Door Handle Height Randomization 的 reward/transition 相关记录。

  (1) Stage0 walk reward、stage0->1 transition 与 `vis_stage0_target` 现在统一使用 env config `a2_stage0_staging_x_offset=0.50`，替代旧 hardcoded 70cm staging distance。

  (2) Online `DoorSpawnerCfg.door_handle_tblr` height range 改为 `(TOP=1.35, BOTTOM=0.80)`，`spawn_door()` 仍使用 `uniform(bottom, top)`；这会扩大 stage1/2 pregrasp/grasp target 高度分布，用于逼迫 policy 学 arm reach，而不是单一固定高度下用 base/trunk 蹭近。

  (3) Static validation 已完成：py_compile、Hydra compose full/stage0-2 config、no-sim source sanity 与 `git diff --check` 均通过。Runtime/PPO smoke 按用户指令跳过。

- 2026-07-01 19:17 HKT - 修复 A2_Piper actual actuator yaml routing 的 IsaacLab configclass runtime crash。

  (1) 用户训练 traceback 显示 `ArticulationCfg.validate()` 在 `__instancecheck__` 中递归到 `RecursionError`；root cause 是 A2 branch 把 Hydra/OmegaConf `ListConfig` 直接传给 `ImplicitActuatorCfg.joint_names_expr`。

  (2) `gr00t/rl/simulator/isaacsim/isaacsim.py` 现在在 IsaacLab config boundary 将 `robot_config.dof_names` 转为 plain `list[str]`，并将 `dof_effort_limit_list`、`dof_vel_limit_list`、`dof_armature_list`、`dof_joint_friction_list` 转为 plain `list[float]` 后再构造 per-DOF dict。

  (3) 这是 container type correction，不改变 A2_Piper actuator 数值语义；当前 gripper actual setting 仍为 `arm_j7/j8 Kp=80.0, Kd=1.0, effort_limit_sim=30.0`。

- 2026-07-01 19:05 HKT - 完成 A2_Piper actual IsaacSim actuator yaml routing 修正。

  (1) `gr00t/rl/simulator/isaacsim/isaacsim.py` 的 `robot_type == "a2_piper"` branch 不再 hardcode `ImplicitActuatorCfg` Kp/Kd，而是从 `robot.control.stiffness` / `robot.control.damping` 解析到 exact per-DOF dict。

  (2) 解析规则 fail-fast：leg DOF 只允许 `hip/thigh/calf` group key，Piper arm/gripper 只允许 exact `arm_j1..arm_j8` key；missing key、unused key、unexpected DOF name 或 per-DOF list length mismatch 都直接 raise。

  (3) A2_Piper actual actuator 的 `effort_limit_sim`、`velocity_limit_sim`、`armature`、`friction` 也从 robot yaml per-DOF lists 进入 `ImplicitActuatorCfg`，不再用 hardcoded A2 branch values；non-A2 branch 不变。

  (4) `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 将 gripper `arm_j7/j8` effort limit 从 `10.0` 改为 `30.0`；当前 resolved actual gripper setting 为 `arm_j7/j8 Kp=80.0, Kd=1.0, effort_limit_sim=30.0`。

  (5) 纠正实验解释：`restrictPre-Grasp_upKP1000` / `restrictPre-Grasp_KP80` 之前的 stiffness trial 只改变 saved config 和 computed diagnostic torque，不是 actual IsaacSim implicit actuator gain 的有效 A/B；后续 contact-force 结论必须基于本修正后的 retrain/eval。

- 2026-07-01 13:50 HKT - 完成 `logs_eval/restrictPre-Grasp_upKP1000` stiffness trial 结论记录与 robot stiffness 调整。

  (1) upKP1000 eval 仍为 `episode_goal_reached=[false,false]` / `stage_overtime`，因此高 stiffness trial 没有解决 formal grasp。

  (2) env0 terminal force 约 `[0.217, 0.635]`，trace 中 `both force > 1.0` 为 0；env1 contact force 全程为 0 且 primitive 保持 open。高 stiffness 没有稳定提高到 both-contact/squeeze history threshold。

  (3) 当前配置回退 arm stiffness 到上一版 arm values：`arm_j1=64.0`、`arm_j2=128.0`、`arm_j3=64.0`、`arm_j4=64.0`、`arm_j5=64.0`、`arm_j6=64.0`；只把 gripper `arm_j7/j8` 调到 80.0 做中间夹持力 trial。Damping/Kd 不变。

  (4) Reward/primitive 方向保持不变：grasp-stage 后续仍应从 aperture/contact/force/stability 设计入手，而不是奖励 fully closed target 或继续整体提高 arm stiffness。

- 2026-06-30 22:00 HKT - 完成 A2_Piper arm/gripper stiffness calibration trial。

  (1) `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 中 shoulder `arm_j2` stiffness 改为 168.0。

  (2) 其余 Piper arm/gripper joints `arm_j1, arm_j3, arm_j4, arm_j5, arm_j6, arm_j7, arm_j8` stiffness 改为 128.0。

  (3) Damping/Kd 不改；leg stiffness/damping 不改；effort limits 不改。

  (4) 这是 actuator force scale calibration：旧 `arm_j7/j8 stiffness=40.0` 配合约 1cm close error 只产生约 0.4N 级 P-control effort，解释了 `restrictPre-Grasp_v2` contact force `<1N`。后续仍需用 runtime/eval 判断 force、squeeze、completion predicate、抖动和 over-force 风险。

- 2026-06-30 21:47 HKT - 完成 `logs_eval/restrictPre-Grasp_v2` 的 Stage2 reward runtime 结论记录。

  (1) 这次 eval 不是 formal success：`episode_goal_reached=[false,false]`，terminal reason 均为 `stage_overtime`。

  (2) Reward fix 的有效进展是明确的：stage2 内 close gate、center-Y、handle-distance tracking 都已明显改善，`gripper_primitive_raw` 持续 close，视频上出现 grasp-like clamp / 双侧弱接触。

  (3) Formal complete 失败点是 contact force / squeeze history 不够：`both force > 1.0` 为 0 帧，completion predicate frames 为 0，`min(abs(squeeze_y))` 最高约 0.419 / 0.472，未满足 5-step history threshold。

  (4) Reward design 方向更新：当前 blocker 更可能来自 1D binary gripper primitive 太简单、close/aperture/contact-force/stability shaping 不足，或 close/contact dynamics 不足；下一步设计应优先考虑 continuous aperture primitive、primitive rate/hysteresis、bilateral squeeze/contact-force reward 与 force stability / over-force penalty，避免 grasp 阶段继续奖励 fully closed target。

- 2026-06-30 19:31 HKT - 完成 Stage0 Arm Default Pose Fix（A2_Piper 主线 memory 记录）。

  (1) `penalty_upper_body_non_gripper_deviation_l1` 现在对 A2 `arm_j1..arm_j6` track robot `default_dof_pos`，不再 track env `resting_dof_pos`；`-5.0` scale 只保留为 historical shaping mitigation，不再是最新/final state。

  (2) A2 reset exact-resets `arm_j1..arm_j6` 到 `default_dof_pos`；legs 继续 randomized，gripper 继续走既有 default randomization。

  (3) `_stage_0_to_1_advance_condition()` 的 arm stability 改为 default pose check，阈值来自 config `a2_stage0_arm_default_max_deviation: 0.10`。

  (4) `DeltaActionBase` 新增 no-op delta-action override hook；`DoorPregrasp` A2 override 在 stage0 将 arm delta buffer action dims `[5..10]` 清零，使 robot moving 期间 arm 维持 default pose。Stage1+ arm reaching 不被该 gate 禁用。

  (5) Static validation 与 independent review PASS。PPO/IsaacSim smoke 未跑，runtime 行为留给后续 retrain/eval 验证。

- 2026-06-30 18:53 HKT - 完成 Stage2 Grasp Target Tracking Reward Fix（FacePos70/restrictPre-Grasp diagnosis 后）。

  (1) `stage2_close_gate_y_tol` 从 0.012 放宽到 0.022；`stage2_close_gate_z_tol=0.015` 与 `stage2_close_gate_x_tol=0.02` 不变。

  (2) 新增 env config：`a2_stage2_handle_center_y_std: 0.015`、`a2_stage2_handle_approach_xz_std: 0.05`、`a2_grasp_target_distance_std: 0.05`、`a2_stage2_single_finger_contact_force_threshold: 1.0`。

  (3) `a2_stage2_handle_center_y` reward scale 从 3.0 提升到 6.0；`a2_stage2_handle_center_y` 与 `a2_stage2_handle_approach_xz` 现在贯穿 `STAGE_GRASP`，不再被 `~close_gate` mask。

  (4) A2 `grasp_target_distance` 改用 `a2_grasp_target_distance_std`；non-A2/G1 path 保持旧 std 0.1。

  (5) 新增 `penalty_a2_stage2_single_finger_contact: -2.0`，stage2 only，使用 existing `_get_a2_gripper_handle_contact_forces()`，仅 exactly one gripper body contact norm 超过 threshold 时返回 1；未加入 `reward_penalty_reward_names`。

  (6) Validation/review：py_compile PASS、git diff --check PASS、pure-Python no-sim formula sanity PASS、independent review PASS。PPO smoke 按用户指令跳过，用户将直接开始 training。

- 2026-06-30 15:00 HKT - 完成 axis-aware stage2 close gate + `a2_stage2_handle_center_y` / `a2_stage2_handle_approach_xz` tracking rewards（A2_Piper 主线）。Close gate 从 L2 norm `<0.015` 改为 per-axis `abs()` with per-axis tolerances（`stage2_close_gate_y_tol=0.012`、`z_tol=0.015`、`x_tol=0.02`）。新 rewards gated by `~close_gate`，scale `3.0/3.0`，std `0.05/0.05`，加入 `reward_penalty_reward_names`。改动文件：`door_open_a2_base.yaml`、`reward_door_open_a2_base.yaml`、`door_open_a2_base.py`。Oracle review PASS，py_compile OK。Rationale：FacePos70 eval L2 gate 无法区分 lateral Y offset（2.2cm, opening axis）与 approach depth，policy 停滞 handle 旁、124 帧单指接触、0 帧 both_contact。

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
- 2026-06-17 00:00 HKT - 新增 stage1+ human docs：`scriptsFORhuman/g1_doorman_transition_correctness_a2_adaptation.md` 记录 staged transition correctness source facts、A2 PASS/TODO 边界与 primary blockers；`scriptsFORhuman/g1_doorman_stage1_reward_adaptation.md` 记录 stage1 reward term mapping、当时未完成项、baseline/global reward 与后续检查建议。
- 2026-06-17 16:25 HKT - 将 A2 `pregrasp_gripper_dof_pos_l1` scale 从 `1.5` 调整为 `0.5`，并在 stage1 checklist 与 memory 中记录 binary gripper primitive 下该 term 仅作低权重 baseline；continuous aperture primitive 后再重设 reward。
- 2026-06-17 16:47 HKT - 将 A2 `_stage_0_to_1_advance_condition()` root-to-handle 平面距离阈值从 `0.3m` 调整为 `0.6m`，并在 transition/stage0/stage1 human docs 中记录原因：G1 直立人形和 A2 四足机器狗的 root footprint 不同，A2 需要更远的 approach boundary 以避免 base/trunk 撞门。
- 2026-06-17 18:43 HKT - 完成 A2 `gripper_handle_orientation` reward metric implementation/review：config 启用 `gripper_handle_orientation: 3.0`，旧 `hand_handle_orientation` 不在 A2 reward YAML / `reward_penalty_reward_names` active path；`penalty_unused_dof_deviation_l1` 记录为 one-arm Piper 不适用并保持 scale `0.0`。Transition correctness 未完成，后续 `_stage_1_to_2_advance_condition()` 仍需接入 raw orientation metrics。
- 2026-06-17 19:37 HKT - 完成 A2 `pregrasp_target_distance` reward metric implementation/review：A2 path 使用 `piper_gripper_handle_frame_transformer` 的 `target_pos_source[:, 1, :]` 计算 Piper TCP 到 pregrasp target distance，使用 `target_pos_w[:, 1, :] - source_pos_w` 和 `simulator._rigid_body_vel[:, end_effector_index, :3]` 做 velocity shaping；config 启用 scale `6.0`，stage `[1]` 与 `reward_penalty_reward_names` membership 保持 origin semantics；缺 sensor/target/config/velocity source 时 fail-fast，不使用 G1 palm/finger fallback。当时 transition correctness 与 `grasp` 尚未完成；19:56 HKT `grasp` reward metric 已完成。
- 2026-06-17 19:56 HKT - 完成 A2 `grasp` reward metric implementation/review：新增 handle-specific `ContactSensor` 读取 `/door_handle` 对 `arm_body7` / `arm_body8` 的 contact force，A2 `_reward_grasp()` 将 world force 旋到 Piper TCP/source frame，使用 source local `+Y` 作为 gripper opening/closing force axis；stage1 惩罚任何 handle contact magnitude，stage2+ 用 two-sided `min` contact reward 并惩罚 off-axis force；config 启用 `grasp: 0.2` 并保留 positive shaping curriculum membership。Transition correctness 与 stage2 completion 尚未完成。
- 2026-06-17 20:34 HKT - 完成 A2 `_stage_1_to_2_advance_condition()` implementation review：A2 branch 最终条件为 `pregrasp_ready | door_open_bypass`；`pregrasp_ready` 使用 Piper TCP/pregrasp distance `<0.1m`、raw `opening_alignment >= 0.8`、raw `approach_alignment >= 0.8`、base command norm `<=0.1`、以及 `arm_j7/arm_j8` actual DOF 位于 open/close target 外扩 25% span 内。Reviewer 将 gripper span guard 改为 fail-fast raise，保留 door-open bypass OR，未加入 above-handle、handle contact、grasp completion、stage0 condition、G1 palm/finger fallback，也未改 stage2 completion 或 reward YAML。
- 2026-06-17 20:52 HKT - 新增 stage2 human-facing checklist：`scriptsFORhuman/g1_doorman_stage2_reward_completion_a2_adaptation.md` 记录 G1 stage2 reward/completion source facts、A2 当前 reward metric / placeholder 边界、Piper grasp completion 设计输入、不要照搬 G1 finger/contact 的风险、建议施工顺序与 human 验收项。该文档仅完成 planning/visibility，A2 `_stage_2_to_complete_condition()` implementation 仍是 P0。
- 2026-06-17 21:21 HKT - 完成 A2 `_stage_2_to_complete_condition()` implementation review：A2 branch 不再 all false，使用 `_get_a2_gripper_handle_contact_forces()` 的 `(num_envs, 2, 3)` handle-specific `arm_body7` / `arm_body8` force，fail-fast 校验 `source_quat_w` shape `(num_envs, 4)`，按 `_reward_grasp()` 同样方式旋到 Piper source/TCP frame；completion boolean 为 `both_contact` (`norm(forces_w)>1.0`)、`sufficient_squeeze` (`abs(source local Y)>0.5`) 与 `opposite_squeeze` (`Y` force signs opposite) 的 AND。`_stage_2_to_3_advance_condition()` 继续保持 completion OR door-open bypass，未改 G1 branch、reward YAML、stage3/open reward。
- 2026-06-17 22:06 HKT - 更新 stage2 reward docs/memory：`grasp_finger_dof_pos_l1` 继续 disabled/deferred，未来等 continuous aperture primitive 后再设计 aperture/contact-aware reward；`grasp_target_distance` 计划提交 Ava 审核，拟用 `piper_gripper_handle_frame_transformer.data.target_pos_source[:, 0, :]` 作为 Piper TCP/source 到 handle target 的 distance。
- 2026-06-17 22:11 HKT - 完成 A2 `grasp_target_distance` reward metric implementation review：A2 path 不再返回 zeros，读取 `piper_gripper_handle_frame_transformer.data.target_pos_source` 并 fail-fast 校验 shape `(num_envs, 2, 3)`，使用 target index `0` (`handle`) 作为 Piper TCP/source 到 handle vector，按 `std=0.1`、`target=0.0`、`scale=1.0` tracking reward 计算；reward YAML 启用 `grasp_target_distance: 3.0` 并保留 `reward_penalty_reward_names` membership。`grasp_finger_dof_pos_l1` 继续 `0.0` / A2 zeros，保持 PASS disabled/deferred。
- 2026-06-17 22:34 HKT - Main + Ava + independent reviewer 三方确认：A2 stage2 reward completion / A2 adaptation 可记录为 `static PASS`；stage2 静态层面没有必须补齐的 blocker。`_stage_2_to_3_advance_condition()` 保持 G1-equivalent `completion | door_open_bypass`，不需要立即修改；下一步转入 bounded smoke 与 stage3/open reward completion/A2 adaptation。
- 2026-06-17 22:41 HKT - 新增 stage3/open human-facing checklist：`scriptsFORhuman/g1_doorman_stage3_reward_completion_a2_adaptation.md`，记录 G1 `STAGE_OPEN=3`、stage3 reward/advance source facts、A2 reward term mapping、`push_door_force` 不可照搬 G1 hand/world-X force 的风险，以及建议施工顺序。
- 2026-06-25 20:30 HKT - 从 `quickTEST` branch 合并回 A2_Piper 主线 B 类 reward/predicate 改动：`_stage_2_to_complete_condition()` contact history gate（`stage2_grasp_contact_history_length: 5`）、`a2_stage2_close_command` / `a2_stage2_close_progress` stage2 close shaping rewards、`pregrasp_gripper_dof_pos_l1` stage-aware target（stage0 close / stage1 open）、`penalty_base_roll_pitch_l2: -2.0`。详见 `quicktest-merge` entry。
- 2026-06-29 16:00 HKT - 完成静态核查 door asset `doorOpenIO` 字段对 hinge joint sign / reward routing 的影响：`doorOpenIO` 在 origin G1 与 A2 door.py 中只赋值、写 metadata、读取到 env，不参与任何 hinge joint 构造、joint axis/sign/limit、reward routing 或 stage condition。hinge joint 对 in/out 门物理构造完全相同。G1 实际只训推门（out），`push_door_force` 的 world -x 对拉门恒为 0。详见 `memory/a2-piper/door-asset-openio-sign/` entry。
- 2026-06-29 17:00 HKT - Stage3 reward completion / A2 adaptation 确认 `static PASS`：所有 stage3 active reward terms（`stage` / `push_door_handle` / `push_door_hinge` / `push_door_force` / `grasp` / `grasp_target_distance` / `gripper_handle_orientation` / `grasp_finger_dof_pos_l1` / `penalty_not_standing_still` / `penalty_unused_dof_deviation_l1` / `penalty_face_door` / door frame/panel contact penalties）不需要改 code。静态验证 door articulation joint index 0=hinge、1=handle，hinge/handle joint 方向正确（开门=正角度增长）。`push_door_force` 保持 disabled。`gripper_handle_orientation` 确认 offset 动态跟随 handle Z 轴。
- 2026-06-29 20:10 HKT - 新增 stage4/swing human-facing checklist：`scriptsFORhuman/g1_doorman_stage4_reward_completion_a2_adaptation.md`。
- 2026-06-29 20:10 HKT - Stage4 第一批 reward adaptation：`stage` / `dont_push_door_handle` / `push_door_hinge` 确认与 robot 无关直接 PASS；`target_root_distance` 的 `target_root_pos` z 从 `0.72` 改为 `0.5`（匹配 A2 trunk 高度），改动文件 `gr00t/rl/config/env/door_open_a2_base.yaml` line 122。
- 2026-06-29 21:00 HKT - Stage4 剩余 reward terms Oracle 独立核查 PASS：`penalty_standing_still` / `grasp` / `grasp_target_distance` / `gripper_handle_orientation` / `penalty_unused_dof_deviation_l1`(disabled) / `grasp_finger_dof_pos_l1`(disabled) / `penalty_door_frame_contact` / `penalty_door_panel_contact` 全部不需要改 code。Stage4 静态 code work 完成。
- 2026-06-29 21:00 HKT - Stage3-5 transition conditions 核查完成：`_stage_3_reward_condition()` / `_stage_3_to_4_advance_condition()` / `_stage_4_reward_condition()` / `_stage_4_to_5_advance_condition()` / `_stage_5_reward_condition()` / `_stage_5_to_complete_condition()` 全部与 G1 origin 逐字节一致，不需要改 code。只依赖 door joint state 和 robot root x 位置，都是 robot-agnostic。
- 2026-06-29 21:00 HKT - Stage4 checklist 清理完成：移除 4 个 stage4 不生效的 terms，同步 z=0.5 已完成标记。
- 2026-06-29 21:30 HKT - Stage5/through reward adaptation：(1) `pregrasp_gripper_dof_pos_l1` 修正 stage5 track close target——新增 `is_through`，`track_close = is_walk | is_through`，修复 gate_mask 从 `track_open.float()` 改为 `(track_close | track_open).float()`，stage0/5 现在真正主动奖励 gripper 收起。(2) `penalty_face_door` stage5 disabled——`effective_in_stage` 从 `[0,1,2,5]` 改为 `[0,1,2]`。Oracle review PASS。
- 2026-06-30 14:05 HKT - `penalty_upper_body_non_gripper_deviation_l1` scale 从 `-1.0` 改为 `-5.0`。Reason: FacePos70 eval videos 显示 stage0（walk to door）中 robot arm 漂移，-1.0 相对 walk_to_door（+5.0）太弱，无法抑制 arm drift。-5.0 使 arm 抑制成为有意义的 counterweight。Oracle review PASS with caveat。该项后来被 2026-06-30 19:31 的 `default_dof_pos` target + stage0 action gate root-cause fix supersede；`-5.0` 只保留为 historical shaping mitigation。改动文件：`gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` line 24。
