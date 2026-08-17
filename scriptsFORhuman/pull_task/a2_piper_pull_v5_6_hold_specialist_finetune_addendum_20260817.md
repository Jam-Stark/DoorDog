# A2+Piper Pull v5.6 — Terminal-Hold Specialist Fine-tune(梯子第三 rung,末级):Addendum

**Plan ID:** `a2_piper_pull_v5_6_terminal_hold_specialist_finetune`
**Date:** 2026-08-17 HKT
**性质:** 本文件是长期 TODO §11 三 rung 梯子**第三(末级)rung 的 planner 正式契约**,兑现 v5.5 §0.6 return-to-planner 裁决。v5 科学契约(P3 定义、DV、invariant 1–11、G1–G13、停止条件、warm-start、reward 冻结)**原文有效**;v5.1 G8 bank(191 态)、v5.2 门侧/override/双源实现、v5.3 P0 表征、v5.4 Stage A 21 常数表、**v5.5 holdtrack 任务/五族 gate/rehearsal/anchor harness 与 r13 sampled/applied provenance 机制**均为既有资产,原样复用不重写。冲突时本文件优先。
**一次性覆盖(用户 2026-08-17 指示):** 本契约一次给出剩余 v5 阶段全链方案(fine-tune → gate → rehearsal → anchor → 门侧 → P3/P4 → 双源 eval → render → 收官),worker 无人值守整轮自主执行,预案覆盖分支决策;仅在预案无法覆盖且继续将违反铁律时按 G11 停。
**GPU 授权:** GPU 4、5、6、7;其余禁用。训练 GPU4,gate 并行 GPU5,P3 解锁后 GPU4–7。
**产出落点:** 延用 `scriptsFORhuman/pull_v5/`,新报告 `PULL_V5_6_ROUND_REPORT.md`(英文)。

---

## 0. Planner 裁决与设计依据(全部引用 v5.5 及此前实测)

1. **v5.5 收官追认:** r13 750/750 完成;T1 gate step250/500/750 = `0/80、1/80、0/80`,唯一 K100 为 step500 `near_rest` env15(XY `0.0397 m`/yaw `0.0299 rad`),远低于 per-family ≥15/16 与 overall ≥77/80;唯一 plateau 选项已消耗;T2/T3/门侧/G2/P3/P4/双源/render 如实 NOT_RUN;G11 正确收官;唯一 formal review FAIL、无二轮 PASS——全部追认。**rung 2 在其注册契约内证伪**(结论限于该 adapter/预算/课程,不外推所有 residual 架构——但见下条,不再重复同类尝试)。`v5_5_planner_architecture_decision.json`、`v5_5_adapter_gate/TRAINING_GATE.json` 与 v5.3/v5.4 adjudication artifacts 一律 immutable。
2. **为什么进入 rung 3(fine-tune),不做第四种"frozen 之上"控制器:** 三类控制器已依次穿过同一 frozen HOMIE base-command 接口失败——v5.2 r4 P 控制 active hold(陷死区)、v5.4 开环粗放+trim scheduler(粗放 0.090 rad 可达,trim 相无权威、16/16 cap_exceeded)、v5.5 学习型三维闭环 residual(本轮 1/80)。缺口由此定位在 **frozen 低层策略自身的命令响应映射**:|u|<0.8 死区/偏置漂移、≥0.8 粗档,不存在可提取的精细权威区间;上层无论脚本或学习都取不出低层不具备的能力。r13 残差结构佐证:XY mean ≈0.33 m(阈值 0.05 m)是主导失效轴(与 A3 的 XY 独立失效一致),yaw 偶达 1e-4 rad 级但不可保持。**唯一剩余 rung = 改变低层策略本身。**joint 级 residual(frozen HOMIE + 12 维腿残差)不另立 rung:HOMIE 经扰动鲁棒训练,会把持续残差当外扰主动抵消,本质仍是第四种"frozen 之上"方案,证据上不优于 fine-tune,不采用。
3. **架构定义(rung 3):** terminal-hold specialist = **HOMIE/A2_Base checkpoint 的派生副本 fine-tune**。原 checkpoint 文件 immutable,继续独占所有非 terminal 相(行走/前奏/transit);specialist 仅在既有 v5.5 handoff/terminal 窗口内接管,输出原 frozen-leg 槽位的 12 维腿动作。目标注入走**既有 carrier 命令槽 0:3**:base 系目标误差 `(ex, ey, wrapped eyaw)` 增益 1、按注册通道界截断、逐步刷新——零新常数、零网络结构改动,warm-start 精确(carrier 本就在 HOMIE 观测路径内)。carrier 其余(3:11 零、11 gripper open)照 v5.5。**灾难遗忘按构造不成立:** transit 永远用原 frozen HOMIE;specialist 只需覆盖 handoff 后分布,五族前奏恰好就是该分布。
4. **Frozen 不动(本轮 immutable):** 原 HOMIE checkpoint 文件、pull actor(v4-B seed1 step750)、pull 任务 reward/stage topology/optimizer、0.05 m/0.15 rad 阈值、S1–S4 目标定义、G8 bank。**新代码只增不改**:v5.5 adapter 任务/gate 既有文件不改,新文件 import/subclass;确需最小接缝时在报告记录 diff 边界。specialist 存为**新版本化资产**,绝不覆写原 checkpoint。
5. **任务/reward 同一性(跨 rung 受控比较):** 复用 v5.5 五族任务、偏移分布(‖dxy‖∈[0,0.5] m、dyaw∈[−0.6,+0.6] rad)、K100/2 s、0.05 m/0.15 rad、350 步预算与 reward 表**原文**;`penalty_adapter_action_delta`(−0.01)作用面移到 specialist 12 维动作增量;不惩罚动作幅值。行类 `interface_characterization`、`scientific_denominator_included=false`、`denominator_scope=none` 照旧。这样 rung2→rung3 唯一变量是可训练面(3 维命令 residual → 低层策略本身),gate 判据逐 rung 同一。
6. **fail-closed 链:** `v5_6_planner_architecture_decision.json`(记录 rung 3 激活、`original_homie_immutable=true`、`ladder_final_rung=true`、引用 v5.5 FAIL receipt 与轮报)→ step-0 基线 gate + T1 训练 gate receipt → T2 rehearsal PASS → T3 G3 anchor PASS → 门侧/P3/P4(v5.2 gates)。缺环拒绝 launch。
7. **末级语义(本轮即梯子终点):** specialist 证伪(T1 预授权选项用尽仍不达 / rehearsal 双 FAIL / anchor 3×FAIL)→ G11 收官时必须明确记录**"三 rung 梯子已穷尽,任务级重设计返回 planner(涉及 anchor 语义/硬件路线等用户级决策)"**;worker 不得自创 rung 4。

