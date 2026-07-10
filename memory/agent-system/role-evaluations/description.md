---
name: codex-agent-role-evaluations
scope: sentinel and ten-role production catalog evaluation
status: phase2_bounded_role_behavior_and_full_tree_wls_pass_remaining_evals_inconclusive
last_updated: 2026-07-11 05:11 HKT
evidence_level: STATIC/STRICT PASS; BOUNDED ROLE/COORDINATION BEHAVIOR PASS; FULL-TREE WRITE SAFETY PASS; GENERAL RUNTIME INCONCLUSIVE
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
- Phase 2 R3 中，`role_probe`、`scope_planner`、`context_researcher`、`isaaclab_worker`、`goal_reviewer`、`code_reviewer`、corrected `isaaclab_reviewer`、`runtime_qa` 的 bounded positive contract behavior PASS；`memory_curator` 完成获批的 exact 12-file atomic delta 与 self-validation。所有 effective metadata 均保持 `UNKNOWN/INCONCLUSIVE`。
- Direct child-to-peer FINDING 与 identical Main mirror PASS；tested child runner 与两份 identical child-owned snapshots PASS。R3 的 C1 single、C2 disjoint concurrent、C3 same-path serialization、C4 partial interrupt/audit/repair behavior PASS，但该轮排除 externally-mutated ignored `logs_rl/`，所以当时 general full-tree write safety 仍为 INCONCLUSIVE。
- P2-FULL-TREE-WLS-R1 在 training 结束且包含 `logs_rl/` 的 full tree 稳定后验证 C1 single、C2 disjoint simultaneous active、C3 strict same-path serialization 与 C4 running partial writer → interrupted terminal → Main partial audit → replacement 全部 PASS；zero out-of-lease change，exact cleanup 后 HEAD/worktree/index 与 same-encoding manifest 精确恢复，general full-tree write safety PASS。
- Candidate `3e9f39a30b051631b8a1133cd9453271537d01b87a6b18b7000184c48292a98c` 的 Goal/Code/IsaacLab content review PASS，`runtime_qa` 为 `STATIC_PASS`。真正 simultaneous three-reviewer wave 因第三 lane 的 unexplained `agent thread limit reached` 为 INCONCLUSIVE；IsaacLab runtime/training NOT_RUN，hooks NOT_RUN，Deep 未调用。

## TODO Summary

- 2026-07-11 05:11 HKT - 获取 authoritative effective role/model/effort/sandbox metadata；诊断 `agent thread limit reached` 并重测 true simultaneous three-reviewer wave；完成 hooks capability assessment。Deep runtime smoke 继续要求 exact separate approval。

## DONE Summary

- 2026-07-11 01:19 HKT - 创建 `ROLE_PROBE_V1` sentinel 与 `.codex/evals/role-discovery.md`，其 PASS/FAIL/INCONCLUSIVE 和 no-write evidence contract 已通过 static review；runtime activation 尚未 PASS。
- 2026-07-11 01:29 HKT - 执行 fresh trusted project-scoped sentinel eval：`ROLE_PROBE_V1` 与 requested Terra/high/read-only profile 返回，child sandbox `read-only` 得到 runtime evidence，outer manifest/no-index-change 提供 external no-project-write evidence；effective child role/model/effort 仍未知，最终 verdict 为 INCONCLUSIVE。
- 2026-07-11 02:50 HKT - 创建并注册九个 production profiles、十角色 truth table 与 role/parallel/write/hooks eval contracts；static matrix、strict startup 与 independent candidate review PASS。Production role runtime behavior、parallel coordination、write safety 与 hooks capability 均保持 NOT_RUN。
- 2026-07-11 04:40 HKT - Phase 2 R3 验证九个 non-Deep role 的 bounded positive contract behavior（含 `memory_curator` exact 12-file delta self-validation）、direct peer FINDING/Main mirror、tested child snapshots 与 C1-C4 behavior PASS。Candidate `3e9f39a30b051631b8a1133cd9453271537d01b87a6b18b7000184c48292a98c` content review PASS、QA ceiling 为 `STATIC_PASS`；true simultaneous three-reviewer wave 与 general full-tree write safety 为 INCONCLUSIVE，effective metadata UNKNOWN，IsaacLab runtime/training、hooks、Deep 均 NOT_RUN。Main independent memory revalidation 仍是 closure gate。
- 2026-07-11 05:11 HKT - P2-FULL-TREE-WLS-R1 在包含稳定 `logs_rl/` 的 full tree 上完成 C1 single、C2 disjoint simultaneous active、C3 strict same-path serialization、C4 partial interrupt/Main audit/replacement；zero out-of-lease change，exact cleanup 后 HEAD/worktree/index 与 same-encoding manifest 精确恢复，general full-tree write safety PASS。Effective metadata、true simultaneous three-reviewer wave、hooks 与 IsaacLab runtime/training 结论未改变；Main independent memory revalidation 仍是 closure gate。
