# READY r2 campaign merge readiness

## Boundary

Task-owned changes are additive and confined to:

- `gr00t/rl/sim2sim/cli/{materialize_paired_case_manifest.py,run_paired_mujoco_campaign.py,compare_paired_campaign.py}`
- `gr00t/rl/sim2sim/mujoco/paired_scene_builder.py`
- `gr00t/rl/sim2sim/schemas/paired_trace_row.schema.json`
- `scriptsFORhuman/sim2sim/CAMPAIGN_*`
- `scriptsFORhuman/sim2sim/artifacts/e5/paired_case_manifest/`
- `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r1/`
- `memory/a2-piper/sim2sim-paired-campaign/`

No `door_open_a2_base.py`, trainer, shared config, `BaseSimulator`, Isaac production hook, `scriptsFORhuman/a2_piper_longterm_TODO.md`, or `memory/a2-piper/MEMORY.md` index was edited by this campaign.

## Mainline merges

Every completed phase ran `git merge A2_Piper`. All but the renderer-fix phase were already up to date. During that phase, local `A2_Piper` advanced to `b38f5f0`; merge commit `ce0dc9a` absorbed its canonical `AGENTS.md` change. That line is mainline-owned and disappears from the task-only diff against current `A2_Piper`; it is not a campaign edit or conflict.

Current expected state at handoff: behind `0`, local campaign commits only, no push.

## Evidence

- Manifest materialization validates 8/8 `DoorInstanceSpec` objects and aligned friction semantics.
- READY r2 native actor strict load completed on CPU.
- Full terminal campaign completed 8/8 cases with 408 finite JSONL rows and 408/408 torque clips.
- Formal comparator schema-validated every MuJoCo row.
- Actual asset screenshot was rendered by MuJoCo under non-accelerated llvmpipe.
- E5 missing Isaac input remains typed and comparison remains `null`.

The only remaining action is data-driven: when the user supplies the matching Isaac trace root, run the committed comparator and add `e5_formal_report.json` without changing production code.
