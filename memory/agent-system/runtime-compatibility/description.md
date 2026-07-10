---
name: codex-agent-runtime-compatibility
scope: project-scoped config parsing, strict startup and runtime activation evidence
status: runtime_inconclusive
last_updated: 2026-07-11 02:50 HKT
evidence_level: PHASE 2 STATIC PASS; STRICT STARTUP PASS; RUNTIME INCONCLUSIVE
owned_paths:
  - .codex/config.toml
  - .codex/agents/role-probe.toml
  - .codex/agents/
  - .codex/evals/role-contract-cases.toml
  - memory/agent-system/runtime-compatibility/
---

## Purpose

区分 project config 的 static compatibility、Codex strict-config startup 与实际 custom-role activation。

## Verified Evidence

- `.codex/config.toml` 与 `.codex/agents/role-probe.toml` 可由 Python `tomllib` 解析，static parse PASS。
- Codex strict-config validation 已到达 startup/model invocation；这证明 config/schema/path 未在 startup parse 阶段失败。
- Usage 恢复后，一个 fresh trusted project-scoped strict session 以 Main `gpt-5.6-sol` / `high` / `read-only` 运行。第一次 spawn request 失败且没有创建 thread；随后恰好一个 project `role_probe` 成功返回。
- Sentinel 返回 `ROLE_PROBE_V1` 与 requested `gpt-5.6-terra` / `high` / `read-only` profile。Runtime 明确暴露 child sandbox 为 `read-only`，但 effective child role/model/effort 仍为 `UNKNOWN`，所以 activation verdict 是 `INCONCLUSIVE`。
- Child read-only command runner 因 `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` 无法生成自己的 before/after snapshot。
- Outer Main 独立重算 probe 前后完整 candidate manifest，两次均为 `b6f6777436abff87284b061d77cdf4db4b99262705ee80ab3a31be90d38e0c8b`，且 Git index 始终为空。这是 external no-project-write evidence，不是 child-owned snapshot。
- Phase 2 的 config、十个 agent profiles 与 role-contract truth table 共 12 个 TOML 通过 parse/matrix validation；本地 catalog 支持所配置的 Sol/Terra/Luna effort，且只有 Deep 使用 Ultra。
- Fresh strict-config startup 成功返回 `STRICT_PRODUCTION_CATALOG_V1`。该 evidence 证明 registry/schema 可加载，不证明任一 production child 的 effective model/effort。

## Decisions

- 不修改 global `~/.codex/config.toml`，不启用 silent fallback。
- User 已明确批准 direct registration/routing；effective child role/model/effort 未暴露时只限制 runtime metadata PASS claim，不撤销 registry。任何 explicit mismatch 必须 fail fast 调查。

## TODO Summary

- 2026-07-11 02:50 HKT - 执行九个 non-Deep role contract runtime cases并继续调查 effective child role/model/effort observability 与 `bwrap` child runner blocker；保持 metadata `UNKNOWN/INCONCLUSIVE`，任何 explicit mismatch fail fast。

## DONE Summary

- 2026-07-11 01:19 HKT - `.codex/config.toml` 与 `.codex/agents/role-probe.toml` 通过 Python `tomllib` static parse；Codex strict-config 到达 startup/model invocation。Sentinel 在 response 前被 usage limit 停止，所以没有 runtime activation 或 effective configuration/no-write PASS evidence。
- 2026-07-11 01:29 HKT - Fresh trusted strict session 成功运行一个 `ROLE_PROBE_V1` child，确认 child sandbox `read-only`；effective child role/model/effort 仍为 `UNKNOWN`。Outer Main 的 before/after manifest 均为 `b6f6777436abff87284b061d77cdf4db4b99262705ee80ab3a31be90d38e0c8b` 且 Git index 为空，提供 external no-project-write evidence；child-owned snapshot 被 `bwrap` loopback error 阻断，runtime verdict 保持 INCONCLUSIVE。
- 2026-07-11 02:50 HKT - Phase 2 的 `.codex/config.toml`、十个 agent profiles 与 `role-contract-cases.toml` 共 12 个 TOML 通过 parse/matrix validation；本地 model catalog 确认 Sol/Terra/Luna effort matrix，fresh strict-config startup 返回 `STRICT_PRODUCTION_CATALOG_V1`。未执行 production role runtime case，effective metadata 仍为 INCONCLUSIVE。
