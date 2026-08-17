---
name: base-v24-friction-force-boundary
scope: A2+Piper base_v24 friction-calibrated force boundary, posture final adjudication, coupling groundwork, and gated-posture pilot
status: p2_terminal_e1_denominator_insufficient_p3_not_admitted
last_updated: 2026-08-17 08:34 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v24-friction-force-boundary/description.md
  - memory/a2-piper/base-v24-friction-force-boundary/TODO.md
  - memory/a2-piper/base-v24-friction-force-boundary/DONE.md
read_when:
  - implementing, executing, or adjudicating base_v24 P0 through final analysis
  - deciding friction GO/NO-GO, E-region admission, Wave 1/2 continuation, or final typed outcome
---

# base_v24 Friction-Calibrated Force Boundary

## Purpose

本 entry 保存 `base_v24` 可复用的单位契约、friction backend 与物理验收、方向性容量/E-region freeze、训练与评估 gate、RQ3/RQ4/Wave 2 typed 结论。live agent 状态、临时 finding 与等待 heartbeat 不写入这里。

## Authority and Scope

- Authority order: v24 worker prompt → `scriptsFORhuman/v24/a2_piper_base_v24_plan_R1_20260816.md` → `scriptsFORhuman/v24/a2_piper_v23_final_adjudication_20260816.md` → referenced pro feedback and v23 execution conventions.
- GPU lease is physical GPU0–3 only; GPU4–7 are out of scope. No push.
- Runtime/source changes are additive, `a2_v24_*` config-gated, default off. New utilities and receipts live under `scriptsFORhuman/v24/`; production runtime code uses a separate v24 module where needed.
- The only owner decision point is Phase 3 result `V24_FRICTION_AXIS_NONDISCRIMINATIVE`; all other covered outcomes follow the preregistered contingency nearest to the evidence.

## Frozen Starting Facts

- v23 final state is `V23_RESEARCH_PASS_NO_RELEASE`; posture force value remains `UNRESOLVED`, while reach/coordination value has medium support.
- v23 realized-dynamics classification failed because degree-surface readbacks were compared against rad-surface values; all v24 cross-artifact mechanics comparisons normalize to the rad surface through `DoorMechanicsUnitContractV1`.
- v23 posthoc is descriptive only and must audit actual intervention doses, keeping zero-dose records in the denominator.
- Friction Branch A is available through IsaacLab `Articulation.write_joint_friction_coefficient_to_sim(static, dynamic, viscous)` with per-env, per-joint tensors. The first physics runtime check is a door-only torque ramp proving requested static friction effort against measured breakaway.
- Frozen warm start is `logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt` (`A1_G7_seed0_step1500`); its provenance is `warm_head_reset` / D1 / seed0 / step1500.
- New formal, smoke, launcher, eval, render, and report artifacts follow the canonical `base_v24` log layout and keep each result folder as one evidence unit.

## Validation Boundary

Static inspection is not runtime proof. P1 requires the preregistered A–I physics acceptance, Phase 3 is the training GO/NO-GO, and each long task follows the gradient short-check protocol before a long sleep. Missing telemetry remains typed missing and is never filled with zero.

## P0.1 Unit Contract and v23 Descriptive Posthoc

- `DoorMechanicsUnitContractV1` and the descriptive v23 posthoc are complete. The source modules are `scriptsFORhuman/v24/_v24_common.py`, `p0_unit_contract.py`, and `p0_v23_posthoc.py`; canonical evidence root is `logs_eval/base_v24/p0/v23_posthoc/`.
- The posthoc realizes 768 records: 747 in-domain, 8 OOD, and 13 typed no-trace. Intervention accounting is `1280 = 256 × 5`; zero-dose records stay in the denominator.
- The temporal dose is a descriptive proxy because actual torque is unavailable. It reports `S_phi=0.0013917272` with `E0/E1=509/238`; `FP_phi=0.0517241379` with paired/high-use/false `180/116/6`, using the `0.02 rad` source band.
- Behavior counts are `HOLD=91`, `QUIET=535`, `UNSAFE=128`, `UNCLASSIFIED=14`, and `FLING=0`. These descriptive counts do not establish causal posture value or upgrade H3/H5.
- G7's provisional path is `warm_head_reset`, not `v22_warm`. This posthoc does not resolve warm-start selection/identity, establish static or runtime compatibility, or claim IsaacSim/runtime-training PASS.
- The frozen candidate has `CODE_QUALITY PASS` and a fresh CPU `NO_SIM PASS` (191.23s). The latter validates the bounded posthoc computation only; it is not an IsaacSim or training runtime result.

