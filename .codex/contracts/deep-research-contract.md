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
STATUS: PASS | FAIL | INCONCLUSIVE
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

## Phase 0A Restriction

本阶段只保存 contract，不创建 production deep-research TOML，也不进行 Ultra smoke。后续 rollout 必须再次获得 user approval。
