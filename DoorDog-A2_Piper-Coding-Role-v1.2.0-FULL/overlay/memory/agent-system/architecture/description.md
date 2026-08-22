---
name: codex-agent-system-architecture
scope: repository-wide AI workflow and runtime coordination
status: jam_coding_role_v1_2_0_current_static_pass_runtime_not_run
last_updated: 2026-08-22 HKT
evidence_level: STATIC_PASS; RUNTIME_NOT_RUN
owned_paths:
  - AGENTS.md
  - .ai/
  - .codex/AGENTS.md
  - .codex/TEAM.md
  - .codex/hooks.json
  - .omo/AGENTS.md
  - .omo/omo.jsonc
  - opencode.json
  - CLAUDE.md
  - .claude/settings.json
  - memory/agent-system/architecture/
---

## Current architecture

- Jam Coding Role v1.2.0 separates universal behavior、DoorDog project facts、workflow、runtime adapters、team state、memory governance、long-run continuity and artifact handoff.
- Codex MultiAgentV2 keeps Main `/root` as the sole control plane while allowing direct sibling `send_message` / `followup_task` communication for bounded technical information.
- Coordination state is stored in a Git-ignored SQLite/JSON ledger. Named agents require a registered task contract before spawn.
- Candidate freezes and scoped verdicts support targeted re-review and conservative invalidation.
- All agents actively propose memory candidates; Main or `memory_curator` may create、move、split、merge、supersede or retire canonical entries.
- Long runs use named tmux、run receipts、checkpoint/eval finalizers and pending events. No claim is made that an external process can always revive an ended Main turn.
- `Pro_Space` is an Owner-approved public-writer, create-only artifact target with allowlist、secret scan、checkpoint opt-in and unique release namespaces.
- OMO retains its own ordinary delegation and Team Mode lifecycle. Standalone Claude Code is single-agent.
- `.codex/config.toml` and `.codex/agents/*.toml` remain project-owned and were intentionally not replaced by the workflow migration.

## Evidence boundary

This entry records a static workflow migration. It does not prove a production Codex P2P session、OMO team run、IsaacLab runtime、training、Google Drive upload or hardware behavior.
