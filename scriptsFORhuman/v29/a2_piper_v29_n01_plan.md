# v29 N01 plan — 局部失抓恢复与 Teacher→Student 传递

版本：**1.2 — 合力平面 / 双GPU对照 / 当前worker交接版**，2026-09-21 HKT。负责人：N01 planner。状态：**高层Teacher保持scratch；方向扩为退出一侧的X–Z连续合力，GPU2/3并行安排两组Teacher。独立v28诊断已证明强档可以破坏握持，减半明显温和；完整N01方法尚未实施，Teacher/Student能力尚未证明。**

工作目录：`/home/baoquanc/workspace/DoorDog-A2_Piper_v29_n01`；分支：`codex/v29-n01`。环境/source底座为完整 C002，保留 B05，参考 tag `v29-c002-baseline`；**高层Teacher不加载C002训练权重**。分支直接来自主线，当前 C002 文件已作为未提交内容带入；Pro 审阅分支和 GPU1 消融均不作方法底座。

本文件是 N01 的当前计划入口。[Owner逐点决定](../novelty/conversations/20260920_codex_n01_plan_decisions.md)优先于[此前最小设计](../novelty/documents/20260920_n01_minimal_recovery_transfer_design.md)；旧文中的开爪 command pulse 不再是首轮课程。Pro 原件保留为研究来源，不回写为 Owner 决定。

## 1. 职责与已定决定

Owner于2026-09-21追加[设计风格偏好](../novelty/conversations/20260921_codex_n01_pro_upload_and_design_preference.md)：**效果优先；简单、高效、避免过于复杂的状态机是偏好，可以为必要效果让步。** “primitive”不要求特定动作原语或分层架构。该偏好交给Pro独立权衡，不自动增加状态/技能，也不为了形式上的简单削弱能力。

**本任务负责N01计划、定向研究与文档，不承担完整方法的code implementation或训练监督。** Owner于2026-09-21 14:05另行明确要求一次v28真实外力quick test，并在保留对照时授权物理GPU2/3；本轮独立诊断的脚本、必要修复和有界运行按该新授权完成。下文的完整方法实施与正式训练仍交给独立执行team；其他baseline任务的权限不转移。

| 编号 | Owner决定 | 本计划的落实 |
|---|---|---|
| N01-D001 | 首轮只做局部 L0＋L1；L2/L3按明确阻断再扩；D023不变 | 当前站位内重新闭合或回到实时pregrasp；不预建base重定位/重观察技能。强回弹后重新伸臂重抓把手仍归N02 |
| N01-D002 | 首轮以掌部/末端外力造成局部滑脱，之后单独加入门侧扰动；保持策略命令，固定短时程，不保证失抓 | 新增真实外力课程的计划；不以开爪覆盖、撑手指、改速度/位置或持续推到失抓代替 |
| N01-D003 | Teacher两臂与Student共享stage-blind接口；Teacher适应后直接12D监督 | 名义Teacher与受扰Teacher共用执行语义，冻结合格Teacher后直接BC；不先增加旧Teacher的effective-increment转换 |
| N01-D004 | finalize计划并交给worker team；授权GPU2，额外GPU另行申请 | 本版固定首轮默认值、实施顺序及有界运行规模；执行team自行完成常规解析/校准，不把工程细节重新列为Owner路线选择 |
| N01-D005 | Owner要求实际把手上的施力方向可视化，并提出N01从头训练 | 本轮采用高层Teacher scratch：T_nom/T_force同一随机初始化、独立训练；保留冻结A2_Base。移除v1.0的C002初始化与T_shared适应阶段 |
| N01-D006 | Owner提出退出与沿柄合力、询问对照必要性并授权GPU2/3并行，明确要求v28真实外力quick test及依结果调整剂量 | 采用连续方向角与总力幅值；保留课程对照，GPU2=T_force、GPU3=T_nom；独立v28诊断不向scratch训练传入模型或数据 |

Owner另明确：`apply_rigid_body_force_at_pos_tensor` 是空实现；外力必须进入实际物理步进路径，可逐step施加以形成连续force。参考项目随后由Owner纠正为 **GuidePup**；LMP不作为当前方案依据。第3节据此细化。

[本轮finalize与GPU2授权](../novelty/conversations/20260921_codex_n01_finalize_and_gpu2.md)要求把计划交给worker执行。以下的具体取值与取舍由planner收敛为**当前实施默认值**，不逐项冒称Owner原话。退出40–100 N、沿把手25–60 N、0.2–0.5s的[离线依据](../novelty/documents/20260921_n01_force_amplitude_duration_window.md)保持有效，但数值仍需首个物理片段校准；它们不等于实测滑脱阈值。[scratch修订与方向说明](../novelty/documents/20260921_n01_scratch_and_force_directions.md)取代v1.0 warm-start安排。执行入口见[worker handoff](a2_piper_v29_n01_worker_handoff.md)，实际能力未知及扩展边界见第6/9节。

## 2. 首轮要形成的能力

目标链条是：**原任务中真实抓稳 → 预定短外力脉冲 → 保持握持或发生局部滑脱 → 策略自行完成L0/L1 → 同一episode继续原任务。** 外力期间策略也正常闭环工作，不冻结动作等到撤力才让策略响应。

