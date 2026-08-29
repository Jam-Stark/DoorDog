# DoorDog A2+PiPER `base_v26-4` Bilateral Grasp Foundation Plan

制定时间：2026-08-28 HKT
阶段状态：`PLAN_ONLY / NOT_IMPLEMENTED / NOT_RUN`
上游：`v26_3_complete_not_admitted`（`MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`）

---

## 1. Outcome first

**本阶段要建立的东西**：一个左右对称的 bilateral grasp foundation，使 push 与 pull
两个任务能从同一个抓握基座出发，之后再按任务特性分叉。

**本阶段明确不做的事**：不追 unlatch、不追 Stage4、不追 goal、不动 reward scale、
不动 gripper effort cap、不跑 wall removal。v26-2/v26-3 的教训是在基座不成立时
反复优化下游 credit；本阶段把顺序倒回来。

**Acceptance 不是 goal，是对称性**：两条独立 seed 上，LEFT 与 RIGHT 的抓握基座指标
落在预注册带内。

---

## 2. Registered question（claim-matched）

```text
QUESTION      当前 bilateral 设置下，LEFT 与 RIGHT 的差异来自表示/动作参数化，
              还是来自运动学几何不可达？
CLAIM CLASS   mechanism / causal（单因素对照）
INTERVENTION  side-canonical representation ON vs OFF
BASELINE      当前 non-canonical bilateral（v26-3 M1 合同）
UNIT/TIMEBASE control step；角度 rad；力矩 Nm；door-relative frame，符号在模块边界声明
DIRECT METRIC 每侧 Stage2→Stage3 K5 admission rate、contact stability、
              handle high-water；以及三者的 LEFT/RIGHT 比值
POPULATION    natural first episode，每侧 exact64，2 seeds
ADMISSION     见 §7
```

---

## 3. 已冻结的本地事实（本阶段的出发点）

以下全部来自当前 source / resolved config / v26-3 已落盘产物，不需要重跑。

### 3.1 不对称出现在把手转动，不在抓握

| 环节 | LEFT | RIGHT | 判读 |
|---|---|---|---|
| D0 natural Stage3 | 32/64 | 36/64 | 对称 |
| E1 forced-close Stage3 | 64/64 | 64/64 | 对称 |
| E1 K5 steps | 35100 | 34356 | 对称 |
| frozen reference handle (M0 baseline) | 0.00104 rad | 0.05090 rad | **约 50×** |
| M1 step750 handle high-water | 0.0008–0.0025 rad | 0.785398 rad | **数量级差** |

`side_seed_support = {seed0_left:false, seed0_right:true, seed1_left:false,
seed1_right:true}`。两条 seed 方向完全一致，因此这是系统性 side 效应，不是 seed 噪声。

来源：`logs_eval/base_v26/v26_3_event_time_creation_20260827/`
的 `diagnostic_decision.json` 与 `main_mechanism.json`。

### 3.2 source 中的两处 handedness 结构

1. **动作参数化锚定在有手性的名义姿态上。**
   `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml` 的 `default_joint_angles.arm_j6 = 1.57`
   （腕滚 90°），而 `gr00t/rl/envs/base_task/a2_base.py:577` 的手臂动作是
   `target = raw_arm_command * action_scale + arm_default_pos`，`action_scale = 0.25`。
   因此一侧位于动作空间原点附近，另一侧若需要镜像腕姿，必须在单个动作维上长期
   维持大幅偏置。v26 config 链未覆盖 `default_joint_angles`。

2. **观测没有 side-canonical 变换。**
   `gr00t/rl/envs/door/door_open_a2_base.py:26686-26688` 只提供 `left`/`right`
   两个 one-hot 槽；其余 door-relative 几何、arm state 与 action 均以非规范化形式
   呈现。策略被告知自己在哪一侧，但必须为两侧各学一套行为。

### 3.3 机器人本体是单臂，且臂座在中线

- `gr00t/rl/envs/door/door_open_a2_base.py:7326-7337`：A2 路径下
  `_left_arm_dof_idx == _right_arm_dof_idx == arm_dof_indices[:6]`，
  `left_palm_idx == right_palm_idx == end_effector_index`，
  G1 的左右手索引全部置空。**"bilateral" 对 A2 指的是门的手性，不是换一只手。**
