# v29 B02/B04：两份独立Pro回包

更新：2026-09-18 19:45 HKT。状态：**ARCHIVED / TARGETED_SOURCE_RECONCILED / OWNER_DECISION_PENDING**。

Owner在当前对话上传两份独立决策结果。本目录按附件编号保存，不推测具体模型身份；原ZIP及全部解压文件保留原名、原文。接收记录见[RECEIPT.json](RECEIPT.json)。

| 编号 | 原ZIP | 原始结论与设计 | 原始解析指引 |
|---|---|---|---|
| Pro1 | [pro_delivery__full_review-1.zip](pro_1/pro_delivery__full_review-1.zip) | [FULL_REVIEW](pro_1/original/FULL_REVIEW.md) · [DESIGN_SPEC](pro_1/original/DESIGN_SPEC.md) · [PARAMETERS](pro_1/original/PARAMETERS.json) | [LOCAL_WORKER_PARSE_PROMPT](pro_1/original/LOCAL_WORKER_PARSE_PROMPT.md) |
| Pro2 | [pro_delivery__full_revie-2.zip](pro_2/pro_delivery__full_revie-2.zip) | [FULL_REVIEW](pro_2/original/FULL_REVIEW.md) · [DESIGN_SPEC](pro_2/original/DESIGN_SPEC.md) · [DESIGN_PARAMETERS](pro_2/original/DESIGN_PARAMETERS.json) | [LOCAL_WORKER_PARSE_PROMPT](pro_2/original/LOCAL_WORKER_PARSE_PROMPT.md) |

共同选择是B02 **A：软件虚拟锁闩＋原生门轴约束**、B04 **原生joint limit，正常最大角U(90°,150°)**。两份对把手行程/回位负载、物理步时相和释放奖励/阶段条件的设计不同，不能视为整套参数已达成一致。完整对照、采用/调整建议及本地未知统一见[LOCAL_RECONCILIATION.md](LOCAL_RECONCILIATION.md)；当前计划见[baseline plan §5–6](../../../v29/a2_piper_base_v29_baseline_plan.md)。

来源仓库为[DoorDog](https://github.com/Jam-Stark/DoorDog)，review分支`codex/v29-b02-b04-pro-20260918`，提交主题`Prepare v29 B02 and B04 Pro decision handoff`，提交时间`2026-09-18T17:14:54+08:00`。原输入/交付记录见[handoff入口](../../../v29/pro_handoff/20260918_b02_b04/README.md)。本次答案仅取Owner附件，未去Drive查找结果。

[LOCAL_SOURCE_ALIGNMENT.json](LOCAL_SOURCE_ALIGNMENT.json)记录本轮文档更新前的逐字节对照：34个输入路径中32个相同，包括全部受核source/config；差异仅为本地较新的v29 README与decision log交付记录。当前工作区已有改动得以保留，未用review分支覆盖工作区。

本轮只完成原包保存、阅读与source/config/本机IsaacLab/已有runtime的定向核对，并更新计划、TODO和D019。原文静态检查文件保持原样，未作为本机测试执行；其中PASS不能证明物理运行或训练。未实施B01/B02/B04、启动训练/仿真/render、添加测试、提交Git或更新Teacher/G7。B02/B04仍待Owner确认；B03保持15°并后置到baseline出来后，B01三档各1/3×closer有无各半沿用。无本轮活动运行或占用资源。
