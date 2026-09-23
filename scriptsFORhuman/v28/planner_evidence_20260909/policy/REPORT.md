# v28 POLICY/REWARD lane report (read-only)

Source: `bbd98db` (branch `A2_Piper`). Tags: **INSPECTED** (source/config/log), **COMPUTED** (CPU scripts in `/tmp/v28_team/policy/`: `trace_stats.py` → `C_S2_{left,right}_stats.json`, `calibration.py` → `calibration.json`), **PROPOSAL**.
Reward per control step = `raw × scale × dt`, dt = 0.02 (`legged_robot_base.py:522-531, 1630-1634`). Train-log `Mean episode rew_*` = episode_sum / 20 s (`legged_robot_base.py:1514-1518`) — diluted by stage occupancy and short episodes, so per-stage numbers below come from the v27 C_S2 DEV eval step trace (`logs_eval/base_v27/v27_bilateral_hardening_20260905/q0_dev/C_S2/DEV/{left,right}/stage2_5_step_trace.json`, 128 episodes/side, deterministic policy).

## 1. Reward mechanics audit (INSPECTED)

| term | raw formula | DOFs | stage gating | per-joint weights | file:line |
|---|---|---|---|---|---|
| `penalty_dof_vel` | Σ dq² (L2, unnormalized) | arm_j1..j6 = `_upper_non_gripper_dof_idx` (built 7782-7786 = `upper_dof_indices` minus gripper) | none | none | `door_open_a2_base.py:17860-17865` (overrides all-20-DOF base `legged_robot_base.py:2016-2018`) |
| `penalty_dof_acc` | Σ (dof_acc)² | arm_j1..j6 | none | none | `17852-17857`; `dof_acc` = IsaacLab `joint_acc` (`isaacsim.py:2752-2753`), a finite difference over the **last physics substep (1/200 s)** because `ArticulationData.update()` refreshes it every sim step (`IsaacLab/.../articulation_data.py:97-102, 772-781`; `isaacsim.py:2923`). Not the control-dt formula of the base class (`2020-2024`). Contact-transient dominated. |
| `penalty_delta_action_rate` | Σ a_k² over `delta_action_indices` = high-level slots 5..10 = arm_j1..j6 **raw per-step increments** | arm_j1..j6 | none | none (indices double as action semantics) | `delta_action_base.py:59-63, 129-130`; config `resolved_config.yaml:1620-1627`. 1 action unit = 0.3×0.25 = 0.075 rad/step = 3.75 rad/s commanded. |
| `penalty_dof_overspeed` | Σ relu(\|dq\|−3.0)² (soft margin off) | arm_j1..j6 | none | none | `17909-17924`, `1842-1885`, floor `184`. j6 sim velocity limit is 3.0 rad/s (`resolved_config.yaml:2031`) → j6 can never trigger it; j1–j5 limit 5.0. |
| `penalty_upper_body_non_gripper_deviation_l1` | Σ \|q − q_default\| (L1) | arm_j1..j6, anchor `_get_a2_arm_default_dof_pos()` (`8484-8510` → `default_dof_pos`) | Stage0 & Stage5 via `effective_in_stage([...])` | none | `15878-15889` |
| `penalty_a2_stage4_arm_default_pose_l1` | same L1 / same anchor | arm_j1..j6 | Stage4 only, **no release gating** | none | `15891-15918`; scale 0.0 in v27 |
| `penalty_unused_dof_deviation_l1` | Σ \|q − resting_dof_pos\| | `arm_dof_indices[:6]` (`7787-7788`), anchor = config `resting_dof_pos` (`7823`; values j2=1.48, j3=−0.63, j4=−0.84, `resolved_config.yaml:1653-1673`) — **not** tied to `default_joint_angles` | Stages 1–4 | none | `15968-15979`; scale 0.0 |

No per-joint weight vector exists anywhere; `effective_in_stage` stage lists are hard-coded decorators (`staged_task_base.py:364-379`). The registry drops zero/absent keys before `_reward_*` lookup (`legged_robot_base.py:525-531, 616-623`), so an absent or zero new key is bit-identical. **Conclusion:** a wrist-only (j4/j5/j6) velocity/acc penalty cannot be expressed with existing keys (narrowing `delta_action_indices` would change j1–j3 action semantics). One new function is needed (§6).

## 2. Income structure

INSPECTED (train logs, iteration 6000 SK_S211_r1 / SC_S203_r1, per-second whole-episode means): dof_acc −0.168/−0.039, dof_vel −0.0055/−0.0018, delta_action_rate −0.059/−0.037, overspeed −0.018/−0.0012, posture L1 −0.97/−0.98 vs push_door_hinge 1.48/0.47, hold_and_drive 1.76/0.43, target_root_distance 2.51/1.16.

