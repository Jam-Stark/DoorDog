# DONE

- 2026-07-08 22:30 HKT - 完成 Base_v7 A route release-after-open implementation memory 记录。

  (1) A2-only stage3->4 threshold 从 `0.174533` 放宽到 `0.6`，只影响 A2 route。

  (2) A2 stage4 release handle：禁用强 `gripper_handle_orientation` / `grasp_target_distance` / `grasp`，新增 `penalty_a2_stage4_arm_default_pose_l1: -1.0`，并将 `penalty_base_roll_pitch_l2` 扩展到 stage4/5。

  (3) Shared diagnostics 补齐 `stage2_5_step_trace.json`，保留 legacy `stage2_step_trace.json`，并增加 stage3/4/5 raw/contact/door/root/doorframe scalar diagnostics。

  (4) 未改 gripper primitive/gain/effort/stage2 completion；validation/review PASS：`py_compile`、`git diff --check`、Hydra compose、no-sim source sanity、read-only review PASS。

- 2026-07-08 20:20 HKT - 完成 full-stage `base_v7` TCP/effort A/B 1000-step train/eval 结果归档，并将 A config 写回默认配置。

  (1) A config: `TCP=0.085`、`arm_j7/j8 effort_limit_sim=10.0/10.0`、`arm_j7/j8 Kp/Kd=80/3`、`num_velocity_iterations=1`、`reward_penalty_curriculum=false` 且 reward penalty scale 固定 1。Eval `logs_eval/base_v7_A_tcp085_effort10_ckpt1000` 为 2/2 complete，`episode_max_stage_reached=[5,5]`，episode length `525/528`，training log iteration 1000 `Env/average_goal_reached=0.7470`。

  (2) B config: `TCP=0.105`、`arm_j7/j8 effort_limit_sim=40.0/40.0`、其余关键 override 与 A 对齐。Eval `logs_eval/base_v7_B_tcp105_effort40_ckpt1000` 为 0/2 success，`episode_max_stage_reached=[4,4]`，episode length `654/654`，terminal reason `stage_overtime`，training log iteration 1000 `Env/average_goal_reached=0.0000`。

  (3) A/B 均未复现 `base_v6_40_effort_08TCP_offset` 的 stage1 no-arm collapse：A 证明 `TCP=0.085` 单独不是 blocker，B 证明 `effort=40` 单独不必然导致 stage1 collapse。base_v6 更可能是 `TCP=0.085 + effort=40` 组合或 stochastic bad basin；若需要确认，后续单独 repeat C。

  (4) B 的可复用经验：stage2 dwell 长（env0 115 frames、env1 105 frames）、negative close command 占比约 91%-93%，target offset mean 2-3cm，说明 40N/旧 TCP 能学到更持久的 stage2 close/contact；但 terminal stage4 gripper raw 为 positive open (`~0.21-0.23`)，j7/j8 接近 open，最终 through 卡门框，说明 stage3/4 缺少 keep-close/contact-retention 与 through heading/clearance reward/diagnostics。

  (5) 默认配置已收敛到 A：`gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` gripper effort 回到 `10/10`；`gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml` full-stage `num_velocity_iterations=1`；`gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` 默认关闭 reward penalty curriculum 并固定 scale=1。

- 2026-07-08 14:20 HKT - 完成 `base_v6_40_effort_08TCP_offset` ckpt1000 eval log diagnosis。

  (1) User-provided path `logs_eval/full_stage_base_v5_no_reward_penalty_scale_last_render_eval2` 不是 base_v6 evidence：该 eval mtime 为 2026-07-07 21:43，早于 base_v6 train dir `base_v6_40_effort_08TCP_offset-20260707_221058`，且 matching saved config `base_v5_no_reward_penalty_scale-20260707_184832/config.yaml` 中 `arm_j7/j8 effort_limit_sim=10.0/10.0`。

  (2) 该 base_v5 eval 确实复现视频观察到的 unstable tip / single-finger contact：`episode_max_stage_reached=[2,2]`，env0 stage2 trace `arm_body8` force max `18.44N`、`>1N` 332/349 frames，`arm_body7` max `0.79N` 且 `>1N` 0 frames；env1 `arm_body8` max `88.32N`、`arm_body7` max `2.33N`，但 `both_contact` 仅 2 frames、`contact_stability=0`，仍是 single `arm_body8` dominant / no stable bilateral grasp。

  (3) 真正 base_v6 eval path 是 `logs_eval/base_v6_40_effort_08TCP_offset_ckpt1000`，输出 mtime 2026-07-08 14:10。结果 `episode_max_stage_reached=[1,1]`、terminal `stage_buf=1`、`stage2_step_trace.json` 为空；terminal diagnostics `contact_force_arm_body7_8_norm=[0,0]`、`squeeze_y=[0,0]`。因此本次不能判断 40N effort 对 stage2 contact force 是否改善。

  (4) base_v6 卡 stage1 的直接日志原因是 pregrasp distance 未达 strict threshold：terminal `target_pos_source_pregrasp_distance=0.166/0.152m`，而 stage1→2 需要 `<0.1m`；orientation 已好（opening/approach alignment 约 `0.996/0.98`），gripper raw 仍 open (`0.72/0.70`)。下一步如果继续 base_v6，应先让 later checkpoint 或 targeted eval 进入 stage2，再比较 `arm_body7` contact、both-contact/contact-stability/squeeze-window 与 over-force。

