# TODO

Status at 2026-07-22 23:41 HKT: `TRAINING_PASS; R14 resolved; base_v16_B Gemini 335L stage1–5 sweep plus eight videos complete; current accepted A2+Piper-only one-update Student Distillation goal complete`.

There is no blocker for the completed goal. The following are explicitly deferred, non-blocking future work and must not be read as completed or implied by `TRAINING_PASS`:

- Optional user-directed G1 compatibility/regression work; it is outside the A2+Piper-only scope.
- R16 lifecycle/harness perfection and independent full-architecture strict reconstruction outside Hydra.
- Wider `right/out` pose search focused on stage5 corridor/door-frame coverage, followed by final physical camera pose/mount and mirrored `left/out` validation. The bounded `base_v16_B` stage1–5 sweep is complete, but all candidates lose stage5 visibility; `x_near_028` is only the next-search center, not an accepted default.
- Visual/material randomization, multi-seed camera validation, larger-scale or multi-seed training.
- Student-only eval, recurrent ONNX/export, policy-quality assessment, and open-door success evaluation.

Any future item needs its own approved scope, frozen candidate, and risk-appropriate validation; no current-goal gate remains.
