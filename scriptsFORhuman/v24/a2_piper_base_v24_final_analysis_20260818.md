# base_v24 final analysis (2026-08-18)

## Final outcome

base_v24 is closed at the Owner-registered terminal `V24_E1_DENOMINATOR_INSUFFICIENT_FINAL`.

The escalated friction axis is physically real and behaviorally discriminative, but the frozen behavioral E1 classifier did not yield at least eight sustained-E1 windows in every F3-prime cell. The valid counts are FULL seed0 `4`, FULL seed1 `1`, RP0 seed0 `8`, and RP0 seed1 `4`, from 32 completed boundary episodes per cell. Per the controlling Owner decision, this is the final denominator result: no further gate revision is permitted, and P3, Wave 1, Route A/B, RQ3, and Wave 2 are not admitted.

This result does **not** mean that the friction axis is null, that the simulator failed to apply the requested friction parameters, or that roll/pitch has no force value. It means that the one permitted parameter-domain escalation established a real friction response, yet the registered training/evaluation population did not realize a dense, replicated E1 region across all four policy cells. RQ3 posture force value therefore remains unresolved rather than negative.

## Artifact/evidence distinction

The historical r13 registered artifact remains unchanged and still says `V24_FRICTION_AXIS_NONDISCRIMINATIVE` because matched modeled required torque was strictly ordered in only `47/96` pairs, below its registered `72/96` gate.

The 2026-08-18 Owner adjudication rules that predictor non-controlling. Modeled required torque contains speed- and acceleration-dependent terms, while the policy slows as friction rises; the resulting dynamic-term compensation invalidates the assumed per-scenario monotonicity. The predictor is therefore retained only as `MODELED_TAU_MATCHED_ORDERING_CONFOUNDED_BY_SPEED_ADAPTATION`.

The new additive artifact reports `V24_FRICTION_AXIS_DISCRIMINATIVE_BEHAVIORAL`. Its evidence is:

- P1-lite breakaway literal containment passes at requested static friction `2`, `5`, `10`, and `20 N·m`;
- median opening progress decreases strictly P02 `0.0611846` > P05 `0.0569030` > P10 `0.0485871` > P20 `0.0389161 rad`;
- P02 progress exceeds P20 in `96/96` matched cap/scenario pairs;
- the low-high median span is `0.0222685 rad`, above the frozen `0.02 rad` floor.

The old artifact says what its historical gate computed; the new artifact says how the Owner adjudicated that gate's scientific validity. Neither file is rewritten.

## Behavioral E-region freeze

The numerical classifier was frozen before any F3-prime population existed, using only the complete r13 sham/calibration evidence:

- behavior deficit = same-checkpoint, same-scenario F00/cap40 progress minus evaluated progress;
- `delta_lo = 0.020 rad`, `delta_hi = 0.040 rad`;
- load-bearing high effort = directional clip fraction `>=0.40` **and** directional utilization `>=0.50`;
- E0 = valid grasp/source, deficit below `delta_lo`, and no load-bearing high effort;
- E1 = valid grasp/source, deficit in `[delta_lo, delta_hi]`, and load-bearing high effort;
- near-E2 candidate = valid grasp/source, deficit above `delta_hi`, and sustained high effort;
- confirmed E2 still requires the registered rescue counterfactual and is never inferred by this classifier.

The non-null ladder is `tau_hi=40`, `tau_boundary=20`, and `tau_rescue=25 N·m`. The boundary face is P10/cap20; the near-E2 candidate face is P20/cap20. Calibration supplied E0 count `8/16` at P02/cap40, E1 count `7/16` at P10/cap20, and near-E2 count `8/16` at P20/cap20.

The earlier min-over-joints directional-capacity estimator collapsed in `358/384` calibration windows while the door still opened. It is therefore typed `CAPACITY_ESTIMATOR_LOWER_BOUND_DEGENERATE`; lambda/capacity remain `ESTIMATE_ONLY_REPORT_ONLY`, and `CAPACITY_COLLAPSED_WINDOW` remains an RQ3 mediator field rather than an E-region admission gate. This is an RQ4 measurement finding, not a solver-applied torque claim.

## F3-prime execution

