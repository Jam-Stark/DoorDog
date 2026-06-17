# G1 Doorman Transition Correctness A2 Adaptation Checklist

本文用于把 Doorman G1/HOMIE 的 staged transition correctness 迁移到 A2+Piper 时做 human quick-check。它只记录 transition / stage condition 的 source-of-truth、A2 当前状态和后续检查建议，不代表 runtime code 已完成。

## 优先级清单

- P0: 重写 A2 `_stage_1_to_2_advance_condition()`，不能只靠 door hinge shortcut；需要 Piper TCP/pregrasp correctness。`gripper_handle_orientation` reward metric 已实现，后续 transition 可复用 raw orientation metrics。
- P0: 重写 A2 `_stage_2_to_complete_condition()` / `_stage_2_to_3_advance_condition()` 的 grasp semantics；当前 A2 grasp completion 是 all false，占位状态。
- P1: 保留并复核 stage0 -> stage1 boundary：A2 已用 Piper `grasp_target` 与 non-gripper arm `arm_j1..j6`，且因 A2 四足 base/trunk footprint 比 G1 直立人形更长，A2 平面距离阈值从 G1 `<0.3m` 调整为 `<0.6m`，当前可视为 `PASS correctness`。
- P1: stage3+ transition 目前主要是 carrier direct reuse；等 stage1/2 grasp semantics 完成后再做 correctness review。
- P2: 所有 transition 实现后再做 bounded smoke，重点看 stage cadence、door hinge shortcut 触发比例、reset/overtime 分布。

## Source of Truth

- Origin env: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- Origin stage base: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/base_task/staged_task_base.py`
- Origin env config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/env/door_open_homie.yaml`
- Origin reward config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`
- Current A2 env: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`
- Current A2 env config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/env/door_open_a2_base.yaml`
- Current A2 reward config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`

## 状态词约定

| 状态 | 含义 |
|---|---|
| `PASS correctness` | A2 condition 的 source、threshold、语义都已经按 Piper/A2 做过等价或合理替换。 |
| `PASS carrier` | stage framework、函数入口、timer、或者 robot-agnostic carrier 可复用；不代表任务语义已经正确。 |
| `PASS baseline` | 当前实现可作为第一版训练 baseline，但仍需 smoke 后看 magnitude/cadence。 |
| `PASS reward metric` | reward 侧 metric 已实现，可作为 transition 设计输入；不代表 stage transition correctness 已完成。 |
| `TODO / placeholder` | 当前 A2 逻辑是 disabled、zero、all false、或只保留 shortcut；不能作为 correctness 完成项。 |

## Stage Framework Quick Check

| 项目 | Source/function | 已核查事实 | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| Stage index | `DoorPregrasp.STAGE_WALK_TO_DOOR` ... `STAGE_THROUGH` | 6 stages: 0 walk, 1 pregrasp, 2 grasp, 3 open, 4 swing, 5 through | PASS carrier | 保留 stage index，不要在 reward adaptation 中重排 stage meaning。 |
| Advance routing | `StagedTaskBase._post_compute_observations_callback()` | 每步检查 `_stage_{i}_to_{i+1}_advance_condition()`；advance 后 `stage_buf += 1`，reset 当步不 advance | PASS carrier | 新 condition 必须返回 `(num_envs,)` bool tensor；不要用 fallback 强行继续。 |
| Stage timing | `door_open_homie.yaml` / `door_open_a2_base.yaml` | `max_stage_time=[250,100,100,100,100,200]` | PASS carrier | 若 stage1/2 新 correctness 变严格，先观察 overtime，不要随手放宽 timer。 |
| Remaining time award | `award_remaining_time_on_advance=True` | advance 时扣当前 stage max time，保留 StagedTaskBase 语义 | PASS carrier | 改 transition 前后都要观察 `time_in_stage` / `actual_time_in_stage`。 |
| Complete reset | `reset_on_complete=True`, `reset_on_complete_delay=50.0` | complete 后延迟 reset，delay 为 50 | PASS carrier | stage5 complete 不要提前替代 stage1/2 correctness。 |
| Stage reward carrier | `StagedTaskBase._reward_stage()` | `stage` reward 依赖当前 stage reward condition，不是 pure alive bonus | PASS carrier | stage reward 的 correctness 由各 stage reward condition 决定。 |

## Transition Mapping Table

