---
name: base-v26-scratch-bilateral-teacher
scope: scratch-born bilateral A2+PiPER Teacher acquisition, far-start navigation, staged reset, and load consolidation
status: v26_8_complete_wave2_not_admitted
last_updated: 2026-09-04 23:17 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/base-v26-scratch-bilateral-teacher/description.md
  - memory/a2-piper/base-v26-scratch-bilateral-teacher/TODO.md
  - memory/a2-piper/base-v26-scratch-bilateral-teacher/DONE.md
  - scriptsFORhuman/v26/V26_REWARD_LINEAGE_REVIEW.md
  - scriptsFORhuman/v26/a2_piper_base_v26_execution_ledger_20260821.md
  - scriptsFORhuman/v26/a2_piper_base_v26_final_analysis_20260822.md
  - scriptsFORhuman/v26/a2_piper_base_v26_acquisition_supplement_20260823.md
  - scriptsFORhuman/v26/a2_piper_base_v26_teacher_handoff_manifest_20260822.json
  - scriptsFORhuman/v26_2/a2_piper_base_v26_2_unlatch_reward_plan_20260825.md
  - scriptsFORhuman/v26_2/a2_piper_base_v26_2_pull_derived_plan_20260825.md
  - scriptsFORhuman/v26_2/a2_piper_base_v26_2_handoff_prompt_20260825.md
  - scriptsFORhuman/v26_3/a2_piper_base_v26_3_event_time_creation_plan_20260827.md
  - scriptsFORhuman/v26_3/a2_piper_base_v26_3_handoff_prompt_20260827.md
  - scriptsFORhuman/v26_3/a2_piper_base_v26_3_execution_closure_20260827.md
  - scriptsFORhuman/v26_4/a2_piper_base_v26_4_bilateral_grasp_foundation_plan_20260828.md
  - scriptsFORhuman/v26_4/a2_piper_base_v26_4_execution_closure_20260828.md
  - scriptsFORhuman/v26_4/a2_piper_base_v26_4_r2_execution_closure_20260829.md
  - scriptsFORhuman/v26_6/a2_piper_base_v26_6_waveA_gripper_capacity_plan_20260831.md
  - scriptsFORhuman/v26_7/a2_piper_base_v26_7_bilateral_native_unlatch_plan_20260902.md
  - scriptsFORhuman/v26_8/a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md
read_when:
  - implementing, training, evaluating, or resuming base_v26
  - selecting the scratch bilateral Teacher or load-robust continuation
---

# base_v26 Scratch Bilateral Teacher

## Purpose

本 entry 路由 v26：高层 Teacher 从随机初始化出生，LEFT/RIGHT 从 batch 0
共同训练；保留 frozen A2_Base low-level policy、FULL posture、active planar base、
strict Stage2 grasp 与 current release/handoff。R0 成功后才进入 moderate load
consolidation。

## Authority and current state

- Canonical plan: `scriptsFORhuman/v26/a2_piper_base_v26_execution_plan_R1_20260821.md`。
- Execution ledger: `scriptsFORhuman/v26/a2_piper_base_v26_execution_ledger_20260821.md`。
- Reward lineage: `scriptsFORhuman/v26/V26_REWARD_LINEAGE_REVIEW.md`。
- Final analysis: `scriptsFORhuman/v26/a2_piper_base_v26_final_analysis_20260822.md`。
- Acquisition supplement: `scriptsFORhuman/v26/a2_piper_base_v26_acquisition_supplement_20260823.md`。
- v26-2 pull-derived unlock plan:
  `scriptsFORhuman/v26_2/a2_piper_base_v26_2_pull_derived_plan_20260825.md`。
- v26-3 event-time creation plan:
  `scriptsFORhuman/v26_3/a2_piper_base_v26_3_event_time_creation_plan_20260827.md`。
- Superseded v26-2 raw-removal-only plan:
  `scriptsFORhuman/v26_2/a2_piper_base_v26_2_unlatch_reward_plan_20260825.md`。
- Teacher handoff: `scriptsFORhuman/v26/a2_piper_base_v26_teacher_handoff_manifest_20260822.json`。
- 2026-08-21 18:37 HKT - 已完成 required memory/source 回溯与真实 runtime
  binding。GPU0–3 空闲；GPU4–7 的独立 Student 不属于 v26。
- 2026-08-21 19:09 HKT - 1-env LEFT/RIGHT、64-env LR 10-batch smoke 与
  4096-env LR 10-batch short-learning gate 均已完成真实 Isaac Sim rollout、
  optimizer update 与 checkpoint save。4096 runtime 固定为 2048/2048，约
  12.9k steps/s；R0 formal matrix 已准入。
- 2026-08-21 19:15 HKT - 四格 4096-env / 4000-batch R0 matrix 已在独立
  tmux 启动并分别绑定 GPU0–3；launcher 将 CUDA visibility 限定为 0–3，
  GPU4–7 只保留独立 Student PID。
- 2026-08-21 21:01 HKT - 四格均写出 step250 checkpoint，exact side count
  未漂移；各格 Stage2 occupancy 约 66–73%，LR seed1 RIGHT 有 Stage3
  high-water，hinge/goal 仍为 0。按 scratch long-horizon contract 继续至后续
  milestones，不改 reward。
