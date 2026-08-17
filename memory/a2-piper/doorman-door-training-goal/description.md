---
name: doorman-door-training-goal
scope: A2_Piper long-term goal for Doorman-based robot replacement and door-opening training
status: active
last_updated: 2026-07-13 16:37 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/doorman-door-training-goal/description.md
  - memory/a2-piper/doorman-door-training-goal/TODO.md
  - memory/a2-piper/doorman-door-training-goal/DONE.md
read_when:
  - 开始 A2_Piper robot replacement、observation/action/reward design、env config、training/eval workflow 或相关文档更新前
  - 需要确认长期目标、当前拆解 TODO 或 Doorman baseline 与用户自有 robot 的适配边界时
---

# Doorman Door Training Goal

## Purpose

记录 A2_Piper 的长期目标：基于 Doorman 的 door-opening task/workflow，替换为用户自己的 robot，并围绕该 robot 设计/适配 observation、action、reward、env config 与 training/eval workflow，最终完成开门任务训练。

## Goal Definition

目标态：

- Robot: 用用户自己的 robot asset/config 替换 Doorman baseline robot，并保持 simulation/runtime 可加载、可 reset、可执行控制。
- Observation: 设计并实现适配新 robot 与 door task 的 observation spec，明确 proprioception、end-effector/handle/door state、camera 或其他 sensor 的数据来源、shape、坐标系与 normalization。
- Action: 设计并实现新 robot 的 action/control interface，明确 action dimension、joint/EE control mapping、limits、scaling 与 policy 输出到 simulator command 的转换。
- Reward: 设计并实现门把手接近、抓握/接触、转动/拉动、door angle/progress、success、safety penalty 等 reward routing，并与训练目标一致。
- Training/Eval: 完成 env config、runner/training config、smoke/eval workflow 与 checkpoint 产物路径，能够稳定跑通开门任务训练与基本验证。

## Scope Boundaries

- A2_Piper 实现与施工状态记录在 `/home/baoquanc/workspace/DoorDog-A2_Piper`。
- `/home/baoquanc/workspace/GR00T-VisualSim2Real` 作为 Doorman baseline/reference worktree，默认只读参考；不要在其中实施 A2_Piper 改动。
- `origin-reference` memory 只记录 baseline/source-of-truth 事实；本 entry 记录长期目标、任务拆解与 A2_Piper 施工状态。
- 详细实验日志、checkpoint 指标或训练曲线如后续增长较多，应拆成新的 experiment progress entry，并从本 entry route 过去。

## A2_Piper Asset Paths

- Robot asset directory: `gr00t/rl/data/robots/A2_Piper/`
- Main URDF: `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf`
- IsaacSim USD: `gr00t/rl/data/robots/A2_Piper/a2_piper.usd`
- Mesh directories: `gr00t/rl/data/robots/A2_Piper/meshes/` and `gr00t/rl/data/robots/A2_Piper/meshes/piper/`
- Robot config: `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml`
- Locomotion base policy directory: `gr00t/rl/data/policies/A2_Base/`
- Locomotion base policy files: `gr00t/rl/data/policies/A2_Base/policy.pt` and `gr00t/rl/data/policies/A2_Base/policy_metadata.json`
- Preview entrypoint: `gr00t/rl/scripts/preview_a2_piper_door_scene.py`
- 2026-06-12 18:02 HKT 当前 preview milestone 已生成 IsaacSim USD，并新增 preview-only scene path；training observation/action/reward 尚未开始。

## Current State

