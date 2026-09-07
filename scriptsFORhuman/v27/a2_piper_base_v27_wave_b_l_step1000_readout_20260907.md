# base_v27 wave_b_l/step1000 readout

2026-09-07 01:23 HKT

状态：`V27_COMPLETE`；step=1000；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| L0_S31 | nominal | left | 62/63/63/63/63/63/12 | 6 | 716.439697265625 | 1.0933659076690674 | 442.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| L0_S31 | nominal | right | 46/61/61/61/61/61/32 | 61 | 0.0 | 1.0743330717086792 | 464.0 | 0.0 | {"stage_overtime": 3, "complete": 61} | 0 |
| L0_S31 | P02 | left | 60/61/61/60/61/61/5 | 8 | 634.8712768554688 | 1.068793535232544 | 449.0 | 0.0 | {"stage_overtime": 3, "complete": 61} | 0 |
| L0_S31 | P02 | right | 48/63/63/63/63/63/32 | 63 | 0.0 | 1.0537909269332886 | 474.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| L0_S31 | P05 | left | 60/61/61/61/60/60/0 | 3 | 570.2683715820312 | 1.0534236431121826 | 455.0 | 0.0 | {"upper_dof_overspeed": 1, "stage_overtime": 3, "complete": 60} | 0 |
| L0_S31 | P05 | right | 48/63/63/63/63/63/34 | 63 | 0.0 | 1.0605217218399048 | 482.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S31 | nominal | left | 40/60/60/60/38/0/0 | 22 | 0.0 | 1.1487822532653809 | 238.0 | 0.0 | {"upper_dof_overspeed": 62, "stage_overtime": 2} | 0 |
| L1_S31 | nominal | right | 57/59/58/58/38/0/0 | 58 | 0.0 | 1.0668963193893433 | 264.0 | 0.0 | {"upper_dof_overspeed": 60, "stage_overtime": 4} | 0 |
| L1_S31 | P02 | left | 46/60/60/60/29/0/0 | 11 | 0.0 | 1.141287088394165 | 245.0 | 0.0 | {"upper_dof_overspeed": 61, "stage_overtime": 3} | 0 |
| L1_S31 | P02 | right | 54/61/61/61/41/0/0 | 61 | 0.0 | 1.0815672874450684 | 264.0 | 0.0 | {"upper_dof_overspeed": 61, "stage_overtime": 3} | 0 |
| L1_S31 | P05 | left | 45/60/60/60/19/0/0 | 6 | 0.0 | 1.1104117631912231 | 247.0 | 0.0 | {"upper_dof_overspeed": 61, "stage_overtime": 3} | 0 |
| L1_S31 | P05 | right | 55/60/60/60/35/0/0 | 59 | 0.0 | 1.0802491903305054 | 270.0 | 0.0 | {"upper_dof_overspeed": 60, "stage_overtime": 4} | 0 |
| L1_S32 | nominal | left | 58/64/64/64/64/64/54 | 55 | 258.3077087402344 | 1.4728578329086304 | 461.0 | 0.17167194128341526 | {"complete": 64} | 0 |
| L1_S32 | nominal | right | 61/62/62/62/62/62/40 | 62 | 0.0 | 1.0979290008544922 | 443.0 | 0.0 | {"stage_overtime": 2, "complete": 62} | 0 |
| L1_S32 | P02 | left | 56/61/61/61/61/61/55 | 57 | 53.26741409301758 | 1.4753053188323975 | 462.0 | 0.17117479470420646 | {"stage_overtime": 3, "complete": 61} | 0 |
| L1_S32 | P02 | right | 57/59/59/59/57/57/32 | 59 | 0.0 | 1.079350471496582 | 447.0 | 0.0 | {"upper_dof_overspeed": 2, "stage_overtime": 5, "complete": 57} | 0 |
| L1_S32 | P05 | left | 58/62/61/61/61/60/52 | 58 | 158.7259521484375 | 1.4437793493270874 | 467.0 | 0.1720275511568811 | {"upper_dof_overspeed": 2, "stage_overtime": 2, "complete": 60} | 0 |
| L1_S32 | P05 | right | 57/59/59/59/59/59/32 | 59 | 0.0 | 1.0656639337539673 | 451.0 | 0.0 | {"stage_overtime": 5, "complete": 59} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "L1_S31−L0_S31": {
      "nominal": {
        "left": {
          "D": -22,
          "S3+": -3,
          "S4+": -3,
          "open_hold": -3,
          "S5+": -25,
          "complete": -63,
          "clean_complete": -12
        },
        "right": {
          "D": 11,
          "S3+": -2,
          "S4+": -3,
          "open_hold": -3,
          "S5+": -23,
          "complete": -61,
          "clean_complete": -32
        }
      },
      "P02": {
        "left": {
          "D": -14,
          "S3+": -1,
          "S4+": -1,
          "open_hold": 0,
          "S5+": -32,
          "complete": -61,
          "clean_complete": -5
        },
        "right": {
          "D": 6,
          "S3+": -2,
          "S4+": -2,
          "open_hold": -2,
          "S5+": -22,
          "complete": -63,
          "clean_complete": -32
        }
      },
      "P05": {
        "left": {
          "D": -15,
          "S3+": -1,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -41,
          "complete": -60,
          "clean_complete": 0
        },
        "right": {
          "D": 7,
          "S3+": -3,
          "S4+": -3,
          "open_hold": -3,
          "S5+": -28,
          "complete": -63,
          "clean_complete": -34
        }
      }
    },
    "L1_S32−L0_S31": {
      "nominal": {
        "left": {
          "D": -4,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 1,
          "complete": 1,
          "clean_complete": 42
        },
        "right": {
          "D": 15,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 1,
          "complete": 1,
          "clean_complete": 8
        }
      },
      "P02": {
        "left": {
          "D": -4,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 1,
          "S5+": 0,
          "complete": 0,
          "clean_complete": 50
        },
        "right": {
          "D": 9,
          "S3+": -4,
          "S4+": -4,
          "open_hold": -4,
          "S5+": -6,
          "complete": -6,
          "clean_complete": 0
        }
      },
      "P05": {
        "left": {
          "D": -2,
          "S3+": 1,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 1,
          "complete": 0,
          "clean_complete": 52
        },
        "right": {
          "D": 9,
          "S3+": -4,
          "S4+": -4,
          "open_hold": -4,
          "S5+": -4,
          "complete": -4,
          "clean_complete": -2
        }
      }
    }
  },
  "negative_deltas": [
    {
      "reference": "L1_S31−L0_S31",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -22,
        "S3+": -3,
        "S4+": -3,
        "open_hold": -3,
        "S5+": -25,
        "complete": -63,
        "clean_complete": -12
      }
    },
    {
      "reference": "L1_S31−L0_S31",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S3+": -2,
        "S4+": -3,
        "open_hold": -3,
        "S5+": -23,
        "complete": -61,
        "clean_complete": -32
      }
    },
    {
      "reference": "L1_S31−L0_S31",
      "stratum": "P02",
      "side": "left",
      "negative_deltas": {
        "D": -14,
        "S3+": -1,
        "S4+": -1,
        "S5+": -32,
        "complete": -61,
        "clean_complete": -5
      }
    },
    {
      "reference": "L1_S31−L0_S31",
      "stratum": "P02",
      "side": "right",
      "negative_deltas": {
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -22,
        "complete": -63,
        "clean_complete": -32
      }
    },
    {
      "reference": "L1_S31−L0_S31",
      "stratum": "P05",
      "side": "left",
      "negative_deltas": {
        "D": -15,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -41,
        "complete": -60
      }
    },
    {
      "reference": "L1_S31−L0_S31",
      "stratum": "P05",
      "side": "right",
      "negative_deltas": {
        "S3+": -3,
        "S4+": -3,
        "open_hold": -3,
        "S5+": -28,
        "complete": -63,
        "clean_complete": -34
      }
    },
    {
      "reference": "L1_S32−L0_S31",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -4
      }
    },
    {
      "reference": "L1_S32−L0_S31",
      "stratum": "P02",
      "side": "left",
      "negative_deltas": {
        "D": -4
      }
    },
    {
      "reference": "L1_S32−L0_S31",
      "stratum": "P02",
      "side": "right",
      "negative_deltas": {
        "S3+": -4,
        "S4+": -4,
        "open_hold": -4,
        "S5+": -6,
        "complete": -6
      }
    },
    {
      "reference": "L1_S32−L0_S31",
      "stratum": "P05",
      "side": "left",
      "negative_deltas": {
        "D": -2
      }
    },
    {
      "reference": "L1_S32−L0_S31",
      "stratum": "P05",
      "side": "right",
      "negative_deltas": {
        "S3+": -4,
        "S4+": -4,
        "open_hold": -4,
        "S5+": -4,
        "complete": -4,
        "clean_complete": -2
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
      "complete_with_crossing_hinge_below_threshold": 16,
      "complete_with_body_contact_above_5N": 49,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 29,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P02/left": {
      "complete_with_crossing_hinge_below_threshold": 25,
      "complete_with_body_contact_above_5N": 52,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P02/right": {
      "complete_with_crossing_hinge_below_threshold": 31,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P05/left": {
      "complete_with_crossing_hinge_below_threshold": 29,
      "complete_with_body_contact_above_5N": 59,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P05/right": {
      "complete_with_crossing_hinge_below_threshold": 28,
      "complete_with_body_contact_above_5N": 1,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P02/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P02/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P05/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P05/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 10,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 22,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P02/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 6,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P02/right": {
      "complete_with_crossing_hinge_below_threshold": 25,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P05/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 8,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P05/right": {
      "complete_with_crossing_hinge_below_threshold": 27,
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
      "iteration": 1000,
      "metrics": {
        "a2_v27_friction_initialized_env_count": 4096.0,
        "a2_v27_friction_static_readback_min": 0.0,
        "a2_v27_friction_static_readback_max": 5.0,
        "a2_v27_friction_dynamic_readback_min": 0.0,
        "a2_v27_friction_dynamic_readback_max": 3.75,
        "a2_v27_friction_viscous_readback_min": 0.0,
        "a2_v27_friction_viscous_readback_max": 0.0,
        "a2_v27_friction_static_0_env_count": 1311.8594,
        "a2_v27_friction_static_2_env_count": 1408.9062,
        "a2_v27_friction_static_5_env_count": 1375.2344
      },
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "L1_S32": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1/runtime.log",
      "iteration": 1000,
      "metrics": {
        "a2_v27_friction_initialized_env_count": 4096.0,
        "a2_v27_friction_static_readback_min": 0.0,
        "a2_v27_friction_static_readback_max": 5.0,
        "a2_v27_friction_dynamic_readback_min": 0.0,
        "a2_v27_friction_dynamic_readback_max": 3.75,
        "a2_v27_friction_viscous_readback_min": 0.0,
        "a2_v27_friction_viscous_readback_max": 0.0,
        "a2_v27_friction_static_0_env_count": 1395.3125,
        "a2_v27_friction_static_2_env_count": 1334.875,
        "a2_v27_friction_static_5_env_count": 1365.8125
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
    "2, 20458 MiB, 49140 MiB, 94 %",
    "3, 20970 MiB, 49140 MiB, 96 %",
    "4, 21866 MiB, 49140 MiB, 95 %",
    "5, 13518 MiB, 49140 MiB, 17 %",
    "6, 1 MiB, 49140 MiB, 0 %",
    "7, 13002 MiB, 49140 MiB, 96 %"
  ],
  "processes": [
    "2254446 2692622    08:00:31 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l0_s31/run.sh",
    "2254448 2254446    08:00:31 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell L0_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31",
    "2254466 2254448    08:00:30 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L0_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L0_S31/output project_name=base_v27_bilateral_hardening experiment_name=V27_L0_S31",
    "2254546 2692622    08:00:26 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r0_s41/run.sh",
    "2254548 2254546    08:00:26 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 5 --cell R0_S41 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41",
    "2254584 2254548    08:00:25 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_R0_S41 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R0_S41/output project_name=base_v27_bilateral_hardening experiment_name=V27_R0_S41",
    "2254696 2692622    08:00:23 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_r2_s41/run.sh",
    "2254698 2254696    08:00:23 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 7 --cell R2_S41 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41",
    "2254791 2254698    08:00:22 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_R2_S41 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/R2_S41/output project_name=base_v27_bilateral_hardening experiment_name=V27_R2_S41",
    "2258700 2692622    07:59:33 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_b/run.sh",
    "2258703 2258700    07:59:33 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave B",
    "2272779 2692622    07:48:15 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s31_r1/run.sh",
    "2272782 2272779    07:48:15 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell L1_S31 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1",
    "2272794 2272782    07:48:14 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S31 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S31_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S31",
    "2272812 2692622    07:48:14 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_l1_s32_r1/run.sh",
    "2272814 2272812    07:48:14 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell L1_S32 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1",
    "2272829 2272814    07:48:12 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_L1_S32 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1/output project_name=base_v27_bilateral_hardening experiment_name=V27_L1_S32",
    "2563341 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_l/step1000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_l/step1000.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_b_l_step1000_readout_20260907.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_l/step1000/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_l/step1000.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## CARRIER_A历史比较与native readback

nominal参考C_S21 endpoint每侧64/seed270001；P02/P05参考probe每侧32/seed270201。以下为百分点差，probe比较不是同episode配对。

| Cell/层/侧 | D Δpp | S3+ Δpp | S4+ Δpp | open_hold Δpp | S5+ Δpp | complete Δpp | clean Δpp |
|---|---:|---:|---:|---:|---:|---:|---:|
| L0_S31/nominal/left | +12.50 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | -60.94 |
| L0_S31/nominal/right | -6.25 | -4.69 | -4.69 | -4.69 | -4.69 | -4.69 | -14.06 |
| L0_S31/P02/left | +9.38 | -4.69 | -4.69 | -6.25 | -4.69 | -4.69 | -64.06 |
| L0_S31/P02/right | -6.25 | +1.56 | +1.56 | +1.56 | +1.56 | +1.56 | -6.25 |
| L0_S31/P05/left | +9.38 | -4.69 | -4.69 | -4.69 | -6.25 | -6.25 | -56.25 |
| L0_S31/P05/right | -6.25 | +1.56 | +1.56 | +1.56 | +1.56 | +1.56 | -3.12 |
| L1_S31/nominal/left | -21.88 | -6.25 | -6.25 | -6.25 | -40.62 | -100.00 | -79.69 |
| L1_S31/nominal/right | +10.94 | -7.81 | -9.38 | -9.38 | -40.62 | -100.00 | -64.06 |
| L1_S31/P02/left | -12.50 | -6.25 | -6.25 | -6.25 | -54.69 | -100.00 | -71.88 |
| L1_S31/P02/right | +3.12 | -1.56 | -1.56 | -1.56 | -32.81 | -96.88 | -56.25 |
| L1_S31/P05/left | -14.06 | -6.25 | -6.25 | -6.25 | -70.31 | -100.00 | -56.25 |
| L1_S31/P05/right | +4.69 | -3.12 | -3.12 | -3.12 | -42.19 | -96.88 | -56.25 |
| L1_S32/nominal/left | +6.25 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +4.69 |
| L1_S32/nominal/right | +17.19 | -3.12 | -3.12 | -3.12 | -3.12 | -3.12 | -1.56 |
| L1_S32/P02/left | +3.12 | -4.69 | -4.69 | -4.69 | -4.69 | -4.69 | +14.06 |
| L1_S32/P02/right | +7.81 | -4.69 | -4.69 | -4.69 | -7.81 | -7.81 | -6.25 |
| L1_S32/P05/left | +6.25 | -3.12 | -4.69 | -4.69 | -4.69 | -6.25 | +25.00 |
| L1_S32/P05/right | +7.81 | -4.69 | -4.69 | -4.69 | -4.69 | -4.69 | -6.25 |

所有P02/P05 terminal rows的native readback分别精确为(2,1.5,0)/(5,3.75,0)。nominal按合同关闭backend。
