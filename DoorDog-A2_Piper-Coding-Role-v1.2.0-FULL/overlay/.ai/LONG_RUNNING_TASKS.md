# Long-running task continuity

## Run contract

Before a run over 30 minutes, record:

```text
run name / tmux session
exact command
source revision and worktree
resolved config / checkpoint lineage
GPU, display, port and output leases
output/log paths
checkpoint expectation
stopping and cancellation conditions
optional follow-up eval
```

## State machine

```text
DECLARED -> LAUNCHED -> RUNNING -> PROCESS_EXITED
-> CHECKPOINT_VALIDATED -> EVAL_RUNNING -> PASS | FAIL | INCONCLUSIVE
```

Use named detached tmux and event-driven completion. Do not keep Main alive through repeated polling or very long reasoning turns.

## Supervisor

```bash
python .ai/scripts/run_supervisor.py prepare ...
python .ai/scripts/run_supervisor.py launch --receipt <path>
python .ai/scripts/run_supervisor.py status --receipt <path>
python .ai/scripts/run_supervisor.py finalize --receipt <path> [--run-eval]
```

The supervisor writes receipts and `.ai/runtime/pending-events/*.json`.

## Explicit limitation

An external tmux/process event cannot always revive an ended or disconnected Main turn. Pending events are durable and are injected/read on a later session start or resume. Runtime-specific app-server wake adapters may be added only after they are verified.

## Evidence

Process exit is not automatically a training pass. Checkpoint existence/readability、expected metrics、formal evaluator output and termination reason are separate facts.
