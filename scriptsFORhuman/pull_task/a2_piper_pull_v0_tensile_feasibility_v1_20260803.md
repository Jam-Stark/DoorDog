# A2+Piper DoorDog Pull-Door Task Family
## Independent Scoping, Mechanism Design, and First-Round Experimental Plan

> Provenance: authored by the cloud pro planner model, delivered 2026-08-03 HKT; archived verbatim into the repo by the local planner session. Adopted **PASS with three binding amendments** — see `a2_piper_pull_v0_worker_execution_split_20260803.md` (which governs on conflict).

**Plan ID:** `a2_piper_pull_v0_tensile_feasibility_v1`
**Date:** 2026-08-03 HKT
**Repository:** `Jam-Stark/DoorDog`
**Source branch:** `A2_Piper`
**Source commit audited:** `78081149096dae0d278b32999438aad5f5311059`
**Task family:** right-hinged, in-opening pull doors (`door_open_io="in"`)
**Round status:** implementation may start; formal training is gated by P0 and the mechanism probes in P1
**Primary scientific object:** tensile handle-load transmission and the non-monotone base trajectory required to open, clear, and traverse a pull door
**Release status:** this is a feasibility-mapping round, not a release round

---

## Executive decision

The first pull-door round should **not** be organized around a stage-4 target coordinate or around an assumed "friction-limited" policy. It should be organized around a physically ordered event funnel:

```text
outside-face alignment
    -> load-bearing tensile capture
    -> latch release
    -> positive hinge progress while capture remains valid
    -> panel-sweep clearance
    -> deliberate release-or-hold decision
    -> root and whole-body clearance to the opposite side
```

The first thing to build is a direction-aware door-task contract plus an in-opening `grasp_target` on the outside face. The first thing to measure is whether the current gripper can transmit a tensile load and produce positive hinge motion without robot-panel body assistance. That measurement is cheaper and more decisive than a training run, a stage-4 reward revision, or a zero-shot initialization argument.

The physical door mechanism should remain the same: the right-hinged panel still opens under positive hinge angle toward world `+X`; the hinge limits, closer spring, and latch mimic do not need sign changes. The robot/task geometry changes: pull starts on world `+X`, faces approximately yaw `pi`, initially approaches in `-X`, pulls the outside handle while yielding back toward `+X`, and only later reverses to traverse toward `-X`.

The main implementation correction to the simple "mirror the robot, not the door" framing is that the **physical panel should not be mirrored, but the asset-attached task target must become `door_open_io`-aware**. The current `grasp_target` is hard-coded to the negative-X handle face. A pull task that mirrors only the robot will point the FrameTransformer and grasp rewards at the far face of the axle.

The first formal policy comparison should be a matched bounded-adaptation experiment, not a single zero-shot verdict:

```text
initialization in {v20 G4 step2500, scratch}
seed in {0, 1, 2}
common pull geometry, actuator profile, reward schedule, and budget
```

Zero-shot remains valuable as a behavioral fingerprint under standing rule 5 (policy as probe) and standing rule 9 (zero-shot before actuator changes), but it cannot decide warm start versus scratch because it confounds transferability with an unadapted push policy's learned direction.

A round that produces a validated geometry contract and a clean force-transmission feasibility landscape, but no release-grade pull policy, is a successful round. It answers whether the task is mechanically feasible under each gripper mechanism and where the event funnel breaks.

---

## 0. Evidence authority, source identity, and audit limitations

### 0.1 Authority order used in this plan

The evidence hierarchy is:

1. current source on `A2_Piper`;
2. the saved resolved configuration of the actual v20 G4 run;
3. project constitution and design history;
4. current plans and memory entries;
5. peer claims and historical unexecuted branches.

This order implements standing rule 10. A repository YAML, ablation template, or planning statement does not override `logs_rl/<run>/config.yaml` when describing what a checkpoint actually experienced.

### 0.2 Current source artifacts directly audited

| Artifact | Authority used here | Relevant symbols |
|---|---|---|
| `gr00t/rl/isaac_utils/playground/env_rand/door.py` | current source; blob `145a9c6a697772978fb114b21885be92bd88fb0b` | `DoorSpawnerCfg`, `spawn_door`, `hinge_joint`, `handle_joint`, `latch_joint`, `grasp_target`, metadata `doorOpenLR` / `doorOpenIO` |
| `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` | current source; blob `c4fb24f8e0ca5ba74c237708c2c601dad4cadf3d` | `door_spawner_cfg`, `multi_spawner_cfg`, `TaskObjCfgDict`, `get_TaskObjCfgDict_for_door_config` |
| `gr00t/rl/config/env/door_open_a2_base.yaml` | current source; blob `6245fb9de04eff6af7fb0a06686ef92f55ff60f7` | `target_obj_transform_sub_prim_path`, stage thresholds, stage-0 band, target root, v20 send/crossing selectors |
| `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` | current source | push/hinge, hold, corridor, crossing, collision, traversal reward scales |
| `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` | current source; blob `c0f7cfc72287d2d1fb5fea4c03e54a43e3d1b320` | current action dimensions, arm/finger effort, stiffness, damping |
| `a2_piper.urdf` | supplied robot model | `arm_j7` and `arm_j8` are prismatic fingers with 10 N URDF effort limits and 0.035 m travel |
| `scriptsFORhuman/a2_piper_project_handoff_20260725.md` | project constitution | North Star, research thesis, closed dead ends, standing rules 1–12 |
| `scriptsFORhuman/a2_piper_longterm_TODO.md` | roadmap authority | Table C item 4: pull task as the second force-feasibility arena |
| `scriptsFORhuman/V21/a2_piper_base_v21_implementation_training_execution_plan_20260801.md` | reusable apparatus | bounded adaptation, M22/all-checkpoint, pooled48, holdout64, render and receipt conventions |
| `scriptsFORhuman/V21/a2_piper_base_v21B_ablation_execution_plan_20260802.md` | anti-block and proxy discipline | measured corrections C1/C2/C3, anti-block doctrine, freeze guard, `ESTIMATE_ONLY` implicit-actuator effort |
| `memory/a2-piper/door-asset-randomization-baseline/description.md` | historical interpretation, rechecked against current source | in/out is a new task rather than a safe one-bit training switch |
| `memory/a2-piper/door-asset-openio-sign/description.md` | historical static audit, rechecked here | `doorOpenIO` is metadata-only in the current builder |
| v20 G4 saved run config | source of truth for warm checkpoint | actual stage/send thresholds, target, reward scales, actuator profile and material selector |

### 0.3 Warm-start binding

The only current hash-verified and render-QA'd candidate is:

```text
logs_rl/a2_piper_full_stage_a2_base/
  base_v20_R3_G4-20260731_004712/model_step_002500.pt
sha256:
  f000f13e817309f7b73e33c5c4d95076397debb992713e5613dce567bfda806d
```

The corresponding saved run config is:

```text
logs_rl/a2_piper_full_stage_a2_base/
  base_v20_R3_G4-20260731_004712/config.yaml
```

Important resolved differences from the current repository robot YAML include:

| Quantity | Current repository default | v20 G4 saved run truth |
|---|---:|---:|
| finger effort limit, each prismatic finger | 10 N | 45 N |
| finger stiffness | 80 | 1300 |
| finger damping | 3 | 32 |
| gripper material selector | shared default disabled | enabled |
| stage-0 distance band | 0.55–0.60 m | 0.50–0.80 m |
| stage 3→4 hinge threshold | 0.174533 rad | 0.25 rad |
| send threshold | shared selector disabled | 0.90 rad |
| stage-4 release threshold | 1.20 rad | 1.60 rad |
| stage 4→5 threshold | 1.0472 rad | 1.25 rad |
| final target | `(+2, 0, 0.5)` m | `(+2, 0, 0.5)` m |

No pull experiment may call the current 10 N profile "the v20 baseline," and no experiment may call the v20 45 N profile "hardware-realistic" without a separate hardware decision.

### 0.4 Explicit source-access limits in this planning session

The current remote branch did not expose `scriptsFORhuman/a2_piper_pull_door_worktree_cut_and_round_design_20260803.md`. Current HEAD is an empty source-tree commit titled `chore(a2): retire transient pull-door planner prompt`; the file was not retrievable at HEAD or its immediate parent through the repository connector. I therefore audited the five peer claims quoted in the task request and do not claim to have audited any unquoted detail of that document.

The historical commit `f624169` and branch `codex/a2-piper-pull-door` were also not present on the remote connector. This plan treats their user-supplied status—v10-era and never simulated—as authoritative context, but does not claim a byte-level review of that diff.

The connector did not return the full approximately 22,000-line `door_open_a2_base.py` body in this session. Its known direction-dependent symbols were cross-checked through current configs, tests, v20/v21 plans, and saved-run evidence. P0 therefore contains a hard source-manifest gate requiring the worker to run `git grep` against the local checkout and close every match before editing. This is not a performance gate; it is an integrity gate under standing rule 10.

The direct contents of the three `scriptsFORhuman/force_feasible/` discussions were not retrievable through the connector. The thesis and closed dead ends were available in the handoff and long-term TODO and are used here. No claim below is attributed to an unseen sentence in those three files.

---

# A. Independent geometry and physics derivation

## A.1 Sign encoding in the current builder

`door.py::spawn_door` maps the task labels as follows:

```text
door_open_lr: left  -> +1
              right -> -1

door_open_io: in   -> +1
              out  -> -1
```

Only `door_open_lr` currently affects construction. `door_open_io` is written to metadata as `doorOpenIO` and otherwise does not affect the panel, hinge, handle, latch, or target pose.

The current scenario fixes:

```text
door_open_lr = right -> -1
door_open_io = out   -> -1
```

Source: `isaacsim.py::door_spawner_cfg`.

## A.2 Which way the panel swings

For a right-hinged door, `door.py::hinge_joint` places the hinge on the positive-Y edge:

```text
hinge point in root frame:
  h = (0.02, -half_width * door_open_lr)
    = (0.02, +half_width)
```

At the closed pose, the panel center is approximately at `(0, 0)`, so the vector from hinge to panel center is:

```text
r = panel_center - hinge
  = (-0.02, -half_width)
```

The hinge axis is world/local `+Z`, the lower and upper limits are `0` and `150 deg`, and opening uses positive angle. The instantaneous velocity under positive angular velocity is:

```text
v = omega_z x r
  = (-r_y, r_x)
  = (+half_width, -0.02)
```

Therefore the panel initially moves toward world `+X` as the positive hinge angle increases. This conclusion follows from the current joint placement and right-hand rule; it does not depend on the `doorOpenIO` metadata label.

### Consequence for robot side

- Current push task: robot starts on the `-X` side and travels generally toward `+X`; the panel moves away from it.
- Pull task using the same physical door: robot starts on the `+X` side, faces generally toward `-X`, and pulls the panel toward its own side as the panel moves `+X`.
- Final pull traversal target is on the `-X` side.

The initial pull action and the final traversal action have opposite X signs. A pull episode is therefore not a global sign flip of the push trajectory.

## A.3 Hinge sign, joint limits, closer, and latch

### Hinge

The physical hinge should remain:

```text
axis             = Z
lower limit      = 0 deg
upper limit      = 150 deg
opening direction = positive hinge angle
```

No pull-specific sign inversion is required. A sign inversion would make the current right-hinged panel try to open through its closed-side geometry or would require rebuilding the panel/hinge convention. The task distinction is which side the robot occupies, not a different positive joint coordinate.

### Self-closing drive

The hinge drive target is `-10 deg`, outside the positive-angle joint range. Within the legal range it therefore produces a closing tendency toward the zero-angle stop. That is the closer spring. It should not be inverted for pull. The closer is a required physical challenge, especially after release, and not a direction bug.

### Handle and latch

The handle joint uses axis `X`, limits `0..45 deg`, and a drive target of `-15 deg`; positive handle motion moves away from the closed stop. The prismatic latch uses axis `Y`, limits `0..0.03 m`, and a mimic gearing of `-0.03/45` relative to the handle joint. These definitions depend on left/right handedness, not on `doorOpenIO`.

Pulling from the opposite handle face does not require a latch or handle-joint sign change. It may require a different wrist motion to create the same positive handle-joint angle, which is a policy and target-frame issue.

This independently confirms the two memory entries' core conclusion: `doorOpenIO` is not currently a construction switch, and the in-opening task is produced by changing robot/task-side geometry while retaining the door's physical opening coordinate.

## A.4 Which handle face and target a pull grasp needs

The current asset creates a double-sided handle:

```text
handle_inside  center x = -axle_length / 2
handle_outside center x = +axle_length / 2
```

It also creates matching optional hooks, `hook_inside` and `hook_outside`, when `spawn_hook` is true. With no deterministic override, the current builder samples hook presence with probability 0.5.

The current `grasp_target` is not double-sided. It is hard-coded to:

```text
grasp_target x = -axle_length / 2
fixed-joint localPos1 x = -axle_length / 2
```

That is the negative-X, inside face used by the current robot on the `-X` side. For the pull robot on `+X`, the required target is on the positive-X, outside face.

A minimal IO-aware translation contract is:

```text
grasp_target_face_x = door_open_io * axle_length / 2
```

This preserves the existing target for `out=-1` and selects the outside target for `in=+1`.

### Recommended target implementation

Use one conditional prim named `grasp_target`, constructed on the active face. This preserves:

- `env.config.task.target_obj_transform_sub_prim_path: grasp_target`;
- observation and FrameTransformer topology;
- checkpoint tensor shapes;
- mixed-task compatibility at the asset level, because each generated door owns a correctly placed target.

Do not hard-code `axle_length` in the environment. The builder owns that sampled dimension and must place the target.

### Target orientation is not settled by static translation alone

The current target has identity local orientation. Several environment terms consume the target frame and gripper orientation. Rotating the robot root by `pi` does not by itself prove that the target-frame orientation error has the intended convention.

**I cannot determine this without runtime evidence.** The exact settling probe is:

1. generate paired, dimension-identical right-hinged `out` and `in` doors;
2. render target-frame axes, the virtual TCP frame, the handle axle, and the approach normal;
3. place the robot in canonical pregrasp poses on each side;
4. verify that the target-to-TCP positional offset points from the active handle face toward the robot;
5. compare the pull canonical orientation error against the push canonical orientation error under `piper_gripper_handle_frame_transformer` and `gripper_handle_orientation`;
6. choose the pull target rotation only after that overlay establishes the frame convention.

A target whose point is correct but whose axes are wrong will manifest as a policy that reaches the visible outside handle yet is continuously penalized for wrist orientation or approaches with the finger opening rotated away from the lever.

## A.5 Force transmission: what changes, and what is not yet proven

### Push

In the current push task, positive panel motion can be produced by a compressive interaction. The robot can transmit `+X` load through the palm, finger surfaces, or a partially captured lever. High normal squeeze is helpful but not necessarily the only way to move the door; geometric contact and compression can carry load even when the grasp is imperfect.

### Pull

In pull, the panel must be accelerated toward the robot side. The handle tends to separate from a gripper that merely touches its near surface. Sustained load therefore requires a tensile retention mechanism, which may be one or a mixture of:

- friction generated by opposing finger normal force;
- bilateral pinch on the lever capsule;
- geometric wrap or form closure around the lever;
- engagement with the optional outside hook;
- contact between the handle and the gripper palm/finger geometry;
- unintended robot-panel contact that assists the opening.

The source does **not** establish a clean transition from "form closure in push" to "friction in pull." The asset has lever geometry and optional hooks on both faces; the gripper uses two prismatic fingers; and the exact collision mesh can permit geometric capture. Calling pull friction-limited before measuring the contact mode would prejudge the round.

The potential binding constraints, in plausible but unverified order, are:

1. wrong face or target-frame alignment;
2. loss of tensile capture because of friction or geometry;
3. finger force limit: 10 N in the current URDF/repo profile versus 45 N in the v20 G4 resolved profile;
4. arm workspace or arm effort while following the handle arc;
5. inability of the base to retreat and side-step without entering the panel sweep;
6. handle spring/latch torque;
7. hinge closer load;
8. self-collision or panel/body contact;
9. insufficient time only after the above events are feasible.

The first mechanism probe must therefore be factorial over hook presence, friction regime, and finger effort profile and must classify first loss rather than report only task success.

## A.6 Procedural versus offline asset generation

The active scenario uses:

```text
DoorSpawnerCfg(func=spawn_door, ...)
MultiAssetSpawnerCfg(assets_cfg=[door_spawner_cfg] * 4096, random_choice=False)
```

The door is procedurally constructed at scene creation. The active task does not load a pre-generated door USD library. Changing `spawn_door` therefore does **not** require regenerating an offline asset library for this training path.

P0 must still verify the resolved run selects this scenario and that no local override substitutes cached USD assets. That is a standing-rule-10 check, not a reason to regenerate assets.

## A.7 Explicit delta from the peer framing

The physical geometry agrees with the narrow statement "do not mirror the door panel." It disagrees with the stronger statement "pull is implemented only by mirroring the robot." The correct split is:

```text
physical door panel, hinge, limits, closer, latch: unchanged
robot side, yaw, staging, path, final target: changed
task target attached to the handle: changed or selected by door_open_io
```

It also does not support a source-only claim that pull is necessarily friction-limited. That question is the first measured dependent variable of this plan.

---

# B. Pull-task definition and North Star

## B.1 Scope of pull-v0

The first task family is intentionally narrow:

```text
hinge handedness: right only
door opening coordinate: positive hinge angle, panel toward +X
door_open_io: in only
robot initial side: +X
robot initial nominal yaw: pi
terminal side: -X
handle type: lever
latch: enabled
closer: enabled
current door width, height, weight, handle-height, handle-torque,
  and hinge-force ranges: retained
full room walls: disabled for the first mechanism/capability round
student/RGB policy: out of scope
mixed push/pull training: out of scope, but direction-parameterized code is in scope
```

This is a new task, not an ablation switch inside the push release claim.

## B.2 Direction contract

The implementation should centralize direction semantics rather than scatter world-X negations. With the current metadata encoding:

```text
io_sign       = doorOpenIO          # in=+1, out=-1
approach_side = io_sign             # pull +X, push -X
travel_dir_x  = -io_sign            # pull -X, push +X
handle_face_x = io_sign             # pull outside +X, push inside -X
```

Useful signed coordinates are:

```text
signed_distance_to_door = travel_dir_x * (door_x - root_x)
# positive before the door when the robot stands on the intended approach side

signed_crossing_progress = travel_dir_x * (root_x - door_x)
# negative before the frame, positive after crossing

final_target_x = door_x + travel_dir_x * target_distance
```

Panel opening remains a positive hinge angle and is intentionally not derived from `io_sign`.

## B.3 Ideal episode by physical event

Standing rule 11 requires every requirement to be attached to the physical event at which it matters. The pull North Star is therefore event-defined, not only stage-number-defined.

| Event | Ideal behavior | Required measurements | Failure class |
|---|---|---|---|
| **E0 — episode reset and approach-side validity** | Robot is on `+X`, outside the closed panel and its immediate sweep envelope, facing the outside handle. It has enough free space to retreat further `+X` after grasp. | signed distance to door, yaw error, minimum robot-panel distance, target-face identity | wrong-side reset, no retreat reserve, robot spawned in sweep |
| **E1 — settled outside-face pregrasp** | TCP approaches the `+X` handle face along the verified target normal. Base motion settles without premature panel or handle motion. Arm remains within a recoverable workspace. | target-frame translation/orientation error, root speed, handle/hinge displacement, arm joint margins | far-face target, wrong wrist axes, base creep, pre-contact collision |
| **E2 — load-bearing tensile capture** | Both fingers or a verified geometric capture hold the lever under a monotone tensile proof action. This is not satisfied by proximity, one-frame contact, or an un-loaded close command. | bilateral/contact mode, proof displacement, separation, finger effort proxy, first-loss mode | touch-only grasp, friction slip, hook miss, finger saturation |
| **E3 — latch release** | Positive handle-joint motion retracts the latch while tensile capture remains valid and without body-panel assistance. | handle angle/velocity, latch displacement, capture state, body contact | wrong handle direction, latch mimic failure, capture lost before unlatch |
| **E4 — first positive hinge progress under retained capture** | The door reaches positive hinge motion while the base yields away from the final target and follows a collision-free portion of the handle arc. | hinge angle/velocity, retained-grasp duration, root outward excursion, arm workspace, panel/body contacts | no force transmission, arm limit, base refuses to yield, body assist |
| **E5 — sweep-clearance and release-or-hold decision** | At a measured clearance state, the policy deliberately either releases or maintains hold. Accidental loss is not accepted as a release. The arm and body are outside the moving panel's pinch/sweep region. | release intent, hinge at decision, minimum clearance, post-release reclosure, recontact | premature release, trapped arm, panel strikes base, closer-induced pinch |
| **E6 — path reversal and doorway entry** | After clearance, root motion changes from the earlier `+X` retreat component to final `-X` traversal. The policy does not cut through the moving panel. | first path-reversal time, signed crossing progress, clearance margins, stage/event timing | target reward fights required retreat, premature crossing, oscillation |
| **E7 — whole-body threshold clear** | Root, legs, Piper arm, and gripper clear the frame and panel on the `-X` side. Robot remains stable; the arm is disentangled; no immediate recontact or closer trap occurs. | body-wise crossing, frame/panel contacts, stability, release-to-clear time, terminal reason | root-only false success, arm left behind, reclosure collision, fall |

## B.4 Pull events that do not have a safe push analogue

A mechanical sign flip of the push institution silently drops four pull-specific requirements:

1. **Tensile proof before unlatch.** Push contact can transmit compression without proving retention. Pull must demonstrate a load-bearing capture before the handle/latch event.
2. **Outward yield before inward traversal.** Pull requires an initial retreat component opposite the final target. A final-target reward activated too early directly conflicts with the feasible motion.
3. **Panel sweep into the approach side.** The door occupies the robot's initial half-space, creating a collision and pinch event that is much weaker in push.
4. **Closer behavior after release.** A released pull door can close back into the robot's intended entry path or trap the arm. "Door angle once exceeded a threshold" is not sufficient.

The current stage numbering may be retained for compatibility, but the event semantics above are authoritative. Stage boundaries must be attached to these events rather than inferred by negating push coordinates.

---

# C. What genuinely differs, ranked by break risk

| Rank | Difference | Why it is hard | Cheapest decisive evidence |
|---:|---|---|---|
| 1 | **Active handle face and target-frame contract** | Current target is on the far face for pull. A wrong point or orientation poisons approach, grasp rewards, stage gates, and all downstream evidence. | paired in/out frame-overlay test and fixed-pose transform assertions |
| 2 | **Non-monotone base trajectory** | Robot approaches in `-X`, must retreat/yield partly in `+X` while opening, then reverses to traverse in `-X`. A single target-root objective cannot be correct across all events. | scripted handle-arc/yield feasibility probe; root path and arm-margin traces |
| 3 | **Tensile force transmission** | Pull requires retention under separating load. The limiter may be friction, pinch force, hook geometry, palm contact, or workspace. | hook × friction × finger-effort load-to-loss factorial |
| 4 | **Panel sweep and robot-panel collision** | The panel moves into the initial robot side. Body contact can both cause failure and masquerade as useful force assistance. | per-body panel contact traces plus collision-free scripted opening |
| 5 | **Arm workspace along the handle arc** | The handle translates `+X` and laterally around the hinge. The base must coordinate so the arm neither reaches a joint boundary nor drags the gripper off the lever. | handle-local slip decomposition, joint-margin traces, arm/base tangent decomposition |
| 6 | **Latch-release-to-hinge coupling** | The grasp must survive handle rotation and immediately carry panel load. Success at either event alone does not establish the combined capability. | event-conditioned capture survival from E2 through E4 |
| 7 | **Self-closing spring after release** | The unchanged closer can reclose into the entry path, strike the robot, or pull the gripper back. | hinge decay and recontact trace from release to whole-body clear |
| 8 | **Direction-dependent stage and reward institutions** | Push uses world `+X` assumptions in reset, traversal, crossing, and send logic. Naive sign edits can create unpaid required motion or an income cliff. | source manifest plus per-component income traces across every event boundary |
| 9 | **No enclosing room walls in the current scenario** | `add_walls=False` means the first round has open retreat space. It does not establish constrained-space pull capability. | keep open-space v0; later paired wall/corridor evaluation after base capability |
| 10 | **Future RGB visibility and direction inference** | Pull can occlude the handle and reverse camera motion; mixed IO needs direction observability. | deferred teacher-to-student camera/observation study after teacher feasibility |

### Why stage 4 is not the first central risk

Stage 4 can certainly fail, but the current evidence does not establish that the through-target is the first or dominant cause. A policy cannot reveal a stage-4 target defect if it never acquires a load-bearing outside grasp or never produces positive hinge motion without body assistance.

The deeper stage-4 design issue is not a coordinate by itself; it is the **event-triggered reversal of desired root motion**. Before clearance, an outward yield may be required. After clearance, inward traversal is required. This plan measures and then implements that transition rather than assuming a mirrored `target_root_pos` is sufficient.

---

# D. Branch and baseline recommendation

## D.1 Branch point and worktree

Create the pull worktree from the current pushed `A2_Piper` HEAD, not from the live v21-B training worktree and not from the historical pull branch:

```bash
cd /home/baoquanc/workspace/DoorDog-A2_Piper
git fetch origin
git checkout A2_Piper
test "$(git rev-parse HEAD)" = "78081149096dae0d278b32999438aad5f5311059"
git status --short

git worktree add ../DoorDog-A2_Piper-pull \
  -b codex/a2-piper-pull-v0-20260803 \
  78081149096dae0d278b32999438aad5f5311059
```

If the worker host reports a newer pushed `A2_Piper` commit, do not silently substitute it. Emit a source-delta report, identify changed direction-dependent symbols, and obtain an arbiter decision before rebasing the plan.

v21-B is training now; its outcome is unknown. Waiting for it would block implementation work that does not depend on its winner. Conversely, merging its live branch would import an unresolved arm profile and freeze-guard changes into a new task, confounding pull mechanics with an unfinished round.

## D.2 Namespace

Use a separate task/config/reward/log namespace. Recommended names are:

```text
gr00t/rl/envs/door/door_open_a2_pull.py
gr00t/rl/config/env/door_open_a2_pull.yaml
gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_pull.yaml
gr00t/rl/config/ablation/wbmanip/pull_v0_*.yaml
logs_rl/a2_piper_full_stage_a2_pull/
logs_eval/a2_piper_pull_v0/
scriptsFORhuman/pull_v0/
```

The new environment may subclass or factor common helpers from `DoorPregrasp`, but pull-specific defaults must not mutate the push namespace.

## D.3 Initialization candidates

### Candidate W — v20 G4 step2500

Use the verified v20 G4 checkpoint as the primary transfer candidate because:

- it is the only hash-verified, render-QA'd checkpoint;
- it already contains approach, grasp, latch, hold, hinge, and traversal representations;
- standing rule 8 records that three of four historical from-scratch runs entered the wrong basin;
- policy-only warm start preserves a known whole-body coordination prior.

It is not automatically the winner. Its learned push-side base trajectory can be negative transfer.

### Candidate V — future v21-B winner

Do not use a future v21-B checkpoint until all of the following exist:

- v21-B round outcome and selected checkpoint;
- saved resolved `config.yaml`;
- checkpoint SHA-256;
- source-lock receipt;
- Route-A render QA;
- an explicit record of its resolved arm and finger profile.

