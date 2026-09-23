# DoorDog v29：B02 / B04独立决策与审阅

**B02选择A：软件判定的虚拟锁闩，使用原生hinge非零游隙限位产生锁止反力。**  
**B04选择原生joint limit：随机机械上限由物理solver处理，不每步重写门角，不新增实体门挡作为baseline前置。**

日期：2026-09-18。输入专用分支：`codex/v29-b02-b04-pro-20260918`；提交主题`Prepare v29 B02 and B04 Pro decision handoff`，时间`2026-09-18T17:14:54+08:00`；release为`20260918_170419__b02_b04_decision`。

这是一份明确的设计选择，不是实现/训练PASS，也不是Owner实施授权。统一规格见`DESIGN_SPEC.md`，参数机器可读版本见`DESIGN_PARAMETERS.json`。来源编号[S01]等在`SOURCES_AND_CODE_MAP.md`给出原厂/API链接、版本和源码定位。

## 0. 证据范围及独立性

已获得两个独立普通ZIP，分别438863 bytes/35文件、63988 bytes/10文件；逐项核对manifest路径和字节数并解压。按Owner顺序先读请求、brief、索引及当前source/config，记录初选A与原生最大角限位后，才比较本地候选、baseline plan和旧Pro的B02/B04段落。该初选在后续核查后保持；参数配方则由本报告独立确定。

源码采用定向函数阅读，不宣称逐行审计大文件内所有历史路径。当前resolved YAML是CPU解析材料；本报告也独立解析了其中有效reward scales、观察与200Hz/50Hz时间口径。GitHub内容API对1.49MB环境文件的一次读取返回空正文，完整源码已从ZIP读取，因此没有以空返回冒充源码证据。[S01–S06]

证据标记：**[源码事实]**为包内实际代码/配置；**[一手资料]**为原厂或官方API；**[工程设计]**为本报告提出的实现规则/初值；**[推断]**为从这些输入得到的可检验解释；**[未知/local-only]**需本机才能证实。未读取未入包的checkpoint、GPU状态、硬件或新运行。没有重跑仿真；旧9月17日one-batch不证明新B01/B02/B04可学。

范围不扩张：B03保留15°并后置；B01三档质量各1/3、有/无closer各半与门轴松紧沿用Owner范围，物理代码尚未落地；不重开v28，不制定N01/N02实验或训练预算，不要求完美Teacher、两套机制并行实施或新增网络。

## 1. 当前事实：不是“现有Boolean换个阈值”

| 当前量/路径 | 已核到的事实 | 不能据此声称 |
|---|---|---|
| handle→latch | 真实Revolute handle经mimic驱动Prismatic latch；高位cone与框碰撞产生阻挡 | 当前已是软件解锁开关 |
| handle | 0–45°；USD author target−15°、raw k50/d0.5、cap1–3N·m | 45°就是精确物理解锁角；raw k/d为每rad |
| latch | 0–30mm；gear−0.03/45 m/degree；cone半径25mm、高50mm，放在door_height−0.1m | 当前扣板脱离角/余量、复锁可靠性已测定 |
| hinge | USD Revolute原生0–150°，左右侧通过joint frame使正q表示开启 | 150°由每步q clamp实现 |
| reward | scalar0.6rad；活跃creation还有45°截断、high-water与归一化 | 改一项YAML就完成角度随机化 |
| 阶段 | Stage3→4：q>0.25rad且握持；release gate：Stage4 q≥1.2rad；Stage4→5：q>1.0472rad、h<0.2rad、root_x>0 | 达解锁阈值就该跳Stage4；过release gate就已经松手 |
| 观察 | Teacher两层256维LSTM；actor有hinge/handle角、接触反馈、质量及几何真值 | Student部署也有这些真值；actor已观察到closer/friction/解锁阈值 |
| 当前运行域 | resolved仍80–120kg、native摩擦off；30s、新自然起点和平滑速度仅CPU/static证据 | 新域已经跑过one-batch或RL |

来源：[S01–S05]及本次resolved YAML。完整域/接线核对结果见`STATIC_REVIEW_CHECKS.json`。

