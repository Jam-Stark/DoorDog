# Paired campaign handoff to the distillation branch

This directory is the fixed Isaac↔MuJoCo case set for READY r2 / GRPO step10. The eight `DoorInstanceSpec` files use only fields already expressible by the distillation branch legacy `door.py`. Every case is right-hinge, out-opening, lever-handle, `no_latch`, explicit/no-RNG, and has `tau_static = tau_dynamic = 0`. The campaign therefore excludes `FRICTION_SEMANTIC_GAP`; do not add a friction overlay or silently expand the case domain.

## Minimal additive consumer

Add a distillation-only consumer beside, not inside, shared production behavior. It should load one case and map exact values onto `DoorSpawnerCfg`: panel width/height → `rand_door_width`/`rand_door_height`; handle height/edge offset → `rand_door_handle_height`/`rand_door_handle_width`; mass → `rand_door_weight`; side/direction/type → `rand_door_open_lr`/`rand_door_open_io`/`rand_door_handle_type`; handle axle/lever/radius → their `rand_*` fields; hinge effort/stiffness → `rand_hinge_drive_max_force`/`rand_hinge_drive_stiffness`; handle effort → `rand_handle_drive_max_force`; and `build_latch=False`. Preserve the old builder's fixed hinge damping `50`, handle damping `0.5`, and handle stiffness `50`.

Legacy consumer authority:

- commit: `a197255212fa65dd9e02337b7971daac71c944fe`
- path: `gr00t/rl/isaac_utils/playground/env_rand/door.py`

After spawn, print a `DoorMechanicsUnitContractV1` receipt containing requested trace-rad, realized USD-degree readback, and normalized rad faces. Record realized width, height, handle pose, mass, hinge damping/stiffness/effort, side, direction, and latch mode. Missing realized values stay typed; never fill them with zero.

## Trace producer

Copy `gr00t/rl/sim2sim/schemas/paired_trace_row.schema.json` from sim2sim commit `0e82607dac859ac7cf35ab25faff69aed357a9af`. Record that commit and path in the Isaac producer receipt; no content hash is required. Emit UTF-8 JSON Lines, one row after every 200 Hz physics step, using the schema exactly. Reset the Student LSTM, action/delta state, A2_Base 30-frame history, camera caches, robot/door state, and seed from `paired_case_manifest.json` for every case. Keep terminal and failed episodes in the dataset.

Task fields are direct state facts: `unlatched` is `handle_hinge >= pi/6`; `open_threshold_crossed` is `door_hinge >= 0.174533 rad`. They are not reward or stage-machine outputs. Pixel data remains domain-gap evidence and must not decide policy regression.

Return one directory containing the copied schema, the unchanged manifest and DoorInstanceSpecs, `isaac_physx/<case_id>/trace.jsonl`, per-case realized mechanics receipts, and a top-level producer receipt with commit+path identities. The sim2sim comparator will consume that directory without modifying the distillation branch.
