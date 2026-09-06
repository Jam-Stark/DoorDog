# base_v27 wave_a/step500 readout

2026-09-05 22:54 HKT

状态：`V27_COMPLETE`；step=500；exact N=64。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| C_S21 | nominal | left | 53/64/56/56/54/53/0 | 54 | None | 0.8636519908905029 | 501.0 | 0.0 | {"upper_dof_overspeed": 11, "complete": 53} | 0 |
| C_S21 | nominal | right | 28/63/42/42/42/42/21 | 42 | 0.0 | 1.0404489040374756 | 561.0 | 0.0 | {"upper_dof_overspeed": 21, "stage_overtime": 1, "complete": 42} | 0 |
| Q1_S21 | nominal | left | 55/64/57/57/56/54/0 | 56 | None | 0.9060105085372925 | 463.0 | 0.0 | {"upper_dof_overspeed": 8, "complete": 54, "stage_overtime": 2} | 0 |
| Q1_S21 | nominal | right | 12/62/60/59/58/58/33 | 58 | 50.43773651123047 | 1.1289290189743042 | 545.0 | 0.0 | {"upper_dof_overspeed": 4, "stage_overtime": 2, "complete": 58} | 0 |
| Q2_S21 | nominal | left | 34/64/62/62/61/61/60 | 0 | 0.0 | 1.4270238876342773 | 458.0 | 0.00013992374156084934 | {"upper_dof_overspeed": 3, "complete": 61} | 0 |
| Q2_S21 | nominal | right | 26/62/43/43/43/43/25 | 43 | 0.0 | 1.0577468872070312 | 515.0 | 0.0 | {"upper_dof_overspeed": 20, "stage_overtime": 1, "complete": 43} | 0 |
| C_S22 | nominal | left | 51/64/63/63/60/60/0 | 61 | None | 0.9241859316825867 | 543.0 | 0.0 | {"complete": 60, "stage_overtime": 4} | 0 |
| C_S22 | nominal | right | 22/63/63/63/63/63/32 | 63 | 0.0 | 1.0585901737213135 | 557.0 | 0.0 | {"stage_overtime": 1, "complete": 63} | 0 |
| Q1_S22 | nominal | left | 37/64/63/63/63/62/45 | 62 | 288.4559631347656 | 1.1845895051956177 | 486.0 | 0.0 | {"upper_dof_overspeed": 2, "complete": 62} | 0 |
| Q1_S22 | nominal | right | 36/64/64/64/62/57/30 | 64 | 0.0 | 1.075774073600769 | 555.0 | 0.0 | {"upper_dof_overspeed": 7, "complete": 57} | 0 |
| Q2_S22 | nominal | left | 55/64/60/60/60/60/13 | 60 | None | 1.0274587869644165 | 469.0 | 0.0 | {"upper_dof_overspeed": 4, "complete": 60} | 0 |
| Q2_S22 | nominal | right | 30/64/60/60/60/60/26 | 60 | 0.0 | 1.0344831943511963 | 547.0 | 0.0 | {"upper_dof_overspeed": 4, "complete": 60} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {
    "Q1_S21−C_S21": {
      "nominal": {
        "left": {
          "D": 2,
          "S3+": 0,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 2,
          "complete": 1,
          "clean_complete": 0
        },
        "right": {
          "D": -16,
          "S3+": -1,
          "S4+": 18,
          "open_hold": 17,
          "S5+": 16,
          "complete": 16,
          "clean_complete": 12
        }
      }
    },
    "Q2_S21−C_S21": {
      "nominal": {
        "left": {
          "D": -19,
          "S3+": 0,
          "S4+": 6,
          "open_hold": 6,
          "S5+": 7,
          "complete": 8,
          "clean_complete": 60
        },
        "right": {
          "D": -2,
          "S3+": -1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": 1,
          "complete": 1,
          "clean_complete": 4
        }
      }
    },
    "Q1_S22−C_S22": {
      "nominal": {
        "left": {
          "D": -14,
          "S3+": 0,
          "S4+": 0,
          "open_hold": 0,
          "S5+": 3,
          "complete": 2,
          "clean_complete": 45
        },
        "right": {
          "D": 14,
          "S3+": 1,
          "S4+": 1,
          "open_hold": 1,
          "S5+": -1,
          "complete": -6,
          "clean_complete": -2
        }
      }
    },
    "Q2_S22−C_S22": {
      "nominal": {
        "left": {
          "D": 4,
          "S3+": 0,
          "S4+": -3,
          "open_hold": -3,
          "S5+": 0,
          "complete": 0,
          "clean_complete": 13
        },
        "right": {
          "D": 8,
          "S3+": 1,
          "S4+": -3,
          "open_hold": -3,
          "S5+": -3,
          "complete": -3,
          "clean_complete": -6
        }
      }
    }
  },
  "negative_deltas": [
    {
      "reference": "Q1_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -16,
        "S3+": -1
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -19
      }
    },
    {
      "reference": "Q2_S21−C_S21",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "D": -2,
        "S3+": -1
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "D": -14
      }
    },
    {
      "reference": "Q1_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S5+": -1,
        "complete": -6,
        "clean_complete": -2
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "left",
      "negative_deltas": {
        "S4+": -3,
        "open_hold": -3
      }
    },
    {
      "reference": "Q2_S22−C_S22",
      "stratum": "nominal",
      "side": "right",
      "negative_deltas": {
        "S4+": -3,
        "open_hold": -3,
        "S5+": -3,
        "complete": -3,
        "clean_complete": -6
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
      "complete_with_crossing_hinge_below_threshold": 49,
      "complete_with_body_contact_above_5N": 47,
      "complete_without_crossing_measurement": 0
    },
    "C_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 21,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 52,
      "complete_with_body_contact_above_5N": 54,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 20,
      "complete_with_body_contact_above_5N": 5,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 1,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S21/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 18,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 49,
      "complete_with_body_contact_above_5N": 57,
      "complete_without_crossing_measurement": 0
    },
    "C_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 31,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 7,
      "complete_with_body_contact_above_5N": 13,
      "complete_without_crossing_measurement": 0
    },
    "Q1_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 26,
      "complete_with_body_contact_above_5N": 1,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/left": {
      "complete_with_crossing_hinge_below_threshold": 33,
      "complete_with_body_contact_above_5N": 23,
      "complete_without_crossing_measurement": 0
    },
    "Q2_S22/nominal/right": {
      "complete_with_crossing_hinge_below_threshold": 31,
      "complete_with_body_contact_above_5N": 3,
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
    "2, 12900 MiB, 49140 MiB, 10 %",
    "3, 13698 MiB, 49140 MiB, 27 %",
    "4, 13862 MiB, 49140 MiB, 34 %",
    "5, 12906 MiB, 49140 MiB, 13 %",
    "6, 13312 MiB, 49140 MiB, 16 %",
    "7, 13738 MiB, 49140 MiB, 17 %"
  ],
  "processes": [
    "1273739 2692622    04:10:22 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s21/run.sh",
    "1273741 1273739    04:10:22 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell C_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21",
    "1273833 1273741    04:10:21 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S21",
    "1273882 2692622    04:10:21 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s21/run.sh",
    "1273884 1273882    04:10:21 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell Q1_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21",
    "1274036 1273884    04:10:19 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S21",
    "1274079 2692622    04:10:19 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s21/run.sh",
    "1274084 1274079    04:10:19 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell Q2_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21",
    "1274172 1274084    04:10:18 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S21",
    "1274215 2692622    04:10:18 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s22/run.sh",
    "1274216 1274215    04:10:18 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 5 --cell C_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22",
    "1274238 1274216    04:10:16 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S22",
    "1274257 2692622    04:10:16 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s22/run.sh",
    "1274259 1274257    04:10:16 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 6 --cell Q1_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22",
    "1274299 1274259    04:10:15 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S22",
    "1274321 2692622    04:10:14 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s22/run.sh",
    "1274323 1274321    04:10:14 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 7 --cell Q2_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22",
    "1274431 1274323    04:10:13 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S22",
    "1294957 2692622    03:53:12 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a_r2/run.sh",
    "1294960 1294957    03:53:12 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave A",
    "1445953 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step500/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step500.json --output scriptsFORhuman/v27/a2_piper_base_v27_wave_a_step500_readout_20260905.md --train-root logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step500/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/wave_a/step500.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## 历史反向读数与本次解读

12 lanes 均 exact64、integrity0、退出0。当前无一侧通过完整 64 样本门：Q2_S21 LEFT 虽 complete=61、clean=60，但 overspeed=3 超过上限2。step500 只报告读数，不结算 endpoint outcome，不改变配方或预算。

相对同一研究父策略 C_S2 的 Q0 DEV（每侧128），所有格两侧 complete 率均下降，所有 RIGHT clean_complete 率也下降。C 两 seed LEFT clean 从父策略75/128降至0/64；与历史 LEFT 常在 crossing 前松手相反，当前 C 两 seed 均多次握门穿过（54/61）。Q2_S21 LEFT 为0次握门穿过、crossing hinge中位1.427 rad，而Q2_S22 LEFT 为60次、中位1.027 rad，显示明显seed差异。以上均是实际观察，不构成因果诊断。

`post_release_body_force_p95=null` 表示没有可用的松手后读数，不能当作0 N。body-panel清洁判据使用首次Stage3至终止的峰值，故松手后p95=0也不意味着 clean。arm_j4限位驻留仅 Q2_S21 LEFT 非零（0.013992%），其余为0。Wave A不启用K或恢复环，相关telemetry记不适用。

| Cell/侧 | D Δpp | S3+ Δpp | S4+ Δpp | open_hold Δpp | S5+ Δpp | complete Δpp | clean Δpp |
|---|---:|---:|---:|---:|---:|---:|---:|
| C_S21/left | -5.47 | +0.00 | -12.50 | -12.50 | -15.62 | -17.19 | -58.59 |
| C_S21/right | -41.41 | -1.56 | -34.38 | -34.38 | -34.38 | -34.38 | -21.09 |
| Q1_S21/left | -2.34 | +0.00 | -10.94 | -10.94 | -12.50 | -15.62 | -58.59 |
| Q1_S21/right | -66.41 | -3.12 | -6.25 | -7.81 | -9.38 | -9.38 | -2.34 |
| Q2_S21/left | -35.16 | +0.00 | -3.12 | -3.12 | -4.69 | -4.69 | +35.16 |
| Q2_S21/right | -44.53 | -3.12 | -32.81 | -32.81 | -32.81 | -32.81 | -14.84 |
| C_S22/left | -8.59 | +0.00 | -1.56 | -1.56 | -6.25 | -6.25 | -58.59 |
| C_S22/right | -50.78 | -1.56 | -1.56 | -1.56 | -1.56 | -1.56 | -3.91 |
| Q1_S22/left | -30.47 | +0.00 | -1.56 | -1.56 | -1.56 | -3.12 | +11.72 |
| Q1_S22/right | -28.91 | +0.00 | +0.00 | +0.00 | -3.12 | -10.94 | -7.03 |
| Q2_S22/left | -2.34 | +0.00 | -6.25 | -6.25 | -6.25 | -6.25 | -38.28 |
| Q2_S22/right | -38.28 | +0.00 | -6.25 | -6.25 | -6.25 | -6.25 | -13.28 |

历史比较采用率差（百分点）；N128与N64不视为逐episode配对。新的字段与比较均未回写v26 artifact。
