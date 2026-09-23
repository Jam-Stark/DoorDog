---
name: codex-agent-system-architecture
scope: repository-wide AI workflow and authority model
status: v1_4_0_installed_host_verification_partial
last_updated: 2026-09-12 17:58 HKT
evidence_level: STATIC_PASS; TEST_PASS; LOCAL_HELPER_RUNTIME_PASS; APP_HOOKS_UNVERIFIED
owned_paths:
  - AGENTS.md
  - .ai/
  - .codex/AGENTS.md
  - .codex/TEAM.md
  - .codex/hooks.json
  - .omo/AGENTS.md
  - opencode.json
  - CLAUDE.md
  - memory/agent-system/architecture/
---

## Purpose

Record Jam Coding Role v1.4.0 for DoorDog: a lean default workflow with optional coordination facilities.

## v1.4.0 本地升级

- 按 Owner 提供的交付包更新 27 个 DoorDog workflow 文件；Main model/effort 继续由用户选择，context/compact 保持 516000/464400。
- 十一角色显式设置 model、最高 high effort、独立 context/compact 和 total scope；新委托使用 `fork_turns="none"`。
- Supervisor 保存绝对 ETA，分离 process/acceptance，自动写完成 outbox，显式 ack 后归档。
- 遵守 Owner 禁止哈希要求：不使用包内安装器；删除 command/source 摘要字段，memory 候选按规范化字段直接去重，ID 使用 UUID。
- 新 supervisor 不兼容 v1.3 receipt/CLI。v26/v27 已关闭的历史 callers 不在此次迁移范围，不能直接用新版 helper 重启；当前 v28 无该依赖。原脚本随迁移备份保留。
- 本机证据与限制见 `.ai/runtime/workflow-v140/` 和 runtime-compatibility entry。没有训练、硬件、外部仓库、commit/push 或 idle wake 交付。

## Current decisions

- FAST and ordinary STANDARD tasks use Main or a small focused set of agents without mandatory ledger、disk contract、candidate freeze、memory curator or artifact handoff.
- HIGH_RISK is an approval overlay for destructive/external/hardware/expensive or difficult-to-reverse work; it does not force a fixed review pipeline.
- Codex MultiAgentV2 P2P is retained. Technical facts may flow directly between peers; authority remains with Main.
- Team state is inactive by default. It is activated only for multiple writers、exclusive resources、cross-session DAG、formal review/QA or verdict dependency.
- Contracts apply only to controlled tasks while coordination is active. Read-only agents and ordinary spawns do not receive leases.
- Candidate freeze applies to formal review/QA or otherwise ambiguous candidates, not normal implementation.
- Memory curation is triggered by a durable verified candidate or real routing debt. It is not a closure ceremony.
- Long-run receipts and tmux may be used independently of the full team ledger for a single authorized run.
- Artifact bundling/upload occurs only when Owner or the stage contract explicitly enables handoff.
- Root `AGENTS.md` is a route table. Optional documents are not a full-reading checklist.
- Git commits require explicit authorization in the current task. Migration tooling defaults to no commit and no push.

## Evidence boundary

This entry records the static workflow migration. It does not claim a production Codex P2P session、OMO Team Mode run、IsaacLab simulation、training、Google Drive upload or hardware validation.
