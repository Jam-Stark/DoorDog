# First-class team state

## Purpose

Keep coordination state outside Main's conversational memory. The ledger distinguishes registered roles、declared tasks、spawned agents、running/waiting agents and terminal agents.

Runtime files live under `.ai/runtime/team/` and are Git-ignored:

```text
team-state.sqlite3
team-snapshot.json
hook-events.jsonl
```

## Task identity

Use semantic task names such as:

```text
context_camera_sync
implement_depthadd_r4
review_code_camera_r4
review_isaac_camera_r4
qa_runtime_depthadd_r4
curate_memory_depthadd_r4
```

Nicknames are display-only.

## Contract fields

```text
task_name
canonical_path / agent_id
role
candidate_revision
outcome / stopping condition
dependencies / consumers
read_set / write_set
resource_leases
acceptance / evidence / non_goals
state / latest verdict / artifacts
```

Before `spawn_agent`, run:

```bash
python .ai/scripts/team_state.py contract create ...
python .ai/scripts/team_state.py contract validate --task-name <name>
```

The Codex PreToolUse hook blocks a named spawn when the task contract is absent or missing role-required fields.

## Lease rules

- Same path has one writer at a time.
- Same GPU、IsaacSim process、display、port、hardware、output root or other exclusive resource has one owner.
- Read-only tasks may share paths.
- Lease transfer or expansion requires Main.

## Freeze and verdict

A candidate freeze binds exact source commit、paths、contracts and runtime topology. Reviewer/runtime verdicts bind to the freeze.

Conservative invalidation:

```text
bound item changed       -> INVALID
explicitly disjoint      -> RETAINED
uncertain dependency     -> REVIEW_REQUIRED
```

The ledger does not claim to infer arbitrary code semantics automatically.

## Communication metadata

All `PEER_FINDING`、`PEER_REQUEST` and `AUTHORITY_REQUEST` edges record sender、receiver、revision、summary、material flag and tool-call ID when available. Full message text need not be mirrored into Main context.
