# 完整 v29 C002 的 N01 恢复机制与 Teacher→Student 能力传递预研

**独立审阅结论｜2026-09-20｜研究建议，不是效果验收或实施授权**

主底座：完整 `v29-c002-baseline`，**保留 B05 七族**。审阅分支：`codex/v29-n01-pro-20260920`。提交主题：`Prepare C002 N01 recovery and teacher-student research handoff`；输入给定时间：2026-09-20T14:22:17+08:00。

本包不改变既有 GPU0/GPU1 任务，不申请或假定训练预算；没有运行仿真、训练、策略推理或评估。没有 checkpoint/权重，不能声明云端复现。Pro 结果只作为对话附件交给 Owner，不上传 Drive。

来源编号与链接集中在 [SOURCES.md](SOURCES.md)。实现、图、采样的完整合同分别见 [RECOVERY_GRAPH.md](RECOVERY_GRAPH.md)、[TEACHER_STUDENT_PLAN.md](TEACHER_STUDENT_PLAN.md)、[PILOT_AND_IMPLEMENTATION_PLAN.md](PILOT_AND_IMPLEMENTATION_PLAN.md)。本文给出完整判断链条与取舍；配套文件把每条边、状态处理、数据字段、伪代码和实验分母展开，不能把其中一张简图脱离合同单独实施。

## 0. 直接回答 Owner 的五项要求

### 0.1 独立判断是什么

**不采用“旧 N01 恢复图已正确，只需补蒸馏”的前提。** 从当前任务出发，恢复的目的应是重新获得能完成任务后缀的物理条件，而非回到某个历史 stage。第一版应比大技能图简单：保留单一 recurrent actor，以少量条件落点组织训练与评估；不强制每个失抓都重新走 Stage2。

先阅读本次 brief/source/runtime、一手研究，写出初步设计后才阅读 historical ZIP。历史中已有很多相同担忧，因此本回包的新增价值主要是 **C002 源码绑定、执行/历史语义和可归因实验设计**，不是宣称首先提出恢复或 DAgger。[C01–C08,E01–E04,H01–H03,P01–P10]

### 0.2 基座选什么

**完整 C002+B05 是唯一主底座。** 保留 B01 固定逐门质量/closer/friction、B04 90–150°最大角、.90–1.20 m 把手高度、B07 自然起点、v29 robot 与当前控制基础。B02 仍为原实体 latch/mimic，不把新软件锁闩、pull 或更强执行器混入这次研究。

旧候选 JSON 的 pending 是历史状态，D056/D060 已接受 C002；但“实现已接受”不等于“恢复 Teacher 已合格”。新 Student recipe 必须真正从 C002 composition 出发，不能直接拿旧 DAgger 默认 robot/reward 充当 v29 Student，更不能暗用 GPU1 的 v29−B05。[C01,C07,E01–E03]

### 0.3 哪里恢复、退回哪里

**局部可捕获：原地再闭合；局部不可捕获但当前 base 可达：实时 pregrasp；当前 base 不可达：安全重新站位；关键状态看不清：重观察/重新找把手；可以安全通过：不必重抓；无安全落点或时间：结束本次尝试。**

推荐四个目标集合 A 获取条件、C 建立握持、M 操作门、P 通过。门运动与全身剩余通行路径决定落点，不能只看“曾经处于 Stage3/4”。在线恢复保留物理状态、累计时间、动作目标和两套 RNN；reset 与失败状态训练采样是另两条路径。

### 0.4 为什么不接受“Teacher学会就会自然传给Student”

因为 Teacher 能力、Student 状态暴露、Teacher 标签有效性、片段采样权重和部署信息条件是不同问题。现有 A2 源码已经能在 Student 当前状态查询 Teacher，但默认实际由 Teacher 执行全部高层动作，且没有跨 rollout 数据库；仅有接口名称“DAgger”不能补齐这些缺口。[C05,C06]

更深的限制是：Teacher 的恢复选择可能依赖 Student 看不到的接触/门运动真值。这类标签即使没有噪声，也可能不适合部分可观测 Student；相关问题在 A2D、CritiQ/ReTRy 中已有一手研究。[P06,P10]

### 0.5 Teacher 与 Student 分别怎么学

