---
name: sim2sim-standing-vitals-r2
scope: corrected handle, robot standing gate, and READY r2 MuJoCo paired campaign
status: mujoco_r2_complete_isaac_input_pending
last_updated: 2026-08-17 23:18 HKT
read_when:
  - running any future MuJoCo closed-loop campaign
  - diagnosing A2+Piper collapse or actuator placement
---

# Sim2sim standing-vitals rule and campaign r2

Every closed-loop MuJoCo campaign must first consume a `PASS / AUTHORIZED` standing-vitals receipt. Finite state is not evidence that A2 can stand.

The READY r2 composed config resolves `armature=0.03` for all 12 A2 leg joints. Omitting it caused the retained r1 campaign's systematic 0.25 s collapse. With armature restored, policy-free posture PD lands at 0.4965 m and frozen A2_Base remains upright for 5 s at 0.4459 m. Door actuators compile at IDs 0/1 and robot motors at name-resolved IDs 2–21; ctrl, actuator force, and generalized joint force audit error is zero.

Formal MuJoCo r2 completed 24,868 schema-valid rows: six horizon and two base-height terminals. E5 remains `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`. r1 is preserved and classified `INVALID_PHYSICS_SUPERSEDED_BY_R2` in the new report.

This entry is intentionally not added to `memory/a2-piper/MEMORY.md`; add routing only during owner merge.
