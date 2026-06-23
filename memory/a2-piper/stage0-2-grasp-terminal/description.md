---
name: stage0-2-grasp-terminal
scope: quickTEST branch stage0-2-only Teacher PPO experiment where stage2 grasp completion is terminal success
status: active
last_updated: 2026-06-23 13:41 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/stage0-2-grasp-terminal/description.md
  - memory/a2-piper/stage0-2-grasp-terminal/TODO.md
  - memory/a2-piper/stage0-2-grasp-terminal/DONE.md
read_when:
  - 开始 quickTEST 分支的 stage0-2-only training config、stage truncation、grasp terminal success 或相关 train smoke 前
  - 需要确认 stage2 grasp completion 是否应作为 terminal success，以及是否可以 resume full 6-stage checkpoint 时
---

# Stage0-2 Grasp Terminal

## Purpose

记录 `quickTEST` 分支的独立实验目标：先训练/验证 A2_Piper Teacher PPO 的 `stage0 -> stage1 -> stage2` 流程，只要求走到并成功握住 door handle；暂时屏蔽 `stage3` 及其后的 open/swing/through 任务。该 entry 不替代 full door-opening 主线，只服务于快速验证 walk、pregrasp、grasp 三段是否能学起来。

## Current Decision

- 2026-06-22 20:29 HKT - 用户确认从 `A2_Piper` 切出新分支 `quickTEST`，用于 stage0-2 grasp-terminal quick test。
- 2026-06-22 20:42 HKT - 已新增独立 config `gr00t/rl/config/exp/wbmanip/door_open_a2_base_stage0_2_grasp_terminal_lstm.yaml`，入口为 `+exp=wbmanip/door_open_a2_base_stage0_2_grasp_terminal_lstm`；默认 `door_open_a2_base_lstm.yaml` 未改动。
- 2026-06-22 21:23 HKT - `PolicyAndValueWrapper` 已改为通过 `object.__setattr__(..., "_a2_base_model", a2_base_model)` 持有 frozen A2_Base TorchScript model，并用 property 暴露访问；该 model 不再注册为 child `nn.Module`，避免 HuggingFace Trainer optimizer parameter scanning 进入 TorchScript `ParameterDict.contains()` crash。
- 2026-06-22 21:31 HKT - `piper_gripper_handle_frame_transformer` 已切换为 A2-local `OrderedTargetFrameTransformer`，保留 `handle -> pregrasp` target order；bounded smoke 已越过旧 target-order fail-fast，当前下一 blocker 是 `_homie_history_length` missing init。
- 2026-06-22 21:35 HKT - A2_Base init path 已显式初始化 `_homie_history_length`，bounded smoke 已越过 `a_history_homie` reset observation；当前下一 blocker 是 `ResetFromDataset` 的 `reset_count` missing init。
- 2026-06-22 21:39 HKT - stage0-2 quick config 已显式关闭 G1 `ResetFromDataset` motion reset，bounded smoke 已推进到 PPO recurrent model forward；当前下一 blocker 是 A2_Base frozen policy injection 的 recurrent minibatch shape mismatch。
- 2026-06-22 22:03 HKT - PPO recurrent A2_Base injection shape mismatch 已按最小边界修复：只在 A2_Base injection 侧将 padded `a2_base_obs` unsplit 回 env-major 后与 `high_level_actions` 对齐，不改 PPO loss tensors 的 env-major contract。
- Stage mapping 保持 Doorman/A2 当前语义：`stage0 = STAGE_WALK_TO_DOOR`，`stage1 = STAGE_PREGRASP`，`stage2 = STAGE_GRASP`。
- 在本 quick test 中，`_stage_2_to_complete_condition()` 表示 terminal success；也就是 A2 branch 的 handle-specific two-sided gripper contact、source local `+Y` squeeze threshold 与 opposite-sign squeeze check 成立后，视为任务完成。
- 默认 full task 仍是 6-stage：`STAGE_OPEN`、`STAGE_SWING`、`STAGE_THROUGH` 不应从主线删除；本实验应通过独立 config 或 branch-local override 实现，不污染默认 `door_open_a2_base_lstm` 语义。

