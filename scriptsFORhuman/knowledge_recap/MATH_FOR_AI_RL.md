# AI / RL 数学底座：从 tensor 到 PPO 与 LSTM

这不是一本追求定理证明的线性代数课，而是一份面试时能拿来推理的“计算语言手册”。读法是：先用每节的数值例子把符号变成可算的量，再把最后一段接回 DoorDog 的 tensor、PPO 或 LSTM。

记号约定：标量写作 ![公式 001](./assets/math/MATH_FOR_AI_RL/math-001.svg)，向量写作 ![公式 002](./assets/math/MATH_FOR_AI_RL/math-002.svg)，矩阵写作 ![公式 003](./assets/math/MATH_FOR_AI_RL/math-003.svg)，batch 维通常记为 ![公式 004](./assets/math/MATH_FOR_AI_RL/math-004.svg)，时间维记为 ![公式 005](./assets/math/MATH_FOR_AI_RL/math-005.svg)。例如 `actor_obs` 的 shape `(B, 133)` 表示一次为 `B` 个并行环境各提供 133 个特征。

## 1. 标量、向量、矩阵与 tensor：同一种数的不同组织方式

### 1.1 从一个数到一批序列

- **标量（scalar）**：一个数，如当前环境的 reward ![公式 006](./assets/math/MATH_FOR_AI_RL/math-006.svg)。shape 是 `()`。
- **向量（vector）**：有顺序的一列数，如一个环境的 action ![公式 007](./assets/math/MATH_FOR_AI_RL/math-007.svg)。shape 是 `(3,)`。
- **矩阵（matrix）**：按行和列排的数，如一个 batch 的 2 个 3D observation：![公式 008](./assets/math/MATH_FOR_AI_RL/math-008.svg)，shape 是 `(2, 3)`。
- **tensor**：泛称任意维数组。对 recurrent rollout，`obs` 常是 `(T, B, D)`：64 个时间步、4096 个环境、每帧 133 个特征。

一个重要但容易漏掉的事实：**shape 只说明槽位数，不说明语义**。`(B, 12)` 可以是 Teacher 的高层 action，也可以是 A2_Base 的腿动作；二者数目相同，含义和下游却不同。

数值例子：若 `obs.shape == (64, 4096, 133)`，元素总数是 ![公式 009](./assets/math/MATH_FOR_AI_RL/math-009.svg)。若是 `float32`，仅这一块约占 ![公式 010](./assets/math/MATH_FOR_AI_RL/math-010.svg) MiB；这解释了为什么 rollout buffer 是训练中的实在成本。

与项目的连接：Teacher actor 在一个时刻实际消费的是 `(B, 133)`；LSTM 会把连续时刻重新组织成 `(T, B, 133)`（或某个 chunk 长度），并为每条序列配套初始 hidden state 和 mask。PPO 保存的是逐 transition 的 action、value、log probability、reward、done，而不是只保存最后一帧。

### 1.2 broadcast、reduce 与维度含义

`(B, 12)` 的 action 乘上 `(12,)` 的 action scale，得到 `(B, 12)`：后者沿 batch 维被 broadcast。例：

![公式 011](./assets/math/MATH_FOR_AI_RL/math-011.svg)

`sum(dim=-1)` 则消掉最后一维。若每个 action 的 Gaussian log-prob 分量为 `(B, 12)`，沿最后一维求和后才得到每个环境一个 joint log-prob，shape `(B,)`。PPO ratio 正是按这个“整个 12D action 的联合概率”计算，而不是逐维随意取平均。

面试自答：

> 问：为什么需要主动说 shape，而不只说“网络输出 action”？
>
> 答：因为 batch、time、feature 三个维度的含义决定了矩阵乘法、mask、log-prob reduction 和 LSTM 状态是否正确。shape 对上但特征顺序或 joint order 错了，policy 仍会运行，却在执行错误的控制合同。

## 2. 点积、范数与投影：相似度、大小和“沿某个方向的量”

### 2.1 点积（dot product）

![公式 012](./assets/math/MATH_FOR_AI_RL/math-012.svg)

令 ![公式 013](./assets/math/MATH_FOR_AI_RL/math-013.svg)，![公式 014](./assets/math/MATH_FOR_AI_RL/math-014.svg)，则点积是 ![公式 015](./assets/math/MATH_FOR_AI_RL/math-015.svg)。几何上它等于 ![公式 016](./assets/math/MATH_FOR_AI_RL/math-016.svg)：同向为正，反向为负，垂直为零。

在线性层，一个 neuron 的 pre-activation 就是 `x @ w + b`。若 ![公式 017](./assets/math/MATH_FOR_AI_RL/math-017.svg)、![公式 018](./assets/math/MATH_FOR_AI_RL/math-018.svg)，输入 ![公式 019](./assets/math/MATH_FOR_AI_RL/math-019.svg) 给出 ![公式 020](./assets/math/MATH_FOR_AI_RL/math-020.svg)。这不是“神经网络的神秘计算”，就是对特征加权求和。

### 2.2 范数（norm）

