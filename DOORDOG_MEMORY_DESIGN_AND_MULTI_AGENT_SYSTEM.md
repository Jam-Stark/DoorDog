# DoorDog Memory 设计与 Multi-Agent 系统说明

> 快照日期：2026-07-19  
> 项目：`DoorDog-A2_Piper`  
> 导出边界：只描述 memory 设计，不包含任何具体 memory 文件或 topic 内容

## 1. 总体关系

本项目将 durable knowledge、agent coordination 和 repository policy 分开管理：

- File-based memory 只保存可长期复用的 verified fact、decision、stable blocker、TODO/DONE 和可复现验证经验。
- `.codex/` 保存项目级 multi-agent registry、role profile、task/message/review contract 和 eval 定义。
- 根 `AGENTS.md` 是 repository-wide canonical policy，约束 route、权限、fail-fast、memory、review 和 Git closure。
- Live heartbeat、临时 mailbox、agent 中途 finding 和当前 task ledger 不进入 durable memory。

本说明是配置快照，不替代仓库中的 source of truth。

## 2. Memory 设计

### 2.1 分层路由

Memory 使用“root index → subsystem index → topic entry”的三级 route：

```text
root memory index
  -> subsystem memory index
       -> topic entry/
            description.md
            TODO.md
            DONE.md
```

- Root index 只列出 subsystem 及知识边界，不承载详细记录。
- Subsystem index 将问题路由到最相关的 topic，并阻止不同知识域互相污染。
- Topic entry 保存一个边界明确、可独立维护的主题；memory 不是聊天历史或无结构日志。

### 2.2 Entry schema

每个 topic entry 通常包含：

- `description.md`：metadata、purpose、verified decisions/evidence、known caveats、TODO summary 和 DONE summary。
- `TODO.md`：尚未完成、尚未验证或明确保留的工作。
- `DONE.md`：已经达到适用 validation gate 的完成记录。

`description.md` 推荐使用稳定 front matter：

```yaml
---
name: stable-entry-name
scope: bounded knowledge domain
status: current verified state
last_updated: YYYY-MM-DD HH:MM HKT
evidence_level: STATIC_PASS | RUNTIME_BEHAVIOR_PASS | INCONCLUSIVE | NOT_RUN
owned_paths:
  - related/path/
---
```

同一事实不能在 `description.md`、`TODO.md` 和 `DONE.md` 中出现互相冲突的状态。

### 2.3 按风险读取

- `FAST_PATH`：读取 root index、目标 subsystem index 和直接命中的 `description.md`；只有判断施工状态、既有 decision 或 validation command 时继续读 `TODO.md`/`DONE.md`。
- `STANDARD_PATH`：在 Fast 基础上读取与当前 code/config/API decision 直接相关的 entry 和 reference。
- `HIGH_RISK_PATH`：只在 user 同意 exact `HIGH_RISK_BRIEF` 后完成与批准 scope 相关的完整路由，仍禁止无差别读取整个 memory tree。

涉及 code/config 时，必须在已路由 memory 中检索任务关键词，提取可复用的 success、failure、gotcha 和 test/debug command。涉及 IsaacLab scene、spawn、observation、reward、env 或 training semantics 时，还必须核对 official docs 和本地 IsaacLab source；memory 不能替代当前 API source of truth。

### 2.4 写入与一致性

- 只写 durable knowledge，不复制对话、raw log、heartbeat 或临时工作状态。
- 时间戳使用 `YYYY-MM-DD HH:MM HKT`，正文采用中文叙述并保留稳定 English technical terms。
- `STATIC_PASS`、`RUNTIME_BEHAVIOR_PASS`、`INCONCLUSIVE` 和 `NOT_RUN` 必须明确区分；静态解析不能写成 runtime PASS。
- 完成一个 TODO 时，要同步维护该 entry 的 `description.md`、`TODO.md` 和 `DONE.md`。
- `FAST_PATH` 与 `STANDARD_PATH` 的 mechanical memory delta 可由 Main 原子更新并重读验证。
- 只有存在 non-mechanical durable delta 且当前 route 的 triggered review 已 PASS，才允许一个 `memory_curator` 获得明确、独占的 memory `WRITE_SET`。
- merge、rebase、cherry-pick、conflict resolution 或 code/config 改动后，必须检查相关 memory 是否 stale。

