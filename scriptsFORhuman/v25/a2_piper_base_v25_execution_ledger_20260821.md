# base_v25 execution ledger

**Authority:** `scriptsFORhuman/v25/a2_piper_base_v25_execution_plan_R2_20260820.md`  
**Worktree:** `/home/baoquanc/workspace/DoorDog-A2_Piper`  
**Branch / starting commit:** `A2_Piper` / `eac78eae58400f6f35b6ac200e937f7e8085f063`  
**Started:** 2026-08-21 00:04 HKT  
**Current milestone:** `V25_COMPLETE_RETAIN_G7`

## Fixed scope

- Push doors only: `door_open_io="out"`.
- M1 first: deterministic LEFT-handle path, raw-label semantics, and the existing RIGHT baseline.
- No mixed-LR training, formal training, broad tests, or new guard layer before M1 owner confirmation.
- Frozen Teacher anchor: `logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt` (`A1_G7_seed0_step1500`).
- Reuse the existing native v24 hinge-friction implementation at `gr00t/rl/envs/door/a2_v24_friction.py`; do not reopen v24.

## Start-state evidence

- The worktree was already dirty before v25 implementation. Existing documentation moves/deletions outside `scriptsFORhuman/v25/` and the new v25 memory/runtime paths are treated as owner work and are not modified by v25.
- GPU0-3 are occupied by other users. GPU4-7 are occupied by the independent Student run, so no Isaac Sim, render, training, or GPU checkpoint-load command is authorized in the current resource state.
- Student tmux session: `depthadd-v3-longtrain-r15` in `/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103`.
- Student resolved config: `/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103/logs_rl/by_batch/depthadd_v3_20260820/depthadd_v3_rgbd_doorman_dr_4x64_s0_12k_r15/ranks/rank0/.hydra/.hydra/config.yaml`.
- That resolved config binds `teacher_actor_path` to `/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt` and `teacher_config_path` to the adjacent G7 `config.yaml`. Student status is therefore `CONFIRMED_G7_STEP1500`; no Student file or process was changed.
- The G7 checkpoint and adjacent saved config both exist locally.
- v24 established a behaviorally discriminative native-friction axis at static efforts `2/5/10/20 N.m`; v25 load selection is deferred until after M1.

## Focused source trace

- `door.py` maps raw `left -> +1` and `right -> -1`. Handle Y is `(half_width - handle_offset) * sign`, while hinge Y is `-half_width * sign`; with the fixed robot approach from -X toward +X, the raw label is the robot-view handle side and the hinge is opposite.
- `scenario_cfg/isaacsim.py` currently fixes `door_open_lr=["right"]`, `door_open_io=["out"]`. The door config hook already owns high-level `DoorSpawnerCfg.replace(...)` composition.
- `simulator/isaacsim/isaacsim.py` selects the task-object config hook before scene assets are instantiated. v25 should route its one config key through this existing hook.
- In A2 mode, `door_open_a2_base.py` reads `doorOpenLR` metadata, obtains grasp and pregrasp from the handle `FrameTransformer`, and computes stage-0 reward/advance from that world-frame grasp target. Positive hinge progress and +X through-door conditions do not depend on handedness.
- No environment patch is required for deterministic LEFT-only M1 unless runtime evidence contradicts this trace.

## Current decisions

- Implement deterministic handedness as one explicit env config field, consumed by the existing scene config hook. Keep `door_open_io` fixed to `out` in the M1 preset.
- Use the existing G7-compatible policy architecture and policy-only load path. Static checkpoint load/shape evidence is permitted while GPUs are unavailable; it is not Isaac Sim parity.
- LEFT/RIGHT visuals and runtime smoke remain pending GPU availability and are not replaced by static claims.

## M1 static implementation

- Preset: `gr00t/rl/config/ablation/wbmanip/base_v25_m1_left_only.yaml`.
- Scene routing: `env.config.a2_v25_door_open_lr=left` is routed through the existing simulator task-config hook and applied with `DoorSpawnerCfg.replace(...)`.
- The v25 selector fixes `rand_door_open_lr="left"` and `rand_door_open_io="out"`; inherited scenario selectors fail immediately rather than silently overriding the requested side.
- `door_open_a2_base.py` is unchanged because its A2 grasp/pregrasp/stage-0 path is already handle-relative and the later opening/through semantics are handedness-independent.

