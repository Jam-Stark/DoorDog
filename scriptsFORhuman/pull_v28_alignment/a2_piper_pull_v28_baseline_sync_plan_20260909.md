# Pull 分支 v28 baseline 同步计划：与主线共享新 asset、新姿态、相机合同与 harness，在新底座上重建双侧 pull 链路

日期：2026-09-09 HKT
状态：`PLAN_FROZEN_NOT_IMPLEMENTED`
适用仓库：pull 训练机 m5（`baoquanc@m5.precognition.team`，4×RTX 3090 24 GB）上的 `/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`，分支 `codex/a2-piper-pull-v0-20260803`，核对 HEAD `025ce28`。
主线对应文件：`scriptsFORhuman/v28/a2_piper_base_v28_plan_20260909.md`（以下称"主线 v28 plan"），其 §1 决策记录对 pull 同样有效，除本文件 §3 明列的 pull 侧差异。
上游：`scriptsFORhuman/pull_task/a2_piper_pull_v7_stage_plan_20260909.md`、`scriptsFORhuman/pull_v7/P2_HANDOFF_20260909.md`、`scriptsFORhuman/pull_v26_8/a2_piper_pull_v26_8_backbone_closure_20260908.md`。
canonical 副本：pull 分支 `scriptsFORhuman/pull_task/a2_piper_pull_v28_baseline_sync_plan_20260909.md`（Owner 提交并推送后训练机可见）；主线镜像在 `scriptsFORhuman/pull_v28_alignment/`。

本文件是 pull 分支 v28 的 authority。与 pull 当前 source / resolved config 冲突时以 source 为准并回报；与主线 v28 plan 冲突时以主线 plan 为准，除 §3 差异表。

---

## 0. 结论与范围

### 0.1 定位

pull 分支与主线在 v28 之后必须共享同一套"基础设施"：robot asset（含腕机塔架碰撞 link）、PiPER reset 姿态、动作语义、A2_Base、三相机几何合同与 camera-aware reward bundle、评估合同字段、harness 纪律。这些在两分支之间以 **byte-identical 文件 / 同一 patch** 交付，不允许 pull 侧自行重生成或改写。pull 自 Stage3→4 起的物理分叉（Stage4 子阶段 A–D、E 事件、send-past-body 收益、10 项 release-ready 门、tensile proof）全部保留。

在新底座上，pull 需要**从零重建**已在 v26-8 上建立的双侧 unlatch→opening（`PULL_OPENING_BILATERAL@5250`），然后在同一底座上继续 v7 登记的 P3–P5（release-ready → 送门过身 → 通行 → E7）。主线 D-17（累积臂目标夹紧）已于 2026-09-09 获 Owner 批准并在两分支同时开启，v7 P2 的处理变量 D2（越界惩罚）因此不进入 pull v28 配方；P2 的 natural 评估仍要先完成并封存，作为 posture trap 的诊断证据，不再路由 pull v28。

### 0.2 non-goals

- 不合并主线分支（不 `git merge`），不整文件覆盖 `door_open_a2_base.py`；共享项以文件级（asset、robot yaml、`delta_action_base.py` patch、测试）与函数级（两个 reward 函数、telemetry）移植。
- 不改 pull 的 E 事件定义、release-ready 门、Stage4 子阶段语义、send-past-body 收益数值。
- 不引入 BC/Teacher、旧 override actor、release-mode 观测。
- 不做 pull 相机渲染（无 Student lane）；相机进入 pull 只作为几何合同（塔架碰撞、姿态、telemetry），保证 push/pull 合一时（N-03）行为已在同一硬件约束下形成。
- 不做 hardware。

### 0.3 三个问题

| 问题 | 内容 | 阶段 |
|---|---|---|
| Q_P0 | v7 P2 的 D2 读数是什么（诊断封存） | P2 closure |
| Q_PG | 共享基建在 pull 仓库与 m5 上是否成立（asset/姿态/夹紧/reward/harness 的静态与 smoke 门） | G0 |
| Q_PS | 新底座上 from-scratch 是否重建双侧 unlatch→opening，且 release margin 结构性缺口是否消失 | Wave P-A |

