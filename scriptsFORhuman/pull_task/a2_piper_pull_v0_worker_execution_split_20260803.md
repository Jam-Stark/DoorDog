# A2+Piper Pull-Door (拉门) v0 — Adopted Plan Amendments & Two-Worker Execution Split

**Document ID:** `a2_piper_pull_v0_worker_execution_split_20260803`
**Date:** 2026-08-03 HKT
**Author:** local planner session (Claude), after cross-review of the cloud plan `a2_piper_pull_v0_tensile_feasibility_v1`
**Adopted base plan:** the cloud pro model's plan **`a2_piper_pull_v0_tensile_feasibility_v1`** (2026-08-03, archived at `scriptsFORhuman/pull_task/a2_piper_pull_v0_tensile_feasibility_v1_20260803.md`) — **PASS with three binding amendments** (§2 below). Where this document is silent, the cloud plan governs. Where this document and the cloud plan conflict, **this document governs** (it encodes the arbiter's adopted corrections).
**Local reference analysis:** `scriptsFORhuman/pull_task/a2_piper_pull_door_worktree_cut_and_round_design_20260803.md` (peer analysis; the cloud plan's §I disagreement register was written without access to it — see Amendment 3).

**Execution split (user-directed, for permission reasons):**

- **WORKER 1** operates in the **mainline worktree** `/home/baoquanc/workspace/DoorDog-A2_Piper` on branch `A2_Piper`. Scope: repository surgery only — archive/delete the stale pull branch and worktree, commit and push the planning documents, cut the new pull branch and worktree. **Worker 1 writes no task code.** Its job ends when the new worktree exists and is pushed.
- **WORKER 2** operates in the **new pull worktree** created by Worker 1. Scope: everything else — the amended cloud plan's Appendix-A build order, P0 admission, P1 mechanism matrix, P2 initialization experiment, and onward. **Worker 2 never edits the mainline worktree** and never touches push-line configs, receipts, or logs.

**Standing context both workers must respect:**

- v21-B formal training is **live on GPUs 0–6** (tmux `base_v21B_formal_v1`). Do not touch those tmux sessions, their GPUs, or anything under `logs_rl/.../base_v21*` / `logs_eval/base_v21/`.
- **GPU7 is not authorized.** Its availability is an open human decision (cloud plan §H-9). No step below requires it.
- Plans/replies in English; repo memory entries follow repo conventions (zh + EN technical terms, HKT timestamps). Repo `AGENTS.md` governs memory etiquette.

---

# 1. What was adopted, in one paragraph

The pull-v0 round follows the cloud plan's structure: an event-funnel definition of the task (E0–E7: outside-face alignment → load-bearing tensile capture → latch release → positive hinge progress under retained capture → sweep-clearance and release-or-hold decision → path reversal → whole-body clear); a single IO-aware `grasp_target` in the door builder (`grasp_target_face_x = door_open_io * axle_length / 2`); an immutable direction contract consumed by every world-X-dependent site; v20 send/crossing curriculum **disabled** in P0–P3 (telemetry ported, behavior not); a P1 hook × friction × finger-effort mechanism matrix that classifies contact mode instead of presuming "friction-limited"; a P2 six-cell warm-vs-scratch bounded-adaptation experiment (W/S × seeds 0/1/2, 256 env × 750 batches) decided on event-funnel learning curves, with zero-shot retained as a P0-F fingerprint only; `report_only` status for all task thresholds until measured (anti-block doctrine); and the no-op set (hinge sign, latch, closer, handle joints, physics ranges, procedural spawner) left untouched.

---

# 2. Binding amendments to the cloud plan (arbiter-adopted)

These three amendments were accepted by the user after local review. Worker 2 must implement the cloud plan **as modified below**.

## Amendment 1 — P1 scripted probe requires a push-side known-good anchor (hard gate)

**Amends:** cloud plan §F.4 (P1-D probe sequence).

Standing rule 5: a scripted probe's verdicts count only after it (a) uses only commandable DOFs and (b) **passes a known-good anchor**. Two historical scripted probes (M18, the 37-revision probe) failed exactly this and produced false infeasibility verdicts.

**Required change:** before any pull-side P1 cell is interpreted, the identical scripted sequence (pregrasp → close under the cell's resolved actuator profile → monotone low-speed tensile/compressive proof → handle rotation → conservative arc/yield follow) must first be run **on the push side** — same fixture door mirrored to the `out` configuration, same actuator profile — where the v20 policy history proves the interaction is physically achievable. The push-side anchor must achieve: stable bilateral capture, latch release, and ≥0.25 rad hinge progress (the v20 G4 resolved stage-3→4 threshold) without body-panel contact.

**Gate:** if the anchor fails on the push side, the probe implementation is defective; **no pull-side P1 verdict may be recorded** until the anchor passes. A pull-side "all cells fail before E2/E4" result without a passing push anchor is `PROBE_INVALID`, not a mechanism finding.

## Amendment 2 — P1 central fixture takes its mass from the resolved v20 G4 config (rule 10)

**Amends:** cloud plan §F.4 (P1-A central deterministic fixture).

The cloud plan set fixture mass to 100 kg as the midpoint of the repository source range `door_weight=(80, 120)`. This repeats the exact rule-10 trap the cloud plan itself documents: the **resolved** v20 G4 run config carries `a2_door_weight_range: [80.0, 160.0]` (verified on the worker host, 2026-08-03, in `logs_rl/a2_piper_full_stage_a2_base/base_v20_R3_G4-20260731_004712/config.yaml`, key at line ~538). The training distribution the warm-start checkpoint actually experienced is 80–160 kg.

**Required change:** P1-A fixture `door mass = 120 kg` (midpoint of the resolved range). All other fixture midpoints in the cloud plan's table were audited against source and stand (handle height 0.95, hinge max-force 7.25, hinge stiffness 5.5, axle 0.195, etc.). The fixture receipt must cite the resolved config path as the range authority, and must state explicitly that the repo-default `(80, 120)` was **not** used and why.

## Amendment 3 — freeze-guard work moves to the front of the build order; disagreement register redone after document push

**Amends:** cloud plan Appendix A (build order) and §I (disagreement register).

(a) **Freeze guard first.** `_validate_a2_v20_r1_config` (`gr00t/rl/envs/door/door_open_a2_base.py`, grep the symbol) is invoked at env construction on **both** the training and the eval path. v21-B's P0-G experience: until a plan-id-keyed branch exists, this guard blocks *everything*, including the P0-F zero-shot fingerprint and the P0-C two-direction smoke. The cloud plan has the pull freeze guard in §E.9 but sequences it too late. **Amended build order for Worker 2: the pull plan-id freeze-guard branch (leaving all v20/v21-B branches byte-identical, with the regression tests in the v21-B P0-G style) is step 3, immediately after source freeze and the direction-site manifest, and before any env/asset edit.**

(b) **Disagreement register is stale by construction.** The cloud plan's §I was written against five quoted claims because the local analysis document and the historical pull branch were not retrievable remotely (both were unpushed/untracked at the time). Two of its recorded "disagreements" (IO-aware `grasp_target`; do-not-rebase the old branch) are in fact agreements with the local document's Tier A2 and §4. **Worker 1 pushes both local planning documents (§4 step 3); after that, a follow-up cloud audit round against the full documents is authorized but not blocking** — Worker 2 does not wait for it.

## Non-amendment clarifications (no change, recorded to prevent drift)

- The cloud plan's E.6-item-5 / F.10 "outward-yield income must not be opposed by the final target" is the same design constraint as the local document's C3/R1, stated at the correct (event) level. One constraint, not two.
- The four open human decisions remain open and block nothing in P0–P1: hook task scope (§H-4), release-or-hold North-Star status (§H-5), authoritative finger force value (§H-3 — 10 N and 45 N are both *simulator profiles* until the user rules), GPU7 (§H-9).
- Verified for Worker 2's convenience (resolved v20 G4 config, worker host, 2026-08-03): 20-entry `dof_effort_limit_list` ends `..., 100.0 ×6 (arm_j1..j6), 45.0, 45.0 (fingers)`; `a2_door_weight_range: [80.0, 160.0]`. The repo robot yaml disagrees (10 N fingers); the resolved config is the authority.

---

# 3. WORKER 1 — mainline repository surgery

**Worktree:** `/home/baoquanc/workspace/DoorDog-A2_Piper` (branch `A2_Piper`).
**Permissions assumption:** may run git branch/worktree/tag/push operations and commit documentation under `scriptsFORhuman/`. Writes **no** code under `gr00t/`.
**Hard constraints:** do not touch tmux sessions, GPUs, `logs_rl/`, `logs_eval/`, or any `memory/` entry other than the one specified in step 6. Do not delete anything not explicitly listed below.

### Step 0 — preconditions

```bash
cd /home/baoquanc/workspace/DoorDog-A2_Piper
git fetch origin
git checkout A2_Piper
git rev-parse HEAD   # record; expected 7808114... or a descendant.
git status --short
```

If HEAD is not `7808114...` or a descendant of it, **stop and report**. Expected dirt at handoff time (2026-08-03): untracked `scriptsFORhuman/pull_task/`, modified `scriptsFORhuman/README.md` (both to be committed in step 3), and v21-B worker files (`scriptsFORhuman/v21B/_v21b_common.py` modified, `scriptsFORhuman/v21B/a2_piper_v21B_postformal_eval.py` untracked) — **leave the v21-B files strictly alone**; they belong to the live v21-B round. Any dirt beyond these: stop and report — do not guess.

### Step 1 — archive the stale pull branch (do not silently destroy history)

The old branch `codex/a2-piper-pull-door` (tip `f624169`, base `496ea4f`, 2026-07-14, never simulated) is retired per the adopted plan (cloud §D.5, local §4). Preserve it as a tag first:

```bash
git tag archive/pull-door-v10-static-20260714 f624169
```

### Step 2 — remove the stale worktree and branch

The worktree at `/home/baoquanc/workspace/DoorDog-A2_Piper_pull` was verified clean (`git status` empty) on 2026-08-03. Re-verify before removal; if it is no longer clean, stop and report instead of forcing.

```bash
git -C /home/baoquanc/workspace/DoorDog-A2_Piper_pull status --short   # must be empty
git worktree remove /home/baoquanc/workspace/DoorDog-A2_Piper_pull
git branch -D codex/a2-piper-pull-door
```

(`-D` is safe: the tip is preserved by the step-1 tag.)

Do **not** touch the other worktrees (`DoorDog-A2_Piper_hold_handle`, the distillation worktree, the `/tmp` runtime worktrees, or `GR00T-VisualSim2Real`).

### Step 3 — commit and push the planning documents

All pull-round planning documents live in `scriptsFORhuman/pull_task/`. Commit the whole directory (Amendment 3b depends on this):

```bash
git add scriptsFORhuman/pull_task/ scriptsFORhuman/README.md
git commit -m "docs(a2): adopt pull-v0 plan with amendments and worker split"
```

Do **not** `git add` anything under `scriptsFORhuman/v21B/` — those files belong to the live v21-B round.

Expected contents (verify all four are present; stop and report if any is missing):

```text
scriptsFORhuman/pull_task/README.md
scriptsFORhuman/pull_task/a2_piper_pull_door_worktree_cut_and_round_design_20260803.md
scriptsFORhuman/pull_task/a2_piper_pull_v0_tensile_feasibility_v1_20260803.md
scriptsFORhuman/pull_task/a2_piper_pull_v0_worker_execution_split_20260803.md
```

(The transient cloud-planner prompt file was already retired by commit `7808114` and is intentionally absent.)

### Step 4 — cut the new pull branch and worktree from current HEAD

```bash
git rev-parse HEAD > /tmp/pull_v0_base_sha.txt   # record the exact base
git worktree add ../DoorDog-A2_Piper_pull_v0 \
  -b codex/a2-piper-pull-v0-20260803 HEAD
```

Naming is fixed: branch `codex/a2-piper-pull-v0-20260803`, worktree `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`. (A fresh directory name avoids any confusion with artifacts of the removed `_pull` worktree.)

### Step 5 — push

```bash
git push origin A2_Piper
git push origin codex/a2-piper-pull-v0-20260803
git push origin archive/pull-door-v10-static-20260714
```

### Step 6 — memory sync (mechanical, minimal)

Update `memory/a2-piper/worktree-routing/` (its `description.md` routing list) to: remove the old `_pull` worktree entry, add the new one (`/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`, branch `codex/a2-piper-pull-v0-20260803`, base SHA from step 4, purpose: pull-v0 per this document). HKT timestamp. Commit on `A2_Piper` and push. Do **not** create or edit the `pull-open-door-task` entry — that is Worker 2's, in the new branch.

### Step 7 — completion report

Report: base SHA, tag SHA, worktree path, branch names pushed, and any deviation. **Worker 1 is then done.** It does not enter the new worktree.

---

# 4. WORKER 2 — pull-v0 implementation in the new worktree

**Worktree:** `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0` (branch `codex/a2-piper-pull-v0-20260803`).
**Governing plan:** the cloud plan `a2_piper_pull_v0_tensile_feasibility_v1` **as amended by §2 of this document**. Read it in full before writing code; read the local analysis document and the handoff's 12 standing rules alongside it.
**Hard constraints:** never modify push-line configs/receipts/logs; keep all pull artifacts in the pull namespace (cloud §D.2/E.9); GPUs — none until P0-F/P1, and then only an explicitly allocated device, never GPU7, never the v21-B GPUs while v21-B runs; all new task thresholds `report_only` until measured; `N/A` never `0%`; `ESTIMATE_ONLY` provenance on all implicit-actuator effort fields.

### 4.1 Amended build order (supersedes cloud Appendix A ordering)

```text
 1. Source freeze: record base SHA, warm-checkpoint hash
    (f000f13e817309f7b73e33c5c4d95076397debbb… — full hash in cloud §0.3; verify byte-for-byte),
    copy the v20 G4 saved config.yaml read-only into the pull evidence bundle.
 2. Direction-site manifest: run the cloud §E.2 git-grep set against THIS checkout;
    classify every match (change / no-op / test) into
    scriptsFORhuman/pull_v0/PULL_V0_DIRECTION_SITE_MANIFEST.json.
    Formal implementation is blocked until every match is classified.
 3. ★ Pull freeze-guard branch (Amendment 3a — moved forward):
    add plan id `a2_piper_pull_v0_tensile_feasibility_v1` handling next to
    `_validate_a2_v20_r1_config`, leaving every v20/v21-B branch byte-identical.
    Unit tests in the v21-B P0-G style: v20 G4 resolved config still validates;
    a pull config validates; a pull config resolving push targets / out-IO /
    +X final target / a different finger profile fails BEFORE the first env step.
 4. Immutable direction contract (io_sign / approach_side_x / travel_dir_x /
    active_handle_face_x / signed helpers) + unit tests instantiating BOTH in and out.
 5. IO-aware grasp_target in spawn_door (single conditional prim,
    face_x = door_open_io * axle_length / 2); hinge/handle/latch signs untouched.
 6. Paired static geometry proof + target/TCP/frame debug render (cloud P0-B),
    including the target-orientation overlay — the orientation is decided from
    the overlay, not guessed.
 7. Pull namespace: env/config/reward/ablation/log roots per cloud §D.2/E.9;
    pull reset (+X side, yaw≈pi), signed staging, signed final target.
 8. Event-state telemetry (E0–E7 fields, cloud §E.8) + finite-data proof (P0-E).
 9. v20 send/crossing/corridor selectors disabled; telemetry ported sign-correct.
10. P0-C two-direction architecture smoke (one out + one in env through
    reset/obs/reward/termination).
11. P0-F frozen-W paired push/pull zero-shot fingerprint on the exact resolved
    v20 actuator profile (45 N / 1300 / 32 fingers) — BEFORE any effort or
    friction change. Report-only.
12. P0-G canonical smoke: 64 env × 50 iterations, pull namespace.
13. P1 mechanism matrix (hook × finger-effort{10,45} × friction{base,low,high}):
    ★ Amendment 1 — the scripted probe must FIRST pass the push-side known-good
    anchor (stable bilateral capture, latch release, ≥0.25 rad hinge progress,
    no body-panel contact) on the mirrored `out` fixture under the same profile.
    No pull verdict is recordable without a passing anchor receipt.
    ★ Amendment 2 — central fixture mass = 120 kg (midpoint of the RESOLVED
    a2_door_weight_range [80,160]); fixture receipt cites the resolved config path.
14. P2 six-cell W/S × seed{0,1,2} bounded adaptation (256 env × 750 batches,
    common v20-resolved actuator profile, send curriculum off), decided on the
    event-funnel learning curves per cloud §D.4 — only after a legal GPU
    allocation is confirmed by the user.
15. Sign one adaptation/acceptance decision from measured P1/P2 results;
    then P3/P4 only along the pre-registered forks (cloud §F.6/F.7/§G).
```

### 4.2 Deliverables (per phase, cloud §E.9 receipts discipline)

- `scriptsFORhuman/pull_v0/` — manifest, geometry-proof report, anchor receipt (Amendment 1), fixture receipt (Amendment 2), P0 admission JSON, P1 landscape report, P2 event-funnel report with the Appendix-D summary-table schema (which must contain the round's own DV — the clean E2→E4 funnel — per standing rule 12).
- A fresh `memory/a2-piper/pull-open-door-task/` entry (replacing the retired one's role): direction contract, evidence boundary (static vs runtime), reproducible commands. HKT timestamps. Sync `scriptsFORhuman/a2_piper_longterm_TODO.md` when the round produces its first archived verdict.
- Commit style follows repo history (`feat(a2): …`, `docs(a2): …`, small bound commits).

### 4.3 Stop conditions (beyond the cloud plan §G table)

Stop and escalate to the user, preserving evidence, when: the push-side anchor cannot be made to pass after one implementation repair (probe design question, not a worker retry loop); the freeze-guard extension cannot preserve v20/v21-B byte-compatibility (fork to an independent key, mirroring v21-B F1, then report); any P0 geometry assertion fails in a way that implicates the door builder rather than the pull code; or any step would require touching a v21-B GPU/tmux/artifact.

---

# 5. Open human decisions (unchanged, for the record)

Blocking nothing in P0–P1; must be decided before the marked phase:

| # | Decision | Blocks |
|---|---|---|
| 1 | Hook task scope — are hooked levers part of the primary task family? | P1 *interpretation*, P3 |
| 2 | Release-before-traversal vs deliberate hold-through — North-Star status | P4 reward design |
| 3 | Authoritative hardware finger force (10 N? 45 N? other?) | P3/P4 "realistic" labeling |
| 4 | GPU7 authorization | nothing (convenience only) |
| 5 | Add a v21-B winner as a third P2 initialization if it qualifies in time | P2 freeze |

---

*One-sentence brief: the cloud plan `a2_piper_pull_v0_tensile_feasibility_v1` is adopted with three amendments — a push-side known-good anchor gating every P1 probe verdict, a 120 kg fixture mass taken from the resolved (not repo-default) v20 G4 weight range, and the pull freeze-guard moved to the front of the build order — and execution is split so Worker 1 only performs mainline git surgery (archive-tag and remove the v10-era pull branch/worktree, push the planning docs, cut `codex/a2-piper-pull-v0-20260803` + worktree `DoorDog-A2_Piper_pull_v0`), after which Worker 2 executes the amended P0→P1→P2 sequence entirely inside the new worktree.*
