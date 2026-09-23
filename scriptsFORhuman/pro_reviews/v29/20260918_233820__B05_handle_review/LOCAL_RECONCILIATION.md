# B05 Pro回包：本地定向核对与待决定建议

后续Owner决定（2026-09-19 00:44 HKT，D029）：全部Pro建议已采纳，并按当前PiPER/TCP完成第二次静态确认；当前配方以[baseline执行规格](../../../v29/a2_piper_base_v29_b05_handle_design.md)及[worker交接](../../../v29/a2_piper_base_v29_b05_worker_handoff.md)为准。下文D028的“待Owner/NOT_APPLIED”保留当时提案状态，不表示当前仍未批准。

2026-09-18 HKT。状态：**回包已归档；完成一次source/静态几何及关键厂家来源核对；扩域参数待Owner确认**。本页是本地整合入口，`original/`原文未改。Main负责planner工作，本轮未实施source/config/asset、运行或监督训练。

## 1. 三问结论与本地意见

| 问题 | Pro结论 | 本地核对/建议 |
|---|---|---|
| 七族是否重复 | 存在局部接触重叠，F5与同径圆直杆最相似；F1/F2截面、F3/F4有限指宽曲率、F6沿程厚度仍有区别 | 支持这一限定结论。保留F0–F6及原标称，不把七个外形名字解释为七种独立接触机制，也不因此删除F5 |
| 是否扩展构型 | 暂不增加第八训练族；优先站距、截面方向、有效长度与return条件域。X1“轻弯×椭圆”留作未见组合候选 | Main建议同意这个优先顺序。X1仍是lever操作，增加的是因素组合，非新操作方式；是否纳入后续对照需Owner确认，没有新实验安排 |
| 简单sim几何能否增强泛化 | 参数化中心线×截面可表达关键因素，现实存在形态先例；尚未证明七族sim可抓或策略泛化 | 支持。厂家形态、静态几何、给定真值目标的Teacher控制、Student感知与实机效果须分别解释，不能串成保证链 |

**本轮已落实的是归档、事实核对和讨论入口。Pro提议的h、直径、roll、长度、return、饰盖及权重均未自动进入已批准参数。** B04/B05继续勾选方案完成；B02独立ablation、B03后置、D023原奖励和N02归属保持。

## 2. 材料与当前版本对照

原ZIP来自Owner当前对话附件，442923 bytes，原名`pro_delivery__full_review (3).zip`；五份要求文档及静态计算JSON、Worker原图共七项均保留在`original/`。附件内接手文本作为回包内容保存，执行范围以Owner本轮请求为准。没有从Drive查找答案、执行附件代码或下载其远程厂家图片。

送审分支`codex/v29-b05-pro-20260918`的提交主题/时间与回包声明相符：`Approve seven-family v29 B05 handle plan and prepare Pro review`，`2026-09-18T21:46:23+08:00`。本地工作分支为A2_Piper；在本轮文档整合前对35项输入中的34个项目路径逐字节比较，32个一致，只有v29 README和decision_log增加了送审后的D027交付记录。当前相关source/config、URDF/三件夹爪mesh、七族规格/参数/图、plan/TODO均与送审输入一致，没有发现需要用旧包覆盖的较新实现。依赖快照单独核对记录见[输入比较](LOCAL_INPUT_COMPARISON.json)；不据此声称整个工作区与审阅分支相同。

## 3. 局部重复与有限指宽：静态数值得到支持

Main直接读取既有families.json，在`sg±28mm`范围内将中心线移至G并对齐G切线；没有执行会重写图/资产的生成脚本。与Pro的计算在显示精度内一致，原始数值见[本地计算](LOCAL_STATIC_COMPARISON.json)。56mm是全指切向包络参照，不是实测接触斑。

| 族/量 | 本地读数 | 可以支持什么 |
|---|---:|---|
| F3相对G切线残差 | 0.979667mm；切向约±4.01047° | 圆截面相同但有限范围内有持续曲率；精确圆弧公式得0.979600mm，微差来自离散样点，不是接触误差 |
| F4相对G切线残差 | 1.099706mm；相对切向最大变化约6.39113° | 给定G的−8.25°姿态仍不等于把整段变成直杆；F4仍为圆截面 |
| F5相同范围 | 中心线残差0、圆径26mm | I内局部接触形状与直圆杆高度重叠，端部/轴颈关系与视觉/力臂仍可不同 |
| F6相同范围 | 直径约24.78765–27.21235mm | 约2.42471mm的沿程厚度变化，不能只用G处26mm判定完全重复 |
| F1/F2理想截面 | F1闭合极点曲率半径19.6mm；F2标称平面段18mm | 支持曲面与平面差别，不是实际接触面积或握持稳定性证明 |
| F5的G到handle轴半径 | 70.45566mm，F0为62.5mm | 可存在力臂混淆；不能把全部效果都归为“偏置族” |

