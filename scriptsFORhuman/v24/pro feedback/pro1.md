# Part 1 — v23 findings 与 insights

## 1.1 证据边界

仓库 `A2_Piper` 当前 HEAD 为：

```text
d0095c6ee5e0118170249c5158c60a078e84e250
docs(a2): publish v23 decision chain and v24 draft
```



随附证据包已校验：

```text
a2_piper_v22_v23_evidence_bundle_20260816.zip

SHA-256:
95cf6112fb5b532252d38c9cb7ca956f9b4387ff2ec2b9cb87b60e33052760ad
```

根部 manifest 明确说明，该包是面向 v24 审阅的精选证据层，包含 typed outcomes、P0 receipts、Route-A/Route-B 聚合、schema 样例及 12 段精选视频；不含 checkpoint、W&B、完整 raw trace forest 或完整 720 个 render 视频。因此：

- 可以核对 v23 的执行拓扑、typed conclusions、聚合结果、部分逐步 schema 和定性行为；
- 不能从包内重新加载 policy；
- 不能完全独立重建所有 Route-A/Route-B reducer 数值；
- 对未包含的生产日志不能作存在性假设。

:chatgpt-content-reference{index="16"}

v23 的正式总结果是：

```text
V23_RESEARCH_PASS_NO_RELEASE
```

而不是 release、policy-quality PASS 或 E2 force-boundary PASS。

- :chatgpt-content-reference{index="17"}
- :chatgpt-content-reference{index="18"}

---

## 1.2 我的总判断

v23 是一次**高信息量的负结果轮次**，但本地 durable memory 和 v24 草案对两个结论表述得过强：

```text
过强结论 1：
RP0 全面平价，因此姿态非必需。

更准确：
在当前 goal-saturated、未建立 realized E1、且 RP0 仍允许 planar/yaw
补偿的条件下，没有检测到稳定的 roll/pitch 任务收益。

过强结论 2：
20 N·m 零样本无退化，因此任务 arm 力矩需求 <=20 N·m。

更准确：
在被选择的 stable-grasp 短窗口内，降低 command-side effort cap
增加了 clipping，却没有改变该窗口的 hinge progress；该 cap 对这项
测量未表现出行为约束性。
```

长期 TODO 已经把 “RP0 全面平价”“任务执行力矩需求 ≤20 N·m”写入归档结论，并据此把 roll/pitch 定位成可达性资源而非力资源。 我的审阅意见是：

> **“roll/pitch 主要表现为可达性资源”目前证据较强；“roll/pitch 不是力资源”仍未获得终裁。**

v23 真正证明的是：

> 当前 door-drive、effort-cap 和分析工具链没有共同产生并识别一个足以裁决姿态力价值的 force-limited regime。

---

## 1.3 H1：v23 没有完成真正的 scratch-vs-warm 裁决

### 有 receipt 的事实

原始 2×2×2 设计中的 scratch cells 最终没有使用真正 scratch actor。scratch 500-batch pilot 的结果是：

```text
completed episodes:      16/16
reached stage 2:         12/16
stable grasp:             0/16
reached stage >=3:        0/16
```

Branch B 又因为 checkpoint `env_state_dict` 不包含 staged-reset snapshot bank，且 canonical evaluator 没有导出 stage≥3 birth-stage episodes，被裁定为：

```text
UNMEASURED_OBSERVABILITY_BLOCKED
```

随后 F1 将正式的 G3/G4/G7/G8 替换为 **head-reset**：

- 保留 shared recurrent representation；
- 保留从 v22 checkpoint 加载的大部分 actor；
- 重置 action head / log-std / critic / optimizer；
- 不等于完整 scratch。

:chatgpt-content-reference{index="19"}

最终 16-cell 表中，初始化字段也明确写为：

```text
warm
head_reset
```

而不是 `warm / scratch`。

### 我的推断

因此：

```text
V23_WARM_START_INHERITANCE_NOT_SUPPORTED
```

只能支持一个较窄结论：

> **持续大 roll/pitch 不是只由最终 action-output head 的初始均值和 log-std 维持。**

它不能排除：

- LSTM/shared representation 已编码“开门时采用强姿态”；
- warm policy 的 state-visitation 和 staged-reset buffers 继续塑造 basin；
- reward、低层 A2 policy 和门几何使 head-reset actor 很快重新发现相同行为；
- 真 scratch 需要更长训练或不同 staged-reset bootstrap。

因此，建议将 H1 的论文语言从：

```text
warm-start inheritance not supported
```

收窄为：

```text
output-head-only inheritance not supported;
deep recurrent and state-visitation inheritance remain unresolved
```

本地 audit 本身已指出 scratch pilot 与 staged-reset observability 是关键修订项，而不是可忽略的实现细节。

---

## 1.4 H2：RP0 不是“全面平价”，而是 seed、初始化与门分布交互很强

### 有 receipt 的事实

下面是同一初始化、同一 door regime 内，`RP0 − FULL` 的 goal-count 差值：

| 对照 | Pooled48 | Holdout64 |
|---|---:|---:|
| warm / D0 / seed0 | −5 | +1 |
| warm / D0 / seed1 | +1 | +2 |
| head-reset / D0 / seed0 | +1 | −3 |
| head-reset / D0 / seed1 | −1 | +1 |
| warm / D1 / seed0 | +4 | +4 |
| warm / D1 / seed1 | −1 | +3 |
| head-reset / D1 / seed0 | −2 | −4 |
| head-reset / D1 / seed1 | −1 | **−9** |

所以最终分析对 H2 的正式裁定并不是 parity，而是：

```text
V23_D0_NO_ACTIVE_POSTURE_SUFFICIENCY_INCONCLUSIVE
```

理由是 D0 的 RP0−FULL 差值跨 seed 改变符号，且 warm seed0 pooled deficit 为 5 门，超过预注册 non-inferiority margin。

:chatgpt-content-reference{index="20"}

### 替代解释 1：RP0 仍然具有强 base assistance

RP0 只关闭高层 action 中的 active roll/pitch 两维，并没有关闭：

```text
forward/backward base command
lateral base command
yaw command
frozen A2 locomotion policy 对外力的被动姿态响应
```

因此 RP0 更准确的定义是：

```text
arm + planar/yaw base assistance
without active posture commands
```

而不是 arm-only。

视频中 RP0 policy 仍然通过：

- lateral sidestep；
- yaw 旋转；
- 贴近门板的 base trajectory；
- frozen locomotion policy 的实际 roll/pitch 响应；

完成开门。RP0 command 为零不等于实际机身始终严格水平。

### 替代解释 2：D1 没有形成可辨识的 force-limited regime

v23 的 confirmed E2 为 0；E1 又没有在 Route B 中成功 realized-classify。因此 D1 可能只是参数采样更复杂，而不是一个真实要求姿态来提高施力裕度的区域。

### 替代解释 3：goal 已接近天花板

16 个 candidate 的 holdout 合计：

```text
goal:                     961/1024 = 93.85%
Wilson 95% interval:      approximately 92.21%–95.16%
reached stage 5:          983/1024 = 96.00%
crossed while holding:    977/1024 = 95.41%
```

在这一饱和区间，goal count 对姿态机制的边际差异不敏感。项目新规则 13——成功率只作为 guardrail、主要测量轴必须换成机械量和行为质量——是正确沉淀。

### 我的结论

> **v23 没有证明 active roll/pitch 对当前任务“必要”，但也没有证明其“无用”。它证明的是 RP0 policy 可以通过 planar/yaw、被动姿态和既有抓握策略进行大量补偿。**

