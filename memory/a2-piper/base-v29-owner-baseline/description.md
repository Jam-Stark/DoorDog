---
name: base-v29-owner-baseline
status: c002_resume8000_delivery_closed
scope: v29 baseline实现验收、GPU0正式运行批准及证据边界；worker训练监督
last_verified: 2026-09-22
evidence: D077接受D074最终交付；exact8000自然64观测双侧各32/32goal；单seed范围，B08未入实验，loss仍未观测
supersedes: 2026-09-19 01:57 HKT及此前“当前未实现/未验收/未批准”状态；历史决定与证据仍保留
read_when:
  - preparing or implementing base_v29
  - changing Stage5 heading/posture, door handle height or the wrist camera asset
source_of_truth:
  - scriptsFORhuman/v29/a2_piper_base_v29_C002_resume8000_final_readout_20260922.md
  - .ai/runtime/v29_baseline_team/D077_C002_RESUME8000_FINAL_ACCEPTANCE.json
  - scriptsFORhuman/v29/README.md
  - .ai/runtime/v29_baseline_team/D074_OWNER_AUTHORIZED_RESUME8000_REGISTRATION.json
  - .ai/runtime/v29_resume8000/OWNER_AUTHORIZED_PLAN.json
  - scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md
  - scriptsFORhuman/v29/a2_piper_base_v29_baseline_plan.md
  - scriptsFORhuman/v29/a2_piper_base_v29_worker_start_prompt.md
  - scriptsFORhuman/v29/a2_piper_base_v29_acceptance_and_coordination.md
  - scriptsFORhuman/v29/a2_piper_base_v29_worker_decision_log.md
  - scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md
  - scriptsFORhuman/v29/a2_piper_base_v29_b05_worker_handoff.md
  - scriptsFORhuman/v29/b05_gripper_confirmation_20260919/README.md
  - scriptsFORhuman/pro_reviews/v29/20260918_233820__B05_handle_review/LOCAL_RECONCILIATION.md
  - scriptsFORhuman/v29/a2_piper_base_v29_decision_log.md
  - scriptsFORhuman/v29/a2_piper_base_v29_overall_arrangement.md
  - scriptsFORhuman/v29/a2_piper_base_v29_baseline_TODO.md
  - scriptsFORhuman/pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/LOCAL_RECONCILIATION.md
  - scriptsFORhuman/pro_reviews/v29/20260918_192550__B02_B04_dual_pro_review/LOCAL_RECONCILIATION.md
  - gr00t/rl/envs/door/door_open_a2_base.py
  - gr00t/rl/config/ablation/wbmanip/base_v29_baseline.yaml
  - gr00t/rl/config/robot/A2_Piper/a2_piper_v29.yaml
  - gr00t/rl/data/robots/a2_piper_v29_merged_20260917/config/camera_rig.json
related_entries:
  - base-v28-camera-aware-rebaseline
  - novelty-research
---

# base_v29 Owner 基础改进

2026-09-22，Owner查看两例8000边界render后提出回臂与clean问题。本次[质量补充分析](../../../scriptsFORhuman/v29/a2_piper_base_v29_8000_quality_followup_20260922.md)确认RIGHT虽complete但gate后身体力约249.85N；原自然64终态中LEFT有1/32例、RIGHT有14/28个gate事件已记录例出现>5N身体力，另4个RIGHT无gate记录、不可计作0。这补充D077的complete结果，不改变其执行验收。B08只解除Stage0动作覆盖，未修改Stage5回臂；当前trace缺实际arm q/dq，无法量化持续hold。建议先质量评估，再同8000起点的C002/B08等更新续训对照；尚未选择新配方、批准或启动运行。

2026-09-22 11:08 HKT，D077已接受并关闭[同配方8000最终交付](../../../scriptsFORhuman/v29/a2_piper_base_v29_C002_resume8000_final_readout_20260922.md)。自然64的LEFT/RIGHT各32/32goal，全部max/final Stage5与complete、staged load0；6000/7000/8000总goal0→31→64。Main命令/预算/实际8000 end capture/loader核对及独立原始结果归约无阻断；六个门字段逐env与6000一致。证据限单seed291有限人口，无family/跨seed/硬件泛化或PPO loss有限性证明，未新增Teacher绑定。旧6000/7000卡点保留历史，B08未入运行。GPU0本任务lease已由worker释放、等待关闭；GPU1 D067不变，下一运行范围须Owner决定。

