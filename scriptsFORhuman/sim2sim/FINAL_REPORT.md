# DoorDog A2+Piper MuJoCo shadow evaluator — final report

Completed: 2026-08-17 20:20 HKT  
Worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_sim2sim`  
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`  
Base: local `A2_Piper` at `45c9decb0080e07e7e3941a9c9b0a176d6bb24b0`

## Outcome

The additive native MuJoCo shadow stack is implemented through E6. The deployable Student actor, exact A2_Base observation/action surface, floating-base A2+Piper MJCF, v24 mechanics/friction door, CPU renderer, independent open-loop runner, native-RGB recurrent loop, paired-trace harness, and robustness sweep all have receipts.

The implemented independent stack is `VALID_WITH_WARNINGS`. A formal Isaac↔MuJoCo paired sim2sim conclusion is not claimed: E5 is `EXPLORATORY_NON_COMPARABLE` with typed input status `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`. No missing measurement is represented as zero.

No shared production file was changed. The original `/home/baoquanc/workspace/DoorDog-A2_Piper` remained read-only. No Git push was performed.

## Evidence ladder

| Level | Classification | Evidence |
|---|---|---|
| E0 Contract/golden | `VALID_WITH_WARNINGS` | READY native-Hydra Student bundle; strict `policy_state_dict`; 3-row action/LSTM replay max diff `0.0`. Adjacent config gripper face remains typed unresolved. |
| E1 Robot/camera | `VALID_WITH_WARNINGS` | A2+Piper compiles `27/26/20`, mass `44.741 kg`; 54D/1620D; 12→19→20; 200/200 torque clips; CPU axis-marker render. |
| E2 Door | `VALID_WITH_WARNINGS` | Door compiles `2/2/2 + neq1`; three-face rad receipt diff `0`; capped hinge force `-4.5 Nm`; constraint gate releases; `FRICTION_SEMANTIC_GAP`. |
| E3 Open-loop | `VALID_WITH_WARNINGS` | Composed scene `29/28/22`; 600-step finite CPU trace; direct hinge threshold crossed at `1.81 s`. |
| E4 RGB/recurrent | `EXPLORATORY_NON_COMPARABLE` | Six actual MuJoCo RGB+proprio rows replay at diff `0`; 24-step recurrent loop finite; pixels recorded only as domain-gap data. |
| E5 Paired | `EXPLORATORY_NON_COMPARABLE` | Comparator operational with v24 P0 row discipline; current Isaac input typed `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`; formal comparison `null`. |
| E6 Robustness | `VALID_WITH_WARNINGS` | Nine finite mass/drive/friction cases; final hinge range `0.16947–0.35859 rad`; static-only change exposes semantic gap. |

## R1–R10 owner crosswalk

| R | Implementation | Receipt/result |
|---|---|---|
| R1 friction axes | `DoorInstanceSpec` carries static effort, dynamic effort, and viscous coefficient. MuJoCo `frictionloss=dynamic`; joint damping carries viscous. Static is never silently discarded. | E2 and all applicable E6 rows report `FRICTION_SEMANTIC_GAP` when static != dynamic. |
| R2 unit contract | `DoorMechanicsUnitContractV1` uses canonical rad and prints requested trace-rad, USD degree readback, and canonical normalized faces. | `50/2/4.5/100` normalizes from USD `2864.789/114.592/4.5/100` at factor `57.2957795`; max diff `0.0`. |
| R3 door resistance | Formal door uses a capped position actuator with `forcerange`; passive spring is absent. | E2 hinge open-range probe reaches exactly `-4.5 Nm`. |
| R4 PD/clip | External PD computes and clips torque every physics step. Robot contract fixes the owner-evaluated gripper face `1300/32/45`. | E1 applies clip 200/200 steps and saturates gripper `[45,45]`; E3 600/600; E4 24/24. The selected config's `80/3/10` remains a provenance warning. |
| R5 golden harness | Policy golden uses ordered capture rows, explicit tensor declarations, deterministic mean output, recurrent state, float tolerance, and exact discrete comparisons. E5 reuses the read-only v24 r6 P0 receipt pattern. | E0 3 rows max diff 0; E4 6 image rows max diff 0; E5 cites v24's own 7,326-row `1e-6` result without substituting it for current paired evidence. |
| R6 deployable scope | Only Student actor/I/O/camera timebase and A2_Base deployable surface are implemented. Dimensions/orders come from the adjacent composed config. Task metrics read `door_hinge`/`handle_hinge` directly. | No privileged obs, reward, task stage machine, or trainer was migrated. E4 fixed arm-delta enable is explicitly exploratory. |
| R7 provenance | Receipts identify Git commit plus path; no new content fingerprints were computed. | Strict exact-hash remains disabled and reserved for a future formal paired E5 artifact. |
| R8 additive architecture | Implementation lives under new `gr00t/rl/sim2sim`, new MuJoCo asset path, new evidence/memory paths. | `door_open_a2_base.py`, trainers, shared configs, `BaseSimulator`, and the Isaac production hook are untouched. |
| R9 order/camera | Golden policy I/O was proved before physics. Camera conversion follows local IsaacLab `world` (+X forward,+Z up) to OpenGL (-Z forward,+Y up) algebraically. | CPU axis-marker comparison uses X red/Y green/Z blue. The Isaac panel is a contract reference, not a runtime RGB frame; no quaternion was visually retuned. |
| R10 pixel interpretation | MuJoCo camera min/max/mean/unique-color statistics are stored. | Native RGB is not used for a policy regression verdict; absent paired Isaac RTX pixels remain typed. |

