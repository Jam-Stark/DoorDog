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
