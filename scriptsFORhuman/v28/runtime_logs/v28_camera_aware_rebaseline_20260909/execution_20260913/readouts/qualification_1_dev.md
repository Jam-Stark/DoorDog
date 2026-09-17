# base_v28 step5000 readout

2026-09-17 17:19 HKT

状态：`V28_COMPLETE`；每侧 exact 128。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S284 | left/nominal | 127 / 128 / 128 / 128 / 128 / 128 / 69 | 0 | 0 | 0 | 1.0738 | CAMERA_UNMET |
| A_S284 | right/nominal | 126 / 127 / 126 / 126 / 126 / 126 / 52 | 1 | 4.0563e-05 | 0 | 0.99758 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S284 / left / nominal

```json
{
  "quality_components": {
    "complete": 128,
    "clean_complete": 69,
    "hinge_below_1p0472": 59,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 128
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 66.37036428766903,
    "wrist_cam_ang_speed_p95_deg_s": 229.93148115418018,
    "wrist_cam_axis_sweep_p95_deg_s": 167.75105866062276,
    "base_cam_ang_speed_p95_deg_s": 78.38393618642687,
    "wrist_cam_axis_elev_p5_deg": -46.06332561378213,
    "wrist_cam_axis_elev_p50_deg": -35.36942562691508,
    "wrist_cam_axis_elev_p95_deg": -14.13090024057353,
    "arm_posture_l1_p50_rad": 1.0692158998863306,
    "post_release_return_time_p50_s": 0.43000000000000016,
    "handle_bearing_deg_p50_stage0_2": 6.521224498748779,
    "crossing_yaw_deg_p50": 163.75607299804688,
    "arm_posture_l1_p95_rad": 4.357043884694567,
    "post_release_return_time_p95_s": 0.4390000000000004,
    "handle_bearing_deg_p95_stage0_2": 28.999725723266593,
    "crossing_yaw_deg_p95": 167.51849441528321,
    "wrist_cam_share_axis_sweep_gt_60": 0.3374434996449786,
    "arm_j6_reversals_per_s": 2.8864011108237353,
    "arm_j6_abs_dev_from_1p57_p95": 0.5226245689392089,
    "wrist_tower_panel_min_clearance_m": 0.009410845010600574,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.04371926687527939,
    "doorway_bearing_deg_p95_stage5": 178.8194664001465,
    "stage0_2_vy_cmd_at_clip_share": 0.3531515422440769,
    "handle_in_wrist_depth_share_stage2_4": 0.9937723855312833,
    "handle_in_wrist_rgb_share_stage2_4": 0.46416701623051854
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 198.75544909607663,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 235.5865751240424,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 142.3167452869702,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 319.2242235314146,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.09663703131039465,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 1.1211552007514218,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 20.01361470388056,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 4.208892147139929,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 4.357043884694567,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.5539057198738674,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.43000000000000016,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.4390000000000004,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 25053,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 2,
      "right_censored_episodes": 126,
      "observed": {
        "min": 0.41999999999999993,
        "p5": 0.42099999999999993,
        "p50": 0.43000000000000016,
        "p95": 0.4390000000000004,
        "max": 0.4400000000000004
      },
      "censor_duration": {
        "min": 2.460000000000001,
        "p5": 2.54,
        "p50": 2.7200000000000006,
        "p95": 3.04,
        "max": 3.74
      }
    }
  },
  "event_counts": {
    "all": 57743,
    "stage0_2": 11185,
    "stage5": 17164,
    "stage2_4": 30991,
    "stage0_5": 25053,
    "crossing_episodes": 128
  }
}
```

### A_S284 / right / nominal

```json
{
  "quality_components": {
    "complete": 126,
    "clean_complete": 52,
    "hinge_below_1p0472": 74,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 1
  },
  "terminal_reasons": {
    "complete": 126,
    "stage_overtime": 1,
    "upper_dof_overspeed": 1
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 90.28846308998618,
    "wrist_cam_ang_speed_p95_deg_s": 231.02788295945984,
    "wrist_cam_axis_sweep_p95_deg_s": 177.71519334287925,
    "base_cam_ang_speed_p95_deg_s": 90.97408819742466,
    "wrist_cam_axis_elev_p5_deg": -54.45954017219565,
    "wrist_cam_axis_elev_p50_deg": -30.677421275872206,
    "wrist_cam_axis_elev_p95_deg": -13.758896645868468,
    "arm_posture_l1_p50_rad": 0.867690766326632,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 6.2675392627716064,
    "crossing_yaw_deg_p50": 178.8067626953125,
    "arm_posture_l1_p95_rad": 2.5844280600547798,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 29.47741565704344,
    "crossing_yaw_deg_p95": 179.92221450805664,
    "wrist_cam_share_axis_sweep_gt_60": 0.5821401046525778,
    "arm_j6_reversals_per_s": 3.6428890967528194,
    "arm_j6_abs_dev_from_1p57_p95": 0.23220387816429147,
    "wrist_tower_panel_min_clearance_m": -1.583227266878373e-05,
    "wrist_tower_contact_step_share": 4.056301464324829e-05,
    "wrist_tower_contact_episodes_gt_5N": 1,
    "handle_bearing_gt_30deg_share_stage0_2": 0.04473007712082262,
    "doorway_bearing_deg_p95_stage5": 89.2009220123291,
    "stage0_2_vy_cmd_at_clip_share": 0.1814910025706941,
    "handle_in_wrist_depth_share_stage2_4": 0.9972222222222222,
    "handle_in_wrist_rgb_share_stage2_4": 0.5711720867208672
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 244.065345801692,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 257.3301647053221,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 174.63862595291164,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 336.41792425244273,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.04879238838740857,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.7314524555902961,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 23.64074328974579,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 5.325581395350094,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 2.5844280600547798,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.02430362889801354,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": null,
        "limit": 2.0,
        "pass": null
      },
      "post_release_return_p95_s": {
        "value": null,
        "limit": 4.0,
        "pass": null
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 18022,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 126,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 1.2400000000000002,
        "p5": 1.42,
        "p50": 1.58,
        "p95": 1.8150000000000002,
        "max": 1.9399999999999995
      }
    }
  },
  "event_counts": {
    "all": 49306,
    "stage0_2": 11670,
    "stage5": 9696,
    "stage2_4": 29520,
    "stage0_5": 18022,
    "crossing_episodes": 126
  }
}
```

## 决策与 K trace

```json
{
  "typed_outcomes": null,
  "invalid_cells": {},
  "k_driver_trace": {
    "A_S284": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s284/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 5000,
      "updates": 319941,
      "first": {
        "update_index": 0,
        "common_step": 0,
        "scale_before": 1.0,
        "scale_after": 1.0,
        "driver_left": null,
        "driver_right": null,
        "natural_sample_left": 0,
        "natural_sample_right": 0,
        "natural_reached_left": 0,
        "natural_reached_right": 0,
        "consumed": false,
        "skipped": true
      },
      "last": {
        "update_index": 319940,
        "common_step": 320000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 4,
        "natural_sample_right": 6,
        "natural_reached_left": 4,
        "natural_reached_right": 6,
        "consumed": true,
        "skipped": false
      },
      "scale_min": 0.20000000298023224,
      "scale_max": 1.0,
      "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."
    }
  }
}
```

针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/qualification_1_dev.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/qualification_1_dev.json)；完整逐阶段指标见相邻 JSON。
