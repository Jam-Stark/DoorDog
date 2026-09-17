# base_v28 step1000 readout

2026-09-16 11:03 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S284 | left/nominal | 0 / 0 / 0 / 0 / 0 / 0 / 0 | 0 | 0 | null | null | CAMERA_PARTIAL |
| A_S284 | right/nominal | 2 / 3 / 0 / 0 / 0 / 0 / 0 | 0 | 0 | null | null | CAMERA_PARTIAL |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S284 / left / nominal

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
    "wrist_cam_ang_speed_p50_deg_s": 20.56787488156494,
    "wrist_cam_ang_speed_p95_deg_s": 67.31635156314046,
    "wrist_cam_axis_sweep_p95_deg_s": 53.408490095781424,
    "base_cam_ang_speed_p95_deg_s": 42.028742850694236,
    "wrist_cam_axis_elev_p5_deg": -27.344774780357323,
    "wrist_cam_axis_elev_p50_deg": -17.75601237957521,
    "wrist_cam_axis_elev_p95_deg": -12.040233356780686,
    "arm_posture_l1_p50_rad": 0.13145138882100582,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 9.780665397644043,
    "crossing_yaw_deg_p50": null,
    "arm_posture_l1_p95_rad": 0.17508963081054388,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 16.581560993194582,
    "crossing_yaw_deg_p95": null,
    "wrist_cam_share_axis_sweep_gt_60": 0.03597712862318841,
    "arm_j6_reversals_per_s": 0.3076792196008799,
    "arm_j6_abs_dev_from_1p57_p95": 0.0059144811630248645,
    "wrist_tower_panel_min_clearance_m": 0.12717324737457564,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.010303442028985508,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.06377377717391304,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.966096050089922
  },
  "camera_targets": {
    "outcome": "CAMERA_PARTIAL",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 45.65001787125642,
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
        "value": 0.05589090096132391,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.3370936519592927,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": null,
        "limit": 2.5,
        "pass": null
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.17508963081054388,
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
    "posture_frame_denominator": 4537,
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
    "stage2_4": 30026,
    "stage0_5": 4537,
    "crossing_episodes": 0
  }
}
```

### A_S284 / right / nominal

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
    "wrist_cam_ang_speed_p50_deg_s": 32.01825173756883,
    "wrist_cam_ang_speed_p95_deg_s": 84.96583630699044,
    "wrist_cam_axis_sweep_p95_deg_s": 72.79480536468242,
    "base_cam_ang_speed_p95_deg_s": 50.97741603857692,
    "wrist_cam_axis_elev_p5_deg": -28.120473730749374,
    "wrist_cam_axis_elev_p50_deg": -20.01941672305021,
    "wrist_cam_axis_elev_p95_deg": -13.462733865541141,
    "arm_posture_l1_p50_rad": 0.13386868522502482,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 3.892556667327881,
    "crossing_yaw_deg_p50": null,
    "arm_posture_l1_p95_rad": 0.17273788049351424,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 11.42628526687622,
    "crossing_yaw_deg_p95": null,
    "wrist_cam_share_axis_sweep_gt_60": 0.09797648115405125,
    "arm_j6_reversals_per_s": 0.8926814181689768,
    "arm_j6_abs_dev_from_1p57_p95": 0.006041525602340636,
    "wrist_tower_panel_min_clearance_m": 0.12395311384633388,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.005818642700771978,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.02241041594653762,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.9654632651701859
  },
  "camera_targets": {
    "outcome": "CAMERA_PARTIAL",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 70.25709706054926,
        "limit": 105,
        "pass": true
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 51.41501504066897,
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
        "value": 0.04304778303917411,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 1.0620718146456691,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": null,
        "limit": 2.5,
        "pass": null
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.17273788049351424,
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
    "posture_frame_denominator": 4710,
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
    "all": 35631,
    "stage0_2": 34716,
    "stage5": 0,
    "stage2_4": 30026,
    "stage0_5": 4710,
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
    "A_S284": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s284/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 1000,
      "updates": 63986,
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
        "update_index": 63985,
        "common_step": 64000,
        "scale_before": 1.0,
        "scale_after": 1.0,
        "driver_left": 0.0,
        "driver_right": 0.0,
        "natural_sample_left": 4,
        "natural_sample_right": 3,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s284_1000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s284_1000.json)；完整逐阶段指标见相邻 JSON。
