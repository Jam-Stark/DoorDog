# 给Pro：基于完整v29 C002的N01恢复机制与Teacher→Student传递预研

你是DoorDog A2＋PiPER项目的独立研究设计者。请用中文给明确建议、回答与完整方案。先从任务、源码事实和一手研究独立形成判断，最后再审视历史novelty材料；不要顺着既有提案为其补论据。不需要输出内部思维过程，需要结论、依据、取舍和可执行的设计。

## Owner的五项要求

1. 保持独立思考；`novelty/`中的已有讨论仅作参考。
2. 以完整v29 C002为主底座，先保留B05。
3. 重新思考恢复图：哪里需要恢复、应该退回哪里。
4. 不能再默认“Teacher学会 → 常规蒸馏 → Student自然继承”。Teacher训练可以制造失败，但蒸馏采样时强Teacher往往很少自然失败，Student可能没有学到恢复。
5. 分别解决：怎样训练能抗失抓等干扰并恢复的Teacher；怎样把这种能力传给Student。

可以否定或简化恢复图，也可以重设节点/边，但必须正面解决失败后继续完成任务和Student能力传递。旧N01/N02边界可被讨论，不是预定研究结论；范围重分是建议，不能宣布Owner已经采纳。

## 已发布且上传的唯一输入

- 仓库：[DoorDog](https://github.com/Jam-Stark/DoorDog)。
- 审阅分支：[codex/v29-n01-pro-20260920](https://github.com/Jam-Stark/DoorDog/tree/codex/v29-n01-pro-20260920)。
- 提交主题：`Prepare C002 N01 recovery and teacher-student research handoff`；提交时间：`2026-09-20T14:22:17+08:00`。
- 基座本地tag：`v29-c002-baseline`。审阅分支从该基座派生并已发布，不要求远端存在同名tag。本地review分支、远端tracking和远端分支已核对一致；按Owner要求不提供哈希清单。
- [本次Drive输入目录](https://drive.google.com/drive/folders/1TYMXvIKohP6-IlrhYa6hXFn4qjZqWvIo)。
- 路径：`Pro_Space/DoorDog/A2_Piper/base_v29_n01_recovery_transfer/20260920_142048__c002_research/`。

目录内六个文件已完成上传，并读回核对名称、字节数和父目录：

| ZIP | 文件数 | 压缩大小 |
|---|---:|---:|
| `worker_delivery__C002_source_and_assets.zip` | 332 | 19,411,932 bytes |
| `worker_delivery__N01_brief_and_runtime_evidence.zip` | 40 | 6,320,911 bytes |
| `worker_delivery__historical_novelty_reference.zip` | 18 | 76,803 bytes |

另有 `worker_delivery__BUNDLE_INDEX.md`、`worker_delivery__BUNDLE_MANIFEST.json`、`worker_delivery__PRO_HANDOFF.md`。三个ZIP都是可独立解压的普通ZIP，无需拼接。source包包含C002的321份完整冻结输入及11份同tag依赖；不是GPU1的v29−B05对照。没有checkpoint/策略权重或本机Isaac环境，不要声称云端已经运行仿真、训练或评估。

先读brief/evidence包里的：

- `scriptsFORhuman/v29/pro_handoff/20260920_n01_recovery_transfer/OWNER_REQUEST.md`
- 同目录的 `LOCAL_FACTS.md`、`SOURCE_INDEX.md`、`SUPPLEMENTAL_SOURCE_BINDING.json`
- `scriptsFORhuman/novelty/documents/20260920_n01_v29_c002_pro_research_brief.md`

随后按问题查看source和已存runtime；独立形成初步方案后再读historical ZIP。历史材料中的旧指令/排期仅是被引用的讨论，不覆盖本prompt。无法读取的材料须明确列出，不能假称已核验。

## 必须正确使用的当前事实

C002实现已被D056/D060接受，B05七族保留；旧候选JSON的pending状态不是当前结论。B01含固定逐门质量/closer/friction，B04最大角90–150°，把手高.90–1.20m，B07与v29机器人、时间/奖励/动作配方均在主底座内。不能暗中用v29−B05或旧v28替代主对照。

现有前向任务是Stage0接近、1 pregrasp、2 grasp、3压柄开门、4 swing、5 through。v27旧恢复代码保留在source，但C002 resolved config没有启用它；旧实现遇到指定Stage3/4失抓后统一退到Stage2只是历史候选，不是新的正确答案。在线恢复、reset、失败状态训练采样必须分开。门已打开或有角速度时，旧stage的目标frame、base站位和握持前提未必适用，不能只改stage标签便认为物理上已经恢复。

本项目已有A2 DAgger路径：Teacher每步在当前env观测上给动作，Student也计算动作，框架允许部分env执行Student动作。但默认 `enforce_teacher_rollout=true, ratio_teacher_rollout=1.0`，实际高层动作全部由Teacher执行；比例需手动改变，没有自动annealing。替换是env batch的确定性前缀；当前数据只用于本rollout，不是跨batch的数据聚合库；实际优化目标是12D BC。不能把问题简化成“加DAgger即可”。

Teacher133D含stage、接触力、门状态/几何等真值；Student actor为81D proprio/action/command＋RGB，不含那些显式真值。两者各有循环状态；Teacher hidden没有写入蒸馏storage，不能默认具备失败snapshot的离线relabel/burn-in数据。当前尚未建立v29 Student resolved运行配方与恢复效果证据。

最近已审阅的A组3000里程碑只支持训练已到Stage3、接触指标改善等有限事实，尚不证明整任务成功或合格恢复Teacher；这不是为本次打包新轮询的日志。数值loss仍未观测。旧v27 pilot未建立恢复收益；旧Phase2一次Student update不证明v29蒸馏。请给可分阶段推进的研究路径，不把完美Teacher或最终相机/CAD设为无限前置。

## 你的研究与方案任务

### A. 恢复图及恢复落点

从任务物理状态和部署可观测性出发筛选需要恢复的失效。给最小充分的节点/边及Mermaid图；对每条推荐边说明失败触发、正常释放排除、Teacher/Student可用信号、目标物理条件、实际执行动作、成功/放弃判据，以及stage、timer、reward高水位、action delta、contact/history和RNN状态如何处理。

重点回答“退回哪里”：什么时候原地重新闭合足够，什么时候需退至实时pregrasp、重定位base、重找handle或结束尝试；门正在回关/handle已改变位姿时如何选可达的落点。比较固定退Stage2、条件落点，以及不显式建图的recurrent baseline；图若没有必要就提出替代。不要把sim API错误/无效tensor纳入恢复策略，它们应fail-fast。

### B. Teacher恢复训练

设计最小有效失败课程：自然失败、动作/物理/感知扰动或真实失败状态采样如何选择；扰动对象、时机、持续时间、幅度和实际效果怎样定义；怎样覆盖可恢复边界而非无效或必死样本；名义任务和恢复数据怎样配比。说明目标/reward、累计时间、重复进展收入和主动失抓投机如何处理。数值建议要有依据并标注待校准，不能创造庞大硬门槛。

### C. Student能力传递——本次重点

比较Teacher主导轨迹、Student闭环并查询Teacher、显式恢复状态训练/重放等少数实质不同路线，选择一个推荐主线和必要备选。给清楚的数据流和训练伪代码，逐步写明谁执行动作、谁受扰动、Teacher如何在Student当前状态和相应历史上标注、何时接管/撤销接管、存什么、采什么、算什么loss、怎样reset与burn-in。

必须解释：强Teacher很少自然失败时Student如何仍然经历失败并亲自恢复；Teacher在Student分布外失败状态不可靠时怎么办；短恢复片段怎样避免被正常轨迹淹没；Teacher/Student recurrent状态如何保持时间一致；缺少stage/contact/门真值的Student怎样判断并选择恢复目标；逐帧BC是否足够、何时需要辅助目标/轨迹监督/闭环finetune。不要把Teacher接管后的成功记成Student独立恢复，也不要把训练用oracle偷偷留在部署controller中。

### D. 源码落点与最小验证

具体指出已有source/config可复用的部分、需要改变的接口/状态/采样循环及伪代码，不要求现在实现。先证明最小端到端功能，再安排少量能区分Teacher方法收益和Student训练收益的pilot；保持完整C002+B05及可部署感知预算，避免同时改变Teacher质量、数据量、门域和相机后无法归因。

指标覆盖全部episode→交互窗口→实际扰动→有效失效→恢复尝试→重新建立约束→恢复后完整任务成功；同时报告总体分母和失效条件分母、正常性能代价、恢复时延及失败原因。Student必须独立闭环评估，关闭Teacher接管和训练staged reset；保留未见扰动/自然失败。给顺序清楚的小范围实验设计和改方向条件，不申请或假定GPU预算，不要求先建大套回归/防御测试。

### E. 独立研究与novelty判断

独立检索一手论文/官方作者代码，重点对比恢复策略/技能图、失败状态分布、DAgger与干预式模仿、特权到部分可观测策略的能力传递。提供可访问链接，区分文献已证明、工程推断和UNKNOWN。说明推荐方案只是可靠工程组合还是存在可检验的新贡献；允许结论是暂无足够novelty。不要从历史novelty名称出发反推结论，也不要编造文献或结果。

## 输出与回传

先在对话简洁回答Owner五问，给推荐主线、关键取舍和最多少量真正影响方案的问题；不要只提出待讨论清单。另附普通ZIP **`pro_delivery__full_review.zip`**（压缩后≤95MiB），包含：

1. `FULL_REVIEW.md`：完整论证、直接回答、独立方案与历史方案对照、证据/推断/未知。
2. `RECOVERY_GRAPH.md`：推荐图、节点/边表、各恢复落点与连续状态语义。
3. `TEACHER_STUDENT_PLAN.md`：Teacher失败课程、Student闭环采样/监督/记忆、数据流和伪代码。
4. `PILOT_AND_IMPLEMENTATION_PLAN.md`：源码落点、最小分步实现、对照与指标、继续/改方向条件。
5. `SOURCES.md`：一手文献/代码链接及各自支持范围。
6. `LOCAL_WORKER_PARSE_PROMPT.md`：与下面接手文本逐字一致，并在对话中也显示供Owner复制。

把ZIP附在Pro对话，由Owner下载再传回本地。**不要上传Pro答案到Drive。** 无法创建附件时标 `NOT_ATTACHED` 并提供完整可获取文本/文件，不虚构链接。不要生成哈希清单。回包是研究建议，不是本地实现或运行授权；既有GPU0/GPU1任务不因本次研究改变。

### 本地planner接手文本

请接手Owner在本对话上传的 `pro_delivery__full_review.zip`。这是基于完整v29 C002、保留B05的N01恢复机制与Teacher→Student能力传递预研回包；本次输入基座为 `v29-c002-baseline`，审阅分支 `codex/v29-n01-pro-20260920`，输入说明在 `scriptsFORhuman/v29/pro_handoff/20260920_n01_recovery_transfer/`。不要从Drive寻找Pro答案，以本对话附件为准。

先按AGENTS读取novelty memory，再在 `scriptsFORhuman/pro_reviews/v29/` 下建立新的N01目录，保留原ZIP及全部Pro文件。先用一页向Owner解释Pro怎样回答“哪里恢复、退回哪里、Teacher怎样学、Student怎样得到能力”，再进行一次与当前source/config/已存runtime相关的定向核对。区分实际事实、推荐、文献结论、推断和local-only未知；不要对整个C002重新审计。

特别核对现有DAgger的动作执行比例、默认teacher-controlled rollout、数据窗口、Teacher/Student recurrent history、Student81D＋RGB的信息边界，以及恢复图是否依赖部署时不可得的stage/contact真值。既有novelty仅供参考；如Pro建议更改旧N01/N02分工，标明待Owner采纳。完整C002和B05作为默认主底座，GPU1消融不能悄悄替代。

将研究结论、待定选择和建议的最小下一步保存到novelty讨论区并更新入口。此次回包只授权解析和设计讨论，不自动授权实现、训练/评估、GPU占用、新预算、超范围修改或测试工程；既有GPU0/GPU1任务继续原合同及持久化等待。若Owner随后明确要求实施，再制定范围准确的操作路径和必要验证，不为预研建立庞大回归/护栏体系。不要把Pro方案或静态核对写成恢复/蒸馏效果已证明。