| 状态 | 行为/结果口径 |
|---|---|
| 抗扰期间仍握住 | 记抗扰保持；能继续完成任务就是有价值的结果，不强迫制造loss |
| 已真实失抓、把手仍在捕获域 | L0：保持可行arm/base条件并重新闭合，建立本次新的握持资格 |
| 把手已离开捕获域、当前站位仍可达 | L1：卸载错误接触、到实时pregrasp再闭合；门持续运动，不能回到失抓前的静态目标 |
| 已失抓但可以继续通过 | 允许名义通过后缀；单列 `loss_then_pass`，不记为重抓能力 |
| 需要有意base重定位或恢复视野 | 记超出本轮局部能力范围或未知；只有它成为明确阻断，才讨论L2/L3 |
| 正常释放、空抓、单帧接触闪断 | 分别保留正常release、capture failure和短闪断，不能混作真实失抓 |

实际base可能受末端力传递而移动；L0/L1范围不意味着物理锁住base。稳定姿态与小幅平衡响应可以存在，新增的有意重新站位能力不在首轮承诺内。局部范围外的事件仍计入扰动分配总体结果，不能在事后删除。

握持资格先复用 C002 的5 control tick挤压口径并结合把手相对几何；这是训练/计分操作定义，不是力闭合证明。真实失抓须有过去的有效握持、当前约束持续受损及相对滑出/脱离等证据；**没有开爪命令也可以真实滑脱，夹爪保持闭合命令也不能证明仍握住。** 新握持不能继承失抓前的接触streak。

当前 release latch 只记录曾达到释放资格，不等于实际松手。课程窗口为**本次真实grasp完成后、正常release开始前，且当前仍需把手控门**；正常释放须结合实际释放意图、物理握持变化及任务条件，不能用latch一项代替。首次校准优先早期稳定握持，门已运动仍在控门的情况随后单列。达到释放资格后若仍真实握持且需要控门，不只因latch=true就排除；这替代v0.1将整个课程限在release资格出现前的保守提案，不改变D023的释放后强回弹边界。

## 3. 末端外力课程合同

### 3.1 受力刚体与施力点

当前 v29 robot 配置的 `end_effector_name` 是 **`arm_body6_to_gripper`**；URDF中它是夹爪掌部，两个手指另为 `arm_body7/arm_body8`。计划以运行时 Articulation 的 body name 绑定这个刚体，不复用旧 `right_palm_index`，也不向两手指分别施力。

首轮作用于该刚体的**质心**，不附加纯扭矩，也不额外选择虚拟TCP或指尖施力点。这样先固定一个空间条件，减少力臂与纯扭矩的混杂。末端力仍会通过关节、接触和支撑传递到arm/base，不能解释为“只改变手的位置”。未来若要改为偏心作用点，须单独明确附加力矩，不能默默变更。

### 3.2 退出与沿柄合力，使用当前G定义

在脉冲开始的真实时刻 `t0`，从已有 FrameTransformer 取得 `p_G(t0)`、`p_pre(t0)` 和 G 的世界旋转 `R_G(t0)`：

| 方向 | 定义 | 当前C002坐标含义 |
|---|---|---|
| 退出 | `d_exit = (p_pre - p_G) / ||p_pre - p_G||` | v29 pregrasp offset为G局部 `(0,0,-0.10)`，因此对应 `−Z_G` |
| 把手一侧 | `d_side+ = R_G · (1,0,0)` | G的X轴沿抓取点处把手中心线切向 |
| 把手另一侧 | `d_side− = −d_side+` | 与上一方向相反，不是另一个任意三维方向 |

这里把Owner的“把手局部左右”具体化为沿把手切线的 `±X_G`，不是世界左右，也不是撑开两指的方向。B05和左右门已有G朝向，不能再套一次door-side符号而重复镜像。

v1.2采用Owner提出的斜向合成：`d(θ)=sin(θ)·X_G−cos(θ)·Z_G`，`θ∈[−90°,90°]`，因此`||d||=1`。0°为退出，±90°为沿柄两侧，±45°同时包含退出与沿柄分量。连续角度和非零幅值形成有限的力向量覆盖面；它不是末端实际运动轨迹，也不包含`+Z_G`或`±Y_G`。

幅值`A`始终表示合力模长：`F=A·d(θ)`。例如A=85 N、θ=45°时，两个分量各约60.1 N；若把100 N退出与60 N沿柄直接相加，合力是116.6 N，不能仍标成100 N。[可视化数据来源](../novelty/documents/20260921_n01_force_visual_geometry.json)沿用C002实际B05七族与夹爪STL；G对齐姿态仍为示意，不是运行观测。

**首轮在t0算好世界方向，并在这次短脉冲内保持不变。** 取的是触发时实时pregrasp，不是关门初始目标；同时避免力向量在脉冲中随滑脱闭环追踪目标。未来若选择随G旋转的方向，那是另一种扰动协议，应单列。实时pregrasp仍持续更新供恢复任务使用，不因冻结本次外力方向而冻结恢复目标。

### 3.3 简单抽样与预定时程

首轮方向角均匀抽样`θ~Uniform(−90°,90°)`；每次脉冲只抽一次方向、总幅值和持续时间。矩形短脉冲已经足够，不先增加任意三维力、随机扭矩、复杂波形或自适应追逐失抓：

`F_world(j) = A · d_world,  j = 0…K−1`；之后N01外力贡献为零。

