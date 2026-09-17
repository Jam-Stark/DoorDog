# base_v28 step6000 readout

2026-09-16 05:01 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S281 | left/nominal | 58 / 62 / 62 / 62 / 62 / 62 / 59 | 1 | 3.6402e-05 | 0 | 1.1981 | CAMERA_UNMET |
| A_S281 | right/nominal | 2 / 64 / 63 / 51 / 63 / 63 / 43 | 0 | 0 | 536.01 | 1.3654 | CAMERA_UNMET |
| A_S282 | left/nominal | 56 / 64 / 63 / 63 / 62 / 62 / 61 | 0 | 0 | 0 | 1.5617 | CAMERA_UNMET |
| A_S282 | right/nominal | 64 / 64 / 64 / 64 / 64 / 64 / 12 | 0 | 0 | 0 | 0.95449 | CAMERA_UNMET |
| A_S283 | left/nominal | 61 / 64 / 64 / 64 / 64 / 64 / 29 | 0 | 0 | 0 | 1.0314 | CAMERA_UNMET |
| A_S283 | right/nominal | 55 / 64 / 64 / 64 / 4 / 4 / 2 | 24 | 0.0070088 | 0 | 1.4041 | CAMERA_UNMET |

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

### A_S282 / left / nominal

```json
{
  "quality_components": {
    "complete": 62,
    "clean_complete": 61,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 1,
    "low_height_or_overspeed": 2
  },
  "terminal_reasons": {
    "upper_dof_overspeed": 2,
    "complete": 62
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 75.10784709841178,
    "wrist_cam_ang_speed_p95_deg_s": 202.124168396235,
    "wrist_cam_axis_sweep_p95_deg_s": 173.53941792040533,
    "base_cam_ang_speed_p95_deg_s": 76.52085374731584,
    "wrist_cam_axis_elev_p5_deg": -54.16361233888485,
    "wrist_cam_axis_elev_p50_deg": -40.803499814055044,
    "wrist_cam_axis_elev_p95_deg": -8.06781593018306,
    "arm_posture_l1_p50_rad": 0.5969907786493422,
    "post_release_return_time_p50_s": 0.7199999999999998,
    "handle_bearing_deg_p50_stage0_2": 8.672525405883789,
    "crossing_yaw_deg_p50": 165.42750549316406,
    "arm_posture_l1_p95_rad": 2.030420371515352,
    "post_release_return_time_p95_s": 1.0290000000000004,
    "handle_bearing_deg_p95_stage0_2": 31.52982759475708,
    "crossing_yaw_deg_p95": 175.9334846496582,
    "wrist_cam_share_axis_sweep_gt_60": 0.4648630693142393,
    "arm_j6_reversals_per_s": 1.0987791342956381,
    "arm_j6_abs_dev_from_1p57_p95": 0.3151966857910155,
    "wrist_tower_panel_min_clearance_m": 0.0074504039734820705,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.06258480325644505,
    "doorway_bearing_deg_p95_stage5": 172.55819702148438,
    "stage0_2_vy_cmd_at_clip_share": 0.3621099050203528,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.9141823030764835
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 135.9398702302326,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 330.5856002559129,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 150.94285343341025,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 197.9737343875603,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.012950012950012652,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.8207343412525449,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 0.6292906178489805,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.3750180923433548,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 2.030420371515352,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.0536563423724457,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.7199999999999998,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 1.0290000000000004,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 15562,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 58,
      "right_censored_episodes": 5,
      "observed": {
        "min": 0.5199999999999996,
        "p5": 0.5570000000000004,
        "p50": 0.7199999999999998,
        "p95": 1.0290000000000004,
        "max": 1.4799999999999995
      },
      "censor_duration": {
        "min": 0.39999999999999947,
        "p5": 1.0559999999999994,
        "p50": 3.880000000000001,
        "p95": 4.0440000000000005,
        "max": 4.080000000000001
      }
    }
  },
  "event_counts": {
    "all": 27094,
    "stage0_2": 5896,
    "stage5": 11637,
    "stage2_4": 10499,
    "stage0_5": 15562,
    "crossing_episodes": 62
  }
}
```

