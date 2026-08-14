# DoorDog A2+Piper `base_v23` plan R1

**Plan ID:** `base_v23_force_feasibility_initialization_posture_R1`
**Revision:** R1 — 2026-08-09 HKT
**Repository / branch:** `DoorDog-A2_Piper` / `A2_Piper`
**Runtime state:** admission, A1, W1 A2/B1, and Route-A A1/A2/B1 are complete; B2 seed1 RP0 is in progress on GPU0--3. F3 is `F3_NOT_TRIGGERED`, so all seed1 D1 uses `normal`. Route-A A1 selected G1 step2000/G3 step0250/G5 step0500/G7 step1500; A2 selected G2 step1250/G4 step1000/G6 step1500/G8 step0750; B1 selected G1 step1000/G3 step0500/G5 step1500/G7 step0500. Each completed subwave has exact 40 rows / 640 canonical16 episodes. B2 step250 files are timing evidence only, not completion.

This is the sole v23 plan document.  It adapts the v22 control/evaluation flow
while keeping v23 identity and source records separate.  A record is identified
by the current git commit together with its readable source or saved-config
paths.  The original R1 preparation tools write plain JSON/Markdown.  The later
P0.6 stationary-rent and P0.8 state-bank tools are separately bounded evaluator
runner/reducers.  The P0.9 runner verifies only four D0 training smokes.  P0.10
consumed that bounded admission and terminated with the pre-registered F1
branch.  F1 is now implemented and smoke-verified for D0 FULL/RP0.  The owner
decision in section 15 supersedes the former R54 symmetric-window gate and the
former requirement to execute the complete P0.8 intervention suite preformal.

## 1. Scientific question and fixed matrix

The experiment separates initialization, door regime, and posture availability.
The arm effort profile is one P0-calibrated constant shared by every cell; D0
and D1 may differ only in door parameters.  RP0 is a distribution-level actor
mask on raw action indices 3 and 4 (pitch and roll), with semantic neutral value
`0.0`; it is not a post-sample action clamp.

| Group | Initialization | Train door | Posture | Two-GPU execution lane |
|---|---|---|---|---:|
| G1 | v22 warm | D0 | FULL | 0 |
| G2 | v22 warm | D0 | RP0 | 0 |
| G3 | warm head-reset | D0 | FULL | 1 |
| G4 | warm head-reset | D0 | RP0 | 1 |
| G5 | v22 warm | D1 | FULL | 0 |
| G6 | v22 warm | D1 | RP0 | 0 |
| G7 | warm head-reset | D1 | FULL | 1 |
| G8 | warm head-reset | D1 | RP0 | 1 |

Every cell uses 4096 environments, the same network and reward registry, the
same staged-reset schedule, the same optimizer and formal budget, and the same
checkpoint cadence.  Only the registered initialization, door regime, posture
mask, and training seed vary.

## 2. Source and warm-start freeze

The warm checkpoint is the v22 G1 endpoint selected for the v23 anchor:

```text
checkpoint: logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/model_step_001250.pt
load mode: policy_only
saved config: logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/config.yaml
alternates (record only): v22 G4 step1750 and v22 G5 step0750
```

The warm checkpoint, source config, and source paths are readable identity
inputs.  No alternate may silently replace the warm anchor.

### D0 source facts

D0 is the G1 saved training-door distribution, not the v22 Wave-2 mixture:

| Field | Value | Authority |
|---|---:|---|
| Door weight | `[80.0, 160.0] kg` | G1 saved `env.config.a2_door_weight_range` |
| Handle height | `[0.85, 1.0] m` | inherited source default; verify in source reader |
| Hinge max force | `[2.5, 4.5]` configured units | inherited source default; source-derived |
| Hinge damping | `50.0` native units | inherited source default; source-derived |
| Hinge stiffness | `[1.0, 10.0]` native units | inherited source default; source-derived |

The source reader records each field path and authority.  These values are not
P0 behavior measurements.

## 3. D1 curriculum and effort rule

D1 is created by the P0.4 physics-first atlas.  It may use only the validated
global bounds `damping <= 200`, `stiffness <= 30`, and `max_force <= 24`; a
confirmed E2 cell is evaluation-only.  Per the 2026-08-10 owner decision, the
primary classifier is scripted door-side free-return/fixed-torque
`tau_required` compared with the matrix-wide effort40 boundary.  Policy FULL
and ACUTE records are auxiliary only: FULL `>=12/16` valid windows may be
archived, sparse ACUTE is typed `ACUTE_WINDOWS_SPARSE_EXPECTED`, and neither
mode imposes a symmetric completeness gate.

| Training interval | E0/current-like | E1 posture-beneficial | near-E2 | confirmed E2 |
|---|---:|---:|---:|---:|
| 0–20% | 100% | 0% | 0% | 0% |
| 20–50% | 60% | 40% | 0% | 0% |
| 50–100% | 30% | 60% | 10% | 0% |

Normal D1 freezes from the measured physics-first provisional zones with schedule
`100/0/0 -> 60/40/0 -> 30/60/10` (E0/E1/nearE2). F2-100 uses D1-lite exactly
`100/0/0 -> 65/35/0 -> 40/55/5`.  D1-lite halves the near-E2 share and narrows
the E1 upper range.  All labels are provisional and are re-adjudicated after
G4/G8 head-reset RP0 training.  The former `min(C_FULL,C_RP0)` admission rule
is historical R54 logic and is not part of the active physics-first freeze.

P0.2 runs the exact effort ladder `[100,60,40,30,25,20] N*m` and exports raw
temporal rows under `a2_piper_base_v23_p0_temporal_records_v1`. Every rung and
each topology (`canonical16`, `heavy16`) must contain exactly 16 evaluable
episodes (32/rung). A row is evaluable only when the lexicographically first
failure-free consecutive 25-control-step window lies wholly in stage 3 or 4
and has stable grasp for at least 20 steps. Missing, duplicate, non-finite, or
non-window evidence is `PENDING`; it cannot imply collapse or selection.
The pre-registered heavy20 source ordering `(4,0,1)` is preserved as source
metadata and is not re-sorted by the reducer.

