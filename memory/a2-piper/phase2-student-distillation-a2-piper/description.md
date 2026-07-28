---
name: phase2-student-distillation-a2-piper
scope: DoorDog-A2_Piper-only Phase2 Student Distillation / DAgger vision policy
status: TRAINING_PASS / R14_RESOLVED / V16B_335L_STAGE1_5_SWEEP_COMPLETE / SCHEME_C_RUNTIME_PASS_VISIBILITY_PARTIAL / SCHEME_C_B_LOWPROFILE_RUNTIME_SMOKE_PASS / V16_CB_STUDENT_ONE_UPDATE_PASS / V16_CB_GPU7_CAPACITY_STABILITY_PASS
last_updated: 2026-07-28 23:06 HKT
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

Status at 2026-07-28 23:06 HKT: `TRAINING_PASS / R14_RESOLVED / V16B_335L_STAGE1_5_SWEEP_COMPLETE / SCHEME_C_RUNTIME_PASS_VISIBILITY_PARTIAL / SCHEME_C_B_LOWPROFILE_RUNTIME_SMOKE_PASS / V16_CB_STUDENT_ONE_UPDATE_PASS / V16_CB_GPU7_CAPACITY_STABILITY_PASS`。DoorDog-A2_Piper 在本 entry 中只按 A2+Piper route 处理；final accepted training goal 已收窄为真实 Student Distillation update 与 bounded capacity/stability pilot，并产生新的 Student checkpoint。原 one-update、C-B v16 one-update 与本次 GPU7 10-batch pilot 都是真实训练完成，不是仅 `STATIC PASS`；camera sweep 和 Scheme C 双视角验证仍只作 Teacher eval diagnostic，没有训练。

Frozen product candidate 为 `90164b26bece1623e6c4a2dfe32769a4af72c2ed5f2efc80857ba9e82d6691cf`；code-quality 与 IsaacLab semantics review 均 PASS，targeted static test 为 `25 passed`。Teacher immutable triplet 已 sealed：checkpoint `logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459/model_step_001000.pt` SHA256 `40939c4af4e9744dfbc9d21315adcb59d01fbad80c1a3e8b480277aa2d463523`；saved config `logs_rl/a2_piper_full_stage_a2_base/base_v10_D_scratch_hold_reward_kp160_base-20260713_174459/config.yaml` SHA256 `3ba6e8a35c2659807acbd43adeae1871bc02d033f4578690a5eb3e4b37bffa77`；manifest `logs_rl/a2_piper_student_distillation_runtime/base_v10_D_teacher-20260714_144359/teacher_manifest.json` SHA256 `c22f0648ca4225cc0d1f44159df0beea4300509eb7eaad0e7c1ff71cd384cadc`。

## Implemented Training Contract

- Student deployable contract：legacy 单路为 `81D proprio + RGB(248832D) -> 12D high-level action`，current C-B 为 `81D proprio + RGB(497664D) -> 12D high-level action`；Teacher actor `133D -> 12D`，optional critic `138D`；frozen A2_Base `1620D -> 12D` leg action。
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

## Scheme C-B: Landscape D435i Up60 + Provisional A2 Head

2026-07-23 20:48 HKT 在 GPU0 用 sealed `base_v16_B` checkpoint 与 clean pinned runtime `815b367f5de2a52b26a4b872d0457af8817d01bd` 完成一次 eval-only、2-env C-B runtime smoke；没有 retry 或 training，进程自然退出 `0`。C-B 保持 D435i trunk local `[0.28,0,0.25]m`、`y=0,yaw=0`、landscape `384×216`，仅把 pitch 改为 `-60°`（wxyz `[0.8660254037844386,0,-0.5,0]`）；A2 Head 继续使用 Scheme C 的 provisional 参数。

- 两个 env 都以 `goal=true / max_stage=5 / complete` 结束；env1 视频 stage0–5 帧数为 `20/10/12/19/53/43`。双 sensor 在同一次 render 后更新，`physics_advanced_between_views=false`，runtime intrinsics error `0px`。
- combined env1 MP4 为 `768×216@10fps`、`157` 帧，SHA256 `0fc26356823fc168adb0efbd92de4ea29ed5aa8a47ed424fc52f2c4f12cab626`；D435i 与 Head 单路视频也均 `157/157` 帧 end-to-end decode PASS。sealed summary 位于 `logs_eval/a2_piper_camera_scheme_c_b_up60_v16_env1-20260723/camera_pose_sweep_summary.json`。
- 结论仅为 `SCHEME_C_B_RUNTIME_SMOKE_PASS`：没有 16-env formal、training、mirrored left/out、physical mount/CAD/calibration 或真实 D435i latency/exposure 结论。A2 Head extrinsic 仍为 provisional；stage5 conservative-union handle+both-fingers 仅 `8/86`（`9.30%`），不升级为 camera hard-gate PASS。

