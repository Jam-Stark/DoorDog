# base_v28 execution closure

2026-09-17 17:31 HKT

执行状态：`V28_EXECUTION_CLOSED`。G1：`FAIL`；资格：`QUALIFICATION_NOT_CONFIRMED`。

原三 seed 的 6000 reach：`REACH_SEED_UNSTABLE`。历史候选、A284 与资格确认分别报告。

| 候选 | Cell / seed / step / driver | DEV | CONF |
|---|---|---|---|
| PRIMARY | A_S282 / 282 / 6000 / 4 | EVALUATED | NOT_RUN |
| BACKUP | A_S284 / 284 / 5000 / 5 | EVALUATED | NOT_RUN |

## 实际资格结果与Owner收尾决定

四条自然exact128 DEV均有效（invalid_cells为空、integrity=0、进程exit0）。门值为complete≥120、clean≥112、low_height+overspeed≤4、tower>5N集≤4。主候选LEFT通过、RIGHT未通过；备选双侧未通过，所以两者CONF均按合同NOT_RUN。未确认合格Teacher，不把未评估checkpoint一概判为不合格。

| 固定候选/侧别 | complete | clean | hinge不足 | 身体接触>5N | low-height/overspeed | tower>5N | DEV门 |
|---|---:|---:|---:|---:|---:|---:|---|
| A_S282@6000 left | 126/128 | 123/128 | 0 | 3 | 1 | 0 | PASS |
| A_S282@6000 right | 128/128 | 47/128 | 81 | 0 | 0 | 0 | FAIL |
| A_S284@5000 left | 128/128 | 69/128 | 59 | 0 | 0 | 0 | FAIL |
| A_S284@5000 right | 126/128 | 52/128 | 74 | 0 | 1 | 1 | FAIL |

hinge/身体接触分量在complete集合内解释，可重叠；low-height/overspeed按全部评估集计。三条未通过lane的clean缺口来自crossing hinge<1.0472rad；原门值保留，后续X21可据此独立重审。原三seed6000可靠性仍为1/3；A284不计分母，也不构成driver因果比较。

四条相机均CAMERA_UNMET（report-only）。回位观测/删失：A282 LEFT120/6、RIGHT9/119；A284 LEFT2/126、RIGHT0/126。观测回位p50/p95依次0.71/0.941s、0.76/0.80s、0.43/0.439s、null/null；这些量只描述已观察回位集，不能把删失窗口当完成时间。A282 LEFT有2集、A284 RIGHT有2集没有进入该release分母。完整26字段、逐stage速度/反向、posture及来源见qualification_summary和两个DEV readout；训练K trace沿用各milestone记录。

Owner D058要求提前终止训练。A284已打印5167迭代、保存至5000；6000训练/评估取消，原D040完整历史条件未达成。按Owner明确修改的执行范围，从已有完整评估中沿原D039排序冻结，身份先于DEV结果读取落锁。已记录预算23667；中断中额外计算未知，未宣称A284完成6000。

## 复用已有render与三相机观察

Owner D059明确要求跳过重复render，使用现成材料。以下保持各自原始配置/选择口径：

- [A282@6000 LEFT四视角演示](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v28/owner_left_fourview_20260917/LEFT_clean_complete_four_views.mp4)：原Owner演示按clean episode选择env0；用于行为展示，不代替统计。
- [主线140mm/38.76°三相机高低把手观察](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v28/side_rgbd_a282_6000_20260917/README.md)：实际把手高度0.85/0.95m、LEFT；保留原RGB/理想depth图和帧记录。
- [180mm/45°光学外参三相机视频](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v28/side_video_a282_6000_h180_h110_20260917/three_camera_rgb_depth.mp4)及[第二次视频](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v28/side_video_a282_6000_h180_h110_20260917/run_r2/three_camera_rgb_depth.mp4)：1.10m把手，物理塔架仍为主线140mm；8.92s/9.6s。
- [隐藏visual包络后的三相机视频](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v28/side_camera_visual_only_20260917/three_camera_rgb_depth.mp4)与[观察说明](/home/baoquanc/workspace/DoorDog-A2_Piper/logs_eval/base_v28/side_camera_visual_only_20260917/README.md)：独立预览保留collision，主线asset/config未随之修改；9.6s。

四份视频首帧均可解码；该窄检查不重评光学覆盖。Depth为理想光轴Z，未建立真实RealSense重建/噪声/畸变或硬件能力。已找到的复用素材来自主候选LEFT，不假定覆盖备选及全部双侧固定render。Owner豁免后没有补跑要求。

本轮自动render的主候选LEFT在取消处理前已完成（seed280303、固定env0/1/2、9个视频），予以保留；RIGHT在watcher取消的交接窗口启动后已取消，备选两侧NOT_RUN_OWNER_REUSE。取消不计作策略失败。

