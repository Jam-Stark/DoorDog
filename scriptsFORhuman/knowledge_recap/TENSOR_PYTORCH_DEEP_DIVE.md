# Tensor / PyTorch：从“能跑”到能在白板上讲清

这不是一份 PyTorch API 字典。目标是建立一套判断法：**先说每个 axis 代表谁，再说变换是否保留这个语义，最后才写算子。** 在 DoorDog 中，shape 不是装饰；它是 policy、rollout、LSTM、controller 之间的运行合同。

## 0. 30 秒总图：数值如何流动

```text
N=4096 parallel envs

obs[T,N,D]  ── policy / value ──>  action[T,N,12]
       │                                  │
       └──── rollout storage <──── env.step / reward / done

actor:  [N,133] ──> [N,12] high-level action
critic: [N,138] ──> [N,1]  value
A2_Base:[N,30,54] -> flatten [N,1620] -> [N,12] locomotion action
concat: [N,12] + [N,12] -> [N,24] env action -> mapped to [N,20] simulator command
```

这里的 `N` 是并行环境数量，`T` 是 rollout 或 sequence 的时间长度，`D` 是 feature dimension。遇到 `[T,N,D]`，不要只说“三维张量”；应说“第 `t` 步、environment `n` 的 `D` 维 feature”。

## 1. 从 scalar 到 tensor：不是类型层级，而是 axis 语义

| 名称 | 例子 | DoorDog 里的直觉 |
|---|---|---|
| scalar / 0-D tensor | `r_t` | 一个 env 在一个 control step 的 reward |
| vector / 1-D | `[12]` | 一台 robot 的 12D high-level action |
| matrix / 2-D | `[N,133]` | 每个并行环境一行 actor observation |
| 3-D tensor | `[T,N,133]` | rollout 中所有时刻、所有环境的 actor observation |
| 更高维 | `[N,C,H,W]` | batch 图像；CNN 常用 channel-first |

“tensor”在 PyTorch 中基本就是带有 `shape`、`dtype`、`device` 和可能的 gradient history 的多维数组。其 rank（`ndim`）只说有几条轴，**并不告诉你轴的含义**。`[4096,133]` 与 `[133,4096]` 都是 2-D，却一个是 batch-major observation，另一个通常已经违反网络输入合同。

最实用的白板注释方式：

```python
actor_obs: torch.Tensor  # [N, 133], float32, cuda
done:      torch.Tensor  # [N], bool
values:    torch.Tensor  # [T, N, 1] or [T, N], float32
```

在写出每个 axis 含义前，不要调用 `reshape`、`mean` 或高级 indexing。

## 2. Shape、axis 与 memory layout：同一个数可以有不同视图

### 2.1 `reshape`、`view`、`flatten`

`x.reshape(new_shape)` 改变你如何分组元素，元素总数必须相同。比如 A2_Base 的一帧是 `54D`，30 帧历史可以是：

```python
history = torch.empty(N, 30, 54)       # [N, frame, features]
flat = history.reshape(N, 30 * 54)     # [N, 1620]
```

这一步仅在 policy metadata 约定的顺序是“30 个连续的 54D frames”时语义正确。若 `history` 实际是 `[N,54,30]`，直接 `reshape(N,1620)` 虽然不报错，但 feature 顺序已错，等价于把时间与 feature 交错喂给网络。

`view` 的语义近似 `reshape`，但要求底层 stride/layout 能直接解释成目标 shape；经 `transpose` 或某些 slicing 后它经常失败。教学和一般业务代码优先 `reshape`；需要保证不复制、且你理解 contiguous layout 时再用 `view`。

`flatten(start_dim=1)` 是更清楚的写法：它保留 batch axis，将其后的 axes 合并。

```python
flat = history.flatten(start_dim=1)    # [N, 1620]
```

### 2.2 `transpose` 与 `permute`：移动轴，不是重排数值序列

