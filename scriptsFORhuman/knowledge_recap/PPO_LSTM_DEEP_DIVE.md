# PPO + LSTM 深挖：从一条 trajectory 到一次参数更新

这份材料只解决六件事：

1. LSTM 到底记了什么；
2. 为什么 recurrent rollout 不能随便打散；
3. TD residual 在比较什么；
4. GAE 为什么从后往前算；
5. PPO ratio 为什么是概率比；
6. clipped objective 在 `A>0` 和 `A<0` 时分别限制什么。

项目锚点使用当前 `door_open_a2_base_lstm` experiment overlay：

```text
4096 envs
64 control steps / rollout
gamma = 0.9975
lambda = 0.985
5 PPO epochs
4 minibatches
clip epsilon = 0.2
actor LSTM = 2 layers x 256 hidden
critic LSTM = 2 layers x 256 hidden
```

证据等级：本材料对当前 source/config 的陈述为 `INSPECTED`，不因此产生新的训练或策略质量结论。

---

## 1. 先固定一条主线

不要把 PPO、GAE 和 LSTM 当成三个孤立算法。它们在一次训练 iteration 中按下面的顺序工作：

```text
LSTM actor 根据历史产生动作分布
        ↓
从旧策略采样 action，Isaac 返回 reward / done / next observation
        ↓
critic 给每个时刻估计 V_t
        ↓
TD residual 衡量每一步“价值预测意外”
        ↓
GAE 从后往前累积这些意外，得到 advantage
        ↓
PPO 用 new/old action probability ratio 更新 actor
        ↓
clip 限制一次更新从旧策略偏离过远
```

一句话记忆：

- LSTM 负责“我到这里之前经历了什么”；
- critic 负责“从这里往后大概还能拿多少回报”；
- TD residual 负责“这一步之后，结果比预测好还是差”；
- GAE 负责“把后面的惊喜或失望分给前面的动作”；
- PPO ratio 负责“新策略对旧动作的态度改变了多少”；
- clip 负责“有收益也别一步改得太猛”。

---

## 2. LSTM：它不是长期数据库，而是可学习的时序状态

### 2.1 为什么普通 MLP 不够

MLP 每一步只计算：

![公式 001](./assets/math/PPO_LSTM_DEEP_DIVE/math-001.svg)

相同的 `o_t` 永远产生相同的输出。可是开门中，相似的当前 pose 可能处在不同上下文：

- 刚接触把手，还是已经稳定夹持 5 个 control steps；
- 相机画面是刚更新的，还是缓存了几十毫秒；
- 机械臂正在接近，还是接触后被弹开；
- 当前 door angle 相近，但运动方向不同。

recurrent policy 计算：

![公式 002](./assets/math/PPO_LSTM_DEEP_DIVE/math-002.svg)

因此相同的当前 observation，可以因为过去不同而产生不同 action。

### 2.2 LSTM 的两个状态

标准 LSTM 有：

- `c_t`：cell state，较长时程的信息通道；
- `h_t`：hidden state，当前对外输出的时序表示。

一组常见写法：

![公式 003](./assets/math/PPO_LSTM_DEEP_DIVE/math-003.svg)

![公式 004](./assets/math/PPO_LSTM_DEEP_DIVE/math-004.svg)

![公式 005](./assets/math/PPO_LSTM_DEEP_DIVE/math-005.svg)

![公式 006](./assets/math/PPO_LSTM_DEEP_DIVE/math-006.svg)

![公式 007](./assets/math/PPO_LSTM_DEEP_DIVE/math-007.svg)

![公式 008](./assets/math/PPO_LSTM_DEEP_DIVE/math-008.svg)

直觉：

- forget gate `f_t`：旧记忆保留多少；
- input gate `i_t`：新候选信息写入多少；
- cell `c_t`：保留后的旧信息加写入的新信息；
- output gate：当前暴露多少 cell 内容成为 `h_t`。

这些 gate 不是人工写成“记住接触”“忘掉相机”。训练只通过最终 PPO/BC loss 学到有用的时序压缩。

### 2.3 当前 DoorDog Teacher 的 shape

rollout 的单步输入：

```text
actor observation: [N, 133]
N = 4096 parallel envs
```

两层 LSTM hidden size 256：

```text
h, c: [num_layers=2, N=4096, hidden=256]
LSTM output: [N, 256]
MLP: 256 -> 512 -> 256 -> 128 -> 12D action mean
```

