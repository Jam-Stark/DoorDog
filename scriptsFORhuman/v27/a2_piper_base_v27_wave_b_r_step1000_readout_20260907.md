# base_v27 wave_b_r/step1000 readout

2026-09-07 02:31 HKT

状态：`V27_COMPLETE`；step=1000；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| R0_S41 | nominal | left | 54/64/64/64/64/64/53 | 2 | 413.3185729980469 | 1.2013535499572754 | 434.0 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | nominal | right | 58/64/61/61/61/61/22 | 61 | 58.49103546142578 | 1.0679270029067993 | 545.0 | 0.0 | {"upper_dof_overspeed": 3, "complete": 61} | 0 |
| R0_S41 | injected | left | 13/64/60/60/60/58/43 | 4 | 135.1322021484375 | 1.2000732421875 | 434.0 | 0.0 | {"upper_dof_overspeed": 5, "complete": 58, "stage_overtime": 1} | 0 |
| R0_S41 | injected | right | 60/63/63/63/62/62/20 | 62 | 94.43159484863281 | 1.0473695993423462 | 552.0 | 0.0 | {"stage_overtime": 2, "complete": 62} | 0 |
| R0_S41 | sham | left | 54/64/64/64/64/64/53 | 2 | 413.3185729980469 | 1.2013535499572754 | 434.0 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | sham | right | 58/64/61/61/61/61/22 | 61 | 58.49103546142578 | 1.0679270029067993 | 545.0 | 0.0 | {"upper_dof_overspeed": 3, "complete": 61} | 0 |
| R2_S41 | nominal | left | 27/64/64/64/64/64/0 | 57 | None | 0.8845617771148682 | 453.0 | 0.0 | {"complete": 64} | 0 |
| R2_S41 | nominal | right | 39/61/61/61/61/61/28 | 61 | 44.14923095703125 | 1.0625059604644775 | 518.0 | 0.0 | {"stage_overtime": 3, "complete": 61} | 0 |
| R2_S41 | injected | left | 9/64/63/62/60/60/1 | 54 | None | 0.8837664127349854 | 458.0 | 0.0006215469613259668 | {"upper_dof_overspeed": 3, "stage_overtime": 1, "complete": 60} | 0 |
| R2_S41 | injected | right | 39/61/61/61/60/59/25 | 61 | 90.7217788696289 | 1.0774670839309692 | 533.0 | 0.0 | {"upper_dof_overspeed": 2, "stage_overtime": 3, "complete": 59} | 0 |
| R2_S41 | sham | left | 27/64/64/64/64/64/0 | 57 | None | 0.8845617771148682 | 453.0 | 0.0 | {"complete": 64} | 0 |
| R2_S41 | sham | right | 39/61/61/61/61/61/28 | 61 | 44.14923095703125 | 1.0625059604644775 | 518.0 | 0.0 | {"stage_overtime": 3, "complete": 61} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "R2_S41−R0_S41": {
      "nominal": {
        "left": {
          "D": -27,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 0,
          "complete": 0,
          "clean_complete": -53
        },
        "right": {
          "D": -19,
          "S3+": -3,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 0,
          "complete": 0,
          "clean_complete": 6
        }
      },
      "injected": {
        "left": {
          "D": -4,
          "S3+": 0,
          "S4+": 3,
          "open_hold": 2,
          "S5+": 0,
          "complete": 2,
          "clean_complete": -42
        },
        "right": {
          "D": -21,
          "S3+": -2,
          "S4+": -2,
          "open_hold": -2,
          "S5+": -2,
          "complete": -3,
          "clean_complete": 5
        }
      },
      "sham": {
        "left": {
          "D": -27,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 0,
          "complete": 0,
          "clean_complete": -53
        },
        "right": {
          "D": -19,
          "S3+": -3,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 0,
          "complete": 0,
          "clean_complete": 6
        }
      }
    }
  },
  "negative_deltas": [
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -27,
        "clean_complete": -53
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -19,
        "S3+": -3
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "injected",
      "side": "left",
      "negative_deltas": {
        "D": -4,
        "clean_complete": -42
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "injected",
      "side": "right",
      "negative_deltas": {
        "D": -21,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2,
        "complete": -3
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "sham",
      "side": "left",
      "negative_deltas": {
        "D": -27,
        "clean_complete": -53
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "sham",
      "side": "right",
      "negative_deltas": {
        "D": -19,
        "S3+": -3
      }
    },
    {
      "reference": "R0_S41−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -5
      }
    },
    {
      "reference": "R0_S41−previous",
      "stratum": "injected",
      "side": "left",
      "negative_deltas": {
        "D": -4
      }
    },
    {
      "reference": "R0_S41−previous",
      "stratum": "injected",
      "side": "right",
      "negative_deltas": {
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -2,
        "complete": -2,
        "clean_complete": -11
      }
    },
    {
      "reference": "R0_S41−previous",
      "stratum": "sham",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -5
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -32
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -5
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "injected",
      "side": "left",
      "negative_deltas": {
        "D": -29,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "injected",
      "side": "right",
      "negative_deltas": {
        "D": -7,
        "complete": -1,
        "clean_complete": -11
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "sham",
      "side": "left",
      "negative_deltas": {
        "D": -32
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "sham",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -5
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
    "R0_S41/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 6,
      "complete_with_body_contact_above_5N": 5,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 30,
      "complete_with_body_contact_above_5N": 13,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/injected/left": {
      "complete_with_crossing_hinge_below_threshold": 9,
      "complete_with_body_contact_above_5N": 7,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/injected/right": {
      "complete_with_crossing_hinge_below_threshold": 30,
      "complete_with_body_contact_above_5N": 15,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/sham/left": {
      "complete_with_crossing_hinge_below_threshold": 6,
      "complete_with_body_contact_above_5N": 5,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/sham/right": {
      "complete_with_crossing_hinge_below_threshold": 30,
      "complete_with_body_contact_above_5N": 13,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 64,
      "complete_with_body_contact_above_5N": 37,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 28,
      "complete_with_body_contact_above_5N": 5,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/injected/left": {
      "complete_with_crossing_hinge_below_threshold": 57,
      "complete_with_body_contact_above_5N": 32,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/injected/right": {
      "complete_with_crossing_hinge_below_threshold": 28,
      "complete_with_body_contact_above_5N": 7,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/sham/left": {
      "complete_with_crossing_hinge_below_threshold": 64,
      "complete_with_body_contact_above_5N": 37,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/sham/right": {
      "complete_with_crossing_hinge_below_threshold": 28,
      "complete_with_body_contact_above_5N": 5,
      "complete_without_crossing_measurement": 0
    }
  },
  "k": {},
  "training": {
    "R0_S41": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41/runtime.log",
      "iteration": 1000,
      "metrics": {
        "a2_v27_bank_raw_capture_left": 0.0,
        "a2_v27_bank_promotion_left": 0.0,
        "a2_v27_bank_eligible_reset_left": 0.0,
        "a2_v27_bank_reset_left": 0.0,
        "a2_v27_bank_available_left": 0.0,
        "a2_v27_bank_raw_capture_right": 0.0,
        "a2_v27_bank_promotion_right": 0.0,
        "a2_v27_bank_eligible_reset_right": 0.0,
        "a2_v27_bank_reset_right": 0.0,
        "a2_v27_bank_available_right": 0.0
      },
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "R2_S41": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41/runtime.log",
      "iteration": 1000,
      "metrics": {
        "a2_v27_bank_raw_capture_left": 29497.4062,
        "a2_v27_bank_promotion_left": 29497.4062,
        "a2_v27_bank_eligible_reset_left": 310381.0,
        "a2_v27_bank_reset_left": 61709.75,
        "a2_v27_bank_available_left": 29497.4062,
        "a2_v27_bank_raw_capture_right": 33254.5625,
        "a2_v27_bank_promotion_right": 29497.4062,
        "a2_v27_bank_eligible_reset_right": 345657.375,
        "a2_v27_bank_reset_right": 69275.0938,
        "a2_v27_bank_available_right": 29497.4062
      },
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    }
  },
  "recovery": {
    "R0_S41/injected/left": {
      "denominator": 64,
      "loss_events": 40,
      "not_triggered": 0,
      "regrasp_success": 23,
      "recovered_complete": 19,
      "recovered_clean_complete": 15
    },
    "R0_S41/injected/right": {
      "denominator": 64,
      "loss_events": 5,
      "not_triggered": 1,
      "regrasp_success": 5,
      "recovered_complete": 4,
      "recovered_clean_complete": 1
    },
    "R2_S41/injected/left": {
      "denominator": 64,
      "loss_events": 11,
      "not_triggered": 0,
      "regrasp_success": 10,
      "recovered_complete": 10,
      "recovered_clean_complete": 0
    },
    "R2_S41/injected/right": {
      "denominator": 64,
      "loss_events": 0,
      "not_triggered": 3,
      "regrasp_success": 0,
      "recovered_complete": 0,
      "recovered_clean_complete": 0
    }
  }
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
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l0_s31/RUN_RECEIPT.json"
    },
    "v27_train_l1_s31": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s31/RUN_RECEIPT.json"
    },
    "v27_train_l1_s31_r1": {
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s31_r1/RUN_RECEIPT.json"
    },
    "v27_train_l1_s32": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s32/RUN_RECEIPT.json"
    },
    "v27_train_l1_s32_r1": {
      "state": "RUNNING",
      "returncode": null,
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
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r0_s41/RUN_RECEIPT.json"
    },
    "v27_train_r1_s41": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r1_s41/RUN_RECEIPT.json"
    },
    "v27_train_r2_s41": {
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r2_s41/RUN_RECEIPT.json"
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
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_b/RUN_RECEIPT.json"
    }
  },
  "gpu": [
    "0, 1 MiB, 49140 MiB, 0 %",
    "1, 1 MiB, 49140 MiB, 0 %",
    "2, 12926 MiB, 49140 MiB, 12 %",
    "3, 13654 MiB, 49140 MiB, 15 %",
    "4, 12918 MiB, 49140 MiB, 10 %",
    "5, 12798 MiB, 49140 MiB, 27 %",
    "6, 1 MiB, 49140 MiB, 0 %",
    "7, 13534 MiB, 49140 MiB, 18 %"
  ],
  "processes": [
    "2254446 2692622    09:07:57 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l0_s31/run.sh",
    "2254448 2254446    09:07:57 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell L0_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31",
    "2254466 2254448    09:07:56 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L0_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31/output project_name=base_v27_bilateral_hardening experiment_name=V27_L0_S31",
    "2254546 2692622    09:07:52 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r0_s41/run.sh",
    "2254548 2254546    09:07:52 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 5 --cell R0_S41 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41",
    "2254584 2254548    09:07:51 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_R0_S41 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41/output project_name=base_v27_bilateral_hardening experiment_name=V27_R0_S41",
    "2254696 2692622    09:07:49 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r2_s41/run.sh",
    "2254698 2254696    09:07:49 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 7 --cell R2_S41 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41",
    "2254791 2254698    09:07:48 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_R2_S41 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41/output project_name=base_v27_bilateral_hardening experiment_name=V27_R2_S41",
    "2258700 2692622    09:06:59 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_b/run.sh",
    "2258703 2258700    09:06:59 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave B",
    "2272779 2692622    08:55:42 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s31_r1/run.sh",
    "2272782 2272779    08:55:42 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell L1_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1",
    "2272794 2272782    08:55:40 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S31",
    "2272812 2692622    08:55:40 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s32_r1/run.sh",
    "2272814 2272812    08:55:40 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell L1_S32 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1",
    "2272829 2272814    08:55:39 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S32 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S32",
    "2607195 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_r/step1000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_r/step1000.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_b_r_step1000_readout_20260907.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_r/step500_cpu_reader_corrected/reducer.json"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_r/step1000/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_r/step1000.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## R1未运行与全模式恢复telemetry

R1保持STOPPED644，未运行1000评估；不引用其500数据作为1000对照。nominal与sham所有reducer质量字段逐侧完全相同，sham实际注入步数为0。

```json
{
  "R0_S41/nominal/left": {
    "episodes": 64,
    "injection_status": {
      "NOT_TRIGGERED": 64
    },
    "applied_steps_observed": [
      0
    ],
    "loss_event": 27,
    "regrasp_success": 0,
    "recovered_complete": 0,
    "recovered_clean_complete": 0
  },
  "R0_S41/nominal/right": {
    "episodes": 64,
    "injection_status": {
      "NOT_TRIGGERED": 64
    },
    "applied_steps_observed": [
      0
    ],
    "loss_event": 0,
    "regrasp_success": 0,
    "recovered_complete": 0,
    "recovered_clean_complete": 0
  },
  "R0_S41/injected/left": {
    "episodes": 64,
    "injection_status": {
      "TRIGGERED": 64
    },
    "applied_steps_observed": [
      6
    ],
    "loss_event": 40,
    "regrasp_success": 23,
    "recovered_complete": 19,
    "recovered_clean_complete": 15
  },
  "R0_S41/injected/right": {
    "episodes": 64,
    "injection_status": {
      "NOT_TRIGGERED": 1,
      "TRIGGERED": 63
    },
    "applied_steps_observed": [
      0,
      6
    ],
    "loss_event": 5,
    "regrasp_success": 5,
    "recovered_complete": 4,
    "recovered_clean_complete": 1
  },
  "R0_S41/sham/left": {
    "episodes": 64,
    "injection_status": {
      "TRIGGERED": 64
    },
    "applied_steps_observed": [
      0
    ],
    "loss_event": 27,
    "regrasp_success": 0,
    "recovered_complete": 0,
    "recovered_clean_complete": 0
  },
  "R0_S41/sham/right": {
    "episodes": 64,
    "injection_status": {
      "TRIGGERED": 64
    },
    "applied_steps_observed": [
      0
    ],
    "loss_event": 0,
    "regrasp_success": 0,
    "recovered_complete": 0,
    "recovered_clean_complete": 0
  },
  "R2_S41/nominal/left": {
    "episodes": 64,
    "injection_status": {
      "NOT_TRIGGERED": 64
    },
    "applied_steps_observed": [
      0
    ],
    "loss_event": 0,
    "regrasp_success": 0,
    "recovered_complete": 0,
    "recovered_clean_complete": 0
  },
  "R2_S41/nominal/right": {
    "episodes": 64,
    "injection_status": {
      "NOT_TRIGGERED": 64
    },
    "applied_steps_observed": [
      0
    ],
    "loss_event": 0,
    "regrasp_success": 0,
    "recovered_complete": 0,
    "recovered_clean_complete": 0
  },
  "R2_S41/injected/left": {
    "episodes": 64,
    "injection_status": {
      "TRIGGERED": 64
    },
    "applied_steps_observed": [
      6
    ],
    "loss_event": 11,
    "regrasp_success": 10,
    "recovered_complete": 10,
    "recovered_clean_complete": 0
  },
  "R2_S41/injected/right": {
    "episodes": 64,
    "injection_status": {
      "NOT_TRIGGERED": 3,
      "TRIGGERED": 61
    },
    "applied_steps_observed": [
      0,
      6
    ],
    "loss_event": 0,
    "regrasp_success": 0,
    "recovered_complete": 0,
    "recovered_clean_complete": 0
  },
  "R2_S41/sham/left": {
    "episodes": 64,
    "injection_status": {
      "TRIGGERED": 64
    },
    "applied_steps_observed": [
      0
    ],
    "loss_event": 0,
    "regrasp_success": 0,
    "recovered_complete": 0,
    "recovered_clean_complete": 0
  },
  "R2_S41/sham/right": {
    "episodes": 64,
    "injection_status": {
      "NOT_TRIGGERED": 3,
      "TRIGGERED": 61
    },
    "applied_steps_observed": [
      0
    ],
    "loss_event": 0,
    "regrasp_success": 0,
    "recovered_complete": 0,
    "recovered_clean_complete": 0
  }
}
```