### 2.5 Durable memory 与 live coordination

Memory 不承担 agent message bus 的职责：

| 内容 | 保存位置 |
|---|---|
| Verified fact、durable decision、stable caveat | Topic `description.md` |
| 未完成工作 | `TODO.md` |
| 已达到验证门槛的完成记录 | `DONE.md` |
| Agent finding、question、heartbeat、interrupt 状态 | 当前 task 的 live message |
| Lease、dependency、candidate、active-agent 状态 | Main 的 live ledger |

这种分离避免 transient state 污染长期知识，也避免后续任务把历史自述误当成当前 runtime evidence。

## 3. Multi-Agent 配置

### 3.1 Source of truth

优先级和职责如下：

1. 根 `AGENTS.md`：repo-wide canonical policy。
2. `.codex/TEAM.md`：architecture、role routing、wave、lease、candidate、review、memory 和 closure。
3. `.codex/contracts/`：delegated task、message、review 和 Deep Research contract。
4. `.codex/config.toml` 与 `.codex/agents/*.toml`：registry 与 role profile。
5. `.codex/evals/`：role discovery、contract、parallel coordination、write-lease safety 和 hooks capability 定义/证据。

`.codex/AGENTS.md` 只作用于 `.codex/` subtree，不能覆盖根 policy。

### 3.2 Project config

| 设置 | 值 | 含义 |
|---|---|---|
| Main | `gpt-5.6-sol` / `xhigh` | 唯一 scope、route、approval、lease、candidate、integration、memory authorization 和 Git authority |
| MultiAgentV2 | `enabled = true` | 启用 project custom role registry |
| Thread target | `6` total | Main + 最多 5 active children；runtime 暴露更低限制时服从实际限制 |
| Default wave | `3` children | 只有完成 independence proof 才扩展到 5 |
| Tool namespace | `agents` | 避免保留 namespace 冲突 |
| Spawn metadata | visible | `hide_spawn_agent_metadata = false` |
| Agent depth | `1` | child 不得递归 fan-out |

扩展到第四、第五个 concurrent child 前，Main 必须证明 sibling 使用 frozen/既有 input、没有 dependency edge、writer 的 `WRITE_SET`/artifact 完全不重叠，且 GPU、IsaacSim、display、port、process 等 resource lease 无冲突。

### 3.3 三级 route

```text
TASK_INTAKE
  -> bounded / low-risk / local / reversible -> FAST_PATH
  -> ordinary product work                  -> STANDARD_PATH
  -> true high-risk trigger                 -> HIGH_RISK_BRIEF
                                                -> approved -> HIGH_RISK_PATH
                                                -> declined -> narrow to Standard | BLOCKED
```

- `FAST_PATH`：Main-only；minimal memory → direct work → targeted validation → one Main diff audit。禁止为形式完整性 spawn、建 candidate 或重复 review。
- `STANDARD_PATH`：普通 product work 默认；按需 discovery/planning、lease-bound implementation、candidate freeze、风险触发 review/QA、必要的 durable memory 和 Main final audit/commit。
- `HIGH_RISK_PATH`：只用于高 blast radius、难回滚或高成本任务；必须先提交 exact brief 并取得 user 明确同意。

### 3.4 Registered roles

| Role | Model / effort | 权限 | 职责 |
|---|---|---|---|
| `role_probe` | Terra / high | read-only | Effective role/model/effort/sandbox/no-write sentinel |
| `scope_planner` | Sol / xhigh | read-only | Scope、architecture、DAG、acceptance、approval-ready plan |
| `context_researcher` | Terra / high | read-only | Repo、docs 和 memory context research |
| `deep_researcher` | Sol / ultra | read-only | Exact per-invocation approval only；never self-activate/downgrade |
| `isaaclab_worker` | Luna / max | workspace-write | 只在 leased `WRITE_SET` 内 implement/debug |
| `goal_reviewer` | Sol / max | read-only | Conditional plan/candidate goal gate |
| `code_reviewer` | Sol / max | read-only | Code quality；按 surface 触发 security/performance/data compatibility |
| `isaaclab_reviewer` | Sol / max | read-only | IsaacLab/RL/reward/env/training semantics review |
| `runtime_qa` | Terra / high | workspace-write | 只写 leased evidence/output，绝不改 candidate |
| `memory_curator` | Terra / high | workspace-write | Approved non-mechanical durable memory single writer |