最常见的 ![公式 021](./assets/math/MATH_FOR_AI_RL/math-021.svg) 范数是向量长度：

![公式 022](./assets/math/MATH_FOR_AI_RL/math-022.svg)

例：![公式 023](./assets/math/MATH_FOR_AI_RL/math-023.svg)，而 ![公式 024](./assets/math/MATH_FOR_AI_RL/math-024.svg)。将向量归一化为单位长度：![公式 025](./assets/math/MATH_FOR_AI_RL/math-025.svg)。

PPO 中常见 `max_grad_norm` 是对**所有参数梯度拼接后**的 ![公式 026](./assets/math/MATH_FOR_AI_RL/math-026.svg) norm 做裁剪；它限制一次异常 batch 给 optimizer 的步长，不等于裁剪 action。若全局 gradient norm 是 10、阈值是 1，则整体乘以 0.1，方向不变、大小变为 1。

### 2.3 投影（projection）

将 ![公式 027](./assets/math/MATH_FOR_AI_RL/math-027.svg) 投影到非零方向 ![公式 028](./assets/math/MATH_FOR_AI_RL/math-028.svg) 上：

![公式 029](./assets/math/MATH_FOR_AI_RL/math-029.svg)

例：![公式 030](./assets/math/MATH_FOR_AI_RL/math-030.svg)，![公式 031](./assets/math/MATH_FOR_AI_RL/math-031.svg)。系数 ![公式 032](./assets/math/MATH_FOR_AI_RL/math-032.svg)，投影为 ![公式 033](./assets/math/MATH_FOR_AI_RL/math-033.svg)，残差 ![公式 034](./assets/math/MATH_FOR_AI_RL/math-034.svg) 与 ![公式 035](./assets/math/MATH_FOR_AI_RL/math-035.svg) 正交。这是“只保留沿某个方向的成分”。

与 RL 的连接：reward 中的 velocity alignment、手柄方向对齐等，常以 dot product 衡量“运动是否朝目标方向”；归一化与尺度决定该值是否能跨场景比较。LSTM 没有显式写投影式，但每个 gate 的权重同样是在把高维 input/hidden 映射到几个可学习方向。

面试自答：

> 问：点积为零说明什么？
>
> 答：对 Euclidean 向量，它们正交；例如一个 residual 对某个方向的投影为零。它不自动表示两个随机变量独立，也不表示两个 tensor 没有任何关系。

## 3. 矩阵乘法与线性层：batch 如何一次过网络

### 3.1 矩阵乘法的行列规则

若 ![公式 036](./assets/math/MATH_FOR_AI_RL/math-036.svg) 是 ![公式 037](./assets/math/MATH_FOR_AI_RL/math-037.svg)，![公式 038](./assets/math/MATH_FOR_AI_RL/math-038.svg) 是 ![公式 039](./assets/math/MATH_FOR_AI_RL/math-039.svg)，则 ![公式 040](./assets/math/MATH_FOR_AI_RL/math-040.svg) 是 ![公式 041](./assets/math/MATH_FOR_AI_RL/math-041.svg)。中间的 ![公式 042](./assets/math/MATH_FOR_AI_RL/math-042.svg) 必须相同。

![公式 043](./assets/math/MATH_FOR_AI_RL/math-043.svg)

左矩阵的每一行与右矩阵的每一列做 dot product：左上角是 ![公式 044](./assets/math/MATH_FOR_AI_RL/math-044.svg)。矩阵乘法不可交换：上例中 ![公式 045](./assets/math/MATH_FOR_AI_RL/math-045.svg)。

### 3.2 PyTorch 线性层的 orientation

概念式是 ![公式 046](./assets/math/MATH_FOR_AI_RL/math-046.svg)：若输入 ![公式 047](./assets/math/MATH_FOR_AI_RL/math-047.svg) 是 3D，输出是 2D，则 ![公式 048](./assets/math/MATH_FOR_AI_RL/math-048.svg) 的 shape 是 `(2, 3)`。PyTorch 对 batch 写作 `y = x @ W.T + b`：若 `x.shape=(B,3)`，结果 `y.shape=(B,2)`。

数值例子：

![公式 049](./assets/math/MATH_FOR_AI_RL/math-049.svg)

输出是 ![公式 050](./assets/math/MATH_FOR_AI_RL/math-050.svg)。之后 ReLU 会把它变为 ![公式 051](./assets/math/MATH_FOR_AI_RL/math-051.svg)；tanh 则保留负号但压到 ![公式 052](./assets/math/MATH_FOR_AI_RL/math-052.svg)。

与项目的连接：`133D -> 512D` 的 actor 第一层就是把 133 个 observation feature 用 512 组可学习权重重新组合。它不会“知道哪个槽位是 door pose”；该语义由 observation construction 的固定顺序提供。网络参数的 shape 在加载 checkpoint 时也是合同的一部分。

### 3.3 非线性为什么必要

两层没有 activation 的线性层：![公式 053](./assets/math/MATH_FOR_AI_RL/math-053.svg)，仍可合并为一层线性变换。ReLU、ELU、tanh 等非线性插入后，网络才能表达非线性决策边界。

