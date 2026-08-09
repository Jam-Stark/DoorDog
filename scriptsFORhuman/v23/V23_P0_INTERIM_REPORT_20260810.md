# v23 P0 interim report — R78 partial P0.8 closure

**Date:** 2026-08-10 HKT
**Scope:** typed adjudication through the verified R78 partial A0/D0 P0.8 runtime receipt
**Answer first:** P0 evidence is partial and typed.  The A8 certificate is
terminal `COMPLETED_TYPED_NEGATIVE`; the R54 D1 capability-source reducer is
`D1_CAPABILITY_SOURCE_INCOMPLETE` with no D1 freeze.  Formal v23 training is a
hard **NO-GO**.  P0.6 common-reward composition and stationary-rent capture are
runtime verified.  R78 also runtime-verifies only the bounded partial A0/D0
P0.8 source-plumbing node and admits the D0 P0.9 smoke; no broader P0.8, D1,
formal, clone, or release claim follows.

## STATUS

`INTERIM_TYPED_ADJUDICATION / FORMAL_NO-GO`

`confirmed_E2=false`.  This report is not a final v23 result and makes no
H1–H5, formal 8×2, F3/D1-lite, or release/goal claim.

## EVIDENCE

### P0 calibration table

| Node | Current status | Evidence and boundary |
|---|---|---|
| P0.1 | `NOT_RUN/PENDING` | Torque-authority extension is not adjudicated here. |
| P0.2 | `MEASURED_FREEZE` + `LADDER_INCONCLUSIVE` | Selected effort `40.0 N*m`; exact 12 runs / 192 records in `logs_eval/base_v23/p0/r33_p02_effort_freeze_20260809/effort_freeze.json`; no normal ladder selection. |
| P0.3 | `NOT_RUN/PENDING` | No new Kp/action-scale/clip adjudication. |
| P0.4 | `MEASURED_RAW` | Atlas and external-threshold producers are raw/typed. Positive brackets: A0/A1 `(10,15]`, A2/A3/A7 `(25,30]`, A4/A5/A6 `(15,20]`, A8 `(30,40]`; negative sign is `RIGHT_CENSORED`. D1 zones/mixture are not frozen. |
| P0.5 certificate | `COMPLETED_TYPED_NEGATIVE` | R49 certificate has pass0, 15 typed-negative records, env5 `RESCUE_NOT_EXECUTED`, and `confirmed_E2=false`. |
| P0.5 D1 source | `D1_CAPABILITY_SOURCE_INCOMPLETE` | R54 has exact16 FULL and exact16 ACUTE source records, but the reducer exits `rc2`; `d1_freeze_written=false`. |
| P0.6 | `RUNTIME_VERIFIED / AUDIT_COMPLETE` | R68 completed a 16-env warm/FULL/D0 short smoke with finite metrics. R72 completed six fresh policy-only stage passes on GPU0; all six processes finished 16 episodes, the pass record counts were `16/16/16/16/16/13`, and the canonical audit is `COMPLETE` with `missing_stages=[]`. |
| P0.7 | `RUNTIME_VERIFIED` | R21 RP0 contract: real 64-env × 10-batch plus FULL resume 64-env × 1-batch, global steps `0→10→11`, raw posture indices 3/4 neutralized at `0.0`. |
| P0.8 | `PARTIAL_A0_D0_RUNTIME_VERIFIED / OVERALL_INCOMPLETE` | R78 completed one fresh 16-env GPU0 source rollout, captured stages 2/3/4, and emitted 3 entries plus 15 typed bindings. Exact state clone, recurrent restore, alternate-mode effects, formal admission, and release remain false/unverified. |
| P0.9 | `D0_SMOKE_ADMITTED / PENDING` | The R78 receipt admits only the bounded D0 four-type 64-env × 10-batch smokes; none ran in R78. |
| P0.10 | `NOT_RUN/PENDING` | D0 FULL pilot is the next bounded node; no GO/NO-GO claim. |

### Certificate versus D1-source distinction