- 2026-07-13 16:37 HKT - Full-stage push/open-door RL optimization 从 `base_v9` 起由独立 [`push-open-door-optimization`](../push-open-door-optimization/description.md) entry 管理。当前 baseline 是 TCP source local-Z `0.085`、gripper Kp/Kd `80/3`、effort `10/10`；2026-07-07 的 base_v6 `40/40` 仍作为当时 mixed TCP/effort trial 的历史事实，不再表示 current default。`base_v9` diagnostics 已停止，下一步是另行审批 `base_v10` RL plan。
- 2026-06-12 16:59 HKT - 已建立长期目标 memory；尚未在本 entry 中记录 robot/observation/action/reward 的具体实现状态或验证结果。
- 2026-06-12 17:07 HKT - 用户已加入 A2_Piper robot URDF assets，路径为 `gr00t/rl/data/robots/A2_Piper/`，主 URDF 为 `a2_piper.urdf`，mesh 包含本体 leg/trunk STL 与 `meshes/piper/` arm/gripper STL。
- 2026-06-12 18:02 HKT - 已完成 Door Scene Preview Robot Replacement milestone：新增 A2_Piper robot config、生成 `A2_Piper/a2_piper.usd`，新增 preview-only scene module 复用 Doorman door scenario source 且不走 DoorPregrasp/G1/HOMIE/finger primitive/sensor hardcode，入口支持 WebRTC 与 stage-0 root pose CLI 调参。
- 2026-06-12 18:30 HKT - Reviewer follow-up 已修复 preview scene `replicate_physics=False`，并将 teardown 收敛为释放 scene 引用后调用 `SimulationContext.clear_all_callbacks()` + `clear_instance()`；bounded IsaacLab smoke 到达 create/reset/zero-action hold 并 clean exit。
- 2026-06-12 18:52 HKT - Preview entrypoint 已对 IsaacLab `AppLauncher` toolbar hiding 做 preview-local guard：当前 livestream/headless Kit 缺少 `omni.kit.widget.toolbar` 时仅 warning 并跳过 `_hide_stop_button`/`_hide_play_button`，不阻塞 scene creation。
- 2026-06-12 18:56 HKT - Preview rendering Kit 选择改为优先使用 `/home/baoquanc/workspace/IsaacLab/apps/isaaclab.python.headless.rendering.kit`，缺失时 read-only fallback 到 repo-local kit，不再向 IsaacLab checkout 写入 kit file。
- 2026-06-12 19:08 HKT - Preview livestream/camera path 记录 UsdRT logical GPU caveat：不要传 `--device cuda:N` (`N != 0`)；如需使用 physical GPU `N`，用 `CUDA_VISIBLE_DEVICES=N` 暴露为 logical `cuda:0`，并传 `--device cuda:0`。
- 2026-06-12 19:35 HKT - Placement bounds preview 已对齐当前 Doorman stage-0 reset hardcode：`--placement-preview corners` 默认 `--placement-bounds doorman-stage0`，展示 x `[-1.5,-0.6]`、y `[-0.5,0.5]`、yaw `[-pi/4,pi/4]`，z 仍来自 `--root-z`；root-centered half range 保留为显式 preview-only mode，不 runtime import `door_open_a2_base.py`。
- 2026-06-12 19:52 HKT - 用户确认当前 Doorman stage-0 reset 下 robot 与 door 的相对位置/朝向范围可以接受；后续 reward、observation 和 pregrasp/approach 设计可先以该 reset range 为合理初始分布，不需要立即收窄或重设 root placement。
- 2026-06-12 20:08 HKT - 用户确认已有成熟 A2 locomotion base policy；短期路线从“先设计全新 locomotion”改为“先导入 locomotion policy 并以其 input/output contract 为中心适配 A2_Piper observation/action”。后续 door policy 应把 locomotion base 当作稳定支撑层，重点定义 base command、Piper arm/gripper action 与 door/handle task observation 的接口。
- 2026-06-12 20:23 HKT - A2_Piper action migration 决策：Piper gripper 对应使用 1 维 gripper primitive，只表达 open/close，不按 Doorman G1 的 2 维 left/right finger primitive 或逐 finger joint action 直接迁移。
- 2026-06-12 20:55 HKT - 已将用户提供的 mature A2 locomotion export 从 `/home/baoquanc/workspace/LMP/logs/manager_dual_rl/lmp_dual_policy/stage1_locomotion_a2_piper/2026-06-05_16-12-09/checkpoints_dog/exported/` 复制到本项目 `gr00t/rl/data/policies/A2_Base/`。当前仅完成 asset import/rename；尚未接入 Doorman env runtime loader。
- 2026-06-12 20:56 HKT - A2_Base `policy.pt` 已在 conda env `isaaclab` 中通过 `torch.jit.load` CPU smoke：输入 shape `[2, 1620]`，输出 shape `[2, 12]`，与 `policy_metadata.json` 的 obs/action contract 一致。
- 2026-06-12 22:41 HKT - A2_Piper + A2_Base action chain replacement 第一阶段已接入当前 `trl_a2_base_api` / `DoorPregrasp` path：high-level actor contract 为 `10D = 3D base command + 6D Piper arm + 1D gripper primitive`，trainer rollout action 为 `22D = 10D high-level + 12D A2_Base leg action`，env 最终 simulator joint command 为 `20D = 12D legs + 6D arm_j1-6 + 2D gripper joints`。本阶段只做 action chain 与 frozen A2_Base 必需 low-level obs adapter，未启动 PPO/train，也未做 Isaac Sim/env smoke。
- 2026-06-12 23:05 HKT - 当前 A2 action-chain primary entrypoint 已完成命名清理：Hydra experiment/config/source module 使用 `door_open_a2_base_lstm`、`door_open_a2_base`、`reward_door_open_a2_base`、`trl_a2_base_api`、`ppo_trainer_a2_base_api`、`a2_base`；primary env import/继承改用 `A2Base`，旧 `HomieBase` 仅作为新 module 内兼容 alias 保留。
- 2026-06-12 23:34 HKT - 用户提供下一阶段 observation replacement overview：Dog policy observation 目标对齐 RoboDuet `auto_train` path 的 `54D x 30 = 1620D` history；后续会逐项描述详细逻辑并分步实现，当前先作为 memory Goal/TODO 记录。
- 2026-06-13 21:15 HKT - 用户补充 A2_Base 训练来源：A2_Base 是在 LMP manager-based workflow 下训练完成的，核心配置入口为 `/home/baoquanc/workspace/LMP/source/LMP/LMP/tasks/manager_based/lmp_manager/lmp_manager_env_cfg.py`。后续每个 A2_Base observation 字段迁移前，应先追溯该 manager-based 训练源码中的 observation/action 计算与更新逻辑，再制定 DoorDog direct/env-hook 侧实现方案。
- 2026-06-12 22:50 HKT - Reviewer follow-up 已修复当时 action contract 细节（old 10D snapshot，已由 2026-06-16 12D contract supersede）：Piper gripper primitive 从 `delta_action_indices` 移除，当时仅 arm dims `[3..8]` 累积 delta，gripper old index 9 保持 instantaneous open/close primitive；A2_Base `policy_metadata.json` 已接入 trainer/env setup，用于校验/派生 `1620D` obs、`30 x 54` history、`12D` action、metadata leg order、`leg_action_scale=0.25` 与 `use_default_offset=true`。
- 2026-06-13 21:33 HKT - 完成 A2_Base observation slice `0:27` parity：DoorDog direct path 的 projected gravity、leg joint position relative default、leg joint velocity scaled `0.05` 已拆为独立 helper 并按 LMP `LEG_JOINT_NAMES` / metadata order 取数；`a2_base_obs` history reset 改为 reset 后首帧用 current frame 填满 30 slots，已初始化 env 继续 shift/append。
- 2026-06-13 22:00 HKT - 完成 A2_Base observation slice `27:50` parity：DoorDog direct path 现在拆出 raw dog action、scaled 5D `commands_dog` 与 6D zero `arm_command_obs` helpers；`commands_dog[39:44]` 现在由 12D high-level action 的 5D base command `[x,y,yaw,pitch,roll]` 注入，velocity/yaw 使用 `raw[:3] * 0.25 * [2.0, 2.0, 0.25]`，pitch/roll 使用 `raw[3:5].clamp(-1,1) * 0.4`，trainer 不再清零 final frame pitch/roll slice。
- 2026-06-13 22:13 HKT - 完成 A2_Base observation slice `50:52` parity：新增 `_get_a2_base_roll_pitch()` 显式返回 `self.rpy[:, 0:2]`，语义为 `[base_roll, base_pitch]` rad，无 scale，并由 `_get_a2_base_obs_frame()` 写入 frame `[50:52]`。
- 2026-06-14 17:22 HKT - 完成 A2_Base observation slice `52:54` parity：DoorDog direct path 新增 LMP-style gait phase buffer、`common_step_counter` at-most-once update guard、reset initial phase/last step pinning 与 standing command phase reset；`_get_a2_base_obs_frame()` 现在用 `_get_a2_gait_clock_signal()` 写入 `clock_inputs`。
- 2026-06-14 17:48 HKT - 新增 standalone full Isaac Sim GUI A2_Base flat-ground locomotion smoke/monitor：`gr00t/rl/scripts/smoke_a2_base_flat_walk.py` 只加载 A2_Piper USD、A2_Base TorchScript policy 与 metadata，在 flat ground 上按 `54D x 30` history contract 直接驱动 12D leg action，不启动 PPO/DAgger/DoorPregrasp/door high-level checkpoint。命令约定为 `--base-command-raw` raw high-level base command、`--base-command-physical` physical `[vx, vy, yaw]`，兼容 `--command` 作为 physical alias；默认 raw `[1,0,0]` 对应 physical `vx=0.25 m/s`。
- 2026-06-14 18:27 HKT - 完成 A2_Piper USD Plant 对齐 LMP Stage1：保持 USD entrypoint，不切 URDF；`a2_piper_physics.usd`、preview/flat-walk `build_a2_piper_robot_cfg()`、A2 door training `isaacsim.py` runtime override、A2 robot YAML 与 exp PhysX override 均对齐 LMP Stage1-equivalent physics/control plant，避免旧 preview plant 覆盖 flat-walk smoke 或后续 door env。
- 2026-06-14 18:37 HKT - 用户在 full Isaac Sim GUI monitor 中确认 A2_Base flat-walk 已能正常 walk；A2_Base observation/action build line 与 USD plant 对齐被标记为成功，可作为 Doorman 原 G1/HOMIE locomotion policy 的替代基础。下一阶段转入 door-opening training policy 的 task observation/action 设计，以及将原 G1 reward 适配为 A2+Piper reward。
- 2026-06-14 20:54 HKT - 已完成 G1 Doorman stage0 baseline reward/transition summary，输出到 `scriptsFORhuman/g1_doorman_stage0_reward_transition.md`；该文档总结 stage0 `STAGE_WALK_TO_DOOR` 的 active rewards、global penalties、stage0 -> stage1 advance condition 与 A2+Piper 迁移启发，供后续 stage0 reward adaptation 使用。
- 2026-06-14 21:48 HKT - 新增 dedicated reward memory entry：`memory/a2-piper/reward-implementation-goal/description.md`。接下来 reward 小目标收窄为实现 global rewards 和 stage0-enabled rewards；reward 迁移必须遵守 IsaacLab direct workflow，必要时分别让 Bella/Galileo 核查 LMP manager-based source logic，让 Ava 核查 Doorman origin-code logic。
- 2026-06-15 22:44 HKT - 用户确认 stage0 reward 与大部分 global reward 已完成可复用审核和 A2_Piper adjustment：stage0 active terms、A2 arm/gripper replacement、base command limit、undesired contact、LMP-style `orientation_control`、height/orientation/arm overspeed termination 等已形成第一版 baseline；后续 reward 工作主要转向 stage1+ Piper EE/handle、gripper/contact、door progress、success 与 smoke 后调参。
- 2026-06-25 20:30 HKT - 从 `quickTEST` branch 合并回 A2_Piper 主线的 A 类通用 bugfix（详见 `quicktest-merge` entry）：
  - `OrderedTargetFrameTransformer`：修复 IsaacLab `FrameTransformer` 用 `set` 导致 target frame order 不可靠 + multi-env duplicate 误判。
  - A2_Base `_homie_history_length` 显式初始化 + fail-fast：修复 A2 early-return 绕过 cooperative MRO 导致的 init crash。
  - `ResetFromDataset` 拆分 `_init_reset_from_dataset()`：修复 A2 early-return 绕过 `ResetFromDataset.__init__()` 导致 `reset_count` missing。
  - PPO recurrent `_a2_base_actions()` 增加 `unsplit_trajectories`：修复 recurrent model padded obs / env-major action shape mismatch。
  - `PolicyAndValueWrapper` 用 `object.__setattr__` 持有 frozen A2_Base TorchScript：修复 HuggingFace Trainer optimizer `ParameterDict.contains()` crash。
  - `staged_task_base.py` `is_complete = is_last_stage & is_stage_complete`：**关键 bugfix**，原代码任何 stage complete 都会触发 episode terminal，6-stage 下 stage2 complete 就会提前结束 episode。
  - eval rendering/diagnostics 重写：terminal reason tracking、per-env mp4 writer lifecycle、`eval_rendering` config、`eval_camera_resolutions` 配置化、`_make_json_safe` + 原子写入。
  - `train_agent_trl.py` toolbar hiding patch：修复 headless Kit 缺 `omni.kit.widget.toolbar` 时 AppLauncher crash。
