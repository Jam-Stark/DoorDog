# A2+PiPER `base_v26-4 R2` bilateral grasp foundation execution closure

Closed: 2026-08-29 06:50 HKT  
Source lineage: local `A2_Piper` HEAD
`e6310042348d24fbe8bb8bdc6ecd70e226fc3e32`; pre-existing dirty v26-3/R1
worktree preserved. No reset, stash, discard, commit, push, pull-branch merge, hardware
operation, or external write was performed.

## 1. Outcome first

R2 completed the corrected kinematics gate, canonical representation seam, four-cell
training matrix, bilateral natural evaluation, and preregistered reducer:

```text
FK     FK_MIRROR_IDENTITY_PASS                         RUNTIME PASS
K      BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET           RUNTIME PASS / ADMITTED
AUDIT  SIDE_INDEPENDENT_ORIENTATION_REFERENCE_FOUND_AT_
       piper_gripper_handle_frame_transformer_target_offsets
                                                        STATIC PASS
C      CANONICAL_IDENTITY_PROOF_PASS                    CPU STATIC PASS
M      CANONICALIZATION_NOT_SUPPORTED                   EXPERIMENT COMPLETE
```

R1 remains an honest historical closure, but its
`BILATERAL_ASYMMETRIC_AT_arm_j4` geometry claim was produced by a defective
side-independent world target orientation. R2's geometry-derived target and actual
articulation FK evidence supersede that claim as current project truth. R1 artifacts,
closure, and typed outcome were not deleted, overwritten, or rewritten.

The experiment does not support the canonical representation as a bilateral grasp
foundation under the frozen §7 criteria. It does not admit a push/pull shared Teacher,
Student G7 binding update, hardware claim, reward change, or actuator/physics change.

## 2. Corrected Wave K

The probe first proved the sagittal FK identity on 14 actual-articulation samples,
including the nine R1 LEFT solutions. Door-local position and quaternion-component
residual maxima were `6.5267e-6 m` and `9.6560e-6`, within the frozen `1e-5`
component tolerance. Quaternion comparison used the same predicted `wxyz` value and
only its `q == -q` double-cover equivalent.

The target pose was then derived from the actual grasp target, panel transform, handle
joint `LocalPos0`/`LocalRot0`, and handle axis. LEFT/RIGHT target position and
orientation satisfied the same mirror relation with recorded component error `0`.
The old side-independent target quaternion was not used.

Only after both gates passed did the probe run the frozen nine-pair Stage3 grid. All
nine LEFT and all nine RIGHT candidates were reachable. The unique registered
selection was `stage3_x_-0.800_abs_y_0.180`; its per-side position residuals were at
most `2.41e-7 m`, orientation residuals at most `5.29e-7 rad`, and minimum hard-limit
margins approximately `0.80067/0.80065 rad`. The margin gap was below the `0.15 rad`
joint-asymmetry threshold, while the side-relative action-origin travel difference was
`1.320776 rad`, above the frozen `0.25 rad` threshold. The typed result was therefore
`BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET`, not a joint hard-limit asymmetry.

Formal artifacts:

- `logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/K/fk_mirror_identity.json`
- `logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/K/k_kinematics.json`

Attempt5 wrote both scientific artifacts before cleanup. The IsaacSim Python process
then lingered in `app.close()` and was interrupted with task-owned `SIGINT`; no PID or
GPU context remained afterward. The supervisor receipt therefore remains `RUNNING`
and must not be described as a clean application exit. Reviewer acceptance is bound to
the complete artifact content and post-run process/GPU audit, not a fabricated receipt
state. Attempts 1–4 remain excluded diagnostics and contribute no typed result.

Evidence boundary: runtime kinematics for the frozen grid and target contract only;
this is not policy, whole-workspace, hardware, or grasp-success evidence.

## 3. Orientation audit and Wave C

The independent source/config/consumer audit found that the active A2
`piper_gripper_handle_frame_transformer` uses the same
`(0.5,0.5,0.5,0.5)` handle/pregrasp target offset on both sides. Its
`target_quat_source` feeds the gripper orientation reward, Stage1 readiness, Stage2
close gate, and actor `gripper_handle_transform`. R2 records this as a v26-5 input and
does not silently modify the training orientation reference.

Audit artifact:
`logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/AUDIT/training_orientation_reference_audit.json`.

Because K routed to §6.1, Wave C implemented the single seam
`env.config.a2_v26_4_side_canonicalization_enabled`. Production and proof share the
same pure mapping helpers. On RIGHT, actor increments are mapped before the
authoritative physical delta accumulator; accumulation and clipping remain in physical
coordinates, Stage0 only resets its own rows to the side-specific physical origin, and
canonical echo/RMS state is restored afterward. The OFF path remains the direct old
path.

The proof binds the actual 133D actor ordering, checks continuous equality modulo the
preserved side one-hot, and executes the real physical accumulation/clip and Stage0/
Stage1 composition. It emitted `CANONICAL_IDENTITY_PROOF_PASS`. A separate C1 runtime
smoke completed `64 env / 4096 timesteps / 1 PPO batch` in `15.85 s` and wrote
`model_step_000001.pt` with a PASS receipt.

Artifacts:

- `logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/C/canonical_identity_proof.json`
- `logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/C/c_route.json`
- `.ai/runtime/runs/v26_4_r2_c1_smoke/RUN_RECEIPT.json`

The identity proof is CPU STATIC evidence and the smoke is runtime-path evidence;
neither is the final causal experiment conclusion.

## 4. Formal training and bilateral evaluation

The exact K/C gate, resolved four-cell matrix, command registry, and source metadata
passed before GPU launch. Formal training used only GPU0–3:

```text
GPU0  C0_CANONICAL_OFF_S0
GPU1  C0_CANONICAL_OFF_S1
GPU2  C1_CANONICAL_ON_S0
GPU3  C1_CANONICAL_ON_S1
```

Each cell ran 4096 environments for 750 PPO batches with checkpoints at
125/250/375/500/625/750, policy-only load plus inherited actor RMS, and the unchanged
v26-3 M1 reward contract. All four train receipts are `PASS`, return code `0`, and all
four step750 checkpoints exist.

Evaluation covered checkpoints 125/250/500/750, LEFT and RIGHT separately, with exact64
natural first episodes per side. All four eval receipts are `PASS`, return code `0`.
The result is 32 side directories and 2048 first episodes in total; every required
metrics, per-env record, trace, and metadata artifact is present. GPU4–7 were never
leased or launched by R2.

Canonical roots:

- training: `logs_rl/by_batch/base_v26_4_r2_bilateral_grasp_foundation_20260828/main/`
- evaluation: `logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/eval/`

## 5. Frozen §7 reducer result

The final reducer artifact is:
`logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/M/bilateral_foundation.json`.
It has schema `a2_piper_base_v26_4_bilateral_foundation_v1`, status
`EXPERIMENT_COMPLETE`, 8 admitted checkpoint pairs, 8 `NOT_ADMITTED` checkpoint
pairs whose reason is `STAGE3_CONTACT_DENOMINATOR_ZERO`, and zero recorded telemetry
integrity violations. All four step750 pairs were admitted.

Registered step750 values:

| cell/seed | K5 gap | Stage3 contact gap | high-water L/R | bands K5/contact/HW |
|---|---:|---:|---:|---|
| C0/S0 | 0.312500 | 0.0022526274 | 0.0010813357 | F / T / F |
| C0/S1 | 0.296875 | 0.0016353946 | 0.0031540447 | F / T / F |
| C1/S0 | 0.171875 | 0.0006321565 | 0.1901489367 | F / T / F |
| C1/S1 | 0.546875 | 0.0077231924 | 0.5224071042 | F / T / T |

For seed0, C1 strictly reduced all three non-negative asymmetry losses relative to C0.
For seed1, only high-water loss improved; K5 and contact losses worsened. More
importantly, both C1 seeds failed at least one preregistered band. The frozen typed
priority therefore emits:

```text
CANONICALIZATION_NOT_SUPPORTED
reason = C1_PREREGISTERED_BAND_FAILED
```

No Stage4/goal value participates in this decision.

Two reducer instrumentation defects were corrected without changing any §7 metric,
denominator, threshold, seed rule, pair reducer, or typed priority:

1. `v26_2.max_handle_rad` samples only `Stage3 AND strict-K5`, while
   `v26_3.handle_highwater` is natural-reset seeded and takes the maximum over all
   post-physics samples. Their former unconditional per-episode equality assertion was
   invalid and was removed only in the R2 in-memory execution overlay. The v26-3
   exact64 maximum remains the registered high-water metric.
2. Production step trace records only first-episode Stage2–5 rows. Completeness now
   requires trace env IDs to equal terminal env IDs whose max stage is at least Stage2;
   an empty trace is legal when that expected set is empty. Stage3 contact still uses
   only `stage_buf == 3` rows.

The on-disk R1 reducer was not modified. Each repair has a separate path/size/mtime
metadata capture and independent bounded review. Final analysis and closure provenance
are bound to:

- `M/source_metadata_reducer_trace_completeness_repair.json`
- `M/source_metadata_pre_analyze_trace_completeness_repair.json`
- `M/source_metadata_closure_trace_completeness_repair.json`

## 6. Review, resources, and final boundary

Independent focused review returned PASS for the corrected K target/FK gate, C runtime
composition and identity proof, M admission wiring, both reducer semantic repairs,
the final 16-pair reduction, and closure provenance. The reviewer independently
recomputed the four step750 pairs and confirmed
`CANONICALIZATION_NOT_SUPPORTED` under the frozen priority.

At closure there was no task-owned train, eval, K, reducer, IsaacSim, or GPU0–3 compute
process and no live R2 tmux session. All task GPU/Isaac/output leases were released.
Unrelated pre-existing processes on GPU4–7 were not touched.

Durable current facts:

- corrected K geometry is action-origin asymmetric, not arm-j4 hard-limit asymmetric;
- the implemented canonical seam is statically coherent and runtime-executable, but the
  four-cell experiment does not support it under §7;
- the active side-independent training orientation reference is a v26-5 investigation
  input;
- Teacher/Student handoff and G7 binding remain unchanged.

No cloud artifact bundle was produced because no stage handoff or external write was
requested. No commit or push was performed.
