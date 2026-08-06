# Pull-Open-Door Task TODO

- 2026-08-06 14:00 HKT - P4 capability boundary: E6/E7 (path reversal, whole-body clear) never reached by any seed in any phase (P2/P3/P4). The pull policy can acquire/capture/progress/clearance-decide but cannot reverse path + clear whole body. Next direction: investigate why E6/E7 is unreachable (path reversal mechanics, doorway clearance geometry, or reward/curriculum design for the clear phase). Requires user direction on scope.
- 2026-08-06 14:00 HKT - seed1 instability: E2-E5 oscillates between 2/16 and 16/16 across checkpoints. Uniform across strata — not explained by spawnHook or hinge force. Possible causes: training instability, reward landscape, or seed-specific basin. Consider matched replicates or longer training to resolve.