If those conditions are met before pull P2, add it as a third initialization arm under the same bounded-adaptation protocol. Do not replace W after inspecting only its headline success metric.

### Candidate S — scratch

Scratch is a scientific comparator, not the default operational path. It is required because a push policy may encode the wrong base-motion basin and because zero-shot cannot distinguish "useful low-level skill" from "directional behavioral inertia."

## D.4 Decision protocol: zero-shot plus replicated bounded adaptation

### Z0 — paired frozen-policy fingerprint

Evaluate v20 G4 step2500 with no optimizer updates on:

1. its exact resolved push control configuration, as a regression anchor;
2. pull geometry with pull rewards disabled or report-only, to observe behavior without reward adaptation.

Report the first event reached, wrong-side motion, target-face error, grip/contact state, hinge progress, and body contact. Poor pull zero-shot performance is expected and does not decide the initialization.

### BAW — matched adaptation

Use the v21 bounded-pilot precedent as an operational budget, not as a pull acceptance threshold:

```text
initialization: W or S
seeds: 0, 1, 2
num_envs: 256
optimizer batches: 750
save checkpoints: 250, 500, 750
common actuator profile: v20 G4 resolved profile for both W and S
common geometry/rewards/randomization: identical
v20 send/crossing curriculum: disabled
```

This yields six cells and leaves one physical GPU available for evaluation when GPUs 0–6 are available. If they are not available, run the same cells sequentially; do not use GPU7 without human confirmation.

The primary decision variable is the **event-funnel learning curve**, not final goal success:

```text
E1 outside-face alignment
E2 load-bearing capture
E3 latch release | E2
E4 positive hinge progress | E3
E5 clearance decision | E4
E7 whole-body clear | E5
```

For each checkpoint, report unconditional and conditional rates, with `N/A` when a conditioning denominator is zero. Also report body-assist incidence and first-loss mechanism.

Decision rule:

- choose W if all three seeds show earlier or larger event-funnel acquisition than S and the gain is not explained by greater robot-panel body assistance;
- choose S if all three seeds show that W is trapped in a wrong-direction or premature-crossing basin while S reaches later clean events;
- if the effect is inconsistent across seeds, label initialization unresolved and either add one matched replicate per initialization or use W operationally for the next capability phase while preserving the unresolved scientific result. The latter default follows the historical scratch-basin evidence; it is not a claim that W is superior.

No single zero-shot episode, final checkpoint, or best-seed result may decide W versus S.

## D.5 Historical pull branch

Do not rebase the v10-era pull implementation. Its environment diff targeted a file that no longer exists in that form and it never received simulation evidence. Rebase would create false confidence by resolving textual conflicts without revalidating semantics.

Manually port only independently reverified ideas:

- an explicit direction contract;
- a separate pull namespace;
- tests that bind robot side, target side, and terminal side;
- artifact/log isolation.

The old branch is reference-only and has no runtime authority.

---

# E. Complete change inventory

## E.1 Required architecture: one direction contract

Before changing rewards or stages, add a small immutable direction object or equivalent helper. It should expose, at minimum:

```text
io_sign
approach_side_x
travel_dir_x
active_handle_face_x
signed_distance_to_door(root_x)
signed_crossing_progress(root_x)
final_target_x(distance)
```

Every world-X-dependent helper must consume this contract. Direct tests should instantiate both `out` and `in`, even though formal pull-v0 trains only `in`. This makes mixed-task support an architectural property without prematurely training a mixed policy.

## E.2 Tier 0 — source-manifest closure before edits

The worker must produce `scriptsFORhuman/pull_v0/PULL_V0_DIRECTION_SITE_MANIFEST.json` from the local checkout. At minimum, inspect all matches from:

```bash
git grep -n -E \
  'door_open_io|doorOpenIO|door_open_lr|doorOpenLR|grasp_target|A2_PREGRASP_OFFSET' \
  -- gr00t/rl

git grep -n -E \
  '_reset_root_states|stage_0_to_1|stage_1_to_2|stage_2_to_3|stage_3_to_4|stage_4_to_5' \
  -- gr00t/rl/envs/door

git grep -n -E \
  'target_root_pos|root_x|crossing|corridor|send_ready|send_hinge|face_door|walk_to_door' \
  -- gr00t/rl/envs/door gr00t/rl/config

git grep -n -E \
  'push_door|dont_push|handle_local|slip|hold_oracle|pd_effort|door_body_contact' \
  -- gr00t/rl/envs/door gr00t/rl/config
```

Generated line numbers are navigation aids only. The manifest must record file, symbol, semantic category, intended change/no-op, and test. Formal implementation is blocked until every match is classified.

## E.3 Tier 1 — asset and scenario

| File / symbol | Change | Must not change | Silent-error manifestation |
|---|---|---|---|
| `door.py::spawn_door` IO parsing | retain sign encoding; use `door_open_io` to select active task target face | do not use IO to invert hinge axis or joint limits | mixed metadata appears correct while physics and target disagree |
| `door.py::grasp_target` translation | set X from active face; preserve sampled axle dimensions | do not hard-code axle length in env | robot reaches through panel or grasps far face |
| `door.py::grasp_target` orientation | add verified IO-aware orientation if P0 overlay requires it | do not guess a `pi` rotation without FrameTransformer evidence | positional success but persistent wrist-orientation penalty |
| `door.py::handle_inside` / `handle_outside` | no geometry change in v0 | do not delete the unused face | unnecessary asset divergence and loss of mixed support |
| `door.py::hook_inside` / `hook_outside` | expose deterministic `rand_spawn_hook` in probe configs; record hook presence | do not assume hooks are realistic or required | apparent "friction" success actually caused by hook capture |
| `door.py::hinge_joint` | no change | axis Z, 0..150 deg, target -10 deg | wrong opening direction or no closing spring |
| `door.py::handle_joint` | no change to joint sign/limits/drive | axis X, 0..45 deg, target -15 deg | latch fails after an unnecessary sign flip |
| `door.py::latch_joint` and mimic | no change | current gearing and LR handling | handle rotates but latch extends or remains engaged |
| `door.py` metadata | add explicit active target face/orientation version if useful | retain `doorOpenIO` and `doorOpenLR` | logs cannot prove which face was trained |
| `isaacsim.py::door_spawner_cfg` | new pull config resolves `door_open_io=["in"]`, right hinge retained | do not mutate shared push baseline | push regressions or ambiguous task identity |
| `isaacsim.py::door_spawner_cfg` physics ranges | retain current ranges in capability-first v0 | do not widen mass/spring to manufacture a force axis | reopens the closed heavy-door dead end under an uncontrolled arm |
| `isaacsim.py::add_walls` | keep false in P0–P4 unless separately authorized | do not claim constrained-room capability | open-space success misreported as constrained pull success |
| `MultiAssetSpawnerCfg` | retain procedural runtime generation; add deterministic probe variants | do not regenerate an offline library | wasted work and non-identical probe assets |

## E.4 Tier 1 — robot spawn, staging, and FrameTransformer

| File / symbol | Change | Must not change | Silent-error manifestation |
|---|---|---|---|
| `door_open_a2_base.py::_reset_root_states` or pull override | spawn on `+X`; yaw approximately `pi`; preserve noise in a signed frame | do not merely negate one coordinate while leaving yaw/target unchanged | robot starts behind itself, walks away, or camera/arm points wrong way |
| stage-0 staging helpers | represent distance in signed door coordinates; calibrate pull band by reach and retreat reserve | do not copy 0.50–0.80 m as an unverified pull optimum | pregrasp is reachable but no room remains to retreat |
| `A2_PREGRASP_OFFSET` and override plumbing | bind offset to active target frame; render target/pregrasp spheres | do not reinterpret a local offset as world X | correct target prim but wrong pregrasp side |
| `scene_creation_callback` debug target/pregrasp geometry | draw the active pull target, pregrasp point, target axes, and sweep envelope from the resolved FrameTransformer config | do not maintain a second hand-written visualization offset | render appears correct while the policy consumes a different target |
| `piper_gripper_handle_frame_transformer` | consume active target and verified orientation | do not alter observation shape in pull-v0 without a checkpoint-load plan | warm checkpoint fails to load or receives incompatible transform semantics |
| `_reward_walk_to_door` | use signed distance/velocity toward the door | do not reward final `-X` traversal during initial approach after contact | oscillation or premature crossing |
| `_reward_penalty_face_door` | face active handle/door frame from `+X` side | do not preserve push yaw target | arm approaches backward |
| stage-1/2 base creep guard | redefine creep relative to approach/yield event | do not penalize the later required `+X` retreat as "backward" | policy learns to hold base fixed and loses arm workspace |

## E.5 Tier 1 — stage machine and success conditions

