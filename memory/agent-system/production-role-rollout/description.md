---
name: codex-production-role-rollout
scope: Phase 2 registered production catalog and runtime rollout
status: selector_gate_pass_three_role_matrix_verified_full_rollout_pending
last_updated: 2026-07-13 16:25 HKT
evidence_level: STATIC/STRICT PASS; APP SELECTOR GATE PASS; THREE-ROLE MATRIX PASS; BOUNDED PRODUCTION BEHAVIOR PASS; FULL-TREE WRITE SAFETY PASS; FULL ROLE MATRIX PENDING
owned_paths:
  - .codex/config.toml
  - .codex/agents/
  - .codex/evals/
  - memory/agent-system/production-role-rollout/
---

## Purpose

记录 production role model/permission matrix、direct registration decision、parallel waves 与后续 runtime safety gates。

## Verified Decisions

- Registry 包含 `role_probe` 与九个 production roles：`scope_planner`、`context_researcher`、`deep_researcher`、`isaaclab_worker`、`goal_reviewer`、`code_reviewer`、`isaaclab_reviewer`、`runtime_qa`、`memory_curator`。
- Main 使用 Sol/xhigh；planning/review 使用 Sol xhigh/max，research/QA/memory 使用 Terra/high，implementation 使用 Luna/max；Deep 是唯一 Sol/Ultra exception。
- Runtime capacity target 为 Main + 最多 5 active children；default wave 为 3。Main 对 sibling dependency、frozen input、writer `WRITE_SET`/output 与 resource lease 完成 independence proof 后，可自主扩展到 5；overlap 始终串行。
- Direct registration 是 user 明确决定；effective child metadata 未暴露时保持 `UNKNOWN/INCONCLUSIVE`，不允许 false runtime/model PASS。
- Deep registered-but-dormant，每次 invocation 重新批准；write-safety runtime eval 与 hook implementation 也需要 separate approval。
- Phase 2 R3 验证九个 non-Deep roles 的 bounded positive contract behavior、direct child-to-peer FINDING/Main mirror、tested child snapshots 与 C1-C4 lease/interrupt behavior PASS。该 evidence 不授权 scope、lease 或 authority transfer，也不证明 effective metadata。
- Frozen candidate `3e9f39a30b051631b8a1133cd9453271537d01b87a6b18b7000184c48292a98c` 的 Goal/Code/IsaacLab content review PASS，`runtime_qa` 仅为 `STATIC_PASS`；true simultaneous three-reviewer wave 因第三 lane 的 unexplained `agent thread limit reached` 为 INCONCLUSIVE。
- Approved R3 排除了 externally-mutated ignored `logs_rl/`，因此该轮 C1-C4 behavior PASS 当时不能提升为 general full-tree write-safety PASS。
- P2-FULL-TREE-WLS-R1 在 training 结束且包含 `logs_rl/` 的 full tree 稳定后验证 C1 single、C2 disjoint simultaneous active、C3 strict same-path serialization 与 C4 running partial writer → interrupted terminal → Main partial audit → replacement 全部 PASS；zero out-of-lease change，exact cleanup 后 HEAD/worktree/index 与 same-encoding manifest 精确恢复，general full-tree write safety PASS。Effective role/model/effort/sandbox 保持 `UNKNOWN/INCONCLUSIVE`；IsaacLab runtime/training NOT_RUN。
- 2026-07-13 merged MultiAgentV2 config使 App fresh-task selector surface可用。Four selector controls PASS，explicit `role_probe/scope_planner/isaaclab_worker` 分别解析到 Terra/high、Sol/xhigh、Luna/max；selector gate解除。Effective permission受 parent live override统一为 `danger-full-access/never`，profile sandbox defaults未证明。
- Production rollout当前 verdict为 `SELECTOR_GATE_PASS / UNBLOCKED`，不是 full rollout PASS；九个 non-Deep roles explicit-selector contract matrix、true simultaneous reviewer wave、hooks与未覆盖 sandbox eval仍需完成，Deep继续 dormant。

## TODO Summary

- 2026-07-13 01:05 HKT - 完成九个 non-Deep roles explicit-selector contract matrix与未覆盖 sandbox-default eval；诊断并重测 true simultaneous three-reviewer concurrency；完成 hooks capability assessment。Deep保持 dormant，仅在 exact separate approved brief 下运行。
- 2026-07-13 16:25 HKT - 在 fresh App task 运行 default 3 / independence-proven expanded 5 的 read-only coordination eval，验证 effective capacity、active-count accounting 与缺少 proof 时不扩展；完成前保持 `NOT_RUN`。

## DONE Summary

- 2026-07-11 02:50 HKT - 完成十角色 direct registry、九个 production profiles、role truth table 与 Phase 2 orchestration/eval contracts；candidate `571e40ab8824f00244c5da586d880f6394d8bdb2c53e3d834e75f6533713b18f` static/strict startup/independent review PASS，runtime evals 未运行。
- 2026-07-11 04:40 HKT - Phase 2 R3 验证九个 non-Deep role bounded positive contract behavior（含 `memory_curator` exact 12-file delta self-validation）、direct peer FINDING/Main mirror、tested child snapshots 与 C1-C4 behavior PASS；candidate `3e9f39a30b051631b8a1133cd9453271537d01b87a6b18b7000184c48292a98c` content review PASS、QA ceiling 为 `STATIC_PASS`。True simultaneous three-reviewer wave 与 general full-tree write safety 保持 INCONCLUSIVE，effective metadata UNKNOWN，IsaacLab runtime/training、hooks、Deep NOT_RUN；Main independent memory revalidation 仍是 closure gate。
- 2026-07-11 05:11 HKT - P2-FULL-TREE-WLS-R1 在包含稳定 `logs_rl/` 的 full tree 上完成 C1 single、C2 disjoint simultaneous active、C3 strict same-path serialization、C4 partial interrupt/Main audit/replacement；zero out-of-lease change，exact cleanup 后 HEAD/worktree/index 与 same-encoding manifest 精确恢复，general full-tree write safety PASS。Effective metadata、true simultaneous three-reviewer wave、hooks 与 IsaacLab runtime/training 结论未改变；Main independent memory revalidation 仍是 closure gate。
- 2026-07-13 01:05 HKT - App fresh-task selector controls与三角色 matrix runtime PASS，merged namespace/metadata config已验证；selector gate UNBLOCKED。Parent permission override与结论 ceiling已记录；full nine-role rollout、sandbox defaults、reviewer concurrency、hooks与Deep仍未完成。
- 2026-07-13 16:25 HKT - 将 production wave policy 从 hard ceiling 3 修正为 default 3 / independence-proven maximum 5，并保持 writer `WRITE_SET`/artifact/resource lease gate；parallel-coordination eval 已扩展为 Main+3 与 Main+5 两种 case，runtime `NOT_RUN`。
