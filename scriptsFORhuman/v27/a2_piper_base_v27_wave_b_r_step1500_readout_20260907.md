# base_v27 wave_b_r/step1500 readout

2026-09-07 04:35 HKT

状态：`V27_COMPLETE`；step=1500；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| R0_S41 | nominal | left | 58/64/64/64/64/64/52 | 0 | 675.9775390625 | 1.2419639825820923 | 428.0 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | nominal | right | 29/64/64/64/64/64/47 | 64 | 0.0 | 1.1406971216201782 | 453.0 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | injected | left | 26/64/62/62/62/62/49 | 2 | 539.7586059570312 | 1.2374811172485352 | 429.0 | 0.0 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |
| R0_S41 | injected | right | 40/64/64/64/64/64/48 | 64 | 0.0 | 1.1443880796432495 | 456.0 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | sham | left | 58/64/64/64/64/64/52 | 0 | 675.9775390625 | 1.2419639825820923 | 428.0 | 0.0 | {"complete": 64} | 0 |
| R0_S41 | sham | right | 29/64/64/64/64/64/47 | 64 | 0.0 | 1.1406971216201782 | 453.0 | 0.0 | {"complete": 64} | 0 |
| R2_S41 | nominal | left | 27/63/63/63/63/63/7 | 58 | 0.0 | 0.9029639363288879 | 424.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| R2_S41 | nominal | right | 28/63/62/62/62/62/41 | 62 | 0.0 | 1.1142686605453491 | 476.0 | 0.0 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |
| R2_S41 | injected | left | 22/63/63/63/63/63/7 | 56 | None | 0.903434693813324 | 422.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| R2_S41 | injected | right | 27/63/62/62/62/62/43 | 61 | 0.0 | 1.1292741298675537 | 478.0 | 0.0 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |
| R2_S41 | sham | left | 27/63/63/63/63/63/7 | 58 | 0.0 | 0.9029639363288879 | 424.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| R2_S41 | sham | right | 28/63/62/62/62/62/41 | 62 | 0.0 | 1.1142686605453491 | 476.0 | 0.0 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "R2_S41−R0_S41": {
      "nominal": {
        "left": {
          "D": -31,
          "S3+": -1,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": -1,
          "clean_complete": -45
        },
        "right": {
          "D": -1,
          "S3+": -1,
          "S4+": -2,
          "open_hold": -2,
          "S5+": -2,
          "complete": -2,
          "clean_complete": -6
        }
      },
      "injected": {
        "left": {
          "D": -4,
          "S3+": -1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 1,
          "complete": 1,
          "clean_complete": -42
        },
        "right": {
          "D": -13,
          "S3+": -1,
          "S4+": -2,
          "open_hold": -2,
          "S5+": -2,
          "complete": -2,
          "clean_complete": -5
        }
      },
      "sham": {
        "left": {
          "D": -31,
          "S3+": -1,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": -1,
          "clean_complete": -45
        },
        "right": {
          "D": -1,
          "S3+": -1,
          "S4+": -2,
          "open_hold": -2,
          "S5+": -2,
          "complete": -2,
          "clean_complete": -6
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
        "D": -31,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1,
        "clean_complete": -45
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -1,
        "S3+": -1,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2,
        "complete": -2,
        "clean_complete": -6
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "injected",
      "side": "left",
      "negative_deltas": {
        "D": -4,
        "S3+": -1,
        "clean_complete": -42
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "injected",
      "side": "right",
      "negative_deltas": {
        "D": -13,
        "S3+": -1,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2,
        "complete": -2,
        "clean_complete": -5
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "sham",
      "side": "left",
      "negative_deltas": {
        "D": -31,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1,
        "clean_complete": -45
      }
    },
    {
      "reference": "R2_S41−R0_S41",
      "stratum": "sham",
      "side": "right",
      "negative_deltas": {
        "D": -1,
        "S3+": -1,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2,
        "complete": -2,
        "clean_complete": -6
      }
    },
    {
      "reference": "R0_S41−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -1
      }
    },
    {
      "reference": "R0_S41−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -29
      }
    },
    {
      "reference": "R0_S41−previous",
      "stratum": "injected",
      "side": "right",
      "negative_deltas": {
        "D": -20
      }
    },
    {
      "reference": "R0_S41−previous",
      "stratum": "sham",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -1
      }
    },
    {
      "reference": "R0_S41−previous",
      "stratum": "sham",
      "side": "right",
      "negative_deltas": {
        "D": -29
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -11
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "injected",
      "side": "left",
      "negative_deltas": {
        "S3+": -1
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "injected",
      "side": "right",
      "negative_deltas": {
        "D": -12
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "sham",
      "side": "left",
      "negative_deltas": {
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1
      }
    },
    {
      "reference": "R2_S41−previous",
      "stratum": "sham",
      "side": "right",
      "negative_deltas": {
        "D": -11
      }
    }
  ]
}
```

## Typed outcomes

```json
{
  "qualification": {
    "outcome": "UNRESOLVED",
    "selected_candidate": null
  },
  "wave_a": {
    "outcome": "UNRESOLVED",
    "recipe_a": null,
    "labels": []
  },
  "wave_b_domain": {
    "outcome": "UNRESOLVED",
    "recipe_b": null
  },
  "recovery": {
    "outcome": "UNRESOLVED"
  },
  "wave_c": {
    "sc_outcome": "UNRESOLVED",
    "sk_outcome": "UNRESOLVED"
  }
}
```

## 质量失败成分、K 与恢复 telemetry

```json
{
  "quality": {
    "R0_S41/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 1,
      "complete_with_body_contact_above_5N": 11,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 17,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/injected/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 13,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/injected/right": {
      "complete_with_crossing_hinge_below_threshold": 16,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/sham/left": {
      "complete_with_crossing_hinge_below_threshold": 1,
      "complete_with_body_contact_above_5N": 11,
      "complete_without_crossing_measurement": 0
    },
    "R0_S41/sham/right": {
      "complete_with_crossing_hinge_below_threshold": 17,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 55,
      "complete_with_body_contact_above_5N": 7,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 21,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/injected/left": {
      "complete_with_crossing_hinge_below_threshold": 56,
      "complete_with_body_contact_above_5N": 5,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/injected/right": {
      "complete_with_crossing_hinge_below_threshold": 19,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/sham/left": {
      "complete_with_crossing_hinge_below_threshold": 55,
      "complete_with_body_contact_above_5N": 7,
      "complete_without_crossing_measurement": 0
    },
    "R2_S41/sham/right": {
      "complete_with_crossing_hinge_below_threshold": 21,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    }
  },
  "k": {},
  "training": {
    "R0_S41": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41/runtime.log",
      "iteration": 1500,
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
      "iteration": 1500,
      "metrics": {
        "a2_v27_bank_raw_capture_left": 46480.5781,
        "a2_v27_bank_promotion_left": 46480.5781,
        "a2_v27_bank_eligible_reset_left": 511999.0,
        "a2_v27_bank_reset_left": 101961.25,
        "a2_v27_bank_available_left": 46480.5781,
        "a2_v27_bank_raw_capture_right": 52857.0,
        "a2_v27_bank_promotion_right": 46480.5781,
        "a2_v27_bank_eligible_reset_right": 556654.75,
        "a2_v27_bank_reset_right": 111300.3594,
        "a2_v27_bank_available_right": 46480.5781
      },
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    }
  },
  "recovery": {
    "R0_S41/injected/left": {
      "denominator": 64,
      "loss_events": 21,
      "not_triggered": 0,
      "regrasp_success": 3,
      "recovered_complete": 3,
      "recovered_clean_complete": 3
    },
    "R0_S41/injected/right": {
      "denominator": 64,
      "loss_events": 1,
      "not_triggered": 0,
      "regrasp_success": 1,
      "recovered_complete": 1,
      "recovered_clean_complete": 1
    },
    "R2_S41/injected/left": {
      "denominator": 64,
      "loss_events": 5,
      "not_triggered": 1,
      "regrasp_success": 5,
      "recovered_complete": 5,
      "recovered_clean_complete": 0
    },
    "R2_S41/injected/right": {
      "denominator": 64,
      "loss_events": 2,
      "not_triggered": 1,
      "regrasp_success": 2,
      "recovered_complete": 2,
      "recovered_clean_complete": 1
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
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r0_s41/RUN_RECEIPT.json"
    },
    "v27_train_r1_s41": {
      "state": "FAIL",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r1_s41/RUN_RECEIPT.json"
    },
    "v27_train_r2_s41": {
      "state": "RUNNING",
      "returncode": 0,
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
    "2, 12934 MiB, 49140 MiB, 36 %",
    "3, 12932 MiB, 49140 MiB, 19 %",
    "4, 13670 MiB, 49140 MiB, 20 %",
    "5, 1 MiB, 49140 MiB, 0 %",
    "6, 1 MiB, 49140 MiB, 0 %",
    "7, 1 MiB, 49140 MiB, 0 %"
  ],
  "processes": [
    "2254446 2692622    11:12:18 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l0_s31/run.sh",
    "2254448 2254446    11:12:18 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell L0_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31",
    "2254466 2254448    11:12:17 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L0_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31/output project_name=base_v27_bilateral_hardening experiment_name=V27_L0_S31",
    "2258700 2692622    11:11:20 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_b/run.sh",
    "2258703 2258700    11:11:20 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave B",
    "2272779 2692622    11:00:02 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s31_r1/run.sh",
    "2272782 2272779    11:00:02 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell L1_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1",
    "2272794 2272782    11:00:01 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S31",
    "2272812 2692622    11:00:01 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s32_r1/run.sh",
    "2272814 2272812    11:00:01 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell L1_S32 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1",
    "2272829 2272814    10:59:59 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S32 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S32",
    "2675589 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_r/step1500/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_r/step1500.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_b_r_step1500_readout_20260907.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_r/step1000/reducer.json"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_r/step1500/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_r/step1500.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## Q_R endpoint冻结

`UNRESOLVED`：R1因读取器误停于644，没有1500 endpoint；不重启、不用500替代。R0/R2完整1500及12条评估均PASS/0、exact64、integrity0。可用的R2注入重抓为5/64、2/64，恢复后clean为0/64、1/64，不满足R2 pilot计数线。不能由R2单独代替完整三臂结论。Q_R不阻塞Wave C；待L endpoint后执行下一阶段。

全部模式恢复telemetry：

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
    "loss_event": 14,
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
    "loss_event": 21,
    "regrasp_success": 3,
    "recovered_complete": 3,
    "recovered_clean_complete": 3
  },
  "R0_S41/injected/right": {
    "episodes": 64,
    "injection_status": {
      "TRIGGERED": 64
    },
    "applied_steps_observed": [
      6
    ],
    "loss_event": 1,
    "regrasp_success": 1,
    "recovered_complete": 1,
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
    "loss_event": 14,
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
      "NOT_TRIGGERED": 1,
      "TRIGGERED": 63
    },
    "applied_steps_observed": [
      0,
      6
    ],
    "loss_event": 5,
    "regrasp_success": 5,
    "recovered_complete": 5,
    "recovered_clean_complete": 0
  },
  "R2_S41/injected/right": {
    "episodes": 64,
    "injection_status": {
      "NOT_TRIGGERED": 1,
      "TRIGGERED": 63
    },
    "applied_steps_observed": [
      0,
      6
    ],
    "loss_event": 2,
    "regrasp_success": 2,
    "recovered_complete": 2,
    "recovered_clean_complete": 1
  },
  "R2_S41/sham/left": {
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
  "R2_S41/sham/right": {
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
  }
}
```