Pro提出约0.25mm几何离散误差目标，目的在于不抹掉约1mm曲率信号。它只是工程建议，不是本地验收门槛，亦不等于求解器接触分辨能力；本轮没有读回PhysX接触参数或更改collision。

## 4. 站距、指体前伸与roll：支持计算，保留适用条件

只读几何核对将当前URDF引用的gripper_base/link7/link8原始STL变换到gripper-base。两指q=0时最大Z为135.8mm，TCP为85mm，前伸50.8mm；全开至±.035m时为50.799871mm，微差来自URDF的1.5708近似。gripper_base最大Z约63mm，位于TCP后22mm。开合沿局部Y、左右目标均保持局部+Z映射到门侧接近a，所以不改变这一工程量级。依据：[URDF](../../../../gr00t/rl/data/robots/a2_piper_v29_merged_20260917/a2_piper.urdf)、[TCP配置](../../../../gr00t/rl/config/env/door_open_a2_base.yaml)。

当TCP恰在G、+Z严格垂直门面，`h−50.8`是这组原始指部几何对无限门平面的最小有符号距离：h77.5时26.7mm，候选h55时4.2mm。固定姿态沿a直线接近时，终点的该平面距离最小。它不覆盖姿态误差、非直线接近、饰盖、return、腕机/其余机器人几何、导入后碰撞及执行扫掠。因此h55是待决定的工程下界，不是已证明可抓或“保守通过”的边界。

Pro建议F1/F2只旋转物体截面，G仍按朝轴颈t、门侧接近a和`R=[−t,t×a,a]`生成。椭圆与圆角矩形的方向支撑宽度公式正确；该方案自洽。roll不改变此处指体的50.8mm法向前伸，却改变物体闭合厚度、法向占据及局部接触。当前设计中“同步目标框架”不能被理解为无条件让G追随薄轴：数据一致性与抓姿选择是两件事。**现行标称φ=0不变，Pro保持G法向的roll规则仍待Owner批准。**

I/J/G仍采用已确认口径。`J=[s0+31,s1−31]`是静态一维候选区，不能命名为已验证的三维可抓集合。弯杆、return与饰盖的完整可插入区域仍未知，不因非空J移除实际几何问题。

## 5. Return与新增饰盖的范围

当前50%概率、40–60mm直Cylinder回返已经存在。Pro新增建议是圆滑90°弯头与关联站距的构造：R20–30mm，直尾b≥0，法向中心线回返H=R+b，候选`H∈[R,min(60,h−r_tip−8)]`。R/H/b分别为曲率半径、法向回返和直尾长，不互换；r_tip由实际端帽读取。弯头还增加约R的切向投影，匹配总包围长度时须调整起弯位置并重新计算I/J。

该末端—门面8mm约束不能代替指体—return间距，参数组合也不能各自独立采样后默认可行。回钩不进入I/J、不作为挂住成功的新抓法。七族仍采用一个door_handle刚体、双指contact语义；所有这些是设计建议，本轮未改资产。

Pro提议的近轴饰盖为门板上的单个Ø54×6mm薄圆柱，不增加DOF或可抓handle body。它是新的邻近障碍建模，**不属于七族已批准标称的自动组成部分**，须单独获Owner确认。当前随机keyhole不是同轴rose。原生成器轴/两杆/两钩组件名义质量合计无钩0.4、有钩0.5kg得到source支持；该加和不是本轮PhysX总质量/惯量读回，也不是真实材料密度证据。

## 6. 现实来源：新增关键字段已核，其他原文保留级别

Pro整理13例现实产品，但本轮本地只复核会影响主要建议的ASSA L/U、FSB1294跨语言冲突和FSB1107组合先例；不重新审计全部图册。原厂字段与条件计算分开，其他条目依[Pro原始来源表](original/SOURCES.md)的读取状态保留，不升级为本地全量核验。

