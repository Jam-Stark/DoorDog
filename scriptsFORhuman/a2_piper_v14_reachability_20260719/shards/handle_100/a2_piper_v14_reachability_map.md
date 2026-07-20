# A2_Piper v14 M18 static reachability map

Option A: root/body heights are static diagnostic placements, not action/command dimensions.

- Cell evidence: `a2_piper_v14_reachability_map.csv`
- Cells: `30`; feasible: `2`
- Highest feasible handle cap: `1.0` m
- 1.10 m allowed: `False`
- Selected standoff band: `0.55`–`0.6` m (2 grid points)

## Feasibility rule

`tcp_error_m < 0.03` and `self_collision == false` and `min_joint_limit_margin_rad > 0.1`; missing/nonfinite evidence is infeasible.

## Deterministic selection

Choose the highest handle-height cap with a non-empty band; within that cap choose the longest continuous standoff band; ties choose the lowest band start.
