# A2+Piper Pull v1 Round Report

**Plan:** `a2_piper_pull_v1_reward_port_and_stage_semantics`
**Branch:** `codex/a2-piper-pull-v0-20260803`
**Status:** COMPLETE
**Evidence identity:** path-bound; this report contains no hashes.

## Technical summary

Pull-v1 closed the implementation and experiment loop, but did not solve the physical Stage3→4 gate. C1–C6, D0 frozen replay, 64×50 smoke, V1-A/V1-B dual-seed training, and the preregistered F1 handle-rescue V1-R all completed. Across 18 accepted v1 cell×checkpoint evals (288 terminal episodes), direct `hinge>0.25 ∧ grasp-streak ∧ panel_clear` success was **0/288**. All four integrity invariants were zero in every row.

The experiment still produced a useful positive finding. V1-A and V1-B stayed at the v0 hinge-noise scale (`valid-hold hinge Δ max ≤0.002201 rad`) and had zero stable unlatch in both seeds. V1-R, which adds `pull_door_handle: 6.0`, restored stable handle rotation in both seeds at step750: `13/16` for seed0 and `2/16` for seed1. Seed0 also reached hinge Δ max `0.100607 rad`, well above v0/A/B, but still below the `0.25 rad` gate; seed1 remained at baseline hinge scale. The defensible conclusion is therefore:

> The reward port is behaviorally active, but it is not sufficient to produce the physical gate transition and is strongly seed/checkpoint sensitive.

The preregistered negative statement **“reward 迁移不是主要瓶颈”** is **not triggered**, because V1-R measurably changed handle and, for seed0, hinge behavior. The next bounded investigation should compare successful R0 handle motion against R1 at the tensile force-transfer and trajectory level; another broad reward migration is not justified by this round.

## 1. Experiment design and metric definitions

- Warm actor: `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v0_p4_formal_seed0-20260805_211252/model_step_002500.pt`.
- V1-A: physical gate repair only; Stage3 bridge scales `0/0`.
- V1-B: V1-A plus `a2_stage3_unlatch_hold=3.0` and `a2_stage3_stage4_hold_and_drive=8.0`.
- V1-R: V1-B plus `pull_door_handle=6.0`, selected by F1 after A/B dual-seed results.
- Each formal cell: 256 environments, 750 training batches, checkpoints 250/500/750, `policy_only` warm start.
- Each accepted eval: full checkpoint load, 16 terminal episodes, diagnostic trace disabled while retaining pull-v1 raw telemetry.
- Only physical GPU6/GPU7 were used. Push-namespace config, receipt, and logs were untouched.

Primary dependent variables (DVs):

1. `true_stage3_to4_rate`: direct physical predicate `hinge>0.25 ∧ grasp-streak ∧ panel_clear`; stage labels are not trusted.
2. `positive_hinge_while_valid_hold_rate` and `hinge_delta_while_valid_hold_rad`.

Secondary funnel metrics: valid grasp, handle-angle distribution, stable unlatch (`handle≥0.3 ∧ stable_contact`), handle `≥0.6`, E2 capture/proof, capture loss, and Stage3 overtime. `N/A` means the component was absent or the conditional denominator was zero; it is not converted to zero. Exact lookup tables are used instead of charts because the main outcome is a binary zero across cells and the audit requires checkpoint-level values.

## 2. Main comparison table

`hinge Δ` and `handle` are median/max in radians. The E2 column is `capture / proof-duration median`. `Inv=0` means all four invariants were individually zero.

