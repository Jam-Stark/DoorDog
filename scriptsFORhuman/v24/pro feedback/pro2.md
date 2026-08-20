# 结论前置

| 评审结论 | 证据性质 | 我的判断 |
|---|---|---|
| v23 是一次**研究执行与证据基础设施完成**，不是 force-feasibility 成功，也不是可发布 policy | 有 receipt | 正确终态仍是 `V23_RESEARCH_PASS_NO_RELEASE` |
| “RP0 全面平价，因此姿态非必需” | 与正式终局报告不一致 | 应改写为：**当前门模型下，chronic RP0 经重新训练后经常能恢复高成功率，但 H2 未过预注册非劣门槛，D1 上还存在明显的 seed×init×posture 交互** |
| “roll/pitch 是可达性资源而非力资源” | 部分推断 | **可达性/协调作用有中等证据；力价值仍未裁决**。现在还不足以写成排他性结论 |
| effort 100→20 N·m 无退化 | 有限测量事实 | 只能称为：**被选择的 stable-grasp 25-step hinge-progress 统计对该梯度不敏感**。不能外推为 arm 不受力矩约束，更不能外推到实机 |
| `DOOR_MODEL_INSUFFICIENT_FOR_E2` | 有 receipt，且比本地总结更广 | 不仅缺 E2；还缺 stiction/breakaway、机器人侧能力映射、连续 realized-dynamics 分类、自然 release 与行为分化 |
| 视频行为 | 定性证据 | v22/v23 代表视频均以 **hold-open** 为主，几乎没有 controlled fling；过门成功但身体与门较贴近，release 偏晚且不够自然，FULL/RP0 的主要差异更像姿态与平面站位之间的替代 |

本次证据边界以附件根部 :chatgpt-content-reference{index="20"} 为准：包内不含 checkpoint、W&B、完整 raw trace 或 720 个 canonical 视频，只包含精选证据和 12 个代表视频。因此，下面把结论区分为：

- **[Receipt]**：文件直接支持；
- **[独立复算]**：我从附件内 episode records 重新聚合；
- **[推断]**：最合理解释，但不是统计或因果证明；
- **[UNKNOWN]**：附件和仓库没有足够证据。

---

# Part 1 — v23 findings 与 insights

## 1. v23 真正证明了什么

### 1.1 有 receipt 的最终事实

**[Receipt]** 16 个 formal cell 全部自然完成到 step 2500；Route A、pooled48、stratified、intervention、holdout64 和 render 流程均完成。holdout 合计为：

- `961/1024` goal；
- `983/1024` 到达 stage 5；
- `977/1024` crossing while holding；
- `2/1024` unsafe post-release contact。

但正式结论仍明确拒绝 release 与 policy-quality claim。来源：:chatgpt-content-reference{index="21"}、:chatgpt-content-reference{index="22"}。

**[Receipt]** 五个假设的正式状态是：

| 假设 | 正式结论 |
|---|---|
| H1 warm/head inheritance | `V23_WARM_START_INHERITANCE_NOT_SUPPORTED` |
| H2 D0 无 active posture sufficiency | `V23_D0_NO_ACTIVE_POSTURE_SUFFICIENCY_INCONCLUSIVE` |
| H3 E1 posture causal effect | `V23_POSTURE_CAUSAL_EFFECT_IN_E1_UNADJUDICATED` |
| H4 E2 boundary | `V23_E2_BOUNDARY_NOT_ESTABLISHED`；secondary 为 `V23_DOOR_MODEL_INSUFFICIENT_FOR_E2` |
| H5 dynamics-selective posture | `V23_SELECTIVE_POSTURE_BY_DYNAMICS_UNADJUDICATED` |

来源：:chatgpt-content-reference{index="21"}。

因此，`scriptsFORhuman/a2_piper_longterm_TODO.md` 归档段和 v24 草案中“RP0 全面平价”“姿态既非必需也非头部继承”的表述，比正式终局报告更强。建议本地 planner 把 durable memory 改回 typed 结论：**H1 negative；H2 inconclusive；H3/H5 unadjudicated**。目前 TODO 确实把 RP0 写成“全面平价”，而 v24 草案也据此取消了姿态争议。 

---

## 2. “RP0 全面平价”不成立；更准确的是“高成功率下可替代，但交互明显”

### 2.1 独立聚合结果

我将 holdout 内的 1024 条 episode record 展平复算，结果如下。原始依据为 :chatgpt-content-reference{index="22"}，复算表为 :chatgpt-content-reference{index="25"}。

| 训练门 | 模式 | Goal | Stage 5 | Crossing while holding | Unsafe | hinge@crossing 中位数 | root-x@release 中位数 | 有 release 记录 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| D0 | FULL | 248/256 | 249 | 250 | 0 | 1.026 rad | 0.510 m | 171/256 |
| D0 | RP0 | 249/256 | 249 | 235 | 0 | 1.048 rad | 0.316 m | 247/256 |
| D1 | FULL | 235/256 | 247 | 256 | 0 | 0.955 rad | 0.550 m | 207/256 |
| D1 | RP0 | 229/256 | 238 | 236 | 2 | 0.926 rad | 0.450 m | 208/256 |

**[独立复算]** 若只看 goal，FULL 为 `483/512`，RP0 为 `478/512`，的确接近；但行为和失败结构并不平价：

- FULL crossing while holding 为 `506/512`，RP0 为 `471/512`；
- D1 RP0 比 D1 FULL 少 6 个 goal、少 9 个 stage-5、少 20 个 holding crossing，并承担全部 2 个 unsafe；
- release 位置也系统不同，但该字段有严重非随机缺失，只能作为描述性信号。

### 2.2 D1 上出现明显交互，而不是稳定非劣

**[Receipt]** D1 的 RP0−FULL holdout 差值为：

| Seed | 初始化 | RP0−FULL |
|---:|---|---:|
| 0 | warm | +4 |
| 0 | head-reset | −4 |
| 1 | warm | +3 |
| 1 | head-reset | −9 |

符号和幅度都随初始化、seed 改变。正式报告因此没有裁决 H3。来源：:chatgpt-content-reference{index="21"}。

**我的解读：**

1. **[推断] D1 仍过易。** D1 没有 confirmed E2，且大多数策略仍能达到极高 crossing/goal。它更像“稍难的 drive 参数混合”，而非可辨识的 force boundary。
2. **[推断] chronic RP0 测到的是“策略是否能重新找替代解”，不是“姿态是否具有物理价值”。** 每个 RP0 cell 都重新训练并从十个 checkpoint 中机械选优；平面站位、yaw、臂轨迹和 release 时机都能适应。
3. **[推断] best-checkpoint selection 掩盖了学习效率。** G3/G4 等 head-reset cell 很早便能选到满分 checkpoint，而其他 cell 需要更晚。最终 checkpoint 横截面无法回答 RP0 是否更难学、是否需要更多样本、是否更脆弱。
4. **[Receipt] RP0 仅屏蔽 raw action 3/4 的主动 pitch/roll command，并不把物理机身锁定在零 roll/pitch。** masked 维度固定为 0、从 entropy/log-prob/PPO ratio 中排除，但实际机身仍会因接触、动态响应和 frozen locomotion 产生 achieved orientation。准确术语应是 **no-active-posture-command**，不是“没有姿态”。
5. **[Receipt]** x/y/yaw 与 arm/gripper 仍可训练；G2 配置只是开启 `rp0_enabled` 并屏蔽 `[3,4]`。

### 2.3 具体的 planar compensation 机制

**[推断，受视频与 holdout 支持]** RP0 可以通过下列机制补偿：

- 改变接近门的侧向位置和 yaw，使把手落在更有利的臂空间；
- 让 frozen locomotion 通过脚步和 base SE(2) 运动追随臂端圆弧；
- 使用更高、更大的臂部绕行轨迹，替代主动 trunk pitch；
- 更早或不同位置 release，减少继续跟随门板的要求；
- 保持抓握更短，依赖已经建立的门动量完成 crossing。

