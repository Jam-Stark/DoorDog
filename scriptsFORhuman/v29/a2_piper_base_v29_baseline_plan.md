# v29 baseline plan

更新：2026-09-19 01:25 HKT。D030–D031：完整baseline由worker team实现与训练监督；Owner离线期间planner自主验收/退回修正，明确批准后在GPU0开训。worker任务ID待Owner回传。

状态：**方案已确认，进入完整worker实施与planner验收阶段；当前等待worker任务绑定**。当前baseline恢复D021之前的门轴、hold_and_drive和grasp公式，不实施按需重抓/回弹恢复奖励。B04方案讨论已完成、最大角代码待实施；B01物理代码待实施，B05七族及Pro全部扩域配方已确认、二次几何核对完成，等待Owner交worker实施。B02后置独立ablation，B03保持15°并后置；N02承接重新抓把手扶门议题。具体正式命令/规模/预算由planner在完整实现验收后锁定并明确批准；当前还没有开训批准。

## 1. 已有基线

| 项目 | 决定与现状 |
|---|---|
| Stage5姿态 | goal `[2,0,.5]`；已实现goal heading与roll/pitch奖励，见D001 |
| 把手高度 | 双侧 `U(.90,1.20)m`，已实现，见D002 |
| 相机/arm reset | 接受MERGED H180/F45与`[0,.10,-.10,0,-.52,1.57]`，B06 PASS；base15°保留，B03后置到v29 baseline出来后微调，不作前置 |
| 自然起点 | 法向1.2–4.0m、横移±.5m，把手bearing±10°∩门法向±35°联合yaw，B07已实现 |
| 时限 | 整集30s；stage `[525,150,150,150,150,300]`，控制dt=.02s，剩余时间结转保留 |
| 当前速度 | Owner确认0.5/0.3m/s；D013已将Stage0改为门法向1.8–2.2m内平滑过渡，外侧0.5、内侧0.3；Stage4/5仍0.3 |

已有决定详见[决策记录](a2_piper_base_v29_decision_log.md)。9月17日one-batch只证明当时配置接线；后续起点/时间/速度改动仅有静态与CPU核对，未证明新域训练成功。

## 2. B01：门重、闭门器与门轴阻力

### 2.1 Owner已经确认的范围

| 因素 | 选择 |
|---|---|
| 门板质量 | `U(30,80)kg`、`U(80,120)kg`、`U(120,160)kg`三档，各1/3；不加入10–30kg |
| 闭门器 | 无/有各1/2；有闭门器组覆盖不同回关强度 |
| 门轴松紧 | 加入，并与hinge drive联合设计；摩擦和主动回关分别表达 |

“回关”表示机器人松手后，闭门器仍施加关门方向的力矩；实际回关速度还取决于阻尼、门轴摩擦、门的惯量和松手时门速，不等于所有样本都会快速猛关。无闭门器没有主动回关力矩，但仍有惯量和门轴阻力，开门时已有的运动不会瞬间消失。

按三档质量×闭门器有无形成六个组合，各占1/6，左右侧内保持同样的目标配比：

| 门重档 | 无闭门器 | 有闭门器 | 合计 |
|---|---:|---:|---:|
| 30–80kg | 1/6 | 1/6 | 1/3 |
| 80–120kg | 1/6 | 1/6 | 1/3 |
| 120–160kg | 1/6 | 1/6 | 1/3 |

各档均覆盖有/无闭门器、不同回关强度及松紧程度；120–160kg不固定搭配强闭门器。有限env数量不能整除时按目标权重分配尽量平衡的整数名额并打散，记录实际数量，不为凑整改变env总数。档内质量、闭门器强度和摩擦从下述有限范围采样。这是训练设计权重，不是现实门的市场概率。

### 2.2 联合动力学配方（本地工程设计，待实施）

第一版复用现有native angular drive与native joint friction，不新增另一套显式回关力矩叠加。门开度 `q≥0`、正门速为开启方向；所有设计参数先用SI，再由写入层转USD degree口径。

