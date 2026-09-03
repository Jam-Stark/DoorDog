# `base_v26-7` step3000 goal 异常只读核查附录

时间：2026-09-03 HKT  
状态：`INSPECTED + artifact-derived`  
路由边界：本附录不修改 v26-7 预注册矩阵、阈值、endpoint 或 reducer 结果。

## 1. 触发读数

step3000 的 Q05 endpoint 已由 durable depression 按预注册 §6.1/§6.2 冻结；另有一个
不参与路由、但相对 v26 历史基线反向的读数需要定性：

| cell / side | durable | Stage5 | `terminal_reasons == complete` | arm_j4 限位驻留 |
|---|---:|---:|---:|---:|
| Q05_S1 LEFT | 62/64 | 62/64 | 62/64 | 31.511620% |
| Q05_S1 RIGHT | 64/64 | 18/64 | 4/64 | 0.2447% |
| Q05_S2 LEFT | 60/64 | 0/64 | 0/64 | 0.0110% |
| Q05_S2 RIGHT | 57/64 | 21/64 | 0/64 | 0.4506% |
| Q05_S0 LEFT / RIGHT | 0/64 / 64/64 | 0/64 / 0/64 | 0/64 / 0/64 | 0% / 0% |

`goal_episodes` 是 reducer 对 terminal string 严格等于 `"complete"` 的计数。冻结计划
§8 明确规定 v26-7 不构成 Stage4、Stage5 或 goal 证据，因此本读数只能作为非路由异常。

## 2. 控制源与完整性

控制源是冻结的 Q05_S1 step3000 LEFT/RIGHT：

- `metrics_eval.json`
- `a2_v14_per_env_records.json`
- `stage2_5_step_trace.json`
- `.hydra/runtime_config.yaml`
- 当前实际执行的 staged-task 与 DoorPregrasp source

两侧均为 exact64 first episodes。LEFT/RIGHT trace 分别有 `44,793/46,590` 行，各覆盖
64 个 env；每个 env 从首个落盘 row 到 terminal row 的 `step_index` 连续，且恰有一个
`complete` 或 `stage_overtime` terminal row。terminal row 满足
`episode_length_buf == step_index + 1`，并与 per-env record 的 goal/max-stage/final-stage 对齐。

重算 terminal reasons：LEFT `complete=62, stage_overtime=2`；RIGHT
`complete=4, stage_overtime=60`。

## 3. `complete` 实际判据的镜像审计

实际执行路径为：

1. `StagedTaskBase` 按六个 stage 动态绑定 `_stage_5_to_complete_condition`；
2. 即时完成谓词为 `stage_buf == 5`、`episode_length_buf >= 2`，并且
   `robot_root_states[:, 0] - env_origins[:, 0] > 1.5`；
3. 当前 `reset_on_complete=true`、`reset_on_complete_delay=50`，terminal reason
   `complete` 还要求 delay 后当前 root-X 谓词仍为真；
4. hinge 与 handle 不在 Stage5→complete 的直接谓词中。它们只在此前 Stage4→5
   入场时要求 `root_x_rel > 0`、hinge `> 1.0472 rad`、handle `< 0.2 rad`；
5. `target_root_pos` 仅用于 Stage4/5 reward 与 telemetry，不进入 complete 判据。

LEFT/RIGHT door root 都位于 env-local `(0,0,0)` 且为 identity/fixed-root；handedness 是
door-local `y` 镜像，完成线沿共同的 door-local `+x`，所以 root-X 阈值无需乘
`doorOpenLR`。LEFT hinge joint frame 通过 `180° about X`、RIGHT handle joint frame通过
`180° about Z` 将两侧正 joint coordinate 规范化为相同物理语义；两侧 hinge/handle limit
也相同。因此 Stage3→4、Stage4→5 的正 hinge/handle scalar 判据不应再做一次符号翻转。

静态 verdict：`PASS_NO_MIRROR_DEFECT_FOUND`。未发现 complete、Stage4→5 或其关节坐标
存在 LEFT 判据线漏镜像。需要保留的语义边界是：terminal complete 不重新检查 hinge/handle，
只要求已经进入 Stage5、root-X 当前越线并满足 delay。

主要 source：

