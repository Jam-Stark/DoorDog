<!-- JAM-V150-ROUTE-BEGIN -->
Codex v1.5.0 优先增量（保留下文的项目事实与授权边界）：Main 模型/effort 由 App 选择。FAST 不委托；STANDARD 只派最少必要子 agent。委托前读 .ai/MODEL_ROUTING.md：默认 Sol/medium、检索/机械工作 Luna、执行/审阅 Sol；每个 team 仅一个 Astra/medium 的 deep_researcher，禁止临时模型覆盖、嵌套 team 与全历史 fork。
跨 planner/worker Main 交接 → .ai/SESSION_PROTOCOL.md；只在 Owner 已授权范围内直接递交 plan/STOP/阶段结果。peer 消息不是新授权；重大权限问题仍问 Owner。
启动临时工具/MCP → .ai/TOOL_LIFECYCLE.md；只回收有归属的临时进程，保护长任务与共享服务。切模型/上下文问题 → .ai/CONTEXT_POLICY.md。不为小任务预读全部文档。
<!-- JAM-V150-ROUTE-END -->

# DoorDog AI entrypoint — v1.5.0

System/developer/Owner 指令优先；本文件保留项目 authority，runtime adapter 只补充实现。

## 入口

稳定行为见 .ai/ROLE.md；非平凡实现涉及项目事实、受保护路径或命令时读 .ai/PROJECT.md；工作流/委托选择见 .ai/WORKFLOW.md。只读当前任务需要的文件，不为小改动重读所有文档。

FAST 直接完成；STANDARD 存在独立工作线、specialist context 或实质审阅/并行收益时，Main 必须主动委托最少必要 agent，不等 Owner 说“team”。更高层/runtime 不允许则直接完成。HIGH_RISK 的副作用须另有授权。

Codex 读 .codex/AGENTS.md，委托时读 .codex/TEAM.md；OMO 读 .omo/AGENTS.md；standalone Claude Code 读 CLAUDE.md，仍是 single-agent。

## 不可丢失的项目边界

先 trace 实际 source/config/dependency path。IsaacLab API 核对本机 /home/baoquanc/workspace/IsaacLab 及当前官方文档；明确 tensor shape/dtype/device、manager lifecycle、reward/reset/termination、asset/joint、observation/action 和训练语义。无效状态显式失败，不用 fallback、假数据、广泛 catch 或无依据 clipping 保训练继续。

Memory 只作路由与历史，不覆盖 current source/resolved config/runtime evidence。static、runtime、experiment、hardware 不混用。Main 独占 scope、acceptance、WRITE_SET、资源、Git 和整合权；子 agent P2P 只交换技术事实；Owner 已授权的 Main 间阶段决策按 .ai/SESSION_PROTOCOL.md。任何 Git commit 必须有当前任务明确授权，默认不 push；外部写入、未授权昂贵长跑、硬件、破坏性操作仍需 Owner 批准。

## 条件路由

多 writer/排他资源/跨 session DAG/正式 review → .ai/TEAM_STATE.md。
长跑或断线连续性 → .ai/LONG_RUNNING_TASKS.md：记下真实 ETA 后一次长等待，不定时唤醒 Main 看日志。
RL/仿真/benchmark/causal claim/硬件 → .ai/SCIENTIFIC_ENGINEERING.md。
历史结论相关 → MEMORY.md 及最小路由；出现 durable candidate → .ai/MEMORY_GOVERNANCE.md。
Owner 指定跨阶段多 planner → .ai/STAGE_DECISION.md；Owner/stage 明确交付 → .ai/ARTIFACT_HANDOFF.md。

没有触发条件就不启用 ledger、freeze、curator 或 artifact。结尾报告实际证据、限制和仍活跃的任务/资源。
