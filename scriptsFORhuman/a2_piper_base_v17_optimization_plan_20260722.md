# A2+Piper base_v17 Optimization Plan — rev2 (EN)
# Fix the bulldoze economics: push-wide-then-release, honest pricing, calibrated shaping

Date: 2026-07-22 (HKT). Supersedes rev1 of this file (2026-07-22, zh). Numbering continues **M34–M38**.
Baseline / warm-start: **v16 release = B ckpt2000** (`base_v16_B_m29_m32_mass80_160-20260721_230405/model_step_002000.pt`), canonical 16/16, pooled 48/48, all mass/spring/height buckets 100%.

---

## 0. Executive summary

v16 delivered perfect task robustness but **all three behavior-shaping objectives failed, and the failures share one root**: the reward economics never actually offered the intended trades. v17 is not "new features" — it is a repricing round: (1) recalibrate every shaping term against the *measured* normalized reward decomposition instead of nominal per-step arithmetic; (2) make the **push-wide-then-release** route institutionally required and salaried, instead of hoping it out-bids the bulldoze route; (3) price the bulldoze route by *event impulse*, which is the only accounting under which a 2–5-frame 800 N slam is visible. The gripper effort-limit change is **deferred out of the main run** (user concern + single-axis discipline) behind a zero-shot probe gate.

## 1. Findings from v16 (what the data actually says)

### F1 — The learned strategy is "hang on, bail early, bulldoze"
Corrected mechanism description (per user's Δroot_x audit, which is right and sharper than the earlier phrasing): during the opening phase the base tracks the door closely; at hinge ≈ threshold the gripper releases; the base then advances **Δroot_x p50 ≈ +1.64 m post-release**, shouldering the door open with trunk/legs on the way (post-release body-panel contact 47/48 envs, force mean 134 N, p95 493 N, max 829 N — worse than v15's 40/48, p90 451 N). This is the exact inversion of the force_feasible thesis (arm does the work; base intervenes only when the arm is infeasible). The bulldoze route wins because it is *physically cheaper and faster*, and nothing we priced in v16 changed that.

### F2 — hinge@release pinned at 1.0402–1.0497: an institutional artifact, not a preference
The stage4→5 advance fires at hinge > 1.0472. Every door-related income stream (hold bundle, hold_and_drive, corridor_door_wide) is stage-3/4-scoped, so crossing into stage5 zeroes them instantly. "Keep pushing wider" is therefore *unpaid by construction*; releasing at the threshold is the unique rational policy. The corridor_door_wide reward (2.0) never entered the auction — it died at the stage boundary before it could pay. This is the **third instance of the stage-boundary income cliff** (v13 doorstop rent, v15 gate dead-zone, v16 unpaid push) — now a standing design rule: *any behavior that must span a stage boundary needs income defined on both sides of that boundary.*

### F3 — Shaping magnitudes were mis-calibrated by an order of magnitude
Measured end-of-training decomposition (normalized units; total episode income ≈ 9.6):
- `penalty_a2_posture_command_l1` paid **−0.095** (≈1% of income) → posture usage rose to 97.7%/98.5% (low/high handle) from v15's 79%/81%. The penalty was active and simply ignorable.
- `penalty_a2_door_body_contact` paid **−0.008**: the slam is a 2–5-frame impulse; per-step pricing of an impulsive event collects almost nothing regardless of the per-step scale.
- `a2_corridor_door_wide` paid 0.14 vs `hold_and_drive` 0.80 — and see F2: scoped out before it mattered.

**Method rule (memory-worthy):** calibrate every new shaping term against the measured normalized decomposition of the *previous* run, targeting 5–15% of total income when fully engaged; and audit the decomposition at every midpoint eval. v16's midpoints checked only goal, so the pre-approved escalation knobs were never triggered.

### F4 — Secondary facts
- j8 open-limit ≈ 9–12.5%, flat across all mass/spring/height buckets — a constant background of the unlatch-press reaction, not load-coupled; it does not gate anything today.
- Variant A (mass 80–120) showed stage0 null-standoff failures (2–5 envs stuck at stage0 across checkpoints); B showed none. Both variants ran the identical reward stack — recorded as a watch item (likely basin/nondeterminism), not root-caused; release is B.
- Mass buckets all 100% goal: within simulated actuation the 80–160 kg range crosses no feasibility boundary, so no differentiated behavior can appear (see §2-D4).

## 2. Decisions on the five open questions

