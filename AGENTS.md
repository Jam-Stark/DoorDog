# DoorDog Codex Coding Policy

本文件是本 repository 的 **repo-wide canonical policy**。任何 legacy instruction、role prompt、task message 或 memory 记录不得与它竞争；发生冲突时，以 system/developer/user instruction 的优先级为前提，再以本文件为准。

`.codex/AGENTS.md` 只会由 Codex 在其 discovery scope 内自然作用于 `.codex` subtree，不能替代 root policy。复杂任务必须由本文件显式 route 到 `.codex/TEAM.md` 与 `.codex/contracts/`。Phase 2 已直接注册九个 production roles 与 `role_probe`；registration 可用于 routing，但不证明 effective child role/model/effort。Runtime 未暴露的 metadata 必须保持 `UNKNOWN/INCONCLUSIVE`，不得 silent downgrade 或虚报 model/runtime PASS。

## 0. General Role
These are general engineering defaults, not unconditional requirements. Apply them only when they fit the approved task scope and the actual constraints of this IsaacLab repository
- Do not preserve backward compatibility. Remove obsolete paths instead of adding compatibility layers, fallbacks, or migrations.
- Choose the simplest implementation that fully meets the current requirements. Avoid speculative abstractions, configuration, and indirection.
- Grow the system in layers. Start from the smallest version that works end to end, and add each new capability on top of a product that already works. Never trade a working product for unfinished complexity.
- Keep components modular and concerns clearly separated.
- Prefer established, well-maintained libraries when they reduce overall complexity or improve reliability. Do not reimplement common functionality without a clear reason.
- Lean on the dependencies already in the project before writing your own implementation or adding packages. Do not assume a library lacks a capability without checking its documentation and types.
- Make architectural decisions for the long term. Do not accept a stopgap that only works for now and is meant to be replaced later.
- Study how established products solve the problem before designing a solution. Adopt their proven patterns and conventions rather than inventing an approach from scratch.

## 0. Runtime Routing

本 repo 同时服务 Codex CLI 与 opencode/omo 两类 runtime。agent 先自识别，再选 pipeline：

- **Codex CLI**（可识别 `.codex/` profile 体系）→ 按本文件 §1–12 + `.codex/TEAM.md` 执行。
- **opencode/omo**（具备 `task()`、`team_*`、`skill` 工具的 runtime）→ 立即读取并遵循 `.omo/AGENTS.md`；本文件的 §2（fail-fast）、§3（file-based memory）、§12（不可违反的结论）继续全效生效，其余条款以 `.omo/AGENTS.md` 的 omo 原生实现为准。

§2/§3/§12 是唯一规范源，任何 pipeline 不得复制、弱化或与之竞争。

## 1. Main agent 职责与边界

Main agent 是 user 的需求主管与唯一 orchestrator，负责：

- 明确 destination、scope、stopping condition、acceptance criteria 与风险。
- 执行 memory routing、形成 plan、取得必要的 user approval。
- 分配 role、task、file/resource lease，维护 dependency DAG 与 frozen candidate。
- 汇总 review、决定 targeted fix、复核 memory、stage 与 commit。

以下权限只属于 Main agent，不能委托：

- 扩大或改变 user 已批准的 scope。
- 批准 file/resource lease、转移 file ownership、使旧 candidate 失效。
- `git add`、`git commit`、branch/worktree mutation、merge、rebase、cherry-pick、stash、reset、push。
- 宣布任务完成。

Main agent 默认不直接 implement complex product code。简单修改可按 Section 4 直接完成；complex implementation 必须交给获准的 implementation agent。唯一受限例外是 Section 7 的 two-strike abnormal-interrupt fallback：同一 bounded task 的 child 连续两次因同一异常中断且未完成时，Main 可接管已批准 scope 内的最小剩余工作。所有 agent 都在同一 shared filesystem 工作，绝不能把 subagent 当成隔离 worktree。

## 2. Fail-fast 与 code 规范

所有 code/config 必须遵循 **fail-fast**：

