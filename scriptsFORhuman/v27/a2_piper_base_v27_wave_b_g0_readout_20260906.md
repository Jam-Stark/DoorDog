# base_v27 Wave B G0 / fixed-friction probe

2026-09-06T09:22:05.066325+00:00 — G0_PASS；formal L/R 尚未启动。

CPU：21项组合检查通过；新增训练日志出口后3项恢复方法检查通过。R2 64-env/32-batch smoke strict actor/RMS加载、正常退出和step32保存均已验证。

训练bank已真实capture/promotion/reset；现有日志记录的是PPO batch均值，不把小数累计快照当作精确episode总数。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| 样本 | Cell | 层 | 侧 | N | 计数 | 握门穿过 | 松手后身体力p95(N) | 终止 | integrity |
|---|---|---|---|---:|---|---:|---:|---|---:|
| 固定摩擦probe | C_S21 | P02 | left | 32 | 27/32/32/32/32/32/23 | 5 | 0.0 | {'complete': 32} | 0 |
| 固定摩擦probe | C_S21 | P02 | right | 32 | 26/31/31/31/31/31/18 | 31 | 0.0 | {'stage_overtime': 1, 'complete': 31} | 0 |
| 固定摩擦probe | C_S21 | P05 | left | 32 | 27/32/32/32/32/32/18 | 10 | 0.0 | {'complete': 32} | 0 |
| 固定摩擦probe | C_S21 | P05 | right | 32 | 26/31/31/31/31/31/18 | 31 | 0.0 | {'stage_overtime': 1, 'complete': 31} | 0 |
| 32-batch接线策略 | R2_S41 | injected | left | 64 | 48/64/64/64/60/59/31 | 56 | 1219.417724609375 | {'bad_orientation': 1, 'complete': 59, 'stage_overtime': 4} | 0 |
| 32-batch接线策略 | R2_S41 | injected | right | 64 | 54/61/61/61/61/61/31 | 61 | 16.46373748779297 | {'stage_overtime': 3, 'complete': 61} | 0 |

P02/P05四个lane均为seed270201、exact32，native readback逐env严格匹配(2,1.5,0)/(5,3.75,0)。observed door_weight均在82.403–159.833 kg。固定probe不能代替L1 per-env训练readback，后者在正式启动首批日志核实。

注入评估：LEFT64/64、RIGHT61/64实际执行6步；RIGHT另3集NOT_TRIGGERED，ITT分母始终64。两侧loss_events/regrasp_success均为0；因此本样本不提供eval失抓后恢复成功的证据，不更改注册的4/6步扰动或10步失抓条件。

训练bank最后batch telemetry：
```json
{
  "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/smoke/wave_b_R2_S41/runtime.log",
  "iteration": 32,
  "metrics": {
    "a2_v27_bank_raw_capture_left": 5.0,
    "a2_v27_bank_promotion_left": 5.0,
    "a2_v27_bank_eligible_reset_left": 9.9062,
    "a2_v27_bank_reset_left": 1.0,
    "a2_v27_bank_available_left": 5.0,
    "a2_v27_bank_raw_capture_right": 13.5312,
    "a2_v27_bank_promotion_right": 5.0,
    "a2_v27_bank_eligible_reset_right": 9.0,
    "a2_v27_bank_reset_right": 2.0,
    "a2_v27_bank_available_right": 5.0
  },
  "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
}
```

所有训练、probe、注入评估均正常退出；所有评估integrity0。该读数只证明接线与固定probe，不用于选择RECIPE_B或判定Q_R。

来源：/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_probe/reducer.json；/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_smoke_injected/reducer.json；/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_smoke_b/RUN_RECEIPT.json。
