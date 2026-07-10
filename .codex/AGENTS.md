# `.codex` Local Policy

本文件只作用于 `.codex/` subtree。它不会替代 repository root 的 `AGENTS.md`，也不得被解释为 project code 的独立 policy source。

## Read Order

维护 `.codex/` 中的配置、contracts 或 eval 前，按以下顺序读取：

1. `../AGENTS.md`：repo-wide canonical policy，包括 approval、fail-fast、memory、review 与 commit gate。
2. `TEAM.md`：Codex multi-agent architecture、authority、waves、lease、candidate freeze 与 closure contract。
3. 与当前改动直接相关的 `contracts/*.md` 或 `evals/*.md`。

发生冲突时，repository root `AGENTS.md` 优先；将冲突报告给 user，不自行弱化 root gate。

## Scope Rules

- Main 是唯一 scope、approval、file/resource lease 与 Git authority。
- Custom agent 不得自行 stage、commit、push、扩大 `WRITE_SET` 或修改 acceptance criteria。
- Shared filesystem 上同一路径同一时刻只能有一个 writer；不得覆盖 user 或其他 agent 的 dirty work。
- Product code/config 改动继续遵循 root `AGENTS.md` 的 Plan → Approval → Implement → Review → Memory Update 流程。
- Canonical memory 是 durable project state，不是 live agent message bus；只由获授权的 memory writer 在 review PASS 后更新。
- 缺少明确 evidence 时使用 `INCONCLUSIVE`，不得把 requested profile、静态解析或 agent 自述当作 runtime PASS。
- Model、effort 或 role selection 不允许 silent fallback。发生 mismatch 时 fail fast 并交回 Main。

## Phase 0A Boundary

当前 `.codex/agents/` 只允许 `role-probe.toml` sentinel。不要在没有新的 approved rollout task 时创建 production role TOML、deep-research role、hook 或 recursive delegation 配置。
