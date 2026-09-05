# Source map：每个概念在项目里落到哪里

本文件把三条分支的知识点钉到真实 source/config。当前 worktree 文件可以直接打开；另外两个分支请使用 `git show <branch>:<path>` 只读查看，不要为了复习切换共享 dirty worktree。

## 1. 当前 `A2_Piper`：Teacher PPO 与 Isaac control

### 入口与 Hydra compose

| 主题 | 路径 / 符号 | 要看什么 | 证据 |
|---|---|---|---|
| 训练入口 | `gr00t/rl/train_agent_trl.py::main` | Hydra compose、env/model/trainer 实例化 | INSPECTED |
| 当前 experiment overlay | `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml` | 4096 env、64-step rollout、γ/λ、网络、A2_Base | INSPECTED |
| PPO base defaults | `gr00t/rl/config/algo/ppo.yaml` | 不要把 base defaults 当 resolved experiment；overlay 会覆盖 | INSPECTED |
| TRL config bridge | `gr00t/rl/config/algo/trl/ppo.yaml` | PPO epochs/minibatches/gamma/lam 如何传入 trainer args | INSPECTED |
| trainer target | `gr00t/rl/config/trainer/trl_a2_base_api.yaml` | `TRLPPOTrainer` 选择 | INSPECTED |

### Environment class hierarchy

```text
DoorPregrasp
  -> StagedTaskBase
  -> A2Base
  -> LeggedRobotBase
  -> BaseTask (gym.Env)
```

| 路径 / 符号 | 责任 |
|---|---|
| `gr00t/rl/envs/door/door_open_a2_base.py::DoorPregrasp` | door scene/sensors/obs/reward/stage predicate/reset |
| `gr00t/rl/envs/base_task/staged_task_base.py` | stage buffer、advance、stage timeout、final completion |
| `gr00t/rl/envs/base_task/a2_base.py::A2Base` | frozen locomotion contract、24D→20D mapping、A2_Base history |
| `gr00t/rl/envs/legged_base_task/legged_robot_base.py` | pre/physics/post step、reward registry、obs assembly、reset |
| `gr00t/rl/envs/base_task/base_task.py` | Gym env 基础、simulator construction、dt/buffers |
| `gr00t/rl/simulator/isaacsim/isaacsim.py::IsaacSim` | IsaacLab scene/assets/sensors、write targets、physics stepping |

这里的关键面试边界：它使用 IsaacLab API，但不是原生 `ManagerBasedRLEnv`。

### Observation contract

主配置：`gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`

| tensor | 当前 shape | 关键组成 |
|---|---:|---|
| `actor_obs` | `[N,133]` | robot/door/task privileged state + commands |
| `critic_obs` | `[N,138]` | actor-like state + transition/complete/timing 5D |
| `a2_base_obs` | `[N,1620]` | `30 × 54` locomotion history |

getter 主要在：

- `door_open_a2_base.py::_get_obs_gripper_handle_transform`
- `door_open_a2_base.py::_get_obs_hand_force`
- `door_open_a2_base.py::_get_obs_privileged_door_info`
- `door_open_a2_base.py::_get_obs_door_dof_pos`
- `a2_base.py::_get_a2_base_obs_frame`
- `a2_base.py::_get_obs_a2_base_obs`

### Network

| 路径 / 符号 | 作用 |
|---|---|
| `gr00t/rl/trl/modules/actor_critic_modules.py::Actor` | Normal(mean,std)、logprob、entropy、RunningMeanStd |
| `gr00t/rl/trl/modules/actor_critic_modules.py::Critic` | value evaluation |
| `gr00t/rl/trl/modules/actor_critic_modules_recurrent.py::RecurrentActor` | LSTM rollout/train path、trajectory mask、12D mean |
| `gr00t/rl/trl/modules/actor_critic_modules_recurrent.py::RecurrentCritic` | recurrent value |
| `gr00t/rl/trl/modules/memory.py::Memory` | LSTM/GRU state、done reset、detach |

当前 experiment 定义：2-layer LSTM、hidden 256、MLP `[512,256,128]`、SiLU。actor 和 critic 各自独立。

### Action chain

| 路径 / 符号 | 合同 |
|---|---|
| experiment YAML `base_command_dim` / `manipulation_action_dim` | high-level `5 + 7 = 12D` |
| `ppo_trainer_a2_base_api.py::PolicyAndValueWrapper` | learned high12 + frozen leg12 composition |
| `a2_base.py::get_a2_high_level_action_layout` | base/arm/gripper slice |
| `a2_base.py::_step_a2_base` | env 24D 解析、name mapping、gripper expansion、base command processing |
| `gr00t/rl/envs/base_task/delta_action_base.py` | arm delta accumulation/scale/clip |
| `gr00t/rl/envs/base_task/finger_primitive_base.py` | semantic gripper primitive |
| `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` | 20 DOF names/order、limits、gains、action scale |
| `gr00t/rl/data/policies/A2_Base/policy_metadata.json` | 1620D/12D frozen locomotion deployment contract |

### Timebase

