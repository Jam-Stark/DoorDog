# DoorDog Codex adapter

Root `../AGENTS.md` and `.ai/*` are canonical. Read `.codex/TEAM.md` when a task needs role selection、P2P、lease、freeze、review or long-run coordination.

Preserve project-owned `.codex/config.toml` and `.codex/agents/*.toml`.

Before a named `spawn_agent`, register its contract with `.ai/scripts/team_state.py`. Use direct P2P for bounded technical information; authority decisions return to `/root`.

Do not recreate removed legacy contract matrices、periodic role probes、blanket reviewer waves or synthetic pass gates. v1.2 team state exists to reduce manual orchestration state, not to force every task through every role.
