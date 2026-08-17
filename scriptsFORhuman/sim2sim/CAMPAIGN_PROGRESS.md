# READY r2 paired full-campaign progress

Worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_sim2sim`  
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`

## Phase log

- Schema phase: introduced the 200 Hz paired JSONL row contract at `0e82607`, then corrected mixed revolute/prismatic target and effort unit names before campaign use. Final schema authority is `2bf0ac417858128ab761fca3fa3aa8451b7ea843`; phase merges returned `Already up to date`, behind `0`.
- Manifest materializer phase: added the explicit legacy-door subset materializer through commit `37d56bf`; each phase merge returned `Already up to date`, behind `0`.
- Case-set phase: materialized eight fixed-seed DoorInstanceSpecs under `artifacts/e5/paired_case_manifest/`. All use `tau_static=tau_dynamic=0`, `no_latch`, and only the distillation `door.py` exact-field surface.
- Runtime implementation phase: added a no-latch paired scene composer and the READY r2 full-episode CPU campaign runner at `2bf0ac4`; `git merge A2_Piper` returned `Already up to date`, behind `0`.

## Remaining in this campaign

- Run every case to horizon or typed episode termination with native RGB, proprio, READY r2 Student, A2_Base, and per-physics-step clipped external PD.
- Produce MuJoCo traces, direct door-state metrics, RGB domain-gap statistics, and an actual MuJoCo asset screenshot.
- Materialize the E5 waiting receipt and comparator entrypoint. A formal Isaac↔MuJoCo comparison remains pending until the user transfers the Isaac trace directory.