例：一维输入 ![公式 054](./assets/math/MATH_FOR_AI_RL/math-054.svg)，目标函数 ![公式 055](./assets/math/MATH_FOR_AI_RL/math-055.svg)。单条直线无法同时拟合 ![公式 056](./assets/math/MATH_FOR_AI_RL/math-056.svg)，但 ![公式 057](./assets/math/MATH_FOR_AI_RL/math-057.svg)。

面试自答：

> 问：`B×133` 乘 `512×133` 为什么报错？
>
> 答：按 `@` 的规则，前者最后一维 133 需等于后者倒数第二维 512。应使用权重转置 `(133,512)`，或使用 `nn.Linear(133,512)`，它已处理权重存储方向。

## 4. gradient、Jacobian 与 chain rule：参数到底怎么收到学习信号

### 4.1 导数、偏导与 gradient

一元函数 ![公式 058](./assets/math/MATH_FOR_AI_RL/math-058.svg) 在 ![公式 059](./assets/math/MATH_FOR_AI_RL/math-059.svg) 的导数为 ![公式 060](./assets/math/MATH_FOR_AI_RL/math-060.svg)：输入小增量造成输出多快变化。

若 ![公式 061](./assets/math/MATH_FOR_AI_RL/math-061.svg)，则

![公式 062](./assets/math/MATH_FOR_AI_RL/math-062.svg)

在 ![公式 063](./assets/math/MATH_FOR_AI_RL/math-063.svg) 处，gradient 为 ![公式 064](./assets/math/MATH_FOR_AI_RL/math-064.svg)。它指向局部增长最快的方向；做最小化时使用反方向 ![公式 065](./assets/math/MATH_FOR_AI_RL/math-065.svg)。学习率 ![公式 066](./assets/math/MATH_FOR_AI_RL/math-066.svg) 的一步是 ![公式 067](./assets/math/MATH_FOR_AI_RL/math-067.svg)。

PPO 的 loss 是对数百万参数的标量；`loss.backward()` 求每个参数的偏导。不是所有参数一定都应有梯度：冻结的 A2_Base 应不参与 Teacher PPO optimizer。

### 4.2 Jacobian：向量输出对向量输入的全部一阶变化

若 ![公式 068](./assets/math/MATH_FOR_AI_RL/math-068.svg)，Jacobian 是 ![公式 069](./assets/math/MATH_FOR_AI_RL/math-069.svg) 矩阵：第 ![公式 070](./assets/math/MATH_FOR_AI_RL/math-070.svg) 行是输出 ![公式 071](./assets/math/MATH_FOR_AI_RL/math-071.svg) 对所有输入的 gradient。

令 ![公式 072](./assets/math/MATH_FOR_AI_RL/math-072.svg)。

![公式 073](./assets/math/MATH_FOR_AI_RL/math-073.svg)

输入小变化 ![公式 074](./assets/math/MATH_FOR_AI_RL/math-074.svg) 时，输出近似变化 ![公式 075](./assets/math/MATH_FOR_AI_RL/math-075.svg)。Jacobian 是局部线性化，不是对大幅变化的精确承诺。

在 actor 中，![公式 076](./assets/math/MATH_FOR_AI_RL/math-076.svg) 是 12D action mean；它对 133D observation 的 Jacobian 描述局部敏感性，对参数 ![公式 077](./assets/math/MATH_FOR_AI_RL/math-077.svg) 的 Jacobian 则是反向传播会用到的链条一部分。

### 4.3 Chain rule：反向传播唯一的核心规则

复合函数 ![公式 078](./assets/math/MATH_FOR_AI_RL/math-078.svg) 有：

![公式 079](./assets/math/MATH_FOR_AI_RL/math-079.svg)

例：![公式 080](./assets/math/MATH_FOR_AI_RL/math-080.svg)，![公式 081](./assets/math/MATH_FOR_AI_RL/math-081.svg)，当 ![公式 082](./assets/math/MATH_FOR_AI_RL/math-082.svg) 时 ![公式 083](./assets/math/MATH_FOR_AI_RL/math-083.svg)。![公式 084](./assets/math/MATH_FOR_AI_RL/math-084.svg)，![公式 085](./assets/math/MATH_FOR_AI_RL/math-085.svg)，所以 ![公式 086](./assets/math/MATH_FOR_AI_RL/math-086.svg)。直接展开 ![公式 087](./assets/math/MATH_FOR_AI_RL/math-087.svg) 也得到 ![公式 088](./assets/math/MATH_FOR_AI_RL/math-088.svg)。

反向传播只是把这个规则从 scalar loss 向网络输入端逐层复用，并缓存 forward 中需要的局部值。对于 layer `z = W x + b`，上游梯度若是 ![公式 089](./assets/math/MATH_FOR_AI_RL/math-089.svg)，则 ![公式 090](./assets/math/MATH_FOR_AI_RL/math-090.svg)：一个很直观的 outer product。

小例：![公式 091](./assets/math/MATH_FOR_AI_RL/math-091.svg)，![公式 092](./assets/math/MATH_FOR_AI_RL/math-092.svg)，则