**质量和惯量**：先按1/3选择质量档，再在档内uniform采样；不能把整个30–160kg直接uniform替代等权三档。门宽/高/厚度仍使用当前几何域，同一几何/质量路径生成惯性，不另抽一套无关惯量。当前`MassAPI`只写质量，最终惯量由物理生成，实施后按实际读回记录。此次三档范围并不表示材质/内部结构已实现。

**120–160kg档的动力学适配**：保持门宽0.8–1.1m；仅用均匀薄门板、边缘竖直门轴的`I_hinge≈m*w²/3`作量级说明，三档约为6.40–32.27、17.07–48.40、25.60–64.53kg·m²。该估算忽略厚度/实际轴偏移及附属部件，不写回仿真、不代替实际惯量。在同几何的门板近似下，160kg比120kg惯量增大约1/3，同净力矩下角加速度降为约3/4；因此重门起动、制动和释放后的运动历程需要由实际动力学体现。

三档共用下述闭门器与门轴摩擦域：不为保持一样的加速度，把T、k、d或摩擦按质量比例自动放大；也不通过强制门速抵消重门惯量。这是本版联合覆盖的选择，不声称现实安装中门重与闭门器选型完全独立。新增重档的实际回关时长、通行成功率和现有stage时限余量仍待实施后的运行证据，不能由参考速度直接推出。

**有闭门器（三个质量档均适用）**：沿用现有 `2.5–12N·m` 的力矩上限覆盖，以有物理含义的两个变量构造drive：

- `T ~ U(2.5,12) N·m`：drive力矩上限，同时定义90°、静止时的回关请求力矩。
- `omega_ref ~ U(.15,.40) rad/s`：90°附近、忽略惯性和摩擦时的准静态参考回关速度，约8.6–22.9°/s。它是阻尼设计量，不是强制门速或实测回关时长；尤其不能要求120–160kg与较轻门以同样时间达到它。
- 保留position target `q0=-10°`、velocity target `0`；由 `k=T/(pi/2+pi/18)`、`d=T/omega_ref` 联合得到刚度和阻尼。
- drive请求为 `k*(q0-q)-d*qdot`，由原生drive以 `T` 限制幅值。USD写入 `stiffness=k*pi/180`、`damping=d*pi/180`、`maxForce=T`，drive type明确为force。

这样回关强度变化时，阻尼随设计速度一起变化；不再独立抽取原生`k=1–10`、`d=50`与cap，使大部分正向开门请求长期被同一cap截断。参考90°处的归一化只是最小弹簧/阻尼近似，未声称复刻液压闭门器完整曲线、末段锁门功能或故障门。实际开门时也允许正常出现drive饱和，不用clipping修改门状态来掩盖问题。

**无闭门器（三个质量档均适用）**：同一drive的 `stiffness=damping=maxForce=0`，不保留隐藏回关项；native joint friction仍按相同松紧分布采样。重门已有的角动量按物理演化，不因“无闭门器”标签直接置零。

**门轴松紧**：使用Pro已标为工程初值的温和范围：静摩擦 `S~U(0,1)N·m`；动/静比 `r~U(.5,1)`，动摩擦为`r*S`；native viscous系数 `b~U(0,.5)N·m·s/rad`。静/动摩擦阻碍运动，粘性项随速度耗散，不产生指定关门方向的主动负载。`b`表达门轴本身的阻力，`d`表达闭门器阻尼；不把同一阻力在两处重复计入。本轮不加入旧2/5N·m挑战档。

首版以每个已生成的门固定其完整参数组：质量、闭门器与摩擦在同一门的episode和staged恢复中保持一致，不在推进stage时换物理门。既有v27每reset抽三桶的接口不直接充当本方案。自然评估使用相同分布/配比；若后续需要固定场景评估，再显式指定同一组参数。

该配方仍可能出现弱闭门器被门轴静摩擦抵消而停在某角度的物理结果；有闭门器表示存在主动回关负载，不表示任何角度都必须完全闭合。不能用回写角度/速度的方式强制达到某条“回关曲线”。

