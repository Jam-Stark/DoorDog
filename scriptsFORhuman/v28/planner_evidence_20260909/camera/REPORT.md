# v28 CAMERA lane report (read-only; all outputs under /tmp/v28_team/camera/)

Evidence levels: **INSPECTED** = read from source/config; **STATIC/COMPUTED** = CPU geometry on URDF meshes / archived v27 traces (no Isaac, no rendering, no hardware). Numbers are *computed* unless marked *nominal*. Package = `/home/baoquanc/workspace/DoorDog-A2-Piper-v13-student-distillation-20260717_2103/camera_setup/Vpiper-Plate-Dual-D435i` (PKG). Precheck = `scriptsFORhuman/v28/v28_u3f0_geometry_precheck.py` (PC). Scripts: `t1_occlusion.py`, `t2_make_variants.py`, `t3_coverage.py`+`t3_aggregate.py`, `t4_clearance.py`+`t4_diag.py`; raw outputs `t1/`, `t3/<variant>/`, `t3/t3_tables.md`, `t4/`, JSONs `variants/`. Package code was copied to `pkgcode/` with `BUNDLE` re-pointed (PKG `code/geometry.py:9`); numba cache in `numba_cache/`; nothing written into any worktree. Python: `anaconda3/envs/isaaclab/bin/python` (numpy 1.26, scipy 1.15.3, trimesh 4.5.1, numba 0.59.1; CPU only).

## 1. Finger / gripper occlusion (G0) — feasible, run (STATIC/COMPUTED)

Tooling found and reused: PKG `code/geometry.py` (`Robot` URDF FK 44–65, trimesh visual meshes 66–79, numba BVH ray cast 100–152), `code/evaluate_forward.py` (finger surface samples 44–48, 160×90 ray lattice 40–43), `code/build_u3_forward.py::make_variant` (17–37; tilt = rotation of the housing about its bar axis = image‑x, `forward=[cos a,0,-sin a]` line 21), gripper meshes PKG `robot/meshes/piper/link7.STL`, `link8.STL`, `gripper_base.STL` (same sha as the package QA; PKG `robot/a2_piper.urdf` differs from `gr00t/rl/data/robots/a2_piper_vpiper_final_20260906/a2_piper.urdf` only by the three fixed-link `<inertial>` blocks (diff lines 961–965, 1189–1197, 1207–1219) → kinematics identical, `arm_j0` z 0.147431554755). Posture `[0,0,0,0,0,1.57]`, `arm_j7=+o, arm_j8=-o` (URDF limit 0.035; inner-face gap = 2·o, measured from mesh: link7 y_max = −0.020 at o=0.020). Targets: 100 mm bar along F±X at F+Z 0.085 (21 pts), 1500 area-weighted surface samples per finger (pad = inner face, z_F 0.075–0.130; tip = last 10 mm, z_F max 0.1358), 212×120 ray lattice to 3 m. Occluders: whole robot except legs + design-envelope brackets + other housings (as in package). Runtime 38 s.

