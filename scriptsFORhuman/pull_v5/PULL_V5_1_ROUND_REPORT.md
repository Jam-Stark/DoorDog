# A2+Piper Pull-v5.1 Round Report

## Executive outcome

Pull-v5.1 r2 closed under G3/G11 without reaching the stopping condition.
F1–F5 were repaired, F5 produced an actual load-only receipt, P2 produced a
complete significant paired result, Source-A produced a G8-admissible 191-row
bank, and P1 reached a real four-command anchor boundary. P1 did not pass its
known-good anchor after the three preregistered G3 corrections, so no door-side
bucket verdict exists and G2/P3/P4 were not authorized. There is no canonical
or natural-start frame-passage claim for v5.1.

## Method and review provenance

- Governing plan: `a2_piper_pull_v5_1_bridge_occupancy_repair`, with the Pull-v5
  scientific contract unchanged.
- Warm actor: Pull-v4 B, seed 1, step 750.
- Reward scales and stage topology: unchanged.
- Optimizer loading: explicitly disabled for every v5.1 training route.
- GPU scope: physical GPUs 4–7 only.
- Formal review provenance: one r1 review wave returned `FAIL`. Its findings
  were targeted-fixed in r2 and are accepted only through runtime validation;
  no second reviewer PASS is claimed.

## F1–F5 repair evidence

The r1 implementation was retained and repaired in place. The single formal
review wave remained `FAIL`; r2 treated its findings as the complete targeted
repair backlog and did not request another reviewer verdict.

| Item | r2 implementation boundary | Current evidence |
| --- | --- | --- |
| F1 | Bank injection is an explicit per-config boolean; disabled routes return before bank access. | The injection-disabled F5, Source-A, P2, and bank-build routes all ran without reading the final bank. Training injection remains enabled only in the four P3 configs. |
| F2 | P2 uses the Pull-v4 B config and v4 plan ID; intervention state and action replacement live in the evaluator. | Complete paired runtime PASS: all selected base slices were bitwise unchanged, and the v4 command audit found zero v5 environment keys. |
| F3 | Source B writes robot and door state through IsaacLab articulation writers after evaluator reset, then settles and admits only valid constructed rows. | Three G9 attempts exhausted: Hydra append error, pre-trace settle ordering, then all constructed rows rejected by settle admission. G8 pure-natural downgrade triggered. |
| F4 | Legacy E5 rows are retained exactly; delayed E5+2 s/E5+4 s captures use real elapsed control steps. | Legacy payload repair passed: 64 rows, 86 unchanged buffers, force buckets `15/18/31`. Both delayed runtime payloads were produced. |
| F5 | Load-only exits before optimizer/batches and records actor/critic/optimizer/scheduler state plus the policy-only normalization observation. | Attempt 1 reached IsaacSim but failed trainer initialization because batch size 1 was not divisible by four mini-batches. Attempt 2 is `ACTUAL`: actor loaded from `policy_state_dict`; critic, optimizer, and scheduler were not loaded and were reset. |

The first Source-A/Source-B runtime launch reached Hydra composition and failed
because an existing `a2_pull_v5_reset_source` key was incorrectly appended with
`+`. G9 attempt 1 was retained, the command was corrected against the actual
config, and attempt 2 was launched. This failure is infrastructure evidence,
not a scientific zero.

Source-B attempt 2 moved construction after evaluator reset but entered the
settle loop before Stage2–5 trace initialization. The ordering was corrected
without disabling telemetry. Attempt 3 then reached the full settle admission
gate and rejected every constructed row. Under G8 there is no fourth attempt;
the remaining bank path is explicitly pure natural.

The F5 receipt records `checkpoint_load_mode=policy_only` and
`load_optimizer=false`. It also records the observed methodology fact that the
evaluation wrapper requested `policy_only` but normalized its effective mode
to `full`. Pull-v5.1 does not alter that wrapper.

## P2 paired intervention

The primary endpoint is the paired K25 no-handle-contact outcome. Adjudication
uses a one-sided exact McNemar/binomial test at alpha 0.05. A blocked or invalid
pair is never converted to a zero outcome.

Attempt 1 completed one episode in each of 16 control and 16 intervention
environments. It was correctly invalidated: one fixture triggered too late to
provide +2 s evidence and one never triggered. Attempt 2 requested two
episodes per environment, but the asynchronous evaluator stopped after 37
control and 35 intervention terminal rows rather than exactly 32. The initial
receipt incorrectly treated this normal overshoot as invalid. G9 attempt 3
fixed the receipt parser, not the immutable simulator fixtures: it used the
overshoot as a screening pool, matched 32 `(episode_index, env_id)` keys, found
no door-scenario mismatch, admitted 22 strict pairs, and selected the first 16
in stable order. Rejected rows retain missing-trigger, missing-+2 s, unmatched,
or selection-quota reasons.

