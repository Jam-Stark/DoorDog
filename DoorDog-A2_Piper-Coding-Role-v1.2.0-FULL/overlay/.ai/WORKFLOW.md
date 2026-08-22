<!-- managed-by: jam-coding-role; file: WORKFLOW.md -->
# DoorDog adaptive workflow

## 1. Lowest sufficient route

### Direct

Bounded read-only work, prose, typo, mechanical config or one clear local change:

```text
minimal memory -> real path -> change/read -> matching evidence -> report
```

### Focused

Normal cross-file implementation or debugging:

```text
route context -> trace real path -> short acceptance plan
-> smallest end-to-end implementation -> claim-matched evidence -> integrate
```

Use 0–3 agents only when they have independent value.

### Coordinated

Use when there are independent research/implementation lanes, multiple writer/resource leases, high-risk cross-subsystem work, long runs, external writes, hardware, or Owner-requested independent review.

## 2. Control plane and information plane

Main `/root` is the control plane. It owns scope, acceptance, revision, lease, Git, external writes, hard stops and final conclusions.

Codex MultiAgentV2 P2P is the information plane. Direct messages should reach the consumer instead of forcing Main to copy every technical detail.

Message classes:

- `PEER_FINDING`: exact source/API/runtime evidence that affects an existing peer assignment;
- `PEER_REQUEST`: bounded diagnosis, evidence or read-only request that does not change scope/lease;
- `AUTHORITY_REQUEST`: revision、scope、acceptance、WRITE_SET、GPU/resource、hard stop、Git 或外部写入请求，只能发给 Main。

All P2P edges enter the team ledger. Only material blocker, candidate-ready state, reviewer/runtime verdict, dependency change or authority request is summarized to Main.

## 3. Structured task before spawn

Before `spawn_agent`, Main registers a task contract in the team ledger. Role-specific required fields are checked before the child turn starts. Contracts contain only what makes the task executable:

```text
task_name / role / revision
outcome / stopping condition
dependencies / consumers
read_set / write_set / resource leases
acceptance / evidence / non-goals
```

Task names use lowercase letters、digits 和 underscores。Generated nicknames are display-only.

## 4. Candidate freeze and targeted re-review

Before review or formal runtime QA, Main freezes exact paths、contracts、resolved config and runtime topology under a candidate revision. Verdicts bind to that scope.

After a narrow change:

- exact bound path/contract/topology changed -> `INVALID`;
- explicitly disjoint change -> `RETAINED`;
- uncertain relationship -> `REVIEW_REQUIRED`.

Do not rely on Main memory to decide silently, and do not rerun unaffected lanes.

## 5. Active memory

Every agent may emit a `MEMORY_CANDIDATE` when a durable fact is new, misclassified, duplicated, superseded or difficult to retrieve. Formal create/move/split/merge/supersede/retire operations are performed by Main or `memory_curator` under `.ai/MEMORY_GOVERNANCE.md`.

Team ledger is live coordination state; memory is durable reusable truth. Never mix them.

## 6. Long runs

Runs over 30 minutes use `.ai/scripts/run_supervisor.py` and named tmux. Process exit can validate checkpoints, trigger an authorized eval and write pending events. It does not claim to revive an ended/disconnected Main turn; a later session reads pending events.

## 7. Evidence and closure

Evidence matches the claim: inspect/static/test/runtime/experiment/hardware. Do not repeat the same proof for reassurance.

Before completion:

- no untracked writer/resource lease remains active;
- diff/path boundary is checked once;
- spawned agents are terminal or intentionally interrupted;
- static/runtime/experiment evidence is reported at its actual level;
- stage artifact packaging is performed only when relevant.
