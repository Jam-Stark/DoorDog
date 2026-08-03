# A2+Piper — Pull-Door (拉门 / `door_open_io="in"`) Worktree Cut & Round Scoping

**Document type:** planner analysis + change inventory (NOT an execution plan — no pre-registered thresholds, no admission DAG)
**Date:** 2026-08-03 HKT
**Author:** planner session (Claude), local worker host
**Repo / branch at time of writing:** `/home/baoquanc/workspace/DoorDog-A2_Piper`, `A2_Piper` @ `7ba69e5`
**Status of the push line at time of writing:** v21-B formal training **live on GPUs 0–6** (tmux `base_v21B_formal_v1`, 7 windows, started 2026-08-02 14:44). GPU7 measured idle (1018 MiB, 0%) but is declared FORBIDDEN by the v21-B plan.

**What this document is for.** The user is opening a parallel branch/worktree to develop the **pull-door** task while the push line (v21-B) finishes. This document answers three things: (1) what the pull task actually *is*, physically, in this codebase; (2) where to cut the branch from and why; (3) the complete inventory of what has to change, tiered by risk. It deliberately stops short of pre-registering thresholds — that is the job of the execution plan that follows, and per standing rule "no threshold without a measured basis" (v21-B §2) most of the numbers cannot be written until the P0 probes below have run.

---

## 0. TL;DR

1. **Do not rebase `codex/a2-piper-pull-door`.** It is based on `496ea4f` (2026-07-14, v10 era). Mainline has since moved 70 commits and `door_open_a2_base.py` went 12,047 → 22,427 lines (+15,270 / −2,447). Its 399-line env diff is not rebaseable in any useful sense. **Cut a fresh branch from `A2_Piper` HEAD, reuse the existing worktree directory, and port the old work as *design*, not as *code*.** Details in §4.
2. **Cut from `A2_Piper` HEAD (v21-B code), not from a v20 or v21 tag.** The code question and the checkpoint question are separable; HEAD is unambiguously the right code. Details in §5.
3. **Do not assume a warm start.** Push and pull are near-inverted in the manipulation phase. Decide warm-start-vs-scratch from a *zero-shot probe of the frozen push policy in the mirrored pull env* — the project's own rules 5 and 9. Details in §5.2 and §8.
4. **Pull is a new task, not a randomization switch, and its hard part is not "open the door wide".** It is *hold the door open against the closer while relocating the base backwards and around the swing arc, and transit the aperture without being struck by the panel*. §2–3.
5. **The force-transmission regime genuinely changes: form closure → friction.** This is the second feasibility regime the thesis has been waiting for (`force_feasible/`, handoff §2, TODO table C item 4), and — importantly — **it costs no new physics work**: the `spawn_hook` factor (p=0.5) and the existing 2.5–12 N·m closer-spring range already span it. §3.2.
6. **Most of the required telemetry already exists.** In particular `orthogonal_arc_residual_m` (`door_open_a2_base.py:1629`) is exactly the pull-off / handle-escape metric, and `spawnHook` / `axleLength` / `handleLength` / `hookLength` are already in door metadata (`door.py:955-976`). §7 Tier F.
7. **The single biggest open design question** is the stage-4/5 base trajectory: today `target_root_distance` pulls the robot toward one fixed point (`[2.0, 0, 0.5]`). Mirrored naively to `[-2.0, 0, 0.5]`, it drives the robot straight into the swinging panel. §7 Tier C3 and §9-R1.

---

## 1. Project background, compressed (what a pull round must not break)

### 1.1 The north star, restated

From `a2_piper_project_handoff_20260725.md` §1. The push task's ideal episode is: approach to a *self-chosen* standoff inside the staging band → lean/pitch-up to raise the arm mount (load-bearing, not waste — P2 probe) → bilateral debounced grasp (K=5 control-step streak) → unlatch via handle rotation → **the arm opens the door through the handle** → push wide and cross **while still holding** → release past the pay ceiling → walk through with zero body/leg-door collision.

The clause that matters most here: **"deliberate body-push is a defect — today"** (handoff §1 item 8). The arm is simulation-superhuman (~100 N·m class), so no real feasibility boundary exists on the push side; body assist would be the policy cheating, not the policy adapting. Whether that clause survives contact with pull is discussed in §3.4 — it may be the first place where body/leg involvement is *legitimate*, and the round should be designed so that this is measurable rather than assumed either way.

### 1.2 The research thesis this round serves

`scriptsFORhuman/force_feasible/`, compressed in handoff §2:

> Among all whole-body configurations that achieve the required force interaction, prefer the one that is **most arm-feasible** (torque margin, away from saturation/limits/singularity) with **minimal base intervention**: `u_base = u_user + gate(s)·u_assist`, gate opens only when the arm is genuinely infeasible.

The blocker has always been that **no feasibility boundary exists in the current sim**. Two routes to create one:

- **Route 1 (in progress, v21-B):** shrink the *arm* effort limits from ~100 N·m to a census-selected realistic value, creating an arm-torque boundary on the heavy door tail.
- **Route 2 (this round):** switch to pull, where transmission through the handle is **friction-limited at the fingers** (45 N nominal, μ 1.1/0.9 since v18) rather than form-closure-limited. TODO table C item 4 names this explicitly: *"拉门(in/out)新任务：摩擦/钩传力、手指 effort 硬上限 → 天然 finger-limited regime，force-feasible 的第二实验场"*.

These are **complementary, not competing** — a policy that must be arm-feasible *and* finger-feasible is a much stronger instantiation of the thesis than either alone. Running them on separate branches in parallel is the right structure.

### 1.3 The standing design rules that will bite this round

All 12 are in handoff §4; the ones with teeth here:

| Rule | Why it bites pull |
|---|---|
| **1. Income-cliff** | Any pull-specific behavior spanning a stage boundary (e.g. "keep holding while the base retreats and re-approaches") must be paid on **both** sides of the boundary. The v21-B analysis found this family is now at **6 instances**. Pull adds several new boundaries at once — this is the highest-probability way for the round to fail. |
| **2. Calibrate by measured decomposition** | `penalty_door_panel_contact` is `-0.1` today because panel contact was rare in push. In pull it becomes the dominant safety event. Do not guess a new scale; measure the decomposition first. Label units (`/20s` vs episode-sum). |
| **3. Capability-first** | Before any reward tuning: can the Piper gripper hold a 12 N·m-closer handle in **friction** while the base translates? If not, no shaping helps. This must be probed, not assumed. |
| **4. Mechanism over reward-carving** | The self-closing spring **already makes** hold-through-crossing necessary in pull (release → door shuts → no aperture). Do not pay for it with a reward term first; check whether the physics already enforces it. |
| **5. Policy-as-probe** | Any scripted pull-feasibility probe must use only *commandable* DOFs and must pass a known-good anchor before its verdicts count. M18 and the 37-revision scripted probe both failed this. |
| **8. Factorial + replicate** | One axis per cell, always a replicate. Basin lottery is real (3/4 historical scratch runs landed in wrong basins) — and a from-scratch pull round is exactly the regime where that statistic was measured. |
| **9. Zero-shot probe before actuator changes** | Extended here to *geometry/direction* changes: probe the frozen push policy in the mirrored env before committing to a warm-start strategy. |
| **11. State requirements at the correct EVENT** | The v19/v20 lesson cost three rounds. For pull the events are different from push (§2.2) — write the requirement at the pull event, not at the push event with a sign flipped. |
| **12. The round's summary must contain the round's own DV** | Pick pull's DVs deliberately (§8.4); do not inherit v20's `hinge_at_crossing` unexamined. |

### 1.4 State of the push line (what the pull branch inherits)

- **v20 closed** `PARTIAL_EFFECT`: winner G4 step2500, `hinge_at_crossing` p50/p95 = 1.0160/1.0628 rad, render `YES_5_OF_5`. **Route A evidence only** — Route B (pooled48/holdout64) has *never run in project history*.
- **v21** (cloud-authored) = θ_send dose ladder 0.90→1.30, arm limits out of scope.
- **v21-B** (local, sibling variant, currently training) = 2×2 θ × arm-limit ablation, θ capped at 1.20 on measured reachability, arm effort census-selected, six acceptance thresholds re-cut against measurement. Its P0 work is directly reusable: the freeze-guard extension pattern (`_validate_a2_v20_r1_config`, `door_open_a2_base.py:5527`), the PD-effort-estimate telemetry with `ESTIMATE_ONLY` provenance (`:19331-19438`), the census→selection→zero-shot→pilot→freeze admission chain, and the anti-block doctrine (§2 of the v21-B plan).

**Recommendation: adopt v21-B's anti-block doctrine verbatim for the pull round.** A brand-new task is precisely where over-strict pre-registered thresholds (written without a measured basis) will block the round for reasons unrelated to the science.

---

## 2. What the pull task actually is, in this codebase

### 2.1 Verified geometry (all facts below re-derived from source at `A2_Piper` @ `7ba69e5`)

**Direction encoding** — `gr00t/rl/isaac_utils/playground/env_rand/door.py:203-229`:

```
door_open_lr: "left" → +1,  "right" → -1
door_open_io: "in"   → +1,  "out"   → -1
```

**Current training distribution** — `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py:583-584`: `door_open_lr=["right"]`, `door_open_io=["out"]`. Also `add_floors=True`, **`add_walls` defaults False** (`door.py:70`) — the door is a free-standing frame with a jamb but no surrounding wall.

**`door_open_io` is inert.** Grep at HEAD across `door.py` and `door_open_a2_base.py`: it is sampled (`door.py:215-225`), written to metadata (`:963`), read back for deterministic replay (`:1109`) — and **used nowhere in geometry, joints, limits, spawn yaw, or reward routing**. In the env, `self.door_open_io` is allocated as zeros (`door_open_a2_base.py:6132`, `:6258`), **never assigned from metadata**, and fed to the privileged obs stack (`:21318`) as a constant-zero channel. The 2026-07-03 memory `door-asset-openio-sign` still holds exactly at HEAD.

**Hinge & panel swing** — `door.py:487-497`: axis `Z`, limits `[0, 150]`, drive target `-10.0` (the closer spring), `LocalPos0 = (0.02, -half_width·lr, 0)`. For right doors (`lr = -1`): hinge sits at **+Y**, handle prim at **−Y** (`:375-380`), and the effective hinge axis is **+Z** (independently confirmed by the v20 arc probe, `door_open_a2_base.py:785-787`: `axis_w = (-lr)·R·ẑ`). Rotating the handle-end offset `(0, -W, 0)` by `+θ` about `+Z` gives `(+W·sinθ, -W·cosθ)` — **the panel swings toward +X**.

So: robot spawns at **−X** (`_reset_root_states`, `:21597-21600`: `x ∈ [-1.5, -0.6]`), the door swings **away** from it (+X), and it walks through toward **+X**. That is **push**.

**Handle is double-sided; the grasp target is not.** `door.py:383-426`: an axle of length `∈ [0.18, 0.21]` m passes through the panel (panel half-thickness 0.02 m), with a lever capsule on each face — `handle_inside` at `X = -axle/2` and `handle_outside` at `X = +axle/2`. But `grasp_target` (`:592-609`) is authored at `X = -axle/2` only — **co-located with `handle_inside`, i.e. on the push-approach face**. `A2_PREGRASP_OFFSET = (-0.10, 0.0, 0.0)` (`door_open_a2_base.py:4971`) then stands the gripper 10 cm further along −X.

**Hooks.** `door.py:428-459`: `spawn_hook` fires with p = 0.5 (`rand_spawn_hook` is unset in the scenario cfg). When present, a cylinder at each face bends from the lever tip back toward the panel, forming an "L". Recorded in metadata as `spawnHook` (`:968`).

### 2.2 Therefore: what "pull" must mean here

Because the door asset's swing direction is fixed and `door_open_io` does not (and per memory, should not) flip the hinge, **pull is implemented by putting the robot on the +X side** — the side the panel swings *into*:

```
              PUSH (today)                      PULL (this round)
robot spawn:  x ∈ [-1.5, -0.6], yaw ≈ 0        x ∈ [+0.6, +1.5], yaw ≈ π
grasp face:   handle_inside  (X = -axle/2)      handle_outside (X = +axle/2)
pregrasp:     (-0.10, 0, 0)                     (+0.10, 0, 0)
door swings:  +X, AWAY from robot               +X, TOWARD robot
through dir:  +X                                −X
success:      root_x > +1.5                     root_x < −1.5
```

