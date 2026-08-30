# base_v26-5 Wave2 R1 — O1 raw authority + C2 gauge + zero residual

> **Supersession (r11 → r12).** The O1 raw-authority + C2 realization
> specified below is historical only. Its r11 K1 completed with the immutable
> typed outcome `KILL_IDENTITY_NOT_ADMITTED`; it must not be re-run, repaired
> in place, or used to admit formal training. The active prospective protocol
> is the r12 registration appended at the end of this document.

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

GPU mapping is temporary: `K1_S0/R1_S0=4`, `K1_S1/R1_S1=5`.  Cold Isaac starts are manual
staggered `train-cell --launch` calls; the orchestrator contains no polling or
retry loop.  Every launch is tmux-backed through `run_supervisor`.

The r1 K1 launch generation ended at the stale seven-argument assertion; r2
then reached the first O0 control side and correctly failed because it asked
that source trace for O1's `a2_stage3_handle_creation` instead of
`push_door_handle`; r3 subsequently exposed the same active-component
contract's missing explicit view-specific scales.  All three roots remain
preserved as failed launch evidence.  The repaired attempt is a fresh,
non-overwriting r4 root:
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260830_r4/` and
`logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260830_r4/`.
It did not generate a receipt or start a task-owned process: its `gpu_idle`
preflight found GPU2 occupied by another workspace.  The resource-remapped r5
attempt on GPUs 4/5 preserved its completed control LEFT exact64 artifacts;
the dual compose failed before a dual receipt.  The r6 static root is retained
as incomplete evidence: its registry was written before the explicit `/obs`
selector form exposed the obsolete single-stage compose claim.  The fresh r7
roots are
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260830_r7/` and
`logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260830_r7/`.
The r7 static evidence is deliberately two-stage: it records the R1
eval-selector partial separately, then invokes the real
`gr00t.rl.eval_agent_trl` entry with `--cfg job --resolve` on
CONT_STEP2000's actual checkpoint-directory `config.yaml` host.  The verifier
binds those two artifacts to the entrypoint's
`OmegaConf.merge(train_config, override_config)` operation, which is where the
runtime final actor/obs contract is formed.  This is a source policy-only
selector/load composition proof, not a pre-run claim
about a future full composite checkpoint; fixed-step full evaluation remains
runtime evidence bound by its load receipt and reducer.

The r7 K1 control LEFT exact64 artifacts remain preserved.  Its dual actor
failed at construction because Hydra supplies `residual_stage_obs_slice` as an
OmegaConf `ListConfig`, which the former list/tuple-only validator rejected.
The fresh r8 roots are
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260830_r8/` and
`logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260830_r8/`.
Their registry requires the repaired actor contract: accept a non-string
`collections.abc.Sequence`, require exactly two true integers, and freeze the
converted `(127, 133)` slice.  This binds the real Hydra construction shape
without changing reward, environment, or training semantics.

The r8 dual actor and policy-only actor/RMS load completed, then diagnostic
initialization established the active reward fact: both O0 control and O1+C2
dual use `push_door_handle`; O1/C2 changes geometry and actor view only.  The
former view-specific creation-term assumption is retired.  The fresh r9 roots
are `logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260830_r9/` and
`logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260830_r9/`.
For both K1 views, the trace term is `push_door_handle` and the explicit
depression/creation scales are both `0.0`.  Each side runs dual first then
control, retaining the same four paired exact64 comparisons.

The r9 K1 GPU receipts passed.  Reducer parser revision
`v2_per_env_window_topology` records raw input root
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260830_r9/eval/K1/`.
Diagnostic rows are per-env observed windows, so `step_index` is required to
be non-negative, unique and contiguous within each env after sorting, but is
not required to begin at global step zero.  No row is dropped or pooled; the
same per-env topology is then compared pairwise and the existing `1e-6`
raw-action threshold remains unchanged.

The r9 raw dry parse passed the repaired per-env topology validation for its
first control input, then correctly refused the unchanged K1 load-mode gate:
the command override requested `policy_only`, but the actual control runtime
config records `checkpoint_load_mode: full`.  The O0A0 selector lacks the
v26-5 policy-only eval contract, so `eval_agent_trl` normalizes it to full;
the dual runtime records policy-only.  No `identity_reducer.json` was written,
and this is not treated as a parser or identity admission result.

The r9 GPU raw evidence remains immutable and has no reducer output.  The
fresh r10 roots are
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260830_r10/` and
`logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260830_r10/`.
K1 control explicitly sets `a2_v26_5_policy_only_identity_control=true` and
`a2_v26_5_policy_only_residual=false`; dual explicitly sets those values to
`false` and `true`, respectively.  Both require actual policy-only load mode,
the v26-5 runtime load receipt, and diagnostic metadata.  The per-env parser
v2 topology criteria and all identity thresholds are unchanged.

The r10 static registry remains immutable.  The fresh r11 roots are
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260830_r11/` and
`logs_rl/by_batch/base_v26/v26_5_wave2_r1_policy_residual_20260830_r11/`.
K1 admission now directly reads every side's runtime load receipt and binds
its source path, policy-only mode, eval kind, exact output root, and actor
facts.  Control requires `legacy_identity_control_exact` with strict exact
keys and no missing/unexpected keys; dual requires
`legacy_exact_without_residual`, strict false, exactly
`residual_module.{0.weight,0.bias,2.weight,2.bias}` missing keys, and no
unexpected keys.  Both require loaded actor RMS, P06 false, their exact
mutually exclusive policy-only flags, and diagnostic metadata's registered
reward terms.  Bad receipt, bad flag, and wrong dual missing-key synthetic
inputs must fail before admission.

