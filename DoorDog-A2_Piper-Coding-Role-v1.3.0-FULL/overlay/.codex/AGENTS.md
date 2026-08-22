# `.codex` local policy

Root `../AGENTS.md` is canonical. Read it first.

- For FAST work, do not read `TEAM.md` and do not initialize team state.
- Read `TEAM.md` only when using project roles、P2P、multiple agents or formal coordinated work.
- `.codex/config.toml` and `.codex/agents/*.toml` are project-owned and must not be overwritten by this role pack.
- `.codex/hooks.json` is adaptive: inactive coordination is a no-op; active coordination enforces only the selected controlled tasks.
- Do not recreate a contract/freeze/review pipeline for ordinary implementation.
- Git commit/push require explicit authorization in the current task; never modify global `~/.codex/config.toml`.
