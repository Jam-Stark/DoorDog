# A2+Piper Pull-v5.2 Round Report

**Task:** `A2_PULL_V5_2_20260815`
**Revision:** `r6-final-report`
**Plan:** `a2_piper_pull_v5_2_anchored_probe_and_assisted_starts`
**Evidence boundary:** path-bound v5.2 static evidence, three natural-anchor runtime receipts, and version-labeled inherited v5.1 receipts
**Current round status:** `CLOSED_G3_G11`

## Executive result

Pull-v5.2 closed under **G3/G11** at the natural open-field narrow anchor. All
three allowed attempts completed 64 terminal episodes, 16 per S1–S4 sequence,
and all three receipts returned `FAIL`. Every sequence remained
`command_solvable=16/16` in every attempt, but no sequence reached the required
16/16 waypoint and yaw criteria. The final attempt improved the measured yaw
error ranges after the initial orientation was changed from open-field yaw 0
to yaw π, but it did not cross the anchor admission threshold.

Across the three attempts, 192 natural-anchor terminal episodes were recorded.
No sequence was admitted to the door-side set, so the three closer-bucket
probes, G1, G2, P3, P4, and the dual-source evaluation were all `NOT_RUN`.
There is no v5.2 door-passage denominator and no v5.2 passage-zero claim. The
stopping condition—reproducible frame passage from both canonical and natural
starts—was not met.

The inherited v5.1 facts remain version-scoped evidence: F1–F5 were repaired,
the P2 paired intervention selected release persistence as binding, and the G8
pure-natural bank contains 191 admitted rows. The v5.2 natural anchor did not
load that bank, and none of these inherited facts is a v5.2 runtime PASS.

## Route, scope, and stopping condition

| Item | Binding value |
| --- | --- |
| Execution route | User-consented `HIGH_RISK_PATH`; bounded T0 implementation, one formal review wave, targeted fixes, three capped G3 runtime attempts, G11 closure, and one final report. |
| Scientific North Star | Release, traverse the door frame, and clear the whole body toward −X. |
| Scientific stopping condition | First **reproducible frame passage from both canonical and natural starts**. A release count or smaller Euclidean frame distance does not satisfy it. |
| v5.2 reached boundary | T1 natural open-field narrow anchor; three attempts exhausted under G3. |
| Planned canonical start for P1 | An admitted G8 bank state followed by the evaluator-level one-second P2 release+tuck override; this path was `NOT_RUN`. |
| Planned canonical start for P3/eval | An injected bank state labeled `bank_natural_e5_override`, with the environment-level arm/gripper override active for the first 50 control steps only; this path was `NOT_RUN`. |
| Actual T1 source | Natural open-field reset. Bank loading and canonical-start override were disabled. |
| G11 stopping boundary | Close truthfully after the third anchor `FAIL`; do not convert the absent door probe into passage zero or authorize downstream phases. |

## Inherited v5.1 F1–F5 facts

These are established v5.1 facts and prerequisites. They are not rerun v5.2
results.

| Repair | Inherited v5.1 fact | Evidence status entering v5.2 |
| --- | --- | --- |
| F1 | Bank injection is a per-config boolean. Injection-disabled census, load-receipt, capture, and probe routes do not require the final bank; P3 cells enable injection explicitly. | v5.1 runtime exercised both the disabled routes and the final-bank build path. |
| F2 | P2 is isolated from the v5 environment. It uses the frozen v4-B plan/config and performs action replacement in the evaluator after policy output. | v5.1 paired runtime receipt; base slices matched in all 16 selected pairs. |
| F3 | Source B writes robot and door state through IsaacLab articulation writers after reset, settles for at least 50 steps, and admits only valid constructed rows. | Three v5.1 attempts reached the final settle gate but admitted 0 constructed rows; G8 was invoked. |
| F4 | Source-A retained the 64 legacy E5 rows, attached per-state closer metadata, and added delayed E5+2 s and E5+4 s captures. | v5.1 produced all three natural capture tiers and a row-level manifest. |
| F5 | The actual load-only receipt loaded the actor from `policy_state_dict`; critic, optimizer, and scheduler were not loaded and were reset. `load_optimizer=false`. | v5.1 `ACTUAL`; the eval wrapper's requested `policy_only` to effective `full` normalization was recorded but not changed. |

