# v29 N02 plan：已握柄 push 后段的持续调节与身体通过

**2026-09-21独立审核状态：Owner要求将本v1.0交Pro严格复审。** [最新请求](../novelty/conversations/20260921_codex_n02_independent_review_request.md)质疑是否过早采用分层学习、模式承诺/退出限制、物理可执行性、技能训练不均衡、冻结历史与预测时域。本页保留当前候选供审议；FINAL表示上一轮planner定稿，**不表示Owner已接受该架构**。三类行为目标不等于必须拆成离散模式，Pro可推荐连续原LSTM或更小方案。本轮不按该方案启动实施/训练，GPU4授权仍保留。交付从[独立审核入口](pro_handoff/20260921_n02_independent_audit/README.md)读取。

版本：**v1.0 FINAL**；2026-09-21 20:12 HKT；负责人：N02 planner。状态：**计划定稿，GPU4已获Owner授权；B08公共修复已同步，N02方法尚未实施/运行。**

工作区 `/home/baoquanc/workspace/DoorDog-A2_Piper_v29_n02`，分支 `codex/v29-n02`。有效开发底座为完整 `v29-c002-baseline`＋B05＋本地已同步B08公共修复；原tag本身未改。本文取代v0.1作为当前方法/实施计划；[9月20日设计](../novelty/documents/20260920_n02_minimal_continuous_adaptation_design.md)保留研究来由。Owner来源：[两项裁定](../novelty/conversations/20260921_codex_n02_owner_decisions.md)、[本轮四问与GPU4授权](../novelty/conversations/20260921_codex_n02_finalize_request.md)。

## 1. 已接受范围与本轮定稿

| 项目 | 状态 | 内容 |
|---|---|---|
| N02-D001 | Owner已接受 | 首段已握柄push后段hold、有限推进、release＋身体路径；首段不覆盖所有困难门 |
| N02-D002 | Owner已接受 | Stage5进入/逐tick收入按身体通过；完成为root终点＋真实释放＋全身清离，共同支持握持/撤臂/回柄 |
| N02-D003 | Owner本轮授权 | N02使用GPU4；更多GPU用于额外ablation时，按具体问题和成本申请，不重复申请GPU4本身 |
| 本轮方法定稿 | Planner按Owner要求确定 | 单一条件执行器＋独立离散selector；行为训练与自主选择分开；selector只用统一物理回报；冻结c后才生成其后果标签 |

普通门近中性、arm操门，允许必要base平移/转向。强回关下首先兑现有效hold与身体继续通过。条件性roll/pitch和D023的释放后强回弹重抓仍属N02后续增量；本首段不包含隐式重抓，也不依赖N01恢复模块。

首段目标是实际根据交互改变行为，不要求必有新网络。原LSTM在共同支持下已经足够时，可以以该方案收束；小头有明确增益问题才进入后续步骤。当前任务是逐点回答并finalize计划，本轮未发起训练或占用GPU。

## 2. B08变更记录与基线证据

### 2.1 B08已落到本worktree，不再列为OPEN依赖

2026-09-21 14:36 HKT，主任务按V29-D075同步的公共补丁已在N02本地存在；本轮读取[共享记录](B08_SHARED_BASELINE.md)、[主实施记录](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_v29_B08_implementation_20260921.md)并定向检查四文件改动：

- `DeltaActionBase.step`删除override hook及调用，正常记录/累计arm增量、限位和目标映射保留。
- `DoorPregrasp`删除Stage0把六维arm累计target覆盖回默认值的实现，canonical step中的同类调用一起删除。
- `a2_v26_4_accumulate_physical_delta`删除`stage0_mask`及在线恢复physical origin；普通/canonical路径都不再按stage清累计，RIGHT镜像语义保留。
- 原 `v26_4_r2_c_identity_proof.py`同步删除失效的Stage0清零断言；这是已有公共补丁的一部分，本轮没有新增或执行测试。

真实episode reset仍初始化累计target与动作历史，Stage0默认姿态reward及晋级条件未因此删除。**B08修复了在线动作覆盖，不等于N01整套方案或N02三行为已经实现。** 原任务已有CPU生产step提取路径证明：输入0.2、scale0.3，连续三步累计约0.18，镜像和选择性reset符合预期。该CPU证据来自主任务，本轮没有复跑；不是Isaac运行或策略收益证明。

四项改动为本地未提交的共享修复，保留而不重做。GPU0/GPU1原任务使用冻结运行输入，其结果不是B08修复后结果。N02后续比较以“C002＋B05＋B08”作为共有执行底座，不能把B08贡献算进后果头收益。