The producer path is a genuine simulator hook: `LeggedRobotBase` invokes
`_post_physics_substep(sim_sub_t)` immediately after each high-level
`simulate_at_each_physics_step()` return. Door temporal rows collect exactly
one GPU-local frame per real substep (nominal/clipped/limit, actual velocity and
limit, target and target increment), then append exactly one control row at the
end of Door `_check_termination` with the current failure flags and
`control_step=episode_length_buf-1`; missing/duplicate frames fail fast. The
canonical combiner consumes exactly twelve explicitly named raw paths (six
rungs × canonical16/heavy16), validates immutable env/provenance identity, and
only then feeds the temporal reducer. Aggregate terminal maxima remain pending
and cannot substitute for the raw combiner.

For a selected window, `p_i = hinge_angle[end] - hinge_angle[start]` and
`P_ref/P_heavy = median(16)`. Response and loss are normalized against the
corresponding effort-100 median (`response_norm=P/P100`, `loss_norm=1-response_norm`).
The reference is non-collapsed iff `P_ref >= 0.02 rad`. At each physics frame
and selected arm joint, saturation is exactly
`abs(nominal_torque)>effort_limit AND abs(clipped_torque)/effort_limit>=0.90`;
episode saturation is the fraction of physics frames with any saturated
selected joint, and `S_ref=median(16)` is meaningful iff `S_ref>=0.30`.
Harder-first is
`D(r)=[P_heavy(100)-P_heavy(r)]-[P_ref(100)-P_ref(r)]`; it passes iff
`D(r)>=0.02 rad`.

The obvious-PD predicate is per joint/window: velocity sign reversals `>=4`
(two cycles), each non-zero lobe peak `>=10%` of its velocity limit, clipped
torque lobes alternate sign at `>=0.90` effort limit, and target increments
reverse `<=1`; zeros are ignored for sign lobes. Missing/non-finite values
invalidate the window. A normal eligible rung is complete32, `P_ref>=0.02`,
0/32 PD windows, `D>=0.02`, and meaningful `S_ref`; scan ascending
`[20,25,30,40,60,100]` with no fallback. The temporary label is exactly
`A0_CANONICAL16_P0_REFERENCE`, never final E0. Candidate promotion requires
P0.4; otherwise emit `A0_NOT_E0_AT_CANDIDATE` and do not recursively change the
rung or freeze a profile.

F2-40 applies only when every rung is complete and non-collapsed, 0/32 PD, and
all `D<0.02`; outcome is
`LADDER_INCONCLUSIVE` at 40 N*m, not a normal selection. F2-100 applies only
when 20..60 are complete with `P_ref<0.02`, `S_ref>=0.30`, 0/32 PD and 100 is
complete with `P_ref>=0.02`, 0/32 PD; outcome is `F2_100_SELECTED` at 100 N*m.
One selected profile, if any, is shared by all eight groups.

## 4. Execution waves and ordering

Owner's latest resource update grants physical GPU0--7. Formal training uses
one cell per independent tmux session, no `CUDA_VISIBLE_DEVICES`, explicit
physical `cuda:N`, distinct ports, and approximately ten-second launch
staggering. Evaluation uses persisted GPU/job plans and at most one live child
per GPU. The active schedule is:

```text
A1 complete: seed0 FULL G1/G3/G5/G7, followed by Route-A A1 and F3
W1: GPU0=G2-s0, GPU1=G4-s0, GPU2=G6-s0, GPU3=G8-s0,
    GPU4=G1-s1, GPU5=G3-s1, GPU6=G5-s1, GPU7=G7-s1
W2 concurrent:
    GPU0--3 = B2 G2/G4/G6/G8 seed1 RP0 training
    GPU4--7 = Route-A A2+B1
W2 closure: Route-A B2 on GPU0--7
Postformal: Route B -> holdout64 -> render -> final analysis/report
```

Formal training is 2500 batches with checkpoints at 250, 500, 750, 1000,
1250, 1500, 1750, 2000, 2250, and 2500.  No evaluation runs on a GPU while a
training process on that GPU is active.

### Route-A selection rule (written before training)

Each checkpoint is evaluated on canonical16.  Select the earliest checkpoint
with the highest `goal_reached` count; break ties by highest supported crossing
count, then lowest unsafe-contact count, then lowest terminal failure count,
then the smallest checkpoint step.  Route-A is a mechanical selection device,
not a statistical claim.  The rule is identical for all four sub-waves and both
seeds.

## 5. P0 nodes

P0 remains preparation and calibration only.  The original R1 skeleton wording
is superseded by the typed R55/R56 interim adjudication below: measured records
are listed where they exist, while incomplete or unadjudicated nodes remain
explicitly typed rather than promoted.