| θ | o (m) / gap | stream | bar in‑frustum+MinZ | bar visible (ray) | bar centre row | f7 pad / f8 pad vis | f7 tip / f8 tip vis | gripper share full / lower‑half | supports share | hit<MinZ |
|---|---|---|---:|---:|---:|---|---|---|---:|---:|
| 35 | 0.020 / 40 mm | RGB | 0% | 0% | 1.26 | 0/0% | 1/13% | 2.7/5.3% | 0 | 0 |
| 35 | 0.020 | depth | 0% | 0% | 1.02 | 0/0% | 0/13% | 3.8/7.7% | 1.4% | 1.6% |
| 40 | 0 / 0 | depth | 100% | 52% | 0.92 | 0/0% | 0/13% | 4.2/8.4% | 3.7% | 5.0% |
| 40 | 0.020 / 40 mm | RGB | 0% | 0% | 1.10 | 1/0% | 1/13% | 5.0/10.1% | 0 | 0 |
| 40 | 0.020 | depth | 100% | 29% | 0.92 | 1/0% | 0/13% | 5.8/11.5% | 3.7% | 5.0% |
| 40 | 0.035 / 70 mm | depth | 100% | 24% | 0.92 | 6/0% | 0/13% | 7.0/14.1% | 3.7% | 5.0% |
| 45 | 0 | RGB / depth | 100 / 100% | 43 / 52% | 0.97 / 0.82 | 0/0% | 0/13% | 5.9/11.8 · 5.7/11.5% | 0 · 6.7% | 0 · 8.9% |
| 45 | 0.020 / 40 mm | RGB / depth | 100 / 100% | 29 / 29% | 0.97 / 0.82 | 1/0 · 2/0% | 1/13 · 0/13% | 8.4/16.9 · 7.1/14.3% | 0 · 6.7% | 0 · 8.9% |
| 45 | 0.035 / 70 mm | RGB / depth | 100 / 100% | 24 / 24% | 0.97 / 0.82 | 0/0 · 8/0% | 0/13 · 0/13% | 11.3/22.2 · 8.3/16.4% | 0 · 6.7% | 0 · 8.9% |

Full table `t1/t1_occlusion.md`, grids `t1/*_ray_grid.npz`. Findings:

1. **Tilt changes framing, not occlusion.** The tower sits on F+Y, which is the finger opening axis (`arm_j8` = +y finger). The depth optical centre is at F (0.017, 0.174, 0.022) for θ=40; the ray to the TCP crosses the upper finger's outer face (y = o+0.0265) at z_F≈0.068, inside the finger span 0.059–0.136 → TCP/lever centre blocked by `arm_body8` at every θ and opening (blockers column: `arm_body6_to_gripper, arm_body8`). Only the lever ends beyond the 56 mm finger width are visible: 52% (o=0) → 29% (o=0.020) → 24% (o=0.035) of the bar length; opening the gripper moves the upper finger closer to the camera and hides more.
2. Finger pads 0–8% visible (inner faces face each other, camera is on the axis). Upper fingertip: 13% of tip samples (outer face + distal edge) visible in both streams at θ≥35; lower fingertip 0–1%. **"Both fingertips visible" is not achievable by tilt alone.** Required lateral tower offset along F x to see the TCP past the upper finger (computed, same-height camera): ≥0.108 m at o=0.020, ≥0.081 m at o=0.035, ≥0.19 m at o=0.
3. Gripper body share of the image (o=0.020): RGB 5.0% (θ40) / 8.4% (θ45), lower half 10.1% / 16.9%; depth 5.8% / 7.1%, lower half 11.5% / 14.3%. The gripper base is at optical z 0.09–0.13 m, below the depth MinZ 0.105 (`hit<MinZ` 5.0% / 8.9% of depth pixels).
4. **Own bracket in the depth FOV:** the design-envelope `wrist_u3_upright` (8×8 mm beam, F x −4.75 mm, vertical in B so 5° off F y; top at F y≈0.166) enters the right/lower part of the depth image at θ≥35 (rows 0.63–1.0 × cols 0.81–1.0 at θ40 = 3.7%; 6.7% at θ45; right_ir 0.8% / 2.9%; RGB 0%) at 2–4 cm range. Cause: the depth imager is 17.5 mm along the bar from the housing centre while the beam is 4.75 mm the other way. To be checked against the real bracket CAD.

G0 spec (rerun): inputs = variant JSON, PKG robot URDF+meshes, posture `[0,0,0,0,0,1.57]`, o ∈ {0, 0.013 (lever r=0.013 closed), 0.020, 0.035}; tool `t1_occlusion.py`; pass = bar proxy visible ≥ 40% of its length in **depth** and ≥ 25% in RGB at grasp opening, upper fingertip outer face ≥ 10% in depth, supports share 0% in depth/right_ir. Under the Owner's literal wording (both fingertips) the check fails for all θ.

## 2. Candidate mount JSONs (STATIC/COMPUTED) — `variants/`

