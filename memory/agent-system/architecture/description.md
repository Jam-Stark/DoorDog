---
name: codex-agent-system-architecture
scope: repository-wide Codex multi-agent workflow and authority model
status: lean_current_schema_static_pass_runtime_not_run
last_updated: 2026-08-17 16:31 HKT
evidence_level: STATIC_PASS; RUNTIME_NOT_RUN
owned_paths:
  - AGENTS.md
  - .codex/AGENTS.md
  - .codex/TEAM.md
  - .codex/config.toml
  - .codex/agents/
  - memory/agent-system/architecture/
---

## Purpose

Record the active lean Codex multi-agent workflow for DoorDog. This entry replaces the previous contract/frozen-candidate/eval-heavy workflow.

## Current decisions

- Current project config uses documented `[agents]` settings. Five spawned threads are allowed in addition to Main; generic children default to Terra/high.
- Standalone `.codex/agents/*.toml` files are the role-definition source. The old feature table, duplicate role registry, role probe, contracts, evals, and rollout gates are not active.
- Active roles are `scope_planner`, `context_researcher`, `deep_researcher`, `isaaclab_worker`, `code_reviewer`, `isaaclab_reviewer`, `runtime_qa`, and `memory_curator`.
- Main is Sol/high. Terra/high handles ordinary planning, implementation, and code review. Luna/high handles repository/API research and runtime proof interpretation. Luna/medium is reserved for mechanical memory curation. Sol/high handles rare IsaacLab semantic review; Sol/Ultra is explicit deep research.
- Routine work is implementation-first: minimal memory, real-path trace, smallest end-to-end implementation, one narrow existing proof, one Main diff/path check, then user report.
- Review/QA/curation are trigger-driven, not mandatory stages. One concern has one owner for one pass; a reviewer returns at most three blocking findings.
- Task IDs, revisions, frozen candidates, manifests, recurring metadata probes, contract matrices, and default review waves were removed.
- Direct messages carry bounded peer questions/findings/handoffs. Only material scope, ownership, model/cost, blocker, and integration decisions are mirrored to Main.
- One path/resource has one writer. Parallelism is favored for read-heavy work and clearly disjoint writers.
- Independent tool calls are batched. Long waits use one appropriate barrier/sleep; runs over 30 minutes use a named detached tmux session.
- No new tests, compatibility, guardrails, mutation coverage, or speculative defensive handling are added before the user confirms implemented behavior unless a concrete failure requires one targeted check.

## TODO summary

- No scheduled audit or eval. Add a targeted TODO only after a concrete workflow defect is observed.

## DONE summary

- 2026-08-17 16:31 HKT - Migrated to the lean current standalone-agent workflow, selectively raised Terra/Luna code and runtime roles to high, retained medium only for mechanical memory curation, removed obsolete audit infrastructure, and statically parsed the replacement TOML. Runtime spawning, simulation, and training were not run by the migration.
