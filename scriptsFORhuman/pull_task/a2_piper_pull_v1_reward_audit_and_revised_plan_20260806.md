# A2+Piper Pull v1 — Reward Audit and Revised Optimization Plan

**Date:** 2026-08-06 HKT  
**Task:** right-hinged, in-opening pull door (`door_open_io="in"`)  
**Recommended plan ID:** `a2_piper_pull_v1_reward_port_and_stage_semantics`  
**Primary change from the prior v1 proposal:** preserve and port the mature push reward topology; do not globally disable mature rewards merely because they are active in a failed pull-v0 trajectory.

---

## 1. Executive decision

The earlier recommendation to set `dont_push_door_handle` and `target_root_distance` to zero as the v1 baseline was too aggressive. The reward audit changes that recommendation.

The pull-v0 failure is better explained as a **reward-topology and activation-semantics migration defect**:

1. Pull v0 retained most Stage 0–2 and grasp-continuity rewards successfully.
2. It retained the mature Stage-4 rewards `dont_push_door_handle=3.0` and `target_root_distance=12.0`.
3. But it removed the two mature A2 Stage-3 bridge rewards that the actual v20 G4 push winner used:
   - `a2_stage3_unlatch_hold: 3.0 -> 0.0`
   - `a2_stage3_stage4_hold_and_drive: 8.0 -> 0.0`
4. It also replaced/bypassed the inherited physical Stage 3→4 condition with `a2_pull_threshold_mode: report_only`, allowing Stage 4 to be reached with effectively zero hinge opening.
5. It disabled the mature v20 traversal-economics gate. Therefore the same `target_root_distance=12.0` scale no longer had the same runtime semantics: the source's disabled legacy path applies a constant Stage-4 multiplier of `0.5`, whereas the mature v20 path pays zero before `send_ready` and ramps only afterwards.

The revised v1 therefore does **not** invent a new reward set. It does four things:

```text
restore the mature Stage-3 bridge rewards
    + restore the physical Stage 3→4 gate
    + retain mature Stage-4 rewards with correct event routing
    + port direction-dependent traversal rewards only after true opening exists
```

The primary v1 baseline keeps direct handle reward at zero. This is deliberate: the actual mature v20 G4 winner also used `push_door_handle=0.0`. Direct handle shaping becomes a pre-registered rescue ablation, not the first fix.

---

## 2. Evidence authority and limits

### 2.1 Files used as sources of truth

1. **Mature push winner saved run config**

```text
a2_piper_v20_cloud_delivery_expanded_20260801/
  logs_rl/a2_piper_full_stage_a2_base/
  base_v20_R3_G4-20260731_004712/config.yaml
```

Local extracted copy:

```text
/mnt/data/v20_extract/base_v20_R3_G4_config.yaml
sha256 76f50e4bd4e4af69d0e404687de4b904a55a50a6bab72f244048352701a29ec2
```

2. **Pull-v0 release-candidate eval resolved config**

```text
logs_eval/a2_piper_pull_v0/p5_release_candidate/
  seed0_step2500_render/hydra/.hydra/runtime_config.yaml
sha256 e6564359c5cb15591cc0243747419bf43cb1a0182788b53720d2c57f111c25e5
```

3. **Pull-v0 release-candidate terminal metrics**

```text
logs_eval/a2_piper_pull_v0/p5_release_candidate/
  seed0_step2500_render/eval/metrics_eval.json
sha256 57e3442abfc824fcc7c5500601887e7228eb98e37af45c89153668252d82f56c
```

4. **Current mature push reward implementation**

```text
gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml
gr00t/rl/envs/door/door_open_a2_base.py
```

Relevant source symbols include:

```text
a2_grasp_gated_door_reward_components
_stage_3_to_4_advance_condition
_reward_a2_stage3_unlatch_hold
_reward_a2_stage3_stage4_hold_and_drive
_reward_push_door_hinge
_reward_dont_push_door_handle
_reward_target_root_distance
a2_v20_stage4_target_root_scale
_reward_a2_corridor_door_wide
_reward_a2_corridor_clean_passage
```

