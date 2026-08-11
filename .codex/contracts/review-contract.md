# Frozen-Candidate Review Contract

Review 的对象是 immutable candidate，不是移动中的 worktree。
Candidate 仅是当前 `TASK_ID`/`REVISION` 与 exact `FROZEN_PATHS` 的 frozen lifecycle state，不生成独立 identity value。

本 contract 只适用于 `STANDARD_PATH` / `HIGH_RISK_PATH` frozen candidate。Main-only `FAST_PATH` 不创建 candidate 或 multi-lane review；其 closure 使用 targeted validation、必要的 memory consistency 与一次 Main diff/final audit。

## Candidate Freeze

Main 在所有 writers terminal 且 leases released 后：

1. 记录当前 `TASK_ID`、`REVISION` 与 `PRE_EXISTING_DIRTY_PATHS`，再用 Git 状态、diff、索引读取和文件读取审计 task paths。
2. 确认只有 assigned `WRITE_SET` 与明确批准的 task artifacts 被当前 task 修改；检查覆盖 tracked modification、tracked deletion、untracked file 与 explicitly approved ignored file。
3. 运行适当 static validation。
4. 记录 exact approved `FROZEN_PATHS`，确认没有 out-of-scope changed path，并在 review 完成前禁止 writer 修改 frozen candidate。

Main 在 freeze 与 pre-commit 各直接检查一次 `FROZEN_PATHS` 的 Git 状态、diff 与文件内容。任意 frozen path 的状态或内容改变、revision 不一致或出现 out-of-scope path 都会使 frozen candidate 与相关 verdict 失效；Main 必须递增 revision 后重新 freeze。Ignored 或 untracked path 不得因为普通 Git diff 看不到而从 frozen path list 排除。

## Required Review Result

```text
STATUS: PASS | FAIL | INCONCLUSIVE
TASK_ID:
REVISION:
FROZEN_PATHS:
LANE:
FINDINGS:
EVIDENCE:
VALIDATION_LEVEL:
UNVERIFIED_BEHAVIOR:
RECOMMENDED_NEXT_ACTION:
```

Reviewer 必须验证其 assigned concern 所需的 `FROZEN_PATHS`、`REVISION` 与直接 Git/file evidence，并确认自己审查的内容属于同一 frozen candidate。Reviewer 不重复 Main 的全局路径审计。缺少 frozen path、revision 不一致、内容不匹配或 candidate 在 review 中变化时返回 `INCONCLUSIVE`。

## Route-aware Review Lanes

`STANDARD_PATH` source/config candidate 默认只需要：

1. `code_reviewer:CODE_QUALITY`
2. risk-proportionate targeted `runtime_qa`

以下 lane 仅按 trigger 增加：

- Goal/Constraint：scope、acceptance、authorization 或 forbidden-action risk。
- IsaacLab/Fail-fast：实际修改 IsaacLab/RL/reward/observation/action/scene/env/training semantics。
- Security / Performance / Data Compatibility：对应 trust/resource/schema surface 改变。
- Memory Context / `memory_curator`：存在 non-mechanical durable memory delta。

`HIGH_RISK_PATH` 的 mandatory lanes 来自 user 已同意 `HIGH_RISK_BRIEF` 的 risk justification；High 不自动等于全部 lane。每个 concern 只有一个 reviewer owner，不用多个 lane 重复审同一问题。

## Verdict Rules

- `PASS`：当前 route 实际 triggered mandatory lanes 对同一 candidate PASS。
- `FAIL`：任一 mandatory lane 发现 blocking defect。
- `INCONCLUSIVE`：没有 confirmed blocking defect，但 evidence 不足、candidate mismatch 或 required validation 未完成。

`INCONCLUSIVE`、`NOT_RUN`、agent 自述、requested profile 或 static parse 不能批准 candidate。

## Validation Levels

```text
NOT_RUN
STATIC_PASS
NO_SIM_PASS
RUNTIME_SMOKE_PASS
TRAINING_PASS
FAIL
```

低层级 evidence 不得冒充高层级：compile/import 不是 runtime PASS，短 smoke 不是 training PASS。

Runtime QA 至少报告 exact command、environment、duration/steps、exit status、actual output、expected output、artifact/log path 与未覆盖行为。

## Severity and Fix Loop

- `P0`：数据破坏、安全问题、错误 training semantics 或不可恢复状态。
- `P1`：功能、reward/transition、shape、device 或 API contract 错误。
- `P2`：明确 maintainability/test gap，但不阻断当前行为。
- `P3`：非阻断建议。

P0/P1 阻断 candidate。Targeted fix 返回获 lease implementer，Main 递增 revision并重新 freeze，只重跑受影响 lanes。只有 scope、public/API contract、runtime semantics、candidate topology 或 material dependency 改变时，才使所有相关 verdict 失效并 full rerun。同类 fix 连续失败两次后停止 shotgun modification，重新评估 route；若需升级 High 或调用 Deep，分别取得对应 user approval。

无 durable memory delta 时跳过 Memory Context 与 curator。Fast/Standard mechanical memory 由 Main 原子更新并重读验证；non-mechanical durable delta 才在 triggered review PASS 后进入单写者 memory update。

## Foundation Versus Runtime Activation

Static catalog acceptance 与 effective runtime observability 是两个独立 evidence dimensions：

- Phase 2 catalog 可以通过 TOML parse、Codex strict-config startup parse、path/schema checks、frozen-path direct audit 与 `git diff --check` 获得 static PASS。User 已明确批准 direct registration，因此 registered profiles 可以用于 Main-controlled routing；registration/static PASS 不证明 effective child identity/model/effort。
- Role-discovery 在缺少 explicit effective role/model/effort/sandbox 与 no-write evidence时保持 `NOT_RUN` 或 `INCONCLUSIVE`。这个 observability gap 不会 unregister 已批准 profiles，也不要求停止 ordinary routing，但任何 effective model/effort、sandbox 或 runtime behavior claim 必须保持 UNKNOWN/INCONCLUSIVE。
- Static PASS、sentinel token、requested profile 或 agent自述不能替代 effective runtime evidence，也不得升级成 false model/runtime PASS。
- `deep_researcher` 每次 invocation 的 explicit approval、write-safety runtime eval、hooks capability + separate approval，以及任何被声称为 PASS 的 runtime behavior 都保留各自独立 gate；不得用 catalog registration 绕过。
