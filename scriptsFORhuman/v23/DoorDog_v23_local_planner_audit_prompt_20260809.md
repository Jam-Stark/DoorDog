# DoorDog base_v23 — Local Planner Independent Audit Prompt

**Use this prompt with the local planner session.**  
This is a source-first audit and plan-freeze task. Do not implement code or launch training in the planner session.

## 0. Role

You are the independent planner and scientific-admission reviewer for the DoorDog A2+PiPER push-door teacher-policy project.

Repository:

```text
https://github.com/Jam-Stark/DoorDog
branch: A2_Piper
```

Primary design input:

```text
DoorDog_v23_training_design_v0.1_20260809.docx
```

The design proposes:

```text
Initialization × Door Force Regime × Posture Availability
= 2 × 2 × 2 factorial
= 8 formal cells
= 4096 environments per cell
= physical GPU0–7
```

Your job is to determine whether the design can be implemented and interpreted correctly against the actual repository. You must read source before accepting the document's assumptions.

## 1. Permitted decisions

Return exactly one:

```text
DECISION = APPROVE_IMPLEMENTATION
DECISION = APPROVE_WITH_BOUNDED_PATCH
DECISION = REVISE_DESIGN_BEFORE_IMPLEMENTATION
DECISION = BLOCK_V23
```

Definitions:

- `APPROVE_IMPLEMENTATION`: all scientific axes and execution contracts are source-supported and fully frozen.
- `APPROVE_WITH_BOUNDED_PATCH`: the design is retained, but a finite list of implementation/admission repairs is required before worker execution.
- `REVISE_DESIGN_BEFORE_IMPLEMENTATION`: one or more causal comparisons are not identifiable or cannot be implemented as specified.
- `BLOCK_V23`: source/evidence is insufficient to define a safe, interpretable experiment without a new design.

Do not approve by relying on the design document alone.

## 2. Mandatory reading order

### 2.1 Read actual source before the v23 design

Inspect at minimum:

```text
gr00t/rl/envs/door/door_open_a2_base.py
gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py
gr00t/rl/trl/modules/actor_critic_modules_recurrent.py
gr00t/rl/eval_agent_trl.py

gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml
gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml
gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml
gr00t/rl/config/env/door_open_a2_base.yaml

gr00t/rl/isaac_utils/playground/env_rand/door.py
gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py
gr00t/rl/data/robots/A2_Piper/a2_piper.urdf

scriptsFORhuman/a2_piper_longterm_TODO.md
scriptsFORhuman/v22/
memory/a2-piper/base-v22-posture-clearance/
```

Also locate the exact v22 selected checkpoint and saved runtime config that the v23 design intends to use as the warm start. Do not infer the warm start from a README.

### 2.2 Then read the v23 design and references

```text
DoorDog_v23_training_design_v0.1_20260809.docx
Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer
RoboDuet: Learning a Cooperative Policy for Whole-body Legged Loco-Manipulation
PiPER quick-start manual and official SDK/URDF references
DoorDog centralized-critic/coupling research notes
DoorDog v21 force-feasibility design notes
```

DoorMan is relevant for staged-reset exploration, stage-conditioned rewards, and broad door-physics randomization. It does not define DoorDog's exact torque limits or reward weights. RoboDuet is relevant for learned pitch/roll guidance and whole-body workspace expansion. It does not establish that a fixed height-to-pitch heuristic is correct for DoorDog.

## 3. Scientific invariants that must be preserved

The planner may patch implementation details, but must not silently change these v23 questions:

1. How much of persistent `0.4 pitch` is inherited from warm-start behavior?
2. Is the current D0 door family solvable without active roll/pitch?
3. Does a near-boundary D1 family create a causal FULL-versus-RP0 gap?
4. Can an `arm + posture infeasible` E2 region be established using valid grasp, high effort, low progress, and counterfactual rescue?
5. Does posture use become selective across E0/E1 rather than universally saturated?

The core matrix remains:

| Group | Initialization | Train regime | Posture |
|---|---|---|---|
| G1 | v22 warm | D0 | FULL |
| G2 | v22 warm | D0 | RP0 |
| G3 | scratch | D0 | FULL |
| G4 | scratch | D0 | RP0 |
| G5 | v22 warm | D1 | FULL |
| G6 | v22 warm | D1 | RP0 |
| G7 | scratch | D1 | FULL |
| G8 | scratch | D1 | RP0 |