## CPU/light smoke

- 2026-08-21 00:09 HKT - `V25_M1_CPU_LIGHT_SMOKE_PASS` in 5.9 s, with no Isaac Sim or CUDA initialization.
- Hydra composed `a2_piper_base_v25_m1_left_only_v1`, `checkpoint_load_mode=policy_only`, LEFT handedness, v24 friction disabled, and reward penalty curriculum disabled.
- The scene selector function body produced `rand_door_open_lr=left` and `rand_door_open_io=out` for the sampled first/last asset configs.
- The existing v24 static checkpoint loader read G7 and returned `STATIC_POLICY_STATE_DICT_COMPATIBLE`: 20 policy keys, actor observation RMS 133-D, action head 12-D.
- Boundary: this is config/function/checkpoint static evidence only. Direct importing the IsaacLab scene module outside `AppLauncher` is unavailable because `pxr` is provided by the Isaac Sim runtime; no attempt was made to start that runtime on occupied GPUs.

## M1 Isaac Sim runtime proof

- 2026-08-21 01:35 HKT - GPU0-3 became available. Ran one deterministic RIGHT and one deterministic LEFT single-environment G7 policy-only eval with the existing three-camera `render_results` path. No formal training or mixed-LR implementation was started.
- The first RIGHT launch reached real Isaac Sim scene and door-metadata initialization, then failed fast because the single-environment preset inherited `num_mini_batches=4`. The preset now sets `algo.config.num_mini_batches=1`; the affected RIGHT smoke was rerun once and completed.
- RIGHT resolved config: `logs_eval/base_v25/m1/right/.hydra/runtime_config.yaml`; renderings: `logs_eval/base_v25/m1/right/renderings/`.
  - Visual: robot-view handle RIGHT, hinge LEFT, target markers on the physical handle.
  - Runtime: `goal_reached=true`, `max_stage=5`, `final_stage=5`, terminal `complete`, 446 steps.
  - Positive opening/crossing: `hinge_at_crossing=0.9108445 rad`, `hinge_at_release=1.6081884 rad`, `root_x_at_release=0.4839534 m`, `crossing_while_holding=true`.
- LEFT resolved config: `logs_eval/base_v25/m1/left/.hydra/runtime_config.yaml`; renderings: `logs_eval/base_v25/m1/left/renderings/`.
  - Visual: robot-view handle LEFT, hinge RIGHT; handle-top view shows the world-frame target markers following the mirrored physical handle and the gripper approaching that target.
  - Runtime: stage-0/1 completed and `max_stage=2`; terminal `stage_overtime` at 452 steps with `goal_reached=false` and near-zero hinge progress.
  - This is expected G7 LEFT zero-shot evidence: geometry/target/staging routing works, while the frozen RIGHT-trained policy does not complete the LEFT grasp/unlatch path in this one episode.
- Both resolved configs keep `checkpoint_load_mode=policy_only`, `a2_v23_p06_policy_only=true`, `door_open_io=out`, v24 friction disabled, and reward penalty curriculum disabled.
- Evidence boundary: one seed-0 episode per side is an M1 route/visual proof, not a side success-rate estimate or Teacher qualification result.

## M1 evidence status

- [x] deterministic LEFT-only config
- [x] focused runtime/config diff
- [x] raw label -> semantic handle-side explanation traced from source
- [x] CPU checkpoint/config smoke
- [x] RIGHT visual/runtime smoke
- [x] LEFT visual/runtime smoke
- [x] owner M1 confirmation (2026-08-21 01:43 HKT)

## Phase C implementation decision