### 1.1 两个直接影响本轮的源码发现

**第一，release gate后的“继续开大门”收入没有完全关闭。** `_reward_push_door_hinge`仅把位置项乘hold-income mask，`10*qdot`仍在；实际`hold_and_drive`在components函数后半被另一条路径覆盖，采用的hold mask不等同release gate。当前有效scale分别6与8。另一个较小但直接的残余是`_reward_grasp`：其A2分支返回双指轴向/离轴受力组合，Stage4 gate后仍可有正值，当前scale0.2。相反，keep-close/open-command惩罚及多项双指收入已经有release mask，不能说所有抓握项都没关。[S02–S04]

**第二，reset里的“15°”数字实际送进effort接口。** `_reset_door_states`构造三列target，将handle列设为`15*pi/180`；下游`apply_torques_at_task_dof`调用的是`set_joint_effort_target`。因此该调用表达的是约+0.261799 N·m命令，而不是把手角度目标。它和USD author target−15°也不是同一个东西。实际运行时native target有没有被implicit actuator缓存覆盖，本轮没有读回，故不对净回位力矩作运行断言。所选设计必须统一位置目标、预载、gain、cap和effort零点，不能照抄这条容易误解的路径。[S03,S05,S11]

## 2. B02并排比较：A与有限改动B

这里的B仅保留当前代理结构并作有限修正，不把精细锁体CAD设为B的成本。A也不等于直接移动门状态。

| 维度 | A：虚拟锁闩＋原生物理限位 | B：保留cone/滑块/mimic |
|---|---|---|
| 解锁可控性 | 给定本门阈值可明确规定解除约束时刻；误差主要是物理步采样、solver容差 | 由传动、搭接、接触容差和负载共同决定；目标角不是实际脱扣角 |
| 反馈与真实性 | 机器人—把手接触、handle回位、门惯量/closer/friction及锁住时反力保留；缺失锁舌侧压摩擦、扣板斜面和机构反驱耦合 | 有真实代理接触及mimic反驱；但高位cone的力路、楔角和锁体位置不等同现实锁体 |
| 实现/维护 | 需做一次2DOF迁移、状态机、限位切换和bank schema；之后角度语义集中 | 复用三DOF主干较省迁移；需参数化传动/stroke/搭接并验证几何脱离与关门过程 |
| 并行环境 | 删除一个刚体/滑动DOF/mimic及其接触，可能减solver负担；setter有CPU copy/同步，净加速未知 | 保留既有solver接触成本，无新增逐事件limit setter；当前拓扑运行历史不能替代新几何成本测量 |
| 角度随机化 | 可在采样时保证阈值小于止挡；仍不能保证机器人可达/可学 | 须用例如x(h)=s*h/H、搭接e共同构造；x越过e才可能退出，必须留容差，不能只改H |
| 左右/push-pull | 采用关节局部正向；不拿world yaw符号当q符号；pull仍需其工作区正确door frame/侧别映射 | 同样依赖frame；cone朝向和接触边必须镜像，不能只镜像角度数值 |
| 自然/staged恢复 | 两个隐状态及本门参数必须恢复；旧三DOF bank不能继续用 | 三DOF state较接近既有路径，但新参数/几何也不能和旧bank混配 |
| N02信息内容 | 保留开门后对closer/friction等交互适应；不支持据此宣称学会现实锁舌受侧压卡滞辨识 | 可以研究代理锁舌侧压与反驱，但未经校准不能当真实锁体方法证据 |

### 2.1 最终选A的决定性理由

**本轮最值得控制的是“物理门相同、但需要下压多少才可开启”，不是精确锁舌内部受力。** A可使阈值、总行程和回位负载成为含义清晰的独立/条件变量，同时保留实际接触、锁止反力及开门动力学。B虽然可有限参数化，却仍须把未测的几何脱扣关系作为训练域的一部分，失败更难区分是策略问题还是代理几何不可开。[工程判断]