- 2026-08-22 23:33 HKT - 四格均完成 4000 batches/exit0；Route A 2,176
  episodes、holdout 256 episodes与双侧三视角 render 全部完成。formal staged
  reset 中 LR S1 左右 Stage3 occupancy 约 29%，但 natural-start holdout LEFT
  0/128 到 Stage3、RIGHT 仅 1/128 到 Stage3，双侧 goal 均 0。阻塞定位为
  natural Stage2 strict-grasp→Stage3/unlatch transition，而非 far-start 或单纯
  bilateral interference。R1 未准入；无 v26 Teacher，Student G7 binding 不变。
- 2026-08-23 01:19 HKT - Owner 将历史 stand-off acquisition 路线裁决为 v26
  增补任务，不创建新 phase。文档固定 `0.70 m` 窄 staging anchor、scratch
  `80/3` + velocity iterations 1、strict control-step K5；双侧 natural repeated
  grasp 后才 policy-only 切 `800/25` + velocity iterations 2。当时尚未实施。
- 2026-08-25 02:07 HKT - acquisition supplement 已完整执行：四格 scratch
  4000/4000 与 2,176-episode Route A 恢复 repeated bilateral natural K5；
  `LR_S1_STEP3000` LEFT `3/64`、RIGHT `2/64` 到 Stage3。其 policy-only
  `800/25` continuation 完成 3000/3000；896-episode Route A 的
  `CONT_STEP2000` 达 LEFT `64/64`、RIGHT `61/64` Stage3，但所有 goal
  为 0。最终边界为 Stage3 unlatch exploration，R1/Teacher/Student 均未准入。
- 2026-08-25 03:20 HKT - Owner 将已完成 supplement 正式命名为 `v26-1`，并
  要求规划 `v26-2` Stage3 unlatch reward 实验。实际日志表明 1000 是重要判读点
  但不是通用终点：v13_A 到约 2000 才出现 Stage4，v13.1 在 500–1000 已快速
  收敛，v26-1 natural bilateral Stage3 到 2000 才稳定出现且后续非单调。v26-2
  因此规划 C0 raw-handle6 与 T0 raw-handle0 的 matched two-cell、每格最多
  2000/save250；formal training 只需 GPU0–1，尚未实现或运行。
- 2026-08-25 03:37 HKT - Owner 提供同机 pull-v1/v2/v4 完整证据，03:20 的
  raw-removal-only 计划已 supersede。实际 pull 并非 random actor scratch，而是从
  base-v20→pull-v0→v1-R→v2-W 的 policy-only warm lineage；`pull_door_handle=6`
  在 v1-R 创建稳定 handle depression，随后 `near_closed 0.1→0.25` 在 v2-W
  拆除 reward wall并形成真实 Stage4。pull handle reward 还受 tensile/load-bearing
  mask，不能与当前 ungated `push_door_handle` 等同。新 v26-2 从
  `CONT_STEP2000` 设计 C/A/R/W 四格：A→R 隔离 K5-gated depression scale6，
  R→W 隔离 threshold0.25；Wave1 GPU0–3 各750，conditional W relay双seed各750，
  最长 lineage1500，尚未实现或运行。
- 当前机器无 GPU-backed X display；interactive GUI preview 不可用。已用真实
  headless runtime 的 asset metadata、root pose、rollout 与训练日志完成对应
  几何/初始化证明，不把该边界写成 GUI PASS。
- 2026-08-27 19:26 HKT - Owner 接受本地对 Cloud Pro 全量审阅的消化结果并批准
  落成 v26-3 完整阶段；另批准后续 Worker 自主使用 GPU0–3 完成实现、test、
  diagnostic、四格训练、全checkpoint bilateral-natural eval、条件分支、render与
  closure。主矩阵是两seed matched `old velocity credit` vs `monotone high-water
  creation credit`；wall只在creation与旧0.1 cliff真实暴露后运行，effort/
  push-axis-work按本地证据条件执行。当前仅plan/handoff落盘，implementation与
  Isaac/GPU execution均为 `NOT_RUN`。
- 2026-08-28 03:25 HKT - v26-3已完整执行并关闭。construction、D/E/F、四格
  4096-env×750、32组all-checkpoint LEFT/RIGHT exact64 natural eval与selected
  render均落盘。M1_S0/S1在RIGHT产生`8/64`、`13/64` durable creation，LEFT均
  `0/64`；所有Stage4/goal为0，integrity为0，main typed outcome为
  `MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`。F为
  `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`；P/W分别
  `NOT_RUN / PUSH_LOAD_BEARING_SIGNAL_INCONCLUSIVE`与
  `NOT_RUN / WALL_REMOVAL_NOT_REACHED`。Teacher holdout未准入，manifest与G7
  binding保持不变，阶段状态为`v26_3_complete_not_admitted`。