| Node | Purpose | Required evidence state |
|---|---|---|
| P0.1 | Extend `computed_torque` and `applied_torque` accumulation with authority labels | `RUNTIME_TYPED / COMPLETE`; R170 FULL exact16 produced 45,776 joined PRE/POST phase frames; computed/applied values are POST estimates derived from PRE state and actual PhysX drive torque remains `UNKNOWN` |
| P0.2 | Effort ladder and shared boundary profile | `F2_CLOSED / MEASURED_FREEZE` at `40.0 N*m`, with `LADDER_INCONCLUSIVE`; one effort profile is frozen for the full matrix |
| P0.3 | Kp/action-scale/clip consistency | `RUNTIME_TYPED / COMPLETE`; R170 exact16 emitted 16 controller identities binding the live action/articulation permutation, FULL load mode, target equation, nominal PD, effort-40 clipped command, and tracking error |
| P0.4 | Door atlas A0–A8 and E-zone provisional labels | `P0_4_D1_PHYSICS_FIRST_FREEZE_ADMITTED`; the canonical R190 receipt freezes normal D1 and D1-lite from measured physics-first brackets and supersedes R54 for admission |
| P0.5 | Feasibility certificate calibration | `THRESHOLDS_FROZEN`; R35 bands are bound into the R190 physics-first receipt with atlas provenance; A8 remains historical `COMPLETED_TYPED_NEGATIVE`, `confirmed_E2=false` |
| P0.6 | Common reward and stationary-rent audit | `RUNTIME_VERIFIED / AUDIT_COMPLETE`; R68 short smoke passed and R72 reduced six stage passes to `COMPLETE` with no missing stage |
| P0.7 | RP0 distribution contract and resume checks | `RUNTIME_VERIFIED`; RP0 64-env × 10-batch plus FULL resume 64-env × 1-batch, global steps `0→10→11` |
| P0.8 | State-bank replay prefixes and forward interventions | `P0_8_PREFORMAL_COMPLETE`; unchanged R78 plumbing plus four real one-env trigger records passed, while the complete intervention suite remains deferred to Route B |
| P0.9 | Four 64-env × 10-batch type smokes | `RUNTIME_VERIFIED / COMPLETE`; R112 WARM_FULL, WARM_RP0, SCRATCH_FULL, and SCRATCH_RP0 each returned runner/child `rc0`, produced a finite step-10 checkpoint, and reduced to the canonical four-type receipt |
| P0.10 | Scratch D0 FULL pilot | `TERMINAL OPERATIONAL NO-GO / SCIENTIFIC INCONCLUSIVE`; Branch A measured-valid-failed at 16 evaluated / 12 stage-2 / 0 stable-grasp, while Branch B is `UNMEASURED_OBSERVABILITY_BLOCKED` and `UNADJUDICATED`; triggered F1 is implemented and its D0 FULL/RP0 64×10 smokes are runtime verified |

### P0.3 evidence tie

Every ladder/atlas row carries the three distinct evidence fields:
`nominal_pd_torque`, `clipped_command_torque`, and `tracking_error`.  A nominal
request is not an applied-force claim; the high-effort certificate uses the
clipped command side only.  R170 additionally binds the live full action to
articulation permutation
`[0,4,9,2,6,11,1,5,10,3,7,12,8,13,14,15,16,17,18,19]`: arm action slots
`[12,13,14,15,16,17]` map to articulation IDs `[8,13,14,15,16,17]`.
PRE snapshots are captured at `PRE_ACTUATOR_COMPUTE`, POST snapshots at
`POST_PHYSICS`, and computed/applied torques are explicitly POST estimates from
the PRE state rather than measured PhysX drive torque.

### P0.4 atlas

```text
A0 current easy
A1 high stiffness
A2 high sustained resistive torque
A3 high breakaway/friction proxy (FRICTION_PROXY)
A4 high damping
A5 high inertia
A6 stiffness + calibrated effort
A7 resistive torque + calibrated effort
A8 compound near-boundary
```

E0/E1/near-E2/confirmed-E2 labels are physics-first and provisional.  Realized
per-episode dynamics telemetry is the analysis stratum; intended buckets are
sampling aids only.  Acute FULL/RP0 contrasts are auxiliary and cannot define
door difficulty on their own.

The external physical diagnostic is a registered A0–A8 producer. Each row
carries the canonical `a2_piper_v23_canonical_geometry_v1` record and an
explicit serialized `geometry_id` built from cell, realized damping/stiffness/
effort/mass, width/height/handle facts, LR/IO signs, and local hinge axis/
anchor. World-origin pose is excluded from this identity. The asset declares
RevoluteJoint axis Z with LR-dependent joint rotation and anchor; the producer
transforms that declaration through the door root pose and never substitutes a
panel-local hardcoded axis. For each sign, probe
`Q=[0,5,10,15,20,25,30,40,60,100] N*m`; before every trial reset
`permanent_wrench_composer`, set the hinge effort target to zero, reset closed,
take one settle capture `q0`, then apply the global wrench for exactly 100
physics frames (`0.5 s` at `dt=0.005`). Raw `q_t`, `q0`, and signed progress
`sign*(q_t-q0)` are retained for both signs; the reducer recomputes the signed
trace and max progress and rejects a stored mismatch. The first magnitude with
`max_progress>=0.02 rad` is the pass. For each cell, conservative
`U=max(first_pass over signs)`, retain every sign tied at `U`, then
`L=max(last_fail among those ties)` and require `L<U`. All-fail, pass-at-zero,
nonmonotone, missing, and ambiguous cases remain typed censored/ambiguous
states. There is no interpolation or fabricated threshold. No low-level USD,
state clone, hidden drive, or silent recovery is allowed.

The opening direction is explicit: `torque_sign=+1`,
`hinge_coordinate=POSITIVE_OPENING`, and basis
`TORQUE_SIGN_TIMES_RESOLVED_HINGE_AXIS; TASK_OPENING_IS_POSITIVE_HINGE_POSITION`.
The positive sign is retained as a typed `UNIDIRECTIONAL_OPENING_BRACKET`;
the measured negative `-1` sign remains raw `RIGHT_CENSORED`. P0.5 freezes the
explicit selected cell `A8` only when its positive upper bracket is the unique
atlas maximum and its first pass is the selected 40 N*m effort. No midpoint or
bilateral relabel is allowed.

The arm binding is floating-base only and exact: body
`arm_body6_to_gripper`, joints `arm_j1..arm_j6`. Read the direct body Jacobian
from `Articulation.root_physx_view.get_jacobians()` (arm columns are articulation
joint ids `+6`) and generalized gravity from
`get_gravity_compensation_forces()[:, arm_joint_ids]` (DOF-only, no `+6`). For
body-origin offset `r_bh=x_h-b`, `Jv_h=Jv_b-skew(r_bh)@Jw`. Project the
hinge-to-handle vector to the plane normal to the resolved axis,
`d_perp=(x_h-h)-a*dot(a,x_h-h)`, set `rho=norm(d_perp)`, and normalize
`tangent=normalize(a x d_perp)`. Zero/nonfinite axis, projected radius, or
sample is invalid. For each joint `d_i=tangent^T Jv_h[:,i]`, gravity `g_i`,
limit `l_i`:

```text
d>0: lower=(-l-g)/d, upper=(l-g)/d
d<0: lower=(l-g)/d, upper=(-l-g)/d
d=0: require abs(g)<=l (valid joint is unbounded), otherwise infeasible
```

Intersect all intervals with `f>=0`; valid iff finite `upper>=lower`, and keep
valid zero capacity. Zero-coefficient joints are typed unbounded when
`abs(g)<=l`, otherwise infeasible. `F_plus=upper`, `C=F_plus*rho` with
canonical output names `lower_nm`, `upper_nm`, `capacities_nm` and recorded
units. Episode/mode capacity is the minimum over the approved deterministic
stable geometry window. The authority is
`ESTIMATE_ONLY_GEOMETRY_CONDITIONED_NOT_PHYSX_FORCE_TRUTH`; only FULL/ACUTE
stable A0 windows enter binding, and rollout success is not a classifier.
With finite valid bracket `L<U`: `E0 iff C_RP0>=U`; `E1 iff
C_RP0<U<=C_FULL`; `nearE2 iff L<C_best<U`; `E2_CANDIDATE_UNCONFIRMED iff
C_best<=L`; otherwise `INCONCLUSIVE`. `confirmed_E2=false`; missing or
invalid capability is never assigned a zone.

### P0.5 certificate

An E2 candidate must satisfy all five conditions after P0 calibration:

1. stable grasp for at least 20 control steps;
2. low hinge progress below the calibrated `0.02–0.04 rad` per `25–40` step
   window in both FULL and RP0;
3. clipped-command effort ratio at least `0.90` for at least 30% of the window;
4. failure exclusion: not fall, lost grasp, door-frame collision, or
   timeout-at-wrong-stage;
5. the same forward prefix gains at least `0.10–0.15 rad/window` under a
   higher-effort or oracle tangential rescue.

The initial R1 certificate state was `NOT_RUN/PENDING`.  The measured A8
certificate is now terminal `COMPLETED_TYPED_NEGATIVE`; the independent D1 source
branch is not a certificate and remains incomplete.  Neither branch confirms E2.

FULL and ACUTE_RP0 raw step rows carry JSON-safe registered capability samples
with canonical geometry/`geometry_id`, normalized realized parameters,
`checkpoint_load_mode=policy_only`, immutable mode/scenario/env/episode/control
identity, status, and raw binding values. P0.5 launch overrides the selected
atlas cell's hinge damping, stiffness, effort limit, and door-panel mass through
IsaacLab high-level articulation writers and records readback geometry receipts;
the plain16 selector does not silently replace those dynamics. The
`capability_binding.py select-cell` command freezes the explicit A8
selected-cell artifact from measured atlas/external/effort inputs with
`zone_state=PENDING_CAPABILITY` and `confirmed_E2=false`; that A8 artifact and
the existing A8 certificate path remain unchanged. The separate D1
`reduce` command additionally requires `--capability-source-freeze` and
consumes exact16 A0 FULL/ACUTE capability-source records. It consumes the
directional opening brackets, validates exact local hinge/handle/right-out/
axis/anchor equality across A0–A8, and emits `a2_piper_v23_d1_freeze_v2` with
`capacity_source_cell_id=A0` and
`capacity_transfer_basis=EXACT_SHARED_CANONICAL_LOCAL_KINEMATIC_FACTS`;
target rows retain their own external geometry identity. Its normal D1 and
D1-lite schedules are fixed; F2-100 computes `S`, `U*`, and every tied max-U
cell for uniform sampling. Empty `S` emits `NO_D1` with H4
`DOOR_MODEL_INSUFFICIENT` and never invents a D1 boundary. `confirmed_E2` is
always false.

`p0_rescue_probe.py` PLAN/RUN consumes the required selected-cell freeze and
measured external threshold path, derives A8 from that freeze, and binds FULL,
ACUTE_RP0, and HIGHER_EFFORT_RESCUE to the same selected geometry. There is no
free `--cell-id` override or legacy geometry fallback.

### P0.8 intervention contract

The five forward-only modes are `FULL`, `ACUTE_RP0`, `BASE0_AT_GRASP`,
`HIGHER_EFFORT_RESCUE`, and `ORACLE_TANGENTIAL_ASSIST`.  Common random numbers
reuse the same episode seed and replay prefix, switching at episode start,
stable-grasp latch, or typed failure latch as declared by the mode.  Exact
PhysX state clone is not implemented; missing prefixes remain typed errors.
Intervention suites run only on selected Route-B checkpoints.

R78 implements and runtime-verifies only the bounded A0/D0 source-plumbing
portion.  One fresh GPU0 warm/FULL/D0 evaluator process completed the normal 16
first episodes, captured one contiguous pre-step replay prefix for each of
stages `2/3/4`, and reduced them to 3 state-bank entries and 15 typed bindings
(`3 stages × 5 modes`).  Only `FULL` is the captured source rollout; the other
four modes remain `STATIC_BOUND_RUNTIME_PENDING` and were not executed.  The
canonical `a2_piper_v23_p08_partial_a0_d0_receipt_v1` receipt is
`logs_eval/base_v23/p0/state_bank/state_bank_plan.json`, with
`PARTIAL_A0_D0_PLUMBING_RUNTIME_VERIFIED`, `p08_overall_status=PARTIAL_INCOMPLETE`,
and `p09_d0_smoke_admission=true`.  It explicitly keeps clone, recurrent-state
restore, formal admission, and release false.

## 6. Common reward freeze

The v23 common registry retains the existing base dense registry and v22 G1
task-flow overrides.  It removes
`penalty_a2_v22_excess_posture`, `a2_v22_posture_feasibility`, and
`penalty_a2_v22_posture_saturation`; it keeps
`a2_v22_clearance_success`, `a2_v22_controlled_fling`, and
`penalty_a2_v22_unsafe_release`.  `penalty_a2_posture_command_l1` remains
exactly `0.0`.

