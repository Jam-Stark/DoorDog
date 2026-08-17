# C-B2H v19 大规模 Camera Eval 报告

日期：2026-08-10 HKT

## 结论先行

预固定判据命中 **(c) 混合**，暂归类为 **暂归类/可见性归因 INCONCLUSIVE**。Teacher−Student gap 为 `9.9609375 pp`（Teacher `255/256`，Student `459/512`），处在设计预设的 5–10 pp 边界；正式 Stage2 contact/streak 信号明确，但 direct visibility share 是 UNKNOWN，不能把本轮写成当前 camera 充分。

因此不调用判据 (a) 或 (b)，而归入混合/可见性归因 INCONCLUSIVE。三次 visibility capture 都在产生合法逐集指标前 fail-fast 停止；较高 handle height 在几何比较中与 failure 相关，但在缺少 direct visual metrics 时，不能把该关联标注为视觉原因而不是 kinematic/contact 原因。

本轮建议：不基于这些数据默认开启双 D435i depth，也不默认增加 wrist camera；若后续单独批准 perception ablation，先测试已有 D435 depth，再考虑硬件 wrist camera。主要下一项 policy work 仍是另行批准的 targeted Stage2 contact-continuity DAgger，本任务没有训练。

本报告不画图：对 768 条逐集证据，精确 audit tables 比图形更清晰，且本次交付要求为 Markdown。

## 1. 总体成功率与置信区间

| Controller | Success | Total | Rate | Wilson 95% CI |
|---|---:|---:|---:|---:|
| Student | 459 | 512 | 89.6484375% | [86.7078065%, 91.9985466%] |
| Teacher | 255 | 256 | 99.6093750% | [97.8209025%, 99.9310118%] |
| Teacher − Student | — | — | **9.9609375 pp** | — |

## 2. Per-seed successes

| Seed | Student | Teacher（seed 0–15） |
|---:|---:|---:|
| 0 | 15/16 | 16/16 |
| 1 | 16/16 | 16/16 |
| 2 | 14/16 | 16/16 |
| 3 | 13/16 | 16/16 |
| 4 | 14/16 | 16/16 |
| 5 | 13/16 | 16/16 |
| 6 | 16/16 | 16/16 |
| 7 | 14/16 | 16/16 |
| 8 | 15/16 | 16/16 |
| 9 | 15/16 | 16/16 |
| 10 | 14/16 | 16/16 |
| 11 | 15/16 | 16/16 |
| 12 | 15/16 | 15/16 |
| 13 | 14/16 | 16/16 |
| 14 | 15/16 | 16/16 |
| 15 | 12/16 | 16/16 |
| 16 | 13/16 | — |
| 17 | 16/16 | — |
| 18 | 13/16 | — |
| 19 | 16/16 | — |
| 20 | 15/16 | — |
| 21 | 15/16 | — |
| 22 | 15/16 | — |
| 23 | 13/16 | — |
| 24 | 13/16 | — |
| 25 | 14/16 | — |
| 26 | 14/16 | — |
| 27 | 14/16 | — |
| 28 | 14/16 | — |
| 29 | 14/16 | — |
| 30 | 14/16 | — |
| 31 | 16/16 | — |

## 3. Failure stage / reason distribution

| Controller | Failure stage | Count |
|---|---:|---:|
| Student | 0 | 15 |
| Student | 1 | 2 |
| Student | 2 | 35 |
| Student | 4 | 1 |
| Teacher | 2 | 1 |

| Controller | Failure terminal reason | Count |
|---|---|---:|
| Student | `stage_overtime` | 53 |
| Teacher | `stage_overtime` | 1 |

## 4. Student failure env-id overlap / Jaccard

Student failure env sets are reported for all 32 seeds in `aggregate_stats.json`. There are `496` seed pairs: `486` evaluated pairs with non-empty union and `10` undefined empty-union pairs. Mean Jaccard over evaluated pairs is `0.061728`; intersection-nonempty pair count is `81`. This quantifies overlap without assigning a value to undefined pairs or promoting it to causality.

