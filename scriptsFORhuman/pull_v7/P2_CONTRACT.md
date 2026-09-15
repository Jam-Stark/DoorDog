# Pull v7 P2 冻结执行合同

2026-09-09 HKT。仓库 `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`，分支
`codex/a2-piper-pull-v0-20260803`，核对 HEAD `025ce28`。方案依据
[a2_piper_pull_v7_stage_plan_20260909.md](../pull_task/a2_piper_pull_v7_stage_plan_20260909.md)
§4；本文件只冻结执行口径，不改动方案的判据。

Owner 已批准处理变量 D2（scale −1.0）与四格预算，并把实施与启动委托给本 stage
lead；integration、Git、memory 文件与 stop 权限仍属 Main planner。

## 1. 处理变量 D2 的唯一实现点

`DoorOpenA2Pull._reward_a2_pull_v7_arm_target_overshoot_penalty`
（`gr00t/rl/envs/door/door_open_a2_pull.py`），一个新方法，无 stage 装饰器，全阶段生效：

```text
q_target_j  = default_dof_pos_j + action_scale · d_j     (d = self._delta_actions)
overshoot_j = max(0, q_target_j − u_j) + max(0, l_j − q_target_j)
raw         = Σ_j overshoot_j                            (arm_j1..arm_j6, rad)
```

实际执行路径（每条都已 INSPECTED）：

| 事实 | 位置 |
|---|---|
| `reward_scales` 的 key 通过 `getattr(self, "_reward_" + name)` 派发；零 scale 先被移除，非零 scale 乘 `dt` | `gr00t/rl/envs/legged_base_task/legged_robot_base.py:525-531,618-623` |
| 臂 PD 目标 `jpos_target = actions_after_delay · action_scale + default_dof_pos`；`randomize_ctrl_delay=false`，所以 `actions_after_delay == actions` | `legged_robot_base.py:1183-1184`、`:667-674` |
| 累积臂状态写回 action 列 5..10（clamp ±15 之后、Stage0 归零之后） | `gr00t/rl/envs/base_task/delta_action_base.py:63-67,90` |
| Stage0 把 `_delta_actions` 归零，因此 Stage0 的 raw 天然为 0 | `gr00t/rl/envs/door/door_open_a2_base.py:7239` |
| action 列 5..10 即 `arm_start=5, arm_end=11`，经 `_a2_arm_dof_indices` 落到 `arm_j1..arm_j6` | `gr00t/rl/envs/base_task/a2_base.py:44-46,440-443,561,572` |
| `_reward_limits_dof_pos` 用的臂 DOF 索引集合 `_upper_non_gripper_dof_idx` = `upper_dof_indices` 去掉 `arm_j7/arm_j8` = `[12,13,14,15,16,17]`，顺序与 `_a2_arm_dof_indices` 相同 | `door_open_a2_base.py:7046-7052,11982-11998`；`gr00t/rl/config/robot/A2_Piper/a2_piper.yaml:30-36,43` |
| `simulator.hard_dof_pos_limits` 是 robot config `dof_pos_lower/upper_limit_list` 的逐元素拷贝，与 `_reward_limits_dof_pos` 同源；因此只读这一个来源 | `gr00t/rl/simulator/isaacsim/isaacsim.py:2398-2399` |
| `action_scale = 0.25`，`delta_action_scale = 0.3`，`delta_action_clip = 15.0`；`arm_j3` 范围 `[−2.967, 0]` 默认 0，`arm_j5` 范围 `±1.22` 默认 0.5，`arm_j6` 范围 `±2.0944` 默认 1.57 | `a2_piper.yaml:62-75,135-142,170`；P_S1/P_S2 `resolved_config.yaml` |
| `only_positive_rewards = false`，所以负项不会被裁掉 | P_S1/P_S2 `resolved_config.yaml` |

方法对形状/索引不匹配直接 `raise`：`_a2_arm_dof_indices` 与
`_upper_non_gripper_dof_idx` 顺序不同、`delta_action_indices` 不是 `[5..10]`、
`_delta_actions` 或默认角形状不符、臂硬限位不是 `(6,2)`。除 `max(0,·)` 外没有
任何 clipping，没有 try/except，没有默认值。

C 格不含该 key，零/缺失 scale 在 `legged_robot_base.py:525-531` 被移除，因此 C 的
reward 路径与 9000 源 bit-identical，新方法对 C 是惰性代码。

## 2. 格、来源与命令

