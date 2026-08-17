# A2+Piper Pull-v5.5 Round Report

**Plan ID:** `a2_piper_pull_v5_5_residual_terminal_hold_adapter`
**Execution date:** 2026-08-17 HKT
**Branch:** `codex/a2-piper-pull-v0-20260803`
**Frozen low-level controller:** A2_Base/HOMIE, unchanged
**Final round verdict:** `T1_ADAPTER_GATE_FAIL / G11_CLOSED / RETURN_TO_PLANNER`

## 1. Executive verdict

Pull-v5.5 implemented and exercised the second rung of the registered terminal-yaw architecture ladder: a three-axis residual terminal-hold adapter above the frozen A2_Base/HOMIE controller. The adapter task was executable end to end, used a real PPO lifecycle, generated checkpoints, loaded them through the evaluator, and produced five-family held-out receipts. The final corrected 750-batch run completed without a runtime error.

The T1 admission gate did not pass. The initial complete run produced zero registered K100 completions at steps 250, 500, and 750. The single permitted plateau option was then used as an evidence-directed target-offset curriculum followed by one from-scratch 750-batch retrain. After two retained G9-invalid attempts exposed and repaired PPO action-provenance defects, the final r13 retrain produced one valid `near_rest` K100 completion at step500, but no other family completion; step750 returned to zero completions. No checkpoint approached the registered requirement of at least 15/16 per family and 77/80 overall.

The durable result is therefore scoped: the preregistered v5.5 adapter, training budget, and one allowed curriculum extension failed T1 admission. This does not prove that every possible residual controller is impossible. It does require a return to the planner. HOMIE fine-tuning is the third ladder rung and was not authorized or started by this worker.

T2 rehearsal, formal T3 S1-S4 anchor, door-side probes, G2, P3, P4, dual-source evaluation, and render all remained fail-closed `NOT_RUN`. They are not passage zeros. No v5.5 scientific door population exists, and the canonical-and-natural `frame_passage` stopping condition remains unmet.

## 2. Planner decision and fail-closed chain

The planner artifact is `logs_eval/a2_piper_pull_v5/v5_5_planner_architecture_decision.json`.

| Field | Recorded decision |
|---|---|
| Architecture | `ACTIVATE_RESIDUAL_TERMINAL_HOLD_ADAPTER` |
| Ladder rung | 2 |
| Observation / trainable action | 12 / 3 |
| High-level carrier / frozen legs | 12 / 12 |
| Scientific denominator | excluded |
| Fine-tune | deferred and unauthorized |

The executable admission chain was:

`planner artifact -> T1 training gate PASS -> T2 rehearsal PASS -> formal T3 anchor PASS -> door/P3/P4`

The final T1 receipt is `logs_eval/a2_piper_pull_v5/v5_5_adapter_gate/TRAINING_GATE.json`. It is `FAIL`, so every later launch boundary remained closed.

## 3. Adapter task and frozen contract

### 3.1 Task surface

| Contract | Implementation |
|---|---|
| Fixture | open field, no door asset |
| Reset yaw | approximately pi, matching the anchor/bank orientation |
| Prelude families | `near_rest`, `coarse_neg`, `coarse_pos`, `straight_minus_x`, `side_step` |
| Handoff goal | measured current pose plus sampled body-frame XY/yaw offset |
| Observation | goal error 3 + planar velocity 2 + yaw rate 1 + gravity 3 + last action 3 = 12 |
| Trainable action | bounded XY/yaw = 3 dimensions |
| Carrier | adapter in indices 0:3, deterministic zeros in 3:11, open gripper at 11 |
| Low-level action | 12 frozen A2_Base leg actions under `no_grad` |
| Entry / hold budget | first tolerance entry by 250 active steps; K100 current-state hold; 350 active steps total |
| Immutable success threshold | XY <= 0.05 m and absolute yaw <= 0.15 rad |
| Row class | `interface_characterization`; `scientific_denominator_included=false`; `denominator_scope=none` |

The final trainer stores sampled policy carriers separately from the applied carrier. Scripted prelude and the one-step handoff transition are excluded from the policy/entropy denominator, while the critic retains the complete trajectory. Environment execution and frozen-leg inference continue to consume the applied carrier.

### 3.2 Adapter-only reward table

No existing pull-task reward, scale, stage topology, checkpoint, or optimizer policy was changed.

