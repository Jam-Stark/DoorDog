# A2+Piper Camera 方案云端调研 Brief

Last updated: 2026-07-22 HKT

Status: `RESEARCH_BRIEF / READ_ONLY_INPUT`。本文记录当前仓库事实、已知风险、云端调研问题与交付格式；它不是最终 camera 选型，也不授权修改仿真、训练或机器人资产。

## 1. Destination 与停止条件

本调研服务于 A2 四足底盘 + Piper 单臂的视觉 Student distillation。目标不是笼统寻找“最好的相机”，而是给出一套能支持 Student 模仿 `base_v13_A` 已观察到的开门行为、且具有实机可落地性的 camera 方案。

准确的行为目标是：

- 从门前接近并对准 handle；
- 观察 Piper gripper 与 handle 的相对关系，完成接近、闭合和持续双侧夹持；
- 在 A2 姿态变化、Piper 运动和门扇转动时继续保留关键视觉线索；
- 模仿 `v13_A` 的 intermediate opening behavior：持续夹持并推动门，而不是虚报完整穿门成功。

`v13_A` 的现有 seed0 evidence 是 `0/16 goal`、`16/16 stage4`、`4/16 stage5`，hinge terminal p50 约 `1.276 rad`。它证明门运动和持续双侧夹持有明显突破，但不是 full-success policy，也不是统计意义上的最终 winner。因此 camera 调研的 stopping condition 是：

1. 核清当前 Camera/robot/task contract；
2. 形成有来源的狗+臂平台、paper、project 与传感器对照表；
3. 给出一个明确的推荐方案，以及一套最小单 camera、推荐双 camera、可选三 camera 方案；
4. 每套方案给出数量、安装 parent/link、位置、朝向、FoV/分辨率/帧率、型号候选、遮挡与集成代价；
5. 明确哪些结论来自 source，哪些是推断，哪些仍需物理测量或仿真 sweep；
6. 给出先验证 transform、再做 pose sweep、最后改 observation/model 的执行顺序。

## 2. Repository pin 与远程入口

| Item | Value |
|---|---|
| Remote repository | https://github.com/Jam-Stark/DoorDog |
| Target branch | `codex/a2-v13-student-distillation-20260717_2103` |
| Remote branch URL | https://github.com/Jam-Stark/DoorDog/tree/codex/a2-v13-student-distillation-20260717_2103 |
| Pinned source commit | `843795013329d9478634c6d87db9756210a311ba` |
| Pinned source URL | https://github.com/Jam-Stark/DoorDog/tree/843795013329d9478634c6d87db9756210a311ba |
| Dedicated local worktree | `/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103` |
| Local IsaacLab source pin | `/home/baoquanc/workspace/IsaacLab` at `c22775241e28f465fe345fa1a482ad6d29d712b0` |

云端调研应优先使用 pinned commit 生成永久链接，再用 target branch 检查后续变动。`logs_rl/` 与 `logs_eval/` 被 Git ignore；远程仓库能看到 config、source 和 memory 结论，但看不到本地 checkpoint、MP4 与大体积 runtime artifacts。不得把“远程看不到 artifact”误写成“artifact 不存在”。

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
| Door opening side/direction | right / out in the current scenario |
| Current staging band | X `0.55–0.60 m`, Y tolerance `0.15 m` |
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

## 5. Known camera evidence and unresolved blockers

### 5.1 What is known

- R13 seed0 camera-only probe completed all 34 geometry/RGB boundaries at `384×216`. Door, handle and gripper-marker region were visible.
- The visual result was only `PASS_PROVISIONAL`: tilted, side-biased, close and partially self-occluded. It was not a final mount, not multi-seed evidence and not physical-hardware validation.
- `v13_A` qualitative eval used the external three-camera diagnostic setup. Those videos support behavior interpretation only and do not validate an onboard camera choice.

### 5.2 Transform blocker

R14 recorded a numerical inconsistency:

- `CameraData.pos_w` versus `trunk_pos + R(trunk_quat) * [0.25,0,0.14]` error norm: `0.859750361 m`;
- measured camera-to-trunk distance: `1.104684372 m`;
- configured offset norm: `0.286530976 m`;
- measured forward-axis up component corresponded to about `0.94°` upward, not the previously assumed large upward pitch.

The mechanism remains `INCONCLUSIVE`. Candidate explanations include stale `CameraData.pos_w` because `update_latest_camera_pose` is false, Fabric/USD synchronization behavior, a same-named authored camera prim, or comparing different frames/times. Before any pose recommendation is implemented, run one targeted high-level probe that records, at the same simulation step:

1. `robot.data` trunk position/quaternion;
2. `XformPrimView('/World/envs/env_.*/Robot/trunk')` world transform;
3. the configured offset transformed from the verified parent pose;
4. camera prim world transform from `XformPrimView`;
5. `CameraData.pos_w` and all available quaternion conventions;
6. `update_latest_camera_pose` effective value;
7. whether `/Robot/trunk/ego_camera` existed before `TiledCamera` construction.

Do not tune quaternions against an unverified transform chain.

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

The report should propose a pose-search envelope, not only one magic pose. A useful sweep should vary forward/up/lateral offset, pitch and optionally yaw, then score multiple robot/door states. Include at least reset, staging, pregrasp, close, unlatch, wide-open and doorway-traversal states.

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
| Historical multi-camera eval facts | `memory/a2-piper/stage0-2-grasp-terminal/description.md` |
| G1→A2 design map | `scriptsFORhuman/g1_doorman_policy_stack_a2_adaptation_map.md` |

Important artifact boundary:

- `base_v13_A` endpoint checkpoint is local at `logs_rl/a2_piper_full_stage_a2_base/base_v13_A_main-20260716_225345/model_step_003000.pt`, but `logs_rl/` is ignored and the checkpoint is not in GitHub.
- Current Student experiment keeps Teacher artifact fields as required placeholders. The historical one-update distillation proof used a sealed `base_v10_D` Teacher artifact, not `base_v13_A`.
- Choosing a camera does not itself switch the Teacher artifact. A later distillation run targeting `v13_A` still needs a separately sealed checkpoint/config/manifest triplet.

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

## 10. Copy-paste prompt for the cloud session

Use the following prompt verbatim or attach this brief and use the shortened first paragraph:

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
> - `memory/a2-piper/stage0-2-grasp-terminal/description.md`
> - `scriptsFORhuman/g1_doorman_policy_stack_a2_adaptation_map.md`
>
> Repo baseline to verify, not blindly repeat: current deployable Student uses one programmatically spawned trunk camera at local position `[0.25,0,0.14] m` and quaternion `[0.315631686,0.134503192,-0.390177116,-0.854428083] wxyz`, convention `world`, RGB-only `384×216`, about `69.4°×42.5°` FoV, clipping `0.1–20 m`. The Student contract is `81D proprio + RGB -> 12D`. The three `main/handle_top/handle_side` cameras are external eval views, not onboard Student inputs. The A2+Piper robot has 20 DoF; Piper is fixed to `trunk` at `[0.145,0,0.154] m`, so arm/camera self-occlusion is critical.
>
> Treat the current transform as unresolved. R14 found a `0.859750361 m` mismatch between `CameraData.pos_w` and the expected trunk+offset transform. Check the exact IsaacLab API and note that current `CameraCfg` defaults `update_latest_camera_pose=false`; this is a hypothesis, not a proven root cause. Recommend no pose tuning until a same-step parent/sensor transform probe resolves it.
>
> Then search primary sources for existing quadruped/dog + arm platforms, papers and projects. For each, capture platform/arm, task, camera count, onboard vs wrist/external placement, parent frame, pose/angle, model, modality, FoV, resolution, fps, minimum depth, shutter, synchronization and how vision is used. Use official docs, repo calibration/URDF/launch files and papers before videos. Never infer exact parameters from a photo; use `UNKNOWN`.
>
> Compare at least four architectures: (1) one trunk/head RGB or RGB-D camera, (2) trunk overview + wrist close-range camera, (3) two complementary fixed onboard cameras, and (4) three cameras only if the third has demonstrated value. Candidate sensor search seeds may include RealSense D405/D435i/D455, OAK-D, ZED Mini/2i and Orbbec Gemini, but do not recommend by brand familiarity. Compare near-field handle depth, FoV, shutter/motion blur, vibration, active-IR interference, synchronization, mass, size, power, heat, cabling, bandwidth, driver maturity, availability and Isaac Sim/ROS integration.
>
> Analyze visibility at reset/approach, staging, pregrasp, finger close, unlatch, wide-open and doorway traversal. Cover the current door range: width `0.8–1.1 m`, height `1.9–2.2 m`, handle height `0.85–0.95 m`, right/out opening. Account for 50 Hz high-level control, A2 pitch/roll/gait vibration, Piper sweep and door swing.
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
