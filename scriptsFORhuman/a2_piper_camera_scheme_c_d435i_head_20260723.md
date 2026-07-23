# A2+Piper Camera 方案 C：Portrait D435i + A2 Head

Last updated: 2026-07-23 18:06 HKT

Status: `RUNTIME_PASS / VISIBILITY_PARTIAL / EVAL_ONLY / HEAD_EXTRINSIC_PROVISIONAL / NO_STUDENT_CHANGE`

## 1. Source and intake

云 session 最新修改版已按原文归档为
[`research_inputs/a2_piper_camera_cloud_scheme_revision_20260723.md`](research_inputs/a2_piper_camera_cloud_scheme_revision_20260723.md)，源文件与归档文件 SHA-256 均为
`c179d59edecb9adb82dc00d0fa45c22018b3430bf384c46c5125a5ceabac52d0`。
归档是 research input；本文记录本仓库的可执行选择和边界。

采用方案 C 的双视角架构：一台竖装 Intel RealSense D435i 上仰，配合 A2
原装 Head wide-context camera。第一阶段只做 Teacher-controlled、eval-only 的双视角
可见性与 render，不训练、不修改 Student observation/model，也不把两路图像误称为
连续 panorama。

**Cloud report correction（2026-07-23）**：原报告的 `front-right cheek` 安装和“向中轴
内转 5-15 deg”建议是失误，与已经多次明确的左右门镜像/左右对称画面需求冲突。
原文归档保持不改以保留 provenance；本仓库不采纳该偏置，而把 D435i optical center
放到 `y=0` 中轴，设 `yaw=0 deg`。只保留 portrait housing 这一架构意图；cloud 的
`25 deg` pitch 也没有硬套，最终 pitch 由本仓库 smoke/contact-sheet evidence 修正为
`-12 deg`。任何重新引入非零 lateral offset 或 yaw 的修改都属于 symmetry-contract drift。

## 2. Repository facts that constrain implementation

- A2_Piper URDF 只有 `trunk` 和 Piper/leg bodies；没有独立 `head_camera`、`camera_link`
  或 lidar body。USD sensor sublayer 也没有可由当前 config 引用的已验证 Head optical frame。
- 当前 simulator 只为 policy path 建立一个 `ego_camera`，但 door env 的
  `scene_creation_callback` 可用 IsaacLab high-level `TiledCameraCfg` 增加第二个 sensor。
- 因此仿真中的 A2 Head 必须先建成 `trunk` 下的 provisional diagnostic optical frame；
  不得把它表述成经过 CAD/实机标定的原装 camera extrinsic。
- 两个 sensor 必须在同一次 `sim.render()` 后各自 `update(dt=0,
  force_recompute=True)`，并证明 physics step counter 不前进。

## 3. Exact simulation seed

### 3.1 Portrait D435i manipulation view

| Field | Value |
|---|---|
| Parent | `trunk` |
| Prim | `d435i_portrait_camera` |
| Optical center | `[0.280, 0.000, 0.250] m` |
| Effective optical RPY | `[0, -12, 0] deg` (`pitch -12` means optical axis up) |
| Quaternion | `[0.9945218953682733, 0.0, -0.10452846326765347, 0.0] wxyz` |
| Housing/image convention | D435i housing portrait; output is software-uprighted portrait, so effective optical frame has zero roll |
| Output | `216 W x 384 H` |
| Nominal source FoV | D435i RGB `69 deg H x 42 deg V`, mechanically rotated portrait |
| Simulation FoV | `42.2725589501 deg H x 69 deg V` |
| Intrinsics | `[fx,fy,cx,cy]=[279.3617335051,279.3617335051,108,192]` |
| Depth | disabled; RGB + raw instance-ID segmentation only |

The first runtime smoke used the cloud report's `x=0.295,z=0.080,pitch=-25 deg`
seed. It completed all synchronization gates but human QA showed both views dominated by the
near door panel/wall/floor; stage-5 handle visibility was only `3/86` for D435i and `0/86` for
Head. That numeric seed is therefore rejected for this repository's actual `trunk` frame.

Revision 2 uses the already validated Gemini sweep evidence: `x_near_028` proved the best
longitudinal seed and `pitch_up_12`/`z=0.25` preserved stage1-4 visibility. Portrait D435i adds
vertical FoV, so the executable seed is `[0.28,0,0.25]` with `pitch=-12 deg`. The Head context
uses the validated `pitch_up_12` seed `[0.32,0,0.25]`, `pitch=-12 deg`, and keeps the wider Head optics.
The cloud report's right-side offset and inward yaw remain rejected: both views keep `y=0` and
`yaw=0 deg` for left/right symmetric optical geometry.
A follow-up contact-sheet check showed that reusing x-near's `pitch=-6 deg` also reproduced the
reported upper-edge loss in the Head panel. The final Head seed therefore uses the already swept
`pitch_up_12` candidate, whose prior 16-env stage1/stage2 handle-visible rates were
`70.47%/78.57%`, rather than continuing a new pose search.

### 3.2 A2 Head context view

| Field | Value |
|---|---|
| Parent | `trunk` |
| Prim | `a2_head_context_camera` |
| Provisional optical center | `[0.320, 0.0, 0.250] m` |
| Provisional optical RPY/quaternion | `[0,-12,0] deg` / `[0.9945218953682733,0,-0.10452846326765347,0] wxyz` |
| Published capability used as target | `132 deg H x 77 deg V`, up to `2568x1448@15 fps` |
| Diagnostic output | `384 W x 136 H` |
| Pinhole approximation | `132 deg H x 77.0024873497 deg V` |
| Intrinsics | `[fx,fy,cx,cy]=[85.4839075792,85.4839075792,192,68]` |

