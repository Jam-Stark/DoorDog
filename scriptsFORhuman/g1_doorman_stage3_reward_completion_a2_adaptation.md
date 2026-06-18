# G1 Doorman Stage3 Reward / Completion A2 Adaptation Checklist

本文给 human 快速看懂：A2+Piper 进入 `STAGE_OPEN = 3` 以后，原版 G1 到底在奖励什么、stage3 怎么进入 stage4、当前 A2 哪些可以先保留、哪些必须重新设计。

一句话结论：stage3/open 的主目标不是“再判断有没有抓住”，而是在已进入 grasp/open routing 后，继续保持 grasp，同时转动 handle、推动 hinge，让 door hinge 超过 `0.174533 rad` 进入 stage4/swing。当前 A2 的 stage3 框架和部分 door-joint progress reward 可作为 baseline；`push_door_force` 不能照搬 G1 hand world-X force，当前保持 disabled/TODO design。

## 优先级清单

- DONE 2026-06-17 22:34 HKT: stage2 reward completion / A2 adaptation 已三方确认 `static PASS`，`_stage_2_to_3_advance_condition()` 保持 `completion | door_open_bypass`。
- DONE 2026-06-17 22:41 HKT: Ava 确认 G1 stage3 是 `STAGE_OPEN = 3`；stage3 reward condition 是“stage2->3 已满足 + base stillness”。
- P0: 先让 user 审核本 checklist，确认 stage3/open 的 adaptation 边界。
- P0: 下一轮优先审核/实现 `push_door_handle`、`push_door_hinge`、`push_door_force` 的 A2 状态。
- P1: bounded smoke 仍要统计 stage2->3 route、stage3 dwell、handle joint progress、hinge progress、grasp hold、door-open bypass ratio。

## Source of Truth

- Origin env: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- Origin reward config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- Current A2 env: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`
- Current A2 reward config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`
- Stage2 checklist: `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/g1_doorman_stage2_reward_completion_a2_adaptation.md`

## 状态词约定

| 状态 | 含义 |
|---|---|
| `PASS carrier` | stage/routing 条件可沿用，但不代表 open 行为已经 smoke 通过。 |
| `PASS baseline` | 第一版可以保留训练，后续看 reward magnitude、方向和副作用。 |
| `PASS reward metric` | reward 侧 metric 已有 A2 实现，可继续作为 shaping。 |
| `PASS disabled` | 当前 A2 明确不启用，或者启用会引入错误语义。 |
| `TODO design` | 需要单独设计 A2/Piper 语义，不能直接照搬 G1。 |
| `TODO smoke` | 静态代码可以先过，但 runtime 需要验证。 |

## Stage3 Boundary Facts

| 项目 | G1/HOMIE 原始语义 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| Stage name | `STAGE_OPEN = 3`，进入后开始转 handle / 开门 | stage index 沿用 | PASS carrier | 不要把 stage3 再当成 grasp completion；stage2 已负责抓住。 |
| Stage3 reward condition | `_stage_3_reward_condition()` = `_stage_2_to_3_advance_condition() & _stage_2_reward_condition()` | A2 同样复用 stage2->3 routing + base stillness | PASS carrier | 前提是 stage2->3 真实走 completion，而不是主要走 door-open bypass；需要 smoke 统计。 |
| Stage3 advance | `_stage_3_to_4_advance_condition()` 要求 door hinge `joint_pos[:, 0] > 0.174533` | A2 当前同 G1 | PASS baseline | 这是 door progress，不是 robot-specific。第一版可保留；后续看是否过早进入 swing。 |
| Stage3 complete function | G1 没有单独 `_stage_3_to_complete_condition()`；stage3 到 stage4 走 advance condition | A2 同样没有单独 stage3 complete | PASS carrier | 文档里说 completion 时，指 stage3->4 advance，不是 final task complete。 |
| Base stillness | stage3 reward condition 继续要求 base command norm `<=0.1` | A2 沿用 `get_physical_homie_commands()[:, :3]` | PASS baseline | 可能压制 A2 开门时微调站姿；smoke 看是否过强。 |

## Stage3 Reward Term Mapping

