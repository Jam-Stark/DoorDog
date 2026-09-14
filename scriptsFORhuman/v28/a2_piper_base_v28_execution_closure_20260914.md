# base_v28 execution closure

2026-09-14 08:58 HKT

执行状态：`OWNER_DECISION_REQUIRED`。G1：`FAIL`；资格：`NOT_RUN`。

本次完成了实现同步、对应CPU检查、G1的500批训练及双侧exact64评估，并按预注册失败门停止。原三seed scratch、1000延长、Wave A/B及候选render均未执行。下一项仅为Owner成本复议：是否允许在原C_T、门值和既有预算内继续三seed scratch。

| G1门/读数（每侧64集） | LEFT | RIGHT | G1要求 |
|---|---:|---:|---|
| D | 62 | 58 | ≥40 |
| S4+ | 64 | 63 | PARTIAL需双侧≥32且至少一侧D<40 |
| complete / clean | 64 / 64 | 63 / 47 | clean≥36 |
| 非complete终止 | 0 | 1 | ≤2 |
| 塔架>5N集数 | 0 | 6 | ≤2；RIGHT使G1失败 |

RIGHT的16集clean损失来自crossing hinge质量分量；body、低高度或超速质量分量均0。两侧D均≥40，不能改走PARTIAL；RIGHT D58<既有SC1000最佳63−4=59，还满足warm附加臂取消条件。累计实际训练500批；首次外部GPU争用失败发生于policy读数前、消耗0批，仅使用1次资源修复。

双侧为report-only CAMERA_UNMET：Stage2腕速p95 LEFT/RIGHT为187.96/181.52°/s，Stage5为209.06/303.57°/s。Stage0/5姿态L1 p95为2.310/2.639rad。释放后回位LEFT为54集观察到/1集右删失，RIGHT为10/53；已观察到回位的RIGHT p50/p95=0.46/0.54s不能代表53集未观察到回位的轨迹。晚阶段camera字段已有事件，无事件仍按null规则处理。塔架采样间隙是几何代理，接触失败不证明几何无解。

D16的eval输出目录修复已在两侧真实评估成立；G1 policy_only+C_S2+actor RMS与500计数已核对。续训、候选冻结和DEV/CONF分支只有实现/CPU证据，未将其标为runtime通过。

[权威G1 decision](runtime_logs/v28_camera_aware_rebaseline_20260909/g1_probe_decision.json) · [停止点核对记录](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/g1_owner_gate_record.json) · [完整阶段/相机readout](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts/milestone_g1_train_500_500.md)

原三 seed 的 6000 reach：未评估（不是0/3）。历史候选、A284 与资格确认分别报告。

| 候选 | Cell / seed / step / driver | DEV | CONF |
|---|---|---|---|

候选资格确认未运行；具体前置条件与未完成项见 manifest。

## 预算与停止原因

```json
{
  "budget": {
    "cap_batches": 36500,
    "scheduled_batches": 0,
    "active_reserved_batches": 0,
    "actual_consumed_batches": 500
  },
  "stop": {
    "reason": "G1_WARM_FAIL",
    "decision": {
      "decision": "FAIL",
      "outcome": "WARM_FAIL",
      "step": 500,
      "action": "STOP",
      "warm_arm_cancelled": true,
      "wave_c_best_D_per_side": {
        "left": 0,
        "right": 63
      },
      "warm_arm_eligible": false,
      "additional_batches": 0
    },
    "at": "2026-09-14T00:47:50+00:00"
  },
  "commit_milestones": {
    "wave_a_step1000_aggregate": "NOT_REACHED_G1_OWNER_GATE",
    "wave_a_endpoint_lock": "NOT_REACHED_G1_OWNER_GATE",
    "final_closure": "SEE_LOCAL_COMMIT_RECEIPT"
  }
}
```

## 后续议题回收

