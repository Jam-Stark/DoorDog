# base_v22 — Revision-3 Change Log

**From:** `base_v22_posture_clearance_force_routing_v2` / `base_v22_execution_v2`
**To:** `base_v22_posture_clearance_force_routing_v3` / `base_v22_execution_v3`
**Date:** 2026-08-05 HKT
**Trigger:** independent local audit executed on the production host (able to run IsaacLab, read resolved configs, and recompute from delivered v21-B evidence).

Revision 2 remains **byte-unchanged** at:

```text
scriptsFORhuman/v22/a2_piper_base_v22_posture_clearance_force_routing_randomization_plan_20260805.md
scriptsFORhuman/v22/a2_piper_base_v22_experiment_manifest_revision2_20260805.yaml
```

Its historical evidence and plan identity remain valid. Revision 3 supersedes it for execution only.

**Path note.** The revision-3 brief referenced two input paths that do not exist in the repository
(`scriptsFORhuman/a2_piper_base_v22_posture_clearance_force_routing_plan_20260805.md`,
`scriptsFORhuman/v22/a2_piper_base_v22_experiment_manifest_20260805.yaml`).
The actual revision-2 artifacts listed above were used as the source of record.

---

## ACCEPTED

### A1 — Posture gates were uncalibrated

Revision 2 pre-registered absolute posture thresholds. Measured on the exact frozen `B1@500` warm start, over all available frames of the delivered v21-B pooled traces, all six fail in **both** profiles:

| quantity | measured | R2 STANDARD | R2 RELAXED_1 |
|---|---|---|---|
| \|pitch\| p50 | 0.2358 rad | ≤0.10 | ≤0.15 |
| \|pitch\| p95 | 0.3524 rad | ≤0.25 | ≤0.30 |
| \|roll\| p50 | 0.3840 rad | ≤0.06 | ≤0.10 |
| \|roll\| p95 | 0.4296 rad | ≤0.18 | ≤0.22 |
| roll saturation ≥0.95×0.40 | 56.9% | ≤8% | ≤15% |

Roll p50 misses by a factor of 6.4. Compounding this, posture-economy shaping is a **closed dead end** in project history: v16 (−0.15) and v17 (−1.5 ≈ 12% of income) both failed to move posture usage, and the P2 probe proved pitch is load-bearing (pitch-clamped goal collapses to 2/16).

### A2 — Same-denominator warm-start calibration added

New mandatory admission node `P0-POSTURE-BASELINE` (plan §7.6):

- raw producer is the exact frozen `B1@500`, no optimizer update, no action intervention, `posture_need` active for telemetry only;
- publishes the `ordinary_need_negative` denominator, contributing episodes, commanded **and** achieved pitch/roll separately, command saturation rates, and each `posture_need` component prevalence individually;
- binding requires ≥8/16 contributing episodes and ≥1000 `ordinary_need_negative` frames, otherwise `REPORT_ONLY_INSUFFICIENT_DENOMINATOR`, which may not block pilot, formal training, Route A, Route B, or a research-complete result;
- `<25%` of valid ordinary opening frames sets `POSTURE_NEED_OVERACTIVE_OR_VACUOUS`, demoting posture-need precision and ordinary-posture release claims to report-only;
- outputs `V22_POSTURE_BASELINE.json`, `V22_POSTURE_DENOMINATOR_ADJUDICATION.json`, `V22_POSTURE_GATE_FREEZE.json`;
- consumes **no** method amendment, **no** waiver budget, and **no** Window-C amendment (plan §3.7).

`posture_need` precision may bind only if its labels come from the independent `P0-B` causal intervention; labels derived from the `posture_need` signals themselves are circular and stay report-only (§7.6.6).

### A3 — Absolute posture thresholds removed as pre-registered blockers

`pitch p50 <=0.10/0.15`, `roll p50 <=0.06/0.10`, and `roll saturation <=8%/15%` are withdrawn as release blockers and replaced by same-denominator, warm-start-relative, command-side gates (plan §16.2/§16.3):

```text
STANDARD   pitch p50 <= 0.85*B0 ; roll p50 <= 0.80*B0 ; roll sat <= 0.70*B0
           pitch p95 <= B0+0.05 ; roll p95 <= B0+0.05
           ordinary goal regression <=1/16 ; ordinary clearance regression <=1/16

RELAXED_1  pitch p50 <= 0.95*B0 ; roll p50 <= 0.90*B0 ; roll sat <= 0.85*B0
           pitch p95 <= B0+0.08 ; roll p95 <= B0+0.08
           ordinary goal regression <=2/16 ; ordinary clearance regression <=2/16
```

No formal config may be promoted before `V22_POSTURE_GATE_FREEZE.json` exists, unless the worker signs `POSTURE_GATES_REPORT_ONLY`.

### A4 — Damping randomization plumbing and trace fields were missing

Verified on the host at the v21-B closure commit:

- hinge damping is read from the USD drive attribute (`door.py:971`), consumed at `door_open_a2_base.py:6347` — it is **not** a repo constant;
- `rand_hinge_drive_stiffness` and `rand_hinge_drive_max_force` exist; **`rand_hinge_drive_damping` does not**;
- the metadata assignment block (`door.py:1102-1117`) does not bind damping;
- accepted task traces carry neither damping nor stiffness.

