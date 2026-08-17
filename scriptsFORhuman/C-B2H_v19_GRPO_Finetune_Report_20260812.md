# C-B2H v19 GRPO Finetune Report（2026-08-12）

## 结论

本轮 best checkpoint 为 `pilot_2x32_lr375e8_syncreset/model_step_000010.pt`。最终同 seed 集、同 fixed-G2 契约、同 formal runner 的 512 集评估为：

- GRPO：`467/512 = 91.2109375%`。
- 启动基线：`459/512 = 89.6484375%`。
- 绝对提升：`+8 case / +1.5625 pp`。
- GRPO Wilson 95% 区间：`[88.4415%, 93.3666%]`。
- Stage2 失败：`35 → 23`，占全部失败的比例由 `66.04% → 51.11%`，下降 `14.93 pp`。
- 其他 stage 并未全部保持不增：Stage0 `15 → 20`，Stage1 `2 → 0`，Stage4 `1 → 2`。

因此，本轮命中设计文档 §6 的 **`88–93% 边缘`** 判据。它没有命中“成功率 ≥93%、Stage2 明显下降且其他 stage 失败不增”的 GRPO 收官判据，也没有触发 `<88%` 回吐/回滚判据。建议下一轮按设计进入 v1 讨论：有限解冻视觉编码器并重新约束更新幅度；本轮未自行启动 v1。

## 验收判据

| 判据 | 结果 | 结论 |
|---|---:|---|
| 3 seed × 16 env 快速回归 | `16/16、14/16、15/16 = 45/48 = 93.75%` | 相对基线 `42/48 = 87.5%` 提升 3 case |
| 512 集成功率 ≥93% | `467/512 = 91.2109375%` | 未命中 |
| 好结果 ≥95% | 未命中 | 未命中 |
| Stage2 失败明显下降 | `35 → 23`（`-12`） | 命中 |
| 其他 stage 失败不增 | Stage0 `+5`、Stage4 `+1` | 未命中 |
| 88–93% 边缘 | `91.2109375%` | **命中，最终结论** |
| <88% 回吐 | 未触发 | 不回滚 |

## 最终失败分布

512 集均为 seeds `0–31`，每 seed 16 env、每 env 一 episode。全部 45 个失败均为 `stage_overtime`。

| 最大 stage | 基线失败 | GRPO 失败 | 变化 |
|---:|---:|---:|---:|
| 0 | 15 | 20 | +5 |
| 1 | 2 | 0 | -2 |
| 2 | 35 | 23 | -12 |
| 3 | 0 | 0 | 0 |
| 4 | 1 | 2 | +1 |
| 5 | 0 | 0 | 0 |
| 合计 | 53 | 45 | -8 |

结果支持 GRPO 确实缓解了主要的 Stage2 bilateral contact/squeeze-continuity 失败，但部分失败迁移到了 Stage0，且 Stage4 多 1 case；因此不能把总体提升解释为全 stage 一致改善。

## 训练配置与停止点

- 初始 actor：`formal_4x64_8k_gpu4-7_timeoutfix_retry/model_step_008000.pt`。
- 训练设备：GPU2、GPU3；Accelerate DDP 两进程，每 rank 独占一个可见 GPU。
- 更新范围：仅 Student LSTM 与 action head；视觉编码器、Head encoder、noise std 均冻结。
- GRPO：actor-only、无 critic/GAE、无 reference KL、无 PPO 对照。
- 探索 std：`0.08`。
- action-rate 系数：`λ_ar = 0.5`。
- 学习率：`3.75e-6`，KL adaptive schedule 以上述值为上限，并允许向下衰减。
- 规模：每 rank 32 env，总 group 64；4 个 env mini-batch；1 epoch；recurrent chunk 128。
- checkpoint/gate：每 10 iteration。
- 预算：200 iteration；实际在 40 iteration 早停。

seed0 deterministic gates：

| Step | 成功数 |
|---:|---:|
| 10 | 16/16 |
| 20 | 16/16 |
| 30 | 16/16 |
| 40 | 16/16 |

连续 4 个 gate 均 ≥15/16，且从 step-10 起最高值 16/16 无进一步提升，故按设计 §5 在 step-40 提前收敛停止。四个 gate 同分时选首次达到最高值的 step-10 作为 best，避免引入无 gate 收益的额外策略漂移。

## Smoke 与 pilot

Smoke（2 env/rank × 1 iteration）通过以下链路：

- success 从 `last_completed_task_buf[dones]` 在 step 后读取，未发生索引错位。
- trajectory-level advantage 正确广播到该轨迹的全部 valid timesteps。
- rollout 保存 `_encode` 的精确 128D latent；更新从该 latent 重放，并与 rollout 使用同一 recurrent/action 路径。
- 首更 ratio max absolute deviation：`3.433e-5`。
- latent replay action-mean max absolute deviation：`9.537e-7`。

Pilot（10 iteration）最终标定：