### 2.3 已证明的操作路径与实施边界

| 路径 | 本轮确认的事实 / 后续落点 |
|---|---|
| `scenario_cfg/isaacsim.py::get_TaskObjCfgDict_for_door_config` | 当前v26 selector逐env创建DoorSpawnerCfg、固定左右手性；三档质量×闭门器的六个组合由此按等权生成，一起传入asset/metadata |
| `env_rand/door.py::DoorSpawnerCfg`及hinge构建 | 已能写固定mass、hinge stiffness/damping/maxForce；联合SI配方在此一次映射到USD，并保留来源参数 |
| `door_open_a2_base.py::_init_a2_v24_friction_runtime` | 当前native friction接入点；每门static/dynamic/viscous参数用现有Articulation API赋值，按实际env绑定 |
| `a2_v24_friction.py` | 已有三项native friction写入/读取能力；不能只把现有单一profile开关置true便宣称已实现本分布 |
| spawn metadata与staged reset | 参数随门绑定，不能使snapshot恢复到与原门不一致的mass/drive/friction |

本机IsaacLab与[官方USD DriveAPI](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/schemas/usdphysics.html)确认angular target为degree、angular k/d按degree、maxForce为力矩；runtime rad口径写入不得再次做同一转换。范围依据及现实数据限制仍见[Pro参数表](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/REAL_WORLD_PARAMETER_TABLES.csv)。

## 3. B01与N02的分工

本地建议把上述回关/摩擦变化纳入baseline共同环境域，不等待N02完成。baseline并非无记忆策略：当前actor/critic为2层256维LSTM，actor能看到连续的门角、机器人状态、动作与双指接触反馈；没有直接门角速度输入，但循环状态可以利用连续观测。具备学习条件不等于已经证明能学会。

当前Teacher还直接接收质量与门几何真值；不接收闭门器类别、k/d/cap或摩擦真值。这些Teacher输入不能等同部署Student的传感器能力，也不能把Teacher成绩写成从交互中辨认质量的证据。

N02负责研究可部署交互历史能否提高对未知回关/摩擦的辨别与适应。后续比较需让对照与N02面对同一环境分布及同等可用观察；否则把新增门域和新增方法同时改动，难以判断收益来源。当前不改N02网络、观察或分支，不启动方法实验。D023已将强回弹后的重新抓把手扶门行为及相应奖励讨论交给N02，候选见[专门记录](../novelty/documents/20260918_n02_regrasp_rebound_discussion.md)；不再作为baseline前置。已有shadow只有有限离线信息量，未证明在线适应收益。

## 4. Stage0按门距离平滑变速（已实施）

Owner提出以相对门2m为界，外侧快、内侧慢且平滑，并在本轮澄清明确为0.5/0.3m/s。D013在D011基础上完成实现。

以固定门框平面的法向距离 `d` 定义gate，与B07自然起点距离口径一致，不用到把手的三维距离。在`1.8–2.2m`的0.4m过渡带使用 `u=clamp((d-1.8)/.4,0,1)`、`s=3u²-2u³`，令 `v=.3+.2*s`。于是2.2m外0.5、2m处0.4、1.8m内0.3，端点斜率为0；保留进入站位带后目标方向归零和Stage0→1停稳条件。这里clamp仅定义有界插值，不裁机器人状态或掩盖仿真错误。

实现位于`_reward_walk_to_door`，用door root的yaw逆变换取得门法向距离；`target_speed`为设备上`(N,)`浮点张量，广播为`(N,1)`乘原有`(N,3)`目标方向。远速、近速和过渡距离分别由`a2_stage0_target_root_vel`、`a2_stage0_near_target_root_vel`、`a2_stage0_speed_transition_distance_range`给定。该段只改变Stage0速度奖励目标；Stage4/5仍0.3m/s，不改动作上限/Student输入。2m附近的变速由连续且端点一阶平滑的距离曲线表达；实际机器人加减速仍由策略和底层步态完成。

