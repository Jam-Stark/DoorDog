# G1 Doorman Teacher Privileged Observation 与 A2_Piper Adaptation Map

Last updated: 2026-06-16 HKT

本文单独展开原版 G1/HOMIE Doorman Teacher PPO privileged observation contract，作为后续 A2_Piper Teacher PPO observation redesign 的 source map。Ava 已对 Doorman origin code 做只读核查；main agent 对当前 A2 worktree 做交叉复核。

Source-of-truth:

- G1 obs config: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/obs/wbmanip/door_open_homie.yaml`
- G1 teacher experiment: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/exp/wbmanip/door_open_homie_lstm.yaml`
- G1 door env: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- G1 base obs helpers: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/legged_base_task/legged_robot_base.py`
- Current A2 obs config: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`
- Current A2 door env: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`
- Current A2 base/action helpers: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/base_task/a2_base.py`

## 0. Reading Notes

| 项目 | 结论 |
|---|---|
| G1 actor membership | `door_open_homie.yaml:6-23` |
| G1 critic membership | `door_open_homie.yaml:25-49`；比 actor 多 5 个 critic-only stage/time terms |
| A2 current membership | `door_open_a2_base.yaml:6-49` 保留 G1 teacher skeleton，但 `hand_handle_transform` 已 rename 为 `gripper_handle_transform`；另有 A2-only `a2_base_obs` group at `:64-66` |
| concat order caveat | 实际 observation concat order 不是 YAML 书写顺序，而是 `sorted(obs_config)`；见 `legged_robot_base.py:1213-1218` |
| G1 actor dim | `246D` |
| G1 critic dim | `251D` |
| A2 current actor dim | `133D` |
| A2 current critic dim | `138D` |
| 核心风险 | A2 `hand_force`、`gripper_handle_transform`、5D `a2_base_command` / `a2_base_command_raw` 与 critic-only stage/time terms 已有 Piper/A2 或 robot-agnostic PASS；Teacher PPO obs carrier/input contract phase complete。后续风险转向 train smoke、normalization/RMS validation、gripper aperture/contact/grasp enhancement、stage1+ transition/reward correctness 与 actor/critic privileged split |

## 1. Teacher Privileged Observation Term Table

