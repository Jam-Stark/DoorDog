# A2+Piper base_v20 Optimization and Execution Plan (EN)
# Send first, follow second: arm-led, continuous, natural door delivery before traversal

**Date:** 2026-07-28 (HKT)
**Repository / branch:** `Jam-Stark/DoorDog`, `A2_Piper`
**Reference format:** `scriptsFORhuman/a2_piper_base_v19_optimization_plan_20260725.md`
**Numbering:** **P0–P2 (pre-run gates), M45–M49 (implementation, training, and evaluation)**
**Formal resource contract:** **7 training groups in parallel, 1 physical GPU per group, 4096 environments per group; GPU 7 reserved for evaluation**
**Proposed repo path:** `scriptsFORhuman/a2_piper_base_v20_optimization_plan_20260728.md`

**Warm-start checkpoint**

```text
logs_rl/a2_piper_full_stage_a2_base/base_v19/
base_v19_G2_norm_control-20260727_012027/
model_step_002000.pt
```

**Expected SHA-256**

```text
b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d
```

**Load contract:** `policy_only`, `auto_load_latest: false`. All scientific cells use the same checkpoint. G1–G6 use training seed 0; G7 is an independent-seed full-method replicate using training seed 1.

---

## 0. Goal, success definition, and executive decision

### 0.1 Scientific goal

base_v20 must determine whether the remaining undesirable form in the current teacher policy can be corrected by changing the **task semantics and reward schedule**, before introducing realistic Piper arm limits or the force-feasibility-aware base-assist mechanism.

The target behavior is:

> **The arm sends the door to a preregistered safe opening angle while the A2 root remains on the approach side; only after that send condition is satisfied may the base follow through the doorway. During the follow-through, the gripper must continue tracking the handle arc smoothly and stably until a controlled release.**

The round is not successful merely because the robot opens the door or crosses while holding. Those capabilities are already solved. The round succeeds only if the route itself becomes arm-led, temporally ordered, smooth, and repeatable.

### 0.2 Desired episode, phase by phase

1. **Approach and stance:** choose a valid standoff; retain the existing load-bearing pitch/roll behavior.
2. **Pre-grasp and grasp:** reach the handle, establish a debounced bilateral grasp, and remain within the squeeze-force red lines.
3. **Unlatch:** rotate/depress the handle without losing the grasp.
4. **Arm-led send:** open the door through the handle while the root remains on the approach side. Small bounded lateral/yaw relief is legal if P1 shows it is mechanically required; premature root-plane crossing is not legal.
5. **Follow:** after the door reaches the frozen send angle, allow the base to begin traversing while the arm continues following the circular handle path.
6. **Controlled release and pass:** release around the existing 1.60-rad region, avoid body/leg contact with the door, and complete the passage.

### 0.3 Formal success statement

A base_v20 release exists only if a selected checkpoint passes all of the following:

- the existing task and safety gates;
- the new send-before-crossing gates;
- the new task-space arm contribution and handle-arc tracking gates;
- the smoothness gates;
- the pooled48 evaluation;
- the post-selection holdout64 confirmation;
- the render behavior gate.

There is **no v20 no-carry fallback**. If no institution-enabled group passes, base_v20 is a scientific FAIL and G2 step2000 remains the operational reference. A task-success-only control is not relabeled as a v20 release.

### 0.4 Executive decision

base_v20 is **not**:

- another release-threshold sweep;
- a larger `arm_j1` reward;
- a realistic arm-limit round;
- a force-feasibility gate/base-assist round;
- a student-distillation round.

base_v20 instead introduces three explicitly controlled factors:

- **I — Send institution:** the robot may not physically cross the door plane before a grasp-qualified send angle is reached.
- **E — Corrected economics:** traversal and corridor rewards no longer pay for premature crossing; the wide-open wage preserves G2's local gradient while extending the paid region.
- **A — Task-space arm-carry tie-breaker:** reward useful arm-produced motion along the door-handle tangent, not the sign of a single joint.

Seven parallel groups provide the main ablations and an independent full-method replicate.

---

## 1. Evidence basis and findings from base_v19

### F1 — Early physical crossing is the dominant v19 route, not an endpoint-selection accident

The independent M22 supplement covers exactly 70 canonical16 checkpoints: 7 groups × 10 saved steps. It contains 55 `STRICT_VALID` and 15 `STRICT_INVALID` rows, with invalid rows retained rather than converted to zero.

Across the 55 strict-valid checkpoints:

- maximum `hinge_at_crossing_p50` = **0.7868818641 rad** (`G1`, step500);
- checkpoints with `hinge_at_crossing_p50 >= 0.9 rad` = **0/55**;
- checkpoints with `hinge_at_crossing_p95 >= 1.0 rad` = **1/55**;
- median `root_x_at_release_p50` = **0.686123848 m**.

Therefore, the common route is:

1. the root crosses the door plane when the hinge is only about 0.7–0.8 rad;
2. the policy remains in the opening/swinging stages;
3. the moving base drags/sends the door further while the gripper still holds the handle;
4. release occurs after the root has already progressed well through the doorway.

M22 can select the best member of this policy family. It cannot repair a route that appears in essentially every valid checkpoint.

### F2 — G2 step2000 is the correct v20 warm start

Selected pooled48 comparison:

| Metric | G2 step2000 | G3 step750 |
|---|---:|---:|
| Goal | 48/48 | 48/48 |
| Crossing while holding | 48/48 | 48/48 |
| Held hinge p50 / p95 | **1.4336 / 1.5431 rad** | 1.2314 / 1.3122 rad |
| Opening slip p95 | **2.9084 cm — PASS** | 3.5947 cm — FAIL |
| Hinge at release p50 | **1.6055 rad** | 1.4020 rad |
| Overspeed terminations | 0/48 | 0/48 |
| Post-release body contact | 0/48 | 0/48 |

G3 was selected by the v19 preregistered no-carry fallback rule, not because it was the closest policy to the desired arm-led carry form. G2 is the only selected pooled endpoint that passes the 3 cm opening-slip gate and is also the closest to the held-hinge target. It is therefore the least destructive warm start for v20.

### F3 — `arm_j1 > +0.3 rad` is not a valid definition of arm carry

G2 has the strongest held/slip result while its pooled median held-phase `arm_j1` delta is negative. G3 has more episodes above +0.3 rad but materially worse held hinge and opening slip. The sign and magnitude of one joint are coordinate-, posture-, and redundancy-dependent.

Decision: retain `arm_j1` as observability only. The v20 carry definition is task-space motion along the handle tangent, decomposed into rigid-base and arm-relative contributions.

### F4 — The v19 normalization study changed both target and reward slope

With `a2_corridor_door_wide` scale fixed at 4.0:

```text
G2: 4.0 / 1.5 = 2.6667 scaled units per rad
G1: 4.0 / 1.8 = 2.2222 scaled units per rad
G7: 4.0 / 2.0 = 2.0000 scaled units per rad
```

G7 therefore had a 25% weaker local wide-open gradient than G2. Its lower plateau cannot be treated as a clean geometric ceiling result. v20 preserves the G2 slope while moving the saturation point.

