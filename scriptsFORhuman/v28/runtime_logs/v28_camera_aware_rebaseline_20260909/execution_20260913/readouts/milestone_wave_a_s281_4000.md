# base_v28 step4000 readout

2026-09-15 14:36 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S281 | left/nominal | 64 / 64 / 64 / 64 / 64 / 64 / 47 | 0 | 0 | 0 | 1.1176 | CAMERA_UNMET |
| A_S281 | right/nominal | 28 / 64 / 64 / 64 / 64 / 64 / 38 | 0 | 0 | 603.27 | 1.4168 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S281 / left / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 47,
    "hinge_below_1p0472": 17,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 86.63093603441192,
    "wrist_cam_ang_speed_p95_deg_s": 280.55702286416954,
    "wrist_cam_axis_sweep_p95_deg_s": 189.77621495841976,
    "base_cam_ang_speed_p95_deg_s": 60.24140592680565,
    "wrist_cam_axis_elev_p5_deg": -39.0664637542951,
    "wrist_cam_axis_elev_p50_deg": -26.699751757636783,
    "wrist_cam_axis_elev_p95_deg": -10.241411724154641,
    "arm_posture_l1_p50_rad": 1.0801782874732453,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 11.3202486038208,
    "crossing_yaw_deg_p50": 170.74451446533203,
    "arm_posture_l1_p95_rad": 3.131986737251281,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 32.988118171691895,
    "crossing_yaw_deg_p95": 174.55060806274415,
    "wrist_cam_share_axis_sweep_gt_60": 0.47513159670670807,
    "arm_j6_reversals_per_s": 2.9267550385512098,
    "arm_j6_abs_dev_from_1p57_p95": 0.5128114509582519,
    "wrist_tower_panel_min_clearance_m": 0.013804170963133074,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.07817310981867943,
    "doorway_bearing_deg_p95_stage5": 178.7582649230957,
    "stage0_2_vy_cmd_at_clip_share": 0.39822100581594255,
    "handle_in_wrist_depth_share_stage2_4": 0.9937302167031897,
    "handle_in_wrist_rgb_share_stage2_4": 0.33808132456781104
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 319.201123420418,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 164.22704451608982,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 169.7524449085292,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 377.55944340172266,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.01223990208078322,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.5212121212120957,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 5.292792792792879,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.952785012181013,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.131986737251281,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.23373184626494423,
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
    "posture_frame_denominator": 12463,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 64,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 2.24,
        "p5": 2.28,
        "p50": 2.620000000000001,
        "p95": 2.9970000000000008,
        "max": 3.500000000000001
      }
    }
  },
  "event_counts": {
    "all": 29636,
    "stage0_2": 5846,
    "stage5": 8314,
    "stage2_4": 16428,
    "stage0_5": 12463,
    "crossing_episodes": 64
  }
}
```

### A_S281 / right / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 38,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 26,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 86.4540006305477,
    "wrist_cam_ang_speed_p95_deg_s": 208.93938451919462,
    "wrist_cam_axis_sweep_p95_deg_s": 156.4405262433316,
    "base_cam_ang_speed_p95_deg_s": 69.80514568616127,
    "wrist_cam_axis_elev_p5_deg": -57.580763856654514,
    "wrist_cam_axis_elev_p50_deg": -38.086252553356324,
    "wrist_cam_axis_elev_p95_deg": -16.200817151528824,
    "arm_posture_l1_p50_rad": 0.8069137913521445,
    "post_release_return_time_p50_s": 1.8200000000000003,
    "handle_bearing_deg_p50_stage0_2": 5.806647300720215,
    "crossing_yaw_deg_p50": 161.54157257080078,
    "arm_posture_l1_p95_rad": 4.848754324763988,
    "post_release_return_time_p95_s": 2.42,
    "handle_bearing_deg_p95_stage0_2": 26.679539012908922,
    "crossing_yaw_deg_p95": 164.81196136474608,
    "wrist_cam_share_axis_sweep_gt_60": 0.543931241197501,
    "arm_j6_reversals_per_s": 0.9374886886020916,
    "arm_j6_abs_dev_from_1p57_p95": 0.6048858773708341,
    "wrist_tower_panel_min_clearance_m": 0.04060406702087427,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03303892705266601,
    "doorway_bearing_deg_p95_stage5": 176.54653778076172,
    "stage0_2_vy_cmd_at_clip_share": 0.20428524697415767,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.5467536851580961
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 256.06109207878626,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 227.52843133436656,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 138.39699765169925,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 226.05613739997887,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.03419972640218891,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.48802129547463374,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 1.3189448441247213,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.005057803468303,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 4.848754324763988,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.12462578999889123,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 1.8200000000000003,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 2.42,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 18038,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 41,
      "right_censored_episodes": 20,
      "observed": {
        "min": 1.2800000000000002,
        "p5": 1.6399999999999997,
        "p50": 1.8200000000000003,
        "p95": 2.42,
        "max": 2.5200000000000005
      },
      "censor_duration": {
        "min": 3.9399999999999995,
        "p5": 3.959,
        "p50": 4.130000000000001,
        "p95": 4.662,
        "max": 4.7
      }
    }
  },
  "event_counts": {
    "all": 27691,
    "stage0_2": 6114,
    "stage5": 13588,
    "stage2_4": 8887,
    "stage0_5": 18038,
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
    "A_S281": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s281/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 4000,
      "updates": 255919,
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
        "update_index": 255918,
        "common_step": 256000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": null,
        "natural_sample_left": 2,
        "natural_sample_right": 0,
        "natural_reached_left": 2,
        "natural_reached_right": 0,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s281_4000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s281_4000.json)；完整逐阶段指标见相邻 JSON。
