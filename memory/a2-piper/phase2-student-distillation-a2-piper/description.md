---
name: phase2-student-distillation-a2-piper
scope: DoorDog-A2_Piper-only Phase2 Student Distillation / DAgger vision policy
status: TRAINING_PASS / R14_RESOLVED / V16B_335L_STAGE1_5_SWEEP_COMPLETE / SCHEME_C_RUNTIME_PASS_VISIBILITY_PARTIAL
last_updated: 2026-07-23 18:06 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/phase2-student-distillation-a2-piper/description.md
  - memory/a2-piper/phase2-student-distillation-a2-piper/TODO.md
  - memory/a2-piper/phase2-student-distillation-a2-piper/DONE.md
read_when:
  - 开始实现、review、debug 或运行 DoorDog-A2_Piper-only Student Distillation route 前
  - 需要恢复 sealed Teacher triplet、Student checkpoint、DAgger、eval 或 ONNX/export validation 前
---

# A2+Piper Phase2 Student Distillation

## Status and Accepted Scope

Status at 2026-07-23 18:06 HKT: `TRAINING_PASS / R14_RESOLVED / V16B_335L_STAGE1_5_SWEEP_COMPLETE / SCHEME_C_RUNTIME_PASS_VISIBILITY_PARTIAL`。DoorDog-A2_Piper 在本 entry 中只按 A2+Piper route 处理；final accepted training goal 已收窄为一次真实的 Student Distillation update 并产生新的 Student checkpoint。该训练目标已经完成，不是仅 `STATIC PASS`；后续 camera sweep 和 Scheme C 双视角验证只做 Teacher eval diagnostic，没有训练。

Frozen product candidate 为 `90164b26bece1623e6c4a2dfe32769a4af72c2ed5f2efc80857ba9e82d6691cf`；code-quality 与 IsaacLab semantics review 均 PASS，targeted static test 为 `25 passed`。Teacher immutable triplet 已 sealed：checkpoint `logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459/model_step_001000.pt` SHA256 `40939c4af4e9744dfbc9d21315adcb59d01fbad80c1a3e8b480277aa2d463523`；saved config `logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459/config.yaml` SHA256 `3ba6e8a35c2659807acbd43adeae1871bc02d033f4578690a5eb3e4b37bffa77`；manifest `logs_rl/a2_piper_student_distillation_runtime/base_v10_D_teacher-20260714_144359/teacher_manifest.json` SHA256 `c22f0648ca4225cc0d1f44159df0beea4300509eb7eaad0e7c1ff71cd384cadc`。

## Implemented Training Contract

- Student deployable contract：`81D proprio + RGB(248832D) -> 12D high-level action`；Teacher actor `133D -> 12D`，optional critic `138D`；frozen A2_Base `1620D -> 12D` leg action。
- rollout contract：`12D Student/Teacher high-level + 12D A2_Base legs = 24D`，再由既有 A2 env action chain 映射为 `20D` simulator command。BC loss 只比较 learned 的 12D high-level action；不复用 HOMIE/G1 trainer、checkpoint、camera link 或 fallback。
- Object prediction 保持 explicitly disabled，直到存在经过验证的 A2 target/frame；checkpoint strict loader behavior 只有 static test evidence。

## One-update TRAINING_PASS Evidence

在 GPU0 的精确 one-update command 为：

```bash
CUDA_VISIBLE_DEVICES=0 HYDRA_FULL_ERROR=1 WANDB_MODE=disabled /home/baoquanc/anaconda3/envs/isaaclab/bin/accelerate launch --num_processes 1 gr00t/rl/train_agent_trl.py +exp=wbmanip/door_open_a2_base_dagger-lstm num_envs=4 algo.config.num_steps_per_env=1 algo.config.num_mini_batches=1 algo.trl.num_total_batches=1 algo.trl.per_device_train_batch_size=4 callbacks.model_save.save_frequency=1 use_wandb=false experiment_dir=logs_rl/a2_piper_student_distillation_one_update teacher_actor_path=logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459/model_step_001000.pt teacher_config_path=logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459/config.yaml teacher_manifest_path=logs_rl/a2_piper_student_distillation_runtime/base_v10_D_teacher-20260714_144359/teacher_manifest.json
```

