# A2+Piper base_v20_R2 Admission and Execution Repair Plan

**Date:** 2026-07-30 HKT
**Repository / branch:** `Jam-Stark/DoorDog`, `A2_Piper`
**R1 blocker commit:** `83cec1036a73c08565601df93aae40ee86856109`
**Rejected revision-4 candidate ID:** `e719ea28fde644c870532e2bb698940abbb9d187ea413f9ac815d628a5e2417a`
**Authoritative scientific plan:** `scriptsFORhuman/a2_piper_base_v20_R1_optimization_plan_20260729.md`
**Authoritative R1 plan SHA-256:** `6827290631feea15497fe76cd64116c30a1343d5bd6c1cb83ba09c35bc247e3c`
**R2 role:** repair the implementation, evidence, admission, execution, and evaluation chain without changing the frozen R1 scientific claim or gates.

---

## Decision block

```text
DECISION = FIX_R1_ADMISSION
R1_STATUS = R1_STATIC_ADMISSION_BLOCKER
R1_P1_STATUS = P1_PHYSICAL_BLOCKER
R1_SCIENTIFIC_CLAIM = RETAIN
R1_SCIENTIFIC_GATES = UNCHANGED
REVISION4_EXECUTABLE_CHAIN = REJECTED
FORMAL_TRAINING_READY_NOW = false
G1_G7_MAY_LAUNCH_NOW = no
LEGAL_PHYSICAL_GPUS = 0-6 only
GPU7 = FORBIDDEN
NEXT_APPROVED_SCOPE = one bounded R2 implementation/admission repair with at most two frozen static candidates and no GPU run before independent P0 admission
NEXT_STOPPING_CONDITION = if R2 revision 1 fails any binding static review, or any first authorized runtime-admission node fails, close as R2_ADMISSION_BLOCKER_FINAL and do not create R3 inside this scope
```

This is not an amendment of the behavior target. `theta_send = 0.90 rad`, the S/E/A factor definitions, the one-shot G4 learnability pilot, the seven-cell matrix, all policy gates, and the simplest-passing-group release rule remain those of the authoritative R1 plan. The failed revision-4 implementation is not eligible for runtime use.

---

## 0. Executive ruling

### 0.1 Why `FIX_R1_ADMISSION` is the only approved decision

The handoff contains no policy-level negative evidence against R1. No R1 B0 regeneration, forced semantic runtime, seven-cell zero-shot admission, pilot, smoke, formal training, M22, pooled endpoint, holdout, or R1 render run was started. The binding failures are implementation and evidence-chain failures:

1. incorrect staged-reset compatibility semantics;
2. incomplete finite-safety in task-space math;
3. a production endpoint record that cannot satisfy its own consumer;
4. self-attested semantic admission rather than executed evidence;
5. a cyclic or non-executable pilot/smoke/promotion/formal chain;
6. bypassable M22, pooled, holdout, render, and final-selection tooling;
7. incomplete P0 coverage.

Therefore the frozen scientific claim is neither passed nor disproved. It remains legitimate to repair admission once, provided the repair is complete, acyclic, mechanically adjudicated, and bounded.

### 0.2 What R2 does not do

R2 does not:

- relabel the closed P1 as PASS;
- lower `theta_send` below `0.90 rad`;
- change the root envelope, safety limits, reward scales, curriculum switch, pilot gates, or formal gates;
- accept a caller-authored JSON field such as `status: PASS` as evidence;
- add hidden action overrides, scripted arm trajectories, DLS control, or simulator-only deployment fallbacks;
- use physical GPU7;
- authorize pilot or formal training at document creation;
- repair revision-4 by changing isolated booleans while leaving the evidence chain intact.

### 0.3 Exact immutable inputs

| Item | Exact identity |
|---|---|
| R1 plan | `scriptsFORhuman/a2_piper_base_v20_R1_optimization_plan_20260729.md` |
| R1 plan SHA-256 | `6827290631feea15497fe76cd64116c30a1343d5bd6c1cb83ba09c35bc247e3c` |
| B0 JSON | `scriptsFORhuman/v20_R1/a2_piper_base_v20_R1_B0_reference_20260729.json` |
| B0 JSON SHA-256 | `98654a976be8b6593e796d89291b4dc6ebdf530d078c625db7130d7a1622c826` |
| B0 CSV | `scriptsFORhuman/v20_R1/a2_piper_base_v20_R1_B0_reference_20260729.csv` |
| B0 CSV SHA-256 | `209b33a1fa9d79d60f715518cc2798f96b13d71aea8fb2aac0f520a516f4585a` |
| G2 step2000 checkpoint | `logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt` |
| Checkpoint SHA-256 | `b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d` |
| Runtime URDF | `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf` |
| URDF SHA-256 | `d02cdacdcd4aaf1480b52ba9a6a62f5e9bbd040036a796154dbff70d1391a1d5` |
| URDF Git blob | `95c7698866962fa6e1b971b9ee534452775d8698` |
| Closed P1 code commit | `365667110b2e64b335dcf3517361245331db604e` |
| P1 closure commit | `282ab4ad118b734535b61440397bfb9e67b10fe6` |
| R1 blocker commit | `83cec1036a73c08565601df93aae40ee86856109` |
| Rejected R1 candidate ID | `e719ea28fde644c870532e2bb698940abbb9d187ea413f9ac815d628a5e2417a` |
| Blocker ZIP SHA-256 | `f72f68992d4b407afac0cca154b712891bf78c9edd2affab5fa54b5a18e01fb5` |

All R1/P1 artifacts are read-only inputs. R2 writes no file under `logs_eval/base_v20/` or `logs_eval/base_v20_R1/`.

---

## 1. Scientific lock inherited unchanged from R1

### 1.1 Behavior claim

R2 retains this R1 claim:

> A learned whole-body high-level policy can move already-achieved door-opening progress earlier in the episode, delay physical root crossing until at least `0.90 rad`, and make the arm provide a majority of positive handle-tangent motion before crossing, without regressing grasp stability, task success, safety, arc tracking, or fluency.

### 1.2 Factors

| Factor | Frozen meaning |
|---|---|
| **S** | Soft-to-hard send curriculum. Batches `0-499`: one-shot graded pre-send crossing penalty, no S terminal. Batches `500-2499`: exact `pre_send_root_crossing` terminal, no duplicate graded penalty. |
| **E** | Pre-send traversal income is zero, root crossing cannot activate the corridor, `send_ready` activates the corridor, and the wide-open wage preserves the G2 local slope. |
| **A** | Task-space arm-relative handle-tangent contribution and handle-to-TCP arc tracking; no single-joint choreography. |

### 1.3 Frozen values

```yaml
base_v20_R1_science:
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
    group: G4
    seed: 0
    envs: 256
    batches: 750
    save_frequency: 250

  formal:
    envs: 4096
    batches: 2500
    save_frequency: 250
```

### 1.4 Frozen B0 headline values

```text
B0 pooled48 goal                         48/48
B0 pooled48 crossing while holding       48/48
hinge at first crossing p10              0.6346503735 rad
hinge at first crossing p50              0.7189994752 rad
hinge at first crossing p95              0.8444905579 rad
hinge at first crossing max              0.8773267269 rad
held hinge p50 / p95                     1.4336078763 / 1.5430807173 rad
opening slip p95                         2.9084465560 cm
release hinge p50 / p95                  1.6054893732 / 1.6115434408 rad
pre-cross hinge velocity p95             0.3246622443 rad/s
pre-cross bilateral / coasting / force   0.9966701114 / 0.0028705936 / 0.0004592950
task time p50 / p95                      12.51 / 13.944 s
overspeed / post-release contact         0/48 / 0/48
```

The two-render-episode task-space values remain diagnostic only. R2 must generate the formal no-learning pooled48 task-space B0 before the pilot.

---

## 2. R2 identity, namespace, and versioning

### 2.1 Two identities, not one

R2 keeps the R1 scientific identity while replacing the execution identity:

```text
scientific_plan_id = base_v20_R1_policy_behavior_v1
admission_plan_id  = base_v20_R2_admission_execution_v1
```

Every R2 config and artifact must contain both. No R2 consumer accepts a record whose scientific plan ID differs from R1 or whose admission plan ID differs from R2.

### 2.2 Repository paths

```text
scriptsFORhuman/a2_piper_base_v20_R2_admission_and_execution_plan_20260730.md
scriptsFORhuman/v20_R2/a2_piper_base_v20_R2_plan_lock_20260730.json
scriptsFORhuman/v20_R2/
scriptsFORhuman/v20_R2/schemas/

gr00t/rl/config/ablation/wbmanip/base_v20_R2_G1_g2_continuation.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R2_G2_economics_only.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R2_G3_send_curriculum_only.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R2_G4_send_curriculum_economics.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R2_G5_send_curriculum_arm_tie.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R2_G6_full.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R2_G7_full_seed1.yaml
gr00t/rl/config/ablation/wbmanip/base_v20_R2_P2_G4_learnability_pilot.yaml
```

### 2.3 Artifact roots

R2 uses fixed, single-attempt roots. Existing roots cause fail-fast refusal; they are never overwritten or timestamp-shifted to create an implicit retry.

```text
logs_eval/base_v20_R2/locks/
logs_eval/base_v20_R2/admission/revision0/p0/
logs_eval/base_v20_R2/admission/revision1/p0/
logs_eval/base_v20_R2/admission/b0/seed0/
logs_eval/base_v20_R2/admission/b0/seed1/
logs_eval/base_v20_R2/admission/b0/seed2/
logs_eval/base_v20_R2/admission/forced/
logs_eval/base_v20_R2/admission/zero_shot/G1/
logs_eval/base_v20_R2/admission/zero_shot/G2/
logs_eval/base_v20_R2/admission/zero_shot/G3/
logs_eval/base_v20_R2/admission/zero_shot/G4/
logs_eval/base_v20_R2/admission/zero_shot/G5/
logs_eval/base_v20_R2/admission/zero_shot/G6/
logs_eval/base_v20_R2/admission/zero_shot/G7/
logs_eval/base_v20_R2/admission/semantic/
logs_eval/base_v20_R2/pilot/
logs_eval/base_v20_R2/smoke/G1/
logs_eval/base_v20_R2/smoke/G2/
logs_eval/base_v20_R2/smoke/G3/
logs_eval/base_v20_R2/smoke/G4/
logs_eval/base_v20_R2/smoke/G5/
logs_eval/base_v20_R2/smoke/G6/
logs_eval/base_v20_R2/smoke/G7/
logs_eval/base_v20_R2/promotion/
logs_eval/base_v20_R2/formal/
logs_eval/base_v20_R2/m22/
logs_eval/base_v20_R2/pooled/G1/
logs_eval/base_v20_R2/pooled/G2/
logs_eval/base_v20_R2/pooled/G3/
logs_eval/base_v20_R2/pooled/G4/
logs_eval/base_v20_R2/pooled/G5/
logs_eval/base_v20_R2/pooled/G6/
logs_eval/base_v20_R2/pooled/G7/
logs_eval/base_v20_R2/release_freeze/
logs_eval/base_v20_R2/holdout/
logs_eval/base_v20_R2/render/
logs_eval/base_v20_R2/final_analysis/

logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/pilot/G4_seed0_256x750/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2/G1/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2/G2/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2/G3/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2/G4/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2/G5/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2/G6/
logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2/G7/
logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal/G1/
logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal/G2/
logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal/G3/
logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal/G4/
logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal/G5/
logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal/G6/
logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal/G7/

logs_rl/launchers/base_v20_R2/pilot/
logs_rl/launchers/base_v20_R2/smoke/
logs_rl/launchers/base_v20_R2/formal/
```

### 2.4 Canonical marker paths

