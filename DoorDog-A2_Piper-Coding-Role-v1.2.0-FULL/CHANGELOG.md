# Changelog

## 1.2.0 — 2026-08-22

### Codex MultiAgentV2

- Corrected the v1.1 review candidate: current Codex MultiAgentV2 supports direct agent-to-agent `send_message` and `followup_task` routing by canonical task path.
- Kept Main as the sole control plane for scope, acceptance, candidate revision, write/resource leases, Git, external writes, and final integration.
- Added `PEER_FINDING`, `PEER_REQUEST`, and `AUTHORITY_REQUEST`, plus material-summary mirroring instead of copying every peer message into Main context.
- Added stable semantic task-name guidance; generated nicknames are display-only.

### Coordination state

- Added `.ai/TEAM_STATE.md`, `templates/TEAM_STATE.toml`, `scripts/team_state.py`, and an optional Codex hook adapter.
- Added task contracts, writer/resource lease checks, candidate freeze records, scoped reviewer verdicts, and conservative verdict invalidation.
- Exact dependency changes invalidate a PASS; uncertain relationships become `REVIEW_REQUIRED` rather than being silently retained.

### Active memory governance

- Added `.ai/MEMORY_GOVERNANCE.md` and `scripts/memory_curator.py`.
- Agents should actively propose new routes, split mixed entries, move misclassified facts, merge duplicates, supersede stale conclusions, and retire obsolete entries instead of mechanically appending to existing files.
- Added a memory-candidate inbox and machine-readable memory index; canonical writes remain controlled by Main or the designated curator.

### Long-running continuity

- Added `.ai/LONG_RUNNING_TASKS.md` and `scripts/run_supervisor.py`.
- Added tmux-backed run receipts, checkpoint validation, optional follow-up evaluation, pending-event persistence, and `tmux wait-for` barriers.
- Explicitly does not claim that an external process can always revive a disconnected or ended Main turn; pending events are injected at a later session start/resume.

### Artifact handoff

- Updated the default Google Drive target to `Pro_Space`, folder ID `1JWQrkkOrItsKlFUjfxsadUrOcXChGpOf`, with Owner-approved public writer access.
- Added create-only standing authorization and capability-based routing: connected Drive upload, browser/computer-use upload, authenticated `rclone`, or `NOT_UPLOADED` with a prepared handoff.
- Preserved allowlist selection, secret scanning, size limits, checkpoint opt-in, unique project/worktree/stage namespaces, and upload receipts.
- Clarified that public editor access in the web UI does not itself create anonymous Drive API credentials.

### Runtime adapters and bootstrap

- Preserved OMO ordinary delegation and official Team Mode lifecycle.
- Preserved standalone Claude Code as a single-agent lane.
- Kept the universal Chinese expression standard for all runtimes and models.
- Added `--codex-coordination-state` and `--long-run-supervisor`.

### Migration

`1.2.0` supersedes the unmerged `1.1.0` review candidate. Bootstrap still refuses to overwrite project-owned entrypoints and adapters; use the migration example or the DoorDog replacement package for deliberate adoption.

## 1.1.0 — review candidate, not released to `AI_things/main`

Added runtime-specific routing, Chinese expression guidance, optional multi-planner stage decisions, and guarded artifact packaging. Its Codex collaboration section understated MultiAgentV2 peer communication and is superseded by 1.2.0.

## 1.0.0 — 2026-08-21

Initial reusable behavior kernel, adaptive workflow, scientific extension, runtime adapters, project-growth model, bootstrap/audit helper, and DoorDog migration example.