D0 RP0 与 FULL 的 goal 几乎相同，但 RP0 的 crossing-while-holding 少 15 个，且 `root_x_at_release` 中位数明显更浅；这更像**策略替代**，而不是“行为完全相同”。字段缺失使最后一项只能作为提示，不能作为因果结论。:chatgpt-content-reference{index="25"}

---

## 3. “roll/pitch 是可达性资源而非力资源”：证据强度评估

### 3.1 对“可达性/协调资源”的证据：中等

**[Receipt]** v22 acute posture intervention 在 48 个独立标签中给出：

- 37 `POSTURE_NEEDED`；
- 3 `POSTURE_NOT_NEEDED`；
- 8 ambiguous。

来源：:chatgpt-content-reference{index="28"}。

这说明一个已经依赖 posture 的 warm policy，在突然移除姿态时经常丢失 stage progression、抓握或过门能力。它支持：

> 姿态是该已训练策略保持 arm geometry、reach/contact continuity 或 trajectory compatibility 的重要自由度。

但它不直接证明：

> 只有姿态才能完成这些状态，或姿态本身增加了末端可用力。

因为 acute removal 同时造成 out-of-distribution 动作、臂根位姿突变和 recurrent-history mismatch。v23 chronic RP0 的高成功率恰好证明：经过重新训练，部分姿态作用可被平面站位和臂轨迹替代。

### 3.2 对“不是力资源”的证据：弱

要证明 posture 不是力资源，至少需要在**匹配 reach、抓握、root SE(2)、门角和接触状态后**，比较 FULL/RP0 的：

- breakaway 成功率与延迟；
- hinge work / torque-normalized progress；
- arm saturation dwell；
- directional arm margin；
- rescue benefit；
- 足底反力、滑移和稳定裕度。

v23 没有完成这些裁决：

- realized E1 分类 `0/768`；
- 1280 intervention episode 全部 `PENDING_RUNTIME_FORWARD_ADJUDICATION`；
- 无 exact state clone / recurrent restore；
- actual PhysX arm drive torque 仍是 `UNKNOWN`；
- confirmed E2 为 false。

来源：:chatgpt-content-reference{index="29"}、:chatgpt-content-reference{index="30"}、:chatgpt-content-reference{index="21"}。

### 3.3 建议的当前表述

最稳妥的论文级措辞是：

> **Under the current drive-based door distribution, active roll/pitch commands appear to be a policy-relative reachability and coordination resource that can often be substituted by planar repositioning after retraining. Their independent contribution to force feasibility remains unresolved.**

对应 typed 状态建议写成：

```text
POSTURE_REACH_COORDINATION_ROLE_SUPPORTED_MODERATELY
POSTURE_FORCE_VALUE_UNRESOLVED
```

不建议现在写：

```text
ROLL_PITCH_IS_NOT_A_FORCE_RESOURCE
```

---

## 4. effort ladder null：它测到了什么，又没有测到什么

### 4.1 receipt 支持的有限事实

**[Receipt]** effort ladder 为 `[100,60,40,30,25,20] N·m`，每档 canonical16+heavy16 共 32 个可评 episode。所有档位：

- `P_ref` 中位数都为约 `0.09864 rad`；
- `P_heavy` 中位数都为约 `0.06582 rad`；
- 20 N·m 仅有约 `2×10^-7 rad` 的 harder-first 差异；
- 0/32 被判定为 obvious PD oscillation；
- 最终状态是 `LADDER_INCONCLUSIVE`，40 N·m 是 F2 关闭后的统一冻结值，不是正常选择出的物理最优值。

来源：:chatgpt-content-reference{index="32"}。

**[独立检查]** heavy16 的 saturation tail 实际随 effort 降低而增长：

- 100 N·m：有一个 episode saturation fraction=1.0；
- 40 N·m：4 个 episode 非零；
- 20 N·m：7 个 episode 非零，尾部约为 `0.05, 0.12, 0.21, 0.40, 0.44, 0.63, 1.0`。

因此数据不是“完全没有 clipping”；而是**clipping 变化没有反映到当前 median hinge-progress 指标**。

### 4.2 至少有六种替代解释

1. **窗口条件化偏差。** 只有已经进入 stage 3/4、保持稳定抓握且 failure-free 的 25-step 窗口才入选。effort 可能影响“能否到达这个窗口”，而不是进入窗口后的短期进度。
2. **中位数隐藏长尾。** heavy16 中已经存在持续 saturation 个例，但 `S_ref` 用的是 canonical median，且进度裁决也使用中位数。
3. **25 control steps 对 force boundary 太短或分辨率太低。** 尤其当前没有 static breakaway，门一旦运动，剩余主要是 kinematic tracking。
4. **arm joint effort 与 hinge torque 没有建立映射。** 六个关节各自的 20/40 N·m 不能直接与门轴 torque 比较；需要 Jacobian、把手到铰链力臂和接触方向。
5. **torque authority 不足。** v23 记录的是 nominal/clipped command 或 PRE state 推导的 POST estimate，不是 solver-reported applied torque。
6. **PD/contact/door drive 可能是主导瓶颈。** effort 降低后 tracking error 或 contact impulse 可能变化，但当前裁决变量只看 hinge angle difference。

因此，正确结论是：

```text
SELECTED_STABLE_GRASP_PROGRESS_PROBE_NONDISCRIMINATIVE_OVER_20_TO_100_NM
```

而不是：

```text
ARM_TORQUE_IS_NOT_A_CONSTRAINT
TASK_REQUIRES_LESS_THAN_20_NM
```

PiPER 官方快速手册给出 1.5 kg payload、626.75 mm reach、供电和运动范围，但没有提供六关节的逐关节持续/峰值力矩曲线；项目中的 20–100 N·m profile 不能作为实机 authority。

---

## 5. `DOOR_MODEL_INSUFFICIENT` 中本地尚未充分点名的模式

### 5.1 不只是“没有 E2”，而是阻力物理缺少关键形态

**[Receipt]** 当前 `door.py` 只有：

- hinge drive max force；
- hinge drive damping；
- hinge drive stiffness；
- door mass/geometry。

没有显式 joint friction、static breakaway、static-to-dynamic hysteresis 或 stiction 状态。

**[推断]** 这会产生一种根本性的识别问题：提高 damping/stiffness 往往改变速度响应或回弹，而不能构造“先卡住、超过阈值后突然动起来”的真实 breakaway 事件。策略可以用持续小运动、几何跟随或 door drive 的数值行为绕过所谓力边界。

### 5.2 E-zone 比较量尚未物理同构

**[Receipt]** v23 physics-first D1 用 door-side scripted torque bracket 与统一 `40 N·m` arm effort boundary 比较，形成 provisional E0/E1/near-E2，且 `confirmed_E2=false`。:chatgpt-content-reference{index="33"}

**[推断]** door-side hinge torque 与某一 arm joint effort limit 不是同一物理量。缺少：

\[
\tau_{\text{joint}}=J(q)^\top w_{\text{EE}}
\]

以及：

\[
\tau_{\text{hinge}}
=
\hat h^\top\left((r_{\text{handle}}-r_{\text{hinge}})\times f_{\text{EE}}+m_{\text{EE}}\right)
\]

因此 v23 的 E1 更准确地说是 **scripted-door-resistance bucket**，还不是 robot-specific force-feasibility zone。

### 5.3 0.02 rad 的 opening pass 太弱

**[Receipt]** atlas 只需达到 `0.02 rad` opening progress 即视为 positive bracket。:chatgpt-content-reference{index="21"}

**[推断]** 约 1.15° 的短时运动只能证明“门动了”，不能证明：

- 能跨过 breakaway；
- 能持续打开；
- 能在稳定抓握下产生足够 hinge work；
- 能完成 release/clearance；
- arm-only 与 base-assisted 之间出现可辨识边界。

