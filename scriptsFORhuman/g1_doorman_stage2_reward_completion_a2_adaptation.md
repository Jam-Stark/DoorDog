# G1 Doorman Stage2 Reward / Completion A2 Adaptation Checklist

本文给 human 快速看懂：A2+Piper 进入 `STAGE_GRASP = 2` 以后，到底哪些 reward 已经有第一版，哪些只是 carrier，哪些还是 placeholder，以及下一步应该先实现什么。

一句话结论：A2 的 stage2 grasp completion 已有第一版 static implementation。`_stage_2_to_complete_condition()` 现在基于 Piper gripper 双侧 handle contact、source local `+Y` squeeze magnitude 与 opposite-sign squeeze 判断是否抓住 handle；`_stage_2_to_3_advance_condition()` 仍保留 completion OR door-open bypass。下一步不是改 stage3/open，而是先做 bounded smoke，确认 completion route 与 bypass ratio。

## 优先级清单

- DONE 2026-06-17 21:21 HKT: A2 `_stage_2_to_complete_condition()` 已实现，不再返回 all false。
- DONE 2026-06-17 21:21 HKT: completion 主通路基于 Piper `arm_body7` / `arm_body8` handle-specific contact force、source local `+Y` squeeze threshold 与 opposite-sign squeeze，不照搬 G1 “4 个手指 link contact”。
- DONE 2026-06-17 21:21 HKT: `_stage_2_to_3_advance_condition()` 继续保留 `completion | door_open_bypass`；door-open 仍只是 escape，需要 smoke 统计是否变成主通路。
- DONE 2026-06-17 22:34 HKT: Main + Ava + independent reviewer 三方确认，当前 stage2 reward completion / A2 adaptation 可记为 `static PASS`；stage2 静态层面没有必须补齐的 blocker。
- P1: `grasp` reward metric 已经有第一版，可作为 completion 设计的数据源之一，但不要直接把 reward scalar 当 completion。
- DONE 2026-06-17 22:11 HKT: `grasp_target_distance` 已启用为 A2 PASS reward metric，使用 Piper TCP/source 到 handle target distance；`grasp_finger_dof_pos_l1` 继续 PASS disabled/deferred，不做 fully-closed close-target reward。
- P1: stage2 completion static implementation 完成后，先 smoke stage2 dwell / completion route / bypass ratio，再回头看 stage3/open reward；`push_door_handle` / `push_door_hinge` / `push_door_force` 是 open stage，不是 stage2 grasp completion。

## Source of Truth

- Origin env: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- Origin reward config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- Current A2 env: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`
- Current A2 reward config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`
- Stage1 checklist: `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/g1_doorman_stage1_reward_adaptation.md`
- Transition checklist: `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/g1_doorman_transition_correctness_a2_adaptation.md`

## 状态词约定

| 状态 | 含义 |
|---|---|
| `PASS carrier` | stage framework、base stillness、door hinge 等载体可用；不代表 grasp 语义完成。 |
| `PASS baseline` | 第一版可以保留训练，但后续要 smoke 看量级和副作用。 |
| `PASS reward metric` | reward 侧 metric 已实现；可以喂给 policy 或作为 completion 设计参考，但不等于 transition 完成。 |
| `PASS disabled` | 已确认当前 A2 不应启用或暂时保持 `0.0`。 |
| `TODO / placeholder` | A2 仍是 zeros/all false/G1-only 语义，不能当成完成。 |
| `TODO design` | 有可用数据源，但 threshold、组合方式、是否需要 temporal stability 还要先审。 |

## Stage2 Boundary Facts

