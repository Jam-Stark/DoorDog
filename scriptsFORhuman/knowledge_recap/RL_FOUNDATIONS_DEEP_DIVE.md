# 通用 RL 基础：从「会跑 PPO」到「能解释决策、学习与证据」

> **阅读定位。** 这是一份通用 reinforcement learning（RL）教材，服务于面试时从第一性原理解释算法。它不替代本仓库的实现证据：凡涉及 DoorDog 的数字、网络、数据流或阶段，以下都以 `SOURCE_MAP.md`、`FOUNDATIONS.md` 和实际源码的 **INSPECTED** 信息为锚点。通用算法出现于本文，并不表示当前项目都已实现或验证。

> **与本项目的关系。** 当前 DoorDog Teacher 是 recurrent PPO / actor–critic；它用 GAE、entropy bonus、分层 action、staged task 和 curriculum。Student 分支使用 BC/DAgger 思想。本文中的 Q-learning、SARSA、offline RL、model-based RL、hierarchical RL 是重要的通用面试知识，**不是把它们都宣称为当前训练器的功能**。

## 0. 一张总地图：RL 究竟在优化什么？

RL 不是“让网络拟合一个标签”，而是让一个会改变未来数据分布的决策者，最大化长期回报。

```text
environment state s_t ── observation o_t ──> policy πθ ── action a_t ──>
        ^                                                             │
        └──── transition P(s_{t+1}|s_t,a_t), reward r_t, done ────────┘

many collected trajectories → estimate credit / value / advantage → gradient update θ
```

常用符号：

| 符号 | 意义 | 不要混淆为 |
|---|---|---|
| `s_t` | 环境完整状态（理论对象） | 一定能被 policy 看见的输入 |
| `o_t` | agent 实际观测 | 完整 state |
| `a_t` | 当前动作 | 环境最终的力、关节角或下一个状态 |
| `r_t` | 这一步 reward | 这一步 action 的唯一价值 |
| `γ` | discount factor | 学习率 |
| `πθ(a|o)` | 参数化策略分布 | 一个固定 action |
| `Vπ(s)` / `Qπ(s,a)` | 对未来回报的期望 | 单次 trajectory 的真实 return |

### DoorDog 锚点

在当前 Teacher 路径中，4096 个并行仿真环境在每个 50 Hz control step 给出 observation；actor 采样或输出 12D 高层 action，环境和冻结的 locomotion policy 最终形成关节目标。64 个 step 的 rollout 收集后，trainer 用奖励、`done`、value estimate 计算 GAE，并进行 PPO update。Physics 以 200 Hz 执行；它不是 policy 每秒做 200 次“思考”。

### 面试开场题

**问：监督学习和 RL 最大的区别？**

答：监督学习的样本和标签通常给定，目标是拟合条件分布；RL 的 action 会影响未来 state、reward 和后续训练数据。目标是最大化 trajectory 的期望 return，因此有 exploration、credit assignment 和 distribution shift。

---

## 1. Agent、environment 与 trajectory：谁负责什么？

### 直觉

把 RL 看作控制闭环。environment 是世界的演化规则；agent 不是“知道正确答案”的模型，而是根据所见决定下一步。一次 episode 是从 reset 到 terminal/truncation 的决策记录：

![公式 001](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-001.svg)

environment 可能是物理仿真、机器人、游戏或推荐系统。agent 通常包含：

- **policy / actor**：在 observation 条件下选择 action；
- **critic / value estimator**：预测此处开始的长期表现，供 actor 学习；
- **learner**：用收集的 rollout 更新参数；
- **buffer**：保存计算 loss 所需的 transition，例如 `obs, action, reward, done, value, old_logprob`。

### DoorDog 锚点

IsaacLab environment 管理并行的机器人、门、reset、reward 和 termination；Teacher actor 输出任务层 action；critic 在训练期估计 value。部署时不需要 critic 发 action。训练器是 learner，不等同于 environment。

### 常见误解

- “reward 是环境给 policy 的梯度。”错。环境通常只给标量 reward；梯度经由 return、value/advantage 和 policy-gradient estimator 回传到网络参数。
- “episode 一定是自然成功或失败。”错。还可能因 time limit 截断；是否 bootstrap 是一个语义问题。

### 面试题

**问：为什么 rollout buffer 要存 old action log-probability？**

答：PPO 更新同一批旧动作时，要比较新旧 policy 给这些动作的概率，构造 importance ratio；不能仅靠 reward 重算这个比例。

---

## 2. MDP、POMDP 与 policy 的输入边界

### 直觉

若当前完整 state 已包含预测未来所需的一切，系统是 Markov 的：

![公式 002](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-002.svg)

一个 MDP（Markov Decision Process）常写为：

