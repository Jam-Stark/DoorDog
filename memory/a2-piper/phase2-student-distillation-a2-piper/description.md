---
name: phase2-student-distillation-a2-piper
scope: DoorDog-A2_Piper-only Phase2 Student Distillation / DAgger vision policy
status: TRAINING_PASS / R14_RESOLVED / V16B_335L_STAGE1_5_SWEEP_COMPLETE / SCHEME_C_RUNTIME_PASS_VISIBILITY_PARTIAL / SCHEME_C_B_LOWPROFILE_RUNTIME_SMOKE_PASS / V16_CB_STUDENT_ONE_UPDATE_PASS / V16_CB_GPU7_CAPACITY_STABILITY_PASS / C_B2_SENSORS_RUNTIME_PASS_PANORAMA_VISUAL_FAIL / C_B2_TOEIN20_RENDER_COMPLETE_PANORAMA_VISUAL_FAIL / C_B2H_DUALRAW_64E_ADMISSION_PASS / C_B2H_FORMAL_10K_CHECKPOINT_COMPLETE / C_B2H_STUDENT_EVAL_RUNTIME_PASS_POLICY_QUALITY_FAIL / C_B2H_RENDER_BEST_ONLY_COMPLETE / C_B2H_TOEOUT6_TRUE_TEACHER_STAGE0_DIAG_COMPLETE / C_B2H_TOEOUT6_G2_STAGE0_CONTRACT_RUNTIME_PASS / C_B2H_G2_MULTISEED_STAGE2_DIAG_COMPLETE / C_B2H_LIFECYCLE_UNRESOLVED
last_updated: 2026-08-09 11:05 HKT
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

Status at 2026-08-09 11:05 HKT: `TRAINING_PASS / R14_RESOLVED / V16B_335L_STAGE1_5_SWEEP_COMPLETE / SCHEME_C_RUNTIME_PASS_VISIBILITY_PARTIAL / SCHEME_C_B_LOWPROFILE_RUNTIME_SMOKE_PASS / V16_CB_STUDENT_ONE_UPDATE_PASS / V16_CB_GPU7_CAPACITY_STABILITY_PASS / C_B2_SENSORS_RUNTIME_PASS_PANORAMA_VISUAL_FAIL / C_B2_TOEIN20_RENDER_COMPLETE_PANORAMA_VISUAL_FAIL / C_B2H_DUALRAW_64E_ADMISSION_PASS / C_B2H_FORMAL_10K_CHECKPOINT_COMPLETE / C_B2H_STUDENT_EVAL_RUNTIME_PASS_POLICY_QUALITY_FAIL / C_B2H_RENDER_BEST_ONLY_COMPLETE / C_B2H_TOEOUT6_TRUE_TEACHER_STAGE0_DIAG_COMPLETE / C_B2H_TOEOUT6_G2_STAGE0_CONTRACT_RUNTIME_PASS / C_B2H_G2_MULTISEED_STAGE2_DIAG_COMPLETE / C_B2H_LIFECYCLE_UNRESOLVED`。DoorDog-A2_Piper 在本 entry 中只按 A2+Piper route 处理；原 one-update、C-B v16 one-update、GPU7 10-batch pilot 与 C-B2H 64-env admission 都有真实 training update 证据，不是仅 `STATIC PASS`。旧 c18/10k seed0 quality FAIL 保留为历史 context。ToeOut6/pitch−50° fixed-G2 true Teacher seed0/1 为 `32/32`；formal pure Student seed0/1/2 为 `13/16`、`16/16`、`13/16`，合计 `42/48 = 87.5%`。seed0 failures `{4,6,9}` 与 seed2 `{8,12,14}` 无交集，matched Stage2 diagnosis 已关闭 contract-drift/handle-visibility 假设，支持 intermittent Student bilateral contact/squeeze-continuity robustness。上述正式结果只覆盖这些 seed、16 env、每 env 一 episode；same-seed replay 仍会变化，不能外推为 determinism、general/deployment 或 physical-camera PASS。旧 `controller=teacher` 结果实际绕过 Teacher `policy_step` 并执行 Student rollout，故其 `8/16` 和“完全相同失败集合”结论无效且已 superseded。camera sweep、Scheme C 与 C-B2 验证仍只作 Teacher eval diagnostic。C-B2 两个 panorama仍因重影、撕裂和空洞保持视觉 FAIL。

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

