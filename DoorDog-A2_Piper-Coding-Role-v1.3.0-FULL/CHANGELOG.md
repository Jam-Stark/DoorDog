# Jam Coding Role v1.3.0 — Adaptive Coordination

## Summary

v1.3.0 keeps the portable behavior kernel and advanced coordination capabilities from v1.2.0, but changes the default from persistent workflow infrastructure to a lean, route-triggered model.

## Added

- FAST / STANDARD / HIGH_RISK routing with explicit activation rules.
- Independent control-facility trigger matrix for ledger、lease、freeze、verdict、curator、long-run and artifact handoff.
- Lazy team-state activation with `adaptive` and `strict` modes.
- `team_state.py status/activate/deactivate/hook-check-spawn` commands.
- Explicit `--confirm-stage-handoff` requirement for artifact packing/upload.
- Opt-in migration Git flags: `--checkpoint-commit` and `--migration-commit`, plus `--confirm-user-authorized-commit` for actual Git writes.

## Changed

- Root `AGENTS.md` is now a route table. Only core documents are read by default; optional documents are conditional.
- Ordinary Codex spawns no longer require a disk-backed task contract.
- Codex hooks are no-op while coordination is inactive and do not create runtime state.
- Team ledger is no longer a prerequisite for FAST or ordinary STANDARD tasks.
- Candidate freeze is limited to formal review/QA, ambiguous dirty/shared candidates or cross-session review.
- Leases are limited to actual concurrent writers or exclusive resources; read-only agents are not leased.
- Memory curator is candidate-triggered rather than a closure stage.
- Artifact handoff is explicit rather than automatic at task completion.
- OMO Team Mode defaults to disabled.
- OpenCode and Claude preload only the core routing files.
- A single authorized long run may use a receipt/tmux without activating the full team ledger.

## Preserved

- Codex MultiAgentV2 P2P communication.
- Main-only authority for scope、acceptance、resources、Git and final integration.
- Standalone Claude Code single-agent routing.
- OMO official ordinary delegation and Team Mode semantics.
- Active memory restructuring capability.
- Pro_Space create-only artifact target.
- Chinese native-language expression rules.
- Claim-matched scientific evidence and hardware safety boundaries.

## Git behavior

The migration tool defaults to no commits. A checkpoint commit and migration commit are created only when the caller supplies explicit flags under current Owner authorization. The tool never pushes.