- 2026-07-07 22:09 HKT - 完成 full-stage `base_v6` TCP/effort A/B 配置改动。

  (1) `gr00t/rl/envs/door/door_open_a2_base.py` 中 A2 `piper_gripper_handle_frame_transformer` 的 `source_frame_offset.pos` 从 `(0.0, 0.0, 0.105)` 改为 `(0.0, 0.0, 0.085)`。IsaacLab `FrameTransformerCfg.source_frame_offset` 语义是相对 source prim frame 的 local offset，因此该改动让 Piper TCP/source 沿 `arm_body6_to_gripper` local `-Z` 后退 2cm。

  (2) `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 中 `dof_effort_limit_list` 最后两个值（`arm_j7/arm_j8`）从 `10.0/10.0` 改为 `40.0/40.0`。`isaacsim.py` 的 A2 actuator routing 会按 `dof_names` 将该 list 传入 `ImplicitActuatorCfg.effort_limit_sim`。

  (3) 本轮未改 reward、stage transition / completion predicate、Kp/stiffness、Kd/damping、velocity iterations、termination curriculum 或 `reward_penalty_reward_names`。目的仅是验证“handle 从 finger tip 移向 finger mid-section + 更高 gripper effort cap”是否改善 `arm_body8` 单侧顶住、`arm_body7` 进不来的 failure mode。

  (4) Validation/review：`py_compile door_open_a2_base.py` PASS、`git diff --check` PASS、Hydra compose sanity PASS（`effort_tail=[100.0, 100.0, 40.0, 40.0]`）、read-only review PASS。Caveat：40N 是 joint effort cap，不等价于保证 40N handle contact force。

- 2026-07-07 16:17 HKT - 完成 full-stage `base_v4` 2k four-way no-render eval analysis。

  (1) Runs: `logs_eval/base_v4_thr0p8_kd3_vel1_ckpt2000_tolog_norender`、`logs_eval/base_v4_thr0p8_kd5_vel0_ckpt2000_tolog_norender`、`logs_eval/base_v4_thr1p0_kd3_vel1_ckpt2000_tolog_norender`、`logs_eval/base_v4_thr1p0_kd5_vel0_ckpt2000_tolog_norender`。

  (2) `threshold=0.8,Kd=3,velocity_iter=1` 与 `threshold=1.0,Kd=5,velocity_iter=0` 均 0/16 success，episode 全部 stage2 overtime，trace contact/squeeze/over-force/signflip 全为 0；说明这两组没有学到有效 handle contact。

  (3) `threshold=0.8,Kd=5,velocity_iter=0` 为 16/16 complete，但 trace 显示 raw close 更饱和、force spike 可达 250N+，stable-contact subset 也出现 over-force；该 run 不应作为正向默认，只能说明 hard predicate 仍允许 violent completion route。

  (4) `threshold=1.0,Kd=3,velocity_iter=1` 为 15/16 complete，1/16 `upper_dof_overspeed`；contact-stability records 无 over-force，raw close 幅度比 Kd5 温和，是四组中最可用候选。但仍存在 single-contact force spike，说明还不能直接作为 solved behavior。

  (5) Code finding: `_get_a2_stage2_grasp_completion_masks()` 当前 completion history 使用 `both_contact & sufficient_squeeze & opposite_squeeze`，没有要求 `squeeze_window`，也没有排除 `over_force`。因此 dense reward 已经记录/惩罚 force-window 与 over-force，但 hard stage2→3 predicate 仍可被超大 force route 触发。下一步应先修 completion predicate，而不是继续单纯调 contact threshold 或 gripper Kd。

- 2026-07-06 21:00 HKT - 完成 full-stage `base_v3` ckpt1000 no-render stage2 completion A/B。

  (1) Shared setup: checkpoint `logs_rl/a2_piper_full_stage_a2_base/base_v3-20260706_155252/model_step_001000.pt`，均使用 `++algo.config.eval.eval_num_envs_episodes=true`、`num_envs=16`、`render_results=false`、`dump_to_log_metrics=true`，因此是 one episode per env。

  (2) `stage2_grasp_contact_history_length=3` 输出 `logs_eval/full_stage_base_v3_ckpt1000_hist3_tolog`：0/16 success，16/16 max/terminal at stage3，全部 `stage_overtime`；`a2_stage2_grasp_complete_frac` / `a2_stage2_to3_advance_frac` 16 个 step 非零，`a2_stage2_door_open_bypass_frac=0`；terminal 15/16 single-contact、1/16 both-contact/contact-stability，mean reward 64.46。结论：history 3 能打开 stage2→3，但对当前 policy 过于宽松，容易让 stage3 在 durable grasp 前启动。

  (3) `a2_stage2_contact_force_threshold=0.8` 输出 `logs_eval/full_stage_base_v3_ckpt1000_thr0p8_tolog`：0/16 success，5/16 max/terminal at stage3、11/16 at stage2，全部 `stage_overtime`；`a2_stage2_grasp_complete_frac` / `a2_stage2_to3_advance_frac` 5 个 step 非零，`a2_stage2_door_open_bypass_frac=0`；terminal 7/16 both-contact/squeeze-window、1/16 contact-stability，mean reward 103.19。结论：threshold 0.8 更保守，更像下一步 render 验证 / potential default config 候选。

  (4) 两组都没有 full-stage success，符合预期：old checkpoint 几乎没学过 stage3/open after strict completion unblock。该 A/B 只判断 route unlocking 与假推进风险，不代表 door-opening behavior 已解决。

- 2026-07-06 20:35 HKT - 完成 full-stage `base_v3` ckpt1000 no-render scalar/trace eval 诊断记录。

  (1) Eval path: `logs_eval/full_stage_base_v3_ckpt1000_tolog_norender`，checkpoint `logs_rl/a2_piper_full_stage_a2_base/base_v3-20260706_155252/model_step_001000.pt`。本次因 override path 走默认 `150 total episodes`，不是原计划 one-episode-per-env。

  (2) Result: 0/150 success，144/150 terminal/max at stage2，`a2_stage2_to3_advance_frac` 只有 3 个 env-step 非零；`termination_level≈1.0`、`reward_penalty_scale≈1.0`，不是 curriculum-state blocker。

  (3) Behavior diagnosis: close-stage reward 生效，`close_gate/stable_close/negative primitive≈0.77`，target offset norm mean `8.8mm`，raw sign flip 很低；但 completion 卡在 unstable bilateral contact，`single_contact≈0.63` 且主要是 `arm_body8`，`arm_body7` force >1N 仅约 25% stage2 records / terminal 34/150，`contact_stability` 仅 3 records。

  (4) What-if trace analysis: current `contact_threshold=1.0` + history 5 只有 4/159 stage2 segments 满足；history 3 可到 59/159；threshold 0.8 + history 5 可到 36/159；threshold 0.5 + history 5 可到 138/159，风险较高。

- 2026-07-06 15:45 HKT - 完成 A2 stage2 bilateral contact/squeeze dense reward 与 diagnostics memory record。

  (1) Binary gripper primitive 保持不变；hard active single-finger penalty 通过 reward scale `0.0` disabled，但保留函数与 diagnostics visibility。

  (2) 新增 A2 stage2 dense rewards：`a2_stage2_both_contact`、`a2_stage2_opposite_squeeze`、`a2_stage2_squeeze_force_window`、`a2_stage2_contact_stability`、`penalty_a2_stage2_over_force`。新增 env thresholds：`a2_stage2_contact_force_threshold=1.0`、`a2_stage2_squeeze_force_min=0.5`、`a2_stage2_squeeze_force_max=20.0`、`a2_stage2_over_force_threshold=40.0`。

  (3) Diagnostics/trace 扩展覆盖 single contact、`arm_body7` / `arm_body8`、duration、both contact、squeeze window、contact stability、over-force、target offset x/y/z/norm 与 gripper raw sign flip。

  (4) Eval-only legacy checkpoint config migration 已显式处理旧 `a2_stage2_single_finger_contact_force_threshold` key；validation 为 `py_compile eval_agent_trl.py + door_open_a2_base.py` PASS、`git diff --check` PASS、conda `isaaclab` no-sim migration sanity PASS。Plain Python Hydra compose 因缺少 `hydra` module 不可用；review PASS。

- 2026-07-04 21:56 HKT - 完成 Full-stage False-Success Route Fix。
- 2026-07-04 22:26 HKT - 完成旧 full-stage `ckpt6000` strict-route 短 eval：命令使用 `++algo.config.eval.eval_num_envs_episodes=true`、`num_envs=2`、`render_results=false`，输出在 `logs_eval/full_stage_base_v0_ckpt6000_strict_route_eval1`。结果 `episode_goal_reached=[true,true]`、`episode_max_stage_reached=[5,5]`、terminal reason 均为 `complete`；stage2 trace 有短暂 negative gripper primitive、both-contact 与 opposite-squeeze spike，说明 strict route 没有把该旧 policy 挡在 stage2。现有 eval runner 未导出 `infos["to_log"]`，因此本次没有精确 `a2_stage*_bypass_blocked_frac` scalar。

  (1) A2 `stage1 -> stage2` 现在只由 true pregrasp readiness 推进，door-open bypass 不再推进 A2 stage1；non-A2/G1 path 保持旧 `door_opened` bypass semantics。

  (2) A2 `stage2 -> stage3` 现在只由 strict grasp completion 推进，door-open bypass 不再推进 A2 stage2；strict completion 仍基于 stage2 contact history、both-contact、sufficient squeeze 与 opposite squeeze predicate。

  (3) A2 `_stage_3_reward_condition()` 改用 base stillness condition，避免进入 stage3 后 `_stage_2_to_3_advance_condition()` 因 `stage_buf != STAGE_GRASP` 变 false 而导致 stage3 reward edge case。

  (4) 新增 15 个 A2 all-env fraction diagnostics：stage1/2 active、pregrasp/grasp readiness、door-open bypass、stage1/2 advance、bypass blocked、stage2 close gate、negative gripper primitive、both-contact、sufficient squeeze 与 opposite squeeze。

  (5) 未改 reward scales、`reward_penalty_reward_names`、termination curriculum、actuator config、YAML 或 continuous aperture primitive。Oracle-style review PASS；IsaacSim/PPO smoke 尚未运行，runtime/eval 验证保留在 TODO。

- 2026-07-04 22:34 HKT - 完成 eval `to_log` scalar dump 与旧 full-stage `ckpt6000` 复验：输出 `logs_eval/full_stage_base_v0_ckpt6000_strict_route_tolog/eval_to_log_metrics.json`。精确 scalar 显示 `a2_stage1_to2_bypass_blocked_frac=0`、`a2_stage2_to3_bypass_blocked_frac=0`；stage1→2 仅由 true pregrasp 在 step 113/116 推进；stage2→3 由 `a2_stage2_grasp_complete_frac` 在 step 147/148 非零推进；door-open bypass 首次出现 step 193，晚于 stage2→3。结论：strict route 生效，剩余问题是 stage2 grasp completion predicate 可被短暂 close/contact/squeeze spike 触发。

- 2026-07-05 18:38 HKT - 完成旧 full-stage `ckpt6000` tightened-completion route eval。用户 render run `logs_eval/full_stage_base_v0_ckpt6000_tightened` 显示 2 env episode0000 均 `len452_reason-stage_overtime`；补充 no-render scalar run `logs_eval/full_stage_base_v0_ckpt6000_tightened_tolog` 使用同 policy 的 `model_step_006000_full_tightened.pt`（`policy_state_dict` 与原 `model_step_006000.pt` 完全一致）生成 `eval_to_log_metrics.json`。结果：`episode_goal_reached=[False, False]`、`episode_max_stage_reached=[2,2]`、terminal reason 均为 `stage_overtime`；`a2_stage2_grasp_complete_frac=0`、`a2_stage2_to3_advance_frac=0`、`a2_stage2_close_gate_frac=0`、`a2_stage2_completion_close_gate_frac=0`，同时旧 policy 仍有 close command/contact/squeeze 信号（如 `a2_stage2_gripper_close_command_frac`、`a2_stage2_both_contact_frac`、`a2_stage2_sufficient_squeeze_frac` 非零）。结论：tightened completion 生效，旧 contact/squeeze spike route 被 close_gate/progress gate 挡在 stage2。

- 2026-07-03 21:59 HKT - 完成 A2 Piper arm overspeed threshold adaptation。

  (1) 基于 `logs_eval/base_v3_term2` 诊断：`termination_level=0.1` / `reward_penalty_scale≈0.2` 下 eval 两条 env 均 formal complete，但 arm reach 明显慢，旧 `upper_dof_overspeed` hard threshold 等效为 `2 rad/s`。

  (2) `penalty_dof_overspeed` threshold 从 `2.0 rad/s` 改为 `3.0 rad/s`，只覆盖 Piper `arm_j1..j6`，继续排除 gripper `arm_j7/j8`。

  (3) `upper_dof_overspeed` hard termination 仍由 `termination_level * 20.0` 控制，但增加 `min=3.0 rad/s` floor；不改变 `termination_level` curriculum、reward scale、stage gate 或 complete predicate。

- 2026-07-03 20:22 HKT - 记录 curriculum-state 调试规则。

  (1) A2 checkpoints 保存并恢复 `env_state_dict.termination_level` 与 `env_state_dict.reward_penalty_scale`。

  (2) `termination_level` 当前影响 A2 `upper_dof_overspeed` threshold：`termination_level * 20 rad/s`，覆盖 `arm_j1..j6`，排除 gripper `arm_j7/j8`。

  (3) `reward_penalty_scale` 会乘到 `reward_penalty_reward_names` 内的 positive shaping reward，例如 `walk_to_door`、`gripper_handle_orientation`、`pregrasp_target_distance`、`grasp_target_distance`、`a2_stage2_close_command/progress`、`a2_stage2_handle_center_y/approach_xz` 等。

  (4) 后续 reward/behavior 诊断看到 reward drop、short episode、stage1/2 behavior drift 或 eval early termination 时，应先核对这两个 saved env-state values 和 wandb history，避免把 curriculum state 的影响误判为 reward/gate/actuator 本身的单变量效果。

- 2026-07-03 15:45 HKT - 完成 `base_v2` rescue ablation config。

  (1) 保留当前 `base_v2` actuator config：`arm_j7/j8 Kp=80, Kd=3, effort_limit_sim=10`。

  (2) 新增 A2 stage2 close-gate only open primitive penalty `penalty_a2_stage2_open_command_in_close_gate: -0.4`，用于让 close gate 内继续 open command 的 frames 直接暴露为 reward cost；该 penalty 不加入 `reward_penalty_reward_names`。

  (3) 新增 stage1/stage2 base forward creep penalty `penalty_a2_stage1_stage2_base_forward_creep: -0.75`，env config 为 `a2_stage1_stage2_base_forward_creep_deadband: 0.10` 与 `a2_stage1_stage2_base_forward_creep_scale: 0.15`；该 penalty 不加入 `reward_penalty_reward_names`。

  (4) Purpose: 只测试 close-stage reward credit assignment 与 stage1/stage2 base-creep constraint 是否能 rescue `base_v2` 的 open-gripper/base-creep local optimum，目标是靠近 `base_v1/replay_v2` behavior；formal success/contact force 不作为该 config alone 的预期。

  (5) Validation/review: py_compile PASS，`git diff --check` PASS，full A2 targeted Hydra compose PASS，stage0-2 targeted Hydra compose PASS，no-sim formula sanity PASS，Oracle-style review PASS。PPO smoke 未跑。

- 2026-07-03 15:13 HKT - 完成 `logs_eval/base_v2` gripper Kp/Kd ablation runtime 记录。

  (1) Saved config 相对 `base_v1` 只差 `arm_j7/j8 Kp/Kd 40/1 -> 80/3` 与 run path；`arm_j7/j8 effort_limit_sim` 仍为 `10.0/10.0`。

  (2) Eval 结果为负向分叉：episode reward `84.58/80.85`，接近 `base_v0` 的低 reward 区间而非 `base_v1`。

  (3) `stage2_step_trace.json` 显示两条 env 的 negative close command frames 为 `0/330` 与 `0/328`，contact force/squeeze 全程 0；env0 虽有 `313/330` 帧 close gate，但仍保持 open primitive，env1 close gate 为 0。

  (4) 结论：增强 gripper joint Kp/Kd 会像 30N effort-only trial 一样扰动 close-stage credit / local optimum，使 policy 选择 open gripper + base/trunk approach；该 trial 不作为当前正向配置。

- 2026-07-03 12:18 HKT - 完成 gripper Kp/Kd ablation config。

  (1) `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 中 `arm_j7/j8` stiffness 从 `40.0/40.0` 改为 `80.0/80.0`。

  (2) `arm_j7/j8` damping 从 `1.0/1.0` 改为 `3.0/3.0`。

  (3) `arm_j7/j8 effort_limit_sim` 保持 `10.0/10.0`，`arm_j1..j6` 保持 base_v1 gains，stage0 offset、online handle height、reward/gate、stage transition、gripper primitive 与 complete predicate 均未改。

  (4) Validation: YAML sanity PASS，`git diff --check` PASS，read-only Oracle-style review PASS。未跑 PPO/IsaacSim smoke。