Plan §5A now specifies the exact plumbing across `door.py`, `generate_door_assets.py`, `scenario_cfg/isaacsim.py`, and the evidence/export path, plus the rule that bucket membership may never be inferred from a scenario name.

### A5 — H0–H4 ranges are no longer frozen before P0-D

`hinge_randomization_state: P0_D_REQUIRED_UNFROZEN`, `final_bucket_ranges: null`, freeze artifact `logs_eval/base_v22/locks/V22_HINGE_RANGE_FREEZE.json`. The revision-2 numeric table survives only as plan **Appendix A**, labelled `PROVISIONAL_CANDIDATE_RANGES_NOT_AUTHORIZED_FOR_FORMAL_TRAINING`.

`P0-D` must first read `GetDampingAttr()` / `GetStiffnessAttr()` / `GetMaxForceAttr()` from actually spawned assets and publish values, units, and authority, then run free-return, fixed-torque, and attribution probes before any range is frozen. Range selection is authorized and consumes no Window-C amendment.

Six new negative tests (plan §20, items 19–24) reject missing runtime damping, metadata mismatch, trace mismatch, label-only bucket assignment, high-damping mislabelled as fast rebound, and formal materialization before the freeze artifact exists.

### A6 — Pooled release goal restored to 46/48

Revision 2 set `pooled goal >=45/48`, below the standing north-star red-line. Restored to **46/48**, non-waivable for a release claim, in STANDARD, RELAXED_1, and WORKER_ADAPTED alike. Research continuation below it is explicitly authorized via `RESEARCH_CONTINUATION_BELOW_RELEASE_GOAL`; a waiver may not relabel a sub-46/48 result as `V22_POSTURE_CLEARANCE_RELEASE` or `V22_FORCE_ROUTING_RELEASE`.

### A7 — 34 h mandatory / 51 h maximum formal budget documented

From measured v21-B wall clock (`base_v21B/formal/B1` step250→2500 = 17 h 07 m; `B4` = 16 h 49 m): Wave 1 ≈17 h, Wave 2 ≈17 h (mandatory ≈34 h), conditional Wave 3 ≈17 h (maximum ≈51 h), excluding P0, posture baseline, dynamics characterization, pilot, Route A, pooled48, Dynamics80, holdout64, and render. Liveness markers replace deadlines: overrun is not a runtime failure while checkpoints advance, metrics stay finite, the process is live, and no evidence error occurs.

---

## ACCEPTED WITH MODIFICATION

### M1 — All-frame B1 posture metrics are diagnostic, not the ordinary denominator

The audit figures come from trace fields `root_pitch` / `root_roll`, which are **achieved trunk angles, not commands**, measured over **all** frames rather than the `ordinary_need_negative` denominator. Revision 2 §20 negative test #2 already forbids conflating command with achieved posture; revision 3 keeps that prohibition and adds test #26 (posture gates evaluated on a denominator other than the frozen `B0`).

Consequence: these numbers justify **withdrawing** the revision-2 gates. They are **not** the `B0` baseline. Only `P0-POSTURE-BASELINE` may produce `B0`, and it must publish the command side separately.

### M2 — Suggested absolute values are not adopted

The audit's suggested interim absolutes (`roll p50 <= 0.30`, `pitch p50 <= 0.20`) are **not adopted**. They are achieved-side and all-frame, so adopting them would repeat the original error in a looser form. Plan §16.5 forbids converting them into gates and permits refinement of the relative formulas only on a stronger measured basis.

### M3 — The release gate stays strict; continuation below it stays authorized

The audit noted that revision 2 had quietly loosened the release goal. Rather than making the gate adaptable, revision 3 makes it **stricter and non-waivable** while making the *round* non-blocking: below 46/48 the worker continues under `RESEARCH_CONTINUATION_BELOW_RELEASE_GOAL` and closes with a valid non-release label. Strict release, permissive research.

---

## PRESERVED

- controlled fling as a legitimate clearance strategy, with no minimum fling rate and no generic coast penalty;
- `HAND_HOLD_CLEARANCE` and `BODY_HOLD_CLEARANCE`;
- the fast-rebound versus high-damping distinction, now enforceable only on measured response;
- the body-assist branch in full: approved bodies (trunk, FL_thigh, FR_thigh), arm-plus-posture failure latch, posture attempt before assist, E4/compound denominator, adjudication only at arm-failure denominator ≥8/16, frame contact never counted as assist, estimate-only torque authority, no true PiPER hardware-force claim, and `BODY_ASSIST_NOT_TRIGGERED` as a valid result that does not block the round;
- `theta_send = 0.90 rad`, release hinge `1.60 rad`, ARM_V20 effort profile, PiPER velocity limits, stage-time budget, 12D action and actor-observation dimensions;
- no legacy/scale-only Formal Wave A;
- formal cells G1–G6 in three two-GPU waves, Wave 3 skippable;
- worker waiver authority, STANDARD / RELAXED_1 / WORKER_ADAPTED, exploratory continuation, adaptation windows A/B/C;
- hard integrity and contact-safety gates;
- the GPU0/GPU1 contract, including the rule that an idle reading is not a lease;
- the verified warm start `d2732c14…`;
- active anti-rebound gripper bracing as a long-term TODO, not v22 scope.

