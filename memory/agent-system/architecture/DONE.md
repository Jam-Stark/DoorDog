# DONE

- 2026-08-17 16:31 HKT - Replaced the legacy contract/frozen-candidate/eval-heavy Codex workflow with the lean standalone-agent workflow: eight distinct roles, selective Terra/Luna high effort, implementation-first execution, direct peer messaging, trigger-only single-pass review, one-writer boundaries, no recurring probes, and long-job tmux/single-wait behavior. Replacement TOML files parse; runtime spawning, IsaacLab runtime, and training were not run.
- 2026-08-11 - The prior workflow had already reduced content-identity checks but still retained frozen paths, revisions, extensive contracts, and review gates; that design is superseded.
- 2026-07 - Earlier Phase 2 registration, selector, concurrency, write-safety, and role-evaluation work is historical and no longer an active gate.