- 2026-09-03 20:48 HKT - v26-7 已由 Owner 验收关闭（Q20 endpoint step2000、Q05 endpoint step3000，scoped
  bilateral unlatch 目标通过；Stage4/5/complete 仅报告）。Owner 裁定进入 v26-8，不结算 v26。v26-8 plan
  已冻结但未实现：`scriptsFORhuman/v26_8/a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md`。
  两问：Q_A bilateral Stage3→4 opening/hold（W 轴 `near_closed 0.1→0.25`，对齐 Stage4 入场线 0.25，消除
  hinge∈[0.1,0.25) 的收入谷）；Q_K scaffold-decay curriculum（改造 `reward_penalty_curriculum`：侧感知、
  natural-start、min-side Stage≥4 到达率 driver 0.5/0.7、floor 0.2、16 项 Stage0–3 脚手架名单）。
  Wave 1 六格 warm-start（`policy_only` + inherited actor RMS）自 Q05_S1/Q05_S2 step3000（SHA 已冻结），
  C/W/K × {S1,S2} 配对，3000 batches，GPU2–7 训练、GPU0–1 评估；Wave 2 条件分支 B1 scratch 可靠性、
  B2 KW 组合。已核实：v26-7 训练内 `average_goal_reached` 最大 0.26，原版 goal-rate curriculum 全程惰性；
  pooled `average_stage_reached` 受 staged reset 与双侧混合抬高（Q05_S0 LEFT 停 Stage2 仍 3.42）。
- 2026-09-03 21:47 HKT - v26-8 已完成最小实现与 G0：20 个 source/config/script/test 文件写入
  source lock，两个冻结 source checkpoint SHA-256 均匹配；六格 compose、16 项非零名单与 eval
  curriculum-off 合同为 `STATIC_PASS`，五类 CPU 单元门共 `6 passed`。正式 review 发现并在 G0 前修正
  K 继承 goal-rate driver、G1 日志、milestone trace 前缀、reducer 字段和 receipt finalization 问题。
  当前证据仅为 `STATIC_PASS/TEST_PASS`；G1 与 Wave 1 尚未运行。
- 2026-09-03 21:59 HKT - v26-8 G1 首次 `K_S1` 64-env/5-batch smoke 在 policy load 前的
  Isaac scene construction 非零退出：远程 `default_environment.usd` 无法打开，supervisor receipt
  为 `FAIL/1`。按冻结 plan 与 Owner 的 K fail-fast 硬规则未重跑、未修改 config/阈值，也未启动 Wave 1。
  Q_A/Q_K、六个 milestone 与 Wave 2 全部为 `NOT_RUN`；阶段终态
  `V26_8_NOT_ADMITTED_G1_RUNTIME_ASSET_FAILURE`。closure：
  `scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260903.md`。
- 2026-09-04 00:01 HKT - Owner 已按 plan §13 授权一次 G1 r2 relaunch，并授权 G1 PASS 后直接
  进入 Wave 1；实验 config、K code、判据、源 checkpoint 均保持不变。r2 使用独立 `_r2` train/eval/
  runtime/receipt/tmux root，每次 launch 前在与 receipt command 相同的六项显式 proxy env 下执行
  `P0_ASSETS`。旧 G0 被直接复用，旧失败 G1 与 receipt 原样保留；逐文件 r2 contract verifier 只允许
  plan §13、orchestrator 与 child-process receipt wrapper 变化，并同时记录 Isaac 子进程与 wrapper 返回码。
  当前处于 P0/G1 r2 prelaunch，尚无新的 GPU/runtime 结果。
- 2026-09-04 00:14 HKT - G1 r2 在 P0、scene construction、strict policy load 与 5 batches 均成功后，
  于 K wiring reducer fail-fast：35 行 trace 中 LEFT/RIGHT 分别有 12/22 行 natural sample，但没有任何
  同一次 update 两侧同时非零，故 35/35 skipped、scale 始终 1.0，未满足 §6.2。外层 receipt `FAIL/1`；
  该失败已执行 policy step，不是可重试 infra。Wave 1/全部 milestone/endpoint/Wave 2 均 `NOT_RUN`，
  终态 `V26_8_NOT_ADMITTED_G1_R2_K_NATURAL_PAIRING_GATE_FAILURE`；不得在本协议下再次 relaunch。
  closure：`scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260904.md`。
- 2026-09-04 00:27 HKT - Owner 授权 plan §14 amendment 与 G1 r3，只修改跨侧 episode 聚合/消费语义。
  r3 保留 same-episode start/max snapshot，新增按侧 pending natural denominator/numerator；缺侧 update
  保留窗口，双侧均非空后才按原 0.5/0.7 driver 决策并原子消费。六格 config、reward/stage、阈值/scale、
  source checkpoint、trainer 与 reducer 判据不变。r3 使用全新 `_r3` source lock/G0/G1/Wave1 roots；
  G1 PASS 后仍直接进入 Wave 1。
- 2026-09-04 01:11 HKT - r3 窄修已通过独立 IsaacLab semantic review、7 项 CPU test 与正式门：
  `R3_CONTRACT_PASS`、`STATIC_PASS`、`G0_PASS`。r3 verifier 以 r2 lock 为 baseline，19 个 locked 文件
  byte-identical，仅 core pending 语义、对应 test、plan §14 与 `_r3` orchestrator 四项差分。当前进入
  P0_ASSETS/GPU0 G1 r3；source 已冻结，不再修改。