| Reward term | G1 scale / stage | G1 大白话 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---:|---|---|---|---|
| `stage` | `+1.0`, all stages | 当前 stage condition 满足时给 flow reward | A2 沿用 `StagedTaskBase` | PASS carrier | 只说明 stage3 条件成立，不代表门真正打开。 |
| `push_door_handle` | `+6.0`, stage `[3]` | 奖励 handle joint velocity 和 handle joint position，也就是把门把手往下压/转动 | A2 scale `6.0`，函数仍读 door articulation `joint_vel[:,1]` / `joint_pos[:,1]` | PASS baseline / verify joint semantics | 先确认 A2 asset 的 handle joint index `1` 和方向仍对；如果方向/范围不同再改。 |
| `push_door_hinge` | `+6.0`, stages `[3,4]` | 奖励 door hinge 速度和 hinge 打开角度 | A2 scale `6.0`，函数仍读 door articulation `joint_vel[:,0]` / `joint_pos[:,0]` | PASS baseline / smoke magnitude | Door hinge progress 是 robot-agnostic；但 `joint_vel * 10` 的量级要 smoke 看是否过强。 |
| `push_door_force` | `+0.3`, stage `[3]` | G1 用选中 hand 对 handle 的 contact force world `x` 分量，奖励推门方向 force | A2 scale `0.0`，A2 path 返回 zeros | PASS disabled now / TODO design | 不能照搬 G1 hand/world-X force。A2 需要基于 Piper gripper/handle contact、source frame 或 door-frame force 重新设计。 |
| `grasp` | `+0.2`, stages `[1,2,3,4]` | 开门时继续保持 hand-handle contact force | A2 已是 handle-specific `arm_body7/arm_body8` source local `+Y` squeeze reward | PASS reward metric | stage3 继续保留，用来防止开门时松手；smoke 看 off-axis/contact spike。 |
| `grasp_target_distance` | `+3.0`, stages `[2,3,4]` | 让 selected palm 继续贴近 grasp target | A2 已改为 Piper TCP/source 到 handle target distance | PASS reward metric | stage3 继续保留，避免开门时 TCP 离 handle 太远。 |
| `gripper_handle_orientation` | G1 `hand_handle_orientation: +3.0`, stages `[1,2,3,4]` | 抓住后手和 handle 的方向也要保持合理 | A2 replacement 已启用 scale `3.0` | PASS reward metric / smoke | 当前 helper 使用 target index `1` 的 orientation；pregrasp offset rotation 是 identity，第一版可保留。后续如开门姿态不自然，再讨论 handle-frame orientation。 |
| `grasp_finger_dof_pos_l1` | `+3.0`, stages `[2,3,4]` | G1 手指保持 close grasp pose | A2 scale `0.0`，A2 path zeros | PASS disabled / deferred | 当前 binary gripper primitive 不做 close-target reward；未来等 continuous aperture primitive 做 aperture/contact-aware reward。 |
| `penalty_not_standing_still` | `-15.0`, stages `[1,2,3]` | 抓/开时 base 不要乱走 | A2 沿用 base command norm penalty | PASS baseline | stage3 可能需要 A2 微调身体位置；smoke 看是否阻碍开门。 |
| `penalty_unused_dof_deviation_l1` | `-1.0`, stages `[1,2,3,4]` | G1 未使用的另一只手不要乱动 | A2 scale `0.0` | PASS disabled | Piper 是 one-arm，不启用。 |
| `penalty_face_door` | `-1.0`, stages `[0,1,2,5]` | G1 stage3 不启用该 term | A2 stage3 同样不受该 term 直接影响 | PASS baseline | 仍要看 stage2 前的 facing 约束是否让 A2 站姿不利于开门。 |
| Door frame/panel contact penalties | `-0.1`, always-on | 撞门框/门板要罚 | A2 已有 sensors 和 scale | PASS baseline | stage3 开门时最容易误碰门板/门框，smoke 要看 false positive 与 expected gripper-handle contact 是否冲突。 |

## Stage3 Open Design Checklist

