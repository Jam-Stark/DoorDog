# Sim2sim contract unknowns

Last updated: 2026-08-17 20:20 HKT

Unknown values are typed here and are never replaced with zero or inferred only from dimensions.

| Contract | State | Required evidence |
|---|---|---|
| Formal Student checkpoint and matching composed config | CLOSED_SOURCE | GRPO step10 checkpoint and adjacent config selected from formal evidence. |
| Native Hydra actor instantiate/load payload keys | CLOSED_RUNTIME | Read-only producer checkout loaded `policy_state_dict` strict on CPU and emitted the READY bundle. |
| Student actor/vision/recurrent I/O for selected checkpoint | CLOSED_RUNTIME | 81D + dual RGB + Head RGB + meta6 -> deterministic mean12, LSTM 2×256; E0 and E4 replay max diff 0. |
| Exact 54D A2 frame order/scales | CLOSED_RUNTIME | 54D frame, 30×54 history, first-frame replication, and name remap proved in E1. |
| 19D applied action timing and values | CLOSED_SOURCE | 12 leg + 6 arm + 1 primitive, previous applied action at policy step. |
| Delta reset/backmap exact formula | CLOSED_SOURCE | Scale 0.3/clip15; stage0/reset zero. Configured backmap is a production no-op. |
| Checkpoint-resolved gains/limits | OWNER_RESOLVED_WITH_SOURCE_GAP | Use 1300/32/45 per R4 and v20+ eval overlay; adjacent GRPO config still contains legacy 80/3/10 and is preserved as a provenance gap. |
| Camera local/world quaternion and portrait convention | CLOSED_WITH_WARNING | Local IsaacLab basis conversion plus CPU axis-marker render proved; no paired Isaac runtime RGB frame. |
| Head/D435 age normalization and capture tick | CLOSED_RUNTIME | 30/30/15 Hz cache and 0.1 s normalized age order executed in E4. |
| MuJoCo availability/render backend | CLOSED_RUNTIME | MuJoCo 3.10 CPU physics; GLX/Xvfb llvmpipe rendering. OSMesa is unavailable. |
| Latch realization | CLOSED_CONSTRAINT_GATE | `constraint_gate` held/released/opened; `physical_collision` was not promoted. |
| Formal paired current Student Isaac trace | BLOCKED_INPUT_ISAAC_PAIRED_TRACE | Deferred shared Isaac hook plus non-conflicting GPU activity window. E5 comparison remains null. |
| Production `BaseSimulator`/Isaac DoorSpec integration | DEFERRED_BY_BRANCH_SCOPE | Shared files are forbidden in this additive branch; hand off spec and reference implementation only. |

Closed items will be moved into build receipts rather than silently deleted from this table.
