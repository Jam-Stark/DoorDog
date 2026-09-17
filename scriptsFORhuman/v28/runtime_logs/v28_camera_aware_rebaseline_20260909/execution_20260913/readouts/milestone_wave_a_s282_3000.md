# base_v28 step3000 readout

2026-09-15 06:50 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S282 | left/nominal | 64 / 64 / 64 / 64 / 20 / 0 / 0 | 0 | 0 | 0 | 0.78576 | CAMERA_UNMET |
| A_S282 | right/nominal | 64 / 64 / 64 / 64 / 0 / 0 / 0 | 10 | 0.0010983 | 0 | 0.79612 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S282 / left / nominal

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
    "wrist_cam_ang_speed_p50_deg_s": 37.496784461806115,
    "wrist_cam_ang_speed_p95_deg_s": 180.0460635470721,
    "wrist_cam_axis_sweep_p95_deg_s": 150.54642607204318,
    "base_cam_ang_speed_p95_deg_s": 58.13837184932915,
    "wrist_cam_axis_elev_p5_deg": -63.04689646934302,
    "wrist_cam_axis_elev_p50_deg": -44.686840957585595,
    "wrist_cam_axis_elev_p95_deg": -7.713444076494994,
    "arm_posture_l1_p50_rad": 1.0820951184505248,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 6.94678258895874,
    "crossing_yaw_deg_p50": 156.85086822509766,
    "arm_posture_l1_p95_rad": 4.353728208132086,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 31.497522354125977,
    "crossing_yaw_deg_p95": 159.08298950195314,
    "wrist_cam_share_axis_sweep_gt_60": 0.17114928456653147,
    "arm_j6_reversals_per_s": 2.338542863710977,
    "arm_j6_abs_dev_from_1p57_p95": 0.4014281558990476,
    "wrist_tower_panel_min_clearance_m": 0.05508813938289957,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.061861029284352796,
    "doorway_bearing_deg_p95_stage5": 95.8793960571289,
    "stage0_2_vy_cmd_at_clip_share": 0.3165829145728643,
    "handle_in_wrist_depth_share_stage2_4": 0.9966978403393753,
    "handle_in_wrist_rgb_share_stage2_4": 0.7090483995372155
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 122.46245056447945,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 264.3729528183312,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 79.03956149739042,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 312.8218804059776,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.0126135216952571,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.7853850093905534,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 1.0050251256281568,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.1296177544834305,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 4.353728208132086,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.13568904593639575,
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
    "posture_frame_denominator": 9905,
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
    "all": 52276,
    "stage0_2": 5771,
    "stage5": 5877,
    "stage2_4": 41488,
    "stage0_5": 9905,
    "crossing_episodes": 58
  }
}
```

### A_S282 / right / nominal

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
    "wrist_cam_ang_speed_p50_deg_s": 69.12657772155441,
    "wrist_cam_ang_speed_p95_deg_s": 138.50315262521838,
    "wrist_cam_axis_sweep_p95_deg_s": 112.9444594857911,
    "base_cam_ang_speed_p95_deg_s": 52.45332640089356,
    "wrist_cam_axis_elev_p5_deg": -41.65740074803909,
    "wrist_cam_axis_elev_p50_deg": -31.12936740247165,
    "wrist_cam_axis_elev_p95_deg": -13.309374307103212,
    "arm_posture_l1_p50_rad": 0.1271379254758358,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 4.855095386505127,
    "crossing_yaw_deg_p50": 158.06160736083984,
    "arm_posture_l1_p95_rad": 0.17127785601187498,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 26.202727127075196,
    "crossing_yaw_deg_p95": 159.9111587524414,
    "wrist_cam_share_axis_sweep_gt_60": 0.2999005305039788,
    "arm_j6_reversals_per_s": 2.5533283532552127,
    "arm_j6_abs_dev_from_1p57_p95": 0.005620168447494444,
    "wrist_tower_panel_min_clearance_m": -0.00018018571893172602,
    "wrist_tower_contact_step_share": 0.0010983090185676392,
    "wrist_tower_contact_episodes_gt_5N": 10,
    "handle_bearing_gt_30deg_share_stage0_2": 0.0300844475721323,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.12297677691766362,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.7650949483775811
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 143.2062514435471,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 211.37871033806928,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 132.79004310789807,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.051493305870235755,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 3.835978835978896,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.769470810039194,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.17127785601187498,
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
    "posture_frame_denominator": 3948,
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
    "stage0_2": 5684,
    "stage5": 0,
    "stage2_4": 43392,
    "stage0_5": 3948,
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
      "through_batch": 3000,
      "updates": 191977,
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
        "update_index": 191976,
        "common_step": 192000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 1,
        "natural_sample_right": 2,
        "natural_reached_left": 1,
        "natural_reached_right": 2,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s282_3000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s282_3000.json)；完整逐阶段指标见相邻 JSON。
