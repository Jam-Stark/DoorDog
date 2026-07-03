---
name: door-asset-openio-sign
scope: 静态核查 door asset 中 doorOpenIO 字段对 door 构造、hinge joint sign、reward routing 的实际影响
status: active
last_updated: 2026-07-03 16:16 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/door-asset-openio-sign/description.md
  - memory/a2-piper/door-asset-openio-sign/TODO.md
  - memory/a2-piper/door-asset-openio-sign/DONE.md
read_when:
  - 开始 stage3/open reward adaptation、push_door_hinge / push_door_handle sign 验证前
  - 需要判断 in/out 门是否需要不同 reward 公式或 sign flip 时
  - 设计或审核 push_door_force A2-specific force projection 前
---

# Door Asset doorOpenIO / Hinge Joint Sign 静态核查

## Purpose

记录对 origin G1 与 A2_Piper door asset / env 中 `doorOpenIO`（"in"/"out"，即拉门/推门）字段的静态核查结论。本 entry 回答两个核心问题：

1. G1 原版 env 到底是推门 out-only 还是同时训练推门 (out) 和拉门 (in)？
2. 如果同时训练推/拉，为什么 G1 的 `push_door_force` 只奖励 world -x 方向力 (推门 out) 还能 work？

## 核查结论（先看这里）

### 1. doorOpenIO 字段在 door asset 构造里**完全未被使用**