- Runtime started `2026-07-15 17:08:07 HKT`; live dimensions were actor `81`, RGB `248832`, Teacher `133`, critic `138`, A2_Base `1620`; frozen A2_Base was used for low-level leg actions.
- Iteration `1` completed with `4` total timesteps. GPU0 pre/post process memory was `1 MiB`; frozen candidate hashes remained unchanged.
- Student artifact is `logs_rl/a2_piper_student_distillation_one_update/model_step_000001.pt`: SHA256 `5ce4d36843b20afde0c4abc61d17641978f7cac078f441cec8786edeb9a67ccc`, size `155631363` bytes, mtime `2026-07-15 17:09:28 HKT`.
- The saved live-model checkpoint has `142` finite policy tensors, `optimizer_state_dict.state` with `78` entries, and serialized `state.global_step=1`.

## Lifecycle and Strict-load Boundaries

The stable checkpoint save occurred before Kit became silent for `207s`. At `17:12:55 HKT`, the sole authorized cleanup sent `TERM` only to exact PGID `3724660`; it exited within `5s`, with no `SIGKILL`. Runner exit `143` is attributable to this cleanup and does not negate `TRAINING_PASS`.

Independent full-architecture strict reconstruction is `PARTIAL/NOT_RUN`: saved unresolved `${hydra:...}` fails outside Hydra with `UnsupportedInterpolationType: hydra`. The checkpoint was emitted by the live model and the policy tensors, optimizer state, and training state were sealed; candidate strict-loader behavior remains statically tested. Do not promote this to an independent architecture reload PASS.

## R14 Camera Transform Resolution

2026-07-22 的专用 `probe_a2_student_camera_transform.py` 在物理 GPU1（`CUDA_VISIBLE_DEVICES=1`，logical `cuda:0`）对一个 env reset 后的同一 physics step 同时采集 `robot.data` trunk、reset 前已初始化的 trunk `XformPrimView`、`TiledCamera` 自身已初始化的 camera `XformPrimView`、configured local offset、cached `CameraData` 与临时 `update_latest_camera_pose=True` 的强制刷新。sealed evidence `/tmp/a2_student_camera_transform_probe_r14_20260722_v3.json` SHA256 为 `d9e32ddaad4037f448cba8fdcdc03f2a69cb1d1ad5f10cb77bc3903ddd60d384`。

- `robot.data` trunk 对 live trunk prim position error `0.0m`、orientation error `9.1292371e-08rad`。
- camera local pose 对 configured `[0.25,0,0.14]` / world-convention quaternion 的 position error `0.0m`、orientation error `8.1713388e-08rad`。
- live camera prim 对 trunk+configured-offset expected transform 的 position error `0.0m`、orientation error `2.0803985e-07rad`。
- 默认 cached `CameraData` 对 live camera prim position error `0.8946629167m`；同一 physics step 内临时开启 pose update 并 `camera.update(dt=0, force_recompute=True)` 后，position error `0.0m`、orientation error `1.3485386e-07rad`，sensor frame 只增加一帧且 physics step counter 不变；flag 随后恢复为 `false`。

因此 R14 root cause 是 IsaacLab `CameraCfg.update_latest_camera_pose=false` 下 `CameraData` 保留初始化 pose，不是 camera parent、configured offset 或 quaternion convention 错误。诊断必须复用 `TiledCamera` 自身已经初始化的 camera `XformPrimView`；为同一 camera path 新建第二个 view 会触发一次 authored USD→Fabric sync 并污染 live diagnostic。该结论不决定最终 camera pose/mount，也不授权修改 Student observation 或 camera config。evidence 在 `SimulationApp.close()` 前 seal；close 仍未返回，之后只 TERM exact probe PID，故 R16 lifecycle 仍未通过。

## Historical `base_v13_A` Gemini 335L Stage1–4 Pose Sweep

