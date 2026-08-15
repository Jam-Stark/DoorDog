# a2_piper base_v24 草案(Draft v0.1,2026-08-16)

状态:**草案**,待 owner 审阅后升级 R1。本轮代号:**Friction Force-Boundary & Coupling Groundwork**。

---

## 1. 定位与 worktree 分工

推门主 worktree(本仓库)= novelty 引擎:force-feasibility / arm-base 力耦合研究主线,并产出对推拉门通用的 posture / 协同能力与接口。拉门 worktree 与蒸馏 worktree 并行走稳定路线,不在本 plan 范围;本 plan 对它们只承担 §11 的接口契约。GPU lease 动态,以当轮用户分配为准(设计按 4-8 卡弹性,§10)。

## 2. 从 v23 继承的输入事实(全部有 receipt)

1. **RP0 全面平价 + head-reset 平价**:当前门模型下姿态既非必需也非头部继承 → v24 **取消 init 轴与 RP0-on-easy 轴**,矩阵大幅简化。
2. **`V23_DOOR_MODEL_INSUFFICIENT_FOR_E2`**:drive 模型(damping/stiffness/max_force≤24)表达不了力边界 → 本轮物理主线 = LT-23-02 joint friction。
3. **effort ladder null(20 N·m 零样本无退化,冻结 40)**:arm 力矩不是约束;指令饱和是 Kp 伪影 → friction 门上 ladder 需重标定(预期这次 conclusive)。
4. **成功率天花板(规则 13)**:success-rate 只作 guardrail,主测量轴换力学量与行为质量。
5. **分析层欠账**:realized-dynamics 分类器 0/768、1280 干预 episode 裁决 PENDING、posture 饱和度从未计算 → v24 P0 先清偿(零 GPU)。
6. 16 个 rc0 candidates 可选 warm-start;forward-intervention / certificate / atlas 工具链就绪。

## 3. 研究问题与预注册假设

- **RQ1(边界)**:joint friction + breakaway 能否建立带反事实救援证据的真实 E1/E2?
  - H1':atlas 在 friction 轴上产出 confirmed E1 与 E2 zones,certificate 五条件可满足,无 solver 病理。
- **RQ2(负载条件化行为)**:真实力负载下,policy 行为是否变成 load-conditioned?(v23 H5 的可运行重做)
  - H2':DF1 上 hold/fling 策略、posture 使用(S_φ)、rescue 触发率随 realized friction 单调变化;DF0 上保持 v23 行为。
- **RQ3(姿态的力价值终裁)**:E1 桶内 FULL vs RP0 是否出现 gap?(v23 H3 重做)
  - H3':E1 内 ΔJ_φ>0 或 FULL-RP0 gap>0。**预注册对冲**:若 friction 负载下 RP0 仍平价,则结合 v22 atlas(neutral 方向性容量近最优)正式裁定"roll/pitch 非力资源",力研究聚焦 bracing/站位——这同样是干净结论,直接决定论文叙事(ledger C.9)。
- **RQ4(力耦合测量,novelty 地基)**:高 arm wrench 状态下,足底反力路径 / frozen locomotion 抗滑补偿的特征是什么?(测量级,为 LT-23-06/07 提供监督数据形态)

## 4. Phase 0 — v23 欠账清偿与选点(零 GPU,~0.5 天)

1. 修 realized-dynamics 分类器(对 v23 的 768 stratified episodes 重跑,验收=分类率≥90%,typed 残余)。
2. 写 forward-intervention 裁决器,关闭 1280 episode 的 ΔJ_φ/结局;从 step trace 计算 16 cell 的 saturation dwell / FP_φ / S_φ + clearance×posture 分析 → 出 `V23_POSTHOC_ANALYSIS.{json,md}`,正式关闭 v23 H1 行为版/H3/H5。
3. **warm-start 机械选点**:16 candidates 中限 FULL cells,按 holdout64 goal ↓ → pooled48 ↓ → unsafe ↑ 排序,优先 D1-trained(对 friction 门的分布先验更近);产出 checkpoint 路径写入 plan。
4. 分类器/裁决器修复即视为 v24 工具链一部分,formal 阶段直接复用(规则 14:一律按 realized telemetry 分层)。

## 5. Phase 1 — LT-23-02 friction retrofit(主线,~1-1.5 天)

