# A2+PiPER `base_v26-7` — 原生双侧 unlatch：几何修复后的 from-scratch 条件策略

**预注册时间：** 2026-09-02（六格启动前冻结）
**上游：** `v26-6` Wave A（`GRIPPER_CAPACITY_CONFIRMED`）与本阶段的 handle target offset 几何审计
**性质：** from-scratch 训练，双因素矩阵，预注册判据；本文冻结后不改阈值、不改矩阵、不事后重解释

---

## 1. 目标

**一个网络（单一 actor）在 Stage0→Stage3 上同时学会 LEFT 与 RIGHT 镜像门的 handle 下压解锁。**

这是标准的多任务 / 条件策略问题，条件信息已核实齐备（§2.1）。Stage4/Stage5 本阶段**只报告、不参与路由**。

## 2. 立论：为什么此前六轮不可能成功

### 2.1 条件信息是齐的（已核实，非推断）

`door_open_a2_base.py:27517` `_get_obs_privileged_door_info` 的第 5/6 槽是 side one-hot：

```python
left  = (self.door_open_lr ==  1.0)
right = (self.door_open_lr == -1.0)
```

它在 **`actor_obs`**（不只是 critic）中，`obs_scale=1.0`、`noise_scale=0.0`。同组还有
`gripper_handle_transform`(18)、`relative_to_door`(9)，噪声同为 `0.0`。因此
「policy 不知道自己面对哪一侧」不成立，瓶颈从来不在信息量。

### 2.2 阻塞一：夹爪执行能力（v26-6 Wave A 已解）

v26 从未覆盖 `dof_effort_limit_list`，沿用 arm_j7/j8 `10/10 N`，而 v18–v25 全部是
`45/45 N` + `1300/32` + M39。Wave A 的 bit-exact 单因素 A/B typed 为
`GRIPPER_CAPACITY_CONFIRMED`：RIGHT `handle≥0.3` 由 `16/64` 升到 `48/64`。

### 2.3 阻塞二：LEFT 抓握目标姿态偏 180°（本阶段定位）

`door_open_a2_base.py:28974,28982` 的 handle/pregrasp `FrameCfg.offset`
硬编码 `rot=(0.5,0.5,0.5,0.5)`，在 `_initialize_impl` 中 `.repeat(num_envs,1)`
广播到所有 clone —— **side-independent**。

该四元数对应 `R_o = [[0,0,1],[1,0,0],[0,1,0]]`（绕 (1,1,1) 转 120°），
**不是镜像不变的**：`mirror(R_o) = M R_o M` 与 `R_o` 相差 **180.00°**（M = diag(1,−1,1)）。
而 `grasp_target` prim 的世界姿态在两侧**都是 identity**（实测互差 `0.18°`），
镜像职责全部落在 offset 上。

恒等式 `mirror(R_g · R_o) = mirror(R_g) · mirror(R_o)`；出厂代码算的是
`mirror(R_g) · R_o`，故 LEFT 目标恒偏 180°。

**runtime 佐证**（Wave A `restored` 逐步 trace）：

| 量 | RIGHT | LEFT |
|---|---:|---:|
| tcp→handle 距离 p50 | `0.0514` | `0.0097` |
| handle 接触力 p50 | `36.0 N` | `44.3 N` |
| `opening / approach alignment` | `0.977 / 0.981` | `0.963 / 0.981` |
| `door_handle_joint_pos` max | `+0.7854` | `+0.00073` |
| `arm_j4`（soft limit `±1.5705`） | target `−0.385` / actual `−0.369` | target `+1.161` / actual `+1.396`，max `+1.762` |

LEFT 抓得更准、夹得更紧，handle 却全程不动，且 `arm_j4` 被夹持反作用力顶出
URDF 上限（`1.745`）。实测 LEFT 目标姿态与 `mirror(RIGHT 成功姿态)` 相差
**`178.64°`**，与代数预测的 `180.00°` 吻合。

**为什么六个版本没发现**：reward 的对齐指标对该误差结构性失明
（`:15383-15386`）——`opening_alignment` 取绝对值、`approach_alignment` 只看 z 分量，
绕 z 的半周旋转在两者上都不可见。

**IK 判决**（pinocchio + 仓库 URDF；FK 复现 trace 误差 median `0.000°`，
IK 自洽性 `0.00e+00 rad`）。对 LEFT 真实抓握状态沿下压轨迹 `θ = 0 → 0.8 rad` 扫描：

```
offset (0.5, 0.5,0.5, 0.5)  出厂值 : 0/25 waypoints reachable（URDF 限位内无解）
offset (0.5,-0.5,0.5,-0.5)  镜像值 : 25/25 全程可达，arm_j4 p50 稳定 −0.60
```

