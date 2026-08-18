# READY GRPO Student — r4 paired MuJoCo campaign report

Completed: 2026-08-18 11:35 HKT  
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`  
Final typed conclusion: `UNRESOLVED_PENDING_E5`

## Outcome

r4 closes the two hard r3 action/control defects and runs the unchanged eight-case paired manifest to full horizon on CPU MuJoCo. The exact production stage-0 contract is active, the true 100/45 effort surface is stable through native position actuators with `implicitfast`, and all three visual prerequisites pass. The resulting 32,000-row physics campaign is finite and schema-valid.

The GRPO-finetuned Student walks toward the door in all 8/8 cases without falling. It does not stop: the physical base-command norm never reaches the production `<=0.1` base-still predicate, so 0/8 cases advance to stage1 and the arm correctly stays in stage-0 hold. Four hinge crossings occur without unlatch or arm enable and are classified as collision-driven door motion, not purposeful door manipulation.

This is a material pipeline/physics improvement over r2/r3: the robot stands and executes directed locomotion instead of numerical arm flight. It is not yet evidence that the residual gap is visually dominant, and it is not a standalone Student-quality verdict. Formal paired attribution remains blocked on the Isaac trace and same-state `t=0` RGB handoff.

## P1 — `STAGE_CONTRACT_MINIMAL`

The production action path was audited directly and the deployable subset was implemented without changing shared production files.

- Stage0 retains the raw six-dimensional arm delta echo for the next 81D observation, accumulates `0.3 * raw_delta`, clips to `[-15,15]`, then zeros the applied accumulator.
- Stage0→1 is evaluated after the action/physics/observation cycle. The reaching action remains stage0; arm delta is enabled on the following policy step.
- Exact advancement predicate: grasp-target minus root x in `[0.5,0.8]` m; absolute lateral error `<0.15` m; maximum six-arm deviation from default `<0.1` rad; physical base-command first-three norm `<=0.1`.
- Normal Student stage1+ has no further base, leg, arm, or gripper action rewrite. Across all stages, raw gripper primitive `>0` opens to `[0.035,-0.035]`; otherwise it closes to `[0,0]`.
- Scripted approach probe passes: arm remains default before the predicate, the reaching step stays stage0, and the first stage1 action applies `0.3` without touching the `±15` cap.

Campaign stage evidence is separate from the frozen paired row schema. Every case has `stage_trace.jsonl`; the aggregate predicate receipt shows the arm-default check passed at all 1,000 policy steps in every case, while base-still passed at zero steps. Minimum observed command norm by case ranges from 0.2360 to 0.3432.

Evidence: `artifacts/e5/stage_contract_r4/` and `artifacts/e5/paired_mujoco_campaign_r4/stage_predicate_diagnostics.json`.

## P2 — stable true 100/45 surface

The prior external-PD instability was localized before switching control realization:

- first `|qacc| >= 1e6` at physics step 11, `t=0.055 s`, on `arm_j4`, with `|qacc|=2,758,195.45`;
- raw PD demand was 6,530.07 N·m;
- contemporaneous named contacts were zero-force door-panel/floor contacts, not a robot foot/contact impulse;
- MuJoCo then warned at `t=0.065 s`, so the huge acceleration begins in the arm control realization.

Under the package D5 authorization, all 20 robot motors were replaced by MuJoCo native position actuators. `kp/kv`, armature, defaults, and effort limits come from the READY resolved config; the owner gripper surface is 1300/32/45. Door actuators remain IDs 0/1, robot actuators are name-resolved IDs 2–21, and targets are written to those IDs. The declared deviation is that Python per-step external-PD clipping is replaced by native `forcerange` inside the `implicitfast` solve.

The true-surface standing gate passes:

| Gate | Result |
|---|---|
| passive landing 2 s | final base 0.49242 m; all four foot forces nonzero; tail span 0.00458 m |
| frozen A2 5 s | final base 0.44315 m; all four foot forces nonzero; tail span 0.00386 m; max roll/pitch 0.03577 rad |
| mapping/effort | target-write error 0; generalized-force error 0; effort over-limit 0 |

The campaign preserves the same surface for all 32,000 steps: maximum qacc 1,935.22, target-write error 0, generalized-force error 0, and effort over-limit 0. Finite is not used as a substitute for the standing gate; the gate receipt authorizes the campaign first.

Evidence: `artifacts/e5/qacc_localization_r4/` and `artifacts/e5/standing_vitals_gate_r4/`.

## P3 — visual path and measurable appearance

- All sites and debug/axis marker geoms use visibility group 5, and the exact render path feeding the policy applies `sitegroup[5]=0` and `geomgroup[5]=0`.
- The door now has four massless/collisionless two-sided inset panels and ten two-sided panel bands. Frame, panel, inset, and trim colors are explicit; door physics and the corrected V2 handle geometry are unchanged.
- Read-only distillation truth is not a fixed single door color. At commit `a197255212fa65dd9e02337b7971daac71c944fe`, the scenario enables preloaded material randomization (`20` transform and `100` color materials), and frame/panel/handle materials are sampled independently at asset spawn. A selected asset binding is fixed during an episode; exact p00 material remains typed unavailable without paired `t=0` frames.
- Brightness/hue gates pass without a camera edit:

| Camera | MuJoCo/Isaac luma mean | circular hue delta |
|---|---:|---:|
| left | 0.70198 | 0.06062 |
| right | 0.73394 | 0.09756 |
| head | 0.91748 | 0.04814 |

All luma ratios are within owner `[0.7,2]×`; all hue deltas are within `0.1`. The Isaac images used here are real nominal eval frames but not paired p00 state, so they judge illumination/material envelope only. Extrinsics and FOV remain byte-equivalent before/after the overlay and are frozen pending paired `t=0` images.

Evidence: `artifacts/e5/visual_parity_r4/`.

## P4 — full campaign

The manifest case set, fixed initial state, seeds, DoorInstanceSpecs, and paired schema are unchanged. Its stale stage/pilot description fields are superseded only at runtime by the owner r3/r4 adjudication; no case material was rewritten.

| Metric | r4 result |
|---|---:|
| cases / policy steps / physics steps | 8 / 8,000 / 32,000 |
| terminal reason | 8 HORIZON; 0 BASE_HEIGHT; 0 INVALID_NUMERICS |
| cases moving toward door | 8 |
| cases reaching stage1 | 0 |
| unlatch events | 0 |
| hinge threshold crossings | 4 |
| purposeful post-stage arm cases | 0 |

Every failed/non-manipulating episode remains a complete trace. Task facts are computed directly from MuJoCo handle and hinge state. RGB statistics remain E4 domain-gap data and do not decide regression.

The comparator validates every MuJoCo row against `paired_trace_row.v1` and returns:

- evidence level: E5;
- classification: `EXPLORATORY_NON_COMPARABLE`;
- input status: `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`;
- numeric error: null;
- r4 typed conclusion: `UNRESOLVED_PENDING_E5`.

The distillation handoff now makes exact policy-input left/right/head `t=0` Isaac frames mandatory for a small subset including p00. Until they arrive, no extrinsic/FOV or formal appearance ruling is made.

## Preserved prior classifications

- r2 campaign: `INVALID_PIPELINE_SUPERSEDED_BY_R3`.
- r2 door-learning result: `VOID`.
- r3 resolved-effort attempt: `INVALID_NUMERICS`.
- r3 40 N·m ablation: `INVALID_CONTROL_CONTRACT_DIAGNOSTIC_ONLY`.
- r3 overall: `VALID_WITH_WARNINGS`, typed `PIPELINE_DEFECT_FOUND_ACTION_CONTROL_CONTRACT`.

No statement that uncontrolled flight is expected Student behavior survives. The READY payload remains the GRPO-finetuned 467/512 (91.2%) Student versus the 459/512 (89.6%) baseline.

## Primary evidence

- Campaign receipt and traces: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r4/`
- E5 waiting report: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r4/e5_waiting_report.json`
- MuJoCo screenshot: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r4/mujoco_asset_initial.png`
- Distillation handoff: `scriptsFORhuman/sim2sim/artifacts/e5/paired_case_manifest/DISTILLATION_HANDOFF.md`

CPU/Xvfb/llvmpipe only; no GPU lease; no push.
