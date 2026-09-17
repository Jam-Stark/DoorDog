# base_v28 step5000 readout

2026-09-15 21:12 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S283 | left/nominal | 64 / 64 / 64 / 64 / 0 / 0 / 0 | 0 | 0 | 0 | 0.85877 | CAMERA_UNMET |
| A_S283 | right/nominal | 61 / 64 / 64 / 64 / 0 / 0 / 0 | 16 | 0.011853 | 0 | 1.3425 | CAMERA_UNMET |

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
    "wrist_cam_ang_speed_p50_deg_s": 51.903833246734095,
    "wrist_cam_ang_speed_p95_deg_s": 125.09627209434248,
    "wrist_cam_axis_sweep_p95_deg_s": 94.08002796477457,
    "base_cam_ang_speed_p95_deg_s": 63.423994347020596,
    "wrist_cam_axis_elev_p5_deg": -49.42049380008571,
    "wrist_cam_axis_elev_p50_deg": -34.753338700337736,
    "wrist_cam_axis_elev_p95_deg": -14.977305767980473,
    "arm_posture_l1_p50_rad": 0.12745401554275304,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 11.231229782104492,
    "crossing_yaw_deg_p50": 158.8684844970703,
    "arm_posture_l1_p95_rad": 0.16681900974363087,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 32.70525588989258,
    "crossing_yaw_deg_p95": 160.0911781311035,
    "wrist_cam_share_axis_sweep_gt_60": 0.1954782824933687,
    "arm_j6_reversals_per_s": 2.162184594954841,
    "arm_j6_abs_dev_from_1p57_p95": 0.005727999210357598,
    "wrist_tower_panel_min_clearance_m": 0.011177515463176763,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.07767334633800319,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.4342968611455932,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.46163039231458713
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 175.64061242995794,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 330.80249263559415,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 115.43015901522264,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.0537778972842145,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.469879518072329,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.4417836078923227,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.16681900974363087,
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
    "posture_frame_denominator": 3783,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 1,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 4.58,
        "p5": 4.58,
        "p50": 4.58,
        "p95": 4.58,
        "max": 4.58
      }
    }
  },
  "event_counts": {
    "all": 48256,
    "stage0_2": 5639,
    "stage5": 0,
    "stage2_4": 43511,
    "stage0_5": 3783,
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
    "wrist_cam_ang_speed_p50_deg_s": 44.30007677525546,
    "wrist_cam_ang_speed_p95_deg_s": 127.1564690191976,
    "wrist_cam_axis_sweep_p95_deg_s": 93.18314289448597,
    "base_cam_ang_speed_p95_deg_s": 50.6165135240297,
    "wrist_cam_axis_elev_p5_deg": -53.14981813933603,
    "wrist_cam_axis_elev_p50_deg": -32.20731006293988,
    "wrist_cam_axis_elev_p95_deg": -10.759975273462345,
    "arm_posture_l1_p50_rad": 0.12586317991372198,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 7.23773980140686,
    "crossing_yaw_deg_p50": 160.61450958251953,
    "arm_posture_l1_p95_rad": 0.17188728039263879,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 27.226088523864707,
    "crossing_yaw_deg_p95": 162.31939468383788,
    "wrist_cam_share_axis_sweep_gt_60": 0.18308604111405835,
    "arm_j6_reversals_per_s": 2.313662018593712,
    "arm_j6_abs_dev_from_1p57_p95": 0.0052327144145964954,
    "wrist_tower_panel_min_clearance_m": -0.0007926178480609988,
    "wrist_tower_contact_step_share": 0.011853448275862068,
    "wrist_tower_contact_episodes_gt_5N": 16,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03473459209120057,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.2892768079800499,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.8049430356486585
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 130.76387333409414,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 353.29821873864864,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 114.55659391618329,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.041299559471364114,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 1.566265060240989,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.6307664599803258,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.17188728039263879,
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
    "posture_frame_denominator": 3696,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 5,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 4.220000000000001,
        "p5": 4.392,
        "p50": 5.780000000000001,
        "p95": 9.443999999999999,
        "max": 9.82
      }
    }
  },
  "event_counts": {
    "all": 48256,
    "stage0_2": 5614,
    "stage5": 0,
    "stage2_4": 43536,
    "stage0_5": 3696,
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
      "through_batch": 5000,
      "updates": 319936,
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
        "update_index": 319935,
        "common_step": 320000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 2,
        "natural_sample_right": 2,
        "natural_reached_left": 2,
        "natural_reached_right": 2,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s283_5000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s283_5000.json)；完整逐阶段指标见相邻 JSON。
