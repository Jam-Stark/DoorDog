<!-- JAM-V150-ROUTE-BEGIN -->
Codex v1.5.0 优先增量（保留下文的项目事实与授权边界）：Main 模型/effort 由 App 选择。FAST 不委托；STANDARD 只派最少必要子 agent。委托前读 .ai/MODEL_ROUTING.md：默认 Sol/medium、检索/机械工作 Luna、执行/审阅 Sol；每个 team 仅一个 Astra/medium 的 deep_researcher，禁止临时模型覆盖、嵌套 team 与全历史 fork。
跨 planner/worker Main 交接 → .ai/SESSION_PROTOCOL.md；只在 Owner 已授权范围内直接递交 plan/STOP/阶段结果。peer 消息不是新授权；重大权限问题仍问 Owner。
启动临时工具/MCP → .ai/TOOL_LIFECYCLE.md；只回收有归属的临时进程，保护长任务与共享服务。切模型/上下文问题 → .ai/CONTEXT_POLICY.md。不为小任务预读全部文档。
<!-- JAM-V150-ROUTE-END -->

# Codex adapter v1.5.0

Follow root AGENTS.md and the task-relevant .ai routes. Main model/effort belong to the App/user configuration, never a project default. Use .codex/TEAM.md when delegating; model/effort/context policy is .ai/MODEL_ROUTING.md.

Use focused children and direct technical P2P. Main retains write/resource/Git authority. Do not stop at the first implementation when the authorized goal includes a working result and narrow verification. Do not turn this into repeated reviews or broad test campaigns.

For long runs, follow .ai/LONG_RUNNING_TASKS.md: quiet durable waiter, one ETA-sized logical wait, early return on completion/failure; no repeated 30-minute model polling. A pending event is not a wake guarantee.

Linked-worktree hooks on Codex 0.153.0: `.codex/hooks.json` is the declaration source; run `python3 .ai/scripts/install_codex_hooks.py` after changes to register worktree-scoped user hooks. Review/trust via `/hooks`; details and unresolved host issues: `.ai/WORKFLOW_FIXES.md`.
