# Pull v7 阶段方案（2026-09-09 修订版）：双侧 plain backbone 到达 goal

日期：2026-09-09 HKT。工作目录：`/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0`。
分支：`codex/a2-piper-pull-v0-20260803`；核对 HEAD：`025ce28`。

本版取代 [0908 版](a2_piper_pull_v7_stage_plan_20260908.md)。0908 版的 P0/P1 定义与产物全部保留并作为本版输入；本版改动的是 P2：把 P0/P1 已回答的"曝光缺口"追到动作积分器这一层，冻结一个处理变量，并把 v6 已验证的"送门过身"轨迹作为目标行为参照。

**状态：方案已落盘。Owner 已否决改动共享 backbone（原 D1），并同意先用 GPU1–3、C_S1 补跑。P2 处理变量改为 D2：pull 侧新增一个 reward 项惩罚 commanded 臂目标超出关节物理范围的量，动作语义与 push 保持一致。D2 的 scale 与四格预算待 Owner 最终确认；未启动新 GPU 任务、未改训练源码/config。**

## 0. 阶段目标

pull 分支目标：在 LEFT/RIGHT 门随机出现的条件下，同一个 plain LSTM actor 从 Stage0 自然出生到达 goal，即每侧 exact64 首 episode 中出现 `complete`/E7，并保留已建立的双侧抓握、解锁、opening。

目标分解为四段中介，每段只在前一段真实出现后才成为主变量：

```text
P2  臂姿态陷阱解除      -> B 阶段 margin 分布抬升、出现有余量 B 入口
P3  B->C 联合 ready     -> natural 出现 ready 窗口、clean release
P4  送门过身 -> 通行    -> persistence25、crossing、frame passage、E6
P5  whole-body clear    -> E7 / complete，两侧各 >=8/64 记 PULL_FULL_CHAIN_OBSERVED
```

本版只冻结 P2 的处理、对照与预算；P3–P5 只登记决策点与已知约束，不伪造矩阵。

## 1. 阻塞判断（P0/P1 + 源码核对）

证据等级：源码/配置 INSPECTED；数值来自 step9000 natural eval 与 P1 训练遥测的只读再分析；无新增实验。

### 1.1 release-ready 卡在哪里

- `release_ready = subphase==C ∧ pre_release_ready`；B→C 本身要求 `pre_release_ready ∧ ~capture`，C 失去 pre-ready 即退回 B；clean release 要求 `release_event ∧ prev_release_ready`。完整链路至少需要 pre-ready 连续 3 步并在其中开爪（`door_open_a2_pull.py:5861-5951`）。旧 env14 正是 B→C、ready、clean 三连步（trace 355–357）。
- pre-ready 是 10 项同步合取。当前 254 条 E5 轨迹（step9000）与 P1 的 13.1M transitions 里联合 ready 为 0，同一步最多过 7/10。
- **workspace margin ≥0.07 在所有轨迹、所有可观测步都不满足**（P0 §3），是唯一"结构性"缺项。其余缺项按侧别分布：hinge 速度 ≥0.15 rad/s 极少（2/6/11/0）；hinge ≥1.134 rad 在 P_S1 LEFT 仅 1/64；clearance ≥0.02 m 在 P_S2 LEFT 0/64；handle-Y ≤0.06 m 在 P_S2 RIGHT 0/64。
- margin 缺项的机制（config 与 P0/P1 数值逐项对上）：
  - 臂动作是累积增量：`d += 0.3·raw`，`d = clamp(d, ±15)`，`q_target = q_default + 0.25·d`（`delta_action_base.py:59-66`；resolved `delta_action_scale=0.3`、`delta_action_clip=15.0`、`action_scale=0.25`）。累积目标范围是默认角 ±3.75 rad。
  - `arm_j3` 默认角 0 是它的上限 0（范围 [−2.967, 0]）；`arm_j2` 默认 0 是下限；`arm_j5` 默认 0.5（范围 ±1.22）。默认姿态已坐在两个限位上，reset 时 d=0（`reset_delta_actions_with_backmap` 实际为空操作，`:149-152`）。
  - P0/P1 观测 j3 target=+3.75、j5 target=−3.25，恰为 `default ± 0.25×15`：累积状态已打死在 clip 上；Stage1 起 99.1%–99.8% 的步 j3 target 指向限位外（P1 上游表）。
  - 要恢复 j3 余量，策略必须连续输出负 raw 把 d 从 +15 推回 0 以下，中间约 50 步（|raw|≈1）里 q 一动不动、reward 无变化，顶限位的支撑力矩还会减弱。这是动作积分器造成的零梯度平台；它解释 P1 的"14,565 个自然 episode 里 j3 只恢复 17 次"和"有余量 B 步 = 0"。
  - `actions` 观测的臂 6 维就是累积 d（`a2_base.py:612`、`:786-796`），策略能看到饱和状态，但没有收益推动它回来。