| Symbol family | Required pull semantics | What must not be inherited blindly | Silent-error manifestation |
|---|---|---|---|
| `_stage_0_to_1_advance_condition` | signed approach-side staging and settled orientation | world-negative X band | stage advances on wrong side |
| `_stage_1_to_2_advance_condition` | outside-face target pose and verified wrist axes | inside-face target and push orientation | stage-2 reward activates through panel |
| `_stage_2_to_3_advance_condition` | load-bearing capture evidence, not only contact/close command | a push-era contact streak that has not been tensile-tested | stage advances on touch-only grasp |
| `_stage_3_to_4_advance_condition` | latch released plus first positive hinge progress while capture valid | a hinge-only threshold that can be reached via body contact | false manipulation capability |
| stage-4 release logic | deliberate release-or-hold event after measured sweep clearance | fixed push release angle or accidental grip loss | panel hits robot or closes on arm |
| `_stage_4_to_5_advance_condition` | clearance event and readiness for path reversal | push-era angle alone | final target activates while retreat is still necessary |
| completion/success | whole-body clear on signed `-X` side, stable and disentangled | root-only X threshold | arm/leg remains in frame while episode declares success |
| timeout attribution | retain event-specific terminal reason | one generic overtime bucket | force failure confused with path-planning failure |

All numeric hinge, distance, and timing thresholds in the first pull round are `report_only` until P1/P2 provide a measured distribution, except hard physical consistency checks such as valid signs, finite values, and non-penetrating spawn.

## E.6 Tier 1 — rewards and income continuity

Known direction-sensitive reward symbols include:

```text
_reward_walk_to_door
_reward_penalty_face_door
_reward_pregrasp_target_distance
_reward_grasp_target_distance
_reward_a2_stage2_handle_center_y
_reward_a2_stage2_handle_approach_xz
_reward_push_door_handle
_reward_push_door_hinge
_reward_push_door_force
_reward_a2_stage3_unlatch_hold
_reward_a2_stage3_stage4_hold_and_drive
_reward_a2_stage3_stage4_keep_close_command
_reward_target_root_distance
_reward_a2_stage4_grasp_target_distance_mild
_reward_dont_push_door_handle
_reward_penalty_a2_door_body_contact
```

Required treatment:

1. Rename or wrap semantically generic positive handle/hinge terms rather than encoding "pull" as negative joint motion. Positive handle and hinge coordinates remain correct.
2. Keep the currently disabled direct `push_door_force` term disabled. Do not reopen force reward carving before the contact mechanism is measured.
3. Preserve load-bearing grasp income from E2 through E5 until a deliberate release event. A stage transition must not remove it while the task still physically requires retention.
4. Pay latch release and positive hinge progress on both sides of the stage-3/4 boundary.
5. Do not activate final target-root income while outward yield is physically required. Use an event-conditioned path phase.
6. Retain body-panel contact accounting and separate manipulator contact from trunk/leg assistance.
7. Report each component as both episode-sum and normalized `/20s` where cross-run comparisons use time normalization. Never silently mix the two.

## E.7 Tier 1 — v20/v21 send curriculum, corridor, and crossing institution

Known symbols include:

```text
a2_v20_send_latch_enabled
a2_v20_send_hinge_threshold
_a2_v20_send_ready
a2_v20_pre_send_crossing_mode
a2_corridor_latch_mode
_reward_penalty_a2_v20_pre_send_crossing
_reward_a2_corridor_door_wide
_reward_a2_corridor_clean_passage
_reward_target_root_distance
```

Recommendation:

- keep all active v20 send/crossing/corridor curriculum selectors **disabled** in P0–P3;
- port and sign-correct telemetry, not behavior;
- do not reuse `theta_send=0.90` as a pull release or crossing threshold;
- after P2 establishes the E4/E5 distributions, design a pull-specific `clearance_ready` event if a gating institution is needed;
- make the event depend on retained capture, panel angle/clearance, and body pose, not only hinge angle;
- calibrate any threshold from measured decomposition under standing rule 2;
- keep the v20 legacy and send-ready paths byte-compatible for push.

Why: the send curriculum solved a push-specific problem—premature forward crossing before sufficient opening. Pull's required early root motion includes outward retreat opposite the terminal target. Importing the institution before measuring the pull path risks a seventh income-cliff instance.

## E.8 Tier 2 — telemetry and diagnostics

### Required per-control-step fields

```text
door_open_io_sign                         unitless
door_open_lr_sign                         unitless
active_handle_face_x_sign                 unitless
travel_dir_x                              unitless
stage                                     integer
event_state                               enum
root_x_rel_door_m                         m
signed_crossing_progress_m                m
root_velocity_toward_door_mps             m/s
root_velocity_yield_outward_mps            m/s
root_velocity_final_travel_mps             m/s
root_yaw_error_rad                        rad
handle_position_rad                       rad
handle_velocity_radps                     rad/s
latch_position_m                          m
hinge_position_rad                        rad
hinge_velocity_radps                      rad/s
target_tcp_position_error_m               m
target_tcp_orientation_error_rad          rad
bilateral_handle_contact                  bool
hook_contact                              bool or N/A
handle_local_slip_xyz_mps                 m/s
gripper_handle_separation_m               m
finger_pd_effort_estimate_N               N, ESTIMATE_ONLY
finger_effort_utilization_estimate         ratio, ESTIMATE_ONLY
arm_pd_effort_utilization_estimate         ratio, ESTIMATE_ONLY
panel_contact_force_by_body_N              N
frame_contact_force_by_body_N              N
minimum_panel_robot_clearance_m             m if available
reward_component_raw                       per control step
```

### Required per-episode fields

```text
first_E1_step / time_s
first_E2_step / time_s
first_E3_step / time_s
first_E4_step / time_s
first_E5_step / time_s
first_E6_step / time_s
first_E7_step / time_s

proof_hold_duration_s
proof_retreat_displacement_m
max_tensile_retreat_before_loss_m
hinge_at_first_positive_progress_rad
hinge_at_first_grip_loss_rad or N/A
held_hinge_max_rad
hinge_at_release_or_hold_decision_rad
root_outward_excursion_before_clear_m
first_path_reversal_step
release_to_whole_body_clear_s or N/A
hinge_reclosure_after_release_rad or N/A
body_panel_contact_steps_per_20s
body_panel_contact_impulse_Ns
crossing_while_valid_capture
whole_body_clear
terminal_reason
```

### Event funnel and denominators

Report:

```text
P(E1)
P(E2 | E1)
P(E3 | E2)
P(E4 | E3)
P(E5 | E4)
P(E7 | E5)
```

If the conditioning event has zero episodes, report `N/A`, never `0%`.

### Proxy discipline

For implicit actuators, `computed_torque` / `applied_torque` and the existing hold-oracle PD estimator are estimates produced by the actuator model, not true PhysX drive-force measurements. Every field and chart must say `ESTIMATE_ONLY`. These estimates support comparisons of commanded/limited effort utilization inside the same simulator implementation; they do not license a claim about true hardware motor force or true PhysX contact-drive force.

If an estimated hinge-resistance work metric is added from configured drive stiffness/damping, label it `ESTIMATE_ONLY` and keep kinematic hinge progress as the primary non-proxy measurement.

Reuse, after a signed-coordinate audit, the existing handle-local slip decomposition and hold-oracle PD-effort estimator rather than creating competing definitions. Add tests that the same physical slip vector transforms consistently in paired `out` and `in` fixtures. The estimator provenance must remain identical to the v21-B `ESTIMATE_ONLY` contract.

## E.9 Tier 2 — namespace, receipts, and artifact isolation

Create separate schemas and roots for:

```text
source freeze
geometry proof
mechanism manifest
P0 admission
P1 load-to-loss
P2 initialization adaptation
formal training
checkpoint census
Route A
future Route B pooled48 / holdout64
render QA
final analysis
```

Every run receipt must bind:

- source commit and dirty-tree status;
- exact ablation/config path;
- saved resolved config hash;
- checkpoint input/output hashes;
- door scenario manifest hash;
- IO/LR task identity;
- target-frame version;
- hook/friction/finger profile;
- GPU identity;
- start/end time HKT;
- status and failure reason.

Push receipts and logs must remain byte-unchanged.

### Pull freeze guard

Add a pull-specific plan identity and construction-time validator. It must freeze IO/LR, target-frame version, robot side/yaw convention, active actuator profile, hook/friction selectors, stage-time budget, and the disabled state of v20 send/crossing behavior. It must leave `_validate_a2_v20_r1_config` and all v20/v21 plan identities backward-compatible. A pull config that silently resolves to the push target, `door_open_io=["out"]`, final `+X` target, or a different finger profile must fail before the first environment step.

## E.10 No-op set: items already correct

The following should remain unchanged in pull-v0 unless a P0 proof falsifies them:

- right-hinge panel geometry;
- positive-Z hinge axis;
- positive hinge opening coordinate and `0..150 deg` limits;
- closer target at `-10 deg`;
- handle joint axis/limits/return spring;
- latch mimic gearing and left/right handling;
- double-sided handle and optional hook geometry;
- current door dimension, mass, handle-height, handle-torque, and hinge-force ranges;
- action dimension and low-level A2 locomotion interface;
- general termination and safety penalties;
- procedural runtime spawner path;
- `door_open_lr=["right"]` for the first round;
- `add_walls=False` for the first open-space feasibility round;
- push v20/v21 code paths and their artifacts.

Identifying this no-op set prevents the round from wasting time on hinge-sign edits, latch reconstruction, asset-library regeneration, or physics-range expansion.

---

# F. Proposed round structure

## F.1 Round-level dependent variable

Standing rule 12 requires the summary table to contain the round's own dependent variable. The primary DV is:

> **The clean event-funnel probability and retention margin from load-bearing tensile capture through first positive hinge progress, without robot-panel body assistance, stratified by hook, friction, finger-effort, initialization, and door scenario.**

