# v19 Progress-Report Media QA

Status: **PASS — CPU/OpenCV media integrity and qualitative contact-sheet review only.**

Scope: the five current matrix-selected v19 roots only: G1/G2/G4/G5 recovery roots and the original G6 root. Four prior failed roots were excluded and untouched.

Matrix: `scriptsFORhuman/progress_report/a2_piper_v19_v21_render_matrix_20260806.json`
SHA-256: `eff869d458caf06e9bb40419506e261f03d327479e093bf59d879d53c5382ce3`

## Decode and inventory result

- Cases: 5
- Finalized MP4s: 15
- Selected primary clips: 15 (env0000 / episode0000 / main + handle_top + handle_side)
- Unfinished `.writing.mp4`: 0
- Every selected MP4 was a regular non-symlink, nonempty file; OpenCV opened it, reported finite positive FPS, decoded to EOF, and produced the same decoded-frame count as reported metadata.
- Each clip had stable nonzero frame shape and varying sampled frame hashes. Full SHA-256, byte counts, dimensions, FPS, reported/decoded frames, durations, and exact paths are recorded in `qa_manifest.json`.

## Per-case qualitative contact-sheet review

### v19_G1_step0500

- Receipt gates: exit `0`, natural exit `True`, startup marker `True`, media gate `True`.
- Media: `3` finalized / `0` unfinished; selected primary `3`.
- Contact sheet: `scriptsFORhuman/progress_report/media_qa/v19/v19_G1_step0500_contact.png`.
- Visual finding: All three camera rows show the robot approaching/interacting around the handle region, then leaving more of the final main/side framing to the door scene. Temporal scene changes are visible.
- Selected clips:
  - `main` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G1_step0500_legacy_defaults_recovery_r1/renderings/2026-08-06_03-26-20_env0000_episode0000_len695_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `696/696`; duration `34.80s`; SHA-256 in manifest.
  - `handle_top` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G1_step0500_legacy_defaults_recovery_r1/renderings/2026-08-06_03-26-20_env0000_episode0000_handle_top_len695_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `696/696`; duration `34.80s`; SHA-256 in manifest.
  - `handle_side` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G1_step0500_legacy_defaults_recovery_r1/renderings/2026-08-06_03-26-20_env0000_episode0000_handle_side_len695_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `696/696`; duration `34.80s`; SHA-256 in manifest.

### v19_G2_step0500

- Receipt gates: exit `0`, natural exit `True`, startup marker `True`, media gate `True`.
- Media: `3` finalized / `0` unfinished; selected primary `3`.
- Contact sheet: `scriptsFORhuman/progress_report/media_qa/v19/v19_G2_step0500_contact.png`.
- Visual finding: The contact sheet shows approach-to-handle framing followed by changed robot/door composition. The final side sample is largely the handle/door view after the robot leaves that camera framing.
- Selected clips:
  - `main` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G2_step0500_legacy_defaults_recovery_r1/renderings/2026-08-06_03-26-19_env0000_episode0000_len763_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `764/764`; duration `38.20s`; SHA-256 in manifest.
  - `handle_top` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G2_step0500_legacy_defaults_recovery_r1/renderings/2026-08-06_03-26-19_env0000_episode0000_handle_top_len763_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `764/764`; duration `38.20s`; SHA-256 in manifest.
  - `handle_side` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G2_step0500_legacy_defaults_recovery_r1/renderings/2026-08-06_03-26-19_env0000_episode0000_handle_side_len763_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `764/764`; duration `38.20s`; SHA-256 in manifest.

### v19_G4_step0500

- Receipt gates: exit `0`, natural exit `True`, startup marker `True`, media gate `True`.
- Media: `3` finalized / `0` unfinished; selected primary `3`.
- Contact sheet: `scriptsFORhuman/progress_report/media_qa/v19/v19_G4_step0500_contact.png`.
- Visual finding: The three rows show non-static robot pose and door/handle composition across the five samples; later main/side framing contains less of the robot.
- Selected clips:
  - `main` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G4_step0500_legacy_defaults_recovery_r1/renderings/2026-08-06_03-27-17_env0000_episode0000_len703_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `704/704`; duration `35.20s`; SHA-256 in manifest.
  - `handle_top` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G4_step0500_legacy_defaults_recovery_r1/renderings/2026-08-06_03-27-17_env0000_episode0000_handle_top_len703_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `704/704`; duration `35.20s`; SHA-256 in manifest.
  - `handle_side` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G4_step0500_legacy_defaults_recovery_r1/renderings/2026-08-06_03-27-17_env0000_episode0000_handle_side_len703_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `704/704`; duration `35.20s`; SHA-256 in manifest.

### v19_G6_step1250

- Receipt gates: exit `0`, natural exit `True`, startup marker `True`, media gate `True`.
- Media: `3` finalized / `0` unfinished; selected primary `3`.
- Contact sheet: `scriptsFORhuman/progress_report/media_qa/v19/v19_G6_step1250_contact.png`.
- Visual finding: The contact sheet shows visible robot pose and door/handle composition changes across all camera rows; the final main/side samples are dominated by the door scene.
- Selected clips:
  - `main` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G6_step1250/renderings/2026-08-06_03-34-45_env0000_episode0000_len640_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `641/641`; duration `32.05s`; SHA-256 in manifest.
  - `handle_top` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G6_step1250/renderings/2026-08-06_03-34-45_env0000_episode0000_handle_top_len640_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `641/641`; duration `32.05s`; SHA-256 in manifest.
  - `handle_side` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G6_step1250/renderings/2026-08-06_03-34-45_env0000_episode0000_handle_side_len640_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `641/641`; duration `32.05s`; SHA-256 in manifest.

### v19_G5_step2250

- Receipt gates: exit `0`, natural exit `True`, startup marker `True`, media gate `True`.
- Media: `3` finalized / `0` unfinished; selected primary `3`.
- Contact sheet: `scriptsFORhuman/progress_report/media_qa/v19/v19_G5_step2250_contact.png`.
- Visual finding: The sheet shows an approach/interaction sequence and later changed door/robot composition; the robot is partly or wholly outside portions of the later main/side framing.
- Selected clips:
  - `main` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G5_step2250_legacy_defaults_recovery_r1/renderings/2026-08-06_03-28-51_env0000_episode0000_len672_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `673/673`; duration `33.65s`; SHA-256 in manifest.
  - `handle_top` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G5_step2250_legacy_defaults_recovery_r1/renderings/2026-08-06_03-28-51_env0000_episode0000_handle_top_len672_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `673/673`; duration `33.65s`; SHA-256 in manifest.
  - `handle_side` — `logs_eval/base_v19/progress_report_multickpt_render_20260806/v19_G5_step2250_legacy_defaults_recovery_r1/renderings/2026-08-06_03-28-51_env0000_episode0000_handle_side_len672_reason-complete.mp4`; 1280×720 @ 20.00 fps; frames reported/decoded `673/673`; duration `33.65s`; SHA-256 in manifest.

## Limitations

- The five temporal samples per camera are a qualitative visual aid, not full subjective review of every frame.
- This QA does not infer grasp/contact state, door-opening success, reward/telemetry validity, policy quality, statistical performance, scientific conclusion, release eligibility, or real-hardware behavior.
- The project memory records v19 as a non-release fallback with an earlier arm-j1 render-behavior gate failure; this media QA does not alter that conclusion.

Machine-readable evidence: `qa_manifest.json`.
