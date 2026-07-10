# Agent Message Protocol

消息用于传递 evidence 与控制 lifecycle，不转移 Main authority。

## Message Envelope

```text
TYPE:
TASK_ID:
REVISION:
FROM:
TO:
CANDIDATE_ID: <value or N/A>
SUMMARY:
EVIDENCE:
ACTION_REQUESTED:
```

## Message Types

- `FINDING`：新 evidence，可能影响另一个 lane。
- `QUESTION`：在既有 scope 内请求澄清。
- `BLOCKED`：当前 stopping condition 无法满足，并给出已尝试 evidence。
- `SCOPE_REQUEST`：请求增加文件、行为、resource lease 或 model tier。
- `CORRECTION`：Main 对 running agent 的方向修正。
- `REVIEW_ISSUE`：reviewer 针对当前 candidate 的具体 finding。
- `HANDOFF`：bounded artifact、diff 或 evidence 已准备好。
- `CLOSURE_READY`：agent 已提交 substantive result，可以进入 terminal state。

## Tool Semantics

### `send_message`

用于向 running agent 发送 evidence、澄清或 correction。它不创建新的 task revision，不扩大 `WRITE_SET`，也不表示原工作已停止。Material scope change 必须由 Main 更新 task contract。

### `followup_task`

用于唤醒 idle agent 处理 targeted fix、补证或同一 bounded context 的下一步。Follow-up 必须带最新 revision 与 candidate context；不能借此规避 approval gate。

### `interrupt_agent`

用于真正停止 current turn。Interrupt 不等于 rollback 或 clean state；Main 随后必须审计 agent 的整个 `WRITE_SET`、artifact 与 lease，再决定 follow-up、abandon 或 reassignment。

## Peer-to-Peer Evidence Transfer

Agent 可以直接把 `FINDING` 或 `QUESTION` 发送给相关 peer，以降低 Main context pollution。但任何会影响 scope、acceptance criteria、candidate、verdict、lease 或 approval 的消息，都必须把同一 distilled summary 同步给 Main。

Peer 不得互相授权 write、model escalation、deep research、candidate mutation 或 Git operation。

## Closure Semantics

- Completion notification 必须包含 required result contract，不得只有 acknowledgement。
- Main 不依赖高频 polling；在 agent 运行期间继续 non-overlapping work，并在 notification/barrier 时汇总。
- Main final 前必须让每个 spawned agent 进入 completed、interrupted 或明确 abandoned 状态。
- Pending peer question、unreturned write lease 或未审计 interrupted writer 都会阻断 closure。
