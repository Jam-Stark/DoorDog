# Legacy coding-role adapter

本文件只为仍会读取 `.github/instructions/*.instructions.md` 的 legacy client 保留，不再定义独立 workflow。

Canonical policy 是 repository root `AGENTS.md`。复杂 Codex multi-agent 协作由 root policy 显式 route 到 `.codex/TEAM.md` 与 `.codex/contracts/`；memory routing 从 root `MEMORY.md` 开始。

Legacy client 必须遵守 root policy 中的 fail-fast、PF1/PF2/PF3、user approval、shared-filesystem lease、review、memory single-writer 与 Main-only Git gate。若无法执行这些 gate，应 fail fast 并报告 capability gap，不得使用本文件中的旧行为作为 fallback。
