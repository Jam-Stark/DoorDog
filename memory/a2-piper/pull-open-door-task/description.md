---
name: pull-open-door-task
scope: A2+Piper pull-door v0 foundations + pull-v1/v2 Stage3→4 + pull-v3/v4 traversal negatives + pull-v5/v5.1 bridge occupancy + pull-v5.2 anchored-probe + pull-v5.3 locomotion-interface + pull-v5.4 scheduler + pull-v5.5 residual-adapter + pull-v5.6-r2 specialist closure + pull-v6 lightweight send-past-body F0 closure
status: active
last_updated: 2026-08-25 14:16 HKT
owned_paths:
  - memory/a2-piper/MEMORY.md
  - memory/a2-piper/pull-open-door-task/description.md
  - memory/a2-piper/pull-open-door-task/TODO.md
  - memory/a2-piper/pull-open-door-task/DONE.md
read_when:
  - 复用 pull-v6 lightweight send-past-body F0 winner，或扩展 light-door robustness / heavier-door release strategy 前
  - 需要区分 v4 L1/L5 结论、v3 G2(c) traversal negative、v2 wall-removal runtime closure 与 v1/v0 历史边界时
---

# Pull-Open-Door Task (v0–v5.6-r2 closures + v6 active plan)

## Purpose

记录 A2+Piper pull-door v0 foundations、pull-v1 physical-gate negative closure、pull-v2 wall-removal/Stage4 occupancy closure、pull-v3 release-then-cross、pull-v4 frame-neighborhood behavior-creation、pull-v5/v5.1 bridge occupancy/release persistence、pull-v5.2 anchored-probe、pull-v5.3 locomotion-interface、pull-v5.4 scheduler、pull-v5.5 residual-adapter、pull-v5.6-r2 specialist closure与 pull-v6 F0 closure 的 direction contract、static-vs-runtime evidence boundary、reproducible commands、当前 TODO/DONE。不复制 raw trace 或长日志；只保存可复用结论。

## Pull-v6 Lightweight Send-Past-Body F0 Closure (2026-08-25 14:16 HKT) — FIRST STRICT-NATURAL E7 WINNER

- Winner checkpoint：`logs_rl/a2_piper_pull_v6/pull_v6_F0_r6an_seed3/model_step_000025.pt`；最终 eval contract：`gr00t/rl/config/ablation/wbmanip/pull_v6_F0_r6ap.yaml`。r6ap 只把已证明仍在稳定向 −X 行走的 Stage5/global time budget 扩为 `800` steps / `36 s`，不改 actor、observation、reward 或 door physics。
- Strict-natural 16-env seed3 eval 的 env14 是首个完整 winner：Phase C/release-ready step356、clean release step357、release persistence K25 step384、frame passage step620、E6 step739、E7 step1308，terminal `complete`；`arm_tangent_share=0.7974`、release hinge=`1.2477 rad`、release hinge velocity=`+0.3719 rad/s`、post-release recontact=`2`、最终 persistence=`998`。该 batch 只有 env14 成功，所以这是 behavior-creation proof，不是 light-door population robustness proof。
- 同 checkpoint/config/seed/env14 的五相机 runtime render 复现 `goal_reached=true`、Stage5、`crossing_while_holding=false`、terminal `reason-complete`，生成 main、handle top、handle side、world +X、world −X 五个 68 s MP4。render 必须保持 `num_envs=16` 才能复现 env14 的 scenario identity，并通过 `render_env_ids=[14]` 只写该 env。
- v6 最终机制边界：2D release mode observation；ready/released gripper mean override；D-only current-observation absolute base/arm mean；post-release arm tuck progress + persistent arm-default quality；world-frame door-through waypoint velocity tracking。heading 仍自由，release 后不 regrasp；当前已证实 90 kg light-door F0，不外推到重门/强 closer。

## Pull-v6 Lightweight Send-Past-Body Plan (2026-08-22 01:36 HKT) — AUTHORIZED / PLAN ONLY

- 用户批准将“送门过身”落为 v6 implementation contract；canonical 文档为 `scriptsFORhuman/pull_v6/A2_PIPER_PULL_V6_SEND_DOOR_PAST_BODY_IMPLEMENTATION_PLAN.md`。本次只完成文档与 backlog 整理，未实施 code、runtime、training 或 capability proof。
- v6 首轮只做 lightweight door：F0 canonical 后再做 F1 mass 80–100 kg / low-closer 2.5–5 N·m 小范围泛化。重门、强 closer 与不同 release 时机/动量策略进入 pull longterm TODO，不混入 behavior-creation 首轮。
- Stage 0–5 编号保持不变；Stage 4 细分为 4A retreat/clearance、4B arm-dominant send-past-body、4C positive-velocity release、4D immediate through。E5 捕获 root XY pivot 但不锁 yaw；heading 由 policy 在 collision、workspace 与 locomotion objective 下自由调整，不添加 absolute-yaw reward。
- 行为 attribution 使用 handle-in-trunk 有向换侧、root-relative arm tangent motion 与 `arm_tangent_share`；release 联合 angle、positive hinge velocity、clearance、arm margin 与 passage readiness，不用单一固定角度或 final hinge angle 代替成功。
- actor 首轮保持 canonical 12D action 与现有 observation order/shape，含 `door_dof_pos` 15-frame history；hinge velocity 先用于 reward/critic/telemetry，避免在 strict warm-start 前静默破坏 actor contract。
- 当前机器 GPU0–3 全部获用户授权用于 v6 实现验证、训练、实验与 test。P2 默认四 seed 一卡一个；P1/P3 按独立 cell 铺满四卡，gate/render 使用最早空闲 GPU 穿插，一张 GPU 同时只运行一个 Isaac Sim/训练作业。
- release 后换握另一侧 handle 或用手/臂撑门通过是独立 future contact-role transition；只在 v6 release/through 稳定且强 closer 直接证明 aperture collapse 后立项。
- pull longterm TODO 已清理为 future-only pull backlog；v0–v5.6 收口历史只保存在本 memory route。