尤其值得注意的是 D1/head-reset：

```text
seed0 RP0-FULL holdout = -4
seed1 RP0-FULL holdout = -9
```

这可能是姿态价值、训练 basin、checkpoint selection 或 clearance/traversal 差异的混合结果，不能被“全面平价”概括。

---

## 1.5 “roll/pitch 是可达性资源而非力资源”的证据强度

### 支持“可达性资源”的证据：中等偏强

v22 P0-B acute interventions 得到：

```text
POSTURE_NEEDED:      37
POSTURE_NOT_NEEDED:   3
AMBIGUOUS:            8
```

而 live-grasp posture atlas 又显示：

- 正向 posture 可显著增加有效 grasp/reach states；
- 在已经建立稳定 grasp 的许多状态中，neutral posture 的方向性能力接近最优。

这支持一个阶段分解：

```text
pregrasp / grasp:
  posture 对可达性、避碰、建立接触有明显价值

stable grasp / opening:
  最大姿态未必持续必要
```

:chatgpt-content-reference{index="21"}

RoboDuet 的证据也只直接支持 pitch/roll guidance 扩大 workspace、提高 6D pose solvability 和改善 whole-body coordination；它没有证明这些自由度在相同末端任务下必然提高持续力裕度。

### 支持“不是力资源”的证据：不足

v23 缺少裁决它所需的三个关键条件：

1. 没有可靠 realized E1/E2；
2. 1280 个 forward interventions 未完成 outcome adjudication；
3. 没有足底反力、滑移、support margin 和 base–arm reaction-force path。

因此当前不能排除：

- posture 改变 arm Jacobian 或 load-bearing joint margin；
- posture 通过足底力分布提高 frozen locomotion 抗滑能力；
- posture 价值只在当前未实现的 friction/breakaway 区域出现；
- RP0 通过更大的 planar/yaw 运动付出了未被 goal 衡量的代价。

### 建议终裁语言

```text
已支持：
roll/pitch 是 reachability/setup resource。

尚未裁决：
roll/pitch 是否在真实 E1 force load 下提供额外 force margin。

若 v24 friction-calibrated E1 中 RP0 仍平价：
才能将“posture 非主要力资源”升级为正式机制结论。
```

---

## 1.6 Effort ladder：不是“零 clipping”，而是“clipping 对所测进展未绑定”

### 有 receipt 的事实

P0 effort ladder：

```text
100 → 60 → 40 → 30 → 25 → 20 N·m
```

正式 outcome：

```text
LADDER_INCONCLUSIVE
selected effort = 40 N·m
```

:chatgpt-content-reference{index="22"}

独立汇总 heavy16：

| Cap | Heavy saturation fraction mean | Episodes with clipping | Mean hinge progress |
|---:|---:|---:|---:|
| 100 N·m | 0.0625 | 1/16 | 0.06608 rad |
| 60 N·m | 0.0700 | 2/16 | 0.06599 rad |
| 40 N·m | 0.1019 | 4/16 | 0.06578 rad |
| 30 N·m | 0.1319 | 6/16 | 0.06624 rad |
| 25 N·m | 0.1525 | 6/16 | 0.06602 rad |
| 20 N·m | 0.1781 | 7/16 | 0.06588 rad |

即：

```text
cap 降低 -> clipping 明显增加
但该短窗口 hinge progress 几乎不变
```

所有明显 clipping 都集中在 evidence 中的 arm slot index 3；该 slot 对应的确切语义关节名没有随 bundle 导出，故记为 `UNKNOWN`。

### 需要否决的本地表述

长期 TODO 写成：

```text
20 N·m 零样本无退化
-> task execution torque demand <=20 N·m
```

这不被证据支持。更准确的是：

> **在被选中的 25-control-step stable-grasp 窗口中，command-side clipping 增加，但未改变该窗口的平均 hinge progress。**

### 其他成因假设

至少有七个合理替代解释：

1. clipping 出现在非 opening-tangent load-bearing joint；
2. 25-step 窗口过短，错过持续阻力和 release/traversal 阶段；
3. “first failure-free stable-grasp window”选择规则排除了最困难轨迹；
4. telemetry authority 是 `CLIPPED_COMMAND_TORQUE`，不是 solver-reported applied torque；
5. planar/yaw/base bracing 重新分配了负载；
6. 当前 hinge 没有 static/breakaway friction，低速准静态需求很低；
7. actor/PD controller 在不同 cap 下通过位置误差积累产生补偿。

PiPER 快速手册给出了 1.5 kg 额定负载、626.75 mm 工作半径、功耗和关节速度，却没有提供各关节连续/峰值扭矩，因此 20、40 或 100 N·m 都不能被称为真实硬件能力。 官方 SDK/URDF 入口可以核对实现与接口，但同样不能替代电机扭矩—转速与热限制规格。

### v24 应采用的测量

不能再使用：

```text
any_joint_clipped
```

作为主要 force-boundary 量。

应改为：

```text
directional load-bearing clipping
+ valid grasp
+ sustained high effort
+ low hinge progress
+ counterfactual rescue
```

---

## 1.7 `DOOR_MODEL_INSUFFICIENT` 的更深层模式

### 有 receipt 的事实

v23 atlas/certificate：

```text
confirmed E2: 0
certificate pass: 0/16
```

:chatgpt-content-reference{index="23"}

Route-B realized-dynamics：

```text
episodes:       768
classified:       0
unclassified:   768

reasons:
UNCLASSIFIED_NO_ATLAS_MATCH: 755
UNCLASSIFIED_NO_TRACE:        13
```

:chatgpt-content-reference{index="24"}

### 本地未明确点名的模式 1：连续随机化不能用 exact atlas tuple 匹配

atlas 用有限离散 cell 建立 E0/E1/near-E2；formal D1 则使用连续参数随机化。若 reducer 要求运行值精确匹配 atlas tuple，那么绝大多数连续样本天然无法匹配。

更严重的是，atlas 中存在明显的单位表面差异：

```text
source/native damping max: 200
runtime attribute example: approximately 11459.16

source/native stiffness max: 30
runtime attribute example: approximately 1718.87
```

二者约相差 `180/π`。这强烈提示 source-native/degree-based 和 runtime/radian-based 数值表面没有统一。确切转换位置仍为 `UNKNOWN`，但它足以说明 exact tuple equality 是脆弱设计。

### 本地未明确点名的模式 2：E 区是“门参数标签”，不是“实时力学状态”

同一个 door parameter tuple 在不同阶段、角度、速度、抓握和姿态下，所需力矩完全不同。E-region 应定义在：

```text
realized required torque
available directional wrench margin
grasp/contact validity
progress response
```

而不是仅由：

```text
mass / damping / stiffness / max-force bucket
```

决定。

### 本地未明确点名的模式 3：drive 模型缺少低速 breakaway 机制

v22/v23 主要使用：

- inertia/mass；
- viscous damping；
- spring/stiffness；
- drive max force。

但 body-assist 或 force-feasibility 最需要的是：

> 即使以低速度推门，也存在一个必须持续超过的准静态阻力或启动阈值。

纯 damping 可以通过减慢速度规避；mass 可以通过降低加速度规避。缺少 Coulomb/stiction/breakaway，正是为什么策略可以慢慢推而不进入真实 E2。

DoorMan 会随机化 hinge damping、latch dynamics 和 resistive torque，并通过 staged-reset 增加晚期接触状态 occupancy；但其数值范围和 asset implementation 不能直接搬到 DoorDog。