## P0.2 Checkpoint-start Freeze and Static Compatibility

- The checkpoint-start freeze is complete through `scriptsFORhuman/v24/p0_checkpoint_freeze.py`; canonical root is `logs_eval/base_v24/p0/checkpoint_freeze/`. It selects `A1_G7_seed0_step1500` at `logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt`, with `warm_head_reset` / D1 / seed0 / step1500 provenance.
- Eight FULL candidates were ranked with pairwise comparable-only criteria: typed missing data is skipped for that pair, never preferred for availability and never filled with zero. `A1_G7` versus `B1_G3` is unsafe-incomparable, tied on holdout and pooled measures, then decided by clearance `0.875 > 0.75`.
- Static compatibility is `V24_COMPATIBILITY_STATIC_COMPLETE_RUNTIME_PENDING` across five representative categories. The policy contract is 20 state-dict keys, RMS 133, two-layer LSTM with hidden size 256, and action dimension 12.
- Frozen-source `CODE_QUALITY PASS` and CPU `NO_SIM PASS` (~5.53s) validate the selection and static inspection. They did not establish IsaacSim parity; the later deterministic friction-off/gate-off runtime gate is closed by the R8-QA6 evidence below.

## P1A Native Friction and Door-only Torque Unit Probe

- Branch A native friction integration uses the high-level IsaacLab friction path and has static review plus unit-semantics runtime authority. The corrected R2 probe ran deterministically on physical GPU0 in a door-only fixture.
- Requested and native-readback static/dynamic/viscous friction are `1.0/0.75/0.0`. Independent 100-frame trials at command efforts `0.0`, `0.5`, and `1.0` measure breakaway bracket `[0.5, 1.0] Nm` at `0.5 Nm` resolution; strict literal containment is true. Stationarity, effort headroom, target cleanup, and friction readback pass.
- The command effort target is not actual generalized torque. This result is a door-only unit-semantics probe, not policy parity, production reset persistence, A–I physical characterization, training, release, or causal evidence.
- R1 remains a reusable gotcha: its cumulative 10-frame trajectory produced invalid `[1.5, 2.0]` and falsely widened containment by ±resolution. Do not widen bracket tolerance or infer static calibration from a cumulative post-motion trajectory; retain the R1 evidence as failure provenance.

## P1 A–G Physical Characterization

- GPU0 `A_I_ACCEPTANCE` runtime smoke is recorded at `logs_eval/base_v24/p1/friction_backend/a_g_acceptance_r9_gpu0/P1_A_G_RECEIPT.json`. A–G receipt semantics pass; its device is `cuda:0`, overall receipt status is `PENDING_H_I`, and parameter-range freeze is `NOT_PERFORMED`.
- A passes literal bracket containment: F00 and F05 are `[0, 0.5] Nm`, F10 is `[0.5, 1.0] Nm`. B passes the registered spread and direction-asymmetry limits. C passes both directional friction and damping ratios. E passes first-breakaway/chatter behavior; F is `PASS_QUALITATIVE_ONLY` for the base/fine-dt classification match.
- G passes all requested fixture gates using public normalized-rad readback. The observed scaled distances are `3.11e-08`–`2.26e-07`, all within the `1e-4` maximum.
- D cannot pass its literal `tau_friction * omega` target: solver friction-torque authority is unavailable, so only the behavioral proxy passes. The sole provisional typed boundary is `V24_FRICTION_AUTHORITY_INSUFFICIENT`; it is never `MODEL_VALID` and does not infer actual generalized torque.
- This A–G receipt itself was `PENDING_H_I`; subsequent P0/H/I runtime evidence and the terminal authority adjudication are recorded below. Its D boundary remains unchanged: the behavioral proxy is not literal D authority.

