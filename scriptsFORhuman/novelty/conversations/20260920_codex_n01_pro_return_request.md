# Codex：N01 Pro回包解析请求摘录

时间：2026-09-20 15:33 HKT。来源：Owner在本Codex任务上传附件后的请求。范围：以下为该条Owner请求原文；不包括整段会话、工具输出或内部推理。研究回应见[结论与下一步](../documents/20260920_n01_pro_review_and_next_step.md)。

附件：`/home/baoquanc/.codex/attachments/f174a06b-5bee-4d45-b0ae-8935f66b80a7/pro_delivery__full_review (4).zip`。原件已按Owner要求另存至[回包目录](../../pro_reviews/v29/20260920_153418__N01_recovery_transfer/README.md)。

## Owner原文

请接手Owner在本对话上传的 `pro_delivery__full_review.zip`。这是基于完整v29 C002、保留B05的N01恢复机制与Teacher→Student能力传递预研回包；本次输入基座为 `v29-c002-baseline`，审阅分支 `codex/v29-n01-pro-20260920`，输入说明在 `scriptsFORhuman/v29/pro_handoff/20260920_n01_recovery_transfer/`。不要从Drive寻找Pro答案，以本对话附件为准。

先按AGENTS读取novelty memory，再在 `scriptsFORhuman/pro_reviews/v29/` 下建立新的N01目录，保留原ZIP及全部Pro文件。先用一页向Owner解释Pro怎样回答“哪里恢复、退回哪里、Teacher怎样学、Student怎样得到能力”，再进行一次与当前source/config/已存runtime相关的定向核对。区分实际事实、推荐、文献结论、推断和local-only未知；不要对整个C002重新审计。

特别核对现有DAgger的动作执行比例、默认teacher-controlled rollout、数据窗口、Teacher/Student recurrent history、Student81D＋RGB的信息边界，以及恢复图是否依赖部署时不可得的stage/contact真值。既有novelty仅供参考；如Pro建议更改旧N01/N02分工，标明待Owner采纳。完整C002和B05作为默认主底座，GPU1消融不能悄悄替代。

将研究结论、待定选择和建议的最小下一步保存到novelty讨论区并更新入口。此次回包只授权解析和设计讨论，不自动授权实现、训练/评估、GPU占用、新预算、超范围修改或测试工程；既有GPU0/GPU1任务继续原合同及持久化等待。若Owner随后明确要求实施，再制定范围准确的操作路径和必要验证，不为预研建立庞大回归/护栏体系。不要把Pro方案或静态核对写成恢复/蒸馏效果已证明。

最后给我一个N01方向planner任务的handover prompt（不要落成文档），我将单开一个session 负责N01 planner职责
