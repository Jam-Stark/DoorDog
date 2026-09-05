# base_v27 q0_dev readout

2026-09-05 19:41 HKT

状态：`V27_COMPLETE`；step=0；exact N=128。

计数顺序：D / S3+ / S4+ / open_hold / S5+ / complete / clean_complete。

| Cell | 层 | 侧 | 计数 | 握门穿过 | 松手后身体力 p95 (N) | 首次 crossing hinge p50 (rad) | 集长 p50 | arm_j4 限位占比 | 终止原因 | integrity |
|---|---|---|---|---:|---:|---:|---:|---:|---|---:|
| C_S2 | DEV | left | 113/128/128/128/128/128/75 | 0 | 729.034912109375 | 2.1003570556640625 | 804.0 | 0.0037984421578997982 | {"complete": 128} | 0 |
| C_S2 | DEV | right | 109/128/128/128/128/128/69 | 128 | 0.0 | 1.0913684368133545 | 490.0 | 0.0 | {"complete": 128} | 0 |
| W_S2 | DEV | left | 120/128/125/125/125/125/100 | 0 | 745.18603515625 | 2.079511880874634 | 576.0 | 0.02621231979030144 | {"complete": 125, "stage_overtime": 3} | 0 |
| W_S2 | DEV | right | 104/128/127/127/127/127/112 | 127 | 0.0 | 1.2179604768753052 | 434.0 | 0.0 | {"complete": 127, "stage_overtime": 1} | 0 |
| K_S2 | DEV | left | 106/127/127/127/127/122/71 | 126 | 961.720947265625 | 1.1669213771820068 | 450.0 | 0.0 | {"upper_dof_overspeed": 6, "complete": 122} | 0 |
| K_S2 | DEV | right | 92/126/125/124/124/122/119 | 120 | 0.0 | 1.2672723531723022 | 420.0 | 0.0 | {"upper_dof_overspeed": 5, "stage_overtime": 1, "complete": 122} | 0 |

## 配对差与反向读数

L1_S32 对 L0_S31、SK 对相同序号 SC 使用预注册配对；PPO seed 数值不同，不宣称同随机轨迹的因果对照。

```json
{
  "paired_deltas": {},
  "negative_deltas": []
}
```

## Typed outcomes

```json
{
  "qualification": {
    "outcome": "NO_QUALIFIED_CANDIDATE",
    "selected_candidate": null
  }
}
```

## 质量失败成分、K 与恢复 telemetry

