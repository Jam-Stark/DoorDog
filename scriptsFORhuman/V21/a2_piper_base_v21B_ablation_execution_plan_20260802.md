# A2+Piper DoorDog — base_v21-B Implementation, Ablation, and Route-B Execution Plan

**Plan ID:** `base_v21B_theta_arm_ablation_v1`
**Execution ID:** `base_v21B_execution_v1`
**Date:** 2026-08-02 HKT
**Repository:** `Jam-Stark/DoorDog`
**Start branch / commit:** `A2_Piper` / `aa8ec0700e59be051e0b9e838f834aa2e9a426f4`
**Worker workspace:** `/home/baoquanc/workspace/DoorDog-A2_Piper`
**Legal physical GPUs:** `0–6`; **GPU7 forbidden** (verified occupied: 12425 MiB, 86% util, 2026-08-02)
**Manifest:** `scriptsFORhuman/V21/a2_piper_base_v21B_experiment_manifest_20260802.yaml`

**Relationship to `base_v21`.** This is a **sibling variant**, not an edit. `a2_piper_base_v21_implementation_training_execution_plan_20260801.md` and its manifest remain byte-unchanged and retain their plan identity. v21-B adopts v21's scientific diagnosis, its Route-B apparatus, and its admission discipline; it changes the experiment matrix, the theta ceiling, and the acceptance thresholds. Where this document is silent, **v21 governs**.

---

## Decision block

```text
V21B_PRIMARY_QUESTION_1 = does physical crossing track theta_send?          (theta axis)
V21B_PRIMARY_QUESTION_2 = do realistic arm limits create a force-feasibility
                          boundary inside the existing door distribution?    (arm axis)
DESIGN            = 2x2 ablation (theta x arm) + replicates on both theta=1.20 cells
                    + one arm-tie probe = 7 cells on 7 GPUs
THETA_LEVELS      = {0.90, 1.20} rad          # 1.25 conditional stretch only, 1.30 REMOVED
ARM_LEVELS        = {ARM_V20 (100 N*m), ARM_REALISTIC (census-selected)}
WARM_START        = v20 G4 step2500, policy_only, sha256 verified on host
VELOCITY_LIMITS   = OUT_OF_SCOPE (confounds with effort; v22)
STAGE_TIME        = OUT_OF_SCOPE
GATE/BASE_ASSIST  = OUT_OF_SCOPE (v21-B builds its precondition)
ACCEPTANCE        = control-referenced against in-round cell B1 + measured absolute floors
GPU7              = FORBIDDEN
```

### Why the matrix is an ablation rather than a choice between rounds

v21 asked the theta question and deferred arm limits to a later round; the handoff queue asked for arm limits with theta as a rider. Running them as one factorial answers both with clean attribution, and costs the same seven GPUs either way. Crucially it protects against the failure mode of a rider: if theta and arm limits moved together in every cell, a rise in heavy-tail overtime could not be attributed to either. The 2×2 separates them, and cells B2/B6 preserve v21's original question intact even if the arm axis is abandoned under fork F2.

---

# 1. Evidence base and corrections

All numbers in this section were recomputed on the worker host from
`logs_eval/base_v20_R2/m22_r3_route_a_f8e3197_offline_20260801`, first episodes only.
The reconstruction reproduces the official reporter to four decimals
(G4@2500 `hinge_at_crossing` p50/p95 = 1.0160/1.0628; `held_hinge_max` p50 = 1.2911),
which is the correctness check for everything below.

## 1.1 The v20 diagnosis — v21 section 1.1 is correct and is adopted

The handoff ADDENDUM paragraph 2 attributes the v20 crossing cluster to the corridor latch's legacy `hinge >= 1.0` OR-branch. **That attribution is wrong.** Verified:

- All seven v20 R3 cells trained with `a2_v20_send_hinge_threshold: 0.9`. Theta was never varied.
- G2/G4/G6/G7 ran `a2_corridor_latch_mode: send_ready_v20`, in which the legacy branch is unreachable (`a2_v20_update_corridor_latch`, `door_open_a2_base.py:694`); G3/G5 ran `legacy_root_or_hinge`. Both families pinned near 1.0, so latch mode cannot be the cause.
- G2 (send-ready latch, no send curriculum) was inert at +0.026 rad, so the latch mode alone drove nothing. The send **curriculum** — the shortfall-scaled pre-send crossing penalty keyed to theta — is the active ingredient.

