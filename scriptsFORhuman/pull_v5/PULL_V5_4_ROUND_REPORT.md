# A2+Piper Pull-v5.4 Round Report

**Plan ID:** `a2_piper_pull_v5_4_terminal_yaw_scheduler`  
**Execution date:** 2026-08-16 HKT  
**Branch:** `codex/a2-piper-pull-v0-20260803`  
**Warm actor:** v4-B seed1 step750  
**Final round verdict:** `STAGE_B_REHEARSAL_FAIL / G11_CLOSED`

## 1. Executive verdict

Pull-v5.4 completed its CPU feasibility study and one fail-closed GPU4 scheduler rehearsal. Stage A returned `GO`: 44 accepted v5.3 traces (352 per-environment trajectories and 75,200 step rows) contained 24 preregistered A4 candidates, including 12 with a positive raw command. The selected fallback was `pure_yaw_p0p05_T4`; its raw command was positive (`+0.05`) although the realized command-window yaw was negative.

Stage B did not pass. The sole evidence-allowed shared correction, `-0.3672668933868408 rad`, reduced both corrected-target populations below the immutable `0.15 rad` numerical yaw-error threshold, but all 16 corrected rows exhausted the 200-step trim cap. Every corrected row ended in scheduler state `FAILED`, with `terminal_current_state=false` and `terminal_hold_steps=0`. Therefore numerical proximity did not qualify as scheduler completion, rehearsal admission failed, and no G3 anchor attempt was consumed.

The addendum's second architecture rung is now active: the next admissible architecture is a residual terminal-hold adapter under a separately issued v5.5 planner contract. This worker did not start residual training. HOMIE fine-tuning remains deferred unless that residual route is disproved.

No door probe, G2 lattice, P3, P4, dual-source evaluation, or eligible render class ran. These phases are `NOT_RUN`, not zero passage. The canonical-and-natural `frame_passage` stopping condition remains unmet.

## 2. Planner decision and fail-closed topology

The planner artifact is `logs_eval/a2_piper_pull_v5/v5_4_planner_architecture_decision.json`. It records:

| Field | Value |
|---|---|
| Decision | `MODEL_BASED_SCHEDULER_FIRST` |
| Residual precommit | `true` |
| Fine-tune deferred | `true` |
| Scientific denominator | `false` |
| Prior adjudication | immutable v5.3 H-D/G11 decision |

The implemented admission chain is:

`planner artifact -> Stage A GO -> Stage B rehearsal PASS -> G3 anchor PASS -> door/P3/P4`

Stage B produced a valid `FAIL`, so every later entry point remained fail-closed.

## 3. Stage A feasibility study

### 3.1 Input inventory and preregistration replay

| Population | Count |
|---|---:|
| Accepted traces | 44 |
| Pure-yaw traces | 36 |
| Coupling traces | 8 |
| Environments per trace | 8 |
| Per-environment trajectories | 352 |
| Step rows | 75,200 |
| Prior anchor receipts | 3 |
| Anchor measurements | 192 |
| Control interval | 0.02 s |

The analysis ignored the stale v5.3 `terminal_after_step` column and recomputed the registered quantities from accepted trace fields. A4 was fixed before the data were evaluated:

1. dispersion plus A2 stability `<= 0.10 rad`;
2. maximum settle time `<= 2.0 s`;
3. maximum hold XY `<= 0.03 m`, or the preregistered A3 concentration condition;
4. at least one passing pure-yaw cell yields `GO`.

All extrema used per-environment worst cases rather than replacing them with means.

### 3.2 A3 causal check

| Statistic | Measured | Registered requirement | Result |
|---|---:|---:|---|
| Point-biserial correlation | -0.0333509695 | >= 0.30 | FAIL |
| Median miss-minus-hit absolute-yaw gap | -0.0295476913 rad | >= 0.05 rad | FAIL |
| A3 concentration | false | both conditions | FAIL |

Waypoint misses were not concentrated at high yaw error under the preregistered rule. Consequently, candidates had to pass the direct XY branch.

### 3.3 A4 selected candidate and measured extrema

