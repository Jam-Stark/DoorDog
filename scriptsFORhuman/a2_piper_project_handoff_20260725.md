# A2+Piper Door-Opening RL — Project Handoff (EN)

Date: 2026-07-25, **updated 2026-08-01 (v20 incorporated)**. Author: diagnosis/planning session (Claude), covering base_v12 → base_v20.
Audience: the successor **planner session** (Claude) taking over diagnosis, planning, and work-session handoffs.
**Project decision structure**: a planner (a Claude session like this one, or a cloud pro model — both have produced adopted plans) writes the detailed next-round plan; **worker sessions** implement, train, and eval; the user arbitrates between planners. The cloud pro model authored v20 (its diagnosis is endorsed and canonized below); versioned plans are indexed in `scriptsFORhuman/README.md` and stored under their corresponding `scriptsFORhuman/vX/` directories.
Repo root: `/home/baoquanc/workspace/DoorDog-A2_Piper`. Plans/replies in **English** (user directive since v17); repo memory entries follow repo conventions (zh + EN technical terms, HKT timestamps).

---

## 1. NORTH STAR — the final expected policy behavior (do not drift from this)

**Task**: A2 quadruped with a front-mounted Piper arm opens a latched, self-closing, randomized door (currently right-hinge, out-opening/push; `build_latch=True` — the latch is real, a mimic-joint cone retracted by handle rotation) and walks through to x > 1.5 m.

**The ideal episode, phase by phase** (each clause is a hard-won requirement — see §4 for the history behind it):
1. **Approach & stance**: walk to a *self-chosen* standoff inside the staging band (stage0 advance requires base-still inside the band — the policy picks its stance, config does not).
2. **Lean & reach**: pitch-up (and roll) to raise the front arm mount — **this is load-bearing behavior, not waste** (P2 probe: pitch-clamped goal collapses 2/16; trunk height is NOT commandable — the 5-D base command is [vx, vy, yaw_rate, pitch, roll]).
3. **Grasp**: bilateral finger grasp on the handle, debounced at control-rate (K=5 streak), squeeze in-window; no single-side lever-pressing.
4. **Unlatch**: press/rotate the handle (grasp-gated unlatch reward; handle spring returns it after).
5. **Open**: the **arm opens the door through the handle** — controlled speed pre-crossing (no flinging), zero body-door contact before crossing.
6. **Send wide & cross**: keep holding through the crossing; push the door wide (institutional requirement: stage4→5 hinge threshold + hold income covering the carry zone). The user's ideal form is the arm *carrying* the door along the handle arc (arm_j1 leftward sweep); shove-then-coast is the currently-achieved acceptable form. Fingertip slide along the handle bar during crossing (~handle length) is **kinematic accommodation, not a defect**.
7. **Release & pass**: release past the pay ceiling; walk through briskly with **zero body/leg-door collisions on normal doors** (v17 achieved 1/48).
8. **Future (not yet)**: when door resistance genuinely exceeds the arm's capability, trunk/thigh assist appears — **only then**. Today, deliberate body-push is a defect: the arm is still simulation-superhuman (~100 N-class joint effort), so no real feasibility boundary exists. The user has explicitly confirmed this ordering.

**Standing quality red-lines** (matched eval): goal ≥15/16 canonical & ≥46/48 pooled; pre-crossing bilateral ≥99%, coasting <2%, over-force <2%; crossing-while-holding ≥46/48; post-release body contact ≤2/48 & force p95 <80 N; controlled opening speed; per-bucket (height/spring/mass) non-collapse.

## 2. THE RESEARCH NOVELTY — force-feasibility-aware policy (guard this, don't dilute it)

Source of truth: `scriptsFORhuman/force_feasible/` (three design discussions). Thesis, compressed:

> Among all whole-body configurations that achieve the required force interaction, the policy should explicitly prefer the one that is **most arm-feasible** (larger torque margin, away from saturation/limits/singularity) with **minimal base intervention**: `u_base = u_user + gate(s) · u_assist`, where the gate opens only when the arm is genuinely infeasible. Training structure: main task first, feasibility preference as a **tie-breaker**; reward/constraint define "force-aware", teacher/guidance only accelerate.

