# A2+Piper base_v18 Optimization Plan (EN)
# Gripper realism: friction + force → enable arm-carry along the handle arc

Date: 2026-07-24 (HKT). Numbering continues **P1–P2 (probes), M39–M41**.
Warm-start baseline: **v17 release = G5 ckpt2500** (`base_v17_G5_full_m34_m35_hinge125-20260723_011415/model_step_002500.pt`, SHA-256 d7d72335…). User approved scope 2026-07-24.

---

## 0. Executive summary

v17 solved push-wide-then-release with clean factorial attribution (institution necessary — G3; pricing necessary — G2; together sufficient and replicated — G1/G5/G6: post-release contact 48/48 → **1/48**, force p95 493 N → **0**). Two things remain, and both route through the same physical bottleneck:

1. The user's ideal form — the **arm carrying the door along the handle arc** (initial forward push, then the leftward arm_j1 sweep) instead of shove-and-coast — has never appeared. Mechanical account: the forward push is form-closure (arm-strength), but the arc-following pull is **friction-transmitted at the fingertips**, bounded by μ × grip force. At effort cap 10 N and default (unverified) contact friction, tangential authority is a few N against a 27+ kg·m² door. The observed in-hold **gripper slip** (user render observation) is the same bound showing itself.
2. Posture economy failed at 10× price (paid −1.12/20 s ≈ 12% of income; low-handle pitch usage still 98–100%). It is **not price-elastic**; the open question is functional-vs-habitual, and it has a cheap zero-shot discriminator.

v18 is **capability-first**: correct the gripper toward real Piper hardware (rubber-pad friction + 40–50 N grip class, both sim2real corrections; the gain change already passed its zero-shot probe 15/16), then test whether arm-carry emerges from the *existing* wages before adding any new reward. No new shaping terms in the main run.

## 1. Findings carried from v17 (evidence base)