### F5 — Current reward topology rationally pays the early-crossing route

The present environment does all three of the following:

- keeps `target_root_distance` alive in unreleased stage4 at half scale;
- permits root crossing itself to activate the corridor latch;
- then pays corridor-wide income while the root is already through the plane but still below the corridor cutoff.

At reward scale 12, the unreleased-stage4 traversal income remains large. The policy is not ignoring the desired behavior; it is optimizing a cheaper route that the current task definition explicitly allows and rewards.

### F6 — Staged reset remains necessary and must become v20-state-complete

DoorMan's staged-reset design exists to place on-policy occupancy in difficult downstream contact states. A2+Piper already relies on the same principle. v20 must keep the staged-reset ratios and capacity fixed so the new round changes only the intended factors.

Any new monotonic latch, reference pose, or event state that changes reward/termination must be included in staged-reset snapshot/load. Restoring robot and door generalized coordinates without restoring `send_ready` and the corresponding reference state would create an invalid Markov state and corrupt the experiment.

---

## 2. Decisions and scope boundaries

### D1 — Warm start

Use G2 step2000 for every cell. Before any runtime test, verify the checkpoint hash and the checkpoint-adjacent saved config. A missing or mismatched checkpoint is a hard preflight failure.

### D2 — Keep the current task regime fixed

In scope:

- right-hinge, out-opening/push lever doors;
- the existing height, spring, and mass ranges;
- the existing M39 gripper material/gain package;
- the existing F2 arm soft-margin fix;
- teacher PPO only.

Out of scope:

- left/right mirror;
- pull/in-opening doors and `door_open_io`;
- realistic Piper arm effort/velocity limits;
- force-feasibility gate/base assistance;
- new cameras;
- student DAgger or GRPO;
- actor observation/action dimension changes.

### D3 — Freeze the send angle through a physical feasibility probe

The provisional candidate set is `0.9 / 1.0 / 1.1 / 1.2 rad`. P1 selects the highest angle that is physically feasible under a live grasp on at least 46/48 pooled probe episodes. The angle is frozen before formal training and may not be moved in response to training results.

### D4 — Institution and economics are separate factors

A hard task constraint and a reward correction answer different questions. They are not bundled in every cell:

- I tests whether the route must be made institutionally necessary;
- E tests whether removing the premature traversal auction is sufficient or additionally helpful;
- I+E is the minimal intended method.

### D5 — Task-space arm contribution, not joint choreography

The A factor is a weak tie-breaker applied only when the door is progressing under a valid hold. It cannot pay for stationary arm motion, wrong-direction motion, or contact loss. It does not prescribe `arm_j1` direction.

### D6 — Real arm limits remain a separate round

The arm is still simulation-superhuman relative to the planned force-feasibility study. Changing limits in v20 would simultaneously alter physical capability, base-assist necessity, and the route under study. That would destroy attribution.

### D7 — Use all eight GPUs deliberately

- physical GPUs 0–6: seven one-process training groups, 4096 env each;
- physical GPU 7: strict canonical checkpoint evaluation, pooled endpoints, matched comparisons, and render queue;
- no multi-process group in this round;
- no training job may spill onto GPU 7.

### D8 — No post-hoc fallback

Controls may be operationally competent, but they cannot become a v20 success if they fail the send-first behavior definition. A failed round remains a result.

---

## 3. Evidence vocabulary and adjudication boundaries

The following words have exact meanings in this plan:

- **STATIC PASS:** CPU/unit/Hydra/source-contract checks only. It says nothing about IsaacSim runtime behavior.
- **RUNTIME PASS:** the specified bounded GPU run completed with valid artifacts. It says nothing beyond that topology and duration.
- **POLICY PASS:** the checkpoint passed the specified matched behavior gates.
- **STRICT_VALID:** all required typed telemetry groups are complete and internally consistent.
- **STRICT_INVALID:** evidence is missing, malformed, topology-inconsistent, non-finite, or the eval process failed. The row is retained and is ineligible for selection.
- **N/A:** a metric is genuinely undefined for that episode/checkpoint and carries an explicit reason. N/A is never zero and never automatically PASS or FAIL.
- **Canonical16:** seed0, 16 deterministic matched doors.
- **Pooled48:** seeds0–2, 16 doors per seed, after the checkpoint is selected within a group.
- **Holdout64:** seeds3–6, 16 doors per seed, run only after a cross-group release candidate is frozen. It is not used to select the checkpoint.

The v19 M41 lesson remains binding: goal does not imply a release event. Crossing and release telemetry remain separately typed groups; a goal row may have an all-null release group if the policy finishes while still holding.

---

## 4. P0 — Provenance, baseline, and disabled-path admission

### P0.1 | Checkpoint and repository provenance

**Actions**

1. Record the exact branch head SHA.
2. Verify the G2 checkpoint path and SHA-256.
3. Load the adjacent saved training `config.yaml` and verify:
   - release threshold `1.60`;
   - wide norm `1.50`;
   - M39 material enabled;
   - F2 soft margin enabled, width `0.5`;
   - finger effort `45/45`, Kp `1300`, Kd `32`;
   - 4096-env historical topology;
   - `policy_only` warm-start behavior for the v20 configs.
4. Record the hashes of the plan, all seven configs, reporter scripts, and test files in a preflight manifest.

**Output**

```text
logs_eval/base_v20/preflight/provenance_<timestamp>/
  a2_piper_v20_provenance.json
  a2_piper_v20_provenance.md
  file_hashes.sha256
```

**PASS**

- checkpoint hash exact;
- all source/config files resolve;
- no mutable `last.pt` alias is accepted;
- Git worktree state is recorded;
- no stale old-path fallback is used.

**FAIL / action**

Stop before simulation. Do not substitute a different checkpoint or infer the missing config from an ablation YAML.

### P0.2 | Freeze the v19 evidence baseline

**Actions**

1. Ingest the consolidated 70-checkpoint JSON/CSV.
2. Verify exact coverage: 70 rows, 55 valid, 15 invalid.
3. Ingest the selected G2/G3 pooled comparison and v19 final analysis.
4. Produce a v20 baseline file containing:
   - crossing-angle distribution across all 55 valid rows;
   - root-at-release distribution;
   - selected G1–G7 pooled metrics;
   - exact metric-boundary notes for held hinge and opening slip.

**Output**

```text
logs_eval/base_v20/preflight/baseline_<timestamp>/
  a2_piper_v20_baseline.json
  a2_piper_v20_baseline.csv
  a2_piper_v20_baseline.md
```

**PASS**

- the reproduced aggregate values match the source package;
- invalid rows remain explicit;
- missing held/slip values remain N/A;
- the G2 warm-start decision is reproducible from the report.

### P0.3 | Disabled-path behavior parity

All new v20 selectors default to disabled. Telemetry may be enabled separately from policy semantics.

**Run**

- G2 step2000;
- canonical16, seed0;
- old semantic path versus new code with every v20 behavior/reward selector disabled;
- strict telemetry enabled in both.

