# A2+Piper v23/v24 cloud Pro review brief (2026-08-20)

## Review setup

- Repository: `Jam-Stark/DoorDog`
- Branch: `A2_Piper`
- Supplementary archive: `DoorDog_A2_Piper_v23_v24_cloud_review_20260820.zip`
- The cloud reviewer cannot access the local IsaacSim production machine. Treat the Git branch as source/document authority and the ZIP as a curated, non-exhaustive runtime-evidence bundle.
- Do not infer that a file absent from the ZIP was absent from the local run. Raw step traces and checkpoints were deliberately excluded for size.

## Decision-authority map

Do not treat “the Planner” as one actor. Historical decisions came from four distinct layers:

1. **Cloud Planner / GPT Pro**: the two advisory reviews in `scriptsFORhuman/v24/pro feedback/pro1.md` and `pro2.md`. They proposed interpretations, physical gates and future experiment structure, but did not run the local environment and were not final authority.
2. **Local Planner / Claude Fable**: the local planning pass that reconciled the cloud reviews with repository/runtime evidence, wrote the v23 adjudication narrative and registered the v24 R1 protocol/gates. Its principal outputs are `a2_piper_v23_final_adjudication_20260816.md` and `a2_piper_base_v24_plan_R1_20260816.md`.
3. **Owner**: the user decisions that superseded defective local-plan gates after new evidence appeared. The D-v2 authority revision, Rule16 measurement-vitals revision, friction-domain escalation and r13 behavioral-gradient adjudication are Owner decisions, not GPT Pro or Claude Fable conclusions.
4. **Worker/Main session**: implemented and executed the currently controlling protocol, preserved old receipts and reported typed outcomes. A faithfully executed gate failure must not be attributed to the worker when a later Owner decision identifies the gate itself as defective.

For every reviewed conclusion, identify which of these four layers originated it, which later layer superseded it, and which immutable receipt actually supports it.

## Requested review outcome

Please independently audit the scientific interpretation of v23 and v24, rather than only checking whether their preregistered reducers were executed faithfully. Return:

1. which v23/v24 conclusions are supported, overstated, or still unresolved;
2. whether v24 chose the right physical intervention but the wrong initial magnitude/model, or whether the intervention itself was misdirected;
3. whether the symmetric `>=8 sustained-E1 windows in every FULL/RP0 x seed cell` admission gate is scientifically valid for testing posture benefit;
4. whether the observed FULL/RP0 E-region asymmetry is merely descriptive or is sufficient to justify a new causal experiment;
5. the smallest next-round door model and experimental design that can distinguish reach/coordination value from true posture force value;
6. a recommended teacher-facing narrative that does not overclaim fire-door realism, solver torque authority, FULL/RP0 equivalence, or a negative posture result.
7. a decision-history audit that separately scores: (a) historical GPT Pro advice, (b) Claude Fable's local synthesis/gate design, (c) Owner revisions, and (d) worker execution fidelity.

Please cite exact repository/ZIP paths for every material claim. Separate verified facts, inference, and recommendation.

## Read order in the repository

### Controlling adjudication and plans

1. `scriptsFORhuman/v24/a2_piper_v23_final_adjudication_20260816.md`
2. `scriptsFORhuman/v24/a2_piper_base_v24_plan_R1_20260816.md`
3. `scriptsFORhuman/v24/DoorDog_v24_worker_session_prompt_20260816.md`
4. `scriptsFORhuman/v24/a2_piper_base_v24_final_analysis_20260818.md`
5. `scriptsFORhuman/v24/a2_piper_base_v24_execution_ledger_20260817.md`
6. `memory/a2-piper/base-v23-force-feasibility/description.md`
7. `memory/a2-piper/base-v24-friction-force-boundary/description.md`

### Owner revisions that control v24 interpretation

1. `scriptsFORhuman/v24/DoorDog_v24_owner_decision_d_gate_revision_20260817.md`
2. `scriptsFORhuman/v24/DoorDog_v24_owner_decision_p2_invalid_measurement_20260817.md`
3. `scriptsFORhuman/v24/DoorDog_v24_owner_decision_friction_domain_escalation_20260818.md`
4. `scriptsFORhuman/v24/DoorDog_v24_owner_decision_r13_gradient_adjudication_20260818.md`

### Prior external review context

- `scriptsFORhuman/v24/pro feedback/pro1.md` — historical cloud GPT Pro review.
- `scriptsFORhuman/v24/pro feedback/pro2.md` — historical cloud GPT Pro review.

These are advisory cloud-Planner inputs, not controlling evidence. Identify any assumptions from them that Claude Fable carried into R1 without adequate empirical support.

### Historical local Planner outputs

- `scriptsFORhuman/v24/a2_piper_v23_final_adjudication_20260816.md` — Claude Fable's synthesis of local evidence and the historical cloud GPT Pro reviews.
- `scriptsFORhuman/v24/a2_piper_base_v24_plan_R1_20260816.md` — Claude Fable's registered local execution plan and gate structure.

