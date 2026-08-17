---
name: sim2sim-shadow-evaluator
scope: additive native MuJoCo A2+Piper Student shadow evaluator and E0-E6 evidence
status: complete_with_typed_e5_blocker
last_updated: 2026-08-17 20:20 HKT
owned_paths:
  - memory/a2-piper/sim2sim-shadow-evaluator/description.md
  - memory/a2-piper/sim2sim-shadow-evaluator/TODO.md
  - memory/a2-piper/sim2sim-shadow-evaluator/DONE.md
read_when:
  - continuing the A2+Piper MuJoCo shadow evaluator or creating the deferred Isaac paired trace
  - changing Student bundle, 54D A2_Base, external PD, camera, DoorSpec, or paired-trace semantics
---

# A2+Piper Sim2sim Shadow Evaluator

The additive branch `sim2sim/a2-mujoco-shadow-evaluator-20260817` implements the deployable Student boundary, floating-base A2+Piper MJCF, v24-mechanics door, independent runner, ordered paired harness, and E0-E6 receipts without changing shared production files.

Durable facts:

- Formal READY Student bundle uses distillation commit `a197255212fa65dd9e02337b7971daac71c944fe`, GRPO step10, native Hydra strict `policy_state_dict`, actor obs 81, action 12, LSTM 2×256, and CPU replay max diff 0.
- A2+Piper compiles under MuJoCo 3.10 as `nq/nv/nu=27/26/20`, mass `44.741 kg`. The exact A2_Base frame/history is 54/1620 and policy-leg remap is `[0,6,3,9,1,7,4,10,2,8,5,11]`.
- External PD clips every 200 Hz physics step. The owner-evaluated gripper face is `1300/32/45`; the selected adjacent config's legacy `80/3/10` remains a provenance warning.
- Door mechanics canonical surface is rad. Requested `50/2/4.5/100` and USD-degree readback normalize with max diff 0. MuJoCo maps dynamic friction to `frictionloss`; static != dynamic is always `FRICTION_SEMANTIC_GAP`.
- Actual latch mode is `constraint_gate`; actual render backend is CPU GLX/Xvfb llvmpipe because OSMesa is unavailable.
- E5 formal paired comparison is `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`. Never substitute the v24 teacher P0 trace for the current Student/scene Isaac trace.

This entry is intentionally not added to `memory/a2-piper/MEMORY.md`; add the routing line only during owner merge.