A的成本是明确且一次性的2DOF/reset迁移，及必须验证的原生窄限位。选择不是因为“软件必然快”“软件绝对真实”或Owner以前偏好A。本机setter源码和PhysX约束定义让该方案有具体可调用路径；它们尚不足以证明运行稳定性。[S06–S09]

**可能改变选择的关键未知也明确：**若本机普通articulation窄限位在合理solver设置下持续泄漏、切换产生不可接受冲量/复锁异常，或者事件式setter同步负担不能接受，则需重新决定机制，不得用q重写假装A通过。另一种改变选择的理由是Owner把“带侧压的实际锁舌卡滞/扣板接触辨识”升为baseline核心；届时B的接触内容更相关。当前没有证据需要预先实现两套作比较。

## 3. B02选定参数：先采机械行程，再采解锁比例

所有下列范围是**工程覆盖域/初值，不是实测频率或标准限值**。统一参数字段与公式在DESIGN_SPEC及JSON中。

| 量 | 本报告选择 | 理由/关联 |
|---|---|---|
| handle机械上限H | U(40°,60°) | 对45°作有限扩域；不以尚未验证的65°尾端作为当前必须覆盖 |
| 解锁比例ρ | U(0.65,0.85)，与H独立采样 | 阈值与总行程相关但余程不固定，不给每门同一个“到底前5°”结构 |
| 解锁角u | u=ρH，支持26–51° | 每个样本都严格小于H，不会产生60°阈值/45°止挡 |
| 机械余程H−u | 派生6–21°，不是另抽uniform | 有有限正余量；达到解锁后继续到底不应再赚creation进度 |
| handle缩回迟滞 | 2° | 上行达到u视为缩回；回位到u−2°才重置该内部状态 |
| 锁住的hinge限位 | [0°,0.25°] | 非零游隙、lower<upper；约对应0.8–1.1m宽门边3.5–4.8mm弧长，非实际扣板间隙测量 |
| 复锁捕获区 | −0.05°≤q≤0.20° | 保留0.05°上边界余量；负端只容忍原有lower约束微小数值误差，不制造额外负向行程 |
| 回位load | 见下述native预载弹簧 | 不沿用含义不清的raw gain/effort数字 |

### 3.1 为什么不是0–45°不变或U20–60°＋5°

固定45°、解锁20–40°是可用的窄域方案，不是错误；但所有门总行程相同，容易让策略把固定深度变成机械先验。U20–60°与stop=u+5°也在算术上可行，前提是stop同步到25–65°；它并非“60°超过45°因此永远不合理”。我不选它，是因为本轮没有65°抓握/腕部可达性证据，而且固定5°余程并无原厂依据。

PDQ GT原厂资料区分41°和65°操作角，说明操作行程不是全球统一45°；它没有给出这些值分别对应机械挡止还是负载下精确脱扣的曲线。因此不能直接复制为u或H。选40–60°/比例采样是有限工程折中，不宣称覆盖所有现实锁体，尤其不覆盖全部65°机构。[S10]

### 3.2 回位负载的单一、可计算定义

保留真实handle Revolute、质量/惯量和接触；native force drive采用：

\[
\tau_h=\operatorname{clip}[-\tau_0-k_h h-b_h\dot h,\ -3,3]\quad\text{N·m},
\]

其中τ₀=0.35 N·m，T_H~U(1,3) N·m，k_h=(T_H−τ₀)/H_rad，b_h=0.05 N·m·s/rad。T_H表示忽略重力、接触和速度时，在机械上限处的**模型回位力矩**，不是旧随机cap的别名。最大drive力矩固定3 N·m；末端高速时会饱和，需记录，不把cap当实测。

用native位置drive实现上述弹簧：`h_target=-τ₀/k_h`，速度target=0，额外effort target=0；target在物理下限外只为产生预载，不改变handle的[0,H]机械范围。按本门H联合计算k，而非H变了还声称力矩-行程关系没变。b和τ₀首版固定，不无根据再扩大随机维数。[工程设计]