The selected control group achieved K25 in `3/16`; intervention achieved
`16/16`. The 13 discordant pairs all changed from control failure to
intervention success, with no pair changing in the opposite direction and
three ties. The preregistered one-sided exact McNemar/binomial test therefore
gave `p=0.0001220703125` with SciPy `1.15.3`, below alpha `0.05`. P2 selects
**release persistence as the binding constraint**. Every selected pair has
complete trigger and +2 s hinge evidence, matched door parameters, and equal
policy/applied base slices. E6 and frame passage remained `0/16` in both
fixtures; the intervention is a mechanism result, not traversal success.
Control retained hinge at or above 1.6 rad in `16/16` at both +1 s and +2 s
(median `1.7363/1.8639` rad). Intervention retained it in `12/16` and `5/16`
(median `1.6312/1.4949` rad), while improving median minimum frame distance
from `0.7410` m to `0.6503` m. Thus forced release creates the preregistered
K25 behavior and modestly advances the base, but also exposes door reclosure;
it does not by itself create E6 or passage.

## G13 state bank

The manifest must contain one row per bank index with provenance, closer force
and bucket, capture tier, settle status/steps, and source row. Strict admission
requires at least 64 rows, all three closer buckets, at least eight
`bank_natural_e5_plus` rows, and at least sixteen `bank_constructed` rows.

The legacy Source-A E5 payload was upgraded offline to source schema v2 without
overwriting its r5 input. Direct tensor/buffer comparison, including NaN-aware
equality, preserved all 64 rows and 86 buffers. Per-row closer force was joined
from the 64 terminal records by exact environment ID; the resulting bucket
counts are `2.5-5: 15`, `5-9: 18`, and `9-12: 31`. Every repaired row has
`bank_natural_e5` provenance, tier `e5`, delay zero, settle steps 50, and source
row `0..63`.

Source B exhausted its three G9 attempts and produced no admitted constructed
row, so G8 was invoked explicitly. The final pure-natural bank is
`PASS_G8_PURE_A`: 191 rows total, comprising 64 `bank_natural_e5` and 127
`bank_natural_e5_plus` rows. Capture tiers are E5 `64`, E5+2 s `64`, and E5+4 s
`63`; closer buckets are `2.5-5:45`, `5-9:54`, and `9-12:92`. All 191 manifest
rows carry provenance, hinge-closer force, bucket, capture tier, settle-valid
status, settle steps, and source-row metadata. Constructed count is `0`, the
only waived G13 class; total count, per-row metadata, all three buckets, and the
near-frame delayed-state requirement remain satisfied.

## P1 anchor and closer-stratified probe

The open-field anchor precedes door-side evidence. Door results are reported
separately for the `2.5-5`, `5-9`, and `9-12` N m closer buckets.

G9 attempt 1 terminated before any waypoint/yaw measurement because the eval
wrapper inherited inactive push-task diagnostic reward names
(`push_door_handle`, `push_door_hinge`) under the pull config. No door probe
started. The failure is retained as infrastructure evidence and is not scored
as an anchor or passage zero; the runner was corrected to bind the already
active pull diagnostic list explicitly before attempt 2. Attempt 2 produced a
measured PASS for 16 `straight_minus_x` rows, but that receipt was rejected as
insufficient for rule 5 because the runner had not exercised the other three
registered primitives. Its first door-side job then exposed the separate B2
bug: the explicit canonical provider selected 16 rows correctly, but the shared
injection function incorrectly demanded staged capacity 64. Before final
attempt 3, anchor mode was changed to require 16/16 rows for each of all four
primitives, and the provider capacity check was separated from the unchanged
G13/payload minimum.

The first complete four-primitive anchor then measured waypoint arrival
`64/64` and `command_solvable=64/64`, but yaw arrival only `32/64`:
`straight_minus_x` and `side_step` passed, while `turn_then_forward` and `arc`
failed. This is the first scientific G3 attempt, distinct from the three G9
implementation attempts above. Receipt telemetry motivated a targeted
stale-frame hypothesis: initialize yaw from the exact high-level root state
written to simulation instead of the post-write articulation cache. G3
correction 2 implemented that hypothesis. The failed receipt remains a
command-library failure, not door passage evidence.

G3 attempt 2 again produced waypoint `64/64`, solvable `64/64`, and yaw
`32/64`; target-frame initialization therefore was not the remaining cause.
Requested/realized yaw exposed the actual HOMIE sign contract: target
`-0.55` ended near `-0.98`, and target `+0.35` ended near `+1.54`, so the
closed-loop correction drove farther away after overshoot. The third and final
G3 correction inverts only this probe yaw-action polarity; targets, XY
commands, gains, tolerances, reward scales, and training actions remain
unchanged.

