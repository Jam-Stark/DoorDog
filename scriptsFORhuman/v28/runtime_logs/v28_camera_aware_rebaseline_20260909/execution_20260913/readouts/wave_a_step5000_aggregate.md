# base_v28 step5000 readout

2026-09-15 21:52 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S281 | left/nominal | 54 / 55 / 55 / 55 / 54 / 52 / 51 | 0 | 0 | 0 | 1.3327 | CAMERA_UNMET |
| A_S281 | right/nominal | 14 / 44 / 44 / 44 / 42 / 0 / 0 | 0 | 0 | 155.07 | 1.4202 | CAMERA_UNMET |
| A_S282 | left/nominal | 53 / 64 / 63 / 63 / 63 / 63 / 12 | 0 | 0 | 846.13 | 1.7239 | CAMERA_UNMET |
| A_S282 | right/nominal | 64 / 64 / 64 / 64 / 64 / 64 / 7 | 0 | 0 | 0 | 0.92155 | CAMERA_UNMET |
| A_S283 | left/nominal | 64 / 64 / 64 / 64 / 0 / 0 / 0 | 0 | 0 | 0 | 0.85877 | CAMERA_UNMET |
| A_S283 | right/nominal | 61 / 64 / 64 / 64 / 0 / 0 / 0 | 16 | 0.011853 | 0 | 1.3425 | CAMERA_UNMET |

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

### A_S282 / left / nominal

```json
{
  "quality_components": {
    "complete": 63,
    "clean_complete": 12,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 51,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 63,
    "stage_overtime": 1
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 65.85224098321405,
    "wrist_cam_ang_speed_p95_deg_s": 189.23225305755443,
    "wrist_cam_axis_sweep_p95_deg_s": 159.31539772484078,
    "base_cam_ang_speed_p95_deg_s": 64.02295514132229,
    "wrist_cam_axis_elev_p5_deg": -50.27037553025915,
    "wrist_cam_axis_elev_p50_deg": -25.733157146472927,
    "wrist_cam_axis_elev_p95_deg": -5.30987404542104,
    "arm_posture_l1_p50_rad": 0.5923257513495628,
    "post_release_return_time_p50_s": 0.41999999999999993,
    "handle_bearing_deg_p50_stage0_2": 9.30545711517334,
    "crossing_yaw_deg_p50": 159.84005737304688,
    "arm_posture_l1_p95_rad": 1.2147920440802409,
    "post_release_return_time_p95_s": 0.7380000000000002,
    "handle_bearing_deg_p95_stage0_2": 32.117233276367195,
    "crossing_yaw_deg_p95": 164.75283813476562,
    "wrist_cam_share_axis_sweep_gt_60": 0.3787334676359814,
    "arm_j6_reversals_per_s": 1.3630912335104781,
    "arm_j6_abs_dev_from_1p57_p95": 0.2155455875396728,
    "wrist_tower_panel_min_clearance_m": 0.04793327484364604,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.06620087336244541,
    "doorway_bearing_deg_p95_stage5": 177.0234146118164,
    "stage0_2_vy_cmd_at_clip_share": 0.3507423580786026,
    "handle_in_wrist_depth_share_stage2_4": 0.9832753046505844,
    "handle_in_wrist_rgb_share_stage2_4": 0.9093509077343944
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 148.43797103115426,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 346.2028787393042,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 138.79293005001372,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 186.43241978447554,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.05064573309698567,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.3705103969753609,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 3.3887468030691075,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.7616318273765879,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 1.2147920440802409,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.029998265996185193,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": 0.41999999999999993,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.7380000000000002,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 17301,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 63,
      "right_censored_episodes": 0,
      "observed": {
        "min": 0.33999999999999986,
        "p5": 0.3420000000000007,
        "p50": 0.41999999999999993,
        "p95": 0.7380000000000002,
        "max": 1.7599999999999998
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
    "all": 34251,
    "stage0_2": 5725,
    "stage5": 13288,
    "stage2_4": 16084,
    "stage0_5": 17301,
    "crossing_episodes": 64
  }
}
```

