# v23 P0 interim report — R55 adjudication (synced R56)

**Date:** 2026-08-10 HKT
**Scope:** documentation-only adjudication of the verified R49/R54 P0 records
**Answer first:** P0 evidence is partial and typed.  The A8 certificate is
terminal `COMPLETED_TYPED_NEGATIVE`; the R54 D1 capability-source reducer is
`D1_CAPABILITY_SOURCE_INCOMPLETE` with no D1 freeze.  Formal v23 training is a
hard **NO-GO**.  Only the bounded D0 preparation DAG may continue.

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
| P0.6 | `NOT_RUN/PENDING` | Common reward registry exists; stationary-rent result remains pending. |
| P0.7 | `RUNTIME_VERIFIED` | R21 RP0 contract: real 64-env × 10-batch plus FULL resume 64-env × 1-batch, global steps `0→10→11`, raw posture indices 3/4 neutralized at `0.0`. |
| P0.8 | `PARTIAL/INCOMPLETE` | R55 permits A0/D0 state-bank/plumbing work only; no exact state clone or release receipt. |
| P0.9 | `CONDITIONAL/PENDING` | Only bounded D0 four-type 64-env × 10-batch smokes are allowed after the P0.8 plumbing step. |
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

## FILES_CHANGED

This documentation synchronization changes only:

1. `scriptsFORhuman/v23/a2_piper_base_v23_plan_R1_20260809.md`
2. `scriptsFORhuman/a2_piper_longterm_TODO.md`
3. `scriptsFORhuman/v23/V23_P0_INTERIM_REPORT_20260810.md`

No v23 core code, config, test, memory, or runtime artifact is changed by R56.

## TESTS_RUN

R56 is docs-only.  No GPU, IsaacSim, trainer, evaluator, renderer, or unit test
was run.  The final handoff performs Markdown readback and one scoped
`git diff --check` over the three paths.

## RESULT_CLASSIFICATION

`INTERIM_TYPED / SCIENTIFIC EVIDENCE PARTIAL / FORMAL_TRAINING_NO-GO`

The measured records support calibration adjudication only.  They do not support
formal 8×2 training, an E2 confirmation, a D1 schedule, or a final success
claim.

## NEXT_DAG_NODE

```text
P0.6 continue (rent/audit)
  -> partial P0.8 A0/D0 state-bank/plumbing work
  -> conditional D0 P0.9 four-type 64-env × 10-batch smokes
  -> D0 P0.10 FULL pilot
  -> adjudicate the resulting evidence
```

This DAG is preparation-only while D1 window closure remains unresolved.

## Allowed versus forbidden continuation

| Allowed now | Forbidden now |
|---|---|
| Continue P0.6 stationary-rent/audit work. | Formal 8×2 v23 training. |
| Implement only the partial P0.8 A0/D0/plumbing node. | F3/D1-lite execution or any D1-mixture claim. |
| Run conditional D0 P0.9 four-type smokes after the P0.8 plumbing receipt. | Writing a D1 freeze before the reducer/window contract passes. |
| Run the bounded D0 P0.10 FULL pilot and adjudicate its own receipt. | H1–H5 claims, final goal/release claims, or direct R54 raw-dim 3/4 claims. |

## STOP_OR_CONTINUE

**STOP:** formal training, formal evaluation, final G1–G8 admission, H1–H5,
8×2, F3/D1-lite, D1 freeze, and release/goal claims.
**CONTINUE:** only the bounded D0 preparation DAG above, with typed receipts and
the fail-fast no-fallback boundary preserved.