```text
logs_eval/base_v20_R2/locks/R2_REVISION_0_SOURCE_FREEZE.json
logs_eval/base_v20_R2/locks/R2_REVISION_1_SOURCE_FREEZE.json
logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json
logs_eval/base_v20_R2/locks/P0_STATIC_PASS.json
logs_eval/base_v20_R2/locks/B0_RUNTIME_PASS.json
logs_eval/base_v20_R2/locks/FORCED_RUNTIME_SEMANTIC_PASS.json
logs_eval/base_v20_R2/locks/ZERO_SHOT7_RUNTIME_SEMANTIC_PASS.json
logs_eval/base_v20_R2/locks/R2_P1_RUNTIME_SEMANTIC_PASS.json
logs_eval/base_v20_R2/locks/PILOT_ATTEMPT_CONSUMED.json
logs_eval/base_v20_R2/locks/PILOT_POLICY_LEARNABILITY_PASS.json
logs_eval/base_v20_R2/locks/SMOKE_WAVE_ATTEMPT_CONSUMED.json
logs_eval/base_v20_R2/locks/SMOKE_PASS.json
logs_eval/base_v20_R2/locks/FORMAL_ADMISSION_BUNDLE.json
logs_eval/base_v20_R2/locks/PROMOTION_PASS.json
logs_eval/base_v20_R2/locks/FORMAL_WAVE_ATTEMPT_CONSUMED.json
logs_eval/base_v20_R2/locks/FORMAL_COMPLETION_PASS.json
logs_eval/base_v20_R2/locks/M22_70ROW_PASS.json
logs_eval/base_v20_R2/locks/POOLED7_PASS.json
logs_eval/base_v20_R2/locks/RELEASE_FREEZE.json
logs_eval/base_v20_R2/locks/HOLDOUT64_PASS.json
logs_eval/base_v20_R2/locks/RENDER_QA_PASS.json
logs_eval/base_v20_R2/locks/FINAL_DECISION.json
```

Every marker is created with `O_CREAT | O_EXCL`, mode `0444`, and a canonical JSON write followed by `fsync(file)`, `fsync(parent)`, and SHA-256 recording. Symlinks are rejected at every path component.

---

## 3. Revision-4 disposition: retain, replace, add, delete

### 3.1 Retain unchanged as immutable evidence

| Path | Disposition |
|---|---|
| `scriptsFORhuman/a2_piper_base_v20_R1_optimization_plan_20260729.md` | Retain byte-for-byte; R2 does not edit it. |
| `scriptsFORhuman/v20_R1/a2_piper_base_v20_R1_B0_reference_20260729.json` | Retain byte-for-byte. |
| `scriptsFORhuman/v20_R1/a2_piper_base_v20_R1_B0_reference_20260729.csv` | Retain byte-for-byte. |
| `logs_eval/base_v20/preflight/p1_tx1_smoke_commit3656671_20260729/` | Read-only closed P1 evidence. |
| `base_v20_R1_static_admission_blocker_summary_20260730.md` | Retain as blocker evidence. |
| `base_v20_R1_candidate_manifest_revision4.json` | Retain as rejected-candidate evidence. |
| `R1_SCIENTIFIC_MANIFEST.json/.md` | Retain as historical scientific-input record, not an admission marker. |

### 3.2 Retain and harden

| File / symbol | R2 action |
|---|---|
| `gr00t/rl/envs/base_task/staged_task_base.py::_filter_staged_reset_snapshot_mask` | Retain the no-op superclass hook and its shape/device validation. Add a second load-time hook described in Section 5. |
| `door_open_a2_base.py::a2_v20_r1_pre_send_crossing_penalty` | Port as `a2_v20_r2_pre_send_crossing_penalty`; preserve the frozen formula and add output finite/range checks. |
| `door_open_a2_base.py::a2_v20_r1_root_reconfiguration` | Port as `a2_v20_r2_root_reconfiguration`; preserve wrapped-yaw semantics and add output finite checks. |
| `door_open_a2_base.py::a2_v20_r1_durable_crossing_event` | Port as `a2_v20_r2_durable_crossing_event`; preserve one-shot crossing ownership. |
| `door_open_a2_base.py::a2_v20_update_send_ready` | Retain with R2 naming/contract tests. |
| `door_open_a2_base.py::a2_v20_handle_opening_tangent` | Retain after computed-output finite/unit-norm validation. |
| `door_open_a2_base.py::a2_v20_handle_to_tcp_transform` | Retain after finite/unit-quaternion validation. |
| `door_open_a2_base.py::a2_v20_handle_local_slip_metrics` | Retain after finite output checks. |
| `door_open_a2_base.py::a2_v20_arc_tracking_quality` | Retain after safe quaternion normalization, finite output checks, and `[0,1]` range assertion. |
| `gr00t/rl/train_agent_trl.py` schedule plumbing | Retain only if R2 P0 tests prove exact batch ownership, resume behavior, and absence of hidden source mutation. |
| `gr00t/rl/trl/utils/scheduler.py::update_scheduled_params` | Retain generic scheduler; add R2 boundary and resume tests. |
| revision-4 G1-G7/P2 values | Clone into R2 config names; do not execute R1 config paths. |

### 3.3 Replace completely

| Revision-4 symbol/file | Replacement |
|---|---|
| `a2_v20_r1_snapshot_incompatibility_mask` and `a2_v20_r1_snapshot_compatibility_mask` | Replace with one unambiguous `a2_v20_r2_snapshot_admission_mask` returning `{admit, reason_code}`. |
| `_filter_staged_reset_snapshot_mask` R1 subclass implementation | Replace with the M45 truth table in Section 5. |
| `_audit_a2_v20_r1_hard_phase_snapshots` | Replace with per-slot hard-phase audit using actual populated-slot masks and stage-specific compatibility. |
| `a2_v20_taskspace_arm_carry` | Replace with `a2_v20_r2_taskspace_arm_carry` using safe denominators and computed-output finite/range checks. |
| `a2_v20_r1_build_endpoint_record` | Remove from production; replace with the sole M48 schema in Section 7. |
| `get_a2_v20_R1_endpoint_records` | Remove from production; replace with `finalize_a2_v20_r2_episode_record`. |
| `_a2_v20_r1_normalize_terminal_diagnostic` | Remove; no normalizer is allowed to fabricate missing metrics from one terminal snapshot. |
| all `scriptsFORhuman/v20_R1/*baseline*`, `*semantic*`, `*endpoint*`, `*pilot*`, `*smoke*`, `*promote*`, `*launcher*`, `*m22*`, `*render*`, `*final*` executable paths | Replace with R2 producers/consumers listed in Section 4. R1 scripts remain historical but are not imported by R2. |
| revision-4 status-driven validation | Replace with raw process receipts plus recomputation by strict adjudicators. |

### 3.4 Add

#### Environment/runtime code

```text
gr00t/rl/envs/door/a2_v20_r2_evidence.py
gr00t/rl/envs/door/a2_v20_r2_forced_semantics.py
```

Modify:

```text
gr00t/rl/envs/base_task/staged_task_base.py
gr00t/rl/envs/legged_base_task/legged_robot_base.py
gr00t/rl/envs/door/door_open_a2_base.py
gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py
gr00t/rl/train_agent_trl.py
gr00t/rl/eval_agent_trl.py
gr00t/rl/config/env/door_open_a2_base.yaml
gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml
```

#### R2 scripts

```text
scriptsFORhuman/v20_R2/__init__.py
scriptsFORhuman/v20_R2/_r2_common.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_source_freeze.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_p0_runner.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_p0_adjudicator.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_eval_runner.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_record_adjudicator.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_forced_runner.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_semantic_adjudicator.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_pilot_launcher.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_pilot_adjudicator.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_smoke_launcher.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_smoke_adjudicator.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_promote_configs.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_formal_launcher.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_formal_completion.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_m22_manifest.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_m22_runner.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_m22_adjudicator.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_pooled_runner.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_pooled_adjudicator.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_release_freeze.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_holdout_runner.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_holdout_adjudicator.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_render_runner.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_render_qa.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_render_review.py
scriptsFORhuman/v20_R2/a2_piper_v20_R2_final_analysis.py
```

#### JSON Schemas

Every schema is JSON Schema Draft 2020-12 with `additionalProperties: false` at every object level.

```text
scriptsFORhuman/v20_R2/schemas/source_lock_v1.schema.json
scriptsFORhuman/v20_R2/schemas/process_receipt_v1.schema.json
scriptsFORhuman/v20_R2/schemas/step_trace_v1.schema.json
scriptsFORhuman/v20_R2/schemas/episode_record_v1.schema.json
scriptsFORhuman/v20_R2/schemas/record_set_v1.schema.json
scriptsFORhuman/v20_R2/schemas/endpoint_report_v1.schema.json
scriptsFORhuman/v20_R2/schemas/p0_raw_v1.schema.json
scriptsFORhuman/v20_R2/schemas/p0_adjudication_v1.schema.json
scriptsFORhuman/v20_R2/schemas/semantic_adjudication_v1.schema.json
scriptsFORhuman/v20_R2/schemas/training_attempt_v1.schema.json
scriptsFORhuman/v20_R2/schemas/formal_completion_v1.schema.json
scriptsFORhuman/v20_R2/schemas/m22_manifest_v1.schema.json
scriptsFORhuman/v20_R2/schemas/m22_adjudication_v1.schema.json
scriptsFORhuman/v20_R2/schemas/release_freeze_v1.schema.json
scriptsFORhuman/v20_R2/schemas/render_execution_v1.schema.json
scriptsFORhuman/v20_R2/schemas/final_decision_v1.schema.json
```

### 3.5 Delete from the R2 executable path

Do not delete historical R1 files from Git. Instead:

1. add `scriptsFORhuman/v20_R1/R1_BLOCKED_DO_NOT_EXECUTE.md`;
2. make every R1 CLI exit `2` if `BASE_V20_ALLOW_BLOCKED_R1_EXECUTION` is absent;
3. do not set that variable in any R2 tool;
4. forbid importing `scriptsFORhuman.v20_R1` from any R2 source through a static import test;
5. exclude all R1 scripts from the R2 source lock except the immutable plan/B0 files.

---

## 4. R2 production modules and ownership

| Concern | Sole owner |
|---|---|
| File hashing, canonical JSON, no-overwrite writes, device environment | `scriptsFORhuman/v20_R2/_r2_common.py` |
| Staged-reset snapshot admission | `DoorPregrasp._filter_staged_reset_snapshot_mask` plus pure helper in `a2_v20_r2_evidence.py` |
| Staged-reset load validation | `StagedTaskBase._validate_loaded_staged_reset_sample` overridden by `DoorPregrasp` |
| Task-space decomposition | `a2_v20_r2_evidence.py::a2_v20_r2_taskspace_arm_carry` |
| Live M48 accumulators | `DoorPregrasp._update_a2_v20_r2_evidence_accumulators` |
| Reward-income accumulation | `LeggedRobotBase._after_reward_components`, overridden by `DoorPregrasp` |
| Per-episode production record | `DoorPregrasp.finalize_a2_v20_r2_episode_record` |
| Runtime process execution | `a2_piper_v20_R2_eval_runner.py` / stage launchers |
| Record/schema strictness | `a2_piper_v20_R2_record_adjudicator.py` |
| Scientific gates | stage-specific adjudicators only |
| Final winner/no-release | `a2_piper_v20_R2_final_analysis.py` only |

Raw producers are forbidden from emitting any field named `status`, `pass`, `passed`, `checks_passed`, `verdict`, or `adjudication`. They may emit only structural producer states such as `PROCESS_COMPLETED` or `RECORD_SET_COMPLETE`. Only strict consumers emit PASS/FAIL vocabulary.

---

## 5. M45-R2 staged-reset and send-state semantics

### 5.1 Snapshot-admission truth table

Define:

```python
a2_v20_r2_snapshot_admission_mask(
    candidate_stage: torch.Tensor,
    populated: torch.Tensor,
    send_ready: torch.Tensor,
    pre_send_crossing_seen: torch.Tensor,
    root_x_rel: torch.Tensor,
    root_x_margin: float,
    stage_swing: int,
    stage_through: int,
) -> dict[str, torch.Tensor]
```

The result contains:

```text
admit: bool[N]
reason_code: int8[N]
```

Reason codes:

```text
0 = NOT_POPULATED
1 = ADMIT_PRE_SWING
2 = ADMIT_SWING_PRE_CROSS
3 = ADMIT_POST_SEND_SWING
4 = ADMIT_POST_SEND_THROUGH
10 = REJECT_PRE_SEND_CROSSING_SEEN
11 = REJECT_SWING_ROOT_BEYOND_MARGIN_WITHOUT_SEND
12 = REJECT_THROUGH_WITHOUT_SEND
13 = REJECT_UNSUPPORTED_STAGE
```