The concrete P0.6 launch config is
`gr00t/rl/config/ablation/wbmanip/base_v23_p06_warm_full_d0_smoke.yaml`.
R68 verified its effective warm step1250, policy-only, FULL/D0 composition in a
16-env GPU0 short smoke.  R72 ran six fresh sequential GPU0 evaluator processes,
one for each target stage `0..5`, with exact zero 12-D applied high-level action
at capture and normal 16-episode finalization.  Pass record counts were
`16/16/16/16/16/13`; every captured row contains 58 finite raw and 58 finite
scaled same-name terms with project semantics `scaled = raw * configured scale`
and no manager `dt` factor.  The canonical receipt
`logs_eval/base_v23/p0/reward/stationary_rent_audit.json` is
`a2_piper_v23_stationary_rent_audit_v1 / COMPLETE` with
`missing_stages=[]`.  This completes the bounded P0.6 audit contract but does
not claim policy quality or long-horizon stationary behavior.

## 7. Configuration freeze boundary

Only `base_v23_common.yaml` is materialized in R1.  It is intentionally
non-launchable and requires the P0 effort, D1, certificate, reward, and state
bank records before a formal cell can be derived.  No G1–G8 formal config is
created until those values are frozen.  Missing freeze inputs are a hard error;
there is no silent numeric default.

The common config records:

```text
algo.config.rp0_enabled: false
algo.config.rp0_mask_indices: [3, 4]
algo.config.rp0_neutral_value: 0.0
```

## 8. Artifact roots and plain-record contract

```text
logs_eval/base_v23/p0/
logs_eval/base_v23/p0/torque/effort_<rung>/{canonical16,heavy16}/
logs_eval/base_v23/p0/a2_v23_p0_temporal_records.json
logs_eval/base_v23/p0/door_external_torque_threshold.json
logs_eval/base_v23/p0/capability_binding/
logs_eval/base_v23/p0/reward/stationary_rent_audit.json
logs_eval/base_v23/p0/reward/stationary_rent_passes/
logs_eval/base_v23/route_a/seed0/
logs_eval/base_v23/route_a/seed1/
logs_eval/base_v23/pooled48/
logs_eval/base_v23/stratified/
logs_eval/base_v23/interventions/
logs_eval/base_v23/holdout64/
logs_eval/base_v23/render/
logs_eval/base_v23/final_analysis/
logs_rl/a2_piper_full_stage_a2_base/base_v23/
logs_rl/launchers/base_v23/
```

P0 tooling emits simple JSON/Markdown records with `status`, source paths, git
commit, measured fields, and typed pending states.  It does not emit content
digests, synthetic PASS results, or hidden controller decisions.

Runtime ownership is explicit: P0.2/P0.4 producers own only the above P0 roots;
the trainer preserves raw episode rows, while `effort_ladder.py` is the sole
CPU reducer. Historical P0 producers used their recorded GPU leases. The
current formal/postformal schedule owns physical GPU0--7 as specified in
section 4, with one formal cell or one eval child per GPU and distinct formal
ports. Formal launch waits only for the owner-approved physics-first D1,
P0.8 preformal-v2, and D1-FULL plumbing-smoke receipts. Calibration changes are
evidence-only: reward/termination semantics are untouched beyond sampling,
trainer transport preserves raw rows, and all scene geometry uses IsaacLab
high-level APIs (no low-level USD escape hatch).

## 9. Pre-registered contingencies F1–F8

* **F1 scratch pilot NO-GO — TRIGGERED / SMOKE-COMPLETE:** P0.10 preserved Branch A's measured
  failure and Branch B's observability block, and recorded
  `V23_SCRATCH_CURRICULUM_INSUFFICIENT_PILOT`.  The approved head-reset now
  resets only actor output rows 3/4 plus corresponding `std`, and both D0 FULL
  and RP0 64×10 smokes passed.  Do not claim full scratch evidence, policy
  quality, or a Branch-B result.
* **F2 effort ladder inconclusive:** retain `LADDER_INCONCLUSIVE`; use the
  planner-approved bounded profile only after recording the missing boundary
  evidence.  Do not chase extreme door parameters.
* **F3 D1 too hard:** preserve A1; switch later D1 cells to the pre-registered
  D1-lite mixture and label them `D1_PRIME_NOT_REPLICATION`.
* **F4 infrastructure interruption:** before optimizer progress, one identical
  restart is permitted; after progress, preserve checkpoints and do not restart
  the run in place.
* **F5 shared early bug:** stop the sub-wave, repair the bounded implementation,
  rerun the relevant type smoke, and restart the sub-wave from its beginning.
* **F6 RP0 semantic error:** invalidate RP0 results, repair the distribution
  contract, rerun RP0 type smokes, and schedule the permitted replacement wave.
* **F7 schedule overrun:** reduce holdout scope first, then render scope, then
  seed-1 Route-B scope; preserve the complete seed-0 Route-A/Route-B floor.
* **F8 evaluation/render utility error:** repair the v22-adapted utility in
  place; missing evidence receives a typed status and is never filled with zero.

## 10. Stopping condition for R1

R1 now continues under the owner-unblock decision in section 15.  Historical
P0 receipts remain immutable evidence.  The immediate stopping condition is to
produce the new physics-first D1/D1-lite receipt, the P0.8 preformal-v2 receipt,
and one passing D1-FULL 64×10 plumbing smoke.  That exact conjunction admits
formal 8×2 training without another approval gate.

## 11. R51 reduction-closure contract (historical; D1 admission superseded by section 15)

The seven-file reduction closure keeps the measured R46 A8 certificate path
byte-compatible while making the two producer purposes explicit:
`P05_CERTIFICATE` is the A8 certificate path and
`D1_CAPABILITY_SOURCE` is a separate A0 source path.  A certificate producer
may use `FULL`, `ACUTE_RP0`, and `HIGHER_EFFORT_RESCUE`; a D1 producer may use
only `FULL` or `ACUTE_RP0`, has no rescue intervention, and must carry the
exact source artifact `a2_piper_v23_capability_source_freeze_v1` with
`source_cell_id=A0`, `selected_effort_nm=40.0`,
`selection_basis=CURRENT_EASY_A0_STABLE_REFERENCE`, and the registered A0
requested and native parameter maps.  The freeze retains exact `atlas`,
`external_threshold`, and `effort_freeze` source paths plus measured external
threshold provenance.  Its bound plain16 selector is
`a2_piper_base_v23_d1_capability_bound_plain16_manifest_v1` with selector
`v23_d1_capability_source_plain16`; scene and consumer dispatch are exact by
schema/purpose and still use IsaacLab high-level articulation replacement.

