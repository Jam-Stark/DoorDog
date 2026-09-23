# 本次输入中的关键源码原文节选

以下均来自本次 source ZIP，保留仓库相对路径与原文件行号。仅供检查出处，不是修改后的补丁。S编号与 SOURCE_MAP.md 一致。

## S01 — `gr00t/rl/isaac_utils/playground/env_rand/door.py`

### 原始 L83–L112

```text
00083 |     return float(np.random.uniform(low, high))
00084 | 
00085 | 
00086 | @configclass
00087 | class DoorSpawnerCfg(sim_utils.RigidObjectSpawnerCfg):
00088 |     articulation_props: sim_utils.ArticulationRootPropertiesCfg = None
00089 |     door_width: tuple[float, float] = (0.8, 1.1)
00090 |     door_height: tuple[float, float] = (1.9, 2.2)
00091 |     door_handle_tblr: tuple[float, float, float, float] = (1.0, 0.85, 0.08, 0.15)
00092 |     door_handle_type: list[Literal["knob", "lever", "pushbar", "handle", "flat"]] = ["lever"]
00093 |     door_open_lr: list[Literal["left", "right"]] = ["left", "right"]
00094 |     door_open_io: list[Literal["in", "out"]] = ["in", "out"]
00095 |     door_weight: tuple[float, float] = (80.0, 120.0)
00096 |     hinge_drive_max_force_range: tuple[float, float] = (2.5, 4.5)
00097 |     # v22 §5A: damping/stiffness become real random variables.  ``None`` keeps the
00098 |     # historical fixed damping 50.0 / stiffness U(1, 10) used by v20/v21.
00099 |     hinge_drive_damping_range: Optional[tuple[float, float]] = None
00100 |     hinge_drive_stiffness_range: Optional[tuple[float, float]] = None
00101 |     handle_drive_max_force_range: tuple[float, float] = (1.0, 2.0)
00102 |     add_walls: bool = False
00103 |     wall_minimum_clearance_fblr: tuple[float, float, float, float] = (3.0, 3.0, 1.0, 1.0)
00104 |     wall_maximum_clearance_fblr: tuple[float, float, float, float] = (10.0, 10.0, 10.0, 10.0)
00105 |     build_latch: bool = False
00106 |     add_floors: bool = False
00107 |     add_lights: bool = False
00108 |     add_ceiling: bool = False
00109 | 
00110 |     randomize_material: bool = False
00111 |     door_frame_material_prim_paths: list[str] = []
00112 |     door_panel_material_prim_paths: list[str] = []
```

### 原始 L513–L632

```text
00513 |     # add articulation
00514 |     articulation_root_api = UsdPhysics.ArticulationRootAPI.Apply(
00515 |         stage.GetPrimAtPath(root_prim_path)
00516 |     )
00517 |     stage.GetPrimAtPath(root_prim_path).CreateAttribute(
00518 |         "physxArticulation:enabledSelfCollisions", Sdf.ValueTypeNames.Bool
00519 |     ).Set(cfg.build_latch)
00520 | 
00521 |     hinge_joint_prim_path = os.path.join(root_prim_path, "hinge_joint")
00522 |     hinge_joint = UsdPhysics.RevoluteJoint.Define(stage, hinge_joint_prim_path)
00523 |     hinge_joint.CreateBody0Rel().SetTargets([root_prim_path])
00524 |     hinge_joint.CreateBody1Rel().SetTargets([panel_prim_path])
00525 |     hinge_joint.GetAxisAttr().Set("Z")
00526 |     hinge_joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.02, -half_door_width * door_open_lr, 0))
00527 |     if door_open_lr == 1:
00528 |         hinge_joint.CreateLocalRot0Attr().Set(Gf.Quatf(real=0.0, imaginary=(Gf.Vec3f(1, 0, 0))))
00529 |     hinge_joint.GetLowerLimitAttr().Set(0.0)
00530 |     hinge_joint.GetUpperLimitAttr().Set(150)
00531 |     hinge_drive = UsdPhysics.DriveAPI.Apply(hinge_joint.GetPrim(), "angular")
00532 |     hinge_drive.GetTargetPositionAttr().Set(-10.0)
00533 |     hinge_drive.GetMaxForceAttr().Set(
00534 |         _sample_uniform_range(
00535 |             cfg.hinge_drive_max_force_range,
00536 |             "hinge_drive_max_force_range",
00537 |         )
00538 |         if cfg.rand_hinge_drive_max_force is None
00539 |         else cfg.rand_hinge_drive_max_force
00540 |     )
00541 |     hinge_drive.GetDampingAttr().Set(
00542 |         _resolve_hinge_drive_scalar(
00543 |             cfg.rand_hinge_drive_damping,
00544 |             cfg.hinge_drive_damping_range,
00545 |             LEGACY_HINGE_DRIVE_DAMPING,
00546 |             "hinge_drive_damping",
00547 |         )
00548 |     )
00549 |     hinge_drive.GetStiffnessAttr().Set(
00550 |         _resolve_hinge_drive_scalar(
00551 |             cfg.rand_hinge_drive_stiffness,
00552 |             cfg.hinge_drive_stiffness_range or LEGACY_HINGE_DRIVE_STIFFNESS_RANGE,
00553 |             None,
00554 |             "hinge_drive_stiffness",
00555 |         )
00556 |     )
00557 |     _update_joint_transform(stage, hinge_joint_prim_path, root_prim_path, panel_prim_path)
00558 | 
00559 |     handle_joint_prim_path = os.path.join(panel_prim_path, "handle_joint")
00560 |     handle_joint = UsdPhysics.RevoluteJoint.Define(stage, handle_joint_prim_path)
00561 |     handle_joint.CreateBody0Rel().SetTargets([panel_prim_path])
00562 |     handle_joint.CreateBody1Rel().SetTargets([handle_prim_path])
00563 |     handle_joint.GetAxisAttr().Set("X")
00564 |     handle_joint.CreateLocalPos0Attr().Set(
00565 |         Gf.Vec3f(0, (half_door_width - door_handle_width) * door_open_lr, door_handle_height)
00566 |     )
00567 |     if door_open_lr == -1:
00568 |         handle_joint.CreateLocalRot0Attr().Set(Gf.Quatf(real=0.0, imaginary=(Gf.Vec3f(0, 0, 1))))
00569 |     handle_joint.GetLowerLimitAttr().Set(0.0)
00570 |     handle_joint.GetUpperLimitAttr().Set(45)
00571 |     handle_drive = UsdPhysics.DriveAPI.Apply(handle_joint.GetPrim(), "angular")
00572 |     handle_drive.GetTargetPositionAttr().Set(-15.0)
00573 |     handle_drive.GetMaxForceAttr().Set(
00574 |         _sample_uniform_range(
00575 |             cfg.handle_drive_max_force_range,
00576 |             "handle_drive_max_force_range",
00577 |         )
00578 |         if cfg.rand_handle_drive_max_force is None
00579 |         else cfg.rand_handle_drive_max_force
00580 |     )
00581 |     handle_drive.GetDampingAttr().Set(0.5)
00582 |     handle_drive.GetStiffnessAttr().Set(50.0)
00583 |     _update_joint_transform(stage, handle_joint_prim_path, panel_prim_path, handle_prim_path)
00584 | 
00585 |     # build latch
00586 |     if cfg.build_latch:
00587 |         latch_link_prim_path = os.path.join(prim_path, "latch_link")
00588 |         create_prim(latch_link_prim_path, "Xform")
00589 |         set_prim_transform(
00590 |             stage,
00591 |             latch_link_prim_path,
00592 |             (-0.083, (half_door_width - 0.005) * door_open_lr, door_height - 0.1),
00593 |             (0, 0, 0),
00594 |             (1.0, 1.0, 1.0),
00595 |         )
00596 |         add_rigid_body(stage, latch_link_prim_path)
00597 | 
00598 |         latch_geom_prim_path = os.path.join(latch_link_prim_path, "latch_geom")
00599 |         create_prim(latch_geom_prim_path, "Cone")
00600 |         set_prim_transform(
00601 |             stage,
00602 |             latch_geom_prim_path,
00603 |             (0, 0, 0),
00604 |             (-90 * door_open_lr, 0, -26.56 * door_open_lr),
00605 |             (1.0, 1.0, 1.0),
00606 |         )
00607 |         cone_geom: UsdGeom.Cone = UsdGeom.Cone.Define(stage, latch_geom_prim_path)
00608 |         cone_geom.GetRadiusAttr().Set(0.025)
00609 |         cone_geom.GetHeightAttr().Set(0.05)
00610 |         cone_geom.GetPurposeAttr().Set("guide")
00611 |         add_mass(stage, latch_geom_prim_path, mass=0.1)
00612 |         add_collider(stage, latch_geom_prim_path)
00613 | 
00614 |         latch_joint_prim_path = os.path.join(panel_prim_path, "latch_joint")
00615 |         latch_joint = UsdPhysics.PrismaticJoint.Define(stage, latch_joint_prim_path)
00616 |         latch_joint.CreateBody0Rel().SetTargets([panel_prim_path])
00617 |         latch_joint.CreateBody1Rel().SetTargets([latch_link_prim_path])
00618 |         latch_joint.GetAxisAttr().Set("Y")
00619 |         latch_joint.CreateLocalPos0Attr().Set(
00620 |             Gf.Vec3f(-0.083, (half_door_width - 0.005) * door_open_lr, door_height - 0.1)
00621 |         )
00622 |         if door_open_lr == 1:
00623 |             latch_joint.CreateLocalRot0Attr().Set(Gf.Quatf(real=0.0, imaginary=(Gf.Vec3f(0, 0, 1))))
00624 |         latch_joint.GetLowerLimitAttr().Set(0.0)
00625 |         latch_joint.GetUpperLimitAttr().Set(0.03)
00626 |         latch_mimic_joint = PhysxSchema.PhysxMimicJointAPI.Apply(
00627 |             latch_joint.GetPrim(), UsdPhysics.Tokens.rotX
00628 |         )
00629 |         latch_mimic_joint.GetReferenceJointRel().AddTarget(handle_joint_prim_path)
00630 |         latch_mimic_joint.GetGearingAttr().Set(-1.0 * 0.03 / 45.0)
00631 |         latch_mimic_joint.GetOffsetAttr().Set(0.0)
00632 |         _update_joint_transform(stage, latch_joint_prim_path, panel_prim_path, latch_link_prim_path)
```