![公式 093](./assets/math/MATH_FOR_AI_RL/math-093.svg)

这说明每个 weight 的更新依赖“该输入 feature 多大”与“该 output unit 的误差信号多大”。

面试自答：

> 问：为什么说 backprop 不是“从 reward 直接传到动作”？
>
> 答：环境的动力学与 reward 通常不可微、也没有穿过 PhysX 反传。PPO 先把 sampled trajectory 变成 advantage，再利用 `log πθ(a|o)` 对参数可微的性质构造 policy-gradient loss；autograd 只在 policy/critic 网络内部按 chain rule 传播。

## 5. LSTM 的数学：memory 是受控的信息通道

普通 RNN 形式为 ![公式 094](./assets/math/MATH_FOR_AI_RL/math-094.svg)。其反复乘以 ![公式 095](./assets/math/MATH_FOR_AI_RL/math-095.svg) 容易让梯度消失或爆炸。LSTM 以 gate 控制 cell state：

![公式 096](./assets/math/MATH_FOR_AI_RL/math-096.svg)

数值例子（把 gate 的输出当作已算好）：若上一 cell ![公式 097](./assets/math/MATH_FOR_AI_RL/math-097.svg)，![公式 098](./assets/math/MATH_FOR_AI_RL/math-098.svg)，![公式 099](./assets/math/MATH_FOR_AI_RL/math-099.svg)，候选 ![公式 100](./assets/math/MATH_FOR_AI_RL/math-100.svg)，则 ![公式 101](./assets/math/MATH_FOR_AI_RL/math-101.svg)。若 ![公式 102](./assets/math/MATH_FOR_AI_RL/math-102.svg)，则 ![公式 103](./assets/math/MATH_FOR_AI_RL/math-103.svg)。forget gate 不是一个二元开关；它是连续的、按 hidden unit 分量不同的向量。

与项目的连接：每个并行环境各有自己的 LSTM `(h,c)`；某一环境 `done` 后，**只**清零这一行的 hidden state。recurrent PPO 需要按 episode 切 sequence、在 padding 位置 mask loss，否则新 episode 会继承旧 episode 的记忆，或 padding 产生假的学习信号。

面试自答：

> 问：LSTM 是否等同于“把过去所有 observation 原样保存”？
>
> 答：不是。它把历史压缩到固定维度的状态，保留什么由损失驱动学习；它可能遗忘，也不保证 reconstruct 过去。它在 POMDP 中提供 belief 的近似，而非完整状态的保证。

## 6. 概率：policy 输出的是分布，不只是一个 action

### 6.1 随机变量、概率质量与概率密度

随机变量 ![公式 104](./assets/math/MATH_FOR_AI_RL/math-104.svg) 是一次随机试验的数值结果。离散变量用概率质量 ![公式 105](./assets/math/MATH_FOR_AI_RL/math-105.svg)，连续变量用 density ![公式 106](./assets/math/MATH_FOR_AI_RL/math-106.svg)。连续情况下 ![公式 107](./assets/math/MATH_FOR_AI_RL/math-107.svg) 不代表 0 “不可能”；具体点的概率为零是 density 的常规性质，区间概率由积分得到。

例：骰子 ![公式 108](./assets/math/MATH_FOR_AI_RL/math-108.svg)，![公式 109](./assets/math/MATH_FOR_AI_RL/math-109.svg)。若 ![公式 110](./assets/math/MATH_FOR_AI_RL/math-110.svg)，![公式 111](./assets/math/MATH_FOR_AI_RL/math-111.svg) 是 density；![公式 112](./assets/math/MATH_FOR_AI_RL/math-112.svg)。

### 6.2 expectation、variance、covariance

期望是长期平均：![公式 113](./assets/math/MATH_FOR_AI_RL/math-113.svg)。公平骰子的期望是 ![公式 114](./assets/math/MATH_FOR_AI_RL/math-114.svg)，不是某次一定能掷出的点数。

方差衡量围绕期望的波动：![公式 115](./assets/math/MATH_FOR_AI_RL/math-115.svg)。公平硬币取 ![公式 116](./assets/math/MATH_FOR_AI_RL/math-116.svg)，![公式 117](./assets/math/MATH_FOR_AI_RL/math-117.svg)，方差也是 ![公式 118](./assets/math/MATH_FOR_AI_RL/math-118.svg)。

协方差是两个变量是否一起偏离各自均值：

![公式 119](./assets/math/MATH_FOR_AI_RL/math-119.svg)

若 ![公式 120](./assets/math/MATH_FOR_AI_RL/math-120.svg) 且 ![公式 121](./assets/math/MATH_FOR_AI_RL/math-121.svg) 等概率，![公式 122](./assets/math/MATH_FOR_AI_RL/math-122.svg)，协方差为 ![公式 123](./assets/math/MATH_FOR_AI_RL/math-123.svg)，是正相关。协方差零不一般地推出独立。

与 PPO 的连接：目标 ![公式 124](./assets/math/MATH_FOR_AI_RL/math-124.svg) 本身是期望，rollout 只提供它的 sample estimate。critic baseline 不改变 policy-gradient 的期望，却可降低 estimator 的方差；这正是 actor–critic 的统计意义。