---

## 1.8 16-cell matrix 与 holdout 还透露了什么？

### 事实：任务完成已进入天花板区

16 个 selected candidate 的 holdout 总计：

```text
goal:                     961/1024
stage 5 reached:          983/1024
crossing while holding:   977/1024
unsafe post-release:        2/1024
```

失败 taxonomy：

```text
pre-stage5 failures:   41
stage5 non-goal:       22
unsafe post-release:    2   # 独立安全计数
```

:chatgpt-content-reference{index="25"}

### 推断 1：成功率已不足以区分机制

约 96% episode 到达 stage5，约 94% 完成 goal。此时：

- 一个机制可能显著改变 posture saturation、base path、arm torque、foot slip；
- goal count 仍几乎不变。

因此 v24 草案把主测量轴改为力学量和行为质量，是正确方向。

### 推断 2：剩余失败不能简单归因于 force infeasibility

当前 taxonomy 没有导出：

```text
valid-grasp high-effort low-progress stall
```

因此 41 个 pre-stage5 failure 可能是：

- reach/grasp；
- lost contact；
- force stall；
- timeout；
- geometry；
- stage transition；

其比例 `UNKNOWN`。

22 个已到 stage5 但未完成 goal 的 episode 则显示 traversal/terminal-state 仍有单独欠账。该模式也符合项目对 handoff quality 的长期担忧：当前阶段成功不等于给下游阶段留下好状态。有关 coupling/handoff critic 的早期讨论也指出，普通 centralized critic 不足以解决 branch credit 与阶段交接质量。

### 推断 3：checkpoint 机械选点仍带来 post-selection 方差

每个 cell 从十个 checkpoint 机械选取不同 step。因而 seed/cell 对比混合了：

- 学习过程；
- checkpoint trajectory；
- mechanical selection；
- evaluation variance。

v24 应保留 all-checkpoint Route A，但主要因果对比还应增加：

```text
matched training steps
selected-checkpoint comparison
area-under-training-curve / stability summary
```

---

## 1.9 Forward interventions：触发成功，因果结果尚不存在

### 有 receipt 的事实

v23 共执行：

```text
80 jobs
1280 episodes
forward-only
state clone supported: false
recurrent state restore: false
```

触发数：

```text
ACUTE_RP0:                 256/256
BASE0_AT_GRASP:            255/256
HIGHER_EFFORT_RESCUE:       52/256
ORACLE_TANGENTIAL_ASSIST:   52/256
```

但所有 job 都是：

```text
PENDING_RUNTIME_FORWARD_ADJUDICATION
```

缺失：

```text
outcome_adjudication_deferred
unsafe_contacts_not_exported_for_route_b_intervention
```

:chatgpt-content-reference{index="26"}

### 我的结论

该工具链证明了：

- intervention 能在指定事件触发；
- prefix/state binding 基本可运行；
- higher-effort 与 oracle assist 有 52 个有效 denominator。

它没有证明：

- posture marginal value；
- rescue success；
- coupling interaction；
- intervention safety；
- E2 causality。

所以草案中“forward-intervention 工具链就绪”应改为：

```text
trigger and evidence-plumbing ready;
outcome adjudication not yet ready.
```

---

## 1.10 视频行为学观察

### 证据性质

证据包只提供：

```text
3 candidates
× ordinary / high damping / fast rebound
= 9 v23 clips

plus 3 v22 references
```

均为：

```text
main camera
env0
canonical episode0
qualitative only
```

因此以下观察不能作为统计证明。

### 观看材料

- :chatgpt-content-reference{index="27"}
- :chatgpt-content-reference{index="28"}
- :chatgpt-content-reference{index="29"}
- :chatgpt-content-reference{index="30"}

代表性视频：

- :chatgpt-content-reference{index="31"}
- :chatgpt-content-reference{index="32"}
- :chatgpt-content-reference{index="33"}
- :chatgpt-content-reference{index="34"}

### Posture 使用形态

- FULL policy 明显以较大身体倾斜和侧向姿态接近门；
- RP0 视频中，机器人实际仍有明显 lean/rotation；
- FULL 与 RP0 的 gross body trajectory 比预期更相似；
- 这支持“planar/yaw + frozen locomotion 的被动响应承担了大量补偿”。

因此视频不支持：

```text
RP0 = upright arm-only
```

### Hold-open vs fling

九段 v23 视频的主模式都是：

```text
gripper/handle sustained support
base side-step/yaw through
late quiet release
```

没有看到清晰的：

```text
deliberate positive release impulse
early hand release
door inertially coasts to create clearance
```

所以定性上仍是 **quiet hold-open dominant**，不是 controlled-fling policy。

### Clearance 质量

- 门在 base 穿行前已有可用开度；
- 机器人通常与门板、门框保持非常近；
- 穿行轨迹依赖侧身/yaw 和持续握持；
- 精选 canonical clips 中没有明显 panel collision；
- 但 clearance margin 肉眼并不宽裕。

### Release 自然度

release 多发生在机器人几乎已经通过门框后：

- 平稳；
- 冲量小；
- 不会明显把门甩回机器人；
- 但显得偏迟、偏保守；
- 没有表现出 dynamics-conditioned 的 release timing。

### 不同 dynamics 的策略变化

ordinary、high-damping、fast-rebound 的视频中：

- posture pattern 相似；
- hold duration 相似；
- 没有明显 fling/hold 策略切换。

因此 H5 的 typed inconclusive 与视觉观察一致。

### 次级 fragility 信号

render receipt 记录了 78 个额外自然-reset media；其中 G7/G3 的低把手、高把手、fast-rebound 和 high-damping extras 中出现多段 `bad_orientation`。这些不在 canonical episode0 QA 中，不能用于计算成功率，但提示：

> 精选 episode0 可能低估了姿态恢复和自然 reset 下的 fragility。

:chatgpt-content-reference{index="35"}

---

## 1.11 对 v23 执行过程本身的审计

| 欠账 | 严重性 | 对 v24 的要求 |
|---|---|---|
| realized-dynamics `0/768` | 高 | 改成连续、canonical-unit mechanics classification |
| 1280 intervention outcomes 全部 pending | 高 | 先完成 outcome reducer，缺字段则最小重跑 |
| exact state clone 不支持 | 中高 | 只称 forward-prefix local causal estimate |
| full scratch 被 head-reset 取代 | 中 | H1 结论收窄，不在 v24 重新开初始化轴 |
| posture saturation / `FP_φ` / `S_φ` 未算 | 中高 | v24 P0 从已有 trace 补算 |
| effort ladder 选 40 N·m 是 fallback | 高 | friction 环境下重新标定 |
| torque authority 非 solver-applied | 高 | 全报告保留 authority 类型 |
| E 区 exact atlas matching | 高 | intended bucket 只作 sampler；按 realized mechanics 分层 |
| bundle 无 checkpoint/full raw forest | 证据边界 | 不作不存在的复评或模型结论 |
| `OWNER_NO_HASH_PATH_IDENTITY` | 中 | v24 记录 hash，但不设 source-SHA 兼容天花板 |

### Part 1 最终独立结论

> **v23 没有证明 roll/pitch 不必要；它证明了在当前 door/control/evidence stack 下，没有形成或识别足以裁决 roll/pitch 力价值的 force-limited regime。**

> **v23 的 strongest result 不是 RP0 parity，而是：D0/D1 goal 已进入天花板、20 N·m command clipping 对短期 progress 未绑定、现有 drive 模型没有 confirmed E2、且当前分析链无法把连续 dynamics 样本映射到 E 区。**