Unless the planner selects `REVISE_DESIGN_BEFORE_IMPLEMENTATION`, it must not replace this factorial with a reward-only experiment.

The following remain outside v23 core and must be written to the long-term TODO rather than implemented:

```text
true PiPER hardware torque calibration
full Coulomb/stiction/breakaway hinge model
dynamics-oracle actor input and deployable system identification
three-branch factorized PPO actor
intervention-supervised coupling critic driving actor updates
counterfactual branch PPO
learned sparse posture gate
handoff/downstream critic
body-assist curriculum
student dynamics/coupling distillation
```

## 4. Required source audits

### 4.1 Actor/action semantics

Resolve and cite exact symbols for:

- the 12D high-level action layout;
- the 5D base-command layout;
- the exact roll and pitch indices;
- action normalization/de-normalization;
- the semantic neutral command for roll and pitch;
- how the frozen A2 policy consumes the 5D command;
- whether command pitch/roll and achieved trunk pitch/roll use the same ordering and sign.

Reject any plan that assumes "the last two dimensions are roll/pitch" without source proof.

### 4.2 RP0 identifiability

Determine how to implement chronic RP0 so that:

```text
executed posture command is neutral
masked posture dimensions contribute zero to log-prob
masked posture dimensions contribute zero to entropy
masked posture dimensions contribute zero to KL
masked posture dimensions contribute zero to PPO ratio
unmasked actions remain sampled and optimized normally
```

A post-log-prob action clamp is forbidden.

State whether the current actor implementation supports a masked distribution without changing parameter count. If not, specify the smallest parameter-matched design.

### 4.3 Warm-start and scratch fairness

Resolve:

- exact warm-start checkpoint path and SHA-256;
- exact adjacent saved-config path and SHA-256;
- whether `policy_only` loads actor mean, recurrent weights, and log-std;
- scratch initialization convention;
- whether warm and scratch can use the same actor/critic architecture;
- whether the current v22 reward registry is scratch-capable.

Audit all early-stage rewards. Identify which approach, pregrasp, grasp, unlatch, and initial-opening rewards must be restored or retained for **all eight groups**, not only scratch groups.

### 4.4 Torque authority and telemetry

Trace the actual torque path from action to actuator. Resolve:

- commanded joint target;
- nominal PD torque, if available;
- clipped/applied torque source;
- per-joint effort limits;
- whether `self.torques` is commanded, solver-reported, or another quantity;
- torque units and update rate;
- any mismatch between 200 Hz physics and 50 Hz control.

The v23 design may use `tau_boundary_calibrated`. It must not call a ladder-selected profile "real PiPER torque" unless a verified manufacturer source supports it.

### 4.5 Door resistance model

Resolve actual runtime source and units for:

```text
door mass / inertia
hinge damping
hinge stiffness
hinge max-force / resistive-torque cap
friction, stiction, or breakaway approximation
latch dynamics
```

State which axes are independently controllable today. Do not treat damping as static friction.

### 4.6 E0/E1/E2 implementability

Verify that a scenario/state can be labeled with:

```text
valid grasp
high effort
low hinge progress
failure exclusion
higher-effort rescue
oracle tangential-assist rescue
```

Resolve whether exact simulator-state clone plus recurrent-history clone is currently possible. If not, define a reproducible prefix-replay alternative and state its limitations.

### 4.7 Staged-reset ownership

List every v23 state variable that must round-trip through staged reset, including:

```text
torque-window accumulators
grasp streaks
high-effort streaks
low-progress windows
E0/E1/E2 labels
RP0 mode
intervention mode
derivative warm-up state
scenario identity
```

Reject any design that loads a stage snapshot without restoring the variables that affect reward, termination, evidence, or classification.

### 4.8 GPU and runtime contract

Verify the current GPU lease. The intended formal mapping is:

```text
G1 -> physical GPU0
G2 -> physical GPU1
G3 -> physical GPU2
G4 -> physical GPU3
G5 -> physical GPU4
G6 -> physical GPU5
G7 -> physical GPU6
G8 -> physical GPU7
```

Each group must run:

```text
4096 environments
same formal batch budget
same checkpoint cadence
one process per GPU
```