## 5. B02：移出当前baseline，后续独立分支做ablation

**Owner决定（D020）：当前先不做B02，等其他baseline项确定后，再单开apply B02分支做ablation。** 本项在本轮baseline清单标DEFERRED_TO_ABLATION；这只关闭本轮范围决定，不表示B02已实现或效果PASS。

当前baseline继续使用实体cone/latch、prismatic joint与mimic的物理解锁链，保留三DOF拓扑、handle 0–45°及现有handle动力学/target路径。B04只改变正常门轴最大角，不增加B02的R/E状态、epsilon锁定限位、两DOF迁移或u/H参数化。现有0.6rad unlatch尺度和creation 45°尺度也不因B04顺带改动。

此前发现的handle角度数值写入effort、作者层目标被runtime零目标覆盖的静态链，继续作为已记录的B02接入问题；不借本次B04计划将handle负载更换混入baseline。B01设置hinge的drive/target时须只操作hinge，保持上述handle路径，避免跨关节覆盖。

后续安排：其他baseline项确定后，从对应的共同baseline版本建立独立分支（建议名`codex/v29-apply-b02`），再落实B02方案与比较。当前不创建分支或启动ablation。对照与apply B02保持相同B01/B04等共同环境域及训练/评估设置；若B02同时改变锁闩机制、handle行程和回位负载，结果解释为这组约定改动的整体效果，不归因为单一锁闩机制。

两份Pro均选A及Main此前倾向Pro2的方案保留为该分支预研，不自动成为最终参数批准。原包、两套参数、API/reset/reward合同与必要未知统一见[双Pro归档](../pro_reviews/v29/20260918_192550__B02_B04_dual_pro_review/README.md)和[定向核对](../pro_reviews/v29/20260918_192550__B02_B04_dual_pro_review/LOCAL_RECONCILIATION.md)。B02与N01/N02是分别安排的工作，不借此新增GPU配额或训练预算。

## 6. B04：原生最大开角与原有奖励

B04按两份Pro反馈保留原生最大角随机化方案。Owner在D023决定baseline暂不做释放/恢复奖励重设计，并明确精确回退D021三处修改，现已完成；B04限位部分仍为**PLAN_DECISION_PASS / IMPLEMENTATION_PENDING**，B04讨论TODO已按Owner的D024确认勾选。B02软件锁态/拓扑迁移及N02重新扶门均不作为本项依赖。

### 6.1 最大角：生成时抽样、原生约束执行

| 项目 | 本版设计 |
|---|---|
| 正常门轴上限M | 每扇门一次采样M~U(90°,150°)，下限始终0° |
| 采样关联 | 左右侧、B01质量/closer组使用同一范围；M独立于这些分组，不把重门或强closer固定配某一最大角 |
| 实现方式 | 参数化当前`UsdPhysics.RevoluteJoint`上限，由solver产生约束反作用；无新增实体stopper，无运行中q/qdot裁写 |
| 单位 | 生成器/源USD用degree；runtime metadata/统计用rad，转换一次 |
| 生命周期 | M随已生成物理门固定，跨episode、stage、staged/recovery恢复均不重新抽取 |
| B02关系 | 保留现有实体latch+mimic/三DOF；hinge正常范围始终[0,M]，没有epsilon临时上限或R/E切换 |
| policy输入 | 不新增M、归一化q/M、限位反力等真值输入；已有观察合同保留 |

两份Pro均选择这一路线。当前150°本来就是原生joint limit，选择依据是现有source路径及其物理语义；90–150°是工程覆盖域，不能称现实门的uniform统计分布。位置接近M只能叫接近上限，没有约束冲量证据时不称“测到撞门挡”。

### 6.2 最小实施路径与reset

