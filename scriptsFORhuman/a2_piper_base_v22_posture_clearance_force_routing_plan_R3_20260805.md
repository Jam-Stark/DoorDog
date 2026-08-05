# A2+Piper DoorDog — base_v22 Posture Arbitration, Clearance Strategy, Force Routing, and Hinge-Randomization Plan — **Revision 3**

**Plan ID:** `base_v22_posture_clearance_force_routing_v3`
**Execution ID:** `base_v22_execution_v3`
**Date:** 2026-08-05 HKT
**Repository / branch:** `Jam-Stark/DoorDog` / `A2_Piper`
**Supersedes:** `base_v22_posture_clearance_force_routing_v2` / `base_v22_execution_v2`
**Superseded source (unmodified, retained as historical evidence):**
`scriptsFORhuman/v22/a2_piper_base_v22_posture_clearance_force_routing_randomization_plan_20260805.md`
`scriptsFORhuman/v22/a2_piper_base_v22_experiment_manifest_revision2_20260805.yaml`
**Scientific base:** v21-B closure commit `89c6538ad274ab6d1256389e3f2b3ceefd68d98a`, or a direct descendant whose additional changes are repository housekeeping only
**Legal physical GPUs:** `0, 1` only
**GPU2–7:** unavailable. GPU2/GPU3 are leased to pull-v0 by the 2026-08-04 lease amendment; GPU4–7 are occupied by another tenant. **An idle reading is not a lease.**
**Warm start:** v21-B B1 release checkpoint, `policy_only`
**Warm-start path:** `logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal/B1/model_step_000500.pt`
**Warm-start SHA-256:** `d2732c148dd3176abafbf3a5c9425d4a34c17b352e8362bbfb38c8ac960d8421` *(verified byte-for-byte on the worker host, 2026-08-05)*
**Warm-start saved-config SHA-256:** `70ccd1b43a07574d36702947c706b5ef80184fffd0d2853cf188c9286a959a79`
**Runtime URDF:** `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf`
**URDF SHA-256:** `d02cdacdcd4aaf1480b52ba9a6a62f5e9bbd040036a796154dbff70d1391a1d5`
**Frozen A2_Base policy SHA-256:** `783c65386ce49127a17ec261794ed3c7002309e293e3cb88562dee922c894b1b`

**Revision-3 basis:** an independent local audit executed on the production host (which can run IsaacLab and read resolved configs) found two revision-2 defects that would have blocked the round, and one release-gate drift. Revision 3 repairs exactly those three items and changes nothing else in the scientific direction.

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
FORMAL_TRAINING_READY_NOW           = false
LEGAL_PHYSICAL_GPUS                 = [0, 1]
THETA_SEND                          = 0.90 rad, frozen for the complete v22 causal round
RELEASE_HINGE                       = 1.60 rad, frozen
ARM_EFFORT_PROFILE                  = unchanged from v21-B (ARM_V20)
PIPER_VELOCITY_LIMITS               = unchanged
STAGE_TIME                          = unchanged unless a worker-authorized research-only diagnostic
ACTION_DIMENSION                    = unchanged (12D)
ACTOR_OBSERVATION_DIMENSION         = unchanged

POSTURE_GATE_STATE                  = P0_CALIBRATION_REQUIRED
HINGE_RANDOMIZATION_STATE           = P0_D_REQUIRED_UNFROZEN
RELEASE_GOAL_POOLED48               = 46/48, non-waivable for a release claim
MANDATORY_FORMAL_BUDGET             = ~34 h (Wave 1 + Wave 2)
MAXIMUM_FORMAL_BUDGET               = ~51 h (incl. conditional Wave 3)
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

## 0.2 Fling is a legitimate strategy (retained from revision 2)

v21-B exposed uncontrolled behavior of the form:

```text
hard shove -> premature hand loss -> large inertial coast
```

The first v22 draft overcorrected by suppressing post-release coast in general. That is rejected and remains rejected.

For a spring-loaded door, a positive release impulse can be desirable because it creates angular clearance and reduces the probability that the panel rebounds into the robot during traversal. v22 distinguishes:

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

## 0.3 Future active anti-rebound gripper bracing — long-term TODO, not v22 scope

A separate future idea is:

> after release or partial release, use the gripper/palm to maintain light compliant contact with the door panel or re-contact the panel to arrest rebound.

Not implemented in v22: it introduces a new contact-mode transition, compliant/force-control requirements, finger-safety questions, and a new student-observability burden.

The worker must append this exact research item to `scriptsFORhuman/a2_piper_longterm_TODO.md` under the parking-lot / future-research section:

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

Changing trunk roll/pitch changes the arm configuration `q`, the directional Jacobian, joint-position and joint-effort margins, gravity load on the mounted arm, and centre-of-mass projection / foot-load distribution.

With an arm reach near `0.63 m`, a `0.4 rad` body rotation can redirect approximately:

```text
0.50    * sin(0.4) = 0.195 m
0.62675 * sin(0.4) = 0.244 m
```

comparable to the `0.85–1.10 m` handle-height span. This explains why maximum pitch is a powerful universal shortcut.

Illustrative force example:

```text
40 N tangential force
0.55 m effective moment arm -> 22 N*m
0.40 m effective moment arm -> 16 N*m
```

A posture reducing the effective moment arm by `0.15 m` reduces the required joint moment by ~`6 N*m` (~27%) before gravity and multi-joint coupling.

These calculations justify posture as a capability lever. They do **not** prove `+0.4 rad` is optimal, and they do not make the simulated 100 N·m arm limits hardware-realistic.

## 0.5 v21-B constraints inherited unchanged

- higher `theta_send` alone did not produce monotonic behavior;
- several high-theta policies learned high-yaw, impulse, release, and coast strategies;
- the v21-B arm-effort axis was right-censored and did not establish a realistic PiPER profile;
- implicit-PD torque evidence is estimate-only;
- no v21-B policy passed complete Route B;
- v22 must not claim true PiPER torque capability.

`theta_send` is held at `0.90 rad` so posture, hinge randomization, release strategy, and body assistance are not confounded by another send-threshold dose.

## 0.6 What revision 3 changes, and the evidence for each change

Revision 3 is a **calibration and admissibility repair**. It preserves every scientific commitment of revision 2.

### 0.6.1 Posture gates were uncalibrated and would have blocked the round

Revision 2 pre-registered absolute posture thresholds (`ordinary |pitch| p50 <= 0.10 / 0.15`, `|roll| p50 <= 0.06 / 0.10`, `roll saturation <= 8% / 15%`).

Diagnostic measurement on the exact frozen warm start `B1@500`, over all available frames of the delivered v21-B pooled traces:

| quantity | measured | R2 STANDARD | R2 RELAXED_1 |
|---|---|---|---|
| \|pitch\| p50 | **0.2358 rad** | ≤0.10 | ≤0.15 |
| \|pitch\| p95 | **0.3524 rad** | ≤0.25 | ≤0.30 |
| \|roll\| p50 | **0.3840 rad** | ≤0.06 | ≤0.10 |
| \|roll\| p95 | **0.4296 rad** | ≤0.18 | ≤0.22 |
| roll saturation at ≥0.95×0.40 | **56.9%** | ≤8% | ≤15% |

All six posture gates fail on the warm start in **both** profiles; roll p50 by a factor of 6.4.

**Provenance caveat, binding on the worker.** These figures were computed from the trace fields `root_roll` / `root_pitch`, which are **achieved trunk angles, not commands.** Revision 2 §20 negative test #2 already forbids treating a command as an achieved value, and that prohibition is retained and extended: the numbers above are **diagnostic only** and are **not** the baseline against which gates bind. They are not like-for-like with the intended ordinary/non-need denominator because `posture_need` does not exist yet, and they are not command-side.

The repair is §7.6 (`P0-POSTURE-BASELINE`) plus §16.2 warm-start-relative, same-denominator gates.

Historical context that makes the repair necessary rather than cosmetic: posture-economy shaping is a **closed dead end** in this project (v16 at −0.15 and v17 at −1.5 ≈ 12% of income both failed to move posture usage; the P2 probe proved pitch is load-bearing, with pitch-clamped goal collapsing to 2/16). A pre-registered demand for a 6.4× roll reduction reopens that dead end as a release blocker.

### 0.6.2 The primary new randomization axis has no plumbing and rests on an unverified constant

Revision 2 froze five bucket ranges (H0–H4) defined by `damping_native`, anchored to the §2.2 claim "hinge drive damping = 50.0". Source audit on the host found:

- hinge damping is obtained at runtime from the USD drive attribute (`hinge_drive.GetDampingAttr().Get()`, `gr00t/rl/isaac_utils/playground/env_rand/door.py:971`) — it is **not** a repo constant and could not be verified statically;
- there is **no `rand_hinge_drive_damping`**; the metadata assignment block (`door.py:1102-1117`) binds `rand_hinge_drive_stiffness` and `rand_hinge_drive_max_force`, but not damping — so per-env damping randomization is **unbuilt**;
- damping and stiffness are **absent from accepted task traces** (traces carry `door_hinge_drive_max_force`, `door_weight`, `door_handle_height`), so bucket membership cannot be audited even after randomization is added.

If the true asset damping is not ≈50, all five bucket ranges are mis-centred. The repair is §5 (ranges unfrozen), §5A (exact plumbing requirements), and §6 (`P0-D` reads the runtime attributes first).

### 0.6.3 Release-goal drift

Revision 2 set pooled48 goal at `>=45/48`, below the standing north-star red-line of `>=46/48`. Restored in §16 and made non-waivable for a release claim, with an explicit research-continuation path below it.

### 0.6.4 What the audit confirmed as correct and left untouched

- warm-start SHA-256 verified byte-for-byte on the host;
- GPU `[0, 1]` is the correct lease;
- release-velocity gate `p95 <= 0.75 rad/s` — measured `0.486` on the warm start, 35% headroom;
- `post-release panel/robot collision = 0` — measured `0/43` on the warm start; this zero-tolerance gate is genuinely satisfiable and is retained;
- `overspeed <= 2/48` — measured base rate ≈2.9%; tight but survivable, with RELAXED_1 at ≤3/48;
- the body-assist denominator guard (§9, §16) is correctly designed and is retained unchanged.

---

# 1. Scope

## 1.1 In scope

1. High-level roll/pitch action semantics and telemetry.
2. Commanded versus achieved trunk roll/pitch, reported separately at every node.
3. Conditional posture use.
4. Live-grasp posture/workspace/relative-wrench diagnostics.
5. Controlled fling, hold-open, and body-support clearance strategies.
6. Hinge damping, stiffness/rebound, and max-force/resistive-torque randomization — **including the source plumbing required to make damping a real random variable**.
7. Safe trunk/front-thigh body assistance.
8. Route-A all-checkpoint evaluation.
9. Selected pooled48, deterministic dynamics manifests, holdout64, and strict render.
10. Worker-authorized bounded gate adaptation and exploratory continuation.
11. Two-GPU sequential execution.
12. **Posture-gate calibration against the frozen warm start (new in revision 3).**

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
- direct root teleport, hidden DLS, scripted train-time action override, or fallback controller;
- restoring the removed legacy/scale-only Formal Wave A.

---

# 2. Source facts that the implementation must preserve

## 2.1 Current posture action

The shared A2 door config exposes a body pitch/roll scale of `0.40 rad`
(`gr00t/rl/envs/base_task/a2_base.py`, `body_pitch_roll_scale`, default `0.4`; applied at the `raw_base_action[:, 3:5]` slice).

The worker must identify the exact action ordering and produce a typed mapping. No v22 source may use anonymous posture indices.

## 2.2 Current door-drive implementation — corrected in revision 3

Verified at the v21-B source:

```text
DoorSpawnerCfg.hinge_drive_max_force_range default = (2.5, 4.5)
  gr00t/rl/isaac_utils/playground/env_rand/door.py:68

scenario_cfg override used by v20/v21 = (2.5, 12.0)
  gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py:587
  delivered v21-B evidence contains values up to ~11.4905 N*m

hinge drive stiffness: randomizable
  cfg.rand_hinge_drive_stiffness            (door.py:106)
  bound from metadata["hingeDriveStiffness"] (door.py:1117)

hinge drive damping: READ ONLY, NOT RANDOMIZABLE
  metadata["hingeDriveDamping"] = hinge_drive.GetDampingAttr().Get()  (door.py:971)
  consumed into self.door_hinge_drive_damping                          (door_open_a2_base.py:6347)
  exposed internally as "hinge_damping"                                (door_open_a2_base.py:8627)
  NO cfg.rand_hinge_drive_damping exists
  NOT bound in the metadata assignment block                           (door.py:1102-1117)

accepted task traces carry:
  door_hinge_drive_max_force, door_handle_drive_max_force,
  door_weight, door_handle_height, door_hinge_joint_pos, door_hinge_joint_vel
accepted task traces DO NOT carry:
  hinge damping, hinge stiffness
```

**Consequence.** The revision-2 statement "hinge drive damping = 50.0" is an unverified runtime value, not a repo constant. It must be read from spawned assets by `P0-D` and published before any bucket range is chosen.