## v5.2 T0 implementation and static evidence

| T0 boundary | Frozen r3 implementation | Evidence at this report boundary |
| --- | --- | --- |
| Narrow sequence set | Registers S1–S4 and evaluates each sequence independently; an anchor receipt exposes `anchored_sequences`, and the door probe consumes only that admitted subset. | Runtime reached 3 × 64 natural-anchor rows; every receipt `FAIL`, so the admitted subset was empty. |
| S3/S4 phase logic | Phase transition and final sequence completion use the current phase's waypoint/yaw errors instead of stale latched arrival flags. | Targeted static acceptance plus three complete runtime receipts; no sequence passed. |
| Anchor tolerances | Environment and receipt consume the same configured waypoint/yaw tolerances: 0.05 m and 0.15 rad. | Targeted static acceptance; all three runtime receipts adjudicated against the synchronized criteria. |
| P1 door start | Each admitted bank row would receive the evaluator-level P2 release+tuck override; terminal trace evidence must prove trigger, fired/active state, and active base-slice equality. | Trace schema and receipt checks were static-accepted; door runtime `NOT_RUN`. |
| Door metrics | Records bucket × sequence frame passage, panel contact, command error, hinge trajectory, and hinge angle at the first passage attempt. | Static/API acceptance; door runtime `NOT_RUN`. |
| P3 canonical-start override | Four P3 configs enable exactly 50 control steps of environment-level arm/gripper override for canonical bank starts; natural starts are excluded by reset-source labeling. | Four YAML configs parsed; P3 runtime `NOT_RUN`. |
| G8 reuse | T1–T4 orchestration and all four P3 configs explicitly admit the approved G8 pure-natural bank. | Static workflow acceptance; the natural anchor did not load the bank and no v5.2 bank rebuild occurred. |
| Dual-source analysis | Eval/analyzer paths carry source-separated frame-passage and K25 release DVs plus passage-attempt hinge telemetry. | Static implementation present; dual-source runtime `NOT_RUN`. |

Targeted validation recorded for r3: core Python compilation exited 0; the
focused core static suite passed 10 checks; workflow Python compilation passed;
all four P3 YAML configs parsed; and dry-run assertions passed. Targeted
IsaacLab/API acceptance was static PASS for pre-`DeltaActionBase` override
ordering, high-level articulation writes, preservation of the base and trailing
action slices, and first-passage hinge capture. None of these static checks is
a v5.2 runtime result.

## Formal review provenance: one FAIL wave, then targeted fixes

The only formal v5.2 review was the r2-frozen wave. Both the code-quality lane
and IsaacLab/API lane returned static `FAIL`. No second reviewer PASS exists or
is claimed.

| r2 finding | r3 targeted repair | Acceptance evidence |
| --- | --- | --- |
| T1–T4 and the four P3 configs did not admit the already approved 191-row `PASS_G8_PURE_A` bank. | Added explicit G8 admission to orchestration and all four YAML configs. | YAML parse for 4 configs and workflow dry-run assertions PASS. |
| Invariant 11 counted step-at-or-after-50 eligibility as an outside-window activation. | Outside-window telemetry now counts actual activation outside the window, `active & ~in_window`. | Focused core static check PASS; canonical/natural override runtime `NOT_RUN`. |
| P1 Hydra commands appended already-defined start-override keys with `+`. | Bound the keys as ordinary overrides. | Workflow dry-run assertions PASS. |
| S3/S4 could advance and finish from stale latched waypoint/yaw flags. | Transition and completion consume current phase errors. | Focused core static check PASS; three complete T1 receipts all returned `FAIL`. |
| Environment tolerances were 0.20 m/0.25 rad while the receipt adjudicated 0.05 m/0.15 rad. | The environment consumes the configured 0.05 m/0.15 rad values used by the receipt. | Focused core static check PASS. |
| The P1 receipt did not prove evaluator override trigger or active base-slice equality. | Terminal-env evaluator trace schema v1 is required and the receipt checks trigger, fired/active state, and base equality while active. | Workflow static acceptance; door runtime `NOT_RUN`. |

