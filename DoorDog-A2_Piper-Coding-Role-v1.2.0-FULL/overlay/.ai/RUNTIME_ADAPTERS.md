<!-- managed-by: jam-coding-role; file: RUNTIME_ADAPTERS.md -->
# Runtime adapters

## Codex MultiAgentV2

- Root `AGENTS.md` is the repository entrypoint; project roles remain in `.codex/agents/*.toml` and model/effort/concurrency remain in `.codex/config.toml`.
- Main owns the agent tree and all authority decisions.
- Current MultiAgentV2 supports direct agent-to-agent `send_message` and `followup_task` routing by relative or canonical task path.
- `send_message` queues a message and does not start a new turn. `followup_task` may trigger work for a non-root target; it is not used to wake root.
- Use P2P for facts, evidence, targeted defects, reproductions and bounded requests. Scope, acceptance, revision, lease, Git and external writes return to Main.
- `.codex/hooks.json` validates registered spawn contracts and records coordination metadata. It must not parse private reasoning or treat the shared filesystem as a chat bus.

## OpenCode / OMO

- `opencode.json.instructions` explicitly loads the canonical `.ai/*` files.
- Ordinary delegation and OMO Team Mode remain separate.
- Team Mode is optional; when enabled it retains official shared task list、mailbox、claim/update and shutdown lifecycle.
- `task(category=...)` and `task(subagent_type=...)` remain distinct routes; ineligible specialists are invoked through ordinary task delegation rather than forced into a team.
- OMO rules do not redefine Codex P2P semantics.

## Standalone Claude Code

- `CLAUDE.md` imports root policy and the `.ai/*` hierarchy.
- Standalone Claude is a single-agent local planner/implementer.
- `.claude/settings.json` denies the Agent tool and disables agent view.
- Claude-family models used inside OMO remain governed by OMO; that does not turn standalone Claude Code into a team.

## Shared rules

- Universal behavior and Chinese expression rules live only in `.ai/ROLE.md`.
- Project facts live only in `.ai/PROJECT.md`.
- Model/provider/tool/runtime details stay in the corresponding runtime config.
- Do not imitate unsupported capability: if a runtime lacks P2P、upload、wake or hardware tools, use the available path and state the limitation.
