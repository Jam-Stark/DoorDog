# Pull-v6.1 Quality → Population stage closure

Status: `QUALITY_PASS__POPULATION_INCONCLUSIVE`

## Outcome

Production remains `logs_rl/a2_piper_pull_v6/pull_v6_F0_r6an_seed3/model_step_000025.pt`. It is still the only checkpoint with a verified strict-natural full chain through E7; no v6.1Q or v6.1P candidate exceeded it.

## Formal strict-natural denominator

All values use four eval seeds, 16 first episodes per seed, 64 episodes total, Stage0-only resets, banks disabled, and evaluator interventions disabled.

| Candidate | E5 | clean release | frame passage | E6 | E7 |
|---|---:|---:|---:|---:|---:|
| r6an baseline | 41 | 5 | 3 | 2 | 1 |
| P integrated step25 / step50 | 19 / 18 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| P grouped-output step25 / step50 | 45 / 46 | 1 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| P B-focus step25 / step50 | 47 / 46 | 2 / 2 | 1 / 1 | 0 / 0 | 0 / 0 |

Full actor unfreeze damaged the learned B→C trajectory. Freezing the LSTM recovered E5 admission, and the sole B-focus curriculum revision raised E5 further, but neither retained baseline clean→E6→E7 conversion. Higher admission alone is not population success.

## Main insight

The population bottleneck is not Stage0/E5 admission and not the gripper release mean. Release means remained close to the r6an source, while natural evaluations produced many premature releases and almost no stable Phase-C windows. The binding problem is continuous natural B→C readiness formation plus preservation of the rare downstream chain. More ratio/reward sweeps on the same 135D contract are not justified by this stage.

## Behavior-quality evidence

- Complete winner seed3/env14: clean step357, frame step620, E6 step739, E7 step1308.
- Representative failure seed0/env3: clean step373, frame step622, E6 step671, no E7; path `7.4429 m`, reversals `52`, arm-frame contact steps `51`, body-frame contact steps `39`.
- Complete five-camera render: `logs_eval/a2_piper_pull_v6/p2_render_F0_r6ap_r6an_seed3_env14/videos/`.
- Failure five-camera render: `logs_eval/a2_piper_pull_v6_1/pull_v6_1_r6an_seed0_env3_e6_no_e7_render/videos/`.

The failure render ends at Stage5 overtime after 1605 frames and exposes the remaining through collision/path-reversal problem.

## Evidence-tool correction

The population analyzer now uses `a2_v14_per_env_records.json` as the exact 16-env denominator and the Stage2–5 trace only as a detail supplement. Environments that never enter the trace window remain upstream failures. Event steps encoded as `"N/A"` are normalized to absent events rather than counted as success.

## Decision

- Quality winner: r6an retained.
- Population winner: none.
- Hardware: `NOT_RUN`.
- A future stage should change B→C decision representation/temporal credit while preserving the r6an carrier, not continue an unbounded curriculum or reward-scale sweep.