### 2.2 Two unresolved provenance gaps

The ZIP does not contain the original pull-v0 `logs_rl/<training-run>/config.yaml`. Therefore the pull numbers below are verified as **eval-time resolved values**, not independently proven training-time values. P0 must compare them against the actual saved training config before formal v1 training.

The remote pull branch still points to documentation commit `4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09`; the actual pull implementation, including `DoorOpenA2Pull` and the exact `pull_door_hinge` / event overrides, is not present remotely. Consequently:

- formula-level conclusions about inherited push functions are source-verified;
- formula-equivalence of pull-specific overrides is **not yet verifiable**;
- formal v1 implementation must be blocked until the executed pull-v0 source is committed and source-locked.

---

## 3. Audit method: formula, scale, and activation are separate questions

A reward is not simply “reused” or “disabled.” Three independent properties must be audited:

| Dimension | Audit question |
|---|---|
| **Formula** | Does the mathematical quantity still represent the desired physical behavior in pull? |
| **Scale** | Is the mature push coefficient still the right baseline coefficient? |
| **Activation** | Is the term paid at the correct pull physical event/stage? |

Examples:

- `dont_push_door_handle`: reuse formula and scale; repair activation by restoring true Stage-4 admission.
- `target_root_distance`: reuse formula and scale; port the mature gate to pull-specific clearance/path-reversal readiness.
- `a2_corridor_door_wide`: reuse the objective and approximate scale, but adapt its push-specific world-X/corridor implementation.
- `a2_stage3_unlatch_hold`: reuse formula, scale, and Stage-3 activation unchanged because the handle/latch joint coordinate remains positive in pull.

---

## 4. Critical three-way reward comparison

The current shared YAML is not the trained baseline. The saved v20 G4 config wins.

| Reward | Current shared YAML | v20 G4 saved truth | Pull-v0 P5 eval | Audit decision |
|---|---:|---:|---:|---|
| `push_door_handle` | 6.0 | **0.0** | 0.0 | Keep direct handle reward zero in primary v1. |
| `pull_door_handle` | N/A | N/A | 0.0 | Keep zero; rescue ablation only. |
| `push_door_hinge` / `pull_door_hinge` | 6.0 | **6.0** | **6.0** under pull alias | Reuse one positive-hinge formula; prove alias equivalence. |
| `a2_stage3_unlatch_hold` | 0.0 default | **3.0** | **0.0** | Restore 3.0. This is the missing dense handle/unlatch bridge. |
| `a2_stage3_stage4_hold_and_drive` | 0.0 default | **8.0** | **0.0** | Restore 8.0. This bridges retained grasp to positive hinge work. |
| `dont_push_door_handle` | 3.0 | **3.0** | **3.0** | Keep 3.0; correct Stage-4 admission instead of disabling it. |
| `target_root_distance` | 12.0 | **12.0** | **12.0** | Keep 12.0; restore/adapt event gating. |
| `a2_corridor_door_wide` | 0.0 default | **4.2666667** | **0.0** | Port after true Stage 4; adapt world-X/corridor logic. |
| `a2_corridor_clean_passage` | 0.0 default | **1.0** | **0.0** | Port after true Stage 4. |
| `penalty_a2_v20_pre_send_crossing` | 0.0 default | **-15.0** | **0.0** | Port as pull pre-reversal/crossing protection, not byte-for-byte. |
| `penalty_a2_door_body_contact` | 0.0 default | **-3.0** | **0.0** | Keep report-only until pull contact decomposition exists. |
| `penalty_a2_posture_command_l1` | 0.0 default | **-0.3** | **0.0** | Defer; pull may legitimately require different base yield/posture. |

The complete 67-key matrix is supplied separately as `a2_piper_pull_v1_reward_audit_matrix.csv`.

---

## 5. What the source says about the missing bridge

### 5.1 `a2_stage3_unlatch_hold` is already the desired dense handle reward

The source computes, conceptually:

```text
hold_streak_ok = stable bilateral grasp streak >= configured control steps
unlatch_press  = clamp(handle_position / 0.6 rad, 0, 1)
near_closed    = hinge_position < 0.1 rad

unlatch_hold = hold_streak_ok * unlatch_press * near_closed
```

It is active in Stage 3. The pull-v0 config already carries the same geometry-independent constants:

```yaml
a2_grasp_streak_control_steps: 5
a2_stage3_unlatch_handle_position_norm: 0.6
a2_stage3_unlatch_near_closed_hinge_threshold: 0.1
```

Important correction to the earlier interpretation: `0.6` is used directly as a **radian normalization denominator**, not as “60% of the 45° handle range.” It is approximately 34.4°.

This term is exactly the reward the current failure needs: it pays positive handle rotation only while grasp is stable and the door is still near closed. It is more selective than the generic DoorMan `push_door_handle` reward.

### 5.2 `a2_stage3_stage4_hold_and_drive` is the existing causal bridge

The source computes, conceptually:

```text
hold_and_drive = stable_grasp * clamp(positive_hinge_velocity / 0.1 rad/s, 0, 1)
```

It is active across Stage 3, Stage 4, and Stage 5, preventing an income cliff at Stage 3→4. Pull-v0 preserved the configuration constants but set the scale to zero.

### 5.3 The handle and hinge joint coordinates do not reverse in pull

The door builder keeps:

```text
handle joint: axis X, legal angle 0..45 deg
latch mimic: positive handle rotation retracts the latch
hinge: positive angle opens the right-hinged door
```

Changing robot side changes the required wrist/base motion, not the desired sign of handle angle or hinge angle. Therefore the two A2 bridge formulas are direction-invariant and should be reused directly.

---

## 6. Why `dont_push_door_handle` should be retained

The source defines it only for Stage 4 and Stage 5:

```text
-handle_velocity + normalized preference for handle returning toward zero
```

That is correct once the door is genuinely open and the latch cannot re-engage. The pull-v0 issue is that Stage 4 was not genuine.

P5 evidence:

| Env | First E3 step | First E4 step | Terminal Stage-4 duration | Hinge at first positive event | Held hinge max |
|---|---:|---:|---:|---:|---:|
| 0 | 454 | 455 | 198 control steps | `1.576e-9 rad` | `0.0018587 rad` |
| 1 | 237 | 240 | 413 control steps | `1.588e-9 rad` | `0.0014142 rad` |

The Stage-4 `dont_push_door_handle` episode sums were:

```text
env0: 11.900930 episode-sum
env1: 24.581676 episode-sum
```

Using `scale=3.0`, `control_dt=0.02 s`, and the terminal Stage-4 durations, the implied mean raw value was approximately:

```text
env0: 1.002
env1: 0.992
```

Thus the term behaved as designed: it paid almost its maximum throughout Stage 4 because the handle was near zero. The defect was the false Stage-4 label, not the reward formula.

**v1 action:** keep `dont_push_door_handle=3.0`; restore a Stage 3→4 gate requiring real hinge opening and valid grasp. Do not add an extra scale-zero workaround.

---

## 7. Why `target_root_distance` should be retained but re-routed

The source formula is reusable:

```text
track root velocity along the direction to target
+ track Euclidean distance to target
```

The mature v20 implementation already contains an economics gate:

```text
if traversal economics disabled:
    Stage-4 multiplier = 0.5   # legacy path
else:
    multiplier = 0 before send_ready
    multiplier ramps from 0 to 0.5 after send_ready
```

Resolved configuration difference:

| Selector | v20 G4 | Pull v0 |
|---|---:|---:|
| `a2_v20_traversal_economics_enabled` | `true` | `false` |
| `a2_v20_send_latch_enabled` | `true` | `false` |
| `a2_v20_send_hinge_threshold` | `0.9 rad` | `1.0 rad`, latch disabled |
| `target_root_distance` scale | `12.0` | `12.0` |

So pull v0 did not preserve the mature behavior even though the coefficient was identical. It fell back to the legacy Stage-4 multiplier.