The correct model is the one stated in v21 §1.1, now measured on the warm start (G4@2500, n=16):

| quantity | value |
|---|---|
| send latch fired | 16/16 |
| crossings **before** send latch | 0/16 |
| send→cross latency | p50 25.5 control steps (0.51 s), p95 63.2 (1.27 s) |
| overshoot `hinge_at_crossing − 0.90` | p50 **0.1160**, p05 0.0620, p95 0.1628 |

So `hinge_at_crossing ≈ theta_send + 0.12`. Theta is already the single active boundary in the send path; the handoff's "unify theta" rider is therefore largely satisfied by existing code, and what remains is to raise theta and remove the guard that pins it.

**Correction C1** is recorded in the manifest. Credit for the correct diagnosis belongs to the base_v21 (cloud) plan, which reached it independently from source alone.

## 1.2 The theta ceiling — why formal cells stop at 1.20

Fraction of first episodes whose door ever reaches theta **while bilaterally held** — i.e. whether the send latch can fire at all:

| theta_send | G4@2500 (warm start, n=16) | mature pool G4/G6/G7 steps 1500–2500 (n=240) |
|---|---|---|
| 1.10 | 100.0% | 99.2% |
| 1.20 | 93.8% | 97.1% |
| 1.25 | 81.2% | 90.8% |
| **1.30** | **37.5%** | **72.1%** |
| 1.40 | 0.0% | 23.3% |

`held_hinge_max` for the warm start is p50 1.2911 / p95 1.3617. At theta = 1.30 the majority of episodes never reach the threshold, the send latch never fires, and the shortfall-scaled pre-send crossing penalty applies for the whole episode with no way to earn it off. That is the **income-cliff / above-ceiling family, 6th instance** (v13 doorstop, v15 gate dead-zone, v16 unpaid push, v18 carry-above-ceiling, v20 theta pin) and it is precisely the standing-rule-1 failure the project has paid for five times.

The payoff argument for stopping at 1.20: predicted crossing p50 = 1.20 + 0.116 ≈ **1.32 rad**, a **+0.30 rad gain over v20's 1.0160** — larger than v20's entire effect — at 94–97% latch feasibility. Going to 1.30 buys roughly +0.10 rad more and drops feasibility to 37–72%.

**Correction C2**: the handoff rider and the v21 manifest both recommend 1.25–1.30. Superseded; n=16 gives a wide interval on the 37.5% figure, which is why 1.25 survives as a conditional stretch rather than being deleted outright.

## 1.3 The heavy tail is not (yet) time-limited

The handoff pre-registered heavy-tail overtime as the main risk of raising theta, from a single render case (160 kg / 11.4905 N·m ending `stage_overtime`). In the mature pool that does not generalise:

| bucket | n | held_hinge_max p50 | reach 1.25 | stage_overtime | send→cross p50 |
|---|---|---|---|---|---|
| heavy (≥140 kg or ≥10 N·m) | 120 | 1.3191 | 85.8% | **0.0%** | 13.5 steps |
| rest | 120 | 1.3530 | 95.8% | 0.8% | 17.0 steps |

Heavy doors cross *sooner* after latch, not later. The 4.0%-vs-2.0% split the handoff cites appears only when immature checkpoints are pooled in. **Correction C3**: retained as a monitored risk, removed as a pre-registered expectation. Raising theta still lengthens the pre-send phase by construction, which is why the pre-send displacement and overtime caps below are widened rather than tightened.

---

# 2. Anti-block doctrine

v20 was blocked repeatedly by admission machinery and only cleared at R3. The remote planner cannot run IsaacLab, cannot execute an eval, and cannot read resolved configs on this host, so its thresholds were necessarily written without a measured basis. v21-B adopts four rules:

1. **No threshold without a measured basis.** Every scientific or fluency threshold cites a measured value from §1 or from a P0 probe. A threshold with no measurement is `report_only` in its first round.
2. **No zero-tolerance gate on a pre-existing defect.** A round may not be blocked by a failure mode it did not set out to fix. Such defects get a rate cap at the measured baseline and are reported.
3. **Every blocker names its unblock path.** A P0 test that can fail must be paired with a pre-registered response (§10 forks). "Stop and escalate" is a valid response; silence is not.
4. **Integrity gates stay hard.** Source/schema/hash/DAG/finite-data/GPU7/no-hidden-override remain absolute. Only *task and fluency* thresholds are subject to rules 1–3.

