---
name: sim2sim-paired-campaign
scope: READY r2 GRPO step10 fixed-case MuJoCo campaign and deferred Isaac comparison
status: mujoco_complete_isaac_input_pending
last_updated: 2026-08-17 20:19 HKT
read_when:
  - producing or comparing the fixed Isaac-MuJoCo paired campaign
  - consuming the distillation branch paired trace handoff
---

# A2+Piper READY r2 paired campaign

The campaign manifest `a2_piper_grpo_step10_legacy_door_subset_r1` contains eight explicit legacy-`door.py` cases. The domain is right/out, lever, `no_latch`, no material RNG, and `tau_static=tau_dynamic=0`; only old distillation `DoorSpawnerCfg.rand_*` fields are varied. Schema authority is sim2sim commit `2bf0ac417858128ab761fca3fa3aa8451b7ea843`, `gr00t/rl/sim2sim/schemas/paired_trace_row.schema.json`.

MuJoCo r1 completed 8 terminal episodes on CPU llvmpipe: 104 policy decisions, 408 physics rows, 408/408 torque clips, finite states. All cases terminated by base height at 0.250–0.260 s before direct handle unlatch or hinge open crossing. This is retained as pilot step10 pipeline/physics evidence, not Student-quality evidence.

E5 remains `BLOCKED_INPUT_ISAAC_PAIRED_TRACE`. Never replace the missing Isaac campaign with teacher/v24 traces or zero-valued events. The committed comparator expects `<isaac-root>/isaac_physx/<case_id>/trace.jsonl`.

This entry is intentionally not added to `memory/a2-piper/MEMORY.md`; add routing only during owner merge.
