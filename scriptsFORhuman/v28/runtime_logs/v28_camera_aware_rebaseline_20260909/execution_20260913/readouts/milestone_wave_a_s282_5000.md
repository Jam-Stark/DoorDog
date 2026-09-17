# base_v28 step5000 readout

2026-09-15 20:47 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S282 | left/nominal | 53 / 64 / 63 / 63 / 63 / 63 / 12 | 0 | 0 | 846.13 | 1.7239 | CAMERA_UNMET |
| A_S282 | right/nominal | 64 / 64 / 64 / 64 / 64 / 64 / 7 | 0 | 0 | 0 | 0.92155 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

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

## 决策与 K trace

```json
{
  "typed_outcomes": null,
  "invalid_cells": {},
  "k_driver_trace": {
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
    }
  }
}
```

针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s282_5000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s282_5000.json)；完整逐阶段指标见相邻 JSON。