2026-09-21 20:04 HKT，D076登记并核对[7000自然里程碑](../../../.ai/runtime/v29_baseline_team/D076_C002_RESUME7000_NATURAL_MILESTONE.json)：LEFT31/32 goal且32例都到Stage5；RIGHT31例Stage3＋1例Stage2、Stage4+仍0。actual eval720.633s/exit0、64唯一首episode/full exact7000，六个可用门字段与6000逐env一致。同PID3055669暂停评估后继续，原D074只到8000；尚无7000→8000持续趋势/RIGHT整任务证明。6000周期性开爪诊断保留历史，本结果已显示多数RIGHT越过Stage2，不能继续套用旧卡点。当前实验未用B08修复，loss不可观测边界不变；具体ETA/同一等待从runtime读取。

2026-09-21 17:13 HKT，对D072既有trace的[新增离线分析](../../../scriptsFORhuman/novelty/documents/20260921_cross_branch_bilateral_attribution.md)定位C002@6000 RIGHT自然评估的Stage2开合周期：有效握持每例最多3–4步，正开爪命令伴随3760次计数中断，未达K5。它不改变D072结果/实现验收，也不是D074新checkpoint效果；训练成因与B05/左右因果尚未隔离。原GPU0/1运行、输入和等待未改。

2026-09-21 14:36 HKT，D075按Owner授权完成B08公共修复与四个开发worktree同步：普通/canonical Stage0不再覆盖六维arm累计target，真实reset保留。证据为限定CPU动作链及一次跨分支源码一致性检查；未运行新增仿真/训练，改动未commit/push。GPU0 C002及GPU1 HA-C001原运行目录源码保持，开发目录和证据统一见[B08实施记录](../../../scriptsFORhuman/v29/a2_piper_v29_B08_implementation_20260921.md)。下方D072/D074及9月20日的OPEN表述是当时状态。

2026-09-21 11:08 HKT，D074以Owner决定登记新的同配方续训授权：[原指令/启动](../../../.ai/runtime/v29_resume8000/OWNER_DECISION_AND_START.md)、[精确计划](../../../.ai/runtime/v29_resume8000/OWNER_AUTHORIZED_PLAN.json)。GPU0从精确6000 full resume到累计8000，新增2000更新；7000/8000各一次相同设置64自然首episode，重点LEFT goal及RIGHT突破Stage2/到Stage4，8000后不自动延长。worker新增控制callback/协调脚本实施7000同PID暂停/串行评估/继续，初始恢复仍natural reset并重建bank，非逐比特物理续接；实际初始化与结果尚待读回。原production reward/action/assets及B08保持，loss仍NOT_OBSERVED。D072原6000交付/0/64与旧任务关闭保留历史；新GPU0租约归v29_baseline_resume8000，GPU1 D067及同6000对照基准不变。Main只登记Owner已生效授权与命令一致性，不重批、不发routineACK；ETA/操作性上限/当前等待只从runtime读取。

2026-09-21，D072关闭冻结C002实现和D060首轮训练/评估交付，见[最终读回](../../../scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md)。训练6000 exit0、45.4594h，final actor/value有限，实际end capture在6000/4096执行；一次64自然首episode full-loader评估exit0、723.228s，条件及预算与D060一致。原始结果0/64 goal：LEFT最高Stage2/4/5为2/27/3，RIGHT32例均Stage2，全部stage_overtime。此为执行交付接受与策略负结果，非完整任务Teacher资格、跨seed总体概率或左右差异的因果解释；loss仍NOT_OBSERVED。质量×closer六格按实际weight/hinge cap派生，每侧各5–6；family/最大开角标签未导出，不能作对应分组结论。B08仍OPEN，GPU0本任务租约按D072关闭，GPU1独立合同不变，无追加运行授权。

