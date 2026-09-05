# base_v27：资格、功能质量、可靠性与恢复环 pilot — Astra

## 0. 结论与授权边界

本阶段先把 v26 的研究收尾落实为 v27.0，再处理 LEFT 功能质量、门侧负载/摩擦分布和 seed/scratch 可靠性。全部基础门满足后，只做一个单次失抓恢复环 pilot。暂不改 PPO/critic、不开 body-assist、不做大一统 push/pull policy、不启动 Student/hardware。

状态：2026-09-05，PROPOSAL_FOR_OWNER_COMPARISON；此文件是可执行提案，不是已获批的新训练或已取得的结果。Owner 选择本方案并下发[开工 prompt](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_start_prompt_20260905-Astra.md)后，执行其中有明确预算的条件分支。另一方案不自动并入本合同。

本阶段不修改 v26-7/v26-8 脚本、artifact、奖励函数、历史裁定。以下新门槛和 v27 overlay 是前瞻性设计；不追溯改变 K_REGRESSED，不把 v26 未准入 Wave 2 改称已授权补跑。Git commit/push、Teacher/G7 更新和硬件均需单独授权。

科学路线与文献边界见[novelty 判断](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_novelty_route_20260905-Astra.md)，长期队列见[TODO-Astra](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/a2_piper_longterm_TODO-Astra.md)。

## 1. 固定事实与研究输入

v26-8 r3a closure 已证明六格 3000 exit0、72 个 exact64 lane/integrity0，结论为 C entry/consolidation、W_NOT_DIFFERENT、K_REGRESSED；仅是 warm continuation 研究。v26 科学收尾不依赖下一阶段是否能选出合格 Teacher。[closure](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260904_wave1_r3a.md)

所有下述父 checkpoint 均为已存在的 r3a step3000，目录：

/home/baoquanc/workspace/DoorDog-A2_Piper/logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/{C_S2,W_S2,K_S2}/model_step_003000.pt

默认 research parent 固定 C_S2；W_S2 是质量候选对照；K_S2 只做诊断参考，不自动重新取得研究 winner 或 Teacher 资格。S1 及中间 milestone 继续引用旧数据，不能为了补强候选随意增加筛选池。

source 输入包括 v26-8 common/C、v26-7 common、v26 acquisition reward、door_open_a2_base 的 stage/observation/telemetry 消费者。当前 actor 是 privileged 135-D LSTM，不是 proprio-only；native action=12、critic=140。此阶段保持其形状和语义，恢复 pilot 的 active-stage 语义变更单独登记。[obs config](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml)

## 2. 统一评估合同：完成、质量、恢复分别计分

所有自然评估：固定侧、first episode only、staged reset off、penalty curriculum off、v26-8 driver=null；使用 checkpoint-adjacent config，明确 full evaluation load。eval 不继承会在线改变奖励 scale 的 driver。新建 v27 reducer，参数化 exact N；不得修改 v26-8 固定64校验让它接受128。

开发 eval manifest 与 sealed confirmation manifest 用不同固定 seeds/episode IDs，初始化时记录参数、side、起点与采样版本；训练不读取 sealed manifest。重复相同门集的不同 checkpoint 是配对观察，不是新增独立门。主表先逐侧/逐seed，再汇总；不只报 pooled。

### 2.1 原始到达与物理事件

- D：handle≥0.6rad 连续≥25 control steps；Sx+：episode max_stage≥x；open_hold：hinge≥0.25rad且both_contact连续≥25步。都是到达计数，不是条件通过率。
- complete 保留当前物理条件，不改成 quality 或奖励达标。普通 crossing 是 root_x 相对 env origin 首次由未过线到 >0m；complete 为 >1.5m。
- crossing_while_holding 当前只是 crossing 当步 both_contact，不是 strict K5，更不是整段无滑脱。另报 Stage2 squeeze-aware K5 与 Stage3/4 contact-streak K5，不能混名。
- 第一次 crossing 的 hinge、速度、持握、body contact；计划 release latch 与实际接触丢失分开。无 release 的 episode 标 NOT_RELEASED，不填0，也不把其后接触假定不存在。
- arm_j4_limit_residence_step_share 沿用旧定义：abs(1.745-q4)<0.001rad，占有效 trace steps 的比例；只覆盖正限位，不称双向关节限位。