### Superseding low-profile C-B revision

2026-07-24 20:13 HKT 按修订后的 C-B 定义直接覆盖同一 config identity：D435i 改为
trunk local `[0.260,0,0.215]m`，保持 landscape `384×216`、`y=0,yaw=0`、pitch
`-60°` 和 wxyz `[0.8660254037844386,0,-0.5,0]`。A2 Head 被固定为
`fixed_oem_context / optimize_pose=false`；其 `[0.32,0,0.25]m / -12°` 只保留为
历史 provisional 仿真外参，实机 OEM extrinsic 仍必须测量。

- GPU0 eval-only 2-env runtime 自然退出 `0`，2/2 env 均 `goal=true / max_stage=5`；
  Teacher/checkpoint/runtime identity 未变，`training_performed=false`。
- env1 combined/D435i/Head 三段视频均为 `157` 帧并 end-to-end decode PASS；combined
  `768×216@10fps` SHA256 为
  `c02bccd372ad36c17382388e2fd0934236d251884dbf58f43c3ec3781eafbb62`。
- same-render gates 为 `physics_advanced_between_views=false`、pose/readback 与 render
  diversity PASS、runtime intrinsic error `0px`。sealed summary 位于
  `logs_eval/a2_piper_camera_scheme_c_b_lowprofile_v16_env1-20260724/camera_pose_sweep_summary.json`。
- 结论为 `SCHEME_C_B_LOWPROFILE_RUNTIME_SMOKE_PASS`，只取代当前 C-B config/render
  identity，不抹除旧 `[0.28,0,0.25]m` provenance。mechanical/CAD clearance、
  mirrored left/out、A2 Head OEM extrinsic、real-camera calibration/latency/exposure
  仍未验证。

## C-B v16 Student One-update

2026-07-28 20:58 HKT，frozen product candidate `5b3f496b10271890a8fa0557ef984577f9f2d5afe368bbdb9cd63b51a2259173` 在基线 `d9077fb4bcc8c68134f74cd68b860751f5603dbb` 完成 `V16_CB_STUDENT_ONE_UPDATE_PASS`。C-B contract 固定为 D435i `[0.26,0,0.215]m`、wxyz `[0.8660254037844386,0,-0.5,0]`、`384×216`，Head `[0.32,0,0.25]m`、wxyz `[0.9945218953682733,0,-0.10452846326765347,0]`、`384×136`，均保持 `y=0/yaw=0`；Head `40/40` letterbox，policy NHWC `(N,216,768,3)` / vision dim `497664`。

- v16 telemetry consumer 在 temporal meter 前消费 over-force optional ratio、crossing prepare/finalize 与八个 quantile sample/mask schemas；unknown Bool/Int 不被 coercion，且没有 `TensorAverageMeter` fallback。focused new `4 passed`、affected existing `7 passed`、full C-B + Student contract `129 passed`、diff check、CODE_QUALITY 与 ISAACLAB_FAIL_FAST static/no-sim 均 PASS。
- 一次 GPU0 retry3 launch 于 `20:50:09 HKT` 启动；required markers 各一次，Teacher `133→12`、Student/A2_Base/rollout `12/12/24`，iteration `1` 完成 `4` timesteps。pinned runtime `815b367f5de2a52b26a4b872d0457af8817d01bd` clean；Teacher checkpoint/config/manifest SHA256 分别为 `5628a25ee53395ddc581d2da184c32635e109ff3691e54a823ad054236475e3f`、`3c8aead9025b66a7f6f2ac3afc81bedc9cdafa1d12bd08fd43058eff8b4fd144`、`79157f10bff40a4c2f66f64a928dee442d856d505e967d6fb45a6539ecc877a1`。
- `logs_rl/a2_piper_student_distillation_v16_B_cb_smoke-20260728_1912_retry3/model_step_000001.pt` SHA256 `6fef5cd92210999b55d1d2130889870672334f69520fd4249ca35963f31ac288`，size `155659963` bytes，含 `142` finite policy tensors、optimizer state `78`、`global_step=1`；candidate、Teacher 与 pinned runtime hashes post-run 未变。
- `TRAINING_COMPLETION` 在 checkpoint 后 PASS；`simulation_app_close_start` 为 `20:52:08 HKT`。没有 `close_complete`：等待超过 `180s` 后仅向 owned PGID `1155351` 发送一次 `TERM`，无 `SIGKILL`，随后 process group 不存在且 GPU0 released。此 lifecycle separation 不削弱 checkpoint training result，也不构成 natural Kit shutdown PASS。

