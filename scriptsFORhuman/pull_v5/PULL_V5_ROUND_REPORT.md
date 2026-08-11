# A2+Piper Pull v5 — Round Report

**Task:** `A2_PULL_V5_20260812`
**Revision:** `r5_closure_docs`
**Plan:** `a2_piper_pull_v5_bridge_occupancy_and_release_persistence`
**Round date:** 2026-08-12 HKT
**Evidence identity:** path-bound; no hashes are recorded.

## Executive result

**v5 is closed under G9/G11 as an infrastructure-blocked negative/inconclusive
round.** The v4-B census confirms the early-open occupancy problem, but the
two-source bank prerequisite was not completed. Consequently there is **no
first dual-source frame passage**, no P3/P4 training or dual-source DV, and no
G2 causal verdict. The stopping condition remains false:

> first reproducible frame passage from both canonical and natural starts.

The correct interpretation is not “v5 passage was zero.” P1 was blocked before
its admissible anchor/door measurements, P2 produced no terminal metrics, and
P3/P4 were not run.

Evidence labels in this report are deliberately separated: `STATIC PASS` means
the recorded contract or artifact check passed; `RUNTIME PASS`/`RUNTIME FAIL`
means a runner reached the corresponding runtime boundary; `BLOCKED` means a
required prerequisite failed; `NOT_RUN` means the phase was not launched; and
`INCONCLUSIVE` means no scientific verdict was admissible.

## Phase verdicts at a glance

| Phase | Verdict | What is actually established |
| --- | --- | --- |
| P0 census | `RUNTIME PASS` | Valid v4-B 64 × 50 staged-reset census; Stage-4 mass remains early-open. |
| P0 load receipt | `RUNTIME FAIL / BLOCKED` | IsaacSim initialized, but the mandatory bank-injection guard stopped the load-only run before checkpoint loading. |
| P0-c archive | `STATIC PASS` | Capped derivative archive is complete under its stated manifest contract. |
| Source A | `RUNTIME PASS` (partial) | 64 exported `bank_natural_e5` states, all settle-valid; not a final canonical bank. |
| Source B / final bank | `RUNTIME FAIL / BLOCKED` | Source B failed the stage-0 reset-ratio invariant; final `pull_v5_state_bank.pt` is absent. |
| P1 anchor/door | `BLOCKED / INCONCLUSIVE` | Bank-dependent construction failed; no passage rate is admissible. |
| P2 intervention | `INCONCLUSIVE` | Control construction failed on the same missing-bank prerequisite; intervention did not start. |
| P3 2 × 2 | `NOT_RUN` | Stopped at unresolved bank/P1 prerequisites; no training or checkpoint DV exists. |
| P4 continuation | `NOT_RUN` | P3 never supplied an admissible continuation candidate. |
| G2 lattice/causal verdict | `NOT_RUN` | P1 did not reach the all-zero-anchor branch that would authorize G2. |

## P0 — occupancy, load receipt, and archive

### Valid v4-B census

The r5 census is a valid v4-B baseline (`seed=1`, 64 environments × 50
batches). It reports the following snapshot counts:

| Stage | Snapshot count | Reset source | Hinge summary (rad) | Stable-contact count |
| ---: | ---: | --- | --- | ---: |
| 0 | 12,800 | natural 12,800 | 0 / 0 / 0 (min / mean / max) | 0 |
| 1 | 64 | natural 64 | `0.000000009–0.000000073`, mean `0.000000036` | 0 |
| 2 | 64 | natural 64 | `0.000000015–0.000000084`, mean `0.000000043` | 0 |
| 3 | 64 | natural 64 | `-0.000000111–0.080829`, mean `0.007538` | 64 |
| 4 | 64 | natural 64 | **`0.250109–0.256819`, mean `0.252803`** | 64 |
| 5 | 0 | natural 0 | N/A | N/A |

Stage-4 root mean was `[0.7623775, -0.1367769, 0.4366283]` m. The census is
therefore runtime evidence that the staged-reset mass is concentrated in the
early-open Stage-4 hinge band and has no Stage-5/post-release or frame-
transition snapshots. It is not evidence of a v5 traversal success.

### Policy-only load receipt