```python
rollout = torch.empty(T, N, 133)       # time-major storage
env_major = rollout.transpose(0, 1)    # [N, T, 133]
image = torch.empty(N, H, W, C)
nchw = image.permute(0, 3, 1, 2)       # [N, C, H, W]
```

`transpose(0,1)` 只交换两条轴；`permute` 指定所有轴的新顺序。两者通常返回同一底层 storage 的 non-contiguous view。之后若某段 kernel/API 要求连续内存，用 `x.contiguous()` 显式建立连续拷贝；不要凭习惯到处插入它。

一个容易混淆的对比：

```python
x.reshape(N, T, D)        # 不移动轴，只重新切分线性元素
x.permute(1, 0, 2)        # 轴语义从 [N,T,D] 改为 [T,N,D]
```

`reshape` 回答“怎么分组”，`permute` 回答“哪条轴放在哪里”。

## 3. Broadcasting：没有复制的“逐轴对齐”

PyTorch 从**尾部**对齐 shapes。每一对维度必须相等，或其中一个为 `1`；缺失的前导维度视为 `1`。

```python
obs = torch.empty(N, 133)          # [N, D]
mean = obs.mean(dim=0)              # [D]
std = obs.std(dim=0)                # [D]
normalized = (obs - mean) / std     # [N,D] - [D] -> [N,D]

reward = torch.empty(N)             # [N]
weight = torch.tensor(0.1)          # []
scaled = reward * weight            # [N] * [] -> [N]
```

这不是把 `mean` 真复制成 `N` 行；多数算子以 stride-0 的方式逻辑扩展它。显式 `expand` 也通常只是 view，`repeat` 才会物理复制。除非下游确实要独立存储，不要用 `repeat` 模拟 broadcasting。

最高频的 bug 是 `[N]` 与 `[N,1]`：

```python
adv = torch.empty(N)                # [N]
value = torch.empty(N, 1)           # [N,1]
bad = adv - value                   # [N,N]，通常不是你想要的
good = adv.unsqueeze(-1) - value    # [N,1]
```

在 loss 前用 `assert tensor.shape == expected` 或打印 shape；不要依赖“能 broadcast 就一定正确”。

## 4. Reduction：消掉哪条轴，决定你在统计什么

```python
rewards = torch.empty(T, N)          # 每个 step / env 的 reward
per_env_return = rewards.sum(dim=0)  # [N]，沿时间累计
mean_reward_at_t = rewards.mean(1)   # [T]，同一时刻跨 env 平均
global_mean = rewards.mean()         # []，一个 scalar
```

`dim` 是被**消掉**的 axis。记不住时，先用自然语言说“我要保留每个环境，只对时间加总”，答案就是 `dim=0`。

`keepdim=True` 会保留长度为 1 的轴，常用于让后续 broadcasting 意图明确：

```python
mean = obs.mean(dim=-1, keepdim=True)   # [N,1]
centered = obs - mean                   # [N,133]
```

PPO 中 advantage normalization 通常是对当前训练 batch 的所有有效 samples 求全局 mean/std；如果是 recurrent padded batch，先用 mask 取出有效位置，不能把 padding 的零混入统计。

## 5. 选择数据：slice、boolean mask、`index_select`、`gather`

它们解决的都是“从哪里取”，区别是索引是否随样本变化。

```python
# 规则一：相同位置 / 连续范围
high_action = action[:, :12]              # [N,24] -> [N,12]

# 规则二：每个 batch 共用同一组 index
arm_ids = torch.tensor([5, 6, 7, 8, 9, 10], device=obs.device)
arm = torch.index_select(obs, dim=1, index=arm_ids)  # [N,6]

# 规则三：每个 batch row 自己选择不同 feature
scores = torch.empty(N, K)                # [N,K]
choice = torch.empty(N, dtype=torch.long) # [N], each in [0,K)
chosen = scores.gather(1, choice[:, None]).squeeze(1)  # [N]
```

`gather(dim, index)` 的 `index` 形状决定输出形状；index 必须是 integer (`torch.long`) 且在对应轴的合法范围内。用在 Q-learning 时，`q_values.gather(1, actions[:,None])` 是“每条 transition 取它实际执行 action 的 Q 值”。PPO 连续动作通常不需要这一步，因为它直接计算该 sampled action 在 Gaussian 下的 log probability。