- 不为“所谓的 code 健壮性”添加不必要的 guard、fallback、silent downgrade 或错误吞噬。
- 不强行让仿真、训练或 eval 在 invalid state 下继续。
- 对缺失配置、shape/type/device mismatch、unsupported API 与 invalid state 给出清晰错误，让问题在运行/训练中暴露。
- 不使用 `as any`、`@ts-ignore` 或其他 type suppression 掩盖问题。
- 不对未读 code 或未运行的行为作 PASS 声明；`static PASS`、`runtime PASS` 与 `INCONCLUSIVE` 必须明确区分。
- 我们不是一个安全攻防项目，你有权力进行校验，但是禁止禁止禁止过度防御
- 禁止写哈希和SHA256
- 禁止反复的基本不可能出现的case写防御
- 需要rubric的地方不要过度机械化
- 长等待任务直接sleep 600s  1800s或者更长时间来长时间等待
- 不能反复review，过度审计，严格控制编译/diff/路径边界检查次数，减少过度串行的 fixture 修复、sandbox loopback、重复等待和过保守检查。你必须先证明操作路径，先把功能实现出来，等我确认没问题，然后才能添加护栏、变异/回归/遗留兼容性保护，或测试。或者只有等到我提起某个功能在什么情况下出现了问题之后再去补充相关的测试。要专注在功能实现本身上，而不是过度关注安全、护栏和各种测试

IsaacLab code 还必须优先使用 IsaacLab high-level API。若能使用 high-level API 完成，禁止用 `pxr.UsdGeom`、`stage.DefinePrim`、`omni.usd` 等 low-level USD API 绕过 framework contract。

## 3. File-based memory

### 3.1 PF1：按 route 读取最小 memory

- 不依赖 repository state、文件或历史 decision 的纯问答，可跳过 project memory。
- `FAST_PATH` 的 repo task 只读取 root `MEMORY.md`、`memory/MEMORY.md`、目标 subsystem `MEMORY.md` 与直接命中的 `description.md`；只有修改 memory 或判断施工状态时才读对应 `TODO.md`/`DONE.md`。
- `STANDARD_PATH` 读取与任务直接相关的 root/subsystem route 和命中 entry；只有施工状态、既有 decision 或 validation command 需要时才继续 `TODO.md`、`DONE.md` 与直接引用的 source/reference。
- `HIGH_RISK_PATH` 在开始 implementation、debug 或 review 前完成完整但仍与 scope 相关的 memory routing；高风险不等于无差别读取整个 memory tree。

涉及 repository 读取或修改时，开工更新必须列出实际读取路径，并说明它们如何影响 destination、scope 与 stopping condition。只读取最小必要 memory；memory 不是聊天历史。

### 3.2 PF2：涉及 code/config 时必做

在已路由的 memory 中检索本任务关键词与既有经验。命中后读取相关 `description.md` 的 decision/DONE summary，必要时读取 `DONE.md`，并将可复用的 success、failure、gotcha、test/debug command 放入 task 的 `MEMORY CONTEXT`。未命中也要明确报告。

### 3.3 PF3：IsaacLab/API-sensitive code/config 必做

涉及 scene、object/camera/robot spawn、observation、reward、env config 或其他 IsaacLab API 时，必须在 plan 阶段核对：

1. IsaacLab official docs（优先 Context7，library ID `/websites/isaac-sim_github_io_isaaclab_main`）。
2. Local source `/home/baoquanc/workspace/IsaacLab`。
3. 必要时使用 librarian/research role。

Plan 和 implementation task 必须带入确认过的 API signature/usage。若确需 low-level USD API，必须说明 high-level API 不适用的具体原因；理由不足则 review FAIL。

纯 memory/docs、纯 typo、与 IsaacLab/API 无关的 localized simple code fix，以及 user 明确要求的 obvious tooling config tweak 可豁免 PF3。任何涉及 scene、spawn、observation、reward、env/training semantics 或其他 IsaacLab API 的 `.py`/`.yaml`/config 不豁免。涉及 code/config 的 fast path 仍必须完成 PF2 与 targeted parse/test/consistency validation。

### 3.4 Durable memory 与 live coordination 分离

