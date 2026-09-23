# v29 B02 / B04 独立决策与审阅

B02选择A：软件定义的虚拟锁闩，以原生门轴限位实现物理约束，不直接重写运行中的门状态。

B04选择原生 joint limit：每扇门固定一个随机正常最大开角；不用逐步角度裁剪，也不新增实体门挡。

**结论等级：有源码/API依据的设计推荐；未实施、未仿真、未训练验收。** 本文与 DESIGN_SPEC.md 共同构成所选方案，后者是参数/状态/接线的统一规范，不是已应用补丁。

## 1. 本次材料、阅读范围与证据等级

输入定位：仓库 `https://github.com/Jam-Stark/DoorDog`；review 分支 `codex/v29-b02-b04-pro-20260918`；提交主题 `Prepare v29 B02 and B04 Pro decision handoff`；提交时间 `2026-09-18T17:14:54+08:00`。只以本次 manifest 中的文件作为当前工作区证据。旧 review 的 B02/B04意见是参考，不继承其全部工作范围。

已从指定 Drive 目录取回五个文件。两个 ZIP 分别为 438,863 bytes / 35 个成员、63,988 bytes / 10 个成员；独立解压、ZIP CRC、manifest 的45项路径及文件字节数一致。没有生成哈希清单。按 Owner 指定顺序，先阅读 OWNER_REQUEST / REVIEW_BRIEF / SOURCE_INDEX，核对本次 source/config 和本机限位API节选并形成 A＋原生限位初判，之后才阅读 LOCAL_CONTEXT_AND_OPTIONS、baseline plan、旧 Pro B02/B04相关文字。

关键源文件与原始行号见 [SOURCE_MAP.md](SOURCE_MAP.md)，随包保留[关键源码节选](source_evidence/SELECTED_SOURCE_EXCERPTS.md)及[本机API原文](source_evidence/ISAACLAB_LIMIT_API.md)。远端抽查了 door.py 的实际关节/锁舌构造、creation helper及模拟器力矩接口；**没有把远端抽查说成整棵分支与输入包的全量逐字比对**。大环境文件的 GitHub 内容接口返回空、raw接口拒绝读取；该文件已从 source ZIP读取，所以其下文审阅并未缺失，但不声称 GitHub 在线全文读取成功。

这里区分四个等级：

| 标签 | 本文含义 |
|---|---|
| SRC | 本次源码、配置、Worker元数据中直接可见的事实；静态接线不等于运行生效 |
| API / PRODUCT | 官方公开API或厂商产品资料；版本和产品适用边界单列 |
| DESIGN / INFERENCE | 本次选择、参数及由明确机制推出的结论，不冒充实验结论 |
| LOCAL-ONLY / UNKNOWN | 需要本机运行才能确认，目前未验证 |

本次不是45份文件逐行全审：大型环境文件按锁闩、物理循环、reset、staged、reward、observation和释放链路定向阅读；URDF/相机、其他任务线、旧报告v28验收与相机研究不作本次论据。未访问未入包checkpoint、GPU状态、硬件或未提供logs；没有运行Isaac Sim、MuJoCo、CUDA、训练或新render。包内9月17日64-env/one-batch记录仅证明**旧接线**曾完成该范围的运行，且 learned_behavior 标为 NOT_EVALUATED；不能转用于新B01/B02/B04。

## 2. 最重要的发现

### 2.1 当前 B 是真正的碰撞锁舌，但“物理”不等于已经标定真实锁具

`door.py:513–632` 创建三自由度结构：hinge、handle、latch；handle 为0–45°；prismatic latch 为0–30 mm。锁舌是门上方、靠自由边的 cone，经过与门框的碰撞/脱离阻止或允许门转动。不是已有 Boolean 开关。[S01]

USD mimic关系为 `s + g*q_handle_deg + offset = 0`，当前 `g=-0.03/45`，所以理想约束下45°对应30 mm。要推出解锁角，还需要实际脱扣所需的 `s_clear` 和接触余量；固定门位姿和几何下只能写近似关系 `q_clear_deg≈45*s_clear/0.03`，不能把0.6 rad、45°或30 mm直接当精确脱扣阈值。[S01, API04]

