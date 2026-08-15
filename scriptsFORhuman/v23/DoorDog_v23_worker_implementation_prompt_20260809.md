# DoorDog base_v23 — Worker Implementation and Training Execution Prompt

**Use this prompt only after the local planner has produced an approved v23 R1 plan, manifest, source audit, selection rule, and implementation patch table.**

## 0. Role

You are the implementation and execution worker for DoorDog base_v23.

Repository:

```text
https://github.com/Jam-Stark/DoorDog
branch: A2_Piper
```

Authoritative scientific input:

```text
DoorDog_v23_training_design_v0.1_20260809.docx
```

Mandatory planner outputs:

```text
scriptsFORhuman/a2_piper_base_v23_force_feasibility_initialization_posture_plan_R1_20260809.md
scriptsFORhuman/v23/V23_SCIENTIFIC_MANIFEST.json
scriptsFORhuman/v23/V23_SELECTION_RULE.json
scriptsFORhuman/v23/V23_PLANNER_DECISION.md
scriptsFORhuman/v23/V23_SOURCE_AUDIT.md
scriptsFORhuman/v23/V23_IMPLEMENTATION_PATCH_TABLE.md
```

Do not start implementation unless:

```text
WORKER_IMPLEMENTATION_MAY_START = yes
```

Do not start formal training unless a strict preformal adjudicator writes:

```text
logs_eval/base_v23/locks/V23_FORMAL_ADMISSION_PASS.json
```

## 1. Scientific matrix

The core matrix is immutable unless the planner decision explicitly revises it:

| Group | Initialization | Train regime | Posture availability | Physical GPU |
|---|---|---|---|---:|
| G1 | v22 warm | D0 | FULL | 0 |
| G2 | v22 warm | D0 | RP0 | 1 |
| G3 | scratch | D0 | FULL | 2 |
| G4 | scratch | D0 | RP0 | 3 |
| G5 | v22 warm | D1 | FULL | 4 |
| G6 | v22 warm | D1 | RP0 | 5 |
| G7 | scratch | D1 | FULL | 6 |
| G8 | scratch | D1 | RP0 | 7 |

Every formal process uses:

```text
4096 environments
same network size, except the preregistered RP0 structural mask
same reward registry
same staged-reset schedule
same optimizer and formal budget
same checkpoint cadence
one process per physical GPU
```

Run two complete waves:

```text
Wave S0: training seed 0, G1–G8 in parallel
Wave S1: training seed 1, G1–G8 in parallel
```

Do not run evaluation on a GPU while its formal training process is active.

## 2. Non-negotiable implementation rules

### 2.1 No fake RP0

RP0 must be implemented in the action distribution or actor head.

Forbidden:

```text
sample action
compute joint log-prob
clamp roll/pitch after log-prob
execute clamped action
```

Required:

```text
executed action == optimized action for all unmasked dimensions
masked posture dimensions produce the semantic neutral command
masked dimensions contribute zero to log-prob, entropy, KL, and PPO ratio
```

### 2.2 No fake torque authority

Every torque field must state its authority:

```text
NOMINAL_PD_TORQUE
CLIPPED_COMMAND_TORQUE
SOLVER_REPORTED_APPLIED_TORQUE
ESTIMATE_ONLY
SOURCE_UNAVAILABLE
```

Do not call a ladder-selected profile "real PiPER torque."

### 2.3 No generic missing-to-zero behavior

Missing core evidence must use typed states. Examples:

```text
NO_VALID_GRASP_WINDOW
NO_HIGH_EFFORT_DENOMINATOR
INSUFFICIENT_PROGRESS_WINDOW
RESCUE_NOT_EXECUTED
TORQUE_SOURCE_UNAVAILABLE
STATE_CLONE_NOT_SUPPORTED
```

### 2.4 No hidden control

Training paths may not use:

```text
scripted door assist
hidden DLS override
root teleport
scripted body contact
oracle action fallback
```

Oracle tangential assist is evaluation-only and must be visibly stamped.

### 2.5 No post-result threshold editing

P0 may calibrate thresholds before formal training. Formal scientific axes, reward registry, selection rules, and evaluation manifests are immutable after the first optimizer update of Wave S0.

## 3. Worker authority and adaptation

The worker may prevent avoidable blocking, but cannot rewrite the causal experiment.

### 3.1 Non-waivable

```text
source/checkpoint/config hash identity
finite physics and metrics
strict record/trace topology
legal GPU lease
RP0 log-prob correctness
no hidden control
no missing-to-zero
staged-reset round-trip correctness
scenario identity and seed identity
unsafe collision/contact limits
```

### 3.2 Adaptable before Wave S0

With a signed artifact, the worker may adjust:

```text
P0 effort-ladder rung selection
D1 near-boundary mixture within planner-approved bounds
E0/E1/E2 numerical thresholds within planner-approved ranges
sample counts for expensive diagnostics
non-safety pilot thresholds
report-only versus binding status for insufficient denominators
```

Write:

```text
logs_eval/base_v23/locks/V23_ADAPTATION_DECISION.json
```

The artifact must include the original value, observed P0 evidence, replacement, claim impact, and exact hashes.

### 3.3 Research continuation

A scientific gate miss may lead to:

```text
V23_RESEARCH_CONTINUATION
```

if runtime evidence is valid and no non-waivable gate failed.

Research continuation allows later diagnostic/evaluation nodes. It does not convert a failed release or causal gate into a pass.

## 4. Repository changes

The planner patch table is authoritative. At minimum, expect the following responsibilities.

### 4.1 Modify

```text
gr00t/rl/envs/door/door_open_a2_base.py
gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py
gr00t/rl/trl/modules/actor_critic_modules_recurrent.py
gr00t/rl/eval_agent_trl.py

gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml
gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml
gr00t/rl/config/env/door_open_a2_base.yaml
gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml

gr00t/rl/isaac_utils/playground/env_rand/door.py
gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py

scriptsFORhuman/a2_piper_longterm_TODO.md
memory/a2-piper/
```

### 4.2 Add

```text
gr00t/rl/envs/door/a2_v23_evidence.py

gr00t/rl/tests/test_a2_v23_action_semantics.py
gr00t/rl/tests/test_a2_v23_rp0_distribution.py
gr00t/rl/tests/test_a2_v23_torque_telemetry.py
gr00t/rl/tests/test_a2_v23_reward_registry.py
gr00t/rl/tests/test_a2_v23_feasibility_certificate.py
gr00t/rl/tests/test_a2_v23_staged_reset.py
gr00t/rl/tests/test_a2_v23_state_bank.py
gr00t/rl/tests/test_a2_v23_artifact_dag.py
gr00t/rl/tests/test_a2_v23_gpu_contract.py

gr00t/rl/config/ablation/wbmanip/base_v23_G1_warm_D0_full.yaml
gr00t/rl/config/ablation/wbmanip/base_v23_G2_warm_D0_rp0.yaml
gr00t/rl/config/ablation/wbmanip/base_v23_G3_scratch_D0_full.yaml
gr00t/rl/config/ablation/wbmanip/base_v23_G4_scratch_D0_rp0.yaml
gr00t/rl/config/ablation/wbmanip/base_v23_G5_warm_D1_full.yaml
gr00t/rl/config/ablation/wbmanip/base_v23_G6_warm_D1_rp0.yaml
gr00t/rl/config/ablation/wbmanip/base_v23_G7_scratch_D1_full.yaml
gr00t/rl/config/ablation/wbmanip/base_v23_G8_scratch_D1_rp0.yaml

scriptsFORhuman/v23/
  _v23_common.py
  source_freeze.py
  p0_torque_telemetry.py
  p0_effort_ladder.py
  p0_kp_clip_audit.py
  p0_door_resistance_atlas.py
  p0_reward_audit.py
  p0_rp0_contract.py
  p0_state_bank.py
  p0_rescue_probe.py
  preformal_adjudicator.py
  formal_launcher.py
  m22.py
  route_a_analysis.py
  pooled48.py
  stratified_eval.py
  intervention_eval.py
  holdout64.py
  render.py
  final_analysis.py
  schemas/
```

Do not import v22 posthoc scripts into the production v23 path unless the planner explicitly approves a source-locked reusable module.

## 5. Production schemas

Implement one production step-trace schema and one production episode-record schema.

### 5.1 Step trace

```text
a2_piper_v23_step_trace_v1
```

Mandatory groups:

```text
provenance
scenario/dynamics
stage/reset source
raw and executed high-level actions
RP0 mask state
commanded and achieved roll/pitch
arm joint state and torque authority
grasp/contact state
hinge state/progress
root/base state
reward-component vector
termination/safety
window-accumulator state
```

### 5.2 Episode record

```text
a2_piper_v23_episode_record_v1
```

Mandatory summaries:

```text
task/stage outcomes
goal/crossing/release
stable-grasp windows
torque utilization and clipping
posture saturation and dwell
E0/E1/E2 certificate fields
rescue execution and result
failure taxonomy
trace path/hash/row count
checkpoint/config/source/scenario identity
```

### 5.3 State-bank entry

```text
a2_piper_v23_state_bank_entry_v1
```

Must bind:

```text
physical state or replay prefix
recurrent observation history
stage/reset source
scenario parameters
random seeds
grasp quality
hinge state
base state
arm state
snapshot/replay integrity hash
```

### 5.4 Intervention record

```text
a2_piper_v23_intervention_record_v1
```

Modes:

```text
FULL
ACUTE_RP0
BASE0_AT_GRASP
HIGHER_EFFORT_RESCUE
ORACLE_TANGENTIAL_ASSIST
```