| Obs term | Actor/Critic | Shape / dim | Origin source/config | Origin getter/function | G1 语义/作用 | A2 当前状态 | A2 适配建议/风险 |
|---|---:|---:|---|---|---|---|---|
| `dof_pos` | both | G1 `43` / A2 `20` | G1 dim `door_open_homie.yaml:205`; A2 dim `door_open_a2_base.yaml:211` | `LeggedRobotBase._get_obs_dof_pos()` at `legged_robot_base.py:1767-1770` | full robot DOF position relative default | `PASS`: A2 full 20D，12D legs + 8D Piper arm/gripper，保持 G1 full-robot parity | 当前按用户决策保留 full A2 robot getter；后续若重构 semantic obs，可另拆 `arm/gripper proprio`，但本批不改。 |
| `dof_vel` | both | G1 `43` / A2 `20` | G1 dim `door_open_homie.yaml:208`, scale `:127`; A2 dim `door_open_a2_base.yaml:214`, scale `:131` | `LeggedRobotBase._get_obs_dof_vel()` at `legged_robot_base.py:1772-1775` | full robot joint velocity，obs scale `0.05` | `PASS`: A2 full 20D，保持 G1 full-robot parity | 当前按用户决策保留 full A2 robot getter；leg velocity 同时也存在于独立 `a2_base_obs`，但 `a2_base_obs` 不混入 Teacher actor/critic obs。 |
| `actions` | both | G1 `31` / A2 `19` | G1 dim `door_open_homie.yaml:209`; G1 exp override `actions_dim: 31` at `door_open_homie_lstm.yaml:124-126`; A2 dim expression `door_open_a2_base.yaml` = `a2_base.leg_action_dim + manipulation_action_dim` | G1 `LeggedRobotBase._get_obs_actions()` at `legged_robot_base.py:1874-1877`; A2 override `A2Base._get_obs_actions()` | G1 action surface = HOMIE lower-body + upper/finger primitive action surface | `PASS`: A2 parity action surface `19D = 12D A2_Base leg output + 6D effective Piper arm action + 1D gripper primitive raw` | 不含 base command；base command 通过 5D `a2_base_command` / `a2_base_command_raw` obs 暴露。不含 expanded gripper joint target，也不再暴露 final simulator `20D` action。 |
| `projected_gravity` | both | `3` | G1 dim `door_open_homie.yaml:210`; A2 dim `door_open_a2_base.yaml:217` | `LeggedRobotBase._get_obs_projected_gravity()` at `legged_robot_base.py:1762-1765`; updated in callback at `:819` | base-frame gravity，用于姿态感知 | `PASS`: direct reuse | 直接来自 A2 `trunk`/base quaternion 和 gravity vector；无需 code adaptation。若后续 high-level action 输出 body pitch/roll command，也应保留。 |
| `base_lin_vel` | both | `3` | G1 dim `door_open_homie.yaml:212`; A2 dim `door_open_a2_base.yaml:219` | `LeggedRobotBase._get_obs_base_lin_vel()` at `legged_robot_base.py:1752-1755`; base-frame compute at `:800-802` | privileged base linear velocity | `PASS`: direct reuse | root linear velocity 转到 A2 `trunk`/base frame；无需 code adaptation。Teacher PPO privileged obs 可保留；Student vision route 后续是否可见另议。 |
| `base_ang_vel` | both | `3` | G1 dim `door_open_homie.yaml:213`; A2 dim `door_open_a2_base.yaml:220` | `LeggedRobotBase._get_obs_base_ang_vel()` at `legged_robot_base.py:1757-1760`; base-frame compute at `:804-806` | privileged base angular velocity | `PASS`: direct reuse | root angular velocity 转到 A2 `trunk`/base frame；无需 code adaptation。 |
| `relative_to_door` | both | `9` | G1 dim `door_open_homie.yaml:207`; A2 dim `door_open_a2_base.yaml:213` | G1 precompute `door_open_homie.py:212`; getter `door_open_homie.py:647-649`; A2 getter `door_open_a2_base.py:775-777` | robot root frame -> door root position + 6D rotation；door z replaced by robot root z | `PASS with caveat`: direct reuse | 可复用为 A2 `trunk`/base-door navigation term；无需 code adaptation。但它不等价于 EE/handle task frame，Teacher short-term obs 仍应新增 Piper EE/gripper relative-to-handle observation。 |
| `door_dof_pos` | both | `2` | G1 dim `door_open_homie.yaml:211`; A2 dim `door_open_a2_base.yaml:218` | G1 `DoorPregrasp._get_obs_door_dof_pos()` at `door_open_homie.py:688-689`; A2 at `door_open_a2_base.py:820-821` | door articulation DOF，通常为 hinge/handle state 前两维 | `PASS`: direct reuse | Door-general term，与 robot 无关；无需 code adaptation。若后续 door asset/DOF order 改动，再显式拆分 `door_hinge_pos`、`handle_pos`。 |
| `hand_force` | both | G1 `48` / A2 `6` | G1 dim `door_open_homie.yaml:206`; A2 dim `door_open_a2_base.yaml:212` | G1 `DoorPregrasp._get_obs_hand_force()` at `door_open_homie.py:662-671`; A2 `DoorPregrasp._get_obs_hand_force()` reads `contact_forces[:, [arm_body7, arm_body8], :]` | G1 left/right hand contact forces flatten，`2 * 8 * 3` | `PASS`: A2 name-based binds Piper `arm_body7`/`arm_body8` and returns 6D gripper net/body force; missing body fail-fast | No zero padding, no 48D compatibility。保持 scale `0.01`、noise `0.0`；后续可另加 aperture/contact/grasp binary cues，但本 term 已完成 strict replacement。 |
| `gripper_handle_transform` | both | `18` | A2 dim `door_open_a2_base.yaml:223`; replaces G1 `hand_handle_transform` | A2 `DoorPregrasp._get_obs_gripper_handle_transform()` reads `piper_gripper_handle_frame_transformer`; old `_get_obs_hand_handle_transform()` raises in A2 mode | Piper TCP/source frame -> handle and pregrasp target frames，each `pos3 + rot6` | `PASS`: 18D `[handle pos3+rot6, pregrasp pos3+rot6]` from `arm_body6_to_gripper` source offset and target-side `grasp_target +Z 0.10m` pregrasp offset | Sorted obs order changes because key rename moves this term before `hand_force`。A2 config 不再引用 `hand_handle_transform`；旧 key 不提供 zero compatibility。 |
| `privileged_door_info` | both | `8` | G1 dim `door_open_homie.yaml:215`; A2 dim `door_open_a2_base.yaml:222` | G1 getter `door_open_homie.py:673-686`; A2 getter `door_open_a2_base.py:805-818` | door width/height/handle height/handle width/weight/open direction | `PASS` | Door-general privileged term，可复用给 teacher actor/critic；student route 后续需决定是否移除。 |
| `stage` | both | `6` | G1 dim `door_open_homie.yaml:214`; A2 dim `door_open_a2_base.yaml:221` | `StagedTaskBase._get_obs_stage()` at `staged_task_base.py:296-297` | current stage one-hot | `PASS` | Stage obs 本身可复用；stage1+ transition semantics 仍另行设计。 |
| `delta_actions` | both | G1 `19` / A2 `6` | G1 dim `door_open_homie.yaml:231`; A2 dim `door_open_a2_base.yaml:239`; origin `delta_action_indices` comes from env config | `DeltaActionBase._get_obs_delta_actions()` at `delta_action_base.py:128-129` | raw delta policy action before accumulation；G1 covers base + arms + finger primitive | `PASS with A2-specific semantics: 6D Piper arm raw delta only` | 仅覆盖 high-level `action[5:11]` 的 Piper arm raw delta；excludes 5D base command and 1D gripper primitive。 |
| `a2_base_command_raw` | both | G1 origin `unwarped_actions` `3` / A2 `5` | G1 dim `door_open_homie.yaml:232`; A2 dim `door_open_a2_base.yaml:240` | A2 `A2Base._get_obs_a2_base_command_raw()` returns `WarpedActionBase._unwarped_actions`; G1 source getter `WarpedActionBase._get_obs_unwarped_actions()` | raw base command before warp；origin warp currently disabled by config (`k=0.0`, `s=0.0`) | `PASS`: A2 5D raw high-level base action `[x,y,yaw,pitch,roll]` from `warped_action.indices=[0..4]`, before warp/scale/clip | Public A2 name now makes raw command semantics explicit while preserving origin relation to G1 `unwarped_actions`。 |
| `a2_base_command` | both | G1 origin `b_homie_commands` `7` / A2 `5` | A2 dim `door_open_a2_base.yaml:224`; replaces old A2 `base_command` and older `b_homie_commands` public keys | A2 `A2Base._get_obs_a2_base_command()`; compatibility `_get_obs_base_command()` / `_get_obs_b_homie_commands()` remain internal aliases | scaled/clipped physical base command obs | `PASS`: `[x,y,yaw,pitch,roll]` processed/clipped physical command scaled by `[2,2,0.25,1,1]`; small-command zeroing affects only velocity/yaw obs `[0:3]`, not pitch/roll | Actor/critic dims remain `133D/138D` because old 7D G1/HOMIE command compatibility obs became 5D while raw command obs is 5D。 |
| `transition` | critic only | `1` | G1 dim `door_open_homie.yaml:226`; A2 dim `door_open_a2_base.yaml:234` | `StagedTaskBase._get_obs_transition()` at `staged_task_base.py:313-314` | current step 是否刚进入新 stage | `PASS: direct reuse` | Critic-only obs carrier 可复用；getter 只读 `StagedTaskBase` stage bookkeeping，不读 robot/joint/body/contact。Caveat: stage1+ transition correctness 不由该 getter 保证，另属 transition/reward design。 |
| `complete` | critic only | `1` | G1 dim `door_open_homie.yaml:227`; A2 dim `door_open_a2_base.yaml:235` | `StagedTaskBase._get_obs_complete()` at `staged_task_base.py:316-317` | task complete flag | `PASS: direct reuse` | Critic-only obs carrier 可复用；getter 只读 `StagedTaskBase` completion bookkeeping，不读 robot/joint/body/contact。Caveat: task completion semantics 仍取决于 A2 stage machine / reward design。 |
| `time_in_stage` | critic only | `1` | G1 dim `door_open_homie.yaml:228`; A2 dim `door_open_a2_base.yaml:236` | `StagedTaskBase._get_obs_time_in_stage()` at `staged_task_base.py:299-302` | normalized stage time，使用 `time_in_stage_buf / max_stage_time[stage]` | `PASS: direct reuse` | Obs carrier/normalization 可复用；getter 只读 `StagedTaskBase` timer bookkeeping，不读 robot/joint/body/contact。Caveat: stage timeout/curriculum 是否合理仍随 stage1+ transition/reward design 另行核查。 |
| `actual_time_in_stage` | critic only | `1` | G1 dim `door_open_homie.yaml:229`; A2 dim `door_open_a2_base.yaml:237` | `StagedTaskBase._get_obs_actual_time_in_stage()` at `staged_task_base.py:307-311` | normalized actual time since stage entered | `PASS: direct reuse` | Obs carrier/normalization 可复用；getter 只读 `StagedTaskBase` timer bookkeeping，不读 robot/joint/body/contact。Caveat: stage machine correctness 不由该 getter 保证。 |
| `total_time` | critic only | `1` | G1 dim `door_open_homie.yaml:230`; A2 dim `door_open_a2_base.yaml:238` | `StagedTaskBase._get_obs_total_time()` at `staged_task_base.py:304-305` | normalized total episode/stage time | `PASS: direct reuse` | Obs carrier/normalization 可复用；getter 只读 `StagedTaskBase` timer bookkeeping，不读 robot/joint/body/contact。Caveat: episode/stage transition/reward semantics 仍另行设计。 |
| `a2_base_obs` | A2-only group | `1620` | A2 obs group `door_open_a2_base.yaml:64-66`; dim `:233` | `A2Base._get_obs_a2_base_obs()` at `a2_base.py:777-797`; frame layout `a2_base.py:763-775` | 不存在于 G1 teacher privileged obs | 已完成，用于 frozen A2_Base trainer inference | 不应直接混进 Teacher door policy `actor_obs`。它服务 low-level dog policy；其中 `arm_command_obs` 当前仍是 zero at `a2_base.py:657-664`。 |