- 2026-06-15 23:06 HKT - Reward build 暂缓，转向 door policy / arm policy 配套设计。已让 Ava 核查 G1/Doorman origin policy stack，并整理 `scriptsFORhuman/g1_doorman_policy_stack_a2_adaptation_map.md`：按 entrypoint/network/action/observation/stage/sensor/student vision 分类列出 G1 source-of-truth、当前 A2 adaptation 状态与下一步 design implications。关键结论：A2_Base locomotion 与 A2 high-level action chain 已可作为 baseline；door policy task obs 仍主要是 G1 schema + A2 zero-shape compatibility，需重新设计 Piper EE/handle/gripper/door state observation；student/vision route 仍是 G1/HOMIE contract，暂不可用。
- 2026-06-16 13:58 HKT - 用户明确短期 training/policy route：先做 A2 Teacher PPO experiment；Student DAgger vision experiment、student trainer 和蒸馏训练后续再确定，不作为当前短期目标。Teacher PPO Actor/Critic 的 network skeleton 可直接复制 G1 origin：`RecurrentActor` / `RecurrentCritic`，`running_mean_std=True`，`rnn_type=lstm`，`rnn_hidden_dim=256`，`rnn_num_layers=2`，MLP hidden dims `[512, 256, 128]`。短期只修改 actor/critic input observation contract 与 actor output action contract，不重新设计 network architecture。
- 2026-06-16 14:08 HKT - Ava 已单独核查 G1 Teacher privileged observation contract，并整理 `scriptsFORhuman/g1_doorman_teacher_privileged_obs_a2_adaptation_map.md`：逐项列出 G1 actor/critic obs term、shape、origin getter、A2 当前状态与 adaptation risk。关键结论：当前 A2 high-level `actor_obs/critic_obs` 仍是 G1-style schema；`hand_handle_transform` 与 `hand_force` 是 zero-shape compatibility，必须优先替换为 Piper EE/handle/gripper/contact semantics。
- 2026-06-16 14:49 HKT - 完成本批 A2 Teacher high-level obs parity：`dof_pos` / `dof_vel` 保持 full A2 robot `20D` getter；`actions` 从 final simulator `20D` 改为 A2/G1 parity action surface `19D = 12D A2_Base leg output + 6D effective Piper arm action + 1D gripper primitive raw`。Actor obs dim `176 -> 175`，critic obs dim `181 -> 180`；`actions` 不含 base command、不含 expanded gripper joint target，`a2_base_obs` 仍不混入 Teacher actor/critic obs。
- 2026-06-16 15:34 HKT - 完成第二批 Teacher high-level observation direct reuse 审核/标记：`projected_gravity`、`base_lin_vel`、`base_ang_vel`、`relative_to_door`、`door_dof_pos` 均无需 code adaptation，直接基于 A2 `trunk`/base root state 或 door articulation 复用；`relative_to_door` 仅作为 base-door navigation term，不替代 Piper EE/handle task-frame observation。
- 2026-06-16 19:38 HKT - 完成 A2 Teacher obs strict replacement：`hand_force` 改为 `arm_body7`/`arm_body8` gripper net/body force 6D；`hand_handle_transform` rename/替换为 `gripper_handle_transform` 18D，读取 `piper_gripper_handle_frame_transformer`，source 为 `arm_body6_to_gripper` + TCP offset（当时为 `(0,0,0.105)`；2026-07-07 base_v6 当前值已改为 `(0,0,0.085)`），target 为 `grasp_target` handle 与 target-side `grasp_target +Z 0.10m` pregrasp frame。A2 path 不再有 zeros fallback 或 door-root approximation，旧 key、missing bodies、missing/wrong transformer target order 均 fail-fast。
- 2026-06-16 20:54 HKT - 完成 A2 Teacher PPO high-level action contract 10D/22D -> 12D/24D 迁移：旧 `10D = 3D base + 6D Piper arm + 1D gripper` 与 `22D = 10D + 12D A2_Base` 记录已 superseded；新 high-level policy action `12D = 5D base_command_raw [x,y,yaw,pitch,roll] + 6D Piper arm_j1..j6 + 1D gripper primitive`，trainer rollout action `24D = 12D high-level + 12D A2_Base leg action`，final simulator joint command 仍为 `20D`。
- 2026-06-16 21:41 HKT - Ava 复核补充 residual TODO：standalone `smoke_a2_base_flat_walk.py` 仍是 velocity-only 3D command monitor，不应作为 5D `[x,y,yaw,pitch,roll]` Teacher PPO action contract 的 pitch/roll 验收工具；后续需升级为 5D smoke 或在 CLI/README 明确标注 velocity-only。
- 2026-06-16 21:46 HKT - 完成 Teacher PPO obs status 文档更新：`privileged_door_info` 与 `stage` 标记 `PASS`，`delta_actions` 标记 `PASS with A2-specific semantics: 6D Piper arm raw delta only`；明确 `delta_actions` 只覆盖 Piper arm raw delta，不含 5D base command 与 1D gripper primitive。
- 2026-06-16 21:59 HKT - 完成 Teacher PPO command obs public rename：active A2 Teacher obs public terms 现在是 `a2_base_command_raw` 与 `a2_base_command`。`a2_base_command_raw` 是 warp/scale/clip 前 5D raw high-level base action `[x,y,yaw,pitch,roll]`，来源关系对应 G1 `unwarped_actions`；`a2_base_command` 是 processed/clipped/scaled 5D physical command obs，scale `[2,2,0.25,1,1]`，small-command zeroing 只作用 velocity/yaw `[0:3]`，不作用 pitch/roll。旧 public `unwarped_actions`、`base_command`、`b_homie_commands` 不再出现在 active A2 obs config 中。
- 2026-06-16 22:13 HKT - 完成 Teacher PPO critic-only `transition/complete/time_in_stage/actual_time_in_stage/total_time` obs PASS 标记；语义来自 `StagedTaskBase` stage/timer bookkeeping，robot-agnostic，不读取 robot/joint/body/contact。该 PASS 只覆盖 obs carrier/normalization direct reuse，不代表 stage1+ transition/reward semantics 完成。
- 2026-06-16 22:24 HKT - 三方 review（main + Ava + independent reviewer）结论均为 `FINISH_OK`：Teacher PPO door-open policy observation adaptation phase / obs carrier-input contract 可阶段性完成。当前 actor/critic dims 为 `133D/138D`，active obs terms 均已有 A2 mapping、direct reuse、strict replacement 或 A2-specific semantics。该完成边界不包含 PPO train smoke、stage1+ transition/reward correctness、Student/vision route，也不把 gripper aperture/contact/grasp cues、normalization/RMS、continuous gripper primitive 作为当前 obs adaptation blocker。
- 2026-07-07 22:09 HKT - Full-stage base_v6 当前 global A2 TCP/effort config：`gripper_handle_transform` source TCP offset 已从 historical `(0,0,0.105)` 改为 `(0,0,0.085)`，`arm_j7/j8 effort_limit_sim` 已从 `10.0/10.0` 改为 `40.0/40.0`；该 run 同时改变 TCP geometry 与 gripper effort cap，后续训练/eval 不能当作单变量 effort ablation 解读。

