# v28 ASSET lane report — switch `A2_Piper/` → `a2_piper_vpiper_final_20260906/`

Evidence levels: **INSPECTED** = read from source/asset files on disk; **STATIC** = derived by CPU computation (no simulator); **INFERRED** = reasoning about PhysX/IsaacLab behaviour not executed here. Scratch outputs: `/tmp/v28_team/asset/` (`urdf_compare.txt`, `mount_clearance.{json,md}`, `com_shift.json`, scripts). No repo file was modified.

## 1. Asset-loading path (INSPECTED)

| Hop | File:line | Fact |
|---|---|---|
| exp | `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml:6,9` | `/simulator: isaacsim`, `/robot: A2_Piper/a2_piper` |
| simulator selection | `gr00t/rl/config/simulator/isaacsim.yaml:5` | `_target_: gr00t.rl.simulator.isaacsim.isaacsim.IsaacSim` — this, not `sim_type`, picks the backend |
| `sim_type` | `gr00t/rl/config/base.yaml:46` | `sim_type: isaacgym` is a **dead field**: no Python under `gr00t/` reads it (only resolved-config dumps echo it). Ignore it in v28 |
| robot asset cfg | `gr00t/rl/config/robot/A2_Piper/a2_piper.yaml:175-177`; `robot_base.yaml:63` | `urdf_file`, `usd_file`, `asset_root: "gr00t/rl/data/robots"` |
| consumption | `gr00t/rl/simulator/isaacsim/isaacsim.py:1261-1262,1271-1272` | `asset_path = robot_config.asset.usd_file`; `abspath(join(asset_root, usd_file))` (CWD-relative → repo root); `assert os.path.isfile` (fail-fast) |
| spawn | `isaacsim.py:1307-1312` | `sim_utils.UsdFileCfg(usd_path=..., activate_contact_sensors=True, rigid_props, articulation_props)`; the `UrdfFileCfg` path is commented out (`:1314-1341`). **`urdf_file` is never read at runtime** |
| self-collision | `isaacsim.py:1293` | `enabled_self_collisions = not bool(robot.asset.self_collisions)`; `self_collisions: 0` (`a2_piper.yaml:180`, exp `:109`) ⇒ **self-collision ON**. IsaacLab applies it on spawn (`IsaacLab/source/isaaclab/sim/spawners/from_files/from_files.py:340-341` → `schemas.py:107-170`), overriding the converter's `self_collision: false` baked into the USD (`a2_piper_vpiper_final_20260906/config.yaml:20`) |
| articulation | `isaacsim.py:1456-1461,1607` | `ARTICULATION_CFG.replace(prim_path="/World/envs/env_.*/Robot", spawn, init_state, actuators)` → `Articulation(...)` |
| contact sensor | `isaacsim.py:1577-1582,1609` | `ContactSensorCfg(prim_path="/World/envs/env_.*/Robot/.*")` — every rigid body under Robot, i.e. **30 bodies with the new USD** |
| API version | `isaacsim.py:16-19`, `gr00t/rl/simulator/isaacsim/.isaacsim_version` (`4.5`) | `isaaclab.*` namespace = local IsaacLab 2.3.2 (`IsaacLab/VERSION`) |

USD is **imported directly, not regenerated**. Mesh data is embedded (`configuration/a2_piper_base.usd` = 35.7 MB, no `.STL` strings inside; `a2_piper.usd` only references `configuration/*.usd`, `validation/usd_import_readback.json:8-14`). STL paths in the URDF matter only at conversion time. The `a2_piper.usd` + `configuration/` pair must move together.

## 2. Names the env depends on (INSPECTED) and index-shift analysis

