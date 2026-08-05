# A2+Piper DoorDog — base_v22 Posture Arbitration, Clearance Strategy, Force Routing, and Hinge-Randomization Plan

**Plan ID:** `base_v22_posture_clearance_force_routing_v2`  
**Execution ID:** `base_v22_execution_v2`  
**Date:** 2026-08-05 HKT  
**Repository / branch:** `Jam-Stark/DoorDog` / `A2_Piper`  
**Scientific base:** v21-B closure commit `89c6538ad274ab6d1256389e3f2b3ceefd68d98a`, or a direct descendant whose additional changes are repository housekeeping only  
**Legal physical GPUs:** `0, 1` only  
**GPU2–7:** unavailable for this task unless the user explicitly reallocates them  
**Warm start:** v21-B B1 release checkpoint, `policy_only`  
**Warm-start path:** `logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal/B1/model_step_000500.pt`  
**Warm-start SHA-256:** `d2732c148dd3176abafbf3a5c9425d4a34c17b352e8362bbfb38c8ac960d8421`  
**Warm-start saved-config SHA-256:** `70ccd1b43a07574d36702947c706b5ef80184fffd0d2853cf188c9286a959a79`  
**Runtime URDF:** `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf`  
**URDF SHA-256:** `d02cdacdcd4aaf1480b52ba9a6a62f5e9bbd040036a796154dbff70d1391a1d5`  
**Frozen A2_Base policy SHA-256:** `783c65386ce49127a17ec261794ed3c7002309e293e3cb88562dee922c894b1b`  

---

## Decision block

```text
V22_PRIMARY_QUESTION_1 =
  can roll/pitch become conditionally useful rather than a universal
  +0.4-rad pitch shortcut?

V22_PRIMARY_QUESTION_2 =
  can the policy choose among three valid clearance strategies:
    (a) controlled fling,
    (b) hold-open with the gripper,
    (c) safe trunk/front-thigh assistance,
  according to the observed door dynamics?

V22_PRIMARY_QUESTION_3 =
  how do hinge damping, hinge stiffness/rebound, and hinge-drive
  max force/resistive torque affect posture use, release strategy,
  arm-force margin, body-assist eligibility, task success, and safety?

FORMAL_WAVE_A_LEGACY_SCALE_ABLATION = removed
FORMAL_TRAINING_READY_NOW = false
LEGAL_PHYSICAL_GPUS = [0, 1]
THETA_SEND = 0.90 rad, frozen for the complete v22 causal round
RELEASE_HINGE = 1.60 rad, frozen
ARM_EFFORT_PROFILE = unchanged from v21-B
PIPER_VELOCITY_LIMITS = unchanged
STAGE_TIME = unchanged unless a worker-authorized research-only diagnostic
ACTION_DIMENSION = unchanged
ACTOR_OBSERVATION_DIMENSION = unchanged
```

---

# 0. Executive scientific position

## 0.1 The target behavior is a hierarchy, not one universal motion

v22 targets the following ordered policy:

```text
ordinary / middle-height / manageable hinge:
  near-neutral trunk
  arm-led opening
  controlled clearance at release

height-extreme or moderately difficult hinge:
  bounded roll/pitch reconfiguration
  arm-led opening
  controlled fling or hold-open according to rebound behavior

arm-plus-posture infeasible hinge:
  measured failure latch
  controlled trunk/front-thigh assistance
  controlled release or continued body support
```

The hierarchy is:

```text
arm only
  -> arm + bounded posture
  -> approved body assistance after measured failure
```

No escalation is selected from door mass alone. Escalation requires online evidence from motion response, tracking error, effort proxy, joint margin, and support state.

## 0.2 Revision from v22 draft 1: fling is a legitimate strategy

v21-B exposed uncontrolled behavior of the form:

```text
hard shove -> premature hand loss -> large inertial coast
```

The first v22 draft overcorrected by suppressing post-release coast in general. That is rejected.

For a spring-loaded door, a positive release impulse can be desirable because it creates angular clearance and reduces the probability that the panel rebounds into the robot during traversal. v22 therefore distinguishes:

```text
CONTROLLED_FLING:
  deliberate positive release velocity
  valid hand support until the release condition
  bounded peak velocity
  no panel/robot collision
  sufficient clearance through traversal

UNCONTROLLED_FLING:
  premature support loss
  excessive velocity or impact
  no clearance benefit
  rebound collision or loss of task control
```

A high-mass or high-damping door is not required to fling successfully. The policy may hold the door open longer, maintain body support, or complete without a large release impulse.

## 0.3 Future active anti-rebound gripper bracing

A separate future idea is:

> after release or partial release, use the gripper/palm to maintain light compliant contact with the door panel or re-contact the panel to arrest rebound.

This is not implemented in v22 because it introduces a new contact-mode transition, compliant/force-control requirements, finger-safety questions, and a new student-observability burden.

The worker must append this exact research item to:

```text
scriptsFORhuman/a2_piper_longterm_TODO.md
```

under the parking-lot or future-research section:

```text
Active anti-rebound gripper bracing / re-contact:
after the teacher push-door behavior is stable, study maintaining compliant
gripper/palm contact on the panel or re-contacting the panel after release to
arrest spring return. Required evidence: force-controlled contact, no finger
crushing or frame contact, visual-policy observability, and comparison against
controlled fling and hold-open strategies.
```

