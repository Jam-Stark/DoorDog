# N02在线适应与方向出力：Pro回包

2026-09-20 HKT。状态：**ARCHIVED_AND_FOCUSED_RECONCILIATION_DONE**。来源为Owner本对话附件，未从Drive寻找答案；主底座完整 `v29-c002-baseline`、保留B05，审阅分支 `codex/v29-n02-pro-20260920`。

先读[给Owner的简要解释](OWNER_BRIEF.md)，再读[本地定向核对与模型更正](LOCAL_RECONCILIATION.md)。长期研究结论和待决项见[novelty](../../../novelty/documents/20260920_n02_pro_review_and_next_step.md)。本地只有INSPECTED证据；Pro CPU模型有执行记录，本机未复跑。

**使用模型前注意：** 夹持模型遗漏单指法向合力上限，156条press_down敏感性记录不能按90N／36.4N解读容量；更紧必要界为45N／18.2N，仍属条件假设。原件全部保留；arm/足地/PD主表及水平夹持情景不受此遗漏影响。详见本地核对第4.3节。

## 完整原件

[Owner原ZIP](<pro_delivery__full_review (5).zip>)：510,523 bytes，46份文件，清单及原始大小见[RECEIPT.json](RECEIPT.json)。

| Pro原文 | 内容 |
|---|---|
| [原README](original/README.md) | 原运行命令与文件说明，作为材料保留，本地未执行 |
| [FULL_REVIEW](original/FULL_REVIEW.md) | 迭代后的最终研究结论 |
| [TARGET_AND_OBSERVABILITY](original/TARGET_AND_OBSERVABILITY.md) | 当前估计/未来预测、信息与数据人口 |
| [CLOSED_LOOP_CONTROL_PLAN](original/CLOSED_LOOP_CONTROL_PLAN.md) | 动作、hold/release、姿态及行为奖励建议 |
| [TEACHER_STUDENT_PLAN](original/TEACHER_STUDENT_PLAN.md) | Teacher/Student输入、实际轨迹、历史及训练 |
| [DYNAMICS_AND_FORCE_ANALYSIS](original/DYNAMICS_AND_FORCE_ANALYSIS.md) | CPU模型、假设、数值与限制；须连同本地更正阅读 |
| [PILOT_AND_IMPLEMENTATION_PLAN](original/PILOT_AND_IMPLEMENTATION_PLAN.md) | 待采纳步骤与source落点 |
| [REFERENCE_COMPARISON_AND_SOURCES](original/REFERENCE_COMPARISON_AND_SOURCES.md) | 文献与来源 |
| [SOURCE_EVIDENCE](original/SOURCE_EVIDENCE.md) | Pro保存的源码/已存runtime摘录 |
| [INPUT_AND_DELIVERY_AUDIT](original/INPUT_AND_DELIVERY_AUDIT.json) | Pro输入/交付自述 |
| [LOCAL_WORKER_PARSE_PROMPT](original/LOCAL_WORKER_PARSE_PROMPT.md) | 附件自带接手文本；不是本轮另要的新planner prompt |

模型入口为[run_analysis.py](original/modeling/run_analysis.py)，其余脚本、依赖和原输入均保存在同级modeling目录；全部结果入口见[RESULTS_INDEX](original/results/RESULTS_INDEX.md)。四张原图：[arm与支撑](original/results/01_arm_vs_supported_capacity.png)、[同20N扭矩](original/results/02_torque_at_same_20N.png)、[独立base平移](original/results/03_separate_base_translation.png)、[PD排序反转](original/results/04_pd_constraint_reverses_ranking.png)。CSV、JSON、NPZ和所有日志均未修改。

## 来源、权限与后续

- [返回模型输入及必要source的直接内容绑定](FOCUSED_INPUT_BINDING.json)
- [Owner本次原话](../../../novelty/conversations/20260920_codex_n02_pro_return_request.md)
- [原R2输入交付入口](../../../v29/pro_handoff/20260920_n02_online_adaptation/README.md)

本轮仅解析与设计讨论，没有N02方法实现、模型本机重算、测试工程、仿真/训练/评估、GPU或新预算，也没有Git提交/外部发布。N01图未实施；GPU0/GPU1原合同及等待不变。新N02 planner交接prompt仅在最终对话回复提供，不另建文档。
