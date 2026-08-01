# A2+Piper DoorDog — base_v21 Implementation, Training, and Route-B Execution Plan

**Plan ID:** `base_v21_theta_dose_arm_tie_v1`  
**Execution ID:** `base_v21_execution_v1`  
**Date:** 2026-08-01 HKT  
**Repository:** `Jam-Stark/DoorDog`  
**Start branch / commit:** `A2_Piper` / `d4a0563850dee52be4f3a6fa79405c84e33ade30`  
**Worker workspace:** `/home/baoquanc/workspace/DoorDog-A2_Piper`  
**Legal physical GPUs:** `0–6`; **GPU7 is forbidden**  
**Status:** implementation may start immediately; **formal v21 training is conditional on the validation phase in Section 0**.

---

## Decision block

```text
V21_PRIMARY_QUESTION = does physical crossing track theta_send as a clean dose response?
PRIMARY_AXIS = theta_send in {0.90, 1.10, 1.20, 1.25, 1.30} rad
COMMON_POLICY_FAMILY = v20 G4 send curriculum + traversal economics
WARM_START = v20 G4 step2500, policy_only
EFFORT_LIMIT_CHANGES = OUT_OF_SCOPE
VELOCITY_LIMIT_CHANGES = OUT_OF_SCOPE
STAGE_TIME_CHANGES = OUT_OF_SCOPE FOR TRAINING AND RELEASE SELECTION
ARM_TIE = CONDITIONAL SECONDARY FACTOR; calibrate first or skip
ONE_SHOT_HIGH_THETA_PILOT = theta_send 1.25, seed0, 256 env, 750 batches
FULL_RELEASE_REQUIRES = strict Route B + pooled48 + holdout64 + strict render + final analysis
GPU7 = FORBIDDEN
```

### Why v21 is not yet formal-ready

The implementation and experiment design are ready, but formal training must not start until the worker has:

1. verified that `theta_send`, not the legacy hard-coded `hinge >= 1.0` corridor branch, is the active boundary in every v21 cell;
2. added mechanism-complete telemetry for send-latch-to-crossing behavior;
3. run a frozen-policy five-level theta probe;
4. calibrated arm-tie to a non-negligible but bounded positive-income share, or explicitly disabled the arm-tie branch;
5. completed exactly one `theta_send=1.25` pilot and frozen the adaptation decision before formal training.

Failure of the high-theta or arm-tie branch **does not block the entire round**. The lower-dose theta experiment continues under the state machine defined below.

---

# 0. Pre-formal validation experiments and implementation admission

## 0.1 Source identity and immutable warm start

Before any code change:

```bash
cd /home/baoquanc/workspace/DoorDog-A2_Piper
git fetch origin
git checkout A2_Piper
test "$(git rev-parse HEAD)" = "d4a0563850dee52be4f3a6fa79405c84e33ade30"
git status --short

git checkout -b codex/a2-piper-base-v21-theta-dose-20260801
```

Worker must locate and hash:

```text
logs_rl/a2_piper_full_stage_a2_base/
  base_v20_R3_G4-20260731_004712/model_step_002500.pt
```

Expected checkpoint SHA-256 from the independently audited v20 corpus:

```text
f000f13e817309f7b73e33c5c4d95076397debb992713e5613dce567bfda806d
```

If path or hash differs, stop before implementation and issue `V21_INPUT_BINDING_BLOCKER.json`. Do not substitute another checkpoint.

## 0.2 V0-A — active-boundary source audit

The worker must prove with source tests and resolved configs that every v21 cell uses:

```yaml
a2_corridor_latch_mode: send_ready_v20
```

The active behavior must be:

```text
send_ready := valid_hold_streak AND hinge >= theta_send
pre-send crossing gate := root_x beyond margin while NOT send_ready
corridor latch := send_ready
stage-4 target-root ramp origin := theta_send
```

The legacy branch:

```text
root_x_ever_crossed OR (stage >= SWING AND hinge >= 1.0)
```

must remain available only for backward-compatible v20 configs and must be unreachable from every v21 formal config.

### Mandatory source tests

Add tests that fail if:

- any enabled v21 config resolves to `legacy_root_or_hinge`;
- the send latch, crossing shortfall, and target-root ramp resolve different theta values;
- an independent `1.0` pay boundary is introduced in the v21 path;
- a v21 config changes stage time, arm effort, arm velocity, physics randomization, reward terms, or the S/E schedule outside the declared theta/A/seed factors.

## 0.3 V0-B — mandatory mechanism telemetry

The existing trace already carries `send_ready`, root crossing, hinge, root-x, task-space and income fields. v21 must make the send-to-cross interval explicit and mechanically auditable.

### Required per-step fields

```text
send_latch_event                     bool
send_ready                           bool
root_crossing_event                  bool
root_x_rel_m                         float
hinge_position_rad                   float
bilateral                            bool
stage                                int
positive_arm_tangent_mps             float
positive_base_tangent_mps            float
taskspace_active                     bool
terminal / terminal_reason
```

### Required per-episode fields