---

# Part 2 — base_v24 自包含方案

# A2+PiPER DoorDog base_v24  
## Friction-Calibrated Force Boundary, Posture Final Adjudication, and Arm–Base Coupling Groundwork

```text
STATUS = DRAFT_FOR_LOCAL_PLANNER_REVIEW
WORKTREE_ROLE = PUSH-DOOR NOVELTY ENGINE
FORMAL_TRAINING_READY_NOW = false

IN_SCOPE:
  force-feasibility boundary
  joint friction / breakaway modeling
  posture force-value adjudication
  arm-base-foot force-coupling measurement
  minimal supervised gated posture pilot

OUT_OF_SCOPE:
  pull-door training
  student distillation
  body-assist training
  counterfactual PPO actor updates
  locomotion-policy unfreezing

GPU CONTRACT = elastic 4–8 physical GPUs
E2 POLICY = held-out evaluation only
HISTORICAL CHECKPOINTS = must remain loadable
SOURCE CHANGES = additive + config-gated, legacy default off
HASH POLICY = provenance identity, not compatibility ceiling
PRIMARY DVS = mechanics and behavior quality
TASK SUCCESS = guardrail
```

项目 long-term ledger 已把推门 worktree 定义为 force-feasibility / arm-base coupling novelty 引擎，并要求 posture/gate/E-region 接口对拉门 worktree task-agnostic。 本方案保持这一分工。

---

## 2.1 相对本地 v24 草案的修改

| 草案内容 | 本方案 | 理由 |
|---|---|---|
| “RP0 全面平价 → posture 非必需” | **收窄为未裁决** | H2 正式是 inconclusive；D1/head-reset 有明显负 gap |
| “head-reset 平价 → inheritance 关闭” | **只关闭 output-head-only hypothesis** | full scratch 没进入 stable grasp |
| v23 classifier 只修 bug后重跑 | **改为 continuous canonical mechanics classifier** | exact atlas match 对连续随机化结构性不适用 |
| 20 N·m null → arm torque 非约束 | **改为 load-bearing cap 未绑定短窗口** | heavy clipping 实际随 cap 下降而增加 |
| friction 接入一条实现路径 | **native friction / explicit proxy 两分支审计** | PhysX static/breakaway semantics 与 per-env API 尚为 `UNKNOWN` |
| friction ranges 直接给 Nm | **按 normalized load ratio 校准** | PiPER joint torque 不明，外部数值不可移植 |
| RQ3 主要看 FULL/RP0 task gap | **以 stable-grasp E1 mechanics + intervention 为主** | success ceiling 无区分力 |
| RQ4 简单 telemetry 包 | **定义 foot/base/arm/door 能量与反作用力路径** | coupling critic 需要明确监督目标 |
| gated posture 输入简述 | **冻结 task-agnostic input/label/interface contract** | 必须可复用到 pull worktree |
| 无稳定 E1 就全轮 stop | **增加 marginal-E1 pilot tier** | 避免因 denominator 稍小而机械阻塞 |
| exact SHA freeze | **hash 记录身份，但 loader 以 schema/shape 兼容为准** | 满足历史 checkpoint 可复评约束 |

本地草案主线——v23 欠账、friction retrofit、FULL/RP0 factorial、shadow coupling critic、gated posture pilot——总体正确，本方案是强化而非推倒。

---

## 2.2 研究问题

### RQ1 — friction 能否建立可反事实验证的 E1/E2？

\[
\tau_{\text{req}}
=
I\ddot{\theta}
+
c\dot{\theta}
+
k(\theta-\theta_0)
+
\tau_{\text{friction}}
\]

目标不是让参数“看起来很大”，而是建立：

```text
E0:
  arm/base resources have clear margin

E1:
  near force boundary;
  behavior/mechanics are sensitive to available assistance

E2:
  arm + posture fail under valid grasp/high effort/low progress;
  a registered rescue restores progress
```

### RQ2 — policy 是否按 realized load 改变行为？

需要观察：

- hold-open / controlled-fling；
- planar stance；
- roll/pitch；
- arm saturation；
- grasp retention；
- clearance；
- release timing；

是否随**实际力学负载**而改变，而不是只随 intended bucket label 变化。

### RQ3 — roll/pitch 的力价值终裁

在 stable-grasp E1 中回答：

```text
FULL 相比 RP0 是否提高：
  directional arm margin
  hinge progress under high effort
  grasp stability
  foot support/slip behavior
  clearance quality
```

如果只改善 pregrasp/reach，而 opening mechanics 不改善，则归类为 reachability resource。

### RQ4 — arm wrench 如何传到 frozen locomotion 与足底？

测量：

```text
arm wrench
  -> trunk reaction
  -> base acceleration/orientation
  -> frozen A2 low-level action
  -> leg torque/power
  -> foot GRF and slip
```

并建立 shadow coupling critic 的监督数据形态。

### RQ5 — 最小 gated posture 是否能选择性调用 posture？

验证：

\[
u_{\phi,t}=g_t\cdot\Delta u_{\phi,t}
\]

其中 gate 只能消费 task-agnostic mechanics/history，而不能读取 push/pull ID 或门参数 oracle。

---

## 2.3 不可改的科学纪律

1. E2 不进入 PPO training distribution。
2. 所有新 source 默认关闭，历史行为路径保持不变。
3. actor observation/action dimensions 在 Wave 1 不变。
4. body assist 不在 v24 中训练。
5. shadow critic 不进入 PPO advantage。
6. task success 不作为主 dependent variable。
7. intended bucket 不是 E-region ground truth。
8. missing mechanics 不得填零。
9. force telemetry 必须携带 authority。
10. qualitative render 不构成统计证明。

Force-feasibility 主张仍是：

> 在多个可行 whole-body 解中，偏好 arm 余量更大、base 干预更小的解；base assistance 只在必要状态通过 gate 打开。

其控制形式：

\[
u_{\text{base}}
=
u_{\text{user}}
+
g(s)\,u_{\text{assist}}
\]



---

# 3. Phase 0 — v23 欠账清偿与 source freeze

## P0.1 v23 post-hoc closure

从本地生产 evidence 重新生成：

```text
logs_eval/base_v24/p0/v23_posthoc/
  V23_REALIZED_MECHANICS_REANALYSIS.json
  V23_INTERVENTION_OUTCOME_ADJUDICATION.json
  V23_POSTURE_BEHAVIOR_ANALYSIS.json
  V23_POSTHOC_ANALYSIS.md
```

### 3.1.1 Realized mechanics 重分层

禁止 exact atlas tuple equality。

每个 episode 使用连续量：

```text
canonical damping
canonical stiffness
modeled spring torque
modeled friction torque, if enabled
door inertia
hinge angle / velocity / acceleration
required opening torque estimate
arm directional capacity estimate
load ratio
```

输出：

```text
CLASSIFIED_E0
CLASSIFIED_E1
CLASSIFIED_NEAR_E2
CLASSIFIED_E2
UNCLASSIFIED_MISSING_TRACE
UNCLASSIFIED_UNIT_AUTHORITY
UNCLASSIFIED_CAPACITY_UNAVAILABLE
```

单位转换必须只有一个 source of truth：

```text
DoorMechanicsUnitContractV1
```

### 3.1.2 Intervention outcome closure

对 1280 existing forward episodes计算：

```text
post-trigger hinge progress
grasp retention
task-stage transition
arm torque utilization
base displacement/yaw
unsafe contact
clearance
terminal reason
```

