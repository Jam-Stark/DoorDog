# DoorDog Codex Multi-Agent Architecture

## Status

当前为 **Phase 2 registered production v1**：project config 直接注册九个 production roles 与 `role_probe`。Configured capacity target 为 Main + 最多 5 active children；default wave 为 3，可证明相互独立时由 Main 自主扩展到 5，`max_depth = 1`。Fresh-task effective 6-thread capacity 尚未 runtime 验证；registration 是可用 routing，不是 effective child identity/model/effort evidence，runtime 不暴露的 metadata 保持 `UNKNOWN/INCONCLUSIVE`。

Pipeline 使用 `FAST_PATH`、`STANDARD_PATH`、`HIGH_RISK_PATH` 三级 route。绝大多数工作默认 Fast 或 Standard；High 只有 user 对 exact `HIGH_RISK_BRIEF` 明确同意后才能进入。Hooks 尚未配置。`deep_researcher` 已注册但 dormant-by-policy，每次 invocation 仍需 exact separate user approval。

## Sources of Truth

- Root `AGENTS.md`：repo-wide canonical policy 与 route authority。
- 本文件：Phase 2 orchestration、role routing、waves、lease 与 closure。
- `contracts/*.md`：task、message、review 与 deep-research executable contracts。
- `evals/*.md` / `evals/*.toml`：static、coordination 与 write-safety evidence contract。
- `memory/`：verified durable knowledge，不是 heartbeat/mailbox/live task ledger。

Nested `.codex/AGENTS.md` 只维护 `.codex` subtree，不能覆盖 root policy。

## Hard Invariants

1. Main 是唯一 scope、route、user approval、acceptance、lease、candidate、integration、memory authorization 与 Git authority。
2. Main 选择最低充分 route；Fast/Standard 是默认，High 必须先获得 user 对 exact brief 的明确同意。
3. Configured budget 的六个 total threads 包含 Main；default wave 为三个 children，满足 independence proof 时 Main 可自主扩展到最多五个 active children。Live task 服从实际暴露的更低上限；Depth 1，child 不得 recursive fan-out。
4. Shared filesystem 上同一路径同一 revision 只有一个 writer；same-path/resource conflict 必须串行。
5. Child 禁止 stage、commit、push、branch/reset/stash/merge/rebase、扩大 scope 或转移 lease。
6. Standard/High review 只针对 frozen candidate；Fast 不创建 candidate。`FAIL`、`BLOCKED`、`INCONCLUSIVE`、`NOT_RUN` 与缺失 evidence 都不是 PASS。
7. 每个 review concern 只有一个 owner；无 risk trigger 不开 lane，不重复 full-manifest audit，不为形式完整性重复已有 evidence。
8. Narrow fix 只重跑 impacted lanes；只有 scope、API/runtime semantics、candidate topology 或 material dependency 改变时才 full rerun。
9. 无 durable memory delta 不开 memory lane；Fast/Standard mechanical memory 由 Main 原子写入并重读验证。
10. Static catalog PASS 不证明 effective runtime identity/model/effort；不允许 silent downgrade 或 false model/runtime PASS。
11. 普通 role ceiling 为 `max`；Deep 是唯一 Sol/Ultra exception，且逐次 approval。

### Adaptive Wave Expansion

Main 在 spawn 第四、第五个 concurrent child 前必须记录：

1. 所有 sibling task 使用 frozen/既有 input，之间没有 `BLOCKED_BY`、result handoff 或 approval dependency。
2. Read-only lanes 可以重叠 `READ_SET`；任何 writer 的 `WRITE_SET` 与 artifact/output path 必须两两 disjoint。
3. GPU、IsaacSim、display、port、process、external service 与其他 resource lease 不冲突。
4. Active-child count 包含尚未 terminal 的旧 child；总数不得超过 5，也不得超过 live task 实际暴露的更低上限。

缺少任一 proof 时使用 default 3。Writer 不因 wave expansion 获得额外 authority；same-path 或 resource conflict 始终串行。

## Registered Role Matrix

| Registry | Model / effort | Sandbox | Trigger / modes |
|---|---|---|---|
| `role_probe` | Terra / high | read-only | `SENTINEL` compatibility evidence |
| `scope_planner` | Sol / xhigh | read-only | unresolved scope、architecture、DAG、acceptance、approval-ready plan |
| `context_researcher` | Terra / high | read-only | `REPO_DISCOVERY`、`ISAACLAB_DOCS`、`MEMORY_EXPERIENCE`；durable delta 时才用 `MEMORY_CONTEXT_REVIEW` |
| `deep_researcher` | Sol / ultra | read-only | exact approved deep brief only；never self-activate |
| `isaaclab_worker` | Luna / max | workspace-write | Standard/approved High 的 `IMPLEMENT`、`DEBUG`；只写 leased `WRITE_SET` |
| `goal_reviewer` | Sol / max | read-only | conditional `PLAN_GATE`、`CANDIDATE_GATE` |
| `code_reviewer` | Sol / max | read-only | source/config 默认 `CODE_QUALITY`；conditional `SECURITY`、`PERFORMANCE`、`DATA_COMPAT` |
| `isaaclab_reviewer` | Sol / max | read-only | actual IsaacLab/RL/reward/env/training semantics change |
| `runtime_qa` | Terra / high | workspace-write | targeted QA；只写 leased evidence/output，绝不修改 candidate |
| `memory_curator` | Terra / high | workspace-write | non-mechanical durable delta 且 route-triggered review PASS 后更新 approved entry |

