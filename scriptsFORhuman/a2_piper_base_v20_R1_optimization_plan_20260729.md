# A2+Piper base_v20_R1 Optimization and Execution Plan (EN)

# Policy-level send-first learning after closure of the deterministic P1 certifier

**Date:** 2026-07-29 (HKT)  
**Repository / branch:** `Jam-Stark/DoorDog`, `A2_Piper`  
**Plan ID:** `base_v20_R1_policy_behavior_v1`  
**Supersedes for future execution:** the active-execution portions of `scriptsFORhuman/a2_piper_base_v20_optimization_plan_20260728.md`  
**Does not overwrite:** the original base_v20 plan, P1 evidence, P1 source snapshots, or P1 adjudication  
**Legal physical GPUs:** `0–6` only; physical GPU7 is unavailable and forbidden  

---

## Decision block

```text
DECISION = REVISE_V20_BEHAVIOR_CLAIM
P1_STATUS = P1_PHYSICAL_BLOCKER
P1_PASS = false
ORIGINAL_DETERMINISTIC_FEASIBILITY_CLAIM = ABANDONED
POLICY_LEVEL_SEND_FIRST_TARGET = RETAINED
R1_FORMAL_TRAINING_READY_NOW = false
R1_G1_G7_MAY_LAUNCH_NOW = no
NEXT_APPROVED_RUNTIME = one base_v20_R1 G4 learnability pilot, only after all R1-P0/R1-P1 gates pass
NEXT_STOPPING_CONDITION = any consumed pilot attempt that fails one required gate closes R1 as R1_POLICY_LEARNABILITY_BLOCKER and forbids G1-G7
```

The original deterministic P1 result remains a real negative result. It is not reclassified, weakened, or replaced by this revision. The revision changes what must be demonstrated **before policy training**: the failed hand-designed DLS/root-relief certifier is no longer treated as a certificate for the learned 12D high-level policy class. The learned policy must still satisfy the original `0.90 rad` send-first behavior target at release time.

---

## 0. Executive summary

### 0.1 Why R1 exists

base_v19 already demonstrates that the learned whole-body policy can:

- reach and grasp the handle;
- unlatch the door;
- retain a stable bilateral grasp;
- open the hinge to the `1.4–1.6 rad` region;
- cross the doorway while holding;
- release around `1.60 rad` without pooled overspeed or post-release body contact in the selected G2 endpoint.

The remaining failure is the **ordering and allocation of motion**. The G2 policy normally crosses the door plane near `0.72 rad` and then lets the moving base contribute most of the remaining door motion. R1 asks whether policy-level reward semantics and staged-reset exploration can move already-achieved opening progress earlier in the episode:

```text
base_v19 route:
    grasp -> open partly -> cross early -> base drags door further -> release

base_v20_R1 target:
    grasp -> learned whole-body send to >=0.90 rad -> cross -> continue tracking -> release
```

The deterministic P1 controller failed at this task, but it used a different controller and state machine from the learned policy. P1 therefore remains a blocker for claims about the deterministic certifier, not proof that the learned policy class cannot discover a valid whole-body strategy.

### 0.2 Revised scientific claim

> **A learned A2+Piper whole-body policy can shift door-opening progress to the pre-crossing phase, such that the hinge reaches at least `0.90 rad` before root-plane crossing, while useful handle-tangent motion is arm-majority, root reconfiguration remains bounded, grasp/arc tracking remains stable, and task success and safety are preserved.**

This claim permits learned base translation, yaw, pitch, and roll. It does **not** claim arm-only opening or the original F1 bound of `0.10 m / 0.15 rad`. The release behavior must remain arm-led and bounded, but the learned policy may use a larger, preregistered whole-body reconfiguration envelope.

### 0.3 What is abandoned

The following statement is permanently abandoned for base_v20_R1:

> The current deterministic DLS/root-relief interface has certified `theta_send >= 0.90 rad` under F0 or F1.

It has not. P1 is closed as `P1_PHYSICAL_BLOCKER`.

### 0.4 What is retained

The following are retained:

- `theta_send = 0.90 rad` as a **post-training policy release gate**;
- no root-plane crossing before a grasp-qualified send latch;
- G2 step2000 as the immutable warm start and B0 reference;
- the E reward-auction correction;
- task-space arm/base decomposition and handle-arc telemetry;
- staged reset;
- seven controlled ablation cells;
- strict canonical16, pooled48, holdout64, and render adjudication;
- zero tolerance for upper-DOF overspeed in formal endpoint evaluation.

### 0.5 One sentence execution rule

```text
Do not launch G1-G7 until one and only one G4 policy learnability pilot passes every frozen gate, all seven 64x50 smokes pass, and a hash-bound formal admission bundle is generated.
```

---

## 1. Immutable evidence boundary

### 1.1 Closed P1 evidence

The following evidence is immutable:

```text
P1 code candidate commit:
365667110b2e64b335dcf3517361245331db604e

P1 closure/docs commit:
282ab4ad118b734535b61440397bfb9e67b10fe6

resolved Hydra config SHA256:
2823acc622a977526872e477e7f6a65605e57df2fa969545922c58cb36012ba9

G2 step2000 checkpoint SHA256:
b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d

P1 adjudication JSON SHA256:
fc8c0fd83c3cea88fa4c808ba96cea48e7164dd11cac76a64b6f082be29a640b

P1 runtime summary SHA256:
70e46893475e7e16d61161925f1eff7e9809d797f30e0b2499c3f0717513d39e
```

The one authorized P1 smoke produced:

```text
mode = F1
theta = 0.90 rad
seed = 0
envs = 4
canonical capture = 4/4
ARC_PROBE_REACHED = 0/4
outcomes = 2 ROOT_BOUND + 2 OVERSPEED
max hinge ~= 0.014 / 0.036 / 0.031 / 0.006 rad
transaction audit = PASS on every sample
root-plane crossing = 0/4
runtime exception / traceback / non-finite = none
```

Correct interpretation:

```text
The current deterministic geometry/control interface failed P1.
Pure geometric impossibility was not isolated or proved.
```

### 1.2 Prohibited reinterpretations

R1 must never state or imply:

- P1 passed;
- canonical capture equals arc feasibility;
- transaction-audit PASS equals physical PASS;
- invalid hinge motion proves feasibility;
- P1 proved that `0.90 rad` is geometrically impossible;
- R1 is a retry of P1;
- R1 may change P1 gains, lead, timeout, DLS lambda, root bounds, or probe thresholds.

### 1.3 Why policy training is a distinct hypothesis

The high-level teacher policy outputs 12 learned actions: five base commands, six Piper arm increments, and one gripper primitive. A frozen A2_Base policy converts the five base commands into 12 low-level leg actions. The learned route can exploit temporal coordination, body pitch/roll, joint redundancy, compliant contact, and staged-reset occupancy. The deterministic P1 oracle instead imposed one prescribed DLS arc-following and relief mechanism.

The P1 failure therefore closes the deterministic-controller hypothesis. R1 tests the learned-policy hypothesis exactly once at pilot scale before spending the seven-GPU formal budget.

---

## 2. Evidence vocabulary

These labels are exact and non-interchangeable.

- **STATIC PASS:** CPU/unit/source/Hydra/hash checks passed. It says nothing about IsaacSim behavior.
- **RUNTIME PASS:** the exact bounded runtime completed with valid artifacts and satisfied its runtime gate. It says nothing beyond that topology.
- **POLICY LEARNABILITY PASS:** the one-shot R1 pilot moved the behavior by the preregistered amount while preserving minimum task/safety signals.
- **POLICY PASS:** a selected formal checkpoint passed canonical, pooled, holdout, and render gates.
- **STRICT_VALID:** all required telemetry, topology, terminal consistency, and provenance fields are complete.
- **STRICT_INVALID:** evidence is malformed, incomplete, non-finite, topology-inconsistent, or execution-invalid. It remains in the result table and is ineligible.
- **INCONCLUSIVE_INFRA:** execution was consumed but external infrastructure prevented scientific adjudication. It is not PASS and does not automatically authorize a rerun.
- **N/A:** an explicitly typed undefined metric with reason and denominator. It is neither zero nor failure by itself.
- **Canonical16:** seed0, 16 matched deterministic doors.
- **Pooled48:** seeds0–2, 16 matched doors per seed.
- **Holdout64:** seeds3–6, 16 doors per seed, used only after a release candidate is frozen.

---

## 3. Immutable warm start and B0 reference

### 3.1 Warm-start checkpoint

```text
logs_rl/a2_piper_full_stage_a2_base/base_v19/
base_v19_G2_norm_control-20260727_012027/
model_step_002000.pt
```

```text
SHA256 = b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d
checkpoint_load_mode = policy_only
auto_load_latest = false
```