critic 是独立网络：

```text
critic observation: [N, 138]
critic LSTM: 2 x 256
critic MLP: 256 -> 512 -> 256 -> 128 -> 1 value
```

actor 和 critic 不共享 `h/c`。actor 的历史用于决策，critic 的历史用于 value estimation。

### 2.4 Rollout mode 与 training mode 为什么不同

Rollout 时按真实时间顺序逐步调用：

```text
o_0 + (h_-1,c_-1) -> h_0,c_0 -> action_0
o_1 + (h_0,c_0)   -> h_1,c_1 -> action_1
...
```

训练时，rollout 已经存在于 buffer。为了并行反向传播，需要把它重新组织成 trajectory batch：

```text
[N, T, obs_dim]
    ↓ 按 done 切段
[num_trajectories, max_length, obs_dim]
    ↓ 短轨迹 padding + mask
LSTM sequence training
```

不能把所有 `[N×T]` timestep 随机洗牌后逐点训练，否则某个 `o_t` 会配上错误的 `h_{t-1}`。

### 2.5 done 为什么必须 reset hidden state

假设 env 17 在 `t=23` 完成 episode，`t=24` 返回新 episode 首帧：

```text
错误：new door o_24 + old door h_23
正确：new door o_24 + zero h/c
```

否则上一扇门、上一条轨迹的隐状态泄漏到新 episode，policy 实际面对的就不是配置定义的 MDP/POMDP。

项目在 `_process_env_step()` 中根据 `dones` reset actor/critic memory；训练前还按 done split/pad trajectories。

### 2.6 padding mask 解决什么

两条 trajectory：

```text
trajectory A: 6 steps
trajectory B: 3 steps
```

为了组成一个矩形 batch，会把 B padding 到 6：

```text
A: [real, real, real, real, real, real]
B: [real, real, real, pad,  pad,  pad ]
```

mask 告诉 loss：后三格只是形状填充，不是环境 transition。没有 mask，网络会把虚构的 padding 当训练样本。

### 2.7 detach hidden state 解决什么

rollout 结束后 detach hidden state，切断 autograd graph：

```text
rollout k graph  X  rollout k+1 graph
```

这叫 truncated backpropagation through time。hidden 数值可以继续作为时序状态，但 gradient 不无限反传穿过所有历史 rollout。

---

## 3. Reward、Return、Value、Advantage 先分清

### Reward

环境当前一步直接给出的标量：

![公式 009](./assets/math/PPO_LSTM_DEEP_DIVE/math-009.svg)

### Return

从当前时刻开始的折扣累计 reward：

![公式 010](./assets/math/PPO_LSTM_DEEP_DIVE/math-010.svg)

### Value

critic 对 return 的预测：

![公式 011](./assets/math/PPO_LSTM_DEEP_DIVE/math-011.svg)

### Advantage

当前 action 的结果相对 baseline 好多少：

![公式 012](./assets/math/PPO_LSTM_DEEP_DIVE/math-012.svg)

因此：

- reward 是当前计分；
- return 是后续总账；
- value 是总账预测；
- advantage 是“采取这个 action 后，相对原预测的超额表现”。

---

## 4. TD residual：一步之后，critic 的预测被打脸多少

### 4.1 公式

![公式 013](./assets/math/PPO_LSTM_DEEP_DIVE/math-013.svg)

拆开看：

```text
r_t + gamma * V_{t+1}   = 走完这一步后看到的“新目标”
V_t                     = 走这一步前 critic 的旧预测
delta_t                 = 新目标 - 旧预测
```

如果 `δ_t > 0`，说明这一 transition 比 critic 预期好；如果 `δ_t < 0`，说明比预期差。

### 4.2 为什么 terminal 要乘 `(1-d_t)`

真正 terminal 后没有同一 episode 的 future value：

![公式 014](./assets/math/PPO_LSTM_DEEP_DIVE/math-014.svg)

不能把 reset 后新 episode 的 `V_{t+1}` 接到旧 episode 上。

### 4.3 timeout 与真正 terminal

time-limit truncation 只是采样窗口结束，不一定是物理终态。项目单独保存 `time_outs`，对 timeout 做 value bootstrap，再进入 GAE。

面试时可说：

> `done` 决定是否切断同一 episode 的 future；纯 timeout 需要单独保留未完成任务的价值，不能和失败 terminal 一概而论。

---

## 5. GAE：把未来多步的预测意外分给当前 action