1. **Plumbing**:door.py hinge 接入 PhysX joint friction(Coulomb 常阻力矩,per-env randomizable,沿用既有 scalar resolver 模式);breakaway 语义 = static>kinetic 的两态近似(若 PhysX 单系数不够,用低速高摩擦/越阈值降摩擦的显式状态机,标注 proxy 语义)。additive + `a2_v24_*` config-gated,默认关闭。
2. **Physics 验证探针**(复用 characterize/fixed-torque 工具):(a) 准静态阻力与速度近无关(区别于 damping);(b) τ_required 随 friction 参数单调、可分辨(直指 v22 的 below-resolution 失败模式);(c) 参数域内无 solver 震荡/门瞬移;(d) 与 mass/damping/stiffness 正交组合稳定。
3. **Atlas 重建 + ladder 重标定**:friction 主轴 × {damping, mass} 副轴;A0 zero-shot ladder(此次预期 conclusive)选 τ_v24(可能维持 40);physics-first E0/E1/near-E2/confirmed-E2 分区 + certificate 阈值定标冻结(判据沿 v23 P0.5 带宽,high-effort 定义在 CLIPPED 执行侧)。
4. **DF0/DF1 冻结**:DF0 = v23 D0 原样(回归锚 + 迁移测量);DF1 = E0/E1/near-E2 混合(curriculum 沿 v23 表),confirmed E2 只进 held-out。同时冻结 DF1-lite(预案)。
5. **GO/NO-GO gate(只挂本轮边界主张)**:若 friction 轴在稳定参数域内仍无法实现 E1(遑论 E2)→ typed `V24_FRICTION_MODEL_ALSO_INSUFFICIENT`,**停止训练波,升级 owner 决策场地问题(拉门/其他)**——这是本草案唯一保留的请示点。

## 6. Phase 2 — Wave 1 science factorial(单波 8 run,~1 天)

v23 已关闭 init 轴 → 简化为 **{FULL, RP0} × {DF0, DF1} × 2 seeds = 8 run**,4096 env × 2500 batches,单一 warm-start(§4.3),common reward 沿 v23 冻结版不动。8 卡=单波;4 卡=两串行 sub-wave(v23 先例)。

| Cell | Door | Posture | 回答 |
|---|---|---|---|
| W1/W2 | DF0 | FULL/RP0 | 回归锚 + friction 训练分布外迁移 |
| W3/W4 | DF1 | FULL/RP0 | H2'/H3' 主对照 |

Route A(10 ckpt × canonical16,机械选点)→ Route B:pooled48 + realized-friction 分层 + 干预套件(含 rescue,此次预期高触发率)+ holdout64 + E2 held-out suite(若 E2 建立)。

## 7. Phase 3 — Wave 2 novelty pilot(conditional,~1 天)

**入场条件 = Wave 1 确认 E1 真实**(H1' 至少 E1 部分成立):

1. **LT-23-08 最小版 gated posture**:`a_φ = g_t·Δφ_t`,gate 输入只用 task-agnostic history(force/progress/margin),1-2 cell 对照 FULL-DF1;判读 = E0 经济性提升且 E1 无损(规则:gate 只在负载桶打开,v15 教训)。
2. **LT-23-06 shadow coupling critic**:用 Wave 1 的干预/telemetry 数据离线训练,只报校准指标,不进 PPO。
3. **RQ4 测量包**:高负载 episode 的足底反力/locomotion 补偿 telemetry 分析(纯分析,不改训练)。
4. 若 Wave 1 还建立了 confirmed E2:LT-23-10 body-assist 解锁进入 v25 规划(不塞进本轮)。

## 8. 指标(规则 13:success-rate 仅 guardrail)

主轴:clipped torque utilization under load、hinge progress under high effort、rescue 触发/成功率、ΔJ_φ、S_φ、FP_φ、hold/fling×realized-friction 条件化、clearance 质量(恢复 v22 口径)、unsafe 率。guardrail:pooled48/holdout goal 不低于 v23 基线 -3 门(DF0)。统计口径沿 v23 修订版(门数 margin + 双 seed 同向 + binomial CI)。

## 9. 预案(草案级)

- F1 friction 数值不稳 → 参数域收缩一次;仍不稳 → §5.5 NO-GO 路径。
- F2 DF1 天花板复现(friction 仍不难)→ ladder×friction 联合再标定一轮(仅一次);再不行 → NO-GO 路径。
- F3 Wave 2 gate 学不出选择性 → typed negative,LT-23-08 退回 long-term,不重试。
- F4/F5(崩溃/系统性 bug)、GPU lease 变动串行重排、长 sleep 自估时长、per-code-path 64×10 smoke:全部沿 v23 worker prompt 条款。

## 10. 资源与日程

P0 0.5 天 → P1 1-1.5 天 → Wave 1 训练 1 天(8 卡)+ eval 0.5 天 → Wave 2 conditional 1 天 + 收尾 0.5 天 ≈ **4.5-5.5 天**(4 卡时训练×2)。

## 11. 交付物与跨 worktree 接口

1. `V23_POSTHOC_ANALYSIS`、friction plumbing + physics receipts、atlas/certificate freeze、Wave 1/2 结果与 typed 裁决、`V24_FINAL_ANALYSIS`、memory entry 与 ledger 更新。
2. **接口契约(拉门 worktree 消费)**:5D posture command 语义不变;gate 模块输入契约 task-agnostic;E-region certificate 工具链与 realized-dynamics 分类器以可 import 形式交付;friction randomization 的 door.py 接口对 in/out 门同样适用。
3. 论文素材:RQ3 无论正负都产出 C.9 叙事的终裁证据;RQ4 产出 coupling critic 的监督数据形态定义。
