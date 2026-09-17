# base_v28 step6000 readout

2026-09-17 17:07 HKT

状态：`V28_COMPLETE`；每侧 exact 128。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S282 | left/nominal | 103 / 128 / 126 / 126 / 126 / 126 / 123 | 0 | 0 | 0 | 1.6941 | CAMERA_UNMET |
| A_S282 | right/nominal | 128 / 128 / 128 / 128 / 128 / 128 / 47 | 0 | 0 | 0 | 0.99452 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S282 / left / nominal

```json
{
  "quality_components": {
    "complete": 126,
    "clean_complete": 123,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 3,
    "low_height_or_overspeed": 1
  },
  "terminal_reasons": {
    "upper_dof_overspeed": 1,
    "complete": 126,
    "stage_overtime": 1
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 75.43861074407859,
    "wrist_cam_ang_speed_p95_deg_s": 200.6738263645562,
    "wrist_cam_axis_sweep_p95_deg_s": 173.24433236936443,
    "base_cam_ang_speed_p95_deg_s": 76.37312202117528,
    "wrist_cam_axis_elev_p5_deg": -54.19792789684378,
    "wrist_cam_axis_elev_p50_deg": -40.952404765865865,
    "wrist_cam_axis_elev_p95_deg": -8.39836287611892,
    "arm_posture_l1_p50_rad": 0.573960929254099,
    "post_release_return_time_p50_s": 0.71,
    "handle_bearing_deg_p50_stage0_2": 7.967525482177734,
    "crossing_yaw_deg_p50": 167.31996154785156,
    "arm_posture_l1_p95_rad": 1.903220595709353,
    "post_release_return_time_p95_s": 0.9410000000000003,
    "handle_bearing_deg_p95_stage0_2": 28.782795143127448,
    "crossing_yaw_deg_p95": 175.42833251953124,
    "wrist_cam_share_axis_sweep_gt_60": 0.4609604171947996,
    "arm_j6_reversals_per_s": 1.2459617408988422,
    "arm_j6_abs_dev_from_1p57_p95": 0.29233518338203424,
    "wrist_tower_panel_min_clearance_m": 0.0070670994506127904,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.041127384196185286,
    "doorway_bearing_deg_p95_stage5": 173.5113182067871,
    "stage0_2_vy_cmd_at_clip_share": 0.31982288828337874,
    "handle_in_wrist_depth_share_stage2_4": 0.9831146187023951,
    "handle_in_wrist_rgb_share_stage2_4": 0.8935945673121043
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 137.63693230441228,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 313.736984750947,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 151.43051856498278,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 193.4531770074903,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.045847524233690096,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.8341867212837394,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.9163802978236005,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.7203617351983351,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 1.903220595709353,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.04756736049035883,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": 0.71,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.9410000000000003,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 31324,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 120,
      "right_censored_episodes": 6,
      "observed": {
        "min": 0.5,
        "p5": 0.539,
        "p50": 0.71,
        "p95": 0.9410000000000003,
        "max": 1.5599999999999996
      },
      "censor_duration": {
        "min": 3.7800000000000002,
        "p5": 3.785,
        "p50": 3.88,
        "p95": 4.119999999999999,
        "max": 4.159999999999999
      }
    }
  },
  "event_counts": {
    "all": 55226,
    "stage0_2": 11744,
    "stage5": 23562,
    "stage2_4": 21794,
    "stage0_5": 31324,
    "crossing_episodes": 127
  }
}
```

### A_S282 / right / nominal

```json
{
  "quality_components": {
    "complete": 128,
    "clean_complete": 47,
    "hinge_below_1p0472": 81,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 128
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 87.2591274602334,
    "wrist_cam_ang_speed_p95_deg_s": 271.64912343952864,
    "wrist_cam_axis_sweep_p95_deg_s": 225.39582842746654,
    "base_cam_ang_speed_p95_deg_s": 113.08012667991945,
    "wrist_cam_axis_elev_p5_deg": -43.39077377724754,
    "wrist_cam_axis_elev_p50_deg": -25.16910181045538,
    "wrist_cam_axis_elev_p95_deg": 18.65378879474846,
    "arm_posture_l1_p50_rad": 1.129850335419178,
    "post_release_return_time_p50_s": 0.7600000000000007,
    "handle_bearing_deg_p50_stage0_2": 5.829998016357422,
    "crossing_yaw_deg_p50": 174.08070373535156,
    "arm_posture_l1_p95_rad": 3.263510761782527,
    "post_release_return_time_p95_s": 0.7999999999999998,
    "handle_bearing_deg_p95_stage0_2": 28.865312767028808,
    "crossing_yaw_deg_p95": 176.44678649902343,
    "wrist_cam_share_axis_sweep_gt_60": 0.5294058991284926,
    "arm_j6_reversals_per_s": 2.2783165050498977,
    "arm_j6_abs_dev_from_1p57_p95": 0.5153023529052734,
    "wrist_tower_panel_min_clearance_m": 0.019704667290024572,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.04054840049854591,
    "doorway_bearing_deg_p95_stage5": 147.4750244140625,
    "stage0_2_vy_cmd_at_clip_share": 0.28832571665974244,
    "handle_in_wrist_depth_share_stage2_4": 0.9990218209179834,
    "handle_in_wrist_rgb_share_stage2_4": 0.42641083521444695
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 249.98689166035211,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 113.75332919020062,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 165.73257390743657,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 375.7420641452157,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.03701875616979061,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 1.3184970657721702,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.3540489642184994,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.301886792453226,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.263510761782527,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.2395139891066524,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.7600000000000007,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.7999999999999998,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 21481,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 9,
      "right_censored_episodes": 119,
      "observed": {
        "min": 0.7399999999999993,
        "p5": 0.7399999999999997,
        "p50": 0.7600000000000007,
        "p95": 0.7999999999999998,
        "max": 0.7999999999999998
      },
      "censor_duration": {
        "min": 1.8399999999999999,
        "p5": 1.9379999999999997,
        "p50": 2.12,
        "p95": 2.34,
        "max": 2.5
      }
    }
  },
  "event_counts": {
    "all": 50143,
    "stage0_2": 12035,
    "stage5": 13249,
    "stage2_4": 26580,
    "stage0_5": 21481,
    "crossing_episodes": 128
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/qualification_0_dev.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/qualification_0_dev.json)；完整逐阶段指标见相邻 JSON。