## 2. Dim And Order

G1 YAML membership order:

- Actor: `dof_pos`, `relative_to_door`, `dof_vel`, `actions`, `projected_gravity`, `door_dof_pos`, `base_lin_vel`, `base_ang_vel`, `hand_force`, `stage`, `privileged_door_info`, `delta_actions`, `hand_handle_transform`, `unwarped_actions`, `b_homie_commands`
- Critic: actor terms plus `transition`, `complete`, `time_in_stage`, `actual_time_in_stage`, `total_time`

A2 current YAML membership order keeps the same skeleton except `hand_handle_transform` is renamed to `gripper_handle_transform`, G1-origin `unwarped_actions` is public `a2_base_command_raw`, and old A2 `base_command` / `b_homie_commands` command obs is public `a2_base_command`.

A2 current concat order after `sorted(obs_config)`:

- Actor: `a2_base_command`, `a2_base_command_raw`, `actions`, `base_ang_vel`, `base_lin_vel`, `delta_actions`, `dof_pos`, `dof_vel`, `door_dof_pos`, `gripper_handle_transform`, `hand_force`, `privileged_door_info`, `projected_gravity`, `relative_to_door`, `stage`
- Critic: `a2_base_command`, `a2_base_command_raw`, `actions`, `actual_time_in_stage`, `base_ang_vel`, `base_lin_vel`, `complete`, `delta_actions`, `dof_pos`, `dof_vel`, `door_dof_pos`, `gripper_handle_transform`, `hand_force`, `privileged_door_info`, `projected_gravity`, `relative_to_door`, `stage`, `time_in_stage`, `total_time`, `transition`

