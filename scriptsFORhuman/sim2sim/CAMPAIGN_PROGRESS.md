# READY r2 paired full-campaign progress

Worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_sim2sim`  
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`

## Phase log

- Schema phase: introduced the 200 Hz paired JSONL row contract at `0e82607`, then corrected mixed revolute/prismatic target and effort unit names before campaign use. Final schema authority is `2bf0ac417858128ab761fca3fa3aa8451b7ea843`; phase merges returned `Already up to date`, behind `0`.
- Manifest materializer phase: added the explicit legacy-door subset materializer through commit `37d56bf`; each phase merge returned `Already up to date`, behind `0`.
- Case-set phase: materialized eight fixed-seed DoorInstanceSpecs under `artifacts/e5/paired_case_manifest/`. All use `tau_static=tau_dynamic=0`, `no_latch`, and only the distillation `door.py` exact-field surface.
- Runtime implementation phase: added a no-latch paired scene composer and the READY r2 full-episode CPU campaign runner at `2bf0ac4`; `git merge A2_Piper` returned `Already up to date`, behind `0`.
- Comparator phase: added the schema-aligned E5 campaign comparator at `264f26b`; `git merge A2_Piper` returned `Already up to date`, behind `0`.
- Renderer fix phase: the first overview request exceeded the MJCF 640 px offscreen width before any trace row. Commit `3340ef9` fixed the screenshot to 640×480. The mandatory phase merge absorbed mainline `b38f5f0` as merge commit `ce0dc9a`; behind returned to `0`.
- Full campaign phase: eight terminal episodes completed on CPU llvmpipe with 104 policy decisions, 408 finite physics rows, and 408/408 torque clips. All terminal reasons are `BASE_HEIGHT`; all absent unlatch/open events remain typed. Artifacts were committed at `b160367`; phase merge was already up to date.
- E5 materialization: the comparator validated all 408 MuJoCo rows. Isaac input is absent, so the current report is `EXPLORATORY_NON_COMPARABLE / BLOCKED_INPUT_ISAAC_PAIRED_TRACE` with `comparison=null`.

## Remaining external input

- Receive the matching Isaac trace directory from the user and run the committed comparator to produce `e5_formal_report.json`.