| Producer purpose | Canonical artifact | Meaning |
|---|---|---|
| A8 P0.5 certificate (`P05_CERTIFICATE`) | `logs_eval/base_v23/p0/r49_p05_reduction_20260809/feasibility_certificate.json`; pair/bundle siblings in the same directory | Terminal typed-negative certificate result. It does not prove E2 or produce a D1 mixture. |
| A0 capability source freeze (`D1_CAPABILITY_SOURCE`) | `logs_eval/base_v23/p0/r50_p05_d1_source_20260809/a0_capability_source_freeze.json` | Source geometry/effort freeze for the D1 producer; it is not the A8 certificate. |
| R54 D1 runtime inputs | `logs_eval/base_v23/p0/r54_p05_d1_source_runtime_20260810/runs/full/a2_v23_p05_episode_records.json` and `runs/acute_rp0/a2_v23_p05_episode_records.json` | Exact16 records per mode, finite, runtime `rc0`; FULL has valid windows for 15/16 envs (env5 has none), ACUTE has a valid window only for env12. |
| R54 reducer receipt | `logs_eval/base_v23/p0/r54_p05_d1_reduction_20260810/d1_capability_source_incomplete.json` | `rc2`, `D1_CAPABILITY_SOURCE_INCOMPLETE`, both modes report `NO_STABLE_FAILURE_FREE_25_STEP_WINDOW`, and `d1_freeze_written=false`. |

The certificate is terminal typed-negative; the D1 source branch is incomplete.
They must not be merged into a single PASS or a `confirmed_E2` claim.

### R53 → R54 debug provenance

R53 FULL and ACUTE reached 16-environment IsaacSim initialization, then failed in
`DoorPregrasp` because the required integer
`env.config.a2_v23_p05_seed` was absent from the resolved configuration.  R54
added the exact seed override and produced finite exact16 FULL and ACUTE source
records with runtime `rc0`.  The remaining failure is the scientific stable-
window contract: FULL lacks env5's valid window, ACUTE retains only env12, and
the canonical reducer therefore exits `rc2`.  No silent recovery or fallback is
being claimed.

### Raw-dimension status

Direct proof of R54 P05 source raw dimensions 3/4 is **INCONCLUSIVE**.  The R21
RP0 contract proves its own mask indices and neutral semantics, but those facts
cannot be used as a substitute for a direct R54 source-dimension receipt.

### P0.6 common reward and stationary-rent evidence

The concrete P0.6 config composes the v23 reward registry for the v22 step1250
warm checkpoint under `FULL/D0`, keeps
`a2_v22_clearance_success=+4`, `a2_v22_controlled_fling=+2`, and
`penalty_a2_v22_unsafe_release=-8`, removes the other three v22 posture terms,
and leaves `penalty_a2_posture_command_l1=0`.  R68 exercised that effective
configuration for 16 completed episodes with 3,590 finite numeric metric
values; R2, RP0, stationary capture, cameras, and rendering were disabled.

R72 then ran six fresh sequential GPU0 processes targeting stages `0..5`.
Every process completed the normal 16-episode evaluator finalization.  The
stage record counts were `16/16/16/16/16/13`: each recorded row has exact
target/pre/post stage identity, a verified all-zero 12-D applied high-level
action, and the same 58 finite raw/scaled reward terms.  The reducer wrote
`logs_eval/base_v23/p0/reward/stationary_rent_audit.json` with schema
`a2_piper_v23_stationary_rent_audit_v1`, status `COMPLETE`, and
`missing_stages=[]`.  This verifies the bounded zero-action same-step audit
contract and reward composition; it is not a policy-quality, long-horizon
stationarity, formal-training, or release claim.

### P0.8 partial A0/D0 state-bank evidence

R78 materialized one fresh R50/R54-bound A0 source manifest and launched the
warm step1250 `FULL/D0` evaluator once on physical GPU0 / logical `cuda:0`.
The process returned `rc0` after normal completion of all 16 first episodes.
All 16 authoritative physical readbacks matched the R50 geometry and requested
door parameters `50/2/4.5/120`; their native readbacks were
`2864.7890625/114.59156036376953/4.5/119.99999237060547` for
damping/stiffness/max-force/mass.