The current code has no independent `rebound` random variable. Rebound is an emergent result of hinge stiffness, hinge damping, hinge drive max force, door inertia/mass and geometry, current angle and angular velocity, and drive target. The worker must not create or report a synthetic scalar named `rebound` without defining its runtime measurement.

## 2.3 Drive-response model to verify

The worker must verify, rather than assume, that the effective drive approximately follows:

```text
tau_drive_raw = - stiffness * (theta - theta_target) - damping * omega
tau_drive     = clip(tau_drive_raw, -max_force, +max_force)
```

The exact IsaacLab/PhysX units and angular convention must be written to the source audit. Until verified, damping and stiffness are called `hinge_drive_damping_native` and `hinge_drive_stiffness_native`. `hinge_drive_max_force` remains reported as configured torque-cap units.

---

# 3. Worker adaptation and gate-waiver authority

The worker is explicitly authorized to continue scientifically useful execution when a non-safety threshold is too strict or poorly calibrated.

## 3.1 Hard non-waivable gates

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
pooled48 goal < 46/48 relabelled as a release   (revision 3, see §16.1)
```

## 3.2 Waivable gates

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

Every waiver must create `logs_eval/base_v22/locks/V22_GATE_WAIVER_<ID>.json` with:

```text
schema, waiver_id, timestamp_hkt, worker_identity,
original_gate, observed_value,
decision = RELAX | SUSPEND | REPLACE | BYPASS_FOR_EXPLORATION,
replacement_gate, evidence_paths, scientific_reason,
safety_impact, claim_impact, affected_nodes, expiration_node,
source/config hashes
```

## 3.4 Exploration may continue after a failed pilot

A failed scientific pilot does not automatically block later training. The worker may issue `EXPLORATORY_CONTINUATION` and continue one or more formal waves when runtime and evidence are valid, no hard safety gate failed, the failure itself is scientifically informative, and the continued cells can answer a declared question.

Such cells cannot be labelled release-admitted solely because the pilot was bypassed. They may still become release candidates if later frozen pooled/holdout/render gates are satisfied.

## 3.5 Adaptation windows

### Window A — after source audit and dynamics characterization

```text
hinge randomization ranges
bucket weights
reward calibration scales
posture need thresholds
fling eligibility/velocity soft bands
```

### Window B — after pilot and before the first formal optimizer update

```text
choose STANDARD, RELAXED_1, or WORKER_ADAPTED profile
prune uninformative cells
activate exploratory continuation
adjust numerical acceptance thresholds
```

### Window C — after Wave 1, before Wave 2

One method amendment if Wave 1 reveals a singular, well-supported failure such as posture need never activating, posture need activating on every ordinary episode, a numerically inactive controlled-fling reward, or a null/impossible randomization bucket.

The amendment creates a new `ADAPTED_COHORT`. Direct causal comparisons with pre-amendment cells are forbidden unless a matched control is rerun. No more than one Window-C amendment is allowed.

## 3.6 Worker-created acceptance profile

`WORKER_ADAPTED` is permitted if written before the relevant formal or Route-B data are inspected. It must state the measured baseline basis, the uncertainty or observed distribution, the new thresholds, why STANDARD/RELAXED_1 were unsuitable, and which release claims remain valid.

Hard integrity and contact-safety gates remain unchanged. `WORKER_ADAPTED` may **not** lower pooled48 goal below 46/48 for a release claim (§16.1).

## 3.7 Planned admission nodes do not consume adaptation budget — new in revision 3

The following are **planned admission work**, not adaptations, and consume **no** `method_amendments_max`, **no** worker waiver budget, and **no** Window-C amendment:

```text
P0-POSTURE-BASELINE          posture baseline + denominator adjudication + gate freeze  (§7.6)
P0-D range selection         hinge runtime baseline + dynamics probe + range freeze     (§6)
```

Rationale: both nodes exist precisely because revision 2 pre-registered values that could not be known without running on the host. Charging the worker's scarce adaptation budget for executing the planned repair would reproduce the blocking failure this revision removes.

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

# 5. v22 randomization — ranges unfrozen pending P0-D

## 5.1 Variables randomized during v22 training

### Already-established axes retained

```text
handle height: Uniform[0.85, 1.10] m
door mass:     Uniform[80, 160] kg
```

These remain independent variables but are not the new scientific intervention.

### New hinge axes

```text
hinge_drive_damping_native      <- requires new plumbing, see §5A
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

## 5.2 Bucket ranges are UNFROZEN

```text
hinge_randomization_state: P0_D_REQUIRED_UNFROZEN
final_bucket_ranges:       null
freeze_artifact:           logs_eval/base_v22/locks/V22_HINGE_RANGE_FREEZE.json
```

No formal config may be materialized before `V22_HINGE_RANGE_FREEZE.json` exists (§20 negative test 24).

The worker is authorized to select the final H0–H4 ranges and mixture weights from measured `P0-D` response (§6). This planned selection consumes no Window-C amendment and requires no gate waiver.

The revision-2 numeric table is retained only as **Appendix A**, labelled
`PROVISIONAL_CANDIDATE_RANGES_NOT_AUTHORIZED_FOR_FORMAL_TRAINING`.

## 5.3 Global worker-adjustable bounds

Every selected value must stay within:

```text
damping:   [10, 200]
stiffness: [0.5, 30]
max force: [2.5, 24] N*m
mass:      [80, 180] kg
height:    [0.85, 1.10] m
```

The worker may exceed `160 kg` only in an explicit stress-test manifest, never in the default training distribution without a Window-A amendment.

## 5.4 Why damping and fast rebound are separate

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

The final report must preserve this distinction. A row may not be labelled `FAST_REBOUND` on parameter values alone — only on measured free-return response (§6.3, §20 negative test 5).

## 5.5 Deterministic evaluation manifests

`E0_CORE16`, `E1_DAMPING16`, `E2_REBOUND16`, `E3_RESISTIVE16`, `E4_COMPOUND16` are constructed **after** `P0-D`, from the frozen ranges, as balanced 16-row manifests over the response classes they are named for. Each manifest is hashed and immutable after Window A. Candidate numeric grids are in Appendix A and are not authorized until frozen.

---

# 5A. Hinge damping randomization — exact implementation requirements (new in revision 3)

## 5A.1 `gr00t/rl/isaac_utils/playground/env_rand/door.py`

```text
add DoorSpawnerCfg.hinge_drive_damping_range: tuple[float, float]
add DoorSpawnerCfg.rand_hinge_drive_damping: Optional[float]
validate finite, non-negative values; reject NaN/Inf/negative with a named error
sample or accept the fixed value on the same code path as
  rand_hinge_drive_stiffness / rand_hinge_drive_max_force
set the runtime USD drive damping from the sampled/fixed value
  (write path symmetric to the existing hinge_drive.GetDampingAttr() read at :971)
serialize damping into the exported metadata dict alongside hingeDriveStiffness
restore damping from metadata in the assignment block at :1102-1117
  cfg.rand_hinge_drive_damping = metadata["hingeDriveDamping"]
```

