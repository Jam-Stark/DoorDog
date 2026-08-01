# Worker Prompt — v20 Route-A Dependent-Variable Readout (zero-training round closure)

Repo: `/home/baoquanc/workspace/DoorDog-A2_Piper`. Read first: `scriptsFORhuman/a2_piper_project_handoff_20260725.md` §8 and rules 11–12; `scriptsFORhuman/v20_R2/a2_piper_base_v20_R2_admission_and_execution_plan_20260730.md`; `base_v20_R3_eval_handoff_20260731.md`.

## Objective (one sentence)
Compute and adjudicate the v20 round's **dependent variable** — door angle at the robot's crossing moment — across the existing 70-checkpoint Route-A corpus, and declare the round's verdict. **No training. No gate/threshold relaxation.** New evals only under the fallback in step 2.

## Why (context you must not lose)
v20 exists to fix one thing: v19 policies crossed the door plane at hinge ≈0.7–0.8 rad and satisfied the raised release ceiling by base-drag (v19 55-valid-ckpt ceiling: hinge_at_crossing_p50 = **0.7869**, 0/55 ≥0.9; root_x_at_release p50 0.686). Route A (`logs_eval/base_v20_R2/m22_r3_route_a_f8e3197_offline_20260801/`) proved task health (goal 14–16/16 broadly) but its summary (`ROUTE_A_METRICS.csv`) contains only goal/crossing/held_crossing — **not the round's target metric**. Standing rule 12: a round's summary table must contain the round's own dependent variable. Your job is to close that gap.

## Steps

1. **Inventory** one `runs/G1/step_002500_*/record_set.json`: list available per-episode fields. Determine whether per-step traces (or per-episode `hinge_at_crossing` / `root_x_at_release` fields) exist in the Route-A runs.
2. **Compute per episode** (1120 records; first-episode protocol):
   - `hinge_at_crossing` = door hinge angle at the first frame with `root_x > 0` (env-origin frame, same convention as prior rounds);
   - `root_x_at_release` = root x at the last bilateral-contact frame;
   - `held_hinge_max` = max hinge while bilateral contact holds;
   - carry-forward: goal, crossing-while-holding (already present).
   **Fallback** if traces are absent from Route-A runs: re-run matched eval (seed0/16env, canonical protocol) ONLY for a shortlist — every group's step-2500 plus its best-goal checkpoint (≤14 runs) — with trace export on, then compute the same quantities. Do not re-run all 70.
3. **Aggregate** per group × checkpoint: p50/p95 of each metric. Emit `SEND_METRICS.{json,csv,md}` alongside `ROUTE_A_METRICS.*` (same directory, same provenance/digest discipline as the existing lock system). Units labeled (rad / m). N/A — never 0 — for missing denominators.
4. **Adjudicate** with the pre-registered rule (do not invent another): **winner = max hinge_at_crossing_p50 subject to goal ≥15/16** at that checkpoint. Comparisons to report explicitly:
   - each send-curriculum cell (G3, G4, G5) vs G2 (economics-only) vs G1 (continuation control) — attribution;
   - G7 vs G6 — seed/replicate check;
   - all vs the v19 baseline **0.7869**. Effect language: ≥1.1 rad = real effect; 0.85–1.1 = partial; ≤0.85 = the send curriculum did not bind.
5. **Renders**: 3–5 episodes of the winning checkpoint (standard 3-cam protocol, include one high-mass and one strong-spring env). The single reviewer question, stated in the QA notes: *is the door visibly wide BEFORE the base enters the door frame?*
6. **Report + memory**: verdict section in `SEND_METRICS.md` (winner, attribution, v19 comparison, render answer); update `memory/a2-piper/push-open-door-optimization/` (`description/DONE/TODO`, HKT timestamps) and tick the A-table item in `scriptsFORhuman/a2_piper_longterm_TODO.md`. If the verdict is "did not bind", say so plainly — a clean negative closes the round and routes to the institutional fallback already recorded in the TODO (gate walk-income/corridor latch on `hinge≥θ & root_x<0`); do **not** attempt that fix yourself.

## Guardrails
- Zero training; zero reward/config changes; fallback evals are read-only measurements of frozen checkpoints.
- Keep the existing lock/admission provenance discipline, but the deliverable is the measurement, not more governance.
- Verify from raw records/traces; do not trust any prior summary's interpretation (rule 10).
- If a record set fails strict validation, mark that checkpoint N/A with the reason — do not silently drop or backfill.
