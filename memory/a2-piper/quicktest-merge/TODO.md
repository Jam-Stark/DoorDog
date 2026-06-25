# TODO

- 2026-06-25 20:30 HKT - 合并后的 A+B 类改动尚未在 6-stage full config（`door_open_a2_base_lstm`）下做 runtime smoke 验证。后续启动 6-stage 训练前，应先跑 small PPO smoke 确认 `staged_task_base` last-stage complete gate、stage2 contact history gate、stage2 close shaping rewards、`OrderedTargetFrameTransformer`、A2_Base init、PPO recurrent unsplit 等改动在 6-stage 下无 crash 且语义正确。