以上定义由[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v26_8/v26_8_reduce.py)、[crossing source](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:15387)、[stage source](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:29068)支持。

### 2.2 v27 新增的功能质量门

定义 clean_complete 为同一个自然 episode 同时满足：complete；首次 crossing hinge≥1.0472rad；从首次进入 Stage3 到 episode 终止 body-panel 非手接触总力不曾 >5N；没有 low_height/upper_dof_overspeed termination。采用 source 同一 body sensor/filter 和 norm-sum，不合并手指/手掌接触。该 5N 来自已有 body event/corridor 尺度，但这里的联合规则是 v27 新提案，并非硬件安全认证。

计划持门或受控松手均允许；不要求 crossing_while_holding=1。质量是功能约束，不强迫 LEFT 与 RIGHT 的关节轨迹或姿态幅度对称。另报 >1N 接触 episode、>5N event、峰值和冲量代理，以免阈值隐藏趋势；5N 门不随结果调整。

64样本工程门：每侧 complete≥60/64，clean_complete≥56/64，low/overspeed 总数≤2/64。128样本确认门：每侧 complete≥120/128，clean_complete≥112/128，low/overspeed总数≤4/128。阈值是此计划的工程接受线，不以小 N 宣称总体真实概率保证；附 complete/clean_complete 的 Wilson 区间。跨seed结论按 seed 为单位，不用全部 episode 假装几百个训练重复。

source 的 upper_dof_overspeed 阈值会依赖有效 termination level；记录实际值，保持 source 行为，不为了统一报表改 termination。当前初始 level=1 时为20rad/s、仅 arm_j1…j6、episode length>20；low_height<0.3m。[source](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:28843)

## 3. v27.0：完成 v26 资格整理，再独立看质量

### G0：一次静态执行路径核对

确认旧 closure 与 endpoint identity，不重跑旧 reducer/训练。记录 v26 仅有 continuation 证据；将附件中 K_S2 LEFT “1500后持续60+”更正为1/0/63/60。附件的额外 contact/holding/关节数字须按§2从现有 trace 复核；若旧字段不够，只标缺失，不重建假数据。

实现 v27 reader/reducer/launcher。静态确认所有输入路径、观测/action、load mode、evaluation flags 和 episode selection；用实际已有 trace 做一轮小样本端到端解析，再做一次 targeted runtime smoke。不能把新 quality 布尔值回写旧 artifact。

### Q0-DEV：三候选的质量开发集

C_S2/W_S2/K_S2 各 exact128/side，共768个 episode，新的固定开发seed 270001。所有候选完整报告；C/W 按128门评资格，K仅诊断。另按预定 episode IDs 每候选每侧3个 render；还应单列最差接触/最长时长个案，标为事后诊断。

候选选择规则先写死：C通过则选C；C未过而W通过则选W；均未过则 NO_QUALIFIED_CANDIDATE。K不在此候选集合中，不能因看起来更优就改 v26 路由。研究父策略仍固定C；无合格候选不阻止 v27.1 的质量研究。

### Q0-CONF：只有一个选中候选使用独立确认集

新 seed 270101，exact128/side，共256；不得看完确认集再换 W/K 重试。通过记 BILATERAL_QUALITY_CONFIRMED_SIM，失败记 QUALIFICATION_NOT_CONFIRMED。两种结果均完成 v27.0；旧 G7、Teacher/Student manifest 不更新。需要正式 handoff 时再请求 Owner 授权，而非先改后报。

## 4. v27.1：一个质量 overlay，与等预算 C continuation 配对

先做最小端到端修改，不铺 reward 大矩阵。两臂仅一个差异：

- C：保留 v26 C acquisition 配方。
- Q：启用已有 body-contact event 消费者：a2_door_body_contact_penalty_mode=event_v17，penalty_a2_door_body_contact=-3.0；event threshold=5N、peak_force_norm=200N、component_cap=2。除该注册 bundle 外，奖励/终止/stage/capability/加载路径不改。不加入 roll/pitch 使用奖励，不强迫持门过线。