## Action Progress Snapshot

- 2026-06-12 22:59 HKT - 当前 action progress：Doorman 的 G1/HOMIE lower-body action chain 已替换为 frozen A2_Base locomotion policy；trainer 不再在 A2 path 加载 `model_walk.pt` / `model_stand.pt`，而是用 `gr00t/rl/data/policies/A2_Base/policy.pt` 和 `policy_metadata.json` 进行 TorchScript inference 与 contract validation。
- 2026-06-12 22:59 HKT - 当前 action interface：high-level actor 输出 `10D = 3D base command + 6D Piper arm + 1D gripper primitive`；trainer 拼接为 `22D = 10D high-level + 12D A2_Base leg action`；env compose 为 `20D = 12D legs + 6D arm_j1-6 + 2D arm_j7/arm_j8 gripper joints`。
- 2026-06-12 22:59 HKT - 历史 action semantics（old 10D snapshot，已由 2026-06-16 12D contract supersede）：base command 是 absolute，raw action 乘 `0.25` 后进入 A2_Base command slice；Piper arm dims `[3..8]` 走 delta 累积；Piper gripper old index 9 是 instantaneous 1D primitive，`+1` open、`0/negative` close/default，不进入 `delta_action_indices`。
- 2026-06-16 20:54 HKT - 当前 action interface supersedes 2026-06-12 10D/22D snapshot：high-level actor 输出 `12D = 5D base_command_raw [x,y,yaw,pitch,roll] + 6D Piper arm + 1D gripper primitive`；trainer 拼接为 `24D = 12D high-level + 12D A2_Base leg action`；env compose 仍为 `20D = 12D legs + 6D arm_j1-6 + 2D arm_j7/arm_j8 gripper joints`。
- 2026-06-16 20:54 HKT - 当前 action semantics supersedes 2026-06-12 3D base snapshot：base command order 为 `[x,y,yaw,pitch,roll]`；velocity/yaw `raw[:3] * 0.25` 后按 threshold clip，pitch/roll `raw[3:5].clamp(-1,1) * 0.4`；A2_Base command obs `[39:44]` 使用 physical `[x,y,yaw,pitch,roll] * [2,2,0.25,1,1]`。Piper arm dims `[5..10]` 走 delta 累积；Piper gripper dim `11` 是 instantaneous 1D primitive。
- 2026-06-12 22:59 HKT - 当前 validation boundary：已通过 `py_compile`、YAML/static metadata checks、TorchScript fake inference `[N,1620] -> [N,12]`、fake compose `[N,10]+[N,12]->[N,20]` 与 reviewer double check；未启动 PPO/train，也未启动 Isaac Sim/env smoke。下一步应接续 full task observation/reward 替换，再做 env/train smoke。
- 2026-06-12 23:05 HKT - 当前 action entrypoint names：`+exp=wbmanip/door_open_a2_base_lstm`、`/env: door_open_a2_base`、`/obs: wbmanip/door_open_a2_base`、`/rewards: wbmanip/reward_door_open_a2_base`、`/trainer: trl_a2_base_api`。
- 2026-06-12 23:17 HKT - Train smoke 溯源提醒：若后续 Hydra compose、Python import、checkpoint resume 或 log path 出现 `door_open_homie*`、`trl_homie_api`、`ppo_trainer_homie_api`、`homie_base` 相关 missing target / stale import / config not found，应优先回查 2026-06-12 23:05 HKT 的 action entrypoint rename；当前 canonical A2 entrypoint 是 `+exp=wbmanip/door_open_a2_base_lstm`，对应 env/obs/reward/trainer/source 均为 `a2_base` 命名。
- 2026-06-14 18:37 HKT - A2_Base locomotion replacement status：frozen A2_Base policy、`54D x 30` dog obs adapter、`12D` leg action remap、Piper arm/gripper action composition、USD LMP Stage1 plant 与 flat-walk full GUI visual check 已共同通过 milestone；后续 door policy 可把 A2_Base 当作 stable locomotion layer，而不是继续维护 G1/HOMIE lower-body path。
- 2026-06-16 14:49 HKT - Teacher observation `actions` surface 已与当前 A2 action stack 对齐为 `19D`：保留 frozen A2_Base `12D` leg output、DeltaActionBase 累积后的 `6D` Piper arm action，以及 `1D` gripper primitive raw；当时 base command 仍由 legacy `b_homie_commands` / later `base_command` 暴露，此 obs public naming 已由 2026-06-16 21:59 HKT 的 `a2_base_command_raw` / `a2_base_command` rename supersede。
- 2026-06-16 20:54 HKT - Teacher observation `actions` surface 仍为 `19D`：保留 frozen A2_Base `12D` leg output、DeltaActionBase 累积后的 `6D` Piper arm action，以及 `1D` gripper primitive raw；base command 不进入 `actions` obs。
- 2026-06-16 21:59 HKT - Teacher command observation public terms 已 rename 为 `a2_base_command_raw` raw 5D 与 `a2_base_command` processed/clipped/scaled 5D；actor/critic dims 仍保持 `133D/138D`。
- 2026-06-15 21:29 HKT - Future action work：当前 Piper gripper dim `11` 的 1D binary primitive 是 minimum viable 版本（`>0` open target，`<=0` close target）。下一版建议改为 continuous aperture primitive，并恢复原版 `FingerPrimitiveBase` 的安全思想：先记录 raw 越界量，再 clamp runtime action，最后用 clipped value 映射 gripper target。推荐语义为 `raw = high_level_actions[:, 11:12]`；`over_limit = relu(abs(raw) - 1.1)` 供 `limits_gripper_primitive_action` 使用；`clipped = raw.clamp(-1.0, 1.0)`；`alpha = (clipped + 1.0) * 0.5`；`target = close_target + alpha * (open_target - close_target)`。这表示 `raw=-1` close/min aperture、`raw=0` half aperture、`raw=+1` fully open；若后续确需 discrete primitive，可在 continuous `alpha` 上 quantize 到 `0/25/50/75/100%` bins，但优先保持 PPO-friendly continuous action surface。