## 0.4 Why roll/pitch can increase dense-contact capability

For a tangential handle force `F_t`:

```text
tau_arm = J_arm(q)^T * (t_open * F_t) + tau_gravity
```

Changing trunk roll/pitch changes:

- the arm configuration `q`;
- the directional Jacobian;
- joint-position and joint-effort margins;
- gravity load on the mounted arm;
- center-of-mass projection and foot-load distribution.

With an arm reach near `0.63 m`, a `0.4 rad` body rotation can redirect approximately:

```text
0.50 * sin(0.4)    = 0.195 m
0.62675 * sin(0.4) = 0.244 m
```

which is comparable to the `0.85–1.10 m` handle-height span. This explains why maximum pitch is a powerful universal shortcut.

An illustrative force example:

```text
40 N tangential force
0.55 m effective moment arm -> 22 N*m
0.40 m effective moment arm -> 16 N*m
```

A posture that reduces the effective moment arm by `0.15 m` reduces the required joint moment by approximately `6 N*m`, or 27%, before gravity and multi-joint coupling.

These calculations justify posture as a capability lever. They do not prove that `+0.4 rad` is optimal or that the simulated 100 N*m arm limits are hardware-realistic.

## 0.5 v21-B constraints inherited unchanged

v22 accepts the following v21-B findings:

- higher `theta_send` alone did not produce monotonic behavior;
- several high-theta policies learned high-yaw, impulse, release, and coast strategies;
- the v21-B arm-effort axis was right-censored and did not establish a realistic PiPER profile;
- implicit-PD torque evidence is estimate-only;
- no v21-B policy passed complete Route B;
- v22 must not claim true PiPER torque capability.

`theta_send` is held at `0.90 rad` so posture, hinge randomization, release strategy, and body assistance are not confounded by another send-threshold dose.

---

# 1. Scope

## 1.1 In scope

1. High-level roll/pitch action semantics and telemetry.
2. Commanded versus achieved trunk roll/pitch.
3. Conditional posture use.
4. Live-grasp posture/workspace/relative-wrench diagnostics.
5. Controlled fling, hold-open, and body-support clearance strategies.
6. Hinge damping, stiffness/rebound, and max-force/resistive-torque randomization.
7. Safe trunk/front-thigh body assistance.
8. Route-A all-checkpoint evaluation.
9. Selected pooled48, deterministic dynamics manifests, holdout64, and strict render.
10. Worker-authorized bounded gate adaptation and exploratory continuation.
11. Two-GPU sequential execution.

## 1.2 Out of scope

- changing PiPER effort limits;
- claiming true hardware torque;
- changing PiPER velocity limits;
- adding a body-height action;
- changing the 12D high-level action dimension;
- changing the frozen A2_Base locomotion policy;
- pull/in-opening doors;
- left/right mirror implementation;
- RGB student distillation;
- active anti-rebound gripper bracing;
- direct root teleport, hidden DLS, scripted train-time action override, or fallback controller.

---

# 2. Source facts that the implementation must preserve

## 2.1 Current posture action

The shared A2 door config currently exposes a body pitch/roll scale of:

```text
0.40 rad
```

The worker must identify the exact action ordering and produce a typed mapping. No v22 source may use anonymous posture indices.

## 2.2 Current door-drive implementation

At the v21-B source:

```text
DoorSpawnerCfg default hinge_drive_max_force_range = (2.5, 4.5)
hinge drive damping = 50.0
hinge drive stiffness = Uniform(1.0, 10.0)
```

v20/v21 deterministic scenarios used larger max-force values, including `5 N*m` and `10 N*m`; the delivered v21 evidence contains values up to approximately `11.4 N*m`.

The current code has no independent `rebound` random variable.

Rebound is an emergent result of:

```text
hinge stiffness
hinge damping
hinge drive max force
door inertia/mass and geometry
current angle and angular velocity
drive target
```

The worker must not create or report a synthetic scalar named `rebound` without defining its runtime measurement.

## 2.3 Drive-response model to verify

The worker must verify, rather than assume, that the effective drive approximately follows:

```text
tau_drive_raw =
  - stiffness * (theta - theta_target)
  - damping * omega

tau_drive =
  clip(tau_drive_raw, -max_force, +max_force)
```

The exact IsaacLab/PhysX units and angular convention must be written to the source audit. Until verified, damping and stiffness are called:

```text
hinge_drive_damping_native
hinge_drive_stiffness_native
```

`hinge_drive_max_force` remains reported as configured torque-cap units.

---

# 3. Worker adaptation and gate-waiver authority

The worker is explicitly authorized to continue scientifically useful execution when a non-safety threshold is too strict or poorly calibrated.

## 3.1 Hard non-waivable gates

The worker may not waive:

```text
non-finite physics or metrics
checkpoint/config/source hash mismatch
fabricated or caller-declared PASS evidence
missing metric silently filled with zero
GPU other than physical 0 or 1
hidden train-time action override
root teleport or scripted task completion
unsafe or unidentified body contact
door-frame contact accepted as assist
staged-reset state corruption
wrong episode/checkpoint/seed topology
```