若现有 schema 缺少这些字段，只允许针对触发 denominator 做一个最小重跑，不重跑全部 v23。

证据标签：

```text
FORWARD_PREFIX_LOCAL_CAUSAL_ESTIMATE
```

不得写成 exact state-clone causal effect。

### 3.1.3 Posture 与 compensation

至少计算：

```text
pitch/roll saturation dwell
stage-conditioned posture use
FP_phi:
  high posture use with no positive intervention utility

S_phi:
  posture use in E1 minus posture use in E0

planar/yaw compensation
actual posture under RP0
body-to-panel/frame clearance
release strategy and release velocity
```

---

## P0.2 Warm-start 机械选点

候选限制为 v23 FULL cells。

选择顺序：

1. strict evidence validity；
2. zero unsafe post-release contact；
3. holdout goal；
4. pooled goal；
5. clearance quality；
6. D1 mechanics coverage；
7. lower posture pathology；
8. lower task-time tail。

现有 bundle 中的 provisional candidate 是：

```text
A1_G7_seed0_step1500
pooled goal: 48/48
holdout goal: 63/64
D1-trained
FULL
```

但 bundle 不含 checkpoint 文件，因此：

```text
checkpoint path/hash = UNKNOWN until local planner verifies production storage
```

不得从 ZIP 文件名推造 checkpoint path。

---

## P0.3 Compatibility freeze

所有修改必须满足：

```text
legacy config:
  new friction = off
  gate = pass-through
  coupling sidecar = off
  evidence additions optional

actor input dim:
  unchanged

actor output dim:
  unchanged

historical checkpoints:
  v20 / v21B / v22 / v23 loadable
```

必测：

```text
load historical checkpoint
canonical prefix replay
legacy reward parity
action parity within numeric tolerance
terminal parity
```

### Hash 规则

记录：

- checkpoint SHA；
- saved config SHA；
- source commit；
- runtime schema；
- URDF；
- IsaacLab/PyTorch versions。

但不得因 source commit 不完全相同而拒绝一个 schema-compatible checkpoint。哈希用于 provenance，不是“必须等于某固定 SHA 才能运行”的天花板。

---

# 4. Phase 1 — Joint friction 与 breakaway 模型

## 4.1 两级实现审计

### Branch A — Native solver friction

首先核对当前 IsaacLab/PhysX 版本是否支持：

- revolute-joint friction；
- per-environment setting；
- static/kinetic distinction；
- solver-reported generalized effort；
- runtime metadata replay。

若全部支持，优先使用 native implementation。

```text
exact API = UNKNOWN until local source/runtime audit
```

禁止绕过 IsaacLab high-level articulation APIs 直接依赖未冻结 private PhysX tensor view。

### Branch B — Explicit breakaway proxy

若 native friction 不能表达 static/kinetic 或不能 per-env randomize，则实现显式 generalized-resistance proxy，并在所有 artifact 中命名：

```text
V24_BREAKAWAY_PROXY
```

不得称为真实 Coulomb/stiction model。

建议两态语义：

```text
STICK candidate:
  |omega| below re-stick threshold
  and estimated external opening demand below tau_static

SLIP:
  breakaway threshold exceeded
  or |omega| above slip threshold
```

滑动态阻力可采用平滑 Stribeck/Coulomb 形式：

\[
\tau_f(\omega)
=
-
\left[
\tau_c+
(\tau_s-\tau_c)
e^{-(|\omega|/v_s)^2}
\right]
\tanh(\omega/v_\epsilon)
\]

其中：

- \(\tau_s\)：breakaway/static cap；
- \(\tau_c\)：kinetic resistance；
- \(v_s\)：Stribeck transition；
- \(v_\epsilon\)：zero-velocity smoothing。

若无法获得可信 external generalized torque，proxy 不能声称精确 stick cancellation；它只提供平滑的低速高阻力行为。

---

## 4.2 参数轴

v24 的主随机化轴：

```text
tau_static
tau_kinetic / tau_static ratio
Stribeck transition velocity
re-stick velocity
viscous damping
spring stiffness
door mass / inertia
```

参数不直接以外部论文的绝对数值冻结。

DoorMan Appendix 给出了其资产上的 hinge max force、damping、stiffness randomization，但没有提供 DoorDog 所需的 breakaway friction；其值只作量级参考。

### 归一化校准

定义：

\[
\rho_{\text{load}}
=
\frac{\tau_{\text{required}}}
     {\tau_{\text{available,dir}}+\epsilon}
\]

P0 使用相对 ladder：

```text
candidate static-load ratios:
  below-boundary
  near-boundary
  above-boundary

exact ratios/ranges:
  P0_CALIBRATION_REQUIRED
```

这样门参数自动随实际 arm directional capacity 定标，而不是盲猜 Nm。

---

## 4.3 数值稳定风险与验收

### 风险

1. 零速不连续导致 chatter；
2. static torque 太高导致永久锁死；
3. proxy 与 existing drive max-force 双重计入；
4. timestep-dependent breakaway；
5. torque direction sign 错误；
6. re-stick 高频振荡；
7. solver energy injection；
8. door teleport / extreme acceleration；
9. contact solver explosion；
10. per-env state machine 与 staged reset 不一致。

### Physics acceptance

必须证明：

```text
A. breakaway:
  motion starts monotonically as applied torque crosses threshold

B. kinetic plateau:
  low-speed sliding resistance remains bounded and approximately speed-independent

C. distinction from damping:
  reducing velocity cannot remove kinetic resistance

D. passivity:
  tau_friction * omega <= small numeric tolerance

E. hysteresis:
  no repeated stick/slip chatter within registered window

F. timestep robustness:
  qualitative classification invariant under one registered dt cross-check

G. orthogonality:
  stable under combinations with mass, damping, stiffness

H. reset:
  friction state round-trips through staged reset

I. legacy:
  disabled path reproduces historical behavior
```

Typed outcomes：

```text
V24_FRICTION_MODEL_VALID
V24_FRICTION_NUMERICALLY_UNSTABLE
V24_FRICTION_AXIS_BELOW_RESOLUTION
V24_FRICTION_AUTHORITY_INSUFFICIENT
```

允许一次参数域收缩；第二次仍失败则不进入 formal training。

---

# 5. Phase 2 — Arm effort 与方向性 force margin 重标定

## 5.1 为什么必须重做 ladder

v23 ladder 已经说明：

- heavy scenes 会 clip；
- lowering cap 增加 clipping；
- clipping 对第一段 progress 未绑定。

friction 加入后，准静态持续需求改变，所以必须重新标定。

所有 Wave-1 cells 使用**同一个** effort profile，避免 door axis 混入 arm-capability axis。实际 v23 D1 formal config 使用 40 N·m 和 4096 env/2500 batches，这一事实应作为历史配置而不是 v24 自动默认。

---

## 5.2 Directional available capacity

对 handle-opening unit tangent \(\hat t\)：

\[
g=J^\top\hat t
\]

给定每关节剩余 torque margin \(m_i\)，估计：

\[
F_{\max,\text{dir}}
=
\min_{i:g_i\ne0}
\frac{m_i}{|g_i|}
\]

再乘 handle 到 hinge 的有效力臂：

\[
\tau_{\text{available,dir}}
=
r_{\text{handle}}\,
F_{\max,\text{dir}}
\]

必须携带 authority：

```text
ESTIMATE_ONLY_DIRECTIONAL_MARGIN
SOLVER_APPLIED_DIRECTIONAL_MARGIN
SOURCE_UNAVAILABLE
```