| cell | 来源 checkpoint | ablation 选择器 | seed | GPU | tmux | 状态 |
|---|---|---|---|---|---|---|
| T_S1 | `wave2/train/P_S1/model_step_009000.pt` | `wbmanip/pull_v7_p2_T_S1` | 1 | 1 | `pull_v7_p2_t_s1` | RUNNING |
| T_S2 | `wave2/train/P_S2/model_step_009000.pt` | `wbmanip/pull_v7_p2_T_S2` | 2 | 2 | `pull_v7_p2_t_s2` | RUNNING |
| C_S2 | `wave2/train/P_S2/model_step_009000.pt` | `wbmanip/pull_v26_8_backbone_P_S2` | 2 | 3 | `pull_v7_p2_c_s2` | RUNNING |
| C_S1 | `wave2/train/P_S1/model_step_009000.pt` | `wbmanip/pull_v26_8_backbone_P_S1` | 1 | 待定 | `pull_v7_p2_c_s1` | DECLARED，Main 在 GPU 空出后启动 |

`wave2` 前缀为
`logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2`。

统一命令（唯一入口）：

```bash
bash scriptsFORhuman/pull_v7/run_p2_cell.sh <GPU> <CELL> \
  /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_rl/a2_piper_pull_v7/p2_20260909/<CELL>
```

脚本依次执行：`--cfg job --resolve` 落盘 `resolved_config.yaml` →
`verify_p2_config.py` → `scriptsFORhuman/pull_v26_8/runner.py`（要求
`model_step_010500.pt`，并全程 200 ms 采样 GPU 显存）。所有格
`checkpoint_load_mode=full`、`auto_load_latest=false`、`num_envs=1024`、
`callbacks.model_save.save_frequency=250`、`algo.trl.num_total_batches=10500`、
`project_name=a2_piper_pull_v7`、`experiment_name=<CELL>`。
GPU0 由其他用户的 LightNav 服务占用（约 12.0 GB），脚本硬性只接受 GPU1/2/3。

输出根：`logs_rl/a2_piper_pull_v7/p2_20260909/<cell>/`；评估根
`logs_eval/a2_piper_pull_v7/p2_20260909/`；receipt
`.ai/runtime/runs/pull_v7_p2_<cell>_20260909/RUN_RECEIPT.json`。

### 2.1 一次启动到 10500 的决定

每格在**同一个进程**里跑到绝对上限 10500，不在 9500 处停止再重启。理由：full
加载不恢复 online staged-reset 库存与 LSTM rollout 历史，重启会让 9500→10500 段
的曝光与 9000→9500 段不可比。方案 §4.4 的 9500 准入门因此改由 **Main 在 9500
milestone eval 之后主动停止不合格的格**来执行，而不是靠重新启动。watcher 不停止、
不重启训练。

### 2.2 预算

每格授权 1500 新 batches（9001..10500），即 1024 env × 64 steps × 1500 =
98,304,000 transitions。checkpoint 期望 9250/9500/9750/10000/10250/10500。
里程碑 eval 在 9500/10000/10500。

## 3. 验证器

| 产物 | 作用 |
|---|---|
| `scriptsFORhuman/pull_v7/verify_p2_config.py` | 逐格核对 resolved config：T 的 `rewards.reward_scales` 等于 9000 源 resolved 值加且仅加 `a2_pull_v7_arm_target_overshoot_penalty = −1.0`（90 → 91 项），C 逐项相同（90 项）；checkpoint 指向对应 9000 文件；`full`；10500；1024；seed；actor/critic 133/138；`enable_staged_reset=true` 且 ratios `[0.5,0.1,0.1,0.1,0.1,0.1]`；两项 v6 bank false。复用 `scriptsFORhuman/pull_v26_8/verify.py` 的 `read_config`、`require`、actor/observation 合同与 ratio 常量。 |
| `scriptsFORhuman/pull_v7/verify_p2_overshoot.py` | 用 `P0_ENTRY_TRAJECTORY.csv` 里已提取的六关节实际 target 列离线重算 overshoot，与 reward 方法同一硬限位来源；输出逐关节与求和的 median/p90/max，以及与 `limits_dof_pos` raw 的比值，供 runtime smoke 数值对照。产物 `P2_OVERSHOOT_REFERENCE.json`。 |

## 4. Smoke 口径（已执行，不重复）

每种格各一次，256 env、5 个新 batch，输出在
`logs_rl/a2_piper_pull_v7/p2_20260909_smoke/{T_S1,C_S2}`。

**已发现的真实约束**：full 续训要求 `num_total_batches` 大于已加载的 global
step，`num_total_batches=5` 会被
`RuntimeError: Full checkpoint resume requires num_total_batches greater than the loaded global step; loaded=9000, requested=5`
拒绝。因此 smoke 的绝对上限是 **9005**（5 个新 batch），不是 5。第一次尝试的
日志保留在 `*_attempt1_batch_ceiling_rejected/`，不算一次有效 smoke。

## 5. 里程碑 eval 与 reducer

- `scriptsFORhuman/pull_v7/eval_p2_cell.sh GPU CELL STEP TRAIN_ROOT EVAL_ROOT`：
  exact64 natural、每侧 first episode、`enable_staged_reset=true` 且 ratios
  `[1.0,0,0,0,0,0]`、两项 v6 bank false、birth-trace 硬检查。evaluator override
  与 `scriptsFORhuman/pull_v26_8/continue_eval_cell.sh` 逐项相同，只改 cell 名、
  里程碑 step 和 GPU 绑定（pull-v26.8 固定 GPU0，现在 GPU0 不可用）；
  natural-protocol 与 plant 检查仍调用未修改的 `pull_v26_8/verify.py`。
