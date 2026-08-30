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
2. **Required runtime wiring smoke.** One 64-env, minimal two-control-tick
   natural eval verifies the separate residual input, policy-only/RMS load, and
   trace wiring. The standard eval timeout is
   `episode_length_buf > ceil(max_episode_length_s/.02)`; the legal minimal
   `max_episode_length_s=.02` therefore yields length 2. This gate proves only
   construction plus actor dual-input runtime wiring: it is not a PPO update
   and writes no training checkpoint.
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

### r12 immutable wiring parser repair

The original r12 wiring supervisor receipt is retained as `FAIL/1`: evaluation
had already completed its exact64 two-control-tick raw output, then the inline
post-eval validator failed at PyYAML's `PosixPath` constructor. The replacement
validator loads the existing runtime YAML through `OmegaConf.load`, verifies
the registered dual-input/receipt and exact64 evidence, and writes a separate,
non-overwrite typed admission artifact. This is a parser-only closure over the
immutable raw output; it does not reinterpret the original supervisor receipt
as PASS and does not rerun Isaac. K1 requires that typed artifact and its
recorded `POST_EVAL_VALIDATOR_YAML_CONSTRUCTOR` failure boundary.

## r13 preregistration — sensor-free gauge from the primary O0 transformer

> **Supersession (r12 → r13).** r12 is immutable historical evidence and its
> `KILL_IDENTITY_NOT_ADMITTED` outcome is not revised. The diagnostic-heavy
> live-shadow/control-repeat r13 proposal is `NOT_RUN` and superseded. The
> active prospective axis is sensor-free O1 gauge realization; it creates new
> r13 outputs and never overwrites, reruns, or re-reduces r12.

### r12 immutable KILL fact and causal premise

The completed r12 fresh cross-process K1 has one topology/discrete mismatch in
each registered pair: `S0-L/env15`, `S0-R/env22`, `S1-L/env18`, and
`S1-R/env23`. All four have `integrity=0`. In every pair the Stage2 physical
state and action divergence precede the recorded topology difference. The
four discrepancies have no common directional bias. This evidence rules out
using r12 cross-process exactness as the identity admission realization; it
does not establish a reward, press, physics, or policy-learning effect.

### Single axis and frozen realization

r13 removes the duplicate O1 scene sensor/PhysX view. The primary O0
`OrderedTargetFrameTransformer` remains the sole live scene reader. At its
initialization it caches the fixed target-local orientation delta

```text
Delta = inv(q_O0) ⊗ q_O1 .
```

For every later live observation, the residual-only gauge is constructed from
the primary transformer's live O0 pose, not from another sensor:

```text
p_residual = p_O0
q_residual = q_O0 ⊗ Delta
```

The cached delta is primary-transformer initialization state, not a registered
second observation term, second scene update, or second PhysX view. If the
primary transformer cannot establish this cache at initialization, the r13
realization fails fast; it must not query an O1 sensor later as a fallback.

- Raw `actor_obs` remains the O0 133D view and is the sole input to frozen
  base RMS, LSTM, base MLP, action standard deviation, and critic.
- The pose assembled above is available only inside `residual_actor_obs` for
  `residual_module.*`; the residual final layer remains zero initialized and
  acts only on mean indices `5:12` at Stage3 or later.
- Target source, reward, press behavior, stage logic and thresholds, physics,
  action transforms, and critic remain O0. C1 and A1 stay off.
- `CONT_STEP2000`, policy-only loading, inherited RMS, all identity thresholds,
  and the no-pooling/no-realignment reducer discipline are unchanged.

### Admission before any r13 training allocation

1. **CPU SE(3) source-checkpoint proof.** With the actual source checkpoint,
   RMS, and matching LSTM states, prove for both target pose slots that the
   cached construction satisfies the double-cover pose identity to the
   registered `1e-6` bound: `p_residual=p_O0` and
   `q_residual=q_O0⊗Delta=q_O1`. Its 18D pose encoding must match the intended
   gauge representation. In the same proof, raw base actor observation, RMS
   input/state, hidden/cell, base mean, standard deviation, and final
   zero-residual action mean are bit-exact where representable, otherwise
   within the existing `1e-6` bound. Static provenance must show exactly one
   live transformer/scene reader and no O1 sensor or PhysX view.