![公式 003](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-003.svg)

它包含 state space、action space、transition kernel、reward rule、discount 和 reset-state distribution。理论里 policy 可以是 deterministic ![公式 004](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-004.svg)，也可以是 stochastic ![公式 005](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-005.svg)。

现实机器人几乎总是 POMDP：真实 state 存在，但相机有遮挡、传感器噪声和延迟，agent 只看到：

![公式 006](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-006.svg)

处理部分可观测性有三种常见层次：堆历史 frame、使用 RNN/LSTM/Transformer 得到 hidden state，或显式维护 belief ![公式 007](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-007.svg)。

### DoorDog 锚点

Teacher 的 privileged observation 比视觉部署条件信息更充分，但仍使用 recurrent actor/critic 来压缩时间信息。Student 仅依据 proprioception 和视觉，部分可观测性、camera age 和 recurrent state 的处理更是 policy contract 的一部分。LSTM 并不是“因为 RNN 更高级”，而是为了从历史中推断当前一帧难以表达的信息。

### 常见误解

- “MDP 要求世界完全确定。”错。`P` 可以是随机转移；Markov 只要求在给定 state/action 后，过去不会额外改变下一步分布。
- “把 observation 命名为 state 就变成 MDP。”错。名字不会恢复被遮挡的信息；对 agent 而言它仍可能是 POMDP。

### 面试题

**问：为什么 RNN rollout 不能随意打散 timestep？**

答：hidden state 来自前序轨迹。训练时必须保留时间顺序、在 `done` 截断 hidden state，并对 padding mask；否则网络会把不同 episode 的记忆错误串联。

---

## 3. Reward、return 与 discount：优化的不是瞬时得分

### 直觉与公式

从时刻 `t` 起的 discounted return：

![公式 008](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-008.svg)

`γ` 让无穷时域和学习尺度可控，也表达更远 reward 的权重。若存在 terminal state，终点后 future return 为零。一个 action 的好坏取决于它怎样改变**之后整段轨迹**，所以 `r_t` 和 `G_t` 不等价。

有限 horizon 任务中，`γ=1` 也可以成立；实践中常取接近 1 的值来保留长期目标，又避免极远 future 主导估计。改变 reward scale 会改变梯度尺度和 value target，不能只把它当“单位换算”。

### DoorDog 锚点

开门中的早期靠近/预抓取动作即时 reward 可能不大，却使后续抓住把手、转轴推进和通过门洞成为可能。staged reward 用更密的信号缩短 long-horizon credit assignment；它不把每一步都变成最终成功。

### 常见误解

- “return 就是累计 reward。”不完整：通常是 discounted 累计，且要处理 terminal 与 truncation。
- “调大 `γ` 一定更聪明。”错。它也令 credit horizon 更长、估计方差更大，未必适合受限 horizon 或 reward 设计。

### 面试题

**问：为什么一个即时 reward 为零的 action 仍值得强化？**

答：它可能让未来到达高回报状态。RL 通过 return 或 TD/GAE 的 bootstrap 把后续改进分配回早期 action。

---

## 4. Value、Q、advantage 与 Bellman：把“未来”变成可递推的预测

### 直觉与公式

给定 policy `π`：

![公式 009](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-009.svg)

![公式 010](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-010.svg)

![公式 011](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-011.svg)

`V` 是“来到这里，平均能有多好”；`Q` 是“在这里做这个具体 action，能有多好”；`A` 是“这个 action 比 policy 在这里的平均选择好多少”。因此 advantage 是**相对基线**，不是 reward、也不是 critic 网络直接输出。

Bellman expectation equation 用一步递推表达未来：

![公式 012](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-012.svg)

![公式 013](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-013.svg)

最优 Bellman equation 则把下一步 action 换为最大化：

![公式 014](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-014.svg)

### Dynamic programming（DP）直觉

已知小型 MDP 的 `P` 与 `R` 时，可以反复做：

1. **policy evaluation**：给固定 `π`，用 Bellman expectation 更新 `V`；
2. **policy improvement**：令 policy 更偏好 `Q` 较大的 action；
3. 二者交替，趋向最优。

DP 是 RL 的概念原型，不适用于高维机器人直接枚举：不知道真实转移分布、state/action 连续且维度巨大。现代 deep RL 用 samples 和神经网络近似替代完整表格与完整模型。

### DoorDog 锚点

critic 估计的是当前 rollout observation 下的 `V`，用于构造 TD residual 和 GAE；actor 的 12D 连续动作来自 Gaussian policy，不会枚举 ![公式 015](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-015.svg)。所以当前 Teacher 更符合 stochastic actor–critic，而非 tabular Q-learning。

### 常见误解