Audit these independently from `pro1.md/pro2.md`. In particular, determine whether the null r12 friction magnitude, missing Rule16 vital, unobservable literal-D authority and symmetric per-policy E1 gate originated in the cloud advice, the local synthesis, or an interaction between them.

### Main implementation paths

- `gr00t/rl/envs/door/a2_v24_friction.py`: native hinge-friction backend.
- `gr00t/rl/envs/door/a2_v24_force_boundary.py`: P2/r13 force-window telemetry and evidence runtime.
- `gr00t/rl/envs/door/a2_v24_df1_sampler.py`: r12 F3 sampling.
- `gr00t/rl/envs/door/a2_v24_r13_f3_sampler.py`: final r13 F3-prime sampling.
- `gr00t/rl/envs/door/a2_v24_r13_f3_evidence.py`: final r13 post-training evidence.
- `gr00t/rl/envs/door/door_open_a2_base.py`: config-gated integration into the door task.
- `scriptsFORhuman/v24/p2_force_boundary.py`: P2 evaluator/reducer path.
- `scriptsFORhuman/v24/p1_friction_domain_escalation.py`: r13 P1-lite magnitude validation.
- `scriptsFORhuman/v24/p2_force_boundary_r13.py`: r13 calibration and original gradient gate.
- `scriptsFORhuman/v24/p2_r13_behavioral_reentry.py`: Owner-adjudicated behavioral classifier and F3-prime lifecycle.
- `scriptsFORhuman/v24/rq4_coupling_measurement.py`: measurement-only coupling proxy.
- `gr00t/rl/config/ablation/wbmanip/base_v24_p2_force_boundary_r13.yaml`
- `gr00t/rl/config/ablation/wbmanip/base_v24_r13_f3_behavioral_pilot.yaml`

## What v23 established

- Final typed state: `V23_RESEARCH_PASS_NO_RELEASE`.
- All 16 formal cells and downstream Route A/B, holdout and render workflows completed.
- Holdout had high task completion, so aggregate success was near a ceiling and did not identify mechanism.
- H1 only rejects the tested output-head-only inheritance route; it does not reject all recurrent/visitation inheritance.
- FULL/RP0 goal-level substitutability was suggested but did not pass the registered equivalence gate. Behavior was not identical: FULL had more crossing-while-holding and a strongly policy-dependent missing-release-event pattern.
- Realized E0/E1/E2 analysis was invalidated by a degree/radian surface mismatch. H3/H5 remained unadjudicated.
- The v23 door used a linear stiffness/damping drive with a `24 N*m` maximum drive output. Damping could be reduced by policy slowing, and confirmed E2 remained zero. This was not a validated heavy fire-door model.
- The 20--100 N*m arm-cap ladder was inconclusive: clipping increased as cap fell, but the selected stable-grasp short-window progress probe barely changed. This does not prove that task demand was below 20 N*m.

## What v24 established

### Friction location and authority

- Friction was written only to the door hinge joint, never to the handle joint. Handle-side force numbers are lever-arm equivalents only.
- Static/dynamic/viscous requested values and high-level readback were validated. Door friction/model-torque fields remain `MODELED_FROM_PARAMS`; solver-applied generalized friction torque was unavailable and must not be claimed.
- D-v2 behavioral energy accounting passed as `V24_FRICTION_MODEL_VALID_BEHAVIORAL`; this is behavioral model validity, not direct solver-torque measurement.

### r12 magnitude failure

- r12 used static friction `0/0.5/1.0 N*m`. Owner later ruled this a null magnitude axis relative to the repository's already solvable `24 N*m` drive-resistance face.
- Therefore r12 only supports “no force boundary within 0--1 N*m,” not “friction cannot establish a force boundary.”

### r13 magnitude escalation and behavioral response

- r13 validated static friction `2/5/10/20 N*m`, dynamic/static ratio `0.75`, without numerical contraction.
- On the same frozen v23 G7 `HI_FULL` checkpoint, with roll/pitch available, median stable-grasp window progress decreased strictly:
  `0.0611846 > 0.0569030 > 0.0485871 > 0.0389161 rad`.
- Low-friction progress exceeded high-friction progress in `96/96` matched cap/scenario pairs. Owner therefore adjudicated `V24_FRICTION_AXIS_DISCRIMINATIVE_BEHAVIORAL`.
- This establishes that friction changed short-window opening behavior. It does not establish episode failure, fire-door realism, or posture benefit.

### FULL/RP0 training and final stop

- F3-prime trained four cells: FULL/RP0 x seed0/1, each `4096 env x 500 batches`.
- FULL left roll/pitch available; RP0 fixed action indices `[3,4]` to zero.
- Same-checkpoint Rule16 sham vitals passed `16/16` in all four cells.
- At P10/cap20, 32 boundary episodes per cell yielded sustained-E1 counts:
  FULL seed0 `4`, FULL seed1 `1`, RP0 seed0 `8`, RP0 seed1 `4`.