COMPUTED per stage, per control step (C_S2 DEV; L/R; 94 214 / 53 012 stage2–5 records):

| Stage | steps L/R | positive income | dof_acc | dof_vel | delta_rate | overspeed | smoothness Σ (% income) | \|dq\| p50 / p95 j4, j5, j6 (rad/s) |
|---|---|---|---|---|---|---|---|---|
| 2 | 1644/1653 | 0.300/0.276 | −.0021/−.0037 | −.0004 | −.0008/−.0011 | −.0030/−.0041 | 2.1% / 3.4% | j4 .46–.84/1.4–1.8; j5 .8–1.0/2.2–2.6; j6 .5/1.4–1.7 |
| 3 | 8066/7602 | 0.568/0.562 | −.0096/−.0064 | −.0002 | −.0005 | −.0004 | 1.9% / 1.3% | j4 .9–1.0/3.9–4.2; j5 .7–1.2/2.1–2.3; j6 2.1–2.8/3.0 |
| 4 | 56938/29595 | 0.538/0.566 | −.0046/−.0056 | −.0002 | −.0004/−.0008 | −.0008/−.0006 | 1.1% / 1.3% | j4 .5–.7/1.9; j5 .1–.6/2.0–4.0; j6 .9–2.1/2.9–3.0 |
| 5 | 27566/14162 | 0.303/0.358 | −.0013/−.0030 | −.0001/−.0004 | −.0019/−.0051 | −.0003/−.0039 | 1.2% / 3.5% (+ posture L1 −0.051/−0.139 = 17%/39%) | j4 .4–.5/1.4–2.9; j5 .4/1.3–3.5; j6 .5/1.5–2.7 |

Findings: (a) all four smoothness terms together are 1–3.5% of stage income while the wrist runs at 1.4–3 rad/s p95 — they are not shaping wrist behaviour; `penalty_dof_acc` is 60–90% of that total and is contact-driven, so it is not a usable wrist lever. (b) Stage3 depression (handle increasing, 2252/2213 steps): |dq6| p50 2.95/3.00, p95 3.00 — j6 rides its 3.0 rad/s joint velocity limit; creation-active steps identical; handle velocity p50 0.66–0.73 rad/s. Any Stage3 j6 velocity penalty taxes task-necessary motion at raw 9.0/step. (c) Stage5: j2/j3 are pinned at hard limits (= default 0,0) by saturated delta integrators (a_raw RMS j2/j3 1.05–3.6 with |dq| p50 ≈ 0.01) — source of the constant `limits_dof_pos` −0.015/step; right side posture L1 p95 = 5.5 rad (late/absent return). (d) Stage4 after hinge ≥ 1.2 with no two-finger contact: 5895/1019 steps, arm L1 p50 7.1/8.4 rad, wrist Σdq² 11–19 (flailing), income 0.20–0.31/step, no return incentive (scale 0).

**Calibration (PROPOSAL; arithmetic COMPUTED).** New term `penalty_a2_wrist_motion_l2`, scale −0.4, raw = Σ_{j∈{4,5,6}} Wv[stage][j]·dq_j² + Σ Wr[stage][j]·relu(−dq_j·dq_j,prev) (prev = `self.last_dof_vel`, control-rate, `legged_robot_base.py:1372`). One wrist joint at 150°/s (2.618 rad/s) sustained costs 0.4·w·0.02·6.854 = 0.0548·w per step.

| Stage | Wv (j4,j5,j6) | Wr (j4,j5,j6) | income/step | cost j4 @150°/s | fraction | j6 fraction | one 2 rad/s reversal |
|---|---|---|---|---|---|---|---|
| 0 strict | .35,.35,.35 | .5,.5,.5 | 0.08 (formula est.: walk_to_door 5·~0.75 + stage 1) | 0.0192 | 24% | 24% | 0.016 once |
| 1 strict | .5,.5,.5 | .5,.5,.5 | 0.12 (formula est.) | 0.0274 | 23% | 23% | 0.016 |
| 2 moderate | .75,.75,.75 | .5,.5,.5 | 0.288 | 0.0411 | 14% | 14% | 0.016 |
| 3 acc/reversal only | .5,.5,**0** | .5,.5,.25 | 0.565 | 0.0274 | 4.9% | **0** | 0.016 (j6 @3 rad/s: 0.018 once) |
| 4 moderate | 1,1,1 | .5,.5,.5 | 0.552 | 0.0548 | 9.9% | 9.9% | 0.016 |
| 5 strict | 1.25,1.25,1.25 | .5,.5,.5 | 0.331 | 0.0685 | 21% | 21% | 0.016 |