| Term | Raw meaning | Scale |
|---|---|---:|
| `adapter_dense_error` | negative normalized XY plus yaw error | 1.00 |
| `adapter_in_tolerance` | current-state dual-threshold bonus | 0.25 |
| `adapter_hold_progress` | K100 progress | 0.50 |
| `adapter_done` | registered terminal completion | 4.00 |
| `penalty_adapter_action_delta` | action change-rate penalty | -0.01 |

There is no action-magnitude penalty; high-amplitude dead-zone-crossing commands remain admissible.

### 3.3 Sole plateau curriculum

The first complete run had identical zero-completion receipts at steps500 and750 and no evidence that continuation alone would improve admission. The one allowed plateau option was therefore a single target-offset curriculum, not a reward change:

| Global simulator steps | Tier | Radius maximum | Yaw maximum |
|---:|---|---:|---:|
| 0-15,999 | small | 0.10 m | 0.15 rad |
| 16,000-31,999 | medium | 0.25 m | 0.30 rad |
| 32,000 onward | full | 0.50 m | 0.60 rad |

This curriculum applies only to `adapter_probe_phase=train`. Every training gate used the registered full 0.50 m / 0.60 rad distribution, recorded `adapter_target_source=training_gate_registered_full`, and never used the easier curriculum distribution.

## 4. Sole formal review and targeted acceptance

The one permitted formal review wave returned `FAIL`; no second formal review was run. The historical verdict remains `FAIL`. Targeted fixes and runtime evidence are not described as reviewer PASS.

| Formal finding / runtime defect | Targeted disposition |
|---|---|
| Initial trainer was not a real PPO lifecycle | Custom trainer now subclasses the established A2 PPO trainer and does not replace `train()` |
| Frozen A2_Base composition was absent | Existing loader/composer and 1620-D A2 observation path are used; leg inference is frozen |
| Dense reward sign was inverted | Negative raw error now has a positive scale |
| Prelude, handoff, and active budget semantics were wrong | Current-pose handoff, one scripted transition, active-only reward/counters, and phase-relative 350-step budget implemented |
| Gate criteria and fail-closed chain were incomplete | Executable 80-episode gate, two-cell rehearsal, runner chain, and nonzero-coverage invariant checks implemented |
| Bounded action inverse could diverge at endpoints | One shared representable tanh margin now owns sampling and inverse recovery |
| Eval-only Hydra composition and wrapper schema were incomplete | Dedicated eval exp and required non-operative wrapper keys added |
| Stored-action surprisal overwrote current entropy | Entropy state was separated from stored-action likelihood |
| PPO treated scripted applied carriers as sampled policy actions | Sampled/applied provenance split and inactive policy masking implemented in r13 |

Static acceptance included one changed-file compile pass per targeted revision, YAML/Hydra composition, generated command checks, CPU action-bound/log-probability fixtures, curriculum boundary fixtures, and sampled/applied storage-mask fixtures. Runtime acceptance is the completed r13 training/evaluation sequence below.

## 5. G9 runtime ledger

Invalid and blocked attempts were retained and excluded from the final capability adjudication.

| Candidate | Outcome | Root cause and disposition |
|---|---|---|
| initial smoke | BLOCKED | Trainer expected `workflow_config`; custom constructor now forwards the real config |
| first formal candidate | IMPLEMENTATION-INVALID | Unbounded likelihood state produced exploding entropy; retained, not used for capability |
| r9 | IMPLEMENTATION-INVALID | Noise ceiling alone did not fix bounded-action inverse mismatch |
| r10 initial complete run | COMPLETE diagnostic | Shared tanh margin made 750 batches finite; all three gates were 0/80, triggering the one plateau option |
| plateau r11 | G9 INVALID at batch366 | PPO actor mean became NaN; stored-action surprisal was incorrectly used as entropy |
| plateau r12 | G9 INVALID at batch230 | Stable entropy was insufficient; scripted applied actions still entered PPO likelihood ratios |
| plateau r13 | VALID final run | Sampled/applied action provenance and inactive masking fixed; 750/750 batches completed in 3820.53 s |

The r11 and r12 tracebacks are implementation evidence, not zero-completion gate rows. Neither consumed an additional plateau option or a downstream scientific count.

## 6. T1 gate results

### 6.1 Initial complete run

The r10 run completed 750 batches in 3713.83 s. It was the evidence used to choose the single plateau curriculum. A later runtime defect showed that its PPO likelihood still mixed scripted and policy actions, so its receipts are retained as implementation diagnostics rather than the final adapter capability result.