End-to-end success is a secondary DV in this first round.

A mechanics boundary alone is not yet a force-feasibility-aware policy result. It establishes where the task is physically feasible. The stronger project thesis is tested only when a policy exposed to different force limits changes its strategy—capture mode, base yield, arm/base contribution, release timing, or recovery—rather than merely succeeding at one limit and failing at another. P1 maps the boundary; P3/P4 test behavioral adaptation.

## F.2 Phase summary

| Phase | Cells / replicates | GPU scale | Primary DV | Gate status |
|---|---|---:|---|---|
| P0 — source, geometry, and baseline-policy admission | paired in/out fixtures; deterministic assertions; frozen W zero-shot on the unchanged v20 actuator profile | none, then eval-scale and 64-env × 50-iter smoke | geometry/target correctness, baseline behavioral fingerprint, and runtime integrity | hard integrity gate |
| P1 — mechanism landscape | hook × friction × finger profile; paired central fixture and two canonical16 manifests | eval-scale only | load-to-loss, E2→E4 funnel, first-loss mechanism | scientific results are report-only |
| P2 — initialization adaptation | W/S × seeds 0/1/2, 256 env × 750 batches | six small cells when GPUs available | event-funnel learning curve and body-assist-free acquisition | no invented performance threshold |
| P3 — mechanism-targeted adaptation | only the factor identified by P1/P2; matched control and treatment with replicates | small-to-medium | causal change in the binding event | conditional fork |
| P4 — capability-first pull training | selected init × at least two formal seeds, 4096 env × 2500 batches, save250 | formal | E2–E7 funnel, clean opening, whole-body clear | acceptance profile written after measured pilot |
| P5 — pull release candidate | all-checkpoint Route A, render QA | eval | stable end-to-end behavior and event quality | not required for round success |
| P6 — Route B | pooled48 then holdout64 using v21 machinery | eval | generalization across held-out pull scenarios | deferred; no historical precedent |
| P7 — mixed push/pull | separate future round | formal | direction-conditioned success and no interference | out of scope |

At plan time, v21-B occupies GPUs 0–6. P0 implementation and static checks proceed in the parallel worktree. Any P0/P1 runtime probe requiring a GPU must use an explicitly allocated device; P2 waits for a legal allocation. GPU7 is not assumed available merely because a spot measurement shows it idle.

## F.3 P0 — admission before GPU expenditure

### P0-A — source freeze

Hard requirements:

- exact source commit recorded;
- clean worktree or explicitly hashed patch set;
- warm checkpoint hash matches;
- v20 saved config is copied read-only into the pull evidence bundle;
- direction-site manifest is complete;
- pull namespace does not modify push configs or receipts.

### P0-B — static geometry proof

Create deterministic paired doors with identical dimensions:

```text
right/out: target on -X face
right/in:  target on +X face
```

Assertions:

- panel/hinge/latch geometry and joint parameters are equivalent except IO metadata and active target pose;
- positive hinge motion moves the right-hinged panel toward `+X` in both cases;
- target face X sign equals IO sign;
- target belongs to the handle and follows handle/door motion;
- robot pull spawn is on `+X`, yaw near `pi`;
- final target is on `-X`;
- no initial collision or penetration;
- target/pregrasp/TCP axes render correctly.

### P0-C — two-direction architecture smoke

Even though training is pull-only, run at least one `out` and one `in` environment through reset, stage observation assembly, reward computation, and termination. This catches hard-coded pull signs before they spread and is cheaper than a later mixed-task port.

### P0-D — resolved-config and actuator proof

For every probe/training cell, save and inspect the resolved config. It must explicitly state:

- IO/LR;
- target-frame version;
- finger effort, stiffness, damping;
- gripper material/friction profile;
- hook selector;
- v20 send/crossing selectors disabled;
- stage times unchanged unless a later human-approved fork says otherwise.

### P0-E — telemetry finite-data proof

Generate one episode for every terminal reason reachable in the smoke harness. Validate:

- schema completeness;
- finite numeric fields;
- units;
- correct `N/A` handling;
- event ordering;
- no impossible event such as E4 before E3;
- `ESTIMATE_ONLY` provenance stamps.

### P0-F — frozen-policy zero-shot before actuator changes

After the geometry contract passes, evaluate the frozen v20 G4 step2500 policy on paired push and pull manifests using its exact resolved 45 N / 1300 / 32 finger profile and gripper material settings. Do this before the P1 effort or friction matrix. This is the required standing-rule-9 ordering and the first standing-rule-5 policy-as-probe readout. It records the unadapted behavior and verifies that later actuator-profile findings are not being substituted for a missing baseline. Poor pull behavior is report-only and does not choose warm start versus scratch.

### P0-G — canonical smoke

Run the project-standard smoke:

```text
64 environments × 50 training iterations
```

Smoke admission checks runtime, gradients, checkpoint saving/loading, and artifact routing. It has no pull performance threshold. Use the launch and canonical evaluation command conventions from handoff §5 unchanged except for the pull task/config/log namespace.

## F.4 P1 — deterministic and randomized mechanics characterization

### P1-A — central deterministic fixture

Use midpoints of the current source ranges, not a newly invented "easy door":

```text
door width                 0.95 m
door height                2.05 m
handle height              0.95 m
handle edge offset         0.115 m
door mass                  100 kg
hinge max-force parameter  7.25 N·m
hinge stiffness parameter  5.5 N·m/rad
hinge damping parameter    50 N·m·s/rad
handle max-force parameter 2.0 N·m
handle stiffness parameter 50 N·m/rad
handle damping parameter   0.5 N·m·s/rad
axle length                0.195 m
handle length              0.125 m
hook length                0.050 m
handle radius              0.013 m
```

These are deterministic midpoints of the active builder/scenario ranges and exist only as a repeatable mechanism fixture.

> **[AMENDED — see Amendment 2 of `a2_piper_pull_v0_worker_execution_split_20260803.md`: door mass = 120 kg, the midpoint of the RESOLVED v20 G4 `a2_door_weight_range: [80, 160]`, not 100 kg from the repo-default (80, 120).]**

### P1-B — factorial cells

Core factors:

```text
hook:          {absent, present}
finger effort: {10 N, 45 N}
friction:      {resolved baseline, calibrated-low, calibrated-high}
```

This is a 2 × 2 × 3 mechanics matrix. The 10 N level is the current URDF/repository profile. The 45 N level is the v20 G4 resolved profile. Neither is labeled hardware-correct by this experiment.

The low/high friction values are not selected by arbitrary coefficients. Before inspecting policy behavior, use a simple material/contact ramp to choose two values that bracket the resolved baseline's measured load-to-slip curve. Record the selection algorithm and resulting coefficients in a signed calibration receipt. These are simulator mechanism probes, not real-material claims.

### P1-C — paired randomized fixtures

Run every mechanics cell on:

- the deterministic central fixture;
- canonical16 manifest seed 0;
- canonical16 manifest seed 1.

All cells consume the exact same door rows and scripted command profile. Hook presence is the declared factor, not a random draw.

### P1-D — probe sequence

The scripted sequence is diagnostic only and cannot be included in a learned policy or release claim:

1. reset to a verified outside pregrasp;
2. close the gripper under the cell's resolved actuator profile;
3. hold the handle near zero angle and apply a monotone low-speed outward retreat command to create a tensile proof load;
4. record the load-to-loss curve and contact mode;
5. on surviving trials, command positive handle motion to release the latch;
6. command a conservative handle-arc/base-yield profile while maintaining the grasp;
7. stop at first grip loss, body-panel assistance, arm limit, terminal event, or safe fixture endpoint.

The probe establishes mechanism feasibility, not autonomous policy capability. Rule 5 is satisfied later by P2; this probe prevents a policy run from being used to debug an asset-face error.

> **[AMENDED — see Amendment 1 of `a2_piper_pull_v0_worker_execution_split_20260803.md`: before any pull-side verdict is recorded, the identical scripted sequence must first pass a push-side known-good anchor (mirrored `out` fixture, same actuator profile: stable bilateral capture, latch release, ≥0.25 rad hinge progress, no body-panel contact). A pull-side failure without a passing anchor receipt is `PROBE_INVALID`, not a mechanism finding.]**

### P1-E — P1 dependent variables

Report per fixture and cell:

- E2 load-bearing capture rate;
- E3 given E2;
- E4 given E3;
- proof-retreat displacement before loss, m;
- hinge angle at first loss, rad;
- maximum held hinge angle, rad;
- handle-local slip velocity distribution, m/s;
- finger effort utilization estimate, `ESTIMATE_ONLY`;
- arm effort utilization estimate, `ESTIMATE_ONLY`;
- hook contact fraction or `N/A`;
- body-panel assistance rate;
- first-loss classification.

No acceptance threshold is attached. P1's success is a reproducible landscape, including the possibility that every cell fails before E4.

## F.5 P2 — policy-as-probe and initialization experiment

The frozen W zero-shot fingerprint is produced in P0-F before any actuator-profile changes. P2 consumes that immutable receipt and does not rerun or reinterpret it after seeing P1.

### P2-BAW — six-cell adaptation matrix

