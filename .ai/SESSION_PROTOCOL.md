<!-- managed-by: jam-coding-role; file: SESSION_PROTOCOL.md -->
# Main-to-Main session protocol v1.5.0

## 1. 授权与身份先于通信

Owner 指定的 planner Main 和 worker Main 分别登记实际 session UUID、host_id、所属 app-server/宿主 endpoint、task_id、稳定 team_id，以及同一个 Owner 授权合同的完整文本 `authority_contract`（双方逐字一致；不生成摘要指纹）。合同说明 scope、资源、写入边界、可自主续行的阶段、验收责任、Owner-only STOP。不得用会话昵称碰运气，不借 peer 消息新增权限。子 agent 只向自己 Main 汇报，不直接指挥对方 team。

经 Owner 合同明确委托后，planner Main 负责阶段规划/验收，worker Main 负责已批准阶段内的实现/写入划分/整合。此 Main-to-Main 通道区别于子 agent 的技术 P2P；旧文档笼统的“P2P 只传事实”不应阻止合同范围内的 plan/验收决定。

本机通信在实际原生工具验证后启用；跨机器保持关闭。不要为了传一句话新启动一个 Codex app-server 或恢复同一会话到另一个进程。现有 App 所拥有线程须通过其正确、已认证的端点访问。

首次配对时核对现有 queue：用户/旧脚本可能已有消息。不能假设本工具的空账本等于原生队列为空。清楚旧 backlog 后才标记 queue_backlog_reviewed。没有验证可用的原生 queue list/cancel/replace 命令，不得编造这些命令。

## 2. 哪些消息值得发送

允许 PLAN_RELEASED、STOP_DECISION、STAGE_RESULT、CRITICAL_BLOCKER、MAJOR_PROGRESS。日常“已开始/还在跑/正在读文件”、逐工具结果、重复 ACK 不发。MAJOR_PROGRESS 必须解释实质变化，最短间隔 30 分钟；这不是“每 30 分钟发一次”的定时任务。普通行动项间隔至少 60 秒；首个独特的紧急阻断可绕过时间间隔，但仍遵守一个在途通知。

每条事件包含 event_key、task/stage、plan_revision、base_revision、短摘要、证据路径、需要的决策与已做的安全停顿。相同 event_key 内容不可变；重试幂等。只合并尚未发送、同 stage 的信息性 progress，独立决策不能被覆盖。

## 3. 传输选择

先读取目标真实状态。正在执行：向现有 turn 发 `turn/steer`，带当前 `expectedTurnId`。空闲：合同允许时向同一个 thread 发 `turn/start`。都不带 model/effort/cwd/权限覆盖。`turn/steer` 是 app-server JSON-RPC 方法，不是一个可凭空调用的 `codex turn/steer` CLI 子命令。

本包 `prepare-native` 只生成正确请求并占用在途名额；**它不会连接你的 App**。发起方 Main 使用本机已暴露并验证的 Codex 工具递交请求，再将真实回执记入账本。若本机工具有不同包装，按真实 schema 适配字段，不猜。这样由两个 Main 自行交接，Owner 不必复制粘贴消息。

只有明确“尚未投递”的失败（例如已验证的 turn 状态竞争错误）可重新读取一次目标状态、修正后重试；最多两次尝试。超时、连接中断、结果不可知记 unknown，**不得再 fallback queue**，以免重复执行。断线后先查实际线程/原调用回执，再人工 reconcile；不设置 TTL 自动重发。

原生通道确实不可用且同机 queue 已通过验证时才用：

```bash
codex queue --thread ACTUAL_TARGET_SESSION_UUID --message 'BOUNDED_EVENT_ENVELOPE'
```

上游源码已有 remote endpoint 参数接线，但本版不启用跨主机 queue，也不提供未经本机 help/schema 验证的 remote 命令。未来验证须包括 owning endpoint、认证、双向回执、同一 event 去重、断线恢复、证据文件两端可访问。不能靠共享/复制 Codex state.sqlite 或 rollout 文件实现。

## 4. 去重、背压与回执

本机每个发送方→接收方同时最多一个 dispatching / accepted / unknown 通知；后续事件只落 outbox，不继续塞原生队列。transport accepted 不是已经阅读，更不是业务处理完成。接收方在实际处理后本地 `resolve`，无需另发一个 ACK turn。回复决策时可在同一正常回复中记录已处理事件 ID。

紧急事件若遇到在途消息，不另排第二条通知：记录证据、在自身授权范围内安全暂停。需要 Owner 权限/危及硬件安全则直接升级 Owner，不让“省消息”妨碍安全。不要把尚未 dispatch 的 outbox 事件当成对方已收到；接收方完成当前事项时检查同一 pair 的剩余行动项，或发送方在下一真实业务机会发出。不启动新的 LLM 轮询器来推送 outbox。

如果一个 Main 当前完全空闲且没有任何调度器，本包的文件记录本身不会唤醒它；需要已验证的 turn/start/queue 宿主机制。已结束的模型轮次不会被 Python 文件自动复活。

## 5. 本机接口（从项目根执行）

```bash
python3 .ai/scripts/workflow_state.py --root . team-init --session ACTUAL_MAIN_UUID --team STABLE_OWNER_TEAM_ID
python3 .ai/scripts/session_bus.py --root . register --alias planner --file /private/planner-peer.json
python3 .ai/scripts/session_bus.py --root . register --alias worker --file /private/worker-peer.json
python3 .ai/scripts/session_bus.py --root . publish --sender worker --target planner --file /private/stage-result.json
python3 .ai/scripts/session_bus.py --root . prepare-native --id EVENT_ID --target-state active --turn-id ACTUAL_CURRENT_TURN_ID
# 发起方 Main 现在用已验证的目标 endpoint 工具递交输出中的 RPC。
python3 .ai/scripts/session_bus.py --root . mark --id EVENT_ID --result accepted --evidence '实际工具回执 ID/路径'
# 接收方完成了需要的处理后（不是一收到就调用）：
python3 .ai/scripts/session_bus.py --root . resolve --id EVENT_ID --target planner --evidence '已完成的决定/验收记录路径'
# 已验证、确实需要的 queue fallback（会实际发送，不是 dry-run）：
python3 .ai/scripts/session_bus.py --root . send-queue --id EVENT_ID
```

peer 字段为 session_id、host_id、endpoint_label、task_id、authority_contract（已审阅的完整授权文本）、native_verified、queue_verified；按需声明 allow_idle_start、queue_backlog_reviewed。不要直接使用交付包内旧摘要字段。event 字段及语义见上文与 session_bus.py。该 CLI 全局 --root 必须放在子命令前。状态在 Git common-dir 的 jam-workflow-v150/state.sqlite3，不进入提交；同机独立 clone 不共享它，v1.5.0 不声称独立 clone 已支持互通。此时先使用同一 common-dir 的 worktree，或由本地集成者实现并验收明确的单机状态桥，不能偷偷把数据库跨网盘同步。

## 6. STOP 分类

planner 可解的技术问题：worker 保存局面→STOP_DECISION→planner 给在授权范围内的修订 plan→worker 校验 revision/权限后续行。Owner-only 权限/预算/实机决定：planner 汇总一次问 Owner，worker 不自动越过。计划规定的停止验收点：阶段结果不是下一阶段执行许可；只有合同约定可由 planner 批准的门才由 planner 放行。scope 改变或过期 plan 需重审；与已批准 base revision 冲突时拒绝直接应用。