## 2.1 Gates inherited from v21 that would have blocked this round

Measured against the policies that actually exist today:

| v21 STANDARD gate | required | measured | verdict |
|---|---|---|---|
| `upper_dof_overspeed = 0` (hard gate) | 0 | **7/240 = 2.9%** (mature pool) | P(pass over 112 release episodes) = **3.6%** |
| `held hinge p50 ≥ 1.35 rad` | ≥1.35 | 1.2911 warm start / 1.3400 pool | blocks |
| `held hinge p95 ≥ 1.45 rad` | ≥1.45 | 1.3617 warm start / 1.4777 pool | blocks on warm start |
| `pre-send yaw p95 ≤ 0.55 rad` | ≤0.55 | **0.5636** | already exceeded, worsens with theta |
| `pre-send planar p95 ≤ 0.75 m` | ≤0.75 | 0.6531 / 0.6748 | ~10% headroom, consumed by theta |
| `stage_overtime ≤ 4/48` | ≤8.3% | 6.2% warm start (1/16) | thin |
| `goal ≥ 45/48` | ≥45 | — | *looser* than the north-star 46/48 |

The overspeed gate is the dangerous one precisely because it looks satisfied: the warm start happens to be 0/16, so a document-only reader concludes it was fixed in v19. It was not — the v18 stiff-finger defect persists at ~2.9%.

**A further structural point:** Route B has never run in project history. There is no pooled48 or holdout64 precedent for this policy family, so all eight of v21's pooled48 thresholds were pre-registered against data that does not exist. v21-B resolves this by making cell **B1** — theta 0.90, ARM_V20, a straight v20 replicate — the in-round reference, and gating on non-regression against it (§9).

---

# 3. P0 — mandatory unblock work

Nothing in this round runs until §3.1 lands. This is the first thing a worker hits and v21 does not mention it.

## 3.1 P0-G — freeze-guard extension (hard blocker)

`_validate_a2_v20_r1_config` (`gr00t/rl/envs/door/door_open_a2_base.py:5527`) is invoked from `_init_a2_door_pregrasp_state` (`:6175`), i.e. **at env construction on both the training and the eval path**. When the send curriculum is enabled it enforces:

```text
:5541  plan_id must == "base_v20_R1_policy_behavior_v1"        (A2_V20_R1_PLAN_ID,  :72)
:5543  soft_phase_end must == 500                              (:74)
:5545  crossing base component and shortfall gain must == 1.0/1.0
:5547  theta_send must == 0.90 exactly                         (A2_V20_R1_THETA_SEND_RAD, :75)
:5549  send tolerance must == 0.05 exactly                     (:76)
:5551  pre-send root-x margin must == 0.03 exactly
```

Consequences today: **every cell with theta ≠ 0.90 raises `RuntimeError("R1 send threshold must remain exactly 0.90 rad.")` before the first step**, and so does any frozen-policy theta ladder, because eval loads the checkpoint-adjacent training config (which carries `a2_v20_R1_send_curriculum_enabled: true` and the R1 plan id) and merges CLI on top. The `scientific_plan_id` field at the head of each ablation yaml is what feeds this check.

**Required change.** Add a v21-B branch keyed on a new plan id, leaving the v20 R1 branch byte-identical:

- accept `scientific_plan_id: base_v21B_theta_arm_ablation_v1`;
- under that id, permit `a2_v20_send_hinge_threshold` in the closed interval `[0.90, 1.30]` and continue to enforce tolerance 0.05, margin 0.03, schedule 0/500, components 1.0/1.0;
- reject theta outside the interval with a message naming the plan id;
- leave `A2_V20_R1_*` constants and the v20 code path untouched.

**Unit tests (must fail before the change, pass after):**

1. a v20 R3 G4 resolved config still validates unchanged (regression guard on backward compatibility);
2. a v21-B config at theta 1.20 validates;
3. a v21-B config at theta 1.35 is rejected;
4. a v20 R1 plan id with theta 1.20 is still rejected;
5. every v21-B formal config resolves `a2_corridor_latch_mode: send_ready_v20`;
6. the send latch, the crossing-shortfall term, and the stage-4 target-root ramp origin all resolve the *same* theta value;
7. no v21-B config alters stage time, velocity limits, Kp/Kd, physics randomization, or reward terms outside the declared theta / arm / arm-tie / seed factors.

