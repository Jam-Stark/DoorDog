# DoorDog 面试速查与白板题

如果 LSTM、TD residual、GAE、PPO ratio 或 clipped objective 仍不牢固，先读 [`PPO_LSTM_DEEP_DIVE.md`](./PPO_LSTM_DEEP_DIVE.md)，再回来做本页闭卷题。如果连 shape、broadcast、梯度、value 或 Bellman 的直觉也不稳，按 [`README.md`](./README.md) 的“从零补课主路线”从数学与 Tensor 开始，不必硬啃 PPO。

## 90 秒项目介绍

> 我做的是 A2 四足底盘加 PiPER 机械臂的开门策略。架构上没有让 PPO 直接学习全部 20 个关节，而是把任务策略和 locomotion 分层：recurrent Teacher PPO 根据 133 维 privileged observation 输出 12 维高层动作，包括 5 维 base command、6 维 arm 和 1 维 gripper primitive；冻结的 A2_Base 根据 30×54 的本体历史输出 12 维腿动作。trainer 组成 24 维环境动作，环境按关节名、delta action 和 gripper 语义映射为 20 个关节 position targets。Isaac physics 是 200 Hz，policy/control 是 50 Hz。一次 PPO rollout 是 4096 个并行环境各 64 步，使用 GAE、clipped policy/value loss 和 recurrent trajectory masking。任务通过六阶段状态机组织，但 reward、stage advance 与 terminal 分开。后续蒸馏分支让 81 维 proprio 加多相机视觉的 Student 用 DAgger 学 Teacher 的 12 维动作，sim2sim 分支再把同一控制和感知合同搬到 MuJoCo 做 shadow evaluation。

## 五张必须能画的白板

### 1. 两个闭环

```text
obs -> policy -> action -> physics -> reward/done -> obs
                         |
4096 x 64 transitions -> GAE -> PPO update -> policy
```

追问：为什么 policy loop 和 training loop 的频率不同？

答：policy 每个 control step 都执行；optimization 要先收集整批 rollout，再对固定 old-policy data 做有限次更新。

### 2. Action contract

```text
Teacher high 12 = base5 + arm6 + grip1
                                      + -> env 24
A2_Base 1620 -> frozen -> legs12

env 24 -> logical 19 -> robot target 20
```

追问：为什么 24 到 20 不是简单截断？

答：5D base command 进入 frozen locomotion policy，不直接对应 robot joint；1D gripper primitive 扩成两个 finger joint targets；关节还要按名称重排。

### 3. GAE

```text
delta_t = r_t + gamma(1-d_t)V_{t+1} - V_t
A_t     = delta_t + gamma lambda (1-d_t) A_{t+1}
R_t     = A_t + V_t
```

追问：`λ` 增大有什么效果？

答：使用更长时程的 TD residual，通常偏差降低、方差增大。它不是 learning rate。

### 4. PPO clip

```text
ratio = exp(new_logp - old_logp)
Lclip = min(ratio*A, clip(ratio, 0.8, 1.2)*A)
```

追问：`A<0` 时 clip 在防什么？

答：防止策略过度降低坏动作的概率，避免一次 update 离采样 policy 太远。

### 5. Teacher → Student

```text
privileged state -> Teacher -> label 12D
proprio + vision -> Student -> predicted 12D
student-visited state -> Teacher relabel -> DAgger correction
```

追问：为什么不是模仿最终 20D？

答：Student 的可学习控制边界是 12D high-level；腿由冻结 A2_Base 负责，gripper expansion 和 joint mapping 属于环境。

## PPO 五连问

### Q1：PPO 为什么需要 old log probability？

同一批 action 是由 old policy 采样的。`new_logp - old_logp` 给出重要性比率，衡量新策略对这些已采样 action 的概率改变。没有 old logp 就无法构造 ratio，也无法判断 update 离行为策略多远。

### Q2：clip 是不是保证 KL 一定小？

不是严格保证。clip 限制 surrogate objective 的继续收益，近似 trust-region；项目还显式计算 Gaussian KL，并用 desired KL 调整 learning rate。

### Q3：为什么还要 critic？

用 state-dependent baseline 降低 policy gradient 方差，并为 rollout 末端/timeout 提供 bootstrap。critic 预测错不会直接发动作，但会影响 advantage 质量。

### Q4：为什么 advantage 要标准化？

稳定当前 batch 的梯度尺度，让正负相对排序更重要。它不改变单个 batch 内谁好谁坏，但不是 reward normalization 的同义词。

### Q5：为什么 recurrent PPO 不能随便 shuffle timestep？

LSTM output 依赖 trajectory 起点 hidden state 和前序 observation。随机打散会破坏时序，跨 done 还会泄漏另一个 episode 的状态。