| Cell | Seed | Step | n | True S3→4 | +hinge/valid hold | hinge Δ med/max | Stable unlatch | Handle med/max / ≥.3 / ≥.6 | E2 / proof | Capture loss | S3 overtime | Integrity |
|---|---:|---:|---:|---:|---:|---|---:|---|---|---:|---:|---|
| v0 P4 | 0 | 2500 | 16 | 0/16 | N/S | N/S | N/S | N/S | 16/16 / N/S | N/S | 16/16 | legacy false-Stage4; not comparable |
| v0 P4 | 1 | 2500 | 16 | 0/16 | N/S | N/S | N/S | N/S | 8/16 / N/S | N/S | 16/16 | legacy false-Stage4; not comparable |
| v0 P5 rendered QA | 0 | 2500 | 2 | 0/2 | proxy 2/2 | held max .001859/.001414 | N/S | max .106772 / 0/2 / 0/2 | 2/2 / N/S | N/S | 2/2 | legacy reward leakage present |
| V1-A | 0 | 250 | 16 | 0/16 | 16/16 | .000568/.001796 | 0/16 | .000265/.145699 / 0/16 / 0/16 | 6/16 / .19s | 5/6 | 5/16 | Inv=0 |
| V1-A | 0 | 500 | 16 | 0/16 | 16/16 | .000852/.002143 | 0/16 | .000525/.041149 / 0/16 / 0/16 | 14/16 / .33s | 14/14 | 14/16 | Inv=0 |
| V1-A | 0 | 750 | 16 | 0/16 | 16/16 | .000619/.001836 | 0/16 | .002993/.645121 / 1/16 / 1/16 | 15/16 / .28s | 15/15 | 15/16 | Inv=0 |
| V1-B | 0 | 250 | 16 | 0/16 | 16/16 | .001423/.001949 | 0/16 | .000452/.053580 / 0/16 / 0/16 | 13/16 / 2.28s | 13/13 | 13/16 | Inv=0 |
| V1-B | 0 | 500 | 16 | 0/16 | 16/16 | .000946/.002072 | 0/16 | .000396/.058059 / 0/16 / 0/16 | 13/16 / .02s | 13/13 | 13/16 | Inv=0 |
| V1-B | 0 | 750 | 16 | 0/16 | 16/16 | .000930/.001937 | 0/16 | .000500/.174092 / 0/16 / 0/16 | 5/16 / .04s | 5/5 | 5/16 | Inv=0 |
| V1-A | 1 | 250 | 16 | 0/16 | 16/16 | .001775/.002201 | 0/16 | .000248/.100565 / 0/16 / 0/16 | 15/16 / 2.18s | 15/15 | 15/16 | Inv=0 |
| V1-A | 1 | 500 | 16 | 0/16 | 16/16 | .001784/.002182 | 0/16 | .003413/.785398 / 1/16 / 1/16 | 2/16 / .82s | 2/2 | 2/16 | Inv=0 |
| V1-A | 1 | 750 | 16 | 0/16 | 16/16 | .001705/.002199 | 0/16 | .000575/.174211 / 0/16 / 0/16 | 14/16 / .14s | 14/14 | 14/16 | Inv=0 |
| V1-B | 1 | 250 | 16 | 0/16 | 16/16 | .001567/.002008 | 0/16 | .000281/.021107 / 0/16 / 0/16 | 11/16 / .30s | 11/11 | 11/16 | Inv=0 |
| V1-B | 1 | 500 | 16 | 0/16 | 16/16 | .001783/.002101 | 0/16 | .000625/.042897 / 0/16 / 0/16 | 9/16 / .20s | 9/9 | 9/16 | Inv=0 |
| V1-B | 1 | 750 | 16 | 0/16 | 16/16 | .000923/.001764 | 0/16 | .000971/.677403 / 1/16 / 1/16 | 13/16 / .24s* | 13/13 | 12/16 | Inv=0 |
| V1-R | 0 | 250 | 16 | 0/16 | 16/16 | .001822/.002205 | 0/16 | .000590/.059751 / 0/16 / 0/16 | 9/16 / .30s | 8/9 | 8/16 | Inv=0 |
| V1-R | 0 | 500 | 16 | 0/16 | 16/16 | .002415/.026866 | 15/16 | .784338/.785398 / 15/16 / 14/16 | 15/16 / 1.26s | 15/15 | 15/16 | Inv=0 |
| V1-R | 0 | 750 | 16 | 0/16 | 16/16 | .012801/.100607 | 13/16 | .785398/.785398 / 13/16 / 13/16 | 13/16 / 2.42s | 13/13 | 13/16 | Inv=0 |
| V1-R | 1 | 250 | 16 | 0/16 | 16/16 | .001287/.002091 | 0/16 | .000431/.069937 / 0/16 / 0/16 | 6/16 / .17s | 6/6 | 6/16 | Inv=0 |
| V1-R | 1 | 500 | 16 | 0/16 | 16/16 | .001718/.002186 | 0/16 | .000513/.060218 / 0/16 / 0/16 | 13/16 / .10s | 13/13 | 13/16 | Inv=0 |
| V1-R | 1 | 750 | 16 | 0/16 | 16/16 | .001154/.002172 | 2/16 | .004848/.700337 / 2/16 / 2/16 | 10/16 / .24s* | 10/10 | 9/16 | Inv=0 |

`N/S` means not serialized in the referenced baseline evidence. The starred proof medians use available numeric values: B1-750 has 12 values for 13 E2 episodes; R1-750 has 9 values for 10 E2 episodes. Raw handle-only excursions in A0-750, A1-500, and B1-750 did not have stable contact, so their stable-unlatch rate remains `0/16`.

The two P5 episodes had legacy `dont_push_door_handle` sums `11.90093/24.58168` and `target_root_distance` sums `7.44853/18.18514`; these are the pre-v1 leakage values repaired by the new gates.

