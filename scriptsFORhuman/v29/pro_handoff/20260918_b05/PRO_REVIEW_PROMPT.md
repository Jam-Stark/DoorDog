# 给Pro：七族handle设计的重复、扩展与现实覆盖审阅

你是DoorDog A2+PiPER项目的独立Pro设计审阅者。请完成下面三项研究并给明确建议，中文回答。关注sim模型简单、接触因素有效覆盖与可解释的泛化假设；不需要实现代码、运行训练或输出内部推理过程。

## Owner最新决定

Owner已确认F0–F6七族全部进入v29 baseline plan：圆直杆、椭圆直杆、圆角扁直杆、单弧轻弯杆、浅S杆、偏置直腹杆、缓变锥度杆。B04/B05均按“设计确认并写入plan”标记方案讨论完成。此前F0–F3优先、F4–F6后续的拆分已取消。

Owner要求你审阅：

1. **设计是否有实质重复？**
2. **是否还需要扩展构型？**
3. **搜集现实handle对比：如何在sim模型设计简单的情况下增强泛化能力，当前证据能否保证这一点？**

请独立判断。你可以建议合并、调整或新增，但必须列为对已确认方案的明确修改建议，不能把本地已批准的七族静默改掉。族概率与连续尺寸域尚未批准，可提出最简合理工程配方，不把工程分布称为现实市场概率。

Main的默认职责是planner：没有Owner明确要求，不进行代码实施或训练监督。本次回包也只进入设计解析与讨论。

## 已发布和上传的输入

