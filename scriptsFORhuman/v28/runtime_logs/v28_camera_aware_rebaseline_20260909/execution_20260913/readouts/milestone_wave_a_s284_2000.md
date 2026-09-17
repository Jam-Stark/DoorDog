# base_v28 step2000 readout

2026-09-16 18:21 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S284 | left/nominal | 64 / 64 / 64 / 64 / 9 / 0 / 0 | 0 | 0 | 220.33 | 1.0676 | CAMERA_UNMET |
| A_S284 | right/nominal | 64 / 64 / 64 / 64 / 1 / 0 / 0 | 1 | 2.0637e-05 | 0 | 0.8199 | CAMERA_UNMET |

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
    "wrist_cam_ang_speed_p50_deg_s": 44.35565233760539,
    "wrist_cam_ang_speed_p95_deg_s": 114.56904190317852,
    "wrist_cam_axis_sweep_p95_deg_s": 86.27862458910671,
    "base_cam_ang_speed_p95_deg_s": 43.28832471687304,
    "wrist_cam_axis_elev_p5_deg": -42.121701813127096,
    "wrist_cam_axis_elev_p50_deg": -32.513092837209626,
    "wrist_cam_axis_elev_p95_deg": -19.906250559067946,
    "arm_posture_l1_p50_rad": 0.14603606518357992,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 8.833682537078857,
    "crossing_yaw_deg_p50": 157.9149398803711,
    "arm_posture_l1_p95_rad": 2.999755752179771,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 29.89925479888916,
    "crossing_yaw_deg_p95": 159.10788650512694,
    "wrist_cam_share_axis_sweep_gt_60": 0.14463197842804354,
    "arm_j6_reversals_per_s": 2.8109437811261273,
    "arm_j6_abs_dev_from_1p57_p95": 0.5133477854728696,
    "wrist_tower_panel_min_clearance_m": 0.019838625967298382,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.049209662988368624,
    "doorway_bearing_deg_p95_stage5": 150.91102905273436,
    "stage0_2_vy_cmd_at_clip_share": 0.27110050700864896,
    "handle_in_wrist_depth_share_stage2_4": 0.9996974703870052,
    "handle_in_wrist_rgb_share_stage2_4": 0.3089525493937772
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 99.09753989813757,
        "limit": 105,
        "pass": true
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 216.4476279647476,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 99.98097192398716,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 210.88132783101224,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.07223693715386414,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.352443609022565,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.314540059347204,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.515002174229885,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 2.999755752179771,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.15864022662889518,
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
    "posture_frame_denominator": 6354,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 37,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 0.040000000000000924,
        "p5": 0.1080000000000009,
        "p50": 1.4600000000000009,
        "p95": 6.312,
        "max": 7.160000000000002
      }
    }
  },
  "event_counts": {
    "all": 50065,
    "stage0_2": 6706,
    "stage5": 2137,
    "stage2_4": 42971,
    "stage0_5": 6354,
    "crossing_episodes": 64
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
    "wrist_cam_ang_speed_p50_deg_s": 56.74054102627875,
    "wrist_cam_ang_speed_p95_deg_s": 117.32759052550263,
    "wrist_cam_axis_sweep_p95_deg_s": 90.93453384765172,
    "base_cam_ang_speed_p95_deg_s": 46.237648307225264,
    "wrist_cam_axis_elev_p5_deg": -33.033134648797216,
    "wrist_cam_axis_elev_p50_deg": -24.247748119548955,
    "wrist_cam_axis_elev_p95_deg": -13.709172221467947,
    "arm_posture_l1_p50_rad": 0.13276199530810118,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 5.507453203201294,
    "crossing_yaw_deg_p50": 158.48455047607422,
    "arm_posture_l1_p95_rad": 0.19231596468016487,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 26.927426719665522,
    "crossing_yaw_deg_p95": 160.42190551757812,
    "wrist_cam_share_axis_sweep_gt_60": 0.20347937346513403,
    "arm_j6_reversals_per_s": 2.331948835576821,
    "arm_j6_abs_dev_from_1p57_p95": 0.007518939971923761,
    "wrist_tower_panel_min_clearance_m": -0.000553391548147205,
    "wrist_tower_contact_step_share": 2.0636853292609944e-05,
    "wrist_tower_contact_episodes_gt_5N": 1,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03231748158070998,
    "doorway_bearing_deg_p95_stage5": 160.78805084228514,
    "stage0_2_vy_cmd_at_clip_share": 0.144675150703282,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.33808059556562553
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 105.1777092544884,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 207.3486631239539,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 110.84421941196898,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 203.83941590829093,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.024319066147859694,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.49504950495049493,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.33076074972437153,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.5663446591174575,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.19231596468016487,
        "limit": 0.5,
        "pass": true
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.0011418131993605847,
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
    "posture_frame_denominator": 4379,
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
        "min": 4.080000000000002,
        "p5": 4.080000000000002,
        "p50": 4.080000000000002,
        "p95": 4.080000000000002,
        "max": 4.080000000000002
      }
    }
  },
  "event_counts": {
    "all": 48457,
    "stage0_2": 5972,
    "stage5": 203,
    "stage2_4": 43253,
    "stage0_5": 4379,
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
    "A_S284": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s284/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 2000,
      "updates": 127972,
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
        "update_index": 127971,
        "common_step": 128000,
        "scale_before": 1.0,
        "scale_after": 1.0,
        "driver_left": 0.0,
        "driver_right": 0.0,
        "natural_sample_left": 2,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s284_2000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s284_2000.json)；完整逐阶段指标见相邻 JSON。