```text
first_send_step
hinge_at_send_latch_rad
root_x_at_send_latch_m
first_crossing_step
hinge_at_crossing_rad
root_x_at_crossing_m
send_to_cross_control_steps
send_to_cross_s
hinge_delta_send_to_cross_rad
root_delta_send_to_cross_m
time_to_send_s
time_cross_to_goal_s
root_forward/lateral/planar/yaw_max_pre_send
positive_arm_tangent_integral_m
positive_base_tangent_integral_m
arm_tangent_integral_share
positive_A_income_ratio
held_hinge_max_rad
root_x_at_last_bilateral_m
crossing_while_holding
goal
stage_overtime / upper_dof_overspeed
```

### Exact integral definition

For raw control frames satisfying the existing valid task-space mask before send:

```text
arm_integral  = sum(positive_arm_tangent_mps * control_dt)
base_integral = sum(positive_base_tangent_mps * control_dt)
arm_integral_share = arm_integral / (arm_integral + base_integral)
```

Return `N/A`, never zero, when the denominator is absent.

## 0.4 V0-C — torque telemetry: preferred, non-blocking for the theta round

Add observability-only torque telemetry when it can be done without altering control semantics:

```text
arm_torque_utilization_6d = abs(applied_clipped_torque_i) / torque_limit_i
arm_torque_utilization_max
arm_torque_argmax_joint
fraction_of_valid_frames_ge_0.90
fraction_of_valid_frames_ge_0.98
first_joint_ge_0.98
per-joint p50/p95/max
```

The source of truth must be the torque actually sent after clipping, not an unclipped PD request.

**This telemetry is diagnostic in v21.** It must not change torque limits, Kp, Kd, action scale, rewards or observations. If the worker cannot add it safely without touching the control path, emit:

```text
TORQUE_TELEMETRY_DEFERRED
```

with the exact reason and proceed with the theta round. No real-hardware force-feasibility claim is then permitted.

## 0.5 V0-D — frozen-policy theta ladder, no optimizer updates

Evaluate the frozen v20 G4 step2500 checkpoint at:

```text
theta_send = 0.90, 1.10, 1.20, 1.25, 1.30 rad
```

All other values must equal v20 G4. Run:

1. canonical16;
2. a fixed, preregistered heavy16 manifest with `door_weight >= 140 kg` and `hinge_force >= 10 N·m`, balanced over available handle heights and other scenario dimensions.

The heavy16 manifest must be generated once, written to JSON, hashed, and reused for all five rungs. No seed or scenario fishing.

### Required readout

For every theta and scenario bucket report:

- goal and crossing-while-holding;
- hinge at send latch and crossing;
- `hinge_delta_send_to_cross` and `send_to_cross_s`;
- held hinge max;
- stage overtime and overspeed;
- pre-send root reconfiguration;
- arm integral share;
- optional torque utilization.

### Interpretation only, not a training gate

This zero-shot probe determines whether high theta is physically reachable by the frozen policy and whether failure is predominantly:

```text
NO_SEND_LATCH
SEND_LATCH_THEN_OVERTIME
SEND_LATCH_THEN_RELEASE_OR_HOLD_FAILURE
SAFETY_FAILURE
```

Poor zero-shot performance is not grounds for changing theta, stage time or rewards. It also does not by itself cancel the one-shot pilot.

## 0.6 V0-E — arm-tie calibration, no training

The v20 arm-tie earned less than one percent of positive income and did not bind. v21 must not train an A cell until the scale is calibrated.

### Calibration method

Use one fixed, telemetry-complete evaluation of the frozen G4 checkpoint. Prefer offline recomputation from unscaled raw A components so all candidate multipliers consume identical trajectories.

Keep the ratio between the two A terms fixed at the v20 ratio:

```text
arm_tangent : arc_tracking = 3.5 : 0.85
```

Sweep one common multiplier:

```text
m in {1, 2, 4, 8, 12, 16, 24}
```

The worker may replace this set with another monotone discrete grid only before any training, provided:

- the ratio remains fixed;
- maximum multiplier is no greater than 24;
- the selection algorithm is written before the result is inspected.

### Preferred calibration envelope

```text
positive A-income ratio p50: 2%–5%
positive A-income ratio p95: <=8%
nonzero A income: >=12/16 canonical episodes
valid task-space coverage: >=10% of pre-send bilateral positive-hinge frames
```

### Relaxed calibration envelope

```text
positive A-income ratio p50: 1.5%–6%
positive A-income ratio p95: <=10%
nonzero A income: >=10/16 episodes
valid task-space coverage: >=7.5%
```

Choose the smallest multiplier satisfying the preferred envelope; otherwise the smallest satisfying the relaxed envelope.

If no multiplier satisfies the relaxed envelope, emit `ARM_TIE_CALIBRATION_FAIL`, disable all A cells, and continue the theta round. Do not invent a new task-space reward during v21.

## 0.7 V0-F — exactly one theta=1.25 pilot

### Pilot contract

```text
base config: v20 G4 S+E
warm start: v20 G4 step2500, policy_only
theta_send: 1.25 rad
arm tie: off
seed: 0
num_envs: 256
num_total_batches: 750
save_frequency: 250
stage-time budget: unchanged
effort/velocity limits: unchanged
GPU: one physical GPU in 0–6
```

Evaluate checkpoints 250, 500 and 750 on canonical16. The scientific attempt is single-shot. A process failure before the first optimizer update is infrastructure and may be fixed and repeated unchanged; poor policy performance is not retryable.

