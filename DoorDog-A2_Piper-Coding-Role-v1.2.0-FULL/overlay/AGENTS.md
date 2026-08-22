# DoorDog AI entrypoint

System、developer、Owner/user 指令优先。处理本仓库任务时按下列顺序读取：

1. `.ai/ROLE.md`：通用 coding behavior 与中文表达规范；
2. `.ai/PROJECT.md`：DoorDog/A2_Piper 真实项目事实与边界；
3. `.ai/WORKFLOW.md`：Direct / Focused / Coordinated 工作方式；
4. `.ai/RUNTIME_ADAPTERS.md`：Codex、OpenCode/OMO、standalone Claude 的官方范式；
5. `.ai/TEAM_STATE.md`：Codex P2P、task contract、lease、freeze、verdict；
6. `.ai/MEMORY_GOVERNANCE.md`：主动创建、拆分、迁移、替代和退役 memory；
7. `.ai/LONG_RUNNING_TASKS.md`：tmux、run receipt、pending event；
8. `.ai/SCIENTIFIC_ENGINEERING.md`：RL/IsaacLab/仿真/实机证据；
9. `.ai/STAGE_DECISION.md`：Owner 启用跨阶段多 planner 时读取；
10. `.ai/ARTIFACT_HANDOFF.md`：阶段产出打包或云端交接时读取；
11. `MEMORY.md` 及其路由：需要历史决策、失败模式或运行证据时读取。

`.codex/*`、`.omo/*`、`opencode.json`、`CLAUDE.md` 是 runtime adapter，不得重新定义或削弱 `.ai/*`。

## 授权与控制面

- answer / inspect / diagnose / review / research / plan 默认只读；
- build / fix / refactor / update 授权执行准确的本地改动和相匹配的非破坏性验证；
- destructive operation、外部写入、材料性 scope 扩张、未授权昂贵长跑和硬件动作必须由 Owner 明确批准；
- Main `/root` 是唯一控制面，拥有 scope、acceptance、candidate revision、WRITE_SET、GPU/resource lease、Git、外部写入和最终整合权；
- 子 agent 可直接交换技术事实和有限请求，但不得借 P2P 改变权限。

## DoorDog 不可违反的边界

- 开工前读取最小相关 file-based memory，再以当前 source/config/runtime 为实现权威；
- 先 trace 真实执行路径，再实现最小端到端版本；
- invalid state、unsupported API、shape/type/device mismatch 和缺失 checkpoint 必须 fail fast；
- 不用 fallback、broad catch、silent downgrade、默认假数据或无依据 clipping 掩盖问题；
- 一个路径或排他资源同一时间只有一个 writer/owner；
- IsaacLab API 变更先核对本机 `/home/baoquanc/workspace/IsaacLab` 与当前官方文档；
- static、runtime、experiment、hardware 证据严格分级；
- 只有 Main 能 stage、commit、push、merge；默认不 push；
- standalone Claude Code 固定 single-agent；OMO 与 Codex 各自保留自己的官方协作范式。

结束前报告实际 changed paths、证据等级、未运行事项、仍活跃的 writer/resource，以及是否产生 durable memory candidate 或 stage artifact handoff。