## Source Facts

- 当前 `StagedTaskBase` 通过 `len(env.config.max_stage_time)` 决定 `num_stages`，并把最后一个 stage 的 `_stage_{last}_to_complete_condition()` 注册为 task complete condition。
- 当前默认 A2 env config 是 6-stage：`max_stage_time`、`stage_reward_scale` 与 `staged_reset_ratios` 都是 6 项。
- 当前默认代码中 `_stage_2_to_complete_condition()` 已实现 A2 grasp completion；但在 6-stage config 下，`_stage_2_to_3_advance_condition()` 使用 `completion | door_open_bypass` 进入 stage3，不是 episode terminal。
- `stage` observation dim 来自 `len(env.config.max_stage_time)`。把任务截成 3-stage 会改变 actor/critic input dim，因此不能直接 resume 6-stage checkpoint。
- 2026-06-22 20:42 HKT static validation resolved `obs_dims.stage: 3`，并确认 stage3+ reward scales 在 quick test config 中为 `0.0`。
- 2026-06-22 21:23 HKT reviewer validation: `py_compile` passed；lightweight probe confirmed A2_Base TorchScript is absent from wrapper `named_children()` / `named_modules()` / `named_parameters()` while property access still works；bounded smoke reached `Using frozen A2_Base policy for low-level leg actions` and `===training policy===`，说明旧 optimizer `ParameterDict contains()` blocker 已移除。
- 2026-06-22 21:31 HKT source fact: IsaacLab `FrameTransformer` 对 duplicate target body 的 frame names 使用 `set`，会让同一个 `grasp_target` rigid body 上的 `handle` / `pregrasp` target order 不可靠；A2-local `OrderedTargetFrameTransformer` 只用于该 gripper-handle sensor，并让 `_get_a2_gripper_handle_frame_transformer()` 保持 exact `['handle', 'pregrasp']` fail-fast contract。
- 2026-06-22 21:35 HKT source fact: `A2Base.__init__` 在 `a2_base.enabled=True` 时执行 `LeggedRobotBase.__init__()`、`_init_a2_base_action_chain()` 后直接 return，因此 non-A2/Homie branch 中的 `_homie_history_length` 初始化不会执行；但 A2 obs config 仍在 `homie_obs` 使用 `a_history_homie`，所以 A2 init path 也必须显式初始化该 field。
- 2026-06-22 21:37 HKT source fact: A2 explicit `ResetFromDataset` init 会加载 `${HOME}/projects/LAFAN-G1` G1 motion files，并在 mapping dof names 时用 `left_hip_pitch_joint` 匹配 A2 robot dof，触发 fail-fast mismatch；因此 stage0-2 quick test 应显式禁用该 G1 motion reset path，而不是给 A2 做 name fallback。
- 2026-06-22 22:03 HKT source fact: recurrent minibatch 中 `mb_obs_dict` 使用 padded trajectory layout `[num_trajectories, max_traj_len, ...]`，但 `actions/logprobs/values/returns/advantages/padding_mask` 保持 rollout env-major `[num_envs, num_steps, ...]`；`RecurrentActor` / `RecurrentCritic` training path 会对 padded `memory_out` 执行 `unsplit_trajectories(..., original_dones)`，所以 A2_Base frozen policy injection 的正确最小修复是在 `_a2_base_actions()` 中只 unsplit padded `a2_base_obs`。
- 2026-06-22 22:07 HKT validation fact: main-agent 复跑 1-iteration smoke 已推进到 `Learning iteration 1`，actor/critic obs dim 分别为 130/135，stage3+ reward scales 保持 0.0；原 `flat_obs` / `high_level_actions` shape mismatch 未复现。训练主体完成后 IsaacSim shutdown 未自然退出，已手动 Ctrl-C 清理会话。
- 2026-06-22 22:15 HKT runtime diagnosis: tmux 中若卡在 `gpu.foundation.plugin No device could be created`、`Failed to open display`、`GLFW initialization failed`、`GPU Foundation is not initialized`，这是 IsaacSim/Kit 在 Vulkan/display/GPU foundation 初始化阶段失败，早于 env/trainer；优先比较 tmux 内外 `DISPLAY`、`XAUTHORITY`、`DBUS_SESSION_BUS_ADDRESS` 与 `vulkaninfo --summary`，不要当作 stage0-2 trainer blocker。
- 2026-06-22 22:15 HKT refined runtime diagnosis: 当前 host 普通 terminal 也没有 `DISPLAY/XAUTHORITY`，且没有安装 `vulkaninfo` 诊断工具；但系统存在 NVIDIA Vulkan ICD `/usr/share/vulkan/icd.d/nvidia_icd.json` 与 `/dev/nvidia*`。这更像 headless server runtime，需要使用 `headless=True` 并可显式设置 `VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json`，不要强行设置假的 `DISPLAY=:0`。
- 2026-06-22 22:40 HKT diagnosis: 用户长训 log 已完成 `simulation start`，真正失败点是 `OrderedTargetFrameTransformer._initialize_impl()` 的 fail-fast `FrameTransformer target frame name 'handle' is duplicated`。main-agent smoke 未遇到是因为 smoke 覆盖了 `num_envs=1`，而 quick config 默认 `num_envs=4096`；当前 duplicate check 用 `frame_name` 作为全局 key，会把多 env 中同名 `handle` offset 误判为重复。
- 2026-06-22 22:52 HKT source fact: `OrderedTargetFrameTransformer._initialize_impl()` 的 duplicate check 已改为只遍历 config-level `FrameTransformerCfg.target_frames` names，因此不同 env regex 展开的同名 `handle` / `pregrasp` 不再触发 duplicate；true config duplicate 仍在 sensor initialization 前 fail-fast。
- 2026-06-22 22:52 HKT source fact: `body_names_to_frames` 现在用 list append 记录同 body target frames，保留 cfg target order `handle -> pregrasp`；`_get_a2_gripper_handle_frame_transformer()` 仍校验 `target_frame_names == ['handle', 'pregrasp']`，order regression 会继续 fail-fast。
- 2026-06-22 23:53 HKT diagnosis: 当前 training entrypoint 通过 IsaacLab `AppLauncher` 支持 WebRTC livestream env path（`LIVESTREAM` + `PUBLIC_IP`），但不建议直接加到 `accelerate --multi_gpu --num_processes 4` 长训上；每个 rank 都会启动 IsaacSim/Kit app，默认 WebRTC port/client 会冲突且额外渲染会污染训练吞吐。可视化 quick diagnosis 应用单进程、小 `num_envs`、独立 GPU 复现实验，或等 checkpoint 后单独跑 visual/eval。
- 2026-06-22 23:59 HKT diagnosis: 当前 `LIVESTREAM=1` single-process visual run 的 env 已传入，但 `ss` 未见 `49100` listening，`omni.kit.livestream.log` 未出现 2026-06-22 的 `start` event；`omni.kit.extension.log` 只显示 `omni.kit.livestream.webrtc` / `omni.services.livestream.nvcf` extension startup。`zenity Failed to open display` 本身不是 training blocker，但说明默认 full `isaaclab.python.kit`/native GUI dialog path 仍在 headless host 上被触发。后续 visual run 应清理旧 IsaacSim processes，并显式传 `--experience /home/baoquanc/workspace/IsaacLab/apps/isaaclab.python.headless.rendering.kit`。
- 2026-06-23 00:07 HKT diagnosis/fix: training entrypoint 在 `LIVESTREAM>=1` 或 `headless=False` 时会进入 IsaacLab `AppLauncher._hide_stop_button()` optional toolbar UI path；当前 Kit runtime 缺少 `omni.kit.widget.toolbar`，导致 visual training 在 app launch 阶段 `ModuleNotFoundError`。`train_agent_trl.py` 已加入与 preview entrypoint 相同的 exact toolbar guard，只跳过缺失 toolbar 的 `_hide_stop_button/_hide_play_button`，其他 `ModuleNotFoundError` 继续 fail-fast。
- 2026-06-23 00:13 HKT diagnosis: toolbar guard 后 visual run 已进入 sim startup，并加载 `omni.kit.livestream.webrtc` / `omni.services.livestream.nvcf` extension；但 `ss` 仍无 `49100` listening，livestream log 仍无 2026-06-23 `start` event。当前机器同时残留两个 GPU3 visual runs、两个 GPU4 `headless=False` visual runs 和一个 4-rank long training，GPU4 还被旧 visual 与 rank0 同时占用；`zenity Failed to open display` 与 PhysX GPU pipeline fallback 在此状态下不能单独解释，需要先清理 stale visual processes 后再复测单一 WebRTC run。
- 2026-06-23 00:19 HKT decision: 如果目标是完整 Isaac Sim GUI，而不是 headless livestream smoke，当前 WebRTC route 已低效；建议转向 `xpra`/remote desktop 方案，但前提是提供真实可用的 X display。GUI run 应取消 `LIVESTREAM`，使用 `headless=False`、小 `num_envs`、独立 GPU，并通过 `DISPLAY` 连接 xpra session；`xpra` 不能替代 GPU/Vulkan driver，只负责提供/转发 desktop。
- 2026-06-23 13:41 HKT diagnosis: `xpra start :100 --bind-tcp=0.0.0.0:14500 --html=on` 已成功启动，`xpra list` 显示 live session 且 `ss` 显示 `14500` listening；但该 session 后端是 `Xvfb-for-Xpra-:100`，`DISPLAY=:100 glxinfo -B` 显示 `OpenGL renderer string: llvmpipe` / `Accelerated: no`。因此当前 `:100` 只能用于验证 xpra/web client，不是 Isaac Sim full GUI/Vulkan 的合格 GPU-backed display。