### 5.4 realized classifier 的问题主要不是缺 trace，而是 atlas 表达错误

**[Receipt]** `0/768` classified 中：

- 755 是 `UNCLASSIFIED_NO_ATLAS_MATCH`；
- 13 才是 `UNCLASSIFIED_NO_TRACE`。

来源：:chatgpt-content-reference{index="29"}。

这意味着主要故障不是“少了几个日志”，而是**连续 realized 参数 tuple 无法精确匹配九个离散 atlas cell**。v24 不能只修文件路径；必须改为连续 physics surrogate、区间分类或带 OOD 拒绝的距离分类。

### 5.5 失败拓扑显示 D1 仍混合了几何、抓握和 handoff 失败

**[独立复算]**

| 分组 | Goal | pre-stage5 failure | stage5 non-goal |
|---|---:|---:|---:|
| D0 FULL | 248 | 7 | 1 |
| D0 RP0 | 249 | 7 | 0 |
| D1 FULL | 235 | 9，且全部停在 max-stage4 | 12 |
| D1 RP0 | 229 | 18，分散在 max-stage0–4 | 9 |

来源：:chatgpt-content-reference{index="25"}。

**[推断]**

- D1 FULL 经常能完成抓握/opening，却在 swing→completion handoff 失败；
- D1 RP0 增加了更早的 approach、pregrasp、grasp/opening failure；
- 这不像单一“力不足”轴，而像 geometry、reach、planar placement、contact continuity 和 handoff 的混合轴。

### 5.6 release 行为可能被固定阈值主导

**[独立复算]**

- 1024 episode 中只有 833 个有 `hinge_at_release`；
- 191 个缺 release 记录；
- 其中 133 个已经 goal，却仍没有 release 记录；
- 有记录者的 `hinge_at_release` 集中在 `1.6000–1.6191 rad`，中位数约 `1.6049 rad`。

来源：:chatgpt-content-reference{index="25"}。

**[推断]** 这更像围绕固定 `release_hinge≈1.60` 的事件逻辑或 telemetry convention，而不是根据 damping/rebound 自主选择的自然 release。v24 必须把：

- “没有 release event”；
- “crossing 后仍保持抓握”；
- “固定角度 release”；
- “低速 quiet release”；
- “受控 fling”；

明确拆开。

### 5.7 几何可能比当前 force axes 更有区分力

**[独立探索，非因果]** 按 handle height 分桶：

- `≤0.90 m`：goal 约 89.6%；
- `0.90–0.98 m`：约 96.2%；
- `0.98–1.05 m`：约 97.6%；
- `>1.05 m`：约 93.8%。

来源：:chatgpt-content-reference{index="25"}。

它与其他 dynamics 参数混杂，不能解释为 handle-height 因果效应；但足以说明 v24 在构建 E1/E2 时必须固定或分层 handle height，否则姿态/reach 与 friction 会继续混在一起。

---

## 6. 对 v23 执行过程本身的评审

### 6.1 做得好的部分

| 项目 | 评审 |
|---|---|
| RP0 语义 | 真正从 action distribution 中屏蔽，masked 维度不进入 log-prob、entropy、KL 和 PPO ratio；不是 sample 后 clamp。 |
| typed outcome | missing 不补零；H2/H3/H5 保持 inconclusive/unadjudicated |
| 无 hidden control | worker prompt 明确禁止 scripted assist、root teleport、oracle fallback 等训练作弊路径。 |
| 协议纠错 | 本地 audit P1–P11 和 owner decision 及时撤销了未经授权的 FULL/ACUTE 对称 completeness gate，并恢复 physics-first D1。 |
| 全矩阵执行 | 16/16 cell、双 seed、全部自然 rc0，且没有把研究完成提升为 release |
| 证据层级 | torque fields 绑定 authority；实际 PhysX torque 不可得时保持 UNKNOWN/estimate |

### 6.2 仍未偿还的分析债务

1. **realized dynamics 0/768。** 这使 H3/H5 的核心分层根本无法运行，而不是一个小比例缺失。
2. **1280 intervention outcome 全 pending。** 有触发记录，不等于有 treatment effect。
3. **无 state clone、无 recurrent restore。** 所有干预都是 forward switching，无法从同一个接触状态做强反事实。
4. **干预 treatment dose 未审计。** 对 chronic RP0 policy 再执行 `ACUTE_RP0` 可能是零剂量；对本已接近零 base command 的状态执行 `BASE0_AT_GRASP` 也可能几乎无差。
5. **rescue trigger 与 candidate 轨迹强耦合。** 52 个 rescue/oracle trigger 仅出现在少数 FULL cells；所有 RP0 cell 都是 0。它可能识别的是当前 policy 的 tracking/saturation trajectory，而非门的物理 hardness。:chatgpt-content-reference{index="30"}
6. **触发与最终失败不一致。** 例如 seed1 G5 holdout 只有 54/64 goal，但 rescue trigger 为 0；说明触发器不能代表一般困难 episode。
7. **Route-A 仍按 goal/crossing/unsafe 选点。** 在 90%+ success ceiling 下，它会偏向“能完成”而非“机械行为更好”，并忽略 force margin、clearance、release 和学习效率。
8. **release telemetry 非随机缺失。** 133 个成功 episode 没有 release event，使 release/root-x 相关分析存在明显选择偏差。
9. **命名债务。** `base_v23_G3_scratch_D0_full.yaml` 文件名仍写 scratch，但机器字段是 `warm_head_reset`；这不会改变科学结果，却容易破坏未来自动审计。
10. **旧数据 posthoc 修复不能追溯升级预注册因果结论。** v24 可以把 v23 1280 episode 做成 `DESCRIPTIVE_POSTHOC`，但不能在看过 outcome 后修 classifier，再把 H3/H5 改写成原本已通过的 causal hypothesis。

---

## 7. 代表视频的实际行为学观察

我逐个检查了附件中的 9 个 v23 视频与 3 个 v22 视频。视频只构成**定性行为证据**，不能替代 1024-episode 统计或 causal intervention。

### 7.1 v23

| 视频组 | 观察 |
|---|---|
| A1 G7 seed0 D1 FULL，ordinary/high-damping/fast-rebound | 有明显持续前倾/侧向姿态；机械臂持续挂住把手并随门运动；机器人在接近门板和门框的狭窄通道中穿过；三种 dynamics 视觉策略高度相似，均为 hold-open，没有明显 fling |
| B1 G3 seed1 D0 FULL | 臂部使用很大的上绕轨迹，trunk 与门板/边缘距离较小；过门时仍保持把手接触；release 很晚，臂在通过后仍较高 |
| B2 G4 seed1 D0 RP0 | 机身看起来比 FULL 更平，但通过 yaw/平面站位和高臂轨迹补偿；仍是 hold-open；在门接近大角度后才松手，身体仍较贴近 doorway |

代表视频：

- :chatgpt-content-reference{index="40"}
- :chatgpt-content-reference{index="41"}
- :chatgpt-content-reference{index="42"}
- :chatgpt-content-reference{index="43"}

### 7.2 v22 对照

- G1 ordinary 同样是明显前倾、长时间持门、较晚 release；
- G4 high-damping 的代表 clip 明显贴近门板，对应记录中的 36.637 N unauthorized panel contact；
- G5 high-damping 出现 thigh/panel bracing，对应 292.119 N，超过 180 N p95 profile。

代表视频：

- :chatgpt-content-reference{index="44"}
- :chatgpt-content-reference{index="45"}
- :chatgpt-content-reference{index="46"}

v22 的正式 render adjudication也明确写出：ordinary、fast-rebound、high-damping 都使用相似的强前倾姿态；策略为 `HAND_HOLD_CLEARANCE`，未观察到 controlled fling；pooled goal 为 46–47/48，但 clearance 只有 29/9/16 of 48。来源：:chatgpt-content-reference{index="47"}、:chatgpt-content-reference{index="48"}。