## 3.2 Waivable gates

The worker may relax, suspend, replace, or bypass:

```text
pilot goal-count thresholds
posture saturation thresholds
calibration income percentages
task-time thresholds
crossing-angle thresholds
fling-rate targets
randomization bucket ranges
minimum denominator counts
exact sample counts when runtime cost is disproportionate
non-load-bearing static or style gates
```

## 3.3 Required waiver artifact

Every waiver must create:

```text
logs_eval/base_v22/locks/V22_GATE_WAIVER_<ID>.json
```

with:

```text
schema
waiver_id
timestamp_hkt
worker_identity
original_gate
observed_value
decision = RELAX | SUSPEND | REPLACE | BYPASS_FOR_EXPLORATION
replacement_gate
evidence_paths
scientific_reason
safety_impact
claim_impact
affected_nodes
expiration_node
source/config hashes
```

## 3.4 Exploration may continue after a failed pilot

A failed scientific pilot does not automatically block later training.

The worker may issue:

```text
EXPLORATORY_CONTINUATION
```

and continue one or more formal waves when:

- runtime and evidence are valid;
- no hard safety gate failed;
- the failure itself is scientifically informative;
- the continued cells can answer a declared question.

Such cells cannot be labeled release-admitted solely because the pilot was bypassed. They may still become release candidates if later frozen pooled/holdout/render gates are satisfied.

## 3.5 Adaptation windows

### Window A — after source audit and dynamics characterization

Worker may adjust:

```text
hinge randomization ranges
bucket weights
reward calibration scales
posture need thresholds
fling eligibility/velocity soft bands
```

### Window B — after pilot and before the first formal optimizer update

Worker may:

```text
choose STANDARD, RELAXED_1, or WORKER_ADAPTED profile
prune uninformative cells
activate exploratory continuation
adjust numerical acceptance thresholds
```

### Window C — after Wave 1, before Wave 2

One method amendment is allowed if Wave 1 reveals a singular, well-supported failure such as:

```text
posture need never activates
posture need activates on every ordinary episode
controlled fling reward is numerically inactive
randomization bucket is null or universally impossible
```

The amendment creates a new `ADAPTED_COHORT`. Direct causal comparisons with pre-amendment cells are forbidden unless a matched control is rerun.

No more than one Window-C amendment is allowed.

## 3.6 Worker-created acceptance profile

`WORKER_ADAPTED` is permitted if written before the relevant formal or Route-B data are inspected.

It must state:

```text
measured baseline basis
uncertainty or observed distribution
new thresholds
why STANDARD/RELAXED_1 were unsuitable
which release claims remain valid
```

Hard integrity and contact-safety gates remain unchanged.

---

# 4. Fixed v22 control contract

```yaml
v22_fixed_contract:
  warm_start:
    path: logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal/B1/model_step_000500.pt
    sha256: d2732c148dd3176abafbf3a5c9425d4a34c17b352e8362bbfb38c8ac960d8421
    load_mode: policy_only

  task:
    theta_send_rad: 0.90
    release_hinge_rad: 1.60
    stage4_to5_hinge_rad: 1.25
    physical_crossing_plane_m: 0.0
    crossing_debounce_steps: 2

  arm:
    profile: ARM_V20
    effort_limits_nm: [100, 100, 100, 100, 100, 100]
    velocity_limits: unchanged
    kp_kd: unchanged
    action_scale: unchanged

  a2_base:
    action_dim: 12
    legacy_pitch_roll_scale_rad: 0.40
    policy_sha256: 783c65386ce49127a17ec261794ed3c7002309e293e3cb88562dee922c894b1b

  formal:
    envs: 4096
    batches: 2500
    save_frequency: 250

  devices:
    allowed_physical: [0, 1]
```

---

# 5. Exact v22 randomization

## 5.1 Variables randomized during v22 training

### Already-established axes retained

```text
handle height:
  Uniform[0.85, 1.10] m

door mass:
  Uniform[80, 160] kg
```

These remain independent variables but are not the new scientific intervention.

### New hinge axes

```text
hinge_drive_damping_native
hinge_drive_stiffness_native
hinge_drive_max_force_nm
```

### Derived metrics, not random variables

```text
free-return half time
free-return peak closing velocity
free-return closing impulse
fixed-torque opening progress
effective rebound class
effective damping class
```

## 5.2 Initial registered training mixture

Every bucket still samples handle height and mass across their full ranges unless stated otherwise.

### Bucket H0 — `CORE`, weight 55%

```text
damping:   Uniform[30, 70]
stiffness: Uniform[1, 10]
max force: Uniform[3, 12] N*m
mass:      Uniform[80, 160] kg
height:    Uniform[0.85, 1.10] m
```

### Bucket H1 — `HIGH_DAMPING`, weight 15%

```text
damping:   Uniform[70, 120]
stiffness: Uniform[2, 10]
max force: Uniform[6, 16] N*m
mass:      Uniform[80, 160] kg
height:    Uniform[0.85, 1.10] m
```

This bucket is intended to be hard to accelerate and comparatively slow to return.

### Bucket H2 — `FAST_REBOUND`, weight 15%