## GPU7 32-env Capacity/Stability Pilot

2026-07-28 23:06 HKT，GPU binding contract 升级为 `single-visible-logical-cuda0-v3`：`CUDA_VISIBLE_DEVICES` 与 `A2_EXPECTED_HOST_GPU_INDEX` 必须精确一致，expected UUID 必须同时匹配 host `nvidia-smi` 与进程内 Torch logical `cuda:0`；IsaacLab high-level `AppLauncher` 将 renderer `activeGpu` 绑定到 physical host GPU，同时把 CUDA/PhysX 保持在 logical GPU `0`。missing/mismatched schema、UUID、world size、logical index 或 Kit setting 均 fail fast，不存在 software fallback。Teacher deterministic recurrent rollout 的 `clear_rollout()` 同时修正为把 `distribution` 重置为 `None`，保留稳定成员 invariant；retry3 在 batch 2 暴露的第二次清理 `AttributeError` 由此关闭。完整 C-B + Student contract 为 `132 passed`，Python compile 与 scoped diff check PASS。

- retry4 使用 physical GPU7 UUID `GPU-7c8cb1d2-4ebf-e2e3-35ad-fa0f6f72924d` / logical `cuda:0`、pinned v16 runtime `815b367f5de2a52b26a4b872d0457af8817d01bd`、`num_envs=32`、`num_steps_per_env=8`、`num_mini_batches=4`、`num_total_batches=10`、per-device batch `8`、save frequency `10`。Kit marker 为 `activeGpu=7` / `physics/cudaDevice=0`，GPU0 未承载 workload；Teacher `133→12`、C-B policy RGB `(32,216,768,3)`、Student/A2_Base/rollout `12/12/24` markers PASS，无 PhysX software fallback 或 UsdRT nonzero-CUDA error。
- 10/10 iterations 完成，`2560` timesteps、`320` episodes，trainer total time `40.34s`。checkpoint `logs_rl/a2_piper_student_distillation_v16_B_cb_capacity_gpu7_32env_10batch-20260728_222446-retry4_bound_physical7_logical0_lifecycle/model_step_000010.pt` SHA256 `b8f681a18a28394e4b3d03281f8d2cb8c9874a5f40fbbeb0c0173f1aedf9786b`，size `155663227` bytes；CPU load 得到 `global_step=max_steps=10`、episode `320`，递归检查 `543` tensors / `513` floating tensors 全 finite（policy/value/optimizer tensors `142/19/234`）。
- 1-second telemetry 共 `345` samples/GPU，覆盖 startup、training 与 stuck close；GPU7 peak 为 `18241 MiB`、`100%` utilization、`255.87W`、`64°C`，GPU0 peak 仅 `2 MiB`。这证明 1× A6000 48GB 对该 pilot 有约 `30.2 GiB` nominal VRAM headroom，但不是更大 env count 的容量保证。
- 训练完成与 checkpoint 保存 PASS；natural Kit shutdown 未 PASS。`[A2_LIFECYCLE] simulation_app_close_start` 后超过 `180s` 无 close-complete，GPU7 仍约 `8.2 GiB/60–70%`；只 TERM exact owned training PID `1216700` 与 telemetry PID，未用 SIGKILL，随后 GPU0/GPU7 均回到 `1 MiB/0%`。该 lifecycle issue 继续作为独立 R16 TODO，不否定 10-batch training/capacity evidence，也不得宣称 clean process exit。

## Historical Failure Facts and Deferred Work

R13 `FAIL_TIMEOUT`, R14 `FAIL_FINAL_SEAL`, and R15 `FAIL_EVIDENCE_SERIALIZATION` remain reusable lifecycle/evidence facts; none was a training PASS. R15 specifically exposed strict JSON serialization of `torch.__version__` as `torch.torch_version.TorchVersion`, before an `evidence.json` seal. They are superseded as blockers for the accepted one-update goal, not erased.