## 1. T0 — Specialist 模式、warm-start receipt 与静态验收

- **命名空间(只增不改):** `pull_v5_6_hold_specialist`(新 exp/config/wrapper/trainer 文件;v5.5 与 pull 任务既有文件不改)。任务/fixture/五族前奏/偏移分布/成功判据与 v5.5 注册原文完全一致。
- **Warm-start receipt(T0 落盘,逐项):** actor 权重自原 HOMIE checkpoint;critic 兼容则同载、不兼容则 fresh 并如实记录;optimizer 一律 fresh;**探索噪声 std 重置为既有 A2 PPO 路径的 fresh-training 初始值**(从现行 config/module 解析并记录解析值),不得继承收敛后塌缩的 std。receipt 记录:源 checkpoint 路径、各部件 init 方式、resolved std、超参(= v5.5 r13 所用既有 A2 trainer 默认,不另调)。
- **Provenance(r13 经验,必须复用):** 前奏/handoff 相腿动作来自 frozen HOMIE,属 scripted/applied,**排除出 policy/entropy 分母**;critic 保留完整 trajectory;env 执行始终消费 applied 动作。
- **Step-0 基线 gate(诊断,不 gate 后续):** 训练前用**未 fine-tune 的 HOMIE + 增益 1 目标误差命令映射**跑一次同款 80-episode gate,落 `v5_6_specialist_gate_step0/`。作用:分离"命令映射本身"与"fine-tune 产生的能力"(按 v5.3/v5.4 死区事实预期近 0/80;若显著非零须在报告解释)。
- 静态验收:改动文件 compile、YAML/Hydra 组合、生成命令检查、warm-start/std/映射截断 fixture 各一遍,不重复串行。

## 2. T1 — Fine-tune 训练与 gate(GPU4/5)

- PPO fine-tune,256 env,≤750 batches,seed0,checkpoint 每 250;独立 tmux `pull_v5_6_specialist_train`,tee 进 `logs_rl/a2_piper_pull_v5_6_hold_specialist/`。
- **课程预授权为默认训练分布:** v5.5 已注册的三档 target-offset 课程(0.10 m/0.15 rad → 0.25/0.30 → 0.50/0.60,按全局 sim steps 换挡)自 batch 0 启用;**gate 评测永远用注册全量程分布**并记录 `training_gate_registered_full`。
- **Gate(每 checkpoint,GPU5 并行):** 五族 × 16 = 80 held-out,判据原文:**任一 checkpoint per-family ≥15/16 且 overall ≥77/80** → 冻结为版本化 specialist 资产,进入 T2;receipt 记录 checkpoint 路径/step。
- **Plateau 预案(末级放宽为至多两次,证据定向,各限一次):** 750 batches 无达标 checkpoint → 依 gate 遥测二选一先用其一:(a) 续训至 ≤1500;(b) 单项定向调整(LR 降档 / std 重置值 / 单一 reward-scale / 课程换挡点,四者取一)+ ≤750 重训。首次后仍不达,可用剩余一项。两项用尽仍不达 → G11,按 §0.7 末级语义收官。
- 训练崩溃/NaN → G9:读 traceback 修根因重跑,invalid attempt 保留存档、不计科学次数;不得改 pull 任务或 v5.5 既有文件来"救"。

## 3. T2 — Rehearsal(GPU4,diagnostic,不占 G3)

