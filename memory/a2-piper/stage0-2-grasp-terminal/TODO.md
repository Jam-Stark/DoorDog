# TODO

- 2026-06-26 01:00 HKT - 方案 B（stage2 gate 外 open target tracking reward）已实施，下一步需要用新 reward retraining，观察 stage2 gate 外 gripper 是否保持张开、gate 内 close command/progress、contact/squeeze complete、overtime reset、termination frequency 与 `average_goal_reached`。
- 2026-06-24 22:45 HKT - true close/aperture condition 或 complete predicate 强化仍未实施；本轮只加 close shaping rewards，不应混入 contact history gate、stage transition、reset、camera、render timing 或 action semantics 修改。