- 2026-07-03 09:40 HKT - 完成 `logs_eval/base_v1` arm Kp/Kd ablation runtime 记录。

  (1) Saved config 相对 `replay_v2` 只差 arm_j1-j6 Kp/Kd 与 run path；`arm_j7/j8 effort_limit_sim` 已回到 `10.0/10.0`。

  (2) Eval behavior 接近 `replay_v2`：episode reward `103.45/101.65` vs baseline `104.90/102.12`，stage2 close gate `339/348` 与 `333/341`，negative close command `335/348` 与 `328/341`。

  (3) Contact/squeeze 仍不足 formal success：both-contact predicate frames 仍为 0；该 run 是 actuator behavior 正确优化，不是 complete fix。

  (4) 结论：5ca012a arm gains 可以作为当前 actuator config；`base_v0` 的行为大变更应解释为 `30N` effort-only 改动导致训练 credit / local optimum 分叉，而不是所有 actuator retrain 都会大漂移。

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

  (3) 后续 stage0-2 reward/actuator/staging/height ablation 以 `replay_v2` 为 baseline，逐个变量做对照。

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

- 2026-07-04 22:56 HKT - 完成 A2 stage2 completion predicate 收紧 (reversible experiment)。`_get_a2_stage2_grasp_completion_masks()` 在 `a2_stage2_completion_close_gate_required: true` 时 AND 三个新 gate：close_gate（复用 `_get_a2_stage2_close_reward_gate()`）、stable_close（raw primitive < `a2_stage2_completion_gripper_close_command_threshold: -0.2`）、close_progress_min（`_get_a2_stage2_gripper_close_progress_min() >= 0.45`，min per-finger `(open_target - dof_pos).abs()/span` clamped [0,1]）。Flag false 时 completion 回退到旧 history/contact/squeeze 行为。新增 4 个 diagnostics：`a2_stage2_completion_close_gate_frac` / `a2_stage2_gripper_stable_close_frac` / `a2_stage2_gripper_close_command_frac` / `a2_stage2_gripper_close_progress_frac`。改动文件：`gr00t/rl/envs/door/door_open_a2_base.py`、`gr00t/rl/config/env/door_open_a2_base.yaml`。py_compile / git diff --check / Hydra compose / no-sim predicate check PASS。Oracle review PASS。
- 2026-07-05 18:38 HKT - 完成 tightened-completion 旧 `ckpt6000` scalar eval：`logs_eval/full_stage_base_v0_ckpt6000_tightened_tolog` 显示 2/2 `stage_overtime` at stage2，`a2_stage2_grasp_complete_frac=0`、`a2_stage2_to3_advance_frac=0`，旧 contact/squeeze spike 不再推进 stage2→3。