No `last.pt`, alias, copied checkpoint, or different v19 endpoint is legal.

### 3.2 Frozen B0 task/safety/crossing values

The following values are frozen from the exact G2 step2000 pooled48 evidence before R1 code or training outcomes are observed.

| Metric | B0 value |
|---|---:|
| Episodes | 48 (`seeds0–2`, 16 each) |
| Goal | 48/48 |
| Crossing while holding | 48/48 |
| Hinge at first root crossing min | 0.5750486 rad |
| Hinge at first root crossing p10 | **0.6346504 rad** |
| Hinge at first root crossing p50 | **0.7189995 rad** |
| Hinge at first root crossing p95 | **0.8444906 rad** |
| Hinge at first root crossing max | 0.8773267 rad |
| Crossings at or above 0.90 rad | 0/48 |
| Crossings at or above 0.85 rad | 3/48 |
| Held hinge p50 | **1.4336079 rad** |
| Held hinge p95 | **1.5430807 rad** |
| Opening slip p50 | 2.1934633 cm |
| Opening slip p95 | **2.9084466 cm** |
| Release hinge p50 | 1.6054894 rad |
| Release hinge p95 | 1.6115434 rad |
| Pre-crossing bilateral rate | 0.9966701 |
| Pre-crossing coasting rate | 0.0028706 |
| Pre-crossing over-force rate | 0.0004593 |
| Pre-crossing hinge velocity p50 | 0.1987069 rad/s |
| Pre-crossing hinge velocity p95 | **0.3246622 rad/s** |
| Pre-crossing hinge velocity max | 0.4179487 rad/s |
| Upper-DOF overspeed termination | 0/48 |
| Post-release body contact | 0/48 |
| Post-release body-force p95 | 0 N |
| Root x at release p50 | 0.5709243 m |
| Root x at release p95 | 0.7298257 m |
| Task time p50 | **12.51 s** |
| Task time p95 | 13.944 s |

Frozen companion artifacts:

```text
a2_piper_base_v20_R1_B0_reference_20260729.json
SHA256 = 98654a976be8b6593e796d89291b4dc6ebdf530d078c625db7130d7a1622c826

a2_piper_base_v20_R1_B0_reference_20260729.csv
SHA256 = 209b33a1fa9d79d60f715518cc2798f96b13d71aea8fb2aac0f520a516f4585a
```

### 3.3 Frozen task-space diagnostic prior

The historical 2-environment G2 render trace is not a pooled baseline. It is nevertheless frozen as a diagnostic prior and may not be rewritten after R1 outcomes.

| Metric | Frozen diagnostic value |
|---|---:|
| Combined step arm tangent share p10 | 0.0000000 |
| Combined step arm tangent share p50 | **0.0893308** |
| Combined step arm tangent share p95 | 1.0000000 |
| Median of per-episode arm-share p50 | 0.0677066 |
| Arc position error p50 | 0.0342777 m |
| Arc position error p95 | 0.0393809 m |
| Arc orientation error p50 | 0.5363777 rad |
| Arc orientation error p95 | 0.7940030 rad |
| Worst episode hinge acceleration p95 | 0.7797296 rad/s² |
| Worst episode hinge jerk p95 | 21.7545256 rad/s³ |
| Worst episode arm raw-action rate p95 | 1.6984240 per control step |
| Worst episode arm raw-action jerk p95 | 2.8311783 per control step² |

The absolute R1 gates are fixed below and dominate this small diagnostic sample. R1-P1 must additionally regenerate task-space B0 on pooled48 using the final v20 telemetry implementation, but that regenerated number may not weaken any gate in this document.

### 3.4 B0 source binding

Authoritative source file digests are recorded in the companion JSON. In particular:

```text
seed0 per-env records SHA256 = 56c152828cd2e57f43e8493097fb062ab1d8a8aef96dd37c0abd8ddf61159f70
seed1 per-env records SHA256 = 388d5e4e4d019427e6b432b3f61c8a2772072f6b65569a89ee4c64373e12423b
seed2 per-env records SHA256 = 10dd616a8b7a3fe723897f92033ca724ff98c24cde8d24387294f06bd805c6c9
endpoint report SHA256 = 9c32a9d208f91982cc1d18d4de15fc326f7d26d18ffe98768188974263ebd60b
bucket report SHA256 = 4c84ca1a6e283d91831baa4380b3e3b580f9707222a83db51ce89da722009d7c
2-env trace SHA256 = 99fba6d134e9f7cb6d7f70d629107e17b67acb47804bb31913abec06563f29fc
```

---

## 4. Physical contract from the actual A2+Piper URDF

### 4.1 URDF identity

The simulation robot is bound to:

```text
gr00t/rl/data/robots/A2_Piper/a2_piper.urdf
Git blob SHA = 95c7698866962fa6e1b971b9ee534452775d8698
```

R1 preflight must hash the user-supplied URDF and the runtime-resolved asset. Both must decode to the same XML content as the repository blob. A mismatch is a hard preflight failure.

### 4.2 A2 body envelope

Official A2 product data reports an approximate standing envelope of:

```text
length = 0.820 m
width  = 0.440 m
height = 0.570 m
mass with batteries ~= 42 kg
```

The simulation URDF main trunk collision box is:

```text
0.24 x 0.28 x 0.17 m
trunk inertial mass = 19.651 kg
```

The policy-level pre-send reconfiguration gates are therefore expressed relative to the full robot root, not only the trunk collision box.

### 4.3 Piper mount and mass

The Piper base is fixed to the A2 trunk at:

```text
trunk -> arm_body0 translation = [0.145, 0.0, 0.154] m
arm_body0 -> arm_j1 axis translation = [0.0, 0.0, 0.123] m
```

Thus the first arm axis is approximately `0.145 m` forward and `0.277 m` above the trunk origin before body pitch/roll is considered.

Approximate mounted Piper assembly mass from the URDF links is:

```text
arm base + six links + gripper base + two fingers ~= 4.67 kg
```

### 4.4 Arm kinematic and limit contract

| Joint | Position limit (rad) | URDF velocity limit (rad/s) | URDF effort |
|---|---:|---:|---:|
| arm_j1 | [-2.618, 2.618] | 5 | 100 |
| arm_j2 | [0, 3.14] | 5 | 100 |
| arm_j3 | [-2.967, 0] | 5 | 100 |
| arm_j4 | [-1.745, 1.745] | 5 | 100 |
| arm_j5 | [-1.22, 1.22] | 5 | 100 |
| arm_j6 | [-2.0944, 2.0944] | **3** | 100 |
| arm_j7 | [0, 0.035] m | 1 m/s | 10 |
| arm_j8 | [-0.035, 0] m | 1 m/s | 10 |

The distal geometric offsets sum to roughly `0.764 m` (`0.28503 + 0.25171 + 0.091 + 0.1358`), but this is not a workspace certificate. Joint axes, orientation constraints, collision meshes, grasp offset, and contact forces reduce usable reach.

The formal training configs retain the established simulation regime:

```text
arm_j1..j6 configured effort class = 100
finger effort override = 45 / 45
finger Kp = 1300
finger Kd = 32
F2 arm overspeed soft margin = enabled, width 0.5
hard upper-DOF overspeed floor = 3.0 rad/s
```

Because `arm_j6` has a `3 rad/s` URDF limit, formal endpoint evaluation keeps upper-DOF overspeed at exactly zero.

### 4.5 Physical rationale for the R1 root envelope

R1 does not reuse the failed F1 `0.10 m / 0.15 rad` certifier bound. The learned policy receives this preregistered envelope from the first grasp-qualified opening reference until `send_ready`:

```text
forward root displacement p95 <= 0.20 m
lateral root displacement p95 <= 0.15 m
planar translation norm p95 <= 0.25 m
yaw change p95 <= 0.30 rad (~17.2 deg)
root-plane crossing before send = forbidden
```

The `0.20–0.25 m` envelope is materially smaller than the A2 body length and close to half of its `0.44 m` standing width. It allows a learned stance correction while preventing the historical `~0.6 m` advance-to-cross route from being called arm-led. Pitch and roll retain their existing command limits and are reported, not newly clipped.

### 4.6 Grasp-scale rationale for arc error

Each finger has `35 mm` travel. The formal TCP-handle position-error gate is `30 mm`, smaller than one finger travel and equal to the original intended arc-tracking tolerance. This is strict enough to reject handle-end drift while remaining tied to the simulated gripper scale.

---

## 5. Scope boundaries

### 5.1 In scope

- right-hinge, out-opening/push lever doors in the existing task regime;
- existing door mass, height, hinge, and latch randomization;
- G2 step2000 warm start;
- teacher PPO only;
- current superhuman simulation arm effort regime;
- M39 gripper material/gain package;
- F2 arm overspeed soft margin;
- existing 12D high-level action and 133D privileged teacher observation;
- staged reset;
- R1 S/E/A factors;
- task-space telemetry and strict evaluation.