| Checkpoint | Overall DONE | XY min / mean (m) | Yaw min / mean (rad) | Gate |
|---:|---:|---:|---:|---|
| 250 | 0/80 | 0.02698 / 0.35688 | 1.72448 / 2.40111 | FAIL |
| 500 | 0/80 | 0.02729 / 0.35707 | 1.72430 / 2.40109 | FAIL |
| 750 | 0/80 | 0.02729 / 0.35707 | 1.72430 / 2.40109 | FAIL |

### 6.2 Final corrected plateau run

| Checkpoint | near_rest | coarse_neg | coarse_pos | straight_minus_x | side_step | Overall | XY min / mean (m) | Yaw min / mean (rad) | Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 250 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/80 | 0.06900 / 0.32254 | 0.00086 / 0.17069 | FAIL |
| 500 | 1/16 | 0/16 | 0/16 | 0/16 | 0/16 | 1/80 | 0.03968 / 0.32624 | 0.00021 / 0.16704 | FAIL |
| 750 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/80 | 0.04284 / 0.39094 | 0.01023 / 1.03139 | FAIL |

The sole positive terminal row was `near_rest`, step500, env15. It was a first-episode row joined to `env.step` returned dones with `terminal_current_state=true`, `terminal_hold_steps=100`, XY error `0.0396828391 m`, and yaw error `0.0298886299 rad`. It is real interface-characterization evidence, but one success cannot satisfy the preregistered family or overall gate. Its disappearance at step750 is also retained rather than selecting a favorable endpoint without meeting the gate.

No checkpoint was frozen as an admitted adapter asset.

## 7. T2, T3, and conditional downstream

| Phase | Registered requirement | v5.5 result | Reason |
|---|---|---|---|
| T2 rehearsal cell A | -2.5 rad + 0.3 m, 8/8 K100 DONE | `NOT_RUN` | T1 gate did not pass |
| T2 rehearsal cell B | +1.0 rad + 0.3 m, 8/8 K100 DONE | `NOT_RUN` | T1 gate did not pass |
| Formal T3 S1-S4 | any sequence 16/16 under 0.05 m / 0.15 rad | `NOT_RUN` | No rehearsal PASS; zero G3 attempts consumed |
| Door closer buckets | admitted sequences, three buckets | `NOT_RUN` | No formal anchor admission |
| G2 lattice | valid all-zero door probe only | `NOT_RUN` | No door probe exists |
| P3 2x2 | four 256-env x 250-batch cells | `NOT_RUN` | G1 not reached |
| P4 | conditional continuation/annealing | `NOT_RUN` | No P3 adjudication |
| Dual-source eval | canonical 16 + natural 16 per checkpoint | `NOT_RUN` | No eligible P3/P4 checkpoint |

The add-only adapter task contains characterization-only anchor targets for harness validation. They explicitly carry `formal_t3_anchor_admission=false` and were never used as the authoritative S1-S4 gate.

## 8. Twelve-invariant audit

T1 rows are interface characterization and cannot promote door-task invariants to runtime PASS.

| # | Invariant | v5.5 verdict | Evidence |
|---:|---|---|---|
| 1 | `fake_e4` | `NOT_RUN` | No scientific door episode |
| 2 | `stage4_snapshot_below_hinge_gate` | `NOT_RUN` | No scientific door episode |
| 3 | `dont_push_before_true_stage3_to4` | `NOT_RUN` | No scientific door episode |
| 4 | `target_root_before_aperture_ready` | `NOT_RUN` | No scientific door episode |
| 5 | `corridor_active_before_aperture_ready` | `NOT_RUN` | No scientific door episode |
| 6 | `complete_without_frame_passage` | `NOT_RUN` | No scientific door episode |
| 7 | `frame_approach_active_before_aperture_ready` | `NOT_RUN` | No scientific door episode |
| 8 | `frame_approach_active_after_frame_passage` | `NOT_RUN` | No scientific door episode |
| 9 | Canonical episodes never count as natural-start DV | `NOT_RUN` | No canonical/natural DV population |
| 10 | Failed-settle rows never enter the bank | inherited v5.1 PASS | The 191-row G8 bank was not rebuilt, modified, or loaded by T1 |
| 11 | Canonical override only in canonical first 50 steps; never natural | `NOT_RUN` | No dual-source episode |
| 12 | Adapter absent from P3/P4 actions and every DV row | `NOT_RUN` with fail-closed static boundary | P3/P4/DV did not launch; there is no runtime population on which to claim PASS |

