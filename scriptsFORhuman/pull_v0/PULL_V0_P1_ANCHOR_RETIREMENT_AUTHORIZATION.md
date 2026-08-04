AUTHORIZATION: pull-v0 gate audit — retire anchor, demote P1, proceed to review + P2
(Amendments 7–9)
Authority: arbiter, 2026-08-05 HKT. Supersedes Amendment 1 in full.
Amendments 3a, 4, 5, 6 remain in force unchanged.

== RATIONALE ==
Grasp capability is not an open question. v13–v20 validated bilateral debounced grasp
(K=5 streak), squeeze force window, and handle approach; v20 G4 closed at canonical goal
15/16 with render QA YES_5_OF_5. Attempt20 re-demonstrated it: on the push fixture the
door reached 1.043 rad with crossing_while_holding=True and max_body_force=0.0 N.

The scripted P1 probe asks whether an OPEN-LOOP TRAJECTORY can hold the handle under load.
That is neither the question we need answered nor a question whose answer transfers: a
policy can regrasp, modulate squeeze, and couple base yield to arm compliance in ways a
hand-written script cannot. Standing rule 5 is "policy-as-probe", and scripted probes have
now failed three times in this project (M18, the 37-revision probe, and this one — 20
attempts, R1–R17, zero mechanism data).

Gate audit result: of 71 non-repair receipts in scriptsFORhuman/pull_v0/, 55 are anchor
apparatus. Every genuinely pull-specific P0 gate already holds a PASS receipt.

== AMENDMENT 7 — retire the push-side anchor; demote P1 ==
RETIRED: Amendment 1 (push-side known-good anchor) in its entirety. It existed solely to
  validate the scripted P1 probe. With P1 no longer gating, it has no subject.
DEMOTED: P1-A/B/C/D/E scripted mechanism probe — from blocking gate to OPTIONAL diagnostic,
  to be reconsidered only if P2's event funnel is ambiguous.
RETIRED: Amendment 2's 120 kg fixture specification (its subject was P1-A). Its underlying
  PRINCIPLE — bind distributions to the RESOLVED v20 G4 config, never repo defaults —
  is retained and relocated to Amendment 9.

PRESERVE, DO NOT DELETE, all 55 anchor artifacts and their hashes. Write ONE closing
receipt (PULL_V0_P1_ANCHOR_RETIREMENT.json) that: binds the hash of this authorization;
lists the retired artifacts; records the terminal state (Attempt20 ANCHOR_FAIL,
scientific_verdict_consumed=false); and states that no pull mechanism verdict was ever
asserted or consumed. Receipt-chain immutability is not waived.

== AMENDMENT 8 — the gate set that remains ==
IN FORCE (all already PASS — confirm receipts, do not re-run unless noted):
  Tier-0 direction-site manifest      CLOSED_STATIC
  P0-B geometry proof (static+runtime) PASS  <- highest-value gate; push can never prove it
  P0-C two-direction smoke             PASS
  P0-D resolved-config assertion       (see Amendment 9)
  P0-E telemetry finite proof          NARROWED: verify only the new pull event fields
                                       (E0–E7 ordering, finiteness, N/A handling,
                                       ESTIMATE_ONLY stamps). Drop the exhaustive
                                       terminal-reason enumeration — push already
                                       exercises that machinery.
  P0-F zero-shot, PULL half            PASS  <- mirror correctness + P2 fingerprint
  P0-G canonical smoke                 PASS, but MUST BE RE-RUN against post-R13/R14/R17 code
  Amendment 3a pull freeze guard       done
  code_reviewer + isaaclab_reviewer    <- THE REAL GATE, still FAIL, must be re-run

NO LONGER A GATE:
  P0-F zero-shot, PUSH half — re-proves v20, already established by v20 Route A, render QA,
  and v21-B. Already executed; do not re-run.

