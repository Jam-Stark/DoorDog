# Sim2sim merge readiness

Last updated: 2026-08-17 17:49 HKT

## Boundary

All owned changes are additive. The branch must not modify any path already tracked by `A2_Piper` except by a later explicit owner decision.

Forbidden shared production paths include:

- `gr00t/rl/envs/door/door_open_a2_base.py`
- `gr00t/rl/trl/trainer/`
- existing shared configs under `gr00t/rl/config/`
- `scriptsFORhuman/a2_piper_longterm_TODO.md`
- `memory/a2-piper/MEMORY.md`

## Added paths

- `scriptsFORhuman/sim2sim/PROGRESS.md`
- `scriptsFORhuman/sim2sim/MERGE_READINESS.md`
- `scriptsFORhuman/sim2sim/source_map.md`
- `scriptsFORhuman/sim2sim/branch_snapshot.json`
- `scriptsFORhuman/sim2sim/contract_unknowns.md`
- `scriptsFORhuman/sim2sim/decisions/local_ai_decision_log.yaml`

This list is updated after each phase.

## Mainline synchronization

| Phase | Sim2sim commit before merge | `A2_Piper` merged | Result | Behind after merge |
|---|---|---|---|---|
| Phase 0 | base `45c9decb` | `45c9decb` | already up to date | 0 |

## Non-intersection proof

Final proof will compare `git diff --name-status A2_Piper...HEAD` against the forbidden list once, after the final narrow runtime proof. No reverse merge into the dirty original worktree is performed by this session.
