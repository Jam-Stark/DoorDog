---
name: novelty-research
status: active
scope: novelty选题、跨版本路线裁定、讨论来源与文档维护
last_verified: 2026-09-20
evidence: INSPECTED — 原会话、人类可读导出、现有plan与实验readout
read_when:
  - 讨论或裁定novelty、恢复图、交互历史适应、coupling critic或Teacher shaping
  - 查找原始Owner想法、Claude与Codex独立判断
  - 产生相关对话、方案、文献比较或方法结论
source_of_truth:
  - scriptsFORhuman/novelty/README.md
  - scriptsFORhuman/novelty/conversations/
  - scriptsFORhuman/novelty/documents/20260920_n02_pro_review_and_next_step.md
  - scriptsFORhuman/novelty/documents/20260920_n01_minimal_recovery_transfer_design.md
  - scriptsFORhuman/novelty/documents/20260920_n01_pro_review_and_next_step.md
  - scriptsFORhuman/novelty/documents/20260910_novelty_status.md
  - scriptsFORhuman/novelty/documents/20260918_n02_regrasp_rebound_discussion.md
  - scriptsFORhuman/a2_piper_longterm_TODO.md
  - scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md
related_entries:
  - base-v27-bilateral-hardening
  - base-v28-camera-aware-rebaseline
---

# Novelty 讨论与路线

2026-09-22 11:08 HKT，[D077最终结果](../../../scriptsFORhuman/v29/a2_piper_base_v29_C002_resume8000_final_readout_20260922.md)将共同baseline的当前事实更新为：同配方6000/7000/8000自然goal0→31→64/64，8000左右各32/32且无staged load。本seed中的早期左右差距随续训追平，6000开爪周期/7000 Stage3诊断保留历史；它们不再是该8000人口的当前阻断。动态side课程、逐侧PPO和recovery bank均未作为本次干预，不能据此归因其必要/无效。单seed不证明稳定泛化或N01/N02方法收益；不自动更换Teacher绑定或启动新预算，GPU0本轮已关闭。

2026-09-21 20:04 HKT，共同baseline新增[D076自然证据](../../../.ai/runtime/v29_baseline_team/D076_C002_RESUME7000_NATURAL_MILESTONE.json)：同配方6000→7000后LEFT goal0→31/32，RIGHT越过Stage2由0→31/32（均止Stage3、仍无Stage4）。这支持训练进度可显著改变左右卡点；不证明更久必然追平或7000→8000持续改善。此前6000的开爪周期仍有效，但不能当作7000多数RIGHT的当前阶段。没有N01/N02方法或动态采样收益证据；原8000等待继续。

2026-09-21 17:13 HKT，[跨分支归因](../../../scriptsFORhuman/novelty/documents/20260921_cross_branch_bilateral_attribution.md)补足现有原始trace：C002@6000 RIGHT32自然例均在Stage2最长3–4步有效握持，3760次streak中断全部伴随开爪/双触消失，呈约4闭＋1开周期。pull同checkpoint双侧各64均到Stage4但goal0，K5相同且gripper PD/effort相同；v28部分seed后期goal双侧增长但非单调，且弱侧多为后段/超速失败。直接阻塞已定位，策略为何学成周期未隔离，B LEFT Stage3联合数据仍缺；不据此启用动态配额或逐侧PPO/恢复bank，原运行保持。

2026-09-21 15:06 HKT，Owner同意先拆弱侧Stage3失败；现有数据的缺口及bank/PPO解释已追加到[初判](../../../scriptsFORhuman/novelty/documents/20260921_v29_bilateral_curriculum_initial_judgment.md)。当前普通阶段bank仍启用，v27 recovery bank是握稳后失抓现场的额外再练机制；二者不能混同。全局advantage归一化是当前共享PPO路径，未观测逐侧advantage/梯度，不能由总reward或无逐侧权重直接归因。没有启用新机制或改现有训练。

2026-09-21 14:53 HKT，按Owner请求完成[v29左右动态分配初判](../../../scriptsFORhuman/novelty/documents/20260921_v29_bilateral_curriculum_initial_judgment.md)。现有单seed环境对照不能把领先反转归因随机；最新有界读数显示B LEFT约71%时间在Stage3而RIGHT已有含staged起点的goal记录，A自然RIGHT仍止Stage2。当前side固定各半、bank按env隔离；优先分清Stage3压柄/门轴运动/握持失败，再讨论side×stage课程，不直接按弱侧重分总env。仅INSPECTED与既有日志分析，机制未实施、原GPU合同/等待不变。