Dim calculation:

| Contract | Calculation | Total |
|---|---|---:|
| G1 actor | `43 + 9 + 43 + 31 + 3 + 2 + 3 + 3 + 48 + 6 + 8 + 19 + 18 + 3 + 7` | `246` |
| G1 critic | `G1 actor 246 + transition/complete/time_in_stage/actual_time_in_stage/total_time` | `251` |
| A2 current actor | `20 + 9 + 20 + 19 + 3 + 2 + 3 + 3 + 6 + 6 + 8 + 6 + 18 + 5 + 5` | `133` |
| A2 current critic | `A2 actor 133 + transition/complete/time_in_stage/actual_time_in_stage/total_time` | `138` |

Important dimension caveat:

- G1 robot config default has `actions_dim: 43`, but teacher experiment overrides `robot.actions_dim: 31` when `use_primitive: True`; see `door_open_homie_lstm.yaml:124-126`.
- A2 experiment keeps simulator `robot.actions_dim: 20`, but Teacher `actions` obs now uses `19D = 12D leg + 6D arm + 1D gripper primitive` so it matches the A2/G1 policy action surface rather than the final simulator command.
- A2 `actions` obs intentionally excludes base command and expanded gripper joint targets.

## 3. A2 Teacher PPO Short-Term Design Implications

Already PASS / direct reuse for Teacher PPO:

- `projected_gravity`
- `base_lin_vel`
- `base_ang_vel`
- `relative_to_door` for base-door navigation
- `door_dof_pos`
- `privileged_door_info`
- `stage`
- critic-only `transition`, `complete`, `time_in_stage`, `actual_time_in_stage`, `total_time`

