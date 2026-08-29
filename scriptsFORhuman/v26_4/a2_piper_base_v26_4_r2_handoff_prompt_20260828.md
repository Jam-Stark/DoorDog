# Handoff prompt: `base_v26-4` R2 — corrected Wave K and stage continuation

在 `/home/baoquanc/workspace/DoorDog-A2_Piper` 组建 team 并自主闭环完成 `base_v26-4 R2`。
Owner 只验收最终结果。已获批 physical GPU0–3，不得使用 GPU4–7。

## 0. R2 存在的原因

R1 已按预注册 typed stop 完整关闭，执行纪律没有问题：没有猜 posture、没有伪造
canonical 等价、M 如实 `NOT_RUN`/`metrics:null`、无训练 GPU 消耗。**但 R1 的 K 结论
`BILATERAL_ASYMMETRIC_AT_arm_j4` 建立在一个目标位姿设定缺陷上，不成立。**

缺陷与证据（全部可在 R1 产物中复核）：

1. **两侧被给了同一个世界系目标朝向。** R1 收据 9/9 候选的
   `tcp_target_orientation_world_wxyz` 在 LEFT 与 RIGHT 完全相同，均为
   `[0.5, 0.5, 0.5, 0.5]`。成因两处叠加：
   - `gr00t/rl/isaac_utils/playground/env_rand/door.py` 中
     `set_prim_transform(stage, grasp_target_prim_path, (pos...), (0, 0, 0), (1,1,1))`
     ——`grasp_target` prim 的旋转恒为单位阵，**不随 `door_open_lr` 镜像**，只有
     y 位置镜像；
   - `scriptsFORhuman/v26_4/v26_4_k_kinematics_probe.py:167` 的
     `OffsetCfg(rot=(0.5, 0.5, 0.5, 0.5))` 是单一、与侧别无关的常量。

   结果是 seed 镜像了、target 没镜像：RIGHT 被要求到达镜像位置同时保持未镜像朝向。

2. **收据自身已记录该失配。** LEFT 的 `downpress_orientation_error_rad` 为
   `2e-7 – 7e-7 rad`；RIGHT 为 `0.356 – 0.685 rad`（20–39°）。RIGHT 的 IK 从未到达
   被请求的朝向，是在追一个非镜像目标时撞上 `arm_j4` 上界。

3. **真正的镜像解可行且余量大得多。** 取 R1 每个候选 LEFT 的收敛
   `ik_requested_q_arm_j1_to_j6_rad`，按 probe 自己声明的掩码
   `(-1, 1, 1, -1, 1, -1)` 取镜像，9/9 全部在限位内，最小 hard-limit margin
   `0.715 – 0.904 rad`；而 R1 的 RIGHT 解 margin 只有 `0.0009 – 0.038 rad`。
   `arm_j1/j4/j6` 限位关于零对称、`arm_j2/j3` 在镜像下不变，因此镜像解的余量与 LEFT
   逐项相等，是构造性的。

**因此 `arm_j4` 的 `0.003–0.039 rad` overshoot 不是"差一点点不可达"，是 IK 在错误
目标上磨到限位。R2 的第一件事是修正目标构造并加上本该存在的自检。**

## 1. R1 产物处置

R1 的 closure 是对一个有缺陷前提的诚实收口，**保留不动**：不删除、不覆盖、不改写
`logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/`、
`scriptsFORhuman/v26_4/a2_piper_base_v26_4_execution_closure_20260828.md`
与其中的 typed outcome。R2 用新的 output root，并在计划文档新增 R2 段落记录该缺陷、
反证与修正后的 Wave K 规格；不重写历史。

memory 中的 `v26_4_complete_requires_asymmetric_posture` 需在 R2 收口时按新结论更新，
并保留 R1 provenance。

## 2. 先读

严格遵循根 `AGENTS.md` 与项目 file-based memory，随后完整读取：

- `scriptsFORhuman/v26_4/a2_piper_base_v26_4_bilateral_grasp_foundation_plan_20260828.md`
  （§3/§5/§6/§7/§9 仍然有效；§7 预注册判据从未被评估，**不得修改**）
