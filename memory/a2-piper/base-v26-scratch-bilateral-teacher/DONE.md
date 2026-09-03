# DONE

- 2026-09-04 00:01 HKT - 完成 v26-8 r2 prelaunch 合同实现：新 `_r2` roots/receipts/tmux，receipt command
  显式六项 proxy env，每次 Isaac launch 前对两个冻结资产执行 HTTP 200 `P0_ASSETS`，复用原 G0，并以
  旧 source lock 逐文件证明实验 core/config/test/train/eval/reducer 不变。child-process receipt 同时记录
  Isaac 与 wrapper 返回码；此条仅为 STATIC/prelaunch 证据，G1 r2 尚未执行。

- 2026-09-03 21:59 HKT - v26-8 G1 首次 K_S1 smoke 在 Isaac scene construction 阶段因远程
  `default_environment.usd` 无法打开而 `FAIL/1`；失败早于 trainer/policy load，没有 policy step、
  checkpoint、K trace 或 load receipt。按 Owner 硬规则未重跑或改 config，Wave 1 与 Wave 2 均未运行；
  终态 `V26_8_NOT_ADMITTED_G1_RUNTIME_ASSET_FAILURE`，closure 已落盘。

- 2026-09-03 21:47 HKT - 完成 v26-8 最小实现与 G0。新增 side-min natural Stage4 driver、同 episode
  start/max 配对、16 项 zero-pop 后 fail-fast 校验、clip 后 scale 日志和 JSONL trace；完成六格 config、
  tmux/receipt/eval/reducer 操作脚本及五类 CPU 单元门。正式 source lock 为 `STATIC_PASS`，冻结 source
  checkpoint SHA-256 均匹配，测试为 `6 passed`。G1/GPU、Wave 1 与 experiment outcome 尚未运行。

- 2026-08-31 20:05 HKT - 完成 v26-6 Wave A 夹爪能力 eval-only 单因素 A/B（预注册合同
  `scriptsFORhuman/v26_6/a2_piper_base_v26_6_waveA_gripper_capacity_plan_20260831.md`）。
  三格 supervisor 均 `PASS/0`，门参数向量 exact 匹配，control 复跑与冻结 artifact
  bit-exact，integrity `0`，typed route `GRIPPER_CAPACITY_CONFIRMED`。RIGHT
  `handle≥0.3` `16/64→48/64`，`drvF>1.6` 分层 `1/43→28/43`，下压合力 `16.8→33.0 N`。
  Stage4/goal 仍为 `0`，剩余阻塞转为 Stage2→3 收入悬崖与 `hinge<0.1` 的 unlatch 墙。

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
- 2026-09-02 16:23 HKT - 完成 v26-7 两条 durable runtime constraint 记录：
  `a2_v26_6_side_mirrored_handle_offset_enabled=true` 在 all-RIGHT eval 的 zero-LEFT
  clone 情况必须为合法 no-op；per-env `doorOpenLR` validation 与 LEFT writes 保持
  fail-fast。step1000 attempt1 的旧 global guard 在 env construction 阶段失败且未执行
  policy step；r3 确认 RIGHT authored offsets bit-identical，attempt2 12/12 与 determinism
  exact PASS，失败证据保留在
  `scriptsFORhuman/v26_7/runtime_logs/v26_7_bilateral_native_unlatch_20260902/failed_attempts/step1000_attempt1/`。
- 2026-09-02 20:33 HKT - v26-7 Q20 在 §6.2 早停后，训练 shell 的全程 checkpoint 后置检查因
  缺少后续 checkpoint 产生 receipt `FAIL/1`，与 reducer 已冻结的科学 endpoint 不冲突；已对未来
  cell 的后置检查做 endpoint-aware 窄修，历史 Q20 receipts 不回写。
- 2026-09-02 20:33 HKT - v26-7 step2000 的 observation：LEFT durable 成功与 `arm_j4=1.745` 限位
  驻留同现；成功 LEFT pooled limit share 为 `38.1163%`，各成功 cell 为 Q05_S1 `51.0748%`、
  Q20_S1 `24.0005%`、Q20_S2 `38.2513%`。三个 LEFT=0 cell（Q05_S0、Q05_S2、Q20_S0）的
  `arm_j4` max 分别为 `1.257779/0.468791/1.289852`，限位步均为 `0`；限位步仅 `17.3697%`
  落在 first-rise→first-max。该 observation/inference 仅支持“探索问题”分支，不宣称机械可达性
  结论，也不作 typed route 最终裁定。
  另确认 trusted `.hydra/runtime_config.yaml` 的 `!!python/object/apply:pathlib.PosixPath`
  必须由 repository-established `yaml.UnsafeLoader` 读取；`safe_load` 会抛
  `ConstructorError`，targeted existing-artifact `side_summary` 已 PASS。
- 2026-09-03 00:30 HKT - 完成 v26-7 step3000 goal anomaly appendix 的只读 qualification：
  Q05_S2 LEFT durable `60/64`、`arm_j4` p95=`1.314685`、限位驻留 `0.0110%`，证明
  durable 不以顶限位为必要条件；Q05_S0 LEFT durable `0/64`、p95=`1.142730`、限位驻留
  `0%`，支持探索/Stage2→3 收入结构分支而非机械撞限。Q05_S1 LEFT 的 unrouted
  `complete=62/64` 经静态与数据核查未发现 complete/Stage4→5 mirror defect，terminal
  hinge 未系统性更小；`95.253%` 限位步在 Stage4，最后限位距首次 `root_x>1.5` 至少
  `34` 步、距 terminal 至少 `84` 步，判为 `NO_THRESHOLD_EVIDENCE`，按 plan §8 不作
  goal 能力或路由证据。详见
  [goal anomaly appendix](../../../scriptsFORhuman/v26_7/a2_piper_base_v26_7_goal_anomaly_appendix_20260903.md)。
