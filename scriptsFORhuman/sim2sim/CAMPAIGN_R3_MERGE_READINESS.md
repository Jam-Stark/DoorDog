# Campaign r3 merge readiness

Last updated: 2026-08-18 01:03 HKT

## Boundary result

r3 remains additive and does not modify the paired manifest, paired schema, distillation handoff, shared task/trainer/config files, long-term TODO, or routed memory index.

## Added source paths

- `gr00t/rl/sim2sim/cli/run_constraint_gate_r3.py`
- `gr00t/rl/sim2sim/cli/run_diagnostic_ladder_r3.py`
- `gr00t/rl/sim2sim/cli/extract_r2_proprio_l1.py`

## Added evidence and documentation paths

- `scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10_ready_r2/manifest_payload_correction_r3.json`
- `scriptsFORhuman/sim2sim/artifacts/e5/constraint_gate_r3/`
- `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_diagnostic_r3/`
- `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_diagnostic_r3_resolved_effort/`
- `scriptsFORhuman/sim2sim/artifacts/e5/r3_owner_adjudication.json`
- `scriptsFORhuman/sim2sim/CAMPAIGN_R3_DIAGNOSTIC_REPORT.md`
- `scriptsFORhuman/sim2sim/CAMPAIGN_R3_PROGRESS.md`
- `scriptsFORhuman/sim2sim/CAMPAIGN_R3_MERGE_READINESS.md`
- `memory/a2-piper/sim2sim-r3-diagnostic/`

## Mainline synchronization

`A2_Piper` at closure is `b38f5f013771e8121080a301337ea72d00bc030e`, an ancestor of this branch. Every completed r3 phase merged it and reported `Already up to date`; behind is 0.

## Forbidden-path proof target

The final one-pass boundary check must show no changes to:

- `gr00t/rl/envs/door/door_open_a2_base.py`
- `gr00t/rl/trl/trainer/`
- existing shared configs under `gr00t/rl/config/`
- `scriptsFORhuman/a2_piper_longterm_TODO.md`
- `memory/a2-piper/MEMORY.md`
- paired manifest/schema and distillation handoff files

No reverse merge, push, stash, reset, or write to `/home/baoquanc/workspace/DoorDog-A2_Piper` was performed.