Three receipts use non-standard status keys and were not machine-verified during the audit:
PULL_V0_SOURCE_FREEZE, PULL_V0_GEOMETRY_RUNTIME, PULL_V0_TELEMETRY_FINITE_PROOF.
Confirm each holds an explicit PASS-equivalent verdict, or say so plainly if it does not.

== AMENDMENT 9 — P2 preconditions ==
Dropping P1 is only safe if P2's telemetry can recover its science. Two gaps found in audit
that must close first:

(9a) spawnHook is NOT read into the env. Only `rand_spawn_hook` config overrides exist.
     Read `spawnHook` from door metadata (door.py writes it) into a per-env tensor and
     into the event-funnel stratification. Without it the hook axis — the free 2-level
     force-transmission factor — is silently lost.

(9b) gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py:36 carries "rand_spawn_hook": True,
     apparently a P1-fixture artifact. Verify it does NOT reach the P2 scenario. Hooks must
     be sampled at p=0.5 for the axis to exist. A deterministic override here would make
     every door hooked with nobody noticing.

(9c) Bind P2 to the RESOLVED v20 G4 config, asserted in P0-D against logs_rl/<run>/config.yaml:
       finger effort 45.0 / 45.0 N, stiffness 1300, damping 32   (NOT repo default 10 N / 80 / 3)
       a2_door_weight_range [80.0, 160.0]                        (NOT repo default [80, 120])
     Standing rule 10: the saved run config is the source of truth.

== EXECUTION ORDER ==
 1. Write PULL_V0_P1_ANCHOR_RETIREMENT.json (Amendment 7).
 2. Confirm the three unverified receipts (Amendment 8).
 3. Close gaps 9a and 9b. Small, product-side, covered by targeted tests.
 4. Re-run P0-G canonical smoke (64 env x 50 iter, GPU2) against post-R13/R14/R17 code.
 5. Re-run code_reviewer + isaaclab_reviewer against R13/R14/R17 + steps 3–4.
 6. On dual PASS: commit. Durable memory permitted. (Repo policy unchanged — this
    authorization clears no review gate; it removes the anchor that was blocking the
    re-run.)
 7. Proceed to P2.

== P2 CONTRACT (unchanged from cloud plan §D.4, with Amendment 9 bindings) ==
  cells:      W/S x seed {0,1,2}  = 6
  budget:     256 env, 750 batches, checkpoints 250/500/750
  actuator:   v20 G4 resolved profile for BOTH arms (do not vary finger effort here —
              it would confound initialization with mechanism; that contrast is P3)
  curriculum: v20 send/crossing/corridor selectors DISABLED
  GPUs:       GPU2 and GPU3 only (Amendment 4). 6 cells on 2 GPUs — sequence them.
  thresholds: all report_only
  DV:         event-funnel conditional probabilities P(E1), P(E2|E1), P(E3|E2), P(E4|E3),
              P(E5|E4), P(E7|E5), N/A never 0%, STRATIFIED BY spawnHook AND
              hinge_drive_max_force. This stratification IS the recovered P1 science —
              it is not optional.
  Amendment 6 accounting applies: failures before the first optimizer update are
  infrastructure, unlimited retry, and do not consume a scientific attempt.

== WHAT THIS AUTHORIZATION DOES NOT DO ==
- clears no review gate; both reviewers must still PASS on their own merits
- does not touch the six R13/R14 findings — they are product defects and the reviewer
  re-run is what confirms they are fixed
- changes no threshold, adds no cell, opens no new scope
- Amendments 3a, 4, 5, 6 unchanged; the five open human decisions (split doc §5) remain open

== ONE TRADE-OFF, STATED ==
This exchanges "map the mechanism boundary before training" for "learn it from training".
If pull is infeasible, P2 spends 6 small cells discovering that. Accepted: those cells are
a deliberately cheap bounded window, and "which event a policy stalls at" is a far more
actionable answer than "which step an open-loop script dropped".
