# G1 Doorman Stage1 Reward A2 Adaptation Checklist

本文用于把 G1/HOMIE Doorman `STAGE_PREGRASP = 1` 的 reward 迁移到 A2+Piper 时做 human quick-check。重点是 reward term mapping、已完成的 stage1->2 pregrasp completion condition、A2 当前 stage2 transition placeholder 边界、以及后续 stage2 grasp completion semantics 的施工顺序。

## 优先级清单

- DONE reward metric + transition input: `hand_handle_orientation` 已替换为 A2 `gripper_handle_orientation`，active scale `+3.0`；2026-06-17 20:34 HKT stage1 -> 2 主判断已消费 raw `opening_alignment >= 0.8` 与 `approach_alignment >= 0.8`。
- DONE reward metric + transition input: `pregrasp_target_distance` 已用 Piper TCP/pregrasp target distance + velocity shaping 重建，active scale `+6.0`，stage `[1]`；2026-06-17 20:34 HKT stage1 -> 2 主判断已消费 `target_pos_source[:, 1, :]` distance `<0.1m`。
- DONE reward metric: `grasp` 已用 handle-specific contact sensor 重建，active scale `+0.2`，stages `[1,2,3,4]`；stage1 惩罚 premature handle contact，stage2+ 奖励 two-sided handle contact force。
- P0: transition correctness 仍剩 stage2 completion：stage1 -> 2 Piper pregrasp completion 已完成；stage2 completion 仍需 grasp/contact semantics。
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
| `PASS reward metric` | reward metric / scale / config routing 已实现；不代表对应 stage 的过关判断已经使用该 metric。 |
| `TODO / placeholder` | 当前 A2 scale 为 `0.0`、函数返回 zeros、或语义仍是 G1-only，不应计入完成。 |
| `Blocked by transition correctness` | reward term 本身可设计，但是否有效取决于 stage1 -> 2 或 stage2 -> 3 correctness。 |

## Stage1 Boundary Facts

| 项目 | Source/function | 已核查事实 | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| Stage name | `DoorPregrasp.STAGE_PREGRASP = 1` | stage1 语义是 move hand / gripper to pregrasp pose before grasp | PASS carrier | Stage1 只做 pregrasp，不要求已经抓住 handle，也不要求已经打开门。 |
| Reward condition | `_stage_1_reward_condition()` | command norm `<=0.1` and still satisfies stage0 -> 1 boundary；A2 stage0 boundary 的 root-to-handle 平面距离已从 G1 `<0.3m` 调整为 `<0.6m` | PASS carrier | stage reward 只说明 base still and remains in A2-safe near-handle window；pregrasp correctness 由 reward/transition 补齐。 |
| Transition out | `_stage_1_to_2_advance_condition()` | Origin 的主逻辑是 pregrasp pose/orientation/gripper readiness；A2 已改为 `pregrasp_ready | door_open_bypass`，其中 `pregrasp_ready` 要求 TCP 到 pregrasp `<0.1m`、opening/approach alignment `>=0.8`、base command norm `<=0.1`、actual `arm_j7/arm_j8` 在 open/close target 外扩 25% span 内。 | PASS correctness | Stage1 不要求 TCP above-handle、handle contact、grasp completion 或已开门；door-open bypass 仅作为 OR escape。 |

## Stage1 Reward Term Mapping