## S02 — `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py`

### 原始 L1976–L2044

```text
01976 | door_spawner_cfg = DoorSpawnerCfg(
01977 |     func=spawn_door,
01978 |     articulation_props=sim_utils.ArticulationRootPropertiesCfg(
01979 |         enabled_self_collisions=True,
01980 |         solver_position_iteration_count=4,
01981 |         solver_velocity_iteration_count=4,
01982 |         fix_root_link=True,
01983 |     ),
01984 |     activate_contact_sensors=True,
01985 |     build_latch=True,
01986 |     add_floors=True,
01987 |     door_open_lr=["right"],
01988 |     door_open_io=["out"],
01989 |     door_handle_tblr=(1.10, 0.80, 0.08, 0.15),
01990 |     door_weight=(80.0, 120.0),
01991 |     hinge_drive_max_force_range=(2.5, 12.0),
01992 |     handle_drive_max_force_range=(1.0, 3.0),
01993 |     randomize_material=True,
01994 |     use_preloaded_materials=True,
01995 |     preloaded_materials_num_transform=20,
01996 |     preloaded_materials_num_color=100,
01997 |     dynamic_material_randomization=False,
01998 |     dynamic_material_randomization_interval=1.0,
01999 | )
02000 | 
02001 | multi_spawner_cfg = sim_utils.MultiAssetSpawnerCfg(
02002 |     assets_cfg=[door_spawner_cfg] * 4096,
02003 |     random_choice=False,
02004 |     activate_contact_sensors=True,
02005 |     rigid_props=sim_utils.RigidBodyPropertiesCfg(
02006 |         disable_gravity=False,
02007 |         retain_accelerations=False,
02008 |         linear_damping=0.0,
02009 |         angular_damping=0.0,
02010 |         max_linear_velocity=1000.0,
02011 |         max_angular_velocity=1000.0,
02012 |         max_depenetration_velocity=1.0,
02013 |     ),
02014 | )
02015 | 
02016 | TaskObjCfgDict = {
02017 |     "door": ArticulationCfg(
02018 |         spawn=multi_spawner_cfg,
02019 |         init_state=ArticulationCfg.InitialStateCfg(
02020 |             pos=(0.0, 0.0, 0.0),
02021 |             rot=(1.0, 0.0, 0.0, 0.0),
02022 |             joint_pos={
02023 |                 ".*hinge.*": 0.0,
02024 |                 ".*handle.*": 0.0,
02025 |                 ".*latch.*": 0.0,
02026 |             },
02027 |             joint_vel={".*": 0.0},
02028 |         ),
02029 |         soft_joint_pos_limit_factor=0.9,
02030 |         actuators={
02031 |             "hinge": ImplicitActuatorCfg(
02032 |                 joint_names_expr=[".*hinge.*"],
02033 |                 velocity_limit_sim=100.0,
02034 |                 stiffness=None,
02035 |                 damping=None,
02036 |             ),
02037 |             "handle": ImplicitActuatorCfg(
02038 |                 joint_names_expr=[".*handle.*"],
02039 |                 velocity_limit_sim=100.0,
02040 |                 stiffness=None,
02041 |                 damping=None,
02042 |             ),
02043 |         },
02044 |     )
```

## S03 — `gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml`

### 原始 L30–L113

```text
00030 |     max_stage_time:
00031 |     - 525
00032 |     - 150
00033 |     - 150
00034 |     - 150
00035 |     - 150
00036 |     - 300
00037 |     a2_v26_door_open_lr: bilateral
00038 |     a2_v26_side_permutation_seed: 281
00039 |     a2_v26_8_penalty_driver: side_min_natural_stage_reach_rate
00040 |     a2_v26_8_penalty_driver_target_stage: 4
00041 |     a2_v26_8_penalty_driver_level_down_rate: 0.5
00042 |     a2_v26_8_penalty_driver_level_up_rate: 0.7
00043 |     a2_v26_8_penalty_curriculum_trace_enabled: true
00044 |     a2_v26_door_handle_height_range:
00045 |     - 0.90
00046 |     - 1.20
00047 |     a2_v26_door_weight_range:
00048 |     - 80.0
00049 |     - 120.0
00050 |     a2_v26_natural_start_enabled: true
00051 |     a2_v26_natural_start_door_normal_distance_range:
00052 |     - 1.2
00053 |     - 4.0
00054 |     a2_v26_natural_start_lateral_offset_range:
00055 |     - -0.5
00056 |     - 0.5
00057 |     # Door-relative +/-35 deg, intersected with handle bearing +/-10 deg.
00058 |     a2_v26_natural_start_relative_yaw_range:
00059 |     - -0.6108652381980153
00060 |     - 0.6108652381980153
00061 |     a2_v29_natural_start_handle_yaw_jitter_rad: 0.17453292519943295
00062 |     a2_v26_bilateral_metrics_enabled: true
00063 |     a2_v23_d1_sampler_enabled: false
00064 |     a2_v24_friction_enabled: false
00065 |     a2_stage0_staging_x_min: 0.68
00066 |     a2_stage0_staging_x_max: 0.72
00067 |     a2_stage0_staging_y_tol: 0.15
00068 |     a2_stage0_target_root_vel: 0.5
00069 |     a2_stage0_near_target_root_vel: 0.3
00070 |     a2_stage0_speed_transition_distance_range: [1.8, 2.2]
00071 |     a2_stage1_stage2_base_forward_creep_deadband: 0.02
00072 |     a2_grasp_gate_mode: control_streak
00073 |     a2_grasp_streak_control_steps: 5
00074 |     a2_stage3_to4_door_hinge_threshold: 0.25
00075 |     a2_stage3_to4_requires_grasp_streak: true
00076 |     a2_stage3_base_unlocked: true
00077 |     a2_stage3_unlatch_handle_position_norm: 0.6
00078 |     a2_stage3_unlatch_near_closed_hinge_threshold: 0.1
00079 |     a2_stage3_stage4_hold_and_drive_velocity_norm: 0.1
00080 |     a2_stage3_stage4_hold_and_drive_velocity_threshold: 0.05
00081 |     a2_stage3_stage4_coasting_velocity_threshold: 0.1
00082 |     a2_stage3_handle_hard_limit_position: 0.785398
00083 |     a2_stage3_handle_hard_limit_tolerance: 0.005
00084 |     a2_stage4_release_hinge_threshold: 1.2
00085 |     a2_stage45_door_frame_contact_scale: 0.2
00086 |     a2_corridor_enabled: false
00087 |     a2_stage5_hold_income_continuity_enabled: false
00088 |     enable_staged_reset: true
00089 |     staged_reset_ratios:
00090 |     - 0.5
00091 |     - 0.1
00092 |     - 0.1
00093 |     - 0.1
00094 |     - 0.1
00095 |     - 0.1
00096 |     staged_reset_max_samples_per_stage: 200
00097 |     a2_v26_4_side_canonicalization_enabled: false
00098 |     a2_v26_2_telemetry_enabled: true
00099 |     a2_v26_2_handle_depression_scale: 0.0
00100 |     a2_v26_3_telemetry_enabled: true
00101 |     a2_v26_3_handle_creation_scale: 6.0
00102 |     a2_m39_gripper_material_enabled: true
00103 |     a2_stage2_squeeze_force_max: 30.0
00104 |     a2_stage2_over_force_threshold: 55.0
00105 |     a2_v26_6_side_mirrored_handle_offset_enabled: true
00106 |     a2_stage2_squeeze_force_min: 0.5
00107 |     delta_action_clamp_to_dof_limits: true
00108 |     a2_v28_camera_telemetry_enabled: true
00109 |     a2_stage4_arm_default_pose_release_gated: true
00110 |     a2_wrist_motion_vel_weights:
00111 |     - - 0.35
00112 |       - 0.35
00113 |       - 0.35
```