| Cell | Initialization | Seed | Common actuator profile | Purpose |
|---|---|---:|---|---|
| W0 | v20 G4 step2500 | 0 | v20 G4 resolved | transfer replicate |
| W1 | v20 G4 step2500 | 1 | v20 G4 resolved | transfer replicate |
| W2 | v20 G4 step2500 | 2 | v20 G4 resolved | transfer replicate |
| S0 | scratch | 0 | v20 G4 resolved | basin comparator |
| S1 | scratch | 1 | v20 G4 resolved | basin comparator |
| S2 | scratch | 2 | v20 G4 resolved | basin comparator |

Common budget:

```text
256 environments
750 optimizer batches
checkpoints 250, 500, 750
same pull reward/config/manifests
same staged-reset law
same physical GPUs class
```

Do not change finger effort to 10 N inside this comparison. That would confound initialization with mechanism feasibility.

### P2 predictions

| Prediction | Status | Basis |
|---|---|---|
| Outside-face target correction is necessary for E1/E2 | preregistered hard prediction | current target is provably on -X face |
| Positive hinge/latch coordinate remains valid in pull | preregistered hard prediction | current joint geometry and mimic derivation |
| Pull will show a larger initial outward root excursion than push | preregistered geometric prediction | panel and handle move into +X approach side |
| Body-panel contact will be a material failure/assistance channel | `report_only` rate | geometry predicts exposure but not frequency |
| 10 N will be more limiting than 45 N | `report_only` | plausible tensile-normal-force mechanism, unmeasured |
| Hooks will improve retention | `report_only` | geometry permits engagement, but contact mode is unknown |
| Warm start will learn faster than scratch | `report_only` | transferable skills compete with directional negative transfer |
| Stage 4 will be the dominant failure | not preregistered | no source/runtime basis |

## F.6 P3 — pre-registered mechanism forks

Under standing rule 4 (mechanism over reward carving), only one mechanism family should be promoted into training at a time:

- If P1 identifies finger effort as the limiter while hooks/friction are nonbinding, run a matched 10 N versus 45 N policy adaptation with identical initialization and at least two seeds per level.
- If friction is the limiter, run baseline versus one calibrated material profile; do not combine it with effort changes.
- If hook presence dominates, decide whether hooks are part of the intended real handle family. If yes, stratify task type; if no, exclude hook success from the primary claim.
- If arm workspace, not retention, is the limiter, change the base-yield geometry or event-conditioned path mechanism before reward scales.
- If body contact is required for E4, treat it as a negative result and redesign staging/path; do not merely reduce the collision penalty.

## F.7 P4 — capability-first formal pull training

P4 is authorized only after P1 and P2 establish at least one clean path to E4 in runtime evidence. Its purpose is capability, not release, following standing rule 3 (capability first).

Recommended formal topology follows project convention:

```text
4096 environments
2500 batches
save every 250 batches
at least two formal seeds
all-checkpoint evaluation
```

The selected actuator/mechanism profile is frozen before launch. A realistic 10 N profile may be the scientific target, but standing rule 3 requires first knowing whether it lies inside the feasible region. If 10 N is outside the measured region, the negative finding is reported; it is not rescued by widening door physics or adding hidden body assistance.

P4 acceptance profiles must be written after P2 measurements and before formal training. Integrity and safety remain hard; task-rate thresholds may begin as `report_only` because no pull baseline exists.

## F.8 P5/P6 — release and Route B

Do not run pooled48/holdout64 merely because the apparatus exists. Route B has never run in this project family. It becomes useful after a pull policy has stable, nonzero E7 performance and event-quality telemetry.

When authorized, reuse v21's machinery:

- M22 all-checkpoint census;
- selected checkpoint plus declared selection rule;
- pooled48 across formal replicates;
- holdout64 with immutable manifest;
- strict render QA;
- source/config/checkpoint hash binding.

Do not inherit push numerical thresholds. Measure a pull baseline first and apply the v21-B anti-block doctrine.

## F.9 P7 — mixed push/pull

Pull-only training should precede mixed training for scientific isolation, but the implementation must not be pull-hard-coded. Mixed training is a separate round after:

- both directions pass geometry/runtime tests;
- `doorOpenIO` is explicit in state and logs;
- the policy observation contract for IO is decided;
- push and pull each have nonzero clean event funnels;
- evaluation is stratified by IO and does not average away one failed direction.

## F.10 Standing-rule-1 income-continuity audit

Every behavioral target must be paid across every stage or threshold boundary it spans.

| Behavioral target | Physical span | Income before boundary | Income after boundary | Required continuity test |
|---|---|---|---|---|
| outside-face alignment | E1 through first stable E2 | target pose/orientation | retained low-weight alignment while capture forms | no disappearance at stage 1→2 |
| load-bearing capture | E2 through deliberate E5 release | capture/contact stability | same capture income through stage 3 and early stage 4 | no unpaid hold interval |
| latch release | late E2 through E3 | handle progress under valid capture | latch-retracted/handle-safe income | no cliff exactly at stage 2→3 |
| positive hinge progress | E3 through E5 | positive hinge motion under valid capture | continued held progress/clearance | no stage 3→4 drop while opening remains required |
| outward base yield | E4 until clearance | geometric yield/arc income | remains active until clearance event | final target must not oppose required retreat |
| collision-free sweep clearance | E4 through E6 | clearance margin | clearance/entry margin | no threshold that removes clearance before body is safe |
| deliberate release or maintained hold | E5 | decision-quality/intent signal | post-release arm neutralization or continued-hold quality | accidental loss cannot earn release income |
| final traversal | late E5/E6 through E7 | entry progress after clearance | signed final-target/whole-body-clear income | no target appearing only after an unreachable threshold |
| post-clear stability/disentanglement | E7 and short terminal window | approach to full clear | terminal stability income | root crossing alone cannot terminate payment |

For each cell, the worker must emit an income trace around every event boundary and report component shares as episode-sum and `/20s`. Rule 2 then calibrates weights from measured decomposition. No reward scale is chosen in this plan without that measurement.

---

# G. Risks and pre-registered forks

| Trigger | Interpretation | Response / unblock path | Prohibited response |
|---|---|---|---|
| P0 target is on far face | asset task target is wrong | fix IO-aware target in builder; rerun paired geometry proof | tune rewards around a wrong target |
| Target point is correct but orientation error is large | target-frame axes are wrong | derive target rotation from frame overlay; add transform test | assume yaw `pi` fixed it |
| Positive handle motion does not retract latch | handle/latch convention or target wrist motion is wrong | isolate joint/mimic test; preserve hinge sign until proven otherwise | flip hinge and latch together |
| E2 denominator is zero | no load-bearing capture | report downstream conditional rates as `N/A`; use P1 matrix to classify mechanism | report 0% E3/E4 as if attempted |
| Hook-on succeeds, hook-off fails | geometric engagement is binding | human decides whether hook handles are in task scope; stratify claims | call the result friction-limited |
| 45 N succeeds, 10 N fails | finger-force feasibility boundary exists in simulator | report boundary; run matched policy ablation if authorized; obtain hardware profile | widen door physics or hide the 10 N result |
| Friction profile changes outcome while hook/effort do not | surface interaction is binding | freeze one calibrated contrast for P3 | stack friction, effort, reward, and timing changes |
| All mechanics cells fail before E3 | target/contact geometry or handle actuation is infeasible | stop policy training; inspect gripper/handle geometry and wrist path | spend 4096-env runs on reward tuning |
| E3 succeeds but E4 fails cleanly | arm/base/hinge transmission limit | inspect effort/workspace and base-yield traces; change mechanism/path | blame stage-4 success target |
| E4 occurs only with trunk/leg panel contact | body assist is carrying the door | classify as negative clean-feasibility result; redesign staging/trajectory | lower collision penalty or count as clean success |
| Arm joint margin collapses before grip loss | workspace is binding | derive feasible base-yield corridor from P1; retrain with event-conditioned geometry | increase arm effort first |
| Door recloses into robot after release | closer/clearance timing failure | defer release, change clearance event or maintain hold; measure post-release decay | invert or remove closer spring |
| Final target causes early inward motion | income conflict at path reversal | gate final traversal on measured clearance event; preserve outward yield income | add stronger final target reward |
| Warm cells preserve wrong-direction behavior | negative transfer | prefer scratch if replicated; inspect policy action/obs semantics | decide from best warm seed only |
| Scratch cells split across basins | historical seed instability recurs | add matched replicate or use warm operational default with unresolved label | report one successful scratch seed as stable |
| W versus S is inconclusive | adaptation window lacks power | add one matched replicate per initialization or freeze W operationally without causal claim | move thresholds after seeing results |
| v21-B winner appears during P2 | new candidate may help | include only after saved config/hash/render audit, as a third matched initialization | silently replace W |
| GPU7 appears idle | availability remains unconfirmed | obtain explicit human authorization and record measurement | schedule required work on GPU7 by assumption |
| Pre-existing overspeed appears | defect not introduced by pull | report against measured baseline; do not zero-tolerance block task science | declare round invalid at first event |
| Route B fails first execution | no historical pooled precedent | classify infrastructure/schema/task failure; use named unblock path | change release thresholds post hoc |
| Source manifest finds unclassified world-X sites | integrity risk | block formal implementation until classified and tested | proceed because smoke happened to run |
| True implicit actuator force is unavailable | proxy limitation | retain `ESTIMATE_ONLY`, constrain claims to simulator estimator | call proxy true motor or PhysX force |

