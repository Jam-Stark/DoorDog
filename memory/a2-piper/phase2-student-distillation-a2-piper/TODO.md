# TODO

Status at 2026-07-22 21:35 HKT: `TRAINING_PASS; R14 resolved; right/out Gemini 335L simulation pose sweep complete; current accepted A2+Piper-only one-update Student Distillation goal complete`.

There is no blocker for the completed goal. The following are explicitly deferred, non-blocking future work and must not be read as completed or implied by `TRAINING_PASS`:

- Optional user-directed G1 compatibility/regression work; it is outside the A2+Piper-only scope.
- R16 lifecycle/harness perfection and independent full-architecture strict reconstruction outside Hydra.
- Final physical camera pose/mount decision and mirrored `left/out` validation; R14 and the bounded `right/out` pose sweep are complete, with `z_low_020` retained only as the current simulation search default.
- Visual/material randomization, multi-seed camera validation, larger-scale or multi-seed training.
- Student-only eval, recurrent ONNX/export, policy-quality assessment, and open-door success evaluation.

Any future item needs its own approved scope, frozen candidate, and risk-appropriate validation; no current-goal gate remains.
