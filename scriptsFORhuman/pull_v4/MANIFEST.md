# Pull v1–v4 evidence excerpt manifest

This archive is a capped derivative excerpt, not a copy of whole evidence units. Original files remain in the repository and are never moved or deleted.

- Archive target: `a2_piper_pull_v1_to_v4_evidence_20260811.zip`
- Decimal byte cap: `500,000,000` bytes (final ZIP size is asserted after writing)
- Manifest reservation used during Tier-2 selection: `2,000,000` bytes
- Planned ZIP size with the generated manifest: `108,407,774` bytes
- Tier-1 inventory: 9 training configs, 1 G6 runtime-config exemplar, 75 formal metrics, and 12 available full training logs.
- Tier-1 missing inventory: 4 required v2 full runner logs, recorded explicitly below.
- Tier 3: none. No hidden continuation or additional tier was inferred.
- Render ordering note: R1→R4 is an operational inference from the enumerated render-directory order; no continuation or priority instruction was recovered.
- R1 runtime status: INCONCLUSIVE / NOT_RUN after exactly three failed launcher attempts; no fourth attempt was made and no behavioral claim is made.

## Tier byte report

| Tier | Included files | Source bytes | Compressed payload bytes |
| --- | ---: | ---: | ---: |
| Tier1 | 97 | 92,551,869 | 7,005,433 |
| Tier2 | 22 | 101,581,145 | 101,374,411 |
| Omitted Tier2 MP4s | 6 | 0 | not archived |

## Source provenance

`Archive path` is the flat path inside the ZIP. `Original repo-relative source` is resolved from this repository root. `Bytes` is the source-file byte count.

