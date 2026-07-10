# `.codex` Local Policy

本文件只作用于 `.codex/` subtree，不替代 repository root `AGENTS.md`。

## Read and Precedence

维护 `.codex` 前依次读取：

1. `../AGENTS.md`：repo-wide canonical policy。
2. `TEAM.md`：Phase 2 architecture、role routing、waves、leases、candidate 与 closure。
3. 当前改动相关的 `contracts/*.md` 与 `evals/*.md`。

发生冲突时 root `AGENTS.md` 优先；不得自行弱化 approval、fail-fast、memory、review 或 Main-only Git gate。

## Registered Catalog Maintenance

Phase 2 registry 必须保持 `.codex/config.toml`、`agents/<role>.toml`、`TEAM.md` role matrix、`evals/role-contract-cases.toml` 与相关 eval 同步。任何 role rename、model/effort/sandbox、mode、activation policy 或 config path 改动必须在同一 candidate 中更新全部对应项，并通过 TOML/path/matrix validation。

- Main 是唯一 scope、approval、lease、candidate、memory authorization 与 Git authority。
- Shared filesystem 同一路径同一 revision 只有一个 writer；same-path/resource conflict 串行。
- Static profile、requested values 或 agent self-report 不证明 effective child role/model/effort。Runtime 未暴露时写 `UNKNOWN/INCONCLUSIVE`，不得 silent fallback。
- Product code/config 继续执行 root 的 Plan → Approval → lease-bound implementation → frozen review → memory → Main commit gate。
- Canonical memory 不是 live message bus，只能在 required review PASS 后由获授权 `memory_curator` 原子更新。

## Prohibitions

- 不得未经 user approval 创建或启用 hook；当前 hooks 未配置，仅允许 capability eval。
- 不得因 `deep_researcher` 已注册而自行调用。每次 invocation 必须取得 exact separate approval brief；不得写文件、spawn child 或降级 Ultra。
- 不得修改 global `~/.codex/config.toml`。
- Child 不得 stage、commit、push、扩大 `WRITE_SET`、转移 lease 或修改 acceptance criteria。
