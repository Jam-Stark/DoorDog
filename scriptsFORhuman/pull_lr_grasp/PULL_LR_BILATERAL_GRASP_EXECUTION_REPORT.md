# Pull LR bilateral Stage0–2 grasp — implementation and execution report

Updated: 2026-08-30 07:18 HKT

## Outcome

The pull task now supports exact raw-asset `LEFT` / `RIGHT` door mirroring and has a confirmed bilateral Stage0–2 grasp checkpoint:

`logs_rl/a2_piper_pull_lr_grasp/pull_lr_grasp_h450_xseg_resume_seed2/model_step_000250.pt`

Two independent natural-reset evaluations, each with 64 first episodes per raw side, produced:

| Eval seed | LEFT strict K5 | RIGHT strict K5 | LEFT clean K5 | RIGHT clean K5 | LEFT overforce | RIGHT overforce |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 62/64 | 62/64 | 51/64 | 35/64 | 9/64 | 4/64 |
| 1001 | 63/64 | 63/64 | 42/64 | 35/64 | 6/64 | 3/64 |
| Combined | **125/128** | **125/128** | **93/128** | **70/128** | **15/128** | **7/128** |

`LEFT` and `RIGHT` in this report always mean the raw door-asset side. Because the pull robot starts with yaw near pi, the apparent side in the robot body view is reversed.

This result proves bilateral Stage0–2 acquisition only. Stage3–5 bilateral opening and traversal are `NOT_RUN` and are not implied by this checkpoint.

## Remote mainline facts used

The implementation was checked against the current fetched `origin/A2_Piper`, not the stale local v25/v26 records.

- The current mainline selector supports `bilateral | left | right`, exact half/half assignment, and seeded permutation.
- The door builder already mirrors the complete physical asset: hinge, panel, handle root, lever/hook/latch, handle joint, and `grasp_target`. No negative scale or new USD is required.
- Stage0/1 target transforms and the natural robot reset already consume live per-env door/handle geometry; no side-specific joint pose or reward branch is needed.
- Privileged handedness is one-hot: LEFT `[1, 0]`, RIGHT `[0, 1]`.
- Mainline 4096-env bilateral runtime evidence uses `replicate_physics=false` and exact `2048/2048` assignment. The slow scene build is expected.

The best mainline v26 acquisition checkpoint and its per-env artifacts are not stored in Git. They were not used as weights because its actor contract is the push-side 133-D contract, while this pull-v6 actor remains 135-D.

## Implemented contract

- Exact per-env LR asset distribution with fixed side for each env lifetime.
- Independent `LIGHT_F0` fixture selector; pull IO remains `in`.
- Six-stage actor topology is preserved for strict warm-start compatibility.
- `completion_stage: 2` terminates the task after a sustained Stage2 grasp.
- Effective horizon is the real Stage0–2 sum `250 + 100 + 100 = 450`, not the six-stage sum.
- Actor observation shape stays 135-D. Only the two existing privileged LR values change from the old scalar-derived representation to one-hot semantics.
- Warm-start RMS changes only the two LR feature statistics. Resetting all 135 RMS dimensions was tested and rejected because it destroyed Stage1→2 transfer.
- Fixed-side evaluation uses 64 natural-reset first episodes, strict sustained K5 completion, clean K5, contact, overforce, and Stage0→1 / Stage1→2 funnels.

## Training realization

Four 4096-env seeds were launched with exact `2048 LEFT / 2048 RIGHT` per process.

- Seed3 completed 250 iterations directly.
- Seeds0/1/2 reached iterations 163/184/141, then hit the same critic-LSTM temporary allocation OOM. Logs showed about 3.7–3.9 GiB reserved-but-unallocated at failure, and seed3 completed with the same learning configuration.
- A full-state continuation smoke proved actor, value, optimizer, scheduler, and global step continuity.
- Seeds0/1/2 resumed from steps 150/175/125 in fresh processes with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` and completed to step250 at the original 4096-env population. No repeat OOM occurred.

Full resume restores model/optimizer/scheduler/trainer counters, but not simulator physics state or all RNG streams; it is standard checkpoint continuation, not bitwise trajectory continuation.

## Reducer and winner

The fixed reducer ranks candidates by:

1. weak-side strict K5;
2. weak-side clean K5;
3. total strict K5;
4. lower worst-side overforce;
5. smaller side gap;
6. weak-side Stage1→2;
7. weak-side Stage0→1.

Resume seed2 step200 led the first screen at `63/64 + 63/64`. Independent seed1001 confirmation favored step250 at `63/64 + 63/64`, with lower overforce. Combining the two predeclared evaluation populations gives step250 symmetric strict success of `125/128` on each raw side and better weak-side clean K5 than step200, so step250 is the final winner.

Evidence:

- `logs_eval/a2_piper_pull_lr_grasp/formal_h450_xseg_screen_evalseed0_summary.json`
- `logs_eval/a2_piper_pull_lr_grasp/formal_h450_xseg_top2_confirm_evalseed1001_summary.json`

## Winner videos

Final render uses two envs and records env0. This is the established recurrent-policy render topology and avoids the evaluator's unrelated `num_envs == 1` legacy CNN ONNX-export branch.

Both rendered episodes independently reached `goal=true`, `max_stage=2`, `reason=complete`:

- raw LEFT: 113 steps, `door_open_lr=+1`;
- raw RIGHT: 40 steps, `door_open_lr=-1`.

Each side has five H.264, 1280×720 views:

- main pull-side oblique view;
- live-handle `handle_top`;
- live-handle `handle_side`;
- world `+X` door-front view;
- world `-X` door-front view.

Video root:

`logs_eval/a2_piper_pull_lr_grasp/h450xseg_s2_step250_winner_render_evalseed1001_r2/`

The failed render attempts are preserved as evidence: the first exposed missing `camera_parent=trunk`; the second proved 64-env camera rendering exceeds the 24 GiB GPU budget. Neither attempt produced a successful episode or video.

## Remaining work

- Integrate LR mirroring into the full Stage3–5 pull policy path and train/evaluate full bilateral opening and traversal.
- Treat LEFT overforce and the lower RIGHT clean-K rate as behavior-quality targets, not as reasons to invalidate the confirmed strict grasp checkpoint.
- Do not claim push-task, full pull-task, real-hardware, or sim-to-real success from this Stage0–2 result.