- Owner confirmed M1 at 2026-08-21 01:43 HKT.
- Mixed LEFT/RIGHT uses the existing `DoorSpawnerCfg` native list with `door_open_lr=["left","right"]` and `rand_door_open_lr=None`; each spawned environment samples the two entries with equal probability while `door_open_io` stays fixed to `out`.
- `StagedTaskBase` allocates its snapshot rings from zero inside each new process and indexes every snapshot by environment id. A fresh v25 run therefore provides a fresh per-env cache without a separate disk cache or migration layer.
- The Phase C smoke preset is `gr00t/rl/config/ablation/wbmanip/base_v25_m2_mixed_lr_64x8_smoke.yaml`: 64 env, 8 updates, G7 policy-only warm start, staged reset enabled, v24 friction disabled for sampler isolation, and reward penalty curriculum disabled.

## Phase C runtime result

- The successful run is `logs_rl/a2_piper_full_stage_a2_base_smoke/base_v25/m2/mixed_lr_64x8_g7_s0_r3`.
- It naturally exited 0 after 8/8 updates, 32768 timesteps and 512 episodes, with exactly 32 LEFT and 32 RIGHT spawned environments and `model_step_000008.pt` written.
- `logs_eval/base_v25/m2/g7_zero_shot_mixed8_s0_r1/a2_v14_per_env_records.json` carries both numeric `door_open_lr` and semantic `door_handle_side`. In this early sample G7 completed RIGHT 6/6 and LEFT 0/2, confirming the handedness gap without claiming final qualification.
- Two earlier launch roots record the local Isaac Sim 5.1 failure caused by `CUDA_VISIBLE_DEVICES`: Vulkan/CUDA enumeration could not create a device. The proven multi-GPU contract is to leave CVD unset and bind each process with `ACCELERATE_TORCH_DEVICE=cuda:N`, matching the repository's v23 formal launcher.

## Phase D friction selection

- Runner: `scriptsFORhuman/v25/run_m2_friction_pilots.sh`; outputs: `logs_eval/base_v25/m2/friction_pilot/{P02,P10,P20}_mixed16_s0`.
- All three policy-only evals naturally exited 0 on the same seed0 mixed distribution (5 LEFT/11 RIGHT each). RIGHT completed 11/11 in all profiles. LEFT completed 0/5; P10 retained one stage4 and one stage3 episode, while P20 retained two stage3 and no stage4.
- v24 already froze a strictly decreasing behavioral progress gradient P02>P05>P10>P20 and selected P10/cap20 as the boundary face. The v25 pilot shows P10 remains usable rather than universal failure on the mixed path.
- Formal primary load is therefore fixed once at native P10: static effort `10.0 N.m`, dynamic effort `7.5 N.m`, viscous coefficient `0.0`. It is identical for LEFT and RIGHT and uses `gr00t/rl/envs/door/a2_v24_friction.py` unchanged.
- Formal configs: `base_v25_formal_full_p10.yaml` and `base_v25_formal_rp0_p10.yaml`. Four-cell launcher: `scriptsFORhuman/v25/launch_formal_four_cells.sh`; it binds GPU0-3 natively without CVD and keeps all cells at 4096 env, 1500 batches, save250, fresh staged reset, mixed LR, curriculum off.

## M2 pre-launch and formal launch

- `scriptsFORhuman/v25/run_m2_prelaunch_smokes.sh` completed FULL and RP0 P10 runs under `logs_rl/a2_piper_full_stage_a2_base_smoke/base_v25/m2/prelaunch_p10`.
- Both naturally exited 0 after 8/8 updates, 512 episodes and 32768 timesteps, each with exactly 32 LEFT/32 RIGHT and a distinct `model_step_000008.pt`. Resolved reward penalty is 0.0; FULL has both RP0 flags false and RP0 has both true.
- At 2026-08-21 02:24 HKT, `scriptsFORhuman/v25/launch_formal_four_cells.sh` started:
  - `v25-full-s0` / GPU0 / `logs_rl/a2_piper_full_stage_a2_base/base_v25/formal/V25_FULL_S0` / log `formal/launch_logs/V25_FULL_S0.log`;
  - `v25-full-s1` / GPU1 / `.../V25_FULL_S1` / log `formal/launch_logs/V25_FULL_S1.log`;
  - `v25-rp0-s0` / GPU2 / `.../V25_RP0_S0` / log `formal/launch_logs/V25_RP0_S0.log`;
  - `v25-rp0-s1` / GPU3 / `.../V25_RP0_S1` / log `formal/launch_logs/V25_RP0_S1.log`.