| 项目 | G1/HOMIE 原始语义 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| Stage name | `STAGE_GRASP = 2`，含义是“已经到 pregrasp，现在要真正抓住 handle” | stage index 沿用 | PASS carrier | 不要把 stage2 当成开门阶段；stage2 首要目标是 grasp completion。 |
| Reward condition | `_stage_2_reward_condition()` 只要求 base command norm `<=0.1` | A2 同样只看 `get_physical_homie_commands()[:, :3]` norm `<=0.1` | PASS carrier | 这个条件只表示抓的时候 base 不要乱动，不检查 gripper 是否抓住。 |
| Completion | G1 `_stage_2_to_complete_condition()`：选中的手，handle contact force norm `>1` 的 hand links 数量 `>=4` | A2 path 已改为双侧 Piper gripper handle contact + source local `+Y` squeeze completion：两侧 force norm `>1.0`，两侧 `abs(Y)>0.5`，且两侧 `Y` force sign opposite | PASS static implementation | 第一版只做 instantaneous contact/squeeze boolean；smoke 看 contact spike、force magnitude、是否需要 aperture/temporal stability。 |
| Advance to stage3 | G1 `_stage_2_to_3_advance_condition()` = completion OR door hinge `>0.174533` | A2 保持 completion OR door-open bypass；completion 不再 all false | PASS static routing; smoke TODO | 保留 OR bypass，但 smoke 要统计 bypass ratio，防止 policy 绕过 grasp。 |
| Stage3 reward condition dependency | `_stage_3_reward_condition()` 会复用 `_stage_2_to_3_advance_condition()` 并要求 base still | A2 已有 stage2 completion 主通路，但 stage3/open runtime correctness 尚未 smoke | TODO dependent smoke | stage3/open 仍不要直接标 PASS；先看 stage2 completion route 是否稳定。 |

## Stage2 Reward Term Mapping

| Reward term | G1 scale / stage | G1 大白话 | 当前 A2 状态 | A2适配状态 | 开发/检查建议 |
|---|---:|---|---|---|---|
| `stage` | `+1.0`, all stages | 当前 stage 条件满足时给 flow reward | A2 沿用 `StagedTaskBase` | PASS carrier | stage reward 不是 grasp success；它只奖励“还在这个 stage 的基本条件 OK”。 |
| `grasp_finger_dof_pos_l1` | `+3.0`, stages `[2,3,4]` | G1 让选中的手指去跟踪 grasp close pose `_p1`，还带 finger velocity shaping | A2 scale `0.0`，函数 A2 path 返回 zeros | PASS disabled / deferred | 当前 A2 gripper primitive 是 binary，不要直接改成“Piper gripper fully close”。更合适的未来版本应等 continuous aperture primitive 后，再做 aperture/contact-aware reward，例如合适开合度、双侧 contact、force 不过大，而不是 close-target reward。 |
| `grasp_target_distance` | `+3.0`, stages `[2,3,4]` | G1 让选中的 palm 继续贴近 `grasp_target`，std `0.1` | A2 scale `3.0`，函数 A2 path 读取 `piper_gripper_handle_frame_transformer.data.target_pos_source[:, 0, :]`，fail-fast 校验 exact shape `(num_envs, 2, 3)`，返回 `std=0.1` tracking reward | PASS reward metric | 用 Piper TCP/source 到 handle target 的 relative distance 替代 G1 palm distance；不要用 G1 palm/body index。 |
| `grasp` | `+0.2`, stages `[1,2,3,4]` | G1 用手和 handle 的 contact force 做抓握 shaping；stage1 反过来惩罚早碰 | A2 已实现 handle-specific contact sensor：`/door_handle` 对 `arm_body7` / `arm_body8`，source local `+Y` 两侧夹持 reward，stage1 惩罚 premature contact；stage2 completion 已复用同一 contact source，但写成独立 boolean condition | PASS reward metric + completion input | completion 没有直接拿 reward scalar 过关；smoke 中继续看 force threshold 和 off-axis/contact spike。 |
| `gripper_handle_orientation` | G1 是 `hand_handle_orientation: +3.0`, stages `[1,2,3,4]` | 抓住以后也要保持手和 handle 方向合理 | A2 已实现 source local `+Y` opening axis、`+Z` approach axis 的 orientation reward | PASS reward metric | stage2 completion 可考虑要求 orientation 仍合理，但要先确认用 pregrasp target 还是 handle target，不要盲目复用 stage1 raw threshold。 |
| `penalty_not_standing_still` | `-15.0`, stages `[1,2,3]` | 抓/开时 base 不要乱走 | A2 同 carrier | PASS baseline | 可能会压制 stage2 细小 base 调整；smoke 看是否过强。 |
| `penalty_unused_dof_deviation_l1` | `-1.0`, stages `[1,2,3,4]` | G1 双臂任务里，没用的另一只手不要乱动 | A2 scale `0.0` | PASS disabled | Piper 是 one-arm，不要为了对齐 G1 强行启用 unused-arm penalty。 |
| `penalty_face_door` | `-1.0`, stages `[0,1,2,5]` | 机器人身体保持面对门 | A2 当前保留 baseline | PASS baseline | A2 可能需要偏侧站姿；如果 grasp 时被这个 term 卡住，再考虑 yaw-only 或 heading offset。 |
| Door frame/panel contact penalties | `-0.1`, always-on | 撞门框/门板要罚 | A2 已有 door contact sensors | PASS baseline | 确认 expected gripper-handle contact 不会被 undesired/door panel contact 误罚。 |
| `push_door_handle` / `push_door_hinge` / `push_door_force` | open stage 起作用 | 真正拧把手/推门的 reward | `push_door_handle`、`push_door_hinge` 保留；A2 `push_door_force` scale 当前 `0.0` | Not stage2 | 这些先不要塞进 stage2 completion。stage2 只判断抓稳，stage3/open 再讨论开门力和门铰链进展。 |