## 5A.2 `gr00t/rl/scripts/generate_door_assets.py`

```text
generate and export hinge drive damping per asset
include damping in metadata.json
keep stiffness and max force exports unchanged
```

## 5A.3 `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`

```text
bind deterministic damping, stiffness, and max force per scenario
extend the existing tuple identity check at :142 and the variant construction at :188
  to carry damping alongside handle height / weight / hinge max force
validate exact ordered values and hashes for every deterministic manifest row
```

## 5A.4 `gr00t/rl/envs/door/door_open_a2_base.py` and the v22 evidence/export path

Add exact per-episode and per-step fields:

```text
door_hinge_drive_damping_native
door_hinge_drive_stiffness_native
door_hinge_drive_max_force_nm
door_hinge_drive_target_rad          (if available; N/A never 0 when absent)
measured_free_return_class
registered_hinge_bucket
```

`self.door_hinge_drive_damping` already exists at `door_open_a2_base.py:6317/6347`; the work is to export it into the accepted trace/record schema, not to recompute it.

## 5A.5 Binding rule

**No accepted record may infer bucket membership from a scenario name alone.** The runtime values must match the signed scenario manifest, row by row, and a mismatch is an evidence failure, not a warning.

---

# 6. Mandatory dynamics characterization before training — `P0-D`

## 6.0 Runtime baseline first

Before any probe, `P0-D` must read, from **actually spawned assets**:

```text
hinge_drive.GetDampingAttr().Get()
hinge_drive.GetStiffnessAttr().Get()
hinge_drive.GetMaxForceAttr().Get()
```

and publish the exact values, their units, and the authority for those units. Revision 2's assumed value of `50.0` is treated as unverified until this artifact exists.

Output: `V22_HINGE_RUNTIME_BASELINE.json`.

## 6.1 Free-return probe

For each registered hinge tuple: place the door at `1.20 rad`, set angular velocity to zero, remove robot contact, simulate the free return. Record:

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

Apply registered constant opening torques `5, 10, 15, 20 N*m` for a fixed interval and record hinge progress, steady angular velocity, and drive-cap activity. This is a door-characterization experiment, not a policy or hardware claim.

## 6.3 Attribution and behavioral class labels

Run damping/stiffness/max-force attribution checks: vary one native parameter at a time and confirm the response moves in the predicted direction of the §2.3 model. Then classify every row from measured response:

```text
CORE
HIGH_DAMPING
FAST_REBOUND
HIGH_RESISTIVE
COMPOUND
UNCLASSIFIED
```

## 6.4 Outputs and freeze

```text
V22_HINGE_RUNTIME_BASELINE.json
V22_HINGE_DYNAMICS_PROBE.json
V22_HINGE_RANGE_FREEZE.json
```

Only after these results may the worker freeze H0–H4 ranges and mixture weights. If the parameter ranges do not produce the intended response classes, the worker adjusts them within §5.3 bounds and records the basis in the freeze artifact.

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

Commanded and achieved posture must be stored under distinct, unambiguous keys and reported separately at every node. Conflating them is a rejected evidence class (§20 negative test 2).

## 7.2 Height-conditioned nominal posture

Use valid live-grasp states, not detached static reachability.

```text
pitch grid = [-0.25, -0.10, 0.00, 0.10, 0.25]
roll  grid = [-0.15,  0.00, 0.15]
```

Select the minimum-norm posture within 95% of the best valid relative directional-wrench capacity satisfying joint-position margin ≥0.10, support margin ≥0.03 m, TCP error ≤0.03 m, and no collision.

Bounds: `|pitch_nominal| <= 0.15 rad`, `|roll_nominal| <= 0.10 rad`. If zero posture is within 5% of the best value, select zero.

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

posture_need = max(height_need, workspace_need, force_need, tracking_need)

hysteresis:
  ON:  score >=0.70 for 5 steps
  OFF: score <=0.35 for 10 steps
```

## 7.4 Reward semantics

### Excess posture penalty

```text
-(1 - posture_need) * Huber(command - height_nominal)

deadbands: pitch 0.05 rad, roll 0.04 rad
```

### Saturation penalty

```text
soft boundaries: pitch 0.30 rad, roll 0.20 rad
physical command scale remains 0.40 rad
```

### Feasibility reward

Reward the result, not posture magnitude:

```text
posture_need * valid_hold * positive_hinge_progress
             * arm_margin_quality * arc_tracking_quality
```

## 7.5 Calibration

Registered scales `[0.25, 0.5, 1, 2, 4, 8]`. Target income ranges are guidance, not hard blockers:

```text
ordinary excess-posture penalty:     1–5% of absolute episode reward
hard-door feasibility reward:        1–6% of positive income
continuous 0.4-rad saturation penalty: 2–8% of absolute episode reward
```

Worker may select the nearest lower stable scale and record a waiver.

## 7.6 `P0-POSTURE-BASELINE` — mandatory admission node (new in revision 3)

### 7.6.1 Raw producer

```text
checkpoint:   the exact frozen B1@500 warm start
              sha256 d2732c148dd3176abafbf3a5c9425d4a34c17b352e8362bbfb38c8ac960d8421
optimizer:    no update
intervention: none for the primary baseline
posture_need: v22 implementation active for TELEMETRY ONLY (no reward, no action effect)
```

The baseline must be produced by the same evidence path that will later produce the gated quantities, so that baseline and candidate are same-denominator by construction.

### 7.6.2 Required denominator

```text
ordinary_need_negative_frame =
      scenario belongs to E0_CORE / ordinary16
  AND stage is OPEN or SWING
  AND valid task-space/reference state
  AND no body-assist eligibility and no body contact
  AND not a terminal-only frame
  AND posture_need_score <= 0.35
```

### 7.6.3 Required published content

`V22_POSTURE_BASELINE.json` must publish:

```text
total ordinary frames
ordinary_need_negative frames
contributing episode count
fraction of ordinary frames classified as need-negative
per-episode and pooled command distributions
commanded AND achieved pitch/roll, separately
command saturation rates
exact posture_need component prevalences
  (height_need, workspace_need, force_need, tracking_need, individually)
