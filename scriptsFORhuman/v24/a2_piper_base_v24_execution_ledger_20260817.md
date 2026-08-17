# base_v24 Execution Ledger（2026-08-17）

## Authority

worker prompt → v24 R1 plan → v23 final adjudication → R1 imported pro feedback；2026-08-17 Owner D-v2 decision supersedes `FINAL_STOP_AT_P1`，Owner P2 invalid-measurement decision supersedes the r10 scientific terminal，and r12 is the current P2 authority。GPU0–3 only；r12 F3 production/evaluation used physical GPU0–3；无 push。

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
| Historical P2 r10 capacity/lambda | RECLASSIFIED | historical product retained | `SUSPECTED_INVALID_MEASUREMENT_PENDING_VITALS`; receipts immutable |
| P2 r12 Rule16 + marginal-E1 F3 | TERMINAL | local r12 closure | `V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3`; valid 64-row population; `P3_ADMITTED=false` |
| P3 historical friction scan | NOT_ADMITTED | — | P2 r12 post-F3 terminal；未执行，不触发 Owner decision |
| Wave 1 / Route A/B | NOT_ADMITTED | — | P3 未准入；未执行 |
| RQ3 / shadow critic | NOT_ADMITTED | — | E1 per-cell denominator gate failed；未执行 |
| RQ4 measurement-only closure | PENDING | — | R1 F3 preserves measurement-only delivery outside the stopped science wave |
| Wave 2a/2b | NOT_ADMITTED | — | 前序 gate 未准入；未执行 |

## Runtime closure

- A–G GPU0 receipt: PASS within qualified gates; D remains literal authority-insufficient.
- Compatibility/H GPU0 R8-QA6: PASS, exit 0, 443.9 s.
- Parity: 7,326 rows; 133/12/24 dimensions; all float max-abs differences `0.0`; done/terminal exact.
- Foot: current source available `(16,4)`; baseline typed unavailable without numeric fill.
- Reset persistence: 16 receipts = 10 ordinary + 6 legitimate staged; sentinel/readback and configured post-reset readback PASS.
- Historical R1 P1 typed result: `V24_FRICTION_AUTHORITY_INSUFFICIENT`; it was later superseded as the round terminal by the Owner D-v2 revision.
- Current P2 typed result: `V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3`. P3 is not admitted；Phase 3 axis nondiscrimination 未执行，故唯一 Owner decision point 未触发。

## Failure provenance

Runtime compatibility r1–r5 are retained and non-admissible: exact work-root collision, Hydra override form, eval load-mode normalization, inherited v20 R2 exporter, and function-local `json` scope bug. Each was corrected from its first concrete failure; no failed partial receipt was promoted.

## Historical R1 closure

The old P1 and P2 receipts remain immutable provenance. The Owner D-v2 decision superseded the P1 stop, and the Owner P2 invalid-measurement decision reclassified the r10 P2 terminal. Neither historical stop controls the current r12 adjudication.

## Owner D-v2 resumption

- Owner decision: `OWNER_GATE_REVISION_D_V2 + CONTINUE_FROM_P2`; literal D is replaced by behavioral total mechanical energy accounting, while the old final and A/B/C/E/F/G/H/I receipts remain immutable.
- Stable product/evidence commit: `eb8aeda`.
- GPU0 / logical `cuda:0` producer exit `0` in `19.814 s`; seed `24017`; `I_model=36.1 kg*m^2`, `k=6 N*m/rad`, `theta_ref=0.5 rad`.
- Fresh F00 tolerances: `tol_step=9.93409096170439e-06 J`, `tol_cumulative=0.0008802263651532332 J`. Fresh F10 final D is `0.007680328808102447 J` / `0.007679495205304246 J`; both signs pass raw continuity, motion, readback, cleanup, step/cumulative tolerance, and final-dissipation checks.
- Typed result: `V24_FRICTION_MODEL_VALID_BEHAVIORAL`; P2/P3 admission `true`. D-v2 source is `CODE_QUALITY PASS` / `ISAACLAB_SEMANTICS PASS`; QA1 runtime/scientific PASS and QA2 historical-input immutability closure PASS.
- Authority: friction/model torque is `MODELED_FROM_PARAMS`; solver friction torque is `UNAVAILABLE_NOT_USED`; command work is `COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE`. No solver-applied or actual generalized-torque claim is made.
- D-v2 准入后的 P2 已按下节完成并到达注册终点；本节不回写或替换任何旧 receipt。

## Historical P2 r10 closure (reclassified)