### Pilot states

#### `PILOT_FULL_PASS`

All integrity and safety checks pass, and the best of steps 250/500/750 satisfies:

```text
goal >=12/16
crossing while holding >=14/16
hinge_at_crossing p50 >=1.15 rad
hinge_at_crossing p10 >=1.05 rad
stage_overtime <=3/16
upper_dof_overspeed = 0
```

#### `PILOT_CONDITIONAL_PASS`

All integrity and safety checks pass, and the best checkpoint satisfies:

```text
goal >=10/16
crossing while holding >=12/16
hinge_at_crossing p50 >=1.10 rad
hinge_at_crossing p10 >=0.98 rad
stage_overtime <=5/16
upper_dof_overspeed = 0
```

and at least one learning-trend condition holds:

```text
crossing p50 improves by >=0.05 rad from step250 to step750
OR goal improves by >=2/16
OR stage_overtime falls by >=2/16 while crossing p50 does not regress >0.03 rad
```

#### `PILOT_HIGH_THETA_STOP`

Any integrity/safety failure, or failure to reach the conditional thresholds.

### Consequences

```text
FULL_PASS:
  enable theta 0.90/1.10/1.20/1.25/1.30
  enable seed-1 theta1.25 replicate
  enable calibrated A cell if calibration passed

CONDITIONAL_PASS:
  enable theta 0.90/1.10/1.20/1.25
  enable seed-1 theta1.25 replicate
  disable theta1.30
  disable A by default; may enable it only if preferred calibration passed and
  the adaptation marker explains why it remains interpretable

HIGH_THETA_STOP:
  enable theta 0.90/1.10/1.20 only
  disable theta1.25/1.30, replicate and A cells
  continue v21 as a lower-dose experiment; do not alter theta or time budget
```

## 0.8 One bounded adaptation window

After V0-D/V0-E/V0-F and before formal smoke/training, the worker must write:

```text
logs_eval/base_v21/locks/V21_ADAPTATION_DECISION.json
```

It must bind:

- source-lock hash;
- pilot receipt and metrics hashes;
- pilot state;
- enabled/disabled cells;
- selected A multiplier or `A_DISABLED`;
- acceptance profile: `STANDARD` or `RELAXED_1`;
- exact reasons selected from the preregistered state machine.

### Acceptance profile rule

- Default is `STANDARD`.
- `RELAXED_1` may be selected only after `PILOT_CONDITIONAL_PASS`, or when the frozen probe shows send latch is reached but completion is dominated by overtime with no safety regression.
- No acceptance threshold may change after this marker is signed.
- Integrity and safety gates are never relaxed.

This is the only worker-authorized adjustment point. It prevents a useful v21 round from being blocked by an over-strict pilot while preventing post-hoc gate shopping.

---

# 1. Scientific rationale and hypotheses

## 1.1 Corrected v20 diagnosis

The v20 crossing cluster is not explained by a common hard-coded corridor `hinge >= 1.0` branch. That branch is active only in legacy latch mode. The G4/G6/G7 send-ready cells do not use it.

The testable model is:

```text
hinge_at_crossing ~= theta_send + hinge travel accumulated between send latch and crossing
```

Traversal economics can increase this latch-to-cross delay, but v20 showed that send curriculum is the principal ingredient and economics is a smaller modifier.

## 1.2 Primary hypotheses

### H1 — threshold tracking

Increasing `theta_send` produces a monotone increase in both `hinge_at_send_latch` and `hinge_at_crossing`.

### H2 — post-latch delay

`hinge_delta_send_to_cross` remains positive and measurable; its distribution explains why crossing occurs above theta.

### H3 — coordination ceiling alternative

If send-latch angle tracks theta but crossing p50 remains near 1.0, the limiting factor is post-latch whole-body coordination or time. If the latch itself is not reached, the limiting factor is pre-crossing manipulation/kinematics rather than the institution.

### H4 — arm-tie calibration

A correctly scaled A term can increase integral arm contribution without materially reducing task success, crossing angle, grip stability, safety or fluency.

### H5 — high-theta time risk

Higher theta increases time-to-send and heavy-tail overtime. This is measured, not rescued inside the primary round.

---

# 2. Frozen scientific controls

All enabled v21 cells must inherit v20 G4 values except the declared theta, A multiplier and seed.

## 2.1 Frozen items

- policy-only warm start from v20 G4 step2500;
- S curriculum schedule: batches 0–499 penalty, batch 500 onward terminal;
- traversal economics enabled;
- `corridor_latch_mode=send_ready_v20`;
- root crossing margin and send tolerance;
- stage transitions, including stage4→5 at 1.25 rad and release at 1.60 rad;
- maximum stage-time and episode-time budgets;
- door/handle physics randomization;
- action space, observations and low-level controller;
- Piper effort limits, velocity limits, Kp/Kd and action scale;
- all non-A reward scales;
- PPO/TRL optimizer and rollout settings;
- 4096 env formal topology and save interval 250.

## 2.2 Explicitly out of scope

- realistic Piper effort or velocity limits;
- Kp/torque retuning;
- extending stage time for a training cell;
- changing door mass/hinge-force ranges to rescue high theta;
- new scripted arm trajectories, action overrides or simulator-only fallbacks;
- camera/student-policy changes;
- push/pull direction inference.

