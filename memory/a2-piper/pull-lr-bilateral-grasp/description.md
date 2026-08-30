---
name: pull-lr-bilateral-grasp
scope: pull branch exact LEFT/RIGHT mirrored door assets and Stage0–2 bilateral handle acquisition
status: active
last_updated: 2026-08-30 07:18 HKT
read_when:
  - 修改 pull/push 共用 door handedness selector、privileged LR observation、Stage0–2 completion 或 bilateral reset/eval 时
  - 需要确认当前 pull bilateral grasp winner、训练 lineage、fixed-side metrics 或 render artifacts 时
source_of_truth:
  - scriptsFORhuman/pull_lr_grasp/PULL_LR_BILATERAL_GRASP_EXECUTION_REPORT.md
  - gr00t/rl/config/exp/wbmanip/door_open_a2_pull_lr_grasp_terminal_lstm.yaml
  - logs_eval/a2_piper_pull_lr_grasp/formal_h450_xseg_screen_evalseed0_summary.json
  - logs_eval/a2_piper_pull_lr_grasp/formal_h450_xseg_top2_confirm_evalseed1001_summary.json
related_entries:
  - ../pull-open-door-task/description.md
  - ../stage0-2-grasp-terminal/description.md
---

# Pull LR bilateral grasp

本 entry 记录 pull branch 从 right-only door asset distribution 转为 exact raw-asset `LEFT/RIGHT` mirrored distribution，并只训练/验证 Stage0–2 walk、pregrasp、sustained grasp 的实现与实验事实。

当前 winner：

`logs_rl/a2_piper_pull_lr_grasp/pull_lr_grasp_h450_xseg_resume_seed2/model_step_000250.pt`

两个 independent eval seeds、每个 raw side 各 64 个 natural-reset first episodes，合计 strict K5：LEFT `125/128`、RIGHT `125/128`。最终 LEFT/RIGHT render 均为真实 `goal=true / Stage2 complete`，每侧保存 main、handle-top、handle-side、world +X、world -X 五个 720p 视角。

边界：raw asset LEFT/RIGHT 在 yaw≈pi 的 robot body view 中视觉左右相反；本 checkpoint 不证明 Stage3–5 bilateral opening、through、push task、hardware 或 sim-to-real。
