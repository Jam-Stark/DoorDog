# DoorDog A2+PiPER `base_v25` Final Analysis

**Plan:** `scriptsFORhuman/v25/a2_piper_base_v25_execution_plan_R2_20260820.md`  
**Execution ledger:** `scriptsFORhuman/v25/a2_piper_base_v25_execution_ledger_20260821.md`  
**Primary load:** native P10 hinge friction, static/dynamic/viscous `10.0/7.5/0.0`  
**Acute policy:** `V25_FULL_S0` step500  
**Final product Teacher:** retain `A1_G7_seed0_step1500`

## Observed facts

### Mirrored LEFT/RIGHT path

- Raw `left` means robot-view LEFT handle and `right` means robot-view RIGHT handle. The hinge is on the opposite lateral side; push-through remains +X and positive hinge progress remains opening on both variants.
- Deterministic M1 rendering showed the handle-relative target markers following the mirrored physical handle. The existing A2 grasp/pregrasp/stage path required no side-specific reward or stage patch.
- G7's single RIGHT proof completed stage5 in 446 steps. Its mirrored LEFT proof reached stage2 but timed out with near-zero hinge progress. The later common suite confirmed that this was a policy distribution gap rather than a geometry-routing failure.
- The mixed-LR path trained end to end. The 64×8 smoke spawned exactly 32 LEFT/32 RIGHT environments and completed all eight optimizer updates.

### Formal adaptation

- FULL/RP0 × seed0/1 each completed 4096 environments × 1500 batches, with step250/500/750/1000/1250/1500 checkpoints.
- Each cell produced 6,144,000 episodes and 393,216,000 timesteps. All used the same mixed LEFT/RIGHT sampler, native P10 load, staged reset, and disabled reward-penalty curriculum.
- The four completed roots are:
  - `logs_rl/a2_piper_full_stage_a2_base/base_v25/formal/V25_FULL_S0`
  - `logs_rl/a2_piper_full_stage_a2_base/base_v25/formal/V25_FULL_S1`
  - `logs_rl/a2_piper_full_stage_a2_base/base_v25/formal/V25_RP0_S0`
  - `logs_rl/a2_piper_full_stage_a2_base/base_v25/formal/V25_RP0_S1`

### Teacher comparison

| Policy | Side | Episodes | Goals | Crossing while holding | Post-release body contact | Relevant stage result |
|---|---:|---:|---:|---:|---:|---|
| G7 step1500 | LEFT | 64 | 0 | 1/64 | 1/64 | only 2/64 reached stage4/5 |
| G7 step1500 | RIGHT | 64 | 64 | 64/64 | 0/64 | 64/64 stage5 |
| FULL S0 step500 | LEFT | 32 | 0 | 22/32 | 6/32 | 30/32 reached stage4/5 |
| FULL S0 step500 | RIGHT | 32 | 32 | 32/32 | 0/32 | 32/32 stage5 |
| FULL S0 step1000 | LEFT | 32 | 1 | 20/32 | 3/32 | the sole goal had body contact |
| FULL S0 step1000 | RIGHT | 32 | 31 | 24/32 | 0/32 | one RIGHT regression |
| FULL S1 step1500 | LEFT | 64 | 0 | 0/64 | 0/64 | 63/64 stopped at stage3 |
| FULL S1 step1500 | RIGHT | 64 | 64 | 62/64 | 0/64 | 64/64 stage5 |

`FULL S0 step500` is the strongest mixed-LR FULL checkpoint for the science experiment: it materially improves LEFT grasp/open progression while preserving the sampled RIGHT result. It is not Teacher-qualified because it produced no clean LEFT completion; later S0 checkpoints did not establish a clean repeatable LEFT goal and showed either RIGHT or contact-quality regression.

### Chronic FULL versus RP0 comparison

The same seed0, step500, P10, deterministic 32-episode-per-side suite was used. RP0 masks roll/pitch command channels throughout adaptation.

| Policy | LEFT crossing while holding | LEFT max stage | RIGHT goals |
|---|---:|---|---:|
| FULL S0 step500 | 22/32 | 24 stage4, 6 stage5 | 32/32 |
| RP0 S0 step500 | 0/32 | all at stage0-3 | 31/32 |

This is a chronic training comparison, not an acute force intervention. It shows that access to posture channels during adaptation substantially improved LEFT reach/grasp/open geometry at the selected checkpoint.

### Acute matched-prefix intervention

- State criterion: existing stable-grasp/contact high-water condition while `abs(hinge) <= 0.25 rad`, P10 active, before episode termination.
- Restore method: deterministic matched-prefix replay, not exact contact-solver serialization.
- Horizon: 50 control steps, approximately one second. Arm and gripper policy outputs remained active and unchanged by the channel mask.
- Effective paired state bank: 30 LEFT and 32 RIGHT. Every latched state completed the horizon.

Branch notation is `P=roll/pitch posture channel`, `M=planar vx/vy/yaw channel`.

