# base_v27 wave_a/step3000 readout

2026-09-06 16:31 HKT

状态：`V27_COMPLETE`；step=3000；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| C_S21 | nominal | left | 54/64/64/64/64/64/51 | 4 | 0.0 | 1.1579347848892212 | 396.0 | 0.0 | {"complete": 64} | 0 |
| C_S21 | nominal | right | 50/64/64/64/64/64/41 | 64 | 0.0 | 1.091548204421997 | 419.0 | 0.0 | {"complete": 64} | 0 |
| Q1_S21 | nominal | left | 49/64/64/64/63/63/5 | 0 | 495.334716796875 | 0.9510986804962158 | 406.0 | 0.0 | {"complete": 63, "stage_overtime": 1} | 0 |
| Q1_S21 | nominal | right | 64/64/64/64/64/64/40 | 64 | 0.0 | 1.0973234176635742 | 417.0 | 0.0 | {"complete": 64} | 0 |
| Q2_S21 | nominal | left | 55/64/64/64/64/64/18 | 11 | None | 1.0674372911453247 | 419.0 | 0.02500092186290055 | {"complete": 64} | 0 |
| Q2_S21 | nominal | right | 26/64/64/63/64/64/21 | 0 | None | 1.0097934007644653 | 411.0 | 0.0 | {"complete": 64} | 0 |
| C_S22 | nominal | left | 56/61/61/61/61/61/0 | 1 | None | 0.8021953701972961 | 403.0 | 0.0 | {"stage_overtime": 3, "complete": 61} | 0 |
| C_S22 | nominal | right | 52/62/62/62/62/62/39 | 62 | 0.0 | 1.1101980209350586 | 430.0 | 0.0 | {"stage_overtime": 2, "complete": 62} | 0 |
| Q1_S22 | nominal | left | 54/64/64/64/64/64/17 | 60 | 0.0 | 0.9597512483596802 | 437.0 | 0.0 | {"complete": 64} | 0 |
| Q1_S22 | nominal | right | 53/63/63/63/63/62/20 | 45 | 0.0 | 0.9921661615371704 | 468.0 | 0.1655883137673426 | {"upper_dof_overspeed": 1, "stage_overtime": 1, "complete": 62} | 0 |
| Q2_S22 | nominal | left | 34/64/63/62/63/63/16 | 0 | 39.362632751464844 | 1.0607613325119019 | 416.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| Q2_S22 | nominal | right | 48/63/63/63/63/63/39 | 63 | 0.0 | 1.0944479703903198 | 420.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "Q1_S21−C_S21": {
      "nominal": {
        "left": {
          "D": -5,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": -1,
          "complete": -1,
          "clean_complete": -46
        },
        "right": {
          "D": 14,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 0,
          "complete": 0,
          "clean_complete": -1
        }
      }
    },
    "Q2_S21−C_S21": {
      "nominal": {
        "left": {
          "D": 1,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 0,
          "complete": 0,
          "clean_complete": -33
        },
        "right": {
          "D": -24,
          "S3+": 0,
          "S4+": 0,
          "open_hold": -1,
          "S5+": 0,
          "complete": 0,
          "clean_complete": -20
        }
      }
    },
    "Q1_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -2,
          "S3+": 3,
          "S4+": 3,
          "open_hold": 3,
          "S5+": 3,
          "complete": 3,
          "clean_complete": 17
        },
        "right": {
          "D": 1,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 1,
          "complete": 0,
          "clean_complete": -19
        }
      }
    },
    "Q2_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -22,
          "S3+": 3,
          "S4+": 2,
          "open_hold": 1,
          "S5+": 2,
          "complete": 2,
          "clean_complete": 16
        },
        "right": {
          "D": -4,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 1,
          "complete": 1,
          "clean_complete": 0
        }
      }
    }
  },
  "negative_deltas": [
    {
      "reference": "Q1_S21−C_S21",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -5,
        "S5+": -1,
        "complete": -1,
        "clean_complete": -46
      }
    },
    {
      "reference": "Q1_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -1
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -33
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -24,
        "open_hold": -1,
        "clean_complete": -20
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -2
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -19
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -22
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -4
      }
    },
    {
      "reference": "C_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -2
      }
    },
    {
      "reference": "C_S21−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -6
      }
    },
    {
      "reference": "Q2_S21−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -11
      }
    },
    {
      "reference": "C_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -2
      }
    },
    {
      "reference": "C_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -1,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2
      }
    },
    {
      "reference": "Q1_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S3+": -1,
        "complete": -1,
        "clean_complete": -9
      }
    },
    {
      "reference": "Q2_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -6,
        "open_hold": -1,
        "clean_complete": -3
      }
    },
    {
      "reference": "Q2_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1,
        "clean_complete": -1
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
    "outcome": "QUALITY_UNRESOLVED",
    "recipe_a": "C",
    "carrier_a": "C_S21",
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
    "C_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 12,
      "complete_with_body_contact_above_5N": 1,
      "complete_without_crossing_measurement": 0
    },
    "C_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 23,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 50,
      "complete_with_body_contact_above_5N": 37,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 24,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 27,
      "complete_with_body_contact_above_5N": 26,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 43,
      "complete_with_body_contact_above_5N": 4,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 61,
      "complete_with_body_contact_above_5N": 10,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 23,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 45,
      "complete_with_body_contact_above_5N": 2,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 42,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 26,
      "complete_with_body_contact_above_5N": 28,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 24,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    }
  },
  "k": {},
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
    "v27_smoke_a": {
      "state": "PASS",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_smoke_a/RUN_RECEIPT.json"
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
    "v27_watch_a": {
      "state": "FAIL",
      "returncode": 143,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a/RUN_RECEIPT.json"
    },
    "v27_watch_a_r2": {
      "state": "RUNNING",
      "returncode": 0,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a_r2/RUN_RECEIPT.json"
    }
  },
  "gpu": [
    "0, 794 MiB, 49140 MiB, 7 %",
    "1, 794 MiB, 49140 MiB, 12 %",
    "2, 2 MiB, 49140 MiB, 0 %",
    "3, 1691 MiB, 49140 MiB, 13 %",
    "4, 2 MiB, 49140 MiB, 0 %",
    "5, 2 MiB, 49140 MiB, 0 %",
    "6, 2 MiB, 49140 MiB, 0 %",
    "7, 2 MiB, 49140 MiB, 0 %"
  ],
  "processes": [
    "2180491 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step3000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step3000.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_a_step3000_readout_20260906.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step2500/reducer.json"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step3000/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step3000.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## 父策略历史比较

参考 C_S2 的 Q0 DEV（每侧128）；以下为百分点差，N128与N64不视为逐episode配对。

| Cell/侧 | D Δpp | S3+ Δpp | S4+ Δpp | open_hold Δpp | S5+ Δpp | complete Δpp | clean Δpp |
|---|---:|---:|---:|---:|---:|---:|---:|
| C_S21/left | -3.91 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +21.09 |
| C_S21/right | -7.03 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +10.16 |
| Q1_S21/left | -11.72 | +0.00 | +0.00 | +0.00 | -1.56 | -1.56 | -50.78 |
| Q1_S21/right | +14.84 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +8.59 |
| Q2_S21/left | -2.34 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | -30.47 |
| Q2_S21/right | -44.53 | +0.00 | +0.00 | -1.56 | +0.00 | +0.00 | -21.09 |
| C_S22/left | -0.78 | -4.69 | -4.69 | -4.69 | -4.69 | -4.69 | -58.59 |
| C_S22/right | -3.91 | -3.12 | -3.12 | -3.12 | -3.12 | -3.12 | +7.03 |
| Q1_S22/left | -3.91 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | -32.03 |
| Q1_S22/right | -2.34 | -1.56 | -1.56 | -1.56 | -1.56 | -3.12 | -22.66 |
| Q2_S22/left | -35.16 | +0.00 | -1.56 | -3.12 | -1.56 | -1.56 | -33.59 |
| Q2_S22/right | -10.16 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | +7.03 |

本次通过完整64样本门的侧：无。非endpoint不结算配方。

松手后身体力无读数不能当作0 N；clean判据使用首次Stage3至终止的身体力峰值。Wave A不启用K或恢复环。

## Wave A endpoint 冻结

`QUALITY_UNRESOLVED`；`RECIPE_A=C`；`CARRIER_A=C_S21 step3000`。C、Q1、Q2的LEFT两seed clean均值分别25.5、11、17，因此Q1/Q2相对C为−14.5/−8.5。所有侧均未达到完整64样本门；endpoint无Q_HARMFUL_RIGHT标签。决策只使用step3000，不替换为较好的中途读数。

六格训练各3000 batches均PASS/0，六个milestones共72 lanes、4608 episodes，均exact64、integrity0。旧v26 artifact未回写。研究载体不是Teacher/G7 binding更新。
