# DoorDog A2+PiPER `base_v26` Execution Ledger

**Plan:** `a2_piper_base_v26_execution_plan_R1_20260821.md`  
**Started:** 2026-08-21 18:37 HKT  
**Branch / HEAD at start:** `A2_Piper` / `7d9d0b6d1debc5c22910c1c963b9eb619ed02cf7`  
**State:** `V26_COMPLETE_CONTINUATION_REQUIRED`

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
- 2026-08-22 20:53 HKT - All four formal cells naturally completed 4000/4000
  batches, wrote `model_step_004000.pt`, and exited 0. Each cell produced
  1,048,576,000 timesteps. LR S0 and both unilateral cells remained at
  Stage2 with zero hinge/goal. LR S1 ended with LEFT/RIGHT Stage3 staged-reset
  occupancy `0.294/0.289`, but still zero goals and hinge mean `0.0002 rad`.
- 2026-08-22 21:57 HKT - Completed Route A for 17 checkpoints with 64 LEFT and
  64 RIGHT natural-start episodes each (2,176 episodes); all four lanes exited
  0. No goal or crossing occurred. The mechanical diagnostic leader was LR S1
  step4000 solely because RIGHT reached Stage3 in 1/64 episodes; LEFT remained
  64/64 at Stage2.
- 2026-08-22 23:33 HKT - Completed the frozen LR S1 step4000 holdout at seed
  260823: LEFT 0/128 goals with all 128 at Stage2; RIGHT 0/128 goals with 127
  at Stage2 and 1 at Stage3. Completed seed260824 bilateral render with three
  MP4 views per side; both episodes ended at Stage2 overtime after 552 steps.
  The first render launch exposed USDRT's process-local `cuda:0` requirement;
  remapping physical GPU1 as the only visible device completed both sides.
- 2026-08-22 23:33 HKT - R1 was not admitted because no scratch LR checkpoint
  produced repeated full goals on both sides. Final typed outcome is
  `V26_SCRATCH_REWARD_OR_EXPLORATION_BLOCKED` with
  `V26_CONTINUATION_REQUIRED`. No v26 checkpoint is Teacher-qualified; G7
  remains the unchanged RIGHT-only Student baseline. Final analysis and handoff
  manifest are `a2_piper_base_v26_final_analysis_20260822.md` and
  `a2_piper_base_v26_teacher_handoff_manifest_20260822.json`.
- 2026-08-23 01:19 HKT - Owner selected the historical stand-off acquisition
  route as a v26 supplement rather than a new phase. Documentation is frozen in
  `a2_piper_base_v26_acquisition_supplement_20260823.md`: restore a narrow
  `0.70 m` staging anchor, use scratch `80/3` / velocity-iterations 1, retain
  strict control-step K=5, and switch policy-only to `800/25` / 2 only after
  repeated bilateral natural grasp. No code/config/run was started by this
  documentation decision.
- 2026-08-23 01:51 HKT - Implemented only the three supplement config changes
  in `base_v26_common_scratch_lr.yaml`: staging `[0.68, 0.72] m`, Stage1/2
  forward-creep deadband `0.02 m`, and scratch gripper `80/3` with PhysX
  velocity iterations `1`. Resolved Hydra config retained exact side routing,
  natural far start, FULL/planar actions, R0 load, six-stage topology, and
  strict control-step K=5.
- 2026-08-23 01:51 HKT - LEFT and RIGHT 1-env smokes each completed one real
  64-step rollout, optimizer update, and step1 checkpoint. The 64-env bilateral
  10-batch smoke completed with exact `32/32` sides and step10 checkpoint;
  Stage0→1 standoff was `p50=0.7091 m`, `p95=0.7132 m`. The first 1-env command
  intentionally failed before optimizer construction because its inherited
  four mini-batches could not divide one env; the corrected smoke used one
  mini-batch and exited 0.
