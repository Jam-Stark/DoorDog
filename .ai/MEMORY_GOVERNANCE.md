# Active memory governance, candidate-triggered

## Principle

Do not append to an existing entry merely because it exists. Before writing, decide whether the fact belongs there. Create、move、split、merge、supersede or retire entries when retrieval quality requires it.

Memory work is not a mandatory closure phase. If the current task produced no durable reusable fact, do nothing.

## Candidate triggers

Any agent may emit a `MEMORY_CANDIDATE` when:

- a verified durable fact fits no current route;
- one entry mixes independent topics;
- the same conclusion is repeatedly rediscovered;
- current source/runtime evidence supersedes an old conclusion;
- historical numbers are easy to mistake for the current baseline;
- duplicate entries begin to drift;
- an entry is too large for efficient recovery.

For a single small candidate, Main may include it in the final report or write an inbox record directly. Spawn `memory_curator` only when canonical writing or non-trivial restructuring is actually needed.

## Canonical write authority

Workers/researchers propose. Main or a triggered `memory_curator` performs canonical writes after checking evidence and classification. The curator may:

```text
create a route or entry
move a misclassified fact
split a mixed entry
merge duplicates
mark superseded/retired
update routers and memory/_index.json
```

Do not create permanent entries for live progress、heartbeat、P2P messages、raw logs or unsupported inference.

## Entry metadata

New or materially reworked entries should state:

```text
status: active | superseded | retired
scope
read_when
source_of_truth
evidence / last_verified
supersedes / related_entries
```

## Tools

```bash
python .ai/scripts/memory_curator.py candidate-add ...
python .ai/scripts/memory_curator.py candidate-list
python .ai/scripts/memory_curator.py candidate-show --candidate <id>
python .ai/scripts/memory_curator.py reindex
```

The script does not automatically perform complex move/split/merge/supersede operations. A curator edits those deliberately, verifies the route, then marks the candidate resolved.
