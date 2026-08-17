# Campaign r2 merge readiness

Updated: 2026-08-17 23:18 HKT

## Scope

All task-owned paths are additive relative to `A2_Piper`. Changes are confined to:

- `gr00t/rl/sim2sim/cli/run_standing_vitals_gate.py`
- `gr00t/rl/sim2sim/cli/render_handle_parity_v2.py`
- `gr00t/rl/sim2sim/cli/run_paired_mujoco_campaign_r2.py`
- `gr00t/rl/sim2sim/doors/mjcf_builder_v2.py`
- `gr00t/rl/sim2sim/mujoco/actuator_map_v2.py`
- `gr00t/rl/sim2sim/mujoco/paired_scene_builder_v2.py`
- `scriptsFORhuman/sim2sim/artifacts/e5/handle_parity_v2/`
- `scriptsFORhuman/sim2sim/artifacts/e5/standing_vitals_gate_r1/`
- `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r2/`
- `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r2_attempt0_constant_frame/`
- `scriptsFORhuman/sim2sim/CAMPAIGN_R2_*.md`
- `memory/a2-piper/sim2sim-standing-vitals-r2/`

## Non-overlap proof

- The original `/home/baoquanc/workspace/DoorDog-A2_Piper` was read-only.
- No shared trainer, `door_open_a2_base.py`, shared config, paired manifest, paired schema, or distillation handoff was modified.
- r1 artifacts remain preserved; supersession is recorded only in new r2 reports.
- Every completed phase ran `git merge A2_Piper`; all returned `Already up to date` through runtime commit `83f176a`.
- Local commits only; no push.