## C-B2H Dual-Raw 64-env Admission

2026-07-31 03:47 HKT，frozen product candidate `09cd8551eef0748da8622599dda0f9be9d7f34980442fe7b3622aeebe808cc56`（base `57b8eda3d500d5778eb9394d7fbc49c5aa3b8a63`）完成 `C_B2H_DUALRAW_64E_ADMISSION_PASS`。policy 输入为 paired D435 RGB raw `384×216@30Hz` 与 independent OEM Head `384×136@15Hz`：D435 shared encoder 对左右流调用两次，Head 使用 separate encoder，fusion 后进入 recurrent 12D Student。exact launch contract 固定为 physical GPU7 / logical `cuda:0`、`num_envs=64`、`num_total_batches=10000`；focused full test `13 passed`，CODE_QUALITY 与 IsaacLab reviews PASS。

- Teacher 固定为 `base_v19_G2_norm_control-20260727_012027/model_step_002000.pt`，checkpoint/config/manifest SHA256 分别为 `b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d`、`65c1537b38d670097bc8498428e0aad1705c3fd66eeef41a93d63e3b6da4cf96`、`479f4460d4dc05feea9d87d3189fa0617b21078f91b6f5176f4a9c41b141d1b7`。clean commit `c18aea8bdc1c76ce850b5223663d0ad8a7474c0a` 是明确标注的 v19 runtime reconstruction，不是原 W&B commit；dual-source launch 由 candidate 提供 Student/trainer/config/entrypoint，由 c18 提供 runtime triplet 与 scenario pin。
- exact 128-env GPU7 attempt 已通过 source/GPU/Teacher/M39/camera startup，但在 optimizer 前 OOM；5-second telemetry peak 为 `47959 MiB`，没有 checkpoint，不能记为容量或训练 PASS，也不能把 sampled peak 解释为安全余量。
- exact 64-env admission 完成真实 `global_step=1 / episode=64`。checkpoint `logs_rl/cb2h_v19_runtime/admission_64e_candidate_09cd8551/model_step_000001.pt` 为 `294254843` bytes，SHA256 `0ebbef5542550e19852fd8e04d8e444cf5947fcb0ad0e59ecf28d097e20bbaed`；CPU structural load 得到 policy `293` entries、value `19` entries、optimizer groups/state 与 `max_steps=10000`。GPU7 peak `31146 MiB`，没有 OOM、fallback 或 alternate GPU；candidate/c18 postflight unchanged，owned admission session 已清理。该证据不证明 sustained 10,000-batch stability、final checkpoint、model quality 或 eval。

## C-B2H Formal R1 Partial-Prime Failure and Static Fix

2026-07-31 的第一次 exact GPU7 / 64-env / 10,000-batch fresh formal run 完成至 iteration 72，随后在下一次 rollout 前以 `C-B2H head camera.frame advanced for non-target environments: [14, 45]` 失败。根因是 public IsaacLab `Camera.data` 的 lazy refresh 会更新所有已经 outdated 的 env row；target-only reset prime 读取 data 时，已到期的 non-target row 合法递增 frame，而 `TiledCamera` 会重写完整 tiled output。旧 code 把这个 public API 行为误判为 corruption；它不是 OOM、Teacher provenance、c18 runtime reconstruction 或 GPU binding 问题。

- frozen fix candidate `f41147ea-5427954a-fbfb1142` 只移除 false non-target frame-advance rejection；required target advancement、D435 left/right frame 与 advancement-mask equality、以及 target-masked policy cache/history/metadata/validity/cadence 均继续 fail fast。
- regression 将 non-target fake row 标记为 outdated，验证 partial prime 时三路 raw frame 可由 `1→2`，但 consumer state 不变；之后 normal scheduled capture 正常提交最新 frame `3`。targeted `1 passed / 12 deselected`、focused file `13 passed`、`py_compile`、diff check、CODE_QUALITY 与 IsaacLab review PASS。
- 这些只是 static/no-sim evidence。failed tmux/process 已结束，用户明确要求的 exact failed output directory 已永久删除；不得把 iteration 72 之前的进展、已删除的 `last.pt` 或本修复扩张成 sustained runtime/final completion PASS。
- fresh retry 使用 committed candidate `0f9c11ecc94204b1acc13b544c2c4dd44ae9910a`、exact c18/G2 step2000、physical GPU7/logical0、64 env、10,000 batches、save500，从 step0 启动。该历史交接时 live iteration 为 `86`、timesteps `44032`、episodes `5504`，已越过旧 failure boundary；错误扫描无旧 non-target signature、Traceback、RuntimeError 或 OOM。fresh `last.pt` 在 global_step `50` CPU load PASS：policy/value entries `293/19`、optimizer state present，SHA256 `c8445ba0e46444b73c0fdc6f3a735c9963578ffb3f80b8ffb68a1f3df6cc703f`；GPU7 observed peak `30505 MiB`。该记录仅是当时 live progress，已由后续 10,000-step completion 取代。

