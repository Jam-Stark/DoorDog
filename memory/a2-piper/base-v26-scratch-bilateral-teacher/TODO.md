# TODO

- v26-1 acquisition supplement 已关闭，无需重跑。
- 2026-08-25 10:54 HKT - v26-2 pull-derived 阶段已完成并按 typed stop 关闭：Wave1 C/A/R/W
  均 750 PASS；24/24 natural Route A evaluations 均为每侧 exact64。
- W 的 Stage3 retention 已通过（`STEP0750` LEFT `32/64`、RIGHT `36/64`），但
  第二个 admission/creation gate 未通过（Stage4 `0/64`，handle/hinge admission
  `0`，integrity `0`），因此
  conditional relay 不运行，状态保持 `v26_2_complete_not_admitted`。
- typed outcome 为 `HANDLE_CREATION_NOT_SUPPORTED`；R→W
  `WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH`；不改 actuator/physics、不启用
  forced-close、不降低 K5、不整体移植 pull event graph、不进入 R1。
- 选定 `W_STEP0750` render 仅达 Stage2、无 goal；Teacher/Student handoff 不更新。