The source rollout captured finite contiguous pre-step prefixes for target
stages `2/3/4`.  Reduction wrote 3 state-bank entries and exactly 15 bindings.
The 3 `FULL` bindings are labeled
`SOURCE_ROLLOUT_CAPTURED_NOT_REEXECUTED`; the 12 bindings for the four alternate
modes remain `NOT_EXECUTED_ALTERNATE_MODE`.  The canonical receipt
`logs_eval/base_v23/p0/state_bank/state_bank_plan.json` has schema
`a2_piper_v23_p08_partial_a0_d0_receipt_v1`, status
`PARTIAL_A0_D0_PLUMBING_RUNTIME_VERIFIED`, `missing_stages=[]`,
`p08_overall_status=PARTIAL_INCOMPLETE`, and `p09_d0_smoke_admission=true`.
Formal admission, release, exact state clone, and recurrent-state restore remain
false.  No intervention-effect or delta-J result is claimed.

## FILES_CHANGED

The R78 closure candidate contains the opt-in trainer capture path, one P0.8
launch config, the state-bank runner/reducer, typed intervention binding updates,
this report, the v23 plan synchronization, and the corresponding mechanical
memory update.
Runtime outputs remain under the canonical ignored `logs_eval/base_v23/p0/`
tree.  The eight user-provided v23 source documents remain untracked and are
not part of the candidate.

## TESTS_RUN

- R68 short smoke: project Python, physical GPU0 / logical `cuda:0`, runtime
  `rc0`, 16 completed episodes, and 3,590 finite numeric metric values.
- R72 stationary-rent RUN: project Python, physical GPU0 / logical `cuda:0`,
  runtime `rc0` in about 23m22s; six fresh sequential stage processes all
  reached normal 16-episode finalization.
- R72 REDUCE: `rc0`; canonical typed audit `COMPLETE`, no missing stage.
- Targeted Hydra composition, Python parse/source checks, code review, and
  IsaacLab semantics review passed for the frozen P0.8 candidate.
- R78 P0.8 RUN: project Python, physical GPU0 / logical `cuda:0`, exactly one
  fresh evaluator process, runtime `rc0` in about 229 seconds, normal 16-episode
  completion, stages `2/3/4`, 3 entries, 15 bindings, and 16 finite physical
  readbacks.
- No retry, separate reduce, training, P0.9, D1, formal evaluation, or rendering
  command was run.

## RESULT_CLASSIFICATION

`INTERIM_TYPED / SCIENTIFIC EVIDENCE PARTIAL / FORMAL_TRAINING_NO-GO`

The measured records support calibration adjudication only.  They do not support
formal 8×2 training, an E2 confirmation, a D1 schedule, or a final success
claim.

## NEXT_DAG_NODE

```text
[R78 COMPLETE] partial P0.8 A0/D0 state-bank/plumbing work
  -> [NEXT/ADMITTED] D0 P0.9 four-type 64-env × 10-batch smokes
  -> D0 P0.10 FULL pilot
  -> adjudicate the resulting evidence
```

This DAG is preparation-only while D1 window closure remains unresolved.

## Allowed versus forbidden continuation

| Allowed now | Forbidden now |
|---|---|
| Consume the R78 partial P0.8 receipt only as D0 P0.9 admission. | F3/D1-lite execution or any D1-mixture claim. |
| Run the admitted D0 P0.9 four-type smokes. | Writing a D1 freeze before the reducer/window contract passes. |
| Run the bounded D0 P0.10 FULL pilot and adjudicate its own receipt. | H1–H5 claims, final goal/release claims, or direct R54 raw-dim 3/4 claims. |

## STOP_OR_CONTINUE

**STOP:** formal training, formal evaluation, final G1–G8 admission, H1–H5,
8×2, F3/D1-lite, D1 freeze, and release/goal claims.
**CONTINUE:** run only the admitted D0 P0.9 node, then the remaining bounded D0
preparation DAG above, with typed receipts and the fail-fast no-fallback boundary
preserved.