## Implementation Boundary

- 优先新增独立 experiment/env config，例如 stage0-2 quick test config，而不是直接改默认 full 6-stage config。
- 3-stage config 必须同步修改 `max_stage_time`、`stage_reward_scale`、`staged_reset_ratios` 等长度相关字段，保持 fail-fast shape/assert 行为。
- `reset_on_complete_delay` 可设为 `0` 或短 delay；若需要观察 grasp 后稳定性，再保留小 delay。
- Stage3+ reward terms 可以在 quick test config 中关闭或不进入，但不要把 open/swing/through reward 从 shared reward implementation 中删除。
- 训练产物、checkpoint 与日志需要用独立 experiment name/project name，避免和 full door-open 6-stage result 混用。

## TODO Summary

- 2026-06-22 20:29 HKT - 训练前确认不 resume 6-stage checkpoint；如需要 checkpoint transfer，必须单独设计 actor/critic shape migration，不作为 quick test 默认路径。
- 2026-06-22 20:29 HKT - 首轮 bounded smoke 重点记录 stage occupancy、stage2 completion route、contact spike false positive、overtime reset、termination frequency 与 `average_goal_reached`。

## DONE Summary

- 2026-06-22 20:29 HKT - 创建独立 memory entry `stage0-2-grasp-terminal`，记录 quickTEST 分支的 stage0-2-only training 目标、stage2 terminal success 语义、与 full 6-stage task 的边界。
- 2026-06-22 20:42 HKT - 新增独立 stage0-2 quick test config，并完成 Hydra static validation：3-stage list values、reset delay 0、stage3+ reward scales 0.0、`obs_dims.stage: 3` 均符合计划。
- 2026-06-22 21:23 HKT - 完成 frozen A2_Base TorchScript non-registered trainer fix review：wrapper 不再把 TorchScript model 注册进 module tree，optimizer scan old blocker 消失，bounded smoke 已推进到 training/reset observation 阶段。
- 2026-06-22 21:31 HKT - 完成 `piper_gripper_handle_frame_transformer` target order 修复：`py_compile` 通过，single-GPU smoke 未再触发 `['pregrasp', 'handle']` mismatch，并推进到 `_homie_history_length` reset observation blocker。
- 2026-06-22 21:35 HKT - 完成 `_homie_history_length` reset observation 修复：`py_compile` 通过，single-GPU smoke 已越过 `_get_obs_a_history_homie()`，并推进到 `ResetFromDataset.reset_count` blocker。
- 2026-06-22 21:39 HKT - 完成 G1 `ResetFromDataset` disable fix：quick config 显式 `reset_from_dataset.enabled: False`，smoke 不再加载 LAFAN motion files，并推进到 PPO forward shape blocker。
- 2026-06-22 22:07 HKT - 完成 PPO recurrent A2_Base injection shape mismatch 修复 review：确认 `a2_base_obs` unsplit 后与 `high_level_actions` 对齐，PPO loss tensors 未切换到 padded layout，fail-fast shape validation 无隐藏 fallback；worker 和 main-agent small smoke 均已到 `Learning iteration 1`。
- 2026-06-22 22:52 HKT - 完成 `OrderedTargetFrameTransformer` multi-env duplicate 修复 review：duplicate check 限定为 config-level target frame names，multi-env 同名 target 不再误判；cfg target order 仍为 `handle -> pregrasp`，true config duplicate 继续 fail-fast。
- 2026-06-22 23:53 HKT - 完成 WebRTC training visualization route diagnosis：结合 static visual alignment memory，确认 full GUI/static preview 是 preview-only workflow；stage0-2 training 可走 IsaacLab `AppLauncher` livestream env path，但应使用 single-process visual run，不直接叠加到 multi-rank PPO 长训。
- 2026-06-22 23:59 HKT - 完成 WebRTC no-ready diagnosis：当前问题不是 `PUBLIC_IP` env 缺失，而是 stream service 未 start；用 `ss`/livestream log 作为 readiness 判据，并建议显式使用 headless rendering kit 规避 full GUI/zenity path。
- 2026-06-23 00:07 HKT - 完成 visual training toolbar blocker 修复：`train_agent_trl.py` 在 AppLauncher 创建前安装 exact `omni.kit.widget.toolbar` guard，允许 full GUI/WebRTC path 越过缺失 optional toolbar widget；验证通过 `py_compile` 与 `git diff --check`。
- 2026-06-23 00:13 HKT - 完成 post-toolbar WebRTC diagnosis：当前不是 toolbar import crash；环境里 stale visual/training processes 叠加导致 GPU/Kit/livestream 状态不可判定，下一步应先终止旧 visual PIDs，再单独复跑一个 `LIVESTREAM=1` visual run 并检查 `49100`/livestream start event。
- 2026-06-23 00:19 HKT - 记录 GUI route decision：完整 GUI 调试优先走 `xpra`/remote desktop 提供 `DISPLAY`，训练命令改为 `headless=False` 且不设置 `LIVESTREAM`；WebRTC route 暂作为非首选。
- 2026-06-23 13:41 HKT - 完成 xpra startup diagnosis：HTML endpoint `http://10.120.16.39:14500/` 可由 xpra web server 提供，但当前 display `:100` 为 Xvfb/llvmpipe software renderer，不能作为 Isaac Sim full GUI/Vulkan 调试目标；需要 GPU-backed Xorg/VirtualGL/TurboVNC/NoMachine 或继续用 headless eval render mp4。
