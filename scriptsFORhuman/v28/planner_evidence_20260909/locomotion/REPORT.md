# v28 LOCOMOTION lane (A2_Base) — report

Read-only inspection of DoorDog (`/home/baoquanc/workspace/DoorDog-A2_Piper`, A2_Piper), LMP worktree (`…/LMP-a2-current-gripper-observation`, uncommitted diff on `3d472dd`), LMP main, sim2sim worktree, v27 eval traces and training logs. CPU stdlib scripts + raw outputs: `/tmp/v28_team/locomotion/` (`urdf_com.py`, `tracking_analysis.py`, `tcp_lpy_distribution.py`, `train_rew_terms.py`, `*.txt`). Labels: **INSPECTED** / **COMPUTED** / **PROPOSAL**.

## 0. Answer

**Replacing A2_Base is not necessary for v28.** (i) The asset/posture change stays far inside the current policy's training distribution (COMPUTED §2): +0.754 kg vs +[0,5] kg trunk-mass randomization, whole-robot CoM shift ≤ 2.2 mm vs ±100 mm CoM randomization; the current policy has walked v1–v27 at a folded posture (TCP l≈0.16 m) farther from its Stage1 hold pose (l≈0.37) than the v28 posture (l≈0.33). (ii) Locomotion quality does matter (sim2sim r22 `BASE_GAIN_CAUSAL`; Isaac free-walk realized/command slope ≈0.5; base penalties 22–29 % of negative reward), so a better base is worth pursuing — but the candidate does not exist: the LMP `44:50` change is syntax-checked only, untrained; the Stage2 exporter writes `.npz`, not TorchScript; its metadata carries stale sphere-center constants; and DoorDog's free-walking TCP (l 0.14–0.33 m) is outside the Stage2 arm-goal box (l ≥ 0.4) in 97–100 % of stage 0/1/5 steps, so the new input slot would be OOD exactly where locomotion matters. **Recommend A** (keep current A2_Base, add a locomotion gate on the new asset), with the swap pre-registered for v29 (C) under §4.3; **B** only if a policy passing G0 arrives before v28 wave-A.

## 1. Interface contract (INSPECTED)

**Frame (54-D × 30 = 1620).** `gr00t/rl/envs/base_task/a2_base.py:1497-1509`: `[0:3]` projected gravity, `[3:15]` leg pos−default (policy leg order), `[15:27]` leg vel×0.05 (:297), `[27:39]` last leg action, `[39:44]` physical command×`[2,2,0.25,1,1]` (:1378-1389), **`[44:50]` `_get_a2_arm_command_obs` = zeros (:1391-1398)**, `[50:52]` `rpy[:,0:2]` (:1400-1401), `[52:54]` gait clock (:1434-1442). History shift/first-frame fill :1511-1531; dims asserted against metadata :20-37 (`policy_metadata.json:6-33`). Trainer: `gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:3455-3484` clones `a2_base_obs`, **overwrites the last frame's `[39:44]` with the current Teacher command**, runs the TorchScript model `(N,1620)→(N,12)`; `[44:50]` is untouched, so a state slot can be filled by the env. Load: `:4343-4431` (`policy_path` default `./gr00t/rl/data/policies/A2_Base/policy.pt`, `torch.jit.load`, frozen); configs `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml:35-47`, `gr00t/rl/config/env/door_open_a2_base.yaml:93-123`.