- “value 越高，当前 reward 越高。”错。value 是从现在开始的**期望未来**回报。
- “advantage 正就意味着 action 本身好。”更准确：它相对于采样时的 policy baseline 表现更好；reward 设计或 critic 误差都会影响估计。

### 面试题

**问：为什么 subtract `V(s)` 不会改变 policy-gradient 的期望？**

答：对固定 state，![公式 016](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-016.svg)。state-only baseline 不引入偏差，却常降低方差。

---

## 5. Monte Carlo、TD、n-step、TD(λ) 与 GAE：不同的信用分配镜头

### Monte Carlo（MC）与 one-step TD

MC 走到 episode 尾部后再拿真实样本 return 当 target：

![公式 017](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-017.svg)

优点是不依赖 bootstrap；缺点是需等待很久、长 horizon 方差大。one-step TD 立刻用下一状态自己的预测 bootstrap：

![公式 018](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-018.svg)

![公式 019](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-019.svg)

TD residual `δ_t` 是“走完这一小步后，现实加下一步预测，比原先 value 预测高/低多少”。TD 更低方差、可在线更新，却把 critic 近似误差带进 target，存在 bias。

### n-step 与 TD(λ)

`n`-step return 看 `n` 步真实 reward 后才 bootstrap：

![公式 020](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-020.svg)

它在 `n=1` 的 TD 与接近 episode 尾部的 MC 间折中。TD(λ) 再用几何权重混合所有 n-step target；`λ=0` 接近 one-step TD，![公式 021](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-021.svg) 接近 MC（在合适 terminal 条件下）。

### GAE（Generalized Advantage Estimation）

actor-critic 常不是直接用 `G_t-V_t`，而用按 `γλ` 衰减的 TD residual：

![公式 022](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-022.svg)

或在一个 rollout 内反向递推：

![公式 023](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-023.svg)

`λ` 调的是 bias–variance：小 `λ` 更信任 critic 的一步预测，方差低但更有 bias；大 `λ` 看更长真实 reward，bias 小但方差更高。一个常用 value/return target 是 `R_t=A_t+V_t`。这不是说 `A` 等于 discounted reward sum；它是 residual 的加权和。

### DoorDog 锚点

当前 PPO trainer 对 batched rollout 反向计算 GAE，并用 `done` 切断 ordinary terminal 的 bootstrap。time-limit truncation 与真实 terminal 语义不同：资料记录项目有独立 `time_outs` 信息来决定 value bootstrap。这个细节很重要，不能笼统地说“done 全都不 bootstrap”。具体实现读 `PPO_LSTM_DEEP_DIVE.md` 和 trainer source。

### 常见误解

- “TD residual 就是 reward。”错，它还包含新旧 value prediction 与 discount。
- “GAE 就是 advantage normalization。”错，GAE 负责时间信用分配；标准化只调整一个 batch 的梯度尺度。
- “λ 是 learning rate。”错，`λ` 是 temporal weighting 参数。

### 面试题

**问：为什么 GAE 从后往前写最方便？**

答：`A_t` 依赖 `A_{t+1}`，反向扫一遍即可在 `O(T)` 时间完成整个 trajectory；`done` 用 mask 让递推不跨 episode。

---

## 6. Tabular control：Q-learning、SARSA 与 on-policy/off-policy

### 直觉

在离散、很小的 state/action 空间，可以用表 `Q(s,a)`，不需要神经网络。行为策略（实际收数据的策略）与目标策略（update 想评估/优化的策略）是否相同，是 RL 的一条核心分界。

### SARSA：on-policy

SARSA 用实际下一动作 ![公式 024](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-024.svg) 的值更新：

![公式 025](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-025.svg)

它评估/改进**当前含探索的行为策略**，所以是 on-policy。名字来自 transition `(S,A,R,S',A')`。

### Q-learning：off-policy

Q-learning 的 target 使用 greedy next action：

![公式 026](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-026.svg)

采样时可用带探索的行为策略，但 target 指向 greedy policy；因此是 off-policy。在满足表格、充分探索和适当学习率等条件下，可收敛到 `Q*`。

| 问题 | SARSA | Q-learning |
|---|---|---|
| target 的下一 action | 实际采样的 `a'` | ![公式 027](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-027.svg) |
| policy 类别 | on-policy | off-policy |
| 学到什么 | 当前探索 policy 的价值 | greedy optimal Q（理想表格条件下） |
| 连续 12D action 的直接适配 | 不适合穷举 | 同样不适合直接 `max` |

### DoorDog 锚点

DoorDog 的连续高维 action、视觉/本体输入和 RNN 不能用一张 `Q[s,a]` 表解决。当前 Teacher PPO 是近似 on-policy：rollout 来自 frozen `π_old`，只做有限 PPO epochs 后丢弃，避免 policy 漂得过远。它不等于 SARSA，但同属“数据分布与更新 policy 紧密绑定”的思路。