The producer pair schema is
`a2_piper_v23_p05_pair_export_v3` and the bundle schema is
`a2_piper_v23_p05_producer_bundle_v3`.  FULL/rescue prefix comparison projects
only typed intervention-latch fields (including nested identity mode); all
physical evidence remains direct equality.  A rescue export with
`switch_step=-1`, `rescue_status=NOT_REQUESTED`, request profile
`{"status":"NOT_REQUESTED"}`, applied profile
`{"status":"NOT_EXECUTED"}`, and no switched rows is a typed
`NO_RESCUE_LATCH` / `NONQUALIFYING` pair with no prefix, not a pass or a
synthetic intervention.  Switched rows require the exact pre/post latch
transition and a direct equal prefix.  Certificate terminal statuses are
`PASS`, `COMPLETED_TYPED_NEGATIVE`, and `RESCUE_NOT_EXECUTED`; a certificate
is terminal only when every group is terminal, and no-latch groups remain
nonqualifying.

The D1 reducer consumes exact16 A0 `FULL` and exact16 A0 `ACUTE_RP0` records.
For each record it takes the lexicographically first failure-free stable
25-control-step window and the minimum valid capacity in that window; the
FULL minimum is primary and ACUTE is auxiliary only.  ACUTE never promotes a
zone.  With a measured directional bracket `L<U`, the fixed hierarchy is
`FULL>=U and ACUTE>=U -> E0`, `FULL>=U and ACUTE<U -> E1`,
`L<FULL<U -> nearE2`, and `FULL<=L -> E2_CANDIDATE_UNCONFIRMED`;
`confirmed_E2` remains false.  Normal and D1-lite schedules remain
`100/0/0 -> 60/40/0 -> 30/60/10` and
`100/0/0 -> 65/35/0 -> 40/55/5` (E0/E1/nearE2), respectively.  Empty valid
sets remain typed `NO_D1`/H4; no cell, threshold, prefix, or rescue fallback
is inferred.

## 12. R55 adjudication and bounded continuation (historical; superseded by section 15)

This section preserves the R54/R55 historical adjudication.  Its symmetric
FULL/ACUTE completeness gate is not an active admission rule after the owner
decision; none of its receipts are modified or relabeled.

### 12.1 Evidence and typed result

| Evidence | Typed result | Boundary |
|---|---|---|
| `logs_eval/base_v23/p0/r33_p02_effort_freeze_20260809/effort_freeze.json` | `MEASURED_FREEZE`; selected effort `40.0 N*m`; `LADDER_INCONCLUSIVE`; exact 12 runs / 192 records | The bound profile is recorded, but the ladder does not constitute a normal effort selection |
| `logs_eval/base_v23/p0/r26_p02_p04_p05_runtime_20260809/p04/door_atlas_raw.json` and `door_external_torque_threshold.json` | `MEASURED_RAW`; positive brackets A0/A1 `(10,15]`, A2/A3/A7 `(25,30]`, A4/A5/A6 `(15,20]`, A8 `(30,40]`; negative sign `RIGHT_CENSORED` | Brackets are raw/typed; D1 zones and the training mixture are `NOT_FROZEN` |
| `logs_eval/base_v23/p0/r49_p05_reduction_20260809/feasibility_certificate.json` plus the R49 pair/bundle | `COMPLETED_TYPED_NEGATIVE`; pass0; 15 typed-negative records; env5 `RESCUE_NOT_EXECUTED`; `confirmed_E2=false` | This is the A8 P0.5 certificate path, not the D1 source path |
| `logs_eval/base_v23/p0/a2_piper_v23_p07_rp0_contract_r21.json` | `RUNTIME_VERIFIED`; real RP0 64-env × 10-batch and FULL resume 64-env × 1-batch; `0→10→11`; raw dimensions 3/4 neutral at zero in the RP0 contract | This contract does not prove R54 P05 source raw dimensions directly |
| `logs_eval/base_v23/p0/r54_p05_d1_source_runtime_20260810/runs/{full,acute_rp0}/a2_v23_p05_episode_records.json` | R54 runtime `rc0`, exact16 finite records per mode; FULL valid windows 15/16 (env5 absent), ACUTE valid only env12 | The records are D1 capability-source inputs, not a D1 freeze |
| `logs_eval/base_v23/p0/r54_p05_d1_reduction_20260810/d1_capability_source_incomplete.json` | reducer `rc2`; `D1_CAPABILITY_SOURCE_INCOMPLETE`; reasons `NO_STABLE_FAILURE_FREE_25_STEP_WINDOW`; `d1_freeze_written=false` | No zones, capacity mixture, normal schedule, D1-lite schedule, or formal admission is emitted |

The A8 certificate and D1 source are intentionally separate producer purposes.
The former is terminal typed-negative; the latter has exact16 runtime inputs but
fails its stable-window reduction contract.  A certificate `PASS` is not implied,
and `confirmed_E2` remains false.

### 12.2 R53 → R54 debug provenance

R53 FULL and ACUTE both reached 16-environment IsaacSim initialization, then
failed in `DoorPregrasp` because the required integer
`env.config.a2_v23_p05_seed` was absent from the resolved config.  R54 supplied
the exact seed override and produced finite exact16 FULL and ACUTE source records
(`rc0`) at the canonical paths above.  The remaining R54 failure is scientific
window coverage, not a silent runtime recovery: FULL has no valid window for
env5, ACUTE has only env12, and the canonical reducer therefore exits `rc2`.

