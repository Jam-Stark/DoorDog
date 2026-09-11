# A2+Piper：从一次走通到可恢复交互 — Astra 独立路线建议

## 结论

建议结束 v26 的 acquisition/scaffold 扫描；把其资格整理计入 v27.0。近期选择方向 2 的一个小切口：**接触失效后仍能在同一物理 episode 内重抓、继续开门的循环技能图**。方向 1 保留为后续科学主线：用交互历史决定如何开、何时持门、何时恢复；方向 3 暂作为测量假设，不直接增加 critic 或奖励姿态幅度。

这不是“三个想法拼起来就是 novelty”。推拉统一、历史估计门属性、失抓后重试、全身协同都已有先例。真正值得检验的是：**按当前接触有效性组织可返回的技能状态，并让训练采样覆盖失效—重入边界，能否比相同 RNN、奖励、扰动数据和预算的普通训练，更可靠地完成受扰开门？** 若不能，就撤销图训练的主张，保留工程修复。

状态：2026-09-05，PROPOSAL_FOR_OWNER_COMPARISON。与另一方案独立；本轮未实施、未训练、未选 Teacher、未更新 G7。后续入口：[v27 plan](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_plan_20260905-Astra.md)。

## 1. 当前证据支持收尾，不支持“可靠 Teacher 已经完成”

v26-8 r3a 六格均训练到 3000、退出 0，72 个 exact64 lane 共 4608 个评估 episode，integrity=0；这是跨 checkpoint 的评估次数，不能当作 4608 扇独立测试门。既有裁定保持 W_NOT_DIFFERENT、K_REGRESSED、C_ENTRY_EMERGED/C_CONSOLIDATED；Wave 2 未运行。[执行 closure](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260904_wave1_r3a.md)

终点 S2 的 complete 到达计数（每侧分母 64）为 C=64/64、W=64/64、K=60/63。它说明存在可用研究父策略，不等于行为质量、不同训练 seed 或 scratch 已可靠。特别是 K_S2 LEFT 的 complete 在 1500/2000/2500/3000 为 1/0/63/60；附件所称“三组从 1500 起持续 60+”不成立。[1500](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step1500_readout_20260904.md:27)、[2000](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step2000_readout_20260904.md:27)、[2500](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_step2500_readout_20260904.md)

附件关于 LEFT 松手后身体接触、K 保持抓握但 overspeed、arm_j4 驻留的数字是待复核的外部分析，不在本文升级成已验证事实。当前 source 的 complete 仅检查 root-x>1.5；Stage4→5 另检查过门位置和门/把手角度；奖励中的多项成熟行为约束在 v26 acquisition 配方里为零。因此“complete 高但行为不同”在机制上完全可能。[stage source](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:29068)、[reward](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_v26_acquisition.yaml:58)

同样不能把“arm 足够”理解为“base 没作用”。v25 stable-grasp 的匹配短窗里 planar 开关有明显 hinge progress 差异，而 roll/pitch 的即时力收益不确定。当前合理对照是 arm+planar 与 arm+planar+posture，不是只看姿态是否出现。[v25 证据](/home/baoquanc/workspace/DoorDog-A2_Piper/memory/a2-piper/base-v25-mirrored-teacher-force-causality/description.md)

## 2. 文献边界：三个方向都不能只靠换名字

以下是截至 2026-09-05 的定向一手文献核对，不是穷尽检索，也不构成“尚无人做过”的证明。表中“对本项目的含义”是本报告的判断。