PiPER 公开资料没有各关节真实 torque curve，因此这一量是仿真内相对 capability，而非实机保证。

---

## 5.3 v24 ladder selection

候选 rungs 由以下量围绕性选择：

```text
v23 observed load-bearing joint torque distribution
friction atlas required torque
Kp/action-scale clipping audit
```

具体 rungs：

```text
P0_CALIBRATION_REQUIRED
```

冻结三个 profile：

```text
tau_hi:
  E0 nearly unclipped, rescue only

tau_boundary:
  E0 remains solvable;
  E1 produces sustained directional utilization/progress sensitivity

tau_rescue:
  one registered higher profile for held-out rescue
```

若降低 cap 到安全下界仍不改变**load-bearing** mechanics：

```text
V24_ARM_COMMAND_PATH_NOT_BINDING
```

此时不得继续用更小数字制造“真实感”；应审计 actuator authority、joint mapping 和 low-level command path。

---

# 6. Phase 3 — E0/E1/E2 mechanics certificate

## 6.1 每个 force window 的必要状态

```text
valid stable grasp
door unlatch confirmed
stage/opening event valid
finite torque authority
finite hinge mechanics
no fall
no door-frame collision
no lost-grasp contamination
```

## 6.2 Continuous realized features

```text
tau_required components:
  inertia
  damping
  spring
  friction

tau_available directional
rho_load
directional clipping fraction
joint-load contribution
hinge progress
hinge velocity
grasp retention
foot slip/support margin
```

## 6.3 Zone semantics

### E0

```text
low realized load ratio
FULL and RP0 both make stable progress
rescue unnecessary
```

### E1

```text
near force boundary
valid denominator
mechanics respond to posture/base/effort intervention
still solvable without oracle assist
```

### near-E2

```text
frequent high effort and low progress
some policies succeed, some fail
rescue evidence incomplete
```

### confirmed E2

同时满足：

```text
FULL fails to make registered progress
RP0 fails to make registered progress
stable grasp remains valid
sustained directional high effort
failure not caused by safety/geometry/stage error
registered higher-effort or oracle tangential rescue restores progress
```

E2 只用于 held-out evaluation。

阈值从 P0 noise floor、friction atlas 和 rescue pilot 冻结：

```text
P0_CALIBRATION_REQUIRED
```

不得在 formal data 后修改。

---

## 6.4 Training distributions

### DF0

```text
v23 D0 source-compatible distribution
new friction disabled
regression anchor
```

### DF1

只包含：

```text
E0
E1
near-E2
```

不含 confirmed E2。

初始 curriculum 形状沿 v23 思路：

```text
easy/current -> E1 mixture -> small near-E2 tail
```

具体比例由 P0 冻结。

### Marginal-E1 fallback

若 E1 存在但 denominator 低于 full-wave requirement：

1. 先运行 4-cell、4096-env、短 horizon pilot：
   - DF1 FULL/RP0 × 2 seeds；
2. 若 sustained realized E1 在 rollout 中出现，晋升 full Wave 1；
3. 否则关闭为：

```text
V24_E1_DENOMINATOR_INSUFFICIENT
```

不把科学 denominator 不足写成 pipeline blocker。

---

# 7. Wave 1 — RQ2/RQ3 science factorial

## 7.1 统一条件

```text
one mechanically selected FULL warm-start
same reward registry
same tau_boundary
same friction implementation
same actor/critic dimensions
same staged-reset schedule
4096 env/run
2500 batches/run by default
save every 250 by default
```

正式数值由本地 planner 对生产预算冻结。

## 7.2 八组矩阵

| Cell | Door | Posture | Seed | 作用 |
|---|---|---|---:|---|
| W1 | DF0 | FULL | 0 | legacy regression |
| W2 | DF0 | RP0 | 0 | D0 posture effect |
| W3 | DF1 | FULL | 0 | friction-load policy |
| W4 | DF1 | RP0 | 0 | E1 posture effect |
| W5 | DF0 | FULL | 1 | regression replicate |
| W6 | DF0 | RP0 | 1 | D0 replicate |
| W7 | DF1 | FULL | 1 | friction replicate |
| W8 | DF1 | RP0 | 1 | E1 replicate |

RP0 必须继续使用 distribution-level mask：

```text
masked posture dimensions:
  neutral executed command
  zero log-prob contribution
  zero entropy contribution
  zero KL contribution
  zero PPO-ratio contribution
```

## 7.3 4–8 GPU 调度

```text
8 GPUs:
  one parallel wave

4 GPUs:
  seed0 sub-wave
  then seed1 sub-wave

5–7 GPUs:
  scheduler preserves matched FULL/RP0 pairs on concurrent or adjacent slots
```

不得因 GPU 数量变化改变：

- seed；
- config；
- training budget；
- checkpoint cadence；
- evaluation order。

---

# 8. RQ3 — 姿态力价值终裁

## 8.1 Primary analysis population

只分析：

```text
stable-grasp E1 windows
```

pregrasp/reach 结果单独报告，不能与 force-value 混合。

## 8.2 主要指标

```text
hinge progress under high effort
directional torque margin
load-bearing clipping duration
grasp retention
TCP-handle tracking
foot friction utilization
foot slip
support margin
planar displacement
yaw displacement
actual roll/pitch
clearance
release velocity and strategy
unsafe contact
```

Task goal 只作 guardrail。

## 8.3 Paired evidence

三层证据必须同向：

1. formal FULL vs RP0，两个 seeds；
2. matched scenario/episode comparison；
3. selected-checkpoint forward intervention。

统计使用：

- paired bootstrap interval；
- seed-wise direction；
- exact door counts；
- continuous effect size。

effect margin 由 P0 measurement noise 冻结，不预先编造绝对数值。

## 8.4 Typed conclusions

### `V24_POSTURE_FORCE_VALUE_SUPPORTED`

要求：

- E1 denominator sufficient；
- 两 seed 中 FULL 相对 RP0 改善至少一个核心 mechanics metric；
- 没有以更大 slip、unsafe contact 或 clearance regression 买入；
- intervention 方向一致。

### `V24_POSTURE_REACHABILITY_ONLY`

要求：

- posture 改善 pregrasp/grasp；
- stable-grasp E1 opening mechanics 无正增量；
- RP0 通过 planar/yaw 补偿完成 opening。

### `V24_POSTURE_REDUNDANT_UNDER_FROZEN_BASE`

要求：

- reach 与 force 两阶段均无有意义增量；
- FULL 只增加姿态动作或不稳定性。

### `V24_POSTURE_FORCE_VALUE_DELETERIOUS`

FULL 在 E1 中增加 slip、unsafe、torque stress 或降低 progress。

### `V24_POSTURE_FORCE_VALUE_UNADJUDICATED`

E1 denominator、authority 或 intervention evidence 不足。

## 8.5 论文叙事

### 正结果

> Under friction-calibrated near-boundary loads, active roll/pitch selectively improves the arm’s directional wrench margin and foot-ground load accommodation.

### 负结果

> Under a frozen locomotion prior, explicit roll/pitch is primarily a reachability resource rather than a force amplifier; force accommodation is instead achieved through planar stance, yaw reconfiguration, and foot-ground bracing.

两个结果都具有方法路线价值。

---

# 9. RQ4 — Arm–base–foot force coupling measurement

## 9.1 Per-foot telemetry

每只脚记录：

```text
3D ground reaction force
normal force
tangential force
friction-utilization ratio
contact state/duration
slip velocity
foot position/velocity
stance identity
```

