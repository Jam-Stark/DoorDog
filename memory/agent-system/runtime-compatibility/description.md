---
name: codex-agent-runtime-compatibility
scope: project config parsing, current standalone-agent schema, and concrete runtime model compatibility
status: v1_5_0_static_pass_runtime_not_run
last_updated: 2026-09-23 14:11 HKT
evidence_level: STATIC_PASS; USER_HOOKS_REGISTERED; V150_RUNTIME_NOT_RUN
owned_paths:
  - .codex/config.toml
  - .codex/agents/
  - memory/agent-system/runtime-compatibility/
---

## v1.5.0 当前同步状态

workflow v1.5.0 已同步：默认/default 为 GPT-6 Sol/medium，子任务并发 5，Main context/compact 516000/464400、total；Main model/effort 由 App 选择。共 12 个角色，唯一 Astra/medium deep_researcher。

本分支静态预检 STATIC_PASS，4 个 worktree hooks 已同步注册；新 hook 信任与实际拦截、effective config、双 Main 通信、模型切换及工具回收均未运行验收。旧证据不自动升级为 v1.5.0 runtime PASS；旧长任务脚本/收据与研究内容保持原样。

来源与备份：`.ai/WORKFLOW_SYNC.md`。以下历史配置/结论仅为旧版本记录，当前配置以本节和实际 source 为准。

## 先前版本记录


## Purpose

Track current project configuration facts and real runtime incompatibilities only. Do not create periodic model/role/sandbox probes.

## Current facts

- `.codex/config.toml` uses `[agents]` with `enabled`, `max_concurrent_threads_per_session`, `default_subagent_model`, `default_subagent_reasoning_effort`, and `interrupt_message`.
- The concurrency value is five spawned threads excluding Main, matching Main plus five.
- Eight standalone custom-agent files define explicit name, description, developer instructions, model/effort, and sandbox mode and parse as TOML.
- Generic children are Terra/high. Terra implementation/review roles are high. Luna research/runtime roles are high; only bounded memory curation remains medium.
- The user confirms the current machine accepts Luna subagents. Luna is an ordinary supported route in this project; no compatibility fallback or catalog patch is required.
- The obsolete feature block, duplicate registry, role probe, contracts, evals, and rollout matrices were removed from the active tree.

## Runtime policy

- Use Luna normally in real work. Do not run a special smoke or metadata matrix merely to reconfirm it.
- If a future real invocation fails, record the exact build and concrete error once, report it, and decide a targeted change. Do not silently substitute another model.
- Static parse does not prove simulation, runtime smoke, or training behavior; those remain `NOT_RUN` until they occur as part of real work.

## TODO summary

- No compatibility TODO. Create one only after a concrete future runtime failure.

## DONE summary

- 2026-08-17 16:31 HKT - Migrated to current `[agents]` and standalone custom-agent schema, raised generic Terra and Luna code/runtime roles to high, recorded user-confirmed Luna availability, and parsed the replacement configuration. Runtime spawning was not separately probed.