### 5.2 Out of scope

- another P1 DLS/root-relief revision;
- realistic Piper arm effort-limit round;
- force-feasibility-aware base assistance;
- left/right mirror;
- pull/in-opening doors;
- camera changes;
- student DAgger or GRPO;
- action/observation dimension changes;
- gripper physics changes;
- hidden action override during training or evaluation;
- any use of GPU7.

### 5.3 No geometry claim

R1 may conclude that policy learning did or did not produce the target behavior. It may not conclude pure geometric reachability or impossibility from policy trajectories alone.

---

## 6. R1 factor definitions

R1 replaces the original factor name `I` with `S`.

### S — Send curriculum

A common, batch-indexed soft-to-hard curriculum:

```text
batches 0–499:
    pre-send crossing emits one graded one-shot penalty;
    crossing is not terminal solely because of S.

batches 500–2499:
    pre-send crossing is an exact terminal reason;
    no graded penalty is emitted for that event.
```

The schedule is identical in G3–G7 and cannot be edited in place.

### E — Corrected traversal economics

- stage4 target-root income is zero before `send_ready`;
- it ramps from `0` to the historical `0.5` stage4 scale over `0.20 rad` after send;
- root crossing alone cannot activate the corridor latch;
- wide-open normalization is `1.60 rad` with scale `4.2666667`, preserving G2's local slope.

### A — Task-space arm/arc tie-breaker

- reward useful arm-relative TCP motion along the positive handle tangent;
- reward handle-arc tracking under valid hold and positive hinge progress;
- zero reward for stationary/closing door, invalid grasp, inactive tangent motion, or post-release state;
- scales fixed at:

```text
a2_v20_arm_tangent_carry = 3.5
a2_v20_handle_arc_tracking = 0.85
```

At 50 Hz, even a fully saturated combined A reward over 200 steps is approximately `17.4` episode-sum units, around `6.7%` of B0 positive income. The actual gated income must remain below the smoke and formal caps below.

---

## 7. M45-R1 — Send curriculum implementation (factor S)

### 7.1 Frozen send latch

```text
theta_send = 0.90 rad
send_hinge_tolerance = 0.05 rad
root_x_margin = 0.03 m
```

The latch remains monotonic:

```text
send_ready[t+1] = send_ready[t] OR (
    valid_bilateral_hold_streak[t]
    AND hinge_position[t] >= 0.90
)
```

`send_ready` is not exposed to the deployed actor observation.

### 7.2 Graded soft-phase event

Define the one-shot event at first physical crossing before send:

```text
pre_send_crossing_event =
    opening_phase
    AND NOT send_ready
    AND root_x_rel > 0.03
    AND NOT pre_send_crossing_seen
```

Define normalized shortfall:

```text
shortfall = clamp((0.90 - hinge_position) / 0.90, 0, 1)
```

Raw reward component:

```text
raw_crossing_component =
    pre_send_crossing_event
    * (1.0 + 1.0 * shortfall)
    / control_dt
```

Reward-manager scale:

```text
penalty_a2_v20_pre_send_crossing = -15.0
```

Because the raw event divides by `control_dt`, the one-shot episode-sum penalty is exactly in the range:

```text
-15.0 to -30.0
```

At the frozen B0 median crossing angle (`0.7189995 rad`), the penalty is about `-18.0`, roughly 10% of the B0 mean total reward rather than an accidental `dt`-attenuated token penalty.

### 7.3 Exact batch schedule

Root config:

```yaml
schedule_dict:
  env@config@a2_v20_pre_send_crossing_mode:
    type: segment
    val_type: str
    seg_steps: [0, 500]
    seg_vals: [penalty, terminal]
    trigger_func: env@on_a2_v20_R1_crossing_mode_transition
```

The generic trainer already updates scheduled parameters at the beginning of every training batch. `train_agent_trl.py` must pass:

```python
schedule_dict=config.get("schedule_dict", None)
```

to the trainer constructor.

`on_a2_v20_R1_crossing_mode_transition()` is called at both segment boundaries. It must:

- at step0 / mode `penalty`: initialize and record the soft phase;
- at step500 / mode `terminal`: audit staged-reset snapshot compatibility, set a monotonic hard-phase flag, and write an exact transition marker;
- reject duplicate or regressing transitions;
- reject any transition at a batch other than 0 or 500;
- never alter policy actions, gains, geometry, or limits.

### 7.4 Staged-reset snapshot guard

A soft-phase snapshot that already violated the future hard institution must not poison hard-phase training.

Add a high-level hook in `StagedTaskBase`:

```python
def _filter_staged_reset_snapshot_mask(self, advance_mask):
    return advance_mask
```

`_post_compute_observations_callback()` must call this hook before storing snapshots.

`DoorPregrasp` overrides it when `a2_v20_R1_snapshot_guard_enabled=true`:

- never store a newly entered stage snapshot if `pre_send_crossing_seen=true` and `send_ready=false`;
- never store a stage5 snapshot with `send_ready=false`;
- allow stage3/stage4 entry snapshots only while the root remains on the approach side or send is already valid;
- count rejected snapshots in telemetry;
- do not silently mutate an existing snapshot.

At batch500, the transition callback audits all available stage4/stage5 R1 buffers. Any incompatible stored snapshot is a runtime error. The callback does not “clean” evidence after the fact.

### 7.5 R1 S config keys

Shared disabled defaults:

```yaml
env:
  config:
    a2_v20_R1_plan_id: disabled
    a2_v20_R1_send_curriculum_enabled: false
    a2_v20_R1_soft_phase_end_batch: 500
    a2_v20_R1_snapshot_guard_enabled: false
    a2_v20_R1_crossing_base_component: 1.0
    a2_v20_R1_crossing_shortfall_gain: 1.0
```

S-enabled config:

```yaml
env:
  config:
    a2_v20_R1_plan_id: base_v20_R1_policy_behavior_v1
    a2_v20_R1_send_curriculum_enabled: true
    a2_v20_R1_soft_phase_end_batch: 500
    a2_v20_R1_snapshot_guard_enabled: true
    a2_v20_send_latch_enabled: true
    a2_v20_send_hinge_threshold: 0.90
    a2_v20_send_hinge_tolerance: 0.05
    a2_v20_pre_send_root_x_margin: 0.03
    a2_v20_pre_send_crossing_mode: penalty
    a2_v20_pre_send_crossing_penalty_component: 1.0
    a2_v20_R1_crossing_shortfall_gain: 1.0

rewards:
  reward_scales:
    penalty_a2_v20_pre_send_crossing: -15.0
```

### 7.6 M45-R1 acceptance

**STATIC PASS** requires:

- exact schedule boundaries 0/500;
- exact string modes `penalty/terminal`;
- event one-shot truth table;
- episode-sum invariance under control `dt`;
- shortfall values at `0.0 / 0.45 / 0.90 / >0.90 rad`;
- no penalty in disabled or terminal mode;
- terminal only in terminal mode;
- no terminal after send;
- no send latch from hinge progress without valid hold;
- snapshot guard and stage5 tests;
- transition callback step0/step500 and duplicate/regression rejection;
- staged-reset round-trip for all R1 state.

**RUNTIME SEMANTIC PASS** is specified in R1-P1.

---

## 8. M46-R1 — Correct traversal economics (factor E)

### 8.1 Stage4 target-root gate

```text
send_progress = clamp((hinge_position - 0.90) / 0.20, 0, 1)
stage4_target_root_scale = 0.5 * send_progress, only after send_ready
```

Before send, stage4 traversal income is exactly zero. Stage5 remains historically full scale.

### 8.2 Corridor latch

```yaml
a2_corridor_latch_mode: send_ready_v20
```

Under this mode:

- root crossing cannot activate the corridor;
- `send_ready` activates it;
- existing hold-continuity, body-contact, and root-range conditions remain.

### 8.3 Wide-open wage

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

### 8.4 M46-R1 acceptance

- exact zero pre-send target-root scale;
- continuous monotonic post-send ramp;
- exact 0.5 saturation;
- stage5 unchanged;
- root crossing cannot latch the v20 corridor;
- send_ready can latch it once;
- legacy branch exact;
- explicit reward units in all reports.

---

## 9. M47-R1 — Task-space arm-majority and arc tracking (factor A)

### 9.1 Arm/base decomposition

At each valid control step:

```text
v_base_at_tcp = v_base + omega_base x (p_tcp - p_base)
v_arm         = v_tcp - v_base_at_tcp

u_base = relu(dot(v_base_at_tcp, tangent_open))
u_arm  = relu(dot(v_arm, tangent_open))

arm_tangent_share = u_arm / (u_arm + u_base)
```

