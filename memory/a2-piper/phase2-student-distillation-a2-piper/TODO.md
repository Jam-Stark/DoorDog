# TODO

Status at 2026-07-28 23:06 HKT: `TRAINING_PASS; R14 resolved; base_v16_B Gemini 335L stage1–5 sweep and Scheme C dual-view eval complete; Scheme C runtime PASS but full-task visibility PARTIAL; C-B v16 Student one-update and GPU7 32-env/10-batch capacity pilot complete (V16_CB_GPU7_CAPACITY_STABILITY_PASS)`.

There is no blocker for the completed goal. The following are explicitly deferred, non-blocking future work and must not be read as completed or implied by `TRAINING_PASS`:

- Optional user-directed G1 compatibility/regression work; it is outside the A2+Piper-only scope.
- R16 lifecycle/harness perfection, including natural Kit close, and independent full-architecture strict reconstruction outside Hydra. The non-natural C-B v16 close is not a training blocker.
- A stage5-aware view/observation design, followed by final physical camera pose/mount and mirrored `left/out` validation. The symmetric portrait D435i + provisional A2 Head Scheme C is runtime-complete and improves stage3–4, but its fixed forward views leave the handle behind after passage; stage5 conservative-union handle/trio visibility is only `10.25%/3.22%`, so it is not an accepted full-task default.
- Visual/material randomization, multi-seed camera validation, and formal longer-scale or multi-seed training。32-env/10-batch GPU7 capacity pilot 已运行，但不等于正式 longer-scale training。
- Student-only eval, recurrent ONNX/export, policy-quality assessment, and open-door success evaluation.

Any future item needs its own approved scope, frozen candidate, and risk-appropriate validation; no current-goal gate remains.

- 2026-07-28 23:06 HKT - GPU binding v3、recurrent Teacher repeated rollout cleanup 与 physical GPU7 上的 32-env/10-batch capacity/stability pilot 已完成；natural Kit close 仍属 R16 TODO，正式 longer-scale/multi-seed training、policy quality 与 open-door success 未验证。