| Consumer | File:line | Names | New URDF/USD |
|---|---|---|---|
| dof order + asserts | `isaacsim.py:2370,2427-2434`; `a2_piper.yaml:30-36` | 20 `dof_names` | unchanged (26 joints identical, `urdf_compare.txt`); readback 20 active joints |
| body list + asserts | `isaacsim.py:2372-2374,2430-2435`; `a2_piper.yaml:48-56` | 27 `body_names` | all 27 present; `find_bodies(names, preserve_order=True)` selects **by name** → `num_bodies` stays 27 and both asserts pass with a 30-body articulation |
| contact remap | `isaacsim.py:2376-2378,2728-2731` | `contact_to_body_idx` by name | `contact_forces` stays `(N,27,3)`; mount bodies' forces are dropped, not mis-attributed |
| body tensors | `isaacsim.py:2755-2771` | `body_pos_w[:, body_ids]` etc. | name-mapped → safe |
| feet/knee/penalty/termination | `base_task.py:255-313`; `a2_piper.yaml:22-23,105-114` | `foot`, `calf` substrings; exact `penalize_contacts_on` (20) | no new name contains `foot`/`calf`; exact-match set unchanged |
| A2 constants | `door_open_a2_base.py:5413-5443,5604-5632,5635` | body-panel 13, arm-panel 10, `A2_PENALIZED_CONTACT_BODY_NAMES`, `A2_M23_SELF_COLLISION_BODY_NAMES` (27, URDF order), feet 4 | all exist; M23 list would **not** cover mount links (opt-in feature, off by default) |
| hand_force / root | `door_open_a2_base.py:7765-7779,28311-28316` | `trunk`, `arm_body7/8` via `simulator.body_names.index` | consistent with remapped `contact_forces` |
| raw-articulation users | `door_open_a2_base.py:11673,22100-22122,22147,27019-27026`; `a2_v24_force_boundary.py:840,1204` | `robot.find_bodies(...)` raw ids used with raw `robot.data.*`/jacobians | self-consistent regardless of insertion position |
| sensors/transformers | `door_open_a2_base.py:29766,29824,29881-29882,29889-29896` | prim paths `Robot/<name>` | names exist |
| **latent mix-up** | `isaacsim.py:791-804` | `robot_config.body_names.index()` (config order) used to index the raw physx `get_disable_gravities()` view | wrong bodies if PhysX order ≠ config order; gated by `disable_gravity_for_arms` (absent from `isaacsim.yaml`) → inactive, note only |

