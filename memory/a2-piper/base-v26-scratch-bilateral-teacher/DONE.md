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
- 2026-08-28 03:25 HKT - 完成v26-3 event-time creation实现、E1 current
  Stage2-close-gate evaluator selector、M0/M1 configs、orchestrator、matrix/source-lock/
  construction/mechanism/F reducers与focused test。natural exact1、staged snapshot、
  64-env common-cap PPO smoke及D0/E1/E2/D3全部真实runtime PASS；E1为
  `STAGE2_LIMIT_CYCLE_CAUSAL_CONFIRMATION`。
- 2026-08-28 03:25 HKT - 完成F10/F20/F40每侧exact16与selected replay。较高cap
  降低tracking error和estimated saturation但无durable creation，关闭为
  `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`；10/10成为正式共同配置，actual
  drive force与handle-axis moment保持`INCONCLUSIVE`。
- 2026-08-28 03:25 HKT - 完成M0_S0/M0_S1/M1_S0/M1_S1四格GPU0–3
  4096-env×750、四份PASS receipt、125/250/500/750 checkpoints与32组共2048个
  bilateral-natural first episodes。M1 RIGHT两seed creation为8/64、13/64，LEFT均0，
  integrity0，最终`MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`。P/W按前置分别
  `NOT_RUN / PUSH_LOAD_BEARING_SIGNAL_INCONCLUSIVE`与
  `NOT_RUN / WALL_REMOVAL_NOT_REACHED`；selected M1_S1_STEP0750 bilateral render
  retry1 PASS。所有goal为0，Teacher/Student manifest不更新，G7 binding保持不变。
- 2026-08-28 21:24 HKT - 完成v26-4 Wave K runtime：冻结Stage3匹配网格九对候选中
  LEFT `9/9` reachable，RIGHT `9/9` first reject，唯一首拒为`arm_j4` upper-limit
  overshoot（`0.003046–0.039405 rad`）；正式K outcome为
  `BILATERAL_ASYMMETRIC_AT_arm_j4`。
- 2026-08-28 21:24 HKT - 完成v26-4 C/M terminal routing：C ceiling为
  `BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE`且canonical identity `NOT_RUN`；
  M四格与metrics `NOT_RUN`。focused independent review PASS；Teacher/Student handoff与
  Student G7 binding不变。
- 2026-08-29 06:48 HKT - 完成v26-4 R2 K corrected geometry proof：FK mirror与冻结
  Stage3网格通过，K outcome为`BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET`，并将R1
  defective-target arm_j4结论保留为历史而不再作为当前事实。
- 2026-08-29 06:48 HKT - 完成R2 C/M：canonical identity CPU/static PASS、C1
  runtime smoke PASS；C0/C1×seed0/1四格formal training与32组bilateral-natural
  exact64 eval全部完成。按冻结§7 reducer，step750 C1 prereg bands未通过且seed1未达
  三指标strict improvement，终态为`CANONICALIZATION_NOT_SUPPORTED`。training
  orientation audit发现side-independent target offsets，作为v26-5输入；v2
  max-handle与v3 high-water的不同exposure semantics已区分。无hardware evidence，
  Teacher/Student handoff与G7 binding不变。