Direct proof of the R54 source raw dimensions 3/4 is **INCONCLUSIVE**.  Do not
infer it from the RP0 mask contract, neutral statistics, or configuration shape.

### 12.3 Formal gate and bounded DAG

This historical gate was superseded by section 15.  The old DAG is retained as
provenance only:

```text
[R78 COMPLETE] partial P0.8 A0/D0 state-bank/plumbing work
  -> [R112 COMPLETE] D0 P0.9 four-type 64-env × 10-batch smokes
  -> [TERMINAL NO-GO] D0 P0.10 FULL pilot
  -> [R182 COMPLETE] F1 head-reset implementation and two D0 type smokes
  -> [NEXT] resolve P0.4 D1 and overall P0.8, or preserve typed NO-GO
```

Do not use this historical paragraph to block the owner-approved revised P0
path.  It remains valid only as a description of what R54/R78 themselves did
and did not prove.

## 13. R170/R173 P0.1/P0.3 closure and P0.10 terminal adjudication (2026-08-10 HKT)

R170 ran one fresh GPU1/logical-`cuda:0` G1 step-1250 FULL exact16 evaluator
under the 40 N*m boundary profile.  The producer exited naturally with `rc0`
and emitted 16 terminal records, 16 temporal episodes, 45,776 joined phase
frames, and 16 controller identities.  Three earlier utility failures remain
typed F8 provenance: R161 failed before App launch due Hydra override syntax,
R164 failed the action/articulation identity assumption, and R169 selected an
inactive diagnostic reward term.  They were neither overwritten nor promoted.
The sole CPU R173 reduction returned `rc0` with
`P0_1_P0_3_RUNTIME_TYPED_ADJUDICATION` at
`logs_eval/base_v23/p0/r170_p01_p03_runtime_20260810/p01_p03_typed_adjudication.json`.
Legacy R31/R33 evidence remains insufficient and is not upgraded.  Actual
PhysX drive torque, D1, formal admission, and release remain unproved.

The sole CPU P0.10 terminal adjudication records
`P0_10_SCRATCH_ADMISSION_NO_GO_BRANCH_A_FAILED_BRANCH_B_OBSERVABILITY_BLOCKED`
at `logs_eval/base_v23/p0/p010_scratch_full_d0_terminal_adjudication.json`.
Branch A is a measured-valid failure: 16 evaluated, 12 reached stage 2, and 0
met the stable-grasp criterion.  Branch B is
`UNMEASURED_OBSERVABILITY_BLOCKED` with policy outcome `UNADJUDICATED`: the
preserved checkpoint does not contain `staged_reset_buf` or
`staged_reset_num_samples`, and canonical16 produced no stage-3-or-later birth
source.  Therefore the operational scratch-admission result is NO-GO, the
scientific result is `P0_10_SCIENTIFIC_INCONCLUSIVE_BRANCH_B_UNMEASURED`, and
F1 is triggered.  Section 14 records the subsequent bounded implementation and
runtime-smoke closure; it does not change the Branch-B scientific result.

## 14. R177–R182 F1 head-reset closure (2026-08-10 HKT)

F1 implements a strict `warm_head_reset` path immediately after the existing
strict `policy_only` actor load.  It reinitializes only
`actor_module.module.6.weight[3:5]`, the matching bias rows, and `std[3:5]`
(`0.8`) using a local device generator seeded from the run seed.  All other
actor/LSTM/RMS tensors remain inherited; critic, optimizer, scheduler, trainer,
and environment state remain fresh.  Future G3/G4/G7/G8 use
`warm_head_reset`, while G1/G2/G5/G6 remain `v22_warm`; G7/G8 are not admitted
while D1 is blocked.

R180 and R181 each ran exactly once at `64 env × 10 batch` with no retry.
HR-FULL-D0 used physical GPU0/logical `cuda:0`; HR-RP0-D0 used physical
GPU1/logical `cuda:0`.  Both child processes returned naturally with `rc0`,
preserved the exact resolved config, and produced finite step-10 checkpoints.
The sole CPU R182 reducer returned `rc0` and wrote
`logs_eval/base_v23/p0/p010_f1_head_reset_d0_type_smoke_receipt.json` with
schema `a2_piper_v23_f1_head_reset_d0_receipt_v1` and status
`P0_10_F1_D0_HEAD_RESET_TWO_TYPE_SMOKES_RUNTIME_VERIFIED`.  This closes only
the F1 implementation/smoke node.  It does not measure Branch B, establish
policy quality, complete P0.8, admit D1/formal work, or support release/goal
success.

## 15. Owner-unblock decision and active continuation (2026-08-10 HKT)

The effective decision is
`scriptsFORhuman/v23/DoorDog_v23_owner_decision_p0_unblock_20260810.md`.
It selects the combined option 2+3, rejects the former terminal NO-GO and a
D0-only continuation, and supersedes only the admission semantics identified
below.  Historical R54 and R78 inputs and receipts remain immutable.

### 15.1 Physics-first D1 and D1-lite freeze

F2 closes P0.2 at one matrix-wide effort boundary of `40.0 N*m`.  The D1
classifier consumes the scripted free-return/fixed-torque atlas brackets and
uses their measured positive-direction upper endpoint `U` without interpolation
or policy-derived promotion:

| Zone | Active normal-D1 cells | Measured rule |
|---|---|---|
| E0 | A0, A1 | `U <= 15 N*m` |
| E1 | A4, A5, A6, A2, A3, A7 | `15 < U <= 30 N*m` |
| near-E2 | A8 | measured `(30,40] N*m`, reaching the effort40 boundary |
| confirmed E2 | none | remains evaluation-only and unconfirmed |

D1-lite keeps E0 unchanged, narrows E1 to A4/A5/A6 (`15 < U <= 20 N*m`),
keeps A8 as near-E2, and uses
`100/0/0 -> 65/35/0 -> 40/55/5`.  Normal D1 uses
`100/0/0 -> 60/40/0 -> 30/60/10`.  This is the minimum F-plan adjudication
that preserves every measured tier boundary, introduces no unmeasured tie-break
or capacity estimate, and implements the owner's narrower-E1/halved-near-E2
D1-lite instruction.  The labels are provisional; HR-RP0 cells re-adjudicate
them after training.

