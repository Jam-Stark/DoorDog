# G1 Doorman Policy Stack 与 A2 Adaptation Map

Last updated: 2026-06-16 HKT

本文是给后续设计 A2_Piper door policy / arm policy 的 source map。Ava 已对 Doorman origin code 做只读核查；main agent 对当前 A2 worktree 做了交叉复核。Reward build 暂缓，本文件只列 policy network、action、observation、trainer/env routing、stage/sensor 配套，以及当前 A2 adaptation 状态。

## 0. 状态标记

- `PASS`: 已完成 A2 适配，可作为当前 baseline。
- `PARTIAL`: 结构可复用或 shape 可运行，但语义仍需重新设计。
- `TODO`: 尚未 A2 化，不能直接用于训练。
- `KEEP`: origin 结构可保留，后续按 A2 obs/action contract 填内容。
- `DO NOT REUSE`: G1/HOMIE-specific 或 checkpoint/shape 不兼容。

## 1. Entrypoint / Hydra Routing

| 类别 | G1 Doorman origin | 当前 A2 状态 | A2适配状态 | 备注 |
|---|---|---|---|---|
| Teacher PPO experiment | `GR00T-VisualSim2Real/gr00t/rl/config/exp/wbmanip/door_open_homie_lstm.yaml` | `DoorDog-A2_Piper/gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml` | `PASS / not train-smoked` | 已切到 `/env: door_open_a2_base`、`/robot: A2_Piper/a2_piper`、`/trainer: trl_a2_base_api`。尚未做 PPO train smoke。 |
| Student DAgger vision experiment | `GR00T-VisualSim2Real/gr00t/rl/config/exp/wbmanip/door_open_homie_dagger-lstm.yaml` | 当前 worktree 仍有 `door_open_homie_dagger-lstm.yaml` | `TODO` | 仍依赖 G1 env/obs/action/teacher checkpoint；不能直接用于 A2。 |
| Train entrypoint | `gr00t/rl/train_agent_trl.py` | 同路径复用 | `KEEP` | Hydra instantiate env / actor / trainer 的入口可复用。 |
| Eval entrypoint | `gr00t/rl/eval_agent_trl.py` | 同路径复用 | `KEEP` | 从 checkpoint sidecar config 恢复再 merge eval overrides；A2 checkpoint 产生前不验证。 |
| Teacher trainer | `config/trainer/trl_homie_api.yaml` -> `ppo_trainer_homie_api.TRLPPOTrainer` | `config/trainer/trl_a2_base_api.yaml` -> `ppo_trainer_a2_base_api.TRLPPOTrainer` | `PASS` | A2 trainer 加载 frozen A2_Base，而不是 HOMIE `model_walk.pt/model_stand.pt`。 |
| Student trainer | `config/trainer/trl_distill_obj_pred_homie_api.yaml` | 仍是 HOMIE/student route | `TODO` | 后续要设计 A2 teacher checkpoint、A2 obs/action、A2 camera/body mounting。 |

## 2. Network Structure

### 2.1 Teacher PPO Actor/Critic

G1 origin:

- Config: `GR00T-VisualSim2Real/gr00t/rl/config/exp/wbmanip/door_open_homie_lstm.yaml`
- Actor: `gr00t.rl.trl.modules.actor_critic_modules_recurrent.RecurrentActor`
- Critic: `gr00t.rl.trl.modules.actor_critic_modules_recurrent.RecurrentCritic`
- Network:
  - `running_mean_std: True`
  - `rnn_type: lstm`
  - `rnn_hidden_dim: 256`
  - `rnn_num_layers: 2`
  - MLP hidden dims `[512, 256, 128]`
  - Actor output dim = `homie_command_dim + non_homie_command_actions_dim = 3 + 16 = 19`
  - Critic output dim = `1`
- Code: `GR00T-VisualSim2Real/gr00t/rl/trl/modules/actor_critic_modules_recurrent.py`

A2 current:

- Config: `DoorDog-A2_Piper/gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml`
- Actor/Critic skeleton 保持 `RecurrentActor` / `RecurrentCritic`。
- Actor output dim = `base_command_dim + manipulation_action_dim = 5 + 7 = 12`。
- `A2适配状态: PASS / phase complete for Teacher PPO obs-action contract`
  - Recurrent PPO skeleton 已可复用。
  - output dim 已改成 A2 high-level 12D。
  - door policy `actor_obs/critic_obs` 当前为 `133D/138D`，active terms 均已有 A2 mapping、direct reuse、strict replacement 或 A2-specific semantics。gripper aperture/contact/grasp cues、actor/critic privileged split、normalization/RMS 与 train smoke 属于 post-finish enhancement/validation；stage1+ reward/transition correctness 另属下一阶段。

### 2.2 Student Vision / DAgger

G1 origin:

- Config: `GR00T-VisualSim2Real/gr00t/rl/config/exp/wbmanip/door_open_homie_dagger-lstm.yaml`
- Actor: `gr00t.rl.trl.modules.vision_actor_critic_modules_obj_pred_recurrent.VisionRecurrentActorObjPred`
- Vision:
  - `vision_obs: rgb_image`
  - camera resolution `[216, 384]`
  - ResNet18 pretrained, trainable
  - `vision_feature_dim: 128`
- Student actor obs: compact proprioception + `b_homie_commands` + `complete`
- Teacher actor: recurrent state teacher loaded from `teacher_actor_path`
- Object predictor: `obj_pred_mlp output_dim: 3`; current config `obj_pred_loss_coef: 0.0`

A2 current:

- `A2适配状态: TODO`
- A2 teacher PPO checkpoint 还不存在。
- A2 student obs/action contract 还没设计。
- origin `teacher_actor_path` 是 G1/HOMIE checkpoint，不能复用。
- origin camera attached link 为 `d435_link`，A2_Piper 是否有同名 camera mount 需要重审。

## 3. Action Contract

### 3.1 G1 Origin Action Flow

| 层级 | 维度 | 来源 | 代码/配置 |
|---|---:|---|---|
| Teacher high-level policy action | `19D` | `3D loco_vel + 14D upper-body arms + 2D finger primitives` | `door_open_homie_lstm.yaml`, `homie_command_dim: 3`, `non_homie_command_actions_dim: 16` |
| HOMIE lower-body action | `15D` | frozen `model_walk.pt/model_stand.pt` | `ppo_trainer_homie_api.py`, `homie_modules.py` |
| Trainer rollout/env action | `34D` | `19D policy + 15D HOMIE` | `ppo_trainer_homie_api.TRLPPOTrainer.policy_step` |
| Env final robot action | `31D` | `15D lower-body + 14D upper non-finger + 2D finger primitive` | `HomieBase.step`, `FingerPrimitiveBase._apply_force_in_physics_step` |

Origin action details:

- `door_open_homie.yaml` 中 `delta_action_indices` 覆盖 policy 19D，origin policy action 全部走 delta accumulation。
- `warped_action.indices: [0, 1, 2]` 只包住 base command，但 `k=0.0, s=0.0`，实际不改变值。
- `HomieBase.step()` 把 active high-level action 写入 7D `homie_commands` + 16D non-HOMIE command buffer，再拼上 HOMIE lower-body action。
- `FingerPrimitiveBase` 是 raw primitive -> over-limit buffer -> clamp -> linear/discrete map 到 G1 finger DOF target。

### 3.2 A2 Current Action Flow

| 层级 | 维度 | 来源 | A2适配状态 | 代码/配置 |
|---|---:|---|---|---|
| Door high-level policy action | `12D` | `5D base command [x,y,yaw,pitch,roll] + 6D Piper arm + 1D gripper primitive` | `PASS / future gripper work needed` | `door_open_a2_base_lstm.yaml` |
| Frozen A2_Base leg action | `12D` | TorchScript `A2_Base/policy.pt` | `PASS` | `ppo_trainer_a2_base_api.py` |
| Trainer rollout/env action | `24D` | `12D high-level + 12D A2_Base` | `PASS` | `PolicyAndValueWrapper._a2_base_actions` |
| Env final robot action | `20D` | `12D legs + 6D arm_j1..j6 + 2D arm_j7/8` | `PASS` | `A2Base._step_a2_base` |

Current A2 semantics:

- Base command: `action[0:5] = [x,y,yaw,pitch,roll]`；velocity/yaw `raw[:3] * 0.25` 后按 threshold clip，pitch/roll `raw[3:5].clamp(-1,1) * 0.4`；A2_Base command obs `[39:44]` 使用 full physical command * `[2,2,0.25,1,1]`。
- Piper arm: `action[5:11]`，6D joint delta command，映射 `arm_j1..arm_j6`。
- Piper gripper: `action[11:12]`，当前 minimum viable binary primitive：
  - `>0` -> open target `[0.035, -0.035]`
  - `<=0` -> close/default `[0.0, 0.0]`
- Teacher `actions` observation 保持 `19D = 12D A2_Base leg output + 6D effective Piper arm action + 1D gripper primitive raw`。它不含 5D base command，也不含 expanded `arm_j7/arm_j8` gripper joint target。
- Teacher public `a2_base_command` observation 是 5D processed/clipped physical command scaled by `[2,2,0.25,1,1]`，替代旧 A2 `base_command` 和更早的 `b_homie_commands` public obs key；`a2_base_command_raw` 是 5D raw high-level command action，保留 origin G1 `unwarped_actions` 的语义关系。
- Future work: gripper 更推荐 continuous aperture primitive，保留 raw over-limit -> clamp -> aperture target 的 origin primitive 思路。
- `homie_*` buffer/function 名称在 A2 path 中仍有 compatibility naming，不代表仍使用 HOMIE lower-body policy。

## 4. Observation Contract

### 4.1 G1 Teacher Privileged Observation

Config: `GR00T-VisualSim2Real/gr00t/rl/config/obs/wbmanip/door_open_homie.yaml`

Actor obs terms:

- `dof_pos`
- `relative_to_door`
- `dof_vel`
- `actions`
- `projected_gravity`
- `door_dof_pos`
- `base_lin_vel`
- `base_ang_vel`
- `hand_force`
- `stage`
- `privileged_door_info`
- `delta_actions`
- `hand_handle_transform`
- `unwarped_actions`
- `b_homie_commands`

Approx actor obs dim from config: `246D`.

Critic obs adds:

- `transition`
- `complete`
- `time_in_stage`
- `actual_time_in_stage`
- `total_time`

Approx critic obs dim from config: `251D`.

Door-specific sources:

- `DoorPregrasp._get_obs_relative_to_door()`: base frame -> door root position + 6D rotation.
- `DoorPregrasp._get_obs_hand_handle_transform()`: left/right hand target frame relative to handle, `18D`.
- `DoorPregrasp._get_obs_hand_force()`: left/right hand contact forces, `2 * 8 * 3 = 48D`.
- `DoorPregrasp._get_obs_privileged_door_info()`: door width/height/handle/weight/open direction, `8D`.
- `DoorPregrasp._get_obs_door_dof_pos()`: door hinge/handle joint pos, `2D`.

### 4.2 G1 Student / Vision Observation

Config: `GR00T-VisualSim2Real/gr00t/rl/config/obs/wbmanip/door_open_homie_dagger.yaml`

Student `actor_obs`:

- `base_ang_vel`
- `projected_gravity`
- `dof_pos_non_finger`
- `dof_vel_non_finger`
- `actions`
- `delta_actions`
- `base_command`
- `complete`

Approx student actor obs dim: `122D`.

Vision obs:

- `rgb_image`, resolution `216 * 384 * 3 = 248832`.

Teacher privileged obs:

- Same main privileged structure as teacher PPO actor obs.

A2 status:

- `TODO`: student/vision obs is not A2-adapted.
- `dof_pos_non_finger` / `dof_vel_non_finger` origin functions use G1 finger slicing logic; if student path is ported, these must become A2/Piper-specific terms.

### 4.3 A2 Current Observation

Config: `DoorDog-A2_Piper/gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`

Current high-level door policy `actor_obs/critic_obs`:

- Still largely mirrors G1 teacher privileged obs skeleton.
- Current actor obs dim by config: `133D`.
- Current critic obs dim by config: `138D`.
- 本批已完成第一组 G1 origin parity：`dof_pos` / `dof_vel` 保持 full A2 robot `20D`；`actions` 保持 A2/G1 parity action surface `19D`；command obs 清理为 `a2_base_command_raw` raw 5D 与 `a2_base_command` processed/clipped/scaled 5D，order `[x,y,yaw,pitch,roll]`。
- 已确认并标记 direct reuse `PASS`：`projected_gravity`、`base_lin_vel`、`base_ang_vel`、`relative_to_door`、`door_dof_pos`。这些 term 基于 A2 `trunk`/base root state 或 door articulation；`relative_to_door` 仅覆盖 base-door navigation，不替代 Piper EE/handle observation。
- 已完成 strict replacement：`hand_force` 改为 Piper gripper body force `6D`，读取 `arm_body7`/`arm_body8` contact forces；`hand_handle_transform` rename 为 `gripper_handle_transform`，输出 `18D` TCP-to-handle/pregrasp pose。
- 已完成本批 Teacher obs status update：`privileged_door_info`: `PASS`；`stage`: `PASS`；`delta_actions`: `PASS with A2-specific semantics: 6D Piper arm raw delta only`，其中 `delta_actions` excludes 5D base command and 1D gripper primitive。
- Critic-only `transition/complete/time_in_stage/actual_time_in_stage/total_time` 已标记 `PASS: direct reuse`：这些 getter 来自 `StagedTaskBase` stage/timer bookkeeping，obs carrier/normalization 可复用且 robot-agnostic；这不代表 stage1+ transition/reward design 已完成。

Important A2 compatibility behavior:

- A2 config 不再引用 `hand_handle_transform`；A2 mode 如果旧 key 被调用会 raise，不再提供 zero compatibility。
- `hand_force` 不再 padding 到 48D，也不返回 zeros；A2 dim 是 `6D`，scale `0.01`、noise `0.0` 保持。
- `gripper_handle_transform` source frame is `/World/envs/env_.*/Robot/arm_body6_to_gripper` with source TCP offset `(0,0,0.105)`；targets are `/World/envs/env_.*/door/grasp_target` handle frame and same target with target-side `+Z 0.10m` pregrasp offset.
- Sorted obs order changes because `a2_base_command*` / `gripper_handle_transform` sort by key；actor/critic input dim remains `133D/138D`.
- `a2_base_obs: 1620D` 仍是独立 obs group，只服务 frozen A2_Base trainer inference，不混入 Teacher `actor_obs` / `critic_obs`。

A2 low-level dog policy obs:

- `a2_base_obs: 1620D` has been added and is complete for frozen A2_Base.
- Layout: `54D frame * 30 history`.
- Code: `DoorDog-A2_Piper/gr00t/rl/envs/base_task/a2_base.py`
- It contains projected gravity, 12 leg pos delta, 12 leg vel scaled, last leg action, 5D dog command, 6D zero arm command obs, base roll/pitch, gait clock.

Door policy obs post-finish enhancement candidates:

- Continue replacing/adding Piper-specific semantic terms around the completed gripper force and TCP-to-handle/pregrasp observations:
  - Piper arm/gripper proprioception.
  - Piper EE pose/velocity relative to handle.
  - handle/door hinge/door panel state.
  - EE-handle task frame and approach target.
  - optional gripper aperture/contact/grasp cues for stage1 reward/transition design.
  - actor/critic privileged split validation.
  - normalization/RMS and history/LSTM policy validation after PPO smoke.

## 5. Stage / Door Task / Sensors

Origin stage machine:

- `DoorPregrasp` stages:
  - `0 WALK_TO_DOOR`
  - `1 PREGRASP`
  - `2 GRASP`
  - `3 OPEN`
  - `4 SWING`
  - `5 THROUGH`
- Stage framework: `gr00t/rl/envs/base_task/staged_task_base.py`
- Door-specific transition functions: `DoorPregrasp._stage_0_to_1_advance_condition()` through `_stage_5_to_complete_condition()`.

G1-specific transition dependencies:

- Stage1/2 depend on `left_hand_palm_link` / `right_hand_palm_link`.
- Grasp depends on `object_to_hand_contact_forces` and G1 hand contact link counts.
- Hand/handle orientation uses G1 left/right hand target frames.

A2 current:

- `StagedTaskBase` framework is still usable.
- Stage0/global rewards and termination baseline have been A2-adjusted.
- `_compute_grasp_target()` in A2 path now reads `piper_gripper_handle_frame_transformer.data.target_pos_w[:, 0, :]`；`_compute_pre_grasp_target()` reads `[:, 1, :]`。不再 fallback 到 door root XY + handle height，也不做 world z `+0.1`。
- Stage1+ transitions and reward semantics remain `TODO` for Piper EE/gripper/contact.

