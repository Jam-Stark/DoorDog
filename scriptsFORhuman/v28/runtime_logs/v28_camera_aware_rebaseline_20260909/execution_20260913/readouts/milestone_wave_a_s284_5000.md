# base_v28 step5000 readout

2026-09-17 15:49 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S284 | left/nominal | 63 / 64 / 64 / 64 / 64 / 64 / 26 | 0 | 0 | 0 | 1.0292 | CAMERA_UNMET |
| A_S284 | right/nominal | 62 / 63 / 63 / 63 / 63 / 63 / 12 | 0 | 0 | 0 | 0.97849 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S284 / left / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 26,
    "hinge_below_1p0472": 38,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 65.3670054023273,
    "wrist_cam_ang_speed_p95_deg_s": 227.45469466799844,
    "wrist_cam_axis_sweep_p95_deg_s": 166.97100992573712,
    "base_cam_ang_speed_p95_deg_s": 79.24415351638845,
    "wrist_cam_axis_elev_p5_deg": -46.2088381655519,
    "wrist_cam_axis_elev_p50_deg": -35.34756557132752,
    "wrist_cam_axis_elev_p95_deg": -13.891696893399732,
    "arm_posture_l1_p50_rad": 1.0521387859698734,
    "post_release_return_time_p50_s": 0.5,
    "handle_bearing_deg_p50_stage0_2": 7.051361083984375,
    "crossing_yaw_deg_p50": 164.3034210205078,
    "arm_posture_l1_p95_rad": 4.318278834223747,
    "post_release_return_time_p95_s": 0.5,
    "handle_bearing_deg_p95_stage0_2": 31.582889747619618,
    "crossing_yaw_deg_p95": 168.19636764526368,
    "wrist_cam_share_axis_sweep_gt_60": 0.33402590207078053,
    "arm_j6_reversals_per_s": 2.61331297286148,
    "arm_j6_abs_dev_from_1p57_p95": 0.5153796005249023,
    "wrist_tower_panel_min_clearance_m": 0.011310052296352433,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.06462464589235127,
    "doorway_bearing_deg_p95_stage5": 178.87864151000977,
    "stage0_2_vy_cmd_at_clip_share": 0.41342067988668557,
    "handle_in_wrist_depth_share_stage2_4": 0.9930385458295733,
    "handle_in_wrist_rgb_share_stage2_4": 0.4372179966481887
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 196.06875396164168,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 235.95945649133807,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 141.86488161028407,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 316.7505983236163,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.0885403491019463,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 1.291469194312717,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 18.853591160221285,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.576370870090997,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 4.318278834223747,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.5388547240635732,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.5,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.5,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 12521,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 1,
      "right_censored_episodes": 63,
      "observed": {
        "min": 0.5,
        "p5": 0.5,
        "p50": 0.5,
        "p95": 0.5,
        "max": 0.5
      },
      "censor_duration": {
        "min": 2.4800000000000004,
        "p5": 2.5420000000000007,
        "p50": 2.6800000000000006,
        "p95": 3.072000000000001,
        "max": 3.58
      }
    }
  },
  "event_counts": {
    "all": 28878,
    "stage0_2": 5648,
    "stage5": 8504,
    "stage2_4": 15514,
    "stage0_5": 12521,
    "crossing_episodes": 64
  }
}
```

### A_S284 / right / nominal

```json
{
  "quality_components": {
    "complete": 63,
    "clean_complete": 12,
    "hinge_below_1p0472": 51,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 1
  },
  "terminal_reasons": {
    "upper_dof_overspeed": 1,
    "complete": 63
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 90.27927242436243,
    "wrist_cam_ang_speed_p95_deg_s": 234.08578699586639,
    "wrist_cam_axis_sweep_p95_deg_s": 179.935030985604,
    "base_cam_ang_speed_p95_deg_s": 90.45589294912438,
    "wrist_cam_axis_elev_p5_deg": -54.64699229439803,
    "wrist_cam_axis_elev_p50_deg": -30.71148347336732,
    "wrist_cam_axis_elev_p95_deg": -13.913659690199601,
    "arm_posture_l1_p50_rad": 0.8818386553321034,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 6.37393045425415,
    "crossing_yaw_deg_p50": 178.85540771484375,
    "arm_posture_l1_p95_rad": 2.544910225924104,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 27.19103717803955,
    "crossing_yaw_deg_p95": 179.91424865722655,
    "wrist_cam_share_axis_sweep_gt_60": 0.5892160486222332,
    "arm_j6_reversals_per_s": 3.489521142999404,
    "arm_j6_abs_dev_from_1p57_p95": 0.23324368476867668,
    "wrist_tower_panel_min_clearance_m": 0.005512651470478112,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.034088912317694606,
    "doorway_bearing_deg_p95_stage5": 89.80502395629883,
    "stage0_2_vy_cmd_at_clip_share": 0.16078017923036372,
    "handle_in_wrist_depth_share_stage2_4": 0.9989008724325067,
    "handle_in_wrist_rgb_share_stage2_4": 0.5685924297588789
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 246.0055285314592,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 258.0597914960766,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 170.72293725956234,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 344.6908644085872,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.0771406531241948,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.6985822888843422,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 22.739187418086857,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 5.088099500611632,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 2.544910225924104,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.02217719238995835,
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
    "posture_frame_denominator": 8883,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 63,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 1.3199999999999994,
        "p5": 1.38,
        "p50": 1.54,
        "p95": 1.7599999999999998,
        "max": 4.5
      }
    }
  },
  "event_counts": {
    "all": 24351,
    "stage0_2": 5691,
    "stage5": 4930,
    "stage2_4": 14557,
    "stage0_5": 8883,
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
    "A_S284": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s284/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 5000,
      "updates": 319941,
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
        "update_index": 319940,
        "common_step": 320000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 4,
        "natural_sample_right": 6,
        "natural_reached_left": 4,
        "natural_reached_right": 6,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s284_5000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s284_5000.json)；完整逐阶段指标见相邻 JSON。
