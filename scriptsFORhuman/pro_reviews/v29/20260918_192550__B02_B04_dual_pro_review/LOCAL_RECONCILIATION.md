# B02/B04 双Pro决策与本地定向核对

更新：2026-09-18 19:45 HKT。维护：Codex Main；两路只读核对分别覆盖锁态/API/reset和drive/reward。范围：Owner本次附件解析指令。**所有“建议采用”均为本地计划建议，未获Owner最终确认，未实施。**

原文、来源仓库/分支/时间与附件映射见[README](README.md)。本文不改写原文；D015的软件偏好和20–60°/+5°候选不作为选择依据。B03保持15°并后置；B01三档等权、closer有无各半不变。

## 1. 两份独立选择及理由

两份均选择 **B02 A（软件虚拟锁闩）＋B04 native hinge joint limit**，拒绝在正常物理步中重写q/qdot来强制锁门或裁最大角。B04原生约束由软件设置参数、由物理求解器产生约束反作用；它不同于后写状态裁剪，也不同于新增实体门挡。

| 比较 | 优点 | 代价/不能表达的部分 | 本地意见 |
|---|---|---|---|
| B02 A：虚拟锁态切换有限游隙/正常限位 | 解锁阈值、把手止挡、回位负载可分别定义；门的惯量、接触、closer和friction仍由物理演化；免去现有高位cone的搭接耦合 | 必须保存迟滞/捕获历史；不模拟锁舌斜面、扣板预载与真实连续接触；有限游隙和高速捕获仍需运行证据 | 建议采用。依据是当前任务目标与真实代码路径，不是旧软件偏好 |
| B02 B：保留当前实体latch+mimic代理 | 保留接触决定解闩的现有链路；锁舌反力直接参与求解 | 当前cone位于门顶附近，行程、mimic、搭接和handle角联动；“保留现有物理”不等于已标定真实锁体，随机解锁角需同步改几何/传动 | 两份均不选；不额外实现B或精细锁体作为对照 |
| B04 native joint limit | 复用当前150°路径，可与B02共用单一限位写入者；保留求解器对接触/动量的处理 | 不是实体door stopper，存在求解容差；不能从接近上限直接声称测到挡止冲量 | 建议采用M~U(90°,150°)，每门固定，属于工程覆盖域 |
| B04实体stopper / 后写角度裁剪 | 前者可表达局部挡止接触；后者实现简单 | 前者新增几何、材料和碰撞标定；后者直接改物理状态，破坏相应动力学语义 | 两份均不选，当前任务没有增加这些路径的必要 |

出处：[Pro1 FULL_REVIEW](pro_1/original/FULL_REVIEW.md)、[Pro2 FULL_REVIEW](pro_2/original/FULL_REVIEW.md)各自的选择与优劣比较；下表参数以各自DESIGN_SPEC/参数附件为准。

## 2. 不能合并成“共识参数”的差异

统一符号：门角q、把手下压角h、把手止挡H、解锁阈值u、正常门轴上限M；以下角度表用degree，runtime使用rad。

| 项目 | Pro1 | Pro2 |
|---|---|---|
| 把手行程与解锁 | H=45°；u~U(25°,40°) | H~U(40°,60°)，ρ~U(.65,.85)，u=ρH；u支持域26–51°，并非uniform 26–51° |
| 解锁后余程 | 5–20° | H−u支持域6–21°，并非独立抽样 |
| 把手迟滞 | 3° | 2° |
| 锁住时门轴游隙 | [0,.25°] | [0,.25°] |
| 复锁捕获区 | q≤.10°；没有显式捕获下界，负向越界另诊断 | −.05°≤q≤.20°；−.05°是容许已有lower误差，不是将物理lower改为负值 |
| handle回位 | 沿用作者层raw USD K=50、D=.5、target=−15°，每门cap~U(1,3)N·m | SI零位预载τ0=.35N·m，端点静态回位T_H~U(1,3)N·m；k=(T_H−τ0)/H_rad、b=.05N·m·s/rad、h_rest=−τ0/k，native cap固定3N·m |
| 运行时handle targets | 显式position=−π/12、velocity=0、effort=0 | 显式position=h_rest、velocity=0、effort=0 |
| FSM时相 | PRE：sim.step前用上一帧状态同步 | POST：scene.update后、日志early return前同步，新限位供下一物理步 |
| release gate后的hinge速度项 | 去掉正收入，保留负关门项 | 整个hinge位置＋速度项乘收入mask，gate后负关门项也不再计入 |
| release gate后的hold_and_drive | 最后覆盖结果也加收入mask | 同左 |
| release gate后的正grasp | 未提出对应修改 | Stage4去掉正grasp，保留其负值 |
| 近闭门的回柄奖励 | hinge≤.25rad时停用，允许再压柄 | 保留原stage/速度项，只将45°位置尺度改为H |
| 双指断触 | 连续3个control间隔确认，并参与Stage4→5和回臂条件 | 连续2个control间隔用于事件记录，保留现有晋级/回臂条件 |