**Roadmap position (critical — this is where drift happens):**
- The feasibility boundary **does not exist in the current sim**: arm joints are superhuman, so pushing any current door (spring ≤12 N·m, mass ≤160 kg, form-closure through the handle) never saturates the arm. Widening spring/mass further is a **dead axis** until this changes (verified twice: v15 §1.5, v17 D4).
- **Next prerequisite round (queued after v19): realistic Piper arm joint effort/velocity limits** — this *creates* the boundary; then the existing 2.5–12 N·m spring range already spans infeasible territory. Only after that does the gate/base-assist mechanism become learnable (a gate trained without a real boundary learns noise — v15 lesson).
- The second natural regime: **pull doors (in-opening)** — friction/hook transmission is finger-effort-limited; a genuinely different feasibility landscape. Big engineering scope (approach-side mirroring, staging signs, through-direction semantics, doorOpenIO into obs) — see memory `door-asset-randomization-baseline`.
- **Closed dead-ends (do not reopen)**: posture-economy shaping as a "minimal intervention" instance (two rounds, v16 −0.15 and v17 −1.5 ≈12% of income, both failed; P2 proved pitch *functional* — you cannot tax load-bearing behavior into disappearing); "heavy-door body-assist emergence" under superhuman arm (falsified v15: 0/10066 pre-crossing body contacts at 12 N·m).

## 3. VERSION LINEAGE (what each round proved)

| Round | Result & the one thing it proved |
|---|---|
| v8–v12 | Stalemate: "moves door XOR holds handle". v12: 2×2 factorial uninterpretable (basin lottery; H-factor reward never emitted) |
| **v13** | Root causes found: stage2→3 gate demanded 5 consecutive *physics*-frames (unattainable at light pinch — single-frame 92%, 5-frame exactly 0); grip force ceiling = Kp×0.035 (2.8 N) vs door needing ~10 N; latch discovered real (`scenario_cfg` `build_latch=True`); `push_door_handle` was an anti-grasp attractor. Fixes: control-step debounced gate (K=5), Kp 800 saturating 10 N effort, grasp-gated unlatch reward, hold_and_drive product |
| v13.1 | Goal loop closed 16/16: release-gate broke the "doorstop rent" equilibrium (scaffold that retired itself); frame-contact penalty softened for passage |
| v14 | Randomization round 1 (spring 2.5–7, handle height 0.80–1.05, staging band + base-still advance); M18 static reachability retracted — **policy-as-probe** doctrine born (policy zero-shot 16/16 at 1.05–1.10 where the scripted probe said infeasible) |
| v15 | Spring→12, height→1.10, band [0.50,0.80]: 47/48. Discovered posture pinning (~80%), release-at-threshold, bulldoze crossing |
| v16 | Mass axis 80–160 (100% all buckets). All three behavior shapings failed **for one root**: magnitudes not calibrated against measured decomposition + stage-boundary income cliffs |
| **v17** | 6-cell factorial cleanly proved: institution (raised stage4→5 hinge threshold) *and* event-relevant pricing both necessary, together sufficient & replicated. Push-wide-then-release solved: contact 47/48→1/48. Release G5 ckpt2500 |
| v18 | Gripper realism (μ 1.1/0.9 + effort 45 N/Kp1300/Kd32 — real Piper grip is 40 N nominal): opening slip −3.5×; **but** endpoint-2500 drifted (midpoint 1500 was 16/16), new `upper_dof_overspeed` failure from stiff fingers, carry target sat above the author's own pay ceiling (null experiment), P2 verdict: pitch functional |
| **v19 (closed)** | 7-group matrix on carry (release ceiling 1.60, wide-norm 1.8, overspeed fix, posture tax already −0.3). **Outcome (70 ckpts, 55 strict-valid): carry did not appear** — hinge_at_crossing_p50 never exceeded 0.7869 rad (0/55 ≥0.9); root_x_at_release p50 drifted to 0.686 m. The raised pay ceiling was satisfied by **base-drag**: cross the plane at ~0.7–0.8 rad, keep holding, let the walking base drag the door open behind it |
| **v20 (closed; cloud-pro-model authored — diagnosis endorsed)** | Root cause named correctly: **the behavioral requirement was stated at the wrong event.** All prior institutions bound door angle to stage labels or to release — never to *the robot's position at crossing*. R2/R3 trained 7 groups × 10 checkpoints; Route A produced 1120 strict-valid first-episode records/traces. The dependent-variable readout selected G4 step2500 under goal≥15/16: hinge_at_crossing p50/p95 `1.0160/1.0628 rad`, root_x_at_release p50/p95 `0.4717/0.6680 m`, held_hinge_max p50/p95 `1.2911/1.3617 rad`; delta vs v19 was `+0.2291 rad`, pre-registered label `PARTIAL_EFFECT`. Winner render QA was `YES_5_OF_5` across 5 episodes × 3 cameras. Route B (`formal_completion`/`pooled48`/`holdout64`/`final_analysis`) was not run. |