```text
damping:   Uniform[15, 40]
stiffness: Uniform[10, 20]
max force: Uniform[10, 18] N*m
mass:      Uniform[80, 160] kg
height:    Uniform[0.85, 1.10] m
```

Low-to-moderate damping plus high stiffness and a nontrivial torque cap is the intended fast-return family.

### Bucket H3 — `HIGH_RESISTIVE_TORQUE`, weight 10%

```text
damping:   Uniform[40, 80]
stiffness: Uniform[6, 16]
max force: Uniform[14, 20] N*m
mass:      Uniform[80, 160] kg
height:    Uniform[0.85, 1.10] m
```

This bucket tests sustained hinge resistance.

### Bucket H4 — `COMPOUND_EXTREME`, weight 5%

```text
damping:   Uniform[90, 150]
stiffness: Uniform[14, 24]
max force: Uniform[16, 22] N*m
mass:      Uniform[140, 160] kg
height:    categorical {0.85, 1.10} m
```

This is a simulation stress-test bucket, not a hardware-realism claim.

## 5.3 Global worker-adjustable bounds

Window A may change bucket ranges, but every selected value must stay within:

```text
damping:   [10, 200]
stiffness: [0.5, 30]
max force: [2.5, 24] N*m
mass:      [80, 180] kg
height:    [0.85, 1.10] m
```

The worker may exceed `160 kg` only in an explicit stress-test manifest, never in the default training distribution without a Window-A amendment.

## 5.4 Why damping and fast rebound are separate

High damping and fast rebound are not synonyms.

```text
high damping:
  resists angular velocity
  usually reduces return speed
  can make both opening and closing slow

fast rebound:
  high restoring stiffness / torque
  relatively low damping
  rapid closing after support is removed
```

The final report must preserve this distinction.

## 5.5 Deterministic evaluation manifests

For every candidate, construct:

### `E0_CORE16`

```text
damping values:   {30, 50, 70}
stiffness values: {2, 6, 10}
max-force values: {5, 10, 12}
mass:              {80, 120, 160}
height:            {0.85, 0.975, 1.10}
balanced Latin-hypercube assignment
```

### `E1_DAMPING16`

```text
damping values:   {50, 75, 100, 120}
stiffness:        6
max force:        12 N*m
mass/height:      balanced
```

### `E2_REBOUND16`

```text
damping values:   {15, 25, 35, 40}
stiffness values: {10, 14, 18, 20}
max-force values: {10, 14, 18}
mass/height:      balanced
```

### `E3_RESISTIVE16`

```text
damping:          50
stiffness:        8
max-force values: {8, 12, 16, 20}
mass/height:      balanced
```

### `E4_COMPOUND16`

```text
damping values:   {90, 120, 150}
stiffness values: {14, 20, 24}
max-force values: {16, 20, 22}
mass:              {140, 150, 160}
height:            {0.85, 1.10}
balanced 16-row manifest
```

Each manifest is hashed and immutable after Window A.

---

# 6. Mandatory dynamics characterization before training

## 6.1 Free-return probe

For each registered hinge tuple:

1. place door at `1.20 rad`;
2. set angular velocity to zero;
3. remove robot contact;
4. simulate the free return.

Record:

```text
time to 0.90 rad
time to 0.60 rad
time to 0.30 rad
peak closing velocity
closing impulse proxy
minimum/maximum drive torque estimate
whether the drive stays force-capped
```

## 6.2 Fixed external-torque opening probe

Apply registered constant opening torques:

```text
5, 10, 15, 20 N*m
```

for a fixed interval and record:

```text
hinge progress
steady angular velocity
drive cap activity
```

This is a door-characterization experiment, not a policy or hardware claim.

## 6.3 Behavioral class labels

Based on measured response, classify every row as:

```text
CORE
HIGH_DAMPING
FAST_REBOUND
HIGH_RESISTIVE
COMPOUND
UNCLASSIFIED
```

If parameter ranges do not produce the intended response classes, the worker is authorized to adjust them in Window A.

---

# 7. Posture semantics

## 7.1 Mandatory telemetry

Per control step:

```text
high_level_action_raw[12]
named planar/yaw commands
named roll command
named pitch command
scaled roll/pitch command
actual trunk roll/pitch
tracking error
saturation flags
handle height and lateral offset

arm joint-position margin
arm velocity margin
implicit-PD effort-proxy margin
arm tracking error
directional Jacobian metric
hinge progress
```

## 7.2 Height-conditioned nominal posture

Use valid live-grasp states, not detached static reachability.

Diagnostic grid:

```text
pitch = [-0.25, -0.10, 0.00, 0.10, 0.25]
roll  = [-0.15,  0.00, 0.15]
```

Select the minimum-norm posture that is within 95% of the best valid relative directional-wrench capacity and satisfies:

```text
joint-position margin >=0.10
support margin >=0.03 m
TCP error <=0.03 m
no collision
```

Bounds:

```text
|pitch_nominal| <=0.15 rad
|roll_nominal| <=0.10 rad
```

If zero posture is within 5% of the best value, select zero.

## 7.3 Need signals

```text
height_need:
  nonzero height-conditioned nominal posture

workspace_need:
  joint-position margin <0.15
  OR directional Jacobian below the measured lower-tail threshold

force_need:
  valid hold
  AND hinge velocity <0.03 rad/s
  AND effort-proxy utilization >0.85
  for 10 steps

tracking_need:
  valid hold
  AND arm tracking error > baseline p90
  AND hinge velocity <0.05 rad/s
  for 10 steps
```

