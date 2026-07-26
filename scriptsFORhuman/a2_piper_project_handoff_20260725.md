# A2+Piper Door-Opening RL — Project Handoff (EN)

Date: 2026-07-25 (HKT). Author: diagnosis/planning session (Claude), covering base_v12 → base_v19.
Audience: the successor session taking over diagnosis, planning, and work-session handoffs.
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
| **v19 (current)** | Plan delivered (`a2_piper_base_v19_optimization_plan_20260725.md`): P0 gates (ckpt1500 re-adjudication → warm-start; M22 mechanization; overspeed DOF diagnosis) + 7-group × 4096-env matrix testing carry with the cliff moved to 1.60. Await work-session results |

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

**Read order for a fresh session**: this handoff → `scriptsFORhuman/a2_piper_longterm_TODO.md` (living schedule + archived verdicts — sync it every round) → latest plan (`a2_piper_base_v19_optimization_plan_20260725.md`) → repo `MEMORY.md` → `memory/a2-piper/MEMORY.md` routing (esp. `push-open-door-optimization`, `door-asset-randomization-baseline`, `phase2-student-distillation`) → per-version plans `scriptsFORhuman/a2_piper_base_v1*..v19_*.md` (each has Findings + decision log) → `force_feasible/` for the thesis. Repo `AGENTS.md` governs memory-update etiquette (HKT timestamps, no origin-reference writes).

**Analysis recipes that keep paying off**:
- *Trace forensics*: load `stage2_5_step_trace.json`, filter `first_episode_active`, group by `env_id`, sort by `step_index`; per-env stage timelines, release detection (last `both_contact` frame), crossing state (first `root_pos_rel[0]>0`), body/arm-panel force channels, per-height stance (pitch/roll/yaw at first stage2 frame). Heights map env_id → linspace over the grid.
- *Decomposition*: grep `rew_<term>:` in the run's `.wandb/.../files/output.log` tail (training) or the eval reports — mind units (rule 2).
- *Config truth*: `logs_rl/<run>/config.yaml`; cross-check any claim about "what was trained" there first (caught two report/summary errors this way).
- *Counterfactual replay*: reconstruct alternative gates/metrics from existing traces before spending GPU (T4-style: predicted the debounced gate 16/16 before any run).
- *Diagnostics scripts*: `scriptsFORhuman/a2_piper_base_v13_diagnostics_20260716.py` (streak/gate reconstruction), `scriptsFORhuman/v18/a2_piper_v18_slip_report.py`, per-version bucket reporters.

## 8. CURRENT STATE & QUEUE

- **In flight**: v19 (plan delivered; P0.1 ckpt1500 re-adjudication decides the v18 verdict and the warm-start; 7-group matrix G1–G7; M43 overspeed fix variant pends the DOF diagnosis).
- **Next after v19**: realistic Piper **arm** limits round (creates the force_feasible boundary) → gate/base-assist mechanism (the thesis experiment) → pull doors (second regime) → left/right mirror, mass-impact axis, distillation per TODO tables B–D.
- **Open watch items**: A-variant stage0 null-standoff anomaly (v16), strict-trace null-telemetry exporter bug (recurred v17/v18 — M41/P0.2), j8 open-limit background ~11→0.04% after v18 gains (resolved, keep watching), posture usage now observability-only.
- **Debts**: launcher natural-exit audit habit; keep pushing memory entries per round (work sessions own them).

*The one-sentence brief for your successor: the robot already opens randomized latched doors 48/48 with a stable bilateral grasp and clean passage — everything from here is (a) making the remaining form ideal (arm-carry), and (b) building the honest physical regime in which the force-feasibility thesis can be demonstrated, without ever shaping the conclusion into existence.*