### 7.3 行为结论

**[定性]**

- **姿态使用形态：** FULL 主要是持续性而非条件性姿态；RP0 用平面站位与臂轨迹替代。
- **hold-open vs fling：** 代表视频几乎全部是 hold-open，未见清晰 controlled fling。
- **clearance：** 能通过，但不是“宽裕而优雅”的 clearance；身体、臂和门板常处于较小间距。
- **身体与门的贴近程度：** 普遍偏近；v22 已有明确 body-contact 超限个例。
- **release 自然度：** release 晚、部分被遮挡、门已处于大角度；看不出根据 rebound/damping 主动选择 quiet release 或 fling。
- **策略条件化：** ordinary/high-damping/fast-rebound 的视觉策略相似，尚未形成理想 policy 所需的 dynamics-conditioned strategy diversity。

---

## 8. Part 1 最终裁定

v23 最有价值的结果不是“姿态不重要”，而是：

> **在当前 drive-based 门模型与 success-ceiling 评测下，重新训练的策略可以用多种运动自由度维持高完成率，因此 success count 无法识别姿态、力边界和协同机制；同时，现有 E-zone、torque ladder、realized classifier 与 intervention adjudication 还不足以完成 force-feasibility 的因果裁决。**

这是一条高信息量负结果，也恰好说明 v24 应把重点从“再做一次成功率矩阵”转向：

1. friction/breakaway 的真实可辨识边界；
2. robot-side force capacity；
3. mechanics 与行为质量指标；
4. matched arm–base interventions；
5. 最小、可选择的 posture gate。

---

# Part 2 — DoorDog `base_v24` 修订方案

# DoorDog A2+PiPER `base_v24` R1  
## Friction/Breakaway Identification, Posture Force-Value Adjudication, and Arm–Base Coupling Supervision

**建议终局类型：** `V24_RESEARCH_PASS_NO_RELEASE`，除非另有独立 release round。  
**本 worktree 角色：** push-door novelty engine。pull-door 与 student distillation 在并行 worktree，不纳入本轮训练矩阵。  
**不确定值：** 一律标 `UNKNOWN`，由 P0/P1 physics calibration 在 formal 第一轮 optimizer update 前冻结。

---

## 1. 相对 v24 草案的关键修订

| 草案内容 | 修订 | 理由 |
|---|---|---|
| “RP0 全面平价→姿态非必需” | 改为 `PRIOR_POSTURE_PHYSICAL_VALUE_UNRESOLVED` | 正式 H2 inconclusive；D1 存在 seed/init 交互 |
| “effort 20 无退化→arm torque 不是约束” | 改为 `PRIOR_EFFORT_PROBE_NONDISCRIMINATIVE` | 只是 selected stable-grasp median progress null；有 saturation tail，actual torque UNKNOWN |
| v24 P0 修复后“正式关闭” v23 H3/H5 | 只能输出 posthoc descriptive adjudication | 不能在看过 outcome 后追溯升级预注册因果结果 |
| 直接给 hinge 加 friction | 先 feature-detect native per-axis friction API；否则显式 proxy | 项目 runtime 版本与 API availability 为 `UNKNOWN` |
| E-zone 继续用 door torque vs 40 N·m | 改为 door requirement / robot-side hinge-moment capacity 的无量纲比值 | 两者必须经过 Jacobian、力臂和接触映射 |
| 8-run factorial 保留 | 保留 `{FULL,RP0}×{DF0-sham,DF1}×2 seeds` | init 轴可因预算/次要科学价值移除，但不是因为“完全平价” |
| Route A 继续以 goal 为主 | mechanics/behavior lexicographic selection | success 已到天花板 |
| coupling critic 只写“离线训练” | 明确定义 2×2 arm/base intervention 与 difference-of-differences target | critic 必须有可识别监督语义 |
| gate 写 `aφ=g·Δφ` | 使用 distribution-correct Bernoulli gate + conditional Gaussian posture proposal | 避免 sample 后乘 gate 导致 PPO optimized action 与 executed action 不一致 |
| gate 输入写 force/progress/margin | 冻结 `a2_posture_gate_obs_v1`，禁止 task/stage/door-specific privileged fields | 满足 pull-door worktree 可直接复用的接口承诺 |

v24 草案来源：

---

## 2. 不可修改的边界

1. 本 worktree 只做 force-feasibility、posture force-value 和 arm–base coupling；不做 distillation 或 pull-door policy。
2. GPU 设计支持 4–8 卡：8 卡单波，4 卡两 sub-wave。
3. 所有缺失和失败必须 typed，不得 missing→0。
4. confirmed E2 只进入 held-out evaluation，训练 share 始终为 0。
5. 所有代码改动 additive、config-gated、默认关闭；friction/gate 关闭时历史 checkpoint 必须可加载并可复评。
6. 不把 SHA-256 或 digest 当作科学天花板；身份依赖 readable commit、source/config/checkpoint path、schema 与 runtime receipt。
7. success-rate 只作 guardrail，主轴是 mechanics 与 behavior quality。
8. 沿用设计规则 11–15：物理事件对齐、汇总表包含本轮因变量、success ceiling 下换测量轴、按 realized telemetry 分层、不得自创 reducer gate。

---

## 3. 研究问题与预注册分支

### RQ1 — friction/breakaway 能否建立可辨识的 E1/E2？

```text
H1a: stable parameter domain 内，door-side breakaway torque 对 friction 参数单调。
H1b: robot-side arm-only capacity 与 door requirement 能形成 E0/E1。
H1c: 至少存在 held-out E2：arm-only 不可行，但 oracle/base rescue 可行。
```

Typed outcomes：

```text
V24_FRICTION_AXIS_DISCRIMINATIVE
V24_FRICTION_AXIS_NONDISCRIMINATIVE
V24_E1_ESTABLISHED
V24_E1_NOT_ESTABLISHED
V24_E2_HELDOUT_ESTABLISHED
V24_E2_NOT_ESTABLISHED
```

### RQ2 — policy 是否出现 load-conditioned behavior？

不只看 goal，而看：

- breakaway latency；
- hinge work；
- hold/fling；
- release timing；
- posture duty；
- arm saturation dwell；
- foot slip / force redistribution；
- clearance。

### RQ3 — roll/pitch 的力价值终裁

预注册四分支，不强迫得到“姿态有用”：

```text
A. POSTURE_FORCE_RESOURCE_SUPPORTED
B. POSTURE_REACH_RESOURCE_ONLY
C. POSTURE_SUBSTITUTABLE_BY_PLANAR_STRATEGY
D. POSTURE_VALUE_UNRESOLVED
```

### RQ4 — arm–base coupling 的测量与监督形态

目标不是本轮直接修改 PPO，而是产出：

- paired intervention dataset；
- calibrated shadow coupling critic；
- 下一轮 branch-specific credit 的可用监督契约。

### RQ5 — LT-23-08 最小 gated posture 是否选择性开启？

要求：

- E0 低 gate duty；
- E1 有条件开启；
- E1 mechanics 不劣于 FULL；
- posture integral、switching 或无必要 base intervention 小于 FULL；
- 不以 success count 单独通过。

---

## 4. Phase 0 — v23 欠账与历史兼容

### P0.1 连续 realized-dynamics classifier

不再 exact-match 九个 atlas cell。建立只使用 physics probe、在查看 policy outcome 前冻结的连续模型：

\[
x_d =
[\tau_s,\tau_d,c_v,k,c,I_{\text{door}},h_{\text{handle}},r_{\text{handle}},\ldots]
\]

输出：

\[
\widehat{\tau}_{\text{req}}(\theta,\dot\theta,\ddot\theta),
\qquad
\sigma_{\text{req}}
\]

分类使用置信区间和 OOD rejection，而不是强迫每个 episode 入桶：