| Seed pair | Intersection env IDs | Jaccard |
|---|---|---:|
| 0 / 3 | [4] | 0.3333333 |
| 0 / 18 | [4] | 0.3333333 |
| 0 / 25 | [4] | 0.5000000 |
| 0 / 27 | [4] | 0.5000000 |
| 2 / 16 | [12] | 0.2500000 |
| 2 / 20 | [12] | 0.5000000 |
| 2 / 21 | [14] | 0.5000000 |
| 2 / 28 | [12] | 0.3333333 |
| 3 / 16 | [9] | 0.2000000 |
| 3 / 18 | [4] | 0.2000000 |
| 3 / 24 | [9] | 0.2000000 |
| 3 / 25 | [4, 11] | 0.6666667 |
| 3 / 27 | [4] | 0.2500000 |
| 4 / 7 | [13] | 0.3333333 |
| 4 / 26 | [13] | 0.3333333 |
| 4 / 27 | [13] | 0.3333333 |
| 5 / 7 | [2] | 0.2500000 |
| 5 / 15 | [2, 5] | 0.4000000 |
| 5 / 23 | [2] | 0.2000000 |
| 5 / 24 | [5] | 0.2000000 |
| 5 / 28 | [2] | 0.2500000 |
| 7 / 15 | [2] | 0.2000000 |
| 7 / 23 | [2] | 0.2500000 |
| 7 / 26 | [13] | 0.3333333 |
| 7 / 27 | [13] | 0.3333333 |
| 7 / 28 | [2] | 0.3333333 |
| 8 / 11 | [8] | 1.0000000 |
| 8 / 15 | [8] | 0.2500000 |
| 8 / 18 | [8] | 0.3333333 |
| 8 / 22 | [8] | 1.0000000 |
| 8 / 23 | [8] | 0.3333333 |
| 8 / 29 | [8] | 0.5000000 |
| 9 / 10 | [7] | 0.5000000 |
| 9 / 13 | [7] | 0.5000000 |
| 9 / 26 | [7] | 0.5000000 |
| 10 / 12 | [6] | 0.5000000 |
| 10 / 13 | [6, 7] | 1.0000000 |
| 10 / 23 | [6] | 0.2500000 |
| 10 / 26 | [7] | 0.3333333 |
| 10 / 29 | [6] | 0.3333333 |
| 10 / 30 | [6] | 0.3333333 |
| 11 / 15 | [8] | 0.2500000 |
| 11 / 18 | [8] | 0.3333333 |
| 11 / 22 | [8] | 1.0000000 |
| 11 / 23 | [8] | 0.3333333 |
| 11 / 29 | [8] | 0.5000000 |
| 12 / 13 | [6] | 0.5000000 |
| 12 / 23 | [6] | 0.3333333 |
| 12 / 29 | [6] | 0.5000000 |
| 12 / 30 | [6] | 0.5000000 |
| 13 / 23 | [6] | 0.2500000 |
| 13 / 26 | [7] | 0.3333333 |
| 13 / 29 | [6] | 0.3333333 |
| 13 / 30 | [6] | 0.3333333 |
| 15 / 18 | [8, 15] | 0.4000000 |
| 15 / 22 | [8] | 0.2500000 |
| 15 / 23 | [2, 8] | 0.4000000 |
| 15 / 24 | [5, 15] | 0.4000000 |
| 15 / 28 | [2] | 0.2000000 |
| 15 / 29 | [8] | 0.2000000 |
| 15 / 30 | [15] | 0.2000000 |
| 16 / 20 | [12] | 0.3333333 |
| 16 / 24 | [9] | 0.2000000 |
| 16 / 28 | [12] | 0.2500000 |
| 18 / 22 | [8] | 0.3333333 |
| 18 / 23 | [8] | 0.2000000 |
| 18 / 24 | [15] | 0.2000000 |
| 18 / 25 | [4] | 0.2500000 |
| 18 / 27 | [4] | 0.2500000 |
| 18 / 29 | [8] | 0.2500000 |
| 18 / 30 | [15] | 0.2500000 |
| 20 / 28 | [12] | 0.5000000 |
| 22 / 23 | [8] | 0.3333333 |
| 22 / 29 | [8] | 0.5000000 |
| 23 / 28 | [2] | 0.2500000 |
| 23 / 29 | [6, 8] | 0.6666667 |
| 23 / 30 | [6] | 0.2500000 |
| 24 / 30 | [15] | 0.2500000 |
| 25 / 27 | [4] | 0.3333333 |
| 26 / 27 | [13] | 0.3333333 |
| 29 / 30 | [6] | 0.3333333 |
| Empty-union pairs | undefined / excluded | — |