- 2026-09-04 01:20 HKT - G1 r3 证明 pending 聚合/消费已生效：35 行中 10 次 bilateral consume，
  首次为 update2。update31 双侧均 `1/1` 到 Stage4，原 0.7 driver 正确把 scale 从 1.0 衰减到
  `0.9998999834060669`，但旧 G1 门要求 5-batch 内 scale 全为 1.0，故 reducer `FAIL/1`。该失败在
  policy load/step 后且不属于 infra；未启动 Wave 1/2，未放宽门或重跑。终态
  `V26_8_NOT_ADMITTED_G1_R3_SCALE_ASSERTION_AFTER_VALID_CONSUMPTION`；closure：
  `scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260904_r3.md`。
- 2026-09-04 01:31 HKT - Owner 授权自主合理修复后，plan §15 将旧 G1“scale 必须全 1.0”替换为逐行
  exact torch-float32 transition verifier；对 immutable r3 artifact 的 CPU-only readjudication 为
  `PASS/0 + G1_READJUDICATION_PASS`，旧 r3 `FAIL/1`、failure JSON 与缺失的 `g1_wiring.json` 均原样保留。
  r3a delta/source/G0 为 PASS，现按 gate 直接启动新 `_r3a` Wave 1 六格。
- 2026-09-04 01:47 HKT - `_r3a` Wave 1 六格已在 GPU2–7 独立 tmux/receipt 启动，六次 P0 HTTP200、
  strict policy-only + actor RMS load、resolved config、source checkpoint/hash/lock 与 receipt provenance
  全部 PASS；当前约 batch13–16，无非零退出。K_S1 scale 已到 `0.945906`（ENGAGED 前兆），K_S2 仍
  `1.0`，符合预期方向但不提前作 milestone 路由；等待六格 step500 后做 12-lane exact64。
- 2026-09-04 05:54 HKT - `_r3a` step500 完成：12×exact64、integrity=0、两条 eval receipt PASS/0，
  reducer `V26_8_MILESTONE_REPORTED`，无停格，endpoint outcomes 仍 null。C_S1 RIGHT D 从源64降至43，
  为 `WARM_START_TRANSIENT`；C_S2 retained。S2 LEFT S4+ 的 C/W/K 为47/64/64（源0），但 RIGHT S5+
  从源21降至1/14/2；S1 LEFT complete 为64/63/62，仅记录。K_S1/K_S2 均衰至0.2，K_S2 惰性预期
  被实际轨迹推翻，但其 LEFT S4+=64，未触发 driver mismatch。eval-only 修复显式 driver=null，与
  curriculum=false 一起在12份 runtime config 验证，未改训练/plan binding。完整计数、同源差、历史反向
  读数与 consumed-only 双侧 driver 轨迹见 `scriptsFORhuman/v26_8/a2_piper_base_v26_8_step500_readout_20260904.md`。
  六格仍运行，下一门为 step1000，不作中途阈值/config 修改。
- 2026-09-04 09:21 HKT - `_r3a` step1000 完成：12×exact64、integrity=0、eval PASS/0，无停格。
  C_S1 warm-start从transient恢复retained。W_S2 LEFT/RIGHT S5+=60/63、complete=59/63，但C_S2已
  自行entry，不能把downstream正读数替换W的entry判据；K_S1 RIGHT D相对C为−9，K_S2 LEFT
  S5+/complete相对C为−39/−37，负向结果保留。K两格在600–1000的100-batch边界均为0.2，
  bilateral driver约0.992–0.999，无mismatch；endpoint仍未裁定。详见
  `scriptsFORhuman/v26_8/a2_piper_base_v26_8_step1000_readout_20260904.md`；下一门step1500。
- 2026-09-04 12:45 HKT - `_r3a` step1500完成：12×exact64、integrity=0、eval PASS/0，无停格。
  C_S2 RIGHT S5+/complete从step1000的4/0升到63/63，W_S2为64/64；K_S2 LEFT仅5/1，相对C
  为−52/−55，RIGHT D相对C为−24（相对历史源−19），即便该侧S5+/complete=64/64也保留负读数。
  W_S1 min-side S5+相对C−8，触及附加downstream-harm数值线但不提前裁定。K两格1100–1500
  边界scale约0.2，双侧driver约0.992–0.999，无mismatch；endpoint仍待3000。计数、同源差、
  历史/上轮差、driver及PID/GPU快照见 `scriptsFORhuman/v26_8/a2_piper_base_v26_8_step1500_readout_20260904.md`。
  六格继续原预算，下一门step2000。
- 2026-09-04 16:11 HKT - `_r3a` step2000完成：12×exact64、integrity=0、eval PASS/0，无停格。
  K_S2 LEFT S4+/open_hold=62/62但S5+/complete=0/0，相对C为−63/−63；K_S1 min-side S5+
  相对C+18，同时RIGHT D−11；W_S1 LEFT D−10、K_S2 RIGHT D−16。正下游计数不取消冻结D guard，
  也不提前裁定endpoint。K两格1600–2000边界scale约0.2，双侧driver约0.994–0.998，无mismatch。
  逐侧计数、同源差、历史/上轮全部差与QA进程快照见
  `scriptsFORhuman/v26_8/a2_piper_base_v26_8_step2000_readout_20260904.md`；下一门step2500，原预算不变。