For pull, the final target `[-2, 0, 0.5]` is valid only after the robot has created panel clearance and begun path reversal. The correct migration is:

```text
keep target_root_distance scale = 12.0
keep the same root tracking formula
replace push send_ready with pull clearance/path-reversal-ready
pay zero before that event
activate/ramp toward the final target after that event
```

This is reward reuse with event adaptation, not reward removal.

---

## 8. Full reward audit by class

### 8.1 Reuse unchanged or with only target-frame verification

The audit classifies 34 terms as `KEEP_EXACT`, plus 8 terms as `KEEP_SCALE_VERIFY_FRAME`. These include:

- generic smoothness, joint-limit, command-limit, termination, and safety terms;
- Stage-0 approach and facing objectives;
- pregrasp position/orientation/finger terms;
- all Stage-2 close/contact/squeeze/stability terms;
- Stage-3/4 close-command, both-contact, opposite-squeeze, force-window, stability, and over-force terms;
- Stage-4 mild grasp-target retention;
- completion, save-time, frozen-leg-prior tracking.

The pull-v0 P5 episodes reached and retained bilateral stable contact, so there is no evidence basis for retuning the Stage-0–2 reward scales in v1.

The terms requiring frame verification rather than scale changes are:

```text
walk_to_door
penalty_face_door
pregrasp_target_distance
gripper_handle_orientation
grasp_target_distance
a2_stage2_handle_center_y
a2_stage2_handle_approach_xz
penalty_a2_stage1_stage2_base_forward_creep
```

The first seven depend on mirrored spawn/active-handle target geometry. The last one is especially important because the inherited source uses push-side world-X geometry.

### 8.2 Restore exactly from the v20 winner

```yaml
a2_stage3_unlatch_hold: 3.0
a2_stage3_stage4_hold_and_drive: 8.0
```

These are the core v1 reward modifications.

### 8.3 Keep zero in the primary baseline

```text
push_door_handle / pull_door_handle
push_door_force
a2_v20_arm_tangent_carry
a2_v20_handle_arc_tracking
a2_v20_R2_evidence_component
grasp_finger_dof_pos_l1
penalty_a2_stage2_single_finger_contact
penalty_a2_stage4_arm_default_pose_l1
penalty_unused_dof_deviation_l1
```

These were zero in the mature push winner or are evidence hooks. Turning them on would introduce a new reward axis rather than repair migration.

### 8.4 Reuse later with pull-specific direction/event adaptation

```text
a2_corridor_door_wide
a2_corridor_clean_passage
penalty_a2_v20_pre_send_crossing
target_root_distance gating
stage5 hold-income continuity
```

The source's corridor implementation contains push-specific root-X and crossing assumptions. These objectives are valuable, but they should be ported only after true Stage-4 occupancy exists.

### 8.5 Defer pending measured decomposition

```text
penalty_a2_door_body_contact
penalty_a2_posture_command_l1
```

Pull changes the contact and base-yield regime. Restoring the push coefficients without pull data would violate measured-calibration discipline. Keep telemetry active and reward scale zero in the first v1 wave.

---

## 9. Revised v1 task definition

### 9.1 Scope

```text
PLAN_ID = a2_piper_pull_v1_reward_port_and_stage_semantics

Actor initialization  = pull-v0 checkpoint
Critic initialization = reset
Optimizer              = reset
Staged-reset buffers   = clear/rebuild
Robot/actuators        = frozen
Door physics           = frozen
PPO architecture       = frozen
Primary DV             = stable unlatch and true Stage 3→4 rate
Full goal              = report_only in the first wave
```

### 9.2 What v1 is not

- not an actuator, friction, spring, mass, or gripper-force round;
- not a direct-handle-reward round by default;
- not a new PPO/critic architecture round;
- not a path-traversal optimization round until true Stage 4 exists;
- not a rewrite of mature push rewards.

---

## 10. P0 reward-audit admission before GPU training

### P0.1 Source and config lock