The five critic-only stage/time terms are `PASS: direct reuse` because they are robot-agnostic `StagedTaskBase` stage/timer bookkeeping getters. Their obs carrier/normalization can be reused directly; this does not validate stage1+ transition correctness or reward semantics, which remain a separate transition/reward design task.

Completed strict replacements:

- `gripper_handle_transform`: `PASS` as 18D TCP-to-handle/pregrasp pose term.
- `hand_force`: `PASS` as 6D Piper gripper body force term.
- Post-finish contact/grasp enhancement: add gripper aperture/contact presence/grasp cues separately if stage1 reward/transition design needs them; do not overload the completed strict replacements.

Command terms:

- `a2_base_command_raw`: `PASS` as 5D raw high-level `[x,y,yaw,pitch,roll]` command before warp/scale/clip, derived from origin `unwarped_actions` semantics.
- `a2_base_command`: `PASS` as 5D processed/clipped physical `[x,y,yaw,pitch,roll]` command obs scaled by `[2,2,0.25,1,1]`；small-command zeroing only affects velocity/yaw `[0:3]`。
- `actions`: current A2 Teacher obs is now the 19D parity action surface: frozen A2_Base leg output + effective Piper arm action + raw gripper primitive. Base command remains in `a2_base_command` / `a2_base_command_raw` rather than `actions`。
- `dof_pos` / `dof_vel`: current Teacher parity keeps full A2 20D robot state. If the schema is later cleaned up, it can be split into explicit `arm/gripper proprio` terms without changing this batch's contract.

Post-finish A2 Teacher obs enhancement candidates:

- Piper arm/gripper proprioception: `arm_j1..arm_j6`, `arm_j7/arm_j8`, velocities, aperture.
- Piper EE/handle relation: EE pose and orientation relative to handle/pregrasp target, ideally pos + 6D rotation.
- Door/handle state: hinge, handle joint, door opening direction and dimensions.
- Base/door navigation: base-door relative pose, base velocity, projected gravity, `a2_base_command_raw` / `a2_base_command`.
- Action memory: last high-level `12D` action or split `a2_base_command_raw`, `arm_delta_action`, `gripper_primitive`.
- Contact/grasp cues: Piper gripper contact/force features, not G1 left/right hand force flatten.

## 4. Current A2 Status Summary

| 类别 | A2 状态 | Note |
|---|---|---|
| Network skeleton | `PASS` | Teacher PPO `RecurrentActor` / `RecurrentCritic` can keep G1 origin architecture. |
| Actor output dim | `PASS` | Current high-level output is `12D = 5D base [x,y,yaw,pitch,roll] + 6D Piper arm + 1D gripper primitive`; trainer rollout is `24D`; final simulator command remains `20D`. |
| Low-level locomotion obs/action | `PASS` | `a2_base_obs: 1620D` and frozen A2_Base policy are complete and visually smoke-checked. |
| Teacher `dof_pos/dof_vel/actions` parity | `PASS` | `dof_pos/dof_vel` keep full A2 20D; `actions` is now 19D A2/G1 parity surface with no base command and no expanded gripper joint target. |
| Teacher base/door state obs | `PASS` | `projected_gravity`、`base_lin_vel`、`base_ang_vel`、`relative_to_door`、`door_dof_pos` direct reuse；`relative_to_door` 只作为 base-door navigation，不替代 Piper EE/handle obs。 |
| Teacher gripper/handle obs | `PASS` | `hand_force` 为 A2 gripper net/body force 6D；`gripper_handle_transform` 为 TCP-to-handle/pregrasp 18D。 |
| High-level Teacher actor obs | `PASS / phase complete` | Teacher PPO obs carrier/input contract 当前为 `133D` actor；active terms 均已有 A2 mapping、direct reuse、strict replacement 或 A2-specific semantics。PPO train smoke、normalization/RMS validation、gripper aperture/contact/grasp cues 与 actor/critic privileged split 是 post-finish enhancement/validation，不是当前 obs adaptation blocker。 |
| High-level Teacher critic obs | `PASS / phase complete` | Teacher PPO obs carrier/input contract 当前为 `138D` critic；critic-only `transition/complete/time_in_stage/actual_time_in_stage/total_time` 已 `PASS: direct reuse` via `StagedTaskBase`。该 PASS 不代表 stage1+ transition/reward correctness 已完成，后者转入下一阶段。 |
| Student/vision obs | `TODO` | Deferred until Teacher PPO experiment route is settled. |
