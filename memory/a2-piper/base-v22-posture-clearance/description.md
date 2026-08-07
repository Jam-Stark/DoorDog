---
name: base-v22-posture-clearance
scope: A2+Piper base_v22 conditional posture / clearance strategy / hinge randomization / body-assist force routing round (plan revision 3)
status: active
last_updated: 2026-08-06 22:50 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v22-posture-clearance/description.md
  - memory/a2-piper/base-v22-posture-clearance/TODO.md
  - memory/a2-piper/base-v22-posture-clearance/DONE.md
read_when:
  - implementing or executing any base_v22 node (P0-A..P0-F, P0-POSTURE-BASELINE, pilot, formal waves)
  - resolving base_v22 admission artifacts, gate states, or GPU/tmux scheduling
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
- 科学基线 commit `89c6538ad274ab6d1256389e3f2b3ceefd68d98a`。

## Hard Boundaries

- 合法 physical GPU 只有 `0` 和 `1`。GPU2/3 已租给 pull-v0，GPU4-7 被其他 tenant 占用；`nvidia-smi` 空闲读数不构成 lease。
- Warm start 固定为 `logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal/B1/model_step_000500.pt`，sha256 `d2732c148dd3176abafbf3a5c9425d4a34c17b352e8362bbfb38c8ac960d8421`，`policy_only`。
- `theta_send=0.90`、`release_hinge=1.60`、ARM_V20 effort profile、12D action 全部冻结。
- pooled48 release goal `>=46/48` 不可 waive；低于该值只能走 `RESEARCH_CONTINUATION_BELOW_RELEASE_GOAL`。
- Posture gate 是 same-denominator warm-start-relative（command side），revision-2 的绝对阈值已撤销，不得重新引入。
- Hinge damping 在 v21-B closure commit 上**没有** randomization 通路；`rand_hinge_drive_damping` 需要新建（plan §5A）。
- Formal 配置在 `V22_HINGE_RANGE_FREEZE.json` 与 `V22_POSTURE_GATE_FREEZE.json` 出现之前不得 materialize/promote。

## Source Facts Verified On Host

- `door.py:508` 以硬编码 `hinge_drive.GetDampingAttr().Set(50.0)` 写入 hinge damping；spawn 时无 randomization 入口。
- `door.py:1116-1117` 只从 metadata 还原 `hingeDriveMaxForce` / `hingeDriveStiffness`，damping 未绑定。
- A2 high-level base command 布局为 `[x, y, yaw, pitch, roll]`（`a2_base.py:399`），achieved 侧 `self.rpy[:, 0:2]` 为 `(roll, pitch)`；两者索引顺序相反，是 P0-A 必须实测确认的项。
- Trace 字段 `root_roll`/`root_pitch` 来自 `rpy`，属于 achieved 角度，不是 command。

## Execution Layout

- Training：`logs_rl/a2_piper_full_stage_a2_base/base_v22/`
- Smoke：`logs_rl/a2_piper_full_stage_a2_base_smoke/base_v22/`
- Launcher：`logs_rl/launchers/base_v22/`
- Eval / artifacts：`logs_eval/base_v22/`，locks 在 `logs_eval/base_v22/locks/`
- Route A（Wave 1 完成）：`logs_eval/base_v22/postformal_20260806_route_a/`（20/20 ROW_PASS，evidence index + selection 在内）
- Render（§15.4，选中 G1:step1250）：`logs_eval/base_v22/render_20260806_g1_step1250/`（5 场景 48/48 主片 PASS + QA contact sheets 在 `qa/`）

## Current State（2026-08-06）

- Wave 1（G1/G2）训练与 Route A 已关闭；裁决选定 **G1:step1250** 为最接近 §23 理想行为的 checkpoint，render 已交付。
- 未关闭：P0-B/P0-F（posture_need precision 保持 report-only）、P0-E、§6.2 fixed-torque probe 重测、Wave 2 bucket 复现验证——Wave 2/3 未启动。
- Route B（pooled48/Dynamics80/holdout64）未执行；本轮不构成 release 决定。