## C-B2H Formal 10k Completion, Student Eval, and Best-only Render

2026-08-02 05:00 HKT，exact G2 step2000 Teacher + c18 reconstruction 的 physical GPU7 / logical `cuda:0`、64-env run 已产出 `model_step_010000.pt`。该 checkpoint SHA256 为 `005705dc033605a24bc231b18fbfaabe3288a699130a7ce2e423eac736963a45`、size `294256699` bytes；同目录 config SHA256 为 `24f94faeca0270928c9c3ff33568e50371dc4f2f3feb767f6fe0607bb084351f`。这关闭 10,000-step checkpoint completion，不构成 natural Kit shutdown、multi-seed stability 或 open-door policy success。

- formal Student-only eval 在 GPU7、16 env、seed0、每 env 一 episode 完成；metrics `formal_student_metrics.json` SHA256 `86ab7f5cdb53b8e3253adaec85a730cd5c9a14f7b309c8a10c38e4a6d0ccaa1d`，canonical selection SHA256 `8865b6989b4e9aaea1df5b1cd0dfcd36736fd312a83473a02d622cc7b185d4de`。protocol/runtime artifacts PASS，但 quality verdict 为 poor/FAIL：`0/16 goal`，max-stage counts `{0:12,1:2,3:2}`，所有 episode 为 `stage_overtime`，mean reward `-174.89537`。
- canonical ranking 选中 env13 episode0，formal outcome 为 stage3、reward `-214.9512176513672`、goal false；其 randomized case 已 seal。三次 independent sequential GPU7 replay 都保持该 case identity，但都 drift 到 stage1/goal false/`stage_overtime`；reward 依次为 `-251.338623046875`、`-252.15257263183594`、`-254.18408203125`。ranking `goal desc → stage desc → reward desc → trial_id asc` 只保留 trial01；其 schema v2 metadata SHA256 为 `8df913f9acf3608daa5c9c4c2ac38fe839ee7324eb3168d92d9d8c33247a313c`。
- retained trial01 有 6 段视频，hash/size 与 metadata 一致并 full decode PASS：3 段 policy video 各 `351` frames / `20fps`，3 段 external video 各 `352` frames / `20fps`。non-best trial02/trial03 和两个旧 failed render target sets 已移入系统 Trash；保留 trial01 runtime/log。该 replay drift 是被 runner 显式记录的 formal-vs-replay outcome difference，不得宣称 same-seed replay bitwise deterministic。
- frozen source candidate `0f5ca9fe8e0a4afcc08c6148e4735aba3c5cd6693c08e8c2d493f0abdb94d8a7` 的 code-quality 与 IsaacLab reviews PASS，focused runner tests `23 passed`；runtime artifact QA 为 `NO_SIM_PASS`。runner canonical binding 了 hash-validated formal ranking，且 fail-fast 保持 exact case identity。以上 product/review evidence 不改变 policy-quality FAIL 或未解决 lifecycle 边界。

## C-B2 Dual-Portrait D435i + OEM A2 Head

2026-07-30 15:29 HKT，新增独立 `C-B2-DUAL-PORTRAIT-OEM` identity，没有覆盖 C-B。方案记录为 `gr00t/rl/config/camera_pose_sweep/C-B2-DUAL-PORTRAIT-OEM.md`；Hydra config 为 `d435i_dual_portrait_up60_a2_head_oem.yaml`。左右 D435i RGB optical center 分别固定为 `[0.215,+0.095,0.165]m / RPY [0,-60,-15]°` 与 `[0.215,-0.095,0.165]m / RPY [0,-60,+15]°`，使用修正后的 RGB FoV `69.4°H×42.5°V`、同向物理 portrait roll 与 software upright；nominal baseline `190mm`、toe-in `±15°`。A2 Head 使用 official Unitree URDF `camera_link` pose `[0.3381,+0.0336,0.0525]m / identity`，仍需真实 lens calibration。