```json
{
  "schema": "a2_piper_v28_next_stage_review_v1",
  "recorded_at": "2026-09-14T08:53:45+08:00",
  "decision_log_id": "V28-D045",
  "reviewed_by": "Codex Main; focused scope_planner input",
  "trigger": "G1_WARM_FAIL scoped execution closure",
  "evidence_level": "INSPECTED",
  "decisions": {
    "N01": {
      "disposition": "CONTINUE",
      "scope": "Bounded next-stage pilot proposal only",
      "experiment_execution": "DEFER",
      "reason": "The prior recovery pilot was UNRESOLVED: missing R1 endpoint and too few observed R2 grasp-loss events; this does not establish benefit or futility.",
      "next_actions": [
        "Define unplanned grasp-loss duration before crossing and distinguish normal release, non-exposure, loss, regrasp and recovered clean completion.",
        "Redesign disturbance timing/amplitude and event exposure; retain nominal/sham controls and the all-injected denominator.",
        "Decide new pilot endpoint and small budget before any multi-seed confirmation. Loss-event definition is distinct from changing optimization losses; any such change needs its own proposal."
      ],
      "entry_conditions": [
        "Explicit simulator asset/checkpoint and reachable interaction window.",
        "Owner-approved pilot scope and budget."
      ],
      "not_required": [
        "Old v27 RECOVERY_PILOT_PROMISING",
        "A final qualified Teacher"
      ],
      "sources": [
        "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/wave_b_recovery_decision.json",
        "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_wave_b_r_step1500_readout_20260907.md"
      ]
    },
    "N02": {
      "disposition": "CONTINUE",
      "scope": "Deployable sensor contract and identifiability proposal only",
      "experiment_execution": "DEFER",
      "reason": "Existing shadow estimation is limited offline evidence and excluded 51 short episodes; the load/friction domain remains unestablished.",
      "next_actions": [
        "Specify proprioception, action history and gripper qpos; verify availability of any effort proxy. Privileged mass/joints/6D hand-force are labels or oracle inputs, not assumed deployment inputs.",
        "Define control-relevant resistance, rebound, grasp confidence and opening-progress targets. Stratify the physical mass 80–160 / friction {0,2,5} domain by side and interaction exposure; retain short/failure episodes explicitly.",
        "Propose a limited-domain pilot with matched sensor budgets for recurrent DR/history latent/oracle, within-episode resistance changes and held-out parameter combinations."
      ],
      "entry_conditions": [
        "Named input sources and informative interaction windows.",
        "Owner-approved independent pilot scope and budget."
      ],
      "not_required": [
        "Perfect Teacher",
        "Final camera layout or CAD"
      ],
      "sources": [
        "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/a2_piper_base_v27_shadow_estimator_readout_20260907.md",
        "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v27/runtime_logs/v27_bilateral_hardening_20260905/wave_b_decision.json"
      ]
    }
  },
  "X05": "CLOSED_REVIEW_COMPLETED_METHODS_REMAIN_OPEN",
  "new_experiments_started": false,
  "interpretation_boundary": "G1 warm failure does not establish scratch failure, infeasible geometry, or method futility."
}
```

本次回收只确定后续立项去向，未启动新的方法实验。

## 证据与限制

G0 沿用既有准入证据；原 FAIL、D36/D37、旧 C3 时点不改写。X24 未建立随机分布校准；X25 的臂前伸耦合残余仍是后续分析线索。相机投影与采样间隙不构成光学、CAD 或硬件验收；无事件保持 null。塔架接触伴随学习失败只支持待区分解释。

[候选与完整评估 manifest](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/a2_piper_base_v28_teacher_candidate_manifest_20260914.json)；[执行状态](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/state.json)；[逐 milestone reducers](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/reducers)；[readouts](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v28/runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/readouts)。

训练、评估与 render 任务均已到终态；watcher/supervisor 与 writer 资源的最终释放由 Main 记录在 cleanup receipt。

收尾证据：[cleanup receipt](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/cleanup_receipt.json)；[本地commit receipt](runtime_logs/v28_camera_aware_rebaseline_20260909/execution_20260913/local_commit_receipt.json)。两个Wave A commit节点未触发，本次仅使用合法停止点closure的本地commit；不push。