`gr00t/rl/config/simulator/isaacsim.yaml`：

```text
physics fps = 200        -> 0.005 s
control_decimation = 4  -> 0.020 s control dt = 50 Hz
rollout = 64 control steps = 1.28 simulated seconds
```

对应 step path：

- `LeggedRobotBase::_pre_physics_step`
- `LeggedRobotBase::_physics_step`
- `LeggedRobotBase::_post_physics_step`

### PPO / GAE

`gr00t/rl/trl/trainer/ppo_trainer.py`：

| 符号 | 讲解重点 |
|---|---|
| `_setup_storage` | time-major buffers、old mean/std/logprob、hidden states |
| `policy_step` | actor rollout、log probability、hidden state capture |
| `_rollout_step` | 64-step no-grad collection、env step、value、timeout bootstrap |
| `_compute_returns` | backward GAE 与 advantage normalization |
| `_get_rollout_data` | `[T,N]` → `[N,T]`、split/pad recurrent trajectories |
| `_get_mb_rollout_data` | trajectory initial hidden states 与 masks |
| `_compute_ppo_loss` | ratio、policy clip、value clip、entropy、KL |
| `train` | 5 epochs × 4 minibatches、backward、grad clip、optimizer |

### Stage / reward / termination

| 路径 | 内容 |
|---|---|
| `gr00t/rl/config/env/door_open_a2_base.yaml` | stage times、staged reset、door/grasp thresholds、termination config |
| `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` | 当前非零 reward scale source |
| `door_open_a2_base.py::_stage_0_to_1_advance_condition` | staging band、arm default、base still |
| `door_open_a2_base.py::_stage_1_to_2_advance_condition` | pregrasp ready |
| `door_open_a2_base.py::_stage_2_to_3_advance_condition` | grasp completion/contact streak |
| `door_open_a2_base.py::_stage_3_to_4_advance_condition` | hinge + hold |
| `door_open_a2_base.py::_stage_4_to_5_advance_condition` | crossed + door wide + handle up |
| `door_open_a2_base.py::_stage_5_to_complete_condition` | final root crossing |
| `memory/a2-piper/quicktest-merge/description.md` | false terminal / contact-spike 历史教训 |

reward source 中定义了大量实验版本函数；不要因为函数存在就说它当前激活。是否激活要看 resolved reward scale。

## 2. 蒸馏分支：视觉 Student / DAgger

分支：`codex/a2-v13-student-distillation-20260717_2103`

推荐只读命令：

```bash
git show codex/a2-v13-student-distillation-20260717_2103:gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py
git show codex/a2-v13-student-distillation-20260717_2103:gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml
```

### 早期 Phase2 主链

| path / symbol | 责任 | 证据 |
|---|---|---|
| `gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py::TRLDistillTrainerA2BaseAPI.policy_step` | Teacher label、Student action、mixed rollout、A2_Base compose | INSPECTED |
| `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml` | Student/Teacher/camera/A2_Base compose | INSPECTED |
| `gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml` | Student 81D proprio 与 Teacher 133D obs | INSPECTED |
| `gr00t/rl/trl/modules/vision_actor_critic_modules_recurrent.py` | vision encoder + LSTM Student | INSPECTED |
| `memory/a2-piper/phase2-student-distillation-a2-piper/description.md` | one-update training evidence 与边界 | RUNTIME for one update only |

核心 shape：

```text
Teacher 133D -> 12D label
Student 81D + RGB -> 12D prediction
A2_Base 1620D -> 12D legs
[chosen high12 | leg12] -> env 24D -> simulator 20D
```

### 多相机 / C-B2H / DepthADD 演进

分支上的关键模块包括：

- `vision_actor_critic_modules_triview_recurrent.py`
- `vision_actor_critic_modules_p2_recurrent.py`
- 双 D435 + Head camera configs
- DepthADD RGB-D input route
- Student eval runners

重要合同：

- Student proprio `81D`；
- 左右视觉通道顺序固定，左右共享 encoder；
- Head context camera 独立 encoder；
- `camera_meta` 包含每路 age + validity；
- Student 和 Teacher 仍对齐 `12D high-level`；
- A2_Base 仍冻结；
- object prediction 对 A2 route 显式关闭。

分支上有真实训练/eval evidence，但每个数字只属于各自 checkpoint、randomization plant 和 eval protocol。尤其不要把不同视觉/plant 版本做无控制的横向因果比较。

### DAgger 关键符号

追踪这些概念，而不是只搜文件名：

- `gt_actions`
- teacher/student rollout mask
- `ratio_teacher_rollout`
- mixed rollout schedule
- masked L2 BC loss
- `distill_only`
- teacher-only eval counters

### Phase3 边界

当前主线 memory：`memory/a2-piper/phase3-student-bootstrapping/description.md`

结论：原有 A2/G1 framework 没有完整 GRPO Phase3 trainer/config/workflow。蒸馏分支的受限 actor-only experiment 可作为探索证据，不能说成完整 Phase3 已实现。

## 3. sim2sim 分支：MuJoCo shadow evaluator