这是复用既有 event_v17 与 v23 的同名 -3 scale，避免重写 reward 函数；其 dt/event 积分语义必须由实际消费者确认。不能仅改 scale 却没有启用对应 mode。[event consumer](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:17205)、[已有 scale](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_v23.yaml:78)

seeds101/102/103，各 C/Q 两格；全部从同一 C_S2 endpoint policy_only + actor RMS 开始，critic/optimizer/RMS中非actor部分和staged bank fresh。4096env，horizon64，每格3000，milestones1000/2000/3000各 natural exact64/side。六格同预算，候选不在中途更换。

终点决策：

1. C 三seed全部通过§2.2：QUALITY_ALREADY_PASS，选择C配方；Q的差异仍报告，不强求新干预有用。
2. 否则 Q 三seed全部通过，且逐seed/逐侧 complete−C≥−4，同时 LEFT clean_complete 的三seed平均差≥8个：QUALITY_ALIGNED，选择Q配方。
3. 其余：QUALITY_UNRESOLVED，结束自动训练序列，交付失败轨迹与下一轮建议；不现场扫 contact scale。

研究载体固定选中配方的 seed101 endpoint；不因 seed102/103更好而换。选择配方本身是开发决策，不是已完成独立效应确认。随后 heldout 按阶段收口统一执行，不能把 v27.0 的 confirmation复用为新策略确认。

## 5. v27.2：收敛门侧负载/摩擦分布，不同时扩所有 DR 轴

当前 v26 的门重80–120kg/把手高0.85–0.95m已实际绑定；native hinge friction=false，legged contact-friction/link-mass DR亦关闭。该阶段只处理门侧变量，手指/地面摩擦、Piper effort、控制频率保持不变。[common](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v26_common_scratch_lr.yaml)

使用已有 a2_v24_friction native backend，先确认远端/本机 IsaacLab setter/readback 和 drive/friction 并存语义，不能把阻尼当静摩擦。P02/P05/P10/P20 旧 profile分别是 static 2/5/10/20Nm、dynamic=.75×static、viscous=0。[profiles](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/config/ablation/wbmanip/base_v24_p1_friction_domain_escalation.yaml)、[backend](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/a2_v24_friction.py)

先用选中 research carrier 对 P02/P05/P10/P20 各 exact32/side作一次开发体征/边界测量（256 episodes），并核对实际参数。P10/P20只是 stress probes，不用策略 E1密度当所有方法的准入；它们不是本阶段必须学会的目标。

训练两臂，各seed111、从相同载体 policy_only+actor RMS、3000 batches：L0固定P02；L1每episode P02/P05各50%。两臂均采用同一个native backend和完全相同的drive设置；门重仍均匀80–120kg，handle height保持原域，左右各半。L0也启用backend，所以L0不是“旧v26原环境”的别名。额外保留legacy nominal评估判断迁移损失。

milestones1000/2000/3000：每臂对legacy nominal/P02/P05分别 exact64/side。终点要求L1在这三组每侧均过§2.2，且各 complete−L0≥−4；若未过，DOMAIN_NOT_CONVERGED，停止自动序列，不升P10/P20、不追加预算。通过时选择 L1 配方，不以“多域”名义声称其必然优于L0。

预留 confirmation：新门几何/起点seed 270202，friction static=3.5Nm与7.5Nm（dynamic=.75×static）各exact64/side；3.5是插值、7.5是训练域外压力测试，二者分开报告，不混成一个“泛化率”。选择不得使用这批结果再回调分布。3.5须过§2.2，7.5 report-only；未过3.5记DOMAIN_CONFIRMATION_FAILED并停止。

## 6. v27.3：真 scratch 与训练 seed 可靠性

只有质量与domain门通过才进入。使用确定的 L1 配方，seeds201/202/203，checkpoint=null、auto-load关闭；policy/critic/optimizer/RMS全新，staged bank靠自己真实到达填充，不注入teacher或其他seed快照。低层A2 locomotion policy仍按共同体系冻结，这里的scratch明确指高层门策略，不声称整个机器人从零学习。

每格6000 batches，保存1000/2000/3000/4000/5000/6000；这些milestone各 natural exact64/side，评估分层为legacy nominal/P02/P05。所有seed终点都报，不追加救援seed、不重置head冒充scratch、不挑中途best作为 endpoint。

