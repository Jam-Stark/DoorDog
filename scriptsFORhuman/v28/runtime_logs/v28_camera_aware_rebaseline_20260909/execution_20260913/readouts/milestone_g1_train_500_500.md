# base_v28 step500 readout

2026-09-14 08:47 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| G1_WARM | left/nominal | 62 / 64 / 64 / 64 / 64 / 64 / 64 | 0 | 0 | 0 | 1.3943 | CAMERA_UNMET |
| G1_WARM | right/nominal | 58 / 63 / 63 / 63 / 63 / 63 / 47 | 6 | 0.00088183 | 0 | 1.1325 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### G1_WARM / left / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 64,
    "hinge_below_1p0472": 0,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 73.89998411016964,
    "wrist_cam_ang_speed_p95_deg_s": 211.97430698963734,
    "wrist_cam_axis_sweep_p95_deg_s": 156.01960601053023,
    "base_cam_ang_speed_p95_deg_s": 61.985020467175104,
    "wrist_cam_axis_elev_p5_deg": -50.832882602809114,
    "wrist_cam_axis_elev_p50_deg": -24.26434269911891,
    "wrist_cam_axis_elev_p95_deg": -7.880096808270283,
    "arm_posture_l1_p50_rad": 0.6520311629465141,
    "post_release_return_time_p50_s": 1.0100000000000002,
    "handle_bearing_deg_p50_stage0_2": 9.55060625076294,
    "crossing_yaw_deg_p50": 167.31439971923828,
    "arm_posture_l1_p95_rad": 2.310167969261238,
    "post_release_return_time_p95_s": 1.3809999999999993,
    "handle_bearing_deg_p95_stage0_2": 33.57376861572264,
    "crossing_yaw_deg_p95": 172.29220809936524,
    "wrist_cam_share_axis_sweep_gt_60": 0.4979224603304433,
    "arm_j6_reversals_per_s": 1.2819251827814506,
    "arm_j6_abs_dev_from_1p57_p95": 0.4699964332580564,
    "wrist_tower_panel_min_clearance_m": 0.05395333794452839,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.08100475624256837,
    "doorway_bearing_deg_p95_stage5": 175.06711425781248,
    "stage0_2_vy_cmd_at_clip_share": 0.3745541022592152,
    "handle_in_wrist_depth_share_stage2_4": 0.9994385176866929,
    "handle_in_wrist_rgb_share_stage2_4": 0.6347958610732334
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 187.95857424409195,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 372.89404694465674,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 150.74612718959645,
        "limit": 150,
        "pass": false
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 209.06236388523763,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.021514629948365203,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.522321064229063,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 5.605889014722629,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 0.9113236814891127,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 2.310167969261238,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.09595396089024605,
        "limit": 0.05,
        "pass": false
      },
      "post_release_return_p50_s": {
        "value": 1.0100000000000002,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 1.3809999999999993,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 17029,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 54,
      "right_censored_episodes": 1,
      "observed": {
        "min": 0.2599999999999998,
        "p5": 0.27999999999999936,
        "p50": 1.0100000000000002,
        "p95": 1.3809999999999993,
        "max": 1.7000000000000002
      },
      "censor_duration": {
        "min": 3.6999999999999993,
        "p5": 3.6999999999999993,
        "p50": 3.6999999999999993,
        "p95": 3.6999999999999993,
        "max": 3.6999999999999993
      }
    }
  },
  "event_counts": {
    "all": 30565,
    "stage0_2": 6728,
    "stage5": 12317,
    "stage2_4": 12467,
    "stage0_5": 17029,
    "crossing_episodes": 64
  }
}
```

### G1_WARM / right / nominal

```json
{
  "quality_components": {
    "complete": 63,
    "clean_complete": 47,
    "hinge_below_1p0472": 16,
    "body_contact_above_5N": 0,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "stage_overtime": 1,
    "complete": 63
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 62.056779380196595,
    "wrist_cam_ang_speed_p95_deg_s": 219.45708301471052,
    "wrist_cam_axis_sweep_p95_deg_s": 158.51428870889967,
    "base_cam_ang_speed_p95_deg_s": 59.22921640382066,
    "wrist_cam_axis_elev_p5_deg": -75.34908763050099,
    "wrist_cam_axis_elev_p50_deg": -34.16319089822866,
    "wrist_cam_axis_elev_p95_deg": -9.761801707974405,
    "arm_posture_l1_p50_rad": 0.9620011409842846,
    "post_release_return_time_p50_s": 0.4600000000000004,
    "handle_bearing_deg_p50_stage0_2": 5.470830678939819,
    "crossing_yaw_deg_p50": 169.3479461669922,
    "arm_posture_l1_p95_rad": 2.638949855603274,
    "post_release_return_time_p95_s": 0.54,
    "handle_bearing_deg_p95_stage0_2": 26.377014636993408,
    "crossing_yaw_deg_p95": 170.70794525146485,
    "wrist_cam_share_axis_sweep_gt_60": 0.3459729570840682,
    "arm_j6_reversals_per_s": 1.2338809975785967,
    "arm_j6_abs_dev_from_1p57_p95": 0.268869750499725,
    "wrist_tower_panel_min_clearance_m": -0.00010759078519735968,
    "wrist_tower_contact_step_share": 0.0008818342151675485,
    "wrist_tower_contact_episodes_gt_5N": 6,
    "handle_bearing_gt_30deg_share_stage0_2": 0.028165236051502146,
    "doorway_bearing_deg_p95_stage5": 176.4623794555664,
    "stage0_2_vy_cmd_at_clip_share": 0.1520922746781116,
    "handle_in_wrist_depth_share_stage2_4": 0.9998104145601617,
    "handle_in_wrist_rgb_share_stage2_4": 0.48192618806875637
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 181.52133735517535,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 377.3965252878622,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 118.4161074435787,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 303.56509111125314,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.045150803684307586,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 1.0036945812807485,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 6.138107416879893,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 1.1587384561768161,
        "limit": 2.5,
        "pass": true
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 2.638949855603274,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.018136970400464306,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": 0.4600000000000004,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 0.54,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 13784,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 10,
      "right_censored_episodes": 53,
      "observed": {
        "min": 0.379999999999999,
        "p5": 0.3979999999999994,
        "p50": 0.4600000000000004,
        "p95": 0.54,
        "max": 0.54
      },
      "censor_duration": {
        "min": 2.200000000000001,
        "p5": 2.3440000000000003,
        "p50": 2.62,
        "p95": 3.3040000000000003,
        "max": 3.4799999999999995
      }
    }
  },
  "event_counts": {
    "all": 30618,
    "stage0_2": 7456,
    "stage5": 8183,
    "stage2_4": 15824,
    "stage0_5": 13784,
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
    "G1_WARM": {
      "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/g1_train_500/attempt2/a2_v26_8_penalty_curriculum_trace.jsonl",
      "through_batch": 500,
      "updates": 31998,
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
        "update_index": 31997,
        "common_step": 32000,
        "scale_before": 0.20803643763065338,
        "scale_after": 0.20801563560962677,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 1,
        "natural_sample_right": 1,
        "natural_reached_left": 1,
        "natural_reached_right": 1,
        "consumed": true,
        "skipped": false
      },
      "scale_min": 0.20801563560962677,
      "scale_max": 1.0,
      "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."
    }
  }
}
```

针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_g1_train_500_500.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_g1_train_500_500.json)；完整逐阶段指标见相邻 JSON。