0.35 N·m是工程预载。按当前两个0.1kg杆、两个可选0.05kg端部回钩、最大0.14m杆长粗算，水平时这些部件对把手轴的重力矩约0.275 N·m，加小目标体后仍约0.28 N·m；这只是当前构造下的量级推算，不替代实际惯量/重力读回，也不延伸至未批准B05形状。选定预载旨在让水平回位留余量。[S01，推断]

SI→USD angular k/d乘π/180，target rad→degree；runtime IsaacLab目标用rad。USD drive明确force类型，不采用acceleration drive。仅在USD写target不够：初始化及自然/staged恢复后须把同一个target写入本机implicit actuator缓存并读回；删除reset里+0.261799 N·m旧effort注入。没有本轮runtime证据确认旧target在实际运行中如何覆盖，故这里是新设计的完整性要求，不是已经归因的训练缺陷。[S05,S08,S11]

## 4. 状态、事件与真正的物理约束

定义q为正向开门角，h为正向下压角；本门机械最大角M始终独立保存。

内部仅需两个有记忆的状态：`lever_retracted`（R）和`latch_engaged`（E）。R用u及2°迟滞更新；它不是可部署传感器，也不是actor输入。E决定原生hinge的有效上限。

| 场景 | 状态/限位动作 | 实际运动与含义 |
|---|---|---|
| 自然起点q=h=0 | R=false,E=true，upper=0.25° | 允许小游隙；继续推的反力由solver与接触链产生 |
| 下压到h≥u | R=true,E=false，upper恢复本门M | 不写q、不清qdot、不施加开门推进；门是否起动由外力/惯量/closer/friction决定 |
| 还未离开捕获区就抬回 | h≤u−2°且q在捕获区→E=true | 允许重新挂住，避免“曾解锁一次就整回合永久畅通” |
| 门已打开、handle回位 | R=false,E仍false，upper仍M | “可复锁”不等于已经锁住；不能在半开门处收紧限位 |
| 回关进入捕获区且R=false | E=true，upper=0.25° | 保留q/qdot，新增上边界没有排除当前正q；后续反力由solver处理 |
| 回关时仍压住把手 | R=true,E=false | 不复锁；其后在闭合附近抬手才挂闩 |

规则在所有stage都生效，不用K5、grasp真假或policy动作当物理解锁条件。K5只用于既有训练阶段/reward。任何对象确实把h转到u，都应改变环境机构；这不等于给policy一个开关。

复锁仅收紧upper，lower保持0。若q已经高于0.20°，不在半空拉回；若q远低于0或在锁住时明显超越0.25°，记录constraint fault并拒绝将该状态写入合格bank，而不是回写q掩盖问题。没有额外“低速才能复锁”规则，以免高速回关在lower端停住后永远漏锁；高速反弹、容差和捕获漏检仍是local-only验证点。

该虚拟锁闩是理想化双状态机构：没有真实斜舌撞扣板时的连续压缩/弹出过程，没有把手受门扇侧压而变沉的额外耦合，也没有实际损坏/断裂模型。不能将它宣传为真实锁体数字孪生。[工程模型边界]

### 4.1 API与步时序

本机可见接口为：

```python
door.write_joint_position_limit_to_sim(
    limits,                 # shape [changed_env_count, 1, 2], rad
    joint_ids=[hinge_id],
    env_ids=changed_env_ids, # unique device-local integer tensor
)
```

只在E变化、初始化、reset恢复时调用，按发生变化的env合批，不对每扇门逐个调用。使用本机public setter，避免绕过其limit/default/soft缓存。它仍会对完整limits缓存做CPU转换；“只更新变化env”不等于只传变化env字节，净成本未知。[S06,S09]

Physics步为5ms，control步20ms。已存在PRE→simulate→scene.update→POST循环。建议在每个POST、任何temporal-evidence early return之前读取新q/h、计算新状态、提交必要的limits并记录事件；新约束在下一物理步生效。启动和reset须在首个有效物理步前提交正确限位。事件至生效的离散延迟不超过一个物理步，不夸称连续时间瞬时解锁。不要放进obs getter或只每20ms判断一次。[S03,S05]