- `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf`：`arm_j0` origin
  `xyz="0.145 0 0.154"`，横向偏置为 0，臂座在矢状面上。
- 臂关节限位：`arm_j1 ±2.618`、`arm_j4 ±1.745`、`arm_j5 ±1.22`、`arm_j6 ±2.0944`
  关于零对称；`arm_j2 [0, 3.14]`、`arm_j3 [-2.967, 0]` 是矢状面内的肩俯仰/肘，
  不破坏左右镜像。

**因此镜像解在关节限位上原则可达，不存在明显的限位墙。** 这使 §3.2 的表示/参数化
解释成为首要候选，但仍需 Wave K 判定，不得直接当结论。

### 3.4 push 与 pull 目前不共享代码

merge-base `4aec9fe`（2026-08-03）。A2_Piper 领先 59 个提交，
`codex/a2-piper-pull-v0-20260803` 领先 56 个。仅在共享文件上：

```text
gr00t/rl/envs/door/door_open_a2_base.py           2663 +/-
gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py  138 +/-
gr00t/rl/envs/base_task/a2_base.py                  67 +
gr00t/rl/isaac_utils/playground/env_rand/door.py      8 +/-
```

pull 分支缺少 A2_Piper 在 `door_open_a2_base.py` 上的 15 个提交。
**"同一框架" 在代码层面当前并不存在**，这是 §8 的 Owner 决定项。

---

## 4. Scope

### 4.1 本阶段必须完成

1. Wave K：双侧运动学可达性判定（无训练、无 policy）。
2. Wave C：按 K 的结论实施表示层修正，并给出静态恒等证明。
3. Wave M：单因素训练对照，唯一 causal seam 为 C 的开关。
4. 按 §7 的对称性准入给出 typed outcome，并据此决定是否可作为 push/pull 共享基座。

### 4.2 本阶段不做

- 不改 `a2_stage3_handle_creation` / `a2_stage3_handle_depression` / `push_door_hinge`
  的任何 scale。
- 不改 `a2_stage3_unlatch_near_closed_hinge_threshold`（wall 属 v26-5 及以后）。
- 不改 gripper effort cap（F 已判 `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`）。
- 不合并 pull 分支，不动 Teacher manifest 与 Student G7 binding。
- 不做 hook / friction / 45N / kp1300 的移植。

---

## 5. Wave K — 运动学可达性判定（无训练）

**目的**：把"镜像抓握是否几何可行"从假设变成判定，再决定 Wave C 的形态。
这是全阶段最便宜、最具决定性的一步，必须先跑。

**协议**：单门 fixture，沿用 `scriptsFORhuman/v26_2/v26_2_u_probe_current_fixture.py`
的 fixture 构造方式，但加载机器人。对 LEFT 与 RIGHT 各自：

1. 取该侧 grasp target 的位姿（door.py 中 `grasp_target` prim 与
   `handle_joint` 的 LocalRot0；注意 `door_open_lr == -1` 时 handle joint frame
   绕 Z 翻转 180°）。
2. 脚本化求解把 gripper 放到该位姿、并保持下压把手所需朝向的臂构型。
3. 记录：是否可达；各关节到限位的余量；`arm_j6` 相对 `default_joint_angles` 的行程；
   把手轴到夹爪接触点的力臂；所需保持的动作向量范数。

**输出**：`logs_eval/base_v26/v26_4_.../K/k_kinematics.json`，含每侧逐项数值与
typed outcome：

- `BILATERAL_KINEMATICALLY_SYMMETRIC` — 两侧均可达且关节余量相当；
- `BILATERAL_ASYMMETRIC_AT_<joint>` — 某关节在一侧余量显著更小或不可达；
- `BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET` — 两侧均可达，但相对 default 的动作偏置
  显著不同。

**这一步不产生任何策略结论**，只给出几何事实。

---

## 6. Wave C — 表示层修正

Wave C 的形态由 K 决定，不得在 K 之前冻结实现。

### 6.1 若 K 判为 `SYMMETRIC` 或 `ASYMMETRIC_IN_ACTION_OFFSET`

实施 **side-canonical representation**：对其中一侧做矢状面镜像，使两侧对策略呈现为
同一个问题。

需要镜像的量（每一项都要在模块边界声明符号约定）：