- 2026-09-04 19:36 HKT - `_r3a` step2500完成：12×exact64、integrity=0、eval PASS/0，无停格。
  K_S2 LEFT S5+/complete从0/0恢复到63/63，但双侧D相对C均−26；W_S2双侧full-chain计数64，
  同时LEFT D相对C−18；W_S1 LEFT D−9。K_S1 min-side S5+相对C+18，正负读数并存，不改D guard。
  K两格2100–2500边界scale约0.2、无mismatch。完整历史反向差、driver与进程快照见
  `scriptsFORhuman/v26_8/a2_piper_base_v26_8_step2500_readout_20260904.md`；下一步3000 endpoint，
  typed outcomes和Wave2仍未裁定，六格继续原预算。
- 2026-09-04 23:17 HKT - v26-8执行结束：六格3000/3000自然exit0，6个milestone/72个lane/4608
  episodes均exact64、integrity=0，18份Wave1 run receipts均PASS/0，无停格/重跑。endpoint为
  `W_NOT_DIFFERENT`、`K_REGRESSED`，C为`C_ENTRY_EMERGED/C_CONSOLIDATED`；独立数值核对PASS。
  K_S1 min-side S5+相对C+8、RIGHT complete+17，但K_S1/K_S2 RIGHT D分别−16/−9，违反NO_REGRESS。
  W_S1下游+11/+17仍是正读数，C_S2已自行entry，故W不获额外entry支持。K两格已engaged，无driver
  mismatch/invalid或oscillating；末段K_S2 driver下降仍记录。按§9 B1/B2均NOT_RUN，不追加预算。
  最终来源核对28个锁定文件通过，仅保留eval前登记的driver-null补充；原r2/r3 FAIL/1及r3 CPU重裁
  PASS均保留。23:10 HKT训练/eval/background writer、v26-8 tmux与open leases均为0，GPU0–7空闲。
  closure：`scriptsFORhuman/v26_8/a2_piper_base_v26_8_execution_closure_20260904_wave1_r3a.md`。
  Teacher/Student/G7/hardware不变；已授权两次commit为e3d496b/aa8a05f，r3/r3a及执行文档待新commit授权，不push。

## Frozen acquisition decisions

- `checkpoint=null`, `checkpoint_load_mode=full`, `auto_load_latest=false`。
- bilateral process 精确 half LEFT / half RIGHT，按 seed 对 env_id 做一次固定
  permutation；snapshot 保持 per-env，因此不会跨 side。
- natural start 使用 door-relative normal `0.90–1.40m`、lateral `±0.25m`、
  yaw `±0.30rad`；Stage0 timer 350 control steps。
- handedness privileged observation 两槽为 LEFT `[1,0]`、RIGHT `[0,1]`；
  observation dimension 不变，Student 不增加 privileged side label。
- R0 friction off、handle height `0.85–0.95m`、door mass `80–120kg`；
  R1 load mixture 只有在 bilateral repeated goal 后才准入。

## Validation boundary

Static/config/runtime/training evidence必须按实际层级记录。v25 的 G7 或 matched
causality evidence不能替代 v26 scratch acquisition 结果。

## Durable runtime findings

- 2026-09-03 22:33 HKT - **长寿 tmux server 会把陈旧 proxy 环境传给所有 supervisor 启动的 Isaac 进程。**
  tmux server（2026-07-31 启动）全局 env 固定 `http(s)_proxy=127.0.0.1:18888`，而当前代理只在 `18889` 监听；
  `run_supervisor.py` 的 `tmux new-session -d` 不显式传 env，因此 v26-8 G1 的 Isaac 进程对
  `omniverse-content-production.s3` 的全部拉取失败，`spawn_ground_plane` 抛 `FileNotFoundError`
  （`default_environment.usd`）。新建 tmux session 内 `curl` 复现退出码 7，当前 shell 与直连均 200。
  之后任何 tmux 长跑必须在 receipt command 中显式写入 proxy 环境，并在启动 Isaac 前做资产 preflight。
  另注意：Isaac 进程在场景构造异常后以 0 退出，wrapper 必须用"strict policy-load 成功行"判定。
- 新 door selector 不仅要实现于 task scenario module，还必须在
  `gr00t/rl/simulator/isaacsim/isaacsim.py::_get_task_obj_cfg_dict_for_door_eval`
  注册入口；否则会落回旧随机 `TaskObjCfgDict`。v26 runtime count check 会在
  optimizer 前明确失败。
- Trainer 的 episode metric accumulator 要求浮点张量；内部 exact count 保留
  `torch.long`，只在写入 `log_dict` 时转 float。
- 4096 个确定性 door variants 首次 scene creation 约 439 秒；后续每个 PPO
  update 约 20.3 秒。正式 4000-batch run 必须独立 tmux 长跑。
- 多个 IsaacSim 单卡进程若取消 `CUDA_VISIBLE_DEVICES`，会在所有可见 GPU
  建立辅助 context；与独立任务共享机器时，应将 visibility 限定到获批 GPU
  集合，再用 `ACCELERATE_TORCH_DEVICE` 选择集合内的单卡。
- 正式日志由 `scriptsFORhuman/v26/summarize_v26_r0_progress.py` 按精确
  iteration 抽取，累计输出为 `logs_eval/base_v26/r0_progress.json`；不要用
  latest table 冒充已冻结 milestone。