Stage A found 24 passing candidates, including 12 positive-raw candidates. None of the preferred high-magnitude positive candidates passed the direct XY constraint, so the registered positive-margin fallback selected `pure_yaw_p0p05_T4`.

| Quantity | Per-environment evidence |
|---|---:|
| Raw command | `+0.05` |
| Command-window yaw min / median / max | -0.1330423991 / -0.1238620917 / -0.0987139384 rad |
| Realized direction | negative |
| Median stop drift | -0.0004932880 rad |
| Maximum settle time | 0.0 s |
| Maximum A2 stability | 0.0004696846 rad |
| Maximum hold XY | 0.0004342895 m |
| Dispersion plus stability | 0.0007834435 rad |
| A4 verdict | `GO` |

For the two coarse profiles used by the scheduler model:

| Cell | Raw | Command-window yaw min / median / max (rad) | Median stop drift (rad) | Max settle (s) | Max stability (rad) | Max hold XY (m) |
|---|---:|---:|---:|---:|---:|---:|
| `pure_yaw_m2_T4` | -2.0 | -1.8743770758 / -1.8542257587 / -1.8333576361 | -0.2168513536 | 1.12 | 0.0124869347 | 0.0429290767 |
| `pure_yaw_p2_T4` | +2.0 | 1.6934463978 / 1.7147439718 / 1.7407058477 | 0.0390889645 | 1.06 | 0.0048334599 | 0.0363753223 |

The machine-readable receipt is `scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json`.

## 4. Frozen scheduler constants

All 21 constants below are copied from `scheduler_derived.constants`; each source is an actual JSONPath in the Stage A receipt.

| Constant | Value | Source JSONPath |
|---|---:|---|
| `dt_s` | 0.02 | `$.preregistration.constants.control_dt_s` |
| `settle_velocity_threshold_rad_s` | 0.05 | `$.preregistration.constants.velocity_settle_threshold_rad_s` |
| `planning_a_rad` | 0.10 | `$.preregistration.constants.a4_rad_budget` |
| `b_trim_rad` | 0.22435537973512823 | `$.preregistration.constants.b_trim_rad` |
| `coarse_raw_negative` | -2.0 | `$.a1_stop_profile.cells.pure_yaw_m2_T4.requested_u` |
| `coarse_raw_positive` | 2.0 | `$.a1_stop_profile.cells.pure_yaw_p2_T4.requested_u` |
| `coarse_rate_negative_rad_s` | -0.463556439676557 | `$.a1_stop_profile.cells.pure_yaw_m2_T4.summaries.command_window_yaw_rad.median` |
| `coarse_rate_positive_rad_s` | 0.4286859929561615 | `$.a1_stop_profile.cells.pure_yaw_p2_T4.summaries.command_window_yaw_rad.median` |
| `coarse_stop_drift_negative_rad` | -0.2168513536453247 | `$.a1_stop_profile.cells.pure_yaw_m2_T4.median_stop_drift_rad` |
| `coarse_stop_drift_positive_rad` | 0.03908896446228027 | `$.a1_stop_profile.cells.pure_yaw_p2_T4.median_stop_drift_rad` |
| `coarse_cutoff_negative_e_rad` | -0.4412067333804529 | `$.preregistration.constants.coarse_cutoff_negative_e_rad` |
| `coarse_cutoff_positive_e_rad` | -0.18526641527284796 | `$.preregistration.constants.coarse_cutoff_positive_e_rad` |
| `minimum_settle_steps_negative` | 56 | `$.a1_stop_profile.cells.pure_yaw_m2_T4.per_env[*].last_above_threshold_hold_index` |
| `minimum_settle_steps_positive` | 53 | `$.a1_stop_profile.cells.pure_yaw_p2_T4.per_env[*].last_above_threshold_hold_index` |
| `settle_deadline_steps` | 100 | `$.a1_stop_profile.cells.pure_yaw_m2_T4.hold_steps` |
| `terminal_hold_steps` | 100 | `$.a1_stop_profile.cells.pure_yaw_m2_T4.hold_steps` |
| `trim_raw` | 0.05 | `$.a1_stop_profile.cells.pure_yaw_p0p05_T4.requested_u` |
| `trim_realized_rate_rad_s` | -0.030965522923741773 | `$.a1_stop_profile.cells.pure_yaw_p0p05_T4.summaries.command_window_yaw_rad.median` |
| `trim_one_step_rad` | -0.0006193104584748354 | `$.scheduler_derived.constants.trim_realized_rate_rad_s.value` |
| `trim_stop_drift_rad` | -0.0004932880401611328 | `$.a1_stop_profile.cells.pure_yaw_p0p05_T4.median_stop_drift_rad` |
| `trim_step_cap` | 200 | `$.preregistration.constants.trim_step_cap` |