## Route Gate

```text
TASK_INTAKE
  -> all low-risk/local criteria satisfied -> FAST_PATH
  -> ordinary product work                -> STANDARD_PATH (default)
  -> high-risk trigger found              -> HIGH_RISK_BRIEF -> WAIT_USER_CONSENT
       -> approved                         -> HIGH_RISK_PATH
       -> declined                         -> safely narrow to STANDARD | BLOCKED
```

Route selection 不以 agent 数量、文件数量或“多审一次更放心”为依据，而以最小充分 evidence 和实际 blast radius 为依据。

### `FAST_PATH`

用于 bounded、low-risk、local/reversible 的问答/read-only inspection、straightforward diagnosis、typo/format/prose、少量 docs、mechanical memory、localized simple implementation/bugfix 与 obvious bounded tooling config tweak。

```text
MINIMAL_MEMORY -> MAIN_DIRECT_WORK -> TARGETED_VALIDATION
  -> MEMORY_CONSISTENCY_IF_TOUCHED -> ONE_MAIN_DIFF_AUDIT -> COMMIT_IF_NEEDED
```

不 spawn、不建 delegated task/lease/candidate、不运行 reviewer、不调用 curator。一次 targeted validation + 一次 Main audit 是默认上限；scope/risk 扩大时升级到 Standard，命中 High trigger 时先请求 consent。

### `STANDARD_PATH` (default product route)

用于 acceptance 清楚的普通 feature/bugfix/debug、bounded multi-file change、normal IsaacLab/API-sensitive task，以及需要 worker 或 targeted reviewer 的工作。User 的 exact change/build/fix request 是该 scope 的 implementation authorization；无需再申请 route approval。

```text
MINIMAL_CONTEXT / OPTIONAL_DISCOVERY_0_TO_3
  -> CONCISE_MAIN_PLAN
  -> OPTIONAL_PLANNER_OR_PLAN_GATE_IF_TRIGGERED
  -> LEASE_BOUND_IMPLEMENTATION
  -> MAIN_LIGHTWEIGHT_FREEZE
  -> CODE_REVIEW + TARGETED_RUNTIME_QA (source/config default)
  -> CONDITIONAL_RISK_LANES_ONLY
  -> DURABLE_MEMORY_IF_ANY
  -> ONE_MAIN_FINAL_AUDIT_AND_COMMIT
```

- Main 可完整使用 ordinary registered roles 与 adaptive 5-child ceiling；不得为凑 wave 启动无必要 discovery/review。
- `scope_planner` 只在 design/scope 未决时使用；`goal_reviewer:PLAN_GATE` / `CANDIDATE_GATE` 只在 goal、acceptance、authorization risk 存在时使用。
- `isaaclab_reviewer` 只在实际修改 IsaacLab/RL/reward/observation/action/scene/env/training semantics 时使用；普通非语义 tooling/config 不自动触发。
- Security、Performance、Data Compatibility 只在对应 surface 改变时使用。
- `MEMORY_CONTEXT_REVIEW` / `memory_curator` 只在存在 non-mechanical durable memory delta 时使用。
- Deep 可由 Main 按 exact brief 申请该次 user approval；获批前不调用。请求 Deep 不自动升级 High。

### `HIGH_RISK_PATH` (explicit-consent only)

候选 trigger 包括：large cross-subsystem architecture、security/auth boundary、persistent data migration、conflicting multi-writer/resource topology、repeated material failure、昂贵长时间 training/eval，或高影响但 semantics/acceptance 仍模糊的 change。普通 bounded IsaacLab task 保持 Standard。

进入前 Main 提交：

```text
HIGH_RISK_BRIEF
WHY_STANDARD_IS_INSUFFICIENT:
APPROVED_SCOPE:
EXPECTED_AGENTS_AND_LEASES:
TRIGGERED_REVIEW_LANES:
RUNTIME_RESOURCE_COST:
STOPPING_CONDITION:
```

User consent 前只允许 Standard 范围内的 bounded read-only discovery/planning，不启动 High writer/review wave。Consent 后运行 brief 中批准的 implementation DAG 和 risk-triggered review/runtime lanes；不再重复索要 generic implementation approval，除非 material scope expansion。

High 也不“review everything”：每个 concern 一个 owner，只有 brief 有 justification 的 lane 才 mandatory，manifest 不由每个 reviewer 重算，narrow fix 只重跑 impacted lanes，无 durable delta 跳过 memory lanes。

## Delegation, Lease, and Candidate Contract

