---
name: base-v24-friction-force-boundary
scope: A2+Piper base_v24 friction-calibrated force boundary, posture final adjudication, coupling groundwork, and gated-posture pilot
status: complete_p1_authority_stop
last_updated: 2026-08-17 00:01 HKT
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

## Final P0 Runtime and P1 H/I Closure

- R8-QA6 completed on physical GPU0 with exit `0` in `443.9 s`. It compares 7,326 canonical16 first-episode rows at seed0 under policy-only loading: actor observation 133-D, raw action mean 12-D, and post-environment/final action 24-D. All four float max-absolute differences are `0.0`; done and terminal facts are exact. The 16 default-off reset receipts are `DEFAULT_OFF_NO_WRITE`.
- The current public `contact_sensor` foot-force source is finite `(16,4)` and ordered `FL/RL/FR/RR` on the z axis. The direct baseline getter is typed unavailable, with no numeric payload and no zero fill.
- H reset persistence passes with native profile `1.0/0.75/0.0`: 16 terminal receipts comprise 10 ordinary plus six legitimate nonzero production snapshots for env `2/4/5/7/8/13`, stages `4/4/3/4/5/4`, each with sample count `1`. Sentinel/write readback and configured post-reset readback both pass.
- Final A–I typed outcome is exactly `V24_FRICTION_AUTHORITY_INSUFFICIENT`. A–C and E–I pass within their stated qualifications; D has only a passing behavioral dissipation proxy because literal solver friction-torque authority is unavailable. This is never `MODEL_VALID` and makes no actual generalized-torque claim.
- Parameter-range freeze is `NOT_PERFORMED_STOPPED_AT_P1_AUTHORITY_GATE`. P2, P3, Wave 1, Route A/B, RQ3/RQ4, shadow critic, and Wave 2 are `NOT_ADMITTED`; Phase 3 F2 and its user decision point were not reached, so no owner decision is required.

## Reusable Runtime Gotchas

- The custom `DoorSpawner` uses the `omni.usd` context stage; do not route this fixture through `create_stage_in_memory`.
- Closing the Isaac application in `finally` can mask the original traceback and exit code; preserve producer failure evidence before application close.
- `ArticulationData.default_mass` requires integer CPU indexing, while joint buffers require device-resident `env_ids`; do not reuse CUDA `env_ids` for the mass readback.
- After `set_simulation_dt`, hard-reset and run `scene.update` before reusing the articulation.
- The eval-agent policy-only path requires `a2_v23_p06_policy_only=true`; explicitly disable the unrelated inherited v20 R2 exporter for this non-R2 workflow.
- Do not pre-create the exact producer work-root. Avoid function-local imports that shadow module bindings before trace serialization.
- QA1–QA5 are retained only as non-admissible implementation/runtime failure provenance; the final admissible pass is R8-QA6.

## DONE Summary

Memory routing and the v24 authority/starting-fact skeleton are established. P0.1/P0.2, P0 runtime parity/foot detection, P1A, P1 A–G, and P1 H/I are complete with their scoped runtime evidence. The terminal P1 result is `V24_FRICTION_AUTHORITY_INSUFFICIENT`; parameter freeze is not performed and no model, training, causal, release, or downstream-phase admission is recorded.

## TODO Summary

There is no active base_v24 work under R1. Reopening any downstream work requires a newly authorized plan and new authority; it is not a current TODO.