**Teacher：**自然失败 + 按实际握持资格触发的小规模失败课程，先做真实有作用的短开爪脉冲，再按失败模式加入一种物理/感知边界；优化恢复后完整任务，不奖励可反复刷的重抓，不刷新时间。

**Student：**以受扰 Teacher 示范启动，但主线改为 Student 亲自执行受扰闭环、失败后继续尝试；Teacher 在实际当前状态和真实历史上 shadow 标注；保存跨 rollout 的事件序列，以正确 prefix 重算 RNN，并对短恢复片段重采样。Teacher 接管只放在明确辅助支路，接管后成功不计自主恢复。首轮不依赖缺失历史的失败 snapshot。

## 1. 当前证据支持到哪里

### 1.1 已核对事实

| 事实 | 能支持的结论 | 不能支持的结论 |
|---|---|---|
| C002 被 D056/D060 接受、B05 保留 | 以完整 C002 作为研究底座是正确的 | 七族上已有合格恢复策略 |
| C002 resolved 没有启用旧 v27 recovery/perturb | 旧恢复代码只是可参考接口 | 当前训练已经训练了该恢复图 |
| Teacher133/critic138，Student81+RGB | 特权与部署信息边界明确 | Student 已拥有显式接触、stage、门状态 |
| 现有 DAgger 支持当前状态查询/部分 Student 执行 | 可以复用在线 label 与控制拼接接口 | 默认 ratio1 已让 Student 闭环训练 |
| storage 是本 rollout、loss 是12D BC | 需要跨段事件存储/采样与历史设计 | 因类继承 PPO 就已做 Student RL |
| 3000里程碑双方 max Stage3，接触指标改善 | 任务训练进入交互阶段的有限迹象 | 自然整任务成功、恢复收益、v29蒸馏效果 |

最新已存 D064 中 Stage2 both-contact 打印 .4098，grasp-complete/to3 打印 .0001，Stage3 active .0462，Stage4/5/goal 打印 .0000。这些是 staged-training 的日志值，不是自然 episode 成功率；四位小数 0 也不证明事件绝未发生。数值 loss 仍 NOT_OBSERVED，策略质量 UNASSESSED。没有为本次额外轮询正在运行的任务。[E04]

### 1.2 取得范围与未知

三个 ZIP 和另外三份入口文件均取得；332/40/18 个条目均可解压。定向读取与本问题相关的源码/配置/已存 runtime，不宣称审计了所有 CAD、mesh 和图片。远端大门任务文件的一次有界 fetch 返回空，但 source ZIP 中完整文件可读；远端 A2 distill trainer 与 delta action 基类读取成功。

没有输入的 checkpoint、完整本地训练 metadata、最终自然评估、v29 Student resolved 运行配方、实际图像到达时序均为 UNKNOWN/local-only。R2D2 作者摘要可读取，但本次 OpenReview 全文遇到浏览器挑战，未核验其具体实验数值。其余使用到的文献/官方作者资源及支持范围见 SOURCES。

## 2. 最重要的 findings

### 2.1 恢复成功的单位应该是“可完成的后缀”

重新闭合、both_contact 回来、stage 又到了3，都只是中间事件。关门器可能已把门带回、base 已失去可达站位、机器人已部分穿门；重新抓住以后仍可能没有足够时间或力学条件完成任务。因此应同时优化/测量：重新建立正确约束，和在同一 episode 内继续达成原 C002 goal。

RecoveryChaining 直接研究恢复到哪一个可继续任务的 nominal controller，而不只恢复前一个技能。本项目可以借用这一问题定义，但没有必要照搬其多 controller/hybrid action 架构。[P03]

### 2.2 目标 frame 已实时更新，问题在于目标是否仍然可执行

C002 的当前 G/pregrasp consumer 已依附当前刚体变换，不能把全部问题归结为“旧目标没跟门转”。真正的缺口是：当前 base 下 arm 能否到达、路径是否撞门、到达时目标是否已移动、是否还应重抓，以及该目标的奖励/动作前提是否仍成立。[C03]

这改变了最小方案：不是只新增一个 frame refresh，而是将恢复落点定义为**当前动态状态下的可执行条件集合**。移动门的候选还需要考虑传感与执行延迟；否则 Teacher 看见的是能救的状态，Student 真正看见时已经错过窗口。

### 2.3 “actor没有真值”不足以证明 controller 没有真值

