# v24 Owner 决策:D gate 修订与复工(2026-08-17)

```text
DECISION            = OWNER_GATE_REVISION_D_V2 + CONTINUE_FROM_P2
FINAL_STOP_AT_P1    = REJECTED_AS_ROUND_TERMINAL(P1 receipt 本身保留为历史,不重标)
WORKER_CONDUCT      = CORRECT(按预注册 typed outcome 收口并如实报告;规则 15 的正确示范)
ROOT_CAUSE          = R1 gate 作者缺陷:literal D 公式引用了许可 API 不暴露的量
```

## 修订理由(4 条)

1. **Gate 引用不可测量则不能裁决任何东西**:literal `τ_friction·ω ≤ tol` 需要 solver 广义摩擦力矩分量;IsaacLab 高层 API 只提供 friction property write/readback(worker 已审计确认)。
2. **项目先例一致性**:arm 侧自 v21B 起就以 `ESTIMATE_ONLY/CLIPPED` authority 运行,v23/v24 的 E2 certificate 因此显式定义在 CLIPPED 面。门侧摩擦力矩字段同理取 `MODELED_FROM_PARAMS` authority(参数是我们设定的,ω 是可测的),而不是要求 solver 内部量。
3. **D 的目的可以由可观测量完整达成**:D 防的是 solver 能量注入(数值病理)。总机械能核算严格用可观测量:对任意探针轨迹,`E_dissipated(t) = W_applied(t) − ΔE_mech(t) ≥ −tol` 且累计耗散在容差内非减,其中 W_applied 来自我们指令的探针力矩×dθ,E_mech = 动能(I 已配置)+弹簧势能(k 已配置),θ/ω 可观测。无需 solver 内部量。
4. **黑盒行为验证正是本项目一贯标准**("策略本体是最高保真仪器"、behavior-based ladder):A/B/C 已经 input-output 验证了摩擦幅值语义(breakaway 在请求 τ_s 处、kinetic 平台对应 τ_d、与 damping 可区分),叠加 D-v2 能量核算即构成完整黑盒验证。下游科学从未需要 solver 摩擦读回:τ_required 来自探针响应,high-effort 在 arm 侧 CLIPPED 面,RQ4 门侧字段本来就定义为 modeled friction torque。

## 指令

1. **D-v2 定义**(取代 literal D,作为 R1 附录修订,引用本决策):按理由 3 的能量核算式;**在全新探针轨迹上运行**(新 seed/轨迹,不复用此前 proxy 数据);容差从新轨迹的噪声底冻结后再判 PASS/FAIL。
2. **Authority 标注**:全部门侧摩擦力矩字段带 `MODELED_FROM_PARAMS`;任何报告不得声称 solver-applied。
3. **新 typed 终点**:A/B/C/E/F/G/H/I(既有 receipts 有效)+ D-v2 PASS → 写 `V24_FRICTION_MODEL_VALID_BEHAVIORAL`(新名字,诚实标注行为学验证与 authority 边界)。R1 admission 行修订为:P2/P3 准入条件 = `MODEL_VALID_BEHAVIORAL`。D-v2 FAIL 则维持停轮,typed `V24_FRICTION_ENERGY_ACCOUNTING_FAIL`。
4. **复工序列**:D-v2(GPU0,分钟级)→ P2(方向性容量/λ/ladder 重标定/E 区 certificate,含此前 `NOT_PERFORMED` 的 parameter-range freeze)→ P3 历史零样本扫描(**真正的 owner 决策点仍在此**:`AXIS_NONDISCRIMINATIVE` 才请示)→ Wave 1 及其后按 R1。等待纪律(梯度短检→长眠)、smoke、命名、additive+gated、不 push 等全部纪律不变。
5. 旧 receipts(`V24_P1_FINAL_ADJUDICATION.json` 等)一律不改;新裁决写新文件并引用本决策为依据。