Pro1的45°方案缩小了行程改动，但不等于负载行为与现有runtime相同：raw K=50配−15°时，零位弹簧请求已达750N·m，远高于1–3N·m cap，设计表现接近饱和回位。Pro2选择渐增负载，其k约.621–3.796N·m/rad；它是另一个明确的物理域，不是单纯修复单位。两者均未给出实机标定或训练优越性证据。Pro2用于说明预载的handle重力估算也不能写成实际读回。

**本地推荐：以Pro2整套行程/负载、POST时相和保留当前阶段条件的设计作为下一版讨论基案，加入下文的本地接入纠正；Pro1作为完整保留的窄行程备选。** 选择理由是总行程与解锁相对位置明确关联、SI回位曲线可解释、POST快照与现有bank保存时机便于统一。不是取两份参数平均，也不把Pro1的额外阶段门槛悄悄并入。H/u域和回位曲线仍由Owner后续确认，不恢复旧20–60°/+5°为默认。

## 3. 当前source、config与API证据

[对照记录](LOCAL_SOURCE_ALIGNMENT.json)为本轮更新文档前的34路径逐字节比较：受核source/config均与review输入一致，只有较新的README/decision log有交付记录差异。因此下述是对当前路径的核对，不是拿旧分支覆盖本地。沿用当时真实入口生成的[resolved config](../../../v29/pro_handoff/20260918_b02_b04/CURRENT_RESOLVED_CONFIG.yaml)，本轮未重复启动配置/模拟器。