- `std=0.08`、`λ_ar=0.5`、learning rate `3.75e-6`。
- 成功 `597/640 = 93.28125%`（带探索噪声，仅作训练诊断）。
- 平均 iteration 墙钟 `350.43 s`。
- 平均 action-rate mean/std：`0.6966 / 0.0935`。
- 平均 KL `0.001836`，平均 clip fraction `0.01167`。
- 零方差 group：`0`。

64 env/rank pilot 的首轮墙钟为 `535.96 s`，投影 200 iteration 约 29.8 h，按设计风险预案降为 32 env/rank。32 env/rank 后满足资源预算。

## 40 iteration 训练监控

累计 40 iteration、2560 条带噪 rollout trajectory：

| 指标 | Mean | Min | Max |
|---|---:|---:|---:|
| iteration seconds | 368.879 | 314.835 | 522.274 |
| group success rate | 0.91094 | 0.82813 | 0.98438 |
| group return std | 0.27198 | 0.11947 | 0.35830 |
| action-rate mean | 0.68855 | 0.66663 | 0.72074 |
| action-rate std | 0.10003 | 0.05236 | 0.14330 |
| analytic KL | 0.001217 | 0.000748 | 0.004263 |
| clip fraction | 0.005167 | 0.001066 | 0.040774 |
| ratio max | 1.53052 | 1.32600 | 2.33193 |
| first replay ratio max abs | `9.073e-5` | `6.771e-5` | `1.297e-4` |
| latent replay mean max abs | `2.572e-6` | `1.907e-6` | `3.338e-6` |

40 iteration 的纯 iteration 总墙钟为 `14755.14 s = 4.10 h`。全程零方差 group 为 0，未发生 advantage 广播越界、success 提取错位或 latent replay 根因错误。

## 实现摘要

- 新增 `GRPOTrainerA2BaseAPI`，子类化 `TRLPPOTrainer`，删除 Teacher/critic/GAE/reference-KL 路径，只保留 actor rollout、group return/advantage、clipped policy update、analytic KL 调度及 DDP 聚合。
- Student actor 新增精确 latent rollout/replay API；更新时以 stepwise recurrent replay 对齐 rollout 的单控制步 LSTM 数值路径。
- recurrent mini-batch 更新保持 rollout 的完整 local env batch geometry，loss 再按 env mini-batch 选取，避免 cuDNN 因 batch geometry 变化导致首更 ratio 漂移。
- 迭代间不重复调用只适合初始化的 `env.reset()`；首轮之后通过自然 timeout step 让所有 vector env 走既有自动 reset 路径，保持 A2 once-per-control-step grasp-streak 契约。
- 新增 GRPO algo/trainer/experiment config、GPU2/3 DDP 启动器及 512 集分片 runner。
- eval loader 支持 GRPO actor-only full checkpoint，并保持 fixed-G2 formal contract 不变。

## 运行中暴露并修复的问题

1. Accelerate 两 rank 同时暴露 GPU2/3 时，Kit/PhysX 无法建立正确 renderer/physics 绑定。改为每个 child 只暴露一个物理 GPU，并显式校验 rank、UUID、renderer physical index 与 physics logical index。
2. rollout 单步 LSTM 与整段 replay 在 cuDNN 下出现 ratio 漂移。根因修复为 stepwise recurrent replay；没有放宽 tolerance。
3. env mini-batch 改变 LSTM batch geometry，导致首更 ratio 漂移。根因修复为完整 local env batch replay后选取 loss mini-batch；没有使用 fallback。
4. 基类 KL schedule 将低 learning rate 强制抬到 `1e-5`。GRPO schedule 改为以 configured initial learning rate 为上限，并允许继续向下调整。
5. 运行后的显式 `env.reset()` 会在同一个 `common_step_counter` 重复执行 A2 grasp streak full update。未修改 env/契约；trainer 改用既有自动 timeout/reset 路径同步下一组 episode。
6. 训练 checkpoint 已落盘后，IsaacSim 多次停在 `simulation_app.close()`；等待确认无新增产物后终止自有关闭进程，未影响 checkpoint/metrics/eval。

## 产物

- 训练根目录：`logs_rl/by_batch/cb2h_v19_toeout6_pitch50_grpo_20260811/`
- Best checkpoint：`pilot_2x32_lr375e8_syncreset/model_step_000010.pt`
- 后续 checkpoint：`main_step_020/model_step_000020.pt`、`main_step_030/model_step_000030.pt`、`main_step_040/model_step_000040.pt`
- Gate：`gates/step_000010_seed0/` 至 `gates/step_000040_seed0/`
- 3-seed quick：seed0 复用 step-10 gate；seed1/2 位于 `best_quick/`
- 512 集：`large_eval/student_gpu2/seed_00..15` 与 `large_eval/student_gpu3/seed_16..31`

## 后续建议（不在本轮执行）

按 §6 的边缘结果路径，v1 可评估有限解冻视觉编码器，同时保持 actor-only GRPO、现有 fixed-G2 env/contract/randomization 和 gate/eval 协议。v1 的首要目标应是保留 Stage2 的 `-12` case 收益，同时查明并抑制 Stage0 的 `+5` case 回退；本报告不把该建议视为已批准实施。
