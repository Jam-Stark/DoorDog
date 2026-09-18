# v29 baseline TODO

更新：2026-09-18 17:04 HKT。维护：-codex planner；依据：-owner。B01三档范围决定PASS，B06/B07已PASS；B02软件/当前物理解锁二选一与B04限位方案交Pro，B03后置到baseline出来后微调，B05继续讨论。

状态：DISCUSSION_OPEN。本文保留逐项讨论与出处；按Owner本轮要求，[baseline plan](a2_piper_base_v29_baseline_plan.md)已开始收录确认部分，尚未整体冻结。

2026-09-18 Pro回传已完成本地解析，原包/原文、来源、参数及复核附件见[本次归档](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/README.md)，详细核对见[LOCAL_RECONCILIATION](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/LOCAL_RECONCILIATION.md)。其中“六项未决”是回传解析时的状态；Owner后续确认以本清单与D008–D015为准，不改Pro原文。

维护方式：新动向追加到对应条目；team 事实、建议与 Owner 决定分别标记。只有与 Owner 讨论后明确确定的事项才改为 `[x]` 并划掉标题，同时保留结论和出处。讨论结案不等于代码已经实施。Owner已要求开始落地plan；逐项收录已确认内容，整体clean后再完成全文与执行安排。

总体 GPU 分工与 N01/N02 独立工作时机见 [总体安排](a2_piper_base_v29_overall_arrangement.md)。

首轮研究证据为source/resolved config读取、历史render与CPU静态几何。后续B07已有source/config实施及CPU采样核对，具体范围见下文；没有新增训练、物理/渲染运行或策略收益证据。

## 待讨论事项