Truth table:

| Populated | Stage | State | Admit |
|---|---|---|---|
| false | any | any | false, reason 0 |
| true | `< STAGE_SWING` | any finite state | true, reason 1 |
| true | `== STAGE_SWING` | `pre_send_crossing_seen=true` | false, reason 10 |
| true | `== STAGE_SWING` | `send_ready=false` and `root_x_rel > 0.03` | false, reason 11 |
| true | `== STAGE_SWING` | `send_ready=false` and `root_x_rel <=0.03` | true, reason 2 |
| true | `== STAGE_SWING` | `send_ready=true` and no earlier pre-send crossing | true, reason 3 |
| true | `== STAGE_THROUGH` | `pre_send_crossing_seen=true` | false, reason 10 |
| true | `== STAGE_THROUGH` | `send_ready=false` | false, reason 12 |
| true | `== STAGE_THROUGH` | `send_ready=true` and no earlier pre-send crossing | true, reason 4 |
| true | `> STAGE_THROUGH` | any | fail-fast configuration error, reason 13 is never silently admitted |

The revision-4 rule `candidate_stage >= STAGE_THROUGH -> reject` is deleted. A legitimate post-send stage-5 snapshot is required for later-stage exploration and must be admitted.

### 5.2 Store-time filtering

`DoorPregrasp._filter_staged_reset_snapshot_mask` must:

1. call the superclass no-op hook;
2. derive `candidate_stage` after stage advancement;
3. compute `populated = filtered_advance_mask`;
4. call the pure helper;
5. increment per-reason rejection counters only for populated candidates;
6. return `filtered_advance_mask & admit`;
7. never mutate `send_ready`, root state, crossing state, or reward state;
8. emit a lightweight training counter and, in evidence mode, a trace row containing the reason code.

### 5.3 Load-time validation

Add to `StagedTaskBase`:

```python
def _validate_loaded_staged_reset_sample(
    self,
    selected_env_ids: torch.Tensor,
    selected_stages: torch.Tensor,
    selected_sample_indices: torch.Tensor,
) -> None:
    return
```

Call it after all object and buffer tensors have been copied into environment buffers, before the first policy observation is computed. `DoorPregrasp` overrides it and re-evaluates the same truth table from restored state. A restored incompatible sample raises `RuntimeError`; it is never silently remapped to stage 0.

### 5.4 State that is snapshotted

The following state changes future reward, termination, stage logic, or task-space reference and must be stored/restored exactly:

```text
_a2_v20_send_ready
_a2_v20_pre_send_crossing_seen
_a2_v20_first_pre_send_crossing_step
_a2_v20_first_send_ready_step
_a2_v20_first_root_crossing_step
_a2_v20_hinge_at_first_root_crossing
_a2_v20_root_x_at_first_crossing
_a2_v20_root_entry_pos_se2
_a2_v20_root_entry_valid
_a2_v20_max_pre_send_displacement_se2
_a2_v20_r2_max_pre_send_reconfiguration
_a2_corridor_latched
_a2_v20_handle_tcp_capture_pos
_a2_v20_handle_tcp_capture_quat
_a2_v20_handle_tcp_capture_valid
_a2_v20_snapshot_crossing_seen
_a2_v20_snapshot_root_x_rel
```

The following transient derivative/one-step state is not copied as historical truth:

```text
_a2_v20_pre_send_crossing_event
_a2_v20_r2_crossing_penalty_raw
_a2_v20_r2_hard_crossing_pending
_a2_v20_prev_tcp_pos_w
_a2_v20_prev_tcp_valid
all M48 per-episode counters, sample arrays, and previous-derivative samples
```

After a staged load:

- one-step event buffers are zeroed;
- previous TCP/action/hinge derivative validity is false for one control step;
- handle-to-TCP captured reference remains restored;
- per-episode M48 accumulators are reset for the new rollout segment;
- a `reset_origin` field records the restored stage and snapshot index;
- the first post-load step is never used for velocity finite differences, acceleration, jerk, action rate, or action jerk.

### 5.5 Hard-phase audit

At the exact soft-to-hard transition, audit every populated slot in stages `STAGE_SWING` and `STAGE_THROUGH` using:

```text
populated_slot[stage, slot, env] = slot < min(staged_reset_num_samples[stage, env], capacity)
```

The audit must evaluate each slot, not one environment-level summary. It fails if any populated slot is incompatible. It reports exact counts by stage and reason code. Empty slots are ignored, never treated as compatible data.

### 5.6 M45 acceptance tests

Positive:

- sent stage-5 snapshot is admitted, stored, restored, and produces identical `send_ready`/corridor/termination decisions;
- unsent stage-5 snapshot is rejected;
- clean pre-cross stage-4 snapshot is admitted;
- contaminated stage-4 snapshot is rejected;
- post-send stage-4 snapshot is admitted;
- hard-phase audit accepts a mixed buffer containing only compatible populated slots;
- first post-load derivative sample is excluded.

Negative:

- revision-4 `all stage5 rejected` behavior fails the test;
- any populated incompatible slot hidden behind unused capacity fails;
- mismatched dtype/device/shape fails;
- load-time incompatibility fails rather than resetting to stage 0;
- a restored one-step crossing event fails;
- snapshotting M48 accumulators fails the source-contract test.

---

## 6. M47-R2 task-space semantics and finite safety

### 6.1 Frame contract

Use the Piper TCP as `source` and the handle target from the existing IsaacLab `FrameTransformer`. Store and compare the canonical transform:

```text
T_HANDLE_TCP
```

The positive opening tangent is computed from the door hinge axis and hinge-to-handle radial vector. No world-axis shortcut and no `arm_j1` sign is permitted.

### 6.2 Capture ownership

Capture the handle-to-TCP reference exactly once per episode or staged-reset segment at the first control step satisfying:

```text
opening_phase
AND valid_hold_streak
AND bilateral_contact
AND finite handle/TCP transforms
AND NOT release_gate
```

A stage-2 contact before opening does not capture the M47 reference. A restored compatible staged snapshot restores its captured reference; it does not recapture on the first post-load step.

### 6.3 Safe decomposition

Replace the revision-4 helper with:

```python
a2_v20_r2_taskspace_arm_carry(
    root_pos_w: Tensor[N,3],
    root_lin_vel_w: Tensor[N,3],
    root_ang_vel_w: Tensor[N,3],
    tcp_pos_w: Tensor[N,3],
    tcp_lin_vel_w: Tensor[N,3],
    opening_tangent_w: Tensor[N,3],
    valid_reference: Tensor[N],
    valid_hold: Tensor[N],
    before_send: Tensor[N],
    positive_hinge_progress: Tensor[N],
    activity_floor_mps: float,
) -> mapping
```

Formula:

```text
v_base_at_tcp = root_lin_vel_w + cross(root_ang_vel_w, tcp_pos_w - root_pos_w)
v_arm         = tcp_lin_vel_w - v_base_at_tcp
u_base_raw     = dot(v_base_at_tcp, opening_tangent_w)
u_arm_raw      = dot(v_arm, opening_tangent_w)
u_base         = max(u_base_raw, 0)
u_arm          = max(u_arm_raw, 0)
u_total        = u_base + u_arm
active          = valid_reference
                  AND valid_hold
                  AND before_send
                  AND positive_hinge_progress
                  AND u_total >= activity_floor_mps
safe_total      = where(active, u_total, 1)
arm_share       = where(active, u_arm / safe_total, 0)
```

Required computed-output checks:

```text
all v_base_at_tcp finite
all v_arm finite
all raw and positive tangent projections finite
all u_total finite and >=0
all active arm_share finite
0 <= arm_share <= 1
opening_tangent norm within 1e-5 of 1 for valid rows
inactive arm_share exactly 0
```

These checks occur after cross-products, sums, dot products, clamping, and division. Input finite checks alone are insufficient.

### 6.4 TCP velocity

In evidence mode, TCP velocity uses the exact control interval `dt` and consecutive post-physics poses. The previous pose must be valid, from the same episode segment, and exactly one control step earlier. The first step after true reset or staged load is invalid for finite differences.

### 6.5 Arc and slip metrics

For valid pre-send held samples:

```text
position_error_m          = norm(p_HANDLE_TCP(t) - p_HANDLE_TCP(capture))
orientation_error_rad     = geodesic quaternion angle in [0, pi]
along_handle_slip_m       = abs(delta_HANDLE_TCP.y)
orthogonal_arc_residual_m = norm(delta_HANDLE_TCP[x,z])
arc_quality               = clamp(1 - position_error / 0.03, 0, 1)
                            * clamp(1 - orientation_error / 0.20, 0, 1)
```

Quaternion norms below machine epsilon, non-finite results, orientation outside `[0,pi]`, negative distances, or quality outside `[0,1]` fail immediately.

### 6.6 Reward scope

A rewards are positive only when all are true:

```text
A enabled
valid opening-phase hold
captured reference valid
before send_ready
before release
positive hinge velocity
active task-space decomposition
```

A income is zero for pure stationary motion, wrong-direction motion, closing hinge, invalid contact, invalid reference, post-send motion, and post-release motion. This pre-send scope matches the R1 arm-majority claim and prevents A from paying for base-dragging after crossing.

### 6.7 M47 acceptance tests

Positive:

- pure rigid-base tangent motion -> share 0;
- pure arm-relative tangent motion -> share 1;
- equal positive contributions -> 0.5;
- root angular velocity contribution included;
- rigid-transform invariance;
- mirrored door tangent sign;
- valid restored reference produces identical metrics after derivative warm-up;
- online results match offline replay to absolute tolerance `1e-6`.

Negative:

- `inf - inf`, overflowed cross-product, non-finite sum, or zero denominator is rejected;
- wrong-direction or zero total tangent cannot become active;
- non-unit tangent is rejected;
- malformed quaternion is rejected;
- post-send or post-release A income is nonzero -> failure;
- input-finite/output-nonfinite synthetic case must fail.

---

## 7. M48-R2: one production record schema

### 7.1 Sole downstream record

The only per-episode object accepted by B0, zero-shot, pilot endpoint, M22, pooled, holdout, paired analysis, render binding, and final analysis is:

```text
a2_piper_v20_R2_episode_record_v1
```

No legacy terminal diagnostic, revision-4 endpoint record, ad hoc summary JSON, or caller-created metric dictionary is accepted downstream.

### 7.2 Record identity

`record_id` is SHA-256 of canonical JSON over every record field except `record_id`. Canonical JSON uses UTF-8, sorted keys, no NaN/Infinity, compact separators, and decimal numbers emitted from finite Python floats.

### 7.3 Required top-level sections

```text
schema
record_id
provenance
topology
scenario
factor
phase
task
safety
send
task_space
smoothness
income
release
trace
accumulator_audit
```

Every section is required. `additionalProperties=false`.

### 7.4 Exact field contract

#### `provenance`

| Field | Type / rule | Producer |
|---|---|---|
| `scientific_plan_id` | exact `base_v20_R1_policy_behavior_v1` | frozen config |
| `admission_plan_id` | exact `base_v20_R2_admission_execution_v1` | frozen config |
| `source_lock_sha256` | lowercase 64 hex | runner |
| `git_commit` | exact active 40-hex commit | runner + runtime |
| `plan_sha256` | exact R2 plan digest from plan lock | runner |
| `r1_plan_sha256` | exact `682729...e3c` | runner |
| `b0_json_sha256` | exact `98654a...826` | runner |
| `b0_csv_sha256` | exact `209b33...58a` | runner |
| `urdf_path` | exact runtime path | resolved Hydra config |
| `urdf_sha256` | exact `d02cda...a1d5` | runner rehash |
| `checkpoint_path` | immutable numeric checkpoint path | runner |
| `checkpoint_sha256` | exact checkpoint digest | runner rehash |
| `checkpoint_step` | non-negative integer parsed from immutable name | runner |
| `source_config_path` | canonical repo-relative R2 config | source lock |
| `source_config_sha256` | exact group-specific digest | source lock |
| `resolved_config_sha256` | exact runtime-resolved Hydra digest | runner |
| `runtime_config_sha256` | exact `.hydra/runtime_config.yaml` digest | runner |
| `command_sha256` | digest of canonical argv/env contract | runner |
| `run_uuid` | UUIDv4 generated before spawn | runner |
| `seed` | exact integer | runtime config |
| `env_id` | unique integer within run | environment |
| `episode_ordinal` | exactly 0 for first-episode-only eval | environment |

