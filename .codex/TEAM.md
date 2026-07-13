# DoorDog Codex Multi-Agent Architecture

## Status

当前为 **Phase 2 registered production v1**：project config 直接注册九个 production roles 与 `role_probe`，`max_threads = 4`、`max_depth = 1`。Registration 是可用 routing，不是 effective child identity/model/effort evidence；runtime 不暴露的 metadata 保持 `UNKNOWN/INCONCLUSIVE`。

Hooks 尚未配置，等待 capability eval 与 separate user approval。`deep_researcher` 已注册但 dormant-by-policy，每次 invocation 仍需 exact separate user approval。

## Sources of Truth

- Root `AGENTS.md`：repo-wide canonical policy。
- 本文件：Phase 2 orchestration、role routing、waves、lease 与 closure。
- `contracts/*.md`：task、message、review 与 deep-research executable contracts。
- `evals/*.md` / `evals/*.toml`：static、coordination 与 write-safety evidence contract。
- `memory/`：verified durable knowledge，不是 heartbeat/mailbox/live task ledger。

Nested `.codex/AGENTS.md` 只维护 `.codex` subtree，不能覆盖 root policy。

## Hard Invariants

1. Main 是唯一 scope、user approval、acceptance、lease、candidate、integration、memory authorization 与 Git authority。
2. 四个 total threads 包含 Main；一个 wave 最多三个 children。Depth 1，child 不得 recursive fan-out。
3. Shared filesystem 上同一路径同一 revision 只有一个 writer；same-path/resource conflict 必须串行。
4. Child 禁止 stage、commit、push、branch/reset/stash/merge/rebase、扩大 scope 或转移 lease。
5. Review 只针对 frozen candidate；candidate content/status 变化使旧 verdict 失效。
6. `FAIL`、`BLOCKED`、`INCONCLUSIVE`、`NOT_RUN` 与缺失 evidence 都不是 PASS。
7. Static catalog PASS 不证明 effective runtime identity/model/effort；不允许 silent downgrade 或 false model/runtime PASS。
8. Canonical memory 在全部 required review PASS 后由单一 `memory_curator` 写入，Main 再验证。
9. 普通 role ceiling 为 `max`；Deep 是唯一 Sol/Ultra exception，且逐次 approval。

## Registered Role Matrix

| Registry | Model / effort | Sandbox | Trigger / modes |
|---|---|---|---|
| `role_probe` | Terra / high | read-only | `SENTINEL` compatibility evidence |
| `scope_planner` | Sol / xhigh | read-only | scope、architecture、DAG、acceptance、approval-ready plan |
| `context_researcher` | Terra / high | read-only | `REPO_DISCOVERY`、`ISAACLAB_DOCS`、`MEMORY_EXPERIENCE`、`MEMORY_CONTEXT_REVIEW` |
| `deep_researcher` | Sol / ultra | read-only | exact approved deep brief only；never self-activate |
| `isaaclab_worker` | Luna / max | workspace-write | `IMPLEMENT`、`DEBUG`，只写 leased `WRITE_SET` |
| `goal_reviewer` | Sol / max | read-only | `PLAN_GATE`、`CANDIDATE_GATE` |
| `code_reviewer` | Sol / max | read-only | `CODE_QUALITY`；conditional `SECURITY`、`PERFORMANCE`、`DATA_COMPAT` |
| `isaaclab_reviewer` | Sol / max | read-only | independent IsaacLab/high-level API/tensor/reward/fail-fast lane |
| `runtime_qa` | Terra / high | workspace-write | 只写 leased evidence/output，绝不修改 candidate |
| `memory_curator` | Terra / high | workspace-write | review PASS 后原子更新 approved memory entry |

## Phase 2 State Machine and Waves

```text
PREFLIGHT
  -> DISCOVERY_WAVE
  -> PLAN_SYNTHESIS
  -> PLAN_GATE
  -> WAIT_USER_APPROVAL
  -> IMPLEMENTATION_WAVE
  -> FREEZE_CANDIDATE
  -> REVIEW_WAVE_1
  -> TARGETED_FIX | REVIEW_WAVE_2
  -> MEMORY_FINALIZE
  -> MEMORY_CONSISTENCY_CHECK
  -> MAIN_FINAL_AUDIT
  -> MAIN_STAGE_AND_COMMIT
```

### Discovery and Planning

- Main 可并发最多三个 `context_researcher`，每个使用不同 mode/axis，避免重复检索。
- `scope_planner` 综合 scope、architecture、DAG、leases 与 acceptance criteria。
- `goal_reviewer:PLAN_GATE` 独立检查 plan；Main 修订后向 user 请求 explicit approval。
- Deep 只作为 discovery 与 plan 之间的 approved branch；没有 exact per-call brief 不得启动。

### Implementation

- Main 为每个 `isaaclab_worker` 发 self-contained task contract 与 exclusive `WRITE_SET`/resource lease。
- 默认 single writer。多个 worker 仅在 Main 能证明 `WRITE_SET`、artifact directory、GPU、IsaacSim/display/port/process 等全部 disjoint 时并发。
- 任一 path/resource overlap 都建立 dependency edge 并串行；peer 不得互授 lease。
- Write-safety runtime eval 当前 `NOT_RUN`，因此不得把一般 multi-writer safety 声称为 runtime PASS。

### Frozen Review Wave 1

所有 writer terminal、lease released 且 Main freeze manifest/candidate 后，并发三个 independent lanes：

