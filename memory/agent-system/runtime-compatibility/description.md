---
name: codex-agent-runtime-compatibility
status: v1_5_0_static_pass_runtime_not_run
scope: 当前sim2sim工作区的Codex配置与已知宿主边界
last_updated: 2026-09-23 14:11 HKT
---

## v1.5.0 当前同步状态

workflow v1.5.0 已同步：默认/default 为 GPT-6 Sol/medium，子任务并发 5，Main context/compact 516000/464400、total；Main model/effort 由 App 选择。共 12 个角色，唯一 Astra/medium deep_researcher。

本分支静态预检 STATIC_PASS，4 个 worktree hooks 已同步注册；新 hook 信任与实际拦截、effective config、双 Main 通信、模型切换及工具回收均未运行验收。旧证据不自动升级为 v1.5.0 runtime PASS；旧长任务脚本/收据与研究内容保持原样。

来源与备份：`.ai/WORKFLOW_SYNC.md`。以下历史配置/结论仅为旧版本记录，当前配置以本节和实际 source 为准。

## 先前版本记录


十一角色与config预检STATIC_PASS。四项hooks通过用户级来源注册，命令限定本工作区；新增定义须经Codex正常信任流程，主线的信任不自动代表此处已信任。

主线同机已验证四项hooks加载/信任、SessionStart触发及单次empty write_stdin353.21秒。这是共享宿主证据，不是本分支独立的事件/训练证明。
已知0.153.0角色context/compact沿用Main，Owner已暂停修复；全局错误shell_environment_policy模型字段已经删除。24h等待与idle wake未验证。
当前接入证据见`.ai/WORKFLOW_SYNC.md`；通用修复历史见`.ai/WORKFLOW_FIXES.md`。