- Staged-reset Stage3 occupancy 不能替代 natural-start complete-chain evidence；
  v26 的 LR S1 在后段 reset 状态可占据 Stage3，但 Route A/holdout 几乎不能
  从 natural Stage2 进入 Stage3。
- USDRT headless render 要求进程内 device ordinal 为 `cuda:0`。使用非零物理
  GPU 时，将该物理卡设为唯一 `CUDA_VISIBLE_DEVICES`，并将
  `ACCELERATE_TORCH_DEVICE` 设为 `cuda:0`。
- v26 plan 虽写明 Stage0 staging target 约 `0.70 m`，正式 common config 未显式
  覆盖，saved config 实际继承 `[0.55,0.60] m`；LR S1 holdout Stage0→1
  standoff p50 约 `0.591 m`。后续不能把计划文字当成 runtime binding。
- v13.1 的 `800/25` + velocity iterations 2 是 v12_C mature grasp actor
  policy-only warm-start 后的 retention/full-chain 能力，不是 batch-0 scratch
  discovery 的历史正证据。
- 原 `policy_only` loader 会把 actor observation RMS 作为 policy submodule
  一起加载。v26 supplement 新增显式 `policy_only_load_actor_rms: false`；
  strict-load actor MLP/std/LSTM，同时保持 actor RMS、critic、optimizer、
  scheduler、trainer state、environment 与 staged-reset buffers fresh。
- `CONT_STEP2000` natural trace 已证明 close persistence 不是剩余阻塞：
  Stage3 bilateral contact 为 1.0，contact stability 为 `0.9689/0.9666`，
  但 handle-joint max 仅 `0.0001305/0.036833 rad`，hinge max 仅
  `0.002131/0.002110 rad`，全部 Stage3 episode overtime。
- Pull-v1/v2 的 durable transfer boundary：`pull_door_handle=6` 相对 no-handle
  control 创建稳定 depression，`near_closed 0.1→0.25` 再创建 Stage4；但其 actor
  是 policy-only warm lineage，gripper为45N/1300/32，且 handle/hinge reward受
  pull-only load-bearing mask。v26-2 只能移植 creation/wall-removal 原理，不能声称
  current raw push term 或 random scratch 已由 pull 证明。
- v26-2 first causal ladder从同一 `CONT_STEP2000`、相同 policy-only + actor-RMS
  contract 启动：A→R 只切 K5-gated handle-depression `0→6`，R→W 只切
  `near_closed 0.1→0.25`。Wave1 750、conditional relay 750；checkpoint selection
  只依据 bilateral natural evidence。
- 2026-08-25 10:54 HKT - v26-2 pull-derived Wave1 C/A/R/W 均以
  `CONT_STEP2000` policy-only + inherited actor RMS 完成 750 iterations、exit0。
  四格共 24/24 个 natural Route A evaluation（每 checkpoint 每侧 exact 64）均
  完成；W `STEP0750` 为 LEFT `32/64`、RIGHT `36/64` Stage3，Stage4 为
  `0/64`、两侧 `handle>=0.6 & hinge>=0.1` 均为 0，integrity counters 为 0。
  因而 Stage3 retention passed，但第二个 admission/creation gate failed，整体
  typed outcome 为 `HANDLE_CREATION_NOT_SUPPORTED`；R→W 为
  `WALL_REMOVAL_NOT_SUPPORTED_IN_PUSH`。conditional relay 未运行；选定的
  `W_STEP0750` bilateral render 仅达 Stage2、无 goal。Teacher/Student handoff
  不更新，当前状态为 `v26_2_complete_not_admitted`。
- 2026-08-27 本地复核对v26-2机制标签作了更精确的解释：W750已有LEFT/RIGHT
  `32/64`、`36/64` Stage3与大量K5/contact、旧depression income，但handle
  high-water仍为noise-scale，因此是
  `HANDLE_VELOCITY_CREDIT_WITHOUT_STATE_CREATION`；R/W从未访问hinge0.1，故wall
  结论应解释为 `WALL_REMOVAL_NOT_REACHED`，不是wall已被push反证。原始artifact
  与2026-08-25 closure不改写。
- 当前A2 eval实际应用 deterministic `policy_model.action_mean`，不是sampled action；
  selected Stage2 gripper sign cycle应归于deterministic actor/LSTM/closed-loop与binary
  full-open/full-close mapping，不能归因于sampling。
- 当前reward registry会把非零scale乘control dt。v26-3 monotone creation raw必须用
  `delta_highwater/(handle_norm*control_dt)`；high-water state还必须进入natural reset
  和staged snapshot store/load，避免reset/restore伪creation。
- 当前hold-detail telemetry可提供contact position/force、joint target/state、gain/
  effort limit和computed/applied effort estimate；actual implicit-drive force仍不可读。
  后续capacity结论不得把estimate写成actual torque，pull45N也不自动迁移。
- v26-3 event-time state必须在completed physics step后、reward与stage advance前只更新
  一次；natural reset从实际written handle初始化，staged restore保留prev/high-water并
  清除one-step cache。这样既能记录control-interval monotone creation，又不会把
  snapshot restore支付成pseudo-creation。
