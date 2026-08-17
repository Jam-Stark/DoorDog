# A2+Piper Pull-v5.6 Round Report

**Plan ID:** `a2_piper_pull_v5_6_terminal_hold_specialist_finetune`
**Execution date:** 2026-08-17 HKT
**Branch:** `codex/a2-piper-pull-v0-20260803`
**Final route:** `G9 × 3 -> G11` at T0 step-0
**Scientific verdict:** `INCONCLUSIVE` — the terminal-hold specialist was implemented and its warm start was validated, but no valid step-0 episode receipt was produced and no fine-tuning run started.

## 1. Executive outcome

Pull-v5.6 activated the authorized third and final ladder rung and added a terminal-only 12-leg HOMIE/A2 specialist without changing the original HOMIE asset, v5.5 sources, the pull actor, pull rewards/stages, thresholds, or the G8 bank. The eager actor reconstruction, fresh critic, fresh optimizer/scheduler contract, fresh exploration standard deviation, carrier injection, sampled/applied provenance, versioned gate schemas, and fail-closed orchestration all passed the bounded static/CPU validation wave.

The sole formal review wave returned `FAIL`. Its findings were repaired in a targeted revision, as required; no second formal review was run. The post-fix CPU/Hydra/synthetic acceptance passed, but runtime step-0 then exposed three successive missing root fields in the eval wrapper composition. The first two fields were repaired at their traceback root. The third and final allowed attempt reached IsaacSim startup and then failed on missing `multi_gpu` before constructing the task or producing `STEP0_GATE.json`.

The G9 retry budget was therefore exhausted. G11 closed the round without launching T1 training, rehearsal, anchor, door probes, P3/P4, dual-source evaluation, or render. These phases are `NOT_RUN`, not zero-success experiments. Canonical and natural `frame_passage` were not evaluated, so the stopping condition was not met.

This closure does **not** scientifically disprove the rung-3 specialist. It establishes an infrastructure blocker at the step-0 eval boundary. No rung 4 was invented. Any renewed rung-3 execution or task-level redesign requires a new planner decision.

## 2. Scope and immutable boundaries

| Surface | Result |
|---|---|
| Original HOMIE JIT | Immutable; still used for transit and step-0 baseline routing |
| Raw eager dog checkpoint | Read-only warm-start source |
| v5.5 task, trainer, configs, gates, and receipts | Unmodified |
| Pull actor, reward scales, stage topology, optimizer policy | Unmodified |
| Waypoint/yaw/K100 thresholds | Unmodified: `0.05 m`, `0.15 rad`, `100` steps |
| G8 state bank | Not rebuilt or rewritten |
| Protected evidence archive and projected traces | Preserved untracked; all 75 projected traces remain present |
| GPU use | Only physical GPU5 was selected for step-0; no process used GPU0–3 |

## 3. T0 implementation and static acceptance

The add-only implementation introduced:

- `pull_v5_6_hold_specialist` environment, eager actor/critic module, PPO trainer, and six Hydra configurations;
- a versioned fail-closed gate/analyzer for planner, warm start, step-0, checkpoint gates, rehearsal, anchor, and invariant 12-prime;
- an orchestration runner with explicit GPU4–7 restriction, checkpoint discovery, per-checkpoint 80-episode gates, selected-checkpoint aggregation, rehearsal/anchor aggregation, and prerequisite rejection;
- a versioned step-0 warm checkpoint and evidence-derived warm-start receipt.

Targeted validation after the formal findings:

| Check | Result |
|---|---|
| Python compilation of the five added Python modules | `PASS` |
| Six YAML parses and train/eval Hydra composition | `PASS` |
| Nine generated T0–T3 commands | `PASS` |
| Strict eager actor and fresh critic warm round-trip | `PASS` |
| Fresh std and max-std clamp | `PASS` |
| Gain-1 carrier fixture and sampled/applied split | `PASS` |
| Synthetic step-0/checkpoint/rehearsal/anchor producer-consumer schemas | `PASS` |
| Fail-closed `NOT_RUN` negative and invariant 12-prime fixtures | `PASS` |
| IsaacSim/GPU semantics before step-0 | `NOT_RUN` at this validation layer |

## 4. Warm-start receipt

Evidence: `logs_eval/a2_piper_pull_v5/v5_6_specialist_t0/WARM_START.json` and the versioned `model_step_000000.pt` under the v5.6 training namespace.

| Component | Actual result |
|---|---|
| Actor source | Strict reconstruction from the raw eager dog checkpoint |
| Actor observation/latent/action | `1620 -> 256 -> 128 -> 25`, then `1645 -> 512 -> 256 -> 128 -> 12` |
| Critic | Fresh, because the holdtrack route lacks the original privileged 25-D critic semantics |
| Optimizer | Fresh / absent from warm asset |
| Scheduler | Fresh / absent from warm asset |
| Source exploration std | Ignored |
| Resolved fresh std | `1.0` |
| Noise ceiling | `1.0` |
| Warm asset global step | `0` |
| Strict actor round-trip | `PASS` |
| Strict critic round-trip | `PASS` |

The deployed actor-only JIT was not treated as a trainable checkpoint. It remained the immutable original-leg route.

## 5. Sole formal review and targeted repairs

The single code-quality and IsaacLab review wave both returned `FAIL`. This verdict remains the formal review record. No second review was scheduled.

