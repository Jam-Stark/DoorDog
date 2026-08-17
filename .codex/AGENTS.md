# `.codex` local policy

Root `../AGENTS.md` is canonical. Read it first. Read `TEAM.md` only when a Codex task needs role selection, delegation, direct agent communication, or long-job coordination.

The active Codex workflow consists only of:

- `.codex/config.toml` for current `[agents]` defaults and concurrency;
- standalone `.codex/agents/*.toml` custom-agent definitions;
- `.codex/TEAM.md` for lean routing and communication.

Do not recreate the removed contracts, evals, frozen-candidate lifecycle, role probe, model matrix, rollout gates, or recurring compatibility ceremony unless the user explicitly requests one concrete evaluation after an observed defect.

When changing agent config, parse the affected TOML files once and perform one final path/reference check. Do not run repeated catalog, sandbox, metadata, compile, or diff audits for reassurance. Do not modify global `~/.codex/config.toml`.