### 2.4 为何必须 from scratch，而非从任何现有 checkpoint 续训

LEFT 侧**不是白纸，而是被强化了 7000+ batches 的错误技能**：它学会把 `arm_j4`
滚到 `+1.396` 顶死限位去对准那个偏 180° 的目标，且该行为一直在被 §2.3 失明的
alignment 指标与 `grasp_target_distance` 支付。修复后正确解在 `−0.60`，
反向偏置 `2.0 rad`。续训需先遗忘高强度强化的错误策略再反向重学，属负迁移。

且 **v26 全系每一个 checkpoint（r0 → Wave B）都训练在该 bug 之上**，不存在干净的
续训起点。共享 LSTM+MLP 下 LEFT 的大幅策略迁移也必然扰动 RIGHT，"保住 RIGHT"
的收益本身打折。

### 2.5 本阶段不动的轴

Stage2→Stage3 每步收入悬崖（`0.28939` vs `0.19655`，`−0.09283/step`）与
`a2_stage3_unlatch_hold` 的 `hinge<0.1` 条件租，**本阶段不改**。依据：v19 在
**完全相同**的 reward scale（`unlatch_hold=3`、`push_door_hinge=6`、
`hold_and_drive=8`、`near_closed=0.1`、K5=5）下做成过全链，故其非必要条件。
`near_closed 0.1→0.25`（Wave B 的 B1 轴）同样不引入。

---

## 3. 矩阵与自变量

全部六格共享，from scratch：

```text
checkpoint: null      checkpoint_load_mode: full      auto_load_latest: false
env.config.a2_v26_door_open_lr: bilateral
env.config.a2_v26_6_side_mirrored_handle_offset_enabled: true      <- 修复二
GRIPPER_CAPABILITY_BUNDLE:                                          <- 修复一
  robot.dof_effort_limit_list[-2:] = [45.0, 45.0]
  robot.control.stiffness.arm_j7/j8 = 1300.0
  robot.control.damping.arm_j7/j8   = 32.0
  env.config.a2_m39_gripper_material_enabled = true
  env.config.a2_stage2_squeeze_force_max     = 30.0
  env.config.a2_stage2_over_force_threshold  = 55.0
num_envs 4096   num_total_batches 6000   save_frequency 250
enable_staged_reset true（训练）   PhysX velocity iterations 2
```

**唯一自变量：`env.config.a2_stage2_squeeze_force_min`**，v26 现值 `0.5` vs v19 值 `2.0`。
它直接进入 K5 gate 谓词（`door_open_a2_base.py:17797`
`sufficient_squeeze = all(|squeeze_y| > squeeze_min)`）。Wave A 实测该 gate 在 `0.5`
下几乎不筛选（Stage3 admission `63/64`），策略可用最小力通过，与「抓不稳→压不住」同构。
这是 v19/v26 之间最后一条从未被测试过的 gate 语义差异。

| cell | GPU | seed | `a2_stage2_squeeze_force_min` |
|---|---:|---:|---:|
| `Q05_S0` | 2 | 0 | `0.5` |
| `Q05_S1` | 3 | 1 | `0.5` |
| `Q05_S2` | 4 | 2 | `0.5` |
| `Q20_S0` | 5 | 0 | `2.0` |
| `Q20_S1` | 6 | 1 | `2.0` |
| `Q20_S2` | 7 | 2 | `2.0` |

三 seed 而非双 seed：v26 已两次因 seed 不稳定得出不可判读结论
（`MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`、`CANONICALIZATION_NOT_SUPPORTED`）。
`GPU0–1` 保留给基线与中期评估，不参与训练。

---

## 4. 前置门（未通过则不得启动六格）

### 4.1 G1 — offset 修复的 runtime 接线确认

64-env、≤5 batch 短跑，`a2_v26_6_side_mirrored_handle_offset_enabled=true`，
dump `target_quat_source_handle`。判据（确定性几何量，不依赖策略）：

```text
LEFT  clone : 新旧 handle 目标姿态相对旋转 = 180° ± 0.5°
RIGHT clone : 新旧 handle 目标姿态 bit-identical
integrity violations = 0
```

任一不满足 → `V26_7_WIRING_NOT_CONFIRMED`，停止，不启动训练。

### 4.2 G2 — Wave B 基线（`45 N` 已恢复、offset 仍错）

`logs_rl/by_batch/base_v26/v26_6_waveB_gripper_capability_20260831/train/` 四格训练
已完成（四份 receipt 已 finalize 为 `PASS`，resolved config contract 静态预检全通过）。
执行其 24 次预注册评估（4 cells × 3 checkpoints × LEFT/RIGHT exact64），
reducer 为 `v26_6_waveB_reduce.py`。

