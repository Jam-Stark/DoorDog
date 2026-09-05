# pull-v26.8 backbone reducer contract

Schema: `a2_piper_pull_v26_8_backbone_reducer_v1`.

`reduce.py` consumes one frozen natural-evaluation milestone.  Its paths are:

```text
<train_root>/<cell>/resolved_config.yaml
<eval_root>/<cell>_STEP<step>/<side>/metrics_eval.json
<eval_root>/<cell>_STEP<step>/<side>/a2_v14_per_env_records.json
<eval_root>/<cell>_STEP<step>/<side>/stage2_5_step_trace.json
<eval_root>/<cell>_STEP<step>/<side>/.hydra/runtime_config.yaml
```

Every cell-side is exact 64 first episodes: `completed_episodes`, terminal diagnostics, and per-env records each have exactly env ids `0..63`.  The source trace intentionally captures only Stage2–5 rows, so its env ids are a checked subset of those exact64 terminal ids; absent trace rows mean a zero duration count for `D` and `open_hold`, and unavailable trace-only aggregates are reported as `null`.  Evaluation is `checkpoint_load_mode=full`, `auto_load_latest=false`, 64 eval envs, natural fixed side, and `enable_staged_reset=false`.  The train config is passed to `verify.validate_config` before any metrics are read.

| Output | Source and definition |
|---|---|
| `D` | Per trace env, handle position at least `0.6 rad` for at least 25 consecutive control steps. |
| `S3+`, `S4+`, `S5+` | `metrics_eval.json.episode_max_stage_reached >= 3`, `>= 4`, `>= 5` respectively. |
| `open_hold` | Per trace env, hinge position at least `0.25 rad` and `both_contact=true` for at least 25 consecutive control steps. |
| `complete` | Terminal diagnostic `terminal_reasons == "complete"`. |
| `K5` | Per trace env, maximum `a2_stage2_squeeze_streak >= 5`. |
| `E2` through `E7` | Counts of `pull_v0_episode.event_reached` for `E2_TENSILE_CAPTURE`, `E3_LATCH_RELEASE`, `E4_POSITIVE_HINGE_RETAINED`, `E5_CLEARANCE_DECISION`, `E6_PATH_REVERSAL_ENTRY`, `E7_WHOLE_BODY_CLEAR`. |
| `arm_j4_p95` | Nearest-rank p95 of trace `arm_joint_pos[3]`. |
| `arm_j4_limit_residence_step_share` | Trace share where `abs(1.745 - arm_j4) < 1e-3`. |
| `press_handle_contact_force_p50` | Nearest-rank p50 of sum of two `handle_contact_force_norm` values on handle-at-least-0.6 trace steps. |
| `over_force_step_share` | Trace share with `over_force=true`. |
| `integrity_violations` | `0` after every terminal `pull_v0_episode` passes the existing `validate_a2_pull_episode` event dependency/time-order contract.  Validation uses the runtime's `a2_pull_threshold_mode`: sequential event predecessors for `report_only`, and `A2_PULL_HARD_GATE_EVENT_PREDECESSORS` for `hard_gate`.  An invalid record fails the reducer immediately. |

The E labels and stage counters are deliberately not substituted for one another.  Numeric stages are `0=walk`, `1=pregrasp`, `2=grasp`, `3=OPEN`, `4=SWING`, `5=THROUGH`.  `K5` is Stage2 grasp evidence.  `E2` is tensile capture and remains a report item.  `E3` is latch release, while `S3+` is task-stage high-water.  `E4` is positive hinge retained; `S4+` is a task-stage high-water that also depends on runtime advancement conditions.  `E5` is clearance decision, `E6` is path-reversal entry, and `E7` is whole-body clear.  `complete` remains a terminal outcome.  `D` and `open_hold` are trace-derived duration tests.  None of these event labels is inferred from a stage number.

Per-cell unlatch outcomes use `D`: `BILATERAL_UNLATCH_SUPPORTED` for LEFT at least 8 and RIGHT at least 32; `LEFT_RECOVERED_RIGHT_REGRESSED` for LEFT at least 8 and RIGHT below 32; `LEFT_STILL_STRUCTURALLY_ZERO` for LEFT zero and RIGHT at least 32; otherwise `BILATERAL_UNLATCH_NOT_LEARNED`.  A milestone is Wave-2 eligible only with two or more supported cells.  Opening/full labels are only report labels: one cell with both E4 at least 16 is `PULL_OPENING_EMERGED`; two cells with both E4 at least 32 is `PULL_OPENING_BILATERAL`; one cell with both E7 at least 8 is `PULL_FULL_CHAIN_OBSERVED`.

`g1_reduce.py` takes matched bilateral old/fixed exact64 terminal metrics and matched all-RIGHT old/fixed exact64 terminal metrics.  It validates each current pull episode record.  Bilateral LEFT target quaternions must differ by `180.00 +/- 0.05` degrees; bilateral RIGHT and all-RIGHT target quaternions must be bit-identical.  The all-RIGHT pair proves the enabled mirror switch is a legal no-op.
