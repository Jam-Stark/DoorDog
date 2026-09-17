# base_v28 step6000 readout

2026-09-16 04:37 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S283 | left/nominal | 61 / 64 / 64 / 64 / 64 / 64 / 29 | 0 | 0 | 0 | 1.0314 | CAMERA_UNMET |
| A_S283 | right/nominal | 55 / 64 / 64 / 64 / 4 / 4 / 2 | 24 | 0.0070088 | 0 | 1.4041 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S283 / left / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 29,
    "hinge_below_1p0472": 34,
    "body_contact_above_5N": 1,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 60.50865196060758,
    "wrist_cam_ang_speed_p95_deg_s": 226.07369984308792,
    "wrist_cam_axis_sweep_p95_deg_s": 178.6948895208614,
    "base_cam_ang_speed_p95_deg_s": 65.22269573978174,
    "wrist_cam_axis_elev_p5_deg": -46.089039292641274,
    "wrist_cam_axis_elev_p50_deg": -33.95166223462533,
    "wrist_cam_axis_elev_p95_deg": 10.616293765442112,
    "arm_posture_l1_p50_rad": 0.894667269771162,
    "post_release_return_time_p50_s": 0.9199999999999999,
    "handle_bearing_deg_p50_stage0_2": 10.728398323059082,
    "crossing_yaw_deg_p50": 159.1650390625,
    "arm_posture_l1_p95_rad": 5.58956478536129,
    "post_release_return_time_p95_s": 0.9600000000000001,
    "handle_bearing_deg_p95_stage0_2": 32.95411376953125,
    "crossing_yaw_deg_p95": 160.3791030883789,
    "wrist_cam_share_axis_sweep_gt_60": 0.2981649825960596,
    "arm_j6_reversals_per_s": 1.7373928946395347,
    "arm_j6_abs_dev_from_1p57_p95": 0.3548289012908936,
    "wrist_tower_panel_min_clearance_m": 0.008553098221405188,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.08069422079083916,
    "doorway_bearing_deg_p95_stage5": 164.73297119140625,
    "stage0_2_vy_cmd_at_clip_share": 0.4524959742351047,
    "handle_in_wrist_depth_share_stage2_4": 0.9978083392690812,
    "handle_in_wrist_rgb_share_stage2_4": 0.43449673990466275
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 383.83514573178,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 265.7648119126439,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 124.28931520884403,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 300.29168581936204,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.013579576317218444,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.9249350252255719,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 4.6202531645570355,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.3506332599116893,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 5.58956478536129,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.0559366244807265,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.9199999999999999,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.9600000000000001,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 10351,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 18,
      "right_censored_episodes": 46,
      "observed": {
        "min": 0.8000000000000007,
        "p5": 0.8170000000000004,
        "p50": 0.9199999999999999,
        "p95": 0.9600000000000001,
        "max": 0.9600000000000009
      },
      "censor_duration": {
        "min": 1.7000000000000002,
        "p5": 1.87,
        "p50": 2.16,
        "p95": 2.5200000000000005,
        "max": 2.580000000000001
      }
    }
  },
  "event_counts": {
    "all": 29591,
    "stage0_2": 5589,
    "stage5": 6605,
    "stage2_4": 18251,
    "stage0_5": 10351,
    "crossing_episodes": 64
  }
}
```

### A_S283 / right / nominal

```json
{
  "quality_components": {
    "complete": 4,
    "clean_complete": 2,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 2,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 4,
    "stage_overtime": 60
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 43.721926989863924,
    "wrist_cam_ang_speed_p95_deg_s": 133.07483068721737,
    "wrist_cam_axis_sweep_p95_deg_s": 101.27836764556805,
    "base_cam_ang_speed_p95_deg_s": 52.99096925816834,
    "wrist_cam_axis_elev_p5_deg": -63.87399531606458,
    "wrist_cam_axis_elev_p50_deg": -36.03658117496137,
    "wrist_cam_axis_elev_p95_deg": -10.00100731809993,
    "arm_posture_l1_p50_rad": 0.13392382860183716,
    "post_release_return_time_p50_s": 0.5999999999999996,
    "handle_bearing_deg_p50_stage0_2": 6.525119781494141,
    "crossing_yaw_deg_p50": 158.9154815673828,
    "arm_posture_l1_p95_rad": 1.8098208541241543,
    "post_release_return_time_p95_s": 0.5999999999999996,
    "handle_bearing_deg_p95_stage0_2": 27.167516708374013,
    "crossing_yaw_deg_p95": 160.45379714965821,
    "wrist_cam_share_axis_sweep_gt_60": 0.19606013478486262,
    "arm_j6_reversals_per_s": 2.0317269159705944,
    "arm_j6_abs_dev_from_1p57_p95": 0.27841751098632805,
    "wrist_tower_panel_min_clearance_m": -0.0005233441936161633,
    "wrist_tower_contact_step_share": 0.007008812856402281,
    "wrist_tower_contact_episodes_gt_5N": 24,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03420487106017192,
    "doorway_bearing_deg_p95_stage5": 177.8088409423828,
    "stage0_2_vy_cmd_at_clip_share": 0.3103510028653295,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.7612543196039974
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 158.39878742507847,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 346.27844976739874,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 108.02232073048496,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 277.7035923565909,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.05511160099200677,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 1.0687022900763359,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 4.475703324808255,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.224812089150811,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 1.8098208541241543,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.04159007352941176,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": 0.5999999999999996,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.5999999999999996,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 4352,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 1,
      "right_censored_episodes": 7,
      "observed": {
        "min": 0.5999999999999996,
        "p5": 0.5999999999999996,
        "p50": 0.5999999999999996,
        "p95": 0.5999999999999996,
        "max": 0.5999999999999996
      },
      "censor_duration": {
        "min": 2.92,
        "p5": 2.9979999999999998,
        "p50": 4.32,
        "p95": 7.897999999999999,
        "max": 8.780000000000001
      }
    }
  },
  "event_counts": {
    "all": 48225,
    "stage0_2": 5584,
    "stage5": 659,
    "stage2_4": 42828,
    "stage0_5": 4352,
    "crossing_episodes": 64
  }
}
```

## 决策与 K trace

```json
{
  "typed_outcomes": null,
  "invalid_cells": {},
  "k_driver_trace": {
    "A_S283": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s283/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 6000,
      "updates": 383928,
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
        "update_index": 383927,
        "common_step": 384000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 2,
        "natural_sample_right": 4,
        "natural_reached_left": 2,
        "natural_reached_right": 4,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s283_6000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s283_6000.json)；完整逐阶段指标见相邻 JSON。
