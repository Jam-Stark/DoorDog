---
name: codex-agent-role-evaluations
scope: sentinel and ten-role production catalog evaluation
status: phase2_static_pass_runtime_not_run
last_updated: 2026-07-11 02:50 HKT
evidence_level: STATIC REVIEW PASS; STRICT STARTUP PASS; PRODUCTION ROLE RUNTIME NOT_RUN
owned_paths:
  - .codex/agents/role-probe.toml
  - .codex/agents/
  - .codex/evals/role-discovery.md
  - .codex/evals/role-contracts.md
  - .codex/evals/role-contract-cases.toml
  - .codex/evals/parallel-coordination.md
  - .codex/evals/write-lease-safety.md
  - .codex/evals/hooks-capability.md
  - memory/agent-system/role-evaluations/
---

## Purpose

记录 `ROLE_PROBE_V1` sentinel、十角色 static contract 与后续 runtime/coordination/write/hooks eval 状态。

## Verified Evidence and Decisions

- Phase 2 registry 包含 `role_probe` 与九个 production roles；user 已批准 direct registration，metadata observability 不再阻断 ordinary routing。
- `.codex/evals/role-discovery.md` 要求 explicit effective role/model/effort/sandbox、token 与 Git/worktree no-write evidence；requested profile 或 self-report 不算 effective evidence。
- Sentinel 与 eval contract 已创建并完成 static review PASS。
- Fresh trusted project-scoped strict session 中，第一次 spawn request 失败且未创建 thread；随后恰好一个 project `role_probe` 成功返回 `ROLE_PROBE_V1` 与 requested profile。
- Runtime 只明确暴露 sentinel child sandbox `read-only`；effective child role/model/effort 仍为 `UNKNOWN`。该限制阻断 metadata PASS claim，但不撤销 user-approved registry。
- Outer Main 的 before/after full candidate manifest 均为 `b6f6777436abff87284b061d77cdf4db4b99262705ee80ab3a31be90d38e0c8b`，Git index 为空，构成 external no-project-write evidence。Child-owned snapshot 因 `bwrap` loopback error 未取得。
- `role-contract-cases.toml` 与十个 profiles/config matrix static PASS；Deep 是唯一 Sol/Ultra role，且从无逐次批准的 runtime smoke 中排除。
- Candidate `571e40ab8824f00244c5da586d880f6394d8bdb2c53e3d834e75f6533713b18f` independent review PASS；所有 production role runtime eval 仍为 NOT_RUN。

## TODO Summary

- 2026-07-11 02:50 HKT - 运行九个 non-Deep tool-free role contract cases与 parallel coordination eval；write-safety 需 separate approval，Deep runtime smoke 必须取得该次完整 approval brief，hooks 先完成 capability assessment。

## DONE Summary

- 2026-07-11 01:19 HKT - 创建 `ROLE_PROBE_V1` sentinel 与 `.codex/evals/role-discovery.md`，其 PASS/FAIL/INCONCLUSIVE 和 no-write evidence contract 已通过 static review；runtime activation 尚未 PASS。
- 2026-07-11 01:29 HKT - 执行 fresh trusted project-scoped sentinel eval：`ROLE_PROBE_V1` 与 requested Terra/high/read-only profile 返回，child sandbox `read-only` 得到 runtime evidence，outer manifest/no-index-change 提供 external no-project-write evidence；effective child role/model/effort 仍未知，最终 verdict 为 INCONCLUSIVE。
- 2026-07-11 02:50 HKT - 创建并注册九个 production profiles、十角色 truth table 与 role/parallel/write/hooks eval contracts；static matrix、strict startup 与 independent candidate review PASS。Production role runtime behavior、parallel coordination、write safety 与 hooks capability 均保持 NOT_RUN。