### 5.1 递推式

![公式 015](./assets/math/PPO_LSTM_DEEP_DIVE/math-015.svg)

展开：

![公式 016](./assets/math/PPO_LSTM_DEEP_DIVE/math-016.svg)

所以必须从后往前算：当前 `A_t` 依赖已经算好的 `A_{t+1}`。

### 5.2 一个使用项目 γ/λ 的五步例子

假设：

```text
gamma = 0.9975
lambda = 0.985
gamma * lambda = 0.9825375
```

trajectory：

| t | reward r_t | value V_t | done |
|---:|---:|---:|---:|
| 0 | 0.0 | 0.4 | 0 |
| 1 | 0.2 | 0.5 | 0 |
| 2 | 0.5 | 0.7 | 0 |
| 3 | 1.0 | 0.9 | 0 |
| 4 | 2.0 | 1.1 | 1 |

先算 TD residual：

| t | δ_t |
|---:|---:|
| 4 | `2.0 - 1.1 = 0.9000` |
| 3 | `1.0 + .9975×1.1 - .9 = 1.1973` |
| 2 | `0.5 + .9975×.9 - .7 = 0.6978` |
| 1 | `0.2 + .9975×.7 - .5 = 0.3983` |
| 0 | `0.0 + .9975×.5 - .4 = 0.0988` |

再从后往前：

```text
A_4 = 0.9000
A_3 = 1.1973 + 0.9825375 * 0.9000 = 2.0815
A_2 = 0.6978 + 0.9825375 * 2.0815 = 2.7429
A_1 = 0.3983 + 0.9825375 * 2.7429 = 3.0933
A_0 = 0.0988 + 0.9825375 * 3.0933 = 3.1380
```

虽然 `t=0` 的即时 reward 为 0，但后面的开门进展让早期 action 得到正 advantage。这就是时序 credit assignment。

return target：

![公式 017](./assets/math/PPO_LSTM_DEEP_DIVE/math-017.svg)

```text
R = [3.5380, 3.5933, 3.4429, 2.9815, 2.0000]
```

critic 接下来拟合这些 return targets。

### 5.3 λ 是 bias–variance 旋钮

`λ=0`：

![公式 018](./assets/math/PPO_LSTM_DEEP_DIVE/math-018.svg)

只看一步 TD，依赖 critic，方差较小但 critic 偏差影响大。

`λ→1`：

融合更长时程 residual，更接近 Monte Carlo credit，通常偏差较小、方差较大。

当前 `λ=.985` 很重视长时程，但仍通过 value bootstrap 降低纯 Monte Carlo 方差。

### 5.4 Advantage normalization 不等于 GAE

GAE 算完后，项目会把整个 batch 的 advantage 标准化：

![公式 019](./assets/math/PPO_LSTM_DEEP_DIVE/math-019.svg)

它稳定梯度尺度，但不会替代 GAE，也不是 reward normalization。

---

## 6. PPO ratio：新策略对同一个旧 action 改了多少概率

### 6.1 先理解 old policy data

rollout 时保存：

```text
observation o_t
sampled action a_t
old log probability log π_old(a_t|o_t)
reward / done / value
```

训练时把相同 `o_t, a_t` 喂给更新中的策略，得到：

```text
new log probability log π_theta(a_t|o_t)
```

ratio：

![公式 020](./assets/math/PPO_LSTM_DEEP_DIVE/math-020.svg)

### 6.2 ratio 的直觉

- `r=1.0`：新旧策略同样看待这个 action；
- `r=1.2`：新策略给这个 action 的概率是旧策略的 1.2 倍；
- `r=0.8`：只剩旧策略的 0.8 倍。

如果 old probability 是 `0.20`：

```text
new probability 0.24 -> ratio 1.20
new probability 0.16 -> ratio 0.80
```

实际连续 action 使用 probability density 和 log probability，不应把 density 当离散事件概率，但 ratio 解释相同。

### 6.3 12D Gaussian action 的 logprob

当前 actor 建立 12 维 diagonal Gaussian。对 joint action：

![公式 021](./assets/math/PPO_LSTM_DEEP_DIVE/math-021.svg)

然后对这个 12D joint action 的总 logprob 做 new–old difference。不是分别得到 12 个 PPO ratios 再平均。

---

## 7. Clipped objective：看 advantage 符号再理解

最大化形式：

![公式 022](./assets/math/PPO_LSTM_DEEP_DIVE/math-022.svg)