boolean mask 更适合“保留有效 token/trajectory”：

```python
loss_per_step = torch.empty(B, L)     # padded sequences
mask = torch.empty(B, L, dtype=torch.bool)
loss = loss_per_step[mask].mean()     # 只对真实时间步求 mean
```

`x[mask]` 会压平被选取的 axes；如果你还需要 sequence 结构，不要早早用它，而是 `masked_fill` 或将 mask 作为加权分母的一部分。

## 6. 组合数据：`cat` 与 `stack` 从问题语义区分

`torch.cat` 沿一个**已有轴**拼接，其他轴必须一致：

```python
teacher_high = torch.empty(N, 12)
legs = torch.empty(N, 12)
env_action = torch.cat([teacher_high, legs], dim=-1)   # [N,24]
```

DoorDog 训练链里，high-level 12D 与 frozen A2_Base 的 leg 12D 由此成为 env 的 24D action；env 再按 robot 关节/action layout 处理成 20D simulator command。`cat(..., dim=0)` 则是把两个 batch 叠成更大的 batch，而不是拼 feature。

`torch.stack` 新建一个轴，所有输入 shape 必须完全相同：

```python
frames = [torch.empty(N, 54) for _ in range(30)]
history = torch.stack(frames, dim=1)                      # [N,30,54]
```

一句面试记忆法：**已有维度上接起来用 cat；要表达“这是第几个样本/时刻”的新维度用 stack。**

## 7. dtype 与 device：数据“是什么”和“在哪里”同样是合同

常见 dtype：

| 数据 | 合理 dtype | 原因 |
|---|---|---|
| observation、action、network weight、loss | `float32`（或训练策略明确的 mixed precision） | 浮点计算与反向传播 |
| action / joint index | `torch.long` | `gather`、embedding、advanced index 要整数 index |
| `done`、trajectory validity | `torch.bool` | 表示逻辑状态 |
| image 原始像素 | 常见 `uint8`，进入网络前转 float/normalize | 节省传输/存储但卷积输入通常是 float |

`device` 必须一致：CPU tensor 和 CUDA tensor 不能直接相加。新建常量/临时 tensor 时最安全的是跟随现有 tensor：

```python
zero = torch.zeros_like(value)
ids = torch.arange(12, device=action.device, dtype=torch.long)
threshold = action.new_tensor(0.2)
```

不要在每个 control step 写 `torch.tensor([...]).cuda()`；这容易产生 CPU→GPU 同步和隐式分配。Device mismatch 和 dtype mismatch 应直接暴露：它们通常表明调用链合同已断。

## 8. Autograd：计算图如何把 loss 连到参数

当 `requires_grad=True` 的 parameter 参与计算，PyTorch 会记录可微操作形成计算图：

```text
obs -> actor(theta) -> mean/logprob -> policy_loss -> backward()
                                                  \-> theta.grad -> optimizer.step()
```

`loss.backward()` 根据 chain rule 在图上反向累积梯度；`optimizer.step()` 才读取 `.grad` 并更新参数。训练循环通常先 `optimizer.zero_grad()`，否则梯度会跨 minibatch 累积。

```python
prediction = model(obs)
loss = (prediction - target).square().mean()
optimizer.zero_grad()
loss.backward()
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
optimizer.step()
```

### `detach()`、`no_grad()` 和 PPO 的 old policy

- `x.detach()`：得到共享数值但从当前 autograd history 切开的 tensor。GAE/rollout 中存的 old logprob、old value、old action distribution 参数不能随 PPO update 获得新梯度。
- `with torch.no_grad():`：块内完全不记录图，适合 rollout inference、evaluation、target construction。DoorDog rollout 收集是 no-grad，minibatch forward/loss 才需要 graph。
- `model.eval()`：改变 dropout/batchnorm 行为，**不等于**关掉 autograd；它和 `no_grad` 解决不同问题。