2026-09-21 14:36 HKT，共同baseline B08已按Owner要求修复并同步N01/N02/B05-ablation开发目录，见[唯一实施记录](../../../scriptsFORhuman/v29/a2_piper_v29_B08_implementation_20260921.md)。N01计划中的Stage0 arm覆盖删除已由公共实现承担，后续不要另加N01特例；仅限定CPU证明，不代表完整N01/N02方法已实现或有效。现有GPU0/GPU1仍是旧冻结输入。

2026-09-21，Owner在D072之后直接授权C002同配方6000→8000及7000/8000各64自然评估，见[主登记D074](../../../.ai/runtime/v29_baseline_team/D074_OWNER_AUTHORIZED_RESUME8000_REGISTRATION.json)。这只检验追加训练下的自然任务趋势，当前没有新结果，不能写成N01/N02方法进展；B08与原reward/action/assets保持，原6000结果继续作已观察基准。

2026-09-21，完整C002首轮结果已由D072验收：最终64自然首episode为0/64 goal，LEFT最高Stage2/4/5=2/27/3，RIGHT32例均Stage2，全部阶段超时。canonical证据在[baseline最终读回](../../../scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md)。N01/N02 planner应以此更新Teacher资格与后段数据人口判断；原Pro输入中的A3000仍是历史证据，不是最新C002结果。执行完成没有证明恢复/适应/Student收益，也不授权方法实验；B08继续由共同baseline待办跟踪。

2026-09-20 17:32 HKT，Owner将N01发现的Stage0 arm覆盖问题要求登记为共同baseline待办；当前路径已确认，canonical跟踪入口为[baseline TODO B08](../../../scriptsFORhuman/v29/a2_piper_base_v29_baseline_TODO.md)。修复仍OPEN，尚未实施；N01/N02接口设计需与共同baseline后续决定衔接，本条不等于Owner已采纳完整stage-blind方法方案。

2026-09-20 N02 Pro回包已从Owner附件完整保存（原ZIP＋46文件），完成一次source/config/既存runtime及CPU模型材料定向核对；[研究结论与待决项](../../../scriptsFORhuman/novelty/documents/20260920_n02_pro_review_and_next_step.md)、[完整原件和核对](../../../scriptsFORhuman/pro_reviews/v29/20260920_162527__N02_online_adaptation/README.md)为当前入口。Pro建议先补有效交互与动作条件进展/风险选择，沿用LSTM再判断辅助头；不预设质量/摩擦/wrench或网络瓶颈。Pro CPU记录有42姿态/26解/104方向与PD补算，支持姿态收益依方向、支撑和PD而变；Main仅INSPECTED，未本机复现。夹持模型漏用F|d·n|≤Nmax，156条press_down敏感性不能按90/36.4N当容量，更紧必要界45/18.2N仍属假设；arm/支撑/PD主表与水平情景不受影响，原件未改。下一步planner明确候选及续接控制c、assistance/fully_clear与逐tick stage收入、Teacher/Student输入/历史和分离比较。D023与N01未实施边界保持；无N02实现、在线/Student或硬件收益证明，无新GPU/预算。

2026-09-20 16:07 HKT，N01 planner完成[最小设计](../../../scriptsFORhuman/novelty/documents/20260920_n01_minimal_recovery_transfer_design.md)，待Owner裁定：正常释放前局部L0＋L1，Teacher两臂与Student共享stage-blind增量执行、Teacher适应后直接12D监督；先全Student在线采集、保留真实done的hidden语义及跨rollout事件结果，序列库/长展开/prefix按具体需要增加。L2/L3不是已证实前置，D023不变。本轮定向source补充：release latch表示达到释放资格，不等于实际松手；Stage1/2 creep按root相对实时G的位置计算，L1原地恢复也可能受影响；stage reward是逐tick收入，不能机械改成一次性奖金。设计含时间/奖励、课程/专家资格、分离比较与未来功能操作路径；只读接口子任务已完成。证据仅INSPECTED，无实现、测试、训练/评估、GPU操作、预算或Git提交；Teacher质量、相机输入、恢复收益与novelty仍未证明。

