# base_v27 wave_b_r/step500 readout

2026-09-06 22:13 HKT

状态：`V27_COMPLETE`；step=500；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| R0_S41 | nominal | left | 38/64/42/42/42/39/14 | 39 | 1005.7468872070312 | 1.0940686464309692 | 447.0 | 0.0 | {"upper_dof_overspeed": 25, "complete": 39} | 0 |
| R0_S41 | nominal | right | 53/64/61/61/60/60/27 | 60 | 0.0 | 1.0202231407165527 | 578.0 | 0.0 | {"upper_dof_overspeed": 4, "complete": 60} | 0 |
| R0_S41 | injected | left | 17/63/49/47/47/44/20 | 33 | 1071.7052001953125 | 1.0917649269104004 | 453.0 | 0.0 | {"upper_dof_overspeed": 16, "stage_overtime": 4, "complete": 44} | 0 |
| R0_S41 | injected | right | 54/64/64/64/64/64/31 | 64 | 0.0 | 1.0434900522232056 | 581.0 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | sham | left | 38/64/42/42/42/39/14 | 39 | 1005.7468872070312 | 1.0940686464309692 | 447.0 | 0.0 | {"upper_dof_overspeed": 25, "complete": 39} | 0 |
| R0_S41 | sham | right | 53/64/61/61/60/60/27 | 60 | 0.0 | 1.0202231407165527 | 578.0 | 0.0 | {"upper_dof_overspeed": 4, "complete": 60} | 0 |
| R1_S41 | nominal | left | 54/64/64/64/64/64/3 | 64 | 2637.13232421875 | 1.002701759338379 | 591.0 | 0.00010513312481930245 | {"complete": 64} | 0 |
| R1_S41 | nominal | right | 43/63/63/63/63/63/32 | 63 | 0.0 | 1.0513098239898682 | 553.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| R1_S41 | injected | left | 18/64/64/64/64/64/0 | 64 | 34585.0546875 | 1.012021541595459 | 588.0 | 0.00010507512871703268 | {"complete": 64} | 0 |
| R1_S41 | injected | right | 43/63/63/63/63/63/32 | 63 | 0.0 | 1.048986792564392 | 555.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| R1_S41 | sham | left | 54/64/64/64/64/64/3 | 64 | 2637.13232421875 | 1.002701759338379 | 591.0 | 0.00010513312481930245 | {"complete": 64} | 0 |
| R1_S41 | sham | right | 43/63/63/63/63/63/32 | 63 | 0.0 | 1.0513098239898682 | 553.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| R2_S41 | nominal | left | 59/64/64/64/63/63/0 | 63 | None | 0.8612967729568481 | 504.0 | 0.0 | {"complete": 63, "stage_overtime": 1} | 0 |
| R2_S41 | nominal | right | 39/61/58/58/57/57/33 | 58 | 0.0 | 1.0845073461532593 | 538.0 | 0.0 | {"stage_overtime": 7, "complete": 57} | 0 |
| R2_S41 | injected | left | 38/64/64/63/61/61/0 | 59 | None | 0.8686181306838989 | 499.0 | 0.0 | {"stage_overtime": 3, "complete": 61} | 0 |
| R2_S41 | injected | right | 46/61/61/61/60/60/36 | 61 | 0.0 | 1.0895227193832397 | 543.0 | 0.0 | {"stage_overtime": 4, "complete": 60} | 0 |
| R2_S41 | sham | left | 59/64/64/64/63/63/0 | 63 | None | 0.8612967729568481 | 504.0 | 0.0 | {"complete": 63, "stage_overtime": 1} | 0 |
| R2_S41 | sham | right | 39/61/58/58/57/57/33 | 58 | 0.0 | 1.0845073461532593 | 538.0 | 0.0 | {"stage_overtime": 7, "complete": 57} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "R1_S41−R0_S41": {
      "nominal": {
        "left": {
          "D": 16,
          "S3+": 0,
          "S4+": 22,
          "open_hold": 22,
          "S5+": 22,
          "complete": 25,
          "clean_complete": -11
        },
        "right": {
          "D": -10,
          "S3+": -1,
          "S4+": 2,
          "open_hold": 2,
          "S5+": 3,
          "complete": 3,
          "clean_complete": 5
        }
      },
      "injected": {
        "left": {
          "D": 1,
          "S3+": 1,
          "S4+": 15,
          "open_hold": 17,
          "S5+": 17,
          "complete": 20,
          "clean_complete": -20
        },
        "right": {
          "D": -11,
          "S3+": -1,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": -1,
          "clean_complete": 1
        }
      },
      "sham": {
        "left": {
          "D": 16,
          "S3+": 0,
          "S4+": 22,
          "open_hold": 22,
          "S5+": 22,
          "complete": 25,
          "clean_complete": -11
        },
        "right": {
          "D": -10,
          "S3+": -1,
          "S4+": 2,
          "open_hold": 2,
          "S5+": 3,
          "complete": 3,
          "clean_complete": 5
        }
      }
    },
    "R2_S41−R0_S41": {
      "nominal": {
        "left": {
          "D": 21,
          "S3+": 0,
          "S4+": 22,
          "open_hold": 22,
          "S5+": 21,
          "complete": 24,
          "clean_complete": -14
        },
        "right": {
          "D": -14,
          "S3+": -3,
          "S4+": -3,
          "open_hold": -3,
          "S5+": -3,
          "complete": -3,
          "clean_complete": 6
        }
      },
      "injected": {
        "left": {
          "D": 21,
          "S3+": 1,
          "S4+": 15,
          "open_hold": 16,
          "S5+": 14,
          "complete": 17,
          "clean_complete": -20
        },
        "right": {
          "D": -8,
          "S3+": -3,
          "S4+": -3,
          "open_hold": -3,
          "S5+": -4,
          "complete": -4,
          "clean_complete": 5
        }
      },
      "sham": {
        "left": {
          "D": 21,
          "S3+": 0,
          "S4+": 22,
          "open_hold": 22,
          "S5+": 21,
          "complete": 24,
          "clean_complete": -14
        },
        "right": {
          "D": -14,
          "S3+": -3,
          "S4+": -3,
          "open_hold": -3,
          "S5+": -3,
          "complete": -3,
          "clean_complete": 6
        }
      }
    }
  },
  "negative_deltas": [
    {
      "reference": "R1_S41−R0_S41",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -11
      }
    },
    {
      "reference": "R1_S41−R0_S41",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -10,
        "S3+": -1
      }
    },
    {
      "reference": "R1_S41−R0_S41",
      "stratum": "injected",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -20
      }
    },
    {
      "reference": "R1_S41−R0_S41",
      "stratum": "injected",
      "side": "right",
      "negative_deltas": {
        "D": -11,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1
      }
    },
    {
      "reference": "R1_S41−R0_S41",
      "stratum": "sham",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -11
      }
    },
    {
      "reference": "R1_S41−R0_S41",
      "stratum": "sham",
      "side": "right",
      "negative_deltas": {
        "D": -10,
        "S3+": -1
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -14
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -14,
        "S3+": -3,
        "S4+": -3,
        "open_hold": -3,
        "S5+": -3,
        "complete": -3
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "injected",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -20
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "injected",
      "side": "right",
      "negative_deltas": {
        "D": -8,
        "S3+": -3,
        "S4+": -3,
        "open_hold": -3,
        "S5+": -4,
        "complete": -4
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "sham",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -14
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "sham",
      "side": "right",
      "negative_deltas": {
        "D": -14,
        "S3+": -3,
        "S4+": -3,
        "open_hold": -3,
        "S5+": -3,
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
    "R0_S41/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 13,
      "complete_with_body_contact_above_5N": 16,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 31,
      "complete_with_body_contact_above_5N": 2,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/injected/left": {
      "complete_with_crossing_hinge_below_threshold": 15,
      "complete_with_body_contact_above_5N": 17,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/injected/right": {
      "complete_with_crossing_hinge_below_threshold": 32,
      "complete_with_body_contact_above_5N": 1,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/sham/left": {
      "complete_with_crossing_hinge_below_threshold": 13,
      "complete_with_body_contact_above_5N": 16,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/sham/right": {
      "complete_with_crossing_hinge_below_threshold": 31,
      "complete_with_body_contact_above_5N": 2,
      "complete_without_crossing_measurement": 0
    },
    "R1_S41/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 39,
      "complete_with_body_contact_above_5N": 58,
      "complete_without_crossing_measurement": 0
    },
    "R1_S41/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 31,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R1_S41/injected/left": {
      "complete_with_crossing_hinge_below_threshold": 38,
      "complete_with_body_contact_above_5N": 62,
      "complete_without_crossing_measurement": 0
    },
    "R1_S41/injected/right": {
      "complete_with_crossing_hinge_below_threshold": 31,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R1_S41/sham/left": {
      "complete_with_crossing_hinge_below_threshold": 39,
      "complete_with_body_contact_above_5N": 58,
      "complete_without_crossing_measurement": 0
    },
    "R1_S41/sham/right": {
      "complete_with_crossing_hinge_below_threshold": 31,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 61,
      "complete_with_body_contact_above_5N": 60,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 24,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/injected/left": {
      "complete_with_crossing_hinge_below_threshold": 57,
      "complete_with_body_contact_above_5N": 59,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/injected/right": {
      "complete_with_crossing_hinge_below_threshold": 24,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/sham/left": {
      "complete_with_crossing_hinge_below_threshold": 61,
      "complete_with_body_contact_above_5N": 60,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/sham/right": {
      "complete_with_crossing_hinge_below_threshold": 24,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    }
  },
  "k": {},
  "training": {
    "R0_S41": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41/runtime.log",
      "iteration": 500,
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
    "R1_S41": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R1_S41/runtime.log",
      "iteration": 500,
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
      "iteration": 500,
      "metrics": {
        "a2_v27_bank_raw_capture_left": 14078.0938,
        "a2_v27_bank_promotion_left": 14078.0938,
        "a2_v27_bank_eligible_reset_left": 133174.9844,
        "a2_v27_bank_reset_left": 26630.3125,
        "a2_v27_bank_available_left": 14078.0938,
        "a2_v27_bank_raw_capture_right": 16828.6562,
        "a2_v27_bank_promotion_right": 14078.0938,
        "a2_v27_bank_eligible_reset_right": 161570.6719,
        "a2_v27_bank_reset_right": 32415.9688,
        "a2_v27_bank_available_right": 14078.0938
      },
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    }
  },
  "recovery": {
    "R0_S41/injected/left": {
      "denominator": 64,
      "loss_events": 12,
      "not_triggered": 11,
      "regrasp_success": 7,
      "recovered_complete": 3,
      "recovered_clean_complete": 0
    },
    "R0_S41/injected/right": {
      "denominator": 64,
      "loss_events": 0,
      "not_triggered": 0,
      "regrasp_success": 0,
      "recovered_complete": 0,
      "recovered_clean_complete": 0
    },
    "R1_S41/injected/left": {
      "denominator": 64,
      "loss_events": 0,
      "not_triggered": 0,
      "regrasp_success": 0,
      "recovered_complete": 0,
      "recovered_clean_complete": 0
    },
    "R1_S41/injected/right": {
      "denominator": 64,
      "loss_events": 0,
      "not_triggered": 1,
      "regrasp_success": 0,
      "recovered_complete": 0,
      "recovered_clean_complete": 0
    },
    "R2_S41/injected/left": {
      "denominator": 64,
      "loss_events": 6,
      "not_triggered": 0,
      "regrasp_success": 4,
      "recovered_complete": 3,
      "recovered_clean_complete": 0
    },
    "R2_S41/injected/right": {
      "denominator": 64,
      "loss_events": 1,
      "not_triggered": 3,
      "regrasp_success": 1,
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
    "2, 13716 MiB, 49140 MiB, 48 %",
    "3, 13732 MiB, 49140 MiB, 15 %",
    "4, 14324 MiB, 49140 MiB, 15 %",
    "5, 12782 MiB, 49140 MiB, 12 %",
    "6, 1 MiB, 49140 MiB, 0 %",
    "7, 13134 MiB, 49140 MiB, 11 %"
  ],
  "processes": [
    "2254446 2692622    04:50:36 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l0_s31/run.sh",
    "2254448 2254446    04:50:36 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell L0_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31",
    "2254466 2254448    04:50:35 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L0_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31/output project_name=base_v27_bilateral_hardening experiment_name=V27_L0_S31",
    "2254546 2692622    04:50:31 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r0_s41/run.sh",
    "2254548 2254546    04:50:31 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 5 --cell R0_S41 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41",
    "2254584 2254548    04:50:30 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_R0_S41 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41/output project_name=base_v27_bilateral_hardening experiment_name=V27_R0_S41",
    "2254696 2692622    04:50:28 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r2_s41/run.sh",
    "2254698 2254696    04:50:28 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 7 --cell R2_S41 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41",
    "2254791 2254698    04:50:27 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_R2_S41 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41/output project_name=base_v27_bilateral_hardening experiment_name=V27_R2_S41",
    "2258700 2692622    04:49:38 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_b/run.sh",
    "2258703 2258700    04:49:38 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave B",
    "2272779 2692622    04:38:21 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s31_r1/run.sh",
    "2272782 2272779    04:38:21 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell L1_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1",
    "2272794 2272782    04:38:19 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S31",
    "2272812 2692622    04:38:19 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s32_r1/run.sh",
    "2272814 2272812    04:38:19 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell L1_S32 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1",
    "2272829 2272814    04:38:18 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S32 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S32",
    "2444147 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_r/step500_cpu_reader_corrected/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_r/step500.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_b_r_step500_readout_20260906.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_r/step500_cpu_reader_corrected/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_r/step500.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## 读取器修正与训练停格

原始R1 nominal LEFT trace为合法706502006-byte JSON，32774 rows。旧分块reader在对象结束/下一块逗号的边界误判INVALID，自动停止R1于644。已移除该reader，改用标准库json.load；10项CPU测试通过。只对原18条artifact做了一次CPU重读，全部exact64、integrity0；未重跑policy或评估、未改原artifact/原INVALID结果。

R1操作状态仍为STOPPED；不擅自恢复训练，不用step500代替1500 endpoint。其余五格继续。此处V27_COMPLETE仅表示本次step500数据读取与合同完整，不表示R1训练已完成。

nominal与sham的全部reducer质量字段逐格逐侧相同；sham有eligibility触发记录但实际注入步数为0。所有模式的终端恢复telemetry如下：

```json
{
  "source_manifest": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_r/step500.json",
  "all_mode_terminal_telemetry": {
    "R0_S41/nominal/left": {
      "episodes": 64,
      "injection_status": {
        "NOT_TRIGGERED": 64
      },
      "applied_steps_observed": [
        0
      ],
      "loss_event": 1,
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
        "NOT_TRIGGERED": 11,
        "TRIGGERED": 53
      },
      "applied_steps_observed": [
        0,
        6
      ],
      "loss_event": 12,
      "regrasp_success": 7,
      "recovered_complete": 3,
      "recovered_clean_complete": 0
    },
    "R0_S41/injected/right": {
      "episodes": 64,
      "injection_status": {
        "TRIGGERED": 64
      },
      "applied_steps_observed": [
        6
      ],
      "loss_event": 0,
      "regrasp_success": 0,
      "recovered_complete": 0,
      "recovered_clean_complete": 0
    },
    "R0_S41/sham/left": {
      "episodes": 64,
      "injection_status": {
        "NOT_TRIGGERED": 10,
        "TRIGGERED": 54
      },
      "applied_steps_observed": [
        0
      ],
      "loss_event": 1,
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
    "R1_S41/nominal/left": {
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
    "R1_S41/nominal/right": {
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
    "R1_S41/injected/left": {
      "episodes": 64,
      "injection_status": {
        "TRIGGERED": 64
      },
      "applied_steps_observed": [
        6
      ],
      "loss_event": 0,
      "regrasp_success": 0,
      "recovered_complete": 0,
      "recovered_clean_complete": 0
    },
    "R1_S41/injected/right": {
      "episodes": 64,
      "injection_status": {
        "NOT_TRIGGERED": 1,
        "TRIGGERED": 63
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
    "R1_S41/sham/left": {
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
    "R1_S41/sham/right": {
      "episodes": 64,
      "injection_status": {
        "NOT_TRIGGERED": 1,
        "TRIGGERED": 63
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
      "loss_event": 4,
      "regrasp_success": 2,
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
      "loss_event": 6,
      "regrasp_success": 4,
      "recovered_complete": 3,
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
      "loss_event": 1,
      "regrasp_success": 1,
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
      "loss_event": 4,
      "regrasp_success": 2,
      "recovered_complete": 0,
      "recovered_clean_complete": 0
    }
  }
}
```

本次注入ITT的R2 regrasp_success为LEFT4/64、RIGHT1/64，recovered_clean_complete均0；R2−R1重抓计数为+4/+1，不能据此给出pilot收益结论。训练bank累计快照为PPO batch均值，完整原生值见JSON sidecar。

## nominal相对研究父策略C_S2的历史率差

Q0 DEV每侧128与本次每侧64，以下为描述性百分点差，不作逐episode配对。

| Cell/侧 | D Δpp | S3+ Δpp | S4+ Δpp | open_hold Δpp | S5+ Δpp | complete Δpp | clean Δpp |
|---|---:|---:|---:|---:|---:|---:|---:|
| R0_S41/left | -28.91 | +0.00 | -34.38 | -34.38 | -34.38 | -39.06 | -36.72 |
| R0_S41/right | -2.34 | +0.00 | -4.69 | -4.69 | -6.25 | -6.25 | -11.72 |
| R1_S41/left | -3.91 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | -53.91 |
| R1_S41/right | -17.97 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | -3.91 |
| R2_S41/left | +3.91 | +0.00 | +0.00 | +0.00 | -1.56 | -1.56 | -58.59 |
| R2_S41/right | -24.22 | -4.69 | -9.38 | -9.38 | -10.94 | -10.94 | -2.34 |