三seed在三组两侧都过§2.2，才记 SCRATCH_3SEED_ESTABLISHED_IN_REGISTERED_DOMAIN；2/3或1/3记SCRATCH_SEED_UNSTABLE，0/3记SCRATCH_NOT_ESTABLISHED。固定预算下失败是有效结论，不回头把 staged bank 改成人工满库。

最后对三seed各做新的exact128/side mixed-domain确认（P02/P05各64，左右各自分层，seed270303）；要求每侧总 complete≥120、clean≥112，且每个friction子组仍满足64门。门失败保留 SEED_CONFIRMATION_FAILED，不宣称scratch已确认。

## 7. v27.4：条件开启单次失抓恢复 pilot

前提：§6三seed确认通过。目标仅为功能可行与方法方向判断，非论文确认。research parent固定§6 seed201终点，3臂同seed301、各1000 batches；不使用extra critic，不扩大obs维度，不混入pull。

### 7.1 状态与奖励语义

保留历史 max_stage/到达记录；新增当前 active skill 状态与失效事件。首次恢复环限于root未crossing、Stage3或Stage4中非计划失抓；已有release latch许可的主动放开不触发。非计划失抓判据为先已有Stage3/4 K5，再both_contact连续5个control steps为false；使用现有50Hz控制计数口径，参数写入resolved config。

恢复时：保持机器人/门/latch实际物理状态、episode时钟、RNN history；只清失效的当前grasp streak与技能局部进度，回到当前把手的pregrasp/regrasp。重新抓稳后，以当前物理latch/hinge选择回到Stage3下压或Stage4开门，不凭历史max放行。obs的stage编码对应active skill；历史到达仅用于记录。完成条件不变。

不得通过reset、传送、重新闭门或把episode时长清零实现“恢复”。stage progress类奖励必须基于每episode历史高水位而非重复入场累计；局部抓握奖励在恢复节点按注册语义消费，不能无限刷stage切换。保留初次到达计数，另计恢复次数，二者不相加。

### 7.2 三臂与最小训练分布

| 臂 | 运行时状态机 | 训练reset来源 |
|---|---|---|
| R0 | 现有单调状态机 | 原成功前向快照 |
| R1 | 新恢复环 | 与R0相同的快照采样 |
| R2 | 与R1相同恢复环 | 80%原分布+20%实际失效/重入边界快照，side均衡 |

三臂都接受同概率20%的单次训练扰动、同样的总步数/超时/quality reward。训练扰动是确认K5后的短时gripper-opening actuator command override，持续4个control steps，然后完全交还policy；必须记录命令、实际接触丢失与门/arm响应，不凭命令声称失抓。R2快照只能来自自己的真实扰动过程，不使用teacher成功数据。其采样器有两个显式状态：BOOTSTRAP沿用原reset分布；两侧均已产生有效恢复边界快照后，进入RECOVERY_READY，执行表中80/20分配。未ready的步数完整计入同一1000-batch预算；全程未ready记RECOVERY_DATA_NOT_ESTABLISHED，不伪造边界数据、不追加warmup，也不把空库当读错数据的fallback。

### 7.3 pilot评估、分母与结论

每臂endpoint在legacy nominal自然exact64/side；另对P02/P05各做单次注入任务exact64/side。注入时点为该episode首次满足上述稳定抓握且尚未过门；若从未达到条件，仍保留在ITT分母，记NOT_TRIGGERED。实际失抓子集另报恢复分母，不能用它替代全部64。

评估扰动持续6步，与训练4步不同；记录triggered/lost/regrasp/clean_complete。重新抓稳必须在失抓后300 control steps内，再在原episode剩余时限内完成；恢复没有额外总时间。另列legacy nominal域的sham（0步）exact32/side，用于确认观察/触发器本身不改行为。计数不足不是自动补采样理由。

仅当R2每侧实际失抓≥32例、恢复后clean_complete≥一半实际失抓例、ITT clean_complete−R0≥8/64、nominal complete−R0≥−4/64，才记RECOVERY_PILOT_PROMISING；同时给R2−R1，若R1相当则不能归功于边界采样。其余按NOT_TRIGGERED/RECOVERY_NOT_LEARNED/NO_ADDED_VALUE分别报告。单seed pilot只能触发下一阶段确认提案，不能自主启动v28大矩阵。