These belong to a later, separately attributable force-feasibility round after v21.

---

# 3. Formal experiment matrix

All cells use v20 G4 S+E and current capability limits.

| Cell | theta_send | Arm tie | Seed | Purpose | Formal eligibility |
|---|---:|---|---:|---|---|
| G1 | 0.90 | off | 0 | exact continuation/regression anchor | always |
| G2 | 1.10 | off | 0 | lower dose | always |
| G3 | 1.20 | off | 0 | intermediate dose | always |
| G4 | 1.25 | off | 0 | primary high-threshold target | pilot-dependent |
| G5 | 1.30 | off | 0 | upper dose and time-risk probe | full-pass only |
| G6 | 1.25 | off | 1 | basin/seed replicate | pilot-dependent |
| G7 | 1.25 | calibrated | 0 | same-seed A contrast vs G4 | calibration and pilot-dependent |

### Optional G8

```text
G8: theta1.25 + calibrated A, seed1
```

G8 is authorized only after G7 demonstrates a material A effect in Route A and G6 provides a viable seed-1 no-A baseline. G8 is required before making a replicated causal claim about A. It is not required to release a no-A theta policy.

### GPU binding

For the seven-cell full wave:

```text
G1->GPU0, G2->GPU1, G3->GPU2, G4->GPU3,
G5->GPU4, G6->GPU5, G7->GPU6, GPU7 unused
```

Disabled cells leave their GPU idle. Never move another treatment into the disabled cell's identity.

---

# 4. Implementation scope and file plan

## 4.1 New plan/tool namespace

Create, rather than mutate v20 receipts:

```text
scriptsFORhuman/a2_piper_base_v21_implementation_training_execution_plan_20260801.md
scriptsFORhuman/v21/
scriptsFORhuman/v21/schemas/
```

Recommended modules:

```text
__init__.py
_v21_common.py
_v21_workflow.py
a2_piper_v21_source_freeze.py
a2_piper_v21_p0_runner.py
a2_piper_v21_p0_adjudicator.py
a2_piper_v21_theta_probe_runner.py
a2_piper_v21_theta_probe_adjudicator.py
a2_piper_v21_arm_tie_calibrator.py
a2_piper_v21_pilot_launcher.py
a2_piper_v21_pilot_adjudicator.py
a2_piper_v21_adaptation_freeze.py
a2_piper_v21_smoke_launcher.py
a2_piper_v21_smoke_adjudicator.py
a2_piper_v21_formal_launcher.py
a2_piper_v21_formal_completion.py
a2_piper_v21_m22_manifest.py
a2_piper_v21_m22_runner.py
a2_piper_v21_m22_adjudicator.py
a2_piper_v21_pooled_runner.py
a2_piper_v21_pooled_adjudicator.py
a2_piper_v21_release_freeze.py
a2_piper_v21_holdout_runner.py
a2_piper_v21_holdout_adjudicator.py
a2_piper_v21_render_runner.py
a2_piper_v21_render_qa.py
a2_piper_v21_render_review.py
a2_piper_v21_final_analysis.py
```

Reuse the v20_R2 workflow only by versioned import/copy with explicit schema upgrades. Do not make v20 artifacts validate under v21 schemas.

## 4.2 Environment/evidence code

Preferred new pure helper module:

```text
gr00t/rl/envs/door/a2_v21_evidence.py
```

Minimal integration changes may be made to:

```text
gr00t/rl/envs/door/door_open_a2_base.py
gr00t/rl/envs/legged_base_task/legged_robot_base.py   # telemetry only, if needed
```

Requirements:

- no reward/control semantic change outside calibrated G7 A scales;
- no hidden fallback;
- all new metric math in pure functions with finite/type/shape tests;
- first-send and first-cross events are monotonic and reset-safe;
- staged resets restore/clear new buffers correctly;
- partial callbacks do not double-increment counters;
- trace rows remain finite and canonical.

## 4.3 Configs

Create:

```text
gr00t/rl/config/ablation/wbmanip/base_v21_G1_theta090.yaml
gr00t/rl/config/ablation/wbmanip/base_v21_G2_theta110.yaml
gr00t/rl/config/ablation/wbmanip/base_v21_G3_theta120.yaml
gr00t/rl/config/ablation/wbmanip/base_v21_G4_theta125.yaml
gr00t/rl/config/ablation/wbmanip/base_v21_G5_theta130.yaml
gr00t/rl/config/ablation/wbmanip/base_v21_G6_theta125_seed1.yaml
gr00t/rl/config/ablation/wbmanip/base_v21_G7_theta125_arm_tie.yaml
```

Optional:

```text
base_v21_G8_theta125_arm_tie_seed1.yaml
```

Each config must contain both plan IDs, exact group/seed binding, source-lock fields, warm-start path/hash, and the adaptation decision hash.

## 4.4 Schemas

At minimum:

```text
source_lock_v1.schema.json
step_trace_v1.schema.json
episode_record_v1.schema.json
record_set_v1.schema.json
process_receipt_v1.schema.json
theta_probe_report_v1.schema.json
arm_tie_calibration_v1.schema.json
pilot_adjudication_v1.schema.json
adaptation_decision_v1.schema.json
formal_completion_v1.schema.json
m22_manifest_v1.schema.json
checkpoint_metrics_v1.schema.json
dose_response_report_v1.schema.json
pooled_report_v1.schema.json
release_freeze_v1.schema.json
holdout_report_v1.schema.json
render_execution_v1.schema.json
final_decision_v1.schema.json
```

