# base_v27 wave_c/step2000 readout

2026-09-11 19:18 HKT

状态：`V27_COMPLETE`；step=2000；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| SC_S203 | nominal | left | 62/64/52/50/0/0/0 | 0 | None | None | 754.0 | 0.00012754017515517388 | {"stage_overtime": 64} | 0 |
| SC_S203 | nominal | right | 63/63/63/63/46/0/0 | 62 | 1143.9180908203125 | 0.6506063938140869 | 955.0 | 0.0 | {"stage_overtime": 64} | 0 |
| SK_S211 | nominal | left | 0/0/0/0/0/0/0 | 0 | None | None | 552.0 | 0.0 | {"stage_overtime": 64} | 0 |
| SK_S211 | nominal | right | 0/0/0/0/0/0/0 | 0 | None | None | 552.0 | 0.0 | {"stage_overtime": 64} | 0 |
| SK_S212 | nominal | left | 0/0/0/0/0/0/0 | 0 | None | None | 552.0 | 0.7552083333333334 | {"stage_overtime": 64} | 0 |
| SK_S212 | nominal | right | 0/0/0/0/0/0/0 | 0 | None | None | 552.0 | 0.7456691576086957 | {"stage_overtime": 64} | 0 |
| SK_S213 | nominal | left | 64/64/64/64/1/0/0 | 64 | 0.0 | 1.075831413269043 | 754.0 | 0.22772767608395073 | {"stage_overtime": 64} | 0 |
| SK_S213 | nominal | right | 62/64/64/64/37/0/0 | 28 | 695.6953735351562 | 1.6924532651901245 | 955.0 | 0.0019751135690302193 | {"stage_overtime": 64} | 0 |
| SC_S201 | nominal | left | 0/0/0/0/0/0/0 | 0 | None | None | 552.0 | 0.0 | {"stage_overtime": 64} | 0 |
| SC_S201 | nominal | right | 0/0/0/0/0/0/0 | 0 | None | None | 552.0 | 0.0 | {"stage_overtime": 64} | 0 |
| SC_S202 | nominal | left | 62/64/64/64/5/0/0 | 9 | 0.0 | 1.0138566493988037 | 754.0 | 0.012443921154665962 | {"stage_overtime": 64} | 0 |
| SC_S202 | nominal | right | 64/64/64/64/3/0/0 | 60 | 0.0 | 1.194777011871338 | 754.0 | 0.0 | {"stage_overtime": 64} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "SK_S211−SC_S201": {
      "nominal": {
        "left": {
          "D": 0,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 0,
          "complete": 0,
          "clean_complete": 0
        },
        "right": {
          "D": 0,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 0,
          "complete": 0,
          "clean_complete": 0
        }
      }
    },
    "SK_S212−SC_S202": {
      "nominal": {
        "left": {
          "D": -62,
          "S3+": -64,
          "S4+": -64,
          "open_hold": -64,
          "S5+": -5,
          "complete": 0,
          "clean_complete": 0
        },
        "right": {
          "D": -64,
          "S3+": -64,
          "S4+": -64,
          "open_hold": -64,
          "S5+": -3,
          "complete": 0,
          "clean_complete": 0
        }
      }
    },
    "SK_S213−SC_S203": {
      "nominal": {
        "left": {
          "D": 2,
          "S3+": 0,
          "S4+": 12,
          "open_hold": 14,
          "S5+": 1,
          "complete": 0,
          "clean_complete": 0
        },
        "right": {
          "D": -1,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": -9,
          "complete": 0,
          "clean_complete": 0
        }
      }
    }
  },
  "negative_deltas": [
    {
      "reference": "SK_S212−SC_S202",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -62,
        "S3+": -64,
        "S4+": -64,
        "open_hold": -64,
        "S5+": -5
      }
    },
    {
      "reference": "SK_S212−SC_S202",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -64,
        "S3+": -64,
        "S4+": -64,
        "open_hold": -64,
        "S5+": -3
      }
    },
    {
      "reference": "SK_S213−SC_S203",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -1,
        "S5+": -9
      }
    },
    {
      "reference": "SC_S203−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S3+": -1
      }
    }
  ]
}
```

## Typed outcomes

```json
null
```

## 质量失败成分、K 与恢复 telemetry

```json
{
  "quality": {
    "SC_S203/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SC_S203/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SK_S211/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SK_S211/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SK_S212/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SK_S212/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SK_S213/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SK_S213/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SC_S201/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SC_S201/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SC_S202/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "SC_S202/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    }
  },
  "k": {
    "SK_S211": {
      "through_batch": 2000,
      "max_common_step": 128000,
      "scale_min": 1.0,
      "first_update_below_0.95": null,
      "share_of_updates_below_0.5": 0.0,
      "reversal_count": 0,
      "skipped_updates": 7873,
      "trace_rows": 127988
    },
    "SK_S212": {
      "through_batch": 2000,
      "max_common_step": 128000,
      "scale_min": 1.0,
      "first_update_below_0.95": null,
      "share_of_updates_below_0.5": 0.0,
      "reversal_count": 0,
      "skipped_updates": 6807,
      "trace_rows": 127996
    },
    "SK_S213": {
      "through_batch": 2000,
      "max_common_step": 128000,
      "scale_min": 0.20000000298023224,
      "first_update_below_0.95": 98368,
      "share_of_updates_below_0.5": 0.15872470110182074,
      "reversal_count": 0,
      "skipped_updates": 17304,
      "trace_rows": 127970
    }
  },
  "training": {
    "SC_S203": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/SC_S203_r1/runtime.log",
      "iteration": null,
      "metrics": {},
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "SK_S211": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/SK_S211_r1/runtime.log",
      "iteration": null,
      "metrics": {},
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "SK_S212": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/SK_S212_r1/runtime.log",
      "iteration": null,
      "metrics": {},
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "SK_S213": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/SK_S213_r1/runtime.log",
      "iteration": null,
      "metrics": {},
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "SC_S201": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/SC_S201_r1/runtime.log",
      "iteration": null,
      "metrics": {},
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "SC_S202": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/SC_S202_r1/runtime.log",
      "iteration": null,
      "metrics": {},
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    }
  },
  "recovery": {}
}
```

## Receipt 与资源

```json
{
  "invalid_cells": {},
  "receipts": {
    "v27_eval_g0_runtime_eval_gpu0": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_g0_runtime_eval_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_g0_runtime_eval_gpu1": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_g0_runtime_eval_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_g0_runtime_eval_r2_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_g0_runtime_eval_r2_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_g0_runtime_eval_r2_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_g0_runtime_eval_r2_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_q0_dev_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_q0_dev_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_q0_dev_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_q0_dev_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_q0_render_gpu0": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_q0_render_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_q0_render_gpu1": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_q0_render_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_q0_render_k_after_cpu_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_q0_render_k_after_cpu_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_q0_render_k_after_cpu_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_q0_render_k_after_cpu_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step1000_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step1000_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step1000_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step1000_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step1500_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step1500_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step1500_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step1500_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step2000_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step2000_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step2000_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step2000_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step2500_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step2500_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step2500_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step2500_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step3000_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step3000_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step3000_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step3000_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step500_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step500_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_a_step500_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_a_step500_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_l_step1000_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_l_step1000_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_l_step1000_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_l_step1000_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_l_step2000_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_l_step2000_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_l_step2000_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_l_step2000_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_l_step3000_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_l_step3000_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_l_step3000_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_l_step3000_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_probe_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_probe_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_probe_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_probe_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_r_step1000_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_r_step1000_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_r_step1000_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_r_step1000_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_r_step1500_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_r_step1500_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_r_step1500_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_r_step1500_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_r_step500_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_r_step500_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_r_step500_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_r_step500_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_smoke_injected_gpu0": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_smoke_injected_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_wave_b_smoke_injected_gpu1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_b_smoke_injected_gpu1/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step1000_part1_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step1000_part1_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step1000_part1_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step1000_part1_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step1000_part2_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step1000_part2_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step1000_part2_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step1000_part2_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step1000_part3_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step1000_part3_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step1000_part3_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step1000_part3_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step2000_part1_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step2000_part1_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step2000_part1_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step2000_part1_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step2000_part2_gpu6": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step2000_part2_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step2000_part2_gpu7": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step2000_part2_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step2000_part2_r1_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step2000_part2_r1_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step2000_part2_r1_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step2000_part2_r1_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step2000_part3_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step2000_part3_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step2000_part3_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step2000_part3_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step3000_part1_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step3000_part1_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step3000_part1_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step3000_part1_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step3000_part2_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step3000_part2_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step3000_part2_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step3000_part2_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step4000_part1_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step4000_part1_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step4000_part1_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step4000_part1_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step4000_part2_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step4000_part2_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step4000_part2_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step4000_part2_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step5000_part1_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step5000_part1_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step5000_part1_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step5000_part1_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step5000_part2_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step5000_part2_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step5000_part2_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step5000_part2_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step5000_part3_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step5000_part3_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step5000_part3_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step5000_part3_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step6000_part1_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step6000_part1_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step6000_part1_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step6000_part1_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step6000_part2_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step6000_part2_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step6000_part2_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step6000_part2_gpu7/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step6000_part3_gpu6": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step6000_part3_gpu6/RUN_RECEIPT.json"
    },
    "v27_eval_wave_c_step6000_part3_gpu7": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_wave_c_step6000_part3_gpu7/RUN_RECEIPT.json"
    },
    "v27_smoke_a": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_smoke_a/RUN_RECEIPT.json"
    },
    "v27_smoke_b": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_smoke_b/RUN_RECEIPT.json"
    },
    "v27_smoke_c": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_smoke_c/RUN_RECEIPT.json"
    },
    "v27_train_c_s21": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s21/RUN_RECEIPT.json"
    },
    "v27_train_c_s22": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s22/RUN_RECEIPT.json"
    },
    "v27_train_l0_s31": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l0_s31/RUN_RECEIPT.json"
    },
    "v27_train_l1_s31": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s31/RUN_RECEIPT.json"
    },
    "v27_train_l1_s31_r1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s31_r1/RUN_RECEIPT.json"
    },
    "v27_train_l1_s32": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s32/RUN_RECEIPT.json"
    },
    "v27_train_l1_s32_r1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s32_r1/RUN_RECEIPT.json"
    },
    "v27_train_q1_s21": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s21/RUN_RECEIPT.json"
    },
    "v27_train_q1_s22": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s22/RUN_RECEIPT.json"
    },
    "v27_train_q2_s21": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s21/RUN_RECEIPT.json"
    },
    "v27_train_q2_s22": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s22/RUN_RECEIPT.json"
    },
    "v27_train_r0_s41": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r0_s41/RUN_RECEIPT.json"
    },
    "v27_train_r1_s41": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r1_s41/RUN_RECEIPT.json"
    },
    "v27_train_r2_s41": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r2_s41/RUN_RECEIPT.json"
    },
    "v27_train_sc_s201": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sc_s201/RUN_RECEIPT.json"
    },
    "v27_train_sc_s201_r1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sc_s201_r1/RUN_RECEIPT.json"
    },
    "v27_train_sc_s202": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sc_s202/RUN_RECEIPT.json"
    },
    "v27_train_sc_s202_r1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sc_s202_r1/RUN_RECEIPT.json"
    },
    "v27_train_sc_s203": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sc_s203/RUN_RECEIPT.json"
    },
    "v27_train_sc_s203_r1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sc_s203_r1/RUN_RECEIPT.json"
    },
    "v27_train_sk_s211": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sk_s211/RUN_RECEIPT.json"
    },
    "v27_train_sk_s211_r1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sk_s211_r1/RUN_RECEIPT.json"
    },
    "v27_train_sk_s212": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sk_s212/RUN_RECEIPT.json"
    },
    "v27_train_sk_s212_r1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sk_s212_r1/RUN_RECEIPT.json"
    },
    "v27_train_sk_s213": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sk_s213/RUN_RECEIPT.json"
    },
    "v27_train_sk_s213_r1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_sk_s213_r1/RUN_RECEIPT.json"
    },
    "v27_watch_a": {
      "state": "FAIL",
      "returncode": 143,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a/RUN_RECEIPT.json"
    },
    "v27_watch_a_r2": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a_r2/RUN_RECEIPT.json"
    },
    "v27_watch_b": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_b/RUN_RECEIPT.json"
    },
    "v27_watch_c": {
      "state": "FAIL",
      "returncode": 143,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_c/RUN_RECEIPT.json"
    },
    "v27_watch_c_isolated": {
      "state": "FAIL",
      "returncode": 143,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_c_isolated/RUN_RECEIPT.json"
    },
    "v27_watch_c_isolated_r1": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_c_isolated_r1/RUN_RECEIPT.json"
    },
    "v27_watch_c_ready": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_c_ready/RUN_RECEIPT.json"
    }
  },
  "gpu": [
    "0, 41232 MiB, 49140 MiB, 59 %",
    "1, 41232 MiB, 49140 MiB, 55 %",
    "2, 41232 MiB, 49140 MiB, 59 %",
    "3, 41232 MiB, 49140 MiB, 57 %",
    "4, 1 MiB, 49140 MiB, 0 %",
    "5, 1 MiB, 49140 MiB, 0 %",
    "6, 1 MiB, 49140 MiB, 0 %",
    "7, 1 MiB, 49140 MiB, 0 %"
  ],
  "processes": [
    "3610353 3155584       00:40 /bin/bash -c rg -l 'V27_COMPLETE|typed_outcomes|V27_' logs_eval logs_rl scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905 2>/dev/null | sort | tail -150",
    "3610354 3610353       00:40 rg -l V27_COMPLETE|typed_outcomes|V27_ logs_eval logs_rl scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905",
    "3610772 3155584       00:00 /bin/bash -c set -euo pipefail V27PY=/home/baoquanc/anaconda3/envs/isaaclab/bin/python V27TRAIN=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train $V27PY scriptsFORhuman/v27/v27_readout.py \\   --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step2000/reducer.json \\   --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step2000.json \\   --train-root \"$V27TRAIN\" \\   --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step1000/reducer.json \\   --output scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step2000_full_readout_20260911.md & pid2000=$! $V27PY scriptsFORhuman/v27/v27_readout.py \\   --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step3000/reducer.json \\   --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step3000.json \\   --train-root \"$V27TRAIN\" \\   --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step2000/reducer.json \\   --output scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step3000_full_readout_20260911.md & pid3000=$! wait \"$pid2000\" wait \"$pid3000\"",
    "3610789 3610772       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step2000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step2000.json --train-root /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step1000/reducer.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step2000_full_readout_20260911.md",
    "3610790 3610772       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step3000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step3000.json --train-root /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step2000/reducer.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step3000_full_readout_20260911.md"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step2000/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step2000.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。
