# A2+PiPER `base_v26-4` bilateral grasp foundation execution closure

Closed: 2026-08-28 21:24 HKT  
Source lineage: local `A2_Piper` HEAD
`e6310042348d24fbe8bb8bdc6ecd70e226fc3e32`; pre-existing dirty v26-3 worktree
preserved; no reset/stash/discard, commit, push, pull-branch merge, or external write.

## 1. Outcome first

The stage closed at its preregistered Wave K branch ceiling:

```text
K  BILATERAL_ASYMMETRIC_AT_arm_j4                 RUNTIME PASS / ADMITTED
C  BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE
   CANONICAL_IDENTITY_PROOF_NOT_RUN                STATIC ROUTE PASS
M  NOT_RUN                                         TERMINAL ROUTE PASS
```

This is not a bilateral canonical-foundation result. The admitted evidence says that,
on the frozen Stage3 matched grid and mirror-matched IK branch, LEFT was reachable while
RIGHT first crossed only the `arm_j4` upper hard limit. The plan therefore required
§6.2 and prohibited a false §6.1 canonical mirror. No admitted non-mirror RIGHT nominal
posture existed, so source/default posture was not guessed and the C0/C1 GPU experiment
was not run.

The legal stage ceiling is
`BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE`; this stage does not admit a
push/pull shared foundation, Teacher update, Student G7 binding change, or new
reward/threshold/actuator/physics claim.

## 2. Wave K runtime geometry

The final probe used one fixed-root A2+PiPER articulation per side, the repository door
fixture, fixed-base Jacobian indexing, direct in-limit joint-state application, and a
`sim.forward()`/FrameTransformer refresh. It did not use policy rollout or training.

The frozen matched grid was:

```text
x     {-0.72, -0.76, -0.80} m
|y|   { 0.18,  0.22,  0.26} m
z      0.415 m
yaw    0 rad
LEFT   +y
RIGHT  -y
```

The seed pair was frozen as an exact sagittal mirror under
`M_arm=[-1,+1,+1,-1,+1,-1]`. Direct joint-state readback error was zero for every
recorded candidate. Results across all nine matched pairs:

- LEFT: `9/9` reachable; no first hard-limit rejection.
- RIGHT: `9/9` first rejected requests had the sole upper-limit mask
  `[false,false,false,true,false,false]`.
- RIGHT first rejection occurred at IK iterations `56–67`.
- `arm_j4` overshoot was `0.003046–0.039405 rad`; no other joint was in the first
  rejection mask.
- The artifact also records root requested/readback offsets, TCP source/target pose and
  residual, the per-side minimum hard-limit margin, `arm_j4`/`arm_j6` travel relative to
  the existing default, holding-action vectors and norms, and handle-axis lever arms.

The formal K artifact is:

- `logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/K/k_kinematics.json`
- companion directional evidence:
  `logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/K/k_kinematics_no_bilateral_candidate_evidence.json`

Earlier attempts remain preserved. In particular, attempt14 was excluded because its
measurement refresh still contained drive dynamics, and attempt15 was `NOT_ADMITTED`
because it had not yet captured the first rejected per-joint request. Neither contributes
to the final typed outcome.

Evidence boundary: this is a runtime geometry result for the frozen Stage3 grid and
mirror-matched branch. It is not a policy-capability result and is not a claim about the
entire workspace.

## 3. Wave C §6.2 route

`scriptsFORhuman/v26_4/v26_4_resolve_c_route.py` fail-fast validates the admitted K
schema, status, typed outcome, all nine candidate IDs, LEFT reachability/no rejection,
RIGHT first-rejection masks, mirror seed identity, root readback contract, and direct
joint readback.

It emits:

- `C/c_route.json`: `BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE`,
  `canonicalization_permitted=false`, `posture_value=NOT_FROZEN_NO_ADMITTED_NON_MIRROR_RIGHT_POSTURE`,
  and `wave_m_status=NOT_RUN`;
- `C/canonical_identity_proof.json`:
  `CANONICAL_IDENTITY_PROOF_NOT_RUN`, `canonicalization_implemented=false`, and
  `proof_result=NOT_RUN`.

