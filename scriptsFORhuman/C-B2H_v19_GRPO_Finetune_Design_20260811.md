# C-B2H v19 GRPO Finetune — 方案设计（DoorMan Phase-3 适配 DoorDog）

日期：2026-08-11
设计：main agent（Claude），独立完成
执行：worker session（按本文档执行，§9 预案范围内自主决策）
GPU：2、3
方法依据：`scriptsFORhuman/research_inputs/doorman_grpo_detailed_en.md`（DoorMan arXiv:2512.01061 Phase-3 技术笔记）+ 本仓库源码实勘
状态：待执行

---

## 1. 目标与依据

当前 Student（`model_step_008000.pt`）512 集大规模 eval：**89.65% [86.7, 92.0]**；真 Teacher **99.61%**。残余 ~10 pp gap 的主体（35/53）是 Stage2 接触连续性（`both_contact` streak 2 vs 要求 5），失败跨 seed 不重叠、同 seed replay 漂移——典型的**部分可观测下接触鲁棒性问题**：特权 Teacher 靠精确接触力/位姿维持接触，视觉 Student 看不到这些量，模仿（DAgger）学不到它需要的闭环补偿策略。这正是 DoorMan Phase-3 GRPO 的适用区间：**让 Student 在自己的观测分布下 rollout，用轨迹级成败信号把成功的闭环策略概率提上去**。

DoorMan 报告 DAgger student 50–70% → GRPO 后 80.8–85.8%（逼近 teacher 上限）。我们起点 89.65%、目标 ≥93%（理想 95%+），需要的改进量远小于 DoorMan，算力预算也相应小（DoorMan 用 64×L40S×12h；我们 2 GPU、目标 24h 内）。

## 2. 算法核心（DoorMan-faithful 部分，不改动）

按 paper Eq.4–5 原样实现：

- 从当前策略采一组 G 条完整轨迹，每条得标量回报 `R_i`；
- 组内归一化轨迹优势：`Â_i = (R_i − mean(R)) / (std(R) + 1e-8)`，**轨迹级**，广播到该轨迹所有 timestep；
- clipped surrogate：`L = −E[min(r_t·Â_i, clip(r_t, 1±ε)·Â_i)]`，`r_t = exp(new_logp − old_logp)`；
- **无 critic、无 GAE、无 value loss、无 reference-policy KL 项**（DoorMan Eq.5 没有）；靠 PPO clip + 小学习率留在 DAgger 初始化附近；
- 回报以**二值任务成功为主** + 少量简单正则（见 §4.4）。

## 3. 本仓库现状实勘（适配的出发点）

| 组件 | 现状 | 对 GRPO 的意义 |
|---|---|---|
| Student actor（`vision_actor_critic_modules_p2_recurrent.py`，`DualD435HeadVisionRecurrentToeOut6Actor`） | 可学习 `std` 参数、`get_actions_log_prob`、`update_distribution`、`rollout`/`act_inference`、LSTM(hidden 256) + hidden state 管理 | **PPO 接口现成**，不需要加分布头 |
| 同上 `_DualD435Core.forward_from_latent(actor_obs, latent, masks, hidden_states)`（:962） | 视觉 latent 与递归/头解耦的现成接口 | **冻结编码器时可缓存 latent 回放**，绕开整回合图像存储 |
| `TRLPPOTrainer`（`ppo_trainer_a2_base_api.py`，3952 行） | RolloutStorage（含 hidden states、episode_attnmask）、`_compute_ppo_loss`（clip + 自适应 KL 调 LR + entropy）、`_compute_returns`（GAE）、accelerate DDP、`sync_advantage_normalization` | GRPO trainer 以它为基类做**减法** |
| 蒸馏 formal config | `num_steps_per_env=8`、`init_noise_std=0.001`、`clip_param=0.2`、`desired_kl=0.005`、`schedule=adaptive`、actor lr 1e-4、4×64 envs | 两处必须改：噪声与 rollout 视界（§4.1、§4.2） |
| success 信号 | `legged_robot_base.py` `_terminal_reason_bufs["complete"]` / `last_completed_task_buf`（reset 时按 env 结算） | 轨迹二值回报来源 |
| 动作链 | Student 出 12D 高层动作（log_prob 只算这 12D，现有 loss 已做切片），a2_base/HOMIE 下层冻结拼接为 24D | GRPO 只优化 12D 高层，**下层完全不动** |

## 4. 适配设计（本方案的核心决策）

### 4.1 探索噪声重注入（适配点 #1，成败关键）

蒸馏后 `std=0.001`——组内所有 rollout 几乎相同，回报零方差，GRPO 无信号。方案：

- GRPO 启动时将 `std` 覆写为 **0.05**（12D 高层动作 raw norm ~4–5，即约 4% 扰动），`freeze_noise_std=true`（v0 冻结不学，去掉 std 塌缩/爆炸这整类风险；entropy_coef=0）。
- smoke 阶段用随机采样 rollout 实测成功率：要求相对确定性 eval 掉幅 ≤ ~15 pp（即 ≥ ~75%）。若掉幅过大 → 降到 0.02；若组内回报方差过小（成功率与确定性几乎无差、失败样本过少）→ 升到 0.08。此为 worker 预案内决策。