2026-07-22 在 GPU0 完成 eval-only、16-env、seed0 的 centered Gemini 335L pose sweep；没有调用 trainer。source Teacher 为 `logs_rl/a2_piper_student_distillation_v13_A_teacher-20260717_2103/model_step_003000.pt`，SHA256 `d576ca4bc6f596e45a8d744ca766164b374f8aba4409b06bcd7c460d6b057a36`；wrapper 将 checkpoint/config 复制到 fresh output 的 `_eval_input` 后再次验证相同 hash，避免 eval 写 sealed source。sealed summary 为 `/tmp/a2_camera_pose_sweep_16env_seed0_20260722/camera_pose_sweep_summary.json`，共 `248` sample events。

- Intrinsics 由 Gemini 335L nominal `94°H×68°V`、centered `1280×800 -> 1280×720 -> 384×216` 推导。spec 值 `[fx,fy,cx,cy]=[179.0428965384,177.9073162215,192,108]`；pinned IsaacLab square-pixel projection 使用 `[179.0428965384,179.0428965384,192,108]`，`fy` 差 `+1.1355803169 px`，不是 physical calibration。
- sweep 复用一个现有 `TiledCamera` 和其 view；candidate local pose 以 OpenGL convention 用 `set_local_poses/get_local_poses` 闭合。每个 candidate 都在同一 physics step `sim.render()` + `camera.update(dt=0, force_recompute=True)`；physics counter 未前进，RGB/raw instance segmentation 对 control 与 search 不全同，runtime intrinsic error 为 `0`。
- stage1-4 diagnostic score 以 handle `0.35`、handle+both fingers `0.35`、door panel `0.15`、handle centered `0.15` 加权。推荐 `z_low_020`：trunk local position `[0.32,0,0.20]m`，RPY `[0,-6,0]°`，quaternion `[0.9986295348,0,-0.0523359562,0] wxyz`，score `0.9230179028`；四项 rate 为 `0.9697357204/0.8729752771/0.9799658994/0.8738277920`。原 `[0.32,0,0.25]` center seed 排第四；legacy control score `0`。
- 该结果是历史 stage1–4 right/out search result；它不再是当前仿真默认，不冻结 physical mount，也不证明 mirrored left/out、calibrated intrinsics/extrinsics、vibration/exposure/latency/depth、cable/thermal/mechanical clearance。

## `base_v16_B` Gemini 335L Stage1–5 Sweep and Videos

2026-07-22 在 GPU0 使用主线完整任务 checkpoint `logs_rl/a2_piper_full_stage_a2_base/base_v16_B_m29_m32_mass80_160-20260721_230405/model_step_002000.pt` 做正式 eval-only 16-env seed0 sweep。checkpoint SHA256 为 `5628a25ee53395ddc581d2da184c32635e109ff3691e54a823ad054236475e3f`，adjacent config SHA256 为 `3c8aead9025b66a7f6f2ac3afc81bedc9cdafa1d12bd08fd43058eff8b4fd144`；clean mainline runtime pin 为 `815b367f5de2a52b26a4b872d0457af8817d01bd`。wrapper 只从专属 worktree overlay camera sweep code/config；`training_performed=false`，没有 trainer。

