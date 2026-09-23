# SOURCES — 来源、核验范围与证据边界

审阅日期：2026-09-20。基座：完整 `v29-c002-baseline`，保留 B05；发布分支 `codex/v29-n01-pro-20260920`。本文件中的 `[Cxx] / [Exx] / [Hxx] / [Pxx]` 是其他五份文件的来源索引。它们不是实验结果编号。

## 1. 输入取得与阅读范围

从 Owner 指定的 [Drive 输入目录](https://drive.google.com/drive/folders/1TYMXvIKohP6-IlrhYa6hXFn4qjZqWvIo) 取得三个普通 ZIP，以及 INDEX、MANIFEST、PRO_HANDOFF。三个 ZIP 均能完整解压，条目数分别为 332、40、18，压缩大小分别为 19,411,932、6,320,911、76,803 bytes；普通 ZIP 完整性检查通过。没有创建或回传哈希清单。

先阅读 OWNER_REQUEST、LOCAL_FACTS、SOURCE_INDEX、SUPPLEMENTAL_SOURCE_BINDING 与当轮 research brief；然后阅读与恢复/控制/蒸馏相关的生产源码、resolved config、D056/D060/D061/D064 和相关原始 readout；结合一手论文写出独立初步方案后，才取得并阅读 historical ZIP。大体量历史会话按恢复、蒸馏、N01/N02 分工进行定向阅读，不声称逐字审计所有会话。三份 ZIP 的文件可取得，不等于全部资产都经过几何验证。

**未进行的工作与不可获得的内容：** 未运行 Isaac、MuJoCo、CUDA、训练、策略推理或闭环评估；输入没有 checkpoint/策略权重。未取得未打包的本地完整 metadata、训练数据库、最终自然评估、v29 Student resolved 配方及其实机相机时序。两张 C001 atlas 图片和所有 mesh/CAD 不作本次重新视觉/结构验收对象；B05 接受结论依据所提供验收记录，不推导为所有把手可恢复。远端 `door_open_a2_base.py` 的一次大行号定向 fetch 返回空内容，该文件的分析来自已完整取得的冻结 source ZIP，不把那次空响应当作源码核验。远端 A2 distill trainer 与 delta_action_base 的有界读取成功。

资料包对“同 tag 的依赖逐字节核对”的陈述来自本地 binding/LOCAL_FACTS；本审阅没有重新对远端整棵树作逐字节审计。生产快照 321 份加 11 份不重复依赖是本次输入范围，不是对远端 tag 存在性的额外要求。

## 2. 源码索引

以下路径相对于仓库根目录；行号对应本次冻结内容。若本地后续行号变化，按函数名定位。源码链接定位本次发布分支，不代替本地已保存输入。

### [C01] 完整 C002 参数与组合

- [base_v29_common.yaml](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/config/ablation/wbmanip/base_v29_common.yaml)，约 29–114：v29 总开关、30 s、阶段预算、B07、把手高度、grasp streak、Stage3/4 门槛、staged reset；约 219–232：Teacher 相机关闭、v29 robot 组合。
- [base_v29_baseline.yaml](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/config/ablation/wbmanip/base_v29_baseline.yaml)：基线组合与 seed。
- [door_v29_parameters.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/isaac_utils/playground/env_rand/door_v29_parameters.py)、[door.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/isaac_utils/playground/env_rand/door.py)：逐门 B01/B04/B05 参数和资产消费者；结合 [E01–E03] 使用。
- 支持：完整 C002+B05 与 v29−B05 是不同条件；没有独立 B05 开关不表示 B05 未启用。不能支持：成熟任务成功率。

### [C02] 阶段、计时、奖励与 staged reset

[staged_task_base.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/envs/base_task/staged_task_base.py)

- 164–220 `_post_compute_observations_callback`：单向 stage advance、剩余时间结转、总时间、高水位、正常阶段 snapshot。
- 约 237：阶段超时；302–338：transition 与 success-save-time 奖励。
- 约 400 及 556–711：设置 stage、snapshot/buffer restore/reset 链路。
- 支持：当前 stage 整数、局部计时与总进展有实际副作用；该基类不是任意在线恢复图。物理 snapshot 不是 Teacher/Student 完整时序样本。

### [C03] 门任务恢复、目标、奖励与完成条件

[door_open_a2_base.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/envs/door/door_open_a2_base.py)

| 位置 | 已核对内容 |
|---|---|
| 5414–5419；6943 附近 | 六个阶段常量；旧 v27 配置缺省解析为空 |
| 8870–8914 `_apply_delta_action_overrides` | Stage0 对机械臂 delta accumulator 强制归零；不能无代价地把在线恢复标成 Stage0 |
| 14371–14413 `_a2_v27_prepare_actor_state` | 已握持窗口中的短时 gripper 列 11 open 覆盖；仅命令不保证物理失抓 |
| 14415–14469 `_update_a2_v27_recovery_state` | 历史 Stage3/4 失抓、正常释放排除、统一退 Stage2、局部计时与 streak 修改 |
| 14471–14588 | 历史 recovery bank 的物理状态/注册 buffer 采集和 reset，不包含完整视觉/RNN 历史 |
| 146xx；17393–17425 | handle creation 高水位；旧恢复对部分重复 stage/transition/save-time 收入的屏蔽 |
| 153xx–15428 | 双指接触/挤压与 control-tick streak 更新 |
| 15706–15905 | 正常 release/crossing 相关历史 gate；root crossing 不能直接当全身扫掠体清空 |
| 15964、15977 附近 | Stage0/5 arm-default 奖励；Stage4 release-gated arm-default 惩罚 |
| 16420、16452、17591 附近 | grasp distance/hold-income 的阶段条件，Stage4/5 handle 回升偏好；恢复接近期间可能存在目标冲突 |
| 18701–18783 | 实时 pregrasp 准备、grasp completion/squeeze/streak；command 停稳并不等价于实测 base 速度 |
| 29732–29783 | Stage0→1 实时站位、arm 默认姿态、base command 条件 |
| 29891–29942 | Stage3→4、4→5 与 Stage5 完成；原目标包括 root 门坐标 x>1.5 |
| 30027–30073 | 当前刚体/G frame 的目标计算，pregrasp offset；目标 frame 并非一律冻结在关门初始时刻 |

上述行号支持具体实现事实；本回包新增的目标可达性判据、事件类型、观测估计器、时间账本和部署适配器均是建议，不是现有实现。

### [C04] 动作语义和低层历史

- [a2_base.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/envs/base_task/a2_base.py)，1141–1249：24D 输入、12D 高层布局、gripper primitive 正号全开/否则全关、腿动作组合；1314–1350：command/actions 观察；1497、1511 附近：冻结低层历史。
- [delta_action_base.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/envs/base_task/delta_action_base.py)，约 54–152：delta 积分、clamp、override、可选 zero_vel/zero_finger；其后 reset/store/load callbacks。该文件另外经远端有界读取；不是凭空补齐的依赖。
- 支持：动作执行者混合必须发生在相应低层动作计算之前；arm 的 delta、累计目标、实际关节位置不是同一个量；恢复不能清掉执行历史。`zero_vel/zero_finger` 在读取的 C002 resolved 中没有显式字段，不能仅凭缺字段断言所有继承路径都无作用，新 Student 配方须显式解析。

### [C05] A2 蒸馏实际执行与标签

[distill_trainer_a2_base_api.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py)

- 340–415：Teacher 每步查询当前 env；Student 同样 forward；`int(N*ratio)` 的确定性前缀替换；冻结低层使用 selected high action；记录 Teacher `gt_actions` 与 Student hidden。
- 417–436：done reset、rollout init/clear。
- 438 起：12D action-mean BC 与序列 mask。
- 支持：已有在线 Teacher 查询和部分 Student 执行接口；不支持“默认就是 Student 闭环”“已有自动 annealing”“Teacher hidden 已存入蒸馏库”。

### [C06] 蒸馏存储与优化目标

[distill_trainer.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/trl/trainer/distill_trainer.py)，264–433：当前 rollout 存储、split/pad/recurrent minibatch；482–488：优化目标是 BC。没有本回包所建议的跨 rollout 事件序列库。

### [C07] Student 配方与信息边界

- [door_open_a2_base_dagger-lstm.yaml](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml)：旧默认组合、手动比例注释、teacher rollout=true/ratio=1、8-tick rollout、BC、LSTM/视觉网络、相机默认配置（187–204 附近）。
- [door_open_a2_base_dagger.yaml](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml)：actor81D、Teacher133D、critic138D、冻结 A2_Base 1620D；没有 actor 显式 stage/contact/door 真值。
- 支持：既有结构可作接口起点，不是已跑通的 v29 Student resolved recipe。旧 actor RGB 为 216×384；不能用 Teacher runtime 的相机字段或高分辨率 eval render 代替实际 actor 输入预算。

### [C08] 两套循环记忆与视觉读入

- [memory.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/trl/modules/memory.py)，40–127：inference/batch、done reset、detach、局部状态恢复接口边界。
- [actor_critic_modules_recurrent.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/trl/modules/actor_critic_modules_recurrent.py)，reset、get_hidden_states、clear_rollout；[vision_actor_critic_modules_recurrent.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/trl/modules/vision_actor_critic_modules_recurrent.py)。
- [legged_robot_base.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/envs/legged_base_task/legged_robot_base.py)，约 2440–2520：RGB tensor/shape 检查与摄像头读入。
- 支持：rollout clear 中 detach 不意味着 online hidden 归零；重新使用旧 hidden 会有版本/时序问题；无效 tensor、API 失败应 fail-fast，不能当作策略恢复样本。

### [C09] 扰动 backend 的实际实现边界

- [isaacsim.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/simulator/isaacsim/isaacsim.py)，约 2360：`apply_rigid_body_force_at_pos_tensor` 为 `pass`；约 2800–2816：清外力与 `wsdpt_push_robot` 路径，后者依赖 torso/right_palm 索引。
- [legged_robot_base.py](https://github.com/Jam-Stark/DoorDog/blob/codex/v29-n01-pro-20260920/gr00t/rl/envs/legged_base_task/legged_robot_base.py)，2199 附近：`_push_robots` 的速度冲击/事件实现。
- 支持：不能把通用 force 函数名当作 A2 上已经有效的物理注入；需要选定实际 backend/body、作用坐标系和读回。速度冲击是人工冲击模型，不是持续原生外力；未在本次执行任何该接口。

## 3. 本次 runtime/brief 证据

均来自 `worker_delivery__N01_brief_and_runtime_evidence.zip`。文件名是准确定位，不把未取得的本地路径当作已读取。

- **[E01] 当前范围/来源**：`scriptsFORhuman/v29/pro_handoff/20260920_n01_recovery_transfer/{OWNER_REQUEST.md,LOCAL_FACTS.md,SOURCE_INDEX.md,SUPPLEMENTAL_SOURCE_BINDING.json}`；`scriptsFORhuman/novelty/documents/20260920_n01_v29_c002_pro_research_brief.md`。支持冻结底座、Owner 问题和来源说明，不单独证明能力。
- **[E02] 接受状态**：`evidence/C002_acceptance/D056_C001_PER_ITEM_ACCEPTANCE.md` 与 `D060_C002_ACCEPTANCE_AND_TRAIN_APPROVAL.json`；`evidence/C002/implementation_report.md`、`stage5_a3_readout.json`。支持 C002 接受、B05 保留，旧候选 pending 不是当前结论。C002 用 Stage5 probe 关闭验收项，不是又改一版生产门域。
- **[E03] 实际初始化与 resolved**：`evidence/C002_runtime/config.yaml`、`D061_INITIALIZATION_AND_LOSS_OBSERVABILITY.json`、`RUN_RECEIPT.json`。4096 env；七族被实际分配、左右各半；旧 v27 recovery/perturb 未启用。有限 reward/tensor/entropy 观察不等价于 loss 或最终成功。
- **[E04] 最新已存里程碑**：`evidence/C002_runtime/D064_BATCH3000_MILESTONE_REVIEW.json`、`batch3000_readout.json`、`batch3000_console.txt`。左右历史 max Stage3；Stage2 both-contact 打印 .4098；grasp-complete/to3 .0001；Stage4/5/goal 打印 .0000。它们是 staged-training 指标，四位小数 0 不证明从未发生，不能解释成自然成功率。数值 loss 仍 NOT_OBSERVED。未为本次重新轮询。
- **[E05] 辅助实现证据**：`evidence/C001/{retained_baseline_semantics.md,mass_frame_readback.json,reference_contact_localization.md,reference_contact34_readout.json,initial_runtime_readback.json,scale4096_physical_readout.json}`，以及 `design_context` 下 v29 baseline/B05 plan。用于定向核对当前范围，不扩大成全 C002 重新审计，也不由有限接触案例推导恢复泛化保证。

## 4. 历史材料：只作对照

均来自 `worker_delivery__historical_novelty_reference.zip`，阅读发生在独立初步方案之后。

- **[H01] 旧路线**：`scriptsFORhuman/novelty/documents/a2_piper_novelty_route_20260905-Astra.md`、`20260905_claude_novelty_decision_excerpt.md`，及 9/5 Astra/Claude conversations。恢复图、困难边界状态、恢复蒸馏的想法已有历史讨论；不能把本回包重复表述当新贡献。
- **[H02] 既有独立审阅**：`scriptsFORhuman/novelty/conversations/pro_20260917_202000.md`（定向阅读恢复/Teacher→Student 部分），及 `20260914_v28_g1_closure_N01_N02.md`、`20260917_v28_closure_N01_N02.md`。旧 v27 仍未证明收益；这些文件不是当前训练授权。
- **[H03] post-release 回关分工**：`scriptsFORhuman/novelty/documents/20260918_n02_regrasp_rebound_discussion.md` 及同日 rebound/B01 conversations。Owner 当时将其放到 N02 讨论待办；不是已实施恢复机制。共享 assistance-needed 语义和“接近前就解除冲突奖励”的问题已有明确历史提醒。
- **[H04] v27 pilot**：`scriptsFORhuman/v27/a2_piper_base_v27_wave_b_r_step1500_readout_20260907.md`、`runtime_logs/v27_bilateral_hardening_20260905/wave_b_recovery_decision.json`。R2 step1500 注入分组左右各 64 episode、各 63 次触发；实际 loss 5/2，regrasp 5/2，recovered_complete 5/2，但 recovered_clean_complete 0/1。不能以 5/5、2/2 宣称合格恢复，更不能映射成 C002 结果。R1 未到计划 endpoint；整体结论 UNRESOLVED。step500 是另一条记录，不混用分母。

## 5. 一手研究与官方作者资源

对每篇都区分“论文研究了什么”和“没有证明什么”。以下摘要是意译，不大量逐字摘引。2026 工作均经过在线核对，不凭记忆判断其最新状态。

### [P01] DAgger

Ross, Gordon, Bagnell. *A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning*. AISTATS 2011.

- [PMLR 官方论文页](https://proceedings.mlr.press/v15/ross11a.html)
- 已核对：让学习者访问自身诱导的状态，再查询专家并聚合数据的核心机制。
- 支持：为什么只用 Teacher 正常轨迹不足；为什么“本 rollout BC”不等于完成跨分布覆盖。
- 不支持：任意部分可观测 actor 都能实现全状态专家；不保证安全、恢复或有限样本成功。

### [P02] DART

Laskey et al. *DART: Noise Injection for Robust Imitation Learning*. CoRL 2017.

- [PMLR 官方论文页](https://proceedings.mlr.press/v78/laskey17a.html)
- [作者项目](https://berkeleyautomation.github.io/DART/)
- [作者代码](https://github.com/BerkeleyAutomation/DART)
- 已核对：在监督者轨迹中注入扰动，让纠正状态进入数据分布；噪声分布设计有其具体方法。
- 本回包的短开爪脉冲只是工程借鉴，不等于实现原文完整 DART。Teacher 被扰后会修正，不证明 Student 自主闭环能恢复。

### [P03] RecoveryChaining

Vats et al. *RecoveryChaining: Learning Local Recovery Policies for Robust Manipulation*. 按 arXiv 2410.13979v2 阅读。

- [论文全文](https://arxiv.org/html/2410.13979v2)
- [作者代码](https://github.com/shivamvats/recovery-chaining)
- 已核对：恢复不只是回到前一个技能；应选择能接续任务的 nominal option，并学习恢复控制与接续选择。
- 支持：把“退回哪里”改成目标技能的可执行前提，而不是固定 Stage2。
- 边界：原论文任务、nominal controllers、失败检测/恢复训练设定不同；没有证明本项目单 RGB、双 RNN、Student 当前分布下的传递。不能把条件恢复图本身列为新颖性。

### [P04] Recovery RL

Thananjeyan et al. *Recovery RL: Safe Reinforcement Learning with Learned Recovery Zones*. ICRA 2021.

- [论文](https://arxiv.org/html/2010.15920)
- [作者代码](https://github.com/abalakrishna123/recovery-rl)
- 已核对：任务策略与恢复安全区域/策略的分工、约束数据使用。
- 支持：应区分安全接管与原任务策略能力；恢复的进入与退出需要条件。
- 边界：避免约束违反不等价于失抓后完成开门；其特定训练重标注不能直接用来把 Teacher 接管算成 Student 自主成功。

### [P05] HG-DAgger

Kelly et al. *HG-DAgger: Interactive Imitation Learning with Human Experts*. ICRA 2019；arXiv 1810.02890。

- [论文](https://arxiv.org/html/1810.02890)
- 已核对：人类在必要时接管并连续控制一段，提供纠正数据，而非频繁逐步切换。
- 支持：辅助采样支路使用连续接管区间、记录接管来源。
- 边界：本任务专家是仿真 Teacher，可以每步 shadow query；无须照搬人类标注成本假设。接管数据价值和 Student 独立成功是两个问题。

### [P06] A2D：特权专家与部分可观测学习者的错配

Warrington, Lavington, Scibior, Schmidt, Wood. *Robust Asymmetric Learning in POMDPs*. ICML 2021；方法名为 adaptive asymmetric DAgger（A2D）。

- [PMLR 官方论文页](https://proceedings.mlr.press/v139/warrington21a.html)
- [作者全文](https://arxiv.org/html/2012.15566)
- [作者代码](https://github.com/plai-group/a2d)
- 已核对：固定全状态专家可能利用学习者无法辨识的信息；把专家适应到学习者可实现行为是一个独立问题。
- 支持：需要检查 observation/action aliasing，不能把失败都归因于数据量或网络容量。
- 边界：不保证本文 proposed Teacher 适配或 PPO + LSTM 自动收敛；A2D 缩写与 A2 机器人没有关系。

### [P07] Miki 等：带记忆的特权到感知策略传递

Miki et al. *Learning robust perceptive locomotion for quadrupedal robots in the wild*. Science Robotics, 2022.

- [作者论文全文](https://arxiv.org/html/2201.08117v1)
- [正式 DOI](https://doi.org/10.1126/scirobotics.abk2822)
- 已核对：特权 Teacher、recurrent Student belief、动作模仿与辅助重建、感知扰动。
- 支持：循环感知表征与训练期辅助目标是可行的设计先例。
- 边界：其感知与足式地形任务不等同于单 RGB 的近距把手接触；不能据此保证隐式接触状态可精确恢复，也不应强迫 Teacher/Student hidden 向量相同。

### [P08] R2D2：循环 replay 的时序与陈旧状态

Kapturowski et al. *Recurrent Experience Replay in Distributed Reinforcement Learning*. ICLR 2019.

- [作者主页摘要](https://willdabney.com/publication/r2d2/)
- [OpenReview 论文入口](https://openreview.net/forum?id=r1lyTjAqYX)
- 已取得：作者摘要关于 representation drift、recurrent state staleness 的说明。
- **访问限制：** 本次 OpenReview 全文/PDF 请求遇到浏览器挑战，未读到该全文，不能声称核验其具体 burn-in 数值或实验结果。本回包“从真实 episode 起点重算 prefix”的实现建议独立给出，不冒充复现 R2D2。

### [P09] ReSYNC

Li et al. *Recover, Discover, Plan: Learning Skills and Concepts from Robot Failures*. 按 arXiv 2606.18328v1 阅读，2026。

- [作者论文全文](https://arxiv.org/html/2606.18328v1)
- 已核对：从失败学习恢复技能与关系概念，并接回规划；文中还包括恢复技能到视觉策略的蒸馏。
- 重要边界：相关视觉实现使用校准的多视角/对象感知资源，不能直接套成本文 81D + 单路 RGB 的部署预算；未核验其官方代码，不提供猜测链接。
- 含义：既不能宣称“首次恢复技能图”，也不能宣称“首次恢复能力视觉蒸馏”。本文按所读版本讨论，不依赖其后续会议接收状态。

### [P10] CritiQ / ReTRy

Kim, Chin, Vasudev, Choudhury. *Distilling Realizable Students from Unrealizable Teachers*. 按 arXiv 2505.09546v1 阅读，2025。

- [论文全文](https://arxiv.org/html/2505.09546v1)
- [作者项目](https://portal-cornell.github.io/CritiQ_ReTRy/)
- 已核对：对不可由 Student 实现的专家监督进行选择，以及利用 Teacher rollout 扩展 Student 的训练起点等方法。
- 支持：不能盲信 OOD/信息不对称状态上的每个 Teacher 动作；Teacher continuation 与 Student 训练分布可分开设计。
- 边界：这些任务的隐藏目标与状态恢复设定不直接解决 DoorDog 双 RNN、delta accumulator、低层历史、RGB prefix 的完整还原；本次未核验作者代码。该文线索来自历史材料，随后独立读取一手论文，不把历史摘要当作论文证据。

### [P11] Potential-based reward shaping

Ng, Harada, Russell. *Policy invariance under reward transformations: Theory and application to reward shaping*. ICML 1999.

- [作者托管 PDF](https://people.eecs.berkeley.edu/~russell/papers/icml99-shaping.pdf)
- 已核对正文及 PDF 第 4 页的定理/公式：`F(s,s') = gamma * Phi(s') - Phi(s)`；有相应有界性与 MDP 条件。
- 支持：普通距离正奖励与循环恢复可能冲突，势差是有理论依据的候选。
- 边界：本项目改变终止、模式、时间和奖励 mask 后，不能自动援引定理宣布最优策略不变；必须把这些变量纳入状态并处理 terminal/timeout 的势函数边界。本回包未证明整套 C002 奖励无投机。

## 6. 文献到建议的对应，而非“已证明”

| 建议 | 一手先例 | 本项目仍需验证 |
|---|---|---|
| 条件物理落点而非固定退 Stage2 | P03、P09 | 开门动态下真实可达、是否比 recurrent baseline 好 |
| Teacher 强制暴露纠正状态 | P02 | 实际失抓、可恢复样本率、名义性能代价 |
| Student 当前状态查询/聚合 | P01、P05 | 12D 动作语义、Teacher 标签可靠性、短事件覆盖 |
| 部分可观测 Student 的辅助记忆学习 | P06、P07、P10 | 81D + RGB 是否足以区分所需动作；不偷渡真值 |
| 跨 batch 循环序列与 prefix 重算 | P08 的问题背景；本文接口设计 | 当前代码中存储/版本/时间一致性与实测收益 |
| 防重复进展收入 | P11 的局部理论 | 完整 C002 奖励/超时/释放冲突是否被实际消除 |

**当前没有一篇文献证明：本项目完整 C002+B05 的合格恢复 Teacher，经过常规蒸馏，就会得到可部署的自主恢复 Student。** 该结论必须由本项目的独立闭环实验获得。
