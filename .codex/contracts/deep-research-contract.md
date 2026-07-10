# Deep Research Contract

Deep research 是唯一允许 `gpt-5.6-sol` / `ultra` 的 exception。它不是默认 escalation，也不能 self-activate。

## Per-Invocation Approval Brief

Main 必须在每次 invocation 前向 user 提交并获得明确确认：

```text
RESEARCH_QUESTION:
WHY_NORMAL_LANES_ARE_INSUFFICIENT:
SOURCE_AXES:
EXPECTED_DELIVERABLE:
MODEL: gpt-5.6-sol
EFFORT: ultra
SUPPORTING_READ_ONLY_LANES:
ALLOWED_TOOLS:
WRITE_POLICY: read-only
STOPPING_CONDITION:
```

先前 task、先前 research 或 architecture plan 的 approval 不能复用于新的 deep invocation。

## Authority and Boundaries

- Main 保留 scope、approval、lane creation、acceptance criteria 与 final synthesis authority。
- Deep researcher 和 supporting lanes 全部 read-only；不得修改 code、config、memory、artifact、Git 或 external state。
- v1 `max_depth = 1`。Deep researcher 不得 spawn child；需要 support 时向 Main 请求，由 Main 在 thread limit 内建立 independent lane。
- 结果必须区分 sourced fact、inference、conflict 与 unresolved uncertainty。

## No-Fallback Rule

- `gpt-5.6-sol`、`ultra`、effective role 或 read-only sandbox 任何一项明确 mismatch 时返回 `FAIL`。
- Runtime 没有提供上述 effective evidence 时返回 `INCONCLUSIVE`。
- Ultra unavailable 时立即停止并交回 Main；不得自动降级为 `max`、其他 model 或普通 research lane。
- Requested profile、TOML 内容、prompt echo 或 agent 自报都不是 effective runtime evidence。

## Required Result

```text
STATUS: PASS | FAIL | BLOCKED | INCONCLUSIVE
RESEARCH_QUESTION:
EFFECTIVE_RUNTIME_EVIDENCE:
FINDINGS:
SOURCE_MAP:
COUNTER_EVIDENCE:
INFERENCES:
UNRESOLVED_UNCERTAINTY:
STOPPING_CONDITION_RESULT:
RECOMMENDED_NEXT_ACTION:
```

## Phase 2 Registered Profile

Phase 2 已注册 `deep_researcher` profile，但 registration 不是 invocation approval，也不证明 effective Sol/Ultra/read-only runtime。该 role 仍保持 dormant-by-policy、never self-activate，且本次 registration 不授权 Ultra smoke。

每一次实际调用都必须重新提交本文件的完整 approval brief 并取得 user 明确确认。缺少逐次 approval 时返回 `BLOCKED`；缺少 effective runtime evidence 时返回 `INCONCLUSIVE`。不得因为 profile 已注册而跳过 approval、降级 model/effort、写文件或 spawn child。
