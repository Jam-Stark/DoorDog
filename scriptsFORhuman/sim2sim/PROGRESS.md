# DoorDog MuJoCo shadow evaluator progress

Last updated: 2026-08-17 19:44 HKT

## Scope and authority

- Worktree: `/home/baoquanc/workspace/DoorDog-A2_Piper_sim2sim`
- Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`
- Mainline source: local branch `A2_Piper`
- Original worktree `/home/baoquanc/workspace/DoorDog-A2_Piper` is read-only; it contains active v24 work and the owner-supplied sim2sim design package.
- This branch only adds isolated sim2sim implementation/evidence paths. Shared production files, `door_open_a2_base.py`, trainers, shared configs, `scriptsFORhuman/a2_piper_longterm_TODO.md`, and `memory/a2-piper/MEMORY.md` are outside the write boundary.

## Evidence ladder

| Level | State | Current evidence |
|---|---|---|
| E0 Contract / golden | COMPLETE_WITH_WARNING | READY native-Hydra Student bundle; CPU action/LSTM golden replay 3/3 rows, max diff 0. Legacy gripper face remains typed. |
| E1 Robot | COMPLETE_WITH_WARNING | Floating-base MJCF compiled 27/26/20 at 44.741 kg; 54D/1620D and 12→19→20 proofs pass; CPU axis marker captured. |
| E2 Door | COMPLETE_WITH_WARNING | Door compiles 2/2/2 + one gate; rad three-face diff 0; capped resistance hits 4.5 Nm; friction semantic gap explicit. |
| E3 Open-loop | COMPLETE_WITH_WARNING | Composed scene 29/28/22; 600-step CPU trace finite; direct door state crossed 0.174533 rad at 1.81 s. |
| E4 Closed-loop proprio/pixel | EXPLORATORY_COMPLETE | 6 native-RGB Student rows replay at diff 0; 24-step CPU loop finite; pixel data recorded, no policy verdict. |
| E5 Paired cases | NOT_STARTED | Requires comparable independent backend traces. |
| E6 Robustness | NOT_STARTED | Requires at least one interpretable E4/E5 path. |

Missing evidence is typed and is never filled with zero.

## Phase log

### Phase 0 — source reconnaissance (complete)

- Confirmed current worktree and `A2_Piper` both start at commit `45c9decb0080e07e7e3941a9c9b0a176d6bb24b0`.
- Confirmed distillation branch `codex/a2-v13-student-distillation-20260717_2103` at `a197255212fa65dd9e02337b7971daac71c944fe`; merge base with `A2_Piper` is `4b29411101a1de4949f42140b61f1ccb4c2e67e7`, left/right counts `106/32`.
- Read the routed memory plus owner audit and the package documents in README order. Owner R1-R10 are treated as fixed decisions.
- Located repository assets `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf`, `gr00t/rl/data/policies/A2_Base/policy.pt`, and `policy_metadata.json`.
- Resolved the exact production 54D frame/history, name-based leg remap, 12→19→20 action path, delta update/reset, and v24 three-face mechanics/friction receipt contracts into `source_map.md`.
- Selected the formal GRPO step10 Student checkpoint and its adjacent config from recorded fixed-G2 evidence; traced the production strict `policy_state_dict` loader. Native runtime export remains an E0 execution item, not a source ambiguity.
- Preserved the checkpoint-adjacent legacy gripper gains `80/3/10` as a source gap while applying the owner-resolved evaluated face `1300/32/45` for MuJoCo control.
- No GPU was leased.

Phase-completion merge record: local `A2_Piper` was already at the worktree base; merge result is recorded in `MERGE_READINESS.md`.

### Phase 1 — E0 Student bundle and golden boundary (complete)

- Opened detached read-only producer checkout `/tmp/DoorDog-student-producer-sim2sim-20260817` at distillation commit `a197255212fa65dd9e02337b7971daac71c944fe`; no files were committed to that branch.
- Preserved the pre-producer typed `BLOCKED_NATIVE_LOADER` bundle, then used the producer branch's native Hydra actor constructor and strict `policy_state_dict` load on CPU.
- Exported only the deployable Student actor surface. Actor observation 81, action 12, applied action 19, physics/control cadence 200/50 Hz, camera cadence 30/30/15 Hz, orders, and shapes all come from the adjacent composed config.
- Corrected a producer-only recurrent row-layout error before formal export. The READY r2 golden stores hidden/cell tensors as `[row, layer, batch, hidden]`.
- Replayed three deterministic contract rows through a newly instantiated native actor; action means and recurrent hidden/cell state matched at `atol=1e-6`, maximum absolute difference `0.0`.
- Retained the source discrepancy: the selected config declares gripper `80/3/10`; the bundle does not silently replace it. The robot realization separately uses the owner-resolved evaluated `1300/32/45` face.
- No GPU was leased.

Phase-completion merge record: `git merge A2_Piper` returned `Already up to date`; behind remains 0.

### Phase 5 — E4 image replay and native-RGB loop (complete at exploratory level)

- Added the exact deployable 81D Student observation order and raw uint8 NHWC normalization surface. Proprio components use the production semantics: local base angular velocity, projected gravity, 20D position delta, 20D velocity, previous 19D action, raw 6D delta, physical 5D command, and raw 5D command.
- Ran the native Student actor and the repository A2_Base TorchScript policy together against the composed MuJoCo scene on CPU. Six Student decisions / 24 physics steps remained finite and applied torque clip on all 24 physics steps.
- Captured left/right at 30 Hz and head at 15 Hz against the 50 Hz policy clock; camera age metadata uses the production 0.1 s normalization and exact `[ages, valid]` order.
- Replayed the six cached MuJoCo RGB+proprio rows through a reset native recurrent Student actor; all mean actions matched with maximum absolute difference `0.0` at `1e-6`.
- Recorded min/max/mean/unique-color data for each MuJoCo camera. No Isaac RTX pixels were acquired while v24 held its activity window, so pixel observations remain domain-gap data under R10.
- Production stage logic was not migrated under R6. The fixed nonzero arm-delta enable makes the native-RGB loop `EXPLORATORY_NON_COMPARABLE`, not a task-quality or regression verdict.

Phase-completion merge record: `git merge A2_Piper` returned `Already up to date`; behind remains 0.

### Phase 4 — E3 composed open-loop scene (complete)

- Composed the proven robot and door artifacts without touching either production simulator. The resulting scene compiles as `nq=29`, `nv=28`, `nu=22`, `neq=1` with explicit robot/door qpos, qvel, and actuator layouts.
- Scoped the door defaults to class `door` before composition so door friction/density do not leak onto robot geoms.
- Ran 600 CPU physics steps at 200 Hz. External robot PD torque clipping was applied 600/600 steps; the full scene remained finite and final base height was `0.5999 m`.
- The constraint gate released at `0.515 s`. A declared 10 Nm E3 hinge excitation then opened the door; direct door-state metrics crossed `0.174533 rad` at `1.81 s` and reached `0.5967 rad`.
- This is open-loop bring-up evidence. The explicit hinge excitation is not attributed to the Student policy and no paired Isaac trajectory is claimed.

Phase-completion merge record: `git merge A2_Piper` returned `Already up to date`; behind remains 0.

### Phase 3 — E2 door mechanics and latch (complete)

- Materialized an explicit right-hinge/out-opening v24-friction door instance with no RNG and generated standalone MJCF plus build receipt.
- `DoorMechanicsUnitContractV1` prints requested trace-rad, realized USD-degree, and canonical rad faces. The 57.2957795 degree/rad conversion returns damping/stiffness to `50/2` with normalized maximum difference `0.0`; mass and effort pass through.
- Parity resistance is a capped position actuator. At the open-range force probe the hinge actuator reaches exactly its `4.5 Nm` cap; passive spring is not used.
- MuJoCo `frictionloss=0.75` maps the dynamic Coulomb face and joint damping `0.0` maps the viscous face. Static `1.0 != 0.75` is retained as `FRICTION_SEMANTIC_GAP` rather than dropped.
- Actual latch mode is `constraint_gate`: it held the closed hinge, released at the configured handle threshold, and the door then opened to `0.2301 rad` under external torque with finite state. Physical-collision latch is not claimed.
- Internal frame/panel/handle collision pairs are excluded because the inherited collision envelopes overlap at the closed pose; robot-to-door collision remains enabled.

Phase-completion merge record: `git merge A2_Piper` returned `Already up to date`; behind remains 0.

### Phase 2 — E1 robot, controller, and camera-basis probe (complete)

- Converted the repository A2+Piper URDF through MuJoCo 3.10 `MjSpec`, then materialized a floating `trunk`, restored the URDF trunk and fixed arm-base inertia faces, and added 20 named torque motors.
- Compiled dimensions are `nq=27`, `nv=26`, `nu=20`; compiled body mass sums to the URDF total `44.741 kg`. Joint and actuator order are exact name-derived contracts.
- External PD runs at 200 Hz and applies torque clipping on every physics step. A 200-step CPU probe remained finite; synthetic gripper saturation is exactly `[45,45]` under the owner-fixed `1300/32/45` face.
- The A2_Base builder produces the exact 54D frame and frame-major 30×54=1620 history. Name mapping from simulator order to policy order is `[0,6,3,9,1,7,4,10,2,8,5,11]`.
- The Student/action surface proves 12 high-level → 19 logical → 20 simulator joints, including open gripper target `[0.035,-0.035]`.
- `MUJOCO_GL=osmesa` failed on the host because the OSMesa context library is unavailable. The required axis-marker probe instead ran with GLX/Xvfb and Mesa llvmpipe, with no GPU lease.
- The camera conversion follows the local IsaacLab source definition exactly: Isaac `world` (+X forward,+Z up) to OpenGL (-Z forward,+Y up), with red X, green Y, blue Z markers. The Isaac side of the comparison is a contract diagram rather than a runtime RGB capture, so pixel parity remains unclaimed.

Phase-completion merge record: `git merge A2_Piper` returned `Already up to date`; behind remains 0.

## Next action

Materialize the E5 ordered paired-trace harness and typed missing-Isaac receipt, then run E6 CPU robustness sweeps over the declared door friction/mechanics axes.