## 6. Artifact roots

```text
logs_eval/base_v23/locks/
logs_eval/base_v23/p0/torque/
logs_eval/base_v23/p0/effort_ladder/
logs_eval/base_v23/p0/kp_clip/
logs_eval/base_v23/p0/door_atlas/
logs_eval/base_v23/p0/reward/
logs_eval/base_v23/p0/rp0/
logs_eval/base_v23/p0/state_bank/
logs_eval/base_v23/p0/rescue/

logs_eval/base_v23/route_a/seed0/
logs_eval/base_v23/route_a/seed1/
logs_eval/base_v23/pooled48/
logs_eval/base_v23/stratified/
logs_eval/base_v23/interventions/
logs_eval/base_v23/holdout64/
logs_eval/base_v23/render/
logs_eval/base_v23/final_analysis/

logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G1/
...
logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G8/
logs_rl/a2_piper_full_stage_a2_base/base_v23/seed1/G1/
...
logs_rl/a2_piper_full_stage_a2_base/base_v23/seed1/G8/

logs_rl/launchers/base_v23/
```

## 7. Artifact DAG

The strict DAG is:

```text
V23_SOURCE_LOCK
  -> V23_ACTION_SEMANTICS_PASS
  -> V23_TORQUE_TELEMETRY_PASS
  -> V23_EFFORT_PROFILE_FREEZE
  -> V23_DOOR_ATLAS_FREEZE
  -> V23_FEASIBILITY_CERTIFICATE_FREEZE
  -> V23_COMMON_REWARD_FREEZE
  -> V23_RP0_CONTRACT_PASS
  -> V23_STATE_BANK_FREEZE
  -> V23_STATIC_PASS
  -> V23_RUNTIME_SEMANTIC_PASS
  -> V23_FORMAL_ADMISSION_PASS
  -> Wave S0
  -> Route A S0
  -> Wave S1
  -> Route A S1
  -> selected pooled48
  -> E0/E1/E2 stratified evaluation
  -> matched interventions
  -> candidate freeze
  -> holdout64
  -> render
  -> final analysis
```

Raw producers may not write PASS. Only strict adjudicators write markers.

Canonical marker files:

```text
V23_SOURCE_LOCK.json
V23_ACTION_SEMANTICS_PASS.json
V23_TORQUE_TELEMETRY_PASS.json
V23_EFFORT_PROFILE_FREEZE.json
V23_DOOR_ATLAS_FREEZE.json
V23_FEASIBILITY_CERTIFICATE_FREEZE.json
V23_COMMON_REWARD_FREEZE.json
V23_RP0_CONTRACT_PASS.json
V23_STATE_BANK_FREEZE.json
V23_STATIC_PASS.json
V23_RUNTIME_SEMANTIC_PASS.json
V23_FORMAL_ADMISSION_PASS.json
V23_WAVE_S0_COMPLETION.json
V23_ROUTE_A_S0.json
V23_WAVE_S1_COMPLETION.json
V23_ROUTE_A_S1.json
V23_POOLED48.json
V23_STRATIFIED_EVAL.json
V23_INTERVENTION_EVAL.json
V23_CANDIDATE_FREEZE.json
V23_HOLDOUT64.json
V23_RENDER_QA.json
V23_FINAL_ANALYSIS.json
```

## 8. Phase order

### Phase 0 — source freeze

Record:

```text
Git HEAD
dirty status
submodule/asset identity
runtime URDF hash
warm checkpoint/config hashes
A2 low-level policy hash
planner manifest/selection-rule hashes
IsaacLab/PyTorch/CUDA versions
GPU lease
```

### Phase 1 — torque telemetry

Implement and verify per-joint torque fields and authority. Run unit tests and a 4-env runtime smoke.

### Phase 2 — effort ladder and Kp/clip audit

Run the planner-frozen ladder on the frozen v22 checkpoint and exact scenario manifests.

Select `tau_boundary_calibrated` mechanically. If no rung creates a meaningful but non-null boundary, write a valid negative result and use the planner's fallback profile.

### Phase 3 — door resistance atlas

Run independent quasi-static and dynamic axes. Build E0/E1/near-E2/confirmed-E2 manifests.

Confirmed E2 remains held-out and contributes no PPO training samples.

### Phase 4 — scratch-capable common reward

Implement the exact common registry and stage scopes. Run source tests, reward replay, and stationary-rent audit.

Warm and scratch configs must differ only in preregistered initialization and factorial axes.

### Phase 5 — RP0 action contract

Implement distribution-level masking. Run positive and negative tests, including checkpoint serialization/resume.

### Phase 6 — state bank and interventions

Implement state clone or prefix replay, recurrent-history binding, common random numbers, and the five intervention modes.

### Phase 7 — admission

