# Codex：N02 Pro回包解析请求摘录

时间：2026-09-20 HKT。来源：Owner在本Codex任务上传N02附件后的请求。以下为该条Owner请求原文，不是整个会话，也不包括工具输出或内部推理。

附件：`/home/baoquanc/.codex/attachments/2bb087c9-33d9-4d44-ae74-a83bf8a66fd6/pro_delivery__full_review (5).zip`。原件另存于[回包目录](../../pro_reviews/v29/20260920_162527__N02_online_adaptation/README.md)。分析结论见[研究文档](../documents/20260920_n02_pro_review_and_next_step.md)。

## Owner原文

请接手Owner在本对话上传的 `pro_delivery__full_review.zip`。这是完整v29 C002保留B05的N02预研回包，输入基座为 `v29-c002-baseline`，审阅分支 `codex/v29-n02-pro-20260920`，本地输入说明在 `scriptsFORhuman/v29/pro_handoff/20260920_n02_online_adaptation/`。Pro结果以本对话附件为准，不去Drive寻找答案。

先按AGENTS读取novelty memory，在 `scriptsFORhuman/pro_reviews/v29/` 新建N02目录保留原ZIP与全部文件。先向Owner简洁解释Pro认定的能力缺口、推荐估计/预测目标及它怎样改变控制，再做一次针对当前source/config/已存runtime的一致性核对。检查是否把网络问题当默认、是否将v27 shadow或论文结果外推C002、是否区分Teacher特权输入与Student部署输入、同窗估计与未来预测、实际/条件动作、Student自身轨迹和RNN历史。

重点分析Owner的近中性姿态/arm主导、有条件roll-pitch、controlled swing或quiet hold、强回弹时维持握持避免trunk碰撞目标：新增信息究竟能改变哪些动作，哪些还需要最小行为/奖励/训练暴露调整；能否把这些收益分开。UniFP和SixthSense是借鉴对象，不是fusion/flow-matching选型指令。N01恢复图尚未实施，双方接口和范围调整都只作为待采纳建议。

另检查Pro动力学/roll-pitch方向出力建模是否实际执行：保留modeling脚本、参数、results数据/图和执行记录；区分同一门坐标/TCP条件下的力上界、重力/足地/抓握约束、坐标旋转与真实能力变化。当前arm100N·m/finger45N是C002仿真配置，不是已确认硬件持续能力。Pro未运行时保持NOT_RUN，不把脚本存在当数值验证。结合建模结果重新判断N02感知目标与有条件姿态，不自动启动本地仿真或训练。

保留Pro原文与其迭代后的最终结论，分清source事实、文献、推断、UNKNOWN和local-only；整理少量真正影响下一步的选择，更新novelty文档/README/memory。此次回包仅授权解析和设计讨论，不自动授权N02方法实现、训练/评估、GPU占用、预算或新增测试工程；原GPU0/GPU1训练与持久化等待不变。Owner明确要求下一阶段后再落实最小功能路径，不能把云端方案写成已经证明的在线适应、Student收益或硬件能力。

最后同样给我一个N02方向planner任务的handover prompt（不要落成文档），我将单开一个session 负责N02 planner职责.
