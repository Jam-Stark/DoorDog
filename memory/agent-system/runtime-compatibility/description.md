---
name: codex-agent-runtime-compatibility
scope: project config parsing, current standalone-agent schema, and concrete runtime model compatibility
status: current_schema_static_pass_luna_user_confirmed
last_updated: 2026-08-17 16:31 HKT
evidence_level: STATIC_PASS; LUNA_USER_CONFIRMED; GENERAL_RUNTIME_NOT_RUN
owned_paths:
  - .codex/config.toml
  - .codex/agents/
  - memory/agent-system/runtime-compatibility/
---

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
