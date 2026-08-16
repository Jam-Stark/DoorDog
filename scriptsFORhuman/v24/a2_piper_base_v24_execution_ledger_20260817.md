# base_v24 Execution Ledger（2026-08-17）

## Authority

worker prompt → v24 R1 plan → v23 final adjudication → R1 imported pro feedback；2026-08-17 Owner D-v2 decision supersedes `FINAL_STOP_AT_P1` as the round terminal。GPU0–3 only；截至 D-v2 只使用 GPU0；无 push。

## Phase ledger

| Phase | Status | Stable product commit | Evidence / stop reason |
|---|---|---|---|
| P0.1 unit + v23 posthoc | COMPLETE | `fce6d68` | `logs_eval/base_v24/p0/v23_posthoc/` |
| P0.2 checkpoint/start freeze | COMPLETE | `5227a9b` | `logs_eval/base_v24/p0/checkpoint_freeze/` |
| P1A native friction + unit probe | COMPLETE | `9ca4374` | `torque_ramp_r4_gpu0/TORQUE_RAMP.json` |
| P1 A–G | COMPLETE | `ba1c4b4` | `a_g_acceptance_r9_gpu0/P1_A_G_RECEIPT.json` |
| P0 runtime parity + foot + P1 H/I | COMPLETE | `f45473b` | R8-QA6, combined receipt r6 |
| Historical R1 P1 final adjudication | SUPERSEDED_AS_ROUND_TERMINAL | product at `f45473b` | Historical `V24_FRICTION_AUTHORITY_INSUFFICIENT`; receipts immutable |
| Owner D-v2 behavioral gate | COMPLETE | `eb8aeda` | `V24_FRICTION_MODEL_VALID_BEHAVIORAL`; P2/P3 admitted |
| P2 capacity/lambda/E-region | ADMITTED_PENDING | — | Includes parameter-range freeze previously `NOT_PERFORMED` |
| P3 historical friction scan | GATED_ON_P2 | — | True Owner decision remains only `V24_FRICTION_AXIS_NONDISCRIMINATIVE` |
| Wave 1 / Route A/B | GATED_ON_P3 | — | Not executed |
| RQ3/RQ4 / shadow critic | GATED_ON_P3_AND_WAVE1 | — | Not executed |
| Wave 2a/2b | GATED_ON_PRIOR_RESULTS | — | Not executed |

## Runtime closure

- A–G GPU0 receipt: PASS within qualified gates; D remains literal authority-insufficient.
- Compatibility/H GPU0 R8-QA6: PASS, exit 0, 443.9 s.
- Parity: 7,326 rows; 133/12/24 dimensions; all float max-abs differences `0.0`; done/terminal exact.
- Foot: current source available `(16,4)`; baseline typed unavailable without numeric fill.
- Reset persistence: 16 receipts = 10 ordinary + 6 legitimate staged; sentinel/readback and configured post-reset readback PASS.
- Final typed result: `V24_FRICTION_AUTHORITY_INSUFFICIENT`.
- Owner decision: not requested; the sole decision point is Phase 3 axis nondiscrimination, and Phase 3 was not reached.

## Failure provenance

Runtime compatibility r1–r5 are retained and non-admissible: exact work-root collision, Hydra override form, eval load-mode normalization, inherited v20 R2 exporter, and function-local `json` scope bug. Each was corrected from its first concrete failure; no failed partial receipt was promoted.

## Historical R1 closure

P2/P3 and every downstream conditional wave are closed by preregistered admission logic, not by budget or owner interruption. Durable memory and the final report carry the terminal boundary. The pre-existing user edit in `scriptsFORhuman/a2_piper_longterm_TODO.md` was not modified.

## Owner D-v2 resumption

- Owner decision: `OWNER_GATE_REVISION_D_V2 + CONTINUE_FROM_P2`; literal D is replaced by behavioral total mechanical energy accounting, while the old final and A/B/C/E/F/G/H/I receipts remain immutable.
- Stable product/evidence commit: `eb8aeda`.
- GPU0 / logical `cuda:0` producer exit `0` in `19.814 s`; seed `24017`; `I_model=36.1 kg*m^2`, `k=6 N*m/rad`, `theta_ref=0.5 rad`.
- Fresh F00 tolerances: `tol_step=9.93409096170439e-06 J`, `tol_cumulative=0.0008802263651532332 J`. Fresh F10 final D is `0.007680328808102447 J` / `0.007679495205304246 J`; both signs pass raw continuity, motion, readback, cleanup, step/cumulative tolerance, and final-dissipation checks.
- Typed result: `V24_FRICTION_MODEL_VALID_BEHAVIORAL`; P2/P3 admission `true`. D-v2 source is `CODE_QUALITY PASS` / `ISAACLAB_SEMANTICS PASS`; QA1 runtime/scientific PASS and QA2 historical-input immutability closure PASS.
- Authority: friction/model torque is `MODELED_FROM_PARAMS`; solver friction torque is `UNAVAILABLE_NOT_USED`; command work is `COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE`. No solver-applied or actual generalized-torque claim is made.
- Next ordered work: P2 directional capacity / lambda / ladder recalibration / E-region certificate plus parameter-range freeze, then P3 frozen historical zero-sample scan. No P2/P3/training/release result is claimed here.
