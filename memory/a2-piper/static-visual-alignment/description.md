---
name: static-visual-alignment
scope: Full Isaac Sim GUI static visualization workflow for A2_Piper-door relative pose/orientation and reward tuning
status: active
last_updated: 2026-06-12 23:05 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/static-visual-alignment/description.md
  - memory/a2-piper/static-visual-alignment/TODO.md
  - memory/a2-piper/static-visual-alignment/DONE.md
  - gr00t/rl/scripts/preview_a2_piper_door_scene.py
  - gr00t/rl/envs/door/a2_piper_door_scene_preview.py
  - gr00t/rl/scripts/README.md
read_when:
  - 启动 A2_Piper door scene 做静态可视化观察前
  - 需要调整 robot 与 door 的初始相对位置、朝向、root pose 或 placement bounds 前
  - 设计/调试 reward、pregrasp target、handle reaching、door progress observation 时需要通过 GUI 观察几何关系前
  - 修改 `preview_a2_piper_door_scene.py` 的 viewer/camera/experience/placement CLI 前
---

# Static Visual Alignment

## Purpose

记录 A2_Piper door preview 的 full Isaac Sim GUI 静态观察 workflow。这个 workflow 用于反复观察 robot 与 door 的相对位置、朝向、reachability、handle/arm 几何关系，并服务后续 observation/reward/pregrasp target 调整。

本 entry 专门约束“静态导入观察”场景：需要完整 Isaac Sim GUI 风格和可移动 viewer，不应默认走 headless camera preview。

## Core Rule

- 静态观察 robot-door relative pose/orientation 时，使用 full Isaac Sim GUI experience：`/home/baoquanc/workspace/IsaacLab/apps/isaaclab.python.kit`。
- 不要使用 `--headless`。
- 不要设置 `ENABLE_CAMERAS=1`，除非当前任务明确是在测试 `TiledCameraCfg` 或 camera sensor。静态对齐观察默认使用 `ENABLE_CAMERAS=0` 或不设置该 env var。
- 不要让这个 workflow 自动切到 `isaaclab.python.headless.rendering.kit`；headless/camera path 只用于 smoke、fixed camera sensor 或 WebRTC camera preview。
- 使用 `--max-steps -1 --reset-interval 0`，让 scene 保持静态可观察状态，直到用户主动关闭或 `Ctrl-C`。
- IsaacSim/UsdRT livestream/camera 相关路径只支持 logical `cuda:0`；需要用 physical GPU `N` 时，用 `CUDA_VISIBLE_DEVICES=N` 暴露成 logical `cuda:0`，脚本仍传 `--device cuda:0`。

## Command Templates

### Single Robot Static Alignment

用于观察当前 stage-0 root pose 下 A2_Piper 与 door 的相对位置和朝向：

```bash
CUDA_VISIBLE_DEVICES=2 PUBLIC_IP=10.120.16.39 LIVESTREAM=1 ENABLE_CAMERAS=0 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/scripts/preview_a2_piper_door_scene.py \
--num-envs 1 \
--device cuda:0 \
--experience /home/baoquanc/workspace/IsaacLab/apps/isaaclab.python.kit \
--max-steps -1 \
--reset-interval 0
```

调 root pose 时优先走 CLI，不要先 hardcode：

```bash
--root-x -0.9 --root-y 0.0 --root-z 0.55 --root-yaw 0.0
```

### Four-Corner Placement Bounds View

用于观察当前 Doorman stage-0 robot reset bounds 的四个顶点。默认 bounds 来自 preview-local constants，镜像 `door_open_a2_base.py::_reset_root_states` 当前 hardcode：x `[-1.5,-0.6]`、y `[-0.5,0.5]`、yaw `[-pi/4,pi/4]`，z 仍来自 `--root-z`。

```bash
CUDA_VISIBLE_DEVICES=2 PUBLIC_IP=10.120.16.39 LIVESTREAM=1 ENABLE_CAMERAS=0 \
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/scripts/preview_a2_piper_door_scene.py \
--placement-preview corners \
--device cuda:0 \
--experience /home/baoquanc/workspace/IsaacLab/apps/isaaclab.python.kit \
--max-steps -1 \
--reset-interval 0
```

