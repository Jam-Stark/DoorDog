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