### 6.3 条件概率与 Bayes

![公式 125](./assets/math/MATH_FOR_AI_RL/math-125.svg)

例：1% 的门存在某种异常；检测器在异常时报警率 90%，正常时误报率 5%。报警时异常概率：

![公式 126](./assets/math/MATH_FOR_AI_RL/math-126.svg)

这提醒我们不要混淆 ![公式 127](./assets/math/MATH_FOR_AI_RL/math-127.svg) 和 ![公式 128](./assets/math/MATH_FOR_AI_RL/math-128.svg)。在 POMDP 里，LSTM 从 observation history 推断看不见的状态，可以被理解为学习某种隐式 ![公式 129](./assets/math/MATH_FOR_AI_RL/math-129.svg) 的摘要；但实际网络没有显式执行 Bayes filter。

面试自答：

> 问：reward 的 batch mean 是不是“真实期望回报”？
>
> 答：不是，它是有限环境、有限随机种子与有限 horizon 下的估计。增大 rollout 或独立 evaluation 有助于降低估计不确定性，但还要明确初始状态分布和成功定义。

## 7. Gaussian、log probability 与数值稳定

### 7.1 为什么连续动作 policy 常用 Gaussian

一维 Gaussian ![公式 130](./assets/math/MATH_FOR_AI_RL/math-130.svg) 的 density：

![公式 131](./assets/math/MATH_FOR_AI_RL/math-131.svg)

对数概率：

![公式 132](./assets/math/MATH_FOR_AI_RL/math-132.svg)

例：![公式 133](./assets/math/MATH_FOR_AI_RL/math-133.svg)，![公式 134](./assets/math/MATH_FOR_AI_RL/math-134.svg)。若独立的 12 个 action dimension 各有 log-prob，则 joint log-prob 是它们的和；普通 probability 则是它们的乘积。

Actor 输出 mean 与可学习 std 后，训练时采样 ![公式 135](./assets/math/MATH_FOR_AI_RL/math-135.svg)。evaluation 取 mean 并非“更正确的概率”，而是选择无探索噪声的部署约定。

### 7.2 PPO ratio 只需 log-prob 的差

![公式 136](./assets/math/MATH_FOR_AI_RL/math-136.svg)

例：旧 log-prob 为 ![公式 137](./assets/math/MATH_FOR_AI_RL/math-137.svg)，新 log-prob 为 ![公式 138](./assets/math/MATH_FOR_AI_RL/math-138.svg)，则 ![公式 139](./assets/math/MATH_FOR_AI_RL/math-139.svg)：新策略将该 sampled action 的概率提高约 22.1%。若新值为 ![公式 140](./assets/math/MATH_FOR_AI_RL/math-140.svg)，则 ratio 是 ![公式 141](./assets/math/MATH_FOR_AI_RL/math-141.svg)：概率下降约 25.9%。这里无需真的计算两个极小 probability 再相除。

### 7.3 log-sum-exp：小数不该被浮点数吞掉

很小概率相乘会 underflow，所以计算 log-prob 后求和。很大 logit 直接 exponentiate 会 overflow。稳定的恒等式：

![公式 142](./assets/math/MATH_FOR_AI_RL/math-142.svg)

例：![公式 143](./assets/math/MATH_FOR_AI_RL/math-143.svg) 直接算 ![公式 144](./assets/math/MATH_FOR_AI_RL/math-144.svg) 可能 overflow。取 ![公式 145](./assets/math/MATH_FOR_AI_RL/math-145.svg)，结果为 ![公式 146](./assets/math/MATH_FOR_AI_RL/math-146.svg)。softmax 和 categorical log-prob 的实现都会用此技巧。

面试自答：

> 问：PPO 为什么存 `old_log_prob` 而不重新用旧网络跑一次？
>
> 答：rollout 时存下的值是行为策略对实际 sampled action 的精确记录，也避免在更新后依赖可能已变的网络状态。用 log difference 计算 ratio 数值稳定且与概率相除等价。

## 8. entropy、KL 与 PPO 的“别走太远”

### 8.1 entropy：分布本身有多分散

离散 entropy：![公式 147](./assets/math/MATH_FOR_AI_RL/math-147.svg)。二元分布 `[0.5, 0.5]` 的 entropy 是 ![公式 148](./assets/math/MATH_FOR_AI_RL/math-148.svg)，而 `[0.99,0.01]` 约是 ![公式 149](./assets/math/MATH_FOR_AI_RL/math-149.svg)，后者更确定。

Gaussian 的 differential entropy 是 ![公式 150](./assets/math/MATH_FOR_AI_RL/math-150.svg)。一维 ![公式 151](./assets/math/MATH_FOR_AI_RL/math-151.svg) 时约 1.419；![公式 152](./assets/math/MATH_FOR_AI_RL/math-152.svg) 时约 -0.884。连续 entropy 可以为负，不能把它直接当离散“不确定性分数”比较。