Door sensors:

- Door frame / panel unwanted contact sensors are reusable and already A2-pass for global contact penalties.
- G1 hand/object contact sensors are not sufficient for Piper grasp; A2-specific gripper/body contact selection remains part of stage1+ design.

## 6. A2 Adaptation Status By Class

| 类别 | 当前状态 | A2适配状态 | 下一步 |
|---|---|---|---|
| A2_Base locomotion policy | Frozen TorchScript policy loaded from `gr00t/rl/data/policies/A2_Base/policy.pt`; flat-walk full GUI visual check passed. | `PASS` | Treat as stable locomotion layer. |
| A2_Base dog observation | `54D x 30 = 1620D` direct-path adapter complete. | `PASS` | Do not redesign unless A2_Base behavior regresses. |
| Door high-level actor skeleton | Recurrent PPO actor/critic skeleton preserved; output dim changed to 12D. | `PASS / phase complete` | Keep skeleton; train smoke and RMS validation remain follow-up. |
| Door high-level action | `5D base [x,y,yaw,pitch,roll] + 6D Piper arm + 1D gripper`; trainer rollout 24D; env compose to 20D. | `PASS with future gripper work` | Consider continuous gripper aperture after this 12D contract is stable. |
| Door task `dof_pos/dof_vel/actions` obs parity | `dof_pos/dof_vel` full A2 20D; `actions` 19D parity surface with no base command and no expanded gripper target. | `PASS` | Remaining obs work should build Piper EE/handle/contact semantics. |
| Door task actor/critic obs | G1 privileged obs skeleton retained; actor/critic dims are `133D/138D`; `hand_force` is now 6D A2 gripper body force, `gripper_handle_transform` is 18D TCP-to-handle/pregrasp, and command obs public names are `a2_base_command_raw` / `a2_base_command`. | `PASS / phase complete` | Active obs terms have A2 mapping/direct reuse/strict replacement/A2-specific semantics. Gripper aperture/contact/grasp cues, actor/critic privileged split, normalization/RMS, PPO train smoke, and stage1+ reward/transition correctness are follow-up work rather than current obs adaptation blockers. |
| Student DAgger/vision policy | Still G1/HOMIE route and G1 teacher checkpoint. | `TODO` | Design after A2 teacher PPO policy exists. |
| Stage machine | Generic staged framework reusable; critic-only stage/time obs terms are `PASS: direct reuse` via `StagedTaskBase`. | `PARTIAL` | Rewrite stage1+ transition for Piper EE/gripper; stage/time obs PASS does not complete transition/reward design. |
| Stage0/global reward | User confirmed current baseline. | `PASS` | Reward build paused; revisit after policy obs/action design. |
| Stage1+ reward | Still G1 hand/contact-heavy. | `TODO` | Redesign around Piper EE, gripper aperture/contact, door progress/success. |
| Normalization / RMS | Recurrent actor uses `running_mean_std`; current obs dims changed. | `PARTIAL` | Recompute/check obs dims and scale after task obs redesign. |

## 7. Direct Design Implications

1. A2 teacher PPO should keep the recurrent actor/critic skeleton unless there is a specific reason to replace it.
2. Teacher PPO door task actor/critic obs carrier/input contract is phase complete at `133D/138D`; the next highest-leverage work is stage1 reward + transition correctness, followed by PPO train smoke/RMS validation.
3. `hand_force` and `hand_handle_transform -> gripper_handle_transform` strict replacements are complete for Teacher PPO: 6D Piper gripper body force and 18D TCP-to-handle/pregrasp pose. Future obs enhancements may add aperture/contact/grasp cues rather than restoring zero compatibility.
4. Student/vision should wait until A2 teacher policy and A2 task obs/action are stable; origin G1 teacher checkpoint is incompatible.
5. Any future action contract change, such as continuous gripper aperture, must update:
   - actor output dim,
   - trainer high-level action split,
   - env action composition,
   - A2_Base command/obs injection,
   - obs dims and `delta_action_indices`,
   - old compatibility names if they become confusing.