每个 delegated Standard/High task 使用 `contracts/task-contract.md`，包含 `ROUTE`、authorization evidence、TASK_ID/REVISION、destination/stopping/acceptance、MEMORY_CONTEXT、BASE_SHA/dirty baseline、READ_SET/WRITE_SET/resource lease、dependencies、deliverable 与 VERIFY。Fast 不创建 dummy delegated contract。

Main live ledger 至少跟踪：

```text
TASK_ID REVISION ROUTE AGENT STATE BASE_SHA READ_SET WRITE_SET
RESOURCE_LEASES BLOCKED_BY CANDIDATE_ID LAST_SUBSTANTIVE_RESULT
```

Main 对 Standard/High frozen candidate 建立 canonical manifest，覆盖 approved tracked/untracked/ignored-explicit/deleted task paths，并在 freeze 与 pre-commit 各验证一次。Reviewer 只验证 assigned concern 所需 paths/entries 与 supplied identity，不重复全量重算。

## Review and Fix Semantics

- Standard source/config 默认 `code_reviewer:CODE_QUALITY` + targeted `runtime_qa`；其余按 trigger。
- High 使用 user-approved brief 中的 risk lanes，不把所有 registered reviewer 自动设为 mandatory。
- 所有 triggered lanes 必须绑定同一 candidate。Reviewer 不修 code。
- Main 将 finding 交给有 lease 的 writer做最小 targeted fix；只使 affected verdict 失效。
- Scope、public/API contract、runtime semantics、candidate topology 或 material dependency 改变时，Main 才宣布 full rerun。
- Main 不重复 reviewer 已覆盖的 concern；pre-commit 只复核 manifest、批准路径、triggered verdict 与 memory consistency。

完整规则见 `contracts/review-contract.md`。

## Message and Lifecycle Semantics

- `send_message`：给 running agent 补 evidence 或 non-destructive correction；不转移 scope/lease。
- Peer `FINDING`/`QUESTION` 可以直接发送，但影响 scope/candidate/verdict/lease 的 distilled finding 必须 mirror 给 Main。
- `followup_task`：唤醒 idle/completed agent处理 bounded targeted follow-up，携带最新 revision/candidate。
- `interrupt_agent`：停止 current turn；不等于 rollback。Main 等待 terminal 后审计完整 lease/partial writes，invalidate candidate，再决定 continuation/reassignment。
- Two-strike abnormal-interrupt fallback：相同 `TASK_ID` + revision + bounded deliverable + `agent_type` + normalized root-cause `failure_signature` 第一次异常中断完成 audit 后最多重试一次；第二次同因中断且未交付时，不再第三次启动，由 Main 接管原批准 scope/lease 内最小剩余工作。Main 缺少必要 capability 时返回 `BLOCKED`。Takeover 仍服从当前 route 实际 triggered gates。
- Main 在 agents 运行时继续 non-overlapping work，不做高频 polling；final 前所有 spawned agents 必须 terminal 或明确 abandoned。

完整 envelope 与 closure 见 `contracts/message-protocol.md`。

## Deep Research Registered-but-Dormant Policy

Standard 与 approved High 都可以由 Main 提交 `contracts/deep-research-contract.md` 的 exact brief，请求该次 user approval。Registration、旧 approval、ordinary research request、High consent 或 planner recommendation都不构成 Deep invocation authorization。

- Missing per-invocation approval：`BLOCKED`。
- Effective Sol/Ultra/read-only 明确 mismatch：`FAIL`。
- Runtime 未暴露任一 effective value：`INCONCLUSIVE`。
- Never self-activate、never spawn child、never write、never downgrade。

## Known Unverified Limits

- Configured capacity target 已改为 6 total threads；App restart + fresh-task occupancy evidence 完成前，effective runtime capacity 保持 `NOT_RUN`。
- Profiles 与 registry 已 static-validated，但 current runtime 可能不暴露 effective child role/model/effort；这些字段只能是 `UNKNOWN/INCONCLUSIVE`。
- Child read-only command runner 曾受 `bwrap` loopback permission 阻断；不能把 command-runner behavior 当作已验证。
- Three-route selection、triggered-lane pruning、impacted-only rerun 与 High consent behavior 尚未 targeted runtime eval；static policy consistency 不能升级为 runtime PASS。
- Hooks 当前未配置。只有 `evals/hooks-capability.md` 证明 capability 且 user另行批准后才可创建。

## Evidence Levels and Closure

- `STATIC_PASS`：parse、registry/path/name/model matrix 与 prompt contract一致。
- `RUNTIME_BEHAVIOR_PASS`：指定 role 完成 approved runtime behavior contract。
- `INCONCLUSIVE`：effective metadata、sandbox/tool execution 或 required evidence 不完整。

Main final 前按 route 确认：Fast 完成 targeted validation、必要 memory consistency 与一次 exact diff audit；Standard/High 的所有 spawned agents terminal、无 active writer/overlapping lease、所有 triggered lanes 对当前 candidate PASS。所有 route 都要求 Git index 只含批准路径，未验证项明确保留 `INCONCLUSIVE/NOT_RUN`。