```text
posture_need =
  max(height_need, workspace_need, force_need, tracking_need)
```

Hysteresis:

```text
ON:  score >=0.70 for 5 steps
OFF: score <=0.35 for 10 steps
```

## 7.4 Reward semantics

### Excess posture penalty

```text
-(1 - posture_need)
* Huber(command - height_nominal)
```

Deadbands:

```text
pitch 0.05 rad
roll  0.04 rad
```

### Saturation penalty

Soft boundaries:

```text
pitch 0.30 rad
roll  0.20 rad
```

The physical command scale remains 0.40 rad.

### Feasibility reward

Reward the result, not posture magnitude:

```text
posture_need
* valid_hold
* positive_hinge_progress
* arm_margin_quality
* arc_tracking_quality
```

## 7.5 Calibration

Registered scales:

```text
[0.25, 0.5, 1, 2, 4, 8]
```

Target income ranges are guidance, not hard blockers:

```text
ordinary excess-posture penalty:
  1–5% of absolute episode reward

hard-door feasibility reward:
  1–6% of positive income

continuous 0.4-rad saturation penalty:
  2–8% of absolute episode reward
```

Worker may select the nearest lower stable scale and record a waiver.

---

# 8. Clearance-strategy arbitration

## 8.1 Three permitted strategies

```text
FLING_CLEARANCE:
  release with positive angular velocity
  door remains clear during traversal

HAND_HOLD_CLEARANCE:
  gripper maintains valid support until root clears the frame

BODY_HOLD_CLEARANCE:
  approved body contact maintains support after hand release
```

The policy is not required to use fling on every door.

## 8.2 Release and clearance events

Record:

```text
last bilateral step
release hinge
release angular velocity
release strategy
root-clear step
minimum hinge after release and before root clear
peak closing velocity
panel/robot contact after release
door-frame contact
goal
```

## 8.3 Controlled-fling eligibility

```text
valid bilateral support until release
door unlatched
release hinge >=1.45 rad
positive release angular velocity
no frame contact
no upper-DoF overspeed at release
```

The historical release threshold of `1.60 rad` remains the main target. `1.45 rad` is only the minimum typed eligibility boundary.

## 8.4 Safe clearance outcome

A strategy succeeds if, until the root clears the frame:

```text
no door-panel collision with the robot
no door-frame collision
minimum hinge >=1.10 rad
goal remains achievable
```

If exact geometry produces a better collision-clearance metric, the worker may replace the `1.10 rad` proxy in Window A and retain it as report-only.

## 8.5 Fling velocity bands

Initial soft bands:

```text
CORE:
  release omega 0.10–0.40 rad/s

FAST_REBOUND:
  release omega 0.20–0.55 rad/s

HIGH_DAMPING / HIGH_RESISTIVE / COMPOUND:
  no minimum release omega
  soft maximum 0.55 rad/s
```

Global soft maximum:

```text
0.75 rad/s
```

A safe episode is not failed merely because release velocity is below the band. The band is a shaping and interpretation tool.

## 8.6 Reward

Pay for clearance outcome, not raw final door angle.

```text
r_clearance_success:
  one-shot when the root clears the frame
  and the selected strategy has avoided collision

r_controlled_fling:
  only when FLING_CLEARANCE is eligible
  and release velocity lies in the response-conditioned soft band

r_unsafe_release:
  premature support loss
  excessive release speed
  collision or rapid rebound into robot
```

Positive post-release hinge motion is allowed and may be useful. There is no generic coast penalty.

## 8.7 Fling is allowed to fail on hard doors

For HIGH_DAMPING, HIGH_RESISTIVE, or COMPOUND doors:

```text
low fling rate = acceptable
```

provided the policy uses hand-hold or body-hold clearance and maintains safety/task success.

---

# 9. Body-assist semantics

## 9.1 Approved bodies

```text
trunk
FL_thigh
FR_thigh
```

Forbidden:

```text
rear thighs
calves
feet
arm links
gripper links
sensor/head bodies
door frame
handle
```

## 9.2 Arm-plus-posture failure latch

```text
valid hold
door unlatched
stage OPEN or SWING
hinge velocity <0.03 rad/s
and one of:
  effort proxy >0.90
  arm tracking error > baseline p95
  joint-position margin <0.10
```

Required persistence:

```text
arm failure >=15 steps
posture assist attempted >=10 steps
```

Then:

```text
body_assist_eligible = true
```

## 9.3 Safe contact

```text
approved body contacts panel
opening-aligned force >0
relative impact speed <=0.20 m/s
no frame contact
no forbidden-body panel contact
```

Five stable steps establish body support.

## 9.4 Reward and safety

```text
body assist reward:
  only after eligibility
  only for safe contact
  only for positive hinge progress

impact penalty:
  contact >150 N
  impact speed >0.20 m/s
  door velocity >0.60 rad/s
```

Suggested hard termination thresholds for the first runtime:

```text
contact peak >300 N
frame collision
forbidden-body assist
fall / bad orientation
```