**Command = `[vx, vy, yaw_rate, body_pitch, body_roll]`** (`a2_base.py:409-414`). `a2_base.py:1193-1206`: `raw[:3]×0.25`, `raw[3:5].clamp(−1,1)×0.4` (pitch/roll always ≤ ±0.4 rad); `clip_homie_command: True` clips velocities to ±0.5 m/s, ±0.5 rad/s (env yaml :266-269; `a2_base.py:254-269, 1207-1212`). `penalty_base_command_limit = Σ(unclipped−clipped)²` (:1285-1289; scale −1, `reward_door_open_a2_base.yaml:93`). Teacher-facing `a2_base_command` zeroes `[:3]` when ‖v‖<0.1 (:1318-1321; not the A2_Base frame). Pitch/roll sign: LMP `desired_body_pitch_roll_quat` uses `(−pitch, −roll)` (`LMP…/mdp/utils.py:14-48`), DoorDog `orientation_control` same formula (`door_open_a2_base.py:17839-17849`) → positive command = negative Euler angle (traces confirm, slopes −0.4…−0.9). `leg_action_scale 0.25` asserted = `robot.control.action_scale` (:172-177; `a2_piper.yaml:170`); `use_default_offset` required (:170-171); leg order asserted (:163-169).

**LMP new `44:50` (worktree diff).** `lmp_manager_env_cfg.py:608-616` → `gripper_position_observation(arm_body6_to_gripper, tcp_offset_local=(0,0,0.105))`; `mdp/observations.py:318-337` = `ee_lpy_in_base_yaw(value_ranges=None, stage_command_name=None)` + 3 zeros; `:289-315`: `TCP_w = body_pos_w + R_body·(0,0,0.105)`; `center_w = (root_xy_w + R_yaw(root)·(cx,cy), z_world)`; `rel_b = R_yawᵀ(TCP_w−center_w)`; `l=‖rel_b‖`, `pitch=atan2(z,hypot(x,y))`, `yaw=atan2(y,x)` (`mdp/utils.py:114-120`; yaw-only frame :8-12,59-61; center :69-99). **Code constants** `sphere_center=(0.145,0.0)`, `sphere_center_z=0.704` **world-fixed** (`lmp_manager_env_cfg.py:82-83`; changed from 0.135/0.687 in LMP `943f3ac`, 2026-06-09). Raw m/rad, no normalization, no hybrid gating. **Stale**: `export_stage2_policy.py:311-324` and `docs/reference/observations/contract.md` ("Dog Current Gripper Position Contract") still say 0.135/0.687 → fix before export. Status `docs/memory/observations/DONE.md` (2026-09-09): "AST syntax PASS；未运行仿真、训练或新增测试".

**Export.** Current `policy.pt` = TorchScript `latent=adaptation(obs); action=actor(cat(obs,latent))`, identity normalizer (`docs/reference/training/dog_policy_export.md:40-47`). `export_stage2_policy.py:18,554` writes `stage2_policy.npz + .json` → not loadable by `torch.jit.load`; the Owner must use `export_dog_policy.py` on the Stage2 run's `checkpoints_dog` (or DoorDog adds an npz loader).

**DoorDog changes for the new policy** (obs_dim 1620, action 12, TorchScript signature unchanged):