## Primary artifacts

- READY Student bundle: `scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10_ready_r2/`
- Typed pre-producer bundle: `scriptsFORhuman/sim2sim/assets/student_bundle_grpo_step10/`
- Robot: `gr00t/rl/data/mujoco/A2_Piper/a2_piper.xml`
- Robot contract: `gr00t/rl/data/mujoco/A2_Piper/robot_contract.json`
- Door instance/XML/report: `scriptsFORhuman/sim2sim/artifacts/door/`
- Axis-marker comparison: `scriptsFORhuman/sim2sim/artifacts/e1/axis_marker/axis_marker_comparison.png`
- Composed scene/open-loop trace: `scriptsFORhuman/sim2sim/artifacts/e3/`
- Native RGB/replay evidence: `scriptsFORhuman/sim2sim/artifacts/e4/`
- Paired boundary: `scriptsFORhuman/sim2sim/artifacts/e5/paired_trace_receipt.json`
- Robustness sweep: `scriptsFORhuman/sim2sim/artifacts/e6/`
- Exact changed-file inventory: `scriptsFORhuman/sim2sim/CHANGED_FILES.txt`

## Narrow runtime proofs actually run

1. Native Student producer in detached read-only distillation checkout, CPU: strict 293-tensor load; READY receipt.
2. Native golden replay, CPU: 3 rows, action plus hidden/cell, max diff `0.0` at `1e-6`.
3. MuJoCo 3.10 robot build/probe, CPU: compiled `27/26/20`; 200-step finite PD run.
4. Axis marker, `LIBGL_ALWAYS_SOFTWARE=1`, GLX/Xvfb: renderer `llvmpipe (LLVM 20.1.2, 256 bits)`; no GPU lease.
5. Door probe, CPU: compiled `2/2/2`; force cap, gate release, normalized unit faces, finite open response.
6. E3 scene, CPU: 600 physics steps / 3 seconds, finite.
7. E4 native RGB Student loop, CPU renderer and inference: 6 policy / 24 physics steps, recurrent replay max diff `0.0`.
8. E5 harness materialization: 8-row operational self-check max diff `0.0`; formal comparison not run without Isaac input.
9. E6 door robustness: nine cases, all finite.

`MUJOCO_GL=osmesa` was attempted and failed because the host has no working OSMesa context. The authorized CPU fallback was GLX/Xvfb with Mesa llvmpipe. GPU0–3 activity was yielded to v24; this session never leased a GPU.

## Scientific limits and handoff

1. `BLOCKED_INPUT_ISAAC_PAIRED_TRACE` is the only formal E5 state. Produce the current Student/scene Isaac trace before making a parity claim.
2. `BaseSimulator` subclassing and Isaac-side DoorSpec integration are deferred because this branch was forbidden from changing shared production files.
3. The selected checkpoint-adjacent config exposes gripper `80/3/10`; owner R4 fixes the evaluated MuJoCo face at `1300/32/45`. Resolve that source overlay in the formal producer rather than adding a silent default.
4. Actual latch mode is `constraint_gate`. Physical-collision latch is not promoted.
5. Door internal frame/panel/handle collision pairs are excluded because inherited envelopes overlap at the closed pose; robot-to-door contact remains enabled.
6. The axis-marker probe confirms the exact configured camera basis, including the selected D435 upward forward-Z component. Do not "correct" it from appearance without a paired Isaac marker frame.
7. Add the new memory entry to `memory/a2-piper/MEMORY.md` only during owner merge; this branch intentionally leaves the index untouched.

## Git and merge readiness

Every completed phase ran `git merge A2_Piper`; each returned `Already up to date`, and the branch remained behind by 0. Work was committed locally phase by phase and was not pushed. `MERGE_READINESS.md` records the merge points and forbidden-path proof.

Superseded generated actor copies and the schema-correction intermediate bundle were removed before commit. The sole formal actor payload is the READY r2 bundle; the small typed pre-producer blocked bundle is intentionally retained.
