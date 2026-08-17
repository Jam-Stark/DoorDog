# Sim2sim contract unknowns

Last updated: 2026-08-17 17:49 HKT

Unknown values are typed here and are never replaced with zero or inferred only from dimensions.

| Contract | State | Required evidence |
|---|---|---|
| Formal Student checkpoint and matching composed config | CLOSED_SOURCE | GRPO step10 checkpoint and adjacent config selected from formal evidence. |
| Native Hydra actor instantiate/load payload keys | CLOSED_SOURCE_RUNTIME_PENDING | Production eval/trainer path and `policy_state_dict` strict load traced; actual bundle load remains pending. |
| Student actor/vision/recurrent I/O for selected checkpoint | CLOSED_SOURCE_RUNTIME_PENDING | 81D + dual RGB + Head RGB + meta6 -> deterministic mean12, LSTM 2×256; golden runtime pending. |
| Exact 54D A2 frame order/scales | CLOSED_SOURCE | Production symbols and arithmetic resolved; independent golden vector pending. |
| 19D applied action timing and values | CLOSED_SOURCE | 12 leg + 6 arm + 1 primitive, previous applied action at policy step. |
| Delta reset/backmap exact formula | CLOSED_SOURCE | Scale 0.3/clip15; stage0/reset zero. Configured backmap is a production no-op. |
| Checkpoint-resolved gains/limits | OWNER_RESOLVED_WITH_SOURCE_GAP | Use 1300/32/45 per R4 and v20+ eval overlay; adjacent GRPO config still contains legacy 80/3/10 and is preserved as a provenance gap. |
| Camera local/world quaternion and portrait convention | OPEN | Production rig source plus axis-marker render evidence. |
| Head/D435 age normalization and capture tick | OPEN | Actor/eval source and camera-meta golden trace. |
| MuJoCo availability/render backend | IN_PROGRESS | IsaacLab Python lacks MuJoCo; isolated MuJoCo 3.10 environment installation started. |
| Physical collision latch stability | OPEN | no_latch -> constraint_gate -> physical_collision probe ladder. |

Closed items will be moved into build receipts rather than silently deleted from this table.
