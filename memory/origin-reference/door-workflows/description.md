---
name: door-workflows
scope: DoorPregrasp training, distillation, and evaluation workflow references
status: active
last_updated: 2026-06-11 22:40 HKT
owned_paths:
  - memory/origin-reference/door-workflows/description.md
  - memory/origin-reference/door-workflows/TODO.md
  - memory/origin-reference/door-workflows/DONE.md
read_when:
  - 修改或运行 door task、teacher PPO、student DAgger vision、eval workflow 前
  - 需要确认 train/eval entrypoints、Hydra config、DoorPregrasp 或 HOMIE model routing 时
---

## Purpose

记录 door opening workflow 的 origin reference map。这里不记录 future migration 或 training progress，只标出当前 source-of-truth paths、配置关系与 known prerequisites。

Workflow facts:

- Teacher workflow: PPO / privileged state observations，top README 指向 `+exp=wbmanip/door_open_homie_lstm`。
- Student workflow: DAgger vision distillation，top README 指向 `+exp=wbmanip/door_open_homie_dagger-lstm`。
- Eval workflow: `gr00t/rl/eval_agent_trl.py` with eval config/checkpoint overrides。
- Door task: `DoorPregrasp` lives in `gr00t/rl/envs/door/door_open_homie.py`。
- Train entrypoint: `gr00t/rl/train_agent_trl.py`。
- Eval entrypoint: `gr00t/rl/eval_agent_trl.py`。
- HOMIE lower-body model paths are config/runtime prerequisites; local required `model_walk.pt` and `model_stand.pt` are indexed in assets memory.
- Student training prerequisite: `teacher_actor_path` in `gr00t/rl/config/exp/wbmanip/door_open_homie_dagger-lstm.yaml` must point to a valid trained teacher checkpoint before student training.
- 2026-06-11 22:40 HKT verified smoke fact: 5-iteration teacher PPO smoke training passed with `+exp=wbmanip/door_open_homie_lstm`, `num_envs=1`, `algo.trl.num_total_batches=5`, and small rollout/epoch/minibatch overrides. Output run dir exists at `logs_rl/g1_open_door_homie/door_open_homie_lstm_smoke5-20260611_223318/`, with checkpoint `logs_rl/g1_open_door_homie/door_open_homie_lstm_smoke5-20260611_223318/model_step_000005.pt` plus `config.yaml`, `.hydra/train.log`, and `.hydra/train_agent_trl.log`.
- This smoke validates the origin runtime chain enough for smoke coverage: AppLauncher/Isaac Sim startup, DoorPregrasp env creation/reset, HOMIE model load, LAFAN-G1 reset data, PPO rollout/update/save. Do not claim policy quality from this checkpoint.

## When Codex/AI Should Read This Entry

- 调整 door task reward、observation、action、reset、trainer 或 Hydra override 前。
- 需要解释 teacher -> student dependency 或 `teacher_actor_path` failure。
- 需要找到 DoorPregrasp train/eval code path。

## Source Paths

- current top workflow docs: `README.md`
- legacy/stale RL README marker: `gr00t/rl/README.MD`
- teacher experiment config: `gr00t/rl/config/exp/wbmanip/door_open_homie_lstm.yaml`
- student experiment config: `gr00t/rl/config/exp/wbmanip/door_open_homie_dagger-lstm.yaml`
- PPO config: `gr00t/rl/config/algo/ppo.yaml`, `gr00t/rl/config/algo/trl/ppo.yaml`
- DAgger vision config: `gr00t/rl/config/algo/dagger_vision_distributed.yaml`
- env config: `gr00t/rl/config/env/door_open_homie.yaml`
- obs config: `gr00t/rl/config/obs/wbmanip/door_open_homie.yaml`, `gr00t/rl/config/obs/wbmanip/door_open_homie_dagger.yaml`
- reward config: `gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- trainers: `gr00t/rl/config/trainer/trl_homie_api.yaml`, `gr00t/rl/config/trainer/trl_distill_obj_pred_homie_api.yaml`
- task source: `gr00t/rl/envs/door/door_open_homie.py`, `gr00t/rl/envs/door/reset_from_dataset.py`
- train/eval entrypoints: `gr00t/rl/train_agent_trl.py`, `gr00t/rl/eval_agent_trl.py`
- HOMIE trainer modules: `gr00t/rl/trl/trainer/ppo_trainer_homie_api.py`, `gr00t/rl/trl/trainer/distill_trainer_obj_pred_homie_api.py`

## TODO Summary

- 2026-06-11 22:40 HKT - 当 DoorPregrasp、env/assets/config/runtime、train/eval entrypoints、Hydra config names、HOMIE model routing 或 `teacher_actor_path` semantics 改变时，刷新 workflow map 并 rerun 5-iteration teacher PPO smoke；eval 如需可使用 `logs_rl/g1_open_door_homie/door_open_homie_lstm_smoke5-20260611_223318/model_step_000005.pt`，但该 checkpoint quality is smoke-only。

## DONE Summary

- 2026-06-11 21:53 HKT - 初始化 door workflow origin reference entry，记录 teacher PPO、student DAgger vision、eval、DoorPregrasp、HOMIE 与 `teacher_actor_path` prerequisite。
- 2026-06-11 22:40 HKT - 记录 verified 5-iteration teacher PPO smoke passed，生成 `model_step_000005.pt`，并明确该结果仅验证 origin runtime smoke chain，不代表 policy quality。

## Recommended Next Files To Read

- `memory/origin-reference/assets-and-data/description.md`
- `memory/origin-reference/runtime-environment/description.md`
- `README.md`
- `gr00t/rl/config/exp/wbmanip/door_open_homie_dagger-lstm.yaml`