### 常见误解

- “off-policy 就是不需要新数据。”错。它表示目标与行为 policy 可以不同；仍需覆盖足够的高质量数据和有效的 distribution correction。
- “Q-learning 比 policy gradient 高级。”错。它们适合不同 action、数据和稳定性条件。

### 面试题

**问：为什么 vanilla Q-learning 很难直接用于连续动作机器人？**

答：Bellman target 的 ![公式 028](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-028.svg) 要在连续高维动作空间做内层优化，昂贵且会放大 function approximation 的误差；actor–critic 显式参数化 actor 能直接产生连续 action。

---

## 7. Policy gradient、REINFORCE 与 actor–critic：直接让 policy 朝更好 action 移动

### 从目标到梯度

定义目标：

![公式 029](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-029.svg)

log-derivative trick 给出 score-function estimator：

![公式 030](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-030.svg)

这就是 REINFORCE：如果 trajectory return 高，就增加当时 sampled action 的 log-probability；低就减少。它不必对环境 transition 求导，却常有很高方差。

### Actor–critic

用 critic 作为 baseline 后，常见 actor objective estimator 变成：

![公式 031](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-031.svg)

- ![公式 032](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-032.svg)：提高这次 action 的概率；
- ![公式 033](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-033.svg)：降低这次 action 的概率；
- critic 用 value loss 拟合 return，例如 ![公式 034](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-034.svg)。

actor 与 critic 常共享部分 encoder，也可独立。它们合作但职责不同：actor 负责选择，critic 负责降低梯度方差和 bootstrap。critic 不应偷偷用部署时不允许的 input 来驱动 actor action。

### DoorDog 锚点

当前 Teacher 有 actor/critic，两者的 recurrent trunk 与 observation 输入按资料区分；critic 在训练期估值，actor 输出可部署的任务 action。privileged critic 是 asymmetric actor–critic 的典型设计：它可在训练中提供更好的 baseline，但部署 action 的依赖边界必须保持清楚。

### 常见误解

- “actor-critic 的 critic 就是监督学习的真实标签。”错。value target 自身通常含 reward sample 和 bootstrap，随 policy 改变而改变。
- “policy gradient 要求 action 离散。”错。连续 Gaussian policy 也能计算 ![公式 035](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-035.svg) 并求梯度。

### 面试题

**问：REINFORCE 为什么方差高，critic 如何缓解？**

答：每个 action 都乘上随机长轨迹 return，噪声很大。减去不依赖当前 action 的 `V(s)` 后，只强化相对预期更好/差的部分，同时不改变梯度期望。

---

## 8. PPO：受约束的 on-policy actor–critic 更新

> 这一节建立位置感；逐步数值例子、Gaussian log-prob、recurrent minibatch 与 value clip 见 `PPO_LSTM_DEEP_DIVE.md`。

### 直觉与公式

rollout 是旧策略 `π_old` 收集的。对其中已经采样的同一个 action，比较更新中 `πθ` 与旧 policy 的概率：

![公式 036](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-036.svg)

若仅最大化 ![公式 037](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-037.svg)，对固定旧 batch 多次更新会鼓励 policy 远离数据分布。PPO clipped surrogate：

![公式 038](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-038.svg)

最小化 loss 的实现通常取其负号，并加 value loss、entropy term（以及实现可选的 KL monitoring/penalty）。clip 的要点是**只阻断过度有利于 objective 的变化**：

| advantage | policy 想做什么 | clip 阻断什么 |
|---|---|---|
| `A>0` | 提高 sampled action 概率，`r>1` | `r>1+ε` 后继续提高带来的 surrogate 收益 |
| `A<0` | 降低 sampled action 概率，`r<1` | `r<1-ε` 后继续降低带来的 surrogate 收益 |

PPO 不是严格的 trust-region 证明本身；它是实用近似。`ε=0.2` 限制的是 likelihood ratio 的 surrogate 区间，不是 action 值被 clip 到 `[-0.2,0.2]`。

### DoorDog 锚点

项目资料的 resolved overlay 记录每次 rollout `4096×64` transition，随后做 5 PPO epochs、每 epoch 4 minibatches，并配 entropy coefficient `0.01`、desired KL `0.005` 等参数。把这些视作当前配置的 INSPECTED 信息，不能由此推出该 policy 的任务成功率或现实鲁棒性。

### 常见误解

- “PPO 是 off-policy，因为一份数据 update 多次。”不准确。数据只来自刚冻结的 `π_old`，并限制更新幅度和 epoch 数；标准 PPO 属于 on-policy family。
- “ratio 是 new action / old action。”错，是新旧 policy 对**同一个 sampled action 的概率密度**之比。

