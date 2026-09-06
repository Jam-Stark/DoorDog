# base_v27 wave_a/step1500 readout

2026-09-06 05:53 HKT

状态：`V27_COMPLETE`；step=1500；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| C_S21 | nominal | left | 50/64/64/64/64/60/27 | 64 | 31.810312271118164 | 1.0344250202178955 | 414.0 | 0.0 | {"upper_dof_overspeed": 4, "complete": 60} | 0 |
| C_S21 | nominal | right | 46/63/63/63/63/63/34 | 63 | 0.0 | 1.0558527708053589 | 499.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q1_S21 | nominal | left | 9/17/16/16/15/14/11 | 1 | 58.46371841430664 | 1.2643977403640747 | 73.0 | 0.0 | {"upper_dof_overspeed": 49, "complete": 14, "stage_overtime": 1} | 0 |
| Q1_S21 | nominal | right | 29/42/42/42/38/24/6 | 42 | 0.0 | 1.0173782110214233 | 347.0 | 0.0 | {"upper_dof_overspeed": 40, "complete": 24} | 0 |
| Q2_S21 | nominal | left | 56/63/63/63/63/63/41 | 0 | 0.0 | 1.2265204191207886 | 418.0 | 0.034713198440690554 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q2_S21 | nominal | right | 38/62/62/62/62/62/42 | 1 | None | 1.136408805847168 | 436.0 | 0.007683785425824667 | {"stage_overtime": 2, "complete": 62} | 0 |
| C_S22 | nominal | left | 59/64/64/64/58/58/12 | 12 | None | 0.9530709981918335 | 440.0 | 0.0 | {"complete": 58, "door_distance": 3, "stage_overtime": 3} | 0 |
| C_S22 | nominal | right | 54/58/58/58/58/58/32 | 58 | 27.277931213378906 | 1.090461254119873 | 494.0 | 0.0 | {"stage_overtime": 6, "complete": 58} | 0 |
| Q1_S22 | nominal | left | 59/64/64/64/64/64/51 | 9 | 0.0 | 1.1766360998153687 | 413.0 | 0.0 | {"complete": 64} | 0 |
| Q1_S22 | nominal | right | 38/63/63/63/63/63/41 | 42 | 143.6223602294922 | 1.1309516429901123 | 448.0 | 0.08046017082098658 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q2_S22 | nominal | left | 43/64/64/64/64/64/31 | 0 | 512.436767578125 | 1.2333152294158936 | 436.0 | 0.0034933875164866505 | {"complete": 64} | 0 |
| Q2_S22 | nominal | right | 38/63/63/63/63/63/36 | 63 | 0.0 | 1.0694018602371216 | 490.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "Q1_S21−C_S21": {
      "nominal": {
        "left": {
          "D": -41,
          "S3+": -47,
          "S4+": -48,
          "open_hold": -48,
          "S5+": -49,
          "complete": -46,
          "clean_complete": -16
        },
        "right": {
          "D": -17,
          "S3+": -21,
          "S4+": -21,
          "open_hold": -21,
          "S5+": -25,
          "complete": -39,
          "clean_complete": -28
        }
      }
    },
    "Q2_S21−C_S21": {
      "nominal": {
        "left": {
          "D": 6,
          "S3+": -1,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": 3,
          "clean_complete": 14
        },
        "right": {
          "D": -8,
          "S3+": -1,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": -1,
          "clean_complete": 8
        }
      }
    },
    "Q1_S22−C_S22": {
      "nominal": {
        "left": {
          "D": 0,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 6,
          "complete": 6,
          "clean_complete": 39
        },
        "right": {
          "D": -16,
          "S3+": 5,
          "S4+": 5,
          "open_hold": 5,
          "S5+": 5,
          "complete": 5,
          "clean_complete": 9
        }
      }
    },
    "Q2_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -16,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 6,
          "complete": 6,
          "clean_complete": 19
        },
        "right": {
          "D": -16,
          "S3+": 5,
          "S4+": 5,
          "open_hold": 5,
          "S5+": 5,
          "complete": 5,
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
        "D": -41,
        "S3+": -47,
        "S4+": -48,
        "open_hold": -48,
        "S5+": -49,
        "complete": -46,
        "clean_complete": -16
      }
    },
    {
      "reference": "Q1_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -17,
        "S3+": -21,
        "S4+": -21,
        "open_hold": -21,
        "S5+": -25,
        "complete": -39,
        "clean_complete": -28
      }
    },
    {
      "reference": "Q2_S21−C_S21",
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
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -8,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -16
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -16
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -16
      }
    },
    {
      "reference": "C_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "complete": -4
      }
    },
    {
      "reference": "C_S21−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -1
      }
    },
    {
      "reference": "Q1_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -41,
        "S3+": -47,
        "S4+": -47,
        "open_hold": -47,
        "S5+": -48,
        "complete": -47,
        "clean_complete": -25
      }
    },
    {
      "reference": "Q1_S21−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S3+": -21,
        "S4+": -21,
        "open_hold": -21,
        "S5+": -25,
        "complete": -39,
        "clean_complete": -28
      }
    },
    {
      "reference": "Q2_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "clean_complete": -7
      }
    },
    {
      "reference": "C_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -2,
        "S5+": -5,
        "complete": -5,
        "clean_complete": -1
      }
    },
    {
      "reference": "C_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -2,
        "complete": -2
      }
    },
    {
      "reference": "Q1_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -1,
        "clean_complete": -1
      }
    },
    {
      "reference": "Q1_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -17
      }
    },
    {
      "reference": "Q2_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -8,
        "clean_complete": -22
      }
    },
    {
      "reference": "Q2_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -6
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
      "complete_with_crossing_hinge_below_threshold": 31,
      "complete_with_body_contact_above_5N": 3,
      "complete_without_crossing_measurement": 0
    },
    "C_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 29,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 2,
      "complete_with_body_contact_above_5N": 2,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 17,
      "complete_with_body_contact_above_5N": 2,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 3,
      "complete_with_body_contact_above_5N": 20,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 19,
      "complete_with_body_contact_above_5N": 4,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 46,
      "complete_with_body_contact_above_5N": 9,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 24,
      "complete_with_body_contact_above_5N": 3,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 11,
      "complete_with_body_contact_above_5N": 3,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 19,
      "complete_with_body_contact_above_5N": 3,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 12,
      "complete_with_body_contact_above_5N": 26,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 27,
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
    "0, 794 MiB, 49140 MiB, 0 %",
    "1, 2 MiB, 49140 MiB, 0 %",
    "2, 13784 MiB, 49140 MiB, 18 %",
    "3, 13307 MiB, 49140 MiB, 49 %",
    "4, 12926 MiB, 49140 MiB, 9 %",
    "5, 14316 MiB, 49140 MiB, 29 %",
    "6, 13188 MiB, 49140 MiB, 9 %",
    "7, 19626 MiB, 49140 MiB, 0 %"
  ],
  "processes": [
    "1273739 2692622    11:09:07 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s21/run.sh",
    "1273741 1273739    11:09:07 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell C_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21",
    "1273833 1273741    11:09:06 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S21",
    "1273882 2692622    11:09:05 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s21/run.sh",
    "1273884 1273882    11:09:05 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell Q1_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21",
    "1274036 1273884    11:09:04 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S21",
    "1274079 2692622    11:09:04 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s21/run.sh",
    "1274084 1274079    11:09:04 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell Q2_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21",
    "1274172 1274084    11:09:03 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S21",
    "1274215 2692622    11:09:02 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s22/run.sh",
    "1274216 1274215    11:09:02 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 5 --cell C_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22",
    "1274238 1274216    11:09:01 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S22",
    "1274257 2692622    11:09:01 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s22/run.sh",
    "1274259 1274257    11:09:01 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 6 --cell Q1_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22",
    "1274299 1274259    11:08:59 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S22",
    "1274321 2692622    11:08:59 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s22/run.sh",
    "1274323 1274321    11:08:59 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 7 --cell Q2_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22",
    "1274431 1274323    11:08:58 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S22",
    "1294957 2692622    10:51:57 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a_r2/run.sh",
    "1294960 1294957    10:51:57 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave A",
    "1768795 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step1500/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step1500.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_a_step1500_readout_20260906.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step1000/reducer.json"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step1500/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step1500.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## 父策略历史比较

参考 C_S2 的 Q0 DEV（每侧128）；以下为百分点差，N128与N64不视为逐episode配对。

| Cell/侧 | D Δpp | S3+ Δpp | S4+ Δpp | open_hold Δpp | S5+ Δpp | complete Δpp | clean Δpp |
|---|---:|---:|---:|---:|---:|---:|---:|
| C_S21/left | -10.16 | +0.00 | +0.00 | +0.00 | +0.00 | -6.25 | -16.41 |
| C_S21/right | -13.28 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | -0.78 |
| Q1_S21/left | -74.22 | -73.44 | -75.00 | -75.00 | -76.56 | -78.12 | -41.41 |
| Q1_S21/right | -39.84 | -34.38 | -34.38 | -34.38 | -40.62 | -62.50 | -44.53 |
| Q2_S21/left | -0.78 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | +5.47 |
| Q2_S21/right | -25.78 | -3.12 | -3.12 | -3.12 | -3.12 | -3.12 | +11.72 |
| C_S22/left | +3.91 | +0.00 | +0.00 | +0.00 | -9.38 | -9.38 | -39.84 |
| C_S22/right | -0.78 | -9.38 | -9.38 | -9.38 | -9.38 | -9.38 | -3.91 |
| Q1_S22/left | +3.91 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +21.09 |
| Q1_S22/right | -25.78 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | +10.16 |
| Q2_S22/left | -21.09 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | -10.16 |
| Q2_S22/right | -25.78 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | +2.34 |

本次通过完整64样本门的侧：无。非endpoint不结算配方。

松手后身体力无读数不能当作0 N；clean判据使用首次Stage3至终止的身体力峰值。Wave A不启用K或恢复环。

## 本次关键变化

Q1_S21 LEFT/RIGHT complete从step1000的61/63降至14/24，超速终止49/40；exact64、integrity0、正常退出，因此记录为注册策略评估退步，不做失败重跑或中途配方变更。Q1_S22 RIGHT clean从58降至41、Q2_S22 LEFT从53降至31。arm_j4驻留最高为Q1_S22 RIGHT 8.046%，另有Q2_S21 LEFT/RIGHT 3.471%/0.768%、Q2_S22 LEFT 0.349%。尚无endpoint结论，继续固定预算。
