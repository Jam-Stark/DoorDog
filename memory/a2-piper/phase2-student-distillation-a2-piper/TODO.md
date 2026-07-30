# TODO

Status at 2026-07-30 17:34 HKT: `TRAINING_PASS; R14 resolved; base_v16_B Gemini 335L stage1–5 sweep, Scheme C, C-B2 and TOEIN20 camera eval complete; C-B2 sensors runtime/sync/video PASS, both panoramas visual FAIL, and full-task visibility PARTIAL; C-B v16 Student one-update and GPU7 32-env/10-batch capacity pilot complete (V16_CB_GPU7_CAPACITY_STABILITY_PASS)`.

There is no blocker for the completed goal. The following are explicitly deferred, non-blocking future work and must not be read as completed or implied by `TRAINING_PASS`:

- Optional user-directed G1 compatibility/regression work; it is outside the A2+Piper-only scope.
- R16 lifecycle/harness perfection, including natural Kit close, and independent full-architecture strict reconstruction outside Hydra. The non-natural C-B v16 close is not a training blocker.
- A stage5-aware view/observation design, followed by final physical camera pose/mount and mirrored `left/out` validation. C-B2's dual portrait D435i + official OEM Head simulation improves manipulation coverage and passes same-render RGB-D panorama/video gates, but the fixed forward views still leave the handle behind after passage; stage5 conservative-union handle/trio visibility is `9.30%/9.30%`, so it is not an accepted full-task default.
- Replace the rejected C-B2 panorama prototype. Diagnose transform/projection convention, `distance_to_image_plane` interpretation, forward-warp/Z-buffer sampling, occlusion seams and hole policy; add explicit visual and quantitative seam-quality acceptance before any Student integration.
- Visual/material randomization, multi-seed camera validation, and formal longer-scale or multi-seed training。32-env/10-batch GPU7 capacity pilot 已运行，但不等于正式 longer-scale training。
- Student-only eval, recurrent ONNX/export, policy-quality assessment, and open-door success evaluation.

Any future item needs its own approved scope, frozen candidate, and risk-appropriate validation; no current-goal gate remains.

- 2026-07-28 23:06 HKT - GPU binding v3、recurrent Teacher repeated rollout cleanup 与 physical GPU7 上的 32-env/10-batch capacity/stability pilot 已完成；natural Kit close 仍属 R16 TODO，正式 longer-scale/multi-seed training、policy quality 与 open-door success 未验证。
- 2026-07-30 16:13 HKT - C-B2 design/config、三相机 runtime 与 v16 Teacher process videos 已完成，但 current panorama 因重影、撕裂和空洞视觉 FAIL；panorama 重构、stage5-aware view、CAD interference、physical calibration、real pair sync、mirrored left/out 与 Student integration 仍需独立批准和验证。
- 2026-07-30 17:34 HKT - C-B2 ±20° toe-in wider-view comparison 已完成；空洞率由 ±15° 的 `22.97%` 升至 `27.08%`，未改善 panorama，重构与 seam-quality gate TODO 保持开放。