**Compare**

- action sequence;
- stage sequence;
- terminal reason;
- goal/complete/crossing counts;
- bilateral/coasting/over-force;
- hinge velocity;
- crossing/release telemetry;
- checkpoint/config binding;
- trace row count and step ordering.

**PASS**

- exact equality for discrete fields;
- floating fields within the existing deterministic tolerance;
- no new reward term emits nonzero value;
- no actor/critic/student observation dimension changes;
- natural exit0 and strict exporter PASS.

**FAIL / action**

No formal training. Find and remove the unintended legacy-path change.

### P0.4 | Reward-unit and decomposition contract

Every new reporter must label reward units explicitly as `episode-sum`, `/20s`, or another exact normalization. Before setting A-factor weights, run counterfactual replay on existing G2 traces and a short zero-shot eval.

**PASS**

- fully engaged A-package income is targeted to approximately 5–10% of successful episode income;
- no new term dominates stage, hinge, or completion income;
- the scale is frozen in a machine-readable calibration artifact before the seven configs are hashed.

---

## 5. P1 — Live-grasp handle-arc feasibility and threshold freeze

The send threshold must be physically feasible under the current simulated arm and gripper. A disconnected static reachability map is not sufficient.

### P1.1 Probe setup

Reuse the existing eval-only DLS hold-oracle infrastructure and start from stable G2 grasp snapshots.

For each door and candidate angle:

1. acquire a valid bilateral grasp and capture the handle-to-TCP relative transform;
2. follow the actual door-handle circular arc;
3. test two modes:
   - **F0 fixed-planar-root:** root XY/yaw held to the capture pose, normal pitch/roll posture retained;
   - **F1 bounded relief:** root planar translation limited to `0.10 m` and yaw change limited to `0.15 rad`, with no root-plane crossing;
4. sweep target hinge angles `0.9 / 1.0 / 1.1 / 1.2 rad`;
5. export per-step IK, Jacobian, joint-margin, contact, arc-error, root-motion, and overspeed data.

The probe is run on seeds0–2, 16 doors per seed.

### P1.2 Per-episode feasibility conditions

A probe episode is feasible only if all are true:

- target angle reached within the probe timeout;
- bilateral contact remains valid through the terminal probe window;
- TCP-handle position error p95 <= `0.03 m`;
- TCP-handle orientation error p95 <= the preregistered probe tolerance;
- no hard/soft joint-limit invalidity;
- no Jacobian condition invalidity;
- no raw/delta action bound violation;
- no upper-DOF overspeed termination;
- no door-body collision;
- root remains on the approach side;
- F1 relief stays within its translation/yaw bounds.

### P1.3 Threshold selection rule

1. Prefer the highest F0 angle with at least `46/48` feasible episodes.
2. If no F0 candidate reaches 46/48, choose the highest F1 angle with at least `46/48` feasible episodes.
3. Require the selected angle to be at least `0.90 rad`.
4. Freeze:
   - `theta_send`;
   - allowed pre-send relief bounds;
   - the selected probe mode;
   - all tolerance values.

**PASS**

A candidate `theta_send >= 0.90 rad` satisfies the pooled rule and the probe artifacts are strict-valid.

**FAIL / action**

Do not launch v20 formal training. A failure below 0.90 rad means the planned behavior is not physically supported by the current geometry/control interface and requires a separate geometry or control investigation.

**Output**

```text
logs_eval/base_v20/preflight/arc_feasibility_<timestamp>/
  a2_piper_v20_arc_feasibility.json
  a2_piper_v20_arc_feasibility.csv
  a2_piper_v20_arc_feasibility.md
  per_env/
```

---

## 6. P2 — Semantic admission and learnability pilot

### P2.1 Zero-shot factor admission

Compose all seven formal configs and evaluate G2 step2000 zero-shot for 16 doors.

This is not a policy-quality test. I-enabled cells are expected to convert the historical early-cross route into `pre_send_root_crossing` failures before retraining.

**Required checks**

- I cells: early crossing produces the exact new terminal reason only before `send_ready`;
- E cells: root crossing alone cannot activate corridor income; target-root reward is zero before send and ramps afterward;
- A cells: task-space terms are zero for stationary, wrong-direction, contact-invalid, and door-closing samples;
- all cells: no hidden action override, no actor-dimension change, no NaN, and exact config binding.

**PASS**

All semantic branches emit the expected signals and exit naturally. Task success is not required for I-enabled zero-shot cells.

### P2.2 Representative learning pilot

Before spending seven full GPUs, run the intended minimal method `G4 = I+E` for:

```text
256 envs × 250 batches, save every 50
```

Use the final formal values of `theta_send`, relief bounds, reward scales, and staged-reset settings.

**PASS**

- natural exit0;
- finite checkpoints and optimizer state;
- no staged-reset restore mismatch;
- last-50-batch send-ready episode rate >= `10%`;
- last-50-batch goal rate is nonzero;
- `pre_send_root_crossing` rate decreases by at least `20%` from the first 50 to the last 50 batches;
- stage4 occupancy remains nonzero;
- no single invalid terminal reason accounts for more than 95% of late pilot episodes.

This is only a learnability admission test, not a v20 behavior PASS.

### P2.3 Pre-approved curriculum fallback

If P2.2 fails while P1 confirms physical feasibility, use one common curriculum for every I-enabled formal cell:

- batches 0–250: early crossing receives a one-shot event penalty; E economics are already active where selected, but early crossing is not terminal;
- batch 250 onward: hard `pre_send_root_crossing` termination is enabled;
- the schedule is fixed before formal launch and included in the config hash.

Rerun P2.2. If the curriculum pilot also fails, do not launch the seven-cell matrix.

No cell-specific threshold relaxation or mid-run curriculum edit is allowed.

---

## 7. M45 — Send-before-crossing institution (factor I)

### 7.1 Monotonic send latch

Introduce a per-environment monotonic latch:

```text
send_ready[t+1] = send_ready[t] OR (
    valid_bilateral_hold_streak[t]
    AND hinge_position[t] >= theta_send
)
```

Properties:

- set only under a valid grasp-qualified hold;
- never cleared during the episode;
- cleared on a true episode reset;
- restored exactly by staged reset;
- independent of the later release gate;
- available to reward, termination, telemetry, and evaluation;
- not added to the deployed actor observation.

### 7.2 Premature physical crossing

Define a physical crossing event from the existing door-relative root coordinate:

```text
pre_send_root_crossing =
    opening_phase
    AND NOT send_ready
    AND root_x_rel > root_x_margin
```

The provisional numeric margin is `0.03 m`; the final value is frozen in P0/P1 and must only absorb numerical boundary noise.

In I-enabled cells, this event is a distinct terminal failure:

```text
terminal_reason = "pre_send_root_crossing"
```

A crossing after `send_ready` is legal. The condition is not a global base freeze: bounded lateral/yaw/pitch/roll motion remains available.

### 7.3 Required v20 state

At minimum, add and validate:

- `send_ready`;
- first send-ready step;
- first root-plane crossing step;
- hinge angle at first root crossing;
- root SE(2) at opening-phase entry;
- maximum pre-send forward/lateral/yaw displacement;
- valid capture flags;
- handle-to-TCP reference transform for M47;
- first release and crossing event groups as independent telemetry.

All state that affects reward or termination must be registered in staged-reset snapshot/load.

### 7.4 Suggested config keys

```yaml
env:
  config:
    a2_v20_send_latch_enabled: false
    a2_v20_send_hinge_threshold: 1.0          # overwritten by P1 result
    a2_v20_send_hinge_tolerance: 0.05
    a2_v20_pre_send_root_x_margin: 0.03
    a2_v20_pre_send_crossing_mode: disabled  # disabled | penalty | terminal
    a2_v20_pre_send_crossing_penalty_component: 1.0
```

Historical configs remain byte-equivalent with the selectors disabled.

### 7.5 M45 acceptance

**CPU/unit**

- monotonic latch truth table;
- grasp qualification required;
- tolerance and boundary tests;
- reset and partial-reset behavior;
- staged-reset round-trip for `send_ready=false` and `send_ready=true`;
- no duplicate event emission;
- no crossing failure after send;
- fail-fast on malformed state.

**1-env GPU semantics**

- forced early crossing before send -> exact terminal reason;
- crossing after send -> no terminal;
- a door that coasts above the threshold without a valid hold does not set the latch;
- staged reset restores identical branch decisions.

**PASS**

All tests pass, P0.3 legacy parity remains intact, and P2 semantic admission passes.

---

## 8. M46 — Correct traversal and corridor economics (factor E)

E is a package because all of its changes repair the same reward auction. It does not add a hard failure.

### 8.1 Gate stage4 traversal income

Replace the historical fixed unreleased-stage4 factor with:

```text
send_progress = clamp(
    (hinge_position - theta_send) / traversal_ramp_width,
    0,
    1
)

stage4_target_root_scale = 0.5 * send_progress
```

Result:

- before send: no stage4 `target_root_distance` income;
- after send: the historical 0.5 stage4 income returns smoothly;
- stage5/released behavior retains the historical full scale;
- no discontinuous one-step wage cliff is introduced.

Provisional ramp width: `0.20 rad`, frozen before formal training.

### 8.2 Correct the corridor latch

Add a versioned mode:

```yaml
a2_corridor_latch_mode: legacy_root_or_hinge  # historical
a2_corridor_latch_mode: send_ready_v20        # E cells
```

Under `send_ready_v20`:

- root crossing alone cannot activate the corridor;
- the corridor latch activates from `send_ready`;
- corridor income remains conditioned on the existing hold-continuity and root-range logic.

### 8.3 Preserve G2's wide-open gradient

Use:

```yaml
env:
  config:
    a2_corridor_door_wide_hinge_norm: 1.60

rewards:
  reward_scales:
    a2_corridor_door_wide: 4.2666667
```

This preserves the G2 local slope:

```text
4.2666667 / 1.60 ~= 4.0 / 1.50
```

Keep:

- `a2_stage4_release_hinge_threshold: 1.60`;
- `a2_stage4_to5_door_hinge_threshold: 1.25`;
- `push_door_hinge: 6.0`;
- existing clean-passage and body-contact economics;
- M39 and F2.

### 8.4 Suggested config keys

```yaml
env:
  config:
    a2_v20_traversal_economics_enabled: false
    a2_v20_target_root_pre_send_scale: 0.0
    a2_v20_target_root_post_send_stage4_scale: 0.5
    a2_v20_target_root_ramp_width_rad: 0.20
    a2_corridor_latch_mode: legacy_root_or_hinge
```

### 8.5 M46 acceptance

**CPU/unit**

- scale is exactly zero below threshold;
- continuous monotonic ramp;
- exactly 0.5 after the ramp;
- stage5 unchanged;
- root crossing cannot activate the v20 corridor latch;
- `send_ready` does activate it;
- effective wide-open slope assertion;
- legacy branch exact.

**Runtime**

- zero-shot traces show zero traversal income before send;
- the reward becomes nonzero only after the latch and increases continuously;
- no duplicate corridor activation;
- episode-sum decomposition labels are explicit.

---

## 9. M47 — Task-space natural-carry metric and tie-breaker (factor A)

### 9.1 Handle opening tangent

Compute the door-handle opening tangent geometrically from the hinge axis and the hinge-to-handle radial vector. Do not hard-code a world-axis or `arm_j1` sign.

The tangent sign must correspond to positive hinge motion. A synthetic mirrored-geometry unit test must confirm sign correctness even though left/right mirroring is not trained in v20.

### 9.2 Rigid-base versus arm-relative TCP velocity

At each control step:

```text
v_base_at_tcp = v_base + omega_base × (p_tcp - p_base)
v_arm         = v_tcp - v_base_at_tcp

u_base = relu(dot(v_base_at_tcp, tangent_open))
u_arm  = relu(dot(v_arm,         tangent_open))

arm_tangent_share = u_arm / (u_arm + u_base + eps)
```

Only evaluate the share when total positive tangent speed is above a small preregistered floor. Otherwise mark the instantaneous share inactive rather than manufacturing a value from epsilon.

### 9.3 Arc tracking quality

At stable grasp, capture the handle-to-TCP relative transform. During the valid held opening phase, compute:

- relative position error;
- relative orientation error;
- along-handle slip;
- orthogonal arc residual;
- contact-valid fraction.

### 9.4 Raw tie-breaker

The recommended raw term is:

```text
r_arm_carry =
    valid_hold
    * positive_hinge_progress
    * arm_tangent_share
    * arc_tracking_quality
```

It is zero when:

- the door is stationary or closing;
- bilateral hold is invalid;
- total positive tangent motion is below the activity floor;
- the handle-to-TCP reference is invalid;
- the release gate has fired.

The A package may contain two logged components (`arm_tangent_share` and `arc_tracking_quality`) but is treated as one experimental factor. Its scale is frozen by P0.4.

### 9.5 Suggested reward registry

Register at zero in the shared reward YAML:

```yaml
a2_v20_arm_tangent_carry: 0.0
a2_v20_handle_arc_tracking: 0.0
```

Only A cells enable the frozen scales.

### 9.6 M47 acceptance

**Pure-function tests**

- pure base motion -> arm share 0;
- pure arm-relative tangent motion -> arm share 1;
- equal positive contributions -> 0.5;
- wrong-direction motion -> inactive/zero reward;
- zero-motion denominator -> inactive, finite output;
- rotational base contribution is included;
- rigid-transform invariance;
- mirrored synthetic door tangent sign;
- non-finite and malformed inputs fail fast.

**Runtime tests**

- no A income before a valid grasp/reference capture;
- no A income after release;
- no A income without positive hinge progress;
- per-step values agree with an offline recomputation from the exported trace;
- the term contributes the P0-frozen fraction of episode income.

---

## 10. M48 — Strict v20 telemetry, M22, paired analysis, and final judgement

v20 must not repeat the v19 boundary in which held hinge and opening slip were unavailable for most checkpoint rows.

