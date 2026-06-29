# TODO

- 2026-06-29 15:56 HKT - 后续 runtime smoke 验证：训练时 in/out 门在物理 sim 中是否真的表现为镜像（robot 站位 / door spawn yaw 是否按 `doorOpenIO` 切换）。需要读 `scenario_cfg/isaacsim.py` 与 door spawn 调用，或在 GUI 里直接观察 in/out 门的物理姿态。当前静态代码无法定论。
- 2026-06-29 15:56 HKT - 后续若 A2 要启用 `push_door_force`，必须基于 door-frame 或 source-frame force projection 设计，不使用 world-x；如混训 in/out，force projection 必须方向对称。
