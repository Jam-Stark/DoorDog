# Base v20训练计划规划

**User:** Anonymous  
**Created:** 7/28/2026 18:50:49  
**Updated:** 8/9/2026 0:04:25  
**Exported:** 8/9/2026 0:16:01  
**Link:** [https://chatgpt.com/g/g-p-6a5fa04b1b588191bc51d34da6e5de18/c/6a688988-840c-83ea-a308-9c9481fc4aa9](https://chatgpt.com/g/g-p-6a5fa04b1b588191bc51d34da6e5de18/c/6a688988-840c-83ea-a308-9c9481fc4aa9)  

## Prompt:
2026/8/8 21:47:38

我阅读了你的v22诊断，同样我想带来一些我的思考，不是基于v22的训练表现或者一些细节，而是从大框架下的一些可能算是查漏补缺，对照我的每个问题回答一下：

1 当前door的randomization：增大mass，damping，这些是不是数值还是不够？导致全程其实处于一个arm-only 就能处理的情况？

2 面对现在依旧猖獗的 policy 无脑输出0.4 pitch问题，这个其实是自从v0版本到现在v22版本就有的问题。而自从v10还是多少版本以后，都是基于前一个版本的winner进行warm up，所以我认为这种“强姿态参与”的毛病是从之前的继承过来的？是不是应该考虑重新训练一个policy？但是因为warm up导致一些basic reward被移除了，重新训练可能要考虑恢复，先判断重新训练的必要性。

3 我在你的回答看到了你似乎在v22设计了一个分类器用于判断 门的开易难度。我想说这里训练的是teacher policy，这些是不是可以作为ground truth告诉policy？比如门的mass，damping等

4 roboduet解决robot无脑顶死0.4 pitch靠的是一个显示的reward启发，我在想是否要参考这个设计一个引导/启发式 reward，但是这或许设计到复杂的arm-base 动力学联动/耦合？ roboduet思路：“这个 reward 的本质是一个“目标高度条件化的机身姿态先验”：

> 先判断操作目标位于机身上方还是下方，再引导 policy 选择更有利于机械臂触达目标的 pitch 姿态。

它不是直接奖励机械臂接近目标，也不是直接约束 pitch action，而是通过实际机身 pitch 间接塑造全身协同姿态。

### 逻辑链路

1. 将机械臂目标转换到世界坐标，得到目标的实际高度。
2. 计算目标相对机身基座的高度差。
3. 根据高度差把目标分成三个区域：

| 目标位置姿态引导 |                     |
| -------- | ------------------- |
| 明显低于机身   | 引导机身向下俯，使机械臂更容易够到低处 |
| 位于中间区域   | 不施加额外 pitch 偏好      |
| 明显高于机身   | 引导机身向上仰，使机械臂更容易够到高处 |

4. 对需要引导的区域，指定一个期望 pitch，并用类似平方误差的形式惩罚实际 pitch 与期望 pitch之间的偏差。
5. Policy 最大化总 reward，因此会逐渐学会：目标低时俯身，目标高时抬头。

可以抽象为：

\$$ \Delta h = h\_{\text{target}}-h\_{\text{base}} \$$\$$ p^\*(\Delta h)= \begin{cases} p\_{\text{down}}, & \Delta h < -\tau\_{\text{low}}\\\ \text{无约束}, & -\tau\_{\text{low}}\leq\Delta h\leq\tau\_{\text{high}}\\\ p\_{\text{up}}, & \Delta h > \tau\_{\text{high}} \end{cases} \$$

激活时使用：

\$$ r\_{\text{pitch}}=-w\\,(p-p^\*)^2 \$$

其中 `pitch` 正负对应“俯身还是抬头”取决于机器人坐标系，迁移时不能直接复制符号，必须先做一次姿态可视化确认。

### 为什么需要中间无约束区

如果所有目标都强制对应一个 pitch，policy 会为了微小的目标高度变化频繁摆动机身，并可能破坏行走稳定性。

中间 deadband 的作用是：

- 只有机械臂确实需要机身配合时才介入；
- 普通目标优先交给机械臂自己完成；
- 减少 pitch 抖动；
- 避免这个启发式 reward 压过真正的末端跟踪目标。

高目标和低目标的阈值还可以不对称。例如，低目标可能更早需要俯身，而抬头通常对稳定性和视野影响更大，因此只有目标足够高才触发。

### 可迁移的设计思想

这个 reward 可以概括成：

> 根据任务上下文，动态选择一个有利于完成任务的全身姿态参考。

它可以迁移到很多任务：

- 目标在左侧或右侧 → 引导 base roll；
- 目标在前方较远 → 引导身体前倾；
- 推重物 → 引导降低重心；
- 高处操作 → 引导伸展身体；
- 窄空间操作 → 引导收缩或侧身。

关键是不要直接奖励“朝上”或“朝下”，而要奖励：

> 在当前目标几何关系下，选择正确方向的姿态。

### 它不负责什么

这个 reward 只是粗粒度的 posture prior：

- 不保证末端最终到达目标；
- 不保证机械臂轨迹合理；
- 不限制 pitch action 的变化速度或饱和；
- 不替代正常的姿态跟踪和行走稳定 reward；
- 不应该在纯 locomotion 阶段持续生效。

因此更合理的组合是：

- 末端跟踪 reward 决定“有没有够到”；
- 常规姿态控制决定“身体是否稳定”；
- 这个启发式 reward 决定“面对高低目标时，身体应该往哪个方向配合”。“

## Response:
2026/8/8 21:47:43

> **准备研究项目**
>
> 我会分别回答四个问题，结合当前代码、训练配置、论文与环境设定，重点核对观测权限、奖励设计、随机化范围，以及从已有策略迁移或重新训练的可行性。
>
> **准备了研究项目**
>
> 
>
> **检查阻尼刚度与响应数据**
>
>
> **检查阻尼刚度与响应数据并提取JSON分析结论**
>
> 
>
> **获取门开任务配置并查找门控观测实现索引**
>
> 
>
> **核对观测权限**
>
> 当前策略似乎已获得部分质量信息，但未获得全部动力学参数。教师可使用完整真值，不过部署策略无法直接访问，因此需要通过接触历史、力反馈或记忆机制完成蒸馏，否则会出现可观测性差距。
>
> **核对观测权限完成**
>
> 
>
> **分析门控与门体环境代码**
>
> 
>
> **提取扳手力范围摘要**
>
>
> **设计重启实验**
>
> 我认为完整从头训练值得作为关键消融实验，但不应直接替代现有方案。先比较续训、重置策略头、完整重启三组，并保留早期奖励与阶段化重置，才能区分结构性问题和继承偏差。
>
> **设计了重启实验**
>
> 
>
> **提取扳手力范围摘要**
>
> 
>
> **核实并评估RoboDuet启发式奖励与策略有效性**
>
> 
>
> **检查提取路径及分析文件存在性**
>
>
> **估算动力学影响**
>
> 我会把门把手半径、最大力矩、质量、转动惯量和阻尼分开估算。当前力矩上限可能足以完成开启，但阻尼与接触瞬态仍可能造成明显差异。
>
> **估算动力学影响**
>
> 
>
> **分析姿态干预与目标高度奖励**
>
>
> **检查门体配置并提取姿态干预评估结果**
>
> 
>
> 思考了 12m 44s

## 前置结论

| 问题 | 我的判断 |
|---|---|
| 1. 门是否还不够难 | **部分同意，但主要问题不是 mass/damping 数值简单偏小。** 当前更准确地说是“arm + 强姿态足以处理”，尚未形成可靠的 `arm + posture infeasible` 区域。真正决定静态力边界的是 hinge stiffness、max-force/resistive torque、摩擦和机械臂真实力矩余量。 |
| 2. `0.4 pitch` 是否由 warm-start 继承 | **很可能有明显继承效应，但不是纯粹历史坏习惯。** 当前几何和 reward 也让大 pitch 在接近/抓握阶段真实有用。需要 scratch 对照，但不宜直接把主线全部改成从零训练。 |
| 3. teacher 能否直接看到 mass/damping | **可以，而且当前 teacher actor 已经直接看到 mass。** 但 damping、stiffness、hinge max-force 尚不在当前 8D `privileged_door_info` 中。建议区分 oracle teacher、critic privilege 和可由 history 推断的 dynamics latent。 |
| 4. 是否采用目标高度条件化 posture prior | **建议采用。** 但应做成“阶段条件化几何先验 + 有界 policy residual + 困难状态下额外 force residual”，不能在整个 episode 中持续奖励某个 pitch。 |

---

# 1. 当前 door randomization 是否仍然不够难？

## 结论：没有建立真正的 force-infeasible regime，但不能简单归因于 mass/damping 太小

首先需要修正一个表述：当前 policy 并不是纯粹的 `arm-only`。

v22 已经证明 roll/pitch 是 load-bearing 的，而且现有行为仍有很强的 base 姿态参与。因此当前更准确的能力区域是：

```text
arm + base posture 足够
body-panel contact 不需要
```

而不是：

```text
arm alone 足够
```

v22 最终只实现了 H0/H1/H2，H3/H4 的高阻力与 compound extreme 区域没有建立；最终状态也明确记录为 randomization boundary identified，而不是完成了完整五类 dynamics coverage。

## 为什么单纯增加 mass 不一定让 arm 推不动

对绕竖直铰链旋转的门，可近似写成：

$$
\tau_{\text{required}}
=
I\alpha
+
c\omega
+
k(\theta-\theta_0)
+
\tau_{\text{friction}}
$$

其中：

- `mass` 主要通过转动惯量 $I$ 影响加速度项 $I\alpha$；
- `damping` 通过 $c\omega$ 影响运动中的阻力；
- `stiffness / spring / max force / static friction` 决定准静态情况下仍然存在的持续阻力。

因此：

```text
增大 mass:
  使快速加速和 fling 更困难
  但 policy 可以选择慢慢推

增大 damping:
  使快速运动更困难
  但 policy 可以降低 angular velocity

增大 stiffness / resistive torque / static friction:
  即使很慢也必须持续输出较大的力
  更容易真正超过 arm + posture 的能力
```

这解释了为什么 `160 kg` 的门仍可能被当前 policy 处理：只要不要求较高角加速度，质量本身并不会持续产生绕竖直铰链的重力力矩。

**所以，mass 更适合研究 fling 和惯性；damping 更适合研究 fling 与 hold-open 的策略选择；stiffness/max-force/static resistance 才更适合建立 body-assist 的力边界。**

## 当前数值并不能简单称为“小”

Wave 2 实际配置大致覆盖：

```text
H0:
  damping 50-150
  stiffness 6-20
  max force 10-24 N·m

H1:
  damping 30-120
  stiffness 2-6
  max force 5-12 N·m

H2:
  damping 15-50
  stiffness 6-20
  max force 10-18 N·m

mass:
  80-160 kg

handle:
  0.85-1.10 m
```

这些范围在数值上不算窄。DoorMan 论文中的另一套门模型使用 `80-120 kg`、hinge max force `20-30 N·m`、damping `5-10`、stiffness `10-20`；但单位约定、机器人结构和 drive 实现不同，只能作为量级参考，不能直接照搬。`Xue 等 - 2025 - Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer.pdf`

v22 没有形成极限力边界，更可能是三个原因叠加：

1. **当前 arm 仍为每关节 100 N·m 的 simulation profile。**  
   PiPER 手册只公开了 `1.5 kg` 额定负载、`626.75 mm` 工作半径、最大功耗不超过 `120 W`，没有公开各关节连续或峰值扭矩，因而 100 N·m 并没有硬件依据。`piper.pdf`

2. **真正的高持续阻力 H3/H4 没有实现。**

3. **当前 `arm_failure` 定义不是可靠的不可行性检测。**  
   v22 中它在大量最终成功的 episode 中也会触发，因此更接近“低 margin、慢进展或 tracking 困难”，而不是“机械臂确实无法继续”。

## 应该怎样判定门是否真的超过 arm + posture 能力

不要根据：

```text
door mass > X
或 damping > Y
```

直接判定困难。

应要求同一个 episode 同时满足：

```text
valid grasp
posture assist 已经尝试
arm effort / tracking / joint margin 持续接近边界
hinge velocity 持续很低
hinge progress 持续接近零
无 body assist
持续 N 个 control steps
```

并做两个反事实：

```text
相同门 + 当前 arm limits:
  失败

相同门 + 更高 arm capability 或允许安全 body contact:
  恢复正向 hinge progress
```

只有这样才能证明存在真正的力可行性边界。

**所以我同意“目前的门还没有把 body-assist 需求逼出来”，但不同意解决方式只是继续提高 mass/damping。优先级应该是：**

```text
1. 校准 arm effort capability
2. 提高或独立控制准静态 resistive torque
3. 再独立增加 damping
4. mass 主要用于惯性/fling 研究
```

---

# 2. `0.4 pitch` 是否是 warm-start 长期继承的坏习惯？是否要从零训练？

## 结论：继承因素很可能存在，但 scratch 不是自动解药

从多个版本连续 `policy_only` warm-start，确实会继承：

- actor 最后一层对 pitch/roll 的输出偏置；
- recurrent hidden representation 中“开门就先大幅倾斜”的状态编码；
- action distribution 的均值和方差；
- 已经形成的 stage visitation 和局部最优 basin；
- “保持最大 pitch 没有明显任务代价”的经验。

即使 optimizer 和 critic 重新初始化，只要 actor 被加载，这个行为先验仍在。

项目历史本身也说明 scratch training 很容易落入不同 basin，曾有多次 scratch run 落错 basin，因此一个 scratch seed 不能作为充分证据。`粘贴的文本 (1).txt`

## 但 P0 也表明：pitch 并不只是坏习惯

v22 的 posture intervention 和 live-grasp atlas 给出了一个非常重要的阶段性结论：

```text
接近/预抓取/建立抓握：
  pitch 对可达性和成功抓握有明显帮助

已经稳定抓住把手以后：
  neutral posture 的方向性 arm capacity 经常已接近最佳
```

这意味着大 pitch 的来源至少有两个：

```text
历史继承：
  过去 policy 已经习惯一开始就打满

结构性收益：
  最大 pitch 确实让早期 reach/grasp 更容易
```

如果使用完全相同的 reward、action parameterization 和 stage scope 从零训练，scratch policy 很可能再次发现：

```text
从开始到结束都保持大 pitch
```

因为它在早期阶段有强收益，却没有明确收益要求它抓稳后恢复中性。

## 是否需要 scratch？

**需要一个 scratch 对照来识别继承效应，但暂时不建议把主开发路线整体切换成 scratch。**

最有诊断力的不是二选一，而是三组：

### A. 当前 warm-start continuation

```text
完整继承现有 actor
```

### B. 局部去继承

保留 arm、gripper 和 shared recurrent representation，但重新初始化：

```text
pitch output row
roll output row
对应 action log-std
必要时 base-command sub-head
```

如果当前 12D actor 还是单一输出层，可以只重新初始化最终线性层中对应 pitch/roll 的两行。

### C. 真正 scratch

```text
actor scratch
critic scratch
恢复完整 early-stage dense rewards
保留 staged-reset exploration
至少两个 training seeds
```

三组结果可以直接区分：

| 结果 | 解释 |
|---|---|
| B 改善，C 也改善 | 主要是输出头的历史习惯 |
| B 不改善，C 改善 | 习惯已进入 recurrent/shared representation |
| B、C 都重新饱和 | 当前 reward/geometry 的结构性最优 |
| C 连基本开门都学不会 | scratch curriculum/reward 不完整，不能据此判断 posture |

## 为什么 scratch 不能直接使用当前 v22 配置

当前 v22 配置明确建立在一个已经会开门的 warm-start 上。例如：

```text
push_door_handle = 0
push_door_force = 0
legacy posture L1 = 0
```

而许多 reward 已转向更后期的：

```text
hinge progress
clearance
release
posture feasibility
```

从零训练时必须重新审计并恢复：

```text
walk-to-door
pregrasp distance/orientation
gripper preparation
both-contact / squeeze / force window
unlatch
initial hinge progress
stage-transition exploration
```

DoorMan 的 teacher 训练也使用完整六阶段 dense shaping；论文的 staged-reset ablation 显示，没有 reset buffer 时 teacher 甚至很难稳定进入 grasp/open 阶段。`Xue 等 - 2025 - Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer.pdf`

因此我的判断是：

> **一次受控 scratch ablation 是必要的；立即完全放弃 warm-start、把全部后续研究押在 scratch 上，目前没有必要。**

优先做局部 posture-head reset，成本更低、因果解释更清晰。

---

# 3. teacher policy 能否直接看到门的 mass、damping 等 ground truth？

## 可以，而且当前 teacher actor 已经直接看到 mass

当前 actor observation 明确包含：

```text
privileged_door_info
```

并且该字段同时进入 actor 和 critic，还使用 observation history。

当前 8D 内容为：

```text
door width
door height
handle height
handle edge distance
door mass / 100
door opening handedness
opposite handedness indicator
door_open_io
```

其维度固定为 8。

所以一个重要新判断是：

> **v22 没有根据 mass 学出明显的姿态/策略条件化，并不是因为 teacher 看不到 mass；它已经直接看到 mass。**

这说明仅仅把 damping 加进 observation，并不能自动保证策略学会：

```text
fast rebound -> fling
high damping -> hold
```

还需要 reward、strategy events 和 training distribution 真的使这些行为产生不同回报。

## damping/stiffness/max-force 可以加给 teacher

推荐的物理向量可以是：

$$
e_{\mathrm{dyn}} =
[
m,\ I_{\mathrm{door}},\
c_{\mathrm{hinge}},\
k_{\mathrm{hinge}},\
\tau_{\max},\
h_{\mathrm{handle}}
]
$$

但要区分三种用法。

### 方案 1：只给 critic

```text
actor:
  仍从 history、motion response、contact 推断

critic:
  直接看到完整 dynamics ground truth
```

这是最稳妥的 asymmetric actor-critic：

- 改善 value estimation；
- 不增加 student 难以复制的 oracle dependency；
- 不改变部署 actor 的信息边界。

### 方案 2：直接给 teacher actor

这适合做一个 **oracle upper-bound**：

> 如果 teacher 明确知道 damping/stiffness/max-force，它是否就能学出策略切换？

若 oracle teacher 仍不切换，问题主要不是 observability，而是 reward/mode structure。

若 oracle teacher 能切换，而 history-only teacher 不行，则问题是系统辨识或记忆能力。

### 方案 3：推荐的主方案--ground-truth supervision，而不是永久 oracle input

训练一个 dynamics estimator：

$$
\hat e_{\mathrm{dyn},t}
=
f_\psi(
o_{t-H:t},
a_{t-H:t},
\theta_{t-H:t},
f_{t-H:t}
)
$$

用 simulation ground truth 监督：

$$
L_{\mathrm{sysID}}
=
\|\hat e_{\mathrm{dyn}}-e_{\mathrm{dyn}}^{GT}\|^2
$$

actor 实际使用：

```text
estimated dynamics latent
```

而不是始终使用 exact mass/damping。

这是对未来 student 最友好的做法，因为现实中的质量、阻尼和 stiffness 通常不能从单张 RGB 直接看到，只能从：

```text
施加动作
-> 门速度/加速度
-> 反作用力
```

的时间关系中推断。

DoorMan 本身就是 privileged teacher 到 RGB/proprio student 的结构；teacher 使用门和机器人 ground-truth transform、contact wrench 等 privilege，student 通过 DAgger 和时间上下文学习可部署行为。`Xue 等 - 2025 - Opening the Sim-to-Real Door for Humanoid Pixel-to-Action Policy Transfer.pdf`

## 哪些信息适合直接给 actor？

| 参数 | 建议 |
|---|---|
| handle height、door geometry | 可以直接给 teacher；视觉 student 也能看到 |
| door mass | 可作为 oracle/辅助监督；当前已直接给 actor |
| damping、stiffness、max force | critic 直接看；actor 优先使用 history estimator |
| difficulty class | 不建议，过度压缩且容易错配 |
| measured force-progress relation | 最值得给 recurrent actor，部署时可通过历史估计 |

还要注意：从 8D 扩展 observation 会改变网络第一层维度，旧 checkpoint 无法直接加载。可以使用：

```text
zero-initialized dynamics adapter
或 FiLM/residual adapter
```

使新增 dynamics 输入初始输出为零，从而保留 warm-start 行为。

---

# 4. 是否应该使用你描述的 RoboDuet 式目标高度 posture reward？

## 结论：值得采用，而且比 v22 的统一 posture-need classifier 更合适

但需要先澄清一点：

你描述的“根据目标高度分区，直接规定期望 pitch”的设计思想是合理的；不过在上传的 RoboDuet 论文正文中，实际机制是：

- arm policy 额外输出 pitch/roll guidance；
- locomotion policy 跟踪这两个 guidance；
- 使用 `r_arm_guide` 约束实际 base orientation 与 arm guidance；
- 两个 policy 在 Stage 2 同步训练。

论文没有明确给出你写出的那套 piecewise height-to-pitch 公式。你提出的是对 RoboDuet cooperative guidance 思想的一种合理、更加显式的 DoorDog 适配，而不是直接复制论文公式。`Pan 等 - 2025 - RoboDuet Learning a Cooperative Policy for Whole-body Legged Loco-Manipulation.pdf`

## 为什么它比当前 v22 机制更合适

v22 的 `posture_need` 是：

```text
height need
OR workspace need
OR force need
OR tracking need
```

其中任何一个恒真，整个 need 就会恒真。实际结果正是：

```text
workspace/joint-margin 条件几乎一直开启
-> posture_need 近似恒真
-> ordinary 与 difficult 无法区分
```

而目标高度是：

- 独立可测；
- 几何意义明确；
- 不依赖一个容易饱和的 force estimator；
- 对未来 RGB student 可观察；
- 可以直接给出高、低、中 handle 的明确监督。

## 不能在整个 episode 中持续使用

若简单设置：

$$
r=-w(p-p^\*(\Delta h))^2
$$

并在所有 stage 生效，策略很可能继续：

```text
抓住以后仍保持大 pitch
```

这正是现在的问题。

应该做成阶段条件化：

| Stage | Height-conditioned prior |
|---|---|
| Walk | 关闭 |
| Pregrasp | 强 |
| Grasp | 强 |
| 刚建立稳定 bilateral grasp | 逐渐衰减 |
| Open/Swing | 只保留 force/workspace residual |
| Release/Traverse | 回归中性，除非仍需 hold-open |

v22 的 P0 结果恰好支持这个分解：

```text
pitch 对建立抓握很重要
但抓住以后 neutral posture 经常已接近最佳
```

## 推荐的数学形式

先定义几何先验：

$$
\Delta z
=
z_{\mathrm{handle}}
-
z_{\mathrm{arm\ mount,neutral}}
$$

$$
p_{\mathrm{geom}}(\Delta z)=
\begin{cases}
p_{\mathrm{low}}, & \Delta z < -\tau_{\mathrm{low}}\\
0, & -\tau_{\mathrm{low}}\le \Delta z\le \tau_{\mathrm{high}}\\
p_{\mathrm{high}}, & \Delta z > \tau_{\mathrm{high}}
\end{cases}
$$

再加入困难门下的力残差：

$$
p_{\mathrm{ref}}
=
g_{\mathrm{pregrasp}}(s)\,p_{\mathrm{geom}}
+
g_{\mathrm{force}}(s)\,\delta p_{\mathrm{force}}
$$

其中：

```text
g_pregrasp:
  在 pregrasp/grasp 为1
  stable grasp 后逐步降为0

g_force:
  仅在持续低 hinge progress
  + 高 effort/tracking error
  + 已保持抓握时开启
```

奖励使用**实际机身姿态**：

$$
r_{\mathrm{posture}}
=
-w_p(p_{\mathrm{actual}}-p_{\mathrm{ref}})^2
-w_r(r_{\mathrm{actual}}-r_{\mathrm{ref}})^2
$$

而不是只比较 action command。

当前系统已经验证了 command `[pitch, roll]` 与 achieved `[roll, pitch]` 的索引顺序不同，而且 command 和 achieved 的符号关系需要实测处理，所以不能直接复制 RoboDuet 的符号。

## Roll 也需要几何先验

Roll 不应由 door mass 决定，主要应由：

```text
handle lateral offset
door hinge side
arm mounting side
lateral reach margin
lateral contact force
```

决定。

可定义：

$$
\Delta y
=
y_{\mathrm{handle}}
-
y_{\mathrm{arm\ base}}
$$

并使用带 deadband 的 $r_{\mathrm{geom}}(\Delta y)$。

## 仅靠 reward 可能仍不够

项目历史已经多次表明：

> load-bearing behavior 很难仅靠提高价格消失。

因此我更推荐将 posture action 改成**参考值上的有界 residual**：

$$
p_{\mathrm{cmd}}
=
p_{\mathrm{ref}}
+
\Delta p_{\mathrm{policy}}
$$

例如：

```text
普通 / 几何辅助：
  residual 范围较小

persistent force need:
  residual 范围扩大

极限情况：
  才允许接近现有 0.4 rad 物理上限
```

概念上可以是：

```text
normal residual:       ±0.08-0.12 rad
force-assist residual: ±0.20-0.25 rad
absolute emergency max: 0.40 rad
```

这些数值应通过姿态 atlas 和实际运行重新定标，不能直接冻结。

这种参数化比纯 reward 更能避免：

```text
policy 发现付出姿态 penalty 仍然值得
于是继续长期打满 0.4
```

## 是否涉及复杂 arm-base 动力学？

**粗粒度 height prior 不需要完整动力学模型。**

它只负责：

```text
高低目标 -> 基础几何协同方向
```

真正复杂的部分仍由 RL residual 学习：

```text
具体角度
动态反作用力
平衡
接触
门的 damping/stiffness
```

因此可以将整个机制拆成：

```text
geometry prior:
  决定“应该往哪个方向”

policy residual:
  决定“具体需要多少”

force gate:
  决定“是否需要扩大可用姿态范围”

body-assist gate:
  决定“arm + posture 是否真的已经不够”
```

---

# 综合判断

你提出的四点可以组合成一个非常清晰的下一步科学假设：

```text
当前 max-pitch 行为 =
  warm-start inheritance
  + pregrasp geometry 的真实需求
  + 姿态使用范围没有 stage separation
  + arm capability 过强 / force boundary 未建立
```

最有价值的验证顺序是：

1. **把 door difficulty 轴分清楚**
   - mass → inertia/fling；
   - damping → speed/hold；
   - stiffness/max force → quasi-static force boundary。

2. **做三种初始化对照**
   - full warm-start；
   - pitch/roll head reset；
   - full scratch with restored dense curriculum。

3. **加入 dynamics privilege 对照**
   - critic-only ground truth；
   - oracle actor；
   - history-estimated latent。

4. **采用阶段条件化 height/lateral posture prior**
   - pregrasp/grasp 强；
   - stable grasp 后衰减；
   - force residual 单独开启；
   - 必要时使用有界 residual action parameterization。

最终我对“是否重新训练”的答案是：

> **需要重新训练实验来识别 warm-start 继承，但真正需要重做的不是简单把网络清零，而是 posture 的阶段语义和 action parameterization。否则 scratch policy 很可能再次发现同一个 `0.4 pitch` 局部最优。**

## Prompt:
2026/8/8 23:43:18

我阅读了你的回答，有下列观点，需要你独立思考，斟酌v23的训练设计，这次任务有8GPU，可以任意设计多组实验并行，保证每组实验env=4096就行，当前v23不方便纳入，但是确实期望落地的修改，可以让worker session写入 longterm TODO就行（在v23方案里写好）：
1 下一步可以设计增加 “hinge stiffness、max-force/resistive torque、摩擦和机械臂真实力矩余量”，创造可靠的 `arm + posture infeasible` 区域。
2 可以v23设计一个ablation实验做scratch 对照，看能不能减小 “0.4 pitch” 现象
3 承接上面两个，能不能重新训练一个强制将 roll/pitch =0的scratch 对照，看看是不是“arm alone 足够” ，从而也能间接证明1的理论-是当前door条件不够恶劣
4 关于第四点“是否应该使用你描述的 RoboDuet 式目标高度 posture reward？” 你的论述聚焦在针对handle 高度考虑arm-base联动的reward设计，我认为这是错的。本质上是想通过这个reward去学习在什么情况下roll/pitch合适，也是如同“普通或有回弹的门：
  保持握持到安全开度
  施加受控的正向释放速度
  利用门的惯性形成通行净空

高阻尼、重门或 fling 无效：
  gripper 继续 hold-open
  或在满足 force-failure gate 后由 trunk/front-thigh 保持门开

禁止的不是 fling，而是：
  过早松手
  无界冲量
  高速甩门
  门回弹碰撞 robot”
一样有选择地去选择进行roll/pitch，同时如何进行roll/pitch，肯定有force/height/torque等综合参与的判断。我认为需要一个动力学判断。
5 关于第四点，还可以参考之前的讨论，可不可以再引入一个critic负责arm-base 联动行为的评价？ 做一个intervention-supervised coupling critic + counterfactual branch advantage？

保持独立思考/研究，首先回答上述建议，然后交付给我一个v23方案初版

## Response:
2026/8/8 23:43:23

> **检索并分析v22规划配置及门控源码**
>
> 
>
> **正在搜索网页**
>
>
> **正在搜索网页**
>
> 
>
> **检索并分析门控环境代码**
>
> 
>
> **检查 DoorDog GitHub 分支**
>
>
> **检查了 DoorDog GitHub 分支**
>
> 
>
> **梳理方案边界**
>
> 我正在理解需求：交付一份 V23 初版方案即可，不直接修改仓库。方案需要研究 critic 耦合、反事实实际分支优势，以及动态判断机制，并整理成后续 TODO。
>
> **梳理方案边界**
>
> 
>
> **检查v22诊断、姿态分类及PPO配置代码**
>
> 
>
> **正在搜索网页**
>
> [Counterfactual Multi-Agent Policy Gradients](https://arxiv.org/abs/1705.08926)
> [Wasserstein Policy Optimization](https://proceedings.mlr.press/v267/pfau25a.html)
>
> **设计约束与取舍**
>
> 我正在把五个视角分别转化为 V23 设计判断，重点区分首版必须验证的内容与暂缓实现、但应写入长期 TODO 的修改。核心还包括物理能力边界、反事实优势与动态机制。
>
> **确定设计约束与取舍**
>
> 
>
> **已搜索 2 个网站**
>
> 
>
> **形成 V23 初版**
>
> 我正在综合五项建议：V23 优先验证动态姿态决策与可行性边界；消融实验检验 0.4 pitch；耦合 critic 与反事实优势先做最小原型，复杂物理改造列入长期 TODO。
>
> **核对证据链**
>
> 我正在据现有实现确认关键事实：姿态命令为 `[x,y,yaw,pitch,roll]`，V22 已有基于高度、工作空间、力与跟踪的需求判据，但工作空间条件可能过度触发；因此 V23 需优先修正动态判断并验证独立消融。
>
> **明确实验优先级**
>
> 我将把 V23 设计成“能力边界×姿态自由度×初始化方式”的因果矩阵：同时检验动态姿态决策、零姿态控制、从零训练，并将静态摩擦与真实力矩标定列入长期 TODO。
>
> **组织耦合建模**
>
> 我会用历史潜变量而非纯特权状态，替换易失效的硬门控；先训练诊断型耦合 critic，再逐步启用反事实分支优势，并通过两阶段八卡实验降低混杂因素。
>
> **规划实验矩阵**
>
> 我正在将 V23 组织成两阶段：先用“初始化×姿态×阻力”因果矩阵定位能力边界，再比较动态潜变量、因子化 actor 与耦合 critic，所有结论都配套干预标签和统一指标。
>
> **形成V23初版并核对证据链，明确实验优先级与耦合建模**
>
> 
>
> **完成v23实验设计并检查配置提交与TODO更新**
>
> 
>
> 思考了 20m 57s

# 核心修正

你对第 4 点的批评成立。上一轮把问题收缩成“handle 高度决定期望 pitch”的姿态 reward，作为 v23 主设计是不对的。那只是一个几何启发式，无法解决真正的问题：

> 在给定门动力学、机械臂力矩余量、抓握状态、底盘稳定裕度和后续任务需求时，policy 应当判断是否需要 roll/pitch、往哪个方向、使用多大幅度、维持多久，以及何时退出。

RoboDuet 的实际机制也不是固定的“高度 → pitch”映射。其 arm policy 输出 6 维机械臂动作和 2 维 pitch/roll guidance，locomotion policy 跟踪这一 learned guidance；它通过端到端任务回报学习全身协同，而不是由目标高度直接指定机身姿态。`Pan 等 - 2025 - RoboDuet Learning a Cooperative Policy for Whole-body Legged Loco-Manipulation.pdf`

因此，v23 不应加入目标高度条件化 posture reward。目标高度可以作为动力学与几何判断中的一个输入，但不能成为决策规则本身。

---

# 一、对五点建议的逐项判断

## 1. 增加 stiffness、resistive torque、摩擦和真实 arm torque margin

### 判断：同意，且应成为 v23 的物理前置主线，但不能简单“把数值调大”

门的近似铰链需求可以写成：

$$
\tau_{\mathrm{req}}
=
I\ddot{\theta}
+
c\dot{\theta}
+
k(\theta-\theta_0)
+
\tau_c\,\mathrm{sgn}(\dot{\theta})
+
\tau_{\mathrm{breakaway}}
$$

其中：

- `mass/inertia` 主要影响加速和 fling；
- `damping` 主要影响运动速度和释放后衰减；
- `stiffness`、持续 resistive torque、静摩擦和 breakaway torque 决定低速、准静态情况下是否仍需要持续施力；
- arm effort limit、姿态和 Jacobian 共同决定当前姿态下能在门切向输出多少有效力。

更合理的可行性指标不是某个 door 参数是否“大”，而是：

$$
M_\tau
=
\tau_{\mathrm{available}}^{\mathrm{arm+posture}}
-
\tau_{\mathrm{required}}
$$

真正的 `arm + posture infeasible` 应通过运行证据确认，而不是按参数名定义。

### v23 应建立三个操作性区域

| 区域 | 操作性定义 |
|---|---|
| **E0：arm/nav sufficient** | 禁止主动 roll/pitch 后仍能稳定开门，arm torque 有明显余量 |
| **E1：posture beneficial/necessary** | 自由姿态成功率或进展显著高于 RP0；姿态改变提高切向输出、工作空间或稳定性 |
| **E2：arm + posture infeasible** | 自由姿态和 RP0 均在有效抓握、高 effort、低 hinge progress 条件下失败，但提高 arm effort、施加 oracle tangential assist 或未来 body-assist 可以恢复进展 |

E2 必须包含“反事实救援”。否则无法区分：

- 门确实太难；
- policy 不会开；
- 抓握失败；
- reward/curriculum 失败；
- 仿真数值不稳定。

DoorMan 的附录第 16 页确实同时随机化门重量、hinge damping、stiffness 和 max force；其训练范围为门重 `80-120 kg`、hinge max force `20-30 Nm`、damping `5-10`、stiffness `10-20`。但这些范围只能作为量级参考，不能直接复制，因为 IsaacLab drive 的单位解释、门几何和机器人能力不同。

PiPER 手册公开了 `1.5 kg` 负载、`626.75 mm` 工作半径和最大功耗不超过 `120 W`，但没有给出各关节连续/峰值扭矩或扭矩-转速曲线，因此当前 URDF 中统一的 `100 Nm` 不能视为真实规格。`piper.pdf` SDK 和 URDF 资源可用于核对实现，但仍不能代替真实电机能力数据。`piper-sdk-&-documentation.txt`

此前 v21 设计中提出的 torque telemetry、`100→60→40→30→25→20 Nm` 零样本 ladder，以及 Kp/action-scale 与 torque clipping 一致性审计，应直接继承为 v23 的 P0。`粘贴的文本 (1).txt`

### 一个重要限制

在当前还没有可靠 body-assist recovery 的情况下，**已确认的 E2 不应大量放进训练分布**。对 PPO 来说，这些 episode 没有可行解，比例过高会推动 policy：

- 不抓门；
- 避免进入困难阶段；
- 学会提前终止；
- 用奖励漏洞代替任务进展。

v23 应当：

- 用 E0/E1/near-boundary 训练；
- 用 E2 做正式 held-out evaluation；
- 等 body-assist 路线实现后，再将 E2 纳入可解训练任务。

---

## 2. 使用 scratch 对照检查 `0.4 pitch` 是否来自 warm-start 继承

### 判断：必要，而且应该是 v23 的正式实验轴

但 scratch 与 warm-start 必须满足完全相同的：

- observation；
- action parameterization；
- reward registry；
- staged-reset distribution；
- dynamics curriculum；
- rollout budget；
- evaluation manifests。

不能让 warm-start 继续使用“已移除 basic reward”的配置，而 scratch 单独恢复 dense reward。否则结果无法区分：

- 初始化差异；
- reward 差异；
- exploration 差异。

因此 v23 应建立一套 **scratch-capable common reward**，同时用于 warm 和 scratch。

DoorMan teacher 的六阶段训练明确保留了 walk、pre-grasp、grasp、handle opening、hinge opening 和 traversal 的 stage-specific dense reward。其 staged-reset 实验还显示，没有 reset buffer 时 teacher 很难稳定进入 grasp 阶段；100-state buffer 明显加快了后续阶段探索。

v23 不必复制 DoorMan 的权重，但应恢复当前项目中与下列语义对应的 early-stage reward：

- 接近门；
- pregrasp 距离和朝向；
- gripper preparation；
- bilateral contact；
- squeeze/contact stability；
- unlatch；
- initial hinge progress。

这些 reward 只在相应 stage 生效，不应在后续阶段形成静态收入。

### scratch 实验必须回答两个不同问题

1. **相同状态下的 policy mapping 是否不同？**  
   使用一组固定 stage-2/3/4 state bank，在相同 observation/history 上查询 warm 与 scratch checkpoint 的 deterministic action。

2. **实际 visitation 下的长期行为是否不同？**  
   比较完整 rollout 中 pitch saturation、抓握、开门和穿门表现。

只看完整 rollout 不够，因为 scratch 与 warm 可能访问完全不同的状态分布。需要存储 recurrent history 或可重放的 prefix，不能只保存瞬时物理状态。

---

## 3. scratch + 强制 `roll/pitch=0` 是否能证明 arm alone 足够

### 判断：这是非常有价值的对照，但仅强制 roll/pitch 为零还不能严格称为 `arm-only`

当前 5D base command 除 roll/pitch 外，仍然包含平面移动和 yaw。即使：

```text
roll_cmd = 0
pitch_cmd = 0
```

policy 仍可能通过：

- 前后移动底盘；
- 横向移动；
- yaw 调整；
- 低层 A2 对外力的被动响应；

来辅助门运动。

因此该实验准确的名称应是：

> **no-active-posture：arm + planar base motion，无主动 roll/pitch**

而不是纯 arm-only。

### v23 应区分三种干预

| 干预 | 含义 | 用途 |
|---|---|---|
| **FULL** | 5D base command 全部自由 | 完整 whole-body policy |
| **RP0** | roll/pitch command 固定为语义中性值，平面 base 仍自由 | 判断主动姿态是否必要 |
| **BASE0@GRASP** | 在 stable grasp 后，将 5D base command 全部固定为中性，仅 arm/gripper 可继续控制 | 更接近 command-level arm-only |

`BASE0@GRASP` 建议先作为 evaluation intervention，不必额外占用一组训练 GPU。

还应区分：

- **acute ablation**：对已经训练好的 FULL policy 临时施加 RP0/BASE0；
- **chronic ablation**：从头训练一个长期无法使用 roll/pitch 的 policy。

前者测“当前 policy 是否依赖姿态”，后者测“policy 是否能通过其他策略补偿”。用户提出的 scratch-RP0 属于后者，科学价值更高。

### 实现要求

RP0 不能采用：

```text
先采样动作 → 计算 log-prob → 再把 roll/pitch clamp 到0
```

这样 PPO 优化的是一个未真正执行的动作。

应当：

- 在 policy distribution 中将对应维度设为 deterministic neutral；
- 或从 actor head 中屏蔽这两个维度；
- masked dimensions 不参与 log-prob、entropy、KL 和 PPO ratio；
- 使用经 action warp/de-normalization 后的语义中性值；
- 同时记录 achieved roll/pitch，因为 command 为零并不代表实际机身姿态严格为零。

---

## 4. roll/pitch 应是综合动力学判断，而不是目标高度 reward

### 判断：同意。v23 应明确否决 height-conditioned posture reward

理想的姿态决策可以写成：

$$
z_t^{\mathrm{dyn}}
=
f_\psi
\left(
o_{t-H:t},
a_{t-H:t},
f_{t-H:t},
\theta_{t-H:t}
\right)
$$

其中 history 至少应包含或隐式反映：

- handle 相对几何；
- arm joint margin；
- arm torque utilization；
- hand/contact wrench；
- hinge progress、velocity、acceleration；
- damping/rebound 特征；
- base stability 和 achieved posture；
- 当前 stage；
- 后续 clearance/traversal 状态。

然后姿态控制不是一个固定 reference，而是：

$$
g_t=\sigma\bigl(g(z_t^{\mathrm{dyn}})\bigr)
$$

$$
a_t^{\mathrm{posture}}
=
g_t\,
\Delta\phi_t
$$

其中：

- $g_t$ 判断是否需要姿态；
- $\Delta\phi_t$ 决定方向和幅度；
- temporal policy 决定持续时间和退出条件。

这与门策略选择完全同构：

```text
低阻尼/有惯性收益：
    允许受控 fling，然后释放

高阻尼或回弹明显：
    继续 hold-open

arm + posture 低 margin：
    进入 body-assist 请求

普通、低负载状态：
    不使用大幅 roll/pitch
```

姿态不是一种固定行为，而是一种 mode-conditioned resource。

### v23 中怎样落地

v23 核心训练中：

- 不增加目标高度 pitch reference；
- 不增加“门重就倾斜”之类 oracle rule；
- 不为 roll/pitch 直接设置人为期望方向；
- 保留任务进展、稳定性、动作平滑和安全约束；
- 通过 FULL 与 RP0 的因果对照判断姿态是否真正有价值；
- 用 torque、hinge response 和 matched intervention 评估 posture utility。

精确 dynamics ground truth 可以作为未来 oracle teacher upper bound，但不应在 v23 主 factorial 中突然加入 actor observation，否则会同时改变网络输入、checkpoint compatibility 和可部署信息边界。

---

## 5. intervention-supervised coupling critic + counterfactual branch advantage

### 判断：方向成立，而且比普通 centralized critic 强；但不建议直接塞进 v23 的核心 8-cell训练矩阵

当前 DoorDog 架构不是两个可训练 PPO。它是一个高层 recurrent actor，联合输出 5D base command 与 7D arm/gripper action；冻结的 A2 locomotion policy 再将 base command 转换为 12D leg action。`Counterfactual Coupling and Handoff Critics for Long-Horizon Legged_Loco-Manipulation.md`

因此，直接“再加一个 critic”但仍保留 joint log-prob 和单一 PPO ratio，不能真正完成 branch-specific credit assignment。

### 更适合 DoorDog 的未来分支不是两分，而是三分

为了专门研究 roll/pitch，建议拆成：

$$
a_t=
\left[
a_t^{\mathrm{nav}},
a_t^{\mathrm{posture}},
a_t^{\mathrm{arm}}
\right]
$$

其中：

- $a^{nav}$：平面速度与 yaw；
- $a^{posture}$：roll/pitch；
- $a^{arm}$：6D Piper + gripper。

只分成 `base` 和 `arm` 会把“底盘前后移动的贡献”和“roll/pitch 的贡献”混在一起，仍无法回答用户当前最关心的问题。

### coupling critic 应有可识别监督

不是简单训练：

$$
V_{\mathrm{coupling}}(s)
$$

而应训练 action-conditioned critic：

$$
Q_C
\left(
z_t,
a_t^{nav},
a_t^{posture},
a_t^{arm}
\right)
$$

针对 posture-arm interaction，可在同一 simulator state、同一随机数条件下执行：

$$
R_{11}=R(a^{posture},a^{arm})
$$

$$
R_{01}=R(0,a^{arm})
$$

$$
R_{10}=R(a^{posture},\bar a^{arm})
$$

$$
R_{00}=R(0,\bar a^{arm})
$$

定义非加性交互：

$$
\Delta_C
=
R_{11}-R_{01}-R_{10}+R_{00}
$$

这能区分：

- 姿态本身的收益；
- arm 本身的收益；
- 姿态与 arm 联动后额外产生的协同收益。

再据此构造 counterfactual advantage：

$$
A_C^{posture}
=
Q_C(z,a^{posture},a^{arm})
-
\mathbb{E}_{\tilde a^{posture}}
Q_C(z,\tilde a^{posture},a^{arm})
$$

$$
A_C^{arm}
=
Q_C(z,a^{posture},a^{arm})
-
\mathbb{E}_{\tilde a^{arm}}
Q_C(z,a^{posture},\tilde a^{arm})
$$

但这要求：

1. 三个 actor head；
2. 三组独立 log-prob；
3. 三组 PPO ratio、KL 和 entropy；
4. 可精确 clone simulator state 的 intervention runner；
5. 对 neutral arm/posture action 的安全定义；
6. control-step 而非 physics-frame horizon。

因此，我建议 v23 只完成：

- intervention 数据接口和指标定义；
- 可选的 shadow/off-policy coupling critic；
- 不让 coupling critic 的输出更新 actor。

完整 counterfactual PPO 应进入 longterm TODO，作为 v24 或独立算法分支。

---

# 二、v23 方案初版

## 名称

**v23 - Force-Feasibility × Initialization × Posture-Availability Factorial**

核心不是再添加一个启发式 reward，而是建立三个因果问题的证据：

1. `0.4 pitch` 有多少来自 warm-start 继承？
2. 当前门是否在无主动姿态条件下仍然可解？
3. 能否构造 E0/E1/E2 三个具有明确因果含义的 force-feasibility 区域？

---

## 1. v23 的预注册假设

### H1：初始化继承假设

在相同门分布、相同 reward 和自由 posture 条件下：

$$
\text{Warm FULL}
\quad \text{vs.} \quad
\text{Scratch FULL}
$$

若 scratch 显著降低无效的 max-pitch dwell，而任务表现不下降，则 warm-start inheritance 是重要原因。

若 scratch 也重新学到长期 `0.4 pitch`，则问题主要来自：

- reward geometry；
- action parameterization；
- dynamics distribution；
- 或姿态确实长期有用。

### H2：当前门 arm/nav sufficient 假设

在当前 D0 门分布中：

$$
\text{Scratch RP0}
$$

若与 Scratch FULL 接近，并且 `BASE0@GRASP` 也保持较高成功率，则当前门主要处于 arm/nav sufficient 区域。

### H3：posture necessity 假设

在 D1 near-boundary 分布中：

$$
\text{FULL} > \text{RP0}
$$

且该差异伴随：

- 更高 hinge progress；
- 更低 arm torque saturation；
- 更好的 arm joint margin；
- 或更稳定的 grasp；

则姿态是因果性有用，而不是装饰动作。

### H4：force-infeasibility 假设

存在 held-out E2 buckets，使得：

- FULL 与 RP0 都失败；
- 抓握有效；
- arm effort 长时间接近上限；
- hinge progress 接近零；
- 高 effort/oracle assist 可以恢复。

### H5：selective posture 假设

理想 policy 应表现为：

$$
\mathbb E[\|a_\phi\|\mid E1]
>
\mathbb E[\|a_\phi\|\mid E0]
$$

而不是所有区域都长期打满。

---

## 2. v23 明确不做的内容

为保证因果可解释性，v23 核心不同时引入：

- target-height posture reward；
- 完整 body-assist curriculum；
- coupling critic 驱动的 actor update；
- 新的 dynamics-ground-truth actor observation；
- arm velocity limit 修改；
- locomotion residual/unfreeze；
- student 蒸馏修改。

这些全部写入 longterm TODO。

---

# 三、P0：训练前的阻塞项

## P0.1 Arm torque telemetry

每个 control step 至少记录：

```text
per_joint_abs_tau
per_joint_tau_over_limit
arm_max_tau_ratio
arm_mean_tau_ratio
fraction_tau_ratio_ge_0.90
fraction_tau_ratio_ge_0.98
first_saturating_joint
arm_mechanical_power
arm_torque_clipping_count
```

并按以下维度聚合：

- door scenario；
- stage；
- door dynamics bucket；
- posture mode；
- success/failure；
- hinge progress window。

没有这些数据，无法声明建立了 force boundary。

---

## P0.2 Effort ladder

冻结 v22 winner，使用统一 scenario manifest 做：

```text
100
60
40
30
25
20 Nm
```

或以每关节不同 profile 表示的等效 ladder。

选取 v23 的 `τ_calibrated` 时不应称为“真实 torque”，除非拿到厂家连续/峰值规格。更准确的名称是：

> `τ_boundary-calibrated`

选择标准：

- 开始出现有意义的 torque saturation；
- E0 不整体崩溃；
- 重门/高阻场景先退化；
- 退化来自 effort boundary，而非 PD 数值振荡。

同时审计：

$$
K_p \times \Delta q_{\max}
$$

是否远高于 effort limit。若大部分时间都被 clip，控制器会退化成近似 bang-bang。

---

## P0.3 Door resistance atlas

先做准静态轴：

```text
hinge stiffness multiplier
resistive/max-force multiplier
breakaway/friction proxy
arm effort profile
```

后做动态轴：

```text
hinge damping
door inertia/mass
release/rebound behavior
```

不能一开始把五六个参数一起随机化后，只根据 aggregate success 判断。

建议建立固定 atlas：

```text
A0: current easy
A1: high stiffness
A2: high sustained resistive torque
A3: high breakaway/friction proxy
A4: high damping
A5: high inertia
A6: stiffness + calibrated effort
A7: resistive torque + calibrated effort
A8: compound near-boundary
```

每个 atlas cell 用 FULL、RP0 和 effort-rescue 三种 evaluation 跑一遍，根据行为结果归入 E0/E1/E2。

---

## P0.4 Feasibility certificate

一个 scenario 只有满足以下条件才能标为 E2：

1. 已建立 stable grasp；
2. FULL 和 RP0 均持续低 hinge progress；
3. arm torque utilization 持续接近上限；
4. 失败不是 fall、lost grasp、door-frame collision 或 timeout-at-wrong-stage；
5. 相同 state 下提高 effort 或增加 oracle tangential assist 可以恢复明显正向进展。

初版窗口可设为：

```text
stable grasp:             ≥ 20 control steps
evaluation window:        25-40 control steps
hinge progress threshold: < 0.02-0.04 rad/window
high effort:              tau_ratio ≥ 0.90 for ≥30% window
rescue progress:           ≥0.10-0.15 rad/window
```

最终阈值在 P0 atlas 完成后锁定，正式训练开始后不再修改。

---

## P0.5 Scratch-capable common reward

所有八组都使用同一套 reward。至少恢复：

- walk-to-door；
- pregrasp；
- grasp/contact；
- unlatch；
- initial hinge progress；
- stage transition；
- final traversal。

同时：

- 不新增姿态期望 reward；
- 不给 max pitch 正奖励；
- 不把 door mass/damping 直接转成姿态标签；
- 每个 dense reward 严格限制在对应 stage；
- 审计 stationary rent。

---

## P0.6 RP0 action contract

确认 5D command 中 roll/pitch 的真实索引和 warp 顺序，禁止依赖“最后两维应该就是姿态”这种假设。

RP0 配置必须通过单元测试证明：

```text
network sampled/executed action一致
masked dims log_prob = 0 contribution
masked dims entropy = 0 contribution
executed semantic command = neutral
achieved posture telemetry remains active
```

---

## P0.7 Common-random-number evaluation bank

冻结一套 scenario/state bank：

- E0/E1/E2；
- stage 2/3/4；
- 不同 hinge velocity 和 grasp quality；
- 包含 recurrent history 或可重放 prefix；
- 固定 physics seed。

所有 checkpoint 在同一 state bank 上查询：

- FULL action；
- RP0 action；
- BASE0 action；
- posture-intervention return。

这能避免把 visitation 差异错误解释为 policy mapping 差异。

---

# 四、8 GPU 主矩阵

每组：

```text
env = 4096
1 GPU / group
same network size except deterministic masked posture dims
same reward
same stage-reset schedule
same training budget
same evaluation manifests
```

| Group | 初始化 | Door train regime | Posture | 核心用途 |
|---|---|---|---|---|
| **G1** | v22 warm | D0 current | FULL | warm/current 基准 |
| **G2** | v22 warm | D0 current | RP0 | warm policy 在无姿态下的适应能力 |
| **G3** | scratch | D0 current | FULL | `0.4 pitch` 继承检验 |
| **G4** | scratch | D0 current | RP0 | 当前门是否无需主动姿态即可学习 |
| **G5** | v22 warm | D1 near-boundary | FULL | warm policy 在强阻门下是否会正确使用姿态 |
| **G6** | v22 warm | D1 near-boundary | RP0 | 强阻门下 warm posture 的因果贡献 |
| **G7** | scratch | D1 near-boundary | FULL | 从零学习动力学条件化姿态 |
| **G8** | scratch | D1 near-boundary | RP0 | 强阻门的 no-posture capability floor |

此外保留一个不训练的：

```text
A0 = frozen v22 winner
```

在新的统一 evaluation suite 上重评。因为 G1 已经使用 v23 common reward，它不是原 v22 的完全不变 continuation，A0 才是历史回归锚点。

---

# 五、D1 训练分布

D1 不能以 E2 为主。建议使用锁定的时间型 curriculum：

| 训练区间 | E0/current-like | E1 posture-beneficial | near-E2 但仍可解 | confirmed E2 |
|---|---:|---:|---:|---:|
| 0-20% | 100% | 0% | 0% | 0% |
| 20-50% | 60% | 40% | 0% | 0% |
| 50-100% | 30% | 60% | 10% | 0% |

confirmed E2 仅进入 formal evaluation。

这样可以同时避免：

- scratch 在一开始遇到大量不可解任务；
- warm policy 只靠历史容易门行为存活；
- 无解 episode 污染 PPO gradient。

---

# 六、训练协议

## 初始化

### Warm groups

```text
load: v22 selected actor policy_only
reset: critic
reset: optimizer
reset: rollout/recurrent hidden state
```

### Scratch groups

```text
actor random init
critic random init
optimizer fresh
same initial log_std policy as project scratch convention
```

Warm actor 的 mean、recurrent representation 和 log-std 都属于继承效应的一部分，不应只加载部分权重后仍称为完整 warm-start。

---

## 训练预算

建议：

```text
Wave A: 8-cell matrix, seed 0
Wave B: exact same 8-cell matrix, seed 1
```

每个 cell 至少获得两个正式 seed。

训练预算统一使用 v22 formal budget；若当前惯例为 2500 iterations，则八组全部 2500，不允许只给 scratch 额外预算。

若所有 scratch groups 在预注册时间点都无法到达 grasp/open stage，则应判定：

> scratch curriculum 不足，当前结果不能用于评价 posture inheritance。

可以启动一个统一的 scratch extension wave，但必须对所有 scratch cells同时延长，不能只延长表现较好的组。

正式方法结论最好再对 G1/G3/G4/G5/G7/G8 补第三 seed。

---

# 七、评价指标

## 1. 任务指标

```text
full success
goal/crossing
stage reach rate
time-to-stage
stable grasp rate
unlatch rate
hinge progress
held_hinge_max
hinge_at_release
hinge_at_crossing
release velocity
rebound collision
failure taxonomy
```

---

## 2. Posture pathology 指标

不能把“出现 0.4”本身定义为坏行为。应判断它是否有边际任务价值。

记录：

```text
commanded roll/pitch
achieved roll/pitch
fraction |cmd| ≥ 0.95 * limit
longest saturation dwell
stage-conditioned saturation
posture action integral
posture action rate
posture sign switches
```

在 matched intervention 中定义：

$$
\Delta J_\phi(s)
=
J_H(s,a^{nav},a^\phi,a^{arm})
-
J_H(s,a^{nav},0,a^{arm})
$$

其中 $H$ 为固定短期 control-step horizon。

定义“无效打满”：

$$
\mathrm{FP}_{\phi}
=
\Pr
\left(
|a^\phi|\ge0.95a^\phi_{\max}
\land
\Delta J_\phi\le\epsilon
\right)
$$

这比简单统计 pitch saturation 更能回答 v0-v22 的问题。

还应报告：

$$
S_{\phi}
=
\mathbb E[\|a^\phi\|\mid E1]
-
\mathbb E[\|a^\phi\|\mid E0]
$$

正且稳定的 $S_\phi$ 才说明 policy 开始进行选择性姿态控制。

---

## 3. 力可行性指标

```text
per-joint torque utilization
time above 0.9 / 0.98 limit
first saturating joint
hinge progress under high effort
arm tracking error under clipping
joint-margin depletion
force direction vs opening tangent
door required torque estimate
```

尤其要报告：

$$
\Pr(\text{low progress}\mid \text{valid grasp, high effort})
$$

而不是把所有 failed episode 混在一起。

---

## 4. `arm-only` 分层评价

对 G3/G4/G7/G8 checkpoint 统一执行：

1. 正常 FULL；
2. acute RP0；
3. BASE0@GRASP；
4. higher-effort rescue；
5. oracle door-assist rescue。

这会产生更完整的能力图：

```text
FULL succeeds, RP0 fails:
    posture causally necessary

RP0 succeeds, BASE0 fails:
    planar base motion causally necessary

BASE0 succeeds:
    command-level arm-only is sufficient

FULL/RP0/BASE0 all fail, effort rescue succeeds:
    arm capability boundary

effort rescue also fails, external assist succeeds:
    door/task geometry or contact-transfer boundary
```

---

## 5. 动力学策略指标

姿态与 fling/hold-open 应在同一个 dynamics-conditioned框架下分析：

```text
fling attempt rate
fling success rate
release angular velocity
post-release hinge deceleration
rebound amount
hold-open duration
premature release
regrasp need
posture use before/after stable grasp
```

需要检查：

- 低阻尼门是否更常选择受控释放；
- 高阻尼门是否更常持续握持；
- E1 是否增加姿态使用；
- E0 是否主动降低姿态；
- E2 是否触发明确的“当前控制资源不够”证据。

---

# 八、结果裁决规则

## 1. warm-start inheritance 成立

至少满足：

- G3 相对 G1 显著降低 E0 中的无效 max-pitch dwell；
- G3 的 D0 成功率在预注册 non-inferiority margin 内；
- matched state bank 上也存在同方向差异；
- 不只是 scratch 从未进入需要姿态的 stage。

建议 D0 成功率 non-inferiority margin 预设为 `5 percentage points`，正式值在训练前锁定。

---

## 2. 当前门主要 arm/nav sufficient

满足：

- G4 与 G3 在 D0 上接近；
- G4 torque saturation 不显著增加；
- G4 time-to-open 没有大幅恶化；
- BASE0@GRASP 仍有较高成功率。

只满足 G4≈G3、但 BASE0 失败时，结论只能是：

> 无主动 roll/pitch 也能完成，但仍需要 planar base motion。

不能写成纯 arm-only。

---

## 3. 姿态确实有动力学价值

满足：

- D1 中 G7 明显优于 G8；
- FULL 的优势集中在 E1，而不是所有 bucket；
- 姿态开启时 hinge progress、arm torque margin 或 grasp stability 改善；
- matched intervention 的 $\Delta J_\phi>0$。

---

## 4. `0.4 pitch` 是结构性坏习惯

若：

- G3/G7 scratch 仍长期打满；
- E0 中 $\Delta J_\phi\le0$；
- RP0 不降低成功率；
- saturation 主要发生在不需要姿态的 stage；

则问题不是单纯 warm-start inheritance，而是 reward/action parameterization 或 policy mode 缺失。

---

## 5. E2 boundary 建立成功

只有在：

```text
FULL fail
RP0 fail
valid grasp
high effort
low progress
effort/oracle/body rescue succeeds
```

同时成立时，才能宣布“创造了 arm + posture infeasible 区域”。

若必须使用极端数值才能得到 E2，且出现：

- drive instability；
- 非物理震荡；
- 门瞬移；
- contact solver explosion；
- 抓握模型先崩溃；

则结论应是：

> 当前门铰链/摩擦模型不足以表达目标 force boundary。

此时应进入 longterm friction/body-contact TODO，而不是继续放大数字。

---

# 九、关于 coupling critic 在 v23 中的最小落地

v23 可以加入一个不影响 policy 更新的 **shadow coupling evaluator**：

1. 从 E0/E1/E2 的 stable-grasp state bank 取样；
2. 对 2%-5% evaluation environments 做 matched short-horizon intervention；
3. 计算 posture marginal return 与 $\Delta_C$；
4. 训练一个 auxiliary $Q_C$；
5. 只报告：
   - $R^2$；
   - Spearman correlation；
   - sign accuracy；
   - stage-wise calibration；
   - E0/E1/E2 coupling distribution。

它不能进入 PPO advantage。这样能够在不污染 2×2×2 factorial 的前提下，为后续算法分支验证：

> intervention-supervised coupling signal 是否确实可学。

若 exact state clone 当前工程代价过高，则整个模块直接进入 longterm TODO，v23 只保留 acute action-mask intervention。

---

# 十、应写入 longterm TODO 的内容

建议 worker session 将以下内容原样归入已有 longterm TODO ledger，并标记：

```text
[POST-v23 - DO NOT IMPLEMENT IN V23 CORE]
```

## LT-23-01：真实 PiPER capability calibration

- 获取各关节连续/峰值扭矩；
- torque-speed curve；
- current/thermal limit；
- 实机静态推力与持续推力测试；
- 修正 URDF effort；
- 校准 Kp、action scale 和 effort clipping。

验收条件：仿真 torque utilization 与实机电流/负载趋势可对齐。

## LT-23-02：真实 hinge friction model

实现并独立随机化：

- Coulomb friction；
- stiction；
- breakaway torque；
- velocity-dependent friction；
- hysteresis；
- latch release discontinuity。

不得继续用 damping 代替静摩擦。

## LT-23-03：Dynamics oracle 与 system identification

Critic/oracle 输入：

$$
[m,I,c,k,\tau_{\max},\tau_{\mathrm{breakaway}},\mu,\tau_{\mathrm{arm\ limit}}]
$$

Actor 使用 history-estimated latent，而不是永久依赖 exact ground truth。

先做：

```text
critic-only privilege
oracle actor upper bound
history-estimator actor
```

三组对照。

## LT-23-04：三分支 factorized actor

```text
shared recurrent trunk
├── navigation head: vx, vy, yaw
├── posture head: roll, pitch
└── manipulation head: arm + gripper
```

分别保存：

```text
log_prob
ratio
KL
entropy
clipfrac
advantage
```

## LT-23-05：Matched intervention runner

支持：

- exact simulator state clone；
- recurrent history clone；
- common random numbers；
- control-step horizon；
- safe neutral posture；
- safe neutral arm hold；
- four-branch rollout。

## LT-23-06：Intervention-supervised coupling critic

实现：

$$
Q_C(z,a^{nav},a^{posture},a^{arm})
$$

监督目标包括：

- posture-arm interaction；
- nav-arm interaction；
- 必要时 triplet residual。

## LT-23-07：Counterfactual branch PPO

为 navigation、posture、arm 分别生成 counterfactual advantage，不允许继续使用 joint ratio 乘 branch-specific advantage。

## LT-23-08：Learned sparse posture gate

实现：

$$
a^\phi_t=g_t\Delta\phi_t
$$

其中 gate 由 dynamics/history/coupling value 决定。

目标是：

- E0 自动关闭；
- E1 适度开启；
- E2 给出低-confidence或body-assist request；
- 不使用目标高度作为硬编码标签。

## LT-23-09：Handoff/downstream critic

预测当前 stage 结束状态对后续完整成功的价值，处理：

- stage farming；
- bad transition state；
- 提前 release；
- 门开了但无法穿过；
- grasp/arm margin 不适合下一阶段。

## LT-23-10：Body-assist curriculum

仅在 E2 certificate 建立后实施：

- trunk/front-thigh candidate contacts；
- safe contact-region mask；
- contact force/velocity limits；
- strict force-failure gate；
- ordinary-door negative curriculum；
- arm+posture rescue 对照。

## LT-23-11：Student dynamics/coupling distillation

Student 不直接接收 door mass/damping GT，而通过：

- RGB；
- proprioception；
- force/history；
- hinge visual motion；

学习 teacher 的 dynamics latent、posture mode 和 release/hold strategy。

---

# 十一、v23 最终定位

v23 不应以“又设计了一个姿态 reward”为核心，也不应急于把 coupling critic 和 body-assist 全部塞进同一轮。

这一轮最清晰的研究主线是：

> **通过 initialization × door force regime × posture availability 的完整 factorial，判断 `0.4 pitch` 是继承、结构性局部最优，还是实际动力学需求；同时建立可被反事实救援验证的 E0/E1/E2 force-feasibility 边界。**

8 GPU 的最佳首轮利用方式就是上述完整 `2×2×2` 矩阵，每组 `4096 env`。随后用第二轮 8 GPU 对同一矩阵换 seed 复现。完整 coupling critic、三分支 actor 和 body-assist 应建立在 v23 得到的因果证据上，而不是与 v23 同时改变。



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)