The sample is inactive when total positive tangent speed is at or below `0.005 m/s`.

### 9.2 Reference and arc quality

Capture `T_HANDLE_TCP` at the first grasp-qualified opening reference. During valid held opening, export:

- position error;
- orientation error;
- along-handle slip;
- orthogonal arc residual;
- arm/base positive tangent components;
- activity mask;
- positive hinge velocity;
- reference-valid flag.

### 9.3 Rewards

```text
r_arm_carry =
    valid_hold
    * positive_hinge_velocity_clipped
    * arm_tangent_share
    * arc_tracking_quality

r_arc =
    valid_hold
    * positive_hinge_motion
    * arc_tracking_quality
```

Scales:

```yaml
a2_v20_arm_tangent_carry: 3.5
a2_v20_handle_arc_tracking: 0.85
```

### 9.4 A-factor income cap

For every smoke, canonical checkpoint, pooled endpoint, and holdout:

```text
A package positive episode income / all positive episode income <= 0.10
```

If the ratio exceeds 10%, the A cell is non-promotable even if behavior improves. The scale is not retuned inside R1.

### 9.5 M47-R1 acceptance

Pure tests:

- pure base motion -> share 0;
- pure arm motion -> share 1;
- equal positive contributions -> 0.5;
- wrong direction -> inactive;
- zero motion -> inactive and finite;
- rigid transform invariance;
- rotational base contribution included;
- tangent sign under mirrored synthetic geometry;
- malformed/non-finite inputs fail fast.

Runtime tests:

- no A income before valid reference;
- no A income after release;
- no A income for closing/stationary door;
- online values match offline trace recomputation;
- A income ratio cap;
- disabled A terms remain bit-exact zero.

---

## 10. M48-R1 — Strict telemetry and adjudication

### 10.1 Required per-episode fields

**Provenance**

- plan ID and plan SHA;
- git commit;
- URDF blob/content hash;
- checkpoint path/SHA;
- source config SHA;
- resolved Hydra SHA;
- seed/topology;
- curriculum phase and transition batch.

**Task/safety**

- goal, complete, max/final stage;
- crossing while holding;
- bilateral, coasting, over-force;
- upper-DOF overspeed;
- body/arm panel contact;
- release and post-release groups;
- task time.

**Send behavior**

- send_ready and first-send step;
- first root-crossing step;
- hinge/root x at crossing;
- pre-send crossing event/seen;
- soft penalty raw/scaled episode component;
- terminal phase reason;
- root reference validity;
- forward/lateral/planar/yaw maximum pre-send reconfiguration;
- rejected staged-reset snapshot count;
- hard-phase transition audit result.

**Task space**

- active sample count;
- arm tangent share p10/p50/p95;
- arm/base tangent integrals;
- arc position/orientation p50/p95;
- along-handle slip;
- orthogonal residual;
- A income and positive-income ratio.

**Smoothness**

- positive hinge velocity p95;
- hinge acceleration p95;
- hinge jerk p95;
- arm raw-action rate p95;
- arm raw-action jerk p95.

### 10.2 Exact root displacement computation

Fix the current component-wise SE(2) subtraction:

```text
delta_xy = current_xy - opening_reference_xy
forward  = projection in door-normal/forward convention
lateral  = orthogonal projection
planar   = norm(delta_xy)
yaw      = abs(wrap_to_pi(current_yaw - reference_yaw))
```

No unwrapped yaw difference is allowed.

### 10.3 Strict schema rules

- no missing metric becomes zero;
- N/A requires reason and denominator;
- goal requires crossing evidence;
- release remains independent all-null/all-valid group;
- held phase requires held/slip/task-space groups;
- trace steps ordered, unique, contiguous, and terminal-consistent;
- schedule phase must match global batch;
- enabled/disabled factor fields must match config;
- exact artifact/checkpoint/config binding;
- no row from original P1 may be mixed into R1 policy evidence.

---

## 11. M49-R1 — Formal seven-cell matrix

### 11.1 Matrix

| Group | GPU | Train seed | S | E | A | Config | Question |
|---|---:|---:|:---:|:---:|:---:|---|---|
| G1 | 0 | 0 | — | — | — | `base_v20_R1_G1_g2_continuation.yaml` | Does ordinary continuation move the route? |
| G2 | 1 | 0 | — | ✓ | — | `base_v20_R1_G2_economics_only.yaml` | Are economics alone sufficient? |
| G3 | 2 | 0 | ✓ | — | — | `base_v20_R1_G3_send_curriculum_only.yaml` | Is the curriculum alone sufficient? |
| G4 | 3 | 0 | ✓ | ✓ | — | `base_v20_R1_G4_send_curriculum_economics.yaml` | Minimal intended R1 mechanism. |
| G5 | 4 | 0 | ✓ | — | ✓ | `base_v20_R1_G5_send_curriculum_arm_tie.yaml` | Does A help under S without E? |
| G6 | 5 | 0 | ✓ | ✓ | ✓ | `base_v20_R1_G6_full.yaml` | Full R1, seed0. |
| G7 | 6 | 1 | ✓ | ✓ | ✓ | `base_v20_R1_G7_full_seed1.yaml` | Independent full-method replicate. |

GPU7 is not assigned to any task.

### 11.2 Shared formal settings

```yaml
checkpoint: <exact G2 step2000 path>
checkpoint_load_mode: policy_only
auto_load_latest: false
num_envs: 4096
headless: true
algo.trl.num_total_batches: 2500
callbacks.model_save.save_frequency: 250
```

Keep unchanged:

```yaml
env.config.enable_staged_reset: true
env.config.staged_reset_ratios: [0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
env.config.staged_reset_max_samples_per_stage: 200
env.config.a2_stage4_release_hinge_threshold: 1.60
env.config.a2_stage4_to5_door_hinge_threshold: 1.25
env.config.a2_arm_dof_overspeed_soft_margin_enabled: true
env.config.a2_arm_dof_overspeed_soft_margin_width: 0.5
```

### 11.3 Release eligibility after claim revision

All cells, including G1 and G2, are eligible **only if they pass every final behavior gate**. This is a deliberate change from the original institution-centric plan.

- If G1 passes, the conclusion is that continued PPO alone was sufficient.
- If G2 passes, the conclusion is that correcting economics was sufficient.
- If G3 passes, the curriculum alone was sufficient.
- If G4 passes, S+E is the minimal revised method.
- G5 tests A without E.
- A-factor value may be claimed only with replicated G6/G7 evidence.

No cell can be promoted merely because it completes the task.

---

## 12. Exact code, config, and test changes

### 12.1 New plan and namespace files

```text
scriptsFORhuman/a2_piper_base_v20_R1_optimization_plan_20260729.md
scriptsFORhuman/v20_R1/
```

The original `scriptsFORhuman/v20/` P1 files remain immutable.

### 12.2 Environment code

**`gr00t/rl/envs/door/door_open_a2_base.py`**

Required changes:

1. Add the R1 graded crossing helper and `dt`-invariant episode component.
2. Add new R1 config getters and fail-fast validation.
3. Add exact curriculum-phase and transition telemetry.
4. Add `on_a2_v20_R1_crossing_mode_transition()`.
5. Add staged-reset snapshot eligibility override.
6. Add hard-phase snapshot audit.
7. Correct yaw displacement with `wrap_to_pi` and add forward/lateral/planar metrics.
8. Preserve all v20 selectors disabled by default.
9. Do not change P1 oracle behavior or artifacts.
10. Do not alter policy actions.

**`gr00t/rl/envs/base_task/staged_task_base.py`**

Required change:

- add a default no-op snapshot-mask hook and call it before snapshot storage;
- validate returned mask shape/dtype/device;
- leave all non-R1 environments byte-equivalent.

### 12.3 Trainer/schedule code

**`gr00t/rl/train_agent_trl.py`**

Pass the root schedule dictionary into the trainer:

```python
schedule_dict=config.get("schedule_dict", None)
```

**`gr00t/rl/trl/utils/scheduler.py`**

No behavior change is required if existing segment/string/trigger behavior passes R1 tests. Add only fail-fast schema tests if needed. Do not create an R1-specific scheduler.

### 12.4 Shared configs

**`gr00t/rl/config/env/door_open_a2_base.yaml`**

Add zero/false R1 defaults listed in Section 7.5.

**`gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml`**

Keep all R1 reward terms zero in the shared registry.

### 12.5 New source configs

```text
gr00t/rl/config/ablation/wbmanip/base_v20_R1_G1_g2_continuation.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R1_G2_economics_only.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R1_G3_send_curriculum_only.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R1_G4_send_curriculum_economics.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R1_G5_send_curriculum_arm_tie.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R1_G6_full.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R1_G7_full_seed1.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R1_P2_G4_learnability_pilot.yaml
```