## Pull-v5.6-r2 Terminal-Hold Specialist (2026-08-20 23:55 HKT) — T1 FAIL / G11 RETURN-TO-PLANNER

- 迁移机按绑定路径恢复 Python/IsaacSim/IsaacLab 与 16 项 archive；static migration verifier、IsaacLab headless smoke、fresh 8-env migration micro 全部 `PASS`。目标机 GPU0–3 经用户显式授权；T1 用 GPU0，checkpoint gates 用 GPU1。
- destination micro 暴露 actor constructor 在框架 strict-load warm checkpoint 前仍硬读 source-host raw checkpoint。已把 runtime actor 构造与一次性 raw warm-asset producer 分离；eval/T1 统一通过现有 trainer strict checkpoint loader 恢复 accepted warm/训练 checkpoint。无需补传 raw checkpoint。
- T1 retry 从 accepted step0 warm asset 启动，越过旧 batch1 `workflow_config` 边界并完成 `750/750`、`12,288,000` timesteps，生成 step250/500/750 三个 checkpoint，process exit `0`。
- 三个 registered five-family×16 gate 全部为 `0/80`；每格 row count 与 Invariant 12′ `PASS`，能力阈值均 `FAIL`。aggregate `infrastructure_status=PASS`、`scientific_status=FAIL`、`valid_fail_matrix=true`、`selected_checkpoint=null`。
- 因 T1 无 admitted checkpoint，rehearsal、formal anchor、door/G2/P3/P4/dual eval/render 全部 `NOT_RUN`；zero G3 attempts、无 passage denominator，canonical+natural `frame_passage` stopping condition 未满足。v5.6-r2 在 G11 return-to-planner 关闭，不自创 rung4、不放宽 `0.05 m/0.15 rad`。
- sole formal review 仍为 `FAIL`；targeted/runtime acceptance 不构成第二轮 reviewer PASS。终局证据：`scriptsFORhuman/pull_v5/PULL_V5_6_R2_ROUND_REPORT.md` 与 `logs_eval/a2_piper_pull_v5/v5_6_specialist_gate/TRAINING_GATE.json`。

## Pull-v5.5 Residual Terminal-Hold Adapter Closure (2026-08-17 08:13 HKT) — T1 FAIL / G11 return-to-planner

- registered rung2 residual terminal-hold adapter 完成 750-batch initial run，随后耗尽唯一 allowed target-offset curriculum retrain；final corrected r13 run `750/750` complete。T1 gates 为 step250 `0/80`、step500 `1/80`（仅 `near_rest`）、step750 `0/80`，远低于每 family `≥15/16` 与 overall `≥77/80`，所以 rung2 在其 registered contract 下 completed/failed；不泛化为所有 residual architecture 均不可行。
- 唯一 valid K100 是 r13 step500 `near_rest` env15：`terminal_current=true`、hold=`100`、XY=`0.0396828391 m`、yaw=`0.0298886299 rad`。它是 denominator=false/none 的 interface-characterization evidence，不能越过 family/overall gate，也不能选择 favorable endpoint；step750 回到零。
- reusable PPO gotcha：scripted prelude 与 one-step handoff 必须从 actor/entropy denominator 排除，critic 保留完整 trajectory；environment execution 和 frozen-leg inference 继续使用 applied carrier。r13 的 sampled/applied carrier provenance fix 使最终 run 有效；earlier G9 invalid attempts 不参与 capability adjudication。
- T2、formal T3 S1–S4、door probes、G2、P3/P4、dual-source eval 与 render 均 `NOT_RUN`，zero G3 attempts、无 passage denominator，canonical+natural `frame_passage` stopping condition 未满足。HOMIE fine-tune/rung3 未自动授权，回到 planner 决策。唯一 formal review 仍 `FAIL`；targeted fixes + runtime acceptance 不构成 reviewer PASS 或第二轮 review。G8 bank 与 protected evidence 未变，v5.4–v5.1 facts 保持 version-scoped。

## Pull-v5.4 Terminal-Yaw Scheduler Closure (2026-08-16 23:44 HKT) — Stage A GO / Stage B FAIL / G11

- Stage A 从 v5.3 accepted `44` traces、`352` env trajectories 与 `75,200` rows 完成 CPU feasibility，A4 选定 `pure_yaw_p0p05_T4`：raw `+0.05`，但 realized command-window yaw 为 negative。Stage A 是 `GO`，不是门侧 scientific population。
- valid Stage B rehearsal 的 sole shared correction 为 `-0.3672668933868408 rad`。两组 corrected target 的 max absolute error 分别为 `0.0900235176/0.0588076115 rad`，均在 immutable `0.15 rad` 内；但全部 `16` corrected rows 都是 `trim_step_cap_exceeded`、`terminal_hold_steps=0`、`terminal_current_state=false`、无 scheduler `DONE`。数值 proximity 不满足 terminal-current/100-step-hold contract，故 Stage B `FAIL`，零 G3 anchor attempt consumed。
- Earlier G9 attempts 是 invalid/blocked infrastructure evidence，不进入 science；valid Stage B 为 `interface_characterization`、denominator `false/none`。anchor、door buckets、G2、P3/P4、dual-source eval 与 render 均 `NOT_RUN`，无 passage denominator，canonical+natural `frame_passage` stopping condition 未满足。
- 三 rung ladder：scheduler rung 已完成并失败；residual terminal-hold adapter precommit 是下一 v5.5 planner-contract item，本轮 worker 未启动；HOMIE fine-tune 是第三 rung，除非 residual 被证伪否则 indefinitely deferred。唯一 formal review 仍 `FAIL`；targeted fixes + runtime acceptance 不构成 reviewer PASS 或第二轮 review。v5.3/v5.2/v5.1 durable facts 保持 version-scoped。

## Pull-v5.3 HOMIE Locomotion-Interface Closure (2026-08-16 16:58 HKT) — H-D/G11 stop