- 2026-07-05 19:00 HKT - 完成 `base_v3` tightened-completion 对照 eval：使用 `logs_rl/a2_piper_stage0_2_grasp_terminal_a2_base/base_v3-20260703_154907/model_step_001000.pt`，只打开 `a2_stage2_completion_close_gate_required=true`、close command threshold `-0.2` 与 close progress min `0.45`，输出 `logs_eval/base_v3_tightened_tolog`。结果 2/2 未 complete，terminal reason 均为 `upper_dof_overspeed`；trace 仍有强 contact/squeeze（env0 `both>1N=60/234`、env1 `both>1N=81/181`，max min-squeeze 约 `3.4/19.7`），但 tightened completion 未触发。结论：`base_v3` 已证明 `arm_j7/j8 Kp/Kd=80/3` 本身可以产生 grasp/contact；当前 tightened completion 会拒绝该类真实 contact/squeeze grasp，不应把 full-stage `base_v1` 的 stage2 failure 主要归因于 gripper gain。

- 2026-07-05 19:14 HKT - 完成 A2 stage2 completion A/B rollback config：`gr00t/rl/config/env/door_open_a2_base.yaml` 默认 `a2_stage2_completion_close_gate_required: false`。本次只恢复 base contact-history completion path 作为 short full-stage train 对照，保留 strict A2 stage1/2 route、tightened gates 的 manual override path、diagnostics、reward scales、termination curriculum 与 actuator config 不变。

