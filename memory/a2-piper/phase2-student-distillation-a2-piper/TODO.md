# TODO

Status at 2026-07-28 20:58 HKT: `TRAINING_PASS; R14 resolved; base_v16_B Gemini 335L stage1–5 sweep and Scheme C dual-view eval complete; Scheme C runtime PASS but full-task visibility PARTIAL; C-B v16 Student one-update goal complete (V16_CB_STUDENT_ONE_UPDATE_PASS)`.

There is no blocker for the completed goal. The following are explicitly deferred, non-blocking future work and must not be read as completed or implied by `TRAINING_PASS`:

- Optional user-directed G1 compatibility/regression work; it is outside the A2+Piper-only scope.
- R16 lifecycle/harness perfection, including natural Kit close, and independent full-architecture strict reconstruction outside Hydra. The non-natural C-B v16 close is not a training blocker.
- A stage5-aware view/observation design, followed by final physical camera pose/mount and mirrored `left/out` validation. The symmetric portrait D435i + provisional A2 Head Scheme C is runtime-complete and improves stage3–4, but its fixed forward views leave the handle behind after passage; stage5 conservative-union handle/trio visibility is only `10.25%/3.22%`, so it is not an accepted full-task default.
- Visual/material randomization, multi-seed camera validation, and formal/longer-scale or multi-seed training; none has run in the C-B v16 one-update scope.
- Student-only eval, recurrent ONNX/export, policy-quality assessment, and open-door success evaluation.

Any future item needs its own approved scope, frozen candidate, and risk-appropriate validation; no current-goal gate remains.
