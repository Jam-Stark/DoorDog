# Novelty 讨论区

创建：2026-09-10 HKT。维护者：与 Owner 讨论 novelty 的 AI session；由 Owner 决定方向与实验授权。

本目录集中保存选题讨论、独立判断、方法提案和证据索引。先读 [novelty memory](../../memory/a2-piper/novelty-research/description.md) 和 [当前状态](documents/20260910_novelty_status.md)，再按问题读取原对话。历史提案不覆盖当前 source、实验结果或 Owner 后续决定。

2026-09-21，Owner要求对N02 v1.0进行严格独立Pro审核，重点核对是否过早采用完整分层架构、控制时域/物理可执行性、技能充分性、冻结历史、后果用途及多项变更归因。[完整六项concern](conversations/20260921_codex_n02_independent_review_request.md)与[审核交付入口](../v29/pro_handoff/20260921_n02_independent_audit/README.md)已保存。两项Owner目标不等于已接受离散模式或selector；Pro可推翻当前技术路线、比较连续原LSTM最小路径。当前v1.0是待审议候选，交付状态以receipt为准；本轮不启动实施/训练。

2026-09-21 20:12 HKT，已按[Owner四问及GPU4授权](conversations/20260921_codex_n02_finalize_request.md)将 [v29 N02 plan](../v29/a2_piper_v29_n02_plan.md)定稿为v1.0 FINAL。B08公共补丁已核对并纳入底座；单一条件LSTM执行器在外部均衡mode指令下学习，临时skill奖励不进入selector；离散selector按统一物理r_task与完整实际时长回报学习，后果头仅作输入。先学会c并冻结，再无头selector、条件性的factual采集/预测/接入；c更新必须另采新版本后果，不能重命名旧标签。GPU4已授权，未申请额外设备，本轮未实施/运行。下方v0.1/B08 OPEN内容是较早时点历史。

2026-09-21 12:57 HKT，Owner已接受N02首段三候选与身体通过合同，当前入口为 [v29 N02 plan v0.1](../v29/a2_piper_v29_n02_plan.md)。首个后续实施包限定P0：统一通过/清离语义、三候选真实12D动作路径及可见功能片段；其后分层推进原LSTM、条件性后果读出和Student独立执行。两项决定不再待确认，时窗/数值参数仍按实际功能收敛。计划已纳入已归档C002的0/64自然完成与B08 OPEN约束；本轮未实施或运行，原训练与等待未接管。

2026-09-20 17:02 HKT，N02 独立 planner 已交付[持续调节的最小设计](documents/20260920_n02_minimal_continuous_adaptation_design.md)，待 Owner 裁定。分支 `codex/v29-n02` / worktree `/home/baoquanc/workspace/DoorDog-A2_Piper_v29_n02` 基于完整 C002+B05。推荐先做已握柄 push 后段 hold/有限推进/release＋身体路径，固定执行者和版本 c 的反馈续接，再判断冻结 LSTM 特征的小头是否有额外价值；Stage5/完成按身体通过与全身清离一起设计。倾斜搜索与释放后重抓建议随后增量，D023 仍归 N02；无实现或效果证明。