```json
{
  "quality": {
    "C_S2/DEV/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 53,
      "complete_without_crossing_measurement": 0
    },
    "C_S2/DEV/right": {
      "complete_with_crossing_hinge_below_threshold": 53,
      "complete_with_body_contact_above_5N": 6,
      "complete_without_crossing_measurement": 0
    },
    "W_S2/DEV/left": {
      "complete_with_crossing_hinge_below_threshold": 0,
      "complete_with_body_contact_above_5N": 25,
      "complete_without_crossing_measurement": 0
    },
    "W_S2/DEV/right": {
      "complete_with_crossing_hinge_below_threshold": 15,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    },
    "K_S2/DEV/left": {
      "complete_with_crossing_hinge_below_threshold": 21,
      "complete_with_body_contact_above_5N": 35,
      "complete_without_crossing_measurement": 0
    },
    "K_S2/DEV/right": {
      "complete_with_crossing_hinge_below_threshold": 3,
      "complete_with_body_contact_above_5N": 0,
      "complete_without_crossing_measurement": 0
    }
  },
  "k": {
    "K_S2": {
      "through_batch": 0,
      "max_common_step": 0,
      "scale_min": 1.0,
      "first_update_below_0.95": null,
      "share_of_updates_below_0.5": 0.0,
      "reversal_count": 0,
      "skipped_updates": 1,
      "trace_rows": 1
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
      "state": "RUNNING",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_q0_render_gpu0/RUN_RECEIPT.json"
    },
    "v27_eval_q0_render_gpu1": {
      "state": "RUNNING",
      "returncode": 1,
      "path": "/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_eval_q0_render_gpu1/RUN_RECEIPT.json"
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
      "state": "RUNNING",
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
    "2, 13702 MiB, 49140 MiB, 48 %",
    "3, 12882 MiB, 49140 MiB, 15 %",
    "4, 12758 MiB, 49140 MiB, 17 %",
    "5, 13148 MiB, 49140 MiB, 38 %",
    "6, 12892 MiB, 49140 MiB, 16 %",
    "7, 12892 MiB, 49140 MiB, 29 %"
  ],
  "processes": [
    "1273739 2692622       57:25 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s21/run.sh",
    "1273741 1273739       57:25 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 2 --cell C_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21",
    "1273833 1273741       57:24 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S21",
    "1273882 2692622       57:23 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s21/run.sh",
    "1273884 1273882       57:23 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 3 --cell Q1_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21",
    "1274036 1273884       57:22 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S21",
    "1274079 2692622       57:22 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s21/run.sh",
    "1274084 1274079       57:22 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 4 --cell Q2_S21 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21",
    "1274172 1274084       57:21 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S21 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S21/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S21",
    "1274215 2692622       57:20 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_c_s22/run.sh",
    "1274216 1274215       57:20 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 5 --cell C_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22",
    "1274238 1274216       57:19 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_C_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/C_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_C_S22",
    "1274257 2692622       57:19 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q1_s22/run.sh",
    "1274259 1274257       57:19 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 6 --cell Q1_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22",
    "1274299 1274259       57:18 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q1_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q1_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q1_S22",
    "1274321 2692622       57:17 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_train_q2_s22/run.sh",
    "1274323 1274321       57:17 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_run_cell.py train --gpu 7 --cell Q2_S22 --output /home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22",
    "1274431 1274323       57:16 /home/baoquanc/anaconda3/envs/isaaclab/bin/python -B -m gr00t.rl.train_agent_trl +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/base_v27_Q2_S22 headless=true use_wandb=false simulator.config.render_results=false simulator.config.cameras.enable_cameras=false experiment_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22 output_dir=/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/Q2_S22/output project_name=base_v27_bilateral_hardening experiment_name=V27_Q2_S22",
    "1294957 2692622       40:15 bash /home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/runs/v27_watch_a_r2/run.sh",
    "1294960 1294957       40:15 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/v27_watch_wave.py --wave A",
    "1323746 3155584       00:01 /bin/bash -c /home/baoquanc/anaconda3/envs/isaaclab/bin/python - <<'PY' import sys sys.path.insert(0,'scriptsFORhuman/v27') from v27_contract import RUNTIME,EVAL,read_json,write_json,input_checkpoint from v27_orchestrate import eval_manifest,eval_launch old=read_json(EVAL/'q0_dev/reducer.json');k=read_json(EVAL/'q0_k_cpu_readjudication/reducer.json');combined=read_json(EVAL/'q0_dev_cpu_adjudicated/reducer.json') combined['lanes']=[lane for lane in old['lanes'] if lane['cell']!='K_S2']+k['lanes'] assert all(lane['status']=='COMPLETE' for lane in combined['lanes']) write_json(EVAL/'q0_dev_cpu_adjudicated/reducer.json',combined,replace=True) p=eval_manifest('q0_render_k_after_cpu',{'K_S2':input_checkpoint('K_S2')},['DEV'],3,270001,extra_overrides={'simulator.config.render_results':True}) eval_launch(p) PY",
    "1323764 1323753       00:01 /home/baoquanc/anaconda3/envs/isaaclab/bin/python /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_p0_assets.py --output /home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/p0_assets/eval_q0_render_k_after_cpu_gpu0.json",
    "1323768 3155584       00:00 /home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/v27/v27_readout.py --reducer logs_eval/base_v27/v27_bilateral_hardening_20260905/q0_dev_cpu_adjudicated/reducer.json --manifest scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/q0_dev.json --train-root logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train --output scriptsFORhuman/v27/a2_piper_base_v27_q0_dev_readout_20260905.md"
  ]
}
```

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v27/v27_bilateral_hardening_20260905/q0_dev_cpu_adjudicated/reducer.json)；[eval manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/eval_manifests/q0_dev.json)。