### 原始 L174–L185

```text
00174 |   reward_scales:
00175 |     push_door_handle: 0.0
00176 |     a2_stage3_handle_depression: 0.0
00177 |     a2_stage3_handle_creation: 6.0
00178 |     penalty_a2_wrist_motion_l2: -0.4
00179 |     penalty_a2_wrist_tower_contact: -1.0
00180 |     penalty_a2_stage4_arm_default_pose_l1: -0.5
00181 |     penalty_a2_stage5_goal_heading_l2: -4.0
00182 |     penalty_a2_stage5_upright_l2: -8.0
00183 | robot:
00184 |   control:
00185 |     stiffness:
```

## S04 — `gr00t/rl/envs/door/a2_v26_3_creation.py`

### 原始 L1–L78

```text
00001 | """Control-interval handle creation state for base_v26-3."""
00002 | 
00003 | from __future__ import annotations
00004 | 
00005 | import math
00006 | 
00007 | import torch
00008 | 
00009 | 
00010 | A2_V26_3_HANDLE_NORM_RAD = 0.785398
00011 | 
00012 | 
00013 | def a2_v26_3_update_handle_creation(
00014 |     handle_position: torch.Tensor,
00015 |     handle_position_prev: torch.Tensor,
00016 |     handle_highwater: torch.Tensor,
00017 |     active: torch.Tensor,
00018 |     *,
00019 |     control_dt: float,
00020 | ) -> dict[str, torch.Tensor]:
00021 |     """Advance the monotone state once and return the authoritative step cache."""
00022 | 
00023 |     if (
00024 |         not torch.is_tensor(handle_position)
00025 |         or handle_position.ndim != 1
00026 |         or not handle_position.is_floating_point()
00027 |         or not torch.is_tensor(handle_position_prev)
00028 |         or handle_position_prev.shape != handle_position.shape
00029 |         or handle_position_prev.dtype != handle_position.dtype
00030 |         or handle_position_prev.device != handle_position.device
00031 |         or not torch.is_tensor(handle_highwater)
00032 |         or handle_highwater.shape != handle_position.shape
00033 |         or handle_highwater.dtype != handle_position.dtype
00034 |         or handle_highwater.device != handle_position.device
00035 |         or not torch.is_tensor(active)
00036 |         or active.shape != handle_position.shape
00037 |         or active.dtype != torch.bool
00038 |         or active.device != handle_position.device
00039 |     ):
00040 |         raise RuntimeError("v26-3 handle creation tensors have incompatible contracts.")
00041 |     if (
00042 |         not torch.all(torch.isfinite(handle_position))
00043 |         or not torch.all(torch.isfinite(handle_position_prev))
00044 |         or not torch.all(torch.isfinite(handle_highwater))
00045 |     ):
00046 |         raise RuntimeError("v26-3 handle creation tensors must be finite.")
00047 |     if (
00048 |         isinstance(control_dt, bool)
00049 |         or not isinstance(control_dt, (int, float))
00050 |         or not math.isfinite(float(control_dt))
00051 |         or float(control_dt) <= 0.0
00052 |     ):
00053 |         raise RuntimeError("v26-3 handle creation requires a finite positive control_dt.")
00054 | 
00055 |     handle_position_current = handle_position.clamp(
00056 |         min=0.0, max=A2_V26_3_HANDLE_NORM_RAD
00057 |     )
00058 |     highwater_prev = handle_highwater.clone()
00059 |     highwater_current = torch.maximum(highwater_prev, handle_position_current)
00060 |     delta_net = handle_position_current - handle_position_prev
00061 |     delta_highwater = highwater_current - highwater_prev
00062 |     creation_raw = (
00063 |         delta_highwater
00064 |         / (A2_V26_3_HANDLE_NORM_RAD * float(control_dt))
00065 |         * active.to(dtype=handle_position.dtype)
00066 |     )
00067 |     if torch.any(delta_highwater < 0.0) or not torch.all(torch.isfinite(creation_raw)):
00068 |         raise RuntimeError("v26-3 handle creation state violated monotonicity or finiteness.")
00069 |     return {
00070 |         "handle_position_current": handle_position_current,
00071 |         "handle_highwater_prev": highwater_prev,
00072 |         "handle_highwater_current": highwater_current,
00073 |         "handle_delta_net": delta_net,
00074 |         "handle_delta_highwater": delta_highwater,
00075 |         "creation_raw": creation_raw,
00076 |         "creation_active": active,
00077 |     }
00078 | 
```

## S05 — `gr00t/rl/envs/door/door_open_a2_base.py`

### 原始 L2089–L2146

```text
02089 | def a2_grasp_gated_door_reward_components(
02090 |     streak: torch.Tensor,
02091 |     required_streak_steps: int,
02092 |     handle_pos: torch.Tensor,
02093 |     hinge_pos: torch.Tensor,
02094 |     hinge_vel: torch.Tensor,
02095 |     unlatch_handle_position_norm: float,
02096 |     unlatch_near_closed_hinge_threshold: float,
02097 |     hold_and_drive_velocity_norm: float,
02098 | ) -> dict[str, torch.Tensor]:
02099 |     """Compute grasp-gated unlatch and hold-and-drive reward components."""
02100 |     floating_values = (handle_pos, hinge_pos, hinge_vel)
02101 |     if (
02102 |         not torch.is_tensor(streak)
02103 |         or streak.ndim != 1
02104 |         or streak.dtype != torch.long
02105 |         or torch.any(streak < 0)
02106 |         or isinstance(required_streak_steps, bool)
02107 |         or not isinstance(required_streak_steps, int)
02108 |         or required_streak_steps <= 0
02109 |         or any(
02110 |             not torch.is_tensor(value)
02111 |             or value.shape != streak.shape
02112 |             or not value.is_floating_point()
02113 |             or value.device != streak.device
02114 |             or not torch.all(torch.isfinite(value))
02115 |             for value in floating_values
02116 |         )
02117 |         or any(
02118 |             isinstance(value, bool)
02119 |             or not isinstance(value, (int, float))
02120 |             or not math.isfinite(float(value))
02121 |             or float(value) <= 0.0
02122 |             for value in (
02123 |                 unlatch_handle_position_norm,
02124 |                 unlatch_near_closed_hinge_threshold,
02125 |                 hold_and_drive_velocity_norm,
02126 |             )
02127 |         )
02128 |     ):
02129 |         raise ValueError(
02130 |             "A2 grasp-gated door rewards require a non-negative long streak, "
02131 |             "positive scalar thresholds, and matching finite floating door tensors."
02132 |         )
02133 | 
02134 |     hold_streak_ok = streak >= required_streak_steps
02135 |     unlatch_press = (
02136 |         handle_pos / float(unlatch_handle_position_norm)
02137 |     ).clamp(0.0, 1.0)
02138 |     near_closed = hinge_pos < float(unlatch_near_closed_hinge_threshold)
02139 |     drive = (hinge_vel / float(hold_and_drive_velocity_norm)).clamp(0.0, 1.0)
02140 |     hold_float = hold_streak_ok.float()
02141 |     return {
02142 |         "hold_streak_ok": hold_streak_ok,
02143 |         "unlatch_press": unlatch_press,
02144 |         "unlatch_hold": hold_float * unlatch_press * near_closed.float(),
02145 |         "hold_and_drive": hold_float * drive,
02146 |     }
```

### 原始 L2214–L2299