| 核对对象 | 本地可确认的厂家信息 | 不能推出什么 |
|---|---|---|
| [ASSA Nordic L](https://www.assaabloy.com/uk/en/solutions/products/door-furniture/scandanavian-lever-and-pull-handles/scanflex-range/lever-handles/nordic-l-lever-on-rose) | 杆径19、length135、projection62、rose Ø54/突出6mm | projection起算面/箭头未读到，不能直接写h=62或52.5mm；135也不是中心线弧长或I |
| [ASSA Nordic U](https://www.assaabloy.com/uk/en/solutions/products/door-furniture/scandanavian-lever-and-pull-handles/scanflex-range/lever-handles/nordic-u-lever-on-rose) | 杆径19、length142、projection64、rose Ø54/突出6mm，圆形回返到门侧 | 不能推出return半径、tip gap或h；只能把它们作为待测量字段 |
| FSB1294[英文页](https://www.fsb.de/en/products/designed-by)/[德文页](https://www.fsb.de/produkte/designed-by) | 英文描述向外展开，德文描述向外渐细，冲突确实存在 | 只采用沿程变截面的共同信息，不择一证明28→24或反向锥度 |
| [FSB1107](https://www.fsb.de/produkte/produktfamilien/fsb-1107) | 高椭圆握段与弯曲造型的定性现实先例 | 不提供X1的R400、弯曲平面、轴长/站距或可抓区；X1仍是工程组合 |

HOPPE本轮Pro没有成功读取图纸，FSB1144的S叙述属于早期设计史，GEZE产品名中的oval指饰盖；这些原文已明确降级，不将旧种子数值补成已核厂家测量。h55–85、roll域、λ、return R/H/gap均是ENGINEERING，厂家projection只能提供方向性动机。

## 7. Teacher观察与泛化解释

当前actor/critic列表均含`gripper_handle_transform`和`privileged_door_info`。前者是handle/pregrasp两组相对位置和6D旋转共18维；后者8维包括门宽/高、安装高/横向位置、质量/100、左右标记与开门方向，其中door_handle_width不是杆径。没有直接加入族ID、局部曲率或完整截面参数。common的`enable_cameras=false`，actor无图像输入。相关依据：[观察列表](../../../../gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml)、[getter](../../../../gr00t/rl/envs/door/door_open_a2_base.py)、[common](../../../../gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml)。

所以Pro“目标位姿真值可消去部分对准难度，但截面/曲率仍影响接触”的解释得到source支持。Teacher给定目标后的控制能力，不等于Student从图像恢复该目标；几何外观只有实际进入Student数据后才提供视觉训练信号。本轮没有新增观察/网络，也没有任何训练效果裁定。

## 8. 待Owner决定的完整建议清单

以下均保持**PROPOSAL / NOT_APPLIED**；主方案七族和原标称仍有效。Main建议优先讨论站距、截面方向与条件return，其余保留为同一份候选配方，不要求一次全部启用。

| 提案 | Pro数值/规则 | Main判断与当前状态 |
|---|---|---|
| 族权重 | 七族各1/7；hook维持1/2 | 简单工程初值可讨论；五个圆截面族合计5/7不等于五种独立机制。未批准新权重 |
| 站距h | 55–85mm；门厚40时完整A150–210mm，保留h77.5锚点 | 有实际覆盖价值，55只有4.2mm理想平面余量；须明确这是扩域候选而非可抓认证。原A180–210不变 |
| 截面尺寸 | F0/F3/F4/F5 dG19–30；F6 dG21–28、根/端±2；F1/F2横截面k .85–1.10 | 19有厂家实例；范围及统一配方为工程选择，未替换原尺寸 |
| 非圆roll | F1/F2 φ∈[−90°,90°)，物体截面转，G保持门法向接近 | 自洽且区别于追随薄轴的抓姿选择；待确认 |
| 平面尺度λ | `[max(.90,65/|I0|),1.10]`，中心线/I同步缩放 | 保留I≥65的既有一维参照；不是完整可抓条件，未批准连续域 |
| 圆滑return | R20–30；H按h/实际端帽/gap条件构造 | 有价值的几何细化，属于明确改变旧直回返，待确认；保留内空隙和总长口径 |
| 同轴饰盖 | 门板上Ø54×6mm薄圆柱 | 参数有厂家实例；新障碍不能自动加到七族，单列待确认 |
| X1未见组合 | F3中心线×F1椭圆截面，h77.5、φ0、无return，沿用F3 I/J/G | 仍是lever操作，可检验因素组合；只登记候选，不加第八训练族、不安排实验 |

未来若开展对比，圆杆与七族应共享共同尺寸/站距域及相同数据量，避免把更多数据或扩域收益误算为族数收益。这只是解释性建议，不新增预算、种子、测试矩阵或训练启动条件。