核查文件：
- Origin: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/isaac_utils/playground/env_rand/door.py`
- A2 (与 origin diff 已确认): `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/isaac_utils/playground/env_rand/door.py`

`door_open_io` 变量在 door.py 里只有 4 处使用（line 49/79 config、line 196-206 采样与赋值、line 931 写 metadata、line 1074 从 metadata 读取），**没有任何一处把 `door_open_io` 用于 hinge joint 构造、joint axis、joint limit、handle 位置、panel 旋转或 spawn 朝向**。

door.py 中所有影响 door 物理构造的方向变量只有 `door_open_lr`（left/right 铰链侧）。`door_open_lr` 影响的是：hinge joint LocalPos0 的 Y 方向、handle prim 位置、handle inside/outside 旋转等几何镜像（line 360/380/397/417/432/451/474/475/500/502/524/536/552/554/572/583）。

### 2. hinge joint 与 handle joint 的 axis / limit / target 在 origin 与 A2 中完全相同且固定

| 项目 | hinge joint | handle joint |
|---|---|---|
| axis | `"Z"` (line 473) | `"X"` (line 498) |
| lower limit | `0.0` (line 477) | `0.0` (line 504) |
| upper limit | `150` (line 478) | `45` (line 505) |
| drive target | `-10.0` (line 480) | `-15.0` (line 507) |
| 与 door_open_io 关系 | **无关** | **无关** |
| 与 door_open_lr 关系 | 仅 LocalPos0 Y 方向镜像（line 474），axis/limit/target 不变 | 仅 LocalPos0 Y 方向镜像 + `door_open_lr==-1` 时 LocalRot0 翻转（line 502-503） |

含义：**对 in 门（拉门）和 out 门（推门），door asset 的物理几何、joint axis、joint sign、limit 完全相同**。"开门"动作在两种门里都对应 hinge angle 从 0 增长到 +150°。

### 3. doorOpenIO 在 env 里只用于 privileged obs，不参与 reward / stage routing

核查文件：
- Origin: `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`
- A2: `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`

**Origin env 使用位置**：
- line 94-95: 声明 `self.door_open_lr` 与 `self.door_open_io` tensor
- line 106: 只读 `door_metadata["doorOpenLR"]`，**`doorOpenIO` 没有对应的 `self.door_open_io[env_id] = door_metadata["doorOpenIO"]` 读取**
- line 683: `door_open_io` 在 `_get_obs_privileged_door_info()` 中被塞进 privileged obs stack（teacher 输入）

**A2 env 使用位置**：
- line 295-296 / 403-404: 两处声明（scene_creation_callback 与另一个 init path）
- line 307 / 415: 读 `door_metadata["doorOpenLR"]`（A2 比 origin 多读了这个字段但同样只塞 tensor，不用于 routing）
- line 1989: 塞入 privileged obs stack

**Reward / stage routing**：origin 与 A2 的所有 `torch.where(self.door_open_lr ...)` routing 都只按 `door_open_lr` 切 left/right hand（origin line 264/269/287/291/348/370/415/502/886；A2 line 607/696/839/861/881/886/931/1156/2322/2414），**无任何 `door_open_io` 的 reward sign flip 或 stage condition 切换**。

### 4. door reset / robot reset 同样不依赖 doorOpenIO

- Origin `_reset_door_states()` (line 766-787)：reset door dof state，无 `door_open_io` 分支
- Origin `_reset_root_states()` (line 722-739)：robot target root pos 随机化 `x ∈ [-1.5, -0.6]`、`y ∈ [-0.5, 0.5]`、yaw `∈ [-π/4, π/4]`，**无 `door_open_io` 依赖**

### 5. 关于"为什么 G1 能混训推/拉"

上一轮回答中曾给出一个未验证推断："G1 用 world -x force reward 只奖励推门 out，但混训推/拉还能 work 是因为机器人站位不同"。**这个推断在本次静态核查中无法被 door.py / env.py 证据支持**。

实际证据显示：
- door asset 物理构造对 in/out 门完全相同，hinge 都朝 +upper limit 开
- `doorOpenIO` 没有任何显式的 robot 站位 / door 朝向切换逻辑
- 唯一与 in/out 有关联的地方是 privileged obs 中把 `door_open_io` 喂给 teacher policy

可能解释（**未经 runtime 验证，只作为假设**）：
- (a) **door asset 的 spawn 位置 / 整体 yaw 可能在更上层 sim scene config 中按 `doorOpenIO` 做了 180° 旋转**，这样 in 门和 out 门在 world frame 里看起来是镜像的，但本核查未覆盖 `scenario_cfg/isaacsim.py` 与 `a2_base.py` 中的 spawn 调用，**留作 TODO 验证**。
- (b) **`door_open_io` 当前只是 metadata 里的一个标签字段**，origin 作者可能预留了这个字段但尚未在 env 里真正使用它切换物理/站位；如果是这样，那么训练时 in/out 门在物理上是**同一个门**，policy 只学到了"把 hinge 推开"这个动作——这种情况下 in/out 标签只是 privileged obs 噪声，实际训练分布只有"out/推"方向。
- (c) **`push_door_force` 的 world -x bias 确实可能只对 out 门有效**，但因为其 scale 只有 +0.3（远小于 `push_door_handle` / `push_door_hinge` 各 +6.0），主驱动来自 door articulation joint progress，所以即使 in 门样本拿不到 force bonus，hinge/handle progress reward 仍能驱动学习。

**哪种解释为真需要 runtime smoke 或进一步读 scenario_cfg / spawn 逻辑确认**，本静态核查无法定论。

## 对 stage3 reward adaptation 的影响

### `push_door_hinge` / `push_door_handle` — PASS baseline 维持

这两个 reward 只依赖 `door.data.joint_pos[:, 0/1]` 与 `joint_vel[:, 0/1]`，**与 `door_open_io` 完全无关**。由于 hinge joint 在所有门里都朝 +upper limit 开，这两个 reward 对 in/out 门天然对称。

**不需要为 in/out 门做 sign flip 或方向特化**。

### `push_door_force` — 维持 PASS disabled / TODO design

stage3 checklist 原本就标这个 term 为 disabled。本次核查进一步确认：
- 原 G1 `push_door_force` 只奖励 world -x 方向力（door_open_homie.py line 500-503，注释 "reward -x direction force (pushing the door)"）
- 在 `door_open_io` 没有任何 sign flip 介入的情况下，这个 reward **对 in 门可能恒为 0**（如果解释 (b)/(c) 成立）
- A2 后续若启用 `push_door_force`，**必须做 door-frame 或 source-frame 投影**，不要用 world-x 方向；且如果未来确实要混训 in/out 门，force projection 必须对两个方向都成立

### stage3→4 advance condition `joint_pos[:, 0] > 0.174533` — PASS baseline 维持

由于 hinge joint sign 对 in/out 门一致（都朝 +upper limit 开），这个 threshold 对 in/out 门都有效，**不需要做 sign flip**。

## Source Files (本次核查实际读取的)

- `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/isaac_utils/playground/env_rand/door.py`（line 49/79/185-206/339-418/460-515/931/1073-1074）
- `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/envs/door/door_open_homie.py`（line 85-114/255-322/480-533/670-739/766-795/886-944）
- `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/scripts/generate_door_assets.py`（line 624-643）
- `/home/baoquanc/workspace/GR00T-VisualSim2Real/data/door_assets_preview/metadata.json`（示例 metadata）
- `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/isaac_utils/playground/env_rand/door.py`（diff vs origin，仅 line 571/573/583/585 处 handle inside offset 差异，不影响本核查结论）
- `/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py`（line 295-307/403-415/607/696/839-931/1156/1987-1989/2322/2414）
- `/home/baoquanc/workspace/GR00T-VisualSim2Real/gr00t/rl/config/rewards/wbmanip/reward_door_open_homie.yaml`（reward scale 参考）

## TODO Summary

- 2026-06-29 15:56 HKT - 静态核查 door asset / env 中 `doorOpenIO` 字段是否影响 hinge joint sign、reward routing、stage condition。**已完成**：`doorOpenIO` 在 door 构造与 reward routing 中完全未被使用，只作为 privileged obs 标签。
- 2026-07-03 16:16 HKT - 当前 origin G1 与 A2 training scene 的 `scenario_cfg/isaacsim.py` 均已确认固定 `door_open_lr=["right"]`、`door_open_io=["out"]`，并无 `doorOpenIO` 驱动的 spawn yaw / robot stance 切换。后续如果真的启用 in/out mixed randomization，仍需 runtime/GUI smoke 验证物理表现与 task semantics。
- 2026-06-29 15:56 HKT - 后续若 A2 要启用 `push_door_force`，必须基于 door-frame 或 source-frame force projection 设计，不使用 world-x；如混训 in/out，force projection 必须方向对称。

## DONE Summary

- 2026-06-29 15:56 HKT - 完成静态核查：`doorOpenIO` 在 origin G1 与 A2 door.py 中只赋值、写 metadata、读取到 env，不参与任何 hinge joint 构造、joint axis/sign/limit、reward routing 或 stage condition；hinge joint 对 in/out 门物理构造完全相同（axis Z、lower 0、upper 150、target -10）；`door_open_io` 在 origin/A2 env 中只用于 privileged obs stack；所有 left/right reward routing 只按 `door_open_lr`。`push_door_hinge` / `push_door_handle` / stage3→4 advance condition 对 in/out 门天然对称，维持 PASS baseline。`push_door_force` 维持 PASS disabled / TODO design，后续若启用必须做 door-frame 或 source-frame force projection。
- 2026-07-03 16:16 HKT - 补充完成 scenario/spawn 层静态核查：origin G1 与 A2 的 `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py` 均固定 `door_open_lr=["right"]`、`door_open_io=["out"]`，官方 GitHub `doorman` branch raw file 同样如此；当前训练 baseline 可视为 right-hinge + out-opening，不是 push/pull mixed distribution。详细 randomization 入口事实另见 `memory/a2-piper/door-asset-randomization-baseline/description.md`。
