# Parallel Coordination Eval

## Status and Scope

`NOT_RUN`. 本 eval 验证 default Main + 3 与 independence-proven expanded Main + 5 的 tool-free/read-only coordination、message handoff 与 lifecycle；禁止 shell、file write、deep research、Git 或 external action。

## Preconditions

- Role-contract static matrix PASS。
- Fresh trusted project-scoped session；记录 worktree/index baseline。
- 每个 task contract 的 `WRITE_SET` 为空，resource lease 为 none。
- Main 记录 agent task name、state、revision 与 substantive result。

## Wave A: Discovery Coordination

Main 同时启动三个不同 axis：

1. `context_researcher:REPO_DISCOVERY`
2. `context_researcher:ISAACLAB_DOCS`
3. `context_researcher:MEMORY_EXPERIENCE`

全部使用提供的静态 fixture text，不调用工具。验证：

- 三个 agent 同时 active，Main 保持第四个 thread并执行 non-overlapping synthesis准备。
- Main 对一个 running lane 使用 `send_message` 发送 `CORRECTION`；agent确认但不扩大 scope/revision。
- 一个 lane向 peer发送 `FINDING`，并把同一 distilled finding mirror给 Main；peer在最终结果中引用该 evidence。
- 每个 completion含 substantive structured output与 `LEASE_RELEASE: read-only`，不是 acknowledgement。

## Wave B: Review Coordination

使用同一个 immutable text candidate，并发：

1. `goal_reviewer:CANDIDATE_GATE`
2. `code_reviewer:CODE_QUALITY`
3. `isaaclab_reviewer`

验证三个结果绑定相同 synthetic `CANDIDATE_ID`，互不代替。Main 对一个 completed/idle agent使用 `followup_task` 请求 bounded evidence clarification，必须携带最新 revision/candidate。

## Wave C: Independence-Proven Expansion

Main 先为五个 tool-free/read-only tasks 记录 expansion proof：所有 input 已固定、`BLOCKED_BY` 为空、没有 sibling result handoff、`WRITE_SET` 为空、resource lease 为 none。然后同时启动五个 non-Deep children，以不同 role/mode/axis 处理互不依赖的 synthetic deliverables。

验证：

- 五个 children 同时 active，Main 保持第六个 total thread并执行 non-overlapping orchestration。
- Main 在 spawn 前而不是事后记录 independence proof；更换 task name 不能替代 proof。
- 所有 children substantive completion 并 terminal 后，active count 回落；没有 hidden child 占用或第六个 child spawn。
- 若移除任一 proof field，Main 保持 default 3，不尝试第四个 child。

## Interrupt Case

在独立 read-only lane 中：

1. Main 启动一个会等待额外 input 的 tool-free task。
2. Main 使用 `interrupt_agent` 停止它。
3. 验证该 lane进入 interrupted terminal、没有 replacement race、没有 pending peer question。
4. 因 `WRITE_SET` 为空，partial-write audit应明确为 no-write—not assumed rollback。

## Evidence and Verdict

```text
STATUS: PASS | FAIL | INCONCLUSIVE
ACTIVE_THREAD_TRACE:
CORRECTION_TRACE:
PEER_FINDING_AND_MAIN_MIRROR:
FOLLOWUP_TRACE:
INTERRUPT_TRACE:
TERMINAL_AGENT_LIST:
WORKTREE_AND_INDEX_BEFORE_AFTER:
EFFECTIVE_METADATA:
```

- PASS：所有 coordination/lifecycle行为与 no-write evidence完整。
- FAIL：scope/authority转移、missing Main mirror、无 proof 扩展、超过 Main+5、unexpected tool/write/deep、agent未 terminal。
- INCONCLUSIVE：surface不暴露必要 state/message evidence。Effective model/effort未暴露时字段保持 UNKNOWN，但不能因此虚报 metadata PASS。

## Stopping Condition

所有 spawned agents terminal，message/followup/interrupt trace完整，worktree/index与 baseline一致；不创建任何 runtime artifact。
