# Campaign r4 merge readiness

Last updated: 2026-08-18 11:35 HKT

## Boundary result

r4 adds sim2sim-only modules, evidence, reports, and one new unrouted memory entry. It does not modify shared door task/trainer/config production files, the long-term TODO, the routed memory index, paired manifest, or paired schema. The sole pre-existing branch-owned content edit is the owner-requested mandatory `t=0` RGB paragraph in `artifacts/e5/paired_case_manifest/DISTILLATION_HANDOFF.md`.

## Added source paths

- `gr00t/rl/sim2sim/mujoco/stage_contract_minimal.py`
- `gr00t/rl/sim2sim/mujoco/native_position_r4.py`
- `gr00t/rl/sim2sim/mujoco/policy_visual_scene_r4.py`
- `gr00t/rl/sim2sim/doors/mjcf_builder_r4.py`
- `gr00t/rl/sim2sim/cli/probe_stage_contract_r4.py`
- `gr00t/rl/sim2sim/cli/localize_qacc_r4.py`
- `gr00t/rl/sim2sim/cli/run_standing_vitals_gate_r4.py`
- `gr00t/rl/sim2sim/cli/probe_visual_parity_r4.py`
- `gr00t/rl/sim2sim/cli/run_paired_mujoco_campaign_r4.py`

## Added evidence and documentation roots

- `scriptsFORhuman/sim2sim/artifacts/e5/stage_contract_r4/`
- `scriptsFORhuman/sim2sim/artifacts/e5/qacc_localization_r4/`
- `scriptsFORhuman/sim2sim/artifacts/e5/standing_vitals_gate_r4/`
- `scriptsFORhuman/sim2sim/artifacts/e5/visual_parity_r4/`
- `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r4/`
- `scriptsFORhuman/sim2sim/CAMPAIGN_R4_REPORT.md`
- `scriptsFORhuman/sim2sim/CAMPAIGN_R4_PROGRESS.md`
- `scriptsFORhuman/sim2sim/CAMPAIGN_R4_MERGE_READINESS.md`
- `memory/a2-piper/sim2sim-r4-campaign/`

## Mainline synchronization

`A2_Piper` at r4 closure is an ancestor of this branch. Every completed phase merged it and reported behind 0. No reverse merge into the original worktree is performed.

## Forbidden-path proof target

The one final boundary check must show no r4 changes to:

- `gr00t/rl/envs/door/door_open_a2_base.py`
- `gr00t/rl/trl/trainer/`
- existing shared configs under `gr00t/rl/config/`
- `scriptsFORhuman/a2_piper_longterm_TODO.md`
- `memory/a2-piper/MEMORY.md`
- `scriptsFORhuman/sim2sim/artifacts/e5/paired_case_manifest/paired_case_manifest.json`
- `gr00t/rl/sim2sim/schemas/paired_trace_row.schema.json`

No push, stash, reset, or write to `/home/baoquanc/workspace/DoorDog-A2_Piper` was performed.