```text
02214 | def a2_stage34_hold_income_mask(
02215 |     stage_buf: torch.Tensor,
02216 |     release_gate: torch.Tensor,
02217 |     stage_open: int,
02218 |     stage_swing: int,
02219 | ) -> torch.Tensor:
02220 |     """Return the stage3/4 hold-income mask with an episode-latched release gate."""
02221 |     if (
02222 |         not torch.is_tensor(stage_buf)
02223 |         or stage_buf.ndim != 1
02224 |         or stage_buf.dtype != torch.long
02225 |         or not torch.is_tensor(release_gate)
02226 |         or release_gate.shape != stage_buf.shape
02227 |         or release_gate.dtype != torch.bool
02228 |         or release_gate.device != stage_buf.device
02229 |         or isinstance(stage_open, bool)
02230 |         or not isinstance(stage_open, int)
02231 |         or isinstance(stage_swing, bool)
02232 |         or not isinstance(stage_swing, int)
02233 |         or stage_open == stage_swing
02234 |     ):
02235 |         raise ValueError(
02236 |             "A2 stage3/4 hold-income mask requires a long stage vector, a matching "
02237 |             "bool release-gate vector, and distinct integer stage values."
02238 |         )
02239 |     return (stage_buf == stage_open) | ((stage_buf == stage_swing) & ~release_gate)
02240 | 
02241 | def a2_update_stage4_release_and_root_latches(
02242 |     release_gate: torch.Tensor,
02243 |     root_x_ever_crossed: torch.Tensor,
02244 |     stage_buf: torch.Tensor,
02245 |     hinge_pos: torch.Tensor,
02246 |     root_x: torch.Tensor,
02247 |     release_hinge_threshold: float,
02248 |     stage_swing: int,
02249 |     update_mask: torch.Tensor | None = None,
02250 | ) -> tuple[torch.Tensor, torch.Tensor]:
02251 |     """OR-latch stage4 release and current-episode root-X crossing state."""
02252 |     if (
02253 |         not torch.is_tensor(release_gate)
02254 |         or release_gate.ndim != 1
02255 |         or release_gate.dtype != torch.bool
02256 |         or not torch.is_tensor(root_x_ever_crossed)
02257 |         or root_x_ever_crossed.shape != release_gate.shape
02258 |         or root_x_ever_crossed.dtype != torch.bool
02259 |         or root_x_ever_crossed.device != release_gate.device
02260 |         or not torch.is_tensor(stage_buf)
02261 |         or stage_buf.shape != release_gate.shape
02262 |         or stage_buf.dtype != torch.long
02263 |         or stage_buf.device != release_gate.device
02264 |         or not torch.is_tensor(hinge_pos)
02265 |         or hinge_pos.shape != release_gate.shape
02266 |         or not hinge_pos.is_floating_point()
02267 |         or hinge_pos.device != release_gate.device
02268 |         or not torch.is_tensor(root_x)
02269 |         or root_x.shape != release_gate.shape
02270 |         or not root_x.is_floating_point()
02271 |         or root_x.dtype != hinge_pos.dtype
02272 |         or root_x.device != release_gate.device
02273 |         or not torch.all(torch.isfinite(hinge_pos))
02274 |         or not torch.all(torch.isfinite(root_x))
02275 |         or isinstance(release_hinge_threshold, bool)
02276 |         or not isinstance(release_hinge_threshold, (int, float))
02277 |         or not math.isfinite(float(release_hinge_threshold))
02278 |         or float(release_hinge_threshold) <= 0.0
02279 |         or isinstance(stage_swing, bool)
02280 |         or not isinstance(stage_swing, int)
02281 |     ):
02282 |         raise ValueError("A2 route latches require matching device-local vectors and a finite positive threshold.")
02283 |     if update_mask is None:
02284 |         update_mask = torch.ones_like(release_gate)
02285 |     elif (
02286 |         not torch.is_tensor(update_mask)
02287 |         or update_mask.shape != release_gate.shape
02288 |         or update_mask.dtype != torch.bool
02289 |         or update_mask.device != release_gate.device
02290 |     ):
02291 |         raise ValueError("A2 route latch update_mask must be a matching device-local bool vector.")
02292 |     release_candidate = update_mask & (stage_buf == stage_swing) & (
02293 |         hinge_pos >= float(release_hinge_threshold)
02294 |     )
02295 |     root_crossing_candidate = update_mask & (root_x > 0.0)
02296 |     return (
02297 |         release_gate | release_candidate,
02298 |         root_x_ever_crossed | root_crossing_candidate,
02299 |     )
```

### 原始 L9133–L9139

```text
09133 |         self.door_dof_state_buf = torch.zeros(
09134 |             self.num_envs, 3, device=self.device, requires_grad=False
09135 |         )
09136 |         self.door_root_state_buf[:, :3] += self.env_origins
09137 | 
09138 |     def _init_a2_v21b_arm_evidence_buffers(self) -> None:
09139 |         """Initialize v21-B arm estimate telemetry without changing control."""
```

### 原始 L14562–L14618

```text
14562 |     def _initialize_a2_v26_3_natural_reset_state(self, env_ids: torch.Tensor) -> None:
14563 |         if not getattr(self, "_a2_v26_3_telemetry_enabled", False):
14564 |             return
14565 |         natural_env_ids = env_ids[self.stage_buf[env_ids] == self.STAGE_WALK_TO_DOOR]
14566 |         if natural_env_ids.numel() == 0:
14567 |             return
14568 |         handle_pos = self._get_door_joint_pos("v26-3 natural reset", 2)[
14569 |             natural_env_ids, 1
14570 |         ].clamp(min=0.0, max=A2_V26_3_HANDLE_NORM_RAD)
14571 |         for name in (
14572 |             "handle_pos_prev_control",
14573 |             "handle_highwater",
14574 |             "handle_highwater_prev",
14575 |         ):
14576 |             getattr(self, f"_a2_v26_3_{name}")[natural_env_ids] = handle_pos
14577 |         for name in (
14578 |             "handle_delta_net",
14579 |             "handle_delta_highwater",
14580 |             "creation_raw_cached",
14581 |         ):
14582 |             getattr(self, f"_a2_v26_3_{name}")[natural_env_ids] = 0.0
14583 |         self._a2_v26_3_creation_active_cached[natural_env_ids] = False
14584 |         self._a2_v26_3_state_initialized[natural_env_ids] = True
14585 | 
14586 |     def _update_a2_v26_3_handle_creation_state(self) -> None:
14587 |         if not getattr(self, "_a2_v26_3_telemetry_enabled", False):
14588 |             return
14589 |         if not torch.all(self._a2_v26_3_state_initialized):
14590 |             missing = torch.where(~self._a2_v26_3_state_initialized)[0].tolist()
14591 |             raise RuntimeError(
14592 |                 "v26-3 handle creation state was not initialized after reset for envs "
14593 |                 f"{missing[:16]}."
14594 |             )
14595 |         if (
14596 |             self._get_a2_grasp_gate_mode()
14597 |             != self.A2_GRASP_GATE_MODE_CONTROL_STREAK
14598 |             or self._get_a2_grasp_streak_control_steps() != 5
14599 |         ):
14600 |             raise RuntimeError("v26-3 handle creation requires strict control-step K5.")
14601 |         handle_pos = self._get_door_joint_pos("v26-3 creation update", 2)[:, 1]
14602 |         stage3 = self.stage_buf == self.STAGE_OPEN
14603 |         strict_k5 = self._get_a2_hold_streak_ok_mask()
14604 |         state = a2_v26_3_update_handle_creation(
14605 |             handle_pos,
14606 |             self._a2_v26_3_handle_pos_prev_control,
14607 |             self._a2_v26_3_handle_highwater,
14608 |             stage3 & strict_k5,
14609 |             control_dt=float(self.dt),
14610 |         )
14611 |         self._a2_v26_3_handle_highwater_prev[:] = state["handle_highwater_prev"]
14612 |         self._a2_v26_3_handle_highwater[:] = state["handle_highwater_current"]
14613 |         self._a2_v26_3_handle_delta_net[:] = state["handle_delta_net"]
14614 |         self._a2_v26_3_handle_delta_highwater[:] = state["handle_delta_highwater"]
14615 |         self._a2_v26_3_creation_raw_cached[:] = state["creation_raw"]
14616 |         self._a2_v26_3_creation_active_cached[:] = state["creation_active"]
14617 |         self._a2_v26_3_handle_pos_prev_control[:] = state["handle_position_current"]
14618 | 
```

### 原始 L15140–L15162

```text
15140 |     def _get_a2_door_income_hold_mask(self) -> torch.Tensor:
15141 |         historical_hold = self._get_a2_hold_streak_ok_mask()
15142 |         stage_buf = getattr(self, "stage_buf", None)
15143 |         if (
15144 |             not torch.is_tensor(stage_buf)
15145 |             or tuple(stage_buf.shape) != (self.num_envs,)
15146 |             or stage_buf.dtype != torch.long
15147 |             or stage_buf.device != torch.device(self.device)
15148 |         ):
15149 |             raise RuntimeError(
15150 |                 "A2 door-income hold mask requires a device-local long stage buffer."
15151 |             )
15152 |         mask = historical_hold.clone()
15153 |         stage5 = stage_buf == self.STAGE_THROUGH
15154 |         if self._get_a2_stage5_hold_income_continuity_enabled():
15155 |             continuation = self._get_a2_stage5_hold_continuation()
15156 |             mask[stage5] = continuation[stage5]
15157 |         else:
15158 |             mask[stage5] = False
15159 |         return mask
15160 | 
15161 |     def _stage_3_to_4_advance_callback(self, env_ids: torch.Tensor) -> None:
15162 |         if self._use_a2_base:
```

### 原始 L15949–L15983

