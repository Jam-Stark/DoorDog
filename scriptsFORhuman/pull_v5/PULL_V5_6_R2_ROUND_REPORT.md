# A2+Piper Pull-v5.6-r2 Round Report

**Plan ID:** `a2_piper_pull_v5_6_terminal_hold_specialist_finetune`  
**Execution window:** 2026-08-17 to 2026-08-20 HKT  
**Branch:** `codex/a2-piper-pull-v0-20260803`  
**Route:** consented `HIGH_RISK_PATH`  
**Current scientific disposition:** `IN_PROGRESS / MIGRATION_PAUSE`

## Technical summary

- The r1 closure was correctly reclassified as an infrastructure-blocked run. The r2 T0.5 chain reached Hydra composition, IsaacSim initialization, task construction, warm-checkpoint loading, completed first episodes, and a strict receipt validator.
- The final T0.5 micro-smoke passed with 8/8 unique diagnostic rows. The registered step-0 then passed structurally with 80/80 unique rows and 16 rows in each of five families. Its capability result was 0/80, but step-0 is explicitly diagnostic and outside the scientific denominator, so T1 was admitted.
- The first T1 launch completed one batch and then hit a new G9 execution fault: the v5.6 trainer subclass did not forward `workflow_config` to its base evidence writer. No checkpoint was produced. The narrow constructor-plumbing fix passed static validation; no retry was launched before migration.
- GPU4-7 remained occupied by external WeaveWAM jobs during the admitted retry windows. No external process was interrupted, attached, or shared. The user then selected migration to an idle host.
- The T1 retry and every conditional downstream phase are `NOT_RUN` at this snapshot. This document is a migration checkpoint, not a terminal scientific closure, and no unexecuted phase is interpreted as zero passage.

## 1. Scope, evidence grain, and immutable boundaries

The unit of evidence is a returned-`dones` first-episode terminal row identified by `env_id` and `episode_id`. T0.5 and step-0 rows are `interface_characterization` records with `scientific_denominator_included=false` and `denominator_scope=none`. T1 held-out gates use five registered families with 16 rows per family. Formal anchor, door, P3/P4, and dual-source denominators are reported only after their prerequisite receipts pass.

| Surface | r2 boundary |
|---|---|
| Original HOMIE JIT | Immutable and retained for transit/inactive specialist rows |
| v4-B pull actor | Immutable primary pull policy |
| Warm specialist asset and `WARM_START.json` | Reused from r1; not regenerated |
| Pull rewards, stages, optimizer policy, thresholds | Unchanged |
| G8 state bank | Preserved |
| Formal review | The sole v5.6 review remains `FAIL`; r2 opens no second formal review |
| Protected evidence ZIP and 75 projected traces | Preserved untracked and unmodified |
| GPU scope | Physical GPUs 4–7 only; dynamically leased around the concurrent distillation job |

## 2. T0.5 repaired the complete eval boundary

### 2.1 Root-schema enumeration

The r1 warm asset has no colocated `config.yaml`, so `eval_agent_trl.py` composes the current eval experiment and then performs root-level reads and writes under OmegaConf struct mode. r2 enumerated the entire executed root surface before retrying.

| Root field | Eval-wrapper use | Provision in r2 |
|---|---|---|
| `checkpoint`, `checkpoint_load_mode` | Checkpoint selection and load normalization | Existing CLI/base eval config |
| `eval_overrides` | Optional override merge | Explicit root `null` |
| `experiment_dir` | Rebound to `checkpoint.parent`, then read | Explicit eval root field |
| `output_dir` | AppLauncher output root | Explicit eval root field |
| `seed`, `num_envs`, `headless` | Runtime construction | Existing eval config/CLI |
| `simulator`, `env`, `algo`, `obs` | Task/trainer construction | Existing composition |
| `callbacks`, `trainer`, `wandb` | Evaluator construction and optional metadata | Existing composition |
| `eval_output_dir` | Receipt output | Existing CLI/config |
| `multi_gpu` | Unconditional struct assignment/read | Explicit `false` |
| `global_rank` | Conditional multiprocess assignment | Explicit `0` |

