# TODO

Status at 2026-08-12 05:26 HKT: `TRAINING_PASS; R14 resolved; base_v16_B Gemini 335L stage1–5 sweep, Scheme C, C-B2 and TOEIN20 camera eval complete; C-B v16 Student one-update and GPU7 pilot complete; C-B2H exact64 formal 10000-step checkpoint complete; ToeOut6/pitch−50° fixed-G2 multi-seed/Stage2 diagnostic, large-scale baseline and v19 GRPO finetune/eval complete at edge verdict; lifecycle unresolved`。

There is no blocker for the completed goal. The following are explicitly deferred, non-blocking future work and must not be read as completed or implied by `TRAINING_PASS`:

- Optional user-directed G1 compatibility/regression work; it is outside the A2+Piper-only scope.
- R16 lifecycle/harness perfection, including natural Kit close, and independent full-architecture strict reconstruction outside Hydra. The non-natural C-B v16 close is not a training blocker.
- A stage5-aware view/observation design, followed by final physical camera pose/mount and mirrored `left/out` validation. C-B2's dual portrait D435i + official OEM Head simulation improves manipulation coverage and passes same-render RGB-D panorama/video gates, but the fixed forward views still leave the handle behind after passage; stage5 conservative-union handle/trio visibility is `9.30%/9.30%`, so it is not an accepted full-task default.
- Replace the rejected C-B2 panorama prototype. Diagnose transform/projection convention, `distance_to_image_plane` interpretation, forward-warp/Z-buffer sampling, occlusion seams and hole policy; add explicit visual and quantitative seam-quality acceptance before any Student integration.
- Visual/material randomization, multi-seed camera validation, and any future multi-seed C-B2H training/eval。ToeOut6/pitch−50° step8000 的三 seed Student baseline 已完成，但不等于 broader training stability。
- Fixed-G2 targeted actor-only GRPO finetune 与 same-seed 512 eval 已完成：`467/512 = 91.2109375%`，Stage2 failures `35→23`，但 Stage0 `15→20`、Stage4 `1→2`，故为 §6 edge。若继续，只能 separately approve v1 有限解冻视觉编码器，并以保留 Stage2 改善、消除 Stage0 回退为 acceptance；不得把当前结果外推为 determinism/general/deployment/physical-camera PASS。Recurrent ONNX/export 仍需独立 scope。
- 2026-08-10 large-scale camera eval 已完成：Student `459/512`、true-action Teacher `255/256`，但 direct visual metrics 为 `0/768`，故 camera/perception attribution 是 `UNKNOWN/INCONCLUSIVE`。修复 direct-visibility capture、existing D435-depth ablation 或 wrist-camera decision 都不是已授权工作；若未来 separately approved perception ablation，先评估已有 D435 depth，不默认启用 depth 或增加 wrist camera。

已授权的 C-B2H 10000-step 长训已经完成；上述任何 future item 都需要独立批准、frozen candidate 与 risk-appropriate validation。

- 2026-07-28 23:06 HKT - GPU binding v3、recurrent Teacher repeated rollout cleanup 与 physical GPU7 上的 32-env/10-batch capacity/stability pilot 已完成；natural Kit close 仍属 R16 TODO，正式 longer-scale/multi-seed training、policy quality 与 open-door success 未验证。
- 2026-07-30 16:13 HKT - C-B2 design/config、三相机 runtime 与 v16 Teacher process videos 已完成，但 current panorama 因重影、撕裂和空洞视觉 FAIL；panorama 重构、stage5-aware view、CAD interference、physical calibration、real pair sync、mirrored left/out 与 Student integration 仍需独立批准和验证。
- 2026-07-30 17:34 HKT - C-B2 ±20° toe-in wider-view comparison 已完成；空洞率由 ±15° 的 `22.97%` 升至 `27.08%`，未改善 panorama，重构与 seam-quality gate TODO 保持开放。
- 2026-08-02 05:00 HKT - fix commit `0f9c11e` 的 fresh c18 + G2 step2000 GPU7/64-env retry 已完成 10,000-step checkpoint；formal Student-only eval 的 protocol/runtime artifacts PASS，但 `0/16 goal`、all `stage_overtime` 为 policy-quality FAIL/poor。exact env13 case 的三次 replay 都 drift 到 stage1，best-only render 已保留 trial01；自然 Kit lifecycle、ONNX/export、多 seed、final policy quality/open-door success 与 physical camera 项保持 TODO，资源不足必须 BLOCK，禁止自动降 env、resume fallback、换 GPU 或 silent retry。
- 2026-08-09 11:05 HKT - fixed-G2 multi-seed/Stage2 diagnosis 已关闭：Teacher seed0/1 为 `32/32`，Student seed0/1/2 为 `42/48 = 87.5%`；env4 Stage2 evidence 指向 intermittent bilateral contact/squeeze continuity，不是 contract drift 或全局 handle visibility loss。任何 targeted DAgger/contact-continuity finetune 都需新 approved `HIGH_RISK` brief、multi-seed/repeated-replay acceptance；不启动 full retrain 或 generic `1–2k` continuation。
- 2026-08-10 19:39 HKT - large-scale eval 已完成并记录于 DONE；remaining visibility/depth work 和 targeted Stage2 finetune 均需 separately approved scope，不能从本 eval 推导 current-camera、deployment 或 physical-camera PASS。
- 2026-08-12 05:26 HKT - v19 GRPO v0 已完成并记录于 DONE；未来 v1 解冻编码器、ONNX/export、natural lifecycle 与 physical-camera work 均需独立 scope。本轮不再启动训练。