## 5. Sole formal review and targeted acceptance

The one permitted formal review wave returned `FAIL`; no second formal review was run. The review findings and bounded repairs were:

| Finding | Targeted repair / acceptance |
|---|---|
| Raw Stage A commands were divided by the action scale a second time | Scheduler now writes measured raw `-2`, `+2`, and `+0.05` directly to probe-side `applied[:,2]` |
| Settle and terminal timing did not match the measured contract | Settle reads world-frame root yaw velocity, requires full measured 56/53 zero-command steps, uses the exact 100-step deadline, and does not trim in the same step |
| Terminal rows could use pre-step termination state | Post-step returned dones now own terminal joins and episode indexing |
| Shared correction and target provenance were ambiguous | Original and planning targets are separate; only the median of all 16 attempt-0 rows forms one shared correction |
| Rehearsal PASS was under-specified | PASS requires scheduler `DONE`, terminal-current state, 100 hold steps, first episode, returned done, and the unchanged error threshold |
| Scheduler constants were not completely traceable | All 21 constants now carry real Stage A source JSONPaths |
| Downstream provenance was not fully bound | Current G1/G2 artifact provenance gates P3/T4; anchor paths are attempt-specific |
| Long-run launch commands were placeholders | P3/P4 generation uses real independent tmux sessions and output tee paths |

Subsequent static acceptance included one changed-file compile pass, Stage A regeneration, the Stage A gate, Hydra compose-only routes, CPU scheduler/settle/terminal/correction fixtures, provenance admission, and tmux/path fixtures. The formal historical verdict remains `FAIL`; the accepted evidence is targeted-fix plus runtime evidence, not a reviewer PASS.

## 6. G9 runtime ledger

Blocked attempts were retained and excluded from scientific interpretation.

| Revision | Outcome | Root cause and disposition |
|---|---|---|
| r7b | BLOCKED before GPU | Output/receipt sibling path rejected; v5.4 eval-root admission was unified |
| r9 | BLOCKED before GPU | Warm checkpoint path omitted the nested experiment directory; command corrected |
| r10 | BLOCKED before GPU | Hydra used an invalid `+num_eval_episodes` override; override prefixes corrected |
| r12 | INVALID runtime | Diagnostic trace requested inactive push reward terms; narrowed to active telemetry terms without changing reward scales |
| r14 | INVALID runtime | Stage-0 timeout ended the first cell during COARSE and trace emission was pre-physics; only scheduler-live stage overtime was masked, other terminal causes remain fatal, and trace emission moved post-physics |
| r16 / retry5 | VALID scientific `FAIL` | Both targets and both allowed attempts completed with returned-done terminal rows; rehearsal gate rejected scheduler state `FAILED` |

No invalid attempt consumed a scientific rehearsal or G3 count.

## 7. Stage B rehearsal receipt

The valid receipt is `logs_eval/a2_piper_pull_v5/V5_4_STAGE_B_REHEARSAL_ATTEMPT1_G9RETRY5.json`. It is an `interface_characterization` record with `scientific_denominator_included=false` and `denominator_scope=none`.

The sole allowed correction was derived from all 16 attempt-0 terminal rows:

`shared_median_signed_original_target_error_rad = -0.3672668933868408`