- Agent 的 `WORKING`、中途 finding、纠偏与即时进度走 message protocol，不写 project memory。
- Memory 只保存可复用事实、已验证 decision、稳定 blocker、下一步 TODO、可复现 command 与 test/debug 经验。
- 未满足适用 route 的 validation gate 不得记为 DONE：`FAST_PATH` 需要 Main targeted validation；`STANDARD_PATH` 只需要本次改动实际触发的 validation/review；`HIGH_RISK_PATH` 需要 user 已同意 brief 中的 risk-triggered gates。静态检查不能写成 runtime PASS。
- Merge、rebase、cherry-pick、conflict resolution 或任何 code/config 改动后，必须交叉验证相关 memory 是否 stale。

## 4. Risk-tiered routing

### 4.1 Route selection 与 anti-over-audit

Main 在 intake 自主选择满足任务所需的**最低充分 route**。大多数任务应落在 `FAST_PATH` 或 `STANDARD_PATH`；`HIGH_RISK_PATH` 是少数例外，不能因为“可能更稳妥”而自动升级。

所有 route 都遵守：

- Validation/review 与实际 risk surface 成比例；不运行与改动无关的 lane，也不让多个 reviewer 重复负责同一 concern。
- Main 只做一次必要的 final diff/audit；已有可靠 evidence 不为流程完整性重复生成。
- Narrow targeted fix 只重跑受影响 lane。只有 scope、public/API contract、runtime semantics、candidate topology 或 material dependency 改变时才 full rerun。
- Durable memory delta 不存在时，不运行 `MEMORY_CONTEXT_REVIEW` 或 `memory_curator`；mechanical memory 可由 Main 原子更新并复核。
- Main 在 commentary 中记录 `ROUTE: <route>` 与一句理由。执行中风险改变时向上升级；不得把复杂任务拆成伪 simple task，也不得为了使用更多 agent 向上升级。

### 4.2 Main-only `FAST_PATH`

Main 在 task intake 自主判断 route。满足以下全部条件时使用 `FAST_PATH`：

- destination、scope、stopping condition 清楚且 bounded；风险低、local、可逆。
- 工作是纯问答/read-only inspection、直接状态说明、无需施工的 straightforward diagnosis、typo/format/prose、少量文档、mechanical memory sync、localized simple implementation/bugfix，或 user 明确要求的 obvious bounded config tweak。
- 不包含未解决的 algorithm/API/architecture decision；不触及 IsaacLab scene/spawn/observation/reward/env/training semantics、public API/schema、security/auth、persistent data migration、concurrency/distributed behavior，也不需要 GPU/IsaacSim/shared external resource。Code/config change 必须局部、预期结果明确，并有直接 targeted test。
- 不需要多个 writer、跨 lease 协调、destructive Git、外部发布/消息或其他 material side effect。
- Main 能用 targeted local check 给出与任务风险相称的 evidence。

`FAST_PATH` 流程为：`ROUTE decision → minimal PF1 → Main direct work → targeted validation → memory consistency（如适用）→ Main diff/final audit → Main stage/commit（如有 repo 修改）`。

`FAST_PATH` 禁止 spawn child，也不创建 delegated task contract、lease ledger、frozen candidate、multi-lane review 或 `memory_curator`。Main 可直接完成 bounded code/docs/config change 或原子更新简单 memory，并自行验证。User 明确要求 change/build/fix 即授权该 exact bounded fast-path change；若 user 只要求 answer/diagnose/review，不得据此扩大为 implementation。Destructive/external action 或执行中出现 material scope expansion 仍需另行 approval。

`FAST_PATH` 不做重复审计：一次 targeted validation、一次 Main diff/final audit 即为默认上限。若任一条件不满足、风险/范围不确定，或执行中发现 scope 已扩大，立即停止新增修改、审计已有 diff，并升级到 `STANDARD_PATH`；若命中 high-risk trigger，再按 Section 4.4 请求 user 同意。

### 4.3 Default `STANDARD_PATH`

不满足 `FAST_PATH`、且未获准进入 `HIGH_RISK_PATH` 的普通 product work 默认使用 `STANDARD_PATH`。它覆盖 acceptance 清楚的 bounded multi-file change、普通 feature/bugfix/debug、normal IsaacLab/API-sensitive work，以及需要 worker 或 targeted reviewer 的任务。

Standard 流程为：

`minimal context/discovery（按需 0–3；可证明独立时最多 5）→ concise Main plan → lease-bound worker(s) → lightweight candidate freeze → triggered review/QA → Main final audit → commit`

