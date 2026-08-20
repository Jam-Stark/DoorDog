# DoorDog Codex multi-agent workflow

## Active shape

Codex discovers project roles from standalone `.codex/agents/*.toml` files. `.codex/config.toml` sets Main to Sol/high, generic children to Terra/high, and allows five spawned threads in addition to Main.

This workflow is implementation-first. It has no mandatory planner gate, frozen candidate, reviewer wave, runtime-QA gate, memory gate, role probe, contract matrix, or periodic model check.

The user confirms the current machine accepts Luna subagents. Use Luna normally for its assigned roles; do not spend work on re-proving availability during ordinary tasks.

## Model and effort matrix

| Role | Model / effort | Use only when |
|---|---|---|
| `scope_planner` | Terra / high | scope, architecture, dependency order, or Main focus genuinely needs clarification |
| `context_researcher` | Luna / high | one repository path, official API, local IsaacLab contract, or routed memory fact must be traced |
| `deep_researcher` | Sol / ultra | the user explicitly approved one deep/Ultra research question normal lanes cannot settle |
| `isaaclab_worker` | Terra / high | implementing or debugging ordinary DoorDog/IsaacLab product work |
| `code_reviewer` | Terra / high | the user asks for review or one concrete correctness concern is triggered |
| `isaaclab_reviewer` | Sol / high | the change alters actual IsaacLab/RL/reward/observation/action/scene/env/training semantics |
| `runtime_qa` | Luna / high | one proof command, failure reproduction, or user-approved long run must be executed and interpreted |
| `memory_curator` | Luna / medium | one validated, bounded durable memory delta must be written mechanically |

`medium` remains only for mechanical memory curation. All code interpretation, implementation, review, research, and runtime interpretation uses `high`. Do not preemptively use `xhigh` or `max`; raise effort only after a concrete task shows a measured quality shortfall. `deep_researcher` is the explicit Ultra exception.

## Routine flow

1. Main reads the minimum routed file memory and distills relevant facts.
2. Main traces the real execution path directly or with focused read-only agents.
3. Main states a concise implementation sequence and assigns exact writer/resource boundaries.
4. Worker implements the smallest end-to-end behavior.
5. Worker or Main runs one narrow pre-existing proof after implementation.
6. Main performs one final diff/path check and reports the result to the user.

No role exists only to approve another role. Review, runtime QA, and memory curation are invoked only by their actual triggers. The feature is implemented before new guardrails, regression infrastructure, mutation coverage, legacy compatibility, or speculative tests are considered.

## Delegation message

Use this compact shape and omit empty sections:

```text
OUTCOME: concrete result and stopping condition
CONTEXT: distilled facts + exact memory paths
BOUNDARY: read scope; exact write paths and exclusive resources for a writer
PROOF: one narrow existing command or observation
DO NOT: task-specific prohibitions not already in root policy
```

Prefer `fork_turns="none"` for named custom agents when the active spawn tool exposes it. Pass only the context needed for the assignment. Use a history fork only when recent conversation state is genuinely required.

A child returns: status, concise outcome, touched paths, command and actual result, blocker or unverified claim, and any durable memory candidate. A generic acknowledgement is not a handoff.

## Direct autonomous communication

A running agent may send a concise `QUESTION`, `FINDING`, `HANDOFF`, or `BLOCKED` message directly to a relevant peer. This is the preferred path for local dependencies that do not change scope.

Mirror to Main only when a message changes or blocks scope, acceptance, write/resource ownership, model/cost choice, or final integration. Peers cannot authorize extra writes, agents, scope, model escalation, or Git operations.

Use `send_message` for an active peer. Use `followup_task` to wake an idle/completed role for real next work. A planner/focus keeper may send Main a correction based on visible plan progress, worktree evidence, or agent results; it does not claim access to Main's private reasoning.

## Parallelism and tool batching

- Default wave: zero to three children.
- Maximum: five spawned threads, excluding Main.
- Read-only work may overlap.
- One writer is preferred. Multiple writers require disjoint paths and disjoint GPU/IsaacSim/display/port/process/output resources.
- Batch independent searches, reads, and tool calls in one parallel wave. In JavaScript/TypeScript code-mode, use `Promise.all` for independent calls; otherwise use the runtime's parallel tool-call facility.
- Main continues non-overlapping work instead of polling.
- Close completed threads to free capacity.

## Review ceiling

A triggered reviewer owns one concern for one pass and returns no more than three high-confidence blocking findings with file/symbol evidence. No style-only review, speculative hardening, generic test agenda, full-rubric scoring, second reviewer for the same concern, or repeat pass for reassurance.

A targeted fix reruns only its affected proof once. Review does not rebuild a candidate lifecycle or invalidate unrelated work.

## Runtime and long jobs

`runtime_qa` runs the smallest exact command and interprets its actual result. It must not edit product code, repair fixtures, hide invalid state, or substitute a cheaper check.

Use one appropriately sized `wait_agent` barrier or one wait such as `sleep 30`, `sleep 200`, `sleep 600`, `sleep 1800`, or the actual expected interval, including very long waits. Do not poll. A run expected to exceed 30 minutes belongs in a named detached `tmux` session with command, session name, and output path recorded. Main should delegate the wait and continue non-overlapping orchestration where possible.