- 两路 D435i 的 RGB + `distance_to_image_plane` 经固定 extrinsics 投影到 `416×384 / 72.5°H×69.4°V` cylindrical virtual camera。µm-quantized deterministic Z-buffer 选择最近 source；depth hole 只选一个 fixed-geometry raw view，绝不平均两路 RGB。A2 Head 保持独立 context stream，不参与 panorama。
- GPU0 eval-only 运行使用 sealed `base_v16_B` checkpoint SHA256 `5628a25ee53395ddc581d2da184c32635e109ff3691e54a823ad054236475e3f` 与 clean pinned runtime `815b367f5de2a52b26a4b872d0457af8817d01bd`；2/2 episodes 均 `goal_reached=true / final_stage=5 / complete`，`training_performed=false`。三相机 same-render frame delta max `0`、physics 未在 views 之间前进、runtime intrinsic max error `0px`。
- 左、右、OEM Head、panorama 与四段 process MP4 均为 `157` 帧、`10fps / 15.7s` 并 end-to-end decode PASS；process layout 为 `216×384 left | 216×384 right | 416×384 panorama | 384×384 letterboxed Head`，总尺寸 `1232×384`。panorama totals 为 valid input depth `9,869,736`、projected `9,743,472`、depth-fused output `6,328,805`、single-view fallback `12,989,567`、empty `5,761,436` pixels。
- conservative three-view union 的 all-stage handle/trio/panel rate 为 `74.09%/64.78%/77.08%`；stage1–4 handle 为 `100%`，但 stage5 handle/trio 只有 `9.30%/9.30%`。三相机 verdict 是 runtime PASS / visibility PARTIAL；panorama verdict 是 `VISUAL_FAIL`，因为第三栏存在明显重影、撕裂和空洞。它不是 stage5 hard-gate、physical mount、CAD interference、mirrored left/out、真实双机同步/标定或 production Student input PASS。sealed evidence 为 `logs_eval/a2_piper_camera_scheme_c_b2_v16_teacher_gpu0-20260730_151827/camera_pose_sweep_summary.json`。

### C-B2 TOEIN20 diagnostic ablation

2026-07-30 17:34 HKT，新增独立 `C-B2-DUAL-PORTRAIT-OEM-TOEIN20`，保留原 C-B2 ±15° identity、位置、baseline、pitch、intrinsics、RGB-D 与 OEM Head contract，仅将左右 yaw 改为 `-20°/+20°`。左右 wxyz 分别为 `[0.852868532,-0.086824089,-0.492403877,-0.150383733]` / `[0.852868532,+0.086824089,-0.492403877,+0.150383733]`；光轴夹角 `40°`，理论 overlap `2.5°`，panorama 扩展为 `474×384 / 82.5°H×69.4°V`。

- sealed `base_v16_B` GPU0 eval-only run 自然退出 `0`，2/2 episodes `goal_reached=true / final_stage=5 / complete`，`training_performed=false`；pair frame delta max `0`。
- 左、右、OEM Head、panorama 与 process MP4 均为 `157` 帧、`10fps / 15.7s` 并 end-to-end decode PASS；process layout 为 `216×384 | 216×384 | 474×384 | 384×384`，总尺寸 `1290×384`。
- panorama totals 为 valid input depth `9,770,648`、projected `9,597,643`、depth-fused `6,387,707`、fallback `14,449,088`、empty `7,739,717`。相较 ±15°，empty ratio 从 `22.97%` 升至 `27.08%`（`+4.11pp`），depth-fused ratio 从 `25.23%` 降至 `22.35%`。
- all-stage union handle/trio/panel 为 `73.75%/65.12%/77.08%`。人工 midpoint/视频 QA 仍见明显重影、撕裂和空洞；因此 verdict 为 `C_B2_TOEIN20_RENDER_COMPLETE_PANORAMA_VISUAL_FAIL`，只作为 wider-view comparison，不是拼接优化或 Student input candidate。sealed evidence 为 `logs_eval/a2_piper_camera_scheme_c_b2_toein20_v16_teacher_gpu0-20260730_172528/camera_pose_sweep_summary.json`。

## ToeOut6/pitch−50° Step8000 Stage0 Diagnostic

