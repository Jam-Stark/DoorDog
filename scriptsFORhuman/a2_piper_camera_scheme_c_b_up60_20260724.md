# A2+Piper Camera 方案 C-B：Landscape D435i Up60 + A2 Head

Last updated: 2026-07-24 15:45 HKT

Status: `RUNTIME_SMOKE_PASS / EVAL_ONLY / ONE_ENV_VIDEO / NO_TRAINING`

## 1. 目标与变更

C-B 是方案 C 的单变量 camera ablation：

- D435i 从 portrait 改为 landscape；
- D435i optical center 保持在 trunk 中轴 `[0.28, 0.0, 0.25] m`；
- D435i 光轴上仰从 C-A 的 `45 deg` 增加到 `60 deg`；
- A2 Head context camera 的位置、姿态、FoV 和 provisional 状态保持不变；
- 两路 camera 继续执行 `y=0, yaw=0` 的左右对称 contract；
- 只做 sealed Teacher eval 和视频诊断，不修改 Student observation/model，不训练。

实现提交为 `384518a3a6efc807b8f4ecdd3c2dae25fff14485`，主要变更：

- 新增 `d435i_landscape_up45_a2_head.yaml` 和
  `d435i_landscape_up60_a2_head.yaml`；
- 增加 `DoorPregraspCameraSchemeCA` / `DoorPregraspCameraSchemeCB`；
- 将 Scheme C wrapper、runtime allowlist、summary seal 和 video layout
  泛化到显式的 C/C-A/C-B identity；
- 增加 C-A/C-B config、geometry、eval-only command 与 runtime-source tests；
- 更新 Student Distillation memory 中的 C-B runtime-smoke evidence。

先前终止的 stage0-3 edge-safe pitch sweep 不属于该提交，也没有被 push。

## 2. C-B 精确仿真配置

### 2.1 Landscape D435i

| Field | Value |
|---|---|
| Parent | `trunk` |
| Prim suffix | `d435i_landscape_camera` |
| Optical center | `[0.28, 0.0, 0.25] m` |
| Effective optical RPY | `[0, -60, 0] deg` |
| Quaternion | `[0.8660254037844386, 0, -0.5, 0] wxyz` |
| Symmetry | `y=0`, `yaw=0` |
| Housing | landscape, no software rotation |
| Output | `384x216` |
| Sim effective FoV | `69 deg H x 42.2725589501 deg V` |
| Intrinsics | `[279.3617335051, 279.3617335051, 192, 108]` |
| Modalities | RGB + raw instance-ID segmentation |

配置路径：
`gr00t/rl/config/camera_pose_sweep/d435i_landscape_up60_a2_head.yaml`。

### 2.2 A2 Head context

A2 Head 沿用方案 C：

| Field | Value |
|---|---|
| Parent | `trunk` |
| Provisional optical center | `[0.32, 0.0, 0.25] m` |
| Provisional optical RPY | `[0, -12, 0] deg` |
| Diagnostic output | `384x136` |
| Sim effective FoV | `132 deg H x 77.0024873497 deg V` |
| Extrinsic status | `provisional_not_cad_or_calibrated` |

## 3. Runtime 与视频合同

- 使用两个 high-level IsaacLab `TiledCamera` sensor；
- 每个采样点只执行一次 `sim.render()`；
- 两个 sensor 分别执行 `update(dt=0, force_recompute=True)`；
- sensor frame 各增加一次，physics counter 不前进；
- D435i 与 A2 Head 独立输出 MP4，并生成固定双栏 combined MP4；
- combined layout 为左侧 `384x216` D435i、右侧 letterboxed A2 Head；
- 视频只取 env1；运行使用 2 env，避免 eval entrypoint 的单 env ONNX side effect。

## 4. Sealed runtime-smoke evidence

运行使用：

- Teacher: `base_v16_B model_step_002000.pt`;
- checkpoint SHA-256:
  `5628a25ee53395ddc581d2da184c32635e109ff3691e54a823ad054236475e3f`;
- adjacent config SHA-256:
  `3c8aead9025b66a7f6f2ac3afc81bedc9cdafa1d12bd08fd43058eff8b4fd144`;
- pinned runtime commit:
  `815b367f5de2a52b26a4b872d0457af8817d01bd`;
- GPU0, 2 env, seed0, eval-only；
- 2/2 env 到达 stage5 并 `goal_reached=true`；
- `training_performed=false`；
- runtime intrinsics 最大误差 `0 px`；
- 进程自然退出 `0`，GPU0 完整释放。

env1 视频覆盖 stage0-5，帧数为 `20/10/12/19/53/43`，合计 157 帧。

### 4.1 Combined video

Path:
`logs_eval/a2_piper_camera_scheme_c_b_up60_v16_env1-20260723/scheme_c_b_d435i_landscape_up60_plus_a2_head_env0001.mp4`

- `768x216 @ 10 fps`;
- 157/157 frames decoded；
- size `336399` bytes；
- SHA-256:
  `0fc26356823fc168adb0efbd92de4ea29ed5aa8a47ed424fc52f2c4f12cab626`。

### 4.2 Separate views

- D435i:
  `camera_scheme_c_b_views/d435i_landscape_up60_env0001.mp4`,
  SHA-256
  `fe3420ca84eb1b1f2f29ceb2fc8eeb416f76466ec84c7f631ed7e4cea0a9a226`；
- A2 Head:
  `camera_scheme_c_b_views/a2_head_context_env0001.mp4`,
  SHA-256
  `41926b8687172348ead9c950efc813ad0af68f89d326330135632be79fea2e1a`。

Sealed summary:
`logs_eval/a2_piper_camera_scheme_c_b_up60_v16_env1-20260723/camera_pose_sweep_summary.json`。

## 5. Validation

- exact staged-index tests: `22 passed`;
- broader working-candidate tests before selective staging: `24 passed`;
- Python compile: PASS；
- staged `git diff --check`: PASS；
- CODE_QUALITY review: PASS；
- IsaacLab/API/fail-fast review: PASS；
- MP4 end-to-end OpenCV decode: PASS。

## 6. Evidence boundary

该结果只证明 C-B 仿真配置和 env1 视频链路可运行。它不证明：

- 16-env formal visibility；
- mirrored `left/out`；
- D435i 实物 bracket、CAD clearance、标定、畸变、曝光、延迟或振动表现；
- A2 Head 的真实 extrinsic；
- Student 双 camera 输入或 policy quality；
- 最终 camera mount 已冻结。

stage5 handle + both fingers 的 union visibility 在该 smoke 中为 `8/86`
（`9.30%`）；这是诊断事实，不影响本次“交付一个 env render 视频”的完成状态，也不能被
表述为 full-task camera hard-gate PASS。
