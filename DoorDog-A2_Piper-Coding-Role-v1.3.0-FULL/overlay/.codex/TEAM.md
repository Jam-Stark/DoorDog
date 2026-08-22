# DoorDog Codex MultiAgentV2 workflow v1.3

## Lean default

FAST and ordinary STANDARD work use Main or a small focused set of agents with prompt-level boundaries. Persistent team state is OFF by default.

Project roles remain those registered in `.codex/agents/*.toml`. Model/effort/concurrency remain in `.codex/config.toml`.

## P2P

Use direct sibling communication for exact API evidence、runtime signatures、reproduction commands、targeted defects and dependency-ready notices. Peers act only within existing assignments.

Use structured `PEER_FINDING` / `PEER_REQUEST` / `AUTHORITY_REQUEST` only when it improves routing or traceability. Main alone changes scope、acceptance、revision、WRITE_SET、exclusive resources、Git or hard stops.

## When to activate coordination state

Activate `.ai/TEAM_STATE.md` only for:

- multiple writers;
- exclusive GPU/IsaacSim/display/port/hardware/output resources;
- cross-session DAG;
- formal review/runtime QA with an exact candidate;
- verdict invalidation after narrow fixes.

```bash
python .ai/scripts/team_state.py activate --mode adaptive --reason "..."
```

A read-only researcher or simple worker spawn does not require a disk contract. In `strict` mode, controlled writer/reviewer/runtime roles require one.

## Candidate freeze

Freeze only for formal review/QA or ambiguous dirty/shared worktrees. Ordinary implementation and temporary QA do not create revisions or verdict objects.

## Review and QA

Review is trigger-driven and concern-specific. One concern has one owner. A narrow fix invalidates only bound verdicts. Runtime QA runs the smallest command that can establish the requested runtime claim.

## Long jobs

A single authorized long run may use `.ai/LONG_RUNNING_TASKS.md` without the full ledger. Add leases when runs or agents compete for exclusive resources.

## Closure

No mandatory curator、freeze、artifact or team-state step. Close active agents/resources and deactivate coordination if it was enabled.