- `scriptsFORhuman/v26_4/a2_piper_base_v26_4_execution_closure_20260828.md`（R1 记录）
- `logs_eval/base_v26/v26_4_bilateral_grasp_foundation_20260828/K/k_kinematics.json`
- `scriptsFORhuman/v26_4/v26_4_k_kinematics_probe.py`
- `memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md`
- `.ai/SCIENTIFIC_ENGINEERING.md`（尤其 §4 准入门必须有效、§7 frame/handedness 符号约定）
- `.ai/LONG_RUNNING_TASKS.md`、`.ai/TEAM_STATE.md`

开工重新记录实际 HEAD、diff、GPU/process/tmux/lease 状态。**不得 reset、stash、
discard 或覆盖本地较新/未跟踪内容**；v26-3 的 dirty 工作区继续保留。

## 3. Wave K R2 — 硬 gate 前置了一个新的硬 gate

### 3.1 FK 镜像恒等式（必须先过，否则不得给出任何可达性判定）

在真实 articulation 上证明镜像掩码确实产生镜像末端位姿：

```text
mirror(FK_LEFT(q)) == FK_RIGHT(mask · q)
```

- 样本集必须包含 R1 记录的 9 个 LEFT 收敛解，外加覆盖工作区的若干构型；
- `mirror` 是矢状面反射，镜像平面取两侧候选呈 ±y 对称的那个 frame（door-local），
  位置分量取负 y；朝向的四元数变换**由本检查验证，不得预设**。候选形式为
  `(w, x, y, z) -> (w, -x, y, -z)`，但必须以本检查的通过与否为准，并在模块边界
  显式声明所用的 wxyz 顺序、frame 与手性约定；
- 逐元素容差内不通过即 fail fast。不通过说明掩码或 frame 约定有误，先修这个，
  不得带着失败的恒等式继续。

产出 `K/fk_mirror_identity.json`，typed outcome `FK_MIRROR_IDENTITY_PASS | FAIL`。

### 3.2 目标位姿改为从几何导出

不要再用侧别无关的常量 offset。RIGHT 的 down-press 目标朝向必须由该侧实际的
把手几何导出——`door.py` 已在 `door_open_lr == -1` 时把 `handle_joint` 的
`LocalRot0` 绕 Z 翻转 180°，把手朝向信息在那里，不在 `grasp_target` prim 的旋转里
（后者恒为单位阵）。导出后的两侧目标必须满足 §3.1 的镜像关系，并把该一致性作为
K 的准入项记录。

### 3.3 其余协议不变

沿用 R1 的固定 root、matched grid（`x ∈ {-0.72,-0.76,-0.80}`、
`|y| ∈ {0.18,0.22,0.26}`、`z = 0.415`、yaw 0）、直接关节状态写入与 readback 校验、
无 policy、无训练。typed outcome 仍取计划 §5 的三选一。

## 4. 并行只读 lane — 训练路径的同类缺陷审计

R1 的缺陷是"镜像了位置、没镜像朝向的参考量"。**独立核查训练路径上是否存在同类
问题**，这条 lane 只读，与 K 并行：

- `door.py` 的 `grasp_target` prim 旋转恒为单位阵，两侧相同；
- 训练 env 主要以位置消费 `grasp_target`（`grasp_target_pos_source`、
  stage0 staging 的 `grasp_target[:, 0/1]`），但存在
  `target_quat_w`/`source_quat_w`/`palm_side_direction` 一类朝向机制；
- `door_open_a2_base.py:7338-7343` 在 A2 路径下把
  `left_hand_palm_side_direction` 与 `right_hand_palm_side_direction`
  都硬设为 `[1.0, 0.0, 0.0, 0.0]`，两侧无区分。

判定：训练用到的 reward / observation / stage 条件中，是否有任何朝向参考量在
LEFT/RIGHT 上取同一个值而本应镜像。产出
`AUDIT/training_orientation_reference_audit.json`，typed outcome
`NO_SIDE_INDEPENDENT_ORIENTATION_REFERENCE` |
`SIDE_INDEPENDENT_ORIENTATION_REFERENCE_FOUND_AT_<site>`。