## Stage2 Completion Design Checklist

| 设计输入 | 当前可用 source | 为什么需要 | A2适配状态 | 第一版建议 |
|---|---|---|---|---|
| 双侧 handle contact | `a2_gripper_handle_contact_sensor.data.force_matrix_w`，shape 应为 `(num_envs, 1, 2, 3)`，两侧分别来自 `arm_body7` / `arm_body8` | Piper gripper 抓住 handle，至少应该两侧都有接触，而不是单边撞上去 | PASS static implementation | 第一版要求两侧 world force norm 都 `>1.0`。 |
| 接触方向 | `_reward_grasp()` 已把 world force 旋到 Piper TCP/source frame，当前奖励 local `+Y` squeeze axis，惩罚 X/Z off-axis | 防止把侧撞、顶撞、刮擦也当成 grasp | PASS static implementation | completion 复用同样 frame transform，要求两侧 source local `abs(Y)>0.5`，且两侧 `Y` force signs opposite；没有使用 world sign check。 |
| Gripper actual DOF / aperture | `_a2_gripper_dof_indices`，`_a2_gripper_open_target`，`_a2_gripper_close_target`，`simulator.dof_pos` | 只看 contact 可能误判；aperture 太开/太闭都可能不是好 grasp | TODO design | 不要求 fully closed。第一版可以要求 actual DOF 在 open/close span 合理范围内，后续 continuous aperture primitive 再做更细。 |
| TCP / handle relative pose | `piper_gripper_handle_frame_transformer` target `handle` / `pregrasp` relative source pose | 确认 gripper 不是在很奇怪的位置碰到 handle | TODO design | 可考虑 TCP 到 handle/pregrasp 的小范围窗口；先确认 target index 和坐标语义，保持 fail-fast。 |
| Orientation hold | `_get_a2_gripper_handle_orientation_metrics()` 或新 helper | 抓住时 gripper opening axis 应继续对 handle 合理 | TODO design | 可以复用 stage1 orientation 思路，但不要默认同一 threshold；stage2 可能需要 handle-frame 而不是 pregrasp-frame metric。 |
| Door-open bypass | `door.data.joint_pos[:, 0] > 0.174533` | 如果门已经被打开一点，不要卡死在 stage2 | PASS carrier | 保留 OR bypass，但 runtime smoke 必须记录 bypass ratio。 |
| Temporal stability | 可能需要 consecutive-step counter 或利用 stage dwell observations | 防止一帧 contact spike 就过关 | TODO design | 第一版可以先做 instantaneous boolean；如果 smoke 发现误触发，再加短窗口稳定性。不要先加复杂状态机。 |