- P0 完成 `44/44` 个 versioned `interface_characterization` cell、每 cell `8` 个 env；诊断记录严格排除 scientific numerator/denominator。T1/T2/T4 的诊断窗口分别精确为 `150/200/300` steps，P0 不改变 frozen stage topology。
- H-D 由 immutable terminal zero-command hold 判据选定：`u=-2` 的 T1/T2/T4 两秒 hold drift mean 分别为 `-0.226979/-0.219226/-0.216827 rad`，每 cell `8/8` 均超过 absolute `0.15 rad`；`u=-0.8,T1` mean=`-0.154359 rad`，`5/8` 超过。frozen HOMIE high-|u| 响应呈 rate-like 但 asymmetric；这不是可由 probe-side gain/sign patch 修复的门侧结论。
- P1 mapping fix、narrow anchor、door closer buckets、G2、P3/P4、dual-source eval 与 render 均 `NOT_RUN`，无 door-side passage denominator；canonical+natural `frame_passage` stopping condition 未满足。`0.05 m/0.15 rad` 阈值不可放宽。
- 唯一 formal review verdict 为 `FAIL`。H-D fail-closed artifact、由 `dones` 派生的 terminal telemetry、independent declared-versus-actual provenance 已定向修复并通过 bounded acceptance；按用户一轮 review 约束未运行第二轮，绝不表述为 reviewer PASS。下一步 residual yaw adapter/policy 或 HOMIE fine-tune 必须由用户以新 approved contract 决定；v5.2 terminal-current-state rule-5 与 v5.1 P2/F5/G8 保持 version-scoped。

## Pull-v5.2 Anchored Probe Closure (2026-08-15 03:08 HKT) — G3/G11 stop

- Rule 5 只认证门侧实际使用的 sequence set；从 v5.2 起，认证必须使用 terminal current-state waypoint + yaw retention，不能把 episode 初始时刻或中途的 historical latch 当作终点保持。v5.1 所谓 S1/S2 yaw PASS 实际来自 initialization latch，不能继续当作 terminal-yaw capability。
- T0 落地了 S1–S4 sequence、G8 pure-A 显式许可、door-only evaluator P2 trace 证明、P3 canonical 前 50 步 env-side arm/gripper override、`bank_natural_e5_override` provenance 与 invariant 11。正式 review 仍只有一轮且 verdict FAIL；r3 findings 以 targeted fixes + runtime acceptance 处理，未生成第二轮 reviewer PASS。
- 三次 natural open-field anchor 均完成四 sequence×16 行，command_solvable 每序列均 `16/16`。attempt1/2/3 waypoint 分别为 `9/10/10/9`、`8/12/12/8`、`7/11/10/8`；yaw 分别为 `0/0/0/0`、`0/0/0/0`、`1/0/1/5`。r4 给 zero-yaw phase 增加 active hold 后未改善；r5 将 open-field root 对齐 bank 的 yaw≈π 后降低了 yaw error，但仍未达到 terminal `16/16`。
- 三次共 `192` 个 natural-anchor terminal episodes，在该 scope 内十一项 invariant 未观测到 violation；natural anchor 未加载 bank，故不能把这写成 canonical bank/override runtime PASS。三桶、G1/G2、P3/P4、dual-source eval 均 NOT_RUN，无 passage denominator；canonical+natural frame-passage stopping condition 未满足。完整英文证据见 `scriptsFORhuman/pull_v5/PULL_V5_2_ROUND_REPORT.md`。
- v5 的 external-review pointer、7 条 metric 语义与 occupancy 规律继续有效；P2 release-persistence binding、F5 ACTUAL 与 191-row `PASS_G8_PURE_A` bank 仍是 v5.1 version-scoped evidence。residual policy 仍属用户/架构决策，不能在无有效 G2 时由 worker 自行采用。

## Pull-v5.1 Repair Closure (2026-08-14 22:35 HKT) — G3/G11 stop

- v5 的 external-review pointer、7 条 metric 语义与 occupancy 规律继续有效：`deliberate_release` 仍只是一帧 contact-transition，persistent release 仍是 K=25；recontact 仍不是 regrasp/brace；`frame_approach` 仍是 strip occupancy；E3 可先于 E2；E5 仍是自动 telemetry；E7 仍是 strict whole-body -X clearance；base reversal 仍无 deadband。外部原文指针仍为 `scriptsFORhuman/pull_v4/pro—feedback/a2_piper_pull_external_review_package_20260812.zip::a2_piper_pull_external_review_package_20260812/a2_piper_pull_external_review_20260812.md`。
- F5 load-only runtime 为 `ACTUAL`：actor 从 `policy_state_dict` 加载；critic/optimizer/scheduler 未加载并 reset；`load_optimizer=false`。receipt 同时记录 eval wrapper 把 requested `policy_only` 归一化为 effective `full`，v5.1 只记录、不改 wrapper。
- P2 frozen v4-B paired intervention 完成：32 个 matched screening keys 中 22 对严格 admissible，稳定取前 16 对；control K25=`3/16`，release+tuck intervention K25=`16/16`，discordant `0/13`、ties `3`，one-sided exact McNemar/binomial `p=0.0001220703125`（SciPy 1.15.3），故 release persistence 是 binding constraint。两组 E6/frame passage 都是 `0/16`；intervention 的 +2s hinge≥1.6 仅 `5/16`（control `16/16`），说明 release 与 door reclosure/base route 仍是耦合问题，不是 traversal success。
- Source-A legacy 64-row/86-buffer payload 经逐态 closer metadata 修复保持不变，并补采 E5+2s/E5+4s `64/63`。Source B 三次 G9 后仍无 settle-admitted row，按 G8 建成 pure-natural bank：总 `191`，provenance E5/E5-plus=`64/127`，closer buckets=`45/54/92`，manifest 每态含 force/bucket/tier/settle/source-row；状态为 `PASS_G8_PURE_A`。
- P1 三次 G9 修复后进入真实 rule-5 anchor；三次 G3 scientific correction 都完成四 primitive×16 rows，waypoint=`64/64`、command_solvable=`64/64`、yaw=`32/64`，最终 receipt 仍 FAIL。门侧三桶从未启动，因此 P1 是 anchor BLOCKED，不是 passage=0；G2/P3/P4/dual-source eval 均 NOT_RUN，canonical/natural stopping condition 未满足。residual policy 仍须等有效 G2 lattice 后由用户决定。
- review provenance 不变：正式 review 只有 r1 一轮且 verdict FAIL；r2 findings 以 targeted fixes + runtime validation 处理，未声称第二轮 reviewer PASS。完整英文证据见 `scriptsFORhuman/pull_v5/PULL_V5_1_ROUND_REPORT.md`。

