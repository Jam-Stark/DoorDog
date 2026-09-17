# base_v28 step4000 readout

2026-09-17 08:42 HKT

状态：`V28_COMPLETE`；每侧 exact 64。证据：实际模拟评估观测；资格结论以权威 decision 为准。

| Cell | 侧/层 | D / S3+ / S4+ / open_hold / S5+ / complete / clean | 塔架 >5N 集数 | 塔架 >1N 步占比 | 松手后身体力 p95 N | crossing hinge p50 rad | 相机标签 |
|---|---|---|---:|---:|---:|---:|---|
| A_S284 | left/nominal | 64 / 64 / 64 / 64 / 64 / 64 / 13 | 0 | 0 | 0 | 0.95696 | CAMERA_UNMET |
| A_S284 | right/nominal | 64 / 64 / 64 / 64 / 64 / 64 / 12 | 0 | 0 | 0 | 0.95589 | CAMERA_UNMET |

## 质量分量与阶段/相机事件

无事件保留 null；相机标签仅报告，不改变 reach 或资格门。回位分位数仅基于已观察到回位的集，未回位集单列为右删失。

### A_S284 / left / nominal

```json
{
  "quality_components": {
    "complete": 64,
    "clean_complete": 13,
    "hinge_below_1p0472": 50,
    "body_contact_above_5N": 1,
    "low_height_or_overspeed": 0
  },
  "terminal_reasons": {
    "complete": 64
  },
  "camera_plan_fields": {
    "wrist_cam_ang_speed_p50_deg_s": 49.17615909866436,
    "wrist_cam_ang_speed_p95_deg_s": 170.90514033427078,
    "wrist_cam_axis_sweep_p95_deg_s": 115.73327186990258,
    "base_cam_ang_speed_p95_deg_s": 59.08309247018899,
    "wrist_cam_axis_elev_p5_deg": -42.21266156641965,
    "wrist_cam_axis_elev_p50_deg": -24.292630121288667,
    "wrist_cam_axis_elev_p95_deg": -10.62452142967797,
    "arm_posture_l1_p50_rad": 0.843194521253281,
    "post_release_return_time_p50_s": 1.08,
    "handle_bearing_deg_p50_stage0_2": 6.979592800140381,
    "crossing_yaw_deg_p50": 158.44965362548828,
    "arm_posture_l1_p95_rad": 3.8182852640748015,
    "post_release_return_time_p95_s": 1.745999999999993,
    "handle_bearing_deg_p95_stage0_2": 31.696977138519273,
    "crossing_yaw_deg_p95": 160.0961929321289,
    "wrist_cam_share_axis_sweep_gt_60": 0.17721793255594076,
    "arm_j6_reversals_per_s": 2.1112732723269763,
    "arm_j6_abs_dev_from_1p57_p95": 0.18891392278671262,
    "wrist_tower_panel_min_clearance_m": 0.018938699913799147,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.06363004172461753,
    "doorway_bearing_deg_p95_stage5": 179.15888214111328,
    "stage0_2_vy_cmd_at_clip_share": 0.39586230876216966,
    "handle_in_wrist_depth_share_stage2_4": 0.9987861458782908,
    "handle_in_wrist_rgb_share_stage2_4": 0.5811124298662063
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 186.18739922260724,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 239.05971697878573,
        "limit": 250,
        "pass": true
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 99.32341751740438,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 363.3368805839003,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.06223549912870212,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.13813744675951814,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 9.152086137281435,
        "limit": 2.5,
        "pass": false
      },
      "stage4_j6_reversals_per_s": {
        "value": 2.685545355532594,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.8182852640748015,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.0016365336658354115,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": 1.08,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 1.745999999999993,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 12832,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 19,
      "right_censored_episodes": 45,
      "observed": {
        "min": 0.7400000000000002,
        "p5": 0.8119999999999987,
        "p50": 1.08,
        "p95": 1.745999999999993,
        "max": 4.5
      },
      "censor_duration": {
        "min": 2.4800000000000004,
        "p5": 2.623999999999999,
        "p50": 2.8200000000000003,
        "p95": 3.011999999999998,
        "max": 3.1999999999999993
      }
    }
  },
  "event_counts": {
    "all": 50768,
    "stage0_2": 5752,
    "stage5": 8751,
    "stage2_4": 37072,
    "stage0_5": 12832,
    "crossing_episodes": 64
  }
}
```