## 4. STANDING DESIGN RULES (each paid for with a failed round — cite them, enforce them)

1. **Income-cliff rule** (4 instances: v13 doorstop, v15 gate dead-zone, v16 unpaid push, v18 carry-above-ceiling): any behavior spanning a stage/threshold boundary needs income on both sides; **audit every behavioral target against the income schedule it sits on** — a target above the pay ceiling is a null experiment.
2. **Calibrate by measured decomposition**, never nominal per-step arithmetic (v16 posture −0.15 ≈1% of income; v17 fixed at −1.5 ≈12%); target 5–15% of income when engaged; **reporters must label units** (`/20s` vs episode-sum — an unlabeled unit change caused a wrong cross-round inference in v18/v19).
3. **Capability-first before shaping** (latch → gate timescale → grip force → friction): if the behavior is physically impossible or unpaid, no reward tuning helps; conversely test whether existing wages suffice once capability exists before adding terms.
4. **Mechanism over reward-carving**: make the desired behavior physically/institutionally necessary (latch made handle-press necessary; raised threshold made wide-open necessary) rather than bidding rewards against a cheaper physical route.
5. **Policy-as-probe**: the trained policy is the highest-fidelity capability instrument; any scripted probe must (a) use only *commandable* DOFs, (b) pass a known-good anchor before its verdicts count (M18 v1 and the 37-revision scripted probe both failed this).
6. **Checkpoint selection is mechanical (M22)**: adjudicate ALL saved checkpoints against red-lines; endpoints drift after goal saturation (v14 3000, v18 2500). This protocol was skipped twice — the v19 P0.2 item makes the runner enforce it.
7. **Phase-scoped constraints**: a global behavior ban (anti-fling) will outlaw a legal behavior in an adjacent phase (the release shove); scope red-lines to the phase they protect.
8. **Factorial + replicate discipline**: one axis per cell, always a replicate cell (basin lottery is real: 3/4 scratch runs historically fell into wrong basins); 8×A6000 GPUs, 4096 envs fit ONE GPU (~13 GB) so up to 7 parallel groups + 1 eval GPU, warm-start `policy_only` from the previous release.
9. **Zero-shot probe before actuator changes** (gains/friction/limits): evaluate the frozen policy under the new physics first (M36/M39 pattern); gain changes have flipped basins historically.
10. **Verify, then trust**: never accept a delivery summary's interpretation — recompute from `metrics_eval.json` / traces; the *saved run* `config.yaml` (in `logs_rl/<run>/`) is the source of truth for what actually trained, not the ablation yaml.
11. **State behavioral requirements at the correct EVENT** (v19/v20 lesson, cloud-model credit): stage-label thresholds and release thresholds do not constrain physical geometry at other moments — the user wanted door-wide-*at-crossing*, and three rounds constrained door-angle-at-release/at-stage-flip instead. Before institutionalizing any target, ask: *at which physical event does the user's sentence apply, and does my constraint bind at that event?*
12. **A round's summary table must contain the round's own dependent variable** (v20 lesson): governance apparatus (locks/admissions/archives) is worth keeping, but it is not a substitute for measuring what the round set out to change. Reject any eval campaign whose aggregate omits the target metric.

## 5. TRAINING & EVAL CONVENTIONS