```text
15949 |     def _reward_penalty_a2_stage4_arm_default_pose_l1(self):
15950 |         if not self._use_a2_base:
15951 |             raise RuntimeError(
15952 |                 "penalty_a2_stage4_arm_default_pose_l1 is only defined for A2 Piper configs."
15953 |             )
15954 |         target_pos = self._get_a2_arm_default_dof_pos()
15955 |         dof_pos = getattr(self.simulator, "dof_pos", None)
15956 |         max_arm_dof_index = max(self._upper_non_gripper_dof_idx)
15957 |         if (
15958 |             dof_pos is None
15959 |             or not torch.is_tensor(dof_pos)
15960 |             or dof_pos.ndim != 2
15961 |             or dof_pos.shape[0] != self.num_envs
15962 |             or dof_pos.shape[1] <= max_arm_dof_index
15963 |         ):
15964 |             shape = None if dof_pos is None else tuple(dof_pos.shape)
15965 |             raise RuntimeError(
15966 |                 "penalty_a2_stage4_arm_default_pose_l1 requires simulator.dof_pos "
15967 |                 f"shape ({self.num_envs}, >{max_arm_dof_index}); got {shape}."
15968 |             )
15969 |         arm_pos = dof_pos[:, self._upper_non_gripper_dof_idx]
15970 |         if tuple(arm_pos.shape) != (self.num_envs, 6):
15971 |             raise RuntimeError(
15972 |                 "penalty_a2_stage4_arm_default_pose_l1 expects arm_j1..arm_j6 "
15973 |                 f"shape ({self.num_envs}, 6); got {tuple(arm_pos.shape)}."
15974 |             )
15975 |         penalty = torch.abs(arm_pos - target_pos).sum(dim=-1)
15976 |         if self.config.get("a2_stage4_arm_default_pose_release_gated", False):
15977 |             masks = self._get_a2_stage3_stage4_contact_squeeze_masks(
15978 |                 "A2 stage4 post-release default pose"
15979 |             )
15980 |             penalty = penalty * (self._a2_stage4_release_gate & ~masks["both_contact"])
15981 |         return penalty
15982 | 
15983 |     def _reward_penalty_a2_wrist_motion_l2(self):
```

### 原始 L17562–L17582

```text
17562 |     @StagedTaskBase.effective_in_stage([STAGE_SWING, STAGE_THROUGH])
17563 |     def _reward_dont_push_door_handle(self):
17564 |         handle_vel_reward = -1.0 * self.simulator.scene.articulations["door"].data.joint_vel[:, 1]
17565 |         handle_pos_reward = (
17566 |             0.785398 - self.simulator.scene.articulations["door"].data.joint_pos[:, 1]
17567 |         ).clamp(min=0.0, max=0.785398) / 0.785398
17568 |         return (handle_vel_reward + handle_pos_reward).clamp(max=1.0, min=-1.0)
17569 | 
17570 |     @StagedTaskBase.effective_in_stage([STAGE_OPEN, STAGE_SWING])
17571 |     def _reward_push_door_hinge(self):
17572 |         hinge_vel_reward = self.simulator.scene.articulations["door"].data.joint_vel[:, 0] * 10
17573 |         hinge_pos_reward = (
17574 |             self.simulator.scene.articulations["door"]
17575 |             .data.joint_pos[:, 0]
17576 |             .clamp(min=0.0, max=1.5708)
17577 |             / 1.5708
17578 |         )
17579 |         if self._use_a2_base:
17580 |             hinge_pos_reward = hinge_pos_reward * self._get_a2_stage34_hold_income_mask().float()
17581 |         return (hinge_vel_reward + hinge_pos_reward).clamp(max=1.0, min=-1.0)
17582 | 
```

### 原始 L18341–L18401

```text
18341 |     def _get_a2_stage34_hold_income_mask(self) -> torch.Tensor:
18342 |         if not self._use_a2_base:
18343 |             raise RuntimeError("A2 stage3/4 hold-income mask is only defined for A2 Piper configs.")
18344 |         stage_buf = getattr(self, "stage_buf", None)
18345 |         release_gate = getattr(self, "_a2_stage4_release_gate", None)
18346 |         return a2_stage34_hold_income_mask(
18347 |             stage_buf, release_gate, self.STAGE_OPEN, self.STAGE_SWING
18348 |         )
18349 | 
18350 |     def _get_a2_corridor_mask(self) -> torch.Tensor:
18351 |         if not self._use_a2_base:
18352 |             raise RuntimeError("A2 corridor is only defined for A2 Piper configs.")
18353 |         corridor_latched = getattr(self, "_a2_corridor_latched", None)
18354 |         if (
18355 |             not torch.is_tensor(corridor_latched)
18356 |             or tuple(corridor_latched.shape) != (self.num_envs,)
18357 |             or corridor_latched.dtype != torch.bool
18358 |             or corridor_latched.device != torch.device(self.device)
18359 |         ):
18360 |             raise RuntimeError(
18361 |                 "A2 corridor requires a device-local bool latch buffer."
18362 |             )
18363 |         if not self._get_a2_corridor_enabled():
18364 |             return torch.zeros_like(corridor_latched)
18365 |         return corridor_latched
18366 | 
18367 |     def _get_a2_grasp_gated_door_reward_components(self):
18368 |         door_joint_pos = self._get_door_joint_pos(
18369 |             "A2 grasp-gated door rewards", 2
18370 |         )
18371 |         door_joint_vel = self._get_door_joint_vel(
18372 |             "A2 grasp-gated door rewards", 2
18373 |         )
18374 |         streak = self._get_a2_grasp_control_streak_buffer(
18375 |             "_a2_stage3_stage4_both_contact_streak",
18376 |             "A2 grasp-gated door rewards",
18377 |         )
18378 |         components = a2_grasp_gated_door_reward_components(
18379 |             streak=streak,
18380 |             required_streak_steps=self._get_a2_grasp_streak_control_steps(),
18381 |             handle_pos=door_joint_pos[:, 1],
18382 |             hinge_pos=door_joint_pos[:, 0],
18383 |             hinge_vel=door_joint_vel[:, 0],
18384 |             unlatch_handle_position_norm=(
18385 |                 self._get_a2_stage3_unlatch_handle_position_norm()
18386 |             ),
18387 |             unlatch_near_closed_hinge_threshold=(
18388 |                 self._get_a2_stage3_unlatch_near_closed_hinge_threshold()
18389 |             ),
18390 |             hold_and_drive_velocity_norm=(
18391 |                 self._get_a2_stage3_stage4_hold_and_drive_velocity_norm()
18392 |             ),
18393 |         )
18394 |         components["hold_and_drive"] = a2_corridor_hold_and_drive_component(
18395 |             self._get_a2_door_income_hold_mask(),
18396 |             door_joint_vel[:, 0],
18397 |             self._get_a2_corridor_mask(),
18398 |             self._get_a2_stage3_stage4_hold_and_drive_velocity_norm(),
18399 |             self._get_a2_stage3_stage4_hold_and_drive_velocity_norm_in_corridor(),
18400 |             self._get_a2_corridor_enabled(),
18401 |         )
```

### 原始 L28462–L28505

```text
28462 |     def _get_obs_hand_force(self):
28463 |         if self._use_a2_base:
28464 |             if not hasattr(self, "_a2_gripper_force_body_indices"):
28465 |                 raise RuntimeError(
28466 |                     "A2 hand_force requires name-based gripper body indices for "
28467 |                     "arm_body7 and arm_body8."
28468 |                 )
28469 |             hand_force = self.simulator.contact_forces[:, self._a2_gripper_force_body_indices, :]
28470 |             result = hand_force.reshape(hand_force.shape[0], 6)
28471 |             if not self._a2_v26_4_side_canonicalization_enabled():
28472 |                 return result
28473 |             return a2_v26_4_canonicalize_hand_force(result, self._a2_v26_4_right_mask())
28474 |         left_hand_force = self.simulator.contact_forces[:, self.left_hand_indices, :]
28475 |         right_hand_force = self.simulator.contact_forces[:, self.right_hand_indices, :]
28476 |         return torch.cat(
28477 |             [
28478 |                 left_hand_force.reshape(left_hand_force.shape[0], -1),
28479 |                 right_hand_force.reshape(right_hand_force.shape[0], -1),
28480 |             ],
28481 |             dim=-1,
28482 |         )
28483 | 
28484 |     def _get_obs_privileged_door_info(self):
28485 |         left = (self.door_open_lr == 1.0).to(dtype=self.door_width.dtype)
28486 |         right = (self.door_open_lr == -1.0).to(dtype=self.door_width.dtype)
28487 |         return torch.stack(
28488 |             [
28489 |                 self.door_width,
28490 |                 self.door_height,
28491 |                 self.door_handle_height,
28492 |                 self.door_handle_width,
28493 |                 self.door_weight / 100.0,
28494 |                 left,
28495 |                 right,
28496 |                 self.door_open_io,
28497 |             ],
28498 |             dim=1,
28499 |         )
28500 | 
28501 |     def _get_obs_door_dof_pos(self):
28502 |         return self.simulator.get_task_dof_pos("door")[:, :2]
28503 | 
28504 |     def _get_a2_student_dof_indices(self):
28505 |         """Resolve the deployable A2 DOF order from names and validate it."""
```

### 原始 L29031–L29100

