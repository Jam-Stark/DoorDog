---
name: codex-agent-system-architecture
scope: repository-wide Codex multi-agent foundation and authority model
status: phase2_bounded_behavior_and_full_tree_wls_pass_general_runtime_inconclusive
last_updated: 2026-07-21 23:10 HKT
evidence_level: STATIC/STRICT PASS; BOUNDED RUNTIME BEHAVIOR PASS; FULL-TREE WRITE SAFETY PASS; GENERAL RUNTIME INCONCLUSIVE
owned_paths:
  - AGENTS.md
  - .omo/AGENTS.md
  - .codex/TEAM.md
  - .codex/contracts/
  - .codex/agents/
  - .codex/evals/
  - memory/agent-system/architecture/
---

## Purpose

记录 DoorDog Codex multi-agent foundation 的 canonical authority、shared-filesystem coordination 与 rollout boundary。

## Verified Decisions

- Root `AGENTS.md` 是 repo-wide canonical policy；`.codex/AGENTS.md` 只自然作用于 `.codex` subtree。
- `.codex/TEAM.md` 与 `.codex/contracts/` 定义 Main-only scope/route/approval/lease/Git authority、single-writer path lease，以及 route-aware candidate/review/memory gates。
- Pipeline 使用三级 route：Main-only `FAST_PATH` 处理 bounded low-risk work；`STANDARD_PATH` 是普通 product work 默认路径并可完整使用 ordinary registered subagents；`HIGH_RISK_PATH` 只在 user 明确同意 exact `HIGH_RISK_BRIEF` 后进入。绝大多数任务应停留在 Fast 或 Standard。
- 所有 route 禁止 over-audit：validation/review 按实际 risk trigger，one concern/one owner；manifest 只由 Main 在 freeze/pre-commit 完整验证；narrow fix 只重跑 impacted lanes；无 durable memory delta 不启动 memory reviewer/curator。
- Project configured capacity target 为 6 total threads（Main + 最多 5 active children）；default wave 为 3 children。Main 在证明 sibling 无 dependency、input 已固定、writer `WRITE_SET`/output 两两 disjoint、resource lease 无冲突后，可自主扩展到 5；配置 static consistency 可验证，fresh-task effective capacity 尚未 runtime 验证。
- User 明确批准绕过旧 activation blocker，Phase 2 直接注册九个 production profiles 与 `role_probe`；registration 可用于 routing，但不证明 effective child role/model/effort。
- Discovery/review default wave 为三个 children，independence-proven wave 可扩展到五个 active children；多个 `isaaclab_worker` 仍只允许 provably disjoint `WRITE_SET`/artifact 与 resource lease，overlap 必须串行。
- `deep_researcher` 已注册但 dormant-by-policy；Standard 与 approved High 都可提交 exact brief 申请调用，但每次 invocation 仍需 separate approval，High consent 不替代 Deep approval；hooks 尚未配置。
- Phase 2 R3 对九个 non-Deep role 的 bounded positive contract behavior、direct child-to-peer FINDING 与 identical Main mirror、tested child-owned snapshots、C1-C4 lease/interrupt behavior 均取得 PASS evidence；该轮因排除 externally-mutated `logs_rl/`，尚不构成 full-tree write safety PASS。
- P2-FULL-TREE-WLS-R1 在 training 结束且 full tree（包含 `logs_rl/`）稳定后验证 C1 single writer、C2 disjoint simultaneous active writers、C3 strict same-path serialization 与 C4 running partial writer → interrupted terminal → Main partial audit → replacement 全部 PASS；无 out-of-lease change，cleanup 后 HEAD/worktree/index 与 same-encoding full-tree manifest 精确恢复。该 evidence 将 general full-tree write safety 提升为 PASS，但不提升其他 runtime metadata 或 IsaacLab runtime/training 结论。
- Two-strike abnormal-interrupt fallback 已成为 Main lifecycle recovery contract：同一 bounded child task 第一次同因异常中断并完成 terminal/partial-write/lease audit 后最多重试一次；第二次仍同因中断且未交付时，不启动第三个相同 child task，由 Main 接管原批准 scope/lease 内的最小剩余工作。该 fallback 不扩大 authority、不绕过 closure gate；Main 缺少必要 capability 时返回 `BLOCKED`。
- Frozen candidate `3e9f39a30b051631b8a1133cd9453271537d01b87a6b18b7000184c48292a98c` 的 Goal/Code/IsaacLab content review 均 PASS，`runtime_qa` 仅为 `STATIC_PASS`。真正 simultaneous three-reviewer wave 因第三 lane 出现 unexplained `agent thread limit reached` 而为 INCONCLUSIVE；IsaacLab runtime/training NOT_RUN。
- 2026-07-21 23:10 HKT - 新增 dual-runtime routing：root `AGENTS.md` §0 按 runtime 自识别分流——Codex CLI 走 §1–12 + `.codex/TEAM.md`，opencode/omo 走 `.omo/AGENTS.md`；root §2/§3/§12 保持唯一规范源。`.omo/AGENTS.md` 为 omo canonical pipeline：保留 omo 目标式委托 + 自主执行者（deep/hephaestus），护栏收敛为 6 条（fail-fast、memory 门、证据纪律、多 writer WRITE_SET+lead 文件系统审计、review 节制、lead-only Git），IsaacLab 工作指引含 local source `/home/baoquanc/workspace/IsaacLab` 与 Context7（IsaacLab ID `/websites/isaac-sim_github_io_isaaclab_main`）触发，角色为触发速查表而非工位。设计依据为 base_v16 全程实测：lead 过载 ~60%、worker 自报两次失真均被 lead 审计兜住。STATIC PASS only；omo pipeline 的 runtime 行为（角色触发命中率、护栏执行、review 节制）尚未 eval，保持 NOT_RUN。

