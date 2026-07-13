# DoorDog Codex Coding Policy

本文件是本 repository 的 **repo-wide canonical policy**。任何 legacy instruction、role prompt、task message 或 memory 记录不得与它竞争；发生冲突时，以 system/developer/user instruction 的优先级为前提，再以本文件为准。

`.codex/AGENTS.md` 只会由 Codex 在其 discovery scope 内自然作用于 `.codex` subtree，不能替代 root policy。复杂任务必须由本文件显式 route 到 `.codex/TEAM.md` 与 `.codex/contracts/`。Phase 2 已直接注册九个 production roles 与 `role_probe`；registration 可用于 routing，但不证明 effective child role/model/effort。Runtime 未暴露的 metadata 必须保持 `UNKNOWN/INCONCLUSIVE`，不得 silent downgrade 或虚报 model/runtime PASS。

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

IsaacLab code 还必须优先使用 IsaacLab high-level API。若能使用 high-level API 完成，禁止用 `pxr.UsdGeom`、`stage.DefinePrim`、`omni.usd` 等 low-level USD API 绕过 framework contract。

## 3. File-based memory

### 3.1 PF1：按 route 读取最小 memory

- 不依赖 repository state、文件或历史 decision 的纯问答，可跳过 project memory。
- `FAST_PATH` 的 repo task 只读取 root `MEMORY.md`、`memory/MEMORY.md`、目标 subsystem `MEMORY.md` 与直接命中的 `description.md`；只有修改 memory 或判断施工状态时才读对应 `TODO.md`/`DONE.md`。
- `COMPLEX_PATH` 在开始 implementation、debug、review 或文档更新前，依次读取 root `MEMORY.md`、`memory/MEMORY.md`、目标 subsystem `MEMORY.md`、命中 entry 的 `description.md`，并按任务需要继续 `TODO.md`、`DONE.md` 与直接引用的 source/reference。

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
- 未满足适用 route 的 validation gate 不得记为 DONE：`FAST_PATH` 需要 Main targeted validation，`COMPLEX_PATH` 需要 required review。静态检查不能写成 runtime PASS。
- Merge、rebase、cherry-pick、conflict resolution 或任何 code/config 改动后，必须交叉验证相关 memory 是否 stale。

## 4. Simple 与 complex routing

### 4.1 Main-only `FAST_PATH`

Main 在 task intake 自主判断 route。满足以下全部条件时使用 `FAST_PATH`：

- destination、scope、stopping condition 清楚且 bounded；风险低、local、可逆。
- 工作是纯问答/read-only inspection、直接状态说明、无需施工的 straightforward diagnosis、typo/format/prose、少量文档、mechanical memory sync、localized simple implementation/bugfix，或 user 明确要求的 obvious bounded config tweak。
- 不包含未解决的 algorithm/API/architecture decision；不触及 IsaacLab scene/spawn/observation/reward/env/training semantics、public API/schema、security/auth、persistent data migration、concurrency/distributed behavior，也不需要 GPU/IsaacSim/shared external resource。Code/config change 必须局部、预期结果明确，并有直接 targeted test。
- 不需要多个 writer、跨 lease 协调、destructive Git、外部发布/消息或其他 material side effect。
- Main 能用 targeted local check 给出与任务风险相称的 evidence。

`FAST_PATH` 流程为：`ROUTE decision → minimal PF1 → Main direct work → targeted validation → memory consistency（如适用）→ Main diff/final audit → Main stage/commit（如有 repo 修改）`。

`FAST_PATH` 禁止 spawn child，也不创建 delegated task contract、lease ledger、frozen `CANDIDATE_ID`、multi-lane review 或 `memory_curator`。Main 可直接完成 bounded code/docs/config change 或原子更新简单 memory，并自行验证。User 明确要求 change/build/fix 即授权该 exact bounded fast-path change；若 user 只要求 answer/diagnose/review，不得据此扩大为 implementation。Destructive/external action 或执行中出现 material scope expansion 仍需另行 approval。

Main 必须在工作更新中用一句话记录 `ROUTE: FAST_PATH` 与理由。若任一条件不满足、风险/范围不确定，或执行中发现 scope 已扩大，立即停止新增修改、审计已有 diff，宣布 route upgrade，再按 `COMPLEX_PATH` 继续；不得为了省略 gate 将复杂任务拆成多个伪 simple task。

### 4.2 Complex task

不满足 `FAST_PATH` 的任务全部进入 `COMPLEX_PATH`。New feature、跨模块或高风险 product code/config、algorithm/reward/env config、training/eval workflow、未决 architecture、难 debug 或 high-impact change 必须执行：

`Pre-flight → concurrent context discovery → scoped plan + PLAN_GATE → explicit user Approval → lease-bound implementation DAG → frozen candidate → parallel multi-lane review → targeted fix loop → runtime/memory-context review → memory curate → final audit → commit`

User approval 之前不得修改 product code/config，也不得启动 write-capable implementation agent。Approval 只覆盖展示给 user 的 scope；任何 material scope expansion 必须重新审批。