`U3_F35/40/45.json` = `make_variant(U3_V_previous, TF, pid, θ)`; `make_variant(…,0)` reproduces shipped `U3_F0.json` wrist transforms to 0.0; base rebuild (rpy −32/−12) reproduces cameras and `base_*_saddle/post/rail` brackets to 0.0. Sign check: TCP (F+Z 0.085) RGB row fraction 3.44 (F0) → 1.105 (F40) → 0.966 (F45); depth 2.54 → 0.919 → 0.823 (decreasing ⇒ toward gripper). Rotation is about the **housing centre** (bar axis); vs the sweep wrapper (rotation about the depth optical centre) rotations agree to 2e‑6°, optical centres differ 5.7 mm (θ40) / 6.4 mm (θ45), hence small differences to the earlier numbers (e.g. RGB TCP row 1.124→1.105).

| variant | camera | xyz (parent, mm) | rpy_deg Rz·Ry·Rx (package convention) | optical axis in B at reference |
|---|---|---|---|---|
| U3_F0 (shipped) | wrist (F) | [−0.143, 179.316, 15.677] | [−0.0067, −85.0036, −89.9475] | [1, 0, 0] |
| U3_F35 | wrist | same | [−0.0009, −50.0036, −89.9534] | [0.819, 0, −0.574] |
| **U3_F40** | wrist | same | **[−0.0008, −45.0036, −89.9535]** | [0.766, 0, −0.643] |
| **U3_F45** | wrist | same | **[−0.0008, −40.0036, −89.9536]** | [0.707, 0, −0.707] |
| `*_B12` | base_left/right (trunk) | [25, ±155, 190] | **[0, −12, 0]** both | [0.978, 0, 0.208] |
| `*_B15` | base_left/right | same | **[0, −15, 0]** both | [0.966, 0, 0.259] |
| shipped | base_left / base_right | same | [0, −32, 0] / [0, −12, 0] | [0.848,0,0.53] / [0.978,0,0.208] |

