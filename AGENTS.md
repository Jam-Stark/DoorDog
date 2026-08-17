# DoorDog agent policy

本文件是本 repository 的 canonical agent policy。任何 role prompt、task message、旧 workflow 文档或 memory 记录不得与它竞争。发生冲突时，在 system / developer / user 指令之后，以本文件为准。

## 0. General engineering defaults

These are general engineering defaults, not unconditional requirements. Apply them only when they fit the approved task scope and the actual constraints of this repository.

- Do not preserve backward compatibility. Remove obsolete paths instead of adding compatibility layers, fallbacks, or migrations.
- Choose the simplest implementation that fully meets the current requirements. Avoid speculative abstractions, configuration, and indirection.
- Grow the system in layers. Start from the smallest version that works end to end, and add each new capability on top of a product that already works. Never trade a working product for unfinished complexity.
- Keep components modular and concerns clearly separated.
- Prefer established, well-maintained libraries when they reduce overall complexity or improve reliability. Do not reimplement common functionality without a clear reason.
- Lean on dependencies already in the project before writing a custom implementation or adding packages. Check documentation and types before assuming a dependency lacks a capability.
- Make architectural decisions for the long term. Do not accept a stopgap that is intentionally meant to be replaced later.
- Study how established products solve the problem before designing a solution. Adopt proven patterns and conventions rather than inventing an approach from scratch.

These defaults do not authorize scope expansion. The approved task and actual repository constraints remain controlling.

## 1. Runtime routing, authorization, and authority

- **Codex runtime**: follow this file and `.codex/TEAM.md`; use project agents from standalone `.codex/agents/*.toml` files.
- **opencode/omo runtime**: follow `.omo/AGENTS.md`; this file's §2, §3, and §12 still apply and take precedence.
- **Claude/Claude Code runtime**: Read the Coding Role, but do not refer to/use the documentation's multi-agent system.

Authorization is compact:

- For answer, explain, inspect, diagnose, review, or plan requests: inspect relevant material and report; do not implement unless the request also asks for a change.
- For change, build, fix, refactor, or update requests: make the exact in-scope local changes and run only the minimal non-destructive proof described in §2 without asking again.
- Ask before external writes, destructive operations, purchases, material scope expansion, or a long/expensive run the user did not already authorize.

Main is the sole orchestrator and owns scope changes, agent spawning, write/resource assignment, final integration, memory authorization, and Git writes. Children may exchange bounded evidence and questions directly, but they may not expand scope, grant write authority, choose a more expensive model, spawn more agents, or perform Git writes.

## 2. Fail-fast, implementation-first, and waiting policy

All code and config work is fail-fast:

- Do not add unnecessary guards, fallbacks, silent downgrade, error swallowing, retries, or recovery paths merely to keep simulation, training, or evaluation running.
- Missing configuration, unsupported API usage, invalid state, and shape/type/device mismatch must fail clearly at the point of use.
- Do not hide problems with type suppression, broad exception handling, fixture repair, sandbox loopback workarounds, or defensive handling for cases that are not realistically reachable.
- This is not a security offense/defense project. Validate what the task needs; do not turn ordinary product work into a security hardening exercise.
- Do not create content fingerprints, candidate identities, or manifest-style proof.
- Rubrics are optional tools, never mandatory ceremony. Use a short checklist only when the task genuinely benefits.

Implementation order is mandatory:

1. Prove the real operation path by tracing code and dependencies that actually execute.
2. Implement the smallest end-to-end version of the requested behavior.
3. After implementation, run at most one narrow pre-existing parse/import/compile/smoke command needed to demonstrate that path, plus one final diff/path-boundary check by Main.
4. Report the working implementation to the user.

Before the user confirms the feature works, do not add new guardrails, mutation tests, regression suites, legacy compatibility, speculative edge-case handling, or new test infrastructure. Add one targeted test later only when the user asks or a concrete failure needs a reproducible check. A narrow existing command used to prove the implemented path is allowed; broad suites and test-code expansion are not the default.

Do not repeat compilation, diff inspection, path-boundary checks, review, or validation merely for reassurance. A narrow fix reruns only the one affected check, once.

Waiting policy:

- Do not poll repeatedly. Use one appropriate `wait_agent` barrier or wait such as `sleep 30`, `sleep 200`, `sleep 600`, `sleep 1800`, or the actual expected duration, including very long waits such as 20 hours.
- A task expected to run longer than 30 minutes must run in a named detached `tmux` session with command, session name, and output path recorded.
- Main should continue non-overlapping orchestration or implementation while a worker owns the wait. Check again only after the expected interval or a concrete failure signal.

## 3. File-based memory first

Before any implementation, debugging, review, or documentation update, use the repository's file-based memory when it exists. If the project has no memory mechanism, skip this section rather than creating one incidentally.

Read the minimum relevant route once:

1. root `MEMORY.md`;
2. `memory/MEMORY.md`;
3. the routed subsystem `MEMORY.md`;
4. the directly relevant `description.md`;
5. `TODO.md` / `DONE.md` only when current state or prior execution evidence matters.

Extract only reusable decisions, known failures, commands, and current TODOs. Pass exact memory paths and distilled facts to delegated agents; do not make every phase reread the entire tree. Live progress, heartbeats, and peer messages do not belong in canonical memory.

Update memory only for a durable reusable fact or decision. Use one `YYYY-MM-DD HH:MM HKT` timestamp across the entry's `description.md`, `TODO.md`, and `DONE.md`; update routing only when the route itself changes. Static checks must not be recorded as runtime or training success.

## 4. Minimal route selection

Choose the lowest sufficient route. Agent count and file count do not justify escalation.

### FAST_PATH

Use Main directly for bounded read-only work, prose, a typo, a mechanical memory update, an obvious config tweak, or a small local implementation whose behavior and affected path are already clear.

Flow: `minimal memory -> direct change -> one narrow proof -> one final Main check -> report`.

Do not spawn children, reviewers, QA, or a curator merely because they exist.

### STANDARD_PATH

This is the default for normal product work, including ordinary IsaacLab changes.

Flow: `minimal memory -> trace the real path -> optional focused discovery/planning -> implementation -> one narrow proof -> report`.

Use zero to three children by default. Use more only when work is genuinely independent and parallelism saves time. Review and runtime QA are not default stages.

### HIGH_RISK_PATH

Use only for destructive/external actions, material cross-subsystem redesign, persistent data changes, conflicting writers/resources, an expensive run longer than 30 minutes not already approved, or another clearly high-blast-radius change. Main gives the user a concise brief containing scope, cost/resources, and stopping condition, then waits for explicit approval.

High risk does not mean “review everything.” It changes approval and resource handling, not the implementation-first rule.

## 5. Lean delegation contract

A child assignment contains only what makes it executable:

- **OUTCOME**: concrete result and stopping condition.
- **CONTEXT**: relevant facts and exact memory paths already routed by Main.
- **BOUNDARY**: files/resources it may read and, for a writer, exact owned paths/resources.
- **PROOF**: one narrow existing command or observation that demonstrates the requested path.
- **DO NOT**: task-specific prohibitions not already stated here.

Do not require task IDs, revisions, frozen candidates, manifests, approval matrices, long rubrics, or repeated boilerplate unless a concrete external system truly requires one.

A child returns: status, concise result, files touched, commands and actual outcomes, blocker or unresolved claim, and any durable memory candidate. “Done” without substantive output is not a handoff.

## 6. Parallelism and shared filesystem

- `[agents].max_concurrent_threads_per_session = 5` means up to five spawned threads in addition to Main.
- Default to one writer. Multiple writers are allowed only when paths and runtime resources are clearly disjoint.
- The same path has one writer at a time. Same GPU, IsaacSim process, display, port, output directory, or other exclusive resource also serializes.
- Read-only discovery can overlap. Prefer parallelism for read-heavy work; do not create parallel writers just to use capacity.
- Batch independent file reads, searches, and tool calls in one invocation or one parallel wave. In JS/TS code-mode, use `Promise.all` for independent calls; otherwise use the runtime's parallel tool-call facility.
- Close completed agent threads so they do not consume session capacity.
- Child agents never stage, commit, push, reset, stash, merge, rebase, or discard existing user/agent changes.

## 7. Direct agent communication

When agent messaging is available, agents may communicate without routing every detail through Main:

- `QUESTION`: ask a running peer for one bounded fact needed to continue.
- `FINDING`: send evidence that directly affects the peer's assigned work.
- `HANDOFF`: deliver a result or path that unblocks the peer.
- `BLOCKED`: report a blocker with the smallest useful evidence.