Original `base_v20_G*.yaml` files are not modified and are not launchable under R1.

### 12.6 New/updated tests

```text
gr00t/rl/tests/test_a2_v20_R1_curriculum.py
gr00t/rl/tests/test_a2_v20_R1_staged_reset_guard.py
gr00t/rl/tests/test_a2_v20_R1_main_config.py
gr00t/rl/tests/test_a2_v20_R1_pilot_adjudicator.py
gr00t/rl/tests/test_a2_v20_R1_launcher.py
gr00t/rl/tests/test_a2_v20_R1_m22.py
```

Update existing v20 telemetry tests only where schemas are versioned. Do not rewrite v19 or P1 schemas.

### 12.7 Human scripts

```text
scriptsFORhuman/v20_R1/a2_piper_v20_R1_preflight.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_baseline.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_semantic_admission.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_pilot_launcher.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_pilot_adjudicator.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_smoke_launcher.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_promote_configs.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_launcher.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_m22_queue.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_endpoint_report.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_paired_analysis.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_render_queue.py
scriptsFORhuman/v20_R1/a2_piper_v20_R1_final_analysis.py
```

Where safe, parameterize v20/v19 logic. Never mutate old evidence in place.

---

## 13. Independent artifact namespace

R1 artifacts must use only:

```text
logs_eval/base_v20_R1/preflight/
logs_eval/base_v20_R1/baseline/
logs_eval/base_v20_R1/semantic/
logs_eval/base_v20_R1/pilot/
logs_eval/base_v20_R1/smoke/
logs_eval/base_v20_R1/m22/G1/ ... G7/
logs_eval/base_v20_R1/pooled/
logs_eval/base_v20_R1/paired_analysis/
logs_eval/base_v20_R1/holdout/
logs_eval/base_v20_R1/render/
logs_eval/base_v20_R1/final_analysis/

logs_rl/a2_piper_full_stage_a2_base/base_v20_R1/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R1/
logs_rl/launchers/base_v20_R1/
```

No R1 process may write under:

```text
logs_eval/base_v20/
logs_rl/.../base_v20/
scriptsFORhuman/v20/
```

One result directory is an indivisible evidence unit. No overwrite, move-after-run, or artifact merging is allowed.

---

## 14. Hash-freeze and configuration promotion

### 14.1 Pre-pilot scientific manifest

Before the pilot, write:

```text
logs_eval/base_v20_R1/preflight/<timestamp>/
  R1_SCIENTIFIC_MANIFEST.json
  R1_SCIENTIFIC_MANIFEST.md
  resolved/
```

It must contain exact SHA-256 values for:

- this plan;
- git commit and dirty-worktree state;
- runtime URDF and Git blob identity;
- G2 checkpoint and adjacent config;
- B0 JSON/CSV and all B0 source files;
- changed source files;
- pilot source config and resolved Hydra config;
- all seven candidate source configs and resolved Hydra configs;
- reward YAML, env YAML, scheduler, trainer;
- tests and adjudicators;
- legal GPU list;
- schedule/reward/gate constants.

No field may contain `TBD`, null, mutable alias, or symlink target that can change.

### 14.2 Candidate versus formal config copies

Before the pilot, the seven candidate configs have:

```text
formal_values_frozen = true
formal_launch = false
calibration_label = base_v20_R1_theta090_S500_A350_0850
```

After pilot and smoke PASS, `a2_piper_v20_R1_promote_configs.py` creates copies under:

```text
scriptsFORhuman/v20_R1/frozen_formal/
```

The only allowed diff is:

```text
formal_launch: false -> true
admission_manifest_sha256: <exact admitted manifest hash>
```

All scientific values, seeds, topology, schedule, rewards, physics, and checkpoint binding must remain byte-equivalent. The promotion script fails on any other diff and writes final resolved config hashes.

### 14.3 Launcher contract

The formal launcher accepts only:

- files under `frozen_formal/`;
- exact manifest hash;
- clean expected branch/commit;
- exact G2 checkpoint hash;
- physical GPU0–6;
- no existing output directory;
- exact one-process/4096-env topology.

---

## 15. R1-P0 — Static and provenance admission

### 15.1 Required checks

1. Checkpoint path/SHA and adjacent v19 config.
2. URDF content/blob binding.
3. B0 evidence/source hashes.
4. Python compile for every changed Python file.
5. `git diff --check`.
6. All existing base_v20 CPU tests.
7. All new R1 CPU tests.
8. Hydra compose for pilot and all seven candidate configs.
9. Disabled-path parity against G2 step2000.
10. Observation/action dimensions unchanged.
11. No hidden action override.
12. Snapshot guard and schedule tests.
13. Strict exporter/adjudicator tests.
14. Exact artifact namespace tests.
15. GPU7 rejection tests.

### 15.2 Disabled-path parity

With all R1 selectors disabled:

- policy action and environment action are unchanged;
- no R1 reward is nonzero;
- no R1 terminal reason appears;
- no snapshot is filtered;
- no observation dimension changes;
- natural exit and strict exporter remain valid.

### 15.3 R1-P0 result

Only the label `STATIC PASS` is legal. STATIC PASS does not authorize the pilot until R1-P1 also passes.

---

## 16. R1-P1 — No-learning baseline and runtime semantic admission

### 16.1 Formal B0 task-space regeneration

Run the exact G2 step2000 policy with **no learning**, v20 telemetry enabled, and all S/E/A effects disabled:

```text
seeds = 0, 1, 2
envs per seed = 16
total = 48
physical GPUs = any fixed subset of 0–6
GPU7 = forbidden
```

Output:

```text
logs_eval/base_v20_R1/baseline/B0_G2_step2000_pooled48_<timestamp>/
```

Requirements:

- 48/48 strict-valid records;
- exact checkpoint/config/URDF binding;
- task/safety values reproduce Section 3 within deterministic tolerance;
- full task-space/smoothness fields are populated;
- no R1 reward or terminal behavior is enabled;
- output is frozen before pilot.

The regenerated baseline is used for paired reporting. It cannot weaken the absolute gates in Sections 18–20.

### 16.2 One-environment forced semantics

On one legal GPU, use scripted high-level actions and/or state setup through existing high-level environment APIs to verify:

1. crossing before send in `penalty` mode -> one graded event, no S terminal;
2. a second crossing frame -> no duplicate event;
3. crossing before send in `terminal` mode -> exact `pre_send_root_crossing` terminal;
4. crossing after send -> legal;
5. hinge `>=0.90` without valid hold -> no latch;
6. valid hold plus hinge `>=0.90` -> latch;
7. E pre-send traversal reward -> zero;
8. E root crossing alone -> no corridor latch;
9. A wrong-direction/stationary/invalid-hold -> zero;
10. staged reset preserves exact latch/reference state;
11. invalid future-hard snapshots are rejected;
12. schedule callback at 0 and 500 produces exact phase markers.

### 16.3 Canonical16 zero-shot config admission

Evaluate each of the seven candidate configs with G2 step2000 and no learning.

This is not a policy test. Expected behavior:

- S soft-phase configs emit penalty semantics, not terminal semantics;
- E branches gate income correctly;
- A terms obey masks;
- disabled factors remain zero;
- all records bind to exact config hashes.

### 16.4 R1-P1 PASS

R1-P1 passes only if all baseline and semantic runs are strict-valid and every forced assertion passes. Any execution-semantic defect blocks the pilot.

---

## 17. R1-P2 — One-shot policy learnability pilot

### 17.1 Pilot identity

```text
cell = G4 (S + E, no A)
training seed = 0
physical GPU = 0
envs = 256
batches = 750
save frequency = 250
warm start = exact G2 step2000
schedule = penalty batches 0–499, terminal batches 500–749
```

GPU0 may be replaced before launch by one fixed idle GPU in 1–6, but the chosen physical ID is written into the frozen attempt manifest and cannot change during the attempt.

### 17.2 Why 750 batches

The formal S schedule switches at batch500. A 500-batch pilot would never collect a meaningful hard-phase window. `750` batches provides:

- 500 batches of soft exploration and behavior shaping;
- 250 batches under the exact hard institution;
- checkpoints at 250, 500, and 750.

### 17.3 Attempt-consumption guard

Before process spawn, the launcher atomically creates:

```text
logs_eval/base_v20_R1/pilot/PILOT_ATTEMPT_CONSUMED.json
```

It contains plan/config/code/checkpoint/URDF hashes, GPU, PID intent, command, and timestamp. Once created, every R1 pilot launcher must refuse another attempt.