## Pull-v5 Closure (2026-08-12 07:45 HKT) — stopped before G2

- 采用外部评审的 Rank 1、Fact D 与 §3.3，外部 review pointer 为 `scriptsFORhuman/pull_v4/pro—feedback/a2_piper_pull_external_review_package_20260812.zip::a2_piper_pull_external_review_package_20260812/a2_piper_pull_external_review_20260812.md`。本轮将语义固定为：`deliberate_release` 是一步 contact-transition label，不是 persistent release；`post_release_recontact_count` 只数 body/arm-panel contact transitions，不是 regrasp 或 brace；`frame_approach` 是 frame-strip occupancy，不是单调 Euclidean proximity；E3 可先于 E2；E5 是自动 latch/telemetry milestone，不是 policy choice；E7 是严格的 whole-body -X clearance，而已验证的 v4 E6 仍为零；`base_reversal_count` 没有 deadband。
- persistent release 的 v5 定义是连续 `K=25` 个无 handle-contact steps；panel clearance 排除在此定义之外，只作诊断。此修正不得倒推为 v3/v4 已学会 release、regrasp 或 brace。
- P0 census runtime PASS（v4-B, 64×50）：Stage0/1/2/3/4/5 snapshot counts 为 `12800/64/64/64/64/0`；Stage4 hinge mean `.252803`、range `.250109–.256819`。这证明 staged-reset occupancy 仍落在 early-open，post-release/frame-transition mass 为零。
- v5 bank runtime：Source A 导出 64 个 `bank_natural_e5` states / 86 buffers，均 `settle_valid` 且 `settle_steps=50`；runtime closer-force buckets 为 `15/18/31`，但 exporter 遗漏 per-state closer force；`frame_approach`/aperture/release 都为零，midpoint distance min `.5448`、median `.7108`。builder 需要的 Source B 缺失，B 在 stage0 ratio invariant 失败，最终 bank 不存在；因此 Source A 不是可用的 canonical bank。
- P0 census 为 PASS；load receipt 仍因 load-only guard conflict unresolved；P0-C archive 为 PASS（`302,913,787` bytes、195 entries、75 projected traces、无 hash）。P1 anchor+door 为 BLOCKED，非 passage=`0`；P2 为 INCONCLUSIVE；P3/P4/G2 为 NOT_RUN。G9/G11 是 negative/infrastructure closure。stopping condition（canonical 与 natural starts 都出现可复现 frame passage）未满足。
- 正式 review provenance 仍是 FAIL，只有一轮 review；r3–r5 的 targeted repairs 与 runtime evidence 不生成第二个 reviewer PASS。任何 future round 都先修复/验证 pure-A builder、per-state closer metadata、真实 holding-near-frame/release capture、anchor/P2 对 bank 的独立性，以及 load-only guard；只有有效 G2 lattice 后，residual policy 才由用户决定。

## Pull-v4 Closure (2026-08-11 19:53 HKT) — negative

- v4 A/L5（移除 `door_wide` maintenance annuity）与 B/L1（A + signed `frame_approach` creation income）都只从 pull-v2 Wave2 seed1 step750 warm start。canonical D0-lite B 为 16×804，八项 invariant 全零，`door_wide` raw 全零且未执行；signed frame raw min/max/median 为 `-1/1/0`，episode income median `-7.829`、range `[-19.590, 7.303]`；G11 correlation `0.993454`、sign alignment `16/16`。B0 64×50 smoke PASS；四个 Wave1 256×750 batch 全部 natural exit。
- 12 个 base eval cell（A/B × seed0/1 × step250/500/750）每格均为 16 episodes、八项 invariant 全零，且 E6/E7/complete 均为 `0/16`。release curve（seed0 step250/500/750，再 seed1 同序）为 v3 `[7,2,0,1,0,0]`、v4 A `[0,1,0,0,1,0]`、v4 B `[2,2,2,2,0,3]`，故 A/L5 单独未逆转 release extinction，L5-only hypothesis 不成立；B/L1 改变了 basin，保留了有限 base release。
- B-only G6 time diagnostic 的 release base→extended 依次为 `2→9, 2→9, 2→12, 2→8, 0→9, 3→11`；六格 frame-midpoint median 均改善，但 `frame_approach`、E6、E7、complete 仍均为零。时间是 release/proximity constraint，不是剩余 primary bottleneck；不再扩预算，也不触发 relay、seed2 或 render。G10 仅记录：base recontact max `10`、max median `0`；extended max `108`、max median `3`；brace 未实现。
- 结论：B/L1 的 signed creation income 确实改善 release/proximity，却未创造 frame-neighborhood capability 或 E6；未确认 L5-only 假说。正式 static review 为 FAIL；其 P1 findings 已定向修复并由 D0、smoke、Wave1、base eval 与 G6 runtime validation 覆盖；依用户指令不做第二轮 review，不能写成 post-fix review PASS。证据路径：`scriptsFORhuman/pull_v4/{D0_LITE_RECEIPT,PULL_V4_ANALYSIS,PULL_V4_G6_ANALYSIS}.json`。

### §0.3 Creation-vs-Maintenance general rule

- 已在较早 basin 学成的 mature push/open mechanism 通常是 maintenance-grade：它能保持或修复已创建的行为，但未必能从 warm-start basin 创造缺失的 downstream behavior。目标行为缺失时，先提供与 signed task progress 绑定的一阶 dense creation income，并给足以驱逐旧 steady state 的 pressure/time；行为出现后才让 maintenance income 承接。证据链包括 `pull_door_handle` 6.0、`near_closed` truncation、corridor port 的既往结果，以及 v4 中 signed L1 改善 release/proximity 但仍未抵达 frame neighborhood 的细化证据；不得把该规律误写成 L5 单独已获确认。