G3 attempt 3 nevertheless repeated the same measured boundary: all four
primitives produced 16 rows, waypoint arrival was `64/64`, command solvability
was `64/64`, and yaw arrival was `32/64`. Its receipt is `FAIL` with
`correction_retry=2`. The three closer buckets therefore have no admitted
episodes and no passage denominator. P1 closes as **BLOCKED at the known-good
anchor**, not as an all-zero door probe; G2 and P3 are forbidden by the plan.

## P3/P4 dual-source DV

Canonical and natural episodes remain separate evidence populations. No
canonical episode is counted in the natural-start DV.

| Cell | Checkpoint | Canonical frame passage | Natural frame passage | E6 | E7 | Complete | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Pull-v4 B seed1 reference | 750 | N/A (no v5.1 bank provider) | 0/16 | 0/16 | 0/16 | 0/16 | Historical natural-start baseline |
| M-s0 | N/A | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | Blocked by G3 anchor |
| M-s1 | N/A | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | Blocked by G3 anchor |
| C-s0 | N/A | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | Blocked by G3 anchor |
| C-s1 | N/A | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | Blocked by G3 anchor |

No checkpoint was trained, so no dual-source evaluator ran and no canonical
episode could contaminate a natural-start denominator. These NOT_RUN cells are
not zero-passage observations.

## Ten invariants

All ten invariants require zero violations. Invariant 9 is canonical-to-natural
source contamination; invariant 10 is admission of a failed-settle bank row.

1. `fake_e4`
2. `stage4_snapshot_below_hinge_gate`
3. `dont_push_before_true_stage3_to4`
4. `target_root_before_aperture_ready`
5. `corridor_active_before_aperture_ready`
6. `complete_without_frame_passage`
7. `frame_approach_active_before_aperture_ready`
8. `frame_approach_active_after_frame_passage`
9. `canonical_not_counted_as_natural_start`
10. `failed_settle_not_in_bank`

All ten counters were present and zero in the 64 terminal rows of the final
four-primitive anchor attempt. The G13 manifest independently contains no
`settle_valid=false` row. P3/eval-specific invariant evidence is NOT_RUN rather
than inferred from the anchor.

## G1–G13 decision log

- **G1:** NOT_EVALUATED because no closer-bucket door probe was admitted.
- **G2:** NOT_TRIGGERED; all-zero door passage was never observed under an
  anchor PASS.
- **G3:** triggered. Three complete four-primitive correction attempts each
  measured waypoint `64/64`, solvable `64/64`, but yaw `32/64`; the final
  receipt remained `FAIL`. The round stopped at the registered implementation
  boundary.
- **G4:** triggered by P2 (`13` favorable discordant pairs, `0` unfavorable,
  `p=0.0001220703125`); release persistence is binding.
- **G5–G7:** NOT_RUN because P3 was not authorized.
- **G8:** triggered after the third Source-B attempt reached the settle gate and
  rejected every constructed row. A documented pure-natural bank passed all
  non-constructed G13 requirements.
- **G9:** used for the three Source-B failures, the P2 evidence-chain repair,
  and three P1 implementation failures before the scientific G3 series.
  Blocked/invalid receipts were preserved and never scored as zero passage.
- **G10:** not triggered; all visible GPU4–7 processes belonged to `baoquanc`.
- **G11:** invoked for truthful minimum closure after the G3 stop. F1/F2/F5,
  complete P2, P1's reached boundary, report, and memory are present.
- **G12–G13:** G12 NOT_RUN; G13 is `PASS_G8_PURE_A` with the 191-row manifest.

## Artifact index

Completed, directly inspected artifacts:

- F5: `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_load_receipts/pull_v5_1_policy_only.json`
- P2: `logs_eval/a2_piper_pull_v5/p2_intervention_v5_1/P2_INTERVENTION_RECEIPT.json`
- Source-A: `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/source_a_actor_e5_v5_1.pt`, `source_a_actor_e5_plus2s_v5_1.pt`, and `source_a_actor_e5_plus4s_v5_1.pt`
- Final bank: `logs_rl/a2_piper_full_stage_a2_pull/pull_v5_state_bank/pull_v5_state_bank.pt`
- G13 receipt and row manifest: `pull_v5_state_bank.pt.receipt.json` and `pull_v5_state_bank_manifest.json` in the same directory
- Final P1 boundary: `logs_eval/a2_piper_pull_v5/pull_v5_1_p1_anchor_probe/anchor_attempt3/P1_anchor_natural_attempt3_RECEIPT.json`
- Preserved G9/G3 logs: `scriptsFORhuman/pull_v5/runtime/`

The pre-existing evidence ZIP and 75 projected v1–v4 traces remain preserved,
unmodified, and outside the v5.1 commits. No hash was computed or recorded.