- 16 episodes 全部完成，`15/16 goal`；env0 stage0 overtime，env1–15 到达 stage5。exact ranking stages 为 `[1,2,3,4,5]`；每 candidate 的 matched sample counts 为 `298/238/397/876/839`。pose readback、render diversity、runtime intrinsic `0px` error 和 candidate 之间 physics counter 不前进全部 PASS。
- 排名为 `x_near_028` `0.5614803625`、`pitch_up_12` `0.5484327795`、`center_seed` `0.5324395770`、`z_high_030` `0.5177492447`、`x_far_036` `0.4969788520`、`pitch_level_00` `0.4939388218`、`z_low_020` `0.4914086103`、legacy `0`。数值 winner `x_near_028` pose 为 `[0.28,0,0.25]m`、RPY `[0,-6,0]°`、quaternion `[0.9986295348,0,-0.0523359562,0] wxyz`。
- 每个 candidate 都输出独立 `384×216@10fps` MP4；env1 每个视频 `224` 帧，stage0–5 帧数为 `32/18/18/26/64/66`。8 个 MP4 均已用 ffmpeg end-to-end decode；manual QA contact sheets 覆盖 stage2/4/5。
- 所有候选在 stage5 都出现严重视野坍塌。`x_near_028` 的 stage5 handle/trio/panel/centered rate 为 `0.0953516091/0.0500595948/0.1370679380/0.061978546`，handle pixel p50 为 `0`；人工帧主要是 floor/wall。因此它只作为下一轮 pose-search center，不接受为 final simulation camera 或 physical mount，不修改 production Student camera/observation。
- sealed summary: `logs_eval/a2_camera_pose_sweep_v16B_ckpt2000_stage1_5_16env_seed0_env1_20260722_2325/camera_pose_sweep_summary.json`。下一步是围绕 stage5 corridor/door-frame coverage 扩展 pose grid，之后再做 mirrored `left/out` 和 calibrated hardware validation。

## Scheme C: Portrait D435i + Provisional A2 Head

2026-07-23 在 GPU0 用同一 `base_v16_B` checkpoint 和 clean pinned runtime commit
`815b367f5de2a52b26a4b872d0457af8817d01bd` 完成 eval-only 16-env Scheme C 验证；没有
trainer，`training_performed=false`。云报告原始修改版按 SHA-256
`c179d59edecb9adb82dc00d0fa45c22018b3430bf384c46c5125a5ceabac52d0` 原样归档，但其
`front-right cheek` 与“向中轴内转 5–15°”建议明确作废：两路 optical frame 都执行
`y=0,yaw=0` 的左右镜像对称 contract。

- D435i 使用 portrait `216×384`、trunk local `[0.28,0,0.25]m`、pitch `-12°` 和
  software-uprighted FoV `42.2725589501°H×69°V`；A2 Head diagnostic 使用
  `384×136`、`[0.32,0,0.25]m`、pitch `-12°`、`132°H×77.0024873497°V`。Head
  extrinsic 是 provisional trunk frame，不是 CAD/实机标定。
- 两个 high-level `TiledCamera` 在同一次 `sim.render()` 后分别
  `update(dt=0, force_recompute=True)`；runtime intrinsics 误差 `0px`，sensor frame
  各增加一次且 physics counter 不变。16 episodes 全部完成，checkpoint 保持
  `15/16 goal`。
- conservative union 的 stage1–5 handle rate 为
  `84.56%/85.71%/99.75%/99.89%/10.25%`，trio rate 为
  `1.01%/12.18%/74.31%/95.66%/3.22%`。三份 env1 MP4 共 `224` 帧、覆盖
  stage1–5，并全部 end-to-end decode；人工 QA 确认 stage3–4 改善，但 stage5
  handle 已在固定朝前相机身后。
- sealed evidence:
  `logs_eval/a2_piper_camera_scheme_c_v16_formal-20260723/camera_pose_sweep_summary.json`。
  结论是 `SCHEME_C_IMPLEMENTED / RUNTIME_PASS / VISIBILITY_PARTIAL`，不是 full-task
  camera hard-gate PASS，也不证明 mirrored left/out 或 physical mount。

## Historical Failure Facts and Deferred Work

R13 `FAIL_TIMEOUT`, R14 `FAIL_FINAL_SEAL`, and R15 `FAIL_EVIDENCE_SERIALIZATION` remain reusable lifecycle/evidence facts; none was a training PASS. R15 specifically exposed strict JSON serialization of `torch.__version__` as `torch.torch_version.TorchVersion`, before an `evidence.json` seal. They are superseded as blockers for the accepted one-update goal, not erased.