---

## 1. m5 与 pull 仓库现状（2026-09-09 18:30 HKT 只读核对）

- 进程：无训练/评估进程；GPU1/2/3 空闲；GPU0 被外部 LightNav 服务占用约 14.5 GB（不处置）。tmux 只有一个无关会话。
- v7 P2：T_S1/T_S2/C_S2 三格 9001→10500 训练已于 09-09 11:18–11:22 完成（exit 0/0，峰值 16.5 GB），checkpoints 9250…10500 齐全；**里程碑评估 9500/10000/10500 一次都没跑**，`eval_p2_cell.sh`/`analyze_p2.py`/`watch_p2.py` 从未在真实产物上执行；receipts 仍是 `RUNNING` 未 finalize；C_S1 补跑未启动。前一执行团队在回传前被终止，`P2_HANDOFF_20260909.md` 是磁盘实况交接。
- 未提交改动：`door_open_a2_pull.py`（+62 行 D2 reward 方法）、`pull_v7_p2_T_S1/S2.yaml`、`scriptsFORhuman/pull_v7/`、两版 v7 plan、memory 三文件与 `_index.json`、`.codex/config.toml`；`gr00t/rl/data/robots/a2_piper_vpiper_final_20260906/` 已拷贝（未跟踪，无塔架 link）。
- 共享文件同一性（sha256，主线 `bbd98db` 对 pull `025ce28`）：`delta_action_base.py`、`config/robot/A2_Piper/a2_piper.yaml`、`scripts/smoke_a2_base_flat_walk.py`、`data/policies/A2_Base/policy.pt` **相同**；`a2_base.py`、`staged_task_base.py`、`legged_robot_base.py`、`isaacsim.py`、`door_open_a2_base.py`（pull 25,694 行 / 主线 30,052 行）**已分叉**。
- 观测/动作合同：两分支 actor/critic 均为 133/138 维、action 19（v26-8 迁移文档写的 135/140 是旧值）；默认姿态两分支同为 `[0,0,0,0.25,0.5,1.57]`；`delta_action_scale 0.3`、`delta_action_clip 15`、`action_scale 0.25` 相同。
- v7 P0/P1 结论（INSPECTED）：release-ready 全为 0 的唯一结构性缺项是 workspace margin ≥0.07 从未满足；机制是累积臂目标 clip ±3.75 rad 超过关节半程、默认姿态坐在 j2/j3 限位、`limits_dof_pos` 按 q 封顶，形成零梯度平台（j3 target 钉在 +3.75，Stage1 起 99% 步越界）。这与主线 v27 trace 的 Stage5 j2/j3 被饱和积分器钉在限位是同一现象，是共享层缺陷。

---

## 2. 共享基建同步清单（S1–S8）

每项给出主线来源、pull 侧交付方式与 G0 判据。"byte-identical" 指两仓库同路径文件 sha256 相同，G0 把清单与 sha 写入 `source_lock`。

