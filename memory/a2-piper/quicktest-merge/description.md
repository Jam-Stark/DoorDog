---
name: quicktest-merge
scope: 记录 2026-06-25 从 quickTEST branch 合并回 A2_Piper 主线的内容清单、分类与 6-stage 影响边界
status: active
last_updated: 2026-06-25 20:30 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/quicktest-merge/description.md
  - memory/a2-piper/quicktest-merge/TODO.md
  - memory/a2-piper/quicktest-merge/DONE.md
read_when:
  - 需要确认 A2_Piper 主线当前包含哪些从 quickTEST 合并回来的 bugfix / reward / eval 改动
  - 需要确认 stage0-2 专属 config / memory 是否已从主线移除
  - 开始 6-stage 训练前需要确认 staged_task_base last-stage complete gate、stage2 contact history gate 等 B 类改动对主线的影响
---

# quickTEST Merge

## Purpose

记录 2026-06-25 将 `quickTEST` branch 的内容合并回 `A2_Piper` 主线的完整清单。`quickTEST` 最初是为 stage0-2 临时训练创建的分支，但在过程中修复了不少 A2_Piper 训练 bug 并优化了 stage0-2 环节。本次合并将通用 bugfix（A 类）和通用增强（B 类）带回主线，同时排除 stage0-2 专属的 config 和 memory（C 类），保持 6-stage 训练框架不被破坏。

## Merge Method

- 方式：fast-forward merge + cleanup commit。
- `A2_Piper` 在 quickTEST 分出后无新 commit，因此 `git merge quickTEST` 为 fast-forward，A2_Piper HEAD 推进到 `34e06b7`。
- 随后删除 C 类文件并新建 cleanup commit，记录合并边界。

## A 类：通用 bugfix（A2_Piper 主线本来就需要的修复）

| 文件 | 改动 | 对 6-stage 的影响 |
|---|---|---|
| `gr00t/rl/envs/base_task/a2_base.py` | 显式初始化 `_homie_history_length` + fail-fast 校验 | 修复 A2_Base init path crash（A2 early-return 绕过 cooperative MRO） |
| `gr00t/rl/envs/door/reset_from_dataset.py` | 拆分 `_init_reset_from_dataset()`，修复 `reset_count` missing init | 修复 A2 early-return 绕过 `ResetFromDataset.__init__()` |
| `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py` | `object.__setattr__` 持有 frozen A2_Base TorchScript，避免 optimizer parameter scan crash | 修复 HuggingFace Trainer optimizer `ParameterDict.contains()` crash |
| `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py` | recurrent `_a2_base_actions()` 增加 `unsplit_trajectories` | 修复 recurrent model padded obs / env-major action shape mismatch |
| `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py` | `_make_json_safe` + temp file + `os.replace()` 原子写入 | 修复 eval `metrics_eval.json` tensor/numpy 不可序列化 |
| `gr00t/rl/train_agent_trl.py` | `patch_app_launcher_toolbar_hiding` | 修复 headless Kit 缺 `omni.kit.widget.toolbar` 时 AppLauncher crash |
| `gr00t/rl/envs/door/door_open_a2_base.py` | 新增 `OrderedTargetFrameTransformer` | 修复 IsaacLab `FrameTransformer` 用 `set` 导致 target frame order 不可靠 + multi-env duplicate 误判 |
| `gr00t/rl/envs/base_task/staged_task_base.py` | `is_complete = is_last_stage & is_stage_complete` | **关键 bugfix**：原代码任何 stage complete 都会触发 episode terminal，6-stage 下 stage2 complete 就会提前结束 episode |
| `gr00t/rl/envs/legged_base_task/legged_robot_base.py` | terminal reason tracking + eval metrics 重写 + `render_results` per-env writer lifecycle | eval 基础设施，支持 terminal reason diagnostics 与 true-episode mp4 |
| `gr00t/rl/simulator/isaacsim/isaacsim.py` | `eval_camera_resolutions` 不再硬编码 256x256 | 通用 eval camera resolution 配置化 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | A2 `_reset_root_states` / `_reset_dofs` randomization + termination `_mark_terminal_reason` | domain randomization + eval diagnostics |