### 2.2 已归档结果只确定起点资格

[C002 6000读回](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md)的0/64是历史时点，不再表述为最新成绩。[baseline已发布入口](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_baseline_TODO.md)记录D076的7000自然64里程碑：LEFT31/32 goal，RIGHT31/32到Stage3但无Stage4。这里只引用已发布结论，不读取运行STATUS或监督后续等待。

这些结果不能直接证明新的条件执行器合格，尤其不能证明B08后、双侧三行为或Student资格。冻结c之前仍需本计划内的实际行为证据。旧逐集结果缺失B05 family时不补猜七族表现；N02新数据记录实际family即可。

## 3. 共同物理任务：所有模式用同一把尺子

### 3.1 通过、握持与完成

以下是环境reward/监督/计分量，不因本设计进入Student输入：

| 量 | 操作含义 |
|---|---|
| `body_clear` | trunk、腿/足、后部及base附件越过门截面并离开回关扫掠区；不包含仍连门的操作臂及其附件 |
| `fully_clear` | body_clear且arm、手部、腕部附件也清离门/框与回关扫掠区。授权指–柄接触可免碰撞处罚，但仍握柄不算清离 |
| `released_now` | 接触与相对捕获几何支持当前已实际脱离把手约束；开爪命令、单帧零接触、旧release gate均不能单独替代 |
| `need_door_assistance` | 当前身体/撤臂路径仍暴露于回关区域；fully_clear时为false，历史释放资格不能永久将其清除 |
| `pass_progress` | 用实际位姿计算身体后部包络沿门开向法线的净推进；另记通路净空改善，允许必要重定位 |

包络使用实际collision几何的少量外包络、door slab/frame和允许回关扫掠区，左右门按各自门坐标变换。可先用允许角范围的保守扫掠，保守性和余量在首个实际片段中说明；不将Pro固定脚位力模型当碰撞几何。

Stage4→5表示开始身体通过：保留root跨原截面，去掉hinge阈值和handle回升的晋级要求，允许握柄进入Stage5；阶段继续单调。Stage5的stage收入仍逐tick，条件为当前通路可用且有有效通过/净空改善，或当前fully_clear，不由历史clear latch永久给分。

Stage5内：`complete_now = (root_x - env_origin_x > 1.5) & released_now & fully_clear`。不另设精确默认arm q门槛；充分撤臂由几何表达，收纳用shaping。release可先于fully_clear；清离后门正常回关不使完成条件或stage收入失效。计划保留30s、原阶段预算/余额结转及50-tick完成延迟，模式切换不重置任何时间或信用。

记录计划开爪、实际脱离、意外失抓、body_clear、fully_clear和真正terminal。失抓后仍完成可记物理任务成功，但不记controlled-release成功。已有complete收入在delayed reset期间持续、goal存在latch，不能把它误当一次性奖金或以曾达goal证明随后无碰撞。

### 3.2 统一任务回报 r_task：严格不读取mode来改变得分

采用 `r_task = f(实际状态转移, 实际执行动作, 共同任务时钟)`。**同一物理转移和实际动作，换mode名称不能改变回报。** 三模式和无头/有头对照共用系数、时间预算与计分口径；自主选择阶段固定这份reward配方及其归一化，不做按模式分开的reward curriculum。

| 项 | 共同物理触发条件；不使用mode开关 |
|---|---|
| 通过、阶段、完成 | 依据上述实际通路、净推进、清离及完成；保留实际耗时影响 |
| 有用握持 | 实际有效握持、仍需辅助且服务于身体通过/所需净空，不因名字叫HOLD就给收入；静止门角不等于无用，原地无限夹持不增加新收益 |
| 撤臂/回默认 | 依据实际握持、实际脱离与身体/arm暴露状态设置目标；仍有效控门时不强迫回默认，实际脱离后鼓励清离、fully_clear后鼓励收纳。不能“选HOLD就免罚、选RELEASE就得分” |
| gripper收纳 | 清离后的真实手部收纳条件才恢复闭爪偏好；不能因选择RELEASE就切换通用奖励或仅奖励一个开爪命令 |
| handle回升 | 依据实际解锁/机构状态与是否仍需压柄，允许已解锁后握柄与handle回升并存；不能按mode放宽机构条件 |
| 姿态、动作、接触 | 相同实际roll/pitch、动作速率、非授权接触/过力使用同一代价，不按“困难/某模式”免除 |

