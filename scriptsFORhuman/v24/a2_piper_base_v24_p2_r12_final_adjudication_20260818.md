# DoorDog A2+PiPER base_v24 P2 r12 Final Adjudication (2026-08-18)

## Outcome

The valid r12 post-F3 typed outcome is:

`V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3`

This is a legitimate scientific terminal: `terminal=true`, `P3_ADMITTED=false`, and the P2 heldout lifecycle is `NOT_ADMITTED_BY_POST_F3_TERMINAL`. It does not invoke the Phase 3 owner-decision point `V24_FRICTION_AXIS_NONDISCRIMINATIVE`, because P3 was never admitted.

The r10 result remains immutable historical evidence but is reclassified by the Owner decision as `SUSPECTED_INVALID_MEASUREMENT_PENDING_VITALS`; it is not the scientific terminal used here.

## Decision lineage

- `DoorDog_v24_owner_decision_d_gate_revision_20260817.md` replaced the unmeasurable literal-D gate with D-v2 and admitted P2 after `V24_FRICTION_MODEL_VALID_BEHAVIORAL`.
- `DoorDog_v24_owner_decision_p2_invalid_measurement_20260817.md` reclassified the r10 zero-denominator result and added the Rule16 sham/easy-vitals gate.
- r12 passed Rule16 before calibration: sham grasp `16/16` (required `14`), stage reach `16/16`, and parameter vitals `16/16`.
- The registered marginal-E1 pilot required four `4096 env × 500 batch` cells followed by exactly 16 canonical F05/cap20 episodes from each final step500 checkpoint. Each cell required at least eight admitted sustained-E1 windows.

## Executed runtime

| Runtime | Result |
|---|---|
| Rule16 sham vitals | PASS, 16/16 grasp, stage reach, and parameter vitals |
| P2 smoke | PASS for F00/F05/F10 |
| Calibration | 288/288 unique completed rows; all stable-grasp windows; 31 model-valid under the pre-pilot measurement semantics |
| Gradient admission | `PASS_OWNER_PROXY_ADJUDICATED`; `strong_model_evidence=false` |
| F3 training smoke | FULL and RP0, 64 env × 10 batches, exit 0 |
| F3 production | FULL/RP0 × seeds 0/1, 4096 env × 500 batches, all exit 0 |
| Final checkpoints | Four distinct `model_step_000500.pt` checkpoints |
| Final post-training evaluation | Four cells × 16 episodes, all exit 0; 64/64 unique completed source-valid rows |

The F3 production checkpoints are:

- `logs_rl/a2_piper_full_stage_a2_base/v24/r12/f3_marginal_e1/production_retry5/DF1_FULL_SEED0/model_step_000500.pt`
- `logs_rl/a2_piper_full_stage_a2_base/v24/r12/f3_marginal_e1/production_parallel1/DF1_FULL_SEED1/model_step_000500.pt`
- `logs_rl/a2_piper_full_stage_a2_base/v24/r12/f3_marginal_e1/production_parallel1/DF1_RP0_SEED0/model_step_000500.pt`
- `logs_rl/a2_piper_full_stage_a2_base/v24/r12/f3_marginal_e1/production_parallel1/DF1_RP0_SEED1/model_step_000500.pt`

## Measurement repair provenance

Blocked and interrupted attempts were retained additively and were never interpreted as scientific zeroes.

The final post-evaluation path fixed three concrete measurement defects exposed by runtime:

1. A negative estimated residual directional margin under command clipping had been typed as unavailable. The valid capacity is zero additional margin, with clipping retained explicitly; it is not missing telemetry.
2. `DIRECTION_EXCLUDED` transitions had also replaced the observable modeled torque with NaN. r12 now retains finite modeled torque and lambda while preserving the scientific direction exclusion, so excluded rows cannot enter E1.
3. A non-grasp fallback selected the first alpha-valid window even when it contained transient foot-vital unavailability. The exporter now selects the first measurement-valid fallback while retaining `excluded_grasp` and `excluded_window_selection`.

These repairs change measurement validity only. Window selection never uses the lambda band and therefore does not select on the E1 outcome.

## Final population and gate

| Cell | Completed/source-valid | Stable-grasp | Selection-valid | Admitted sustained E1 | Required |
|---|---:|---:|---:|---:|---:|
| DF1_FULL_SEED0 | 16/16 | 16 | 16 | 5 | 8 |
| DF1_FULL_SEED1 | 16/16 | 16 | 16 | 1 | 8 |
| DF1_RP0_SEED0 | 16/16 | 16 | 16 | 3 | 8 |
| DF1_RP0_SEED1 | 16/16 | 15 | 15 | 3 | 8 |

The population contains 64 unique completed windows and 12 admitted sustained-E1 windows in total, but the preregistered gate is per cell. Every cell is below eight, so promotion is forbidden and `V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3` is required.

## Authority

- Door friction and required-torque fields use `MODELED_FROM_PARAMS`.
- `solver_applied=false`; no report claims solver-applied friction torque.
- Directional capacity and lambda remain `ESTIMATE_ONLY_DIRECTIONAL_MARGIN`.
- Actual generalized torque remains unavailable and unused.
- Missing, excluded, blocked, and not-run states are never converted to numeric zeroes.

## Canonical r12 evidence

- `logs_eval/base_v24/p2/force_boundary/r12/vitals/P2_SHAM_VITALS_RECEIPT.json`
- `logs_eval/base_v24/p2/force_boundary/r12/smoke/P2_SMOKE_RECEIPT.json`
- `logs_eval/base_v24/p2/force_boundary/r12/calibration/P2_CALIBRATION_RECEIPT.json`
- `logs_eval/base_v24/p2/force_boundary/r12/V24_P2_LADDER_FREEZE.json`
- `logs_eval/base_v24/p2/force_boundary/r12/V24_P2_CERTIFICATE_THRESHOLD_FREEZE.json`
- `logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/P2_MARGINAL_E1_PILOT_REGISTRATION.json`
- `logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/P2_MARGINAL_E1_STEP500_CHECKPOINTS.json`
- `logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/post_training_eval_retry5/`
- `logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/P2_MARGINAL_E1_PILOT_POPULATION.jsonl`
- `logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/P2_MARGINAL_E1_PILOT_ADJUDICATION.json`
- `logs_eval/base_v24/p2/force_boundary/r12/marginal_e1/P2_MARGINAL_E1_POST_PILOT_FINALIZATION.json`

## Stop boundary

P2 heldout, P3, Wave 1, Route A/B, RQ3, and Wave 2 are not admitted. No training-wave, causal posture-value, E2, release, or solver-applied-torque claim is made. The already completed P0 descriptive posthoc remains valid. The separate R1 F3 measurement-only RQ4 deliverable subsequently closed as `V24_COUPLING_FORWARD_PROXY_ONLY`; see `scriptsFORhuman/v24/a2_piper_base_v24_rq4_measurement_only_20260818.md`.