## IsaacLab / simulator 五连问

### Q1：这个项目使用标准 ManagerBasedRLEnv 吗？

不是。它是自定义 Gym-style task hierarchy 和 IsaacSim adapter，内部使用 IsaacLab scene、articulation、sensor API。应描述真实类链，不要把所有 IsaacLab 项目都叫 manager-based。

### Q2：physics 200 Hz、control 50 Hz 是什么意思？

policy 每 20 ms 产生一次新动作；该动作在 4 个 5 ms physics substeps 中保持/执行。contact 和 PD dynamics 在 200 Hz 演化，reward/done/obs 按 control step 汇总。

### Q3：并行环境的 done 如何处理？

每个 env 有自己的 done mask。post-physics 只 reset 完成的 env，并把对应 LSTM hidden state 清零；其他 env 继续当前 episode。

### Q4：为什么 returned obs 和 done 看起来属于不同 episode？

done 描述刚结束的 transition；同一个 `env.step` 内完成 selective reset 后，returned obs 可以是新 episode 的首帧。这是 vectorized env 的正常约定。

### Q5：FrameTransformer 为什么重要？

reward 和 observation 需要 gripper 相对 handle/pregrasp 的 pose。必须固定 source/target order、frame convention 和 rotation representation；目标顺序漂移会让相同 tensor slot 语义变化。

## Network 五连问

### Q1：为什么 LSTM 放在 MLP 前？

先把 observation sequence 编码到 256D recurrent state，再由 MLP 映射到 action mean/value，使 head 看到已经聚合的时序上下文。

### Q2：actor 和 critic 是否共享 LSTM？

当前不是。它们各自独立的 RunningMeanStd、2-layer LSTM 和 MLP，input contract 也不同。

### Q3：Actor 输出的 12D 是 action 还是 mean？

network 输出 Gaussian mean；训练 rollout 从 `Normal(mean,std)` 采样，evaluation 使用 mean。std 是可学习参数并受配置上限约束。

### Q4：为什么要 RunningMeanStd，又要物理 scale？

物理 scale 表达固定单位/量级先验；RunningMeanStd 适应实际数据分布。两者层次不同。

### Q5：为什么 A2_Base 要 30 帧 history？

低层 locomotion 需要运动趋势、上一动作、步态相位和命令上下文。`54×30` 是该冻结 policy 的部署合同，不能随意改为单帧。

## Reward / stage 五连问

### Q1：return 高能否说明成功率高？

不能。dense shaping 可能被利用；success 必须由 door angle、grasp continuity、crossing 等任务指标单独定义。

### Q2：stage complete 是否等于 episode done？

中间 stage complete 只推进状态机。完整任务只有最后 stage complete 才是 success terminal；还可能有 failure 和 timeout terminals。

### Q3：为什么 stage2 contact 要 history gate？

单帧 collision spike 可能造成 false grasp。连续 control-step contact/squeeze 证据更接近稳定抓取。

### Q4：staged reset 是作弊吗？

它是 curriculum，用来缩短长时程 credit assignment；但不能用后段起点结果替代 natural-start full task evidence。

### Q5：reward scale 的物理含义是什么？

它不是现实世界单位，而是优化权重；仍应检查原始 term 的单位、时间累积和门限，避免某个高频 term 仅因采样频率占据 return。

## Distillation / DAgger 五连问

### Q1：为什么 Teacher 可以看 privileged state？

Teacher 是 simulation oracle / label policy，目标是产生高质量 action；Student 才受部署 sensor 限制。部署时不带 Teacher。

### Q2：DAgger 比普通 BC 多了什么？

让 Student 控制部分 rollout，并在 Student 实际到达的状态上向 Teacher 查询标签，缓解 covariate shift。

### Q3：teacher rollout ratio 等于 Phase3 吗？

不等于。它是 Phase2 mixed rollout / curriculum；Phase3 是 Student 在自己的闭环分布上用任务 return/success 做 RL fine-tuning。

### Q4：为什么 camera age/valid 是输入？

左右 D435、Head camera 更新频率不同，50 Hz policy tick 可能看到缓存帧。age/valid 让 LSTM知道信息新鲜度，属于正式 policy contract。

### Q5：object prediction 是否启用？

A2 route 显式关闭。代码存在不等于当前系统使用；缺少验证过的 object target/frame contract 时必须诚实说明。

## sim2sim 五连问

### Q1：为什么不能只把 URDF 转 MJCF？

policy 依赖的不只是几何：joint order、frame、control gains/limits、action decimation、history、camera cadence 和 normalization 都是闭环的一部分。

### Q2：为什么按 physics step 比 paired trace？

