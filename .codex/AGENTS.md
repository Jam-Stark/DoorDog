# Codex adapter v1.4.0

Follow root AGENTS.md and the task-relevant .ai routes. Main model/effort belong to the App/user configuration, never a project default. Use .codex/TEAM.md when delegating; model/effort/context policy is .ai/MODEL_ROUTING.md.

Use focused children and direct technical P2P. Main retains write/resource/Git authority. Do not stop at the first implementation when the authorized goal includes a working result and narrow verification. Do not turn this into repeated reviews or broad test campaigns.

For long runs, follow .ai/LONG_RUNNING_TASKS.md: quiet durable waiter, one ETA-sized logical wait, early return on completion/failure; no repeated 30-minute model polling. A pending event is not a wake guarantee.

Linked-worktree hooks on Codex 0.153.0: `.codex/hooks.json` is the declaration source; run `python3 .ai/scripts/install_codex_hooks.py` after changes to register worktree-scoped user hooks. Review/trust via `/hooks`; details and unresolved host issues: `.ai/WORKFLOW_FIXES.md`.
