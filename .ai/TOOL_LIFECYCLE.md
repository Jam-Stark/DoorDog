<!-- managed-by: jam-coding-role; file: TOOL_LIFECYCLE.md -->
# Tool / MCP lifecycle v1.5.0

先区分资源归属，不把“存在时间长”误当“泄漏”。类型为：本 task 的临时工具；同 session 仍在用的 MCP；多 session 共享宿主服务；单独授权的 durable training/eval。只有第一类在本 task 结束时回收。关闭子 agent 后应核对其实际临时进程；不能假定关闭聊天窗口一定触发 OS 进程回收。

先保存一个只读基线：

```bash
python3 .ai/scripts/process_inventory.py --limit 100 > /private/process-before.json
```

它只列同 UID 的 PID/PPID/启动标识/RSS/本次盘点内命令分组编号，不输出可能含密钥的命令参数，也不 kill。结束后再取 after 对照；命令参数只在内存中逐字比较；分组编号仅在单次盘点内有效，重复只是排查线索，不能据此自动删除。

## 优先原生、缺口才用包装器

已有 native command/process handle 时，用宿主提供的 terminate/kill/close API，并核对回执。不要绕过宿主用进程名扫杀。共享 MCP 能否复用取决于实际宿主；没有经过验证的 pooling 能力就不能仅在文档里宣称“一台机器只起一个”。先盘点哪些工具是每次调用/每个 child 重复启动，按必要能力缩小子 agent 工具集，避免不需要的 MCP eager startup。

stdio MCP 正常关闭顺序：停止接收新任务→关闭 stdin→给进程自行退出的时间→只对确定归属的进程 TERM→宽限后 KILL。MCP 不需要虚构一个通用 shutdown JSON-RPC 方法。远程 HTTP MCP 关闭客户端请求/连接，不杀第三方服务器。tool request timeout 也不等于 server 进程已经回收。

## 本包可运行的 Linux 边界

`tool_guard.py` 是 **opt-in 的短生命周期工具/stdio MCP 包装器**，不是全系统清理器。要求 Linux + pidfd。它在启动前记录 owner PID/启动标识、boot ID、UID、随机继承 token、可执行文件名（不记录参数）；子树继承 token。任务退出、父 owner 消失、取消或 stdio EOF 后清理被登记的临时子树。stdout 保持透明；诊断走 stderr；原子收据只写本机私有路径。

```bash
# 只演示无副作用短工具；不等于授权任何训练。
python3 .ai/scripts/tool_guard.py run \
  --receipt /private/unique-tool-receipt.json --owner-pid ACTUAL_OWNER_PID \
  --owner-session ACTUAL_SESSION_UUID --task-id ACTUAL_TASK_ID \
  -- python3 -c 'print("tool smoke")'

# stdio MCP 启动配置的 command/args 可选择显式接入同一包装器：
python3 .ai/scripts/tool_guard.py run \
  --receipt /private/unique-mcp-receipt.json --owner-pid ACTUAL_HOST_PID \
  --owner-session ACTUAL_SESSION_UUID --task-id ACTUAL_TASK_ID \
  --stdio -- EXACT_MCP_COMMAND EXACT_ARGS

# wrapper 和 owner 均已死亡时，仅审查已登记的孤儿（默认不 kill）：
python3 .ai/scripts/tool_guard.py reap --receipt /private/old-tool-receipt.json
# 人工确认这个 task 的临时资源应结束后，再加 --apply。
```

**任务结束不等于宿主 PID 结束。** 多个 session 可能共用一个长期存活的宿主进程，因此还须登记逻辑 owner-session/task-id；在该任务的成功、失败或取消 teardown 中，对它实际登记的临时 receipt 逐个执行 finish，而不能只等宿主退出。

```bash
# 默认仅核对归属、预览。已确认本任务临时工具应关闭时才 --apply。
python3 .ai/scripts/tool_guard.py finish --receipt /private/unique-mcp-receipt.json \
  --owner-session ACTUAL_SESSION_UUID --task-id ACTUAL_TASK_ID
python3 .ai/scripts/tool_guard.py finish --receipt /private/unique-mcp-receipt.json \
  --owner-session ACTUAL_SESSION_UUID --task-id ACTUAL_TASK_ID --apply
```

finish 只终止这份私有 receipt 对应的包装器/被标记的临时后代，不给共享宿主 PID 发信号。session/task 不匹配则拒绝；共享服务根本不应登记成这类临时 receipt。该 teardown 应成为本地 worker 的任务收尾步骤，不另起一个 LLM 定时器。没有登记逻辑 owner 的老 receipt 不能用 finish 猜归属。

不能传临时 exec shell 的 PID 却指望它退出后工具仍长期存活；owner 必须是实际持有生命周期的进程。每次启动使用唯一 receipt，不能复用旧文件。包装器不重写用户的全局 MCP 设置，只有本地验证后才接入。

没有 token 的历史遗留进程、主动清空环境的后代、其他用户进程都不会被该脚本误判并强杀。残留必须报告和单独确认；这限制了清理覆盖范围，但比杀错训练安全。wrapper 被 SIGKILL 时不能执行 finally；持久收据允许之后显式 reap。机器断电、睡眠、共享服务生命周期不由本脚本保证。

macOS 需要另验 launchd/进程组或原生宿主句柄；Windows 需要 Job Objects/原生句柄。本包没有实现这两个 OS 的自动回收，不能在它们上面假装工具守卫已经生效。

## 禁止事项与验收

禁止 pkill node/python/npx/codex，禁止按“运行超过 30 分钟”杀进程，禁止静默日志判断训练死锁。禁止把 training/eval/tmux、Codex App、shared app-server 包成 ephemeral tool。不得为解决泄漏新造每个 hook/每个消息一个常驻管理进程。

部署验收：空闲进程基线→连续 30 次短工具→失败/取消/stdio EOF/owner 退出→数量和 RSS 回到合理基线；记录 pid/start identity，不只看名称。另开一个获授权的独立长任务作为保护对象，确认它完全未被触碰。历史无归属进程先出清单，请 Owner 确认后针对精确身份处理；这不是本包默认自动动作。

本项目实施约束：以上运行验收场景是后续按需验证说明，不是本次安装自动启动的测试任务。Owner 确认实现或报告具体问题后再安排相关测试；未执行项保持 NOT_RUN。