### 面试题

**问：为什么连续 action 下仍能算 PPO ratio？**

答：actor 输出如 Gaussian 的均值/方差，采样时保存 joint action 的总 log-prob。update 时重算同一 action 的新 log-prob，取指数差即可得到联合概率密度 ratio。

---

## 9. Exploration、entropy 与 exploitation：为什么训练时要有随机性？

### 直觉与公式

只选当前估值最高 action 是 exploitation；主动试未充分探索 action 是 exploration。没有探索，early lucky/poor sample 可能把 policy 锁在局部行为。离散 policy entropy：

![公式 039](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-039.svg)

连续 Gaussian 的 entropy 与协方差/标准差相关；分布越宽，采样范围通常越大。许多 actor–critic 最大化：

![公式 040](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-040.svg)

等价地，若使用 gradient descent 写 loss，会以合适符号加入负 entropy。

探索不只来自 entropy：也可用 `ε`-greedy、parameter noise、intrinsic reward、count-based bonus、随机 reset 或 domain randomization。不同策略改变的对象不同，不能一概而论。

### DoorDog 锚点

Teacher 训练时从 action distribution 采样以探索，评估常取 mean/确定性 action 来测可复现控制。资料显示 PPO loss 有 entropy 项；它鼓励足够探索，却不能替代合适 reward、reset coverage 或真实泛化评估。

### 常见误解

- “entropy 越高越好。”错。过高意味着长时间随机，妨碍收敛；entropy coefficient 是探索–利用权衡。
- “evaluation 也必须随机采样才公平。”不一定。应先声明协议；常用 deterministic mean 评估，也可额外报告 stochastic robustness。

### 面试题

**问：训练 return 上升而 entropy 快速坍塌，你会担心什么？**

答：可能已收敛，也可能过早锁进局部策略。要结合成功率、不同 seed、状态覆盖、KL/行动方差与 holdout 场景判断，不能单凭 entropy 下结论。

---

## 10. Credit assignment：成功究竟该归功于哪一步？

### 直觉

长任务的最终门开了，不代表最后一个 action 独自有功。早期 walk、对准、预抓取和接触建立了后续可行状态。credit assignment 就是将 delayed outcome 合理归因给较早 action 的问题。

三类常用帮助：

1. **return / MC**：真实地看完整后果，但 noisy；
2. **TD / GAE**：用 critic bootstrap 与多步 residual 平衡方差；
3. **task design**：reward shaping、curriculum、reset distribution 或 hierarchical decomposition 缩短有效 horizon。

注意：好算法无法从完全无信息、极稀疏且从未偶然成功的奖励中凭空创造梯度。探索与状态覆盖也必须成立。

### DoorDog 锚点

六阶段任务组织和 staged reset 有助于把“从自然起点走到门后”的超长学习问题分段暴露。但 staged reset 的后段成功只能证明对应条件下的能力，不能替代 natural-start 完整闭环成功证据。

### 常见误解

- “dense reward 自动解决 credit assignment。”错。它可能引入错误捷径，或令局部 proxy 压过真正任务目标。
- “critic 的 A 值是因果归因。”错。advantage 是在当前训练数据与函数近似下的统计学习信号，不是干预式因果结论。

### 面试题

**问：为何 curriculum 有时比单纯增大学习率更有效？**

答：它改变 reset/state distribution，使 agent 更频繁地看到可学习的成功前缀和有效 reward，而不是只让优化器对极稀疏、同样缺乏信息的数据走得更大步。

---

## 11. Reward shaping 与 reward hacking：奖励是规范，不是注释

### 直觉与公式

环境真正优化的是你实现的 `R`，不是你脑中想表达的任务。reward shaping 通过中间信号改善学习，例如距离、朝向、接触或进度。但每个 proxy 都可能被钻空子。

一种理论上保持最优 policy 的 shaping 形式是 potential-based shaping：

![公式 041](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-041.svg)

在标准假设下，return 只差一个与起点有关的望远镜项，所以不改变最优 policy；但工程 reward 常不满足这些理想条件，仍需行为验证。

reward hacking / specification gaming 是 agent 最大化 proxy，却不完成意图。例如反复蹭把手取得接触奖励、不通过门洞却刷局部进度、利用 reset/termination 漏洞避免惩罚。

### DoorDog 锚点

项目明确区分 reward、stage advance、terminal success 和 timeout。阶段推进能组织学习，不能本身构成最终成功；必须以真正的门开、通过及预注册评估标准核验。DoorDog 的 reward 设计应由当前 source/config 和实验结果裁定，不能从一个总 return 曲线推断“真的会开门”。

### 常见误解

