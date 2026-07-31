# TODO

Status at 2026-07-31 19:04 HKT: `TRAINING_PASS; R14 resolved; base_v16_B Gemini 335L stage1–5 sweep, Scheme C, C-B2 and TOEIN20 camera eval complete; C-B v16 Student one-update and GPU7 pilot complete; C-B2H exact64 admission complete; first formal run failed after iteration 72; partial-prime fix STATIC PASS; fresh authorized 10000-batch retry pending`。

There is no blocker for the completed goal. The following are explicitly deferred, non-blocking future work and must not be read as completed or implied by `TRAINING_PASS`:

- Optional user-directed G1 compatibility/regression work; it is outside the A2+Piper-only scope.
- R16 lifecycle/harness perfection, including natural Kit close, and independent full-architecture strict reconstruction outside Hydra. The non-natural C-B v16 close is not a training blocker.
- A stage5-aware view/observation design, followed by final physical camera pose/mount and mirrored `left/out` validation. C-B2's dual portrait D435i + official OEM Head simulation improves manipulation coverage and passes same-render RGB-D panorama/video gates, but the fixed forward views still leave the handle behind after passage; stage5 conservative-union handle/trio visibility is `9.30%/9.30%`, so it is not an accepted full-task default.
- Replace the rejected C-B2 panorama prototype. Diagnose transform/projection convention, `distance_to_image_plane` interpretation, forward-warp/Z-buffer sampling, occlusion seams and hole policy; add explicit visual and quantitative seam-quality acceptance before any Student integration.
- Visual/material randomization, multi-seed camera validation, and formal longer-scale or multi-seed training。32-env/10-batch GPU7 capacity pilot 已运行，但不等于正式 longer-scale training。
- 完成并监控已授权的 C-B2H physical GPU7 / exact64-env / 10000-batch 长训；admission 的 `global_step=1` 与 `31146 MiB` peak 只证明启动和 bounded capacity，不证明 sustained completion、final checkpoint、model quality 或 eval。
- Student-only eval, recurrent ONNX/export, policy-quality assessment, and open-door success evaluation.

除已授权的 C-B2H 10000-batch 长训外，任何 future item 都需要独立批准、frozen candidate 与 risk-appropriate validation。

- 2026-07-28 23:06 HKT - GPU binding v3、recurrent Teacher repeated rollout cleanup 与 physical GPU7 上的 32-env/10-batch capacity/stability pilot 已完成；natural Kit close 仍属 R16 TODO，正式 longer-scale/multi-seed training、policy quality 与 open-door success 未验证。
- 2026-07-30 16:13 HKT - C-B2 design/config、三相机 runtime 与 v16 Teacher process videos 已完成，但 current panorama 因重影、撕裂和空洞视觉 FAIL；panorama 重构、stage5-aware view、CAD interference、physical calibration、real pair sync、mirrored left/out 与 Student integration 仍需独立批准和验证。
- 2026-07-30 17:34 HKT - C-B2 ±20° toe-in wider-view comparison 已完成；空洞率由 ±15° 的 `22.97%` 升至 `27.08%`，未改善 panorama，重构与 seam-quality gate TODO 保持开放。
- 2026-07-31 19:04 HKT - C-B2H exact128 attempt 在 optimizer 前 OOM；exact64 admission 已 load-validate step-1 checkpoint。formal R1 在 iteration 72 后因 false non-target partial-prime invariant 失败，候选 `f41147ea-5427954a-fbfb1142` 只有 static/no-sim PASS。当前 TODO 是从 step0 fresh 启动 c18 + G2 step2000 的 GPU7/64-env/10000-batch retry，至少越过旧 iteration 72，并验证 checkpoints、sustained/final completion；资源不足必须 BLOCK，禁止自动降 env 或 fallback。
