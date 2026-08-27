# DONE

- 2026-08-21 18:37 HKT - 完成 v26 memory route、execution ledger、GPU/process/
  worktree boundary、local IsaacLab root-state/quaternion contract检查，以及一次性
  `V26_REWARD_LINEAGE_REVIEW.md`。证据为 source/static；尚无 Isaac Sim 或训练 PASS。
- 2026-08-21 19:09 HKT - 完成 clean R0 reward/config、exact fixed side
  distribution、symmetric privileged one-hot、door-relative far reset 与双侧
  staged-reset telemetry 的真实训练路径实现。
- 2026-08-21 19:09 HKT - 完成 1-env LEFT/RIGHT 各 1 batch、64-env LR
  10 batches、4096-env LR 10 batches；四次通过运行均产生 checkpoint，4096
  runtime side count 为精确 2048/2048。
- 2026-08-21 19:15 HKT - 正式 R0 四格训练已在 GPU0–3 独立 tmux 启动；
  CUDA visibility 限定为 0–3，未占用独立 Student 所在 GPU4–7。
- 2026-08-21 21:01 HKT - 四格均写出 step250 checkpoint；side counts 精确，
  Stage2 occupancy 已成为主体，尚无 hinge/goal，训练按原 reward/budget 继续。
- 2026-08-22 23:33 HKT - 四格均自然完成 4000/4000、step4000 checkpoint、
  exit0；完成 2,176-episode Route A、256-episode holdout与 LEFT/RIGHT 各三视角
  render。无 natural goal，R1 gate 未通过。
- 2026-08-22 23:33 HKT - 完成 unified summaries、final analysis与 Teacher/
  Student handoff manifest；v26 以 `V26_SCRATCH_REWARD_OR_EXPLORATION_BLOCKED`
  / `V26_CONTINUATION_REQUIRED` 关闭，无 Teacher release，G7 binding 不变。
- 2026-08-23 01:19 HKT - 完成 v26 acquisition supplement 文档与 lineage
  correction：确认 formal saved config 实际为 `[0.55,0.60] m`，并将历史
  `0.70 m` stand-off、scratch `80/3`、mature-grasp 后 policy-only `800/25`、
  strict K5 close persistence 固化为同一 v26 增补任务。无 code/config/runtime/
  training 变更。
- 2026-08-25 02:07 HKT - 完成 supplement config、双侧真实 smoke、四格
  4096-env × 4000-batch scratch formal 与 17-checkpoint Route A。四格均
  natural exit0；`LR_S1_STEP3000` 以 LEFT `3/64`、RIGHT `2/64` Stage3
  通过 repeated bilateral natural-K5 gate，M7 未启用。
- 2026-08-25 02:07 HKT - 完成 actor-only/fresh-RMS policy-only loader 合同、
  64-env runtime proof，以及 `LR_S1_STEP3000` → `800/25` 的
  4096-env × 3000-batch continuation。formal natural exit0；七 checkpoint
  Route A 共 896 episodes，最佳 `CONT_STEP2000` 为 LEFT `64/64`、RIGHT
  `61/64` Stage3。
- 2026-08-25 02:07 HKT - 完成 Stage3 mechanical trace、final analysis、
  Teacher/Student manifest 与 memory closure。所有 supplement natural goal
  为 0，最终为 `V26_STAGE3_UNLATCH_EXPLORATION_BLOCKED` /
  `V26_CONTINUATION_REQUIRED`；R1 未准入、无 v26 Teacher、G7 binding 不变。
- 2026-08-25 10:54 HKT - 完成 pull-derived v26-2：C/A/R/W Wave1 均从
  `CONT_STEP2000` 以 policy-only + inherited actor RMS 完成 750 PASS；24/24
  natural Route A evaluations 每侧 exact64。W `STEP0750` 为 LEFT `32/64`、
  RIGHT `36/64` Stage3，Stage4 `0/64`，handle/hinge admission `0`，integrity
  `0`。Stage3 retention passed，但第二个 admission/creation gate failed；typed
  outcome 为 `HANDLE_CREATION_NOT_SUPPORTED`；R→W
  `WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH`。conditional relay 未运行；
  `W_STEP0750` render 为 Stage2/no goal；Teacher/Student handoff 不更新。
