# base_v28 step3000 readout

2026-09-15 07:08 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S283 | left/nominal | 62 / 64 / 64 / 64 / 0 / 0 / 0 | 3 | 0.00053879 | 0 | 1.1131 | CAMERA_PARTIAL |
| A_S283 | right/nominal | 17 / 17 / 0 / 0 / 0 / 0 / 0 | 0 | 0 | null | null | CAMERA_PARTIAL |

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
    "wrist_cam_ang_speed_p50_deg_s": 40.01494619230968,
    "wrist_cam_ang_speed_p95_deg_s": 102.00706621975752,
    "wrist_cam_axis_sweep_p95_deg_s": 79.68875704091758,
    "base_cam_ang_speed_p95_deg_s": 50.812745838846226,
    "wrist_cam_axis_elev_p5_deg": -40.39571962725747,
    "wrist_cam_axis_elev_p50_deg": -25.80877040976108,
    "wrist_cam_axis_elev_p95_deg": -13.955841371748576,
    "arm_posture_l1_p50_rad": 0.12543849926441908,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 8.355619430541992,
    "crossing_yaw_deg_p50": 157.89224243164062,
    "arm_posture_l1_p95_rad": 0.16616881601512432,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 31.48480415344238,
    "crossing_yaw_deg_p95": 158.34138031005858,
    "wrist_cam_share_axis_sweep_gt_60": 0.11039041777188328,
    "arm_j6_reversals_per_s": 1.6133383134140007,
    "arm_j6_abs_dev_from_1p57_p95": 0.005555059671401991,
    "wrist_tower_panel_min_clearance_m": -5.3970308199469824e-05,
    "wrist_tower_contact_step_share": 0.0005387931034482759,
    "wrist_tower_contact_episodes_gt_5N": 3,
    "handle_bearing_gt_30deg_share_stage0_2": 0.062100606259216776,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.27232508602326727,
    "handle_in_wrist_depth_share_stage2_4": 0.9987835108336394,
    "handle_in_wrist_rgb_share_stage2_4": 0.5549256334924716
  },
  "camera_targets": {
    "outcome": "CAMERA_PARTIAL",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 94.20036946922117,
        "limit": 105,
        "pass": true
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 197.48310693130006,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 87.45712346568503,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.04006410256410137,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.8882309400444277,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.7780539037315224,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.16616881601512432,
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
    "posture_frame_denominator": 3808,
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
    "all": 48256,
    "stage0_2": 6103,
    "stage5": 0,
    "stage2_4": 43568,
    "stage0_5": 3808,
    "crossing_episodes": 35
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
    "wrist_cam_ang_speed_p50_deg_s": 28.291766967317823,
    "wrist_cam_ang_speed_p95_deg_s": 88.57575120126361,
    "wrist_cam_axis_sweep_p95_deg_s": 77.04189259881296,
    "base_cam_ang_speed_p95_deg_s": 46.936039494238756,
    "wrist_cam_axis_elev_p5_deg": -37.037491767391806,
    "wrist_cam_axis_elev_p50_deg": -30.17725972037474,
    "wrist_cam_axis_elev_p95_deg": -13.0004674917641,
    "arm_posture_l1_p50_rad": 0.12719155990635045,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 1.8489025831222534,
    "crossing_yaw_deg_p50": null,
    "arm_posture_l1_p95_rad": 0.17470781648080447,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 12.17130279541015,
    "crossing_yaw_deg_p95": null,
    "wrist_cam_share_axis_sweep_gt_60": 0.09939263058442435,
    "arm_j6_reversals_per_s": 0.3623482328765304,
    "arm_j6_abs_dev_from_1p57_p95": 0.005995236635208068,
    "wrist_tower_panel_min_clearance_m": 0.07038224705792571,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.005157740909481647,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.02790910914352847,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.9893315244203256
  },
  "camera_targets": {
    "outcome": "CAMERA_PARTIAL",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 71.57612502744962,
        "limit": 105,
        "pass": true
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 185.0696452272637,
        "limit": 250,
        "pass": true
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
        "value": 0.027685492801770812,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.2001852954802004,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": null,
        "limit": 2.5,
        "pass": null
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.17470781648080447,
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
    "posture_frame_denominator": 3676,
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
    "all": 37045,
    "stage0_2": 34899,
    "stage5": 0,
    "stage2_4": 32432,
    "stage0_5": 3676,
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
    "A_S283": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s283/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 3000,
      "updates": 191973,
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
        "update_index": 191972,
        "common_step": 192000,
        "scale_before": 1.0,
        "scale_after": 1.0,
        "driver_left": 1.0,
        "driver_right": 0.0,
        "natural_sample_left": 3,
        "natural_sample_right": 4,
        "natural_reached_left": 3,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s283_3000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s283_3000.json)；完整逐阶段指标见相邻 JSON。