### 1.2 策略是否得到可用信号与激励

- E5 后 B 阶段有密集正收益：`a2_pull_v6_arm_tangent_progress 12`、`arc_tracking 4`、`handoff_side_progress 24`、`handoff_hinge_momentum 12`，加 Stage3/4 hold 类 `both_contact/opposite_squeeze/squeeze_force_window/contact_stability` 各 0.5（hold 收益到 `a2_stage4_release_hinge_threshold=1.60` 或 Phase D 才停付，高于 ready 的 1.134）。P1 证实这些都有实际非零支付。
- 全部 release 链收益（`release_open_command_quality 96`、`clean_release_quality 30`、`post_release_*`）在 13.1M transitions 里 active 步数为 0：它们都在 ready 门后。B→C 有 `handle_side_bonus 30` 脉冲、C 阶段有 `hinge_momentum 4`，并且 `penalty_open_command`/`keep_close_command` 在 C 不生效（`:9413-9442`）。**到 C 的激励存在，缺的是可达性。**
- `limits_dof_pos −5`（乘 dt 后 −0.1）每步都付，但按实际 q 算越界：q 被 PhysX 压在硬限位，越界量封顶（j3 约 0.074、j5 约 0.061 rad），target 再外推不多付，回收到 d<0 前也不少付；且它只覆盖到 0.95 软限位，对应归一化 margin 0.025，到 0.07 之间没有任何梯度。
- `premature_release_penalty −12`：未 ready 松手被罚。综合结果："抓着门把摆到 Stage4 超时"是稳定局部最优。
- 训练路径没有夹爪强制闭合：`a2_forced_gripper_close_*` 只在 `base_eval.yaml` 且 `enabled:false`；`_step_a2_base` 中 primitive>0 即开（`a2_base.py:574-582`）。夹爪从未打开是策略行为。

### 1.3 release / crossing / E6 / E7 判据是否冲突

- 无循环依赖：ready 不要求 crossing 或 frame passage；E6 = prior E5 ∧ 正向 crossing 与速度 ∧ panel clear ∧ frame passage ∧ `clean_release ∧ persistence ≥25`（`:6574-6587`，25 为硬编码）；E7 = prior E6 ∧ 全部 body 越过门平面 1.5 m ∧ panel clear ∧ frame passage（`:6588-6593`）。Stage4→5 要求 E6（`:9800-9826`）。
- 冲突在激励层：B 阶段收益要求双指接触，ready 是 10 项合取，未 ready 松手被罚。不需要改 E 事件定义。

### 1.4 判断

阻塞点不在 release 语义，也不能归为"训练不够久"。它是一个上游姿态陷阱——默认姿态坐在限位、累积动作 clip 比关节范围宽 3.75 rad、限位惩罚封顶——叠加 B 阶段收益高原。旧 r6an 成功靠的是不同姿态（j3 在 −0.95 至 −2.6 rad 区间，E5 入口 margin ≈0.10–0.12、clearance ≈0.3 m），不是不同 reward 权重（P0 已比对 71 个非零权重相同）。

## 2. "送门过身"参照：v6 已验证的目标行为

v6 阶段把 Stage4 细分为 4A retreat/clearance、4B arm-dominant send-past-body、4C positive-velocity release、4D immediate through（`memory/a2-piper/pull-open-door-task/description.md:45`）。唯一 strict-natural 完整链路 `pull_v6_F0_r6an_seed3/model_step_000025.pt` 的 env14 时间线：Phase C 356、clean 357、K25 384、frame passage 620、E6 739、E7 1308、`complete`（[v6.1 population 报告](../pull_v6_1/PULL_V6_1_P_POPULATION_REPORT.md)）。natural64 口径 E5/clean/frame/E6/E7 = 41/5/3/2/1。

它对本版的价值与边界：

