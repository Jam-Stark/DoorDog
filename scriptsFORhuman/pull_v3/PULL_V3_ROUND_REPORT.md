# A2+Piper Pull v3 Round Report

**Plan:** `a2_piper_pull_v3_release_then_cross_traversal`
**Round date:** 2026-08-10–11 HKT
**Status:** COMPLETE_NEGATIVE — G2 scientific-negative conclusion; no positive in-frame crossing was observed.
**Evidence identity:** path-bound; no hashes are recorded.

## Executive conclusion

G2 triggered. Across the six Wave1 checkpoint cells (two seeds × steps 250/500/750; 96 terminal episodes), the producer metrics report `E6=0/16`, `E7=0/16`, and `episode_goal_reached=0/16` in every cell. Some cells contain deliberate release and first negative-X motion, but frame approach, frame passage, planar crossing, and detour are all zero. The policy therefore reaches the release/negative-X diagnostic branch without producing the required through-frame traversal. This is a negative result for the v3 release-then-cross capability, not a positive crossing or completion claim.

The G2 branch is the measured “negative-X motion exists but does not approach the frame” case. No reward scale was changed after this finding. G10 also triggered because one cell recorded a maximum post-release recontact count of 18; this is recorded as evidence only, with no in-round arm re-extension implementation.

## 1. C1–C7 implementation summary

| Item | Implemented contract and evidence |
|---|---|
| C1 | v3 guard plan id: `a2_piper_pull_v3_release_then_cross_traversal`; v0/v1/v2 branches remain outside this round. |
| C2 | Diagnostic-neutral budget expansion: `max_episode_length_s=24`, `max_stage_time=[250,100,100,100,250,300]`. |
| C3 | Latched `frame_passage` requires the in-frame geometry and panel-clear predicate; E6, E7, and completion remain frame-gated. |
| C4 | Pull-local `penalty_a2_stage3_stage4_open_command` is masked to zero once `aperture_ready` is latched, so an intentional release is no longer penalized. Squeeze/grasp income naturally becoming zero after release is preserved; no extra release reward scale was introduced. |
| C5 | Pull-side corridor terms use the recorded scales `a2_corridor_door_wide=4.2666667` and `a2_corridor_clean_passage=1.0`, with aperture/stage gating. |
| C6 | Report-only swept-arc signed clearance, base path length, base reversal count, panel-contact steps, and post-release recontact telemetry; no new body-contact penalty was added because the v2 panel-contact median is zero. |
| C7 | Warm-start v2 Wave2 seed1 step750 actor, `policy_only` training, 256 environments × 750 batches, checkpoints at steps 250/500/750; resolved configs are preserved under each `pull_v3_T_wave1_seed*` run. |

## 2. D0-lite and smoke

### D0-lite attempts

| Attempt | Preserved path | Result |
|---|---|---|
| 1 | `logs_eval/a2_piper_pull_v3/D0_lite_seed1_step750_attempt1_config_fail/runner.log` | Hydra failed closed because strict composition rejected missing `env.config.a2_v20_R1_plan_id`. |
| 2 | `logs_eval/a2_piper_pull_v3/D0_lite_seed1_step750_attempt2_reward_order_fail/runner.log` | Runtime telemetry failed closed because raw `a2_corridor_door_wide` was not finite. |
| 3 | `logs_eval/a2_piper_pull_v3/D0_lite_seed1_step750_attempt3_pre_c6_fix/runner.log` and `scriptsFORhuman/pull_v3/D0_LITE_RECEIPT_attempt3_pre_c6_fix.json` | 16 episodes completed with the six zero invariants; preserved as a pre-C6-fix attempt. |
| Final | `logs_eval/a2_piper_pull_v3/D0_lite_seed1_step750/` and `scriptsFORhuman/pull_v3/D0_LITE_RECEIPT.json` | PASS: 16 episodes, 16×804 steps, all six invariants zero, E6/E7 zero, and corridor raw pre-aperture income zero. |