## Observation Replacement Goal

2026-06-12 23:34 HKT - 下一阶段 observation 替换目标先聚焦 frozen A2_Base dog policy observation contract，保持 RoboDuet-compatible history：

- History shape: `54D x 30 = 1620D`，frame-major order 为 `[obs(t-29), obs(t-28), ..., obs(t)]`。
- RoboDuet source assumption: single-frame layout replicates RoboDuet `auto_train` path；`config_go1()` disables `observe_vel`，`config_wtw()` enables `observe_clock_inputs`，`auto_train()` disables `observe_two_prev_actions`，最终 dog actor obs 为 `54D`。
- `[0:3] projected_gravity_b`: 投影重力方向 `3D`。
- `[3:15] dog_joint_pos - default_joint_pos`: 腿部 `12` 关节位置偏差。
- `[15:27] dog_joint_vel x obs_scales.dof_vel`: 腿部 `12` 关节速度 scaled。
- `[27:39] dog_actions`: 上一步腿部 `12D` action。
- `[39:44] commands_dog x commands_scale_dog`: 狗指令 `[lin_x, lin_y, yaw, pitch, roll]`。
- `[44:50] arm_command_obs`: 机械臂目标观测 `6D`，语义为 `lpy + abg`。
- `[50] base_roll`: 机体 roll angle，单位 rad。
- `[51] base_pitch`: 机体 pitch angle，单位 rad。
- `[52:54] clock_inputs`: global gait clock `[sin, cos]`。

Implementation reminder:

- 用户强调原始设计按 IsaacLab `manager-based` workflow 规范使用 `ObservationManager` 管理 observation 拼接与 history；后续实现前必须查询 IsaacLab official docs（Context7 library ID `/websites/isaac-sim_github_io_isaaclab_main`）并可对照 local source `/home/baoquanc/workspace/IsaacLab`，确认 `direct` workflow 与 `manager-based` workflow 在 observation registration、`ObsTerm`、`ObsGroup.concatenate_terms=True`、`history_length=30`、`flatten_history_dim=False` 等行为上的差异。
- 目标 manager-based 语义：每个 observation semantic field 注册为独立 `ObsTerm`，由 `ObsGroup.concatenate_terms=True` 拼接单帧 observation；`history_length=30` 保留最近 30 帧；`flatten_history_dim=False` 让 manager 返回 `(N, H, D)`，wrapper 再展平成 RoboDuet-compatible frame-major history。
- 当前 Doorman/A2 path 是否继续沿用 direct env obs hooks、引入 manager-based adapter、或做 wrapper bridge，需要等用户逐项给出详细逻辑后再定；不要在未确认 workflow 差异前直接大改 observation runtime。
- A2_Base manager-based training source: `/home/baoquanc/workspace/LMP/source/LMP/LMP/tasks/manager_based/lmp_manager/lmp_manager_env_cfg.py`。后续每个 field implementation 前，应先提取训练时对应 `ObsTerm`/helper/config 的数据源、scale、update timing、history/clock/action buffer 语义，再映射到 DoorDog 当前 `door_open_a2_base` direct path。

2026-06-14 18:37 HKT - A2_Base low-level dog observation/action migration 已由用户 visual monitor 标记为成功；后续 `Observation Replacement Goal` 的主语切换为 door-opening training policy 的 task-level observation/action：Piper arm/gripper proprioception、EE/handle/door state、door/handle task frame、normalization、actor/critic obs contract，以及 high-level door policy action surface。
2026-06-16 13:58 HKT - Teacher PPO experiment 是当前短期优先级；Student DAgger vision / distillation 暂缓。Teacher PPO network architecture 复用 G1 origin recurrent actor/critic，只围绕 A2_Piper door task 改 observation input 和 action output。
2026-06-16 14:49 HKT - 第一批 G1 origin parity 已完成 `dof_pos/dof_vel/actions`。2026-06-16 15:34 HKT 第二批 direct reuse 已标记 `PASS`：`projected_gravity`、`base_lin_vel`、`base_ang_vel`、`relative_to_door`、`door_dof_pos`。后续又完成 Piper EE/handle frame、hand-force/contact strict replacement 与 command obs rename。
2026-06-16 22:24 HKT - Teacher PPO observation adaptation phase 已阶段性完成：active obs direct reuse/pass 列表包含 `projected_gravity/base_lin_vel/base_ang_vel/relative_to_door/door_dof_pos`、`privileged_door_info`、`stage`、critic-only `transition/complete/time_in_stage/actual_time_in_stage/total_time`，并已完成 `hand_force -> 6D arm_body7/8 force`、`hand_handle_transform -> gripper_handle_transform 18D TCP-to-handle/pregrasp`、`a2_base_command_raw` raw 5D、`a2_base_command` processed/clipped/scaled 5D、`delta_actions` 6D Piper arm raw delta semantics 与 `actions` 19D A2/G1 parity surface。当前 actor/critic dims 为 `133D/138D`。gripper aperture/contact/grasp cues、normalization/RMS、actor/critic privileged split 与 continuous gripper primitive 进入 post-finish enhancement/validation；stage1+ transition/reward correctness 明确转入下一阶段。
2026-07-07 22:09 HKT - base_v6 TCP/effort A/B 已改变 current `gripper_handle_transform` source geometry：历史 `(0,0,0.105)` 只作为 2026-06-16/06-26 baseline；当前训练/eval 应按 `(0,0,0.085)` 解读 TCP-to-handle observation、pregrasp/handle distance 和 grasp-frame diagnostics。

## TODO Summary