```text
E0
E1
near-E2
E2
UNCLASSIFIED_PHYSICS_OOD
UNCLASSIFIED_MISSING_TELEMETRY
```

不建议把“分类率≥90%”设成硬 gate，因为它可能鼓励过度外推。更合理的验收是：

- coverage 报告；
- OOD distance；
- calibration error；
- 每个区间最小有效 denominator；
- 未分类保持 typed。

v23 旧数据的输出只能是：

```text
V23_POSTHOC_CLASSIFICATION_RECOVERED_DESCRIPTIVE
V23_POSTHOC_ATLAS_COVERAGE_INSUFFICIENT
```

### P0.2 旧 intervention 的 dose audit

对 1280 个 v23 episode 计算：

\[
D_{\phi}
=
\sum_t\|a_{\phi,t}^{\text{original}}-a_{\phi,t}^{\text{intervened}}\|
\]

\[
D_{\text{base}}
=
\sum_t\|u_{\text{base},t}^{\text{original}}-u_{\text{base},t}^{\text{intervened}}\|
\]

\[
D_{\text{effort}}
=
\sum_t\|\tau_{\max}^{\text{rescue}}-\tau_{\max}^{\text{nominal}}\|
\]

零剂量 episode 不进入 treatment-effect denominator。由于无 clone/recurrent restore，所有旧 intervention 统一标：

```text
FORWARD_INTERVENTION_DESCRIPTIVE_ONLY
```

### P0.3 v23 posture/clearance posthoc

从现有 trace 计算：

- command saturation dwell；
- achieved roll/pitch dwell；
- `S_phi`、`FP_phi`；
- stable-grasp 条件下 posture；
- clearance×posture；
- release missingness；
- body contact 与姿态/door bucket 的关联。

这可以完成诊断债务，但不能把原 H3/H5 改写为 preregistered causal pass。

### P0.4 checkpoint compatibility

至少测试：

1. v22 warm anchor；
2. v23 一个 FULL candidate；
3. v23 一个 RP0 candidate。

在以下配置中加载：

```text
friction_enabled=false
gate_enabled=false
```

要求：

- actor parameter/buffer key contract 不变；
- deterministic observation batch 上动作一致到冻结容差；
-旧 checkpoint 的 RMS/LSTM 恢复；
- evaluator 行为回归无系统偏移。

当前 RP0 实现特意把 mask tensors 保持为 plain attributes，以保护旧 checkpoint strict key set；v24 gate 也应采用“旧路径完全不实例化新参数”的 additive subclass，而不是无条件改 base actor。

### P0.5 warm-start 选择

精确 checkpoint 为 **UNKNOWN**，因为附件不含 `.pt` 和完整 mechanics trace。

本地 planner 应在 FULL candidates 中按预注册规则选择：

1. finite/safe；
2. E1 stable-grasp coverage；
3. hinge work / breakaway；
4. clearance；
5. release quality；
6. goal guardrail；
7. earliest checkpoint。

不建议仅因 D1-trained 就无条件优先，也不建议仅按 63/64 goal 选点。

---

## 5. Phase 1 — joint friction 与 breakaway 建模

### 5.1 先做 runtime feature detection

最新 Omni Physics 提供 per-axis：

- `staticFrictionEffort`；
- `dynamicFrictionEffort`；
- `viscousFrictionCoefficient`。

对 revolute articulation，前两者单位为 torque；动态摩擦应不大于静态摩擦，viscous 项按关节速度叠加。项目实际 Kit/PhysX 是否包含该 API 为 **UNKNOWN**，必须由 smoke receipt 确认。

旧 `physxJoint:jointFriction` 是无量纲、随 transmitted load 变化的 friction coefficient，类似 static/Coulomb，但不是直接 torque threshold；它不适合作为主要可控 E-boundary 轴。

不得把 `UsdPhysics.Joint.breakForce` 当 breakaway friction；articulation joint 会忽略该属性。

建议 backend 枚举：

```text
NATIVE_AXIS_FRICTION_EFFORT
LEGACY_UNITLESS_JOINT_FRICTION
EXPLICIT_BREAKAWAY_PROXY
UNAVAILABLE
```

只有 `NATIVE_AXIS_FRICTION_EFFORT` 或经严格验证的 `EXPLICIT_BREAKAWAY_PROXY` 可支撑正式 torque-boundary claim。

### 5.2 native friction 模型

移动状态下：

\[
\tau_f(\dot\theta)
=
-\operatorname{sign}(\dot\theta)
\left(
\tau_d+c_v|\dot\theta|
\right)
\]

静止状态下：

\[
|\tau_{\text{external}}|\le\tau_s
\Rightarrow \dot\theta\approx0
\]

约束：

\[
0\le \tau_d\le\tau_s
\]

所有 telemetry 同时保存：

```text
requested_static_effort
requested_dynamic_effort
requested_viscous_coefficient
runtime_readback
unit_convention
backend
```

官方 angular viscous coefficient 使用 torque·s/degree，因此项目内部若以 rad/s 分析，必须显式记录 degree↔radian conversion，不能重演 v23 damping/stiffness readback 的 57.3 倍语义混淆。

### 5.3 explicit proxy 路径

若 native API 不可用，可实现两态 proxy：

```text
STICK:
    固定 theta_stick
    可抵消上限 tau_static_proxy
    达到 break condition 持续 N_break steps 后切 SLIDE

SLIDE:
    tau = -tau_dynamic * tanh(omega / omega_eps)
          - c_viscous * omega

RESTICK:
    |omega| < omega_rest
    且 demand 低于带 hysteresis 的 restick threshold
    持续 N_rest steps
```

其中：

- `N_break`、`N_rest`、`omega_eps`、hysteresis 均为 `UNKNOWN`；
- 若 transition 依据的是 commanded/estimated torque，而非 solver-applied torque，必须标 `BREAKAWAY_PROXY_COMMAND_SIDE`；
- proxy 不得命名为 native Coulomb friction；
- 其能量必须满足无主动注能约束。

### 5.4 randomization 轴

第一主轴：

```text
tau_static
rho_dynamic = tau_dynamic / tau_static
viscous_coefficient
```

副轴：

```text
door inertia/mass
existing hinge stiffness
existing hinge damping
handle height
handle lever arm
gripper-handle friction
```

设计原则：

1. 先固定 geometry 做 1D `tau_static` sweep；
2. 再做 `tau_static × rho_dynamic`；
3. 最后加入 mass/damping 的稀疏正交设计；
4. handle height 在 calibration 阶段固定或严格分层；
5. gripper contact friction 是 nuisance，不与 hinge friction 共用同一个参数名；
6. 正/负 opening direction 做镜像 probe，检查符号对称。

所有数值范围在 runtime probe 前均为 `UNKNOWN`，不直接搬用外部论文或实机猜测。

### 5.5 数值稳定 gate

每个候选参数域需通过：

- torque ramp 下 breakaway 单调；
- static hold 无持续 creep；
- moving drag 对速度方向正确；
- static→dynamic 有滞回而无高频 chatter；
- `dt` / substep 改变后的 threshold 漂移在冻结容差内；
- 无 NaN、door teleport、joint-limit impulse 爆发；
- friction work 不产生净正能量；
- fixed-seed replay 一致；
- 与 mass/damping/stiffness 组合无 solver pathology。

Typed outcomes：

```text
V24_NATIVE_FRICTION_AVAILABLE
V24_BREAKAWAY_PROXY_REQUIRED
V24_FRICTION_MODEL_VALID
V24_FRICTION_MODEL_NUMERICALLY_UNSTABLE
V24_FRICTION_RUNTIME_UNAVAILABLE
```

---

## 6. Phase 2 — 机器人侧能力与 E1/E2 certificate

### 6.1 door-side required hinge moment

定义：

\[
M_{\text{req}}
=
M_{\text{static/dynamic friction}}
+
c\dot\theta
+
k(\theta-\theta_0)
+
I\ddot\theta
\]