Fork **F1** covers the case where backward compatibility cannot be preserved: introduce theta as an independent key instead of reusing `a2_v20_send_hinge_threshold`, leaving the v20 path wholly untouched.

## 3.2 P0-T — arm torque telemetry (mandatory, was optional in v21)

v21 marks torque telemetry "preferred, non-blocking" — correct for a theta-only round. In v21-B the arm axis makes it the **primary instrument**: without it there is no way to claim a feasibility boundary exists, and DV2 is unmeasurable. It is therefore mandatory.

Observability only: it must not alter torque limits, Kp/Kd, action scale, rewards or observations.

**Provenance — ESTIMATE_ONLY (worker-raised plan conflict, adjudicated 2026-08-02).** The A2 arm joints are implicit actuators (`gr00t/rl/simulator/isaacsim/isaacsim_articulation_cfg.py:111`, `"arms": ImplicitActuatorCfg`). PhysX does not expose the true drive force for implicit actuators; IsaacLab's `computed_torque` / `applied_torque` (`door_open_a2_base.py:19334-19335`) are the actuator model's own PD estimate and clipped estimate. **P0-T therefore measures a clipped implicit-PD torque proxy and must never be reported as true PhysX drive torque.**

Reuse the existing, already-reviewed repo pattern rather than new vocabulary — the gripper hold-oracle path at `door_open_a2_base.py:19331-19438` already implements it via `a2_hold_pd_effort_estimates(q, qdot, qtarget, kp, kd, limit) -> (unclipped, clipped, saturated)`, cross-checked against the IsaacLab estimates and stamped with an authority label. P0-T is the same functions applied to `arm_j1..arm_j6`, keeping one provenance vocabulary across the repo:

```text
arm_pd_effort_estimate_unclipped_6d
arm_pd_effort_estimate_clipped_6d
arm_pd_effort_estimated_saturation_6d
isaaclab_implicit_computed_effort_estimate_6d
isaaclab_implicit_applied_effort_estimate_6d
isaaclab_implicit_effort_estimate_crosscheck_error_6d
isaaclab_implicit_effort_estimate_authority  = ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE
```

**Record both clip states — they answer different questions.** v21 §0.4 (and the first draft of this section) declared the post-clip value the single source of truth. That is correct for DV2, where the limit is the treatment and saturation fraction is the readout, but **wrong for the census** of §4.1, which extrapolates candidate limits from a run at 100 N·m: the fraction that would saturate at limit *k* is `P(|unclipped| >= k)`, which post-clip data cannot supply. So:

- **census (§4.1) → unclipped estimate**, plus an explicit right-censoring report (the fraction of frames already at/above 100 N·m; if that mass is non-trivial the extrapolation is biased and must be flagged rather than silently used);
- **DV2 in formal cells → clipped estimate + saturation flag**, since there the limit is the manipulated variable.

Derived per-episode: per-joint p50/p95/max utilization; fraction of valid frames ≥0.90 and ≥0.98; `first_joint_ge_0.98`; heavy/light bucket split. `N/A` never `0` for empty denominators.

**Non-proxy corroboration (mandatory for DV2).** So that the boundary claim does not rest on an estimate alone, record joint tracking error — `joint_pos_target − joint_pos` and `joint_vel` per arm joint, all already read at `:19325-19330`. A saturated joint physically cannot track its target, so persistent tracking-error growth on the heavy bucket, coincident with estimated saturation, is a physically grounded corroboration that is independent of the torque model. `root_physx_view.get_link_incoming_joint_force()` is available in this repo (`isaacsim.py:709-716` shows `root_physx_view` access) but is **advisory-only and explicitly not required**: it returns link-space constraint force rather than drive torque, and projecting it onto the joint axis adds implementation risk for no additional adjudication power.

**What the proxy does and does not limit.** The *treatment* is not a proxy: IsaacLab configures the PhysX drive's force limit from `effort_limit`, so lowering it genuinely constrains the physics whether or not we can read the resulting torque back. Only the *claim* tightens. Permitted: "the arm's commanded PD effort saturates its configured limit on the heavy bucket, corroborated by tracking-error growth." Not permitted: "we measured the true applied PhysX joint torque." No real-hardware force-feasibility claim is permitted from v21-B under any outcome.

## 3.3 P0-A — arm profile plumbing