### A_S282 / right / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 12,
    "hinge_below_1p0472": 52,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 86.11654536462306,
    "wrist_cam_ang_speed_p95_deg_s": 271.26761255503857,
    "wrist_cam_axis_sweep_p95_deg_s": 227.76222955438,
    "base_cam_ang_speed_p95_deg_s": 112.77994956469142,
    "wrist_cam_axis_elev_p5_deg": -43.334252044918735,
    "wrist_cam_axis_elev_p50_deg": -24.91259898508898,
    "wrist_cam_axis_elev_p95_deg": 19.83398507033816,
    "arm_posture_l1_p50_rad": 1.1464586243964732,
    "post_release_return_time_p50_s": 0.7599999999999998,
    "handle_bearing_deg_p50_stage0_2": 5.384093284606934,
    "crossing_yaw_deg_p50": 174.23956298828125,
    "arm_posture_l1_p95_rad": 3.193228126317262,
    "post_release_return_time_p95_s": 0.8500000000000003,
    "handle_bearing_deg_p95_stage0_2": 26.292263412475574,
    "crossing_yaw_deg_p95": 176.26101837158203,
    "wrist_cam_share_axis_sweep_gt_60": 0.5287141322083814,
    "arm_j6_reversals_per_s": 2.326138131908364,
    "arm_j6_abs_dev_from_1p57_p95": 0.5151784706115722,
    "wrist_tower_panel_min_clearance_m": 0.01925078136010273,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.030620599312264615,
    "doorway_bearing_deg_p95_stage5": 146.76023788452147,
    "stage0_2_vy_cmd_at_clip_share": 0.27378418208613065,
    "handle_in_wrist_depth_share_stage2_4": 0.9991782459285821,
    "handle_in_wrist_rgb_share_stage2_4": 0.45465411624084867
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 247.47463634878088,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 111.67819857037695,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 166.38518946925146,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 376.82162611521613,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.07248127567045122,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 1.1512134411948487,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.204030226700287,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.5691109669042125,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.193228126317262,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.2433847592332866,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.7599999999999998,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.8500000000000003,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 10695,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 3,
      "right_censored_episodes": 61,
      "observed": {
        "min": 0.7400000000000002,
        "p5": 0.7420000000000002,
        "p50": 0.7599999999999998,
        "p95": 0.8500000000000003,
        "max": 0.8600000000000003
      },
      "censor_duration": {
        "min": 1.7599999999999998,
        "p5": 1.88,
        "p50": 2.0999999999999996,
        "p95": 2.3200000000000003,
        "max": 2.46
      }
    }
  },
  "event_counts": {
    "all": 25127,
    "stage0_2": 6107,
    "stage5": 6492,
    "stage2_4": 13386,
    "stage0_5": 10695,
    "crossing_episodes": 64
  }
}
```

### A_S283 / left / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 29,
    "hinge_below_1p0472": 34,
    "body_contact_above_5N": 1,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 60.50865196060758,
    "wrist_cam_ang_speed_p95_deg_s": 226.07369984308792,
    "wrist_cam_axis_sweep_p95_deg_s": 178.6948895208614,
    "base_cam_ang_speed_p95_deg_s": 65.22269573978174,
    "wrist_cam_axis_elev_p5_deg": -46.089039292641274,
    "wrist_cam_axis_elev_p50_deg": -33.95166223462533,
    "wrist_cam_axis_elev_p95_deg": 10.616293765442112,
    "arm_posture_l1_p50_rad": 0.894667269771162,
    "post_release_return_time_p50_s": 0.9199999999999999,
    "handle_bearing_deg_p50_stage0_2": 10.728398323059082,
    "crossing_yaw_deg_p50": 159.1650390625,
    "arm_posture_l1_p95_rad": 5.58956478536129,
    "post_release_return_time_p95_s": 0.9600000000000001,
    "handle_bearing_deg_p95_stage0_2": 32.95411376953125,
    "crossing_yaw_deg_p95": 160.3791030883789,
    "wrist_cam_share_axis_sweep_gt_60": 0.2981649825960596,
    "arm_j6_reversals_per_s": 1.7373928946395347,
    "arm_j6_abs_dev_from_1p57_p95": 0.3548289012908936,
    "wrist_tower_panel_min_clearance_m": 0.008553098221405188,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.08069422079083916,
    "doorway_bearing_deg_p95_stage5": 164.73297119140625,
    "stage0_2_vy_cmd_at_clip_share": 0.4524959742351047,
    "handle_in_wrist_depth_share_stage2_4": 0.9978083392690812,
    "handle_in_wrist_rgb_share_stage2_4": 0.43449673990466275
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 383.83514573178,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 265.7648119126439,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 124.28931520884403,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 300.29168581936204,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.013579576317218444,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.9249350252255719,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 4.6202531645570355,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.3506332599116893,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 5.58956478536129,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.0559366244807265,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 0.9199999999999999,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.9600000000000001,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 10351,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 18,
      "right_censored_episodes": 46,
      "observed": {
        "min": 0.8000000000000007,
        "p5": 0.8170000000000004,
        "p50": 0.9199999999999999,
        "p95": 0.9600000000000001,
        "max": 0.9600000000000009
      },
      "censor_duration": {
        "min": 1.7000000000000002,
        "p5": 1.87,
        "p50": 2.16,
        "p95": 2.5200000000000005,
        "max": 2.580000000000001
      }
    }
  },
  "event_counts": {
    "all": 29591,
    "stage0_2": 5589,
    "stage5": 6605,
    "stage2_4": 18251,
    "stage0_5": 10351,
    "crossing_episodes": 64
  }
}
```