## Pull-v3 Closure (2026-08-11 00:03 HKT)

- North Star 固定为 `aperture_ready → deliberate release → through-frame → whole-body clear to -X`，不做 hold-through。C1–C7 已落地：v3 guard、Stage4/5 时间预算 `250/300` 与 `24 s` episode、frame-passage 门框谓词、aperture 后 open-command penalty 遮罩、仅两项 corridor reward（`4.2666667/1.0`）、signed trunk-footprint-to-current-panel clearance/base path/reversal/recontact telemetry，以及 `pull_v3_T_traversal.yaml`。`penalty_a2_v20_pre_send_crossing` 未移植，其余 reward scale/threshold 未改。
- Frozen pull-v2 Wave2 actor 的 canonical D0-lite 为 16×804 steps：E6/E7 均为 `0/16`，六项 invariant 全零，corridor 在 aperture 前激活为零；单次 64×50 smoke natural exit。Wave1 两 seed 均为 256 env×750 batches，step250/500/750 checkpoint 齐备；六个 checkpoint 各 eval 16 episodes，Stage4 admission 为 seed0 `16/15/15`、seed1 `16/16/16`，六项 invariant 每格全零。
- Wave1 六格 E6/E7/complete 全为零，双 seed 同判 `G2`，不触发 Wave2 或 seed2。具体为 G2(c)：deliberate release 依次为 seed0 `7/16,2/16,0/16`、seed1 `1/16,0/16,0/16`，发生 release 的 episode 均观测到 −X motion，但所有格 frame-approach/frame-passage/planar-crossing/detour 仍为零。结论是 traversal approach/path-distribution 的科学负结果；本轮未追加或修改 reward scale，下一候选仅预登记 v4 frame-neighborhood/path shaping。
- G10 触发：seed0 step500 的 post-release recontact 最大 `18`（median `0`）；只在 pull longterm TODO 第 1 条勾稽 arm brace 期货，本轮不实现。G5 未触发（六格 panel-contact median 均为 `0`），G6 未触发。
- Durable trace contract：`stage2_5_step_trace` 只覆盖 terminal `stage_buf∈{2,3,4,5}`；terminal diagnostics 仍必须完整覆盖 16 episodes 并作为 E0–E7/complete 分母。stage0/1 terminal 无 trace row 是合法域外，不得误判为丢行，也不得把真正的 stage2–5 缺行降级为零。
- Review evidence boundary：唯一一轮 code/IsaacLab review 的正式 verdict 为 FAIL；C6 signed clearance 与 analyzer/orchestration/report findings 已定向修复，修复后由 targeted static checks、canonical D0、smoke、formal train/eval 与 fail-closed analysis 验证。依用户“一轮 review 上限”未生成第二轮 reviewer PASS，不得把它表述为 review PASS。

## Pull-v2 Closure (2026-08-10 09:32 HKT)

- Canonical deterministic U-probe（无机器人）测得 `theta*=0.6 rad`，回填 `a2_pull_e3_latch_threshold_m=0.02292371541261673`；θ=0 时 hinge max `0.001943 rad`，G5/G6 均未触发。第一次 sampled-fixture receipt 已标记 invalid，不作为标定证据。
- V2-W 从 v1-R seed0 step750 `policy_only` warm start。唯一 reward 改动是 `a2_stage3_unlatch_near_closed_hinge_threshold 0.1→0.25`；`UNLATCH_NORM=0.6`、速度 norm、`dont_push_door_handle`、`target_root_distance` 与 Stage3→4 hard gate 均未改。E3 改用 calibrated latch threshold + stable contact，handle/latch 双口径 stable-unlatch/relock 进入 telemetry。
- 单次 64×50 smoke 验证 v2 plan-id、训练路径与 resolved `near_closed=0.25`；它发生在 canonical probe 回填之前，resolved latch threshold 为 sampled attempt 值，因此只构成 smoke acceptance，不构成 canonical E3 runtime calibration PASS。Wave1/Wave2 formal resolved config 使用 canonical threshold。
- Wave1 双 seed 触发 G1：step750 true Stage3→4 为 seed0 `10/16`、seed1 `6/16`，valid-hold hinge Δ max 为 `0.749745/0.492656 rad`；dwell `0.105–0.25` 为 `1997/1193`，不再是 v1 恒零墙。最佳 Wave1 seed0 step750 relay 进入 Wave2。
- Wave2 六格 true Stage4 依次为 seed0 `13/16,14/16,15/16`、seed1 `11/16,16/16,16/16`；step750 hinge Δ max `2.527259/2.617994 rad`。Wave1+Wave2 共 12 cell、192 terminal episode，四项 integrity invariant 每格均为零；A0 因 G3 false 而 `NOT_TRIGGERED`。下一 round 转 traversal/V1-C，不在 v2 继续追加 reward seam。
- Review evidence boundary：唯一一轮 code/IsaacLab review 的正式 verdict 为 FAIL；其 seed forwarding、E3 predicate、analyzer、U-probe fixture/GPU binding 与 orchestration findings 已定向修复。依用户“一轮 review 上限”未生成第二轮 reviewer PASS；修复后的 acceptance evidence 来自 Hydra/static check、canonical U-probe、smoke、两轮训练/eval 与 fail-closed analysis。不得把它表述为第二轮 review PASS。

## Pull-v1 Closure (2026-08-09 15:19 HKT)

