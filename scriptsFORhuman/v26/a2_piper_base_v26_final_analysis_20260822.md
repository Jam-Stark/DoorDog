# DoorDog A2+PiPER `base_v26` Final Analysis

**Plan:** `scriptsFORhuman/v26/a2_piper_base_v26_execution_plan_R1_20260821.md`  
**Acquisition supplement:** `scriptsFORhuman/v26/a2_piper_base_v26_acquisition_supplement_20260823.md`  
**Execution ledger:** `scriptsFORhuman/v26/a2_piper_base_v26_execution_ledger_20260821.md`  
**Final state:** `V26_SUPPLEMENT_COMPLETE_CONTINUATION_REQUIRED`  
**Student decision:** do not bind a v26 checkpoint

## Outcome

v26 completed the original clean scratch bilateral protocol and the full
Owner-approved acquisition supplement. The supplement restored repeated
bilateral natural-start strict-K5 acquisition, and the policy-only `800/25`
actuator continuation retained that acquisition. It did not discover the
Stage3 unlatch transition or produce a bilateral full-goal Teacher.

Final typed outcomes:

- `V26_ACQUISITION_SUPPLEMENT_PROTOCOL_VALID`
- `V26_NATURAL_BILATERAL_K5_RECOVERED`
- `V26_POLICY_ONLY_RETENTION_PASS`
- `V26_STAGE3_UNLATCH_EXPLORATION_BLOCKED`
- `V26_R1_NOT_ADMITTED`
- `V26_CONTINUATION_REQUIRED`

The following outcomes are explicitly not claimed:

- `V26_BILATERAL_SCRATCH_TEACHER_READY`
- `V26_MODERATE_LOAD_CONSOLIDATION_PASS`
- `V26_TEACHER_LR_ACQUISITION_READY`
- `V26_TEACHER_LR_LOAD_ROBUST_READY`

## Original R0 closure

The original four 4096-env R0 cells completed 4000/4000 batches with exit code
0. Each produced 1,048,576,000 timesteps. Route A evaluated 17 checkpoints on
64 LEFT plus 64 RIGHT natural-start episodes each (2,176 episodes), followed
by a 128-per-side holdout and bilateral render. No goal occurred. The best
holdout result reached Stage3 in only 1/128 RIGHT episodes and 0/128 LEFT
episodes, localizing the original failure to natural Stage2 acquisition rather
than far-start navigation or bilateral side routing.

The original frozen boundaries remained intact throughout the supplement:

- exact fixed bilateral side distribution and symmetric privileged side slots;
- door-relative natural start `0.90–1.40 m / ±0.25 m / ±0.30 rad`;
- FULL posture, active planar base, six-stage observation/action topology;
- strict control-step K5 semantics and the v13/v13.1 full-chain bridge;
- R0 friction/load/handle-height distribution;
- GPU0–3 only, with the independent Student on GPU4–7 untouched.

## Acquisition supplement implementation

The supplement changed only the frozen acquisition factors:

- explicit Stage0 staging band `[0.68, 0.72] m` with lateral tolerance
  `0.15 m`;
- Stage1/2 forward-creep deadband `0.02 m`;
- scratch arm j7/j8 stiffness/damping `80/3` and PhysX velocity iterations 1.

LEFT and RIGHT one-env smokes each completed a real rollout, PPO update and
checkpoint. A 64-env bilateral 10-batch smoke retained exact `32/32` sides and
measured Stage0→1 standoff `p50=0.7091 m`, `p95=0.7132 m`.

## Supplement scratch matrix and natural Route A

All four supplement cells naturally completed 4000/4000 batches and passed
their run receipts. Each cell used 4096 envs and produced 1,048,576,000
timesteps.

| Cell | Endpoint result | Strict K5 fraction | Goal |
|---|---|---:|---:|
| LR S0 | Stage3 occupancy LEFT 0.2714 / RIGHT 0.2078 | 0.0017 | 0 / 0 |
| LR S1 | Stage3 occupancy LEFT 0.2498 / RIGHT 0.2477 | 0.0017 | 0 / 0 |
| LEFT S0 | max Stage5; Stage3/4/5 occupancy 0.6935/0.0312/0.0169 | — | 0 |
| RIGHT S0 | max Stage2; close/contact/K5 0.0033/0/0 | 0 | 0 |

The scratch supplement Route A again evaluated 17 checkpoints at 64 episodes
per side, 2,176 natural-start episodes total. `LR_S1_STEP3000` was the unique
bilateral acquisition leader: LEFT reached Stage3 in `3/64` and RIGHT in
`2/64`. Because Stage2→3 requires the frozen strict control-step K5 gate, this
passed the preregistered repeated bilateral natural-K5 admission gate. All
goals remained zero.

M7 forced-close was therefore not enabled: the intended `0.70 m + 80/3`
single factor recovered close persistence and bilateral K5 without it.

