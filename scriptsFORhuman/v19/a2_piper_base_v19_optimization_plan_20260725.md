# A2+Piper base_v19 Optimization Plan (EN)
# Carry, fairly tested: remove the self-built income cliff; fix stiff-finger overspeed; stop taxing load-bearing posture

Date: 2026-07-25 (HKT). Numbering: **P0 (pre-run), M42–M44**. Prior: v18 plan + v18 analysis (in-chat, 2026-07-24).
Warm-start: **re-adjudicated v18 release — expected ckpt1500** (pending P0.1; endpoint-2500 is a drifted checkpoint, not the round's verdict).

---

## 0. Findings recap from v18 (basis for every choice below)

1. **Self-built income cliff (the round's core lesson)**: the carry target (held hinge ≥1.5) sat *above* M35's own pay ceiling (`release_hinge_threshold=1.40` cuts hold income). Held hinge p95 = 1.4223 hugging the cliff; 0/44 ≥1.5; midpoint 4/16 ≥1.5 was unpaid exploration being correctly extinguished. **A behavioral target above the pay ceiling is a null experiment** (income-cliff rule, 4th instance — this time by the plan author). v19 moves the ceiling before re-testing carry.
2. **Corridor "slip" is kinematic accommodation**: p50 ≈ 11 cm ≈ handle length — sliding to the handle end while walking through is how hold-through-crossing coexists with arm reach. Retired as a target; observability only. The true grip metric — opening slip — improved 3.5× under M39 (8.36→2.37 cm p95): friction+force worked where intended.
3. **Genuine new pathology**: `upper_dof_overspeed` terminations (4/8 endpoint failures) from Kp 800→1300 finger stiffening — velocity spikes on contact snap/handle-end events. Needs a dynamics fix, not threshold relaxation.
4. **Endpoint drift + M22 skipped twice**: midpoints 1000/1500 were 16/16 strict-VALID with all door-income terms higher than 2500. Checkpoint selection must become mechanical.
5. **P2 landmark**: pitch-clamped goal 2/16 (collapse) → **pitch is functional** (trunk height non-commandable; press-down unlatch needs the raised arm base at every height); roll-clamped 9/16 (partially load-bearing). Two rounds of posture-economy shaping were taxing load-bearing behavior (−5.3/episode at λ=−1.5). Target retired; tax cut to token.

## 1. P0 — pre-run gates (no training)

1. **Re-adjudicate v18**: 3-seed endpoint + 48-door report at ckpt1500 (ckpt1000 as control). Passing red-lines → v18 release = 1500 = v19 warm-start. Record the re-scored v18 verdict.
2. **Make M22 mechanical**: eval runner adjudicates *all* saved checkpoints against the red-line set before any "endpoint" is declared (protocol has been skipped in v14 and v18).
3. **Overspeed diagnosis**: from v18 endpoint traces, identify which DOFs trip `upper_dof_overspeed` (expected j7/j8 prismatic snaps; possibly arm j1–j6 during the release shove). Output decides the M43 fix variant.

## 2. Change list

### M42 | Carry institution, contradiction-free [core]
- `a2_stage4_release_hinge_threshold: 1.40 → 1.60` — hold income now covers the carry zone.
- `a2_corridor_door_wide` normalization `min(hinge/1.5,1) → min(hinge/1.8,1)` — wage gradient alive through 1.6+.
- `a2_stage4_to5_door_hinge_threshold` stays 1.25/1.35 as trained (advance unchanged; only the pay ceiling moves).
- Target (correctly placed this time): **held hinge p50 ≥ 1.45, inside the paid zone**; held p95 expected to hug the new 1.60 cliff — that signature is success, not failure.

### M43 | Stiff-finger overspeed fix [required; variant chosen by P0.3]
- Variant F1 (fingers): j7/j8 `Kd 32 → 40` + finger raw-action rate limit (|Δraw| cap per step).
- Variant F2 (arm): dof-vel soft-margin penalty on j1–j6 (pre-termination shaping), gains untouched.
- Acceptance: overspeed terminations = 0/48 at endpoint; opening slip p95 ≤ 3 cm retained; bilateral ≥99%.

### M44 | Posture: no config change — verify, close out, and fix the unit bug that hid this [required, amended 2026-07-25]
**Correction (user-caught):** v18 already trained with `penalty_a2_posture_command_l1: -0.3` — the v18 plan §2-P2 pre-registered exactly this cut ("pitch-clamp collapse → token −0.3"), P2 returned *functional* (2/16) before the main run, and the work session applied it correctly. My v19 rev1 wrote "−1.5 → −0.3" from a misread of the v18 midpoint decomposition: **−5.34 is a per-episode-sum figure, while v17's −1.12 was per-/20s** — reconciled (−5.34/20 ≈ −0.27) it matches λ=−0.3 at ~100% usage exactly. Consequences:
1. M44 config action = none (verify −0.3 present in warm-start config; it is).
2. The "tax squeezes income margin → contributes to late degradation" hypothesis from the v18 analysis is **dead**: the tax was already cut and degradation happened anyway. The 1500→2500 degradation suspects narrow to **overspeed dynamics + post-saturation drift** — sharpening M43's importance.
3. Ops (add to P0.2 scope): all decomposition reporters must label units explicitly (`/20s` vs `episode-sum`); this exact unlabeled unit change produced a wrong cross-round inference.
4. Memory: posture campaign formally closed (functional verdict; two shaping rounds against load-bearing behavior).

## 3. Run matrix (user directive: multi-group ablation; 8 GPUs; **4096 envs per group**)

v12 evidence: 4096 envs fit a single A6000 (~13 GB) → **1 GPU × 4096 envs per group**, identical global batch to the 4×1024 lineage. 7 training groups + 1 GPU reserved for the mechanical-M22 eval queue. All groups warm-start from the P0.1 release, 2500 iters, save 250.

| Group | thr / norm | posture λ | overspeed fix | Question |
|---|---|---|---|---|
| **G1 (main)** | 1.60 / 1.8 | −0.3 | yes | the intended v19 |
| G2 | 1.60 / 1.5 | −0.3 | yes | is the norm raise needed, or does the ceiling move alone suffice? |
| G3 | 1.40 / 1.5 | −0.3 | yes | no-carry control: tax-cut+fix alone; fallback release if carry fails everywhere ("accept shove form") |
| G4 | 1.60 / 1.8 | −0.3 | yes | **= G1 but warm-started from drifted ckpt2500**: is a drifted endpoint recoverable, or is early-checkpoint selection (M22) load-bearing? (replaces the retired tax-restore cell — v18 already ran at −0.3, so λ=−1.5 would test tax *restoration*, a dead hypothesis per M44) |
| G5 | 1.60 / 1.8 | −0.3 | **no** | is the fix necessary / what does it cost? |
| G6 | = G1 | −0.3 | yes | replicate (nondeterminism/basin check — paid off in v17) |
| G7 | **1.80 / 2.0** | −0.3 | yes | geometric hold-ceiling probe: where does carry physically saturate? |

Judgement (endpoint, canonical + 3-seed 48-door; release by mechanical M22 across all midpoints):

| Metric | Target | v18@1500 baseline (pending P0.1) |
|---|---|---|
| goal canonical / pooled | ≥15/16 / ≥46/48 | 16/16 seed0 |
| held hinge p50 | **≥1.45** (G1/G2/G6); G7 reports its own plateau | 1.347 |
| overspeed terminations | **0/48** | 4/8 failures @2500 |
| opening slip p95 | ≤3 cm | 2.37 |
| hinge@release p50 | ≥1.55 (G1) | 1.404 |
| post-release contact / force p95 | ≤2/48 / <80 N | 0 / 0 |
| pre-crossing red-lines | bilateral ≥99%, coasting <2%, over-force <2% | pass |
| crossing-while-holding | ≥46/48 | 41/48 @2500 (drifted) |
| render check | arm_j1 leftward sweep during carry (delta > 0.3 rad) | ≈0 |

Contingencies (pre-approved): G1/G2 carry stalls below 1.45 while G7 shows a plateau ≥1.5 → the ceiling is kinematic, accept the plateau and re-target; overspeed persists in all fixed groups → revert Kp 1300→1000 as F3 and re-probe zero-shot.

## 4. Checklist
1. [ ] P0.1 re-adjudication (flips the v18 verdict if 1500 passes) → warm-start locked; P0.2 mechanical M22 in runner; P0.3 overspeed diagnosis → M43 variant.
2. [ ] M42/M43/M44 config diffs ×7 groups; smoke each (64 env × 50 iter: decomposition sanity, no NaN, fix active).
3. [ ] 7-group launch; midpoints 500/1000/1500/2000 via the eval GPU with decomposition + behavior audit per group.
4. [ ] Endpoint: winner by judgement table; 3-seed 48-door + renders (reviewer watches for the j1 sweep / carry form; one G7 env included).
5. [ ] Memory: income-cliff 4th instance (author-inflicted) + "audit every behavioral target against the income schedule it sits on"; P2 posture verdict (functional, campaign closed); corridor-slip reinterpretation; M22 mechanization.
6. [ ] TODO sync: arm-limit realism round (force_feasible boundary) queued immediately after v19.
