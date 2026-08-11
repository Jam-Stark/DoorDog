# A2+Piper Pull v4 Round Report

**Plan:** `a2_piper_pull_v4_annuity_removal_and_frame_approach`
**Round date:** 2026-08-11 HKT
**Status:** COMPLETE_NEGATIVE — both arms retained zero frame traversal and zero producer completion.
**Evidence identity:** path-bound; no hashes are recorded.

## Executive conclusion

Pull-v4 tested two changes on the v3 release-then-cross contract. Arm A removed
the `a2_corridor_door_wide` annuity (L5 only); arm B made that same removal and
added signed `a2_pull_frame_approach=6.0` (L1). The frozen warm actor was the
v2 Wave2 seed1 step750 checkpoint. D0, smoke, four Wave1 trainings, twelve
baseline checkpoint evaluations, and six G6 extended evaluations completed with
natural exits and fail-closed analysis.

A/L5-only did not reverse extinction: its release curve was
`0/16,1/16,0/16,0/16,1/16,0/16`, versus the v3 baseline
`7/16,2/16,0/16,1/16,0/16,0/16`. B/L1 modestly preserved base release
(`2/16,2/16,2/16,2/16,0/16,3/16`) and the G6 extension increased release and
shortened frame-midpoint distance, but frame-approach, frame-passage, E6, E7,
and completion remained zero in every cell. Extra time therefore exposed a
release/proximity constraint but did not change the remaining primary outcome
bottleneck. No relay, seed2, or render QA was authorized by the adjudication.

## 1. Frozen comparison and runtime topology

Both arms forked the v3 traversal contract: the v2 Wave2 seed1 step750 warm
actor, `policy_only`, 256 environments × 750 batches, checkpoints at steps
250/500/750, the v3 frame-passage predicate, release mask, clean-passage term,
near-closed latch threshold, and six inherited invariants. A set
`a2_corridor_door_wide=0.0` and retained clean passage at `1.0`; B additionally
set `a2_pull_frame_approach=6.0` with signed raw telemetry and frame-passage
lockout. The frame reward is not an annuity and is not active before
`aperture_ready`.

The twelve primary cells are A/B × seed0/seed1 × step250/500/750, each with
16 evaluation episodes. Conditional stage2–5 traces use the producer domain
`stage_buf ∈ {2,3,4,5}`; terminal diagnostics retain all 16 episodes.

## 2. D0, smoke, and Wave1 execution evidence

### D0-lite

The final D0 used arm B with the frozen v2 actor. Two earlier launches failed
closed at Hydra composition: attempt 1 rejected a duplicate `auto_load_latest`
override and attempt 2 rejected a duplicate `num_envs` override. The corrected
launch completed the required replay.

| D0 result | Evidence |
|---|---|
| Topology | 16 episodes × 804 steps; all episodes natural exit |
| Traversal outcomes | E6 `0/16`, E7 `0/16`; completion `0/16` |
| Integrity | all eight invariants `0` |
| Disabled L5 term | door-wide raw min/max `0.0/0.0`; `executed=false` |
| Signed L1 raw | count `11689`; median `0.0`; range `[-1.0,1.0]` |
| Per-episode L1 income | median `-7.829`; range `[-19.590,7.303]` |
| G11 diagnostic | signed-income/net-motion correlation `0.993454`; sign alignment `16/16` |

### Smoke

Arm B smoke used 64 environments × 50 batches: 3,200 episodes and 204,800
timesteps. The runner natural-exited in `670.76 s`.

### Wave1 training

All four v2-warm Wave1 launches natural-exited at 256 × 750 with
12,288,000 timesteps and checkpoints at 250/500/750.

| Run | Total time |
|---|---:|
| A seed0 | 10,942.33 s |
| A seed1 | 11,139.88 s |
| B seed0 | 11,284.71 s |
| B seed1 | 11,014.08 s |

The twelve baseline evaluations each completed one 16-episode batch. The six
G6 extended evaluations were run only for arm B after the base analysis showed
terminal stage-4/5 overtime with remaining signed approach evidence.

## 3. Primary A/B × seed × checkpoint table

The `E0/E1/E2/E3/E4/E5/E6/E7` column is a count out of 16. `complete` is the
producer `episode_goal_reached` field, distinct from E7. Frame approach,
frame passage, and detour are each `0/16` in every row; `Inv` is the total
number of non-zero invariant counters.