No core environment, observation/action representation, robot default, URDF hard limit,
reward, threshold, effort cap, or gain was changed. A side-conditioned `arm_j4` action
origin is technically implementable, but it cannot enlarge the physical hard limit and
there is no admitted non-mirror posture value to freeze. The stage therefore does not
substitute a guessed `+0.25/-0.25` default for evidence.

Independent focused review returned PASS with zero blockers and explicitly confirmed
that these artifacts are an honest §6.2 closure, not an identity-proof PASS.

## 4. Wave M terminal route

The preregistered M scaffold was built and statically checked before outcomes: C0/C1 ×
seed0/1, 4096 exact2048/2048, policy-only + inherited actor RMS, 750/save125, exact64
natural first episodes per side/checkpoint, and the unchanged v26-3 M1 reward contract.
The reducer froze K5 admission, Stage3-conditional contact stability, exact64 high-water,
the three bands, and two-seed strict asymmetry-loss improvement before results.

Because C did not produce exact `CANONICAL_IDENTITY_PROOF_PASS`, none of that experiment
was admissible. `v26_4_resolve_m_route.py` binds the K and C artifacts, requires v26-4
train/eval roots to be absent, and writes:

- `M/m_outcome.json`: all four cells and checkpoints 125/250/500/750 are `NOT_RUN`;
  all 16 metric fields are `null`;
- `M/orchestrator_terminal_receipt.json`: `TERMINAL_NOT_RUN` and
  `no_gpu_or_source_lock_or_train_or_eval=true`;
- `scriptsFORhuman/v26_4/evidence/terminal/m_route_registry.json`:
  `TERMINAL_NOT_RUN_VERIFIED`.

The actual `orchestrate_base_v26_4.sh main` command exited zero through this resolver
before source lock, GPU inspection/launch, tmux, training, or evaluation. No v26-4
train/eval root, source lock, or runtime training log was created. Therefore §7 has no
measured K5/contact/high-water values, no C1-vs-C0 causal comparison, and no admissible
foundation outcome. Metrics were not filled from v26-3 or from K.

Independent focused review returned PASS with zero blockers.

The machine-readable final reducer is
`logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/closure_evidence.json`;
`v26_4_finalize_closure.py` revalidates the exact K/C/M artifacts and rejects any
non-`null` M metric before writing it.

## 5. Verification and resource closure

Executed proofs relevant to the final route:

```text
scriptsFORhuman/v26_4/run_base_v26_4_kinematics_probe.sh 0
python3 scriptsFORhuman/v26_4/v26_4_resolve_c_route.py
bash -n scriptsFORhuman/v26_4/orchestrate_base_v26_4.sh
python3 -m py_compile <K/C/M route and registry scripts>
scriptsFORhuman/v26_4/orchestrate_base_v26_4.sh main \
  --gpus 0,1,2,3 \
  --canonical-key env.config.a2_v26_4_side_canonicalization_enabled
python3 scriptsFORhuman/v26_4/v26_4_verify_command_registry.py <terminal args>
python3 scriptsFORhuman/v26_4/v26_4_finalize_closure.py
```

One resource defect was found during closure: the successful directional K receipt had
been written while its IsaacSim process still remained alive on GPU0. The exact
task-owned runner/Python/tee process tree was terminated, the success cleanup path was
narrowed to direct `app.close()`, and the K script recompiled without rerunning the
scientific probe. Final process and `nvidia-smi` checks found no v26-4 process or active
GPU0–3 compute process. All v26-4 leases were released.

## 6. Final boundary

The durable fact from this stage is the admitted `arm_j4` directional hard-limit
asymmetry on the frozen Stage3 matched grid. A future stage may run a separately
preregistered non-mirror posture-discovery probe and only then freeze a side-conditioned
nominal posture. This closure does not pre-authorize that probe, a URDF limit expansion,
canonicalization, reward changes, or the C0/C1 GPU matrix.

No artifact bundle was produced because no cloud handoff was requested and external
writes were out of scope. No commit or push was performed.