证据：真实模拟评估/注册条件下的计数；不构成硬件或部署证据。

## v27.0 收口与明确的失败成分

最终 `NO_QUALIFIED_CANDIDATE`，CONF `NOT_RUN`；三候选均未同时满足两侧门槛。

C LEFT 的 53 个不干净 complete 都由 Stage3 起身体接触力 >5 N 导致；C RIGHT 有 53 集首次 crossing hinge <1.0472，另有 6 集身体接触 >5 N。W LEFT 25 集身体接触 >5 N，RIGHT 15 集 crossing hinge 不足。K LEFT 的 21 集角度不足与 35 集身体接触存在重叠；RIGHT 只有 3 集角度不足，但两侧超速终止分别 6/5 >4。

K 初版 reducer 的覆盖断言错误排除了 LEFT env119（Stage1 超速终止）和 RIGHT env107（Stage0 overtime）；Owner 明确授权后只做了 CPU 重判。原 INVALID 保留，训练/DEV rollout 重跑数为 0。后续 reducer 按实际 Stage2–5 trace 覆盖范围读取，早期终止仍计入 exact N。

QA 为每候选每侧 env0/1/2 的首回合，共 18 episodes / 54 videos；已解码并抽查 18 个主视角视频的 72 帧。C/W 渲染先完成；K 因临时停格尚未启动的渲染在 CPU 重判后补齐，没有重跑已有渲染。主视角穿门后存在门板遮挡，不用这些帧判定接触力或修改资格结论。

同历史 source 的差按比例报告，避免把 exact64 与 exact128 计数直接相减。K 的训练 trace 是只读引用的 v26-8 历史谱系；本次评估 curriculum/driver 均关闭。

```json
{
  "same_lineage_W_K_minus_C_counts": {
    "W": {
      "left": {
        "D": 7,
        "S3+": 0,
        "S4+": -3,
        "open_hold": -3,
        "S5+": -3,
        "complete": -3,
        "clean_complete": 25
      },
      "right": {
        "D": -5,
        "S3+": 0,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -1,
        "clean_complete": 43
      }
    },
    "K": {
      "left": {
        "D": -7,
        "S3+": -1,
        "S4+": -1,
        "open_hold": -1,
        "S5+": -1,
        "complete": -6,
        "clean_complete": -4
      },
      "right": {
        "D": -17,
        "S3+": -2,
        "S4+": -3,
        "open_hold": -4,
        "S5+": -4,
        "complete": -6,
        "clean_complete": 50
      }
    }
  },
  "all_historical_rate_deltas_pp": {
    "C_S2": {
      "left": {
        "D": -0.78125,
        "S3+": 0.0,
        "S4+": 0.0,
        "open_hold": 0.0,
        "S5+": 0.0,
        "complete": 0.0
      },
      "right": {
        "D": 0.78125,
        "S3+": 0.0,
        "S4+": 0.0,
        "open_hold": 0.0,
        "S5+": 0.0,
        "complete": 0.0
      }
    },
    "W_S2": {
      "left": {
        "D": -4.6875,
        "S3+": 0.0,
        "S4+": -2.34375,
        "open_hold": -2.34375,
        "S5+": -2.34375,
        "complete": -2.34375
      },
      "right": {
        "D": 3.125,
        "S3+": 0.0,
        "S4+": -0.78125,
        "open_hold": -0.78125,
        "S5+": -0.78125,
        "complete": -0.78125
      }
    },
    "K_S2": {
      "left": {
        "D": 1.5625,
        "S3+": -0.78125,
        "S4+": -0.78125,
        "open_hold": -0.78125,
        "S5+": 0.78125,
        "complete": 1.5625
      },
      "right": {
        "D": 1.5625,
        "S3+": 0.0,
        "S4+": -0.78125,
        "open_hold": -1.5625,
        "S5+": -1.5625,
        "complete": -3.125
      }
    }
  }
}
```

[候选 manifest v1](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_teacher_candidate_manifest_20260905.json)；[render QA](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/q0_render_qa.json)。