#### `topology`

```text
name: canonical16 | pooled_seed16 | holdout_seed16 | forced1 | render1
environment_count: positive int
expected_episode_count: positive int
first_episode_only: true
single_process: true
physical_gpu: integer 0-6
render: bool
```

#### `scenario`

Required raw door values, never inferred from bucket labels:

```text
scenario_id
door_open_lr
door_width_m
door_height_m
handle_height_m
handle_edge_distance_m
door_mass_kg
hinge_damping
hinge_stiffness
hinge_max_force_nm
handle_damping
handle_stiffness
handle_max_force_nm
initial_root_pose_se2
```

All numeric fields finite; dimensions/mass positive; `door_open_lr` exactly `-1` or `+1`.

#### `factor`

```text
group: G1..G7 or B0 or FORCED
send_curriculum: bool
economics: bool
arm_tie: bool
curriculum_phase: disabled | soft | hard
theta_send_rad: 0.90
root_x_margin_m: 0.03
arm_tangent_scale: 0.0 or 3.5
arc_tracking_scale: 0.0 or 0.85
```

#### `phase`

```text
opening_start_step
opening_start_batch
terminal_step
terminal_batch
max_stage
stage_at_terminal
time_in_terminal_stage
reset_origin: initial | staged
reset_stage
reset_snapshot_index
schedule_transition_observed
```

Event-step fields use typed event objects:

```json
{"observed": false, "step": null}
```

or

```json
{"observed": true, "step": 123}
```

No generic `N/A` is permitted.

#### `task`

```text
goal: bool
complete: bool
terminal_reason: exact non-empty string
crossing_event.observed: bool
crossing_event.step: int|null
crossing_while_holding: bool|null
release_event.observed: bool
release_event.step: int|null
task_time_s: finite non-negative float|null
```

If an event is not observed, its conditioned values are null and its event object is explicit. A goal without an observed crossing event is structurally invalid.

#### `safety`

```text
upper_dof_overspeed: bool
body_collision: bool
door_body_contact: bool
body_contact_force_max_n: metric object
post_release_body_contact: bool|null
post_release_body_force_max_n: metric object
pre_cross_bilateral_rate: metric object
pre_cross_coasting_rate: metric object
pre_cross_over_force_rate: metric object
```

#### `send`

```text
send_ready: bool
first_send_event: event object
pre_send_crossing_event: event object
hinge_at_first_crossing_rad: metric object
root_x_at_first_crossing_m: metric object
send_before_crossing: bool|null
max_forward_displacement_m: metric object
max_lateral_displacement_m: metric object
max_planar_displacement_m: metric object
max_abs_yaw_change_rad: metric object
stage4_overtime: bool
```

#### `task_space`

Every distribution has `state`, `sample_count`, `p10`, `p50`, `p95`, and `max`. `state` is `DEFINED` or a specific reason code from this list:

```text
NO_VALID_REFERENCE
NO_VALID_HOLD
NO_PRE_SEND_INTERVAL
INSUFFICIENT_CONSECUTIVE_SAMPLES
NO_ACTIVE_TANGENT_SAMPLES
```

No field uses `N/A`; values are null only when `state != DEFINED`.

Required distributions:

```text
arm_tangent_share
positive_arm_tangent_mps
positive_base_tangent_mps
arc_position_error_m
arc_orientation_error_rad
along_handle_slip_m
orthogonal_arc_residual_m
```

Required integrals:

```text
positive_arm_tangent_integral_m
positive_base_tangent_integral_m
arm_integral_share
```

#### `smoothness`

Required distributions:

```text
positive_hinge_velocity_radps
hinge_acceleration_radps2
hinge_jerk_radps3
arm_raw_action_rate_per_step
arm_raw_action_jerk_per_step2
```

#### `income`

```text
positive_total_income
positive_a_income
positive_a_income_ratio
reward_component_sums: complete mapping for every enabled reward component
```

If `positive_total_income <= 0`, the record is structurally valid only with reason `NO_POSITIVE_INCOME`, but it is ineligible for every policy gate. It is never assigned a ratio of zero.

#### `release`

```text
observed
hinge_at_release_rad
root_x_at_release_m
held_hinge_max_rad
opening_slip_max_m
post_release_body_contact
post_release_body_force_max_n
```

Conditioned fields are null only when `observed=false`.

#### `trace`

```text
path
sha256
row_count
first_step
last_step
terminal_row_index
```

The record does not embed a scalar or list `step_index`. The referenced JSONL trace is the source of truth.

#### `accumulator_audit`

```text
pre_cross_steps
valid_hold_steps
pre_send_steps
active_tangent_steps
hinge_velocity_samples
hinge_acceleration_samples
hinge_jerk_samples
action_rate_samples
action_jerk_samples
reward_steps
snapshot_rejections_by_reason
post_load_derivative_warmup_exclusions
```

### 7.5 Metric object

Every scalar/distribution metric uses one of:

```json
{"state":"DEFINED","sample_count":42,"value":0.1}
```

or

```json
{"state":"NO_PRE_SEND_INTERVAL","sample_count":0,"value":null}
```

Distributions replace `value` with `p10/p50/p95/max`. Bare null, zero-filled missing data, free-form reasons, and generic `N/A` are rejected.

### 7.6 Step trace schema

`a2_piper_v20_R2_step_trace_v1` is JSONL, one row per control step for every first episode. Required fields include:

```text
schema
run_uuid
env_id
episode_ordinal
step_index
batch_index
stage
curriculum_phase
root_se2
door_hinge_position_rad
door_hinge_velocity_radps
hold_valid
bilateral
coasting
over_force
send_ready
pre_send_crossing_event
root_crossing_event
release_event
root_x_rel_m
arm_raw_action_6d
taskspace_active
positive_arm_tangent_mps
positive_base_tangent_mps
arm_tangent_share
arc_position_error_m
arc_orientation_error_rad
along_handle_slip_m
orthogonal_arc_residual_m
reward_components_scaled
terminal
terminal_reason
```

For each `(run_uuid, env_id)`:

```text
step_index starts at 0
step_index is unique and contiguous
exactly one terminal row exists
the terminal row is last
terminal_reason matches the episode record
row_count == last_step + 1
```

### 7.7 Required live accumulators and exact update mapping

Full sample arrays are allocated only when `env.config.a2_v20_R2_evidence_enabled=true`. Training uses lightweight counters and episode event JSONL; evaluation uses full arrays sized `[num_envs, max_episode_length]` plus masks.

| Buffer | Update scope and formula | Final field |
|---|---|---|
| `_r2_pre_cross_step_count` | increment during opening phase before first physical crossing | denominator for pre-cross rates |
| `_r2_bilateral_count` | increment when bilateral mask true in pre-cross scope | `pre_cross_bilateral_rate` |
| `_r2_coasting_count` | increment when coasting mask true in pre-cross scope | `pre_cross_coasting_rate` |
| `_r2_over_force_count` | increment when over-force mask true in pre-cross scope | `pre_cross_over_force_rate` |
| `_r2_hinge_velocity_samples/mask` | positive hinge velocity during valid-held opening before release | smoothness velocity distribution |
| `_r2_prev_hinge_velocity/_valid` | updated only on consecutive valid scope steps | acceleration input |
| `_r2_hinge_accel_samples/mask` | `(v_t-v_t-1)/dt` on consecutive valid steps | acceleration distribution |
| `_r2_prev_hinge_accel/_valid` | updated only on consecutive acceleration samples | jerk input |
| `_r2_hinge_jerk_samples/mask` | `(a_t-a_t-1)/dt` | jerk distribution |
| `_r2_prev_arm_raw_action/_valid` | six learned arm raw actions, policy output indices `5:11`, before delta accumulation/warping | action-rate input |
| `_r2_arm_action_rate_samples/mask` | `L2(a_t-a_t-1)` per control step | action-rate distribution |
| `_r2_prev_arm_action_rate_vector/_valid` | stores first difference vector, not its norm | action-jerk input |
| `_r2_arm_action_jerk_samples/mask` | `L2((a_t-a_t-1)-(a_t-1-a_t-2))` | action-jerk distribution |
| `_r2_arm_share_samples/mask` | valid-held, pre-send, active tangent samples | arm-share distribution |
| `_r2_positive_arm_samples/mask` | same scope | arm tangent distribution |
| `_r2_positive_base_samples/mask` | same scope | base tangent distribution |
| `_r2_arc_position_samples/mask` | valid captured reference + valid hold + pre-send | arc position distribution |
| `_r2_arc_orientation_samples/mask` | same | arc orientation distribution |
| `_r2_along_slip_samples/mask` | same | along-slip distribution |
| `_r2_orthogonal_residual_samples/mask` | same | orthogonal residual distribution |
| `_r2_positive_arm_integral` | `+= positive_arm_tangent * dt` in active pre-send scope | arm integral |
| `_r2_positive_base_integral` | `+= positive_base_tangent * dt` | base integral |
| `_r2_positive_total_income` | `+= sum(max(scaled_component,0))` each reward step | positive total income |
| `_r2_positive_a_income` | `+= max(scaled_arm_tangent,0)+max(scaled_arc_tracking,0)` | A income |
| `_r2_reward_component_sums` | exact scaled component sum per registered reward name | reward decomposition |
| `_r2_body_contact_force_max` | max of body/panel/frame force observations over episode | safety max |
| `_r2_held_hinge_max` | maximum hinge under valid hold before release | held hinge |
| `_r2_opening_slip_max` | maximum valid handle-local total/along opening slip under hold | opening slip |
| `_r2_trace_rows` | one row after post-physics state/reward update and before reset | trace artifact |

### 7.8 Reward-component hook

Modify `LeggedRobotBase._compute_reward` to collect each raw and scaled component in local dictionaries and call:

```python
self._after_reward_components(raw_components, scaled_components)
```

The base implementation is a no-op. `DoorPregrasp` validates complete reward-name coverage and updates R2 income accumulators. The hook cannot change `rew_buf`, `episode_sums`, component values, or reset state. A unit test compares rewards bit-for-bit with evidence disabled.

### 7.9 Finalization timing

Finalize the production episode record after all terminal reasons are marked and before episode buffers are reset. The sequence is:

```text
post-physics state update
reward computation and income hook
termination marking
append terminal trace row
finalize episode record
atomic append to record-set staging file
reset environment buffers
```

A record is never built from a single terminal diagnostic snapshot.

---

## 8. Strict status vocabulary

### 8.1 Producer states

Raw producers may emit only:

```text
SOURCE_FROZEN
COMMAND_PLANNED
PROCESS_STARTED
PROCESS_COMPLETED
RECORD_SET_COMPLETE
LAUNCH_PLAN_COMPLETE
ATTEMPT_CONSUMED
```

These are not PASS states.

### 8.2 Adjudicator states

```text
STATIC_PASS
RUNTIME_PASS
RUNTIME_SEMANTIC_PASS
POLICY_LEARNABILITY_PASS
SMOKE_PASS
FORMAL_COMPLETION_PASS
STRICT_VALID
STRICT_INVALID
INCONCLUSIVE
POLICY_PASS
POLICY_FAIL
NO_PROMOTABLE_CHECKPOINT
NO_RELEASE
```

`INCONCLUSIVE` is reserved for an interrupted run that produced no complete strict evidence unit. It does not permit a retry unless the relevant stage explicitly allows one. `STRICT_INVALID` evidence is retained and cannot become zero or a failure count by coercion.

---

## 9. Device contract

### 9.1 Non-render jobs

For training, B0, forced semantics, zero-shot, pilot evaluation, smoke, formal, M22, pooled, and holdout:

```text
ACCELERATE_TORCH_DEVICE=cuda:N
CUDA_VISIBLE_DEVICES is absent
AppLauncher device = cuda:N
Accelerator device = cuda:N
N is one of 0,1,2,3,4,5,6
```

The command must not address logical `cuda:0` when `N != 0`.

### 9.2 Render jobs

For rendering only:

```text
CUDA_VISIBLE_DEVICES=N
ACCELERATE_TORCH_DEVICE=cuda:0
AppLauncher device = cuda:0
Accelerator device = cuda:0
N is one of 0,1,2,3,4,5,6
```

### 9.3 GPU7

Any argv, environment, process receipt, resolved config, Vulkan device, or CUDA observation containing physical GPU7 fails before spawn or causes `STRICT_INVALID` after runtime. No “reserved but visible” exception exists.

### 9.4 Device acceptance tests

Positive:

- non-render GPU3 has no visibility mask and uses `cuda:3` everywhere;
- render GPU3 exposes only GPU3 and uses logical `cuda:0`;
- observed NVML PID binding matches the requested physical GPU.

Negative:

- non-render visibility mask present;
- render visibility mask absent;
- render uses logical `cuda:3`;
- any GPU7 token;
- AppLauncher/Accelerator mismatch;
- a subprocess inherits a prohibited mask.

---

## 10. Source freeze and P0 static admission

### 10.1 Bounded source revisions

R2 permits exactly two frozen static candidates:

```text
revision 0 = first complete R2 implementation
revision 1 = one bounded repair after binding independent review
```

The rejected R1 revision-4 candidate does not count as R2 revision 0. There is no R2 revision 2.

### 10.2 Exact source-freeze commands

```bash
REPO=/home/baoquanc/workspace/DoorDog-A2_Piper
PY=/home/baoquanc/anaconda3/envs/isaaclab/bin/python

$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_source_freeze \
  --repo-root "$REPO" \
  --revision 0 \
  --required-branch A2_Piper \
  --required-ancestor 83cec1036a73c08565601df93aae40ee86856109 \
  --output "$REPO/logs_eval/base_v20_R2/locks/R2_REVISION_0_SOURCE_FREEZE.json"
```

The only optional second command changes `--revision 0` to `--revision 1` and the output filename accordingly. The tool refuses a dirty worktree, detached HEAD, symlinked file, untracked source under an owned path, or an existing output.

### 10.3 Source-lock contents

Schema: `a2_piper_base_v20_R2_source_lock_v1`.

It enumerates and hashes:

- active Git commit and tree;
- R2 plan and plan-lock companion;
- immutable R1 plan/B0 inputs;
- checkpoint and adjacent config;
- actual runtime URDF;
- every modified Python/YAML file relative to `83cec...`;
- every R2 script;
- every R2 JSON Schema;
- every base-v20, v20-R1, and v20-R2 test selected by deterministic filesystem discovery;
- all eight source configs;
- all eight resolved Hydra configs;
- observation dimensions, actor action dimension, base command dimension, manipulation action dimension;
- exact command/environment templates.

The source lock contains no PASS field.

### 10.4 Exact P0 runner command

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_p0_runner \
  --repo-root "$REPO" \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/R2_REVISION_0_SOURCE_FREEZE.json" \
  --output-root "$REPO/logs_eval/base_v20_R2/admission/revision0/p0"
```

### 10.5 P0 raw producer

Producer: `a2_piper_v20_R2_p0_runner.py`
Schema: `a2_piper_base_v20_R2_p0_raw_v1`
Output: `p0_execution.json` plus one stdout/stderr pair per command.

The runner executes, rather than merely lists:

1. exact source-lock rehash;
2. `git status --porcelain=v1` and branch/ancestor checks;
3. B0/R1/checkpoint/URDF hash checks;
4. `python -m py_compile` for every changed or added Python file;
5. `git diff --check 83cec1036a73c08565601df93aae40ee86856109 HEAD`;
6. deterministic full test discovery for `test_a2_v20*.py`, `test_a2_v20_R1*.py`, and `test_a2_v20_R2*.py`;
7. the full discovered pytest set in one command and the focused R2 set in one command;
8. Hydra `--cfg job --resolve` for G1-G7 and pilot;
9. exact source-to-resolved config factor tests;
10. disabled-path v19 G2 parity tests;
11. actor/critic observation and action dimension parity;
12. no hidden action override tests;
13. staged-reset store/load ownership tests;
14. M48 production-record-through-production-consumer tests;
15. device-environment tests;
16. canonical output-root and UTC timestamp-format tests.

The raw file stores exact argv, selected environment variables, PID, start/end UTC times, exit code, stdout/stderr paths and hashes, and observed commit for every command.

### 10.6 P0 strict consumer

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_p0_adjudicator \
  --repo-root "$REPO" \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/R2_REVISION_0_SOURCE_FREEZE.json" \
  --raw "$REPO/logs_eval/base_v20_R2/admission/revision0/p0/p0_execution.json" \
  --output "$REPO/logs_eval/base_v20_R2/locks/P0_STATIC_PASS.json"
```

The adjudicator reconstructs the expected command list, rehashes every file and log, verifies every exit code and test count, parses Hydra outputs, and independently checks the factor matrix. It ignores and rejects any raw `status` field.

### 10.7 P0 advance condition

Advance only when:

```text
all commands executed exactly once
all exit codes are zero
full and focused test sets have no skipped/xfailed/error tests unless explicitly allowlisted in the R2 plan lock
py_compile covers every Python source in the source lock
diff-check is clean
all eight Hydra configs resolve
legacy parity/dimension/no-hidden-action checks pass
all three independent reviews return CODE_QUALITY PASS, ISAACLAB_SEMANTICS PASS, and CANDIDATE_GATE PASS
```

The adjudicator then creates `ACTIVE_SOURCE_LOCK.json` and `P0_STATIC_PASS.json`. An independent review failure on revision 0 may authorize revision 1. Any revision-1 failure closes `R2_STATIC_ADMISSION_BLOCKER_FINAL`.

---

## 11. Executable R2-P1 runtime semantic admission

### 11.1 Common execution rule

Every runtime node is launched by an R2 runner that:

1. consumes the exact active source lock and parent PASS marker;
2. reconstructs commands internally;
3. creates output directories with exclusive semantics;
4. spawns the process itself;
5. records process receipts and observed device binding;
6. requires exit 0 and natural shutdown;
7. hashes runtime config, records, traces, and logs;
8. never reads a caller-authored PASS JSON.

### 11.2 B0 no-learning pooled48

#### Producer command

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_eval_runner b0 \
  --repo-root "$REPO" \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --p0-pass "$REPO/logs_eval/base_v20_R2/locks/P0_STATIC_PASS.json" \
  --checkpoint "$REPO/logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt" \
  --physical-gpus 0,1,2 \
  --output-root "$REPO/logs_eval/base_v20_R2/admission/b0"
```

The runner executes seeds `0,1,2`, `16` environments each, first episode only, no learning, S/E/A reward effects disabled, R2 evidence enabled. It uses the exact v19 G2 policy and runtime physics plus R2 telemetry-only code.

Raw producer: `a2_piper_v20_R2_eval_runner.py`
Raw schema: `a2_piper_base_v20_R2_record_set_v1`
Strict consumer: `a2_piper_v20_R2_record_adjudicator.py b0`.

#### Consumer command

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_record_adjudicator b0 \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --b0-reference "$REPO/scriptsFORhuman/v20_R1/a2_piper_base_v20_R1_B0_reference_20260729.json" \
  --seed0 "$REPO/logs_eval/base_v20_R2/admission/b0/seed0/record_set.json" \
  --seed1 "$REPO/logs_eval/base_v20_R2/admission/b0/seed1/record_set.json" \
  --seed2 "$REPO/logs_eval/base_v20_R2/admission/b0/seed2/record_set.json" \
  --output "$REPO/logs_eval/base_v20_R2/locks/B0_RUNTIME_PASS.json"
```

#### Advance condition

- exactly `48` unique strict-valid records;
- exact seeds and environment IDs;
- every trace contiguous and terminal-consistent;
- exact checkpoint/config/URDF/source binding;
- Appendix E.3 parity tolerances all pass;
- formal task-space B0 distributions are defined with required denominators;
- no action/reward/termination change relative to telemetry-disabled G2 parity run.

### 11.3 Forced one-environment semantics

#### Cases

The forced runner executes these exact named cases in one legal GPU process, one environment per case:

```text
S_SOFT_PRE_SEND_CROSS
S_HARD_PRE_SEND_CROSS
SEND_VALID_HOLD
SEND_NO_HOLD
POST_SEND_CROSS
E_ROOT_CROSS_NO_CORRIDOR
E_SEND_ACTIVATES_CORRIDOR
A_PURE_BASE
A_PURE_ARM
A_EQUAL_CONTRIBUTION
A_CLOSING_HINGE
A_INVALID_REFERENCE
SNAPSHOT_SWING_CLEAN
SNAPSHOT_SWING_CONTAMINATED
SNAPSHOT_THROUGH_SENT
SNAPSHOT_THROUGH_UNSENT
STAGED_LOAD_DERIVATIVE_WARMUP
```

The forced environment uses high-level IsaacLab articulation/root state APIs only. Direct PhysX tensor mutation, hidden action override, and DLS control are forbidden.

#### Producer command

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_forced_runner \
  --repo-root "$REPO" \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --b0-pass "$REPO/logs_eval/base_v20_R2/locks/B0_RUNTIME_PASS.json" \
  --physical-gpu 0 \
  --seed 0 \
  --output-root "$REPO/logs_eval/base_v20_R2/admission/forced"
```

Raw schema: `a2_piper_base_v20_R2_forced_trace_v1`. Raw rows contain measured state/reward/termination values and no expected-result booleans.

#### Strict consumer

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_semantic_adjudicator forced \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --raw "$REPO/logs_eval/base_v20_R2/admission/forced/forced_trace.jsonl" \
  --process-receipt "$REPO/logs_eval/base_v20_R2/admission/forced/process_receipt.json" \
  --output "$REPO/logs_eval/base_v20_R2/locks/FORCED_RUNTIME_SEMANTIC_PASS.json"
```

The consumer computes every expected relation itself, including the exact S penalty, terminal ownership, corridor latch, task-space shares, snapshot truth table, and derivative warm-up.

### 11.4 Seven canonical16 zero-shot cells

#### Producer command

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_eval_runner zero-shot \
  --repo-root "$REPO" \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --forced-pass "$REPO/logs_eval/base_v20_R2/locks/FORCED_RUNTIME_SEMANTIC_PASS.json" \
  --checkpoint "$REPO/logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/model_step_002000.pt" \
  --physical-gpus 0,1,2,3,4,5,6 \
  --output-root "$REPO/logs_eval/base_v20_R2/admission/zero_shot"
```

Each cell runs seed0 canonical16, first episode only, no learning. S-enabled cells are evaluated in hard phase; G1/G2 have S disabled. The runner uses the group-specific R2 source config and records its distinct source/resolved/runtime hashes.

#### Strict consumer

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_semantic_adjudicator zero-shot \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --root "$REPO/logs_eval/base_v20_R2/admission/zero_shot" \
  --output "$REPO/logs_eval/base_v20_R2/locks/ZERO_SHOT7_RUNTIME_SEMANTIC_PASS.json"
```

Advance only if all seven record sets are strict-valid and factor semantics match exactly:

| Group | Required active behavior | Required exact-zero behavior |
|---|---|---|
| G1 | telemetry only | S penalty/terminal, E changes, A rewards |
| G2 | E | S penalty/terminal, A rewards |
| G3 | S hard terminal | E changes, A rewards |
| G4 | S hard terminal + E | A rewards |
| G5 | S hard terminal + A | E changes |
| G6 | S hard terminal + E + A | none |
| G7 | S hard terminal + E + A | none |

Distinct group config hashes are required. Equality across all seven hashes is an error, not a gate.

### 11.5 R2-P1 aggregate marker

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_semantic_adjudicator aggregate \
  --p0 "$REPO/logs_eval/base_v20_R2/locks/P0_STATIC_PASS.json" \
  --b0 "$REPO/logs_eval/base_v20_R2/locks/B0_RUNTIME_PASS.json" \
  --forced "$REPO/logs_eval/base_v20_R2/locks/FORCED_RUNTIME_SEMANTIC_PASS.json" \
  --zero-shot "$REPO/logs_eval/base_v20_R2/locks/ZERO_SHOT7_RUNTIME_SEMANTIC_PASS.json" \
  --output "$REPO/logs_eval/base_v20_R2/locks/R2_P1_RUNTIME_SEMANTIC_PASS.json"