The r3 fixes were accepted through the targeted checks above. This preserves
the binding discipline: one formal review `FAIL`, targeted repair, and no
second formal review. The later r4 active-hold and r5 yaw-π anchor corrections
were targeted runtime fixes; they also do not create a reviewer PASS.

## G8 bank carried into v5.2

| Bank fact | Admitted rows / denominator |
| --- | ---: |
| Total pure-natural bank | 191/191 |
| `bank_natural_e5` provenance | 64/191 |
| `bank_natural_e5_plus` provenance | 127/191 |
| E5 tier | 64/191 |
| E5+2 s tier | 64/191 |
| E5+4 s tier | 63/191 |
| Closer 2.5–5 N·m | 45/191 |
| Closer 5–9 N·m | 54/191 |
| Closer 9–12 N·m | 92/191 |
| Constructed rows | 0/191; this is the sole G8-waived G13 class |
| Rows with provenance, closer force/bucket, tier, settle status/steps, and source row | 191/191 |

The bank verdict entering v5.2 is `PASS_G8_PURE_A`. It remained available for
the planned canonical P1/P3 routes but was not loaded by the natural open-field
anchor. Its presence is not evidence that Source B succeeded or that v5.2
exercised canonical starts.

## Inherited v5.1 P2 paired intervention

P2 used 16 strictly admissible matched pairs selected from a larger screening
pool. The primary endpoint was the K25 no-handle-contact result.

| Endpoint | Control | Release+tuck intervention | Denominator / interpretation |
| --- | ---: | ---: | --- |
| K25 persistent release | 3/16 | 16/16 | 16 matched pairs |
| +1 s hinge ≥1.6 rad | 16/16 | 12/16 | 16 matched pairs |
| +2 s hinge ≥1.6 rad | 16/16 | 5/16 | 16 matched pairs |
| E6 | 0/16 | 0/16 | v5.1 measured result only |
| Frame passage | 0/16 | 0/16 | v5.1 measured result only |
| Median minimum frame distance | 0.7410 m | 0.6503 m | 16 matched pairs per fixture |

Discordant pairs were 13 favorable, 0 unfavorable, with 3 ties. The one-sided
exact McNemar/binomial result was `p=0.0001220703125` at alpha 0.05. P2 therefore
selects **release persistence as the binding constraint**. It does not prove
traversal; the intervention also exposed a roughly 2–4 s reclosure race.

## T1 natural narrow anchor — final G3 result

Each attempt completed exactly 16 terminal rows per sequence, 64 rows total.
All sequences were command-solvable in all rows, but none reached the required
16/16 waypoint and yaw criteria. The three valid receipts therefore exhausted
the G3 attempt limit as `FAIL`, with 192/192 planned natural-anchor terminal
episodes completed.

| Attempt | Terminal rows | S1 waypoint / yaw | S2 waypoint / yaw | S3 waypoint / yaw | S4 waypoint / yaw | Command-solvable | Receipt |
| ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 64/64 | 9/16 / 0/16 | 10/16 / 0/16 | 10/16 / 0/16 | 9/16 / 0/16 | 16/16 for every sequence | `FAIL` |
| 2 | 64/64 | 8/16 / 0/16 | 12/16 / 0/16 | 12/16 / 0/16 | 8/16 / 0/16 | 16/16 for every sequence | `FAIL` |
| 3 | 64/64 | 7/16 / 1/16 | 11/16 / 0/16 | 10/16 / 1/16 | 8/16 / 5/16 | 16/16 for every sequence | `FAIL` |