G1 compatibility/regression, R16 lifecycle perfection, final physical camera mount and mirrored left/right validation, randomization, multi-seed validation, Student eval, ONNX/export, policy quality, and open-door success are deferred and non-gates for the completed training scope. The bounded v16 stage1–5 sweep and Scheme C prototype are complete, but both confirm that fixed forward trunk views lose the handle after passage. A full-task design still needs a distinct stage5-aware viewpoint or an explicit observation requirement that stops needing the handle after release. These items must be separately approved and validated before any future claim about those outcomes.

## TODO Summary

- 2026-07-15 17:17 HKT - Current accepted one-update A2+Piper Student Distillation goal is complete at `TRAINING_PASS`; optional future tuning/validation is non-blocking and requires separate scope/approval.
- 2026-07-22 21:35 HKT - R14 transform root cause and the historical `base_v13_A` stage1–4 sweep are complete.
- 2026-07-22 23:41 HKT - `base_v16_B` stage1–5 sweep and all eight candidate videos are complete; `x_near_028` is only the next search center because stage5 visibility collapses, while final right/out pose, physical mount and mirrored left/right remain deferred.
- 2026-07-23 18:06 HKT - Symmetric Scheme C portrait D435i + provisional A2 Head eval is complete; runtime/synchronization/video gates passed, stage3–4 visibility improved, but stage5 remains a documented visibility failure and final hardware/mirrored validation stays deferred.

- 2026-07-23 20:48 HKT - C-B landscape D435i up60 + provisional A2 Head 的 2-env runtime smoke 与 env1 三路视频已完成；该证据不关闭 final physical mount、mirrored left/out 或 stage5-aware view TODO。
- 2026-07-24 20:13 HKT - 当前 C-B 已由 low-profile `[0.260,0,0.215]m` revision 与新 env1 三路视频取代；A2 Head 仍为固定 OEM context role，但仿真外参只属 historical provisional，physical clearance 和 OEM extrinsic 继续开放。
- 2026-07-28 20:58 HKT - `V16_CB_STUDENT_ONE_UPDATE_PASS`: C-B v16 telemetry compatibility 与一次 GPU0 retry3 Student update 已完成并产生 `global_step=1` checkpoint；自然 Kit close 未 PASS 不阻塞 training completion，formal/long training 仍未运行。
- 2026-07-28 23:06 HKT - `V16_CB_GPU7_CAPACITY_STABILITY_PASS`: physical GPU7 / logical `cuda:0` binding、recurrent Teacher repeated cleanup 与 32-env/10-batch pilot 已通过；checkpoint `global_step=10` 可加载且 finite，GPU7 peak `18241 MiB`，GPU0 peak `2 MiB`。Natural Kit close 仍未 PASS，正式 longer-scale/multi-seed training 仍未运行。
## DONE Summary

- 2026-07-13 22:28 HKT - Static A2+Piper Phase2 Student Distillation framework completed and statically reviewed; runtime/training remained INCONCLUSIVE at that time.
- 2026-07-14 23:21 HKT - Immutable non-`last.pt` Teacher checkpoint/config/manifest triplet sealed and identity-validated; this alone did not claim Teacher runtime load.
- 2026-07-14/15 HKT - R13/R14/R15 camera/lifecycle attempts recorded `FAIL_TIMEOUT` / `FAIL_FINAL_SEAL` / `FAIL_EVIDENCE_SERIALIZATION`; these are preserved historical lifecycle facts, not training success.
- 2026-07-15 17:17 HKT - `TRAINING_PASS`: one real GPU0 Student Distillation update completed and sealed as `model_step_000001.pt`; lifecycle cleanup and independent strict reconstruction limitations are explicitly bounded above.
- 2026-07-22 15:36 HKT - `R14_STALE_INITIALIZATION_POSE_CONFIRMED`: same-step GPU probe closed parent/local-offset/live-camera transforms and isolated the large mismatch to default cached `CameraData`; camera config was unchanged and R16 remains open.
- 2026-07-22 21:35 HKT - `335L_POSE_SWEEP_COMPLETE`: eval-only 16-env seed0 stage1–4 sweep used crop-derived nominal intrinsics and the sealed `base_v13_A` Teacher; same-step pose/readback/render/intrinsics/physics gates passed and `z_low_020` ranked first. This is preserved as historical evidence, not a current default or physical mount.
- 2026-07-22 23:41 HKT - `V16B_335L_STAGE1_5_SWEEP_COMPLETE`: clean pinned mainline `base_v16_B` eval completed 16 episodes with `15/16 goal`; exact stage1–5 ranking selected `x_near_028`, all eight candidate MP4s covered stages1–5 and decoded fully, and manual QA exposed universal stage5 visibility collapse. `x_near_028` is only the next-search center; no candidate was accepted as final simulation or physical camera.
- 2026-07-23 18:06 HKT - `SCHEME_C_RUNTIME_PASS_VISIBILITY_PARTIAL`: centered `y=0,yaw=0` portrait D435i + provisional A2 Head high-level sensors passed same-render/intrinsic/pose/no-physics-advance gates; formal 16-env videos decoded and showed strong stage3–4 union visibility but only `10.25%/3.22%` stage5 union handle/trio visibility. Cloud right-offset/inward-yaw advice is rejected; no full-task camera or physical mount claim.

