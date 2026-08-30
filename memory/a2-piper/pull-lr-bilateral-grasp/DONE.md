# DONE

- 2026-08-30 07:18 HKT — 核对当前 remote `origin/A2_Piper` 的 v26 LR selector 与 door builder：完整物理 door asset 已支持 exact mirror，不需要新 USD 或 negative scale；Stage0/1 target/reset 使用 live per-env geometry。
- 2026-08-30 07:18 HKT — pull branch 实现 `bilateral|left|right` exact per-env distribution、seeded permutation、runtime side-count telemetry 与 one-hot privileged LR observation；actor shape 保持 135-D。
- 2026-08-30 07:18 HKT — 实现六 stage topology + `completion_stage: 2`，有效 task horizon 修正为 Stage0–2 的 450 steps；strict warm-start 仅重基 LR 两个 RMS feature。
- 2026-08-30 07:18 HKT — pilot 证据拒绝 fresh 135-D RMS：fresh-adaptive 两个 seeds 均无法 Stage1→2；targeted symmetric LR RMS 能保留 acquisition transfer。
- 2026-08-30 07:18 HKT — 四个 4096-env formal seeds 均实现 exact `2048 LEFT / 2048 RIGHT`。三格晚期 critic-LSTM OOM 后，以 full checkpoint + fresh process + expandable CUDA segments 在不降低 env 数的情况下全部续到 step250，未再 OOM。
- 2026-08-30 07:18 HKT — 12 个 resumed checkpoint 完成 fixed-side64 natural-reset screen；seed2-step250 在 independent eval seed1001 confirmation 排名第一。两轮合计 strict K5 LEFT/RIGHT=`125/128` each，clean K5=`93/128`、`70/128`。
- 2026-08-30 07:18 HKT — final winner raw LEFT/RIGHT 单独 render 均真实 Stage2 complete；每侧五个 H.264 1280×720 MP4 通过 ffprobe。
