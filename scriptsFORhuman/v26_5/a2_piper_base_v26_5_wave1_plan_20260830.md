# base_v26-5 Wave1 R1: O-by-A Stage5 route

## Question

Can geometry-derived active target orientation (O1), with or without a one-time
Stage2-to-3 physical arm delta rebase (A0/A1), turn the v26-4 stable-grasp /
handle-depression behavior into bilateral policy-generated door opening?

## Frozen scope

- Current LEFT/RIGHT mirrored door randomization remains active.
- Canonicalization is off. Reward, physics, action RMS, source checkpoint and
  all non-factor config leaves remain the v26-4 C0 values.
- Training uses CONT_STEP2000, policy-only loading with actor RMS, 4096 envs,
  750 batches and save frequency 125.
- O1A0 and O1A1 each run seed0 and seed1 on physical GPU2/4/5/6. Each
  process exposes only its assigned card and uses process-local `cuda:0`.
- Formal training is deliberately staggered: launch one cell, confirm its
  Isaac startup, 4096-environment construction and first training iteration,
  then launch the next cell. This prevents concurrent GPU Foundation startup;
  it does not alter cell factors, seeds or resources.
- O0A1 runs only as a matched-prefix diagnostic: it reuses v26-4 C0 step750
  policies under an eval-time rebase. It is not a snapshot clone and cannot
  establish training improvement.

## Gates and evidence

1. Runtime contract probe reads the active `OrderedTargetFrameTransformer` in
   full A2 environments for O0/O1 and both sides. O1 neutral target quaternion
   must match the independently derived geometry oracle under quaternion
   double-cover; handle/pregrasp positions and frame order must agree across O0/O1.
2. A real O1A1 64-env, one-PPO-batch smoke on physical GPU2 must write `model_step_000001.pt`
   after the contract probe. It preserves CONT_STEP2000, policy-only actor RMS,
   reward and physics, with only batch/save count reduced.
3. O0A1 diagnostic is four independent exact64 natural-side lanes, sequenced
   under one tmux/supervisor receipt on physical GPU7.
4. Formal step750 evaluation is exact64 natural first episodes for LEFT and
   RIGHT for every formal cell, retaining only `stage2_5_step_trace.json`.
   Launch evaluation one cell at a time: confirm Isaac startup and the LEFT
   exact64 lane has begun before launching the next cell; each launched cell
   then naturally completes LEFT followed by RIGHT in parallel with later cells.
5. The reducer reports K5, contact, highwater, sustained
   `handle >= .1 && current K5` for five controls and time-to-event, hinge .1/.25,
   Stage4, Stage5 and goal. Contact alone never promotes a factor.

## Initial typed decisions

- `PROMOTE_BILATERAL_POLICY_GOAL`: both seeds have natural LEFT and RIGHT goal.
- `PROMOTE_BILATERAL_STAGE5_CONTINUE_TO_GOAL`: both seeds have bilateral Stage5.
- `PROMOTE_BILATERAL_STAGE4_CONTINUE`: both seeds have bilateral Stage4.
- `PROMOTE_BILATERAL_SUSTAINED_DEPRESSION_RELAY`: without Stage4, every
  seed/side has Stage3 admission at least 16/64, sustained Stage3
  `handle >= .1 && current K5` at least 2/64, contact at least .90, and zero
  integrity violations.
- `ACQUISITION_INCONCLUSIVE`: any seed/side has fewer than 16 Stage3 episodes.
- `KILL_NO_BILATERAL_STAGE4_CONTACT_ALONE_INSUFFICIENT`: otherwise.