**D1 — Gripper effort limit (user concern upheld; deferred).** Project memory indeed records that actuator-gain changes have flipped policy basins before (v12 B/D 160/6 → avoidance basin; v13_B Kp80 grip destroyed by training noise within 250 iters). Changing the finger actuator mid-lineage while simultaneously repricing three rewards would make v17 unattributable. Decision: **M36 is removed from the v17 main run** and parked behind a *zero-shot gain probe*: evaluate the frozen v17 release policy under (effort 45 N, Kp 1300, Kd 32) with no training — the policy-as-probe method from M23. If goal and grasp red-lines hold zero-shot, the change is adiabatic and can be adopted in v18 warm-start; if they collapse, design an adaptation schedule (gain ramp over first 300 iters). Nothing today is blocked on it (j8 11% is background).

**D2 — Route choice: "push far before release" (user proposal adopted, hardened).** Wages alone lost the auction in v16; v17 makes wide-open a *requirement*, not a bid: raise the stage4→5 hinge condition itself (M35.1). The arm does not need to *hold* to 1.35 rad (the hold ceiling is ≈1.2 by handle-arc geometry); it needs the door to *reach* 1.35 while the robot crosses — an end-of-hold shove that lets the door coast through the threshold satisfies it. This is exactly the user's "先推远再松手", encoded in the stage machine where it cannot be out-bid.

**D3 — Pitch overuse: not primarily a warm-start artifact; scratch retrain rejected for now.** Warm-start entrenchment is real but incentive-responsive: this same lineage un-learned the v13_A doorstop equilibrium and re-learned staging when incentives materially changed. The v16 posture penalty failed on magnitude (1% of income), not on lineage immunity. Sequence: try the ×10 recalibration (M34.1) first; escalate λ at midpoints if usage does not fall; scratch retrain (with forced-close curriculum + staged-reset seeding, given the historical 3-of-4 scratch basin failures) is recorded in the TODO as a last-resort contingency, not a v17 action.

