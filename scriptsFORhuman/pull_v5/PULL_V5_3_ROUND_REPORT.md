# A2+Piper Pull v5.3 Round Report

**Plan ID:** `a2_piper_pull_v5_3_locomotion_interface_probe`  
**Task ID:** `A2_PULL_V5_3_20260816`  
**Branch:** `codex/a2-piper-pull-v0-20260803`  
**Report date:** 2026-08-16 HKT

## 1. Executive outcome

Pull-v5.3 completed the preregistered P0 HOMIE yaw-interface characterization and selected **H-D: low-level capability gap**. The accepted attempt produced 44/44 versioned characterization cells, eight environments per cell, one complete first-episode trace per environment, and an aggregate receipt with `scientific_denominator_included=false`.

The decisive observation was zero-command drift after large negative commands. For `u=-2.0`, the mean two-second hold drift was `-0.226979`, `-0.219226`, and `-0.216827 rad` after the 1, 2, and 4 second command windows; all eight environments in every one of those cells exceeded the immutable `0.15 rad` bound. The `u=-0.8,T=1` cell also had mean drift `-0.154359 rad`, with 5/8 environments above the bound. This directly satisfies the addendum's H-D stop rule.

Accordingly, v5.3 made no P1 mapping change and did not run the narrow anchor, door buckets, G2 lattice, P3, P4, dual-source evaluation, or representative anchor/P3 rendering. Those phases are `NOT_RUN`, not zero-passage results. The canonical-plus-natural `frame_passage` stopping condition remains unmet. Residual policy or HOMIE fine-tuning remains a user-level architecture decision.

The sole formal review wave returned `FAIL`: it found that the H-D decision was not yet a fail-closed launch dependency, `terminal_after_step` used stale pre-termination state, and P1/invariant-9 provenance checks were not independent. All three findings received bounded targeted fixes and acceptance without a second formal review. A human-fixed H-D artifact now rejects every downstream entry point before IsaacSim launch; a one-cell GPU4 acceptance run proved corrected terminal timing; and synthetic source fixtures proved strict natural-versus-bank isolation.

## 2. Scope, preflight, and protected state

- Physical GPUs 4–7 were the only authorized devices. P0 used physical GPU4; pre-launch ownership checks found GPUs 4–7 idle, and GPU4 was released after the accepted run.
- Warm actor: `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_B_wave1_seed1/model_step_000750.pt`.
- Existing G8 bank: 191 pure Source-A rows, retained but not loaded by P0.
- The pre-existing evidence ZIP and exactly 75 projected traces remained untracked and unmodified.
- No reward scale, training stage topology, scientific threshold, or optimizer-loading policy changed. All v5.3 training routes still specify `load_optimizer=false`.
- P0 ran in `pull_v5_3_p0_gpu4`. The accepted attempt exited `0` and wrote the aggregate receipt at 2026-08-16 16:28 HKT.

## 3. T0 harness and runtime repair chain

### 3.1 Accepted static and runtime contract

- The evaluator applies the actor output, leaves the ordinary P1 probe disabled, then writes the diagnostic raw yaw command directly to high-level action index 2 before DeltaAction/HOMIE conversion.
- Every row records requested phase command, audited raw base slice, scaled/clipped physical command, pre/post world yaw, planar root motion, and control timestep.
- Characterization uses an explicit v5.3 plan ID and `record_class=interface_characterization`; neither row traces nor the aggregate receipt enter a scientific numerator or denominator.
- The diagnostic horizon does not modify the frozen stage configuration. It masks only Stage-0 overtime while a characterization window is pending, preserves every other terminal reason, and emits diagnostic completion at exactly 150, 200, or 300 steps for T1, T2, or T4 cells.
- Per-cell strict validation runs before the next cell starts. The accepted run produced 44 traces and only then wrote the aggregate receipt.

### 3.2 G9 repair receipts

The blocked launches were retained as infrastructure evidence and never counted as scientific attempts.