```text
29031 |     def reset_envs_idx(self, env_ids, target_states=None, target_buf=None):
29032 |         """Reapply native friction after ordinary or staged state writes complete.
29033 | 
29034 |         ``LeggedRobotBase.reset_envs_idx`` writes the ordinary door state via
29035 |         ``_reset_object_states_callback``.  ``StagedTaskBase.reset_envs_idx``
29036 |         instead writes sampled door root/joint tensors directly before it
29037 |         returns.  This outer hook therefore runs after both state-write paths,
29038 |         while the disabled backend remains a true no-write path.
29039 |         """
29040 | 
29041 |         self._a2_p0_h_pending_stage_selection = None
29042 |         self._a2_p0_h_pending_sample_selection = None
29043 |         sentinel_receipt = None
29044 |         if self._a2_p0_h_reset_audit_enabled and env_ids.numel() > 0:
29045 |             sentinel_receipt = self._a2_p0_h_write_sentinel(env_ids)
29046 | 
29047 |         recovery_config = self._a2_v27_recovery_config
29048 |         bank_env_ids = torch.empty(0, dtype=torch.long, device=self.device)
29049 |         if (
29050 |             recovery_config is not None
29051 |             and recovery_config["enabled"]
29052 |             and recovery_config["bank_reset_share"] > 0.0
29053 |             and not self.is_evaluating
29054 |             and self._a2_v27_bank is not None
29055 |             and env_ids.numel() > 0
29056 |         ):
29057 |             bank_valid = self._a2_v27_bank["available"][:, env_ids].any(dim=0)
29058 |             for side_index, side_sign in enumerate((1.0, -1.0)):
29059 |                 self._a2_v27_bank["eligible_reset_count_by_side"][side_index] += (
29060 |                     bank_valid & (self.door_open_lr[env_ids] == side_sign)
29061 |                 ).sum()
29062 |             choose_bank = bank_valid & (
29063 |                 torch.rand(env_ids.numel(), device=self.device)
29064 |                 < recovery_config["bank_reset_share"]
29065 |             )
29066 |             bank_env_ids = env_ids[choose_bank]
29067 | 
29068 |         result = super().reset_envs_idx(env_ids, target_states, target_buf)
29069 |         if bank_env_ids.numel() > 0:
29070 |             self._restore_a2_v27_recovery_bank(bank_env_ids)
29071 |         self._record_a2_v26_reset_origins(env_ids)
29072 |         if getattr(self, "_a2_v26_3_telemetry_enabled", False):
29073 |             self._initialize_a2_v26_3_natural_reset_state(env_ids)
29074 |             staged_env_ids = env_ids[
29075 |                 self.stage_buf[env_ids] != self.STAGE_WALK_TO_DOOR
29076 |             ]
29077 |             if staged_env_ids.numel() > 0 and torch.any(
29078 |                 ~self._a2_v26_3_state_initialized[staged_env_ids]
29079 |             ):
29080 |                 raise RuntimeError(
29081 |                     "v26-3 nonzero staged reset did not restore initialized creation state."
29082 |                 )
29083 |         if self._a2_v27_friction_bucket_config is not None and env_ids.numel() > 0:
29084 |             self._apply_a2_v27_friction_bucket(env_ids)
29085 |         backend = self._a2_v24_friction_backend
29086 |         if backend is not None and env_ids.numel() > 0:
29087 |             receipt = backend.apply(env_ids)
29088 |             receipt["backend"] = backend.receipt_fragment()
29089 |             if self.enable_staged_reset:
29090 |                 if (
29091 |                     self._a2_p0_h_reset_audit_enabled
29092 |                     and self._a2_p0_h_pending_stage_selection is None
29093 |                 ):
29094 |                     raise RuntimeError("P0 H staged reset did not expose its selected stages.")
29095 |                 if (
29096 |                     self._a2_p0_h_reset_audit_enabled
29097 |                     and self._a2_p0_h_pending_sample_selection is None
29098 |                 ):
29099 |                     raise RuntimeError("P0 H staged reset did not expose its selected samples.")
29100 |                 selected_stages = self.stage_buf[env_ids]
```

### 原始 L29299–L29305

```text
29299 |     def _reset_object_states_callback(self, env_ids):
29300 |         self._reset_door_states(env_ids)
29301 |         return super()._reset_object_states_callback(env_ids)
29302 | 
29303 |     @override
29304 |     def _reset_robot_states_callback(self, env_ids, target_states=None):
29305 |         if self._use_a2_base:
```

### 原始 L29444–L29466

```text
29444 |     def _reset_door_states(self, env_ids):
29445 |         randomize_door_init_state = self.config.get("randomize_door_init_state", False)
29446 |         self.door_dof_state_buf[:] = 0.0
29447 |         if randomize_door_init_state:
29448 |             # 33% of the environments to have a different initial state
29449 |             rand_env_ids = env_ids[torch.randperm(len(env_ids))[: len(env_ids) // 3]]
29450 |             self.door_dof_state_buf[rand_env_ids, 0] = torch_rand_float(
29451 |                 0.261799, 1.74533, (len(rand_env_ids), 1), device=self.device
29452 |             ).squeeze(-1)
29453 |         door_dof_state_dict = {
29454 |             "door": (
29455 |                 self.door_dof_state_buf,
29456 |                 torch.zeros_like(self.door_dof_state_buf),
29457 |                 torch.tensor([0, 1, 2], device=self.device, dtype=torch.long),
29458 |             )
29459 |         }
29460 |         self.simulator.set_task_dof_state_tensor(env_ids, door_dof_state_dict)
29461 | 
29462 |         door_dof_target = torch.zeros(self.num_envs, 3, device=self.device, requires_grad=False)
29463 |         door_dof_target[:, 0] = 0.0
29464 |         door_dof_target[:, 1] = 15 * torch.pi / 180.0  # tension the door handle
29465 |         self.simulator.apply_torques_at_task_dof(env_ids, {"door": door_dof_target})
29466 | 
```

### 原始 L29855–L29906

```text
29855 |     def _stage_3_to_4_advance_condition(self):
29856 |         # rotate the door handle and open the door
29857 |         threshold = (
29858 |             self._get_a2_stage3_to4_door_hinge_threshold()
29859 |             if self._use_a2_base
29860 |             else 0.174533
29861 |         )
29862 |         door_opened = (
29863 |             self._get_door_joint_pos("stage3 to stage4 advance", 1)[:, 0]
29864 |             > threshold
29865 |         )
29866 |         if not self._use_a2_base:
29867 |             return door_opened
29868 |         hold_streak_ok = a2_stage3_to4_hold_streak_mask(
29869 |             current_streak_ok=self._get_a2_hold_streak_ok_mask(),
29870 |             stage3_highwater=self._a2_stage3_grasp_streak_highwater,
29871 |             requires_grasp_streak=self._get_a2_stage3_to4_requires_grasp_streak(),
29872 |             highwater_enabled=self._get_a2_stage3_to4_streak_highwater(),
29873 |         )
29874 |         return a2_stage3_to4_advance_mask(
29875 |             door_opened=door_opened,
29876 |             hold_streak_ok=hold_streak_ok,
29877 |             requires_grasp_streak=True,
29878 |         )
29879 | 
29880 |     def _stage_4_reward_condition(self):
29881 |         # keep grasping the door handle
29882 |         return self._stage_3_to_4_advance_condition()
29883 | 
29884 |     def _stage_4_to_5_advance_condition(self):
29885 |         # walk through the door and leave handle up
29886 |         walked_through_door = (
29887 |             self.simulator.robot_root_states[:, 0] - self.env_origins[:, 0]
29888 |         ) > 0.0
29889 |         door_joint_pos = self._get_door_joint_pos(
29890 |             "stage4 to stage5 advance", 2
29891 |         )
29892 |         hinge_threshold = (
29893 |             self._get_a2_stage4_to5_door_hinge_threshold()
29894 |             if self._use_a2_base
29895 |             else 1.0472
29896 |         )
29897 |         door_opened = door_joint_pos[:, 0] > hinge_threshold
29898 |         handle_up = door_joint_pos[:, 1] < 0.2
29899 |         return walked_through_door & handle_up & door_opened
29900 | 
29901 |     def _stage_5_reward_condition(self):
29902 |         # keep walking through the door
29903 |         return self._stage_4_to_5_advance_condition()
29904 | 
29905 |     def _stage_5_to_complete_condition(self):
29906 |         return (self.simulator.robot_root_states[:, 0] - self.env_origins[:, 0]) > 1.5
```

### 原始 L30045–L30081

