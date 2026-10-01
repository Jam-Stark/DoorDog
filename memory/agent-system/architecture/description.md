---
name: codex-agent-system-architecture
scope: repository-wide AI workflow and authority model
status: v1_5_0_static_pass_runtime_not_run
last_updated: 2026-09-23 14:11 HKT
evidence_level: STATIC_PASS; USER_HOOKS_REGISTERED; V150_RUNTIME_NOT_RUN
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

## v1.5.0 当前同步状态

workflow v1.5.0 已同步：默认/default 为 GPT-6 Sol/medium，子任务并发 5，Main context/compact 516000/464400、total；Main model/effort 由 App 选择。共 12 个角色，唯一 Astra/medium deep_researcher。

本分支静态预检 STATIC_PASS，4 个 worktree hooks 已同步注册；新 hook 信任与实际拦截、effective config、双 Main 通信、模型切换及工具回收均未运行验收。旧证据不自动升级为 v1.5.0 runtime PASS；旧长任务脚本/收据与研究内容保持原样。

来源与备份：`.ai/WORKFLOW_SYNC.md`。以下历史配置/结论仅为旧版本记录，当前配置以本节和实际 source 为准。

## 先前版本记录


## Purpose

Record Jam Coding Role v1.3.0 for DoorDog: a lean default workflow with optional coordination facilities.

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
