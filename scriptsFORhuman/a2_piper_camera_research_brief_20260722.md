# A2+Piper Camera 方案云端调研 Brief

Last updated: 2026-07-22 HKT

Status: `CLOUD_REPORT_ARCHIVED / R14_RESOLVED / V16B_STAGE1_5_SWEEP_COMPLETE / NEXT_SEARCH_CENTER_X_NEAR_028 / PHYSICAL_MOUNT_DEFERRED`。本文记录当前仓库事实、云端调研结论、已采纳的设计约束与后续验证入口；它不是最终采购 BOM，也不表示 Student observation 已经修改或实物 camera mount 已经冻结。

## 1. Destination 与停止条件

本调研服务于 A2 四足底盘 + Piper 单臂的视觉 Student distillation。最初目标是覆盖 `base_v13_A` 的 intermediate opening behavior；现在主线已有能执行完整推门序列的 `base_v16_B` checkpoint，因此当前 camera 评测 driver 和可见性目标已经扩展到完整 stage1–5。`v13_A` 仍是本蒸馏分支的历史 provenance，不再是当前 pose ranking 的唯一行为上界。

准确的行为目标是：

- 从门前接近并对准 handle；
- 观察 Piper gripper 与 handle 的相对关系，完成接近、闭合和持续双侧夹持；
- 在 A2 姿态变化、Piper 运动和门扇转动时继续保留关键视觉线索；
- 在 stage5 穿门阶段继续观察 opening corridor、门框、门扇和相关碰撞上下文，而不只优化 grasp/open 阶段。

历史 `v13_A` seed0 evidence 是 `0/16 goal`、`16/16 stage4`、`4/16 stage5`，hinge terminal p50 约 `1.276 rad`。当前正式 camera sweep 使用 `base_v16_B`；本次 16-env seed0 rollout 为 `15/16 goal`，其中 env0 在 stage0 overtime、其余 env 到达 stage5。单次 rollout 仍不是统计意义上的最终 winner。因此 camera 调研的 stopping condition 是：

1. 核清当前 Camera/robot/task contract；
2. 形成有来源的狗+臂平台、paper、project 与传感器对照表；
3. 给出明确的第一阶段单 camera 推荐，以及触发 wrist/双 camera 升级的证据门槛；三 camera 仅在第三视角具有独立价值时保留；
4. 每套方案给出数量、安装 parent/link、位置、朝向、FoV/分辨率/帧率、型号候选、遮挡与集成代价；
5. 明确哪些结论来自 source，哪些是推断，哪些仍需物理测量或仿真 sweep；
6. 给出先验证 transform、再做 pose sweep、最后改 observation/model 的执行顺序。

## 2. Repository pin 与远程入口

| Item | Value |
|---|---|
| Remote repository | https://github.com/Jam-Stark/DoorDog |
| Target branch | `codex/a2-v13-student-distillation-20260717_2103` |
| Remote branch URL | https://github.com/Jam-Stark/DoorDog/tree/codex/a2-v13-student-distillation-20260717_2103 |
| Cloud-report research pin | `843795013329d9478634c6d87db9756210a311ba` |
| Cloud-report pinned URL | https://github.com/Jam-Stark/DoorDog/tree/843795013329d9478634c6d87db9756210a311ba |
| V16 camera-sweep overlay base | `ca67daa76549f8983f6b04c9e1fe5f9734619a80` in the dedicated worktree |
| V16 Teacher runtime pin | `815b367f5de2a52b26a4b872d0457af8817d01bd` in `/home/baoquanc/workspace/DoorDog-A2_Piper` |
| Dedicated local worktree | `/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103` |
| Local IsaacLab source pin | `/home/baoquanc/workspace/IsaacLab` at `c22775241e28f465fe345fa1a482ad6d29d712b0` |

云端调研应优先使用 cloud-report research pin 生成永久链接，再用 target branch 检查后续变动。`logs_rl/` 与 `logs_eval/` 被 Git ignore；远程仓库能看到 config、source 和 memory 结论，但看不到本地 checkpoint、MP4 与大体积 runtime artifacts。不得把“远程看不到 artifact”误写成“artifact 不存在”。

### 2.1 Cloud report 归档与 intake decision

Cloud Pro 返回的原始报告已按原文归档为 [`scriptsFORhuman/research_inputs/a2_piper_camera_cloud_pro_report_20260722.md`](research_inputs/a2_piper_camera_cloud_pro_report_20260722.md)，source SHA-256 为 `7432bded48ea950e74633d8460ab8aede84b4f3227bcf2145859f632cf276e8c`。归档文件是 research input，不是本仓库已经验证的 runtime 事实；本 brief 才记录当前采纳、修正和延后的决定。