Effort limits are already overridden per-ablation, not in the robot yaml: each ablation carries a `robot: dof_effort_limit_list:` block of 20 entries (12 leg + `arm_j1..j6` + `arm_j7/j8`). The repo default `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml:83` lists `10.0, 10.0` for the fingers, but the **resolved** v20 G4 config carries `45.0, 45.0` — the v18 gripper-realism change lives in the ablation layer. A worker who edits the robot yaml will therefore change nothing.

Requirement: express `ARM_V20` and `ARM_REALISTIC` as named, versioned blocks emitted into each ablation yaml, and assert in the P0 admission step that `logs_rl/<run>/config.yaml` resolves the intended 20-entry list (standing rule 10: the saved run config is the source of truth).

## 3.4 P0-B — send/cross episode telemetry

Most of v21 §0.3 already exists in the trace and needs **reporter** work rather than env surgery, which lowers the implementation risk v21 implies. Verified present: `v20_send_ready`, `v20_first_send_ready_step`, `v20_first_root_crossing_step`, `v20_hinge_at_first_root_crossing`, `v20_root_x_at_first_crossing`, `v20_pre_send_root_crossing`, `v20_r1_max_pre_send_reconfiguration` (`[forward, lateral, planar, yaw]`), `v20_arm_tangent_share`, `v20_along_handle_slip_m`, `door_hinge_joint_pos`, `both_contact`, `terminal_reasons`.

Derived offline: `hinge_at_send_latch` (hinge at `v20_first_send_ready_step`), `send_to_cross_control_steps`, `send_to_cross_s`, `hinge_delta_send_to_cross`, `held_hinge_max`, `task_time_s`. Only the torque fields of §3.2 are genuinely new.

---

# 4. Pre-formal probes

## 4.1 P0-T-census — where does the boundary fall?

Run the frozen warm-start checkpoint under full randomization with torque telemetry, canonical16 plus a **pre-registered heavy16 manifest** (`door_weight ≥ 140 kg` and `hinge_force ≥ 10 N·m`, balanced over handle heights). Generate the manifest once, write it to JSON, hash it, reuse it for every rung. No seed or scenario fishing.

Report per joint and per bucket: peak and p95 **unclipped** PD effort estimate (§3.2 provenance applies — this is an implicit-PD proxy, not PhysX drive torque), utilization against the current 100 N·m, the right-censored mass at 100 N·m, and the implied utilization under each candidate limit in `{40, 30, 25, 20}` N·m.

**Selection rule for `ARM_REALISTIC`, fixed before any result is inspected** — choose the **largest** candidate k such that, computed on the unclipped estimate,

- heavy bucket: fraction of episodes with peak `|unclipped| / k` ≥ 1.0 is **≥ 0.30**, and
- light bucket: fraction of episodes with peak `|unclipped| / k` ≤ 0.85 is **≥ 0.80**.

If the right-censored mass at 100 N·m exceeds 5% of **raw valid heavy frames**, the extrapolation is biased upward and the census must report `CENSUS_RIGHT_CENSORED` rather than silently selecting k; fork F3 then applies. Raw rows are grouped by exact `(episode_id, scenario_id, topology, heavy_bucket)` only for episode-peak candidate selection; the right-censor denominator remains the raw valid heavy-frame count, so unequal episode lengths cannot change the stated frame fraction.

This places the boundary *inside* the existing door distribution, which is what the force_feasible thesis requires — a limit that saturates on the heavy tail while leaving light doors comfortably feasible. It is deliberately measurement-driven rather than datasheet-driven: **if AgileX PiPER rated joint torques are supplied, they take precedence** and the census instead reports where that datasheet boundary lands relative to the door distribution (which may itself be the more interesting finding). Fingers stay at 45 N and velocity limits stay unchanged, so the axis is effort-only.

Fork **F3** covers either signed terminal status `CENSUS_RIGHT_CENSORED` or `BOUNDARY_NOT_SEPARABLE`. It skips zero-shot, pilot, and arm-tie dependencies and freezes `THETA_ONLY_FALLBACK_F3`; no numeric k or fabricated adaptation digest is permitted. Formal cells are all `ARM_V20` with six arm limits 100 N·m, arm-tie/DV4 disabled, and the exact theta ladder: `B1=0.90 seed0`, `B2=1.20 seed0`, `B3=1.05 seed0`, `B4=1.15 seed0`, `B5=1.25 seed1`, `B6=1.20 seed1`, `B7=1.25 seed0`.