A "stop and escalate" outcome is valid when the response requires a human task-scope or hardware decision. Every stopped branch must preserve the evidence bundle and name the next deciding probe.

---

# H. Open questions requiring a human or planner-arbiter decision

1. **Active target representation.** Approve the recommended single conditional `grasp_target`, or require explicit `grasp_target_inside` / `grasp_target_outside` prims. The former preserves checkpoint/config topology; the latter is more verbose for mixed-task debugging.
2. **Target-frame orientation convention.** P0 will produce the overlay; a human only needs to arbitrate if two conventions both satisfy static alignment but imply different wrist behavior.
3. **Authoritative finger profile.** Confirm whether the hardware-grounded continuous force limit is 10 N per prismatic finger, another value, or unknown. Until then, 10 N and 45 N are simulator profiles, not "realistic" and "unrealistic" labels.
4. **Hook task scope.** Decide whether the procedural hook represents intended real lever handles. This determines whether hook-dependent success counts toward the primary task family or a separate handle subtype.
5. **Release policy.** Decide whether release before traversal is a North-Star requirement, or whether deliberate maintained hold through crossing is also valid. The first round records both without rewarding accidental loss.
6. **Open-space versus constrained-space charter.** Approve `add_walls=False` for pull-v0 mechanism/capability isolation. Enabling walls creates a separate geometry factor and should not be bundled silently.
7. **Policy observation for IO.** For pull-only warm start, the recommendation is to preserve observation shape and keep IO explicit in environment state/telemetry. Mixed training must add or formally derive a direction-observation contract. Approve whether that observation change happens now with checkpoint surgery or in the mixed round.
8. **Future v21-B checkpoint.** Decide whether a qualified v21-B winner is added as a third initialization if it becomes available before P2 freezes.
9. **GPU7.** Confirm whether GPU7 may be used. No phase in this plan depends on it.
10. **Namespace naming.** Approve `door_open_a2_pull` / `a2_piper_pull_v0`, or provide the project-standard alternative before files and receipts are created.
11. **First release threshold authority.** Decide who signs the first measured pull acceptance profile after P2. Workers may not invent or relax numerical task thresholds independently.

---

# I. Explicit disagreement register

The peer file itself was unavailable on the current remote branch, so this register addresses the claims quoted in the task request. It does not manufacture agreement or disagreement with unseen details.

| Peer claim | Verdict | Independent reasoning | Evidence that settles it |
|---|---|---|---|
| Pull must be implemented by mirroring the robot rather than the door | **Partly agree, materially incomplete** | The physical panel/hinge should remain; the robot side must change. But the asset-attached `grasp_target` is hard-coded to the inside `-X` face and must become IO-aware. | `door.py::handle_inside`, `handle_outside`, and `grasp_target`; P0 paired target proof |
| Force transmission changes from form closure to friction | **Disagree as a pre-established conclusion** | Pull changes compression to tensile retention, but current lever, two-finger geometry, palm contacts, and optional hooks can create frictional or geometric retention. Source does not identify the binding mode. | P1 hook × friction × finger-effort load-to-loss matrix and contact classification |
| Stage-4 through-target is the central design risk | **Disagree with the ranking** | A stage-4 target may be wrong, but no runtime evidence says it is first. Target-face correctness, tensile capture, latch-to-hinge coupling, panel sweep, and non-monotone root motion precede it. The deeper target issue is the event-triggered reversal of desired root direction. | P0 geometry, P1 E2→E4 funnel, P2 root trajectory and income traces |
| Pull-only should precede mixed push/pull | **Agree operationally; disagree architecturally if it means hard-coded pull signs** | Pull-only isolates a new task and force regime. The code should still instantiate both directions in tests and centralize direction semantics now. | two-direction P0 smoke; later stratified mixed-task round |
| A zero-shot probe should decide warm start versus scratch | **Disagree** | Zero-shot diagnoses transfer behavior but confounds direction with absence of adaptation. Historical scratch basin instability also requires replication. | W/S × three-seed bounded adaptation with event-funnel curves |
| The door asset needs no change | **Disagree if "asset" includes the task target; agree for physical panel mechanics** | Hinge, panel, latch, and double-sided handle are correct. The active grasp target is not. | current `grasp_target` X coordinate and P0 target-face test |
| The prior pull branch should be rebased | **Disagree** | It is v10-era, never simulated, and targets obsolete environment structure. Semantic ideas may be manually ported after rederivation. | current source-manifest diff and runtime tests |

> **[Local planner note (2026-08-03): this register was written without access to the local analysis document (unpushed at the time). Rows 1 and 7 are in fact agreements with that document's Tier A2 and §4. A follow-up audit round against the full documents is authorized but non-blocking — see Amendment 3b of the execution split document.]**

---

# Appendix A — Immediate worker build order

1. Freeze source, checkpoint, and saved config hashes.
2. Create the separate worktree and namespace.
3. Generate the complete direction-site manifest with local `git grep`.
4. Add the immutable direction contract and unit tests for `in` and `out`.
5. Make `grasp_target` active-face-aware in `spawn_door`; do not alter hinge/latch signs.
6. Add paired target/TCP/frame debug render and static assertions.
7. Add pull reset, yaw, signed staging, and signed final target.
8. Add event-state telemetry and `ESTIMATE_ONLY` effort provenance.
9. Keep v20 send/crossing behavior disabled; add signed telemetry only.
10. Run the frozen W paired push/pull zero-shot on the exact resolved v20 actuator profile before changing effort or friction.
11. Run P0 two-direction architecture smoke and 64-env × 50-iteration smoke.
12. Run the P1 mechanism matrix before any formal policy training.
13. Run the six-cell W/S bounded-adaptation experiment after GPU availability is confirmed.
14. Sign a single adaptation/acceptance decision from measured P1/P2 results.
15. Launch P3 or P4 only along the pre-registered fork.

> **[AMENDED — see Amendment 3a and §4.1 of `a2_piper_pull_v0_worker_execution_split_20260803.md`: the pull plan-id freeze-guard branch on `_validate_a2_v20_r1_config` is inserted as step 3 (immediately after source freeze and the direction-site manifest, before any env/asset edit). The 15-step amended order in that document supersedes this list.]**

---

# Appendix B — Negative results that count as round success

The following are scientifically useful outcomes when produced by a clean, complete evidence bundle:

- the outside-face geometry is correct, but no tested mechanism achieves E2 under the current gripper;
- E2 occurs only with hooks and therefore does not generalize to unhooked lever handles;
- 45 N succeeds while 10 N fails, establishing a simulator finger-force feasibility boundary;
- E3 occurs but E4 does not under any clean no-body-contact condition;
- E4 requires robot-panel body assistance, falsifying a clean gripper/arm-only claim;
- arm workspace, not effort, is the first binding constraint;
- the closer makes every tested release policy recontact before whole-body clearance;
- warm and scratch adaptation both fail at the same physical event, localizing the problem to mechanism rather than initialization;
- warm start exhibits replicated directional negative transfer while scratch acquires the pull event funnel;
- scratch remains basin-unstable, confirming that a larger exploration/reset intervention is needed;
- open-space pull works but adding walls later breaks the base-yield corridor, defining the next task boundary.

None of these should be relabeled as "the round failed." The round fails only if it does not preserve enough controlled evidence to distinguish these mechanisms.

---

# Appendix C — Scope exclusions

The first round explicitly excludes:

- RGB/student distillation and camera changes;
- mixed push/pull training;
- left-hinged pull doors;
- full-room walls and constrained corridor randomization;
- widening door mass or hinge-force ranges as a feasibility axis;
- posture-economy shaping as a minimal intervention;
- heavy-door body-assist emergence under a superhuman arm;
- velocity-limit changes bundled with finger/effort changes;
- scripted arm trajectories in any release policy;
- reward-scale rescue before the physical limiter is measured;
- a Route-B release claim without a stable pull policy and a measured acceptance profile.

These exclusions preserve the closed dead ends in the handoff. A later round may reopen one only with an explicit argument and a changed precondition, such as a hardware-grounded force-limited actuator profile.

---

# Appendix D — Required round summary table schema

Every final pull-v0 report must include a table with at least:

| Cell | Source/checkpoint | Init | Seed | IO/LR | Hook | Friction | Finger N | E1 | E2 | E3\|E2 | E4\|E3 | E5\|E4 | E7\|E5 | Clean E4 | Body assist | Held hinge max rad | First-loss mode | Goal | Unit/provenance |
|---|---|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|

Rules:

- conditional zero denominators are `N/A`;
- event rates state numerator and denominator;
- angle is rad, distance m, time s, control latency control steps plus s;
- reward is labeled episode-sum or `/20s`;
- implicit-actuator effort is `ESTIMATE_ONLY`;
- the table contains the pull round's event-funnel DV, not only inherited push goal/crossing metrics;
- best-checkpoint results are accompanied by all-checkpoint trajectories and selection rule.

---

# Final round interpretation rule

The first pull-door round answers three questions in order:

1. **Is the source/task geometry correct?**
2. **Which physical mechanism, if any, transmits tensile handle load through latch release into positive hinge motion without body assistance?**
3. **Given a feasible mechanism, which initialization and learning path acquire the full pull event funnel?**

Only after those questions are measured should the project ask for release thresholds, mixed push/pull, student distillation, or constrained-room generalization.
