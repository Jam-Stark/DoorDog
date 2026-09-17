# base_v28 step3000 readout

2026-09-17 01:38 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S284 | left/nominal | 64 / 64 / 64 / 64 / 0 / 0 / 0 | 0 | 0 | 228.26 | 1 | CAMERA_UNMET |
| A_S284 | right/nominal | 64 / 64 / 64 / 64 / 64 / 64 / 32 | 0 | 0 | 0 | 1.0471 | CAMERA_UNMET |

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
    "wrist_cam_ang_speed_p50_deg_s": 39.42505143556076,
    "wrist_cam_ang_speed_p95_deg_s": 104.41845285245645,
    "wrist_cam_axis_sweep_p95_deg_s": 71.61701704635615,
    "base_cam_ang_speed_p95_deg_s": 46.142009429657065,
    "wrist_cam_axis_elev_p5_deg": -44.05706927400619,
    "wrist_cam_axis_elev_p50_deg": -33.70323468372357,
    "wrist_cam_axis_elev_p95_deg": -17.238995333364656,
    "arm_posture_l1_p50_rad": 0.12843681685626507,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 7.8303351402282715,
    "crossing_yaw_deg_p50": 158.28112030029297,
    "arm_posture_l1_p95_rad": 0.17531912441627356,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 31.260129451751713,
    "crossing_yaw_deg_p95": 159.20587158203125,
    "wrist_cam_share_axis_sweep_gt_60": 0.08738809681697612,
    "arm_j6_reversals_per_s": 1.3591467463487723,
    "arm_j6_abs_dev_from_1p57_p95": 0.0062628674507140495,
    "wrist_tower_panel_min_clearance_m": 0.03319199402780991,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.06144578313253012,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.363855421686747,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.5832485666728315
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 106.54543634227552,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 314.098443103303,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 93.58625977594937,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.09682885499878882,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.6139410187667966,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.4612634710234063,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.17531912441627356,
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
    "posture_frame_denominator": 4195,
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
    "stage0_2": 5810,
    "stage5": 0,
    "stage2_4": 43256,
    "stage0_5": 4195,
    "crossing_episodes": 64
  }
}
```

### A_S284 / right / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 32,
    "hinge_below_1p0472": 32,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 50.64239133354586,
    "wrist_cam_ang_speed_p95_deg_s": 126.255832283282,
    "wrist_cam_axis_sweep_p95_deg_s": 104.3354638699094,
    "base_cam_ang_speed_p95_deg_s": 55.05403022763802,
    "wrist_cam_axis_elev_p5_deg": -48.162806937673245,
    "wrist_cam_axis_elev_p50_deg": -32.38895166013955,
    "wrist_cam_axis_elev_p95_deg": -13.028291005874939,
    "arm_posture_l1_p50_rad": 0.8491001133588725,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 6.443987846374512,
    "crossing_yaw_deg_p50": 168.7838134765625,
    "arm_posture_l1_p95_rad": 2.120211210846903,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 26.523842811584473,
    "crossing_yaw_deg_p95": 171.3393913269043,
    "wrist_cam_share_axis_sweep_gt_60": 0.20139318530739442,
    "arm_j6_reversals_per_s": 1.014296532575111,
    "arm_j6_abs_dev_from_1p57_p95": 0.3511827301979066,
    "wrist_tower_panel_min_clearance_m": 0.036394169701580714,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03180510911859245,
    "doorway_bearing_deg_p95_stage5": 90.44386444091796,
    "stage0_2_vy_cmd_at_clip_share": 0.20537980037218745,
    "handle_in_wrist_depth_share_stage2_4": 0.9950508917732748,
    "handle_in_wrist_rgb_share_stage2_4": 0.25589068384847635
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 123.46616107236018,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 230.31730933562852,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 93.98099491134226,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 191.10957662187872,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.07107320540156334,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.03152088258471576,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 3.4366576819407544,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.1987020423749306,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 2.120211210846903,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.12979240695717226,
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
    "posture_frame_denominator": 10694,
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
        "min": 1.5,
        "p5": 1.675,
        "p50": 2.0300000000000002,
        "p95": 2.677999999999999,
        "max": 5.239999999999998
      }
    }
  },
  "event_counts": {
    "all": 43641,
    "stage0_2": 5911,
    "stage5": 6409,
    "stage2_4": 32127,
    "stage0_5": 10694,
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
      "through_batch": 3000,
      "updates": 191952,
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
        "update_index": 191951,
        "common_step": 192000,
        "scale_before": 1.0,
        "scale_after": 1.0,
        "driver_left": 0.0,
        "driver_right": 0.6,
        "natural_sample_left": 2,
        "natural_sample_right": 5,
        "natural_reached_left": 0,
        "natural_reached_right": 3,
        "consumed": true,
        "skipped": false
      },
      "scale_min": 0.9998999834060669,
      "scale_max": 1.0,
      "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."
    }
  }
}
```

针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s284_3000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s284_3000.json)；完整逐阶段指标见相邻 JSON。