- 轴向范围保持退出40–100 N、沿柄25–60 N；连续角度对**总幅值范围**作线性插值：`u=|θ|/90°`，`A_min=40−15u`、`A_max=100−40u`，`A~Uniform(A_min,A_max) N`。因此±45°为32.5–80 N。插值只是接续两个轴向范围的首轮抽样规则，不是物理阈值模型；不把两个分量的上限独立叠加。
- 持续时间0.2–0.5s：当前200Hz下均匀抽整数 `K=40…100` physics step，实际持续 `K·dt_physics`，与方向内幅值独立抽样。记录实际秒数，不把control tick误当physics tick。
- 本次新的5 control tick握持资格成立、仍需控门且正常释放尚未开始时，随机等待0–15 control tick（当前0–0.3s）；到时资格仍成立才触发。等待中窗口消失则取消本次计划，记录未施加，不不断重抽直到成功注入。
- 第一版每episode最多一次计划脉冲，便于解释；自然失败照常发生，策略的恢复尝试不因此限为一次。
- 上述力幅/时长/等待值由实际物理片段校准；训练时T_force与Student均按episode独立分配50%名义、50%计划扰动，T_nom为全名义。分配与左右门/B05族独立；分配到扰动但未进入窗口的episode照常保留。功能校准和受扰评估可设100%计划扰动以观察实效，仍不保证实际注入或loss。

数值依据：当前手指是prismatic，kp=1300 N/m、kd=32 N·s/m、drive cap=45 N/指；默认指–把手组合估计μs=0.8、μd=0.7。以每指距闭合target 14mm为未实测示例，静摩擦容量约29 N；当前URDF的5个合成可达姿态显示退出方向比沿把手方向更硬。计入示例20–40mm位移与0.1m/s速度后，力幅约为退出40–115 N、沿把手34–52 N，作为上述初始范围的量级依据。它不包含真实预载、base/门运动或策略target更新，也没有证明20–40mm就是脱离距离。详见[独立估算](../novelty/documents/20260921_n01_force_amplitude_duration_window.md)和[完整计算数据](../novelty/documents/20260921_n01_force_estimate.json)。

新增[v28实际诊断](../novelty/documents/20260921_n01_force_probe_readout.md)：固定0.35s，强档为退出100 N、沿柄60 N、±45°总力85 N；非零11/12到窗，其中8个在t0+0.55s内持续双指脱离，11个满足较宽约束失效。各方向减半后同样11/12到窗，持续脱离0/11、宽口径1/11；两轮各4个0 N对照均无短窗事件。全部触发均70次连续真实physics请求。强档无需扩大，低档允许抗扰保持；这不是每个中间幅值/角度或0.2–0.5s全时程的阈值验证，更不是B05结论。

其中−X_G方向仅有较弱约束失效，尚未观测完整脱离；独立0 N视频案例也能出现宽口径loss，故该读数不单独证明扰动造成失抓。8 env补录已取得真实100 N退出脱离短片，所有本轮诊断进程已结束。

0.5s作为首轮长档；1–2s留给后续独立的持续外力条件。2s相当于100次策略更新，可能在失抓后继续拖动arm/base，或者改变为持续载荷下恢复。低于静摩擦阈值时延长时间也不必然脱手，因此不能用更长时程代替对力幅和几何的解释。

**外力不按是否失抓续长、增力或提前撤除。** 若中途滑脱，仍按原定短时程结束；若始终抓住，就记录保持握持。真实episode done会结束该episode的剩余脉冲，不能把残余外力施到reset后的新episode。

这项取消/结束语义属于扰动定义，不是为了获得有利结果的救援器。若脉冲中进入正常释放、任务终止或非局部状态，分别保留实际发生顺序；不能重贴标签成干净局部恢复。

### 3.4 每个physics step写入，接入真实步进

当前配置入口是200Hz物理步、control decimation=4：`dt_physics=0.005s`，`dt_control=0.02s`。实施时以实际resolved值为准。一个持续若干control tick的外力必须覆盖期间的**每个physics step**，不能只在每次actor forward时写一次瞬时力。

本机IsaacLab源码提供 `robot.instantaneous_wrench_composer.add_forces_and_torques(...)`。计划使用世界力、单个掌部body、`positions=None`，在每个真实physics step的写出前添加本步力：

```text
本control tick：Teacher/Student正常产生与执行高层命令
  每个physics step：
    原有actuator/关节控制路径照常
    若当前在预定pulse时程内，向掌部添加本步world force
    scene.write_data_to_sim()
    sim.step(render=False)
    scene.update(dt_physics)
  读取实际运动/接触，供下一control tick与事件计分使用
```

本机 instantaneous composer 在 `write_data_to_sim()` 后清空，所以脉冲期间要逐物理步重写；脉冲结束后停止添加即可。外力请求没有额外乘 `dt` 再当force传入；仿真自己积分。矩形脉冲的请求冲量为 `J=A·K·dt_physics`，它是施加量记录，不是保证末端产生某个速度变化的公式。

最小接点是现有 `_apply_force_in_physics_step()` 调用链，位于 simulator 的 `scene.write_data_to_sim()` 之前。不给空的 `apply_rigid_body_force_at_pos_tensor` 传一个非零tensor便宣布有外力，也不要求先实现完整通用force-at-position包装器。只接N01所需的单刚体、质心、世界力路径。

请求tensor为 `(选中env数,1,3)` 浮点数，采用robot实际buffer dtype/device；本机composer初始化为float32。body/env索引与实际Articulation一致。显式N01 torque为零；不覆盖其他已存在的物理作用。pulse计数随真实物理步推进，reset时只结束对应env的剩余时程；Teacher/Student hidden仍只按真实done清零。

