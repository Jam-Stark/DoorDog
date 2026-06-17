# G1 Doorman Stage1 Reward A2 Adaptation Checklist

本文用于把 G1/HOMIE Doorman `STAGE_PREGRASP = 1` 的 reward 迁移到 A2+Piper 时做 human quick-check。重点是 reward term mapping、A2 当前 placeholder 边界、以及下一步 stage1 reward + transition correctness 的施工顺序。

## 优先级清单

- DONE reward metric: `hand_handle_orientation` 已替换为 A2 `gripper_handle_orientation`，active scale `+3.0`；但这不代表 stage1 -> 2 transition correctness 已完成。
- P0: `pregrasp_target_distance` 不能继续 zero placeholder；用 Piper TCP/pregrasp target distance + velocity shaping 重建。
- P0: `grasp` 不能继续 zero placeholder；stage1 需要 premature/incorrect contact penalty，stage2+ 才奖励 stable grasp。
- P1: `penalty_unused_dof_deviation_l1` 对 one-arm Piper 不适用，当前保持 disabled。
- P1: `stage`、`penalty_not_standing_still`、stage0/global baseline terms 可以作为 carrier/baseline，但必须 smoke reward magnitudes。

## Source of Truth

- Origin env: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- Origin reward config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- Origin stage base: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/base_task/staged_task_base.py`
- Current A2 env: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`
- Current A2 reward config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`
- Stage0 baseline doc: `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/g1_doorman_stage0_reward_transition.md`
- Transition checklist: `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/g1_doorman_transition_correctness_a2_adaptation.md`

## 状态词约定

| 状态 | 含义 |
|---|---|
| `PASS carrier` | 函数入口、stage gating、base command carrier、或 stage framework 可复用；不代表 reward 语义已完成。 |
| `PASS baseline` | 当前实现可作为第一版训练 baseline，但还需要 smoke magnitude/cadence validation。 |
| `PASS disabled` | 已确认当前 A2 不应启用，保持 scale `0.0` 是预期状态。 |
| `PASS reward metric` | reward metric / scale / config routing 已实现；不代表 staged transition correctness 已完成。 |
| `TODO / placeholder` | 当前 A2 scale 为 `0.0`、函数返回 zeros、或语义仍是 G1-only，不应计入完成。 |
| `Blocked by transition correctness` | reward term 本身可设计，但是否有效取决于 stage1 -> 2 或 stage2 -> 3 correctness。 |

## Stage1 Boundary Facts

| 项目 | Source/function | 已核查事实 | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| Stage name | `DoorPregrasp.STAGE_PREGRASP = 1` | stage1 语义是 raise hand / gripper to pregrasp before grasp | PASS carrier | 不要把 door hinge shortcut 当成 stage1 success 的唯一标准。 |
| Reward condition | `_stage_1_reward_condition()` | command norm `<=0.1` and still satisfies stage0 -> 1 boundary；A2 stage0 boundary 的 root-to-handle 平面距离已从 G1 `<0.3m` 调整为 `<0.6m` | PASS carrier | stage reward 只说明 base still and remains in A2-safe near-handle window；pregrasp correctness 由 reward/transition 补齐。 |
| Transition out | `_stage_1_to_2_advance_condition()` | Origin 有 pregrasp pose/orientation/gripper readiness；A2 目前只剩 hinge `>0.174533` shortcut | TODO / placeholder | Stage1 reward adaptation 应和 transition correctness 一起做，否则 reward 学到的 pregrasp 可能不会被 stage routing 使用。 |

## Stage1 Reward Term Mapping

| Reward term | Origin scale / stage | Origin logic summary | Current A2 state | A2适配状态 | 开发/检查建议 |
|---|---:|---|---|---|---|
| `stage` | `+1.0`, all stages via `_reward_stage()` | 根据 `_stage_1_reward_condition()` 给 flow reward；不是 pure alive bonus | A2 同 scale，同 StagedTaskBase carrier | PASS carrier only | 不要把 `stage` reward 当成 pregrasp correctness；等 stage1 condition/transition 完成后再看 stage reward cadence。 |
| `pregrasp_finger_dof_pos_l1` -> `pregrasp_gripper_dof_pos_l1` | G1 `+1.5`, stages `[0,1,5]` | G1 selected finger p0 / velocity shaping，pregrasp 阶段准备手指 | A2 已改名完成，scale 降为 `+0.5`，stages `[0,1,5]`；当前跟踪 Piper `arm_j7/arm_j8` close target，`pos_track + 0.2 * vel_track` | PASS baseline, not grasp correctness | 当前 gripper primitive 仍是 binary close/open，先降低权重避免过度驱动 fully closed target；未来改 continuous aperture 后再重新设计该 reward。 |
| `penalty_unused_dof_deviation_l1` | `-1.0`, stages `[1,2,3,4]` | 双臂 G1 中惩罚 unused arm 偏离 resting pose | A2 scale `0.0`；one-arm Piper 直接复用 invalid | PASS disabled / not applicable to one-arm Piper | 保持 `0.0`；若未来需要，另建 A2-specific non-task arm/body regularization，不要为了对齐 origin 强开。 |
| `hand_handle_orientation` -> `gripper_handle_orientation` | `+3.0`, stages `[1,2,3,4]` | selected hand frame 与 handle orientation tracking，stage1 transition 要求 reward `>0.2` | A2 active scale `+3.0`；使用 `piper_gripper_handle_frame_transformer.data.target_quat_source[:, 1, :]` 的 pregrasp target relative source rotation，source local `+Y` 为 opening axis，source local `+Z` 为 approach axis；`opening_alignment = abs(dot(source_y, target_y_source))`，`approach_alignment = dot(source_z, target_z_source)`，采用用户选定 `+Z` approach sign；reward 为两个 `std=0.25` tracking terms 的 product 并 clamp `[0,1]`；legacy `_reward_hand_handle_orientation()` A2 path fail-fast | PASS reward metric; transition still TODO | 该 reward metric 可供后续 `_stage_1_to_2_advance_condition()` 复用 raw metrics，但当前 A2 stage1 -> 2 仍是 hinge shortcut，不算 transition correctness 完成。 |
| `pregrasp_target_distance` | `+6.0`, stage `[1]` | palm 到 pregrasp target distance tracking + palm velocity toward target | A2 scale `0.0`，`_reward_pregrasp_target_distance()` 在 A2 path 返回 zeros | TODO / placeholder, P0 | 用 Piper TCP/pregrasp target position 和 TCP velocity 重建；先保留 origin distance threshold intuition，再 smoke 调 std/scale。 |
| `penalty_not_standing_still` | `-15.0`, stages `[1,2,3]` | 惩罚 physical base command norm，鼓励 pregrasp/grasp/open 时 base 不动 | A2 scale `-15.0`，同 carrier `get_physical_homie_commands()[:, :3]` | PASS baseline | 语义是 no translate/yaw while pregrasping；后续看 pitch/roll command 是否需要额外约束。 |
| `grasp` | `+0.2`, stages `[1,2,3,4]` | Contact force reward；在 stage1 取 `-abs(reward)`，惩罚 premature/incorrect contact | A2 scale `0.0`，`_reward_grasp()` 在 A2 path 返回 zeros | TODO / placeholder, P0 | 用 `arm_body7`/`arm_body8` contact force、aperture、handle relative stability 设计；stage1 应惩罚早碰，stage2+ 才奖励稳定 grasp。 |
| `penalty_face_door` | `-1.0`, stages `[0,1,2,5]` | 惩罚 root-to-door orientation error，鼓励面对 door | A2 当前保留 baseline | PASS baseline | 若 A2 trunk roll/pitch 或必要侧身站姿被过度惩罚，改 yaw-only heading error 或加 desired heading offset。 |

## Stage1 Active Global / Baseline Rewards

这些项在 stage1 仍会影响训练，但大多已经在 stage0/global baseline 中完成第一版 A2 replacement。它们不替代 stage1-specific Piper EE/handle reward。

| Reward / mechanism | Current A2 source | A2适配状态 | 开发/检查建议 |
|---|---|---|---|
| DOF safety: `penalty_dof_acc`, `penalty_dof_vel`, `limits_dof_pos`, `penalty_dof_overspeed` | `_upper_non_gripper_dof_idx` / Piper `arm_j1..j6` | PASS baseline | 确认 stage1 arm motion 不被过强安全项压死；看 reward magnitude。 |
| `penalty_delta_action_rate` | A2 `delta_action_indices=[5..10]`, Piper arm raw delta only | PASS baseline | 只平滑 `arm_j1..j6`；不覆盖 5D base command 或 gripper primitive。 |
| `limits_gripper_primitive_action` | raw A2 gripper primitive over-limit | PASS baseline | 若未来改 continuous aperture primitive，同步改 raw over-limit semantics。 |
| `penalty_base_command_limit` | scaled raw base command vs clipped scaled command | PASS baseline | 与 `penalty_not_standing_still` 一起看，避免 base command 被双重惩罚后无法微调站姿。 |
| `ref_dof_legs` | LMP-style gait ref prior | PASS baseline | stage1 静止/微调时看是否和 pregrasp arm motion 冲突。 |
| door frame/panel contact penalties | `penalty_door_frame_contact`, `penalty_door_panel_contact` | PASS baseline | 保持；靠近/pregrasp 时检查是否误惩罚 gripper-handle intended contact。 |
| `penalty_undesired_contact` | A2 exact-match contact list, excludes gripper links | PASS baseline | 若新 grasp contact sensor 使用 gripper links，确认 undesired contact 不会惩罚 expected grasp。 |
| `orientation_control` | LMP-style pitch/roll command tracking | PASS baseline | 和 stage1 standing still 一起 smoke；看 pitch/roll policy 是否合理。 |
| `termination` | A2/LMP height/orientation/arm overspeed adjustments | PASS baseline | 记录 stage1 reset reason，尤其是 bad orientation 和 arm overspeed。 |

## Stage1 Implementation Checklist

| 检查项 | A2适配状态 | 开发/检查建议 |
|---|---|---|
| Orientation reward design | PASS reward metric | `gripper_handle_orientation` 已按 target-frame opening/approach alignment 启用；后续 transition correctness 应复用 raw orientation metrics，不要 fallback 到 G1 left/right palm transform。 |
| Pregrasp distance reward design | TODO | 使用 Piper TCP/pregrasp target distance 和 TCP velocity；origin runtime config `pregrasp_target_vel=0.3`，code fallback default 为 `0.5`，第一版应优先按 config 语义迁移并在 smoke 中校准。 |
| Gripper readiness | TODO | 把 `pregrasp_gripper_dof_pos_l1` 当 baseline，不要当 grasp closure success；后续补 aperture/readiness condition。 |
| Premature contact penalty | TODO | `grasp` stage1 branch 应惩罚错误/过早 contact；stage2+ 再奖励 stable handle grasp。 |
| Transition consistency | TODO | reward 完成后同步 `_stage_1_to_2_advance_condition()`，否则 policy 可能学到 reward 但 stage routing 仍只看 hinge。 |
| Reward scale activation | PASS reward metric / remaining TODO | `gripper_handle_orientation: +3.0` 已启用并加入 `reward_penalty_reward_names`；`pregrasp_target_distance` / `grasp` 仍是 remaining P0 placeholder，后续开启时继续同步检查 curriculum membership。 |
| Smoke validation | TODO | 不在 docs-only 阶段运行 PPO/Isaac；后续 code 完成后记录 reward magnitude、stage1 dwell time、stage1 -> 2 route、door hinge shortcut ratio。 |
| Fail-fast policy | PASS requirement | 缺 sensor/body/target order 时直接 raise；不要用 zeros/fallback 强行让训练继续。 |
