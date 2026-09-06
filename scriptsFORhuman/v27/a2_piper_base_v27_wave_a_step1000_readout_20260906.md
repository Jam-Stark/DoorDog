# base_v27 wave_a/step1000 readout

2026-09-06 02:49 HKT

状态：`V27_COMPLETE`；step=1000；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| C_S21 | nominal | left | 46/64/64/64/64/64/7 | 64 | 389.23162841796875 | 0.9461756944656372 | 468.0 | 0.0 | {"complete": 64} | 0 |
| C_S21 | nominal | right | 47/63/63/63/57/57/2 | 40 | 0.0 | 1.0177462100982666 | 623.0 | 0.0 | {"stage_overtime": 5, "upper_dof_overspeed": 2, "complete": 57} | 0 |
| Q1_S21 | nominal | left | 50/64/63/63/63/61/36 | 63 | 43.2717170715332 | 1.0892013311386108 | 453.0 | 0.0 | {"upper_dof_overspeed": 2, "complete": 61, "stage_overtime": 1} | 0 |
| Q1_S21 | nominal | right | 26/63/63/63/63/63/34 | 63 | 0.0 | 1.0754669904708862 | 512.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q2_S21 | nominal | left | 47/62/62/62/61/58/48 | 15 | 98.98406219482422 | 1.280705451965332 | 438.0 | 0.0 | {"upper_dof_overspeed": 4, "stage_overtime": 2, "complete": 58} | 0 |
| Q2_S21 | nominal | right | 29/61/61/61/60/57/26 | 61 | 226.707763671875 | 1.0849298238754272 | 597.0 | 0.0 | {"upper_dof_overspeed": 7, "complete": 57} | 0 |
| C_S22 | nominal | left | 61/64/63/62/63/63/13 | 55 | 165.63966369628906 | 0.9993795156478882 | 462.0 | 0.0 | {"complete": 63, "stage_overtime": 1} | 0 |
| C_S22 | nominal | right | 52/60/60/60/60/60/29 | 60 | 171.23025512695312 | 1.0921478271484375 | 577.0 | 0.0 | {"stage_overtime": 4, "complete": 60} | 0 |
| Q1_S22 | nominal | left | 60/64/64/64/64/64/52 | 15 | 27.033931732177734 | 1.1995235681533813 | 443.0 | 0.0 | {"complete": 64} | 0 |
| Q1_S22 | nominal | right | 34/62/62/62/62/62/58 | 58 | 0.0 | 1.278818964958191 | 498.0 | 6.277857994852157e-05 | {"stage_overtime": 2, "complete": 62} | 0 |
| Q2_S22 | nominal | left | 51/64/64/64/64/63/53 | 8 | 0.0 | 1.229886531829834 | 432.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |
| Q2_S22 | nominal | right | 44/61/61/61/59/58/33 | 61 | 0.0 | 1.0772147178649902 | 511.0 | 0.0 | {"stage_overtime": 3, "upper_dof_overspeed": 3, "complete": 58} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "Q1_S21−C_S21": {
      "nominal": {
        "left": {
          "D": 4,
          "S3+": 0,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": -3,
          "clean_complete": 29
        },
        "right": {
          "D": -21,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 6,
          "complete": 6,
          "clean_complete": 32
        }
      }
    },
    "Q2_S21−C_S21": {
      "nominal": {
        "left": {
          "D": 1,
          "S3+": -2,
          "S4+": -2,
          "open_hold": -2,
          "S5+": -3,
          "complete": -6,
          "clean_complete": 41
        },
        "right": {
          "D": -18,
          "S3+": -2,
          "S4+": -2,
          "open_hold": -2,
          "S5+": 3,
          "complete": 0,
          "clean_complete": 24
        }
      }
    },
    "Q1_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -1,
          "S3+": 0,
          "S4+": 1,
          "open_hold": 2,
          "S5+": 1,
          "complete": 1,
          "clean_complete": 39
        },
        "right": {
          "D": -18,
          "S3+": 2,
          "S4+": 2,
          "open_hold": 2,
          "S5+": 2,
          "complete": 2,
          "clean_complete": 29
        }
      }
    },
    "Q2_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -10,
          "S3+": 0,
          "S4+": 1,
          "open_hold": 2,
          "S5+": 1,
          "complete": 0,
          "clean_complete": 40
        },
        "right": {
          "D": -8,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": -1,
          "complete": -2,
          "clean_complete": 4
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
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -3
      }
    },
    {
      "reference": "Q1_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -21
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -3,
        "complete": -6
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -18,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -1
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -18
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -10
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -8,
        "S5+": -1,
        "complete": -2
      }
    },
    {
      "reference": "C_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -7
      }
    },
    {
      "reference": "C_S21−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -19
      }
    },
    {
      "reference": "Q1_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -5
      }
    },
    {
      "reference": "Q2_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "S3+": -2,
        "complete": -3,
        "clean_complete": -12
      }
    },
    {
      "reference": "Q2_S21−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S3+": -1
      }
    },
    {
      "reference": "C_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "open_hold": -1
      }
    },
    {
      "reference": "C_S22−previous",
      "stratum": "nominal",
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
      "reference": "Q1_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -2,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2
      }
    },
    {
      "reference": "Q2_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -4
      }
    },
    {
      "reference": "Q2_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S3+": -3,
        "S5+": -1,
        "complete": -2
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
      "complete_with_crossing_hinge_below_threshold": 48,
      "complete_with_body_contact_above_5N": 39,
      "complete_without_crossing_measurement": 0
    },
    "C_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 34,
      "complete_with_body_contact_above_5N": 52,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 23,
      "complete_with_body_contact_above_5N": 2,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 29,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 1,
      "complete_with_body_contact_above_5N": 9,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 24,
      "complete_with_body_contact_above_5N": 14,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 41,
      "complete_with_body_contact_above_5N": 25,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 28,
      "complete_with_body_contact_above_5N": 8,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 9,
      "complete_with_body_contact_above_5N": 4,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 2,
      "complete_with_body_contact_above_5N": 2,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 5,
      "complete_with_body_contact_above_5N": 6,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 25,
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
    "2, 13320 MiB, 49140 MiB, 28 %",
    "3, 13322 MiB, 49140 MiB, 26 %",
    "4, 12916 MiB, 49140 MiB, 27 %",
    "5, 13326 MiB, 49140 MiB, 38 %",
    "6, 13326 MiB, 49140 MiB, 49 %",
    "7, 13456 MiB, 49140 MiB, 36 %"
  ],
  "processes": [
    "1273739 2692622    08:05:49 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s21/run.sh",
    "1273741 1273739    08:05:49 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell C_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21",
    "1273833 1273741    08:05:48 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S21",
    "1273882 2692622    08:05:48 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s21/run.sh",
    "1273884 1273882    08:05:48 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell Q1_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21",
    "1274036 1273884    08:05:47 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S21",
    "1274079 2692622    08:05:46 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s21/run.sh",
    "1274084 1274079    08:05:46 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell Q2_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21",
    "1274172 1274084    08:05:45 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S21",
    "1274215 2692622    08:05:45 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s22/run.sh",
    "1274216 1274215    08:05:45 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 5 --cell C_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22",
    "1274238 1274216    08:05:44 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S22",
    "1274257 2692622    08:05:43 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s22/run.sh",
    "1274259 1274257    08:05:43 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 6 --cell Q1_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22",
    "1274299 1274259    08:05:42 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S22",
    "1274321 2692622    08:05:42 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s22/run.sh",
    "1274323 1274321    08:05:42 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 7 --cell Q2_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22",
    "1274431 1274323    08:05:40 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S22",
    "1294957 2692622    07:48:39 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a_r2/run.sh",
    "1294960 1294957    07:48:39 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave A",
    "1638107 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step1000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step1000.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_a_step1000_readout_20260906.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step500/reducer.json"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step1000/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step1000.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## 父策略历史比较

参考 C_S2 的 Q0 DEV（每侧128）；以下为百分点差，N128与N64不视为逐episode配对。

| Cell/侧 | D Δpp | S3+ Δpp | S4+ Δpp | open_hold Δpp | S5+ Δpp | complete Δpp | clean Δpp |
|---|---:|---:|---:|---:|---:|---:|---:|
| C_S21/left | -16.41 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | -47.66 |
| C_S21/right | -11.72 | -1.56 | -1.56 | -1.56 | -10.94 | -10.94 | -50.78 |
| Q1_S21/left | -10.16 | +0.00 | -1.56 | -1.56 | -1.56 | -4.69 | -2.34 |
| Q1_S21/right | -44.53 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | -0.78 |
| Q2_S21/left | -14.84 | -3.12 | -3.12 | -3.12 | -4.69 | -9.38 | +16.41 |
| Q2_S21/right | -39.84 | -4.69 | -4.69 | -4.69 | -6.25 | -10.94 | -13.28 |
| C_S22/left | +7.03 | +0.00 | -1.56 | -3.12 | -1.56 | -1.56 | -38.28 |
| C_S22/right | -3.91 | -6.25 | -6.25 | -6.25 | -6.25 | -6.25 | -8.59 |
| Q1_S22/left | +5.47 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +22.66 |
| Q1_S22/right | -32.03 | -3.12 | -3.12 | -3.12 | -3.12 | -3.12 | +36.72 |
| Q2_S22/left | -8.59 | +0.00 | +0.00 | +0.00 | +0.00 | -1.56 | +24.22 |
| Q2_S22/right | -16.41 | -4.69 | -4.69 | -4.69 | -7.81 | -9.38 | -2.34 |

本次通过完整64样本门的侧：Q1_S22/right。非endpoint不结算配方。

松手后身体力无读数不能当作0 N；clean判据使用首次Stage3至终止的身体力峰值。Wave A不启用K或恢复环。