- [x] **~~B01：门重、闭门器与门轴松紧联合随机化~~ — PASS（范围决定；物理代码待实施）。** handle 高度继续沿用已实施的 uniform `[0.90,1.20] m`。
  - **Owner决定（D012，质量由D014更新）**：30–80、80–120、120–160kg三档各1/3；有/无闭门器各1/2，有闭门器覆盖不同回关强度；门轴松紧加入并与hinge drive联合设计。六个质量×闭门器组合各1/6、左右侧目标配比一致；不把重门固定搭配强闭门器。
  - **工程设计已写入[baseline plan](a2_piper_base_v29_baseline_plan.md)**：用有限的回关力矩和参考速度联动k/d/cap，门轴static/dynamic/viscous摩擦单独表达；新数值是本地工程初值，未称为Owner逐一指定或现实分布。当前代码仍为旧80–120kg/原drive/native friction off，不能把讨论PASS写成物理实现PASS。
  - **baseline/N02分工**：本地建议在baseline加入正常回关范围。当前actor已有LSTM、连续门角/接触反馈，并接收质量真值，但没有闭门器/摩擦真值；具备学习条件，不保证学会。N02研究同一门域、同等可用观察下交互历史能否带来额外适应收益，不成为加入基础门型的前置条件。旧shadow结论不变。
  - **新增重档适配**：三档共用T=2.5–12N·m、参考速度0.15–0.40rad/s及温和摩擦域，仍按T/参考速度联动k/d；实际惯量随质量与几何生成，保留重门的起动/制动差异，不用按质量放大drive或强制门速掩盖。完整定义与薄板惯量量级说明见plan §2.2；新档尚无运行证据。
  - 以下保留确认前的研究与建议，当前决定以上述D012/D014和plan为准。
  - 研究关注：实际 selector/spawn/物理参数链路；mass、惯量、回弹 drive 与摩擦各自含义；不得把已有能力误报为当前已启用。
  - Team 核实（INSPECTED）：当前door panel mass已经是 `U(80,120) kg`；hinge drive maxForce为 `U(2.5,12.0)`、stiffness为 `U(1,10)`、damping固定 `50`。handle drive maxForce为 `U(1,3)`，stiffness/damping为 `50/0.5`。这些是生成链路中的参数分布，不表示实际每步恒定施加该上限的力矩。[selector](../../gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py#L1745)、[默认drive范围](../../gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py#L1985)、[质量采样](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L224)、[drive写入](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L531)
  - Team 核实：native hinge friction明确关闭，profile为null；robot link mass/PD/generic contact-friction/RFI随机化也关闭，但它们不是door panel mass随机化。[v29 resolved config](runtime_logs/baseline_no_center_smoke_20260917/config.yaml)、[native friction分支](../../gr00t/rl/envs/door/door_open_a2_base.py#L6897)
  - 历史对照：v27 L1曾用mass `[80,160] kg`、native static friction `{0,2,5}`、dynamic为static的0.75倍、viscous为0；v22的bucket还联合改变质量、stiffness、damping和drive上限。它们是历史试验分布，不代表v27/v28 baseline一直开启或已经证明有效。[v27 L1配置](../../gr00t/rl/config/ablation/wbmanip/base_v27_L1_S32.yaml)
  - Team 建议（未确认）：无需重新开启已经生效的mass/drive随机化；baseline可先沿用当前分布。若Owner希望恢复80–160kg覆盖，直接将其作为扩域决定讨论；hinge damping分布、native friction是否纳入分别决定，避免机械地恢复旧版成套bucket。这里不要求为每个参数另开实验。`penalty_driver`调的是reward curriculum，不覆盖hinge/handle物理drive。
  - **Pro追加（未确认）**：优先补轻门/工程木门与有无闭门器的联合域，不只把重端扩到160kg；质量、尺寸/惯量、闭门器曲线与摩擦分别表达。旧域可作历史对照，不称一般现实分布。
  - **证据/出处**：[来源S01–S08](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/SOURCES.md)、[参数CSV M01–M11/D01–D05/P01–P08](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/REAL_WORLD_PARAMETER_TABLES.csv)。LPD指定SKU的10/13kg是原厂值；金属门40–75kg/m²为面密度，按假定尺寸换kg是推算；TS93是特定样品图读，不是总体分布。P01–P07是工程初值，P08是历史项目摩擦值，国内概率与摩擦/阻尼分布仍UNKNOWN。
  - **本地核对/与旧意见异同**：单位换算得到支持：USD angular k/d按degree，转SI/rad乘180/π，d=50等价值约2864.79N·m·s/rad。q≥2°且qdot≥0等条件下，简化drive请求触及当前2.5–12N·m cap；不能外推关门段、所有零角样本或实际每步施力。当前没有后置D1覆盖，但spawn metadata不等于PhysX读回。相对首轮“沿用80–120”的建议，现更倾向先明确轻/中/重门覆盖目标，再决定分层；不自动接受Pro整套工程参数。
  - **确认前的待决记录**：实际runtime gain/施力/饱和比例/惯量；是否纳入轻门与无闭门器、门型权重、摩擦域及单位适配接口。当时尚未批准；后续范围决定见D012/D014，新增动力学尚未实施。
  - **2026-09-18 14:44给Owner的三个建议（历史；此处10–30kg起始三档已被D012/D014取代）**：
    1. 门重覆盖：建议补轻门/中等门，首版以10–30、30–80、80–120kg三档各占1/3作为工程覆盖目标，暂不向160kg扩。实际采样需与尺寸/惯量相配套；这些分档和比例不是产品统计或市场概率。原厂10–13kg中空门与34–50kg工程木门支持补轻端的方向，不证明这套分档。
    2. 回关行为：建议同时覆盖无闭门器与有闭门器，首版各占1/2；有闭门器组再包含不同回关强度。无闭门器仍可有摩擦，不设成完美无阻力；不把轻门固定等同无闭门器。具体力矩/速度规律在方向确认后按物理语义落实，现有大gain加cap不能直接称现实曲线。
    3. 门轴顺滑程度：建议增加温和摩擦变化，首版采用Pro的0–1N·m起动摩擦、动态/静态比0.5–1、附加粘性0–0.5N·m·s/rad作为工程初值；暂不恢复历史2/5N·m强摩擦档。它与闭门器主动回关分开表达。Owner决定覆盖范围和行为，单位换算/避免重复施力属于实现责任。

- [ ] **B02：latch 解锁角度与转轴动力学随机化。** Owner 希望覆盖现实不同 latch 解锁角度，并让 robot 学会根据下压交互判断解锁；原始意图为“下压到压不动了就是解锁了”。
  - **Owner最新范围（D016，覆盖D015软件偏好）**：交Pro在“软件约束虚拟锁闩A / 保留当前碰撞锁舌+mimic物理解锁B”之间二选一，列优劣、明确选择与所选方案设计。此前软件偏好及20–60°/+5°均非已批准结论；B02未PASS、未实施。见[本次Owner任务](pro_handoff/20260918_b02_b04/OWNER_REQUEST.md)。
  - **机理澄清**：当前latch确实负责锁门；“没有独立布尔阈值”指handle通过mimic缩回碰撞锁舌，是否脱离门框由几何决定。高位代理是放在门顶附近的简化锁舌，并非软件锁，也非把手旁精细锁体。
  - **team讨论/Main推荐（未确认）**：解锁阈值`U(20°,60°)`，机械止挡为本门阈值`+5°`（25–65°），每门固定。较小改动候选为解锁20–40°、止挡固定45°；不建议0°附近几乎无需下压的样本。推荐版同步调整硬限位、固定0.6rad下压尺度和creation路径的45°截断/归一化。它不依赖B04的门轴最大开角决定。
  - **行为与观察**：允许baseline学会压到底再保持抓握试推，不强求精确识别解锁瞬间；明显开门是正反馈，无运动不必然是未解锁，也可能是重门/闭门器/摩擦。内部阈值/锁态不加入actor/Student；不新增脚本试推。Pro的41°/65°为操作角锚点，20–60°与5°余程是工程建议。
  - **实施路线建议**：原生hinge有限游隙约束`[0,epsilon]`与正常开角上限切换；已打开的门不会因handle回位锁死半空，重新关闭后的复锁规则需明确。当前IsaacLab API有batched限位写入，PhysX不允许把相等上下限视为普通limit。删除旧latch/mimic/第三DOF假定并同步natural/staged reset；细节与出处统一在[plan §5](a2_piper_base_v29_baseline_plan.md)。未运行验证或写入物理代码。
  - 以下保留研究与本地候选；当前以D016的Pro独立二选一范围为准，不预设软件或实体方案获选。
  - 研究关注：解锁阈值、机械行程终点、阻力/回位与解锁后的可观测反馈是否被当前模型混为一谈；先澄清行为目标，再决定随机化维度。
  - Team 核实（INSPECTED）：当前把手机械行程固定 `0–45°`，回位目标 `−15°`、stiffness `50`、damping `0.5`；latch 是带碰撞的滑动刚体，最大缩回 `0.03 m`，mimic gearing=`−0.03/45`。实际解闩由缩回量与门框几何共同决定，没有独立的布尔解锁角开关。[生成链路](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L559)
  - Team 核实：v29 的 `0.6 rad` 是 unlatch reward 归一化/饱和尺度，不能当作物理解闩阈值；另有45°硬限位遥测常量。[配置](../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml#L72)、[公式](../../gr00t/rl/envs/door/door_open_a2_base.py#L2134)
  - Team 建议（未确认）：支持覆盖不同下压行程和回位负载，但把“最大下压行程”“latch退出门框所需行程”“回位负载”分开定义并协调采样。对本轮正常可开启门，可保证到挡止前或到挡止时已经解闩；策略目标是交互完成解闩，不能仅把运动停滞当作解闩证据。若改变行程，reward尺度与限位遥测应同步对应样本，而非只改一个reward阈值。
  - 外部语义核对：[NVIDIA mimic 定义](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.2/dev_guide/schemas/physxschema.html)；[Allegion关于全行程仍未充分缩回latch的原厂实例](https://kc.allegion.com/kb/article/why-doesn-t-full-rotation-of-the-ad-or-co-series-exit-trim-993-outside-lever-fully-retract-the-von-duprin-98-99-exit-device-latch/)。后者只说明不能把二者视为普遍等价，不要求本轮加入故障锁。
  - **Pro追加（未确认）**：将开始缩舌、完成缩舌、几何脱扣与机械挡止分开；允许首批只支持线性子类，不强制网络或完整非线性机构。
  - **证据/出处**：[S13 PDQ原厂](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/SOURCES.md)与CSV L01–L05支持不同backset的41°/65°操作角、12.7/14.2875/19.05mm throw组合，不能直接标成q_clear/q_stop或完整曲线。国内完整行程/回位负载/搭接分布为U03–U05未知项。
  - **本地核对/异同**：确认当前是门顶附近的锥体代理latch（z=door_height−.1m，x=−.083m，半径25mm、高50mm），未随handle高度移动。`−.03/45 m/deg`与USD写入面一致；prismatic的mimic实例名rotX本身不是bug。与首轮联合采样意见一致，新增了代理几何与产品操作角的边界。不能只把30mm改成14mm而宣称真实化；本轮尚未求出精确脱扣行程，也未证明14mm必然无解。
  - **历史待决与最新重开**：D015曾按Owner偏好讨论软件替代；D016现重新开放软件/保留当前物理代理二选一。精细重建把手旁锁体不是默认第三路线；原45°/30mm仅是现状参照，不要求添加兼容路径。

- [x] **~~B03：重新计算 base 双 D435i 上仰角~~ — DEFERRED（Owner明确后置）。**
  - **Owner决定（D017）**：保持当前15°，等待v29 baseline出来后再微调base双D435i上仰角；不作为本轮baseline或Pro决策前置。勾选表示本轮处置已确定，不是新角度/成像验证PASS。下方保留既有研究，25°仍非批准值。
  - 研究关注：实际相机位置、RGB/depth 内外参、近远距离、机身姿态、遮挡与高度范围。旧角度来源及图像观察先保留为待核事实，不预先指定新角度。
  - Team 核实（INSPECTED/静态计算）：base外壳中心相对trunk是 `[0.025,±0.155,0.190] m`、上仰15°；RGB/depth光心分别偏离外壳中心，不能用同一光心替代。[当前rig](../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/config/camera_rig.json#L16)。已证明15°被继承，未证明它最初专为0.85–0.95m设计。
  - Team 核实：有效v28预览的真实renderer K为RGB `fx=fy=1396.80859`（1920×1080，约69°×42.2726°），depth `fx=fy=446.80276`（848×480，约87°×56.4849°）。rig名义fy分别是1406.74809/432.97146；本机IsaacLab的square-pixel实现使两者不同，计算采用实际manifest K。[有效manifest](../../logs_eval/base_v28/side_video_a282_6000_h180_h110_20260917/run_r2/video_manifest.json)、[官方Camera源码](https://isaac-sim.github.io/IsaacLab/main/_modules/isaaclab/sensors/camera/camera.html)
  - Team 计算：冻结该有效预览首个Stage2（step96、1.92s）的机器人姿态与目标XY，仅替换把手高度并调整相机仰角，1080行RGB中的投影行如下。这是静态投影，未重跑高把手下的策略轨迹。

| 上仰角 | 高度0.90m | 高度1.10m | 高度1.20m |
|---|---:|---:|---:|
| 15° | 402.4 | 56.9 | −100.7（越过上缘） |
| 20° | 526.2 | 191.0 | 42.8 |
| 25° | 649.7 | 319.4 | 177.5 |
| 30° | 774.9 | 444.2 | 306.3 |

Team 建议（未确认）：提高仰角有依据；优先讨论20–25°，近距离1.20m把手覆盖优先时倾向25°。但在水平trunk、RGB光心约0.742m的剖面计算下，25°会使0.90m目标在约2.337m以外掉出画面下沿，30°则约1.012m即出现该限制。需Owner共同取舍近高把手与远低把手/下方视野，不凭单帧批准最终倾角。已排除首次位姿读取受干扰的录制，只用`run_r2`有效记录。

**Pro追加（未确认）**：独立初判30°，经计算改为25°名义候选，与本地倾向收敛；仍需讨论base远距定位与wrist近距观察的分工。[原始几何附件](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/GEOMETRY_AUDIT.json)为CPU推算，非渲染/策略证据。

**本地核对/修正**：Pro表实际用合并trace的**env1、step_index91/episode_length92**，上表用视频**env0、step_index95/episode_length96**；不是同一环境提前4步，像素差不构成算法冲突。Pro的env1数值已按对应记录复现。其随倾角旋转光心的解析远距界更精细：25°约**2.317m**、30°约**0.999m**；上段2.337/1.012m是固定光心高度近似，逐姿态投影表不受该近似修正影响。数据源仍为历史有效run_r2的实际K，S19硬件标称FOV不能代替它。

**local-only/Owner待决**：25°是否作为新名义值、近高/远低视野优先级及三相机分工；当前v29自然轨迹、renderer实际K/遮挡/深度仍未新增验证。不恢复v28豁免render条件。

- [ ] **B04：门最大张开角随机化。** Owner 观察 v28 会持把手开到最大角度才释放，提出把最大开角随机化为 90° 至当前上限，以覆盖现实门的不同限位。
  - **Owner追加（D017）**：与B02同包交Pro，更细判断软件限制还是物理限制，并给出所选随机化方案。当前150°是原生关节物理约束，非每步裁剪；须区分强制改角度、原生joint limit、实体stopper三种方式。范围/实施待Pro选择与后续落实。
  - 研究关注：当前 joint limit、stage/release/hold 与奖励阈值的关系；较小机械限位是否使固定阈值不可达；区分改变环境上限与改变何时松手的行为目标。
  - Team 核实（INSPECTED）：当前机械上限 `150°`，闭门 drive target `−10°`。[门轴构建](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L521)。当前 Stage3→4 约 `14.3°`、release gate `1.2 rad≈68.8°`、Stage4→5 开度门 `1.0472 rad≈60°`，还分别需要握持/释放及root位置条件；因此 `90°` 本身没有被这些固定角度阈值排除。[配置](../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml#L69)、[阶段条件](../../gr00t/rl/envs/door/door_open_a2_base.py#L29804)
  - Team 核实：release gate 后 hinge位置收入关闭，但 `hold_and_drive` 仍奖励有效双指握持与正门速；收臂惩罚又要求已经失去双指接触才生效。这是继续持把开门的收益线索，尚未证明是v28观测行为的因果来源。[hold条件](../../gr00t/rl/envs/door/door_open_a2_base.py#L15123)、[门角奖励](../../gr00t/rl/envs/door/door_open_a2_base.py#L17537)、[握持驱动奖励](../../gr00t/rl/envs/door/door_open_a2_base.py#L18360)、[收臂条件](../../gr00t/rl/envs/door/door_open_a2_base.py#L15942)
  - Team 建议（未确认）：支持讨论 `U(90°,150°)` 的机械限位变化，保留按实际通行需求表达的释放/过门条件。随机终点仍可能得到“开到各自挡止才松手”；如果Owner还希望改变这一行为，再单独讨论release后继续握持的收入。当前不把提前松手另立为已批准要求，也未验证90°门的实际通行和回弹质量。
  - **Pro追加（未确认）**：90–150°是工程覆盖域（CSV P09），原厂安装120°/180°示例不支持把该uniform叫现实分布；释放目标结合净空、回弹时间和接触需求，不奖励无条件提前松手。与本地“随机挡止不自动修复持握”一致，强调首次crossing时序而非全episode最大角。
  - **证据/本地核对**：[Pro release语义附件](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/RELEASE_EVENT_SEMANTICS.json)得到源码支持：`hinge_at_release`是逻辑gate首次置位，不要求实际松手；`post_release_body_force`从gate后stage≥4累计。**回位时间是另一窗口**：`v28_post_release=gate & ~both_contact`，从首次满足该flag的记录开始；不等于gate时刻、两指全无接触或计划释放。clean又使用首次Stage3起的身体力最大值，三者不能互换。[本地事件对照](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/LOCAL_RECONCILIATION.md)
  - **local-only/Owner待决**：是否采纳机械限位随机化及门型关联；是否以净通行/回弹时序定义v29释放质量；计划张爪、失去双指接触、非计划loss与再接触的区分。既有共现/收益线索不是reward因果证明，不回写v28门值。

- [ ] **B05：handle 几何族与概率末端回钩。** 保持当前圆截面直杆的大体抓握方式，讨论椭圆截面、曲线/不规则轮廓与不同现实把手形状，并按概率启用末端回钩。
  - Owner 决定：待讨论。
  - 研究关注：已有 generator 能力、可抓握区域、碰撞与 visual 一致性；形状变化对抓握目标定义和 push/pull 的影响。先讨论具体形状族，不自动改变抓握方式。
  - Team 核实（INSPECTED）：实际generator为圆截面Capsule杆，长度 `0.11–0.14 m`、半径 `0.011–0.015 m`；**末端已存在50%概率回钩**，长度 `0.04–0.06 m`，朝向门板。`door_handle_type`枚举当前仅被采样/记录，并未按knob/lever/pushbar分派几何。[尺寸与概率](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L305)、[几何构建](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L426)
  - Team 核实：当前grasp_target固定在杆中点、绑定同一handle刚体；改变杆中心线后需要根据真实可抓握段更新目标位置/方向。[目标生成](../../gr00t/rl/isaac_utils/playground/env_rand/door.py#L634)
  - Team 建议（未确认）：先讨论“椭圆截面直杆”和“轻微弯曲且保留中央抓握段”两个有限形状族；保留两指相向夹握与同一handle接触语义。回钩概率单独决定，不当作从零新增功能。visual/collision、抓握frame与质量建模同步说明；自由不规则形状暂不无限扩张到新抓法。
  - **Pro追加（未确认）**：圆直杆对照之外，椭圆、圆角扁截面和轻弯杆都可考虑，采用中心线×截面×return同源几何；不把恰好两个新族当固定要求。[形状原文](../pro_reviews/v29/20260918_102906__baseline_and_v28_pro_review/original/HANDLE_FAMILIES.md)及S14–S18/S23提供产品形态锚点；CSV P10–P17中的轴长、曲率、自由抓握段和3–5mm余量是**工程初值**，并非厂家完整CAD或现实分布。
  - **本地核对/关键接入差异**：当前目标还经过固定四元数、LEFT side mirror和pregrasp偏置，不能只改grasp_target点。Pro的`[a,c=t×a,t]`需映射到PiPER局部Y开合、Z接近；若a指TCP向把手，可讨论`R_target=[−t,c,a]`与`p_pre=p_grasp−d·a`，由同一层一次性处理左右手性、FixedJoint姿态及offset。该映射只是可行性说明，未实施。维持同一handle刚体/双指接触语义，退化抓点不能以静默fallback掩盖。
  - **补充事实**：Pro的URDF每指10N是资产声明；当前v29配置为45/45N、1300/32，并有写入effort_limit_sim路径，不能把10N当当前仿真能力上限。45N也不是实测接触力。70mm仅为差动关节行程；净开口/指垫局部面仍待相应几何核对。
  - **local-only/Owner待决**：首批形状族、尺寸域、族/回钩设计权重，以及统一grasp/pregrasp frame的责任层；现有指部真实可插入区域、产品图纸未核箭头/截面/曲率保留未知。

- [x] **~~B06：相机光路与 MERGED 几何精度——当前init/reset setup确认~~ — PASS。**
  - Owner 决定（2026-09-18）：同意Pro对当前setup的判断，接受现有MERGED、三相机及arm init/reset=`[0,.10,-.10,0,-.52,1.57]`。本项讨论确认通过，不为连线夹角凑零改几何。依据见D008；下方保留研究过程。
  - Owner 提供的核对结果（保留原始输入；team已用当前资产配旧reset复现，见下表后说明）：

| 检查项 | Owner 提供结果 | 原判断 |
|---|---|---|
| 夹爪开合轴与地面法线 | reset 相差 28.77° | 不对地竖直 |
| 图像水平轴与夹爪开合轴 | 89.95° | 基本垂直，偏差约 0.046° |
| 图像水平轴与地面 | reset 倾斜约 0.00018° | 初始画面基本水平 |
| 180/45 外壳中心—安装端中心连线与开合轴 | 相差 1.74° | 不是严格平行 |
| 180/45 光轴相对水平面 | reset 向前下俯 21.22° | 朝前，非水平前视 |

Team 核实（CPU静态FK）：同一当前URDF/rig下，Owner表的全部数值对应旧reset `j5=−0.415`；当前 `j5=−0.52` 得到下表。光轴俯角变化 `6.01606°` 正好等于 `0.105 rad` 的reset差，不是两套光学定义冲突。[当前reset](../../gr00t/rl/config/robot/A2_Piper/a2_piper_v29.yaml#L135)、[URDF关节链](../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/a2_piper.urdf#L1277)、[生成器](v29_build_asset.py#L44)

| 检查量（trunk参考系） | 旧j5=−0.415 | 当前j5=−0.52 |
|---|---:|---:|
| 开合轴与trunk法线夹角 | 28.77397° | 34.79002° |
| 图像横轴与开合轴夹角 | 89.95413° | 89.95413° |
| 图像横轴相对trunk水平倾斜 | 0.0001759° | 0.0002225° |
| 外壳中心—安装端中心连线与开合轴夹角 | 1.744408° | 1.744408° |
| 光轴相对trunk水平面俯仰 | −21.22225° | −15.20619° |

这些静态量只有在trunk水平时才能直接称“相对地面”；实际world角度需组合trunk姿态。1.744°是确实存在的安装连线差，但该连线不等于光轴或支架梁轴；0.046°是图像横轴相对开合轴的非正交差，不是画面滚转。Team建议（未确认）：优先统一rig与实际renderer内参口径、视场/遮挡需求；没有安装平行度要求或可见问题时，不为凑零改掉现有几何。光学世界姿态精度、有效深度与成像质量仍未获本轮运行验证。

**Pro追加与本地核对（未确认）**：旧/新reset FK和trunk/world区分一致。Pro所算“法兰原点→壳中心”4.9964°、“支架梁轴”5.1613°，与本地“支架start→壳中心”1.7444°是三条不同连线；本轮已核实第三条端点定义，关闭的是这一**静态未知量**，不是勾选B06。25°、外壳隐藏和质量补建也未获新批准。

**证据/异同**：rig/URDF与renderer历史K一致性为source+CPU证据；Pro补充base相机未独立计质量和门板guide保留整板collision，均与源码相符。中央旧盒未计质量，不能虚构扣减。门板80%是代码采样期望而非当前实测频率；此问题已有长期TODO **DIST-01 / v28 X-16**归属Student lane，并非新发现或当前baseline自动前置。Pro将X24泛称参数校准应收窄为原G0-L locomotion随机校准范围。

**local-only/Owner待决**：是否补base相机实际质量建模及依据、统一实际K/坐标定义的具体范围；实机标定、当前v29 USD/renderer/遮挡与质量影响仍未知。若要将DIST-01前移到baseline，需Owner另行明确范围，不恢复旧render收尾条件。

**Owner确认范围补充**：B06的PASS接受当前init/reset setup；上述扩展事项不再作为本项未结理由，仍按原有独立议题归属处理。它不改变B03倾角讨论，也不把当前setup接受写成新的实机/成像质量结果。

- [x] **~~B07：扩大自然起点位置范围，并联合采样初始yaw~~ — PASS（Owner认可方向，范围已实施）。**
  - **已落地范围**：门root局部法向距离`U(1.2,4.0)m`；门root局部横向偏移`U(−0.5,0.5)m`；朝闭门主握杆中心的水平方位±10°，同时满足相对门法向yaw±35°。
  - **联合采样**：先取距离/横移，再由该位置和闭门`grasp_target`计算bearing β；从`[β−10°,β+10°] ∩ [−35°,35°]`均匀采样yaw。不是独立随机yaw，也不把抽样结果裁到边界。当前门几何边界下区间最窄约5.12°，无需拒绝采样或fallback。
  - **实际路径**：`_init_door_metadata`从源USD的闭门grasp_target相对door变换缓存目标；自然`_reset_root_states`使用该目标，避免robot先reset、door后reset时读取上轮移动把手。只影响自然Stage0起点；显式state/staged恢复路径保留。natural eval继承新范围。没有新增Student目标真值输入。
  - **时间配置已由side window落地并承接**：整集30s；Stage0 525步/10.5s；Stage1–4各150步/3s；Stage5 300步/6s。控制dt=.02s，各stage相对此前350/100/100/100/100/200增加50%；`award_remaining_time_on_advance=true`保留。见D009。
  - **范围依据**：Owner转述side window对当前base15°/wrist reset、双侧门及尺寸/高度边界的静态投影结果；名义及body height0.47–0.55m、pitch±3°网格中，同一相机RGB/depth覆盖主握杆包络，最差约10%边缘余量。本轮记录该既有结论，未重跑视场网格；自身遮挡、Student裁剪/降采样及真实深度仍不在其证明范围内。
  - **实施核对**：[v29 common](../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml)、[源码](../../gr00t/rl/envs/door/door_open_a2_base.py)、[配置解析与CPU采样记录](implementation_evidence/init_range_20260918/implementation_readout.json)。实际配置解析和生产yaw分支的1218个CPU边界网格样本满足两重角窗；这是实施/静态证据，不是定位成功率或训练质量PASS。
  - **速度后续决定（D011–D013）**：D011按4m起点与10.5s预算将Stage0目标改0.5m/s；Owner随后要求按门距离平滑变速，并确认0.5/0.3。当前以门法向1.8–2.2m为过渡带，使用smoothstep从内侧0.3连续过渡到外侧0.5，2m处0.4。进入站位带后原目标方向归零及停稳条件保留；Stage4/5仍0.3。配置解析与source AST通过，未启动仿真/训练。

## 已确认结论

B01范围决定PASS，三档联合设计进入[baseline plan](a2_piper_base_v29_baseline_plan.md)，物理代码待实施。B06/B07已PASS，Stage0平滑速度已实现。B03明确后置；B02机制与B04限位交Pro独立决定，B05待讨论。完整决定见[决策记录D008–D017](a2_piper_base_v29_decision_log.md)。

## Pro对v28的验收与本地边界

Pro接受已声明Owner范围变更后的执行收尾，限域接受核心实验结论，仍判新Teacher资格未确认、恢复/适应/部署能力未验证。本地核对四份512条记录的核心计数与Pro一致；clean/相机只核源码口径与已有汇总，未重跑完整trace。原三seed6000 reach1/3，固定主备DEV clean123/47、69/52，CONF未运行、Teacher/G7不变；v28原结论及render豁免保留。

回位120/6、9/119、2/126、0/126是已观察/删失计数，不自动按128或只比较已观察者均值；S0+S5姿态L1是arm六关节偏差，不是base roll/pitch。Pro evidence index中的`state.json`未在本次输入bundle中，不能作为云端独立读取证明；已有锁定/启动/停止/清理收据足以支持相应收尾核对。

## 当前建议讨论优先级

B02/B04按本次Pro任务收敛；B05几何族与目标frame继续讨论。B03等待baseline出来后再微调，不阻塞当前版本；B06扩展事项按独立议题处理。N01/N02仍按baseline落地后独立分支安排，不因本段产生训练预算。