All paths/hashes must be canonical, finite and source-bound. Fix the prior render-provenance length defect; a v21 render cannot be accepted without a valid strict record set.

---

# 5. Static and runtime admission

## 5.1 Mandatory unit tests

Add tests for:

1. send-latch monotonicity and exact first-event capture;
2. send-to-cross interval and missing-event states;
3. linear percentile aggregation with no zero-fill;
4. arm/base tangent integrals;
5. A-income calibration selection;
6. optional torque utilization from applied clipped torques;
7. reset and staged-reset parity;
8. config factor matrix and exact inherited-value diff;
9. GPU0–6 binding and GPU7 rejection;
10. source-lock and plan-lock validation;
11. adaptation state-machine transitions;
12. M22 all-checkpoint, pooled48, holdout64 and render DAG completeness;
13. holdout consumer recomputing actual performance gates, not merely topology;
14. no accepted render without a strict valid record set.

## 5.2 P0 commands

Exact module names may follow repository conventions, but the worker must provide a top-level runner equivalent to:

```bash
export PYTHONPATH=/home/baoquanc/workspace/DoorDog-A2_Piper
PY=/home/baoquanc/anaconda3/envs/isaaclab/bin/python

$PY -B -m pytest -q gr00t/rl/tests/test_a2_v21_*.py
$PY -B -m compileall -q gr00t/rl/envs scriptsFORhuman/v21
$PY -B -m scriptsFORhuman.v21.a2_piper_v21_source_freeze ...
$PY -B -m scriptsFORhuman.v21.a2_piper_v21_p0_runner ...
$PY -B -m scriptsFORhuman.v21.a2_piper_v21_p0_adjudicator ...
```

P0 is a hard gate. Scientific thresholds may be relaxed only through the adaptation profile; source, schema, safety, finite-data and DAG defects may not.

---

# 6. Smoke and pilot execution

## 6.1 Implementation smoke

After any environment/evidence/config change:

```text
one G1 smoke
64 env
10 batches
save at end
one physical GPU0–6
```

It must initialize, train, save, evaluate and emit a strict record set naturally.

## 6.2 Matrix smoke

After the adaptation marker freezes enabled cells:

```text
every enabled cell
64 env
50 batches
save25
one cell per physical GPU
```

Smoke is runtime admission only. No cell is promoted or rejected on reward mean.

## 6.3 Pilot

Run Section 0.7 exactly once after P0 and before formal. The worker must not lower theta, add time, change reward, change door physics or launch a second scientific pilot.

---

# 7. Formal training execution

## 7.1 Common contract

```text
num_envs = 4096
num_total_batches = 2500
checkpoint save interval = 250
checkpoint_load_mode = policy_only
auto_load_latest = false
headless = true
one process per physical GPU
GPU7 forbidden
```

Freeze one W&B mode for the wave before launch. `offline` is preferred for reproducibility; if online monitoring is required, all cells must use the same mode and still retain saved configs, Hydra logs, launcher logs, process receipts and exit codes.

For non-render execution:

```text
unset CUDA_VISIBLE_DEVICES
ACCELERATE_TORCH_DEVICE=cuda:N
```

Do not hand-edit formal commands. Generate them from the signed adaptation decision and promoted configs.

## 7.2 Operational retry policy

A maximum of one unchanged operational replay per cell is allowed only for failures such as simulator crash, host interruption, disk fault or process teardown failure. The retry must preserve:

```text
config bytes
seed
warm-start checkpoint
optimizer settings
environment count
batch count
GPU treatment identity
```

Both failure and replay receipts remain immutable. Poor performance is never retryable.

A failed cell does not automatically cancel completed cells. Dose-response analysis may proceed with at least three valid no-A theta cells, but release requires a complete strict path for the selected candidate.

---

# 8. Route A / M22 all-checkpoint evaluation

Evaluate every saved checkpoint of every enabled formal cell:

```text
steps 250, 500, ..., 2500
canonical16
deterministic first-episode protocol
strict per-env raw traces
```

If all seven cells launch, M22 contains 70 checkpoint rows and 1120 episodes. If the adaptation state prunes cells, the manifest must state the exact expected count; no missing launched checkpoint is permitted.

## 8.1 Exact episode metric definitions

- `hinge_at_send_latch`: hinge on the first raw frame where `send_ready` becomes true.
- `hinge_at_crossing`: hinge on the first raw frame where `root_x_rel_m > 0`.
- `send_to_cross_s`: control-time difference between those exact frames.
- `root_x_at_release`: root x on the final frame where `bilateral == true`.
- `held_hinge_max`: maximum hinge over bilateral frames.
- `crossing_while_holding`: bilateral state on the first crossing frame.
- `goal`: canonical goal field from the strict record.
- percentiles: linear interpolation; missing values remain `N/A`.

## 8.2 Within-cell checkpoint selection

Generate two selections when possible.

### Mechanism checkpoint

Eligible when:

```text
goal >=13/16
crossing while holding >=13/16
upper_dof_overspeed = 0
strict-valid = true
```

Lexicographic selection:

1. maximize `hinge_at_crossing p50`;
2. maximize goal;
3. minimize stage overtime;
4. minimize task-time p50;
5. choose the earlier checkpoint on an exact tie.

### Release checkpoint

Eligible when:

```text
goal >=15/16
crossing while holding >=15/16
upper_dof_overspeed = 0
strict-valid = true
```

Use the same lexicographic rule. Do not prefer the endpoint by default.

A cell may be scientifically informative even if it has only a mechanism checkpoint.

---

# 9. Dose-response adjudication

Use the no-A seed0 cells only for the primary dose curve. G6 is a replicate, not another point in the seed0 fit.

Report:

```text
hinge_at_send_latch p10/p50/p95
hinge_at_crossing p10/p50/p95
hinge_delta_send_to_cross p10/p50/p95
send_to_cross_s p10/p50/p95
goal, held crossing, overtime
pre-send root reconfiguration
arm integral share
```

## 9.1 Mechanism classifications

These are descriptive mechanistic classifications, not statistical-significance claims.

### `THETA_TRACKING`

Preferred evidence:

```text
slope of crossing-p50 vs theta >=0.70
no adjacent reversal larger than 0.03 rad
highest enabled theta improves crossing p50 by >=0.20 rad vs theta0.90
send-latch p50 remains within 0.03 rad of configured theta
```

### `THETA_PARTIAL_TRACKING`

```text
slope 0.35–0.70
OR upper doses plateau after a clear lower-dose increase
OR one adjacent reversal >0.03 but the end-to-end increase remains >=0.12 rad
```

### `PRE_CROSSING_CEILING`

```text
slope <0.35
AND high-theta crossing p50 stays <=1.08 rad or rises <0.08 rad vs theta0.90
```

Sub-classify using raw events:

```text
LATCH_CEILING: high theta send latch is usually not reached
POST_LATCH_COORDINATION_CEILING: latch is reached, crossing remains delayed/absent
TIME_BUDGET_RISK: latch is reached and overtime dominates
```

If only three lower-dose cells were enabled after pilot stop, report `LOWER_RANGE_ONLY`; do not extrapolate to 1.25/1.30.

---

# 10. Arm-tie adjudication

G7 is compared directly with G4 at seed0. It is not selected merely because it has a higher reward.

## 10.1 Preferred A effect

```text
A-income p50 within 2%–5%, p95 <=8%
arm integral-share p50 improvement >=0.08
absolute arm integral-share p50 >=0.45
goal regression <=1/16
crossing-p50 regression <=0.04 rad
stage-overtime increase <=1/16
opening-slip p95 regression <=0.005 m
overspeed = 0
```

## 10.2 Relaxed A effect

```text
A-income p50 within 1.5%–6%, p95 <=10%
arm integral-share p50 improvement >=0.05
absolute arm integral-share p50 >=0.40
goal regression <=2/16
crossing-p50 regression <=0.05 rad
overspeed = 0
```

If G7 fails the relaxed A effect, classify `ARM_TIE_DID_NOT_BIND` and keep no-A cells eligible. Do not retune A after formal results.

A replicated A-factor claim requires optional G8 and the same-direction relaxed effect relative to G6. Without G8, G7 may be reported as a same-seed mechanistic result but not a cross-seed causal replication.

---

# 11. Route B execution

Route A is not a release. Complete all stages below.

## 11.1 Pooled48

For every enabled cell's selected release checkpoint—or mechanism checkpoint when no release checkpoint exists—run:

```text
seeds 0,1,2
16 env per seed
48 episodes per cell
strict raw traces and record sets
```

Pooled adjudication must recompute every v21 metric from traces. It may not accept a precomputed summary field as the sole evidence.

## 11.2 Candidate selection and release freeze

Select the simplest passing no-A theta cell by default. Among eligible no-A cells:

1. prefer the lowest theta that achieves the same release tier;
2. then maximize crossing p50;
3. then minimize heavy-tail overtime;
4. then minimize task-time p50;
5. then use the earlier checkpoint.

An A cell is not release-eligible by default. It becomes eligible only if it passes the A effect and optional G8 provides the required replicated comparison, or the final report explicitly releases the policy without claiming A causality.

Freeze candidate group, config, checkpoint SHA, acceptance profile and pooled report hash before holdout.

## 11.3 Holdout64

Run only the frozen candidate:

```text
seeds 3,4,5,6
16 env per seed
64 episodes
```

The holdout adjudicator must recompute task, mechanism, safety, time and bucket gates. Topology validity alone is insufficient.

## 11.4 Strict render

Run five first episodes × three cameras:

```text
main
handle_side
handle_top
```

The fixed five-case manifest must include:

- one low-mass/easy-spring case;
- two middle cases;
- one high-mass case;
- one high-mass + strong-spring case.

Required QA questions:

1. Is the door visibly wide before the base enters the frame?
2. Is bilateral hold maintained at crossing?
3. Does the policy avoid abrupt base lunge, arm fling or door-panel collision?
4. Is the arm/handle path visually continuous through send and crossing?

Render acceptance requires a strict valid record set, complete raw traces, correct camera/env binding and full media decode.

## 11.5 Final analysis