2026-09-20 17:32 HKT，Owner要求确认N01发现的Stage0 arm action覆盖并加入baseline待办。已沿当前C002非canonical路径确认：每步积分后Door环境把六维arm累计增量置0，再映射为default_dof_pos关节目标；不是仅reset初始化或物理锁死，base/gripper不属于这六维覆盖。canonical事实、source行号、影响与后续最小处理统一见[baseline TODO B08](../../../scriptsFORhuman/v29/a2_piper_base_v29_baseline_TODO.md)。状态为高优先级OPEN、修复未实施；本轮仅INSPECTED和登记，未运行测试/仿真/训练、未改变GPU0/GPU1候选或等待，未认定当前训练困难由它单独造成。

2026-09-20 11:30 HKT，D066 Owner通信约束：planner、baseline worker和handle ablation worker统一低频通知，仅重大进展/待决策/实质异常/最终交付发送；普通进度、本地记录和无需行动的review不发送“收到/继续”确认链。同一事件整合一次，已有文件事件时不重复queue；启动与初始化、正常终态与后续eval尽量合并。规则见验收合同§6，不改变任何运行预算或配方。

2026-09-20 11:25 HKT，D065：Owner新增GPU1旧把手对照与Git版本保存，独立事实/待办从[handle ablation entry](../base-v29-handle-ablation/description.md)读取。原GPU0已批准运行与等待保持；本条不记录新的baseline训练结论。

2026-09-19 11:31 HKT，D062通信事实：当前worker通过run-local `wait_event.py`读取STATE变化与消息文件，已经处理的批准不依赖界面queue副本。CLI queue是后续turn输入，不是steer；旧D032–D061副本可由Owner清除。Main向这个仍有文件事件waiter的worker通知新决定时，沿用既有STATE事件，不再重复enqueue；实际删除未由Main执行。记录与适用范围见D062，不泛化到无文件事件接收者。

2026-09-19 06:52 HKT，D061监督边界：当前trainer会把完整数值metrics写入内存`state.log_history`，但ModelSaveCallback在保存checkpoint前显式删除该字段；既有实际4096 step1 checkpoint的CPU读回确认没有它。Rich未打印policy/value/weighted PPO loss且本轮use_wandb=false，因此本轮loss为NOT_OBSERVED，不能从reward、entropy或checkpoint存在推断loss有限。原worker prompt包含loss监督，Planner已在[D061](../../../.ai/runtime/v29_baseline_team/D061_INITIALIZATION_AND_LOSS_OBSERVABILITY.json)明确登记本轮监督范围例外，保持已运行冻结候选；没有追加导出改动或要求重启。

2026-09-19 05:48 HKT，D060：**C002 完整baseline实现验收通过，首轮GPU0正式训练已批准**。D056逐项验收的唯一Stage5缺口已由两环境实际reward输出关闭：heading .35rad为−.0098，roll/pitch .10/.08的旧−2与新−8项合计−.00328，Stage4新项为零；dt=.02、实际K路径排除三项。C002生产代码/配置/资产继承C001冻结320文件，仅新增定向probe。决定与范围从[主D日志](../../../scriptsFORhuman/v29/a2_piper_base_v29_decision_log.md)、[D056逐项验收](../../../.ai/runtime/v29_baseline_team/D056_C001_PER_ITEM_ACCEPTANCE.md)和[D060授权](../../../.ai/runtime/v29_baseline_team/D060_C002_ACCEPTANCE_AND_TRAIN_APPROVAL.json)读取，memory不授予运行权限。

接受的运行证据包括B05实际34门固定root reference主握段双指接触及Main亲自查看的资产/接触图、B01/B04原生参数与释放/触限窗口、natural及真实Stage1 snapshot/restore保持、4096单batch与step1 checkpoint、64环境实际full reload路径。各证据只覆盖所记录条件；env load不等于完整物理/staged精确恢复，未证明策略质量、任意动作无接缝或硬件效果。D060批准worker一次seed291/4096env/6000batch/save100/scratch，含启动48h上限；正常完成后精确final checkpoint的64自然首episode eval上限20min。正式输出使用logs_rl/.../base_v29/push_baseline_C002_seed291及logs_eval/base_v29/.../natural_final。实际启动/ETA/资源/等待由`.ai/runtime/v29_baseline_team/STATE.json`与真实receipt记录，不写成memory heartbeat。

