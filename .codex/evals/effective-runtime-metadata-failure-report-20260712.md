# Effective Child Profile Selection Diagnostic Report

## Executive Summary

- **Date:** 2026-07-12 HKT
- **Repository:** `DoorDog-A2_Piper`
- **Observed baseline HEAD:** `a1d0734d8652e3a4f3e2b93fb3335c704263ed06`
- **Codex surface under test:** ChatGPT desktop App project task
- **Phase 0 verdict:** The tested App spawn surface did not expose a custom-profile selector.
- **Phase 1 status:** The metadata experiment and GPT-5.6 namespace compatibility fix are merged and static-validated.
- **Phase 2 status:** Fresh-task selector controls and the three-role distinguishing matrix are runtime `PASS`; the selector gate is unblocked, while the full nine-role contract matrix remains separate work.

The project-scoped registry and agent TOMLs still have static evidence, but the previous runtime probes did not exercise custom-profile selection. The available `spawn_agent` schema accepted only `task_name`, `fork_turns`, and `message`; it did not expose `agent_type`. A role name in `task_name` or prompt text is not a selector. The resulting children were generic, parent-derived children, so their Main-like role/model/effort metadata does not prove that a selected profile was loaded and then ignored.

The previous sandbox failure conclusion is also superseded. Codex reapplies the parent task's live sandbox and approval settings to children, including custom agents. A child matching a `danger-full-access` parent is therefore documented override behavior, not by itself evidence of profile-selection failure.

## Corrected Verdicts

```text
PROFILE_STATIC: PASS
APP_SELECTOR_EXPOSURE: FAIL
CUSTOM_ROLE_RUNTIME_SELECTION: NOT_EXERCISED
CUSTOM_PROFILE_EFFECTIVE_ROLE: INCONCLUSIVE
CUSTOM_PROFILE_EFFECTIVE_MODEL: INCONCLUSIVE
CUSTOM_PROFILE_EFFECTIVE_EFFORT: INCONCLUSIVE
GENERIC_CHILD_PARENT_INHERITANCE: EXPECTED FOR THE TESTED INVOCATION
PARENT_LIVE_SANDBOX_OVERRIDE: EXPECTED
CUSTOM_PROFILE_SANDBOX_DEFAULT: NOT PROVEN
COORDINATION_BEHAVIOR: BOUNDED PASS
FULL_TREE_WRITE_SAFETY: PASS
APP_PRODUCTION_ROLE_ROLLOUT: BLOCKED
DEEP_RESEARCHER: NOT_RUN / DORMANT
```

These verdicts describe the Phase 0 baseline. The repaired Phase 1 configuration has not yet received a fresh-task selector verdict; a preflight run made under the intermediate namespace-only configuration did not satisfy the Phase 1 precondition and is not Phase 2 evidence.

`FAIL` here applies to selector exposure on the tested App task. It does not establish a launcher defect after successful profile selection, because no selector was submitted. `INCONCLUSIVE` fields must not be upgraded using requested TOML values, prompt identity, task names, sentinel tokens, child self-report, or UI labels alone.

## Expected Selection Contract

The project registry maps an explicit custom role to its profile. After a trusted project resolves `agent_type`, these profile defaults are expected before higher-priority live overrides are applied:

| Registered role | Profile model | Profile effort | Profile sandbox default |
|---|---|---:|---|
| `role_probe` | `gpt-5.6-terra` | `high` | `read-only` |
| `scope_planner` | `gpt-5.6-sol` | `xhigh` | `read-only` |
| `context_researcher` | `gpt-5.6-terra` | `high` | `read-only` |
| `deep_researcher` | `gpt-5.6-sol` | `ultra` | `read-only` |
| `isaaclab_worker` | `gpt-5.6-luna` | `max` | `workspace-write` |
| `goal_reviewer` | `gpt-5.6-sol` | `max` | `read-only` |
| `code_reviewer` | `gpt-5.6-sol` | `max` | `read-only` |
| `isaaclab_reviewer` | `gpt-5.6-sol` | `max` | `read-only` |
| `runtime_qa` | `gpt-5.6-terra` | `high` | `workspace-write` |
| `memory_curator` | `gpt-5.6-terra` | `high` | `workspace-write` |

The parent Main profile is `gpt-5.6-sol` / `xhigh`. Sandbox values in the table are profile defaults, not guarantees against a higher-priority parent live sandbox/approval override.

## What the Previous Probes Actually Exercised

Three uniquely named children were created:

1. `/root/metadata_role_probe_20260712_r2a`
2. `/root/metadata_scope_planner_20260712_r2b`
3. `/root/metadata_isaaclab_worker_20260712_r2c`

The available spawn surface exposed only:

- `task_name`
- `fork_turns`
- `message`

It did not expose `agent_type`, `role`, or another registry-key field. Consequently:

- Unique task names only established distinct collaboration task identities.
- Role names and tokens inside `message` tested prompt-following behavior.
- The children were not valid custom-profile activation probes.
- Main-like role/model/effort values were expected generic-child inheritance for that invocation.
- The synthetic worker correctly returned `BLOCKED` for `WRITE_SET=[]` and made no project write; this remains bounded behavioral evidence, not role activation evidence.

The user-observed UI metadata remains useful auxiliary evidence that the children behaved as generic Main-derived children. The UI cannot show whether an unsubmitted selector would have resolved correctly, and it is not a substitute for launcher/state metadata.

## `fork_turns` Constraint

For the inspected `0.144.0-alpha.4` path, role/model/effort overrides must be tested with:

```text
fork_turns = "none"
```

The full-history fork path (`fork_turns="all"`) inherits the parent configuration and does not provide the required custom-profile override path; an explicit override combined with full-history fork should be rejected rather than silently treated as a successful custom-role launch. Phase 2 must include this as a negative control.

Relevant version-pinned implementation references:

- [`spawn.rs`](https://github.com/openai/codex/blob/rust-v0.144.0-alpha.4/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs)
- [`multi_agents_spec.rs`](https://github.com/openai/codex/blob/rust-v0.144.0-alpha.4/codex-rs/core/src/tools/handlers/multi_agents_spec.rs)
- [`role.rs`](https://github.com/openai/codex/blob/rust-v0.144.0-alpha.4/codex-rs/core/src/agent/role.rs)

## Sandbox Precedence

Codex custom-agent configuration supplies defaults. Parent-turn live sandbox and approval settings are reapplied to children. Therefore a child created under a live `danger-full-access` parent can legitimately have effective `danger-full-access`, even when its custom profile declares `read-only` or `workspace-write`.

Phase 2 must record both:

- requested profile sandbox default; and
- effective sandbox plus its override source.

It must not demand mechanically distinct child sandboxes while a single parent live override forces the same effective permission. A separate session without such a live override is required to validate profile sandbox defaults, if the App surface permits one.

Official reference: [Codex Subagents — approvals and sandbox controls](https://developers.openai.com/codex/multi-agent#approvals-and-sandbox-controls).

## Phase 1 Configuration Experiment and Compatibility Repair

The original Phase 1 experiment opted into the version-pinned MultiAgentV2 metadata surface:

```toml
[features.multi_agent_v2]
enabled = true
max_concurrent_threads_per_session = 4
hide_spawn_agent_metadata = false
```

It omitted `tool_namespace`, so MultiAgentV2 used the `collaboration` default. On the affected GPT-5.6 Responses path, `collaboration.spawn_agent` collided with the model-reserved namespace/schema and every message was rejected before inference. This was a request-construction failure, not evidence about selector resolution.

The intermediate namespace-only workaround restored messaging by setting `tool_namespace = "agents"`, but it did not retain `hide_spawn_agent_metadata = false` or the V2 concurrency control. The resulting fresh task still hid `agent_type`, `model`, and `reasoning_effort`; that preflight did not satisfy the Phase 1 prerequisite and cannot be counted as Phase 2.

The repaired experiment merges both requirements:

```toml
[features.multi_agent_v2]
enabled = true
max_concurrent_threads_per_session = 4
hide_spawn_agent_metadata = false
tool_namespace = "agents"

[agents]
max_depth = 1
interrupt_message = true
```

`tool_namespace = "agents"` preserves GPT-5.6 messaging compatibility, while `hide_spawn_agent_metadata = false` requests selector exposure. The legacy `agents.max_threads` setting is removed so it does not compete with `max_concurrent_threads_per_session`; every registry table remains unchanged.

The merged TOML, ten role registrations, profile paths, and Codex configuration loading passed static validation on 2026-07-13 HKT. This is still not runtime evidence. It does not prove that the ChatGPT desktop App host will expose the selector fields. A full App restart and a fresh trusted project task are required.

## Phase 2 Fresh-Task Gate

After restarting the App, create a new task in this trusted project. Before spawning any child, inspect the available `spawn_agent` schema.

Required selector surface:

```text
agent_type
model
reasoning_effort
```

If these fields are still absent:

1. Stop without running role probes.
2. Mark the App host or managed tool plan as overriding/ignoring the project experiment.
3. If the metadata experiment has no benefit, remove its metadata/concurrency controls only after recording the result; retain `tool_namespace = "agents"` so the GPT-5.6 reserved-schema failure does not return.
4. Prepare an upstream bug bundle with App/build version, effective project path, sanitized config, tool schema, and logs.

Do not attempt to compensate by placing the role in `task_name` or `message`.

If the fields are present, run read-only controls with `fork_turns="none"`:

| Control | Required result |
|---|---|
| Unknown `agent_type` | Fail before child creation |
| `task_name="role_probe"` without `agent_type` | Remain the default/generic role |
| Custom `agent_type` with `fork_turns="all"` | Reject before child creation |
| `agent_type="role_probe"`, unique task name, `fork_turns="none"` | Resolve the registered profile |

Only after these controls pass should the three-role distinguishing matrix run:

| Explicit selector | Required profile model/effort |
|---|---|
| `role_probe` | `gpt-5.6-terra` / `high` |
| `scope_planner` | `gpt-5.6-sol` / `xhigh` |
| `isaaclab_worker` | `gpt-5.6-luna` / `max` |

Effective sandbox must be judged using the precedence rule above. `deep_researcher` remains excluded: registration is not invocation approval, and Deep requires a fresh exact user-approved brief plus effective Sol/Ultra/read-only evidence.

## Phase 2 Fresh-Task Runtime Result — 2026-07-13 HKT

The repaired Phase 1 configuration loaded in a fresh trusted App task and exposed the full selector surface:

```text
agent_type
fork_turns
message
model
reasoning_effort
service_tier
task_name
```

Selector controls produced the required fail-fast behavior:

| Control | Runtime evidence | Verdict |
|---|---|---|
| Unknown `agent_type` | App log at `2026-07-12T16:31:28.613380Z` records `unknown agent_type 'nonexistent_role_selector_control_20260713'`; no child rollout was created. | PASS |
| `task_name="role_probe"` without `agent_type` | Rollout `019f572b-c342-7303-aac8-39b14f1175e1` omits the `session_meta.agent_role` key and uses Main `gpt-5.6-sol/xhigh`. | PASS |
| Explicit profile override with `fork_turns="all"` | App log at `2026-07-12T16:32:19.119757Z` rejects the incompatible full-history fork before child creation; no silent fallback occurred. | PASS |
| `agent_type="role_probe"`, `fork_turns="none"` | Rollout `019f572c-a912-73f0-940b-461ee680f034` resolves `agent_role="role_probe"` with `gpt-5.6-terra/high`. | PASS |

The distinguishing matrix used explicit selectors with `fork_turns="none"`:

| Selector | `session_meta.agent_role` | `turn_context` model/effort | Effective permission |
|---|---|---|---|
| `role_probe` | `role_probe` | `gpt-5.6-terra / high` | `danger-full-access / never` |
| `scope_planner` | `scope_planner` | `gpt-5.6-sol / xhigh` | `danger-full-access / never` |
| `isaaclab_worker` | `isaaclab_worker` | `gpt-5.6-luna / max` | `danger-full-access / never` |

The effective permission is the App parent task's live sandbox/approval override. It is consistent with the documented precedence rule and does not prove the profiles' `read-only` or `workspace-write` sandbox defaults effective in a session without that override.

Authoritative rollout evidence:

- Generic control: `/home/baoquanc/.codex/sessions/2026/07/13/rollout-2026-07-13T00-31-53-019f572b-c342-7303-aac8-39b14f1175e1.jsonl`, SHA-256 `f2efb7aa698c6d4b27e3ff244acc90951766e9b4f18566ebe84c5ba1b317f735`.
- Explicit `role_probe` control: `/home/baoquanc/.codex/sessions/2026/07/13/rollout-2026-07-13T00-32-52-019f572c-a912-73f0-940b-461ee680f034.jsonl`, SHA-256 `562338a7b3fe3461f601cf51e7d0c7be91eb0db9750b63c57fbb0c5705dd1e7b`.
- Matrix `role_probe`: `/home/baoquanc/.codex/sessions/2026/07/13/rollout-2026-07-13T00-33-35-019f572d-50fb-7b53-9034-b338dbe19465.jsonl`, SHA-256 `226ded2e4d9740df2f1bd8f9d19b0567a33a87e7c7836cf458827371a4621d4b`.
- Matrix `scope_planner`: `/home/baoquanc/.codex/sessions/2026/07/13/rollout-2026-07-13T00-33-54-019f572d-996f-7ad0-88fd-598ec4f576ae.jsonl`, SHA-256 `9985adfb7d30b70316a9b96a331d88cdc05361544f0b5f0de5e22ee195b7dce5`.
- Matrix `isaaclab_worker`: `/home/baoquanc/.codex/sessions/2026/07/13/rollout-2026-07-13T00-34-11-019f572d-dd01-79b1-ad97-1b249ffc7588.jsonl`, SHA-256 `2d5141fda24fb23ab67b80b2f2acc069decbd17838dbccf76c170c0332b242ce`.

All five child rollouts contain `task_started` and `task_complete`, with zero tool calls. The scoped session list contains no `deep_researcher`. Before/after evidence remains HEAD `a1d0734d8652e3a4f3e2b93fb3335c704263ed06` with only the two pre-existing task paths (`M .codex/config.toml` and the untracked report); the selector test introduced no project or Git-index delta.

```text
APP_SELECTOR_EXPOSURE: PASS
PHASE_2_SELECTOR_CONTROLS: PASS
CUSTOM_ROLE_RUNTIME_SELECTION: PASS
PHASE_2_DISTINGUISHING_MATRIX: PASS
APP_PRODUCTION_ROLE_ROLLOUT: SELECTOR_GATE_PASS / UNBLOCKED
PROFILE_SANDBOX_DEFAULTS: NOT_PROVEN UNDER PARENT LIVE OVERRIDE
DEEP_RESEARCHER: NOT_RUN / DORMANT IN SCOPED SESSION SET
```

The verdict ceiling is selector-gate PASS for the App surface and runtime metadata PASS for the three tested profiles. It is not a nine-role contract-matrix PASS, profile-sandbox-default PASS, hooks PASS, or simultaneous-reviewer PASS.

## Evidence Requirements

Evidence priority for Phase 2 is:

1. launcher/subagent start metadata containing `agent_id`, selected `agent_type`, model, and effective permission;
2. runtime telemetry/state containing model, effort, sandbox, and approval policy;
3. child rollout/state metadata;
4. App UI as cross-check only;
5. child-generated text as non-authoritative behavioral evidence only.

App and CLI must receive separate verdicts. A CLI PASS cannot be used as an App PASS, and an App selector-exposure FAIL does not prove the same failure in CLI.

## Preserved Evidence Boundary

- The repaired merged Phase 1 config, project profiles, and registry consistency are `STATIC PASS` as of 2026-07-13 HKT.
- App selector exposure, four selector controls, and the three-role distinguishing matrix are runtime `PASS` within the scoped Phase 2 evidence.
- Previously tested bounded role/coordination behavior remains `BOUNDED PASS`.
- Previously completed full-tree write-lease/interrupt evaluation remains `PASS`.
- Effective custom role/model/effort is proven for the three tested explicit selectors; the remaining registered roles still require the separate explicit-selector contract matrix.
- Profile sandbox defaults remain unproven because the App parent live permission override forced `danger-full-access / never`.
- No hook capability test has been run; hook work remains a separate approval boundary.
- No Deep invocation occurred in the scoped Phase 2 session set.
- The earlier namespace-only preflight created no child and is not Phase 2 selector evidence.
- Pre-existing product changes remain outside this diagnostic scope.

## Builder Remediation if Selector Exposure Still Fails

If a fresh App task still hides the selector, the product-level remedy is to:

1. Expose an explicit typed `agent_type` independently of `task_name`.
2. Resolve it against the trusted project registry before child creation.
3. Apply the resolved developer instructions, model, and reasoning effort atomically.
4. Apply parent live sandbox/approval overrides as a separate documented precedence layer.
5. Fail before child creation for unknown roles, invalid profiles, unavailable model/effort, or unsupported fork/override combinations; do not silently claim profile activation.
6. Return authoritative requested/resolved/effective metadata and override sources from spawn and agent-detail surfaces.
7. Keep Deep's exact per-invocation approval, no-downgrade, read-only policy mechanically enforceable.

Phase 2 now establishes explicit selector resolution and effective role/model/effort metadata for the three-role distinguishing matrix on the App surface. The selector blocker is removed. Full production closure still requires the separate nine-role explicit-selector contract matrix and any independently approved concurrency, hooks, or sandbox-default evaluations; Deep remains dormant without a fresh exact approval brief.
