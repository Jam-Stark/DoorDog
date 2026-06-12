---
name: doorman-door-training-goal
scope: A2_Piper long-term goal for Doorman-based robot replacement and door-opening training
status: active
last_updated: 2026-06-12 23:17 HKT
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
- 2026-06-12 22:50 HKT - Reviewer follow-up 已修复 action contract 细节：Piper gripper primitive 从 `delta_action_indices` 移除，现仅 arm dims `[3..8]` 累积 delta，gripper dim `9` 保持 instantaneous open/close primitive；A2_Base `policy_metadata.json` 已接入 trainer/env setup，用于校验/派生 `1620D` obs、`30 x 54` history、`12D` action、metadata leg order、`leg_action_scale=0.25` 与 `use_default_offset=true`。

## Action Progress Snapshot

- 2026-06-12 22:59 HKT - 当前 action progress：Doorman 的 G1/HOMIE lower-body action chain 已替换为 frozen A2_Base locomotion policy；trainer 不再在 A2 path 加载 `model_walk.pt` / `model_stand.pt`，而是用 `gr00t/rl/data/policies/A2_Base/policy.pt` 和 `policy_metadata.json` 进行 TorchScript inference 与 contract validation。
- 2026-06-12 22:59 HKT - 当前 action interface：high-level actor 输出 `10D = 3D base command + 6D Piper arm + 1D gripper primitive`；trainer 拼接为 `22D = 10D high-level + 12D A2_Base leg action`；env compose 为 `20D = 12D legs + 6D arm_j1-6 + 2D arm_j7/arm_j8 gripper joints`。
- 2026-06-12 22:59 HKT - 当前 action semantics：base command 是 absolute，raw action 乘 `0.25` 后进入 A2_Base command slice；Piper arm dims `[3..8]` 走 delta 累积；Piper gripper dim `9` 是 instantaneous 1D primitive，`+1` open、`0/negative` close/default，不进入 `delta_action_indices`。
- 2026-06-12 22:59 HKT - 当前 validation boundary：已通过 `py_compile`、YAML/static metadata checks、TorchScript fake inference `[N,1620] -> [N,12]`、fake compose `[N,10]+[N,12]->[N,20]` 与 reviewer double check；未启动 PPO/train，也未启动 Isaac Sim/env smoke。下一步应接续 full task observation/reward 替换，再做 env/train smoke。
- 2026-06-12 23:05 HKT - 当前 action entrypoint names：`+exp=wbmanip/door_open_a2_base_lstm`、`/env: door_open_a2_base`、`/obs: wbmanip/door_open_a2_base`、`/rewards: wbmanip/reward_door_open_a2_base`、`/trainer: trl_a2_base_api`。
- 2026-06-12 23:17 HKT - Train smoke 溯源提醒：若后续 Hydra compose、Python import、checkpoint resume 或 log path 出现 `door_open_homie*`、`trl_homie_api`、`ppo_trainer_homie_api`、`homie_base` 相关 missing target / stale import / config not found，应优先回查 2026-06-12 23:05 HKT 的 action entrypoint rename；当前 canonical A2 entrypoint 是 `+exp=wbmanip/door_open_a2_base_lstm`，对应 env/obs/reward/trainer/source 均为 `a2_base` 命名。

## TODO Summary

- 2026-06-12 18:02 HKT - 后续训练阶段需在 preview 基础上设计 training-grade A2_Piper kinematics/collision/control mapping，并决定是否复用/替换现有 simulator `robot.asset.usd_file` loader。
- 2026-06-12 22:41 HKT - 后续 observation 目标：在已完成 `a2_base_obs` low-level adapter 之外，继续设计 training-grade A2_Piper task observation，覆盖 Piper arm/gripper proprioception、EE/handle/door state、door/handle task frame、normalization 与 actor/critic obs contract。
- 2026-06-12 16:59 HKT - 设计 door-opening reward spec，覆盖 approach、handle interaction、door progress、success condition、termination、penalty 与 reward weights。
- 2026-06-12 18:02 HKT - 在 preview-only env 之后继续接入并验证 training env config、training config、smoke test 与 eval workflow，形成可重复的训练入口。
- 2026-06-12 23:17 HKT - 后续 train smoke 若遇到 Hydra/import/checkpoint resume 指向旧 `homie` entrypoint 的错误，先按 action entrypoint rename 记录检查命令、config defaults、`_target_`、log/checkpoint metadata 是否仍引用旧名。
- 2026-06-12 19:35 HKT - 后续若 `door_open_a2_base.py::_reset_root_states` 的 Doorman stage-0 hardcoded x/y/yaw bounds 改动，需同步更新 A2_Piper preview local constants 与 README，避免 placement bounds preview 漂移。

## DONE Summary

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

## Recommended Next Files To Read

- `memory/a2-piper/worktree-routing/description.md`
- `memory/origin-reference/door-workflows/description.md`
- `memory/origin-reference/assets-and-data/description.md`
- `memory/origin-reference/repo-baseline/description.md`