Attempt 1 exposed a zero-yaw correction cap. The r4 targeted active-hold
change did not improve yaw admission in attempt 2. Attempt 2 then identified a
source-orientation mismatch: the open-field anchor initialized yaw at 0 while
the intended bank-side orientation is approximately π. The r5 targeted repair
initialized the third natural anchor at yaw π. Attempt 3 improved the observed
yaw-error ranges, especially at the low end, but remained far from 16/16
admission and did not authorize a fourth attempt.

| Sequence | Attempt-3 waypoint-error range (m) | Attempt-3 yaw-error range (rad) | Attempt-3 waypoint / yaw admission |
| --- | ---: | ---: | ---: |
| S1 | 0.0139–0.1067 | 0.0438–1.4791 | 7/16 / 1/16 |
| S2 | 0.0051–0.0780 | 0.1659–1.4569 | 11/16 / 0/16 |
| S3 | 0.0061–0.0781 | 0.1201–1.4573 | 10/16 / 1/16 |
| S4 | 0.0177–0.1067 | 0.0681–1.4793 | 8/16 / 5/16 |

This is a natural open-field locomotion-anchor failure. The bank was not
loaded, no release override was active, and these measurements are not door
feasibility or passage evidence.

## T1 door probe — three closer buckets NOT_RUN

No sequence passed the natural anchor, so no door-side job launched. Each
bucket × sequence cell required 16 actual terminal rows. The final denominator
is **0 executed / 16 planned** and every outcome is
`NOT_RUN`, not `0/16`.

### Closer bucket: 2.5–5 N·m

| Sequence | Actual / planned rows | Frame passage | Panel-contact rows | Passage-attempt hinge | Command error | Status |
| --- | ---: | --- | --- | --- | --- | --- |
| S1 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |
| S2 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |
| S3 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |
| S4 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |

### Closer bucket: 5–9 N·m

| Sequence | Actual / planned rows | Frame passage | Panel-contact rows | Passage-attempt hinge | Command error | Status |
| --- | ---: | --- | --- | --- | --- | --- |
| S1 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |
| S2 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |
| S3 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |
| S4 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |

### Closer bucket: 9–12 N·m

| Sequence | Actual / planned rows | Frame passage | Panel-contact rows | Passage-attempt hinge | Command error | Status |
| --- | ---: | --- | --- | --- | --- | --- |
| S1 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |
| S2 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |
| S3 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |
| S4 | 0/16 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | Blocked by final anchor FAIL |

## Conditional G1/G2 branch

| Observed T1 boundary | Required action | Current status |
| --- | --- | --- |
| Any admitted bucket × sequence has frame passage greater than zero | G1: occupancy/exploration hypothesis is supported; authorize P3. | `NOT_RUN`; no sequence reached the door probe |
| Every admitted bucket × sequence is measured zero after release is guaranteed and routes are anchored | G2: run the locomotion lattice focused on requested/realized yaw and lateral motion under door/panel disturbance. | `NOT_RUN`; no anchor PASS or all-zero door receipt exists |
| G2 shows the interface is infeasible | Stop the round and report; a residual policy remains a user decision. | `NOT_RUN` |
| G2 shows a narrow command-library defect | Apply one evidence-directed probe repair and rerun the affected branch. | `NOT_RUN` |

Residual-policy work remains a user decision only after a valid G2 lattice.
Because G2 did not run, this round supplies no residual-policy authorization or
interface-feasibility verdict.

## Conditional P3/P4 execution

P3 and P4 were not authorized because T1 never produced an admitted door
sequence or G1 result.