```text
30045 |             contact_detail_kwargs = a2_hold_contact_sensor_detail_kwargs(
30046 |                 contact_detail_enabled,
30047 |                 self._get_a2_hold_contact_capacity() if contact_detail_enabled else None,
30048 |             )
30049 |             a2_gripper_handle_contact_sensor_config: ContactSensorCfg = ContactSensorCfg(
30050 |                 prim_path=f"/World/envs/env_.*/{target_obj}/{target_contact_sub_prim}",
30051 |                 history_length=self._get_a2_stage2_grasp_contact_history_length(),
30052 |                 filter_prim_paths_expr=[
30053 |                     "/World/envs/env_.*/Robot/arm_body7",
30054 |                     "/World/envs/env_.*/Robot/arm_body8",
30055 |                 ],
30056 |                 **contact_detail_kwargs,
30057 |             )
30058 |             simulator.scene.sensors[self.A2_GRIPPER_HANDLE_CONTACT_SENSOR] = ContactSensor(
30059 |                 a2_gripper_handle_contact_sensor_config
30060 |             )
30061 |             body_panel_filter_paths = [
30062 |                 f"/World/envs/env_.*/Robot/{body_name}"
30063 |                 for body_name in self.A2_DOOR_BODY_PANEL_FILTER_NAMES
30064 |             ]
30065 |             arm_panel_filter_paths = [
30066 |                 f"/World/envs/env_.*/Robot/{body_name}"
30067 |                 for body_name in self.A2_DOOR_ARM_PANEL_FILTER_NAMES
30068 |             ]
30069 |             body_panel_contact_sensor_config = ContactSensorCfg(
30070 |                 prim_path=f"/World/envs/env_.*/{target_obj}/door_panel",
30071 |                 filter_prim_paths_expr=body_panel_filter_paths,
30072 |                 history_length=0,
30073 |                 update_period=0.0,
30074 |             )
30075 |             arm_panel_contact_sensor_config = ContactSensorCfg(
30076 |                 prim_path=f"/World/envs/env_.*/{target_obj}/door_panel",
30077 |                 filter_prim_paths_expr=arm_panel_filter_paths,
30078 |                 history_length=0,
30079 |                 update_period=0.0,
30080 |             )
30081 |             simulator.scene.sensors[self.A2_DOOR_BODY_PANEL_CONTACT_SENSOR] = ContactSensor(
```

### 原始 L30196–L30213

```text
30196 |     def _apply_force_in_physics_step(self):
30197 |         if self._use_a2_base:
30198 |             result = A2Base._apply_force_in_physics_step(self)
30199 |             self._capture_a2_v23_pre_actuator_compute()
30200 |             return result
30201 |         return super()._apply_force_in_physics_step()
30202 | 
30203 |     def _parse_palm_side_direction(self, palm_side_direction: list[str]) -> torch.Tensor:
30204 |         """
30205 |         Convert the palm side direction to a quaternion that rotates anything
30206 |         expressed in the finger frame to point into the palm.
30207 |         """
30208 |         output = torch.zeros(len(palm_side_direction), 4, device=self.device)  # wxyz
30209 |         for i, direction in enumerate(palm_side_direction):
30210 |             if direction == "+x":
30211 |                 output[i] = torch.tensor([1.0, 0.0, 0.0, 0.0], device=self.device)
30212 |             elif direction == "-x":
30213 |                 output[i] = torch.tensor([0.0, 0.0, 0.0, 1.0], device=self.device)
```

## S06 — `gr00t/rl/envs/base_task/staged_task_base.py`

### 原始 L200–L243

```text
00200 |         # incompatible snapshot (for example, R1 soft-phase states that would
00201 |         # violate the hard send institution).  The hook is shape/device checked
00202 |         # here so malformed masks fail fast.
00203 |         if self.enable_staged_reset:
00204 |             filtered_advance_mask = self._filter_staged_reset_snapshot_mask(advance_mask)
00205 |             if (
00206 |                 not torch.is_tensor(filtered_advance_mask)
00207 |                 or tuple(filtered_advance_mask.shape) != (self.num_envs,)
00208 |                 or filtered_advance_mask.dtype != torch.bool
00209 |                 or filtered_advance_mask.device != torch.device(self.device)
00210 |             ):
00211 |                 shape = None if not torch.is_tensor(filtered_advance_mask) else tuple(filtered_advance_mask.shape)
00212 |                 dtype = None if not torch.is_tensor(filtered_advance_mask) else filtered_advance_mask.dtype
00213 |                 device = None if not torch.is_tensor(filtered_advance_mask) else filtered_advance_mask.device
00214 |                 raise RuntimeError(
00215 |                     "staged-reset snapshot mask must be a device-local bool vector "
00216 |                     f"of shape ({self.num_envs},); got shape={shape}, dtype={dtype}, device={device}."
00217 |                 )
00218 |             self._take_snapshot_of_buffered_states(filtered_advance_mask)
00219 | 
00220 |         return super()._post_compute_observations_callback()
00221 | 
00222 |     def _filter_staged_reset_snapshot_mask(self, advance_mask: torch.Tensor) -> torch.Tensor:
00223 |         """Return stage entries eligible for snapshot storage.
00224 | 
00225 |         The default is intentionally a no-op so legacy environments preserve
00226 |         their staged-reset behavior.  DoorPregrasp adds the R1 compatibility
00227 |         guard.
00228 |         """
00229 |         return advance_mask
00230 | 
00231 |     def _validate_loaded_staged_reset_sample(
00232 |         self,
00233 |         selected_env_ids: torch.Tensor,
00234 |         selected_stages: torch.Tensor,
00235 |         selected_sample_indices: torch.Tensor,
00236 |     ) -> None:
00237 |         """Validate and warm up a staged sample after every state writer ran.
00238 | 
00239 |         Subclasses may use this hook to validate restored historical state and
00240 |         clear one-step transients.  The base implementation intentionally does
00241 |         nothing so legacy staged-reset tasks retain their existing behavior.
00242 |         """
00243 |         return None
```

### 原始 L630–L700

```text
00630 |             self._reset_robot_states_callback(user_env_ids, target_states)
00631 |             self._reset_object_states_callback(user_env_ids)
00632 |             self._post_reset_callback(user_env_ids)
00633 | 
00634 |         # handle staged reset
00635 |         if len(selected_env_ids) > 0:
00636 |             self.set_to_stage(selected_env_ids, selected_stages)
00637 |             root_states = {}
00638 |             dof_states = {}
00639 |             for name, state_case in self.staged_reset_buf.items():
00640 |                 if name == "robot":
00641 |                     self.target_robot_root_states[selected_env_ids] = state_case["root_state"][
00642 |                         selected_stages, selected_sample_indices, selected_env_ids
00643 |                     ].clone()
00644 |                     self.target_robot_dof_state[selected_env_ids] = state_case["dof_state"][
00645 |                         selected_stages, selected_sample_indices, selected_env_ids
00646 |                     ].clone()
00647 |                 elif state_case["type"] == "rigid_object" or state_case["type"] == "articulation":
00648 |                     root_states[name] = torch.zeros(
00649 |                         self.num_envs,
00650 |                         13,
00651 |                         device=self.device,
00652 |                         dtype=torch.float,
00653 |                         requires_grad=False,
00654 |                     )
00655 |                     root_states[name][selected_env_ids] = state_case["root_state"][
00656 |                         selected_stages, selected_sample_indices, selected_env_ids
00657 |                     ].clone()
00658 |                     if state_case["type"] == "articulation":
00659 |                         obj: Articulation = state_case["obj"]
00660 |                         dof_pos = torch.zeros(
00661 |                             self.num_envs,
00662 |                             obj.num_joints,
00663 |                             device=self.device,
00664 |                             dtype=torch.float,
00665 |                             requires_grad=False,
00666 |                         )  # dof_pos
00667 |                         dof_vel = torch.zeros(
00668 |                             self.num_envs,
00669 |                             obj.num_joints,
00670 |                             device=self.device,
00671 |                             dtype=torch.float,
00672 |                             requires_grad=False,
00673 |                         )  # dof_vel
00674 |                         dof_pos[selected_env_ids] = state_case["dof_state"][
00675 |                             selected_stages, selected_sample_indices, selected_env_ids, :, 0
00676 |                         ].clone()
00677 |                         dof_vel[selected_env_ids] = state_case["dof_state"][
00678 |                             selected_stages, selected_sample_indices, selected_env_ids, :, 1
00679 |                         ].clone()
00680 |                         dof_states[name] = (
00681 |                             dof_pos,
00682 |                             dof_vel,
00683 |                             torch.arange(obj.num_joints, device=self.device, dtype=torch.long),
00684 |                         )
00685 |                 elif state_case["type"] == "buffer":
00686 |                     state_case["load_callback"](
00687 |                         selected_env_ids,
00688 |                         state_case["data"][
00689 |                             selected_stages, selected_sample_indices, selected_env_ids
00690 |                         ].clone(),
00691 |                     )
00692 | 
00693 |             if root_states:
00694 |                 self.simulator.set_task_root_state_tensor(selected_env_ids, root_states)
00695 |                 self.simulator.set_task_dof_state_tensor(selected_env_ids, dof_states)
00696 | 
00697 |             self._validate_loaded_staged_reset_sample(
00698 |                 selected_env_ids,
00699 |                 selected_stages,
00700 |                 selected_sample_indices,
```

## S07 — `gr00t/rl/envs/legged_base_task/legged_robot_base.py`

### 原始 L1100–L1133

