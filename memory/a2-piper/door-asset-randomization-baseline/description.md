---
name: door-asset-randomization-baseline
scope: 当前 Doorman/G1 与 A2_Piper door training asset baseline，以及后续 door asset randomization 的入口事实
status: active
last_updated: 2026-07-03 16:16 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/door-asset-randomization-baseline/description.md
  - memory/a2-piper/door-asset-randomization-baseline/TODO.md
  - memory/a2-piper/door-asset-randomization-baseline/DONE.md
read_when:
  - 开始 door asset randomization、door_open_lr / door_open_io randomization、door spawn config 或 training distribution 改动前
  - 需要判断当前 Doorman/G1 origin 是否已经覆盖 push/pull 或 left/right 多门形态时
  - 需要解释 project page 的 pull-door demo 与当前 repo training objective 的差异时
---

# Door Asset Randomization Baseline

## Purpose

记录当前 repo 中 Doorman/G1 origin 与 A2_Piper door training 的实际 door asset baseline，供后续做 door asset randomization 时快速路由，不需要重新从 door asset 源码、scenario config、reward 和日志目录开始调研。

## 当前结论

- 当前训练 scene baseline 是固定 `right-hinge + out-opening`，不是 left/right/in/out mixed distribution。
- Source-of-truth config:
  - A2 当前 worktree: `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` 中 `door_open_lr=["right"]`、`door_open_io=["out"]`。
  - Doorman/G1 origin reference worktree `/home/baoquanc/workspace/GR00T-VisualSim2Real` 的同名文件配置一致。
  - 官方 GitHub `doorman` branch raw file 也与本地一致。
- 对 G1 / 当前 task 坐标而言，robot 从 door 的 `-X` 侧走向门并向 `+X` 方向穿门；`door_open_lr="right"` 在 door geometry 中把 hinge 放在 `+Y` 侧、handle 放在 `-Y` 侧。机器人面朝门时，handle 落在 robot right-hand side。
- 当前训练目标可以简化理解为：面朝门，右手侧 handle，推开门后向 `+X` 进入。
- 当前 repo 不应被视为已经掌握 push/pull mixed door-opening。Project page / paper 可能展示或声明 pull-door demo，但当前公开/本地 code path 没有对应训练配置、reward routing、obs 读取或本地训练产物证据。

## doorOpenIO 与 Randomization Caveat

- `DoorSpawnerCfg` 和 offline generation scripts 支持 `door_open_io=["in", "out"]`、`door_open_lr=["left", "right"]`，所以存在 asset generation scaffold。
- 但当前 training scene 没有启用该 scaffold；`scenario_cfg/isaacsim.py` 直接固定为 `door_open_io=["out"]`。
- `doorOpenIO` 在 `door.py` 中只采样/写入 metadata，不参与 hinge joint axis、joint limit、panel orientation、handle geometry 或 spawn yaw。
- Origin/A2 env 中 `self.door_open_io` 被初始化并放进 privileged obs stack，但当前代码没有把 `door_metadata["doorOpenIO"]` 赋值给 `self.door_open_io`。因此即使 asset metadata 有 in/out，policy 侧当前也没有实际可用的 in/out signal。
- Stage3/open reward 主要是 `push_door_handle` / `push_door_hinge` 的 door joint progress；origin G1 的 `push_door_force` 是 world-x pushing force，A2 path 当前 disabled/zero。未来如果要训练真正 push/pull mixed distribution，不能只把 `door_open_io` list 改成 `["in", "out"]`。

## 对后续 Door Asset Randomization 的影响

未来做 randomization 前，至少需要显式决定以下边界：

- 只 randomize geometry/dynamics/material while keeping `right-hinge + out-opening`：相对低风险，重点检查 handle/pregrasp/grasp target 是否随 geometry 正确更新。
- randomize `door_open_lr` left/right：需要检查 hand/arm selection、handle side、gripper target frame、stage1/2 grasp routing、policy observation 中的 side signal，以及 A2 Piper single-arm 是否能覆盖 left-hinge/right-hinge distribution。
- randomize `door_open_io` in/out：这是新任务，不是当前 baseline 的简单 domain randomization。需要定义真正的 in/out physical semantics、robot spawn/approach side、reward sign/force projection、stage4/5 through-door direction 与 privileged/actor obs signal。
- 若启用 `push_door_force` 或设计 A2-specific force reward，必须用 door-frame 或 source-frame projection，不要沿用 origin 的 world-x pushing force。

## Source Files / Evidence

- `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`
- `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`
- `gr00t/rl/isaac_utils/playground/env_rand/door.py`
- `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/isaac_utils/playground/env_rand/door.py`
- `gr00t/rl/envs/door/door_open_a2_base.py`
- `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`
- `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- `gr00t/rl/scripts/generate_door_assets.py`
- `gr00t/rl/scripts/generate_1000_doors.sh`
- `gr00t/rl/scripts/README.md`
- `logs_rl/` and `logs_eval/` grep for `door_open_io` / `doorOpenIO` overrides found no training/eval override away from current scene config.

## Related Memory

- `memory/a2-piper/door-asset-openio-sign/description.md`: lower-level核查 `doorOpenIO` 对 door construction、hinge sign、reward routing 的影响。
- `memory/a2-piper/reward-implementation-goal/description.md`: stage3+ reward / transition adaptation 状态。

## TODO Summary

- 2026-07-03 16:16 HKT - 后续 door asset randomization 方案设计前，先决定 randomization scope：geometry/dynamics/material only、left/right handedness、还是真正 in/out push/pull mixed task；不同 scope 对 env/reward/obs/transition 的施工量不同。
- 2026-07-03 16:16 HKT - 若计划启用 `door_open_lr` 或 `door_open_io` randomization，必须先做 static plan + user approval，再实现并用 GUI/runtime smoke 验证 spawn pose、handle side、grasp target、stage transitions 与 reward direction。

## DONE Summary

- 2026-07-03 16:16 HKT - 记录当前训练 baseline：origin G1 与 A2 training scene 均固定 `door_open_lr=["right"]`、`door_open_io=["out"]`；当前 repo 没有 push/pull mixed training 证据。明确对 G1/A2 当前 task 可理解为面朝门、右手侧 handle、推门进入；后续 `door_open_io` in/out randomization 是新任务，不是当前 baseline 的简单开关。