- door-relative 位置的横向分量与 relative yaw；
- handle joint 角与角速度的符号；
- 接触点位置的横向分量、接触力的横向分量；
- arm action 中的 roll / yaw 维；
- `default_joint_angles` 中有手性的分量（当前是 `arm_j6`），改为按 side 取镜像值，
  使两侧都位于各自动作空间原点附近。

**静态恒等证明（GPU 之前必须通过）**：在 fixture 上逐元素验证
`canonical(LEFT_obs) ≈ canonical(mirror(RIGHT_obs))`，以及 action 侧的
往返一致性 `mirror(mirror(a)) == a`。任一元素超出容差即 fail fast，不做 fallback。

保留 `left`/`right` one-hot 槽不变（`door_open_a2_base.py:26686-26688`），
观测维度不变，Student binding 不受影响。

### 6.2 若 K 判为 `ASYMMETRIC_AT_<joint>`

不做假镜像。改为最小充分修正：把该关节在受限侧的名义姿态或可用行程补足，
并如实记录这是"给策略补足权限"，不是"两侧等价"。此时本阶段的 typed outcome
上限为 `BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE`，不能宣称共享基座。

---

## 7. Wave M — 单因素训练对照与准入

**共同合同**（除 canonicalization 外全部相同）：

```text
source checkpoint  logs_rl/by_batch/base_v26_acquisition_supplement_20260823/
                   continuation/V26A_LR_S1_POLICY800/model_step_002000.pt
load               policy_only + policy_only_load_actor_rms: true
env                4096，bilateral exact 2048/2048
seeds              2
reward             与 v26-3 M1 完全一致，不改任何 scale
gripper            effort 10/10，kp800/kd25
GPU                GPU0–3，不使用 GPU4–7
```

**两格**：`C0_CANONICAL_OFF`（= v26-3 M1 复现）与 `C1_CANONICAL_ON`。
唯一 causal seam 是 §6 的变换开关。

**评估**：每 checkpoint 每侧 exact64 natural first episode。

**预注册准入指标与判据**（看到结果后不得修改）：

| 指标 | 准入条件 |
|---|---|
| Stage2→Stage3 K5 admission rate | 两侧之差 ≤ 0.15（绝对） |
| Stage3 contact stability | 两侧之差 ≤ 0.05 |
| handle high-water 的 LEFT/RIGHT 比值 | ∈ [0.5, 2.0] |
| seed 一致性 | 上述三项在 2 条 seed 上同向 |

三项全过且两 seed 同向 → `BILATERAL_GRASP_FOUNDATION_SUPPORTED`。
仅 K5/contact 过而 high-water 比值不过 → `BILATERAL_CONTACT_SYMMETRIC_ROTATION_ASYMMETRIC`。
C1 未优于 C0 → `CANONICALIZATION_NOT_SUPPORTED`。

注意：**本阶段不以 Stage4/goal 作为准入指标**。若出现 goal，如实记录，但不改判据。

---

## 8. Owner 决定项

以下两项超出 planner 权限，需要 Owner 裁决后才能进入实施：

1. **共享基座落在哪里。** 建议：先在 A2_Piper 上完成 Wave K/C/M 并取得 typed outcome，
   再把已验证的 canonical 变换作为一个独立、可关闭的 seam 落到共享的
   `door_open_a2_base.py`，最后把 pull 分支 rebase 上来。理由是 pull 分支落后
   A2_Piper 在该文件上的 15 个提交，先合并会把一次表示层验证变成一次大规模合并
   冲突处理，两件事的失败会混在一起。

2. **是否接受"本阶段不追 goal"。** 这是相对 v26-2/v26-3 的显式降速：用一整轮
   换一个可复用的对称基座。若 Owner 要求本轮仍需 goal 证据，则本计划不成立，
   需要重写。

---

## 9. Typed closure tree

```text
K  -> BILATERAL_KINEMATICALLY_SYMMETRIC
      | BILATERAL_ASYMMETRIC_AT_<joint>
      | BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET

C  -> CANONICAL_IDENTITY_PROOF_PASS | FAIL（FAIL 则不进 GPU）

M  -> BILATERAL_GRASP_FOUNDATION_SUPPORTED
      | BILATERAL_CONTACT_SYMMETRIC_ROTATION_ASYMMETRIC
      | CANONICALIZATION_NOT_SUPPORTED
      | NOT_RUN
```