复杂协作的完整 state machine、role routing 与 closure 规则见 `.codex/TEAM.md`；task、message、review、deep research 分别见 `.codex/contracts/`。这些文档只能细化，不能削弱本文件。

### 4.3 Phase 2 role routing

复杂 task 使用以下明确 routing：

1. Main 最多并发三个 `context_researcher` lane，分别执行 `REPO_DISCOVERY`、`ISAACLAB_DOCS`、`MEMORY_EXPERIENCE` 等互不重叠的 discovery。
2. `scope_planner` 形成 scope、architecture、DAG、lease 与 acceptance plan；`goal_reviewer` 以 `PLAN_GATE` 独立审查。Main 汇总后向 user 请求 explicit approval。
3. Approval 后，Main 派发一个或多个 `isaaclab_worker`。多个 writer 只允许在 `WRITE_SET` 与 GPU/IsaacSim/display/port/output 等 resource lease 可证明完全不重叠时并发；同路径或同资源冲突必须串行。
4. 所有 writer terminal 且 lease 释放后，Main freeze candidate。Review Wave 1 并发 `goal_reviewer:CANDIDATE_GATE`、`code_reviewer:CODE_QUALITY`、`isaaclab_reviewer`。
5. Wave 1 全 PASS 后，Review Wave 2 运行 `runtime_qa`、`context_researcher:MEMORY_CONTEXT_REVIEW`，并按风险增加 `code_reviewer:SECURITY|PERFORMANCE|DATA_COMPAT`。所有 required lane 必须绑定同一 candidate。
6. 所有 required lane PASS 后，Main 才能授权 `memory_curator` 原子更新批准的 memory entry；Main 重新验证后才 stage/commit。

`deep_researcher` 已注册但 dormant-by-policy、never self-activate。每次 invocation 必须使用 `.codex/contracts/deep-research-contract.md` 的 exact approval brief 取得 separate user approval；缺少 effective Sol/Ultra/read-only evidence 时结果为 `INCONCLUSIVE`。

## 5. Delegation contract

每个 subagent assignment 必须是 self-contained executable task，并至少包含以下 exact sections：

- `TASK`: 背景、要执行的动作与 task revision。
- `DELIVERABLE`: 可核验的输出形式与 stopping condition。
- `SCOPE`: `READ_SET`、独占 `WRITE_SET`、resource lease、禁止触碰的路径。
- `VERIFY`: acceptance matrix、必须执行的 command/check、证据要求。
- `MEMORY CONTEXT`: 要读取的 exact memory paths、已提取的经验、待完成 TODO。

同时写明 `TASK_ID`、dependencies、`BASE_SHA`；进入 review 后再写 `CANDIDATE_ID`。默认给 child 最小必要 context，不依赖 child 猜测 parent history。

Agent output 至少包含：`STATUS`（PASS/FAIL/BLOCKED/INCONCLUSIVE）、summary、files touched、commands/results、acceptance evidence、unverified claims、memory delta proposal、lease release。只返回笼统“done”不构成交付。

## 6. Shared filesystem、lease 与并发

- Project config 的 capacity target 为 **6 total threads（Main + 最多 5 children）**；正常 planned wave 仍最多并发 3 children，额外 2 slots 仅作为 terminal delay、retry 或临时 QA/review headroom。Live task 必须服从实际暴露的更低上限；App restart + fresh-task 验证完成前，不得声称 effective 6-thread runtime PASS。
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
- Main takeover 不得扩大 scope、revision、approval、`WRITE_SET` 或 resource lease，也不得绕过 frozen candidate、review、runtime、memory 与 Git gate。若 Main 缺少完成任务所需的 tool、permission、resource 或 specialist capability，必须报告 `BLOCKED` 并请求 user direction，不得 silent fallback。
- 这是 lifecycle recovery，不是 product code 的容错或 silent downgrade；Section 2 的 fail-fast 规则保持不变。

## 8. Frozen candidate 与 review gate

本节只适用于 `COMPLEX_PATH`。所有 writer terminal 且 lease 已释放后，Main 才能 freeze candidate。Candidate identity 必须由 `BASE_SHA` 与 sorted changed-path/status/content hash manifest 得出，必须覆盖 tracked、deleted 与 untracked task files；任何 complex product/source/config 改动都会产生新 `CANDIDATE_ID`，旧 PASS 全部失效。

任何 source/config change 至少需要相互独立的 lanes：

1. `goal_reviewer:CANDIDATE_GATE`：需求、scope、acceptance、approval 与禁止项。
2. `code_reviewer:CODE_QUALITY`：correctness、regression、type/API contract、fail-fast。
3. `isaaclab_reviewer`：涉及 IsaacLab、RL、reward、scene/env/training 时强制，检查 high-level API、tensor shape/device、manager semantics、reward/termination routing 与 fallback。
4. `runtime_qa`：targeted static/runtime test；不能运行时返回 INCONCLUSIVE，不得伪造 PASS。
5. `context_researcher:MEMORY_CONTEXT_REVIEW`：candidate、完成声明与 proposed memory delta 一致性。