FULL and RP0 `64 env x 10 batch` smoke runs both exited `0` and wrote step10 checkpoints. Four production cells then ran concurrently on physical GPU0-3:

| Cell | Topology | Runtime result | Final checkpoint |
|---|---:|---|---|
| DF1_FULL_SEED0 | 4096 env x 500 batches | exit 0 | step500 present |
| DF1_FULL_SEED1 | 4096 env x 500 batches | exit 0 | step500 present |
| DF1_RP0_SEED0 | 4096 env x 500 batches | exit 0 | step500 present |
| DF1_RP0_SEED1 | 4096 env x 500 batches | exit 0 | step500 present |

Each final checkpoint first ran its own Rule16 F00/cap40 canonical16 sham vital. All four cells passed with `16/16` stable-grasp/stage-valid episodes and `16/16` parameter vitals, above the required `14/16`. Only then did each checkpoint run 32 P10/cap20 boundary episodes. All eight eval processes exited `0`, and the final population contains exactly 128 unique completed, source-valid, stable-grasp windows.

| Cell | E0 | E1 | near-E2 candidate | Unclassified | Invalid measurement |
|---|---:|---:|---:|---:|---:|
| DF1_FULL_SEED0 | 20 | 4 | 1 | 7 | 0 |
| DF1_FULL_SEED1 | 23 | 1 | 0 | 8 | 0 |
| DF1_RP0_SEED0 | 5 | 8 | 3 | 16 | 0 |
| DF1_RP0_SEED1 | 12 | 4 | 1 | 15 | 0 |

Because three cells are below the registered minimum eight, the typed final is `V24_E1_DENOMINATOR_INSUFFICIENT_FINAL`, `terminal=true`, and `P3_ADMITTED=false`. Missing, blocked, or invalid measurements were not converted to zero; the terminal is supported by passing same-checkpoint vitals and a complete valid population.

## Downstream disposition

- P3 historical zero-sample scan: `NOT_ADMITTED_BY_FINAL_E1_DENOMINATOR`.
- Wave 1 and Route A/B: not launched.
- RQ3 posture force-value adjudication: `UNRESOLVED_NOT_ADMITTED`.
- RQ4: prior `V24_COUPLING_FORWARD_PROXY_ONLY` remains valid; r13 additionally records `CAPACITY_ESTIMATOR_LOWER_BOUND_DEGENERATE`. No shadow critic is trained.
- Wave 2a/2b: not launched because E1 is not established across cells.
- Release: none.

## Authority and durable rules

Door friction and modeled door torque remain `MODELED_FROM_PARAMS`; `solver_applied=false`; actual generalized torque is `UNAVAILABLE_NOT_USED`. State and behavioral progress use high-level articulation data. No report claims solver-applied friction torque.

Rules 16 and 17 are now empirical project rules, and Rule18 is added as a durable candidate:

1. calibration/evaluation denominators and terminals require same-checkpoint easy/sham measurement-vitals admission;
2. every parameter-domain freeze must cite a repository-evidence magnitude anchor;
3. a gate on a derived quantity must first establish the monotonicity/validity assumption it requires, otherwise that quantity is report-only.

## Canonical evidence

- `logs_eval/base_v24/p2/force_boundary/r13/behavioral_reentry/V24_P2_R13_BEHAVIORAL_GRADIENT_ADJUDICATION.json`
- `logs_eval/base_v24/p2/force_boundary/r13/behavioral_reentry/V24_P2_R13_BEHAVIORAL_LADDER_FREEZE.json`
- `logs_eval/base_v24/p2/force_boundary/r13/behavioral_reentry/V24_P2_R13_BEHAVIORAL_E_REGION_FREEZE.json`
- `logs_eval/base_v24/p2/force_boundary/r13/behavioral_reentry/P2_R13_F3_PRIME_BEHAVIORAL_ADJUDICATION.json`
- `logs_eval/base_v24/p2/force_boundary/r13/behavioral_reentry/P2_R13_F3_PRIME_FINALIZATION.json`
- `logs_eval/base_v24/final/V24_FINAL_ANALYSIS.json`

All prior r10-r13 receipts and adjudication artifacts are preserved unchanged. Runtime outputs are local; no push is performed.