For a paired K1 comparison, every env's complete sorted `step_index` sequence
must be equal.  An unequal window is recorded with env/count/first/last and
its first differing index, yields `trace_topology_identical=false`, skips
continuous raw-action verification (`null` rather than an inferred overlap
value), and produces `KILL_IDENTITY_NOT_ADMITTED` without a reducer exception.
No intersection, truncation, or re-alignment is permitted.

## r11 immutable KILL evidence

The fresh r11 root is
`logs_eval/base_v26/v26_5_wave2_r1_policy_residual_20260830_r11/`. Its
`K1/identity_reducer.json` is an `EXPERIMENT_COMPLETE` artifact with typed
outcome `KILL_IDENTITY_NOT_ADMITTED`; it is immutable historical evidence.

- Both LEFT pairs passed exactly: seed0 and seed1 each had identical complete
  topology and discrete outcomes, zero integrity violations, and
  `policy_mean_raw_action_max_abs=0.0`.
- Both RIGHT pairs failed. The reducer records five topology mismatches for
  seed0 RIGHT (`env_id` 0, 24, 38, 47, 53) and three for seed1 RIGHT
  (`env_id` 9, 28, 46). It consequently reports non-identical discrete
  outcomes and does not infer a continuous action comparison from mismatched
  windows.
- The matched-prefix implementation scan supplies the causal fact that the
  reducer could not: on RIGHT the frozen base actor action already differs at
  the first comparable step (`seed0=0.0177`, prefix maximum `6.73`; `seed1=0.0187`,
  prefix maximum `7.02`). Base action indices `0:5` differ, while the residual
  final layer is bit-zero.
- Root cause: the r11 C2 gauge replaces the target-pose slot inside the 133D
  `actor_obs`, and that gauge is then fed into the frozen legacy RMS, LSTM,
  and base MLP. A zero residual only prevents the final additive residual; it
  cannot restore a changed frozen base input. LEFT passing does not rescue the
  RIGHT counterexample.

The proposed K2 and every "same gauge control" route are therefore retired:
they address an already disproved simulator-nondeterminism premise rather than
the observed pre-physics base-policy difference. They are `NOT_RUN` and are
not authorized by this plan.

## r12 preregistration — base raw view, residual gauge only

### Single axis and frozen boundary

The r12 axis is the placement of the O1-derived gauge: it is available only as
an independent `residual_actor_obs` input to `residual_module.*`. The frozen
legacy base path is the raw O0 view:

```text
O0 raw actor_obs -> frozen RMS -> frozen LSTM -> frozen base MLP -> base mean
O1-derived residual_actor_obs -------------------------------> residual module
                                                           -> +mean[5:12], Stage3+
```

- `CONT_STEP2000`, `policy_only`, and inherited actor RMS remain the source
  contract. C1 and A1 remain off.
- The O0 raw 133D `actor_obs` is the sole input to the frozen base RMS, LSTM,
  base MLP, action standard deviation, and critic. The separate O1-derived
  gauge may not replace, append to, normalize with, or mutate that base view.
- Reward, press behavior, stage logic/thresholds, target transformer, physics,
  action transforms, and critic target inputs remain O0. The O1 gauge must not
  become `target_quat_source` or another reward/stage/critic input.
- The Stage3-or-later residual remains limited to mean indices `5:12`; its
  final layer is zero initialized. Only `residual_module.*` may be trainable;
  legacy memory, base MLP, standard deviation, and RMS remain frozen.
- If the O1-derived gauge cannot be emitted without contaminating an O0 base,
  reward, stage, target, or critic path, r12 fails fast. It must not fall back
  to r11's same-gauge actor input.

### Admission sequence before any training allocation

1. **Required CPU shadow.** Load the actual source checkpoint/RMS and compare
   legacy control against r12 under matching raw actor inputs and LSTM states.
   Base raw actor observation, RMS input/state, LSTM hidden/cell, base mean,
   standard deviation, and final zero-residual action mean must be bit-exact
   where representable (otherwise the unchanged registered `1e-6` bound).
   The residual is exactly zero before Stage3 and zero initialized at Stage3.
   This is a hard static gate, not a training run.
2. **Required runtime wiring smoke.** One 64-env, one-control-tick natural
   eval verifies the separate residual input, policy-only/RMS load, and trace
   wiring. It is not a PPO update and writes no training checkpoint.
3. **Fresh `K1_R12` exact64.** Only after both gates pass, run
   `seed={0,1} × side={left,right}` as paired natural first episodes: O0 legacy
   control versus O0 base raw view plus O1-derived residual gauge and zero
   residual. Each pair retains independent provenance and full per-env traces.

Every r12 K1 pair must have identical complete topology, Stage3/K5/terminal
outcomes, integrity, base-path observables, policy mean, and raw action. It
also proves that the gauge is present only in the residual branch and has not
entered target source, reward, stage, critic, or frozen base fields. No
pooling, prefix intersection, re-alignment, seed selection, checkpoint
selection, or threshold change is allowed. Any failed CPU shadow, wiring
smoke, or seed-by-side pair yields `KILL_R12_IDENTITY_NOT_ADMITTED`.

Only `K1_R12_IDENTITY_ADMITTED` after all four pairs pass may start two fresh
`R12_S0/R12_S1` formal cells (`4096×250`, saves at 125 and 250, bilateral
natural exact64 evaluation). The existing step250 reducer thresholds and
side/seed-independent routing remain unchanged.

### r12 resources and stopping point

The CPU shadow uses no GPU. The wiring smoke completes before K1. K1 and any
later formal cells use separate tmux/supervisor receipts; start the second
Isaac process only after the first has constructed and reached its first
control tick, using an in-tmux `sleep 600` instead of a polling loop. No
formal-training receipt, PPO smoke, render, relay, or Teacher/Student action
is permitted before all four r12 K1 pairs pass.