| Archive path | Original repo-relative source | Bytes | Category | Status |
| --- | --- | ---: | --- | --- |
| `configs/v0_p4_formal_seed0__config.yaml` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v0_p4_formal_seed0-20260805_211252/config.yaml` | 41,184 | config | INCLUDED |
| `configs/v1_A_seed0__config.yaml` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_A_seed0-20260809_025222/config.yaml` | 41,332 | config | INCLUDED |
| `configs/v1_B_seed0__config.yaml` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_B_seed0-20260809_025222/config.yaml` | 41,332 | config | INCLUDED |
| `configs/v1_R_seed0_retry2__config.yaml` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_R_seed0-20260809_110901_retry2/config.yaml` | 41,346 | config | INCLUDED |
| `configs/v2_W_wave1_seed0__config.yaml` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave1_seed0/config.yaml` | 41,377 | config | INCLUDED |
| `configs/v2_W_wave2_relay_seed1__config.yaml` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave2_relay_seed1/config.yaml` | 41,428 | config | INCLUDED |
| `configs/v3_T_wave1_seed0__config.yaml` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v3_T_wave1_seed0/config.yaml` | 41,414 | config | INCLUDED |
| `configs/v4_A_wave1_seed0__config.yaml` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_A_wave1_seed0/config.yaml` | 41,446 | config | INCLUDED |
| `configs/v4_B_wave1_seed0__config.yaml` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_B_wave1_seed0/config.yaml` | 41,446 | config | INCLUDED |
| `configs/v4_B_wave1_seed0_step250_g6__runtime_config.yaml` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed0_step250_g6_budget/hydra/.hydra/runtime_config.yaml` | 47,314 | runtime_config | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step250/eval/metrics_eval.json` | 361,764 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step500/eval/metrics_eval.json` | 362,298 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step750/eval/metrics_eval.json` | 362,471 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step1000__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step1000/eval/metrics_eval.json` | 362,310 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step1250__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step1250/eval/metrics_eval.json` | 362,478 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step1500__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step1500/eval/metrics_eval.json` | 362,651 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step1750__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step1750/eval/metrics_eval.json` | 362,795 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step2000__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step2000/eval/metrics_eval.json` | 362,225 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step2250__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step2250/eval/metrics_eval.json` | 362,564 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed0_step2500__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed0_step2500/eval/metrics_eval.json` | 362,051 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step250/eval/metrics_eval.json` | 362,456 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step500/eval/metrics_eval.json` | 361,794 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step750/eval/metrics_eval.json` | 359,990 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step1000__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step1000/eval/metrics_eval.json` | 361,167 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step1250__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step1250/eval/metrics_eval.json` | 361,562 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step1500__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step1500/eval/metrics_eval.json` | 362,230 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step1750__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step1750/eval/metrics_eval.json` | 361,407 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step2000__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step2000/eval/metrics_eval.json` | 359,047 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step2250__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step2250/eval/metrics_eval.json` | 359,520 | formal_metric | INCLUDED |
| `eval_metrics/v0_p4_event_funnel_seed1_step2500__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p4_event_funnel/seed1_step2500/eval/metrics_eval.json` | 360,344 | formal_metric | INCLUDED |
| `eval_metrics/v0_p5_release_candidate_seed0_step2500_render__metrics_eval.json` | `logs_eval/a2_piper_pull_v0/p5_release_candidate/seed0_step2500_render/eval/metrics_eval.json` | 45,522 | formal_metric | INCLUDED |
| `eval_metrics/v1_A_seed0_step250_retry1__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave1/A_seed0_step250_retry1/eval/metrics_eval.json` | 358,184 | formal_metric | INCLUDED |
| `eval_metrics/v1_A_seed0_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave1/A_seed0_step500/eval/metrics_eval.json` | 358,882 | formal_metric | INCLUDED |
| `eval_metrics/v1_A_seed0_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave1/A_seed0_step750/eval/metrics_eval.json` | 359,612 | formal_metric | INCLUDED |
| `eval_metrics/v1_B_seed0_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave1/B_seed0_step250/eval/metrics_eval.json` | 363,816 | formal_metric | INCLUDED |
| `eval_metrics/v1_B_seed0_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave1/B_seed0_step500/eval/metrics_eval.json` | 363,329 | formal_metric | INCLUDED |
| `eval_metrics/v1_B_seed0_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave1/B_seed0_step750/eval/metrics_eval.json` | 362,243 | formal_metric | INCLUDED |
| `eval_metrics/v1_A_seed1_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave2/A_seed1_step250/eval/metrics_eval.json` | 359,966 | formal_metric | INCLUDED |
| `eval_metrics/v1_A_seed1_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave2/A_seed1_step500/eval/metrics_eval.json` | 359,298 | formal_metric | INCLUDED |
| `eval_metrics/v1_A_seed1_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave2/A_seed1_step750/eval/metrics_eval.json` | 359,730 | formal_metric | INCLUDED |
| `eval_metrics/v1_B_seed1_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave2/B_seed1_step250/eval/metrics_eval.json` | 363,562 | formal_metric | INCLUDED |
| `eval_metrics/v1_B_seed1_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave2/B_seed1_step500/eval/metrics_eval.json` | 363,314 | formal_metric | INCLUDED |
| `eval_metrics/v1_B_seed1_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave2/B_seed1_step750/eval/metrics_eval.json` | 363,561 | formal_metric | INCLUDED |
| `eval_metrics/v1_R_seed0_step250_retry2__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave3/R_seed0_step250_retry2/eval/metrics_eval.json` | 365,230 | formal_metric | INCLUDED |
| `eval_metrics/v1_R_seed0_step500_retry2__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave3/R_seed0_step500_retry2/eval/metrics_eval.json` | 365,884 | formal_metric | INCLUDED |
| `eval_metrics/v1_R_seed0_step750_retry2__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave3/R_seed0_step750_retry2/eval/metrics_eval.json` | 364,968 | formal_metric | INCLUDED |
| `eval_metrics/v1_R_seed1_step250_retry2__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave3/R_seed1_step250_retry2/eval/metrics_eval.json` | 364,272 | formal_metric | INCLUDED |
| `eval_metrics/v1_R_seed1_step500_retry2__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave3/R_seed1_step500_retry2/eval/metrics_eval.json` | 365,289 | formal_metric | INCLUDED |
| `eval_metrics/v1_R_seed1_step750_retry2__metrics_eval.json` | `logs_eval/a2_piper_pull_v1/wave3/R_seed1_step750_retry2/eval/metrics_eval.json` | 364,942 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave1_seed0_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave1_seed0_step250/eval/metrics_eval.json` | 381,579 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave1_seed0_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave1_seed0_step500/eval/metrics_eval.json` | 382,061 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave1_seed0_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave1_seed0_step750/eval/metrics_eval.json` | 381,261 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave1_seed1_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave1_seed1_step250/eval/metrics_eval.json` | 382,044 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave1_seed1_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave1_seed1_step500/eval/metrics_eval.json` | 381,972 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave1_seed1_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave1_seed1_step750/eval/metrics_eval.json` | 382,057 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave2_relay_seed0_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave2_relay_seed0_step250/eval/metrics_eval.json` | 380,905 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave2_relay_seed0_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave2_relay_seed0_step500/eval/metrics_eval.json` | 381,038 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave2_relay_seed0_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave2_relay_seed0_step750/eval/metrics_eval.json` | 381,840 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave2_relay_seed1_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave2_relay_seed1_step250/eval/metrics_eval.json` | 379,984 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave2_relay_seed1_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave2_relay_seed1_step500/eval/metrics_eval.json` | 381,853 | formal_metric | INCLUDED |
| `eval_metrics/v2_W_wave2_relay_seed1_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v2/W_wave2_relay_seed1_step750/eval/metrics_eval.json` | 383,196 | formal_metric | INCLUDED |
| `eval_metrics/v3_T_wave1_seed0_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v3/pull_v3_T_wave1_seed0_step250/eval/metrics_eval.json` | 429,645 | formal_metric | INCLUDED |
| `eval_metrics/v3_T_wave1_seed0_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v3/pull_v3_T_wave1_seed0_step500/eval/metrics_eval.json` | 429,773 | formal_metric | INCLUDED |
| `eval_metrics/v3_T_wave1_seed0_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v3/pull_v3_T_wave1_seed0_step750/eval/metrics_eval.json` | 430,282 | formal_metric | INCLUDED |
| `eval_metrics/v3_T_wave1_seed1_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v3/pull_v3_T_wave1_seed1_step250/eval/metrics_eval.json` | 430,564 | formal_metric | INCLUDED |
| `eval_metrics/v3_T_wave1_seed1_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v3/pull_v3_T_wave1_seed1_step500/eval/metrics_eval.json` | 431,505 | formal_metric | INCLUDED |
| `eval_metrics/v3_T_wave1_seed1_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v3/pull_v3_T_wave1_seed1_step750/eval/metrics_eval.json` | 431,411 | formal_metric | INCLUDED |
| `eval_metrics/v4_A_wave1_seed0_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_A_wave1_seed0_step250/eval/metrics_eval.json` | 439,661 | formal_metric | INCLUDED |
| `eval_metrics/v4_A_wave1_seed0_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_A_wave1_seed0_step500/eval/metrics_eval.json` | 440,955 | formal_metric | INCLUDED |
| `eval_metrics/v4_A_wave1_seed0_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_A_wave1_seed0_step750/eval/metrics_eval.json` | 442,820 | formal_metric | INCLUDED |
| `eval_metrics/v4_A_wave1_seed1_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_A_wave1_seed1_step250/eval/metrics_eval.json` | 441,219 | formal_metric | INCLUDED |
| `eval_metrics/v4_A_wave1_seed1_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_A_wave1_seed1_step500/eval/metrics_eval.json` | 442,454 | formal_metric | INCLUDED |
| `eval_metrics/v4_A_wave1_seed1_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_A_wave1_seed1_step750/eval/metrics_eval.json` | 443,014 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed0_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed0_step250/eval/metrics_eval.json` | 444,335 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed0_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed0_step500/eval/metrics_eval.json` | 443,375 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed0_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed0_step750/eval/metrics_eval.json` | 444,391 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed1_step250__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed1_step250/eval/metrics_eval.json` | 444,999 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed1_step500__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed1_step500/eval/metrics_eval.json` | 445,247 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed1_step750__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed1_step750/eval/metrics_eval.json` | 444,052 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed0_step250_g6_budget__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed0_step250_g6_budget/eval/metrics_eval.json` | 444,151 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed0_step500_g6_budget__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed0_step500_g6_budget/eval/metrics_eval.json` | 443,815 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed0_step750_g6_budget__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed0_step750_g6_budget/eval/metrics_eval.json` | 444,933 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed1_step250_g6_budget__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed1_step250_g6_budget/eval/metrics_eval.json` | 444,745 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed1_step500_g6_budget__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed1_step500_g6_budget/eval/metrics_eval.json` | 444,821 | formal_metric | INCLUDED |
| `eval_metrics/v4_B_wave1_seed1_step750_g6_budget__metrics_eval.json` | `logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed1_step750_g6_budget/eval/metrics_eval.json` | 444,101 | formal_metric | INCLUDED |
| `training_logs/v1_A_seed0__train_stdout.txt` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_A_seed0-20260809_025222/train_stdout.txt` | 5,061,666 | training_log | INCLUDED |
| `training_logs/v1_A_seed1__train_stdout.txt` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_A_seed1-20260809_071140/train_stdout.txt` | 5,061,536 | training_log | INCLUDED |
| `training_logs/v1_B_seed0__train_stdout.txt` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_B_seed0-20260809_025222/train_stdout.txt` | 5,188,784 | training_log | INCLUDED |
| `training_logs/v1_B_seed1__train_stdout.txt` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_B_seed1-20260809_071140/train_stdout.txt` | 5,188,756 | training_log | INCLUDED |
| `training_logs/v1_R_seed0_retry2__train_stdout.txt` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_R_seed0-20260809_110901_retry2/train_stdout.txt` | 5,252,918 | training_log | INCLUDED |
| `training_logs/v1_R_seed1_retry2__train_stdout.txt` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_R_seed1-20260809_110901_retry2/train_stdout.txt` | 5,252,625 | training_log | INCLUDED |
| `training_logs/v3_T_wave1_seed0__runner.log` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v3_T_wave1_seed0/runner.log` | 5,383,690 | training_log | INCLUDED |
| `training_logs/v3_T_wave1_seed1__runner.log` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v3_T_wave1_seed1/runner.log` | 5,383,560 | training_log | INCLUDED |
| `training_logs/v4_A_wave1_seed0__runner.log` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_A_wave1_seed0/runner.log` | 5,320,139 | training_log | INCLUDED |
| `training_logs/v4_A_wave1_seed1__runner.log` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_A_wave1_seed1/runner.log` | 5,320,142 | training_log | INCLUDED |
| `training_logs/v4_B_wave1_seed0__runner.log` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_B_wave1_seed0/runner.log` | 5,383,889 | training_log | INCLUDED |
| `training_logs/v4_B_wave1_seed1__runner.log` | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_B_wave1_seed1/runner.log` | 5,383,759 | training_log | INCLUDED |
| `videos/R1_v2_W_wave2_seed1_step750__render_failure_receipt.json` | `logs_eval/a2_piper_pull_v4/renders/R1_v2_W_wave2_seed1_step750/renderings/render_failure_receipt.json` | 2,238 | render_failure_receipt | INCONCLUSIVE_NOT_RUN: exactly three failed launcher attempts; no fourth attempt per user contract |
| `videos/R2_v4_B_seed0_step750__render_outcome_receipt.json` | `logs_eval/a2_piper_pull_v4/renders/R2_v4_B_seed0_step750/renderings/render_outcome_receipt.json` | 4,422 | render_receipt | INCLUDED |
| `videos/R2_v4_B_seed0_step750__2026-08-11_22-27-51_env0000_episode0000_handle_side_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R2_v4_B_seed0_step750/renderings/2026-08-11_22-27-51_env0000_episode0000_handle_side_len804_reason-stage_overtime.mp4` | 3,531,445 | video | INCLUDED |
| `videos/R2_v4_B_seed0_step750__2026-08-11_22-27-51_env0000_episode0000_handle_top_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R2_v4_B_seed0_step750/renderings/2026-08-11_22-27-51_env0000_episode0000_handle_top_len804_reason-stage_overtime.mp4` | 5,949,519 | video | INCLUDED |
| `videos/R2_v4_B_seed0_step750__2026-08-11_22-27-51_env0000_episode0000_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R2_v4_B_seed0_step750/renderings/2026-08-11_22-27-51_env0000_episode0000_len804_reason-stage_overtime.mp4` | 1,476,553 | video | INCLUDED |
| `videos/R2_v4_B_seed0_step750__2026-08-11_22-27-51_env0001_episode0000_handle_side_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R2_v4_B_seed0_step750/renderings/2026-08-11_22-27-51_env0001_episode0000_handle_side_len804_reason-stage_overtime.mp4` | 3,625,759 | video | INCLUDED |
| `videos/R2_v4_B_seed0_step750__2026-08-11_22-27-51_env0001_episode0000_handle_top_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R2_v4_B_seed0_step750/renderings/2026-08-11_22-27-51_env0001_episode0000_handle_top_len804_reason-stage_overtime.mp4` | 8,160,370 | video | INCLUDED |
| `videos/R2_v4_B_seed0_step750__2026-08-11_22-27-51_env0001_episode0000_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R2_v4_B_seed0_step750/renderings/2026-08-11_22-27-51_env0001_episode0000_len804_reason-stage_overtime.mp4` | 989,603 | video | INCLUDED |
| `videos/R3_v4_B_seed1_step500_g6__render_outcome_receipt.json` | `logs_eval/a2_piper_pull_v4/renders/R3_v4_B_seed1_step500_g6/renderings/render_outcome_receipt.json` | 4,208 | render_receipt | INCLUDED |
| `videos/R3_v4_B_seed1_step500_g6__2026-08-11_22-30-12_env0000_episode0000_handle_side_len2304_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R3_v4_B_seed1_step500_g6/renderings/2026-08-11_22-30-12_env0000_episode0000_handle_side_len2304_reason-stage_overtime.mp4` | 11,943,278 | video | INCLUDED |
| `videos/R3_v4_B_seed1_step500_g6__2026-08-11_22-30-12_env0000_episode0000_handle_top_len2304_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R3_v4_B_seed1_step500_g6/renderings/2026-08-11_22-30-12_env0000_episode0000_handle_top_len2304_reason-stage_overtime.mp4` | 16,178,537 | video | INCLUDED |
| `videos/R3_v4_B_seed1_step500_g6__2026-08-11_22-30-12_env0000_episode0000_len2304_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R3_v4_B_seed1_step500_g6/renderings/2026-08-11_22-30-12_env0000_episode0000_len2304_reason-stage_overtime.mp4` | 3,421,636 | video | INCLUDED |
| `videos/R3_v4_B_seed1_step500_g6__2026-08-11_22-30-12_env0001_episode0000_handle_side_len2304_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R3_v4_B_seed1_step500_g6/renderings/2026-08-11_22-30-12_env0001_episode0000_handle_side_len2304_reason-stage_overtime.mp4` | 9,206,687 | video | INCLUDED |
| `videos/R3_v4_B_seed1_step500_g6__2026-08-11_22-30-12_env0001_episode0000_handle_top_len2304_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R3_v4_B_seed1_step500_g6/renderings/2026-08-11_22-30-12_env0001_episode0000_handle_top_len2304_reason-stage_overtime.mp4` | 13,027,109 | video | INCLUDED |
| `videos/R3_v4_B_seed1_step500_g6__2026-08-11_22-30-12_env0001_episode0000_len2304_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R3_v4_B_seed1_step500_g6/renderings/2026-08-11_22-30-12_env0001_episode0000_len2304_reason-stage_overtime.mp4` | 4,475,788 | video | INCLUDED |
| `videos/R4_v4_A_seed1_step750__render_outcome_receipt.json` | `logs_eval/a2_piper_pull_v4/renders/R4_v4_A_seed1_step750/renderings/render_outcome_receipt.json` | 4,080 | render_receipt | INCLUDED |
| `videos/R4_v4_A_seed1_step750__2026-08-11_22-32-58_env0000_episode0000_handle_side_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R4_v4_A_seed1_step750/renderings/2026-08-11_22-32-58_env0000_episode0000_handle_side_len804_reason-stage_overtime.mp4` | 3,830,250 | video | INCLUDED |
| `videos/R4_v4_A_seed1_step750__2026-08-11_22-32-58_env0000_episode0000_handle_top_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R4_v4_A_seed1_step750/renderings/2026-08-11_22-32-58_env0000_episode0000_handle_top_len804_reason-stage_overtime.mp4` | 5,769,211 | video | INCLUDED |
| `videos/R4_v4_A_seed1_step750__2026-08-11_22-32-58_env0000_episode0000_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R4_v4_A_seed1_step750/renderings/2026-08-11_22-32-58_env0000_episode0000_len804_reason-stage_overtime.mp4` | 1,327,583 | video | INCLUDED |
| `videos/R4_v4_A_seed1_step750__2026-08-11_22-32-58_env0001_episode0000_handle_side_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R4_v4_A_seed1_step750/renderings/2026-08-11_22-32-58_env0001_episode0000_handle_side_len804_reason-stage_overtime.mp4` | 3,164,739 | video | INCLUDED |
| `videos/R4_v4_A_seed1_step750__2026-08-11_22-32-58_env0001_episode0000_handle_top_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R4_v4_A_seed1_step750/renderings/2026-08-11_22-32-58_env0001_episode0000_handle_top_len804_reason-stage_overtime.mp4` | 3,781,479 | video | INCLUDED |
| `videos/R4_v4_A_seed1_step750__2026-08-11_22-32-58_env0001_episode0000_len804_reason-stage_overtime.mp4` | `logs_eval/a2_piper_pull_v4/renders/R4_v4_A_seed1_step750/renderings/2026-08-11_22-32-58_env0001_episode0000_len804_reason-stage_overtime.mp4` | 1,706,651 | video | INCLUDED |
| — | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave1_seed0/runner.log` | — | training_log | MISSING: required full runner.log is unavailable; .hydra/train.log is intentionally not substituted |
| — | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave1_seed1/runner.log` | — | training_log | MISSING: required full runner.log is unavailable; .hydra/train.log is intentionally not substituted |
| — | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave2_relay_seed0/runner.log` | — | training_log | MISSING: required full runner.log is unavailable; .hydra/train.log is intentionally not substituted |
| — | `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave2_relay_seed1/runner.log` | — | training_log | MISSING: required full runner.log is unavailable; .hydra/train.log is intentionally not substituted |
| — | — | — | expected_logical_artifact | OMITTED: R1_FAILED_AFTER_3_LAUNCH_ATTEMPTS (env0000/episode0000/main) |
| — | — | — | expected_logical_artifact | OMITTED: R1_FAILED_AFTER_3_LAUNCH_ATTEMPTS (env0000/episode0000/handle_side) |
| — | — | — | expected_logical_artifact | OMITTED: R1_FAILED_AFTER_3_LAUNCH_ATTEMPTS (env0000/episode0000/handle_top) |
| — | — | — | expected_logical_artifact | OMITTED: R1_FAILED_AFTER_3_LAUNCH_ATTEMPTS (env0001/episode0000/main) |
| — | — | — | expected_logical_artifact | OMITTED: R1_FAILED_AFTER_3_LAUNCH_ATTEMPTS (env0001/episode0000/handle_side) |
| — | — | — | expected_logical_artifact | OMITTED: R1_FAILED_AFTER_3_LAUNCH_ATTEMPTS (env0001/episode0000/handle_top) |