| Reward term | Origin scale / stage | Origin logic summary | Current A2 state | A2适配状态 | 开发/检查建议 |
|---|---:|---|---|---|---|
| `stage` | `+1.0`, all stages via `_reward_stage()` | 根据 `_stage_1_reward_condition()` 给 flow reward；不是 pure alive bonus | A2 同 scale，同 StagedTaskBase carrier | PASS carrier only | 不要把 `stage` reward 当成 pregrasp correctness；等 stage1 condition/transition 完成后再看 stage reward cadence。 |
| `pregrasp_finger_dof_pos_l1` -> `pregrasp_gripper_dof_pos_l1` | G1 `+1.5`, stages `[0,1,5]` | G1 selected finger p0 / velocity shaping，pregrasp 阶段准备手指 | A2 已改名完成，scale 降为 `+0.5`，stages `[0,1,5]`；当前跟踪 Piper `arm_j7/arm_j8` close target，`pos_track + 0.2 * vel_track` | PASS baseline, not grasp correctness | 当前 gripper primitive 仍是 binary close/open，先降低权重避免过度驱动 fully closed target；未来改 continuous aperture 后再重新设计该 reward。 |
| `penalty_unused_dof_deviation_l1` | `-1.0`, stages `[1,2,3,4]` | 双臂 G1 中惩罚 unused arm 偏离 resting pose | A2 scale `0.0`；one-arm Piper 直接复用 invalid | PASS disabled / not applicable to one-arm Piper | 保持 `0.0`；若未来需要，另建 A2-specific non-task arm/body regularization，不要为了对齐 origin 强开。 |
| `hand_handle_orientation` -> `gripper_handle_orientation` | `+3.0`, stages `[1,2,3,4]` | selected hand frame 与 handle orientation tracking，stage1 transition 要求 reward `>0.2` | A2 active scale `+3.0`；使用 `piper_gripper_handle_frame_transformer.data.target_quat_source[:, 1, :]` 的 pregrasp target relative source rotation，source local `+Y` 为 opening axis，source local `+Z` 为 approach axis；`opening_alignment = abs(dot(source_y, target_y_source))`，`approach_alignment = dot(source_z, target_z_source)`，采用用户选定 `+Z` approach sign；reward 为两个 `std=0.25` tracking terms 的 product 并 clamp `[0,1]`；legacy `_reward_hand_handle_orientation()` A2 path fail-fast；stage1 -> 2 transition 使用 raw `opening_alignment >= 0.8` 与 `approach_alignment >= 0.8` | PASS reward metric + transition input | 该 reward 能教 gripper 在 pregrasp 阶段对准 handle/pregrasp target；transition 中的 raw alignment 只表示 pregrasp pose 合格，不表示已经抓住、接触或开门。 |
| `pregrasp_target_distance` | `+6.0`, stage `[1]` | palm 到 pregrasp target distance tracking + palm velocity toward target | A2 active scale `+6.0`；`_reward_pregrasp_target_distance()` 使用 `piper_gripper_handle_frame_transformer.data.target_pos_source[:, 1, :]` 计算 Piper TCP 到 pregrasp target distance，使用 `target_pos_w[:, 1, :] - source_pos_w` 做 velocity direction，当前 velocity 来自 `simulator._rigid_body_vel[:, end_effector_index, :3]`；`pregrasp_target_vel` 必须存在且为正数；保持 G1 `std=0.2` pos + `std=0.15` vel 和 clamp max `1.0`；stage1 -> 2 transition 使用同一 `target_pos_source[:, 1, :]` distance `<0.1m` | PASS reward metric + transition input | 已按 fail-fast config/source 检查实现，无 G1 palm/finger fallback；smoke 中检查 reward magnitude、TCP 到 target 的收敛和 bypass route 比例。 |
| `penalty_not_standing_still` | `-15.0`, stages `[1,2,3]` | 惩罚 physical base command norm，鼓励 pregrasp/grasp/open 时 base 不动 | A2 scale `-15.0`，同 carrier `get_physical_homie_commands()[:, :3]` | PASS baseline | 语义是 no translate/yaw while pregrasping；后续看 pitch/roll command 是否需要额外约束。 |
| `grasp` | `+0.2`, stages `[1,2,3,4]` | Contact force reward；在 stage1 取 `-abs(reward)`，惩罚 premature/incorrect contact | A2 active scale `+0.2`；新增 `a2_gripper_handle_contact_sensor` 只读取 `/door_handle` 对 `arm_body7` / `arm_body8` 的 `force_matrix_w`；`_reward_grasp()` 将 world force 旋到 Piper TCP/source frame，使用 source local `+Y` 作为 gripper opening/closing force axis；stage1 对任何 handle contact magnitude 给 negative reward，stage2+ 用 two-sided `min` contact reward 并惩罚 off-axis force | PASS reward metric; grasp completion TODO | Reward metric 已完成且保持 fail-fast sensor/shape/source 检查；但 `_stage_2_to_complete_condition()` 尚未使用该 contact source，stage2+ completion 仍需 aperture/contact stability semantics。 |
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
| Orientation reward design | PASS reward metric + transition input | `gripper_handle_orientation` 已按 target-frame opening/approach alignment 启用；stage1->2 pregrasp completion condition 已复用 raw orientation metrics，不 fallback 到 G1 left/right palm transform。 |
| Pregrasp distance reward design | PASS reward metric | 使用 Piper TCP/pregrasp target distance 和 TCP velocity；A2 path 要求 runtime config `pregrasp_target_vel=0.3` 存在且为正数，不使用 origin legacy fallback default `0.5`；后续在 smoke 中校准 reward magnitude。 |
| Gripper readiness | PASS transition input | `_stage_1_to_2_advance_condition()` 使用 actual `arm_j7/arm_j8` 是否位于 open/close target 外扩 25% span 内；span zero/near-zero 时 fail-fast raise。该条件只表示 pregrasp readiness，不表示 grasp closure success。 |
| Premature contact penalty | PASS reward metric | `grasp` stage1 branch 已惩罚 handle contact magnitude；stage2+ 已有 two-sided contact reward，但这还不是 stage2 completion。 |
| Transition consistency | PARTIAL PASS | `_stage_1_to_2_advance_condition()` 已同步 reward metrics/readiness，不再只依赖 door-open bypass；`_stage_2_to_complete_condition()` 仍需 Piper grasp/contact semantics。 |
| Reward scale activation | PASS reward metric | `gripper_handle_orientation: +3.0`、`pregrasp_target_distance: +6.0`、`grasp: +0.2` 已启用并加入 `reward_penalty_reward_names`，对齐 origin positive shaping curriculum。 |
| Smoke validation | TODO | 不在 docs-only 阶段运行 PPO/Isaac；后续 code 完成后记录 reward magnitude、stage1 dwell time、stage1 -> 2 route、door-open bypass ratio。 |
| Fail-fast policy | PASS requirement | 缺 sensor/body/target order 时直接 raise；不要用 zeros/fallback 强行让训练继续。 |