官方mimic是双向力学耦合：锁舌的碰撞冲量也可传回handle。它可能提供有价值的预载/卡滞信号，也可能引入这个高位代理结构特有的反馈。未提供接触测量或实际锁体标定，不能断言该反馈更接近部署对象。`rotX` token 本身不是已证实错误；官方支持单DOF转动/滑动关节的连接及相应角度/距离单位。[API04]

### 2.2 A 不必抹掉“推不动”的物理反馈

选A不是 `q_hinge=0` 或 `q_hinge=clip(q_hinge)`。本设计让求解器在窄限位内承担锁住时的约束反力；机器人仍通过真实gripper–handle/panel接触受力，解锁后仍需克服B01质量、闭门器和摩擦。A删除的是实体锁舌的局部脱扣/摩擦/回传细节，而非所有接触和反作用力。[DESIGN, API01–03]

代价必须承认：A不能用来论证“学会了真实斜舌被压紧时的减载解锁”、锁舌回弹声音/碰撞、某种锁体内部失效恢复，或者真实锁具的负载依赖解锁角。它是可控的任务级机械近似。

### 2.3 B04最小联动不只是把150改成随机数

现有位置奖励在约90°饱和不是限位。更关键的是，`_reward_push_door_hinge` 只给位置项乘了 Stage4 release gate 的收入mask，速度项仍保留；`_get_a2_door_income_hold_mask` 也未在Stage4 gate后关闭 hold-and-drive 收入。持续向正开门方向运动仍可能得分。因此90–150°限位随机化本身不能推出“无需到挡止就释放”。[S05:17562–17582,15140–15162,18341–18401]

另一个逻辑差别：当前回默认臂姿态使用 `~both_contact`，它包含“还剩单指接触”，不是双指均已断触。Stage4→5也没有实际断触条件。[S05:15949–15983,29884–29906]

### 2.4 一个容易继续传播的单位/接线错误

`_reset_door_states` 把 `15*pi/180` 写入 `door_dof_target[:,1]`，注释为 tension handle；但调用的 `apply_torques_at_task_dof` 最终是 `set_joint_effort_target`。它是约 **+0.261799 N·m的effort目标**，不是15°位置目标。USD作者层另有−15°回位目标，不能把二者混为一谈。[S05:29444–29466,S08:2818–2840]

IsaacLab运行时还会传播位置、速度、effort目标。仅看到USD drive目标不能证明每个物理步的实际目标未被运行时buffer覆盖。所选设计必须建立单一回位负载来源；这是明确化接线，不声称“完整复刻当前有效回位力曲线”。[API03]

## 3. B02 A/B比较与明确选择

| 维度 | A：虚拟锁闩＋原生限位 | B：保留现有实体代理、有限调整 |
|---|---|---|
| 解锁可控性 | θ_u显式可审计；可加滞回和复锁规则 | 脱扣由stroke、cone/frame几何、接触和solver共同决定，当前精确阈值未测 |
| 接触/反馈 | 保留机器人接触、门惯性与限位反力；丢失锁舌局部受力细节 | 保留cone/frame阻挡及双向mimic回传；真实性尚未标定 |
| 一次实现成本 | 需要FSM、两DOF迁移、缓存/恢复及运行时setter接线，绝非只切build_latch | 最少可保留现有拓扑；做可控角度随机化时仍需有限几何/行程协同 |
| 长期维护 | 参数与事件含义明确；可避免不断追查代理几何 | 需持续维护几何、mimic/stroke与左右门接触的一致性 |
| 并行成本 | 少一个DOF/锁舌接触，但setter会CPU传整份limit缓存，不能保证更快 | 多一个DOF和接触/mimic约束；不需每次解锁host修改门轴限位；已有旧运行但新域成本未知 |
| 角度随机化 | θ_u与机械止挡独立定义，联合采样保证可达 | 可做，不能只改handle limit：应协调s_clear、gearing、stroke上限和余量 |
| 自然/关门恢复 | 门开后回柄不重锁；回到捕获区才复锁，由FSM明确实现 | 依赖实际cone/frame重接触、闭门挤压与mimic回传；现有复锁可靠性未知 |
| staged恢复 | 必须保存隐藏FSM/配方、废弃旧三DOF bank | 必须恢复三个DOF及mimic兼容状态、接触一致性；也非只保存门角 |
| 观察与N02 | 不加答案观察；有时序交互，但统一压到底可绕过阈值辨识 | 同样不需答案观察；更多反馈不等于Teacher/Student一定利用，也不自动等于真实N02能力 |