接触、力和 hinge event 可能发生在 4 个 substeps 中间；只比较 policy tick 会隐藏关键误差。

### Q3：action replay 通过证明了什么？

它隔离并验证已锁定 action 下的控制/physics path；不证明 live rendered pixels 会让 policy 产生相同 action。

### Q4：external PD 与 native position actuator 等价吗？

不等价。一个在 Python 显式计算并 clip torque，另一个由 solver 内部处理；只能作为已声明 deviation 单独验证。

### Q5：当前能说 sim2sim 成功吗？

不能笼统说。可说 bundle/load、若干 observation/action/control/door modules 有运行证据，r7 对视觉域差有隔离证据；正式 same-case paired parity 曾因缺 Isaac trace blocked，更不是 hardware pass。

## 最容易说错的十句话

| 错误说法 | 更准确的说法 |
|---|---|
| “网络直接控制 20 个关节。” | Teacher 学 12D 高层动作；冻结 A2_Base 学腿；环境再映射到 20 DOF。 |
| “PPO 每 5 ms 出一次动作。” | physics 200 Hz；policy/control 50 Hz，每个动作跨 4 substeps。 |
| “critic 和 actor 输入一样。” | 当前 actor 133D，critic 多 5 个训练标量为 138D。 |
| “stage2 完成就成功了。” | stage2 只是 grasp；完整 success 在 final stage。 |
| “奖励越高就越会开门。” | return 只是优化信号，要看 natural-start success 和直接门/抓取指标。 |
| “Student 是离线模仿 Teacher。” | mixed rollout / DAgger 在 Student 访问状态上继续取得 Teacher label。 |
| “Student 学 24D 动作。” | Student 与 Teacher 对齐的是 12D high-level；leg12 来自冻结 A2_Base。 |
| “代码里有 object prediction，所以我们用了。” | A2 配置显式关闭，目前没有可部署的验证合同。 |
| “MuJoCo 跑起来就证明 sim2sim 了。” | module runtime 与 paired parity 不同；必须同 case、同 trace、同指标比较。 |
| “仿真 effort 没超限，所以实机安全。” | simulation command/force 不是 hardware safety evidence。 |

## 追问陷阱

### “4096 个环境就是 4096 条独立 episode 吗？”

不一定。每个 rollout window 内不同 env 可能在不同时间 done/reset；一个 env 也可能跨 batch 延续 episode。storage 是 `[T,N]` transitions，不等同于每列恰好一个完整 episode。

### “rollout 64 步就是 64 个物理帧吗？”

不是。64 个 control steps，每步 4 个 physics substeps，因此对应 256 physics steps、1.28 秒仿真时间。

### “γ=.9975 为什么这么接近 1？”

任务是长时程且 control frequency 高；以 50 Hz 计算，几十到几百步仍应保留明显信用。必须结合 dt 解释，而不是只说“更重视未来”。

### “为什么 critic 可以看 actor 看不到的信息，不会作弊吗？”

critic 只在训练时估计 baseline，不参与部署动作。只要部署 actor 不依赖 privileged input，这是 asymmetric training 的常见用法；仍需保证 advantage/value learning 不发生错误的数据泄漏。

### “LSTM 能解决视觉域差吗？”

不能保证。它能利用时间一致性，但若像素分布、颜色、纹理、相机模型超出训练分布，hidden state 只会累积错误证据。sim2sim r7 正好说明 perception 与 physics 需要分开隔离。

## 闭卷自测

不看材料，逐题在 60 秒内回答：

1. 从 `actor_obs` 到 PhysX joint target 的每个 tensor shape 是什么？
2. 为什么 `actor_obs=133`、`critic_obs=138`？多出来的 5 维是什么？
3. `54D` A2_Base frame 每一块分别是什么？
4. control 50 Hz 与 physics 200 Hz 如何在 `env.step` 内配合？
5. 写出 TD residual、GAE、PPO ratio 和 clipped objective。
6. `A>0` 和 `A<0` 时 PPO clip 分别阻止什么？
7. recurrent rollout 为什么要保存 hidden state、按 done 切 trajectory、mask padding？
8. reward、stage advance、done、timeout 的区别是什么？
9. staged reset 为什么有用，又为什么不能证明 natural-start success？
10. DAgger 如何缓解普通 BC 的 covariate shift？
11. Phase2 teacher rollout、PPO value bootstrap、Phase3 student bootstrapping 有何不同？
12. sim2sim 中 action replay 能隔离什么，不能证明什么？
13. 为什么 joint order 和 camera age 都是 policy contract？
14. 当前有哪些结论只是 source inspected，哪些是 branch 上的 runtime/experiment，哪些明确 blocked？
15. 为什么所有仿真结果都不能自动升级为 hardware safety evidence？
