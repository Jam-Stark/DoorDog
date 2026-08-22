# Optional long-running task continuity

Read this file only when a run is expected to exceed 30 minutes or must survive chat/network interruption.

## Minimal choice

- One bounded, already-authorized run may use a named `tmux` session and a `RUN_RECEIPT.json` without activating the full team ledger.
- Activate team ledger/leases only when multiple runs、writers or exclusive resources can conflict.

## Run contract

Record:

```text
run name / tmux session
exact command
source revision and worktree
resolved config / checkpoint lineage
actual exclusive resources
output/log paths
checkpoint expectation
stopping and cancellation conditions
optional authorized follow-up eval
```

## State machine

```text
DECLARED -> LAUNCHED -> RUNNING -> PROCESS_EXITED
-> CHECKPOINT_VALIDATED -> EVAL_RUNNING -> PASS | FAIL | INCONCLUSIVE
```

## Supervisor

```bash
python .ai/scripts/run_supervisor.py prepare ...
python .ai/scripts/run_supervisor.py launch --receipt <path>
python .ai/scripts/run_supervisor.py status --receipt <path>
python .ai/scripts/run_supervisor.py finalize --receipt <path> [--run-eval]
```

The supervisor writes receipts and pending events. It does not claim to revive an ended/disconnected Main turn; a later session reads pending events.

Process exit is not automatically a training pass. Checkpoint existence/readability、expected metrics、formal evaluator output and termination reason remain separate facts.
