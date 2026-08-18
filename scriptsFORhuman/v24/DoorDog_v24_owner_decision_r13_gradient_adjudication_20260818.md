# v24 Owner 决策:r13 梯度终局裁决与 E 区分类器修订(2026-08-18)

```text
DECISION_Q(47/96 是否控制终局)     = NO——matched modeled-τ strict ordering 预测子不控制终局
新 typed 结果                      = V24_FRICTION_AXIS_DISCRIMINATIVE_BEHAVIORAL(新 artifact,旧件不改)
matched modeled-τ 预测子           = 降级为 report-only 诊断,typed
                                     MODELED_TAU_MATCHED_ORDERING_CONFOUNDED_BY_SPEED_ADAPTATION
E 区分类器                         = 修订为行为响应分类(见 §2;F3′ 种群生成前冻结数值)
WORKER_CONDUCT                     = 范本级:注册请示点正确停止、零 gate 改写、诚实区分 artifact 与证据
```

## 1. 为什么 47/96 不控制终局

1. **该预测子要求物理上并不保证的性质**:modeled τ_req = I·θ̈ + c·ω + k·θ + τ_f(ω)。摩擦升高 → policy 变慢(96/96 方向性证实)→ c·ω 与 I·θ̈ 分量下降,在 matched scenario 内部分抵消摩擦分量;stick/低速相位的 τ_f(ω) 建模值也系统偏低。τ_s 从 2→20 N·m(+18),modeled 中位数只 +2.2(27.39→29.57)——恰是速度自适应抵消的量级指纹。对这种量要求 72/96 的 per-scenario 严格序,是把"轴是否真实"误写成"一个受混杂的派生量是否单调"。
2. **轴的物理真实性已在 P1-lite input-output 层面确立**:breakaway literal containment [1.5,2.0]/[4.5,5.0]/[9.5,10.0]/[19.5,20.0],B/C/E/G 全过。
3. **注册的行为判据以最强形式通过**:四档中位 progress 严格递减(0.0612→0.0569→0.0486→0.0389),P02>P20 96/96,span 0.0223 > 0.02 冻结底线;modeled-τ 中位数亦严格递增。
4. 结论:friction 轴在 escalated 域上**同时具有物理真实性与行为判别力**,这正是 R1"gradient admission"想测的语义。

## 2. E 区分类器修订(本决策授权,F3′ 前冻结)

r13 同时暴露:registered capacity floor 下 **358/384 加载窗口 CAPACITY_COLLAPSED**、仅 26 行有限 λ、四档 E1 计数 2/0/0/0——而这些"超出容量"的窗口里门仍被打开(progress 0.039-0.061)。即 min-over-joints 方向性余量是**过保守下界**,在加载相位结构性塌缩,λ 不能作为主分类器。typed 记录:`CAPACITY_ESTIMATOR_LOWER_BOUND_DEGENERATE`(本身是 RQ4 值得报告的 finding)。

**修订(policy-as-instrument,对齐 ledger 既有原则与规则 13)**:主分类器 = 行为响应 × 已验证的请求轴(τ_s × cap 网格):

- **E0**:valid grasp + progress 在 sham 带内(deficit < δ_lo)+ 无方向性 load-bearing 高负荷证据;
- **E1**:valid grasp + 梯度化 progress deficit ∈ [δ_lo, δ_hi] + 方向性 load-bearing clip fraction/utilization ≥ 冻结底线;
- **near-E2/E2 候选**:valid grasp + deficit > δ_hi + 持续方向性高负荷;confirmed E2 仍须 rescue 反事实(tau_rescue/oracle)按 certificate;
- λ/capacity 字段保留为 ESTIMATE_ONLY 报告量(RQ3/RQ4 用),`CAPACITY_COLLAPSED_WINDOW` 保留 RQ3 mediator 角色;
- δ_lo/δ_hi/clip-floor 数值由 r13 校准分布冻结,**先于 F3′ 种群生成**(F3′ 裁决数据尚不存在,校准集的用途就是定义分区——合法)。

## 3. 复工序列

1. 出具新 gradient 裁决 artifact(§1)→ ladder freeze:用 (τ_s × cap) 行为面选 `tau_hi / tau_boundary / tau_rescue`(应非 null)→ E 区冻结(§2)→ **F3′**(32 eps/cell,≥8/cell,注册语义不变)。
2. F3′ 通过 → 自主继续 P3 → Wave 1 → Route A/B → RQ3 → Wave 2a(/2b),纪律与等待协议不变。
3. **F3′ 在行为分类器下仍 <8/cell → `V24_E1_DENOMINATOR_INSUFFICIENT_FINAL`,收口整轮,不再有任何 gate 修订**;这将构成"轴有判别力但 E1 密度不可达"的最终负结果,场地问题升级 owner。
4. 旧 receipts(r10-r13)一律不改;新裁决新文件引用本决策。规则 16/17 本轮已实证有效,连同规则 18 候补(**派生量 gate 必须证明其单调性/有效性假设,否则只能 report-only**——本次 47/96 的教训)轮末入 ledger。