2026-09-20 N01 Pro回包已按Owner附件完整保存，并完成一次source/config/既存runtime定向核对；[结论与待定选择](../../../scriptsFORhuman/novelty/documents/20260920_n01_pro_review_and_next_step.md)、[原件和核对记录](../../../scriptsFORhuman/pro_reviews/v29/20260920_153418__N01_recovery_transfer/README.md)为当前入口。默认DAgger Teacher执行比例1.0成立；8 tick为数据窗口，Teacher/Student hidden按done reset，不是每8 tick失忆。Student81D中的actions为19D腿动作/累计arm target/gripper，另有6D delta；Stage0会按真值stage覆盖arm target，故Pro的stage-blind执行/有效标签是新的控制接口设计。全prefix重放、恢复目标/时间奖励分离和事件库均为提案，无方法实现或效果证明。优先正常释放前L0/L1的最小路径是Main建议，未成为Owner合同；Pro把释放后重抓纳入N01的建议待Owner采纳，D023当前边界不变。下一步为N01 planner收敛最小设计；原GPU任务与预算不变。

2026-09-20 Owner同步启动N02独立Pro预研：完整C002保留B05，先找具体能力缺口，再选估计/预测目标及其控制用途，之后才选网络。必须包含短/失败/无有效接触轨迹，v27 shadow只作旧证据；UniFP/SixthSense只用于分析可借鉴部分，不能预选fusion/flow-matching。Teacher与Student从输入/数据/监督/记忆起分别设计，并直接讨论近中性姿态/arm主导、有条件roll-pitch、controlled swing或quiet hold、强回弹下持续握持避免trunk碰撞目标。见[研究brief](../../../scriptsFORhuman/novelty/documents/20260920_n02_v29_c002_pro_research_brief.md)与[交付入口](../../../scriptsFORhuman/v29/pro_handoff/20260920_n02_online_adaptation/README.md)。Owner同轮追加Pro实际尝试A2＋PiPER动力学和roll/pitch方向出力建模，原URDF/惯量/config限值与计算要求一并交付；Main只提取输入，未计算力能力。方法尚未选定/实施，无新本地实验或预算；N01接口待共同裁定。

2026-09-20 Owner启动N01预研：以完整v29 C002（`v29-c002-baseline`）为主底座，先保留B05，打包给Pro独立重思恢复图、哪些失败需恢复及退回何处。既有novelty只是参考，不预定方法结论；恢复Teacher学习与Student获取能力必须分别设计，不能默认常规蒸馏自然继承。当前A2 DAgger默认Teacher执行比例1.0、无自动退火/跨batch数据聚合；Student81D＋RGB不含Teacher的stage/contact/门真值，这些source事实只是研究输入。见[研究brief](../../../scriptsFORhuman/novelty/documents/20260920_n01_v29_c002_pro_research_brief.md)和[交付入口](../../../scriptsFORhuman/v29/pro_handoff/20260920_n01_recovery_transfer/README.md)。尚无N01实现或新实验；原GPU0/GPU1训练合同不变。

2026-09-18 20:45 HKT，Owner/v29 D023：强回弹时重新伸臂扶门移入N02讨论，首版明确重抓把手；baseline精确恢复D021前三处原奖励，不等待按需辅助设计。[原话](../../../scriptsFORhuman/novelty/conversations/20260918_codex_rebound_n02_excerpt.md)与[既有候选/source依据](../../../scriptsFORhuman/novelty/documents/20260918_n02_regrasp_rebound_discussion.md)已保存。候选未实施，N02交互历史方向及baseline落地后独立分支时机不变，N01未取消；需要区分任务reward改动与方法增益，无新实验/预算或能力结论。

2026-09-18 15:08 HKT：Owner确认v29 B01有/无闭门器各半及门轴松紧，并问baseline学习能力/N02是否前置。本地source确认当前Teacher actor/critic为LSTM，含门角、交互反馈及质量真值，不含closer/friction真值；建议把门域纳入baseline，N02比较同等环境/观察下额外适应收益。建议不等于训练成功或方法有效。canonical设计见[v29 baseline plan §3](../../../scriptsFORhuman/v29/a2_piper_base_v29_baseline_plan.md)，[本轮摘录](../../../scriptsFORhuman/novelty/conversations/20260918_codex_b01_n02_excerpt.md)已归档；无N02实现/实验，旧shadow证据不变。