由 door-only torque ramp、constant-velocity 和 fixed-torque probes 建立 surrogate，而不是只用“是否移动 0.02 rad”。

### 6.2 arm-side directional capacity

在 stable-grasp state bank 中，使用：

\[
\tau = J(q)^\top w
\]

估计末端目标 wrench 方向上的 local joint margin。进一步映射到门轴：

\[
M_{\text{arm}}(s)
=
\max_{w\in\mathcal W_{\text{arm}}(s)}
\hat h^\top
\left[
(r_h-r_o)\times f + m
\right]
\]

约束集合至少包括：

- configured joint effort margin；
- joint position margin；
- tracking error；
- contact direction；
- gripper retention；
- self-collision；
- 当前 arm pose。

这仍是 **model-derived configured-sim capacity**，不是实机 torque authority。

### 6.3 无量纲 load ratio

\[
\lambda(s,d)
=
\frac{M_{\text{req}}(d)}
     {M_{\text{arm}}(s)+\epsilon}
\]

初始解释：

```text
E0: arm-only 有明显正余量
E1: 余量低、成功概率与 mechanics 指标对姿态/站位敏感
E2: arm-only 在稳定抓握和正确几何下仍无法 break away，
    但高 effort/oracle/base assist 能恢复
```

具体阈值为 `UNKNOWN`，由 physics-only 与 historical-checkpoint preformal probes 在 formal 前冻结。

### 6.4 confirmed E2 的必要条件

一个 episode 不能因“没抓住把手”或“够不到”被叫做 E2。confirmed E2 需同时满足：

1. stable grasp；
2. 目标切向方向正确；
3. reach/joint-limit 仍有效；
4. arm utilization 高或 local margin 低；
5. arm-only hinge work 持续不足；
6. matched rescue 能显著恢复；
7. 无 solver pathology。

否则 typed 为：

```text
GEOMETRY_INFEASIBLE
GRASP_INFEASIBLE
DIRECTION_WRONG
CONTACT_SLIP
NUMERIC_PATHOLOGY
FORCE_INFEASIBLE
```

confirmed E2 始终只进入 held-out evaluation。

---

## 7. 在成功率天花板下让 E1/E2 真正有判别力

### 7.1 主 mechanics 轴

- breakaway probability；
- breakaway latency；
- fixed-window hinge work；
- post-break hinge velocity；
- hinge progress conditional on stable grasp；
- arm clipped-utilization integral；
- saturation dwell；
- arm tracking error；
- directional force margin；
- grip retention；
- rescue effect；
- foot slip；
- support/contact margin。

### 7.2 behavior-quality 轴

- `HOLD_OPEN` / `CONTROLLED_FLING` / `UNSAFE_RELEASE`；
- release angle、release speed、release root pose；
- no-release rate；
- post-release recontact；
- minimum body-panel/frame clearance；
- body contact force；
- crossing path width；
- arm joint margin at crossing；
- completion time。

建议事件定义：

```text
QUIET_HOLD_RELEASE:
    crossing 时仍稳定持握，
    crossing 后低角速度、低接触冲击 release

CONTROLLED_FLING:
    crossing 前 release，
    release 后门继续向目标方向增加开度，
    无高 rebound、无 body recontact、无 unsafe contact

UNSAFE_RELEASE:
    release 后门回弹导致 recontact，
    或 excessive angular velocity/body contact
```

### 7.3 success guardrail

DF0 holdout goal 只用于检查是否严重退化。草案中的 “v23 baseline −3 doors” 可以保留为暂定 guardrail，但最终门数应由 local planner 根据相同 scenario/seed denominator 冻结；不把它当主要科学胜负。

---

## 8. Phase 3 — historical zero-shot re-evaluation

训练前，先用历史 v22/v23 checkpoints 在以下集合零样本复评：

```text
DF0 historical path
DF0-sham friction code path with zero friction
DF1 E0
DF1 E1-low
DF1 E1-high
held-out E2 candidates
```

目的：

1. 证明 additive code path 没破坏历史策略；
2. 确认 friction 参数确实能让旧 policy 出现连续退化；
3. 冻结 E1 范围；
4. 检查 E2 是否是力失败，而非抓握/几何失败；
5. 冻结 formal randomization mixture。

若 historical policy 在所有 friction 值上仍无 mechanics 退化，则直接：

```text
V24_FRICTION_AXIS_NONDISCRIMINATIVE
```

不进入昂贵 formal training。

---

## 9. Phase 4 — Wave 1 science factorial

### 9.1 矩阵

| Door distribution | Posture | Seed |
|---|---|---:|
| DF0-sham | FULL | 0 |
| DF0-sham | RP0 | 0 |
| DF1 | FULL | 0 |
| DF1 | RP0 | 0 |
| DF0-sham | FULL | 1 |
| DF0-sham | RP0 | 1 |
| DF1 | FULL | 1 |
| DF1 | RP0 | 1 |

- 统一 warm-start；
- 统一 reward；
- 4096 env × 2500 batches、save250 可沿用 v23 production precedent；
- confirmed E2 share=0；
- DF0-sham 走完整 friction code path，但 friction 参数为零；
- 另保留 feature-disabled DF0 作为历史 parity smoke，不计入 8-run 科学矩阵。

取消 init 轴的理由是：

> H1 已没有一致正效应，且 v24 的主研究问题是 physics×posture。

不是：

> warm 和 head-reset 已证明完全等价。

### 9.2 GPU 编排

```text
8 GPU: 8 cell 单波
4 GPU: seed0 四 cell -> seed1 四 cell
```

每条 code path formal 前均做 `64 env × 10 batch` smoke。训练与 eval 不共占同一 GPU。

### 9.3 checkpoint 选择

Route A 不再以 goal 第一。建议机械顺序：

1. finite、无 unsafe；
2. E1 stable-grasp denominator；
3. E1 breakaway / hinge work；
4. arm saturation dwell；
5. clearance；
6. release quality；
7. goal guardrail；
8. earliest checkpoint。

同时保留全 checkpoint curve，以比较学习效率，而不是只看 winner。

若两 seed 的主要 mechanics effect 符号相反，则预注册触发第三 seed；否则不追加。

---

## 10. RQ3 — 姿态力价值的终裁设计

### 10.1 三层证据

#### A. Chronic policy contrast

比较经过训练的 FULL 与 RP0：

- task success；
- mechanics；
- planar path；
- arm pose；
- clearance；
- release。

回答“姿态是否可被重新训练后的策略替代”。

#### B. Acute matched posture-off

在 stable grasp、相似门角、root SE(2)、arm pose 和 friction 下关闭姿态 proposal。

必须记录实际 treatment dose；dose≈0 不计入。

回答“当前 configuration 中姿态是否有即时作用”。

#### C. Planar-compensated RP0

允许 x/y/yaw 与 arm trajectory 适应，但禁止主动 pitch/roll。

回答“姿态作用是否可被平面策略替代”。

### 10.2 Reach 与 force 分离

定义 reach/geometry mediators：

- EE pose/orientation error；
- joint-limit margin；
- arm manipulability/directional margin；
- grasp stability；
- contact direction；
- root-handle geometry。

定义 force outcomes：

- breakaway；
- hinge work；
- saturation dwell；
- rescue effect；
- foot-force redistribution。

判读：

| 结果 | 裁决 |
|---|---|
| FULL 改善 force outcomes，且在匹配 reach/contact 后仍保留 | `POSTURE_FORCE_RESOURCE_SUPPORTED` |
| FULL 只改善 reach/contact，匹配后 force effect 消失 | `POSTURE_REACH_RESOURCE_ONLY` |
| acute FULL 有效，但 chronic RP0 通过平面站位恢复 mechanics | `POSTURE_SUBSTITUTABLE_BY_PLANAR_STRATEGY` |
| denominator 或匹配不足 | `POSTURE_VALUE_UNRESOLVED` |

### 10.3 对应论文叙事