若 CoP 可由现有 contact API 可靠获取，则记录；否则：

```text
COP_SOURCE_UNAVAILABLE
```

## 9.2 Base/locomotion telemetry

```text
base linear acceleration
base angular acceleration
roll/pitch/yaw and rates
planar/yaw/posture high-level commands
frozen A2 low-level leg action
leg joint torque/power
foot slip
support-polygon proxy
```

## 9.3 Arm/contact telemetry

```text
handle wrench
opening-tangent wrench
per-joint command/clipped/applied authority
joint torque/power
joint-position/velocity margin
TCP tracking
grasp state
```

## 9.4 Door telemetry

```text
friction torque
spring torque
damping torque
inertial torque
hinge velocity/acceleration
door work and power
```

## 9.5 分析窗口

以事件为中心：

```text
pre-contact
stable grasp
high-wrench onset
low-progress onset
posture intervention
base intervention
release / support transfer
```

主要量：

\[
\Delta F_{\text{foot}},
\quad
\Delta v_{\text{slip}},
\quad
\Delta\tau_{\text{arm}},
\quad
\Delta\dot{\theta}_{\text{door}}
\]

## 9.6 干预

```text
FULL
ACUTE_RP0
BASE0_AT_GRASP
HIGHER_EFFORT_RESCUE
ORACLE_TANGENTIAL_ASSIST
```

由于 exact state clone 当前不支持，所有结论标为：

```text
FORWARD_PREFIX_LOCAL_CAUSAL_ESTIMATE
```

不得宣称 exact counterfactual causality。

---

# 10. Shadow coupling critic

## 10.1 定位

只做 offline/shadow evaluation：

```text
no actor update
no PPO advantage
no reward shaping
```

普通 centralized critic 或多 value head 已有大量先例；真正有价值的是 action-conditioned、intervention-supervised coupling target。

## 10.2 输入

```text
privileged recurrent mechanics history
navigation action
posture action
arm/gripper action
grasp/contact state
door mechanics
foot GRF/slip
```

## 10.3 监督目标

不预测一个含义模糊的 scalar total return，而预测短时域向量：

```text
hinge progress delta
arm load-bearing saturation delta
foot slip delta
support-margin delta
grasp-retention delta
clearance delta
unsafe-contact probability
```

目标由 matched forward interventions 的差值构造。

## 10.4 验收

```text
R²
Spearman correlation
sign accuracy
calibration error
E0/E1/near-E2 stratified performance
stage-conditioned performance
```

Typed outcomes：

```text
V24_COUPLING_SIGNAL_LEARNABLE
V24_COUPLING_SIGNAL_NOT_LEARNABLE
V24_COUPLING_EVIDENCE_INSUFFICIENT
```

在没有 exact clone 和完整四分支 neutral intervention 前，不宣称已学习到严格的非加性交互项。

---

# 11. Wave 2 — LT-23-08 最小 gated posture

## 11.1 入场条件

至少满足：

```text
stable E1 denominator exists
posture intervention labels available
friction model valid
Wave 1 complete
```

不要求 RQ3 必须为正；负结果也可以测试 gate 是否学会保持关闭。

## 11.2 机制

\[
u_{\phi,t}=g_t\Delta u_{\phi,t}
\]

其中：

- \(\Delta u_{\phi,t}\)：现有 roll/pitch policy output；
- \(g_t\in[0,1]\)：supervised gate；
- planar/yaw command 不乘 gate；
- legacy/default mode `g=1`，保证历史兼容。

建议先训练 gate，冻结后再进行 PPO；不在本轮让 gate 与 actor 联合无约束 co-adapt。

## 11.3 Task-agnostic gate input contract

```text
ForceFeasibilityGateInputV1
```

只允许：

```text
arm torque-margin history
joint-position/velocity margins
EE tracking error and velocity
contact wrench in canonical manipulation frame
sign-normalized articulation progress/load
foot GRF/slip/support margin
actual base roll/pitch and angular rates
grasp/contact confidence
recent posture/action history
```

禁止：

```text
door mass
door damping
door stiffness
friction parameter
push/pull task ID
hinge sign
door opening direction label
stage integer
reward value
intended bucket
```

## 11.4 Push/pull 通用轴

由 task adapter 提供：

```text
ManipulationAxisSpecV1
```

其作用仅是把：

- opening direction；
- tangential wrench；
- articulation progress；
- base-assist direction；

变换到 canonical sign。

gate 本身不得知道 push 或 pull。

这正是推门 worktree 对拉门 worktree的接口承诺；拉门实现与训练不进入 v24。

## 11.5 Gate labels

在 matched E1 interventions 中：

```text
positive:
  posture improves registered mechanics utility
  without safety/clearance regression

negative:
  posture has no benefit or worsens mechanics

ambiguous:
  evidence conflict or denominator insufficient
  -> excluded from supervised loss
```

Gate utility 不能只用 goal，也不能只用 posture magnitude。

## 11.6 稀疏与稳定

加入：

```text
E0 sparsity
gate slew penalty
minimum on/off dwell
hysteresis
```

精确阈值由 P0 measurement noise 冻结。

## 11.7 Wave-2 最小矩阵

| Cell | Inputs | Door | Seed |
|---|---|---|---:|
| P1 | full coupling input | DF1 | 0 |
| P2 | arm-only input | DF1 | 0 |
| P3 | full coupling input | DF1 | 1 |
| P4 | arm-only input | DF1 | 1 |

Wave-1 FULL/RP0 作为 control。

若有 8 GPU 且预算允许，可增加 DF0 对照四组；不是 mandatory。

## 11.8 Wave-2 判读

成功不是“gate 经常打开”，而是：

```text
E0:
  gate sparse
  posture economy improves

E1:
  gate activates selectively
  mechanics non-inferior to FULL

near-E2:
  gate confidence/activation increases appropriately

no safety regression
```

失败输出：

```text
V24_GATED_POSTURE_NOT_SELECTIVE
```

不进行第二轮 reward retuning。

---

# 12. Evaluation 与 checkpoint selection

## 12.1 Route A

每个正式 run：

```text
10 checkpoints:
250,500,750,1000,1250,1500,1750,2000,2250,2500

canonical16
strict episode record
raw trace
realized mechanics classification
```

## 12.2 Checkpoint selection

Lexicographic：

1. integrity；
2. safety；
3. valid E1 mechanics denominator；
4. hinge progress under high effort；
5. lower foot slip / higher support；
6. lower load-bearing saturation；
7. grasp retention；
8. clearance/release quality；
9. task goal guardrail；
10. time.

不以 reward mean 或 endpoint 优先。

## 12.3 Route B

每个 selected cell：

```text
pooled48
realized E0/E1/near-E2 stratification
matched forward interventions
```

最终候选：

```text
holdout64
confirmed-E2 held-out suite
matched render
final analysis
```

confirmed E2 不参与训练或 checkpoint selection。

## 12.4 Render reviewer questions

1. 普通门是否仍无必要地保持大姿态？
2. E1 门上 posture 是否有条件增强？
3. FULL 与 RP0 是否只是通过不同 planar/yaw path 补偿？
4. 门是 quiet hold-open、controlled fling，还是 premature release？
5. robot 与门板/门框的 clearance 是否充足？
6. release 是否自然、及时、安全？
7. 是否出现足端滑移、身体贴门或门框蹭碰？
8. 高负载下是否出现 frozen locomotion 的明显抗滑/姿态补偿？

视频仍只作定性证据。

---

# 13. Primary metrics 与 guardrails

## 13.1 Primary mechanics