| ID | 项 | 主线来源 | pull 侧交付 | G0 判据 |
|---|---|---|---|---|
| S1 | robot asset：主线 2026-09-11 选定 **MERGED** 候选 `gr00t/rl/data/robots/a2_piper_v28_merged_20260909/`（mount 并入 trunk，28 native 刚体），含 `wrist_camera_tower` 固定 link（**140 mm / θ 38.76°** 的支架盒 + 外壳盒，带 inertial）、trunk 上 base 相机支架/外壳的**两布局并集**盒、重生成的 `a2_piper.usd` + `configuration/`、更新的 `validation/usd_import_readback.json` | 主线 v28 plan §4.2；主线 G0 产出后 SHA 冻结 | 整目录 rsync 自主线，**pull 不自行生成**；主线未交付前 pull 的 G0 只能做不依赖塔架的静态项 | 目录内全部文件 sha256 与主线 source lock 一致 |
| S2 | robot yaml：`gr00t/rl/config/robot/A2_Piper/a2_piper_vpiper.yaml`（`usd_file/urdf_file` 指向 MERGED、`default_joint_angles` j2/j3/j4/j5 = 0.10/−0.10/0.0/**−0.415**、`body_names` 28 含 `wrist_camera_tower`） | 主线 v28 plan §4.1 | byte-identical 拷贝；pull 的 `/robot:` 选择改为 `override /robot: A2_Piper/a2_piper_vpiper` | sha 相同；CPU compose 后 `robot.*` 与主线 SC 合同的 robot 段逐键相同 |
| S3 | reset 姿态与动作零点：`[0,0.10,−0.10,0,−0.415,1.57]`（D-03/D-03a/D-35） | 主线 v28 plan §5.1 | 随 S2 生效；pull 的 Stage0 归零、`a2_stage0_arm_default_max_deviation` 等相对默认定义不变 | `test_a2_v28_config_contract_default_posture` 在 pull 通过 |
| S4 | 累积臂目标夹紧 `delta_action_clamp_to_dof_limits`（D-17，已批准） | 主线 v28 plan §5.1a；`delta_action_base.py` 两分支当前 byte-identical | 同一 patch；pull 配置置 true | `test_a2_v28_delta_action_clamp_to_limits` 通过；键缺失 bit-identical |
| S5 | camera-aware bundle：`penalty_a2_wrist_motion_l2`（+两张 6×3 权重表）、`penalty_a2_wrist_tower_contact`、释放后姿态回位项 | 主线 v28 plan §6 | 函数级移植到 `door_open_a2_pull.py`（或 pull 的 base 类），公式与主线纯函数逐字相同、共用同一 CPU 测试文件；**pull 侧权重与门控差异见 §3** | 纯函数单测在两仓库产出相同数值；pull 侧权重表按 §3 冻结 |
| S6 | 评估合同字段：主线 `v28_reduce.py` 的相机/塔架 telemetry 字段（§6.4）追加进 pull reducer；`++experiment_dir` 评估不写训练 root；trace 只对 `max_stage ≥ 2` 强制；stdlib `json.load` | 主线 v28 plan §6.4、§7 | 追加到 `scriptsFORhuman/pull_v26_8/reduce.py` 的后继 `pull_v28/reduce.py`；pull 的 K5/E2–E7 与 4A/4B 指标、margin/overshoot 中介全部保留 | reducer 合同文档更新；CPU 测试 |
| S7 | harness 纪律：watcher 对已就绪格独立推进；GPU 按实际余量选择并写入 receipt（m5：GPU0 外部占用）；receipt 显式环境；`P0_ASSETS` preflight；reducer `INVALID` 不自动停训练；policy 读数前失败自主 relaunch ≤2 次 | 主线 v28 plan §9；pull 已有 `pull_v26_8/{orchestrate.sh,runner.py,verify.py,watch_wave*.py,p0_assets.py}` 与 `pull_v7/watch_p2.py` | 在 pull 现有脚本上修订为 `scriptsFORhuman/pull_v28/`，不复制主线脚本（两边路径/receipt 机制不同） | 与主线相同的四个 harness CPU 测试 |
| S8 | A2_Base：保留当前 `policy.pt`（两分支 sha 相同）；G0-L 步行门在 m5 上用新 asset 跑一次 | 主线 v28 plan §5.2 | 同一 `smoke_a2_base_flat_walk.py` 扩展（文件当前 byte-identical） | 0 摔倒/64 env；|e| p50 ≤ 旧 asset 基线 ×1.15 |

主线 G0 完成前 pull 可先做的：S3/S4（patch 与测试）、S5 的函数移植与单测、S6 reducer、S7 harness、P2 closure（§4）。S1/S2/S8 等主线交付。

---

## 3. pull 侧差异表（相对主线 v28 plan）

| 项 | 主线 | pull | 依据 |
|---|---|---|---|
| Stage3→4 及之后语义 | 单一 Stage4 + release latch 1.2 rad + Stage5 through | Stage4 子阶段 A retreat/B send-past-body/C release/D through；E4–E7 事件；10 项 release-ready；`clean_release`；Stage4→5 要求 E6 | pull v6/v7 文档；不改 |
| `penalty_a2_wrist_motion_l2` Stage4 权重 | Wv (1,1,1) | **Stage4 子阶段 B（arm-dominant send-past-body）是任务必需的大幅臂运动**：Wv 在 Stage4 取 (0.5,0.5,0.25)，Wr 同主线；Stage3 j6=0 同主线；Stage0/1/2/5 同主线 | 待 G0 用 pull step9000 trace 的 4A/4B 段校准（同主线 §6.3 方法，目标 10–20% 收入占比） |
| 释放后姿态回位项 | `penalty_a2_stage4_arm_default_pose_l1` 门控 `release_gate ∧ ¬both_contact` | 门控 `release_event ∧ ¬both_contact ∧ stage ∈ {4C,4D}`（pull 自己的 release 事件缓冲），scale −0.5 | pull `door_open_a2_pull.py:5861-5951` 的 release 链 |
| `penalty_a2_wrist_tower_contact` | −1.0 全 stage | 同主线 | 塔架损坏风险与门类型无关 |
| 门域 | mass 80–120，friction off，`a2_v26_door_open_lr=bilateral` | 沿用 pull 当前 `pull_v26_8_backbone_common` 的门域与 `a2_door_open_lr_distribution` | pull 迁移 plan §3 |
| env 数 / 预算 | 4096 env，6000 batches | 1024 env（3090 24 GB；峰值 16.5–18.6 GB），6000 batches（v26-8 双侧 opening 出现在 5250）；≈22 s/batch → ≈37 h/格 | pull v26-8 与 v7 receipts |
| GPU | 0/1 评估、2–7 训练 | GPU1/2/3 训练；评估放在 P_S2 系格所在 GPU 且空闲 ≥5 GB，或格结束后；GPU0 外部占用不使用 | P2 合同 eval 放置规则 |
| 观测 | 133/138 | 133/138（相同） | 训练日志 `algo_obs_dim_dict` |
| 资格认定 | exact128 DEV/CONF | 不做 Teacher 资格；endpoint 用 exact64/侧 natural（pull reducer 口径） | pull 无 Teacher/Student 产出 |
| 相机 telemetry | FK 计算，进 reducer | 同主线（同一 mount JSON `U3_F45_B15`） | 合一前提 |

---

## 4. 第一步：v7 P2 closure（不改合同，只补评估与封存）

- 对 T_S1/T_S2/C_S2 的 9500/10000/10500 各做每侧 exact64 natural（`eval_p2_cell.sh`，共 18 lanes × ≈12 min；两 GPU 并行约 2 h），运行 `analyze_p2.py` 出 P2 中介（overshoot、margin、有余量 B 步、ready/clean）与保留能力（K5/D/E4/E5、4A/4B）。
- finalize 三个 receipts；写 `scriptsFORhuman/pull_v7/P2_CLOSURE_<date>.md`：按 v7 plan §4.4 给 typed 读数（`P2_MARGIN_LIFTED / P2_OVERSHOOT_ONLY / P2_NO_EFFECT / P2_RETENTION_LOSS`），但**不再触发 §4.5 的任何下一单变量**；C_S1 补跑取消（预算释放给 pull v28）。
- 预注册：P2 读数只作 posture trap 的诊断证据；D-17 已批准，pull v28 配方不带 D2。D2 方法 `_reward_a2_pull_v7_arm_target_overshoot_penalty` 保留在源码中但 scale 不出现在 v28 配置（注册表丢弃缺失键，路径 bit-identical）。
- 旧 asset 上的 P2 checkpoints 不在新 asset 上评估（v7 plan §4.6 规则 1 保持）。

---

## 5. G0（pull 侧）

| ID | 内容 | 判据 |
|---|---|---|
| PG-1 | S1/S2 落地：sha 与主线 source lock 一致；pull `isaacsim.py`（已分叉）中 body/dof 选择路径核对为按名称 `find_bodies(..., preserve_order=True)`，`num_bodies` 断言对 28 名成立 | 静态 + 断言 |
| PG-2 | S3/S4 patch 与测试；pull 的 `resting_dof_pos`/`penalty_unused_dof_deviation_l1` 保持 0 | CPU 测试 |
| PG-3 | S5 函数移植：`penalty_a2_wrist_motion_l2`、`penalty_a2_wrist_tower_contact`、释放后回位项；§3 权重表用 step9000 trace 校准并冻结；键缺失 bit-identical | CPU 测试同主线 |
| PG-4 | 扁平冻结 `pull_v28_common.yaml`（继承点为 `pull_v26_8_backbone_common` 的 resolved 合同，方法同主线 D-15：CPU compose-diff 对 Wave2 P_S2 resolved config，差集 = allowlist：asset、robot 段、姿态、S4 键、S5 键、seed/标签） | compose-diff 通过 |
| PG-5 | LEFT 镜像 G1 口径重跑一次（新 asset）：LEFT 目标偏 180°±0.05°、RIGHT bit-identical、all-RIGHT no-op | 同 v26-8 G1 |
| PG-6 | 256 env × 5 batch smoke（新 asset、新姿态、bundle）：body 计数、`contact_sensor.num_bodies`、reset 零指令 50 步 `arm_body0`/`wrist_camera_tower` 接触力 <1 N、两项新 reward 在日志中出现且 C 格不出现、`Mean episode rew_*` 表完整 | 同主线 R1–R3 |
| PG-7 | S8 步行门（`smoke_a2_base_flat_walk.py` 扩展版，新 asset，64 env） | 同主线 G0-L |
| PG-8 | harness：`pull_v28/{contract.py,verify.py,orchestrate.sh,run_cell.sh,eval_cell.sh,reduce.py,watch_wave.py}` 与四个 CPU 测试；receipt 含 GPU 余量快照 | 测试通过 |

---

## 6. Wave P-A：新底座 from-scratch 重建（Q_PS）

- cells `PA_S1/PA_S2/PA_S3`（seeds 1/2/3，`a2_v26_side_permutation_seed` 同值）：`checkpoint: null`、`full`、1024 env、6000 batches、save 250、milestones 1500/3000/4500/6000 各双侧 exact64 natural（pull reducer 口径 + S6 字段）。GPU1/2/3。
- 可选 G1 warm probe（与主线 §8.1 对称，1 格 500 batches ≈3 h）：源 `wave2/train/P_S2/model_step_009000.pt`，`policy_only` + RMS；`WARM_PASS` ⇔ 双侧 K5/D/E4 ≥ 40/64 且 overshoot 中介为 0（S4 开启时自然为 0）且塔架接触 ≤2 → 追加一个 warm arm 替换 PA_S3；否则三格全部 scratch。默认不做 G1（posture trap 使旧策略处于坏盆地，收益预期低），除非 Owner 要求。
- 路由（endpoint 6000）：
  - `PULL_V28_OPENING_ESTABLISHED`：≥2/3 seed 两侧 K5/D/E4/E5 ≥ 60/64 且塔架接触事件 ≤2/64/侧；
  - `PULL_V28_OPENING_UNSTABLE`：1/3；
  - `PULL_V28_OPENING_NOT_ESTABLISHED`：0/3。
  - 独立并列标签 `MARGIN_TRAP_RESOLVED / PERSISTS`：E5 后 release margin ≥0.07 的步份额 >0 且逐关节 target overshoot 中位 = 0（S4 开启）→ RESOLVED；否则 PERSISTS 并把该读数交给 D-17 的重审。
  - 相机行为标签同主线 `CAMERA_MET/PARTIAL/UNMET`（report-only）。
- 硬件反馈分支同主线 §8.2：RIGHT 侧失败伴随塔架接触 → 升级 X-01。

---

## 7. Wave P-B：P3–P5 在新底座上继续（登记，不冻结矩阵）

以 Wave P-A 的 `ESTABLISHED` seed 为来源，按 v7 plan §5 的决策点逐步推进：P3 B→C 联合 ready（候选单变量：hold 收益停付阈值 1.60 与 ready 1.134 的错位、clearance、handle-Y、hinge 速度；每次一项 + 同批 C）；P4 送门过身→通行（先核 Stage4 剩余时间容纳 clean→E6 的 382 步）；P5 E7/complete。每步单变量、同批对照、预注册判据，另出 addendum。若 `MARGIN_TRAP_RESOLVED` 已成立，P3 的第一变量直接取分侧缺项，不再讨论 margin。

---

## 8. 自主决策权（继承主线 §9，m5 特化）

- 同主线 §9.1–9.4、9.9。
- GPU：只用 GPU1/2/3；启动前核实 ≥20 GB 空闲且无外部进程；评估 ≥5 GB 且不与 18 GB 级训练格同卡；GPU0 的外部服务只记录。
- 预授权本地 commit 点（pull 分支）：P2 closure 后；G0 通过后；Wave P-A endpoint 后；closure 后。不 push。
- 必须等 Owner：改 E 事件/ready 门/Stage4 子阶段语义；超出预算（P2 评估 + G0 smoke + 3×6000 + 可选 G1 500 = 18,500 batches 上限）；硬件。

---

## 9. 资源与时间（m5）

```text
P2 closure : 18 lanes × ≈12 min（两 GPU 并行）≈ 2 h
G0         : CPU 为主 + 256 env 5-batch smoke + 步行 smoke ≈ 40 min GPU
Wave P-A   : 3 × 6000 batches × ≈22 s ≈ 37 h/格（计划 42 h），三格并行；4 milestones × 6 lanes ≈ 5 GPU-h
可选 G1    : ≈ 3 h
```

---

## 10. 文档与 memory

- 新建 memory entry `memory/a2-piper/pull-v28-baseline-sync/{description,TODO,DONE}.md`；`pull-lr-full-stage` 在 P2 closure 后置 `closed_p2_diagnostic`，其 `source_of_truth` 精简为 v7 P2 closure 与本文件（现有 60+ 条 logs 路径迁到 DONE 附录）。
- 决策日志与待办登记：复用主线的 `V28-D-*`/`X-*` 编号并加 `P` 前缀（`V28P-D-*`），双向同步表放在两分支的 plan 目录；主线 `a2_piper_longterm_TODO.md` A 表登 `PULL-02 v28 baseline 同步`。
- 每 milestone readout 与 `wave_pa_decision.json` 同主线 schema；同步清单 S1–S8 的 sha 表进 closure。

---

## 11. Owner 需提供 / 决定

1. ~~D-17~~ 已批准（2026-09-09 18:40）。
2. 主线 G0 产出的 S1/S2 文件（asset 目录 + robot yaml）如何交付到 m5（建议：主线第一个 commit 点后由 Owner 在 pull 分支复制并推送）。
3. 本文件与 P2 handoff 一起提交到 pull 分支并推送；同时把主线参考件（主线 v28 plan、deferred register、`planner_evidence_20260909/policy/REPORT.md`、`camera/REPORT.md`、`camera/variants/U3_F45_B15.json`）放到 pull 分支 `scriptsFORhuman/pull_v28/mainline_reference/`。

---

## 12. 结论边界

pull v28 对 Q_PS 给 experiment 证据（1024 env、3 seed、单门域）；不构成 E7/complete 的能力声明，不构成 hardware 证据；push/pull 合一（N-03）的前提是两分支在同一基建上都建立 opening，本文件只完成 pull 侧这一半。