- v26-3 E1证明Stage2 close-gate的deterministic mean gripper cycle对后续K5有因果影响：
  两侧forced-close恢复大量Stage3∧K5，结果为
  `STAGE2_LIMIT_CYCLE_CAUSAL_CONFIRMATION`；但Stage3/4 generic forced-close没有创建
  durable handle state，不能把E1诊断override当作natural policy能力。
- v26-3 main首次在同一bilateral lineage看到两条seed一致的RIGHT durable creation，
  但LEFT仍为0；selected M1_S1 render同样是LEFT high-water `0.000208 rad`、RIGHT
  `0.597800 rad`。因此monotone credit清除了velocity farming并可在单侧创建state，
  但尚未形成seed×side稳定机制，不能进入wall wave或Teacher。
- v26-3 bounded F中20/40 Nm显著降低gripper target error/estimated saturation，却未让
  任一侧形成durable creation，故common cap保持10/10。actual implicit-drive force与
  canonical handle-axis moment仍不可读，P必须保持signal-inconclusive而非制造物理claim。
- 2026-08-28 21:24 HKT - v26-4在预注册Wave K分支上关闭为
  `v26_4_complete_requires_asymmetric_posture`。K admitted：冻结Stage3匹配网格
  LEFT `9/9` reachable、RIGHT `9/9` first reject，唯一首拒为`arm_j4` upper-limit
  overshoot（`0.003046–0.039405 rad`）；C ceiling为
  `BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE`，
  canonical identity为`NOT_RUN`；M四格与全部metrics为`NOT_RUN`。Teacher与Student
  handoff/G7 binding不变，focused review为PASS。未来仅可另开plan做non-mirror posture
  discovery，不能由本entry预授权。
- 2026-08-29 06:48 HKT - v26-4 R2已完成。修正后的geometry-derived target通过FK mirror
  与冻结Stage3网格，K outcome为`BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET`，supersede
  R1同世界orientation/arm_j4 defective-target结论（R1 artifacts与closure保留历史）。
  C canonical identity为CPU/static PASS，C1 runtime smoke PASS；C0/C1×seed0/1四格
  formal training与32组bilateral-natural exact64 eval全部完成。R2 reducer按预注册
  §7判为`CANONICALIZATION_NOT_SUPPORTED`：step750 C1未通过preregistered bands，且
  seed1未达三指标strict improvement。active training orientation audit发现
  frame-transformer target offsets仍side-independent，列为v26-5输入；无hardware证据。
  v2 max-handle与v3 high-water保留各自不同exposure semantics，不作错误的一致性断言。
- 2026-08-31 20:05 HKT - **v26 全程的 unlatch 阻塞已定位为夹爪执行能力回退，不是
  reward/observation/geometry 问题。** v26 从 scratch 起家时没有覆盖
  `robot.dof_effort_limit_list`，直接继承 `A2_Piper/a2_piper.yaml` 的 arm_j7/j8
  `10/10 N`；而 v18–v25 与 pull 全部覆盖为 `45/45 N` + Kp/Kd `1300/32` +
  `a2_m39_gripper_material_enabled=true`（指垫 static 1.1 / dynamic 0.9）+
  squeeze 上界 `30`、over-force `55`。resolved-config 证据为
  `logs_rl/a2_piper_full_stage_a2_base/base_v25/formal/V25_FULL_S0/config.yaml`
  与 `logs_rl/by_batch/base_v26_acquisition_supplement_20260823/formal/V26A_LR_S1/config.yaml`。
  `Kp800 × 最大几何行程0.035 = 28 N` 被 `10 N` cap 截断，`1300 × 0.035 = 45.5 N`
  不截断，因此 effort cap 与 Kp 必须成对看。
- 2026-08-31 20:05 HKT - R15 runtime 证据推翻"policy 学不会下压"这个描述：
  `R15_S1/model_step_000250` 在 RIGHT 有 16/64 把 handle 压到 `0.785398 rad` 硬限位，
  但握不住、回弹、latch 重咬。按门的 `door_handle_drive_max_force` 分层，
  `≤1.6 N·m` 为 `15/21`、`>1.6 N·m` 为 `1/43`；训练分布是 `U(1.0,3.0)`，即约 70%
  的门对该夹爪物理上不可解锁。同 door asset 家族的 v19 G3 step2500 是 16/16 到
  stage5、`max_handle 0.594–0.785`，含 `drvF 2.77/2.75/2.50/2.43` 四扇门。下压期
  handle 合力 v19 p50 `28.6 N`（受力指约 21.6 N）vs v26 p50 `16.8 N`（受力指钉在
  `10.5 N`）。
- 2026-08-31 20:05 HKT - v26-6 Wave A eval-only 单因素 A/B 给出 runtime 因果证据，
  typed route `GRIPPER_CAPACITY_CONFIRMED`。同一 R15_S1 step250 checkpoint、同 seed、
  门参数向量 exact 匹配、control 复跑与冻结 artifact bit-exact（`max_abs_delta 0.0`）。
  只加 `GRIPPER_CAPABILITY_BUNDLE`（45N + 1300/32 + M39 + 窗口30/55）后 RIGHT
  `handle≥0.3` 由 `16/64→48/64`，分层 `[1.6,2.2)` `1/27→23/27`、`[2.2,3.0]`
  `0/16→5/16`；下压期合力 `16.8→33.0 N`，最长持续下压 p50 `0→91` control step；
  Stage3 准入 `60→63/64`，over-force 步占比 `0`。因此 v26-3 的
  `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE` **不成立为容量结论**：该 ladder 是
  eval-only、用 10 N 下训练的 checkpoint、且保持 `over_force_threshold=40`、M39 关闭，
  等于一边放开力一边罚它用力。后续计划不得再以它为禁令。artifact：
  `logs_eval/base_v26/v26_6_waveA_gripper_capacity_20260831/reducer.json`。