```text
directional torque margin
load-bearing clipping duration
hinge progress under high effort
rho_load
rescue trigger/success
foot friction utilization
foot slip
support margin
arm/base/door work
```

## 13.2 Posture/coordination

```text
Delta J_phi
S_phi
FP_phi
pitch/roll dwell
planar/yaw compensation
actual posture under RP0
```

## 13.3 Behavior quality

```text
clearance
hold/fling strategy
release velocity
rebound collision
grasp continuity
body-to-panel/frame distance
task time
unsafe contact
```

## 13.4 Guardrail

```text
goal
stage reach
crossing while holding
fall/overspeed
```

不预注册一个脱离 v23 measured baseline 的任意 success threshold。正式比较报告：

- exact door counts；
- confidence intervals；
- 与 v23 baseline 的差值；
- 双 seed 方向。

---

# 14. Typed outcomes

## Physics

```text
V24_FRICTION_MODEL_VALID
V24_FRICTION_NUMERICALLY_UNSTABLE
V24_FRICTION_AXIS_BELOW_RESOLUTION
V24_FRICTION_AUTHORITY_INSUFFICIENT
```

## Force boundary

```text
V24_E1_BOUNDARY_ESTABLISHED
V24_E1_DENOMINATOR_INSUFFICIENT
V24_E2_BOUNDARY_ESTABLISHED
V24_E2_BOUNDARY_NOT_ESTABLISHED
V24_ARM_COMMAND_PATH_NOT_BINDING
V24_DOOR_MODEL_REMAINS_INSUFFICIENT
```

## Posture

```text
V24_POSTURE_FORCE_VALUE_SUPPORTED
V24_POSTURE_REACHABILITY_ONLY
V24_POSTURE_REDUNDANT_UNDER_FROZEN_BASE
V24_POSTURE_FORCE_VALUE_DELETERIOUS
V24_POSTURE_FORCE_VALUE_UNADJUDICATED
```

## Coupling

```text
V24_COUPLING_SIGNAL_LEARNABLE
V24_COUPLING_SIGNAL_NOT_LEARNABLE
V24_COUPLING_EVIDENCE_INSUFFICIENT
```

## Gate

```text
V24_GATED_POSTURE_SELECTIVE
V24_GATED_POSTURE_NOT_SELECTIVE
V24_GATE_DENOMINATOR_INSUFFICIENT
```

## Round terminal

```text
V24_RESEARCH_PASS_NO_RELEASE
V24_POLICY_CANDIDATE
V24_PIPELINE_BLOCKER
```

科学负结果不是 pipeline blocker。

---

# 15. Worker authority 与停止条件

## 15.1 Worker 可自主决定

在 formal freeze 前：

- 一次 friction 参数域收缩；
- 一次 normalized load-ratio ladder 调整；
- denominator 不足时选择 marginal-E1 pilot；
- expensive diagnostic sample count；
- report-only / binding 状态；
- 4–8 GPU 排程。

所有决定写入：

```text
V24_ADAPTATION_DECISION_<ID>.json
```

并记录 evidence、旧值、新值和 claim impact。

## 15.2 不可越过

```text
NaN/Inf
energy injection / solver explosion
friction sign error
checkpoint/config identity corruption
GPU lease violation
staged-reset corruption
missing metric -> zero
E2 entering training
hidden controller
root teleport
unsafe contact suppression
post-result threshold change
```

## 15.3 Stop rules

### 无稳定 friction model

```text
STOP TRAINING
V24_FRICTION_NUMERICALLY_UNSTABLE
```

### 稳定但无 E1

允许 marginal-E1 pilot；仍无 denominator：

```text
STOP FORMAL SCIENCE WAVE
V24_E1_DENOMINATOR_INSUFFICIENT
```

### E1 存在但 gate 失败

```text
close Wave 2 once
V24_GATED_POSTURE_NOT_SELECTIVE
```

### E2 未建立

不阻止 RQ3/RQ4；记录：

```text
V24_E2_BOUNDARY_NOT_ESTABLISHED
```

### E2 建立

只解锁：

```text
v25 body-assist planning
```

不在 v24 临时加入 body-assist。

---

# 16. Additive implementation map

可能修改：

```text
gr00t/rl/isaac_utils/playground/env_rand/door.py
gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py
gr00t/rl/envs/door/door_open_a2_base.py
gr00t/rl/eval_agent_trl.py
gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py
relevant env/ablation configs
```

建议新增：

```text
gr00t/rl/envs/door/a2_v24_friction.py
gr00t/rl/envs/door/a2_v24_mechanics.py
gr00t/rl/envs/door/a2_v24_gate.py

gr00t/rl/tests/test_a2_v24_friction.py
gr00t/rl/tests/test_a2_v24_energy_passivity.py
gr00t/rl/tests/test_a2_v24_mechanics_units.py
gr00t/rl/tests/test_a2_v24_e_region.py
gr00t/rl/tests/test_a2_v24_historical_compatibility.py
gr00t/rl/tests/test_a2_v24_gate_contract.py
gr00t/rl/tests/test_a2_v24_staged_reset.py

scriptsFORhuman/v24/
  v23_posthoc_analysis.py
  friction_characterization.py
  effort_recalibration.py
  mechanics_atlas.py
  e_region_freeze.py
  formal_launcher.py
  route_a.py
  route_b.py
  intervention_adjudicator.py
  coupling_shadow.py
  gated_posture.py
  render.py
  final_analysis.py
```

具体 PhysX/IsaacLab API 名称由本地 source/runtime audit 冻结；当前为 `UNKNOWN`，不得伪造。

---

# 17. 跨 worktree 接口

推门 worktree 交付：

```text
ManipulationAxisSpecV1
ForceFeasibilityGateInputV1
RealizedMechanicsRecordV1
ERegionCertificateV1
ForwardInterventionRecordV2
```

要求：

- 不包含 push/pull ID；
- articulation progress 和 wrench sign canonicalized；
- friction 参数对 in/out 门均可配置；
- gate 不读 door oracle 参数；
- pull worktree 可 import，不复制实现。

蒸馏 worktree不进入本方案。DoorMan 的 privileged-teacher → RGB student → bootstrap 路线仍是并行参考，但 v24 不修改 student。

---

# 18. 最终建议

我背书本地 v24 草案的主方向：

```text
friction force boundary
-> FULL/RP0 final adjudication
-> foot/base coupling measurement
-> supervised minimal posture gate
```

但建议本地 planner 必须先修正三个叙事前提：

1. `RP0全面平价` 改为 `goal-level effect inconclusive / force value unadjudicated`；
2. `20 N·m zero degradation` 改为 `short-window progress insensitive despite increasing clipping`；
3. `0/768 classifier` 不作为一个简单 reducer bug，而作为 E-region 定义需要从离散参数标签升级为连续 realized mechanics 的证据。

v24 最有价值的潜在结果并不只是一支更高成功率 policy，而是获得以下任一干净结论：

```text
A. friction-calibrated E1 中 posture 确实提高 force margin；

B. posture 只解决 reachability，真正的 force accommodation 来自
   planar stance + foot-ground bracing；

C. frozen A2 command interface 本身无法表达或测量目标 force boundary；

D. task-agnostic gate 能在 E0 关闭、E1 打开，为 push/pull 共用机制奠基。
```

其中 A 或 B 都能直接关闭长期路线图中的 RQ3；C 会明确指出下一步需要改变低层控制/接触模型；D 则是 force-feasibility-aware minimal-base-intervention 方法线真正开始具备算法贡献的节点。