```text
01100 |                     self.config.robot.meta_kp_scale_limit[1]
01101 |                     - self.config.robot.meta_kp_scale_limit[0]
01102 |                 )
01103 |                 * meta_kp_scale
01104 |             )
01105 |             self._meta_kd_scale[:] = (
01106 |                 self.config.robot.meta_kd_scale_limit[0]
01107 |                 + (
01108 |                     self.config.robot.meta_kd_scale_limit[1]
01109 |                     - self.config.robot.meta_kd_scale_limit[0]
01110 |                 )
01111 |                 * meta_kd_scale
01112 |             )
01113 | 
01114 |     def _physics_step(self):
01115 |         self.render()
01116 |         for sim_sub_t in range(self.config.simulator.config.sim.control_decimation):
01117 |             self._update_meta_pd_scale(sim_sub_t)
01118 |             self._apply_force_in_physics_step()
01119 |             self.simulator.simulate_at_each_physics_step()
01120 |             # The simulator has advanced and scene state has been refreshed at
01121 |             # this point.  Subclasses may capture one frame for this real
01122 |             # physics substep; control-rate callbacks must not synthesize it.
01123 |             self._post_physics_substep(sim_sub_t)
01124 | 
01125 |     def _post_physics_substep(self, sim_sub_t: int) -> None:
01126 |         """Hook invoked once after each real physics substep."""
01127 |         del sim_sub_t
01128 | 
01129 |     def _compute_perturbation_forces(self):
01130 |         """
01131 |         Should be implemented in the child class if needed.
01132 |         """
01133 |         pass
```

## S08 — `gr00t/rl/simulator/isaacsim/isaacsim.py`

### 原始 L2818–L2840

```text
02818 |     def set_task_root_state_tensor(self, set_env_ids, root_states):
02819 |         for name, task_obj in self._task.items():
02820 |             if name in root_states.keys():
02821 |                 task_obj.write_root_state_to_sim(root_states[name][set_env_ids, :], set_env_ids)
02822 |                 task_obj.reset()
02823 | 
02824 |     def set_task_dof_state_tensor(self, set_env_ids, dof_states):
02825 |         for name, task_obj in self._task.items():
02826 |             if name in dof_states.keys():
02827 |                 dof_pos, dof_vel, dof_ids = dof_states[name]
02828 |                 task_obj.write_joint_state_to_sim(
02829 |                     dof_pos[set_env_ids, :], dof_vel[set_env_ids, :], dof_ids, set_env_ids
02830 |                 )
02831 | 
02832 |     def apply_torques_at_task_dof(self, set_env_ids, torques):
02833 |         for name, task_obj in self._task.items():
02834 |             if name in torques.keys():
02835 |                 if isinstance(task_obj, Articulation):
02836 |                     task_obj.set_joint_effort_target(
02837 |                         torques[name][set_env_ids, :], env_ids=set_env_ids
02838 |                     )
02839 |                 else:
02840 |                     raise ValueError(f"Task {name} is not an articulation.")
```

### 原始 L2910–L2952

```text
02910 |     def simulate_at_each_physics_step(self):
02911 |         self._sim_step_counter += 1
02912 |         is_rendering = self.sim.has_gui() or self.sim.has_rtx_sensors()
02913 | 
02914 |         self.scene.write_data_to_sim()
02915 |         # simulate
02916 |         self.sim.step(render=False)
02917 |         # render between steps only if the GUI or an RTX sensor needs it
02918 |         # note: we assume the render interval to be the shortest accepted rendering interval.
02919 |         #    If a camera needs rendering at a faster frequency, this will lead to unexpected behavior.
02920 |         if self._sim_step_counter % self.simulator_config.sim.render_interval == 0 and is_rendering:
02921 |             self.sim.render()
02922 |         # update buffers at sim
02923 |         self.scene.update(dt=1.0 / self.simulator_config.sim.fps)
02924 | 
02925 |     def setup_viewer(self):
02926 |         self.viewer = self.viewport_camera_controller
02927 | 
02928 |     def render(self, sync_frame_time=True):
02929 |         pass
02930 | 
02931 |     def apply_commands(self, commands_description):
02932 |         if commands_description == "forward_command":
02933 |             self.commands[:, 0] += 0.1
02934 |             logger.info(f"Current Command: {self.commands[:, ]}")
02935 |         elif commands_description == "backward_command":
02936 |             self.commands[:, 0] -= 0.1
02937 |             logger.info(f"Current Command: {self.commands[:, ]}")
02938 |         elif commands_description == "left_command":
02939 |             self.commands[:, 1] -= 0.1
02940 |             logger.info(f"Current Command: {self.commands[:, ]}")
02941 |         elif commands_description == "right_command":
02942 |             self.commands[:, 1] += 0.1
02943 |             logger.info(f"Current Command: {self.commands[:, ]}")
02944 |         elif commands_description == "heading_left_command":
02945 |             self.commands[:, 3] -= 0.1
02946 |             logger.info(f"Current Command: {self.commands[:, ]}")
02947 |         elif commands_description == "heading_right_command":
02948 |             self.commands[:, 3] += 0.1
02949 |             logger.info(f"Current Command: {self.commands[:, ]}")
02950 |         elif commands_description == "zero_command":
02951 |             self.commands[:, :4] = 0
02952 |             logger.info(f"Current Command: {self.commands[:, ]}")
```

## S09 — `gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml`

### 原始 L1–L43

```text
00001 | # @package _global_
00002 | 
00003 | # Be careful when using _raw, history
00004 | obs:
00005 |   obs_dict:
00006 |     actor_obs: [
00007 |       dof_pos,
00008 |       relative_to_door,
00009 |       dof_vel,
00010 |       actions,
00011 |       projected_gravity,
00012 |       door_dof_pos,
00013 |       base_lin_vel,
00014 |       base_ang_vel,
00015 |       hand_force,
00016 |       stage,
00017 |       privileged_door_info,
00018 |       delta_actions,
00019 |       gripper_handle_transform,
00020 |       a2_base_command_raw,
00021 | 
00022 |       a2_base_command
00023 |     ]
00024 | 
00025 |     critic_obs: [
00026 |       dof_pos,
00027 |       relative_to_door,
00028 |       dof_vel,
00029 |       actions,
00030 |       projected_gravity,
00031 |       door_dof_pos,
00032 |       base_lin_vel,
00033 |       base_ang_vel,
00034 |       hand_force,
00035 |       stage,
00036 |       privileged_door_info,
00037 |       delta_actions,
00038 |       gripper_handle_transform,
00039 |       a2_base_command_raw,
00040 | 
00041 |       transition,
00042 |       complete,
00043 | 
```

### 原始 L201–L224

```text
00201 | 
00202 |   add_noise_currculum: False
00203 |   noise_initial_value: 0.05
00204 |   noise_value_max: 1.00
00205 |   noise_value_min: 0.00001
00206 |   soft_dof_pos_curriculum_degree: 0.00001
00207 |   soft_dof_pos_curriculum_level_down_threshold: 100
00208 |   soft_dof_pos_curriculum_level_up_threshold: 900
00209 | 
00210 |   obs_dims:
00211 |     - dof_pos: ${robot.dof_obs_size}
00212 |     - hand_force: 6
00213 |     - relative_to_door: 9
00214 |     - dof_vel: ${robot.dof_obs_size}
00215 |     # A2 Teacher actions parity: 12D A2_Base leg + 6D effective Piper arm + 1D gripper primitive; no base command.
00216 |     - actions: ${eval:'${env.config.a2_base.leg_action_dim} + ${algo.config.manipulation_action_dim}'}
00217 |     - projected_gravity: 3
00218 |     - door_dof_pos: 2
00219 |     - base_lin_vel: 3
00220 |     - base_ang_vel: 3
00221 |     - stage: ${eval:'len(${env.config.max_stage_time})'}
00222 |     - privileged_door_info: 8
00223 |     - gripper_handle_transform: 18
00224 |     - a2_base_command: 5
```

## S10 — `gr00t/rl/config/exp/wbmanip/door_open_a2_base_lstm.yaml`

### 原始 L51–L85

```text
00051 |     init_noise_std: 0.8
00052 |     max_noise_std: 0.8
00053 |     clamp_noise_std: True
00054 |     save_interval: 500
00055 | 
00056 |     gamma: 0.9975
00057 |     lam: 0.985
00058 | 
00059 |     init_at_random_ep_len: True
00060 | 
00061 |     actor:
00062 |       _target_: gr00t.rl.trl.modules.actor_critic_modules_recurrent.RecurrentActor
00063 |       running_mean_std: True
00064 |       rnn_type: "lstm"
00065 |       rnn_hidden_dim: 256
00066 |       rnn_num_layers: 2
00067 |       backbone:
00068 |         _target_: gr00t.rl.agents.modules.modules.BaseModule
00069 |         process_output_dim: True
00070 |         module_config_dict:
00071 |           input_dim: [actor_obs]
00072 |           output_dim:
00073 |             - ${eval:'${algo.config.base_command_dim} + ${algo.config.manipulation_action_dim}'}
00074 |           layer_config:
00075 |             type: MLP
00076 |             hidden_dims: [512, 256, 128]
00077 |             activation: SiLU
00078 |     critic:
00079 |       _target_: gr00t.rl.trl.modules.actor_critic_modules_recurrent.RecurrentCritic
00080 |       running_mean_std: True
00081 |       rnn_type: "lstm"
00082 |       rnn_hidden_dim: 256
00083 |       rnn_num_layers: 2
00084 |       backbone:
00085 |         _target_: gr00t.rl.agents.modules.modules.BaseModule
```

