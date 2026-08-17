# Sim2sim merge readiness

Last updated: 2026-08-17 19:09 HKT

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
- `gr00t/rl/sim2sim/contracts/`
- `gr00t/rl/sim2sim/policy/`
- `gr00t/rl/sim2sim/schemas/student_policy_bundle.schema.json`
- `gr00t/rl/sim2sim/cli/export_student_policy_bundle.py`
- `gr00t/rl/sim2sim/cli/inspect_policy_bundle.py`
- `gr00t/rl/sim2sim/cli/produce_native_hydra_actor.py`
- `gr00t/rl/sim2sim/cli/replay_native_hydra_golden.py`
- `scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10/`
- `scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10_ready_r2/`
- `scriptsFORhuman/sim2sim/artifacts/e0/`
- `gr00t/rl/sim2sim/mujoco/`
- `gr00t/rl/sim2sim/robot/`
- `gr00t/rl/sim2sim/cli/build_a2_piper_mjcf.py`
- `gr00t/rl/sim2sim/cli/probe_e1_robot.py`
- `gr00t/rl/sim2sim/cli/render_axis_marker_probe.py`
- `gr00t/rl/data/mujoco/A2_Piper/`
- `scriptsFORhuman/sim2sim/artifacts/e1/`
- `gr00t/rl/sim2sim/doors/`
- `gr00t/rl/sim2sim/cli/build_mjcf_door.py`
- `gr00t/rl/sim2sim/cli/probe_e2_door.py`
- `scriptsFORhuman/sim2sim/artifacts/door/`
- `scriptsFORhuman/sim2sim/artifacts/e2/`

This list is updated after each phase.

## Mainline synchronization

| Phase | Sim2sim commit before merge | `A2_Piper` merged | Result | Behind after merge |
|---|---|---|---|---|
| Phase 0 | base `45c9decb` | `45c9decb` | already up to date | 0 |
| Phase 1 / E0 | `2842df8` | `45c9decb` | already up to date | 0 |
| Phase 2 / E1 | `9e5659a` | `45c9decb` | already up to date | 0 |
| Phase 3 / E2 | `485a8f2` | `45c9decb` | already up to date | 0 |

## Non-intersection proof

Final proof will compare `git diff --name-status A2_Piper...HEAD` against the forbidden list once, after the final narrow runtime proof. No reverse merge into the dirty original worktree is performed by this session.