现有 Stage0 会把 arm delta accumulator 清零。若把在线重定位简单标成 Stage0，物理目标会跳变；若 Student 评估仍借用此真值 stage gate，控制器就在 Student 输出之外替它完成一部分决策。[C03,C04]

因此新 Student 配方需明确 stage-blind 执行适配器，并把 Teacher raw action 投影成相同语义的有效增量标签。这个必要改动属于完整 C002 任务/资产上的显式部署接口适配，必须在所有 Student 对照中共享、检查名义代价，不能悄悄声称完全没有接口变化。

### 2.4 Teacher 很少自然失败，不是提高 Teacher 失败率就能全部解决

Teacher 注入课程解决的是“示范里有没有纠正行为”；Student 执行自己的轨迹解决的是“自己的错误状态有没有被访问”；事件序列重采样解决的是“短恢复片段有没有足够梯度”；观测匹配解决的是“标签能不能被 Student 当前信息实现”。这四个干预不等价。

DART 为第一项提供先例，DAgger 为第二项提供先例；固定专家在部分可观测环境中的问题仍由 A2D/CritiQ/ReTRy 提醒，不能用其中任何一个名字覆盖剩下三项。[P01,P02,P06,P10]

### 2.5 开爪动作是二值 primitive；有些物理注入接口甚至是空的

A2 adapter 用 gripper primitive 的正负号决定全开/全关。所谓“开爪幅度从0.2加到1”并不构成连续物理剂量；应测持续时间、实际关节开口与相对几何/约束损失。[C04]

本次 source 的 IsaacSim `apply_rigid_body_force_at_pos_tensor` 为 `pass`，不能把其调用成功算作实际施力。其他施力路径还需要核对 A2 的 body/frame；已有 push helper 中有速度冲击模型，要如实标注，不能误称持续真实力。[C09] 首轮复用可读回的开爪路径，避免无作用扰动制造虚假鲁棒性。

### 2.6 少量失抓被救回，可能只是几何容错，而不是新策略能力

短 pulse 结束后恢复原闭合命令，恰好仍在两指间的把手可能自行重新被抓住。因此不仅要报 K，还应比较 T_nom 与 T_fail，并在必要时用少量“维持原 target/名义闭合”的负对照区分被动重合拢与反馈重定位。

这也解释为什么旧 R2 的少量条件重抓不能直接证明研究收益，更不能作为 C002 Teacher 的能力背书。[H04]

## 3. 推荐恢复图与落点

### 3.1 小图，不是大网络栈

推荐 A 获取条件、C 建立握持、M 操作门、P 通过，成功与终止为终点。A 内包含实时 pregrasp、base 重新站位、重新观察，作为同一策略不同目标情况，而不是三个独立 actor。

核心边为：捕获失败 C→A；近距真失抓 M→C；离开捕获域/不可达 M→A；有握持但无进展 M→M 做有限操作修正；可安全放手/无需重抓 M→P；后续回关阻断 P→A；完整通过 P→成功。

**首轮主要实现/训练未授权释放前的 M→C/A 和捕获失败 C→A。** post-release P→A 在物理上属于完整任务恢复问题，应设计清楚，但按照历史 Owner 路由，它目前是 N02 待办；建议未来归入任务层恢复的第二阶段，待 Owner 采纳，不以研究结论替代 Owner 范围决定。[H03]

### 3.2 六种落点的明确选择

| 状态 | 推荐落点 | 理由 |
|---|---|---|
| 把手仍在捕获域，闭合时间内相对运动很小 | 原地再闭合 | 最小动作；没必要撤回整个阶段 |
| 把手已偏离两指，但当前 base 下 arm 仍可安全接近 | 实时 pregrasp | 修正接近条件，而不是对空气持续闭爪 |
| 当前 arm 极限/站位不利，门扫掠区外存在更好位置 | base 重新站位后 pregrasp | 仅退 Stage2 没有改变不可达性 |
| 关键视觉丢失/过期且不同解释对应不同动作 | 重观察/重新找把手 | 不从无信息里虚构精确门/接触状态 |
| 门开口和运动允许安全完成通过 | 直接继续通过 | 重抓不是任务目标，返回可能更危险 |
| 两条候选都不安全或剩余预算不足 | 终止本次尝试 | 不用 reset 或无限重试伪装恢复 |