The worker may adjust 150/300 N after the safe-contact probe, but may not waive body identity or frame-collision safety.

---

# 10. Required pretests

## P0-A — action semantics

Produce:

```text
V22_ACTION_SEMANTICS.json
```

and prove roll/pitch command order, scaling, units, and achieved-posture telemetry.

## P0-B — frozen posture interventions

On identical scenario manifests:

```text
legacy
zero posture
clamp pitch/roll to 0.15/0.10
height-conditioned nominal
```

Run:

```text
ordinary16
height16
hard16
```

## P0-C — live-grasp posture atlas

Generate the relative directional-wrench and support-margin atlas.

## P0-D — hinge dynamics characterization

Run free-return and fixed-torque probes over the initial hinge ranges.

## P0-E — safe trunk/front-thigh contact

Four-env probe for trunk and four-env probe for front thighs.

Failure of P0-E disables body-assist cells but does not block posture/randomization training.

## P0-F — clearance strategy replay

Use the frozen B1 checkpoint and classify existing episodes as:

```text
fling
hand hold
unsafe release
```

Verify clearance-window telemetry and reward calibration.

---

# 11. Pilot

```text
cell: conditional posture + common clearance semantics
GPU0
256 env
750 batches
save250
current door distribution
body assist off
```

GPU1 concurrently finishes hinge-characterization and deterministic manifests.

## Pilot classifications

### `PILOT_FULL`

```text
goal >=12/16
supported crossing >=14/16
ordinary pitch saturation <=20%
unsafe release <=2/16
non-finite =0
```

### `PILOT_PARTIAL`

```text
goal >=10/16
supported crossing >=12/16
ordinary pitch saturation <=40%
unsafe release <=4/16
non-finite =0
```

### `PILOT_NULL`

Valid evidence below PARTIAL.

## Responses

```text
FULL:
  proceed to all formal waves

PARTIAL:
  proceed under RELAXED_1 or WORKER_ADAPTED

NULL:
  worker may:
    continue exploratory posture training,
    skip directly to randomization research with the warm start,
    or issue one method amendment.
```

No scientific pilot outcome automatically terminates v22.

---

# 12. Formal matrix — revised, no old Wave A

All cells:

```text
4096 env
2500 batches
save250
policy_only warm start
theta_send=0.90
release threshold=1.60
arm profile unchanged
stage time unchanged
```

## Wave 1 — conditional posture

| Cell | GPU | Seed | Posture | Randomization | Body assist |
|---|---:|---:|---|---|---|
| G1 | 0 | 0 | conditional | current v21 distribution | off |
| G2 | 1 | 1 | conditional | current v21 distribution | off |

Purpose:

- establish whether conditional posture removes universal maximum pitch;
- test training-basin replication;
- compare against frozen B1 and P0 interventions.

There is no formal legacy-versus-scale-only Wave A.

## Wave 2 — hinge-randomization training

| Cell | GPU | Seed | Posture | Randomization | Body assist |
|---|---:|---:|---|---|---|
| G3 | 0 | 0 | selected conditional mechanism | v22 mixture H0–H4 | off |
| G4 | 1 | 1 | selected conditional mechanism | v22 mixture H0–H4 | off |

Purpose:

- determine conditional strategy changes over damping/stiffness/max-force;
- test whether randomization induces appropriate fling versus hold-open behavior;
- measure posture and release-strategy adaptation.

## Wave 3 — body-assist routing

| Cell | GPU | Seed | Posture | Randomization | Body assist |
|---|---:|---:|---|---|---|
| G5 | 0 | 0 | same as G3 | same as G3 | gated on |
| G6 | 1 | 1 | same as G4 | same as G4 | gated on |

Purpose:

```text
G5 vs G3 = body-assist effect, seed0
G6 vs G4 = body-assist effect, seed1
```

The worker may skip Wave 3 if:

- P0-E is unsafe;
- no arm-failure denominator exists;
- body-assist is scientifically irrelevant under the frozen envelope.

Skipping yields a valid posture/randomization round.

---

# 13. Staged-reset ownership

Round-trip:

```text
posture-need hysteresis
height-nominal reference
arm-failure streak/latch
body-assist eligibility/latch
safe-contact streak
support strategy
release strategy
clearance-window state
last bilateral step
release hinge/velocity
rebound/clearance state
task-space derivative warm-up
```

Reject snapshots with:

```text
non-finite state
unsafe release
unidentified body contact
body assist without eligibility
frame collision
pre-send physical crossing
invalid dynamics metadata
```

---

# 14. Route A

Every completed cell:

```text
steps:
250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500

canonical16
strict first-episode traces
```

Mandatory dependent variables:

```text
goal
raw/debounced crossing
supported crossing
hinge at crossing
held hinge max
release hinge/velocity
clearance strategy
clearance success
minimum hinge before root clear
post-release collision
unsafe release
final hinge

pitch/roll command and actual distributions
posture saturation
posture-need precision/recall
arm margins and failure latch

hinge parameter bucket
free-return class
body-assist eligibility/use
body contact force/progress
```

Checkpoint eligibility initial guide:

```text
goal >=14/16
supported crossing >=13/16
unsafe release <=2/16
unauthorized body contact =0
strict evidence valid
```

The worker may relax numerical thresholds with a waiver.

