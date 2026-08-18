---
name: sim2sim-r4-campaign
scope: true-100/45 MuJoCo stage-contract paired campaign
status: mujoco_campaign_complete_e5_pending
last_updated: 2026-08-18 11:35 HKT
read_when:
  - preparing or interpreting the next A2_Piper sim2sim paired campaign
  - changing MuJoCo action stage or robot actuator realization
---

# Sim2sim r4 paired campaign

The deployable production stage contract starts at stage0: raw arm delta is echoed but applied accumulated delta is zero. Stage0→1 occurs only after the action/physics/observation cycle when grasp-root x is `[0.5,0.8]` m, lateral error is `<0.15` m, arm default deviation is `<0.1` rad, and physical base-command norm is `<=0.1`. Normal stage1+ adds no further Student action rewrites; positive gripper opens and nonpositive closes.

The READY 100 N·m arm / 45 gripper surface is numerically stable in MuJoCo when all 20 robot joints use native position actuators, resolved kp/kv/armature/effort, and `implicitfast`. This is a declared D5 deviation from external PD: native actuator `forcerange` replaces Python per-step clipping. Standing must pass before every campaign.

r4 ran eight unchanged paired cases for 32,000 physics steps with no numerics, effort-limit, mapping, or standing failure. All cases moved toward the door, but none issued a base command at or below 0.1, so stage1 never enabled and the arm correctly remained held. Four hinge crossings without unlatch are collision-driven and not purposeful manipulation. Formal result remains `UNRESOLVED_PENDING_E5` / `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`.

Visual prerequisites pass the owner luma/hue envelope, while camera extrinsics/FOV remain frozen pending exact paired `t=0` Isaac frames. This entry is intentionally not added to `memory/a2-piper/MEMORY.md`; add routing only during owner merge.