PPO loss 常加入 entropy bonus，鼓励训练早期保留探索。但 entropy coefficient 很大时会把 action noise 奖励得比任务 reward 更重要；它是 optimization tradeoff，不是环境 reward。

### 8.2 KL divergence：两个分布不同多少

![公式 153](./assets/math/MATH_FOR_AI_RL/math-153.svg)

它非负，且为零当且仅当两分布相同（几乎处处），但不对称：一般 ![公式 154](./assets/math/MATH_FOR_AI_RL/math-154.svg)。

例：对 Bernoulli，![公式 155](./assets/math/MATH_FOR_AI_RL/math-155.svg)，![公式 156](./assets/math/MATH_FOR_AI_RL/math-156.svg)：

![公式 157](./assets/math/MATH_FOR_AI_RL/math-157.svg)

PPO clip 限制的是 surrogate objective 的可得收益，并**不严格保证** KL 小；实际训练可监控近似 KL，以检测策略是否离 rollout policy 太远。ratio 是单个 sampled action 的概率变化，KL 是分布整体差异，二者相关但不是同一指标。

面试自答：

> 问：entropy 与 KL 都和概率有关，分别回答什么问题？
>
> 答：entropy 问“一个 policy 自己有多随机”；KL 问“新 policy 和旧 policy 相差多大”。PPO 里前者服务探索，后者服务更新幅度诊断。

## 9. sampling、Monte Carlo 与估计的偏差—方差取舍

### 9.1 sampling 与 Monte Carlo estimate

要计算难以解析的期望 ![公式 158](./assets/math/MATH_FOR_AI_RL/math-158.svg)，可以采样 ![公式 159](./assets/math/MATH_FOR_AI_RL/math-159.svg) 次取平均：![公式 160](./assets/math/MATH_FOR_AI_RL/math-160.svg)。

例：从某 reward distribution 获得 `[1, 0, 1, 1, 0]`，sample mean 是 ![公式 161](./assets/math/MATH_FOR_AI_RL/math-161.svg)。这不证明真实成功率正好 60%；再采到 5 次，值会波动。独立样本数增加时，sample mean 通常更稳定。

一个 trajectory 的 Monte Carlo return：![公式 162](./assets/math/MATH_FOR_AI_RL/math-162.svg)。若 rewards 为 `[1, 2, 3]`、![公式 163](./assets/math/MATH_FOR_AI_RL/math-163.svg)，则 ![公式 164](./assets/math/MATH_FOR_AI_RL/math-164.svg)。它不 bootstrap critic，因而在完整 episode 下对真实 return 无偏，但可能方差很大、也必须等到后续 reward 出现。

### 9.2 TD、GAE 的 bias—variance 图景

一步 TD target 是 ![公式 165](./assets/math/MATH_FOR_AI_RL/math-165.svg)。它立刻 bootstrap，方差低，但若 critic 不准就会引入 bias。

例：真实后续 discounted return 是 5，当前 reward 是 1、![公式 166](./assets/math/MATH_FOR_AI_RL/math-166.svg)。若 critic 预测下一状态值为 3，则 TD target 为 3.7，比真实 5 偏低；完整 Monte Carlo 可以得到 5，但若 episode reward 很随机，样本方差更高。

GAE 把多步 TD residual 指数加权：

![公式 167](./assets/math/MATH_FOR_AI_RL/math-167.svg)

当 ![公式 168](./assets/math/MATH_FOR_AI_RL/math-168.svg)，只用一步 TD residual，低方差但更依赖 critic；![公式 169](./assets/math/MATH_FOR_AI_RL/math-169.svg) 时接近长回报，通常低 bias 高方差。以两步例子：![公式 170](./assets/math/MATH_FOR_AI_RL/math-170.svg)，![公式 171](./assets/math/MATH_FOR_AI_RL/math-171.svg)。

与 PPO 的连接：advantage 不需要是“绝对真值”才有用，但它的 bias 和 noise 会改变 policy update。critic value loss、reward scale、done/timeout bootstrap 语义都会进入这个估计器。

面试自答：

> 问：为什么不能简单说“Monte Carlo 一定更好，因为无偏”？
>
> 答：训练要看有限样本下的可用性。高方差梯度会使更新不稳定、样本效率差；TD/GAE 有意用可控 bias 换取更小方差和更快更新。无偏不是唯一目标。

## 10. optimization：从损失到一次参数更新

### 10.1 目标函数与梯度下降

训练不是在寻找“某个神奇网络”，而是在最小化标量 loss。例：![公式 172](./assets/math/MATH_FOR_AI_RL/math-172.svg)，梯度是 ![公式 173](./assets/math/MATH_FOR_AI_RL/math-173.svg)。从 ![公式 174](./assets/math/MATH_FOR_AI_RL/math-174.svg) 出发、learning rate ![公式 175](./assets/math/MATH_FOR_AI_RL/math-175.svg)：

![公式 176](./assets/math/MATH_FOR_AI_RL/math-176.svg)

新的 loss 从 9 降为 ![公式 177](./assets/math/MATH_FOR_AI_RL/math-177.svg)。学习率太大（例如 2）会从 0 跳到 12，loss 变为 81，发生 overshoot。