## Historical R1 P0 Runtime and P1 H/I Closure

- R8-QA6 completed on physical GPU0 with exit `0` in `443.9 s`. It compares 7,326 canonical16 first-episode rows at seed0 under policy-only loading: actor observation 133-D, raw action mean 12-D, and post-environment/final action 24-D. All four float max-absolute differences are `0.0`; done and terminal facts are exact. The 16 default-off reset receipts are `DEFAULT_OFF_NO_WRITE`.
- The current public `contact_sensor` foot-force source is finite `(16,4)` and ordered `FL/RL/FR/RR` on the z axis. The direct baseline getter is typed unavailable, with no numeric payload and no zero fill.
- H reset persistence passes with native profile `1.0/0.75/0.0`: 16 terminal receipts comprise 10 ordinary plus six legitimate nonzero production snapshots for env `2/4/5/7/8/13`, stages `4/4/3/4/5/4`, each with sample count `1`. Sentinel/write readback and configured post-reset readback both pass.
- Final A–I typed outcome is exactly `V24_FRICTION_AUTHORITY_INSUFFICIENT`. A–C and E–I pass within their stated qualifications; D has only a passing behavioral dissipation proxy because literal solver friction-torque authority is unavailable. This is never `MODEL_VALID` and makes no actual generalized-torque claim.
- Parameter-range freeze is `NOT_PERFORMED_STOPPED_AT_P1_AUTHORITY_GATE`. At this historical R1 terminal, P2, P3, Wave 1, Route A/B, RQ3/RQ4, shadow critic, and Wave 2 were `NOT_ADMITTED`; Phase 3 F2 and its user decision point were not reached.

## Owner D-v2 Behavioral Energy-accounting Revision

- The 2026-08-17 Owner decision `OWNER_GATE_REVISION_D_V2 + CONTINUE_FROM_P2` supersedes `FINAL_STOP_AT_P1` as the round terminal. It preserves the historical `V24_FRICTION_AUTHORITY_INSUFFICIENT` closure and its immutable receipts as provenance, while replacing literal D with D-v2 behavioral total mechanical energy accounting.
- Frozen D-v2 source/config review is `CODE_QUALITY PASS` and `ISAACLAB_SEMANTICS PASS`; these are static gates, not runtime proof. Fresh physical GPU0 / logical `cuda:0` producer runtime (seed `24017`, 19.814 s) and QA1 scientific/runtime validation pass. QA2 historical-input immutability is a metadata closure, not a new physical runtime result.
- D-v2 uses `I_model=36.1 kg*m^2`, `k=6 N*m/rad`, and `theta_ref=0.5 rad`. Both fresh F00 signs completed before tolerance freeze: `tol_step=9.93409096170439e-06 J` and `tol_cumulative=0.0008802263651532332 J`. Both F10 signs then completed 200 intervals (100 command + 100 coast): final D is `0.007680328808102447 J` for sign -1 and `0.007679495205304246 J` for sign +1. Raw-row continuity, motion, step/cumulative tolerance, final dissipation, readback, and cleanup checks pass.
- The verified typed result is exactly `V24_FRICTION_MODEL_VALID_BEHAVIORAL`; P2/P3 admission is true and this gate requires no owner decision. P2/P3 have not been executed.
- Authority remains explicit: door friction/model-torque fields are `MODELED_FROM_PARAMS`; solver friction torque is `UNAVAILABLE_NOT_USED`; command work is `COMMAND_EFFORT_TARGET_NOT_ACTUAL_GENERALIZED_TORQUE`. No actual generalized torque or solver-applied torque is claimed.
- Canonical additive artifacts are `logs_eval/base_v24/p1/friction_backend/d_v2_energy_r1_gpu0/D_V2_TOLERANCE_FREEZE.json`, `logs_eval/base_v24/p1/friction_backend/d_v2_energy_r1_gpu0/D_V2_ENERGY_RECEIPT.json`, `logs_eval/base_v24/p1/friction_backend/d_v2_energy_r1_gpu0/QA_SEMANTIC_VALIDATION.json`, and `logs_eval/base_v24/p1/final_adjudication/d_v2_r1/V24_P1_D_V2_FINAL_ADJUDICATION.json`.