This is the route the 2026-07-03 memory `door-asset-randomization-baseline` recommends ("用 `doorOpenIO` 作为 semantic label，显式 mirror robot approach side、yaw、stage0 target、through target/success direction 与 diagnostics；不要 hidden mirror"), and it is what the 2026-07-14 branch implemented. **It is correct, and it requires no change to the hinge, the latch, or the joint signs.** Hinge-positive still means "opening" for both directions — do not flip it.

**The events change, not just the signs.** Rule 11 says state the requirement at the physical event where it applies. Pull's events are:

| | push | pull |
|---|---|---|
| E1 | door reaches θ_send while held | same (but θ must be re-derived; §7 Tier E2) |
| E2 | — | **base clears the panel's swept arc** ← new, has no push analogue |
| E3 | root crosses door plane toward +X | root crosses door plane toward −X, *after* E2 |
| E4 | release (door coasts open behind robot) | release — **and the closer immediately starts shutting the door** |
| E5 | goal at `root_x > +1.5` | goal at `root_x < −1.5` |

E2 is genuinely new and E4 changes character completely. A mechanical sign flip of the v20/v21 institution gets E1/E3/E5 right and **silently drops E2 and misprices E4**. That is the rule-11 trap for this round.

---

## 3. Why pull is hard — the four things that actually differ

### 3.1 The base trajectory becomes non-monotonic

In push the base can march monotonically forward: approach → stand → grasp → shove → walk through. Every phase has `vx ≥ 0`.

In pull the base must **reverse while holding**, because the panel sweeps into the space the robot is standing in; then **translate laterally** around the swing arc; then **advance** through the aperture in the *opposite* world direction from the reverse. `vx` changes sign at least twice while a bilateral grip is maintained.