Ordering: IsaacLab `body_names` = `root_physx_view.shared_metatype.link_names` (`IsaacLab/.../articulation.py:161-163`, PhysX order). The three new fixed joints (`trunk_to_vpiper`: trunk→`vpiper_main`; `vpiper_to_support`, `vpiper_to_plate`: children of `vpiper_main`; last three `<joint>` elements of the new URDF) insert three bodies into that raw order, shifting raw indices of deeper links. Because every env-side index goes through `find_bodies`/`contact_to_body_idx`, **no code path indexes robot bodies by integer position from config**, and `robot.num_bodies: 27` (`a2_piper.yaml:7`) is never read by code (only the door articulation's `num_bodies` is checked, `door_open_a2_base.py:10486-10534`). Risk: LOW; runtime assert at `isaacsim.py:2435` fails fast on any name mismatch.

## 3. Self-collision / contact filtering (INSPECTED + STATIC)

Configuration: articulation-level `enabledSelfCollisions=True` (Section 1). Converter/importer defaults: `UrdfConverterCfg.self_collision=False` (`urdf_converter_cfg.py:128`), joints imported with collision disabled between **parent–child only** (INFERRED, standard importer behaviour); so `trunk↔arm_body0`, `trunk↔vpiper_main`, `vpiper_main↔{support,plate}` are filtered, but `arm_body0↔metal_plate_5mm`, `arm_body0↔vpiper_main`, `arm_*↔mount` are **active self-collision pairs**. No `filter_ints`/collision groups exist in this path (`a2_piper.yaml:196` null, unused by `isaacsim.py`).

CPU check (`mount_clearance_check.py`; convex hull per `<collision>` mesh as PhysX `collider_type: convex_hull`, exact LP/QP convex separation, arm FK from URDF):

| Case | Closest pair | Result |
|---|---|---|
| new asset, q=[0,0,0,0,−0.44,1.57] | `arm_body0`–`metal_plate_5mm` | **0.0000 m, touching, no interior overlap** (arm base sits flush on plate top: 0.0924+0.05+0.005 = 0.147432 = `arm_j0` z) |
| same | `arm_body0`–`vpiper_main` / `vpiper_support` | 5.0 mm / 15.4 mm |
| same | all other arm links vs mount/plate/trunk | ≥ 21.7 mm |
| new asset, j5=−0.52 | identical (wrist only) | same |
| new asset, old q=[0,0,0,0.25,0.5,1.57] | same pairs | same minima; no overlap |
| old asset, either q | `arm_body1`–`trunk` | 41.5 mm (nothing closer) |
| sweep j1∈{0,±90°,150°} × j2∈[0,3.14] × j3∈[−2.967,0] (884 cfgs, j4=0,j5=−0.44,j6=1.57) | | 99 cfgs overlap something; **only 4 overlap in new asset but not old** (all j2≥1.57 with j3=0: gripper/`arm_body5-6` sweeping into plate/`vpiper_main`); mount adds a thin layer above the trunk box, not a new workspace obstacle |

Consequences: (a) no initial penetration at reset with either posture (STATIC); (b) a **persistent zero-gap contact pair** `arm_body0`–plate will exist (PhysX generates contacts within contactOffset; INFERRED). `arm_body0` ∈ `penalize_contacts_on`, `penalty_undesired_contact: -0.2` is active (`reward_door_open_a2_base.yaml:94`), and the dedup only subtracts door-panel contacts (`door_open_a2_base.py:17879-17900`); the base `legged_robot_base.py:1996-2006` thresholds |F|>1 N. With reduced-coordinate fixed joints the constraint force should be ≈0, but this must be measured (G0 item R2). Mitigation if it fires: shrink plate collision box height 5→4 mm keeping its top 1 mm below `arm_j0` (URDF `metal_plate_5mm` `<collision>` origin/size), or add a `UsdPhysics FilteredPairsAPI` post-conversion; do not flip `self_collisions`.

## 4. Camera-hardware collision bodies (INSPECTED)

`a2_piper_U3_F0_clearance_only.urdf` (student worktree) is already built on the **new 30-link asset** (`arm_j0` z = 0.147431554755 identical; 42 links / 41 joints). Additions:

| Where | Elements | Geometry |
|---|---|---|
| `trunk` (+8 collisions) | `base_foot`, `base_crossbar` (0.022×0.33×0.008 @ z 0.1554), `base_{left,right}_{crossbar_rail,post,saddle}` | boxes; saddles pitched −32° (left) / −12° (right) |
| `arm_body6_to_gripper` (+4 collisions) | `wrist_u3_foot` 0.04×0.004×0.024; `wrist_u3_upright` 0.008×0.008×**0.132** m (the "180 mm tower" = foot + upright + head); `wrist_u3_short_head`; `wrist_u3_saddle` 0.022×0.08×0.004 | boxes, all in F frame |
| 3 housing links `dd_{base_left,base_right,wrist}_M` + 9 optical frames | fixed joints; housing collision box 0.025×0.09×0.025; **no `<inertial>`** | `dd_wrist_M_fixed` origin xyz (−0.00014, 0.17932, 0.01568), rpy (−0.0001, −1.4836, −1.5699) ⇒ camera centre 180 mm above flange |

Tilt dependence (F0 vs F15 files): `dd_wrist_M_fixed` and `wrist_u3_saddle_collision` pitch −85°→−70°; saddle origin y 0.16487→0.16569, z 0.0144→0.0107; `short_head` length 16.0→20.2 mm and rpy change; upright 132.0→132.6 mm. For 40–45° the envelope **must be regenerated** from `config/U3_*.json` via `code/reproduce.py` (single parameter `design_revision.reference_down_pitch_B_deg`), not hand-edited. Caveat: the bundle's reference posture is `[0,0,0,0,0,1.57]` (`config/U3_F0.json assumptions_and_scope.reference_q`), **not** the v28 `[0,0,0,0,−0.44,1.57]`; j5=−0.44 already pitches the whole F frame by 25.2°, so "head tilt 40–45°" must be defined relative to F before regeneration.

Merge recipe into the training asset: (1) append the 8+4 `<collision>` boxes to `trunk`/`arm_body6_to_gripper` in the new URDF (no new bodies ⇒ Section 2 untouched; contact on tower attributes to `arm_body6_to_gripper`, which is in the arm-panel filter but **not** in the penalty set, `door_open_a2_base.py:5440-5443`); (2) housings: either fold the 3 boxes into parent links (compose fixed-joint origin × collision origin), or keep them as fixed links **with explicit `<inertial>`** — massless links are risky (README §4 of the bundle admits importer behaviour unverified; converter `link_density=0.0`, `urdf_converter.py:135`); (3) update `arm_body6_to_gripper` inertial if tower+D435i mass (~0.1–0.2 kg at 0.18 m) is to be modelled; (4) regenerate USD with the README command (`a2_piper_vpiper_final_20260906/README.md:19-26`): `convert_urdf.py <urdf> <usd> --headless --device cpu --joint-stiffness 0.0 --joint-damping 0.0`. IsaacLab facts: `UrdfConverterCfg.merge_fixed_joints` defaults **True** (`urdf_converter_cfg.py:104-105`), but `scripts/tools/convert_urdf.py:42-47,110` exposes `--merge-joints` with `default=False` ⇒ omitting the flag **preserves** fixed-joint links (as the readback's 30 bodies confirm). `convert_urdf.py` has no `--self-collision` switch (irrelevant: runtime overrides it).

## 5. Mass / inertia (INSPECTED + STATIC)

`urdf_compare.txt`: all 27 shared links have **bit-identical** inertial origin/mass/inertia and identical collision/visual elements; the only shared-element diff is `arm_j0` xyz z 0.154→0.147431554755. Shared mesh SHA256 identical (19/19). New links:

| Link | mass kg | COM (link) m | Ixx/Iyy/Izz kg·m² | source |
|---|---:|---|---|---|
| `vpiper_main` | 0.310684 | (−0.0377, 0, 0.0366) | 1.36e-3/1.41e-3/2.64e-3 (+Ixz −9.7e-5) | PETG, **estimated** 50% solid ×1250 = 625 kg/m³ |
| `vpiper_support` | 0.105624 | (0.0308, 0, 0.0315) | 1.15e-4/1.94e-4/3.01e-4 | same estimate |
| `metal_plate_5mm` | 0.3375 | (0,0,0.0025) | 2.82e-4/1.76e-3/2.04e-3 | Al 2700 kg/m³, nominal 250×100×5 envelope, no holes |

`config/mass_properties_to_complete.json` marks every new mass `MATERIAL ESTIMATE ... not measured`; bolts and camera hardware excluded. `usd_import_readback.json` confirms the USD carries these masses/COMs/inertias (readback within 1e-7 of URDF). Totals 44.741→45.4948 kg (+0.7538, +1.7%). Whole-robot COM at default legs (STATIC, `com_shift.json`, trunk frame): old asset/old posture (0.0020, 0, 0.0099) → new asset/old posture (0.0042, 0, 0.0113) → new asset/new posture (0.0041, −0.0003, 0.0130) m; i.e. the mount adds +2 mm forward / +1.4 mm up, the new posture another +1.7 mm up. Upper assembly mass 4.67→5.42 kg. `A2Base` (`a2_base.py:20-37,148-184`) validates only obs/action/`leg_action_scale` contracts; **no mass term** exists in code or `policy_metadata.json`; the frozen locomotion policy simply experiences +0.75 kg and a ~3 mm COM shift — small but unvalidated (G0 item R4).

## 6. Reset posture in the asset path (INSPECTED)

| Consumer | File:line | Posture source |
|---|---|---|
| spawn `init_state.joint_pos` | `isaacsim.py:1344-1352` | `robot.init_state.default_joint_angles` (config) |
| `default_dof_pos` (obs zero, action offset, reset) | `legged_robot_base.py:189-195,215-216,1151,2267,2331`; `a2_base.py:593-596`; `door_open_a2_base.py:8484-8524,29238-29246,29537-29554` | same config dict; arm reset is exactly default (no noise), stage0→1 requires |q−default|<0.10 (`door_open_a2_base.yaml:138`) |
| v26.4 mirror | `door_open_a2_base.py:8520-8524` | sign vector, posture-agnostic |
| evidence modules | `a2_v23_evidence.py:238-320`; `a2_v26_4_canonicalization.py:66-139` | take `default_dof_pos` as input |

No `.py` or test hard-codes 0.25/0.5 for `arm_j4/j5` (repo-wide search; only `a2_piper.yaml:138-139` and archived resolved configs). `test_a2_v20_env_semantics.py:60` `[0,0,0.25,0.5,0.5]` is a ramp test, unrelated. Camera bundle `reference_joint_pose.json`/`reference_q` use `[0,0,0,0,0,1.57]` and legs 0.7/−1.4 — a **design** posture, not runtime. Required v28 actions: edit `a2_piper.yaml:138-139` (or override in the v28 ablation yaml); add a CPU test asserting the v28 posture lies inside `dof_pos_*_limit_list` and equals the frozen contract; note that `dof_pos − default_dof_pos` observations and `action·scale + default` targets (`legged_robot_base.py:2331`, `a2_base.py:596`) shift for `arm_j4/j5`, so `policy_only` loads of v27 checkpoints are **not posture-neutral** (training lane).

Stale/silent items: `test_a2_v15_dynamic_reachability.py:770-773` reads the **old** URDF path and asserts 27 link names == `M23_SELF_COLLISION_BODY_NAMES` → keeps passing after the switch (stale); if repointed it fails (30 links). `test_a2_student_distillation_contract.py:72,173` asserts `/robot: A2_Piper/a2_piper` → keep that group name; switch via `asset.urdf_file/usd_file` values. Tool defaults still point at the old USD: `smoke_a2_base_flat_walk.py:18`, `preview_a2_piper_door_scene.py:18-19`, `a2_piper_v14_reachability_map.py:26`.

## 7. G0 checklist for the asset switch

**Static (done here, re-run in CI):** S1 URDF parse: 30 links/29 joints, shared 27 links inertially identical, only `arm_j0` z differs (`urdf_compare.py`). S2 name diff: 27 config `body_names` ⊂ URDF links; 20 `dof_names` identical and same order. S3 mass table above; readback = URDF. S4 clearance: no overlap at reset for both postures; `arm_body0`–plate gap 0.000 m recorded. S5 USD sublayers present (`configuration/{base,physics,robot,sensor}.usd`), root only references `configuration/`.

**CPU tests to add:** T1 `test_a2_v28_asset_contract.py`: parse resolved robot yaml → URDF at `asset_root/urdf_file`; assert body/dof name superset, `arm_j0` z = 0.147431554755, total mass 45.494808±1e-6, USD + 4 sublayers exist, `usd_import_readback.json` rigid_body_count==30. T2 posture test (Section 6). T3 update `test_m23_self_collision_body_order...` to read the resolved asset and assert the 27-name tuple is a prefix/subset. T4 clearance regression: rerun `mount_clearance_check.py` logic on the resolved URDF, fail if any interior overlap at reset posture.

**Narrowest runtime smoke (Owner-authorised GPU, 64 envs, 5 batches, `num_steps_per_env` default):** R1 `simulator.num_bodies==27`, `simulator.body_names==config`, `robot.num_bodies==30`, `contact_sensor.num_bodies==30`, `dof_names` order equal (asserts already fail-fast). R2 after `reset` and 50 physics steps standing with zero commands: max over envs of `contact_forces` norm on `arm_body0`, `trunk`, `arm_body1..6` **< 1 N** (else the undesired-contact penalty is polluted) and `penalty_undesired_contact` reward term mean == 0 in stage 0 before door contact. R3 no joint-limit or depenetration spikes: `|joint_vel|` arm < 0.5 rad/s during the standing hold; root z within 0.50–0.56 m. R4 locomotion: `smoke_a2_base_flat_walk.py --usd-file <new>/a2_piper.usd --num-envs 1 --headless` walks 1.0 m/s command for 10 s without fall (root z > 0.35, |roll|,|pitch| < 0.3 rad). R5 reach: at reset `body_pos_w[arm_body6_to_gripper].z − root.z ≈ 0.398±0.01` (STATIC prediction) and stage-2 grasp success rate not below v27 seed baseline by >10 pts on the 5-batch window (band 0.85–0.95 m ⇒ 0.19–0.29 m above the new arm base; with trunk standing at 0.515–0.55 m the reset TCP sits at ≈0.91–0.95 m world, inside the band; old posture put it at 0.84–0.87 m).

**Rollback (config only):** in the v28 ablation yaml set `robot.asset.usd_file: "A2_Piper/a2_piper.usd"`, `robot.asset.urdf_file: "A2_Piper/a2_piper.urdf"`, and restore `robot.init_state.default_joint_angles.arm_j4: 0.25`, `arm_j5: 0.5`; nothing else in code depends on the folder name. Do not delete `gr00t/rl/data/robots/A2_Piper/`.

**Not run:** any Isaac Sim import, physics stepping, or GPU; USD prim names not parsed (no `pxr` outside Isaac Sim) — relied on the importer's name-preserving behaviour plus the runtime asserts.
