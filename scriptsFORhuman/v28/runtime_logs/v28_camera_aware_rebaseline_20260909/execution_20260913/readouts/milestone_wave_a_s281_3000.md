# base_v28 step3000 readout

2026-09-15 07:35 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S281 | left/nominal | 64 / 64 / 64 / 64 / 5 / 5 / 1 | 0 | 0 | 0 | 0.91349 | CAMERA_UNMET |
| A_S281 | right/nominal | 53 / 64 / 64 / 64 / 64 / 64 / 40 | 0 | 0 | 1080.7 | 1.6443 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S281 / left / nominal

```json
{
  "quality_components": {
    "complete": 5,
    "clean_complete": 1,
    "hinge_below_1p0472": 4,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 5,
    "stage_overtime": 59
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 67.73782701823552,
    "wrist_cam_ang_speed_p95_deg_s": 156.56623865551336,
    "wrist_cam_axis_sweep_p95_deg_s": 117.05724724343672,
    "base_cam_ang_speed_p95_deg_s": 50.6267868949109,
    "wrist_cam_axis_elev_p5_deg": -39.81606987747574,
    "wrist_cam_axis_elev_p50_deg": -28.45083281290662,
    "wrist_cam_axis_elev_p95_deg": -15.558735370354645,
    "arm_posture_l1_p50_rad": 0.13145256508141756,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 10.00781774520874,
    "crossing_yaw_deg_p50": 176.82917022705078,
    "arm_posture_l1_p95_rad": 1.7815534475880668,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 32.02792320251464,
    "crossing_yaw_deg_p95": 179.38659057617187,
    "wrist_cam_share_axis_sweep_gt_60": 0.3548934058435516,
    "arm_j6_reversals_per_s": 3.9785079818646616,
    "arm_j6_abs_dev_from_1p57_p95": 0.4748978579044342,
    "wrist_tower_panel_min_clearance_m": 0.05801841275090033,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.06723796967699407,
    "doorway_bearing_deg_p95_stage5": 167.2033935546875,
    "stage0_2_vy_cmd_at_clip_share": 0.3951878707976269,
    "handle_in_wrist_depth_share_stage2_4": 0.9977922870966227,
    "handle_in_wrist_rgb_share_stage2_4": 0.7543567100380477
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 287.1043573296443,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 204.53303489615504,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 144.46802925646935,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 256.5525688924415,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.0,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.38809831824062097,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 6.006006006006109,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 4.158542773966563,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 1.7815534475880668,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.08971291866028708,
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
    "posture_frame_denominator": 5016,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 6,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 2.58,
        "p5": 2.735,
        "p50": 3.670000000000001,
        "p95": 6.539999999999999,
        "max": 7.42
      }
    }
  },
  "event_counts": {
    "all": 48361,
    "stage0_2": 6068,
    "stage5": 778,
    "stage2_4": 42578,
    "stage0_5": 5016,
    "crossing_episodes": 64
  }
}
```

### A_S281 / right / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 40,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 24,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 53.428676271733245,
    "wrist_cam_ang_speed_p95_deg_s": 178.50638527635445,
    "wrist_cam_axis_sweep_p95_deg_s": 140.3057044535099,
    "base_cam_ang_speed_p95_deg_s": 61.1137770407306,
    "wrist_cam_axis_elev_p5_deg": -46.71959758589576,
    "wrist_cam_axis_elev_p50_deg": -38.957700419660654,
    "wrist_cam_axis_elev_p95_deg": -15.083270526207048,
    "arm_posture_l1_p50_rad": 0.5780307263557916,
    "post_release_return_time_p50_s": 0.8599999999999994,
    "handle_bearing_deg_p50_stage0_2": 6.221484661102295,
    "crossing_yaw_deg_p50": 160.58513641357422,
    "arm_posture_l1_p95_rad": 3.2290423993021298,
    "post_release_return_time_p95_s": 1.4540000000000004,
    "handle_bearing_deg_p95_stage0_2": 26.74001550674438,
    "crossing_yaw_deg_p95": 171.89054489135742,
    "wrist_cam_share_axis_sweep_gt_60": 0.3003381303863758,
    "arm_j6_reversals_per_s": 0.668896321070644,
    "arm_j6_abs_dev_from_1p57_p95": 0.2740726833343507,
    "wrist_tower_panel_min_clearance_m": 0.040490365946884585,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03308575286968265,
    "doorway_bearing_deg_p95_stage5": 174.2041778564453,
    "stage0_2_vy_cmd_at_clip_share": 0.17302498311951384,
    "handle_in_wrist_depth_share_stage2_4": 0.9984793627805938,
    "handle_in_wrist_rgb_share_stage2_4": 0.6623461259956553
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 239.48346591841397,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 227.94101139024997,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 95.480314474566,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 238.49954394073254,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.06043026347594826,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.4256795106262272,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.3893214682981155,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 0.6857960282735166,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.2290423993021298,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.03767021170857768,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": 0.8599999999999994,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 1.4540000000000004,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 20122,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 64,
      "right_censored_episodes": 0,
      "observed": {
        "min": 0.5,
        "p5": 0.5999999999999996,
        "p50": 0.8599999999999994,
        "p95": 1.4540000000000004,
        "max": 2.0999999999999996
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
    "all": 48502,
    "stage0_2": 5924,
    "stage5": 15921,
    "stage2_4": 27620,
    "stage0_5": 20122,
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
      "through_batch": 3000,
      "updates": 191951,
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
        "update_index": 191950,
        "common_step": 192000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 3,
        "natural_sample_right": 1,
        "natural_reached_left": 3,
        "natural_reached_right": 1,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s281_3000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s281_3000.json)；完整逐阶段指标见相邻 JSON。
