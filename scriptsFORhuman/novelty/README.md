# Novelty 讨论区

创建：2026-09-10 HKT。维护者：与 Owner 讨论 novelty 的 AI session；由 Owner 决定方向与实验授权。

本目录集中保存选题讨论、独立判断、方法提案和证据索引。先读 [novelty memory](../../memory/a2-piper/novelty-research/description.md) 和 [当前状态](documents/20260910_novelty_status.md)，再按问题读取原对话。历史提案不覆盖当前 source、实验结果或 Owner 后续决定。

2026-09-22 11:08 HKT：[共同baseline8000最终结果](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_C002_resume8000_final_readout_20260922.md)已验收关闭，本seed自然64双侧全部完成；此前左右归因文档已加最终时点更新，未启动动态side/PPO/bank改动。

2026-09-21补充：[跨push/pull/B05/v28的左右归因](documents/20260921_cross_branch_bilateral_attribution.md)完成既有trace与milestone离线分析。新增定位C002@6000 RIGHT周期性开爪使K5持续失败；pull双侧均过前段但goal仍0，v28弱侧后期可追上也可因不同机制退步。未改变训练或启用新方法。

2026-09-21补充：[v29左右动态分配初判](documents/20260921_v29_bilateral_curriculum_initial_judgment.md)已完成。领先方向反转不能归因纯随机；B LEFT已有大量Stage3练习，优先区分物理失败类型，再讨论按side×stage的课程分配。保存本次既有日志100-batch读数，未修改训练或实施机制。

2026-09-20当前N02进展：[Pro回包已完整归档并完成一次定向核对](../pro_reviews/v29/20260920_162527__N02_online_adaptation/README.md)。推荐先判断有效交互与动作后果，再决定网络；[简要解释](../pro_reviews/v29/20260920_162527__N02_online_adaptation/OWNER_BRIEF.md)及[研究结论、模型更正和待定选择](documents/20260920_n02_pro_review_and_next_step.md)已保存。Pro有CPU模型执行记录，本机未复跑；压柄夹持敏感性156行遗漏更紧单指法向约束，须按本地更正阅读。候选后的续接控制、fully_clear与逐tick stage收入仍待设计；无N02实现、在线适应/Student或硬件效果证明。

2026-09-20当前N01进展：[planner最小设计已交付](documents/20260920_n01_minimal_recovery_transfer_design.md)，待Owner裁定。推荐正常释放前局部L0＋L1，Teacher/Student共享stage-blind接口、Teacher适应后提供同语义12D监督；先让Student全程实际执行，保留在线hidden与跨rollout事件结果，按需要再增加序列库/prefix。L2/L3、完整恢复图和Student RL不是已接受前置，D023仍有效。原[Pro回包与定向核对](../pro_reviews/v29/20260920_153418__N01_recovery_transfer/README.md)、[四问解释](../pro_reviews/v29/20260920_153418__N01_recovery_transfer/OWNER_ONE_PAGE.md)及[上一轮待定项](documents/20260920_n01_pro_review_and_next_step.md)保留。所有新设计仍为推荐，只有INSPECTED证据，无N01实现或效果证明。

最新方向（2026-09-17 21:13 HKT）：Owner 已将 N01/N02 纳入 v29，总体 GPU 与时机以[v29总体安排](../v29/a2_piper_base_v29_overall_arrangement.md)为准；待baseline落地后各自独立branch/worktree。当前先讨论baseline，方法证据限制未变。

2026-09-18补充：Owner确认B01有/无闭门器与门轴松紧，并询问是否应留给N02；本地建议先纳入baseline共同门域，N02随后研究同等观察/门域下的额外适应收益。当前Teacher有LSTM与质量/几何真值，不能等同部署Student感知。依据统一见[v29 baseline plan §3](../v29/a2_piper_base_v29_baseline_plan.md)，没有新方法实验。

2026-09-18补充（2026-09-18 20:38 HKT）：Owner将强回弹后“重新伸臂扶门”移到N02讨论，首版限定重抓把手；baseline回退奖励、暂不实施按需恢复设计。[原话](conversations/20260918_codex_rebound_n02_excerpt.md)与[候选/待讨论项](documents/20260918_n02_regrasp_rebound_discussion.md)已保存。无新N02实现或实验授权。

2026-09-20补充：Owner启动[N01 Pro预研](documents/20260920_n01_v29_c002_pro_research_brief.md)，要求完整C002保留B05、独立重思恢复图和“退回哪里”，并把恢复Teacher训练与Student能力传递分别设计/验证。历史novelty仅作参考；[原话](conversations/20260920_codex_n01_recovery_distillation_request.md)与[交付入口](../v29/pro_handoff/20260920_n01_recovery_transfer/README.md)已登记。当前仅研究交付，无N01方法实现或新实验。