Selection order:

1. integrity and contact safety;
2. goal and supported crossing;
3. ordinary posture pathology;
4. clearance success and rebound collision;
5. hinge-bucket robustness;
6. task time and crossing;
7. body-assist increment where applicable.

---

# 15. Route B

## 15.1 Pooled48

```text
seeds 0,1,2
16 env each
```

## 15.2 Dynamics80

For candidates surviving pooled evaluation:

```text
E0_CORE16
E1_DAMPING16
E2_REBOUND16
E3_RESISTIVE16
E4_COMPOUND16
```

## 15.3 Holdout64

Simplest passing candidate and, if distinct, the body-assist candidate:

```text
seeds 3,4,5,6
16 env each
```

## 15.4 Render

Five scenarios, three cameras:

```text
ordinary middle-height
low handle
high handle
fast rebound
high damping/resistive or compound
```

Questions:

1. Is posture near neutral on ordinary doors?
2. Is posture visibly conditional?
3. Does the policy choose controlled fling, hand hold, or body hold sensibly?
4. Does a fling create clearance without slamming or rebound contact?
5. Does body assist occur only after visible arm/posture difficulty?
6. Is contact on the panel rather than the frame?
7. Does the robot complete without remaining at maximum pitch?

---

# 16. Acceptance profiles

## 16.1 Non-waivable

```text
strict provenance
finite data
legal GPUs
no hidden control
no frame-assist
no unidentified/forbidden body assist
no source/checkpoint/config substitution
```

## 16.2 STANDARD

### Task

```text
pooled goal >=45/48
pooled supported crossing >=44/48
holdout goal >=59/64
holdout supported crossing >=58/64
overspeed <=2/48
```

### Posture

```text
ordinary pitch saturation <=8%
ordinary |pitch| p50 <=0.10 rad
ordinary |pitch| p95 <=0.25 rad
ordinary |roll| p50 <=0.06 rad
ordinary |roll| p95 <=0.18 rad
posture-need precision >=0.65
```

### Clearance

```text
pooled clearance success >=44/48
post-release panel/robot collision =0
unsafe release <=2/48
release velocity p95 <=0.75 rad/s
```

No minimum fling rate.

### Dynamics manifests

```text
E0 goal >=15/16
E1 goal >=13/16
E2 clearance success >=13/16
E3 goal >=12/16
E4 goal >=9/16 or a clean force-routing boundary
```

### Body assist

Only adjudicated if E4 arm-failure denominator >=8/16:

```text
G5-G3 or G6-G4 goal/clearance gain >=3/16
ordinary body assist <=1/16
unauthorized body contact =0
contact p95 <=180 N
contact max <=300 N
```

## 16.3 RELAXED_1

```text
pooled goal >=43/48
pooled supported crossing >=42/48
holdout goal >=56/64
holdout supported crossing >=55/64
overspeed <=3/48

ordinary pitch saturation <=15%
ordinary |pitch| p50 <=0.15 rad
ordinary |pitch| p95 <=0.30 rad
ordinary |roll| p50 <=0.10 rad
ordinary |roll| p95 <=0.22 rad
posture-need precision >=0.50

pooled clearance success >=41/48
unsafe release <=4/48
release velocity p95 <=0.90 rad/s

E0 goal >=14/16
E1 goal >=11/16
E2 clearance success >=11/16
E3 goal >=10/16
E4 report-only boundary accepted
```

## 16.4 WORKER_ADAPTED

Permitted under Section 3.

It must be frozen before the evaluation node it governs. It cannot waive hard safety/integrity gates.

---

# 17. Release taxonomy

## `V22_POSTURE_CLEARANCE_RELEASE`

Requires:

```text
complete pooled48
complete Dynamics80
complete holdout64
complete render
frozen accepted profile
ordinary posture pathology corrected
safe clearance by any valid strategy
```

## `V22_FORCE_ROUTING_RELEASE`

Additionally requires:

```text
valid arm-failure denominator
safe body-assist increment
ordinary body-assist suppression
seed-consistent direction in G5/G6 comparisons
```

## Valid non-release outcomes

```text
V22_RESEARCH_PASS_NO_RELEASE
V22_POSTURE_CONDITIONALLY_USEFUL
V22_POSTURE_MECHANISM_NULL
V22_CONTROLLED_FLING_USEFUL
V22_HOLD_OPEN_DOMINANT
V22_BODY_ASSIST_NOT_TRIGGERED
V22_BODY_ASSIST_UNSAFE
V22_BODY_ASSIST_NO_INCREMENT
V22_DAMPING_BOUNDARY_IDENTIFIED
V22_REBOUND_BOUNDARY_IDENTIFIED
V22_RESISTIVE_BOUNDARY_IDENTIFIED
```

---

# 18. Two-GPU execution schedule

## Phase P0

```text
GPU0:
  posture intervention
  free-return/fixed-torque characterization
  trunk-contact probe

GPU1:
  posture atlas
  deterministic dynamics manifests
  front-thigh probe
```

## Pilot

```text
GPU0:
  conditional-posture pilot

GPU1:
  clearance replay and randomization calibration
```

## Wave 1

```text
GPU0 G1
GPU1 G2
```

## Wave 2