Required artifacts:

```text
actual pull-v0 implementation commit
actual pull-v0 training logs_rl/.../config.yaml
pull-v0 checkpoint hash
p5 eval runtime-config hash
v20 G4 saved-config hash
```

Block formal training if the training config cannot be matched to the checkpoint or if the pull-specific source is still uncommitted.

### P0.2 Machine-readable migration matrix

Generate one row per reward:

```text
reward key
source function
stage decorator / event mask
v20 G4 saved scale
pull-v0 training scale
pull-v0 eval scale
formula inputs
world-frame dependence
joint-coordinate dependence
activation predicate
v1 decision
```

The supplied CSV is the initial 67-key matrix; the worker must add exact source-function hashes and pull-specific override locations.

### P0.3 Canonical state reward probe

Construct deterministic states, without policy learning:

```text
S0: approach
S1: pregrasp
S2: stable grasp, handle≈0, hinge≈0
S3a: stable grasp, partial positive handle rotation, hinge≈0
S3b: stable grasp, handle near 0.6 rad, hinge≈0
S3c: stable grasp, positive hinge velocity
S4: hinge > 0.25 rad with valid grasp
S4R: pull clearance/path-reversal-ready
S5: crossing/traversal
```

For every state, record per control step:

```text
raw reward
scale
weighted reward
active/inactive reason
stage mask
physical event mask
```

Admission requirements are structural, not performance thresholds:

```text
no Stage-4-only reward active in S2/S3a/S3b
unlatch_hold positive in S3a/S3b only with valid grasp
hold_and_drive positive only with valid grasp and positive hinge velocity
Stage 3→4 false below 0.25 rad
Stage 3→4 true only above threshold with grasp streak
final target reward zero before pull-clearance/path-reversal readiness
```

### P0.4 Push/pull paired formula test

For dimension-identical doors and equivalent joint/contact states:

- direction-invariant rewards must match numerically;
- target-frame rewards must match after the active-face transform;
- world-X/crossing rewards must exhibit the explicitly intended sign change;
- `pull_door_hinge` must match the inherited positive-hinge formula exactly.

### P0.5 Reward-income telemetry

Every evaluation must export, with units:

```text
episode-sum
per-active-control-step mean
positive-income fraction
active-step denominator
reward share before/after each physical event
stationary rent by stage
```

Do not compare episode sums across rewards without their active-step denominators.

---

## 11. Implementation changes

### Change 1 — Restore the mature Stage-3 bridge

```yaml
a2_stage3_unlatch_hold: 3.0
a2_stage3_stage4_hold_and_drive: 8.0
pull_door_handle: 0.0
pull_door_hinge: 6.0
```

Prefer reusing the existing A2 functions rather than creating pull duplicates.

### Change 2 — Restore inherited physical Stage 3→4 admission

Use the existing mature condition:

```text
hinge_position > 0.25 rad
AND valid 5-control-step grasp streak
```

Pull E3/E4 telemetry, stage advancement, reward activation, and staged-reset admission must derive from the same predicate family. `report_only` may remain as a diagnostic mode, but not as the training stage transition.

### Change 3 — Retain `dont_push_door_handle=3.0`

No new custom gate is necessary if Stage-4 admission is physically correct. Verify through the canonical state probe that it is inactive below true Stage 4.

### Change 4 — Retain `target_root_distance=12.0` and port mature gating

Do not set its coefficient to zero. Replace the disabled legacy Stage-4 multiplier with a pull-aware readiness latch:

```text
pull_clearance_ready / path_reversal_ready
```

Before this event: runtime multiplier zero.  
After this event: activate/ramp the same target-root formula toward `[-2, 0, 0.5]`.

The first implementation should reuse the existing v20 economics machinery with a direction-aware event provider rather than add a separate reward implementation.

### Change 5 — Rebuild staged-reset buffers

Discard every pull-v0 Stage-4 snapshot that does not satisfy the restored physical Stage 3→4 predicate.

Cache only:

```text
Stage 3: stable grasp and physically consistent handle/latch state
Stage 4: hinge > 0.25 rad with valid grasp
Stage 5: only after pull-specific reversal/crossing admission is implemented
```

### Change 6 — Preserve deferred terms as telemetry

Keep body-contact and posture-command measurements, but retain zero scales in the first v1 wave.

---

## 12. Training structure

The existing v0 checkpoint is already the fixed baseline artifact. Do not spend a formal cell reproducing it.

### D0 — Frozen actor reward replay, no learning

Run the pull-v0 actor in the corrected v1 environment. Purpose:

- verify reward activation;
- verify Stage-4 false positives disappear;
- quantify how often the frozen actor naturally produces handle rotation under the restored gate.

### V1-A — Physical gate repair only

```text
actor warm-start: pull v0
critic/optimizer reset
v0 reward scales retained
physical Stage 3→4 gate restored
invalid reset snapshots removed
```

Question: was false stage advancement alone hiding an existing handle-opening tendency?

### V1-B — Mature reward-port cell

V1-A plus:

```yaml
a2_stage3_unlatch_hold: 3.0
a2_stage3_stage4_hold_and_drive: 8.0
```

This is the primary v1 candidate.

### V1-C — Pull traversal-economics port

Run only if V1-B produces true Stage-4 occupancy. Add:

```text
pull-aware clearance/path-reversal latch
target_root_distance mature gating
pull-adapted corridor door-wide / clean-passage terms
pull pre-reversal/crossing protection
stage5 hold-income continuity
```

Do not mix V1-C into the handle/unlatch diagnosis if V1-B never reaches true Stage 4.

### Replication and budget

- V1-A and V1-B: at least two seeds under the same bounded adaptation budget.
- Run the project-standard `64 env × 50 iter` smoke first.
- Select checkpoints by the v1 dependent variables, not by `max_stage` or mean return alone.
- Full goal, E6 reversal, and E7 whole-body clearance remain `report_only` in V1-A/B.

No unmeasured performance threshold is pre-registered. Only source/config integrity and false-event absence are blocking invariants.

---

## 13. Dependent variables

### Primary

```text
stable_unlatch_rate
true_stage3_to4_rate
```

Definitions must use the physical source of truth, not pull-v0 event labels.

### Mechanism funnel

```text
valid_grasp_rate
max_handle_angle_rad
handle_0p6rad_reach_rate
stable_unlatch_duration_control_steps
relock_before_hinge_0p25_rate
positive_hinge_while_valid_hold_rate
hinge_delta_while_valid_hold_rad
capture_loss_during_initial_pull_rate
stage3_overtime_rate
```

### Reward-economics diagnostics

```text
unlatch_hold episode-sum and per-active-step mean
hold_and_drive episode-sum and per-active-step mean
dont_push active-before-true-stage4 count
target_root active-before-reversal-ready count
stage stationary-rent per control step
positive-income fraction at S3a/S3b/S3c/S4
```

### Integrity invariants

```text
false Stage 4 count = 0
Stage-4 snapshot admitted below physical gate = 0
Stage-4-only reward active below physical gate = 0
```

These are implementation-correctness requirements, not performance gates.

---

## 14. Income-continuity audit

| Physical interval | Required positive income | Reward carrier |
|---|---|---|
| Stable grasp → partial handle rotation | grasp/contact continuity plus handle progress | Stage-2/3 grasp terms + `a2_stage3_unlatch_hold` |
| Partial handle rotation → latch clear | continued normalized handle income | `a2_stage3_unlatch_hold` |
| Latch clear → first hinge motion | retained grasp plus hinge velocity | `a2_stage3_stage4_hold_and_drive` + hinge reward |
| Late Stage 3 → early Stage 4 | same hold/drive income on both sides | `hold_and_drive` spans Stage 3/4/5; grasp-retention terms span Stage 3/4 |
| True Stage 4 before reversal readiness | maintain grip/opening; no final-target pull | hold/drive, hinge, mild grasp target; target-root multiplier zero |
| Reversal-ready → crossing | final-target and corridor income | `target_root_distance`, adapted corridor rewards |
| Stage 4 → Stage 5 | no hold-income cliff | restore/adapt Stage-5 hold-income continuity |
| Deliberate release after latch-safe opening | handle may return to neutral | `dont_push_door_handle` remains active in true Stage 4/5 |