- Factorial: G3 (pricing-only) hinge@release pinned 1.044 → institution necessary. G2 (institution-only) relapsed to 14/16 contact, 485 N by 2500 → pricing necessary. G1/G5/G6 → 0 contact; replicate G6 rules out basin luck. G5 opened to 1.404 despite its 1.25 threshold — the corridor wage covered the last 0.15 rad once the release-at-threshold habit broke.
- Release endpoint (G5 2500, 3 seeds × 16): 48/48 goal, all mass/spring/height buckets 100%, crossing-while-holding 48/48, hinge@release p50 1.4044, post-release contact 1/48 (F max 114 N), pre-crossing bilateral 99.80%, coasting 0.05%, hinge-vel p95 0.336.
- Decomposition at endpoint: posture −1.121, hold_and_drive +1.711, corridor-wide +0.219, clean-passage +0.262, body-event −0.003 (nothing left to charge).
- **M36 zero-shot gain probe PASSED**: effort 45 N / Kp 1300 / Kd 32 → 15/16 goal, bilateral 99.93%, 0 sign-flip frames (0/4298). Change is adiabatic for the current policy.
- Posture: λ=−1.5 paid in the target band with no behavior change (98–100% low-handle pitch). Price-elasticity falsified; discriminator needed (P2).
- Ops: 4/30 candidate checkpoints emitted null telemetry (`G4/500`, `G4/1500`, `G6/1000`, `G6/1500` — strict-invalid, 0/10 gates despite 15/16+ goal). Telemetry pipeline bug, not policy fact.
- User render observations reconciled: calf-kicks belong to ablation cells G2/G3/G4 (contact events, up to 325 N in G2's heavy env); G1@2000 and released G5@2500 renders show 0 contact. The "carry" gap is real but distinct from the (solved) collision gap.

## 2. Probes (no training; run before the main run)

### P1 | Slip quantification probe
From the G5 ckpt2500 endpoint traces (already on disk), measure fingertip slip: TCP displacement **along the handle axis** (source-frame Y of `target_pos_source_handle`) accumulated while bilateral contact holds, per env, split by opening phase vs corridor. Deliver: slip p50/p95 (cm) — the v18 before/after headline metric. (Honest note: not yet quantified; user observed visible sliding in renders.)

### P2 | Posture discriminator probe
Zero-shot eval of G5 ckpt2500 with the **pitch command clamped to 0** (and a second pass clamping roll), heights 0.80–0.95 grid.
- Goal collapses at low handles → pitch is **functional** (raised arm base needed for the press-down unlatch geometry given non-commandable trunk height): retire the <30% posture target, drop `penalty_a2_posture_command_l1` to a token −0.3 (drift guard), and record that the force_feasible "minimal-intervention" instantiation moves to the arm-limit round where a real trade exists.
- Goal holds → pitch is **habitual**: schedule the scratch posture experiment (with basin-forcing curriculum) as its own branch; do NOT fold into v18 main.

## 3. Change list

### M39 | Gripper realism package [required, the round's core]
Both changes are corrections toward real Piper hardware (rubber-padded fingers, 40 N nominal / 50 N peak grip; user authorized 45 N):
1. **Finger-pad friction**: first *verify* current μ on arm_body7/8 (and handle) — the outstanding v13-M2 item; then set physics material μ_static/μ_dynamic ≈ **1.2 / 1.0** on arm_body7/8 (handle stays default).
2. **Adopt M36 gains**: `dof_effort_limit j7/j8 10 → 45`, `Kp 800 → 1300`, `Kd 25 → 32`, `a2_stage2_squeeze_force_max 20 → 30`, `a2_stage2_over_force_threshold 40 → 55`.
3. **Combined zero-shot probe** before training (friction+gains together on the frozen policy): gate = goal ≥ 15/16, bilateral ≥ 99%, no finger chatter (j7/j8 velocity spectrum), over-force (new scale) < 2%. Gains alone already passed; this catches friction interactions.
4. Expected effect: tangential grip authority ↑ ≈ 5–6× (μ ~1.5–2× × N ~3×) — the capability behind arm-carry and slip elimination.

### M40 | Main run and judgement — capability-first, no new rewards
**v18_main**: M39 only, warm-start G5 ckpt2500 (policy_only), 2500 iters, save 250, resource 4×1024 (back to lineage scale; the v17 factorial is done). Midpoints 500/1000/1500/2000 with behavior + decomposition audit (standing M37 rule).

| Metric | Target | v17 baseline |
|---|---|---|
| goal canonical / pooled 48 | ≥15/16 / ≥46/48 | 16/16 / 48/48 |
| slip (P1 metric) p95 | **≤ 50% of P1 baseline** | TBD by P1 |
| hinge@release p50 | ≥1.40 (not regress) | 1.404 |
| post-release contact / force p95 | ≤2/48 / <80 N | 1/48 / 0 |
| **arm-carry emergence** (observational): hinge at *hold-end* vs release gap; corridor-wide paid | carry ↑ ⇒ corridor-wide paid ↑ (>0.4) and door reaches 1.5 while held more often | 0.219 |
| pre-crossing red-lines | bilateral ≥99%, coasting <2%, over-force <2% (new scale) | 99.8/0.05/0.53 |
| j8 open-limit (unlatch press) | < 8% (expect drop with 45 N authority) | ~11% |
| crossing-while-holding pooled | ≥46/48 | 48/48 |

Contingency (pre-approved): if carry emerges partially, raise `a2_corridor_door_wide` normalization 1.5 → 1.8 in a follow-up 1000-iter continuation — only after M39 capability is confirmed, never concurrently.

### M41 | Ops
1. Fix the null-telemetry checkpoint bug (4/30 in v17 candidate matrix) — exporter must fail loudly or emit complete rows.
2. Memory: v17 factorial conclusions (institution+pricing both necessary), posture price-inelasticity + P2 outcome, M36 probe PASS, slip/friction mechanical account, "capability-first before shaping" as the standing design rule (4th application: latch, spring, arm-limits, now friction).
3. Long-term TODO sync (done this round): arm-limit realism (feasibility boundary for force_feasible) remains the next round after v18; body-push emergence explicitly expected only after that boundary exists (user position, agreed).

## 4. Checklist
1. [ ] P1 slip baseline from existing traces; P2 posture discriminator (two zero-shot evals).
2. [ ] M39.1 μ verification + material change; M39.3 combined zero-shot probe (gate before training).
3. [ ] v18_main; midpoints with decomposition + slip + carry observables.
4. [ ] Endpoint: canonical + 3-seed 48-door + renders (low-handle light, high-handle heavy, ≥150 kg strong-spring; reviewer watches for the j1 leftward sweep / carry form).
5. [ ] M41 telemetry fix; memory entries; TODO sync.
