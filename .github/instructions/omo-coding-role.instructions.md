# Legacy OMO adapter

本文件仅保留 OpenCode/OMO legacy discovery compatibility，不再维护 OMO-specific agent/category/workflow 定义。

Repository root `AGENTS.md` 是唯一 canonical coding policy。Codex-native team state machine 与 contracts 位于 `.codex/TEAM.md`、`.codex/contracts/`；project facts/progress 从 root `MEMORY.md` route。

若 legacy OMO surface 参与任务，它必须映射到 root policy 的相同 gates：fail-fast、Plan + explicit user Approval、single writer/path、frozen-candidate independent review、review PASS 后 memory single-writer、Main-only Git、no push。无法可靠映射时返回 capability blocker，不得复制或恢复旧的线性 workflow。