| Original target | Attempt | Planning target | Rows | Mean absolute original-target error | Max absolute original-target error | Scheduler result |
|---:|---:|---:|---:|---:|---:|---|
| -2.5 rad | 0 | -2.5 rad | 8 | 0.3748272061 | 0.4112486839 | 8/8 `FAILED`, trim cap |
| -2.5 rad | 1 | -2.8672668934 rad | 8 | 0.0392494798 | 0.0900235176 | 8/8 `FAILED`, trim cap |
| +1.0 rad | 0 | +1.0 rad | 8 | 0.3641406596 | 0.4028127193 | 8/8 `FAILED`, trim cap |
| +1.0 rad | 1 | +0.6327331066 rad | 8 | 0.0248698294 | 0.0588076115 | 8/8 `FAILED`, trim cap |

All 32 terminal rows were first-episode rows joined to `env.step` returned dones. In the corrected attempt, all 16 rows were within `0.15 rad`, but every row had:

- `scheduler_state=FAILED`;
- `failure_reason=trim_step_cap_exceeded`;
- `terminal_current_state=false`;
- `terminal_hold_steps=0`.

The rehearsal therefore truthfully failed. Error-only success would violate the registered terminal-hold contract.

## 8. Anchor and conditional downstream matrix

| Phase | Registered population | v5.4 state | Reason |
|---|---|---|---|
| G3 anchor attempt 1–3 | S1–S4 under 0.05 m / 0.15 rad | `NOT_RUN` | Stage B rehearsal did not pass; zero G3 attempts consumed |
| Door closer bucket 2.5–5 N | 16 episodes per admitted sequence set | `NOT_RUN` | No admitted anchor subset |
| Door closer bucket 5–9 N | 16 episodes per admitted sequence set | `NOT_RUN` | No admitted anchor subset |
| Door closer bucket 9–12 N | 16 episodes per admitted sequence set | `NOT_RUN` | No admitted anchor subset |
| G2 lattice | 36 representative states x command lattice | `NOT_RUN` | No anchor PASS and door all-zero receipt |
| P3 M-s0/M-s1/C-s0/C-s1 | 256 env x 250 batches per cell | `NOT_RUN` | G1 not reached |
| P4 continuation/annealing | selected P3 cell | `NOT_RUN` | No P3 adjudication |
| Dual-source evaluation | canonical 16 + natural 16 per checkpoint | `NOT_RUN` | No eligible checkpoint |

There is no v5.4 door-side passage denominator, no v5.4 v4-B comparison row, and no canonical/natural DV row.

## 9. Eleven-invariant audit

Stage A and Stage B are diagnostic/interface-characterization populations and cannot promote door-task invariants to runtime PASS.

| # | Invariant | v5.4 verdict | Evidence |
|---:|---|---|---|
| 1 | `fake_e4` | `NOT_RUN` | No scientific door episode |
| 2 | `stage4_snapshot_below_hinge_gate` | `NOT_RUN` | No scientific door episode |
| 3 | `dont_push_before_true_stage3_to4` | `NOT_RUN` | No scientific door episode |
| 4 | `target_root_before_aperture_ready` | `NOT_RUN` | No scientific door episode |
| 5 | `corridor_active_before_aperture_ready` | `NOT_RUN` | No scientific door episode |
| 6 | `complete_without_frame_passage` | `NOT_RUN` | No scientific door episode |
| 7 | `frame_approach_active_before_aperture_ready` | `NOT_RUN` | No scientific door episode |
| 8 | `frame_approach_active_after_frame_passage` | `NOT_RUN` | No scientific door episode |
| 9 | Canonical episodes never count as natural-start DV | `NOT_RUN` | No dual-source population; diagnostics explicitly use denominator `none` |
| 10 | Failed-settle rows never enter the bank | Inherited v5.1 PASS | The 191-row G8 bank was not rewritten or loaded by Stage A/B |
| 11 | Canonical override only in canonical first 50 steps; never natural | `NOT_RUN` | No canonical override or dual-source episode |

Additional v5.4 admission checks passed at runtime: every valid rehearsal row was `interface_characterization`, denominator exclusion was explicit, all required terminal rows used returned dones and episode index zero, and no reward scale, stage topology, optimizer policy, checkpoint, or 0.05 m / 0.15 rad threshold changed.

## 10. Render index

