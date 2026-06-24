# TODO

- 2026-06-24 21:52 HKT - 后续 real PPO training diagnostics 继续观察 later checkpoints 是否从 stage2 overtime 发展到 stable contact/squeeze complete；重点记录 stage occupancy、stage2 completion route、contact spike false positive、overtime reset、termination frequency 与 `average_goal_reached`。
- 2026-06-24 18:17 HKT - 后续单独设计 true close/aperture condition 或明确 close command/DOF diagnostic，以及 A2 gripper close shaping；用户已明确本轮 defer，不应混入 A2 Grasp Frame + Contact History Complete Fix。