当前 `ε=.2`，区间 `[0.8,1.2]`。

### 7.1 `A>0`：这是比预期好的 action

目标是提高它的概率，即希望 `r>1`。假设 `A=+2`：

| ratio | raw `rA` | clipped branch | objective |
|---:|---:|---:|---:|
| 1.0 | 2.0 | 2.0 | 2.0 |
| 1.1 | 2.2 | 2.2 | 2.2 |
| 1.3 | 2.6 | 2.4 | **2.4** |

超过 1.2 后，不再因为继续提高概率而获得更多 surrogate gain。

### 7.2 `A<0`：这是比预期差的 action

目标是降低它的概率，即希望 `r<1`。假设 `A=-2`：

| ratio | raw `rA` | clipped branch | objective |
|---:|---:|---:|---:|
| 1.0 | -2.0 | -2.0 | -2.0 |
| 0.9 | -1.8 | -1.8 | -1.8 |
| 0.6 | -1.2 | -1.6 | **-1.6** |

注意 `min`：当 ratio 降到 0.6，objective 选择更保守的 `-1.6`，不再奖励继续把坏 action 的概率压得更低。

### 7.3 clip 只切“有利方向上的过度更新”

若 `A=-2` 但 `r=1.3`，新策略反而提高了坏 action 的概率：

```text
raw = -2.6
clipped = -2.4
min = -2.6
```

这里不会帮你截成更舒服的 `-2.4`；loss 仍强烈推动策略纠正错误方向。

同理，`A>0` 但 ratio 过低时，也不会用 clip 掩盖这种退步。

### 7.4 为什么代码里是 `max` 而不是 `min`

论文常写“最大化 objective”。PyTorch optimizer 通常“最小化 loss”，所以代码取负号：

```python
pg_losses  = -A * ratio
pg_losses2 = -A * clamp(ratio, 1-eps, 1+eps)
pg_loss    = max(pg_losses, pg_losses2)
```

`max(负 objective)` 等价于 `-min(正 objective)`。

---

## 8. Value clip、Entropy、KL 分别做什么

### Value loss

critic 拟合 `R_t`。项目同时计算原始 value prediction 与围绕 old value 的 clipped prediction，取较大的 squared error，避免 critic 一次改变过猛。

### Entropy

Gaussian entropy 越大，分布越宽、探索越多。代码把：

![公式 023](./assets/math/PPO_LSTM_DEEP_DIVE/math-023.svg)

乘正系数加入总 loss，所以最小化总 loss 会鼓励 entropy。

### KL

clip 是 surrogate objective 的局部限制，不保证整体 KL 一定小。项目还计算 old/new Gaussian KL，并以 `desired_kl=.005` 自适应调整 learning rate。

---

## 9. 把公式重新接回项目代码

### 9.1 Rollout

`gr00t/rl/trl/trainer/ppo_trainer.py::_rollout_step`

```text
for t in 64 control steps:
  recurrent actor -> sampled high-level action
  frozen A2_Base -> leg action
  env.step()
  store obs/action/logprob/reward/done/value/hidden state
```

### 9.2 GAE

`TRLPPOTrainer::_compute_returns`

```text
reverse t = T-1 ... 0
delta = reward + (1-done) * gamma * next_value - value
adv   = delta + (1-done) * gamma * lambda * next_adv
return = adv + value
```

### 9.3 Recurrent batch

`_get_rollout_data` / `_get_mb_rollout_data`

```text
transpose to env-major
split at done
pad trajectories
build masks
restore trajectory-start hidden states
```

### 9.4 PPO update

`_compute_ppo_loss`

```text
new_logprob - old_logprob -> ratio
ratio + normalized advantage -> clipped policy loss
new value + return -> clipped value loss
entropy -> exploration term
KL -> learning-rate adaptation
```

### 9.5 当前训练规模

```text
one rollout = 4096 * 64 = 262,144 transitions
simulated time per env = 64 / 50 Hz = 1.28 s
same rollout reused for 5 PPO epochs
each epoch split into 4 minibatches
```

“复用 5 epochs”仍是有限的近端 on-policy update，不是把这批数据永久放进 replay buffer。

---

## 10. 最常见的错误理解

### “TD residual 就是 reward”

错。它是 `reward + discounted next value - current value`，衡量预测变化。

### “GAE 就是 discounted reward sum”

错。GAE 累积的是 TD residual，并由 `γλ` 衰减。

### “advantage 是 critic 输出”