| 可参照 | 依据 | 不能照搬 |
|---|---|---|
| 目标轨迹形状：先退避取得 clearance，再以臂为主把门把送过躯干（`handle_send_y` 朝 −0.08），门角与正速度同时达标后一步松手，随后立刻通行 | v6 4A–4D 与 env14 trace；当前 reward 文件 `reward_pull_v6_send_past_body.yaml` 权重与 r6an 相同 | 旧 override actor、2 维 release-mode 观测、冻结 carrier |
| 执行 4B 需要臂有 workspace：env14 在 E5 入口 margin 0.122、E4→E5 期间从近限位恢复到 0.10 | P0 §2.3/§6 | 把 env14 单条成功当群体分布 |
| B→C 的瓶颈是"持续的 natural readiness 形成"而不是夹爪 release mean | v6.1 population 结论 | 再做 ratio/reward 扫描 |
| Stage4 集中曝光曾配合 E5 bank 产生过链路 | r6an 训练：256 env、99% Stage4 reset、专用 bank | 在没有高 margin 库存时直接提高 Stage4 ratio（P1 证明当前无库存可采） |

当前策略已部分表现出 4A/4B：`handoff_reached` 21–64/64、tangent share ≥0.6 在 58/21/64/36、`handle_crossed` 在 P_S2 LEFT 64/64（但 clearance 全程 <0.02 m，即送门时躯干贴着门板）。P2 起把 4A/4B 指标作为"保留能力"一并度量，不让 D2 换来 margin 却丢掉送门。

时间预算约束（P4 时再核）：Stage4 上限 250 步，`award_remaining_time_on_advance=true` 会把前段剩余时间累加（`staged_task_base.py:190-193`）；Stage4→5 要求 E6，所以 clean→persistence→crossing→frame→E6 必须在 Stage4 剩余时间内完成。env14 clean→E6 用了 382 步，其训练合同为 24 s/Stage5 300 步，eval 为 36 s/800。

## 3. 冻结基线（除 T 格新增 D2 一项 reward scale 外与 0908 版相同）

| 项目 | 固定值 |
|---|---|
| Actor / critic | 原生 plain RecurrentActor/RecurrentCritic，LSTM，133/138 维，native RMS |
| 策略来源 | P_S1、P_S2 各自 Wave2 step9000；P1 的 9050/9100 诊断 checkpoint 不作来源 |
| 几何与 plant | LEFT 抓握目标镜像开启；finger 45/45 N，Kp/Kd 1300/32，M39 开启 |
| 抓握能力窗口 | squeeze 0.5/30；over-force 55 |
| Gate / rewards / events | grasp_completion；现有 reward 权重与 E 事件语义全部保留；T 格仅追加 `a2_pull_v7_arm_target_overshoot_penalty=-1.0` |
| 训练 reset | `enable_staged_reset=true`，固定 `[0.5,0.1,0.1,0.1,0.1,0.1]`；两项 v6 bank 关闭 |
| Natural eval | `enable_staged_reset=true`，Stage0-only `[1.0,0,0,0,0,0]`；两项 v6 bank 关闭；核对真实首 episode 出生 trace；reducer 合同不变 |
| 时间尺度 | 0.02 s/control step；64 control steps/batch；1024 env |
| Full 加载限制 | 恢复 policy/critic/optimizer/scheduler/TrainerState；online reset 样本新进程重新积累 |

## 4. P2：单一处理 D2 与同期对照

### 4.1 处理变量 D2：pull 侧臂目标越界惩罚

定义（仅 `DoorOpenA2Pull` 新增一个 `_reward_*` 方法，不触碰 `DeltaActionBase`、`a2_base.py` 或任何共享类）：

```text
q_target_j   = default_dof_pos_j + action_scale · d_j          (d 为当前累积臂状态 self._delta_actions，已过 clamp 与 Stage0 归零)
overshoot_j  = max(0, q_target_j − u_j) + max(0, l_j − q_target_j)   (l/u 为 6 个臂关节硬限位，单位 rad)
raw          = Σ_j overshoot_j
reward_scales.a2_pull_v7_arm_target_overshoot_penalty = −1.0   (与其它项一样在 env 初始化时乘 dt)
```