- C1–C6 的 Stage3→4 hard gate、event semantics 与 V1-A/B/R configs 已完成；static validation 为 Python compile PASS、YAML/Hydra composition PASS。namespace suite 为 `148 passed / 4 failed`，四项为缺失历史 Kit logs 的无关 fixture，未修复。
- D0 frozen replay runtime PASS：16/16 终止 episode 均停在 Stage3，E4/E5 均为 0，四项 semantic/integrity invariant 均为零。V1-B 64 env × 50 batch smoke natural exit。
- V1-A/V1-B/R 双 seed formal training 与 checkpoint eval 均完成。18 个 accepted v1 cell×checkpoint、288 terminal episodes 的 true Stage3→4（`hinge>0.25 ∧ grasp-streak ∧ panel_clear`）均为 0；每行四项 integrity invariant 均为 0，不能宣称真实 Stage4 capability PASS。
- A/B 的 valid-hold hinge Δ max ≤0.002201 rad，双 seed stable unlatch 均为 0。R 的 `pull_door_handle` reward port 行为上 active：step750 stable unlatch 为 seed0 13/16、seed1 2/16；R0 hinge Δ max 0.100607 rad 仍低于 0.25 gate，R1 保持 baseline scale。预注册“reward 迁移不是主要瓶颈”negative 未触发。
- R 的两次 construction-guard defect 都在 batch1 前按 root cause 修复；最终 A/B/R exact config/runtime contracts fail fast，第三次 R launch 每 seed natural exit。下一 scope 仅比较 R0/R1 与 matched A/B 的 handle-frame force direction、arm/base trajectory、grasp stability 与 hinge torque transfer；不要先启动 V1-C 或另一轮 broad reward sweep。

## Governing Design

- 三条 binding amendments（split doc §2 确认）：
  1. Pull-side P1 verdicts require a passing push-side known-good anchor first。Anchor FAIL → `PROBE_INVALID`，不算 mechanism finding；one-shot scientific verdict 不消耗。
  2. P1 central fixture mass = 120 kg（resolved v20 G4 `[80,160]` midpoint）。
  3. Pull plan-id freeze-guard + regression tests precede env/asset changes。
- Anchor/review order: repair → targeted tests → push anchor → freeze → code_reviewer → isaaclab_reviewer → unlock P1 pull matrix → P2（P2 需 explicit GPU allocation）。
- Anchor admission reruns 不消耗 one-shot scientific verdict；只有 admission 通过且 anchor 完成才消耗。
- Thresholds 保持 `report_only`；inapplicable metrics 用 N/A；implicit-actuator effort 标 `ESTIMATE_ONLY`。

## Direction Contract

- Production pull-cell handle command 必须产生 door-frame +X force（toward robot / tension），不是 world -X compression。
- Proof direction: world +X（door-frame tension），proof offset 0.006m，ramp 30 steps，hold 10 steps。
- Commandable DOFs only：DifferentialIKController DLS to arm_j1..j6 + high-level gripper primitive + bounded base planar velocity。No low-level USD runtime writes。

## Static-vs-Runtime Evidence Boundary

### R17 Repair (2026-08-04 22:29–23:45 HKT) — STATIC PASS

- Schema: `pull_v0_repair_r17_receipt_v1`，sha256 `73d0e2184980579b4664d260ab245647bf2d3f4189cc81d3bb0aee165c8dfaf9`。
- Status: `APPROVED_FOR_ATTEMPT20_PREPARATION_ONLY`，`runtime_validation: NOT_RUN`，`scientific_verdict_consumed: false`。
- Chain: parent R16.4 (`cf0d7107…`) + Attempt19 PROBE_INVALID receipt (`4f92eba0…`)。
- Root cause: Attempt19 steady capture failed closed under R16.4 G-only nonselected rule；observed footprint 是已知 NVIDIA driver/Kit enumeration behavior（eval PID 低显存 context 出现在所有可见 GPU，selected GPU2 独占 compute）。Evidence-admission defect，非 plant/pull verdict；physical plant `INCONCLUSIVE_NO_PROOF_SAMPLES`。
- Repair: helper attempt-label threading + Attempt20 enumeration classification（C/G/C+G same-PID acceptable, FB≤1024, NOT_REPORTED preserved, 0%-util-unless-OTHER_TENANT）；runner exact Attempt20 support + lifecycle-robust process_receipt（SIGINT/SIGTERM → 600s wait → SIGKILL only on timeout, unknown timestamps null/NOT_RECORDED）；Attempt19 capture-failure + PROBE_INVALID receipts；focused tests（152 passed）。
- Full namespace suite: **152 passed**（R16.4 baseline 142 → +10）。
- Prep-only closure: 确认无 Attempt20 artifact。

### Attempt19 (2026-08-04 22:18–22:19 HKT) — PROBE_INVALID (immutable)

- Reached evaluation boundary (stdout line 621) then evidence capture failed closed。
- Runner PID 2219008 / eval PID 2219040 reaped；no process_receipt.json。
- Receipts: `PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_CAPTURE_FAILURE.json` (sha `6fab55d0…`) + `PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_RECEIPT.json` (sha `4f92eba0…`)。
- Immutable artifacts: plan `cf23ee03…` / launch `03530324…` / stdout `2614844d…`。

### Attempt20 (2026-08-04 23:45–23:56 HKT) — ADMISSION PASS / ANCHOR FAIL

- R17 枚举分类修复生效：runtime 完成自然退出 (returncode 0, natural_exit true)。
- Process receipt: runner_pid 2271508 / eval_pid 2271525，summary + metrics 全部产出。
- Receipt: `PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_RECEIPT.json` (sha `b1b2fa0d…`)。
- **Anchor verdict: FAIL** — `BASE_RELIEF_DISPLACEMENT_LIMIT`，zero proof samples，zero terminal bilateral streak。
  - Hinge at crossing 1.043 rad (>0.25 ✓)，crossing_while_holding ✓，latch released ✓，body-panel contact 0.0 N ✓。
  - Episode: length 804, stage 4, stage_overtime, goal_reached false。
- `scientific_verdict_consumed: false` — anchor 未通过，one-shot verdict 未消耗。
- Steady-state footprint 未捕获（eval 在 600s sleep 内完成自然退出，早于 steady capture window；process_receipt + summary + metrics 是更完整的证据集）。

## GPU Lease