The wrapper intentionally set `experiment_dir` to the warm checkpoint parent. The primary schema repair was sufficient; the backup simulated training-run layout was not used.

### 2.2 Micro-smoke evidence

Evidence root: `logs_eval/a2_piper_pull_v5/v5_6_specialist_t0_5_micro_r2/`.

| Check | Result |
|---|---|
| Compose -> IsaacSim -> task -> warm load -> completed first episodes | `PASS` |
| Strict micro validator | `PASS` |
| Rows / unique env IDs | `8 / 8` |
| Specialist mounted | `false` |
| Original HOMIE provenance | present on all rows |
| Returned-dones binding | present on all rows |
| Scientific denominator | `false / none` |
| T1 prerequisite / launch eligibility | `false / false` by design |

Two failed diagnostic attempts were retained rather than converted to evidence: one used an incorrect 350-step evaluator horizon, and one exposed a producer/validator trace-schema mismatch. Both were G9 execution faults; neither entered a scientific denominator.

## 3. Exact-80 step-0 passed structurally

Evidence: `logs_eval/a2_piper_pull_v5/v5_6_specialist_gate_step0/STEP0_GATE.json`.

| Family | Rows | Diagnostic successes |
|---|---:|---:|
| `near_rest` | 16 | 0 |
| `coarse_neg` | 16 | 0 |
| `coarse_pos` | 16 | 0 |
| `straight_minus_x` | 16 | 0 |
| `side_step` | 16 | 0 |
| **Overall** | **80** | **0** |

All 80 `env_id` values were unique. Every row used the authoritative trace schema, original JIT provenance, returned-dones binding, and `scientific_denominator_included=false`. The 0/80 capability count is diagnostic-only under the r2 contract and did not block T1.

## 4. T1 specialist fine-tune and held-out gates

The registered training contract remains 256 environments, at most 750 batches, checkpoints every 250 batches, seed 0, curriculum defaults enabled, and `load_optimizer=false`.

### 4.1 G9 training startup repair

The first launch completed batch 1 in 5.30 seconds, then failed before any checkpoint because `PullV56HoldSpecialistPPOTrainer` had received no explicit `workflow_config`. The base trainer's evidence writer failed fast. Source tracing showed that `train_agent_trl.py` injects this object only for the exact base-trainer target, not subclasses. The v5.6 subclass now follows the proven v5.5 pattern: preserve a caller-supplied workflow config, otherwise forward its live config to the base class.

This attempt is infrastructure evidence only. It contributes no training checkpoint or held-out episode.

### 4.2 Checkpoint gate matrix

| Checkpoint | near_rest | coarse_neg | coarse_pos | straight_minus_x | side_step | Overall | Adjudication |
|---|---:|---:|---:|---:|---:|---:|---|
| Step 250 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Migration pause before checkpoint creation |
| Step 500 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Migration pause before checkpoint creation |
| Step 750 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Migration pause before checkpoint creation |

Registered PASS requires at least 15/16 in every family and at least 77/80 overall at the same checkpoint.

## 5. Rehearsal and formal S1-S4 anchor

| Phase | Receipt | Result |
|---|---|---|
| Rehearsal yaw -2.5 | versioned two-cell aggregate | `NOT_RUN` |
| Rehearsal yaw +1.0 | versioned two-cell aggregate | `NOT_RUN` |
| Formal anchor attempt 0 | S1-S4, 16 rows each | `NOT_RUN` |
| Formal anchor attempt 1 | conditional | `NOT_RUN` |
| Formal anchor attempt 2 | conditional | `NOT_RUN` |

The formal anchor is distinct from holdtrack characterization. It keeps v4-B as the primary pull actor and mounts the selected specialist only as a deterministic secondary 12-D leg policy during terminal positioning. Transit rows retain original HOMIE legs. PASS remains terminal-current K100 at 0.05 m and 0.15 rad, with 16/16 rows per admitted sequence and a maximum of three valid attempts.

