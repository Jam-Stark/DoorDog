---
name: sim2sim-r3-diagnostic
scope: READY GRPO Student MuJoCo action/control diagnosis
status: pipeline_defect_found_campaign_denied
last_updated: 2026-08-18 01:03 HKT
read_when:
  - interpreting READY r2 MuJoCo results
  - preparing another closed-loop sim2sim campaign
---

# Sim2sim r3 action/control diagnosis

The READY bundle is a GRPO-finetuned Student with 467/512 (91.2%) Isaac success, not a pilot. MuJoCo failure is not expected Student behavior.

r2 had two hard pipeline defects: it forced arm delta stage 1 instead of production WALK_TO_DOOR stage 0, and it used 40 N·m for arm_j1–arm_j6 instead of the READY resolved 100 N·m. Stage-0 repair makes applied arm delta zero, but the 40 N·m diagnostic still has 4.87–5.60 rad arm motion. Applying the resolved 100 N·m surface causes MuJoCo huge-QACC at 0.065 s and fails the standing gate. No closed-loop campaign is authorized until the resolved control surface passes standing.

The exact policy RGB tensor path has zero-error inverse normalization and no BGR/vertical-flip defect. Camera-meta freshness is not the sole cause. A visual domain/framing gap exists, but dominance and extrinsic/FOV attribution remain pending same-state paired Isaac RGB/E5.

This entry is intentionally not added to `memory/a2-piper/MEMORY.md`; add routing only during owner merge.