```

The aggregate consumer rehashes and reparses all parents. It does not accept a path whose payload merely declares PASS.

---

## 12. Acyclic artifact DAG

```text
R2 plan lock
  -> revision0 source freeze
      -> P0 raw execution
          -> independent P0 adjudication/reviews
              -> ACTIVE_SOURCE_LOCK + P0_STATIC_PASS
                  -> B0 raw record sets
                      -> B0_RUNTIME_PASS
                          -> forced raw traces
                              -> FORCED_RUNTIME_SEMANTIC_PASS
                                  -> seven zero-shot raw record sets
                                      -> ZERO_SHOT7_RUNTIME_SEMANTIC_PASS
                                          -> R2_P1_RUNTIME_SEMANTIC_PASS
                                              -> PILOT_ATTEMPT_CONSUMED
                                                  -> pilot training completion
                                                      -> pilot endpoint record set
                                                          -> PILOT_POLICY_LEARNABILITY_PASS
                                                              -> SMOKE_WAVE_ATTEMPT_CONSUMED
                                                                  -> seven smoke training completions
                                                                      -> SMOKE_PASS
                                                                          -> FORMAL_ADMISSION_BUNDLE
                                                                              -> promoted frozen configs
                                                                                  -> PROMOTION_PASS
                                                                                      -> formal launch plan
                                                                                          -> FORMAL_WAVE_ATTEMPT_CONSUMED
                                                                                              -> seven formal completions
                                                                                                  -> FORMAL_COMPLETION_PASS
                                                                                                      -> exact 70-entry M22 manifest
                                                                                                          -> 70 canonical record sets
                                                                                                              -> M22_70ROW_PASS
                                                                                                                  -> seven selected pooled48 sets
                                                                                                                      -> POOLED7_PASS
                                                                                                                          -> RELEASE_FREEZE
                                                                                                                              -> if release candidate: holdout64
                                                                                                                                  -> HOLDOUT64_PASS
                                                                                                                                      -> real matched renders
                                                                                                                                          -> RENDER_QA_PASS
                                                                                                                                              -> FINAL_DECISION
                                                                                                                              -> if NO_RELEASE: FINAL_DECISION directly
```

No node consumes a downstream artifact. Promotion does not require `POLICY_PASS`; it requires only admission artifacts. A launch manifest is never a runtime PASS. Holdout cannot influence checkpoint or group selection.

---

## 13. One-shot G4 policy learnability pilot

### 13.1 Attempt marker and command

The launcher creates `PILOT_ATTEMPT_CONSUMED.json` atomically before process spawn. Any spawn consumes the attempt, including OOM, interruption, or infrastructure failure.

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_pilot_launcher \
  --repo-root "$REPO" \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --semantic-pass "$REPO/logs_eval/base_v20_R2/locks/R2_P1_RUNTIME_SEMANTIC_PASS.json" \
  --config "$REPO/gr00t/rl/config/ablation/wbmanip/base_v20_R2_P2_G4_learnability_pilot.yaml" \
  --physical-gpu 0 \
  --output-root "$REPO/logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/pilot/G4_seed0_256x750" \
  --launcher-root "$REPO/logs_rl/launchers/base_v20_R2/pilot"
```

Exact identity:

```text
G4 = S+E, A disabled
training seed = 0
physical GPU = 0
num_envs = 256
batches = 750
save = 250
warm start = exact G2 step2000 policy_only
```

### 13.2 Training raw evidence

`ppo_trainer_a2_base_api.py` writes append-only:

```text
r2_training_batch_metrics.jsonl
r2_training_episode_events.jsonl
```

Each row includes active source/config/checkpoint hashes, batch index, schedule phase, environment denominators, completed episode counts, terminal-reason counts, send-ready counts, goal counts, crossing counts, and reward decomposition. The trainer never writes a pilot PASS status.

### 13.3 Endpoint evaluation

After natural batch750 completion, the pilot launcher invokes canonical16 evaluation of `model_step_000750.pt` in hard phase through the production eval runner. It may not use an ad hoc evidence dictionary.

### 13.4 Strict consumer

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_pilot_adjudicator \
  --attempt "$REPO/logs_eval/base_v20_R2/locks/PILOT_ATTEMPT_CONSUMED.json" \
  --training-root "$REPO/logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/pilot/G4_seed0_256x750" \
  --endpoint "$REPO/logs_eval/base_v20_R2/pilot/endpoint/record_set.json" \
  --output "$REPO/logs_eval/base_v20_R2/locks/PILOT_POLICY_LEARNABILITY_PASS.json"
```

It computes all R1 pilot gates from production traces/records and training JSONL. The frozen gates remain:

```text
exact 750/750 natural completion
finite step250/500/750 checkpoints
goal >= 8/16
crossing while holding >= 8/16
send-ready >= 4/16
hinge@crossing p50 >= 0.82 rad
hinge@crossing p10 >= 0.70 rad
p50 improvement over B0 >= 0.10 rad
at least 4/16 crossings at >=0.90 rad
pre-send arm-share p50 >=0.30
overspeed = 0/16
arc position p95 <=0.050 m
arc orientation p95 <=0.90 rad
hinge velocity p95 <=0.45 rad/s
hinge acceleration p95 <=1.25 rad/s2
hinge jerk p95 <=35 rad/s3
action rate p95 <=2.75 per step
action jerk p95 <=4.50 per step2
last-50 send-ready rate >=10%
last-50 goal rate >0
late hard crossing-terminal rate <=0.80 * early hard rate
no terminal reason >95% of late episodes
```

Any failure produces `R2_POLICY_LEARNABILITY_BLOCKER`. There is no pilot retry, resume, alternate seed, reward change, or threshold change.

---

## 14. Seven-cell 64x50 smoke

### 14.1 Attempt marker

`SMOKE_WAVE_ATTEMPT_CONSUMED.json` is created before any group process. It contains seven group-specific config hashes and commands. One group starting consumes the entire wave.

### 14.2 Exact command

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_smoke_launcher \
  --repo-root "$REPO" \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --pilot-pass "$REPO/logs_eval/base_v20_R2/locks/PILOT_POLICY_LEARNABILITY_PASS.json" \
  --physical-gpus 0,1,2,3,4,5,6 \
  --launcher-root "$REPO/logs_rl/launchers/base_v20_R2/smoke" \
  --training-root "$REPO/logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2"
```

Each group is one process, 64 environments, 50 batches, save at 50, formal seed. Because the run ends before batch500, S cells remain in soft phase for all 50 batches.

### 14.3 Common admission

- natural exit 0;
- exact 50/50 batches;
- finite loadable checkpoint and optimizer state;
- exact checkpoint/config/source/device binding;
- no OOM/NCCL/device mismatch/NaN/traceback;
- no staged-reset store/load mismatch;
- all production records/episode JSONL structurally valid;
- disabled factors exact zero;
- GPU7 absent.

### 14.4 Factor admission

| Group | Required positive evidence | Required absence |
|---|---|---|
| G1 | telemetry and normal G2 rewards | S penalty/terminal, E latch/ramp, A income |
| G2 | E target-root gate and send-ready corridor | S penalty/terminal, A income |
| G3 | at least one soft S penalty event | S terminal, E changes, A income |
| G4 | soft S penalty + E | S terminal, A income |
| G5 | soft S penalty + A income within valid scope | S terminal, E changes |
| G6 | soft S penalty + E + A | S terminal |
| G7 | soft S penalty + E + A | S terminal |

### 14.5 Adjudicator

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_smoke_adjudicator \
  --attempt "$REPO/logs_eval/base_v20_R2/locks/SMOKE_WAVE_ATTEMPT_CONSUMED.json" \
  --training-root "$REPO/logs_rl/a2_piper_full_stage_a2_base_smoke/base_v20_R2" \
  --output "$REPO/logs_eval/base_v20_R2/locks/SMOKE_PASS.json"
```

The consumer checks each group against its own expected hash. Distinct config hashes are mandatory. No second smoke wave is allowed.

---

## 15. Promotion and formal admission

### 15.1 Acyclic admission bundle

`FORMAL_ADMISSION_BUNDLE.json` is produced only from:

```text
ACTIVE_SOURCE_LOCK
P0_STATIC_PASS
B0_RUNTIME_PASS
FORCED_RUNTIME_SEMANTIC_PASS
ZERO_SHOT7_RUNTIME_SEMANTIC_PASS
R2_P1_RUNTIME_SEMANTIC_PASS
PILOT_POLICY_LEARNABILITY_PASS
SMOKE_PASS
```

It contains no `POLICY_PASS` requirement.

### 15.2 Config promotion

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_promote_configs \
  --repo-root "$REPO" \
  --admission-bundle "$REPO/logs_eval/base_v20_R2/locks/FORMAL_ADMISSION_BUNDLE.json" \
  --output-root "$REPO/logs_eval/base_v20_R2/promotion/frozen_configs"
```

The only allowed source-to-frozen changes are:

```text
env.config.a2_v20_R2_formal_launch: false -> true
env.config.a2_v20_R2_admission_bundle_sha256: null -> exact bundle SHA-256
```

No other scalar, list, key, interpolation, reward, seed, topology, or factor may differ. Promoted configs are resolved and hashed again. `PROMOTION_PASS.json` binds all seven distinct source/frozen/resolved hashes.

### 15.3 Formal launch plan is not runtime evidence

The formal launcher first emits `formal_launch_plan.json` with producer state `LAUNCH_PLAN_COMPLETE`. It cannot emit `RUNTIME_PASS`.

The exact Hydra override is:

```text
env.config.a2_v20_R2_admission_bundle_sha256 is set by the launcher to the SHA-256 of the exact bytes at logs_eval/base_v20_R2/locks/FORMAL_ADMISSION_BUNDLE.json; the launcher rejects a caller-supplied override
```

Passing the digest at the Hydra root is prohibited.

### 15.4 Formal attempt and GPU map

```text
GPU0 -> G1 seed0
GPU1 -> G2 seed0
GPU2 -> G3 seed0
GPU3 -> G4 seed0
GPU4 -> G5 seed0
GPU5 -> G6 seed0
GPU6 -> G7 seed1
GPU7 -> forbidden
```

Before the first spawn, create `FORMAL_WAVE_ATTEMPT_CONSUMED.json`.

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_formal_launcher \
  --repo-root "$REPO" \
  --promotion-pass "$REPO/logs_eval/base_v20_R2/locks/PROMOTION_PASS.json" \
  --physical-gpus 0,1,2,3,4,5,6 \
  --launcher-root "$REPO/logs_rl/launchers/base_v20_R2/formal" \
  --training-root "$REPO/logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal"
```

### 15.5 Formal completion consumer

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_formal_completion \
  --attempt "$REPO/logs_eval/base_v20_R2/locks/FORMAL_WAVE_ATTEMPT_CONSUMED.json" \
  --training-root "$REPO/logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal" \
  --output "$REPO/logs_eval/base_v20_R2/locks/FORMAL_COMPLETION_PASS.json"
```

Per non-futility-stopped group:

```text
2500/2500 batches
10 immutable numeric checkpoints at 250..2500
natural exit0
finite loadable checkpoint and optimizer payload
exact saved config and source/resolved binding
W&B finished when online, or exact offline completion receipt when offline
no partial/.writing file
process tree closed
```

A preregistered futility stop remains a completed formal outcome, not a replacement cell. Operational failure is retained and is not automatically rerun.

---

## 16. Strict 7x10 M22

### 16.1 Manifest producer

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_m22_manifest \
  --formal-completion "$REPO/logs_eval/base_v20_R2/locks/FORMAL_COMPLETION_PASS.json" \
  --training-root "$REPO/logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal" \
  --output "$REPO/logs_eval/base_v20_R2/m22/m22_manifest.json"
```

Schema: `a2_piper_base_v20_R2_m22_manifest_v1`.

Exactly 70 entries are required:

```text
G1..G7 x checkpoint steps 250,500,750,1000,1250,1500,1750,2000,2250,2500
```

Each entry contains:

```text
entry_id = SHA256(canonical entry without entry_id)
group
checkpoint_step
checkpoint_path
checkpoint_sha256
training_run_config_path
training_run_config_sha256
frozen_source_config_sha256
resolved_config_sha256
scientific_plan_id
admission_plan_id
formal_completion_sha256
```

Aliases such as `last.pt` are forbidden.

### 16.2 Runner

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_m22_runner \
  --manifest "$REPO/logs_eval/base_v20_R2/m22/m22_manifest.json" \
  --physical-gpus 0,1,2,3,4,5,6 \
  --output-root "$REPO/logs_eval/base_v20_R2/m22/runs"
```

