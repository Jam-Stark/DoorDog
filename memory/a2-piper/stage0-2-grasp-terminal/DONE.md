# DONE

- 2026-07-02 21:31 HKT - 完成 arm Kp/Kd ablation config。

  (1) `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 将 `arm_j7/j8` effort limit 从 `30.0/30.0` 回退到 `10.0/10.0`。

  (2) Actual arm Kp/Kd 改为：`arm_j1=64/3`、`arm_j2=128/4.5`、`arm_j3=64/3`、`arm_j4=64/3`、`arm_j5=64/3`、`arm_j6=64/3`；`arm_j7/j8` 保持 `40/1`。

  (3) Stage0 offset、online handle height、reward/gate、stage transition、gripper primitive 与 complete predicate 均未改；目标是基于 `replay_v2` baseline 重新训练/评估 softer/lower-damped arm dynamics 对 stage1 reach vs base creep 与 stage2 grasp tracking 的影响。

  (4) Validation: YAML sanity PASS，`git diff --check` PASS，read-only Oracle-style review PASS；当前 shell 缺少 `hydra` module，未跑 Hydra compose。未跑 PPO/IsaacSim smoke。

- 2026-07-02 21:23 HKT - 完成 `logs_eval/base_v0` effort-only ablation 诊断。

  (1) Saved training config 与 `replay_v2` 递归 diff 仅有 experiment/output path 和 `robot.dof_effort_limit_list[18/19] 10.0 -> 30.0`。

  (2) Eval 结果为负向分叉：`episode_goal_reached=[false,false]`，terminal reason 均为 `stage_overtime`，episode rewards 从 `replay_v2` 的约 `102-105` 降到约 `71-82`。

  (3) `stage2_step_trace.json` 显示 `base_v0` 两条 env 的 `gripper_primitive_raw` 全程 positive/open，contact force 与 squeeze 全程 0；env0 虽有 279/330 帧 close gate 但未学会 close command，env1 close gate 0/310。

  (4) 结论：`30N` effort limit 不是当前 sufficient fix；下一步应回到 gripper primitive / close-stage shaping 与 stage1/base-creep 约束设计，不继续把 blocker 归因于单纯夹持力上限不足。

- 2026-07-02 18:51 HKT - 完成 stage0-2 train/eval log cleanup。

  (1) `logs_eval` 只保留 `replay_v2`，删除其他 historical eval records。

  (2) `logs_rl/a2_piper_stage0_2_grasp_terminal_a2_base` 只保留 `replay_v2-20260702_162608`，删除其他 historical training records。

  (3) 后续 stage0-2 ablation training/eval 以 `replay_v2` 为 baseline，逐个变量做对照。

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

- 2026-07-01 21:55 HKT - 完成 Stage0 Staging Offset + Door Handle Height Randomization。

  (1) `gr00t/rl/config/env/door_open_a2_base.yaml` 新增 `a2_stage0_staging_x_offset: 0.50`，`DoorPregrasp` 的 stage0 walk reward、stage0->1 advance condition 与 `vis_stage0_target` 都通过同一个 fail-fast config helper 读取该 offset，不再 hardcode `0.70`。

  (2) `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` 的 online `DoorSpawnerCfg.door_handle_tblr` 从 `(0.95, 0.85, 0.08, 0.15)` 改为 `(1.35, 0.80, 0.08, 0.15)`；`spawn_door()` 仍按 `uniform(bottom, top)` 采样 height，因此实际范围为 `0.80~1.35m`。Offline generator 未改，避免误扩 scope。

  (3) Validation: `py_compile` PASS；Hydra compose full A2 与 stage0-2 quick config 均解析出 `a2_stage0_staging_x_offset=0.50`；no-sim source sanity 确认 `door_handle_tblr` 与 `uniform(bottom, top)` semantics；`git diff --check` PASS。PPO/IsaacSim smoke 按用户指令未跑。

- 2026-07-01 19:17 HKT - 修复 A2_Piper actuator yaml routing 导致的 env construction `RecursionError`。

  (1) 训练 traceback 的 crash 点是 `Articulation(robot_articulation_config)` 内部调用 `ArticulationCfg.validate()`；root cause 是 `ImplicitActuatorCfg.joint_names_expr` 收到了 Hydra/OmegaConf `ListConfig`。

  (2) `gr00t/rl/simulator/isaacsim/isaacsim.py` 现在在构造 A2_Piper `ImplicitActuatorCfg` 前，把 `robot_config.dof_names` 转为 plain `list[str]`，把 per-DOF effort/velocity/armature/friction lists 转为 plain `list[float]`，避免 OmegaConf container 泄漏进 IsaacLab configclass validation。

  (3) Actual actuator 数值语义不变：gripper `arm_j7/j8` 仍为 `Kp=80.0, Kd=1.0, effort_limit_sim=30.0`；下一轮 retrain/eval 仍应基于 19:05 的 yaml actuator routing 结论重新判断 contact force / squeeze。

- 2026-07-01 19:05 HKT - 完成 A2_Piper actual IsaacSim actuator yaml routing 修正。

  (1) `gr00t/rl/simulator/isaacsim/isaacsim.py` 的 A2_Piper `ImplicitActuatorCfg` 不再使用 hardcoded leg/arm/gripper Kp/Kd/limits，而是从 `a2_piper.yaml` 生成 exact per-DOF actuator config。

  (2) `stiffness/damping` 使用 fail-fast mapping：leg DOF 解析到 `hip/thigh/calf` group key，Piper arm/gripper 解析到 exact `arm_j1..arm_j8`；missing/unused/unexpected key 直接报错。

  (3) `effort_limit_sim/velocity_limit_sim/armature/friction` 使用 robot yaml per-DOF lists；gripper `arm_j7/j8` effort limit 从 `10.0` 改为 `30.0`。

  (4) `restrictPre-Grasp_upKP1000` 和 `restrictPre-Grasp_KP80` 的相同 trace/checkpoint state 应解释为之前 yaml stiffness 没进入 actual IsaacSim implicit actuator；旧 trial 不是 actual actuator Kp/Kd A/B。后续 stage0-2 grasp retrain/eval 需要基于本修正重新判断 contact force、squeeze 与 base-creep/arm-reaching behavior。

- 2026-07-01 13:50 HKT - 完成 `logs_eval/restrictPre-Grasp_upKP1000` stiffness trial 诊断与回退调整。

  (1) upKP1000 eval 仍是 `episode_goal_reached=[false,false]`，terminal reason 均为 `stage_overtime`，因此不能记录为 formal grasp success。

  (2) env0 terminal contact force 约为 `[0.217, 0.635]`，trace 中 `both force > 1.0` 为 0；env1 contact force 全程为 0，且 `gripper_primitive_raw` 保持 positive/open。整体提高 arm/gripper stiffness 没有把 contact force / squeeze 推到 `_stage_2_to_complete_condition()` 阈值。

  (3) 用户从视频观察到 stage1 仍倾向 base 往前靠近 handle，而不是主要伸 arm reach grasp target；高 arm stiffness 可能让 arm tracking 更昂贵或更僵硬，不适合继续整体加硬 arm。

  (4) `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 已回退 arm stiffness：`arm_j1=64.0`、`arm_j2=128.0`、`arm_j3=64.0`、`arm_j4=64.0`、`arm_j5=64.0`、`arm_j6=64.0`；gripper `arm_j7/j8` 改为 80.0 做中间夹持力 trial。Damping/Kd、leg stiffness/damping、effort limits 不改。