2026-08-08 23:30 HKT，current-worktree ToeOut6/pitch−50° step8000 Student 的 formal 16-env、one episode per env 三 seed baseline 保持 seed0 `8/16`、seed1 `12/16`、seed2 `9/16`，合计 `29/48` goal（`60.4%`）；终局为 Stage0 `16`、Stage2 `3`、Stage5 `29`，这不是 bitwise determinism claim。

- 旧 `controller=teacher` formal lane 是 mislabeled/invalid Teacher evidence：它绕过 Teacher `TRLDistillTrainerA2BaseAPI.policy_step` 并调用 Student rollout，因此旧的 Teacher `8/16` 与“完全相同失败集合”结论均已 superseded。
- 校正后的 true Teacher route 已 runtime-verified：provider 为 `TRLDistillTrainerA2BaseAPI.policy_step`，high-level source 为 `gt_actions`，Teacher ratio `1.0`，Teacher/exact-match steps 为 `688`、env count 为 `11008`，Student rollout calls 为 `0`，composed action 为 `24D`。同一 seed0/16 case 的 true Teacher 为 `10/16`；failures 仅为 Stage0 env `0,4,5,7,12,15`。Student seed0 是 `8/16`（Stage0 env `0,2,4,5,7,12,15`、Stage2 env `9`）；Teacher-only successes 是 env `2,9`。
- 六个 true Teacher Stage0 failures 都满足 arm condition，仅 `staging_distance < 0.1m` 未满足；均未到达 Stage1。final gate gaps 为 `2.53–12.08cm`，best-ever gaps 为 `0.55–9.18cm`；tail static metrics 显示 near-static attractor，而非 Stage1 pregrasp/alignment 或 streak failure。
- 全部 16 case 均已捕获 17-key door `customData`。单 seed、n=16 下没有任何一个维度可分离 six failures 与 ten successes；`hingeDriveMaxForce`、`doorHandleWidth` 仅是 leading hypotheses，仍为 inconclusive。
- `gr00t/rl/scripts/run_a2_toeout6_student_eval.py` 已具备 formal Teacher、multi-seed Student 与 validated arbitrary Student env render。上述当时的 Stage0 replication/directional-analysis 建议已由下列 sealed G2 Stage0 contract 结果取代；不要把旧 point-gate evidence 用于 Student retraining 或 global threshold relaxation。

## Sealed G2 Stage0 Contract and Matched Replays

2026-08-09 02:59 HKT，`C_B2H_TOEOUT6_G2_STAGE0_CONTRACT_RUNTIME_PASS` 完成。该 sealed G2 Stage0 contract 固定 `0.50 <= dx <= 0.80`、严格 `abs(dy) < 0.15`、arm deviation `<0.10` 与 physical base command norm `<=0.10`；legacy `a2_stage0_staging_x_offset=0.7` 只是 inert resolved-provenance residue，不参与 band predicate。此前 current-worktree point-gate true Teacher replay 为 `10/16`，其六个失败 env `0,4,5,7,12,15` 的各自 final 50 条 Stage0 records 全部已满足 G2-ready predicate，故该 point-gate evidence 不能代表 sealed contract 的终态行为。

- Candidate `G2-STAGE0-CONTRACT-R4-20260809` 只改变 env transition/reward/visual/trace，以及 runner 的 effective-config injection/validation；没有 observation、action 或 camera contract 变更。CODE_QUALITY 与 IsaacLab review 均 PASS。
- GPU4 fixed true Teacher replay（seed0、16 env、每 env 一 episode）为 `16/16`，全部 stage5 / `complete`；high-level action source 是 `gt_actions`，Teacher 为 `694` steps / `11104` env-actions，Student calls 为 `0`。该结果只验证这一个 matched seed0 replay，不是 multi-seed PASS。
- GPU5 matched pure Student replay（seed0、16 env、每 env 一 episode）由 point-gate 的 `8/16` 提升至 `13/16`；remaining failures 为 env `4,6,9`，均为 Stage2 `stage_overtime`。当时没有启动 Student finetune；下列 multi-seed/matched Stage2 diagnostic 已关闭 diagnosis scope，但不授权训练，不能声称 Student parity 或 broader policy-quality PASS。

## Fixed-G2 Multi-seed and Matched Stage2 Diagnostic Closure