| 一手工作 | 已覆盖的核心内容 | 对本项目的含义 |
|---|---|---|
| [DoorMan, 2025](https://arxiv.org/html/2512.01061v1) | stage-conditioned 任务与成功边界快照的 staged-reset 探索 | 不是六个独立网络依次学；把 reset 分类从线改树，本身贡献很弱 |
| [Learning to Open and Traverse Doors with a Legged Manipulator, CoRL 2024](https://arxiv.org/abs/2409.04882) | 单策略推/拉及左右门、交互中估计门属性；正文也讨论扰动恢复和错抓后的重试 | 最接近的必比基线；不能声称首次推拉统一、首次估门或首次 retry |
| [RMA, RSS 2021](https://ashish-kmr.github.io/rma-legged-robots/) | 基础策略与在线 adaptation module | 历史 latent 是成熟方法工具，不是开门任务里的自动 novelty |
| [RecoveryChaining, 2024/2025](https://arxiv.org/abs/2410.13979) | 层级 recovery policy，选择何时及向哪个 nominal controller 返回 | 加 recovery 分支和切换网络不足以区别于已有工作 |
| [Deep Whole-Body Control, CoRL 2022](https://arxiv.org/abs/2210.10044) | 统一 locomotion/manipulation；Advantage Mixing 与在线适应 | 增加分支 critic/credit assignment 必须有额外可检验机制 |
| [Learning Force Control for Legged Manipulation, ICRA 2024](https://arxiv.org/abs/2405.01402) | 无力传感输入的 learned force control、可变柔顺全身控制 | “不用 F/T 传感器也能调力/联动”不是空白领域 |

特别注意最近邻门论文的限制：采用 hook，门位姿观测由外部跟踪提供；把手未转足仍是失败模式。A2+Piper 的夹持把手、连续下压、接触丢失与重新入场可形成更明确的问题设置，但**换硬件或换夹爪本身仍不是算法贡献**。[原文 §3/§5](https://arxiv.org/html/2409.04882v1)

## 3. 三条路线的裁定

### 方向 1：保留，但从“精确识别门参数”改为“对控制有用的交互状态估计”

值得做。建议估计有效阻力/回弹趋势、抓握可信度、近期动作能否产生 opening progress，以及这些预测的不确定性；不要求从短段本体感知唯一恢复 mass、inertia、stiffness、damping。不同参数组合、抓握滑动和执行器跟踪误差可能产生相近响应；把它们强行归为质量变化会误导控制。这是建模判断，不是本仓库已有辨识结果。

当前 actor 已经是 LSTM，但还直接看到门重、门关节、side/IO、handle/pregrasp 相对变换和仿真手接触力。删除 mass 字段并不等于 proprio-only。未来必须分别登记：可部署的编码器/IMU/动作历史；估计得到的 base 状态；视觉或跟踪得到的门/把手几何；只供 teacher/critic 的仿真真值。力/电流信号以实际硬件可提供的量为准，不凭空承诺。[obs](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml)、[privileged bundle](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:27763)

未来最小方法比较：同传感预算的 recurrent DR baseline、增加 action-conditioned history latent 的版本、oracle 上界。必须有 episode 内阻力改变和训练外参数组合；仅在静态随机化门上赢，不足以证明“实时适应”。辅助辨识 loss 还需与无辨识 loss 的相同 RNN 对比，避免把 recurrence 收益记到 estimator 名下。

普通/困难/极限三个层级不宜由策略是否失败来定义。先按物理场景分层，再报告各策略表现。近中性姿态是代价偏好，不是所有轻门的硬约束；quiet-hold 与 controlled-swing 是允许的不同策略，要分别评估接触、速度、净空和完成，不强迫同一种外观。trunk/髋接触辅助留远期：它需要额外接触模型与硬件范围，不是自动下一档。

### 方向 2：现在切入“可返回的接触状态图”，不是树形多任务分类

LEFT/RIGHT 是条件变量，不必各长一棵互不共享的策略树；push/pull 也是独立任务条件。重试有环，正确抽象是有向图。当前基类只让 stage 增加，没有失抓后的降级路径。[状态机](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/base_task/staged_task_base.py:164)

把三个概念分开：历史到达进度（评估）、当前有效技能状态（控制）、训练 reset 来源（采样）。一次到过 Stage4，不代表现在还抓着门；让控制状态回到 pregrasp 不应删除历史，也不能重置门角、latch 或 episode 时钟。成功必须再次满足物理条件，而不是由历史 max_stage 直接放行。

近期只实现一条恢复环：未过门前非计划失抓 → 找回当前把手 → 重抓 → 根据当前 latch/hinge 决定继续下压或继续开门。Stage0/1 站位 repair、多次外扰、任意时刻被打断、开门方式自动识别都不塞入首次 pilot。

可检验的方法区别是**训练分布与重入语义的配套**：普通阶段快照主要覆盖成功前向边界；新增的恢复边界快照覆盖“门已经动过、接触却无效”的状态，按 side 和失效边界分层采样。对比三臂：原单调状态机+相同扰动、仅运行时恢复图、恢复图+恢复边界训练采样。训练步数、扰动概率、网络容量和非恢复奖励保持匹配。这不是把环境 reset 伪装成机器人 recovery。

v27 只做工程基础与小样本 pilot；算法效益需要后续多 seed、同预算、未见扰动的确认。若普通 RNN 已同样会重抓，则应接受“显式图无附加收益”，不继续增加树深或 critic。

### 方向 3：当前不加 coupling critic；先确认究竟缺的是能力还是证据

现有 PPO critic 已通过整体任务回报间接评价 arm/base 配合；缺的是可识别的联动监督和因果证据，不是“系统完全无人给联动打分”。奖励非零 roll/pitch 或动作相关性会制造看起来联动的动作，不能证明开门能力增强。

建议先做匹配状态/历史的四支干预，分离 planar 和姿态，再测接触丢失、hinge progress、机身稳定与功耗代理；同时区分短窗 acute 能力和长期适应后的策略性能。旧 v24 的容量代理退化、E1 对称准入与假设混杂，不应再成为入场阻碍。[v24 归档](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/a2_piper_longterm_TODO.md)

只有测得跨场景稳定、可预测的 interaction residual，且额外 critic 在 held-out 干预上优于简单模型，才让它进入训练。先 shadow、后干预监督、最后才讨论 branch PPO。若只改善姿态外观而没有任务/质量收益，就关闭路线。

## 4. 分阶段落点与可证伪条件

| 阶段 | 本阶段交付 | 不宣称什么 |
|---|---|---|
| v27.0 | v26 资格归档；独立候选质量读出；research parent 与 qualified candidate 分开 | 不追溯重判 K，不自动替换 G7 |
| v27.1–3 | LEFT 功能质量；明确负载/摩擦分布；独立训练 seed 和真 scratch | 不把 continuation seeds 当从零复现 |
| v27.4 条件 pilot | 单次失抓恢复环；三臂同预算探索 | 不把 1 seed pilot 写成算法获胜 |
| v28 候选 | 恢复图确认；历史自适应与图训练 2×2 消融 | 不把静态 DR 当实时辨识 |
| 后续条件路线 | push/pull 联训、重复扰动、策略模式选择、测量支持的协同监督 | 不提前承诺精确质量辨识或 body-assist |

停止条件包括：同预算恢复图无收益；隐变量只编码 side/阶段而不响应物理变化；质量收益完全来自更长 episode；为了制造 posture 必要性才人为把 arm 调弱。负结果属于合法产出，而不是追加预算理由。

## 5. 证据、限制与下一步

本报告的 source 事实由当前两个 worktree 的只读检查得到；v26 数字来自已存在 closure/readout；pull 远端历史来自指定 Codex 会话及其 2026-09-01 handoff，不能代表远端现在的 GPU/文件状态。附件额外质量统计须在 v27.0 定义事件后核验。没有新 rollout、硬件校准或文献算法复现。

本文采用技术报告的“结论—证据—方法—局限—下一步”结构。按 Owner 要求交付仓库 Markdown，不另建 HTML/Sites；对照表用于精确查阅条件与证据边界，不绘制缺乏新数据的定量图。

建议按配套 plan 先取得可信的功能质量和恢复入口，再投资 estimator/critic。仍需实验回答的核心问题是：LEFT 的差异来自阶段边界经济、几何策略还是负载；恢复边界采样是否有超越普通扰动训练的收益；真实可用观测能否分辨“门重”和“没解锁”。这些问题均不能由现有高 complete 计数直接回答。