这修正v0.1中容易被理解为“按mode开关回臂/闭爪通用奖励”的写法。mode只能改变执行器的行为目标，不能替selector更换评分规则。共同任务本身的奖励权重仍需首个真实行为片段支持，不宣称以上设计已经证明不存在其他奖励投机。

## 4. 三种行为怎么学：一个共享条件执行器

### 4.1 架构与命令位置

Teacher、Student分别使用自己的执行器；每个执行器内部三种行为共享同一个原LSTM/视觉骨干和动作decoder：

`h_t = E(o_<=t)`

`a_t^12 = D(h_t, onehot(mode), phase_t)`

mode的3维one-hot与1维自指令phase放在**LSTM之后、动作MLP之前**，不作为新增门传感器、不使用真值stage。每拍E只推进一次真实历史，候选查询只重复纯decoder/后果头计算，不复制/清零hidden。输出保持base5＋arm_delta6＋gripper1；选中高层动作后再产生匹配leg12。没有三套独立训练的技能网络，也不把真值IK作为部署执行器。

| mode | 初始10 control tick | 后续30 control tick与退出 |
|---|---|---|
| HOLD_TRAVERSE | 维持有效握持，arm与base反馈协调 | 持握并继续身体通过，抑制无用门运动 |
| ADVANCE_TRAVERSE | 一次有限开向推进 | 转为hold/traverse；这是phase规定的续接，不是selector再次选模式 |
| RELEASE_TRAVERSE | 实际开爪与撤臂并开始通过 | 继续撤臂退出；本首段一旦发起RELEASE，就以同一退出程序持续到任务结束，不隐式重抓 |

初版40 tick对应当前20ms时基的0.8s；每tick仍反馈观察和连续动作，不是开环保持命令。HOLD/ADVANCE到窗末才重新选择。需要更快重规划时，修改并重新绑定控制协议及数据，而非保留旧标签却悄悄逐步重选。真实done可以提前终止。

### 4.2 模式分配与行为训练回报

**先外部指派mode训练c，不先让尚不会行为的selector挑最容易的模式。** 在真实建立握持/解锁的后段机会，三模式按决策窗口各1/3交错采样，同一batch/训练过程更新共享参数；在左右门/B05/回关条件内打散，不固定env前缀分工，也不逐个训完后覆盖前一个技能。

1/3是**训练指令分配**，不是部署概率或要求三模式执行tick相等；RELEASE尾段长短不同，实际窗口、tick、失败分母均记录。自然完整轨迹保留以维持接近/抓握能力；后段机会不足时可用受控局部起点或真实前缀补暴露，但必须实际形成握持，不能把reset位置重合当成功抓握。局部/自然起点分表。

执行器学习用 `r_c = r_task + lambda_skill * r_skill(mode)`，由现有连续动作PPO学习同一个c；必要的短oracle动作示范只用于说明/启动行为，不代替最终策略执行。

| 仅行为学习的临时 r_skill | 作用 |
|---|---|
| HOLD | 在有效握持下抑制不必要门速、保持可用arm工作空间，并配合身体前进；不奖励接触力越大越好 |
| ADVANCE | 初始段奖励实际有用开向进展，后续转为持握；不持续奖励把门推到最大角 |
| RELEASE | 实际脱离与撤臂轨迹进展，而非只奖励命令为正；最终通过仍由共同r_task衡量 |

这些临时项只进c的行为学习loss及其训练value目标，**绝不进入selector的return、advantage、value target、候选评分或最终成绩**。模式之间临时shaping不同是为了教会不同指令，不保证原任务最优性不变。selector阶段停止这些学习信号，也冻结c，不让c通过后续联合更新退化成只会一个模式。

### 4.3 局部入口与整任务入口

首段功能/学习可由真实握持窗口开始；利用模拟真值安排这种起点属于训练/局部诊断，不算Student自然任务。整任务保留共享decoder的**名义续行**上下文（mode全零，复用原接近/抓握行为），同一自主selector在进入N02前可选名义续行或三个程序；是否开始使用N02也由自身h决定，不由Student外部真值stage/contact决定。进入N02后三选，发起RELEASE后仅继续退出。

名义续行不是新增第四种开门技能，也不是另挂旧Teacher。它和三模式同属一个c，冻结时一起冻结。整任务若一直没有启用N02，完成成绩仍如实保留，但不能据此声称使用了N02信息。

## 5. 自主选择怎么学：独立离散selector与真实回报

### 5.1 候选与选择权

