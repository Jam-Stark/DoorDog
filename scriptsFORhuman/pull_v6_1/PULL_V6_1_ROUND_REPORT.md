# Pull-v6.1 Round Report

Status: `QUALITY_INCONCLUSIVE`

## Evidence

| Phase | Artifact | Evidence status | Result |
| --- | --- | --- | --- |
| Static | integrated compile + Hydra composition | `STATIC_PASS` | Core env/trainer/actor/scripts compile; P integrated config composes. |
| Q0 | existing strict-natural env14 trace reduction | `RUNTIME_PASS` | E5=319, release=357, K25=384, frame=620, E6=739, E7=1308; release→E7=19.02 s. |
| Q1 | 10 s A/B/C/D action-hook smoke | `RUNTIME_PASS` | First active row=358 after release row=357; target slices and 15 non-target no-op contract pass. |
| Q2 | `PULL_V6_1_COUNTERFACTUAL_ADMISSION_REPORT.json` | `NOT_ADMITTED` | A reproduces the env14 baseline and all target release+1/prefix checks pass, but non-target env0 differs at its final row in B. No 2×2 causal claim is made. |
| Q3 | `PULL_V6_1_REWARD_RANKING_REPORT.json` | `NOT_ADMITTED` | B/C/D have only 447 clean-release tail steps, shorter than the preregistered 569-step equal horizon. Rewards remain unchanged. |
| Q4 capture/restore | `PULL_V6_1_BANK_RESTORE_REPORT.json` | `RUNTIME_PASS` | Exact v1 D25/frame/E6 bank captured from env14; all three rows restore to the correct Stage4/Stage5 source with finite first actions. |
| Q4 continuation | `PULL_V6_1_BANK_CONTINUATION_REPORT.json` | `NOT_ADMITTED` | Four cold-recurrent rollouts per row ran 650 steps; none reached D25→frame, frame→E6, or E6→E7. |
| Q5–Q6 | Q quality train/eval/render | `NOT_RUN` | Stopped before training by the Q4 continuation gate. Four target batches are registered as `gated_not_launched`. |
| P1–P3 | population train/eval/render | `NOT_RUN` | No qualified Q candidate; population integration was not entered. |

## Registered contracts

- Source checkpoint: `pull_v6_F0_r6an_seed3/model_step_000025.pt`.
- Q uses `pull_v6_1_Q_specialist`; P uses `pull_v6_1_P_integrated` after a Q selection.
- Q curriculum: Stage0/Stage4/Stage5 = `0.10/0.60/0.30`; Stage4 is D25/frame = `0.50/0.50`.
- P curriculum: Stage0/Stage4/Stage5 = `0.50/0.35/0.15`; Stage4 is B/C/D25/frame = `0.30/0.30/0.20/0.20`.
- Hardware evidence: `NOT_RUN`.

Q0 source: `logs_eval/a2_piper_pull_v6/p2_true_natural_F0_r6ap_seed3_step025/eval/stage2_5_step_trace.json`.

Q1 admitted only the action/lifecycle interface. Its 10 s episode timeout is not a Q2 outcome and is excluded from scientific comparison.

## Gate conclusion

- Q2 observed outcomes are descriptive only: A completed; B/C/D ended in Stage4 overtime. The batch is not admitted for causal attribution.
- Q4 mechanism evidence is reusable: bank schema `a2_piper_pull_v61_late_state_bank_v1`, ordered labels D25/frame/E6, source steps `385/620/739`, and 143 registered buffers.
- The known r6an policy cannot continue from any restored late row under cold recurrent state within the registered 650-step stage horizon. Per plan, Q5 and P remain unlaunched.
- Final verdict: `QUALITY_INCONCLUSIVE`. Hardware: `NOT_RUN`.