source / checkpoint / config hashes
```

### 7.6.4 Denominator adjudication

Binding posture gates require at least:

```text
contributing episodes           >= 8/16
ordinary_need_negative frames   >= 1000
```

If either denominator is smaller:

```text
posture_gate_state = REPORT_ONLY_INSUFFICIENT_DENOMINATOR
```

and posture gates **must not block** the pilot, formal training, Route A, Route B, or a research-complete result.

If `ordinary_need_negative` is below 25% of valid ordinary opening frames:

```text
posture_need_state = POSTURE_NEED_OVERACTIVE_OR_VACUOUS
```

The worker may continue, but `posture_need` precision and ordinary-posture release claims become report-only until corrected through the already-authorized adaptation window.

Output: `V22_POSTURE_DENOMINATOR_ADJUDICATION.json`.

### 7.6.5 Gate freeze

The adjudicated baseline values become `B0_same_denominator_*` and are frozen into
`V22_POSTURE_GATE_FREEZE.json` together with the resolved gate arithmetic of §16.2.

**No formal config may be promoted before `V22_POSTURE_GATE_FREEZE.json` exists**, unless the worker explicitly selects `POSTURE_GATES_REPORT_ONLY` through a signed waiver artifact (§3.3).

### 7.6.6 Circularity rule for `posture_need` precision

`posture_need` precision may be **binding** only if its positive/negative labels are defined independently, through the frozen causal-intervention experiment of `P0-B` (zero / clamped posture versus unchanged policy). If the label is derived from the same signals used to compute `posture_need`, precision is circular and must remain **report-only**.

---

# 8. Clearance-strategy arbitration

## 8.1 Three permitted strategies

```text
FLING_CLEARANCE:      release with positive angular velocity; door remains clear during traversal
HAND_HOLD_CLEARANCE:  gripper maintains valid support until root clears the frame
BODY_HOLD_CLEARANCE:  approved body contact maintains support after hand release
```

The policy is not required to use fling on every door.

## 8.2 Release and clearance events

```text
last bilateral step, release hinge, release angular velocity, release strategy,
root-clear step, minimum hinge after release and before root clear,
peak closing velocity, panel/robot contact after release, door-frame contact, goal
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

The historical release threshold of `1.60 rad` remains the main target; `1.45 rad` is only the minimum typed eligibility boundary.

## 8.4 Safe clearance outcome

Until the root clears the frame:

```text
no door-panel collision with the robot
no door-frame collision
minimum hinge >=1.10 rad
goal remains achievable
```

If exact geometry produces a better collision-clearance metric, the worker may replace the `1.10 rad` proxy in Window A and retain it as report-only.

## 8.5 Fling velocity bands

```text
CORE:                                   release omega 0.10–0.40 rad/s
FAST_REBOUND:                           release omega 0.20–0.55 rad/s
HIGH_DAMPING / HIGH_RESISTIVE / COMPOUND: no minimum; soft maximum 0.55 rad/s
global soft maximum:                    0.75 rad/s
```

A safe episode is not failed merely because release velocity is below the band. The band is a shaping and interpretation tool. *(Audit note: the warm start measures release-velocity p95 = 0.486 rad/s, so the 0.75 global maximum has ~35% headroom.)*

## 8.6 Reward

```text
r_clearance_success: one-shot when the root clears the frame and the selected strategy avoided collision
r_controlled_fling:  only when FLING_CLEARANCE is eligible and release velocity lies in the response-conditioned band
r_unsafe_release:    premature support loss, excessive release speed, collision, or rapid rebound into robot
```

Positive post-release hinge motion is allowed and may be useful. **There is no generic coast penalty.**

## 8.7 Fling is allowed to fail on hard doors

For HIGH_DAMPING, HIGH_RESISTIVE, or COMPOUND doors a low fling rate is acceptable, provided the policy uses hand-hold or body-hold clearance and maintains safety and task success.

---

# 9. Body-assist semantics — preserved unchanged

## 9.1 Approved bodies

```text
approved:  trunk, FL_thigh, FR_thigh
forbidden: rear thighs, calves, feet, arm links, gripper links,
           sensor/head bodies, door frame, handle
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

persistence:
  arm failure            >=15 steps
  posture assist attempted >=10 steps

then body_assist_eligible = true
```

Posture must be attempted before body assist. Escalation is never selected from door mass alone.

## 9.3 Safe contact

```text
approved body contacts panel
opening-aligned force >0
relative impact speed <=0.20 m/s
no frame contact
no forbidden-body panel contact
five stable steps establish body support
```

## 9.4 Reward and safety

```text
body assist reward: only after eligibility, only for safe contact, only for positive hinge progress
impact penalty:     contact >150 N, impact speed >0.20 m/s, door velocity >0.60 rad/s

hard termination (first runtime): contact peak >300 N, frame collision,
                                  forbidden-body assist, fall / bad orientation
```

The worker may adjust 150/300 N after the safe-contact probe, but may not waive body identity or frame-collision safety.

## 9.5 Insufficient denominator is a valid result

If the arm-failure denominator is insufficient:

```text
body_assist_result = BODY_ASSIST_NOT_TRIGGERED
```

This is a valid scientific result and must not block posture/randomization completion.

Torque evidence remains estimate-only (`ESTIMATE_ONLY_ACTUAL_PHYSX_DRIVE_FORCE_UNAVAILABLE`); no true PiPER hardware-force claim is permitted from v22 under any outcome.

---

# 10. Required pretests

| id | content | blocking? |
|---|---|---|
| `P0-A` | action semantics; produce `V22_ACTION_SEMANTICS.json` proving roll/pitch command order, scaling, units, achieved-posture telemetry | yes |
| `P0-B` | frozen posture interventions on identical scenario manifests: legacy / zero posture / clamp to 0.15,0.10 / height-conditioned nominal, over `ordinary16`, `height16`, `hard16`. **Supplies the independent labels for §7.6.6** | yes |
| `P0-C` | live-grasp posture atlas: relative directional-wrench and support-margin | yes |
| `P0-D` | hinge runtime baseline + free-return + fixed-torque + attribution + class labels + range freeze (§6) | yes, blocks formal materialization |
| `P0-E` | safe trunk/front-thigh contact; four-env probe each. Failure disables body-assist cells but does not block posture/randomization training | partial |
| `P0-F` | clearance strategy replay on frozen B1: classify existing episodes as fling / hand hold / unsafe release; verify clearance-window telemetry and reward calibration | yes |
| `P0-POSTURE-BASELINE` | §7.6: baseline, denominator adjudication, gate freeze | blocks formal promotion unless `POSTURE_GATES_REPORT_ONLY` is signed |

---

# 11. Pilot

```text
cell: conditional posture + common clearance semantics
GPU0, 256 env, 750 batches, save250
current door distribution
body assist off
```

GPU1 concurrently finishes hinge characterization and deterministic manifests.

## Pilot classifications

