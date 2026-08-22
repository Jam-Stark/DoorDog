# DoorDog Codex MultiAgentV2 workflow

## Roles

Use the existing project `.codex/agents/*.toml` definitions. Typical capabilities remain:

```text
scope_planner
context_researcher
deep_researcher
isaaclab_worker
code_reviewer
isaaclab_reviewer
runtime_qa
memory_curator
```

Registered role、declared task、spawned agent、running/waiting agent and terminal agent are different states. Read `.ai/runtime/team/team-snapshot.json` rather than inferring them from role registration.

## Main authority

`/root` is the sole orchestrator. Only Main may change scope、acceptance、candidate revision、WRITE_SET、GPU/resource lease、model/cost escalation、hard stop、Git and external writes.

## Spawn sequence

```bash
python .ai/scripts/team_state.py contract create \
  --task-name context_camera_sync \
  --role researcher \
  --outcome "Locate the current camera pose contract" \
  --read-set gr00t/rl/envs \
  --acceptance "Return exact files, API evidence and reproduction"

python .ai/scripts/team_state.py contract validate --task-name context_camera_sync
```

Then call `spawn_agent(task_name="context_camera_sync", ...)`.

## P2P

Use:

- `PEER_FINDING` for exact code/API/runtime evidence;
- `PEER_REQUEST` for bounded diagnosis or read-only help;
- `AUTHORITY_REQUEST` to `/root` for scope、revision、lease、gate、Git or hard stop.

`send_message` is for a live peer and does not start a new turn. `followup_task` is for real subsequent work on a non-root target. Do not use the shared filesystem as a chat bus.

Record material P2P metadata in the team ledger. Mirror only material summaries to Main; do not flood Main with every technical message.

## Candidate and review

Freeze exact candidate paths、contracts and runtime topology before review/QA. Reviewers return scoped verdicts. A narrow fix invalidates only bound or uncertain lanes; unaffected verdicts remain retained.

## Long runs

`runtime_qa` owns exact commands and receipts, not product code. Runs over 30 minutes use the long-run supervisor and named tmux. Completion creates a pending event; it does not assume an ended Main turn can be revived.