| Cell | GPU | Canonical injection p | Seed | Train denominator | Checkpoints | Current status |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| M-s0 | 4 | 0.5 | 0 | 256 env × 250 batches planned | every 50 batches | `NOT_RUN` |
| M-s1 | 5 | 0.5 | 1 | 256 env × 250 batches planned | every 50 batches | `NOT_RUN` |
| C-s0 | 6 | 0.9 | 0 | 256 env × 250 batches planned | every 50 batches | `NOT_RUN` |
| C-s1 | 7 | 0.9 | 1 | 256 env × 250 batches planned | every 50 batches | `NOT_RUN` |

- If any P3 cell has canonical passage greater than zero, G5 selects the best
  cell for P4 continuation by 250–500 batches over two seeds.
- If canonical passage is positive but natural passage is zero, G6 makes P4 a
  canonical-probability anneal from 0.9 to 0.5 to 0.3.
- If both sources produce reproducible passage, the stopping condition is met.
- If P3 is all-zero, G7 permits one evidence-selected single-axis fork; it does
  not authorize speculative multi-axis reward changes.
- If the C arm significantly degrades natural-start E4/E5, G12 records
  catastrophic forgetting and favors M without adding a rescue regularizer.

## P3/P4 dual-source DV — NOT_RUN

Every P3 checkpoint requires 16 canonical and 16 natural episodes, reported as
separate populations. K25 persistent release is a secondary DV in v5.2. A
canonical episode must never enter a natural denominator.

| Cell / reference | Checkpoint | Canonical frame passage (actual/16) | Natural frame passage (actual/16) | Canonical K25 (actual/16) | Natural K25 (actual/16) | E6 / E7 / complete by source | Passage-attempt hinge | Status |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| Pull-v4 B seed1 historical reference | 750 | N/A | 0/16 | N/A | N/A | natural 0/16 / 0/16 / 0/16 | N/A | Historical v4 runtime only; not v5.2 |
| M-s0 | N/A | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |
| M-s1 | N/A | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |
| C-s0 | N/A | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |
| C-s1 | N/A | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |
| P4 selected cell | N/A | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | 0 executed / 16 planned | `NOT_RUN` | `NOT_RUN` | `NOT_RUN`; no G5/G6 selection |

The v4-B reference is retained only to anchor historical natural-start
capability. No v5.2 canonical/natural difference, forgetting effect, or policy
effect can be inferred from these unexecuted rows.

## Eleven invariants

Every applicable v5.2 runtime counter must be zero. The three natural-anchor
receipts reported an aggregate observed invariant-violation count of zero over
192 terminal episodes. Invariants 9 and 11 require the unexecuted dual-source
or canonical-override paths and therefore remain `NOT_RUN`; the natural anchor
cannot promote them to PASS.

| # | Invariant | Required value | Available evidence | v5.2 runtime verdict |
| ---: | --- | --- | --- | --- |
| 1 | `fake_e4` | 0 violations / actual rows | Observed aggregate 0/192 natural-anchor rows | `RUNTIME PASS` in natural-anchor scope |
| 2 | `stage4_snapshot_below_hinge_gate` | 0 / actual rows | Observed aggregate 0/192 natural-anchor rows | `RUNTIME PASS` in natural-anchor scope |
| 3 | `dont_push_before_true_stage3_to4` | 0 / actual rows | Observed aggregate 0/192 natural-anchor rows | `RUNTIME PASS` in natural-anchor scope |
| 4 | `target_root_before_aperture_ready` | 0 / actual rows | Observed aggregate 0/192 natural-anchor rows | `RUNTIME PASS` in natural-anchor scope |
| 5 | `corridor_active_before_aperture_ready` | 0 / actual rows | Observed aggregate 0/192 natural-anchor rows | `RUNTIME PASS` in natural-anchor scope |
| 6 | `complete_without_frame_passage` | 0 / actual rows | Observed aggregate 0/192 natural-anchor rows | `RUNTIME PASS` in natural-anchor scope |
| 7 | `frame_approach_active_before_aperture_ready` | 0 / actual rows | Observed aggregate 0/192 natural-anchor rows | `RUNTIME PASS` in natural-anchor scope |
| 8 | `frame_approach_active_after_frame_passage` | 0 / actual rows | Observed aggregate 0/192 natural-anchor rows | `RUNTIME PASS` in natural-anchor scope |
| 9 | `canonical_not_counted_as_natural_start` | 0 / actual dual-source episodes | No canonical or dual-source episode ran | `NOT_RUN` |
| 10 | `failed_settle_not_in_bank` | 0 / admitted bank rows | Inherited G8 manifest has 0 failed-settle rows / 191 admitted rows; bank not loaded in T1 | Inherited v5.1 bank evidence only |
| 11 | Start override activates only in canonical episodes and only in the first 50 steps; natural episodes have zero activations | 0 outside-window activations / opportunities and 0 natural activations / natural episodes | No canonical-start override or dual-source evaluation ran | `NOT_RUN` beyond natural-anchor scope |

