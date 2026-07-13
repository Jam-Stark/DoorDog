# Frozen-Candidate Review Contract

Review 的对象是 immutable candidate，不是移动中的 worktree。

本 contract 只适用于 `COMPLEX_PATH` frozen candidate。Main-only `FAST_PATH` 不创建 candidate 或 multi-lane review；其 closure 使用 targeted validation、必要的 memory consistency 与 Main diff/final audit。

## Candidate Freeze

Main 在所有 writer terminal 后：

1. 对照 `BASE_SHA` 与 `PRE_EXISTING_DIRTY_PATHS` 审计 task diff。
2. 确认只有 assigned `WRITE_SET` 与明确批准的 task artifacts 被当前 task 修改。
3. 运行适当 static validation。
4. 对 approved task paths 建立 canonical manifest，并计算 candidate ID：

   ```text
   CANDIDATE_MANIFEST = sort_by_repo_relative_path([
     path + status_relative_to_BASE_SHA + sha256(exact_current_content_or_DELETED)
     for every approved task path
   ])

   CANDIDATE_ID = sha256(BASE_SHA + canonical_serialize(CANDIDATE_MANIFEST))
   ```

5. Manifest 必须递归覆盖 approved `WRITE_SET` 与明确批准 task artifacts 中的所有路径，包括 tracked modification、tracked deletion、untracked file 与 ignored-but-explicit task file。存在的文件记录 exact content hash；deletion 记录明确 `DELETED` status/sentinel。
6. 确认没有 out-of-scope changed path，并在 review 完成前禁止 writer 修改 candidate。

任意 approved task path 的 status/content 改变都会生成新 `CANDIDATE_ID`，并使旧 code/config/runtime review verdict 全部失效。Ignored 或 untracked 不得因为普通 Git diff 看不到而从 candidate 排除。

## Required Review Result

```text
STATUS: PASS | FAIL | INCONCLUSIVE
CANDIDATE_ID:
LANE:
FINDINGS:
EVIDENCE:
VALIDATION_LEVEL:
UNVERIFIED_BEHAVIOR:
RECOMMENDED_NEXT_ACTION:
```

Reviewer 必须验证 canonical manifest 的路径全集、status、content hash 与当前 worktree 精确一致，重新核对 candidate hash，并确认没有 out-of-scope changed path。只复述 Main 提供的 candidate ID 不算验证。Manifest/ID 缺失、内容不匹配或无法覆盖 ignored/untracked explicit task file 时返回 `INCONCLUSIVE`。

## Review Lanes

复杂 IsaacLab/RL task 默认需要：

1. Goal/Constraint
2. Code Quality
3. IsaacLab/Fail-fast
4. Runtime QA
5. Memory Context

Dependency、network、auth、credential 或 external data surface 变化时增加 Security。高风险、多 writer、merge/conflict 或 repeated-fix task 可增加 Final Gate。

## Verdict Rules

- `PASS`：所有 mandatory lanes 对同一 candidate PASS。
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

P0/P1 阻断 candidate。Targeted fix 返回原 implementer，Main 递增 revision，重新 freeze，并重跑所有 mandatory code/config lanes。同类 fix 连续失败两次后停止 shotgun modification，转入 architecture consultation；需要 deep research 时仍必须单独 user approval。

Canonical memory update 晚于 review PASS。Complex-path memory-only patch 必须重跑 Memory Context 与 Main final audit；fast-path mechanical memory 由 Main 原子更新并重读验证。

## Foundation Versus Runtime Activation

Static catalog acceptance 与 effective runtime observability 是两个独立 evidence dimensions：

- Phase 2 catalog 可以通过 TOML parse、Codex strict-config startup parse、path/schema checks、candidate manifest audit 与 `git diff --check` 获得 static PASS。User 已明确批准 direct registration，因此 registered profiles 可以用于 Main-controlled routing；registration/static PASS 不证明 effective child identity/model/effort。
- Role-discovery 在缺少 explicit effective role/model/effort/sandbox 与 no-write evidence时保持 `NOT_RUN` 或 `INCONCLUSIVE`。这个 observability gap 不会 unregister 已批准 profiles，也不要求停止 ordinary routing，但任何 effective model/effort、sandbox 或 runtime behavior claim 必须保持 UNKNOWN/INCONCLUSIVE。
- Static PASS、sentinel token、requested profile 或 agent自述不能替代 effective runtime evidence，也不得升级成 false model/runtime PASS。
- `deep_researcher` 每次 invocation 的 explicit approval、write-safety runtime eval、hooks capability + separate approval，以及任何被声称为 PASS 的 runtime behavior 都保留各自独立 gate；不得用 catalog registration 绕过。