The final consumer must support these terminal outcomes:

```text
V21_RELEASE
V21_RESEARCH_PASS_NO_RELEASE
V21_THETA_PARTIAL_TRACKING
V21_PRE_CROSSING_CEILING
V21_HIGH_THETA_UNREACHABLE
V21_ARM_TIE_DID_NOT_BIND
V21_NO_SAFE_CANDIDATE
V21_PIPELINE_BLOCKER
```

A non-release result is a completed scientific outcome, not an automatic project blocker.

---

# 12. Acceptance profiles

Integrity and safety are hard gates. Task/fluency thresholds have one bounded relaxation profile selected before formal training.

## 12.1 Hard gates for every profile

```text
all expected records/traces present and strict-valid
all hashes, paths, configs, seeds and checkpoints match
no fallback evaluation
no NaN/Inf or zero-filled missing values
natural process completion or documented unchanged operational replay
GPU7 unused
no hidden control/action override
upper_dof_overspeed = 0 for a release candidate
no unapproved effort/velocity/stage-time/reward changes
```

## 12.2 `STANDARD` release profile

### Canonical16

```text
goal >=15/16
crossing while holding >=15/16
hinge_at_crossing p50 >=1.10 rad
hinge_at_crossing p50 >= theta_send - 0.10 rad
hinge_at_crossing p10 >= theta_send - 0.20 rad
```

### Pooled48

```text
goal >=45/48
crossing while holding >=45/48
stage_overtime <=4/48
opening slip p95 <=0.035 m
held hinge p50/p95 >=1.35/1.45 rad
task time p50/p95 <=16.5/19.0 s
pre-send planar displacement p95 <=0.75 m
pre-send yaw change p95 <=0.55 rad
```

### Heavy+strong pooled bucket

At least 12 preregistered episodes:

```text
goal >=10/12
crossing while holding >=10/12
stage_overtime <=2/12
overspeed = 0
```

### Holdout64

```text
goal >=59/64
crossing while holding >=59/64
stage_overtime <=6/64
hinge_at_crossing p50 >=1.10 rad
hinge_at_crossing p50 >= theta_send - 0.10 rad
hinge_at_crossing p10 >= theta_send - 0.20 rad
```

### Heavy+strong holdout bucket

At least 16 preregistered episodes:

```text
goal >=13/16
crossing while holding >=13/16
stage_overtime <=3/16
overspeed = 0
```

### Render

```text
door visibly wide before crossing: 5/5
crossing while holding: 5/5
goal: >=4/5
no catastrophic collision or uncontrolled lunge
```

## 12.3 `RELAXED_1` release profile

This profile may be frozen only under Section 0.8.

### Canonical16

```text
goal >=14/16
crossing while holding >=14/16
hinge_at_crossing p50 >=1.10 rad
hinge_at_crossing p50 >= theta_send - 0.15 rad
hinge_at_crossing p10 >= theta_send - 0.25 rad
```

A candidate with 14/16 canonical must still meet pooled and holdout gates; Route A alone cannot release it.

### Pooled48

```text
goal >=44/48
crossing while holding >=44/48
stage_overtime <=6/48
opening slip p95 <=0.040 m
held hinge p50/p95 >=1.30/1.40 rad
task time p50/p95 <=17.5/20.0 s
pre-send planar displacement p95 <=0.85 m
pre-send yaw change p95 <=0.65 rad
```

### Heavy+strong pooled bucket

```text
goal >=9/12
crossing while holding >=9/12
stage_overtime <=3/12
overspeed = 0
```

### Holdout64

```text
goal >=58/64
crossing while holding >=58/64
stage_overtime <=8/64
hinge_at_crossing p50 >=1.10 rad
hinge_at_crossing p50 >= theta_send - 0.15 rad
hinge_at_crossing p10 >= theta_send - 0.25 rad
```

### Heavy+strong holdout bucket

```text
goal >=12/16
crossing while holding >=12/16
stage_overtime <=4/16
overspeed = 0
```

Render requirements remain unchanged. Safety and evidence gates remain unchanged.

## 12.4 Research-pass profile

A cell or round may be declared `V21_RESEARCH_PASS_NO_RELEASE` when it establishes a clear theta mechanism but misses one or more release gates.

Minimum research viability:

```text
at least three strict-valid no-A theta cells
canonical goal >=13/16 at their selected mechanism checkpoints
canonical held crossing >=13/16
overspeed = 0
end-to-end crossing p50 increase >=0.12 rad
or a well-supported PRE_CROSSING_CEILING classification
```

This ensures the round produces a useful result instead of being labeled blocked merely because no policy is release-grade.

---

# 13. Time-budget diagnostic, never winner-eligible

Do not include extended stage time in the formal matrix.

Only after a candidate checkpoint is frozen, and only when raw traces show:

```text
send latch reached in >=14/16
crossing/goal failure dominated by stage_overtime
no overspeed or hold-collapse dominance
```

run one zero-training diagnostic with the relevant stage budget extended by a fixed preregistered amount, suggested `100 -> 150` control steps, on canonical16 + heavy16.

This diagnostic:

- cannot change the selected winner;
- cannot satisfy a failed release gate;
- cannot be used to claim causal proof;
- may motivate a separate v21.1/v22 time-budget round.