普通articulation限位lower必须严格小于upper；[0,0]不是该setter已证明可用的锁法。PhysX文档提到的eLOCKED是另一条motion接口，本轮不把未验证绑定当后门替代方案。[S07]

## 5. 能否允许“压到底，再试推”

**允许作为baseline中可学习的统一稳健策略，但不把它硬编码为外环脚本，也不把到底/停滞等同解锁成功。** 本门H处必有h≥u，因此在理想模型且确实转到了handle自身止挡时，压到底足以解除锁约束。这是环境可检验性质；policy没有H/u真值，必须从动作、实际关节/接触响应与后续门运动获得反馈。

机器人关节受限、腕姿不对、夹爪夹错或滑移也能“压不动”，并不意味着h到了H。解锁后，重门初始加速度很小，静摩擦有起动门槛，closer有持续回位力矩；短时间q不变不能唯一识别仍上锁。能够持续开出超过游隙的角度，是更强的开启证据；但A2自身位移/夹爪滑动不是门角证据。

在已有动作空间和安全代价下，允许策略保持合适下压、施加有限方向性推/拉，观察响应；无响应时可以调整接触/下压/施力，不要求先训练专用force estimator或脚本试推器。有限感知窗口和有限力下，有些状态就是不可辨识，不能承诺LSTM总能区分锁住与高阻力。

Teacher当前接收门质量真值，不能声称它必须通过交互辨识质量；其sim hand_force和门角也不自动成为Student可部署输入。新u/H/M/R/E以及归一化u进度一概不加入actor/Student，本轮也不新增critic输入。N02仍可围绕未显式给出的closer/friction响应研究，但本轮不开展该实验，更不据A宣称真实锁舌侧压适应已解决。[S02,S03]

## 6. B02最小联动：拓扑、reward与恢复

### 6.1 拓扑与自碰撞

选择A后，在v29实际入口删除cone/collider、latch_link、latch_joint、mimic、0.1kg代理质量及第三DOF initial/reset字段。按名称解析hinge/handle，断言两DOF；`door_dof_state_buf`和torque目标改为两列。不是隐藏锁舌、留一个仍在挡门的collider，也不是保留无用dummy joint骗过旧bank。[S01–S03]

`build_latch`当前同时用于早期self-collision authoring，而场景`articulation_props.enabled_self_collisions=True`还可能后写覆盖。必须解除这两个概念的耦合；v29明确保持现有应有的门板/门框/把手接触与过滤关系，仅移除锁舌相关几何。不能以`build_latch=False`顺手关闭全部自碰撞，也不能仅看早期author属性推断最终有效值。[S01,S02]

### 6.2 reward与telemetry

下压进度统一为p=clip(h/u,0,1)。活跃creation与初始化采用本门u截断的角度high-water，或等价p high-water；公式为K5/Stage3有效窗口中的Δp_max/control_dt。保留当前活动窗口与high-water更新时序，达到u后继续压到H没有新增creation。迟滞/复锁不清空回合high-water，避免开关锁刷进度。[S03,S04，工程设计]

0.6rad `unlatch_hold`归一化同样换为本门u；near-closed 0.1rad是奖励窗口，不改称物理捕获角。45°hard-limit getter/初始化/日志消费者改为本门H，near-stop容差沿用0.005rad。`dont_push_door_handle`的位置项改为clip(1−h/H,0,1)，保留原速度项。只改这些实际消费者，不无差别替换所有0.785398常量（机器人腕角等无关值不动）。Stage3→4仍以真实q>0.25rad＋握持，不因E=false直接跳阶段。

事件必须分开：`unlock_constraint_released`、`relatch_constraint_engaged`、`release_permission_enter`、`gripper_open_intent`、`two_finger_contact_lost`、`all_finger_contact_lost`、`contact_reacquired`、`first_root_crossing`。位置接近limit只能叫`near_stop`，没有constraint reaction证据不能假报stop接触力；有单指接触时不能说全部断触。

旧`hinge_at_release`按原定义保留为legacy字段或明确迁移为`hinge_at_release_permission`。新增物理断触字段另起名，不能静默改变旧语义。接触事件用既有handle接触阈值，初始取连续2个control样本确认；保留首次样本时间和确认时间，缺事件为null。open-intent与断触并列，不据二者自动宣布N01中的“计划释放/意外失抓”分类已验证。