## 5. Paired Student/Teacher outcomes, seeds 0–15

The machine-readable artifact contains all 256 `(seed, env_id)` rows. The compact audit table below reports every paired seed and the differing env IDs.

| Seed | Student success | Teacher success | Student-only envs | Teacher-only envs | Both-failure envs |
|---:|---:|---:|---|---|---|
| 0 | 15/16 | 16/16 | [] | [4] | [] |
| 1 | 16/16 | 16/16 | [] | [] | [] |
| 2 | 14/16 | 16/16 | [] | [12, 14] | [] |
| 3 | 13/16 | 16/16 | [] | [4, 9, 11] | [] |
| 4 | 14/16 | 16/16 | [] | [0, 13] | [] |
| 5 | 13/16 | 16/16 | [] | [2, 3, 5] | [] |
| 6 | 16/16 | 16/16 | [] | [] | [] |
| 7 | 14/16 | 16/16 | [] | [2, 13] | [] |
| 8 | 15/16 | 16/16 | [] | [8] | [] |
| 9 | 15/16 | 16/16 | [] | [7] | [] |
| 10 | 14/16 | 16/16 | [] | [6, 7] | [] |
| 11 | 15/16 | 16/16 | [] | [8] | [] |
| 12 | 15/16 | 15/16 | [8] | [6] | [] |
| 13 | 14/16 | 16/16 | [] | [6, 7] | [] |
| 14 | 15/16 | 16/16 | [] | [1] | [] |
| 15 | 12/16 | 16/16 | [] | [2, 5, 8, 15] | [] |

## 6. Success-vs-failure Stage2 comparisons

Values are per-episode first-episode trace metrics; seconds use validated `4/200 = 0.02 s` control dt.

| Controller | Outcome | n | Max squeeze streak mean | Both-contact steps mean | Longest both-contact steps mean | Stage2 duration steps mean |
|---|---|---:|---:|---:|---:|---:|
| Student | success | 459 | 5.000000 | 9.592593 | 5.028322 | 131.873638 |
| Student | failure | 53 | 0.622642 | 2.037736 | 0.622642 | 226.528302 |
| Teacher | success | 255 | 5.000000 | 8.803922 | 5.000000 | 161.121569 |
| Teacher | failure | 1 | 4.000000 | 18.000000 | 4.000000 | 325.000000 |

Full q25/median/q75 plus success-minus-failure means are in `aggregate_stats.json`; no direct visual quantity is substituted for these contact metrics.

## 7. Success-vs-failure 17-field geometry comparisons

Numeric rows show mean / q25 / median / q75 and Mann–Whitney U, two-sided p, and rank-biserial effect. Categorical rows show success/failure counts and rates.

### Numeric fields