| Report item | Intake decision |
|---|---|
| 单个 trunk RGB/RGB-D overview camera，保持现有单 RGB Student contract | **采纳为第一阶段架构**。Student 仍只消费一个 `384×216` RGB stream；depth 只允许记录/诊断，不得静默进入 policy input。 |
| Orbbec Gemini 335L | **采纳为 preferred prototype / sim-target candidate**，按下表的官方规格建立后续 camera config；尚不是最终采购或实机 bring-up PASS。 |
| trunk 高位右偏安装、右偏 yaw/crop | **否决为 nominal design**。它会把当前 `right/out` 训练资产的偶然 handedness 固化到硬件；未来仿真与实机都必须覆盖 left/right-opening doors。 |
| trunk 中心线安装 + left/right mirror-paired sweep | **采纳**。默认 `Y=0`、yaw `0°`，如测试偏置，必须同时测试符号相反的 lateral/yaw pair。 |
| Gemini 305 wrist camera | **保留为第二阶段 upgrade candidate**。只有单 camera 在 left/right 镜像场景的近距 handle/gripper visibility gate 明确失败，才启动多视角 observation/model 设计。 |
| R14 transform probe | **已完成并解除 pose-sweep blocker**。same-step probe 证明 configured local pose 和 live camera prim 数值闭合；旧 mismatch 来自 `update_latest_camera_pose=false` 时的 stale initialization `CameraData`。该结论不等于 final mount。 |
| `j8 open-limit <10%` 作为 camera hard gate | **不采纳**。`v13_A` Teacher 本身为 `14.151%`，该项只能作为 inherited Teacher guardrail/non-regression diagnostic，不能单独否决 camera。 |
| 单个 16-env batch 的百分比提升阈值 | **不采纳为最终统计门槛**。后续行为对比必须使用预先声明的 multi-seed/episode matrix，并报告 paired counts 与不确定性。 |

### 2.2 已批准的 hardware target specs

以下是后续 camera config 与实机候选筛选的 source-backed target，不是端到端实测吞吐、延迟或深度质量保证。

