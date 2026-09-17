# base_v28 step5000 readout

2026-09-15 21:52 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S281 | left/nominal | 54 / 55 / 55 / 55 / 54 / 52 / 51 | 0 | 0 | 0 | 1.3327 | CAMERA_UNMET |
| A_S281 | right/nominal | 14 / 44 / 44 / 44 / 42 / 0 / 0 | 0 | 0 | 155.07 | 1.4202 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S281 / left / nominal

```json
{
  "quality_components": {
    "complete": 52,
    "clean_complete": 51,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 1,
    "low_height_or_overspeed": 12
  },
  "terminal_reasons": {
    "upper_dof_overspeed": 12,
    "complete": 52
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 92.71230287661743,
    "wrist_cam_ang_speed_p95_deg_s": 228.33380698241007,
    "wrist_cam_axis_sweep_p95_deg_s": 186.93749420578814,
    "base_cam_ang_speed_p95_deg_s": 95.89205443472288,
    "wrist_cam_axis_elev_p5_deg": -41.445426482924475,
    "wrist_cam_axis_elev_p50_deg": -19.6327889494273,
    "wrist_cam_axis_elev_p95_deg": 0.49867450116902784,
    "arm_posture_l1_p50_rad": 1.114846074327943,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 7.753454208374023,
    "crossing_yaw_deg_p50": 174.58535766601562,
    "arm_posture_l1_p95_rad": 3.4173303894698615,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 31.245541095733643,
    "crossing_yaw_deg_p95": 179.034814453125,
    "wrist_cam_share_axis_sweep_gt_60": 0.5643959319656321,
    "arm_j6_reversals_per_s": 1.9100580270798253,
    "arm_j6_abs_dev_from_1p57_p95": 0.5228454875946045,
    "wrist_tower_panel_min_clearance_m": 0.009682938876077827,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.06043593130779392,
    "doorway_bearing_deg_p95_stage5": 179.6035369873047,
    "stage0_2_vy_cmd_at_clip_share": 0.35535006605019814,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.5034390523500191
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 262.12905801049146,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 167.39738114219736,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 192.4463790198374,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 255.1243845806806,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.1221896383186693,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.21648044692737642,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 4.247990815155064,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.486251402918101,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.4173303894698615,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.36534740545294636,
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
    "posture_frame_denominator": 11370,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 55,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 0.0,
        "p5": 1.8520000000000003,
        "p50": 2.839999999999999,
        "p95": 2.9600000000000004,
        "max": 3.0200000000000005
      }
    }
  },
  "event_counts": {
    "all": 22812,
    "stage0_2": 6056,
    "stage5": 7214,
    "stage2_4": 10468,
    "stage0_5": 11370,
    "crossing_episodes": 55
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
    "low_height_or_overspeed": 64
  },
  "terminal_reasons": {
    "upper_dof_overspeed": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 72.94095295059041,
    "wrist_cam_ang_speed_p95_deg_s": 186.72750059286744,
    "wrist_cam_axis_sweep_p95_deg_s": 143.71225442223977,
    "base_cam_ang_speed_p95_deg_s": 73.8986084954129,
    "wrist_cam_axis_elev_p5_deg": -45.58113648332759,
    "wrist_cam_axis_elev_p50_deg": -33.90321698401713,
    "wrist_cam_axis_elev_p95_deg": -14.993965916653504,
    "arm_posture_l1_p50_rad": 0.13329790718853474,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 5.914028167724609,
    "crossing_yaw_deg_p50": 165.8849334716797,
    "arm_posture_l1_p95_rad": 7.491819269000552,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 27.496666812896727,
    "crossing_yaw_deg_p95": 172.45025024414062,
    "wrist_cam_share_axis_sweep_gt_60": 0.45376955903271693,
    "arm_j6_reversals_per_s": 1.8732117310440104,
    "arm_j6_abs_dev_from_1p57_p95": 1.4422924113273616,
    "wrist_tower_panel_min_clearance_m": 0.03349358061980283,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03691275167785235,
    "doorway_bearing_deg_p95_stage5": 142.52229003906248,
    "stage0_2_vy_cmd_at_clip_share": 0.2066407629812787,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.49276361130255
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 213.4962661328161,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 177.94588388096957,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 174.47436080000773,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 297.8738075977122,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.03504672897196257,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.9641873278236917,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.518134715025914,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 4.4702914798204665,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 7.491819269000552,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.08528111181301326,
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
    "posture_frame_denominator": 4749,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 36,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 0.0,
        "p5": 0.0,
        "p50": 0.09999999999999964,
        "p95": 0.2500000000000001,
        "max": 0.5199999999999996
      }
    }
  },
  "event_counts": {
    "all": 11248,
    "stage0_2": 5662,
    "stage5": 405,
    "stage2_4": 5804,
    "stage0_5": 4749,
    "crossing_episodes": 43
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
      "through_batch": 5000,
      "updates": 319728,
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
        "update_index": 319727,
        "common_step": 320000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 0.8333333333333334,
        "driver_right": 0.6666666666666666,
        "natural_sample_left": 6,
        "natural_sample_right": 3,
        "natural_reached_left": 5,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s281_5000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s281_5000.json)；完整逐阶段指标见相邻 JSON。