This schedule reuses mature rewards while changing only the physical event at which direction-dependent traversal income turns on.

---

## 15. Pre-registered forks

| Trigger | Response |
|---|---|
| V1-A remains in Stage 3 with little handle motion | This is an informative result: gate repair alone is insufficient. Continue to V1-B. |
| V1-B increases handle angle and stable unlatch | Keep direct handle reward zero; continue the mature topology. |
| V1-B still produces almost no handle motion | Run a rescue ablation with the existing generic handle reward formula at scale 6.0; do not adopt it without a replicate. |
| Handle rotates but latch does not physically clear | Audit latch-clear calibration/mechanism; do not increase reward scale first. |
| Latch clears but hinge does not move | Diagnose arm/base tensile trajectory and force transmission; reward migration is no longer the primary blocker. |
| True Stage 4 appears, but policy moves directly toward `[-2,0,0.5]` too early | Port/fix the pull readiness latch and target-root gating; retain scale 12.0. |
| `dont_push_door_handle` causes premature handle return even after true hinge >0.25 rad | Measure latch-safe hinge/relock behavior; adjust event activation, not the coefficient by default. |
| Body-panel contact rises during valid pull | Report decomposition first; only then decide whether `penalty_a2_door_body_contact=-3.0` transfers. |
| V1-B succeeds in one seed only | Treat as basin sensitivity; add the required replicate before any reward conclusion. |
| Actual training config differs from P5 eval config | Recompute this audit against the saved training config before launch. |

---

## 16. Explicit corrections to the previous v1 proposal

1. **Retracted:** globally set `dont_push_door_handle=0`.  
   **Replacement:** keep `3.0`; restore physical Stage-4 admission.

2. **Retracted:** globally set `target_root_distance=0` before redesign.  
   **Replacement:** keep scale `12.0`; port mature event-gated activation.

3. **Corrected:** direct handle reward being zero was presented as the primary migration error.  
   **Replacement:** the actual v20 G4 winner also used direct handle reward zero. The stronger defect is that pull v0 zeroed `unlatch_hold=3.0` and `hold_and_drive=8.0`.

4. **Corrected:** `a2_stage3_unlatch_handle_position_norm=0.6` was previously interpreted as a 60%-of-range threshold.  
   **Replacement:** source uses `0.6` directly as a radian normalization denominator.

5. **Added:** same reward coefficient does not imply same reward behavior. Pull v0 kept target-root scale `12.0` but disabled the mature v20 economics gate, changing runtime income.

---

## 17. Final recommendation

Build v1 around **reward-port fidelity**, not reward deletion:

```text
1. Push and source-lock the actual pull-v0 implementation.
2. Bind the actual pull-v0 training config to the checkpoint.
3. Restore the inherited hinge/grasp Stage 3→4 gate.
4. Restore `a2_stage3_unlatch_hold=3.0`.
5. Restore `a2_stage3_stage4_hold_and_drive=8.0`.
6. Keep direct handle reward zero in the primary cell.
7. Keep `dont_push_door_handle=3.0` with correct stage routing.
8. Keep `target_root_distance=12.0` with pull-aware mature gating.
9. Rebuild staged-reset buffers from physically valid states.
10. Train V1-A and V1-B with replicates; open V1-C only after true Stage 4 exists.
```

The negative result worth reporting is precise:

> Under a physically valid Stage 3→4 gate and the mature v20 G4 Stage-3 reward bridge, the pull policy still fails to achieve stable unlatch or positive held hinge motion across replicated bounded adaptations.

That result would justify moving from reward migration to target-frame/action-sign, latch mechanics, or tensile trajectory/force-transmission analysis. Until then, actuator or gripper redesign is not the evidence-supported next move.