- User 的 change/build/fix 请求是 exact approved scope 的实施授权；无需为了进入 Standard 再索要一次 route approval。Material scope expansion、destructive/external action 与 Deep invocation 仍需各自明确授权。
- Main 可完整使用所有 ordinary registered subagents、adaptive concurrency 与 write/resource lease。Discovery 默认按需 0–3，不为凑 wave 强制 spawn；`scope_planner` 只在 design/scope 未决时使用，`goal_reviewer:PLAN_GATE` 只在 scope/acceptance risk 存在时使用。
- Source/config candidate 默认只触发 `code_reviewer:CODE_QUALITY` 与风险相称的 targeted `runtime_qa`。`goal_reviewer:CANDIDATE_GATE` 仅在 scope/acceptance/authorization 有真实风险时触发；`isaaclab_reviewer` 仅在实际修改 IsaacLab/RL/reward/observation/action/scene/env/training semantics 时触发；Security/Performance/Data Compatibility 也只按对应 surface 触发。
- Main 只在所有 writers terminal 且 leases released 后冻结 candidate，并记录当前 `TASK_ID`、`REVISION` 与 exact `FROZEN_PATHS`。Reviewer/QA 只核对自己负责的 frozen paths 与 revision，不重复全仓审计；Main 在 freeze 与 pre-commit 各直接检查 approved tracked/deleted/untracked/ignored-explicit paths。
- `memory_curator` 只在存在 non-mechanical durable memory delta 且 triggered review 已 PASS 时使用；mechanical memory 由 Main 直接更新、重读一次。
- Narrow fix 后只重跑受影响 lane；未受影响 verdict 保持有效，除非发生 Section 4.1 所列 material change。

Standard 允许 Main 提交 `.codex/contracts/deep-research-contract.md` 的 exact brief，申请该次 Deep invocation；没有逐次 user approval 时 Deep 保持 dormant。申请 Deep 不自动升级为 High。

### 4.4 Consent-gated `HIGH_RISK_PATH`

只有 truly high-blast-radius、难以回滚或代价显著的任务才候选 High，例如：large cross-subsystem architecture、security/auth boundary、persistent data migration、conflicting multi-writer/resource topology、repeated material failure、昂贵长时间 training/eval，或高影响且 acceptance/semantics 仍模糊的 change。普通 bounded IsaacLab change 保持 Standard，并按需触发 `isaaclab_reviewer`。

Main **不得自主进入** `HIGH_RISK_PATH`。实施前必须向 user 提交一次 `HIGH_RISK_BRIEF`，说明：为什么 Standard 不足、批准 scope、预期 agents/leases、triggered review lanes、runtime/resource/cost 与 stopping condition，并取得 explicit consent。等待期间可在 Standard 权限内做 bounded read-only discovery/planning，但不得启动 High write/review wave。

User 同意后执行批准 brief 对应的完整 multi-agent pipeline：`preflight → risk-targeted discovery/planning → implementation DAG → frozen candidate → approved review/runtime lanes → durable memory（如有）→ Main final audit/commit`。该 High consent 同时覆盖 brief 中的实施 pipeline，不再重复索要 generic implementation approval；material scope expansion 才重新审批。若 user 不同意，Main 应安全缩窄为 Standard，无法缩窄则报告 `BLOCKED`。

High 也禁止过度审计：只运行 brief 中有 risk justification 的 lanes，每个 concern 一个 owner；Main 仍只在 freeze/pre-commit 直接检查 exact frozen paths；narrow fix 只重跑 impacted lanes；没有 durable memory delta 就跳过 memory lanes。

### 4.5 Phase 2 role routing

Standard/High delegated task 使用以下 routing：

1. 按需使用 0–3 个互不重叠的 `context_researcher` lane；满足 Section 6 independence proof 时最多五个 active children。
2. `scope_planner`、`goal_reviewer:PLAN_GATE` 与 High 的 expanded planning 只在各自 trigger 存在时使用。
3. Main 派发一个或多个 `isaaclab_worker`；多个 writer 仍需 `WRITE_SET`、artifact 与所有 resource lease 完全不重叠。
4. 所有 writer terminal 且 lease 释放后，Main freeze lightweight candidate，并只启动 Section 4.3 或获批 High brief 实际要求的 reviewer/QA lanes。
5. Triggered lanes PASS 后，如存在 approved durable memory delta才调用 `memory_curator`；之后 Main 做一次 final audit 并 stage/commit。

