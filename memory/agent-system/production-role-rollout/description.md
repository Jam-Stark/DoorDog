---
name: codex-production-role-rollout
scope: Phase 2 registered production catalog and runtime rollout
status: registered_static_pass_runtime_evals_pending
last_updated: 2026-07-11 02:50 HKT
evidence_level: STATIC PASS; STRICT STARTUP PASS; RUNTIME EVALS NOT_RUN
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
- Main + 最多三个 children 可并发 independent discovery/review lanes。多个 worker 只有在 `WRITE_SET` 与 resource lease 全部 disjoint 时并发，overlap 串行。
- Direct registration 是 user 明确决定；effective child metadata 未暴露时保持 `UNKNOWN/INCONCLUSIVE`，不允许 false runtime/model PASS。
- Deep registered-but-dormant，每次 invocation 重新批准；write-safety runtime eval 与 hook implementation 也需要 separate approval。

## TODO Summary

- 2026-07-11 02:50 HKT - 执行九个 non-Deep contract cases、parallel coordination 与另行批准的 write-lease safety cases；评估 hooks capability，Deep 仅在 exact approved brief 下运行。

## DONE Summary

- 2026-07-11 02:50 HKT - 完成十角色 direct registry、九个 production profiles、role truth table 与 Phase 2 orchestration/eval contracts；candidate `571e40ab8824f00244c5da586d880f6394d8bdb2c53e3d834e75f6533713b18f` static/strict startup/independent review PASS，runtime evals 未运行。