### 10.1 Required canonical16 checkpoint fields

For every strict-valid v20 checkpoint, export:

**Task and safety**

- goal / complete;
- max stage;
- terminal reason counts;
- crossing while holding;
- bilateral, coasting, over-force;
- hinge velocity p95;
- upper-DOF overspeed;
- post-release body contact and force.

**Send-first behavior**

- send-ready count and first-send step;
- pre-send crossing count;
- hinge at first root crossing p10/p50/p95;
- root x at first crossing;
- pre-send root forward/lateral/yaw displacement p50/p95;
- stage4 dwell and overtime.

**Carry and smoothness**

- held hinge p50/p95/max;
- opening slip p50/p95;
- arm tangent share p10/p50/p95 in the pre-send and post-send held phases;
- TCP-handle position/orientation error p50/p95;
- orthogonal arc residual;
- hinge acceleration/jerk p95;
- arm action-rate and action-jerk p95;
- task time and stage durations.

**Observability only**

- `arm_j1` and all arm-joint held-phase deltas;
- release hinge distribution;
- corridor slip.

### 10.2 Strict schema rules

- a goal row requires non-null crossing evidence;
- release evidence remains an independent all-null/all-non-null group;
- a strict-valid goal row with a valid held phase requires non-null held-hinge and opening-slip groups;
- if a metric is undefined, emit typed `N/A` plus reason and denominator;
- no missing value becomes 0;
- all reward decomposition fields carry units;
- trace topology must be ordered, unique, contiguous, and terminal-consistent;
- checkpoint path, SHA, saved config, seed, topology, and artifact directory must bind exactly.

### 10.3 Mechanical M22

- discover all ten numeric checkpoints per group: steps 250–2500;
- ignore `last.pt` and mutable aliases;
- run canonical16 seed0 on all 70 checkpoints;
- preserve strict-invalid rows;
- select one checkpoint per group by the preregistered lexicographic rule in Section 15;
- run seeds1/2 only after within-group selection;
- produce a pooled48 endpoint report for all seven selected checkpoints.

### 10.4 Matched factor comparisons

Use identical per-env doors to compute paired differences:

- G1 -> G2: E without I;
- G1 -> G3: I effect;
- G3 -> G4: incremental E under I;
- G3 -> G5: incremental A under I;
- G4 -> G6: incremental A under I+E;
- G6 -> G7: independent-seed replication.

Report paired distributions for:

- hinge at first crossing;
- early-crossing outcome;
- held hinge;
- opening slip;
- arm tangent share;
- arc error;
- hinge/action smoothness;
- task time.

The comparison report may use bootstrap intervals or paired sign counts as descriptive evidence, but pooled48 is not claimed as statistical proof.

---

## 11. M49 — Formal seven-cell training matrix

### 11.1 Factor definitions

- **I:** M45 terminal send-before-crossing institution.
- **E:** M46 target-root gating, send-ready corridor latch, and slope-preserving wide wage.
- **A:** M47 task-space arm-carry/arc-tracking tie-breaker.

All groups keep the same stage machine thresholds, gripper package, F2 fix, staged-reset ratios, PPO architecture, warm start, global batch size, and checkpoint cadence unless a factor column explicitly changes them.

### 11.2 Matrix

| Group | GPU | Train seed | I | E | A | Proposed config | Question |
|---|---:|---:|:---:|:---:|:---:|---|---|
| **G1** | 0 | 0 | — | — | — | `base_v20_G1_g2_continuation.yaml` | Exact G2 continuation/drift control. Does ordinary continuation ever repair the route? |
| **G2** | 1 | 0 | — | ✓ | — | `base_v20_G2_economics_only.yaml` | Are corrected economics alone sufficient without a hard institution? |
| **G3** | 2 | 0 | ✓ | — | — | `base_v20_G3_send_institution_only.yaml` | Is making send-before-crossing mandatory sufficient by itself? |
| **G4** | 3 | 0 | ✓ | ✓ | — | `base_v20_G4_send_economics.yaml` | Minimal intended method: correct task semantics and reward schedule, no motion prescription. |
| **G5** | 4 | 0 | ✓ | — | ✓ | `base_v20_G5_send_arm_tie.yaml` | Does the task-space tie-breaker add value under the institution without E? |
| **G6** | 5 | 0 | ✓ | ✓ | ✓ | `base_v20_G6_full.yaml` | Full v20 method. |
| **G7** | 6 | 1 | ✓ | ✓ | ✓ | `base_v20_G7_full_seed1.yaml` | Independent-seed full-method replication / basin robustness. |

Physical GPU 7 is reserved for evaluation and may not host a training group.

### 11.3 Shared formal settings

```yaml
checkpoint: <exact G2 step2000 path>
checkpoint_load_mode: policy_only
auto_load_latest: false
num_envs: 4096
headless: true
algo.trl.num_total_batches: 2500
callbacks.model_save.save_frequency: 250
```

Keep:

```yaml
env.config.enable_staged_reset: true
env.config.staged_reset_ratios: [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
env.config.staged_reset_max_samples_per_stage: 200
env.config.a2_stage4_release_hinge_threshold: 1.60
env.config.a2_stage4_to5_door_hinge_threshold: 1.25
env.config.a2_arm_dof_overspeed_soft_margin_enabled: true
env.config.a2_arm_dof_overspeed_soft_margin_width: 0.5
```

G1 must preserve the exact G2 norm/scale economics. E cells use the M46 values. A cells use the P0-frozen scales.

### 11.4 Matrix config tests

A CPU config test must assert:

- exact warm-start path and hash reference;
- exact I/E/A factor table;
- exact seeds;
- exact 4096 env, 2500 batches, save250;
- G6 and G7 differ only in seed and descriptive header;
- G1 matches G2-v19 semantics except for v20 telemetry defaults;
- no config silently inherits a nonzero A reward;
- no cell changes arm or gripper physics.

---

## 12. Static, composition, and review admission

### 12.1 Required static tests

1. M45 pure-function/state tests.
2. M46 reward/latch arithmetic tests.
3. M47 task-space decomposition tests.
4. Staged-reset snapshot/load round-trip tests.
5. v20 seven-cell config matrix tests.
6. Observation/action dimension parity tests for teacher and student routes.
7. v20 strict exporter and N/A tests.
8. v20 M22 queue/adjudicator tests.
9. paired reporter tests.
10. final-analysis and render-binding tests.
11. `py_compile` for every changed Python file.
12. Hydra compose for all seven configs and the eval overrides.

### 12.2 Required review lanes

- **CODE_QUALITY:** state ownership, selectors, legacy parity, no hidden action override, no dead code.
- **IsaacLab semantics:** articulation/frame math, root-relative coordinates, contact timing, staged-reset state, device-local tensor behavior.
- **Runtime QA:** actual IsaacSim semantics, exporter completeness, shutdown, process/GPU binding, artifact durability.

Each review result is scoped. Static review does not count as runtime or policy evidence.

### 12.3 Admission gate

Formal launch is forbidden until:

- all static tests pass;
- all seven Hydra compositions pass;
- P0.3 parity passes;
- P1 passes and freezes `theta_send`;
- P2.1 semantic admission passes;
- P2.2 learnability pilot passes, directly or through the frozen common curriculum;
- the final config hashes are recorded.

---

## 13. Runtime smoke plan

### S0 | One-environment deterministic semantics

Run scripted/forced cases for:

- crossing before send;
- crossing after send;
- hinge threshold without grasp;
- valid grasp and send latch;
- staged reset before and after send;
- pure-base and pure-arm task-space motion;
- release-without-crossing and crossing-without-release telemetry.

**PASS:** exact terminal/reward/telemetry semantics, natural exit0, no NaN.

### S1 | Canonical16 zero-shot admission

Run every final config with the warm-start checkpoint, no learning.

**PASS:** config/checkpoint binding, expected factor behavior, strict telemetry, no physics or device failure. Goal is not required for I cells.

### S2 | Seven-group bounded training smoke

Run each cell:

```text
64 env × 50 batches, save at 50
```

**PASS per group**

- natural exit0;
- checkpoint CPU-loadable and finite;
- no OOM/NCCL/renderer/device mismatch;
- no staged-reset restore error;
- all enabled factors emit nonzero telemetry in the intended phase;
- disabled factors remain exactly zero;
- no terminal/reward group is malformed;
- output lands directly in the canonical base_v20 smoke layout.

### S3 | Learnability pilot

P2.2 is the final runtime admission for the institution. The seven formal jobs are launched only after S3 PASS.

---

## 14. Formal launch and GPU allocation

### 14.1 Physical allocation

```text
GPU0 -> G1
GPU1 -> G2
GPU2 -> G3
GPU3 -> G4
GPU4 -> G5
GPU5 -> G6
GPU6 -> G7
GPU7 -> M22/eval/render queue only
```

Each group is one process and sees one physical GPU. Do not convert the contract into 4×1024 or a multi-process group.

### 14.2 Launcher and output contract

Use one versioned launcher root:

```text
logs_rl/launchers/base_v20/base_v20_7cell_<timestamp>/
```

It must contain:

- one command file per group;
- one stdout/stderr log per group;
- PID and GPU binding;
- branch/source/config hashes;
- start/end timestamps;
- exit code;
- natural-exit marker;
- W&B run identity/state;
- no overwrite of existing artifacts.

Formal runs write directly to:

```text
logs_rl/a2_piper_full_stage_a2_base/base_v20/<run-dir>/
```

Do not first write to an old layout and move later.

### 14.3 Training command template

Reuse the validated single-process v19 launcher semantics. Conceptually:

```bash
CUDA_VISIBLE_DEVICES=<physical_gpu> \
${ISAACLAB_PYTHON} gr00t/rl/train_agent_trl.py \
  +exp=wbmanip/door_open_a2_base_lstm \
  +ablation=wbmanip/<base_v20_group_config> \
  project_name=a2_piper_full_stage_a2_base \
  experiment_name=<base_v20_group_name>
```

The generated command, not this schematic snippet, is the source of truth and is saved in the launcher artifact.

### 14.4 Startup acceptance

Within the first runtime window, verify for every group:

- one process bound to the intended physical GPU;
- 4096 environments actually instantiated;
- expected checkpoint loaded in `policy_only` mode;
- correct factor header and resolved values;
- nonzero GPU utilization and stable memory;
- W&B run visible with the correct group identity;
- no traceback, OOM, NCCL, or invalid action/observation message.

### 14.5 Completion acceptance

For every non-stopped formal group:

- trainer global/max batch = 2500/2500;
- all ten numeric checkpoints exist;
- natural process exit0;
- W&B state `finished`;
- no `.writing` or partial checkpoint remains;
- final config and checkpoint hashes recorded;
- launcher and process tree fully closed.

A checkpoint existing on disk is not sufficient evidence of natural completion.

---

## 15. Online checkpoint evaluation and training review

### 15.1 Evaluation queue

GPU7 continuously evaluates newly produced checkpoints in round-robin order. Required total: 70 canonical16 evaluations.

Priority:

1. missing earlier checkpoint for any group;
2. mandatory review steps 500, 1000, 1500, 2000;
3. remaining numeric checkpoints;
4. step2500 last only because it is produced last, not because it is preferred.

A backlog does not authorize skipping checkpoints.

### 15.2 Mandatory midpoint reviews

At steps 500, 1000, 1500, and 2000, produce a cross-group table containing:

- strict status;
- goal/stage distribution;
- send-ready and early-crossing rates;
- hinge at first crossing;
- pre-send root motion;
- held hinge and opening slip;
- arm tangent share and arc error;
- hinge/action smoothness;
- reward decomposition with explicit units;
- terminal reasons;
- task time.

The review may stop a clearly futile cell under Section 15.3. It may not change the running config.

### 15.3 Preregistered futility rule

No behavioral early stop before step1000.

After step1000, a cell may be stopped only if two consecutive strict-valid checkpoints satisfy all of:

- goal = 0/16;
- send-ready count <2/16;
- no improvement in hinge-at-crossing or early-crossing rate;
- stage4 occupancy is collapsing or terminal behavior is effectively degenerate.

Operational failures may be stopped immediately. A stopped cell remains part of the result and is not silently replaced. A follow-up uses a new config and run name.

### 15.4 No in-place retuning

The following are prohibited during a formal run:

- changing `theta_send`;
- changing I/E/A scales;
- changing the curriculum schedule;
- changing physics, gains, or limits;
- changing staged-reset ratios;
- editing selection gates.

Any follow-up is versioned as `base_v20_R1_*` and is judged separately.

---

## 16. Evaluation plan

### E0 | All-checkpoint canonical16

- 7 groups × 10 checkpoints = 70 evaluations;
- seed0;
- exact ordered 16-door topology;
- strict telemetry and full v20 metric set;
- mechanical per-group selection.

### E1 | Selected pooled48

For the selected checkpoint in every group:

- seeds0,1,2;
- 16 doors per seed;
- one pooled48 report;
- bucket breakdown by handle height, spring/hinge resistance, and mass;
- all hard gates evaluated.

All seven groups receive pooled48 evaluation, not only the anticipated winner. This preserves the factorial interpretation.

### E2 | Matched causal comparison

Run the paired comparisons in M48 on identical door instances and produce per-env deltas. This report answers factor questions; it does not replace the hard release gates.

### E3 | Cross-group release freeze

Apply the selection rule in Section 18. Freeze exactly one release candidate and its checkpoint SHA before any holdout64 or final render review.

### E4 | Post-selection holdout64

Evaluate the frozen release candidate on seeds3–6:

```text
4 seeds × 16 doors = 64 holdout episodes
```

The holdout is never used to choose another checkpoint. If it fails, the frozen candidate fails confirmation; do not search those seeds for a replacement.

### E5 | Matched render review

Render at least:

- G1 selected control;
- best institution-only or I+E candidate;
- G6 full-method candidate;
- G7 independent-seed replicate.

For each checkpoint use three matched doors:

1. low handle / light door / weak spring;
2. high handle / heavy door / strong spring;
3. median configuration.