2026-09-17 21:13 HKT：Owner 明确将 N01/N02 纳入 v29 总体方向，分别计划 GPU2/GPU3；待 v29 baseline 落地后各自 checkout 独立 branch/worktree。当前先完成baseline六项讨论；具体方法设计/实验尚未执行，旧pilot与shadow证据限制未变。阶段安排以[v29总体安排](../../../scriptsFORhuman/v29/a2_piper_base_v29_overall_arrangement.md)为准，原话见[本次方向摘录](../../../scriptsFORhuman/novelty/conversations/20260917_codex_v29_direction_excerpt.md)。这取代此前“是否纳入v29尚未决定”的排期状态，不取代方法科学结论。

2026-09-17：v28恢复执行后的closure已完成N01/N02增量复核（D059/X05）。原三seedreach1/3，固定主备DEV均未双侧过门；两方法仍设计CONTINUE、实验DEFER，Owner更急切后续改动优先，未自动定义v29方法排期。[增量复核](../../../scriptsFORhuman/novelty/documents/20260917_v28_closure_N01_N02.md)。

2026-09-14：v28 G1停止点已按D045完成N01/N02回收；两项CONTINUE仅指有界立项设计，实验执行DEFER。N01先建立扰动/失抓有效暴露与完整endpoint，N02先明确可部署输入及含短集/失败集的可辨识门域。X05本次复核义务关闭，方法条目仍开放；无新实验或收益确认。[证据与下次动作](../../../scriptsFORhuman/novelty/documents/20260914_v28_g1_closure_N01_N02.md)。

2026-09-10 Owner建立并要求持续维护 [novelty讨论区](../../../scriptsFORhuman/novelty/README.md)。后续相关AI session须保存对话至`conversations/`、产出至`documents/`或按需新建主题目录，更新README索引，并同步本entry的description/TODO/DONE；跨阶段计划仍在原位维护。历史原话、提议、Owner决定和实验结论分别标明，不把归档变成新实验授权。

## 已核对的讨论来源

- Claude Code：`e09e9a1e-287d-44ec-8975-3e4afdc682c4`，原名Main，后为base_v26-7总结continuation的Branch标题；2026-09-05 03:19起提出三条想法，08:27给出裁定。`592fc504-dd4b-49f2-9996-843c39c4fc68`含同段分支记录，不重复归档。
- Codex：[执行 base_v26-8 训练评估流程](codex://threads/01a06769-5a89-7780-8705-c7035834dd29)，2026-09-05 03:28–03:49，Owner要求独立比较并使用`-Astra`后缀。
- 两份人类可读原文和2026-09-10回顾已存讨论区；每份注明来源与范围，不含内部推理、工具输出或系统指令。

## 当前可复用结论

近期方法切口为N-01恢复图＋失效边界采样；N-02交互历史状态估计为后续科学主线；N-06 coupling critic暂缓；N-07b Teacher shaping的配对蒸馏仍待研究。

v27恢复pilot为UNRESOLVED（R1缺endpoint、可用R2注入loss稀少）；shadow estimator只支持有限的模拟数据离线可辨识性，不代表actor在线适应。详细证据与数字从[状态文档](../../../scriptsFORhuman/novelty/documents/20260910_novelty_status.md)路由。

2026-09-09 v28 D-01已将N-01/N-02顺延v29；旧Astra/Claude文档的“v28方法实验”是历史排期。Teacher碰撞包络C_T与Student光学C_S分阶段冻结已由Owner于2026-09-11按D30批准，base单/双和真实光学/CAD仍在蒸馏前决定；不再标为PROPOSED。

2026-09-12 17:18 HKT（修改：-codex planner；依据：-owner，v28 D038）：v28 closure成功或失败均触发下一planner主动复核N01/N02。N01先决定是否重新立项pilot、重设计扰动/loss，取得新证据后再讨论多seed；N02复核可部署传感、可辨识性与适用门域（含v27未收敛门域），记录继续/延期/关闭，不把完美Teacher或最终相机无限前置。此处更新的是回收入口，未证明方法收益，也不授权新实验；当前跨阶段合同见[v28决策日志](../../../scriptsFORhuman/v28/a2_piper_base_v28_decision_log.md)。
