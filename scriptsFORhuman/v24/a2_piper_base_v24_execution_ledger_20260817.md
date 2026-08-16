# base_v24 Execution Ledger（2026-08-17）

## Authority

worker prompt → v24 R1 plan → v23 final adjudication → R1 imported pro feedback。GPU0–3 only；本轮只使用 GPU0；无 push。

## Phase ledger

| Phase | Status | Stable product commit | Evidence / stop reason |
|---|---|---|---|
| P0.1 unit + v23 posthoc | COMPLETE | `fce6d68` | `logs_eval/base_v24/p0/v23_posthoc/` |
| P0.2 checkpoint/start freeze | COMPLETE | `5227a9b` | `logs_eval/base_v24/p0/checkpoint_freeze/` |
| P1A native friction + unit probe | COMPLETE | `9ca4374` | `torque_ramp_r4_gpu0/TORQUE_RAMP.json` |
| P1 A–G | COMPLETE | `ba1c4b4` | `a_g_acceptance_r9_gpu0/P1_A_G_RECEIPT.json` |
| P0 runtime parity + foot + P1 H/I | COMPLETE | `f45473b` | R8-QA6, combined receipt r6 |
| P1 final adjudication | COMPLETE | product at `f45473b` | `V24_FRICTION_AUTHORITY_INSUFFICIENT` |
| P2 capacity/lambda/E-region | NOT_ADMITTED | — | P1 was not `MODEL_VALID` |
| P3 historical friction scan | NOT_ADMITTED | — | P2/P3 admission closed at P1 |
| Wave 1 / Route A/B | NOT_ADMITTED | — | Phase 3 not reached |
| RQ3/RQ4 / shadow critic | NOT_ADMITTED | — | Phase 3 not reached |
| Wave 2a/2b | NOT_ADMITTED | — | Phase 3 not reached |

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

## Closure

P2/P3 and every downstream conditional wave are closed by preregistered admission logic, not by budget or owner interruption. Durable memory and the final report carry the terminal boundary. The pre-existing user edit in `scriptsFORhuman/a2_piper_longterm_TODO.md` was not modified.
