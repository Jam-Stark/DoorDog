---
name: codex-agent-runtime-compatibility
scope: project config parsing, current standalone-agent schema, and concrete runtime model compatibility
status: v1_4_0_integrated_known_child_budget_defect_paused
last_updated: 2026-09-12 18:14 HKT
evidence_level: CONFIG_RUNTIME_PASS; CHILD_BUDGET_RUNTIME_MISMATCH; HOOK_EXECUTION_BLOCKED; LONG_WAIT_NOT_RUN
owned_paths:
  - .codex/config.toml
  - .codex/agents/
  - memory/agent-system/runtime-compatibility/
---

## Purpose

Track current project configuration facts and real runtime incompatibilities only. Do not create periodic model/role/sandbox probes.

## 当前验收（2026-09-12 最新证据）

- v1.4.0替换与hooks本机注册完成；四项加载/信任PASS，真实SessionStart execve触发PASS。其他事件未逐项runtime验收，hook独立完成退出状态UNVERIFIED；不重测已通过部分。
- 当前测试任务原生sleep360 exit0、无输出；仅一次empty write_stdin实际353.210386087秒，无300秒截断或二次轮询。此前把schema默认范围视为硬上限的结论已被推翻。24h等待、Desktop热加载、idle wake未验证。
- 角色model/effort/Total生效，但context/compact沿用Main，宿主typed role overrides缺少对应字段。Owner已暂停该缺陷修复，未编译部署补丁。
- 原始证据：`.ai/runtime/workflow-v140/HOOKS_RETEST.md`；当前汇总：`.ai/WORKFLOW_FIXES.md`。下列原验证过程中的未信任、NOT_RUN与BLOCKED描述为历史，以上述状态为准。

## Current facts

- v1.4.0 共十一角色：Astra low default/scope_planner；Astra medium code/IsaacLab reviewer 与 isaaclab_worker；Astra high deep_researcher；Terra high worker、medium runtime_qa；Luna high context_researcher/explorer、medium memory_curator。
- Astra 子角色预算 262144/229376，Terra/Luna 196608/163840，compact scope 均为 total；这些是配置意图；本轮 explorer 实际未采用角色 context/compact，详见下述宿主证据。
- `codex-cli 0.153.0` 的新 app-server `config/read` 实际返回 Main 516000/464400、total、background_terminal_max_timeout=86400000、default Astra/low、并发五子任务。
- 2026-09-12 Owner 授权后删除全局 `[shell_environment_policy]` 下误放的 `model` 和 `model_reasoning_effort`；`codex app-server --strict-config` initialize 成功，原 schema 阻断已解除。随后 hooks/list 仍为空，stderr 提示 Linux bubblewrap 无法创建 user namespace；不能据此认定 hook 未加载的唯一原因。
- 2026-09-12 修复前宿主接入验证：独立 app-server 与 CLI `/hooks` 均列出0项。系统调用 trace 证明配置读取当前 worktree，但 JSON hooks 查找主仓库 `GR00T-VisualSim2Real/.codex/hooks.json`，没有读取本 worktree hooks.json；内联到 worktree config 的尝试也被忽略，已撤回。该次验证 BLOCKED 在加载阶段，后续用户级注册已解除加载阻断（见下文）；hook trust 与实际生命周期执行仍 UNVERIFIED；不能归因于 bubblewrap，也不能声称只需用户信任即可解决。未改写信任。
- 一个实际只读 explorer（`fork_turns="none"`，子任务 `01a09514-42b0-7a60-95bd-501adfe07d10`）已完成。宿主 telemetry 证明 Luna/high 与 Total scope 生效，但有效 context=490200、compact=464400，与角色196608/163840不符。490200恰为Main516000的95%；原始 resolved context 字段仍UNVERIFIED。预算验收BLOCKED，不能以角色TOML或子任务自述宣称生效。
- 当前新任务 `write_stdin` schema 仍声明 empty poll 最多300000ms，上层另要求避免超过60秒阻塞等待；按Owner条件未启动sleep360。独立app-server解析86400000不证明活动Desktop transport支持24h。进程完成/提前返回/实际transport截断均NOT_RUN，idle wake未实现。
- 本轮精确证据与后续操作：`.ai/runtime/workflow-v140/HOST_VALIDATION.md`；`hook-loading-paths.log`、`child-budget-telemetry.json`、`native-wait-evidence.json`。该历史验证曾撤回无效inline改动；后续已新增用户级注册适配，详见下文。
- 包内 32 项 helper 测试通过；哈希移除后 21 项受影响的 memory/runner 检查全部通过；named tmux 短任务在声明 10h ETA 下提前正常完成。证据在 `.ai/runtime/workflow-v140/`。
- 历史 Luna 用户确认仍有效；此次配置读取及 helper 验证不构成模型质量、计费阈值或权限隔离证明。

## Runtime policy

- Use Luna normally in real work. Do not run a special smoke or metadata matrix merely to reconfirm it.
- If a future real invocation fails, record the exact build and concrete error once, report it, and decide a targeted change. Do not silently substitute another model.
- Static parse does not prove simulation, runtime smoke, or training behavior; those remain `NOT_RUN` until they occur as part of real work.

## TODO summary

- 唯一已知未修复功能缺陷：named-role context/compact应用不符，按Owner要求暂停，后续workflow迭代或宿主更新再处理。
- 24h/idle wake没有验收声明，不安排周期性验证。

## DONE summary

- 2026-08-17 16:31 HKT - Migrated to current `[agents]` and standalone custom-agent schema, raised generic Terra and Luna code/runtime roles to high, recorded user-confirmed Luna availability, and parsed the replacement configuration. Runtime spawning was not separately probed.

## Hooks 接入修复（更新）

此前加载BLOCKED已由本机适配解除：`.ai/scripts/install_codex_hooks.py`将工作区限定的四个入口注册到用户hooks。严格hooks/list返回4项、untrusted、无错误；实际事件执行仍待用户信任。0.153.0源码说明linked-worktree有意取root checkout hooks并删除本地inline，不是格式问题。修复、已解决的全局模型字段问题与仍未解决的角色预算/等待限制统一见`.ai/WORKFLOW_FIXES.md`；原HOST_VALIDATION保留为修复前证据。