Run:

```text
CPU/static suite
Hydra composition for all 8 configs
1-env end-to-end runtime
8-env mixed semantic runner
staged-reset round trip
resume test
GPU contract test
artifact-DAG negative tests
```

Only then may the strict adjudicator write `V23_FORMAL_ADMISSION_PASS.json`.

### Phase 8 — Wave S0

Launch G1–G8 on physical GPU0–7. Each process must naturally complete. No automatic policy restart after optimizer progress.

### Phase 9 — Route A S0

For each run evaluate:

```text
steps 250,500,750,1000,1250,1500,1750,2000,2250,2500
canonical16
strict record set
raw trace per environment
```

Expected topology:

```text
8 groups × 10 checkpoints = 80 checkpoint evaluations
80 × 16 = 1280 episode records/traces
```

Apply the planner-frozen selection rule.

### Phase 10 — Wave S1

Repeat the exact matrix with training seed 1.

### Phase 11 — Route A S1

Repeat exact topology. Do not change selection rules after seeing seed0.

### Phase 12 — Route B

Run selected checkpoints through:

```text
pooled48
E0/E1/E2 stratified manifests
matched state-bank interventions
holdout64 for final candidates
strict render when motion-quality claims are made
```

## 9. Training execution contract

### 9.1 Launchers

Each launcher records:

```text
physical GPU
command
PID
start/end time
resolved config path/hash
warm checkpoint hash or SCRATCH
seed
exit code
last checkpoint written
natural completion
stdout/stderr hash
```

### 9.2 GPU policy

Use physical GPU0–7 only according to the frozen mapping.

Do not remap based on idle readings. A lease change requires a signed planner/owner artifact.

### 9.3 Attempts

```text
implementation candidates: at most 2
formal process per run: 1
infra restart before first optimizer update: 1 with identical hashes
restart after optimizer progress: forbidden
scratch extension wave: at most 1, applied to all scratch cells equally
```

## 10. Required acceptance logic

### 10.1 Pipeline pass

Requires strict provenance, finite evidence, exact topology, and valid RP0 semantics.

### 10.2 Scientific completion

A scientific negative is not a pipeline blocker.

Valid outcomes include:

```text
V23_WARM_START_INHERITANCE_SUPPORTED
V23_WARM_START_INHERITANCE_NOT_SUPPORTED
V23_D0_NO_ACTIVE_POSTURE_SUFFICIENT
V23_PLANAR_BASE_MOTION_NECESSARY
V23_POSTURE_CAUSALLY_USEFUL_IN_E1
V23_POSTURE_NOT_SELECTIVE
V23_E2_BOUNDARY_ESTABLISHED
V23_E2_BOUNDARY_NOT_ESTABLISHED
V23_DOOR_MODEL_INSUFFICIENT_FOR_E2
V23_SCRATCH_CURRICULUM_INSUFFICIENT
V23_RESEARCH_PASS_NO_RELEASE
```

True blockers are:

```text
V23_SOURCE_IDENTITY_BLOCKER
V23_RP0_SEMANTICS_BLOCKER
V23_TORQUE_AUTHORITY_BLOCKER
V23_STAGED_RESET_CORRUPTION
V23_RUNTIME_EVIDENCE_BLOCKER
V23_GPU_CONTRACT_BLOCKER
```

## 11. Long-term TODO update

Append a clearly labeled section:

```text
[POST-v23 — DO NOT IMPLEMENT IN V23 CORE]
```

Include:

1. true PiPER torque/thermal calibration;
2. real Coulomb/stiction/breakaway hinge model;
3. critic-only/oracle/history-estimated dynamics latent;
4. navigation/posture/manipulation factorized actor;
5. exact state/history clone intervention runner;
6. intervention-supervised coupling critic;
7. counterfactual branch PPO;
8. learned sparse posture gate;
9. handoff/downstream critic;
10. body-assist curriculum after E2 certificate;
11. student dynamics/coupling distillation;
12. active anti-rebound gripper bracing/re-contact.

## 12. Required worker status reports

After each phase, write:

```text
STATUS
EVIDENCE
FILES_CHANGED
TESTS_RUN
RESULT_CLASSIFICATION
NEXT_DAG_NODE
STOP_OR_CONTINUE
```

Never report:

```text
P0 PASS
RP0 PASS
E2 established
formal completion
release
```

unless the strict consumer has written the corresponding marker.

## 13. Final worker output

Return:

1. exact Git commit;
2. changed-file list;
3. all marker paths and hashes;
4. P0 calibration results;
5. training launch matrix and exits;
6. Route-A and Route-B integrity totals;
7. hypothesis results with confidence limits or seed-wise effects;
8. failure taxonomy;
9. long-term TODO patch;
10. final typed v23 outcome.

Do not start POST-v23 algorithm work in the same branch or artifact namespace.