The dedicated r5 load-only command requested `checkpoint_load_mode=policy_only`
and `load_optimizer=false` on physical GPU 6. It started the trainer and
initialized IsaacSim, but failed before the checkpoint loader:

| Load boundary | Runtime result |
| --- | --- |
| trainer started | true |
| IsaacSim environment initialized | true |
| checkpoint loader reached / actor loaded | false / false |
| critic, optimizer, scheduler reset | false / false / false |
| optimizer step or batch | false |

Root cause: the load-receipt command set
`a2_pull_v5_stage4_bank_injection_enabled=false`, while
`DoorOpenA2Pull._load_a2_pull_v5_state_bank` requires bank injection for every
Pull-v5 training configuration. The requested load receipt was not produced.
The r5 census also records that the evaluation wrapper normalized its requested
`policy_only` mode to `full` before environment construction; neither path is
a runtime proof of the requested policy-only load semantics.

### Evidence archive (P0-c)

The P0-c receipt is `STATIC PASS`. The archive contains 195 entries: Tier 1
`97`, Tier 3 projected traces `75`, Tier 2 `22`, plus `MANIFEST.md`.

| Archive fact | Recorded value |
| --- | ---: |
| Final ZIP bytes | `302,913,787` (under decimal 500,000,000 cap) |
| Tier-1 / Tier-3 / Tier-2 | `97 / 75 / 22` |
| Projected traces | `75`, one per formal metric cell, all present and non-empty |
| Original Tier-3 source bytes | `22,665,835,160` |
| Projected Tier-3 source bytes | `1,250,007,189` |
| Compressed ZIP payload bytes | `194,484,166` |
| MP4s included / omitted | `18 / 6` (six logical R1 omissions remain explicit) |

The size reduction is an intentional projection, not a loss silently attributed
to compression: each projected trace retains every original Stage-2–5 row,
count, order, and analyzer-required field, while the manifest records the
original and projected paths and byte counts. The projected 1.250 GB source
set compresses to about 194 MB inside the final 302.9 MB archive. Source
evaluation units were not modified and no hash/digest fields were added.

### r3 → r4 → r5 failure chronology

The failure chain is preserved rather than collapsed into a generic “P0
failed”:

1. **r3:** the census launcher passed `gr00t.rl.eval_agent_trl` as a positional
   script path. Python attempted to open a literal repository path; runtime and
   CUDA initialization never started.
2. **r4:** module launch was corrected and IsaacSim initialized, but the runner
   forced `a2_v20_telemetry_enabled=true`, violating the frozen v4-B guard
   (`false`). The run failed at environment construction; the wrapper also
   normalized `policy_only` to `full`.
3. **r5:** the census path was corrected and passed. Source A exported a valid
   partial bank. The dedicated load-only receipt then hit the bank-injection
   guard, Source B hit the stage-0 ratio assertion, and bank-dependent P1/P2
   construction failed closed. No final bank was produced.

## State-bank evidence

### Source A (natural E5 export)

`source_a_actor_e5_r5.pt` is a valid **partial** source payload, not the final
canonical bank:

- `64` `bank_natural_e5` states;
- `86` registered buffers per state payload;
- `64/64` settle-valid after `50` settle steps;
- runtime closer-force distribution `15 / 18 / 31` across the three planned
  force ranges, but **per-state closer metadata was not exported**;
- no `frame_approach`, aperture, or release state was captured;
- midpoint clearance minimum `.5448` m and median `.7108` m.

The source-A payload is useful evidence about the natural E5 basin. Its zero
settle-failure count is scoped only to this exported payload; it cannot be
promoted to a final-bank or P3 invariant result.

### Source B and final-bank status

Source B was launched as a constructed, settle-valid capture with 50 settle
steps, but the requested override set
`staged_reset_ratios=[0,0,0,0,1,0]`. During environment construction,
`StagedTaskBase` asserted:

```text
AssertionError: staged_reset_ratios[0] must be greater than 0
```

The producer exited without `source_b_constructed_r5.pt`. The final builder
then failed because Source B was missing, so
`logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt`
does not exist. Source B therefore supplies no settle-valid states, and the
final bank supplies no canonical start states.