- [仓库](https://github.com/Jam-Stark/DoorDog)
- [独立审阅分支codex/v29-b05-pro-20260918](https://github.com/Jam-Stark/DoorDog/tree/codex/v29-b05-pro-20260918)
- 提交主题：`Approve seven-family v29 B05 handle plan and prepare Pro review`
- 提交时间：`2026-09-18T21:46:23+08:00`；本地review分支、远端tracking和远端分支已核对一致，按Owner要求不提供哈希清单。
- [本次唯一Drive输入目录](https://drive.google.com/drive/folders/1VJ-lhwltmidIGWbASzv4sTPtI3NwXZBZ)
- 路径：`Pro_Space/DoorDog/A2_Piper/base_v29_b05_handle_review/20260918_214440__b05_handle_review/`

五个文件已完成上传及名称、字节数、父目录读回核对：

| 文件 | 内容/大小 |
|---|---|
| `worker_delivery__BUNDLE_INDEX.md` | 阅读入口 |
| `worker_delivery__BUNDLE_MANIFEST.json` | 35个选定文件、来源与证据范围 |
| `worker_delivery__PRO_HANDOFF.md` | 交付说明 |
| `worker_delivery__source_and_configs.zip` | 347849 bytes；22个文件 |
| `worker_delivery__geometry_and_reference.zip` | 804432 bytes；13个文件 |

两个都是可独立解压的普通ZIP，不需拼接；项目文件保留repo相对路径。分支继承的其他阶段文件不自动属于本次审阅，以本次manifest为准。如果无法读取某项，明确列出未读材料，不假称核验完成。

先读source包`scriptsFORhuman/v29/pro_handoff/20260918_b05/OWNER_REQUEST.md`、`REVIEW_BRIEF.md`、`SOURCE_INDEX.md`以及`scriptsFORhuman/v29/a2_piper_base_v29_b05_handle_design.md`。对照geometry包`scriptsFORhuman/v29/b05_designs_20260918/`下PNG/SVG、families.json、geometry_readout.json和绘图脚本。独立初判后再读REAL_WORLD_SEEDS.md和历史Pro形状建议，继续核实一手厂家来源。

## 1. 重复性：区别外轮廓与实际接触

比较七族的整体轮廓/视觉差异、G邻域截面和曲率、局部闭合厚度/接触面、可插入区域、门板站距、有效自由段与抓握姿态。不能仅凭“有七个名字”认为覆盖七种独立机制，也不能只因截面相同就判为完全相同。

F0/F3/F5在标称G处为圆径26mm，F6在G处也约26mm；F3中心切向接近平直但有连续曲率，F5是抬高8mm的直腹，F6沿杆缓变。F4圆径24mm且G处倾斜约−8.25°；F1/F2是椭圆/圆角扁截面。F4/F5并不是扁杆。判断哪些差别可由实际指体接触察觉，哪些主要是外观、位置或被目标frame直接给定的姿态变化。

结合当前Teacher观察与真值目标接线，说明几何随机化对控制与视觉感知分别可能提供什么；不要把Teacher使用几何真值时的表现等同部署Student的识别与泛化能力。给紧凑对照表、冗余/互补判断和建议，允许“局部接触高度重叠但仍有视觉/净空差别”的结论。

## 2. 扩展：最少必要构型或参数轴

明确回答是否值得新增，若是，给最少量且有独立价值的新增项。优先判断长度/厚度、截面方向、法向站距、回返形状/净空等连续变化是否比增加族名更有效。

新增建议要说明现实依据、中心线×截面的简单表达、自由主握段I、TCP中心候选J、G的位置/朝向、collision近似及增量复杂度。避免全形凸包填掉回钩内空隙，也不要求精细复刻锁体、装饰纹理或所有产品CAD。旋钮、拉环、推杠等若改变操作方式，单列为超出当前lever baseline的方向。

给完整七族保留/调整/合并/新增的推荐组合，以及必要的简单尺寸/采样建议。现有标称尺寸是工程选择；如果建议更改，逐项写出原值、推荐值/范围、理由和来源支持程度。

## 3. 现实对比与泛化判断

搜集代表性厂家产品、官方技术图纸或CAD，以链接及必要图示建立现实handle对照。包内七个种子包括FSB 1147/1108/1226/1144/1230/1294与HOPPE Trondheim；它们是起点而非预定结论，很多只有定性形态，部分只是设计历史或局部渐变。

对每例写品牌/型号、原厂URL、可靠可读的尺寸/截面/曲率/偏置/站距/return信息、与七族的映射及未覆盖点。没有图纸就只做定性判断；不要从照片推断精确尺寸，也不要把产品整体包围尺寸当中心线弧长或曲率半径。明确厂家实测/标注、计算推断、工程假设和UNKNOWN。

分别回答：外形有无现实先例；简单几何是否覆盖关键接触/净空因素；当前是否已证明sim可抓；是否已证明未见型号或sim-to-real泛化收益。当前只有source与标称设计证据，不能以“七族都有外形参照”保证泛化。仍需给出明确、可执行的设计推荐，不以缺少训练结果代替设计判断。

最后仅给少量必要的后续验证建议，用于区分几何扩域收益与训练数据量/参数域变化，例如同等设置下的未见产品几何对比。不要新增训练预算、庞大测试矩阵或云端无法核实的本地验收门槛。

## 必须保留的本地事实

- 当前源码仍只有圆杆；50%概率、40–60mm回返已存在。多族尚未实施，类型枚举不等于几何已实现。
- Capsule的110–140mm为轴段，半径11–15mm，含帽132–170mm；完整axle180–210mm。标称A195、门厚40使握杆中心距选定门面77.5mm，实际表面净空还须扣截面/指体/动态扫掠，不能把77.5mm直接称净空。
- 七族主握段I约65–74mm，用56mm原始全指切向包络加每端3mm工程余量得到3–12mm中心候选J。该一维收缩不是曲杆的三维可抓性证明；实际指垫尚未标定。70mm差动行程不是净开口，45N配置不是实测接触力。
- `p=γ(s_g)`，t朝轴颈，a为接近方向，c=t×a，`R=[−t,c,a]`对应PiPER Y闭合/+Z接近；pregrasp局部−Z退100mm。拟由生成器统一输出目标及FixedJoint，consumer去掉对应旧旋转/LEFT补偿，尚未实施。
- 一个door_handle刚体、现有双指sensor/contact语义；visual/collision、质量/COM/惯量从相同组合几何一致表达。材料/摩擦与几何因素要区分，但本次不顺带修改其他动力学。
- B02后置独立ablation；B03保留15°后置；D023已恢复原hinge/hold_and_drive/grasp奖励；强回弹重抓把手归N02。本轮不重新选择这些内容。

三件夹爪mesh仅支持局部几何审阅，不是完整运行资产。包内没有checkpoint、B05训练日志、GPU或硬件证据；不得声称已运行仿真或确认成功率。

## 最终输出与回传

对话先按顺序简洁回答三问，再列最有价值的保留/修改建议、来源和必要未知。另附一个标准ZIP **`pro_delivery__full_review.zip`**（压缩后≤95MiB），含：

- `FULL_REVIEW.md`：完整比较、结论、证据/推断/UNKNOWN/local-only区分。
- `DESIGN_RECOMMENDATIONS.md`：推荐组合、必要修改/新增、参数与I/J/G方案、简单碰撞建模及工程取舍；不写实施代码。
- `REAL_HANDLE_COMPARISON.csv`或`.md`：现实型号、尺寸/形态、对应族/缺口、来源与数据类型。
- `SOURCES.md`：一手链接、访问日期及支持范围。
- `LOCAL_WORKER_PARSE_PROMPT.md`：与下方接手文本逐字一致，同时把它显示在对话中供复制。

请在Pro对话附ZIP，由Owner下载并传回本地。**不要将Pro结果上传Drive。** 不能附ZIP时标明`NOT_ATTACHED`并提供可获取文件，不虚构URL。不生成哈希清单。

### 给本地planner的接手prompt

请按项目AGENTS与memory入口接手Owner在当前对话上传的`pro_delivery__full_review.zip`。这是v29 B05七族handle独立审阅回包；来源仓库`https://github.com/Jam-Stark/DoorDog`，审阅分支`codex/v29-b05-pro-20260918`，提交主题`Approve seven-family v29 B05 handle plan and prepare Pro review`，提交时间`2026-09-18T21:46:23+08:00`。对应Worker输入目录`https://drive.google.com/drive/folders/1VJ-lhwltmidIGWbASzv4sTPtI3NwXZBZ`，但Pro回包以当前对话附件为准，不去Drive寻找答案。

在`scriptsFORhuman/pro_reviews/v29/`下建立新的B05审阅目录，保留原ZIP并提取FULL_REVIEW、DESIGN_RECOMMENDATIONS、REAL_HANDLE_COMPARISON、SOURCES及LOCAL_WORKER_PARSE_PROMPT。先读三问结论与推荐组合，再对照七族已确认规格、当前source/config及原始指部几何做一次有针对性的核对；明确厂家数据、工程假设、推断和local-only，保留Pro原文。重点看局部接触冗余、法向站距/净空、回钩、I/J/G与PiPER有向轴，以及推荐的新增是否超出lever操作范围。

Owner已确认七族全部进入plan，B04/B05的TODO按方案讨论完成保持勾选。你默认是planner：整理Pro的保留/合并/扩展建议供Owner决定，记录到计划/决策讨论入口，不静默删除或替换已批准族，不因代码尚未实施而撤销方案完成。未获Owner新的明确要求，不实施代码、修改资产或训练配置、不启动或监督训练、不添加大规模测试。B02独立ablation、B03后置、D023原奖励与N02归属保持；云端静态意见不升级为抓取、泛化或硬件PASS。当前source可能比审阅分支更新，核对相关差异，不覆盖较新本地改动。