| 设计输入 | 当前可用 source | 为什么需要 | A2适配状态 | 第一版建议 |
|---|---|---|---|---|
| Handle joint progress | `door.data.joint_pos[:, 1]`, `door.data.joint_vel[:, 1]` | stage3 先要转/压 handle，G1 `push_door_handle` 直接奖励这个 | PASS baseline / verify | 保留 scale `6.0`，先确认 joint index/range/direction；如方向反了再 fail-fast 调整。 |
| Hinge progress | `door.data.joint_pos[:, 0]`, `door.data.joint_vel[:, 0]` | stage3->4 advance 依赖 hinge `>0.174533` | PASS baseline | 保留 threshold 和 `push_door_hinge` 第一版，smoke 看是否过早/过晚。 |
| Grasp hold | A2 `_stage_2_to_complete_condition()` 和 `_reward_grasp()` contact source | 开门时不能松开 handle | PASS reward metric; condition reuse via stage3 reward condition | 第一版不改 `_stage_3_reward_condition()`；如果 smoke 发现靠 door-open bypass 进入 stage3 后没抓住，再讨论更严格 gate。 |
| Push force | A2 `a2_gripper_handle_contact_sensor` filtered forces, source frame / door frame | 需要知道 Piper 是否真的在有效开门方向施力 | TODO design | 暂不启用 `push_door_force`。后续设计应避免 world-X sign，优先考虑 door hinge axis/handle frame/source frame 的投影。 |
| Base stillness | `get_physical_homie_commands()[:, :3]` | G1 开门时 base 不走动 | PASS baseline / smoke | 保留，但监控是否压制 A2 必要微调。 |
| Door contact safety | door frame/panel contact sensors | 开门动作可能撞门板/门框 | PASS baseline / smoke | 统计 frame/panel penalty frequency，避免把合理接触误罚成失败。 |

## 不要做的事

| 不要做 | 原因 |
|---|---|
| 不要把 `push_door_force` 直接从 G1 搬到 A2 | G1 用 selected hand contact force 的 world `x` 分量；Piper 姿态和夹持方向不同，world sign 很脆。 |
| 不要把 stage3 改成再次完成 grasp | stage2 已负责 grasp completion；stage3 应聚焦 open progress，同时保持 grasp。 |
| 不要因为 `push_door_handle` / `push_door_hinge` 看起来 robot-agnostic 就直接标 runtime PASS | door joint index、方向、速度量级仍要 smoke。 |
| 不要重新启用 `grasp_finger_dof_pos_l1` | 当前 A2 binary gripper primitive 不适合 close-target reward。 |
| 不要用 door-open bypass 掩盖 stage2 grasp 或 stage3 open 的问题 | bypass 是 escape route，runtime 要统计比例。 |

## 建议施工顺序

| 顺序 | 工作 | 验收标准 |
|---:|---|---|
| 1 | user 审核本 stage3/open checklist | 明确哪些 term 先 PASS baseline，哪些进入 TODO design。 |
| 2 | 静态确认 `push_door_handle` / `push_door_hinge` 的 door joint index 和方向 | `joint_pos/vel[:,1]` 确实是 handle，`joint_pos/vel[:,0]` 确实是 hinge，方向与 reward 正号一致。 |
| 3 | 单独设计 A2 `push_door_force` 是否启用 | 如果启用，必须是 A2/Piper-specific force projection，不用 G1 world-X hand force。 |
| 4 | bounded smoke | 记录 stage2->3 route、stage3 dwell、handle joint progress、hinge progress、grasp hold、door contact penalties、reset/overtime。 |
| 5 | 再进入 stage4/swing | stage3 open progress 稳定后，再讨论 `dont_push_door_handle`、`target_root_distance`、`penalty_standing_still` 等 swing/through terms。 |

## Human 验收建议

| 验收项 | 当前状态 | 看什么 |
|---|---|---|
| Static source review | TODO after user review | `push_door_handle` / `push_door_hinge` 是否只依赖 door articulation，是否可作为 A2 baseline。 |
| Force reward review | TODO design | `push_door_force` 是否继续 disabled，或设计 A2 source/door-frame projection。 |
| Stage routing review | PASS static from stage2 | `_stage_2_to_3_advance_condition()` 不立即改；stage3 reward condition 复用它。 |
| Runtime smoke | TODO | stage3 是否真的转 handle / 推 hinge，而不是刚进 stage3 就靠阈值跳走或 reset。 |
