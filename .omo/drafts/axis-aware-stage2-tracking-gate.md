# axis-aware-stage2-tracking-gate - Draft

## Status
- 2026-06-30 — exploration complete, all unknowns resolved from codebase
- status: awaiting-approval
- pending action: write .omo/plans/axis-aware-stage2-tracking-gate.md (append todos)

## Findings
1. Source frame axes confirmed (FacePos70 data + memory):
   - target_pos_source[:, 0, 0] = X axis (lateral, perpendicular to opening and approach)
   - target_pos_source[:, 0, 1] = Y axis = gripper opening/closing direction
   - target_pos_source[:, 0, 2] = Z axis = approach/forward direction (along gripper body)
2. Current close gate: `door_open_a2_base.py:642-678` uses `norm(target_pos_source[:, 0, :]) < 0.015`
3. Existing stage2 rewards pattern: `@StagedTaskBase.effective_in_stage(STAGE_GRASP)`, fail-fast for non-A2, use `_get_a2_stage2_close_reward_gate()` for gating
4. Reward YAML: `reward_door_open_a2_base.yaml`, shared by full 6-stage and stage0-2 quick test
5. Stage0-2 exp config (`door_open_a2_base_stage0_2_grasp_terminal_lstm.yaml:125-132`) only zeros out stage3+ rewards; no stage2-specific overrides needed there
6. `_tracking_reward_util` signature: (value, std, target, scale, offset) → tracking-shaped reward

## Adopted defaults (reversible training params)
- `a2_stage2_handle_center_y` scale: 3.0, std: 0.05
- `a2_stage2_handle_approach_xz` scale: 3.0, std: 0.05
- Close gate thresholds: y_tol=0.012, z_tol=0.015, x_tol=0.02
  - y_tol 0.012 ≈ handle_radius (0.011-0.015), ensures handle centered between fingers
  - z_tol 0.015 = approach depth tolerance ≈ handle_radius
  - x_tol 0.02 = other lateral, slightly looser
- Both new rewards added to `reward_penalty_reward_names` for curriculum consistency
- Gate thresholds as config keys in `door_open_a2_base.yaml` for tunability

## Approval gate
Approach: 4 todos across 2 waves + verification + memory. Presenting brief for user approval.