| Stage edge / condition | Origin G1/HOMIE logic | Current A2 logic | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| `_stage_0_reward_condition()` | Stage0 恒 True，walk-to-door stage 内一直满足 stage reward condition | A2 同样恒 True | PASS carrier | 无需改；stage0 reward correctness 见 `g1_doorman_stage0_reward_transition.md`。 |
| `_stage_0_to_1_advance_condition()` | G1: Root XY 到 `grasp_target` 距离 `<0.3`，且 upper non-finger max deviation `<0.25` | A2: 平面距离阈值改为 `<0.6m`，避免 A2 base/trunk 为满足 G1 人形距离阈值而撞门；`_compute_grasp_target()` 读取 Piper `piper_gripper_handle_frame_transformer` target `handle`；arm stability 使用 `_upper_non_gripper_dof_idx` / `arm_j1..j6`，排除 `arm_j7/arm_j8` | PASS correctness | 后续 smoke 重点看 root-to-handle false-positive、Piper reach envelope、base/trunk 是否仍碰门。 |
| `_stage_1_reward_condition()` | command norm `<=0.1` 且仍满足 stage0 -> 1 boundary | A2 使用同一 carrier：`get_physical_homie_commands()[:, :3]` norm `<=0.1` + A2 stage0 boundary；因此也继承 `<0.6m` near-handle window | PASS carrier | 这只说明 pregrasp 阶段要求 base 不乱动且保持在 A2-safe approach window；不代表 Piper TCP 已到 pregrasp。 |
| `_stage_1_to_2_advance_condition()` | pregrasp correctness：selected palm z `> handle_height+0.05`，palm-pregrasp distance `<0.1`，finger p0 mean error `<0.174533`，`hand_handle_orientation >0.2`，command norm `<=0.1`；OR door hinge `>0.174533` | A2 `_use_a2_base` path 目前直接返回 `door.joint_pos[:,0] > 0.174533`；`gripper_handle_orientation` reward metric 已实现但尚未接入 transition | TODO / placeholder, primary blocker | 必须用 Piper TCP/pregrasp target、gripper aperture/readiness、raw orientation metrics 和 base stillness 重建 correctness；door-open shortcut 可保留为 OR，但不能是唯一通路。 |
| `_stage_2_reward_condition()` | command norm `<=0.1` | A2 同样使用 command norm carrier | PASS carrier | 只覆盖 grasp 阶段 base stillness；grasp correctness 另看 `_stage_2_to_complete_condition()`。 |
| `_stage_2_to_complete_condition()` | handle contact count `>=4`，按 selected hand 判断 grasped | A2 `_use_a2_base` path 返回 all false | TODO / placeholder, primary blocker | 需要基于 `arm_body7`/`arm_body8` contact force、aperture、handle relative stability 设计 Piper grasp completion。 |
| `_stage_2_to_3_advance_condition()` | `_stage_2_to_complete_condition()` OR door hinge `>0.174533` | 因 A2 complete all false，实际只剩 door hinge shortcut | TODO / placeholder | 重写 stage2 grasp completion 后再允许 hinge shortcut 作为 escape；检查 shortcut 触发比例。 |
| `_stage_3_reward_condition()` | keep grasping: `_stage_2_to_3_advance_condition()` AND `_stage_2_reward_condition()` | A2 继承同一 carrier，但 upstream grasp completion placeholder 会污染语义 | TODO dependent | stage2 grasp 完成前不要把 stage3 correctness 标成 PASS。 |
| `_stage_3_to_4_advance_condition()` | door hinge `>0.174533` | A2 同 threshold | PASS carrier | 该 edge robot-agnostic，但必须等 stage2 grasp correctness 完成后再评估是否过早 open。 |
| `_stage_4_reward_condition()` | keep grasping/opened carrier：复用 `_stage_3_to_4_advance_condition()` | A2 同 threshold | PASS carrier | 后续 review 应结合 handle/door contact semantics，不要只看 hinge。 |
| `_stage_4_to_5_advance_condition()` | root x passes door `>0.0`，door hinge `>1.0472`，handle joint `<0.2` | A2 同 logic：`robot_root_states[:,0] - env_origins[:,0] > 0.0`，hinge/handle thresholds unchanged | PASS carrier, later review | 等 swing/open reward 完成后再做 correctness；A2 body length/door crossing margin 可能需要 smoke 校准。 |
| `_stage_5_reward_condition()` | keep walking through door，复用 stage4 -> 5 condition | A2 同 carrier | PASS carrier | 不要用 stage5 condition 掩盖 earlier stage shortcut。 |
| `_stage_5_to_complete_condition()` | root x `>1.5` relative to env origin | A2 同 threshold | PASS carrier, later review | A2 尺寸和 gait cadence 可能影响 success timing；待 full episode smoke。 |

## Stage1 -> Stage2 A2 Correctness Checklist