## Tier-2 selection and omissions

Each render receipt is mandatory and appears before its selected MP4 entries; only cap-eligible actual MP4 files from successful R2–R4 renders are considered in stable filename order and may be omitted for the decimal cap, while the six R1 logical NOT_RUN artifacts are omitted because three launches failed.

R1 has an exact failure receipt instead of an outcome receipt. Its six omitted entries are logical env×camera artifacts only; no timestamped filenames, source paths, or behavioral claims are invented.

R1 failure-receipt attempt evidence paths (recorded by the copied receipt):
- `logs_eval/a2_piper_pull_v4/renders/R1_v2_W_wave2_seed1_step750_attempt1_fail`
- `logs_eval/a2_piper_pull_v4/renders/R1_v2_W_wave2_seed1_step750_attempt1_fail/hydra/launcher_stdout.log`
- `logs_eval/a2_piper_pull_v4/renders/R1_v2_W_wave2_seed1_step750_attempt2_fail`
- `logs_eval/a2_piper_pull_v4/renders/R1_v2_W_wave2_seed1_step750_attempt2_fail/hydra/launcher_stdout.log`
- `logs_eval/a2_piper_pull_v4/renders/R1_v2_W_wave2_seed1_step750`
- `logs_eval/a2_piper_pull_v4/renders/R1_v2_W_wave2_seed1_step750/hydra/launcher_stdout.log`

Required v2 full runner logs are explicitly missing. The corresponding `.hydra/train.log` files are not substituted.

The archive contains no content-digest fields or functions.
