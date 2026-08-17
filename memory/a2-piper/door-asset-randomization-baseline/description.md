---
name: door-asset-randomization-baseline
scope: 当前 Doorman/G1 与 A2_Piper door training asset baseline，以及后续 door asset randomization 的入口事实
status: active
last_updated: 2026-07-03 16:31 HKT
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

## Left/Right Randomization Decision

- 2026-07-03 16:24 HKT - 讨论结论：在当前 `right-only` stage0-2 训练调顺后，加入 `door_open_lr=["left", "right"]` 重新训练是合理的第一阶段 randomization。
- 理由：A2 当前 stage0 staging target 已改为 handle-relative：`grasp_target` 来自 `piper_gripper_handle_frame_transformer.data.target_pos_w[:, 0, :]`，stage0 target 是 `grasp_target.x - a2_stage0_staging_x_offset`，因此 `door_open_lr` 镜像 handle Y 时，stage0 staging 的 Y 也会跟随镜像，不会固定在 right-handle 旧位置。
- Stage1/2 的主要 reward / transition 也已经走 frame transformer：`pregrasp_target_distance` 用 `target_pos_source[:, 1, :]`，`grasp_target_distance`、stage2 close gate、`a2_stage2_handle_center_y`、`a2_stage2_handle_approach_xz` 用 `target_pos_source[:, 0, :]`。这些 target 会随 asset 中的 `grasp_target` 镜像。
- Caveat：A2+Piper 是 single-arm setup，`door_open_lr` left/right 只是 handle-side mirror randomization，不等于已经 runtime 验证 single-arm workspace 对 left/right 都舒服。实现前仍应先跑 GUI/static preview 或 short smoke，检查 base staging、Piper reach、`penalty_face_door`、stage0->1 threshold、stage1 pregrasp 与 stage2 close gate。
- 推荐顺序：先完成并确认 `right-only` stage0-2 稳定，再启用 `door_open_lr=["left", "right"]` retrain；暂时不要同时启用 `door_open_io=["in", "out"]`。

## In/Out Randomization Decision

- 2026-07-03 16:31 HKT - 讨论结论：如果后续做 push/pull style randomization，不建议保持 `door_open_io=["out"]` 然后隐藏地 mirror robot initial pose。更推荐启用 `door_open_io=["out", "in"]`，并把 `door_open_io` 当作 task-side semantic label，驱动 robot-door relative pose 与 through direction。
- 理由：保持 asset metadata `out` 但让部分 env 从另一侧 approach，会造成 config/obs/eval/log/curriculum/checkpoint 语义混乱；episode 到底是 push 还是 pull 无法从 `doorOpenIO` 判断，debug 成本高。
- 当前 `doorOpenIO` 不改变 door asset 物理构造、hinge sign、handle geometry 或 reward routing；真正要 randomize 的是 robot 与 door 的相对侧。可将 `door_open_io` 语义定义为：
  - `out`: current default side，robot 从 `-X` 侧 approach，reset yaw around `0`，stage0 staging 为 `grasp_target.x - offset`，through direction / target 为 `+X`。
  - `in`: mirrored side，robot 从 `+X` 侧 approach，reset yaw around `pi`，stage0 staging 为 `grasp_target.x + offset`，through direction / target 为 `-X`。
- 工程上需要引入 per-env `approach_sign` / `through_sign`，并同步修改 `_reset_root_states()`、`_reward_walk_to_door()`、`_stage_0_to_1_advance_condition()`、`target_root_pos` / `target_root_distance`、stage4/5 through conditions（当前固定 `root_x > 0.0` / `root_x > 1.5`），以及 `penalty_face_door` / heading 类 reward 的方向假设。
- 同时必须真正读取 `door_metadata["doorOpenIO"]` 写入 `self.door_open_io`，并在 obs/log/diagnostics 中保留该 semantic label；不要继续让 `self.door_open_io` 全 0。
- Door hinge / door joint progress reward 可以先保持统一正向：当前 hinge 正角度增长代表 opening progress；in/out mixed 的首要工作是 robot side / stage direction semantics，而不是改 door asset hinge sign。

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
- 2026-07-03 16:24 HKT - `door_open_lr=["left", "right"]` randomization 的推荐 gate：先把当前 `right-only` stage0-2 调到稳定，再做 mixed retrain；验证重点是 base staging 是否随 handle Y 镜像、Piper reachability、stage1 pregrasp route、stage2 close gate/contact 指标。
- 2026-07-03 16:31 HKT - 若实现 `door_open_io=["out", "in"]` randomization，不要 hidden mirror；用 `doorOpenIO` 作为 semantic label，显式 mirror root reset side/yaw、stage0 staging sign、target_root_pos / through direction、stage4/5 success condition，并写入 obs/log/diagnostics。

## DONE Summary

- 2026-07-03 16:16 HKT - 记录当前训练 baseline：origin G1 与 A2 training scene 均固定 `door_open_lr=["right"]`、`door_open_io=["out"]`；当前 repo 没有 push/pull mixed training 证据。明确对 G1/A2 当前 task 可理解为面朝门、右手侧 handle、推门进入；后续 `door_open_io` in/out randomization 是新任务，不是当前 baseline 的简单开关。
- 2026-07-03 16:24 HKT - 记录 left/right randomization discussion：A2 stage0 staging、pregrasp、grasp target/reward plumbing 均由 handle-relative `grasp_target` / frame transformer 驱动，理论上会随 `door_open_lr` 镜像；因此在 `right-only` stage0-2 稳定后，可将 `door_open_lr=["left", "right"]` 作为第一阶段 retrain randomization。该结论不覆盖 `door_open_io` in/out mixed task。
- 2026-07-03 16:31 HKT - 记录 in/out randomization discussion：物理上可以理解为 mirror robot pose，但工程上应启用 `door_open_io=["out", "in"]` 并按该 semantic label mirror robot approach side、yaw、stage0 target、through target/success direction 与 diagnostics；不建议保持 `door_open_io=["out"]` 同时偷偷 mirror robot 初始状态。