2. **64-env minimal two-control-tick wiring gate.** Run one natural r13 eval
   with `max_episode_length_s=.02`; the standard condition
   `episode_length_buf > ceil(max_episode_length_s/.02)` yields the legal
   length two. Runtime receipts and traces must prove primary-cache gauge
   construction, separate residual input, policy-only/RMS load, and absence
   of a second scene reader. This is construction plus dual-input runtime
   wiring only: no PPO update and no training checkpoint.
3. **Fresh `K1_R13` exact64.** Only after both prior gates pass, run four
   independent paired natural first episodes,
   `seed={0,1} × side={left,right}`: O0 legacy control versus O0 base raw view
   plus the primary-cache residual gauge and zero residual. Every env's full
   topology, Stage3/K5/terminal discrete outcomes, integrity, base-path
   observables, policy mean, and raw action must match under the unchanged
   reducer. Each pair is independently required to pass; there is no pooling,
   prefix intersection, seed/side selection, checkpoint selection, or
   threshold change.

Failure of any gate yields `KILL_R13_IDENTITY_NOT_ADMITTED` and stops before
training. Only all four exact64 K1 pairs passing yields
`R13_CAUSAL_IDENTITY_ADMITTED`; this is the prospective, sensor-free identity
admission and does not relabel r12.

### r13 post-admission boundary

`R13_CAUSAL_IDENTITY_ADMITTED` may start only the existing minimal formal
budget: fresh `R13_S0` and `R13_S1` cells at `4096×250`, with saves/evaluation
at 125 and 250 and bilateral natural exact64 evaluation. The existing step250
reducer, independent seed/side routing, and all no-relay boundaries remain in
force. No reward soup, press change, physics change, additional cells, PPO
smoke, render, or Teacher/Student action is authorized before that admission.

## r14 preregistration — post-construction reseed

> **Supersession (r13 → r14).** r13 K1 is immutable `KILL`: its four paired
> natural first episodes diverged at `S0-L/env15`, `S0-R/env22`, `S1-L/env18`,
> and `S1-R/env23`, matching r12's byte-identical raw evidence. Telemetry is
> not pre-action evidence and the root cause remains unassigned. r14 changes
> only the evaluator's post-construction reseed axis; it creates fresh roots
> under `v26_5_wave2_r1_policy_residual_20260831_r14` and never rewrites r12/r13.

### Pilot admission

The pilot is two sequential cold GPU4 processes, seed0 LEFT, exact64 and
`max_episode_length_s=.98` (legal first-episode length 50): O0A0 control and
sensor-free R13 dual. Both load CONT_STEP2000 policy-only with inherited RMS,
enable `a2_v26_5_post_construction_reseed=true` plus the pilot-only trace
flag, and write the runtime load, post-construction reseed, and first-episode
raw O0 observation/action traces.
The reducer compares every reset snapshot and each env's 50-tick topology,
raw actor observation, action mean, raw action, terminal/discrete outcomes and
integrity under `1e-6`, without pooling or prefix alignment.

- reset snapshot mismatch: `KILL_R14_POST_CONSTRUCTION_RESEED_NOT_ALIGNED`;
- matched snapshot with first mean/action mismatch:
  `KILL_R14_BASE_PATH_NOT_IDENTICAL`;
- matched snapshot/action with a later 50-tick observation or physical split:
  `KILL_R14_CROSS_PROCESS_TRAJECTORY`;
- all gates: `R14_RESEED_PILOT_ADMITTED`.

The pilot does not train. Its typed admission alone starts fresh full K1:
seed0/1 × LEFT/RIGHT exact64, reseed receipts plus existing natural-episode
evidence (the pilot per-step trace is disabled), and unchanged per-env reducer,
yielding `K1_R14_IDENTITY_ADMITTED` only when all four pairs pass; any failure
is `KILL_R14_IDENTITY_NOT_ADMITTED`. K1 S1 remains a separate
tmux cold launch with `sleep 600`. A single-process shadow is non-admission
evidence. Formal smoke/train/eval are registered fail-closed behind full K1;
formal train and formal full-checkpoint eval do not enable post-construction
reseed. Formal eval retains and verifies its full-checkpoint runtime-load
receipt.

## r15 preregistration — shared actor observation

> **Supersession (r14 → r15).** r14's immutable pilot is
> `KILL_R14_CROSS_PROCESS_TRAJECTORY`: reset and tick-zero 12D policy actions
> matched, but the later trace diverged. Source and artifact review locate the
> intervening cause at the second observation group's independent noise/RNG
> consumption, not at reward, thresholds, or physics. r15 changes only this
> observation realization and writes fresh roots under
> `v26_5_wave2_r1_policy_residual_20260831_r15`.