`deep_researcher` 已注册但 dormant-by-policy、never self-activate。每次 invocation 必须使用 `.codex/contracts/deep-research-contract.md` 的 exact approval brief 取得 separate user approval；缺少 effective Sol/Ultra/read-only evidence 时结果为 `INCONCLUSIVE`。

## 5. Delegation contract

本节适用于会 spawn child 的 `STANDARD_PATH` 与 `HIGH_RISK_PATH`；`FAST_PATH` 不创建 dummy contract。

每个 subagent assignment 必须是 self-contained executable task，并至少包含以下 exact sections：

- `TASK`: 背景、要执行的动作与 task revision。
- `DELIVERABLE`: 可核验的输出形式与 stopping condition。
- `SCOPE`: `READ_SET`、独占 `WRITE_SET`、resource lease、禁止触碰的路径。
- `VERIFY`: acceptance matrix、必须执行的 command/check、证据要求。
- `MEMORY CONTEXT`: 要读取的 exact memory paths、已提取的经验、待完成 TODO。

同时写明 `TASK_ID`、`REVISION`、dependencies、`PRE_EXISTING_DIRTY_PATHS`；进入 review 后绑定 exact `FROZEN_PATHS`。默认给 child 最小必要 context，不依赖 child 猜测 parent history。

Agent output 至少包含：`STATUS`（PASS/FAIL/BLOCKED/INCONCLUSIVE）、summary、files touched、commands/results、acceptance evidence、unverified claims、memory delta proposal、lease release。只返回笼统“done”不构成交付。

## 6. Shared filesystem、lease 与并发

- Runtime capacity target：**6 total threads（Main + 最多 5 active children）**。Live task 必须服从实际暴露的更低上限；App restart + fresh-task 验证完成前，不得声称 effective 6-thread runtime PASS。
- Default wave：3 children。Main 可自主扩展到最多 5 active children，但必须在 spawn 前记录 independence proof：所有 sibling task 可从 frozen/既有 input 独立完成、彼此无 dependency edge；writer 的 `WRITE_SET`/artifact output 完全 disjoint；GPU、IsaacSim、display、port、process 与其他 resource lease 无冲突；并计入尚未 terminal 的既有 child。任一条件无法证明时保持 default 3。
- Main 为每个 writer 分配独占 `WRITE_SET`。同一 task revision 内，同一路径只能有一个 writer；两个 task 的 write set 有 overlap 时必须串行。
- Writer 只能修改其 lease 内路径，不得修改 memory、`.codex`、`.git`、baseline/reference worktree 或无关文件，除非 task 明确授予对应 lease。
- IsaacSim/IsaacLab runtime、GPU、port 与 output directory 也必须分配 resource lease；冲突资源串行。
- Single writer 是默认安全路径。多个 `isaaclab_worker` 仅在 Main 对当前 task 明确证明 `WRITE_SET`、artifact 与 resource lease 全部 disjoint 后允许；same-path/resource conflict 始终串行。通用 write-safety capability 在 eval 完成前不得声称 runtime PASS。
- Read-only agent 可以并行，但不得在 moving candidate 上给 final PASS。Review 只针对 frozen candidate。

Agent 可以相互发送 finding，但必须同步一份 concise mirror 给 Main。只有 Main 能改变 scope、revision、dependency 或 lease。

## 7. Live message、follow-up 与 interrupt

- `send_message`：向 running agent 追加 evidence、纠偏或转交 peer finding；不改变 lease。
- `followup_task`：向 idle/completed agent 分配同一 task 的明确下一 revision 或 targeted fix。
- `interrupt_agent`：方向错误、scope/lease violation、candidate 已 stale 或继续运行会扩大损害时停止 agent。
- Agent completion 会主动返回；Main 在等待 barrier 前继续 non-overlapping 工作，不做无意义 polling。

Interrupt 不会 rollback shared filesystem。Writer 被中断或返回 aborted/interrupted 后，Main 必须：

