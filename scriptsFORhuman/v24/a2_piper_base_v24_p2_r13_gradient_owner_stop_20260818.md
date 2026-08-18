# base_v24 P1-lite and P2 r13 Owner-stop adjudication (2026-08-18)

## Outcome first

The Owner-approved one-time friction-domain escalation executed through the registered r13 gradient gate and stopped there. No F3-prime training, P3 scan, Wave 1, Route A/B, RQ3, or Wave 2 runtime was launched.

The immutable registered gradient artifact emits `V24_FRICTION_AXIS_NONDISCRIMINATIVE` and requires an Owner decision. Its sole failing predicate is matched per-scenario modeled required-torque ordering: `47/96`, below the registered `72/96` minimum.

This typed artifact must not be paraphrased as “no behavioral friction gradient.” The same complete population shows a strong behavioral gradient: median opening progress decreases strictly from P02 `0.0611846` to P05 `0.0569030`, P10 `0.0485871`, and P20 `0.0389161 rad`; P02 exceeds P20 in `96/96` matched cap/scenario pairs; and the low-high median span is `0.0222685 rad`, above the frozen `0.02 rad` floor. Modeled required-torque medians also increase strictly (`27.3945`, `27.5752`, `28.4334`, `29.5670 N·m`). The Owner must therefore decide whether the registered matched modeled-torque predicate is controlling or over-constrains the intended “true gradient” semantic. No post-data gate rewrite was made.

## P1-lite magnitude validation

Controlling decision: `scriptsFORhuman/v24/DoorDog_v24_owner_decision_friction_domain_escalation_20260818.md`.

GPU0 P1-lite completed naturally with exit `0`. The full registered domain `tau_s={2,5,10,20} N·m`, dynamic/static ratio `0.75`, and zero viscous coefficient remained stable, so no domain contraction was used.

- A breakaway brackets are `[1.5,2.0]`, `[4.5,5.0]`, `[9.5,10.0]`, and `[19.5,20.0] N·m`, with literal containment at every profile and nondecreasing upper brackets.
- B kinetic-platform and C damping-distinction gates pass at every profile.
- E chatter passes at every profile with zero sign reversals and zero slip re-entries.
- G passes at P20 for A0 and A8. Realized fixture scaled distances are `1.9313e-07` and `1.2233e-07`, below `1e-4`.

Canonical evidence: `logs_eval/base_v24/p1/friction_backend/p1_lite_domain_escalation_r13_gpu0/`.

## Pre-data r13 registration

Before any r13 policy population was generated, the run froze:

- calibration grid: four escalated profiles x six arm caps x sixteen scenarios = 384 rows;
- E1 demand floor: `tau_required >= 2 N·m`;
- E1 capacity floor: `tau_available,directional >= 2 N·m`;
- lambda rule: invalidate below the capacity floor with no numeric clamp;
- typed capacity collapse: `CAPACITY_COLLAPSED_WINDOW`, excluded from E1 and counted separately for the RQ3 reach-mediator interpretation;
- F3-prime denominator: 32 episodes per FULL/RP0 x seed0/1 cell, requiring at least eight sustained-E1 windows in every cell;
- Rule17 candidate: parameter-domain freezes require a repository-evidence magnitude anchor. Here the anchor is the v22 solvable `24 N·m` drive-resistance face, used only as a magnitude anchor and not as a claim of friction equivalence.

Artifacts: `V24_P2_R13_PARAMETER_AND_E1_FREEZE.json` and `V24_P2_R13_F3_PRIME_REGISTRATION.json` under the canonical r13 root.

## Rule16, smoke, and calibration

Rule16 passed before calibration: sham F00 stable grasp `16/16` (required `14`), stage reach `16/16`, and parameter vitals `16/16`. The P02/P10/P20 smoke completed naturally with exit `0` and is non-evidentiary.

The formal GPU0 calibration completed naturally with exit `0` and produced exactly `384/384` unique rows. All 384 rows have stable grasp, stage reach, parameter vitals, and available model/grasp sources.

The r13 denominator protection worked as registered:

- `358/384` windows are typed `CAPACITY_COLLAPSED_WINDOW` and never receive a numeric lambda for admission;
- `26/384` windows retain finite admissible lambda, with range `0.0532308..0.738496` and median `0.153469`;
- no r12-style epsilon-denominator lambda explosion enters the admission path;
- E-region counts are P02 `E0=6, E1=2, collapsed=88`; P05 `E0=6, E1=0, collapsed=90`; P10 `E0=7, E1=0, collapsed=89`; P20 `E0=5, E1=0, collapsed=91`.

Because the registered gradient artifact is terminal and the ladder prerequisites are not met, `tau_hi`, `tau_boundary`, and `tau_rescue` remain null, the E-region freeze is `NOT_ADMITTED`, and F3-prime is not launched.

Canonical evidence: `logs_eval/base_v24/p2/force_boundary/r13/`.

## Authority and immutability

All door friction and modeled door-torque fields retain `MODELED_FROM_PARAMS`; `solver_applied=false`; directional capacity/lambda authority is `ESTIMATE_ONLY_DIRECTIONAL_MARGIN`. No solver-applied friction torque or actual generalized torque is claimed.

All r10, r11, and r12 receipts remain unchanged. The r13 artifacts are additive. GPU0 is released, and no v24 r13 tmux session remains.

## Required Owner decision

Choose whether the registered `47/96 < 72/96` matched modeled-torque predicate should control the semantic terminal despite the complete, monotone, `96/96` behavioral progress gradient. Until that decision is supplied, F3-prime and all downstream science remain stopped.