### A_S282 / right / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 7,
    "hinge_below_1p0472": 57,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 93.17821146531084,
    "wrist_cam_ang_speed_p95_deg_s": 307.510638358801,
    "wrist_cam_axis_sweep_p95_deg_s": 238.6898779067871,
    "base_cam_ang_speed_p95_deg_s": 101.02508469429016,
    "wrist_cam_axis_elev_p5_deg": -42.457574881703245,
    "wrist_cam_axis_elev_p50_deg": -26.804387535746216,
    "wrist_cam_axis_elev_p95_deg": 8.071926729800166,
    "arm_posture_l1_p50_rad": 0.9511196725070477,
    "post_release_return_time_p50_s": 0.8600000000000003,
    "handle_bearing_deg_p50_stage0_2": 4.942252159118652,
    "crossing_yaw_deg_p50": 169.15953826904297,
    "arm_posture_l1_p95_rad": 3.4680359154939673,
    "post_release_return_time_p95_s": 1.072,
    "handle_bearing_deg_p95_stage0_2": 26.652424049377444,
    "crossing_yaw_deg_p95": 171.965283203125,
    "wrist_cam_share_axis_sweep_gt_60": 0.5306514145330313,
    "arm_j6_reversals_per_s": 2.585908338785688,
    "arm_j6_abs_dev_from_1p57_p95": 0.2809380578994751,
    "wrist_tower_panel_min_clearance_m": 0.03068493631548091,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03204320432043204,
    "doorway_bearing_deg_p95_stage5": 146.72926025390626,
    "stage0_2_vy_cmd_at_clip_share": 0.31989198919891987,
    "handle_in_wrist_depth_share_stage2_4": 0.998093422306959,
    "handle_in_wrist_rgb_share_stage2_4": 0.40896091515729266
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 313.75571690599094,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 116.61126483210366,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 186.87777515322463,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 425.1431659649707,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.0130276185513285,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.7073658311548949,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 4.617604617604687,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.825522303782551,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.4680359154939673,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.03744388193714777,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": 0.8600000000000003,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 1.072,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 10469,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 33,
      "right_censored_episodes": 31,
      "observed": {
        "min": 0.7199999999999998,
        "p5": 0.7199999999999998,
        "p50": 0.8600000000000003,
        "p95": 1.072,
        "max": 1.12
      },
      "censor_duration": {
        "min": 1.88,
        "p5": 1.9200000000000004,
        "p50": 2.12,
        "p95": 2.2600000000000002,
        "max": 2.3
      }
    }
  },
  "event_counts": {
    "all": 26051,
    "stage0_2": 5555,
    "stage5": 6567,
    "stage2_4": 14686,
    "stage0_5": 10469,
    "crossing_episodes": 64
  }
}
```

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
    "wrist_cam_ang_speed_p50_deg_s": 51.903833246734095,
    "wrist_cam_ang_speed_p95_deg_s": 125.09627209434248,
    "wrist_cam_axis_sweep_p95_deg_s": 94.08002796477457,
    "base_cam_ang_speed_p95_deg_s": 63.423994347020596,
    "wrist_cam_axis_elev_p5_deg": -49.42049380008571,
    "wrist_cam_axis_elev_p50_deg": -34.753338700337736,
    "wrist_cam_axis_elev_p95_deg": -14.977305767980473,
    "arm_posture_l1_p50_rad": 0.12745401554275304,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 11.231229782104492,
    "crossing_yaw_deg_p50": 158.8684844970703,
    "arm_posture_l1_p95_rad": 0.16681900974363087,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 32.70525588989258,
    "crossing_yaw_deg_p95": 160.0911781311035,
    "wrist_cam_share_axis_sweep_gt_60": 0.1954782824933687,
    "arm_j6_reversals_per_s": 2.162184594954841,
    "arm_j6_abs_dev_from_1p57_p95": 0.005727999210357598,
    "wrist_tower_panel_min_clearance_m": 0.011177515463176763,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.07767334633800319,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.4342968611455932,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.46163039231458713
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 175.64061242995794,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 330.80249263559415,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 115.43015901522264,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.0537778972842145,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.469879518072329,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.4417836078923227,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.16681900974363087,
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
    "posture_frame_denominator": 3783,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 1,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 4.58,
        "p5": 4.58,
        "p50": 4.58,
        "p95": 4.58,
        "max": 4.58
      }
    }
  },
  "event_counts": {
    "all": 48256,
    "stage0_2": 5639,
    "stage5": 0,
    "stage2_4": 43511,
    "stage0_5": 3783,
    "crossing_episodes": 64
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
    "wrist_cam_ang_speed_p50_deg_s": 44.30007677525546,
    "wrist_cam_ang_speed_p95_deg_s": 127.1564690191976,
    "wrist_cam_axis_sweep_p95_deg_s": 93.18314289448597,
    "base_cam_ang_speed_p95_deg_s": 50.6165135240297,
    "wrist_cam_axis_elev_p5_deg": -53.14981813933603,
    "wrist_cam_axis_elev_p50_deg": -32.20731006293988,
    "wrist_cam_axis_elev_p95_deg": -10.759975273462345,
    "arm_posture_l1_p50_rad": 0.12586317991372198,
    "post_release_return_time_p50_s": null,
    "handle_bearing_deg_p50_stage0_2": 7.23773980140686,
    "crossing_yaw_deg_p50": 160.61450958251953,
    "arm_posture_l1_p95_rad": 0.17188728039263879,
    "post_release_return_time_p95_s": null,
    "handle_bearing_deg_p95_stage0_2": 27.226088523864707,
    "crossing_yaw_deg_p95": 162.31939468383788,
    "wrist_cam_share_axis_sweep_gt_60": 0.18308604111405835,
    "arm_j6_reversals_per_s": 2.313662018593712,
    "arm_j6_abs_dev_from_1p57_p95": 0.0052327144145964954,
    "wrist_tower_panel_min_clearance_m": -0.0007926178480609988,
    "wrist_tower_contact_step_share": 0.011853448275862068,
    "wrist_tower_contact_episodes_gt_5N": 16,
    "handle_bearing_gt_30deg_share_stage0_2": 0.03473459209120057,
    "doorway_bearing_deg_p95_stage5": null,
    "stage0_2_vy_cmd_at_clip_share": 0.2892768079800499,
    "handle_in_wrist_depth_share_stage2_4": 1.0,
    "handle_in_wrist_rgb_share_stage2_4": 0.8049430356486585
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 130.76387333409414,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 353.29821873864864,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 114.55659391618329,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": null,
        "limit": 90,
        "pass": null
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.041299559471364114,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": null,
        "limit": 1.5,
        "pass": null
      },
      "stage2_j6_reversals_per_s": {
        "value": 1.566265060240989,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.6307664599803258,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 0.17188728039263879,
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
    "posture_frame_denominator": 3696,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 0,
      "right_censored_episodes": 5,
      "observed": {
        "min": null,
        "p5": null,
        "p50": null,
        "p95": null,
        "max": null
      },
      "censor_duration": {
        "min": 4.220000000000001,
        "p5": 4.392,
        "p50": 5.780000000000001,
        "p95": 9.443999999999999,
        "max": 9.82
      }
    }
  },
  "event_counts": {
    "all": 48256,
    "stage0_2": 5614,
    "stage5": 0,
    "stage2_4": 43536,
    "stage0_5": 3696,
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
    },
    "A_S282": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s282/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 5000,
      "updates": 319943,
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
        "update_index": 319942,
        "common_step": 320000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 3,
        "natural_sample_right": 2,
        "natural_reached_left": 3,
        "natural_reached_right": 2,
        "consumed": true,
        "skipped": false
      },
      "scale_min": 0.20000000298023224,
      "scale_max": 1.0,
      "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."
    },
    "A_S283": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/wave_a_s283/attempt1/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 5000,
      "updates": 319936,
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
        "update_index": 319935,
        "common_step": 320000,
        "scale_before": 0.20000000298023224,
        "scale_after": 0.20000000298023224,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 2,
        "natural_sample_right": 2,
        "natural_reached_left": 2,
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

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/aggregates/wave_a_step5000_reducer.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/aggregates/wave_a_step5000_manifest.json)；完整逐阶段指标见相邻 JSON。