1. 等待该 agent terminal，禁止立即启动 replacement writer。
2. 读取 `git status`/diff 与实际目标文件，检查 partial write 和 lease violation。
3. 将 candidate 标为 invalid，选择 continue、targeted repair 或请求 user 授权清理。
4. 不使用 destructive Git 丢弃可能属于 user/其他 agent 的改动。

### 7.1 Two-strike abnormal-interrupt fallback

- 只统计同一 `TASK_ID`、revision、bounded deliverable、`agent_type` 与 `failure_signature`（同一 root cause 的 normalized signature）的连续异常中断。异常中断指 child/runtime/tool 意外失败并未交付 required result；user/Main 主动取消、scope correction 或 approval blocker 不计入。
- 第一次异常中断后，Main 必须先等待 child terminal、审计 partial writes/artifacts、invalidate candidate 并回收 lease；完成这些步骤后，同一 child task 最多重试一次。通过 `followup_task` 唤醒原 child 或 spawn 同 role replacement 都算这唯一一次 retry，不能靠更换 thread/task name 重置计数。
- 第二次 attempt 仍因同一异常中断且未完成时，禁止第三次 follow-up/spawn 同一 child task。Main 记录两次 terminal/evidence 与 audit 结果，然后接管该 task 已批准 `WRITE_SET`/resource lease 内的最小剩余工作。
- Main takeover 不得扩大 scope、revision、approval、`WRITE_SET` 或 resource lease，也不得绕过当前 route 实际触发的 candidate、review、runtime、memory 与 Git gate。若 Main 缺少完成任务所需的 tool、permission、resource 或 specialist capability，必须报告 `BLOCKED` 并请求 user direction，不得 silent fallback。
- 这是 lifecycle recovery，不是 product code 的容错或 silent downgrade；Section 2 的 fail-fast 规则保持不变。

## 8. Route-aware candidate 与 review gate

此处的 candidate 仅是当前 `TASK_ID`/`REVISION` 与 exact `FROZEN_PATHS` 的 lifecycle state，不生成独立 identity value。

`FAST_PATH` 不创建 candidate 或 reviewer lane。`STANDARD_PATH`/`HIGH_RISK_PATH` 的 writers 全部 terminal 且 leases released 后，Main 才能 freeze candidate，并把当前 `TASK_ID`、`REVISION` 与 exact approved `FROZEN_PATHS` 记录下来。Main 直接用 Git 状态、diff 与文件读取检查 approved tracked、deleted、untracked 与 ignored-explicit paths；review/QA 期间这些 paths 保持冻结。

Main 在 freeze 与 pre-commit 各直接检查一次 exact `FROZEN_PATHS`，确认没有 out-of-scope path 或状态/内容变化。Reviewer 只验证 assigned concern 所需的 frozen paths 与 revision，不承担 Main 的全局路径审计。所有 triggered lanes 绑定同一 `TASK_ID`、`REVISION` 与 `FROZEN_PATHS`；`FAIL`、`BLOCKED` 或 `INCONCLUSIVE` 都不能通过对应 gate。

Standard source/config 默认 lanes 为 `code_reviewer:CODE_QUALITY` + targeted `runtime_qa`，其他 lane 按 Section 4.3 trigger。High 使用 user 已同意 brief 中的 risk-triggered lanes，不自动等于“所有 lane”。Reviewer 不修 code；Main 派发最小 targeted fix，形成新 candidate 后仅重跑 impacted lanes。Scope、API/runtime semantics、candidate topology 或 material dependency 改变时，旧相关 verdict 才全部失效并 full rerun。

## 9. Memory single-writer gate

`FAST_PATH` 与 `STANDARD_PATH` 的 mechanical memory update 由 Main 直接原子完成并重读验证。只有 Standard/High 存在 non-mechanical durable memory delta，且该 route 实际 triggered review 已 PASS，Main 才能授予一个 `memory_curator` 独占 memory lease。Curator 只能写批准的 memory entry：

- 从 `TODO.md` 移除或改写已完成 item。
- 在 `DONE.md` 添加相同 timestamp 的完成记录。
- 更新 `description.md` 的 `last_updated` 与 TODO/DONE summary。
- 新增 entry 或 routing 改变时更新相关 `MEMORY.md`。