| Boundary | Observed failure | Root repair | Scientific rows |
|---|---|---|---:|
| Initial composition | Existing `save_videos` key used Hydra append syntax | Direct override | 0 |
| Composition retry 1 | Existing `num_save_episodes` key used append syntax | Direct override after base-config membership check | 0 |
| Composition retry 2 | New P2 key lacked append syntax | Added the required `+`; full command compose-only check | 0 |
| First full runtime | Audited raw yaw tensor was captured before index 2 was populated | Populated raw yaw before applied-action copy; validate every cell immediately | 0 accepted traces |
| Provenance boundary | Trace inherited the v5 base plan ID | Added explicit v5.3 characterization plan ID | 0 accepted cells |
| Window boundary | T4 required 300 rows but frozen Stage-0 overtime ended at 250 | Diagnostic-only exact horizon; no topology change | 2 partial cells, no aggregate receipt |
| Guard boundary | Direct `max_stage_time` override was rejected by the frozen guard | Removed override and used terminal-reason-aware diagnostic horizon | 0 accepted cells |
| Accepted attempt | 44/44 cell traces and aggregate receipt | No further repair | 44 cells / 352 environment trajectories |

## 4. P0 per-cell transfer curves

All values are means over eight environments. `Latency` is the first nonzero realized-yaw sample; every cell responded at one control step (`0.02 s`). `Hold drift` covers the two-second zero-command segment.

