# READY r2 paired MuJoCo full-campaign report

Completed: 2026-08-17 20:19 HKT  
Branch: `sim2sim/a2-mujoco-shadow-evaluator-20260817`  
Policy: READY r2, GRPO step10

## Outcome

The fixed paired-case dataset and MuJoCo side of the formal campaign are complete. Eight explicit `DoorInstanceSpec` cases ran the native RGB + proprio Student/A2_Base closed loop on MuJoCo CPU until the real episode terminal condition. All emitted JSONL rows validate against the paired 200 Hz schema, all states remained finite, and torque clipping executed on every physics step.

Campaign classification is `VALID_WITH_WARNINGS`: it proves the campaign pipeline, controller, renderer, trace, and door-physics evidence path. It is not evidence that the pilot step10 Student is good. E5 remains `EXPLORATORY_NON_COMPARABLE` with typed input `BLOCKED_INPUT_ISAAC_PAIRED_TRACE` until the user transfers the matching Isaac directory.

## Paired case contract

- Manifest ID: `a2_piper_grpo_step10_legacy_door_subset_r1`
- Eight cases: baseline, mass 80/120 kg, width 0.8/1.1 m, height 1.9/2.2 m, and hinge stiffness/effort 10/2.5.
- Every case is explicit/no-RNG, right-hinge, out-opening, lever-handle, and `no_latch`.
- Every case has `tau_static = tau_dynamic = 0` and viscous friction `0`; `FRICTION_SEMANTIC_GAP` is excluded.
- Only fields already realizable by distillation commit `a197255212fa65dd9e02337b7971daac71c944fe` `door.py` are varied.
- Fixed initial state includes root pose, 20 joint positions/velocities, door/handle state, zero LSTM/action/delta state, replicated 30×54 A2_Base history, and valid time-zero cameras.
- Direct task facts are handle `>= pi/6` for unlatch and hinge `>= 0.174533 rad` for open crossing.

The distillation handoff records the exact additive `DoorSpawnerCfg` mapping and requires three-face `DoorMechanicsUnitContractV1` realized values. The paired schema authority is commit `2bf0ac417858128ab761fca3fa3aa8451b7ea843`, path `gr00t/rl/sim2sim/schemas/paired_trace_row.schema.json`; provenance is commit+path, not a content hash.

## MuJoCo campaign result

| Case | Policy steps | Physics rows | Terminal | Unlatched | Open crossing |
|---|---:|---:|---|---|---|
| p00_baseline | 13 | 51 | `BASE_HEIGHT` | no | no |
| p01_mass80 | 13 | 51 | `BASE_HEIGHT` | no | no |
| p02_mass120 | 13 | 51 | `BASE_HEIGHT` | no | no |
| p03_width080 | 13 | 51 | `BASE_HEIGHT` | no | no |
| p04_width110 | 13 | 52 | `BASE_HEIGHT` | no | no |
| p05_height190 | 13 | 51 | `BASE_HEIGHT` | no | no |
| p06_height220 | 13 | 50 | `BASE_HEIGHT` | no | no |
| p07_drive_k10_cap25 | 13 | 51 | `BASE_HEIGHT` | no | no |

Totals: 104 policy decisions, 408 physics rows, and 408/408 per-step external-PD torque clips. Terminal times are 0.250–0.260 s. Every episode is retained exactly through its environment terminal row; none is extended after `BASE_HEIGHT`, and no absent unlatch/open event is filled with zero.

The common early fall is a measured pilot-Student/independent-runtime trajectory outcome. It does not invalidate the case set and is not turned into a success-rate verdict. The paired objective remains trajectory and mechanics comparison against the same Isaac cases.

## RGB and asset-render evidence

Each case stores final left/right/head native MuJoCo frames and E4-style min/max/mean/unique-RGB statistics. These are domain-gap data only. The acceptance screenshot is a real `mujoco.Renderer` frame from `p00_baseline` `axis_overview`, 640×480 RGB PNG.

Renderer evidence: `MUJOCO_GL=glx`, `LIBGL_ALWAYS_SOFTWARE=1`, Xvfb, Mesa `llvmpipe (LLVM 20.1.2, 256 bits)`, `Accelerated: no`, GPU lease `NONE`. v24 activity on GPU0 was not disturbed.

The first screenshot attempt requested 1280 px against MuJoCo's 640 px offscreen framebuffer and failed before any trace row. The corrected 640×480 run is the formal r1 campaign. The four-file failed scratch was moved, not deleted, to `/tmp/doordog_sim2sim_paired_campaign_r0_framebuffer_failure`.

## E5 handoff

Current waiting report:

- classification: `EXPLORATORY_NON_COMPARABLE`
- input status: `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`
- MuJoCo schema validation: 8/8 traces, 408/408 rows
- numeric error: `null`
- formal comparison: `null`

After the user transfers the Isaac producer directory, run:

```bash
PYTHONPATH=. /home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  gr00t/rl/sim2sim/cli/compare_paired_campaign.py \
  --manifest scriptsFORhuman/sim2sim/artifacts/e5/paired_case_manifest/paired_case_manifest.json \
  --schema gr00t/rl/sim2sim/schemas/paired_trace_row.schema.json \
  --mujoco-root scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r1 \
  --isaac-root PATH_FROM_USER \
  --output-report scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r1/e5_formal_report.json
```

The comparator aligns by fixed case/initial-state/seed and physics step, reports scalar/vector max error and RMSE plus direct unlatch/open event deltas, and uses the five-class result discipline. It intentionally imposes no universal physics-error threshold and does not use RGB or success rate as a regression verdict.

## Primary artifacts

- Case manifest and handoff: `scriptsFORhuman/sim2sim/artifacts/e5/paired_case_manifest/`
- Paired row schema: `gr00t/rl/sim2sim/schemas/paired_trace_row.schema.json`
- MuJoCo campaign: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r1/`
- Campaign receipt: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r1/campaign_receipt.json`
- E5 waiting report: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r1/e5_waiting_report.json`
- Asset screenshot: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r1/mujoco_asset_initial.png`
- Render receipt: `scriptsFORhuman/sim2sim/artifacts/e5/paired_mujoco_campaign_r1/mujoco_asset_render_receipt.json`

No shared production file was edited, no GPU was leased, no push was performed, and the original A2_Piper worktree remained read-only.