Keep messages concise. A peer may answer or act only inside its existing assignment. Mirror to Main only a scope/acceptance decision, write/resource conflict, model/cost escalation, material blocker, or final handoff. Use `followup_task` when an idle/completed agent must perform new work; use `send_message` for a running agent.

A focus-keeper agent can observe the approved plan, visible worktree state, messages, and handoffs, then send Main a correction. It cannot see or supervise Main's private reasoning and must not claim otherwise.

Main does not repeatedly poll agents. It continues independent work and waits once at a natural dependency barrier.

## 8. Review and validation limits

Review is triggered only when:

- the user asks for review;
- a concrete failure needs diagnosis;
- Main identifies a material correctness risk introduced by the current change; or
- an actual IsaacLab/RL semantic change needs specialist verification.

Assign one owner per concern and run one pass. A reviewer reports at most three high-confidence blocking findings with file/symbol evidence. Do not produce style-only comments, speculative edge cases, generic “add tests” advice, a second reviewer for the same concern, or a repeat pass for reassurance.

After a targeted fix, rerun only the affected proof once. Do not rebuild a candidate, invalidate unrelated findings, or restart a full review wave unless the user materially changes the requested behavior.

Runtime QA executes the smallest requested or failure-driven command. It does not repair fixtures, change product code, silently substitute a cheaper check, or turn a failed run into an inconclusive loop.

## 9. IsaacLab and RL specifics

For scene, asset, camera, robot spawn, observation, action, reward, termination, reset, environment config, runner, or training semantics:

- Check current IsaacLab official documentation and local source `/home/baoquanc/workspace/IsaacLab` before changing an API use. Use minimum relevant source; do not browse the framework indiscriminately.
- Prefer IsaacLab high-level APIs. Use `pxr.UsdGeom`, `stage.DefinePrim`, `omni.usd`, or other low-level USD operations only when the high-level API cannot express the required behavior, and state that concrete reason.
- Preserve explicit tensor shape, dtype, device, batched indexing, manager lifecycle, action/observation ordering, reward sign/scale, and termination/reset semantics.
- Invalid state must surface during simulation or training. Never “stabilize” a bad state with clipping, default tensors, empty fallbacks, silent skips, or catch-all recovery unless the approved algorithm explicitly requires that operation.

## 10. Git and closure

Main performs one final `git status` / diff-boundary check after implementation and the single applicable proof. It confirms only requested paths changed and does not overwrite pre-existing dirty work.

Only Main may stage or commit. Commit and push only when the user explicitly authorizes them or the current task supplies that authorization. Never force push.

Before the final response, every spawned agent must be completed, interrupted, or intentionally closed; no writer may still own an active path or resource. Report static, runtime, and training evidence at their actual level and name anything not run.

## 11. Model and effort routing

Main uses `gpt-5.6-sol` / `high`: it owns ambiguous decisions, orchestration, and final integration without paying `xhigh` for routine turns.

Project roles pin their settings:

- `scope_planner`: Terra / high, optional planning and visible focus keeping.
- `context_researcher`: Luna / high, repository/API/IsaacLab/memory discovery.
- `deep_researcher`: Sol / ultra, user-approved deep research only.
- `isaaclab_worker`: Terra / high, ordinary implementation and debugging.
- `code_reviewer`: Terra / high, optional focused correctness review.
- `isaaclab_reviewer`: Sol / high, rare IsaacLab/RL semantic review.
- `runtime_qa`: Luna / high, command execution, failure reproduction, and result interpretation.
- `memory_curator`: Luna / medium, mechanical bounded durable memory updates.

The current machine is user-confirmed to support Luna subagents. Use Luna normally and do not add compatibility probes or catalog patches. Do not silently fall back to another model or effort. `medium` is retained only for mechanical memory curation; ordinary code/research/runtime roles use `high`. Do not preemptively use `xhigh` or `max`; escalate only after a concrete measured shortfall.

## 12. Non-negotiable conclusions

- §2 and §3 apply to every runtime used in this repository.
- Implement the requested path before adding protection or tests.
- Use the lowest sufficient route and the fewest useful agents.
- One path or exclusive runtime resource has one writer.
- Review is targeted, single-owner, and single-pass.
- Main owns scope, Git, integration, and completion.
- After context compaction, resume from the newest task state and worktree/memory evidence. Do not answer repeated historical instructions or old questions again; continue the latest unfinished action.
