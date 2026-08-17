# Standing-gated MuJoCo paired campaign r2

Completed: 2026-08-17 23:18 HKT  
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`  
Runner authority: commit `83f176a31675e3b581819310fe9aca68e5dc9084`, `gr00t/rl/sim2sim/cli/run_paired_mujoco_campaign_r2.py`

## Outcome

Handle geometry parity and the mandatory standing-vitals gate both pass. The unchanged eight-case manifest then completed a corrected native RGB + proprio MuJoCo campaign: 24,868 physics rows, six 20 s horizon episodes, two real `BASE_HEIGHT` terminals, and one direct hinge open crossing. All rows pass the unchanged paired schema. E5 remains typed `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`; no Isaac values or absent events are filled with zero.

This is pipeline and corrected-physics evidence for a pilot GRPO step10 Student. It is not Student-quality evidence, and success rate is not a paired parity verdict.

## 1. Handle geometry parity v2

Authority is `gr00t/rl/isaac_utils/playground/env_rand/door.py`: axle/levers lines 416–473, hooks lines 461–490, and actual `grasp_target` fixed-joint local position lines 637–652.

For the right-hinge/out-opening paired case, `door_open_lr=-1` and the realized handle-local values are:

- axle: X axis, length 0.195 m;
- inside lever center: `(-0.0975, +0.0625, 0)` m;
- outside lever center: `(+0.0975, +0.0625, 0)` m;
- both capsules: 0.125 m, rotated 90 degrees about X;
- `door_grasp_target`: `(-0.0975, +0.0625, 0)` m, exactly the Isaac fixed-joint `localPos1` on the robot-facing lever;
- the unchanged legacy paired DoorInstanceSpecs contain no `spawn_hook` field. The builder therefore records typed `LEGACY_PAIRED_DOOR_INSTANCE_HAS_NO_SPAWN_HOOK_FIELD` and preserves the existing no-hook subdomain. If a future spec explicitly sets `spawn_hook=true`, v2 requires `handle_hook_length_m` and constructs both hook cylinders at the Isaac positions.

Build report is `artifacts/e5/handle_parity_v2/door_build_report_v2.json`; both actual MuJoCo closeups are in the same directory.

## 2. Standing-vitals gate

The gate discovered that r1 omitted `robot.dof_armature_list` from the evaluated READY r2 composed config. The resolved surface is 0.03 on all 12 leg joints and 0.0 on the eight Piper/gripper joints. No extra joint damping or friction was introduced.

| Gate | Duration | Base-height evidence | Contact/orientation evidence | Result |
|---|---:|---|---|---|
| policy-free default-posture PD landing | 2.0 s | final 0.49650 m; tail span 0.00242 m | all four feet nonzero; tail mean total normal force 433.27 N; final vertical speed 0.0103 m/s | PASS |
| frozen A2_Base, zero command | 5.0 s | final 0.44587 m; tail 0.44487–0.44934 m | tail max abs roll/pitch 0.05453 rad; tail mean normal force 444.61 N | PASS |
| composed actuator mapping | 1,400 audited physics steps | door actuator IDs 0/1; robot IDs 2–21 | max ctrl-write, actuator-force, and generalized-force error all 0 | PASS |

The requested approximate standing band is 0.45–0.65 m. Frozen A2 sits on its lower edge; the receipt explicitly applies a 0.01 m contact/solver numerical margin, yielding the evaluated 0.44–0.66 m band. The raw 0.44587 m value is retained and not rounded into the stricter band.

`finite` is no longer accepted as standing evidence. Every future closed-loop campaign must consume a `PASS / AUTHORIZED` standing-vitals receipt before actor loading or episode execution.

## 3. Actuator and torque-clip finding

r1's 51/51 field meant the clip function was invoked on every physics step. It did not mean all rows saturated. Reanalysis of retained p00 gives 50/51 rows with at least one saturated joint and 381 saturated joint-steps.

r2 deliberately compiles the door's two position actuators first. Robot effort is written with name-resolved IDs and read back in `robot_ctrl_effort` using the same joint order. Across r2, the clip ran 24,868 times, 24,858 rows had at least one actual saturation, and 137,297 joint-steps saturated. Thus torque clipping is load-bearing, while invocation and saturation are now separate measurements.

## 4. Campaign r2 result

The manifest and paired schema are unchanged. Every failed episode is retained to its real terminal row.

| Case | Policy steps | Physics rows | Terminal | Unlatched | Open crossing |
|---|---:|---:|---|---|---|
| p00_baseline | 1000 | 4000 | `HORIZON` | no | no |
| p01_mass80 | 122 | 487 | `BASE_HEIGHT` | no | no |
| p02_mass120 | 1000 | 4000 | `HORIZON` | no | no |
| p03_width080 | 1000 | 4000 | `HORIZON` | no | yes, first 3.700 s |
| p04_width110 | 1000 | 4000 | `HORIZON` | no | no |
| p05_height190 | 1000 | 4000 | `HORIZON` | no | no |
| p06_height220 | 96 | 381 | `BASE_HEIGHT` | no | no |
| p07_drive_k10_cap25 | 1000 | 4000 | `HORIZON` | no | no |

p03 reached max hinge 2.25138 rad and max handle 0.51860 rad. Its handle remained below the 0.52360 rad unlatch threshold; because this paired subdomain is explicitly `no_latch`, hinge crossing without the derived unlatch event is retained as direct state evidence, not rewritten.

## 5. r1 supersession and renderer evidence

r1 remains byte-for-byte preserved and is now classified `INVALID_PHYSICS_SUPERSEDED_BY_R2`. Its systematic 0.25–0.26 s collapse came from omitted resolved leg armature plus the absence of a standing gate. Its actuator slice happened to match its robot-first compiled order, but it did not satisfy the name-resolution contract.

The first r2 attempt is also preserved. It produced 300 p00 rows before the moving camera saw an untextured constant black background and the Student RGB contract failed fast. The corrected scene adds a render-only gradient skybox and checker floor; no contact or friction value changed.

Formal r2 rendering used `MUJOCO_GL=glx`, `LIBGL_ALWAYS_SOFTWARE=1`, Xvfb, and Mesa llvmpipe `(LLVM 20.1.2, 256 bits)`, `Accelerated: no`. GPU lease was `NONE`; active GPU workloads were not touched. The 640×480 r2 initial/terminal screenshots and two 640×480 handle closeups are actual `mujoco.Renderer` images.

## 6. E5 boundary

The committed comparator schema-validates 24,868/24,868 MuJoCo rows and reports no numeric error. Until the user transfers `<isaac-root>/isaac_physx/<case_id>/trace.jsonl`, E5 remains:

- result: `EXPLORATORY_NON_COMPARABLE`;
- input: `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`;
- comparison: `null`.

Use the existing comparator with `--mujoco-root scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r2` and write `e5_formal_report.json` beside the r2 receipt after Isaac input arrives.

## Primary artifacts

- Handle v2: `scriptsFORhuman/sim2sim/artifacts/e5/handle_parity_v2/`
- Standing gate: `scriptsFORhuman/sim2sim/artifacts/e5/standing_vitals_gate_r1/`
- Formal campaign: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r2/`
- Failed RGB attempt: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r2_attempt0_constant_frame/`
- r1 retained evidence: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r1/`

No paired manifest, paired schema, distillation handoff, shared production file, or original A2_Piper worktree was changed. No push was performed.
