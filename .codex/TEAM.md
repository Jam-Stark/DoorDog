# DoorDog Codex Multi-Agent Architecture

## Status

当前为 **Phase 0A foundation + role-discovery sentinel**。本阶段只建立 project config、team contracts 与 `role_probe`；production roles、hooks、parallel writers 和 deep-research agent 尚未启用。

## Sources of Truth

- Repository root `AGENTS.md`：repo-wide canonical policy，拥有最高 project-policy priority。
- 本文件：multi-agent orchestration architecture 与 rollout boundary。
- `contracts/*.md`：delegation、message、review 与 deep-research 的 executable contract。
- `evals/*.md`：可重复的 compatibility smoke。
- `memory/`：verified durable project knowledge；不是 agent heartbeat、mailbox 或 live task ledger。

Nested `.codex/AGENTS.md` 只约束 `.codex/` subtree，不承担 repository root policy。

## Hard Invariants

1. Main 默认使用 `gpt-5.6-sol` / `xhigh`，并且是唯一 scope、approval、lease、integration 与 Git authority。
2. `agents.max_threads = 4`，包含 Main；一个 wave 最多同时运行三个 child lanes。
3. `agents.max_depth = 1`；v1 child 不得 recursive fan-out。
4. Shared filesystem 上同一文件同一时刻只有一个 writer。Main 在派发前登记 `READ_SET`、`WRITE_SET` 与 resource lease。
5. Child 禁止 stage、commit、push、reset/revert unrelated work，禁止扩大 scope 或 acceptance criteria。
6. Review 只读取 frozen candidate；source/config diff 改变后旧 verdict 全部失效。
7. Canonical memory 只有一个 writer，并且晚于 required code review 与 QA。
8. 每个 role 显式固定 model/effort；role 未生效、model unavailable 或 silent downgrade 都不能继续伪装成功。
9. 普通 role 的 reasoning 上限是 `max`。`gpt-5.6-sol` / `ultra` 只允许 deep research，且每次 invocation 都要 user 明确批准。
10. `FAIL`、`INCONCLUSIVE`、`NOT_RUN` 与缺失 evidence 都不是 PASS。

## Authority Model

Main 独占以下决定：

- 明确 destination、stopping condition 与 acceptance criteria；
- 请求和记录 user approval；
- 分配、扩大或转移 file/resource lease；
- 选择 required lanes、model tier 与 escalation；
- freeze candidate、判定 verdict invalidation、整合 patch；
- 授权 canonical memory update；
- stage 与 commit。除非 user 明确要求，否则不 push。

Child 只在 task contract 内执行 bounded work。需要额外文件、资源、model 或行为变化时，返回 `SCOPE_REQUEST`，不得先做后报。

## Orchestration State Machine

```text
PREFLIGHT
  -> DISCOVERY_WAVE
  -> PLAN_SYNTHESIS
  -> PLAN_REVIEW
  -> WAIT_USER_APPROVAL          # complex product write only
  -> IMPLEMENTATION_WAVE
  -> FREEZE_CANDIDATE
  -> REVIEW_WAVE_1
  -> REVIEW_WAVE_2
  -> TARGETED_FIX | MEMORY_FINALIZE
  -> MEMORY_CONSISTENCY_CHECK
  -> MAIN_FINAL_AUDIT
  -> MAIN_STAGE_AND_COMMIT
```

Deep research 是 `DISCOVERY_WAVE` 与 `PLAN_SYNTHESIS` 之间的 optional approved branch，必须满足 `contracts/deep-research-contract.md`。

## Concurrent Waves

并发只用于 dependency-independent lanes；Main 在 child 运行时可以执行 non-overlapping work。

- Discovery：最多三个 read-only lanes，例如 scope、codebase、official API evidence。
- Implementation：v1 默认单 writer。未来只有 `WRITE_SET`、output 与 resource lease 完全不重叠时才允许 parallel writers。
- Review Wave 1：Goal/Constraint、Code Quality、IsaacLab/Fail-fast。
- Review Wave 2：Runtime QA、Memory Context，以及按风险触发的 Security 或 Final Gate。
- Deep research：只有逐次 user approval 后才可建立 read-only lanes；Phase 0A 没有可运行的 deep role TOML。

Wave barrier 要求所有 dependency lanes 返回 substantive terminal result。只返回 acknowledgement 不算完成。

## Shared Filesystem Leases

Main 的 live task ledger 至少记录：

```text
TASK_ID
REVISION
AGENT
STATE
BASE_SHA
READ_SET
WRITE_SET
RESOURCE_LEASES
BLOCKED_BY
CANDIDATE_ID
LAST_SUBSTANTIVE_RESULT
```

Read lease 可以重叠；write lease 不可重叠。Git index、branch、commit 永久属于 Main。一个 memory entry 的 `description.md`、`TODO.md` 与 `DONE.md` 作为同一 atomic write unit。

Interrupted writer 可能留下 partial writes。Main 必须先审计其完整 `WRITE_SET` 和 dirty baseline，再 follow up、转移 lease 或重新派发，不能直接假定 rollback。

## Frozen Candidate