| Requested class | Eligible episode | Render state | Reason |
|---|---|---|---|
| Anchor PASS example | None | `NOT_RUN_BY_FAIL_CLOSED_GATE` | Anchor did not run |
| Anchor FAIL example | None | `NOT_RUN_BY_FAIL_CLOSED_GATE` | Stage B diagnostic failure is not an anchor episode |
| Door closer buckets | None | `NOT_RUN_BY_FAIL_CLOSED_GATE` | Door probes did not run |
| Final canonical/natural checkpoint | None | `NOT_RUN_BY_FAIL_CLOSED_GATE` | P3/P4/eval did not run |

The Stage B receipt is a valid diagnostic artifact, but it is not an eligible anchor, door-bucket, or final-policy render class. No video was fabricated or relabeled.

## 11. G1–G13 decision log

| Gate | v5.4 state | Evidence-backed action |
|---|---|---|
| G1 | `NOT_RUN` | Rehearsal failed before anchor and door buckets. |
| G2 | `NOT_RUN` | No valid anchor-plus-door all-zero receipt exists. |
| G3 | `NOT_RUN` | No scientific anchor attempt was consumed. |
| G4 | Inherited confirmed | v5.1 P2 selected release persistence; it is not a v5.4 traversal result. |
| G5 | `NOT_RUN` | No P3 canonical-start result. |
| G6 | `NOT_RUN` | No canonical-positive/natural-zero result. |
| G7 | `NOT_RUN` | No P3 all-zero result. |
| G8 | Inherited available | The 191-row pure-A bank was retained and not loaded. |
| G9 | Triggered and closed | Five invalid/blocked rehearsal attempts were root-fixed and archived; retry5 is the sole valid scientific rehearsal receipt. |
| G10 | PASS for Stage B | GPU4–7 were clear before launch; the accepted rehearsal used GPU4 only. |
| G11 | Invoked | Stage B FAIL minimum truthful closure: report, memory/TODO synchronization, downstream `NOT_RUN`, residual precommit activated. |
| G12 | `NOT_RUN` | No C-arm natural-start degradation comparison. |
| G13 | Inherited `PASS_G8_PURE_A` | 191/191 bank rows retain required metadata; the bank was not rebuilt. |

## 12. Artifact index and protected state

| Artifact | Location / status |
|---|---|
| Planner architecture decision | `logs_eval/a2_piper_pull_v5/v5_4_planner_architecture_decision.json` |
| Stage A feasibility receipt | `scriptsFORhuman/pull_v5/V5_4_STAGE_A_FEASIBILITY.json` |
| Stage B valid receipt | `logs_eval/a2_piper_pull_v5/V5_4_STAGE_B_REHEARSAL_ATTEMPT1_G9RETRY5.json` |
| Stage B accepted output | `logs_eval/a2_piper_pull_v5/v5_4_stage_b_rehearsal_attempt1_g9retry5/` |
| Stage B accepted stdout/exit | `logs_eval/a2_piper_pull_v5/v5_4_stage_b_rehearsal/runtime_retry5_stdout.log`, `runtime_retry5_exit_code.txt` |
| Invalid G9 attempts | retained beside the Stage B rehearsal logs and excluded from science |
| Final state bank | `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt`, unchanged |
| Render directory | no eligible render; not created |

The pre-existing evidence ZIP and all 75 projected stage-2.5 trace files remain untracked and unmodified. GPU0–3, the push line, and the mainline worktree were not touched. P3/P4 were not launched, so no optimizer state was loaded; generated training routes retain `load_optimizer=false`.

## 13. Final disposition

Pull-v5.4 answered the architecture question without contaminating the scientific passage denominator. A measurement-derived terminal-yaw scheduler can place the robot numerically near both rehearsal targets after one shared correction, but it cannot establish or hold a valid terminal state: every corrected environment spends the entire registered trim budget and terminates with zero hold steps.

Under the binding three-rung ladder, that is a Stage B rehearsal failure and activates the residual terminal-hold adapter as the next architecture. A new v5.5 contract is required before that work starts. HOMIE fine-tuning remains the third rung and is indefinitely deferred until residual control is disproved. The v5.4 frame-passage stopping condition was not reached.
