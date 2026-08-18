# v24 Owner 决策:friction 参数域量级升级(一次性注册,2026-08-18)

```text
DECISION                          = REGISTERED_FRICTION_DOMAIN_ESCALATION(一次)+ E1 语义补丁 + 继续注册生命周期
V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3(r12) = 程序合法,保留;科学含义重述为
  "在 τ_s∈[0,1.0] N·m 的域内不存在力边界"——该域比 v22 已证可解的 24 N·m drive 阻力低 ~25×,
  比真实防火门低 ~50×,是 null 轴;本轮尚未测试过"friction 能否建立力边界"这个问题本身
WORKER_CONDUCT                    = 合规;缺陷第四次在 gate 作者侧:R1 "数值范围由 probe 定"未锚定目标量级
RQ4 measurement-only 结论         = 接受(FORWARD_PROXY_ONLY / CRITIC_UNCALIBRATED 为有效 typed 交付)
```

## 证据要点(本地已核)

1. `V24_P2_PARAMETER_RANGE_FREEZE.json`:F00/F05/F10 = τ_s 0 / 0.5 / **1.0 N·m**(handle 侧 ≈1.2 N)。
2. gradient medians 0.0829/0.0817/0.0800(~3% 总效应),`strong_model_evidence=false`——axis 在此域内无判别力,与 r12 终局一致且互证。
3. pilot population λ:median 0.538,**max 4.9×10⁷**——λ 在方向性容量塌缩处爆炸;12 个 sustained-E1 窗口主要是 Jacobian 差构型信号(arm 几何),不是门阻力信号。
4. 规则 17(候补,轮末入 ledger):**参数域冻结必须携带目标量级锚**——量级由仓库内已有证据标定(此处:v22 可解上限 24 N·m、arm 方向性容量估计),probe 只负责验证该量级下的稳定性,不负责决定科学量级。

## 指令(按序)

1. **P1-lite 量级复验**(GPU0,分钟级):escalated 网格 τ_s ∈ {2, 5, 10, 20} N·m(ρ=0.75;c_v=0 为主,可加一个非零变体),重跑探针 A(breakaway containment)/B/C(平台与 damping 区分)/E(chatter)/G(正交,A0/A8×最高档)。出现不稳 → 收缩到稳定最大值继续,typed 记录;不再逐级请示。
2. **E1 certificate 语义补丁**(新测量总体的 gate,r13 数据前冻结,合法):E1 admission = (i) τ_req ≥ demand floor(从 escalated probe 定,量级 ≥2 N·m 面)**且** (ii) λ∈band 且 τ_avail,dir ≥ capacity floor;τ_avail,dir < floor → typed `CAPACITY_COLLAPSED_WINDOW`,不入 E1,单独统计(它是 reach/geometry 信号,归 RQ3 mediator 侧使用)。λ 分母加下限保护(typed,不做数值 clamp)。
3. **P2 r13**:Rule16 vitals → calibration(6 cap × escalated friction 网格 × 16 paired scenarios)→ gradient admission(期望真实梯度;仍无梯度且域已达稳定最大 → 这次才是真语义的 `V24_FRICTION_AXIS_NONDISCRIMINATIVE`,**触发 P3 owner 决策点语义,停下请示**)→ ladder/certificate freeze(tau_hi/tau_boundary/tau_rescue 应非 null)→ E 区冻结。
4. **F3' 评估分母加宽**:denominator gate 在 r13 校准前注册为"每 cell 32 episodes 中 admitted sustained-E1 ≥8"(密度 bar 25%;不复用 r12 的 16-episode 语义)。
5. E1 成立 → 按注册生命周期自主继续:P3 历史零样本扫描 → Wave 1 → Route A/B → RQ3 → Wave 2a(/2b),全部纪律与等待协议不变。E1 仍不足(在 escalated 域 + 新语义 + 32 分母下)→ `V24_E1_DENOMINATOR_INSUFFICIENT_FINAL`,收口整轮,这将构成"当前 push-door + 该机器人构型下摩擦轴无法制造力边界"的强负结果,场地问题升级 owner。
6. escalation 仅此一次注册;旧 receipts 一律不改;新裁决新文件引用本决策。