- `gr00t/rl/envs/base_task/staged_task_base.py:58,246-276`
- `gr00t/rl/envs/door/door_open_a2_base.py:28816-28867`
- `gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py:1817,1976-2016`
- `gr00t/rl/isaac_utils/playground/env_rand/door.py:521-577`
- `scriptsFORhuman/v26_7/v26_7_reduce.py:157`

## 4. complete terminal 的实际开门量

单位为 rad，p50/p95 为 nearest-rank；signed 与 absolute 相同，因为所有 complete
terminal hinge 都为正。

| side | n | hinge min | p50 | p95 | max | terminal `root_x_rel > 1.5` |
|---|---:|---:|---:|---:|---:|---:|
| LEFT complete | 62 | 1.451306 | 2.227745 | 2.513293 | 2.591353 | 62/62 |
| RIGHT complete | 4 | 1.541534 | 1.700604 | 2.036075 | 2.036075 | 4/4 |

LEFT 只有 1/62 个 terminal hinge 低于 RIGHT complete 的最小值 `1.541534`，该样本仍为
`1.451306`，明显高于 Stage4→5 的 `1.0472` 门槛；其余 61/62 均更高。不存在 LEFT 在
系统性更小的实际开门量上提前判 complete 的证据。

数据 verdict：`PASS_NO_THRESHOLD_EVIDENCE`。

## 5. arm_j4 限位驻留与 complete 时刻

限位严格按报告口径 `abs(1.745 - arm_j4) < 1e-3`。

| LEFT stage | limit steps | trace steps | stage 内占比 |
|---|---:|---:|---:|
| Stage2 | 0 | 975 | 0% |
| Stage3 | 0 | 6,759 | 0% |
| Stage4 | 13,445 | 29,846 | 45.0479% |
| Stage5 | 670 | 7,213 | 9.2888% |
| 全部 | 14,115 | 44,793 | 31.511620% |

`13,445/14,115 = 95.253%` 的限位步发生在 Stage5 之前，只有 4.747% 在 Stage5。
62 个 complete episode 全部曾有过限位步，两个 stage-overtime episode 都没有，说明二者
在 episode 粒度上同现；但时序不支持“限位触发 complete”：

- 最后一次限位到首次 Stage5 `root_x_rel > 1.5` 的间隔
  `min/p50/p95/max = 34/50/64/229` step；首次越线 row 为限位的 episode 是 `0/62`；
- 最后一次限位到 terminal complete 的间隔
  `84/100/114/315` step；
- terminal row，以及 terminal 前 1、5、10、25 step 内仍有限位的 episode 均为 `0/62`。

因此 31.5% 是主要位于 Stage4 的行为相关量，不与 complete 判定时刻重合；当前证据不支持
“arm_j4 顶限位导致 LEFT 提前 complete”。

## 6. 对 step2000 confound 的更新

- Q05_S2 LEFT 在 step3000 达到 durable `60/64`，arm_j4 p95=`1.314685`、限位驻留仅
  `0.0110%`。这直接否定“LEFT durable 必然伴随 arm_j4 顶死”的必要关系。
- Q05_S0 LEFT 仍为 durable `0/64`，arm_j4 p95=`1.142730`、限位驻留 `0%`，从未接近
  `1.745`。LEFT zero 不是撞到行程末端后被挡回；证据落在“探索通路未被找到 / 当前
  Stage2→3 收入结构未使该通路出现”的分支。
- confound 转移到非路由的 goal 异常，但本次静态与数据核查均未发现 threshold/mirror artifact；
  Q05_S1 LEFT 的 `62/64` 应保留为真实落盘的 policy/trajectory-side 现象，而不是升级为
  v26-7 goal 能力结论，也不能从当前相关性推断 arm_j4 因果。

## 7. 冻结与结论边界

- Owner 已验收的 durable route 保持不变：Q05 以 step3000、Q20 以 step2000 为 endpoint；
- 本附录不给 goal 分配新 typed route，不改 reducer，不重跑，不追加预算；
- 不更新 Teacher/Student handoff 或 G7 binding；
- `v26_7_terminal_candidate_r1` 已由 Owner 以
  `REJECTED_PENDING_GOAL_ANOMALY` 拒绝；只有纳入本附录与 memory 定性后才能建立新的终态候选。

