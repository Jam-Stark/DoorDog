# base_v27 wave_b_l/step3000 readout

2026-09-07 15:21 HKT

状态：`V27_COMPLETE`；step=3000；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| L0_S31 | nominal | left | 21/59/59/59/59/59/0 | 47 | None | 0.8844587206840515 | 391.0 | 0.0 | {"stage_overtime": 5, "complete": 59} | 0 |
| L0_S31 | nominal | right | 44/56/56/56/56/56/40 | 56 | 0.0 | 1.117089033126831 | 390.0 | 0.07731072271327441 | {"stage_overtime": 8, "complete": 56} | 0 |
| L0_S31 | P02 | left | 21/59/59/59/59/59/0 | 49 | None | 0.8465180993080139 | 397.0 | 0.0 | {"stage_overtime": 5, "complete": 59} | 0 |
| L0_S31 | P02 | right | 47/56/56/56/56/56/38 | 56 | 0.0 | 1.1136618852615356 | 397.0 | 0.07731490621915103 | {"stage_overtime": 8, "complete": 56} | 0 |
| L0_S31 | P05 | left | 21/59/59/59/59/59/0 | 49 | None | 0.8305384516716003 | 400.0 | 0.0 | {"stage_overtime": 5, "complete": 59} | 0 |
| L0_S31 | P05 | right | 46/56/56/56/56/56/36 | 56 | 0.0 | 1.1203550100326538 | 402.0 | 0.07697427665322423 | {"stage_overtime": 8, "complete": 56} | 0 |
| L1_S31 | nominal | left | 62/63/63/63/63/63/17 | 5 | 476.1720275878906 | 1.014570713043213 | 392.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S31 | nominal | right | 51/64/64/64/64/60/43 | 64 | 0.0 | 1.1376157999038696 | 393.0 | 0.0 | {"upper_dof_overspeed": 4, "complete": 60} | 0 |
| L1_S31 | P02 | left | 59/63/63/63/59/59/11 | 0 | None | 0.9677457213401794 | 397.0 | 0.0 | {"upper_dof_overspeed": 4, "stage_overtime": 1, "complete": 59} | 0 |
| L1_S31 | P02 | right | 48/64/64/64/64/57/41 | 64 | 0.0 | 1.1275293827056885 | 394.0 | 0.0 | {"upper_dof_overspeed": 7, "complete": 57} | 0 |
| L1_S31 | P05 | left | 59/63/63/63/62/62/8 | 0 | None | 0.9327198266983032 | 405.0 | 0.0 | {"upper_dof_overspeed": 1, "stage_overtime": 1, "complete": 62} | 0 |
| L1_S31 | P05 | right | 53/64/64/64/64/61/44 | 64 | 0.0 | 1.1400028467178345 | 396.0 | 0.0 | {"upper_dof_overspeed": 3, "complete": 61} | 0 |
| L1_S32 | nominal | left | 62/63/63/63/63/63/63 | 0 | 0.0 | 1.469866156578064 | 395.0 | 0.29919566775503703 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S32 | nominal | right | 49/62/62/62/62/62/52 | 61 | 0.0 | 1.2006617784500122 | 385.0 | 0.0 | {"complete": 62, "stage_overtime": 2} | 0 |
| L1_S32 | P02 | left | 61/63/63/63/63/63/63 | 1 | 0.0 | 1.4117454290390015 | 402.0 | 0.3052876097484153 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S32 | P02 | right | 49/62/62/62/62/62/53 | 62 | 0.0 | 1.1847288608551025 | 389.0 | 0.0 | {"stage_overtime": 2, "complete": 62} | 0 |
| L1_S32 | P05 | left | 61/63/63/63/63/63/63 | 2 | 0.0 | 1.3706048727035522 | 404.0 | 0.3168135381735943 | {"stage_overtime": 1, "complete": 63} | 0 |
| L1_S32 | P05 | right | 50/62/62/62/62/62/52 | 62 | 0.0 | 1.1766459941864014 | 393.0 | 0.0 | {"stage_overtime": 2, "complete": 62} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "L1_S31−L0_S31": {
      "nominal": {
        "left": {
          "D": 41,
          "S3+": 4,
          "S4+": 4,
          "open_hold": 4,
          "S5+": 4,
          "complete": 4,
          "clean_complete": 17
        },
        "right": {
          "D": 7,
          "S3+": 8,
          "S4+": 8,
          "open_hold": 8,
          "S5+": 8,
          "complete": 4,
          "clean_complete": 3
        }
      },
      "P02": {
        "left": {
          "D": 38,
          "S3+": 4,
          "S4+": 4,
          "open_hold": 4,
          "S5+": 0,
          "complete": 0,
          "clean_complete": 11
        },
        "right": {
          "D": 1,
          "S3+": 8,
          "S4+": 8,
          "open_hold": 8,
          "S5+": 8,
          "complete": 1,
          "clean_complete": 3
        }
      },
      "P05": {
        "left": {
          "D": 38,
          "S3+": 4,
          "S4+": 4,
          "open_hold": 4,
          "S5+": 3,
          "complete": 3,
          "clean_complete": 8
        },
        "right": {
          "D": 7,
          "S3+": 8,
          "S4+": 8,
          "open_hold": 8,
          "S5+": 8,
          "complete": 5,
          "clean_complete": 8
        }
      }
    },
    "L1_S32−L0_S31": {
      "nominal": {
        "left": {
          "D": 41,
          "S3+": 4,
          "S4+": 4,
          "open_hold": 4,
          "S5+": 4,
          "complete": 4,
          "clean_complete": 63
        },
        "right": {
          "D": 5,
          "S3+": 6,
          "S4+": 6,
          "open_hold": 6,
          "S5+": 6,
          "complete": 6,
          "clean_complete": 12
        }
      },
      "P02": {
        "left": {
          "D": 40,
          "S3+": 4,
          "S4+": 4,
          "open_hold": 4,
          "S5+": 4,
          "complete": 4,
          "clean_complete": 63
        },
        "right": {
          "D": 2,
          "S3+": 6,
          "S4+": 6,
          "open_hold": 6,
          "S5+": 6,
          "complete": 6,
          "clean_complete": 15
        }
      },
      "P05": {
        "left": {
          "D": 40,
          "S3+": 4,
          "S4+": 4,
          "open_hold": 4,
          "S5+": 4,
          "complete": 4,
          "clean_complete": 63
        },
        "right": {
          "D": 4,
          "S3+": 6,
          "S4+": 6,
          "open_hold": 6,
          "S5+": 6,
          "complete": 6,
          "clean_complete": 16
        }
      }
    }
  },
  "negative_deltas": [
    {
      "reference": "L0_S31−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -21,
        "S3+": -1,
        "S4+": -1,
        "clean_complete": -23
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "P02",
      "side": "left",
      "negative_deltas": {
        "D": -16,
        "clean_complete": -16
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "P02",
      "side": "right",
      "negative_deltas": {
        "S3+": -3,
        "S4+": -3,
        "open_hold": -3,
        "S5+": -3,
        "complete": -3,
        "clean_complete": -3
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "P05",
      "side": "left",
      "negative_deltas": {
        "D": -16,
        "clean_complete": -9
      }
    },
    {
      "reference": "L0_S31−previous",
      "stratum": "P05",
      "side": "right",
      "negative_deltas": {
        "D": -3,
        "S3+": -3,
        "S4+": -3,
        "open_hold": -3,
        "S5+": -3,
        "complete": -3,
        "clean_complete": -5
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -12
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "complete": -4
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "P02",
      "side": "left",
      "negative_deltas": {
        "D": -1,
        "S5+": -2,
        "complete": -2,
        "clean_complete": -8
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "P02",
      "side": "right",
      "negative_deltas": {
        "complete": -7
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "P05",
      "side": "left",
      "negative_deltas": {
        "D": -1,
        "clean_complete": -3
      }
    },
    {
      "reference": "L1_S31−previous",
      "stratum": "P05",
      "side": "right",
      "negative_deltas": {
        "complete": -3
      }
    },
    {
      "reference": "L1_S32−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1
      }
    },
    {
      "reference": "L1_S32−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -13,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2,
        "complete": -2
      }
    },
    {
      "reference": "L1_S32−previous",
      "stratum": "P02",
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
      "reference": "L1_S32−previous",
      "stratum": "P02",
      "side": "right",
      "negative_deltas": {
        "D": -15,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2,
        "complete": -2
      }
    },
    {
      "reference": "L1_S32−previous",
      "stratum": "P05",
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
      "reference": "L1_S32−previous",
      "stratum": "P05",
      "side": "right",
      "negative_deltas": {
        "D": -12,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2,
        "complete": -2
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
    "outcome": "DOMAIN_NOT_CONVERGED",
    "recipe_b": "CURRENT_DOMAIN"
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
    "L0_S31/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 58,
      "complete_with_body_contact_above_5N": 25,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 16,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P02/left": {
      "complete_with_crossing_hinge_below_threshold": 57,
      "complete_with_body_contact_above_5N": 35,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P02/right": {
      "complete_with_crossing_hinge_below_threshold": 18,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P05/left": {
      "complete_with_crossing_hinge_below_threshold": 59,
      "complete_with_body_contact_above_5N": 39,
      "complete_without_crossing_measurement": 0
    },
    "L0_S31/P05/right": {
      "complete_with_crossing_hinge_below_threshold": 20,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 35,
      "complete_with_body_contact_above_5N": 19,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 17,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P02/left": {
      "complete_with_crossing_hinge_below_threshold": 40,
      "complete_with_body_contact_above_5N": 21,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P02/right": {
      "complete_with_crossing_hinge_below_threshold": 16,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P05/left": {
      "complete_with_crossing_hinge_below_threshold": 48,
      "complete_with_body_contact_above_5N": 32,
      "complete_without_crossing_measurement": 0
    },
    "L1_S31/P05/right": {
      "complete_with_crossing_hinge_below_threshold": 17,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 10,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P02/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P02/right": {
      "complete_with_crossing_hinge_below_threshold": 9,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P05/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "L1_S32/P05/right": {
      "complete_with_crossing_hinge_below_threshold": 10,
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
      "iteration": 3000,
      "metrics": {
        "a2_v27_friction_initialized_env_count": 4096.0,
        "a2_v27_friction_static_readback_min": 0.0,
        "a2_v27_friction_static_readback_max": 5.0,
        "a2_v27_friction_dynamic_readback_min": 0.0,
        "a2_v27_friction_dynamic_readback_max": 3.75,
        "a2_v27_friction_viscous_readback_min": 0.0,
        "a2_v27_friction_viscous_readback_max": 0.0,
        "a2_v27_friction_static_0_env_count": 1371.0156,
        "a2_v27_friction_static_2_env_count": 1351.5469,
        "a2_v27_friction_static_5_env_count": 1373.4375
      },
      "aggregation": "Trainer means across the PPO batch; cumulative counters are batch-averaged snapshots, not exact end-of-batch totals."
    },
    "L1_S32": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/L1_S32_r1/runtime.log",
      "iteration": 3000,
      "metrics": {
        "a2_v27_friction_initialized_env_count": 4096.0,
        "a2_v27_friction_static_readback_min": 0.0,
        "a2_v27_friction_static_readback_max": 5.0,
        "a2_v27_friction_dynamic_readback_min": 0.0,
        "a2_v27_friction_dynamic_readback_max": 3.75,
        "a2_v27_friction_viscous_readback_min": 0.0,
        "a2_v27_friction_viscous_readback_max": 0.0,
        "a2_v27_friction_static_0_env_count": 1360.3281,
        "a2_v27_friction_static_2_env_count": 1410.2031,
        "a2_v27_friction_static_5_env_count": 1325.4688
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
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_b/RUN_RECEIPT.json"
    }
  },
  "gpu": [
    "0, 41232 MiB, 49140 MiB, 62 %",
    "1, 41232 MiB, 49140 MiB, 46 %",
    "2, 41232 MiB, 49140 MiB, 49 %",
    "3, 41232 MiB, 49140 MiB, 52 %",
    "4, 4 MiB, 49140 MiB, 0 %",
    "5, 4 MiB, 49140 MiB, 0 %",
    "6, 4 MiB, 49140 MiB, 0 %",
    "7, 4 MiB, 49140 MiB, 0 %"
  ],
  "processes": [
    "3023794 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_l/step3000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_l/step3000.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_b_l_step3000_readout_20260907.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_l/step2000/reducer.json"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_b_l/step3000/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_b_l/step3000.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## Wave B冻结结论

`DOMAIN_NOT_CONVERGED`，`RECIPE_B=current`（mass80–120、friction off）；Q_R为`UNRESOLVED`（R1 endpoint缺失）。L1_S32 LEFT三层clean均63/64，但RIGHT52/53/52、另一seedLEFT17/11/8，未满足两seed三层双侧质量门。没有选择中途checkpoint。

所有P02/P05 terminal native readback逐env精确匹配(2,1.5,0)/(5,3.75,0)。L三格各3000均PASS/0，endpoint18 lanes exact64/integrity0；B调度器已正常完成。Wave C按C质量overlay+当前域从零运行，恢复pilot不进入其配方。
