# base_v28 step6000 readout

2026-09-16 05:00 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S281 | left/nominal | 58 / 62 / 62 / 62 / 62 / 62 / 59 | 1 | 3.6402e-05 | 0 | 1.1981 | CAMERA_UNMET |
| A_S281 | right/nominal | 2 / 64 / 63 / 51 / 63 / 63 / 43 | 0 | 0 | 536.01 | 1.3654 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S281 / left / nominal

```json
{
  "quality_components": {
    "complete": 62,
    "clean_complete": 59,
    "hinge_below_1p0472": 3,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 2
  },
  "terminal_reasons": {
    "upper_dof_overspeed": 2,
    "complete": 62
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 72.3075265301235,
    "wrist_cam_ang_speed_p95_deg_s": 160.5942198687787,
    "wrist_cam_axis_sweep_p95_deg_s": 134.76793732396595,
    "base_cam_ang_speed_p95_deg_s": 93.77451909978019,
    "wrist_cam_axis_elev_p5_deg": -49.88448925109256,
    "wrist_cam_axis_elev_p50_deg": -28.900020488005367,
    "wrist_cam_axis_elev_p95_deg": 0.8278336519598,
    "arm_posture_l1_p50_rad": 1.9628194502511178,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 7.559875726699829,
    "crossing_yaw_deg_p50": 177.16008758544922,
    "arm_posture_l1_p95_rad": 4.414999652281402,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 28.658742904663086,
    "crossing_yaw_deg_p95": 179.8007583618164,
    "wrist_cam_share_axis_sweep_gt_60": 0.43376651741836847,
    "arm_j6_reversals_per_s": 0.7406866858834509,
    "arm_j6_abs_dev_from_1p57_p95": 0.5244643259048462,
    "wrist_tower_panel_min_clearance_m": -5.9202651751681656e-05,
    "wrist_tower_contact_step_share": 3.640202395253176e-05,
    "wrist_tower_contact_episodes_gt_5N": 1,
    "handle_bearing_gt_30deg_share_stage0_2": 0.04271548436308162,
    "doorway_bearing_deg_p95_stage5": 178.88777770996094,
    "stage0_2_vy_cmd_at_clip_share": 0.32837528604118993,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.3142205323193916
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 184.7891129414966,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 130.7392620790549,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 154.25217307814845,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 174.94678855381065,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.04900759617740696,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.3457479073152793,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.531319910514542,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.6240852484272121,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 4.414999652281402,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.28730923694779115,
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
    "posture_frame_denominator": 12450,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 61,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 2.3000000000000007,
        "p5": 2.459999999999999,
        "p50": 2.6599999999999993,
        "p95": 2.9400000000000004,
        "max": 3.4800000000000004
      }
    }
  },
  "event_counts": {
    "all": 27471,
    "stage0_2": 7866,
    "stage5": 8305,
    "stage2_4": 13150,
    "stage0_5": 12450,
    "crossing_episodes": 62
  }
}
```

### A_S281 / right / nominal

```json
{
  "quality_components": {
    "complete": 63,
    "clean_complete": 43,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 20,
    "low_height_or_overspeed": 1
  },
  "terminal_reasons": {
    "upper_dof_overspeed": 1,
    "complete": 63
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 59.510996067643276,
    "wrist_cam_ang_speed_p95_deg_s": 122.76093727589092,
    "wrist_cam_axis_sweep_p95_deg_s": 93.27933526152886,
    "base_cam_ang_speed_p95_deg_s": 70.37113221168813,
    "wrist_cam_axis_elev_p5_deg": -43.98016483848263,
    "wrist_cam_axis_elev_p50_deg": -30.88446606194158,
    "wrist_cam_axis_elev_p95_deg": -16.360180816527176,
    "arm_posture_l1_p50_rad": 1.337203711271286,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 5.940798997879028,
    "crossing_yaw_deg_p50": 169.2146759033203,
    "arm_posture_l1_p95_rad": 6.576085069775578,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 25.354232978820768,
    "crossing_yaw_deg_p95": 177.01595001220704,
    "wrist_cam_share_axis_sweep_gt_60": 0.2606747303993005,
    "arm_j6_reversals_per_s": 0.5824569091442475,
    "arm_j6_abs_dev_from_1p57_p95": 1.062049622535705,
    "wrist_tower_panel_min_clearance_m": 0.02870825459245369,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.027777777777777776,
    "doorway_bearing_deg_p95_stage5": 177.61382064819335,
    "stage0_2_vy_cmd_at_clip_share": 0.19061728395061728,
    "handle_in_wrist_depth_share_stage2_4": 0.96669391091132,
    "handle_in_wrist_rgb_share_stage2_4": 0.6595831630568042
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 169.42239614704158,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 141.67073405180858,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 114.31572439852685,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 118.17956290485378,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.06703910614525191,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.2304949117160567,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.1807851239669404,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.841948900772492,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 6.576085069775578,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.4194670476427107,
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
    "posture_frame_denominator": 16099,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 49,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 3.5999999999999996,
        "p5": 3.64,
        "p50": 3.8000000000000007,
        "p95": 4.0200000000000005,
        "max": 4.12
      }
    }
  },
  "event_counts": {
    "all": 27448,
    "stage0_2": 8100,
    "stage5": 11560,
    "stage2_4": 9788,
    "stage0_5": 16099,
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
    "A_S281": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s281/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 6000,
      "updates": 383721,
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
        "update_index": 383720,
        "common_step": 384000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 0.5,
        "natural_sample_left": 3,
        "natural_sample_right": 2,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s281_6000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s281_6000.json)；完整逐阶段指标见相邻 JSON。