- 全阶段生效，不加 stage 门：陷阱在 Stage1 形成（P1：Stage1 j3 target 指向限位外 99.1%–99.8%），Stage0 的 d 已被 `_apply_delta_action_overrides` 归零（`door_open_a2_base.py:7239`），自然为 0。
- 与现有 `limits_dof_pos`（按实际 q、0.95 软限位、slope 5/rad）构成单调的越界惩罚：目标进入范围前 slope 1/rad 作用于 target，进入范围后 q 越界部分由 `limits_dof_pos` 接管，两段之间没有零梯度区。它不改变动作映射、观测、actor、E 事件、reset ratios、默认角或 `delta_action_clip`。
- scale −1.0 的依据：当前四侧 E5 附近 overshoot 约 3.75（j3）+ 0–2.03（j5，P_S1 LEFT 的 j5 target 在范围内）≈ 3.75–5.8 rad，对应每步 −3.75 至 −5.8（乘 dt 前），与 B 阶段正收益合计约 +4.3/步同量级，低于 Stage3 的 `hold_and_drive 8`/`pull_door_handle 6`/`pull_door_hinge 6` 级别，不会压垮既有抓握/解锁收益。对策略梯度真正起作用的是斜率：一步 raw ±1 改变 d 0.3、target 0.075 rad，该改变持续存在，按 γ=0.9975 折现约 ×400，相当于一次 30（乘 dt 前）的回报差，足以被 PPO 捕获。`penalty_delta_action_rate −0.01·raw²` 与 `penalty_dof_acc` 仍在，限制策略用大幅负动作把 d 一步拉回。
- 加载时策略行为不变（reward 变、动作不变），critic 会重新拟合基线；这是 D2 相对结构 clamp 的优点。`actions` 观测的臂 6 维仍是累积 d，策略可以直接看到自己在减少 overshoot。
- 同期 C：完全不加该项（零 scale 的项在 `legged_robot_base.py:525-531` 被移除，因此 C 的 reward 路径与 9000 源 bit-identical；新增方法对 C 是惰性代码）。
- 允许的唯一重试：9500 门若 margin 中介已动而保留能力跌破 48/64，仅把 scale 改为 −0.3 重跑 T 格一次；不再扫更多值。

为什么不再选结构 clamp（原 D1）：把累积臂目标 clamp 到物理范围会让 pull 的动作语义与 push 分叉，合一时必须再统一，这个代价不应由当前阶段承担。`delta_action_clip=15` × `action_scale=0.25` = 3.75 rad 超过每个臂关节的半程，且实机 PiPER 对越界目标本来就会拒绝或截断，仿真里靠 Kp×3.75 的支撑力矩是实机不会有的——这是共享层的真实缺陷，登记到 push/pull 合一阶段对两侧同时处理，不在这里单侧修。

为什么不选其它方向：`workspace_margin_progress`（scale 不在 v26_8 lineage 里，属新增项）按 q 算，在平台区仍零梯度；改默认臂姿态不改激励结构会重新打死；放松 ready 门槛既不解决另外三四项缺项也削弱硬件安全含义；采样干预没有库存（P1）。

### 4.2 格与来源

| Cell | 来源 | 处理 | GPU |
|---|---|---|---|
| T_S1 | `wave2/train/P_S1/model_step_009000.pt` | D2 scale −1.0 | 1 |
| T_S2 | `wave2/train/P_S2/model_step_009000.pt` | D2 scale −1.0 | 2 |
| C_S2 | 同 P_S2 9000 | 原配置 | 3 |
| C_S1 | 同 P_S1 9000 | 原配置 | 补跑：首个格结束或 GPU0 空出后启动，与 T_S1 同 batch 数 |

`checkpoint_load_mode=full`，起点 iteration 9001；输出根 `logs_rl/a2_piper_pull_v7/p2_<date>/`，评估根 `logs_eval/a2_piper_pull_v7/p2_<date>/`。P1 已提供两来源各 100 batches 的原配置曝光遥测，但它不替代 C 的 natural 能力读数。C_S1 补跑期间，T_S1 的 9500 门先与 C_S2 及 P_S1 自身 9000 源读数比较，C_S1 到达后补齐同源比较。

GPU0 当前被其他用户进程占用（LightNav 服务，约 12 GB），本方案只用 GPU1/2/3，启动时按实际空闲核对，不从历史编号推定。

### 4.3 预算与时间

