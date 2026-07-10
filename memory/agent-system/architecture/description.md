---
name: codex-agent-system-architecture
scope: repository-wide Codex multi-agent foundation and authority model
status: phase2_registered
last_updated: 2026-07-11 02:50 HKT
evidence_level: PHASE 2 STATIC PASS; STRICT STARTUP PASS; ROLE RUNTIME NOT_RUN
owned_paths:
  - AGENTS.md
  - .codex/TEAM.md
  - .codex/contracts/
  - .codex/agents/
  - .codex/evals/
  - memory/agent-system/architecture/
---

## Purpose

记录 DoorDog Codex multi-agent foundation 的 canonical authority、shared-filesystem coordination 与 rollout boundary。

## Verified Decisions

- Root `AGENTS.md` 是 repo-wide canonical policy；`.codex/AGENTS.md` 只自然作用于 `.codex` subtree。
- `.codex/TEAM.md` 与 `.codex/contracts/` 定义 Main-only scope/approval/lease/Git authority、single-writer path lease、最多 Main + 3 children 的 independent lanes、frozen manifest candidate、multi-lane review、memory single-writer 与 commit gate。
- User 明确批准绕过旧 activation blocker，Phase 2 直接注册九个 production profiles 与 `role_probe`；registration 可用于 routing，但不证明 effective child role/model/effort。
- Discovery/review 默认并发最多三个 children；多个 `isaaclab_worker` 只允许 provably disjoint `WRITE_SET` 与 resource lease，overlap 必须串行。
- `deep_researcher` 已注册但 dormant-by-policy，每次 invocation 仍需 exact separate approval；hooks 尚未配置。
- Candidate `571e40ab8824f00244c5da586d880f6394d8bdb2c53e3d834e75f6533713b18f` 完成两轮 targeted fix 后 independent review PASS。Runtime role、parallel、write-safety 与 hooks eval 尚未运行。

## TODO Summary

- 2026-07-11 02:50 HKT - 依次执行九个 non-Deep role contract cases、parallel coordination 与另行批准的 write-safety eval；完成 hooks capability assessment，Deep 只在 exact per-invocation approval 后调用。

## DONE Summary

- 2026-07-11 01:19 HKT - 完成 Codex-native root `AGENTS.md`、`.codex/TEAM.md`、contracts 与 Phase 0A/1 rollout boundary；static foundation review PASS，未声称 runtime activation PASS。
- 2026-07-11 02:50 HKT - 按 user 明确批准完成 Phase 2 direct registration：新增九个 production profiles、十角色 registry、parallel routing 与五组 eval contracts；candidate `571e40ab8824f00244c5da586d880f6394d8bdb2c53e3d834e75f6533713b18f` 经独立 review PASS，validation level 为 STATIC PASS + strict startup PASS，未声称 production role runtime PASS。