**我选择A。** 当前任务需要的是在B01新力学域中建立可解释、可采样、可恢复的解锁机制，而不是先把未测的高位cone脱扣曲线用更多参数包装成“解锁角随机化”。A的一次拓扑/恢复迁移是真成本，但范围明确；其最关键不确定性集中在“动态窄限位的稳定性与host更新成本”，可用少量本机检查直接判别。

B不是被判定为错误或必须精细重建实际锁体。它可作为现有实现保留在历史任务配置中，不要求本轮再实现或训练一套B。若A在必要的限位强度/游隙下不稳定，或host切换开销不可接受，B才成为重新决策的主要替代；不能通过偷偷增大游隙、瞬移门角、修改stage阈值来掩盖A失败。

## 4. B02统一参数与机械事件

### 4.1 采用的参数

| 参数 | 本次选择 | 解释与边界 |
|---|---|---|
| handle机械行程 | 原生 `[0°,45°]` | 保留现有有限操作包络，不做65°扩展 |
| 解锁角 θ_u | 每门 `Uniform(25°,40°)` | 有限工程覆盖域，不是实物统计或当前B的标定 |
| 退回阈值 θ_r | `θ_u−3°` | 滞回；低于该值表示虚拟锁舌伸出/待捕获 |
| 机械余程 | `45°−θ_u`，即5–20° | 联合规则自然保证至少5°，不是全部门固定+5° |
| 锁住时门轴范围 | `[0°,0.25°]` | 非零物理游隙；不使用未证明可用的`[0,0]` |
| 复锁捕获门角 | `q_hinge≤0.10°` | 严格小于窄上限；绝非reward里的0.1 rad |
| 门离框诊断角 | 2° | 仅区分near/open事件，不增加新的锁定物理边界 |
| handle回位drive | cap `Uniform(1,3) N·m`；USD K=50、D=0.5；目标−15° | 保留名义作者层参数域，明确runtime目标并移除混淆的正effort；非实测扭矩曲线 |

0.25°对应本次门宽0.8–1.1 m时，自由边位移约3.5–4.8 mm（`w*sin(0.25°)`）。这是允许的几何游隙估算，**不含solver超限、框接触偏置或结构变形**。它远小于Stage3→4的0.25 rad。实际受载超限是否可接受，必须local测。[S01,DESIGN]

为何不直接选20–60°：在45°机械止挡下会生成不可解锁样本。若把机械止挡随阈值设为`θ_u+5°`，则止挡跨度25–65°，数学合法但同时扩大把手/夹爪碰撞、可达性和运动负载域；本轮没有证据要求承担这种扩展。20–40°/45°也是合法的更宽低端候选，但本次明确采用25–40°，先围绕既有约34.4°的shaping量级做有限扰动；这不是把0.6 rad误认成脱扣测量，更不是声称25°具有经验最优性。

厂商PDQ XGT当前产品页给出标准41°操作转角及特定配置65°转角。这说明产品操作包络确实不唯一，但**操作转角不等于精确解锁阈值，也不等于最大机械过行程**；该资料不足以证明20–60°均匀解锁分布。产品抗破坏扭矩也不应用作回位/解锁扭矩。[PRODUCT01]

### 4.2 状态与事件

隐藏状态只需 `handle_retracted` 与 `latch_engaged` 两个布尔量。它们属于环境物理语义，不进入actor/Student/critic新输入。

