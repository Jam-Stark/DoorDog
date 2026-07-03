# TODO

- 2026-07-03 16:16 HKT - 当前 origin G1 与 A2 training scene 的 `scenario_cfg/isaacsim.py` 均已确认固定 `door_open_lr=["right"]`、`door_open_io=["out"]`，并无 `doorOpenIO` 驱动的 spawn yaw / robot stance 切换。后续如果真的启用 in/out mixed randomization，仍需 runtime/GUI smoke 验证物理表现与 task semantics。
- 2026-06-29 15:56 HKT - 后续若 A2 要启用 `push_door_force`，必须基于 door-frame 或 source-frame force projection 设计，不使用 world-x；如混训 in/out，force projection 必须方向对称。