---

## Audit findings confirmed correct and left untouched

| item | measured | status |
|---|---|---|
| warm-start SHA-256 | matches byte-for-byte | correct |
| GPU lease `[0,1]` | GPU2/3 leased to pull-v0; GPU4–7 occupied | correct |
| release velocity p95 ≤0.75 rad/s | 0.486 on warm start | 35% headroom |
| post-release collision = 0 | 0/43 on warm start | satisfiable; zero-tolerance retained |
| overspeed ≤2/48 | base rate ≈2.9% | tight but survivable |
| body-assist denominator guard | — | correctly designed |

---

## Patch table — revision 2 → revision 3

| R2 section | R3 section | change |
|---|---|---|
| header | header | plan/execution id → v3; supersession block; audit basis; GPU lease rationale |
| §0.1–0.5 | §0.1–0.5 | unchanged |
| — | **§0.6** | new: what R3 changes and the evidence for each |
| §1.1 | §1.1 | added item 12 (posture-gate calibration) and damping plumbing to item 6 |
| §1.2 | §1.2 | added "no restoration of legacy Wave A" |
| §2.2 | §2.2 | corrected: damping is a runtime USD attribute, not a constant; randomization absent; traces lack damping/stiffness |
| §2.3 | §2.3 | unchanged |
| §3.1 | §3.1 | added sub-46/48 relabelling to non-waivable list |
| §3.2–3.6 | §3.2–3.6 | unchanged except WORKER_ADAPTED cannot lower the release goal |
| — | **§3.7** | new: planned admission nodes consume no adaptation budget |
| §4 | §4 | unchanged |
| §5.2 (H0–H4 numeric) | **§5.2 + Appendix A** | ranges unfrozen; numeric table demoted to unauthorized appendix |
| §5.5 | §5.5 | manifests constructed after P0-D; candidate grids moved to Appendix A |
| — | **§5A** | new: exact damping plumbing requirements per file |
| §6 | §6 + **§6.0**, **§6.4** | runtime attribute read first; attribution checks; three required outputs; freeze |
| §7.1 | §7.1 | commanded and achieved must be distinct keys, reported separately |
| §7.2–7.5 | §7.2–7.5 | unchanged |
| — | **§7.6** | new: `P0-POSTURE-BASELINE`, denominator, adjudication, freeze, circularity rule |
| §8 | §8 | unchanged; §8.5 annotated with measured 0.486 headroom |
| §9 | §9 + **§9.5** | unchanged; insufficient-denominator result made explicit |
| §10 | §10 | reformatted as a table; `P0-POSTURE-BASELINE` added; P0-B flagged as the independent label source |
| §11 | §11 | posture clause dropped when gates are report-only |
| §12 | §12 | randomization column now "frozen by P0-D" |
| §13 | §13 | staged reset adds hinge bucket and free-return class |
| §14 | §14 | command/achieved reported separately; bucket from runtime values not names |
| §15 | §15 | unchanged |
| §16.1 | §16.1 | pooled48 ≥46/48 added as non-waivable; research-continuation label defined |
| §16.2 posture | §16.2 posture | absolute → same-denominator warm-start-relative |
| §16.2 task | §16.2 task | pooled goal 45 → 46 |
| §16.3 | §16.3 | relative posture formulas; pooled goal stays 46 |
| §16.4 | §16.4 | cannot lower release goal |
| — | **§16.5** | new: refinement rule forbidding unmeasured absolutes |
| §17 | §17 | release requires ≥46/48; non-release taxonomy extended with the four brief-specified labels |
| §18 | §18 | expanded with device rationale and measured wall-clock budget; liveness rule |
| §19 | §19 | added `generate_door_assets.py`, `posture_baseline.py`, `test_a2_v22_posture_baseline.py` |
| §20 | §20 | 18 → 28 negative tests (items 19–28 new) |
| §21 | §21 | added item 8 (damping plumbing absent at base commit) |
| §22 | §22 | P0 nodes exempt from budget; sub-46/48 added to "do not stop" list |
| §23 | §23 | unchanged |
| — | **Appendix A** | provisional unauthorized ranges |
| — | **Appendix B** | audit measurements, explicitly diagnostic and non-binding |

---

## Manifest typed-state summary

```text
posture_gate_state:                 P0_CALIBRATION_REQUIRED
posture_baseline_artifact:          null
posture_gate_freeze_artifact:       null
posture_need_state:                 null
hinge_randomization_state:          P0_D_REQUIRED_UNFROZEN
final_bucket_ranges:                null
hinge_range_freeze_artifact:        null
release_goal_pooled48:              46   (non-waivable)
formal_training_ready:              false
```

No unresolved runtime value is written as a frozen number anywhere in the revision-3 manifest.