- 2026-08-23 01:52 HKT - Launched the supplement acquisition matrix in tmux
  sessions/run receipts `v26a_lr_s0`, `v26a_lr_s1`, `v26a_l_s0`, and
  `v26a_r_s0`, bound to GPU0–3. Formal outputs are under
  `logs_rl/by_batch/base_v26_acquisition_supplement_20260823/formal/`; runtime
  logs are under `runtime_logs/acquisition_supplement/`. Each run expects 4096
  envs, 4000 batches, 250-batch checkpoints, and a natural exit before Route A.
- 2026-08-23 03:40 HKT - All four supplement cells wrote step250 checkpoints
  and remain active. Exact side counts are `2048/2048`, `2048/2048`, `4096/0`,
  and `0/4096`. Stage0→1 standoff p50 is `0.6959/0.6999/0.7026/0.6980 m`
  for LR S0/LR S1/L/R, with p95 `0.7160–0.7166 m`. All cells have max stage 2,
  zero K5/goal, and zero Stage3 occupancy at this early milestone. LR Stage2
  close-command fraction is `0.0744/0.0639`; this is not used to trigger M7 or
  stop a scratch long-horizon run. Exact tables are in
  `logs_eval/base_v26/acquisition_supplement_20260823/progress.json`.
- 2026-08-23 05:19 HKT - All four supplement cells wrote step500 checkpoints
  and remain active. LR S1 is the first cell to reach Stage3 on both LEFT and
  RIGHT during staged-reset training, with Stage3 occupancy `0.1818/0.1807`
  and strict K5 fraction `0.0008`; it still has zero goal and hinge mean only
  `0.0006 rad`. LR S0 and both unilateral cells remain at Stage2 with zero K5
  and goal. Stage0→1 standoff p50 remains `0.6965–0.7136 m`, while LR S1 has
  materially higher Stage2 close/both-contact fractions (`0.4788` / `0.1483`).
  This is retained as a training-side acquisition signal only; it does not
  admit policy-only continuation before bilateral natural-start evidence.
- 2026-08-23 08:28 HKT - All four supplement cells wrote step1000 checkpoints
  and remain active. LR S1 retains bilateral Stage3 occupancy `0.1140/0.1287`
  with strict K5 fraction `0.0005`, close-command fraction `0.6703`, and
  both-contact fraction `0.2761`. LEFT-only now also has Stage3 occupancy
  `0.0665` and K5 fraction `0.0002`; RIGHT-only remains at Stage2 with close,
  both-contact, and K5 fractions `0.0035/0/0`. LR S0 has bilateral Stage3
  high-water events but zero Stage3 occupancy and K5. All cells still have zero
  goals. This is evidence that the acquisition setting recovered a partial
  staged-reset basin, not proof of bilateral natural-start acquisition.
- 2026-08-23 11:44 HKT - All four supplement cells wrote step1500 checkpoints
  and remain active. LR S1 has bilateral Stage3 occupancy `0.1415/0.1434`, K5
  fraction `0.0005`, close fraction `0.6788`, and both-contact fraction
  `0.3033`; LEFT-only has Stage3 occupancy `0.1025` and K5 `0.0003`. LR S0 now
  has Stage3 occupancy `0.0089/0.0443` but K5 remains zero. RIGHT-only remains
  at Stage2 with close fraction `0.0033` and zero both-contact/K5. All cells
  still have zero goal; scratch therefore continues without admitting an
  actuator continuation or changing the single-factor acquisition contract.
- 2026-08-23 15:04 HKT - All four supplement cells wrote step2000 checkpoints
  and remain active. LR S1 has bilateral Stage3 occupancy `0.3014/0.2387` and
  K5 fraction `0.0015`; LR S0 now has bilateral Stage3 occupancy
  `0.0834/0.0995` and K5 `0.0003`. LEFT-only has Stage3 occupancy `0.1392` and
  K5 `0.0006`. RIGHT-only remains at Stage2 with close/both-contact/K5 fractions
  `0.0036/0/0`. All four still have zero goal. The supplement has restored a
  staged acquisition basin in both LR seeds, but natural-start evaluation is
  still required before any policy-only continuation.
