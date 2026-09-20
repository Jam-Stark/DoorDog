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
  - scriptsFORhuman/novelty/documents/20260910_novelty_status.md
  - scriptsFORhuman/novelty/documents/20260918_n02_regrasp_rebound_discussion.md
  - scriptsFORhuman/a2_piper_longterm_TODO.md
  - scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md
related_entries:
  - base-v27-bilateral-hardening
  - base-v28-camera-aware-rebaseline
---

# Novelty 讨论与路线

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