- 2026-07-05 21:34 HKT - 完成 rollback short full-stage 600 checkpoint scalar eval：命令使用 `logs_rl/a2_piper_full_stage_a2_base/base_v1_lose_close_gate-20260705_192136/last.pt`、2 env、no rendering、`dump_to_log_metrics=true`，输出 `logs_eval/full_stage_base_v1_lose_close_gate_ckpt600_tolog`。结果 `episode_goal_reached=[False, False]`、`episode_max_stage_reached=[2,2]`、terminal reason 均为 `stage_overtime`；`a2_stage2_grasp_complete_frac=0`、`a2_stage2_to3_advance_frac=0`、`a2_stage2_negative_gripper_primitive_frac=0`、`both_contact/sufficient_squeeze/opposite_squeeze=0`。Trace 显示 close gate 大量触发（env0 `305/332`、env1 `265/325`），但 handle contact force/squeeze 全程 0，terminal primitive 仍 positive/open。

- 2026-07-05 22:04 HKT - 完成 full-stage base creep penalty 增强 config ablation。

  (1) `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` 中 `penalty_a2_stage1_stage2_base_forward_creep` 从 `-0.75` 加强到 `-1.5`。

  (2) `gr00t/rl/config/env/door_open_a2_base.yaml` 中 `a2_stage1_stage2_base_forward_creep_deadband` 从 `0.10` 收紧到 `0.05`，`a2_stage1_stage2_base_forward_creep_scale` 从 `0.15` 收紧到 `0.10`。

  (3) 本轮只增强已有 A2 stage1/2 base-forward creep penalty，目标是压低 full-stage 中用 base 替代 arm reach handle 的 local optimum；未改 reward 函数、strict A2 stage route、stage2 completion predicate、actuator config、reward curriculum membership 或 `reward_penalty_reward_names`。