如果只想看 XY 四角、不让 yaw 变化混入判断：

```bash
--placement-corner-yaws uniform
```

如果需要围绕当前 `--root-*` 做 preview-only 小范围观察：

```bash
--placement-preview corners \
--placement-bounds root-centered \
--placement-x-half-range 0.35 \
--placement-y-half-range 0.35 \
--placement-yaw-half-range 0.25
```

## Preview Script Adjustment Norms

- `gr00t/rl/scripts/preview_a2_piper_door_scene.py` 负责 launch/CLI/experience 选择；`gr00t/rl/envs/door/a2_piper_door_scene_preview.py` 负责 scene spawn、robot/door articulation 和 reset pose。
- 静态视觉观察相关选项应放在 preview-only entrypoint，不要接训练入口、runner、policy、checkpoint 或 reward execution path。
- 保持默认 single robot preview 行为稳定：`--placement-preview none`、`--num-envs 1`、默认 root pose `x=-0.9, y=0.0, z=0.55, yaw=0.0`。
- full UI static alignment 不应强制创建 `TiledCameraCfg`；`ENABLE_CAMERAS=1` 只在明确需要 camera sensor/fixed camera preview 时使用。
- 需要可视化多个候选 pose 时，优先使用 IsaacLab cloned envs，例如 `--placement-preview corners` 自动 4 env；不要在单 env 里手动堆多个 robot articulation。
- 不要 runtime import `door_open_a2_base.py`、DoorPregrasp、G1/HOMIE、FingerPrimitive 或 hand/contact sensor hardcode。若必须复用稳定数值常量，可在 preview scene 中本地定义 constants，并用注释标明 source path。
- 调整 robot-door 初始相对位置时，先通过 `--root-x/y/z/yaw` 在 full UI 中观察，确认后再决定是否更新默认值、README 或 training config。
- `sim.set_camera_view(...)` 只负责初始 viewer camera；不等同于 fixed sensor camera。full UI 中应允许用户通过 Isaac Sim viewer 自己移动视角。

## Reward Tuning Usage

后续写 reward 时，经常需要用这个 workflow 观察：

- A2_Piper arm/end-effector 到 handle 的 reachability 与初始距离。
- Base yaw、door normal、handle direction 与 arm workspace 是否一致。
- Leg/base collision clearance、door frame clearance、gripper/handle 初始高度差。
- Approach reward、pregrasp reward、handle interaction reward、door angle/progress reward 的几何 reference 是否合理。
- 随机 reset bounds 是否导致一部分 corner 初始状态明显不可达或碰撞。

观察得到的稳定结论应再同步到 observation/reward spec 或后续 experiment progress memory；不要只留在聊天上下文。

## Current State

- 2026-06-12 19:48 HKT - 已建立 full Isaac Sim GUI static alignment memory。静态观察 robot-door 相对位置/朝向的规范命令应使用 `isaaclab.python.kit`、`ENABLE_CAMERAS=0`、不加 `--headless`、`--max-steps -1 --reset-interval 0`。

## TODO Summary

- 2026-06-12 19:48 HKT - 若后续 preview script 新增 `--viewer-mode full-ui/static`、camera sensor disable flag 或专用 visual marker，需更新本 entry 与 `gr00t/rl/scripts/README.md`。
- 2026-06-12 19:48 HKT - Reward tuning 开始后，把已确认的 robot-door relative pose、handle/EE frame、可达性结论与推荐 root pose 同步记录到对应 reward/experiment memory。

## DONE Summary

- 2026-06-12 19:48 HKT - 新建 static visual alignment memory entry，记录 full Isaac Sim GUI experience 命令规范、preview script 调整边界、placement corners 用法与 reward tuning 可视化用途。

## Recommended Next Files To Read

- `memory/a2-piper/worktree-routing/description.md`
- `memory/a2-piper/doorman-door-training-goal/description.md`
- `gr00t/rl/scripts/preview_a2_piper_door_scene.py`
- `gr00t/rl/envs/door/a2_piper_door_scene_preview.py`
