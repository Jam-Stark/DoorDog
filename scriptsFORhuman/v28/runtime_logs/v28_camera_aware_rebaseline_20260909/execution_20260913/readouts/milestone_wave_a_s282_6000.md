# base_v28 step6000 readout

2026-09-16 03:51 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S282 | left/nominal | 56 / 64 / 63 / 63 / 62 / 62 / 61 | 0 | 0 | 0 | 1.5617 | CAMERA_UNMET |
| A_S282 | right/nominal | 64 / 64 / 64 / 64 / 64 / 64 / 12 | 0 | 0 | 0 | 0.95449 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S282 / left / nominal

```json
{
  "quality_components": {
    "complete": 62,
    "clean_complete": 61,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 1,
    "low_height_or_overspeed": 2
  },
  "terminal_reasons": {
    "upper_dof_overspeed": 2,
    "complete": 62
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 75.10784709841178,
    "wrist_cam_ang_speed_p95_deg_s": 202.124168396235,
    "wrist_cam_axis_sweep_p95_deg_s": 173.53941792040533,
    "base_cam_ang_speed_p95_deg_s": 76.52085374731584,
    "wrist_cam_axis_elev_p5_deg": -54.16361233888485,
    "wrist_cam_axis_elev_p50_deg": -40.803499814055044,
    "wrist_cam_axis_elev_p95_deg": -8.06781593018306,
    "arm_posture_l1_p50_rad": 0.5969907786493422,
    "post_release_return_time_p50_s": 0.7199999999999998,
    "handle_bearing_deg_p50_stage0_2": 8.672525405883789,
    "crossing_yaw_deg_p50": 165.42750549316406,
    "arm_posture_l1_p95_rad": 2.030420371515352,
    "post_release_return_time_p95_s": 1.0290000000000004,
    "handle_bearing_deg_p95_stage0_2": 31.52982759475708,
    "crossing_yaw_deg_p95": 175.9334846496582,
    "wrist_cam_share_axis_sweep_gt_60": 0.4648630693142393,
    "arm_j6_reversals_per_s": 1.0987791342956381,
    "arm_j6_abs_dev_from_1p57_p95": 0.3151966857910155,
    "wrist_tower_panel_min_clearance_m": 0.0074504039734820705,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.06258480325644505,
    "doorway_bearing_deg_p95_stage5": 172.55819702148438,
    "stage0_2_vy_cmd_at_clip_share": 0.3621099050203528,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.9141823030764835
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 135.9398702302326,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 330.5856002559129,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 150.94285343341025,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 197.9737343875603,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.012950012950012652,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.8207343412525449,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.6292906178489805,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.3750180923433548,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 2.030420371515352,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.0536563423724457,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.7199999999999998,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 1.0290000000000004,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 15562,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 58,
      "right_censored_episodes": 5,
      "observed": {
        "min": 0.5199999999999996,
        "p5": 0.5570000000000004,
        "p50": 0.7199999999999998,
        "p95": 1.0290000000000004,
        "max": 1.4799999999999995
      },
      "censor_duration": {
        "min": 0.39999999999999947,
        "p5": 1.0559999999999994,
        "p50": 3.880000000000001,
        "p95": 4.0440000000000005,
        "max": 4.080000000000001
      }
    }
  },
  "event_counts": {
    "all": 27094,
    "stage0_2": 5896,
    "stage5": 11637,
    "stage2_4": 10499,
    "stage0_5": 15562,
    "crossing_episodes": 62
  }
}
```

### A_S282 / right / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 12,
    "hinge_below_1p0472": 52,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 86.11654536462306,
    "wrist_cam_ang_speed_p95_deg_s": 271.26761255503857,
    "wrist_cam_axis_sweep_p95_deg_s": 227.76222955438,
    "base_cam_ang_speed_p95_deg_s": 112.77994956469142,
    "wrist_cam_axis_elev_p5_deg": -43.334252044918735,
    "wrist_cam_axis_elev_p50_deg": -24.91259898508898,
    "wrist_cam_axis_elev_p95_deg": 19.83398507033816,
    "arm_posture_l1_p50_rad": 1.1464586243964732,
    "post_release_return_time_p50_s": 0.7599999999999998,
    "handle_bearing_deg_p50_stage0_2": 5.384093284606934,
    "crossing_yaw_deg_p50": 174.23956298828125,
    "arm_posture_l1_p95_rad": 3.193228126317262,
    "post_release_return_time_p95_s": 0.8500000000000003,
    "handle_bearing_deg_p95_stage0_2": 26.292263412475574,
    "crossing_yaw_deg_p95": 176.26101837158203,
    "wrist_cam_share_axis_sweep_gt_60": 0.5287141322083814,
    "arm_j6_reversals_per_s": 2.326138131908364,
    "arm_j6_abs_dev_from_1p57_p95": 0.5151784706115722,
    "wrist_tower_panel_min_clearance_m": 0.01925078136010273,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.030620599312264615,
    "doorway_bearing_deg_p95_stage5": 146.76023788452147,
    "stage0_2_vy_cmd_at_clip_share": 0.27378418208613065,
    "handle_in_wrist_depth_share_stage2_4": 0.9991782459285821,
    "handle_in_wrist_rgb_share_stage2_4": 0.45465411624084867
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 247.47463634878088,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 111.67819857037695,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 166.38518946925146,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 376.82162611521613,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.07248127567045122,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 1.1512134411948487,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.204030226700287,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.5691109669042125,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.193228126317262,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.2433847592332866,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.7599999999999998,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.8500000000000003,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 10695,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 3,
      "right_censored_episodes": 61,
      "observed": {
        "min": 0.7400000000000002,
        "p5": 0.7420000000000002,
        "p50": 0.7599999999999998,
        "p95": 0.8500000000000003,
        "max": 0.8600000000000003
      },
      "censor_duration": {
        "min": 1.7599999999999998,
        "p5": 1.88,
        "p50": 2.0999999999999996,
        "p95": 2.3200000000000003,
        "max": 2.46
      }
    }
  },
  "event_counts": {
    "all": 25127,
    "stage0_2": 6107,
    "stage5": 6492,
    "stage2_4": 13386,
    "stage0_5": 10695,
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
      "through_batch": 6000,
      "updates": 383941,
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
        "update_index": 383940,
        "common_step": 384000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": null,
        "driver_right": 1.0,
        "natural_sample_left": 0,
        "natural_sample_right": 2,
        "natural_reached_left": 0,
        "natural_reached_right": 2,
        "consumed": false,
        "skipped": true
      },
      "scale_min": 0.20000000298023224,
      "scale_max": 1.0,
      "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."
    }
  }
}
```

针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s282_6000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s282_6000.json)；完整逐阶段指标见相邻 JSON。
