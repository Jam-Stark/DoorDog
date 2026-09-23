# DONE

- 2026-09-12 17:58 HKT — 记录 v1.4.0 config/read、helper runtime 和 hooks/strict-config/transport 的实际边界；未用模型自述作为 effective config 证据。

- 2026-08-17 16:31 HKT - Migrated the project to current `[agents]` settings and standalone custom-agent schema; replacement config and eight role TOMLs parse. User confirms the current machine accepts Luna subagents, so Luna is used normally without a compatibility branch. Runtime spawning was not separately probed.
- 2026-07 - Earlier selector, role-metadata, sandbox, write-safety, and full-role-matrix experiments are historical and no longer an active workflow gate.

- 2026-09-12 18:02 HKT — Owner 授权删除全局 shell_environment_policy 下误放的 model/effort，严格 app-server 初始化成功；hooks 仍未列出。

- 2026-09-12 18:14 HKT — 完成三项宿主接入的定向诊断：定位hooks实际发现路径差异；一个explorer的telemetry证实Luna/high/Total但context与compact沿用Main预算；原生长等待按上层限制未运行。无效内联迁移撤回，验收仍BLOCKED，证据见HOST_VALIDATION.md。

- 2026-09-12 — 完成限定工作区的用户hooks接入，严格hooks/list列出4项；实际执行待信任。修复记录见.ai/WORKFLOW_FIXES.md。

- 2026-09-12 — 整合HOOKS_RETEST：四项hooks加载/信任及SessionStart触发PASS；sleep360与一次353.21秒empty write_stdin PASS。角色预算缺陷按Owner要求暂停，未部署补丁。