Negative package pitch = optical axis tilted **up** (assumption: Owner's "12–15°" means the current right-camera up-tilt). Files: `U3_F40.json`, `U3_F45.json` (base unchanged), `U3_F{40,45}_B{12,15}.json`, plus `U3_F35*.json`, `U3_F0_B{12,15}.json`, `U3_F40_B20.json` (sensitivity), `variants_summary.json`. Each carries `v28_variant` metadata and `hardware_status: PLANNING_CANDIDATE_v28`. Wrist brackets (saddle/short head) are regenerated per θ; the F0 reference uses `reset_posture_hint_rad` j5 = −0.44 / −0.52 (Owner values; −0.35 for θ35 by the same −(θ−15°) rule).

## 3. Three-camera coverage (STATIC/COMPUTED; PC conventions: pinhole + MinZ, base arm-capsule screen, no mesh/panel occlusion)

Runs: 6+1 variants × cells `C_S2`,`C_S21` (66,688 trace rows; FK check vs exported flange p50 5e‑8 m); synthetic Stage0/1 with `DEFAULT_ARM_Q=[0,0,0,0,−0.44|−0.52,1.57]`. Base results do not depend on θ, wrist results do not depend on base tilt. Full tables `t3/t3_tables.md` (A–F).

**A. Handle visibility, per lane/stage** (values asym/B12/B15/B20; W = wrist th40/th45):

| lane | stage | n | L‑RGB clear | R‑RGB clear | L‑depth | R‑depth | W‑RGB | W‑depth |
|---|---|---:|---|---|---|---|---|---|
| C_S2/left | 2 | 1644 | 52/53/53/52 | 60/60/60/60 | 100/100/100/100 | 100/100/100/100 | 79/99 | 100/100 |
| C_S2/left | 3 | 8066 | 22/22/23/23 | 17/17/17/17 | 100/100/100/100 | 100/100/100/100 | 12/45 | 98/100 |
| C_S2/left | 4 | 11898 | 48/30/**39**/47 | 14/14/**21**/36 | 96/74/**87**/97 | 73/73/**86**/98 | 33/90 | 95/95 |
| C_S2/right | 2 | 1653 | 93/94/93/93 | 49/49/49/49 | 100/100/100/100 | 100/100/100/100 | 87/100 | 100/100 |
| C_S2/right | 3 | 7602 | 12/**85**/85/79 | 47/47/47/40 | 53/**100**/100/100 | 100/100/100/100 | 16/65 | 100/100 |
| C_S2/right | 4 | 6532 | 11/**53**/53/48 | 39/39/38/32 | 51/60/62/64 | 46/46/46/46 | 4/68 | 100/100 |
| C_S21/left | 3 | 3843 | 5/4/5/5 | 2/2/2/2 | 100/100/100/100 | 100/100/100/100 | 14/34 | 88/100 |
| C_S21/left | 4 | 1402 | 81/46/**69**/81 | 51/51/**68**/75 | 100/99/100/100 | 99/99/100/100 | 44/98 | 100/100 |
| C_S21/right | 3 | 3971 | 13/**89**/89/79 | 62/62/62/51 | 61/**100**/100/100 | 100/100/100/100 | 17/72 | 100/100 |
| C_S21/right | 4 | 4492 | 13/**62**/62/55 | 70/70/70/63 | 67/84/84/85 | 75/75/75/74 | 22/63 | 99/99 |

Stage 5: handle ≤ 30% for every camera/variant; W‑depth TCP 100% in all stages/θ (rigid). Door frame at z=1.0 (base RGB, handle-side jamb, asym/B12/B15/B20): left-door Stage 3 L cam 100/50/66/96, R cam 54/54/71/97; right-door Stage 3 L cam 38/72/72/71, R cam 100 all. Hinge-side jamb on right doors, L cam Stage 3: 28/93/93/93. **Doorway floor, floor+1 m and lintel are 0% for both base cameras in all stages for every variant** (lower FOV edge −17° at 12°, −14° at 15°; ground first visible ≥2.2 m ahead), except the asym L cam sees the lintel on right doors (88%/85% in Stage 3) — it looks over the handle. Wrist (θ40/θ45): RGB floor+1 m 27–84% / 21–94% in Stage 3–4 (100% in Stage 2); depth doorway floor ≤ 31/54% (Stage 2) and ≤ 13/40% (Stage 4).

**C. Mirror symmetry** (LEFT-door lane vs RIGHT-door lane, same camera role): mean |Δ| over 80 metric rows: asym 10.3 pp (max 88), B12 10.5 (max 86), B15 9.6 (max 86), B20 9.2 (max 76). The asym rig has camera-induced asymmetries: hinge-side depth handle Stage 3 100/53 (Δ47), hinge-side lintel 0/88; B12/B15 remove those (100/100, 0/0). Remaining Δ (e.g. handle-side RGB clear Stage 3 C_S21 4/62) comes from arm occlusion differences between left- and right-door trajectories, not from the cameras.

**D. Synthetic Stage 0/1** (LEFT door W 0.95, handle 0.90, trunk z 0.48, new reset posture; share of 9 poses): L‑RGB handle at 1.5 / 1.2 / 1.0 / 0.8 m: asym **0**/89/89/89 vs B12=B15 100/100/89/89 (asym L cam sees the lintel 100/78/22/0 instead); R‑RGB handle 100/100/100/89 all; base depth handle 100 everywhere; base doorway floor 0 everywhere. Wrist at reset posture (axis −14.75° θ40 / −15.16° θ45, origin B z 0.566): W‑RGB handle 100/100/100/89, W‑depth handle 100 all, W‑RGB handle-side jamb 100/100/89/89, W‑RGB doorway floor 11–22% at 1.5 m only, W‑depth doorway floor 100/33(θ40) 67(θ45)/0/0. B12 and B15 rows are identical in this table.

**Recommendation: base 15° up, both sides.** Versus 12°: +13 pp L‑depth handle and +9 pp L‑RGB clear in Stage 4 left doors (74→87, 30→39), +13 pp R‑depth (73→86), +16/+17 pp handle-side jamb in Stage 3 (50→66, 54→71), within 2 pp on right doors and identical in Stage 0–2; 12° gains only ≤3 pp floor+1 m in one cell. Both remove the asym rig's right-door deficits (Stage 3 L‑depth 53→100, L‑RGB clear 12→85). Sensitivity: 20° recovers Stage 4 handle-side coverage to the old 32° level (97–100% depth, 47–81% RGB) and Stage 3 jamb 76–97%, but costs the far camera on right doors (Stage 3 R‑RGB clear 47→40, L 85→79). Caveats: PC `W_est=2(|handle_y|+0.115)` (PC 262–265) underestimates door width (fitted W p50 0.957, §4) so jamb/lintel points are ~0.1 m too close to the centre; PC `piper_fk` uses `arm_j0` z 0.154 (PC 103) vs 0.1474 in the new asset (6.6 mm, negligible); panel/wall occlusion and stereo validity not modelled.

## 4. Tower–door clearance sweep (STATIC/COMPUTED) — feasible, run

Envelopes: PKG `robot/a2_piper_U3_F0_clearance_only.urdf` wrist collision boxes (lines 920–943: foot 40×4×24, upright 8×8×132, short head 8×8×16, saddle 22×80×4) + housing 25×90×25 at `T_parent_M`; for θ40/45 taken from `variants/U3_F{40,45}.json` (saddle/head regenerated), 992–1,016 surface points at 5 mm pitch (min distance = upper bound within ~2.5 mm). Door rebuilt in the trace's D frame from `gr00t/rl/isaac_utils/playground/env_rand/door.py` (INSPECTED): panel box half-thickness 0.02 at x=0 (391–400), hinge at (0.02, −side·W/2) (526–528), frames/covers x∈[−0.08,0.04] (323–389), lever/axle/hook (407–492; nominal L 0.125, r 0.013, axle 0.195, hook 0.05), H nominal 1.9 (lowest lintel). Door width **fitted per env** from the grasp-target trajectory (rms 0.2 mm; 383/383 envs; W p5/p50/p95 = 0.82/0.957/1.08; rotation sign confirms PC `rz(−side·hinge)`); lever half-length fitted 0.0627 (= nominal). Frames are the sampled export (dense 50 Hz Stage 2/3, 10 Hz Stage 4/5) → minima are upper bounds. `t4/t4_clearance.md`, `t4/t4_diag.json`.

| lane | stage | panel min / p5 (mm) F0 · F40 · F45 | panel <0 share F0/F40/F45 | handle min (mm) | frame min (mm) |
|---|---|---|---|---|---|
| C_S2/left | 2 | 111/133 · 108/132 · 108/132 | 0 | 35 | 119 |
| C_S2/left | 3 | 56/74 · 56/72 · 56/73 | 0 | 24–27 | 89 |
| C_S2/left | 4 | −20/40 · −20/39 · −20/38 | 3.7/3.7/3.7% | 23 | −31 (<1% frames) |
| C_S2/right | 2 | 124/139 · 121/137 · 121/137 | 0 | 41 | 125 |
| C_S2/right | 3 | 27/56 · 28/56 · 29/56 | 0 | 33 | 71 |
| C_S2/right | 4 | −20/−20 (all) | **65.7 / 64.5 / 64.2%** | 16 | 62 |
| C_S21/left | 3–4 | 61–65 / 75–99 | 0 | 27 | 120 |
| C_S21/right | 3 | 39/62 · 40/62 · 41/62 | 0 | 32 | 50 |
| C_S21/right | 4 | −20/−20 (all) | **41.7 / 41.5 / 41.3%** | −13 (lever/hook proxy, nominal dims) | 55 |
| all | 5 | −20 min, 0.1–1.5% frames | | | |

Diagnosis (`t4_diag.py`): the right-door Stage 4 penetrations occur **while holding the handle** (handle–TCP distance p50 0.029 m, all 128/128 and 62/63 envs, terminal `complete`), flange origin 117–141 mm in front of the panel, but `arm_j5` = 1.22 rad (p5=p50=p95; PiPER j5 limit) with `arm_j6` 0.5–1.3: the flange z-axis points ~39° down into the door and the tower axis (F+Y) has x-component 0.62–0.85 toward the panel (leans 38–58° from the panel plane) → the housing/saddle/upright pass through the panel 0.57–0.85 m from the hinge at z≈1.0 m (SDF saturates at −20 mm = beyond the mid-plane). Left-door Stage 4 penetrations (3.7%) happen after release (handle–TCP 0.17–0.62 m) while the arm swings past the panel. Stage 3 minima are 27–65 mm (housing), Stage 2 >100 mm. **θ is irrelevant to this (differences ≤3 mm, ≤1.5 pp):** the housing rotates about its own centre. The v27 right-door grasp posture is incompatible with any 180 mm tower on F+Y; the tower must be part of the v28 Teacher's collision model (or the posture constrained) or the real bracket will hit the door. Tower lean limit for a flange 0.13 m from the panel face: x-component < ~0.54 (≈33°).

G0 procedure: rerun `t4_clearance.py` on v28 traces (or in-env, §5) with the final CAD envelopes; pass = panel SDF ≥ 20 mm on 100% of Stage 2–4 frames on both sides at 50 Hz, frame ≥ 20 mm, no penetration in Stage 5 except after release with the arm retracted; report min/p1/p5 per stage/side as above.

## 5. Camera-motion telemetry for the Teacher (no rendering) — spec (INSPECTED sources)

Already in the env (`gr00t/rl/envs/door/door_open_a2_base.py`): flange body id via `robot.find_bodies("arm_body6_to_gripper")` (11673–11676); IsaacLab `ArticulationData.body_pos_w/body_quat_w/body_lin_vel_w/body_ang_vel_w` (`IsaacLab/source/isaaclab/isaaclab/assets/articulation/articulation_data.py` 1056–1076); trunk `root_pos_w/root_quat_w/root_ang_vel_w`, `arm_joint_pos/arm_joint_vel`, `gripper_joint_pos`, `tcp_to_handle_pos` already written per step into the Stage 2–5 trace (27701–27751; TCP FrameTransformer on `/Robot/arm_body6_to_gripper` with offset `a2_gripper_source_tcp_offset_z`=0.085, 29824–29827; capture 27790–27888; file `stage2_5_step_trace.json`, `ppo_trainer_a2_base_api.py:9785`); door panel/handle body poses `door_articulation.data.body_pos_w/body_quat_w` (10481–10494).

Computation (constants from the chosen variant JSON, fixed in F): `R_F_cam = T_parent_optical[:3,:3]` (depth stream), `R_W_cam = R(body_quat_w[flange]) @ R_F_cam`; optical axis `a = R_W_cam[:,2]`; elevation `asin(a_z)`; azimuth relative to the door `atan2` of `a` in the door root frame. Angular speed of a rigidly mounted camera = flange `body_ang_vel_w` (no finite differences): `|ω|`; axis sweep rate `sqrt(|ω|²−(ω·a)²)`; base cameras use `root_ang_vel_w`. Handle-in-wrist-frustum (geometric): `p_F = tcp_to_handle_pos + [0,0,0.085]`, `p_cam = inv(T_parent_optical) p_F`, pinhole with SDK K (424×240) and MinZ 0.105. j6 reversals: sign flips of `arm_joint_vel[5]` above 0.3 rad/s per second (replay dq6 p50 0.55–1.46, p95 1.7–3.2 rad/s). Tower–panel clearance: SDF of the 5 envelope boxes (F frame) vs the panel body box (0.02 × W/2 × H/2) using the panel `body_pos_w/quat_w` — exact per step, replaces §4's trace fit.

Proposed `a2_v28_camera` per-episode terminal dict (Stage 2–4 steps), reduced across episodes with `percentile()` in the v27 style (`scriptsFORhuman/v27/v27_reduce.py` 107–112, 236–283: flat snake_case with `_p50/_p95/_share` suffixes, `finite_number` validation 114–117, `require` 33; gates only in `passes_gate` 368–376):

| field | type | replay reference (θ40, Stage 2/3) | role |
|---|---|---|---|
| `wrist_cam_ang_speed_p50_deg_s`, `wrist_cam_ang_speed_p95_deg_s` | float | 71–112 / 159–403 | report |
| `wrist_cam_axis_sweep_p95_deg_s`, `wrist_cam_share_axis_sweep_gt_60` | float | 127–258 / 44–64% | report |
| `wrist_cam_axis_elev_p5_deg`, `_p50_deg`, `_p95_deg` | float | S3: −56…−39 / −37…−31 / −27…−22 | report |
| `base_cam_ang_speed_p95_deg_s` | float | 37–59 | report |
| `arm_j6_reversals_per_s`, `arm_j6_abs_dev_from_1p57_p95` | float | az-reversal proxy 2.5–12/s | report |
| `handle_in_wrist_depth_share_stage2_4`, `handle_in_wrist_rgb_share_stage2_4` | float | depth 0.88–1.0; RGB 0.04–0.92 (θ40) / 0.34–1.0 (θ45) | report; candidate gate after one wave (e.g. depth ≥ 0.9) |
| `wrist_tower_panel_min_clearance_m`, `wrist_tower_panel_penetration_step_share` | float | −0.02 / 0.65 (v27 right doors) | **gate candidate**: share == 0 if the tower is not in the collision model; report-only if it is |
| `handle_visible_upper_finger_only` (const from §1) | bool | true | documentation |

## 6. Integration notes and risks

- Rendering lives only in the student worktree: `gr00t/rl/simulator/isaacsim/native_d435.py` (RGB+depth `Camera` per role, `distance_to_image_plane`), `gr00t/rl/utils/d435_native_calibration.py::load_d435_native_rig`, `scripts/run_a2_d435_native_preview.py`, `config/exp/wbmanip/door_open_a2_d435_native_preview.yaml:34–37` (`calibration_dir: camera_setup/d435_native_calibration/20260907`, `layout_file: …/config/U3_F0.json`). Main repo `gr00t/rl/simulator/isaacsim/` has no `native_d435.py`; the Teacher needs nothing for rendering — only the FK telemetry of §5 (constants = one variant JSON) and, if the Owner wants the policy to respect the bracket, tower collision boxes in the asset (pattern: `a2_piper_U3_F0_clearance_only.urdf`; a HIGH_RISK asset/USD change).
- Student lane: `load_d435_native_rig` hard-fails unless `plan_id == "U3_F0"` (`d435_native_calibration.py:96–99`) and takes only the depth `T_parent_optical` as anchor (51–63). The variant JSONs use `plan_id` `U3_F40/…` → the loader check must be updated explicitly (keep fail-fast; do not accept arbitrary ids). Also `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml:176 usd_file: "A2_Piper/a2_piper.usd"` must point to the new asset for both lanes.
- Risks: (1) tower–panel conflict on right-door grasps (§4) — highest; (2) near-field TCP/pads/lower finger never visible from the F+Y tower (§1) — the near-field requirement needs rewording or a lateral tower offset ≥0.08–0.11 m; (3) `wrist_u3_upright` inside the depth FOV at θ≥35 (§1.4) — verify with real CAD; (4) depth MinZ 0.105 vs gripper at 0.09–0.13 m and D435 stereo accuracy <0.2 m not modelled; (5) PC W_est bias (§3 caveat) and no panel occlusion in coverage shares; (6) Stage 3 wrist RGB handle share only 12–17% (θ40) vs 34–72% (θ45) while depth is 88–100% for both — θ45 is the better wrist choice for RGB, at the price of 8.9% depth pixels below MinZ and 6.7% own-bracket pixels; (7) reset posture j5 −0.44/−0.52 is inside the PiPER j5 range (±1.22 observed in traces) — fine.

Not run: Isaac/rendering, hardware, any v28 trace. No durable memory candidate created; no stage artifact handoff. No writer/lease held.
