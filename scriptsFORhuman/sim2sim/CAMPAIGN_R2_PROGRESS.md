# MuJoCo paired campaign r2 progress

Updated: 2026-08-17 23:18 HKT

## Phase log

- Handle parity v2: commit `d7e9aa9`; rebuilt the two levers and grasp target from `door.py`, rendered both sides, merged `A2_Piper` (`Already up to date`).
- Standing-vitals gate: commit `8b2f302`; exported resolved leg armature, proved foot-floor forces and frozen-A2 standing, proved name-resolved torque placement, merged `A2_Piper` (`Already up to date`).
- Campaign runtime: commit `83f176a`; added gate consumption, door-first actuator order, name-resolved effort trace, actual saturation telemetry, and informative native RGB background after the recorded attempt0 failure; merged `A2_Piper` (`Already up to date`).
- Formal campaign: 8/8 cases, 24,868 rows, comparator/schema validation complete; artifact/report commit pending at the time this file was authored.

## Current boundary

- MuJoCo r2: complete.
- Isaac paired trace: `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`.
- E5 comparison: pending user transfer; no zeros or substitute traces.