Static/compose failures that occur **before** creation do not consume the pilot. Any process spawn after creation consumes it, including crash, OOM, interruption, or infrastructure failure.

### 17.4 Endpoint evaluation

Evaluate `model_step_000750.pt` on canonical16 seed0 with the hard terminal semantics and full strict telemetry.

The pilot does not select among checkpoints. Step750 is the only adjudicated pilot endpoint.

### 17.5 Pilot PASS gates

All are required.

**Execution and provenance**

- natural exit0;
- exact 750/750 batches;
- finite step250/500/750 checkpoints and optimizer state;
- exact schedule transition at batch500 once;
- no snapshot-audit failure;
- strict-valid canonical16 = 16/16;
- no NaN/non-finite/malformed telemetry;
- exact hash binding.

**Minimum task retention**

- goal `>=8/16`;
- crossing while holding `>=8/16`;
- stage4 occupancy nonzero;
- last-50-hard-batch goal rate `>0`;
- no single terminal reason exceeds 95% of hard-phase completed episodes.

**Learnability movement**

- crossing-hinge p50 `>=0.82 rad`;
- at least `4/16` valid-hold episodes cross at hinge `>=0.90 rad`;
- send_ready `>=4/16`;
- pre-send arm tangent share p50 `>=0.30`;
- hard-phase send-ready episode rate in batches700–749 `>=10%`;
- pre-send terminal rate in batches700–749 `<=0.80` times the rate in batches500–549.

**Pilot safety and tracking**

- upper-DOF overspeed `0/16`;
- no goal episode has body collision before crossing;
- arc position error p95 `<=0.050 m`;
- arc orientation error p95 `<=0.90 rad`;
- positive hinge velocity p95 `<=0.45 rad/s`;
- hinge acceleration p95 `<=1.25 rad/s²`;
- hinge jerk p95 `<=35 rad/s³`;
- arm raw-action rate p95 `<=2.75` per control step;
- arm raw-action jerk p95 `<=4.50` per control step².

### 17.6 Pilot failure

Any failed gate yields:

```text
R1_STATUS = R1_POLICY_LEARNABILITY_BLOCKER
FORMAL_TRAINING_READY = false
G1-G7 MAY LAUNCH = no
```

No second pilot, continuation from a pilot checkpoint, reward edit, curriculum edit, threshold edit, or different seed is authorized inside R1.

An infrastructure failure after attempt consumption is `INCONCLUSIVE_INFRA`, but it still does not authorize an automatic rerun. A new user-approved amendment would be required.

---

## 18. Seven-cell 64x50 training smoke

Run only after the pilot passes.

### 18.1 Topology

```text
G1->GPU0, G2->GPU1, ..., G7->GPU6
64 env per group
50 batches
save at 50
one process per group
GPU7 forbidden
```

### 18.2 Common operational admission

Every group must satisfy:

- natural exit0 at 50/50;
- finite checkpoint and optimizer state;
- exact source/resolved config and checkpoint hashes;
- intended physical GPU and no cross-GPU process;
- no OOM, NCCL, Vulkan/device mismatch, traceback, NaN, or non-finite action;
- no staged-reset store/load mismatch;
- no malformed terminal/reward/telemetry group;
- stage3 occupancy `>0` and stage4 occupancy `>0`;
- upper-DOF overspeed termination rate `<=0.5%` over completed smoke episodes;
- output written directly into the R1 smoke namespace;
- no `.writing` or partial checkpoint after natural exit.

### 18.3 Exact factor matrix

| Group | Required active behavior | Required exact-zero behavior |
|---|---|---|
| G1 | v20 telemetry only | S penalty/terminal, E, A |
| G2 | E pre-send gate/corridor/wide wage | S penalty/terminal, A |
| G3 | S penalty phase and snapshot guard | E, A |
| G4 | S penalty phase + E | A |
| G5 | S penalty phase + A | E |
| G6 | S penalty phase + E + A | none of S/E/A |
| G7 | same as G6, seed1 | none of S/E/A |

### 18.4 Factor-specific smoke gates

**G1**

- all R1 reward terms exactly zero;
- goal rate `>0`;
- no R1 terminal reason.

**G2**

- target-root pre-send scale exactly zero when E gate active;
- root crossing never activates the E corridor latch;
- no S penalty/terminal;
- no A income;
- goal rate `>0`.

**G3/G4/G5/G6/G7**

- schedule remains `penalty` for all 50 batches;
- at least one pre-send crossing penalty event is observed across the run;
- zero `pre_send_root_crossing` terminal events, because batch500 is not reached;
- snapshot rejection counter is finite and non-negative;
- no schedule transition to terminal.

**A cells G5/G6/G7**

- A reward is nonzero in at least one valid held-progress sample;
- A reward is exactly zero outside its valid mask;
- A positive-income ratio `<=10%`;
- no non-finite share/error output.

### 18.5 Smoke failure policy

- Any execution-semantic or policy-safety failure blocks formal training.
- No reward, schedule, physics, or threshold tuning is permitted.
- An evaluation/export-only defect may be repaired once only if policy execution bytes and checkpoint are unchanged; preserve the original strict-invalid artifact and repair provenance.
- A training-execution defect has no automatic rerun under R1.

---

## 19. Formal launch and GPU allocation

### 19.1 Readiness gate

`FORMAL_TRAINING_READY` becomes true only when all are present:

```text
R1-P0 = STATIC PASS
R1-P1 = RUNTIME SEMANTIC PASS
R1-P2 = POLICY LEARNABILITY PASS
G1-G7 64x50 smokes = PASS
formal promotion diff whitelist = PASS
final formal config hashes = recorded
formal admission manifest = signed by exact hashes
```

### 19.2 GPU allocation

```text
GPU0 -> G1
GPU1 -> G2
GPU2 -> G3
GPU3 -> G4
GPU4 -> G5
GPU5 -> G6
GPU6 -> G7
GPU7 -> unavailable / prohibited
```

During seven-group training, evaluation waits until one GPU0–6 is released or all groups finish.

### 19.3 Startup acceptance

For each group:

- one process bound to intended physical GPU;
- 4096 environments instantiated;
- exact policy-only G2 checkpoint loaded;
- exact S/E/A header and schedule;
- correct seed;
- W&B identity and output root;
- nonzero GPU utilization and stable memory;
- no traceback/OOM/NCCL/device error;
- batch1 completed.

### 19.4 Completion acceptance

For each non-futile group:

- 2500/2500 batches;
- checkpoints at 250–2500 every 250;
- natural exit0;
- W&B `finished`;
- no partial checkpoint;
- exact saved config and hashes;
- launcher/process tree closed.

---

## 20. Online review and futility

### 20.1 Mandatory checkpoints

Review steps:

```text
500, 1000, 1500, 2000
```

Step500 is the first checkpoint at the soft/hard boundary. It is not treated as full hard-phase evidence.

### 20.2 No behavior stop before step1000

Operational failures stop immediately. Behavioral futility is not applied before step1000.

### 20.3 Futility after step1000

A group may stop only if two consecutive strict-valid checkpoints satisfy all:

- goal `0/16`;
- send_ready `<2/16`;
- crossing-hinge p50 does not improve by at least `0.03 rad` between the checkpoints;
- stage4 occupancy is collapsing or one terminal reason exceeds 95%;
- no safety improvement offsets the collapse.

The stopped cell remains in the matrix and is never replaced in R1.

### 20.4 No in-place retuning

Prohibited during formal training:

- theta or tolerance change;
- S boundary or penalty change;
- E normalization/scale/ramp change;
- A scale change;
- staged-reset ratio/capacity change;
- arm/gripper physics change;
- checkpoint substitution;
- selection-gate change.

---

## 21. Evaluation plan

### E0 — All-checkpoint canonical16

```text
7 groups x 10 checkpoints = 70 rows
seed0
16 matched doors
strict R1 schema
```

No endpoint preference and no missing-row imputation.

### E1 — Mechanical within-group selection

Apply the fixed lexicographic order in Section 23. Select exactly one strict-valid checkpoint per group or mark `NO_PROMOTABLE_CHECKPOINT`.

### E2 — Selected pooled48

For every selected group checkpoint:

```text
seeds0–2
16 doors each
48 total
```

All seven groups receive pooled evaluation when they have a strict-valid selected checkpoint.

### E3 — Matched factor analysis

Paired comparisons:

```text
G1 -> G2: E without S
G1 -> G3: S without E
G3 -> G4: incremental E under S
G3 -> G5: incremental A under S
G4 -> G6: incremental A under S+E
G6 -> G7: training-seed replication
```

### E4 — Release freeze

Freeze one candidate and checkpoint SHA before holdout or render review.

### E5 — Holdout64

```text
seeds3–6
16 doors each
64 total
```