| Field | Gemini 335L preferred trunk candidate | Gemini 305 optional wrist candidate |
|---|---|---|
| RGB | up to `1280×800 @ 60 fps` | up to `1280×800 @ 60 fps` |
| RGB FoV | `94° H × 68° V` | `94° H × 68° V` |
| Shutter | global-shutter sensors | global-shutter stereo color |
| Depth | up to `1280×800 @ 30 fps`; `0.17–20 m+`, optimal `0.25–6 m` | up to `1280×800 @ 30 fps`; `0.04–1 m+`, ideal `0.07–0.5 m` |
| Mass / size | `133 g`; `124×29×27 mm` | `68 g`; `42×42×23 mm` |
| Power / ingress | average `<3 W`; `IP65` | average `<2 W`; `IP54` |
| Integration-relevant features | USB 3 Type-C, IMU, trigger, multi-device synchronization | hardware/software trigger; compact wrist-oriented form factor |
| Official source | [Orbbec Gemini 335L](https://www.orbbec.com/products/stereo-vision-camera/gemini-335l/) | [Orbbec Gemini 305](https://www.orbbec.com/gemini-305/) |

For the approved one-camera target, the acquisition path is `1280×800 @ 60 fps` RGB capture, calibrated/undistorted **centered** `1280×720` crop, then resize to `384×216` for the current Student. No handle-side-biased crop is allowed. The native `94°×68°` RGB FoV does not remain unchanged after a 16:9 crop; exact effective intrinsics/FoV must be calculated from the calibrated cropped stream. Capture rate, transport rate, inference rate and 50 Hz control rate remain separate quantities and require runtime measurement.

Using the nominal vendor FoV rather than a physical calibration, the native pinhole values are `fx=596.8096551281`, `fy=593.0243874051`, `cx=640`, `cy=400`. The centered `1280×720` crop keeps `fx/fy`, moves `cy` to `360`, and the `384×216` resize yields spec-derived `[fx,fy,cx,cy]=[179.0428965384,177.9073162215,192,108]`, effective FoV `94° H × 62.5203301934° V`. The pinned IsaacLab projection assumes square pixels, so the sweep uses `[179.0428965384,179.0428965384,192,108]`, preserving horizontal FoV and producing `62.1973813521° V`; the `fy` difference is `+1.1355803169 px`. Both sets are nominal/spec-derived, not a substitute for calibrated 335L intrinsics.

## 3. 当前 Student perception contract

### 3.1 部署/训练用 ego camera

当前 Student 只有一条部署视觉流。它不是 URDF 中的实体 camera link，而是代码在 `trunk` 下创建的 IsaacLab `TiledCamera`：

| Field | Current value | Source |
|---|---:|---|
| Enabled | `true` | `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml` |
| Parent body | `trunk` | 同上 |
| Prim suffix | `ego_camera` | 同上 |
| Resulting prim path | `/World/envs/env_.*/Robot/trunk/ego_camera` | `gr00t/rl/simulator/isaacsim/isaacsim.py` |
| Local position | `[0.25, 0.0, 0.14] m` | Student experiment config |
| Local quaternion | `[0.315631686, 0.134503192, -0.390177116, -0.854428083]`, `wxyz` | Student experiment config |
| Offset convention | `world` | Student experiment config |
| Optical forward/up for `world` convention | `+X / +Z` | IsaacLab `CameraCfg.OffsetCfg` |
| Focal length | `1.88` | Student experiment config |
| Focus distance | `0.5` | Student experiment config |
| Horizontal aperture | `2.6035` | Student experiment config |
| Vertical aperture | `1.4621` | Student experiment config |
| Derived full FoV | approximately `69.4° H × 42.5° V` | Derived from focal length/aperture |
| Clipping | `[0.1, 20.0] m` | Student experiment config |
| Update period | `0.0` | Student experiment config |
| Stream | RGB enabled; depth disabled | Student experiment config |
| Training resolution | `384 × 216` pixels, config order `[H,W]=[216,384]` | Student experiment config |
| Eval resolution | `1280 × 720` | Student experiment config |
| Normalization | ImageNet mean `[.485,.456,.406]` / std `[.229,.224,.225]` | Student experiment config |
| Lighting randomization | `randomize_dome_light: false` | Student experiment config |
| Image augmentation | disabled | Student experiment config |

The camera output contract is strict:

- Raw IsaacLab RGB is `torch.uint8` with shape `[num_envs,H,W,3]`.
- Repo code rejects a missing sensor, wrong shape/dtype, non-finite values, or an all-zero environment.
- RGB is converted to `float / 255`, normalized, then flattened as the `rgb_image` observation.
- Current resolution contributes `216 × 384 × 3 = 248,832` visual scalars before the ResNet encoder.

The Student model is `ResNet18`, ImageNet-pretrained and trainable, with `128D` vision feature followed by a two-layer `LSTM` with hidden size `256`. The deployable policy contract is:

`81D proprio + one 384×216 RGB frame -> 12D high-level action`

The `81D` proprioception contains base angular velocity, projected gravity, 20D A2+Piper joint position, 20D joint velocity, 19D previous effective actions, 6D Piper delta actions, and two 5D A2 base command views. It does not contain door pose, handle pose, privileged stage, or privileged gripper-handle transform. Camera therefore carries essentially all exteroceptive door/handle information.

Physics is configured at `200 Hz` with control decimation `4`, so high-level control is `50 Hz`. Hardware research must distinguish camera capture rate, transport rate, inference rate and control rate; it must not assume they are identical.

### 3.2 Camera implementation semantics

Relevant implementation behavior:

- `gr00t/rl/simulator/isaacsim/isaacsim.py` validates an explicit, normalized pose and supports only explicit `camera_convention: world` on this A2 path.
- Camera parent must resolve to exactly one robot body. Current parent `trunk` is valid.
- The camera is spawned through high-level `TiledCameraCfg` and `PinholeCameraCfg`; no low-level USD camera creation is needed for the deployed sensor.
- `CameraCfg.OffsetCfg.pos/rot` are relative to the parent frame. The convention describes the camera axes used to interpret the offset orientation.
- Local IsaacLab `CameraCfg` currently defaults `update_latest_camera_pose=false`. The repo does not override it. This means `CameraData.pos_w` may represent initialization pose rather than live pose. This is a specific hypothesis to verify against the exact installed/runtime version before interpreting transform telemetry; it is not yet the confirmed R14 root cause.
- Repo properties named `_camera_pos` and `_camera_quat` return the configured parent body pose from `robot.data`, not the optical sensor pose. Any diagnostic must label parent pose and sensor pose separately.

Official/current API references:

- IsaacLab Camera overview: https://isaac-sim.github.io/IsaacLab/main/source/overview/core-concepts/sensors/camera.html
- Pinned IsaacLab `CameraCfg` source: https://github.com/isaac-sim/IsaacLab/blob/c22775241e28f465fe345fa1a482ad6d29d712b0/source/isaaclab/isaaclab/sensors/camera/camera_cfg.py
- Pinned IsaacLab `TiledCameraCfg` source: https://github.com/isaac-sim/IsaacLab/blob/c22775241e28f465fe345fa1a482ad6d29d712b0/source/isaaclab/isaaclab/sensors/camera/tiled_camera_cfg.py

### 3.3 Evaluation cameras are not Student sensors

The repository also has three external, qualitative rendering viewpoints:

| Name | Anchor/mode | Eye offset/value | Look-at | Purpose |
|---|---|---|---|---|
| `main` | door-relative `door_top_down` | `[-2.5,-2.5,2.2]` | `[-0.5,0,0.45]` | Whole robot/door behavior |
| `handle_top` | handle center | `[0,0,0.65]` | `[0,0,0]` | Gripper/handle relationship from above |
| `handle_side` | handle center | `[0,0.62,0.02]` | `[0,0,0]` | Closing depth/contact geometry from side |

They render at `1280×720@20 fps` and write independent MP4 files after one shared `sim.render()`. They are diagnostic cameras placed in the environment, not deployable onboard inputs and not part of `vision_obs`. A cloud report must never count these as “the current robot has three cameras”.

The G1/Doorman legacy Student config is another design clue: it references a robot-authored `d435_link` with offset `[0,0.035,0]`, quaternion `[0.99955,0,0.0299955,0]` and the same `216×384` RGB route. That file uses legacy camera keys and is not the active A2 camera contract. It is evidence that the upstream design expected an Intel D435-class physical mount, not proof that D435 is optimal for A2+Piper.

## 4. A2 + Piper geometry and task context

### 4.1 Robot

| Fact | Value/path |
|---|---|
| Robot config | `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` |
| URDF | `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf` |
| Main USD | `gr00t/rl/data/robots/A2_Piper/a2_piper.usd` |
| USD sublayers | `gr00t/rl/data/robots/A2_Piper/configuration/a2_piper_base.usd`, `a2_piper_physics.usd`, `a2_piper_robot.usd`, `a2_piper_sensor.usd`（后三者同目录） |
| Bodies / DoF | 27 bodies / 20 DoF |
| Legs / arm-gripper | 12 leg DoF / `arm_j1..arm_j8` |
| Torso parent | `trunk` |
| End-effector body | `arm_body6_to_gripper` |
| Piper fixed mount | `arm_j0`: parent `trunk`, child `arm_body0`, origin `[0.145,0,0.154] m` |
| Current ego camera offset | parent `trunk`, `[0.25,0,0.14] m` |
| Initial base position | `[0,0,0.55] m` |
| Trunk main collision box | `0.24×0.28×0.17 m` around trunk origin |

The Piper base and ego camera are both mounted from `trunk` at similar forward/up offsets. Arm self-occlusion is therefore expected to be a first-class constraint, especially when the arm rises, folds, or crosses the optical axis. The remote report must inspect the URDF meshes/link chain and must not select a pose from a single static screenshot.

The names “A2” and “Piper” do not by themselves prove the exact commercial revision, camera bracket, compute carrier or available power/connectors. If the repository does not contain a hardware BOM or mechanical drawing, mark those fields `UNKNOWN` and list the physical measurements required from the user. Do not infer a vendor/revision merely from naming.

### 4.2 Door task and visibility envelope

| Fact | Value/path |
|---|---|
| Task config | `gr00t/rl/config/env/door_open_a2_base.yaml` |
| Environment implementation | `gr00t/rl/envs/door/door_open_a2_base.py` |
| Door generator | `gr00t/rl/isaac_utils/playground/env_rand/door.py` |
| Door scenario config | `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` |
| Door root target | `[2.0,0.0,0.5]` |
| Door width/height range | `0.8–1.1 m / 1.9–2.2 m` |
| Handle height range | `0.85–0.95 m` in the current scenario |
| Door opening side/direction | fixed `right / out` in the current source scenario; first future handedness extension is mirrored `left / out` |
| Current stage0 staging offset | `0.70 m` behind the handle-relative grasp target along X |
| Grasp target prim | `door/grasp_target` |
| Contact target | `door/door_handle` |
| Virtual Piper TCP offset | local Z `0.085 m` |
| Stages | six stages with max control steps `[250,100,100,100,100,200]` |

Camera coverage must be evaluated across the complete sequence, not only at reset:

1. Door and handle at approach distance;
2. handle + pregrasp + gripper during fine alignment;
3. finger closure at near range, including the `0.1 m` near clipping boundary;
4. handle retention while the door rotates;
5. door frame, opening corridor and body/arm collision context while the base moves;
6. A2 pitch/roll/yaw and locomotion vibration.

### 4.3 Left/right symmetry contract

The current `right/out` asset is a source baseline, not a camera-mount requirement. Future `door_open_lr=["left","right"]` randomization mirrors the hinge/handle side, and real deployments must encounter both handednesses. Camera design therefore obeys these constraints:

- Nominal physical mount lies on the trunk sagittal centerline (`Y=0`) with zero nominal yaw. A fixed right- or left-offset mount is not accepted merely because it performs well on the current one-sided asset.
- The first documentation-level search seed was parent `trunk`, optical-frame position `[0.320,0.000,0.250] m`, RPY `[0,-6,0]°`, quaternion `[0.998629535,0.0,-0.052335956,0.0] wxyz`, convention `world`. It ranked fourth in the historical `v13_A` stage1–4 sweep and third in the `v16_B` stage1–5 sweep; it remains a search baseline, not a final transform.
- The preferred frame chain is `trunk -> mechanical_mount -> calibrated_optical_frame -> sensor(identity)`. `sensor(identity)` is valid only after the measured housing-to-optical correction is represented by `calibrated_optical_frame`.
- Pose sweeps start from the centerline seed. Optional lateral/yaw ablations must be mirror pairs: `(+Y,+yaw)` and `(-Y,-yaw)` with identical X/Z/pitch, evaluated on identical mirrored state sets.
- First symmetry validation covers current `right/out` and mirrored `left/out`. `in/out` push/pull is a separate task-semantics expansion and is not silently included in this camera brief.
- Cropping, augmentation, visibility masks and score regions must also be left/right symmetric. No fixed crop may privilege the handle side in the current right-only asset.
- A recommendation cannot be frozen while either handedness systematically loses handle/gripper visibility or behavior. Report per-handedness results and the paired gap rather than hiding it in an aggregate mean.

## 5. Known camera evidence and pose-sweep results

### 5.1 What is known

- R13 seed0 camera-only probe completed all 34 geometry/RGB boundaries at `384×216`. Door, handle and gripper-marker region were visible.
- The visual result was only `PASS_PROVISIONAL`: tilted, side-biased, close and partially self-occluded. It was not a final mount, not multi-seed evidence and not physical-hardware validation.
- `v13_A` qualitative eval used the external three-camera diagnostic setup. Those videos support behavior interpretation only and do not validate an onboard camera choice.

### 5.2 R14 transform resolution

The dedicated same-step GPU probe closed R14. The live camera prim matched the verified trunk plus configured local offset with `0.0 m` position error and `2.0803985e-07 rad` orientation error. Default cached `CameraData` differed from the live prim by `0.8946629167 m`; temporarily enabling `update_latest_camera_pose` and forcing one sensor update reduced the live error to `0.0 m` and `1.3485386e-07 rad` without advancing the physics counter. The root cause is stale initialization pose in default `CameraData`, not the parent, local offset, or quaternion convention. Diagnostics must reuse the `TiledCamera`'s initialized view; creating a second same-path view can perturb Fabric/USD state.

### 5.3 Historical `base_v13_A` stage1–4 Gemini 335L sweep

The first eval-only sweep reused the sealed `base_v13_A` Teacher checkpoint `model_step_003000.pt` with SHA-256 `d576ca4bc6f596e45a8d744ca766164b374f8aba4409b06bcd7c460d6b057a36`; no training ran. It evaluated one legacy control plus seven centerline candidates in one 16-env seed0 rollout. For every sample it reused the existing `TiledCamera`, set and read back each local pose, rendered all candidates without advancing physics, and required both RGB/segmentation diversity and exact runtime intrinsics. The sealed local summary is `/tmp/a2_camera_pose_sweep_16env_seed0_20260722/camera_pose_sweep_summary.json`.

That historical stage1–4 ranking selected `z_low_020`: local pose on `trunk` `[0.320,0.000,0.200] m`, RPY `[0,-6,0]°`, quaternion `[0.9986295348,0,-0.0523359562,0] wxyz`, score `0.9230179028`. Its handle, handle-plus-both-fingers, door-panel, and centered-handle rates were `0.9697357204/0.8729752771/0.9799658994/0.8738277920`. The remaining search order was `x_far_036`, `x_near_028`, `center_seed`, `pitch_up_12`, `pitch_level_00`, `z_high_030`, then the zero-scoring legacy control.

This was only a historical right/out search result. The full-task stage1–5 evidence below supersedes it for choosing the next search center; it was never a frozen simulation camera or physical mount.

### 5.4 `base_v16_B` stage1–5 sweep with per-candidate videos

The final eval-only run used mainline checkpoint `logs_rl/a2_piper_full_stage_a2_base/base_v16_B_m29_m32_mass80_160-20260721_230405/model_step_002000.pt` (SHA-256 `5628a25ee53395ddc581d2da184c32635e109ff3691e54a823ad054236475e3f`) and adjacent config (SHA-256 `3c8aead9025b66a7f6f2ac3afc81bedc9cdafa1d12bd08fd43058eff8b4fd144`). The clean mainline runtime was pinned to commit `815b367f5de2a52b26a4b872d0457af8817d01bd`; only the dedicated camera-sweep overlay came from this worktree. No trainer ran and `training_performed=false` is sealed.

The 16-env seed0 rollout completed 16 episodes: `15/16` reached the goal, env0 ended by stage0 overtime, and env1–15 reached stage5. Exact ranking stages were `[1,2,3,4,5]`, with matched samples per candidate of `298/238/397/876/839`. Pose readback, render diversity, runtime intrinsics (`0 px` maximum error), and unchanged physics counter all passed. The sealed summary is `logs_eval/a2_camera_pose_sweep_v16B_ckpt2000_stage1_5_16env_seed0_env1_20260722_2325/camera_pose_sweep_summary.json`.

| Rank | Candidate | Stage1–5 score |
|---:|---|---:|
| 1 | `x_near_028` | `0.5614803625` |
| 2 | `pitch_up_12` | `0.5484327795` |
| 3 | `center_seed` | `0.5324395770` |
| 4 | `z_high_030` | `0.5177492447` |
| 5 | `x_far_036` | `0.4969788520` |
| 6 | `pitch_level_00` | `0.4939388218` |
| 7 | `z_low_020` | `0.4914086103` |
| 8 | `legacy_pose_control` | `0.0` |

The numerical winner `x_near_028` is on `trunk` at `[0.280,0.000,0.250] m`, RPY `[0,-6,0]°`, quaternion `[0.9986295348,0,-0.0523359562,0] wxyz`. Its aggregate ranked handle, handle-plus-both-fingers, door-panel, and centered-handle rates are `0.6367069486/0.4339123867/0.7265861027/0.5185045317`.

All eight candidates wrote independent `384×216`, 10 fps MP4s from env1, 224 frames each. The selected trajectory covers stage0–5 with frame counts `32/18/18/26/64/66`; sealing requires every ranked stage to be present. Every MP4 was decoded end-to-end with ffmpeg. Manual contact sheets at frames 58/120/180 cover stage2/stage4/stage5 and are stored under the run's `manual_qa/` directory.

Numerical and manual evidence agree on a major limitation: all seven centerline search poses lose most useful task geometry in stage5. For `x_near_028`, stage5 handle visibility is `0.0953516091`, handle-plus-both-fingers `0.0500595948`, door panel `0.1370679380`, centered handle `0.061978546` and handle-pixel p50 `0`. Manual stage5 frames are dominated by floor/wall rather than the opening corridor. Therefore `x_near_028` is only the **next search center**. No candidate in this grid is accepted as the final simulation camera or physical mount; production camera config and Student observation remain unchanged. The next sweep must explicitly improve stage5 corridor/door-frame coverage and later repeat on mirrored `left/out` before any mount decision.

## 6. Cloud research questions

### 6.1 Comparable systems

Find concrete dog/quadruped + arm platforms, papers and open projects. Search seeds may include Spot+Arm, ANYmal/ALMA-style systems, Unitree quadruped+Z1 systems, and other legged mobile manipulators, but include an item only after verifying it from a primary source.

For every included system collect:

- platform and arm model;
- task type, especially door/handle/cabinet/valve or close-contact manipulation;
- camera count and whether each camera is onboard, wrist-mounted, head/trunk-mounted or external;
- exact parent frame/link and mount location if published;
- angle/pose or enough calibration data to recover it;
- RGB, stereo, RGB-D, fisheye or event modality;
- sensor model;
- resolution, frame rate, horizontal/vertical/diagonal FoV;
- minimum depth range and practical near-field behavior;
- shutter type, motion blur considerations, IMU and hardware synchronization;
- whether vision feeds control directly, object pose estimation, mapping, teleoperation or only evaluation;
- source URLs and stable GitHub permalinks.

Evidence priority:

1. official hardware/project documentation;
2. repository code, URDF/Xacro, calibration YAML and launch config;
3. paper and supplementary material;
4. author presentation/video;
5. third-party description.

Do not derive an exact camera angle/model from a photo. Mark unavailable fields `UNKNOWN`.

### 6.2 Architectures to compare

At minimum compare:

1. Single trunk/head RGB or RGB-D camera — closest to current Student contract and cheapest model change.
2. Trunk overview + wrist/forearm close-range camera — likely strongest for approach plus grasp, but requires multi-view observation/model changes and cable/impact analysis.
3. Two fixed onboard cameras with complementary pitch/yaw — avoids a moving wrist stream but adds bandwidth and calibration.
4. Three-camera architecture — only if evidence shows the third view materially resolves a remaining failure; diagnostic cameras are not a justification by themselves.

For each architecture answer:

- Can it see the whole door and handle during stage0?
- Can it keep both handle and gripper visible at stage1/2 near range?
- What fraction of representative arm poses self-occlude the handle?
- Does door swing move the handle out of frame at stage3/4?
- Can it see the doorway/corridor for stage5?
- How sensitive is it to A2 pitch/roll and gait vibration?
- What is the compute, bandwidth and policy-architecture delta relative to one `384×216` RGB stream?
- Can a single physical model serve simulation and real deployment with a credible calibration/noise model?

### 6.3 Sensor/model comparison

Candidate search seeds—not recommendations—may include Intel RealSense D405/D435i/D455, Luxonis OAK-D variants, Stereolabs ZED Mini/2i and Orbbec Gemini-class sensors. Add or remove candidates based on primary evidence.

Compare:

- physical size, mass and center-of-mass impact;
- minimum working distance and depth quality around a gripper/door handle;
- RGB FoV and depth FoV overlap;
- global versus rolling shutter;
- low-light, high-contrast and reflective/dark handle behavior;
- active-IR interference and multi-camera interference;
- vibration resistance and motion blur;
- RGB/depth synchronization, timestamping and ROS/driver maturity;
- USB/Ethernet connector, cable bend radius, bandwidth, power and heat;
- availability and support horizon;
- calibration access and Isaac Sim/ROS integration cost.

Price alone is not a deciding metric. Unsupported estimates must be labeled as estimates with date/region.

### 6.4 Pose and optics proposal

Every recommended onboard camera must include:

- physical parent link;
- proposed `xyz` in meters relative to that link;
- proposed orientation as human-readable roll/pitch/yaw and repo-compatible `wxyz` quaternion;
- declared convention and optical forward/up axes;
- target horizontal/vertical FoV;
- target RGB/depth resolution and frame rate;
- near/far clipping or useful depth range;
- expected visible objects per stage;
- predicted self-occlusion cases;
- mechanical bracket and cable constraints;
- calibration procedure.

The report should propose a pose-search envelope, not only one magic pose. A useful sweep should vary forward/up/lateral offset, pitch and optionally yaw, then score multiple robot/door states. The nominal pose must be centerline/symmetric; every non-zero lateral/yaw candidate must have a mirror-paired counterpart. Include at least reset, staging, pregrasp, close, unlatch, wide-open and doorway-traversal states for both `right/out` and mirrored `left/out`.

## 7. Recommended decision criteria

### 7.1 Hard gates

A recommendation fails if any of the following is unresolved:

- transform chain cannot be reproduced numerically;
- the handle or gripper is systematically outside FoV in a required stage;
- near-field handle/gripper distance is below the sensor’s credible working range;
- Piper or its cable blocks a critical view for a substantial part of the motion;
- proposed mass/mount/cable/power is not physically feasible;
- hardware stream cannot meet the chosen control/inference latency budget;
- the proposal silently changes one-camera Student input into multi-camera input without stating model/training cost.
- the nominal mount, crop or validation set is biased to the current right-opening asset and has no mirrored left-opening evidence.

### 7.2 Ranking dimensions

Rank surviving options on:

- full-stage visibility and pixels-on-handle;
- occlusion robustness;
- motion/vibration robustness;
- sim-to-real fidelity;
- calibration maintainability;
- compute/bandwidth/latency;
- mechanical integration risk;
- availability/cost;
- minimum change from the current Student contract.

The final report must select one recommended architecture. If evidence is close, state the recommended default and the exact experiment that would reverse the choice.

## 8. Repository source map for the cloud session

Read these paths at the pinned commit:

| Topic | Path |
|---|---|
| Student experiment/camera/model | `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml` |
| Student observation contract | `gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml` |
| Simulator defaults | `gr00t/rl/config/simulator/isaacsim.yaml` |
| Camera creation/output/eval cameras | `gr00t/rl/simulator/isaacsim/isaacsim.py` |
| RGB observation preprocessing | `gr00t/rl/envs/legged_base_task/legged_robot_base.py` |
| Static camera contract checker | `gr00t/rl/scripts/smoke_a2_student_camera.py` |
| Gemini 335L pose/intrinsics config | `gr00t/rl/config/camera_pose_sweep/gemini_335l_centerline.yaml` |
| Pose sweep wrapper/runtime overlay | `gr00t/rl/scripts/sweep_a2_student_camera_pose.py`, `run_a2_camera_pose_eval.py` |
| Pose sweep scoring/runtime adapter | `gr00t/rl/utils/a2_camera_pose_sweep.py`, `gr00t/rl/envs/door/door_open_a2_camera_pose_sweep.py` |
| Distillation trainer | `gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py` |
| Vision policy | `gr00t/rl/trl/modules/vision_actor_critic_modules_recurrent.py` |
| Distillation contract tests | `gr00t/rl/tests/test_a2_student_distillation_contract.py` |
| A2+Piper config | `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` |
| A2+Piper URDF | `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf` |
| A2+Piper USD assets | `gr00t/rl/data/robots/A2_Piper/` |
| Door env config | `gr00t/rl/config/env/door_open_a2_base.yaml` |
| Door env implementation | `gr00t/rl/envs/door/door_open_a2_base.py` |
| Door procedural geometry | `gr00t/rl/isaac_utils/playground/env_rand/door.py` |
| Door scenario/randomization | `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` |
| External eval camera config | `gr00t/rl/config/env/base_task.yaml` |
| `v13_A` config | `gr00t/rl/config/ablation/wbmanip/base_v13_A_main.yaml` |
| `v13_A` behavior/eval evidence | `memory/a2-piper/push-open-door-optimization/description.md` and `DONE.md` |
| Student camera R13–R15 evidence | `memory/a2-piper/phase2-student-distillation-a2-piper/description.md`, `TODO.md`, `DONE.md` |
| Door handedness/randomization baseline | `memory/a2-piper/door-asset-randomization-baseline/description.md` |
| Historical multi-camera eval facts | `memory/a2-piper/stage0-2-grasp-terminal/description.md` |
| G1→A2 design map | `scriptsFORhuman/g1_doorman_policy_stack_a2_adaptation_map.md` |
| Archived Cloud Pro research input | `scriptsFORhuman/research_inputs/a2_piper_camera_cloud_pro_report_20260722.md` |

Important artifact boundary:

- `base_v13_A` endpoint checkpoint is local at `logs_rl/a2_piper_full_stage_a2_base/base_v13_A_main-20260716_225345/model_step_003000.pt`, but `logs_rl/` is ignored and the checkpoint is not in GitHub.
- The current full-task camera driver is local in the mainline worktree at `logs_rl/a2_piper_full_stage_a2_base/base_v16_B_m29_m32_mass80_160-20260721_230405/model_step_002000.pt`; its adjacent resolved config and all `logs_eval/` videos are also ignored and not remotely visible.
- Current Student experiment keeps Teacher artifact fields as required placeholders. The historical one-update distillation proof used a sealed `base_v10_D` Teacher artifact, not `base_v13_A` or `base_v16_B`.
- Choosing or evaluating a camera does not itself switch the Student distillation Teacher artifact. Any later distillation run targeting a new Teacher still needs a separately sealed checkpoint/config/manifest triplet.

## 9. Required cloud deliverable

Return one Markdown report with:

1. An answer-first recommendation in no more than ten lines;
2. Current-repo camera/robot/task baseline, with pinned permalinks;
3. Comparable-system evidence table;
4. Sensor-model comparison table;
5. Architecture comparison for one/two/three cameras;
6. Exact proposed mount frames, positions, orientations and optics;
7. Stage-by-stage FoV/occlusion analysis;
8. Sim-to-real, calibration, synchronization and latency analysis;
9. Recommended validation matrix and pass/fail thresholds;
10. Unknowns and the smallest user measurements needed;
11. A source list with primary sources and access dates;
12. A clear separation of `SOURCE FACT`, `DERIVED`, `INFERENCE` and `UNKNOWN`.

The cloud session is read-only. It must not edit the repository, open a PR, change camera config, or claim runtime validation.

## 10. Historical copy-paste prompt used for the cloud session

The following prompt is preserved verbatim as research provenance. Its `v13_A` behavior target, `z_low_020` recommendation and commit pin describe the original cloud-session intake; the later `v16_B` stage1–5 evidence and `x_near_028` next-search decision in Section 5.4 supersede those parts for current camera work.

> 你是一个只读的 robotics/camera research agent。请为 A2 四足底盘 + Piper 单臂的 door-opening vision Student 做 camera 方案调研。不要修改仓库、不要开 PR、不要运行昂贵训练。最终输出一份中文 Markdown 研究报告，并对每个关键事实给出 primary source URL 或 pinned GitHub permalink。
>
> 远程仓库：https://github.com/Jam-Stark/DoorDog
>
> 目标分支：`codex/a2-v13-student-distillation-20260717_2103`
>
> 固定审计 commit：`843795013329d9478634c6d87db9756210a311ba`
>
> Branch URL：https://github.com/Jam-Stark/DoorDog/tree/codex/a2-v13-student-distillation-20260717_2103
>
> Pinned URL：https://github.com/Jam-Stark/DoorDog/tree/843795013329d9478634c6d87db9756210a311ba
>
> 任务目标：为 Student 选择能模仿 `base_v13_A` intermediate door-opening behavior 的 camera 架构。`v13_A` 并非 full success：现有 seed0 evidence 为 `0/16 goal`、`16/16 stage4`、`4/16 stage5`，hinge terminal p50 约 `1.276 rad`。目标是看清并学习接近门、对准 handle、Piper 闭合、持续双侧夹持和推门；不要把它表述成完整穿门能力。
>
> 先做 repo audit。必须读取：
>
> - `gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml`
> - `gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml`
> - `gr00t/rl/config/simulator/isaacsim.yaml`
> - `gr00t/rl/simulator/isaacsim/isaacsim.py`
> - `gr00t/rl/envs/legged_base_task/legged_robot_base.py`
> - `gr00t/rl/scripts/smoke_a2_student_camera.py`
> - `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml`
> - `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf`
> - `gr00t/rl/config/env/door_open_a2_base.yaml`
> - `gr00t/rl/envs/door/door_open_a2_base.py`
> - `gr00t/rl/isaac_utils/playground/env_rand/door.py`
> - `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`
> - `gr00t/rl/config/env/base_task.yaml`
> - `gr00t/rl/config/ablation/wbmanip/base_v13_A_main.yaml`
> - `memory/a2-piper/push-open-door-optimization/description.md`
> - `memory/a2-piper/phase2-student-distillation-a2-piper/description.md`, `TODO.md`, `DONE.md`
> - `memory/a2-piper/door-asset-randomization-baseline/description.md`
> - `memory/a2-piper/stage0-2-grasp-terminal/description.md`
> - `scriptsFORhuman/g1_doorman_policy_stack_a2_adaptation_map.md`
>
> Repo baseline to verify, not blindly repeat: current deployable Student uses one programmatically spawned trunk camera at local position `[0.25,0,0.14] m` and quaternion `[0.315631686,0.134503192,-0.390177116,-0.854428083] wxyz`, convention `world`, RGB-only `384×216`, about `69.4°×42.5°` FoV, clipping `0.1–20 m`. The Student contract is `81D proprio + RGB -> 12D`. The three `main/handle_top/handle_side` cameras are external eval views, not onboard Student inputs. The A2+Piper robot has 20 DoF; Piper is fixed to `trunk` at `[0.145,0,0.154] m`, so arm/camera self-occlusion is critical.
>
> Current decision to respect: the first-stage preferred candidate is one trunk-mounted Orbbec Gemini 335L, using source capability `1280×800@60 fps` RGB and a calibrated centered 16:9 crop/resize to the existing `384×216` Student input. Its nominal mount must be trunk-centerline `Y=0`, yaw `0°`. A local right/out-only simulation sweep now recommends `[0.320,0.000,0.200] m`, RPY `[0,-6,0]°`, quaternion `[0.998629535,0,-0.052335956,0] wxyz` as the next simulation default; it is not a frozen physical mount and still requires mirrored left/right validation. Gemini 305 is an optional wrist-camera upgrade only if the one-camera mirrored visibility gate fails.
>
> Treat R14 as resolved by the later same-step GPU probe: the configured local pose and live camera prim close numerically, while default `CameraData` is a stale initialization pose because `update_latest_camera_pose=false`. Do not reopen R14 or tune against cached `CameraData` without contradictory evidence. The later right/out pose sweep is diagnostic evidence, not physical/mirrored validation.
>
> Then search primary sources for existing quadruped/dog + arm platforms, papers and projects. For each, capture platform/arm, task, camera count, onboard vs wrist/external placement, parent frame, pose/angle, model, modality, FoV, resolution, fps, minimum depth, shutter, synchronization and how vision is used. Use official docs, repo calibration/URDF/launch files and papers before videos. Never infer exact parameters from a photo; use `UNKNOWN`.
>
> Compare at least four architectures: (1) one trunk/head RGB or RGB-D camera, (2) trunk overview + wrist close-range camera, (3) two complementary fixed onboard cameras, and (4) three cameras only if the third has demonstrated value. Treat Gemini 335L as the selected first-stage target and Gemini 305 as the optional wrist candidate; evaluate RealSense D405/D435i/D455, OAK-D and ZED Mini/2i only as alternatives or evidence that could reverse the choice. Compare near-field handle depth, FoV, shutter/motion blur, vibration, active-IR interference, synchronization, mass, size, power, heat, cabling, bandwidth, driver maturity, availability and Isaac Sim/ROS integration.
>
> Analyze visibility at reset/approach, staging, pregrasp, finger close, unlatch, wide-open and doorway traversal. Cover the current door range: width `0.8–1.1 m`, height `1.9–2.2 m`, handle height `0.85–0.95 m`. The source scenario is fixed `right/out`, but the camera design and validation matrix must include mirrored `left/out`; do not bias the physical mount, yaw or crop to the current handle side. Account for 50 Hz high-level control, A2 pitch/roll/gait vibration, Piper sweep and door swing.
>
> Give a concrete recommendation, not only a survey. Provide:
>
> 1. recommended camera count and models;
> 2. a minimum one-camera fallback and optional higher-capability variants;
> 3. for every camera: parent link, xyz meters, roll/pitch/yaw, wxyz quaternion, convention, FoV, resolution, fps, useful depth range and expected stage coverage;
> 4. predicted occlusion/failure cases and mechanical/cable constraints;
> 5. compute/bandwidth/model changes relative to one `384×216` stream;
> 6. a pose-search envelope and representative-state validation matrix;
> 7. hard pass/fail thresholds;
> 8. sim-to-real calibration/randomization plan;
> 9. unknown physical measurements to request from the user;
> 10. what evidence would reverse the recommendation.
>
> Mark every substantive item as `SOURCE FACT`, `DERIVED`, `INFERENCE` or `UNKNOWN`. Use pinned commit links where possible. Do not claim that remote absence of `logs_rl/logs_eval` means local artifacts do not exist, and do not conflate camera selection with switching the Student Teacher from the historical sealed `base_v10_D` artifact to the desired `base_v13_A` artifact.