The frozen v2 Wave2 seed1 step750 actor used for D0 is `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave2_relay_seed1/model_step_000750.pt`. D0 is a negative baseline by design; it does not establish v3 traversal capability.

### Smoke

The smoke run `pull_v3_T_smoke_seed0` completed with 64 environments × 50 batches, 3,200 episodes, 204,800 total timesteps, and `model_step_000050.pt` saved. The runner log reports total time 671.15 s and a natural completion.

## 3. Wave1 training and checkpoint/evaluation topology

| Run | Physical launch assignment | Environments × batches | Total timesteps | Iteration time | Total time | Saved checkpoints |
|---|---|---:|---:|---:|---:|---|
| `pull_v3_T_wave1_seed0` | GPU2 launch, process `cuda:0` | 256×750 | 12,288,000 | 14.99 s | 11,249.84 s | `model_step_000250.pt`, `000500.pt`, `000750.pt`, `last.pt` |
| `pull_v3_T_wave1_seed1` | GPU3 launch, process `cuda:0` | 256×750 | 12,288,000 | 14.78 s | 11,037.62 s | `model_step_000250.pt`, `000500.pt`, `000750.pt`, `last.pt` |

The six evaluation cells are exactly:

`seed0/step250`, `seed0/step500`, `seed0/step750`, `seed1/step250`, `seed1/step500`, and `seed1/step750`.

Each cell uses 16 environments with one episode per environment and produces `metrics_eval.json`, `stage2_5_step_trace.json`, diagnostic metadata, and the runner log under `logs_eval/a2_piper_pull_v3/<cell>/eval/`. Terminal diagnostics retain all 16 episodes. The stage2–5 trace domain is validated separately against terminal `stage_buf`.

## 4. Main comparison table

`complete` is the producer `episode_goal_reached` field; it is intentionally distinct from E7. `Inv` reports invariant violations: v2 supplies the four inherited counters, while each v3 row supplies all six.

| Cell | E0–E4 | E5 | E6 | E7 | complete | release | first −X | frame passage | detour | Inv |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2 Wave2 seed1 step750 baseline | 16/16 | 16/16 | 0/16 | 0/16 | 0/16 | N/A | N/A | N/A | N/A | 0 (4 inherited) |
| v3 Wave1 seed0 step250 | 16/16 | 15/16 | 0/16 | 0/16 | 0/16 | 7/16 | 7/16 | 0/16 | 0/16 | 0 |
| v3 Wave1 seed0 step500 | 15/16 | 15/16 | 0/16 | 0/16 | 0/16 | 2/16 | 2/16 | 0/16 | 0/16 | 0 |
| v3 Wave1 seed0 step750 | 15/16 | 15/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0 |
| v3 Wave1 seed1 step250 | 16/16 | 16/16 | 0/16 | 0/16 | 0/16 | 1/16 | 1/16 | 0/16 | 0/16 | 0 |
| v3 Wave1 seed1 step500 | 16/16 | 16/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0 |
| v3 Wave1 seed1 step750 | 16/16 | 16/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 | 0 |

The v2 baseline facts are E0–E5 16/16, E6/E7 0/16, terminal length 654 steps, panel-contact median 0 and maximum 21. The v3 terminal-length summaries are 804 steps in every cell median; seed0 steps 500 and 750 include one 250-step early terminal, while their maximum remains 804.

## 5. E5→E7 and release/negative-X/frame timeline

No cell has an observed E7, so `E5→E7` is `N/A` (zero valid samples) everywhere. Release and negative-X telemetry is:

| Cell | Release count | Release step median [range] | First −X count | Release→first −X median [range] | Frame approach | Frame passage | Detour | E5→E7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| seed0 step250 | 7/16 | 612 [538, 737] | 7/16 | 0 [0, 37] | 0/16 | 0/16 | 0/16 | N/A |
| seed0 step500 | 2/16 | 447 [417, 477] | 2/16 | 0 [0, 0] | 0/16 | 0/16 | 0/16 | N/A |
| seed0 step750 | 0/16 | N/A | 0/16 | N/A | 0/16 | 0/16 | 0/16 | N/A |
| seed1 step250 | 1/16 | 790 [790, 790] | 1/16 | 0 [0, 0] | 0/16 | 0/16 | 0/16 | N/A |
| seed1 step500 | 0/16 | N/A | 0/16 | N/A | 0/16 | 0/16 | 0/16 | N/A |
| seed1 step750 | 0/16 | N/A | 0/16 | N/A | 0/16 | 0/16 | 0/16 | N/A |

The negative-X observations are therefore not through-frame crossings: no frame-approach or frame-passage event was recorded, and no planar detour was recorded.

## 6. C6 signed-clearance and base-avoidance telemetry

Values are episode summaries from the final analysis. Clearance is the swept-arc signed margin in metres; base path is metres; reversal and recontact counts are per episode. `med [min, max]` is used where all 16 episodes supplied the metric.

| Cell | Signed clearance med [min, max] | Base path med [min, max] | Reversals med [max] | Panel contact med [max] | Post-release recontact med [max] |
|---|---:|---:|---:|---:|---:|
| v2 baseline | N/A | N/A | N/A | 0 [21] | N/A |
| seed0 step250 | −0.049 [−0.244, 0.127] | 3.469 [2.909, 4.289] | 21.5 [36] | 0 [76] | 0 [1] |
| seed0 step500 | 0.024 [−0.079, 0.416] | 3.197 [0.475, 4.733] | 19.0 [48] | 0 [86] | 0 [18] |
| seed0 step750 | 0.076 [−0.043, 0.353] | 3.524 [0.576, 4.496] | 13.5 [32] | 0 [0] | 0 [0] |
| seed1 step250 | −0.054 [−0.091, 0.107] | 3.172 [2.393, 5.017] | 23.0 [37] | 0 [20] | 0 [0] |
| seed1 step500 | 0.082 [0.002, 0.179] | 3.438 [2.752, 4.333] | 18.0 [39] | 0 [0] | 0 [0] |
| seed1 step750 | 0.089 [0.051, 0.172] | 3.634 [2.953, 4.685] | 15.5 [31] | 0 [0] | 0 [0] |

The largest recontact count, 18, is the G10 trigger. This round records it and does not add the long-term arm re-extension behavior.

## 7. Corridor income and integrity invariants

The D0 receipt reports `corridor_raw_pre_aperture=0`. In the six Wave1 cells, both `corridor_door_wide_pre_aperture_steps` and `corridor_clean_passage_pre_aperture_steps` are zero, and the combined `corridor_active_before_aperture_ready` invariant is zero in every cell. The training runner’s terminal iteration reports nonzero episode-sum income terms—seed0 `a2_corridor_door_wide=0.8559`, `a2_corridor_clean_passage=0.2092`; seed1 `0.8372` and `0.2088`—but these observed sums do not imply pre-aperture activation; the trace gate remains zero.

All six invariant counters are zero for every formal cell and the final D0 receipt:

1. `fake_e4`
2. `stage4_snapshot_below_hinge_gate`
3. `dont_push_before_true_stage3_to4`
4. `target_root_before_aperture_ready`
5. `corridor_active_before_aperture_ready`
6. `complete_without_frame_passage`

## 8. Exact G1–G10 decision log