门快速回关时应比较“及时抓回”“安全通过”“先退出扫掠区待门停稳再重开”三种可能，而非固定采用其中一种。Teacher 可用真值评估训练目标；Student 要从实际输入历史选择行为。root 越过门平面不等于全身清空；计分仍保留 C002 原 goal，不偷偷换更容易的成功定义。[C03]

### 3.3 连续状态合同比画边更重要

在线边不改变 root/q/qdot、不重采样门参数、不 reset、不清 RNN、不清 low-level 历史、不清 arm accumulator、不刷新任务时间。真实约束中断只清新握持 qualification，并保留原始历史与事件 epoch。

将当前 `task_phase`、单调 `progress_highwater`、全局 elapsed/预算账本、当前与历史 release/hold 信息分开。重新回到已达阶段不发第二次 transition/stage/save-time 或 handle creation 收入；不设可刷的固定 regrasp 奖金。恢复获取条件时，从开始接近就解除确实冲突的 arm-return/grasp/handle-return 奖励条件；不是握住后才解除。[C02,C03,H03]

所有边的失败触发、正常释放排除、Teacher/Student 信号、动作、成功/放弃与状态处理在 RECOVERY_GRAPH 中逐条定义。

## 4. Teacher 恢复训练：最少够用的课程

### 4.1 第一种干预与数值依据

使用已真实建立握持、仍需控制门的窗口；随机触发短开爪命令。可从旧6 tick附近的3/6/12 tick（.06/.12/.24 s）做读回校准，依据仅为现有控制 dt、旧注入机制和5 tick握持时间尺度；这是待校准值，不是已验证最优区间。[C01,C04,H04]

开始可用约70%名义episode、30%计划注入episode，且都保留自然失败。计划分配不等于实际触发：没到窗口的episode照样计入assigned总体。第一轮每episode最多一次计划脉冲便于解释，后续是否多次扰动再看错误类型，不给部署设“一次失败就结束”的新硬限制。

在动态门/七族上，强度以实际q开合比例、把手相对夹爪位移/速度和捕获裕量归一化；不要用primitive数值大小当物理幅度。只有命令脉冲通过时，结论限于command-visible干扰；至少保留自然或一种命令仍闭合却发生实际失约束的测试，排除只学到脉冲结束再闭合。

### 4.2 避免两端无效样本

过轻：大量命令触发但没有物理失抓；应校准实效，不是再跑更久。过重：大多超出安全落点/时间；应减弱或换时机，并把这些样本保留为边界/未知统计，不靠删除分母做出好成绩。

训练优先可恢复候选和邻近边界。几何/时间筛选不是可恢复真值，少量Teacher continuation用来核对是否能接上任务后缀；Teacher失败也不自动等于物理必死。API错误或非finite tensor走工程fail-fast，不进入课程。

### 4.3 目标与防投机

Task goal和名义质量不降级。恢复消耗同一个全局时钟，stage信用只在首次真实进展解锁，重复重抓不得“重获一生”。保留高水位，避免循环奖金；需要dense目标时只加少量有界势差候选，且明确终止/timeout/mode变量。引用shaping理论不能代替整套reward检查。[P11]

Teacher当前未成熟，并不阻止先验证课程/存储链路；但没有后缀成功证据的区域不能作为高置信专家来指责Student。Teacher方法对照应从同权重、同新增兼容层、同训练量比较名义续训T_nom和失败课程T_fail，而不是只对比额外训练后的策略和旧checkpoint。

## 5. Student能力传递：推荐主线的完整合同

### 5.1 谁执行、谁被扰动

用少量受扰Teacher轨迹启动。主Student cohort从自然起点执行自己的高层动作；在它当前env的交互窗口施加扰动；失败后仍由Student尝试恢复。Teacher每步在同一真实env观测上shadow查询，不接管也照样更新自己的hidden。

控制权按episode分层随机分配，避免固定env前缀与左右/七族分配耦合。辅助Teacher cohort可用人工阶段比例逐步减少，但不能把“降低比例”本身写成已实现的自动课程。

Student还到不了交互窗口时，采用Teacher真实执行前缀、Student一路观察、切给Student后再扰动的局部诊断备选。它保持真实历史，但只证明接手后的局部能力，不是独立整episode成功。最终评估必须自然起点全Student。