| 检查项 | Origin 语义 | A2 可用 source | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| Target source | `_compute_pre_grasp_target()` = `grasp_target + Z 0.1m` | A2 `_compute_pre_grasp_target()` 读取 `piper_gripper_handle_frame_transformer` target `pregrasp`，source frame 是 `/Robot/arm_body6_to_gripper` + TCP offset `(0,0,0.105)` | PASS carrier | 保持 fail-fast：target order 必须是 `["handle", "pregrasp"]`，`target_obj_transform_sub_prim_path` 必须是 `grasp_target`。 |
| Height above handle | selected palm z `> handle_height+0.05` | Piper TCP/pregrasp target and `door_handle_height` | TODO | 用 Piper TCP 或 gripper center frame 替代 G1 palm；不要读 G1 left/right palm indices。 |
| Pregrasp distance | palm to pregrasp distance `<0.1` | `gripper_handle_transform` / frame transformer source-relative target pose | TODO | 优先用 TCP-to-pregrasp distance；threshold 可先对齐 `0.1`，再 smoke 调参。 |
| Finger p0 readiness | selected finger p0 mean error `<0.174533` | A2 gripper `arm_j7/arm_j8` aperture / primitive state | TODO | 不要直接复用 G1 finger p0；定义 Piper pregrasp aperture/readiness，避免把 fully closed 当 grasp correctness。 |
| Hand-handle orientation -> gripper-handle orientation | `_reward_hand_handle_orientation() > 0.2` | A2 `gripper_handle_orientation` 已实现：读取 `piper_gripper_handle_frame_transformer.data.target_quat_source[:, 1, :]`，使用 source local `+Y` opening axis、source local `+Z` approach axis 和用户选定 `+Z` approach sign，输出 raw `opening_alignment` / `approach_alignment` 以及 product reward | PASS reward metric; TODO transition | 后续 `_stage_1_to_2_advance_condition()` 应复用 raw orientation metrics，而不是只看 reward scalar；当前 A2 stage1 -> 2 仍是 hinge shortcut，transition correctness 未完成。 |
| Base stillness | command norm `<=0.1` over physical command `[:3]` | A2 compatibility carrier `get_physical_homie_commands()[:, :3]` | PASS carrier | 语义是禁止 translate/yaw；pitch/roll 是否也要约束，留给 smoke/review。 |
| Door-open shortcut | hinge `>0.174533` | `door.data.joint_pos[:,0]` | PASS carrier only | 可以作为 OR shortcut，但不应是唯一 advance route。 |

## Stage2 -> Stage3 Grasp Correctness Checklist

| 检查项 | Origin 语义 | A2 可用 source | A2适配状态 | 开发/检查建议 |
|---|---|---|---|---|
| Grasp contact | selected hand handle contact count `>=4` | `arm_body7` / `arm_body8` gripper contact bodies, `hand_force` obs replacement, door/handle contact sensors if available | TODO / placeholder | 设计双侧 contact 或 stable handle constraint；不要照搬 G1 4-finger count。 |
| Premature/incorrect contact | Stage1 `grasp` reward 对 contact reward 取 `-abs(reward)` | A2 `grasp` scale `0.0` and `_reward_grasp()` returns zeros in A2 path | TODO | stage1 应惩罚早碰/侧向撞击，stage2+ 才奖励稳定 grasp。 |
| Aperture readiness | G1 grasp finger p1 / contact 配套 | A2 gripper aperture / primitive target / actual `arm_j7/arm_j8` | TODO | grasp 完成不要奖励完全闭合；更应看合适 aperture、双侧接触、contact force 不过大。 |
| Door-open shortcut | hinge `>0.174533` | `door.data.joint_pos[:,0]` | PASS carrier only | shortcut 保留后需要统计它是否绕过真实 grasp。 |

## 人工验收建议

| 验收项 | A2适配状态 | 开发/检查建议 |
|---|---|---|
| Static source review | TODO | 修改后 grep `_stage_1_to_2_advance_condition`，确认 A2 path 不再只有 hinge shortcut。 |
| Static source review | TODO | 修改后 grep `_stage_2_to_complete_condition`，确认 A2 path 不再 `torch.zeros(...)` all false。 |
| Config review | PASS reward metric / remaining TODO | `gripper_handle_orientation: +3.0` 已启用并替换旧 `hand_handle_orientation`；`pregrasp_target_distance` / `grasp` 后续开启时继续同步检查 `reward_door_open_a2_base.yaml` scale 和 `reward_penalty_reward_names`。 |
| Bounded smoke | TODO | 只在 code 完成后运行；记录 stage transition cadence、door-open shortcut rate、overtime/reset reason、stage reward magnitude。 |
| Fail-fast policy | PASS requirement | 缺少 Piper frame/contact/body source 时应直接 raise，不要 fallback 到 G1 palm/finger 或 zeros。 |