候选生成器只枚举上述三个固定程序及其既定身体路径/phase，使用当前h经同一decoder得到相应首拍动作；不先训练另一个候选生成网络，不按门质量/真值风险挑候选。每个程序内部的连续arm/base协调由c完成；Student生成器也只使用Student输入与自指令。

无后果头基线为 `g_0(mode | stopgrad(h))`；方法组为 `g_1(mode | stopgrad(h), stopgrad(p_useful), stopgrad(F(H)), stopgrad(F(A)), stopgrad(F(R)))`。它们是小型categorical selector，使用相同可选程序、同一冻结c与相同任务回报。全任务入口额外包含上述名义续行选项；局部三选不读真值可行性筛选器。

**selector用离散PPO、从真实执行的r_task学习，不用“正确模式”的oracle分类标签。** 预测只作为输入特征，不能用预测的进展/低风险分替代环境奖励，也不直接按预测argmax宣称其已学会选择。Teacher selector使用Teacher信息；Student selector用自己的h/预测及自身执行回报，不默认由Teacher模式标签就能迁移。

### 5.2 不同时间跨度的正确记账

选择m后实际持续K个control tick，累计：

`R_window = sum_i gamma**i * r_task[t+i]`

`target = R_window + gamma**K * V(next_decision)`（非任务终止时）。

HOLD/ADVANCE通常K=40或提前真实终止；RELEASE首次选择之后的强制退出尾段也归该选择，累计至任务终止，而不是只计前40tick后把剩余成本丢掉。所有tick的时间/接触/完成回报都算入；不按模式平均窗口得分或只给每次选择一次时间罚。RELEASE尾段没有新的自主选择，不能制造重复selector样本刷信用。

完成/任务失败不bootstrap；单纯rollout切分/采集截断在正确末状态处理bootstrap，不跨auto-reset连到下一集。阶段/总任务超时按本首段任务失败口径处理，不能盲用一个通用time_out位将其与完成混算。selector记录真实categorical log-prob，不能复用12D Gaussian动作log-prob。

固定c时只训练selector和其独立value head。LSTM/vision、输入归一化、decoder、动作采样规则、p/F均不接收selector梯度。**参数冻结不等于hidden冻结**：两套hidden仍沿真实轨迹逐tick推进，仅真实done reset。

## 6. 先有可用c，再学它的后果

| 顺序 | 实际工作与可以声称的交付 |
|---|---|
| P0：共同任务与功能链 | 使用已同步B08底座，接通通过/清离/真实释放与统一r_task、12D命令链；短功能片段显示hold下身体通过、有限推进、释放撤臂、清离后正常回关。真值IK演示只证明动作路径 |
| P1：条件执行器学习 | 外部均衡mode指令、共享c、r_task＋临时r_skill；保留自然轨迹。实际区分三种响应，并有相应条件下继续完成身体通过的证据；发出动作或有有限权重不算c可用 |
| P2：冻结c_v，建立自主基线 | 确认冻结后的实际推理规则可执行后，冻结整条c并用真实r_task训练g_0。行为训练可Gaussian探索，冻结版默认确定性action mean；冻结后另换随机规则即新版本 |
| P3：有价值时采集与学后果 | 在固定c_v下随机指派实际候选，保留全部factual人口；只监督执行的m。训练小p/F读出，不回传c，随后冻结p/F。g_0若已足够，此步可不进入 |
| P4：接入选择并比较 | 同一c_v下从g_0出发训练g_1，只更新selector/value，用同一真实r_task。无头对照也获得可比的额外交互/优化预算；后果采集/拟合成本单列，不能把它当免费优势 |
| P5：Student自己的对应链 | 条件c_S先从同mode的Teacher12D示范/真实Student轨迹学习；再冻结c_S，学习自己的g_0、必要时采集F_S并训练g_1。不能拿c_T的未来充当c_S后果 |

P0先实现并展示可见功能，再按实际需要验证，避免预建测试/快照框架。三种动作在错误物理条件下可以失败，这些失败是后果数据，不要求每种模式在每扇门均成功才开展选择。若连适当条件下的动作都不能兑现，先修c/训练暴露，不能用预测头替代执行能力。

随机指派的后果采集是独立数据阶段，不冒充当前selector的on-policy PPO rollout。PPO采样保持其真实旧策略概率；离线随机数据可以训练F，但不能不加区分地塞进g的on-policy损失。