Additional T1 runtime checks passed: all final gate receipts contained exactly 80 first-episode rows; every row used the full registered gate target envelope; every row was denominator-excluded; checkpoint path and step were present; and the one DONE row was bound to returned dones and K100 current-state retention.

## 9. Render index

| Requested class | Eligible episode | Render state | Reason |
|---|---|---|---|
| Rehearsal PASS/FAIL | None | `NOT_RUN_BY_FAIL_CLOSED_GATE` | T2 did not run |
| Formal anchor PASS/FAIL | None | `NOT_RUN_BY_FAIL_CLOSED_GATE` | T3 did not run |
| Door closer buckets | None | `NOT_RUN_BY_FAIL_CLOSED_GATE` | Door probe did not run |
| Final canonical/natural checkpoint | None | `NOT_RUN_BY_FAIL_CLOSED_GATE` | P3/P4/DV did not run |

Training-gate rows are not eligible rehearsal, anchor, door, or final-policy render classes. No video was fabricated or relabeled. The machine-readable render status is `logs_eval/a2_piper_pull_v5/render_v5_5/RENDER_STATUS.json`.

## 10. G1-G13 decision log

| Gate | v5.5 state | Evidence-backed action |
|---|---|---|
| G1 | `NOT_RUN` | No admitted anchor or door-bucket passage receipt |
| G2 | `NOT_RUN` | No valid all-zero door probe exists |
| G3 | `NOT_RUN` | Zero formal anchor attempts consumed |
| G4 | inherited confirmed | v5.1 P2 selected release persistence; not a v5.5 traversal result |
| G5 | `NOT_RUN` | No P3 canonical result |
| G6 | `NOT_RUN` | No canonical-positive/natural-zero result |
| G7 | `NOT_RUN` | No P3 all-zero result |
| G8 | inherited available | The 191-row pure-A bank remained untouched |
| G9 | triggered and closed | Two plateau training crashes were retained; r13 fixed sampled/applied provenance and completed 750 batches |
| G10 | PASS for executed T1 jobs | Authorized GPU4 ran training and GPU5 ran concurrent checkpoint gates; GPU0-3 were not used |
| G11 | invoked | Final T1 gate FAIL after the sole plateau option; truthful report/memory/TODO closure and return to planner |
| G12 | `NOT_RUN` | No C-arm natural-start comparison |
| G13 | inherited `PASS_G8_PURE_A` | Bank was not rebuilt or injected |

## 11. Artifact index and protected state

| Artifact | Path / state |
|---|---|
| Binding addendum | `scriptsFORhuman/pull_task/a2_piper_pull_v5_5_residual_adapter_addendum_20260817.md` |
| Planner decision | `logs_eval/a2_piper_pull_v5/v5_5_planner_architecture_decision.json` |
| Initial corrected training | `logs_rl/a2_piper_pull_v5_5_adapter_r10/` |
| Final corrected plateau training | `logs_rl/a2_piper_pull_v5_5_adapter_plateau_curriculum_r13/` |
| Initial gates | `logs_eval/a2_piper_pull_v5/v5_5_adapter_r10_gate_step{250,500,750}/` |
| Final plateau gates | `logs_eval/a2_piper_pull_v5/v5_5_adapter_plateau_r13_gate_step{250,500,750}/` |
| Final fail-closed gate receipt | `logs_eval/a2_piper_pull_v5/v5_5_adapter_gate/TRAINING_GATE.json` |
| Invalid G9 attempts | retained in `pull_v5_5_adapter_plateau_curriculum/` and `_r12/`; excluded from capability counts |
| Render status | `logs_eval/a2_piper_pull_v5/render_v5_5/RENDER_STATUS.json` |

The root evidence ZIP and all 75 projected traces remained untracked and unmodified. No hash was computed or written. The G8 bank was not rebuilt or changed.

## 12. Final disposition

Pull-v5.5 reached a valid architecture-level negative result at T1. The corrected adapter could occasionally complete K100 in the easiest family, but it did not generalize across the registered full-range distribution and degraded again by step750. The one permitted plateau adjustment was consumed, so additional continuation, reward tuning, or multi-axis search would violate the preregistered round.

The round closes under G11 and returns to the planner. The next planner may decide whether the ladder's third rung, HOMIE fine-tuning, should be authorized, or whether a differently scoped residual architecture is warranted. This worker made neither decision. The frame-passage stopping condition was not reached.