| Cell | Raw yaw `u` | Duration (s) | Coupling | Command yaw (rad) | Mean yaw rate (rad/s) | Gain (rad/s/u) | Latency (s) | Hold drift (rad) | Planar displacement (m) |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| pure_yaw_m0p05_T1 | -0.05 | 1 | none | -0.104049 | -0.104049 | 2.080979 | 0.02 | -0.016471 | 0.018090 |
| pure_yaw_m0p05_T2 | -0.05 | 2 | none | -0.120476 | -0.060238 | 1.204763 | 0.02 | 0.000080 | 0.018177 |
| pure_yaw_m0p05_T4 | -0.05 | 4 | none | -0.120813 | -0.030203 | 0.604067 | 0.02 | 0.000426 | 0.018090 |
| pure_yaw_p0p05_T1 | 0.05 | 1 | none | -0.102857 | -0.102857 | -2.057143 | 0.02 | -0.017656 | 0.018132 |
| pure_yaw_p0p05_T2 | 0.05 | 2 | none | -0.119653 | -0.059826 | -1.196527 | 0.02 | -0.000831 | 0.018217 |
| pure_yaw_p0p05_T4 | 0.05 | 4 | none | -0.119920 | -0.029980 | -0.599600 | 0.02 | -0.000480 | 0.018154 |
| pure_yaw_m0p1_T1 | -0.10 | 1 | none | -0.104551 | -0.104551 | 1.045510 | 0.02 | -0.015965 | 0.018031 |
| pure_yaw_m0p1_T2 | -0.10 | 2 | none | -0.120972 | -0.060486 | 0.604858 | 0.02 | 0.000611 | 0.018149 |
| pure_yaw_m0p1_T4 | -0.10 | 4 | none | -0.121295 | -0.030324 | 0.303237 | 0.02 | 0.000937 | 0.018079 |
| pure_yaw_p0p1_T1 | 0.10 | 1 | none | -0.102091 | -0.102091 | -1.020909 | 0.02 | -0.018349 | 0.018166 |
| pure_yaw_p0p1_T2 | 0.10 | 2 | none | -0.119199 | -0.059599 | -0.595993 | 0.02 | -0.001106 | 0.018279 |
| pure_yaw_p0p1_T4 | 0.10 | 4 | none | -0.119352 | -0.029838 | -0.298381 | 0.02 | -0.000881 | 0.018202 |
| pure_yaw_m0p2_T1 | -0.20 | 1 | none | -0.106057 | -0.106057 | 0.530283 | 0.02 | -0.014602 | 0.017955 |
| pure_yaw_m0p2_T2 | -0.20 | 2 | none | -0.121889 | -0.060944 | 0.304722 | 0.02 | 0.001533 | 0.018038 |
| pure_yaw_m0p2_T4 | -0.20 | 4 | none | -0.122151 | -0.030538 | 0.152689 | 0.02 | 0.001752 | 0.017955 |
| pure_yaw_p0p2_T1 | 0.20 | 1 | none | -0.100709 | -0.100709 | -0.503544 | 0.02 | -0.019686 | 0.018266 |
| pure_yaw_p0p2_T2 | 0.20 | 2 | none | -0.118214 | -0.059107 | -0.295535 | 0.02 | -0.001979 | 0.018362 |
| pure_yaw_p0p2_T4 | 0.20 | 4 | none | -0.118439 | -0.029610 | -0.148049 | 0.02 | -0.001740 | 0.018312 |
| pure_yaw_m0p4_T1 | -0.40 | 1 | none | -0.108721 | -0.108721 | 0.271803 | 0.02 | -0.012303 | 0.017770 |
| pure_yaw_m0p4_T2 | -0.40 | 2 | none | -0.123863 | -0.061932 | 0.154829 | 0.02 | 0.003045 | 0.017816 |
| pure_yaw_m0p4_T4 | -0.40 | 4 | none | -0.124286 | -0.031072 | 0.077679 | 0.02 | 0.003423 | 0.017720 |
| pure_yaw_p0p4_T1 | 0.40 | 1 | none | -0.097813 | -0.097813 | -0.244533 | 0.02 | -0.022332 | 0.018365 |
| pure_yaw_p0p4_T2 | 0.40 | 2 | none | -0.116055 | -0.058028 | -0.145069 | 0.02 | -0.003820 | 0.018434 |
| pure_yaw_p0p4_T4 | 0.40 | 4 | none | -0.116109 | -0.029027 | -0.072568 | 0.02 | -0.003891 | 0.018382 |
| pure_yaw_m0p8_T1 | -0.80 | 1 | none | -0.149100 | -0.149100 | 0.186375 | 0.02 | -0.154359 | 0.120776 |
| pure_yaw_m0p8_T2 | -0.80 | 2 | none | -0.355540 | -0.177770 | 0.222213 | 0.02 | -0.137607 | 0.220989 |
| pure_yaw_m0p8_T4 | -0.80 | 4 | none | -0.748183 | -0.187046 | 0.233807 | 0.02 | -0.136705 | 0.407315 |
| pure_yaw_p0p8_T1 | 0.80 | 1 | none | 0.117125 | 0.117125 | 0.146407 | 0.02 | -0.062995 | 0.115466 |
| pure_yaw_p0p8_T2 | 0.80 | 2 | none | 0.292389 | 0.146195 | 0.182743 | 0.02 | -0.062688 | 0.207769 |
| pure_yaw_p0p8_T4 | 0.80 | 4 | none | 0.661682 | 0.165421 | 0.206776 | 0.02 | -0.039273 | 0.373423 |
| pure_yaw_m2_T1 | -2.00 | 1 | none | -0.354797 | -0.354797 | 0.177399 | 0.02 | -0.226979 | 0.126177 |
| pure_yaw_m2_T2 | -2.00 | 2 | none | -0.860005 | -0.430002 | 0.215001 | 0.02 | -0.219226 | 0.220490 |
| pure_yaw_m2_T4 | -2.00 | 4 | none | -1.852757 | -0.463189 | 0.231595 | 0.02 | -0.216827 | 0.356024 |
| pure_yaw_p2_T1 | 2.00 | 1 | none | 0.312577 | 0.312577 | 0.156289 | 0.02 | 0.032532 | 0.100614 |
| pure_yaw_p2_T2 | 2.00 | 2 | none | 0.772108 | 0.386054 | 0.193027 | 0.02 | 0.038319 | 0.176321 |
| pure_yaw_p2_T4 | 2.00 | 4 | none | 1.717072 | 0.429268 | 0.214634 | 0.02 | 0.039078 | 0.292231 |
| coupling_straight_minus_x_m0p2_T2 | -0.20 | 2 | straight_minus_x | -0.145862 | -0.072931 | 0.364655 | 0.02 | -0.056334 | 0.338143 |
| coupling_side_step_m0p2_T2 | -0.20 | 2 | side_step | -0.117270 | -0.058635 | 0.293176 | 0.02 | -0.084161 | 0.370269 |
| coupling_straight_minus_x_p0p2_T2 | 0.20 | 2 | straight_minus_x | 0.006612 | 0.003306 | 0.016530 | 0.02 | -0.030239 | 0.336887 |
| coupling_side_step_p0p2_T2 | 0.20 | 2 | side_step | 0.042970 | 0.021485 | 0.107425 | 0.02 | -0.064798 | 0.369242 |
| coupling_straight_minus_x_m0p8_T2 | -0.80 | 2 | straight_minus_x | -0.384590 | -0.192295 | 0.240369 | 0.02 | -0.091844 | 0.336518 |
| coupling_side_step_m0p8_T2 | -0.80 | 2 | side_step | -0.367280 | -0.183640 | 0.229550 | 0.02 | -0.114087 | 0.367986 |
| coupling_straight_minus_x_p0p8_T2 | 0.80 | 2 | straight_minus_x | 0.239560 | 0.119780 | 0.149725 | 0.02 | 0.003092 | 0.334985 |
| coupling_side_step_p0p8_T2 | 0.80 | 2 | side_step | 0.284406 | 0.142203 | 0.177754 | 0.02 | -0.037137 | 0.369106 |