### 3.5 Shared filesystem 与 authority

所有 agent 共享同一 filesystem，不是隔离 worktree：

- 同一路径、同一 revision 只有一个 writer；path/resource overlap 必须串行。
- Delegated task 必须明确 task/revision/route/authorization、destination、stopping condition、acceptance、memory context、baseline、`READ_SET`、exclusive `WRITE_SET`、resource lease、dependencies、deliverable 和 verify。
- Child 不得扩大 scope、转移 lease、修改 acceptance、stage/commit/push 或清理 pre-existing dirty path。
- Main 独占 scope/route/approval/lease/candidate/memory authorization、所有 Git mutation 和完成声明。
- Interrupt 不等于 rollback；Main 必须等待 terminal、审计 partial write/lease violation 并 invalidate candidate。
- 同一 bounded child task 因同一异常连续失败两次后，禁止第三次启动；Main 只可接管原批准 scope/lease 内的最小剩余工作，缺少能力则返回 `BLOCKED`。

### 3.6 Candidate、review 与 closure

- Fast 不创建 candidate；Standard/High 只有在所有 writer terminal、lease 释放后才能 freeze candidate。
- Main 在 freeze 和 pre-commit 各计算一次 canonical manifest；reviewer 只核对 assigned paths/entries 和 supplied candidate identity。
- Standard source/config 默认触发 code quality review 与 targeted runtime QA；其余 lane 只在对应风险 surface 真实改变时触发。
- 每个 concern 只有一个 owner，reviewer 不修 code。Narrow fix 只重跑 impacted lane；material scope/API/runtime/candidate/dependency 改变时才 full rerun。
- `FAIL`、`BLOCKED`、`INCONCLUSIVE`、`NOT_RUN` 或缺失 evidence 都不能通过 gate。
- Git 由 Main 独占；满足当前 route 的 validation/review/memory/terminal gate 后才 stage/commit，默认不 push。

## 4. Fail-fast

Code/config 不添加不必要的 guard、fallback、silent downgrade 或错误吞噬。缺失配置、shape/type/device mismatch、unsupported API 和 invalid state 应给出清晰错误并在运行/训练中暴露。IsaacLab code 优先 high-level API；能用 framework contract 完成时，不用 low-level USD API 绕开约束。

系统证据也遵循 fail-fast：requested profile、静态 TOML、agent self-report 或 registration 都不自动等于 effective runtime PASS；runtime 没有暴露的字段保持 `UNKNOWN/INCONCLUSIVE`。

## 5. 当前 multi-agent evidence ceiling

- Project TOML、role profile 和 contract matrix 已有 static/strict validation evidence。
- Selector control 与三个 distinguishing roles 的 effective metadata 已验证：`role_probe` = Terra/high、`scope_planner` = Sol/xhigh、`isaaclab_worker` = Luna/max。
- Full-tree write-lease safety 的 C1-C4 场景已有 PASS evidence。
- 九个 non-Deep role 的 bounded positive contract behavior 有保存的 PASS evidence，但完整 explicit-selector nine-role matrix 尚未完成。
- Fresh-task effective 6-thread capacity 与 route-aware coordination 仍为 `NOT_RUN`。
- True simultaneous three-reviewer wave 为 `INCONCLUSIVE`；hooks 未配置。
- `deep_researcher` registered-but-dormant，没有逐次批准不得调用。
- Profile sandbox defaults 未被完整证明；parent live override 与 profile default 必须分层记录。

## 6. 导出包内容

压缩包保留以下仓库相对路径：

```text
DOORDOG_MEMORY_DESIGN_AND_MULTI_AGENT_SYSTEM.md
AGENTS.md
.codex/
```

- `.codex/` 包含 local policy、`TEAM.md`、`config.toml`、十个 role profile、contracts 和 eval/evidence 文件。
- `AGENTS.md` 包含 repo-wide route、fail-fast、memory 和 multi-agent authority policy。
- 不包含任何 `MEMORY.md` 或 `memory/` topic 内容，也不包含 `.git/`、日志、模型、数据、产品源码或 `scriptsFORhuman/` 工作文件。

迁移到另一项目时，必须重新核对目标项目的 root policy、路径、model catalog、permission profile、runtime capability 和 memory route，不能把本项目的 static/runtime evidence 直接当作目标项目的 PASS。
