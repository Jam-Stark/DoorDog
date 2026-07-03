# TODO

- 2026-07-03 20:53 HKT - full 6-stage entry 的 G1 `ResetFromDataset` blocker 已修：`door_open_a2_base_lstm.yaml` 显式设置 `env.config.reset_from_dataset.enabled=False`。合并后的 A+B 类改动仍未在 6-stage full config 下做 small PPO smoke；如正式训练前需要 smoke，应验证 `staged_task_base` last-stage complete gate、stage2 contact history gate、stage2 close shaping rewards、`OrderedTargetFrameTransformer`、A2_Base init、PPO recurrent unsplit 等在 6-stage 下无 crash 且语义正确。