- 2026-08-23 21:41 HKT - All four supplement cells wrote step3000 checkpoints
  and remain active. LR S0/S1 have bilateral Stage3 occupancy
  `0.3123/0.1746` and `0.3223/0.2832`, with K5 fractions `0.0012/0.0020`.
  LEFT-only reaches Stage3 occupancy `0.5767` and hinge mean `0.0244 rad`;
  RIGHT-only remains at Stage2 with close/both-contact/K5 `0.0032/0/0`. Goals
  remain zero in every cell. The natural-start Route A orchestrator remains the
  gate and will start only after all four step4000 runs exit cleanly.
- 2026-08-24 04:44 HKT - All four supplement scratch cells naturally completed
  4000/4000, exited 0, and passed run-receipt finalization. Each produced
  1,048,576,000 timesteps. LR S0/S1 end with bilateral Stage3 occupancy
  `0.2714/0.2078` and `0.2498/0.2477`, K5 `0.0017/0.0017`, and zero goals.
  LEFT-only reaches max Stage5 with Stage3/4/5 occupancy
  `0.6935/0.0312/0.0169` and hinge mean `0.3436 rad`, but still no goal.
  RIGHT-only remains at Stage2 with close/both-contact/K5 `0.0033/0/0` and zero
  hinge. The 17-checkpoint bilateral natural-start Route A matrix started
  automatically after scratch exit and is still running on GPU0–3.
- 2026-08-24 05:43 HKT - Completed the supplement Route A matrix for 17
  checkpoints with 64 LEFT and 64 RIGHT natural-start episodes per checkpoint
  (2,176 episodes total); all four lanes and the orchestration receipt passed.
  `LR_S1_STEP3000` is the unique bilateral acquisition leader: LEFT reaches
  Stage3 in `3/64` episodes and RIGHT in `2/64`, satisfying the frozen repeated
  natural strict-K5 gate of at least two episodes per side. There are zero goals
  across the matrix. Policy-only actuator continuation is therefore admitted;
  M7 forced-close, R1, and Teacher/Student handoff are not admitted.
- 2026-08-24 05:50 HKT - Added the single `LR_S1_STEP3000` continuation config:
  bilateral seed1, one GPU x 4096 envs, 3000 batches, policy-only actor
  warm-start, gripper `800/25`, and PhysX velocity iterations `2`. Source trace
  showed the existing loader also inherited actor observation RMS, contrary to
  the supplement's fresh-RMS contract; the loader now supports the explicit
  `policy_only_load_actor_rms: false` setting and exactly excludes the three
  actor RMS state keys while strictly inheriting the MLP/std/LSTM state. Critic,
  optimizer, scheduler, environment, and staged-reset buffers remain fresh.
- 2026-08-24 06:03 HKT - The 64-env continuation smoke completed one real PPO
  update, exact `32/32` sides, and a step1 checkpoint. Loader trace records
  `actor_rms_loaded=False`; source actor RMS count was 4,501,449,728 while the
  freshly initialized post-smoke count was 23,041. Launched the formal
  continuation as the proven v26 topology (one GPU, 4096 envs), rather than
  changing selector/RNG/scene topology to historical v13 multi-rank. Runtime
  validates exact `2048/2048` sides and has completed its first six updates.
  A detached orchestrator will evaluate seven saved checkpoints on 64+64
  natural-start episodes after the 3000-batch run exits cleanly.
- 2026-08-24 07:34 HKT - The policy-only continuation wrote step250 and remains
  active. Both sides reach Stage2, but Stage2 occupancy is only
  `0.0105/0.0030`; close, bilateral contact, K5, hinge, and goal are zero. This
  is retained as the expected fresh critic/RMS/staged-buffer warm-start
  transient. No config, reward, or M7 change is admitted before the historical
  step500 recovery checkpoint.
- 2026-08-24 09:04 HKT - At step500 the continuation has recovered bilateral
  Stage3 occupancy `0.0289/0.0262`, with close fraction `0.1686`, both-contact
  `0.0521`, and strict K5 `0.0001`. Goal and hinge remain effectively zero.
  The fresh-state transient has therefore recovered without a fallback or M7;
  the frozen 800/25 continuation continues to its long-horizon checkpoints.