首批最小冻结内容包括：E/vision权重、输入RMS及预处理、D、动作mean/随机规则、mode/phase/时窗、累计/缩放/限位路径与冻结腿策略。集合记为简单版本名如`c_T_001`或`c_S_001`，不新增内容哈希体系。共同r_task、环境/标签定义也单独记版本；冻结后不悄悄让RMS继续在线更新。

## 7. 后果目标、版本与旧数据

后果头记为 `F_v(h,A)`，对应此前`Q(h,A,c_v)`的**短窗物理后果向量**，不是随未来selector变化的长期RL Q-value。首版预测40tick内身体通过进展、非授权门/框接触、fully_clear事件；p_useful估计当前有效交互，不是力大小。静止可靠hold可为有效，模糊接触标unknown，不冒称双指接触就是force closure。

F的40tick窗口内A/c完全按已约定程序执行；HOLD/ADVANCE下一次自主选择发生在窗末之后。RELEASE真实退出可能更长，其尾段风险/任务收益由完整真实selector return覆盖；**不能凭F在0.8s内没预测碰撞就批准整个释放过程安全**，也不能将短窗输出描述成全程风险预测。

| 变化 | 旧标签如何处理 |
|---|---|
| 只更新g，c/标签定义不变 | 短窗后果定义不变；状态访问分布可能变化，必要时在新分布补采同一c的数据。无需因为g更新就重命名全部标签 |
| 只更新F，c不变 | 原factual标签仍可用；在轮次边界重新拟合/冻结F，下一轮g用新鲜on-policy数据。不能在同一PPO rollout更新共享预测特征制造旧概率错配 |
| 更新E/vision、RMS、D、动作随机性、执行链或续接规则 | 形成新c版本，重新取得行为证据并采集它的factual未来；旧标签保留为旧c历史，不改名当新版结果 |
| 用新E重算旧prefix/hidden | 只改变表示，不生成新c未执行的未来，不能据此“重标注”新版动作后果 |
| Teacher变Student，或改变目标/几何标签定义 | 明确新控制器/新标签语义；不把Teacher代控或旧清离定义产生的结果混成新版Student监督 |

旧模型权重可作为初始化，旧物理未来不能自动当新c监督。旧数据不删除，来源与覆盖保留；首版不建跨c通用预测器来规避重新采集。mode、实际执行者、c版本、协议、起点与终止原因随每窗记录。

保留短、失败、无接触和未到窗口的人口。碰撞提前终止时risk已知为正，其余未观察未来逐目标mask；超时/记录停止不补成安全，一条hold轨迹不能给release反事实标签。冻结c可缓存当时h和跨rollout待结算事件，不先要求完整快照；旧数据replay/换Teacher重标注若确有需要，再保存对应真实prefix。

## 8. Teacher与Student输入、历史及独立成绩

Teacher133D特权条件、Student81D＋RGB保持；Student及其selector/候选生成器不增加stage、接触力、门角/位姿/质量或base linear velocity真值。mode/phase是自身命令。已知q/gravity/目标可计算目标误差/限位，但未知载荷和门几何不能用“小模型”暗补。

Student的actions19D是腿12＋累计arm target6＋gripper1，另有6D delta，不是高层12D，也不是实际q/力。保存提议与真正执行命令、累计目标和实际响应的对应关系；模拟真值仅作训练监督/计分。送入actor的RGB视路、帧时间/延迟按实际配方绑定，不把旧trunk外参或录像当作v29输入证据。

c_S训练时Teacher始终沿同一真实Student轨迹维护自己的hidden，并针对同一自指令mode查询动作；Student自己真正执行的采集与Teacher示范分开。Teacher标签资格按已证明局部区域说明，未知/失败样本保留其他监督和人口。之后的小型Student selector可以用真实环境回报学习，但不默认解冻整个Student执行器作RL fine-tune。

8tick是数据/梯度窗口，不是记忆清零。mode切换、控制权交接、窗口缝和rollout缝均保留hidden、arm累计与腿历史，仅真实done reset。Teacher/Student不共享hidden，后果头不需要反复消费一帧来评三个候选。

独立Student成绩必须自然起点、自己决定何时进入三候选、全程无Teacher接管或真值selector；局部真实前缀接手另列。未启用N02、未到交互、实际失抓及未覆盖重抓需求都保留。任务完成、预测误差和信息是否改变选择是不同证据。

## 9. 源码落点与最小实施边界

本轮只检查已发生的B08补丁，没有重审C002。下列是方法实施落点，不表示已修改代码：