The earlier r4 Source-A attempt is retained as a separate failure: its exporter
found no Stage-4 snapshots after settle. r5 fixed that filter and produced the
partial Source-A payload, but did not resolve Source B or final-bank admission.

### Closer-bucket readiness

The three planned closer buckets were `2.5–5`, `5–9`, and `9–12 N·m`. Source A
has only the aggregate `15/18/31` runtime distribution; because force was not
stored per state, no state can be assigned to a bucket for P1 reporting.

| Source / bucket | Episodes with admissible bucket metadata | Passage / panel metrics | Verdict |
| --- | ---: | --- | --- |
| Source A / `2.5–5` | N/A (aggregate only) | N/A | `BLOCKED` |
| Source A / `5–9` | N/A (aggregate only) | N/A | `BLOCKED` |
| Source A / `9–12` | N/A (aggregate only) | N/A | `BLOCKED` |
| Source B / all buckets | 0 | N/A | `RUNTIME FAIL` |

## P1 — canonical anchor and door probe

P1 is **`NOT_RUN/BLOCKED` at environment construction**, because the final
bank file required by Pull-v5 was absent. The anchor runner started its command
but produced no terminal metrics (`metrics_eval.json` was missing); the root
error was `FileNotFoundError: Pull-v5 state bank is required before v5
construction`. The planned deterministic anchor count is therefore `1/3`
attempts, not a completed anchor result.

The door probe is `BLOCKED/INCONCLUSIVE`. No closer-bucket episodes were
admitted, and no frame-passage, panel-contact, or release number can be
reported. In particular, this is **not** a passage rate of `0`.

## P2 — paired intervention

The P2 control construction failed on the same missing-bank prerequisite. The
receipt records `control_started=true`, `control_terminal_records=false`, and
`intervention_started=false`; metrics were not produced. The static override
contract (base action slice preserved, arm/gripper default pose, and no
out-of-threshold activation) is a **STATIC PASS only**, not runtime evidence.

| Pair | Persistent release | +1 s hinge | +2 s hinge | Frame passage | E6 | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Control | N/A | N/A | N/A | N/A | N/A | `BLOCKED` |
| Intervention | N/A | N/A | N/A | N/A | N/A | `NOT_RUN / BLOCKED` |

K25 persistent-release, hinge-hold, E6, G4, and G7 evidence is therefore
`INCONCLUSIVE`; static action semantics do not turn an unlaunched intervention
into a runtime finding.

## P3/P4 — dual-source DV boundary

P3 was not authorized after the bank and P1 prerequisites failed. No training,
checkpoint, canonical-start eval, natural-start eval, or P4 continuation was
run. Do not synthesize 16+16 episode rows or checkpoint values.

### 2 × 2 dual-source DV table

The verified v4-B row is a historical natural-start reference, not a v5
dual-source result. Its six v4-B checkpoint cells each had 16 episodes with
`frame_approach=0/16`, `frame_passage=0/16`, `E6=0/16`, `E7=0/16`, and
`complete=0/16`; the v4-B release curve was `2/16, 2/16, 2/16, 2/16, 0/16,
3/16` in seed0 step250/500/750 then seed1 step250/500/750 order.

| Cell / reference | GPU | p | Seed | Canonical frame passage | Natural frame passage | E6 / E7 / complete | Status / reason |
| --- | ---: | ---: | ---: | --- | --- | --- | --- |
| v4-B historical baseline (six 16-episode cells) | — | — | 0/1 | N/A (no canonical source) | `0/16` in every cell | `0/16 / 0/16 / 0/16` in every cell | `RUNTIME PASS` historical v4 reference |
| M-s0 | 4 | 0.5 | 0 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN`: unresolved bank/P1 prerequisite |
| M-s1 | 5 | 0.5 | 1 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN`: unresolved bank/P1 prerequisite |
| C-s0 | 6 | 0.9 | 0 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN`: unresolved bank/P1 prerequisite |
| C-s1 | 7 | 0.9 | 1 | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN`: unresolved bank/P1 prerequisite |

There is no P3 evidence from which to infer a canonical/natural difference,
catastrophic forgetting, or a positive/negative v5 policy effect. P3 and P4
remain `NOT_RUN`; no G2 causal interpretation is admissible.