### 5.2 失败后不能马上接管

主仿真cohort无需失抓即Teacher救援；危险超界时可直接终止。确有必要的assisted支路使用连续Teacher接管区间，达到可交回的稳定物理条件后交还，两套RNN不重置。

保存`teacher_ever_in_episode`与`teacher_after_failure`两个不同标志。Teacher前缀、失败后Teacher救援、自主自然起点是三种不同证据；接管成功不能进入Student independent成功分母。

### 5.3 数据与历史

存储单位是能链接完整prefix和最终outcome的episode/event sequence。保存实际81D、交付RGB与frame时间、Teacher133D、Teacher有效动作标签、Student proposal、实际issued command、执行者、真值事件字段、done/terminal observation、版本与归一化信息。真值字段不进入actor输入。

首轮不依赖现有缺失历史的snapshot。当前Teacher每步在线标签可以直接保存；Teacher更换版本后不能拿旧hidden离线重标注。对Student训练，用当前权重从真实episode起点重放prefix得到窗口初始hidden，再对loss窗口训练；重放已记录输入不推进物理仿真。收集器权重更新后，仍在进行的episode也要重算新版本online hidden，不能零hidden配半开的门。[C05–C08,P08]

旧8 tick rollout不等于LSTM只会记8 tick；需要解决的是跨段保留和训练状态一致性。起始可用64–128 tick的loss unroll，事件更长时连接后续窗口，保留最终成功/失败，不能截到“刚抓回”就结束监督。

### 5.4 防止恢复片段被淹没

将约一半训练loss窗口分配给恢复事件、另一半给名义数据，先按事件均衡再采时刻。这个比例是待调起点，不是新硬门槛；实际需要以事件覆盖与名义代价调整。

库保持有限、按frame_id去重，不要求生产4096env全录像。相同数据库比较uniform与event-balanced sampler，匹配优化有效帧数；否则“采样器有效”可能只是它训练了更多步。

### 5.5 Teacher错误标签与不可实现标签

Teacher在新Student状态上不可靠时，保留失败序列，暂不强施加该动作的BC；对代表性状态/历史做少量Teacher后缀检查，unknown与rejected仍计入失败分母。finite、critic高或T/S接近不等于标签正确。

Teacher自己也失败：将真实Student-origin failure回流下一版Teacher课程，再冻结Teacher重做局部对照。Teacher能做但依赖看不见的信息：增加观测获取行为、观测匹配的Teacher或选择性监督，而不是反复模仿同样冲突标签。[P06,P10]

### 5.6 现有网络能否学会

**建议先保留当前ResNet18 + 两层256 LSTM的单actor。** 没有证据证明局部重闭合/重新接近必须依赖更大网络，也没有证据证明现有网络能可靠学会完整动态恢复图。先把分布、标签和历史做正确，再由错误类型决定是否升级。

序列化逐时刻12D BC可以作为第一版；不是无记忆单帧模仿。只有在接触/释放判断错误、长时段链条缺失或信息aliasing明确时，依次考虑辅助状态/运动预测、轨迹监督、observability-aware Teacher或独立的Student RL finetune。当前类继承PPO不代表已经做了最后一步。[C06]

## 6. 最小实验路径与判断标准

### 6.1 顺序

**P0功能链**：完整v29 Student resolved、一次有效扰动与Student执行、跨rollout正确序列、一次update、无接管检查。现有Teacher不成熟时只声明功能，不能说恢复/蒸馏有效。

**P1扰动校准**：同一Teacher、同一C002门域，实际作用与loss分开；必要时检查被动闭合是否解释了所谓恢复。

**P2 Teacher收益**：同起点同训练量的T_nom/T_fail；从全部episode与真实失效两种分母比较完整后缀，不把旧C002未续训当唯一弱对照。

**P3 Student收益**：固定同一恢复Teacher，S_T受扰Teacher轨迹，S_C Student闭环+uniform sequence，S_E同类闭环+event-balanced sequence。S_C/S_E先用同一数据库分离sampler，所有组网络/相机/门域/训练token一致。主实验先不加aux/RL。

只有发现错误落点或信息aliasing等特定阻断才追加相应小对照。不自动开展全部图×Teacher×Student×相机的组合网格。

### 6.2 完整漏斗而非单一恢复率