## 3. Integrity invariants

| Invariant | Accepted v1 rows | Aggregate result |
|---|---:|---:|
| `dont_push_door_handle` active before true Stage4 | 18 | 0 |
| `target_root_distance` active before latched `aperture_ready` | 18 | 0 |
| False E4 episode | 18 | 0 |
| Stage4 snapshot below the physical gate | 18 | 0 |

This is implementation evidence, not a scientific outcome: any nonzero result would have invalidated the affected cell and required a bug fix/replay.

## 4. Reward economics

V1-A bridge components are absent because their scales are zero; they are `N/A`, not zero. V1-B has bridge terms but no `pull_door_handle` term. Values below are `episode-sum total / active-step count / per-active-step mean`.

| Cell | Unlatch hold | Hold-and-drive | Pull-door-handle |
|---|---|---|---|
| B0-250 | .006027 / 649 / .000009286 | .244865 / 927 / .000264148 | N/A |
| B0-500 | .031965 / 183 / .000174674 | .930952 / 1073 / .000867616 | N/A |
| B0-750 | .001231 / 119 / .000010348 | .962948 / 359 / .002682306 | N/A |
| B1-250 | .004529 / 252 / .000017973 | 1.423520 / 1204 / .001182326 | N/A |
| B1-500 | .079275 / 830 / .000095513 | .206195 / 642 / .000321176 | N/A |
| B1-750 | 1.201453 / 2306 / .000521012 | .507274 / 1023 / .000495869 | N/A |
| R0-250 | .260822 / 1170 / .000222924 | .887319 / 694 / .001278558 | -5.518633 / 952 / -.005796883 |
| R0-500 | 147.939538 / 2713 / .054529870 | 10.594149 / 1386 / .007643686 | 215.038926 / 2011 / .106931341 |
| R0-750 | 116.234104 / 2030 / .057258179 | 41.651436 / 1330 / .031316869 | 194.681739 / 1823 / .106791958 |
| R1-250 | .070220 / 407 / .000172530 | .795200 / 526 / .001511788 | -2.653811 / 499 / -.005318258 |
| R1-500 | .156935 / 1296 / .000121091 | 1.146140 / 888 / .001290698 | -4.376323 / 363 / -.012055985 |
| R1-750 | 19.386527 / 1564 / .012395478 | .371858 / 961 / .000386949 | 5.753740 / 311 / .018500773 |

The R0-500/R0-750 economics align with stable handle behavior and increased hinge motion. R1 only shows a smaller late effect. This supports an active reward path but not a robust gate-capable policy.

## 5. Implementation and validation closure

C1–C6 completed:

1. Registered the reachable pull-v1 construction guard while preserving the v0 `report_only` route.
2. Defined hard-gate Stage3→4 as the base hinge/grasp-streak predicate AND exact body+arm `panel_clear`.
3. Made E3 a report-only `handle_position≥0.3 ∧ stable_contact` label.
4. Added a latched `aperture_ready` predicate and used it to gate E5/`target_root_distance`; clearance remains telemetry only.
5. Made the event graph explicit as `E0→E1→E2→E4→E5→E6→E7`, with E3 independent.
6. Added V1-A, V1-B, and the conditional F1 V1-R configs.

Static validation: Python compile PASS; YAML/Hydra composition PASS. The existing namespace suite reported `148 passed / 4 failed`; the four failures require missing historical Kit logs and were not repaired as unrelated fixtures. The single review wave found the original E4←E3 predecessor defect; it was fixed before D0 and no second broad review was run.

V1-R exposed two real construction-guard bugs at runtime: the first guard admitted only `pull_door_handle=0`; the first fix then compared runtime `dt`-scaled config values against unscaled constants. Both failed before batch1 and were fixed at the root. The final guard has exact config/runtime contracts for A=`0/0+handle0`, B=`3/8+handle0`, and R=`3/8+handle6`; invalid combinations still fail fast. The third launch attempt for each R seed trained and evaluated naturally.

## 6. D0 frozen replay and smoke

Accepted D0: `logs_eval/a2_piper_pull_v1/d0_frozen_replay/attempt3/`.

| D0 criterion | Result |
|---|---:|
| Completed episodes | 16/16 |
| Terminal/max stage ≤3 | 16/16; all stage3 |
| E4 / E5 | 0 / 0 |
| `dont_push_door_handle` episode-sum | zero in every episode |
| `target_root_distance` episode-sum | zero in every episode |
| `a2_stage3_unlatch_hold` raw | 7,734/7,734 finite; 2,491 nonzero only under Stage3+bilateral/stable contact |
| `a2_stage3_stage4_hold_and_drive` raw | 7,734/7,734 finite; 1,334 nonzero only under Stage3+bilateral/stable contact |
| Stage4-or-higher trace rows / below-gate Stage4 | 0 / 0 |