2026-08-09 11:05 HKT，`C_B2H_G2_MULTISEED_STAGE2_DIAG_COMPLETE` 完成。fixed-G2 true Teacher seed0/1 均为 `16/16`，合计 `32/32`；formal pure Student seed0/1/2 分别为 `13/16`、`16/16`、`13/16`，合计 `42/48 = 87.5%`。seed0 failure set `{4,6,9}` 与 seed2 `{8,12,14}` 无交集，故目前不支持 stable hard-negative 或 fixed-case root-cause 解释。每一正式结果都只覆盖指定 seed、16 env、每 env 一 episode。

- Matched R4 Stage2 traces 使用相同 contract。env4 Student 的 maximum bilateral-contact/squeeze streak 为 `2`，而 Teacher 在 `t=160` 达到 required streak `5` 并完成 Stage2；Student env6/env9 则分别在 `t=108` / `t=219` 完成 Stage2。env4 同时存在 close command 与 physical stable close，说明支持的诊断是 intermittent Student bilateral contact / squeeze-continuity robustness，而不是 Stage2 contract drift、没有 close command 或夹爪不能物理闭合。
- same-seed evidence 不可视为 deterministic：formal/diagnose/render replay 已观察到 `13/16→14/16→15/16`，env9 formal success 还能在 render replay 变成 Stage2 `stage_overtime`。因此正式 batch 与单次 replay 必须保持不同证据角色。
- env4/env6/env9 D435 side-by-side inspection 中，handle 在左右两路均保持可见；抓取邻域只见 arm/gripper local self-occlusion，不支持把当前 Stage2 failure 归因于全局 handle visibility loss。此诊断不构成 physical-camera PASS。
- 不启动 full retrain 或 generic `1–2k` continuation。若后续需要 targeted Stage2 DAgger/contact-continuity finetune，必须先取得新的 approved `HIGH_RISK` brief，并以 formal multi-seed 与 repeated-replay acceptance 为 gate；本 closure 不授权训练。

## Historical Failure Facts and Deferred Work

R13 `FAIL_TIMEOUT`, R14 `FAIL_FINAL_SEAL`, and R15 `FAIL_EVIDENCE_SERIALIZATION` remain reusable lifecycle/evidence facts; none was a training PASS. R15 specifically exposed strict JSON serialization of `torch.__version__` as `torch.torch_version.TorchVersion`, before an `evidence.json` seal. They are superseded as blockers for the accepted one-update goal, not erased.

G1 compatibility/regression, R16 lifecycle perfection, final physical camera mount and mirrored left/right validation, randomization, multi-seed validation, recurrent ONNX/export, final policy-quality improvement, and open-door success remain deferred and non-gates for the completed checkpoint scope. Student-only eval is no longer unrun: its protocol/runtime artifacts passed but its `0/16` quality result is explicitly FAIL/poor. The bounded v16 stage1–5 sweep and Scheme C prototype are complete, but both confirm that fixed forward trunk views lose the handle after passage. A full-task design still needs a distinct stage5-aware viewpoint or an explicit observation requirement that stops needing the handle after release. These items must be separately approved and validated before any future claim about those outcomes.

## TODO Summary

- 2026-07-15 17:17 HKT - Current accepted one-update A2+Piper Student Distillation goal is complete at `TRAINING_PASS`; optional future tuning/validation is non-blocking and requires separate scope/approval.
- 2026-07-22 21:35 HKT - R14 transform root cause and the historical `base_v13_A` stage1–4 sweep are complete.
- 2026-07-22 23:41 HKT - `base_v16_B` stage1–5 sweep and all eight candidate videos are complete; `x_near_028` is only the next search center because stage5 visibility collapses, while final right/out pose, physical mount and mirrored left/right remain deferred.
- 2026-07-23 18:06 HKT - Symmetric Scheme C portrait D435i + provisional A2 Head eval is complete; runtime/synchronization/video gates passed, stage3–4 visibility improved, but stage5 remains a documented visibility failure and final hardware/mirrored validation stays deferred.