## 4.2 P0-Z — zero-shot probe under the selected arm profile

Standing rule 9: never change actuator limits without evaluating the frozen policy under the new physics first; gain changes have flipped basins historically. Evaluate the warm start under `ARM_REALISTIC` on canonical16 + heavy16, reporting goal, max stage reached, terminal reasons, torque utilization, and crossing metrics.

This probe **selects and sanity-checks k; it is not a performance gate.** A trained-at-100 policy evaluated at 25 N·m is expected to degrade; training recovers. Only a genuine capability failure triggers fork **F2**: canonical goal `< 3/16` **and** the majority of episodes failing to reach stage 3 (i.e. the arm can no longer grasp and unlatch at all). The response is to step back one grid point and re-probe once, then fall back to a theta ladder if still collapsed.

## 4.3 P0-P — one pilot, at the highest-variance cell

Exactly one pilot: **B4** (theta 1.20 × ARM_REALISTIC), 256 envs × 750 batches, seed 0. v21 piloted theta 1.25 with a frozen arm; in v21-B the interaction cell carries the variance, so that is what gets piloted.

Readout: send-latch fire rate, `hinge_at_send_latch`, `hinge_at_crossing`, send→cross latency, stage_overtime, overspeed, torque utilization, decomposition sanity, no NaN. Fork **F4** triggers if the canonical send-latch fire rate is `< 60%`, dropping theta to 1.10 for all theta-high cells before freeze.

## 4.4 P0-E — arm-tie calibration (inherited from v21 §0.6, unchanged)

v20's arm-tie earned under 1% of positive income and did not bind. Calibrate offline from unscaled raw A components on one fixed telemetry-complete eval of the frozen checkpoint, holding the v20 ratio `arm_tangent : arc_tracking = 3.5 : 0.85` and sweeping one common multiplier `m ∈ {1, 2, 4, 8, 12, 16, 24}`, selection algorithm written before results are inspected, target 5–15% of positive income when engaged (standing rule 2). If calibration fails, B7 runs with `arm_tie: false` as a second replicate of B4 and DV4 is recorded as not tested.

---

# 5. Formal matrix