- Selected physical GPU2；authorized `[2,3]`；GPU7 never as compute。
- NVIDIA driver auto-creates low-memory enumeration contexts of the eval PID on every visible GPU — acceptable under Attempt20 classification（FB≤1024 MiB, PMON NOT_REPORTED-or-zero, 0% device util unless OTHER_TENANT）。
- OTHER_TENANT evidence 永不归因于 attempt PID。
- Attempt20 运行时 GPU2 独占 compute；GPU4 有 OTHER_TENANT (v13-student-distillation camera eval)，未干扰。

## Reproducible Commands

```bash
# R17 validate-only (prep-only closure)
/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/pull_v0/run_p1_push_anchor.py \
  --attempt 20 --repair-receipt scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R17_RECEIPT.json \
  --repair-receipt-sha256 73d0e2184980579b4664d260ab245647bf2d3f4189cc81d3bb0aee165c8dfaf9 \
  --validate-only

# R17 prepare-only (generate immutable Attempt20 plan + input)
# (same args, --prepare-only instead of --validate-only)

# Attempt20 launch occupancy capture
/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/pull_v0/capture_p1_anchor_gpu_evidence.py \
  --mode launch --attempt 20

# Attempt20 GPU eval (tmux, long run ~9min)
/home/baoquanc/anaconda3/envs/isaaclab/bin/python scriptsFORhuman/pull_v0/run_p1_push_anchor.py \
  --attempt 20 --repair-receipt scriptsFORhuman/pull_v0/PULL_V0_REPAIR_R17_RECEIPT.json \
  --repair-receipt-sha256 73d0e2184980579b4664d260ab245647bf2d3f4189cc81d3bb0aee165c8dfaf9

# Full namespace suite (once)
/home/baoquanc/anaconda3/envs/isaaclab/bin/python -m pytest gr00t/rl/tests/test_a2_pull_namespace.py -q
```

## Key Source Facts

- `capture_p1_anchor_gpu_evidence.py`: `ATTEMPT_GPU_CONTEXT_CLASSIFICATION_MODES` — `[19]=STRICT_G_ONLY_INACTIVE_VULKAN_ENUMERATION` (historical, preserved), `[20]=LOW_MEMORY_SAME_PID_ENUMERATION_CONTEXTS` (R17)。`attempt: int = ATTEMPT` 线程化所有 shared validators。
- `run_p1_push_anchor.py`: `_LifecycleSignal` + `_stop_child_after_lifecycle_signal` (600s wait, SIGKILL only on timeout)。`validate_preparation(20, ...)` / `prepare(20, ...)` / `run(20, ...)`。CLI `--validate-only` / `--prepare-only`。
- Attempt20 plan: `pull_v0_p1_push_anchor_plan_v1`，attempt 20，checkpoint base_v20_R3_G4 step2500，fixture 120kg / handle 0.95m，capacity 64 anchor-only。

## TODO Summary

- 2026-08-20 23:55 HKT - v5.6-r2 rung3 已完成/失败：T1 `750/750` 后 step250/500/750 gate 全为 `0/80`，没有 selected checkpoint，故 G11 return-to-planner。三 rung ladder 均已在各自 registered contract 下完成/失败；新架构或新预算必须由用户另行授权，不得自动进入 rung4。rehearsal/anchor/door/P3/P4/DV/render 保持 NOT_RUN，无 passage denominator。
- 2026-08-17 08:13 HKT - v5.5 rung2 residual terminal-hold adapter 已在 registered T1 contract 下完成/失败：r13 gate=`0/80,1/80,0/80`，唯一 valid K100 不能满足 `≥15/16` per-family 与 `≥77/80` overall。当前状态为 return-to-planner；rung3 HOMIE fine-tune 非自动授权，须新的 planner decision。sampled/applied carrier provenance 是后续 PPO 工作必须复用的经验。
- 2026-08-16 23:44 HKT - v5.4 scheduler rung 已以 Stage A `GO`、valid Stage B `FAIL` 收口：shared correction 后 corrected max error=`0.0900235176/0.0588076115 rad` 虽低于 `0.15 rad`，但全部 `16` rows `trim_step_cap_exceeded`、terminal hold=`0`，不能启动 G3 或门侧下游。当前 active architecture item 是用户须另发 v5.5 planner contract 的 residual terminal-hold adapter；HOMIE fine-tune 仅在 residual 被证伪后考虑。
- 2026-08-14 22:35 HKT - v5.1 已清偿 pure-A builder、per-state closer metadata、P2 bank 独立性与 load-only receipt；下一 occupancy/traversal round 的唯一 active blocker 是 rule-5 四 primitive yaw execution（当前稳定 32/64），必须先得到 anchor PASS 才能启动三桶门侧 P1/G2/P3。P2 已确认 release persistence binding，但 +2s reclosure 与 E6=0 表明不可单独据此扩 P3；residual policy 仍只在有效 G2 lattice 后由用户决策。
- 2026-08-06 14:30 HKT - v0 E6/E7 capability boundary remains a separate historical problem: the policy never attempts path reversal (first_path_reversal_step=N/A for all episodes), ends at E5 with stage_overtime at 654 steps, and has tiny outward excursion (0.013-0.099m). Possible causes remain clear-phase reward, stage-time budget, or base-motion action space; investigate only under separately authorized scope.
- 2026-08-06 14:00 HKT - v0 seed1 E2-E5 instability remains historical context: checkpoints oscillated between 2/16 and 16/16 uniformly across strata, not explained by spawnHook or hinge force. Matched replicates or longer training remain a separate option.

## DONE Summary