| 项 | 数值 | 依据 |
|---|---|---|
| 每 batch transitions | 65,536 | 1024 env × 64 steps |
| 每 batch 时间 | ≈22 s | Wave2 3000 batches 18 h 22 min |
| 准入门 | 9000→9500，每格 500 新 batches = 32,768,000 transitions，≈3.1 h | — |
| 继续上限 | 9500→10500，每格再 1000 batches，累计 1500 = 98,304,000 transitions，≈9.2 h | — |
| 四格合计 | 393,216,000 transitions，≈36.8 GPU 小时（不含启动与 eval）；前三格并行约 9.2 h 墙钟，C_S1 补跑另计 | 若 9500 门终止则四格共 131,072,000 |
| natural eval | 每侧 exact64 约 12 min、峰值约 3.8 GB；里程碑 9500/10000/10500 各 6 侧 | Wave2 eval receipt |

eval 显存：训练峰值 P_S1 系 18.6 GB、P_S2 系 16.5 GB。里程碑 eval 优先放在 P_S2 系格所在 GPU（合计约 20.3 GB），启动前核对实际空闲 ≥5 GB，否则排队等格完成；不在 18.6 GB 的格旁边跑 eval。

### 4.4 直接中介与判据（每侧 exact64 natural，分母 64，T 与 C 同批比较）

保留能力（每侧）：K5、D、E4、E5 各 ≥60/64；4A/4B 保留指标 `handoff_reached`、tangent share ≥0.6、`handle_crossed` 同批报告。

P2 直接中介（来自现有 trace 字段，P0 CSV 已含六关节 q 与 target）：

0. 逐关节 target overshoot 分布（Stage1–4 全程与 E5 后各一份）：这是 D2 直接作用量，C 的参照约 j3 3.75、j5 0–2.03 rad。
1. 六关节 release margin 的每 episode 最大值分布（中位、p90）；C 的参照值约 2.5e−4。
2. 有余量 B 步数（margin ≥0.07）与有余量新 E5 入口数；
3. j3/j5 实际 q 离开限位的首次 age 与比例；
4. 同一步通过条件数分布与"仅缺一项"窗口数；
5. ready 步数/episode 与 clean release 数（能出现即记录，不作为 P2 成功前提）。

判据：

- **9500 准入**：T 任一来源两侧 overshoot（0）明显下降且 margin 中介（1、2）相对同批 C 有可解释抬升（中位 >0.025，或有余量 B 步 >0），且保留能力未低于 48/64。满足则继续。overshoot 下降但 margin 不动，说明策略只是把 target 收到边界仍顶着限位，进入 §4.5 第一行；overshoot 本身不降，说明 scale 无法对抗既有收益，进入 §4.5 第三行。
- **10500 成功**：至少一个来源在 natural 出现 ready 窗口 >0（任一侧），并保留能力 ≥60/64；更强读数为 clean release ≥1。此时 P3 的中介切换为 §1.1 的分侧缺项。
- **停止**：NaN/异常/来源配置不符/Owner 停止；任一侧保留能力 <48/64 且 margin 中介无改善（9500 或 10000）；到 10500 绝对上限不自动延长，即使 ready 仍为 0。
- **不据以下判死**：单个来源失败；ready 出现但 clean 为 0；C 自身波动 ≤4/64。

### 4.5 D2 后的预登记分支（不同时运行）

| 读数 | 下一单变量 | 说明 |
|---|---|---|
| overshoot 降到 0 附近、margin 抬到 0.025 附近后停住，ready 仍 0 | `soft_dof_pos_limit` 0.95→0.86，使 `limits_dof_pos` 边界与 0.07 门对齐 | 改一个现有数值，不加新项；影响全部 20 关节，需核对腿部 |
| margin 分布跨过 0.07、有余量 B 入口出现，但 ready 仍 0 | 进入 P3：分侧缺项（hinge 速度、clearance、handle-Y）与 hold 收益 1.60 阈值 | 此时才允许提出下一个 reward 语义改动交 Owner |
| overshoot 不降 | scale −1.0 无法对抗既有收益；先核对 Stage1/2 哪一项收益在顶住 j3（pregrasp/grasp 距离项），再决定是否允许一次更大 scale | 需要新的诊断问题，不自动开新训练 |
| overshoot 降、margin 动，但保留能力 <48/64 | 唯一允许的重试：scale −0.3 重跑 T 格 | 见 §4.1 |

### 4.6 资产迁移门 A（Owner 2026-09-09 15:11 新增要求）