## G1–G13 decision log

| Gate | v5.2 state | Evidence / next action |
| --- | --- | --- |
| G1 | `NOT_RUN` | No sequence passed the narrow anchor, so no door bucket had a passage denominator. |
| G2 | `NOT_RUN` | The prerequisite anchor PASS and all-zero door receipt do not exist; no lattice or interface verdict is admissible. |
| G3 | `TRIGGERED / CLOSED FAIL` | Three complete 64-row attempts exhausted the cap. Waypoint/yaw admission remained below 16/16 for every sequence despite the r4 active-hold and r5 yaw-π corrections. |
| G4 | `INHERITED CONFIRMED` | v5.1 P2 had 13 favorable and 0 unfavorable discordant pairs, selecting release persistence as binding. This is not a v5.2 traversal result. |
| G5 | `NOT_RUN` | No P3 canonical-start passage receipt exists. |
| G6 | `NOT_RUN` | No canonical-positive/natural-zero P3 result exists. |
| G7 | `NOT_RUN` | No all-zero P3 result exists. |
| G8 | `INHERITED AVAILABLE` | v5.2 accepts the 191-row `PASS_G8_PURE_A` bank, but the natural anchor did not load it. |
| G9 | `NOT_TRIGGERED` | All three T1 launches produced complete 64-row receipts; corrections were G3 scientific repairs, not crash recovery. |
| G10 | `NOT_EVALUATED` | GPU ownership/capacity is outside the receipt evidence summarized here. |
| G11 | `INVOKED / CLOSED` | Minimum truthful closure contains T0 evidence, inherited F5/P2/G8 facts, the three-attempt natural-anchor boundary, this report, and explicit downstream `NOT_RUN` states. |
| G12 | `NOT_RUN` | No C-arm natural-start E4/E5 comparison exists. |
| G13 | `INHERITED PASS_G8_PURE_A` | 191/191 rows have required row metadata; constructed count is 0/191 under the explicit G8 waiver. |

## Artifact index

### Governing documents and inherited evidence

- `scriptsFORhuman/pull_task/a2_piper_pull_v5_bridge_occupancy_plan_20260812.md`
- `scriptsFORhuman/pull_task/a2_piper_pull_v5_1_repair_addendum_20260812.md`
- `scriptsFORhuman/pull_task/a2_piper_pull_v5_2_anchored_probe_addendum_20260814.md`
- `scriptsFORhuman/pull_v5/PULL_V5_1_ROUND_REPORT.md`
- `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_1_policy_only.json`
- `logs_eval/a2_piper_pull_v5/p2_intervention_v5_1/P2_INTERVENTION_RECEIPT.json`
- `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt`
- `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt.receipt.json`
- `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank_manifest.json`

### Frozen v5.2 implementation paths

