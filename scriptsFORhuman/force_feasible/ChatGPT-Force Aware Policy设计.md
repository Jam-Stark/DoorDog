# Force Aware Policy设计

**User:** Anonymous (cao2855100723@gmail.com)  
**Created:** 3/30/2026 19:47:02  
**Updated:** 3/30/2026 22:03:42  
**Exported:** 3/30/2026 23:02:46  
**Link:** [https://chatgpt.com/g/g-p-69a13fef262c819191c391f75509aca6-force-control-research/c/69ca62af-ad34-8322-9c97-5e3d9c38124d](https://chatgpt.com/g/g-p-69a13fef262c819191c391f75509aca6-force-control-research/c/69ca62af-ad34-8322-9c97-5e3d9c38124d)  

## Prompt:
当前敲定了research 方向是 arm学习指导base去微调roll/pitch/height 来实现获得一个更好的arm构型去apply force，或者我们说对比roboDuet 更加的 “force aware”。那么怎么让policy学会 “force aware”呢？设计奖励函数？还是创建相关guidance/teacher？

## Response:
我先把问题重新钉死：关键不是“能不能做 whole-body force control”，而是现有训练是否已经会为了减轻 arm 受力/不舒适构型而主动重构 base。接着我会对齐这些方法真正优化的目标、控制接口和作者承认的边界，再判断你的方向还能落在哪个明确增量上。

我还会顺手把另一个关键判断收束掉：pitch/roll/height 这些 base 自由度到底值不值得纳入，以及你的贡献该如何表述才不落成“又一个 whole-body force policy”。

Thought for 21m 27s

这个困惑我给你一个直接判断：

**如果你的 claim 只是“whole-body force control / arm 指导 base 配合施力”，那确实已经离 Portela、uniFP、FACET 很近了。**  
**但如果你的 claim 改成“force-feasibility-aware 的最小 base 重构”——也就是在 workspace edge / arm 近伸直 / 扭矩余量不足时，主动选一个尽量小、尽量不违背  $v_{\text{user}}\approx 0$  的 base 微调，让同样的  $F_{cmd}$  变得更可实现、同时 arm 更不容易饱和——这个方向仍然是成立的。** 这其实和你们自己的 benchmark 文档里写的目标已经一致了。

AliengoZ1\_ForceCoupling\_Baselin…

你的困惑本质上在于：**“whole-body 会施力”** 和 **“whole-body 会为 arm 选一个更省扭矩、更舒服的施力构型”** 不是同一个问题。

RoboDuet 做的是 **pose/workspace solvability**。它确实让 arm policy 输出对 base pitch/roll 的 guidance，来改善 whole-body 的 6D pose tracking 和可达性，但它的核心目标是姿态到达、避碰、workspace 扩展，不是“在同样末端力目标下选更低 arm stress 的构型”。

Pan 等 - 2025 - RoboDuet Learnin…

Portela 更强，它已经做到了 **whole-body force control**：position mode 把 workspace 从 0.81 m³ 扩到 1.29 m³，硬件上能拉到约 90N，而且作者也明确说在 reaching 极限处 force tracking error 会更高。也就是说，它已经证明了“whole-body 的确能扩大可施力范围”。但它的目标仍然是 **position/force tracking + 一般安全正则**；它没有把“在达到同样  $F_{cmd}$  时，显式最小化 arm 扭矩压力、关节饱和时间、或者选更舒服的 force posture”当成主目标。

Portela 等 - 2024 - Learning For…

uniFP 进一步把 position 和 force 放进一个 unified policy，但论文自己也写得很清楚：虽然理论上可以把 base 和 end-effector 的净力互相变换，实际实现里仍然是把 base 和 end-effector **独立处理**，body-part 之间更集成的推导留作 future work。也就是说，它不是在做你现在这件“arm feasibility 驱动的 base assist”。

Zhi 等 - 2025 - Learning a Unifi…

FACET 则更像 **impedance / force-adaptive behavior**。它在 multi-body 扩展里用一个显式耦合参数  $a$  去控制 end-effector 的 spring force 是否传到 base，这说明它承认 base–eef 力耦合是重要的；但它自己的 limitation 也承认 multi-body 机械约束和 reference target infeasibility 还没被充分处理。所以它也不是“基于 arm 力可行性、动态决定最小必要 base 重构”的方案。

Xu 等 - 2025 - FACET Force-Adapt…

所以，你现在真正应该说的是：

**你不是在做“让 robot 学会 whole-body 施力”**，  
而是在做：

**“在多个可达的 whole-body 构型里，学会挑那个让 arm 更容易施力的构型。”**

也就是从“能不能到”升级到“到了以后，这个姿势是不是一个好的施力姿势”。

这也是为什么你直觉里会觉得：  
“Portela/uniFP/FACET 好像只靠 position whole-body coordination + force training 就已经能 arm/base 配合施力了。”  
这个判断**没错**。它们当然可能学到“配合施力”。但问题是：

**它们学到的是“能成功就行”，还是“会主动选更省 arm 的方式成功”？**

如果 reward 只关心 force error / pose error，RL 没有理由偏好“更舒服”的 arm 几何。它只要把任务做成就行，哪怕 arm 长时间贴着饱和边缘、哪怕 base 动得更大。Portela 的 reward 设计就很能说明这点：force/position tracking 是主任务项，arm torque limit 更像 safety penalty，而不是“同等成功下优先选更低 arm stress”的主优化目标。

Portela 等 - 2024 - Learning For…

所以你现在的题目能不能成立，关键不在于“stage1 position + stage2 force 能不能学到协同”，而在于：

**你有没有把“arm 更舒服 / 更可施力”这件事变成 policy 必须显式追求的东西。**

这就要求你的 Ours 不能只比：

*   force RMSE
*   success rate

你必须比：

*   在同样 force 误差下，**arm max  $|\tau|/\tau_{max}$ ** 更低
*   **arm saturation time** 更少
*   **joint-limit proximity time** 更少
*   **force-feasible workspace** 更大（不是 geometric workspace）
*   **base displacement / 对  $v_{user}=0$  的违背** 更小

只要这些指标没有出来，你的方法就很容易被归类成“another whole-body force policy”。这也是你们自己的 benchmark 文档已经写出来的真正评价逻辑。

AliengoZ1\_ForceCoupling\_Baselin…

关于你第二个担心：**pitch/roll 可能没什么用**。  
我基本同意你的直觉。

在很多 Aliengo/Z1 这类前向接触任务里，通常更直接起作用的是：

*   **base 前后/左右平移**
*   **height**

pitch/roll 往往是二级项。RoboDuet 里 pitch/roll 很重要，是因为它要解决的是 6D pose / workspace shaping；但在你的 force task 上，它们未必有同样大的边际收益。

Pan 等 - 2025 - RoboDuet Learnin…

所以对你最稳的做法不是先假设 pitch/roll 有用，而是把它当成一个**待证实的 action dimension**。你们自己的文档里那条 action ablation 路线其实是对的：

$$
\Delta v \text{ only} \rightarrow \Delta v + \Delta h \rightarrow \Delta v + \Delta h + \text{pitch/roll}
$$

如果最后实验表明 pitch/roll 基本没贡献，那不是坏事，反而说明你的 story 更干净：  
**真正有用的是“translation + height 的最小 assist”，而不是所有 base DOF 都有用。**

AliengoZ1\_ForceCoupling\_Baselin…

所以我给你的结论是：

1.  **你的方向还能做，但必须再窄一层。**  
    不要说“whole-body force control”，要说  
    **force-feasibility-aware minimal base reconfiguration**。
2.  **Stage1 position WBC + Stage2 force reward 必须作为强 baseline。**  
    因为它确实可能已经学到一部分 arm/base 协同。
3.  **你的新意不在“会不会协同”，而在“是否会主动选更省 arm 的协同方式”。**
4.  **pitch/roll 不要预设有价值，先做 sensitivity scan。**  
    很可能最后真正有用的是 `vx / vy / h`，这完全可以接受。
5.  **即使最后你的 policy 学到的主要只是“增大 force-feasible workspace”或“减少 arm 饱和时间”，这也已经是一个清晰结果。**  
    你不需要证明所有 base DOF 都有贡献，也不需要证明它能“凭空造出更大力”；你只要证明它能把原来对 arm 不友好的施力点，变成更可持续、更稳定、更少饱和的施力点，就足够了。
    AliengoZ1\_ForceCoupling\_Baselin…

我觉得你下一步最重要的不是继续想 architecture，而是先做两个会“打脸自己”的实验：一个是 **base pose/height 对同一  $F_{cmd}$  的 arm torque margin 扫描**，另一个是 **plain stage1+stage2 baseline**。这两个结果一出来，你这个题目是不是还值得继续，就会非常清楚。

## Prompt:
你还是没有回答我的问题：我明确了我要做“在多个可达的 whole-body 构型里，学会挑那个让 arm 更容易施力的构型。”  那么怎么让policy学会 “force aware”呢？设计奖励函数？还是创建相关guidance/teacher？ 怎么让policy学会“会主动选更省 arm 的方式成功”？

## Response:
Thought for 27m 19s

最直接的答案是：

**不是“奖励函数 vs teacher”二选一。**  
对你这个题目，**reward/constraint 是必须的，teacher/guidance 是强烈建议的。**

因为你现在要学的，不是“能不能把力做出来”，而是：

**在已经能成功的多个 whole-body 解里，偏好那个更省 arm、更少饱和、更少违背  $v_{user}$  的解。**

这个“偏好”如果不写进优化目标里，policy 没理由自己学会。仅靠 `force error` 或 `success rate`，它只会学“做成就行”，不会学“更省 arm 地做成”。这正是你和 Portela / uniFP / RoboDuet / FACET 的分界：它们分别证明了 whole-body、force tracking、arm-to-base guidance、teacher-student 很有用，但并没有把“同等 force 成功下优先保 arm 余量”设成核心目标。Portela 的 reward 里有 body velocity tracking，也只有一个 arm torque-limit penalty；uniFP 用两阶段训练做 force/position tracking，但明确把 end-effector 和 base 独立处理；RoboDuet 的 guidance 和 `rarmguide` 是为了 body orientation / pose tracking；FACET 的 teacher-student 是为了学 impedance reference tracking，并且作者自己也承认 multi-body 的机械约束和 infeasible target 还没真正解决。

Portela 等 - 2024 - Learning For…

Zhi 等 - 2025 - Learning a Unifi…

Pan 等 - 2025 - RoboDuet Learnin…

Pan 等 - 2025 - RoboDuet Learnin…

Xu 等 - 2025 - FACET Force-Adapt…

Xu 等 - 2025 - FACET Force-Adapt…

所以我给你的建议是一个很明确的“三层做法”。

### 1\. 先把“force-aware”定义成一个显式可优化量，而不是一句口号

不要只奖励“力跟踪好”。  
要奖励的是：

**沿着当前  $F_{cmd}$  方向，arm 还有多少施力余量。**

最简单的 proxy 有三个，先不用很复杂：

*   `torque margin`:  $1 - \max_i |\tau_i|/\tau_{i,\max}$ 
*   `joint-limit margin`: 离限位还有多远
*   `stretch/singularity risk`: arm 是否接近伸直、肘是否接近打直

更好的版本是做一个**方向相关**的可行性分数，而不是泛泛的 manipulability。因为你关心的不是“这个姿势通不通用”，而是“这个姿势对当前这一个力方向舒不舒服”。

也就是说，policy 观测里必须显式看到这些量。  
没有这些输入，它根本不知道“现在 arm 很难受，只是还没彻底失败”。

* * *

### 2\. reward 必须写成“先做成，再比较谁更省 arm”

这是最关键的地方。

如果你直接写：

$$
r = -\|F_{cmd}-F_{est}\|^2 - \lambda_\tau \cdot \text{torque\_penalty}
$$

会有一个问题：policy 可能为了减小扭矩，干脆少发点力。

所以更好的写法是**success-conditioned reward**，也就是：

*   **先**逼它把力做出来
*   **只有当力误差已经进阈值**，才开始比较“谁更省 arm、谁更少动 base”

形式上你可以写成：

$$
r = r_{\text{force}} + \mathbf{1}[\|F_{err}\|<\epsilon_F] \Big( \lambda_m \, r_{\text{margin}} -\lambda_b \, r_{\text{base\_move}} -\lambda_u \, r_{\text{user\_deviation}} \Big) -\lambda_s r_{\text{stability}}
$$

这里：

*   `r_force`：力跟踪
*   `r_margin`：arm torque margin / limit margin / stretch risk
*   `r_base_move`：base 总动作尽量小
*   `r_user_deviation`：尽量不违背  $v_{user}$ 
*   `r_stability`：别滑、别倒、别爆腿

这一步其实就把你们 benchmark 文档里那句目标完全落实了：  
**在力误差约束下，最小化 base 位移、违背  $v_{user}$ 、arm 饱和时间。**

AliengoZ1\_ForceCoupling\_Baselin…

一句话概括：

**reward 决定了“什么叫 force-aware”。**

没有这一步，teacher 再强，也只是教出一个“像 teacher 的动作”，不是“真正最省 arm 的策略”。

* * *

### 3\. teacher/guidance 不是定义目标，而是解决“学不会”的问题

你的任务天然很难学，原因是：

*   真正需要 base assist 的状态很少，主要出现在 workspace edge / near-straight-arm
*   credit assignment 很长：base 先动一点，几百毫秒后 arm torque 才下降
*   如果 action 一上来就是 `vx/vy/h/pitch/roll` 全开，探索会很乱

这时候，**teacher/guidance 非常值**。  
但它的角色不是替代 reward，而是**让 reward 真的能学出来**。

我建议你用一个**很弱但很实用**的 teacher：

每次只在一小组候选 base 微调里做一阶搜索：

$$
\mathcal{A}=\{0,\pm \Delta x,\pm \Delta h,\pm \Delta \text{pitch},\pm \Delta \text{roll}\}
$$

然后选那个能让下面这个量提升最多的动作：

$$
\Delta(\text{arm feasibility}) - \alpha \cdot \Delta(\text{base cost})
$$

也就是：

**哪一个最小 base 微调，能让 arm 更容易沿  $F_{cmd}$  施力。**

这根本不需要很重的 MPC/QP。  
你甚至可以先用离散候选动作 + 一步 look-ahead + 简单静态指标来做。

然后做两件事：

*   用这个 teacher 去监督一个 `guidance head`
*   再用 PPO / RL 按上面的 reward 去 fine-tune

这时 teacher 只负责告诉 policy：  
“遇到这种 hard case，base 往哪边微调通常是有帮助的。”

而 reward 决定：  
“最终到底要不要这么调、调多大、值不值得。”

这和 RoboDuet 的结构很像，但你把 guidance 的语义从“pose/body orientation”换成了“force feasibility”。RoboDuet 已经证明了 arm policy 输出 guidance、loco policy 去跟这个 guidance 是个可行接口。

Pan 等 - 2025 - RoboDuet Learnin…

Pan 等 - 2025 - RoboDuet Learnin…

* * *

### 4\. 训练流程我建议你这样排

**Stage 1**：先学稳的 whole-body reaching / locomotion  
这个没问题，跟 RoboDuet / uniFP 一样。

Pan 等 - 2025 - RoboDuet Learnin…

Zhi 等 - 2025 - Learning a Unifi…

**Stage 2**：只开最少的 assist DOF  
先别一上来就 `vx, vy, h, pitch, roll` 全开。  
我会建议：

*   先 `Δv_x`
*   再 `Δv_x + Δh`
*   最后如果扫描证明有帮助，再加 `pitch/roll`

因为你真正要学的是“最小必要 base assist”，不是“给 base 无限自由度去乱补”。

**Stage 3**：只在 hard states 上开 teacher loss  
hard states = `接触成立` 且 `force gap 持续` 且 `arm margin 低`

别全程 imitation。  
否则最后你学到的是 heuristic，而不是比 heuristic 更好的 policy。

**Stage 4**：后期逐步减小 teacher 权重  
最后只留 RL 的主目标，让策略自己在真实 trade-off 上收敛。

* * *

### 5\. 如果你现在只想做 MVP，先做这个，不要贪大

如果你现在只能做一个最小系统，我建议：

**先做 reward + 少量 feasibility observation，不先做复杂 teacher。**

也就是先加：

*   `F_cmd, F_est`
*   `|\tau|/\tau_max`
*   `joint-limit margin`
*   `straight-arm indicator`
*   `contact`
*   assist action 只开 `Δv_x`

然后 reward 用我上面那种 success-conditioned 版本。

原因很简单：

*   这一步最能证明你的核心 claim
*   这一步不会把 novelty 淹没在“teacher 很强”里
*   如果它学不出来，再加 heuristic teacher，故事也很自然

* * *

### 6\. 一句最关键的话：什么叫“会主动选更省 arm 的方式成功”？

不是“加 force reward”。  
而是：

**在力已经基本达标时，继续奖励“更大的 arm 余量 + 更小的 base assist + 更少的  $v_{user}$  违背”。**

也就是说，你真正需要的是：

**force-tracking objective + arm-feasibility tie-breaker + minimal-assist regularization**

而不是单独任何一个。

* * *

如果你要我给一个一句话结论：

**你的方法应该是：用 reward/constraint 明确写出“同等 force 成功时优先保 arm 余量、尽量少动 base”，再用一个很弱的 force-feasibility teacher 只在 hard cases 上提供 guidance。**  
**reward 定义你要什么，teacher 解决你怎么学到。**

我觉得下一步最值得做的是，我直接帮你把这个写成一版“可抄进代码里的 reward 和 teacher 伪代码”。

## Prompt:
你的任务天然很难学，原因是： \* 真正需要 base assist 的状态很少，主要出现在 workspace edge / near-straight-arm \* credit assignment 很长：base 先动一点，几百毫秒后 arm torque 才下降

这一段描述是有问题的吧：
1 为了我的research 方法更加的general。 所以对于常规workspace内也希望 能够通过微调base学出一个比 “先有position control学出wbc再接着学force control”的方法有一个更优的arm构型去apply force，不需要workspace edge / near-straight-arm的condition
2 为什么是“base 先动一点，几百毫秒后 arm torque 才下降”？ 学完后应该表现上就是arm和base一起实时直接调整到最优位置了吧？ 不存在arm先动base后动或者反过来的先后顺序？

## Response:
Thought for 14m 25s

对，这两点你纠正得对。我前面的表述应该改。

**1）“workspace edge / near-straight-arm”不该是方法定义，只该是最容易出效果的 benchmark。**

你要的更 general 版本，应该是：

**在整个可接触 workspace 内，只要存在多个都能完成相近 force tracking 的 whole-body 构型，policy 都优先选那个让 arm 更省扭矩、更远离限位/伸直、同时尽量少扰动 base 的构型。**

也就是说：

*   **edge case 只是最容易看出增益的区域**
*   **不是只有到了 edge 才触发你的方法**
*   **normal workspace 里也应该存在“更优的 force posture”这个偏好**

你们自己的 benchmark 文档其实已经是在往这个方向写了：在力误差约束下，最小化 base 位移、违背  $v_{user}$ 、以及 arm 饱和时间。

AliengoZ1\_ForceCoupling\_Baselin…

这里还有一个很重要的修正：

**general 不等于“处处都让 base 微调”。**  
真正 general 的含义是：**base assist 是一个可选自由度，值得时才用，不值得时就不动。**

所以在 regular workspace 内，最优策略很多时候可能就是：

*   力已经能稳定做出来
*   arm 余量也够
*   那就别动 base

这反而更像“force-aware”。

你前面的担心也是对的：  
Portela 明确把 whole-body force control 的价值写成“优化 whole-body posture 来在更大 workspace 里施加大力”；uniFP 也确实是先学 whole-body reaching / locomotion，再加入 force commands 和 disturbances。基于这些训练设计，**我认为**这些 baseline 很可能已经会学到一部分“挑更好施力姿势”的能力——这是我的推断，不是论文原话。

Portela 等 - 2024 - Learning For…

Zhi 等 - 2025 - Learning a Unifi…

所以你的差异不能再写成：

**“我也让 arm 和 base 一起配合施力。”**

而要写成：

**“我把 arm feasibility / arm comfort 变成全域显式偏好，而不是只靠任务成功自己涌现。”**

更直接地说，你不是做一个 corner-case fixer，  
而是在做一个 **global tie-breaker**：

同样都能把  $F_{cmd}$  做出来时，  
**谁让 arm 更舒服，谁就更优。**

所以训练目标也应该是**全域连续型**，而不是只在 near-singularity 才开一个二值 trigger。形式上更像：

$$
J = -\|F_{err}\|^2 + \lambda\, m_{arm} - \mu \|u_{assist}\| - \nu \|v_{base} - v_{user}\|
$$

这里  $m_{arm}$  可以是 torque margin、joint-limit margin、或 stretch / singularity proxy。  
这样 hard case 只是  $\lambda m_{arm}$  影响最大的区域，不是唯一适用区域。

AliengoZ1\_ForceCoupling\_Baselin…

* * *

**2）“base 先动一点，几百毫秒后 arm torque 才下降”这句话，如果用来描述最终表现，确实不准确。**

你说得对。  
**学好以后，外在表现应该是 arm 和 base 同步实时协同调整。**  
不是必须“先 arm 后 base”，也不是必须“先 base 后 arm”。

RoboDuet 的 stage 2 本来就是 arm guidance 和 loco policy 协同工作；uniFP 的 two-stage、FACET 的 teacher-student，本质上也都是**训练策略**，不是部署时的串行执行。

Pan 等 - 2025 - RoboDuet Learnin…

Zhi 等 - 2025 - Learning a Unifi…

Xu 等 - 2025 - FACET Force-Adapt…

我前面那句话真正想表达的是：

**从学习角度看，base 微调的收益常常是 delayed effect。**

也就是：

*   你这一步 base 微调
*   会改变后续几步里的接触几何、力臂、负载分配
*   最终体现在 arm torque / force error 上

所以对 RL 来说，这是一种**跨时步 credit assignment**问题。

但这不等于部署时动作是串行的。

更准确的一句话应该改成：

**arm 和 base 的命令是同步输出的，但 base assist 对 arm feasibility 的收益通常是跨时步显现的。**

这两件事不冲突：

*   **控制执行层面**：同步
*   **学习 credit 层面**：延迟体现

还有一个更细的物理层面也值得区分：

*   **命令可以同步发**
*   但 **arm 与 base 的物理时间常数不一样**

arm 关节往往更快，  
base 的 COM、足端重分配、步态调整更慢。  
所以即便策略同步输出，你在状态上也可能看到“arm 先有小变化，base 后面完成重构”，或者反过来。  
这只是系统动力学，不是策略逻辑必须有先后顺序。

* * *

所以，把你的研究重新表述成一句更准的话，会是：

**不是做一个只在 near-singularity 才救场的策略，而是做一个在整个 force-feasible workspace 内，把“更省 arm 的 whole-body 构型”作为显式偏好的策略；hard case 只是最容易验证价值的地方。**

如果继续往下推，最关键的一步其实是：  
**把“general workspace 内的显式偏好”写成可训练目标，而不是写成一句 intuition。**

2/2

## Prompt:
对，那么变成general workspace内的优化后，独立研究后给出我reward/constraint的设计思路/指导/案例。teacher/guidance的方法等

## Response:
Thought for 23m 42s

最稳的答案是：

**reward / constraint 负责定义“什么叫 force-aware”，teacher / guidance 负责让它更容易学出来。**

对你现在这个 **general workspace** 版本，不应该再用“只在 workspace edge 才触发”的二值逻辑，而应该把目标写成一个**全域连续偏好**：

**在所有能把  $F_{cmd}$  做出来的 whole-body 构型里，优先选那个 arm 扭矩余量更大、离限位/伸直更远、同时 base 改动更小、对  $v_{user}$  违背更少的构型。**

你们自己的文档其实已经给了最合适的接口：  
 $u_{base}=u_{user}+gate(s)\cdot u_{assist}$ ，并且目标本来就应当在力误差约束下最小化 base 位移、违背  $v_{user}$ 、以及 arm 扭矩饱和时间。

AliengoZ1\_ForceCoupling\_Baselin…

* * *

1\. 先把目标写成“主任务 + tie-breaker”，不要一锅炖
-----------------------------------

我建议你把目标拆成三层。

### 第一层：主任务

必须先把力做出来。

也就是：

*   接触建立
*   Hold 窗口内 force error 达标
*   不跌倒、不滑、不爆关节

这和你们 benchmark 文档里的 success 定义是一致的：Hold 阶段要求  $|F_{est}-F_{cmd}|$  的均值/峰值达标，同时 arm 长时间扭矩饱和、关节顶限位、滑移、跌倒都不允许。

AliengoZ1\_ForceCoupling\_Baselin…

### 第二层：在“已经做出来”以后，再比较谁更省 arm

这是你真正的 novelty。

定义一个连续的 arm-feasibility 分数，例如

$$
m_{arm} = w_\tau \Big(1-\max_i |\tau_i|/\tau_{i,\max}\Big) + w_q\,m_{q\_limit} + w_s\,m_{stretch}
$$

这里可以分别对应：

*   扭矩余量
*   关节限位余量
*   伸直/奇异风险 proxy

注意这里我不建议只用 manipulability 这种太泛的量。  
你更关心的是**当前  $F_{cmd}$  方向下的舒适程度**，所以最重要的还是 torque margin。

### 第三层：在“省 arm”之外，再要求 base assist 尽量小

否则 policy 很容易学成“为了舒服，base 总是乱动”。

所以再加：

*   assist 动作大小
*   对  $v_{user}$  的偏离
*   对 nominal posture / 接触建立时 posture 的偏移

这一步非常关键，因为它保证 general workspace 下，policy 不会总是跑去一个“全球最舒服的站姿”。

* * *

2\. 推荐 reward 结构
----------------

我建议用一个**分层激活**的 reward，而不是单纯线性加权。

可以写成：

$$
r_t = r_{\text{force}} + \alpha_t\, r_{\text{margin}} - \alpha_t\,(r_{\text{assist}}+r_{\text{user}}+r_{\text{anchor}}) - r_{\text{stability}} - r_{\text{safety}}
$$

其中

$$
\alpha_t = \mathbf{1}[\text{contact}] \cdot \sigma\!\left(\frac{\epsilon_F-\|F_{cmd}-F_{est}\|}{k_F}\right)
$$

它的意思是：

*   **没接触**时，不谈 force-aware
*   **力还没做出来**时，先专注把力做出来
*   **力基本做出来**之后，margin / minimal assist 才开始起 tie-breaker 作用

这个形式很重要，因为它避免了一个经典坏解：

> policy 为了减小扭矩，干脆少出一点力。

* * *

### 2.1 force reward

建议不要只看幅值，最好拆成三项：

$$
r_{\text{force}} = w_F \exp(-\|F_{err}\|/\sigma_F) + w_D \cos(F_{cmd},F_{est}) + w_H \mathbf{1}[\|F_{err}\|<\epsilon_F]
$$

对应：

*   力向量误差
*   力方向误差
*   进入目标 corridor 的奖励

Portela 的训练里就用了 force reward，并且 force command 采用 ramp-up / hold / ramp-down 的调度；这非常适合你，因为可以减少突然冲击和 estimator 抖动。

Portela 等 - 2024 - Learning For…

* * *

### 2.2 arm-feasibility reward

建议至少有三项：

$$
r_{\text{margin}} = w_\tau m_\tau + w_q m_q + w_s m_s
$$

其中：

*    $m_\tau$ : 扭矩余量
*    $m_q$ : 离 joint limit 的余量
*    $m_s$ : 离伸直/奇异的余量

一个实用版本是：

$$
m_\tau = 1-\max_i |\tau_i|/\tau_{i,\max}
$$

这个最直接，也最贴你的 claim。

Portela 的 reward 里已经有 arm torque limit penalty，但它更像 safety regularizer，不是“同等 force 成功下优先保 arm 余量”的主目标；你这里要把它升级成主 tie-breaker。

Portela 等 - 2024 - Learning For…

* * *

### 2.3 minimal-assist reward

这一项决定你的方法是不是“general workspace 内的最小必要 assist”。

$$
r_{\text{assist}} = w_u \|u_{assist}\|^2 + w_{\Delta} \|\Delta u_{assist}\|^2
$$

也就是：

*   assist 本身越小越好
*   assist 变化越平滑越好

RoboDuet 在 stage 2 里加入了 `rarmsmooth` 和 `rarmguide`，本质上就是在 whole-body guidance 上加平滑和一致性约束。你可以借这个思想，但把语义从 pose guidance 改成 force-feasibility guidance。

Pan 等 - 2025 - RoboDuet Learnin…

* * *

### 2.4 user-semantics reward

因为你现在不是“自主导航机器人”，而是“用户命令 + assist”，所以必须有：

$$
r_{\text{user}} = w_v \|v_{base}-v_{user}\|^2
$$

如果你有姿态/高度命令，也可以扩展成对  $(h,pitch,roll)$  的偏差惩罚。

这项直接对应你们文档里写的 “对  $v_{user}$  的违背量”。

AliengoZ1\_ForceCoupling\_Baselin…

* * *

### 2.5 anchor reward

这是我建议你额外补的一项。

为了避免 general workspace 下 policy 总把 base 调去一个“全球舒服”姿态，加入：

$$
r_{\text{anchor}} = w_p \|\xi_{base}-\xi_{ref}\|^2
$$

这里  $\xi_{ref}$  可以取：

*   接触建立瞬间的 base posture
*   或 locomotion prior 给出的 nominal posture

这样做的意义是：

**policy 只有在“真的值得”时才去改 base。**

* * *

### 2.6 stability / safety

这些别只当小罚项，权重要高，甚至部分做 hard constraint：

*   slip penalty
*   fall termination
*   posture / height 越界
*   long torque saturation
*   long joint-limit hitting

你们 benchmark 文档里已经把这些写得很清楚了。

AliengoZ1\_ForceCoupling\_Baselin…

* * *

3\. 哪些要做 constraint，不要只做 reward
-------------------------------

我的建议很简单：

### 用 hard constraint / clipping 的

*    $u_{assist}$  每个维度的幅值上限
*    $pitch/roll/h$  的安全范围
*   无接触时 assist 禁止或极小
*   持续滑移、跌倒、连续饱和直接终止
*   每个 trial 的 base displacement budget

### 用 soft reward 的

*   force tracking
*   arm comfort / feasibility
*   minimal assist
*   smoothness
*   与  $v_{user}$  的一致性

你们自己的接口设计里已经非常适合这么做：  
`u_base = u_user + gate(s) * u_assist`，并对 `u_assist` 限幅、加最小动作正则。

AliengoZ1\_ForceCoupling\_Baselin…

我还建议你给 `gate(s)` 加**滞回**，避免抖动开关：

*   进入 assist： $\|F_{err}\| > F_{on}$  或  $m_\tau < \tau_{on}$ 
*   退出 assist： $\|F_{err}\| < F_{off}$  且  $m_\tau > \tau_{off}$ 

并要求  $F_{on}>F_{off}$ ， $\tau_{on}<\tau_{off}$ 。

* * *

4\. teacher / guidance 怎么做
--------------------------

### 结论先说

**先上 reward/constraint；teacher 只负责缩短探索。**  
不要一开始就让 teacher 定义“什么是对的”，否则你最后只是在复现 heuristic。

我给你三个层级。

* * *

### 方案 A：弱启发式 assist teacher

这是我最推荐的第一版。

只给 assist 通道一个老师，不教 whole-body 全动作。

做法很简单：每个时刻只在一个小候选集里选动作：

$$
\mathcal{A} = \{0,\pm \Delta v_x,\pm \Delta h,\pm \Delta pitch,\pm \Delta roll\}
$$

然后给每个候选动作打分：

$$
S(a) = -w_F \|F_{err}^{pred}(a)\| + w_\tau \Delta m_\tau^{pred}(a) + w_s \Delta m_s^{pred}(a) - w_u \|a\|^2 - w_v \|u_{user}+a-u_{user}\|^2
$$

意思就是：

*   能不能减小 force gap
*   能不能增加 torque margin / stretch margin
*   动作是不是太大
*   是否太违背用户命令

teacher 只在 **hard states** 启用：

*   已建立接触
*   force gap 持续
*   arm margin 低

然后只监督

$$
L_{guide} = \mathbf{1}[\text{hard state}]\,\|u_{assist}-u_{assist}^{*}\|^2
$$

这个方法最大的优点是：

**它天然能学会“什么时候不该动”。**

比如你担心的“下压力场景里降低 base height 根本没用”，那 teacher 的 candidate scoring 就会给出：

*   所有候选都不提升 predicted margin
*   最优就是  $a=0$ 

这恰恰是你要的行为。

* * *

### 方案 B：RoboDuet-style guidance head

RoboDuet 的结构非常适合你这个故事：

*   stage 1：先学 robust locomotion
*   stage 2：arm policy 输出 guidance，loco policy 跟这个 guidance 协调
*   并且在 stage 2 加 `rarmguide`、`rarmsmooth` 和 reward adjustment。
    Pan 等 - 2025 - RoboDuet Learnin…
    Pan 等 - 2025 - RoboDuet Learnin…

你可以直接借这个接口，但换掉语义：

*   RoboDuet 的 guidance：为了 pose / reachability
*   你的 guidance：为了 force feasibility / arm comfort

具体上可以让 arm 头输出：

$$
g_{base}=[\Delta v_x,\Delta h,\Delta pitch,\Delta roll]
$$

然后 base/loco 头去跟踪这个 guidance，并加：

*   `r_guide = -||u_{assist}-g_{base}||`
*   `r_guide_smooth = -||g_t-g_{t-1}||^2`

这个版本很适合你想讲“arm 指导 base”的论文故事。

* * *

### 方案 C：FACET-style privileged teacher-student

如果你发现只靠 reward 很难学，或者 force estimator 太噪，那就用 FACET 那套思路。

FACET 用的是：

*   teacher 能看到 privileged 信息
*   student 用真实可观测量
*   student 从 teacher 初始化后，还继续 PPO fine-tune，而不是停在 imitation 上。
    Xu 等 - 2025 - FACET Force-Adapt…

你这里可以让 teacher 看到：

*   真实  $\tau$ 
*   真实接触状态 / 滑移
*   更准确的 force / external force
*   甚至直接看到你定义的 force-feasibility score

然后 teacher 只负责教 assist / guidance 头。  
student 再在真实观测下继续 RL。

这个版本最强，但工程量也最大。

* * *

5\. 我最推荐的训练顺序
-------------

### 第 0 步：先做 sensitivity scan

先不要训练大 policy。

对几个典型 contact task，扫描：

*    $v_x$ 
*    $h$ 
*    $pitch$ 
*    $roll$ 

看在相同  $F_{cmd}$  下：

*    $\max |\tau|/\tau_{max}$ 
*   saturation time
*   steady-state force error
*   slip

如果 pitch/roll 没明显收益，就别急着把它们放进 action space。

* * *

### 第 1 步：Stage 1 locomotion / whole-body prior

这点可以沿用 RoboDuet / uniFP 的经验：  
先学稳的 locomotion / whole-body reaching，再上 force。RoboDuet 和 uniFP 都用了 staged training，而且都表明这样更稳定。

Pan 等 - 2025 - RoboDuet Learnin…

Zhi 等 - 2025 - Learning a Unifi…

* * *

### 第 2 步：先开最少 assist DOF

我的建议顺序：

1.  `Δv_x`
2.  `Δv_x + Δh`
3.  最后再加 `Δpitch/Δroll`

不要一开始就 5 个 DOF 全开。

* * *

### 第 3 步：先只用 reward/constraint

先验证：

*   不用 teacher，policy 能不能学出“力达标后更省 arm”
*   在 general workspace 内是否会自然地少量重构 base

这一步最能证明你 claim。

* * *

### 第 4 步：收敛慢时，再加 hard-state teacher

只在：

*   contact 已建立
*   force gap 持续
*   torque margin 低

时加 imitation / guidance loss。  
不要全程 imitation。

* * *

### 第 5 步：逐步减小 teacher loss

最后留给 RL 去做真正 trade-off。  
FACET 的经验正是：student 继续 fine-tune，而不是只忠实模仿 teacher。

Xu 等 - 2025 - FACET Force-Adapt…

* * *

6\. 三个具体案例
----------

### 案例 1：墙面水平推

在 workspace 中心附近，通常有多个能达到同样  $F_x$  的构型。

这时：

*   `r_force` 都差不多
*   `r_margin` 会偏好 arm 不那么伸、扭矩更低的构型
*   `r_assist + r_user + r_anchor` 又会阻止 base 乱走

最终学到的是：  
**只做最小必要前移/降高，或者干脆不动。**

* * *

### 案例 2：桌面向下压

这正是你最担心的场景。

如果 lowering base / pitch forward 并没有提升 predicted torque margin，  
那 teacher 最优动作就是 0，reward 也会因为 `r_assist + r_anchor` 把无效 base motion 压掉。

所以这里你不是在逼 policy“总要补力”，而是在逼它学会：

**什么时候 base 重构有用，什么时候没用。**

这个“会判断不该动”本身就是结果。

* * *

### 案例 3：擦拭 / 侧向 contact maintain

这类任务里 pitch/roll 有时会有帮助，但不一定大。

所以别预设它们一定有贡献。  
让它们通过 scan + ablation 进入 action space，而不是靠直觉。

* * *

7\. 你现在最该实现的 MVP
----------------

我建议你先实现这一版：

**观测：**

*    $F_{cmd}, F_{est}, \Delta F$ 
*   contact / slip
*    $|\tau|/\tau_{max}$ 
*   joint-limit margin
*   arm extension ratio / elbow angle
*    $v_{user}, v_{base}$ 
*   base posture / height

**动作：**

*    $u_{assist}=[\Delta v_x,\Delta h]$ 

**reward：**

*    $r_{force}$ 
*   success-conditioned  $r_{margin}$ 
*    $r_{assist}$ 
*    $r_{user}$ 
*    $r_{anchor}$ 
*    $r_{slip}, r_{fall}, r_{sat}$ 

**teacher：**

*   先不上
*   学不出来再加 weak candidate-search teacher

这版最容易验证你的核心 claim，而且不会把故事弄得太散。

* * *

一句话收束：

**general workspace 版本下，你的方法不该被设计成“edge-case 才启动的救火器”，而应该是一个全域的 tie-breaker：在 force 成功的所有解里，持续偏好更大的 arm feasibility 和更小的 base intervention。reward/constraint 定义这个偏好；teacher/guidance 只在 hard states 上帮助它更快学会。**

下一条我就把它整理成一版可直接抄进代码的 reward 表、gate 逻辑和 teacher 伪代码。



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)