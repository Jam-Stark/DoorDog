# TODO

- 2026-09-04 00:01 HKT - Owner 已授权两次本地 commit（v26-6/v26-7、v26-8；不 push）及 plan §13
  G1 r2 relaunch。下一步按冻结顺序执行 r2 source/contract lock → `P0_ASSETS` → GPU0 G1；若 G1 PASS，
  不再等待审批，立即启动 Wave 1 六格。旧失败 root/receipt 不得覆写。
- 2026-09-03 21:59 HKT - **v26-8 已在 G1 fail-fast 后关闭并交回 Owner**。G0 为
  `STATIC_PASS/TEST_PASS`；首次 K_S1 smoke 因远程 `default_environment.usd` 无法打开而在 scene
  construction 非零退出，未到 policy load/step。按冻结合同不得重跑；Wave 1/milestone/endpoint/Wave 2
  均为 `NOT_RUN`。若 Owner 后续决定重试，必须明确授权新的 run/output root；不得覆写本次 failure artifact。
- v26-7 已关闭：不重跑、不改 endpoint；S0 LEFT discovery（Stage2→3 悬崖）留给 v26-9 候选。

- 2026-08-31 20:05 HKT - v26-3 的 `ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE` 已被
  v26-6 Wave A 推翻，**不再作为禁止改 gripper effort/gain 的依据**；v26-4/v26-5 handoff
  中"不移植 45N/kp1300"的措辞同样失效（45N/1300/32 是本仓库 v18–v25 的 push 基线，
  不是 pull-only 移植）。
- 待批准 Wave B：从 `CONT_STEP2000` 用 `GRIPPER_CAPABILITY_BUNDLE` 双 seed 重训并做
  全 checkpoint 双侧 exact64 natural eval。
- 待批准 Wave C（条件）：durable 下压成立但 hinge 仍停在 `<0.1` 时，启用 pull-v2-W 的
  `a2_stage3_unlatch_near_closed_hinge_threshold: 0.1 -> 0.25`。
- Stage2→Stage3 `-0.093/step` 收入悬崖与 `push_door_hinge + hold_and_drive` 仅
  `0.0090/step` 的定价，属独立 axis，需单独设计。
- LEFT 侧无下压行为，属 v26-4 `BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET`，需独立处理。

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
- 2026-08-28 03:25 HKT - v26-3 canonical stage已完整关闭为
  `v26_3_complete_not_admitted`，不需重跑当前M0/M1矩阵。四格750与32组natural
  exact64均PASS，最终为`MONOTONE_CREATION_SEED_OR_SIDE_UNSTABLE`：M1两seed的
  RIGHT creation为8/64、13/64，LEFT均0。
- F已关闭为`ACTUATOR_CAPACITY_NOT_CAUSAL_AT_TESTED_RANGE`并保留10/10；P因canonical
  axis-work signal不可识别而`NOT_RUN`，W因未形成bilateral creation/未访问wall而
  `NOT_RUN`。不要在本阶段追加effort、friction、hook、threshold、降K5或relay sweep。
- 所有natural goal为0，Teacher exact128 holdout未准入；manifest与Student G7 binding
  保持不变。只有未来新plan先解决LEFT creation不稳定并满足双seed双侧repeated full
  goal，才重新评估Teacher gate。
- 后续若Owner另开阶段，应以v26-3 RIGHT-positive/LEFT-negative的matched trace作为新的
  side-asymmetry因果起点；本memory不预授权新的reward/actuator/physics预算。
- 2026-08-28 21:24 HKT - v26-4已完成且无需重跑：K admitted为冻结Stage3匹配网格
  LEFT `9/9` reachable、RIGHT `9/9` first reject，唯一首拒为`arm_j4` upper-limit
  overshoot（`0.003046–0.039405 rad`）；C ceiling为
  `BILATERAL_FOUNDATION_REQUIRES_ASYMMETRIC_POSTURE`，
  canonical identity `NOT_RUN`，M四格与metrics `NOT_RUN`，Teacher/Student不变。
- 未来若继续，必须先建立独立、预注册的non-mirror posture-discovery新plan，再由证据
  冻结side-conditioned posture；本entry不预授权该probe、canonicalization、URDF limit、
  reward/threshold/actuator/physics变更或C0/C1 GPU矩阵。
- 2026-08-29 06:48 HKT - v26-4 R2已关闭，无需重跑：K corrected geometry/FK mirror
  为`BILATERAL_ASYMMETRIC_IN_ACTION_OFFSET`，C canonical identity CPU/static PASS、
  C1 runtime smoke PASS，C0/C1×seed0/1四格训练与32组exact64 bilateral eval完成。
  reducer终态为`CANONICALIZATION_NOT_SUPPORTED`（step750 C1 prereg bands不通过，
  seed1未达三指标strict improvement）。orientation audit的side-independent target
  offsets进入v26-5；不得把v2 max-handle与v3 high-water的不同exposure semantics当作
  integrity failure，也不增加本阶段训练/硬件预算。