全部episode E → 交互窗口W → 扰动分配I/实际施加A → 实际状态改变D → 有效失效F → 策略实际恢复尝试R → 新约束K或续行B → C002完整任务成功G。正常释放单列；自然失败不要求经过A/D。

主报告同时给`G/E`、`G/I`、`W/I`、`F/A`、`R/F`、`K/F`、`G_after_K/F`、`G_after_K/I`以及无需重抓分支。按自然起点独立Student、Teacher前缀和Teacher救援分表。成功时延不能忽略未恢复/超时样本；logger的真值检测时刻不能冒充Student内部检测时刻。

第一阶段用既有64自然首episode量级的分层小样本看主导阻断，左右/七族和B01参数都记录；不宣称统计充分或每个组合已覆盖。没有新GPU预算承诺。

### 6.3 何时继续、何时改方向

失效曝光不足→校准实效；Teacher只抓回不能完成→修物理落点/后缀/奖励；Teacher可靠但Student失败→先看Student是否经历同类失败及历史是否正确；同数据event sampler无益→简化；无图RNN不劣→删图调度；相同Student历史要求相反Teacher动作→获取信息/适配专家，不盲目扩大网络；名义任务受损→恢复名义quota并检查奖励/动作适配。

独立Student最终评估关闭Teacher动作、接管、staged reset、失败bank与K辅助；从自然分布开始，保留自然失败及未见扰动。未测的失效种类写UNKNOWN，不能按相邻测试代签。

## 7. 一手研究如何改变方案

| 研究 | 已有的直接启示 | 本项目没有被证明的部分 |
|---|---|---|
| DAgger [P01] | 学习者诱导的状态分布与专家标注/聚合 | 当前默认Teacher执行不满足想要的暴露；部分可观测标签不自动可实现 |
| DART [P02] | 强专家也能通过扰动提供纠正示范 | Teacher-only噪声示范是否覆盖Student真实错误 |
| RecoveryChaining [P03] | 恢复选择哪个可继续执行的后缀/技能 | 本任务动态门、单RGB与单actor部署中的实际收益 |
| Recovery RL / HG-DAgger [P04,P05] | 接管进入/退出、纠正数据与安全行为要区分 | 被Teacher救回不能当Student独立任务能力 |
| A2D / CritiQ-ReTRy [P06,P10] | 不可实现专家、部分可观测模仿偏差是独立问题 | DoorDog具体信息边界与可靠标签的可操作判定 |
| Miki等 [P07] | recurrent belief与训练期辅助监督是有效先例 | 近距RGB把手接触是否可辨识，不能直接借足式地形结果担保 |
| R2D2作者摘要 [P08] | recurrent replay有representation drift与hidden staleness风险 | 本回包未核验其全文burn-in数值，更没复现其算法 |
| ReSYNC [P09] | 失败技能/概念/规划以及恢复技能视觉蒸馏已有先例 | 其多视角/对象感知条件不能被算成本项目现有单路预算 |
| Potential shaping [P11] | 某类势差变换有策略不变理论条件 | 当前恢复、超时、mode和reward mask组合不自动满足全套条件 |

这支持一个克制的工程选择：先采用已有研究启发下的正确执行/分布/记忆设计，不因为“模块都是已有的”否定工程价值，也不因为模块名字组合新就宣称方法新颖。

## 8. 历史方案对照与 N01/N02 范围建议

历史阅读没有推翻独立主线，但使两点更明确：一是当前很多担忧并不是新发现，9/17 Pro材料已深入讨论Teacher→Student、条件落点与历史；二是9/18 post-release rebound文件已指出接近前就要处理共享assistance-needed和冲突奖励，不能只加一个both_contact之后的hold reward。[H02,H03]