| Cell | theta_send | arm profile | arm-tie | seed | GPU | role |
|---|---|---|---|---|---|---|
| B1 | 0.90 | ARM_V20 | no | 0 | 0 | control; v20 replicate; **supplies the pooled48 baseline that has never existed** |
| B2 | 1.20 | ARM_V20 | no | 0 | 1 | theta main effect (v21's original question, preserved) |
| B3 | 0.90 | ARM_REALISTIC | no | 0 | 2 | arm main effect |
| B4 | 1.20 | ARM_REALISTIC | no | 0 | 3 | **interaction — the thesis cell** |
| B5 | 1.20 | ARM_REALISTIC | no | 1 | 4 | replicate of B4 |
| B6 | 1.20 | ARM_V20 | no | 1 | 5 | replicate of B2 |
| B7 | 1.20 | ARM_REALISTIC | calibrated | 0 | 6 | arm-tie carry lever (DV4) |

Contrasts: theta = B2/B6 vs B1; arm = B3 vs B1; interaction = B4 vs B2 and B4 vs B3; seed replication = B5 vs B4 and B6 vs B2; arm-tie = B7 vs B4. One axis per contrast, replicates on both theta-high conditions (standing rule 8; basin lottery is real).

**Common contract.** Warm start `logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G4-20260731_004712/model_step_002500.pt`, `policy_only`, sha256 `f000f13e817309f7b73e33c5c4d95076397debb992713e5613dce567bfda806d` (**verified byte-for-byte on this host, 2026-08-02**). Formal cells use 4096 envs, 2500 batches, save250. Before any formal launch, run exactly one B4 smoke with the signed materialized B4 config: 64 envs × 10 batches, save10, then perform the exact train/eval/launcher cleanup and write a cleanup PASS receipt. Only after smoke PASS plus cleanup PASS may formal launch proceed. GPU7 unused. At iteration 50, verify finite contiguous metrics and per-window liveness, detach attached tmux clients without stopping training, recheck liveness, and record `STARTUP_50_PASS`/`TRAINING_CONTINUES`; this is not formal completion. Natural-exit audit remains recorded per cell.

---

# 6. Hypotheses and pre-registered predictions

**DV1 — theta tracking (B2, B6).** `hinge_at_crossing` p50 predicted in **[1.26, 1.38] rad**, from theta 1.20 plus measured overshoot p50 0.1160 (p05 0.0620, p95 0.1628). Labels: `THETA_TRACKING` inside the band; `THETA_PARTIAL_TRACKING` in [1.10, 1.26); `PRE_CROSSING_CEILING` below 1.10 while the latch angle itself tracks theta.

**DV2 — boundary created (B3, B4, B5, B7).** Fraction of heavy-bucket valid frames with clipped-estimate utilization `≥ 0.98` predicted **≥ 0.30** in ARM_REALISTIC cells and **< 0.05** in ARM_V20 cells. Labels: `BOUNDARY_CREATED`, `BOUNDARY_ABSENT`, `BOUNDARY_SATURATED_EVERYWHERE` (the last means k was too aggressive and the light bucket saturates too). **`BOUNDARY_CREATED` requires both** the estimated-saturation criterion **and** the non-proxy corroboration of §3.2 — a heavy-bucket joint tracking-error increase relative to the matched ARM_V20 cell. Estimated saturation alone, without tracking-error corroboration, is reported as `BOUNDARY_ESTIMATE_ONLY_UNCORROBORATED`.

**DV3 — base intervention (B4 vs B2, B3 vs B1).** With a genuine boundary, does base involvement appear on the saturated bucket? Metrics: pre-send planar displacement, pre-send yaw, `arm_tangent_integral_share`, pre-crossing body/door contact. This is the **first direct measurement of the force_feasible dependent variable** in the project; v15 falsified "heavy-door body-assist emergence" under a superhuman arm (0/10066 pre-crossing body contacts at 12 N·m), and DV3 is the same question asked once the arm is no longer superhuman. A null result here is a publishable negative, not a round failure.

**DV4 — arm-tie carry (B7 vs B4).** Hypothesis: arm-tie raises carry even though v20 scored it inert on crossing. v20 best-checkpoint `held_hinge_max` for arm-tie cells G5/G6/G7 = 1.3179/1.3918/1.4453 versus non-arm-tie G1/G2/G3/G4 = 1.3184/1.2776/1.3040/1.2911 — the arm-tie cells occupy the top of the range, but this is confounded by checkpoint step in v20, so B7 vs B4 is the clean test. If it holds, arm-tie is the lever that makes a `held_hinge` target reachable, and v21's "calibrate or skip" framing is wrong.

Standing rule 12 is satisfied by construction: DV1–DV4 are the round's own dependent variables and every summary table must carry them.

---

# 7. Route A / M22

Inherit v21 §8 unchanged: all saved checkpoints adjudicated mechanically against red-lines (standing rule 6 — endpoints drift after goal saturation, as at v14 step3000 and v18 step2500), 16 episodes per checkpoint, first episode only, strict trace topology validation, `N/A` never `0%` for zero denominators.

Two selections per cell, kept distinct:

- **Mechanism checkpoint** — best on DV1/DV2, used for scientific attribution.
- **Release checkpoint** — best under the §9 acceptance profile, used for any release claim.

Per-bucket reporting (height / spring / mass) plus the heavy/light torque split.

---

# 8. Route B

Inherit v21 §11. Pooled48 = seeds {0,1,2} × 16 envs; holdout64 = seeds {3,4,5,6} × 16; render 5 episodes × 3 cameras with QA contact sheets; the heavy bucket drawn from the hashed manifest of §4.1. **B1 must complete pooled48 first**, because it defines the reference the other cells are gated against.

---

# 9. Acceptance

Integrity gates are absolute: strict-valid records and traces, hashes/paths/configs/seeds/checkpoints matching, zero fallback evaluations, no NaN/Inf or zero-filled missing values, natural completion or documented replay, GPU7 unused, no hidden control or action override, resolved config matching the declared factors.

**`upper_dof_overspeed` is not a hard gate in v21-B.** See §2.1.

### STANDARD release profile

| scope | threshold | basis |
|---|---|---|
| canonical16 | goal ≥15/16, held-crossing ≥15/16 | unchanged from v21 |
| pooled48 | goal ≥**46**/48, held-crossing ≥46/48 | restores the north-star red-line v21 set to 45 |
| pooled48 | `stage_overtime` ≤6/48 | measured 6.2% warm start; theta lengthens the pre-send phase |
| pooled48 | `upper_dof_overspeed` ≤3/48 | measured base rate 2.9%; a zero gate passes 3.6% of the time |
| pooled48 | opening slip p95 ≤0.035 m | measured 0.0094 / 0.0124 — ample headroom, kept |
| pooled48 | pre-send planar p95 ≤0.90 m | measured 0.6531 / 0.6748 |
| pooled48 | pre-send yaw p95 ≤0.70 rad | measured 0.5636, already over v21's 0.55 |
| pooled48 | task time p95 ≤19.0 s | measured 15.98 / 15.83 — kept |
| pooled48 | `held_hinge` p50 | **report-only + non-regression vs B1** (measured 1.2911/1.3400 vs v21's 1.35 requirement) |
| holdout64 | goal ≥61/64, held-crossing ≥61/64, overtime ≤8/64, overspeed ≤4/64 | scaled from pooled |
| crossing | p50 ≥1.10 rad absolute; p50 ≥ theta − 0.10; p10 ≥ theta − 0.20 | measured overshoot +0.116 makes these comfortable at theta 1.20 |

### Non-regression against B1

Goal-rate drop ≤0.04; overspeed-rate increase ≤0.02; task-time p95 increase ≤3.0 s. This is what replaces the absent pooled48 precedent, and it is also the honest way to score the arm axis: a weaker arm is *expected* to cost something, and the question is how much.

One bounded adaptation window, at the decision point after census + zero-shot + pilot, immutable after freeze.

---

# 10. Pre-registered forks

| id | trigger | response |
|---|---|---|
| F1 | guard extension cannot preserve v20 byte-compatibility | introduce theta as an independent key; v20 path untouched |
| F2 | zero-shot at selected k gives canonical goal <3/16 **and** majority failing to reach stage 3 | step back one grid point, re-probe once; if still collapsed convert B3/B4/B5/B7 to a theta ladder {1.05, 1.15, 1.25, 1.25-seed1} and record `ARM_AXIS_DEFERRED_TO_V22` |
| F3 | census status is exactly `CENSUS_RIGHT_CENSORED` or `BOUNDARY_NOT_SEPARABLE` | skip zero-shot/pilot/tie, freeze `THETA_ONLY_FALLBACK_F3`, and launch all cells as ARM_V20/100 with the exact ladder B1=.90 s0, B2=1.20 s0, B3=1.05 s0, B4=1.15 s0, B5=1.25 s1, B6=1.20 s1, B7=1.25 s0; no invented k |
| F4 | B4 pilot send-latch fire rate <60% canonical | drop theta to 1.10 for all theta-high cells before freeze |
| F5 | no cell satisfies STANDARD | a non-release result is a completed scientific outcome; report DV1–DV4 and stop |

Under F2 or F3 the round still answers v21's original question through B1/B2/B6 plus the converted ladder cells, so the arm axis cannot block the round.

---

# 11. Deliverables

1. `V21B_P0_ADMISSION.json` — guard tests, resolved-config assertions, checkpoint hash, GPU binding.
2. `V21B_TORQUE_CENSUS.{json,md}` — per-joint/per-bucket utilization and the selected `ARM_REALISTIC`, with the selection rule stamped before results.
3. `V21B_ZERO_SHOT_PROBE.{json,md}` — frozen-policy behaviour under the selected profile.
4. `V21B_PILOT_B4.{json,md}` — pilot readout and the frozen adaptation decision.
5. `V21B_ROUTE_A_METRICS.{csv,json}` + `V21B_DV_READOUT.md` — must contain DV1–DV4 in its summary table (standing rule 12).
6. `V21B_ROUTE_B.{json,md}` — pooled48/holdout64/render/final analysis.
7. A per-round memory entry and a `a2_piper_longterm_TODO.md` sync (standing debt: worker sessions own these).

## Outstanding planner actions (not worker scope)

The handoff ADDENDUM ¶2–3 and TODO table A still carry corrections C1–C3 in their original, superseded form. They should be amended by the planner before the next round inherits them.

---

*One-sentence brief: v21-B keeps base_v21's corrected diagnosis and Route-B apparatus, caps theta at 1.20 on measured reachability evidence, re-cuts six acceptance thresholds that measurement shows would have blocked the round (the `upper_dof_overspeed = 0` hard gate passes only 3.6% of the time), unblocks the theta freeze guard that currently prevents even the zero-shot probe from running, and spends the same seven GPUs on a 2×2 theta × arm-limit ablation so that the round advances the force-feasibility thesis instead of only polishing crossing geometry.*
