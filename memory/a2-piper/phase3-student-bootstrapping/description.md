---
name: phase3-student-bootstrapping
scope: Doorman paper Phase3 Student Bootstrapping / GRPO fine-tuning finding and future A2+Piper route
status: planned
last_updated: 2026-07-08 15:22 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/phase3-student-bootstrapping/description.md
  - memory/a2-piper/phase3-student-bootstrapping/TODO.md
  - memory/a2-piper/phase3-student-bootstrapping/DONE.md
read_when:
  - 讨论、设计、实现、review 或 debug Doorman paper Phase3 Student Bootstrapping / GRPO fine-tuning route 前
  - 需要判断当前框架是否已有 G1 Phase3 implementation 或 A2 Phase3 可复用基础前
  - Phase2 A2 student distillation 完成后，准备继续做 student self-improvement / RL fine-tuning 前
---

# Phase3 Student Bootstrapping Finding

## Purpose

记录对 Doorman paper 中 Phase3 `Student Bootstrapping` 的理解、当前 DoorDog/A2_Piper 与 origin G1/HOMIE reference worktree 的实现核查结论，以及未来 A2+Piper 若要实现 Phase3 时的 route boundary。

本 entry 是 finding + future implementation reference；当前没有实施 Phase3 code。

## Paper Meaning

Doorman paper 的 Phase3 `Student Bootstrapping` 是 Phase2 `Student Distillation` 之后的 student self-improvement / RL fine-tuning phase。

核心作用：

- Phase2 DAgger student 主要学习 teacher action，但 teacher 有 privileged state，student 只有 RGB + proprioception，因此会留下 partial observability gap。
- Phase3 让 student 用自己的 observation/action distribution 在 simulation 中继续闭环试错，直接优化任务 success / return。
- Paper 采用 GRPO-based fine-tuning：GRPO 是 actor-only PPO variant，不依赖 learned value function，而是从 grouped trajectory scores 中估计 baseline / relative advantage。
- 这个阶段用于改善 long-horizon closed-loop consistency、partial observability 下的 recovery、以及 active perception 行为，例如保持 handle / task-relevant region 在 camera FOV 中。
- Paper reported finding：当 teacher success 已能达到约 `80-90%` 时，Phase2 student 可能停在约 `50-70%`；GRPO bootstrapping 后 student success 提升到约 `80.8-85.8%`，接近 teacher upper bound。

Primary paper refs:

- `https://arxiv.org/html/2512.01061v1`
- `https://openaccess.thecvf.com/content/CVPR2026/html/Xue_Opening_the_Sim-to-Real_Door_for_Humanoid_Pixel-to-Action_Policy_Transfer_CVPR_2026_paper.html`

## Current Framework Finding

2026-07-08 HKT 核查当前 A2 worktree `/home/baoquanc/workspace/DoorDog-A2_Piper` 与 G1/HOMIE reference worktree `/home/baoquanc/workspace/GR00T-VisualSim2Real` 后，结论如下：

- 当前框架有 G1/HOMIE Phase1 Teacher PPO route。
- 当前框架有 G1/HOMIE Phase2 Student DAgger / vision distillation route：
  - `gr00t/rl/config/exp/wbmanip/door_open_homie_dagger-lstm.yaml`
  - `gr00t/rl/config/algo/dagger_vision_distributed.yaml`
  - `gr00t/rl/config/obs/wbmanip/door_open_homie_dagger.yaml`
  - `gr00t/rl/config/trainer/trl_distill_obj_pred_homie_api.yaml`
  - `gr00t/rl/trl/trainer/distill_trainer.py`
  - `gr00t/rl/trl/trainer/distill_trainer_obj_pred.py`
  - `gr00t/rl/trl/trainer/distill_trainer_obj_pred_homie_api.py`
- 当前框架没有完整 G1 Phase3 Student Bootstrapping / GRPO implementation。
- Searches found no dedicated `GRPO` / `grpo` config, trainer, phase3 experiment, bootstrap experiment, actor-only GRPO loss, grouped trajectory baseline or binary-success grouped score workflow.

Important non-Phase3 items:

- `rollout_with_teacher_num_steps`, `teacher_rollout_ratio`, `enforce_teacher_rollout`, `ratio_teacher_rollout` belong to Phase2 distillation teacher-rollout / curriculum mechanics. They are not Phase3 Student Bootstrapping.
- PPO trainer comments about final value `bootstrapping` refer to value-function bootstrap in regular PPO. They are not paper Phase3 `Student Bootstrapping`.
- `policy_distill_ppo` branch exists as a mode hook in trainer code, but there is no complete GRPO / Phase3 workflow around it.

## Future A2+Piper Implication

A2+Piper Phase3 should be treated as a separate future implementation after A2 Phase2 student route exists and produces a usable checkpoint.

Prerequisites:

- A2 Teacher PPO checkpoint is trained and valid.
- A2 Phase2 Student Distillation / DAgger route is implemented and produces a usable RGB student checkpoint.
- A2 student eval route can restore camera, student obs, frozen A2_Base compose and checkpoint sidecar config.

Future A2 Phase3 target should include:

- New A2-specific GRPO / student bootstrapping experiment config.
- A2-specific trainer implementing GRPO-style actor-only update from grouped trajectory returns or binary success scores.
- Student checkpoint initialization from A2 Phase2 output.
- Rollout action compose preserved: student emits A2 high-level action; frozen A2_Base provides leg action; env receives full A2 rollout action.
- Success / return scoring aligned with A2 staged task completion and door-opening metrics.
- No value-model dependency unless deliberately choosing a different algorithm than paper GRPO.
- Domain randomization / camera route consistent with A2 Phase2 vision route.
- Eval comparing Phase2 student vs Phase3 bootstrapped student under the same A2 door tasks.

## Design Guardrails

- Do not call Phase2 teacher rollout curriculum "Phase3".
- Do not treat PPO value bootstrap as paper Student Bootstrapping.
- Do not claim current G1 framework contains Phase3 unless a real GRPO/phase3 trainer + config + workflow is added.
- For A2 adaptation, implement Phase2 student first; Phase3 depends on a student checkpoint and its camera/obs/action contract.
- Follow fail-fast style: checkpoint mismatch, obs/action dim drift, missing camera, missing grouped scores or invalid success signal should raise instead of silently falling back to PPO/DAgger behavior.

## TODO Summary

- 2026-07-08 15:22 HKT - Future implementation TODO: after A2 Phase2 student exists, design and implement full A2+Piper Phase3 Student Bootstrapping / GRPO fine-tuning route with A2 student checkpoint initialization, grouped trajectory scoring, actor-only update, A2_Base action compose, camera/domain randomization compatibility and eval comparison against Phase2 student.

## DONE Summary

- 2026-07-08 15:22 HKT - Recorded finding: paper Phase3 is GRPO-style student self-improvement after DAgger distillation; current A2/G1 framework has Phase2 distillation but no complete G1 Phase3 / GRPO implementation.

## Recommended Next Files To Read

- `memory/a2-piper/phase2-student-distillation-a2-piper/description.md`
- `memory/a2-piper/doorman-door-training-goal/description.md`
- `memory/origin-reference/door-workflows/description.md`
- `gr00t/rl/config/exp/wbmanip/door_open_homie_dagger-lstm.yaml`
- `gr00t/rl/trl/trainer/distill_trainer_obj_pred_homie_api.py`
- `gr00t/rl/trl/trainer/ppo_trainer.py`
- `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py`