一个典型的 PPO boundary：`π_old` 的 log probability 是采样时固定的行为策略记录；只有再经当前 `π_θ` forward 得到的 `new_logprob` 应参与梯度。若不 detach/不切断 rollout graph，会让 update 反传到旧 rollout 计算，既浪费显存又错过 on-policy 的“旧策略固定”语义。

### in-place 的风险

`x.add_(...)`、`x[:, 0] = ...` 等 in-place 操作直接改 storage。它们并非一律禁止，但如果 autograd 为 backward 保存了该 tensor 的旧值，后续可能报错，或在 alias/view 场景中产生难查的语义错误。

```python
# 更容易审计
next_hidden = hidden * (1.0 - done.float().view(1, N, 1))

# 只有明确知道该 buffer 不再被当前图需要时，才考虑原地 reset
```

RL loop 尤其要小心：buffer 常被多个 view、rollout storage 与 recurrent state 共享。面对“one of the variables needed for gradient computation has been modified in-place”，优先追踪谁保存了图中 tensor；不要用 `.data`、`retain_graph=True` 或 broad `detach` 掩盖问题。

## 9. Mask、padding 与 recurrent training：零不是“无数据”的天然标志

并行环境会在不同时间 `done`。recurrent PPO 需要把 `[T,N,D]` 依照 episode boundary 切成多条 `[L_i,D]` trajectory，再 padding 成相同 `L_max` 才能批处理。

```text
valid trajectory:  [o0, o1, o2]             length 3
short trajectory:  [o0, o1, PAD]            length 2
mask:               [ 1,  1,   0]
```

padding value 常是 0，但 observation 中合法 feature 也可能正好是 0。因此 mask 才是权威语义。masked average 应使用真实 token 数：

```python
masked_sum = (per_step_loss * mask).sum()
loss = masked_sum / mask.sum().clamp_min(1)
```

上面 `clamp_min(1)` 只用于定义空 reduction 的数值；正常训练 batch 不应出现全空 sequence。若它出现，应该检查 trajectory slicing/minibatch generation，而不是把它当可接受 fallback。

LSTM 的 initial hidden state 必须对应**该 trajectory 的第一个真实 step**；done 后仅 reset 对应 env 的 hidden state。否则 history 会跨 episode 泄漏。训练结束或 truncated BPTT 边界 detach hidden state，避免图无限向过去增长。

## 10. DoorDog shape walkthrough：每一箭头都应能报出 shape

当前 Teacher / A2_Base 主要合同可在白板上写成：

```text
Teacher actor observation     actor_obs       [N,133]
Teacher critic observation    critic_obs      [N,138]
  └─ critic extra five scalar timing/transition signals

Teacher recurrent actor       [N,133] + h,c  -> high action [N,12]
Teacher recurrent critic      [N,138] + h,c  -> value       [N,1]

A2_Base history frames        [N,30,54]
flatten according to metadata  [N,1620]
frozen A2_Base                 [N,1620] -> leg action [N,12]

compose                         cat(-1): [N,12] + [N,12] -> [N,24]
environment adapter/layout                                 -> [N,20]
Isaac/PhysX target write                                     per robot
```

`133` 与 `138` 不是“模型输入大小的两个超参数”。它们是两份不同 observation contract：actor 部署时只能依赖 133D，critic 训练时额外看到 transition、complete、`time_in_stage`、`actual_time_in_stage`、`total_time` 这 5D 辅助信息，形成 asymmetric actor–critic。把 `[N,133]` 随意 pad 成 `[N,138]` 或从 critic input 切掉最后五维后复用，都应视为接口改动，而不是张量技巧。

recurrent rollout storage 通常是 time-major，便于按 control step 写入：

```text
actor_obs storage    [T,N,133]
actions              [T,N,12]
rewards/dones        [T,N]
values/logprob       [T,N] (或保留尾部 singleton 的 [T,N,1])
```