- 2026-08-17 08:13 HKT - pull-v5.5 residual adapter 的 750-batch initial run、唯一 target-offset curriculum retrain 与 corrected r13 `750/750` 已完成；T1 gate fail-closed 为 `0/80,1/80,0/80`，只有 step500 `near_rest` env15 K100，故 G11 return-to-planner。T2/T3/door/G2/P3/P4/dual eval/render NOT_RUN，无 passage denominator；formal review FAIL，targeted/runtime acceptance 非 reviewer PASS。
- 2026-08-16 23:44 HKT - pull-v5.4 Stage A feasibility `GO` 使用 `44/352/75,200` v5.3 diagnostic evidence；valid Stage B rehearsal 在所有 corrected rows 数值误差低于 `0.15 rad` 的情况下，仍因 `trim_step_cap_exceeded`、terminal-current false 与 100-step hold=`0` truthfully `FAIL`。无 G3 attempt，门侧下游 NOT_RUN，无 passage denominator。formal review 保持 FAIL；targeted/runtime acceptance 不是 reviewer PASS。下一 architecture rung 是 residual terminal-hold adapter precommit。
- 2026-08-14 22:35 HKT - pull-v5.1 repair closure: F5 ACTUAL、P2 paired verdict PASS、Source-A metadata/delayed capture 与 191-row G8 pure-natural bank 完成；P2 K25 `3/16→16/16`、13 个 favorable discordants、`p=0.0001220703125`，确认 release persistence binding，但 E6/frame passage 仍 `0/16`。P1 四 primitive anchor 三次均 waypoint/solvable `64/64`、yaw `32/64`，按 G3/G11 在 anchor BLOCKED 收口；三桶、G2、P3/P4、双源 DV NOT_RUN，stopping condition 未达。正式 review 保持一轮 FAIL，无第二轮 PASS claim。
- 2026-08-12 07:45 HKT - pull-v5 bridge-occupancy/release-persistence closure: adopted external review Rank1/FactD/§3.3 and corrected metric semantics; P0 v4-B census runtime PASS (`12800/64/64/64/64/0`, Stage4 hinge `.252803` / `.250109–.256819`) proves early-open reset occupancy with no post-release/frame-transition mass. Source A produced 64 settle-valid E5 states/86 buffers but omitted per-state closer force; Source B failed stage0 ratio invariant, so no canonical bank exists. P0 load-only receipt remains unresolved; P0-C archive PASS (`302,913,787` bytes, 195 entries, 75 projected traces, no hash). P1 anchor+door BLOCKED, P2 INCONCLUSIVE, P3/P4/G2 NOT_RUN; stopping condition not met. One formal review wave remains FAIL; r3–r5 targeted repairs/runtime evidence are not reviewer PASS.
- 2026-08-12 00:07 HKT - Handoff preparation completed: the capped derivative excerpt is at `a2_piper_pull_v1_to_v4_evidence_20260811.zip` (untracked root artifact; 108,407,774 bytes, 120 entries, within the 500,000,000-byte cap). Its tracked-source manifest and builder are `scriptsFORhuman/pull_v4/MANIFEST.md` and `scriptsFORhuman/pull_v4/build_pull_v1_v4_evidence.py`; source render evidence is under `logs_eval/a2_piper_pull_v4/renders/`. Tier1 has 97 files, Tier2 has 22 files, and the six R1 logical video omissions are explicit. Four unavailable v2 full runner logs remain omitted and `.hydra/train.log` was not substituted. R1 is INCONCLUSIVE/NOT_RUN after three launcher attempts with zero videos; this launcher-lifecycle limitation is not a policy or product-runtime verdict. R2-R4 each natural-exited and produced six full-decode 1280×720@20fps MP4s. The archive is a derivative excerpt; original evidence units remain untouched. No behavior-success claim is made.
- 2026-08-11 19:53 HKT - pull-v4 negative closure: A/L5 与 B/L1 仅从 pull-v2 Wave2 seed1 step750 warm start；B D0-lite、B0 smoke、四个 Wave1 与 12 cell eval 完成。所有 base cell 的 E6/E7/complete `0/16`、八项 invariant 零；L5-only 不成立，L1 改善 release/proximity 但未创造 frame-neighborhood/E6。G6 不再扩时，G10 只记录不实现 brace。formal static review FAIL；targeted repairs + runtime validation；依指令无第二轮 review。
- 2026-08-11 00:03 HKT - pull-v3 closure: C1–C7, canonical D0-lite, single smoke, dual-seed Wave1 train and six checkpoint evals completed. All six invariants were zero; all cells had E6/E7/complete `0/16`, so G2(c) closed as a traversal approach/path-distribution negative and no Wave2/seed2 ran. G10 triggered on recontact max `18`; one review wave remained formally FAIL with bounded fixes runtime/target validated and no second reviewer PASS.
- 2026-08-10 09:32 HKT - pull-v2 closure: canonical U-probe measured `theta*=0.6 rad` and latch threshold `0.02292371541261673`; only reward change was `near_closed 0.1→0.25`. Wave1 step750 true Stage3→4 reached `10/16` and `6/16`, triggering G1. Wave2 relay produced true Stage4 `13/16,14/16,15/16` and `11/16,16/16,16/16`; all four invariants were zero across 12 accepted cells/192 terminal episodes. A0 was NOT_TRIGGERED; next scope is traversal/V1-C.
- 2026-08-09 15:19 HKT - pull-v1 closure: C1–C6 implemented; Python compile and YAML/Hydra composition static PASS. D0 frozen replay runtime PASS (16/16 terminal Stage3, E4/E5 0, four integrity invariants 0) and V1-B 64×50 smoke natural exit. V1-A/B/R dual-seed training/eval completed: 18 accepted rows / 288 terminal episodes have true Stage3→4 0/288 and all four invariants zero. A/B hinge Δ max ≤0.002201 rad with zero stable unlatch; R reward port is behaviorally active at step750 (stable unlatch R0 13/16, R1 2/16), but R0 hinge Δ max 0.100607 rad remains below 0.25 and R1 is baseline scale. Two pre-batch1 construction-guard root fixes landed; final A/B/R contracts fail fast. The preregistered negative statement was not triggered.
- 2026-08-05 00:20 HKT - R17 repair complete: helper attempt-label threading + Attempt20 enumeration classification + runner Attempt20 support + lifecycle-signal receipt + Attempt19 PROBE_INVALID receipts + focused tests (152 passed)。R17 receipt sha `73d0e218…`。
- 2026-08-05 00:20 HKT - Attempt20 executed: admission PASS (R17 fix validated at runtime), anchor FAIL (BASE_RELIEF_DISPLACEMENT_LIMIT, zero proof samples)。scientific_verdict_consumed false。Receipt sha `b1b2fa0d…`。