- `scriptsFORhuman/pull_v7/analyze_p2.py`：P2 中介 reducer，复用 `analyze_p0.py`
  的 `stream`/`compact`/`THRESHOLDS`/window 记账，每条 trace 只流式读一次，输出
  `P2_MEDIATOR_step<step>.json` 与同名 `.md`。列包含 §4.4 的 0–5 项、K5/D/E4/E5
  保留能力、`handoff_reached` / tangent share ≥0.6 / `handle_crossed`，以及 trace
  内 `reward_raw`/`reward_scaled` 的 D2 项，用于把 reward 实现与离线重算闭环。
  reducer 只报告，不判定。
- `scriptsFORhuman/pull_v7/watch_p2.py`（tmux `pull_v7_p2_watch`）：对每个
  milestone 等到**所有**在跑的格都写出该 checkpoint 后再逐格 eval，再跑一次
  reducer，保证 T/C 同批比较。某格进程已退出且该 checkpoint 不存在时，发
  `ATTENTION_REQUIRED` 并停在该 milestone，交 Main 处理。watcher 只写
  `watch_state.json` 与新事件，从不停止或重启训练。

### 5.1 eval 放置规则

训练峰值 P_S1 系约 18.6 GB、P_S2 系约 16.5 GB；natural eval 峰值约 3.8 GB；
卡为 24 GB。因此：

1. 里程碑 eval 只放在指定的 eval GPU3（C_S2 旁边）；
2. 启动前 `nvidia-smi` 预检实际空闲 ≥ 5 GB（5120 MiB），否则排队等待，不降级；
3. 绝不把 eval 放在 P_S1 系格（T_S1、C_S1）旁边；
4. GPU0 永不使用。

## 6. 门限与停止（判定权在 Main）

- **9500 准入**：T 任一来源两侧 overshoot 明显下降，且 margin 中介相对同批 C 有
  可解释抬升（每 episode 最大 margin 中位 > 0.025，或有余量 B 步 > 0），且保留能力
  不低于 48/64。不满足的格由 Main 停止（本合同 §2.1）。
- **10500 成功**：至少一个来源在 natural 出现 ready 窗口 > 0（任一侧），且保留能力
  ≥ 60/64；更强读数为 clean release ≥ 1。
- **停止**：NaN／异常／来源配置不符／Owner 停止；任一侧保留能力 < 48/64 且 margin
  中介无改善；10500 为绝对上限，即使 ready 仍为 0 也不延长。
- 唯一允许的重试：overshoot 降、margin 动但保留能力 < 48/64 时，把 scale 改为
  −0.3 重跑 T 格一次；不扫更多值。
- **不据以下判死**：单个来源失败；ready 出现但 clean 为 0；C 自身波动 ≤ 4/64。

## 7. 边界

WRITE_SET：`gr00t/rl/envs/door/door_open_a2_pull.py`（仅新增一个方法）、
`gr00t/rl/config/ablation/wbmanip/pull_v7_p2_*.yaml`、
`scriptsFORhuman/pull_v7/` 下的新文件、`logs_rl/a2_piper_pull_v7/`、
`logs_eval/a2_piper_pull_v7/`、`.ai/runtime/`。不改 `memory/`、`MEMORY.md`、方案
文档、`.codex/`、`Codex-Cashier/`、robot 目录，以及任何 `pull_v26_8` 脚本与既有
P0/P1 文件。不 `git add/commit/push`。

Ledger：task `pull_v7_p2_20260909`（adaptive 模式），lease `gpu:1`、`gpu:2`、
`gpu:3`、`output:logs_rl/a2_piper_pull_v7/p2_20260909`、
`output:logs_eval/a2_piper_pull_v7/p2_20260909`，以及
`path:gr00t/rl/envs/door/door_open_a2_pull.py`、
`path:gr00t/rl/config/ablation/wbmanip/pull_v7_p2_T_S1.yaml`、
`path:gr00t/rl/config/ablation/wbmanip/pull_v7_p2_T_S2.yaml`、
`path:scriptsFORhuman/pull_v7`。

## NO_DELEGATION_REASON

方案要求用 `cursor-grok-4.6-high-fast` 子 agent 分三条 lane 并行。该 model slug
在本 runtime 的可用列表里不存在（可用的只有 `inherit` 与
`composer-2.5-fast`），按规则不擅自替换成别的模型，因此三条 lane 由 stage lead
顺序自行完成：reward 方法与离线验证器、配置与配置验证器与启动脚本、watcher 与
中介 reducer。所有 source 事实均在 §1 表格中给出 file:line。