The runner executes all entries. It cannot expose a single-group-only CLI. Each output record set carries its exact `entry_id`.

### 16.3 One-to-one adjudication

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_m22_adjudicator \
  --manifest "$REPO/logs_eval/base_v20_R2/m22/m22_manifest.json" \
  --runs "$REPO/logs_eval/base_v20_R2/m22/runs" \
  --output "$REPO/logs_eval/base_v20_R2/locks/M22_70ROW_PASS.json"
```

The consumer constructs two maps keyed by `entry_id` and requires exact set equality. It rejects:

- duplicate entry IDs;
- duplicate `(group,step)` identities;
- missing or extra rows;
- checkpoint substitution;
- config substitution;
- a row copied from another checkpoint/group;
- mutable aliases;
- strict-invalid evidence represented as zero.

Each row receives `STRICT_VALID` or `STRICT_INVALID`. Within-group checkpoint selection uses the unchanged R1 lexicographic order. If no checkpoint passes canonical hard gates, the best strict-valid diagnostic checkpoint is retained but marked `NO_PROMOTABLE_CHECKPOINT`.

---

## 17. Selected pooled48

### 17.1 Producer

All seven mechanically selected checkpoints, including diagnostic-only selections, receive pooled evaluation:

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_pooled_runner \
  --m22 "$REPO/logs_eval/base_v20_R2/locks/M22_70ROW_PASS.json" \
  --physical-gpus 0,1,2,3,4,5,6 \
  --output-root "$REPO/logs_eval/base_v20_R2/pooled"
```

Each group runs seeds0,1,2, 16 first episodes per seed. Exact 48 unique scenario identities are required.

### 17.2 Adjudicator

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_pooled_adjudicator \
  --m22 "$REPO/logs_eval/base_v20_R2/locks/M22_70ROW_PASS.json" \
  --root "$REPO/logs_eval/base_v20_R2/pooled" \
  --output "$REPO/logs_eval/base_v20_R2/locks/POOLED7_PASS.json"
```

It validates seven disjoint group reports, 48 strict records each, exact scenario matching, full M48 metrics, and all frozen R1 policy gates. `POOLED7_PASS` means the seven reports are complete and adjudicated; it does not mean a release exists.

---

## 18. Mechanical release freeze and holdout64

### 18.1 Simplest-passing-group logic

From pooled results, eligible groups are those passing every hard pooled gate. Selection order is fixed:

```text
1. G1
2. G2
3. G3
4. G4
5. G5
6. G6/G7 replicated full-method pair
```

G6/G7 are eligible only if both pass all hard gates and satisfy the A-factor replication gate. When the pair is eligible, choose between the two selected checkpoints by lower pooled median task time; if equal within `1e-9`, choose earlier checkpoint step; if still equal, choose G6.

A more complex group can never replace a simpler passing group because it has a numerically better secondary metric.

### 18.2 Release freeze

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_release_freeze \
  --pooled "$REPO/logs_eval/base_v20_R2/locks/POOLED7_PASS.json" \
  --output "$REPO/logs_eval/base_v20_R2/locks/RELEASE_FREEZE.json"
```

If no group passes, the artifact states `NO_RELEASE` and the DAG skips holdout/render promotion to a release. Diagnostic renders may still be produced, but final status remains no-release.

### 18.3 Holdout producer

For one frozen candidate only:

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_holdout_runner \
  --release-freeze "$REPO/logs_eval/base_v20_R2/locks/RELEASE_FREEZE.json" \
  --physical-gpus 0,1,2,3 \
  --seeds 3,4,5,6 \
  --output-root "$REPO/logs_eval/base_v20_R2/holdout"
```

### 18.4 Holdout adjudicator

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_holdout_adjudicator \
  --release-freeze "$REPO/logs_eval/base_v20_R2/locks/RELEASE_FREEZE.json" \
  --root "$REPO/logs_eval/base_v20_R2/holdout" \
  --output "$REPO/logs_eval/base_v20_R2/locks/HOLDOUT64_PASS.json"
```

Exactly 64 records, seeds3-6, 16 each. A failure confirms no release; the tool cannot search holdout seeds for a replacement.

---

## 19. Real matched render execution and QA

### 19.1 Queue membership

Render these checkpoint bindings:

1. G1 selected checkpoint;
2. simplest selected S-enabled checkpoint among G3 then G4 then G5, using the first available in that order;
3. G6 selected checkpoint;
4. G7 selected checkpoint;
5. frozen release checkpoint if it is not already included.

### 19.2 Deterministic matched doors

Choose three scenarios from the frozen pooled topology without using policy outcomes:

- **low/light/weak:** lexicographic minimum of `(handle_height_m, door_mass_kg, hinge_max_force_nm, scenario_id)`;
- **high/heavy/strong:** lexicographic maximum of the same tuple;
- **median:** scenario minimizing the absolute difference between its rank-sum and the median rank-sum, ties by `scenario_id`.

The render queue stores exact scenario parameter hashes.

### 19.3 Cameras

```text
default
handle_side
handle_top
```

Every checkpoint receives all three doors and all three cameras. Output video is `1280x720`, `20 fps`, H.264 MP4, with synchronized sidecar telemetry.

### 19.4 Real runner

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_render_runner \
  --release-freeze "$REPO/logs_eval/base_v20_R2/locks/RELEASE_FREEZE.json" \
  --m22 "$REPO/logs_eval/base_v20_R2/locks/M22_70ROW_PASS.json" \
  --pooled "$REPO/logs_eval/base_v20_R2/locks/POOLED7_PASS.json" \
  --physical-gpu 0 \
  --output-root "$REPO/logs_eval/base_v20_R2/render"
```

The runner actually invokes the renderer. It does not accept a caller result JSON. Render device contract is visibility mask plus logical `cuda:0`.

Each episode/camera directory contains:

```text
command.json
process_receipt.json
runtime_config.yaml
video.mp4
video.sha256
frame_manifest.jsonl
overlay_source.jsonl
trace_binding.json
stdout.log
stderr.log
```

### 19.5 Mechanical media QA

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_render_qa \
  --root "$REPO/logs_eval/base_v20_R2/render" \
  --output "$REPO/logs_eval/base_v20_R2/render/render_qa.json"
```

The QA tool:

- runs `ffprobe` and stores raw output;
- decodes every frame with PyAV;
- verifies exact resolution, fps, codec, nonzero duration, and no decode error;
- verifies frame indices contiguous and equal to sidecar count;
- verifies overlay-source rows bind to the same production M48 trace;
- verifies camera/scenario/checkpoint/config hashes;
- rejects `.writing`, zero-frame, duplicate, substituted, or truncated media;
- verifies the overlay burn-in region is nonempty in every sampled frame and its source hash matches the sidecar.

### 19.6 Human behavior review without caller-declared PASS

Two independent reviewers run:

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_render_review \
  --render-qa "$REPO/logs_eval/base_v20_R2/render/render_qa.json" \
  --reviewer-id reviewer_A \
  --output "$REPO/logs_eval/base_v20_R2/render/review_A.json"
```

and the same command with `reviewer_B`. The CLI presents each fixed checklist item; it computes the verdict and binds every answer to the video SHA. It does not accept a top-level PASS argument. Any disagreement is render failure, not a third-review opportunity.

Checklist:

```text
no pre-send root crossing
arm visibly initiates/sustains send
base follows only after send
no fling
no grasp loss or handle-end instability
no body/leg-door collision
controlled release and passage
```

`RENDER_QA_PASS.json` requires mechanical QA plus two agreeing computed reviews.

---

## 20. Final analysis and no-release logic

Release-candidate branch:

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_final_analysis release \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --m22 "$REPO/logs_eval/base_v20_R2/locks/M22_70ROW_PASS.json" \
  --pooled "$REPO/logs_eval/base_v20_R2/locks/POOLED7_PASS.json" \
  --release-freeze "$REPO/logs_eval/base_v20_R2/locks/RELEASE_FREEZE.json" \
  --holdout "$REPO/logs_eval/base_v20_R2/locks/HOLDOUT64_PASS.json" \
  --render "$REPO/logs_eval/base_v20_R2/locks/RENDER_QA_PASS.json" \
  --output "$REPO/logs_eval/base_v20_R2/locks/FINAL_DECISION.json"
```

No-release branch:

```bash
$PY -B -m scriptsFORhuman.v20_R2.a2_piper_v20_R2_final_analysis no-release \
  --source-lock "$REPO/logs_eval/base_v20_R2/locks/ACTIVE_SOURCE_LOCK.json" \
  --m22 "$REPO/logs_eval/base_v20_R2/locks/M22_70ROW_PASS.json" \
  --pooled "$REPO/logs_eval/base_v20_R2/locks/POOLED7_PASS.json" \
  --release-freeze "$REPO/logs_eval/base_v20_R2/locks/RELEASE_FREEZE.json" \
  --output "$REPO/logs_eval/base_v20_R2/locks/FINAL_DECISION.json"
```

The no-release subcommand requires `RELEASE_FREEZE.json` to contain the mechanically computed `NO_RELEASE` state and rejects holdout/render inputs. The release subcommand requires both holdout and render PASS artifacts.

The consumer independently recomputes:

- exact 70-row completeness;
- each within-group checkpoint selection;
- each pooled gate;
- simplest-passing-group order;
- A replication eligibility;
- frozen candidate binding;
- holdout confirmation;
- render binding and verdict.

Outcomes:

```text
POLICY_PASS with exactly one release checkpoint
or
NO_RELEASE with exact failed-gate lists
```

G2 step2000 remains a previous v19 operational reference and can never be labeled a base_v20_R2 release unless G1/G2 formal training produces a new selected checkpoint that passes every R1 release gate.

---

## 21. Frozen policy gates

R2 does not change these gates.

### 21.1 Common task/safety

| Metric | Canonical16 | Pooled48 | Holdout64 |
|---|---:|---:|---:|
| Goal | `>=15/16` | `>=46/48` | `>=60/64` |
| Crossing while holding | `>=15/16` | `>=46/48` | `>=60/64` |
| Upper-DOF overspeed | `0` | `0/48` | `0/64` |
| Pre-cross bilateral | `>=99%` | `>=99%` | `>=99%` |
| Pre-cross coasting | `<2%` | `<2%` | `<2%` |
| Pre-cross over-force | `<2%` | `<2%` | `<2%` |
| Post-release body contact | report | `<=2/48` | `<=3/64` |
| Post-release force p95 | report | `<80 N` | `<80 N` |
| Opening slip p95 | `<=3 cm` if defined | `<=3 cm` | `<=3 cm` |
| Held hinge | report | p50 `>=1.45`, p95 `>=1.50 rad` | same |

### 21.2 Send-first

```text
zero goal episodes with pre-send crossing
send-before-cross >=15/16 canonical, >=46/48 pooled, >=60/64 holdout
hinge at first crossing p50 >=0.90 rad
hinge at first crossing p10 >=0.85 rad
crossing-hinge p50 improvement over B0 >=0.15 rad
pre-send forward p95 <=0.20 m
pre-send lateral p95 <=0.15 m
pre-send planar p95 <=0.25 m
pre-send yaw p95 <=0.30 rad
stage4 overtime <=2/48 pooled with no one-bucket concentration
```

### 21.3 Arm-majority / arc

```text
pre-send arm tangent share p50 >=0.60
pre-send arm tangent share p10 >=0.45
relative p50 improvement over frozen B0 diagnostic >=0.15
TCP-handle position error p95 <=0.030 m
TCP-handle orientation error p95 <=0.25 rad
along-handle slip p95 <=0.030 m
A positive-income ratio p95 <=10%
```

### 21.4 Smoothness / fluency

```text
positive hinge velocity p95 <=0.40 rad/s
hinge acceleration p95 <=1.00 rad/s2
hinge jerk p95 <=28 rad/s3
arm raw-action rate p95 <=2.20 per control step
arm raw-action jerk p95 <=3.60 per control step2
median successful task time <=15.0 s
render behavior PASS
```