- All four completed 4096-env scene setup and entered the first optimizer update. LEFT/RIGHT spawn counts are `2065/2031` for seed0 and `2010/2086` for seed1. Reward penalty is 0.0 in all four. First-update time is 24.49-24.94 s, giving an initial completion ETA near 10.2 h.
- Post-formal scripts are prepared but not executed early: `launch_teacher_comparison.sh` runs G7/FULL-S0/FULL-S1 at 64 episodes per deterministic side; `launch_matched_intervention.sh` runs the selected FULL policy across the four P/M branches at 32 episodes per deterministic side.
- 2026-08-21 04:26 HKT - All four cells crossed step250 and wrote `model_step_000250.pt`; the tmux sessions remain active and healthy with the original common budget.

## Formal completion

- All four cells naturally completed 1500/1500 batches. Each produced 6,144,000 episodes, 393,216,000 timesteps, and checkpoints at steps 250/500/750/1000/1250/1500.
- Final roots: `logs_rl/a2_piper_full_stage_a2_base/base_v25/formal/{V25_FULL_S0,V25_FULL_S1,V25_RP0_S0,V25_RP0_S1}`.
- GPU0-3 were released after natural completion. The independent Student on GPU4-7 was not touched.

## Teacher comparison and decision

- Common G7 evaluation: LEFT 0/64 goals and 1/64 crossing while holding; RIGHT 64/64 goals and 64/64 crossing while holding.
- FULL S0 step500: LEFT 0/32 goals but 22/32 crossing while holding and 30/32 reaching stage4/5; RIGHT 32/32 goals. This is the strongest science checkpoint.
- FULL S0 step1000 produced the only LEFT goal, but that episode had post-release body contact and RIGHT regressed to 31/32. Later S0 checkpoints increased contact or reduced RIGHT quality. FULL S1 step1500 produced no LEFT crossings.
- Product decision: retain `A1_G7_seed0_step1500`. No v25 FULL checkpoint passed clean bidirectional Teacher qualification, and the Student binding remains unchanged.
- Chronic comparison at S0 step500: FULL LEFT crossed while holding 22/32; RP0 LEFT 0/32 and never exceeded stage3. RIGHT was 32/32 FULL versus 31/32 RP0.
- Representative G7 and FULL step500 LEFT/RIGHT videos are under `logs_eval/base_v25/m3/teacher_videos/`.

## Matched-prefix causality

- Runner used deterministic matched-prefix replay at existing stable grasp, `abs(hinge)<=0.25 rad`, fixed P10, and 50 control steps. Arm/gripper commands remained untouched.
- Four branches completed on 30 paired LEFT states and 32 paired RIGHT states. Every latched state completed the horizon.
- With planar active, posture ON−OFF median/mean hinge effects were `+0.007/-0.010 rad` LEFT and `-0.013/-0.007 rad` RIGHT.
- With posture active, planar ON−OFF median/mean effects were `+0.074/+0.076 rad` LEFT and `+0.148/+0.135 rad` RIGHT.
- Posture-off and planar-off branches removed nonzero command dose, and achieved roll/pitch/base displacement changed in the intended direction. The immediate hinge-progress result is therefore assigned to planar base motion, not an inactive-mask artifact.
- FULL contact retention was 0.974 LEFT/0.997 RIGHT. LEFT posture-off reduced retention to 0.812, supporting a contact-maintenance role without an immediate mean hinge benefit.
- Unified data: `logs_eval/base_v25/final/v25_summary.json`; paired figure: `logs_eval/base_v25/final/v25_causality_paired.png`; raw records: `logs_eval/base_v25/causality/V25_FULL_S0_STEP0500/`.
- All four LEFT representative branch videos completed under `logs_eval/base_v25/causality_videos/V25_FULL_S0_STEP0500/`, with three rendered views and one intervention record per branch.

## Final artifact

- Final analysis and Teacher handoff: `scriptsFORhuman/v25/a2_piper_base_v25_final_analysis_20260821.md`.