该结果**不选起点**（本阶段 from scratch），只作为 offset 修复的前测：

```text
Wave B endpoint LEFT durable depression == 0   -> 符合预期，继续
Wave B endpoint LEFT durable depression >  0   -> V26_7_PREMISE_CHALLENGED，暂停并交回 Owner
```

后者会推翻「LEFT 的零来自几何而非能力」的立论，必须重新审视再决定是否启动。

---

## 5. 评估与中期读数

每个 milestone 对六格做 LEFT/RIGHT exact64 natural 评估
（`enable_staged_reset=false`，first-episode-only），共 12 次 / milestone，
在 `GPU0–1` 上分批完成，与训练并行。

```text
milestones: step 1000 / 2000 / 3000 / 4000 / 5000 / 6000
```

`durable depression` 沿用 Wave B 已注册定义：**连续 ≥25 control steps 保持
`door_handle_joint_pos ≥ 0.6 rad`**。

---

## 6. 预注册路由与终止规则

### 6.1 endpoint 判据（每 config 需 ≥2/3 seed 满足）

```text
LEFT >= 8/64  且 RIGHT >= 32/64   -> BILATERAL_UNLATCH_SUPPORTED
LEFT >= 8/64  且 RIGHT <  32/64   -> LEFT_RECOVERED_RIGHT_REGRESSED
LEFT == 0     且 RIGHT >= 32/64   -> LEFT_STILL_STRUCTURALLY_ZERO
其余                              -> BILATERAL_UNLATCH_NOT_LEARNED
```

LEFT 门槛 `8` 而非对称的 `32`：LEFT 从结构性的 `0` 起步，本阶段确认的是它
**是否离开零**，不是一步要求双侧对称。

### 6.2 提前成功终止

在任一 milestone，若某 config 有 `≥2/3` seed 满足 `BILATERAL_UNLATCH_SUPPORTED`，
该 config 三格**可停**，以该 milestone 为其 endpoint。
不得因「再等等看会更好」而继续，也不得事后下调阈值。

### 6.3 提前失败终止

```text
step 2000 时六格 LEFT 的 arm_j4 分布仍贴住 soft limit（p95 >= 1.50）
   -> V26_7_FIX_NOT_EFFECTIVE_IN_TRAINING，全部停止
step 4000 时六格 LEFT Stage3 admission 全为 0
   -> V26_7_LEFT_STAGE3_NOT_REACHED，全部停止，不加预算
```

### 6.4 第二读数（报告，不单独路由）

`squeeze_min 0.5 vs 2.0` 的主效应：双侧 durable depression、Stage3 admission、
下压期 handle 接触力 p50、K5 通过率、over-force 步占比。

### 6.5 完整性

每格每侧 exact 64 episode；`integrity_violations = 0`；六格 resolved config 必须满足
capability bundle、`a2_v26_6_side_mirrored_handle_offset_enabled=true`、各自的
`squeeze_force_min`，且 seed 与 cell 名一致。任一不满足即 `V26_7_INVALID`。

多次 milestone 检验会抬高假阳性；本阶段接受该代价，因为目标效应量
（LEFT 由结构性 `0` 变为 `≥8/64`）远大于噪声，且属探索阶段而非确证阶段。

---

## 7. 资源与停止条件

```text
GPU2–7  六格训练，每格独立 tmux + run receipt，CUDA_VISIBLE_DEVICES 限单卡，
        进程内 cuda:0，ACCELERATE_TORCH_DEVICE=cuda:<physical>
GPU0–1  G2 Wave B 基线（前置）与六个 milestone 的中期评估
```

按实测 `20.3 s/update` + 场景构建约 `439 s`，每格约 **34 小时**，六格并行；
中期评估 12 次/milestone 在双卡上约 32 分钟，与训练并行。总墙钟约 **35 小时**。

任一格非零退出即停止该格并保留失败证据：**不重跑、不放宽阈值、不中途改 config、
不追加预算**。checkpoint 每 250 存，进程级中断可从最近 checkpoint 续。

## 8. 结论边界

- 本阶段只对「几何修复 + 夹爪能力恢复后，单一条件策略能否原生学会双侧 unlatch」
  给出 experiment 证据。
- **不**构成 Stage4/Stage5/goal 证据，不更新 Teacher/Student handoff 与 G7 binding。
- **不**构成 hardware、sim-to-real 或部署证据。
- `LEFT_STILL_STRUCTURALLY_ZERO` 不证明条件策略路线不可行；它表明在 6000 batches
  与当前收入结构下未跨过，下一步应处理 Stage2→3 收入悬崖，而非继续加训练量。
