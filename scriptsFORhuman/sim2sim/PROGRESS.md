# DoorDog MuJoCo shadow evaluator progress

Last updated: 2026-08-17 17:49 HKT

## Scope and authority

- Worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_sim2sim`
- Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`
- Mainline source: local branch `A2_Piper`
- Original worktree `/home/baoquanc/workspace/DoorDog-A2_Piper` is read-only; it contains active v24 work and the owner-supplied sim2sim design package.
- This branch only adds isolated sim2sim implementation/evidence paths. Shared production files, `door_open_a2_base.py`, trainers, shared configs, `scriptsFORhuman/a2_piper_longterm_TODO.md`, and `memory/a2-piper/MEMORY.md` are outside the write boundary.

## Evidence ladder

| Level | State | Current evidence |
|---|---|---|
| E0 Contract / golden | IN_PROGRESS | Production source and Student checkpoint reconnaissance started. |
| E1 Robot | IN_PROGRESS | Repository URDF and A2_Base policy assets located; MJCF not built yet. |
| E2 Door | IN_PROGRESS | v24 unit/friction source and door-generator path under trace; builder not built yet. |
| E3 Open-loop | NOT_STARTED | Requires E0 action transform plus compiled robot/door. |
| E4 Closed-loop proprio/pixel | NOT_STARTED | Requires E0 policy runtime and camera contract. |
| E5 Paired cases | NOT_STARTED | Requires comparable independent backend traces. |
| E6 Robustness | NOT_STARTED | Requires at least one interpretable E4/E5 path. |

Missing evidence is typed and is never filled with zero.

## Phase log

### Phase 0 — source reconnaissance (complete)

- Confirmed current worktree and `A2_Piper` both start at commit `45c9decb0080e07e7e3941a9c9b0a176d6bb24b0`.
- Confirmed distillation branch `codex/a2-v13-student-distillation-20260717_2103` at `a197255212fa65dd9e02337b7971daac71c944fe`; merge base with `A2_Piper` is `4b29411101a1de4949f42140b61f1ccb4c2e67e7`, left/right counts `106/32`.
- Read the routed memory plus owner audit and the package documents in README order. Owner R1-R10 are treated as fixed decisions.
- Located repository assets `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf`, `gr00t/rl/data/policies/A2_Base/policy.pt`, and `policy_metadata.json`.
- Resolved the exact production 54D frame/history, name-based leg remap, 12→19→20 action path, delta update/reset, and v24 three-face mechanics/friction receipt contracts into `source_map.md`.
- Selected the formal GRPO step10 Student checkpoint and its adjacent config from recorded fixed-G2 evidence; traced the production strict `policy_state_dict` loader. Native runtime export remains an E0 execution item, not a source ambiguity.
- Preserved the checkpoint-adjacent legacy gripper gains `80/3/10` as a source gap while applying the owner-resolved evaluated face `1300/32/45` for MuJoCo control.
- No GPU was leased.

Phase-completion merge record: local `A2_Piper` was already at the worktree base; merge result is recorded in `MERGE_READINESS.md`.

## Next action

Freeze the source map and unknowns, then implement the additive schemas/contracts/validator/exporter and golden harness before any policy-driven physics claim.