1. `goal_reviewer:CANDIDATE_GATE`
2. `code_reviewer:CODE_QUALITY`
3. `isaaclab_reviewer`

任一 FAIL/INCONCLUSIVE 阻断。Reviewer 不修 code；Main 递增 revision，将 targeted fix 交给获 lease writer，重新 freeze 并重跑 required lanes。

### Review Wave 2

Wave 1 全 PASS 后，最多并发：

1. `runtime_qa`
2. `context_researcher:MEMORY_CONTEXT_REVIEW`
3. 按风险触发的 `code_reviewer:SECURITY|PERFORMANCE|DATA_COMPAT`

Runtime QA 的 `WRITE_SET` 只能包含 evidence/output paths，candidate 必须 before/after immutable。缺少 runtime/resource evidence返回 INCONCLUSIVE，不降级测试并伪报 PASS。

### Memory and Closure

所有 required lane PASS 后，Main 授予 `memory_curator` 一个 atomic memory lease（description/TODO/DONE 与必要 route）。Curator 完成后 Main 重读 actual files、重建 manifest、运行 Memory Context/final audit，然后独占 stage/commit；默认不 push。

## Task, Lease, and Candidate Contract

每个 task 必须使用 `contracts/task-contract.md`，包含 TASK_ID、REVISION、destination/stopping/acceptance、MEMORY_CONTEXT、BASE_SHA/dirty baseline、READ_SET/WRITE_SET/resource lease、dependencies、deliverable 与 VERIFY。

Main live ledger 至少跟踪：

```text
TASK_ID REVISION AGENT STATE BASE_SHA READ_SET WRITE_SET
RESOURCE_LEASES BLOCKED_BY CANDIDATE_ID LAST_SUBSTANTIVE_RESULT
```

Frozen candidate 使用 `contracts/review-contract.md` 的 canonical manifest：approved tracked/untracked/ignored-explicit/deleted paths 全部按 status + exact content hash 排序，结合 BASE_SHA 计算 `CANDIDATE_ID`。Reviewer 必须核对 manifest/worktree，而不是复述 Main 的 ID。

## Message and Lifecycle Semantics

- `send_message`：给 running agent 补 evidence 或 non-destructive correction；不转移 scope/lease。
- Peer `FINDING`/`QUESTION` 可以直接发送，但影响 scope/candidate/verdict/lease 的 distilled finding 必须 mirror 给 Main。
- `followup_task`：唤醒 idle/completed agent处理 bounded targeted follow-up，携带最新 revision/candidate。
- `interrupt_agent`：停止 current turn；不等于 rollback。Main 等待 terminal 后审计完整 lease/partial writes，invalidate candidate，再决定 continuation/reassignment。
- Two-strike abnormal-interrupt fallback：对相同 `TASK_ID` + revision + bounded deliverable + `agent_type` + normalized root-cause `failure_signature`，第一次异常中断完成 terminal/partial-write/lease audit 后最多重试一次；`followup_task` 与 same-role replacement spawn 都计入 retry，不能靠更换 thread/task name 重置。第二次同因异常中断且未交付时，不再第三次 follow-up/spawn，由 Main 接管原批准 scope/lease 内的最小剩余工作。Main 缺少必要 capability 时返回 `BLOCKED`，所有 candidate/review/runtime/memory/Git gate 保持不变。
- Main 在 agents 运行时继续 non-overlapping work，不做高频 polling；final 前所有 spawned agents 必须 terminal 或明确 abandoned。

完整 envelope 与 closure 见 `contracts/message-protocol.md`。

## Deep Research Registered-but-Dormant Policy

`deep_researcher` 每次 invocation 前必须向 user 提交 `contracts/deep-research-contract.md` 的 exact brief。Registration、旧 approval、ordinary research request 或 planner recommendation都不构成调用授权。

- Missing approval：`BLOCKED`。
- Effective Sol/Ultra/read-only 明确 mismatch：`FAIL`。
- Runtime 未暴露任一 effective value：`INCONCLUSIVE`。
- Never self-activate、never spawn child、never write、never downgrade。

## Known Unverified Limits

- Profiles 与 registry 已 static-validated，但 current runtime 可能不暴露 effective child role/model/effort；这些字段只能是 `UNKNOWN/INCONCLUSIVE`。
- Child read-only command runner 曾受 `bwrap` loopback permission 阻断；不能把 command-runner behavior 当作已验证。
- Parallel coordination、write lease collision、interrupt/partial-write 与 hook enforcement 需要对应 eval；未运行项保持 `NOT_RUN`。
- Hooks 当前未配置。只有 `evals/hooks-capability.md` 证明 identity/revision/dynamic lease/path/atomic deny 覆盖且 user另行批准后才可创建。

## Evidence Levels and Closure

- `STATIC_PASS`：parse、registry/path/name/model matrix 与 prompt contract一致。
- `RUNTIME_BEHAVIOR_PASS`：指定 role 完成 tool-free 或 approved runtime behavior contract。
- `INCONCLUSIVE`：effective metadata、sandbox/tool execution 或 required evidence 不完整。
- Requested profile、identity token 或 self-report 不得升级为 effective model/effort PASS。

Main final 前确认：所有 agents terminal；无 active writer/overlapping lease/pending approval；required lanes绑定当前 candidate并 PASS；memory一致；Git index只含批准路径；未验证项明确保留 `INCONCLUSIVE/NOT_RUN`。