接点来自本机源码和[IsaacLab官方Articulation写出实现](https://isaac-sim.github.io/IsaacLab/main/_modules/isaaclab/assets/articulation/articulation.html#Articulation.write_data_to_sim)。本轮独立v28诊断已实际走通该原生方法及逐步施力/撤力，并保存接触和运动响应；完整N01生产路径仍待实施。本机IsaacLab元数据为0.54.4、editable源为 `/home/baoquanc/workspace/IsaacLab/source/isaaclab`，IsaacSim元数据为5.1.0.0，不能只凭仓库旧版本文本判断API。执行team仍须展示C002+B05上的首个真实功能片段。

### 3.5 实效分类与最小记录

事件记录从计划分配到最终任务结果连续，第一版只需要足以解释这条链的信息：

| 层次 | 最小记录 |
|---|---|
| 计划与实际施力 | episode/门实例、接管来源、方向ID及t0世界向量、请求幅值、计划/实际起止physics step、作用body、实际持续时间/冲量；取消原因 |
| 物理响应 | 掌部/TCP与把手的相对位置和运动、夹爪实际q、已有挤压/接触、base响应；外力前后的门角和门运动 |
| 结果 | 仍握持、真实滑脱、局部可恢复候选/超范围/未知；L0/L1、新握持与原任务结果，超时和Teacher接管单列 |

施力有效不等于一定有明显位移；接触/控制可能抵消运动而改变约束力。相反，门或base动了也不等于真实失抓。不能只看force命令、单帧both_contact或stage变化判断成功。

脉冲内短暂重新接触可记下，但稳定恢复要看撤力后的新握持与原任务后缀。抗扰保持不制造新的hold事件；不能把撤力本身当作失抓后重新握持。

即使力施在末端，也可能经原握持把门带得更开。记录门角/运动变化和直接续行分支；只有完成率上升而没有真实loss及其恢复证据，不能说已学会失抓恢复。后续门板力/门轴力矩的直接助推更强，必须独立课程和结果表，不与首轮末端力混为一种剂量。

### 3.6 GuidePup参考：控制步更新命令，物理步重复施力

Owner已纠正参考项目为 **GuidePup**。只读子agent定位、planner核读的直接案例是：

| 参考入口 | 已读的具体做法 | N01取舍 |
|---|---|---|
| [ApplyForceCommandAction](/home/baoquanc/workspace/GuidePup/source/LMP/acc/tasks/manager_based/uniFP_aliengo/mdp/actions.py:404)及[配置接线](/home/baoquanc/workspace/GuidePup/source/LMP/acc/tasks/manager_based/uniFP_aliengo/unifpaliengo_env_cfg.py:393) | ActionTerm读取3D force command，扩为 `(N,1,3)`，零torque，调用原生 `set_external_force_and_torque`；配置receiver为 `base_link`，world frame，省略位置参数 | 借鉴独立物理外力通路；N01 receiver使用已核实的掌部body，首轮CoM纯力 |
| 同ActionTerm的 `dim=0` 及本机ManagerBasedEnv的decimation循环 | 不占actor动作维度；每physics step执行apply_action，再scene.write_data_to_sim、sim.step | N01仍为12D高层动作，不把force拼入动作；利用DoorDog已有physics hook，不为此迁移到manager-based环境 |
| [reverse_push_eval的有限脉冲](/home/baoquanc/workspace/GuidePup/scripts/experiments/uniFP_aliengo/reverse_push_eval.py:406) | 每env step先clear_force，再对预定时程内的env设力，策略照常推理和env.step；每次env.step内部的所有physics step重复施加当前力 | 这条有限时程模式最贴近首轮；触发条件从其base运动条件改为N01真实握持窗口，方向/幅值/时长另定 |
| [VariableForceCommand](/home/baoquanc/workspace/GuidePup/source/LMP/acc/tasks/manager_based/uniFP_aliengo/commands/force_command.py:62) | env step层更新间隔、ramp-up、hold、ramp-down，结束清零command/target；reset重采样也清状态 | 只借鉴时程管理与施加分离；首轮采用更简单的预定短矩形pulse，不照搬其三维随机力、时长或课程 |

GuidePup基础 `force_range=(0,0)`，另有[force range curriculum](/home/baoquanc/workspace/GuidePup/source/LMP/acc/tasks/manager_based/uniFP_aliengo/unifpaliengo_env_cfg.py:680)切到非零范围，评估脚本也可手动set_force。因此证据是“配置与调用链已接通”，不是默认所有episode都有非零外力，更不是本次运行验证。

**撤力语义须随API明确。** GuidePup使用的旧setter在本机IsaacLab中转发permanent composer；其clear_force先将command归零，再由下一轮apply_actions写入零力。N01使用instantaneous composer逐physics step添加，写出后自动清空，脉冲结束不再添加即可；不能将“停止调用”套到会保留上次力的permanent接口上。

已接线案例的receiver是base，不是末端/夹爪。未把未接线的通用 `VariableForceAction` 当作已验证末端案例，也不复制GuidePup的刚体编号、力值、force观察或估计网络。N01保持Student81D＋RGB，force计划参数不额外进入Teacher/Student actor。GuidePup能支持施力结构的借鉴，不能证明C002会滑脱、能局部恢复或能传给Student。

## 4. 共同执行、Teacher与Student合同

### 4.1 动作和时序

发布现状补充：当前工作树已移除Stage0 arm delta强制覆盖；这是本次打包前已有的源码变化。下列合同中的对应删除项已有部分落地，其他执行路径与完整恢复图仍待实现；以本次Pro输入的当前源码事实表为准。

- 所有N01 Teacher与Student使用同一stage-blind增量执行路径：`base5 + arm_delta6 + gripper1 = 12D`。由实际选中命令驱动冻结A2_Base产生leg12，组成环境24D。删除N01路径的Stage0 arm target覆盖，关闭Stage3 rebase、zero_vel/zero_finger以及其他stage驱动的命令覆盖；保持C002 canonicalization关闭。沿用现有动作尺度、关节target限位及真实reset初始化。
- `actions19 = leg12 + 累计arm target6 + gripper1`，另有`delta_actions6`；继续记录实际公开命令，不能用外力伪造命令或历史。外力只在物理层逐步添加。恢复、控制权交接或rollout边界均不清arm累计量、腿历史或任一RNN hidden。
- Teacher可以使用原133D特权观察和当前训练目标；Student只有81D＋RGB。pulse计划、方向、幅值、剩余时间和新恢复标签都不新增到actor输入。真值目标只组织Teacher训练、奖励与计分，不能绕过Student给arm/base/gripper写动作。
- 每个control tick，Teacher与Student各消费同一条实际历史的一帧，各推进一次自身hidden；Teacher标签是当前12D输出。选择真正执行者后再派生腿动作，执行物理步。新物理事件和新目标在相应下一帧Teacher观察构建前生效，避免同一标签使用不同目标上下文；终端事件在auto-reset前保存。
- hidden只按真实done清零。保留现有8 tick Student rollout与保存边界hidden的训练近似；首轮不增加prefix replay、burn-in、通用事件库或多技能网络。事件身份和最终结果必须跨rollout连续。

### 4.2 高层Teacher从头训练与资格

**本版取消C002 checkpoint warm-start，也取消T_shared共同名义适应。** T_nom与T_force从同一个随机初始actor/critic开始，各自完整训练。两臂模型初始化seed固定为291，RMS、optimizer、scheduler、训练计数、环境课程和RNN均从各自初始状态开始；不继承C002的actor、critic、RMS或经验。配置显式`checkpoint=null`、`auto_load_latest=false`、`enable_staged_reset=false`，旧恢复bank保持关闭。

同一随机初始化可用固定模型构建seed实现，或记录明确未训练的N01 update0初始状态；它不是训练过的高层checkpoint。额外的pulse随机数流与门域采样分开，不让是否创建扰动调度器改变模型初始权重。干预发生后物理轨迹与reset时刻会分化，不能声称相同seed保证全程逐状态配对。

“从头”指高层开门/恢复Teacher。既有冻结A2_Base腿部运动策略继续使用，动作仍为高层12D＋腿部12D；重新训练腿部运动不在N01范围。C002＋B05继续提供共同物理域，N01共同控制/目标/奖励/计时变化在两臂一致。

T_nom从开始为无外力课程；T_force从update0起按episode分配50%名义/50%计划扰动，只有真实握持资格成立后才注入力。早期尚不会抓握时自然没有实际pulse，不另设“先训会再fork”的阶段，不凑足失抓数、不给受扰臂补训练量；到窗数量本身是结果。

采用scratch的理由是：从一开始就在新stage-blind执行语义下学习，并直接比较两种完整课程。v1.0 warm-start有利于较早得到交互样本，但研究对象包含旧策略适应；不是N01方法的必要前提。C002既存[step6000最终readout](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md)为0/64自然完整成功，只作历史参考，不能直接作为合格蒸馏Teacher。

P1若需要尽快获得真实握持校准外力，可以在**单列的工具诊断run**中使用已有C002策略；该run的权重、RMS、optimizer和轨迹不进入两条scratch训练臂，也不计入N01从头学习的结果。没有可用握持就报告当前功能证据边界，不捏造已施力/失抓。恢复训练始终由两个新Teacher自行形成能力。

Teacher资格依据真实后缀：分别报告名义完成、受扰保持、L0/L1新握持后完成、直接续行和失败。只做到了左侧或L0，就如实限制标签/结论范围；不能把右侧或L1的finite标签当作能力证明。首轮若没有合格恢复后缀，交付Teacher能力缺口，不能静默切回C002旧专家进入Student。最终由新训练、合格的T_force提供Student监督。

### 4.3 Student输入和优化默认值

首轮固定**现有A2 Student单路trunk/ego_camera仿真输入**。这是已存在的可接线camera contract；v29 asset的base_left/base_right/wrist三路rig不自动成为Student三路输入，也不在首轮改变光学方案。

| 项目 | 当前默认 |
|---|---|
| 标量观察 | 81D，沿用`door_open_a2_base_dagger.yaml`顺序：3+3+20+20+19+6+5+5；Teacher133D、可选critic138D、冻结A2_Base1620D分开 |
| RGB | 一台`trunk/ego_camera`，216×384×3，NHWC；沿用A2 dagger recipe的pose、optics、clip与ImageNet归一化 |
| 帧时序 | physics 200Hz、control 50Hz；camera update_period=0.0，每次actor读取最近一次已经render/update的真实帧，不推进额外物理步，不填假帧 |
| 比较一致性 | 训练与定量评估保持同一216×384 actor输入；720×1280仅用于独立展示，不改变推理观察分布 |
| 模型/损失 | 沿用现有A2 vision＋LSTM actor；纯12D BC，`distill_only=true`，L2、系数1、LR=1e-4、每轮1 epoch/4 minibatch；不加入Student PPO/RL |
| 记忆 | rollout=8 control tick，hidden跨rollout/恢复连续，只有真实done重置 |

N01 Student配方从C002物理/env/reward底座组合，再加入A2 Student的网络/观察/相机；不能让旧dagger的robot、solver velocity=1、target覆盖或reset选项覆盖回C002。实际Actor RGB覆盖、帧龄和观察shape由首个功能片段展示；本plan没有虚构已完成的Student runtime或硬件相机标定。

Student从自身模型初始化开始，由新训练的T_force示范启动；这不是加载v29 baseline的高层策略。随后从相同Student起点比较`S_demo`与`S_online`：前者Teacher执行，后者`enforce_teacher_rollout=false`且Teacher执行比例0，Teacher只shadow。配对采集/query与优化量相同，实际状态/失抓数量作为结果。第一版不使用按env固定前缀的混合Teacher/Student cohort。

Teacher示范的恢复监督使用实际合格后缀；在线shadow在Teacher已展示能力的局部范围内训练，明确的超范围/未知样本保留记录并排除BC。首轮不训练额外置信度模型，也不以标签finite代替资格。若Student状态上的Teacher本身不会恢复，先归入Teacher问题。Teacher前缀后交接只作局部诊断；自然起点全Student、前缀交接、失败后接管分别报告。

Teacher交付给Student的描述只需绑定实际checkpoint路径、resolved config、state_dict key、观察/动作/机器人语义和已有资格记录。现有`validate_a2_teacher_checkpoint.py`强制摘要字段，与Owner“不写hash/SHA256”的要求不符；worker在本工作树简化这一直接加载合同，去掉摘要生成/必填依赖，保留必要语义核对与strict state_dict加载。不生成旧格式再加兼容层，也不为本次交接创建Git提交。

## 5. 恢复目标、计时与奖励

### 5.1 目标路由

首轮只用单actor和局部L0/L1。当前目标`goal_stage`可复用`stage_buf`表达；另用单调的`budget_stage/highwater`保存首次取得的前进进度，优先复用现有`current_max_stage_buf`。批量stage/计时字段为robot device上的`(N,) int64`，资格/事件mask为`(N,) bool`。不要建立第二套通用任务框架。

| 当前物理事实 | 下一目标 |
|---|---|
| 无确认loss、尚未正常release | 沿C002名义操作；外力期间也继续闭环 |
| 已确认loss，把手仍在可闭合捕获域且姿态相容 | L0，目标为重新闭合/新握持（对应Stage2语义） |
| 已确认loss，已离开捕获域且仍需控门 | L1，目标为实时pregrasp（Stage1语义）；达到当前pregrasp条件后进入L0/Stage2 |
| 新握持连续成立 | 门仍近关闭/需要重新解锁时回Stage3，否则按当前门状态回Stage4；不强制重复已经完成的压柄 |
| 已失抓但当前已经允许正常通过 | 沿名义Stage4/5后缀，记loss_then_pass；不为计恢复数强制重抓 |
| 正常release后强回弹，或明确要新增有意base重定位/重新观察技能 | 不引入新恢复边；保留结果，后续按D023/N02或L2/L3范围处理 |

握持建立沿用C002 5 control tick资格并结合当前把手几何。loss的初始确认窗为3 control tick：过去有合格握持、当前双指挤压约束持续失效，并有相对滑出/脱离或实际开口变化证据，且不是允许的正常释放；单帧接触闪断不算。捕获/滑移几何先用当前B05与既有close gate定义，worker从首个实际片段确定对应几何量和阈值并记录，不能凭门角或单一contact flag宣布loss。

3 tick期间策略照常执行，仍计任务时间；确认后只废止失效的当前hold资格/streak。原`_a2_stage3_grasp_streak_highwater`若被用于当前hold资格，须与“曾经握持”和预算进度分开，不能让旧hold资格自动认可新握持。历史任务进展、handle creation高水位和过去正常release记录保留。超局部范围不新增脚本救援，也不因标签变为unknown就自动reset；仍按原任务done/超时结束。

第一次校准集中首次稳定握持后的早期窗口，不据此宣称已覆盖整段pre-release时域。门已经运动仍需控门的情况按同一合同单列后续校准；普通的幅值/几何阈值调整由worker依据实际结果完成，比较运行前固定分布，不逐个参数请Owner猜值。

### 5.2 时间合同

保留C002的30s物理episode上限、`[525,150,150,150,150,300]` control tick阶段信用及`>=`超时比较。恢复不调用reset/restore、不清门速度、不改q/qdot/root、不返还时间。

- 首次真实前进到从未到过的阶段，沿用C002一次性的余额结转和该advance tick的原记账；单调budget_stage向前一次。
- 回退、重抓、回到曾到过的阶段均作为普通control tick消耗预算，不结转、不重获阶段信用、不重得免费advance tick。
- `time_in_stage_buf`和超时索引按budget_stage记账，不能因为目标退到Stage1而套用Stage1的新预算。total/episode计数继续增长。`actual_time_in_stage`用于原前进阶段计时，恢复耗时另用事件时刻计算，不覆盖预算计数。
- transition/新进展奖励只对应首次真实前进；回到旧目标不重新触发。目标更新与时间更新各执行一次，不同时运行旧单调stage callback再补一次N01更新。

这保持名义首次前进的时间语义，只消除恢复循环重复取得信用的路径；不新增时间补偿常数或shadow模拟器。

### 5.3 最小奖励变化

| 部分 | N01处理 |
|---|---|
| stage dense reward | 保留C002逐tick形态、原尺度及`accumulate_stage_reward=false`；按当前目标和当前物理条件发放，不把预算高水位直接换成持续高阶段收入 |
| L1获取 | 复用live pregrasp距离、朝向、开爪与稳定条件；恢复Stage1不再调用要求默认arm的Stage0站位条件 |
| L0闭合 | 复用当前close gate、闭合进度/命令与挤压/新streak奖励；不能继承失抓前hold资格 |
| Stage1/2 forward-creep | 只在L0/L1恢复目标期间停用基于初次站位带的位置惩罚；保留实际base稳定、碰撞、姿态和关节代价，不新增有意base重定位奖励 |
| 再次压柄/操门 | 依据当前门状态选操作目标；需要重新压柄时不同时发dont_push_door_handle回升奖励；handle creation高水位不清零、不刷重复创建收入 |
| 通行收臂 | L0/L1目标不发通行收臂奖励；返回名义操门/通过后恢复C002 release-gated arm return与Stage5语义 |
| 外力/事件 | 不新增“受扰、失抓、重抓”固定奖金；抗扰保持并完成可以优于先失抓再恢复 |

以上动作、目标、奖励和记账变化在T_nom/T_force/所有Student之间完全共享，只有课程/执行者不同。参数尺度优先沿用C002；只对功能片段暴露的实际冲突作窄修正，不扩成全局奖励重设计。

## 6. 首轮工作顺序、资源与运行上限

**物理GPU2/3均已获Owner授权供N01使用。** 正式Teacher配对安排GPU2=T_force、GPU3=T_nom，各有独立命名tmux、receipt与输出；不占用GPU0/1、不接管其他任务。本次v28 quick test先使用GPU2，GPU3暂未启动进程。

v1.2仍需要T_nom：两个Teacher共享scratch起点、stage-blind执行、恢复目标/奖励和预算，仅外力课程不同，才能区分课程作用与重新训练/共同环境改动。旧C002或v28 checkpoint不能替代这组对照。

以下是本版的首轮有界执行规模，不是保证收敛的训练量。worker接手后可以直接落实配置、操作路径和运行receipt；实际入口仍用现有train/eval/TRL，不把本plan里尚未存在的N01 overlay当作已经能运行的命令。

| 顺序 | 工作与默认规模 | 交付/结束点 |
|---|---|---|
| P1＋P2 功能实现 | 先共同执行、外力、loss/L0/L1与计时奖励；16 env、最多64个自然episode的首轮片段，允许必要的少量PPO/BC更新用于展示真实学习通路 | 显示实际逐步施力/撤力、公开命令、接触/相对运动、连续时间/hidden与原任务后缀。当前权重做不到恢复则如实显示；不为了等成功无限重复 |
| P3 Teacher scratch配对 | 同一随机actor/critic初始化，各4096 env×64 tick×6000 PPO update，seed291；T_nom无外力，T_force从开始分配课程但等真实hold才施力 | 两个固定终点，各一次128自然＋128计划扰动episode评估；同一左右门/B05分布与seed，实际到窗人口另记。无checkpoint大扫选 |
| P4 Student示范启动 | 新训练的合格T_force冻结后，Student自身初始化，128 env×8 tick、1000 BC update；50%计划扰动，Teacher执行 | 得到共同Student起点S0；配套Teacher config/描述和实际RGB/标签时序可用 |
| P4 Student配对 | S_demo/S_online从同一个S0起步，各128 env×8 tick、2000 BC update；相同采集/query和优化量 | 各终点一次128自然＋128计划扰动episode评估，正式成绩全Student执行；仅有实际需要时补Teacher前缀局部诊断 |
| P5 条件扩展 | 事件采样、长序列/prefix、L2/L3、持续1–2s或门侧扰动均不是本轮必跑项 | 先提交具体阻断/新问题，再扩对应最小范围；额外GPU单独申请 |

运行前一次实际吞吐/显存观察可据实调整并行env数；同组配对同步调整，并用总control transition数与优化量配平，不能把降低env数后的同update数冒充同预算。不要重启已经产生有效数据的配对臂来凑形式。超过上述更新量或新增训练组不是自动无限续跑；交付当前结果和下一项明确建议。

v1.0的500＋1000＋1000 update建立在warm-start假设上，本版不沿用。首轮scratch仍为6000 update/臂，不保证收敛。按C002既存45.46h/6000 update粗估，两张GPU并行的Teacher训练墙钟约45.5h，总GPU工作量约90.9h，另计校准/评估/Student；实际新路径吞吐需实测。执行team启动时记录真实ETA。超过30min用独立命名tmux及现有run_supervisor，完成一次启动确认后按真实ETA做一个持久化逻辑等待，完成/失败早返回；不定时唤醒模型看日志，不把ETA当自动kill时限。

先展示首个功能片段供Owner确认，不先补护栏、回归/变异/遗留兼容测试体系。已授权范围内的实现、必要运行和具体失败修复由worker team推进；本planner不承担运行监督。首轮指标未改善也应在固定终点交付真实结论，不自动加seed、加倍时长或换门域。

## 7. 结果和验收口径

首轮主比较是Teacher课程配对、Student执行数据配对及自主能力；同数据事件采样对照保留为有实际需要时的独立问题，不为四张表同时开训练。

| 要回答的问题 | 首轮证据 | 不能混入的归因 |
|---|---|---|
| 外力是否真正进入物理 | 每physics step请求时程、实际掌部/把手/门/base响应和固定撤力 | 有非零tensor不代表已施力，有门运动不代表失抓 |
| Teacher课程是否有用 | T_nom/T_force匹配起点与训练量；名义代价、受扰分配总体任务完成、保持/真实loss/L0/L1结果 | 只比较失抓后的成功率会改变分母；force把门推开不能单独解释为恢复 |
| Student自身执行数据是否有用 | S_demo/S_online同起点/模型/相机/优化量，正式评估均全Student | 两臂状态分布和实际loss数量不同是结果，不能说采到了相同数据 |
| 是否自主恢复 | 从自然reset全Student，真实loss→新握持→原任务完成 | 前缀Teacher参与不算自然起点全自主；失败后Teacher接管不算自主恢复；L0不能单独支撑L1能力 |

每个结果只保留必要可解释量：全部分配episode数、真正到窗/施力数、保持/确认loss/非局部或未知数、L0/L1新握持数、loss_then_pass、最终任务完成、超时、左右门和B05族、Teacher前缀/接管。以每episode首个真实loss作为主事件，重试另记。正常release和取消注入保留；门角/速度变化用于判断助推作用。

首条功能链交付实际actor RGB＋全景短片和按tick的紧凑表，包含执行者、Teacher label/Student proposal、发出命令与累计target、实际q/接触、pulse/loss/新hold、目标/预算阶段/剩余时间、done与最终结果。不得挑选一个片段宣称总体恢复成功。

最终交付分别标明：实现/运行事实、Teacher名义与恢复能力、Student自主能力、对照收益。没有后缀能力就不冻结为合格恢复Teacher；没有Student自主证据就不宣布传递成功。本版不预设80%等未经论证的成功率门槛，也不以退出码或有限张量作科学PASS。

## 8. Source/API事实与当前证据

| 入口 | 已读事实/拟议接点 |
|---|---|
| [v29 robot](../../gr00t/rl/config/robot/A2_Piper/a2_piper_v29.yaml):28；[URDF](../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/a2_piper.urdf):1217 | 掌部body为arm_body6_to_gripper，手指为arm_body7/8；runtime仍需按Articulation名字绑定 |
| [B05几何](../../gr00t/rl/isaac_utils/playground/env_rand/handle_v29.py):211；[door env](../../gr00t/rl/envs/door/door_open_a2_base.py):30030 | G的X沿把手切向、Z为approach；v29 pregrasp在−Z 0.10m，目标随当前刚体更新 |
| [LeggedRobotBase](../../gr00t/rl/envs/legged_base_task/legged_robot_base.py):1114；door env `_apply_force_in_physics_step` | 每control step循环真实physics step，在simulator step前有force hook；计划在此添加N01本步外力 |
| [IsaacSim backend](../../gr00t/rl/simulator/isaacsim/isaacsim.py):2360、2910 | 通用force-at-pos wrapper是pass；实际step顺序write_data_to_sim→sim.step→scene.update |
| 同backend `wsdpt_push_robot` / `clear_external_force_and_torque` | 旧路径依赖私有force buffer，A2 right_palm索引还指向torso；不直接作为末端外力实现 |
| `/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/assets/articulation/articulation.py`:207、239、1003 | reset清composer；write使用真实wrench并清instantaneous；旧set_external_force_and_torque为deprecated转发 |
| `/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/utils/wrench_composer.py`:123 | 原生composer接受force/body/env/frame信息；首轮每物理步add世界力，positions=None |
| [simulator配置](../../gr00t/rl/config/simulator/isaacsim.yaml):16；[C002 common](../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml) | 物理200Hz、decimation4及完整C002组合；不能拿旧Student默认solver/robot取代 |
| [A2 distill trainer](../../gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py):353 | 查询Teacher、Student forward与动作选择已存在；默认Teacher执行1.0尚不构成Student实际控制 |

本planner完成定向source/API阅读与离线代数，并按Owner新授权通过独立probe取得v28有限掌部力的实际施加、失抓与减半结果。诊断脚本位于`scriptsFORhuman/v29/n01/quick_force_probe.py`；它不是完整N01共同执行/恢复方法实现。C002+B05、Teacher学习、Student传递及硬件效果均未获新证明；GuidePup仍仅为施力结构参考。

## 9. 交接与剩余事项

**v1.2增加合力平面、GPU2/3并行和独立v28诊断，保留v1.1 scratch决定。** 共享控制、L0/L1、时间奖励、随机初始化、Student单路RGB/8tick/纯BC及每臂首轮规模保持；首轮总力插值范围已明确。常规config解析、B05上的几何/剂量校准、显存/吞吐与操作路径证明由实施worker完成。

仍未证明的是实际扰动人口、合格Teacher后缀、Student视野与自主恢复、方法收益。这些必须由实现与结果消除，不能靠计划签字变成已知。若固定首轮运行后仍无法形成合格Teacher，交付具体失败与下一步选择；不偷偷进入无限续训或把未合格Teacher交给Student充数。

worker team的具体边界、依赖与最小回报见[交接说明](a2_piper_v29_n01_worker_handoff.md)。实施Main负责WRITE_SET、分工和GPU2/3实际占用；一个共享路径/资源只能有一个writer/owner，独立环境/Student工作线可并行，集成后两个Teacher也可分别在GPU2/3并行。新增护栏/回归等遵Owner的先功能确认要求，不建立重复审阅队列。

GPU2/3之外资源、L2/L3、门侧/持续外力课程、Student网络/相机范围扩展或超出本轮的新增大训练组，依具体结果再提请Owner决定。Git commit/push、外部发布和硬件动作没有在本次被授权。本轮仅运行另行授权的v28诊断，未启动正式N01训练；既有其他任务仍归原监督者。[本轮Owner原话与范围](../novelty/conversations/20260921_codex_n01_force_plane_gpu23_quick_test.md)。