[复用素材与取消记录](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/owner_reuse_render_20260917.json)；[已完成主候选LEFT render manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/attempts/render_0_a_s282_step6000_left/attempt1/render_manifest.json)。

## 后续范围

N01/N02继续有界立项设计、实验执行DEFER；本次X05增量复核完成。Owner更急切的后续改动优先，v29范围尚未定义；未自动启动新训练/方法实验。X24/X25和C_S/G2继续保持原入场条件；Teacher/G7绑定、硬件与push未授权。

[DEV主候选](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/qualification_0_dev.md) · [DEV备选](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/qualification_1_dev.md) · [结构化资格汇总](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/closure_evidence_20260917/qualification_summary.json)

## 预算与停止原因

```json
{
  "budget": {
    "cap_batches": 36500,
    "scheduled_batches": 0,
    "active_reserved_batches": 0,
    "actual_consumed_batches": 23667
  },
  "stop": null,
  "commit_milestones": {
    "wave_a_step1000_aggregate": "COMMITTED",
    "wave_a_endpoint_lock": "COMMITTED",
    "final_closure": "REACHED",
    "prior_final_closure_reference": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/archives/resume_wave_a_20260914T025619Z/closure_receipt_before_resume.json"
  }
}
```

## 后续议题回收

```json
{
  "schema": "a2_piper_v28_next_stage_review_v1",
  "recorded_at": "2026-09-17 17:31 HKT",
  "review_scope": "Resumed v28 closure after Owner D058/D059; focused scope_planner recommendation integrated by Main.",
  "evidence_level": "INSPECTED with completed Wave B experiment references; no method experiment",
  "v28_context": {
    "qualification": "QUALIFICATION_NOT_CONFIRMED",
    "original_three_seed_endpoint": "1/3 REACH_SEED_UNSTABLE",
    "primary": "A_S282@6000 DEV clean123/128 LEFT,47/128 RIGHT",
    "backup": "A_S284@5000 DEV clean69/128 LEFT,52/128 RIGHT",
    "CONF": "NOT_RUN_DEV_DID_NOT_PASS_BILATERALLY",
    "source": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/closure_evidence_20260917/qualification_summary.json"
  },
  "decisions": {
    "N01": {
      "disposition": "CONTINUE",
      "scope": "Bounded pilot design only",
      "experiment_execution": "DEFER",
      "rationale": "Old recovery pilot remains UNRESOLVED: R1 endpoint absent, R2 loss exposure onlyLEFT5/64 RIGHT2/64. V28 nominal reach/completion does not establish induced-loss recovery benefit.",
      "next_steps": [
        "Distinguish unplanned grasp loss from planned release and define duration.",
        "Design perturbation timing/magnitude and sham/nominal controls with all-injection denominator.",
        "Specify asset/checkpoint, reachable interaction window and separate small budget before execution; only then decide multiseed."
      ]
    },
    "N02": {
      "disposition": "CONTINUE",
      "scope": "Deployable sensing and identifiability design only",
      "experiment_execution": "DEFER",
      "rationale": "Offline shadow estimator excluded51 short-window episodes; neither failure/short-episode validity nor online adaptation benefit established. V28 qualification outcome does not settle this method question.",
      "next_steps": [
        "Define proprio/action history/gripper qpos and actual effort availability; do not equate simulator door state/hand_force to deployable input.",
        "Stratify physical mass/friction, side and exposure including short/failed episodes and v27 unconverged domains.",
        "Propose finite-domain pilot with separate scope/budget after informative interaction window is specified."
      ]
    }
  },
  "priority": "Owner urgent next-stage changes take priority. No automatic assignment to v29 and no new experiment authorization.",
  "prior_review": "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/next_stage_review.json",
  "references": [
    "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/novelty/documents/20260914_v28_g1_closure_N01_N02.md",
    "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/a2_piper_longterm_TODO.md"
  ]
}
```

本次回收只确定后续立项去向，未启动新的方法实验。

## 证据与限制

G0 沿用既有准入证据；原 FAIL、D36/D37、旧 C3 时点不改写。X24 未建立随机分布校准；X25 的臂前伸耦合残余仍是后续分析线索。相机投影与采样间隙不构成光学、CAD 或硬件验收；无事件保持 null。塔架接触伴随学习失败只支持待区分解释。

[候选与完整评估 manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/a2_piper_base_v28_teacher_candidate_manifest_20260917.json)；[执行状态](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/state.json)；[逐 milestone reducers](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers)；[readouts](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts)。

训练、评估与 render 任务均已到终态；watcher/supervisor 与 writer 资源的最终释放由 Main 记录在 cleanup receipt。

## 资源与归档

本任务训练、评估、render、watcher和持久等待均已终止，已确认无本任务存活Python进程、tmux或GPU作业；output_root lease已释放，team task标记done。外部任务未改动，checkpoint和原始证据保留。[cleanup receipt](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/cleanup_receipt_20260917.json)。旧v1.3事件未清空或升级为实验结论。