| Cell | E0/E1/E2/E3/E4/E5/E6/E7 | complete | release | frame approach | frame passage | detour | Inv |
|---|---|---:|---:|---:|---:|---:|---:|
| v4 A seed0/250 | 16/15/14/14/14/14/0/0 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 A seed0/500 | 16/15/15/15/15/15/0/0 | 0/16 | 1/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 A seed0/750 | 16/16/16/16/16/15/0/0 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 A seed1/250 | 16/16/14/14/14/13/0/0 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 A seed1/500 | 16/15/15/15/15/15/0/0 | 0/16 | 1/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 A seed1/750 | 16/16/16/16/16/16/0/0 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 B seed0/250 | 16/16/16/16/16/15/0/0 | 0/16 | 2/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 B seed0/500 | 16/15/15/15/15/15/0/0 | 0/16 | 2/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 B seed0/750 | 16/16/16/16/16/16/0/0 | 0/16 | 2/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 B seed1/250 | 16/16/16/16/16/16/0/0 | 0/16 | 2/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 B seed1/500 | 16/16/16/16/16/16/0/0 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0 |
| v4 B seed1/750 | 16/16/16/16/16/16/0/0 | 0/16 | 3/16 | 0/16 | 0/16 | 0/16 | 0 |

All twelve rows have E6/E7/complete `0/16`; all approach/passage/detour
predicates are zero; and all eight invariant counters are zero.

## 4. Release comparison and frame distance

The release order is seed0 step250/500/750 followed by seed1 step250/500/750.

| Release curve | seed0/250 | seed0/500 | seed0/750 | seed1/250 | seed1/500 | seed1/750 |
|---|---:|---:|---:|---:|---:|---:|
| v3 Wave1 baseline | 7/16 | 2/16 | 0/16 | 1/16 | 0/16 | 0/16 |
| v4 A (L5 only) | 0/16 | 1/16 | 0/16 | 0/16 | 1/16 | 0/16 |
| v4 B (L5 + L1) | 2/16 | 2/16 | 2/16 | 2/16 | 0/16 | 3/16 |

Base frame-midpoint distance medians (metres), in the same checkpoint order,
were:

| Arm | Distance medians |
|---|---|
| A | `0.7126, 0.7252, 0.7186, 0.7370, 0.7618, 0.7685` |
| B | `0.7256, 0.7436, 0.7562, 0.7462, 0.7508, 0.7337` |

No base row had a frame-approach event, frame passage, planar crossing, or
detour. The midpoint-distance distributions are diagnostic distances, not
traversal success.

## 5. Episode-sum income accounting

The following are episode-sum medians from the validated base analyses. They
are accounting rows, not claims that a term is a useful creation signal. The
door-wide term is serialized as raw zero and not executed; the A arm has no
frame-approach term. Values are ordered by arm/seed/checkpoint.

| Cell | dont_push | target_root | pull_handle | pull_hinge | clean_passage | door_wide | frame_approach |
|---|---:|---:|---:|---:|---:|---:|---:|
| A0/250 | 31.322 | 23.599 | 2.323 | 30.600 | 9.220 | 0.000 | — |
| A0/500 | 31.024 | 44.628 | 7.278 | 25.260 | 10.390 | 0.000 | — |
| A0/750 | 30.483 | 54.675 | 6.311 | 27.120 | 10.010 | 0.000 | — |
| A1/250 | 29.290 | 35.068 | 5.541 | 27.660 | 9.480 | 0.000 | — |
| A1/500 | 29.889 | 46.666 | 3.449 | 25.440 | 10.480 | 0.000 | — |
| A1/750 | 28.992 | 47.029 | 7.309 | 30.480 | 9.930 | 0.000 | — |
| B0/250 | 26.673 | 32.181 | 6.870 | 26.915 | 9.380 | 0.000 | -4.981 |
| B0/500 | 30.641 | 48.250 | 5.574 | 22.860 | 10.160 | 0.000 | -0.173 |
| B0/750 | 31.826 | 54.751 | 5.136 | 26.820 | 9.750 | 0.000 | 2.835 |
| B1/250 | 28.987 | 42.532 | 3.752 | 28.620 | 9.550 | 0.000 | -8.599 |
| B1/500 | 24.479 | 53.590 | 9.507 | 26.220 | 10.180 | 0.000 | -1.453 |
| B1/750 | 25.559 | 57.206 | 9.205 | 27.360 | 10.020 | 0.000 | -0.304 |

The signed B income includes both positive and negative motion. D0 measured
the raw contract directly: median `0`, min `-1`, max `1`, with per-episode
income median `-7.829`. This is consistent with a signed creation signal, not
a standing annuity.

## 6. Eight integrity invariants

Every invariant counter is zero in the final D0, all twelve base cells, and all
six G6 extended cells:

1. `fake_e4`
2. `stage4_snapshot_below_hinge_gate`
3. `dont_push_before_true_stage3_to4`
4. `target_root_before_aperture_ready`
5. `corridor_active_before_aperture_ready`
6. `complete_without_frame_passage`
7. `frame_approach_active_before_aperture_ready`
8. `frame_approach_active_after_frame_passage`

The L5 disabled path therefore reports raw zero with
`corridor_door_wide_reward_executed=false`, while the frame-approach activation
guards remain structurally clean.

## 7. G6 extended diagnostic

G6 was triggered once because base B cells terminated in stage 4/5 overtime
while signed frame motion remained measurable. Each affected episode required
positive signed raw evidence and a corroborating decrease in midpoint distance
within the 20-step/50-step windows. The base-to-extended release and distance
readout is:

| Cell | Release base → G6 | Distance base → G6 (m) | Affected episodes |
|---|---:|---:|---:|
| B0/250 | 2 → 9 | 0.726 → 0.666 | 3/16 |
| B0/500 | 2 → 9 | 0.744 → 0.528 | 6/15 |
| B0/750 | 2 → 12 | 0.756 → 0.660 | 5/16 |
| B1/250 | 2 → 8 | 0.746 → 0.627 | 7/16 |
| B1/500 | 0 → 9 | 0.751 → 0.464 | 6/16 |
| B1/750 | 3 → 11 | 0.734 → 0.645 | 9/16 |

G6 did not create a frame-approach event: frame approach, E6, E7, and
completion stayed zero in all six extended cells, and all eight invariants
stayed zero. `changed_cell_count=0` for the outcome fields
`E6_rate/E7_rate/complete_rate`. Across the six base B cells, recontact had
maximum `10` and maximum per-cell median `0`; across the six G6 cells it had
maximum `108` and maximum per-cell median `3`.

## 8. G1–G11 adjudication and preplan log

The statuses below apply the v4 plan §5 rules to the terminal evidence.

| Gate | Status | Adjudication |
|---|---|---|
| G1 | NOT TRIGGERED | E6 was `0/16` in every A/B cell; no relay was started. |
| G2 | TRIGGERED — negative close | Both arms had E6 `0/16`; A did not reverse release extinction, and B did not create frame approach. No new scale was added. |
| G3 | NOT TRIGGERED | No planar crossing or detour was observed, so there was no bypass shape to classify. |
| G4 | NOT TRIGGERED | Seeds differed in release counts but not in the adjudicated E6 outcome; no third seed was needed. |
| G5 | NOT TRIGGERED | Base panel-contact medians were zero; no body-contact penalty was enabled. |
| G6 | TRIGGERED — exhausted once | B-only extended windows increased release/proximity evidence but changed no E6/E7/complete cell; no further extension was run. |
| G7 | NOT TRIGGERED | Four Wave1 trainings and all base/G6 evaluations completed with natural exits. |
| G8 | NOT TRIGGERED | The assigned four-launch topology completed; no GPU-availability branch was needed. |
| G9 | NOT TRIGGERED | The required Wave1, evaluation, analysis, and report evidence completed within scope. |
| G10 | TRIGGERED — record only | Base recontact max/median-max was `10/0`; G6 max/median-max was `108/3`. No arm-brace implementation was made. |
| G11 | NOT TRIGGERED | D0 signed raw was bounded to `[-1,1]`, correlation was `0.993454`, and sign alignment was `16/16`; no income-shape repair was required. |

The G2 close deliberately ends the round: no Wave2 relay, seed2, or rendering
lane was run.

## 9. Failure, targeted-fix, and review provenance

The first two D0 launches failed closed at configuration composition and were
preserved as diagnostic attempts. The corrected D0 path then completed and
produced the receipt used here. The fail-closed v4 analyzers accepted the
conditional stage2–5 trace domain, the terminal denominator, all eight
invariants, and the base/G6 outcome comparison.

The single formal static/code review wave returned **FAIL** with bounded
findings. Those findings were subsequently targeted-fixed and validated by
targeted static checks, the corrected D0, smoke, four natural-exit Wave1
trainings, twelve base evaluations, six G6 evaluations, and the fail-closed
analysis artifacts. The user’s one-review cap was honored: there was no second
review and no post-fix reviewer PASS claim.

## 10. Evidence boundary and unverified claims

Runtime evidence is limited to:

- `D0_LITE_RECEIPT.json` and its corrected B-arm replay;
- the B smoke runner receipt/log;
- four Wave1 training runner logs and their saved checkpoints;
- twelve base 16-episode evaluation payloads;
- six B-arm G6 evaluation payloads;
- `PULL_V4_ANALYSIS.json` and `PULL_V4_G6_ANALYSIS.json`.

The analysis `PASS` means the JSON metrics, terminal diagnostics, and
conditional stage2–5 traces passed their fail-closed validation. It does not
mean a positive traversal, release-level capability, or reviewer PASS.

The following were not executed in this round: conditional Wave2 relay, seed2,
render QA, pooled/holdout release evidence, or any arm-brace implementation.
No claim is made for those paths, and no threshold or reward recommendation is
issued beyond recording the measured negative result.

## 11. Conclusion and bounded follow-up

Pull-v4 is a completed negative round. Removing the wide-door annuity alone did
not reverse the v3 release extinction curve. Adding the signed frame-approach
term preserved some base release and, when given extra time, produced more
release and shorter midpoint distances, but it never produced a frame-neighbor
event or an E6/E7/complete outcome. The remaining bottleneck is therefore not
simply the release-time budget: the policy still lacks a reliable
frame-neighborhood/path-distribution behavior.

G10 is recorded as a bounded arm-brace future input only. No brace, relay,
seed2, rendering, or additional reward scale was introduced in this round.