2026-09-19 01:57 HKT，D033–D034：C001有界验证命令已由planner批准；64-env短PPO可先行，固定root reference bench只用于局部几何/目标/接触。要求一次补齐F2联合边界（34门）、动态接触定位/腕掌panel读数及真实checkpoint重载身份；纯读callback已定向核对，worker完成明确修正后可直接在GPU0原额度执行。运行事实及正式候选仍待提交，无TRAIN_APPROVED。当前批准细节从`.ai/runtime/v29_baseline_team/STATE.json`及其D034入口恢复。

2026-09-19T01:38:12+08:00，D032：实际worker任务`01a0b592-48e3-7ad0-9263-4cb605862ed6`已接手完整baseline，C001准备中。Main已绑定任务/归属并为worker租用GPU0，只批准有界验证（64/4096 env各1-batch及待具体命令核对的资产/contact/重载路径）；正式训练批准仍为空。实际绑定、验证命令、待办及事件等待以`.ai/runtime/v29_baseline_team/STATE.json`为入口；worker自主实施并回报ETA/候选，planner逐项验收及裁定。

2026-09-19 01:25 HKT，D030–D031：Owner委托worker负责完整baseline实现与训练监督，授权Owner离线时与planner自主双向沟通；planner逐项严格验收、退回修正，最终批准后worker仅GPU0首轮开训。当前[完整启动prompt](../../../scriptsFORhuman/v29/a2_piper_base_v29_worker_start_prompt.md)与[验收合同](../../../scriptsFORhuman/v29/a2_piper_base_v29_acceptance_and_coordination.md)已重写，B05仅技术附件。planner任务01a0af49-b5e0-75f2-8fdd-ad5c3e20744b已确认，worker ID待Owner回传；活动绑定从.ai/runtime/v29_baseline_team/STATE.json恢复，当前无候选/开训批准/运行。turn/steer是协议非本机CLI，备用codex queue语法已读help核对；入队不等审批。Owner/Planner主D日志与Worker独立W日志区分来源，禁止把旧方案/静态PASS当新实现或训练PASS。

2026-09-19 00:44 HKT，D029：Owner全部采用B05 Pro建议，要求按当前PiPER/TCP二次确认后由planner写plan、Owner交worker实现。全部参数已在[执行规格](../../../scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md)定稿，七族1/7、h55–85、截面/roll/λ、条件圆滑return、rose与X1训练外安排不再待决。[二次静态确认](../../../scriptsFORhuman/v29/b05_gripper_confirmation_20260919/README.md)支持约70/74mm开口、34.071mm最大截面及默认G组合分离；h55的4.2mm仍是理想平面量。R/H按有效联合域抽样。B04/B05方案PASS，生产实现/导入接触证据待worker；[交接](../../../scriptsFORhuman/v29/a2_piper_base_v29_b05_worker_handoff.md)备好未派发。无生产代码/资产/配置修改或训练监督。

2026-09-18 23:48 HKT，D028：B05 Pro附件已原包/原文归档并完成一次[定向核对](../../../scriptsFORhuman/pro_reviews/v29/20260918_233820__B05_handle_review/LOCAL_RECONCILIATION.md)。七族保持，Pro建议暂不加第八训练族，优先h/截面方向/条件return，X1轻弯×椭圆留未见组合候选。F5局部重叠、约0.98/1.10mm曲率残差、F6约2.42mm梯度及指体前伸50.8mm获静态支持；h55的4.2mm只是理想平面余量。ASSA projection不当h，FSB1294跨语言方向冲突保留。全部新域/权重/饰盖仍待Owner决定，B04/B05方案PASS与默认planner职责保持，无实现/训练。

2026-09-18 21:53 HKT，D027：B05独立Pro输入已完成[发布/上传](../../../scriptsFORhuman/v29/pro_handoff/20260918_b05/README.md)。分支codex/v29-b05-pro-20260918与远端一致；两个ZIP/三索引五文件按名称、字节数、父目录读回。D026七族全量批准、B04/B05方案PASS及默认planner职责保持；Pro结果待Owner附件回传，不去Drive找答案。无代码实施/仿真/训练监督；输入35文件仅含三件局部夹爪mesh，非完整运行包。