PPO 实际会组合 policy surrogate loss、value loss 和 entropy term，按 batch mean 后交给 Adam。每个 term 的符号与 coefficient 都是目标定义的一部分；例如“最大化 entropy bonus”在用 gradient descent 写 loss 时表现为减去 entropy。

### 10.2 convex 直觉与神经网络现实

凸函数满足任意两点连线在函数图像上方；直觉是一个碗形地形，没有糟糕的局部盆地。![公式 178](./assets/math/MATH_FOR_AI_RL/math-178.svg) 是凸的，局部最小就是全局最小。

深度网络与 PPO 的目标通常非凸：网络层、recurrent dynamics、sampling、clip 都引入复杂地形。因此不能承诺“梯度下降一定到全局最优”。但局部梯度仍是高维参数空间中实用的改进方向，Adam、normalization、合理 batch 和学习率调度共同改善可训练性。

### 10.3 Adam 的直觉（不必背完整推导）

SGD 只用当前 gradient；Adam 同时维护 gradient 的滑动均值与平方的滑动均值，相当于按各参数近期的典型尺度做自适应步长。它不是自动修复错误 reward、错位 observation 或错误 done mask 的工具；那些会让它稳定地优化错误目标。

面试自答：

> 问：PPO 有 clip，是否就不需要关心 learning rate？
>
> 答：仍需关心。clip 只改变 surrogate 的一部分梯度收益，过大的 optimizer step 仍可造成大 KL、value 破坏或不稳定；clip 是近似 trust-region 机制，不是完整的步长保证。

## 11. constraints 与 Lagrange：把“必须满足”写进优化问题

无约束优化写作 ![公式 179](./assets/math/MATH_FOR_AI_RL/math-179.svg)。若必须满足 ![公式 180](./assets/math/MATH_FOR_AI_RL/math-180.svg)，构造 Lagrangian：

![公式 181](./assets/math/MATH_FOR_AI_RL/math-181.svg)

例：在 ![公式 182](./assets/math/MATH_FOR_AI_RL/math-182.svg) 下最小化 ![公式 183](./assets/math/MATH_FOR_AI_RL/math-183.svg)。

![公式 184](./assets/math/MATH_FOR_AI_RL/math-184.svg)

令偏导为零：![公式 185](./assets/math/MATH_FOR_AI_RL/math-185.svg)，得到 ![公式 186](./assets/math/MATH_FOR_AI_RL/math-186.svg)。约束把原本“各自趋向 0”的最优点排除掉了。

不等式约束（如 action 限制、力限制）更严格地涉及 KKT 条件与互补松弛；面试中知道它们表达“约束未激活时 multiplier 为零，激活时会影响最优条件”即可。工程上 action clamp、joint limit 或 safety monitor 是系统约束；不能仅因 PPO loss 加了 penalty 就宣称它有硬约束保证。

与 RL 的连接：PPO 的 clip 不是传统意义对参数的硬 constraint，而是改写目标函数以削弱过度改变 action probability 的收益。真正的 constrained RL 会把期望 cost 约束（例如 ![公式 187](./assets/math/MATH_FOR_AI_RL/math-187.svg)）作为独立对象，并可能学习 Lagrange multiplier；DoorDog 的 simulation reward/termination 也不能自动给出 hardware safety guarantee。

面试自答：

> 问：reward penalty 与 hard constraint 的区别？
>
> 答：penalty 允许违约，只是让违约在优化中更贵，权重不当仍可违约；hard constraint 把可行域直接缩小。把力 penalty 调大不等于证明机器人永不会超过力限。

## 12. 把这套数学接回一次 DoorDog PPO update

拿 rollout 的一个时间步和一个环境为例：actor 从 133D vector 得到 LSTM hidden，再经 MLP 得到 12D Gaussian mean；采样的 12D action 与 `old_log_prob` 一起被存入 buffer。environment 将它纳入控制合同，返回 ![公式 188](./assets/math/MATH_FOR_AI_RL/math-188.svg)、`done`、下一 observation；critic 产生 ![公式 189](./assets/math/MATH_FOR_AI_RL/math-189.svg)。

反向扫描时，若 ![公式 190](./assets/math/MATH_FOR_AI_RL/math-190.svg)，则：

![公式 191](./assets/math/MATH_FOR_AI_RL/math-191.svg)

再把未来 residual 按 ![公式 192](./assets/math/MATH_FOR_AI_RL/math-192.svg) 加入，得到 advantage。假设这个 action 的新旧 joint log-prob 分别为 ![公式 193](./assets/math/MATH_FOR_AI_RL/math-193.svg)，则 ratio ![公式 194](./assets/math/MATH_FOR_AI_RL/math-194.svg)。若 advantage ![公式 195](./assets/math/MATH_FOR_AI_RL/math-195.svg)、![公式 196](./assets/math/MATH_FOR_AI_RL/math-196.svg)，未裁剪目标是 ![公式 197](./assets/math/MATH_FOR_AI_RL/math-197.svg)，裁剪目标是 ![公式 198](./assets/math/MATH_FOR_AI_RL/math-198.svg)，取较小者 2.4：正 advantage 的“继续增大该动作概率”收益被截住。