只有 `BILATERAL_GRASP_FOUNDATION_SUPPORTED` 才允许把该基座宣称为 push/pull 共享起点。

---

## 10. 证据等级声明

- §3 全部为 INSPECTED（source/config）与已落盘的 RUNTIME/EXPERIMENT 归约，本阶段不重跑。
- Wave K 为 RUNTIME_PASS 级几何事实，不得升级为策略能力结论。
- Wave C 恒等证明为 STATIC_PASS/TEST_PASS。
- Wave M 为 EXPERIMENT 级，且只对 §7 注册的对称性判据成立。
- 本计划中"`arm_j6` 的名义姿态是主因"是**假设**，由 §3.2 的 source 事实支持、
  由 Wave K 判定，未经判定不得写成结论。

---

## 11. Execution closure（2026-08-28）

本阶段已按 typed stop 完整关闭，权威 closure 为
`scriptsFORhuman/v26_4/a2_piper_base_v26_4_execution_closure_20260828.md`。

- K：`BILATERAL_ASYMMETRIC_AT_arm_j4`，reviewer PASS/ADMITTED。冻结 9 组
  Stage3 matched grid 中 LEFT `9/9` reachable；RIGHT `9/9` 首次越界均仅为
  `arm_j4` upper limit，overshoot `0.003046–0.039405 rad`。
- C：按 §6.2 关闭为 `BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE`；没有
  admitted non-mirror RIGHT posture 可冻结，因此不猜 default、不改 core source，
  identity artifact 为 `CANONICAL_IDENTITY_PROOF_NOT_RUN`。reviewer 0-blocker PASS。
- M：`NOT_RUN`。orchestrator 在 source-lock/GPU/tmux/train/eval 前 terminal exit；
  四 cell × 125/250/500/750 全部明确 NOT_RUN、metrics null。reviewer 0-blocker PASS。
- §7 没有实测 K5/contact/high-water，也没有 C1-vs-C0 单因素结论；不得从 K 或 v26-3
  填值。本阶段不准入 push/pull shared foundation、Teacher 或 Student binding。
- 最终无 v26-4 活跃 process/tmux/GPU compute/lease；未使用 GPU4–7，未 commit/push，
  未产生 cloud artifact bundle。

---

## 12. R2 correction preregistration（2026-08-28）

### 12.1 R1 provenance 与已确认缺陷

R1 closure 与正式产物保留为历史证据，不删除、不覆盖、不改写。R1 的执行纪律与 typed
stop 仍然成立，但其 K 几何结论不能继续作为当前事实：R1 在镜像 root position 与 arm seed
的同时，把 LEFT/RIGHT 的 TCP world target orientation 都固定为
`[0.5, 0.5, 0.5, 0.5]`。这使 RIGHT 求解的是镜像位置加非镜像朝向，并在错误目标上触发
`arm_j4` upper-limit first rejection。

反证来自 R1 自身的九组结果：把每个 LEFT 收敛解按已声明 arm mask
`[-1, +1, +1, -1, +1, -1]` 映射后，所得 RIGHT mirror-matched joint vector 仍在对称
hard limits 内，最小余量与 LEFT 相同，为 `0.715–0.904 rad`；这与 R1 实际 RIGHT branch
仅 `0.0009–0.038 rad` 的余量不相容。因此 `BILATERAL_ASYMMETRIC_AT_arm_j4` 只保留为
R1 defective-target protocol 的历史 typed outcome，R2 必须重新判定。

R2 正式输出根冻结为：

```text
logs_eval/base_v26/v26_4_r2_bilateral_grasp_foundation_20260828/
```

### 12.2 Wave K R2 hard gates

K 必须按以下顺序执行；前一项未 PASS 时，后一项不得运行或给出可达性结论。

1. 在真实 A2+PiPER articulation 上证明
   `mirror(FK_LEFT(q)) == FK_RIGHT(mask * q)`。样本包含 R1 九个 LEFT 收敛解以及覆盖
   工作区的额外构型；比较在 door-local 的 `y -> -y` 镜像平面完成，并处理 quaternion
   的 `q == -q` 等价。候选映射 `(w,x,y,z) -> (w,-x,y,-z)` 只可由 runtime FK 数据证明，
   不得作为先验直接写入判据。正式产物为 `K/fk_mirror_identity.json`，typed
   `FK_MIRROR_IDENTITY_PASS` 或 `FK_MIRROR_IDENTITY_FAIL`。
