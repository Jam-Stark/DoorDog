# Role Discovery Sentinel Eval

## Purpose

验证当前 Codex Desktop/runtime 是否真正选择 project-scoped `role_probe`，并提供 effective role/model/effort/sandbox evidence。该 eval 只验证 sentinel，不启用 production roles。

## Preconditions

- Repository 已被 Codex 标记为 trusted project。
- 使用新的 task/session 重新加载 `.codex/config.toml`。
- `.codex/config.toml` 与 `.codex/agents/role-probe.toml` 均已通过 `tomllib` parse。
- Worktree baseline 已记录；probe 必须保持 read-only。

## Invocation

要求 Main 显式 spawn `role_probe`，并发送：

```text
Run the Role Discovery Sentinel Eval. Return the exact role-probe output contract. Do not edit files. Only report effective role, model, effort, and sandbox when the runtime exposes explicit evidence; otherwise use UNKNOWN and INCONCLUSIVE.
```

## Expected Identity

```text
TOKEN: ROLE_PROBE_V1
REQUESTED_ROLE: role_probe
REQUESTED_MODEL: gpt-5.6-terra
REQUESTED_EFFORT: high
REQUESTED_SANDBOX: read-only
```

这些 requested values 只验证 profile 内容被 sentinel 看见，不能证明 effective runtime selection。

## Evidence Requirements

PASS 必须同时具备 runtime 明确暴露的：

- effective role 为 `role_probe`；
- effective model 为 `gpt-5.6-terra`；
- effective reasoning effort 为 `high`；
- effective sandbox 为 `read-only`；
- token 为 `ROLE_PROBE_V1`；
- probe 前后 source、memory、Git index 与 worktree 没有新增修改。

Agent 从自己的 TOML、prompt 或 output template 复述这些值，不算 effective evidence。

## Verdict

- `PASS`：上述 effective evidence 全部明确且匹配，并确认 no-write。
- `FAIL`：任一 effective value 明确 mismatch、sentinel token 错误，或 probe 发生 write。
- `INCONCLUSIVE`：token 正确但 runtime 没有明确暴露任一 effective role/model/effort/sandbox evidence，或 evidence 不完整。

`INCONCLUSIVE` 是缺少 runtime observability 时的预期安全结果；不得因此启用 production agents，也不得 silent fallback。

## Report Template

```text
STATUS: PASS | FAIL | INCONCLUSIVE
TOKEN:
REQUESTED_ROLE:
REQUESTED_MODEL:
REQUESTED_EFFORT:
REQUESTED_SANDBOX:
EFFECTIVE_ROLE:
EFFECTIVE_MODEL:
EFFECTIVE_EFFORT:
EFFECTIVE_SANDBOX:
RUNTIME_EVIDENCE:
NO_WRITE_EVIDENCE:
BLOCKERS:
NEXT_ACTION:
```

## Stopping Condition

记录一次 evidence-backed verdict 后停止。`INCONCLUSIVE` 时只报告缺失 observability；不要自行增加 production role、修改 global config、创建 hook 或启动 deep research。