- 2026-06-16 19:38 HKT - A2_Piper USD physics/control plant 已对齐 LMP Stage1，且 Teacher obs 已有 Piper TCP-to-handle/pregrasp frame；剩余 training-grade kinematics/collision mapping TODO 收窄为 door-task contact body selection、arm/gripper contact semantics 与 reward/observation 侧验证。
- 2026-06-16 22:24 HKT - Teacher PPO obs adaptation phase 已阶段性完成，并已移出当前 obs 未完成清单：当前 actor/critic dims 为 `133D/138D`，active obs terms 均已归类为 A2 mapping、direct reuse、strict replacement 或 A2-specific semantics。下一阶段 TODO 转入 stage1 reward + transition correctness；obs 相关仅保留 post-finish enhancement/validation，包括 gripper aperture/contact/grasp cues、normalization/RMS、PPO smoke 后调参、actor/critic privileged split 与 continuous gripper primitive。Network skeleton 仍复用 G1 recurrent actor/critic；Student DAgger vision / distillation route 暂缓。
- 2026-06-13 21:15 HKT - Observation migration workflow TODO：每个 A2_Base obs field 实现前，先从 LMP manager-based training source `lmp_manager_env_cfg.py` 及其 helper 中确认训练时计算/更新逻辑，再给出 DoorDog 当前 direct path 的实现方案；长期协作 subagent Bella 负责辅助提取/总结这部分来源逻辑。
- 2026-06-15 22:44 HKT - A2+Piper reward adaptation TODO：stage0 reward 与大部分 global reward 已形成第一版 baseline；后续重点转向 stage1/pregrasp、grasp、open、swing、through 的 Piper EE/handle interaction、gripper/contact semantics、door progress、success condition 与 reward weights。
- 2026-06-15 22:44 HKT - Reward implementation workflow TODO：后续 stage1+ reward 设计、实现、review 前仍先读 `memory/a2-piper/reward-implementation-goal/description.md`，并按 Bella/Galileo、Ava 与 IsaacLab direct workflow 约束执行；若新增 stage-specific transition doc，继续维护 `A2适配状态` 列。
- 2026-06-12 18:02 HKT - 在 preview-only env 之后继续接入并验证 training env config、training config、smoke test 与 eval workflow，形成可重复的训练入口。
- 2026-06-12 23:17 HKT - 后续 train smoke 若遇到 Hydra/import/checkpoint resume 指向旧 `homie` entrypoint 的错误，先按 action entrypoint rename 记录检查命令、config defaults、`_target_`、log/checkpoint metadata 是否仍引用旧名。
- 2026-06-12 19:35 HKT - 后续若 `door_open_a2_base.py::_reset_root_states` 的 Doorman stage-0 hardcoded x/y/yaw bounds 改动，需同步更新 A2_Piper preview local constants 与 README，避免 placement bounds preview 漂移。

## DONE Summary