- 2026-08-31 20:05 HKT - 恢复能力后剩余阻塞是 Stage3 收入结构，不是能力：44/64
  episode 把 handle 按在 `>0.6 rad` 达 p50 `64`、max `187` control step，`hinge` 仍
  `≤0.0111`，64/64 `stage_overtime`，保持期 `door_body_panel_normal_force_total` 为
  `0`。per-step 收入为 Stage2 滞留 `0.28939` vs Stage3 按住 `0.19655`，即 Stage2→3
  有 `-0.093/step` 悬崖（`a2_stage2_handle_center_y 0.119` 与
  `a2_stage2_handle_approach_xz 0.059` 进 Stage3 归零且无替代）；Stage3 内最大项
  `a2_stage3_unlatch_hold 0.0599/step` 以 `hinge<0.1` 为条件，替代它的
  `push_door_hinge + hold_and_drive` 仅 `0.0090/step`。Stage2 滞留中位数 `408`
  control step，说明 v26-3 E1 的"Stage2 夹爪开合极限环"是理性收入行为而非采样伪影。
  门解锁后是自由的：v26-3 U-probe 在 handle `0.5/0.6 rad` 得 hinge `0.0478/0.1443 rad`。
- 2026-08-31 20:05 HKT - `restored/left` 三个分层仍 `0/64`：LEFT 本就没有下压行为，
  单纯加力不诱发，属 v26-4 `BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET` 轴，需独立处理。
- 2026-09-02 16:23 HKT - v26-7 runtime constraint：`a2_v26_6_side_mirrored_handle_offset_enabled=true`
  对 all-RIGHT eval（zero LEFT clones）必须是合法 no-op；per-env `doorOpenLR` validation
  与 LEFT writes 仍 fail-fast。step1000 attempt1 的 removed-global-guard 前状态在 env
  construction 阶段失败，未执行 policy step；r3 复核确认 RIGHT authored offsets bit-identical，
  attempt2 12/12 与 determinism exact PASS。证据保留于
  `scriptsFORhuman/v26_7/runtime_logs/v26_7_bilateral_native_unlatch_20260902/failed_attempts/step1000_attempt1/`。
- 2026-09-02 16:23 HKT - trusted local `.hydra/runtime_config.yaml` 可能含
  `!!python/object/apply:pathlib.PosixPath`；reducer 读取该 artifact 必须使用 repository-established
  `yaml.UnsafeLoader`，因为 `safe_load` 会抛 `ConstructorError`；targeted existing-artifact
  `side_summary` 已通过。
- 2026-09-02 20:33 HKT - v26-7 Q20 在 §6.2 早停后，训练 shell 的全程 checkpoint 后置检查因
  缺少后续 checkpoint 产生 receipt `FAIL/1`，与 reducer 已冻结的科学 endpoint 不冲突；已对未来
  cell 的后置检查做 endpoint-aware 窄修，历史 Q20 receipts 不回写。
- 2026-09-02 20:33 HKT - v26-7 step2000 的 observation：LEFT durable 成功与 `arm_j4=1.745` 限位
  驻留同现；成功 LEFT pooled limit share 为 `38.1163%`，各成功 cell 为 Q05_S1 `51.0748%`、
  Q20_S1 `24.0005%`、Q20_S2 `38.2513%`。三个 LEFT=0 cell（Q05_S0、Q05_S2、Q20_S0）的
  `arm_j4` max 分别为 `1.257779/0.468791/1.289852`，限位步均为 `0`；限位步仅 `17.3697%`
  落在 first-rise→first-max。该 observation/inference 仅支持“探索问题”分支，不宣称机械可达性
  结论，也不作 typed route 最终裁定。
- 2026-09-03 00:30 HKT - v26-7 step3000 qualification：Q05_S2 LEFT durable `60/64`、
  `arm_j4` p95=`1.314685`、限位驻留 `0.0110%`，证明 durable 不以顶限位为必要条件；
  Q05_S0 LEFT durable `0/64`、p95=`1.142730`、限位驻留 `0%`，支持探索/Stage2→3
  收入结构分支而非机械撞限。详见 [goal anomaly appendix](../../../scriptsFORhuman/v26_7/a2_piper_base_v26_7_goal_anomaly_appendix_20260903.md)。
  同一附录记录 unrouted goal anomaly：Q05_S1 LEFT `complete=62/64`；静态审计未发现
  complete/Stage4→5 mirror defect，terminal hinge 未系统性更小；`95.253%` 限位步在
  Stage4，且最后限位距首次 `root_x>1.5` 至少 `34` 步、距 terminal 至少 `84` 步，
  因此为 `NO_THRESHOLD_EVIDENCE`。按 plan §8 不作 goal 能力或路由证据。
