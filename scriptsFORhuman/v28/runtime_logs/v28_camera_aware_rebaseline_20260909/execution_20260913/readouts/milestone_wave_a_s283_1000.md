# base_v28 step1000 readout

2026-09-14 17:52 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S283 | left/nominal | 0 / 0 / 0 / 0 / 0 / 0 / 0 | 0 | 0 | null | null | CAMERA_PARTIAL |
| A_S283 | right/nominal | 0 / 4 / 0 / 0 / 0 / 0 / 0 | 0 | 0 | null | null | CAMERA_PARTIAL |

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
    "wrist_cam_ang_speed_p50_deg_s": 34.02392782504354,
    "wrist_cam_ang_speed_p95_deg_s": 83.50334224163569,
    "wrist_cam_axis_sweep_p95_deg_s": 74.87224139933433,
    "base_cam_ang_speed_p95_deg_s": 39.836322215912254,
    "wrist_cam_axis_elev_p5_deg": -31.99993394908543,
    "wrist_cam_axis_elev_p50_deg": -27.11455543130667,
    "wrist_cam_axis_elev_p95_deg": -10.761884776650433,
    "arm_posture_l1_p50_rad": 0.12572397652547807,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 2.5660241842269897,
    "crossing_yaw_deg_p50": null,
    "arm_posture_l1_p95_rad": 0.16815518722869455,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 16.369133758544926,
    "crossing_yaw_deg_p95": null,
    "wrist_cam_share_axis_sweep_gt_60": 0.0851166213768116,
    "arm_j6_reversals_per_s": 0.5643148820329502,
    "arm_j6_abs_dev_from_1p57_p95": 0.004975520372390684,
    "wrist_tower_panel_min_clearance_m": 0.13113367683645888,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.012539628623188406,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.039487092391304345,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.9555259209868311
  },
  "camera_targets": {
    "outcome": "CAMERA_PARTIAL",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 67.5612307782397,
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
        "value": 0.03573130061934236,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.6598509906120228,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": null,
        "limit": 2.5,
        "pass": null
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.16815518722869455,
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
    "posture_frame_denominator": 4262,
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
    "stage2_4": 29995,
    "stage0_5": 4262,
    "crossing_episodes": 0
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
    "wrist_cam_ang_speed_p50_deg_s": 41.29044605634514,
    "wrist_cam_ang_speed_p95_deg_s": 84.2057194673871,
    "wrist_cam_axis_sweep_p95_deg_s": 73.71772755414565,
    "base_cam_ang_speed_p95_deg_s": 46.75573025653863,
    "wrist_cam_axis_elev_p5_deg": -33.879043613373646,
    "wrist_cam_axis_elev_p50_deg": -27.59487525713643,
    "wrist_cam_axis_elev_p95_deg": -11.226733573734572,
    "arm_posture_l1_p50_rad": 0.12759367655962706,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 5.12355899810791,
    "crossing_yaw_deg_p50": null,
    "arm_posture_l1_p95_rad": 0.1722245942801237,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 13.965983390808105,
    "crossing_yaw_deg_p95": null,
    "wrist_cam_share_axis_sweep_gt_60": 0.09003134445315124,
    "arm_j6_reversals_per_s": 0.5130649321523282,
    "arm_j6_abs_dev_from_1p57_p95": 0.005156450271606383,
    "wrist_tower_panel_min_clearance_m": 0.12726618489179203,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.005323843416370107,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.019786476868327404,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.9179473649495415
  },
  "camera_targets": {
    "outcome": "CAMERA_PARTIAL",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 71.65252718855773,
        "limit": 105,
        "pass": true
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 34.381597472850636,
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
        "value": 0.05900401227283436,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.5918856025094406,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": null,
        "limit": 2.5,
        "pass": null
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.1722245942801237,
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
    "posture_frame_denominator": 4301,
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
    "all": 35732,
    "stage0_2": 35125,
    "stage5": 0,
    "stage2_4": 30322,
    "stage0_5": 4301,
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
      "through_batch": 1000,
      "updates": 63998,
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
        "update_index": 63997,
        "common_step": 64000,
        "scale_before": 1.0,
        "scale_after": 1.0,
        "driver_left": null,
        "driver_right": 0.0,
        "natural_sample_left": 0,
        "natural_sample_right": 1,
        "natural_reached_left": 0,
        "natural_reached_right": 0,
        "consumed": false,
        "skipped": true
      },
      "scale_min": 1.0,
      "scale_max": 1.0,
      "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."
    }
  }
}
```

针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s283_1000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s283_1000.json)；完整逐阶段指标见相邻 JSON。