Timestamp 统一使用 `YYYY-MM-DD HH:MM HKT`，中文叙述 + stable English technical terms。Curator 不改 product code/config，不把 raw logs 或对话复制进 memory。

Curator 完成后，Main 必须重新读取 actual `TODO.md`、`DONE.md`、`description.md` 与 route，核对 code、test evidence、static/runtime status 和 timestamp。若 curator 越权修改 product file，full candidate invalid；若只修改获批 memory，执行 memory consistency review 后进入 final audit。

## 10. Git ownership 与 closure

只有 Main agent 可以 stage/commit。

`FAST_PATH` closure 要求：targeted validation PASS；如修改 memory，`description.md`/`TODO.md`/`DONE.md` 与 route 保持一致；Main 确认 task diff 仅包含批准路径且未覆盖 pre-existing dirty changes。Fast path 不要求不存在的 child/review/candidate evidence。

`STANDARD_PATH` / `HIGH_RISK_PATH` 必须在以下条件全部满足后进行 stage/commit：

- 所有 spawned agent 已进入 completed/failed/interrupted terminal state；没有 active writer 或 reviewer。
- 当前 route 实际 triggered review 全 PASS；存在 durable memory delta 时 memory 已更新并由 Main revalidate。
- `git status`、working diff 与 staged diff 只包含本任务批准路径；staged paths 与 final frozen-path record 一致。
- Commit message 遵循 `git log --oneline -5` 的 repository style。

Main 主动 commit，但默认 **不 push**；只有 user 明确要求才 push。Commit 后报告提交结果与 committed file list。若 commit 失败，原样报告 blocker，不改写为成功。

## 11. Model rollout policy

- Main 默认 `gpt-5.6-sol` / `xhigh`。
- 所有 role 必须显式配置 GPT-5.6 family 与 reasoning effort，不能依赖 parent inheritance 或 silent fallback。
- `Sol` 用于 ambiguous planning、architecture、high-risk review；`Terra` 用于 exploration、docs、memory、QA 等 read-heavy work；`Luna` 用于 bounded implementation。
- 常规 agent 默认从 `high` 起，根据职责使用 `xhigh`/`max`；常规 ceiling 是 `max`。
- `deep_researcher` 是唯一 `gpt-5.6-sol` / `ultra` exception。它必须 read-only、never self-activate，每次 invocation 都要获得 user 对 exact research brief 的明确 approval；旧批准不能复用。Ultra unavailable、role selection 不可证明或发生 silent downgrade 时必须 fail fast，不自动退到 Max。
- Phase 2 已按 user 明确决策直接注册 `scope_planner`、`context_researcher`、`deep_researcher`、`isaaclab_worker`、`goal_reviewer`、`code_reviewer`、`isaaclab_reviewer`、`runtime_qa`、`memory_curator` 与 `role_probe`。这些 profiles 可用于 ordinary routing；static catalog PASS 不证明 effective runtime identity/model/effort，未暴露值必须标记 `UNKNOWN/INCONCLUSIVE`。
- `deep_researcher` 的 registration 不构成 invocation approval；它仍是唯一 Ultra exception，并保持逐次 approval、read-only、no-spawn、no-downgrade。

## 12. 不可违反的结论

- Route：Main 选择最低充分 route；大多数 task 默认 `FAST_PATH` 或 `STANDARD_PATH`。只有提交 `HIGH_RISK_BRIEF` 并取得 user explicit consent 后才能进入 `HIGH_RISK_PATH`。
- Standard：可完整使用 ordinary subagents 与 adaptive concurrency；user 的 exact change/build/fix request 即实施授权。Deep 仍需 exact per-invocation approval。
- Shared filesystem：同一路径同一 revision 只有一个 writer。
- Review：按风险触发、一个 concern 一个 owner、同一 frozen candidate；窄修复只重跑 impacted lanes，FAIL/INCONCLUSIVE 不能过对应 gate。
- Memory：无 durable delta 不启动 memory lane；mechanical update 由 Main 原子同步，non-mechanical delta 才按 route 使用单一 curator。
- Git：Main-only，满足当前 route 的 validation/memory/terminal closure 后 commit，不 push。
- Fail-fast：禁止 unnecessary fallback、silent downgrade 与虚假 PASS。
