# DoorDog A2+Piper `base_v23` plan R1

**Plan ID:** `base_v23_force_feasibility_initialization_posture_R1`
**Revision:** R1 — 2026-08-09 HKT
**Repository / branch:** `DoorDog-A2_Piper` / `A2_Piper`
**Runtime state:** interim P0 adjudication; P0.6, the bounded partial A0/D0 P0.8 node, and the R112 D0 P0.9 four-type smokes are runtime verified; P0.10 is admitted, the D1 source branch is incomplete, and there is no formal training admission

This is the sole v23 plan document.  It adapts the v22 control/evaluation flow
while keeping v23 identity and source records separate.  A record is identified
by the current git commit together with its readable source or saved-config
paths.  The original R1 preparation tools write plain JSON/Markdown.  The later
P0.6 stationary-rent and P0.8 state-bank tools are separately bounded evaluator
runner/reducers.  The P0.9 runner verifies only four D0 training smokes and
admits P0.10; none of these tools authorizes formal training, formal evaluation,
or rendering.

## 1. Scientific question and fixed matrix

The experiment separates initialization, door regime, and posture availability.
The arm effort profile is one P0-calibrated constant shared by every cell; D0
and D1 may differ only in door parameters.  RP0 is a distribution-level actor
mask on raw action indices 3 and 4 (pitch and roll), with semantic neutral value
`0.0`; it is not a post-sample action clamp.

| Group | Initialization | Train door | Posture | Formal GPU in a sub-wave |
|---|---|---|---|---:|
| G1 | v22 warm | D0 | FULL | 0 |
| G2 | v22 warm | D0 | RP0 | 1 |
| G3 | scratch | D0 | FULL | 2 |
| G4 | scratch | D0 | RP0 | 3 |
| G5 | v22 warm | D1 | FULL | 0 |
| G6 | v22 warm | D1 | RP0 | 1 |
| G7 | scratch | D1 | FULL | 2 |
| G8 | scratch | D1 | RP0 | 3 |

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
confirmed E2 cell is evaluation-only.

| Training interval | E0/current-like | E1 posture-beneficial | near-E2 | confirmed E2 |
|---|---:|---:|---:|---:|
| 0–20% | 100% | 0% | 0% | 0% |
| 20–50% | 60% | 40% | 0% | 0% |
| 50–100% | 30% | 60% | 10% | 0% |

Normal D1 freezes only with a nonempty E0/E1/nearE2 set and schedule
`100/0/0 -> 60/40/0 -> 30/60/10` (E0/E1/nearE2). F2-100 uses D1-lite exactly
`100/0/0 -> 65/35/0 -> 40/55/5`. In either case choose uniformly among all
max-U cells satisfying `U<=min(C_FULL,C_RP0)`; if the set is empty, do not
freeze D1 and emit `NO_D1`/H4. F2-100 pre-marks H4 and its D1-lite zones are
exactly every tied max-U cell `M` (no other valid cell); it does not invent a
tie-break.

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

Physical GPUs 0–3 are the only v23 runtime lease.  Four-cell sub-waves are
serial in the following order; each completed sub-wave is followed immediately
by its Route-A evaluation before the next training sub-wave:

```text
A1: seed 0, G1/G3/G5/G7
Route-A A1
A2: seed 0, G2/G4/G6/G8
Route-A A2
B1: seed 1, G1/G3/G5/G7
Route-A B1
B2: seed 1, G2/G4/G6/G8
Route-A B2
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
| P0.1 | Extend `computed_torque` and `applied_torque` accumulation with authority labels | `NOT_RUN/PENDING`; authority must remain estimate-only where solver force is unavailable |
| P0.2 | Effort ladder and shared boundary profile | `MEASURED_FREEZE` at `40.0 N*m`, with `LADDER_INCONCLUSIVE`; exact 12 runs / 192 records, no normal selection |
| P0.3 | Kp/action-scale/clip consistency | `NOT_RUN/PENDING`; tie nominal PD, clipped command, tracking error |
| P0.4 | Door atlas A0–A8 and E-zone provisional labels | `MEASURED_RAW`; typed brackets exist, but D1 zones/mixture remain `NOT_FROZEN` |
| P0.5 | Feasibility certificate calibration | A8 certificate `COMPLETED_TYPED_NEGATIVE`; separate D1 source/reducer branch remains incomplete and `confirmed_E2=false` |
| P0.6 | Common reward and stationary-rent audit | `RUNTIME_VERIFIED / AUDIT_COMPLETE`; R68 short smoke passed and R72 reduced six stage passes to `COMPLETE` with no missing stage |
| P0.7 | RP0 distribution contract and resume checks | `RUNTIME_VERIFIED`; RP0 64-env × 10-batch plus FULL resume 64-env × 1-batch, global steps `0→10→11` |
| P0.8 | State-bank replay prefixes and forward interventions | `PARTIAL_A0_D0_RUNTIME_VERIFIED / OVERALL_INCOMPLETE`; R78 captured stages 2/3/4 and emitted 15 typed bindings, with no exact state clone or release receipt |
| P0.9 | Four 64-env × 10-batch type smokes | `RUNTIME_VERIFIED / COMPLETE`; R112 WARM_FULL, WARM_RP0, SCRATCH_FULL, and SCRATCH_RP0 each returned runner/child `rc0`, produced a finite step-10 checkpoint, and reduced to the canonical four-type receipt |
| P0.10 | Scratch D0 FULL pilot | `ADMITTED / PENDING`; the R112 P0.9 receipt admits only this bounded next node, with no GO/NO-GO claim yet |

### P0.3 evidence tie

Every ladder/atlas row carries the three distinct evidence fields:
`nominal_pd_torque`, `clipped_command_torque`, and `tracking_error`.  A nominal
request is not an applied-force claim; the high-effort certificate uses the
clipped command side only.

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
CPU reducer. Physical runtime is restricted to GPU0--3; no GPU4--7, no display,
no port lease, and no training process may share a probe GPU. Until temporal,
external, and capability evidence is reduced and the exact D1 freeze is
written, formal training is a formal **NO-GO**. Calibration changes are
evidence-only: reward/termination semantics are untouched beyond sampling,
trainer transport preserves raw rows, and all scene geometry uses IsaacLab
high-level APIs (no low-level USD escape hatch).

## 9. Pre-registered contingencies F1–F8

* **F1 scratch pilot NO-GO:** preserve the evidence, then use the approved
  head-reset interpretation for scratch cells uniformly; record the typed
  curriculum-insufficient result.  Do not claim full scratch evidence.
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

The R1 implementation stopped after the plan, source reader, P0.2/P0.3/P0.4/P0.5
and P0.8 pure-data skeletons, reward registry, and non-launchable common config
were statically parseable.  The later R49/R54/R68/R72 records are evidence-only
interim calibration adjudication: P0.2, P0.4, the A8 P0.5 certificate, P0.6,
P0.7, the bounded partial A0/D0 P0.8 node, and the R112 D0 P0.9 four-type
smokes have typed evidence; the D1 source, overall P0.8, and P0.10 remain
incomplete.  Formal
training, formal evaluation, rendering, and final G1–G8 configs remain
`NOT_RUN/PENDING`, and the formal training gate remains **NO-GO**.

## 11. R51 reduction-closure contract (effective schema update)

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

## 12. R55 adjudication and bounded continuation (interim; 2026-08-10 HKT; synced R56)

This section is the current answer-first adjudication of the measured P0
records.  It does not change the fixed thresholds, schedules, or F1–F8
contingencies above.

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

Formal training is a hard **NO-GO** until the D1 source/window contract is
reduced and the exact D1 freeze is written.  The only allowed continuation is the
bounded D0 preparation DAG:

```text
[R78 COMPLETE] partial P0.8 A0/D0 state-bank/plumbing work
  -> [R112 COMPLETE] D0 P0.9 four-type 64-env × 10-batch smokes
  -> [NEXT/ADMITTED] D0 P0.10 FULL pilot
  -> adjudicate the resulting evidence
```

The following remain forbidden in this interim state: formal 8×2 training,
F3/D1-lite execution, any D1 freeze or D1-mixture claim, H1–H5 claims, final
goal/release claims, and any claim that the R54 raw dimensions were directly
proved.  P0.4 remains raw/typed, P0.5 D1 remains incomplete, and P0.8 remains
overall incomplete despite its bounded R78 receipt.  P0.9 is complete only for
the R112 D0 smoke contract; P0.10 remains incomplete until its own receipt
exists.
