---
name: codex-agent-system-architecture
status: v1_5_0_static_pass_runtime_not_run
scope: 当前sim2sim工作区的AI workflow
last_updated: 2026-09-23 14:11 HKT
---

## v1.5.0 当前同步状态

workflow v1.5.0 已同步：默认/default 为 GPT-6 Sol/medium，子任务并发 5，Main context/compact 516000/464400、total；Main model/effort 由 App 选择。共 12 个角色，唯一 Astra/medium deep_researcher。

本分支静态预检 STATIC_PASS，4 个 worktree hooks 已同步注册；新 hook 信任与实际拦截、effective config、双 Main 通信、模型切换及工具回收均未运行验收。旧证据不自动升级为 v1.5.0 runtime PASS；旧长任务脚本/收据与研究内容保持原样。

来源与备份：`.ai/WORKFLOW_SYNC.md`。以下历史配置/结论仅为旧版本记录，当前配置以本节和实际 source 为准。

## 先前版本记录


Owner批准将A2_Piper已接受的workflow1.4.0同步到本分支。当前采用FAST/STANDARD/HIGH_RISK与按需委托；无默认合同、freeze、review队列或角色探针。十一角色使用当前standalone schema；Main不设model/effort，context/compact保留516000/464400。

项目事实、科研memory、artifact配置和产品代码保持原样。同步路径与证据见`.ai/WORKFLOW_SYNC.md`；历史DONE记录不构成当前执行授权。