若 ![公式 199](./assets/math/MATH_FOR_AI_RL/math-199.svg)，未裁剪项是 ![公式 200](./assets/math/MATH_FOR_AI_RL/math-200.svg)，裁剪项是 ![公式 201](./assets/math/MATH_FOR_AI_RL/math-201.svg)，`min` 选 ![公式 202](./assets/math/MATH_FOR_AI_RL/math-202.svg)。最大化此目标时，它比 ![公式 203](./assets/math/MATH_FOR_AI_RL/math-203.svg) 更不利，因而避免 policy 通过让 ratio 过高来逃避负 advantage 的约束。实现时常把最大化目标取负写成要最小化的 policy loss。

这条链同时包含：tensor shape 与 reduction、Gaussian log-prob、expectation 的采样估计、TD/GAE 的 credit assignment、PPO clip 的局部更新约束、autograd 对网络参数的 chain rule。把它讲顺，比孤立背公式更能应对追问。

## 13. 12 题闭卷口述检查

1. `B×133` observation 经过 `nn.Linear(133,512)` 后 shape 是什么，为什么？
   - `(B,512)`；每一行是一个环境，133 个 feature 与每个 output neuron 的 133 个权重做 dot product。
2. 点积、elementwise product、matrix product 有何区别？
   - dot product 把两个同长度 vector reduce 成 scalar；elementwise 保持 shape；matrix product 按行列做多个 dot product 并改变最后两维。
3. 为什么 gradient direction 是局部最陡上升？
   - 一阶近似 ![公式 204](./assets/math/MATH_FOR_AI_RL/math-204.svg)，固定 ![公式 205](./assets/math/MATH_FOR_AI_RL/math-205.svg) 时 Cauchy–Schwarz 表明与 gradient 同向的内积最大。
4. 一个 Jacobian 的行和列各代表什么？
   - 行对应 output 分量，列对应 input 分量；元素是一个 output 对一个 input 的偏导。
5. LSTM 的 ![公式 206](./assets/math/MATH_FOR_AI_RL/math-206.svg) 与 ![公式 207](./assets/math/MATH_FOR_AI_RL/math-207.svg) 分别是什么？
   - cell 是内部长期记忆通道，hidden 是对外读出的、受 output gate 控制的状态；都应在 episode boundary 正确处理。
6. expectation 与 sample mean 的关系？
   - expectation 是分布的理论平均，sample mean 是有限样本的估计，后者会有随机误差。
7. 为什么连续动作的“某个精确 action 的概率”不直接当作普通概率？
   - 连续点概率为零；网络使用 density 和 log density，区间概率才是积分得到的 probability。
8. `new_logp-old_logp` 为何能变 PPO ratio？
   - ![公式 208](./assets/math/MATH_FOR_AI_RL/math-208.svg)，避免很小概率直接相除。
9. entropy bonus 与 KL monitor 分别防止什么？
   - entropy 防止过早失去探索；KL monitor 检查新旧策略整体偏移是否太大。
10. MC、TD 与 GAE 的核心取舍？
   - MC 少 bootstrap bias 但方差大；TD 方差低但依赖 critic；GAE 由 ![公式 209](./assets/math/MATH_FOR_AI_RL/math-209.svg) 连续折中。
11. PPO clip 是不是 action clip？
   - 不是。它裁的是 probability ratio 在 surrogate objective 中的有效范围；action range 是环境/分布参数化的另一层问题。
12. reward penalty 能否证明硬件安全？
   - 不能。它只修改仿真中的优化偏好；硬约束、系统级监控和 hardware evidence 是不同层次。

## 14. 面试时不应混淆的词

| 容易混淆 | 正确区分 |
|---|---|
| reward / return / advantage | reward 是一步信号；return 是折扣累计；advantage 是该 action 相对 value baseline 的好坏。 |
| probability / density / log-prob | 离散 action 可谈具体概率；连续 action 用 density；log-prob 是稳定的训练计算形式。 |
| batch dimension / time dimension | batch 可并行独立处理；time 对 LSTM 有因果顺序，不能任意打散。 |
| policy mean / sampled action | mean 是分布中心；训练 sampled action 产生探索并决定 rollout data。 |
| PPO ratio / KL | ratio 是样本 action 的概率变化；KL 是两个完整分布的平均差异。 |
| clip / constraint | PPO clip 是目标函数的局部饱和；它不是保证任何物理量不越界的硬约束。 |
| source-inspected 公式 / runtime 结论 | 公式和配置可由源码核对；训练是否成功、是否安全必须有对应 runtime、experiment 或 hardware 证据。 |

下一步：在掌握本文后，回到 [`PPO_LSTM_DEEP_DIVE.md`](./PPO_LSTM_DEEP_DIVE.md) 将抽象公式对照当前实现，再用 [`INTERVIEW_CHEATSHEET.md`](./INTERVIEW_CHEATSHEET.md) 的闭卷题做 60 秒口述。