## Census before/after and ten invariants

### Census before/after

| Boundary | Stage0 / Stage1 / Stage2 / Stage3 / Stage4 / Stage5 | Verdict |
| --- | --- | --- |
| v4-B before P3 (r5 census) | `12800 / 64 / 64 / 64 / 64 / 0` | `RUNTIME PASS` |
| v5 after P3 | N/A — P3 not run | `NOT_RUN` |

### Ten-invariant evidence

Invariant 9 cannot be passed without a P3 dual-source evaluator, and Invariant
10 is only partially evidenced by the exported Source-A payload; neither is a
final-bank/P3 PASS.

| # | Invariant | Exact available evidence | v5 verdict |
| ---: | --- | --- | --- |
| 1 | `fake_e4` | v4-B historical analysis counter `0`; no v5 P1/P2/P3 counter emitted | `REFERENCE ONLY / NOT_RUN` |
| 2 | `stage4_snapshot_below_hinge_gate` | v4-B historical analysis counter `0`; r5 census Stage-4 hinge range is above `.25` | `REFERENCE ONLY / NOT_RUN` |
| 3 | `dont_push_before_true_stage3_to4` | v4-B historical analysis counter `0`; no v5 episode analysis | `REFERENCE ONLY / NOT_RUN` |
| 4 | `target_root_before_aperture_ready` | v4-B historical analysis counter `0`; no v5 episode analysis | `REFERENCE ONLY / NOT_RUN` |
| 5 | `corridor_active_before_aperture_ready` | v4-B historical analysis counter `0`; no v5 episode analysis | `REFERENCE ONLY / NOT_RUN` |
| 6 | `complete_without_frame_passage` | v4-B historical analysis counter `0`; no v5 episode analysis | `REFERENCE ONLY / NOT_RUN` |
| 7 | `frame_approach_active_before_aperture_ready` | v4-B historical analysis counter `0`; no v5 episode analysis | `REFERENCE ONLY / NOT_RUN` |
| 8 | `frame_approach_active_after_frame_passage` | v4-B historical analysis counter `0`; no v5 episode analysis | `REFERENCE ONLY / NOT_RUN` |
| 9 | canonical starts never enter natural-start DV | No P3 dual-source eval was launched | `NOT_RUN` (cannot PASS) |
| 10 | failed settle states never enter the state bank | Source A exported `64/64` settle-valid states (`0` source-A failures); Source B and final bank are absent | `PARTIAL / INCONCLUSIVE` (not a final-bank PASS) |

The source-A settle result is intentionally scoped to the exported Source-A
payload. It does not certify the absent final bank, and invariant 9 cannot be
evaluated until a P3 dual-source DV exists.

## G1–G12 contingency log

The following records the plan gates without converting blocked phases into
scientific outcomes.

| Gate | Status | Evidence/adjudication |
| --- | --- | --- |
| G1 | `BLOCKED / NOT_REACHED` | P1 had no admissible bucket passage because bank construction failed. |
| G2 | `NOT_RUN` | The “P1 all-zero with passing anchor” branch was never reached; no lattice or causal verdict. |
| G3 | `BLOCKED` | Anchor construction failed on the missing-bank prerequisite; this is not a probe passage result. |
| G4 | `INCONCLUSIVE` | P2 intervention did not start; no release-persistence comparison. |
| G5 | `NOT_RUN` | No P3 canonical-start cell existed from which to test passage. |
| G6 | `NOT_RUN` | No P3 canonical-positive/natural-zero cell existed. |
| G7 | `NOT_RUN` | No P3 all-zero result existed; no waypoint or maintenance fork was authorized. |
| G8 | `BLOCKED` | Source B failed at environment construction before settle capture; Source A alone cannot complete the required bank. |
| G9 | `TRIGGERED — infrastructure failure` | r3 launcher, r4 guard, r5 load-only, Source B, P1, and P2 failures were preserved with tracebacks/receipts. |
| G10 | `NOT_TRIGGERED` | No P3 matrix was launched; no partial GPU-occupancy branch was needed. |
| G11 | `TRIGGERED — minimum closure` | The minimum P0 + blocked P1/P2 evidence was sufficient to stop without forcing invalid P3 work. |
| G12 | `NOT_RUN` | No C-arm natural-start training/eval existed to test degradation. |