- `gr00t/rl/envs/door/a2_pull_v0_guard.py`
- `gr00t/rl/envs/door/door_open_a2_pull.py`
- `gr00t/rl/config/ablation/wbmanip/pull_v5_M_s0.yaml`
- `gr00t/rl/config/ablation/wbmanip/pull_v5_M_s1.yaml`
- `gr00t/rl/config/ablation/wbmanip/pull_v5_C_s0.yaml`
- `gr00t/rl/config/ablation/wbmanip/pull_v5_C_s1.yaml`
- `scriptsFORhuman/pull_v5/run_pull_v5_p1_anchor_probe.py`
- `scriptsFORhuman/pull_v5/run_pull_v5_training.py`
- `scriptsFORhuman/pull_v5/run_pull_v5_eval.py`
- `scriptsFORhuman/pull_v5/analyze_pull_v5.py`
- `scriptsFORhuman/pull_v5/run_pull_v5_orchestration.py`

### v5.2 natural-anchor runtime artifacts

- Attempt 1 receipt:
  `logs_eval/a2_piper_pull_v5/pull_v5_2_p1_anchor_probe/anchor/P1_v5_2_anchor_natural_attempt1_RECEIPT.json`
- Attempt 1 sequence-log directory:
  `logs_eval/a2_piper_pull_v5/pull_v5_2_p1_anchor_probe/anchor/`; the exact logs
  are `S1/runner.log`, `S2/runner.log`, `S3/runner.log`, and `S4/runner.log`.
- Attempt 2 receipt:
  `logs_eval/a2_piper_pull_v5/pull_v5_2_p1_anchor_probe/anchor_attempt2/P1_v5_2_anchor_natural_attempt2_RECEIPT.json`
- Attempt 2 sequence-log directory:
  `logs_eval/a2_piper_pull_v5/pull_v5_2_p1_anchor_probe/anchor_attempt2/`; the
  exact logs are `S1/runner.log`, `S2/runner.log`, `S3/runner.log`, and
  `S4/runner.log`.
- Attempt 3 receipt:
  `logs_eval/a2_piper_pull_v5/pull_v5_2_p1_anchor_probe/anchor_attempt3/P1_v5_2_anchor_natural_attempt3_RECEIPT.json`
- Attempt 3 sequence-log directory:
  `logs_eval/a2_piper_pull_v5/pull_v5_2_p1_anchor_probe/anchor_attempt3/`; the
  exact logs are `S1/runner.log`, `S2/runner.log`, `S3/runner.log`, and
  `S4/runner.log`.
- T1 orchestration log: `scriptsFORhuman/pull_v5/v5_2_t1_tmux.log`

No door-probe, G2-lattice, P3-training, P3-eval, or P4 artifact exists because
those phases were not run.

## Limitations and evidence boundary

1. The v5.2 runtime evidence ends at the natural open-field anchor. It does not
   establish door-side feasibility, passage, canonical-start behavior, or P3
   learning.
2. The r3 validation evidence remains static/API acceptance. The later runtime
   receipts validate only the natural anchor paths that they actually ran.
3. The formal review provenance remains one two-lane static `FAIL` wave.
   Targeted fixes were validated without a second reviewer verdict.
4. The v5.1 P2, F5, anchor, and G8 results retain their original denominators
   and version labels. None is renamed as a v5.2 runtime PASS.
5. The canonical bank is pure natural under G8: 0/191 constructed rows. v5.2
   planned assisted-start paths would add the explicit release+tuck override,
   but the natural anchor loaded neither the bank nor the override.
6. The three anchor attempts establish a reproducible locomotion-interface
   admission failure under their 0.05 m/0.15 rad criteria. Their error ranges
   do not establish a door-side all-zero result and cannot trigger G2.
7. No door denominator, G1/G2 verdict, P3 checkpoint, dual-source episode, P4
   continuation, or successful v5.2 stopping-condition verdict exists.
8. Every `0 executed / 16 planned` door or dual-source entry describes an
   unrun phase. It is not a passage outcome and must not enter a scientific
   numerator/denominator.