- 关门且未压柄：`engaged=True`，门轴是窄限位；推门可产生接触与约束反力。
- 把手达到θ_u：`retracted=True, engaged=False`，仅把上限恢复为本门真正的θ_max；不改q/qdot，不给开门速度，不取消闭门器或摩擦。
- 把手降到θ_r以下但门仍在捕获区外：`retracted=False, engaged=False`，表示锁舌已伸出但不在门框内；**不能把已开门瞬间锁在0°附近**。
- 门回到捕获区且把手不保持退舌：`engaged=True`，收紧上限。当前q必须不超过新的上限；不靠重写状态满足这一条件。
- 持续压柄关门：仍为unlocked；松手后，只有位置已在捕获区才复锁。

所以自然失抓可以有两类后果：尚未离开捕获区就松手会复锁；门已打开时松手只让把手回位，随后是否闭门及何时复锁取决于真实门运动。不会用“进入Stage4”永久屏蔽复锁。

### 4.3 “压到底再试推”的政策

**baseline允许。** 不额外制造“必须先猜出θ_u”的任务限制，也不通过脚本替代policy试推。所有本门θ_u都比45°机械止挡低至少5°，充分压柄后再尝试推动是一种合法、稳健但未必最高效的统一策略。creation奖励在θ_u后饱和，额外压到止挡不再增加creation收入；原有过力/运动惩罚保留。drive的1–3 N·m cap不是对机器人外部接触力的安全上限。

一次“推不动”不能唯一归因为未解锁。质量影响加速度，闭门器与静摩擦可保持低位移，接触几何/用力方向也可能无效；在有限时间和噪声下，单次力/位移反应不能唯一辨识这些原因。策略可以利用现有LSTM和动作—角度—交互反馈序列，重新压柄、调整接触、维持/改变推动；这是可利用的信息结构，不是保证已经学会的策略。[S09,S10,INFERENCE]

当前Teacher还知道质量和几何真值，不能声称其质量辨识完全来自反馈。部署Student未必有相同的角度/力/质量观测。不会新增解锁阈值、锁态、最大角、closer/friction真值或阈值归一化角度到actor/Student，也不让日志自动拼进RNN输入。

对N02的边界：θ_u随机化不等于阈值辨识实验；固定45°止挡可以被统一策略绕过。本次只建立物理交互条件，不宣称N02 novelty成立、Teacher恢复已成立或蒸馏可自动传递恢复。

## 5. B04限制方式、分布及与A的联合机制

| 方式 | 实际机制 | 本次结论 |
|---|---|---|
| 逐步裁剪/重写状态 | 每步改q，常伴随改qdot；绕开部分求解器运动/冲量过程 | 不选。reset初始化可以写状态，运行中不能用它限制开角 |
| 原生joint limit | USD或runtime API设置允许角度，由物理求解器处理约束 | **选用**。与当前150°的机制同类，且可与A共享同一门轴约束管理器 |
| 实体stopper | 门板碰撞一个有几何、材料、安装位置的实体 | 不选为baseline统一方案。若研究撞门挡局部反馈才有额外价值；会增加非本轮必需的碰撞域和维护 |

采用每扇门 `θ_max ~ Uniform(90°,150°)`，生成/分配door recipe时采样，固定到该门资产生命周期结束，不在每次episode或staged reset重抽。左右门、B01三质量档、有/无closer之间采用相同角度域并独立随机流，有限样本尽可能分层平衡。该均匀分布是工程覆盖选择，不代表真实建筑门的频率。

生成USD时 `RevoluteJoint.GetUpperLimitAttr().Set(theta_max_deg)`，单位是度。进入IsaacLab/PhysX张量setter后使用rad。当前代码已通过局部关节frame翻转令两侧开门joint坐标均为正；不要再乘一次左右符号。对未来不同轴定义必须显式映射，不用`abs(q)`掩盖符号错误。[S01,API01,API02]

**必须保留两个量：**

`normal_hinge_max_rad[i] = radians(sampled_theta_max_deg[i])`：door recipe的不可变物理上限。