**这条 lane 只做判定，不改训练 source。** 若发现同类缺陷，它可能是 v26-3
LEFT/RIGHT 不对称的共同根因，属重大发现，写进 closure 并作为 v26-5 的输入，
但不在 R2 内修复。

## 5. Wave C / M

K R2 给出 typed outcome 后按原计划 §6 选形态、§7 执行单因素训练对照。

- 若 K 回到 `SYMMETRIC` 或 `ASYMMETRIC_IN_ACTION_OFFSET` → 走 §6.1 canonical
  representation，恒等证明未过不得上 GPU，随后 C0/C1 × 2 seed 四卡并发。
- 若 K 仍判 `ASYMMETRIC_AT_<joint>`，且这次是在 §3.1 恒等式 PASS 的前提下得到的
  → 走 §6.2，此时该结论才是关于机器人的事实。
- §7 的预注册判据（K5 admission 差 ≤ 0.15、contact stability 差 ≤ 0.05、
  high-water 比值 ∈ [0.5, 2.0]、2 seed 同向）**保持原样，看到结果后不得修改**。
- 本阶段仍不以 Stage4/goal 作为准入。

## 6. Team 与 reviewer 归属

Owner 要求组建 team，delegation gate 视为已触发。建议 lane：K R2 probe、
训练路径朝向审计（§4）、C 实现、M 编排与长跑 supervisor。

**reviewer 改挂到当前硬 gate 上。** R1 的 reviewer 被限定于 §6.1 恒等证明与 §7 判据，
而 K 一旦路由到 §6.2，这两项分别是 `NOT_RUN` 与未评估，独立复核在结构上是空的。
R2 的 reviewer 必须独立复核**当前硬 gate 的目标构造与 frame/符号约定本身**，
具体是 §3.1 的 FK 镜像恒等式与 §3.2 的目标导出，且必须独立于实现该 probe 的 agent。
任何下游证明都不能替代这一项。

若 runtime 禁止 sub-agent，退化为 single-agent 并写明 `NO_DELEGATION_REASON`。
多 writer 与 GPU/IsaacSim/output-root 排他资源触发 `.ai/TEAM_STATE.md` ledger 与
lease；>30min 作业用独立 tmux 与 `.ai/scripts/run_supervisor.py` receipt。

## 7. 权限

**覆盖**：本阶段所需的本地 source/config/script/test/docs 改动、IsaacLab smoke、
GPU0–3 probe/训练/eval/render、artifact analysis、typed closure、memory 同步。

**不覆盖**：GPU4–7、hardware、外部写入、删除或覆盖 R1 artifact、reset/stash/discard、
commit/push、合并 pull 分支、更新 Teacher manifest 或 Student G7 binding。

**禁止自行加入**：修改任何 reward scale、改 `near_closed` 阈值、改 gripper effort cap
或 kp/kd、移植 pull 的 hook/friction/45N/kp1300/tensile mask、降 K5、加 hysteresis、
跑 W wave、在 §4 lane 里修改训练 source、修改 §7 预注册判据。

遇到计划外 invalid state，先用真实 source/runtime 定位并修复同一路径，不得用
fallback 或 silent downgrade。无法继续时仍完成 closure，写清 `INCONCLUSIVE`、
已完成证据、block 与所有 `NOT_RUN` 分支。

## 8. 交付

修正后的 K probe、`K/fk_mirror_identity.json`、`K/k_kinematics.json`（新 output root）、
§4 审计产物、C/M 实际产物或 typed `NOT_RUN`、
`a2_piper_base_v26_4_r2_execution_closure_<date>.md`、计划 R2 段落、memory 更新
（保留 R1 provenance）、资源释放状态。

最终向 Owner 返回结果优先的验收摘要：FK 镜像恒等式结果、K R2 的 typed outcome
及其与 R1 的差异、§4 训练路径审计结论、C/M 实际执行情况与 §7 判据实测值、
changed paths、证据等级、仍 active 的 writer/排他资源、是否 commit/push（默认否）。
