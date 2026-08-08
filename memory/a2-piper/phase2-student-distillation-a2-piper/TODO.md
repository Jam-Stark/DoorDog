# TODO

Status at 2026-08-08 20:03 HKT: `TRAINING_PASS; R14 resolved; base_v16_B Gemini 335L stage1–5 sweep, Scheme C, C-B2 and TOEIN20 camera eval complete; C-B v16 Student one-update and GPU7 pilot complete; C-B2H exact64 formal 10000-step checkpoint complete; old Student-only eval quality FAIL/poor; ToeOut6/pitch−50° step8000 multi-seed baseline and Teacher-shared Stage0 diagnostic complete; lifecycle unresolved`。

There is no blocker for the completed goal. The following are explicitly deferred, non-blocking future work and must not be read as completed or implied by `TRAINING_PASS`:

- Optional user-directed G1 compatibility/regression work; it is outside the A2+Piper-only scope.
- R16 lifecycle/harness perfection, including natural Kit close, and independent full-architecture strict reconstruction outside Hydra. The non-natural C-B v16 close is not a training blocker.
- A stage5-aware view/observation design, followed by final physical camera pose/mount and mirrored `left/out` validation. C-B2's dual portrait D435i + official OEM Head simulation improves manipulation coverage and passes same-render RGB-D panorama/video gates, but the fixed forward views still leave the handle behind after passage; stage5 conservative-union handle/trio visibility is `9.30%/9.30%`, so it is not an accepted full-task default.
- Replace the rejected C-B2 panorama prototype. Diagnose transform/projection convention, `distance_to_image_plane` interpretation, forward-warp/Z-buffer sampling, occlusion seams and hole policy; add explicit visual and quantitative seam-quality acceptance before any Student integration.
- Visual/material randomization, multi-seed camera validation, and any future multi-seed C-B2H training/eval。ToeOut6/pitch−50° step8000 的三 seed Student baseline 已完成，但不等于 broader training stability。
- 先诊断/改善 current-worktree G2 Teacher 的 Stage0 near-handle dead-zone；如需按环境难度归因，扩充 formal selection 的完整 door customData。不要先只增加 Student iteration。Recurrent ONNX/export、final policy-quality improvement 与 open-door success evaluation 仍需独立 scope。

已授权的 C-B2H 10000-step 长训已经完成；上述任何 future item 都需要独立批准、frozen candidate 与 risk-appropriate validation。

- 2026-07-28 23:06 HKT - GPU binding v3、recurrent Teacher repeated rollout cleanup 与 physical GPU7 上的 32-env/10-batch capacity/stability pilot 已完成；natural Kit close 仍属 R16 TODO，正式 longer-scale/multi-seed training、policy quality 与 open-door success 未验证。
- 2026-07-30 16:13 HKT - C-B2 design/config、三相机 runtime 与 v16 Teacher process videos 已完成，但 current panorama 因重影、撕裂和空洞视觉 FAIL；panorama 重构、stage5-aware view、CAD interference、physical calibration、real pair sync、mirrored left/out 与 Student integration 仍需独立批准和验证。
- 2026-07-30 17:34 HKT - C-B2 ±20° toe-in wider-view comparison 已完成；空洞率由 ±15° 的 `22.97%` 升至 `27.08%`，未改善 panorama，重构与 seam-quality gate TODO 保持开放。
- 2026-08-02 05:00 HKT - fix commit `0f9c11e` 的 fresh c18 + G2 step2000 GPU7/64-env retry 已完成 10,000-step checkpoint；formal Student-only eval 的 protocol/runtime artifacts PASS，但 `0/16 goal`、all `stage_overtime` 为 policy-quality FAIL/poor。exact env13 case 的三次 replay 都 drift 到 stage1，best-only render 已保留 trial01；自然 Kit lifecycle、ONNX/export、多 seed、final policy quality/open-door success 与 physical camera 项保持 TODO，资源不足必须 BLOCK，禁止自动降 env、resume fallback、换 GPU 或 silent retry。
- 2026-08-08 20:03 HKT - ToeOut6/pitch−50° step8000 Student 的三 seed formal baseline 为 `29/48` goal；seed0 pure G2 Teacher 对照与 Student 有完全相同失败集合，env0/env5/env12 render 均为 Stage0 near-handle 无接触停滞。下一步为 Teacher Stage0 diagnosis/improvement，必要时完整 door customData selection，不是盲目延长 Student training。