| 当前路径 | B04落点 |
|---|---|
| `env_rand/door.py::DoorSpawnerCfg/spawn_door` | 增加正常最大角参数/采样结果，将当前hinge upper=150°替换为本门M；现有metadata与deterministic_config链携带同一值 |
| `scenario_cfg/isaacsim.py`活跃逐env selector | 传递本版最大角范围/本门值，与B01门参数共同绑定；保留build_latch及三关节init |
| `door_open_a2_base.py`门metadata | 缓存每env固定M(rad)，用于记录和状态解释；不从soft upper或reward的90°饱和点反推M |
| natural/staged/recovery | 自然door q=0符合所有M；现有bank按env恢复同一门，直接沿用其固定限位。无需B02的临时放宽/重新锁定事务、布尔锁态或新bank迁移框架 |
| `base_v29_common.yaml`及natural eval继承路径 | 明确B04范围/奖励选择，训练与自然评估使用同一设计域；不通过评估时临时换限位伪装同配置 |

当前`randomize_door_init_state=false`继续保持，本版不增加预开门起点。限位在生成/初始化时生效，不需要每5ms或每control调用限位setter；已有public API能力是后续B02的候选工具，不因此成为B04运行时依赖。相同物理门的恢复不重抽M，也不把超限状态clamp成看似有效的恢复结果。

### 6.3 D023：精确恢复原有开门/握持奖励

Owner选择“恢复D021之前的原公式（精确回退）”，包括hinge、最终hold_and_drive与grasp三处；没有额外打开更早版本已关闭的门角位置项。已按函数源码逐段对照review输入版本，三处完全一致，见[回退记录](implementation_evidence/reward_revert_20260918/readout.json)。

令原收入mask `A = Stage3 OR (Stage4 AND NOT release_gate)`，当前原公式为：

| 活跃项 | D023恢复后的行为 |
|---|---|
| `push_door_hinge`，scale=6 | `clip(10*qdot + A*clip(q,0,1.5708)/1.5708, -1,1)`；gate只关闭门角位置项，门速正/负项仍计入 |
| `hold_and_drive`，scale=8 | 有效握持×正门速的原最终输出，不额外乘release收入mask；当前corridor=false，Stage5 continuity=false |
| `grasp`，scale=.2 | 原有接触力奖励及pregrasp处理；撤回Stage4 gate后去掉正值的新增逻辑 |

因此baseline继续提供持握推动收入，但**gate之后恢复的是门速/持握推动收益，不是门角位置持续加分**。位置项仍以90°饱和，并受旧gate控制；合成奖励也有原有[-1,1]限幅。原门速负项一并恢复，不保留D021仅取消回关惩罚的部分。较大开角/实际通行行为是否学出仍需训练证据。

D021曾实施的三处关闭及当时CPU结果保留为历史记录，已不代表当前行为。D022的按需辅助、净空风险、Stage4/5接近/握持/回臂/再压柄候选移入[N02待讨论文档](../novelty/documents/20260918_n02_regrasp_rebound_discussion.md)，首版仍限定重新抓把手；本baseline不实现该候选，也不反复重开此议题作为前置。

### 6.4 保留当前阶段条件与事件口径

| 条件 | baseline继续使用 |
|---|---|
| Stage3→4 | 实际门角>.25rad及现有握持条件 |
| release permission | Stage4门角≥1.2rad后锁存；不发张爪命令、不停止closer |
| Stage4→5 | 门角>1.0472rad、handle<.2rad、root_x>0 |
| 回臂条件 | 保留现有`release_gate & ~both_contact`，不在本项重新设计姿态门 |

Pro1要求新增release gate＋连续3control间隔两指均断触作为Stage4→5门槛，本版不采纳。上表记录当前baseline源码，回臂mask也保持；D022相关候选已交N02讨论，不把“尽早松手”另立为baseline目标。M≥90°大于角度门槛只说明没有静态门槛冲突，不证明实际净空或通行成功。

B04后续记录每门M及现有门角/门速、release gate和root crossing口径。两指断触、重新接触与按需扶门的专门事件/去抖设计由N02讨论时细化，不因本次限位随机化追加恢复行为或新的晋级门槛。