错。critic 输出 `V_t`；advantage 由 reward、done、values 经过 GAE 得到。

### “ratio 是 new action / old action”

错。ratio 是同一个 sampled action 在 new/old policy 下的 probability-density ratio。

### “clip 把 action 限制在 [-0.2,0.2]”

错。`0.2` 限制 PPO ratio 的 surrogate improvement 区间，不是 action range。

### “clip 后 ratio 永远不会超过 1.2”

错。网络实际 ratio 可以超过；clip 只是让 objective 在有利方向上不再继续奖励超界变化。KL/clipfrac 会记录偏移。

### “LSTM 有 hidden state，所以不需要 observation history”

错。是否需要显式 history 取决于 policy contract。Teacher 使用 learned LSTM memory；冻结 A2_Base 明确要求 `30×54` history，两者不能互相替代。

### “done 只影响 return，不影响 LSTM”

错。done 同时切断 GAE bootstrap、切分 recurrent trajectory、reset 对应 env 的 hidden state。

---

## 11. 面试白板回答模板

### 30 秒解释 LSTM

> 单帧 observation 对接触、遮挡和运动方向不一定充分，所以 actor/critic 各自用两层 256 hidden 的 LSTM 累积时序上下文。rollout 时 hidden state 按 env 逐步推进，done 时只清零对应 env；训练时按 done 切 trajectory、padding 并 mask，保证不跨 episode 泄漏，也不把 padding 当样本。

### 30 秒解释 TD + GAE

> TD residual 是 `r + γV_next - V_now`，表示走完一步后 value target 相对旧预测的意外。GAE 从后往前按 `γλ` 累积多步 TD residual，得到当前 action 的 advantage；λ 控制一步 TD 与长时程 Monte Carlo 之间的 bias–variance 折中。

### 30 秒解释 PPO ratio + clip

> rollout 保存 old policy 对 sampled action 的 logprob。更新时新策略重新计算同一 action 的 logprob，指数差得到 ratio。正 advantage 希望 ratio 上升，负 advantage 希望下降；clip 让超过 `[0.8,1.2]` 的有利变化不再增加 surrogate gain，从而限制一次 update 走得太远。

---

## 12. 闭卷练习

1. 为什么 `δ_t>0` 不等于 `r_t>0`？
2. terminal 时为什么不能使用 reset 后 observation 的 value？
3. `λ=0` 和 `λ→1` 分别接近什么？
4. 为什么 GAE 必须反向计算？
5. old probability `0.25`、new probability `0.30`，ratio 是多少？
6. `A=+3, r=1.4, ε=.2`，clipped objective 取多少？
7. `A=-3, r=.5, ε=.2`，clipped objective 取多少？
8. `A=-3, r=1.4` 为什么不应在 1.2 处“保护”新策略？
9. 为什么 recurrent PPO 的 timestep 不能像 MLP batch 那样完全随机打散？
10. done 对 LSTM、GAE、trajectory packing 各有什么影响？

答案：

1. TD residual 还包含 next/current value prediction；
2. 那属于另一个 episode，会造成 bootstrap 泄漏；
3. 一步 TD；长时程/近 Monte Carlo advantage；
4. `A_t` 依赖 `A_{t+1}`；
5. `1.2`；
6. `3×1.2=3.6`；
7. `-3×0.8=-2.4`；
8. 提高坏 action 概率是错误方向，应保留完整惩罚梯度；
9. hidden state 与 observation 的时间对应会被破坏；
10. reset 对应 env memory、截断 future bootstrap、切分新 trajectory。

---

## 13. 精确源码入口

- `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml`
- `gr00t/rl/trl/modules/memory.py::Memory`
- `gr00t/rl/trl/modules/actor_critic_modules.py::Actor`
- `gr00t/rl/trl/modules/actor_critic_modules_recurrent.py::RecurrentActor`
- `gr00t/rl/trl/modules/actor_critic_modules_recurrent.py::RecurrentCritic`
- `gr00t/rl/trl/trainer/ppo_trainer.py::_rollout_step`
- `gr00t/rl/trl/trainer/ppo_trainer.py::_compute_returns`
- `gr00t/rl/trl/trainer/ppo_trainer.py::_get_rollout_data`
- `gr00t/rl/trl/trainer/ppo_trainer.py::_get_mb_rollout_data`
- `gr00t/rl/trl/trainer/ppo_trainer.py::_compute_ppo_loss`