The dual evaluation builds the legacy O0 `actor_obs` once, then shares every
noisy non-target term with `residual_actor_obs`; only its 18D target-pose term
is replaced by the primary-cache O1 gauge. The frozen base actor continues to
consume raw O0. Control explicitly keeps
`a2_v26_5_shared_residual_observation_enabled=false`; dual explicitly sets it
true. No reward, threshold, stage, scene/physics, target source, or action
transform changes.

The first gate is a sequential cold GPU4 pilot: seed0 LEFT, 64 environments,
policy-only `CONT_STEP2000` plus RMS, post-construction reseed, and pilot
trace enabled. `max_episode_length_s=.98` gives the legal exact first-episode
length 50. Trace-v2 records, for every env and control tick, raw O0
`actor_obs[133]`, policy mean and applied high-level action `[12]`, and the
post-delay physical `actions_after_delay[20]`. The reducer requires reset,
all 50-tick continuous fields, exact64 terminal/discrete evidence, diagnostic
forced-close-off evidence, and integrity zero at `1e-6`, without pooling or
alignment.

- reset mismatch: `KILL_R15_POST_CONSTRUCTION_RESEED_NOT_ALIGNED`;
- first raw/base/physical mismatch:
  `KILL_R15_BASE_OR_PHYSICAL_PATH_NOT_IDENTICAL`;
- later continuous, terminal, or topology mismatch:
  `KILL_R15_CROSS_PROCESS_TRAJECTORY`;
- all pilot evidence: `R15_SHARED_O0_PILOT_ADMITTED`.

Only that pilot admission may start fresh natural K1
`seed={0,1}×side={LEFT,RIGHT}`. K1 retains post-construction reseed receipts
but disables the pilot trace, and uses the existing complete per-env base
reducer without pooling, altered thresholds, or intersection. All four pairs
must pass for `K1_R15_IDENTITY_ADMITTED`; any failure is
`KILL_R15_IDENTITY_NOT_ADMITTED`. K1 S1 stays a separate tmux cold launch with
`sleep 600`.

Only full K1 admission opens the fail-closed formal sequence: 64-env smoke,
then `R15_S0/R15_S1` at `4096×250`, saves at 125/250, and bilateral exact64
full-checkpoint evaluation. Formal training and full-checkpoint evaluation do
not enable post-construction reseed; the latter retains its runtime-load
receipt.

Pilot also compares the existing short `stage2_5_step_trace` as per-env sorted
contiguous `step_index` windows over all `env_id=0..63`; an empty control and
dual window is identical, but any unequal window is a typed
`KILL_R15_CROSS_PROCESS_TRAJECTORY` detail. After all four formal supervisor
receipts pass, `eval-reduce` loads all eight bilateral full-checkpoint outputs,
validates R15 shared/full/reseed-off provenance and diagnostics, then applies
the unchanged R1 fixed-step metrics and step250 route.

### R15 formal execution amendment — full-checkpoint diagnostic term

The original `formal_eval/` step125 attempts for `R15_S0` and `R15_S1` are
preserved as `FAIL/1` launch evidence. Both full checkpoints loaded, then the
diagnostic initializer failed before evaluation because the command asked for
`push_door_handle`, while the restored full reward state has the active,
non-zero `a2_stage3_handle_creation` term. This is a diagnostic selector
repair only: formal evaluation now records
`[a2_stage3_handle_creation, a2_stage3_unlatch_hold, push_door_hinge,
a2_stage3_stage4_hold_and_drive]`. Policy-only pilot and K1 retain their
registered `push_door_handle` list.

No reward scale, threshold, axis, checkpoint, trainer, or reducer decision
route is changed. The non-overwriting retry uses
`formal_eval_retry1/`, fresh `*_eval_retry1_*` supervisor receipts, fresh
runtime logs, and writes its reducer to `formal_eval_retry1/reducer.json`.
Before any retry launch, `preregister-retry1` creates the independent
`M/static_retry1/` execution-amendment registry and selector contract. It
records the preserved original registry, fresh output/log roots, supervisor
name template, formal diagnostic terms, and reducer output; neither this
contract nor retry artifacts overwrite `M/static/`.
