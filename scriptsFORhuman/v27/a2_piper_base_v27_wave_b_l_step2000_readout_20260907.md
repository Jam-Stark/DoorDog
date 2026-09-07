# base_v27 wave_b_l/step2000 readout

2026-09-07 08:14 HKT

状态：`V27_COMPLETE`；step=2000；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| L0_S31 | nominal | left | 42/60/60/59/59/59/23 | 24 | 544.476806640625 | 1.088686466217041 | 412.0 | 0.0 | {"upper_dof_overspeed": 1, "stage_overtime": 4, "complete": 59} | 0 |
| L0_S31 | nominal | right | 40/56/56/56/56/56/39 | 56 | 0.0 | 1.1478569507598877 | 410.0 | 0.03803796278894945 | {"stage_overtime": 8, "complete": 56} | 0 |
| L0_S31 | P02 | left | 37/59/58/58/58/58/16 | 20 | 572.3269653320312 | 1.054004430770874 | 420.0 | 0.0 | {"stage_overtime": 6, "complete": 58} | 0 |
| L0_S31 | P02 | right | 43/59/59/59/59/59/41 | 59 | 0.0 | 1.1552437543869019 | 419.0 | 0.04762602042684043 | {"stage_overtime": 5, "complete": 59} | 0 |
| L0_S31 | P05 | left | 37/59/59/57/58/58/9 | 16 | 911.0093994140625 | 1.0433349609375 | 427.0 | 0.0 | {"stage_overtime": 6, "complete": 58} | 0 |
| L0_S31 | P05 | right | 49/59/59/59/59/59/41 | 59 | 0.0 | 1.14548659324646 | 423.0 | 0.04895867408134336 | {"stage_overtime": 5, "complete": 59} | 0 |
| L1_S31 | nominal | left | 57/63/63/63/63/63/29 | 3 | 594.3803100585938 | 1.1212823390960693 | 410.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S31 | nominal | right | 44/64/64/64/64/64/38 | 64 | 0.0 | 1.0774133205413818 | 405.0 | 0.0 | {"complete": 64} | 0 |
| L1_S31 | P02 | left | 60/61/61/59/61/61/19 | 6 | 1432.470947265625 | 1.0681402683258057 | 413.0 | 0.0 | {"stage_overtime": 3, "complete": 61} | 0 |
| L1_S31 | P02 | right | 41/64/64/64/64/64/37 | 64 | 0.0 | 1.055759310722351 | 407.0 | 0.0 | {"complete": 64} | 0 |
| L1_S31 | P05 | left | 60/61/61/61/61/61/11 | 6 | 400.1104431152344 | 1.0410670042037964 | 420.0 | 0.0 | {"stage_overtime": 3, "complete": 61} | 0 |
| L1_S31 | P05 | right | 41/64/64/64/64/64/34 | 64 | 0.0 | 1.0534178018569946 | 409.0 | 0.0 | {"complete": 64} | 0 |
| L1_S32 | nominal | left | 58/64/64/64/64/63/62 | 30 | 0.0 | 1.5469577312469482 | 418.0 | 0.12262515078407721 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| L1_S32 | nominal | right | 62/64/64/64/64/64/48 | 64 | 0.0 | 1.1542739868164062 | 400.0 | 0.0 | {"complete": 64} | 0 |
| L1_S32 | P02 | left | 61/64/64/64/64/64/62 | 15 | 0.0 | 1.5656218528747559 | 423.0 | 0.12999815395975634 | {"complete": 64} | 0 |
| L1_S32 | P02 | right | 64/64/64/64/64/64/47 | 64 | 0.0 | 1.1522533893585205 | 403.0 | 0.0 | {"complete": 64} | 0 |
| L1_S32 | P05 | left | 59/64/64/64/64/64/58 | 17 | 114.47193908691406 | 1.5428581237792969 | 425.0 | 0.15107623482820579 | {"complete": 64} | 0 |
| L1_S32 | P05 | right | 62/64/64/64/64/64/46 | 64 | 0.0 | 1.1379426717758179 | 406.0 | 0.0 | {"complete": 64} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "L1_S31−L0_S31": {
      "nominal": {
        "left": {
          "D": 15,
          "S3+": 3,
          "S4+": 3,
          "open_hold": 4,
          "S5+": 4,
          "complete": 4,
          "clean_complete": 6
        },
        "right": {
          "D": 4,
          "S3+": 8,
          "S4+": 8,
          "open_hold": 8,
          "S5+": 8,
          "complete": 8,
          "clean_complete": -1
        }
      },
      "P02": {
        "left": {
          "D": 23,
          "S3+": 2,
          "S4+": 3,
          "open_hold": 1,
          "S5+": 3,
          "complete": 3,
          "clean_complete": 3
        },
        "right": {
          "D": -2,
          "S3+": 5,
          "S4+": 5,
          "open_hold": 5,
          "S5+": 5,
          "complete": 5,
          "clean_complete": -4
        }
      },
      "P05": {
        "left": {
          "D": 23,
          "S3+": 2,
          "S4+": 2,
          "open_hold": 4,
          "S5+": 3,
          "complete": 3,
          "clean_complete": 2
        },
        "right": {
          "D": -8,
          "S3+": 5,
          "S4+": 5,
          "open_hold": 5,
          "S5+": 5,
          "complete": 5,
          "clean_complete": -7
        }
      }
    },
    "L1_S32−L0_S31": {
      "nominal": {
        "left": {
          "D": 16,
          "S3+": 4,
          "S4+": 4,
          "open_hold": 5,
          "S5+": 5,
          "complete": 4,
          "clean_complete": 39
        },
        "right": {
          "D": 22,
          "S3+": 8,
          "S4+": 8,
          "open_hold": 8,
          "S5+": 8,
          "complete": 8,
          "clean_complete": 9
        }
      },
      "P02": {
        "left": {
          "D": 24,
          "S3+": 5,
          "S4+": 6,
          "open_hold": 6,
          "S5+": 6,
          "complete": 6,
          "clean_complete": 46
        },
        "right": {
          "D": 21,
          "S3+": 5,
          "S4+": 5,
          "open_hold": 5,
          "S5+": 5,
          "complete": 5,
          "clean_complete": 6
        }
      },
      "P05": {
        "left": {
          "D": 22,
          "S3+": 5,
          "S4+": 5,
          "open_hold": 7,
          "S5+": 6,
          "complete": 6,
          "clean_complete": 49
        },
        "right": {
          "D": 13,
          "S3+": 5,
          "S4+": 5,
          "open_hold": 5,
          "S5+": 5,
          "complete": 5,
          "clean_complete": 5
        }
      }
    }
  },
  "negative_deltas": [
    {
      "reference": "L1_S31−L0_S31",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -1
      }
    },
    {
      "reference": "L1_S31−L0_S31",
      "stratum": "P02",
      "side": "right",
      "negative_deltas": {
        "D": -2,
        "clean_complete": -4
      }
    },
    {
      "reference": "L1_S31−L0_S31",
      "stratum": "P05",
      "side": "right",
      "negative_deltas": {
        "D": -8,
        "clean_complete": -7
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -20,
        "S3+": -3,
        "S4+": -3,
        "open_hold": -4,
        "S5+": -4,
        "complete": -4
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -6,
        "S3+": -5,
        "S4+": -5,
        "open_hold": -5,
        "S5+": -5,
        "complete": -5
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "P02",
      "side": "left",
      "negative_deltas": {
        "D": -23,
        "S3+": -2,
        "S4+": -3,
        "open_hold": -2,
        "S5+": -3,
        "complete": -3
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "P02",
      "side": "right",
      "negative_deltas": {
        "D": -5,
        "S3+": -4,
        "S4+": -4,
        "open_hold": -4,
        "S5+": -4,
        "complete": -4
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "P05",
      "side": "left",
      "negative_deltas": {
        "D": -23,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -4,
        "S5+": -2,
        "complete": -2
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "P05",
      "side": "right",
      "negative_deltas": {
        "S3+": -4,
        "S4+": -4,
        "open_hold": -4,
        "S5+": -4,
        "complete": -4
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -13
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "P02",
      "side": "left",
      "negative_deltas": {
        "open_hold": -1
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "P02",
      "side": "right",
      "negative_deltas": {
        "D": -13
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "P05",
      "side": "right",
      "negative_deltas": {
        "D": -14
      }
    },
    {
      "reference": "L1_S32−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "complete": -1
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
    "L0_S31/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 26,
      "complete_with_body_contact_above_5N": 15,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 17,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P02/left": {
      "complete_with_crossing_hinge_below_threshold": 28,
      "complete_with_body_contact_above_5N": 24,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P02/right": {
      "complete_with_crossing_hinge_below_threshold": 18,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P05/left": {
      "complete_with_crossing_hinge_below_threshold": 30,
      "complete_with_body_contact_above_5N": 35,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P05/right": {
      "complete_with_crossing_hinge_below_threshold": 18,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 19,
      "complete_with_body_contact_above_5N": 22,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 26,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P02/left": {
      "complete_with_crossing_hinge_below_threshold": 24,
      "complete_with_body_contact_above_5N": 23,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P02/right": {
      "complete_with_crossing_hinge_below_threshold": 27,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P05/left": {
      "complete_with_crossing_hinge_below_threshold": 32,
      "complete_with_body_contact_above_5N": 32,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P05/right": {
      "complete_with_crossing_hinge_below_threshold": 30,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 1,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 16,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P02/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 2,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P02/right": {
      "complete_with_crossing_hinge_below_threshold": 17,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P05/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 6,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P05/right": {
      "complete_with_crossing_hinge_below_threshold": 18,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    }
  },
  "k": {},
  "training": {
    "L0_S31": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31/runtime.log",
      "iteration": null,
      "metrics": {},
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "L1_S31": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1/runtime.log",
      "iteration": 2000,
      "metrics": {
        "a2_v27_friction_initialized_env_count": 4096.0,
        "a2_v27_friction_static_readback_min": 0.0,
        "a2_v27_friction_static_readback_max": 5.0,
        "a2_v27_friction_dynamic_readback_min": 0.0,
        "a2_v27_friction_dynamic_readback_max": 3.75,
        "a2_v27_friction_viscous_readback_min": 0.0,
        "a2_v27_friction_viscous_readback_max": 0.0,
        "a2_v27_friction_static_0_env_count": 1373.5156,
        "a2_v27_friction_static_2_env_count": 1344.2969,
        "a2_v27_friction_static_5_env_count": 1378.1875
      },
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "L1_S32": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1/runtime.log",
      "iteration": 2000,
      "metrics": {
        "a2_v27_friction_initialized_env_count": 4096.0,
        "a2_v27_friction_static_readback_min": 0.0,
        "a2_v27_friction_static_readback_max": 5.0,
        "a2_v27_friction_dynamic_readback_min": 0.0,
        "a2_v27_friction_dynamic_readback_max": 3.75,
        "a2_v27_friction_viscous_readback_min": 0.0,
        "a2_v27_friction_viscous_readback_max": 0.0,
        "a2_v27_friction_static_0_env_count": 1383.75,
        "a2_v27_friction_static_2_env_count": 1342.0,
        "a2_v27_friction_static_5_env_count": 1370.25
      },
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
    "2, 13354 MiB, 49140 MiB, 47 %",
    "3, 12946 MiB, 49140 MiB, 17 %",
    "4, 13828 MiB, 49140 MiB, 35 %",
    "5, 1 MiB, 49140 MiB, 0 %",
    "6, 1 MiB, 49140 MiB, 0 %",
    "7, 1 MiB, 49140 MiB, 0 %"
  ],
  "processes": [
    "2254446 2692622    14:51:11 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l0_s31/run.sh",
    "2254448 2254446    14:51:11 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell L0_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31",
    "2254466 2254448    14:51:09 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L0_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31/output project_name=base_v27_bilateral_hardening experiment_name=V27_L0_S31",
    "2258700 2692622    14:50:13 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_b/run.sh",
    "2258703 2258700    14:50:13 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave B",
    "2272779 2692622    14:38:55 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s31_r1/run.sh",
    "2272782 2272779    14:38:55 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell L1_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1",
    "2272794 2272782    14:38:54 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S31",
    "2272812 2692622    14:38:53 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s32_r1/run.sh",
    "2272814 2272812    14:38:53 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell L1_S32 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1",
    "2272829 2272814    14:38:52 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S32 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S32",
    "2782448 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_l/step2000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_l/step2000.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_b_l_step2000_readout_20260907.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_l/step1000/reducer.json"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_l/step2000/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_l/step2000.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

所有P02/P05评估terminal native readback仍逐env匹配(2,1.5,0)/(5,3.75,0)；nominal按合同关闭backend。L1_S32 LEFT三层通过当前单侧64样本门，但RIGHT与另一seed尚未通过，不能在step2000提前结算DOMAIN_CONVERGED。