- 2026-07-23 20:48 HKT - C-B landscape D435i up60 + provisional A2 Head 的 2-env runtime smoke 与 env1 三路视频已完成；该证据不关闭 final physical mount、mirrored left/out 或 stage5-aware view TODO。
- 2026-07-24 20:13 HKT - 当前 C-B 已由 low-profile `[0.260,0,0.215]m` revision 与新 env1 三路视频取代；A2 Head 仍为固定 OEM context role，但仿真外参只属 historical provisional，physical clearance 和 OEM extrinsic 继续开放。
- 2026-07-28 20:58 HKT - `V16_CB_STUDENT_ONE_UPDATE_PASS`: C-B v16 telemetry compatibility 与一次 GPU0 retry3 Student update 已完成并产生 `global_step=1` checkpoint；自然 Kit close 未 PASS 不阻塞 training completion，formal/long training 仍未运行。
- 2026-07-28 23:06 HKT - `V16_CB_GPU7_CAPACITY_STABILITY_PASS`: physical GPU7 / logical `cuda:0` binding、recurrent Teacher repeated cleanup 与 32-env/10-batch pilot 已通过；checkpoint `global_step=10` 可加载且 finite，GPU7 peak `18241 MiB`，GPU0 peak `2 MiB`。Natural Kit close 仍未 PASS，正式 longer-scale/multi-seed training 仍未运行。
- 2026-07-30 16:13 HKT - `C_B2_SENSORS_RUNTIME_PASS_PANORAMA_VISUAL_FAIL`: 独立 C-B2 三相机 2-env eval 的 goal、same-render/frame-sync/intrinsics/sealing/decode gates 通过，但用户明确拒绝第三栏 panorama 的重影、撕裂和空洞；stage5 handle/trio 仍仅 `9.30%/9.30%`，panorama 重构、physical/CAD/calibration 与 Student input 未验证。
- 2026-07-30 17:34 HKT - `C_B2_TOEIN20_RENDER_COMPLETE_PANORAMA_VISUAL_FAIL`: 独立 ±20° yaw ablation 与五段 157-frame v16 Teacher 视频已完成；82.5° panorama 的 empty ratio `27.08%`，较 ±15° 增加 `4.11pp`，重影/撕裂/空洞仍明显，故仅保留为 wider-view comparison。
- 2026-08-02 05:00 HKT - C-B2H exact64 GPU7 retry 已完成 10,000-step checkpoint；formal Student-only seed0/16-env eval 已执行且 protocol/runtime artifacts PASS，但 policy quality 为 `0/16 goal`、all `stage_overtime` 的 poor/FAIL。env13 sealed-case replay best-only render 已完成；natural Kit lifecycle、ONNX/export、多 seed、final policy quality/open-door success 与 physical camera 项继续开放。
- 2026-08-09 11:05 HKT - Fixed-G2 multi-seed + matched Stage2 diagnostic 已完成：Teacher seed0/1 为 `32/32`，pure Student seed0/1/2 为 `42/48 = 87.5%`；Stage2 evidence 支持 intermittent bilateral contact/squeeze-continuity robustness，不是 contract drift 或全局 handle visibility loss。任何 targeted Stage2 DAgger/contact-continuity finetune 都需新的 approved `HIGH_RISK` brief、multi-seed 与 repeated-replay acceptance；不启动 full retrain 或 generic `1–2k` continuation。
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
- 2026-07-30 16:13 HKT - `C_B2_SENSORS_RUNTIME_PASS_PANORAMA_VISUAL_FAIL`: 保存独立 C-B2 方案并实现三路 high-level `TiledCamera`、双 RGB-D fixed-extrinsic cylindrical/Z-buffer panorama、single-view depth-hole fallback 与四段 process video。sealed v16 Teacher GPU0 eval 2/2 goal，三路各 `157` 帧、pair frame delta `0`、intrinsics error `0px`，五个 MP4 全部完整解码；all-stage handle/trio/panel `74.09%/64.78%/77.08%`，stage5 handle/trio `9.30%/9.30%`。这些 runtime gates 不推翻用户对 panorama 重影/撕裂/空洞的视觉 FAIL；未训练或改变 Student observation，panorama 重构、CAD/physical mount、real pair calibration/sync 与 mirrored left/out 仍开放。
- 2026-07-30 17:34 HKT - `C_B2_TOEIN20_RENDER_COMPLETE_PANORAMA_VISUAL_FAIL`: 新增不覆盖 ±15° 的 ±20° toe-in config/class，v16 Teacher GPU0 eval 2/2 goal，五个 MP4 各 `157` 帧且完整解码；水平 FoV `82.5°`、理论 overlap `2.5°`，empty ratio `27.08%`，panorama 视觉 FAIL 维持。没有训练或修改 Student observation。