| 路径/模块 | 职责 |
|---|---|
| `config/ablation/wbmanip/base_v29_n02.yaml`（拟新增） | 继承完整C002+B05，使用本worktree共享B08；N02共同任务配方与行为训练临时shaping分开，不改冻结baseline输入 |
| `envs/door/door_open_a2_base.py` | body/full-clear、真实释放、Stage4/5/完成；统一物理r_task。几何必要时收在同目录小模块，mode私有shaping与task回报分开返回/记录 |
| `envs/base_task/staged_task_base.py` | 复用阶段/时钟/延迟完成；不为mode重置阶段预算。优先task override，不重造任务框架 |
| `envs/base_task/delta_action_base.py`、`envs/door/a2_v26_4_canonicalization.py`、`envs/base_task/a2_base.py` | 保留已同步B08与现有累计/限位/leg组合；不再实现Stage0修复或增加兼容开关 |
| `trl/modules/actor_critic_modules_recurrent.py`、`vision_actor_critic_modules_recurrent.py`及小型N02模块 | 复用现有Memory/视觉；暴露一次h、条件D、独立categorical selector/value与可选p/F。无需独立历史encoder |
| `trl/trainer/ppo_trainer_a2_base_api.py`及N02选择训练入口 | c阶段是连续12D PPO＋临时skill奖励；g阶段用窗口transition、categorical log-prob、真实任务回报与gamma**K。复用已有PPO计算，不冒用continuous动作的log-prob |
| `trl/trainer/distill_trainer_a2_base_api.py`与N02 Student配方 | 同mode的12D监督、真实Student执行及各自hidden；当前独立auxiliary policy插槽受限，小头在N02 actor模块内接入 |
| `scriptsFORhuman/v29/n02/`（按需要创建） | 一条真实功能入口及简短读回，之后才增加对应训练/采集/选择命令；不先建庞大编排或测试工程 |

以上代码路径均相对`gr00t/rl/`，最后一行为仓库相对路径。公共B08四文件已有外部改动归主任务，本轮只记录/保留；N02自己的首个实施包仍为P0。

## 10. 比较、资源和执行交付

最小比较分三层：

1. 原C002参考 → **B08＋共同任务/行为支持＋相应暴露**的原LSTM执行器/selector。只能归因这组共同变化，不将其包装成头收益。
2. 同一冻结c下无头g_0与有头g_1，传感输入、程序集合、统一r_task、控制时序一致；给无头组可比的额外交互/优化机会，单列后果数据与计算成本。模式shaping绝不进入其中任一组的selector评分。
3. 后果误差/覆盖，合理同人口特征置换下的动作变化，独立任务完成/耗时/接触分别报告。Teacher、Student、局部接手与自然整任务不混为一个成绩。

每组保留全部分配episode和实际mode使用、身体净进展、握持中断/实际释放、非授权接触、全身清离与未覆盖数；旧/新Stage5定义不同，旧stage reach不能直接混算。split以门实例/episode为单位，镜像及同门不同策略不跨集泄漏，不用成功长窗筛掉短失败人口。

**GPU4是已授权的N02资源。** 功能、主学习链和必要的无头对照优先在GPU4串行安排；小读出可按实际成本使用CPU或同GPU。本轮不申请更多GPU、不检查/占用设备。若特定ablation确需并行，再提交“问题—对照—额外设备—预计时长/成本”的具体申请；原GPU0/GPU1任务与等待不变。

定稿不虚构launcher、checkpoint或已验证训练规模。实施产生首个可工作路径后，运行记录须有实际source/config、checkpoint/控制器版本、命令、GPU4绑定、规模和预计时长；不因为已有GPU授权设置无限重试/实验队列。当前本轮只完成问答/定稿，未发起运行、模型重算、测试、Git提交或发布。

Pro夹持模型的局部更正与证据边界沿用[本地核对](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pro_reviews/v29/20260920_162527__N02_online_adaptation/LOCAL_RECONCILIATION.md)：156条press_down的90/36.4N不是完整容量，45/18.2N仍为假设必要界；原件/模型未重跑，仿真限值不作硬件能力。它不是P0前置。

学习记账参考一手方法：[PPO](https://arxiv.org/abs/1707.06347)支持独立策略/价值更新的算法起点；[时间扩展动作](https://www.sciencedirect.com/science/article/pii/S0004370299000521)说明按实际持续时间累计回报/折扣；[reward shaping边界](https://ai.stanford.edu/~ang/papers/shaping-icml99.pdf)不支持将任意mode shaping直接视为不改变任务目标。这里采用的是明确的项目设计，文献不构成DoorDog运行证据。
