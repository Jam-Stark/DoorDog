# Sim2sim merge readiness

Last updated: 2026-08-18 11:35 HKT

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
- `gr00t/rl/sim2sim/mujoco/scene_builder.py`
- `gr00t/rl/sim2sim/doors/metrics.py`
- `gr00t/rl/sim2sim/cli/build_shadow_scene.py`
- `gr00t/rl/sim2sim/cli/run_e3_open_loop.py`
- `scriptsFORhuman/sim2sim/artifacts/e3/`
- `gr00t/rl/sim2sim/policy/observations.py`
- `gr00t/rl/sim2sim/cli/run_e4_rgb_closed_loop.py`
- `scriptsFORhuman/sim2sim/artifacts/e4/`
- `gr00t/rl/sim2sim/evaluation/`
- `gr00t/rl/sim2sim/cli/build_e5_paired_receipt.py`
- `scriptsFORhuman/sim2sim/artifacts/e5/`
- `gr00t/rl/sim2sim/cli/run_e6_robustness.py`
- `scriptsFORhuman/sim2sim/artifacts/e6/`

This list is updated after each phase.

### r4 additions

- `gr00t/rl/sim2sim/{mujoco,doors,cli}/*r4.py` and `mujoco/stage_contract_minimal.py`
- `scriptsFORhuman/sim2sim/artifacts/e5/{stage_contract_r4,qacc_localization_r4,standing_vitals_gate_r4,visual_parity_r4,paired_mujoco_campaign_r4}/`
- `scriptsFORhuman/sim2sim/CAMPAIGN_R4_{REPORT,PROGRESS,MERGE_READINESS}.md`
- `memory/a2-piper/sim2sim-r4-campaign/`

The owner-requested `t=0` Isaac RGB requirement is appended to the branch-owned paired distillation handoff. The paired manifest and paired row schema remain unchanged.

The original E0–E6 file inventory is `scriptsFORhuman/sim2sim/CHANGED_FILES.txt`; the additive r4 inventory is recorded separately in `scriptsFORhuman/sim2sim/CAMPAIGN_R4_MERGE_READINESS.md`.

## Mainline synchronization

| Phase | Sim2sim commit before merge | `A2_Piper` merged | Result | Behind after merge |
|---|---|---|---|---|
| Phase 0 | base `45c9decb` | `45c9decb` | already up to date | 0 |
| Phase 1 / E0 | `2842df8` | `45c9decb` | already up to date | 0 |
| Phase 2 / E1 | `9e5659a` | `45c9decb` | already up to date | 0 |
| Phase 3 / E2 | `485a8f2` | `45c9decb` | already up to date | 0 |
| Phase 4 / E3 | `ad8b1f3` | `45c9decb` | already up to date | 0 |
| Phase 5 / E4 | `c5e1194` | `45c9decb` | already up to date | 0 |
| Phase 6 / E5 | `78ff837` | `45c9decb` | already up to date | 0 |
| Phase 7 / E6 | `ba2d304` | `45c9decb` | already up to date | 0 |
| Phase 8 / closure | `24430d6` | `45c9decb` | already up to date | 0 |

### r4 synchronization

| Phase | Sim2sim commit before merge | Result | Behind after merge |
|---|---|---|---:|
| pre-r4 mainline sync | `a3ace7e` | merged A2_Piper | 0 |
| P1 stage contract | `ab65398` | already up to date | 0 |
| P2 true 100/45 | `ca8abe7` | already up to date | 0 |
| P3 visual parity | `536e6b0` | already up to date | 0 |
| P4 campaign | `ab82c51` | already up to date | 0 |
| receipt classification correction | `5389ef6` | already up to date | 0 |

## Non-intersection proof

Final proof compares `git diff --name-status A2_Piper...HEAD` against the forbidden list once after the closure commit. Expected changed roots are only:

- `gr00t/rl/sim2sim/`
- `gr00t/rl/data/mujoco/A2_Piper/`
- `scriptsFORhuman/sim2sim/`
- `memory/a2-piper/sim2sim-shadow-evaluator/`

Forbidden intersections must be empty. No reverse merge into the dirty original worktree is performed by this session.

The original owner package under `/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/sim2sim/` was read-only reference. This worktree's identically named additive evidence directory is branch-owned and does not modify a path tracked by base `A2_Piper`.