The `384x136` raster is a FoV-preserving diagnostic pinhole approximation padded into a
`384x216` video panel. It is not a claim that the physical A2 wide-angle optics are rectilinear.
The optical center/orientation remain provisional until measured CAD or real calibration exists.

## 4. Render contract

The final video is a fixed two-panel canvas, not panorama stitching:

```text
left 384x216: portrait D435i, aspect-preserved and pillarboxed
right 384x216: A2 Head context, aspect-preserved and letterboxed
combined: 768x216 @ 10 fps
```

The selected video environment must traverse every ranked stage 1-5. Separate raw-view MP4s
are also sealed so an artificial panel resize cannot hide a visibility failure.

## 5. Rejected smoke evidence

The non-overwriting revision-1 output is retained locally at
`logs_eval/a2_piper_camera_scheme_c_v16_smoke-20260723/`. It is a runtime PASS for sensor
construction/synchronization and a visual FAIL for camera placement; it must not be presented as
the final Scheme C render. The revised seed must pass the same gates below in a fresh output.

## 6. Acceptance gates

- use the sealed `base_v16_B` checkpoint/config identities; no trainer;
- two distinct high-level `TiledCamera` sensors and unique prim paths;
- runtime intrinsic readback within `1e-4 px` of both declared matrices;
- local pose readback closes for both views;
- one same-step render per sample; both sensor frames increment exactly once; physics does not;
- stage1-5 samples exist for both views and the combined visibility diagnostic;
- independent D435i, A2 Head and combined MP4s are non-empty, equal-length where applicable,
  contain stage1-5, and decode end-to-end;
- manually inspect approach, grasp/open, swing and through frames;
- report per-view and conservative combined visibility. Combined trio visibility means at least
  one single view sees handle plus both fingers; it is not assembled across views;
- keep production Student camera/observation/model unchanged.

## 7. Formal 16-env result

正式 GPU0 eval 使用完整推门 checkpoint
`logs_rl/a2_piper_full_stage_a2_base/base_v16_B_m29_m32_mass80_160-20260721_230405/model_step_002000.pt`
（SHA-256 `5628a25ee53395ddc581d2da184c32635e109ff3691e54a823ad054236475e3f`）
和 adjacent config（SHA-256
`3c8aead9025b66a7f6f2ac3afc81bedc9cdafa1d12bd08fd43058eff8b4fd144`）。
runtime 固定到 clean mainline commit
`815b367f5de2a52b26a4b872d0457af8817d01bd`；`training_performed=false`。
16 个 episode 全部完成，checkpoint 保持 `15/16 goal`。

sealed summary 位于
`logs_eval/a2_piper_camera_scheme_c_v16_formal-20260723/camera_pose_sweep_summary.json`。
两路相机的 runtime intrinsic 最大误差均为 `0.0 px`；每次采样只做一次
`sim.render()`，两个 sensor frame 各增加一次，physics counter 不变。env1 合成视频共
`224` 帧，stage0–5 分别为 `32/18/18/26/64/66` 帧。

| Stage | D435i handle / trio | A2 Head handle / trio | Conservative union handle / trio |
|---|---:|---:|---:|
| 1 | 78.19% / 1.01% | 75.84% / 0.00% | 84.56% / 1.01% |
| 2 | 69.33% / 10.92% | 79.41% / 3.36% | 85.71% / 12.18% |
| 3 | 67.00% / 41.06% | 95.97% / 68.51% | 99.75% / 74.31% |
| 4 | 99.20% / 95.09% | 98.97% / 81.39% | 99.89% / 95.66% |
| 5 | 6.32% / 3.22% | 9.30% / 0.36% | 10.25% / 3.22% |

这里 `trio` 要求同一个 view 同时看到 handle 和两根 finger；union 不会跨 view 拼装
目标。三份 MP4 均已 end-to-end decode：

- combined:
  `logs_eval/a2_piper_camera_scheme_c_v16_formal-20260723/scheme_c_d435i_portrait_plus_a2_head_env0001.mp4`
- portrait D435i:
  `logs_eval/a2_piper_camera_scheme_c_v16_formal-20260723/camera_scheme_c_views/d435i_portrait_up12_env0001.mp4`
- A2 Head:
  `logs_eval/a2_piper_camera_scheme_c_v16_formal-20260723/camera_scheme_c_views/a2_head_context_env0001.mp4`

人工审查覆盖 stage1–5 边界与中间帧：stage3–4 操作区可见性明显改善，尤其 D435i
stage4 trio 为 `95.09%`；但机器人过门后，两台固定朝前的 trunk camera 都把 handle
留在身后，stage5 conservative-union handle/trio 只有 `10.25%/3.22%`。因此最终
verdict 是 `SCHEME_C_IMPLEMENTED / RUNTIME_PASS / VISIBILITY_PARTIAL`，不是 full-task
camera hard-gate PASS。严格中轴 `y=0,yaw=0` 已保持，没有采纳云报告的右偏安装或
“向中轴内转 5–15°”；本轮资产仍只有 right/out，左右镜像行为尚未由 runtime 证明。

## 8. Non-claims

Passing this prototype does not prove physical bracket clearance, measured Head extrinsics,
D435i color calibration/distortion, 15/30 fps synchronization, rolling-shutter blur, real latency,
left/right door symmetry, Student policy quality, or a final camera mount. It only characterizes
this exact simulated two-view seed and shows that a further stage5-aware viewpoint/observation
design is still required before the next hardware/calibration decision.
