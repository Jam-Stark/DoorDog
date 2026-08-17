# READY r2 bundle — r3 gate and diagnostic report

Completed: 2026-08-18 01:03 HKT  
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`  
Final typed conclusion: `PIPELINE_DEFECT_FOUND_ACTION_CONTROL_CONTRACT`

## Outcome

The READY payload is the GRPO-finetuned Student that reached 467/512 (91.2%) in Isaac, versus the 459/512 (89.6%) baseline. It is not a pilot payload. The previous explanation that MuJoCo arm flight was expected Student behavior is withdrawn.

r3 found two hard pipeline defects before any defensible visual-domain dominance claim:

1. r2 forced the arm delta accumulator to `stage=1` from the first step. Production starts at `STAGE_WALK_TO_DOOR=0`, records the raw six-dimensional delta for the next observation, and zeros the applied arm accumulator. In r2 p00, the bad accumulator first reached `±15` at policy step 18 and robot joint speed reached 483.15 rad/s.
2. r2 clipped arm_j1–arm_j6 at 40 N·m although the READY resolved config declares 100 N·m. The owner-resolved gripper surface remains 1300/32/45. Restoring the true 100/45 effort surface made the composed MuJoCo robot numerically unstable at the standing gate: the first huge-QACC warning occurred at 0.065 s, passive final base height was 0.1331 m, and the gate denied campaign authorization.

Therefore r2 door-learning results remain void and are classified `INVALID_PIPELINE_SUPERSEDED_BY_R3`. The 40 N·m r3 four-way ablation is diagnostic-only; the resolved-effort attempt is `INVALID_NUMERICS`. No new formal campaign is claimed.

MuJoCo evidence does not decide Student quality. The corrected Isaac success figures strengthen the requirement to fix the pipeline rather than weakening that boundary.

## Gate r3

The door constraint gate passes all three owner-required checks:

| Check | Evidence | Result |
|---|---:|---|
| equality effective | 20 N·m for 1 s; max locked hinge drift 0.00003210 rad | PASS |
| release logic | below threshold remains active; above threshold disables equality | PASS |
| locked-door contrast | same 20 N·m after release moves hinge 0.29518 rad | PASS |

The prior 40 N·m standing receipt remains useful evidence for contact and name-resolved actuator placement, but cannot authorize a resolved-contract campaign. The new 100/45 standing receipt is the controlling r3 result and is `FAIL / DENIED`. Rule 16 remains enforced: finite is not standing evidence, and no closed-loop campaign may bypass this gate.

## L1 — proprio and action evidence

r2 did not directly serialize its 81D actor input. r3 reconstructed all 1000 p00 policy boundaries without inventing values: step 0 comes from the fixed manifest state; for steps 1–999, the previous policy step's final physics row is exactly the next pre-inference boundary. World angular velocity is rotated into the recorded base frame; dof state, action echoes, raw deltas, and commands come from the preceding row.

| Component | r2 abs max | bundle fixture abs max | ratio | screen |
|---|---:|---:|---:|---|
| base_ang_vel | 3.2113 | 0.0500 | 64.2× | suspect |
| projected_gravity | 1.0000 | 1.0000 | 1.0× | no |
| dof_pos offset | 4.9870 | 0.0425 | 117.3× | suspect |
| scaled dof_vel | 18.0282 | 0.0175 | 1030.2× | suspect |
| previous applied actions | 15.0000 | 0.0300 | 500.0× | suspect |
| previous raw delta | 9.4769 | 0.0375 | 252.7× | suspect |
| physical base-command echo | 2.3091 | 0.04375 | 52.8× | suspect |
| raw base-command echo | 4.6183 | 0.0500 | 92.4× | suspect |

The bundle golden authority is explicitly `DETERMINISTIC_CONTRACT_FIXTURES_NOT_ISAAC_STATE_TRACE`. These >10× ratios are the requested screens, not empirical Isaac parity results. The exact production contracts are retained: 12-leg + 6-applied-arm + 1-gripper previous-action echo; previous raw arm delta; raw k=s=0 warp; physical command echo multiplier `[2,2,.25,1,1]`; local, not world, angular velocity; name-resolved dof order and default offset. `reset_delta_actions_with_backmap=true` is also recorded honestly: the production implementation is a `pass`, while reset-to-zero is the behavior that actually runs.

## L2 — exact actor image tensor

At policy steps 0, 10, and 50, r3 inverted the exact tensors passed to the actor—there is no parallel screenshot path. All nine left/right/head round trips have maximum uint8 error 0.

- MuJoCo Renderer output reaches the actor as RGB, not BGR.
- The actor path does not vertically flip the readback.
- D435 stays 384(H)×216(W); head stays 136(H)×384(W).
- `vision_obs` is NHWC left RGB at channels 0:3 followed by right RGB at 3:6.
- ImageNet mean/std inversion is exact; separate R/G/B images are stored for all three cameras.

The bundle golden images are normalized zeros, hence their inverse is exactly ImageNet mean gray. L4(ii) and L4(iii) are therefore identical inputs in this bundle; they are not an Isaac-image replay and are not described as one.

## L3 — camera evidence

Actual Isaac eval frames were extracted from the read-only distillation worktree and placed beside the exact MuJoCo policy input. They show a material difference in background, material, occlusion, apparent door scale, and framing.

However, the available Isaac videos are not the transferred fixed-p00 state. Robot pose and door state therefore confound an extrinsic/FOV comparison. r3 classifies this level `UNRESOLVED_PENDING_PAIRED_SAME_STATE_RGB` and makes no camera transform edit from unmatched evidence. Formal camera calibration remains part of the paired E5 input, not a visual guess.

## L4 — four-way ablation

The stage-0 repair makes applied arm delta exactly zero throughout all four 1000-step rollouts. All four keep base height above termination, but under the invalid 40 N·m controller the physical arm still moves 4.87–5.60 rad.

| Mode | Base-action std | Raw arm-action std | Applied arm abs max | Physical arm displacement | Terminal |
|---|---:|---:|---:|---:|---|
| live MuJoCo RGB | 1.4420 | 3.8331 | 0 | 4.8701 rad | HORIZON |
| frozen contract-golden image | 1.4477 | 3.6512 | 0 | 5.3541 rad | HORIZON |
| ImageNet-mean gray | 1.4477 | 3.6512 | 0 | 5.3541 rad | HORIZON |
| live RGB, forced-fresh meta | 1.4060 | 3.5976 | 0 | 5.5979 rad | HORIZON |

Frozen golden and mean are bit-identical, as expected. Fresh metadata is not uniquely stabilizing. Because all four retain large arm motion even with zero applied arm delta, the discriminator points to the action/control/physics path. The subsequent resolved-effort standing failure confirms this before visual causality can be interpreted.

`VISUAL_DOMAIN_GAP_DOMINANT` is therefore not issued. A visual gap exists, but causal dominance remains unresolved until the control contract passes standing and E5 supplies paired Isaac state/RGB.

## L5 and classifications

- L5: `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`.
- Formal five-class status of the resolved-effort MuJoCo attempt: `INVALID_NUMERICS`.
- r2 campaign: `INVALID_PIPELINE_SUPERSEDED_BY_R3`.
- r2 door-learning result: `VOID`.
- r3 40 N·m ablation: `INVALID_CONTROL_CONTRACT_DIAGNOSTIC_ONLY`.
- Overall diagnostic evidence: `VALID_WITH_WARNINGS`, typed `PIPELINE_DEFECT_FOUND_ACTION_CONTROL_CONTRACT`.

## Payload correction

The additive overlay `assets/student_bundle_grpo_step10_ready_r2/manifest_payload_correction_r3.json` records:

- GRPO-finetuned Student: 467/512 = 0.912109375, reported 91.2%;
- baseline: 459/512 = 0.896484375, reported 89.6%;
- exact read-only source report roots for both 512-episode sets;
- retained rule that MuJoCo evidence is not a Student-quality verdict;
- withdrawn pilot/expected-flight interpretation.

## Primary evidence

- Final adjudication: `scriptsFORhuman/sim2sim/artifacts/e5/r3_owner_adjudication.json`
- Door gate: `scriptsFORhuman/sim2sim/artifacts/e5/constraint_gate_r3/`
- L1–L4 diagnostic evidence: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_diagnostic_r3/`
- Resolved-effort standing failure: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_diagnostic_r3_resolved_effort/`
- Bundle correction: `scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10_ready_r2/manifest_payload_correction_r3.json`

The paired manifest, paired schema, distillation handoff, shared production files, and original A2_Piper worktree were not changed. CPU/Xvfb/llvmpipe only; no GPU lease; no push.