## 8. 实现范围与预算总表

建议文件：gr00t/rl/config/ablation/wbmanip/base_v27_*.yaml；新v27 reducer/evaluator/orchestrator与readout；恢复pilot采用小的v27状态/采样模块，在现有状态机hook接入。不得为了v27整理全部旧版本、修改trainer loader或旧reward函数。quality是新配置overlay；恢复奖励消费语义有专门§7合同。

| 阶段 | 最大正式训练batches | 自然milestone评估 |
|---|---:|---|
| v27.0 | 0 | 三候选开发128/side；最多一候选确认128/side |
| v27.1 | 6×3000=18000 | 3 milestones×6 cells×2 sides×64=2304 episodes |
| v27.2 | 2×3000=6000 | 3 milestones×2 cells×3域×2 sides×64=2304，加前述probe/confirmation |
| v27.3 | 3×6000=18000 | 6 milestones×3 cells×3域×2 sides×64=6912，加终点768确认episodes |
| v27.4 | 3×1000=3000 | 3 cells×(nominal128+扰动256+sham64)=1344 episodes |

最大正式训练45000 batches；另允许最多两次32-batch接线smoke（基础/恢复模块各一次），不进入统计。训练env/horizon固定4096/64；成本用本机首个稳定receipt估算，不将batches直接许诺为墙钟小时。只有前置通过才消耗后段预算。

一次必要的静态路径核对、功能路径smoke和针对实际新语义的小测试；恢复状态消费者改动做一次focused IsaacLab review。禁止泛化测试堆砌、反复审核未改变部分。工作区已有的未提交改动必须保留；Main是唯一整合/Git控制面。

## 9. Orchestration、失败与汇报

长跑独立tmux，orchestrator自动保存、调度eval与reducer，receipt记录完整命令、必要proxy env、effective config/load mode、资源、checkpoint与退出码；不记录秘密凭据。不新增哈希/SHA设施，旧stage已有provenance只引用。文件/root按phase/cell唯一命名，不覆盖历史。

GPU按Owner采纳时授权分配；允许与已协调任务共存，但以实际memory余量安排。不kill其他session，不把某GPU空闲写成永久事实。Main确认正确接线、首个有效训练更新和orchestrator在位后使用产品事件/长间隔唤醒；不要求每N个iteration人工监督。每个注册milestone和失败/结束必须汇报，不能睡过未自动处理的评估点。

非零退出立即停止该cell并保留证据；数据完整性或resolved-contract不成立记V27_INVALID。学习失败按对应科学结论收口，不加budget、不松阈值。发现可修复bug应记录最小cause/fix及新root计划；新训练重跑不由“合理修复”自动取得额外预算。不得broad catch、默认假数据、缺lane补零、失败后只挑好seed。

milestone向Owner报告逐cell/side/domain的D/S3+/S4+/open_hold/S5+/complete、clean_complete、接触/holding/overspeed/关节驻留、相对同seed对照差、receipt/integrity、活跃进程/GPU；出现与历史相反的读数也列出。由版本化简短readout承载，未变化状态保持安静。

## 10. 收口与下一阶段分支

交付scriptsFORhuman/v27/a2_piper_base_v27_execution_closure_<date>-Astra.md，包含资格结果、质量/domain/seed/scratch/recovery各typed outcome、所有未运行项、source/runtime/experiment证据等级、changed paths与资源状态。更新已被Owner采纳的memory路径，不把此草案先写成既定project truth。

v27可合法以QUALITY_UNRESOLVED、DOMAIN_NOT_CONVERGED或SCRATCH_SEED_UNSTABLE结束；v26仍然收尾。只有baseline与pilot足够支持时，提出v28的多seed恢复确认及history-adaptation对照；不自动运行。Teacher候选的正式handoff、G7修改、commit/push另提请求。

最终确认自己的writer、tmux、排他lease已结束；共享GPU上其他任务只记录、不处置。本文所有threshold是拟采纳的工程决策线，不是新实验数据；截至写作没有执行本计划。