```text
PILOT_FULL:
  goal >=12/16
  supported crossing >=14/16
  ordinary posture improvement meets STANDARD (§16.2) if gates are binding
  unsafe release <=2/16
  non-finite =0

PILOT_PARTIAL:
  goal >=10/16
  supported crossing >=12/16
  ordinary posture improvement meets RELAXED_1 (§16.3) if gates are binding
  unsafe release <=4/16
  non-finite =0

PILOT_NULL:
  valid evidence below PARTIAL
```

If `posture_gate_state = REPORT_ONLY_INSUFFICIENT_DENOMINATOR`, the posture clause is dropped from the pilot classification and the remaining clauses decide.

## Responses

```text
FULL:    proceed to all formal waves
PARTIAL: proceed under RELAXED_1 or WORKER_ADAPTED
NULL:    worker may continue exploratory posture training,
         skip directly to randomization research with the warm start,
         or issue one method amendment
```

No scientific pilot outcome automatically terminates v22.

---

# 12. Formal matrix — no legacy Wave A

All cells: `4096 env, 2500 batches, save250, policy_only warm start, theta_send=0.90, release 1.60, arm profile unchanged, stage time unchanged`.

## Wave 1 — conditional posture

| Cell | GPU | Seed | Posture | Randomization | Body assist |
|---|---:|---:|---|---|---|
| G1 | 0 | 0 | conditional | current v21 distribution | off |
| G2 | 1 | 1 | conditional | current v21 distribution | off |

Purpose: establish whether conditional posture removes universal maximum pitch; test basin replication; compare against frozen B1 and the P0-B interventions.

There is no formal legacy-versus-scale-only Wave A.

## Wave 2 — hinge-randomization training

| Cell | GPU | Seed | Posture | Randomization | Body assist |
|---|---:|---:|---|---|---|
| G3 | 0 | 0 | selected conditional mechanism | v22 mixture H0–H4 (frozen by P0-D) | off |
| G4 | 1 | 1 | selected conditional mechanism | v22 mixture H0–H4 (frozen by P0-D) | off |

## Wave 3 — body-assist routing (conditional)

| Cell | GPU | Seed | Posture | Randomization | Body assist |
|---|---:|---:|---|---|---|
| G5 | 0 | 0 | same as G3 | same as G3 | gated on |
| G6 | 1 | 1 | same as G4 | same as G4 | gated on |

```text
G5 vs G3 = body-assist effect, seed0
G6 vs G4 = body-assist effect, seed1
```

The worker may skip Wave 3 if `P0-E` is unsafe, no arm-failure denominator exists, or body assist is scientifically irrelevant under the frozen envelope. Skipping yields a valid posture/randomization round.

---

# 13. Staged-reset ownership

Round-trip:

```text
posture-need hysteresis, height-nominal reference,
arm-failure streak/latch, body-assist eligibility/latch, safe-contact streak,
support strategy, release strategy, clearance-window state,
last bilateral step, release hinge/velocity, rebound/clearance state,
task-space derivative warm-up,
registered hinge bucket and measured free-return class
```

Reject snapshots with:

```text
non-finite state, unsafe release, unidentified body contact,
body assist without eligibility, frame collision, pre-send physical crossing,
invalid dynamics metadata, hinge parameters absent from the record
```

---

# 14. Route A

Every completed cell, steps `250 … 2500` (10 checkpoints), `canonical16`, strict first-episode traces.

Mandatory dependent variables:

```text
goal, raw/debounced crossing, supported crossing, hinge at crossing,
held hinge max, release hinge/velocity, clearance strategy, clearance success,
minimum hinge before root clear, post-release collision, unsafe release, final hinge

pitch/roll COMMAND and ACHIEVED distributions, reported separately
posture saturation (command side)
posture-need precision/recall, flagged binding or report-only per §7.6.6
arm margins and failure latch

hinge parameter bucket (from runtime values, not scenario name)
free-return class
body-assist eligibility/use, body contact force/progress
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

Selection order: integrity and contact safety; goal and supported crossing; ordinary posture pathology; clearance success and rebound collision; hinge-bucket robustness; task time and crossing; body-assist increment where applicable.

---

# 15. Route B

```text
15.1 Pooled48    seeds 0,1,2; 16 env each
15.2 Dynamics80  E0_CORE16, E1_DAMPING16, E2_REBOUND16, E3_RESISTIVE16, E4_COMPOUND16
15.3 Holdout64   simplest passing candidate and, if distinct, the body-assist candidate; seeds 3,4,5,6; 16 env each
15.4 Render      five scenarios x three cameras:
                 ordinary middle-height, low handle, high handle,
                 fast rebound, high damping/resistive or compound
```

Render questions:

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
legal GPUs (physical 0/1 only)
no hidden control
no frame-assist
no unidentified/forbidden body assist
no source/checkpoint/config substitution

pooled48 goal >= 46/48 for any release claim
```

The pooled48 release-goal gate is restored to the standing north-star red-line and is **non-waivable for a formal release claim**. Neither `RELAXED_1` nor `WORKER_ADAPTED` may lower it, and a waiver may not relabel a result below 46/48 as `V22_POSTURE_CLEARANCE_RELEASE` or `V22_FORCE_ROUTING_RELEASE`.

The worker **may** continue evaluation, adaptation, rendering, and scientific analysis below 46/48 by issuing:

```text
RESEARCH_CONTINUATION_BELOW_RELEASE_GOAL
```

Other behavior and fluency thresholds remain worker-adaptable under §3.

## 16.2 STANDARD

### Task

```text
pooled goal              >=46/48        (non-waivable for release)
pooled supported crossing >=44/48
holdout goal              >=59/64
holdout supported crossing >=58/64
overspeed                 <=2/48
```

### Posture — same-denominator, warm-start-relative

All posture gates are evaluated on the **same `ordinary_need_negative` denominator** as the frozen `B0` baseline of §7.6, on the **command** side, and are binding only when `posture_gate_state = BINDING`.

```text
pitch-command |p50|   <= 0.85 * B0_same_denominator_pitch_p50
roll-command  |p50|   <= 0.80 * B0_same_denominator_roll_p50
roll saturation rate  <= 0.70 * B0_same_denominator_roll_saturation
pitch p95             <= B0_same_denominator_pitch_p95 + 0.05 rad
roll  p95             <= B0_same_denominator_roll_p95  + 0.05 rad

ordinary goal regression              <= 1/16 canonical
ordinary clearance-success regression <= 1/16 canonical
```

`posture-need precision` is binding only under §7.6.6; otherwise report-only.

The absolute thresholds of revision 2 (`pitch p50 <=0.10/0.15`, `roll p50 <=0.06/0.10`, `roll saturation <=8%/15%`) are **withdrawn as pre-registered release blockers** and must not be reintroduced.

