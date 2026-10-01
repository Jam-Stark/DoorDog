<!-- managed-by: jam-coding-role; file: MODEL_ROUTING.md -->
# Model routing v1.5.0

Main 的 model / effort 由 App 选择；按 Owner 要求保留项目 Main 窗口 516000、compact 464400、scope=total。独立 planner Main 与 worker Main 分别算一个 team；Main 不占子 agent 名额。一个 team 通常只需要 0–2 个子 agent；并发上限 5 不是必须开满的目标。

| 子角色 | 模型 / effort | 边界 |
|---|---|---|
| memory_curator | GPT-6 Luna / medium | 机械整理 |
| default | GPT-6 Sol / medium | 默认有界任务 |
| explorer / context_researcher | GPT-6 Luna / high | 指定路径/问题的检索与有出处的事实摘要 |
| runtime_qa | GPT-6 Luna / high | 精确命令的执行、结果与错误归档；复杂失败因果交回 Main/Sol |
| scope_planner / worker | GPT-6 Sol / medium | 有界任务拆分、普通实现；scope_planner 子角色不是跨 session 的 planner Main |
| semantic_worker / code_reviewer | GPT-6 Sol / high | 语义密集实现、按具体 concern 触发的审阅 |
| isaaclab_worker / isaaclab_reviewer（DoorDog） | GPT-6 Sol / high | 保留现有 IsaacLab/source/tensor/manager/训练语义约束 |
| deep_researcher | GPT-6 Astra / **medium，唯一** | 最难的数学、动力学、复杂根因或科研机制判断；只读咨询，不做日常检索/重复审阅 |

## 必须执行的预算边界

整个 team 生命周期仅分配一个 Astra 子 agent 身份；需要继续咨询时复用它，不通过 close→新建轮流消费昂贵模型。关闭后可恢复同一身份；不可恢复时由 Owner 决定是否重建，不用 TTL 自动释放。若有确定证据证明 spawn 从未创建子 agent，可人工 reconcile 对应未绑定 reservation。

默认子 agent 必须是 Sol/medium；每次 spawn 必须选择已注册角色，显式 `fork_turns="none"`。禁止传 model、effort、reasoning_effort、model_reasoning_effort 覆盖。禁止 fork_context、完整 Main 历史继承、子 agent 再建子 team。自定义角色必须先审计，不以 unknown/default 悄悄回退 Astra。

Astra medium 不得升级 high/xhigh/max。Sol/Luna 默认上限 high；Sol max 仅是另外获准的离线比较候选，不进入 v1.5.0 自动路由。普通任务不用“先低端试错再层层升级”的固定链；按实际语义复杂度直接派合适的有界角色。

首次委托前，从宿主取得实际 Main session_id，按当前 Owner 工作单登记稳定 team_id：

```bash
python3 .ai/scripts/workflow_state.py --root . team-init --session ACTUAL_MAIN_SESSION_ID --team OWNER_TASK_TEAM_ID
python3 .ai/scripts/codex_preflight.py --root .
```

Astra 配额由 PreToolUse 在 SQLite 事务中先预留，PostToolUse 再绑定实际 child ID。结果未知保留占用；compact/重启不清空；同一 Git common-dir 的 worktree 共享同机状态。不要把 SQLite 放在跨机器 NFS，也不要复制状态数据库来实现远程通信。

本地验收须证明所有 spawn/resume 路径，包括工具命名空间与 Code Mode 的相关调用，都经过守卫。无法证明时禁用未覆盖的委托路径；Main 单独工作，不能宣称昂贵模型配额已经在实际宿主生效。角色配置、hooks、源码检查不是计费系统硬限额，也不是对可改配置的恶意代码的安全隔离。

## 有界上下文

Luna 子角色 65,536 / 49,152；Sol/Astra 196,608 / 163,840（窗口 / compact 阈值）。这是本工作流的保守预算，不是模型最大能力或扣费硬上限。仍要新鲜短 brief、精确路径、必要证据片段；大日志放文件。Astra notes/history 与 Sol/Luna compact 的区别见 .ai/CONTEXT_POLICY.md。

保留单写入方、Main 整合/授权、昂贵实验与实机单独授权的既有规则。没有数学难题就不启动 Astra，没有审阅 concern 就不启动 reviewer。