### 4.2 Rollout 组织：整回合、reset-all（适配点 #2）

- 每次迭代开始 **reset 全部 env、清 LSTM hidden**，跑到所有 env 终止（成功/失败/超时），上限 850 步（`max_stage_time` 总和）；每 env 恰好贡献 1 条完整轨迹。
- 组构造：**全局组** = 2 GPU × 64 env = **G=128**（`accelerator.gather` 回报后算全局 mean/std，复用 `sync_advantage_normalization` 模式）。不做难度匹配分组（paper 未要求；p≈0.9 时全局组每组约 10–15 条失败轨迹，信号充足）。
- 边界情形：组内回报 std < 1e-6（如全成功）→ 跳过本次更新，只记录。p=0.9、G=128 时全成功概率 ≈ 10⁻⁶，基本不会发生。
- 若渲染显存/速度不支持 64 env/GPU，降到 48 或 32（G=96/64 仍可用），worker 按 smoke 实测定。

### 4.3 视觉编码器冻结 + latent 缓存（适配点 #3，工程上最大的一步棋）

**v0 冻结视觉编码器**（ResNet/D435 encoder 不更新），rollout 时把 `encode_dual` 的 latent 逐步缓存进 storage，更新阶段用 `forward_from_latent` 回放（梯度只过 LSTM + MLP 头）。收益：

- 不存图像：latent(≈256d) + actor_obs + hidden，整回合 850 步 × 64 env 也只有百 MB 量级，storage 直接放 GPU；
- 更新阶段无编码器前向，单次迭代墙钟 ≈ rollout 时间（估 2–6 min），24h 可跑 200+ 迭代；
- 蒸馏学出的视觉表征零漂移风险。

代价：放弃"感知表征随 GRPO 适应"。判断：我们的 gap 是接触时机/保持行为（LSTM+头的职责），且 DoorMan 的 active-perception 收益主要通过**身体运动**实现（行为层面，冻结表征不阻碍）。若 v0 提升不足再走 v1（解冻编码器 + uint8 CPU 图像存储回放，编码器 LR 0.1×）——v1 不在本轮范围内。

注意 fail-fast：latent 缓存路径必须与 rollout 前向严格同源（同一次 `encode_dual` 输出直接入 storage，不二次计算）；`normalize_actor_obs` 在 `forward_from_latent` 内部对 proprio 部分照常生效，回放传入原始 `actor_obs` 即可。

### 4.4 轨迹回报

```
R_i = 1.0 × success_i  −  λ_ar × mean_t ||a_t − a_{t−1}||²
```

- `success_i`：该 env 本回合 `_terminal_reason_bufs["complete"]`（在 done 结算时捕获，auto-reset 前）。
- action-rate 正则从 storage 里已存的 12D 高层动作直接计算（不动 env 奖励代码）；`λ_ar` 取值使该项在组内的散布 ≈ 0.03–0.05（约为二值项的 1/20–1/30），worker 用 smoke 数据标定一次后固定。作用：给同为成功/同为失败的轨迹提供平滑度排序，并抑制噪声注入带来的抖动漂移。
- **不加** joint vel/acc 正则（v0 从简，行为已由 BC 初始化平滑；若中期 eval 发现动作变糙再补——预案内）、**不加** stage shaping、**不加**部分完成分（保持 mostly-binary；p 高时失败轨迹天然获得强负优势 `−√(p/(1−p)) ≈ −3`，这正是我们要的"强抑制残余失败"机制）。

### 4.5 GRPOTrainer 实现路径（对 `TRLPPOTrainer` 的最小改动集）

新文件 `gr00t/rl/trl/trainer/grpo_trainer_a2_base_api.py`，子类化 `TRLPPOTrainer`：

**删**：value model 构建与前向（`PolicyAndValueWrapper` 只留 actor + a2_base）、`_compute_returns`（GAE）、vf_loss/vf_clipfrac（`vf_coef=0` 并直接不算）、DAgger BC loss、imgaug BC loss、teacher 全部管线。

**改**：
- `_setup_storage`：视界 850；去 `values/returns`；`advantages` 改为迭代末一次性填充（轨迹优势广播）；新增 `latent` key；保留 `actions/actions_log_prob/action_mean/action_sigma/dones/hidden_states`（现成）。
- rollout 循环：reset-all 起步；逐步存 latent；per-env 记录终止步与 success；全部终止或 850 步止。
- 优势计算：per-env 轨迹回报 → `accelerator.gather` → 全局 mean/std → `Â_i` 广播到该轨迹 `[0, T_i)`，越界步（已终止后的填充步）padding mask 剔除（复用现有 padding 机制）。
- `_compute_loss`：只留 pg_loss（clip 0.2）+ 现有自适应 KL 调 LR（`desired_kl=0.005` 保留，这是比 DoorMan 更稳的保留项，作用等价于软 trust region）；entropy_loss 系数 0。
- 回放：整回合按 chunk（长度 128，minibatch 沿用 `num_mini_batches=4`）从存储的 hidden state 起步回放，`num_learning_epochs=1`（单 epoch，off-policy 漂移最小，recurrent hidden 失配问题也随之消失）。