Stage3 check: depression j6 at 3.0 rad/s → new term 0; existing `penalty_dof_vel` 0.001·0.02·9 = 1.8e-4/step (0.03%); `penalty_dof_acc` unchanged (≈1.7%/1.1%); a single depress→release reversal costs 0.018 once vs handle_creation ≈ 0.09/step over ~10% of Stage3. Only the j4 p95 tail (4.1 rad/s, not the depression DOF) pays 0.067/step (11.9%). Stage0/1 incomes are formula estimates (no stage0/1 trace); confirm from a v28 G0 smoke before freezing W[0], W[1].

## 3. Posture anchor (INSPECTED)

Flow: `robot.init_state.default_joint_angles` (`gr00t/rl/config/robot/A2_Piper/a2_piper.yaml:122-139`) → `default_dof_pos` (`legged_robot_base.py:189-195, 215`) →
(a) reset: `_reset_dofs` sets arm j1–j6 exactly to `_get_a2_arm_default_dof_pos(env_ids)`, legs 0.8–1.2× default (`door_open_a2_base.py:29234-29247`); IsaacLab initial joint state uses the same dict (`isaacsim.py:1344-1350`);
(b) action zero: `jpos_target = actions_after_delay*0.25 + default_dof_pos` (`legged_robot_base.py:1150-1151`); arm slots routed `a2_base.py:1170-1181`; delta integration `delta_action_base.py:59-90`; backmap `legged_robot_base.py:1163-1166`, `a2_base.py:1252-1270`;
(c) anchors: `15879-15889`, `15891-15918` via `8484-8510`. Also the Stage0→1 advance requires max_j|q_j−default_j| < `a2_stage0_arm_default_max_deviation` = 0.1 rad (`29537-29554`; `resolved_config.yaml:1524`).
Observations move with it too: `dof_pos` obs = q − default (`legged_robot_base.py:2328-2331`; A2 override `17934-17939` passes through, canonicalization off), `actions` obs = cumulative arm delta (`a2_base.py:1347-1357`), `delta_actions` obs = last increments (`delta_action_base.py:132-133`). **Changing the yaml alone retargets (a), (b), (c), the stage0 gate and sim init — confirmed.** Not retargeted: `resting_dof_pos` (only consumer `penalty_unused_dof_deviation_l1`, scale 0 → must stay 0 or be updated).

Snapshot banks: staged reset stores robot root/dof state and tracked buffers incl. `delta_actions` (`7813-7819`) in GPU tensors (`staged_task_base.py:79-120, 503-565`); v27 recovery bank likewise (`14480-14528`). No `torch.save` in `gr00t/rl/envs`; trainer checkpoints hold no bank; `reset_from_dataset.enabled: false`; `reset_delta_actions_with_backmap` is a no-op (`delta_action_base.py:149-152`). Per-run only, restored with their own delta actions → no old-posture embedding across runs (verified).

Release detection: `_a2_stage4_release_gate` is an **income latch**, not a physical detector — OR-latched by `stage==4 & hinge ≥ a2_stage4_release_hinge_threshold(1.2)` (`2281-2288`, `15794-15805`, buffer `8876`, reset `28551`); it ends hold income (`a2_stage34_hold_income_mask` `2203-2228`, `18247-18254`) and un-halves `target_root_distance` (`2644-2671`, `17542-17545`). `dont_push_door_handle` (`17481-17486`) is handle kinematics only; `a2_v20_arm_tangent_carry` is disabled (scale 0). Physical release = `~_get_a2_stage3_stage4_contact_squeeze_masks(ctx)["both_contact"]` (`18514-18518`; streak buffer `_a2_stage3_stage4_both_contact_streak` `8869`; open command `_get_a2_gripper_primitive_raw_column` `6616`). **Proposed gate:** `(stage_buf == STAGE_SWING) & _a2_stage4_release_gate & ~both_contact`. Return-time telemetry can key off `_a2_release_event_valid` / `_a2_hinge_at_release` (`8907-8915`).

## 4. Action-zero shift and warm start

