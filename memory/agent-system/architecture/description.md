---
name: codex-agent-system-architecture
scope: repository-wide Codex multi-agent foundation and authority model
status: phase2_bounded_behavior_pass_general_runtime_inconclusive
last_updated: 2026-07-11 04:40 HKT
evidence_level: STATIC/STRICT PASS; BOUNDED RUNTIME BEHAVIOR PASS; GENERAL RUNTIME INCONCLUSIVE
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
- Phase 2 R3 对九个 non-Deep role 的 bounded positive contract behavior、direct child-to-peer FINDING 与 identical Main mirror、tested child-owned snapshots、C1-C4 lease/interrupt behavior 均取得 PASS evidence；这不等于 general runtime、full-tree write safety 或 effective metadata PASS。
- Frozen candidate `3e9f39a30b051631b8a1133cd9453271537d01b87a6b18b7000184c48292a98c` 的 Goal/Code/IsaacLab content review 均 PASS，`runtime_qa` 仅为 `STATIC_PASS`。真正 simultaneous three-reviewer wave 因第三 lane 出现 unexplained `agent thread limit reached` 而为 INCONCLUSIVE；IsaacLab runtime/training NOT_RUN。

## TODO Summary

- 2026-07-11 04:40 HKT - 获取 authoritative effective role/model/effort/sandbox metadata；诊断并重测 true simultaneous three-reviewer concurrency；在 isolated/stable environment 重跑不排除 externally-mutated paths 的 full-tree write safety；按 route 完成 hooks capability assessment。Deep 保持 dormant，只有 exact separate approval 后才可调用。

## DONE Summary

- 2026-07-11 01:19 HKT - 完成 Codex-native root `AGENTS.md`、`.codex/TEAM.md`、contracts 与 Phase 0A/1 rollout boundary；static foundation review PASS，未声称 runtime activation PASS。
- 2026-07-11 02:50 HKT - 按 user 明确批准完成 Phase 2 direct registration：新增九个 production profiles、十角色 registry、parallel routing 与五组 eval contracts；candidate `571e40ab8824f00244c5da586d880f6394d8bdb2c53e3d834e75f6533713b18f` 经独立 review PASS，validation level 为 STATIC PASS + strict startup PASS，未声称 production role runtime PASS。
- 2026-07-11 04:40 HKT - Phase 2 R3 验证九个 non-Deep role 的 bounded positive contract behavior、direct peer FINDING/Main mirror、tested child snapshots 与 C1-C4 write-lease/interrupt behavior PASS；candidate `3e9f39a30b051631b8a1133cd9453271537d01b87a6b18b7000184c48292a98c` content review PASS、QA ceiling 为 `STATIC_PASS`。因 `logs_rl/` 被批准排除，general full-tree write safety 保持 INCONCLUSIVE；true simultaneous three-reviewer wave 亦为 INCONCLUSIVE，effective metadata UNKNOWN，IsaacLab runtime/training NOT_RUN。`memory_curator` 已完成 exact 12-file atomic delta 与 self-validation；Main independent revalidation 仍是 closure gate。
