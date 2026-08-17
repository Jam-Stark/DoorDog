# Role Discovery Sentinel Eval

## Purpose

验证当前 Codex Desktop/runtime 对 project-scoped `role_probe` 的 effective role/model/effort/sandbox 与 no-write observability。该 eval 只评估 metadata evidence，不控制已经 user-approved 的 Phase 2 profile registration 或 Main-controlled routing。

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

`INCONCLUSIVE` 是缺少 runtime observability 时的预期安全结果：它表示不能声称 effective model/effort/sandbox 或相关 runtime PASS。它不会 unregister、删除或要求停用已经 user-approved 的 registered profiles，但仍禁止 silent fallback 与虚假 metadata claim。

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

记录一次 evidence-backed metadata verdict 后停止。`INCONCLUSIVE` 时只报告缺失 observability，保持 registered catalog 与 ordinary routing 不变；不要修改 global config、创建 hook、启动 deep research、运行未批准 write eval、删除或禁用 registered role。
