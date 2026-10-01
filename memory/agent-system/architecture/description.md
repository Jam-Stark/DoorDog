---
name: codex-agent-system-architecture
scope: repository-wide AI workflow and authority model
status: v1_5_0_installed_static_pass_runtime_unverified
last_updated: 2026-09-23 14:02 HKT
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

## Purpose

Record Jam Coding Role v1.5.0 for DoorDog, with explicit Owner configuration overrides.

## v1.5.0 当前配置

- 默认与 default 角色为 GPT-6 Sol/medium，并发上限 5；Main 保留 516000/464400、total，model/effort 由 App 选择。其余按 v1.5.0 角色分工，唯一 Astra/medium deep_researcher；新增 semantic_worker，共 12 角色。
- 配额/outbox 使用本地持久状态，完整 team coordination 仍按需；通信合同和事件直接比较文本，不生成内容指纹。临时工具按进程身份与逻辑任务归属管理。
- 静态预检 STATIC_PASS；4 个 worktree 用户 hooks 已同步注册。新 hook 实际拦截、当前 App effective config、Main 间通信、模型切换与工具进程回收均未执行运行验收；旧角色 context/compact 生效缺陷没有宣称修复。未启动测试矩阵、训练或模型任务。
- 源码入口：`.ai/MODEL_ROUTING.md`、`.ai/SESSION_PROTOCOL.md`、`.ai/TOOL_LIFECYCLE.md`；本机记录：`.ai/runtime/v150/LOCAL_ACCEPTANCE.json`。

## v1.4.0 历史升级

- 按 Owner 提供的交付包更新 27 个 DoorDog workflow 文件；Main model/effort 继续由用户选择，context/compact 保持 516000/464400。
- 十一角色显式设置 model、最高 high effort、独立 context/compact 和 total scope；新委托使用 `fork_turns="none"`。
- Supervisor 保存绝对 ETA，分离 process/acceptance，自动写完成 outbox，显式 ack 后归档。
- 遵守 Owner 禁止哈希要求：不使用包内安装器；删除 command/source 摘要字段，memory 候选按规范化字段直接去重，ID 使用 UUID。
- 新 supervisor 不兼容 v1.3 receipt/CLI。v26/v27 已关闭的历史 callers 不在此次迁移范围，不能直接用新版 helper 重启；当前 v28 无该依赖。原脚本随迁移备份保留。
- 本机证据与限制见 `.ai/runtime/workflow-v140/` 和 runtime-compatibility entry。没有训练、硬件、外部仓库、commit/push 或 idle wake 交付。

## Current decisions

- FAST and ordinary STANDARD tasks use Main or a small focused set of agents without mandatory full team ledger、candidate freeze、memory curator or artifact handoff. v1.5.0 child allocation still requires the small quota ledger before delegation.
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

## v1.5.0 通用源与分支同步

2026-09-23 14:11 HKT — 本地 AI_things 通用源与 7 个活跃 DoorDog 工作树已同步，保留研究内容和长任务设施；各目标静态预检通过、worktree hooks 注册完成。仍为工作树修改，未 commit/push；精确清单 `.ai/runtime/v150/SYNC_SUMMARY.md`。
