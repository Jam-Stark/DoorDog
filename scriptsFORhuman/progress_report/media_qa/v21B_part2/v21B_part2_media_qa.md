# v21B Part 2 Media QA

Status: **PASS** — every scoped finalized MP4 passed full OpenCV decode.

Matrix: `scriptsFORhuman/progress_report/a2_piper_v19_v21_render_matrix_20260806.json` (`eff869d458caf06e9bb40419506e261f03d327479e093bf59d879d53c5382ce3`)
Scope: canonical16 qualitative report-only renders; selected surface `env0002/l02`, episode `0000`.

## Decode summary

| Case | Primary | Auxiliary | Finalized total | Writing | Full decode | Contact sheet |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| v21B_B5_step0750 | 48 | 0 | 48 | 0 | PASS | `scriptsFORhuman/progress_report/media_qa/v21B_part2/v21B_B5_step0750_env0002_l02_contact_3x5.png` |
| v21B_B6_step0750 | 48 | 12 | 60 | 0 | PASS | `scriptsFORhuman/progress_report/media_qa/v21B_part2/v21B_B6_step0750_env0002_l02_contact_3x5.png` |
| v21B_B6_step2500 | 48 | 9 | 57 | 0 | PASS | `scriptsFORhuman/progress_report/media_qa/v21B_part2/v21B_B6_step2500_env0002_l02_contact_3x5.png` |

## Human contact-sheet inspection

All three `env0002/l02` 3×5 sheets were viewed. They show approach/reach near the doorway; later camera framing often occludes the robot or shows only partial geometry. This is qualitative context, not a grasp/latch/hinge/success determination.

### v21B_B5_step0750

- Viewed env0002/l02 contact sheet: the robot begins outside the doorway, reaches into the handle/doorway region in middle samples, and is only partially visible in later handle-side frames.
- The five sampled views do not by themselves establish a completed grasp, latch event, hinge displacement, or task success.

Selected clips:
- main: `logs_eval/base_v21B/progress_report_multickpt_render_20260806/v21B_B5_step0750/renderings/2026-08-06_02-19-55_env0002_episode0000_len612_reason-complete.mp4`
- handle_top: `logs_eval/base_v21B/progress_report_multickpt_render_20260806/v21B_B5_step0750/renderings/2026-08-06_02-19-55_env0002_episode0000_handle_top_len612_reason-complete.mp4`
- handle_side: `logs_eval/base_v21B/progress_report_multickpt_render_20260806/v21B_B5_step0750/renderings/2026-08-06_02-19-55_env0002_episode0000_handle_side_len612_reason-complete.mp4`

### v21B_B6_step0750

- Viewed env0002/l02 contact sheet: the robot approaches the doorway and the arm/body enter the handle-adjacent region in middle samples; later frames are substantially occluded by the door/frame or show partial body only.
- The sheet is qualitative visual context only and does not establish contact state, opening magnitude, or success.

Selected clips:
- main: `logs_eval/base_v21B/progress_report_multickpt_render_20260806/v21B_B6_step0750/renderings/2026-08-06_01-50-25_env0002_episode0000_len690_reason-complete.mp4`
- handle_top: `logs_eval/base_v21B/progress_report_multickpt_render_20260806/v21B_B6_step0750/renderings/2026-08-06_01-50-25_env0002_episode0000_handle_top_len690_reason-complete.mp4`
- handle_side: `logs_eval/base_v21B/progress_report_multickpt_render_20260806/v21B_B6_step0750/renderings/2026-08-06_01-50-25_env0002_episode0000_handle_side_len690_reason-complete.mp4`

### v21B_B6_step2500

- Viewed env0002/l02 contact sheet: the robot approaches and reaches into the doorway/handle region across early and middle samples; later samples mainly show the door/frame and partial robot geometry.
- The sheet is qualitative visual context only and does not establish contact state, opening magnitude, or success.

Selected clips:
- main: `logs_eval/base_v21B/progress_report_multickpt_render_20260806/v21B_B6_step2500/renderings/2026-08-06_02-15-28_env0002_episode0000_len668_reason-complete.mp4`
- handle_top: `logs_eval/base_v21B/progress_report_multickpt_render_20260806/v21B_B6_step2500/renderings/2026-08-06_02-15-28_env0002_episode0000_handle_top_len668_reason-complete.mp4`
- handle_side: `logs_eval/base_v21B/progress_report_multickpt_render_20260806/v21B_B6_step2500/renderings/2026-08-06_02-15-28_env0002_episode0000_handle_side_len668_reason-complete.mp4`

## Sampling note

- Every multi-frame video has distinct first/middle/last decoded-frame hashes. One-frame auxiliary clips were fully decoded and SHA-verified; intra-video variation is `N/A`.

## Qualitative limits

- Qualitative render-media QA only; no scientific, release, or hardware performance conclusion.
- Effort/torque remains ESTIMATE_ONLY; no true applied PhysX or hardware torque is inferred.
- OpenCV full decode checks file/frame-stream integrity, not robot-task semantic correctness.