### A_S283 / right / nominal

```json
{
  "quality_components": {
    "complete": 4,
    "clean_complete": 2,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 2,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 4,
    "stage_overtime": 60
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 43.721926989863924,
    "wrist_cam_ang_speed_p95_deg_s": 133.07483068721737,
    "wrist_cam_axis_sweep_p95_deg_s": 101.27836764556805,
    "base_cam_ang_speed_p95_deg_s": 52.99096925816834,
    "wrist_cam_axis_elev_p5_deg": -63.87399531606458,
    "wrist_cam_axis_elev_p50_deg": -36.03658117496137,
    "wrist_cam_axis_elev_p95_deg": -10.00100731809993,
    "arm_posture_l1_p50_rad": 0.13392382860183716,
    "post_release_return_time_p50_s": 0.5999999999999996,
    "handle_bearing_deg_p50_stage0_2": 6.525119781494141,
    "crossing_yaw_deg_p50": 158.9154815673828,
    "arm_posture_l1_p95_rad": 1.8098208541241543,
    "post_release_return_time_p95_s": 0.5999999999999996,
    "handle_bearing_deg_p95_stage0_2": 27.167516708374013,
    "crossing_yaw_deg_p95": 160.45379714965821,
    "wrist_cam_share_axis_sweep_gt_60": 0.19606013478486262,
    "arm_j6_reversals_per_s": 2.0317269159705944,
    "arm_j6_abs_dev_from_1p57_p95": 0.27841751098632805,
    "wrist_tower_panel_min_clearance_m": -0.0005233441936161633,
    "wrist_tower_contact_step_share": 0.007008812856402281,
    "wrist_tower_contact_episodes_gt_5N": 24,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03420487106017192,
    "doorway_bearing_deg_p95_stage5": 177.8088409423828,
    "stage0_2_vy_cmd_at_clip_share": 0.3103510028653295,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.7612543196039974
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 158.39878742507847,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 346.27844976739874,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 108.02232073048496,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 277.7035923565909,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.05511160099200677,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 1.0687022900763359,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 4.475703324808255,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.224812089150811,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 1.8098208541241543,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.04159007352941176,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": 0.5999999999999996,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.5999999999999996,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 4352,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 1,
      "right_censored_episodes": 7,
      "observed": {
        "min": 0.5999999999999996,
        "p5": 0.5999999999999996,
        "p50": 0.5999999999999996,
        "p95": 0.5999999999999996,
        "max": 0.5999999999999996
      },
      "censor_duration": {
        "min": 2.92,
        "p5": 2.9979999999999998,
        "p50": 4.32,
        "p95": 7.897999999999999,
        "max": 8.780000000000001
      }
    }
  },
  "event_counts": {
    "all": 48225,
    "stage0_2": 5584,
    "stage5": 659,
    "stage2_4": 42828,
    "stage0_5": 4352,
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
    },
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
    },
    "A_S283": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s283/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 6000,
      "updates": 383928,
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
        "update_index": 383927,
        "common_step": 384000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 2,
        "natural_sample_right": 4,
        "natural_reached_left": 2,
        "natural_reached_right": 4,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/aggregates/wave_a_step6000_reducer.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/aggregates/wave_a_step6000_manifest.json)；完整逐阶段指标见相邻 JSON。