| Formal finding | Targeted disposition |
|---|---|
| Step-0 unsupported/non-executable and semantically capability-gating | Added exact 80-row full-distribution structural step-0 with specialist disabled; capability count is diagnostic only |
| Receipt schemas, paths, checkpoint provenance, and aggregation disagreed | Aligned versioned schemas/paths; added checkpoint step inference and phase-specific aggregation |
| Auto-reset could duplicate episodes | Restored returned-dones first-episode filtering and exact row counts |
| Prerequisite chain could bypass `NOT_RUN`; only final checkpoint was gated | Added fail-closed step-0 dependency and every-discovered-checkpoint gate matrix |
| Invariant 12-prime was disconnected/vacuous | Wired allowed/forbidden phase provenance and strict synthetic coverage |
| Warm receipt was literal | Replaced it with an actual strict eager load/round-trip and versioned warm asset |
| Noise ceiling ignored; mask comparison incorrect | Enforced std ceiling and fixed the mask comparison |
| Eval root config lacked wrapper-required fields | Runtime-targeted fixes added `experiment_dir` and `output_dir`; the final retry exposed a third missing field, `multi_gpu` |

Targeted fixes passed bounded static/CPU acceptance. They do not convert the formal verdict into reviewer `PASS`.

## 6. Step-0 runtime attempts

All attempts used the same registered 80-environment baseline command, specialist disabled, immutable original JIT route, GPU5, and the versioned warm asset. None produced a scientific row.

| G9 attempt | Runtime boundary reached | Traceback root | Receipt | Scientific count |
|---|---|---|---|---|
| 1 | Hydra eval composition | root `experiment_dir` absent under struct mode | absent | invalid / excluded |
| 2 | Hydra eval composition | root `output_dir` absent under struct mode | absent | invalid / excluded |
| 3 | IsaacSim startup, before task construction | root `multi_gpu` absent under struct mode | absent | invalid / excluded |

Blocked evidence is retained in:

- `logs_eval/a2_piper_pull_v5/v5_6_specialist_gate_step0/runner.log`
- `logs_eval/a2_piper_pull_v5/v5_6_specialist_gate_step0/runner_retry1.log`
- `logs_eval/a2_piper_pull_v5/v5_6_specialist_gate_step0/runner_retry2.log`

The registered family matrix is therefore:

| Phase | near_rest | coarse_neg | coarse_pos | straight_minus_x | side_step | Overall |
|---|---:|---:|---:|---:|---:|---:|
| Step-0 baseline | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |
| Step 250 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |
| Step 500 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |
| Step 750 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |

No training curve exists because T1 was never admitted.

## 7. Conditional phases

| Phase | Status | Reason |
|---|---|---|
| T1 specialist fine-tune | `NOT_RUN` | Missing valid step-0 receipt; fail-closed chain rejected launch |
| T1 checkpoint gates | `NOT_RUN` | No training checkpoints |
| Plateau option A/B | `NOT_RUN` | No valid 750-batch run to adjudicate |
| T2 rehearsal cells | `NOT_RUN` | No passing T1 checkpoint |
| T3 S1–S4 anchor | `NOT_RUN` | No rehearsal PASS; zero G3 attempts |
| Door closer buckets / G2 lattice | `NOT_RUN` | No admitted anchor sequence |
| P3/P4 | `NOT_RUN` | Door-side gate never reached |
| Canonical/natural dual-source eval | `NOT_RUN` | No P3/P4 checkpoint |
| Render | `NOT_RUN` | No eligible runtime receipt or episode |

No passage denominator exists in v5.6.

## 8. Invariant table

| Invariant | Status | Evidence boundary |
|---|---|---|
| 1–8 | `NOT_RUN` | Door/P3/P4/eval never launched |
| 9 reset-source isolation | `NOT_RUN` | No canonical or natural DV rows |
| 10 | `NOT_RUN` | No downstream terminal population |
| 11 canonical override/provenance | `NOT_RUN` | No canonical evaluation |
| 12-prime specialist provenance | static/synthetic `PASS`; runtime `NOT_RUN` | Validator rejects specialist attachment in P3/P4/DV and requires checkpoint/original-JIT provenance in allowed phases; no valid runtime row was produced |

There were no accepted rows from which to infer runtime invariant rates.

## 9. G1–G13 log

| Gate | Disposition |
|---|---|
| G1 | `NOT_RUN` — no door bucket probe |
| G2 | `NOT_RUN` — no all-zero admitted door probe |
| G3 | `NOT_RUN` — zero anchor attempts |
| G4 | `NOT_TRIGGERED` |
| G5 | `NOT_RUN` — no dual-source evaluation |
| G6 | `NOT_RUN` |
| G7 | `NOT_RUN` |
| G8 | `NOT_TRIGGERED`; existing bank preserved |
| G9 | `TRIGGERED × 3`; each traceback preserved and root-read; retry ceiling exhausted |
| G10 | `NOT_TRIGGERED` |
| G11 | `TRIGGERED`; minimum truthful closure after uncovered final-attempt step-0 infrastructure failure |
| G12 | `NOT_RUN` |
| G13 | `NOT_TRIGGERED`; bank was not rebuilt |

## 10. Final adjudication and next decision

- The authorized rung-3 implementation exists and its warm-start semantics are statically/CPU validated.
- Rung-3 locomotion capability is `INCONCLUSIVE`, not `FAIL`: no valid step-0, training, or held-out gate episode was recorded.
- The three-rung ladder reached its final rung operationally, but the final rung was not scientifically adjudicated. The first two rungs remain completed/failed under their own contracts.
- The current autonomous execution path is exhausted under G9/G11. The task returns to the planner; a future decision may either authorize a fresh v5.6 execution revision after completing the eval wrapper root schema or choose task-level redesign. It must not reinterpret this blocked run as passage zero or introduce an unapproved rung 4.
- The canonical-plus-natural reproducible `frame_passage` stopping condition remains unmet.