### Clearance

```text
pooled clearance success        >=44/48
post-release panel/robot collision = 0     (measured 0/43 on the warm start; satisfiable)
unsafe release                  <=2/48
release velocity p95            <=0.75 rad/s  (measured 0.486 on the warm start)
```

No minimum fling rate.

### Dynamics manifests

```text
E0 goal              >=15/16
E1 goal              >=13/16
E2 clearance success >=13/16
E3 goal              >=12/16
E4 goal              >=9/16 or a clean force-routing boundary
```

### Body assist

Only adjudicated if the E4 arm-failure denominator >=8/16:

```text
G5-G3 or G6-G4 goal/clearance gain >=3/16
ordinary body assist               <=1/16
unauthorized body contact          = 0
contact p95                        <=180 N
contact max                        <=300 N
```

## 16.3 RELAXED_1

```text
pooled goal               >=46/48      (UNCHANGED - non-waivable)
pooled supported crossing >=42/48
holdout goal              >=56/64
holdout supported crossing >=55/64
overspeed                 <=3/48

pitch-command |p50|  <= 0.95 * B0_same_denominator_pitch_p50
roll-command  |p50|  <= 0.90 * B0_same_denominator_roll_p50
roll saturation rate <= 0.85 * B0_same_denominator_roll_saturation
pitch p95            <= B0_same_denominator_pitch_p95 + 0.08 rad
roll  p95            <= B0_same_denominator_roll_p95  + 0.08 rad

ordinary goal regression              <= 2/16 canonical
ordinary clearance-success regression <= 2/16 canonical

pooled clearance success >=41/48
unsafe release           <=4/48
release velocity p95     <=0.90 rad/s

E0 goal >=14/16
E1 goal >=11/16
E2 clearance success >=11/16
E3 goal >=10/16
E4 report-only boundary accepted
```

## 16.4 WORKER_ADAPTED

Permitted under §3.6. Must be frozen before the evaluation node it governs. It cannot waive hard safety/integrity gates and cannot lower pooled48 goal below 46/48 for a release claim.

## 16.5 Refinement rule

The planner may refine the §16.2/§16.3 posture formulas only by citing a **stronger measured basis**. They may not be replaced with new unmeasured absolute values. Specifically, the audit's diagnostic figures (achieved-angle `roll p50 = 0.3840`, `pitch p50 = 0.2358`) may **not** be converted into absolute gates such as `roll p50 <= 0.30` or `pitch p50 <= 0.20`; they are achieved-side, all-frame, and not the ordinary denominator.

---

# 17. Release taxonomy

## `V22_POSTURE_CLEARANCE_RELEASE`

```text
complete pooled48 with goal >=46/48
complete Dynamics80
complete holdout64
complete render
frozen accepted profile
ordinary posture pathology corrected against the frozen B0 baseline
safe clearance by any valid strategy
```

## `V22_FORCE_ROUTING_RELEASE`

Additionally requires a valid arm-failure denominator, a safe body-assist increment, ordinary body-assist suppression, and seed-consistent direction in the G5/G6 comparisons.

## Valid non-release outcomes

```text
V22_RESEARCH_PASS_NO_RELEASE
V22_RANDOMIZATION_BOUNDARY_IDENTIFIED
V22_POSTURE_CONDITIONALLY_USEFUL_NO_RELEASE
V22_BODY_ASSIST_NO_INCREMENT
V22_POSTURE_CONDITIONALLY_USEFUL
V22_POSTURE_MECHANISM_NULL
V22_CONTROLLED_FLING_USEFUL
V22_HOLD_OPEN_DOMINANT
V22_BODY_ASSIST_NOT_TRIGGERED
V22_BODY_ASSIST_UNSAFE
V22_DAMPING_BOUNDARY_IDENTIFIED
V22_REBOUND_BOUNDARY_IDENTIFIED
V22_RESISTIVE_BOUNDARY_IDENTIFIED
```

A non-release result is a completed scientific outcome, not a project failure.

---

# 18. Execution-time and GPU schedule

## 18.1 Device contract

```text
physical GPU0 and GPU1 only
GPU2/GPU3: leased to pull-v0 (2026-08-04 amendment)
GPU4-7:    occupied by another tenant
An idle nvidia-smi reading is NOT a lease and does not authorize scheduling.
```

Non-render: `no CUDA_VISIBLE_DEVICES`, `ACCELERATE_TORCH_DEVICE=cuda:N`, IsaacLab `device=cuda:N`, `N in {0,1}`.
Render: `CUDA_VISIBLE_DEVICES=N`, logical `cuda:0`, `N in {0,1}`.

## 18.2 Phase allocation

```text
Phase P0   GPU0: posture intervention, free-return/fixed-torque characterization, trunk-contact probe
           GPU1: posture atlas, deterministic dynamics manifests, front-thigh probe
Pilot      GPU0: conditional-posture pilot
           GPU1: clearance replay and randomization calibration
Wave 1     GPU0 G1 | GPU1 G2
Wave 2     GPU0 G3 | GPU1 G4
Wave 3     GPU0 G5 | GPU1 G6
```

Evaluation uses paired queues after training processes naturally exit.

## 18.3 Expected wall clock

Measured v21-B reference: one 4096-env / 2500-batch formal wave ≈ **17 hours**
(`base_v21B/formal/B1` step250→step2500 = 17 h 07 m; `B4` = 16 h 49 m).

```text
Wave 1 conditional posture      ~17 h
Wave 2 hinge randomization      ~17 h
mandatory formal subtotal       ~34 h

Wave 3 body assist              ~17 h, conditional
maximum formal subtotal         ~51 h
```

These estimates **exclude** P0 source work, posture baseline, dynamics characterization, pilot, Route-A checkpoint evaluation, pooled48, Dynamics80, holdout64, and render.

## 18.4 Liveness rather than deadline

Require process-liveness markers at registered intervals. **A wave is not a runtime failure merely because it exceeds the estimate**, provided:

```text
checkpoints continue to advance
metrics remain finite
GPU process remains live
no natural-exit or evidence error occurs
```

---

# 19. Implementation files

## Modify

