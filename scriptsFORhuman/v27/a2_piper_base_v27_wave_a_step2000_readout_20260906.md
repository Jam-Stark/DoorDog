# base_v27 wave_a/step2000 readout

2026-09-06 09:25 HKT

状态：`V27_COMPLETE`；step=2000；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| C_S21 | nominal | left | 56/64/64/64/64/64/44 | 55 | 0.0 | 1.135756254196167 | 405.0 | 0.0 | {"complete": 64} | 0 |
| C_S21 | nominal | right | 47/63/63/63/63/63/36 | 63 | 0.0 | 1.0764728784561157 | 448.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q1_S21 | nominal | left | 47/63/63/63/63/63/36 | 0 | 99.44085693359375 | 1.1128379106521606 | 415.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q1_S21 | nominal | right | 56/64/64/64/64/64/38 | 64 | 0.0 | 1.083150863647461 | 457.0 | 0.0 | {"complete": 64} | 0 |
| Q2_S21 | nominal | left | 51/62/62/62/1/1/0 | 0 | None | 1.3559669256210327 | 218.0 | 0.08748288534985948 | {"upper_dof_overspeed": 63, "complete": 1} | 0 |
| Q2_S21 | nominal | right | 34/63/63/62/41/19/6 | 0 | 0.0 | 1.0725653171539307 | 241.0 | 0.0 | {"upper_dof_overspeed": 45, "complete": 19} | 0 |
| C_S22 | nominal | left | 61/62/62/62/60/60/26 | 0 | 0.0 | 1.0306463241577148 | 423.0 | 0.001048142258204424 | {"stage_overtime": 2, "complete": 60, "door_distance": 2} | 0 |
| C_S22 | nominal | right | 55/63/63/63/63/63/36 | 63 | 0.0 | 1.0778173208236694 | 470.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q1_S22 | nominal | left | 49/63/63/63/63/63/36 | 0 | 512.2661743164062 | 1.1522258520126343 | 419.0 | 0.00022297372626258873 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q1_S22 | nominal | right | 52/64/64/63/64/64/37 | 0 | 0.0 | 1.0780225992202759 | 439.0 | 0.08714194327955078 | {"complete": 64} | 0 |
| Q2_S22 | nominal | left | 29/64/64/64/64/64/28 | 2 | 161.15902709960938 | 1.1647138595581055 | 432.0 | 0.014382769586585718 | {"complete": 64} | 0 |
| Q2_S22 | nominal | right | 56/64/64/64/63/63/36 | 64 | 0.0 | 1.0905907154083252 | 448.0 | 0.0 | {"upper_dof_overspeed": 1, "complete": 63} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "Q1_S21−C_S21": {
      "nominal": {
        "left": {
          "D": -9,
          "S3+": -1,
          "S4+": -1,
          "open_hold": -1,
          "S5+": -1,
          "complete": -1,
          "clean_complete": -8
        },
        "right": {
          "D": 9,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 1,
          "complete": 1,
          "clean_complete": 2
        }
      }
    },
    "Q2_S21−C_S21": {
      "nominal": {
        "left": {
          "D": -5,
          "S3+": -2,
          "S4+": -2,
          "open_hold": -2,
          "S5+": -63,
          "complete": -63,
          "clean_complete": -44
        },
        "right": {
          "D": -13,
          "S3+": 0,
          "S4+": 0,
          "open_hold": -1,
          "S5+": -22,
          "complete": -44,
          "clean_complete": -30
        }
      }
    },
    "Q1_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -12,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 3,
          "complete": 3,
          "clean_complete": 10
        },
        "right": {
          "D": -3,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 0,
          "S5+": 1,
          "complete": 1,
          "clean_complete": 1
        }
      }
    },
    "Q2_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -32,
          "S3+": 2,
          "S4+": 2,
          "open_hold": 2,
          "S5+": 4,
          "complete": 4,
          "clean_complete": 2
        },
        "right": {
          "D": 1,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 0,
          "complete": 0,
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
        "D": -9,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1,
        "clean_complete": -8
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -5,
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2,
        "S5+": -63,
        "complete": -63,
        "clean_complete": -44
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -13,
        "open_hold": -1,
        "S5+": -22,
        "complete": -44,
        "clean_complete": -30
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -12
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -3
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -32
      }
    },
    {
      "reference": "Q2_S21−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -5,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -62,
        "complete": -62,
        "clean_complete": -41
      }
    },
    {
      "reference": "Q2_S21−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -4,
        "S5+": -21,
        "complete": -43,
        "clean_complete": -36
      }
    },
    {
      "reference": "C_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "S3+": -2,
        "S4+": -2,
        "open_hold": -2
      }
    },
    {
      "reference": "Q1_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -10,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1,
        "clean_complete": -15
      }
    },
    {
      "reference": "Q1_S22−previous",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "clean_complete": -4
      }
    },
    {
      "reference": "Q2_S22−previous",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -14,
        "clean_complete": -3
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
      "complete_with_crossing_hinge_below_threshold": 20,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "C_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 27,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 20,
      "complete_with_body_contact_above_5N": 14,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 26,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 1,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 11,
      "complete_with_body_contact_above_5N": 4,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 33,
      "complete_with_body_contact_above_5N": 4,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 27,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 12,
      "complete_with_body_contact_above_5N": 20,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 27,
      "complete_with_body_contact_above_5N": 1,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 13,
      "complete_with_body_contact_above_5N": 30,
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
    "2, 12922 MiB, 49140 MiB, 100 %",
    "3, 15958 MiB, 49140 MiB, 10 %",
    "4, 12942 MiB, 49140 MiB, 36 %",
    "5, 19838 MiB, 49140 MiB, 0 %",
    "6, 12818 MiB, 49140 MiB, 33 %",
    "7, 13202 MiB, 49140 MiB, 44 %"
  ],
  "processes": [
    "1273739 2692622    14:41:16 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s21/run.sh",
    "1273741 1273739    14:41:16 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell C_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21",
    "1273833 1273741    14:41:14 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S21",
    "1273882 2692622    14:41:14 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s21/run.sh",
    "1273884 1273882    14:41:14 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell Q1_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21",
    "1274036 1273884    14:41:13 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S21",
    "1274079 2692622    14:41:13 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s21/run.sh",
    "1274084 1274079    14:41:13 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell Q2_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21",
    "1274172 1274084    14:41:11 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S21",
    "1274215 2692622    14:41:11 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s22/run.sh",
    "1274216 1274215    14:41:11 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 5 --cell C_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22",
    "1274238 1274216    14:41:10 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S22",
    "1274257 2692622    14:41:09 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s22/run.sh",
    "1274259 1274257    14:41:09 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 6 --cell Q1_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22",
    "1274299 1274259    14:41:08 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S22",
    "1274321 2692622    14:41:08 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s22/run.sh",
    "1274323 1274321    14:41:08 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 7 --cell Q2_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22",
    "1274431 1274323    14:41:07 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S22",
    "1294957 2692622    14:24:05 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a_r2/run.sh",
    "1294960 1294957    14:24:05 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave A",
    "1910378 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step2000/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step2000.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_a_step2000_readout_20260906.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train --previous logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step1500/reducer.json"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step2000/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step2000.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## 父策略历史比较

参考 C_S2 的 Q0 DEV（每侧128）；以下为百分点差，N128与N64不视为逐episode配对。

| Cell/侧 | D Δpp | S3+ Δpp | S4+ Δpp | open_hold Δpp | S5+ Δpp | complete Δpp | clean Δpp |
|---|---:|---:|---:|---:|---:|---:|---:|
| C_S21/left | -0.78 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +10.16 |
| C_S21/right | -11.72 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | +2.34 |
| Q1_S21/left | -14.84 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | -2.34 |
| Q1_S21/right | +2.34 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +5.47 |
| Q2_S21/left | -8.59 | -3.12 | -3.12 | -3.12 | -98.44 | -98.44 | -58.59 |
| Q2_S21/right | -32.03 | -1.56 | -1.56 | -3.12 | -35.94 | -70.31 | -44.53 |
| C_S22/left | +7.03 | -3.12 | -3.12 | -3.12 | -6.25 | -6.25 | -17.97 |
| C_S22/right | +0.78 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | +2.34 |
| Q1_S22/left | -11.72 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | -2.34 |
| Q1_S22/right | -3.91 | +0.00 | +0.00 | -1.56 | +0.00 | +0.00 | +3.91 |
| Q2_S22/left | -42.97 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | -14.84 |
| Q2_S22/right | +2.34 | +0.00 | +0.00 | +0.00 | -1.56 | -1.56 | +2.34 |

本次通过完整64样本门的侧：无。非endpoint不结算配方。

松手后身体力无读数不能当作0 N；clean判据使用首次Stage3至终止的身体力峰值。Wave A不启用K或恢复环。

## 本次关键变化

Q1_S21 LEFT/RIGHT complete从step1500的14/24恢复到63/64；Q2_S21则从63/62降至1/19，超速终止63/45。全部lane exact64、integrity0、退出0；不重跑、不更改配方或预算。Q1_S22 LEFT clean从51降至36，Q2_S22 LEFT D从43降至29，比C_S22少32。单次milestone的恢复与退步均不能代替endpoint路由。