- 与 v5.5 注册原文相同:cell-A 净转 −2.5 rad + 0.3 m、cell-B +1.0 rad + 0.3 m,每 cell 8 env;PASS = 8/8 注册 DONE(K100 current-state 保持,阈值原文,terminal 行取 `env.step` 返回 dones)。
- FAIL → 一次由 trace 定向的修正(handoff/窗口常数,或指向具体未覆盖初始条件族的单次补训)+ 单次复跑;仍 FAIL → G11(§0.7)。

## 4. T3 — Anchor 与条件下游(照 v5.2/v5.5 原文)

1. **S1–S4 narrow anchor 复跑**,判据原文(每序列 16/16 terminal current-state,0.05 m/0.15 rad,rule-5 语义);specialist 仅 terminal 相 active(挂既有 handoff 钩子)。新开 G3 计数 ≤3;attempt 间仅 receipt 定向的常数/handoff 修正;receipt 指认具体未覆盖初始条件族时允许一次定向补训。
2. **任一序列 PASS** → rule-5 admitted subset 进门侧:**原样恢复 v5.2 addendum §1–§2 全部下游**(三桶 → G1/G2 → P3 2×2(GPU4–7)→ 条件 P4 → 双源 eval);门侧定位 primitive 同样 specialist-active;G5/G6/G7/G12 按 v5 契约原文执行,代码不重写。
3. **3×FAIL** → G3/G11 收官(§0.7),附训练曲线与全部 gate/rehearsal/anchor receipts。

## 5. Invariant 12′(specialist provenance,运行期核验)

`hold_specialist_active` 仅允许在 locomotion probe 相(holdtrack 任务、anchor primitive、门侧定位 primitive)为真;**永不**出现在 P3/P4 训练动作或任何 canonical/natural DV episode 行。每 receipt 行记录该布尔 + specialist checkpoint 路径/step + 原 HOMIE checkpoint 路径(证明 transit 侧未换);P3/P4/双源 eval 运行期断言 specialist 未挂载。invariant 1–11 原文不变。

## 6. 排程与预算

```text
T0  decision JSON + specialist 模式 + warm-start receipt + step-0 基线 gate + 静态验收(~1.5–2.5 h)
T1  fine-tune ≤750 batches + 每 250 gate(GPU4/5,~4–5 h;plateau 预案至多再 +~9 h)
T2  rehearsal 2 cell(GPU4,~0.5–1 h)
T3  anchor 复跑(GPU4,G3 ≤3,单次 ~30 min)
T4  (条件)v5.2 门侧三桶 → G1/G2 → P3(GPU4–7)→ P4 → 双源 eval,照 v5.2 排程
T5  render + 英文报告 + memory + 两级 TODO(§11 rung-3 末级)+ commit/push
```

仅 T0–T3+T5 约 8–12 h;T4 解锁全轮 14–20 h。等待纪律照旧:大块 sleep(训练 3600 递进、允许一次 20h 级)、禁轮询、子 agent 值守。

## 7. Review 纪律

一轮 formal review,重点点名:(a) **原 HOMIE 不可触碰**——原 checkpoint 文件零修改、transit 路径仍加载原件、specialist 为新资产、切换 provenance 正确;(b) carrier 命令槽目标误差映射(base 系、wrapped yaw、注册界截断、增益 1、零新常数);(c) warm-start/std/optimizer receipt 与 r13 provenance 分母隔离;(d) gate/rehearsal/anchor 判据预注册与 fail-closed 链逐级生效;(e) invariant 12′ 实现与运行期断言。**FAIL findings = 定向修复 + runtime 验收,不停轮、不二轮**(durable 契约)。

## 8. 交付物

1. feat(a2) 小步 commit(runtime-proven 即提交)+ push 到 `codex/a2-piper-pull-v0-20260803`。
2. `scriptsFORhuman/pull_v5/PULL_V5_6_ROUND_REPORT.md`(英文):warm-start receipt 表、step-0 基线 vs 各 checkpoint 五族矩阵、训练曲线摘要、rehearsal receipt、anchor 逐序列 receipt、条件下游各表(照 v5.2 报告格式)、render 索引、G1–G13 日志、invariant 表(含 12′)。不写哈希。
3. `logs_eval/a2_piper_pull_v5/v5_6_planner_architecture_decision.json`(§0.6 字段)。
4. 落点:训练 `logs_rl/a2_piper_pull_v5_6_hold_specialist*/`;gate `logs_eval/a2_piper_pull_v5/v5_6_specialist_gate*/`;anchor 前缀 `v5_6_`;门侧/P3/P4 照 v5.2 惯例;render `logs_eval/a2_piper_pull_v5/render_v5_6/`。
5. Memory 更新(specialist 能力判定为 durable fact;证伪则记录"三 rung 梯子穷尽、任务级重设计返回 planner")+ 两级 TODO 勾稽(§11 rung-3 末级状态)。
6. 受保护 evidence ZIP 与 75 条 projected traces 保持未跟踪、未修改;G8 bank 不重建不改写。