- Because the registered minimum was `>=8` in every cell, the final state was `V24_E1_DENOMINATOR_INSUFFICIENT_FINAL`. P3, Wave 1, Route A/B and RQ3 were not admitted.
- v24 therefore did train both posture conditions, but did not complete the causal test of whether allowing roll/pitch mitigates friction load. Posture force value remains `UNRESOLVED_NOT_ADMITTED`, not negative.

## Current scientific pain points to audit

### 1. Force-boundary instrument versus realistic door model

Native hinge friction is a useful stress axis because it cannot be eliminated merely by slowing. However, using up to `20 N*m` of Coulomb-like hinge friction is not equivalent to modeling a real heavy closer or fire door. A more realistic resisting torque likely needs separately identified components:

`tau_resist = tau_closer(theta) + c(theta, omega)*omega + tau_breakaway + tau_seal/pressure(theta) + tau_latch(theta)`.

The next round should not simply increase damping or reinterpret all closer torque as dry hinge friction. It needs a repository- or manufacturer-evidence target torque-angle-speed envelope.

### 2. Raw coefficient comparisons are misleading

Friction is reported in torque-like `N*m`, while damping is `N*m*s/rad` and produces `tau_d=c*omega`. Comparing `20` friction with `200` damping without an angular velocity is dimensionally invalid. Conversely, a very large damping coefficient can still be behaviorally avoidable when the policy slows.

### 3. Possible structural defect in the symmetric E1 admission gate

The final boundary population was asymmetric:

- FULL E0 counts: `20/32`, `23/32`;
- RP0 E0 counts: `5/32`, `12/32`;
- FULL sustained-E1: `4/32`, `1/32`;
- RP0 sustained-E1: `8/32`, `4/32`.

If roll/pitch genuinely helps a FULL policy turn a boundary episode into low-deficit E0 behavior, then requiring FULL to retain at least eight E1 windows may punish the hypothesis being tested. The gate may conflate “enough task-side load exposure” with “the policy remains behaviorally impaired.” This asymmetry is still confounded by seed, only 500 adaptation batches, and unequal unclassified counts, so it is descriptive rather than causal. Audit whether future admission should be task/door-side and policy-independent, or anchored on RP0 load density with matched scenarios.

### 4. Derived capacity estimator failure

The min-over-joints directional-capacity estimator collapsed in `358/384` calibration windows while the door continued opening. It was correctly demoted to `ESTIMATE_ONLY_REPORT_ONLY`. Audit whether this reflects a bad lower-bound construction, omitted base/leg/contact contribution, action-to-joint semantics, or an invalid single-arm directional model.

### 5. Missing physical observables

The project did not directly observe solver-applied hinge friction torque, handle wrench, full 3-D ground-reaction force, or complete base/leg load transfer. Existing RQ4 evidence is `FORWARD_PROXY_ONLY`, not a causal coupling result.

## ZIP contents

The supplementary ZIP is deliberately curated below 500 MB. It contains no checkpoints and excludes duplicated multi-hundred-megabyte raw step traces.

### `evidence/v23/`

- final analysis JSON/Markdown;
- Route-B, candidate-freeze, holdout and render receipts;
- 15 representative canonical episode-0 handle-top videos: one environment from each of three selected checkpoints x five render scenarios.

### `evidence/v24/`

- v23 posthoc unit/mechanics/intervention analysis outputs;
- D-v2 tolerance, energy, semantic-validation and final-adjudication receipts;
- r13 P1-lite friction-domain registration/receipt/runtime summary;
- r12 Rule16/calibration/freeze/F3 terminal artifacts needed to audit the null-domain history;
- r13 Rule16, smoke, calibration rows, behavioral freezes, commands, complete 128-row F3-prime population, adjudication/finalization, exit receipts and runtime summaries;
- RQ4 measurement-only pair rows and final receipt;
- v24 final JSON result.

### `historical_untracked_v24_source/`

- the earlier r11 marginal-E1 sampler/evidence/config/launcher/reducer files that were present locally but never became controlling r12/r13 source;
- these files are included only to preserve review provenance. They must not be treated as the final implementation or used to override committed r12/r13 evidence.

## Important interpretation boundaries

- Do not describe v23 as proving FULL/RP0 parity.
- Do not describe v24 as proving roll/pitch has no force value.
- Do not describe `20 N*m` hinge friction as a validated heavy fire-door model.
- Do not claim solver-applied friction torque was directly measured.
- Do not reinterpret E1 count as success rate or policy quality.
- Do not propose reopening v24 by changing its terminal gate after observing the data. Any new test should be a separately registered round with a corrected physical model and admission criterion.