G1 compatibility/regression, R16 lifecycle perfection, final physical camera mount and mirrored left/right validation, randomization, multi-seed validation, Student eval, ONNX/export, policy quality, and open-door success are deferred and non-gates for the completed training scope. The bounded v16 stage1–5 sweep and Scheme C prototype are complete, but both confirm that fixed forward trunk views lose the handle after passage. A full-task design still needs a distinct stage5-aware viewpoint or an explicit observation requirement that stops needing the handle after release. These items must be separately approved and validated before any future claim about those outcomes.

## TODO Summary

- 2026-07-15 17:17 HKT - Current accepted one-update A2+Piper Student Distillation goal is complete at `TRAINING_PASS`; optional future tuning/validation is non-blocking and requires separate scope/approval.
- 2026-07-22 21:35 HKT - R14 transform root cause and the historical `base_v13_A` stage1–4 sweep are complete.
- 2026-07-22 23:41 HKT - `base_v16_B` stage1–5 sweep and all eight candidate videos are complete; `x_near_028` is only the next search center because stage5 visibility collapses, while final right/out pose, physical mount and mirrored left/right remain deferred.
- 2026-07-23 18:06 HKT - Symmetric Scheme C portrait D435i + provisional A2 Head eval is complete; runtime/synchronization/video gates passed, stage3–4 visibility improved, but stage5 remains a documented visibility failure and final hardware/mirrored validation stays deferred.

## DONE Summary

- 2026-07-13 22:28 HKT - Static A2+Piper Phase2 Student Distillation framework completed and statically reviewed; runtime/training remained INCONCLUSIVE at that time.
- 2026-07-14 23:21 HKT - Immutable non-`last.pt` Teacher checkpoint/config/manifest triplet sealed and identity-validated; this alone did not claim Teacher runtime load.
- 2026-07-14/15 HKT - R13/R14/R15 camera/lifecycle attempts recorded `FAIL_TIMEOUT` / `FAIL_FINAL_SEAL` / `FAIL_EVIDENCE_SERIALIZATION`; these are preserved historical lifecycle facts, not training success.
- 2026-07-15 17:17 HKT - `TRAINING_PASS`: one real GPU0 Student Distillation update completed and sealed as `model_step_000001.pt`; lifecycle cleanup and independent strict reconstruction limitations are explicitly bounded above.
- 2026-07-22 15:36 HKT - `R14_STALE_INITIALIZATION_POSE_CONFIRMED`: same-step GPU probe closed parent/local-offset/live-camera transforms and isolated the large mismatch to default cached `CameraData`; camera config was unchanged and R16 remains open.
- 2026-07-22 21:35 HKT - `335L_POSE_SWEEP_COMPLETE`: eval-only 16-env seed0 stage1–4 sweep used crop-derived nominal intrinsics and the sealed `base_v13_A` Teacher; same-step pose/readback/render/intrinsics/physics gates passed and `z_low_020` ranked first. This is preserved as historical evidence, not a current default or physical mount.
- 2026-07-22 23:41 HKT - `V16B_335L_STAGE1_5_SWEEP_COMPLETE`: clean pinned mainline `base_v16_B` eval completed 16 episodes with `15/16 goal`; exact stage1–5 ranking selected `x_near_028`, all eight candidate MP4s covered stages1–5 and decoded fully, and manual QA exposed universal stage5 visibility collapse. `x_near_028` is only the next-search center; no candidate was accepted as final simulation or physical camera.
- 2026-07-23 18:06 HKT - `SCHEME_C_RUNTIME_PASS_VISIBILITY_PARTIAL`: centered `y=0,yaw=0` portrait D435i + provisional A2 Head high-level sensors passed same-render/intrinsic/pose/no-physics-advance gates; formal 16-env videos decoded and showed strong stage3–4 union visibility but only `10.25%/3.22%` stage5 union handle/trio visibility. Cloud right-offset/inward-yaw advice is rejected; no full-task camera or physical mount claim.

## Recommended Next Files To Read

- `memory/a2-piper/phase2-student-distillation-a2-piper/TODO.md`
- `gr00t/rl/scripts/README.md`
- `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`
- `gr00t/rl/scripts/validate_a2_teacher_checkpoint.py`
