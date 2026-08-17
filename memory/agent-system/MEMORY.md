# Codex Agent System Memory

This subsystem records the active repository-wide Codex workflow and concrete runtime compatibility facts. It is durable knowledge, not a live task ledger, heartbeat, mailbox, or recurring audit program.

## Active entries

- [architecture/description.md](architecture/description.md): current lean Codex multi-agent policy, role routing, direct communication, implementation-first flow, effort matrix, and review limits.
- [runtime-compatibility/description.md](runtime-compatibility/description.md): current project config schema, user-confirmed Luna availability, and concrete future compatibility evidence.

The previous role-evaluation and production-rollout entries were removed because they described an obsolete probe/contract/eval workflow. Git history and the pre-migration tag are the archive; future agents must not treat historical gates as active requirements.

## Evidence rules

- `STATIC_PASS` proves parse and internal consistency only.
- The user confirms the current machine accepts Luna subagents; use Luna normally without a probe lane.
- Record a future incompatibility only when a real invocation produces a concrete error. Do not run periodic role, model, sandbox, or metadata matrices.
- Memory updates use one `YYYY-MM-DD HH:MM HKT` timestamp across `description.md`, `TODO.md`, and `DONE.md`.
