# base_v27 wave_a/step2500 readout

2026-09-06 12:57 HKT

状态：`V27_COMPLETE`；step=2500；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| C_S21 | nominal | left | 56/64/64/64/64/64/41 | 41 | 0.0 | 1.1033120155334473 | 396.0 | 0.0 | {"complete": 64} | 0 |
| C_S21 | nominal | right | 56/64/64/64/64/64/34 | 64 | 0.0 | 1.058774709701538 | 422.0 | 0.0 | {"complete": 64} | 0 |
| Q1_S21 | nominal | left | 35/51/51/51/30/30/4 | 0 | 2912.22021484375 | 0.9662180542945862 | 222.0 | 0.0 | {"upper_dof_overspeed": 33, "stage_overtime": 1, "complete": 30} | 0 |
| Q1_S21 | nominal | right | 41/43/43/43/42/31/19 | 43 | 0.0 | 1.1362910270690918 | 295.0 | 0.0 | {"upper_dof_overspeed": 32, "stage_overtime": 1, "complete": 31} | 0 |
| Q2_S21 | nominal | left | 54/64/64/64/28/28/17 | 0 | 98.08425903320312 | 1.205216407775879 | 221.0 | 0.04793547732575834 | {"upper_dof_overspeed": 36, "complete": 28} | 0 |
| Q2_S21 | nominal | right | 37/63/63/63/63/41/16 | 0 | None | 1.0511618852615356 | 388.0 | 0.0 | {"upper_dof_overspeed": 23, "complete": 41} | 0 |
| C_S22 | nominal | left | 51/54/54/54/53/52/2 | 9 | None | 0.898313045501709 | 407.0 | 0.0 | {"upper_dof_overspeed": 9, "stage_overtime": 3, "complete": 52} | 0 |
| C_S22 | nominal | right | 53/64/64/64/64/0/0 | 64 | 0.0 | 1.089660882949829 | 293.0 | 0.0 | {"upper_dof_overspeed": 64} | 0 |
| Q1_S22 | nominal | left | 46/52/52/52/42/0/0 | 33 | 0.0 | 1.1515007019042969 | 248.0 | 0.0018734266143668403 | {"upper_dof_overspeed": 52, "stage_overtime": 12} | 0 |
| Q1_S22 | nominal | right | 51/64/63/63/63/63/29 | 0 | 0.0 | 1.03970468044281 | 432.0 | 0.13056625508477626 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| Q2_S22 | nominal | left | 40/63/63/63/63/63/19 | 0 | 1036.433349609375 | 1.0831170082092285 | 420.0 | 0.0019938706937931545 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q2_S22 | nominal | right | 41/64/64/64/64/64/40 | 64 | 0.0 | 1.0994586944580078 | 419.0 | 0.0 | {"complete": 64} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "Q1_S21−C_S21": {
      "nominal": {
        "left": {
          "D": -21,
          "S3+": -13,
          "S4+": -13,
          "open_hold": -13,
          "S5+": -34,
          "complete": -34,
          "clean_complete": -37
        },
        "right": {
          "D": -15,
          "S3+": -21,
          "S4+": -21,
          "open_hold": -21,
          "S5+": -22,
          "complete": -33,
          "clean_complete": -15
        }
      }
    },
    "Q2_S21−C_S21": {
      "nominal": {
        "left": {
          "D": -2,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": -36,
          "complete": -36,
          "clean_complete": -24
        },
        "right": {
          "D": -19,
          "S3+": -1,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": -23,
          "clean_complete": -18
        }
      }
    },
    "Q1_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -5,
          "S3+": -2,
          "S4+": -2,
          "open_hold": -2,
          "S5+": -11,
          "complete": -52,
          "clean_complete": -2
        },
        "right": {
          "D": -2,
          "S3+": 0,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": 63,
          "clean_complete": 29
        }
      }
    },
    "Q2_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -11,
          "S3+": 9,
          "S4+": 9,
          "open_hold": 9,
          "S5+": 10,
          "complete": 11,
          "clean_complete": 17
        },
        "right": {
          "D": -12,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 0,
          "complete": 64,
          "clean_complete": 40
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
        "D": -21,
        "S3+": -13,
        "S4+": -13,
        "open_hold": -13,
        "S5+": -34,
        "complete": -34,
        "clean_complete": -37
      }
    },
    {
      "reference": "Q1_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -15,
        "S3+": -21,
        "S4+": -21,
        "open_hold": -21,
        "S5+": -22,
        "complete": -33,
        "clean_complete": -15
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -2,
        "S5+": -36,
        "complete": -36,
        "clean_complete": -24
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -19,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -23,
        "clean_complete": -18
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -5,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -11,
        "complete": -52,
        "clean_complete": -2
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -2,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -11
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -12
      }
    },
    {
      "reference": "C_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -3
      }
    },
    {
      "reference": "C_S21−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -2
      }
    },
    {
      "reference": "Q1_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -12,
        "S3+": -12,
        "S4+": -12,
        "open_hold": -12,
        "S5+": -33,
        "complete": -33,
        "clean_complete": -32
      }
    },
    {
      "reference": "Q1_S21−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -15,
        "S3+": -21,
        "S4+": -21,
        "open_hold": -21,
        "S5+": -22,
        "complete": -33,
        "clean_complete": -19
      }
    },
    {
      "reference": "C_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -10,
        "S3+": -8,
        "S4+": -8,
        "open_hold": -8,
        "S5+": -7,
        "complete": -8,
        "clean_complete": -24
      }
    },
    {
      "reference": "C_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -2,
        "complete": -63,
        "clean_complete": -36
      }
    },
    {
      "reference": "Q1_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -3,
        "S3+": -11,
        "S4+": -11,
        "open_hold": -11,
        "S5+": -21,
        "complete": -63,
        "clean_complete": -36
      }
    },
    {
      "reference": "Q1_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -1,
        "S4+": -1,
        "S5+": -1,
        "complete": -1,
        "clean_complete": -8
      }
    },
    {
      "reference": "Q2_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1,
        "clean_complete": -9
      }
    },
    {
      "reference": "Q2_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -15
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
    "C_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 23,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "C_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 30,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 17,
      "complete_with_body_contact_above_5N": 16,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 12,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 2,
      "complete_with_body_contact_above_5N": 11,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 25,
      "complete_with_body_contact_above_5N": 1,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 50,
      "complete_with_body_contact_above_5N": 14,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 34,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 28,
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
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s21/RUN_RECEIPT.json"
    },
    "v27_train_c_s22": {
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s22/RUN_RECEIPT.json"
    },
    "v27_train_q1_s21": {
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s21/RUN_RECEIPT.json"
    },
    "v27_train_q1_s22": {
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s22/RUN_RECEIPT.json"
    },
    "v27_train_q2_s21": {
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s21/RUN_RECEIPT.json"
    },
    "v27_train_q2_s22": {
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s22/RUN_RECEIPT.json"
    },
    "v27_watch_a": {
      "state": "FAIL",
      "returncode": 143,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a/RUN_RECEIPT.json"
    },
    "v27_watch_a_r2": {
      "state": "RUNNING",
      "returncode": null,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a_r2/RUN_RECEIPT.json"
    }
  },
  "gpu": [
    "0, 1 MiB, 49140 MiB, 0 %",
    "1, 1 MiB, 49140 MiB, 0 %",
    "2, 13900 MiB, 49140 MiB, 15 %",
    "3, 13756 MiB, 49140 MiB, 0 %",
    "4, 13960 MiB, 49140 MiB, 0 %",
    "5, 20934 MiB, 49140 MiB, 96 %",
    "6, 13792 MiB, 49140 MiB, 12 %",
    "7, 12960 MiB, 49140 MiB, 16 %"
  ],
  "processes": [
    "1273739 2692622    18:13:29 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s21/run.sh",
    "1273741 1273739    18:13:29 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell C_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21",
    "1273833 1273741    18:13:28 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S21",
    "1273882 2692622    18:13:27 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s21/run.sh",
    "1273884 1273882    18:13:27 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell Q1_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21",
    "1274036 1273884    18:13:26 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S21",
    "1274079 2692622    18:13:26 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s21/run.sh",
    "1274084 1274079    18:13:26 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell Q2_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21",
    "1274172 1274084    18:13:25 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S21",
    "1274215 2692622    18:13:24 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s22/run.sh",
    "1274216 1274215    18:13:24 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 5 --cell C_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22",
    "1274238 1274216    18:13:23 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S22",
    "1274257 2692622    18:13:23 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s22/run.sh",
    "1274259 1274257    18:13:23 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 6 --cell Q1_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22",
    "1274299 1274259    18:13:22 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S22",
    "1274321 2692622    18:13:21 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s22/run.sh",
    "1274323 1274321    18:13:21 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 7 --cell Q2_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22",
    "1274431 1274323    18:13:20 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S22",
    "1294957 2692622    17:56:19 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a_r2/run.sh",
    "1294960 1294957    17:56:19 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave A",
    "2008403 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step2500/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step2500.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_a_step2500_readout_20260906.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step2000/reducer.json"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step2500/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step2500.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## 父策略历史比较

参考 C_S2 的 Q0 DEV（每侧128）；以下为百分点差，N128与N64不视为逐episode配对。

| Cell/侧 | D Δpp | S3+ Δpp | S4+ Δpp | open_hold Δpp | S5+ Δpp | complete Δpp | clean Δpp |
|---|---:|---:|---:|---:|---:|---:|---:|
| C_S21/left | -0.78 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +5.47 |
| C_S21/right | +2.34 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | -0.78 |
| Q1_S21/left | -33.59 | -20.31 | -20.31 | -20.31 | -53.12 | -53.12 | -52.34 |
| Q1_S21/right | -21.09 | -32.81 | -32.81 | -32.81 | -34.38 | -51.56 | -24.22 |
| Q2_S21/left | -3.91 | +0.00 | +0.00 | +0.00 | -56.25 | -56.25 | -32.03 |
| Q2_S21/right | -27.34 | -1.56 | -1.56 | -1.56 | -1.56 | -35.94 | -28.91 |
| C_S22/left | -8.59 | -15.62 | -15.62 | -15.62 | -17.19 | -18.75 | -55.47 |
| C_S22/right | -2.34 | +0.00 | +0.00 | +0.00 | +0.00 | -100.00 | -53.91 |
| Q1_S22/left | -16.41 | -18.75 | -18.75 | -18.75 | -34.38 | -100.00 | -58.59 |
| Q1_S22/right | -5.47 | +0.00 | -1.56 | -1.56 | -1.56 | -1.56 | -8.59 |
| Q2_S22/left | -25.78 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | -28.91 |
| Q2_S22/right | -21.09 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +8.59 |

本次通过完整64样本门的侧：无。非endpoint不结算配方。

松手后身体力无读数不能当作0 N；clean判据使用首次Stage3至终止的身体力峰值。Wave A不启用K或恢复环。

## 本次关键变化

C_S22 RIGHT与Q1_S22 LEFT complete均为0：前者64集超速终止，后者52集超速、12集超时。C_S21 complete两侧64，但clean41/34仍未达门。seed22 RIGHT相对C的大正差由本轮C下降至0产生，不构成Q arm已达标的证据。所有lane exact64、integrity0、退出0；保持原预算及endpoint规则。