- Stable product/evidence commit: `f0a3a44`。Canonical root：`logs_eval/base_v24/p2/force_boundary/r10/`；旧 r1–r8 receipt 保持不变且不作为裁决输入。
- Parameter-range freeze 已执行。Physical GPU0 smoke exit `0`（`175.36 s`）；calibration exit `0`（`2860.99 s`），得到 288 rows = 6 caps × 3 friction profiles × 16 paired scenarios。
- Foot source `AVAILABLE` 288/288；`stable_grasp` 0/288。有效 model/capacity rows 为 42/288，有限 `tau`/`lambda` 为 42/42；有效 loaded-foot slip window 为 0，E0/E1 denominator count 为 0/0。
- `command_path_binding=true`；`tau_hi_nm`、`tau_boundary_nm`、`tau_rescue_nm` 均为 null；contingency 未触发。正常 `>=8` / Q99 / full-heldout E-region 路径未执行，不声明该路径 PASS。
- CPU-only freeze → heldout → adjudicate → QA 全部 exit `0`，独立重算一致。Heldout 是 exact zero-row `NOT_ADMITTED_BY_P2_TERMINAL` receipt。
- The historical reducer emitted `V24_E1_DENOMINATOR_INSUFFICIENT`, but the Owner decision reclassifies it as `SUSPECTED_INVALID_MEASUREMENT_PENDING_VITALS` because the 0/288 grasp population failed the newly required instrument-vitals precondition. It is not the current scientific terminal.
- Authority 保持：door friction/model torque 为 `MODELED_FROM_PARAMS`，`solver_applied=false`；不声称 solver-applied friction torque。
- 新 P2 裁决：`scriptsFORhuman/v24/a2_piper_base_v24_p2_final_adjudication_20260817.md`。

## Owner P2 invalid-measurement revision and Rule16

- Authority: `scriptsFORhuman/v24/DoorDog_v24_owner_decision_p2_invalid_measurement_20260817.md`. r10 receipts are unchanged.
- Rule16: every calibration/evaluation population must first reproduce an easy/sham checkpoint baseline vital. Derived denominators, partitions, and terminals are interpretable only after that vital passes; a zero-denominator terminal without a passing vital is invalid.
- r12 sham vitals pass: stable grasp `16/16` (required `14`), stage reach `16/16`, and parameter vitals `16/16`. P2 smoke passes F00/F05/F10; calibration completes 288/288 unique stable-grasp rows.
- The calibration gradient is owner-proxy admission only: all-window medians are ordered F00 `0.0828638` > F05 `0.0817359` > F10 `0.0799669`, with 78/96 strictly ordered matched triples, while the model-valid medians are not monotonic. `strong_model_evidence=false`; this authorizes only the registered F3 pilot.

## P2 r12 post-F3 terminal closure

- F3 training smoke passed for FULL and RP0. Four production cells (FULL/RP0 × seeds 0/1) each completed `4096 env × 500 batches`, exit `0`, with distinct final `model_step_000500.pt` checkpoints.
- Runtime measurement defects were retained as additive blocked/inconclusive receipts. Clipped negative residual margin is now valid zero additional capacity; direction exclusions retain finite modeled torque/lambda; non-admissible fallback selection requires complete measurement vitals. None of these repairs selects on the lambda/E1 outcome.
- Final retry5 evaluation completed four cells × 16 canonical F05/cap20 episodes, all exit `0`. The canonical population has 64 unique completed rows and 64/64 valid model, grasp, and foot source vitals.
- Admitted sustained-E1 counts are FULL seed0 `5`, FULL seed1 `1`, RP0 seed0 `3`, and RP0 seed1 `3`, versus the preregistered minimum `8` in every cell.
- Final typed result is exactly `V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3`, `terminal=true`, `P3_ADMITTED=false`; heldout is `NOT_ADMITTED_BY_POST_F3_TERMINAL`. P3/Wave 1/Route A/B/RQ3/Wave 2 stop without execution. The measurement-only RQ4 closure remains separately pending under R1 F3.
- Authority remains `MODELED_FROM_PARAMS` for door friction/model torque, `solver_applied=false`, and `ESTIMATE_ONLY_DIRECTIONAL_MARGIN` for capacity/lambda. Missing/excluded/blocked states are not numeric zeroes.
- Canonical evidence root: `logs_eval/base_v24/p2/force_boundary/r12/`. Final report: `scriptsFORhuman/v24/a2_piper_base_v24_p2_r12_final_adjudication_20260818.md`.
