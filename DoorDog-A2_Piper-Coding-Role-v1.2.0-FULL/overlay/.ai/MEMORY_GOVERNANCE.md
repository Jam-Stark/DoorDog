# Active memory governance

## Principle

Do not append to an existing entry merely because it exists. Before writing, decide whether the fact belongs there. Actively create、move、split、merge、supersede or retire entries when retrieval quality requires it.

## Memory candidate triggers

Any agent should emit a candidate when:

- a durable fact fits no current route;
- one entry mixes independent topics;
- the same conclusion is rediscovered repeatedly;
- current source/runtime evidence supersedes an old conclusion;
- historical numbers are easy to mistake for the current baseline;
- duplicate entries begin to drift;
- an entry is too large for efficient recovery.

Candidate records go to `.ai/runtime/memory-inbox/` and contain source evidence、suggested action、target route and bounded body text.

## Canonical write authority

Workers/researchers propose. Main or `memory_curator` performs canonical writes after checking evidence and classification. The curator may:

```text
create a new route or entry
move a misclassified fact
split a mixed entry
merge duplicates
mark superseded/retired
update root/subsystem routers and memory/_index.json
```

Do not create a permanent entry for live progress、heartbeat、P2P messages、raw logs or unsupported inference.

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

When new evidence overturns an old claim, keep enough provenance to understand the change while making current truth easy to find.

## Tools

```bash
python .ai/scripts/memory_curator.py candidate add ...
python .ai/scripts/memory_curator.py candidate list
python .ai/scripts/memory_curator.py promote --candidate <id> --yes
python .ai/scripts/memory_curator.py reindex
```

Promotion is a material repository write and remains under Main/Owner authority.