Δdefault = (j4 −0.25, j5 −0.94 rad). Loading C_S2 step 3000 `policy_only` on the new default: output — the same cumulative delta maps to targets shifted by (−0.25, −0.94) rad (j5 −54°); input — `dof_pos` obs shifted by (+0.25, +0.94) rad and the `actions` obs by (+1.0, +3.76) units for any physical pose (COMPUTED). With `policy_only_load_actor_rms: true` (`ppo_trainer_a2_base_api.py:7758-7793`, strict load incl. `running_mean_std`) j5 starts ≈2–3σ off the inherited statistics. Task-space obs (`gripper_handle_transform`, `relative_to_door`) are unaffected, so closed-loop recovery is plausible but unproven; the reset pose itself is consistent (delta 0 → new default).

**G1 probe (PROPOSAL):** cell `V28_G1_WARM`: checkpoint `logs_rl/by_batch/base_v26/v26_8_bilateral_opening_scaffold_decay_20260903_r3a/train/C_S2/model_step_003000.pt`, `checkpoint_load_mode: policy_only`, `policy_only_load_actor_rms: true`, otherwise the full v28 recipe (new asset, new default, camera bundle, no K), seed 281, 500 batches, saves at 250/500, exact64/side natural eval at 500. GPU: measured 22.05–22.96 s/iteration (4096 envs × 64 steps) → 500 batches ≈ 3.1 h + eval ≈ 15 min (a 128-episode eval took 11.5 min) ≈ 3.5 h on one GPU. Rule: **WARM_PASS** iff both sides D ≥ 40/64, clean ≥ 36/64, low_height+overspeed terminations ≤ 2 (S4+ ≥ 32 is implied) → add one warm arm to Wave A; **WARM_PARTIAL** iff both sides S4+ ≥ 32/64 but D < 40 → extend once to 1000 batches, re-apply; else **WARM_FAIL** → from-scratch only. Additionally the warm arm is dropped if D(warm, 500) < D(best SC seed, step 1000) − 4 on either side once Wave C step-1000 data exist.

**Wave C routing (pre-registered; labels from `scriptsFORhuman/v27/v27_reduce.py:495-520`):** `SCRATCH_3SEED_ESTABLISHED` → Wave A = 3 scratch seeds; `SCRATCH_SEED_UNSTABLE` → 3 scratch seeds, G1 mandatory, reserve a 4th seed; `SCRATCH_NOT_ESTABLISHED` → G1 mandatory, and if G1 fails → STOP for Owner decision. `K_SCRATCH_SUPERIOR` → include the 16-name scaffold decay (`reward_penalty_curriculum true`, min 0.2, degree −1e-4, driver `side_min_natural_stage_reach_rate` target 4, as `base_v27_SK_S211.yaml:13-45`) **and** add `penalty_a2_wrist_motion_l2` to `reward_penalty_reward_names` (otherwise at the 0.2 floor the Stage2 wrist fraction rises 5× to ~70%; accepted side effect: Stage4/5 wrist penalty also decays, posture terms do not); `K_SCRATCH_NONINFERIOR` / `INFERIOR` / `UNRESOLVED` → no K. Status now: SC_S203 and SK_S211–213 at 6000, SC_S201/202 at ~850 (restarted); no Wave C eval yet.

## 5. Typed outcomes for v28 (PROPOSAL)