| Side | Paired channel effect | Median hinge effect | Mean hinge effect |
|---|---|---:|---:|
| LEFT | posture ON−OFF, planar active | +0.007 rad | -0.010 rad |
| LEFT | posture ON−OFF, planar disabled | -0.025 rad | -0.039 rad |
| LEFT | planar ON−OFF, posture active | +0.074 rad | +0.076 rad |
| LEFT | planar ON−OFF, posture disabled | +0.050 rad | +0.047 rad |
| RIGHT | posture ON−OFF, planar active | -0.013 rad | -0.007 rad |
| RIGHT | posture ON−OFF, planar disabled | -0.005 rad | -0.007 rad |
| RIGHT | planar ON−OFF, posture active | +0.148 rad | +0.135 rad |
| RIGHT | planar ON−OFF, posture disabled | +0.152 rad | +0.136 rad |

The masks removed material command dose: posture-off with planar active removed mean posture L1 dose `4.128` on LEFT and `2.650` on RIGHT; planar-off with posture active removed mean planar L1 dose `5.289` on LEFT and `5.533` on RIGHT. Achieved roll/pitch also changed as intended: FULL versus posture-off mean absolute roll/pitch was `0.303 vs 0.093 rad` on LEFT and `0.152 vs 0.083 rad` on RIGHT.

Contact retention remained high in the FULL branch (`0.974` LEFT, `0.997` RIGHT). LEFT posture-off reduced it to `0.812`, so posture can help retain LEFT contact even though it did not yield a positive mean hinge-progress effect over this horizon. Planar-off retained `0.881` LEFT and `1.000` RIGHT contact while sharply reducing hinge progress; the planar effect is therefore not explained by immediate grasp loss.

## Worker interpretation

- G7 is clearly out of distribution on LEFT, while the simulator/task mirrored route itself is working.
- Warm adaptation learned useful LEFT approach/grasp/open behavior, especially in FULL S0, but did not produce a clean, repeatable bidirectional Teacher.
- The acute stable-grasp opening mechanism is dominated by planar base motion. Roll/pitch posture is neutral to mildly harmful for immediate hinge progress at P10 over 50 steps.
- The chronic FULL/RP0 gap and LEFT contact-retention gap support a narrower role for posture: it mainly helps reach/grasp geometry and contact maintenance during learning, rather than supplying immediate opening mechanics after stable grasp.

## Remaining unknowns

- No v25 checkpoint established clean repeatable LEFT completion, so the best long-horizon bidirectional policy remains unknown.
- Acute causality was measured at one load, one FULL checkpoint, and one matched-prefix state distribution. It was not an exact restore of contact-solver internals.
- Numeric causal evaluation covers both sides; representative causal videos cover LEFT, where the adaptation gap is most informative.
- Real door friction, compliance, actuator torque margins, foot-ground interaction, and contact geometry were not measured here.

## Teacher decision and handoff

**Decision: retain v23 G7. Do not replace the Student Teacher.**

- Checkpoint: `logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt`
- Resolved training config: `logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/config.yaml`
- Run/seed/step: `A1_G7`, seed0, step1500
- Training distribution: legacy RIGHT-handle push-door distribution; no mixed-LR adaptation
- Load distribution: no v24 native hinge-friction augmentation in the retained G7 run; v25 qualification used fixed native P10
- Known weakness: LEFT 0/64 goals and only 1/64 crossing-while-holding on the v25 common suite
- Contract: unchanged. Retaining G7 preserves the existing Student observation/action contract; the action head remains 12-D and no Student worktree file or process was changed.

`V25_FULL_S0/model_step_000500.pt` remains a science checkpoint only, not a Student Teacher handoff.

## Posture-causality decision

**Category:** posture mainly helps reach/grasp geometry; planar motion supplies the immediate stable-grasp opening mechanics. Posture appears neutral or mildly harmful for short-horizon hinge progress in this P10 setting, while helping LEFT contact retention.

This does not imply that posture has no value over a full episode or under other loads. It specifically rejects the stronger claim that roll/pitch command activity was the main immediate source of door-opening progress in the measured stable-grasp states.

## Real-site relevance

- Preserve posture capability for acquisition/contact geometry rather than removing it from future policies solely because the acute hinge effect is small.
- Prioritize validating commanded planar base motion, foot traction, collision clearance, and contact retention on hardware.
- Do not infer real-world hinge torque capacity from these simulation command masks or the P10 parameter.
- Keep G7 as the current Student Teacher until a later checkpoint demonstrates clean repeatable LEFT success without RIGHT or contact-quality regression.

## Artifacts

- Unified data: `logs_eval/base_v25/final/v25_summary.json`
- Paired causal figure: `logs_eval/base_v25/final/v25_causality_paired.png`
- Numeric intervention records: `logs_eval/base_v25/causality/V25_FULL_S0_STEP0500/`
- G7 videos: `logs_eval/base_v25/m3/teacher_videos/G7_STEP1500_VIDEO_R2/`
- FULL S0 step500 videos: `logs_eval/base_v25/m3/teacher_videos/V25_FULL_S0_STEP0500_VIDEO_R3/`
- LEFT representative causal videos: `logs_eval/base_v25/causality_videos/V25_FULL_S0_STEP0500/`