| Controller | Field | Success mean [q25, median, q75] | Failure mean [q25, median, q75] | U | p | Rank-biserial |
|---|---|---|---|---:|---:|---:|
| Student | `doorWidth` | 0.948296 [0.867219, 0.956269, 1.024201] | 0.948602 [0.892883, 0.941980, 1.000330] | 12127.000000 | 0.971840 | -0.003001 |
| Student | `doorHeight` | 2.058211 [1.984561, 2.059176, 2.136563] | 2.027555 [1.953730, 2.023486, 2.106952] | 14584.000000 | 0.017643 | 0.198997 |
| Student | `doorHandleHeight` | 0.897502 [0.873800, 0.896523, 0.921956] | 0.912713 [0.885387, 0.926830, 0.940208] | 8498.000000 | 0.000326 | -0.301352 |
| Student | `doorHandleWidth` | 0.115367 [0.097180, 0.115367, 0.133339] | 0.116533 [0.099963, 0.116266, 0.134093] | 11738.000000 | 0.676861 | -0.034982 |
| Student | `doorWeight` | 99.603789 [90.251863, 99.536448, 109.448212] | 101.367893 [93.869525, 102.956467, 110.835395] | 11006.000000 | 0.256567 | -0.095162 |
| Student | `totalWallHeight` | 2.698312 [2.545359, 2.695868, 2.851957] | 2.680528 [2.531514, 2.647406, 2.853786] | 12849.000000 | 0.501772 | 0.056357 |
| Student | `axleLength` | 0.194449 [0.187136, 0.194276, 0.202037] | 0.194700 [0.187568, 0.194193, 0.202882] | 12026.000000 | 0.893133 | -0.011304 |
| Student | `handleLength` | 0.124629 [0.116887, 0.124176, 0.132152] | 0.125992 [0.119820, 0.125578, 0.131287] | 11023.000000 | 0.263621 | -0.093764 |
| Student | `hookLength` | 0.050326 [0.045370, 0.051037, 0.055507] | 0.049442 [0.044739, 0.049284, 0.053407] | 13227.000000 | 0.297241 | 0.087434 |
| Student | `handleRadius` | 0.012987 [0.011941, 0.012949, 0.014062] | 0.012635 [0.011711, 0.012331, 0.013801] | 14241.000000 | 0.041681 | 0.170798 |
| Student | `hingeDriveMaxForce` | 3.512339 [3.047926, 3.469817, 3.993670] | 3.670662 [3.333340, 3.660271, 4.128145] | 10175.000000 | 0.051246 | -0.163481 |
| Student | `hingeDriveStiffness` | 5.496162 [3.010220, 5.493124, 7.904600] | 5.311474 [3.381973, 5.474241, 7.595959] | 12652.000000 | 0.632274 | 0.040161 |
| Student | `handleDriveMaxForce` | 1.495917 [1.262351, 1.507832, 1.710981] | 1.514996 [1.278763, 1.515771, 1.726730] | 11670.000000 | 0.628790 | -0.040572 |
| Teacher | `doorWidth` | 0.949570 [0.864387, 0.959309, 1.024911] | 0.810064 [0.810064, 0.810064, 0.810064] | 241.000000 | 0.117188 | 0.890196 |
| Teacher | `doorHeight` | 2.051365 [1.969860, 2.051934, 2.132581] | 2.054793 [2.054793, 2.054793, 2.054793] | 123.000000 | 0.968750 | -0.035294 |
| Teacher | `doorHandleHeight` | 0.901265 [0.876623, 0.900904, 0.927732] | 0.888295 [0.888295, 0.888295, 0.888295] | 163.000000 | 0.726562 | 0.278431 |
| Teacher | `doorHandleWidth` | 0.116198 [0.099514, 0.115367, 0.134363] | 0.095652 [0.095652, 0.095652, 0.095652] | 205.000000 | 0.398438 | 0.607843 |
| Teacher | `doorWeight` | 100.132227 [90.251863, 100.099240, 110.345830] | 98.238138 [98.238138, 98.238138, 98.238138] | 142.000000 | 0.890625 | 0.113725 |
| Teacher | `totalWallHeight` | 2.698394 [2.548292, 2.681809, 2.855549] | 2.490395 [2.490395, 2.490395, 2.490395] | 218.000000 | 0.296875 | 0.709804 |
| Teacher | `axleLength` | 0.194742 [0.187373, 0.194591, 0.202687] | 0.190025 [0.190025, 0.190025, 0.190025] | 168.000000 | 0.687500 | 0.317647 |
| Teacher | `handleLength` | 0.124997 [0.118297, 0.124730, 0.132154] | 0.134331 [0.134331, 0.134331, 0.134331] | 51.000000 | 0.406250 | -0.600000 |
| Teacher | `hookLength` | 0.050332 [0.045058, 0.051172, 0.055014] | 0.045772 [0.045772, 0.045772, 0.045772] | 182.000000 | 0.578125 | 0.427451 |
| Teacher | `handleRadius` | 0.012872 [0.011803, 0.012795, 0.013977] | 0.011308 [0.011308, 0.011308, 0.011308] | 235.000000 | 0.164062 | 0.843137 |
| Teacher | `hingeDriveMaxForce` | 3.533912 [3.070296, 3.522841, 4.026534] | 4.118747 [4.118747, 4.118747, 4.118747] | 52.000000 | 0.414062 | -0.592157 |
| Teacher | `hingeDriveStiffness` | 5.473148 [3.192599, 5.436876, 7.706958] | 2.818508 [2.818508, 2.818508, 2.818508] | 198.000000 | 0.453125 | 0.552941 |
| Teacher | `handleDriveMaxForce` | 1.483653 [1.270998, 1.489148, 1.694903] | 1.789709 [1.789709, 1.789709, 1.789709] | 44.000000 | 0.351562 | -0.654902 |