**分支 A：**

> Load-gated posture expands the feasible wrench set under hinge breakaway.

**分支 B：**

> Posture primarily preserves reach and contact geometry; sustained force is supplied by arm actuation and planar bracing.

**分支 C：**

> Active posture is one member of a redundant strategy set. Policies can trade posture for planar repositioning, but with different release, clearance or holding costs.

任何一个分支都可形成干净结论，无需强行证明 roll/pitch 是力资源。

---

## 11. RQ4 — arm–base 力耦合测量

### 11.1 telemetry 契约

#### Arm

- q/qdot；
- target / target increment；
- nominal torque；
- clipped torque；
- solver-applied torque，若可得，否则 `UNKNOWN`；
- effort utilization；
- joint-limit margin；
- EE pose/twist；
- EE wrench estimate；
- gripper contact/stability。

#### Base / locomotion

- 5D high-level command；
- achieved roll/pitch/yaw；
- root linear/angular velocity与acceleration；
- frozen A2 policy 12D output；
- leg target、q/qdot、torque estimate、power；
- commanded vs achieved planar velocity。

#### Feet

- per-foot normal/tangential reaction force；
- contact state；
- slip velocity；
- friction utilization；
- CoP/support polygon margin。

若当前 runtime 无可靠 per-foot force，标：

```text
FOOT_FORCE_SOURCE_UNAVAILABLE
```

不得用零代替。

#### Door

- hinge angle/velocity/acceleration；
- friction backend/mode；
- modeled friction torque；
- required torque；
- hinge work；
- breakaway event；
- handle contact geometry。

### 11.2 2×2 matched intervention

在 stable-grasp state bank 上构造：

| | Arm actual | Arm safe-hold |
|---|---|---|
| Base actual | \(Y_{11}\) | \(Y_{10}\) |
| Base neutral | \(Y_{01}\) | \(Y_{00}\) |

其中：

- `base neutral`：x/y/yaw/pitch/roll semantic neutral；
- `arm safe-hold`：保持当前 arm target 与 gripper state，不是全零 arm action；
- horizon 为 `UNKNOWN`，由 P0 pilot 冻结；
- 四分支使用相同 state、RNG、door params、policy hidden state。

优先实现恢复：

- robot/door root and joint state；
- stage counters；
- staged-reset state；
- actor/critic LSTM hidden state；
- action history；
- RNG state。

contact solver cache 能否精确恢复为 **UNKNOWN**。若不支持，则输出：

```text
STATE_CLONE_APPROXIMATE_CONTACT_CACHE_UNRESTORED
```

并把结果降级为 paired forward proxy。

### 11.3 coupling target

对每一个 mechanics outcome \(y\)：

\[
\Delta_{\text{cpl}}^{(y)}
=
Y_{11}^{(y)}
-
Y_{10}^{(y)}
-
Y_{01}^{(y)}
+
Y_{00}^{(y)}
\]

推荐 outcome vector：

\[
y =
[
\text{hinge work},
-\text{breakaway latency},
-\text{arm clip dwell},
-\text{foot slip},
\text{stability margin},
\text{clearance}
]
\]

这样 interaction 具有明确语义：

- 正 hinge-work coupling：base+arm 合作超过二者独立贡献之和；
- 负 slip/stability coupling：合作动作带来破坏性干扰；
- 近零：当前状态可近似分解。

### 11.4 shadow coupling critic

输入：

\[
C_\psi
(
h_t^{priv},
a_t^{base},
a_t^{arm},
d_t
)
\]

其中 `h_priv` 是 privileged recurrent history，`d_t` 是 realized dynamics。

输出多头：

```text
delta_hinge_work
delta_breakaway
delta_arm_saturation
delta_foot_slip
delta_stability
delta_clearance
uncertainty
```

训练损失：

- Huber regression；
- interaction sign classification；
- pairwise ranking；
- uncertainty calibration。

评测：

- R²；
- Spearman；
- sign accuracy；
- calibration error；
- E0/E1/E2 分层；
- unseen handle height；
- unseen friction组合；
- historical vs newly trained checkpoint。

本轮不把 critic 输出反馈 PPO。typed outcomes：

```text
V24_COUPLING_SIGNAL_IDENTIFIED
V24_COUPLING_SIGNAL_NOT_IDENTIFIED
V24_COUPLING_FORWARD_PROXY_ONLY
V24_COUPLING_CRITIC_CALIBRATED
V24_COUPLING_CRITIC_UNCALIBRATED
```

---

## 12. LT-23-08 — 最小 gated posture

### 12.1 动作结构

当前 base command 为：

```text
[vx, vy, yaw, pitch, roll]
```

v23 RP0 屏蔽 raw indices `[3,4]`。

最小 gate 定义：

\[
m_t\sim\mathrm{Bernoulli}(p_t)
\]

\[
z_{\phi,t}\sim\mathcal N(\mu_{\phi,t},\sigma_{\phi,t})
\]

\[
a_{\phi,t}=m_t z_{\phi,t}
\]

\[
u_{\text{base},t}
=
[v_x,v_y,\omega_z,a_{\text{pitch}},a_{\text{roll}}]
\]

PPO log-prob：

\[
\log\pi
=
\log\pi_{\text{planar+arm}}
+
\log\mathrm{Bernoulli}(m_t;p_t)
+
m_t\log\mathcal N(z_{\phi,t};\mu_{\phi,t},\sigma_{\phi,t})
\]

这样：

- gate off 时 posture 精确为 0；
- Gaussian posture 不贡献 log-prob；
- gate on 时完整优化 posture；
- executed action 与 optimized latent action 一致；
- RP0 可解释为 `m_t≡0`；
- FULL 可解释为 `m_t≡1`。

不建议把一个普通 Gaussian action sample 后直接乘 sigmoid gate，因为这会改变实际执行分布而没有正确修正 PPO likelihood。

### 12.2 gate dwell

为避免高频开关：

- gate 只每 `K_gate` control steps 采样一次；
- 中间保持；
- 只在决策 step 计算 Bernoulli log-prob；
- `K_gate=UNKNOWN`，由 P0 chatter/response pilot 冻结。

正则：

\[
L_{\text{gate}}
=
\lambda_{\text{on}}\sum m_t
+
\lambda_{\text{switch}}\sum|m_t-m_{t-1}|
+
\lambda_{\phi}\sum m_t\|z_{\phi,t}\|^2
\]

但这些只能作为主任务已满足后的 tie-breaker，不能压过 hinge work、grasp 和安全。

### 12.3 `a2_posture_gate_obs_v1`

部署侧允许：

- arm q/qdot；
- arm tracking error；
- configured/clipped utilization history；
- joint-limit margin；
- EE twist；
- contact reaction proxy；
- gripper stability；
- generic interaction-axis force/velocity/power；
- base IMU、angular velocity、linear acceleration；
- planar command tracking；
- foot contact/slip summary；
- previous gate 与 previous action；
- validity mask；
- recurrent history。

禁止：

```text
stage id
task id
door_open_io
door type
ground-truth hinge friction
ground-truth door pose
success flag
oracle E-region label
```

### 12.4 通用 interaction-axis 接口

pull 与 push 的 caller 都提供：

```text
interaction_axis_base[3]
```

约定：

```text
沿期望任务进展方向为正
```

gate 只接收投影后的通用信号：

\[
f_{\parallel}=f_{\text{EE}}\cdot d_{\text{int}}
\]

\[
v_{\parallel}=v_{\text{EE}}\cdot d_{\text{int}}
\]

\[
P_{\parallel}=f_{\parallel}v_{\parallel}
\]

它不需要知道该轴来自推门还是拉门。

### 12.5 历史 checkpoint 加载

- gate disabled：实例化旧 actor path，参数 key 完全不变；
- gate enabled + FULL checkpoint：旧 pitch/roll head 作为 `z_phi` proposal，gate 初始化为 open；
- RP0 复评：使用 forced-off wrapper；
- 新增参数 missing-key 只能通过显式 allowlist；
- 必须有 deterministic action parity test。

