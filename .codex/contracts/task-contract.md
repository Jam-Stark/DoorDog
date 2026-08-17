# Delegated Task Contract

每个 delegated task 必须由 Main 提供完整 contract。缺失 destination、stopping condition、write ownership 或 validation target 时，child 返回 `BLOCKED` 或 `SCOPE_REQUEST`，不得自行扩展。

## Route Applicability

本 contract 只适用于会 spawn child 的 `STANDARD_PATH` / `HIGH_RISK_PATH` delegated task。Main-only `FAST_PATH` 不创建 dummy task contract、lease ledger 或 candidate；若 Fast 执行中升级，Main 先审计已有 diff，再从最新 baseline/revision 建立完整 contract。

- `STANDARD_PATH`：`AUTHORIZATION_EVIDENCE` 可以引用 user 对 exact change/build/fix scope 的原始请求；无需额外 route approval。
- `HIGH_RISK_PATH`：必须附 user 对 exact `HIGH_RISK_BRIEF` 的明确 consent evidence。
- Deep invocation 不由本 contract 授权；Standard/High 都必须另走 `deep-research-contract.md` 的逐次 approval。

## Required Envelope

```text
TASK_ID:
REVISION:
ROLE:
ROUTE: STANDARD_PATH | HIGH_RISK_PATH
AUTHORIZATION_EVIDENCE:

DESTINATION:
STOPPING_CONDITION:
ACCEPTANCE_CRITERIA:

BACKGROUND:
MEMORY_CONTEXT:
  - exact paths
  - read order
  - verified decisions and caveats

PRE_EXISTING_DIRTY_PATHS:
FROZEN_PATHS:  # required for review/QA/curator tasks after freeze

READ_SET:
WRITE_SET:
RESOURCE_LEASES:

DEPENDENCIES:
BLOCKED_BY:

DELIVERABLE:
VERIFY:

MUST_DO:
MUST_NOT_DO:

OUTPUT_CONTRACT:
```

## Contract Semantics

- Main 独占 route、scope、approval、lease 与 acceptance criteria。
- Child 必须核对 route 与 authorization evidence：Standard 接受 exact originating user request；High 缺少 exact brief consent 时返回 `BLOCKED`。
- `READ_SET` 可与其他 reader 重叠；`WRITE_SET` 必须是 exclusive lease。
- Child 只能写 `WRITE_SET`，不得 stage、commit、push、reset 或清理 pre-existing dirty paths。
- 发现额外工作时发出 `SCOPE_REQUEST`；在 Main 回复前保持 blocked。
- Shared output directory、GPU、IsaacSim process、display 与 port 都必须作为 resource lease 明确登记。
- Task revision 改变时，child 必须确认使用最新 contract；旧 revision 的结果不能直接并入新 candidate。
- Review/QA/curator tasks additionally receive the current `REVISION` and exact `FROZEN_PATHS`; their results bind to that revision and path list.

## Required Result

```text
STATUS: PASS | FAIL | BLOCKED | INCONCLUSIVE

RESULT:
EVIDENCE:
  - files and symbols
  - exact commands
  - actual output

CHANGED_PATHS:
VALIDATION:
UNVERIFIED_CLAIMS:
MEMORY_FACTS_USED:
MEMORY_DELTA_CANDIDATES:
BLOCKERS:
RECOMMENDED_NEXT_ACTION:
```

`PASS` 需要满足 stopping condition 与 acceptance criteria 的 evidence。Acknowledgement、计划、requested configuration 或没有实际输出的 “done” 都不是 substantive completion。