| # | Change | Where |
|---|---|---|
| 1 | Replace zeros with TCP-LPY writer: `arm_body6_to_gripper` pose (already `end_effector_pos/rot`, `legged_robot_base.py:177-178`, `a2_piper.yaml:28`), offset **0.105** (not DoorDog's 0.085, env yaml :133), center `root_xy+R_yaw·(0.145,0)`, `z=0.704+ground_height(0.0)` (:1310-1312), yaw-only, spherical, 3 zeros | `a2_base.py:1391-1398, 1506` |
| 2 | Typed metadata field `obs.slot_44_50` (`zeros` vs `gripper_tcp_lpy_v1` + constants); loaders validate, fail fast | `a2_base.py:20-37`, `ppo_trainer_a2_base_api.py:483`, `distill_trainer_a2_base_api.py:185` |
| 3 | New dir `gr00t/rl/data/policies/A2_Base_v2/`; `policy_path/metadata_path` | `door_open_a2_base_lstm.yaml:38-39`, `door_open_a2_base.yaml:95`, v28 ablation yamls |
| 4 | Smoke: also write `[42:44]` (today only `[39:42]`, :542) and `[44:50]`; headless/64-env/scripted commands/metrics | `smoke_a2_base_flat_walk.py:528-548` |
| 5 | Unit test writer == LMP formula, flat root z 0.55: old default→(0.1956, 0.7238, 0.1594); v28 posture→(0.3325, 1.1530, 0); Stage1 hold→(0.3693, 0.3164, 0) (COMPUTED) | new test |
| 6 | sim2sim MuJoCo 54-D builder (zeros at 44:50) | other lane |

DoorDog has no LPY equivalent today (`tcp_to_handle_pos`/`gripper_handle_transform` are handle-relative, offset 0.085).

## 2. Training-distribution compatibility (INSPECTED + COMPUTED)

Provenance: `policy_metadata.json:234-236,108` → LMP run `stage1_locomotion_a2_piper/2026-06-05_16-12-09`, iter 2000, exported at `a96f071`. Its final log metrics are **0.625 / 0.563** (lin-vel/yaw, `windows.csv` 1801–2000) — the *worse* Stage1 run; the Owner's 0.434/0.480 is the un-exported 06-04 run. Versus the deployed run, Stage2-20k (0.473/0.457) is −24 %/−19 % on the same log metric (not a same-condition eval, `summary.md` "相比 Stage1…").

Stage1 (`lmp_manager_env_cfg.py`): arm **fixed** at `[0,1.48,−0.63,−0.84,0,1.57]` (:276-283; wrapper zeroes arm actions outside hybrid, `runners/dual_policy_wrapper.py:261-263`), reset jitter ±0.1 rad leg+arm (:878-889); pitch/roll uniform ±0.4 (:494-497; `dual_policy_plan_command.py:125-139`); vx∈[−1,1], vy∈[−0.5,0.5], wz∈[−1,1], 10 % standing (:479-486); DR friction 0.3–3.0, PD ±20 %, **trunk mass +[0,5] kg, trunk CoM ±0.1 m xyz, gripper +[0,0.2] kg**, pushes ±0.3 m/s / 8 s (:908-1007); dt 1/200, decimation 4 (:1421-1424) = DoorDog 0.02 s. Stage2: same velocity sampler (`dual_policy_plan_command.py:27`), pitch/roll from the arm plan, pushes off, arm goals l∈[0.4,0.8], p∈[−1,1], y∈[−1.2,1.2] (:95-97). DoorDog trains with `NO_domain_rand` (mass/CoM off, `NO_domain_rand.yaml:21-29,58`).

Asset: LMP `resources/A2_Piper/a2_piper.urdf` ≡ DoorDog `gr00t/rl/data/robots/A2_Piper/a2_piper.urdf` (sha256 `d02cdac…`), 44.741 kg. v28 `a2_piper_vpiper_final_20260906/a2_piper.urdf`: 45.4948 kg (+0.7538: vpiper_main 0.3107 @ (0.143,0,0.092), support 0.1056, plate 0.3375), `arm_j0` z 0.154→0.14743 (−6.57 mm).

| Posture (legs 0/0.5/−1) | asset | robot CoM_trunk x / z [m] | TCP(0.105) x / z | LPY (code center, root z 0.55) |
|---|---|---|---|---|
| old default `[0,0,0,0.25,0.5,1.57]` | v27 | +0.0020 / +0.0099 | 0.290 / 0.284 | l 0.196, p 0.72, y 0.16 |
| old default | v28 | +0.0042 / +0.0113 | 0.290 / 0.277 | l 0.191, p 0.70 |
| **v28 `[0,0,0,0,−0.44,1.57]`** | **v28** | **+0.0041 / +0.0130** | 0.280 / 0.451 | **l 0.327, p 1.14, y 0** |
| Stage1 hold | v27 | +0.0168 / +0.0169 | 0.496 / 0.269 | l 0.369, p 0.32 |

Asset-only CoM shift ≈ +2.2 mm x / +1.4 mm z; posture-only ≈ −0.1 / +1.7 mm; all ≪ randomization ⇒ **v28 asset+posture does not leave the current policy's distribution**.

## 3. Is locomotion a bottleneck? (INSPECTED / COMPUTED)

**(a) sim2sim (MuJoCo-vs-Isaac experiments, not policy comparisons).** `logs_eval/sim2sim/depthadd_v3_20260904/R22/STANCE_ORIGIN.md`: "Decision: `STANCE_FROM_BASE_TRACKING` … stage0-to-1 forward displacement is MuJoCo=0.359108 versus Isaac=0.183543 m". `R22/REPORT.md`: lane `d` (stage 0–2 forward gain 0.7) **`BASE_GAIN_CAUSAL`, st5 30→61, McNemar p=3.0e-4**; lane `a` `FRAME_CONTACT_CAUSAL` 30→288. `R22/PLANNER_REVIEW_R22_20260905.md:25`: "MuJoCo 横向命令 +0.34 m/s 实现 0.02 m/s". `SIM2SIM_FIX_SESSION_HISTORY_20260901.md:705`: "自由行走 stage 0 两侧横向跟踪相当（斜率 0.23/0.28）；握把手 stage 3 Isaac cmd vy +0.134→real +0.154 … L1 +0.240→+0.012"; `:741`: "L1 Stage3 body vy 命令/实现 p50 0.2437/0.01118，Isaac 0.1342/0.1287". `memory/a2-piper/sim2sim-r7-stage5-push/description.md:16`: "locomotion tracking ratio 0.69 vs Isaac ~0.70". Reading: stage-5 arrival is sensitive to how the base realizes stage 0–2 commands; the demonstrated lever is a plant/gain mismatch.

**(b) Isaac traces (COMPUTED).** `logs_eval/base_v27/v27_bilateral_hardening_20260905/wave_a/step3000/C_S21/nominal/{left,right}/stage2_5_step_trace.json` (19 996 / 20 964 records) hold `physical_base_command[5]` (post-clip), `base_lin_vel/base_ang_vel[3]` (body, `legged_robot_base.py:153-156`), `root_roll/pitch`, `post_delta_post_warp_base_action[5]`, `arm_joint_pos`, `root_pos_w/quat_w`; stages 2–5 only. Stage 0–1 exists only in `DoorDog-A2_Piper_sim2sim/logs_eval/sim2sim/depthadd_v3_20260908/R30/source_eval/stage0_1_step_trace.json` (Isaac, **Student**, 16 envs; world→body rotation verified vs `base_lin_vel` to 2.6e-7).

| lane / stage | n | \|e_vx\| p50/p95 | \|e_vy\| | \|e_wz\| | \|e_pitch\| | vx at clip | pitch at ±0.4 | slope vx/vy/wz |
|---|---|---|---|---|---|---|---|---|
| LEFT s2 | 925 | 0.107/0.414 | 0.150/0.369 | 0.172/0.501 | 0.083/0.331 | 20 % | 0 % | 0.23/−0.39/1.34 |
| LEFT s3 | 2964 | 0.393/0.587 | 0.325/0.715 | 0.509/1.076 | 0.203/0.380 | **100 %** | 61 % | 0.20/−0.15/0.55 |
| LEFT s4 | 4683 | 0.079/0.236 | 0.375/0.610 | 0.399/0.937 | 0.216/0.504 | 96 % | 21 % | 0.99/0.05/0.42 |
| LEFT s5 | 11424 | 0.064/0.179 | 0.389/0.696 | 0.323/0.684 | 0.256/0.469 | 100 % | 56 % | 1.10/0.04/0.24 |
| RIGHT s2 | 885 | 0.114/0.320 | 0.103/0.299 | 0.106/0.331 | 0.170/0.389 | 21 % | 3 % | 0.47/−0.24/−0.24 |
| RIGHT s3 | 2798 | 0.260/0.368 | 0.247/0.722 | 0.272/0.682 | 0.183/0.349 | 100 % | 19 % | 0.50/0.11/0.55 |
| RIGHT s4 | 8060 | 0.067/0.220 | 0.424/0.765 | 0.299/0.814 | 0.155/0.450 | 99 % | 48 % | 0.86/−0.11/0.58 |
| RIGHT s5 | 9221 | 0.045/0.134 | 0.365/0.726 | 0.247/0.694 | 0.205/0.512 | 100 % | 57 % | 1.02/0.02/0.15 |
| R30 Student s0 (free walk) | 904 | 0.209/0.540 | 0.201/0.578 | 0.221/0.677 | 0.290/0.504 | 56 % | 39 % | **0.54/0.47/0.76** |
| R30 Student s1 | 963 | 0.113/0.391 | 0.110/0.440 | 0.143/0.515 | 0.077/0.306 | 16 % | 34 % | 0.58/−0.08/0.45 |

m/s, rad/s, rad; slope = realized/command LS through origin (|cmd|>0.05). The Teacher pins vx at +0.5 in ~100 % of stage 3–5 steps (raw |a₀|>2 same share), vy/wz at clip 15–47 %, pitch at ±0.4 in 19–61 %; stage 2 is 53–57 % standing commands. Lateral/yaw commands are essentially unrealized under door contact (slopes ≈0); free walking realizes ~half of vx/vy.

**(c) Reward income** (`logs_rl/by_batch/base_v27/v27_bilateral_hardening_20260905/train/*/runtime.log`, "Mean episode rew_*" as logged, mean of last 50 iterations; scales `reward_door_open_a2_base.yaml:23-33,50,82,93,96`):

| term (scale) | SK_S211_r1 @6000 (goal 0.60) | SK_S211_r1 @3000 (goal 0.00) | C_S21 @3000 (goal 0.61) |
|---|---|---|---|
| penalty_not_standing_still (−15) | −0.164 | **−0.457 (20.5 % of negatives)** | −0.171 |
| penalty_base_command_limit (−1) | −0.120 | −0.015 | −0.134 |
| orientation_control (−5) | −0.246 | −0.158 | −0.231 |
| penalty_base_roll_pitch_l2 (−2) | −0.077 | −0.001 | −0.029 |
| penalty_standing_still (−1) | −0.0005 | 0 | 0 |
| face_door (−1) / creep (−1.5) | −0.018 / −0.006 | −0.110 / −0.006 | −0.019 / −0.005 |
| **base-behaviour sum** | **−0.631 = 22 % of negatives, 7.8 % of positive (8.09)** | −0.748 = 34 % / 11 % | **−0.589 = 29 % / 12 % (positive 4.91)** |

The Teacher pays ~0.36/unit continuously for saturating vx and for unrealized pitch — real, but below `penalty_upper_body_non_gripper_deviation_l1` (−0.97/−0.52) and termination.

## 4. Decision analysis (PROPOSAL)

**(i) Distribution — fails.** §2: mass/CoM changes are 1–2 orders below LMP randomization; the arm enters the current policy only through dynamics (44:50 is zero), and it already operates folded. No "necessary" case.

**(ii) Tracking↔grasp — real, indirect.** r22 shows stance/stage-5 sensitivity to base forward tracking (p=3e-4) and Isaac free-walk slope ≈0.5 leaves headroom; but the v28 Teacher is retrained on whatever base it gets, so the gain is staging precision and ≤ 8–12 % of income, not a known success delta. The LMP gain (−24 %/−19 % vs the deployed run) is a training-log metric.

**(iii) Coupling.** v28 already loses attribution to v27; a gated swap adds little attribution cost but real schedule risk — nothing to gate yet.

**(iv) Distribution for the new policy.** Velocity ranges cover vx=0.5, but the Teacher's joint regime (vx clip + pitch ±0.4 + sustained door forces) is in neither stage (pushes off in Stage2). Slot 44:50 (COMPUTED, `tcp_lpy_distribution.txt`): stages 2–4 sit inside the Stage2 box (l 0.47–0.73, p 0.14–0.50; 0–17 % outside), but **stage 0/1/5 and the v28 posture are outside** (l 0.14–0.33 < 0.4; v28 p≈1.07–1.15 > 1.0; 97–100 % of steps) → OOD in the walking phases unless LMP adds folded/DoorDog postures to Stage1-hold or Stage2 sampling.

**Recommendation: A (+ pre-registered C).** Keep `gr00t/rl/data/policies/A2_Base/policy.pt` in v28 behind gate **G0-loco-current** (§4.3 with the current policy on the v28 asset+posture; baseline = same script on the v27 asset; pass: 0 falls/64 envs, block p50 |e| ≤ 1.15× baseline, slope(vx@0.5) ≥ baseline−0.05). Swap slot at **v29** (or an opt-in v28 side-branch only if delivered before wave-A) under **G0-loco-swap**. Deciding evidence: A holds while §2 holds; B needs the deliverables below plus a G0-swap pass; C = A plus a dated swap slot.

**Owner deliverables for B/v29:** TorchScript `policy.pt` via `export_dog_policy.py` from the Stage2 `checkpoints_dog` (or npz loader), `policy_metadata.json` with a `gripper_position` field holding the *trained* constants (center xy/z, TCP offset, body) + LMP commit hash, Stage1/Stage2 iteration counts, statement whether training covered TCP l∈[0.14,0.35]/pitch ≤1.15 rad; fix `export_stage2_policy.py:319-320` and `contract.md` (0.135/0.687 → trained values).

### 4.3 Pre-registered acceptance for any A2_Base swap

1. **Interface test (CPU, <5 min).** `torch.jit.load` CPU; metadata: `dog_frame_dim 54`, `history_length 30`, `flattened_dim 1620`, action 12, `leg_joint_names` unchanged, `leg_action_scale 0.25`, `use_default_offset true`, `delay [0,1]`, latent 25, `slot_44_50` constants; `zeros(1,1620)`→finite `(1,12)`, `randn(64,1620)`→`(64,12)`, eager-vs-scripted diff 0; LPY writer vs LMP formula on the three postures of §1 row 5 (tol 1e-3); fail fast.
2. **64-env scripted-command smoke (GPU, ~10 min).** Extend `smoke_a2_base_flat_walk.py` (headless, `--num-envs 64`, `--usd-file …/a2_piper_vpiper_final_20260906/a2_piper.usd`, `--arm-posture`, `--command-script`, `--metrics-json`; today it requires GUI cuda:0, :180-185); flat plane, no door, arm PD-held. 6-s blocks, seeded, identical for every policy: stand; vx 0.25; vx 0.5; vy ±0.25; wz ±0.5; vx 0.5+pitch −0.32 (stage-3 mean); vx 0.5+pitch ±0.4; roll ±0.2; Teacher replay (per-step `physical_base_command` from a C_S21 lane, stage 2–3). Postures {v28 default, Stage1 hold, stage-2-like l 0.6/p 0.35}. ≈60 s × 64 envs ≈ 3 000 policy steps.
3. **Metrics.** Body-frame |e| p50/p95 per block (vx, vy, wz), pitch/roll error with Euler = −cmd, realized/cmd slope, falls (root z < 0.3 or |roll|,|pitch| > 0.9), leg action rate, base height, per-posture deltas.
4. **Pass (swap).** 0 falls; every block/posture p50 and p95 ≤ current policy on the identical script and asset; slope(vx@0.5) ≥ 0.8, slope(vy) ≥ 0.6, slope(wz) ≥ 0.7; degradation at v28/folded postures vs hold posture ≤ 20 % (tests 44:50 OOD); Teacher-replay p50 |e_vx| ≤ current. **Pass (current, v28 gate):** as in the recommendation.

Not run: no GPU/Isaac, no LMP training/export, sim2sim builder untouched. No durable-memory candidate (planning only); artifacts under `/tmp/v28_team/locomotion/`.