`active_hinge_upper_rad[i] = epsilon_rad if engaged[i] else normal_hinge_max_rad[i]`：当前求解器上限。

A的解锁、复锁、natural/staged恢复都通过同一个limit管理器写active值；禁止把当时读到的窄上限或soft limit当成normal最大角。也不能在解锁时统一恢复150°而抹掉90°/120°等本门采样。

## 6. 物理步、reset和奖励的最小完整接线

详细伪代码、参数校验和按源文件改动见 DESIGN_SPEC.md。这里强调不可省的部分。

**物理步：** 在每个physics substep使用已刷新到最近一物理步的handle/hinge状态评估事件，变化环境合并一次setter，随后才`scene.write_data_to_sim → sim.step → scene.update`。本配置200 Hz、decimation4意味着事件判别不能只放进50 Hz reward函数。一次物理步延迟是采样机制边界；高速越阈值后又回落可能漏检，需本地记录而不是宣称连续时间精确。[S07,S08]

**成本：** 本机extension 0.54.4节选中setter会更新limit/default/soft缓存，并用CPU tensor调用`set_dof_limits`。default被裁剪不等于当前物理q被直接裁剪，但会影响恢复配置。只对事件环境批量调用；不逐环境调用，也不每步无条件重写。大并行下“单env事件稀疏”并不保证“全局调用稀疏”：任一env触发就可能导致整份limit缓存的CPU传输，实际吞吐仍未知。[LOCAL API,API03]

**拓扑：** 删除A资产中的cone、latch link、prismatic和mimic，不保留假第三DOF。将`build_latch`与self-collision解耦；保留门框/门板及机器人接触所需碰撞。`TaskObjCfgDict.init_state`、三列门DOF buffer、reset索引/effort目标、直接`[:,0/1]`消费者都需改成名称解析。网络角度观察仍输出规范顺序 `[hinge,handle]` 的两维。[S01,S02,S05]

**reset与staged：** 静态recipe不重抽；只改reset envs。所有root/DOF/恢复bank写入完成之后，恢复FSM、回位目标、奖励状态并施加与当前q兼容的active limit。旧三DOF bank或不匹配recipe/schema样本拒收，不删一列后假称兼容。不向已开门样本先施加窄限位再让solver“修正”。当前自然起点的门角随机化为false；保留的15–100°旧随机初始化分支若启用，必须在采样时受本门θ_max约束，而非事后夹住不兼容bank。[S05,S06]

**reward：** 同时处理0.6 rad和活跃creation helper里的45°。后者使用本门θ_u归一化并截断high-water增量，不给θ_u→45°额外creation奖励；硬止挡telemetry用45°，不混成解锁阈值。关闭release gate后的正开门速度与hold-and-drive收入，保留关闭方向惩罚和过门/安全目标。Stage4/5的回柄奖励在门又接近关闭时停用，避免阻止自然再压柄；不加新恢复网络或脚本。[S03–S05]

**释放：** 保留1.2 rad gate，仅作为奖励/阶段资格；不强制开夹爪、不证明实际断触。最小复用现有两指—handle定向接触sensor，连续3个control interval双指均低于既有1 N接触判据，才记录“测得双指断触”；不能把`~both_contact`当双指断触。该sensor只覆盖arm_body7/8，不能虚报整个机器人已与handle分离或零接触力。[S05:18530–18564,30045–30060]

给Stage4回默认臂姿态的条件和Stage4→5加入这个稳定断触条件；后者再要求既有release gate已发生，并保留root_x>0、hinge>1.0472 rad、handle<0.2 rad。实际断触、手指开命令、首次允许释放的时间/门角分别记；未发生值为null。

Stage3→4仍为hinge>0.25 rad且握持达标；90°在数值上高于这些阈值，**只证明阈值可达，不证明arm收回、身体净空、门板扫掠、闭门器回弹下的通行成功**。本轮不擅自重定义全部成功指标；现有root_x>1.5仍单列，不能替代全身几何通行证据。[S05]

