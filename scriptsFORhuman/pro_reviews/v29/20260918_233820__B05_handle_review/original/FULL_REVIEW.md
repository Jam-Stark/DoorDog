# FULL_REVIEW｜七族handle设计的重复、扩展与现实覆盖

日期：2026-09-18。项目：DoorDog A2+PiPER，v29 B05。

审阅分支：`codex/v29-b05-pro-20260918`。发布主题：`Approve seven-family v29 B05 handle plan and prepare Pro review`；Worker报告提交时间：`2026-09-18T21:46:23+08:00`。本回包为独立设计意见，不改变Owner的批准记录。

## 0. 三问直接结论

**1｜有实质重叠，但不是七族完全重复。** F0/F3/F5/F6在G的圆截面高度重叠，其中F5在整个主握腹段内与同径F0局部最相似。F3/F4仍有有限指宽内的曲率残差，F6有厚度梯度，F1/F2有非圆截面与面接触差异。七个外形名字不能数成七个独立接触机制；同一圆截面也不能抹掉端部障碍、接近空间和全局姿态差异。

**2｜不建议现在增加第八个训练族。** 推荐七族全部保留，以站距/邻近障碍、真实截面厚度与方向、有效主握段、条件return等参数补充覆盖。最有价值的额外组合是X1“F3轻弯×F1椭圆”，优先留作未见几何对照而不加入训练；这样它能检验组合泛化。保留F5标签，但不要赋予它与F1/F2同等明确的新接触机制解释。

**3｜现实先例可支持设计方向，不能保证泛化。** 原厂资料证实圆管、椭圆、圆角平面、曲线、偏置、变截面、return都存在；部分种子的映射必须降级：FSB1144的S描述属于设计史，FSB1294英德文锥度方向冲突，HOPPE图纸本轮未读成功。当前证据只到source＋标称静态设计，既未证明多族sim可抓，也未证明未见型号或sim-to-real收益。

**核心建议：七族保留；比“第八种轮廓”更优先的是“门法向站距×整指扫掠空间”，其次是截面方向与有效长度。** 这些是对现方案的显式参数/构造补充建议，不静默改变已批准方案。来源与边界见[SRC-01](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/pro_handoff/20260918_b05/OWNER_REQUEST.md)、[SRC-02](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md)、[SRC-11](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/a2_piper_base_v29_baseline_plan.md)。

## 1. 审阅范围、顺序与证据等级

先读OWNER_REQUEST、REVIEW_BRIEF、SOURCE_INDEX、已批准设计；对照families.json、geometry_readout、绘图脚本、PNG/SVG与源代码，形成局部接触初判并做独立静态计算；随后读REAL_WORLD_SEEDS和历史Pro形状/来源/参数文件，再核查厂家。

两个ZIP均可独立解压，合计35个manifest选定文件，路径/字节数与manifest相符。源文件定向读取相关函数/配置，不声称全仓审计。另在线读取专用审阅分支的设计文件、Teacher观察列表及common配置相关片段。三件STL只支持局部几何计算；没有补齐整机资产，没有安装或运行Isaac/MuJoCo/CUDA，没有checkpoint、B05训练日志、GPU或硬件结果。

| 标记 | 本报告含义 |
|---|---|
| SOURCE / DESIGN | 当前源码事实，或Owner已批准但未实现的标称设计；两者不混用 |
| FACTORY_TEXT / FACTORY_IMAGE_QUAL | 原厂可读字段/文字，或只能支持定性的官方产品图片；不等于实物测量 |
| DERIVED | 根据已知参数/网格作出的显式静态计算；不是接触仿真 |
| ENGINEERING | Pro建议的尺寸域、抽样/简化方法，不是厂家分布或Owner批准 |
| UNKNOWN / LOCAL_ONLY | 当前没有证据；需要实际导入、策略比较或实机数据才能回答 |

