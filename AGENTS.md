# DoorDog AI entrypoint

System、developer、Owner/user 指令优先。本文件只负责路由与不可违反的项目边界，不要求每次任务全量读取所有 workflow 文档。

## 1. 最小读取集

处理非平凡任务时先读：

1. `.ai/ROLE.md`：稳定的 coding behavior 与中文表达规范；
2. `.ai/PROJECT.md`：DoorDog/A2_Piper 的项目事实、受保护路径和证据边界；
3. `.ai/WORKFLOW.md`：FAST / STANDARD / HIGH_RISK 路由及按需控制设施。

随后只读取与当前 runtime 对应的 adapter：

- Codex：`.codex/AGENTS.md`，需要委托或 P2P 时再读 `.codex/TEAM.md`；
- OpenCode/OMO：`.omo/AGENTS.md`；
- standalone Claude Code：`CLAUDE.md`，固定 single-agent。

## 2. 条件读取表

| 触发条件 | 再读取 | 启用内容 |
|---|---|---|
| 多 writer、排他资源、跨 session 协调、正式 review/QA | `.ai/TEAM_STATE.md` | ledger、必要合同、lease、freeze、verdict |
| 产生 durable memory candidate 或 memory 分类需要重构 | `.ai/MEMORY_GOVERNANCE.md` | create/move/split/merge/supersede/retire |
| 运行预计超过 30 分钟或需要断线连续性 | `.ai/LONG_RUNNING_TASKS.md` | tmux、run receipt、pending event |
| RL、IsaacLab、仿真、benchmark、causal claim、实机 | `.ai/SCIENTIFIC_ENGINEERING.md` | claim-matched scientific evidence |
| Owner 选择跨阶段多 planner | `.ai/STAGE_DECISION.md` | local/cloud planner synthesis |
| Owner 要求阶段交付，或当前 stage 明确声明 artifact handoff | `.ai/ARTIFACT_HANDOFF.md` | allowlist bundle 与 Pro_Space 上传 |
| 历史决策、已知失败或当前 TODO 与任务相关 | `MEMORY.md` 及最小路由 | durable project truth |

没有触发条件时，不为“流程完整”打开对应设施。

## 3. Mandatory delegation gate

Main 必须自动选择 FAST、STANDARD 或 HIGH_RISK。FAST 由 Main 直接完成；每个非 FAST 任务在进入深度工作前，必须检查：

1. 是否有两个或以上可独立推进的 read-heavy / research lane；
2. specialist 是否拥有与 Main 显著不同且必要的上下文；
3. 独立 review / QA 是否能显著降低风险；
4. 并行执行是否能显著缩短时间或避免 noisy exploration 污染 Main context。

任一条件成立且 runtime 允许 sub-agent 时，Main 必须立即 spawn 最少且有用的 1–3 个 focused agent，不等待 Owner 说“team”，也不先自行完成原本应委托的工作。HIGH_RISK 的 destructive、external、hardware 或昂贵副作用仍需先获得 Owner 授权，但安全的只读 scout、planner、source verification 或 reviewer lane 可按同一 gate 启动。

非 FAST 任务只有在没有独立价值、任务紧耦合且 Main 直接完成成本更低，或更高层/runtime 限制禁止 sub-agent 时，才可保持 single-agent；此时在 task plan 中记录简短的 `NO_DELEGATION_REASON`。scope 扩张或出现新 lane 时重新检查本 gate。

## 4. 授权与控制面

- answer / inspect / diagnose / review / research / plan 默认只读；
- build / fix / refactor / update 授权执行准确的本地改动与相匹配的非破坏性验证；
- destructive operation、外部写入、材料性 scope 扩张、未授权昂贵长跑和硬件动作必须由 Owner 明确批准；
- Main `/root` 是唯一控制面，拥有 scope、acceptance、WRITE_SET、排他资源、Git、外部写入和最终整合权；
- 子 agent 可通过 P2P 直接交换技术事实、复现和有限请求，但不得改变权限。

## 5. DoorDog 不可违反的边界

- 先 trace 实际执行的 source/config/dependency path，再实现最小端到端版本；
- memory 是路由和历史，不得覆盖当前 source、resolved config 和 runtime 事实；
- invalid state、unsupported API、shape/type/device mismatch 和缺失 checkpoint 必须 fail fast；
- 不用 fallback、broad catch、silent downgrade、默认假数据或无依据 clipping 掩盖问题；
- 一个路径或排他资源同一时间只有一个 writer/owner；
- IsaacLab API 变更先核对本机 `/home/baoquanc/workspace/IsaacLab` 与当前官方文档；
- static、runtime、experiment、hardware 证据严格分级；
- 只有 Main 能 stage、commit、push、merge；任何 Git commit 都需要当前任务中的明确授权，默认不 push；
- FAST 和普通 STANDARD 任务不创建 ledger、freeze、memory curator 或 artifact bundle，除非出现对应触发条件。

结束时只报告实际相关内容：changed paths、证据等级、未运行事项、仍活跃的 writer/排他资源，以及是否真实产生 durable memory candidate 或 stage artifact handoff。
