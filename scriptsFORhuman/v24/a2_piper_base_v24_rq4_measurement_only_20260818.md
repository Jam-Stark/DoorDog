# DoorDog A2+PiPER base_v24 RQ4 Measurement-only Closure (2026-08-18)

## Outcome

RQ4 closes with:

- `V24_COUPLING_FORWARD_PROXY_ONLY`
- `V24_COUPLING_CRITIC_UNCALIBRATED`

This is an executed descriptive measurement, not an identified arm–base–foot coupling signal. The P2 terminal `V24_E1_DENOMINATOR_INSUFFICIENT_POST_F3` stopped the science wave before the registered base-neutral × arm-safe-hold interventions, and the r12 rows do not expose the full RQ4 telemetry contract.

## Population and pairing

- Source: the canonical 64-row r12 post-F3 population.
- Source vitals: 64/64 model, grasp, and foot-slip sources valid.
- Pairing: 32 FULL–RP0 pairs matched within training seed and scenario.
- Stable grasp: FULL 32/32; RP0 31/32.
- Admitted sustained-E1 windows: FULL `6`, RP0 `6`, but every registered cell remains below the required per-cell denominator of eight.

The pairing is chronic and descriptive. It is not an acute posture intervention and cannot be treated as an exact or forward local counterfactual.

## Available proxy deltas

Values are pooled FULL minus RP0 medians across 32 matched seed/scenario pairs. Sign counts report how many pairs are negative/positive; they are descriptive only.

| Proxy | Median delta | Negative / positive / zero |
|---|---:|---:|
| directional utilization | `-0.3771484` | 24 / 8 / 0 |
| directional clip fraction | `-0.20` | 20 / 11 / 1 |
| modeled required torque | `-5.618907 N·m` | 23 / 9 / 0 |
| hinge progress over window | `-0.0110707 rad` | 19 / 13 / 0 |
| max loaded-foot slip | `+0.0564594 m/s` | 14 / 18 / 0 |

These mixed chronic differences do not isolate a coupling mechanism. In particular, lower utilization/clipping in FULL occurs together with lower median hinge progress, while the slip sign is mixed. Policy visitation, posture, reach, and load are not experimentally separated.

## Lambda handling

Continuous lambda differences are not used as an effect size. When estimated additional directional capacity is zero, the frozen `1e-6` denominator creates epsilon-dependent million-scale lambda values. r2 therefore reports only frozen zones and right-censor counts.

- Epsilon-right-censored rows: FULL seed0 `0`, FULL seed1 `0`, RP0 seed0 `6`, RP0 seed1 `6`.
- Pair zones include 11 `E0_PROXY → ABOVE_BOUNDARY_RIGHT_CENSORED` cases and only two `E1_BAND → E1_BAND` cases.

The superseded r1 continuous-lambda summary remains additive failure provenance and is not used scientifically.

## Telemetry authority boundary

| Group | Available | Unavailable |
|---|---|---|
| arm | estimated directional utilization, clipping, lambda zone | actual generalized torque, joint power, handle wrench |
| base/leg | none | acceleration/rates, leg action/torque/power, support polygon |
| feet | max loaded-foot slip | 3D GRF, normal/tangential force, friction utilization, contact duration, CoP |
| door | modeled required torque, hinge progress, modeled friction parameters | solver-applied friction torque, door work/power |

Door/model torque authority is `MODELED_FROM_PARAMS`; capacity is `ESTIMATE_ONLY_DIRECTIONAL_MARGIN`; `solver_applied=false`.

## Why the critic was not trained

The registered shadow critic requires intervention-derived vector targets for hinge progress, arm saturation, foot slip, support margin, grasp retention, clearance, and unsafe contact. The 2×2 forward intervention was not admitted, base/leg and 3D foot-force targets are unavailable, and per-cell E1 denominators are insufficient. Training a critic on the chronic proxy pairs would manufacture a target not authorized by R1.

## Canonical evidence

- `logs_eval/base_v24/rq4/measurement_only/r2/V24_RQ4_COUPLING_PAIR_ROWS.jsonl`
- `logs_eval/base_v24/rq4/measurement_only/r2/V24_RQ4_COUPLING_MEASUREMENT.json`
- `logs_eval/base_v24/rq4/measurement_only/r1/RQ4_R1_SUPERSEDED_RECEIPT.json`

No P3, Wave 1, Route A/B, RQ3, shadow-critic training, or Wave 2 runtime was performed. No causal coupling or posture-force-value claim is made.