```text
GPU0 G3
GPU1 G4
```

## Wave 3

```text
GPU0 G5
GPU1 G6
```

Evaluation uses paired queues after training processes naturally exit.

Non-render:

```text
no CUDA_VISIBLE_DEVICES
ACCELERATE_TORCH_DEVICE=cuda:N
IsaacLab device=cuda:N
N in {0,1}
```

Render:

```text
CUDA_VISIBLE_DEVICES=N
logical cuda:0
N in {0,1}
```

---

# 19. Implementation files

## Modify

```text
gr00t/rl/envs/door/door_open_a2_base.py
gr00t/rl/isaac_utils/playground/env_rand/door.py
gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py
gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py
gr00t/rl/eval_agent_trl.py
gr00t/rl/config/env/door_open_a2_base.yaml
scriptsFORhuman/a2_piper_longterm_TODO.md
memory/a2-piper/MEMORY.md
```

## Add

```text
gr00t/rl/envs/door/a2_v22_evidence.py

gr00t/rl/tests/test_a2_v22_action_semantics.py
gr00t/rl/tests/test_a2_v22_posture.py
gr00t/rl/tests/test_a2_v22_hinge_randomization.py
gr00t/rl/tests/test_a2_v22_clearance_strategy.py
gr00t/rl/tests/test_a2_v22_body_assist.py
gr00t/rl/tests/test_a2_v22_staged_reset.py
gr00t/rl/tests/test_a2_v22_worker_waiver.py

gr00t/rl/config/ablation/wbmanip/base_v22_G1_posture_seed0.yaml
gr00t/rl/config/ablation/wbmanip/base_v22_G2_posture_seed1.yaml
gr00t/rl/config/ablation/wbmanip/base_v22_G3_randomized_seed0.yaml
gr00t/rl/config/ablation/wbmanip/base_v22_G4_randomized_seed1.yaml
gr00t/rl/config/ablation/wbmanip/base_v22_G5_body_assist_seed0.yaml
gr00t/rl/config/ablation/wbmanip/base_v22_G6_body_assist_seed1.yaml

scriptsFORhuman/v22/
  source_freeze.py
  characterize_hinge_dynamics.py
  build_dynamics_manifests.py
  posture_intervention.py
  posture_atlas.py
  clearance_replay.py
  body_contact_probe.py
  calibrate_rewards.py
  pilot.py
  gate_waiver.py
  formal_launcher.py
  m22.py
  pooled48.py
  dynamics80.py
  holdout64.py
  render.py
  final_analysis.py
  schemas/
```

---

# 20. Required negative tests

Reject:

1. roll/pitch action swap;
2. command mistaken for achieved posture;
3. missing dynamics parameters filled with zero;
4. synthetic `rebound` without a runtime definition;
5. high damping labeled fast rebound without measurement;
6. fling rewarded before valid release;
7. excessive release speed accepted as controlled fling;
8. rebound collision accepted as clearance success;
9. body assist before failure latch;
10. rear thigh/calf/foot assist;
11. frame contact as panel assist;
12. waiver of a hard safety gate;
13. waiver without evidence paths;
14. `WORKER_ADAPTED` frozen after candidate results;
15. GPU outside 0/1;
16. holdout used to reselect checkpoint;
17. adapted cohort compared causally without matched control;
18. active gripper bracing silently implemented in v22.

---

# 21. Long-term TODO patch

The worker must:

1. archive v21-B as `COMPLETED_SCIENTIFIC_NO_RELEASE`;
2. mark v22 posture/clearance/force-routing/randomization as active;
3. correct the old common-1.0-rad corridor-branch diagnosis;
4. preserve realistic PiPER torque as unresolved;
5. add active anti-rebound gripper bracing/re-contact;
6. state that v22 hinge stress ranges are simulation behavior tests, not hardware specifications;
7. preserve pull doors, mirror doors, velocity realism, and student distillation as separate scopes.

---

# 22. Stopping rules

```text
implementation candidates:
  2

pilot attempts after optimizer progress:
  1

Window-A range adjustment:
  1

Window-B profile/matrix adaptation:
  1

Window-C method amendment:
  1

formal process per cell/cohort:
  1
```

Stop immediately for:

```text
non-finite physics
unsafe body-contact cluster
source/config/checkpoint mismatch
GPU violation
evidence fabrication
staged-reset corruption
```

Do not stop merely because:

```text
fling is ineffective on high-damping doors
conditional posture is null
body assist is not triggered
an extreme bucket is unsolved
a numeric scientific gate is missed
```

The worker is authorized to document, waive, adapt, continue, and close with a scientifically valid non-release conclusion.

---

# 23. Ideal v22 behavior

```text
ordinary middle-height door:
  near-zero roll/pitch
  arm-led opening
  controlled fling or quiet hold-open
  no rebound contact

height-extreme or moderately difficult door:
  bounded posture
  improved arm margin
  strategy selected from observed dynamics

fast-rebound door:
  controlled positive release impulse
  sufficient clearance
  no slam or collision

high-damping / high-resistive door:
  hold-open if fling is ineffective
  body assist only after measured arm-plus-posture failure

compound extreme door:
  safe trunk/front-thigh force routing if feasible
  otherwise clean failure boundary, not uncontrolled impact
```