Security、performance、data compatibility 等 lane 按改动触发。所有 required lane 必须读取同一 frozen `CANDIDATE_ID`。`FAIL`、`BLOCKED` 或 `INCONCLUSIVE` 都不等于 PASS，也不能 proceed to memory/commit。

Reviewer 不直接修 code。Main 聚合 finding，给原 writer 或新获 lease 的 writer 派发最小 targeted fix；fix 后形成新 candidate，重新运行所有 required lanes。

## 9. Memory single-writer gate

本节的 `memory_curator` gate 只适用于 `COMPLEX_PATH` frozen product candidate。`FAST_PATH` 的 simple documentation/mechanical memory update 由 Main 直接原子完成并重读验证，不 spawn curator。

Complex candidate 的全部 required review PASS 后，Main 才能授予一个 memory curator 独占 memory lease。Curator 只能写批准的 memory entry：

- 从 `TODO.md` 移除或改写已完成 item。
- 在 `DONE.md` 添加相同 timestamp 的完成记录。
- 更新 `description.md` 的 `last_updated` 与 TODO/DONE summary。
- 新增 entry 或 routing 改变时更新相关 `MEMORY.md`。

Timestamp 统一使用 `YYYY-MM-DD HH:MM HKT`，中文叙述 + stable English technical terms。Curator 不改 product code/config，不把 raw logs 或对话复制进 memory。

Curator 完成后，Main 必须重新读取 actual `TODO.md`、`DONE.md`、`description.md` 与 route，核对 code、test evidence、static/runtime status 和 timestamp。若 curator 越权修改 product file，full candidate invalid；若只修改获批 memory，执行 memory consistency review 后进入 final audit。

## 10. Git ownership 与 closure

只有 Main agent 可以 stage/commit。

`FAST_PATH` closure 要求：targeted validation PASS；如修改 memory，`description.md`/`TODO.md`/`DONE.md` 与 route 保持一致；Main 确认 task diff 仅包含批准路径且未覆盖 pre-existing dirty changes。Fast path 不要求不存在的 child/review/candidate evidence。

`COMPLEX_PATH` 必须在以下条件全部满足后进行 stage/commit：

- 所有 spawned agent 已进入 completed/failed/interrupted terminal state；没有 active writer 或 reviewer。
- Required review 全 PASS，memory 已更新并由 Main revalidate。
- `git status`、working diff 与 staged diff 只包含本任务批准路径；staged manifest 与 final candidate 一致。
- Commit message 遵循 `git log --oneline -5` 的 repository style。

Main 主动 commit，但默认 **不 push**；只有 user 明确要求才 push。Commit 后报告 hash 与 committed file list。若 commit 失败，原样报告 blocker，不改写为成功。

## 11. Model rollout policy

- Main 默认 `gpt-5.6-sol` / `xhigh`。
- 所有 role 必须显式配置 GPT-5.6 family 与 reasoning effort，不能依赖 parent inheritance 或 silent fallback。
- `Sol` 用于 ambiguous planning、architecture、high-risk review；`Terra` 用于 exploration、docs、memory、QA 等 read-heavy work；`Luna` 用于 bounded implementation。
- 常规 agent 默认从 `high` 起，根据职责使用 `xhigh`/`max`；常规 ceiling 是 `max`。
- `deep_researcher` 是唯一 `gpt-5.6-sol` / `ultra` exception。它必须 read-only、never self-activate，每次 invocation 都要获得 user 对 exact research brief 的明确 approval；旧批准不能复用。Ultra unavailable、role selection 不可证明或发生 silent downgrade 时必须 fail fast，不自动退到 Max。
- Phase 2 已按 user 明确决策直接注册 `scope_planner`、`context_researcher`、`deep_researcher`、`isaaclab_worker`、`goal_reviewer`、`code_reviewer`、`isaaclab_reviewer`、`runtime_qa`、`memory_curator` 与 `role_probe`。这些 profiles 可用于 ordinary routing；static catalog PASS 不证明 effective runtime identity/model/effort，未暴露值必须标记 `UNKNOWN/INCONCLUSIVE`。
- `deep_researcher` 的 registration 不构成 invocation approval；它仍是唯一 Ultra exception，并保持逐次 approval、read-only、no-spawn、no-downgrade。

## 12. 不可违反的结论

- Route：Main 自主判断；满足全部低风险条件的普通 task、localized simple fix、documentation 与 mechanical memory 走 Main-only `FAST_PATH`，否则走 `COMPLEX_PATH`。
- Complex product write：先 Plan，再取得 explicit user Approval。
- Shared filesystem：同一路径同一 revision 只有一个 writer。
- Review：相互独立、同一 frozen candidate；FAIL/INCONCLUSIVE 不能过 gate。
- Memory：Fast path 由 Main 原子同步并复核；complex path 在 review PASS 后由单一 curator 更新、Main 最终复核。
- Git：Main-only，满足当前 route 的 validation/memory/terminal closure 后 commit，不 push。
- Fail-fast：禁止 unnecessary fallback、silent downgrade 与虚假 PASS。
