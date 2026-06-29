# G1 Doorman Stage4 Reward / Completion A2 Adaptation Checklist

本文给 human 快速看懂：A2+Piper 进入 `STAGE_SWING = 4` 以后，原版 G1 到底在奖励什么、stage4 怎么进入 stage5、当前 A2 哪些可以先保留、哪些必须重新设计。

一句话结论：stage4/swing 的主目标是门已经打开（hinge > 10°）后，松开 handle（让 handle 回弹关闭）、推门穿过门框。G1 的 stage4 reward 大部分是 robot-agnostic 的 door-joint progress + root locomotion，可作为 A2 baseline；`target_root_pos` z 已从 G1 的 0.72 调整为 A2 的 0.5（匹配 trunk 高度）；`penalty_standing_still` 的 std=0.05 是否匹配 A2 四足走动需要 smoke 验证。

## 优先级清单

- DONE 2026-06-29: stage3 reward completion / A2 adaptation 已确认 `static PASS`，`push_door_handle` / `push_door_hinge` joint index 和方向静态验证通过，`push_door_force` 保持 disabled。
- DONE 2026-06-29: `target_root_pos` z 从 G1 的 `0.72` 调整为 A2 的 `0.5`（匹配 trunk 高度），消除 `target_root_distance` 的恒定 offset。
- DONE 2026-06-29: `penalty_standing_still` / `grasp` / `grasp_target_distance` / `gripper_handle_orientation` 确认沿用，不需要改 code。
- P1: bounded smoke 仍要统计 stage3→4 route、stage4 dwell、handle 回弹、hinge 持续 progress、root locomotion、door-open bypass ratio。

## Source of Truth