## 5. Hypothesis adjudication

**Selected: H-D.** The hard stop is the registered zero-command drift test, not an interpretive fit. All three `u=-2.0` duration cells had 8/8 environments beyond `0.15 rad` during the two-second hold, and the worst per-environment absolute drift was `0.244354 rad`.

The transfer curves also expose useful structure without changing the verdict:

- At `|u|>=0.8`, command-window yaw grows approximately with duration, consistent with a rate-like region. Across T1/T2/T4, rate coefficient of variation was about 0.09–0.14 for `u=±0.8,±2.0`.
- Small commands `|u|<=0.4` were dominated by a negative approximately `-0.12 rad` transient/bias and did not have a duration-linear command response.
- The channel is asymmetric. `u=-2.0` and `u=2.0` had similar command-window rate magnitudes but radically different zero-hold drift (`about -0.22 rad` versus `about +0.04 rad`).
- Translational primitives materially perturb yaw. At `u=0.2,T=2`, pure-yaw displacement was `-0.118214 rad`, while straight-minus-X and side-step yielded `+0.006612` and `+0.042970 rad`.

Those observations would inform a future low-level redesign, but the H-D rule forbids a v5.3 mapping-only repair, residual policy, or HOMIE fine-tune.

## 6. P1-fix and formal review

- **P1-fix:** `NOT_RUN`. The ordinary probe-side `applied[:,2]` mapping was not changed after P0 because H-D is a mandatory stop.
- **Formal review verdict:** `FAIL` in the sole allowed review wave. Code review found the missing H-D orchestration dependency. IsaacLab review found the same launch-gate defect plus stale `terminal_after_step` timing and a vacuous/mixed-source P1 invariant-9 contract. Both reviews confirmed that the raw/scaled yaw action order, WXYZ world-yaw convention, exact diagnostic windows, denominator isolation, unchanged P1 mapping, and immutable `0.05 m / 0.15 rad` thresholds were otherwise valid.
- **Targeted H-D gate repair:** `logs_eval/a2_piper_pull_v5/v5_3_p0_adjudication.json` records the human-fixed `H-D`, `downstream_admitted=false`, attempt8/report provenance, and no hypothesis recomputation. P1, orchestration T1+, training, eval, and render all rejected this artifact before command/runtime launch. An admitted H-A fixture generated dry-run commands; H-A with `downstream_admitted=false` was also rejected.
- **Targeted terminal repair:** the trainer now fills `terminal_after_step` from the `dones` returned by `env.step`, after termination evaluation. The dedicated GPU4 acceptance cell at `logs_eval/a2_piper_pull_v5/v5_3_review_fix_acceptance/interface_t1_cell` exited `0` in about 60 seconds: eight environments each produced 150 rows, one terminal flag at step 149, no step-0 flag, raw yaw `-0.05`, scaled yaw `-0.0125`, and finite yaw telemetry.
- **Targeted provenance repair:** invariant 9 now compares independent declared-provider and actual reset provenance. Synthetic acceptance admitted natural-only and bank-only populations and rejected mixed natural/bank P1 and eval rows.
- **Review boundary:** these repairs have compile/static plus bounded runtime acceptance; they do not convert the sole formal `FAIL` into reviewer `PASS`, and no second review was run.