## B 类：通用增强（对 6-stage stage2 也有益的 reward / predicate 改进）

| 文件 | 改动 | 对 6-stage 的影响 |
|---|---|---|
| `gr00t/rl/config/env/door_open_a2_base.yaml` | `stage2_grasp_contact_history_length: 5` | stage2→stage3 advance 从瞬时 contact 改为 5 步连续 contact history gate，防止 open-gripper collision spike 误触发 advance |
| `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` | `penalty_base_roll_pitch_l2: -2.0` | stage0/1 防止 base roll/pitch 倾斜 |
| `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` | `a2_stage2_close_command: 1.0` / `a2_stage2_close_progress: 0.5` | stage2 close shaping rewards，引导 gripper 在 gate 内从张开到闭合 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_reward_pregrasp_gripper_dof_pos_l1` stage-aware target | stage0 track close target（行走时收起），stage1 track open target（准备抓取） |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_stage_2_to_complete_condition()` contact history gate + `actual_time_in_stage_buf` gate | 同 config 行，stage2 completion 要求最近 H 个 contact history samples 都来自 stage2 |
| `gr00t/rl/envs/door/door_open_a2_base.py` | `_get_a2_terminal_diagnostics` + `init_a2_eval_stage2_step_trace` + `_capture_a2_eval_stage2_step_trace` | eval diagnostics 基础设施，记录 terminal frame 的 gripper/contact/orientation/distance 状态 |
| `gr00t/rl/config/env/base_task.yaml` | `eval_rendering` config block | 通用 eval rendering 配置（camera_mode / eye / lookat / fps / frame flags） |

## C 类：stage0-2 专属（已从主线排除）

| 文件 | 说明 |
|---|---|
| `gr00t/rl/config/exp/wbmanip/door_open_a2_base_stage0_2_grasp_terminal_lstm.yaml` | stage0-2 专属 3-stage config（`max_stage_time` 3 项、stage3+ reward scales=0.0、`reset_from_dataset.enabled=False`） |
| `memory/a2-piper/stage0-2-grasp-terminal/description.md` | stage0-2 专属 memory entry |
| `memory/a2-piper/stage0-2-grasp-terminal/TODO.md` | 同上 |
| `memory/a2-piper/stage0-2-grasp-terminal/DONE.md` | 同上 |

## 保留的通用 memory 改动

以下 memory 改动虽在 quickTEST 中产生，但属于通用可视化 workflow 事实，与 stage0-2 无关，已保留在主线：

- `memory/a2-piper/static-visual-alignment/`：WebRTC training visualization 边界、stale visual process 清理记录、xpra display validation（Xvfb/llvmpipe software renderer 不适合 Isaac Sim full GUI/Vulkan）。

## 6-stage 影响说明

- 默认 full task config `door_open_a2_base_lstm.yaml` 未被 quickTEST 修改，6-stage 语义保持。
- `staged_task_base.py` 的 `is_complete = is_last_stage & is_stage_complete` 是 bugfix：原代码在 6-stage 下 stage2 complete 就会终止 episode，这是错误的；修复后只有 last stage（stage5）complete 才触发 episode terminal，中间 stage complete 只触发 stage advance。
- B 类改动（contact history gate、stage2 close rewards）会改变 6-stage 的 stage2→stage3 advance 条件，但这是为了修复 false-success（open gripper 撞出 contact spike 误触发 advance）。用户已审查并确认接受这些改动进入 6-stage 主线。

## Source Facts

- `merge-base A2_Piper quickTEST` = `c58b82b` = 合并前 A2_Piper HEAD，即 A2_Piper 自 quickTEST 分出后无新 commit。
- quickTEST 领先 A2_Piper 4 个 commit：`60696ff` → `3138ddf` → `ac423ca` → `34e06b7`。
- 合并后 A2_Piper HEAD = `34e06b7`，随后新增 cleanup commit 删除 C 类文件并更新 memory。