If the lease differs, do not silently remap. Record the lease artifact and revise the execution schedule explicitly.

## 5. Required scientific-admission outputs

The planner must freeze all of the following before approving worker implementation.

### 5.1 Exact warm start

```text
warm_start_checkpoint_path
warm_start_checkpoint_sha256
warm_start_saved_config_path
warm_start_saved_config_sha256
checkpoint_load_mode
```

### 5.2 Formal training budget

```text
num_envs = 4096
num_total_batches
save_frequency
training seeds
rollout length
minibatches
learning epochs
learning-rate schedule
```

### 5.3 D0 source lock

Define D0 as an exact source-locked distribution or finite manifest. No prose-only "current doors."

### 5.4 P0 atlas contract

Freeze the initial effort ladder and door-resistance atlas. Runtime-selected values may remain typed as:

```text
P0_CALIBRATION_REQUIRED
```

but the selection rule, range bounds, and artifact schema must already be fixed.

### 5.5 E0/E1/E2 certificate thresholds

Thresholds may be finalized from P0 data, but the planner must define:

- raw producer;
- aggregation;
- allowed range;
- freeze timing;
- strict consumer;
- typed insufficient-data outcome.

### 5.6 Common reward registry

Provide the exact reward components and stage scopes shared by warm and scratch. Include a stationary-rent audit.

### 5.7 Checkpoint selection rule

Create a mechanical, preregistered rule for each run. It must not select by endpoint preference or reward mean alone.

### 5.8 Route-A and Route-B topology

At minimum define:

```text
Route A:
  10 checkpoints/run
  canonical16
  exact record and raw-trace schema
  8 groups × 2 seeds × 10 checkpoints = 160 checkpoint evaluations

Route B:
  selected pooled48
  E0/E1/E2 stratified evaluation
  matched intervention/state-bank evaluation
  holdout64 for final candidates
  strict render if any policy claim depends on motion quality
```

### 5.9 Worker adaptation authority

Define a bounded mechanism that prevents numerical scientific gates from blocking all execution:

- hard integrity/safety gates are non-waivable;
- P0 may calibrate scientific thresholds before formal training;
- a worker may continue with `RESEARCH_CONTINUATION` after a scientific miss if evidence remains valid;
- a waiver cannot relabel a failed release gate as a release;
- all adaptations must be frozen before the data they govern are inspected.

## 6. Required planner deliverables

Create repository-ready files:

```text
scriptsFORhuman/a2_piper_base_v23_force_feasibility_initialization_posture_plan_R1_20260809.md

scriptsFORhuman/v23/V23_SCIENTIFIC_MANIFEST.json
scriptsFORhuman/v23/V23_SELECTION_RULE.json
scriptsFORhuman/v23/V23_PLANNER_DECISION.md
scriptsFORhuman/v23/V23_SOURCE_AUDIT.md
scriptsFORhuman/v23/V23_IMPLEMENTATION_PATCH_TABLE.md
```

The manifest must not disguise unresolved runtime values as frozen numbers. Use typed states such as:

```text
P0_CALIBRATION_REQUIRED
SOURCE_AUDIT_REQUIRED
INSUFFICIENT_DENOMINATOR
NOT_IMPLEMENTABLE_WITH_CURRENT_STATE_CLONE
```

## 7. Required planner response format

```text
DECISION = <one permitted decision>
FORMAL_TRAINING_READY = false
WORKER_IMPLEMENTATION_MAY_START = yes | no
SCIENTIFIC_MATRIX = retain | revise
LEGAL_PHYSICAL_GPUS = <exact set>
WARM_START = <exact checkpoint and hash, or unresolved>
PRIMARY_BLOCKER = <one sentence or NONE>
```

Then output only:

1. `SOURCE FACTS`
2. `DESIGN AUDIT`
3. `PATCH TABLE`
4. `FROZEN SCIENTIFIC CONTRACT`
5. `P0 ADMISSION`
6. `TRAINING AND EVALUATION DAG`
7. `WORKER HANDOFF`
8. `LONG-TERM TODO PATCH`
9. `STOPPING RULES`

Every substantive claim must cite an exact repository path, symbol, config key, or evidence artifact. Mark unsupported items `UNKNOWN` or `INCONCLUSIVE`; do not fill them with general robotics assumptions.
