---
name: phase2-student-distillation-a2-piper
scope: DoorDog-A2_Piper-only Phase2 Student Distillation / DAgger vision policy
status: TRAINING_PASS / R14_RESOLVED / 335L_POSE_SWEEP_COMPLETE
last_updated: 2026-07-22 21:35 HKT
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

Status at 2026-07-22 21:35 HKT: `TRAINING_PASS / R14_RESOLVED / 335L_POSE_SWEEP_COMPLETE`。DoorDog-A2_Piper 在本 entry 中只按 A2+Piper route 处理；final accepted training goal 已收窄为一次真实的 Student Distillation update 并产生新的 Student checkpoint。该训练目标已经完成，不是仅 `STATIC PASS`；后续单 camera pose sweep 只做 Teacher eval diagnostic，没有训练。

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

## Gemini 335L Single-camera Pose Sweep

2026-07-22 在 GPU0 完成 eval-only、16-env、seed0 的 centered Gemini 335L pose sweep；没有调用 trainer。source Teacher 为 `logs_rl/a2_piper_student_distillation_v13_A_teacher-20260717_2103/model_step_003000.pt`，SHA256 `d576ca4bc6f596e45a8d744ca766164b374f8aba4409b06bcd7c460d6b057a36`；wrapper 将 checkpoint/config 复制到 fresh output 的 `_eval_input` 后再次验证相同 hash，避免 eval 写 sealed source。sealed summary 为 `/tmp/a2_camera_pose_sweep_16env_seed0_20260722/camera_pose_sweep_summary.json`，共 `248` sample events。

- Intrinsics 由 Gemini 335L nominal `94°H×68°V`、centered `1280×800 -> 1280×720 -> 384×216` 推导。spec 值 `[fx,fy,cx,cy]=[179.0428965384,177.9073162215,192,108]`；pinned IsaacLab square-pixel projection 使用 `[179.0428965384,179.0428965384,192,108]`，`fy` 差 `+1.1355803169 px`，不是 physical calibration。
- sweep 复用一个现有 `TiledCamera` 和其 view；candidate local pose 以 OpenGL convention 用 `set_local_poses/get_local_poses` 闭合。每个 candidate 都在同一 physics step `sim.render()` + `camera.update(dt=0, force_recompute=True)`；physics counter 未前进，RGB/raw instance segmentation 对 control 与 search 不全同，runtime intrinsic error 为 `0`。
- stage1-4 diagnostic score 以 handle `0.35`、handle+both fingers `0.35`、door panel `0.15`、handle centered `0.15` 加权。推荐 `z_low_020`：trunk local position `[0.32,0,0.20]m`，RPY `[0,-6,0]°`，quaternion `[0.9986295348,0,-0.0523359562,0] wxyz`，score `0.9230179028`；四项 rate 为 `0.9697357204/0.8729752771/0.9799658994/0.8738277920`。原 `[0.32,0,0.25]` center seed 排第四；legacy control score `0`。
- 该结果只把 `z_low_020` 设为当前 right/out simulation search default，不冻结 physical mount，不证明 mirrored left/out、calibrated intrinsics/extrinsics、vibration/exposure/latency/depth、cable/thermal/mechanical clearance，也不修改 production Student camera config/observation。

## Historical Failure Facts and Deferred Work

R13 `FAIL_TIMEOUT`, R14 `FAIL_FINAL_SEAL`, and R15 `FAIL_EVIDENCE_SERIALIZATION` remain reusable lifecycle/evidence facts; none was a training PASS. R15 specifically exposed strict JSON serialization of `torch.__version__` as `torch.torch_version.TorchVersion`, before an `evidence.json` seal. They are superseded as blockers for the accepted one-update goal, not erased.

G1 compatibility/regression, R16 lifecycle perfection, final physical camera mount and mirrored left/right validation, randomization, multi-seed validation, Student eval, ONNX/export, policy quality, and open-door success are deferred and non-gates for this completed scope. The right/out simulation pose search is complete but does not close those items. They must be separately approved and validated before any future claim about those outcomes.

## TODO Summary

- 2026-07-15 17:17 HKT - Current accepted one-update A2+Piper Student Distillation goal is complete at `TRAINING_PASS`; optional future tuning/validation is non-blocking and requires separate scope/approval.
- 2026-07-22 21:35 HKT - R14 transform root cause and the bounded right/out 335L simulation pose sweep are complete; final physical mount plus mirrored left/right validation remain separately deferred.

## DONE Summary

- 2026-07-13 22:28 HKT - Static A2+Piper Phase2 Student Distillation framework completed and statically reviewed; runtime/training remained INCONCLUSIVE at that time.
- 2026-07-14 23:21 HKT - Immutable non-`last.pt` Teacher checkpoint/config/manifest triplet sealed and identity-validated; this alone did not claim Teacher runtime load.
- 2026-07-14/15 HKT - R13/R14/R15 camera/lifecycle attempts recorded `FAIL_TIMEOUT` / `FAIL_FINAL_SEAL` / `FAIL_EVIDENCE_SERIALIZATION`; these are preserved historical lifecycle facts, not training success.
- 2026-07-15 17:17 HKT - `TRAINING_PASS`: one real GPU0 Student Distillation update completed and sealed as `model_step_000001.pt`; lifecycle cleanup and independent strict reconstruction limitations are explicitly bounded above.
- 2026-07-22 15:36 HKT - `R14_STALE_INITIALIZATION_POSE_CONFIRMED`: same-step GPU probe closed parent/local-offset/live-camera transforms and isolated the large mismatch to default cached `CameraData`; camera config was unchanged and R16 remains open.
- 2026-07-22 21:35 HKT - `335L_POSE_SWEEP_COMPLETE`: eval-only 16-env seed0 sweep used crop-derived nominal intrinsics and the sealed `base_v13_A` Teacher; same-step pose/readback/render/intrinsics/physics gates passed and `z_low_020` ranked first. This is a right/out simulation default, not physical mount or mirrored validation.

## Recommended Next Files To Read

- `memory/a2-piper/phase2-student-distillation-a2-piper/TODO.md`
- `gr00t/rl/scripts/README.md`
- `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`
- `gr00t/rl/scripts/validate_a2_teacher_checkpoint.py`