当前`~both_contact`可能仍有一指接触；arm_body7/8过滤只覆盖两指，不能把两指阈值以下扩称“全机器人脱离把手”。最大角、逻辑gate、实际松手、过门各有独立含义，不升级旧v28指标或Teacher/G7结论。

### 6.5 证据与本次边界

设计基于两份[Pro原文和本地source核对](../pro_reviews/v29/20260918_192550__B02_B04_dual_pro_review/LOCAL_RECONCILIATION.md)。现有原生约束、逐env门、metadata及per-env bank提供实施路径；当前仍是固定150°，最大角采样未实施；三处奖励已按D023精确恢复到D021之前。阶段条件、1.2rad释放门、奖励权重、观察/动作、物理参数与reset均未改。

实际M读回、90°附近的接触/通行/回弹、B01重门与closer组合下的释放行为、策略是否仍追逐挡止均未知。参数化上限及原奖励能否促成较大开角和成功通行仍待后续证据。D023的函数源码对照及AST解析通过；未运行旧D021 probe，也没有新仿真/训练或render。旧CPU结果只对应当时已撤回的公式，实际通行与策略效果仍需后续运行证据。

## 7. B05：全部采用Pro方案，完成PiPER几何二次确认（D029）

**当前决定**：Owner确认全部按Pro建议执行；planner已结合当前PiPER URDF/STL、TCP=.085m完成第二次静态确认。F0–F6全部保留，B04/B05继续标方案完成。详细构造以[B05执行规格](a2_piper_base_v29_b05_handle_design.md)为准；[B05技术附件](a2_piper_base_v29_b05_worker_handoff.md)属于[全版worker任务](a2_piper_base_v29_worker_start_prompt.md)；正式训练须通过planner验收并获GPU0开训批准。

### 7.1 确定的完整配方

| 项目 | 采用方案 |
|---|---|
| 族/回钩比例 | 七族各1/7，hook存在概率1/2；左右侧同域，不与颜色绑定 |
| 站距 | 主握中心到门板面h~U(55,85)mm；T40时完整A150–210mm |
| 圆杆尺寸 | F0/F3/F4/F5 dG19–30mm；F6 dG21–28、根/端±2mm，保留smoothstep |
| 非圆截面 | F1/F2 k~U(.85,1.10)；φ~U[−90°,90°)，只转截面，G保持门法向接近 |
| 平面尺度 | λ~U(max(.90,65/长度I0),1.10)，中心线/I同步缩放，截面与h分别采样 |
| 圆滑return | 90°弯头；C=min(60,h−r_tip−8)，R~U(20,min(30,C))，H~U(R,C)，b=H−R；保留主杆长度并显式记录弯头增加的总长 |
| 同轴饰盖 | 每操作门面一片Ø54×6mm薄圆柱，挂在门板同刚体，不加DOF/可抓body；总门质量口径保持 |
| X1 | F3轻弯×F1椭圆，h77.5/φ0/λ1/无return；作为未见组合配置，排除训练抽样 |

七个原标称锚点保留，当前旧图仅展示标称；上述工程uniform不是现实份额。现有轴颈圆柱及11–15mm半径域保持，长度A跟随h；双侧杆按同族参数镜像生成。门几何生成后固定，reset/staged重建使用保存参数。

### 7.2 默认G及接入关系

I排除轴颈、端帽、急过渡和return；先缩放I，再以56mm指体切向参照＋每端3mm得到J。默认G取J中点，本版不额外随机抓点。p=γ(s_g)，t朝轴颈、a门侧接近，R=[−t,t×a,a]，PiPER Y闭合/+Z接近；pregrasp局部−Z100mm。物体截面roll不令G追随薄轴。

生成器统一输出G与FixedJoint；consumer移除旧目标造成的重复固定旋转/LEFT补偿。闭门目标缓存、自然起点、observation/creation/reward引用同一G；保留其维度与现有训练语义。完整采样参数、截面/目标与deterministic重建同步，不让旧handleRadius概念替代非圆几何。

