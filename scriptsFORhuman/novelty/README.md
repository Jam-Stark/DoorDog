# Novelty 讨论区

创建：2026-09-10 HKT。维护者：与 Owner 讨论 novelty 的 AI session；由 Owner 决定方向与实验授权。

本目录集中保存选题讨论、独立判断、方法提案和证据索引。先读 [novelty memory](../../memory/a2-piper/novelty-research/description.md) 和 [当前状态](documents/20260910_novelty_status.md)，再按问题读取原对话。历史提案不覆盖当前 source、实验结果或 Owner 后续决定。

## 目录与维护约定

- `conversations/`：相关对话的人类可读原文或明确标注的摘录。注明平台、任务标题／会话 ID、时间、来源和选取范围；保留 Owner 原话及 AI 结论，区分原文与整理者补充。不收录内部推理、系统指令、工具原始输出或无关聊天。
- `documents/`：独立判断、方案、文献比较、决策和实验结果的分析文档。新产出默认放在这里；引用既有实验 artifact，不重复搬运大日志。跨阶段的执行 plan、长期 TODO 继续在原位维护，通过链接引用。
- 必要时可新建主题子目录，例如 `recovery/` 或 `interaction-history/`；按实际内容组织，不预建空框架。新增入口必须登记到本 README。
- 文件名建议 `YYYYMMDD_<topic>_<platform-or-author>.md`，沿用既有名称的迁入文件可保留原名。文档注明日期、作者、状态（提议／Owner 已批准／实验结论／已取代）、依据与未解决项。
- 每次产生有实质内容的 novelty 讨论，负责 session 在结束前保存可取得的对话、放置产出并更新本 README。只能取得片段时标明范围，不能用摘要冒充原文。
- 同步维护 [memory 三文件](../../memory/a2-piper/novelty-research/description.md)：`description.md` 保存当前可复用事实与路由，`TODO.md` 保存真实未决事项，`DONE.md` 保存已完成事项及证据。新决定取代旧决定时保留来源；普通讨论不自动变成已批准的实验。若没有新增 durable fact，明确保持原状态，不制造进度条目。
- 影响版本排期或执行合同时，同步对应 plan／长期 TODO／相关版本 memory；单纯归档不改实验合同。历史对话与提案不回写成新结论，用新文档说明取代关系。

## 对话索引

时间均为 HKT（UTC+8）。

| 日期 | 平台／任务 | 内容与范围 |
|---|---|---|
| 2026-09-05 03:19–08:27 | [Claude Code 原 Main 会话](conversations/20260905_claude_novelty_route.md) | Owner 三条想法、参考 Astra 的补充、Claude 最终裁定；同段 pull/v27 上下文保留。分支副本不重复收录 |
| 2026-09-05 03:28–03:49 | [Codex / Astra：执行 base_v26-8 训练评估流程](conversations/20260905_codex_astra_novelty_route.md) | 独立比较请求、调查进展与最终建议；对应 `-Astra` 产出 |
| 2026-09-10 | [Codex：检查 v28 意图](conversations/20260910_codex_novelty_status_and_provenance.md) | v28 意图、novelty 当前进展与历史讨论定位；截至讨论区整理开始之前 |

## 文档索引

| 文档 | 性质／状态 |
|---|---|
| [Astra 独立路线建议](documents/a2_piper_novelty_route_20260905-Astra.md) | 2026-09-05 历史提案；从 v27 目录迁入，正文保留；其中 v28 方法实验排期已被后续决定取代 |
| [Claude 路线裁定](documents/20260905_claude_novelty_decision_excerpt.md) | 2026-09-05 最终回答中 novelty 部分的原文摘录 |
| [当前路线与证据状态](documents/20260910_novelty_status.md) | 2026-09-10 基于已有记录的状态整理；不构成新的实验授权 |

## 跨阶段依据（原位维护）

- [长期 TODO：R 节路线裁定及 D 节队列](../a2_piper_longterm_TODO.md)、[Astra 独立长期 TODO](../a2_piper_longterm_TODO-Astra.md)。R 节保留历史排期，读取时同时看 2026-09-09 修订。
- [v27 执行计划](../v27/a2_piper_base_v27_plan_20260905.md)、[Astra 独立计划](../v27/a2_piper_base_v27_plan_20260905-Astra.md)。
- [恢复 pilot endpoint](../v27/a2_piper_base_v27_wave_b_r_step1500_readout_20260907.md)、[shadow estimator 结果](../v27/a2_piper_base_v27_shadow_estimator_readout_20260907.md)。
- [v28 计划](../v28/a2_piper_base_v28_plan_20260909.md)、[待办登记 X-02／X-05](../v28/a2_piper_base_v28_deferred_register.md)、[Teacher 包络与 Student 光学分阶段讨论](../v28/v28_progress_for_planner_20260910.md)。

本次归档只整理文档与 memory；未重判实验、恢复训练或修改 Teacher/G7 binding。
