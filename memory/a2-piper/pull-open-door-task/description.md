---
name: pull-open-door-task
scope: A2+Piper pull-only door task 的静态方向 contract、独立 pipeline 与 runtime verification 边界
status: active
last_updated: 2026-07-14 00:43 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/pull-open-door-task/description.md
  - memory/a2-piper/pull-open-door-task/TODO.md
  - memory/a2-piper/pull-open-door-task/DONE.md
read_when:
  - 开始 pull-only door scenario、env、experiment、reward/observation interface 或 direction contract 改动前
  - 需要区分 pull task 的 static/no-sim evidence 与尚未完成的 IsaacSim、PPO 或 eval 验证时
---

# Pull-Open-Door Task

## Purpose

本 entry 保存 A2+Piper pull-only door task 的可复用静态事实。它不宣称 scenario 已在 IsaacSim 中成功构造、Piper 已可达/可抓取，也不代表 PPO 或 eval 已完成。

## Task / Worktree Boundary

- 实施 branch 是 `codex/a2-piper-pull-door`，linked worktree 是 `/home/baoquanc/workspace/DoorDog-A2_Piper_pull`，base SHA 为 `496ea4fd2ef88de23995458badff5cb78e6a3701`。
- pull route 使用独立 identity：task `door_pull`、env `door_pull_a2_base`、experiment `door_pull_a2_base_lstm`、project `a2_piper_pull_door_a2_base`，以及 `gr00t/rl/data/tasks/door_pull/` scenario package；不能把其 artifact 与 push route 混用。
- 此 task 复用 shared A2 trainer、reward YAML 与 observation interface；其独立性来自 explicit pull task mode、scenario metadata 和 pipeline namespace，不是 fork 一套 trainer/reward/obs 实现。
- 该 entry 只记录 pull task。通用 workspace routing entry 由 Main 单独机械同步，不能据此修改 `worktree-routing`。

## Static Direction Contract

- `doorOpenIO` 使用 authored sign：`out`/push 为 `-1`，沿 door local `-X` approach；`in`/pull 为 `+1`，沿 door local `+X` approach；`through = -approach`。world direction 由 door root 的 high-level pose 旋转出来，不能回退为 fixed world-X。
- door hinge 的 opening progress 统一保持 positive：hinge angle 朝正方向增长表示开门；pull route 不为此 sign flip。
- pull pregrasp 是 configured static contract：offset `(+0.10, 0, 0)`，WXYZ rotation `(0.5, 0.5, -0.5, -0.5)`。它不是 Piper pregrasp/grasp reachability、collision 或 contact 的 runtime proof。
- pull stage4 的 root-distance reward 保持 approach-side clearance target，满足 clearance predicate 后才进入 stage5；stage5 reward 在 door-open 且 handle-up 时持续 active，不以 transit/clearance geometry 重新 gate。完成条件是 signed `through` progress `> 1.5`。

## Evidence Boundary

- Candidate `b45cf375076b4d671173488f07c985dc1831c1c309f467ccfd99ce7cdd633c32` 的 static implementation 及其 no-sim checks 已完成；candidate diff/hash immutability、Hydra push/pull compose 和 81 tests 均是 supplied QA evidence。
- `CODE_QUALITY` 与 IsaacLab static review 为 PASS；`runtime_qa` 为 `NO_SIM PASS`。这些 verdict 都不等同于 runtime PASS，IsaacSim/physical/training evidence 仍见 TODO。

## Reproducible Static Command

在 pull worktree 中可用 worktree-local import path 和 IsaacLab conda Python 复跑方向 contract 的 targeted test：

```bash
PYTHONPATH=/home/baoquanc/workspace/DoorDog-A2_Piper_pull \
  /home/baoquanc/anaconda3/envs/isaaclab/bin/python -m pytest \
  gr00t/rl/tests/test_a2_pull_direction_contract.py
```

## TODO Summary

- 2026-07-14 00:43 HKT - runtime 验证仍由用户拥有：scenario import/env construction、right/in metadata、`+X` reset 与 yaw≈pi、pregrasp/grasp reachability/collision/contact、positive hinge opening、stage4 clearance `0.30` adequacy、stage5 signed `-X` completion，以及后续 PPO/eval（如需要）。

## DONE Summary

- 2026-07-14 00:43 HKT - pull-only static implementation/pipeline 已通过 candidate-bound `CODE_QUALITY PASS`、IsaacLab static PASS 和 `NO_SIM PASS`；81 tests、Hydra push/pull compose、candidate diff/hash immutability 已由 QA evidence 覆盖，未执行 runtime simulation。