| 结论 | 当前证据定位 | 等级/含义 |
|---|---|---|
| 当前仍为handle→mimic→prismatic latch→cone/frame碰撞解锁；门轴上限150°、handle上限45° | [door.py](../../../../gr00t/rl/isaac_utils/playground/env_rand/door.py)，spawn_door的hinge/handle/latch构建，约521–632行 | INSPECTED；A尚不存在 |
| 删除latch不能顺便关闭整个door articulation自碰撞 | 同文件约517–519行将enabledSelfCollisions绑定build_latch；[场景配置](../../../../gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py)的articulation_props也参与最终配置 | INSPECTED；须解耦开关并保留必要panel/frame/handle接触，不证明当前接触质量 |
| native limit setter可选env/joint，输入为(M_changed,1,2)浮点tensor，env ids为device-local long，runtime角度rad | [本机Articulation](../../../../../IsaacLab/source/isaaclab/isaaclab/assets/articulation/articulation.py)，write_joint_position_limit_to_sim约710行；[官方API](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.assets.html#isaaclab.assets.Articulation.write_joint_position_limit_to_sim) | INSPECTED；维护hard/default/soft缓存，完整limits转CPU后按env indices提交，不重写当前q |
| 正常最大角M不能从当前active upper或soft upper反推 | 同上API及两份DESIGN_SPEC | 设计约束；锁态时active upper只有.25°；单独持有每门M |
| USD angular gain按degree，SI/rad增益写USD时乘π/180；target在USD用degree、runtime用rad | [本机schemas](../../../../../IsaacLab/source/isaaclab/isaaclab/sim/schemas/schemas.py)的drive配置约646–677行；[OpenUSD DriveAPI](https://openusd.org/dev/api/class_usd_physics_drive_a_p_i.html) | INSPECTED；cap是N·m上限，不是逐步实测关节/接触力 |
| reset把+15π/180写入effort target | [Door环境](../../../../gr00t/rl/envs/door/door_open_a2_base.py)::_reset_door_states，约29462–29465行 → [模拟器](../../../../gr00t/rl/simulator/isaacsim/isaacsim.py)的effort writer，约2832–2838行 | INSPECTED；这是+.261799N·m前馈目标，不能当作15°位置目标 |
| 作者层−15°目标会被零位runtime position-target覆盖，所查路径未另设handle position target | 场景ImplicitActuatorCfg约2032；本机articulation初始化target buffers约1641–1647，write_data_to_sim约262；[ImplicitActuator](../../../../../IsaacLab/source/isaaclab/isaaclab/actuators/actuator_pd.py)约118–143；模拟器每步scene.write_data_to_sim约2914 | STATIC_INFERENCE：链路完整；实际PhysX targets/施力曲线未读回，不能称RUNTIME_PASS |
| 两条活跃handle reward尺度都需改 | Door helper约2090/5737/18384的0.6rad与float标量接口；[creation helper](../../../../gr00t/rl/envs/door/a2_v26_3_creation.py)约10/54–65的45°，环境初始化/更新约14570/14604 | INSPECTED；仅改YAML不够，需每env u(N,)且device/dtype匹配 |
| 两类bank已经按env保存/恢复 | [staged_task_base](../../../../gr00t/rl/envs/base_task/staged_task_base.py)约529/556/642/738；Door recovery约14449/14475/14512 | INSPECTED；staged[stage,slot,env_id]，recovery[slot,env_id]；左右配平不搬运其他门状态 |
| 物理调用顺序是PRE→sim.step→scene.update→POST | [legged_robot_base](../../../../gr00t/rl/envs/legged_base_task/legged_robot_base.py)::_physics_step约1114；模拟器约2910；Door hooks约9534/30196 | INSPECTED；control=.02s、physics=.005s，锁态不应只随reward/control更新 |

本机IsaacLab路径以当前安装源码为准；包内节选是输入证据，在线main文档只用于交叉核对，不能代替实际安装版本或本机运行。

## 4. 锁态、拓扑与恢复的采用/调整意见

**采用两布尔历史。** R表示带迟滞的退舌分支，E表示是否已捕获门框。h≥u令R=true；h≤u−δ令R=false；中间保留历史。R=true优先解除E；R=false且进入捕获区才置E=true；否则保留E。自然闭门R=false/E=true；半开门松把手不会收紧限位；压住把手关门不会复锁；已锁门在捕获区外、.25°游隙内移动仍保持E。其余质量、closer、friction正常求解，不按stage暂停。

**选定时相后才定义快照合法性。** Pro1 PRE方案允许最后一个物理步刚跨u、尚未下一PRE同步的快照出现h≥u而R=false；这是它已说明的时相，不是自相矛盾。Pro2 POST方案在保存前已同步，才可使用h≥u⇒R=true的即时校验。本地推荐POST，机制更新须位于现有temporal-evidence early return之前，不能被日志开关关闭；首次物理步前就应有正确限位。不可拿Pro2 validator检查Pro1阶段的快照。

**纠正Pro2文字歧义。** 其DESIGN_SPEC §5.2“超过捕获区的open/armed状态E=false”不能解释成q>capture就判E=true非法：捕获后的门可在capture与epsilon之间合法晃动。应保持§3的历史FSM；例如q=.22°、R=false、E=true仍在.25°锁游隙内。这里只澄清计划语义，未添加fixture或测试。

**拓扑一次迁移。** A删除latch cone/collider、滑块joint、mimic及附属质量，不保留伪第三DOF。hinge/handle按名称找到索引，所有直接读写、buffer、target、观测仍输出明确的hinge/handle两维。现有三列buffer与`[0,1,2]`reset不能继续沿用。旧三DOF bank不进入新机制；不建立兼容迁移层，不为新baseline添加旧三DOF兼容分支。

**复用现有per-env bank。** 每门参数生成后固定，现有索引已支持同门恢复；tracked buffers支持bool，R/E可接入并随recovery收录。没有证据需要新建跨env身份匹配框架、完整配方复制或通用schema迁移器。只保留机制版本/参数对应关系所需最少标识与R/E历史。参数改变或重建物理门时旧bank不能继续当合法状态；发现不一致显式失败，不新增“丢掉坏样本继续跑”的兜底。原有无可用bank时的natural起点逻辑与坏状态掩盖不同。

**最终提交必须在全部恢复之后。** reset事务内先给选中env准备[0,M]，随后执行natural/staged/recovery的原状态恢复，最后恢复R/E、creation/history、handle targets及相应active bounds，再允许physics step。`DoorPregrasp.reset_envs_idx`约29069在super之后仍可调用recovery restore，后者约14555直接写状态、不会调用staged validator；只修natural callback或staged validator会漏掉此路。

**准确区分两处reset影响。** `door_dof_state_buf[:]`全清的是临时buffer，实际DOF writer只写env_ids，不能据此声称其他门q被重置。模拟器root writer约2818的无参`task_obj.reset()`才会调用本机Articulation.reset清全部actuator/wrench状态；它不重写q或joint limits。接入时改为选中env，别把这项扩大为“已证明所有native targets被reset清除”。

以上限位writer只在状态变化或明确reset时批量提交，正常M保持不可变；API成功提交才发布对应状态/事件，实际反作用在下一solver步产生。(.25°,.20°,.05°)仍是工程初值，高速捕获、锁定承载及大量env下CPU传输成本保留LOCAL_ONLY。

## 5. 奖励、释放与观察：哪些采用，哪些不自动加入

**两份共同且必要的参数接线**：creation截断/归一化和unlatch_hold使用u；hard-stop遥测和dont_push_handle位置尺度使用H。creation high-water在同一episode复锁后不清零，natural初值/staged恢复不能凭reset发新进度。helper接口从标量改成同device/dtype的(N,)参数；不能把q/u作为新增policy观察。

当前Stage3→4仍需真实门角>.25rad和握持条件；软件解锁事件不是晋级成功。release gate在Stage4门角≥1.2rad后锁存，Stage4→5当前仅需q>1.0472rad、h<.2rad、root_x>0。门上限M≥90°仅满足角度阈值顺序，不证明机器人净空/过门成功。

当前源码确有三处收入需要分别看待：`_reward_push_door_hinge`约17571只mask位置、未mask速度；最终覆盖后的`hold_and_drive`约18394调用无gate的hold mask；`_reward_grasp`约16817仍可有正值。resolved scales分别为6/8/.2。这证明存在激励路径，不证明它们造成了v28“开到挡止”的行为。

| 意见 | 具体边界 |
|---|---|
| 建议采用Pro2的post-gate收入方案，待Owner确认 | hinge整项与最终hold_and_drive乘原Stage3或Stage4未gate的收入mask；Stage4 gate后grasp只保留负值。B01允许物理回关，因此不让同一开门项在release gate后继续惩罚正常关门；代价是不能再靠该项推动gate后的重开恢复，后续任务收益能否支撑恢复未知 |
| 保留现有stage/回臂条件作为本次建议基案 | 不自动加入Pro1的gate＋连续3间隔两指全断触晋级门槛。它改变阶段成功合同及回臂时机，不是B04限位随机化的必要修复 |
| Pro1近闭门回柄mask单列，不直接采纳 | hinge≤.25rad停用回柄奖励可能减轻再压柄冲突，但它是恢复奖励扩展；Pro2未包含，当前任务未确认恢复行为设计 |
| 事件定义采纳、去抖参数仍为候选 | release permission、张爪意图、失去双指同时接触、两指均无接触、再接触、root crossing分别记录；Pro2的2control间隔只用于事件，不变成隐藏stage guard |

当前回臂条件`release_gate & ~both_contact`允许仍有一指接触；Pro1改成两指均断触是实质差异。现有handle filter只覆盖arm_body7/8，阈值以下只能叫“两指传感判据下无接触”，不能报告全机器人脱离把手。指令、逻辑许可、接触与成功不互相代替。

两份都不向actor/Student新增u/H/M、R/E、closer/friction真值或限位反力答案。Teacher已有质量/几何特权输入及LSTM不变；不新增网络或脚本试推。“压到底再推”仍是允许学习出的策略，无运动也可能由重门/closer/friction造成，不能直接当未解锁标签。

## 6. 证据等级与必要未知

| 证据 | 可支持 | 不能支持 |
|---|---|---|
| 两份原始STATIC_CHECKS/参数/伪代码 | CLOUD_STATIC：报告内角度关系、示例状态转移、单位推导与作者建议 | 本机PhysX、真实随机门、机器人接触或训练PASS；本轮没有执行包内检查 |
| 本轮source/config/本机IsaacLab定向阅读 | INSPECTED及明确标注的STATIC_INFERENCE：操作路径、shape/单位、活跃reward、reset次序 | 新机制已经工作、比B更真实或更好学 |
| [9月17日最终资产one-batch](../../../v29/runtime_logs/baseline_no_center_smoke_20260917/runtime_readout.json) | 当时64env、PPO一批4096timesteps完成；learned_behavior未评估 | 尚未实施的B01/B02/B04、9月18日起点/速度域、成像质量；旧日志也明确renderer问题 |
| 实施后才可取得的证据 | LOCAL_ONLY：锁游隙承载/泄漏、高速复锁冲量、目标与扭矩曲线、90°通行/回弹、staged/recovery真实恢复、setter成本 | 当前不得预填结果或用云端PASS代替 |

剩余Owner选择集中在：是否采用共同A/native方向、Pro2或Pro1的行程/回位负载配方、是否连同post-gate收入调整一起纳入B04。Pro1新增阶段条件另列，不默认为必须。实际参数承载和学习表现仍未知；当前不批准运行预算，也不添加测试矩阵或安全框架。

本轮只写本目录与当前plan/TODO/决策入口/memory。B02/B04未勾选、未PASS；B01范围沿用、B03后置、B05待讨论。没有source/config/asset改动、仿真/训练/render、测试、Git提交/发布或Teacher/G7更新，未重开v28验收；两路只读工作均已结束，无活动资源。