- 2026-06-30 22:00 HKT - 完成 A2_Piper arm/gripper stiffness calibration trial。

  (1) `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 中 shoulder `arm_j2` stiffness 改为 168.0。

  (2) 其余 Piper arm/gripper joints `arm_j1, arm_j3, arm_j4, arm_j5, arm_j6, arm_j7, arm_j8` stiffness 改为 128.0。

  (3) Damping/Kd 暂不改；leg stiffness/damping 不改；effort limits 不改。

  (4) Rationale: `restrictPre-Grasp_v2` 中 gripper close error 约 1cm，旧 `arm_j7/j8 stiffness=40.0` 在 P-control 下只会产生约 0.4N 级 effort，与 trace contact force `<1N` 对齐，未表达 Piper 官方 40N 夹持能力。该 trial 先验证更高 Kp 是否能把 contact force / squeeze 推到 success predicate 区间，同时 watch contact chatter / over-force。

- 2026-06-30 21:47 HKT - 完成 `logs_eval/restrictPre-Grasp_v2` 的 Stage2 Grasp Target Tracking Reward Fix runtime 诊断记录。

  (1) metrics 结果仍是 `episode_goal_reached=[false,false]`，terminal reason 均为 `stage_overtime`，因此不能记录为正式 env complete success。

  (2) stage2 trace 显示 reward fix 已基本解决 grasp target tracking：stage2 non-negative timer 内两条 env 都是 101/101 帧在 close gate 内；`target_pos_source_handle` 的 abs-Y p95 约 0.0049 / 0.0038；末端 handle distance 约 0.0058 / 0.0088；`gripper_primitive_raw` stage2 内保持 negative close command，没有 open/close sign flip。

  (3) 视频上可见 grasp-like clamp / 双侧弱接触，但 completion predicate 仍未满足：`both force > 1.0` 为 0 帧，predicate frames 为 0；`min(abs(squeeze_y))` 最大约 0.419 / 0.472，低于 `abs(squeeze_y)>0.5` threshold，且没有 5-step two-sided contact history。

  (4) 当前结论：Stage2 reward 修改已经把 policy 从单侧 Y offset / target drift 推到比较准确的 handle center close attempt；剩余 blocker 更可能来自 1D binary gripper primitive 太简单、close/aperture/force/stability shaping 不足，或 gripper close/contact dynamics 不足。后续方案应优先考虑 continuous aperture primitive、primitive rate/hysteresis、bilateral squeeze/contact-force reward 与 force stability / over-force penalty，而不是继续改 grasp_target 位置。

- 2026-06-30 19:31 HKT - 完成 Stage0 Arm Default Pose Fix（stage0-2 relevant memory 记录）。

  (1) Stage0 arm drift 的 current root-cause fix 是 `default_dof_pos` target + stage0 action gate；14:05 的 `penalty_upper_body_non_gripper_deviation_l1: -5.0` 只作为 historical shaping mitigation 保留。

  (2) `penalty_upper_body_non_gripper_deviation_l1` 对 A2 `arm_j1..arm_j6` track robot `default_dof_pos`；A2 reset exact-resets `arm_j1..arm_j6` 到 `default_dof_pos`，legs randomized 与 gripper default randomization 保持原有行为。

  (3) `_stage_0_to_1_advance_condition()` arm stability 改为 default pose check，并使用 config `a2_stage0_arm_default_max_deviation: 0.10`。

  (4) `DeltaActionBase` 新增 no-op delta-action override hook；`DoorPregrasp` A2 override 在 stage0 清零 arm delta buffer action dims `[5..10]`，避免 robot moving 时 arm drift。Stage1+ arm reaching 不被该 gate 禁用。

  (5) Static validation 与 independent review PASS。PPO/IsaacSim smoke 未跑，后续 stage0-2 retrain/eval 需验证 arm default 保持、stage1 reaching 和 grasp terminal path。

- 2026-06-30 18:53 HKT - 完成 Stage2 Grasp Target Tracking Reward Fix（FacePos70/restrictPre-Grasp diagnosis 后，A2_Piper 主线）。

  (1) `stage2_close_gate_y_tol` 从 0.012 放宽到 0.022；`stage2_close_gate_z_tol=0.015` 与 `stage2_close_gate_x_tol=0.02` 不变。

  (2) 新增 env config：`a2_stage2_handle_center_y_std: 0.015`、`a2_stage2_handle_approach_xz_std: 0.05`、`a2_grasp_target_distance_std: 0.05`、`a2_stage2_single_finger_contact_force_threshold: 1.0`。

  (3) `a2_stage2_handle_center_y` reward scale 从 3.0 提升到 6.0；`a2_stage2_handle_center_y` 与 `a2_stage2_handle_approach_xz` 改为整个 `STAGE_GRASP` 持续 active，不再被 `~close_gate` mask。

  (4) A2 `grasp_target_distance` 改用 `a2_grasp_target_distance_std`；non-A2/G1 path 保持旧 std 0.1。

  (5) 新增 `penalty_a2_stage2_single_finger_contact: -2.0`，stage2 only，复用 `_get_a2_gripper_handle_contact_forces()`；只有 exactly one gripper body contact norm 超过 threshold 时返回 1。该 penalty 不加入 `reward_penalty_reward_names`。

  (6) Validation/review 已完成：py_compile PASS、git diff --check PASS、pure-Python no-sim formula sanity PASS、independent review PASS。PPO smoke 按用户指令跳过，因为用户将直接启动 training。

- 2026-06-30 15:00 HKT - 完成 axis-aware stage2 close gate + 两个新 stage2 tracking rewards（A2_Piper 主线，非 quickTEST）。

  (1) close gate 从 L2 norm `norm(target_pos_source[:,0,:]) < 0.015` 改为 per-axis `abs()` checks：`abs(Y) < stage2_close_gate_y_tol(0.012)`、`abs(Z) < stage2_close_gate_z_tol(0.015)`、`abs(X) < stage2_close_gate_x_tol(0.02)`。Config keys 在 `door_open_a2_base.yaml`。

  (2) 新增两个 stage2 tracking rewards（outside close gate）：`a2_stage2_handle_center_y`（scale 3.0, std 0.05，驱动 opening-axis Y → 0）和 `a2_stage2_handle_approach_xz`（scale 3.0, std 0.05，驱动 lateral X + approach Z → 0）。两者 gated by `~close_gate`，均加入 `reward_penalty_reward_names` 用于 curriculum。

  (3) 改动文件：`gr00t/rl/config/env/door_open_a2_base.yaml`、`gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`、`gr00t/rl/envs/door/door_open_a2_base.py`。

  (4) Oracle review PASS，py_compile OK。No-sim formula sanity 验证：centered handle → max reward；FacePos70 [0.005, 0.022, 0.011] → gate False（Y 超 y_tol=0.012），center_y reward=0.9077，approach_xz reward=0.9856。

  (5) 动机：FacePos70 eval 视频显示 L2 gate + L2 reward 无法区分 lateral Y offset（2.2cm, opening axis）与 approach depth，policy 在 handle 旁停滞、124 帧单指接触、0 帧 both_contact。

- 2026-06-29 15:00 HKT - 完成 walk_to_door staging position + stage0→1 advance condition 修改。walk_to_door target 从 grasp_target 改为 grasp_target+(-0.40,0,0)（handle 前方 40cm staging pos），advance condition 从 `(root_pos-grasp_target).norm<0.6` 改为 `(root_pos-stage0_target).norm<0.1`。原条件太松（0.6m 就转换，base Y 差 4-5cm 没对齐 handle），新条件强制 base 到 staging pos 10cm 内才转换。同时改了 arm init joint state：j2 1.48→0, j3 -0.63→0, j4 -0.84→0.25, j5 0→0.5（yaml+USD 三处同步）。pregrasp_distance 阈值从 0.03 改回 0.1（0.03 太紧导致 stage1 overtime）。memory 记录了原值和新值方便恢复。

- 2026-06-28 01:30 HKT - 撤销 grasp_target capsule 改动，改回 handle_inside（X=-axle_length/2）。01:00 错误地改为 handle_outside，用户从 eval 视频确认 inside 是正确的 grasp handle。教训：grasp_target capsule 选择必须以 eval 视频物理交互为准，不能只靠几何推理。camera offset 远离 50cm 保留。

- 2026-06-28 01:00 HKT - 完成 grasp_target capsule correction + camera offset tuning。grasp_target 从 handle_inside（X=-axle_length/2, 门内侧杆）改到 handle_outside（X=+axle_length/2, 门外侧杆）。原因：gripper 从 +X（门外侧）approach，grasp_target 应在外侧杆；原选内侧杆导致 pregrasp 落在门板位置（X≈0），gripper 被迫侧滑绕过门板。改后 pregrasp 在门外侧（X≈+0.20），gripper 可直前 approach。诊断：grasp_target 位置不影响 finger 碰到哪条杆（contact sensor 测整个 door_handle prim），只影响 approach 路径 + close gate hd + reward 方向。camera handle_top eye [0,0,0.15]→[0,0,0.65]、handle_side eye [0,0.12,0.02]→[0,0.62,0.02]，远离 50cm 以看清 pregrasp 阶段相对位置。py_compile 通过。

- 2026-06-26 22:00 HKT - 完成 multi-camera eval rendering 实现：新增 2 个 additional cameras（handle_top ego-view + handle_side depth-view）与既有 main eval camera 同时渲染。所有 camera 通过一次 sim.render() 输出，各自写入独立 mp4。isaacsim.py 创建 `self.eval_cameras: dict[str, TiledCamera]`（always 含 "main" + additional），legged_robot_base.py render_results 改为 3-phase（set all poses→single sim.render()→per-camera update+write），新 camera_mode handle_top_down/handle_side 用 lever center（grasp_target pos_w）做 anchor，A2 override `_get_handle_anchor_pos`。base_task.yaml 加 optional `additional_cameras` list。Backward compatible：无 additional_cameras 时仅有 main camera，filename/行为不变。py_compile 通过。runtime eval 验证待跑。

- 2026-06-26 20:30 HKT - 完成 grasp_target 位置修正根因诊断与修复。诊断链：eval trace 分析→contact 仅出现于 open approach 阶段，close 全程 contact=0；gripper 几何确认 finger 仅前伸 3.1cm 而非预估 12cm；door asset 几何计算确认 grasp_target 距 handle_inside 胶囊中心 X 方向 -4.5 ~ -6 cm（偏门板）、Z 方向 +2 cm（把手上方）。修复：set_prim_transform X -0.15→-axle_length/2、Z door_handle_height+0.02→door_handle_height；FixedJoint LocalPos1 同步改为 Gf.Vec3f(-axle_length/2, -handle_length/2*lr, 0.0)。Z +0.02 移除的原因是 G1-hand approach-space preference，Piper 2-finger 只需正中夹持 lever center。随机化完全跟踪各轴参数（axle_length、handle_length、door_handle_height），无 residual mean-error。auto-correct 效果：grasp_target_distance/pregrasp_target_distance/stage1→2 advance/stage2 close gate 现在都量 lever center 而非偏 4.5-6cm 的点。旧 checkpoint 无效，需 retrain。py_compile 通过。

- 2026-06-26 01:00 HKT - 完成 `_reward_pregrasp_gripper_dof_pos_l1` stage2 gate 外 open tracking 扩展（方案 B）：将 reward 的 `effective_in_stage` 从 `[STAGE_WALK_TO_DOOR, STAGE_PREGRASP, STAGE_THROUGH]` 扩展到包含 `STAGE_GRASP`。A2 branch 在 stage2 时调用 `_get_a2_stage2_close_reward_gate()`，gate 外（handle_dist ≥ 0.015）track `open_target`（gripper 保持张开前伸），gate 内 return 0（交给 `a2_stage2_close_command` / `a2_stage2_close_progress` 引导闭合）。non-A2 branch 保持原行为。诊断依据：两组新训练 eval（addSTIFF + CONSTRAIN）均进入 stage2 且 handle_dist < 1cm，但 gripper_primitive ≈ -1.1（close），contact force = 0——gripper 在 stage2 gate 外提前闭合，闭合的 gripper 无法真正夹住 handle。`py_compile` 通过；未改 close rewards 公式、complete predicate、contact history gate、stage transition、reset、camera、render timing 或 action semantics。
- 2026-06-26 00:50 HKT - 完成 Piper arm stiffness/damping 调整：`gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 中 arm_j2 stiffness `80.0`→`128.0`、damping `4.0`→`3.0`；arm_j1/j3/j4/j5/j6 stiffness `80.0`/`60.0`→`64.0`、damping `4.0`/`3.0`→`1.5`；arm_j7/j8（gripper）保持不变。目的：让 arm 更硬，更好靠近 pregrasp target。
- 2026-06-26 00:50 HKT - 完成 pregrasp_distance 阈值放宽→改回：`_stage_1_to_2_advance_condition` 中 `pregrasp_distance` 阈值从 `< 0.1` 放宽到 `< 0.15`（commit on quickTEST），后改回 `< 0.1`。对比 eval 发现 addSTIFF 组（未放宽，仅 stiffness）也能进入 stage2，说明 stiffness/damping 调整已足够帮助 arm 靠近 pregrasp target，不需要放宽阈值。
- 2026-06-26 00:40 HKT - 完成两组对比 eval 诊断：`stage2_finished_grasp_OPEN_addSTIFF-20260625_231407`（仅 stiffness/damping，pregrasp_distance 保持 0.1）与 `stage2_finished_grasp_OPEN_constrain-20260625_231959`（stiffness/damping + pregrasp_distance 放宽到 0.15）的 ckpt2000 eval 均进入 stage2（`episode_max_stage_reached=[2,2]`），handle_dist < 1cm，但 `goal_reached=false`，terminal reason 均为 stage_overtime。两组表现接近，gripper_primitive ≈ -1.1（close），contact force = 0。结论：stiffness/damping 调整帮助 arm 进入 stage2，但 gripper 过早闭合问题仍未解决。
- 2026-06-25 23:30 HKT - 完成 pregraspFIX eval 诊断：`stage2_finished_pregraspFIX` eval 显示 `episode_max_stage_reached=[1,1]`，policy 从未进入 stage2，`stage2_step_trace.json` 为空。Terminal 时 pregrasp_dist=0.103/0.123（刚好超过 0.1 阈值），handle_dist=0.077/0.108。根因：pregrasp target 修复后（handle 上方→前方），policy 需要学会往前伸臂到 pregrasp target 10cm 以内，但训练不足。
- 2026-06-25 20:30 HKT - **完成 quickTEST → A2_Piper 主线 fast-forward merge**：A2_Piper HEAD 推进到 quickTEST HEAD `34e06b7`，随后新增 cleanup commit `2a7fa3e` 删除 C 类 stage0-2 专属文件（本 config + 本 memory entry）并更新主线 memory。A 类通用 bugfix（OrderedTargetFrameTransformer、A2_Base init、ResetFromDataset、PPO recurrent unsplit、TorchScript 持有、staged_task_base last-stage complete gate、eval rendering/diagnostics、toolbar patch、JSON serialization fix）与 B 类通用增强（stage2 contact history gate、stage2 close shaping rewards、pregrasp stage-aware target、penalty_base_roll_pitch_l2）已全部保留在主线。主线新增 `memory/a2-piper/quicktest-merge/` entry 记录完整合并清单。独立子 agent 审核结果 APPROVED。**后续 quickTEST 新更新 merge 回主线时，只需 merge `34e06b7` 之后的新 commit。**
- 2026-06-25 17:30 HKT - 完成 `_get_a2_stage2_close_reward_gate` handle_distance 阈值收紧：从 `< 0.03`（3cm）改为 `< 0.015`（1.5cm），防止 `a2_stage2_close_command` / `a2_stage2_close_progress` 在 gripper 还未真正贴近 handle 时过早触发。诊断依据：`stage2_finished_grasp_OPEN-20260625_105101/last.pt` eval trace 显示 env0 在 handle_dist=0.062（gate 外）时 prim 已从 0.349 转为 -0.001 开始闭合，gate 首次触发（dist=0.0255）时 prim 已为 -0.927（已闭合）；env1 同样在 gate 外提前闭合。`py_compile` 通过；未改 stage2 close rewards 公式、complete predicate、contact history gate、stage transition、reset、camera、render timing 或 action semantics。
- 2026-06-25 10:40 HKT - 完成 `_reward_pregrasp_gripper_dof_pos_l1` stage-aware target 修复：原实现 stage0/1 均用 `_a2_gripper_close_target`，导致 stage0/1 全程 reward gripper 闭合，policy 进入 stage2 时 gripper 已闭合，gate 内 `a2_stage2_close_*` 无法形成"张开→闭合"真实抓取。修复后 stage0（STAGE_WALK_TO_DOOR）track `close_target`（行走时收起），stage1（STAGE_PREGRASP）track `open_target`（准备抓取），span 统一用 `open_target - close_target`。`py_compile` 通过；未改 stage2 close rewards、complete predicate、contact history gate、stage transition、reset、camera、render timing 或 action semantics。
- 2026-06-25 10:30 HKT - 完成最新训练 checkpoint `stage2_finished_grasp-20260624_225622/model_step_003000.pt` 的 720p eval recording：输出目录 `logs_eval/a2_stage0_2_eval_stage2_finished_grasp_ckpt3000_720p/`，`metrics_eval.json` 与 `stage2_step_trace.json` 均可解析。两个 mp4 为 `env0000_len351_reason-stage_overtime` 与 `env0001_len452_reason-stage_overtime`，均为 720p、fps 20。trace 显示 stage2 全程 `gripper_primitive_raw ∈ [-1.2, -0.93]`（close），`arm_j7/j8_pos ≈ [0.005, -0.000001]`（接近 close_target），handle_distance 最小 0.0015m（gate 内），但 contact force 全程为 0——闭合 gripper 撞向 handle 但未夹住。诊断结论：`pregrasp_gripper_dof_pos_l1` 在 stage0/1 reward close 是 gripper 不张开的根因。
- 2026-06-22 20:29 HKT - 创建独立 memory entry `stage0-2-grasp-terminal`，记录 quickTEST 分支的 stage0-2-only training 目标、stage2 terminal success 语义、与 full 6-stage task 的边界。
- 2026-06-22 20:42 HKT - 新增独立 quick test config `gr00t/rl/config/exp/wbmanip/door_open_a2_base_stage0_2_grasp_terminal_lstm.yaml`，入口为 `+exp=wbmanip/door_open_a2_base_stage0_2_grasp_terminal_lstm`，保持默认 full 6-stage config 不变。
- 2026-06-22 20:42 HKT - 完成 Hydra static validation：resolved config 为 3-stage `max_stage_time/stage_reward_scale/staged_reset_ratios`，`reset_on_complete_delay: 0`，stage3+ reward scales 为 `0.0`，`obs_dims.stage: 3`。
- 2026-06-22 21:23 HKT - 完成 frozen A2_Base TorchScript non-registered trainer fix review：`PolicyAndValueWrapper` 通过 `_a2_base_model` 普通 attribute 持有 TorchScript model，并以 property 暴露访问，避免 HuggingFace Trainer optimizer parameter scanning 把 frozen A2_Base 纳入 module tree。
- 2026-06-22 21:23 HKT - validation 结果：`py_compile` 通过；lightweight probe 确认 A2_Base TorchScript 不出现在 `named_children()` / `named_modules()` / `named_parameters()`；bounded smoke 已到 `Using frozen A2_Base policy for low-level leg actions` 与 `===training policy===`，旧 optimizer `ParameterDict contains()` crash 未复现。
- 2026-06-22 21:31 HKT - 修正 `piper_gripper_handle_frame_transformer` target order blocker：新增 A2-local `OrderedTargetFrameTransformer`，保留 `FrameTransformerCfg.target_frames` 中 `handle -> pregrasp` 的顺序，避免 IsaacLab duplicate target body 使用 `set` 导致 runtime `target_frame_names` 变成 `['pregrasp', 'handle']`；原 A2 exact-order fail-fast check 保留。
- 2026-06-22 21:31 HKT - validation 结果：`py_compile` 通过；single-GPU stage0-2 bounded smoke 完成 scene sensors initialization 并进入 `reset_all()`，未再触发 target-order fail-fast；新 blocker 是 `a2_base.py::_get_obs_a_history_homie()` 访问缺失的 `_homie_history_length`。
- 2026-06-22 21:35 HKT - 修正 `a_history_homie` reset observation blocker：在 A2_Base init path 中显式读取 `obs.homie_history_length` 到 `_homie_history_length`，并 fail-fast 校验该 key 存在且为正数；不使用默认值 fallback。
- 2026-06-22 21:35 HKT - validation 结果：`py_compile` 通过；single-GPU stage0-2 bounded smoke 已越过 `_get_obs_a_history_homie()`，进入 `_post_compute_observations_callback()`；新 blocker 是 `ResetFromDataset._post_compute_observations_callback()` 访问缺失的 `reset_count`。
- 2026-06-22 21:37 HKT - 完成 `ResetFromDataset.reset_count` diagnosis/fix step：将 `ResetFromDataset` 初始化体拆为 `_init_reset_from_dataset()`，并在 A2 `DoorPregrasp` branch 显式调用，确认 A2 early-return 确实绕过了 cooperative MRO 中的 `ResetFromDataset.__init__()`。
- 2026-06-22 21:37 HKT - validation 结果：`py_compile` 通过；single-GPU smoke 不再以缺失 `reset_count` 失败，但暴露新 config/contract blocker：G1/LAFAN motion reset 的 dof name `left_hip_pitch_joint` 不存在于 A2 robot，因此 stage0-2 quick test 不应启用该 reset path。
- 2026-06-22 21:39 HKT - 完成 stage0-2 quick config 的 G1 `ResetFromDataset` disable fix：新增 explicit `reset_from_dataset.enabled` gate，quick experiment 覆盖为 `False`；default behavior 保持 enabled，若 A2 误开 G1 dataset reset 会继续 fail-fast 暴露 dof mismatch。
- 2026-06-22 21:39 HKT - validation 结果：`py_compile`、Hydra resolved config 与 `diff --check` 通过；single-GPU smoke 不再加载 LAFAN motion files，已进入 PPO recurrent model forward；新 blocker 是 A2_Base frozen policy injection 的 `flat_obs` / `high_level_actions` batch dimension mismatch。
- 2026-06-22 22:03 HKT - 完成 PPO recurrent A2_Base injection shape mismatch diagnosis：`RecurrentActor` / `RecurrentCritic` training path 会将 padded `memory_out` 通过 `unsplit_trajectories(..., original_dones)` 转回 env-major `[num_envs, num_steps, ...]`，因此 A2_Base frozen policy injection 也应只把 padded `a2_base_obs` unsplit 到 env-major 后再与 `high_level_actions` 对齐，PPO loss tensors 继续保持 rollout env-major layout。
- 2026-06-22 22:03 HKT - 完成最小修复 review：`ppo_trainer_a2_base_api.py::_a2_base_actions()` 在 obs/action leading shape mismatch 且提供 recurrent `masks/original_dones` 时 fail-fast 校验 layout，然后对 `a2_base_obs` 执行 `unsplit_trajectories`；未引入 repeat、trim、try/except fallback，也未把 PPO loss tensors 改成 padded layout。
- 2026-06-22 22:03 HKT - validation 结果：reviewer shape probe、`py_compile` 与 `diff --check` 通过；记录 worker small smoke 已推进到 `Learning iteration 1`。
- 2026-06-22 22:07 HKT - main-agent 复跑 1-iteration smoke：`obs_dims.stage: 3`、actor obs 130、critic obs 135、stage3+ reward scales 0.0，训练日志已打印 `Learning iteration 1`，原 `flat_obs` / `high_level_actions` shape mismatch 未复现；训练主体完成后 IsaacSim shutdown 未自然退出，已手动 Ctrl-C 清理会话。
- 2026-06-22 22:52 HKT - 完成 `OrderedTargetFrameTransformer` multi-env duplicate diagnosis review：原 blocker 来自用 runtime-expanded `frame_name` 全局判重，默认 `num_envs=4096` 时不同 env 的同名 `handle` / `pregrasp` 被误判为 duplicate。
- 2026-06-22 22:52 HKT - 完成 worker 修复 review：`target_offsets` duplicate check 已收敛到 config-level `FrameTransformerCfg.target_frames` names，true config duplicate 继续 fail-fast；`body_names_to_frames` 使用 list append 保留 cfg target order，`handle -> pregrasp` 不回退到 IsaacLab `set` 无序行为。
- 2026-06-22 22:52 HKT - validation 结果：code inspection 确认无 hidden fallback、repeat/trim/reorder 掩盖；Hydra compose resolved quick config 默认 `num_envs: 4096`；本地 `num_envs=2` run `20260622_224609` 已越过 scene sensors initialization 且未再触发 duplicate error。
- 2026-06-22 23:53 HKT - 完成 WebRTC training visualization route diagnosis：IsaacLab `AppLauncher` 支持 `LIVESTREAM`/`PUBLIC_IP` path，但 multi-rank `accelerate` 长训不应直接启用 livestream；推荐独立 single-process visual run 或 checkpoint 后 visual/eval run。
- 2026-06-22 23:59 HKT - 完成 WebRTC no-ready diagnosis：`zenity Failed to open display` 只是 headless host 上 native dialog path 的 warning；当前 readiness 失败依据是无 `49100` listening 且无 2026-06-22 livestream `start` event，后续 visual run 应清理旧进程并显式传 headless rendering kit。
- 2026-06-23 00:07 HKT - 完成 visual training toolbar blocker 修复：`train_agent_trl.py` 增加 exact guard，缺失 `omni.kit.widget.toolbar` 时仅跳过 AppLauncher optional toolbar hiding，其他 missing module 继续 fail-fast；验证通过 `py_compile` 与 `git diff --check`。
- 2026-06-23 00:13 HKT - 完成 post-toolbar WebRTC diagnosis：visual run 已越过 toolbar crash 并加载 livestream extensions，但 no `49100` listening / no current livestream start event；机器上残留多个 old visual processes 与 4-rank long training，下一步应先清理旧 visual PIDs 再复测单一 WebRTC run。
- 2026-06-23 00:19 HKT - 记录 GUI route decision：完整 GUI 调试优先走 `xpra`/remote desktop 提供 `DISPLAY`，训练命令改为 `headless=False` 且不设置 `LIVESTREAM`；WebRTC route 暂作为非首选。
- 2026-06-23 13:41 HKT - 完成 xpra startup diagnosis：`xpra start :100 --bind-tcp=0.0.0.0:14500 --html=on` 已启动 live session 且 web server 返回 HTML，但 `DISPLAY=:100 glxinfo -B` 显示 Xvfb/llvmpipe software renderer；当前 xpra session 不能作为 Isaac Sim full GUI/Vulkan 调试目标。
- 2026-06-23 19:57 HKT - 记录 checkpoint visualization route：主训练 run `20260622_233941` 已产出 `model_step_001000.pt` 到 `model_step_004000.pt`；推荐用 single-process headless eval + `simulator.config.render_results=true` 生成 observer-camera mp4，Hydra override 使用 `++headless=True`、`++num_envs=1`、`++simulator.config.render_results=true` 等 `++` 语法。
- 2026-06-23 20:03 HKT - 记录 A2 eval smoke result：`model_step_004000.pt` eval 已完成 2 episodes 并生成 `viewer_0/viewer_1` mp4；最后在 `json.dump(eval_dict)` 因 tensor/numpy value 不可序列化失败，且当前 render video 只有约 `0.1s / 5 frames`，observer camera 画面不足以判断 policy 效果。
- 2026-06-23 20:12 HKT - 完成 A2 eval metrics JSON serialization 修复：`ppo_trainer_a2_base_api.py` 写 `metrics_eval.json` 前将 metrics 显式转换为 JSON-safe data，支持 tensor/numpy/list/tuple/dict，未知对象类型仍 fail-fast 报 metrics key path；metrics 通过 temp file + `os.replace()` 写入，避免半截 JSON。
- 2026-06-23 20:12 HKT - validation 结果：`py_compile`、`git diff --check`、targeted helper smoke 均通过；最终代码版本复跑 `model_step_004000.pt` 的 2-episode eval smoke 完整写出 `logs_eval/a2_stage0_2_eval_smoke_ckpt4000/metrics_eval.json`，且 `python -m json.tool` 可解析。observer-camera mp4 仍偏短，camera/timing 作为后续单独问题处理。
- 2026-06-23 20:33 HKT - 完成 A2 Eval True-Episode Rendering Fix review：确认 per-env mp4 writer lifecycle 满足 initial frame after reset、terminal frame before reset、non-terminal rollout frames、no cross-episode stitching；`eval_rendering` 只支持 `env_static/root_tracking`，unknown mode 与缺 required key fail-fast。
- 2026-06-23 20:33 HKT - diagnostics review 结果：`metrics_eval.json` summary 覆盖 `episode_lengths`、`episode_rewards`、`episode_goal_reached`、`episode_max_stage_reached`、`episode_terminal_reasons`，terminal reason set 覆盖 `complete/stage_overtime/episode_timeout/low_height/bad_orientation/door_distance/upper_dof_overspeed/unknown_reset`；验证通过 `py_compile`、targeted `git diff --check` 与 no-IsaacSim helper smoke，完整 IsaacSim runtime smoke 仍待 main-agent 复跑确认 mp4 画面质量。
- 2026-06-23 20:44 HKT - 完成 true-episode render runtime smoke：旧 `model_step_004000.pt` checkpoint config 不含 `env.config.eval_rendering`，本次 eval 用显式 CLI override 保持 fail-fast contract；runtime 成功写出 `logs_eval/a2_stage0_2_eval_true_episode_ckpt4000/metrics_eval.json`，`python -m json.tool` 可解析。
- 2026-06-23 20:44 HKT - 修复 runtime 暴露的 recorder tail issue：trainer 现在在 completion bookkeeping 后才为 non-terminal env 写 step frame，并在 `eval_num_envs_episodes` 下过滤已完成 env；最终输出只剩 `env0000_episode0000_len5_reason-bad_orientation.mp4` 与 `env0001_episode0000_len4_reason-bad_orientation.mp4`，分别为 6/5 frames，无 `.writing.mp4` 或 `rollout_end` 尾巴视频。
- 2026-06-23 21:15 HKT - 完成 A2 Door Reset Stabilization code review：`door_open_a2_base.py` 的 A2-only `_reset_root_states()` default branch 先复制 `base_init_state` 并加 `env_origins`，再随机 x/y/yaw、清零 root vel；`target_root_states` path 委托 `A2Base._reset_root_states()` 保持 parent/fail-fast contract。A2-only `_reset_dofs()` default branch 使用 `default_dof_pos * U(0.8,1.2)` 并清零 DOF vel；`target_state` path 仍委托 parent。Non-A2/G1 reset hunk 未改旧逻辑，未引入 fallback/retry/silent clamp。
- 2026-06-23 21:15 HKT - validation 结果：`py_compile`、targeted `git diff --check`、Hydra compose quick config 均通过；resolved quick config 仍为 3-stage `max_stage_time/stage_reward_scale/staged_reset_ratios`，actor/critic obs dim 130/135。2-env headless eval smoke 输出 `logs_eval/a2_stage0_2_eval_reset_stabilized_ckpt4000/metrics_eval.json` 与两个 mp4；episode lengths `[452, 452]`，terminal reasons `["stage_overtime", "stage_overtime"]`，max stages `[2, 2]`，goal reached 均为 `false`，两个 mp4 均为 453 frames，4/5 step `bad_orientation` 未复现。
- 2026-06-23 21:27 HKT - 完成 door-top-down eval camera patch review：`eval_rendering.camera_mode` 支持并默认设为 `door_top_down`，camera anchor 为 `self.simulator.get_task_root_state("door")[:, :3]`，`camera_eye` / `camera_lookat` 保持 door-relative offset；default config 为 `camera_eye: [0.05, 0.0, 2.0]`、`camera_lookat: [0.0, 0.0, 0.0]`。缺 `eval_rendering` / required key、unknown `camera_mode`、非法 `fps` 或非 bool frame flags 均继续 fail-fast；review 未发现 camera patch 改动 reward、stage transition、reset、termination predicate 或 trainer action logic。
- 2026-06-23 21:27 HKT - validation 结果：`/home/baoquanc/anaconda3/envs/isaaclab/bin/python -m py_compile gr00t/rl/envs/legged_base_task/legged_robot_base.py` 通过；targeted `git diff --check` 通过。完整 IsaacSim runtime eval 未跑，按计划留给 main-agent。
- 2026-06-23 21:50 HKT - 完成 door-top-down runtime camera diagnosis/fix：Hydra resolved config 与 `set_world_poses_from_view()` 都已生效，但 mp4 仍旧视角的 root cause 是 IsaacLab `TiledCamera` 的 `XformPrimView` 默认只写 Fabric transform，tiled render product 需要 USD-authored camera transform。`render_results()` 现在 fail-fast 检查 camera view 暴露 `_sync_usd_on_fabric_write`，再打开 USD sync、`sim.render()`、`eval_camera.update(..., force_recompute=True)` 后读取 RGB。
- 2026-06-23 21:50 HKT - validation 结果：`py_compile` 与 targeted `git diff --check` 通过；extreme camera probe 输出 `logs_eval/a2_stage0_2_eval_camera_extreme_probe_usdsync_ckpt4000/`，preview 清楚显示 robot+door 的 oblique 新视角，证明 USD sync pose write 生效。用户指定 `[0.05,0,2]` probe 输出 `logs_eval/a2_stage0_2_eval_door_top_down_usdsync_probe_ckpt4000/`，preview 已变为 door-relative top-down，但视野太近，只能看到门/把手边缘和局部机器人，下一步需要调高或偏移 camera 参数。
- 2026-06-23 21:50 HKT - 完成 eval camera default tuning：`base_task.yaml` 的 default `env.config.eval_rendering` 保持 `camera_mode: door_top_down`，但 offsets 改为已验证的 door-root anchored 斜俯视 `camera_eye=[-2.5,-2.5,2.2]`、`camera_lookat=[-0.5,0.0,0.45]`，用于同时观察 robot、door 和 handle。
- 2026-06-23 21:58 HKT - 完成 rendering cleanup 与 full oblique eval recording：清理 `logs_eval` 下旧 `renderings/`、`previews/` 和 `camera_compare_previews/`，保留历史 `metrics_eval.json`；用 `model_step_004000.pt` 跑 2-env complete eval，输出 `logs_eval/a2_stage0_2_eval_oblique_full_ckpt4000/`。验证结果：`episode_lengths=[452,452]`、`episode_terminal_reasons=["stage_overtime","stage_overtime"]`、`episode_max_stage_reached=[2,2]`、`episode_goal_reached=[false,false]`，两个 mp4 均 453 frames，preview 显示斜俯视覆盖 robot、door 与 handle 区域。
- 2026-06-23 22:10 HKT - 完成 eval camera 720p default resolution：`gr00t/rl/config/simulator/isaacsim.yaml` 新增 `simulator.config.cameras.eval_camera_resolutions: [720,1280]`，`isaacsim.py` 的 `render_results` eval camera 不再硬编码 `256x256`，而是在 `render_results=true` 时 fail-fast 校验该 `[height,width]` 后创建 `TiledCamera`；验证通过 `py_compile`、targeted `git diff --check` 与 Hydra compose。
- 2026-06-23 22:10 HKT - 完成 720p full oblique eval recording：按用户确认清空整个 `logs_eval` 目录内容后，用 `model_step_004000.pt` 重录 `logs_eval/a2_stage0_2_eval_oblique_720p_ckpt4000/`。验证结果：两个 mp4 均 453 frames，frame shape `(720,1280,3)`；`metrics_eval.json` 可解析，`episode_lengths=[452,452]`、`episode_terminal_reasons=["stage_overtime","stage_overtime"]`、`episode_max_stage_reached=[2,2]`、`episode_goal_reached=[false,false]`；preview 显示 720p 画面比旧 256x256 明显更清晰。
- 2026-06-24 16:35 HKT - 完成最新训练 run `stage2_finished-20260623_221222/model_step_004000.pt` 的 720p door-root anchored 斜俯视 eval recording，输出目录为 `logs_eval/a2_stage0_2_eval_stage2_finished_720p_ckpt4000/`。验证结果：两个 mp4 frame shape 均为 `(720,1280,3)`，episode lengths `[83,108]`，episode terminal reasons `["complete+upper_dof_overspeed","complete"]`，episode max stage reached `[1,1]`，episode goal reached `[true,true]`；`metrics_eval.json` 可解析，并生成了 initial/mid/terminal preview frames。
- 2026-06-24 16:40 HKT - 完成 latest 720p eval grasp semantics 诊断：视频中未见 gripper 闭合与 metrics `episode_max_stage_reached=[1,1]` 一致，当前 `complete` 由未 gate 到 final stage 的 `_stage_2_to_complete_condition()` contact/squeeze predicate 触发；该 result 不能作为真实 stage2 close-grasp success。
- 2026-06-24 17:19 HKT - 完成 A2 Eval Terminal Diagnostics runtime validation：使用 `logs_rl/a2_piper_stage0_2_grasp_terminal_a2_base/stage2_finished-20260623_221222/model_step_004000.pt` 输出到 `logs_eval/a2_stage0_2_eval_stage2_finished_terminal_diag_ckpt4000`；`metrics_eval.json` 可用 `python -m json.tool` 解析，两个 720p mp4 分别为 84/109 frames，frame shape 均为 `(720,1280,3)`，top-level metrics 为 `completed_episodes=2`、`episode_lengths=[83,108]`、`episode_terminal_reasons=["complete+upper_dof_overspeed","complete"]`、`episode_max_stage_reached=[1,1]`、`episode_goal_reached=[true,true]`，`episode_terminal_diagnostics` length 为 2。
- 2026-06-24 17:19 HKT - 完成 terminal diagnostics 解释记录：diagnostics 确认 success 发生在 `stage_buf=1` 而不是 stage2；两条 episode 的 `arm_j7_j8_pos=[0.035,-0.035]`、`arm_j7_j8_close_target=[0.0,0.0]`，且 `gripper_primitive_raw` 为 positive open command，说明 gripper 仍在 open target。`handle_contact_force_norm` 与 `contact_force_arm_body7_8_norm` 在本次 terminal frames 中相等，handle-specific sensor/body mapping 未见明显 mismap；但 large contact force/squeeze 出现在 open gripper 状态，说明 current contact/squeeze complete predicate 对 open-gripper collision/contact spike 过宽，后续仍需单独修复 complete last-stage gate、gripper close/aperture 或 close-command 条件，以及 A2 stage2 gripper close shaping。
- 2026-06-24 17:36 HKT - 完成 A2 Terminal Orientation Diagnostics code implementation + static review：`DoorPregrasp._get_a2_terminal_diagnostics()` 新增 pregrasp/handle orientation alignment、source gripper quat/axes、handle/pregrasp target quat/axes/pos fields；确认 diagnostics 仍在 reset 前 capture，pregrasp alignment 复用 `_get_a2_gripper_handle_orientation_metrics()` semantics，handle alignment 对 `target_quat_source[:, 0, :]` 使用同一公式，target order 与 quat shape checks 保持 fail-fast。验证通过指定 `py_compile` 与 targeted `git diff --check`。
- 2026-06-24 17:41 HKT - 完成 A2 Terminal Orientation Diagnostics runtime eval：使用 `logs_rl/a2_piper_stage0_2_grasp_terminal_a2_base/stage2_finished-20260623_221222/model_step_004000.pt` 输出到 `logs_eval/a2_stage0_2_eval_stage2_finished_orientation_diag_ckpt4000`；`metrics_eval.json` 可用 `/home/baoquanc/anaconda3/envs/isaaclab/bin/python -m json.tool` 解析。两个 720p mp4 分别为 84/109 frames，shape 均为 `(720,1280,3)`，fps 为 20；top-level metrics 为 `completed_episodes=2`、`episode_lengths=[83,108]`、`episode_terminal_reasons=["complete+upper_dof_overspeed","complete"]`、`episode_max_stage_reached=[1,1]`、`episode_goal_reached=[true,true]`，`episode_terminal_diagnostics` length 为 2 且新增 orientation fields 均存在。
- 2026-06-24 17:41 HKT - 完成 terminal orientation 解释记录：runtime output 确认仍是同一 false-success mode，complete 在 `stage_buf=1` 触发，gripper DOFs 仍 open，primitive raw 仍为 positive open command，并伴随 large two-sided contact/squeeze。handle 与 pregrasp alignment 数值相同，原因是 pregrasp target 仅有 positional offset 且 quaternion 与 handle target 相同；`opening_alignment ~= 0.81` 勉强满足当前 stage1 opening threshold，但 `approach_alignment=-0.075/-0.039` 对应约 92-94 degree approach-axis mismatch，说明 angled open-gripper geometry 可以在 true grasp/close 前撞出 contact/squeeze。
- 2026-06-24 18:17 HKT - 完成 A2 Grasp Frame + Contact History Complete Fix implementation/static review：`handle` 与 `pregrasp` target frame rot 均为 `(0.5,0.5,0.5,0.5)`，`pregrasp` pos 保持 `(0,0,0.10)`；该 rot 按 raw `grasp_target` identity frame 映射 target X=old Y、target Y=old Z、target Z=old X。`_get_a2_gripper_handle_orientation_metrics()` formula 未改。
- 2026-06-24 18:17 HKT - 完成 ContactSensor history complete predicate review：A2 handle sensor 以 handle prim_path 为 body、`arm_body7/arm_body8` 为 filters，`force_matrix_w_history` expected shape 为 `(num_envs,H,1,2,3)`，helper 返回 `(num_envs,H,2,3)`；`stage2_grasp_contact_history_length: 5`。A2 complete 要求每个 history sample 都满足 both contact `>1.0`、local-Y abs `>0.5`、opposite sign，并 gate `stage_buf == STAGE_GRASP`。
- 2026-06-24 18:17 HKT - 完成 reviewer 最小修正：由于 `LeggedRobotBase._post_physics_step()` 先 `_check_termination()` 后 `_compute_observations()` / stage advance，stage2 首几步的 contact history 可能混入 stage1 samples；A2 complete predicate 已追加 `actual_time_in_stage_buf >= stage2_grasp_contact_history_length - 1` gate，不使用会被 `award_remaining_time_on_advance=True` 影响的 `time_in_stage_buf`，也不自维护 counter。
- 2026-06-24 18:17 HKT - 完成 `StagedTaskBase._check_termination()` review：final complete 已 gate 到 last stage，`reset_on_complete_delay` 行为保持为 last-stage complete 后延迟 reset；full 6-stage A2 中 stage2 predicate 不再能直接触发 episode complete。
- 2026-06-24 18:17 HKT - validation 结果：`py_compile` 通过；Hydra quick compose resolved `stage2_grasp_contact_history_length: 5` 且 `max_stage_time/stage_reward_scale/staged_reset_ratios` 均为 3 项；Hydra full A2 compose resolved same history length 且三组 stage lists 均为 6 项；no-sim probe 验证 `(0.5,0.5,0.5,0.5)` axis mapping 与 synthetic history predicate behavior。尚未跑旧 checkpoint diagnostic eval 或 small PPO smoke，不记录 runtime eval result。
- 2026-06-24 18:26 HKT - 完成 A2 Grasp Frame + Contact History Complete Fix old-checkpoint runtime eval：旧 checkpoint `logs_rl/a2_piper_stage0_2_grasp_terminal_a2_base/stage2_finished-20260623_221222/model_step_004000.pt` 输出到 `logs_eval/a2_stage0_2_eval_stage2_finished_grasp_frame_history_fix_ckpt4000`；`metrics_eval.json` 可用 `python -m json.tool` 解析，`completed_episodes=2`、`episode_lengths=[21,250]`、`episode_terminal_reasons=["upper_dof_overspeed","stage_overtime"]`、`episode_max_stage_reached=[0,0]`、`episode_goal_reached=[false,false]`、`episode_rewards=[-22.020288467407227,-29.03823471069336]`，`episode_terminal_diagnostics` length 为 2。两个 render mp4 存在：env0000 len250 reason-stage_overtime、env0001 len21 reason-upper_dof_overspeed，均为 720p、fps 20。
- 2026-06-24 18:26 HKT - 完成 old-checkpoint runtime diagnosis：diag0 为 `env_id=1`、`stage_buf=0`、`time_in_stage_buf=21`、`episode_length_buf=21`、`terminal_reasons=upper_dof_overspeed`、pregrasp opening/approach `0.8847/0.5954`、handle/pregrasp distance `1.1629/1.1497`、`gripper_primitive_raw=-1.9915`；diag1 为 `env_id=0`、`stage_buf=0`、`time_in_stage_buf=250`、`episode_length_buf=250`、`terminal_reasons=stage_overtime`、pregrasp opening/approach `0.9168/0.4261`、handle/pregrasp distance `0.1867/0.2293`、`gripper_primitive_raw=-1.9207`。旧 false-success checkpoint 在新 target frame + last-stage/history gate 下不再 stage1 complete，且没有 sensor history/target frame fail-fast；该 checkpoint 不应 resume，必须重新训练。
- 2026-06-24 18:26 HKT - 完成 A2 Grasp Frame + Contact History Complete Fix small PPO smoke：quick exp 使用 `num_envs=2`、`algo.trl.num_total_batches=2`、`algo.config.num_steps_per_env=8`、`algo.config.num_mini_batches=1`、`algo.config.num_learning_epochs=1`、`save_interval=9999`，project 为 `a2_piper_stage0_2_grasp_terminal_a2_base_smoke`，experiment 为 `door_open_a2_base_stage0_2_grasp_terminal_lstm_smoke_history_fix`。env create/reset 与 scene sensors initialization 完成，training loop 打印 `Learning iteration 1` 和 `Learning iteration 2`，actor/critic obs dims 保持 130/135，`Env/average_stage_reached=0`、`Env/average_goal_reached=0`、`Env/average_last_stage_goal_reached=0`，无 target frame/contact history crash。tiny `2x8` rollout 没有 episode completions，mean rewards/length 为 `nan` 是 expected empty episode statistics；training iterations 结束后 IsaacSim shutdown hang，main-agent Ctrl-C 后 session exit code 0。
- 2026-06-24 21:52 HKT - 完成最新训练 checkpoint `stage2_finished_orientation-20260624_183146/model_step_001000.pt` 的 720p eval recording：输出目录为 `logs_eval/a2_stage0_2_eval_stage2_finished_orientation_ckpt1000_720p/`，`metrics_eval.json` 可解析；两个 mp4 为 `env0000_episode0000_len452_reason-stage_overtime.mp4` 与 `env0001_episode0000_len452_reason-stage_overtime.mp4`，均为 720p、fps 20。
- 2026-06-24 21:52 HKT - 完成 checkpoint 1000 eval diagnosis：`completed_episodes=2`、`episode_lengths=[452,452]`、`episode_terminal_reasons=["stage_overtime","stage_overtime"]`、`episode_max_stage_reached=[2,2]`、`episode_goal_reached=[false,false]`、`episode_rewards=[46.406917572021484,41.90083312988281]`。terminal diagnostics 显示两个 env 均在 `stage_buf=2` 且 `time_in_stage_buf=100` overtime；opening/approach alignment 约 `0.986/0.955` 与 `0.990/0.977`，handle distance 约 `0.014/0.015`，但 `handle_contact_force_norm=[0,0]`、`squeeze_y=[0,0]`，gripper DOF 仍偏 open，说明当前 policy 已学到 stage2 对准 handle 附近，但还没有 stable contact/squeeze 或 true close grasp。
- 2026-06-24 22:11 HKT - 完成 A2 stage0-2 eval-only per-step trace diagnostics implement review：确认 `stage2_step_trace.json` 是 A2-only / eval-only / stage2-only，字段复用 `_get_a2_terminal_diagnostics()`，hook 在 `_check_termination()` / `_compute_reward()` 后且 `reset_envs_idx()` 前 capture，不会漏 stage2 terminal/overtime 最后一帧或读取 reset 后状态；JSON 写入复用 `_make_json_safe(..., path="stage2_step_trace")` 并使用 `.tmp` + `os.replace()`。reviewer 追加 A2 eval missing-init fail-fast 修正；本轮未发现 reward、stage transition、complete predicate、reset、camera 或 render timing 改动；runtime eval / 数值判断留给 main-agent。
- 2026-06-24 22:19 HKT - 完成 ckpt1000 stage2 per-step trace runtime diagnosis：输出保存在 `logs_eval/a2_stage0_2_eval_stage2_finished_step_trace_ckpt1000/`，`metrics_eval.json` 与 `stage2_step_trace.json` 均可解析，两个 720p mp4 输出正常。env0 trace 122 条，primitive open/close `117/5`、sign switches `1`、handle distance min `0.0105m`、contact/squeeze/complete-predicate frames 均为 `0`。env1 trace 150 条，primitive open/close `138/12`、sign switches `15`、`abs(primitive)<0.05` 为 `108`、handle distance min `0.0103m`、contact/squeeze/complete-predicate frames 均为 `0`。结论：用户观察到的 env1 grasp-target 附近 open/close oscillation 成立，但当前 checkpoint 未形成物理 contact/squeeze，不是 handle 阻挡后的稳定 close grasp。
- 2026-06-24 22:45 HKT - 完成 A2 Stage2 Close Shaping Rewards implement review：确认新增 `a2_stage2_close_command` 与 `a2_stage2_close_progress`，strict gate 为 stage2 + handle distance `<0.03m` + opening/approach alignment `>=0.9`；reviewer 最小修正了 command literal formula、progress mean-clamp order、zero span fail-fast 与 gripper DOF index validation。验证通过 `py_compile`、Hydra quick/full compose 与 no-sim formula sanity。
- 2026-06-24 22:49 HKT - 完成 A2 Stage2 Close Shaping Rewards bounded PPO smoke：quick exp 跑到 `Learning iteration 1`，reward functions 正常注册并输出 `rew_a2_stage2_close_command` / `rew_a2_stage2_close_progress`，无 reward shape 或 rollout crash；tiny `2x8` stage0-only smoke 中两项 reward 为 0 属 expected，训练主体完成后 IsaacSim shutdown hang，Ctrl-C 后 exit code 0。
- 2026-06-24 22:54 HKT - 完成 stage0/1 actual base roll/pitch upright penalty：新增 `penalty_base_roll_pitch_l2: -2.0`，reward helper 直接返回 `self.rpy[:,0:2]` 的 L2 并对 rpy shape fail-fast；验证通过 `py_compile`、targeted `git diff --check`、Hydra quick/full compose 与 no-sim formula sanity。