Holdout failure rejects the frozen candidate. It does not reopen checkpoint selection.

### E6 — Matched render review

Render at minimum:

- G1 selected control;
- simplest passing non-control candidate;
- G6;
- G7;
- low/light/weak, median, and high/heavy/strong doors;
- default, handle-side, and handle-top cameras.

Overlay:

- stage;
- hinge position/velocity;
- root x and pre-send displacement;
- send latch;
- curriculum phase;
- hold state;
- arm/base tangent contribution;
- arc error;
- release;
- terminal reason.

---

## 22. Formal acceptance gates

### 22.1 Common task and safety

| Metric | Canonical16 | Pooled48 | Holdout64 |
|---|---:|---:|---:|
| Goal | >=15/16 | >=46/48 | >=60/64 |
| Crossing while holding | >=15/16 | >=46/48 | >=60/64 |
| Upper-DOF overspeed | 0 | 0/48 | 0/64 |
| Pre-crossing bilateral | >=99% | >=99% | >=99% |
| Pre-crossing coasting | <2% | <2% | <2% |
| Pre-crossing over-force | <2% | <2% | <2% |
| Post-release body contact | report | <=2/48 | <=3/64 |
| Post-release force p95 | report | <80 N | <80 N |
| Opening slip p95 | <=3.0 cm if defined | <=3.0 cm | <=3.0 cm |
| Held hinge | report | p50>=1.45, p95>=1.50 rad | same |

### 22.2 Send-first behavior

```text
theta_send = 0.90 rad
```

| Metric | Gate |
|---|---|
| Goal episodes with pre-send crossing | exactly 0 |
| Send-before-cross rate | >=15/16 canonical; >=46/48 pooled; >=60/64 holdout |
| Hinge at first root crossing p50 | >=0.90 rad |
| Hinge at first root crossing p10 | >=0.85 rad |
| Crossing-hinge p50 improvement over B0 | >=0.15 rad (absolute 0.90 gate dominates) |
| Pre-send forward displacement p95 | <=0.20 m |
| Pre-send lateral displacement p95 | <=0.15 m |
| Pre-send planar translation p95 | <=0.25 m |
| Pre-send yaw change p95 | <=0.30 rad |
| Root-plane crossing before valid latch | forbidden |
| Stage4 overtime | <=2/48 pooled and no single-bucket concentration |

### 22.3 Arm-majority and arc tracking

The frozen diagnostic B0 arm-share p50 is `0.0893308`. The formal gate is intentionally absolute and materially higher.

| Metric | Gate |
|---|---|
| Pre-send arm tangent share p50 | **>=0.60** |
| Pre-send arm tangent share p10 | **>=0.45** |
| Relative p50 improvement over frozen B0 diagnostic | >=0.15 (absolute gate dominates) |
| TCP-handle position error p95 | <=0.030 m |
| TCP-handle orientation error p95 | <=0.25 rad |
| Along-handle slip p95 | <=0.030 m |
| A positive-income ratio | <=10% |

### 22.4 Smoothness and fluency

| Metric | Formal gate |
|---|---:|
| Positive hinge velocity p95 | <=0.40 rad/s |
| Hinge acceleration p95 | <=1.00 rad/s² |
| Hinge jerk p95 | <=28 rad/s³ |
| Arm raw-action rate p95 | <=2.20 per control step |
| Arm raw-action jerk p95 | <=3.60 per control step² |
| Median task time | <=15.0 s |
| Render behavior | PASS |

The smoothness caps are approximately 1.25–1.30 times the frozen worst two-episode B0 diagnostic values. The task-time cap is approximately `1.20 x 12.51 s`.

### 22.5 A-factor claim gate

To claim A adds value:

- G6 and G7 both pass all hard gates;
- each improves pre-send arm-share p50 by at least `0.10` over G4;
- neither regresses pooled goal by more than `2/48`;
- both keep opening slip `<=3 cm`;
- both pass arc/smoothness gates;
- paired-effect direction agrees across G6/G7.

A single-seed A improvement is not promoted.

---

## 23. Mechanical selection and release wording

### 23.1 Within-group order

1. STRICT_VALID and exact provenance;
2. common task/safety gates;
3. send-first gates;
4. arm-majority/arc gates;
5. smoothness/fluency gates;
6. lower task time;
7. earlier checkpoint only as final tie-breaker.

### 23.2 Across-group order

Prefer the simplest passing mechanism:

1. G1 if ordinary continuation alone passes all behavior gates;
2. otherwise G2 if E alone passes;
3. otherwise G3 if S alone passes;
4. otherwise G4 if S+E passes and A is not materially replicated;
5. G5 if it is the simplest superior passing mechanism;
6. G6/G7 full-method claim only under replicated A gate.

A control may become the release if it genuinely passes the revised behavior claim. It cannot support a causal claim for a factor it does not contain.

### 23.3 No-release result

If no group passes all gates:

```text
base_v20_R1 = NO RELEASE
G2 step2000 remains the prior operational reference
```

No task-success-only fallback exists.

---

## 24. One-shot and failure rules

### C1 — P1 status

P1 remains `P1_PHYSICAL_BLOCKER`; no P1 rerun or controller revision is legal.

### C2 — R1-P0/P1 semantic failure

Do not consume the pilot until static and semantic code is corrected. These are implementation admission gates, not policy attempts.

### C3 — Pilot failure

Any consumed pilot failure closes R1 as `R1_POLICY_LEARNABILITY_BLOCKER`. No retry, continuation, alternate seed, or threshold change.

### C4 — Smoke failure

No formal launch. Only a provably evaluation-only repair can be separately adjudicated; training-semantic changes require a new version.

### C5 — Formal seed sensitivity

If G6 passes and G7 fails, no full A claim. A simpler passing group may still release.

### C6 — Holdout failure

The frozen release candidate fails. Do not choose another checkpoint using holdout seeds.

### C7 — Reporter defect

A targeted evaluation-only repair may rerun the exact checkpoint if policy execution semantics are unchanged. Preserve old strict-invalid artifacts.

### C8 — GPU availability

GPU7 remains forbidden. Loss of a legal GPU delays work; it does not authorize topology change or GPU7 use.

---

## 25. Acceptance/resource matrix

| Stage | GPU | Envs | Seeds | Max attempts | Required classification to proceed |
|---|---:|---:|---|---:|---|
| R1-P0 static | CPU | 0 | — | until pre-runtime freeze | STATIC PASS |
| B0 no-learning pooled | 0–6 only | 16/run | 0,1,2 | 1 complete evidence set | RUNTIME PASS, 48/48 strict-valid |
| Forced semantics | one of 0–6 | 1 | 0 | 1 evidence set | RUNTIME SEMANTIC PASS |
| Seven zero-shot configs | 0–6 | 16 each | 0 | 1/group | RUNTIME SEMANTIC PASS |
| G4 pilot | one fixed GPU0–6 | 256 | train0/eval0 | **1 consumed attempt total** | POLICY LEARNABILITY PASS |
| Seven smokes | GPUs0–6 | 64/group | formal seeds | 1/group | all PASS |
| Formal G1–G7 | GPUs0–6 | 4096/group | G1–6=0, G7=1 | 1/group | natural completion or registered futility |
| Canonical M22 | released GPU0–6 | 16 | eval0 | 70 exact rows | strict adjudication |
| Pooled endpoint | released GPU0–6 | 16/run | 0,1,2 | 1 set/group | hard gates |
| Holdout | released GPU0–6 | 16/run | 3,4,5,6 | 1 frozen candidate | confirmation |
| Render | released GPU0–6 | 1–3 | bound | fixed queue | render PASS |

---

## 26. Required deliverables

### 26.1 Preflight

```text
R1_SCIENTIFIC_MANIFEST.json
R1_SCIENTIFIC_MANIFEST.md
B0 pooled48 JSON/CSV/MD
semantic admission JSON/MD
resolved Hydra configs
source/hash manifest
```

### 26.2 Pilot

```text
PILOT_ATTEMPT_CONSUMED.json
launcher command/log/PID/exit/natural-exit
step250/500/750 checkpoints
training-window metrics
canonical16 endpoint artifact
pilot adjudication JSON/CSV/MD
```

### 26.3 Smoke/formal

- one immutable launcher bundle;
- per-group command/log/PID/GPU/config hashes;
- checkpoint manifests;
- all M22 rows;
- seven endpoint reports;
- paired analysis;
- holdout and render artifacts;
- final release/no-release JSON and Markdown.

---

## 27. Execution checklist

### Pre-runtime