Cameras:

- default;
- handle-side;
- handle-top.

Overlay or synchronize:

- stage;
- hinge angle/velocity;
- root x;
- send-ready latch;
- first-cross threshold;
- bilateral hold;
- arm/base tangent contribution;
- arc error;
- release state;
- terminal reason.

**Media QA**

- full decode;
- expected resolution/frame rate;
- no `.writing` remnants;
- exact checkpoint/Hydra/camera binding;
- contact sheets for each reviewed episode.

**Behavior review**

- no premature root crossing;
- arm visibly initiates and sustains the send;
- base begins following only after the send condition;
- no abrupt fling;
- no visible grasp loss or handle-end instability;
- no body/leg-door collision;
- controlled release and passage.

`arm_j1` sign is not a render gate.

### E6 | Final analysis

Produce JSON and Markdown containing:

- provenance and hashes;
- all 70 M22 rows;
- seven pooled48 reports;
- factor comparisons;
- holdout64 result;
- render QA and behavior verdict;
- per-group numeric/full judgement;
- release decision or explicit no-release result;
- a statement that the evaluated sample sizes are not statistical proof.

---

## 17. Acceptance gates

### 17.1 Hard common task and safety gates

| Metric | Canonical16 | Pooled48 | Holdout64 |
|---|---:|---:|---:|
| Goal | >=15/16 | >=46/48 | >=60/64 |
| Crossing while holding | >=15/16 | >=46/48 | >=60/64 |
| Upper-DOF overspeed | 0 | 0/48 | 0/64 |
| Pre-crossing bilateral | >=99% | >=99% | >=99% |
| Pre-crossing coasting | <2% | <2% | <2% |
| Pre-crossing over-force | <2% | <2% | <2% |
| Post-release body contact | report | <=2/48 | <=3/64 |
| Post-release body-force p95 | report | <80 N | <80 N |
| Opening slip p95 | <=3.0 cm if defined | <=3.0 cm | <=3.0 cm |
| Held hinge | report | p50 >=1.45, p95 >=1.50 rad | same |

### 17.2 Hard send-first gates

Let `theta_send` and `relief_limit` be frozen by P1.

| Metric | Gate |
|---|---|
| Goal episodes with pre-send crossing | exactly 0 |
| Overall send-before-cross rate | >=15/16 canonical; >=46/48 pooled; >=60/64 holdout |
| Hinge at first root crossing p50 | >= `theta_send` |
| Hinge at first root crossing p10 | >= `theta_send - 0.05 rad` |
| Pre-send forward root displacement p95 | <= `relief_limit + 0.02 m` |
| Pre-send root-plane margin | no goal may cross before the latch |
| Stage4 overtime | <=2/48 pooled and no concentration in one door bucket |

For fixed-root P1 mode, `relief_limit` is the small measured numerical/locomotion allowance frozen in the probe; it is not automatically 0.10 m.

### 17.3 Hard carry and naturalness gates

P0 freezes the G2 task-space baseline before training.

| Metric | Gate |
|---|---|
| Pre-send arm tangent share p50 | >= `max(0.60, G2_baseline + 0.15)` |
| Pre-send arm tangent share p10 | >=0.45 |
| TCP-handle position error p95 | <=3.0 cm |
| TCP-handle orientation error p95 | <= P0-frozen tolerance |
| Positive hinge velocity p95 | <=0.40 rad/s |
| Hinge acceleration/jerk p95 | <=1.25× G2 baseline |
| Arm action-rate/jerk p95 | <=1.25× G2 baseline |
| Median task time | <=1.20× G2 baseline |
| Render behavior | PASS |

The absolute arm-share floor is a preregistered behavior requirement. The `+0.15` term ensures the metric represents a material improvement over the actual G2 route.

### 17.4 A-factor claim gate

To claim that M47 adds value beyond I+E:

- both G6 and G7 must pass all hard gates;
- both must improve pre-send arm-share p50 by at least `0.10` over G4;
- neither may regress pooled goal by more than 2/48;
- neither may regress opening slip beyond 3 cm;
- both must maintain arc-error and smoothness gates;
- the direction of the paired effect must agree in G6 and G7.

If full-method replication fails, M47 is not promoted even if one seed looks strong.

---

## 18. Mechanical checkpoint and release selection

### 18.1 Within-group M22 order

Select one checkpoint per group lexicographically:

1. `STRICT_VALID` and exact provenance;
2. common task/safety gates;
3. send-first gates;
4. carry/arc gates;
5. smoothness gates;
6. lower task time;
7. earlier checkpoint only as a final tie-breaker.

Endpoint step2500 receives no preference.

If no checkpoint passes all hard canonical gates, retain the best strict-valid candidate for diagnosis but mark the group `NO_PROMOTABLE_CHECKPOINT`.

### 18.2 Across-group release order

Controls G1/G2 are not v20 release candidates because they do not contain the send institution. Eligible cells are G3–G7.

Prefer the **simplest replicated behaviorally sufficient mechanism**:

1. If G3 passes all hard gates and G4/G5/G6/G7 add no material replicated improvement, release G3.
2. Otherwise, if G4 passes and the A package is not replicated/material, release G4.
3. G5 is eligible if it passes all hard gates and is superior to the simpler cells under the same preregistered order.
4. Promote the full A claim only if both G6 and G7 satisfy Section 17.4; select the better of their M22 checkpoints using the same fixed order.
5. If no I-enabled group passes, declare base_v20 FAIL and keep G2 step2000 as the previous operational reference, not as a v20 release.

### 18.3 Full judgement

Each group receives:

- `numeric_gate_status`;
- `render_gate_status` where rendered;
- `full_judgement_status`;
- exact failed gate list;
- no inferred PASS from missing metrics.

---

## 19. Failure contingencies

### C1 — P1 shows fixed-root infeasibility but bounded relief works

Use the F1 relief bounds and state the claim as **arm-led send with minimal bounded base relief**, not arm-only opening.

### C2 — P1 fails even at 0.90 rad

Stop. Do not train a policy against an unverified target. Open a separate geometry/control investigation.

### C3 — I cells collapse in P2.2

Use the one common preregistered penalty-to-terminal curriculum, rerun the pilot, and freeze it for all I cells. Do not weaken one cell only.

### C4 — E alone solves send-before-crossing

This is a valid result. G2 tests whether the route was purely an economic artifact. A control without the hard institution still cannot become a v20 release unless it passes the same hard behavior gates and the project explicitly changes the release rule before seeing the result. Under this plan, release eligibility remains I-enabled.

### C5 — I solves the route and A adds nothing

Prefer G3 or G4. A null M47 result is scientifically useful and keeps the deployed/student behavior simpler.

### C6 — A improves arm share but worsens slip or smoothness

A fails promotion. A separately named follow-up may tune arc/A scales, but may not simultaneously change gripper physics.

### C7 — Full method is seed-sensitive

If G6 passes and G7 fails, no full-method claim. Prefer a simpler passing cell or run a separately approved additional replicate.

### C8 — Reporter/exporter defect appears after training