**不动**：a2_base/HOMIE 冻结下层、12D log_prob 切片逻辑、env/契约/随机化（与蒸馏 formal config 完全同源，继承 G2 band）、`max_grad_norm=1.0`。

### 4.6 优化器超参（工程选择，非 paper 值）

| 项 | 值 | 说明 |
|---|---|---|
| actor lr | 3e-5 起，adaptive KL（desired_kl 0.005） | 蒸馏 1e-4 的 1/3；finetune 定位 |
| clip ε | 0.2 | 沿用仓库 PPO 值（paper 未报） |
| epochs / minibatch | 1 / 4 | 单 epoch，见 §4.5 |
| std | 0.05 冻结（预案 0.02–0.08） | §4.1 |
| entropy / vf coef | 0 / 0 | DoorMan Eq.5 |
| 编码器 | 冻结 | §4.3 |
| grad clip | 1.0 | 沿用 |

## 5. 训练运行方案（GPU2、3）

- 启动脚本 `gr00t/rl/scripts/run_a2_grpo_finetune_v19.py`：参照现有 mgpu 蒸馏启动器（accelerate DDP 2 进程），绑定 GPU2/3，加载 `model_step_008000.pt`（actor 全量：编码器+LSTM+头+std 覆写）。
- 输出：`logs_rl/by_batch/cb2h_v19_toeout6_pitch50_grpo_20260811/<run_name>/`（config 快照、checkpoint、metrics jsonl）。
- **迭代预算 200**（约 8–20 h，按实测单迭代墙钟修正）；checkpoint 每 10 迭代。
- **Eval gate 每 10 迭代**：16 env × seed0 确定性（`act_inference`）快评，记录成功率与 stage 分布。跟踪 best checkpoint（按 gate 成功率）。
- **早停**：连续 3 次 gate 相对启动基线（13/16）下降 ≥3 case → 停，回滚 best；gate 连续 4 次 ≥15/16 且无提升趋势 → 提前收敛停。
- 阶段划分：smoke（2 env×1 迭代，验证整链路 + ratio 首次更新 ≈1 + 优势广播正确 + success 提取正确）→ pilot（10 迭代，标定 λ_ar、std、单迭代墙钟）→ 主跑（其余预算）。

## 6. 验收

1. 快速回归：best checkpoint 3 seed × 16 env（对比 13/16、16/16、13/16 基线）。
2. **最终判定：复用大规模 eval 管线原样重跑 512 集**（与 89.65% 基线同 seed 集、同契约），判据：
   - 成功 ≥93%（好结果 ≥95%）且 Stage2 失败占比明显下降、其他 stage 失败不增 → GRPO 收官，产出报告；
   - 88–93% 边缘 → 报告中给出组回报方差、KL、clip fraction 诊断与 v1（解冻编码器）建议，不自行启动 v1；
   - <88%（回吐）→ 回滚，报告失败分析。
3. 监控指标（训练全程 jsonl）：组均值/方差、每组成功数、Â 分布、approx_kl、clip_fraction、ratio max、action-rate cost、gate 成功率、零方差组次数。

## 7. 明确不做（本轮范围外）

reference-policy KL 项（Eq.5 无）；stage-conditioned shaping；critic/GAE（即"PPO finetune 对照"这一消融）；解冻编码器（v1）；难度匹配分组；腕部/深度相机任何改动；对 env、契约、随机化的任何修改。

## 8. 风险与预案（worker 自主处置）

| 风险 | 信号 | 预案 |
|---|---|---|
| 噪声注入砸成功率 | smoke 随机 rollout <75% | std 0.05→0.02；仍不行 0.01 并升 G |
| 组方差不足 | 失败轨迹 <5/组 或 std≈0 频发 | std 上调 0.08 或加大随机化采样确认非侥幸 |
| 更新不稳 | approx_kl 持续 > 2×desired_kl、ratio max 爆 | adaptive 调 LR 已自动处理；仍不稳 lr 减半重启自 best |
| 成功率停滞不升 | 50 迭代 gate 无改善 | 检查 clip_fraction（<2% 说明步子太小 → lr×2）；仍停滞则如实报告，不硬调 |
| 渲染 OOM/慢 | smoke 实测 | env 数 64→48→32，G 相应缩 |
| 行为变糙 | gate 视频/action-rate cost 上行 | 补 joint vel/acc 正则（小权重）|
| latent 回放数值不一致 | smoke 首更 ratio 偏离 1 超过 1e-3 量级 | fail-fast 查同源性（禁止用容忍阈值糊过去）|

## 9. Coding 风格约束

fail-fast，禁止为"健壮性"加 fallback 让训练带病运行；先证明操作路径、先跑通功能，护栏与测试只在问题实际出现后补；严控 review/diff/边界检查次数；禁止哈希/SHA256 校验代码；等待一律长 sleep，不轮询；工具调用批量并行。
