# TODO

- 2026-06-24 22:54 HKT - A2 Stage2 Close Shaping Rewards 与 stage0/1 base roll/pitch upright penalty 已完成 static validation；下一步需要用新 reward retraining，继续观察 stage occupancy、stage0/1 roll/pitch magnitude、stage2 close command/progress、contact/squeeze complete、overtime reset、termination frequency 与 `average_goal_reached`。
- 2026-06-24 22:45 HKT - true close/aperture condition 或 complete predicate 强化仍未实施；本轮只加 close shaping rewards，不应混入 contact history gate、stage transition、reset、camera、render timing 或 action semantics 修改。