包内无读取失败导致的材料遗漏；外部FSB技术图册、HOPPE数据表/绘图文件、GEZE PDF未成功读取，DWG未解析。没有从照片猜精确尺寸，没有把旧Pro图册数值当本轮已核验数值。详见[SOURCES](SOURCES.md)。

## 2. 首先锁定：现源码仍是圆杆，不是七族实现

当前生成器`handle_inside/outside`均为Capsule；类型枚举存在不代表相应几何已实现。随机Capsule轴段110–140、半径11–15，因此含帽总长132–170；完整axle180–210，当前v29/scenario未见较短axle override。两个握杆和有概率的两侧return都在同一door_handle刚体内。50%概率、40–60直Cylinder回返早已存在，不是B05首次引入。

标称A195、门厚40：握杆中心到选定门面`h=(195−40)/2=77.5`。圆径26时，杆表面静态距离门面64.5。h不是净空，64.5也不是加入指体后的净空。OpenUSD的Capsule height是轴段，不含两帽。[SRC-04](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/isaac_utils/playground/env_rand/door.py)、[SRC-08](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py)、[W14](https://openusd.org/release/api/class_usd_geom_capsule.html)。

以下七族、目标frame与FixedJoint统一输出都仍是plan。原有consumer固定旋转与LEFT补偿仍在源码中；不能把示意图已经转对了当成运行接线已正确。B04/B05的TODO保持“方案讨论完成”，不因上述实现空缺撤销勾选。[SRC-02](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md)、[SRC-06](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/envs/door/door_open_a2_base.py)、[SRC-11](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/a2_piper_base_v29_baseline_plan.md)。

## 3. 七族：轮廓不同与接触不同分开看

![Worker原始七族标称图；静态设计非仿真](figures/worker_nominal_seven_family_atlas.png)

图：复制Worker原图，未修改。它反映已批准的工程标称，不是实际产品测量或可抓证明。下表单位mm；I、J是弧长坐标，不是任意世界坐标线段。

| 族 | 主杆、截面与G | I长度 / J长度 | 指体可能感知的因素 | 重叠/互补判断 |
|---|---|---|---|---|
| F0 | 直圆d26；轴125/含帽151；sg62.5 | 65 / 3 | 圆形闭合、圆面局部法向与直段滑动 | 基准，不把“原来能开门”移植成七族证明 |
| F1 | 直椭圆，法向28×闭合20；sg65 | 74 / 12 | 方向相关厚度、接触法向变化速度、roll | 与圆杆实质互补；与F2同为非圆，但曲率/平面不同 |
| F2 | 圆角扁30×18/R6；sg65 | 74 / 12 | 平面—圆角分区、厚度与转动对齐 | 有独立意义；效果和厚度不同会混淆，不能只以族名归因 |
| F3 | 圆d26、弧135/R400；sg67.5；G抬高5.68 | 69 / 7 | 有限指宽内持续曲率；端部相对姿态 | G处同F0圆截面/近水平不代表整段等价，但差异很轻 |
| F4 | **圆d24**，S投影130/振幅3；sg65.34；G倾斜−8.25° | 68.68 / 6.68 | 变号曲率和有限指宽内残差；d24也改变闭合厚度 | 姿态真值给出后仍有S残差；不是扁杆，也非仅一根转斜直杆 |
| F5 | **圆d26**，投影140/平直腹偏置8/过渡32；sg71.17 | 72 / 10 | I内直圆；全局轴颈/末端关系、力臂、视觉轮廓 | **局部最冗余**；偏置是门平面内z，不增加门法向站距 |
| F6 | 直中心线130；d从28平滑降24；sg65处26 | 70 / 8 | 有限范围内直径梯度、先后接触、轴向滑移趋势 | 不等于恒径26；作用大小依实际指垫长度/接触状态而定 |

来源：[SRC-02](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md)、[SRC-03](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/b05_designs_20260918/families.json)。所有族标称h77.5；沿门面弯曲不会自行改变h。按G截面计算的杆—门面静态距离分别F0 64.5、F1 63.5、F2 62.5、F3 64.5、F4 65.5、F5 64.5、F6 64.5，均未扣指体/动态扫掠。

### 3.1 独立有限指宽计算：不能只检查G的一个截面

我将各中心线移到G，并对齐G处切向，检查弧长`sg±28`的56 mm范围。28来自现有原始整指包络的一半，不是实测接触斑半长。结果见附带[STATIC_CALCULATIONS.json](STATIC_CALCULATIONS.json)。

| 几何 | 相对G切线最大残差 | 局部方向/厚度读数 | 可检验的设计解释 |
|---|---:|---|---|
| F0/F1/F2直中心线 | 0 | 无曲率 | 区别来自截面，不来自中心线 |
| F3 | 约0.98 mm | 两端相对G切线约±4.01° | 持续轻弯可能改变接触分布，但必须先保证collision真正保留这个量级 |
| F4 | 约1.10 mm | 相对G切线方向最大变化约6.39°；G本身为拐点 | 给出−8.25°目标姿态只去掉刚体倾斜，没有去掉变号曲率 |
| F5 | 0 | 在该范围内持续为恒径26直腹 | 完美姿态/位置对齐后，主握接触与F0高度重叠 |
| F6 | 0 | 该范围直径约27.21→24.79，跨度约2.42 mm | 是沿接触长度的梯度，不只是G处26这一数字 |

F3也可由圆弧弓高`R[1−cos(28/R)]≈0.98`核对。F4用包内中心线数值投影；F6用原smoothstep直径函数。以上是DERIVED，不是求解后的接触点、摩擦裕度或抓握成功率。

包内collider帮助函数仅启用碰撞，运行时各shape的contact/rest设置没有读回；不能把近似精度当接触分辨能力，也不能直接把contact offset当几何膨胀。本次不更改这些动力学/求解参数。

若真实有效指垫只有较短一段，F3弓高按长度平方下降，F6厚度差也下降，因此当前“整指包络能看到差别”不能自动变成实际指垫能稳定辨认差别。反过来，整指侧边与return/轴颈碰撞又可能使全局轮廓差异重要。

### 3.2 F1/F2为何不能简单合并

F1在标称闭合方向上的厚度20，而F2为18；F1的接触面仍曲，F2存在平面及圆角。在理想截面几何上，半轴14/10的椭圆在闭合极点曲率半径为14²/10=19.6，圆杆对应13；F2的标称相向平面沿法向可有30−2×6=18的直线段。它们提供不同表面法向与滚动/对齐条件，但这**不是实际接触斑面积**，更不能据此承诺平面一定抓得更牢。

为了研究“截面形状”而非“杆更细”，应在同等厚度/近似净空设置下对照，并说明哪些尺寸无法同时匹配。不能七族每族固定一组不同尺寸后，把所有成功率差异归因于形状。

### 3.3 不删F5，但降低其机制叙述强度

F5提供可见的端部过渡、平移偏置、不同lever几何关系，Student图像中的背景遮挡也可能不同；这些足以保留其作为形态/空间组合实例。另一个DERIVED混淆量是绕handle轴的G位置半径：F0为62.5，F5为√(70²+8²)≈70.46 mm；力的方向合适时会改变有效力矩，但这也可由长度/抓点位置轴产生，不能只归因于“偏置族”。它的I被刻意选在直腹，恰好排除了最可能提供独特接触的过渡段。因此“F5是独立的第五种抓握机制”缺乏支持。

采用生成器统一G后，F5的8 mm位置变化会直接进入Teacher目标。Teacher成功对准这个新位置，首先证明跟踪给定几何真值目标，而不是证明其从外观辨认出偏置杆。建议共享底层直腹构造，不删除Owner已批准的F5标签。[SRC-02](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md)、[SRC-05](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml)、[SRC-06](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/envs/door/door_open_a2_base.py)。

## 4. 最高优先级缺口：h与整指扫掠，而不是更多平面波形

当前所有标称族h77.5，F3/F4/F5也只在平行门板的平面弯曲。它们无法替代较低h、较大截面法向尺寸、贴门return或饰盖的净空压力。

三件mesh经URDF关节变换，原始手指局部X跨度约56；在TCP处Z85截面跨度约41.46，在Z72与98处约52.50/34.43。这与Worker给出的41.47/52.51/34.43量级一致，末端25.4不能替代当前TCP的宽度参照。URDF关节差动行程70 mm不是净开口，配置effort45不是实测接触力。[SRC-07](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml)、[SRC-09](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/data/robots/a2_piper_v29_merged_20260917/a2_piper.urdf)。

**新增静态警示：** 当前mesh在gripper-base中的最前Z约135.8，TCP在85，沿+Z最大前伸约50.8。若G在主杆中心、+Z严格沿门法向接近，光看无限平面几何，前端离门面的最小剩余量约为`h−50.8`，而不是`h−13`。标称h77.5时约26.7；拟议h55时约4.2。这是网格极值推导，不考虑饰盖、手掌、转动姿态或真实指垫变形，不是可抓性结论。

厂家可读例子包括Nordic L/U的19 mm杆、projection62/64、rose突出6；projection的起算面未读图，不能硬写成h。但条件换算会落到约52.5/54.5或58.5/60.5，提示“所有族始终h77.5”的现实覆盖假设需要收窄。ASSA696的总体长度106也提示短握段问题，不能由总长反推I。[W09](https://www.assaabloy.com/uk/en/solutions/products/door-furniture/scandanavian-lever-and-pull-handles/scanflex-range/lever-handles/nordic-l-lever-on-rose)、[W10](https://www.assaabloy.com/uk/en/solutions/products/door-furniture/scandanavian-lever-and-pull-handles/scanflex-range/lever-handles/nordic-u-lever-on-rose)、[W11](https://www.assaabloy.com/uk/en/solutions/products/door-furniture/scandanavian-lever-and-pull-handles/classic-range/lever-handles/696-unsprung-lever-handle)。

因此推荐h55–85的保守工程扩域、保留更低h为明确能力缺口；不要以范围里包含一个较贴门值就声称整个域可抓。这个建议是**显式改变之前保持axle长度不动的对照设置**，需要Owner决定。真实站距与当前TCP不兼容时，问题可能是形态可达性而不只是policy不够泛化。

## 5. Teacher接线：几何扩域对控制、对视觉不是一回事

### 5.1 当前actor拿到了什么

actor与critic观察都包括`gripper_handle_transform`、`privileged_door_info`、门关节位置与手部力。前者为相对handle与pregrasp各自的3D位置＋6D旋转，共18维，来自FrameTransformer真值。后者8维为门宽、门高、handle安装高、handle安装横向距离、门质量/100、左右标记、开门方向；**其中door_handle_width是安装位置相关量，不是杆径。** 包内没有给actor直接接入族ID、局部曲率或完整截面参数。[SRC-05](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml)、[SRC-06](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/envs/door/door_open_a2_base.py)。

因此不能说Teacher所有形状信息都被直接告知：截面厚度与曲率仍可通过碰撞、动作误差和时序力反馈影响控制。但G位置/姿态已由真值给出，许多位姿调整无需视觉识别；F4中心倾斜、F5平移尤其如此。hand_force是仿真手指体力信息，不是高分辨接触面/曲率传感器。

### 5.2 对控制可能有的收益

在目标明确的条件下，让动作与闭合对不同厚度、平面/曲率、轴向梯度、障碍净空更稳健；让部分姿态误差或接近误差能被有限接触反馈吸收。这是合理的机械泛化假设，前提是collision实际保留差异、目标接线一致、样本包含足够的真实接触变化。

如果只改visual，或者把轻曲线的collision近似成同一根圆杆，当前无图像Teacher的控制训练不会获得预期的几何信号。几何随机化的单位应是“接触/净空因素”，不是渲染中有几个名字。

### 5.3 对视觉Student可能有的收益与不能推出的结论

当前v29 common中`enable_cameras=false`，Teacher actor列表没有图像输入。图像/深度中的外观分布只有在后续确实生成并供给Student训练数据时才产生视觉学习信号；有渲染能力不等于已经完成这一步。几何/target同源会使未来标签更自洽，但不保证Student能在遮挡、深度噪声或外参变化下恢复那些真值。

“Teacher在七族上成功”即使将来成立，也最多先支持给定真值目标的控制覆盖。它不证明Student会识别七族，不证明未见厂牌/型号的G可以可靠预测，也不证明实体未见门能开。不要先要求Student做族名分类；真正需要的是可用的局部几何/位姿与接触反馈，而非记住F0–F6标签。[SRC-05](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml)、[SRC-06](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/envs/door/door_open_a2_base.py)、[SRC-07](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-b05-pro-20260918/gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml)。

## 6. 现实对比：能确认什么，哪些种子应降级

完整13例见[REAL_HANDLE_COMPARISON](REAL_HANDLE_COMPARISON.md)，包含品牌/型号、原厂URL、可读字段、映射、UNKNOWN与图示。关键修正如下。

FSB1108明确椭圆握段，FSB1226明确平面及圆边，对F1/F2是有价值的定性支持。FSB1147的锥形变化位于过渡，不能代表F6全主握段渐变。FSB1144现售图为流线宽扁造型；访谈的早期S形不能确认F4当前圆截面浅S。FSB1230偏置版本只支持存在偏置，不提供8 mm、方向或直腹长度。FSB1294英文向外展开、德文向外渐细互相冲突，因此本轮只采用“沿程变截面”的共同信息，不擅自确定方向。[W01](https://www.fsb.de/en/products/collections/fsb-1147)、[W02](https://www.fsb.de/en/products/collections/fsb-1108)、[W03](https://www.fsb.de/en/products/designed-by)、[W04](https://www.fsb.de/produkte/designed-by)、[W05](https://www.fsb.de/en/products/collections/fsb-1144)、[W06](https://www.fsb.de/en/magazine/interview-jasper-morrison-fsb-1144)。

HOPPE官方产品页和下载列表已读，但PDF/DWG几何未读成功，保留主杆几何UNKNOWN。GEZE LH103的oval是饰盖名，杆的Diameter字段19支持细圆管，不支持椭圆截面。ASSA Nordic U与HEWI111.23R提供round/U形return现实依据；return的R20–30、H条件域是工程建议，不是厂家测量。[W07](https://www.hoppe.com/se-en/product/1000391521/trondheim-entrance-door-sets?FARBE=F69)、[W10](https://www.assaabloy.com/uk/en/solutions/products/door-furniture/scandanavian-lever-and-pull-handles/scanflex-range/lever-handles/nordic-u-lever-on-rose)、[W12](https://www.geze.com.cn/en/products-solutions/access_control_and_safety/door_hardware/door_handle_sets/handle_lh_103_oval/p_91480)、[W13](https://catalog.hewi.com/en-DE/product/6811699)。

**最有信息量的补充现实组合是FSB1107：椭圆截面＋曲线。** 当前七个固定组合中椭圆和平面族是直杆，弯杆族都是圆截面；因素出现过不等于它们的组合出现过。保留一个X1未见组合比再造一个与F5近似的圆直腹族更能检验设计的泛化假设。[W08](https://www.fsb.de/produkte/produktfamilien/fsb-1107)。

## 7. 四个命题分别给结论，不能串成保证链

| 命题 | 本轮判断 | 证据边界 |
|---|---|---|
| 外形因素有无现实先例 | **有，部分种子只能定性且映射要修正** | 厂家文字/照片，少量官方尺寸字段；不是七个工程标称的精确产品复刻 |
| 简单几何是否能表达关键接触/净空因素 | **可以，建议采用参数化扫掠与局部凸段；当前覆盖仍有限** | 表达能力由几何构造支持；h/roll/邻近障碍及因素组合是主要缺口 |
| 当前是否已经证明七族sim可抓 | **没有** | 七族未实现；非空J和静态mesh不能代替导入、接触或闭环结果 |
| 已证明未见型号或sim-to-real收益吗 | **没有** | 没有相应Teacher对照、Student数据或硬件证据；产品照片不提供这种因果证据 |

可解释的泛化假设应写成：“当未见lever的局部截面厚度/法向、有限指宽内曲率、可插入空间及相关动态接触落入已训练覆盖域，且部署观察足以定位并反馈接触时，策略有理由复用行为。”其中两个条件都需要检验，不能由“七族有出处”推出成立。材质/摩擦、锁闩阈值、门动力学与视觉域差异仍是独立因素，本轮不把它们混为几何收益。

## 8. 明确保留与修改建议

**保留：** 七族标签与精确标称锚点、一个door_handle、双指接触语义、I/J/G口径、proper有向轴、pregrasp局部−Z100 mm、与几何一致的COM/惯量。保留B02/B03/D023/N02已有归属。

**建议Owner批准的修改：** 主动加入h55–85（A150–210于T40）、较细圆杆19–30与非圆roll；按I约束选择长度，不把70差动行程当净开口；return采用与h关联的圆滑几何并保留内空隙；必要的同轴饰盖只用一个门板刚体上的简单薄圆柱表达。所有值与原值逐项列于[DESIGN_RECOMMENDATIONS](DESIGN_RECOMMENDATIONS.md)。

**不推荐：** 为凑数量增加另一个圆截面波形族；把F4/F5改名解释为扁杆；用全形凸包填满回钩；以圆碰撞体承载椭圆visual；因G非空宣称抓取PASS；为了较短产品静默移动TCP/削指/换抓法。X1不作为第八训练族，优先留作未见组合对照。

这些修改没有获得Owner自动授权；主方案仍是已批准的七族，不被本Pro文字静默替换。

## 9. 少量必要的后续判别，不新增预算或测试矩阵

**几何层面的一次定向核对：** 在七个标称和拟议低h/return边界处，用实际原始指体而非细指垫猜测核对G、接近和闭合扫掠，记录不兼容的来源。目的在于识别参数化是否悄悄产生穿门/假卡点，以及几何真值目标是否一致，不把静态可行升级为运行可抓。当前指垫/TCP未实测，优先明确这一未知；不指定云端无法证实的硬件阈值。

**未来同等设置下的最小因果对照：** 在Owner原定资源内比较“扩展共同尺寸/站距域的圆杆”与“同样域、同等数据量的七族”，固定原有摩擦、门动力学、目标/奖励/观察设置；预留少量未见几何，重点包含X1和一个有可靠图纸/实物数据的贴门return型号。没有图纸时只称未见工程几何，不能冠以精确产品重建。这样才有机会区分族形状收益与尺寸域/训练量收益，不要求额外大矩阵。

**结论分层报告：** 同一小组未见几何上，真值目标Teacher与部署观察Student分开报结果。前者好、后者差优先说明感知/蒸馏缺口；两者都差再看几何/控制；sim好而实物差也不自动归因于shape，仍需区分摩擦/观测/动力学。只使用实际拥有的结果，不承诺本轮无证据的成功率。

## 10. 交付与必要未知

当前未知：实际指垫接触区域、实际净开口/力、真实TCP标定误差、厂家缺失的截面/曲率/站距、各族导入后的collision精度与指体扫掠、有效J_3D、Teacher/Student对照及sim-to-real结果。本地新source与审阅快照可能不同；planner需定向比对，不覆盖较新修改。

回包由Owner从对话下载再上传本地，**未上传Drive**。包含五份要求文档、一个静态计算JSON和Worker原始标称PNG。没有实现代码、模型权重、哈希清单、伪造运行日志或硬件PASS。
