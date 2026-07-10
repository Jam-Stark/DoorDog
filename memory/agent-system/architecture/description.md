---
name: codex-agent-system-architecture
scope: repository-wide Codex multi-agent foundation and authority model
status: active
last_updated: 2026-07-11 01:19 HKT
evidence_level: STATIC FOUNDATION PASS
owned_paths:
  - AGENTS.md
  - .codex/TEAM.md
  - .codex/contracts/
  - memory/agent-system/architecture/
---

## Purpose

记录 DoorDog Codex multi-agent foundation 的 canonical authority、shared-filesystem coordination 与 rollout boundary。

## Verified Decisions

- Root `AGENTS.md` 是 repo-wide canonical policy；`.codex/AGENTS.md` 只自然作用于 `.codex` subtree。
- `.codex/TEAM.md` 与 `.codex/contracts/` 定义 Main-only scope/approval/lease/Git authority、single-writer path lease、最多 Main + 3 children 的 independent lanes、frozen manifest candidate、multi-lane review、memory single-writer 与 commit gate。
- Phase 0A/1 只包含 project config、contracts/eval 与 `ROLE_PROBE_V1` sentinel。Production role catalog、deep-research TOML、hooks 与 parallel writers 均 disabled。
- Root policy 与 foundation files 已完成 static review；此结论不证明 runtime role activation。

## TODO Summary

- 2026-07-11 01:19 HKT - 只有 runtime sentinel activation PASS 且取得 separate user approval 后，才设计并 rollout production role catalog/evals；在此之前保持 production roles、deep execution、hooks 与 parallel writers disabled。

## DONE Summary

- 2026-07-11 01:19 HKT - 完成 Codex-native root `AGENTS.md`、`.codex/TEAM.md`、contracts 与 Phase 0A/1 rollout boundary；static foundation review PASS，未声称 runtime activation PASS。