If high theta never reaches the send latch, do not run the time diagnostic.

---

# 14. Stop, continuation and non-blocking rules

## 14.1 Continue despite branch failure

- torque telemetry deferred → continue theta round;
- arm-tie calibration fails → skip A, continue theta round;
- theta1.25 pilot conditional → prune 1.30/A as defined, continue;
- theta1.25 pilot fails → run 0.90/1.10/1.20 only;
- one formal cell has an unrecoverable operational failure → mark incomplete, continue other cells;
- no release candidate → complete final analysis as research/no-release.

## 14.2 Stop the whole execution only for

- source/checkpoint/config binding mismatch;
- evidence schema unable to represent the primary dependent variable;
- invalid or non-finite trace production after one implementation repair;
- hidden action/control intervention;
- GPU7 use;
- systematic overspeed/safety failure across the viable cells;
- inability to complete a strict DAG for any candidate.

## 14.3 No post-result rescue

After the adaptation marker:

- no theta change;
- no stage-time extension in training;
- no reward retuning;
- no effort/velocity/Kp change;
- no scenario replacement;
- no acceptance-profile change;
- no checkpoint substitution.

---

# 15. Artifact roots

Use new, immutable roots:

```text
logs_eval/base_v21/locks/
logs_eval/base_v21/admission/p0/
logs_eval/base_v21/admission/theta_probe/
logs_eval/base_v21/admission/arm_tie_calibration/
logs_eval/base_v21/pilot/
logs_eval/base_v21/smoke/G*/
logs_eval/base_v21/formal/
logs_eval/base_v21/m22/
logs_eval/base_v21/pooled/G*/
logs_eval/base_v21/release_freeze/
logs_eval/base_v21/holdout/
logs_eval/base_v21/render/
logs_eval/base_v21/final_analysis/

logs_rl/a2_piper_full_stage_a2_base/base_v21/pilot/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v21/G*/
logs_rl/a2_piper_full_stage_a2_base/base_v21/formal/G*/
logs_rl/launchers/base_v21/{pilot,smoke,formal}/
```

Existing roots cause fail-fast refusal. Never overwrite or timestamp-shift to create an implicit retry.

---

# 16. Required worker deliverables

## Implementation closure

- source-lock and plan-lock;
- exact source/config diff report against v20 G4;
- P0 raw output and adjudication;
- unit/compile/Hydra resolution results;
- mechanism trace example with independently recomputed metrics;
- torque telemetry status: `IMPLEMENTED` or `DEFERRED`;
- frozen theta-probe report;
- A calibration report or explicit fail/skip;
- pilot receipts, checkpoint evals and adjudication;
- signed adaptation decision.

## Training closure

For each enabled cell:

- promoted config and SHA;
- launch command/env/GPU binding;
- launcher log and process receipt;
- exit code;
- saved resolved config;
- checkpoints every 250 through 2500 or documented unchanged operational replay;
- no model files copied into evidence bundles unless separately authorized.

## Evaluation/release closure

- exact M22 manifest and all checkpoint rows;
- raw traces and strict record sets;
- checkpoint metrics CSV/JSON/MD;
- dose-response report;
- A-factor report;
- pooled48 reports for all enabled cells;
- release freeze or no-release marker;
- holdout64 report for the frozen candidate;
- strict 5×3 render, QA and reviewer decision;
- final decision with allowed/forbidden claims;
- memory/DONE/TODO and handoff updates.

---

# 17. Final claims discipline

The final report may say:

- crossing angle tracks theta over the tested range;
- tracking is partial or reaches a pre-crossing ceiling;
- send-to-cross delay explains a measured overshoot;
- calibrated arm-tie did or did not increase arm contribution;
- a candidate passed full Route B and is the v21 release.

It may not say:

- realistic Piper effort/velocity feasibility was validated;
- a torque ladder selected a real hardware limit;
- Route A alone is a release;
- a single seed establishes statistical significance;
- extended-time diagnostics prove time as the unique cause;
- an A factor is replicated without G8;
- a failed 1.25 pilot invalidates the lower-dose experiment;
- a relaxed profile was selected after seeing formal/holdout results.

---

# 18. Worker completion checklist

```text
[ ] HEAD and warm-start checkpoint hash verified
[ ] v21 source branch created
[ ] active-boundary audit proves send_ready_v20 for all v21 cells
[ ] mandatory send-latch/time/integral telemetry implemented and tested
[ ] torque telemetry implemented or explicitly deferred
[ ] five-level frozen theta probe complete
[ ] A calibration complete or A branch disabled
[ ] one-shot theta1.25 pilot adjudicated
[ ] adaptation decision frozen before formal
[ ] all enabled configs byte-diffed against v20 G4
[ ] G1 implementation smoke passed
[ ] all enabled matrix smokes passed
[ ] formal wave completed or immutable failures recorded
[ ] all enabled checkpoints evaluated under strict M22
[ ] dose-response and A attribution independently recomputed
[ ] pooled48 complete for all enabled selected checkpoints
[ ] release candidate frozen before holdout
[ ] holdout64 complete and mechanically gated
[ ] strict 5×3 render complete with valid record set
[ ] final analysis emitted one authorized terminal state
[ ] no GPU7, no hidden rescue, no post-formal gate change
```