## Runtime resources and waits

The recorded phase requests were GPU 6 for the r5 census/load, GPU 7 for
Source-A/Source-B bank work, GPU 4 for the P1 anchor command, and GPU 5 for the P2 control. Source B
also reached IsaacSim construction on its assigned logical `cuda:0` before its
reset-ratio assertion. The planned P3 leases (GPUs 4–7) were never acquired
for training. The logs show normal IsaacSim startup “wait” messages and CUDA
enumeration warnings, but no measured wait duration or concurrent P3 occupancy;
this report does not infer a GPU scheduling result from those messages.

## Review provenance and contract boundary

The formal review provenance remains **one r2 review wave with verdict `FAIL`**.
The r3–r5 targeted repairs and runtime evidence above are not a second review
and must not be described as a reviewer PASS. No reward-scale change, stage
split, or load-optimizer drift is claimed by this closure report. The only
observed load-path issue is the unresolved bank-injection guard before the
checkpoint loader.

## Evidence and artifact index

Paths below are repository-relative unless shown as absolute in the recorded
receipt:

- `logs_eval/a2_piper_pull_v5/p0_v4b_census/P0_A_v4_B_seed1_r5/CENSUS_RECEIPT.json`
  and `pull_v5_census.json` — valid r5 census.
- `logs_eval/a2_piper_pull_v5/p0_v4b_census/P0_A_v4_B_seed1_r5/runner.log` —
  census runtime and resolved-load-mode evidence.
- `logs_eval/a2_piper_pull_v5/p0_v4b_census/P0_A_v4_B_seed1/P0_A_RUNTIME_FAILURE_RECEIPT.json`
  — r3 launcher failure.
- `logs_eval/a2_piper_pull_v5/p0_v4b_census/P0_A_v4_B_seed1_r4/P0_A_RUNTIME_FAILURE_RECEIPT_r4.json`
  — r4 guard failure.
- `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_p0_load_only_r5/P0_LOAD_R5_RUNTIME_FAILURE_RECEIPT.json`
  and its `runner.log` — r5 load-only failure.
- `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/source_a_actor_e5_r5.pt`
  and `source_a_actor_e5_r5.runner.log` — partial Source-A payload/runtime.
- `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/source_b_constructed_r5.runner.log`
  and `STATE_BANK_R5_SOURCE_B_COMMAND.log` — Source-B assertion and missing
  payload.
- `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/STATE_BANK_R5_SOURCE_A_COMMAND.log`
  — final builder failure due missing Source B.
- `logs_eval/a2_piper_pull_v5/p1_anchor_r5_final/P1_ANCHOR_R5_FINAL_COMMAND.log`
  and `anchor_canonical_attempt1/runner.log` — P1 construction boundary.
- `logs_eval/a2_piper_pull_v5/p2_intervention_r5_final/P2_R5_FINAL_FAILURE_RECEIPT.json`
  and `p2_intervention_r5_final/control/runner.log` — P2 construction boundary.
- `scriptsFORhuman/pull_v5/evidence_zip_work/P0_C_EVIDENCE_ZIP_RECEIPT.md` and
  `a2_piper_pull_v1_to_v4_evidence_20260811.zip` — P0-c archive receipt and
  archive.
- `scriptsFORhuman/pull_v4/PULL_V4_ANALYSIS.json` and
  `scriptsFORhuman/pull_v4/PULL_V4_ROUND_REPORT.md` — verified v4-B historical
  baseline and inherited invariant reference.
- `scriptsFORhuman/pull_task/a2_piper_pull_v5_bridge_occupancy_plan_20260812.md`
  — phase, DV, invariant, and G1–G12 contract.

## Closure and next admissible action

The round is closed with stopping condition **false**. A future occupancy/
traversal round must first produce a valid two-source bank with per-state
closer metadata and real holding-near-frame/release captures, repair the
pure-A/builder path and load-only guard, and make P1/P2 bank independence
explicit. Only after an admissible P1 result may the G2 lattice or a new policy
fork be considered. Existing panel-contact/recontact tails are not regrasp or
brace evidence.
