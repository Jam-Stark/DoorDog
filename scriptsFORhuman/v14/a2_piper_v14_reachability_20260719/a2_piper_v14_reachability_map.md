# A2_Piper v14 M18 static reachability map

Option A: root/body heights are static diagnostic placements, not action/command dimensions.

- Cell evidence: `a2_piper_v14_reachability_map.csv`
- Cells: `210`; feasible: `12`
- Highest feasible handle cap: `1.05` m
- 1.10 m allowed: `False`
- Selected standoff band: `0.55`–`0.6` m (2 grid points)
- Retained high handles (>=1.00 m) require root height >=0.70 m: `True`

## Per-handle summary

| Handle height (m) | Any feasible cell | Minimum feasible root height (m) |
| ---: | :---: | ---: |
| `0.8` | `True` | `0.55` |
| `0.85` | `True` | `0.55` |
| `0.9` | `True` | `0.65` |
| `0.95` | `True` | `0.65` |
| `1.0` | `True` | `0.75` |
| `1.05` | `True` | `0.75` |
| `1.1` | `False` | `None` |

## Feasibility rule

`tcp_error_m < 0.03` and `self_collision == false` and `min_joint_limit_margin_rad > 0.1`; missing/nonfinite evidence is infeasible.

## Deterministic selection

Choose the highest handle-height cap with a non-empty band; within that cap choose the longest continuous standoff band; ties choose the lowest band start.