## TODO Summary

- 2026-07-11 05:11 HKT - 获取 authoritative effective role/model/effort/sandbox metadata；诊断并重测 true simultaneous three-reviewer concurrency；按 route 完成 hooks capability assessment。Deep 保持 dormant，只有 exact separate approval 后才可调用。
- 2026-07-13 15:21 HKT - 为 two-strike abnormal-interrupt → Main takeover contract 增加 targeted runtime eval；在完成前仅声明 policy/static consistency PASS，runtime behavior 保持 `NOT_RUN`。
- 2026-07-13 16:25 HKT - 在 App restart 后验证 fresh-task effective capacity 为 Main + 5 children、default 3 与 independence-proven expansion 5 的 coordination behavior，并观察代表性 `FAST_PATH` routing；在完成前只声明 static policy/config consistency PASS，runtime behavior 保持 `NOT_RUN`。
- 2026-07-13 17:23 HKT - Targeted 验证三级 route 的实际选择、Standard triggered-lane pruning/impacted-only rerun 与 High consent stop gate；在完成前只声明 policy/TOML/static consistency PASS，runtime behavior 保持 `NOT_RUN`。

## DONE Summary

- 2026-07-11 01:19 HKT - 完成 Codex-native root `AGENTS.md`、`.codex/TEAM.md`、contracts 与 Phase 0A/1 rollout boundary；static foundation review PASS，未声称 runtime activation PASS。
- 2026-07-11 02:50 HKT - 按 user 明确批准完成 Phase 2 direct registration：新增九个 production profiles、十角色 registry、parallel routing 与五组 eval contracts；candidate `571e40ab8824f00244c5da586d880f6394d8bdb2c53e3d834e75f6533713b18f` 经独立 review PASS，validation level 为 STATIC PASS + strict startup PASS，未声称 production role runtime PASS。
- 2026-07-11 04:40 HKT - Phase 2 R3 验证九个 non-Deep role 的 bounded positive contract behavior、direct peer FINDING/Main mirror、tested child snapshots 与 C1-C4 write-lease/interrupt behavior PASS；candidate `3e9f39a30b051631b8a1133cd9453271537d01b87a6b18b7000184c48292a98c` content review PASS、QA ceiling 为 `STATIC_PASS`。因 `logs_rl/` 被批准排除，general full-tree write safety 保持 INCONCLUSIVE；true simultaneous three-reviewer wave 亦为 INCONCLUSIVE，effective metadata UNKNOWN，IsaacLab runtime/training NOT_RUN。`memory_curator` 已完成 exact 12-file atomic delta 与 self-validation；Main independent revalidation 仍是 closure gate。
- 2026-07-11 05:11 HKT - P2-FULL-TREE-WLS-R1 在包含稳定 `logs_rl/` 的 full tree 上完成 C1 single、C2 disjoint simultaneous active、C3 strict overlap serialization、C4 partial interrupt/Main audit/replacement；zero out-of-lease change，exact cleanup 后 HEAD/worktree/index 与 same-encoding manifest 精确恢复，general full-tree write safety PASS。Effective metadata、true simultaneous three-reviewer wave、hooks 与 IsaacLab runtime/training 结论未改变；Main independent memory revalidation 仍是 closure gate。
- 2026-07-13 15:21 HKT - 将 two-strike abnormal-interrupt fallback 写入 root canonical policy、TEAM lifecycle semantics 与 message protocol：第一次同因异常中断经 audit 后只允许一次 retry，第二次仍中断且未交付则禁止第三次相同 child 启动并由 Main bounded takeover；静态一致性已验证，targeted runtime behavior `NOT_RUN`。
- 2026-07-13 16:15 HKT - 新增 Main autonomous `FAST_PATH / COMPLEX_PATH` route gate：普通 read-only、少量 documentation、mechanical memory 与 localized low-risk simple fix 可由 Main 单独完成，免除 child/lease/candidate/multi-review/curator；复杂任务保持完整 pipeline。同步记录 configured 6-thread capacity target 与 planned 3-child wave 分离；static consistency PASS，fresh-task capacity/route runtime `NOT_RUN`。
- 2026-07-13 16:25 HKT - 修正 adaptive concurrency policy：Main + 最多 5 active children，default wave 3；在无 dependency、frozen input、writer path/output 与 resource lease 全部可证明独立时，Main 可自主扩展到 5。Writer safety gate 不放宽；static consistency PASS，expanded-wave runtime `NOT_RUN`。
- 2026-07-13 17:23 HKT - 将 `FAST_PATH / COMPLEX_PATH` 改为 risk-tiered `FAST_PATH / STANDARD_PATH / HIGH_RISK_PATH`：Fast/Standard 成为默认，Standard 可完整调用 ordinary roles 并逐次申请 Deep，High 需 user 对 exact brief 明确同意；同步移除固定全 lane review、per-reviewer full-manifest recompute 与 narrow-fix full rerun。Policy/contract/TOML static consistency PASS，三级 route runtime behavior `NOT_RUN`。