2026-09-18 21:38 HKT，D026：Owner确认B05七族全部纳入baseline plan，B04/B05均按方案讨论完成勾选。取消七族分首批/扩展的建议；族配比/连续域由Pro后续细化，不能因此撤销讨论结案。Owner明确Main默认planner，仅有明确要求才做代码实施或训练监督。本轮独立Pro审阅聚焦构型重复、扩展必要性和现实handle覆盖；不启动实现/仿真/训练。最新canonical为plan §7、B05设计及D026。

2026-09-18 21:23 HKT，D024–D025：Owner确认B04应按方案讨论完成勾选，已标PASS并另列实现待办（仍150°）。B05两路team给出七族与当前指部/frame事实，Main交付[规格与图](../../../scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md)：圆直、椭圆、圆角扁、单弧、浅S、偏置直腹、缓锥度。G由收缩后主段弧长中心与朝轴颈的有向切线确定，Y闭合/+Z接近；56mm全指包络只是静态参照。B05待选族/参数/权重，未实施资产或运行；D023奖励和N02归属保持。

2026-09-18 20:45 HKT，D023：Owner要求baseline暂不做按需回弹恢复，并澄清选择精确恢复D021之前的原公式；hinge、hold_and_drive、grasp三处已回退，与D021前review输入逐段一致、AST通过。当前gate后门速/持握推动收入恢复，门角位置项仍沿旧gate规则；未额外开放角度收入。重新抓把手扶门及D022候选已移入[N02讨论](../../../scriptsFORhuman/novelty/documents/20260918_n02_regrasp_rebound_discussion.md)，不作为baseline前置。B04最大角仍待实施、当前150°；D021 CPU证据标历史，不作当前结果，无新仿真/训练。

2026-09-18 20:35 HKT，D022：Owner补充强回弹后重新伸臂扶门目标，明确首版限定重新抓把手。D021仍是当前源码，但最终释放/恢复奖励合同重新讨论；Stage4/5接近把手、回臂及近闭门回柄也存在恢复激励冲突。候选与source依据统一在[plan §6.3.1](../../../scriptsFORhuman/v29/a2_piper_base_v29_baseline_plan.md)：历史release事件与当前辅助需求分开，按需恢复引导且避免重复领取进度。具体几何/时窗/权重/Phi未定，无新代码/测试/仿真/训练；B02/N01/N02既有分支安排保持。

2026-09-18 20:22 HKT，D021：Owner明确要求先直接修复release gate后的奖励冲突，三处共享A2源码已改：hinge整项与最终hold_and_drive按既有Stage3/Stage4未gate mask收束，Stage4 gate后grasp去正留负；gate前收入、阶段/权重和观察保持。[CPU证据](../../../scriptsFORhuman/v29/implementation_evidence/release_income_20260918/README.md)通过，覆盖gate前/后、正负门速/握持与锁存；未运行IsaacSim/训练。B04最大角仍150°、新增事件未实施，B02后置安排不变；不把CPU分支证明升级为行为改善。

2026-09-18 20:00 HKT，D020：Owner将B02移出当前baseline，其他baseline项确定后再单开apply B02分支做ablation；当前未建分支。baseline保留实体latch/mimic三DOF、原handle动力学/尺度。B04按双Pro形成[plan §6](../../../scriptsFORhuman/v29/a2_piper_base_v29_baseline_plan.md)：每门固定native M90–150°、Pro2 post-gate收入、原阶段条件，无B02临时锁限位依赖；工程方案未实施、未标PASS。B01三档与B03后置不变，B05待讨论；总体安排和独立ablation TODO已同步。

2026-09-18 19:47 HKT，D019：两份Owner附件已原包/原文归档并定向核对。[当前对照](../../../scriptsFORhuman/pro_reviews/v29/20260918_192550__B02_B04_dual_pro_review/LOCAL_RECONCILIATION.md)是选择、差异与source事实的canonical入口。两份均选A虚拟锁闩/native M90–150°，Main建议以Pro2行程/SI回位/POST/保留阶段条件为讨论基案；尚待Owner确认，B02/B04未实施或勾选。核实effort/position target混淆、runtime零目标覆盖静态链、per-env bank、outer recovery后最终同步、0.6rad与45°双reward路径；参数/性能/学习效果未验证。B01三档与B03后置保持，无运行或资格更新。

