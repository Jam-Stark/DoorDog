# Force-feasibility-aware Policy

**User:** Anonymous (g5sxgcmxg4@privaterelay.appleid.com)  
**Created:** 3/31/2026 11:07:10  
**Updated:** 4/1/2026 0:04:43  
**Exported:** 4/1/2026 0:04:57  
**Link:** [https://chatgpt.com/c/69cb3a35-2328-8320-95da-e10be2e40a49](https://chatgpt.com/c/69cb3a35-2328-8320-95da-e10be2e40a49)  

## Prompt:
描述一下当前最新mark的research方向，我确定你清楚的知道我想要做的direction后再继续讨论

## Response:
我先对照你刚刚那份设计稿，把你“当前已经收敛到哪一步”提炼成几条明确的研究目标，再给出我对你方向的判断。

Thought for 40s

我理解你**当前最新 mark 的方向**，已经不是“再做一个 whole-body force control”，而是把问题重新收窄成：

**在 general workspace 内，只要存在多个都能完成相近 force tracking 的 whole-body 构型，policy 就应该主动偏好那个让 arm 更容易施力、更不容易饱和、同时 base 改动尽量小的构型。**

ChatGPT-Force Aware Policy设计

换句话说，你现在要做的不是“让 arm 和 base 一起施力”本身，而是一个更明确的目标：

**force-feasibility-aware / arm-comfort-aware 的最小 base 重构。**  
也就是在满足力跟踪的前提下，把“arm 扭矩余量更大、离限位/伸直更远、对 `v_user` 违背更少、base intervention 更小”变成 policy 的显式偏好，而不是希望它从普通的 force reward 里自己涌现出来。

ChatGPT-Force Aware Policy设计

AliengoZ1\_ForceCoupling\_Baselin…

我理解你现在这条线有 6 个关键点：

1.  **研究范围已经从 edge case 扩成了 general workspace。**  
    edge / near-singularity 只是最容易看出增益的 benchmark，不再是方法定义本身。你要的是全域 tie-breaker。
    ChatGPT-Force Aware Policy设计
2.  **base assist 是可选自由度，不是默认总要动。**  
    真正“force-aware”的 policy，应该学会“什么时候值得动 base，什么时候不值得”，很多 regular workspace 的状态下最优解可能就是不动。
    ChatGPT-Force Aware Policy设计
3.  **核心接口已经基本定了。**  
    你想用的是  
    `u_base = u_user + gate(s) · u_assist`，  
    其中 `u_assist` 是一个小的、受限幅和正则约束的 base 助力项，`gate(s)` 是状态相关门控。
    AliengoZ1\_ForceCoupling\_Baselin…
4.  **你和现有工作的差异，不是“会不会 whole-body”，而是“会不会显式偏好更省 arm 的解”。**  
    你自己的文档里也已经把这个差异写得很清楚：不是再证明能 whole-body 施力，而是在力误差约束下最小化 base 位移、`v_user` 违背、arm 扭矩饱和时间。
    AliengoZ1\_ForceCoupling\_Baselin…
5.  **训练目标会是“主任务 + tie-breaker”。**  
    先把力做出来，再在力已基本达标时，奖励更大的 arm 余量、更小的 base assist、更少的 `v_user` 偏离，而不是把这些东西一开始就和 force error 平铺混在一起。
    ChatGPT-Force Aware Policy设计
6.  **teacher/guidance 不是主角，reward/constraint 才是主角。**  
    你最新的设计里已经收敛到这个判断：reward/constraint 定义“什么叫 force-aware”，teacher/guidance 只是帮助更快学出来，最好先从弱启发式或 hard-state guidance 开始。
    ChatGPT-Force Aware Policy设计

如果我把你现在的方向压成一句论文式表述，我会写成：

**We study a state-dependent, minimally invasive base-assist policy that globally biases whole-body force interaction toward more arm-feasible configurations, rather than merely achieving force tracking.**

再翻成更口语一点，就是：

**不是“让机器人能施力”，而是“在能施力的所有解里，优先选那个对 arm 更友好的解”。**

另外，我觉得你最新版本里还有两个很重要的边界我也理解到了：

*   你不想把故事讲成“workspace edge 专用救火器”，而是 **general workspace 下的连续偏好优化**。
    ChatGPT-Force Aware Policy设计
*   你也不预设 `pitch/roll` 一定重要，而是倾向于先做 sensitivity scan，再决定 action space 从 `Δv`、`Δh` 逐步扩到 `pitch/roll`。
    ChatGPT-Force Aware Policy设计
    AliengoZ1\_ForceCoupling\_Baselin…

所以我的判断是：**我清楚你现在想做的 direction 了。**  
它本质上是一个 **global force-feasibility tie-breaker + minimal base intervention** 的问题，不是另一个泛化版 RoboDuet，也不是单纯把 force reward 接到已有 whole-body policy 后面。

ChatGPT-Force Aware Policy设计

如果这个概括和你心里的版本一致，下一步我就可以直接按这个定义，继续往下和你讨论：  
**怎么把它落成具体的 reward、constraint、gate 设计，以及 teacher/guidance 的最小可行方案。**

## Prompt:
Ok，你对我当前想做的research direction确实有足够理解了。那么我有以下问题需要你进行充分研究/思考后回答，推荐大量阅读相关可靠的文献：

1. 我没有机器人学/动力学/机械相关背景，所以对如何去判断arm在某一direction上是否有force余量没有idea。这显然导致我不知道怎么去设计reward或者guidance
2. 比如说之前提到的目标效果是“如果有几个潜在的可以reach到同一个target position的arm构型，那么policy会选择对force 最优/最有余量的”，那么这个arm构型首先就非常难计算出来了，如果能够提前计算出来的话，那么我这个research也没有意义了。其次还需要微调base，也就是自由度或者说“构型空间”被扩展为整个robot全身关节了。那么更加难处理了。

## Response:
我会先把问题拆成两部分：先定义并估计某个方向上的力余量，再研究在不显式求最优 whole-body 构型时，如何把这种偏好做成可学习的 reward/guidance。

我已经把文献线索收拢成一个关键主线：先默认你关心的是末端给定方向上的准静态施力，再用一个可在线计算、方向相关的局部 margin/评分替代“提前求全局最优构型”。接下来我会把这个评分放到三层来讲清楚——Jacobian 映射、关节扭矩上限、wrench polytope——并直接对应到 reward/guidance 的写法。

接下来我会把这个 force-feasibility score 进一步分成“便宜但好用”的版本和“更完整但更重”的版本，并解释为什么这并不等于提前把你的 research 做完。

Thought for 25m 2s

这两个问题其实指向同一个核心：

**你不需要先把“全身最优构型”解出来，才能做这个 research。**  
你真正需要的是一个**局部、方向相关、可在线计算的 force-feasibility score**，再让 policy 去学“在保持任务成功的前提下，把这个 score 变大”。文献里真正可操作的路线也基本都是这样：先定义 capability / manipulability / wrench score，再在冗余自由度里做局部优化、null-space 优化、低维参数化搜索，或者把这种优化摊销成 learned policy。[Springer+3modernrobotics.northwestern.edu+3modernrobotics.northwestern.edu+3](https://modernrobotics.northwestern.edu/nu-gm-book-resource/velocity-kinematics-and-statics/)

1\. 先把“某个方向上的 force 余量”讲清楚
--------------------------

最基本的关系只有一句话：

$$
\tau = J(q)^\top f
$$

也就是，末端施加的力/力矩  $f$  会通过 Jacobian  $J(q)$  映射成各关节需要承担的力矩  $\tau$ 。Modern Robotics 直接给出了这个静力学关系，并指出 joint torque limits 可以通过  $J^\top$  映射成 tip force limits；同一本资料也说明了 force ellipsoid 和 manipulability ellipsoid 是一对互逆对象，用来表达“在哪些方向容易施力、哪些方向不容易施力”。[modernrobotics.northwestern.edu+1](https://modernrobotics.northwestern.edu/nu-gm-book-resource/velocity-kinematics-and-statics/)

所以，对你最有用的定义不是抽象的“这个 arm 姿态舒不舒服”，而是：

**在当前构型  $q$  下，沿着目标方向  $d$ （单位向量）还能再加多少力，直到某个关节先撞上扭矩上限。**

如果只看**局部、准静态**情形，这个量其实很好算。

设

$$
d=\frac{F_{\text{cmd}}}{\|F_{\text{cmd}}\|}, \qquad g = J(q)^\top d
$$

那么  $g_i$  表示“沿着目标方向加 1N（或 1 单位 wrench）时，第  $i$  个关节要多承担多少 torque”。  
再设当前关节扭矩估计为  $\tau^{\text{cur}}$ ，关节上下限为  $[\tau^{\min},\tau^{\max}]$ 。  
那第  $i$  个关节还能承受的**额外目标方向力**是：

$$
\mu_i = \begin{cases} \dfrac{\tau_i^{\max}-\tau_i^{\text{cur}}}{g_i}, & g_i>0 \\ \dfrac{\tau_i^{\min}-\tau_i^{\text{cur}}}{g_i}, & g_i<0 \\ +\infty, & g_i=0 \end{cases}
$$

然后取所有会先饱和的关节里的最小正值：

$$
\mu_{\text{dir}}(q,d)=\min_i \mu_i
$$

这个  $\mu_{\text{dir}}$  就是我最推荐你用的**local directional force margin**。  
它非常贴近你的目标：如果两个构型都能 reach 到同一个 target，但一个构型的  $\mu_{\text{dir}}$  更大，就说明它在当前力方向上更“有余量”、更不容易被某个关节先卡死。这个定义直接来自  $\tau=J^\top f$  的静力映射，也和文献里“给定 wrench direction 看 actuator saturation / transmission ratio”的路线一致。[modernrobotics.northwestern.edu+2Frontiers+2](https://modernrobotics.northwestern.edu/nu-gm-book-resource/velocity-kinematics-and-statics/)

### 这比 manipulability 更适合你

经典 manipulability / force ellipsoid 很有用，但它本质上更像**平均能力**或**各向能力**。Modern Robotics 说明了 ellipsoid 能表达不同方向的施力能力；Frontiers 2024 的综述进一步强调：如果你的任务只关心**单一目标方向**，那么各向同性体积指标就不够了，**direction-specific** 的 transmission ratio 更合适；同时，wrench ellipsoid 只是近似，wrench polytope 更能反映真实 actuator constraints。[modernrobotics.northwestern.edu+2Frontiers+2](https://modernrobotics.northwestern.edu/nu-gm-book-resource/5-4-manipulability/)

所以你可以把“force-aware score”分成三档：

第一档，**最便宜的 proxy**：  
用 force ellipsoid / transmission ratio。它便宜、可微、很适合做 dense reward：

$$
r_{\text{ellip}}(q,d)\propto \frac{1}{\sqrt{d^\top J W^{-2} J^\top d}}
$$

这里  $W$  可以编码 joint torque limits。这个方向上的“半径”越大，说明越容易沿  $d$  施力。Modern Robotics 给了 force ellipsoid 的基础解释；Frontiers 2024 明确指出 transmission ratio 就是“在给定方向上，沿 ellipsoid 从原点走到边界的距离”。[modernrobotics.northwestern.edu+1](https://modernrobotics.northwestern.edu/nu-gm-book-resource/5-4-manipulability/)

第二档，**我最推荐的 MVP 指标**：  
直接用上面的  $\mu_{\text{dir}}$ 。  
它比 ellipsoid 更贴你的研究问题，因为它直接回答“哪个关节先饱和，还能多出多少力”。

第三档，**更高保真但更复杂**：  
wrench polytope / saturating wrench。Frontiers 2024 综述说得很清楚：polytope 比 ellipsoid 更真实，但优化更难；已有工作会对给定 wrench direction 求 actuator saturation，或者做 lower-level LP。这个方向你后面当然可以上，但我不建议拿它做第一版。[Frontiers](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1442813/full)

2\. 你没有动力学背景，也仍然可以先做对
---------------------

你现在最不需要的是一上来就碰 full dynamics。  
你的 first working version 完全可以把任务视为**准静态接触任务**：推墙、压桌面、拉物体、维持接触。对这类任务，静力关系  $\tau=J^\top f$  已经足够给你一个很强的、方向相关的 margin signal。动态 manipulability 当然存在，Yoshikawa 1985 把它定义成“在 joint driving force 约束下，末端可实现加速度集合形成的 ellipsoid”；Azad 等 2019 还强调了 weighting matrix 的选择会显著影响 dynamic manipulability 的结果。可这些更适合你第二阶段去处理“快、冲击、瞬时 acceleration”任务，而不是现在的 MVP。[J-STAGE+1](https://www.jstage.jst.go.jp/article/sicetr1965/21/9/21_9_970/_article/-char/en)

换句话说：

**先用 quasi-static directional margin 把问题做对，再考虑 dynamic manipulability。**

这条路线和你现在的 research direction 是一致的。

3\. “如果能算出最优构型，那这个 research 不就没意义了？”——不是
----------------------------------------

这是最关键的误解。

**score 和 solver 不是一回事。**

你需要的是一个“这个构型在当前力方向上好不好”的**打分函数**，而不是一个“全身最优轨迹/最优配置的闭式解”。  
这在文献里非常常见：

Kapusta & Kemp 的 TOC 直接说了，找有效 robot configurations 很难，因为几何复杂、自由度多、任务复杂；他们不是求闭式最优解，而是用 task-centric reachability 和 task-centric manipulability 这些 score 去做**离线重计算的 configuration scoring**。[Springer+1](https://link.springer.com/article/10.1007/s10514-019-09847-2)

Frontiers 2024 这篇关于 wrench capability 的综述也很明确：  
冗余系统的 wrench optimization 很快就会碰到高维、非线性、IK constraint；因此一个主流做法不是在全 joint space 里硬搜，而是用 **redundancy parameterisation** 把“保持同一 end-effector pose 时还可以变化的 self-motion”压缩成一个低维参数空间，再在这个低维空间里做优化。文章还指出，local redundancy resolution 可能数值不稳定、轨迹次优，而全局 over-trajectory optimization 则更难。[Frontiers](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1442813/full)

这其实正好说明你的 research 仍然有意义：

*   你不需要闭式求出“全身最优构型”
*   你只需要一个**局部 score**
*   再让 RL / policy 在真实接触、用户命令、base dynamics、稳定性约束下，学会**在线把自己推向高分区域**

这和“我已经知道最优答案了”完全不是一回事。

4\. 你的搜索空间也不该是“全身所有关节”
----------------------

这个担心也对：如果你真的把 search space 设成“整个机器人所有关节的所有等效构型”，问题会很快不可控。

更好的做法，是把你的方法明确定义成：

**在固定 end-effector task 的前提下，对一个低维 self-motion / base-assist 子空间做优化。**

这正是 redundancy parameterisation 的思路：用一个最小的冗余变量集合描述“保持末端 pose 不变时还能怎么变”，从而避免直接在全 joint space 上优化，也绕开非线性 IK constraint。Frontiers 2024 明确把这一点讲得很清楚。[Frontiers](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1442813/full)

对你来说，最自然的低维子空间其实不是“全身关节”，而是：

$$
z = [\Delta x_{\text{base}}, \Delta h, \Delta pitch, \Delta roll]
$$

或者更保守地先从：

$$
z = [\Delta x_{\text{base}}, \Delta h]
$$

开始。

这样你就把问题从“求 full-body 最优构型”变成了：

**在一个 2 到 4 维的 assist space 里，找能提高 directional force margin、同时又不太打扰用户命令和稳定性的那个小动作。**

这和已有移动机械臂文献也吻合。Tugal 等 2022 的工作就是通过**optimal base localization** 来提高 selected task directions 上的 force transmission，同时保持 velocity control；他们把“人会调整身体姿态来更有效地用手臂施力”作为出发点，并用方向 manipulability 做优化。2025 年那篇 mobile dual-arm 工作则把 manipulability optimization 和 force tracking 放到同一个 QP/impedance 控制框架里。[Springer+2Springer+2](https://link.springer.com/article/10.1007/s10514-022-10050-z)

这两类工作都说明：  
**base reconfiguration + force capability optimization** 本来就是合理研究方向。  
你的新意在于把它做成 **legged + learned + minimal-assist + arm-feasibility-aware**，而不是显式优化器。

5\. 我给你的 reward 设计建议
--------------------

我建议你的核心 reward 不要直接写成“force error + torque penalty”那种简单相加。  
那样 policy 会倾向于“少出一点力来换更小扭矩”。

你要的是**主任务 + tie-breaker**：

$$
r_t = r_{\text{force}} + \alpha_t \Big( w_m \,\hat{\mu}_{\text{dir}} + w_q \,m_{\text{jlimit}} + w_e \,m_{\text{elbow}} - w_u \|u_{\text{assist}}\|^2 - w_v \|v_{\text{base}}-v_{\text{user}}\|^2 - w_a \|\xi_{\text{base}}-\xi_{\text{anchor}}\|^2 \Big) - r_{\text{safety}}
$$

其中：

$$
\alpha_t = \mathbf{1}[\text{contact}] \cdot \sigma\!\left(\frac{\epsilon_F-\|F_{\text{err}}\|}{k}\right)
$$

也就是：

*   **没接触**：不谈 force-aware
*   **力还没做出来**：先做力
*   **力基本做出来后**：才比较“谁更省 arm、谁更少动 base”

这点和你之前已经收敛出的 success-conditioned 思路是一致的。你上传的设计文档里也已经明确了这个方向。

ChatGPT-Force Aware Policy设计

### 具体每一项怎么落

`r_force`  
先只做最朴素的：

*   force magnitude error
*   force direction error
*   hold bonus

`hat{μ_dir}`  
把前面那个 local directional force margin 做一个归一化，比如：

$$
\hat{\mu}_{\text{dir}} = \tanh\left(\frac{\mu_{\text{dir}}}{F_{\text{scale}}}\right)
$$

或者更直观：

$$
\rho_{\text{reserve}} = \frac{\mu_{\text{dir}}}{\|F_{\text{cmd}}\|+\epsilon}
$$

它表示“当前命令力之外，你还剩下多少方向相关余量”。

`m_jlimit`  
不要只看 torque。Kapusta & Kemp 在 TOC 里展示过一种很实用的 joint-limit weighted Jacobian 思路：用一个对角权重矩阵给接近关节限位的关节降权，再基于这个加权 Jacobian 算 manipulability / isotropy。你完全可以照这个精神，先用简单版：

$$
m_{\text{jlimit}} = \min_i \text{dist\_to\_limit}(q_i)
$$

或者做一个 smoother 的 joint-limit weight。[Springer](https://link.springer.com/article/10.1007/s10514-019-09847-2)

`m_elbow`  
这个不是必须，但工程上很好用。  
比如用 elbow bend angle / extension ratio。它能帮你把“快伸直了”的几何坏姿态也早点压掉。

`u_assist`、`v_base-v_user`、`anchor`  
这三项负责保证你的方法不是“为了舒服，base 到处乱动”。

*   `u_assist`：最小 intervention
*   `v_base-v_user`：尊重用户命令语义
*   `anchor`：prefer 接触建立时或 locomotion prior 的 nominal base pose

这能直接把你的研究方向写实：**不是求最强施力，而是在任务成功前提下求最小必要 base 重构。**

`safety`  
至少包括：

*   slip
*   fall
*   foot/contact instability
*   sustained torque saturation
*   hard joint limit hit

6\. teacher / guidance 怎么做，才不会变成“提前解题”
--------------------------------------

我不建议你一开始上一个很强的全局 teacher。  
你最适合的是：

### 方案 A：先不上 teacher，只上 reward

这是最能证明你 claim 的版本。  
如果只靠 reward，policy 就能学出“力达标后更省 arm”，这个故事最干净。

### 方案 B：弱 teacher，只在低维 assist space 里选动作

这个是我最推荐的第二步。

令候选 assist 集合为：

$$
\mathcal{A} = \{0,\ \pm \Delta x,\ \pm \Delta h,\ \pm \Delta pitch,\ \pm \Delta roll\}
$$

对每个候选  $a$ ，算一个局部 score：

$$
S(a) = \hat{\mu}_{\text{dir}}(s,a) + \lambda_q m_{\text{jlimit}}(s,a) - \lambda_u \|a\|^2 - \lambda_v \|v_{\text{user}}+a-v_{\text{user}}\|^2 - \lambda_s \text{slip\_risk}(s,a)
$$

然后 teacher 只输出：

$$
a^* = \arg\max_{a\in\mathcal{A}} S(a)
$$

这不是在“提前解出 whole-body 最优构型”，因为：

1.  你只在一个很小的 low-dim assist space 里选
2.  你选的是**局部最优候选动作**，不是全局轨迹
3.  这个 score 只负责“哪个方向更好”，真正的长期 trade-off 仍然由 RL 去学

它本质上更像一个 **weak preference teacher**。

### 方案 C：RoboDuet 风格 guidance 接口，但语义改掉

RoboDuet 的接口本身非常值得借：arm policy 输出 guidance，loco/base policy 跟这个 guidance 协同。只是 RoboDuet 的 guidance 主要服务于 pose tracking / workspace expansion，而不是你要的 directional force reserve。

Pan 等 - 2025 - RoboDuet Learnin…

所以你完全可以保留它的接口形式，但把 guidance 的语义改成：

**“沿当前  $F_{\text{cmd}}$  方向提高  $\mu_{\text{dir}}$  的 base assist 建议”。**

### 为什么 FACET 式 teacher-student 也值得借

FACET 的价值在于，它不是 teacher-only imitation，而是 student 继续 fine-tune。对你很重要，因为你不想让 teacher 定义目标，只想让 teacher 缩短探索。FACET 也承认 multi-body setting 里 reference infeasibility 和 mechanical constraints 仍然是难点。

所以你的 teacher 最好只在：

*   已建立接触
*   force gap 持续
*   directional margin 低

这些 hard states 上开，并且后期逐步退火掉。

7\. 你现阶段最值得实现的 MVP
------------------

我会建议你先做这一版，不要一下上满：

**观测**

*    $F_{\text{cmd}}, F_{\text{est}}, \Delta F$ 
*   contact / slip
*   当前 arm torque 或 torque estimate
*    $|\tau|/\tau_{\max}$ 
*    $\mu_{\text{dir}}$  或其归一化版
*   joint-limit margin
*   elbow angle / extension ratio
*    $v_{\text{user}}, v_{\text{base}}$ 
*   base height / pitch / roll

**动作**

*   先只开  $u_{\text{assist}}=[\Delta x_{\text{base}}, \Delta h]$ 
*   pitch/roll 先不要默认放进来

**reward**

*   `r_force`
*   success-conditioned `r_margin`
*   `r_assist`
*   `r_user`
*   `r_anchor`
*   `r_slip / r_fall / r_sat`

**teacher**

*   第一版先不上
*   学不出来，再加低维 candidate-search teacher

这版足够回答你现在的两个根本问题，而且不会把 story 弄散。

8\. 你现在最该读的文献顺序
---------------

先读这 4 篇，把“什么是 force margin”真正弄懂：

1.  **Modern Robotics, Chapter 5**  
    先把 Jacobian、 $\tau=J^\top f$ 、manipulability ellipsoid、force ellipsoid 搞懂。这是后面所有 reward 的母语。[modernrobotics.northwestern.edu+1](https://modernrobotics.northwestern.edu/nu-gm-book-resource/velocity-kinematics-and-statics/)
2.  **Yoshikawa, 1985, Dynamic Manipulability of Robot Manipulators**  
    这是“manipulability 不是只有 kinematic，也可以看 torque→acceleration capability”的经典起点。[J-STAGE](https://www.jstage.jst.go.jp/article/sicetr1965/21/9/21_9_970/_article/-char/en)
3.  **Azad, Babič, Mistry, 2019**  
    这篇非常适合你，因为它强调 dynamic manipulability 的 weighting matrix 不是小细节，而是决定分析是否物理可信的关键。[Springer](https://link.springer.com/article/10.1007/s10514-018-09819-y)
4.  **Frontiers 2024, Maximising the wrench capability of mobile manipulators**  
    这一篇几乎是给你量身定做的桥梁：它把 wrench ellipsoid、transmission ratio、wrench polytope、directional capability、redundancy parameterisation、trajectory-level difficulty 全串起来了。[Frontiers+1](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1442813/full)

然后读这 4 篇，理解“怎么从 score 走到 config / base assist”：

5.  **Woolfrey et al., 2019**  
    外力存在时，如何通过 null-space control 最小化 joint torque。[Springer](https://link.springer.com/article/10.1007/s10846-018-0964-8)
6.  **Kapusta & Kemp, 2019, TOC**  
    学“configuration scoring”和“高维配置问题不需要闭式求解”的思路，尤其是 task-centric reachability / manipulability。[Springer+1](https://link.springer.com/article/10.1007/s10514-019-09847-2)
7.  **Tugal et al., 2022**  
    直接看“通过 optimal base localization 提高 selected directions 上的 force transmission”。这篇和你的 base assist 关系非常近。[Springer](https://link.springer.com/article/10.1007/s10514-022-10050-z)
8.  **Zhang, 2025, manipulability optimization + force tracking**  
    看看 optimization-based mobile manipulation 社区已经把“manipulability 优化 + force tracking”推到了哪里。[Springer](https://link.springer.com/article/10.1007/s10846-025-02247-y)

最后再对照你现在的 4 个直接 baseline：

*   **Portela 2024**：whole-body force control 很强，但 reward 里主项还是 position/force tracking，arm torque limit 更像安全项，不是你的 explicit arm-feasibility objective。
*   **RoboDuet 2025**：arm-guided base coordination 接口很有启发，但 guidance 语义主要是 pose/workspace，不是 force margin。
*   **Zhi 2025**：统一 force-position 很强，但文中明确把 end-effector 和 base 分开建模，集成 derivation 留作 future work。
*   **FACET 2025**：teacher-student + force-adaptive 很值得借，但它自己也承认 multi-body infeasibility / mechanics 仍是局限。

一句话收束：

**你现在最该做的，不是求“全身最优构型”，而是先把“局部、方向相关的 force reserve”定义对。**  
在你的题目里，我最推荐把这个 reserve 定义成：

**当前构型下，沿  $F_{\text{cmd}}$  方向还能再加多少力，直到某个关节先撞上扭矩上限。**

这个量既足够物理，也足够便宜，还不会把你的 research 变成“先求闭式最优解”。  
如果你愿意，我下一条就直接把它写成一版**可抄进训练代码的 reward / observation / teacher 伪代码**。

## Prompt:
进一步细化你给我的 reward 设计建议，我就是机器人学的新人，所有符号，公式推导/意义都得解释清楚

## Response:
我会先按**准静态接触任务**来讲，把问题拆成两层：先用最小可用的物理量解释“方向上的 force 余量”怎么从末端力映射到关节负担，再把它一步步翻成你能直接实现的 reward / constraint / guidance。

我会先给你一版**最小可用 reward 公式**，再把每个符号、来源、物理意义，以及哪些该做 soft reward、哪些该做 hard constraint 逐项讲清楚。

Thought for 32m 10s

好，我这次不再只给“设计思路”，而是把它整理成一版**你可以真的照着实现**的 reward 方案，并把每个符号、每条公式、为什么这么写，都用**机器人学新手可读**的方式解释清楚。

我会先故意做一个**第一版可落地的简化**：

*   先只考虑**慢速接触任务**，比如推、压、拉、擦、维持接触。
*   先只考虑**末端 3D 力**，不先上 6D wrench（力+力矩）。
*   先只考虑 **arm force margin + 小范围 base assist**，不先做 full-body 最优控制。

这是合理的，因为在这类 quasi-static 任务里，文献通常先把完整阻抗模型

$$
F = K(x-x_{des}) + D(\dot x-\dot x_{des}) + M(\ddot x-\ddot x_{des})
$$

简化成主要由位置偏差决定的静态关系；Zhi 等也明确说了这种简化适用于擦拭、拔河这类慢速接触任务。Modern Robotics 在讲力控制时也同样指出，机器人在静止或很慢时，速度和加速度相关项可以先忽略。

Zhi 等 - 2025 - Learning a Unifi…

[现代机器人学](https://modernrobotics.northwestern.edu/nu-gm-book-resource/11-5-force-control/)

* * *

1\. 先把你真正要优化的东西说成一句话
====================

你现在的目标不是：

> 让机器人“能施力”。

而是：

> **在已经能把目标力做出来的前提下，偏好那个让 arm 在目标方向上“更有余量”的 whole-body 构型，同时尽量少动 base。**

这句话很重要，因为它直接决定 reward 不能只是“force error 越小越好”。  
否则 policy 很容易学成：

*   要么疯狂动 base，
*   要么为了减小 arm torque，干脆少出一点力，
*   要么在 regular workspace 里也无意义地调 base。

所以你需要的是一个**分层目标**：

1.  **先**把目标力做出来。
2.  **再**在这些成功解里，偏好 arm 更有余量的解。
3.  **再**在这些“有余量”的解里，偏好 base 改动更小的解。

这就是后面 reward 里“success-conditioned gate”的来源。

* * *

2\. 先定义所有符号
===========

我先把后面会出现的符号统一说明。

2.1 机器人状态
---------

### arm 相关

$$
q_a \in \mathbb{R}^{n_a}
$$
*   表示 arm 的关节角向量。
*    $n_a$  是 arm 关节数。比如 6-DoF arm，就有 6 个元素。

* * *

$$
\dot q_a \in \mathbb{R}^{n_a}
$$
*   表示 arm 各关节角速度。

* * *

$$
\tau^{cur} \in \mathbb{R}^{n_a}
$$
*   表示**当前时刻** arm 各关节的力矩。
*   在仿真里通常可以直接拿到。
*   在真实机器人上，可以用电机电流估计、控制器输出力矩估计，或者一个 learned estimator。

* * *

$$
\tau^{lim} \in \mathbb{R}^{n_a}
$$
*   表示各关节的力矩上限。
*   如果第  $i$  个关节最大允许力矩是 30 Nm，那么  $\tau^{lim}_i = 30$ 。

* * *

2.2 末端和力
--------

$$
x_{ee} \in \mathbb{R}^3
$$
*   end-effector 的位置。
*   第一版只看位置，不看姿态。

* * *

$$
F_{cmd} \in \mathbb{R}^3
$$
*   你想让末端施加的**目标力**。
*   例如：
    *   往前推墙： $F_{cmd}=[20,0,0]^T$  N
    *   往下压桌面： $F_{cmd}=[0,0,-15]^T$  N

* * *

$$
F_{true} \in \mathbb{R}^3
$$
*   仿真里可拿到的**真实接触力**。
*   **训练 reward 最好用这个**，因为它最干净。

* * *

$$
F_{est} \in \mathbb{R}^3
$$
*   policy 或 estimator 估计出来的接触力。
*   **部署时**只能靠这个。
*   训练时它适合进 observation，不适合作为唯一 reward 信号，因为会引入估计噪声。Zhi 等的 unified force-position policy 也是一边训练 state estimator，一边用仿真中的真实状态/外力来监督估计器。
    Zhi 等 - 2025 - Learning a Unifi…

* * *

2.3 Jacobian
------------

$$
J_v(q_a) \in \mathbb{R}^{3\times n_a}
$$
*   这是 arm 的**线速度 Jacobian**。
*   它把关节速度映射到末端线速度：
    
$$
\dot x_{ee} = J_v(q_a)\dot q_a
$$

你现在第一版只关心“末端线力”，所以用 **3× $n_a$ ** 的线 Jacobian 就够了。  
Modern Robotics 也明确建议把 Jacobian 的线速度部分和角速度部分分开，因为线速度/力和角速度/力矩单位不同，分开分析更清楚。[现代机器人学](https://modernrobotics.northwestern.edu/nu-gm-book-resource/5-4-manipulability/)

* * *

2.4 base 指令
-----------

$$
u_{user}
$$
*   用户原本想要的 base 命令。
*   比如只包含  $v_x, h, pitch, roll$  里的某些量。

* * *

$$
u_{assist}
$$
*   你的 policy 学出来的**小幅 base 补偿**。
*   它不是整个 base 动作，只是“在 user 命令基础上的微调”。

* * *

$$
u_{base}
$$
*   最终送给 base 的命令。
*   你可以写成：
    
$$
u_{base} = u_{user} + g_t\,u_{assist}
$$

其中  $g_t$  是一个 gate，决定“此刻要不要让 assist 生效”。

* * *

2.5 base 姿态
-----------

$$
\xi_{base}
$$
*   一个你自己定义的 base posture 向量。
*   第一版可以简单设成：
    
$$
\xi_{base} = [h,\ pitch,\ roll]^T
$$

也就是 base 高度、俯仰、横滚。

* * *

$$
\xi_{ref}
$$
*   一个参考 base 姿态。
*   可以取：
    *   接触刚建立时的 base posture；
    *   或者 stage-1 locomotion/WBC 的 nominal posture。

* * *

2.6 其他辅助量
---------

$$
c_t \in \{0,1\}
$$
*   contact indicator。
*   有接触时  $c_t=1$ ，否则  $c_t=0$ 。

* * *

$$
e_F
$$
*   force tracking error，目标力误差。

* * *

$$
\alpha_t
$$
*   success-conditioned gate。
*   它控制：**只有当力基本做出来后，margin reward 才真正开始发挥作用**。

* * *

3\. 你必须知道的两条物理关系
================

这两条就是整个 reward 的物理基础。

* * *

3.1 慢速接触任务里，可以先用 quasi-static 近似
--------------------------------

Zhi 等把 unified force-position control 写成阻抗形式：

$$
F = K(x-x_{des}) + D(\dot x-\dot x_{des}) + M(\ddot x-\ddot x_{des})
$$

并说明在擦拭、拔河这类慢速任务里，可以忽略阻尼和惯性项，得到更简单的静态近似。Modern Robotics 也在 force control 章节里说明，机器人静止或很慢时，可以先忽略速度和加速度相关项。

Zhi 等 - 2025 - Learning a Unifi…

[现代机器人学](https://modernrobotics.northwestern.edu/nu-gm-book-resource/11-5-force-control/)

这意味着：  
你第一版不需要先精通 full rigid-body dynamics，先做**慢速接触近似**就够了。

* * *

3.2 末端力和关节力矩的关系是 Jacobian 转置
----------------------------

这是最关键的一条：

$$
\tau = J_v(q_a)^T F
$$

含义是：

*    $F$  是末端施加的线力；
*    $J_v^T$  把这个末端力映射成各关节需要承受的力矩；
*    $\tau$  就是这些关节负担。

Modern Robotics 通过功率守恒推导了这个关系：关节侧功率  $\dot q^T\tau$  等于末端侧功率  $v^T f$ ，因此得到 Jacobian 把速度映射过去，也把力/力矩用转置映射回来。它同时指出：某些构型下机器人在某些方向上更容易施力、另一些方向上更难施力；这正是 force ellipsoid / manipulability ellipsoid 背后的物理意义。[现代机器人学+1](https://modernrobotics.northwestern.edu/nu-gm-book-resource/velocity-kinematics-and-statics/)

**对你来说，最重要的直觉是：**

同样一个 20N 的目标力，  
在不同 arm 构型下， $J_v^T$  不同，所以需要的关节力矩也不同。  
这就是“同一个 target position，对某些构型来说更容易施力”的来源。

* * *

4\. 先定义“沿某个方向的 force 余量”
========================

这一步是整个设计的核心。

你之前最困惑的是：

> 我怎么知道 arm 在某个方向上还有没有余量？

答案是：

> 不需要先算“全局最优构型”，只需要在当前构型下，算**如果我沿目标方向再加一点力，哪个关节会最先爆掉**。

这就是**directional force margin**。

* * *

4.1 第一步：把目标力方向变成单位向量
--------------------

定义

$$
d = \frac{F_{cmd}}{\|F_{cmd}\|+\varepsilon}
$$

这里：

*    $d\in\mathbb{R}^3$  是一个单位方向向量；
*    $\|F_{cmd}\|$  是目标力大小；
*    $\varepsilon$  是一个很小的数，防止除零。

如果  $F_{cmd}=0$ ，就没有“目标方向”可言。  
这时你可以直接规定：**不计算 margin reward**。

* * *

4.2 第二步：看“沿方向  $d$  多加 1N”会让哪些关节更吃力
-----------------------------------

定义

$$
g = J_v(q_a)^T d
$$

其中

$$
g \in \mathbb{R}^{n_a}
$$

第  $i$  个元素  $g_i$  的意义是：

> 如果我沿目标方向  $d$  额外增加 1N 力，第  $i$  个关节力矩会变化多少。

所以：

*    $g_i$  大：说明这个关节对该方向力很敏感，很容易先吃满。
*    $g_i$  小：说明该关节对该方向力不敏感。

* * *

4.3 一个几何近似版：先不看当前已有负载，只看构型本身
----------------------------

这是一个**最简单、最便宜**的方向余量 proxy，适合刚开始理解。

先定义一个“单位关节力矩球”：

$$
\Delta\tau^T W_\tau \Delta\tau \le 1
$$

其中

$$
W_\tau = \mathrm{diag}\left(\frac{1}{(\bar\tau_1)^2},\frac{1}{(\bar\tau_2)^2},\dots,\frac{1}{(\bar\tau_{n_a})^2}\right)
$$

这里：

*    $\Delta\tau$  是“额外增加”的关节力矩；
*    $\bar\tau_i$  是第  $i$  个关节允许承担的力矩预算；
*    $W_\tau$  是一个对角矩阵，用来把不同关节的 torque limit 纳入同一个归一化空间。

如果你沿目标方向加一个额外末端力

$$
\Delta F = \lambda d
$$

其中  $\lambda$  是“额外多加了多少牛顿”，那么

$$
\Delta\tau = J_v^T\Delta F = \lambda J_v^T d
$$

代回去：

$$
(\lambda J_v^Td)^T W_\tau (\lambda J_v^T d)\le 1
$$

整理得：

$$
\lambda^2\, d^T J_v W_\tau J_v^T d \le 1
$$

因此可得这个构型在方向  $d$  上的大致力半径：

$$
\lambda^{ellip}_{max} = \frac{1}{\sqrt{d^T J_v W_\tau J_v^T d}}
$$

### 这个量是什么意思？

它表示：

> **如果只考虑关节力矩上限，而不考虑当前已经背了多少负载，那么在当前构型下，沿方向  $d$  大致还能施加多大额外力。**

这其实就是 force ellipsoid / transmission ratio 思路的方向化版本。Modern Robotics 解释了 force ellipsoid 如何描述不同方向上的施力能力；Frontiers 那篇移动机械臂 wrench capability 论文也明确指出，对于“只关心某个目标方向”的任务，方向相关的 transmission ratio / directional capability 比单纯看 ellipsoid 体积更有意义。[现代机器人学+1](https://modernrobotics.northwestern.edu/nu-gm-book-resource/5-4-manipulability/)

### 但它有什么缺点？

它**没看当前已经有多累**。  
也就是说，如果一个关节现在已经快到上限了，这个公式还不知道。

所以这个量适合做：

*   geometry-only 的辅助项，
*   teacher 的快速打分，
*   或 warm start。

但如果你真想表达“当前这一刻 arm 还有多少余量”，你需要下面这个更强的版本。

* * *

4.4 更实用的版本：当前状态下的精确方向余量
-----------------------

这才是我最推荐你真正放进 reward 的核心量。

### 设当前每个关节已经承担了力矩

$$
\tau^{cur}_i
$$

并且它的对称力矩上限是

$$
|\tau_i| \le \tau_i^{lim}
$$

如果你再沿目标方向加一个额外力  $\lambda d$ ，那么第  $i$  个关节的新力矩近似变成：

$$
\tau_i(\lambda)=\tau_i^{cur} + \lambda g_i
$$

其中  $g_i$  就是前面算出来的  $J_v^T d$  的第  $i$  个元素。

我们希望所有关节都不超限：

$$
|\tau_i^{cur} + \lambda g_i| \le \tau_i^{lim}
$$

现在分情况看：

### 情况 A： $g_i > 0$ 

说明沿目标方向继续加力，会让该关节力矩往“正方向”增长。  
它还能承受的额外力是：

$$
\mu_i = \frac{\tau_i^{lim} - \tau_i^{cur}}{g_i}
$$

* * *

### 情况 B： $g_i < 0$ 

说明沿目标方向继续加力，会让该关节力矩往“负方向”增长。  
它还能承受的额外力是：

$$
\mu_i = \frac{\tau_i^{lim} + \tau_i^{cur}}{-g_i}
$$

* * *

### 情况 C： $g_i = 0$ 

说明目标方向上的额外力不会增加这个关节的负担。  
所以：

$$
\mu_i = +\infty
$$

* * *

### 最终，真正的方向余量定义为：

$$
\mu_{dir} = \min_i \mu_i
$$

这是什么意思？

> **沿目标方向继续加力时，最先撞上 torque limit 的那个关节，决定了整个 arm 还能再加多少力。**

这就是你要找的“这个构型在当前方向上还有多少 force reserve”。

* * *

4.5 为什么这个量非常适合你的 research
-------------------------

因为它正好对应你的论文 claim：

*   目标位置相同；
*   目标接触力方向相同；
*   但不同 arm/base 构型会导致不同的  $J_v$  和不同的  $\tau^{cur}$ ；
*   因此  $\mu_{dir}$  不同。

**谁的  $\mu_{dir}$  大，谁就是对当前 force task 更“舒服”的构型。**

而且注意：

> 你并没有预先算出“全局最优构型”。

你只是给当前状态打了一个**局部、方向相关**的分数。  
RL 会通过探索去发现：哪些 base 微调能让这个分数变大。

这跟“我已经把最优 IK 解出来了”完全不是一回事。  
移动机械臂 wrench optimization 文献本身也普遍不是直接在全关节空间做闭式全局求解，而是把冗余变量压到低维 redundancy space 再做方向相关优化。Frontiers 2025 这篇就明确把问题写成低维参数化冗余空间上的 bi-level optimization。[Frontiers](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2024.1442813/full)

* * *

5\. 现在开始设计 reward
=================

接下来是最重要的部分。

* * *

5.1 第一项：force tracking reward
-----------------------------

先定义归一化后的力误差：

$$
\tilde F_{cmd} = \frac{F_{cmd}}{F_{scale}},\qquad \tilde F_{true} = \frac{F_{true}}{F_{scale}}
$$

这里  $F_{scale}$  是一个你自己选的 force normalization 常数，比如：

*   20 N
*   30 N
*   50 N

看你的任务量级。

然后定义

$$
e_F = \|\tilde F_{true} - \tilde F_{cmd}\|_2
$$

含义：

*    $e_F$  越小，说明真实接触力越接近目标力。

最简单的 task reward 可以写成：

$$
r_{force} = \exp\left(-\frac{e_F^2}{\sigma_F^2}\right)
$$

### 每个符号是什么意思？

*    $\exp(\cdot)$  是指数函数。
*    $\sigma_F$  是“误差容忍尺度”。
    *   小：reward 对误差更敏感。
    *   大：reward 更宽松。

### 为什么用指数形式？

因为它有三个优点：

1.  平滑；
2.  有界，通常在  $0\sim1$ ；
3.  误差小的时候梯度比较友好。

如果你更喜欢直观一点，也可以用：

$$
r_{force}=1-e_F
$$

但前提是你先把  $e_F$  clip 到  $[0,1]$  里。  
第一版我还是更推荐指数形式。

* * *

5.2 为什么不能直接把 force reward 和 margin reward 硬加起来
----------------------------------------------

这是最容易“把 reward 设计歪”的地方。

如果你直接写：

$$
r = r_{force} + \lambda r_{margin}
$$

policy 可能会学到：

> “我少出一点力，虽然 force 没完全达标，但 torque 更小，margin 反而更高。”

这不是你想要的。

你想要的是：

> **先达标，再比较谁更省 arm。**

所以需要一个“力达标后才启用 tie-breaker”的 gate。

* * *

5.3 第二项：success-conditioned gate
--------------------------------

定义：

$$
\alpha_t = c_t \cdot \sigma\!\left(\frac{\varepsilon_F - e_F}{k_F}\right)
$$

这里：

*    $c_t\in\{0,1\}$ ：有无接触。
*    $\sigma(z)=\frac{1}{1+e^{-z}}$ ：sigmoid 函数。
*    $\varepsilon_F$ ：你认为“力基本达标”的误差阈值。
*    $k_F$ ：过渡有多软。

### 这个式子怎么理解？

先看 sigmoid 里面：

$$
\frac{\varepsilon_F - e_F}{k_F}
$$
*   如果  $e_F$  很大，说明力还没做出来，那么这个值是负的，sigmoid 接近 0。
*   如果  $e_F$  小于  $\varepsilon_F$ ，说明力已经比较接近目标，那么这个值是正的，sigmoid 接近 1。

再乘上  $c_t$ ：

*   没接触时， $\alpha_t=0$ 
*   有接触且力误差已经小了， $\alpha_t\approx1$ 

### 直觉

*   **没接触**：先别谈 force-aware。
*   **力还差很远**：先把力做出来。
*   **力差不多做出来了**：这时再比较谁更省 arm、谁更少动 base。

这就是“先主任务，再 tie-breaker”。

* * *

5.4 第三项：directional margin reward
---------------------------------

现在把刚才定义的  $\mu_{dir}$  变成 reward。

最简单的写法：

$$
r_{margin} = \tanh\left(\frac{\mu_{dir}}{F_{scale}}\right)
$$

这里：

*    $\tanh(\cdot)$  是双曲正切；
*   当  $\mu_{dir}$  很小，reward 也小；
*   当  $\mu_{dir}$  已经很大，它会逐渐饱和，不再无限鼓励。

### 为什么要用  $\tanh$ 

因为如果你直接用  $\mu_{dir}$  本身，policy 可能会过度追求极大 margin，导致 base 动得太夸张。  
 $\tanh$  会让“很大很大”的 margin 不再比“已经足够大”的 margin 好太多。

* * *

5.5 一个很有用的评估指标：relative reserve
-------------------------------

虽然 reward 我建议用  $\tanh(\mu_{dir}/F_{scale})$ ，  
但你做实验时还可以记录：

$$
\rho_{reserve} = \frac{\mu_{dir}}{\|F_{cmd}\|+\varepsilon}
$$

它的意思是：

> 当前目标力之外，你还有多少“相对余量”。

例如：

*    $\rho_{reserve}=0.2$ ：说明你基本快到头了。
*    $\rho_{reserve}=2.0$ ：说明你还能再沿这个方向多出两倍当前目标力。

这个量很适合作为论文里的 diagnostic metric。

* * *

5.6 第四项：joint-limit margin reward
---------------------------------

只靠 torque margin 有时不够。  
因为有些构型 torque 还没爆，但几何上已经很差，比如某个关节已经快到限位了。

定义每个关节距离最近限位的距离：

$$
\delta_i = \min(q_{a,i}-q_i^{min},\ q_i^{max}-q_{a,i})
$$

这里：

*    $q_i^{min}, q_i^{max}$  是关节角下限和上限；
*    $\delta_i$  越小，说明这个关节越靠近限位。

然后定义归一化 margin：

$$
r_{jlimit} = \frac{1}{n_a} \sum_{i=1}^{n_a} \mathrm{clip}\!\left(\frac{\delta_i}{\delta_i^{safe}},\,0,\,1\right)
$$

这里：

*    $\delta_i^{safe}$  是你设定的“安全缓冲区”，比如 10° 或 15°；
*   clip 表示把值截到  $[0,1]$ 。

### 直觉

*   离限位很远：这一项接近 1。
*   快撞限位：这一项接近 0。

* * *

5.7 第五项：minimal assist penalty
------------------------------

你不希望 base 总是乱动，所以要罚 assist。

先把 assist 动作归一化。  
假设你第一版 action 先只开两个维度：

$$
u_{assist} = [\Delta v_x,\ \Delta h]^T
$$

那么定义归一化动作：

$$
\tilde u_{assist} = \left[ \frac{\Delta v_x}{v_x^{max}}, \frac{\Delta h}{h^{max}} \right]^T
$$

如果以后加 pitch/roll：

$$
\tilde u_{assist} = \left[ \frac{\Delta v_x}{v_x^{max}}, \frac{\Delta h}{h^{max}}, \frac{\Delta pitch}{\theta^{max}}, \frac{\Delta roll}{\phi^{max}} \right]^T
$$

然后 penalty：

$$
r_{assist} = \|\tilde u_{assist}\|_2^2
$$

### 为什么先归一化再平方？

因为不同维度单位不同：

*   速度是 m/s
*   高度是 m
*   角度是 rad

你不能把这些原始数值直接平方相加。  
**归一化是非常重要的工程习惯。**

* * *

5.8 第六项：anchor penalty
----------------------

这是为了防止 policy 学出一个“全局看起来很舒服、但总是奇怪地歪着”的 base 姿态。

定义归一化后的 base posture：

$$
\tilde\xi_{base} = \left[ \frac{h}{h^{range}}, \frac{pitch}{\theta^{range}}, \frac{roll}{\phi^{range}} \right]^T
$$

参考姿态：

$$
\tilde\xi_{ref} = \left[ \frac{h_{ref}}{h^{range}}, \frac{pitch_{ref}}{\theta^{range}}, \frac{roll_{ref}}{\phi^{range}} \right]^T
$$

然后：

$$
r_{anchor} = \|\tilde\xi_{base} - \tilde\xi_{ref}\|_2^2
$$

### 这项的意义

它不是说 base 永远不能变。  
而是说：

> **除非真的能换来更好的 force reserve，否则不要离开 nominal posture 太远。**

* * *

5.9 第七项：smoothness penalty
--------------------------

你还需要防止 assist 抖动。

$$
r_{smooth} = \|\tilde u_{assist,t} - \tilde u_{assist,t-1}\|_2^2
$$

含义：

*   assist 每一步变化太大，就罚。

如果你后面发现还抖，可以再加二阶差分：

$$
\|\tilde u_t - 2\tilde u_{t-1} + \tilde u_{t-2}\|^2
$$

但第一版先用一阶差分就够了。

* * *

5.10 第八项：safety penalty
-----------------------

至少包括三类：

### 滑移

$$
\mathbf{1}_{slip}
$$
*   足端滑移就罚。

### 跌倒

$$
\mathbf{1}_{fall}
$$
*   跌倒直接大罚，甚至终止 episode。

### 持续接近 torque saturation

定义：

$$
s_\tau = \frac{1}{n_a} \sum_{i=1}^{n_a} \mathbf{1}\left(|\tau_i^{cur}| > \eta \tau_i^{lim}\right)
$$

这里  $\eta$  通常可以取 0.9。  
表示“多少比例的关节已经超过 90% 扭矩上限”。

然后：

$$
r_{safety} = \lambda_{slip}\mathbf{1}_{slip} + \lambda_{fall}\mathbf{1}_{fall} + \lambda_{sat}s_\tau
$$

* * *

6\. 一版我最建议你先实现的总 reward
=======================

如果你是新手，我建议第一版不要写太多项。  
先上这个：

$$
\boxed{ r_t = w_F r_{force} + \alpha_t \Big( w_M r_{margin} + w_Q r_{jlimit} - w_U r_{assist} - w_A r_{anchor} \Big) - w_{Sm} r_{smooth} - w_S r_{safety} }
$$

这是一个很干净的 starter reward。

* * *

6.1 每一项再翻译成大白话
--------------

###  $w_F r_{force}$ 

*   主任务。
*   不把目标力做出来，别谈后面的“更优构型”。

* * *

###  $\alpha_t(\cdots)$ 

*   这是 tie-breaker gate。
*   只有接触成立、而且 force error 已经不大时，后面的 “更有余量、更少动 base” 才真正重要。

* * *

###  $w_M r_{margin}$ 

*   这是你的核心 novelty。
*   同样都能达到当前目标力时，偏好方向余量更大的构型。

* * *

###  $w_Q r_{jlimit}$ 

*   补充约束。
*   防止策略跑到关节快顶死的几何坏姿态。

* * *

###  $-w_U r_{assist}$ 

*   惩罚 assist 过大。
*   防止策略为了舒服而过度移动 base。

* * *

###  $-w_A r_{anchor}$ 

*   惩罚离 nominal base posture 太远。
*   进一步保证“只在值得时才改构型”。

* * *

###  $-w_{Sm} r_{smooth}$ 

*   不要抖。

* * *

###  $-w_S r_{safety}$ 

*   别滑、别倒、别长时间爆扭矩。

* * *

7\. 一个具体数值例子，让你感受到  $\mu_{dir}$  在算什么
=====================================

假设你现在做“向前推墙”任务。

目标力：

$$
F_{cmd} = [20, 0, 0]^T \text{ N}
$$

所以单位方向：

$$
d = [1,0,0]^T
$$

* * *

构型 A
----

假设当前 arm 关节力矩是：

$$
\tau^{cur} = [8,\ 20,\ 5]^T \text{ Nm}
$$

各关节上限：

$$
\tau^{lim} = [30,\ 30,\ 20]^T \text{ Nm}
$$

并且计算得到：

$$
g = J_v^T d = [0.2,\ 0.9,\ 0.1]^T \text{ Nm/N}
$$

意思是：

*   每多推 1N，
*   第 1 个关节多承担 0.2 Nm，
*   第 2 个关节多承担 0.9 Nm，
*   第 3 个关节多承担 0.1 Nm。

于是：

$$
\mu_1 = \frac{30-8}{0.2}=110
$$
 
$$
\mu_2 = \frac{30-20}{0.9}\approx 11.1
$$
 
$$
\mu_3 = \frac{20-5}{0.1}=150
$$

所以

$$
\mu_{dir} = \min(110,11.1,150)=11.1 \text{ N}
$$

含义：

> 在当前构型下，沿着目标方向最多只能再加约 11.1N，第二个关节会先撞上上限。

* * *

构型 B：base 微微前移并下沉一点
-------------------

现在假设经过 base 小幅调整后，

$$
\tau^{cur} = [7,\ 17,\ 5]^T
$$

而且

$$
g = J_v^T d = [0.15,\ 0.5,\ 0.08]^T
$$

那么：

$$
\mu_1 = \frac{30-7}{0.15}\approx 153
$$
 
$$
\mu_2 = \frac{30-17}{0.5}=26
$$
 
$$
\mu_3 = \frac{20-5}{0.08}\approx 187.5
$$

于是：

$$
\mu_{dir}=26\text{ N}
$$

这说明：

*   target position 没变，
*   target force direction 没变，
*   但 base 微调以后，arm 在这个方向上的 reserve 从 11.1N 提升到了 26N。

这就是你想要 reward 自动偏好的行为。

* * *

8\. 一个最小可行实现版本
==============

如果你现在就要开写代码，我建议你按这个顺序来。

第 1 步：先只做这几个 observation
------------------------

给 policy 的输入里，至少放：

*    $F_{cmd}$ 
*    $F_{est}$ 
*    $\Delta F = F_{cmd} - F_{est}$ 
*   contact flag
*    $|\tau^{cur}|/\tau^{lim}$ 
*    $q_a$  和 joint-limit distance
*    $u_{user}$ 
*   base posture  $(h,pitch,roll)$ 

如果你能算出  $\mu_{dir}$ ，也可以把它喂给 policy。  
但第一版不喂也可以，只把它用于 reward。

* * *

第 2 步：先只开低维 assist action
-------------------------

别一上来就上全 DOF。  
先：

$$
u_{assist}=[\Delta v_x,\ \Delta h]
$$

就够了。

如果这版有效，再加 pitch/roll。

* * *

第 3 步：训练 reward 用仿真真值，不用估计值
---------------------------

这是一个非常重要的工程建议。

### 训练时

*   用  $F_{true}$  算  $r_{force}$ 
*   用仿真里的  $\tau^{cur}$  算  $\mu_{dir}$ 

### observation 给 policy 时

*   可以只给  $F_{est}$ 、proprioception、history

这样做的好处是：

*   reward 干净；
*   policy 仍然逼自己学会从有限观测里推断接触状态。

这跟 Zhi 等的做法是一致的：他们同时训练 force estimator，并用仿真中的真实量去监督 estimator。

Zhi 等 - 2025 - Learning a Unifi…

* * *

9\. 一个我建议你实际使用的初始版本
===================

如果你不想一开始就太复杂，我建议第一版真的就上下面这一版：

$$
r_t = 1.0\,r_{force} + \alpha_t \Big( 0.2\,r_{margin} + 0.05\,r_{jlimit} - 0.03\,r_{assist} - 0.02\,r_{anchor} \Big) - 0.01\,r_{smooth} - r_{safety}
$$

注意：

*   这不是“正确答案”；
*   这是**归一化做对之后**的一组合理初值。

关键不在于绝对数值，而在于：

1.  所有项都先归一化到大致  $O(1)$ ；
2.  先保证  $r_{force}$  是主项；
3.   $r_{margin}$  是 force 达标后的 tie-breaker；
4.  assist / anchor / smooth 是 regularizer。

* * *

10\. 哪些东西第一版不要做
===============

这部分我也直接告诉你，不然你很容易把系统搞得太复杂。

10.1 不要第一版就做 full dynamic manipulability
----------------------------------------

Yoshikawa 1985 的 dynamic manipulability 讨论的是“在 joint torque 约束下，末端可实现的加速度集合”；Azad 等 2019 又进一步强调了 weighting matrix 的选择会显著影响 dynamic manipulability 的物理意义。这个方向当然重要，但它更适合高速、动态、冲击型任务。你当前第一版做 slow contact，先不用上。[J-STAGE+1](https://www.jstage.jst.go.jp/article/sicetr1965/21/9/21_9_970/_article/-char/en)

* * *

10.2 不要第一版就求“全局最优构型”
--------------------

你不需要先 enumerate 所有 IK 解。  
你只需要当前时刻的**局部方向余量**  $\mu_{dir}$ 。

这已经足够让 RL 学会：

*   哪些 base 微调让 force reserve 变大，
*   哪些 base 微调没用，
*   什么时候不该动。

* * *

10.3 不要第一版就把 6D wrench、multiple contacts、full-body Jacobian 全上
--------------------------------------------------------------

先把：

*   3D 线力
*   低维 assist
*   quasi-static reward

跑通。

因为 reward 一旦太复杂，你就分不清到底是“方法没用”还是“实现没收敛”。

* * *

11\. 这版 reward 的本质是什么
=====================

最后我用一句最短的话，把整套设计再收一下。

你现在的 reward 其实是在近似下面这个**层级优化**：

$$
\text{先最小化 force error}
$$

然后在“force error 已经足够小”的解里：

$$
\text{最大化 directional force reserve}
$$

再在这些解里：

$$
\text{最小化 base intervention}
$$

这就是为什么我们要写：

*    $r_{force}$ ：主任务
*    $\alpha_t$ ：分层 gate
*    $r_{margin}$ ：arm force-aware 核心项
*    $r_{assist}, r_{anchor}, r_{smooth}$ ：minimal intervention
*    $r_{safety}$ ：安全约束

* * *

如果你愿意，下一条我直接把这整套东西继续往前推成两份你能直接用的内容：

一份是**训练伪代码 / Python 风格函数**，  
另一份是**适合放进论文 Method 部分的正式数学表述**。

## Prompt:
给我适合放进论文 Method 部分的正式数学表述。

## Response:
我先把前面那套 reward 设计整理成论文 Method 可直接使用的正式表述：统一符号后依次给出问题定义、base-assist 参数化、directional force reserve、分层奖励、约束与训练目标。

我也会对齐你文档里的接口定义，并按论文小节结构直接展开，而不再停留在直觉解释。

Thought for 23m 37s

下面给你一版**可以直接放进论文 Method 部分**的正式数学表述。我先给“可直接粘贴版”，再给“符号释义版”。为便于第一版落地，这里采用**慢速接触 / 准静态**设定，把问题写成“位置–力联合跟踪 + arm 方向余量最大化 + 最小 base assist”的形式；这种写法和近期 unified force-position policy、impedance-inspired force-aware locomotion/manipulation 的接口是一致的。

Zhi 等 - 2025 - Learning a Unifi…

Xu 等 - 2025 - FACET Force-Adapt…

* * *

3 Method
========

3.1 Problem formulation
-----------------------

We consider a legged manipulator that receives, at each time step  $t$ , a desired end-effector position  $x_t^\star \in \mathbb{R}^3$ , a desired contact force  $F_t^\star \in \mathbb{R}^3$ , and a nominal user/base command  $u_t^{\mathrm{usr}}$ . Our goal is to learn a policy that, among multiple whole-body configurations that achieve comparable position and force tracking performance, prefers the one that admits larger **arm-side directional force reserve** while using as little base intervention as possible.

Let  $q_t^a \in \mathbb{R}^{n_a}$  denote the arm joint configuration, and let  $\xi_t^b \in \mathbb{R}^{m_b}$  denote a low-dimensional base posture variable (e.g., height, pitch, and roll). We parameterize base assistance in a low-dimensional subspace:

$$
u_t^b = u_t^{\mathrm{usr}} + \eta_t\, u_t^{\mathrm{as}}, \tag{1}
$$

where  $u_t^{\mathrm{as}} \in \mathbb{R}^{m_u}$  is the learned assist action, and  $\eta_t \in [0,1]$  is a state-dependent assist gate.

The policy outputs

$$
(a_t^{a},\,u_t^{\mathrm{as}},\,\eta_t) = \pi_\theta(o_t), \tag{2}
$$

where  $a_t^{a}$  is the arm control action and  $o_t$  is the observation. Unless otherwise stated, all position and force quantities are expressed in the same task frame.

The desired behavior can be written as the following constrained preference problem:

$$
\begin{aligned} \max_{\pi_\theta}\quad & \mathbb{E}_{\pi_\theta}\!\left[\sum_{t=0}^{T-1}\gamma^t \Big( \mathcal{M}_t -\lambda_u\|\tilde u_t^{\mathrm{as}}\|_2^2 -\lambda_v\|\widetilde{u_t^{b}-u_t^{\mathrm{usr}}}\|_2^2 -\lambda_p\|\tilde \xi_t^b-\tilde \xi_{\mathrm{ref}}^b\|_2^2 \Big)\right] \\ \text{s.t.}\quad & \|x_t^{ee}-x_t^\star\|_2 \le \varepsilon_x, \\ & \|F_t-F_t^\star\|_2 \le \varepsilon_F, \\ & \text{no slip, no fall, and no sustained actuator saturation.} \end{aligned} \tag{3}
$$

Here  $\mathcal{M}_t$  denotes the arm-side directional force reserve defined below. Since directly optimizing Eq. (3) with hard constraints is inconvenient in RL, we implement it with a soft reward and a success-conditioned gate.

* * *

3.2 Directional arm force reserve
---------------------------------

To quantify how much additional force the arm can still generate **along the commanded force direction**, we define a directional reserve score based on the arm Jacobian.

Let  $J_a(q_t)\in\mathbb{R}^{3\times n_a}$  denote the **translational arm Jacobian** of the end-effector with respect to arm joints only. Under the standard quasi-static relation, end-effector force and joint torque are related by

$$
\tau_t^a = J_a(q_t)^\top F_t, \tag{4}
$$

which is the standard Jacobian-transpose static mapping between endpoint force and joint torque. [modernrobotics.northwestern.edu](https://modernrobotics.northwestern.edu/nu-gm-book-resource/velocity-kinematics-and-statics/)

We define the commanded force direction as

$$
d_t = \frac{F_t^\star}{\|F_t^\star\|_2+\epsilon}, \qquad d_t\in\mathbb{R}^3, \tag{5}
$$

where  $\epsilon>0$  avoids division by zero. The corresponding unit-direction transmission vector is

$$
g_t = J_a(q_t)^\top d_t \in \mathbb{R}^{n_a}. \tag{6}
$$

The  $i$ \-th entry  $g_{t,i}$  measures the incremental torque induced at joint  $i$  when applying a **unit additional force** along direction  $d_t$ . Let the current arm actuator torque be  $\tau_{t,i}^a$ , and let the allowable torque interval be  $[\tau_i^{\min},\,\tau_i^{\max}]$ . The maximum additional force along direction  $d_t$  before joint  $i$  saturates is

$$
\mu_{i,t} = \begin{cases} \dfrac{\tau_i^{\max}-\tau_{t,i}^a}{g_{t,i}}, & g_{t,i}>0,\\[8pt] \dfrac{\tau_i^{\min}-\tau_{t,i}^a}{g_{t,i}}, & g_{t,i}<0,\\[8pt] +\infty, & g_{t,i}=0. \end{cases} \tag{7}
$$

We retain only positive admissible values and define the **directional force reserve** as

$$
\mu_t = \min_{i:\,\mu_{i,t}>0}\mu_{i,t}, \qquad \mu_t := 0 \ \text{if no positive admissible value exists}. \tag{8}
$$

Finally, we normalize the reserve score as

$$
\bar\mu_t = \tanh\!\left(\frac{\mu_t}{F_{\mathrm{scale}}}\right), \tag{9}
$$

where  $F_{\mathrm{scale}}>0$  is a task-dependent normalization constant.

We deliberately compute this reserve using the **arm sub-Jacobian**  $J_a$ , rather than a full-body Jacobian, because our objective is explicitly to improve **arm-side loadability**. Base reconfiguration influences  $\bar\mu_t$  implicitly by changing the whole-body geometry and thus the arm Jacobian and current arm torque.

* * *

3.3 Task terms and regularization terms
---------------------------------------

### Position and force tracking

We define normalized task errors

$$
e_t^x = \frac{\|x_t^{ee}-x_t^\star\|_2}{x_{\mathrm{scale}}}, \qquad e_t^F = \frac{\|F_t-F_t^\star\|_2}{F_{\mathrm{scale}}}, \tag{10}
$$

and corresponding dense rewards

$$
r_t^x = \exp\!\left(-\frac{(e_t^x)^2}{\sigma_x^2}\right), \qquad r_t^F = \exp\!\left(-\frac{(e_t^F)^2}{\sigma_F^2}\right). \tag{11}
$$

### Success-conditioned gate

To ensure that arm-feasibility optimization acts as a **tie-breaker** rather than weakening the primary task, we activate it only when the robot is already close to both the target position and target force.

We define a binary contact indicator

$$
c_t = \mathbf{1}\!\left[\|F_t\|_2 > F_{\mathrm{th}}\right], \tag{12}
$$

and the success gate

$$
\alpha_t = c_t\, \sigma\!\left(\frac{\varepsilon_x-e_t^x}{k_x}\right) \sigma\!\left(\frac{\varepsilon_F-e_t^F}{k_F}\right), \tag{13}
$$

where  $\sigma(\cdot)$  is the logistic sigmoid, and  $\varepsilon_x,\varepsilon_F,k_x,k_F>0$  are hyperparameters.

Thus, the reserve maximization term is emphasized only after the robot has approximately reached the target and established the desired contact.

### Joint-limit margin

To avoid geometrically poor arm configurations, we define the distance to the nearest joint limit as

$$
\delta_{i,t} = \min\big(q_{t,i}^a-q_i^{\min},\ q_i^{\max}-q_{t,i}^a\big), \tag{14}
$$

and the normalized joint-limit margin reward as

$$
r_t^Q = \frac{1}{n_a} \sum_{i=1}^{n_a} \operatorname{clip}\!\left(\frac{\delta_{i,t}}{\delta_i^{\mathrm{safe}}},\,0,\,1\right), \tag{15}
$$

where  $\delta_i^{\mathrm{safe}}>0$  is a safety margin.

### Minimal-assist regularization

We regularize base assistance by penalizing both its magnitude and its deviation from the user command:

$$
r_t^U = \|\tilde u_t^{\mathrm{as}}\|_2^2, \qquad r_t^V = \|\widetilde{u_t^b-u_t^{\mathrm{usr}}}\|_2^2. \tag{16}
$$

### Anchor regularization

To prevent the policy from drifting toward globally comfortable but unnecessarily displaced base postures, we anchor the base around a reference posture  $\xi_{\mathrm{ref}}^b$ , e.g., a stage-1 nominal posture or the posture at contact establishment:

$$
r_t^P = \|\tilde \xi_t^b-\tilde \xi_{\mathrm{ref}}^b\|_2^2. \tag{17}
$$

### Smoothness and safety

We penalize rapid variation of base assistance:

$$
r_t^{\mathrm{Sm}} = \|\tilde u_t^{\mathrm{as}}-\tilde u_{t-1}^{\mathrm{as}}\|_2^2. \tag{18}
$$

We also penalize unsafe events, including slip, fall, and sustained near-saturation of arm actuators:

$$
s_t^\tau = \frac{1}{n_a} \sum_{i=1}^{n_a} \mathbf{1}\!\left[|\tau_{t,i}^a|>\eta_\tau \tau_i^{\max}\right], \tag{19}
$$
 
$$
r_t^S = \lambda_{\mathrm{slip}}\mathbf{1}_{\mathrm{slip}} + \lambda_{\mathrm{fall}}\mathbf{1}_{\mathrm{fall}} + \lambda_{\mathrm{sat}} s_t^\tau. \tag{20}
$$

* * *

3.4 Overall reward
------------------

The final reward is

$$
\boxed{ r_t = w_x r_t^x + w_F r_t^F + \alpha_t \Big( w_M \bar\mu_t + w_Q r_t^Q - w_U r_t^U - w_V r_t^V - w_P r_t^P \Big) - w_{\mathrm{Sm}} r_t^{\mathrm{Sm}} - w_S r_t^S } \tag{21}
$$

The policy is trained to maximize the discounted return

$$
J(\theta)= \mathbb{E}_{\pi_\theta} \left[\sum_{t=0}^{T-1}\gamma^t r_t\right]. \tag{22}
$$

Eq. (21) can be interpreted as a soft relaxation of Eq. (3):  
 $r_t^x$  and  $r_t^F$  enforce the primary task, while  $\bar\mu_t$  acts as a **force-aware tie-breaker** among equally feasible solutions, and  $r_t^U,r_t^V,r_t^P$  ensure that such preference is realized through **minimal base intervention**.

* * *

3.5 Two-stage training
----------------------

Directly learning reaching, contact formation, force regulation, and redundancy resolution from scratch is difficult. We therefore adopt a two-stage training scheme, inspired by recent whole-body coordination and teacher-student/two-stage force-aware training paradigms.

Pan 等 - 2025 - RoboDuet Learnin…

Xu 等 - 2025 - FACET Force-Adapt…

In **Stage I**, we disable base assistance by setting  $\eta_t=0$ , and optimize only the nominal reaching/stability objective:

$$
r_t^{(1)} = w_x r_t^x - w_S r_t^S. \tag{23}
$$

In **Stage II**, we enable the assist channel and optimize the full reward in Eq. (21):

$$
r_t^{(2)} = r_t. \tag{24}
$$

This decomposition encourages the policy to first acquire stable reaching/locomotion priors, and then learn when and how to use base assistance to improve directional force reserve.

* * *

3.6 Optional weak guidance for base assistance
----------------------------------------------

To further reduce exploration difficulty, we optionally introduce a **weak guidance** signal only for the assist action  $u_t^{\mathrm{as}}$ . Rather than solving a full-body optimization problem, we search over a small candidate set in the low-dimensional assist space:

$$
\mathcal A = \{0,\ \pm \Delta e_1,\ \pm \Delta e_2,\ \dots,\ \pm \Delta e_{m_u}\}, \tag{25}
$$

where  $e_j$  is the  $j$ \-th basis vector and  $\Delta>0$  is a small step.

For each candidate  $a\in\mathcal A$ , we define a one-step score

$$
S_t(a) = \bar\mu_t^{+}(a) + \lambda_Q r_t^{Q,+}(a) - \lambda_U \|\tilde a\|_2^2 - \lambda_P r_t^{P,+}(a), \tag{26}
$$

where  $(\cdot)^{+}(a)$  denotes the corresponding quantity after a one-step state update or local kinematic rollout under assist action  $a$ .

The guidance action is chosen as

$$
a_t^\star = \arg\max_{a\in\mathcal A} S_t(a). \tag{27}
$$

We apply imitation only in hard states:

$$
\mathcal H_t = \mathbf{1}\!\left[ c_t=1\ \land\ e_t^x<\varepsilon_x^{\mathrm{on}} \ \land\ \big(\bar\mu_t<\mu^{\mathrm{on}} \ \lor\ e_t^F>\varepsilon_F^{\mathrm{on}}\big) \right]. \tag{28}
$$

The corresponding guidance loss is

$$
L_{\mathrm{guide}} = \mathbb{E}\left[ \mathcal H_t \|u_t^{\mathrm{as}}-a_t^\star\|_2^2 \right]. \tag{29}
$$

When guidance is used, the total optimization objective becomes

$$
\mathcal L = \mathcal L_{\mathrm{RL}} + \lambda_G L_{\mathrm{guide}}, \tag{30}
$$

where  $\mathcal L_{\mathrm{RL}}$  is a standard RL loss such as PPO.

This guidance does **not** provide a full optimal whole-body solution; it only supplies a weak local preference over the low-dimensional assist space, leaving the long-horizon trade-offs to RL.

* * *

符号释义版
=====

下面把最关键的符号再用“新人可读”的方式解释一遍。

 $x_t^\star$ ：目标末端位置。  
 $F_t^\star$ ：目标末端接触力。  
 $x_t^{ee}$ ：当前末端位置。  
 $F_t$ ：当前真实接触力；训练时最好用仿真真值。  
 $q_t^a$ ：arm 关节角。  
 $\tau_t^a$ ：当前 arm 各关节已经承担的力矩；它代表“当前已经占用了多少 actuator 预算”。  
 $J_a(q_t)$ ：末端位置对 arm 关节的 Jacobian，只看 arm，不看 full-body。  
 $d_t$ ：目标力方向的单位向量。  
 $g_t=J_a^\top d_t$ ：沿目标方向多加 1N 时，各个关节会额外增加多少 torque。  
 $\mu_{i,t}$ ：如果继续沿目标方向加力，第  $i$  个关节还能扛多少牛顿才会先撞上限。  
 $\mu_t$ ：所有关节里最先饱和的那个决定的“整体方向余量”。这就是你最核心的 force-aware 指标。  
 $\bar\mu_t$ ：把  $\mu_t$  归一化后的 reward 版本。  
 $u_t^{\mathrm{usr}}$ ：用户原本想给 base 的命令。  
 $u_t^{\mathrm{as}}$ ：你学出来的 base assist，小幅微调。  
 $\eta_t$ ：assist gate，决定当前时刻要不要启用 assist。  
 $\xi_t^b$ ：你选取的低维 base posture，例如  $[h, pitch, roll]$ 。  
 $\xi_{\mathrm{ref}}^b$ ：base 的参考姿态，通常取 nominal posture 或接触刚建立时的 posture。  
 $r_t^x, r_t^F$ ：主任务项，先保证 reach 和 force。  
 $\alpha_t$ ：success-conditioned gate，只有“位置差不多对 + 力差不多对 + 已接触”时，才开始比较谁更有余量。  
 $r_t^U,r_t^V,r_t^P$ ：分别约束 assist 不能太大、不能太违背用户语义、不能离 nominal posture 太远。  
 $r_t^{\mathrm{Sm}}$ ：让 assist 平滑。  
 $r_t^S$ ：安全罚项。

* * *

你真正可以直接放进论文里的核心句子
=================

如果你想把整件事压成一句 Method 里的关键句，可以直接用这一句：

> We define a directional arm force reserve that measures the maximum additional end-effector force that can still be generated along the commanded force direction before any arm joint reaches its torque limit, and use it as a success-conditioned tie-breaker among equally feasible whole-body solutions.

这句话基本就是你整篇方法的“数学核心”。

如果你愿意，我下一条可以继续给你两样东西：  
一是**英文版 Method 正式写法**，二是**这套公式里哪些超参数该怎么初始化**。



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)