所有 writer terminal 后，Main 审计 dirty baseline、assigned paths 与 static validation，然后建立 canonical manifest：

```text
CANDIDATE_MANIFEST = sort_by_repo_relative_path([
  path + status_relative_to_BASE_SHA + sha256(exact_current_content_or_DELETED)
  for every approved task path
])

CANDIDATE_ID = sha256(BASE_SHA + canonical_serialize(CANDIDATE_MANIFEST))
```

Manifest 必须覆盖 approved `WRITE_SET` 与明确批准的 task artifact 中的每个路径，包括 tracked modification、tracked deletion、untracked file、ignored-but-explicit task file，以及 approved path 下递归出现的文件。存在的文件记录 exact content hash；deletion 使用明确的 `DELETED` status/sentinel。Main 还必须确认没有 out-of-scope changed path。

每个 reviewer 必须验证 manifest 路径全集、status、content hash 与 worktree 精确一致，并回报同一个 `CANDIDATE_ID`；只复述 Main 给出的 ID 不算验证。Review 期间禁止 writer 修改 candidate。任何 approved task path 的 status/content 变化都生成新 ID，并使旧 code/config/runtime verdict 失效；只改 canonical memory 时必须重建 manifest，并重跑 Memory Context 与 final audit。

详细 verdict 与 evidence 规则见 `contracts/review-contract.md`。

## Message and Agent Lifecycle

Message types、`send_message`、`followup_task`、`interrupt_agent` 与 peer evidence transfer 见 `contracts/message-protocol.md`。

核心语义：

- `send_message` 为 running agent 补充 evidence 或 non-destructive correction；不会转移 authority。
- `followup_task` 唤醒 idle agent 处理同一 bounded context 中的 targeted follow-up。
- `interrupt_agent` 真正停止当前 turn；停止后必须进行 partial-write audit。
- Peer-to-peer finding 若影响 scope、candidate 或 verdict，必须同步给 Main。
- Final 前 Main 必须让所有 spawned agents 进入 terminal state，不能把 cleanup 留给 user。

## Memory Lifecycle

Live task state 留在当前 task ledger，包括 heartbeat、agent state、lease、revision、candidate 与 transient blockers；不得写进 canonical memory。

Canonical memory 只记录 verified architecture decision、completed TODO、stable blocker、reproducible runtime/debug fact 与 cross-task handoff。Required reviews PASS 后，由单一 memory writer atomic 更新相关 `TODO.md`、`DONE.md` 与 `description.md`，Main 再做 consistency audit。Static、smoke、runtime 与 training evidence 必须明确区分。

## Deep Research Exception

Deep research 是唯一允许 `gpt-5.6-sol` / `ultra` 的 role class。每次调用前 Main 都必须提供 research brief 并取得 user 明确确认；它保持 read-only，不能 self-activate、写 code/memory、改变 plan 或创建 Git state。

如果 Ultra、effective role 或 effort 缺少明确 runtime evidence，结果为 `INCONCLUSIVE`；如果明确 mismatch，结果为 `FAIL`。禁止自动降级到 `max` 或其他 model。Phase 0A 只保存 contract，不创建 production deep agent TOML。

## No-Fallback Policy

- 不因 role selection 失败而切换 built-in/default agent 并继续相同 gate。
- 不因 model/effort unavailable 而 silent downgrade。
- 不把 static parse、requested profile 或 prompt echo 当作 effective runtime evidence。
- 不用 defensive fallback 掩盖 IsaacLab API、tensor shape、device、asset 或 training semantics 问题。

## Closure Contract

Main final 前确认：

- 所有 spawned agents 为 completed、interrupted 或明确 abandoned；
- 没有 active writer、overlapping lease 或 pending scope/deep/resource approval；
- 每个 mandatory lane 有 substantive result，并绑定当前 candidate；
- code/config 与 canonical memory 一致，或明确记录 no memory delta；
- Git index 只包含当前 task 文件；
- 未验证行为保持 `INCONCLUSIVE` 或 `NOT_RUN`。

## Phase 0A/1 Gates

### Foundation Artifact Acceptance

Phase 0A static foundation artifact 可以在以下 evidence 全部 PASS 后完成：

1. 两个 TOML 均可由 Python `tomllib` 解析。
2. Codex strict-config startup parse 接受 project config 与 sentinel schema/path。
3. `config_file`、required files、relative links 与 allowlist paths 全部存在且一致。
4. `git diff --check` 与 candidate manifest audit PASS。

这个 static acceptance 只证明 foundation artifact 可解析且内部一致，不证明 custom role 已在 runtime 生效。

### Runtime Role-Discovery Activation

Role-discovery runtime 在取得 explicit effective role/model/effort/sandbox 与 no-write evidence 前必须保持 `NOT_RUN` 或 `INCONCLUSIVE`。Sentinel token、文件存在、requested profile、strict-config parse 或 agent 复述都不能把该 gate 变成 PASS。

只有 runtime activation gate PASS 后，才可另行批准 production roles。Production role TOML、deep-research TOML、hooks 与 parallel writers 在此之前全部保持 disabled；foundation artifact acceptance 不得绕过这一 activation gate。
