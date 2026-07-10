---
name: codex-agent-role-evaluations
scope: ROLE_PROBE_V1 sentinel and production-role activation gate
status: runtime_inconclusive
last_updated: 2026-07-11 01:29 HKT
evidence_level: STATIC REVIEW PASS; SENTINEL RUNTIME INCONCLUSIVE; EXTERNAL NO-PROJECT-WRITE PASS
owned_paths:
  - .codex/agents/role-probe.toml
  - .codex/evals/role-discovery.md
  - memory/agent-system/role-evaluations/
---

## Purpose

记录 `ROLE_PROBE_V1` sentinel/eval contract、PASS 条件与 production rollout gate。

## Verified Evidence and Decisions

- `role_probe` 是 Phase 0A/1 唯一 agent role，requested profile 为 `gpt-5.6-terra` / `high` / `read-only`。
- `.codex/evals/role-discovery.md` 要求 explicit effective role/model/effort/sandbox、token 与 Git/worktree no-write evidence；requested profile 或 self-report 不算 effective evidence。
- Sentinel 与 eval contract 已创建并完成 static review PASS。
- Fresh trusted project-scoped strict session 中，第一次 spawn request 失败且未创建 thread；随后恰好一个 project `role_probe` 成功返回 `ROLE_PROBE_V1` 与 requested profile。
- Runtime 只明确暴露 child sandbox `read-only`；effective child role/model/effort 为 `UNKNOWN`，因此 role-discovery verdict 是 `INCONCLUSIVE`，production roles 保持 disabled。
- Outer Main 的 before/after full candidate manifest 均为 `b6f6777436abff87284b061d77cdf4db4b99262705ee80ab3a31be90d38e0c8b`，Git index 为空，构成 external no-project-write evidence。Child-owned snapshot 因 `bwrap` loopback error 未取得。

## TODO Summary

- 2026-07-11 01:29 HKT - 当 runtime 暴露 effective child role/model/effort 且 child read-only runner 可用时，重跑 role-discovery eval 并取得 child-owned no-write snapshot；完整 activation PASS 前保持 production role rollout disabled。

## DONE Summary

- 2026-07-11 01:19 HKT - 创建 `ROLE_PROBE_V1` sentinel 与 `.codex/evals/role-discovery.md`，其 PASS/FAIL/INCONCLUSIVE 和 no-write evidence contract 已通过 static review；runtime activation 尚未 PASS。
- 2026-07-11 01:29 HKT - 执行 fresh trusted project-scoped sentinel eval：`ROLE_PROBE_V1` 与 requested Terra/high/read-only profile 返回，child sandbox `read-only` 得到 runtime evidence，outer manifest/no-index-change 提供 external no-project-write evidence；effective child role/model/effort 仍未知，最终 verdict 为 INCONCLUSIVE。
