<!-- managed-by: jam-coding-role; file: STAGE_DECISION.md -->
# Optional Multi-Planner Stage Decision Workflow

本文件用于长周期科研、训练或复杂产品迭代。它是 Owner 可选的决策模式，不是每一阶段都必须执行的审批流水线。

## 1. 角色与权限

- **Owner**：发起阶段、选择 planner 组合、确定预算与最终方案。
- **Local planner（常见为 standalone Claude）**：能读本地 worktree、memory、未跟踪 artifact、resolved config，并可运行本地 smoke/IsaacLab；负责生产可执行性和资源现实性。
- **Cloud insight planner（常见为 GPT Pro）**：读取远程仓库和阶段 artifact bundle，独立分析 novelty、研究问题、替代解释和实验设计；不得假设看不到的本地运行事实。
- **Worker**：实现和运行正式方案；不替 Owner 决定科学主张或放宽 release 标准。

## 2. Owner 选择 planner roster

每一阶段由 Owner 从下列组合中选择，不设默认强制双审：

- Owner 直接决定；
- 只用 local planner；
- 只用 cloud insight planner；
- local + cloud 独立出方案，再由 local planner 综合；
- 使用其他指定 planner/reviewer。

## 3. 推荐的双 planner 流程

```text
上一阶段收口
-> worker 固化 code / ledger / artifact bundle
-> local planner 独立方案
-> cloud planner 独立方案
-> local feasibility audit + comparison
-> formal synthesis
-> Owner approval
-> worker execution
```

为了减少锚定，两份独立方案应在相互可见前先完成各自第一版。

## 4. Cloud plan 的证据边界

Cloud planner 可以：

- 对照远程代码与上传 artifact 提出新 insight、novelty、替代解释和实验轴；
- 审核因变量、对照组、因果边界和论文叙事；
- 指出远程代码与 artifact 之间的矛盾。

Cloud planner 不可以仅凭远程材料断言：

- 本地 IsaacLab API、GPU、display、driver 或依赖一定可用；
- 未打包日志、resolved config、checkpoint 或 render 存在；
- 某个 formal budget、denominator 或 gate 在生产环境一定可实现；
- static evidence 等同于 runtime/training pass。

## 5. Local feasibility audit

Local planner 综合时至少检查：

- 文件、符号、config key、checkpoint 和 artifact 路径是否真实；
- IsaacLab/依赖 API 是否与本机版本相符；
- GPU、worktree、输出目录和运行时长是否可执行；
- gate 所需 denominator、telemetry、event 和 reducer 是否实际可观测；
- cloud 方案是否把 descriptive finding 写成 causal/release gate；
- 是否存在会结构性排除“假设为真”样本的 admission rule；
- 哪些 insight 应保留，哪些标准应降级为 report-only、pilot 或 future work。

## 6. Formal synthesis 的输出

正式方案应明确：

```text
Owner decisions
Product outcome
Science questions
Accepted insights and rejected proposals
Implementation scope / non-scope
Local source and resource facts
Admission / stopping / release criteria
Fallback or typed terminal states
Artifact and handoff requirements
```

“综合”不是取平均值。保留最强 insight，同时删除无法执行、无法观测或证据等级不匹配的 gate。