- “reward 高就证明任务成功。”错。它可能只证明 reward code 可被优化。
- “多加几个 penalty 一定更安全。”错。会改变最优策略、信用分配与尺度；需要明确失败模式和评估指标。

### 面试题

**问：怎样发现 reward hacking？**

答：把优化指标与独立 task metric 分开，查看 rollout/video、逐项 reward 分解、失败 termination、跨 reset/随机化评估；发现 return 与真实成功脱钩时，先定位被利用的 proxy 再改规范。

---

## 12. Imitation learning、BC、DAgger 与 offline RL：数据并非都来自当前 policy

### Behavior Cloning（BC）

给 demonstrations `(o,a^*)`，直接做监督学习：

![公式 042](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-042.svg)

BC 简单、样本有效，却有 covariate shift：训练数据来自 expert 访问的 state，而部署中 learner 的一个小错误会进入 expert 没覆盖的 state，下一步更易错，误差累计。

### DAgger

Dataset Aggregation 的循环是：

```text
current learner controls / mixed rollout
        → learner actually visits off-expert states
        → query expert/Teacher for the correct action there
        → aggregate labels and retrain learner
```

它的关键不是“多收一点 expert data”，而是让标签覆盖 learner 自己的闭环状态分布。Teacher 也可能有限、昂贵或在 student observation 下不可完全复制，DAgger 并不魔法般解决所有问题。

### Offline RL

offline RL 只从固定数据集 `D` 学 policy，不再在线采样。它可利用历史日志、避免在线试错风险，但主要困难是 distributional shift / extrapolation：policy 若选择数据没覆盖的 action，value 学习会过度乐观。典型方法以 conservative value、behavior regularization 或 advantage-weighted objective 减轻 out-of-distribution action 问题。

### DoorDog 锚点

Student 蒸馏分支采用 Teacher label 和 mixed rollout / DAgger 的思路，目标是让视觉 Student 在自己可能走到的状态也获得 Teacher 的 12D task-action 指导。它不是纯 offline RL，也不等于完整 Phase3 task-return RL fine-tuning；现有资料须把 Phase2 已实现和 Phase3 尚未完整实现分开表述。

### 常见误解

- “BC 的 loss 很低就说明闭环控制好。”错。validation 也必须包含 learner rollout 下的 task metrics。
- “DAgger 就是拿 student action 当标签。”错。标签仍是 Teacher/expert action；student action 用于访问需要被纠正的 states。
- “有 dataset 就是 offline RL。”不一定。BC 是 imitation；offline RL 特指从静态数据以 return/value 目标优化 policy 的一类问题设定。

### 面试题

**问：DAgger 如何缓解 covariate shift？**

答：让 learner 或混合 policy 执行，收集 learner 实际访问状态，再由 expert 标注这些状态并聚合进训练集；因此训练分布逐步接近部署分布。

---

## 13. Model-free 与 model-based RL：要不要学/用世界模型？

### 直觉

- **model-free**：直接学习 value、policy 或两者，不显式预测 `P(s'|s,a)`；例如 PPO、SAC、DQN。
- **model-based**：已知或学习 dynamics model，再用 planning、model predictive control（MPC）、imagined rollout 或 value expansion 选择 action。

model-based 在模型足够准时可更 sample-efficient，因为能在模型内试很多 action；代价是 model bias：策略会利用模型错误，在真实环境中失败。模型是否显式出现是一条谱，不是二元神学。例如 actor-critic 的 critic 不是 dynamics model；它预测 return，不直接预测下一 state。

### DoorDog 锚点

当前 Teacher PPO 训练路径是 model-free policy optimization：Isaac physics environment 提供真实仿真转移，但 trainer 不学习一个供规划的世界模型。Isaac Sim 是 simulator，不意味着算法自动成为 model-based RL。

### 常见误解

- “只要有 simulator 就是 model-based RL。”错。是否以 dynamics model 做 planning/imagined learning 才是分类关键。
- “model-free 完全不使用模型。”通常是“不显式学习并用于决策 dynamics model”；environment 仍按其物理规则转移。

### 面试题

**问：为什么 learned world model 会导致真实机器人风险？**

答：优化器会反复寻找模型预测高回报的 action；若模型在接触、摩擦、延迟等区域错得系统性，planner 可能专门利用这些误差。必须用不确定性、真实数据和保守验证约束，而非只看 imagined return。

---

## 14. Hierarchical RL 与动作分层：不同时间尺度的控制问题

### 直觉

长任务可拆成高层选择子目标/skill，低层在较快时间尺度执行。例如：

![公式 043](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-043.svg)

`z` 可以是 option、goal、base velocity command、gripper primitive 或 latent skill。分层可能减少高层的 action dimension 与 credit horizon，复用已有 locomotion skill；但也会把 interface 固化成 contract，并可能限制最优联合行为。

