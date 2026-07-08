# TODO

- 2026-07-08 15:22 HKT - Future implementation TODO: after A2 Phase2 student distillation exists and produces a usable checkpoint, design and implement full A2+Piper Phase3 Student Bootstrapping / GRPO fine-tuning route:
  - Add A2-specific Phase3 experiment/config route.
  - Initialize from A2 Phase2 RGB student checkpoint.
  - Implement GRPO-style actor-only update from grouped trajectory returns or binary success scores.
  - Preserve A2 rollout compose: student high-level action + frozen A2_Base leg action -> env rollout action.
  - Define A2 success / return scoring from staged door task metrics.
  - Keep camera/domain randomization compatible with A2 Phase2 vision route.
  - Add eval comparing Phase2 student vs Phase3 bootstrapped student.
  - Fail-fast on checkpoint mismatch, obs/action dim drift, missing grouped scores, missing camera or invalid success signal.