v7 阶段替换 robot 模型为 `gr00t/rl/data/robots/a2_piper_vpiper_final_20260906`（URDF `a2_piper.urdf`、USD `a2_piper.usd` + `configuration/` 相对引用层）。已核对（INSPECTED）：

- 与当前 `A2_Piper` 资产相比，保留原 27 个 link 与 20 个活动关节，关节名、顺序、限位、effort/velocity 上限与 `a2_piper.yaml` 逐项相同（`config/joint_mapping.csv`）；因此 obs 133/138、action 19、限位表与 D2 reward 的硬限位来源都不需要改。
- 新增 3 个固定 body：`vpiper_main`（0.3107 kg）、`vpiper_support`（0.1056 kg）、`metal_plate_5mm`（0.3375 kg），带 51 个凸碰撞块与板碰撞箱；rigid body 数 27→30。`arm_j0` 原点 `[0.145, 0, 0.154]`→`[0.145, 0, 0.147431554755]` m，臂基座下移 6.57 mm。
- 资产自带验证只到 Isaac 导入读回（30 bodies、20 joints、相对引用），没有仿真步进、接触或策略评估；旧根层 USD 含关节 drive 属性覆盖，新根层没有，需要 diff 并确认由 runtime articulation cfg 设置。
- 该变更改变 TCP–handle 几何与躯干上表面碰撞，是 plant 变更；`.ai/PROJECT.md` 要求 runtime 行为变化必须有 runtime 证据。

规则：

1. **P2 的 T/C 读数只在旧资产上完成**（三格已在旧资产训练完毕，其里程碑 eval 也用旧资产）。不把新资产上的 eval 当作 D2 因果读数，也不把旧资产 checkpoint 在新资产上的表现当作 D2 失败。
2. 门 A 独立于 P2，包含：(a) 新 robot config 变体（只改 `asset.urdf_file/usd_file`，`body_names`/`penalize_contacts_on` 按实际 USD body 集合补入三个新 body 并核对索引一致性，其余不变）；(b) 64 env 构造/导入 smoke：关节名序、限位、默认角、body 数与 FrameTransformer 目标帧读回与旧资产逐项比较，LEFT 镜像 G1 口径重跑一次；(c) 迁移评估：把 P2 最终 checkpoint（T_S1/T_S2/C_S2 10500）与 9000 两源在新资产上各做一次 natural64/侧，报告 K5/D/E4/E5 与 4A/4B 保留指标、E5 后 margin/overshoot 中介。
3. 门 A 之后的所有新训练与正式评估都使用新资产；旧资产 artifact 只读。P3 起点 checkpoint 由 P2 读数选择，若门 A (c) 显示保留能力低于 48/64，先在新资产上做一次原配置（或带 D2，按 P2 结论）的再适应续训，预算另报，再进入 P3。
4. 门 A 不改 reward、E 事件、reset ratios、actor；不改共享 env 类；不改资产包内容（资产包 `config.yaml` 里的绝对路径指向另一 worktree，是转换器记录，不是运行入口，USD 内部无绝对路径）。

## 5. P3–P5 登记（决策点，不冻结）

- **P3 B→C 联合 ready**：以 P2 成功格为来源，在门 A 之后的新资产上进行。候选单变量按证据顺序：hold 类收益停付阈值 1.60 与 ready 1.134 的错位；P_S2 LEFT 的 clearance（4A retreat 不足）；P_S2 RIGHT 的 handle-Y；hinge 速度 ≥0.15。每次只动一项，同期 C。v6 的 Stage4 集中曝光（提高 Stage4 ratio、依赖 `E5_stage4_phase1` online snapshot）只在 P1 式遥测证明高 margin B 库存 >0 后才可提出。
- **P4 送门过身→通行**：clean release 后 persistence25、crossing、frame passage、E6。需先核对 Stage4 剩余时间是否容得下 clean→E6（env14 用 382 步）；E6 的硬编码 25 与 `a2_pull_v6_release_persistence_steps` 同值，属代码卫生，不在实验中途改。
- **P5 E7/complete**：Stage5 800 步内 whole-body clear 1.5 m；v6.1 的失败样本（seed0/env3：E6 后 path 7.44 m、52 次 reversal、无 E7）是 through 阶段碰撞/路径反转参照。

以上任一阶段若要引入 BC/Teacher、旧 override、release-mode 观测或 E 门改动，都是新的 Owner 决策。

## 6. 报告口径