- 2026-08-24 12:05 HKT - At step1000 bilateral Stage3 occupancy reaches
  `0.4257/0.3378`, with K5 `0.0019` and Stage3/4 both-contact `0.3389`.
  Hinge remains `0.0002 rad` and Stage4/goal remain zero. This matches the
  historical v13 pre-breakthrough Stage3 plateau, so the single-factor
  continuation remains unchanged.
- 2026-08-24 15:10 HKT - At step1500 bilateral Stage3 occupancy is
  `0.3453/0.3044`, K5 is `0.0014`, and Stage3/4 both-contact is `0.2977`.
  Hinge is `0.0004 rad` and Stage4/goal remain zero. The run remains on the
  historical Stage3 plateau and continues unchanged to the step2000
  breakthrough checkpoint.
- 2026-08-24 18:18 HKT - At step2000 bilateral Stage3 occupancy is
  `0.3158/0.2704`, K5 is `0.0023`, and Stage3/4 both-contact is `0.2719`.
  Hinge is `0.0005 rad`; Stage4, release, crossing, and goal remain zero. The
  historical v13 breakthrough timing has not reproduced, but bilateral
  acquisition retention is strong and the frozen 3000-batch budget continues
  without an in-run reward change.
- 2026-08-24 21:26 HKT - At step2500 bilateral Stage3 occupancy is nearly
  symmetric at `0.3106/0.3107`, K5 is `0.0018`, and Stage3/4 both-contact is
  `0.2905`. Stage4, hinge progress, release, crossing, and goal remain zero.
  The final 500 batches continue unchanged; absence of a terminal breakthrough
  will be typed as a full-chain reward/exploration block rather than hidden by
  another factor.
- 2026-08-25 02:07 HKT - The policy-only continuation naturally completed
  3000/3000, exited 0, and passed its run receipt, producing 786,432,000
  timesteps. Endpoint LEFT/RIGHT Stage3 occupancy is `0.2819/0.2255`, K5 is
  `0.0022`, and Stage3/4 both-contact is `0.2362`; hinge mean is
  `0.0003 rad`, with zero Stage4, release, crossing, and goal.
- 2026-08-25 02:07 HKT - Completed continuation Route A for seven checkpoints,
  64 LEFT plus 64 RIGHT natural episodes each (896 total). `CONT_STEP2000`
  is the balanced leader at LEFT `64/64` and RIGHT `61/64` Stage3+, while
  every checkpoint has zero goals. The original orchestrator completed 13/14
  side cells and correctly closed rc1 after a transient external NVIDIA MDL
  asset-server failure on step3000 RIGHT; one exact-protocol rerun of only that
  missing cell exited 0 and completed the summary.
- 2026-08-25 02:07 HKT - Mechanical trace of `CONT_STEP2000` shows sustained
  close, bilateral contact and squeeze after natural Stage3 entry, but
  handle-joint max only `0.0001305/0.036833 rad` and hinge max only
  `0.002131/0.002110 rad`; all Stage3 episodes overtime. Final boundary is
  `V26_ACQUISITION_RECOVERED_STAGE3_UNLATCH_EXPLORATION_BLOCKED`, not close
  persistence. M7, R1, Teacher handoff and Student rebinding remain unadmitted.
- 2026-08-25 02:07 HKT - Updated the supplement, final analysis,
  Teacher/Student manifest, execution ledger and durable memory. Final phase
  state is `V26_SUPPLEMENT_COMPLETE_CONTINUATION_REQUIRED`; the existing
  RIGHT-only G7 Student binding remains unchanged.
- 2026-08-25 02:12 HKT - Confirmed GPU0–3 idle with no v26 tmux process,
  marked `v26_acquisition_supplement` COMPLETED, released all task leases, and
  archived the adaptive coordination state as
  `.ai/runtime/team/coordination-20260825-021249.json`.