此前 N02 [Pro 回包及本地更正](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pro_reviews/v29/20260920_162527__N02_online_adaptation/README.md)、[研究结论](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/novelty/documents/20260920_n02_pro_review_and_next_step.md)，以及尚未实施的 [N01 最小设计](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/novelty/documents/20260920_n01_minimal_recovery_transfer_design.md)继续引用主工作目录原件。本分支没有复制附件、接管既有训练/等待或新建预算。

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
| 2026-09-21 | [Codex：N02独立审核与六项concern](conversations/20260921_codex_n02_independent_review_request.md) | Owner要求Pro独立判断能否work、是否过度架构化/偏离原novelty，附baseline与真实证据 |
| 2026-09-21 | [Codex：N02定稿四问与GPU4授权](conversations/20260921_codex_n02_finalize_request.md) | B08同步记录、共享条件执行器、统一回报selector、固定c与标签版本；GPU4已授权 |
| 2026-09-21 | [Codex：N02 Owner两项裁定](conversations/20260921_codex_n02_owner_decisions.md) | 首段已握柄push三候选与Stage5/完成合同已接受，要求据此制定plan |
| 2026-09-20 | [Codex：N02 planner 请求摘录](conversations/20260920_codex_n02_planner_request.md) | 研究/文档授权、行为目标、两个控制合同与资源边界；公开交付摘要单列 |
| 2026-09-05 03:19–08:27 | [Claude Code 原 Main 会话](conversations/20260905_claude_novelty_route.md) | Owner 三条想法、参考 Astra 的补充、Claude 最终裁定；同段 pull/v27 上下文保留。分支副本不重复收录 |
| 2026-09-05 03:28–03:49 | [Codex / Astra：执行 base_v26-8 训练评估流程](conversations/20260905_codex_astra_novelty_route.md) | 独立比较请求、调查进展与最终建议；对应 `-Astra` 产出 |
| 2026-09-17 | [Codex：v28提前收尾摘录](conversations/20260917_codex_v28_closure_excerpt.md) | Owner停止训练、复用render与后续优先级的有界摘录 |
| 2026-09-14 | [Codex：v28 closure回收摘录](conversations/20260914_codex_v28_closure_excerpt.md) | Owner授权和公开回收结论的有界摘录；不是完整会话 |
| 2026-09-10 | [Codex：检查 v28 意图](conversations/20260910_codex_novelty_status_and_provenance.md) | v28 意图、novelty 当前进展与历史讨论定位；截至讨论区整理开始之前 |

## 文档索引

| 文档 | 性质／状态 |
|---|---|
| [N02 v1.0独立Pro审核交付](../v29/pro_handoff/20260921_n02_independent_audit/README.md) | 当前审阅阶段；Owner concern原文、baseline背景与资料地图，发布/上传以receipt为准 |
| [v29 N02 plan](../v29/a2_piper_v29_n02_plan.md) | v1.0 FINAL；N02-D001/D002已接受、GPU4已授权；B08已同步，条件执行器/统一物理回报selector/固定c后果已定稿；N02方法尚未实施/运行 |
| [N02：持握、推进与释放通行的最小设计](documents/20260920_n02_minimal_continuous_adaptation_design.md) | 研究依据；首段范围与通过合同已接受，其余技术细节仍为提案；当前计划见上行 |
| [Astra 独立路线建议](documents/a2_piper_novelty_route_20260905-Astra.md) | 2026-09-05 历史提案；从 v27 目录迁入，正文保留；其中 v28 方法实验排期已被后续决定取代 |
| [Claude 路线裁定](documents/20260905_claude_novelty_decision_excerpt.md) | 2026-09-05 最终回答中 novelty 部分的原文摘录 |
| [v28最终closure N01/N02增量复核](documents/20260917_v28_closure_N01_N02.md) | 2026-09-17；设计继续/实验延期，Owner更急切后续范围优先 |
| [v28 G1停止点N01/N02复核](documents/20260914_v28_g1_closure_N01_N02.md) | 2026-09-14；两项继续有界立项设计、实验DEFER；方法收益未建立 |
| [当前路线与证据状态](documents/20260910_novelty_status.md) | 2026-09-10 基于已有记录的状态整理；不构成新的实验授权 |

## 跨阶段依据（原位维护）

- [长期 TODO：R 节路线裁定及 D 节队列](../a2_piper_longterm_TODO.md)、[Astra 独立长期 TODO](../a2_piper_longterm_TODO-Astra.md)。R 节保留历史排期，读取时同时看 2026-09-09 修订。
- [v27 执行计划](../v27/a2_piper_base_v27_plan_20260905.md)、[Astra 独立计划](../v27/a2_piper_base_v27_plan_20260905-Astra.md)。
- [恢复 pilot endpoint](../v27/a2_piper_base_v27_wave_b_r_step1500_readout_20260907.md)、[shadow estimator 结果](../v27/a2_piper_base_v27_shadow_estimator_readout_20260907.md)。
- [v28 计划](../v28/a2_piper_base_v28_plan_20260909.md)、[待办登记 X-02／X-05](../v28/a2_piper_base_v28_deferred_register.md)、[Teacher 包络与 Student 光学分阶段讨论](../v28/v28_progress_for_planner_20260910.md)。

本次归档只整理文档与 memory；未重判实验、恢复训练或修改 Teacher/G7 binding。
