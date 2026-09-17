# base_v28 step4000 readout

2026-09-15 13:52 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S282 | left/nominal | 62 / 64 / 64 / 64 / 61 / 36 / 3 | 13 | 0.004801 | 1010 | 1.1132 | CAMERA_UNMET |
| A_S282 | right/nominal | 64 / 64 / 64 / 64 / 33 / 33 / 2 | 0 | 0 | 94.432 | 0.87381 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S282 / left / nominal

```json
{
  "quality_components": {
    "complete": 36,
    "clean_complete": 3,
    "hinge_below_1p0472": 17,
    "body_contact_above_5N": 33,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "stage_overtime": 28,
    "complete": 36
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 42.6826394907212,
    "wrist_cam_ang_speed_p95_deg_s": 171.18119422280589,
    "wrist_cam_axis_sweep_p95_deg_s": 142.96868158594123,
    "base_cam_ang_speed_p95_deg_s": 53.90460539533125,
    "wrist_cam_axis_elev_p5_deg": -55.82635921301053,
    "wrist_cam_axis_elev_p50_deg": -37.993056881314416,
    "wrist_cam_axis_elev_p95_deg": 26.795843986096152,
    "arm_posture_l1_p50_rad": 0.7241573331812106,
    "post_release_return_time_p50_s": 0.7299999999999995,
    "handle_bearing_deg_p50_stage0_2": 8.226525783538818,
    "crossing_yaw_deg_p50": 155.6590576171875,
    "arm_posture_l1_p95_rad": 4.655685447156429,
    "post_release_return_time_p95_s": 1.907000000000001,
    "handle_bearing_deg_p95_stage0_2": 31.14366302490231,
    "crossing_yaw_deg_p95": 157.150390625,
    "wrist_cam_share_axis_sweep_gt_60": 0.2798641663460413,
    "arm_j6_reversals_per_s": 1.1119484216703412,
    "arm_j6_abs_dev_from_1p57_p95": 0.42229375958442694,
    "wrist_tower_panel_min_clearance_m": 0.06902010597270901,
    "wrist_tower_contact_step_share": 0.0048010170795764395,
    "wrist_tower_contact_episodes_gt_5N": 13,
    "handle_bearing_gt_30deg_share_stage0_2": 0.059441764300482425,
    "doorway_bearing_deg_p95_stage5": 176.10128784179688,
    "stage0_2_vy_cmd_at_clip_share": 0.3559614059269469,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.3128107766024772
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 114.16499021404366,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 306.4856438655177,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 59.51546511165658,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 204.1499261227114,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.03864983251739158,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.35516605166060694,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.4858757062147303,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.5853743148552948,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 4.655685447156429,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.09405902047808144,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.7299999999999995,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 1.907000000000001,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 25686,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 32,
      "right_censored_episodes": 0,
      "observed": {
        "min": 0.40000000000000036,
        "p5": 0.41999999999999993,
        "p50": 0.7299999999999995,
        "p95": 1.907000000000001,
        "max": 2.1799999999999997
      },
      "censor_duration": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      }
    }
  },
  "event_counts": {
    "all": 59779,
    "stage0_2": 5804,
    "stage5": 21741,
    "stage2_4": 33183,
    "stage0_5": 25686,
    "crossing_episodes": 61
  }
}
```

### A_S282 / right / nominal

```json
{
  "quality_components": {
    "complete": 33,
    "clean_complete": 2,
    "hinge_below_1p0472": 30,
    "body_contact_above_5N": 8,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "stage_overtime": 31,
    "complete": 33
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 70.63388995448564,
    "wrist_cam_ang_speed_p95_deg_s": 173.15613968033819,
    "wrist_cam_axis_sweep_p95_deg_s": 128.33194054096398,
    "base_cam_ang_speed_p95_deg_s": 60.27673632657189,
    "wrist_cam_axis_elev_p5_deg": -39.95473613283934,
    "wrist_cam_axis_elev_p50_deg": -28.556262633504925,
    "wrist_cam_axis_elev_p95_deg": -2.787814913206696,
    "arm_posture_l1_p50_rad": 0.7431102375212504,
    "post_release_return_time_p50_s": 1.42,
    "handle_bearing_deg_p50_stage0_2": 5.167898654937744,
    "crossing_yaw_deg_p50": 167.6932830810547,
    "arm_posture_l1_p95_rad": 4.035311585664752,
    "post_release_return_time_p95_s": 4.12,
    "handle_bearing_deg_p95_stage0_2": 26.47933826446533,
    "crossing_yaw_deg_p95": 173.41888427734375,
    "wrist_cam_share_axis_sweep_gt_60": 0.32952600711470054,
    "arm_j6_reversals_per_s": 3.657996573037105,
    "arm_j6_abs_dev_from_1p57_p95": 0.5168712091445924,
    "wrist_tower_panel_min_clearance_m": 0.012565378813824375,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.031662746517097884,
    "doorway_bearing_deg_p95_stage5": 155.5337112426758,
    "stage0_2_vy_cmd_at_clip_share": 0.2384657137687715,
    "handle_in_wrist_depth_share_stage2_4": 0.9946203692382932,
    "handle_in_wrist_rgb_share_stage2_4": 0.646533806088764
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 260.80506051510656,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 174.25296870971775,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 141.77712785082664,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 295.29636778272237,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.05319148936170059,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.1175180194296584,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 7.421875000000117,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 4.697568635947645,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 4.035311585664752,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.3090145522023635,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 1.42,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 4.12,
        "limit": 4.0,
        "pass": false
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 10239,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 17,
      "right_censored_episodes": 17,
      "observed": {
        "min": 1.0999999999999996,
        "p5": 1.1639999999999997,
        "p50": 1.42,
        "p95": 4.12,
        "max": 4.280000000000001
      },
      "censor_duration": {
        "min": 0.2400000000000002,
        "p5": 2.5760000000000005,
        "p50": 3.700000000000001,
        "p95": 4.4879999999999995,
        "max": 5.0
      }
    }
  },
  "event_counts": {
    "all": 52005,
    "stage0_2": 5527,
    "stage5": 6415,
    "stage2_4": 40895,
    "stage0_5": 10239,
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
    "A_S282": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s282/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 4000,
      "updates": 255955,
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
        "update_index": 255954,
        "common_step": 256000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 0.75,
        "natural_sample_left": 1,
        "natural_sample_right": 4,
        "natural_reached_left": 1,
        "natural_reached_right": 3,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s282_4000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s282_4000.json)；完整逐阶段指标见相邻 JSON。
