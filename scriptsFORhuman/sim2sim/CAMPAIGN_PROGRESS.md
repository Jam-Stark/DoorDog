# READY r2 paired full-campaign progress

Worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_sim2sim`  
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`

## Phase log

- Schema phase: added the 200 Hz paired JSONL row contract at commit `0e82607dac859ac7cf35ab25faff69aed357a9af`; `git merge A2_Piper` returned `Already up to date`, behind `0`.
- Manifest materializer phase: added the explicit legacy-door subset materializer through commit `37d56bf`; each phase merge returned `Already up to date`, behind `0`.
- Case-set phase: materialized eight fixed-seed DoorInstanceSpecs under `artifacts/e5/paired_case_manifest/`. All use `tau_static=tau_dynamic=0`, `no_latch`, and only the distillation `door.py` exact-field surface.

## Remaining in this campaign

- Run every case to horizon or typed episode termination with native RGB, proprio, READY r2 Student, A2_Base, and per-physics-step clipped external PD.
- Produce MuJoCo traces, direct door-state metrics, RGB domain-gap statistics, and an actual MuJoCo asset screenshot.
- Materialize the E5 waiting receipt and comparator entrypoint. A formal Isaac↔MuJoCo comparison remains pending until the user transfers the Isaac trace directory.