Consequences:
- The arm's workspace demand goes up sharply — the gripper must stay on a handle that is itself travelling along an arc of radius ≈ door width, while the base is doing something different. In push, base and handle move roughly together.
- `penalty_not_standing_still` (stage1, −15.0), `penalty_standing_still` (stage4, −1.0) and `penalty_a2_stage1_stage2_base_forward_creep` (−1.5) encode push-shaped assumptions about when motion is good.
- **This is the most likely place the Piper genuinely runs out of reach** — which is scientifically *useful* (it is a kinematic feasibility boundary, the sibling of v21-B's torque boundary), but only if it is measured rather than tuned away.

### 3.2 Force transmission: form closure → friction (the thesis payload)

**Push:** the gripper wraps the lever bar and presses it toward the panel. The bar cannot escape — it is backed by the panel. This is **form closure**; grip force barely matters, which is exactly why v15 found 12 N·m springs and 160 kg panels never saturated the arm, and why the spring/mass axis was declared dead (handoff §2).

**Pull:** the gripper wraps `handle_outside` and pulls in **+X**, *away* from the panel. Nothing backs the bar. Transmission is:
- **friction** on a cylinder of radius `handle_radius`, at 45 N nominal finger effort with μ 1.1 / 0.9 (v18); plus
- **hook geometry** when `spawn_hook` is true — and note the hook bends from the lever tip *back toward the panel* (`door.py:446-459`, `hook_outside` at `X = +axle/2 - hook_length/2`), i.e. it resists the gripper sliding off the bar **end** in Y, and only incidentally helps in X.

So pull is **finger-limited**, and the resistance it must overcome is the closer spring (2.5–12 N·m) plus panel inertia (80–160 kg) — both **already randomized**. The round therefore gets a real feasibility landscape for free:

```
free 2×N factorial:  spawn_hook {true, false}  ×  hinge_drive_max_force ∈ [2.5, 12.0]
                     (p = 0.5, already sampled)    (already sampled, already bucketed)
```

**This is the single strongest argument for doing the pull round now.** It delivers the thesis's second regime without any new physics, new asset, or new actuator work — the opposite of v21-B, which had to manufacture its boundary by shrinking effort limits.

Caveat to flag honestly: friction in PhysX with capsule-on-capsule contact at these scales is not a high-fidelity model of a real gripper on a real lever. The claim the round may make is *"in this simulator, transmission is friction-limited and the policy's success is a measurable function of hook presence and closer force"* — not *"we validated real hardware pull feasibility."* Same discipline as v21-B's `ESTIMATE_ONLY` torque provenance.

### 3.3 The closer spring makes hold-through-crossing mandatory, not merely desirable

In push, `release → the door coasts open` — v19 even found the policy exploiting this ("shove-then-coast", and later "base-drag"). The whole v17/v19/v20 apparatus exists to *force* the robot to keep holding when it would rather let go.

In pull, `release → the closer (target −10°, max force 2.5–12 N·m, stiffness 1–10) shuts the door`. **The institution the push line spent four rounds constructing is enforced by the physics for free.** This is standing rule 4 (mechanism over reward-carving) handed to us on a plate: before adding any hold-through-crossing reward, check whether the closer already makes it necessary.

The corollary is a new failure mode with no push analogue: **the door closing onto the robot mid-transit**. Which leads to:

### 3.4 Body/panel contact goes from rare to central — and body assist may become legitimate

Today `penalty_door_panel_contact = -0.1` and `penalty_a2_door_body_contact = 0.0`; v15 measured **0/10066 pre-crossing body contacts** at 12 N·m in push. In pull the panel actively travels toward the robot, so contact is the expected default, not a rarity.

Two consequences:
1. Those scales are calibrated for a regime that no longer exists. Rule 2 applies — re-derive them from a measured decomposition, do not guess.
2. **Handoff §1 item 8 ("deliberate body-push is a defect — today") may need a pull-specific reading.** In pull, bracing the door with a paw or the trunk while re-gripping, or blocking the aperture with a leg before releasing, is *how humans do it* and may be genuinely necessary rather than cheating. The round should therefore **measure body/panel involvement as a dependent variable, not ban it a priori** — and should keep the ban only for the phases where it is still clearly a defect (rule 7: scope red-lines to the phase they protect). This is also the first realistic chance to observe the `gate(s)·u_assist` behavior the thesis predicts, *emergently*, before anyone implements a gate.

**This should be an explicit decision by the user/planner before implementation, not a worker judgement call.** See §10-Q1.

---

## 4. The existing `codex/a2-piper-pull-door` branch: keep the design, discard the code

**Measured drift** (from the pull worktree):

| | value |
|---|---|
| pull branch base | `496ea4f`, 2026-07-14 (v10 era) |
| commits on `A2_Piper` since that base | **70** |
| `door_open_a2_base.py` at base / at HEAD | 12,047 → **22,427** lines |
| mainline diff on that one file since base | **+15,270 / −2,447** |
| the pull commit's own diff on that file | +399 |

A 399-line diff against a file that has since been two-thirds rewritten is not rebaseable in any meaningful sense; conflict resolution would be strictly more work than re-deriving, and would carry a high risk of silently reinstating v10-era semantics into a v21-B-era env (exactly the class of defect standing rule 10 exists to catch).

**Recommendation:**

1. Keep the directory `/home/baoquanc/workspace/DoorDog-A2_Piper_pull` — no need to burn disk on a new checkout.
2. Tag the old branch for reference (e.g. `archive/pull-door-v10-static-2026-07-14`) so the design survives, then create a **fresh branch off `A2_Piper` HEAD** in that worktree.
3. **Port as design, not as patch.** What is worth carrying over from `f624169`:
   - the **direction contract** itself (it is correct — §2.2 above independently re-derives the same mapping);
   - the **separate-namespace decision**: task `door_pull`, env `door_pull_a2_base`, exp `door_pull_a2_base_lstm`, project `a2_piper_pull_door_a2_base`, and `gr00t/rl/data/tasks/door_pull/scenario_cfg/`. This is the right call and matches the `log-layout` memory contract — pull artifacts must never mix with push artifacts;
   - the **`a2_door_direction.py` helper-module shape** (295 lines): a single place where `approach_sign` / `through_sign` live, rather than sign flips scattered across a 22k-line env. Re-derive its contents; keep its role.
   - the **`test_a2_pull_direction_contract.py` structure** (290 lines): a targeted contract test is exactly right, and matches v21-B's P0 test discipline.
   - the memory entry `memory/a2-piper/pull-open-door-task/` — **re-create it fresh**, and preserve its most valuable property: it is scrupulously explicit that `NO_SIM PASS` ≠ runtime PASS. Everything in that branch is static evidence; none of it has ever been in a simulator.
4. **Discard entirely:** the `door_open_a2_base.py` hunks, the `scenario_cfg/factory.py` refactor (mainline's `scenario_cfg/isaacsim.py` has since grown the whole v21-B manifest/digest machinery — a v10-era factory split would fight it), and the old `door_open_a2_base.yaml` edits.

One caveat worth stating plainly: the old branch's stage-4 design ("root-distance reward keeps an approach-side clearance target; stage5 activates on a clearance predicate") is the *only* prior attempt at the §3.1 problem, and it was never simulated. Treat it as a hypothesis to test, not a solution to port.

---

## 5. Where to cut from: v20, v21, or HEAD

Two questions that are usually conflated. Separate them.

### 5.1 Which **code** to branch from → `A2_Piper` HEAD, unambiguously

Not v20, not the v21 plan commit. HEAD carries:

- the **send-curriculum / corridor-latch mechanism** in `send_ready_v20` mode (`door_open_a2_base.py:672-760`) — pull will need a sign-aware analogue, and re-deriving it from the v20 tag would mean re-doing v21-B's corrections;
- the **freeze-guard extension pattern** (`_validate_a2_v20_r1_config`, `:5527`; v21-B P0-G) — the pull plan will need its own plan-id branch in exactly the same shape;
- **PD-effort-estimate telemetry with `ESTIMATE_ONLY` provenance** (`a2_hold_pd_effort_estimates`, `:19331-19438`) — for pull this gets pointed at the **fingers** rather than `arm_j1..j6`, which is a smaller change than writing it from scratch;
- the **arm-profile plumbing** (`dof_effort_limit_list` as a 20-entry per-ablation block, v21-B P0-A) — note the trap it documents: the repo robot yaml says fingers `10.0/10.0` (`config/robot/A2_Piper/a2_piper.yaml:83`) but the **resolved** config carries `45.0/45.0`. A worker editing the robot yaml changes nothing. This matters more for pull than for push, because fingers are the binding constraint;
- the strict-trace / record-set / evidence apparatus and the `scriptsFORhuman/v21B/` runner suite, which the pull round can fork rather than reinvent.

Cost of branching from HEAD: you inherit v21-B's in-flight state (its ablation yamls, manifests, locks). That is cosmetic — the pull round uses its own namespace anyway.

### 5.2 Which **checkpoint** to warm-start from → decide by probe, not by argument

Candidates: **v20 G4 step2500** (`logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G4-20260731_004712/model_step_002500.pt`, sha256 `f000f13e…a806d`, hash-verified on this host 2026-08-02) — the only hash-verified, render-QA'd policy the project has; or a **v21-B winner**, unknown until that round closes.

**The case against warm-starting from either:** the push policy's manipulation-phase prior is close to *inverted*. It has learned to drive `vx > 0` while holding the handle, to lean into the door, and to treat "door moving away" as progress. In pull, all three are wrong, and two of them are actively dangerous (driving forward while holding pulls the robot into the closing panel). Warm-starting into a contradictory task can be worse than scratch — the policy must first *unlearn*, and the basin it starts in is the wrong one by construction.

**The case for:** stages 0–3 are substantially direction-agnostic once the staging band is mirrored — locomotion, the bilateral debounced grasp (K=5), the squeeze force window, handle approach in `xz`, the unlatch sequence. That machinery took v13–v18 to get right and is expensive to relearn. And standing rule 8 records that **3 of 4 historical from-scratch runs landed in the wrong basin** — scratch is not the safe option either.

**Recommendation — resolve it empirically, cheaply, before committing (this is standing rules 5 and 9 applied to a geometry change rather than an actuator change):**

> **P0-Z(pull): zero-shot the frozen v20 G4 step2500 in the mirrored pull env.** No optimizer updates. Canonical16 + a hook/no-hook × spring-low/high manifest. Read out: max stage reached per episode, terminal-reason histogram, whether the staging band is entered at all, whether bilateral grasp is achieved, `orthogonal_arc_residual_m` at first pull attempt, panel-contact events.

This probe pays for itself three times over:
1. It is the **implementation-correctness test for the mirror**. If `approach_sign` is wrong anywhere, the policy will fail in a *diagnosable, localized* way (never enters the band; never faces the door; pregrasp on the wrong face) long before any training GPU is spent.
2. It answers warm-start-vs-scratch with evidence. Rough reading: reaches **stage 2–3 routinely** → warm-start is viable and stages 0–3 transfer; **stalls at stage 0–1** → the mirror is buggy or the transfer is nil, and scratch (or a staged/frozen-lower-body warm start) is indicated.
3. It is the **capability-first probe** (rule 3) for §3.2 — it directly shows whether the gripper can hold at all when the load reverses.

It also fits the GPU situation: it is an *eval*, not a training run, so it can be run on a single GPU in gaps, or immediately once v21-B releases 0–6.

### 5.3 A third option worth considering: don't warm-start the policy, warm-start the *curriculum*

Rather than choosing between one push checkpoint and scratch, a **staged distribution curriculum** may dominate both, and it is what standing rule 3 (capability-first) actually implies:

```
Stage I   hook = ALWAYS TRUE, spring ∈ [2.5, 5], height mid-band, mass low
          → the easiest possible pull. Establish that the behavior is learnable at all.
Stage II  open the hook axis   (hook ∈ {true, false})
Stage III open the spring/mass axes to the full push-line ranges
```

The v8–v12 stalemate ("moves door XOR holds handle", 2×2 factorial uninterpretable, basin lottery) is precisely what happens when a hard new behavior is attacked at full randomization. v13 broke it by finding the capability blocker first. A new task at full randomization risks repeating v8–v12 — and unlike then, the project now knows better.

Note this is a **pre-registered curriculum, not a permanent narrowing** — say so in the plan, so the round is not later mistaken for a scoped-down result.

---

## 6. My overall recommendation on the cut

**Cut it, now, in parallel with v21-B — with the round scoped as capability-establishment, not as a release round.**

Reasons:

1. **It is the right kind of parallelism.** v21-B occupies all 7 legal GPUs but occupies *zero* implementation bandwidth — its code is frozen and it is just burning batches. The pull round's next ~1–2 weeks are almost entirely implementation, static tests, GUI verification, and a small zero-shot eval. The two lines barely contend.
2. **It de-risks the thesis by not putting it all on the arm-limit route.** If v21-B returns `BOUNDARY_ABSENT` or `BOUNDARY_ESTIMATE_ONLY_UNCORROBORATED` (both are live outcomes in its fork table), the thesis needs a second regime — and pull is it. Starting it only *after* v21-B closes serializes two multi-week rounds for no reason.
3. **The free factorial (§3.2) is unusually cheap science.** Hook presence and closer force are already sampled. No asset regeneration is needed: doors are spawned **procedurally at runtime** via `spawn_door` inside `MultiAssetSpawnerCfg` (`scenario_cfg/isaacsim.py:567-600`), so a `door.py` edit takes effect immediately.
4. **The prior branch's existence is a net asset** once its code is discarded: the direction contract has already been derived once, independently, and this document's re-derivation agrees with it.

**Where I would push back on an over-ambitious scope:**

- **Do not aim for a release-grade pull policy in round 1.** The push line took v8→v20 to reach a Route-A-only release claim. A pull round that declares `RESEARCH_PASS_NO_RELEASE` with a clean feasibility landscape is a *success*.
- **Do not do mixed push+pull randomization yet.** Mixed doubles the plumbing (per-env `approach_sign`, sign-dependent obs, `doorOpenIO` into obs as a *live* channel rather than the constant zero it is today) and destroys attribution — you would not know whether a failure is a pull failure or a mixing failure. Pull-only first; mixed is a later round once pull alone is solved. (Note the pleasant consequence: for pull-only, every sign is a **constant**, not a per-env tensor. That is a dramatically smaller and safer diff.)
- **Do not enable `push_door_force`.** It is 0.0 today and the `door-asset-openio-sign` memory is explicit that if it is ever enabled it must use a door-frame/source-frame projection, never world-x.
- **Do not flip the hinge sign.** Positive hinge = opening, for both directions. Both memory entries say this; §2.1 re-confirms it.
- **Do not touch the push line's files.** Namespace isolation from day one (§4 item 3).

---

## 7. Change inventory

Tiered by risk. Line numbers are anchors at `7ba69e5` — **grep the symbol, not the line** (handoff §6).

### Tier A — asset & scenario (LOW risk, but must be first)

| # | Site | Change |
|---|---|---|
| A1 | `data/tasks/door_pull/scenario_cfg/isaacsim.py` (new) | New package; `door_open_io=["in"]`, `door_open_lr=["right"]` initially. Do **not** fork the v21-B manifest/digest machinery — import it if needed. |
| A2 | `env_rand/door.py:592-600` — `grasp_target` prim at `X = -axle/2` | Must sit on the **pull face** (`+axle/2`, co-located with `handle_outside`). Three options: **(a)** make the X sign a function of `door_open_io` (cleanest for pull-only — one prim, one sign, no env change downstream, since the whole grasp pipeline just reads `grasp_target`); **(b)** add a second `grasp_target_pull` prim (needed later for mixed); **(c)** keep the prim and add a fixed FrameTransformer offset of `+axle_length` — **reject**: `axle_length` is per-door randomized over `[0.18, 0.21]` (`:272-273`), so a constant offset carries ±1.5 cm error against a handle of radius ~2 cm. Recommend (a). |
| A3 | `door_open_a2_base.py:6131-6143`, `:6257-6269` — metadata read | Add `doorOpenIO` → `self.door_open_io` (today allocated zeros and fed to privileged obs at `:21318` as a constant-zero channel — a latent bug the pull round should fix regardless). Also read `spawnHook`, and `axleLength` if option (b)/(c) is chosen. All are already in metadata (`door.py:955-976`). |
| A4 | `door.py:1101-1129` — `get_deterministic_door_config` | Already round-trips `doorOpenIO` (`:1109`). Verify the replay path still reproduces byte-identical doors once A2 lands. |

### Tier B — robot spawn & staging geometry (MEDIUM risk — this is where a silent sign error hides)

| # | Site | Change |
|---|---|---|
| B1 | `door_open_a2_base.py:21589-21610` — `_reset_root_states` | `x ∈ [-1.5, -0.6]` → `[+0.6, +1.5]`; yaw `∈ [-π/4, +π/4]` → `π ± π/4`. Watch the yaw wrap: `quat_from_euler_xyz` with a raw `π + δ` is fine, but every downstream consumer of yaw error must `wrap_to_pi`. |
| B2 | `:2617-2633` `a2_stage0_staging_band_mask`; `:2636-2662` `a2_stage0_nearest_staging_target` | Both compute `dx = grasp_target.x - root.x` and require `dx ∈ [x_min, x_max]` with **both bounds positive**. Signed: `dx = approach_sign · (grasp_target.x - root.x)`. Keep the band's *shape* (self-chosen standoff, handoff §1 item 1) — only the sign moves. |
| B3 | `:4971` `A2_PREGRASP_OFFSET = (-0.10, 0, 0)` and `:22210-22235` FrameTransformer `handle`/`pregrasp` frames | Offset → `(+0.10, 0, 0)`. The frames' `rot=(0.5, 0.5, 0.5, 0.5)` encodes the gripper's approach orientation and **must be re-derived, not guessed** — the 2026-07-14 branch used `(0.5, 0.5, -0.5, -0.5)`, which is plausible but was never simulated. **Verify in the Isaac Sim GUI** per the `static-visual-alignment` memory before any training. |
| B4 | `:11393-11401` `_reward_penalty_face_door` | Penalizes `‖axis_angle(relative_door_rot_buf)‖`, i.e. desired relative rotation = identity. For pull the desired heading is door-yaw + π, so this term is **maximal at the correct pose** — it would actively fight the task. Needs a desired-heading offset. The code comment at `:11395-11397` already anticipates exactly this ("Future option: … add a desired heading offset if A2 needs a non-square stance"). |
| B5 | `:11423-11445` `_reward_penalty_a2_stage1_stage2_base_forward_creep` | `stage0_near_boundary_x = grasp_target.x - x_min`, penalty ramps as `root_x` exceeds it. Sign flip, via the same `approach_sign`. |
| B6 | (new) `envs/door/a2_pull_direction.py` | One module owning `approach_sign` / `through_sign` and the signed helpers, so no bare `±X` literal survives anywhere else. Port this *role* from the old branch's `a2_door_direction.py`. Pair with a contract test that greps for un-signed `root_x` comparisons. |

### Tier C — stage machine & success (MEDIUM risk; C3 is the round's real design problem)

| # | Site | Change |
|---|---|---|
| C1 | `:22100-22114` `_stage_4_to_5_advance_condition` | `walked_through_door = (root_x - origin_x) > 0.0` → `through_sign · (root_x - origin_x) > 0.0`. `handle_up` (`joint_pos[:,1] < 0.2`) and the hinge threshold are direction-agnostic — keep. |
| C2 | `:22118` `_stage_5_to_complete_condition` | `> 1.5` → `through_sign · (…) > 1.5`. |
| C3 | `config/env/door_open_a2_base.yaml:224` `target_root_pos: [2.0, 0.0, 0.5]`, consumed by `_reward_target_root_distance` (`:11209-11225`, scale **12.0** — the largest single stage-4 term) | **The naive mirror `[-2.0, 0, 0.5]` is wrong and dangerous**: it is a straight-line attractor from `+X` to `−X` *through the region the panel is sweeping*. With scale 12.0 it will dominate, and the policy will learn to walk into the door. This needs a **swing-arc-aware structure** — a waypoint lateral of the arc, or a clearance predicate gating the through-target, or a target that tracks the aperture rather than a fixed point. The 2026-07-14 branch proposed a clearance predicate (never simulated). **This is the one item that deserves genuine design debate, and it is exactly where the income-cliff rule will bite** — whatever structure is chosen must pay income on both sides of every boundary it introduces. |
| C4 | `:9329`, `:9349` stage advance callbacks; `award_remaining_time_on_advance` | Pull episodes are longer by construction (retreat + arc + transit vs. a straight walk-through). Check the 20 s `max_episode_length_s` budget and the stage-time budget against measured pull durations **before** training, not after — v21-B's `stage_overtime` experience says time is the sneaky binding constraint. |

### Tier D — rewards (MEDIUM; do not tune before measuring)

| # | Term (scale) | Note |
|---|---|---|
| D1 | `walk_to_door` (5.0) | Follows the staging band; fixed automatically by B2. |
| D2 | `push_door_handle` (6.0), `push_door_hinge` (6.0) | Pure joint progress; direction-agnostic. **Keep unchanged.** Confirmed by `door-asset-openio-sign` memory and re-verified here. |
| D3 | `push_door_force` (0.0) | **Leave at 0.0.** If ever enabled: door-frame/source-frame projection only, never world-x. |
| D4 | `dont_push_door_handle` (3.0, stage4) | Semantics need review: in pull, releasing the handle lets the closer shut the door, so "don't push the handle" and "must keep holding" interact differently than in push. |
| D5 | `penalty_door_panel_contact` (−0.1), `penalty_door_frame_contact` (−1.0), `penalty_a2_door_body_contact` (0.0) | Calibrated for a regime where panel contact was ~0 (v15: 0/10066). In pull the panel comes to the robot. **Re-derive from a measured decomposition (rule 2); target 5–15% of income when engaged. Do not guess.** And see §10-Q1 — some body/panel contact may be legitimate in pull. |
| D6 | `penalty_not_standing_still` (−15.0, stage1), `penalty_standing_still` (−1.0, stage4) | Encode push-shaped assumptions about when motion is good. Re-examine against the pull phase structure. |
| D7 | `a2_corridor_door_wide`, `a2_corridor_clean_passage`, `penalty_a2_v20_pre_send_crossing`, `a2_v20_arm_tangent_carry`, `a2_v20_handle_arc_tracking` (all 0.0 in the registry, enabled per-ablation) | All keyed on `root_x`/crossing. Sign work **plus semantic re-derivation** — see Tier E. |
| D8 | new terms | Register at **0.0** in `config/rewards/wbmanip/reward_door_open_a2_base.yaml` (or a pull-specific registry) and enable per-ablation — the repo convention (handoff §6). **But first check whether the closer spring already makes the behavior necessary (rule 4).** |

### Tier E — the v20/v21 institution (HIGH risk — sign work is easy, semantics are not)

| # | Site | Change |
|---|---|---|
| E1 | `:684` `a2_v20_root_crossing_event` (`opening_phase & ~send_ready & (root_x_rel > margin)`); `:2137` `root_crossing_candidate = update_mask & (root_x > 0.0)`; `:752` corridor latch (`send_ready` vs legacy `root_x_ever_crossed \| (stage ≥ SWING & hinge ≥ 1.0)`) | All signed. Mechanical — but there are several, and missing one produces a *silent* mispricing rather than a crash. Cover with contract tests. |
| E2 | θ_send / send curriculum | The **semantics** change. In push, "crossing before the door is wide" = bulldozing. In pull, the robot is on the swing side: the real pre-crossing hazards are *getting struck* and *releasing early*. θ_send must be re-derived from a **pull-side reachability census** — reuse v21-B §1.2's method exactly (fraction of episodes whose door ever reaches θ while bilaterally held, from a mature checkpoint pool), which is the measurement that stopped v21-B from repeating the income-cliff failure a sixth time. |
| E3 | `:5527` `_validate_a2_v20_r1_config`, invoked from `_init_a2_door_pregrasp_state` (`:6175`) at env construction on **both** the training and eval paths | Currently hard-pins `plan_id`, `theta_send == 0.90`, tolerance 0.05, margin 0.03. v21-B P0-G added a plan-id-keyed branch; the pull round needs its own, in the same shape, leaving the v20/v21-B branches byte-identical. **This will block even the zero-shot probe until it lands** — v21-B learned this the hard way. Do it first. |
| E4 | `:761-880` v20 arc probe (`hinge_local`, `axis_w` from `door_open_lr`) | Already computed in the door frame and sign-correct, so likely reusable as-is; but the *handle arc target direction* for pull must be re-derived. Verify, don't assume. |

### Tier F — telemetry & evidence (LOW risk, HIGH value — do this early, it is how everything else gets diagnosed)

| # | Item | Note |
|---|---|---|
| F1 | **`orthogonal_arc_residual_m`** (`:1628-1646`) | Handle-local TCP displacement is already decomposed into `along = \|Δ_y\|` (sliding along the bar) and `orthogonal = ‖Δ_(x,z)‖` (radial escape). **`orthogonal` is exactly the pull-off metric** and it is already exported per-episode (`:8207-8208`, `:8660`). Refine: split it by **signed** direction so "escaping in +X" (pull-off) is distinguished from "settling in −X". This is the round's cheapest and most direct transmission DV. |
| F2 | Finger PD-effort estimate | Point v21-B's `a2_hold_pd_effort_estimates(q, q̇, q_target, kp, kd, limit)` (`:19331-19438`) at `arm_j7/arm_j8` instead of `arm_j1..j6`. Carry the **same `ESTIMATE_ONLY` provenance label** — implicit actuators, PhysX does not expose true drive force. Corroborate non-proxily with finger joint tracking error, exactly as v21-B §3.2 does for the arm. |
| F3 | Hook / spring / mass bucketing | `spawnHook` is in metadata (`door.py:968`) but never read into the env. Add it (A3) — it is the free 2-level factor of §3.2. |
| F4 | Panel-robot contact, timed | New: contact events tagged by phase (pre-unlatch / during-pull / during-transit / post-release), with impulse. Distinguishes "brushed the panel" from "was struck by the closing door". |
| F5 | Swing-arc clearance margin | New: signed min distance from the robot footprint to the swept panel region. This is the instrument for the E2 event (§2.2) and for C3's design. Without it, C3 cannot be adjudicated. |
| F6 | Reused unchanged | `hinge_at_crossing`, `held_hinge_max`, `crossing_while_holding`, `send_to_cross_*`, `root_x_at_release`, terminal-reason histograms, strict trace topology validation, `N/A` never `0%`. |

### Tier G — namespace, configs, artifacts (LOW risk; get it right on day one)

- Task `door_pull` / env `door_pull_a2_base` / exp `door_pull_a2_base_lstm` / project `a2_piper_pull_door_a2_base` — from the old branch, and correct.
- New ablation yamls under `gr00t/rl/config/ablation/wbmanip/`, each carrying plan id, group/seed binding, source-lock fields, warm-start path+hash.
- New log roots per the `log-layout` memory contract. Never write into `logs_rl/.../base_v2x/` or `logs_eval/base_v2x/`.
- New `scriptsFORhuman/<pull-round>/` directory; new memory entry `memory/a2-piper/pull-open-door-task/`.

---

## 8. Proposed round structure

Deliberately shaped as **capability-establishment**, not a release round.

### P0 — implementation & admission (no training GPUs)

1. **E3 first**: extend the freeze guard with a pull plan id. Nothing — not even the zero-shot probe — runs until this lands.
2. Tier A + B + C1/C2 + F1–F5. Contract tests in the v21-B P0 style, including a test that fails if any unsigned `root_x` comparison survives outside `a2_pull_direction.py`.
3. **GUI static verification** (`static-visual-alignment` memory): spawn pose, yaw ≈ π, which handle face the gripper frames land on, pregrasp orientation (B3), staging band on the correct side, panel swing vs. robot position. **Cheap, and it catches the whole class of sign errors that would otherwise cost a training wave.**
4. **P0-Z(pull)** — zero-shot the frozen v20 G4 step2500 (§5.2). Interpretation only, never a training gate.
5. **P0-F(pull)** — friction/capability probe (rule 3): can the gripper hold against the closer while the base translates? Prefer the existing hold-oracle path over a new scripted probe (rule 5: a scripted probe must use only commandable DOFs and must clear a known-good anchor first — two prior scripted probes failed this).
6. Freeze one adaptation decision (v21-B §0.8 pattern) binding the enabled cells, the curriculum stage, and the warm-start choice.

### Phase 1 — learnability at the easy corner

Stage I of the §5.3 curriculum: hook always on, spring 2.5–5, mid-band height, low mass. One or two cells + a replicate (rule 8). Question: **is pull learnable at all in this env?** A negative here is informative and cheap; a negative discovered at full randomization is neither.

### Phase 2 — the free factorial

Open `spawn_hook`, then spring/mass. This is the force-feasibility landscape of §3.2. Cells and replicates per rule 8; θ (E2) as a rider only if Phase 1 shows the crossing moment is even the binding constraint — **do not assume it is; that is a push finding.**

### DVs (rule 12 — pick these deliberately, put them in every summary table)

- **DV-1 transmission:** signed `orthogonal_arc_residual_m` and slip-to-failure rate, split by `spawnHook` × closer force. *The round's headline.*
- **DV-2 safety:** panel-robot contact rate and impulse, by phase (F4).
- **DV-3 completion under the closer:** `crossing_while_holding` and `hinge_at_crossing` — in pull these are near-necessary conditions rather than quality metrics (§3.3).
- **DV-4 base intervention:** clearance margin (F5), base path length / reversal count, body-panel involvement. **This is the force_feasible dependent variable** (v21-B DV3), asked in the regime where the answer may finally be non-null. A null result here is a publishable negative, not a round failure.

---

## 9. Risks, ranked

| | risk | mitigation |
|---|---|---|
| **R1** | **C3 — `target_root_distance` (scale 12.0) as a straight-line attractor through the swing arc.** Highest-probability single cause of round failure. | Design it deliberately (§10-Q2); instrument with F5 *before* choosing; audit whatever is chosen against the income-cliff rule. |
| **R2** | **Income cliffs at the new stage boundaries.** The family is at 6 instances; pull introduces several boundaries at once. | Audit every pull-specific target against the income schedule it sits on, both sides (rule 1). Do this on paper before smoke. |
| **R3** | **Silent sign errors.** A missed `root_x > 0` mis-prices rather than crashes. | B6 single-owner module + contract tests + the GUI check + P0-Z as an end-to-end smoke test of the mirror. |
| **R4** | **Basin lottery on a from-scratch hard task.** 3/4 historical scratch runs landed wrong. | Replicate cells (rule 8) + the §5.3 curriculum + the P0-Z-informed warm-start decision. |
| **R5** | **Pull is genuinely infeasible for the Piper** (reach, or friction). | That is a *result*, not a failure — it is a kinematic/force feasibility boundary and directly serves the thesis. But find it in P0 (steps 4–5), not after a 7-cell wave. |
| **R6** | **Time budget.** Pull episodes are structurally longer; `max_episode_length_s: 20` and the stage budgets were sized for push. | Measure durations in P0-Z; adjust *before* freezing, and treat any post-hoc time extension as a diagnostic that can never select a winner (v21 §13). |
| **R7** | **GPU contention.** All 7 legal GPUs are on v21-B. GPU7 measured idle but is declared forbidden. | P0 needs almost no GPU. Sequence Phase 1 after v21-B releases; confirm GPU7's status with the user rather than assuming. |
| **R8** | **`add_walls=False`** (`door.py:70`) — the door is a free-standing frame, so sidestepping around the swing arc is unrealistically unconstrained. | Acceptable for round 1 (and it keeps the task learnable). Flag it as a known optimism in any claim, and consider `add_walls=True` as a later hardening axis. |

---

## 10. Open questions for the user / planner (these are decisions, not worker judgement calls)

- **Q1 — Is body/leg involvement legitimate in pull?** Handoff §1 item 8 bans deliberate body-push *today* because the arm is superhuman. In pull, bracing the panel or blocking the aperture before releasing may be genuinely necessary and is how humans do it. Ban it, measure it, or reward it? This changes D5 and DV-4 materially. My recommendation: **measure it, ban nothing a priori in the pull-specific phases, and keep the push-phase ban scoped to the phases it protects** (rule 7).
- **Q2 — What replaces `target_root_pos` in stage 4/5?** Waypoint lateral of the arc / clearance-gated through-target / aperture-tracking target / something else. This is the round's central design decision (R1).
- **Q3 — Pull-only, confirmed?** I recommend yes, strongly (§6). Mixed push/pull is a later round.
- **Q4 — θ_send: rider or out of scope?** I lean **out of scope for Phase 1**. Whether the crossing moment is even the binding constraint in pull is unknown, and importing a push-derived institution unexamined is the rule-11 trap in its purest form.
- **Q5 — GPU7:** actually forbidden, or was that specific to v21-B's measurement on 2026-08-02? It now reads 1018 MiB / 0%.
- **Q6 — Does the pull round wait for v21-B's verdict before Phase 1?** Not for implementation. But if v21-B selects a realistic `ARM_REALISTIC` effort profile, Phase 2 should probably adopt it, so that arm-feasibility and finger-feasibility are studied in the same actuator regime rather than two incompatible ones.

---

## 11. Reading list for whoever picks this up

1. `scriptsFORhuman/a2_piper_project_handoff_20260725.md` — §1 north star, §2 thesis, §4 the 12 rules, §6 code map. **Non-negotiable.**
2. `scriptsFORhuman/a2_piper_longterm_TODO.md` — table C item 4 is this round's charter.
3. `memory/a2-piper/door-asset-randomization-baseline/description.md` — the in/out decision, pre-analyzed 2026-07-03. Still accurate at HEAD.
4. `memory/a2-piper/door-asset-openio-sign/description.md` — why the hinge sign must NOT flip; why `push_door_force` stays off.
5. `scriptsFORhuman/V21/a2_piper_base_v21B_ablation_execution_plan_20260802.md` — **§2 anti-block doctrine and §3 P0 are the templates to copy**, plus §3.2's proxy-provenance discipline.
6. `scriptsFORhuman/V21/a2_piper_base_v21_implementation_training_execution_plan_20260801.md` — Route-B apparatus (§8, §11, §12) and the adaptation-window pattern (§0.8).
7. `scriptsFORhuman/force_feasible/` — the thesis. Read before claiming the round advances it.
8. `git show f624169` on branch `codex/a2-piper-pull-door` — prior art. **Read the direction contract; do not merge the code.**
9. `memory/a2-piper/log-layout/`, `memory/a2-piper/static-visual-alignment/` — artifact paths, and the GUI verification recipe P0 step 3 depends on.

---

*One-sentence brief: cut a fresh pull-door branch from `A2_Piper` HEAD (not from the unrebaseable v10-era `codex/a2-piper-pull-door`), scope it as pull-only capability-establishment rather than a release round, resolve warm-start-vs-scratch with a zero-shot probe of the frozen v20 G4 checkpoint in the mirrored env, and treat the already-randomized `spawn_hook` × closer-force factorial as the round's headline — it delivers the force-feasibility thesis's second, finger-limited regime at essentially zero physics cost, provided the stage-4 through-target is redesigned so it does not walk the robot into the swinging panel.*