- 2026-07-06 14:20 HKT - 完成 `base_v2` 1000-step render/scalar eval 与 workflow preference 记录。

  (1) Eval checkpoint：`logs_rl/a2_piper_full_stage_a2_base/base_v2-20260705_221205/last.pt`（loaded step 1000）。Outputs：`logs_eval/full_stage_base_v2_ckpt1000_render`（2 env × default/handle_top/handle_side videos）与 `logs_eval/full_stage_base_v2_ckpt1000_tolog`；render metrics 与 scalar-only metrics 一致。

  (2) Result：`episode_goal_reached=[False, False]`、`episode_max_stage_reached=[2,2]`、terminal reason 均为 `stage_overtime`、rewards `97.66/95.23`。Curriculum sanity：`termination_level≈1.0001`、`reward_penalty_scale≈1.0001`，`penalty_a2_stage1_stage2_base_forward_creep=-1.5` 生效且仍不在 `reward_penalty_reward_names`。

  (3) Behavior diagnosis：相比 `base_v1_lose_close_gate` 的 `negative_gripper_primitive=0`，本 run `a2_stage2_negative_gripper_primitive_frac mean=0.379`，`a2_stage2_gripper_stable_close_frac mean=0.324`，`a2_stage2_close_gate_frac mean=0.765`，handle distance 到 2-6mm；但 `a2_stage2_grasp_complete_frac=0`、`both_contact/sufficient_squeeze/opposite_squeeze=0`。Trace 中只有 transient single-side `arm_body8` contact（env0 any contact 34/357，env1 48/353），`arm_body7` 始终 0，因此无法 bilateral squeeze。

  (4) User workflow preference：后续 policy eval 默认生成 rendering 版本；如先跑 no-render scalar prepass，应随后补 render eval，并用 render + scalar/trace 一起判断行为。