## 不要做的事

| 不要做 | 原因 |
|---|---|
| 不要把 G1 `>=4 hand links` 直接改成 Piper `>=4` | Piper 只有两侧 gripper contact body，计数语义完全不同。 |
| 不要用 G1 left/right hand、finger DOF、palm indices fallback | A2 是 one-arm Piper，缺 source 应该 fail-fast。 |
| 不要把 gripper fully closed 当成 grasp success | handle 在中间时，强追 fully closed target 可能制造过大接触力和抖动。 |
| 不要让 door-open bypass 成为主通路 | 这会让 policy 学会没抓稳也进入 open stage。 |
| 不要先改 stage3/open 来掩盖 stage2 all-false | stage3 依赖 stage2 advance；先修 grasp completion。 |
| 不要为了 reward config 对齐 G1 强开 `grasp_finger_dof_pos_l1` | 该 term 需要 continuous aperture primitive 后再做 aperture/contact-aware 设计，尤其要避开 G1 finger fully-closed 假设。`grasp_target_distance` 已有 A2-specific Piper TCP/source-to-handle implementation。 |

## 建议施工顺序

| 顺序 | 工作 | 验收标准 |
|---:|---|---|
| 1 | 先让 user 审核 stage2 completion 条件列表 | DONE 2026-06-17 21:21 HKT：第一版只纳入双侧 contact、source local `Y` squeeze magnitude、opposite-sign squeeze。 |
| 2 | 只实现 `_stage_2_to_complete_condition()` | DONE 2026-06-17 21:21 HKT：A2 path 不再 all false；`_stage_2_to_3_advance_condition()` 仍是 completion OR door-open bypass；未改 stage3/open。 |
| 3 | Bounded smoke | TODO：记录 stage2 dwell time、completion route、door-open bypass ratio、two-side contact force magnitude、off-axis force、gripper aperture、reset/overtime。 |
| 4 | 复核 stage2 reward placeholders | DONE 2026-06-17 22:11 HKT：`grasp_target_distance` 已按 Piper TCP/source 到 handle target distance 落地；`grasp_finger_dof_pos_l1` 继续 disabled/deferred，等 continuous aperture primitive 后再设计。 |
| 5 | 再进入 stage3/open reward | TODO after smoke：再讨论 `push_door_handle`、`push_door_hinge`、`push_door_force` 和 opening progress。 |

## Human 验收建议

| 验收项 | 当前状态 | 看什么 |
|---|---|---|
| Static source review | PASS 2026-06-17 21:21 HKT | `_stage_2_to_complete_condition()` A2 path 不再 `torch.zeros(...)` all false，使用 `both_contact & sufficient_squeeze & opposite_squeeze`。 |
| Contact source review | PASS source | 确认 `a2_gripper_handle_contact_sensor` 只看 `/door_handle` 对 `arm_body7` / `arm_body8`，不混 global contact。 |
| Fail-fast review | PASS requirement | 缺 sensor、shape 不对、target order 不对时直接 raise，不返回 zeros。 |
| Stage routing review | PASS static 2026-06-17 21:21 HKT | `_stage_2_to_3_advance_condition()` 保持 `completion | door_open_bypass`；runtime 是否主走 completion 仍需 smoke。 |
| Runtime smoke | TODO | 看 stage2 是否正常停留并完成，是否频繁靠 door-open bypass 跳过，是否出现 contact spike 误判。 |
