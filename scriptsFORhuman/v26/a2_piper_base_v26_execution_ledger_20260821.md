# DoorDog A2+PiPER `base_v26` Execution Ledger

**Plan:** `a2_piper_base_v26_execution_plan_R1_20260821.md`  
**Started:** 2026-08-21 18:37 HKT  
**Branch / HEAD at start:** `A2_Piper` / `7d9d0b6d1debc5c22910c1c963b9eb619ed02cf7`  
**State:** `R0_FORMAL_RUNNING`

## Start boundary

- GPU0–3 were idle at start. GPU4–7 are occupied by the independent depth-add
  Student run and are outside v26 scope.
- Existing user worktree changes are limited to document moves plus the
  untracked v26 plan; they are preserved.
- v25 is closed and retains G7. v26 starts a new scratch high-level Teacher and
  does not modify the Student worktree or process.

## Frozen R0 decisions

- High-level checkpoint is null with full-load mode and auto-load disabled.
- Door side assignment is exact, seed-permuted, and fixed for each env:
  bilateral runs use half LEFT / half RIGHT; unilateral diagnostic cells use
  one side only.
- Natural start is door-relative with normal distance `0.90–1.40 m`, lateral
  offset `±0.25 m`, and relative yaw `±0.30 rad`.
- Stage timers are `[350, 100, 100, 100, 100, 200]`; episode length remains
  `20 s`, exactly covering the 950 stage steps plus 50-step completion delay at
  the current 50 Hz control rate.
- Common neutral arm pose is retained. No side-conditioned joint mirroring.
- R0 uses normal legacy door dynamics with native v24 friction disabled,
  handle height `0.85–0.95 m`, and mass `80–120 kg`.
- R0 gripper capability is the first-complete-chain v13.1 setting:
  `arm_j7/j8 Kp=800`, `Kd=25`, effort `10/10`, PhysX velocity iterations `2`.
- Reward lineage and current function binding are recorded in
  `V26_REWARD_LINEAGE_REVIEW.md`.

## Execution log

- 2026-08-21 18:37 HKT - Completed required memory/source route, current
  worktree/GPU/process audit, local IsaacLab quaternion/root-state contract
  check, and one-time reward lineage review. No Isaac Sim or optimizer update
  has run yet.
- 2026-08-21 19:09 HKT - Completed clean v26 R0 implementation and resolved
  config proof. A fail-fast 1-env run exposed that the IsaacSim selector router
  omitted the new v26 key; adding that single dispatch entry made the configured
  fixed side reach the real spawner. A second runtime failure exposed integer
  counters at the trainer log boundary; the persistent counters remain integer
  and are emitted as float metrics.
- 2026-08-21 19:09 HKT - Headless 1-env LEFT and RIGHT runs each completed one
  64-step optimizer update with runtime side counts `(1, 0)` and `(0, 1)` and
  checkpoints `left_1env_pass/model_step_000001.pt` and
  `right_1env_pass/model_step_000001.pt`. No GPU-backed X display was available,
  so runtime geometry/pose readback replaced an interactive GUI preview.
- 2026-08-21 19:09 HKT - The 64-env LR smoke completed 10 batches and saved
  `lr_seed0_64env_10batch/model_step_000010.pt`; runtime counts stayed exactly
  `32 LEFT / 32 RIGHT`, with per-side Stage0 snapshot occupancy confined to the
  corresponding 32 envs.
- 2026-08-21 19:09 HKT - The 4096-env LR short-learning gate completed 10
  batches and saved `lr_seed0_4096env_10batch/model_step_000010.pt`. Runtime
  counts stayed exactly `2048 LEFT / 2048 RIGHT`; scene creation took 438.9 s,
  steady training throughput was about 12.9k steps/s, and an update took about
  20.3 s. At batch 10 RIGHT had reached Stage1 while LEFT remained in Stage0;
  this early diagnostic signal is left for the four-cell R0 matrix rather than
  being hidden by a reward change.
- 2026-08-21 19:15 HKT - Started the formal 4096-env / 4000-batch R0 matrix in
  detached tmux sessions `v26_r0_lr_s0`, `v26_r0_lr_s1`, `v26_r0_l_s0`, and
  `v26_r0_r_s0`, bound to `cuda:0`, `cuda:1`, `cuda:2`, and `cuda:3`.
  Runtime logs are `runtime_logs/V26_LR_S0.log`, `V26_LR_S1.log`,
  `V26_L_S0.log`, and `V26_R_S0.log`; run directories are under
  `logs_rl/by_batch/base_v26_r0_20260821/`. The first launcher attempt failed
  before IsaacSim because two metadata overrides lacked Hydra's `+`; the
  corrected launcher also constrains `CUDA_VISIBLE_DEVICES=0,1,2,3`, so GPU4–7
  retain only the independent Student processes.
- 2026-08-21 21:01 HKT - All four R0 cells wrote `model_step_000250.pt` and
  remain active. Exact side counts are `2048/2048` for both LR cells,
  `4096/0` for LEFT-only, and `0/4096` for RIGHT-only. At the step250 table,
  Stage2 occupancy is `0.711/0.717` (LR S0 LEFT/RIGHT), `0.701/0.730`
  (LR S1), `0.659` (LEFT-only), and `0.731` (RIGHT-only). LR S1 RIGHT has a
  Stage3 high-water event; all four still have zero hinge mean and goals. This
  is retained as expected early scratch progression, not an early-stop or
  reward-change trigger. Machine-readable tables are in
  `logs_eval/base_v26/r0_progress.json`.