分支：`sim2sim/a2-mujoco-shadow-evaluator-20260817`

推荐只读命令：

```bash
git show sim2sim/a2-mujoco-shadow-evaluator-20260817:gr00t/rl/sim2sim/contracts/policy_bundle.py
git show sim2sim/a2-mujoco-shadow-evaluator-20260817:gr00t/rl/sim2sim/cli/run_paired_mujoco_campaign.py
git show sim2sim/a2-mujoco-shadow-evaluator-20260817:gr00t/rl/sim2sim/FINAL_REPORT.md
```

### Policy bundle / strict load

| path / symbol | 作用 |
|---|---|
| `sim2sim/contracts/policy_bundle.py` | resolved config + actor + contract manifest/export/validation |
| `sim2sim/cli/produce_native_hydra_actor.py` | native Hydra actor reconstruction |
| `sim2sim/cli/replay_native_hydra_golden.py` | action/LSTM golden replay |

### Observation / action / control

| path / symbol | 作用 |
|---|---|
| `sim2sim/policy/observations.py` | 81D actor obs、RGB normalization、dual RGB composition |
| `sim2sim/mujoco/action_warp_r5.py::FullActionWarpR5` | base warp、arm delta、gripper/stage semantics |
| `sim2sim/mujoco/stage_contract_minimal.py` | post-observation stage update contract |
| `sim2sim/mujoco/a2_base_obs.py` | 54D frame、30-frame history |
| `sim2sim/mujoco/names.py::A2PiperJointMap` | policy order ↔ simulator order name mapping |
| `sim2sim/mujoco/native_position_r4.py` | MuJoCo native position control route |
| `sim2sim/mujoco/external_pd.py` | earlier explicit external-PD route |

### Scene / door / evaluator

| path / symbol | 作用 |
|---|---|
| `sim2sim/mujoco/paired_scene_builder_v2.py` | robot + door paired scene |
| `sim2sim/mujoco/policy_visual_scene_r4.py` | live policy visual scene |
| `sim2sim/doors/spec.py` | door mechanics unit contract |
| `sim2sim/doors/runtime.py` | constraint gate / latch semantics |
| `sim2sim/doors/metrics.py` | door metrics |
| `sim2sim/cli/compare_paired_campaign.py` | paired trace schema validation 与 raw/RMSE/event comparison |
| `sim2sim/schemas/paired_trace_row.schema.json` | physics-row trace schema |

### 必须讲清的 order mapping

MuJoCo simulator leg order 与 low-level A2 policy order不同。分支通过 joint name 构建 explicit index mapping；不要按原数组位置假设同序。

### 必须讲清的 timebase

```text
physics 200 Hz
Student + A2_Base 50 Hz
left/right cameras 30 Hz
head camera 15 Hz
camera age normalized by 0.1 s
```

50 Hz policy action 持有 4 个 physics rows。camera 未到更新周期时复用缓存帧，age/valid 写入 Student input。

### 当前证据结论

- strict actor reconstruction / golden replay、robot compile、若干 control/door/vision replay 有各自的 RUNTIME 证据；
- r7 用 replayed Isaac visuals 与 live MuJoCo visuals 隔离出视觉域差对当前 checkpoint 的关键影响；这是指定干预下的 EXPERIMENT 结论；
- formal same-case Isaac↔MuJoCo paired E5 曾因缺当前 Student/scene Isaac trace 标为 `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`；
- 所以不能宣称完整 sim2sim parity；
- 没有 hardware evidence。

## 4. Memory 入口

| 主题 | memory path |
|---|---|
| A2 总入口 | `memory/a2-piper/MEMORY.md` |
| 长期 door training 目标与 action/obs 历史 | `memory/a2-piper/doorman-door-training-goal/description.md` |
| reward migration | `memory/a2-piper/reward-implementation-goal/description.md` |
| quickTEST merge 与 false-terminal 修复 | `memory/a2-piper/quicktest-merge/description.md` |
| Phase2 Student Distillation | `memory/a2-piper/phase2-student-distillation-a2-piper/description.md` |
| Phase3 / GRPO 边界 | `memory/a2-piper/phase3-student-bootstrapping/description.md` |
| 当前实验版本索引 | `memory/a2-piper/MEMORY.md` 中 base-v21B…v26 routes |

Memory 是路由和历史事实，不覆盖当前 source、resolved config 和 runtime artifacts。

## 5. 面试时如何引用 evidence

推荐句式：

- “从当前 experiment/config 和 trainer source，我确认 shape 是……；这是 source-inspected contract。”
- “该分支对 one-update / strict replay / 指定 eval 有运行或实验记录，但它只证明登记问题。”
- “formal paired trace 因输入缺失被标为 blocked，所以我不会把局部模块通过说成完整 parity。”
- “目前没有硬件证据，仿真 effort 与成功率不构成实机安全结论。”

不推荐：

- “代码看起来能跑，所以应该没问题。”
- “某个文件叫 final，所以系统已经完成。”
- “Teacher/Student/MuJoCo 有一个高成功率数字，因此 sim2real 已通过。”
