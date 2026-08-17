# base_v24 Execution Ledger（2026-08-17）

## Authority

worker prompt → v24 R1 plan → v23 final adjudication → R1 imported pro feedback；2026-08-17 Owner D-v2 decision supersedes `FINAL_STOP_AT_P1` as the round terminal。GPU0–3 only；D-v2 与 P2 只使用 physical GPU0；无 push。

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
| P2 capacity/lambda/E-region | TERMINAL | `f0a3a44` | `V24_E1_DENOMINATOR_INSUFFICIENT`; `P3_ADMITTED=false` |
| P3 historical friction scan | NOT_ADMITTED | — | P2 registered terminal；未执行，不触发 Owner decision |
| Wave 1 / Route A/B | NOT_ADMITTED | — | P3 未准入；未执行 |
| RQ3/RQ4 / shadow critic | NOT_ADMITTED | — | P3/Wave 1 未准入；未执行 |
| Wave 2a/2b | NOT_ADMITTED | — | 前序 gate 未准入；未执行 |

## Runtime closure

- A–G GPU0 receipt: PASS within qualified gates; D remains literal authority-insufficient.
- Compatibility/H GPU0 R8-QA6: PASS, exit 0, 443.9 s.
- Parity: 7,326 rows; 133/12/24 dimensions; all float max-abs differences `0.0`; done/terminal exact.
- Foot: current source available `(16,4)`; baseline typed unavailable without numeric fill.
- Reset persistence: 16 receipts = 10 ordinary + 6 legitimate staged; sentinel/readback and configured post-reset readback PASS.
- Final typed result: `V24_FRICTION_AUTHORITY_INSUFFICIENT`.
- Owner decision: not requested. P2 已以注册终点阻断 P3；Phase 3 axis nondiscrimination 未执行，故唯一 Owner decision point 未触发。

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
- D-v2 准入后的 P2 已按下节完成并到达注册终点；本节不回写或替换任何旧 receipt。

## P2 registered terminal closure

- Stable product/evidence commit: `f0a3a44`。Canonical root：`logs_eval/base_v24/p2/force_boundary/r10/`；旧 r1–r8 receipt 保持不变且不作为裁决输入。
- Parameter-range freeze 已执行。Physical GPU0 smoke exit `0`（`175.36 s`）；calibration exit `0`（`2860.99 s`），得到 288 rows = 6 caps × 3 friction profiles × 16 paired scenarios。
- Foot source `AVAILABLE` 288/288；`stable_grasp` 0/288。有效 model/capacity rows 为 42/288，有限 `tau`/`lambda` 为 42/42；有效 loaded-foot slip window 为 0，E0/E1 denominator count 为 0/0。
- `command_path_binding=true`；`tau_hi_nm`、`tau_boundary_nm`、`tau_rescue_nm` 均为 null；contingency 未触发。正常 `>=8` / Q99 / full-heldout E-region 路径未执行，不声明该路径 PASS。
- CPU-only freeze → heldout → adjudicate → QA 全部 exit `0`，独立重算一致。Heldout 是 exact zero-row `NOT_ADMITTED_BY_P2_TERMINAL` receipt。
- Final typed result 仅为 `V24_E1_DENOMINATOR_INSUFFICIENT`，`terminal=true`、`P3_ADMITTED=false`、`owner_decision_required=false`。P3、Wave 1 及后续条件工作自动停止；这不是 `V24_FRICTION_AXIS_NONDISCRIMINATIVE` Owner decision point。
- Authority 保持：door friction/model torque 为 `MODELED_FROM_PARAMS`，`solver_applied=false`；不声称 solver-applied friction torque。
- 新 P2 裁决：`scriptsFORhuman/v24/a2_piper_base_v24_p2_final_adjudication_20260817.md`。