### A_S284 / right / nominal

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
    "wrist_cam_ang_speed_p50_deg_s": 77.42242332572421,
    "wrist_cam_ang_speed_p95_deg_s": 216.90510804316082,
    "wrist_cam_axis_sweep_p95_deg_s": 172.42342503705044,
    "base_cam_ang_speed_p95_deg_s": 72.18919520187595,
    "wrist_cam_axis_elev_p5_deg": -48.19874519511854,
    "wrist_cam_axis_elev_p50_deg": -28.086517780641856,
    "wrist_cam_axis_elev_p95_deg": -12.568013633064899,
    "arm_posture_l1_p50_rad": 0.8030383512377739,
    "post_release_return_time_p50_s": 0.8999999999999995,
    "handle_bearing_deg_p50_stage0_2": 5.66302490234375,
    "crossing_yaw_deg_p50": 169.6569366455078,
    "arm_posture_l1_p95_rad": 3.3925091475248337,
    "post_release_return_time_p95_s": 1.2239999999999998,
    "handle_bearing_deg_p95_stage0_2": 26.83012065887452,
    "crossing_yaw_deg_p95": 174.23004074096679,
    "wrist_cam_share_axis_sweep_gt_60": 0.4576009413841289,
    "arm_j6_reversals_per_s": 2.24659049023306,
    "arm_j6_abs_dev_from_1p57_p95": 0.23989754199981683,
    "wrist_tower_panel_min_clearance_m": 0.04534693780951965,
    "wrist_tower_contact_step_share": 0.0,
    "wrist_tower_contact_episodes_gt_5N": 0,
    "handle_bearing_gt_30deg_share_stage0_2": 0.033304272013949435,
    "doorway_bearing_deg_p95_stage5": 90.10676040649413,
    "stage0_2_vy_cmd_at_clip_share": 0.15780296425457715,
    "handle_in_wrist_depth_share_stage2_4": 0.9995145336488864,
    "handle_in_wrist_rgb_share_stage2_4": 0.4716912434006918
  },
  "camera_targets": {
    "outcome": "CAMERA_UNMET",
    "report_only": true,
    "checks": {
      "stage2_wrist_speed_p95_deg_s": {
        "value": 105.59803681799337,
        "limit": 105,
        "pass": false
      },
      "stage3_wrist_speed_p95_deg_s": {
        "value": 335.6280272935912,
        "limit": 250,
        "pass": false
      },
      "stage4_wrist_speed_p95_deg_s": {
        "value": 140.92366064887423,
        "limit": 150,
        "pass": true
      },
      "stage5_wrist_speed_p95_deg_s": {
        "value": 296.65420840683487,
        "limit": 90,
        "pass": false
      },
      "stage0_j6_reversals_per_s": {
        "value": 0.10065425264217245,
        "limit": 1.5,
        "pass": true
      },
      "stage5_j6_reversals_per_s": {
        "value": 0.30387220003474774,
        "limit": 1.5,
        "pass": true
      },
      "stage2_j6_reversals_per_s": {
        "value": 2.182284980744579,
        "limit": 2.5,
        "pass": true
      },
      "stage4_j6_reversals_per_s": {
        "value": 3.2077880625591546,
        "limit": 2.5,
        "pass": false
      },
      "stage0_5_arm_posture_l1_p95_rad": {
        "value": 3.3925091475248337,
        "limit": 0.5,
        "pass": false
      },
      "stage0_5_j6_deviation_gt_0p3_frame_share": {
        "value": 0.023932664030017238,
        "limit": 0.05,
        "pass": true
      },
      "post_release_return_p50_s": {
        "value": 0.8999999999999995,
        "limit": 2.0,
        "pass": true
      },
      "post_release_return_p95_s": {
        "value": 1.2239999999999998,
        "limit": 4.0,
        "pass": true
      }
    },
    "classification": "Any measured target failure: UNMET; no measured failure but missing events: PARTIAL; all targets measured and passed: MET.",
    "posture_frame_denominator": 9861,
    "release_censoring": {
      "threshold_l1_rad": 0.5,
      "observed_episodes": 17,
      "right_censored_episodes": 47,
      "observed": {
        "min": 0.33999999999999986,
        "p5": 0.3400000000000006,
        "p50": 0.8999999999999995,
        "p95": 1.2239999999999998,
        "max": 1.2399999999999993
      },
      "censor_duration": {
        "min": 1.54,
        "p5": 1.5999999999999996,
        "p50": 1.8600000000000003,
        "p95": 2.142,
        "max": 2.1800000000000006
      }
    }
  },
  "event_counts": {
    "all": 27194,
    "stage0_2": 5735,
    "stage5": 5823,
    "stage2_4": 16479,
    "stage0_5": 9861,
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
      "through_batch": 4000,
      "updates": 255947,
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
        "update_index": 255946,
        "common_step": 256000,
        "scale_before": 0.2941158413887024,
        "scale_after": 0.29408642649650574,
        "driver_left": 1.0,
        "driver_right": 1.0,
        "natural_sample_left": 1,
        "natural_sample_right": 2,
        "natural_reached_left": 1,
        "natural_reached_right": 2,
        "consumed": true,
        "skipped": false
      },
      "scale_min": 0.29408642649650574,
      "scale_max": 1.0,
      "scope": "Observed training curriculum updates through the requested batch; not an independent causal comparison."
    }
  }
}
```

针孔投影未建模遮挡或双目重建；采样间隙为几何代理。学习失败伴随塔架接触不能证明几何无解；A284 结果不计入原三 seed 终点分母。

来源：[reducer](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers/milestone_wave_a_s284_4000.json)；[manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/manifests/milestone_wave_a_s284_4000.json)；完整逐阶段指标见相邻 JSON。