## 7. 四个关键LOCAL-ONLY判别点

以下是后续Owner授权实施后的定向验证，不授权Worker现在自动实施、训练或扩成测试矩阵。

1. **A约束与单位。** 在本机API上检查两DOF名称、左右正方向、90°/150°写入读回；锁住时受载仅有设定游隙及有界solver误差，θ_u越过后恢复各自θ_max；q/qdot没有程序重写。当前窄区间可行性尚无运行证据。
2. **回柄与复锁。** 检查θ_u两端、保持压柄关门、近闭门失抓、开门后回柄、回到捕获区复锁以及再解锁；确认实际drive/effort目标、符号和cap，不把回位/约束冲量当脚本动作。无需训练A/B。
3. **恢复与隔离。** 对natural、Stage3/4/5合法新bank样本检查相同recipe、FSM、高水位、接触去抖和gate恢复；旧三DOF/不同M样本应明确拒收。局部reset不得改其他env的状态、上限或缓存语义。
4. **90°行为语义与开销。** 用现有本地工具观察90°边界的实际释放和通行/回弹；记录gate、双指断触、逼近最大角和过门的不同事件。同期测事件setter耗时、每physics步调用次数、CPU传输/同步及整体吞吐。不是要求新render、两套方案训练或全量参数网格。

可能改变A选择的关键未知只有三类：窄限位在所需负载/游隙下无法稳定约束；大并行事件setter成本不可接受；后续任务证据明确要求锁舌预载/局部卡滞的真实性而A缺失该机制。此时应重新决策，不把A的无效运行包装成PASS。B若接替，还须测自身脱扣/复锁而不是凭旧路径存在即宣布完成。

## 8. 范围锁定与最终判断

B01沿用Owner已批准的三质量档等权、closer有无各半及摩擦，不借B02把重门/closer/friction关闭。B03保持双D435i上仰15°，等待v29 baseline后再微调；不重开25°候选、相机研究或新增render前置。30 s、新自然起点、Stage0平滑速度保留，但新物理域的学习结果仍未知。

**推荐实施方向是A＋原生joint limit，不是两套都做。** 当前交付是独立决策及最小完整设计，Worker接手仍限于解析、与本地较新源码/API/已有runtime定向核对并记入plan/TODO/决策记录；代码实施、训练及新的运行验证依Owner后续授权。

## 9. 一手API/产品出处

所有网页于2026-09-18查阅。页面内容仅用于各自具体命题，不能代替本机运行；版本绑定以包内extension 0.54.4方法节选优先。各来源的简要用途也见 SOURCE_MAP.md。

- API01：[PhysX 5.8 PxArticulationLimit](https://nvidia-omniverse.github.io/PhysX/physx/5.8.0/_api_build/structPxArticulationLimit.html)：lower严格小于upper，角度限位单位rad；等值锁定不是本次已验证接口。
- API02：[OpenUSD RevoluteJoint](https://openusd.org/dev/api/class_usd_physics_revolute_joint.html)：USD angular lower/upper单位为degree。
- API03：[IsaacLab v2.3.0 articulation源码](https://isaac-sim.github.io/IsaacLab/v2.3.0/_modules/isaaclab/assets/articulation/articulation.html)：批量limit写入、缓存/default/soft副作用及运行时目标传播；不推断本机整个安装等于v2.3.0。
- API04：[PhysxMimicJointAPI](https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/latest/physxschema/class_physx_schema_physx_mimic_joint_a_p_i.html)：线性关系、单位与双向作用；运行时增删mimic等拓扑改变有额外代价，但本次A在资产生成时删除。
- API05：[OpenUSD DriveAPI](https://openusd.org/dev/api/class_usd_physics_drive_a_p_i.html)：angular target degree；raw stiffness/damping的每度单位；force cap是扭矩上限。
- PRODUCT01：[PDQ XGT官方产品页](https://www.pdqlocks.com/products/xgt-cylindrical-lock)：41°及特定选型65°操作转角；不用于推导θ_u分布或回位扭矩。