- **Launch**: `CUDA_VISIBLE_DEVICES=<GPUs> accelerate launch --multi_gpu --num_processes <N> --main_process_port <port> gr00t/rl/train_agent_trl.py +exp=wbmanip/door_open_a2_base_lstm +ablation=wbmanip/<name> project_name=a2_piper_full_stage_a2_base experiment_name=<name>`; ablation yamls in `gr00t/rl/config/ablation/wbmanip/`; global batch 4096 envs; save250; smoke 64 env × 50 iter before any formal run (check decomposition sanity, no NaN, new mechanisms alive).
- **Canonical eval**: `python gr00t/rl/eval_agent_trl.py checkpoint=<ckpt> +num_envs=16 +seed=0 +headless=true algo.config.eval.num_eval_episodes=16 +algo.config.eval.eval_num_envs_episodes=true '+env.config.a2_eval_door_handle_height_linspace=[0.80,1.10]' eval_output_dir=logs_eval/base_vN/<name>` — keys absent from `base_eval.yaml` need `+`; eval loads the checkpoint-adjacent training config and merges CLI on top. Endpoint = 3 seeds × 16 = 48 doors + bucket report (height/spring/mass); renders 2–3 env × 3 cams with QA contact sheets; midpoints mandatory **with behavior + decomposition audit**, not goal-only.
- **Artifacts**: evals co-located `logs_eval/base_vN/`; reporters per version `scriptsFORhuman/vN/`; strict trace topology validation; N/A (never 0%) for zero denominators.

## 6. CODE & CONFIG MAP (anchors move; grep the symbol, not the line)

- `gr00t/rl/envs/door/door_open_a2_base.py` (~12k lines): stage machine (`_stage_N_to_M_advance_condition`), grasp gate/streaks, release gate, corridor latch, all `a2_*` rewards, staging band. Stages: 0 walk / 1 pregrasp / 2 grasp / 3 open / 4 swing / 5 through; `award_remaining_time_on_advance` banks time (episodes ~450–700 steps @50 Hz, physics 200 Hz, decimation 4).
- `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`: door spawner truth (latch ON, tblr heights, spring/handle force ranges, mass via `a2_door_weight_range` hook); `gr00t/rl/isaac_utils/playground/env_rand/door.py`: door construction (hinge drive = closer spring, capped maxForce; latch mimic joint).
- `gr00t/rl/envs/base_task/a2_base.py`: 5-D base command semantics (NO height channel; pitch/roll ±0.4 via scale 0.4); `staged_task_base.py`: stage machine + staged reset (per-env snapshots, door tracked).
- `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml`: joint limits/efforts (fingers now 45 N; arm still superhuman ~100 — the force_feasible prerequisite lives here); reward registry `gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml` (register new terms at 0.0, enable in ablation).

## 7. DOCUMENT SOURCES & SEARCH METHODS

**Read order for a fresh session**: this handoff → `scriptsFORhuman/a2_piper_longterm_TODO.md` (living schedule + archived verdicts — sync it every round) → latest execution plan (`scriptsFORhuman/v20_R2/a2_piper_base_v20_R2_admission_and_execution_plan_20260730.md`) → repo `MEMORY.md` → `memory/a2-piper/MEMORY.md` routing (esp. `push-open-door-optimization`, `door-asset-randomization-baseline`, `phase2-student-distillation`) → `scriptsFORhuman/README.md` and the per-version plans under `scriptsFORhuman/vX/` (each has Findings + decision log) → `force_feasible/` for the thesis. Repo `AGENTS.md` governs memory-update etiquette (HKT timestamps, no origin-reference writes).

**Analysis recipes that keep paying off**:
- *Trace forensics*: load `stage2_5_step_trace.json`, filter `first_episode_active`, group by `env_id`, sort by `step_index`; per-env stage timelines, release detection (last `both_contact` frame), crossing state (first `root_pos_rel[0]>0`), body/arm-panel force channels, per-height stance (pitch/roll/yaw at first stage2 frame). Heights map env_id → linspace over the grid.
- *Decomposition*: grep `rew_<term>:` in the run's `.wandb/.../files/output.log` tail (training) or the eval reports — mind units (rule 2).
- *Config truth*: `logs_rl/<run>/config.yaml`; cross-check any claim about "what was trained" there first (caught two report/summary errors this way).
- *Counterfactual replay*: reconstruct alternative gates/metrics from existing traces before spending GPU (T4-style: predicted the debounced gate 16/16 before any run).
- *Diagnostics scripts*: `scriptsFORhuman/a2_piper_base_v13_diagnostics_20260716.py` (streak/gate reconstruction), `scriptsFORhuman/v18/a2_piper_v18_slip_report.py`, per-version bucket reporters.

