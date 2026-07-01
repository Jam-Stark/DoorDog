# TODO

- 2026-06-30 19:31 HKT - Stage0 Arm Default Pose Fix 已完成 static/review，但未跑 PPO/IsaacSim smoke；后续 stage0-2 retrain/eval 需要确认 `arm_j1..arm_j6` 在 stage0 保持 `default_dof_pos`、stage0 action gate 不阻塞 stage1 reaching、stage0->1 transition cadence 无 regression。
- 2026-07-01 13:50 HKT - 下一轮 retrain/eval 使用 arm stiffness 回退 + `arm_j7/j8=80`；需要重点检查 `contact_force_arm_body7_8_norm` 是否适度提高、`squeeze_y` 与 5-step completion predicate frames 是否改善、gripper contact chatter/over-force 是否可控，以及 stage1 是否仍出现 base 往前蹭替代 arm reaching。
- 2026-06-30 21:47 HKT - `restrictPre-Grasp_v2` 表明 Stage2 Grasp Target Tracking Reward Fix 已解决大部分 handle center tracking / close gate 问题，但 env success 仍未通过；下一步应围绕 gripper primitive / close-stage reward 设计做方案：continuous aperture primitive、gripper primitive rate/hysteresis、bilateral squeeze/contact-force shaping、force stability / over-force penalty，而不是继续把主要问题归因到 grasp target 位置。
- 2026-06-24 22:45 HKT - true close/aperture condition 或 complete predicate 强化仍未实施；本轮只加 close shaping rewards，不应混入 contact history gate、stage transition、reset、camera、render timing 或 action semantics 修改。
