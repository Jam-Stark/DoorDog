# base_v28 step1000 readout

2026-09-14 18:07 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S281 | left/nominal | 0 / 0 / 0 / 0 / 0 / 0 / 0 | 0 | 0 | null | null | CAMERA_PARTIAL |
| A_S281 | right/nominal | 0 / 0 / 0 / 0 / 0 / 0 / 0 | 0 | 0 | null | null | CAMERA_PARTIAL |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S281 / left / nominal

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
    "wrist_cam_ang_speed_p50_deg_s": 29.331898789487443,
    "wrist_cam_ang_speed_p95_deg_s": 69.85876414475686,
    "wrist_cam_axis_sweep_p95_deg_s": 57.24067210663092,
    "base_cam_ang_speed_p95_deg_s": 44.91524154386793,
    "wrist_cam_axis_elev_p5_deg": -33.98078997298082,
    "wrist_cam_axis_elev_p50_deg": -28.362313010444566,
    "wrist_cam_axis_elev_p95_deg": -16.906279369927326,
    "arm_posture_l1_p50_rad": 0.13508567749522626,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 7.354429721832275,
    "crossing_yaw_deg_p50": null,
    "arm_posture_l1_p95_rad": 0.1645351956598461,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 15.204985284805302,
    "crossing_yaw_deg_p95": null,
    "wrist_cam_share_axis_sweep_gt_60": 0.043025362318840576,
    "arm_j6_reversals_per_s": 0.8081896551728182,
    "arm_j6_abs_dev_from_1p57_p95": 0.004694361209869391,
    "wrist_tower_panel_min_clearance_m": 0.13042237843297474,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.010614809782608696,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.038892663043478264,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.9992231304465311
  },
  "camera_targets": {
    "outcome": "CAMERA_PARTIAL",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 55.10167644096887,
        "limit": 105,
        "pass": true
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 250,
        "pass": null
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 150,
        "pass": null
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.08288437629507016,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.9308780718980298,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": null,
        "limit": 2.5,
        "pass": null
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.1645351956598461,
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
    "posture_frame_denominator": 4890,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 0,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
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
    "all": 35328,
    "stage0_2": 35328,
    "stage5": 0,
    "stage2_4": 29606,
    "stage0_5": 4890,
    "crossing_episodes": 0
  }
}
```

### A_S281 / right / nominal

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
    "wrist_cam_ang_speed_p50_deg_s": 33.72299673203612,
    "wrist_cam_ang_speed_p95_deg_s": 79.15100758246062,
    "wrist_cam_axis_sweep_p95_deg_s": 64.30905838909004,
    "base_cam_ang_speed_p95_deg_s": 51.97645348299111,
    "wrist_cam_axis_elev_p5_deg": -35.07881845461144,
    "wrist_cam_axis_elev_p50_deg": -28.61191803307989,
    "wrist_cam_axis_elev_p95_deg": -15.149266063661127,
    "arm_posture_l1_p50_rad": 0.13556585717014968,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 4.983945369720459,
    "crossing_yaw_deg_p50": null,
    "arm_posture_l1_p95_rad": 0.17007727054879068,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 13.670165348052981,
    "crossing_yaw_deg_p95": null,
    "wrist_cam_share_axis_sweep_gt_60": 0.06091485507246377,
    "arm_j6_reversals_per_s": 1.1257940108898554,
    "arm_j6_abs_dev_from_1p57_p95": 0.005879323482513364,
    "wrist_tower_panel_min_clearance_m": 0.12575751131612553,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.005066802536231884,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.029438405797101448,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.997723102018623
  },
  "camera_targets": {
    "outcome": "CAMERA_PARTIAL",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 61.33442601318744,
        "limit": 105,
        "pass": true
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 250,
        "pass": null
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 150,
        "pass": null
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.039541320680111895,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 1.3418704447931509,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": null,
        "limit": 2.5,
        "pass": null
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.17007727054879068,
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
    "posture_frame_denominator": 5122,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 0,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
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
    "all": 35328,
    "stage0_2": 35328,
    "stage5": 0,
    "stage2_4": 29426,
    "stage0_5": 5122,
    "crossing_episodes": 0
  }
}
```

## 决策与 K trace

```json
{
  "typed_outcomes": null,
  "invalid_cells": {},
  "k_driver_trace": {
    "A_S281": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s281/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 1000,
      "updates": 63997,
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
        "update_index": 63996,
        "common_step": 64000,
        "scale_before": 1.0,
        "scale_after": 1.0,
        "driver_left": 0.0,
        "driver_right": 0.0,
        "natural_sample_left": 3,
        "natural_sample_right": 6,
        "natural_reached_left": 0,
        "natural_reached_right": 0,
        "consumed": true,
        "skipped": false
      },
      "scale_min": 1.0,
      "scale_max": 1.0,
      "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."
    }
  }
}
```

针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s281_1000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s281_1000.json)；完整逐阶段指标见相邻 JSON。