## Policy-only actuator continuation

Only `LR_S1_STEP3000` entered continuation. It retained the proven one-process,
4096-env v26 topology and switched j7/j8 to `800/25` with PhysX velocity
iterations 2 for 3000 batches, saving every 250 batches.

Source review found that the existing `policy_only` loader restored the actor
observation RMS together with the actor/LSTM. The loader was narrowed with the
explicit `policy_only_load_actor_rms: false` contract: MLP/std/LSTM are strictly
loaded, while actor RMS, critic, optimizer, scheduler, trainer state,
environment and staged-reset buffers start fresh. A real 64-env smoke recorded
`actor_rms_loaded=False` and completed a PPO update/checkpoint. The formal
continuation then completed 3000/3000 batches, exited 0 and produced
786,432,000 timesteps.

At the formal endpoint both sides retained Stage3, with Stage3 occupancy
`0.2819/0.2255`, strict K5 `0.0022`, Stage3/4 bilateral contact `0.2362`, and
hinge mean `0.0003 rad`. Stage4, release, crossing and goal remained zero.

## Continuation natural Route A

Seven checkpoints (`250, 500, 1000, 1500, 2000, 2500, 3000`) were each
evaluated on 64 LEFT and 64 RIGHT natural-start episodes: 896 episodes total.

| Step | LEFT Stage3+ | RIGHT Stage3+ | LEFT/RIGHT goal |
|---:|---:|---:|---:|
| 250 | 0/64 | 0/64 | 0 / 0 |
| 500 | 0/64 | 0/64 | 0 / 0 |
| 1000 | 1/64 | 0/64 | 0 / 0 |
| 1500 | 54/64 | 4/64 | 0 / 0 |
| 2000 | 64/64 | 61/64 | 0 / 0 |
| 2500 | 37/64 | 63/64 | 0 / 0 |
| 3000 | 40/64 | 63/64 | 0 / 0 |

`CONT_STEP2000` is the balanced mechanical diagnostic leader, not a Teacher.
The original orchestrator completed 13 of 14 side cells; the final step3000
RIGHT scene initialization hit a transient external NVIDIA MDL asset-server
failure and the receipt correctly closed with rc1. One exact-protocol rerun of
that missing cell exited 0, after which the complete summary was rebuilt. No
failed result was silently reclassified as a passing orchestrator receipt.

## Final failure localization

The `CONT_STEP2000` natural traces show that acquisition and persistence are no
longer the limiting factors:

- all Stage3 rows commanded the negative close primitive on both sides;
- bilateral contact fraction was 1.0, contact stability was 0.9689 LEFT and
  0.9666 RIGHT, and squeeze-window fraction was 1.0;
- maximum Stage3/4 contact streak was 207 LEFT and 198 RIGHT;
- all Stage3 episodes ended by overtime;
- handle-joint maximum was only `0.0001305 rad` LEFT and `0.036833 rad` RIGHT;
- hinge maximum was only `0.002131 rad` LEFT and `0.002110 rad` RIGHT.

The final scientific boundary is therefore
`V26_ACQUISITION_RECOVERED_STAGE3_UNLATCH_EXPLORATION_BLOCKED`. It is not a
close-persistence failure, so M7 is not the next admitted action. A future
continuation, if separately authorized, should isolate Stage3 handle-depression
and unlatch exploration while keeping side distribution, natural start,
strict K5, R0 load, action topology and success semantics fixed.

## R1, Teacher and Student decision

R1 was not admitted. The frozen gate requires repeated full natural goals on
LEFT and RIGHT before introducing the moderate-load mixture; every supplement
scratch and continuation natural episode produced zero goals.

No v26 checkpoint is Teacher-qualified. `CONT_STEP2000` is science and future
continuation evidence only. The existing Student remains unchanged on the
RIGHT-only G7 baseline:

- checkpoint:
  `logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt`
- saved config:
  `logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/config.yaml`
- action: unchanged

## Artifacts

- original R0 progression: `logs_eval/base_v26/r0_progress.json`
- original unified evaluation: `logs_eval/base_v26/final/v26_eval_summary.json`
- supplement scratch progression:
  `logs_eval/base_v26/acquisition_supplement_20260823/progress.json`
- supplement scratch Route A:
  `logs_eval/base_v26/acquisition_supplement_20260823/route_a_summary.json`
- continuation progression:
  `logs_eval/base_v26/acquisition_supplement_20260823/continuation_progress.json`
- continuation Route A:
  `logs_eval/base_v26/acquisition_supplement_20260823/continuation_route_a_summary.json`
- formal continuation:
  `logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/`
- Teacher handoff manifest:
  `scriptsFORhuman/v26/a2_piper_base_v26_teacher_handoff_manifest_20260822.json`

The v26 supplement is complete as a research acquisition result. It does not
authorize a hardware release, R1 load consolidation, Teacher handoff or
Student rebinding.
