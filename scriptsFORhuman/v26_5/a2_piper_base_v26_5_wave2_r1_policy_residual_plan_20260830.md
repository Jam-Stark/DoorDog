# base_v26-5 Wave2 R1 — O1 raw authority + C2 gauge + zero residual

## Registered question

Can a trainable Stage3-only 7D mean residual preserve the `CONT_STEP2000`
acquisition policy at initialization while exposing a minimal manipulation
adaptation path?  The only new trainable actor parameters are
`residual_module.*`; the inherited recurrent memory, actor MLP, action standard
deviation and actor RunningMeanStd remain frozen.

## Frozen realization

- Source: `CONT_STEP2000`, loaded `policy_only` with inherited actor RMS.
- Raw environment authority: O1 geometry-derived target; C1 and A1 are off.
- C2 changes only the actor target-pose representation.  Critic target-pose
  input remains raw O1.
- Zero residual affects only mean indices `5:12` at Stage3 or later.  It is
  zero initialized; no reward, gate, curriculum, physics or action transform
  is changed.

## K1 hard admission

Before a training allocation, paired exact64 natural starts run for each
`seed={0,1}` and `side={left,right}`.  Each pair uses the same source
checkpoint and seed: O0A0 control versus O1+C2 with the zero residual actor.
The reducer requires complete per-env coverage, matching topology, matching
discrete Stage3/K5/terminal outcomes, integrity zero, and stepwise policy
mean/raw-action difference at most `1e-6`.  The O1 trace must retain the raw
target source fields.  The trace does not export `std`; its frozen state is
instead a static actor/selector/loader contract and a separate actual-load
receipt fact.  Failure is `KILL_IDENTITY_NOT_ADMITTED`.

## Formal R1

After K1 only, two independent cells (`R1_S0`, `R1_S1`) run `4096×250`, save
step125 and step250, and evaluate both checkpoints on LEFT and RIGHT exact64
natural first episodes.  Step250 is the sole first-round routing endpoint.
The reducer reports, per seed×side and fixed step, K5, contact stability,
five-control sustained `handle>=0.1 && current K5`, Stage4/5/goal and summed
integrity.  It never pools sides or seeds to admit a route.

## Resources

GPU mapping is temporary: `R1_S0=2`, `R1_S1=3`.  Cold Isaac starts are manual
staggered `train-cell --launch` calls; the orchestrator contains no polling or
retry loop.  Every launch is tmux-backed through `run_supervisor`.

The r1 K1 launch generation ended at the stale seven-argument assertion; r2
then reached the first O0 control side and correctly failed because it asked
that source trace for O1's `a2_stage3_handle_creation` instead of
`push_door_handle`.  Both artifact roots remain preserved as failed launch
evidence.  The repaired attempt is a fresh, non-overwriting r3 root:
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260830_r3/` and
`logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260830_r3/`.
