# Pull-v5.6-r2 AI Handoff

**Handoff state:** `RESUME_REQUIRED_AFTER_MIGRATION`

**Prepared:** 2026-08-20 19:53 HKT

**Branch:** `codex/a2-piper-pull-v0-20260803`

**Plan ID:** `a2_piper_pull_v5_6_terminal_hold_specialist_finetune`

## 1. Mission and current truth

Continue the existing r2 execution. Do not open a new science revision and do not rerun or reinterpret accepted prerequisites.

Current evidence boundary:

- T0.5 root-schema repair: runtime PASS.
- T0.5 micro-smoke: PASS, 8 unique diagnostic rows.
- Exact step-0: PASS, 80 unique rows, 16 per family, diagnostic capability 0/80. By r2 contract this is non-gating and admits T1.
- T1 initial launch: infrastructure G9 after batch 1, before any checkpoint. The v5.6 subclass now forwards `workflow_config`; static validation passed.
- T1 retry: NOT_RUN because external GPU4-7 jobs held every authorized device, followed by the migration decision.
- Rehearsal, formal S1-S4 anchor, door probe, G2, P3/P4, dual-source evaluation, and render: NOT_RUN.
- Scientific stopping condition: not evaluated. There is no passage denominator and no valid zero-passage conclusion in r2.
- Sole v5.6 formal review: remains FAIL by contract. Do not claim a second review PASS.

The immediate job is therefore: restore and prove the destination runtime, then launch the unchanged T1 training contract.

## 2. Binding reading order

Read project memory first, then:

1. `scriptsFORhuman/pull_task/a2_piper_pull_v5_6_r2_execution_restart_addendum_20260817.md`
2. `scriptsFORhuman/pull_task/a2_piper_pull_v5_6_r2_worker_prompt_20260817.md`
3. `scriptsFORhuman/pull_v5/PULL_V5_6_R2_ROUND_REPORT.md`
4. `scriptsFORhuman/pull_v5/PULL_V5_6_R2_MIGRATION_AND_SETUP.md`
5. `memory/a2-piper/pull-open-door-task/description.md`
6. `memory/a2-piper/pull-open-door-task/TODO.md`

The r2 restart addendum governs execution semantics. Earlier v5.6 documents retain the scientific thresholds and contingency ladder where the r2 documents do not override them.

## 3. Immutable and protected boundaries

- Physical GPUs 4-7 only.
- Original HOMIE JIT and v4-B pull actor remain immutable.
- Warm asset and accepted source-host receipts are reused, never regenerated or overwritten.
- No reward-scale, stage-topology, threshold, optimizer-loading, or scientific-budget changes.
- `load_optimizer=false` remains explicit.
- Step-0 and other characterization rows remain outside scientific denominators.
- Specialist bridge is permitted only in registered holdtrack/rehearsal/formal positioning phases. It must be absent in P3/P4 and canonical/natural DV rows.
- Preserve exact reset-source provenance and invariant 9; canonical rows never enter natural-start DV.
- Infrastructure crashes use G9 without a numerical retry ceiling: read traceback, repair the actual root cause, retain failed logs, and retry. Do not convert blocked work to FAIL or zero.
- Do not modify the legacy root evidence ZIP or the 75 projected traces.

## 4. Destination bootstrap gate

Complete Sections 3-6 of `PULL_V5_6_R2_MIGRATION_AND_SETUP.md`. The required order is:

```text
clone exact branch/path
  -> extract top-level runtime archive at repository root
  -> install exact Isaac Sim / IsaacLab / Python stack
  -> static migration verifier PASS
  -> IsaacLab headless smoke PASS
  -> fresh 8-env migration micro-smoke PASS
  -> T1 launch
```

Do not rerun the 80-env step-0 after the migrated source-host receipt validates. It is already an accepted chain prerequisite. A fresh 8-env micro-smoke is sufficient to prove the new machine boundary.

## 5. T1 launch and checkpoint gates

### 5.1 Resource admission

Check GPU ownership once. If another user occupies the planned GPU, wait 600 seconds once, then use another free authorized GPU or serialize. Do not use GPU0-3. Long jobs run in independent tmux sessions.

### 5.2 Formal training

Run T1 on one free authorized GPU, preferably GPU4:

```bash
cd /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0
mkdir -p logs_rl/a2_piper_pull_v5_6_hold_specialist
tmux new-session -d -s pull_v5_6_specialist_train \
  "cd /home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0 && \
   /home/baoquanc/anaconda3/envs/isaaclab/bin/python \
   scriptsFORhuman/pull_v5/run_pull_v5_6_hold_specialist.py \
   --run --level train_only --gpu 4 \
   2>&1 | tee logs_rl/a2_piper_pull_v5_6_hold_specialist/r2_migrated_train_stdout_stderr.log"
```

Use the project wait discipline: short 30-second and 200-second checks to prove the process survives construction and the prior batch-1 boundary, then sleep to the first checkpoint estimate. The source-host first batch took about 5.3 seconds; use actual destination throughput to estimate the 250-batch boundary. Do not poll.