经典 options 框架含 initiation set、intra-option policy 和 termination condition。不要把任意多网络架构都叫 HRL；核心是有意义的 temporal abstraction / skill interface。

### DoorDog 锚点

DoorDog 并非让一个网络从零输出所有 20 个关节：Teacher PPO 输出 12D 任务层 action，其中包含 base command、arm 与 gripper primitive；冻结的 A2_Base 从本体历史输出腿 action，再由 trainer/environment 组合。这是明确的控制分层。六个任务 stage 是 curriculum/task organization，和 policy 的 option learning 相关但不应自动画等号。

### 常见误解

- “分层一定更好。”错。接口丢失信息、低层能力不足、两个层的 timebase 不匹配都可能成为瓶颈。
- “高层 action 就是最终 torque。”错。高层 command 经过低层 policy、action mapping 和 PD/physics 后才是关节层作用。

### 面试题

**问：分层 policy 的主要好处和风险分别是什么？**

答：好处是复用低层稳定技能、降低高层搜索空间、缩短有效 horizon；风险是高低层 contract 成为硬约束，若低层覆盖不到开门所需姿态或时间尺度错配，上层再好也无法补救。

---

## 15. Curriculum、staged reset 与 domain randomization：改变训练分布，但不替代评估

### Curriculum

curriculum 将难任务排成可学习序列，例如先从门边已就位状态学抓取，再逐步扩展到自然起点、更多初始姿态或更复杂门参数。它本质上改变训练 reset distribution：

![公式 044](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-044.svg)

它可以解决稀疏成功和长 horizon，但会产生 distribution gap：只在容易起点表现好，不能证明自然起点全流程成功。

### Domain randomization（DR）

DR 在训练中采样 domain parameters：

![公式 045](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-045.svg)

目标是让 policy 对合理变化鲁棒。randomization 的范围、频率、相关性与真实分布是否匹配都很关键；随机得太宽会使学习困难，随机错维度也不会补上真正 sim-to-real gap。

### DoorDog 锚点

DoorDog 的 staged reset 是 curriculum，不是自然起点的成功证据。项目还讨论门铰链、姿态、摩擦等条件；任何“泛化/robust”的结论必须绑定实际 randomization config、holdout protocol 与实验结果。sim2sim 的 joint order、timebase、camera age 等 contract 也不能被“我做了 randomization”替代。

### 常见误解

- “训练随机化越多，sim2real 越强。”错。未被建模的接触、执行器、传感器和系统辨识误差仍可能主导失败。
- “从 Stage 4 reset 成功，说明能从 Stage 0 开门。”错。只说明条件状态下的一段能力。

### 面试题

**问：怎样验证 curriculum 没有掩盖起点分布失败？**

答：独立报告自然初始状态的完整成功率和阶段覆盖，而非只报告按 curriculum 起点的平均 return；预先固定场景、seed、门参数与 success criterion。

---

## 16. Evaluation、统计证据与实验边界：曲线不是结论

### 直觉

训练曲线是优化过程的观测，不是 policy capability 的直接证明。完整评估至少说明：

- **metric**：success、return、constraint violation、completion time、energy 等各自定义；
- **protocol**：initial-state distribution、domain parameters、deterministic/stochastic action、episode horizon；
- **sample unit**：episode、seed、scene 还是 checkpoint；
- **aggregation**：mean/median/success rate、置信区间或 bootstrap interval；
- **comparison**：baseline、ablation、matched seeds/conditions；
- **selection discipline**：checkpoint 选择是否偷看了 test/holdout。

如果 `k` 次独立 episode 中成功 `x` 次，点估计是 ![公式 046](./assets/math/RL_FOUNDATIONS_DEEP_DIVE/math-046.svg)，但必须呈现不确定性。小样本的 `100%` 不代表真实成功概率为 100%；多个 seed 的方差也不应藏在一个最佳曲线后面。

### 证据等级

| 等级 | 可说什么 | 不能自动推到 |
|---|---|---|
| INSPECTED | 源码/config 中存在某逻辑 | 它实际运行正确 |
| STATIC_PASS | 语法、类型、导入等通过 | 仿真行为正确 |
| RUNTIME_PASS | 某条真实路径跑过 | 泛化或任务成功 |
| EXPERIMENT_PASS | 在已注册协议下得到指标 | 硬件安全/部署可靠 |
| HARDWARE_PASS | 指定实机条件验证 | 所有现实条件都安全 |

### DoorDog 锚点

知识材料应持续区分：当前 Teacher contract 属于 source/config inspected；部分分支可能有对应 runtime/experiment artifact；sim2sim paired parity 和 hardware safety 不能因一个 MuJoCo module 跑通而自动成立。门开动作牵涉接触与设备，simulator return 更不能直接升级为实机安全证据。