### 7.3 第二次确认的结果与范围

[当前PiPER核对证据](b05_gripper_confirmation_20260919/README.md)：入口净开口约70mm、TCP附近约74mm；F2全roll最大宽34.071033mm；主杆与掌基保守分离4.964483mm。默认G下两指与Ø54rose及return的投影分离至少3.499和13.463484mm，当前固定腕部件也在法向上分离。h55保留，理想门平面余量4.2mm；未前移TCP或修改手指。

联合采样补充避免h55＋最大端帽时独立抽R30导致H区间为空：该组合R上限约29.964484mm，其他组合仍可达30。直接从有效联合域采样，不削减Pro的总体范围或改变族/h配比。

因此全部建议作为**已批准、可交worker实现的规划**落地。证据限定原始几何、默认G及参考姿态全开直线接近；实际导入碰撞/接触、整机可达、动作误差与握持/训练效果由worker实现后报告。0.25mm离散建议仍为工程参考，不新增训练门槛。

visual/collision/质量/COM/惯量表示同一组合形状；保持单一door_handle和双指sensor语义。rose纳入原门板总质量，B02/B03/D023/N02既有安排不因B05改变。原Pro附件及D028核对保留为历史来源，以本D029规格取代其中待确认状态。

## 8. 当前未结与后续分支

本次baseline：B01已确认范围、物理代码待实施；B04方案已讨论完成、最大角代码待实施，奖励已恢复原公式。B05七族、全部Pro参数及目标设计已定稿，二次几何确认完成，待Owner交worker实施；已有B06/B07及Stage0速度决定沿用；B03保持15°并后置。强回弹后重抓把手已移到N02讨论。

B02已移出本版，其他baseline项确定后再开独立apply B02分支做ablation；不是当前baseline的阻塞项。该分支的具体配方、预算与评估安排届时确定，不从旧Pro静态PASS或既有6000-batch默认值推导授权。D023仅撤回D021三处A2 reward修改；没有配置/资产改动、分支创建或活动训练/仿真。

## 9. 完整worker任务、planner验收与GPU0开训（D030–D031）

Owner将完整v29 baseline实现和训练监督委托给一个worker team，并授权其与planner在Owner离线期间自主双向沟通。统一入口为[可复制worker启动prompt](a2_piper_base_v29_worker_start_prompt.md)，逐项证据要求和权责见[验收/协调合同](a2_piper_base_v29_acceptance_and_coordination.md)。B05文件只是技术附件，不能缩减总任务范围。

worker完成全部实现后向planner任务`01a0af49-b5e0-75f2-8fdd-ad5c3e20744b`报告具体候选；planner逐项严格核实，特别查看B05真实生成/导入的door asset、随机组合、G/frame与接触。问题由planner通过turn/steer或queue直接退回worker修正；必要项全部通过并锁定执行配方后，planner发送TRAIN_APPROVED，worker才可用物理GPU0正式开训并负责监督。方案TODO完成、worker自评及消息入队都不是该批准。

当前本机没有codex turn/steer CLI子命令，它们属于App Server协议；可用的CLI备用通道为`codex queue --thread UUID --message TEXT`。Owner已验证同机queue可行，双方按可用接口直接沟通，不要求Owner在线转述。worker thread ID由Owner创建后回传，当前不伪造绑定或启动任务。

原seed291/4096env/6000batches仅作为首轮提交默认；planner依据当前实现和目标规模证据批准最终命令/预算/ETA。首轮GPU0批准不自动覆盖第二seed、GPU1、pull或N01/N02/B02消融。运行超过30分钟使用独立tmux和持久化监督/逻辑等待，失败/完成主动报告，避免模型周期轮询。

决策必须区分来源：Owner授权与planner裁定记录在主decision_log，worker自行决定记录在[worker决策日志](a2_piper_base_v29_worker_decision_log.md)。每条含角色/任务ID、依据、影响、候选/运行及状态，提案、接收和批准分开。B04/B05保持方案完成，实际实现/验收/训练状态另列。
