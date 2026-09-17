# base_v28 step4000 readout

2026-09-15 14:13 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S283 | left/nominal | 64 / 64 / 64 / 64 / 0 / 0 / 0 | 0 | 0 | 0 | 0.98622 | CAMERA_UNMET |
| A_S283 | right/nominal | 64 / 64 / 64 / 64 / 7 / 0 / 0 | 26 | 0.051004 | 649.73 | 1.375 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S283 / left / nominal

```json
{
  "quality_components": {
    "complete": 0,
    "clean_complete": 0,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "stage_overtime": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 44.86975618266827,
    "wrist_cam_ang_speed_p95_deg_s": 111.57706894718726,
    "wrist_cam_axis_sweep_p95_deg_s": 86.13587789216422,
    "base_cam_ang_speed_p95_deg_s": 52.646417278928524,
    "wrist_cam_axis_elev_p5_deg": -44.96414028701428,
    "wrist_cam_axis_elev_p50_deg": -28.596404539268242,
    "wrist_cam_axis_elev_p95_deg": -13.257359566288468,
    "arm_posture_l1_p50_rad": 0.12783349584788084,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 13.133829116821289,
    "crossing_yaw_deg_p50": 159.82906341552734,
    "arm_posture_l1_p95_rad": 0.16816163538023826,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 33.45102500915527,
    "crossing_yaw_deg_p95": 161.76438827514647,
    "wrist_cam_share_axis_sweep_gt_60": 0.15142158488063662,
    "arm_j6_reversals_per_s": 2.0376826029228923,
    "arm_j6_abs_dev_from_1p57_p95": 0.005947690010070737,
    "wrist_tower_panel_min_clearance_m": 0.009631309976695479,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.08598097289535092,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.40854424699335845,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.4632638521821065
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 132.5604792063063,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 294.7066251680909,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 97.88187910255385,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.05372011818425833,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.7853403141361379,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.3395413267674683,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.16816163538023826,
        "limit": 0.5,
        "pass": true
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.0,
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
    "posture_frame_denominator": 3787,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 3,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 2.540000000000001,
        "p5": 2.674000000000001,
        "p50": 3.880000000000001,
        "p95": 3.880000000000001,
        "max": 3.880000000000001
      }
    }
  },
  "event_counts": {
    "all": 48256,
    "stage0_2": 5571,
    "stage5": 0,
    "stage2_4": 43513,
    "stage0_5": 3787,
    "crossing_episodes": 64
  }
}
```

### A_S283 / right / nominal

```json
{
  "quality_components": {
    "complete": 0,
    "clean_complete": 0,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "stage_overtime": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 42.373317649209305,
    "wrist_cam_ang_speed_p95_deg_s": 116.33177750191066,
    "wrist_cam_axis_sweep_p95_deg_s": 96.9039103936127,
    "base_cam_ang_speed_p95_deg_s": 49.70668299083474,
    "wrist_cam_axis_elev_p5_deg": -45.635546726210606,
    "wrist_cam_axis_elev_p50_deg": -24.429353701533454,
    "wrist_cam_axis_elev_p95_deg": -7.490505851146354,
    "arm_posture_l1_p50_rad": 0.164993098936975,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 9.579386234283447,
    "crossing_yaw_deg_p50": 159.78369140625,
    "arm_posture_l1_p95_rad": 2.526148549625941,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 26.858970260620133,
    "crossing_yaw_deg_p95": 161.07420349121094,
    "wrist_cam_share_axis_sweep_gt_60": 0.19288001127600024,
    "arm_j6_reversals_per_s": 3.1200225811023587,
    "arm_j6_abs_dev_from_1p57_p95": 0.5245664405822753,
    "wrist_tower_panel_min_clearance_m": -0.0014686658197784093,
    "wrist_tower_contact_step_share": 0.051003765378652116,
    "wrist_tower_contact_episodes_gt_5N": 26,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03280701754385965,
    "doorway_bearing_deg_p95_stage5": 167.73976135253906,
    "stage0_2_vy_cmd_at_clip_share": 0.26859649122807017,
    "handle_in_wrist_depth_share_stage2_4": 0.9900784659782013,
    "handle_in_wrist_rgb_share_stage2_4": 0.9362493739416633
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 116.33461438154828,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 265.7190271484035,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 102.75443421862515,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 138.84854975590903,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.04061738424045357,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.08535336292250195,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.4463007159904926,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.8381538634530497,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 2.526148549625941,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.41132526520245033,
        "limit": 0.05,
        "pass": false
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
    "posture_frame_denominator": 6693,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 19,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 0.20000000000000107,
        "p5": 1.262000000000001,
        "p50": 5.460000000000001,
        "p95": 10.005999999999998,
        "max": 11.320000000000002
      }
    }
  },
  "event_counts": {
    "all": 49663,
    "stage0_2": 5700,
    "stage5": 2936,
    "stage2_4": 41929,
    "stage0_5": 6693,
    "crossing_episodes": 63
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
      "through_batch": 4000,
      "updates": 255952,
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
        "update_index": 255951,
        "common_step": 256000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 1,
        "natural_sample_right": 5,
        "natural_reached_left": 1,
        "natural_reached_right": 5,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s283_4000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s283_4000.json)；完整逐阶段指标见相邻 JSON。