## 8. CURRENT STATE & QUEUE (as of 2026-08-01)

- **Closed**: v20 Route-A dependent-variable readout scanned 70/70 checkpoints, 1120/1120 records/traces and 740,908 trace rows; no fallback eval was needed. G4 step2500 won under goal≥15/16 with hinge_at_crossing p50 `1.0160 rad` versus v19 `0.7869 rad` (`+0.2291 rad`, `PARTIAL_EFFECT`). Five winner episodes × three cameras produced 15 fully decoded MP4 files; the pre-crossing visual question was `YES_5_OF_5`.
- **Conditional institutional fallback**: not triggered, because v20 cells moved hinge_at_crossing into the pre-registered partial-effect band. The option remains recorded only for a future no-bind result.
- **Next**: realistic Piper **arm** limits round (creates the force_feasible boundary) → gate/base-assist mechanism (the thesis experiment) → pull doors (second regime) → left/right mirror, mass-impact axis, distillation per TODO tables B–D.
- **Open watch items**: v20 governance overhead vs measurement relevance (rule 12); strict-trace/null-telemetry exporter recurrences; posture usage observability-only (P2: functional); A-variant stage0 anomaly (v16).
- **Debts**: launcher natural-exit audit habit; per-round memory entries (worker sessions own them); keep `a2_piper_longterm_TODO.md` synced every round.

*The one-sentence brief for your successor: v20 closed the crossing-moment readout at `PARTIAL_EFFECT` (G4 step2500, hinge_at_crossing p50 `1.0160 rad`, render `YES_5_OF_5`); the next queued round is the realistic Piper arm-limit prerequisite for the force-feasibility experiment.*

## ADDENDUM (planner analysis, 2026-08-01) — why v20 stopped at 1.0 rad, and the rider for the next round

The SEND_METRICS attribution is unusually clean and carries one diagnosis the summary verdict does not state:

1. **Send curriculum is the single active ingredient.** G3 (send-only) +0.207; G2 (economics-only) +0.026 = inert; G4 (send+econ) +0.229 — economics adds ~0.02 on top; G5 arm-tie adds nothing (+0.187 < G3); G6/G7 replicate (seed delta −0.018). Unlike v17 (institution AND pricing both necessary), here the economics axis never bound because `target_root_distance` income was not the constraint the curriculum had to beat.
2. **Every send-bearing cell pins at hinge_at_crossing p50 ≈ 1.00–1.02, p95 ≤ 1.08 — a shared wall, not a tuning spread.** That is the signature of the corridor latch's `hinge ≥ 1.0` OR-branch: once the door reaches 1.0, corridor wages unlock *without crossing*, so 1.0 is the next pay boundary and the crossing moment migrated to it. **Threshold-hugging, 5th instance of the income-topology family** (v13 doorstop, v15 gate dead-zone, v16 unpaid push, v18 carry-above-ceiling, v20 latch-branch pin). The behavior obeys the pay landscape exactly; to move it, move the boundary.
3. **Rider for the arm-limit round** (recorded in TODO table A): unify θ_send — one config value driving the corridor-latch hinge branch, the send-curriculum target, and any crossing gate; set ≈1.25–1.30. Pre-registered prediction: crossing p50 chases θ_send up to the kinematic ceiling. Pre-registered risk: the 160 kg/11.5 N·m render case reached 1.0 pre-crossing but ended `stage_overtime` — **on the heavy tail the binding constraint is time, not force**; if overtime exceeds ~3/48 at θ_send=1.3, compensate with stage-time budget or post-crossing speed, not by lowering θ.
4. **Release-claim hygiene**: G4@2500 is the best policy on Route-A evidence only (goal 15/16). A formal release claim requires the never-run Route B (pooled48/holdout64) — recorded as a conditional debt, not a blocker for the next round.
