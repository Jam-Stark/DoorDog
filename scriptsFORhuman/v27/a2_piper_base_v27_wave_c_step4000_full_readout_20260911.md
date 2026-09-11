# base_v27 wave_c/step4000 readout

2026-09-11 19:18 HKT

状态：`V27_COMPLETE`；step=4000；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| SC_S203 | nominal | left | 56/64/61/35/61/61/0 | 22 | 113.66328430175781 | 0.6503556966781616 | 444.0 | 0.0 | {"upper_dof_overspeed": 3, "complete": 61} | 0 |
| SC_S203 | nominal | right | 64/64/64/64/64/64/0 | 61 | 182.65415954589844 | 0.6676942706108093 | 512.0 | 0.0 | {"complete": 64} | 0 |
| SK_S211 | nominal | left | 0/0/0/0/0/0/0 | 0 | None | None | 552.0 | 0.0 | {"stage_overtime": 64} | 0 |
| SK_S211 | nominal | right | 0/0/0/0/0/0/0 | 0 | None | None | 552.0 | 0.0 | {"stage_overtime": 64} | 0 |
| SK_S212 | nominal | left | 0/51/0/0/0/0/0 | 0 | None | None | 653.0 | 0.8168927098001433 | {"stage_overtime": 64} | 0 |
| SK_S212 | nominal | right | 64/64/26/21/0/0/0 | 0 | None | None | 653.0 | 0.7029807735602683 | {"stage_overtime": 64} | 0 |
| SK_S213 | nominal | left | 64/64/64/64/0/0/0 | 64 | 0.0 | 1.1221383810043335 | 754.0 | 4.1445623342175064e-05 | {"stage_overtime": 64} | 0 |
| SK_S213 | nominal | right | 11/63/63/63/63/63/58 | 1 | 79.57083892822266 | 1.65632963180542 | 448.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| SC_S201 | nominal | left | 0/0/0/0/0/0/0 | 0 | None | None | 552.0 | 0.0 | {"stage_overtime": 64} | 0 |
| SC_S201 | nominal | right | 24/24/20/20/0/0/0 | 0 | None | None | 552.0 | 0.0 | {"stage_overtime": 64} | 0 |
| SC_S202 | nominal | left | 64/64/64/64/64/64/0 | 64 | 600.7787475585938 | 0.9789655804634094 | 755.0 | 0.0 | {"complete": 64} | 0 |
| SC_S202 | nominal | right | 54/62/61/61/61/60/18 | 60 | 0.0 | 0.9734892845153809 | 431.0 | 0.002762817374274323 | {"complete": 60, "stage_overtime": 4} | 0 |

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
          "D": -24,
          "S3+": -24,
          "S4+": -20,
          "open_hold": -20,
          "S5+": 0,
          "complete": 0,
          "clean_complete": 0
        }
      }
    },
    "SK_S212−SC_S202": {
      "nominal": {
        "left": {
          "D": -64,
          "S3+": -13,
          "S4+": -64,
          "open_hold": -64,
          "S5+": -64,
          "complete": -64,
          "clean_complete": 0
        },
        "right": {
          "D": 10,
          "S3+": 2,
          "S4+": -35,
          "open_hold": -40,
          "S5+": -61,
          "complete": -60,
          "clean_complete": -18
        }
      }
    },
    "SK_S213−SC_S203": {
      "nominal": {
        "left": {
          "D": 8,
          "S3+": 0,
          "S4+": 3,
          "open_hold": 29,
          "S5+": -61,
          "complete": -61,
          "clean_complete": 0
        },
        "right": {
          "D": -53,
          "S3+": -1,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": -1,
          "clean_complete": 58
        }
      }
    }
  },
  "negative_deltas": [
    {
      "reference": "SK_S211−SC_S201",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -24,
        "S3+": -24,
        "S4+": -20,
        "open_hold": -20
      }
    },
    {
      "reference": "SK_S212−SC_S202",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -64,
        "S3+": -13,
        "S4+": -64,
        "open_hold": -64,
        "S5+": -64,
        "complete": -64
      }
    },
    {
      "reference": "SK_S212−SC_S202",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S4+": -35,
        "open_hold": -40,
        "S5+": -61,
        "complete": -60,
        "clean_complete": -18
      }
    },
    {
      "reference": "SK_S213−SC_S203",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "S5+": -61,
        "complete": -61
      }
    },
    {
      "reference": "SK_S213−SC_S203",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -53,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1
      }
    },
    {
      "reference": "SC_S203−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -2,
        "S4+": -3,
        "open_hold": -29,
        "S5+": -3,
        "complete": -3
      }
    },
    {
      "reference": "SK_S213−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -32,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1
      }
    },
    {
      "reference": "SC_S202−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -9,
        "S3+": -1,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2,
        "complete": -3
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
      "complete_with_crossing_hinge_below_threshold": 61,
      "complete_with_body_contact_above_5N": 61,
      "complete_without_crossing_measurement": 0
    },
    "SC_S203/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 64,
      "complete_with_body_contact_above_5N": 27,
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
      "complete_with_body_contact_above_5N": 5,
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
      "complete_with_crossing_hinge_below_threshold": 47,
      "complete_with_body_contact_above_5N": 64,
      "complete_without_crossing_measurement": 0
    },
    "SC_S202/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 42,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    }
  },
  "k": {
    "SK_S211": {
      "through_batch": 4000,
      "max_common_step": 256000,
      "scale_min": 1.0,
      "first_update_below_0.95": null,
      "share_of_updates_below_0.5": 0.0,
      "reversal_count": 0,
      "skipped_updates": 19070,
      "trace_rows": 255979
    },
    "SK_S212": {
      "through_batch": 4000,
      "max_common_step": 256000,
      "scale_min": 1.0,
      "first_update_below_0.95": null,
      "share_of_updates_below_0.5": 0.0,
      "reversal_count": 0,
      "skipped_updates": 20961,
      "trace_rows": 255983
    },
    "SK_S213": {
      "through_batch": 4000,
      "max_common_step": 256000,
      "scale_min": 0.20000000298023224,
      "first_update_below_0.95": 98368,
      "share_of_updates_below_0.5": 0.5793475585216328,
      "reversal_count": 0,
      "skipped_updates": 44467,
      "trace_rows": 255931
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
    "0, 41232 MiB, 49140 MiB, 57 %",
    "1, 41232 MiB, 49140 MiB, 50 %",
    "2, 41232 MiB, 49140 MiB, 46 %",
    "3, 41232 MiB, 49140 MiB, 48 %",
    "4, 1 MiB, 49140 MiB, 0 %",
    "5, 1 MiB, 49140 MiB, 0 %",
    "6, 1 MiB, 49140 MiB, 0 %",
    "7, 1 MiB, 49140 MiB, 0 %"
  ],
  "processes": [
    "3610353 3155584       01:07 /bin/bash -c rg -l 'V27_COMPLETE|typed_outcomes|V27_' logs_eval logs_rl scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905 2>/dev/null | sort | tail -150",
    "3610354 3610353       01:07 rg -l V27_COMPLETE|typed_outcomes|V27_ logs_eval logs_rl scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905",
    "3611068 3155584       00:00 /bin/bash -c set -euo pipefail V27PY=/home/baoquanc/anaconda3/envs/isaaclab/bin/python V27TRAIN=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train $V27PY scriptsFORhuman/v27/v27_readout.py \\   --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step4000/reducer.json \\   --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step4000.json \\   --train-root \"$V27TRAIN\" \\   --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step3000/reducer.json \\   --output scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step4000_full_readout_20260911.md & pid4000=$! $V27PY scriptsFORhuman/v27/v27_readout.py \\   --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step5000/reducer.json \\   --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step5000.json \\   --train-root \"$V27TRAIN\" \\   --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step4000/reducer.json \\   --output scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step5000_full_readout_20260911.md & pid5000=$! wait \"$pid4000\" wait \"$pid5000\"",
    "3611085 3611068       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step4000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step4000.json --train-root /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step3000/reducer.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step4000_full_readout_20260911.md",
    "3611086 3611068       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step5000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step5000.json --train-root /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step4000/reducer.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_c_step5000_full_readout_20260911.md"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_c/step4000/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_c/step4000.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。