### 6.3 自然与staged恢复

每门固定完整参数组H/u/T_H/M及B01参数，不每episode重新抽样。自然起点q=h=0、R=false/E=true。当前randomize_door_init_state=False保持；旧0.261799–1.74533rad随机初开路径不能直接用于M可能只有90°的新门。[S02,S03]

bank必须包含机制/参数schema、同门身份、R/E、u进度high-water、release gate及必要历史buffer。自然与staged共用outer reset的最终“参数—状态—目标—限位”一致性步骤，因为staged恢复会直接写door joint state而绕过自然`_reset_door_states`。

reset选中env先临时恢复其正常[0,M]以接纳合法snapshot，再恢复q/h/速度和登记buffer，最后根据恢复的E提交[0,ε]或[0,M]并重设native handle targets；中间不推进物理。两种限位之间的reset操作不是训练步中clamp。旧三DOF bank失效并重建；参数变更也失效，不把旧snapshot角度强裁成新域。没有合格同门snapshot时按既有自然起点处理并标明来源，不偷偷把staged样本换成另一扇门。

## 7. B04明确选择及设计

| 限制方式 | 物理含义及代价 | 本轮决定 |
|---|---|---|
| 每步q裁剪/重写、清速度 | 在求解后改状态，反力和能量变化不由同一接触求解解释；可能隐藏穿透/注入或删除动量 | 拒绝作为锁闩或正常最大角实现。合法reset写状态是另一回事 |
| 原生joint limit | 改约束参数，由solver处理反力；可与A共用hinge的一组有效bounds，不需门挡几何 | **选择**。当前150°就属此类，扩成每门M |
| 实体stopper碰撞 | 表达接触位置/材料/局部顺应性，也可能改变通行/机器人碰撞；需几何摆位、碰撞归属和镜像 | 本轮不选，不作为前置；若以后研究真实门挡碰撞再单独建模 |

### 7.1 最大角与采样

M~U(90°,150°)，每扇门生成时一次采样，在自然episode、staged恢复和该门全部交互中固定。分布是工程覆盖权重，不是门型市场统计。与B01质量档、closer有无、friction以及B02的H/u独立采样，除左右镜像语义外不把困难参数绑定在某一侧。B01已批准的等权分层保持，不为方便改变成全区间均匀。

创建正常机械限位时`RevoluteJoint.GetUpperLimitAttr().Set(M_deg)`；运行时用rad。A锁止会临时把effective upper改为ε；M存于独立immutable参数buffer/customData，绝不从锁住后的`joint_pos_limits`、soft limits或effective upper反推。解锁恢复本门M，而非统一恢复150°。[S01,S06–S09]

当前左右joint frame已令q>0表示开启，两侧均[0,M]，不是RIGHT写负上限。若pull工作区采用不同坐标定义，须先确认其canonical q与raw q映射；不能把本包push/out的观察直接当作pull路径已核验。

### 7.2 到挡止后的行为

不清速度、不停掉closer/friction、不把碰到最大角自动定义成解锁/松手/成功。无closer门仍有惯量、摩擦和限位；有closer门可在解除机器人支撑后回关，弱closer也可能被静摩擦留在某角度。重门同样允许利用适量惯性或持续hold，但不能因“重”就规定必须撞stop。native limit是理想集中约束，不提供实际门挡材料的碰撞力时程。[工程设计边界]

Stage3→4的0.25rad、release gate的1.2rad、Stage4→5的1.0472rad和h<0.2rad、root_x>0均保留。90°虽大于这些角度门，不能证明机器人宽度、姿态、抓握轨迹和回弹时序下有通行成功。M是物理边界，不是训练目标角，更不是每扇门必须达到的成功条件。

### 7.3 只做必要的release联动，不扩写全部reward

**最大角随机化本身不能让策略停止“开到各自挡止再松手”。** 本轮建议修正已定位的三处直接收入：