2026-09-20补充：Owner同步启动[N02 Pro预研](documents/20260920_n02_v29_c002_pro_research_brief.md)，先明确能力缺口与估计/预测目标，再比较LSTM/辅助监督/历史编码与视觉；UniFP/SixthSense仅作借鉴。要求解释持续感知如何改变姿态、甩门/quiet握持及强回弹下控门，并从开始单独设计Student数据与记忆。[原话](conversations/20260920_codex_n02_online_adaptation_request.md)与[交付入口](../v29/pro_handoff/20260920_n02_online_adaptation/README.md)已登记。与N01同步研究，均无新方法实现/实验。Owner同轮追加Pro实际尝试A2＋PiPER动力学建模与roll/pitch方向出力计算，修订资料已加入原模型/限值/惯量输入及执行回传要求。

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
| 2026-09-21 | [Codex：LEFT/RIGHT动态课程研究](conversations/20260921_codex_bilateral_curriculum_request.md) | 当前两组训练左右优势、Stage3瓶颈与是否动态分配的Owner原话；仅研究授权 |
| 2026-09-20 | [Codex：N02 Pro回包解析请求](conversations/20260920_codex_n02_pro_return_request.md) | Owner要求归档/定向核对/建模执行证据检查及设计讨论；planner交接prompt仅在对话交付 |
| 2026-09-20 | [Codex：N01 planner最小设计请求](conversations/20260920_codex_n01_planner_request.md) | Owner研究/定向追踪/文档授权原文；四问、比较要求、D023与资源边界 |
| 2026-09-20 | [Codex：N01 Pro回包解析请求](conversations/20260920_codex_n01_pro_return_request.md) | Owner附件解析/定向核对/设计讨论范围；新planner交接prompt仅在对话交付 |
| 2026-09-20 | [Codex：N02在线适应预研请求](conversations/20260920_codex_n02_online_adaptation_request.md) | Owner六问、行为目标与指定论文参考边界 |
| 2026-09-20 | [Codex：N01恢复与蒸馏预研请求](conversations/20260920_codex_n01_recovery_distillation_request.md) | Owner五项原话，完整C002/B05与独立Pro方案范围 |
| 2026-09-18 | [Codex：回弹扶门转入N02摘录](conversations/20260918_codex_rebound_n02_excerpt.md) | Owner指定接触方式并将行为移至N02讨论，baseline回退另见D023 |
| 2026-09-18 | [Codex：B01与N02分工摘录](conversations/20260918_codex_b01_n02_excerpt.md) | Owner确认B01覆盖并提出学习能力疑问；公开回复与范围边界，无新方法效果结论 |
| 2026-09-17 | [Codex：v29方向摘录](conversations/20260917_codex_v29_direction_excerpt.md) | Owner将N01/N02纳入v29、baseline落地后各自独立branch/worktree的原话摘录 |
| 2026-09-17 20:20（导出） | [ChatGPT Pro：Owner 的 novelty 路线讨论](conversations/pro_20260917_202000.md) | Owner 提供的原始 Markdown 导出，讨论时间为 2026-09-06 至 09-16；涉及交互历史适应、恢复机制及 arm–base 联动等路线。原文完整保留；讨论中的指令与提议不作为当前执行授权 |
| 2026-09-05 03:19–08:27 | [Claude Code 原 Main 会话](conversations/20260905_claude_novelty_route.md) | Owner 三条想法、参考 Astra 的补充、Claude 最终裁定；同段 pull/v27 上下文保留。分支副本不重复收录 |
| 2026-09-05 03:28–03:49 | [Codex / Astra：执行 base_v26-8 训练评估流程](conversations/20260905_codex_astra_novelty_route.md) | 独立比较请求、调查进展与最终建议；对应 `-Astra` 产出 |
| 2026-09-17 | [Codex：v28提前收尾摘录](conversations/20260917_codex_v28_closure_excerpt.md) | Owner停止训练、复用render与后续优先级的有界摘录 |
| 2026-09-14 | [Codex：v28 closure回收摘录](conversations/20260914_codex_v28_closure_excerpt.md) | Owner授权和公开回收结论的有界摘录；不是完整会话 |
| 2026-09-10 | [Codex：检查 v28 意图](conversations/20260910_codex_novelty_status_and_provenance.md) | v28 意图、novelty 当前进展与历史讨论定位；截至讨论区整理开始之前 |

## 文档索引

| 文档 | 性质／状态 |
|---|---|
| [跨分支LEFT/RIGHT归因](documents/20260921_cross_branch_bilateral_attribution.md) | 既有逐步trace与v28固定协议对照；直接行为已定位，学习成因未隔离 |
| [v29左右动态分配初判](documents/20260921_v29_bilateral_curriculum_initial_judgment.md) | 当前日志/源码/一手研究支撑的建议；未实施、无效果结论 |
| [N02：Pro回包结论、模型更正与下一步](documents/20260920_n02_pro_review_and_next_step.md) | 完整C002＋B05；Pro CPU执行材料已检查、夹持界局部更正；设计继续，无本地复跑或在线效果证据 |
| [N01：局部恢复与Teacher→Student最小设计](documents/20260920_n01_minimal_recovery_transfer_design.md) | planner推荐，待Owner裁定；共享执行接口、L0/L1、时间奖励、Teacher课程、Student执行/记忆、分离比较及未来功能路径；无实施/实验 |
| [N01：Pro回包研究结论与最小下一步](documents/20260920_n01_pro_review_and_next_step.md) | 完整C002＋B05；原件归档、一次source/config/既存证据核对；设计继续，实施/实验未批准 |
| [N02：C002能力/目标/在线控制预研](documents/20260920_n02_v29_c002_pro_research_brief.md) | Owner研究请求，目标先于网络，Teacher/Student分开；尚无方法选型/实验 |
| [N01：C002恢复机制与Teacher→Student传递预研](documents/20260920_n01_v29_c002_pro_research_brief.md) | 2026-09-20 Owner研究请求；问题与资料包，不是方法已选或实验批准 |
| [N02：强回弹后重抓把手候选](documents/20260918_n02_regrasp_rebound_discussion.md) | 2026-09-18 Owner指定N02讨论；D022源码依据与未实施候选，不作为baseline前置 |
| [v29 baseline plan：B01/N02分工](../v29/a2_piper_base_v29_baseline_plan.md) | 2026-09-18跨阶段原位文档；共同环境域与方法收益分开，Teacher输入/source已核，训练效果未知 |
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