| Rule | Analyzer status | Evidence and action |
|---|---|---|
| G1 | NOT_TRIGGERED | E6 is 0/16 in every seed/checkpoint; no Wave2 relay and no seed2 run. |
| G2 | TRIGGERED | E6=0; release/negative-X exists only in a subset and no frame approach/passage occurs. Scientific conclusion is negative; no scale change. |
| G3 | NOT_TRIGGERED | Planar crossing and detour are both zero; no crossing was observed to classify as a bypass. |
| G4 | NOT_TRIGGERED | Both seeds classify as G2; no opposite seed conclusion and no third seed. |
| G5 | NOT_TRIGGERED | Panel-contact median is 0 in all six cells, matching the v2 median 0; no new penalty. |
| G6 | NOT_TRIGGERED | The fail-closed analyzer records no overtime-progress adjudication trigger requiring another budget round. |
| G7 | NOT_TRIGGERED for formal Wave1 | Both formal training runs and all six evaluations completed. The two earlier D0 implementation failures remain preserved as fixed attempts, not formal training crashes. |
| G8 | NOT_TRIGGERED | The authorized GPU2/GPU3 launch topology completed; no lease-unavailable branch was taken. |
| G9 | NOT_TRIGGERED | Wave1, six-cell evaluation, analysis, and report completed within the round. |
| G10 | TRIGGERED | Maximum post-release recontact is 18 at seed0 step500; record only, no in-round arm re-extension change. |

## 9. Trace-contract analyzer failure and root fix

The first formal analysis attempt failed because `_validate_trace_coverage` required all 16 terminal environment IDs in `stage2_5_step_trace.json`. The producer trace is conditional: it contains only terminal environments whose producer `stage_buf` is in `{2,3,4,5}`. For example, seed0 step500 has a terminal env at stage 0 with no stage2–5 trace rows.

The targeted root fix strictly validates every terminal `stage_buf`, derives the expected trace-ID set from the stage2–5 domain, and retains exact equality plus one producer episode identity per trace environment. It does not synthesize rows or relax the terminal denominator. After the fix, the affected seed0/seed1 step500/750 payloads load and the six-cell comparator produces `PULL_V3_ANALYSIS_WAVE1.json` and the final available `PULL_V3_ANALYSIS.json`. No Wave2/seed2 analysis artifact is claimed.

## 10. Review boundary

One code-review wave returned FAIL with bounded findings covering D0 discovery, invariant gating, trace coverage, iterative output safety, seed2 family naming, concurrent child reaping, completion-source semantics, and stale reporting. Those findings were targeted-fixed, followed by the trace-domain repair above after the actual analyzer failure. The user’s one-review cap was honored: there is no second reviewer PASS and this report does not claim one.

## 11. Artifact and path inventory

- Report and tooling: `scriptsFORhuman/pull_v3/PULL_V3_ROUND_REPORT.md`, `analyze_pull_v3.py`, `run_pull_v3_training.py`, `run_pull_v3_eval_all_checkpoints.py`, `run_pull_v3_orchestration.py`.
- Analysis: `scriptsFORhuman/pull_v3/PULL_V3_ANALYSIS_WAVE1.json` and `scriptsFORhuman/pull_v3/PULL_V3_ANALYSIS.json` (six Wave1 cells; no Wave2/seed2 cells).
- D0: `scriptsFORhuman/pull_v3/D0_LITE_RECEIPT.json`, preserved pre-C6 receipt, and `logs_eval/a2_piper_pull_v3/D0_lite_seed1_step750*` attempt directories.
- Smoke: `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v3_T_smoke_seed0/`, including `model_step_000050.pt` and `runner.log`.
- Training: `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v3_T_wave1_seed0/` and `pull_v3_T_wave1_seed1/`, each with steps 250/500/750, `last.pt`, resolved `config.yaml`, and `runner.log`.
- Evaluation: `logs_eval/a2_piper_pull_v3/pull_v3_T_wave1_seed{0,1}_step{250,500,750}/`, each with metrics, terminal diagnostics, stage2/2–5 traces, metadata, Hydra logs, and runner log.

## 12. Evidence boundary and unverified claims

Runtime evidence consists of the D0 replay, smoke natural exit, two Wave1 training runs, and six 16-episode checkpoint evaluations. Static/read-only evidence consists of the fail-closed analyzer output, trace-contract repair reproduction, and this path-bound report cross-check.

The following remain unverified or deliberately not run: any positive E6/E7/producer completion, any successful through-frame crossing, conditional Wave2 relay, seed2, render QA, or a second reviewer PASS. No scale or threshold recommendation is made here; future traversal shaping remains a separate v4 TODO decision.