D0 attempt1 exposed a Hydra append-syntax error before IsaacSim. Attempt2 proved the core gate invariants with V1-A but could not materialize zero-scale bridge telemetry. Attempt3 used V1-B with the same actor/gate/episodes and closed the mandatory raw predicate.

Accepted smoke: `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_smoke_B_seed0-20260809_023541_retry1/`. V1-B 64 environments × 50 batches completed naturally in 655.20s with step50/last/config. The first smoke launch failed before environment construction because the current-worktree `PYTHONPATH` was absent; retry changed only the launch environment.

## 7. Autonomous decision log

| Rule | Evidence | Decision and result |
|---|---|---|
| F1 | A/B dual-seed primary DVs stayed at v0 scale; all 12 rows true gate `0/16`, stable unlatch `0/16` | Triggered V1-R. Isolated A/B handle-only crossings were not treated as repeatable gain. R produced secondary gains, so the preregistered negative sentence was not triggered. |
| F2 | V1-B did not beat V1-A on a primary DV in both seeds | Not triggered. |
| F3 | V1-A did not produce hinge progress beyond v0 scale | Not triggered. |
| F4 | A/B had no opposite primary-DV seed verdict; R later showed seed sensitivity after the fixed F1 scope was already running | No third-seed cherry-pick. Report the R seed split as uncertainty. |
| F5 | No true Stage4 occurred | Not triggered; `aperture_ready` early-latch behavior was not evaluated as a behavioral failure. |
| F6 | First two R launches failed before batch1 on distinct guard defects | Fixed each traceback root cause. The third/final permitted attempt passed for both seeds; no cell abandoned. |
| F7 | GPU6/GPU7 remained available | No serial fallback. |
| F8 | Accepted D0 had no C1–C4 semantic violation | No post-D0 product loop required. |
| F9 | Each completed formal cell remained below the 6-hour cutoff | No required matrix item was cut. |

V1-C remained outside the mandatory scope and was not run.

## 8. Interpretation, limitations, and next action

The gate repair is correct and the reward routes are active, but the learned behavior does not transfer handle rotation into sufficient door-hinge rotation. Seed0 R shows that the configuration can produce substantially more hinge motion; seed1 shows that this is not robust. The primary unresolved boundary lies between stable handle motion and tensile force delivered to the door hinge, not in the integrity of Stage3→4 labeling.

Limitations:

- Two training seeds and 16 eval episodes per checkpoint bound uncertainty; R cannot be called robust.
- Checkpoints are reported separately and are not pooled.
- P5 is a two-episode rendered-QA sample; it is not pooled with P4 or v1.
- B1-750 and R1-750 each lack one numeric proof-duration field; their E2 and loss denominators remain intact.
- No causal trajectory/force-transfer attribution was attempted in this round.

Recommended next scope: compare R0-500/R0-750 against R1-750 and matched A/B episodes using handle-frame force direction, arm/base trajectory, grasp stability, and hinge torque transfer. Preserve the hard gate and current invariants. Do not start V1-C or another reward sweep until that analysis identifies whether the limitation is tensile alignment, kinematics/action space, or trajectory basin.

## 9. Artifact index and evidence boundaries

- D0: `logs_eval/a2_piper_pull_v1/d0_frozen_replay/`
- Smoke: `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_smoke_B_seed0-20260809_023541_retry1/`
- Wave1 training: `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_{A,B}_seed0-20260809_025222/`
- Wave1 eval: `logs_eval/a2_piper_pull_v1/wave1/` (A step250 accepted path ends in `_retry1`)
- Wave2 training: `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_{A,B}_seed1-20260809_071140/`
- Wave2 eval: `logs_eval/a2_piper_pull_v1/wave2/{A,B}_seed1_step{250,500,750}/`
- Wave3 accepted training: `logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_R_seed{0,1}-20260809_110901_retry2/`
- Wave3 accepted eval: `logs_eval/a2_piper_pull_v1/wave3/R_seed{0,1}_step{250,500,750}_retry2/`
- Wave3 guard-failure evidence, excluded from scientific DVs: `pull_v1_R_seed{0,1}-20260809_104958/` and `pull_v1_R_seed{0,1}-20260809_110138_retry1/`

One mistyped A seed1 step750 eval launch targeted `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v1/wave2/A_seed1_step750`. It was stopped after approximately 1.3s, produced no eval metrics, was never used as evidence, and was left untouched. The accepted path is the `DoorDog-A2_Piper_pull_v0/logs_eval/...` path listed above.