1. [ ] Record exact branch head and clean/dirty state.
2. [ ] Verify G2 checkpoint path/SHA and adjacent config.
3. [ ] Verify actual runtime URDF against blob `95c769...`.
4. [ ] Install R1 independent namespace and no-overwrite guards.
5. [ ] Implement graded `dt`-invariant S penalty.
6. [ ] Wire root `schedule_dict` into trainer.
7. [ ] Implement snapshot guard and hard-phase audit.
8. [ ] Correct wrapped-yaw/root reconfiguration telemetry.
9. [ ] Add R1 configs, scripts, tests, exporter schema.
10. [ ] Pass all R1-P0 checks.
11. [ ] Write complete scientific manifest with no null/TBD hashes.

### Runtime admission

12. [ ] Run no-learning B0 pooled48 and freeze it.
13. [ ] Run forced one-env semantics.
14. [ ] Run seven canonical16 zero-shot config admissions.
15. [ ] Confirm R1-P1 PASS.

### One-shot pilot

16. [ ] Atomically consume the pilot attempt.
17. [ ] Run G4 256 env x 750 batches on one legal GPU.
18. [ ] Evaluate step750 canonical16.
19. [ ] Apply every pilot gate mechanically.
20. [ ] If any gate fails, close R1 and stop.

### Smoke and formal

21. [ ] Run seven 64x50 smokes on GPU0–6.
22. [ ] Apply common and factor-specific smoke gates.
23. [ ] Promote configs with whitelist-only provenance diff.
24. [ ] Record final formal hashes and admission manifest.
25. [ ] Set `FORMAL_TRAINING_READY=true` only now.
26. [ ] Launch G1–G7 on GPU0–6.
27. [ ] Keep GPU7 unused.
28. [ ] Run mandatory reviews without in-place edits.
29. [ ] Complete all canonical, pooled, paired, holdout, and render stages.
30. [ ] Publish one release or explicit no-release result.

---

## Appendix A — Frozen numerical constants

```yaml
base_v20_R1:
  plan_id: base_v20_R1_policy_behavior_v1
  theta_send_rad: 0.90
  send_tolerance_rad: 0.05
  root_x_margin_m: 0.03

  curriculum:
    soft_start_batch: 0
    hard_start_batch: 500
    soft_mode: penalty
    hard_mode: terminal
    crossing_base_component: 1.0
    crossing_shortfall_gain: 1.0
    reward_scale: -15.0

  economics:
    target_root_pre_send_scale: 0.0
    target_root_post_send_stage4_scale: 0.5
    ramp_width_rad: 0.20
    corridor_latch_mode: send_ready_v20
    door_wide_norm_rad: 1.60
    door_wide_scale: 4.2666667

  arm_tie:
    activity_floor_mps: 0.005
    arc_position_tolerance_m: 0.03
    arc_orientation_reward_tolerance_rad: 0.20
    arm_tangent_scale: 3.5
    arc_tracking_scale: 0.85

  pilot:
    envs: 256
    batches: 750
    save_frequency: 250

  formal:
    envs: 4096
    batches: 2500
    save_frequency: 250
```

---

## Appendix B — Plan-level claim language

### Allowed if R1 succeeds

> The learned policy shifts door-opening progress before traversal and achieves an arm-majority, grasp-stable send to at least 0.90 rad under a bounded learned whole-body reconfiguration envelope.

### Forbidden

- “P1 passed.”
- “The arm alone opens the door.”
- “F1 relief was certified.”
- “The geometry is proven reachable/unreachable.”
- “A factor works” without the corresponding ablation and replication gates.
- “The student can learn it” before a separate distillation study.

---

## Appendix C — Scientific rationale for staged reset

DoorMan’s staged-reset method is retained because contact-rich long-horizon policies may avoid or unlearn difficult downstream states when those states are rarely visited. Staged reset reweights occupancy toward later task stages and increases the frequency of useful gradients. In R1 it is an exploration mechanism only; it is not a physical-feasibility certificate and is never included in the reward itself.

---

## Final status at document creation

```text
P1 = CLOSED / P1_PHYSICAL_BLOCKER
R1-P0 = NOT RUN
R1-P1 = NOT RUN
R1-P2 PILOT = NOT RUN
G1-G7 = FORBIDDEN NOW
FORMAL_TRAINING_READY = false
LEGAL PHYSICAL GPUS = 0-6 only
```

---

## Appendix D — Exact source-config factor contract

All candidate source configs explicitly bind every R1 selector. No factor is inherited implicitly.

| Key | G1 | G2 | G3 | G4 | G5 | G6 | G7 |
|---|---|---|---|---|---|---|---|
| `seed` | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| `a2_v20_telemetry_enabled` | true | true | true | true | true | true | true |
| `a2_v20_send_hinge_threshold` | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 |
| `a2_v20_send_latch_enabled` | false | true | true | true | true | true | true |
| `a2_v20_R1_send_curriculum_enabled` | false | false | true | true | true | true | true |
| initial crossing mode | disabled | disabled | penalty | penalty | penalty | penalty | penalty |
| `schedule_dict` S entry | absent | absent | exact 0/500 | exact 0/500 | exact 0/500 | exact 0/500 | exact 0/500 |
| snapshot guard | false | false | true | true | true | true | true |
| crossing reward scale | 0.0 | 0.0 | -15.0 | -15.0 | -15.0 | -15.0 | -15.0 |
| traversal economics | false | true | false | true | false | true | true |
| corridor latch mode | legacy | send_ready | legacy | send_ready | legacy | send_ready | send_ready |
| wide norm / scale | 1.50 / 4.0 | 1.60 / 4.2666667 | 1.50 / 4.0 | 1.60 / 4.2666667 | 1.50 / 4.0 | 1.60 / 4.2666667 | 1.60 / 4.2666667 |
| arm tie enabled | false | false | false | false | true | true | true |
| arm tangent scale | 0.0 | 0.0 | 0.0 | 0.0 | 3.5 | 3.5 | 3.5 |
| arc tracking scale | 0.0 | 0.0 | 0.0 | 0.0 | 0.85 | 0.85 | 0.85 |

Additional mandatory fields in every candidate config:

```yaml
env:
  config:
    a2_v20_R1_plan_id: base_v20_R1_policy_behavior_v1
    a2_v20_R1_p1_status: P1_PHYSICAL_BLOCKER
    a2_v20_formal_values_frozen: true
    a2_v20_formal_launch: false
    a2_v20_calibration_label: base_v20_R1_theta090_S500_A350_0850
```

G1 and G2 have no S schedule. G2 still enables send-latch plumbing because E requires `send_ready`; it receives no crossing penalty or terminal. G1 computes send metrics through telemetry but cannot use them for reward or termination.

Pilot config differs from candidate G4 only in:

```yaml
num_envs: 256
algo.trl.num_total_batches: 750
callbacks.model_save.save_frequency: 250
env.config.a2_v20_formal_launch: false
experiment role: one_shot_policy_learnability_pilot
```

No scientific selector differs from G4.

---

## Appendix E — Metric denominators and deterministic comparison tolerances

### E.1 Pilot denominators

- `goal`, `crossing_while_holding`, `send_ready`: denominator is all 16 canonical episodes.
- crossing-hinge quantiles: denominator is episodes with a valid first physical root-crossing record. Fewer than 8 valid crossing records fails the pilot through the crossing-while-holding gate.
- pre-send arm-share quantiles: one per-episode median is first computed over active, valid-hold, pre-send samples; the reported p50 is then the median over episodes with at least 20 active samples. Fewer than 8 eligible episodes fails.
- arc-error quantiles: pooled active, valid-reference, valid-hold, pre-send samples, plus per-episode values in the artifact.
- training-window terminal rates: completed episodes whose opening phase began in the named batch window.
- A-income ratio: per episode, then p95 across eligible episodes; the 10% cap applies to p95, not only the mean.

### E.2 Formal denominators

- send-before-cross rate: all episodes that physically cross; any goal without a valid crossing record is strict-invalid.
- arm-share release gate: per-episode p50 over pre-send active samples, followed by p10/p50 across eligible episodes. Eligibility requires at least 20 active samples and a valid handle reference.
- smoothness: computed only over valid held opening samples before release, with exact 50 Hz control timing.
- task time: successful goal episodes only; success count gates apply first.

### E.3 B0 no-learning parity tolerances

The R1-P1 no-learning pooled48 reproduction must satisfy:

```text
counts and terminal counts: exact
crossing-hinge p10/p50/p95: within 0.01 rad of frozen B0
held-hinge p50/p95: within 0.01 rad
release-hinge p50/p95: within 0.01 rad
opening-slip p95: within 0.20 cm
bilateral/coasting/over-force rates: within 0.002 absolute
hinge-velocity p95: within 0.02 rad/s
task-time p50: within 0.20 s
```

A mismatch beyond tolerance is not automatically policy degradation because this is a no-learning run; it is a runtime/parity blocker that must be resolved before pilot consumption.