- 2026-07-31 03:47 HKT - `C_B2H_DUALRAW_64E_ADMISSION_PASS`: exact G2 step2000 Teacher 与 c18 v19 reconstruction 的 dual-source C-B2H candidate 在 physical GPU7 以 64 env 完成 `global_step=1`，step-1 checkpoint 可加载，peak `31146 MiB`；128 env 则在 optimizer 前 OOM。正式 10,000-batch completion 未声称。
- 2026-08-02 05:00 HKT - `C_B2H_FORMAL_10K_CHECKPOINT_COMPLETE / C_B2H_STUDENT_EVAL_RUNTIME_PASS_POLICY_QUALITY_FAIL / C_B2H_RENDER_BEST_ONLY_COMPLETE`: 10,000-step checkpoint 的 SHA256 为 `005705dc033605a24bc231b18fbfaabe3288a699130a7ce2e423eac736963a45`；Student-only 16-env seed0 eval protocol/runtime artifacts PASS，但 `0/16 goal`、all `stage_overtime` 为 policy-quality poor/FAIL。env13 sealed-case 三次 replay 均 drift 到 stage1，only trial01 的 6 段视频保留并 full decode PASS；natural Kit lifecycle 与 final quality/open-door success 未关闭。
- 2026-08-08 23:30 HKT - `C_B2H_TOEOUT6_TRUE_TEACHER_STAGE0_DIAG_COMPLETE`: 校正 true Teacher action route 后，seed0 Teacher 为 `10/16`、Student 为 `8/16`；旧 `controller=teacher` lane 使用 Student rollout，不能再作为 Teacher evidence。true Teacher 共享 Stage0 failures 为 env `0,4,5,7,12,15`，Teacher-only successes 为 env `2,9`。六个 failures 都通过 arm condition、仅失败于 staging-distance gate，且 tail static metrics 支持 gate 外 attractor；全量 17-key `customData` 对单 seed n=16 无单一分离维度。
- 2026-08-09 02:59 HKT - `C_B2H_TOEOUT6_G2_STAGE0_CONTRACT_RUNTIME_PASS`: historical reconstructed true Teacher baseline 为 `16/16`；sealed G2 contract 为 `0.50 <= dx <= 0.80`、严格 `abs(dy) < 0.15`、arm deviation `<0.10`、physical base command norm `<=0.10`。旧 point-gate true Teacher replay 为 `10/16`，其六个 failures `0,4,5,7,12,15` 的 final 50 Stage0 records 均 G2-ready。candidate 只更新 env transition/reward/visual/trace 与 runner effective-config injection/validation，未改 observation/action/camera。GPU4 fixed true Teacher seed0/16-env/one-episode replay 为 `16/16` stage5/complete（`gt_actions`、Student calls `0`）；GPU5 matched pure Student 为 `13/16`，remaining `4,6,9` 都是 Stage2 `stage_overtime`，没有 finetune。所有 runtime verdict 仅限该 seed0 replay，不是 multi-seed/general PASS。
- 2026-08-09 11:05 HKT - `C_B2H_G2_MULTISEED_STAGE2_DIAG_COMPLETE`: fixed-G2 true Teacher seed0/1 为 `32/32`；formal pure Student seed0/1/2 为 `13/16`、`16/16`、`13/16`，共 `42/48 = 87.5%`，seed0 `{4,6,9}` 与 seed2 `{8,12,14}` failures 无交集。matched R4 Stage2 下 env4 Student streak `2` 对 Teacher streak `5` at `t=160`；Student env6/env9 分别 at `t=108` / `t=219` 完成。相同 contract、env4 close command/physical stable close 以及 D435 handle-visible/local-self-occlusion evidence 支持 intermittent Student bilateral contact/squeeze-continuity robustness，不支持 contract drift 或 global handle visibility loss。same-seed replay 从 `13/16` 变化至 `14/16`、`15/16`，env9 formal success 可在 render replay 变为 Stage2 overtime；不授权 full retrain/generic `1–2k` continuation。任何 targeted Stage2 DAgger/contact-continuity finetune 需新的 approved `HIGH_RISK` brief、multi-seed/repeated-replay acceptance；无 determinism/general/deployment/physical-camera PASS，lifecycle 仍 unresolved。

## Recommended Next Files To Read

- `memory/a2-piper/phase2-student-distillation-a2-piper/TODO.md`
- `gr00t/rl/scripts/README.md`
- `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`
- `gr00t/rl/scripts/validate_a2_teacher_checkpoint.py`