## P2 Directional Capacity and Registered Terminal

- The P2 parameter-range freeze executed, followed by physical GPU0 producer smoke (`175.36 s`) and calibration (`2860.99 s`). Calibration produced 288 rows: six arm caps × three friction profiles × 16 paired scenarios. The foot source is `AVAILABLE` in 288/288 rows; `stable_grasp` is 0/288.
- Valid model/capacity rows are 42/288, with finite `tau`/`lambda` in 42/42. Valid loaded-foot slip windows are 0, so the frozen E0/E1 denominator counts are 0/0. `command_path_binding=true`; `tau_hi`, `tau_boundary`, and `tau_rescue` are null, and the registered contingency was not triggered.
- The exact terminal is `V24_E1_DENOMINATOR_INSUFFICIENT`, `terminal=true`, `P3_ADMITTED=false`. The heldout receipt is canonical zero-row `NOT_ADMITTED_BY_P2_TERMINAL`; P3 and Wave 1+ were not executed and stop automatically. This is a preregistered typed P2 terminal, not the Phase 3 nondiscriminative Owner decision.
- Runtime boundary: smoke and calibration are GPU0 producer evidence. The exact freeze → heldout → adjudicate → QA lifecycle is CPU `NO_SIM PASS`. The normal `>=8` / Q99 / full-heldout E-region path was not executed and is not a PASS claim.
- Authority remains `MODELED_FROM_PARAMS` for door friction/model torque with `solver_applied=false`; no solver-applied friction torque is claimed. Canonical P2 evidence is `logs_eval/base_v24/p2/force_boundary/r10/`.

## Reusable Runtime Gotchas

- The custom `DoorSpawner` uses the `omni.usd` context stage; do not route this fixture through `create_stage_in_memory`.
- Closing the Isaac application in `finally` can mask the original traceback and exit code; preserve producer failure evidence before application close.
- `ArticulationData.default_mass` requires integer CPU indexing, while joint buffers require device-resident `env_ids`; do not reuse CUDA `env_ids` for the mass readback.
- After `set_simulation_dt`, hard-reset and run `scene.update` before reusing the articulation.
- The eval-agent policy-only path requires `a2_v23_p06_policy_only=true`; explicitly disable the unrelated inherited v20 R2 exporter for this non-R2 workflow.
- Do not pre-create the exact producer work-root. Avoid function-local imports that shadow module bindings before trace serialization.
- QA1–QA5 are retained only as non-admissible implementation/runtime failure provenance; the final admissible pass is R8-QA6.

## DONE Summary

Memory routing and the v24 authority/starting-fact skeleton are established. P0.1/P0.2, P0 runtime parity/foot detection, P1A, P1 A–G, P1 H/I, Owner D-v2, and P2 are complete with scoped evidence. The historical R1 P1 terminal is preserved as `V24_FRICTION_AUTHORITY_INSUFFICIENT`; D-v2 passed behavioral energy accounting as `V24_FRICTION_MODEL_VALID_BEHAVIORAL`, admitting P2. P2 then reached the preregistered terminal `V24_E1_DENOMINATOR_INSUFFICIENT`: P3 is not admitted and downstream phases stop automatically. No training, causal, release, normal E-region, or solver-applied-friction-torque result is recorded.

## TODO Summary

There is no remaining active v24 execution under current R1: P2 terminal `V24_E1_DENOMINATOR_INSUFFICIENT` does not admit P3, and P3/Wave 1+ stop automatically. The normal `>=8` / Q99 / full-heldout E-region path remains unexecuted.
