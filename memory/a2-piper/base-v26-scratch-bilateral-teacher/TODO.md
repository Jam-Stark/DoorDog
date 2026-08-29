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