### 12.6 gate 训练与裁决

只有 Wave 1 确立 E1 后才启动：

```text
GATED-DF1 seed0
GATED-DF1 seed1
```

FULL/RP0 基线直接复用 Wave 1；DF0 以 held-out eval 检查 gate economy，无需再训练一组 DF0 gate。

通过标准：

1. E1 mechanics 对 FULL non-inferior；
2. E0 gate duty 明显低于 E1；
3. posture integral 小于 FULL；
4. switching/chatter 受控；
5. slip/unsafe 不增加；
6. 不能只因 goal 不变而通过。

Typed outcomes：

```text
V24_GATED_POSTURE_SELECTIVE
V24_GATED_POSTURE_ALWAYS_ON
V24_GATED_POSTURE_ALWAYS_OFF
V24_GATED_POSTURE_MECHANICS_DEGRADED
V24_GATED_POSTURE_INCONCLUSIVE
```

---

## 13. pull-door worktree 接口承诺

推门 worktree 应交付：

1. 5D base command 语义不变；
2. `a2_posture_gate_obs_v1` 固定字段、shape、normalization、validity mask；
3. `interaction_axis_base` 正向规范；
4. gate module 可 import，且不依赖 push-door stage/reward；
5. friction 参数化对 hinge 正/负方向镜像；
6. E-region classifier 接受 signed interaction direction；
7. coupling dataset schema 不含 push-only字段；
8. 历史 checkpoint loader 不依赖 push task；
9. 只承诺接口和算法可复用，**不承诺 push-trained gate 权重零样本适用于 pull**。

这与 long-term TODO 中“posture command、gate 输入、certificate 工具链保持 task-agnostic”的承诺一致。

---

## 14. 统计与报告规则

1. 所有主要 effect 按 seed 单独报告，再给 pooled 描述。
2. 能用 CRN/matched state 时优先配对分析。
3. count 指标用 exact binomial interval。
4. continuous mechanics 指标用 episode/scenario 分层 bootstrap。
5. 不再使用固定“5 percentage points”作为普适显著性规则。
6. intervention 必须报告：
   - eligible denominator；
   - triggered denominator；
   - nonzero-dose denominator；
   - completed paired denominator；
   - typed missing reasons。
7. summary table 必须包含本轮因变量：
   - friction；
   - breakaway；
   - hinge work；
   - arm margin；
   - foot slip；
   - posture duty；
   - clearance；
   - release class。
8. 视频只用于解释已量化的行为，不用于代替统计证明。

---

## 15. 总体 typed outcome 树

```text
P0
├─ V23_POSTHOC_CLASSIFICATION_RECOVERED_DESCRIPTIVE
├─ V23_POSTHOC_ATLAS_COVERAGE_INSUFFICIENT
└─ V23_FORWARD_INTERVENTION_DESCRIPTIVE_ONLY

Physics
├─ V24_NATIVE_FRICTION_AVAILABLE
├─ V24_BREAKAWAY_PROXY_REQUIRED
├─ V24_FRICTION_MODEL_VALID
├─ V24_FRICTION_MODEL_NUMERICALLY_UNSTABLE
└─ V24_FRICTION_RUNTIME_UNAVAILABLE

Boundary
├─ V24_FRICTION_AXIS_DISCRIMINATIVE
├─ V24_FRICTION_AXIS_NONDISCRIMINATIVE
├─ V24_E1_ESTABLISHED
├─ V24_E1_NOT_ESTABLISHED
├─ V24_E2_HELDOUT_ESTABLISHED
└─ V24_E2_NOT_ESTABLISHED

RQ3
├─ POSTURE_FORCE_RESOURCE_SUPPORTED
├─ POSTURE_REACH_RESOURCE_ONLY
├─ POSTURE_SUBSTITUTABLE_BY_PLANAR_STRATEGY
└─ POSTURE_VALUE_UNRESOLVED

RQ4
├─ V24_COUPLING_SIGNAL_IDENTIFIED
├─ V24_COUPLING_SIGNAL_NOT_IDENTIFIED
├─ V24_COUPLING_FORWARD_PROXY_ONLY
├─ V24_COUPLING_CRITIC_CALIBRATED
└─ V24_COUPLING_CRITIC_UNCALIBRATED

Gate
├─ V24_GATED_POSTURE_SELECTIVE
├─ V24_GATED_POSTURE_ALWAYS_ON
├─ V24_GATED_POSTURE_ALWAYS_OFF
├─ V24_GATED_POSTURE_MECHANICS_DEGRADED
└─ V24_GATED_POSTURE_INCONCLUSIVE

Overall
├─ V24_RESEARCH_PASS_NO_RELEASE
├─ V24_RESEARCH_CONTINUATION
└─ V24_PHYSICS_AXIS_NO_GO
```

---

## 16. 建议交付物

```text
V23_POSTHOC_DIAGNOSTIC.{json,md}
V24_FRICTION_BACKEND_RECEIPT.json
V24_FRICTION_STABILITY_REPORT.{json,md}
V24_DOOR_REQUIREMENT_SURROGATE.*
V24_ARM_HINGE_CAPACITY_ATLAS.json
V24_E_REGION_FREEZE.json
V24_WAVE1_FINAL_ANALYSIS.{json,md}
V24_POSTURE_VALUE_ADJUDICATION.{json,md}
V24_COUPLING_DATASET_SCHEMA.json
V24_COUPLING_CRITIC_REPORT.{json,md}
V24_POSTURE_GATE_INTERFACE.json
V24_GATE_PILOT_ANALYSIS.{json,md}
V24_FINAL_ANALYSIS.{json,md}
```

代码侧建议保持：

```text
gr00t/rl/isaac_utils/playground/env_rand/door.py
    additive friction backend，默认关闭

gr00t/rl/envs/door/a2_v24_evidence.py
    mechanics / coupling telemetry

gr00t/rl/trl/modules/
    gated actor 作为独立 config path，不改变旧 actor 默认 state_dict

gr00t/rl/config/ablation/wbmanip/base_v24_*.yaml
    DF0-sham / DF1 / FULL / RP0 / GATED

gr00t/rl/tests/
    friction units
    breakaway monotonicity
    energy/passivity
    checkpoint backward compatibility
    gate log-prob/executed-action parity
    treatment dose
    coupling 2×2 topology
```

---

## v24 最终建议

保留本地草案的总体顺序——**先 friction，再正式 FULL/RP0，再 gate/coupling pilot**——但必须修改三个核心叙事：

1. v23 没有证明“姿态非必需”，只证明 current door model 下存在可训练的替代策略；
2. effort ladder 没有证明“arm 力矩不是约束”，只证明旧 probe 不具判别力；
3. v24 的科学单位不应是“某个 friction config 成功了多少门”，而应是：

\[
\text{door requirement}
\leftrightarrow
\text{arm capacity}
\leftrightarrow
\text{base/foot compensation}
\leftrightarrow
\text{behavior quality}
\]

按此修订，v24 即使最终得到“RP0 仍平价”，也不会是又一次天花板 null；它将能够区分：

- 姿态确实增加 force feasibility；
- 姿态只改善 reach/contact；
- 姿态可被 planar strategy 替代但付出 clearance/release 代价；
- 当前机器人或 simulator 仍没有可识别的 coupling signal。

:chatgpt-content-reference{index="23"}

:chatgpt-content-reference{index="24"}

:chatgpt-content-reference{index="26"}

:chatgpt-content-reference{index="27"}

:chatgpt-content-reference{index="31"}

:chatgpt-content-reference{index="34"}

:chatgpt-content-reference{index="35"}

:chatgpt-content-reference{index="36"}

:chatgpt-content-reference{index="37"}

:chatgpt-content-reference{index="38"}

:chatgpt-content-reference{index="39"}