## 7. Narrow anchor and conditional downstream

| Phase | Planned denominator | Runtime state | Evidence boundary |
|---|---:|---|---|
| Narrow anchor attempts 1–3 | 4 sequences × 16 episodes per attempt | `NOT_RUN` | H-D stopped before P1-fix and rule-5 admission |
| Door closer bucket 2.5–5 N | 16 episodes per admitted sequence set | `NOT_RUN` | No admitted anchor subset |
| Door closer bucket 5–9 N | 16 episodes per admitted sequence set | `NOT_RUN` | No admitted anchor subset |
| Door closer bucket 9–12 N | 16 episodes per admitted sequence set | `NOT_RUN` | No admitted anchor subset |
| G2 lattice | 36 representative states × command lattice | `NOT_RUN` | No anchor PASS or door all-zero receipt |
| P3 M-s0/M-s1/C-s0/C-s1 | 256 env × 250 batches per cell | `NOT_RUN` | G1 not reached |
| P4 continuation/annealing | Selected P3 cell | `NOT_RUN` | No G5/G6/G7/G12 selection |
| Dual-source evaluation | Canonical 16 + natural 16 per checkpoint | `NOT_RUN` | No P3/P4 checkpoint |

There is no door-side passage denominator and no v5.3 canonical/natural DV row. The v4-B baseline, v5.1 P2, and 191-row bank retain their inherited version labels only.

## 8. Eleven-invariant audit

P0 is diagnostic and excluded from the scientific episode population, so it cannot promote door-task invariants to runtime PASS. The bank invariant retains inherited v5.1 evidence.

| # | Invariant | v5.3 verdict | Evidence |
|---:|---|---|---|
| 1 | `fake_e4` | `NOT_RUN` | No scientific v5.3 episode |
| 2 | `stage4_snapshot_below_hinge_gate` | `NOT_RUN` | No scientific v5.3 episode |
| 3 | `dont_push_before_true_stage3_to4` | `NOT_RUN` | No scientific v5.3 episode |
| 4 | `target_root_before_aperture_ready` | `NOT_RUN` | No scientific v5.3 episode |
| 5 | `corridor_active_before_aperture_ready` | `NOT_RUN` | No scientific v5.3 episode |
| 6 | `complete_without_frame_passage` | `NOT_RUN` | No scientific v5.3 episode |
| 7 | `frame_approach_active_before_aperture_ready` | `NOT_RUN` | No scientific v5.3 episode |
| 8 | `frame_approach_active_after_frame_passage` | `NOT_RUN` | No scientific v5.3 episode |
| 9 | Canonical episodes never count as natural-start DV | `NOT_RUN` (contract repaired) | No dual-source episode; independent declared-versus-actual provenance passed synthetic isolation checks, while diagnostic P0 remained excluded |
| 10 | Failed-settle rows never enter the bank | Inherited v5.1 PASS | 0 failed-settle rows in the 191-row G8 manifest; bank not loaded by P0 |
| 11 | Canonical override only in canonical first 50 steps; never natural | `NOT_RUN` | No canonical override or dual-source episode |

## 9. Render index