Wave A: `V28_SC_S281/282/283` scratch, camera bundle, 6000 batches, milestones 1000…6000, exact64/side natural eval; plus the warm arm only if WARM_PASS.
(i) Reachability: reuse `passes_gate` (64: D ≥ 60, clean ≥ 56, low_height+upper_dof_overspeed ≤ 2 per side) → `REACH_3SEED` / `REACH_SEED_UNSTABLE` / `REACH_NOT_ESTABLISHED`; selection = earliest milestone passing both sides, tie smallest seed.
(ii) Camera behaviour, report-only (CAMERA lane computes; thresholds from the v27 baseline): wrist-cam angular speed p95 Stage2 ≤ 105°/s (half of 159–211), Stage5 ≤ 90°/s, Stage4 ≤ 150°/s, Stage3 ≤ 250°/s (j6 depression floor 172°/s); reversals/s ≤ 1.5 in Stage0/5, ≤ 2.5 in Stage2/4; Stage0/5 arm L1 p95 ≤ 0.5 rad and frames with |q6−q6,def| > 0.3 rad ≤ 5%; post-release return (L1 < 0.5 rad) p50 ≤ 2.0 s, p95 ≤ 4.0 s → `CAMERA_MET` / `PARTIAL` / `UNMET`; never blocks selection in v28.
(iii) Safety: tower–door panel/frame contact events > 5 N ≤ 2 per 64 episodes per side (if the tower collision body is present) in addition to the body-panel ≤ 5 N clean rule.
Wave B: selected seed → exact128 DEV and CONF at the selected milestone and at 6000, gate 120/112/4 → `a2_piper_base_v28_teacher_candidate_manifest` (checkpoint sha, resolved config, camera + safety metrics). Defaults: j5 = −0.44 (−0.52 only if the CAMERA lane's FOV check fails); no K unless routed; no controller low-pass; no no-bundle control. Not decided by v28: G7 binding (Owner), bundle ablation, sim2sim filtering, student distillation.

## 6. Change list (PROPOSAL)

| key | old | new | stage gating | rationale | CPU test |
|---|---|---|---|---|---|
| `robot.init_state.default_joint_angles.arm_j4/arm_j5` (`a2_piper.yaml:138-139`) | 0.25 / 0.5 | 0.0 / −0.44 | n/a | Owner decision; retargets reset, action zero, both posture anchors, stage0 gate (§3) | `test_a2_v28_config_contract_default_posture` (yaml arm values == [0,0,0,0,−0.44,1.57]; `penalty_unused_dof_deviation_l1 == 0`) |
| `penalty_a2_wrist_motion_l2` (new) | absent | −0.4 | via tables | only lever that targets j4–j6 without taxing j1–j3 or Stage3 j6 | `test_a2_v28_wrist_motion_raw_penalty_formula`, `..._reversal_only_on_sign_flip`, `..._stage3_j6_weight_zero` |
| `a2_wrist_motion_vel_weights` (new, 6×3) | absent | table §2 | per-stage gather on `stage_buf` | strict 0/1/5, moderate 2/4, Stage3 j6 = 0 | `test_a2_v28_wrist_motion_weights_contract_fail_fast` (shape (6,3), finite, ≥ 0; required only when the term is active) |
| `a2_wrist_motion_reversal_weights` (new, 6×3) | absent | table §2 | same | reversal-free Stage3 without a velocity cap | same test |
| `penalty_a2_stage4_arm_default_pose_l1` | 0.0 | −0.5 | Stage4 & release latch & no both_contact | start the camera-posture return in Stage4 (arm L1 7–8 rad after release; cost 0.5·0.02·7.5 = 0.075/step = 25–37% of released income) | `test_a2_v28_stage4_post_release_mask` (pure mask fn) |
| `a2_stage4_arm_default_pose_release_gated` (new bool) | absent | true | — | required when the term is active; `false` reproduces current stage-only gating | `test_a2_v28_stage4_post_release_gate_false_is_stage_mask` |
| `penalty_dof_vel` / `penalty_dof_acc` / `penalty_delta_action_rate` / `penalty_dof_overspeed` | −0.001 / −1e-5 / −0.01 / −0.1 | unchanged | none | raising any of them taxes j2/j3 approach at 5 rad/s (Stage2), contact transients, or exploration noise (σ 0.8 ⇒ E[a²] ≥ 0.64/joint) rather than wrist behaviour | registry test `test_a2_v28_reward_registry_absent_or_zero_key_bit_identical` |
| `penalty_upper_body_non_gripper_deviation_l1` | −5.0 | unchanged | Stage0/5 | already 17–39% of Stage5 income; anchor retargets automatically | — |
| `penalty_unused_dof_deviation_l1` / `resting_dof_pos` | 0.0 / stale vector | unchanged (0.0) | — | stale anchor; must not be enabled | covered by config contract test |
| K scaffold-decay block + `reward_penalty_reward_names` += wrist term | absent | only if `K_SCRATCH_SUPERIOR` | — | §4 routing | `test_a2_v28_k_recipe_names_include_wrist_term` (branch only) |

Minimal new function (spec): module-level pure `a2_wrist_motion_raw_penalty(dof_vel_wrist, last_dof_vel_wrist, stage_buf, vel_weights, reversal_weights)` → `(N,)`; wrapper `_reward_penalty_a2_wrist_motion_l2` reads `simulator.dof_vel[:, idx]` and `self.last_dof_vel[:, idx]` with `idx = _upper_non_gripper_dof_idx[3:6]` (asserting names arm_j4..j6), gathers weights by `stage_buf`; fails fast on missing/ill-shaped tables. Tests follow the existing AST-extraction pattern (`gr00t/rl/tests/test_a2_v19_env_semantics.py:27-31`) so they run without IsaacLab. Runtime evidence still needed (not run): a v28 G0 smoke to confirm the term appears in `Mean episode rew_*`, the reset posture, and Stage0/1 income for W[0], W[1].

Nothing in any repository was modified; scratch outputs only under `/tmp/v28_team/policy/`.