- 2026-07-23 20:48 HKT - `SCHEME_C_B_RUNTIME_SMOKE_PASS`: centered landscape D435i up60 + unchanged provisional A2 Head 通过 eval-only same-render/intrinsics/video decode 门；2/2 Teacher episodes complete，combined env1 为 157 帧，但没有 16-env formal 或 physical-camera claim。
- 2026-07-24 20:13 HKT - `SCHEME_C_B_LOWPROFILE_RUNTIME_SMOKE_PASS`: 同一 C-B config 直接改为 D435i `[0.260,0,0.215]m`，保留 `y=0/yaw=0/pitch=-60°`；2/2 Teacher episodes complete，三段 env1 MP4 各 157 帧并完整解码，未训练。A2 Head OEM extrinsic 与 mechanical clearance 未验证。
- 2026-07-28 20:58 HKT - `V16_CB_STUDENT_ONE_UPDATE_PASS`: frozen candidate `5b3f496b10271890a8fa0557ef984577f9f2d5afe368bbdb9cd63b51a2259173` 完成 C-B v16 Student one-update。C-B D435i/Head 固定为 `[0.26,0,0.215]m` + up60 `384×216` / `[0.32,0,0.25]m` + `384×136`，`y=0/yaw=0`、Head `40/40` letterbox 与 NHWC `(N,216,768,3)`/vision dim `497664` contract 一致；v16 telemetry schema 消费、unknown Bool/Int fail-fast 与无 `TensorAverageMeter` fallback 已由 static gates 覆盖（new `4 passed`、affected `7 passed`、full `129 passed`、diff/CODE_QUALITY/ISAACLAB_FAIL_FAST PASS）。唯一 GPU0 retry3 launch 于 `20:50:09 HKT` 产生一次 required-marker set，Teacher `133→12`、Student/A2_Base/rollout `12/12/24`，iteration `1` / `4` timesteps；`model_step_000001.pt` SHA256 `6fef5cd92210999b55d1d2130889870672334f69520fd4249ca35963f31ac288`、`155659963` bytes、`142` finite policy tensors、optimizer state `78`、`global_step=1`。checkpoint 后 `TRAINING_COMPLETION PASS`；`simulation_app_close_start` 后无 `close_complete`，超过 `180s` 才对 owned PGID `1155351` 一次 TERM、无 SIGKILL，PGID 消失且 GPU0 released；故自然 Kit shutdown 未 PASS，但不否定 training completion。candidate/Teacher/pinned-runtime identity post-run 未变；formal/long training、physical camera、policy quality 与 multi-seed 均未声称。
- 2026-07-28 23:06 HKT - `V16_CB_GPU7_CAPACITY_STABILITY_PASS`: binding v3 将 physical renderer GPU7 映射到 process-local logical `cuda:0`/PhysX GPU0，并由 host/Torch UUID、Accelerate、AppLauncher/Carbonite markers fail-fast 验证；recurrent Teacher deterministic inference 的 repeated rollout cleanup 已修复。full contract `132 passed`。retry4 以 `32 env × 8 steps × 10 batches` 完成 `2560` timesteps / `320` episodes，trainer total `40.34s`；checkpoint `model_step_000010.pt` SHA256 `b8f681a18a28394e4b3d03281f8d2cb8c9874a5f40fbbeb0c0173f1aedf9786b`、`155663227` bytes、`global_step=10`，递归 tensor finite PASS。GPU7 peak `18241 MiB/100%/255.87W/64°C`，GPU0 peak `2 MiB`。checkpoint 后 Kit close 超过 `180s` 未返回，exact PID TERM 后 GPU released；因此 training/capacity PASS，但 natural Kit shutdown 仍未 PASS。

## Recommended Next Files To Read

- `memory/a2-piper/phase2-student-distillation-a2-piper/TODO.md`
- `gr00t/rl/scripts/README.md`
- `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`
- `gr00t/rl/scripts/validate_a2_teacher_checkpoint.py`