| Requested class | Eligible runtime receipt | Render state | Reason |
|---|---|---|---|
| Anchor PASS example | None | `NOT_RUN` | H-D stopped before anchor |
| Anchor FAIL example | None in v5.3 | `NOT_RUN` | Replaying v5.2 would mislabel version provenance |
| Door closer buckets | None | `NOT_RUN` | Door probes not reached |
| Final canonical/natural checkpoint | None | `NOT_RUN` | P3/P4/eval not reached |

The v5.3 render runner passed static command/receipt-selection validation, but the fixed H-D artifact rejects its executable route and no eligible v5.3 scientific receipt exists. Render is non-blocking and does not alter the H-D decision.

## 10. G1–G13 decision log

| Gate | v5.3 state | Evidence-backed action |
|---|---|---|
| G1 | `NOT_RUN` | H-D stopped before anchor and door buckets. |
| G2 | `NOT_RUN` | No valid anchor and all-zero door receipt exist. |
| G3 | `NOT_RUN` | No v5.3 scientific anchor attempt was consumed. |
| G4 | Inherited confirmed | v5.1 P2 selected release persistence; it is not a v5.3 traversal result. |
| G5 | `NOT_RUN` | No P3 canonical-start result. |
| G6 | `NOT_RUN` | No canonical-positive/natural-zero result. |
| G7 | `NOT_RUN` | No P3 all-zero result. |
| G8 | Inherited available | 191-row pure-A bank retained but not loaded by P0. |
| G9 | Triggered and closed | Hydra, telemetry, provenance, diagnostic-horizon, H-D launch-gate, terminal-timing, and source-isolation defects were root-fixed; blocked receipts were preserved and excluded from science. |
| G10 | PASS for P0 | GPU4–7 ownership check was clear; accepted P0 used GPU4 only. |
| G11 | Invoked | H-D minimum truthful closure: accepted P0 characterization, report, memory/TODO synchronization, and downstream `NOT_RUN`. |
| G12 | `NOT_RUN` | No C-arm natural-start degradation comparison. |
| G13 | Inherited `PASS_G8_PURE_A` | 191/191 bank rows retain required metadata; no constructed rows under G8. |

## 11. Load, optimizer, and artifact receipts

- P0 evaluator logs record the frozen v4-B step750 checkpoint load. The evaluation wrapper requested `policy_only` and normalized it to `full`; v5.3 records this existing methodology fact and does not change the wrapper.
- The accepted characterization receipt is `logs_eval/a2_piper_pull_v5/v5_3_interface_characterization_receipt.json`.
- The human-fixed downstream gate is `logs_eval/a2_piper_pull_v5/v5_3_p0_adjudication.json`; it records `H-D` and `downstream_admitted=false` without recomputing the hypothesis.
- The 44 source traces are `logs_eval/a2_piper_pull_v5/v5_3_char_*/characterization_trace.json`.
- Targeted terminal-semantics runtime acceptance is under `logs_eval/a2_piper_pull_v5/v5_3_review_fix_acceptance/interface_t1_cell`.
- Blocked attempts and their runner logs remain archived under the `v5_3_p0_attempt*` evidence paths.
- The final bank remains `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt` and was not rewritten.
- P3/P4 optimizer state was never loaded because those phases were not launched; their generated commands retain `load_optimizer=false`.

## 12. Final disposition

Pull-v5.3 achieved its diagnostic objective and established a durable low-level interface fact: the frozen HOMIE yaw channel has a rate-like high-command region but fails the registered terminal hold requirement under negative large commands, with repeatable two-second zero-command drift above `0.15 rad`. The correct preregistered action is H-D/G11 closure, not a probe-side gain/sign patch.

The next architecture decision is outside this worker's authority: either introduce a residual yaw policy/adapter with its own approved scientific contract or fine-tune the HOMIE low-level controller for symmetric rate response and terminal zero-command hold. No door-side occupancy or passage inference is admissible until that capability is demonstrated under the unchanged 0.05 m / 0.15 rad rule-5 thresholds.