---

## 22. Gate-to-evidence contract matrix

| Gate | Raw evidence producer | Raw schema | Strict consumer | Exact DAG advance |
|---|---|---|---|---|
| Source freeze | `source_freeze.py` | `source_lock_v1` | `p0_adjudicator.py` | exact clean source hashes |
| P0 | `p0_runner.py` | `p0_raw_v1` | `p0_adjudicator.py` + 3 independent reviews | `P0_STATIC_PASS` |
| B0 | `eval_runner.py b0` + environment M48 producer | `record_set_v1` | `record_adjudicator.py b0` | `B0_RUNTIME_PASS` |
| Forced | `forced_runner.py` | `forced_trace_v1` | `semantic_adjudicator.py forced` | `FORCED_RUNTIME_SEMANTIC_PASS` |
| Seven zero-shot | `eval_runner.py zero-shot` | seven `record_set_v1` | `semantic_adjudicator.py zero-shot` | `ZERO_SHOT7_RUNTIME_SEMANTIC_PASS` |
| R2-P1 aggregate | prior strict artifacts | `semantic_adjudication_v1` | `semantic_adjudicator.py aggregate` | `R2_P1_RUNTIME_SEMANTIC_PASS` |
| Pilot | `pilot_launcher.py`, trainer JSONL, eval runner | `training_attempt_v1` + `record_set_v1` | `pilot_adjudicator.py` | `PILOT_POLICY_LEARNABILITY_PASS` |
| Smoke | `smoke_launcher.py`, trainer JSONL | seven process/training receipts | `smoke_adjudicator.py` | `SMOKE_PASS` |
| Promotion | `promote_configs.py` | config-promotion record | same tool strict verify + P0 config verifier | `PROMOTION_PASS` |
| Formal completion | `formal_launcher.py` and trainer | process/checkpoint receipts | `formal_completion.py` | `FORMAL_COMPLETION_PASS` |
| M22 | `m22_manifest.py`, `m22_runner.py` | manifest + 70 record sets | `m22_adjudicator.py` | `M22_70ROW_PASS` |
| Pooled | `pooled_runner.py` | 21 seed record sets | `pooled_adjudicator.py` | `POOLED7_PASS` |
| Release freeze | pooled strict artifact | `release_freeze_v1` | `release_freeze.py` | exactly one candidate or `NO_RELEASE` |
| Holdout | `holdout_runner.py` | four record sets | `holdout_adjudicator.py` | `HOLDOUT64_PASS` or no-release |
| Render | `render_runner.py` | real MP4 + sidecars | `render_qa.py` + two computed reviews | `RENDER_QA_PASS` |
| Final | all strict parents | `final_decision_v1` | `final_analysis.py` | `POLICY_PASS` or `NO_RELEASE` |

---

## 23. Required positive and negative tests

### 23.1 Production-record integration

Positive:

- run the actual environment finalizer to produce a record;
- write its trace;
- feed that exact record set into the actual record adjudicator;
- aggregate canonical16 and confirm expected metrics.

Negative:

- scalar `trace.step_index` rejected;
- mutated trace after record creation rejected by SHA;
- all smoothness denominators zero rejected for gate eligibility;
- absent income denominator rejected;
- omitted plan/checkpoint/config/URDF hash rejected;
- bare null and generic `N/A` rejected;
- duplicate env ID rejected;
- non-contiguous trace rejected.

### 23.2 Self-attestation bypass

Negative tests must prove:

- a handcrafted `{"status":"RUNTIME SEMANTIC PASS"}` is rejected;
- a raw artifact containing `checks_passed=true` is rejected by schema;
- command builders that were not executed cannot produce an adjudication;
- missing stdout/stderr/process receipt fails;
- exit code absent or nonzero fails;
- caller-supplied counts differing from raw rows are ignored and rejected.

### 23.3 DAG bypass

- pilot launcher without exact R2-P1 parent fails;
- smoke launcher without pilot PASS fails;
- promotion without smoke PASS fails;
- promotion with a pre-promotion `POLICY_PASS` artifact is irrelevant and rejected if supplied;
- formal launcher without `PROMOTION_PASS` fails;
- formal launch plan cannot satisfy formal completion;
- wrong Hydra key for admission hash fails;
- missing commit binding fails;
- any parent hash mutation invalidates downstream artifacts.

### 23.4 M22/pooled/holdout

- duplicate one checkpoint row 10 times fails;
- substitute G1 row for G2 fails;
- 69 or 71 entries fail;
- `last.pt` fails;
- pooled seed repeated or omitted fails;
- holdout result used to choose another checkpoint fails;
- a simpler passing group skipped for a complex group fails final analysis.

### 23.5 Render

- self-declared render result without MP4 fails;
- zero-frame/truncated/undecodable MP4 fails;
- wrong checkpoint/config/camera/scenario binding fails;
- wrong device contract fails;
- overlay sidecar not matching M48 trace fails;
- one reviewer disagreement fails.

### 23.6 Hidden behavior changes

- R2 evidence disabled must reproduce v19 G2 action/reward/termination bit-for-bit for canonical forced parity;
- evidence hooks cannot write actions, root state, joint targets, reward values, or reset buffers;
- actor output remains 12D high-level action;
- no new actor observation contains `send_ready` or privileged hinge state;
- no DLS or scripted fallback is reachable in training/eval policy paths.

---

## 24. Bounded implementation order

### Phase I — contracts before behavior

1. Add R2 plan lock and schemas.
2. Add `_r2_common.py` and source-freeze/P0 tools.
3. Add negative schema, no-overwrite, path, hash, and device tests.
4. No environment behavior change is accepted before these tests pass locally.

### Phase II — M45/M47 repair

5. Implement snapshot admission truth table and load-time validation.
6. Implement task-space finite-safe math.
7. Add staged-reset and task-space positive/negative tests.
8. Run disabled-path parity tests.

### Phase III — M48 production instrumentation

9. Add live accumulators and reward hook.
10. Add sole episode-record and trace producers.
11. Add production record -> production consumer integration tests.
12. Remove production use of revision-4 normalizer/builder.

### Phase IV — executable admission

13. Implement P0 runner/adjudicator.
14. Implement B0 runner/consumer.
15. Implement forced runner/consumer.
16. Implement seven zero-shot runner/consumer.
17. Freeze R2 revision 0 and request three independent reviews.

### Phase V — at most one static repair

18. If revision 0 fails a binding static review, create exactly one revision 1 limited to the reported defects.
19. Re-freeze all source/config/schema hashes.
20. If revision 1 fails any binding static review, stop permanently as `R2_STATIC_ADMISSION_BLOCKER_FINAL`.

### Phase VI — runtime admission and training DAG

21. Run B0 once.
22. Run forced semantics once.
23. Run seven zero-shot cells once.
24. If any node fails, stop as `R2_RUNTIME_SEMANTIC_BLOCKER_FINAL`.
25. Consume and run the pilot once.
26. If pilot fails, stop as `R2_POLICY_LEARNABILITY_BLOCKER`.
27. Consume and run one smoke wave.
28. If smoke fails, stop as `R2_SMOKE_BLOCKER`.
29. Promote, freeze, and run formal once.
30. Complete strict M22, pooled, release freeze, holdout, render, and final analysis without in-place retuning.

---

## 25. One-shot stopping rules

### 25.1 Static revisions

```text
maximum R2 frozen static candidates = 2
revision indexes allowed = 0,1
revision 1 may exist only after a documented revision-0 binding review failure
revision 2 is prohibited
```

### 25.2 Runtime admission

Each of B0, forced, and seven zero-shot may run once under the active source lock. A process spawn consumes that node. No changed-code retry is allowed. An evaluation-only parser repair after completed policy execution is allowed only if:

- policy/environment execution semantics are byte-identical;
- original evidence remains immutable;
- the parser defect is independently reviewed;
- repaired evidence is labeled `TARGETED_EVAL_REPAIR` with old/new hashes;
- the node does not rerun simulation.

### 25.3 Pilot

One process spawn total. No retry or continuation.

### 25.4 Smoke

One seven-cell wave total. No group replacement.

### 25.5 Formal

One run per cell. A preregistered futility stop is final for that cell. No in-place retuning and no replacement cell.

### 25.6 Final closure states

```text
R2_STATIC_ADMISSION_BLOCKER_FINAL
R2_RUNTIME_SEMANTIC_BLOCKER_FINAL
R2_POLICY_LEARNABILITY_BLOCKER
R2_SMOKE_BLOCKER
R2_FORMAL_OPERATIONAL_FAIL
R2_POLICY_NO_RELEASE
R2_POLICY_PASS
```

No failure state automatically creates R3. A new scope requires a new user decision.

---

## 26. Training-readiness transition

`FORMAL_TRAINING_READY` is false until all are true:

```text
ACTIVE_SOURCE_LOCK exists and rehashes cleanly
P0_STATIC_PASS
B0_RUNTIME_PASS
FORCED_RUNTIME_SEMANTIC_PASS
ZERO_SHOT7_RUNTIME_SEMANTIC_PASS
R2_P1_RUNTIME_SEMANTIC_PASS
PILOT_POLICY_LEARNABILITY_PASS
SMOKE_PASS
FORMAL_ADMISSION_BUNDLE exact
PROMOTION_PASS exact
current Git commit equals active source lock
current worktree clean
GPU map 0-6 available and GPU7 absent
```

Only `a2_piper_v20_R2_promote_configs.py` may create the formal admission bundle, and only `a2_piper_v20_R2_formal_launcher.py` may consume it. No manual marker, environment variable, or command-line boolean can set readiness true.

---

## 27. Final implementation checklist

### Repository/static

- [ ] Commit this R2 plan and its plan-lock companion.
- [ ] Preserve R1 plan/B0 hashes exactly.
- [ ] Mark R1 scripts blocked and non-importable by R2.
- [ ] Implement M45 snapshot truth table and load audit.
- [ ] Implement M47 finite-safe task-space math.
- [ ] Implement sole M48 production schema and all accumulators.
- [ ] Implement reward-component observation hook with bitwise reward parity.
- [ ] Implement executable runners and strict consumers.
- [ ] Implement all bypass-negative tests.
- [ ] Freeze revision 0.
- [ ] Obtain CODE_QUALITY, ISAACLAB_SEMANTICS, and CANDIDATE_GATE PASS.
- [ ] Use revision 1 only if revision 0 fails; no revision 2.

### Runtime admission

- [ ] Run B0 pooled48 once.
- [ ] Freeze formal task-space B0.
- [ ] Run forced semantics once.
- [ ] Run seven canonical16 zero-shot cells once.
- [ ] Create R2-P1 aggregate marker only by strict consumer.

### Policy admission

- [ ] Consume pilot attempt and run exact G4 256x750.
- [ ] Evaluate endpoint through production M48 chain.
- [ ] Stop permanently on pilot failure.
- [ ] Consume and run one seven-cell 64x50 smoke wave.
- [ ] Stop on smoke failure.

### Formal/evaluation

- [ ] Promote configs by two-key whitelist only.
- [ ] Freeze admission bundle and group hashes.
- [ ] Consume formal wave and run G1-G7 on GPUs0-6.
- [ ] Complete 70-entry M22 exact-set adjudication.
- [ ] Run seven pooled48 endpoints.
- [ ] Freeze simplest passing candidate or `NO_RELEASE`.
- [ ] Run holdout64 only for the frozen candidate.
- [ ] Execute and decode real matched renders.
- [ ] Produce one final `POLICY_PASS` or `NO_RELEASE` artifact.

---

## 28. Status at R2 document creation

```text
DECISION = FIX_R1_ADMISSION
R1_P1 = CLOSED / P1_PHYSICAL_BLOCKER
R1_REVISION4 = STATIC ADMISSION FAIL / DO NOT EXECUTE
R2_REVISION0 = NOT IMPLEMENTED
R2_P0 = NOT RUN
R2_RUNTIME_ADMISSION = NOT RUN
R2_PILOT = NOT RUN
R2_SMOKE = NOT RUN
R2_FORMAL = NOT RUN
FORMAL_TRAINING_READY = false
G1_G7_MAY_LAUNCH = no
LEGAL_PHYSICAL_GPUS = 0-6 only
```