- 同一 cell 两侧分别 exact64 首 natural episode，保留真实出生 trace 与当前 E 事件 validator；K5/D/E4/E5、margin 中介、ready、clean、persistence25、frame、E6、E7、complete 分别报告。先报每侧全体 64 分母，再报 E5 到达者的条件转化率。
- T/C 必须同批、同来源、同 batch 数比较，并保留各自 9000 源读数。
- 一条 natural E7 只标记"观察到完整链路"；同一 cell 两侧 E7 各 ≥8/64 沿用 `PULL_FULL_CHAIN_OBSERVED`；两个独立来源复现再报重复性。
- 中介改善但 ready/E6/E7 未形成时，保留中介结论并明确全链路未达成；负结果只适用于该处理与曝光。

## 7. 施工顺序与产物

1. 本轮：本文与 memory 路由；不改训练源码/config，不启动 GPU 任务。
2. Owner 批准后：`DoorOpenA2Pull` 新增 `_reward_a2_pull_v7_arm_target_overshoot_penalty`（最小 diff，形状/限位来源与 `_reward_limits_dof_pos` 一致，非法形状直接报错）；T 配置从 `pull_v26_8_backbone_common` 派生，仅加该 scale；C 配置不加。复用 `scriptsFORhuman/pull_v26_8/` 的 `continue_cell.sh`、`eval_cell.sh`、`reduce.py`、`verify.py` 与 receipt 机制，新增一个 P2 中介 reducer（复用 P0 的 margin/条件重算，加 overshoot 列）。
3. 启动前一次 256 env×5 batch runtime smoke：T 格该项 raw 非零且数值与离线按 trace target 重算一致，C 格 resolved `reward_scales` 与 9000 源逐项相同；不做重复 smoke。
4. 三格独立 tmux + receipt，`.ai/LONG_RUNNING_TASKS.md` 规则；GPU lease 只在启动时创建。
5. 里程碑 eval 与 reducer 由 watcher 执行；Main 只报告新结果或失败。
6. 不 commit/push；`.codex/config.toml`、`Codex-Cashier/` 与 robot 目录不在 WRITE_SET。

Owner 已定：不改共享 backbone；先用 GPU1–3，C_S1 补跑。仍需 Owner 最终确认：(a) D2 作为 pull 侧新增 reward 项及 scale −1.0（含 §4.1 的唯一重试规则）；(b) §4.3 四格预算（各 500 准入 + 最多 1000 继续）。

## 8. 证据路由

- 0908 版方案与 P0/P1：[0908 plan](a2_piper_pull_v7_stage_plan_20260908.md)、[P0_DIAGNOSIS](../pull_v7/P0_DIAGNOSIS.md)、[P1_EXPOSURE_REPORT](../pull_v7/P1_EXPOSURE_REPORT.md)、`P1_EXPOSURE_SUMMARY.json`。
- 迁移 closure：[v26.8 closure](../pull_v26_8/a2_piper_pull_v26_8_backbone_closure_20260908.md)、[SUMMARY](../pull_v26_8/SUMMARY.json)、[REDUCER_CONTRACT](../pull_v26_8/REDUCER_CONTRACT.md)。
- 送门过身：[v6.1 population 报告](../pull_v6_1/PULL_V6_1_P_POPULATION_REPORT.md)；`memory/a2-piper/pull-open-door-task/description.md`；env14 trace `logs_eval/a2_piper_pull_v6/p2_render_F0_r6ap_r6an_seed3_env14/eval/stage2_5_step_trace.json.gz`。
- 动作积分器：`gr00t/rl/envs/base_task/delta_action_base.py:59-66,135-152`；`gr00t/rl/envs/base_task/a2_base.py:545-612,786-796`；resolved `wave2/train/P_S1/resolved_config.yaml` 的 `delta_action_*`、`default_joint_angles`、`dof_pos_*_limit_list`、`max_stage_time`、`reward_scales`、`reward_limit`。
- release/E6/E7/reward 门：`gr00t/rl/envs/door/door_open_a2_pull.py:5609-5991,6561-6593,9237-9826`；`door_open_a2_base.py:2100-2183,11982-11998`；stage 时间 `gr00t/rl/envs/base_task/staged_task_base.py:190-196,262-275`。
- 当前四侧 trace：`logs_eval/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/eval/milestones/step9000/{P_S1,P_S2}_STEP9000/{left,right}/`。