The new receipt is
`logs_eval/base_v23/p0/p04_d1_physics_first_20260810/p04_d1_physics_first.json`
with schema `a2_piper_v23_p04_d1_physics_first_v1`.  It records the effort40
comparison, normal and lite zones/schedules, `confirmed_E2=false`, the R35
P0.5 bands, and atlas provenance including the measured `0.02 rad`
opening-pass threshold.  Policy probes are auxiliary only: FULL with at least
12/16 valid windows is archived, ACUTE is typed
`ACUTE_WINDOWS_SPARSE_EXPECTED`, and the known env5 gap is non-blocking.  No
fresh raw-action dimensions 3/4 telemetry is required for this freeze.

### 15.2 P0.8 preformal-v2 gate

R78 already satisfies the state-bank plumbing requirement: stages 2/3/4, three
entries, and 15 static bindings.  A new default-off `a2_v23_p08_v2_*` path must
execute exactly one 1--2-environment trigger verification for each non-FULL
mode: `ACUTE_RP0`, `BASE0_AT_GRASP`, `HIGHER_EFFORT_RESCUE`, and
`ORACLE_TANGENTIAL_ASSIST`.  Each record must identify the observed switch/latch,
pre/post action transformation, and, for rescue, the high-level six-joint
effort-limit request/readback.  These short runs prove only connection,
switching, and record marking; they do not claim causal effect, policy quality,
state cloning, or recurrent-state restoration.

The reducer writes
`logs_eval/base_v23/p0/interventions/preformal_v2/p08_preformal_v2_receipt.json`
with schema `a2_piper_v23_p08_preformal_v2_receipt_v1` and status
`P0_8_PREFORMAL_COMPLETE` iff unchanged R78 plumbing is present and exactly one
valid triggered record exists for all four modes.  The complete four-mode
runtime suite remains deferred to Route B on selected checkpoints.

The canonical receipt is now complete.  The bounded runtime evidence is:
ACUTE switched at episode start step `0`; BASE0 observed the real stable-grasp
high-water latch at step `180` and switched at `181`; higher-effort rescue and
oracle assist observed the frozen typed-failure latch at step `530` and switched
at `531`.  Rescue proves only a configured six-joint solver-limit request and
readback.  The receipt keeps `formal_admission=false`, `release_receipt=false`,
and makes no causal, policy-quality, exact-clone, recurrent-restore, or actual
PhysX torque claim.

### 15.3 Formal admission, resources, and source discipline

Formal 8x2 admission is the conjunction of:

1. the physics-first D1/D1-lite receipt;
2. the `P0_8_PREFORMAL_COMPLETE` receipt; and
3. one passing D1-FULL `64 env x 10 batch` bucket-plumbing smoke.

That conjunction is complete.  R228 was the preserved fail-fast attempt that
stopped before optimizer initialization because the D1 root config did not
carry the exact measured v22 contact-table input.  After that source contract
was fixed, R233 completed the fresh GPU0 training run naturally and produced a
finite step-10 checkpoint.  R238 reduced the immutable R233 raw record to
`logs_eval/base_v23/p0/d1_full_64x10/d1_full_64x10_receipt.json`, schema
`a2_piper_v23_d1_full_64x10_receipt_v1`, status
`D1_FULL_64X10_BUCKET_PLUMBING_RUNTIME_VERIFIED`.  This is a bucket-plumbing
and short-training pass only; it does not claim policy quality or release.

The CPU-only canonical reducer
`scriptsFORhuman/v23/formal_admission.py` binds those three receipts to the
`READY_TO_ADMIT` GPU0/1 formal plan and writes
`logs_eval/base_v23/locks/V23_FORMAL_ADMISSION_PASS.json`, schema
`a2_piper_v23_formal_admission_v1`, status `V23_FORMAL_ADMISSION_PASS`, scope
`START_FORMAL_TRAINING_ONLY`.  Its `formal_admission=true` means only that the
frozen matrix may start; `formal_training_completed`, `policy_quality_claim`,
and `release_receipt` remain false.

All four A1 cells have natural `rc0` completion at global step 2500 and bind
their exact `model_step_002500.pt` checkpoints. Route-A A1 sealed exact 40
rows / 640 canonical16 episodes. Its mechanical selection is G1 step2000, G3
step0250, G5 step0500, and G7 step1500. The append-only F3 endpoint receipt is
`F3_NOT_TRIGGERED`: both G5 and G7 step2500 traces contain stage3 observations
for all 16 env IDs. Later seed1 D1 therefore remains `normal`.

No other reducer completeness or symmetry rule may be added. Physical GPU0--7
are available under the W1/W2 schedule in section 4. The long-run wait uses the observed
step-250 checkpoint interval extrapolated by `1.05`, then one long sleep and a
natural-exit/OOM/traceback check.

All new v23 tests, runners, launchers, orchestration, and analysis scripts live
under `scriptsFORhuman/v23/`.  A runtime-imported production module may remain
inside `gr00t` only as a separate v23 module.  Shared source/config changes are
additive and gated by default-off `a2_v23_*` keys; existing `a2_v20_*`,
`a2_v21B_*`, and `a2_v22_*` semantics remain unchanged.  No v23 file is moved,
renamed, or cleaned up mid-round.  Post-v23 source isolation is recorded as
LT-23-12 in `scriptsFORhuman/a2_piper_longterm_TODO.md`.

The active DAG is therefore:

```text
physics-first D1/D1-lite receipt + P0.8 preformal-v2 receipt
  -> D1-FULL 64x10 plumbing smoke
  -> A1 complete + Route-A A1 + F3
  -> W1 eight-cell A2/B1 + W2 B2 concurrent with Route-A A2/B1
  -> Route-A B2
  -> selected Route B full interventions
  -> holdout64 -> render -> final analysis/report
```