### Categorical fields

| Controller | Field | Value | Success count/rate | Failure count/rate |
|---|---|---|---:|---:|
| Student | `doorHandleType` | `"lever"` | 459/459 (100.000000%) | 53/53 (100.000000%) |
| Student | `doorOpenLR` | `-1` | 459/459 (100.000000%) | 53/53 (100.000000%) |
| Student | `doorOpenIO` | `-1` | 459/459 (100.000000%) | 53/53 (100.000000%) |
| Student | `spawnHook` | `false` | 231/459 (50.326797%) | 24/53 (45.283019%) |
| Student | `spawnHook` | `true` | 228/459 (49.673203%) | 29/53 (54.716981%) |
| Teacher | `doorHandleType` | `"lever"` | 255/255 (100.000000%) | 1/1 (100.000000%) |
| Teacher | `doorOpenLR` | `-1` | 255/255 (100.000000%) | 1/1 (100.000000%) |
| Teacher | `doorOpenIO` | `-1` | 255/255 (100.000000%) | 1/1 (100.000000%) |
| Teacher | `spawnHook` | `false` | 130/255 (50.980392%) | 0/1 (0.000000%) |
| Teacher | `spawnHook` | `true` | 125/255 (49.019608%) | 1/1 (100.000000%) |

The higher-handle-height association is descriptive only; without visibility metrics it cannot be called visual rather than kinematic/contact.

## 8. Source counts, gaps, and defensive threshold

| Source | Expected | Observed | Gap |
|---|---:|---:|---:|
| student_formal_artifacts | 32 | 32 | 0 |
| teacher_formal_artifacts | 16 | 16 | 0 |
| customdata_diagnostic_artifacts | 32 | 32 | 0 |
| formal_episodes | 768 | 768 | 0 |
| stage2_trace_cases | 768 | 768 | 0 |
| visual_metric_cases | 768 | 0 | 768 |

### customData provenance qualification

