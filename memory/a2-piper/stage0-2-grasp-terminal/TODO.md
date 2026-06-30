# TODO

- 2026-06-30 19:31 HKT - Stage0 Arm Default Pose Fix 已完成 static/review，但未跑 PPO/IsaacSim smoke；后续 stage0-2 retrain/eval 需要确认 `arm_j1..arm_j6` 在 stage0 保持 `default_dof_pos`、stage0 action gate 不阻塞 stage1 reaching、stage0->1 transition cadence 无 regression。
- 2026-06-26 20:30 HKT - grasp_target 已修正到 handle lever center（root cause fix：原 grasp_target 在把手上方 2cm 且偏门板 4.5-6cm）。下一步需要用新 asset retraining，观察 contact force、complete predicate、goal_reached；同时验证 close gate hd<0.015 对应 lever surface 的自然闭合时机。
- 2026-06-24 22:45 HKT - true close/aperture condition 或 complete predicate 强化仍未实施；本轮只加 close shaping rewards，不应混入 contact history gate、stage transition、reset、camera、render timing 或 action semantics 修改。