2026-09-18 D018：B02/B04独立Pro输入交付完成。[入口/prompt](../../../scriptsFORhuman/v29/pro_handoff/20260918_b02_b04/README.md)；review分支codex/v29-b02-b04-pro-20260918已push并核对远端一致，Drive两个ZIP/三个索引均按名称/字节数/父目录读回。当前resolved仅解析，旧smoke为历史；无新训练/物理实现。B02机制重新二选一、B04限位设计待Pro，B03按Owner后置。Pro结果由Owner以附件回传，不去Drive寻找答案。

2026-09-18 17:04 HKT：D016按Owner要求将B02重新开放软件约束A/当前物理解锁B二选一，交Pro比较并给选择与设计；D015软件偏好及20–60°/+5°不预设结论。D017将B03后置到baseline出来后微调（当前15°，不作前置），同包追加B04软件裁剪/native limit/实体stopper辨析及设计。当前正准备独立review分支与create-only Drive交付，未实施B02/B04或启动训练。

2026-09-18 16:45 HKT：B02按Owner意见选择软件虚拟锁闩方向。当前实际是高位cone+mimic物理碰撞锁门，非现成Boolean开关；两路只读讨论后Main建议解锁U20–60°、机械止挡+5°，角度/复锁细则待Owner确认。plan §5与D015记录有限游隙原生约束路线、0.6rad与creation固定45°奖励同步、移除第三DOF与natural/staged锁态恢复；未实施、未勾选B02或启动运行。B01三档和D013速度保持。

2026-09-18 15:27 HKT：D014按Owner要求将B01质量更新为30–80/80–120/120–160kg三档各1/3；有/无闭门器各半，六组合各1/6，替代D012两档。plan补充重门惯量量级和瞬态差异，三档共用T/参考速度及摩擦域，不按质量放大drive抵消重门效应。仅计划与记录更新，B01物理代码仍待实施，无新测试/训练/仿真。

2026-09-18 15:08 HKT：Owner确认B01质量30–80/80–120kg各半、有/无闭门器各半及门轴松紧与drive联合设计，并要求开始落地baseline plan。B01讨论PASS，联合SI配方及baseline/N02分工已进入新plan，物理代码未改，B02–B05未决（D012）。Owner确认速度为0.5/0.3m/s、2m附近平滑过渡；D013已实施门法向1.8–2.2m smoothstep，Stage4/5仍0.3，配置解析与source AST通过，无新测试/仿真/训练。当前Teacher有LSTM、门角/接触反馈和质量真值，无closer/friction真值；这支持baseline纳入回关的设计判断，不证明策略已学会或N02有效。

2026-09-18 14:44 HKT：Owner授权判断0.3m/s是否满足新起点并直接实施。因最远起点至站位约3.2–3.4m、Stage0仅10.5s，已将Stage0独立速度目标`a2_stage0_target_root_vel`设为0.5；Stage4/5仍使用原`target_root_vel=0.3`。配置解析及source AST通过，现有底盘clip允许0.5；未训练/仿真。见决策D011。B01三个待决项目为轻中重覆盖及比例、有无闭门器、温和门轴摩擦；建议仅在baseline TODO，未批准或实施。

2026-09-18 11:48 HKT：Owner确认B06当前init/reset setup PASS（D008）；side window已改时限30s与stage `[525,150,150,150,150,300]`，dt=.02s、时间结转保留（D009）。Owner授权的B07已实施：door-local法向1.2–4.0m、横移±.5m，yaw在闭门握杆中心bearing±10°与门法向±35°的交集均匀采样；初始化缓存源USD的grasp_target相对door位置，避免先robot后door reset读上轮handle姿态。自然Stage0与natural eval使用新范围，staged/显式state恢复不变，不新增Student目标真值。B06/B07在TODO已PASS，B01–B05未决；远距0.5m/s仍建议，当前0.3不变。新改动证据为[配置解析及CPU采样](../../../scriptsFORhuman/v29/implementation_evidence/init_range_20260918/README.md)，旧one-batch不作为新范围runtime证据；未启动训练或render。