1. 将`_reward_push_door_hinge`的整个hinge项（包括速度项）乘既有`_get_a2_stage34_hold_income_mask()`，而不只mask位置项。
2. 实际覆盖后的`hold_and_drive`也乘同一mask。保留既有stage5 hold-income continuity=false。
3. `_reward_grasp`仅在Stage4且gate=true时截去正收益，保留其负值；其他stage不变。否则两条驱门收入关闭后仍可能保留静态挤压力收入。

这样Stage4 release gate进入后，不再从前两条路径为继续开大/抓住驱门领取收入，也移除第三条正挤压力收入；hinge项的关门速度负收益不继续迫使策略为阻止正常回关而长期持门。gate前scale6/8等不扩张；已有close/open-command和双指mask不重复改写。over-force、碰撞、全身稳定、安全项不能随gate关闭。root目标、handle回位与现有轻量手臂恢复项保持。

这不是命令立即张爪：强closer/不良净空下，策略仍可为了后续通行保持接触；没有奖励到M、M−固定差值、`q/M=1`或碰到stop的项。现有gate是回合内OR锁存，不因回弹反复开关来刷收入；代价是gate后重新开门不再获得这两项dense进度奖励，恢复依赖后续任务收益。这是本轮有界取舍，不宣称已经训练验证，也不借此悄悄设计完整N01恢复课程。[S02,S03]

## 8. 少量必要local-only证明与可能改变选择的条件

| 定向问题 | 必须看到的证据 | 不能以什么替代 |
|---|---|---|
| 原生窄带是否真实锁住、切换不改q | 已授权后，在实际backend带接触/载荷下读回limit、q/qdot、约束误差与切换前后状态；重门/closer预载下不持续穿出；到u扩大后运动由力产生 | API存在、CPU状态机通过、把q写回0 |
| 复锁与异步env reset | 开门回位不收紧；回关才捕获；压住回关不捕获；一个env锁/解锁/复位不污染其他env；高速捕获/小容差是否可用 | 把开门snapshot直接塞入窄带、关门时清速度 |
| 2DOF、native targets与bank一致性 | joint名字/数量、self-collision最终值、参数身份、default与实际target/effort/gain读回；旧三DOF bank明确拒绝 | dummy latch、只改USD target或只改自然reset |
| 原生M、行为收入与事件成本 | 90°/150°边界可达限位附近且无state clamp；gate后两条驱门收入为0、grasp无正收入；区分断触与gate；记录setter调用数及耗时/同步占比 | 以门槛低于90°当通行成功；声称A必然更快 |

这些是选择所必需的少量判别点，不要求A/B两套训练、庞大矩阵或新增相机render。当前Owner仅授权解析与定向核对；实际运行/实现仍按后续指示。静态参数/逻辑检查随包附上，但它们不提供上述物理证明。

若只能通过加大游隙到明显改变任务、每步裁角、清零速度或忽略复锁来“稳定A”，则A未通过，必须回Owner重议；不把建议选择偷换成无条件验收。

## 9. 与本地方案和旧Pro的异同

本报告与本地一致选择A、同意删除旧代理及第三DOF、保留真实handle和以实际门角过stage；也同意B04应区分原生约束与改状态。但选择的依据是当前目标与可调用API，不是延续软件偏好。

不同点：不采用U20–60°＋固定5°余程；选择H40–60°与ρ0.65–0.85联合采样；指定非零锁游隙及复锁捕获，而非[0,0]；显式统一return drive和reset effort；B04给出固定每门U90–150°和唯一limits writer，定向关掉gate后两条继续开大收入及一处正挤压力残余。

旧Pro关于“操作角、机械挡止、物理解锁、实际断触需区分”的原则保留；它围绕实体机构的行程/搭接分析不再成为A的前置。旧25°相机候选不进入本轮，旧v28验收结论不回写。当前source的30s/自然起点/Stage0改动也不被本报告冒称已运行。

**最终决策不悬置：B02=A，B04=原生joint limit。待核的是所选设计的运行成立条件，不是要求Owner在本报告两套方案之间再替Pro作选择。**