| 历史观点/实现 | 本回包决定 | 理由 |
|---|---|---|
| v27统一Stage3/4失抓→Stage2 | 不作主线；保留局部对照 | 只适于捕获域内，不能解决base不可达/门运动/安全续行 |
| 恢复图+困难边界采样 | 保留物理目标和事件分层，缩成四目标单actor | 避免大图与多网络先于证据；图收益需独立验证 |
| Teacher恢复后常规蒸馏 | 明确拒绝作为充分链条 | 默认Teacher执行、短片段稀释、OOD与信息错配均可能阻断 |
| recovery bank / staged reset | 只作有明确历史的训练备选 | 不是在线恢复；当前缺双RNN/视觉前缀 |
| post-release regrasp放N02 | 尊重当前Owner路由；建议未来作为任务层恢复第二阶段 | 任务连续性有合理性，但范围修改待采纳；第一pilot不强迫纳入 |
| N02更复杂交互辨识/估计 | 暂不绑到第一版恢复必需条件 | 可先学习局部恢复；observability匹配可以成为后续连接问题 |
| v27 pilot已验证恢复 | 不接受 | R2 step1500左右各64、实际loss5/2、clean恢复完成0/1，整体UNRESOLVED |

旧R2的regrasp和recovered_complete为5/2不等于无条件恢复率高；clean完成仅0/1，而且不是C002。R1没到计划endpoint。旧Phase2一次update也不证明v29蒸馏。[H04,E01]

## 9. Novelty判断：目前不足，什么才值得研究

### 9.1 当前结论

**目前没有足够novelty证据把“恢复图 + 失败注入 + DAgger + RNN重采样”直接包装成新方法。** 条件恢复已有RecoveryChaining，扰动模仿已有DART，学习者分布已有DAgger，部分可观测专家错配已有A2D/CritiQ-ReTRy，恢复技能到视觉策略亦有ReSYNC等先例。[P01–P03,P06,P09,P10]

这不意味着不值得实施：对DoorDog而言，先把完整任务失败后的闭环与传递做实，是必要且可能很有价值的工程进展。但一个工程必要性不能代替新颖性与效果证据。

### 9.2 值得保留的可检验研究问题

更有潜力的问题是：**当门持续运动时，如何选择“物理上还能到达、且Student依照其实际到达的观测历史还能及时选择”的恢复落点，并把这种选择传递给受限视觉策略？**

可以把两个边界分开：给全状态Teacher的物理可恢复区域；给固定81D+RGB时序的可实现恢复区域。Teacher在前者成功、Student在后者失败，不应全部归因成模型不够大。候选方法是让Teacher的恢复示范/标签尊重Student的可观测时机，在模糊处主动恢复视野或选更稳妥落点，而不是利用不可见的瞬时接触真值做最激进动作。

这只是研究假设，且与A2D/ReTRy有明显关系，不能预先命名成已成立的新贡献。需要至少排除：数据量更多、Teacher更好、相机更好、baseline偷偷没有Student闭环、被动自动闭爪、真值controller辅助等替代解释。

### 9.3 一个足以改变判断的证据组合

在同一完整C002、同一Teacher候选池、同一Student输入/网络和训练量下，对比普通当前状态标签与观测匹配的恢复目标/示范；固定物理失效前缀，改变实际交付观测年龄或可见性；验证方法是否改善**无接管Student的恢复后完整任务成功**，而不仅是动作BC/接触恢复。再看自然/未见扰动与正常性能代价。

若收益只来自事件采样加权或Teacher前缀，应如实称可靠工程组合；若在匹配条件下反复显示“可观察恢复落点选择”解决了普通分布聚合无法解决的误差，再考虑提出方法贡献。没有结果前不写“首次”“保证泛化”或“已具硬件可部署性”。

## 10. 当前明确推荐与 local-only 决定

现在可以确定：完整C002+B05；单recurrent actor；条件物理落点；先未授权释放前失抓；Teacher实际失败课程；Student真实执行和shadow标签；有限事件序列库；连续RNN/prefix语义；无接管自然起点评估；不先做大snapshot/多技能/force外环。

仍需本地在实施前确定的只有真正影响接口的事实：选哪一版可用Teacher及其可信区域；哪一路当前可实际安装的RGB视角和实际帧时序；新resolved composition与stage-blind动作标签转换是否吻合现有部署控制。它们有明确默认路径和P0验证办法，不是要求Owner先讨论完所有架构或等最终CAD。

是否将post-release回关从历史N02路由改为N01后续阶段，是Owner范围决定；不自动扩大第一轮实现。是否升级辅助目标/观测匹配Teacher/StudentRL，应由小pilot错误类型决定。

**最小下一步：先做设计定向核对和一页Owner说明；只有Owner随后明确授权，再实施P0功能链。** 本回包自身不是修改、训练、GPU占用或测试工程授权。