### 常见误解

- “best checkpoint 的最好视频就是证据。”错。它可做定性诊断，不能取代固定 protocol 的样本统计。
- “没有 p-value 就没有任何结论。”也不对。先报告 effect size、样本量、区间、协议和限制；统计检验应匹配具体问题，而不是机械套用。

### 面试题

**问：为什么要区分 training return、evaluation success 和 hardware evidence？**

答：它们测的对象不同：训练 return 反映已定义 reward 下的优化；评估 success 反映独立任务准则；hardware 还包含传感器、执行器、接触和安全边界。低层证据不能逻辑地替代高层。

---

## 17. 面试时的“算法选择”框架

不要背算法名，先按问题回答：

| 条件 | 常见选择逻辑 | DoorDog 对应理解 |
|---|---|---|
| 小型离散、可充分探索 | tabular DP / SARSA / Q-learning | 仅作概念基础，不适用于 12D continuous actor |
| 高维连续、能在线收 rollout | actor–critic，如 PPO / SAC / TD3 | 当前 Teacher 是 recurrent PPO family |
| 有专家示范，在线试错昂贵 | BC 起步，DAgger 扩展状态覆盖 | Student Phase2 的核心思想 |
| 固定历史数据、不能交互 | offline RL / conservative policy learning | 不要把 DAgger mixed rollout 误叫 offline RL |
| 已知或可学可靠 dynamics | planning / MPC / model-based RL | 当前 PPO trainer 不学习 planning world model |
| 长任务，可复用低层 skill | hierarchical policy / options / goals | Teacher task layer + frozen A2_Base |
| sim-to-real / scene variation | curriculum + targeted DR + independent evaluation | 必须保留 contract 与真实 holdout 证据 |

### 一分钟通用回答模板

> 我先把问题写成 POMDP：机器人看到的 observation 不等于完整物理 state，因此 policy 需要当前输入和必要历史。目标是最大化 discounted return，而不是某一步 reward。actor 给出连续 action distribution，critic 估计从当前状态开始的 expected return。一次 rollout 后，用 TD residual 和 GAE 把 delayed outcome 变成低方差 advantage；PPO 再用新旧 policy 对同一 sampled action 的概率比做保守更新，entropy 保留探索。长时程任务还要靠 reward 规范、curriculum 和必要的分层控制改善 credit assignment，但最终只接受独立 natural-start/holdout protocol 下的 success 与约束指标，不能把训练曲线或仿真通过说成实机证据。

---

## 18. 闭卷自测：从“定义”到“工程判断”

1. `s`、`o`、belief、history 何时不同？为什么 POMDP 需要 RNN 或 history？
2. 写出 `G_t`、`Vπ`、`Qπ`、`Aπ` 和 Bellman expectation equation，并解释每项语义。
3. MC target 与 one-step TD target 各依赖什么？谁的方差更高、谁的 bootstrap bias 更强？
4. 写出 TD residual、n-step return、TD(λ)/GAE 递推；`λ=0` 与接近 1 分别意味着什么？
5. SARSA 与 Q-learning 的 target 为什么不同？on-policy/off-policy 到底描述哪两个 policy 的关系？
6. 从 `J(θ)` 推出为什么 REINFORCE 乘 `∇logπ`；baseline 为什么不会改变期望梯度？
7. actor、critic、return target 和 advantage 各做什么？critic 错会如何影响 actor？
8. 写出 PPO ratio 与 clipped surrogate。`A>0`、`A<0` 时哪一种“走太远”会被截断？
9. entropy 奖励的是什么，为什么不能无限大？train/eval 的 action 采样协议应如何说明？
10. 举一个 reward hacking 例子，并说明你会用什么独立 metric 和视频/telemetry 去发现它。
11. 普通 BC 的 covariate shift 怎么产生？DAgger 如何改变数据收集分布？
12. simulator、model-based RL、model-free PPO 三者各是什么关系？
13. staged reset/curriculum 为什么能帮忙，又为何不能证明 natural-start success？
14. 给出一份实验结果时，至少应交代哪些统计和证据边界？

## 进一步阅读顺序

1. `PPO_LSTM_DEEP_DIVE.md`：把 TD residual、GAE、ratio、clip 与 recurrent rollout 逐式吃透；
2. `FOUNDATIONS.md`：把概念接回 DoorDog 的 observation、action、Isaac control loop；
3. `INTERVIEW_CHEATSHEET.md`：60 秒白板复述；
4. `SOURCE_MAP.md`：若要声称“项目实际怎样做”，回到可定位的 source/config，而不是背教材。