Expected outputs are `model_step_000250.pt`, `model_step_000500.pt`, and `model_step_000750.pt` under `logs_rl/a2_piper_pull_v5_6_hold_specialist/`.

### 5.3 Gate each checkpoint

As each checkpoint appears, use a separately leased authorized GPU, preferably GPU5:

```bash
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  scriptsFORhuman/pull_v5/run_pull_v5_6_hold_specialist.py \
  --run --level checkpoint_gate --gpu 5 \
  --checkpoint logs_rl/a2_piper_pull_v5_6_hold_specialist/model_step_000250.pt
```

Repeat for steps 500 and 750, then aggregate:

```bash
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  scriptsFORhuman/pull_v5/run_pull_v5_6_hold_specialist.py \
  --run --level aggregate_training
```

The same checkpoint must achieve at least 15/16 in each of five families and at least 77/80 overall. If no checkpoint passes, apply only the preregistered plateau option from the v5.6 contract. Do not invent a new curriculum or architecture rung.

## 6. Rehearsal and formal anchor

After a training gate PASS, run the two-cell rehearsal through the split runner levels so every cell and aggregate has its own receipt. Example for revision 0:

```bash
for cell in cell_-2.5 cell_+1.0; do
  /home/baoquanc/anaconda3/envs/isaaclab/bin/python \
    scriptsFORhuman/pull_v5/run_pull_v5_6_hold_specialist.py \
    --run --level rehearsal_cell --gpu 4 --rehearsal-cell "${cell}" --rehearsal-revision 0
done
/home/baoquanc/anaconda3/envs/isaaclab/bin/python \
  scriptsFORhuman/pull_v5/run_pull_v5_6_hold_specialist.py \
  --run --level aggregate_rehearsal --rehearsal-revision 0
```

Before consuming formal G3 attempt 0, run a separate two-environment seam diagnostic derived from `run_pull_v5_6_formal_probe.py` with a new diagnostic output directory. Its purpose is only to prove that the v4-B primary 12-D actor, the selected specialist leg policy, the `carrier12_legs12` action seam, and terminal-only masking construct and step correctly. Do not count it as an anchor attempt.

Once that seam is proven, execute S1-S4 with 16 rows per sequence. G3 admits at most three valid attempts. The thresholds remain 0.05 m, 0.15 rad, terminal-current K100, and 16/16 within an admitted sequence. Use the split `anchor_sequence` and `aggregate_anchor` levels so attempt 1/2 aggregates contain the contiguous history.

## 7. Conditional door and downstream chain

Only admitted anchor sequences proceed to the closer-bucket door probe. Use `run_pull_v5_6_formal_probe.py` for the explicit sequence/bucket cells and `pull_v5_6_downstream_gates.py` for fail-closed receipts. Any bucket/sequence passage greater than zero releases P3 under G1. An all-zero valid door probe invokes G2; interface infeasibility closes at the residual-policy decision boundary.

If G1 releases P3, launch the four cells together when four authorized GPUs are free:

| GPU | Cell | Injection ratio |
|---:|---|---:|
| 4 | M-s0 | 0.5 |
| 5 | M-s1 | 0.5 |
| 6 | C-s0 | 0.9 |
| 7 | C-s1 | 0.9 |

Use independent tmux sessions and the `run_pull_v5_6_downstream.py` command generator. Before the first P3 launch, treat the downstream stack as a runtime-unverified candidate: run its static matrix, inspect the generated P3 command against the binding v5/P3 configuration, and perform one bounded construction smoke. The existing checks prove composition and provenance contracts, not a completed IsaacSim P3 batch.

Evaluate every completed checkpoint with 16 canonical and 16 natural episodes. Canonical uses the explicit bank provider; natural uses Stage 0. Both keep training injection disabled during evaluation. Run invariant 12-prime and invariants 1-11 at receipt time. Apply G5/G6/G7/G12 exactly as preregistered; only one evidence-selected single-axis G7 fork is allowed.

## 8. Render and closure

After all applicable eval receipts exist, render representative rehearsal/anchor outcomes, each executed closer bucket, and final canonical/natural checkpoints. Put outputs under `logs_eval/a2_piper_pull_v5/render_v5_6_r2/`. A render pipeline failure gets one root-cause repair but does not alter a scientific gate.

Update the English round report in place. Replace migration-pause `NOT_RUN` entries only with actual receipts. Synchronize the pull memory and both long-term TODO levels, then make small `feat(a2)` commits and push the existing branch without force. The stopping condition is reproducible `frame_passage` from both canonical and natural starts; otherwise close truthfully at the applicable registered gate.

## 9. First-response checklist for the destination AI

1. State that this is the same r2 plan, not a new round.
2. Read memory and binding documents before editing or running.
3. Confirm the exact clone and conda paths.
4. Extract the root archive and run the static verifier.
5. Run one IsaacLab headless smoke and one fresh 8-env migration micro-smoke.
6. Confirm an authorized GPU lease; never preempt another process.
7. Launch T1 and survive the old batch-1 boundary before the first long sleep.
8. Keep every blocked attempt outside scientific denominators.
