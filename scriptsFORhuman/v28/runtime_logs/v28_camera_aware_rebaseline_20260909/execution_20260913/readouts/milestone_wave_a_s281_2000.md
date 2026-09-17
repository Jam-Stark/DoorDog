# base_v28 step2000 readout

2026-09-15 00:41 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S281 | left/nominal | 64 / 64 / 64 / 64 / 8 / 0 / 0 | 0 | 0 | 340.39 | 1.0325 | CAMERA_UNMET |
| A_S281 | right/nominal | 59 / 64 / 64 / 64 / 9 / 0 / 0 | 1 | 0.00041945 | 173.84 | 1.3976 | CAMERA_UNMET |

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
    "wrist_cam_ang_speed_p50_deg_s": 54.4725048939912,
    "wrist_cam_ang_speed_p95_deg_s": 129.6000790776031,
    "wrist_cam_axis_sweep_p95_deg_s": 95.93622546923952,
    "base_cam_ang_speed_p95_deg_s": 47.5948520057295,
    "wrist_cam_axis_elev_p5_deg": -42.67375688808646,
    "wrist_cam_axis_elev_p50_deg": -33.41491616702747,
    "wrist_cam_axis_elev_p95_deg": -14.933980544901026,
    "arm_posture_l1_p50_rad": 0.1430835323408246,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 6.523116111755371,
    "crossing_yaw_deg_p50": 178.01760864257812,
    "arm_posture_l1_p95_rad": 3.7100512364787392,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 30.577830982208244,
    "crossing_yaw_deg_p95": 179.90802001953125,
    "wrist_cam_share_axis_sweep_gt_60": 0.1863468634686347,
    "arm_j6_reversals_per_s": 4.446787148597138,
    "arm_j6_abs_dev_from_1p57_p95": 0.9435787183046341,
    "wrist_tower_panel_min_clearance_m": 0.03812336132488853,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.05442583732057416,
    "doorway_bearing_deg_p95_stage5": 118.99896049499512,
    "stage0_2_vy_cmd_at_clip_share": 0.31713516746411485,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.3119349639077721
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 123.59180616851431,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 231.28355613782097,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 103.8773841379178,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 296.5472833524874,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.02318034306907743,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 2.2978959025470918,
        "limit": 1.5,
        "pass": false
      },
      "stage2_j6_reversals_per_s": {
        "value": 1.6654598117306603,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 5.260182635167115,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.7100512364787392,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.27164082687338503,
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
    "posture_frame_denominator": 6192,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 8,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 3.5000000000000018,
        "p5": 3.5350000000000015,
        "p50": 3.870000000000001,
        "p95": 5.373000000000001,
        "max": 5.940000000000001
      }
    }
  },
  "event_counts": {
    "all": 49864,
    "stage0_2": 6688,
    "stage5": 1814,
    "stage2_4": 42807,
    "stage0_5": 6192,
    "crossing_episodes": 64
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
    "wrist_cam_ang_speed_p50_deg_s": 49.38853668640583,
    "wrist_cam_ang_speed_p95_deg_s": 198.44199549307945,
    "wrist_cam_axis_sweep_p95_deg_s": 138.75598775586099,
    "base_cam_ang_speed_p95_deg_s": 59.64209288979581,
    "wrist_cam_axis_elev_p5_deg": -49.01547654921678,
    "wrist_cam_axis_elev_p50_deg": -34.03306706554143,
    "wrist_cam_axis_elev_p95_deg": -10.64946047120905,
    "arm_posture_l1_p50_rad": 0.162114952752745,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 4.292765378952026,
    "crossing_yaw_deg_p50": 159.73440551757812,
    "arm_posture_l1_p95_rad": 5.735199607163663,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 25.468578338623047,
    "crossing_yaw_deg_p95": 163.92189025878906,
    "wrist_cam_share_axis_sweep_gt_60": 0.2120643163886947,
    "arm_j6_reversals_per_s": 1.1089778204442808,
    "arm_j6_abs_dev_from_1p57_p95": 1.0185867887735354,
    "wrist_tower_panel_min_clearance_m": 0.028755455237057453,
    "wrist_tower_contact_step_share": 0.000419454708878458,
    "wrist_tower_contact_episodes_gt_5N": 1,
    "handle_bearing_gt_30deg_share_stage0_2": 0.02854483400558486,
    "doorway_bearing_deg_p95_stage5": 166.474112701416,
    "stage0_2_vy_cmd_at_clip_share": 0.1825938566552901,
    "handle_in_wrist_depth_share_stage2_4": 0.9882994948050711,
    "handle_in_wrist_rgb_share_stage2_4": 0.576970736822038
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 90.05751525363956,
        "limit": 105,
        "pass": true
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 223.0833713765071,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 99.7834030173245,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 428.0809923868213,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.022883295194508074,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.4099821746880724,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.18264840182648717,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 0.9543742151532699,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 5.735199607163663,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.25206953642384106,
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
    "posture_frame_denominator": 7248,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 26,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 0.8599999999999994,
        "p5": 1.5100000000000002,
        "p50": 3.820000000000001,
        "p95": 8.445000000000002,
        "max": 8.560000000000002
      }
    }
  },
  "event_counts": {
    "all": 50065,
    "stage0_2": 6446,
    "stage5": 2814,
    "stage2_4": 41964,
    "stage0_5": 7248,
    "crossing_episodes": 23
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
      "through_batch": 2000,
      "updates": 127975,
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
        "update_index": 127974,
        "common_step": 128000,
        "scale_before": 0.3010256290435791,
        "scale_after": 0.30099552869796753,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 2,
        "natural_sample_right": 2,
        "natural_reached_left": 2,
        "natural_reached_right": 2,
        "consumed": true,
        "skipped": false
      },
      "scale_min": 0.30099552869796753,
      "scale_max": 1.0,
      "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."
    }
  }
}
```

针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s281_2000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s281_2000.json)；完整逐阶段指标见相邻 JSON。