```text
gr00t/rl/envs/door/door_open_a2_base.py
gr00t/rl/isaac_utils/playground/env_rand/door.py
gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py
gr00t/rl/scripts/generate_door_assets.py
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
gr00t/rl/tests/test_a2_v22_posture_baseline.py
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
  posture_baseline.py
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
5. high damping labelled fast rebound without measurement;
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
18. active gripper bracing silently implemented in v22;
19. **missing runtime hinge damping;**
20. **metadata damping mismatch against the spawned asset;**
21. **trace damping mismatch against the signed scenario manifest;**
22. **bucket assignment based only on a scenario label;**
23. **high damping mislabelled as fast rebound without response evidence;**
24. **formal config materialization before `V22_HINGE_RANGE_FREEZE.json` exists;**
25. **formal config promotion before `V22_POSTURE_GATE_FREEZE.json` exists without a signed `POSTURE_GATES_REPORT_ONLY` waiver;**
26. **posture gates evaluated on a denominator different from the frozen `B0` baseline;**
27. **binding `posture_need` precision whose labels are derived from the `posture_need` signals themselves;**
28. **any release label applied to a pooled48 result below 46/48.**

---

# 21. Long-term TODO patch

The worker must:

1. archive v21-B as `COMPLETED_SCIENTIFIC_NO_RELEASE`;
2. mark v22 posture/clearance/force-routing/randomization as active, with revision-3 identities;
3. correct the old common-1.0-rad corridor-branch diagnosis;
4. preserve realistic PiPER torque as unresolved;
5. add active anti-rebound gripper bracing/re-contact (exact text in §0.3);
6. state that v22 hinge stress ranges are simulation behavior tests, not hardware specifications;
7. preserve pull doors, mirror doors, velocity realism, and student distillation as separate scopes;
8. record that hinge damping randomization required new source plumbing not present at the v21-B closure commit.

---

# 22. Stopping rules

```text
implementation candidates:            2
pilot attempts after optimizer progress: 1
Window-A range adjustment:            1
Window-B profile/matrix adaptation:   1
Window-C method amendment:            1
formal process per cell/cohort:       1
```

Per §3.7, `P0-POSTURE-BASELINE` and `P0-D` range selection consume **none** of the above.

Stop immediately for:

```text
non-finite physics, unsafe body-contact cluster, source/config/checkpoint mismatch,
GPU violation, evidence fabrication, staged-reset corruption
```

Do not stop merely because:

```text
fling is ineffective on high-damping doors
conditional posture is null
body assist is not triggered
an extreme bucket is unsolved
a numeric scientific gate is missed
pooled48 lands below 46/48   (issue RESEARCH_CONTINUATION_BELOW_RELEASE_GOAL)
```

The worker is authorized to document, waive, adapt, continue, and close with a scientifically valid non-release conclusion.

---

# 23. Ideal v22 behavior

```text
ordinary middle-height door:
  near-zero roll/pitch, arm-led opening,
  controlled fling or quiet hold-open, no rebound contact

height-extreme or moderately difficult door:
  bounded posture, improved arm margin,
  strategy selected from observed dynamics

fast-rebound door:
  controlled positive release impulse, sufficient clearance, no slam or collision

high-damping / high-resistive door:
  hold-open if fling is ineffective,
  body assist only after measured arm-plus-posture failure

compound extreme door:
  safe trunk/front-thigh force routing if feasible,
  otherwise a clean failure boundary, not uncontrolled impact
```

---

# Appendix A — `PROVISIONAL_CANDIDATE_RANGES_NOT_AUTHORIZED_FOR_FORMAL_TRAINING`

The following revision-2 numeric table is retained for continuity only. It is **not authorized** for formal training, manifest freezing, or scenario construction. It is anchored to an unverified runtime damping value of `50.0` (§2.2) and must be replaced by measured `P0-D` output before use.

```text
H0 CORE            w=0.55  damping [30,70]   stiffness [1,10]   maxforce [3,12]  mass [80,160]  height [0.85,1.10]
H1 HIGH_DAMPING    w=0.15  damping [70,120]  stiffness [2,10]   maxforce [6,16]  mass [80,160]  height [0.85,1.10]
H2 FAST_REBOUND    w=0.15  damping [15,40]   stiffness [10,20]  maxforce [10,18] mass [80,160]  height [0.85,1.10]
H3 HIGH_RESISTIVE  w=0.10  damping [40,80]   stiffness [6,16]   maxforce [14,20] mass [80,160]  height [0.85,1.10]
H4 COMPOUND_EXTREME w=0.05 damping [90,150]  stiffness [14,24]  maxforce [16,22] mass [140,160] height {0.85,1.10}
```

Candidate deterministic manifest grids (also unauthorized until frozen):

```text
E0_CORE16       damping {30,50,70}      stiffness {2,6,10}      maxforce {5,10,12}   mass {80,120,160}  height {0.85,0.975,1.10}
E1_DAMPING16    damping {50,75,100,120} stiffness 6             maxforce 12          mass/height balanced
E2_REBOUND16    damping {15,25,35,40}   stiffness {10,14,18,20} maxforce {10,14,18}  mass/height balanced
E3_RESISTIVE16  damping 50              stiffness 8             maxforce {8,12,16,20} mass/height balanced
E4_COMPOUND16   damping {90,120,150}    stiffness {14,20,24}    maxforce {16,20,22}  mass {140,150,160} height {0.85,1.10}
```

---

# Appendix B — Revision-3 audit measurements (diagnostic, non-binding)

Source: delivered v21-B evidence, `logs_eval/base_v21B/postformal_20260804_route_b_b1_pooled48_r24` (48 first episodes) and `logs_eval/base_v20_R2/m22_r3_route_a_f8e3197_offline_20260801/runs/G4/step_002500_*` (16 first episodes). Reconstruction validated against the official reporter to four decimals.

| quantity | v20 G4@2500 | v21-B B1@500 (v22 warm start) |
|---|---|---|
| \|achieved pitch\| p50 / p95 | 0.2837 / 0.3695 | **0.2358 / 0.3524** |
| \|achieved roll\| p50 / p95 | 0.3185 / 0.4177 | **0.3840 / 0.4296** |
| achieved-roll saturation ≥0.95×0.40 | 26.2% | **56.9%** |
| release velocity p50 / p95 | 0.368 / 0.548 | 0.369 / **0.486** |
| post-release body contact | 0/10 | **0/43** |
| upper-DoF overspeed base rate | ~2.9% (mature v20 cells) | 0/48 at this checkpoint |

**These are achieved-angle, all-frame measurements.** They are not command-side and not the `ordinary_need_negative` denominator. They justify *withdrawing* the revision-2 absolute posture gates; they do **not** constitute the `B0` baseline, which only `P0-POSTURE-BASELINE` may produce.

---

*One-sentence brief: revision 3 preserves the whole v22 scientific direction — conditional posture, three legitimate clearance strategies, hinge randomization, gated body assist, worker waiver authority — while replacing two pre-registered blockers with measured admission nodes (`P0-POSTURE-BASELINE` and an unfrozen `P0-D` hinge range), restoring the pooled48 release goal to 46/48 with an explicit research-continuation path below it, and documenting a 34 h mandatory / 51 h maximum two-GPU formal budget.*
