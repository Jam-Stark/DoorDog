---
name: sim2sim-r5-campaign
scope: full-resolved-action-warp r5 MuJoCo paired campaign and staging-band probe
status: r5_complete_in_contract_0_of_8_base_still_e5_pending
last_updated: 2026-08-18 23:57 HKT
read_when:
  - preparing any future A2_Piper sim2sim runner that maps Student actions to MuJoCo writes
  - interpreting the r5 Student-under-gap evidence or the staging-band probe split
  - resuming E5 after the Isaac paired trace handoff arrives
---

# Sim2sim r5 full-action-warp campaign

Every future sim2sim runner must map raw Student actions through the full resolved production warp (`gr00t/rl/sim2sim/mujoco/action_warp_r5.py`): base scale 0.25/0.4 with posture `[-1,1]` clamp and the resolved 5D clamp `±[0.5,0.5,0.5,0.4,0.4]` loaded from the config snapshot (never hardcoded), arm delta scale 0.3/clip 15 with the stage0 gate, gripper primitive, leg name map, and the final 20D clip at `action_clip_value=100` before `default + 0.25*action` targets. The clipped physical command is the single truth feeding gait clock, frame builder, observation echo (multipliers 2/2/0.25/1/1 + 0.1 deadband), stage predicate, stage traces, and receipt norms. The 11-node audit receipt is `artifacts/e5/action_warp_r5/` (NONE_MISSING). Note the semantic: posture axes hit the ±0.4 cap via the posture clamp, so at-cap counts can be high while final-5D clip counts are zero.

r5 re-ran the unchanged eight-case manifest under this contract (r4 behavior voided by the BASE_COMMAND_CLIP recurrence; r4 artifacts byte-preserved with `paired_mujoco_campaign_r5/r4_supersession_receipt.json`). All 8 cases ran to the 20 s horizon with zero numerics/effort/mapping failures and 8/8 collision-driven hinge crossings (0 unlatch). The Student saturates the x/z command caps for ~95% of steps, y for ~44%, and never issues a base-still command: minimum in-contract first-three norm per case 0.379–0.436, base-still steps 0/1000 everywhere, stage1 never enables. Typed campaign conclusion: `IN_CONTRACT_0_OF_8_BASE_STILL_STUDENT_UNDER_GAP_EVIDENCE`.

The pre-authorized staging-band probe (`artifacts/e5/staging_band_probe_r5/`) initialized the robot stationary inside the band (dx=0.65, dy=0), command history zeroed, LSTM reset then naturally evolved, full camera rig: still 0/1000 base-still steps (min norm 0.495), robot walks out of the band (+1.15 m x). Typed `COMMAND_DYNAMICS_NEVER_CONVERGE_FROM_CLEAN_IN_BAND_START` — approach-phase history/visual transients are not the sole cause; the command generation itself never converges in this shadow. This does not adjudicate the visual channel: formal attribution stays blocked on the mandatory paired `t=0` Isaac frames (E5 unchanged).

This entry is intentionally not added to `memory/a2-piper/MEMORY.md`; add routing only during owner merge.
