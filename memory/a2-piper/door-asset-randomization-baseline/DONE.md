# DONE

- 2026-07-03 16:16 HKT - 记录当前训练 baseline：origin G1 与 A2 training scene 均固定 `door_open_lr=["right"]`、`door_open_io=["out"]`；当前 repo 没有 push/pull mixed training 证据。明确对 G1/A2 当前 task 可理解为面朝门、右手侧 handle、推门进入；后续 `door_open_io` in/out randomization 是新任务，不是当前 baseline 的简单开关。
- 2026-07-03 16:24 HKT - 记录 left/right randomization discussion：A2 stage0 staging、pregrasp、grasp target/reward plumbing 均由 handle-relative `grasp_target` / frame transformer 驱动，理论上会随 `door_open_lr` 镜像；因此在 `right-only` stage0-2 稳定后，可将 `door_open_lr=["left", "right"]` 作为第一阶段 retrain randomization。该结论不覆盖 `door_open_io` in/out mixed task。
- 2026-07-03 16:31 HKT - 记录 in/out randomization discussion：物理上可以理解为 mirror robot pose，但工程上应启用 `door_open_io=["out", "in"]` 并按该 semantic label mirror robot approach side、yaw、stage0 target、through target/success direction 与 diagnostics；不建议保持 `door_open_io=["out"]` 同时偷偷 mirror robot 初始状态。