## 6. Conditional door, P3/P4, and dual-source evaluation

| Phase | Result |
|---|---|
| Door closer bucket 2.5-5 | `NOT_RUN` |
| Door closer bucket 5-9 | `NOT_RUN` |
| Door closer bucket 9-12 | `NOT_RUN` |
| G2 lattice, if required | `NOT_RUN` |
| P3 M-s0 / M-s1 / C-s0 / C-s1 | `NOT_RUN` |
| Canonical 16 + natural 16 per checkpoint | `NOT_RUN` |
| Conditional P4 and corresponding eval | `NOT_RUN` |

Specialist provenance is legal only for formal anchor and door positioning. P3, P4, canonical DV, and natural DV must assert that the specialist bridge is not mounted and must record `hold_specialist_active=false` with null specialist checkpoint provenance.

## 7. Evidence-quality and invariant audit

| Check | Current status |
|---|---|
| Micro row count and unique env IDs | `PASS` (8/8) |
| Step-0 row count and unique env IDs | `PASS` (80/80) |
| Step-0 family balance | `PASS` (16 each) |
| Trace schema consistency | `PASS` for admitted T0.5/step-0 receipts |
| Returned-dones first-episode binding | `PASS` for admitted T0.5/step-0 receipts |
| Diagnostic/scientific denominator isolation | `PASS` for T0.5/step-0 |
| Invariants 1-11 | `NOT_RUN` at conditional downstream boundary |
| Invariant 12-prime | Runtime `PASS` for specialist-disabled T0.5/step-0; downstream `NOT_RUN` |

## 8. Render index

| Episode class | Artifact | Status |
|---|---|---|
| Rehearsal PASS/FAIL representatives | - | `NOT_RUN` |
| Formal anchor PASS/FAIL representatives | - | `NOT_RUN` |
| Executed door buckets | - | `NOT_RUN` |
| Final canonical/natural DV | - | `NOT_RUN` |

Render is evidence-only and does not change any gate.

## 9. G1-G13 execution log

| Gate | r2 disposition |
|---|---|
| G1 | `NOT_REACHED` |
| G2 | `NOT_REACHED` |
| G3 | `NOT_REACHED` |
| G4 | `NOT_TRIGGERED` to date |
| G5 | `NOT_REACHED` |
| G6 | `NOT_REACHED` |
| G7 | `NOT_REACHED` |
| G8 | Existing bank preserved; no downgrade triggered to date |
| G9 | Triggered for T0.5 horizon, trace-schema alignment, and T1 workflow-config plumbing; blocked logs retained |
| G10 | `NOT_TRIGGERED` to date |
| G11 | `NOT_TRIGGERED`; migration pause preserves the active r2 chain |
| G12 | `NOT_REACHED` |
| G13 | Existing admissible bank reused |

## 10. Migration adjudication and durable conclusions

This is an `IN_PROGRESS / MIGRATION_PAUSE` snapshot. T0.5 and exact-80 step-0 are admitted runtime prerequisites. Step-0's 0/80 capability count remains diagnostic-only. The workflow-config repair is static-only until the migrated T1 process survives the former batch-1 boundary and emits a checkpoint. No G11 scientific closure is taken, and the r2 dependency chain resumes unchanged on the destination host.

## 11. Migration package and successor instructions

The top-level `a2_piper_pull_v5_6_r2_runtime_assets_20260820.zip` carries 16 ignored runtime assets with repository-relative paths: the warm specialist asset and receipt, T0.5/step-0 evidence, v4-B checkpoint/config, the G8 bank/manifest/receipt, planner reference evidence, and the first T1 G9 log. It excludes the protected legacy evidence archive and 75 projected traces.

Environment and restore instructions are in `scriptsFORhuman/pull_v5/PULL_V5_6_R2_MIGRATION_AND_SETUP.md`. The continuation DAG, launch commands, immutable boundaries, and reporting rules are in `scriptsFORhuman/pull_v5/PULL_V5_6_R2_AI_HANDOFF.md`.