The four exact formal overlaps are `door_handle_drive_max_force ↔ handleDriveMaxForce`, `door_handle_height ↔ doorHandleHeight`, `door_hinge_drive_max_force ↔ hingeDriveMaxForce`, and `door_weight ↔ doorWeight`. The remaining 13 preserved fields are deterministic seeded-provenance joins, not independently exact-observed formal values. Every per-episode record retains all 17 fields and its outcome association.

Student <70% defense status: **NOT_TRIGGERED** (observed `89.6484375%`). No contract/checkpoint/source downgrade was inferred.

## 9. Visibility capture gap

Status: **UNKNOWN**; capture status: `NOT_COLLECTED_AFTER_RETRY_LIMIT`. Valid direct visual metric artifacts: `0`. All 768 per-episode records set `visual_conditions.metrics` to JSON `null`; no numeric visual field was invented.

| Attempt | Root cause | Retained logs |
|---:|---|---|
| 1 | camera interface lookup failed: missing sensor d435i_left_portrait_up50_toeout6 | `/tmp/cb2h_visibility_failed_smoke_20260810_1815/visibility_student_gpu4/seed_00.runner.log`<br>`/tmp/cb2h_visibility_failed_smoke_20260810_1815/visibility_teacher_gpu5/seed_00.runner.log` |
| 2 | over-strict runtime contract rejected ego_camera.offset.pos tensor shape (expected three values) | `/tmp/cb2h_visibility_failed_smoke_20260810_1815/visibility_student_gpu4_r4/seed_00.runner.log`<br>`/tmp/cb2h_visibility_failed_smoke_20260810_1815/visibility_teacher_gpu5_r4/seed_00.runner.log` |
| 3 | over-strict sealed offset contract rejected the observed ego_camera pose as offset drift | `logs_eval/by_batch/cb2h_v19_toeout6_pitch50_largescale_camera_eval_20260810/visibility_student_gpu4/seed_00.runner.log`<br>`logs_eval/by_batch/cb2h_v19_toeout6_pitch50_largescale_camera_eval_20260810/visibility_teacher_gpu5/seed_00.runner.log` |

The missing visibility metrics leave the visual share UNKNOWN; this is not evidence of either camera sufficiency or camera insufficiency.

## 10. Mentor-ready paragraph

在固定 G2 契约下，我们完成了 Student 32 seeds × 16 env = 512 集（成功 459）和 true-action Teacher 16 seeds × 16 env = 256 集（成功 255）。Teacher−Student gap 为 9.9609375 个百分点，处于预设 5–10 个百分点边界；正式 Stage2 接触/连续 streak 统计和 Teacher `gt_actions` route audit 均有效，Student 失败没有形成稳定的 env-id 集合。相机可见性量化 lane 连续三次因接口/过严格 runtime contract 错误在指标生成前停止，因此 visual share 是 UNKNOWN，不能把较高 handle height 的失败关联解释为视觉问题。当前建议是不默认开启 D435 depth 或增加 wrist camera；如果之后单独批准感知 ablation，先验证已有 D435 depth。下一项应另行审批 targeted Stage2 contact-continuity DAgger，而不是本任务内训练。

## 11. Limitations

- 每个正式 `(seed, env_id)` 只有一条 first episode；same-seed replay drift、real-camera calibration、latency、exposure、deployment 与 generalization 不在本报告中宣称。
- Teacher 仅覆盖 seeds 0–15；paired table 只覆盖这 16 个共同 seed。
- 几何比较是描述性关联；Mann–Whitney p 值不构成视觉因果证明。
- Visibility capture stopped after its approved retry limit; no fallback projection or imputation was used.

## 12. Reproducibility

```bash
/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/analyze_cb2h_v19_largescale_camera_eval_20260810.py
```

Generated artifacts: `logs_eval/by_batch/cb2h_v19_toeout6_pitch50_largescale_camera_eval_20260810/summary/per_episode_records.json`, `logs_eval/by_batch/cb2h_v19_toeout6_pitch50_largescale_camera_eval_20260810/summary/aggregate_stats.json`, and this report.