- Origin env: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- Origin reward config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- Current A2 env: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`
- Current A2 reward config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`
- A2 env config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/env/door_open_a2_base.yaml`
- Stage3 checklist: `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/g1_doorman_stage3_reward_completion_a2_adaptation.md`

## 状态词约定

| 状态 | 含义 |
|---|---|
| `PASS carrier` | stage/routing 条件可沿用，但不代表 swing 行为已经 smoke 通过。 |
| `PASS baseline` | 第一版可以保留训练，后续看 reward magnitude、方向和副作用。 |
| `PASS reward metric` | reward 侧 metric 已有 A2 实现，可继续作为 shaping。 |
| `PASS disabled` | 当前 A2 明确不启用，或者启用会引入错误语义。 |
| `TODO design` | 需要单独设计 A2/Piper 语义，不能直接照搬 G1。 |
| `TODO smoke` | 静态代码可以先过，但 runtime 需要验证。 |

## Stage4 Boundary Facts

| 项目 | G1/HOMIE 原始语义 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| Stage name | `STAGE_SWING = 4`，门已打开，开始松 handle、推门穿过 | stage index 沿用 | PASS carrier | stage4 不是"继续开门"，而是"门开了之后穿过去"。 |
| Stage4 reward condition | `_stage_4_reward_condition()` = `_stage_3_to_4_advance_condition()`（hinge > 0.174533） | A2 同 G1 | PASS carrier | stage4 只要求门打开过一次就持续给 stage reward，不要求保持开门。 |
| Stage4 advance | `_stage_4_to_5_advance_condition()` 要求 `walked_through_door` (root_x > 0.0) & `door_opened` (hinge > 1.0472=60°) & `handle_up` (handle < 0.2) | A2 当前同 G1 | PASS baseline / verify root_x | `walked_through_door` 用 `robot_root_states[:, 0] - env_origins[:, 0] > 0.0`，假设 door 在 x=0 处、robot 要穿到 x>0。A2 root 是 `trunk` body，z 高度不同但 x 语义相同。第一版保留；smoke 看是否过早/过晚进入 through。 |
| `target_root_pos` | G1 config `[2.0, 0.0, 0.72]`——door 前方 2m、z=0.72（G1 pelvis 高度） | A2 config `[2.0, 0.0, 0.5]`——z 已改为 A2 trunk 高度 | DONE | z 从 0.72 改为 0.5，消除 `target_root_distance` 的恒定 0.22m offset。 |
| `handle_up` 条件 | stage4→5 要求 `joint_pos[:, 1] < 0.2`（handle 回弹到接近 0） | A2 同 G1 | PASS baseline | handle joint lower=0、drive target=-15，弹簧会自动回弹。policy 需要在 swing 阶段松开 handle 让它回弹。door-joint progress，robot-agnostic。 |

## Stage4 Reward Term Mapping

仅列出在 stage4 (`STAGE_SWING = 4`) 生效的 reward terms。

| Reward term | G1 scale / stage | G1 大白话 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---:|---|---|---|---|
| `stage` | `+1.0`, all stages | 当前 stage condition 满足时给 flow reward | A2 沿用 `StagedTaskBase` | PASS carrier | 只说明 stage4 条件成立（门曾打开过），不代表 robot 正在穿门。 |
| `dont_push_door_handle` | `+3.0`, stages `[4,5]` | 奖励 handle 回弹（vel 取负、pos 从 45° 回到 0），即松开 handle 让它关闭 | A2 scale `3.0`，函数与 G1 完全一致 | PASS baseline | door-joint progress，robot-agnostic。stage4 应该松 handle 让弹簧回弹，这个 reward 引导 policy 不要继续压 handle。 |
| `push_door_hinge` | `+6.0`, stages `[3,4]` | 继续奖励 hinge 速度和开门角度 | A2 scale `6.0`，与 G1 完全一致 | PASS baseline | stage4 门还在继续开，hinge reward 仍有效。stage5 不再给（effective_in_stage 是 [3,4]）。 |
| `target_root_distance` | `+12.0`, stages `[4,5]` | 奖励 robot root 朝 `target_root_pos` 方向移动 + 接近目标位置 | A2 scale `12.0`，函数与 G1 完全一致，`target_root_pos` z 已改为 0.5 | PASS baseline | stage4 时 `reward *= 0.5`（line 1210），stage5 时 full reward。root_vel target=0.3 m/s。 |
| `penalty_standing_still` | `-1.0`, stage `[4]` | stage4 开始走动，惩罚 base command norm 太小（不走） | A2 scale `-1.0`，函数与 G1 完全一致 | PASS baseline / smoke | G1 人形用 HOMIE locomotion 走门；A2 四足用 A2_Base locomotion。`std=0.05` 的 tracking 可能对 A2 太严或太松。smoke 看 A2 是否敢走。 |
| `grasp` | `+0.2`, stages `[1,2,3,4]` | stage4 仍保持 gripper-handle contact（还没松手） | A2 已有 handle-specific contact sensor 实现 | PASS reward metric | stage4 初期仍需保持抓握，直到 `dont_push_door_handle` 引导松开。smoke 看 contact spike。 |
| `grasp_target_distance` | `+3.0`, stages `[2,3,4]` | stage4 仍保持 TCP 接近 handle | A2 已有 Piper TCP→handle distance 实现 | PASS reward metric | stage4 初期仍有效，引导 TCP 不离 handle 太远直到松开。 |
| `gripper_handle_orientation` | `+3.0`, stages `[1,2,3,4]` | stage4 仍保持 gripper-handle 方向合理 | A2 已启用 scale `3.0`，offset 动态跟随 handle | PASS reward metric | 已确认 offset 在 handle local frame，handle 转动时动态跟随。stage4 handle 回弹时 orientation 约束也跟着变。 |
| `penalty_unused_dof_deviation_l1` | `-1.0`, stages `[1,2,3,4]` | G1 未使用的另一只手不要乱动 | A2 scale `0.0` | PASS disabled | Piper 是 one-arm，不启用。 |
| `grasp_finger_dof_pos_l1` | `+3.0`, stages `[2,3,4]` | G1 手指保持 close grasp pose | A2 scale `0.0` | PASS disabled | binary gripper primitive 不适合。 |
| Door frame/panel contact penalties | `-0.1`, always-on | 穿门时撞门框/门板要罚 | A2 已有 sensors 和 scale | PASS baseline | stage4 穿门时最容易碰门框，smoke 要看 false positive。 |

## Stage4 Swing Design Checklist

| 设计输入 | 当前可用 source | 为什么需要 | A2适配状态 | 第一版建议 |
|---|---|---|---|---|
| Handle 回弹 progress | `door.data.joint_pos[:, 1]`, `door.data.joint_vel[:, 1]` | stage4 要松 handle 让它回弹，G1 `dont_push_door_handle` 直接奖励这个 | PASS baseline | 保留 scale `3.0`，door-joint progress robot-agnostic。 |
| Hinge 持续 progress | `door.data.joint_pos[:, 0]`, `door.data.joint_vel[:, 0]` | stage4 门还在继续开 | PASS baseline | `push_door_hinge` stages [3,4] 继续有效。 |
| Root locomotion | `robot_root_states[:, :3]`, `target_root_pos`, `_rigid_body_vel[:, root_idx, :]` | stage4 要开始走向门后方 | DONE | `target_root_pos` z 已从 0.72 改为 0.5（匹配 A2 trunk 高度）。 |
| Base 走动鼓励 | `get_physical_homie_commands()[:, :3]` | stage4 要走动，不能站着不动 | PASS baseline / smoke | `penalty_standing_still` std=0.05，A2 四足走动时 base command 量级可能不同。 |
| Grasp 释放 timing | `grasp` reward stages [1,2,3,4] + `dont_push_door_handle` | stage4 初期保持抓握，后期松开 | PASS reward metric | 第一版不改；如果 smoke 发现 policy 过早松手或过晚松手，再调 grasp scale 或 dont_push_door_handle scale 的比例。 |
| Door contact safety | door frame/panel contact sensors | 穿门时撞门框 | PASS baseline / smoke | 统计 frame/panel penalty frequency。 |
| Walk-through 阈值 | `robot_root_states[:, 0] - env_origins[:, 0] > 0.0` | stage4→5 要求 robot root x 越过门平面 | PASS baseline / verify | A2 trunk body 的 x 位置语义与 G1 pelvis 相同（都是 root）。第一版保留 x>0.0 阈值。 |

## 不要做的事

| 不要做 | 原因 |
|---|---|
| 不要在 stage4 继续启用 `push_door_handle` | stage4 应该松 handle，不应继续压。`push_door_handle` 的 `effective_in_stage` 只含 [3]。 |
| 不要把 `target_root_pos` 的 x 改成门后方很远的位置 | G1 用 [2.0, 0.0, ...]，x=2.0 是 door 前方 2m 处。stage4 是走向目标位置，不是瞬移。 |
| 不要因为 `penalty_standing_still` 看起来 robot-agnostic 就直接标 runtime PASS | A2 四足走动的 base command 量级和 G1 HOMIE 不同，std=0.05 的 tracking 可能不匹配。 |
| 不要在 stage4 重新设计 grasp 释放逻辑 | `dont_push_door_handle` + handle 弹簧回弹已经引导松开。如果效果不好，调 scale 比例而不是加新 logic。 |

## 建议施工顺序

| 顺序 | 工作 | 验收标准 |
|---:|---|---|
| 1 | user 审核本 stage4/swing checklist | 明确哪些 term 先 PASS baseline，哪些进入 TODO design。 |
| 2 | 静态确认 `dont_push_door_handle` 的方向 | handle 回弹 = handle joint_pos 从 45° 回到 0，reward 的 `0.785398 - joint_pos` 确实奖励回弹方向。DONE：与 G1 完全一致，door-joint progress。 |
| 3 | `target_root_pos` z 调整 | DONE：z 从 0.72 改为 0.5，匹配 A2 trunk 高度。 |
| 4 | 确认 `penalty_standing_still` std=0.05 是否匹配 A2 | A2 四足走动 base command 量级需 smoke 确认。 |
| 5 | bounded smoke | 记录 stage3→4 route、stage4 dwell、handle 回弹 timing、hinge 持续 progress、root locomotion、door contact penalties、reset/overtime。 |
| 6 | 再进入 stage5/through | stage4 swing progress 稳定后，确认 stage4→5 advance 和 stage5 complete。 |

## Human 验收建议

| 验收项 | 当前状态 | 看什么 |
|---|---|---|
| Static source review | DONE | `dont_push_door_handle` / `target_root_distance` / `penalty_standing_still` 只依赖 door articulation + root state，可作为 A2 baseline。`grasp` / `grasp_target_distance` / `gripper_handle_orientation` 沿用已有 A2 实现。 |
| `target_root_pos` z review | DONE | z 已从 0.72 改为 0.5，匹配 A2 trunk 高度。 |
| Stage routing review | PASS static from stage3 | `_stage_3_to_4_advance_condition()` 不改；stage4 reward condition 复用它。stage4→5 advance 的 `walked_through_door` + `handle_up` + `door_opened` 保留。 |
| Runtime smoke | TODO | stage4 是否真的松 handle 回弹、推门 hinge、开始走向 target_root_pos，而不是卡在 stage4 不动。`penalty_standing_still` std=0.05 是否匹配 A2 四足走动。 |