A targeted repair may rerun evaluation on the exact checkpoint only if policy execution semantics are unchanged. Preserve the original invalid artifact, record the repair reason, and keep reuse/repair provenance. Never rewrite a checkpoint.

### C9 — Evaluation queue falls behind

Training may continue, but no winner is declared until all 70 canonical rows are adjudicated. Do not skip early checkpoints to catch up.

### C10 — Real arm limits become tempting mid-round

Do not add them. Queue them for the next zero-shot/probe-gated round after v20 is closed.

---

## 20. Student-distillation compatibility

The v20 teacher keeps the existing 12D learned high-level action and the existing privileged teacher observation contract. `send_ready` is used for reward, termination, and evaluation only; it is not exposed as a deployment-time privileged actor input.

This is expected to make later DAgger easier, not harder, because the teacher route becomes less multimodal:

```text
send -> follow -> release -> pass
```

rather than crossing at variable early hinge angles and dragging the door with different base trajectories.

No student training is part of v20. After the teacher is frozen, the later distillation round must verify that the RGB+LSTM student can infer the send/follow phase. An auxiliary visual hinge-progress prediction head is a possible later tool; ground-truth hinge state must not be added directly to the deployed actor.

---

## 21. Required code, config, test, and artifact deliverables

### 21.1 Code and config

- `gr00t/rl/envs/door/door_open_a2_base.py`
- `gr00t/rl/config/env/door_open_a2_base.yaml`
- `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`
- `gr00t/rl/config/ablation/wbmanip/base_v20_G1_g2_continuation.yaml`
- `gr00t/rl/config/ablation/wbmanip/base_v20_G2_economics_only.yaml`
- `gr00t/rl/config/ablation/wbmanip/base_v20_G3_send_institution_only.yaml`
- `gr00t/rl/config/ablation/wbmanip/base_v20_G4_send_economics.yaml`
- `gr00t/rl/config/ablation/wbmanip/base_v20_G5_send_arm_tie.yaml`
- `gr00t/rl/config/ablation/wbmanip/base_v20_G6_full.yaml`
- `gr00t/rl/config/ablation/wbmanip/base_v20_G7_full_seed1.yaml`

### 21.2 Tests

- `gr00t/rl/tests/test_a2_v20_env_semantics.py`
- `gr00t/rl/tests/test_a2_v20_main_config.py`
- `gr00t/rl/tests/test_a2_v20_staged_reset_state.py`
- `gr00t/rl/tests/test_a2_v20_taskspace_carry.py`
- `gr00t/rl/tests/test_a2_v20_m22_adjudicator.py`
- `gr00t/rl/tests/test_a2_v20_endpoint_report.py`
- `gr00t/rl/tests/test_a2_v20_render_qa.py`
- `gr00t/rl/tests/test_a2_v20_final_analysis.py`

### 21.3 Human/report scripts

- `scriptsFORhuman/a2_piper_base_v20_optimization_plan_20260728.md`
- `scriptsFORhuman/v20/a2_piper_v20_arc_feasibility.py`
- `scriptsFORhuman/v20/a2_piper_v20_m22_queue.py`
- `scriptsFORhuman/v20/a2_piper_v20_m22_evidence.py`
- `scriptsFORhuman/v20/a2_piper_v20_m22_adjudicator.py`
- `scriptsFORhuman/v20/a2_piper_v20_endpoint_report.py`
- `scriptsFORhuman/v20/a2_piper_v20_paired_analysis.py`
- `scriptsFORhuman/v20/a2_piper_v20_render_queue.py`
- `scriptsFORhuman/v20/a2_piper_v20_render_qa.py`
- `scriptsFORhuman/v20/a2_piper_v20_final_analysis.py`

Where practical, parameterize and reuse v19 logic; do not mutate v19 evidence or schemas in place.

### 21.4 Canonical artifact layout

```text
logs_rl/a2_piper_full_stage_a2_base/base_v20/<run-dir>/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20/<family>/<run-dir>/
logs_rl/launchers/base_v20/<launcher-dir>/
logs_eval/base_v20/preflight/<result-folder>/
logs_eval/base_v20/G1_m22/ ... G7_m22/<result-folder>/
logs_eval/base_v20/m22_shared/<result-folder>/
logs_eval/base_v20/paired_analysis/<result-folder>/
logs_eval/base_v20/render/<result-folder>/
logs_eval/base_v20/final_analysis/<result-folder>/
```

One eval/result directory is an indivisible evidence unit containing Hydra config, logs, metrics, traces, diagnostics, reports, and renderings.

---

## 22. Execution checklist

### Pre-run

1. [ ] Record branch head and worktree state.
2. [ ] Verify G2 step2000 path, SHA, and saved config.
3. [ ] Reproduce the 70-checkpoint evidence baseline and metric boundaries.
4. [ ] Implement zero-default v20 telemetry and pass disabled-path parity.
5. [ ] Complete P1 pooled48 live-grasp arc probe; freeze `theta_send` and relief bounds.
6. [ ] Freeze M47 reward scales from explicit-unit decomposition.
7. [ ] Implement M45/M46/M47 and staged-reset state ownership.
8. [ ] Implement M48 strict exporter, queue, and reports.
9. [ ] Pass all static/Hydra/review lanes.
10. [ ] Pass P2.1 semantic admission.
11. [ ] Pass all seven 64×50 smokes.
12. [ ] Pass the 256×250 G4 learnability pilot.
13. [ ] Hash and freeze all seven formal configs.

### Formal training

14. [ ] Launch G1–G7 on physical GPUs0–6, one process and 4096 env each.
15. [ ] Reserve physical GPU7 for evaluation only.
16. [ ] Verify startup binding, env count, checkpoint, factors, W&B, and memory.
17. [ ] Evaluate every saved checkpoint on canonical16.
18. [ ] Produce mandatory midpoint reviews at 500/1000/1500/2000.
19. [ ] Apply only the preregistered futility rule; no in-place retuning.
20. [ ] Verify 2500/2500 natural exit and W&B `finished` for every completed group.

### Selection and evaluation

21. [ ] Complete all 70 strict M22 rows.
22. [ ] Mechanically select one checkpoint per group.
23. [ ] Run pooled48 for all seven selected checkpoints.
24. [ ] Produce matched factor comparisons.
25. [ ] Freeze one cross-group release candidate.
26. [ ] Run holdout64 without checkpoint reselection.
27. [ ] Render matched G1 / minimal-method / G6 / G7 cases with overlays.
28. [ ] Complete media QA and behavior review.
29. [ ] Produce final JSON/Markdown with per-group and winner judgement.
30. [ ] Update memory, long-term TODO, scriptsFORhuman index, and log-layout references.

---

## 23. One-sentence handoff

> base_v20 is a seven-cell, 7×4096-env teacher-PPO experiment that tests whether enforcing and correctly paying **arm-led send before base traversal**, with an optional task-space carry tie-breaker, can convert G2's successful but early-crossing door-drag route into a continuous, natural, stable handle-arc delivery policy without changing hardware capability or the future student interface.