**D4 — Spring (hinge resistance) widening beyond 12 N·m: rejected for v17.** Differentiated "arm vs base" behavior requires a *feasibility boundary inside the randomized range*. In simulation the arm pushes through the handle by form closure with ~100 N-class joint effort: neither 160 kg nor 20 N·m crosses any boundary, so widening either axis buys noise, not differentiation. The boundary arrives when arm joint limits are set to real Piper specs (v18, TODO B-table) — after which the *existing* 2.5–12 N·m range already spans infeasible territory. (Side note: a stronger spring would coincidentally punish bulldozing harder, but M34.2's event pricing does that attributably.)

**D5 — Language/format.** This and all future plans and replies in English; each plan carries an explicit Findings section (§1) and decision log (§2).

## 3. Change list (M34–M38)

### M34 | Shaping recalibration by measured decomposition [required]
1. **Posture economy**: `penalty_a2_posture_command_l1: -0.15 → -1.5` (target paid magnitude ≈ −0.9, ~10% of income at v16 usage; ladder −1.0/−2.0 pre-approved). Success: low-handle pitch usage < 30%, p50 off the clip; high-handle usage retained; height-bucket goal unchanged.
2. **Event-based body-contact pricing** (replaces per-step form): a contact *event* = body-panel force rising through 5 N until falling below it; charge once at event end: `-3.0 × min(F_peak / 200 N, 2.0)` (an 829 N slam ≈ −6.0; a typical bulldoze pass of 2–3 events ≈ −8 to −15 — decisively visible against the ~1 s the bulldoze saves). Per-env event state machine with reset/stage-boundary clearing; arm-panel and handle contact remain free.
3. **Corridor clean-passage wage**: `a2_corridor_clean_passage: +1.0` per corridor step with zero body-panel contact — a continuous cash flow that compensates the time cost of doing it cleanly.

### M35 | Push-wide-then-release as an institution [required, core]
1. **Raise the stage4→5 hinge condition**: new config key `a2_stage4_to5_door_hinge_threshold: 1.35` (was hard-coded 1.0472 in `_stage_4_to_5_advance_condition`). Crossing only counts when the door has actually been sent wide — the requirement cannot be out-bid. (Condition is instantaneous: shove-then-coast satisfies it; holding to 1.35 is not required.)
2. **Stage-boundary income continuity** (F2 fix): `a2_corridor_door_wide` and `hold_and_drive` effective through **stage5 while holding**; corridor velocity saturation 0.4 applies there too.
3. `a2_stage4_release_hinge_threshold: 1.05 → 1.40` (hold-bundle wages continue through the push-wide phase, aligned with the new advance threshold).
4. `a2_corridor_door_wide: 2.0 → 4.0`, wide-target normalization `min(hinge/1.5, 1)` unchanged.
5. Contingency (pre-approved): if midpoint hinge@release p50 < 1.2, escalate corridor_door_wide → 6.0 and/or lower the advance threshold to 1.25 (geometry fallback).

### M36 | Gripper effort sim2real correction [DEFERRED — probe-gated, not in the main run]
Zero-shot probe after v17 release: eval frozen policy under `effort 45 N / Kp 1300 / Kd 32 / squeeze_max 30 / over_force 55`. Probe PASS (goal ≥ 15/16, bilateral ≥ 99%, no chatter) → adopt in v18 warm-start config. Probe FAIL → gain-ramp adaptation schedule, separate run. Rationale: D1.

### M37 | Run plan and judgement — parallel ablation matrix (8 GPUs available)

All groups warm-start from v16 B ckpt2000 (policy_only), 2500 iters, save 250, **1 GPU × 1024 envs each** so every cell shares identical batch dynamics (internally comparable; note the batch-size caveat vs the 4×1024 v16 lineage when comparing absolute numbers). Two GPUs stay free for the midpoint/endpoint eval queue.

| Group | Config | Question it answers |
|---|---|---|
| **G1 (main)** | M34 + M35 full | the intended v17 |
| G2 | M35 only (institution, v16 pricing) | does the raised threshold alone flip the route? |
| G3 | M34 only (pricing, v16 institution) | does honest pricing alone suffice? (predict: no — F2) |
| G4 | neither (v16 stack continued) | drift control / warm-start baseline |
| G5 | G1 with `a2_stage4_to5_door_hinge_threshold: 1.25` | threshold-geometry sensitivity, de-risks the 1.35 bet |
| G6 | G1 replicate, training nondeterminism re-roll | basin sensitivity (history: 3/4 scratch runs basin-flipped) |

Selection: winner = best cell on the judgement table below; release ckpt by M22 red-line protocol within that cell. Escalation knobs (corridor_wide 6.0, posture λ ladder) become targeted follow-up cells only if G1/G5 midpoints demand them. **Midpoint evals (500/1000/1500/2000) must audit behavior metrics and the reward decomposition table per group**, not only goal — v16's knobs went untriggered because nobody looked.

| Metric | Target | v16 baseline |
|---|---|---|
| goal (canonical / pooled 48) | ≥15/16 / ≥46/48 | 16/16 / 48/48 |
| hinge@release p50 | **≥1.35** | 1.044 (pinned) |
| post-release body-contact envs | **≤10/48**, F p95 < 80 N | 47/48, 493 N |
| low-handle pitch usage | **<30%** | 97.7% |
| high-handle capability | height-bucket goal not degraded | 24/24 |
| pre-crossing red-lines (scoped) | bilateral ≥99%, coasting <2%, over-force <2% | 99.9/0.05/0.12 |
| crossing-while-holding | ≥15/16 pooled | 47/48 |
| posture penalty paid (decomposition) | −0.6 … −1.2 | −0.095 |
| Δroot_x post-release with body contact | shrinks toward 0 (bulldoze distance) | +1.64 m p50 |

Risks: M35.1 raises task difficulty → watch stage4 dwell/overtime at midpoints (fallback 1.25); M34.1 ×10 collapses high-handle reach → λ ladder down; event penalty punishes the final residual graze → acceptable if ≤10/48 and low-force.

### M38 | Evaluation additions
Mass-bucket continuous metrics (episode length, post-release peak force, opening-phase duration) — the correct lens for Q3-type questions while all buckets sit at 100% goal; posture-value evidence remains "usage stratifies by handle height after M34.1 works".

## 4. Checklist
1. [ ] M34 (event state machine: reset + stage-boundary clearing; decomposition telemetry per midpoint) + M35 (new config keys; income scoping through stage5-while-holding).
2. [ ] Smoke: posture penalty ≈ −0.6…−1.0 in decomposition; event penalty visible in a forced-bulldoze episode; corridor income alive in stage5; stage4→5 threshold honored.
3. [ ] v17_main; midpoints per M37 (behavior + decomposition audit, not goal-only).
4. [ ] Endpoint: canonical + 3-seed 48-door + renders (low-handle light door, high-handle heavy door, ≥150 kg strong spring).
5. [ ] M36 zero-shot gain probe after release selection.
6. [ ] Memory: F2 design rule (3rd instance), F3 calibration method, D1 deferral rationale, D4 boundary argument; update `a2_piper_longterm_TODO.md` (done this round).