2026-09-18 10:41 HKT：Owner已回传Pro ZIP，原包/12份原文保存在[本次独立归档](../../../scriptsFORhuman/pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/README.md)；V29-D007记录只读解析范围。单位换算/条件饱和推导、代理latch与曲杆grasp frame已对照source；Pro相机投影实际为env1，与此前env0不同，安装三条连线各自成立；release字段需区分逻辑gate、身体力窗口及gate且失去双指同时接触的回位窗口。512条既有记录核心计数相符，未重算完整trace/重新运行。24来源、70行参数的事实/推算/工程初值/未知分列，六项保持未决；v28科学结论和render豁免不变。详细依据只从[本地核对](../../../scriptsFORhuman/pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/LOCAL_RECONCILIATION.md)与baseline TODO读取。

2026-09-18交付历史：V29-D006授权的专用review分支已push并验证远端一致，三个ZIP及三个索引文件已上传Drive并读回核对。[原交付入口与prompt](../../../scriptsFORhuman/v29/pro_handoff/20260918/README.md)保留，不回写云端原文。

2026-09-17 21:13 HKT：Owner 已确定 v29 总体方向与八卡分工：push baseline GPU0/1、pull同步GPU4/5各2 seed，N01 GPU2、N02 GPU3，GPU6动态、GPU7监控/eval等。N01/N02待baseline落地后进入独立branch/worktree；当前先研究并逐项讨论六项baseline议题。canonical入口为[总体安排](../../../scriptsFORhuman/v29/a2_piper_base_v29_overall_arrangement.md)与[baseline TODO](../../../scriptsFORhuman/v29/a2_piper_base_v29_baseline_TODO.md)，Owner确认整体clean后才落地正式baseline文档；未启动实验或创建worktree。

2026-09-17 21:22 HKT：三路只读研究已将六项初步事实/建议写入上述TODO，均待Owner确认。当前mass/hinge drive仍有随机化、native hinge friction关闭；generator已有50%末端回钩。相机旧表的21.22°由当前资产配旧j5=−0.415精确复现，当前j5=−0.52为15.206°，均相对trunk；两者非光学定义冲突。base仰角20–25°仅为基于历史有效render姿态的静态投影候选，不是已批准配置或v29成像通过。详细source和计算限定只从TODO读取。

2026-09-17（HKT），按 Owner“直接改，然后将基础改动记录”完成三项基础实现。canonical 决定与参数见 [V29-D001–D003](../../../scriptsFORhuman/v29/a2_piper_base_v29_decision_log.md)。

- Stage5 goal 保持 `[2,0,0.5]`；新增 goal heading 平方误差 scale=-4 与实际 roll/pitch 平方误差 scale=-8，后者和原 -2 合计 -10。新项仅在 Stage5 生效，不随 K 衰减；完成条件仍为 root_x>1.5。
- v29 bilateral uniform handle 高度为0.90–1.20m；natural eval 从 checkpoint 相邻 config 继承。v26 selector 不走另一路 linspace 的1.10m默认上限，且继续拒绝 v26+linspace 组合。
- MERGED腕机物理/光学180mm/45°，arm init/reset=`[0,.10,-.10,0,-.52,1.57]`；新资产几何核对默认光轴pitch=-15.206°。rig只有base_left/base_right/wrist三台相机；三台外壳visual隐藏、collision保留，支架可见。Owner追加要求后，旧中央包络的visual/collision/rig几何已完整删除；中央盒原先没有质量/惯量贡献，trunk保留原机身+三固定安装件合并的20.404808kg。

初版64-env/1-batch PPO在GPU4完成，exit0、step1、4096timesteps；中央碰撞包络删除后又按同规模复核最终资产。最新证据见 [运行读数](../../../scriptsFORhuman/v29/runtime_logs/baseline_no_center_smoke_20260917/runtime_readout.json)和[资产/配置核对](../../../scriptsFORhuman/v29/asset_and_config_verification_20260917.json)。接线运行未证明Stage5姿态改善、高把手成功率或成像质量；headless renderer有GPU Foundation初始化错误，未计为渲染通过。

v28已关闭，结论不回写。v29完整方案/正式预算随后制定；common继承的6000-batch默认值不是已启动预算。N01/N02已获Owner明确阶段归属决定，实施时机与研究证据边界见上述当前入口。