进入 sequence minibatch 时，常转换成 `[N,T,D]` 或按 done 重组为 `[B,L,D]`。这不是为了“让它看起来像 batch first”，而是为了把同一 trajectory 的时间相邻样本和正确 initial hidden state 一起送进 LSTM。

## 11. 面试里的常见追问：不要只背结论

### 问：为什么 `mean(dim=0)` 和 `mean(dim=1)` 都不报错，却有一个可能错？

答：shape checking 只检查可执行性，不检查语义。对于 `[T,N]` rewards，`dim=0` 保留每个 env，得到每条 rollout trajectory 的时间平均；`dim=1` 保留每个 time step，得到并行 env 平均。要先说要保留谁。

### 问：为什么 `[N] - [N,1]` 会产生 `[N,N]`？

答：broadcast 从尾部对齐。`[N]` 被看作 `[1,N]`，与 `[N,1]` 合成 `[N,N]`。它没有错误，因为数学上每对行/列都能相减；但它几乎肯定不是每个 env 的一对一 value/advantage 计算。

### 问：`cat` 和 `stack` 什么时候容易用反？

答：高层 action 与 leg action 已经各有 feature axis，拼成更长 action 用 `cat(dim=-1)`；30 个 `54D` history frame 原来没有“time axis”，需要用 `stack(dim=1)` 新建该 axis。判断标准是“这个维度在输入中是否已经存在”。

### 问：为什么 rollout 用 `no_grad`，但 PPO 更新不能？

答：rollout 的 job 是采集固定行为策略的数据、存 old logprob/value，不优化它们；PPO update 必须对 current policy 的 new logprob、value、entropy 反传到参数。把整个 PPO update 放进 `no_grad` 会得到没有 `grad_fn` 的 loss。

### 问：为什么 masked loss 的分母不能是 `B*L`？

答：那会让短 trajectory 的 padding 稀释 loss/gradient，batch composition 改变有效样本权重。应除以 `mask.sum()`，只按真实 time step 平均。

## 12. 60 秒自测

1. 用一句话解释 `[T,N,D]` 三条轴各自代表什么，并写出转成 `[N,T,D]` 的表达式。
2. `x=[N,30,54]` 为什么 `flatten(start_dim=1)` 是 `[N,1620]`？什么情况下它的 feature order 仍可能错？
3. `torch.cat([a,b],dim=-1)` 与 `torch.stack([a,b],dim=-1)` 的结果 shape 分别是什么，若 `a,b` 都是 `[N,12]`？
4. `[N]` 和 `[N,1]` 能否一对一相减？正确写法是什么？
5. `index_select` 和 `gather` 分别适合“所有 batch 同一组 feature”还是“每一行不同 index”？
6. `detach`、`no_grad`、`eval()` 各自在切断什么？
7. 为什么 `done` 后 LSTM hidden state 需要按 environment mask reset，而不是清掉所有 `N` 个 env？
8. 说出 `133 -> 12`、`138 -> 1`、`30×54 -> 1620 -> 12`、`12+12 -> 24 -> 20` 各自对应什么模块。

## 13. 真实 source 锚点与证据边界

以下是当前 worktree 的 **INSPECTED** source anchors，不是 runtime benchmark 声明：

- `gr00t/rl/envs/base_task/a2_base.py::_get_a2_base_obs_frame` 与 `_get_obs_a2_base_obs`：A2_Base history construction；
- `gr00t/rl/trl/trainer/ppo_trainer.py::_compute_returns` 与 `_compute_ppo_loss`：rollout return / PPO loss；
- `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py`：high-level 与 A2_Base action composition；
- `gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py`：Student/Teacher branch 中同样的 12D + 12D composition；
- `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml`：`base_command_dim=5`、`manipulation_action_dim=7`，合计 high-level 12D；
- `gr00t/rl/config/simulator/isaacsim.yaml`：control decimation 4。

面试回答应把“我从 source 读到的接口”与“我亲自跑出的训练/实验结果”分开。张量合同可以从 source 讲清；它不自动证明某个 checkpoint 的策略质量。