- 2026-07-13 16:37 HKT - 在长期 door-training goal 中注册 `push-open-door-optimization` active route，并把当前 baseline 更新为 v7/v9 的 TCP `0.085`、Kp/Kd `80/3`、effort `10/10`；base_v6 `40/40` 保留为 historical mixed-factor record。
- 2026-07-07 22:09 HKT - 记录 base_v6 current TCP/effort config：A2 `gripper_handle_transform` source TCP offset `(0,0,0.085)`，`arm_j7/j8 effort_limit_sim=40.0/40.0`；历史 `0.105` geometry 仅作为 earlier baseline。
- 2026-06-12 16:59 HKT - 新建独立 memory entry，记录基于 Doorman 替换用户自有 robot 并适配 observation/action/reward 完成开门训练的长期目标。
- 2026-06-12 17:07 HKT - 记录用户已加入 A2_Piper robot URDF assets：`gr00t/rl/data/robots/A2_Piper/a2_piper.urdf` 与对应 `meshes/` STL assets。
- 2026-06-12 18:02 HKT - 完成 preview milestone：`gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 定义 A2_Piper DOF/body/limits/default joint pose，`gr00t/rl/data/robots/A2_Piper/a2_piper.usd` 由 URDF 生成，`gr00t/rl/envs/door/a2_piper_door_scene_preview.py` 与 `gr00t/rl/scripts/preview_a2_piper_door_scene.py` 提供 Doorman door scene + A2_Piper zero-action hold preview；入口缺失 USD 时 fail-fast 并打印生成命令，不 fallback to G1。
- 2026-06-12 18:30 HKT - 完成 reviewer fixes：preview scene 禁用 `replicate_physics`，entrypoint 支持 direct conda IsaacLab Python repo import，missing USD 在 app launch 前 fail-fast，teardown 使用 public SimulationContext callback/instance cleanup；`--max-steps 1` bounded smoke clean exit。
- 2026-06-12 18:52 HKT - 修复 preview livestream/headless runtime caveat：`AppLauncher` toolbar button hiding 缺少 `omni.kit.widget.toolbar` 时被 preview-local wrapper 转为 warning，其他 exception 仍会 propagate。
- 2026-06-12 18:56 HKT - 完成 P3 cleanup：toolbar guard 仅匹配 `exc.name == "omni.kit.widget.toolbar"`；livestream/headless camera preview 不再 copy rendering kit 到 IsaacLab apps，而是使用 existing IsaacLab kit 或 repo-local read-only fallback。
- 2026-06-12 19:08 HKT - 修复 preview UsdRT GPU selection caveat：entrypoint 对 `--device cuda:N` (`N != 0`) 做 preview-local fail-fast，并更新 README 示例为 `CUDA_VISIBLE_DEVICES=N ... --device cuda:0`。
- 2026-06-12 19:25 HKT - 完成 preview-only placement bounds visualization：entrypoint 新增 `--placement-preview corners`、`--show-placement-corners` 与 x/y/yaw half range CLI；scene reset 支持 per-env robot root pose override，4 个 env 分别显示 XY 四角，默认单 robot preview 行为不变。
- 2026-06-12 19:35 HKT - Reviewer correction：`--placement-preview corners` 默认改为 Doorman stage-0 reset bounds，而非 root-centered preview range；新增 `--placement-bounds root-centered` 作为显式 preview-only override，并在 scene 中本地定义 Doorman bounds constants 以避免 runtime import HOMIE/G1/hand logic。
- 2026-06-12 19:52 HKT - 记录用户判断：当前 Doorman stage-0 reset 的 robot-door relative pose/orientation range 可接受，可作为下一阶段 reward/observation/pregrasp 调整的初始 placement assumption。
- 2026-06-12 20:08 HKT - 记录用户已具备 mature A2 locomotion base policy；observation/action 迁移短期目标改为围绕该 locomotion policy 的 input/output contract 进行接口适配，并让 Piper arm/gripper task policy 建立在稳定 locomotion support 之上。
- 2026-06-12 20:23 HKT - 记录 A2_Piper action 迁移约束：Piper gripper 使用 1D gripper primitive 表达 open/close，不复用 G1/HOMIE 的 2D finger primitive 或逐 finger joint action 设计。
- 2026-06-12 20:55 HKT - 完成 A2_Base locomotion policy asset copy：`policy.pt` 与 `policy_metadata.json` 已从 LMP exported checkpoint 复制到 `gr00t/rl/data/policies/A2_Base/`，并通过 sha256 比对确认 copy 一致。
- 2026-06-12 20:56 HKT - 完成 A2_Base policy load smoke：在 conda env `isaaclab` 中 `torch.jit.load` 成功，zero obs `[2,1620]` inference 输出 `[2,12]`，确认 exported policy 与 metadata shape contract 对齐。
- 2026-06-12 22:41 HKT - 完成 Doorman action chain 第一阶段替换：当前入口已命名为 `door_open_a2_base_lstm`，切到 `robot/A2_Piper/a2_piper.yaml` 与 A2_Base mode；`trl_a2_base_api` 在 A2 mode 不加载 `model_walk.pt`/`model_stand.pt`，改为 frozen TorchScript A2_Base，读取 `obs_dict["a2_base_obs"]` 并在 final frame dog command slice 注入 `raw_base_action * 0.25 * [2.0, 2.0, 0.25]`；`A2Base` 将 `22D` rollout action compose 成 `20D` simulator joint-space command，并按 metadata leg order name-based remap；Piper gripper primitive `+1` 映射 open target `[0.035,-0.035]`，`0/negative` 映射 close/default `[0,0]`。
- 2026-06-12 22:41 HKT - 完成 minimal A2_Base obs adapter：新增 `a2_base_obs`，按 `30 x 54 = 1620D` frame-major history 输出；single frame layout 为 projected gravity、12D leg pos delta、12D leg vel `*0.05`、last 12D leg action、5D dog command、6D zero arm goal、base roll/pitch、2D gait clock。G1 grasp/contact reward 本阶段 zero-scaled/guarded；未做 train smoke 或 Isaac Sim/env smoke。
- 2026-06-12 22:50 HKT - 完成 reviewer follow-up：`delta_action_indices` 改为 `[3,4,5,6,7,8]`，保持 base absolute、arm 6D delta、gripper 1D instantaneous primitive；`policy_metadata.json` path 已 wire 到 env/trainer config，trainer/env 均读取 metadata 并 fail-fast 校验 duplicated YAML override 与 metadata drift，runtime leg order 从 metadata 派生且必须与 override 一致。验证仅限 py_compile、YAML/static metadata、TorchScript 与 fake compose smoke，未跑 PPO/train 或 Isaac Sim/env。
- 2026-06-12 22:59 HKT - 整理当前 action progress snapshot，明确 action chain replacement 已完成到 static/reviewer-approved milestone：G1/HOMIE lower-body 被 A2_Base 替代，high-level action 为 `10D`，gripper 为 instantaneous 1D primitive，后续重点转入 full task observation/reward 与 env/train smoke。
- 2026-06-12 23:05 HKT - 完成当前 A2 action-chain entrypoint rename：primary config/source 从 `door_open_homie_lstm`、`door_open_homie`、`reward_door_open_homie`、`trl_homie_api`、`ppo_trainer_homie_api`、`homie_base` 重命名为 `door_open_a2_base_lstm`、`door_open_a2_base`、`reward_door_open_a2_base`、`trl_a2_base_api`、`ppo_trainer_a2_base_api`、`a2_base`；primary env import/继承改用 `A2Base`，旧 `HomieBase` 仅作为新 module 内兼容 alias 保留。
- 2026-06-12 23:17 HKT - 补充 action entrypoint rename 的 train smoke traceability reminder：后续若 smoke 失败并出现旧 `homie` config/module 名，应优先检查命令、Hydra defaults、`_target_`、resume checkpoint/log metadata 是否还指向 rename 前入口。
- 2026-06-12 23:34 HKT - 记录下一阶段 observation replacement Goal/TODO：A2_Base dog policy observation 目标为 RoboDuet-compatible `54D x 30 = 1620D` history，single-frame semantic slices 已写入 memory，并补充实现前必须查询 IsaacLab official docs/local source 以确认 `direct` 与 `manager-based ObservationManager` workflow 差异。
- 2026-06-13 21:15 HKT - 记录 A2_Base manager-based training source 与 observation migration workflow：A2_Base 来源入口为 LMP `lmp_manager_env_cfg.py`，后续每个 observation field 先追溯训练时 computation/update logic，再制定 DoorDog direct path 实现方案；Bella 作为长期只读 subagent 协助提取/总结 LMP observation/action 逻辑。
- 2026-06-13 21:33 HKT - 完成 A2_Base observation slice `0:27` parity：`_get_a2_projected_gravity_b()` 对齐 `projected_gravity`，`_get_a2_dog_joint_pos_rel()` 对齐 `joint_pos_rel` + default offset，`_get_a2_dog_joint_vel_scaled()` 对齐 `joint_vel(scale=0.05)`；env config 显式记录 `dog_joint_vel_scale: 0.05`，history reset parity 支持 uninitialized env 首帧 full-history fill 与 mixed batch shift/append。
- 2026-06-13 22:00 HKT - 完成 A2_Base observation slice `27:50` parity：新增 `_get_a2_dog_actions()` 返回 raw `_last_a2_leg_actions`，`_get_a2_commands_dog_scaled()` 输出 `[lin_x, lin_y, yaw, pitch, roll]`，`_get_a2_arm_command_obs()` 输出 6D zero arm command；env config 显式记录 `command_scale: 0.25`、`command_obs_multipliers: [2.0, 2.0, 0.25]`、`body_pitch_roll_scale: 0.4`，trainer 保持 10D high-level action 且不再清零 final frame `[42:44]`。验证通过 `py_compile`、A2Base fake tensor smoke、trainer fake smoke 与 `body_pitch_roll_scale == 0.4` static check；未启动 PPO/Isaac Sim。
- 2026-06-13 22:13 HKT - 完成 A2_Base observation slice `50:52` parity：`_get_a2_base_roll_pitch()` 对齐 LMP `base_roll_pitch()` 的 roll then pitch 语义，DoorDog direct path 使用 `LeggedRobotBase` 已维护的 `self.rpy[:, 0:2]` 写入 frame `[50:52]`；验证通过 `py_compile`、A2Base fake tensor smoke 与 `git diff --check`，未启动 PPO/Isaac Sim。
- 2026-06-14 17:22 HKT - 完成 A2_Base observation slice `52:54` parity：新增 direct gait phase buffer `_a2_gait_phase` 与 `_a2_gait_last_update_step`，按 LMP `GaitPhaseCommand` 语义在每个 `common_step_counter` 最多 advance 一次，standing physical command phase reset 为 0，`clock_inputs` 输出 `[sin(2*pi*phase), cos(2*pi*phase)]`；验证通过 `py_compile`、A2Base fake tensor smoke、YAML/static grep 与 `git diff --check`，未启动 PPO/Isaac Sim。
- 2026-06-14 17:48 HKT - 完成 standalone full GUI A2_Base flat walk smoke entrypoint：`smoke_a2_base_flat_walk.py` 复用 preview AppLauncher/toolbar guard/logical `cuda:0` fail-fast/cleanup 思路与 A2_Piper robot cfg，构建 flat scene（ground、dome light、robot only），按 metadata leg order name-based remap policy action 到 simulator joint targets，并在 `gr00t/rl/scripts/README.md` 记录 launch command 与 raw/physical command convention；未启动 full GUI。
- 2026-06-14 18:27 HKT - 完成 A2_Piper USD Plant 对齐 LMP Stage1：保持 `UsdFileCfg`/`a2_piper.usd` entrypoint，不切 URDF；patch `configuration/a2_piper_physics.usd` articulation/rigid/drive attrs，并同步 preview/flat-walk builder、A2 door training runtime overrides、robot YAML 与 README。当前 USD readback 确认 self-collision enabled、solver `4/0`、sleep `0.005`、stabilization `0.001`、rigid max velocity `1000.0`、depenetration `300.0`、damping `0.0`、force-style neutral drive；training-grade kinematics/collision TODO 已收窄到 door-task contact body 与 EE/handle frame 验证。
- 2026-06-14 18:37 HKT - 用户 full GUI monitor 确认 A2_Base flat-walk 已能正常 walk；A2_Base observation/action build 与 USD LMP Stage1 plant 对齐整体标记为成功，当前可替代 G1/HOMIE locomotion policy。后续工作切换到 door-opening policy 的 task observation/action 与 A2+Piper reward adaptation。
- 2026-06-14 20:54 HKT - 完成 G1 Doorman stage0 reward/transition 人类可读表格：`scriptsFORhuman/g1_doorman_stage0_reward_transition.md`，作为 A2+Piper stage0 reward adaptation 的 baseline reference。
- 2026-06-14 21:48 HKT - 新建 reward implementation memory entry，记录 global/stage0 reward 小目标、IsaacLab direct workflow 约束、Bella/Galileo 与 Ava 协作职责，以及 Doorman-derived 破坏性修改审核门槛。
- 2026-06-15 22:44 HKT - 用户确认 stage0 reward 与大部分 global reward 已完成可复用审核和 A2_Piper adjustment；长期 door-training 目标中的 reward work 从 stage0/global baseline 迁移收窄为 stage1+ interaction/progress/success reward 与 smoke 后权重调参。
- 2026-06-15 23:06 HKT - 完成 G1 Doorman policy stack / A2 adaptation map 文档：`scriptsFORhuman/g1_doorman_policy_stack_a2_adaptation_map.md`。Ava 核查 origin code 后，文档分类记录 teacher PPO、student DAgger vision、network structure、action contract、observation contract、stage/sensor 配套与当前 A2 adaptation 状态，作为下一步 door policy / arm policy observation-action design 的入口。
- 2026-06-16 13:58 HKT - 记录短期 policy/training route：当前先做 Teacher PPO experiment；Student DAgger vision / student trainer / distillation 暂缓；Teacher PPO Actor/Critic network 复用 G1 origin `RecurrentActor` / `RecurrentCritic` recurrent architecture，只修改 A2_Piper door task 的 observation input 与 action output contract。
- 2026-06-16 14:08 HKT - 完成 G1 Teacher privileged observation 详细表：`scriptsFORhuman/g1_doorman_teacher_privileged_obs_a2_adaptation_map.md`。该表单独展开 actor/critic obs term、dim/order、origin getter、A2 current status 与 Teacher PPO short-term design implications，明确 A2 当前 `hand_handle_transform` / `hand_force` 只是 zeros compatibility。
- 2026-06-16 14:49 HKT - 完成本批 Teacher high-level `dof_pos/dof_vel/actions` observation parity：`dof_pos/dof_vel` 保持 full A2 robot `20D`，`actions` 改为 `19D = 12D A2_Base leg output + 6D effective Piper arm action + 1D gripper primitive raw`；同步更新 obs config、A2Base getter 与两份 `scriptsFORhuman` adaptation map，记录 actor obs `175D`、critic obs `180D`。
- 2026-06-16 15:34 HKT - 完成第二批 Teacher high-level observation direct reuse 标记：`projected_gravity`、`base_lin_vel`、`base_ang_vel`、`relative_to_door`、`door_dof_pos` 不需要 code adaptation；已同步 `scriptsFORhuman/g1_doorman_teacher_privileged_obs_a2_adaptation_map.md` 与 policy stack map。
- 2026-06-16 19:38 HKT - 完成 A2 Teacher obs strict replacement：`hand_force` 改为 `arm_body7`/`arm_body8` gripper net/body force 6D；`hand_handle_transform` rename/替换为 `gripper_handle_transform` 18D，使用 `arm_body6_to_gripper` source TCP offset 与 `grasp_target` handle/pregrasp target frames；A2 path 无 zeros fallback、无 door-root approximation，相关 missing/mismatch 状态 fail-fast。
- 2026-06-16 20:54 HKT - 完成 A2 Teacher PPO high-level action contract 10D/22D -> 12D/24D 迁移：旧 `10D = 3D base + 6D Piper arm + 1D gripper` 与 `22D = 10D + 12D A2_Base` 记录已 superseded；新 contract 为 `12D = 5D base_command_raw [x,y,yaw,pitch,roll] + 6D Piper arm_j1..j6 + 1D gripper primitive`，trainer rollout `24D = 12D high-level + 12D A2_Base leg action`，final simulator joint command 仍为 `20D`。当时 command obs 仍使用旧 public names，已由 2026-06-16 21:59 HKT 的 `a2_base_command_raw` / `a2_base_command` rename supersede；`actions` obs 保持 `19D`，actor/critic dims 保持 `133D/138D`。
- 2026-06-16 21:59 HKT - 完成 Teacher PPO command obs public rename：`unwarped_actions -> a2_base_command_raw`，`base_command -> a2_base_command`；`a2_base_command_raw` 为 raw 5D `[x,y,yaw,pitch,roll]` high-level base action before warp/scale/clip，`a2_base_command` 为 processed/clipped/scaled 5D physical command obs，obs scale `[2,2,0.25,1,1]`，small-command zeroing 只作用 velocity/yaw `[0:3]`。
- 2026-06-16 21:46 HKT - 完成 Teacher PPO obs status 文档同步：`privileged_door_info`、`stage`、`delta_actions` 三项已在 privileged obs map 与 policy stack map 中状态更新；`delta_actions` 明确为 6D Piper arm raw delta only，不含 5D base command 或 gripper primitive。
- 2026-06-16 22:13 HKT - 完成 Teacher PPO critic-only `transition/complete/time_in_stage/actual_time_in_stage/total_time` obs PASS 标记；语义来自 `StagedTaskBase` stage/timer bookkeeping，robot-agnostic，不读取 robot/joint/body/contact，obs carrier/normalization 可 direct reuse。
- 2026-06-16 22:24 HKT - 三方 review（main + Ava + independent reviewer）确认 Teacher PPO door-open policy obs adaptation 阶段性完成：actor/critic input contract 当前为 `133D/138D`，active obs terms 均已有 A2 mapping/direct reuse/strict replacement/A2-specific semantics；后续切到 stage1 reward + transition correctness，且不把 PPO train smoke、Student/vision route、gripper aperture/contact/grasp cues、normalization/RMS 或 continuous gripper primitive 计入本阶段完成范围。

## Recommended Next Files To Read

- `memory/a2-piper/worktree-routing/description.md`
- `memory/origin-reference/door-workflows/description.md`
- `memory/origin-reference/assets-and-data/description.md`
- `memory/origin-reference/repo-baseline/description.md`
- `scriptsFORhuman/g1_doorman_policy_stack_a2_adaptation_map.md`
