---
name: base-v22-posture-clearance
scope: A2+Piper base_v22 conditional posture / clearance strategy / hinge randomization / body-assist force routing round (plan revision 3)
status: completed_scientific_no_release
last_updated: 2026-08-08 18:39 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v22-posture-clearance/description.md
  - memory/a2-piper/base-v22-posture-clearance/TODO.md
  - memory/a2-piper/base-v22-posture-clearance/DONE.md
read_when:
  - implementing or executing any base_v22 node (P0-A..P0-F, P0-POSTURE-BASELINE, pilot, formal waves)
  - resolving base_v22 admission artifacts, gate states, selections, or release taxonomy
---

# base_v22 Posture / Clearance / Force Routing

## Purpose

本 entry 记录 `base_v22` 这一轮的 plan identity、admission chain、实现边界与执行进度。它不覆盖 v21-B 的科学终态（见 [base-v21b-ablation](../base-v21b-ablation/description.md)），也不拥有 log path 契约（见 [log-layout](../log-layout/description.md)）。

## Plan Identity

- Plan ID `base_v22_posture_clearance_force_routing_v3`，Execution ID `base_v22_execution_v3`。
- 权威 plan：`scriptsFORhuman/a2_piper_base_v22_posture_clearance_force_routing_plan_R3_20260805.md`。
- 权威 manifest：`scriptsFORhuman/v22/a2_piper_base_v22_experiment_manifest_R3_20260805.yaml`。
- Change log：`scriptsFORhuman/v22/a2_piper_base_v22_R3_change_log_20260805.md`。
- Revision 2 文档为 byte-unchanged 历史证据，不得修改。
- 科学基线为 v21-B closure candidate。

## Hard Boundaries

- GPU lease 是外部动态调度事实，不写入 durable memory；每次执行以用户当轮分配为准。
- Warm start 固定为 `logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal/B1/model_step_000500.pt`，`policy_only`。
- `theta_send=0.90`、`release_hinge=1.60`、ARM_V20 effort profile、12D action 全部冻结。
- pooled48 release goal `>=46/48` 不可 waive；低于该值只能走 `RESEARCH_CONTINUATION_BELOW_RELEASE_GOAL`。
- Posture gate 是 same-denominator warm-start-relative（command side），revision-2 的绝对阈值已撤销，不得重新引入。
- v21-B closure candidate 没有 hinge damping randomization；v22 已实现 `rand_hinge_drive_damping` 并由 P0-D 验证。
- Formal 配置在 `V22_HINGE_RANGE_FREEZE.json` 与 `V22_POSTURE_GATE_FREEZE.json` 出现之前不得 materialize/promote。

## Source Facts Verified On Host

- `door.py` 已通过统一 scalar resolver 写入 hinge damping/stiffness/max force，并支持 per-env range randomization；asset metadata 同步保存与还原 damping。
- `generate_door_assets.py` 已导出 per-asset damping；P0-D 证明请求值、runtime drive 属性与 selector telemetry 一致。
- A2 high-level base command 布局为 `[x, y, yaw, pitch, roll]`（`a2_base.py:399`），achieved 侧 `self.rpy[:, 0:2]` 为 `(roll, pitch)`；两者索引顺序相反，是 P0-A 必须实测确认的项。
- Trace 字段 `root_roll`/`root_pitch` 来自 `rpy`，属于 achieved 角度，不是 command。

## Execution Layout

- Training：`logs_rl/a2_piper_full_stage_a2_base/base_v22/`
- Smoke：`logs_rl/a2_piper_full_stage_a2_base_smoke/base_v22/`
- Launcher：`logs_rl/launchers/base_v22/`
- Eval / artifacts：`logs_eval/base_v22/`，locks 在 `logs_eval/base_v22/locks/`
- Route A Wave 1：`logs_eval/base_v22/postformal_20260806_route_a/`（G1/G2，20/20 ROW_PASS，选中 G1:step1250）。
- Route A Wave 2/3：`logs_eval/base_v22/postformal_20260808_route_a_wave23/`（G3-G6，40/40 ROW_PASS；选中 G4:step1750 与 G5:step0750）。
- Route B：`logs_eval/base_v22/route_b_20260806_g1_step1250/`、`route_b_20260808_g4_step1750/`、`route_b_20260808_g5_step0750/`。
- Render：对应三个 candidate 的 `render_*` roots；每个 5 场景 × 16 env × 3 相机，media gate 全 PASS，QA contact sheets 在各自 `qa/`。
- Final：`logs_eval/base_v22/V22_FINAL_ANALYSIS.json` 与 `V22_RENDER_ADJUDICATION.json`。

## Final State（2026-08-08）

- 六个 formal cell 全部自然完成；Route A 共 60/60 ROW_PASS，三波选中 G1:step1250、G4:step1750、G5:step0750。
- 三候选 pooled48 goal 分别 46/48、47/48、47/48，均通过不可 waive 的 goal 线；但 pooled clearance 分别 29/48、9/48、16/48，均低于 44/48。
- 三候选均完成 realized Dynamics48（E0/E1/E2）、holdout64 与 render；H3/H4 仍 unrealized，因此完整 Dynamics80 未完成。Route B 的 Dynamics 还暴露 unauthorized body contact 与 E2 clearance failure。
- P0-B 独立标签 precision 0.925 / recall 1.0，但整体 posture gate 继续 `REPORT_ONLY_INSUFFICIENT_DENOMINATOR`；render 中 ordinary posture 仍非 near-neutral。
- P0-E 证明 trunk/front-thigh 的安全接触路径可实现；Wave 3 high-damping render 的唯一 eligible FL_thigh assist 为 292.119 N，超过 180 N p95 profile，且 Route B E1 另有 unauthorized FL_calf contact。
- Bucket reproduction 证明 runtime registration 48/48 正确，但 H0 response class 混合，H1/H2 也有少量跨类；25/30 N·m 补充探针仍低于 resolution，未实现 H3/H4。
- §17 终态为 **NO_RELEASE**：`V22_RESEARCH_PASS_NO_RELEASE`、`V22_RANDOMIZATION_BOUNDARY_IDENTIFIED`、`V22_POSTURE_CONDITIONALLY_USEFUL_NO_RELEASE`、`V22_BODY_ASSIST_UNSAFE`、`V22_HOLD_OPEN_DOMINANT`。