2. 从实际 `grasp_target`、handle geometry 与 `handle_joint LocalRot0` 推导每侧完整 target
   pose，并显式验证两侧 target 的位置与朝向满足同一镜像关系。禁止使用 side-independent
   constant target quaternion。
3. 只有上述两项 PASS 后，才运行 R1 冻结的 matched grid：
   `x={-0.72,-0.76,-0.80}`、`|y|={0.18,0.22,0.26}`、`z=0.415`、`yaw=0`。
   DLS、mirror-matched seed、阈值、direct joint-state write、`sim.forward()`、readback 与
   typed three-way tree 均保持不变；不加载 policy，不训练，不用 fallback 或 clipping。

### 12.3 并行 training orientation-reference audit

独立只读 lane 沿实际训练 source/config/consumer 路径审计与 R1 同类的“位置镜像但朝向参考
未镜像”缺陷，至少覆盖 `door.py` 的 `grasp_target` frame、A2 左右 palm direction、
FrameTransformer offset 以及 reward/observation/stage consumers。输出
`AUDIT/training_orientation_reference_audit.json`，typed 为
`NO_SIDE_INDEPENDENT_ORIENTATION_REFERENCE` 或
`SIDE_INDEPENDENT_ORIENTATION_REFERENCE_FOUND_AT_<site>`。本 lane 不修改训练 source；发现
只进入 R2 closure，并作为 v26-5 输入。

### 12.4 C/M 与 §7 冻结路由

- K 为 `BILATERAL_KINEMATICALLY_SYMMETRIC` 或
  `BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET`：进入 §6.1；C identity proof 必须在 GPU 前 exact
  PASS，随后才允许 C0/C1 × 2 seeds 使用 physical GPU0–3。
- K 仍为 `BILATERAL_ASYMMETRIC_AT_<joint>`：进入 §6.2，禁止伪造 canonical identity，M
  明确 `NOT_RUN`。
- §7 不因 R2 修改：K5 admission gap `<=0.15`、Stage3 conditional contact stability gap
  `<=0.05`、每侧 exact64 high-water 的 LEFT/RIGHT ratio 在 `[0.5,2.0]`；两个 seed 上 C1
  相对 C0 的三项非负 asymmetry loss 均须严格下降。Stage4/goal 只记录，不参与准入。

独立 reviewer 只对当前 K hard gate 的 FK frame/mask/quaternion 恒等式、handle-derived target
推导与 gate ordering 给 formal verdict。GPU4–7、hardware、外部写入、R1 artifact overwrite、
commit/push、reward/threshold/effort/gain/friction/hook/K5/hysteresis/W-wave 变更均不在 R2
授权范围内。

### 12.5 R2 execution closure（2026-08-29）

权威 closure 为
`scriptsFORhuman/v26_4/a2_piper_base_v26_4_r2_execution_closure_20260829.md`。

- FK/K：真实 articulation FK mirror 与 geometry-derived target 均 PASS；冻结九对
  Stage3 grid 全部 bilateral reachable，typed 为
  `BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET`。R1 `arm_j4` 结论保留为 defective-target
  历史，不再是当前几何事实。
- AUDIT：active A2 frame-transformer handle/pregrasp target offsets 仍为
  side-independent，进入 v26-5；R2 不修改该训练参考。
- C：canonical identity CPU/static PASS，C1 64-env/one-batch runtime smoke PASS。
- M：C0/C1×seed0/1 四格 4096-env×750 均 PASS；125/250/500/750 的 32 组
  LEFT/RIGHT exact64 natural eval 均 PASS。step750 C1 两 seed 均未通过全部预注册
  bands，且 seed1 仅 high-water loss 改善，最终为
  `CANONICALIZATION_NOT_SUPPORTED`。
- reducer 仅修复两个 instrumentation contract：v2 active-only max 与 v3 all-episode
  high-water 不可无条件相等；Stage2–5 trace 只需覆盖 terminal max-stage>=2 的 env。
  §7 metric、denominator、threshold、seed rule 与 typed priority 均未修改。
- Teacher/Student handoff与G7 binding保持不变；无hardware证据；GPU4–7未使用；无
  commit/push 或外部写入。
