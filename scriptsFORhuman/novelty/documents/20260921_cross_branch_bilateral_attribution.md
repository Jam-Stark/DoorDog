# LEFT/RIGHT学习差异：v29 push、B05消融、pull与v28对照

**最终更新（2026-09-22 11:08 HKT，D077）：** 同配方8000自然64已全部goal/complete，左右各32/32，staged load0；本轮验收关闭，无续训授权。6000→7000→8000总goal0→31→64，原左右卡点在本次8000人口中已不再阻止完成。下文保留早期checkpoint的诊断及当时建议，针对旧周期的干预不再作为当前8000继续工作的前置。[canonical最终结果](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_C002_resume8000_final_readout_20260922.md)。

**后续证据更新（2026-09-21 20:04 HKT，D076）：** 同配方7000自然64中LEFT31/32goal且全部32到Stage5；RIGHT31例Stage3＋1例Stage2、仍无Stage4。六个可用门字段与6000逐env一致；继续原8000授权。以下6000/早期训练窗口的诊断是历史证据，不能继续当成7000当前状态；本轮未归约7000动作trace，因此不宣称开爪周期完全消失。[正式登记](/home/baoquanc/workspace/DoorDog-A2_Piper/.ai/runtime/v29_baseline_team/D076_C002_RESUME7000_NATURAL_MILESTONE.json)。

2026-09-21 17:13 HKT；Codex v29 planner。Owner要求基于给定pull双侧eval、v29 baseline/B05-ablation及v28历史进一步归因。证据为已有运行产物的离线归约与定向源码/配置检查；未启动新仿真或训练，未修改生产代码、checkpoint、资源或既有等待。

**当前最具体的发现：C002@6000的RIGHT自然评估被周期性开爪打断，持续有效握持只达到3–4步，始终未满足Stage2→3的K=5。它不是已经进入Stage3却始终压不下的同一种失败。** 为什么策略学成该周期尚未隔离；现有证据优先支持具体阶段行为与学习历程的差异，不支持直接把全局PPO归一化或未启用v27 recovery bank当成已确认根因。

## 1. 先统一结果口径

| 版本/阶段 | LEFT | RIGHT | 证据人口 |
|---|---|---|---|
| push C002@6000 | 27到Stage4、3到Stage5、2止Stage2；goal0/32 | 32止Stage2；goal0/32 | 一次双侧64自然首episode，各32 |
| pull v29@4000 | 64到Stage4；goal0/64 | 64到Stage4；goal0/64 | 同一bilateral checkpoint，分侧各64自然首episode |
| B05-ablation 3576–3675 | 约71.2%时间Stage3，Stage4可恢复env数均值2 | 约69.2%时间Stage4/5，累计训练goal计数非零 | 含staged reset的训练窗口；尚非自然eval |

pull两份Owner指定per-env均为64唯一env，side一致、seed291，全部Stage4超时，长度1129控制步。它证明这个checkpoint双侧均已越过前段门槛，没有证明完整goal成功。`runtime_result.actual_success=true`是执行成功，不替代goal字段。

pull eval的`enable_staged_reset=true`配`[1,0,0,0,0,0]`，关闭额外Stage4/late/broadcast bank；raw trace明确128个episode_start均Stage0、episode_index0。push eval为staged=false。可比较自然前段行为，但两套reset实现、单侧/混合场景、参数人口不是逐门完整配对。

来源：Owner的[pull LEFT](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v29/step4000_lr_exact64_20260921/left_a4/a2_v14_per_env_records.json)、[pull RIGHT](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/logs_eval/a2_piper_pull_v29/step4000_lr_exact64_20260921/right_a1/a2_v14_per_env_records.json)、[push D072](/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/v29/a2_piper_base_v29_C002_final_readout_20260921.md)、[B既有窗口](evidence/20260921_v29_bilateral_curriculum/current_windows.json)。

## 2. 新增的逐步证据：push RIGHT卡在持续握持

本次离线读取既有三份完整trace，以标准库json解码。push按每env episode_length首次回退截断，排除后续episode行28629条；pull用其first_episode_active/episode_index标志，保留首episode。每env最终长度与结果一致：push827/1129/1430，pull1129。分析代码及结果在[evidence目录](evidence/20260921_cross_branch_bilateral)。这补充了此前只读摘要时缺少的同步信息。

| 读数 | push LEFT | push RIGHT | pull LEFT / RIGHT |
|---|---:|---:|---:|
| Stage2达到K5的episode | 30/32 | **0/32** | 64/64、64/64 |
| 每例Stage2最长streak | 4–5步 | **3–4步** | 都达到5步 |
| Stage2时长的跨env中位数 | 40步 | **620步≈12.4s** | 12步、12.5步 |
| 每例双指接触时间比例的跨env中位数 | 52.6% | **59.2%** | 41.7%、41.7% |
| Stage3实际同时满足hinge>.25与hold K5 | 30/30进入者 | 无Stage3自然样本 | 64/64、64/64 |

RIGHT不是完全够不到/碰不到把手：32例都有双触，Stage2 TCP到G距离的每例中位数再取跨env中位数约9.86mm。但触碰不能持续成合格握持。其Stage2把手角各例最大值范围仅0.000112–0.002240rad；缺下压是可见现象，但更早的持续握持已阻塞晋级。

进一步针对RIGHT首episode的19206个Stage2控制样本，找到3760次`streak>0 → 0`：

- 3760次全部出现在当步gripper命令为正、双接触消失、squeeze_window=false；前一步命令全部非正。
- 其中3519次中断前streak=3，214次为4，其余27次为1或2。
- 非正命令连续段最常见长度4步（3735段），正命令连续段最常见长度1步（3760段）。扣除初始张爪接近，表现为约4步闭爪＋1步开爪的重复模式。
- env1的一个片段：控制步277/278/279的streak为1/2/3，闭爪raw命令约−1.86/−1.96/−1.97；280步raw变为+1.30，双触消失，streak清零。这个正值不是接近零的数值误差。

[逐步序列和条件统计](evidence/20260921_cross_branch_bilateral/push_right_gripper_sequence.json)。这些是同32例内反复发生的控制事件，不是3760个独立episode。

当前[A2解码器](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/base_task/a2_base.py:1183)用`gripper_primitive>0`直接选全开目标，否则选闭合目标。命令先进入物理步，接触与streak在物理更新后记录。由此可定位到“执行中的周期性开爪—失去接触—K5被打断”的直接行为链；尚未做固定闭爪等单因素干预，不能宣称它是唯一必要/充分原因，更不能直接用强制闭爪替代策略控制作为修复。

Stage2的K5累计条件是双触、足够挤压力、方向相反；诊断`squeeze_window`的上界不是额外的K5硬门。此处所有周期中断都同时失去双触，结论不依赖该差别。

## 3. pull对哪些猜测构成约束

pull训练是scratch、checkpoint=null，同一bilateral策略；实际v29/B05 selector与4096左右各2048有配置/运行证据。两边gripper配置都是45/45N、Kp1300/Kd32，默认arm关节角相同。学习率1e−4、5 PPO epochs、4 minibatches、gamma .9975、lambda .985等主要保存配置相同；都使用全局advantage归一化，训练普通staged比例都为[.5,.1,.1,.1,.1,.1]。pull额外Stage4/late/broadcast bank在训练时也关闭。

因此，共享PPO、没有逐侧归一化、没有特殊恢复bank这些公共事实，无法单独解释为何push RIGHT在K5前形成循环而pull双侧能通过。它们仍可能与具体数据分布相互作用，不因这个对照而被完全排除。

pull并没有通过放松K5来得到双侧Stage4：其Stage2→3仍继承grasp_completion；Stage3→4反而在hinge>.25和hold之外增加panel contact为零及E2 tensile-capture事件。

也不能把push/pull当成只翻转方向的受控实验。已看到的差异包括：

- 操作方向、抓握/拉力事件和奖励不同；pull有独立事件状态逻辑。
- Stage0站位带push为[.68,.72]m，pull为[.5,.8]m；Stage1/2 forward-creep deadband分别.02/.05m。
- push有penalty curriculum/side-min driver，pull关闭该curriculum；本次没有把这点单独归因。
- 两边source分叉，pull eval未保存可完全绑定当时dirty source的版本信息；实际config/trace支持上述运行读数，当前source只补充执行合同。

[保存配置的限定对照](evidence/20260921_cross_branch_bilateral/push_pull_selected_training_config.json)。push source：[Stage2 gate](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:29870)、[Stage3 gate](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/envs/door/door_open_a2_base.py:29891)、[PPO](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:7367)；pull source：[阶段override](/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0/gr00t/rl/envs/door/door_open_a2_pull.py:9947)。

## 4. v28确实可能追上，但不是统一、单调地追上

下表都是natural exact64，数字为LEFT/RIGHT goal数；此处goal与complete terminal数相等。eval seed280001，staged=false。原三seed都scratch。

| v28 cell | 3000 | 4000 | 5000 | 6000 |
|---|---:|---:|---:|---:|
| A_S281 | 5/64 | 64/64 | 52/0 | 62/63 |
| A_S282 | 0/0 | 36/33 | 63/64 | 62/64 |
| A_S283 | 0/0 | 0/0 | 0/0 | 64/4 |
| A_S284，条件臂 | 0/64 | 64/64 | 64/63 | 未运行 |

每个数的分母均为64，斜杠分隔LEFT和RIGHT，不是一个比例。A284另改driver target_stage=5且后于5167打印处停止，不并入原三seed分母。完整1000–6000及clean计数见[v28_milestone_summary.json](evidence/20260921_cross_branch_bilateral/v28_milestone_summary.json)和其中六份原聚合表链接。

A281 RIGHT四个3000/4000/5000/6000 lane的eval配置仅checkpoint/output不同，逐env静态门参数也一致。因此64→64→0→63不能归因于换了测试seed或门参数；仍不声称完整simulator RNG/state逐集配对。

更关键的是，这些“失衡”的失败阶段不同：

- A281@3000 LEFT的59个失败全已到Stage4，5个到goal。它当时主要缺后段通行，和v29 C002 RIGHT卡Stage2不同。
- A281@5000 RIGHT虽然goal0，却有42例已到Stage5、2例到Stage4、20例止Stage1；**64例全部因upper_dof_overspeed终止**。不能把这个下降解释成突然不会抓握或下压。
- A283@6000 RIGHT的60个失败全到Stage4超时，其余4个goal；仍是后段问题。

上述v28固定自然评估人口的门重约80–120kg、把手高度约.85–.95m；v29当前域已扩展到30–160kg、.90–1.20m，并改变B05把手表示及门动力学。相同iteration数不是同一任务难度下的学习进度。

所以Owner关于“迭代增加后可以双侧到goal”的记忆有依据，但它不证明任何seed/任何卡点追加迭代都会自然消失。v28的goal还不等于clean/最终资格；本轮用goal分析学习进展，保留原qualification结论。

## 5. 当前归因排序与下一步

**已观察到的直接阻塞**：C002@6000 RIGHT的Stage2周期性开爪、接触中断、K5不成立。它比笼统的“右侧采样少”更具体，也发生在v27 recovery所处理的“Stage3/4曾握稳后失抓”之前。

**有数据支持的总体解释**：不同侧在不同任务/几何/姿态下，可能先学到不同的稳定行为或失败循环；历史v28显示同一协议下checkpoint表现可显著变化，且失败模式随阶段改变。B05撤回后训练领先方向改变，支持环境与学习历程存在相互作用，但B的自然eval尚缺，不能完成同口径因果对照。

**合理但未隔离的放大机制**：训练使用采样动作与staged起点，自然eval执行action mean且从Stage0开始；一个env曾靠探索获得Stage3 snapshot，不保证确定性策略能再次从自然起点到达。per-env bank使早期突破改变后续访问状态。共享PPO的advantage/critic/梯度差异可能进一步影响两侧，但本次未取得逐侧训练advantage/梯度数据。

训练执行采样动作见[rollout](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:6120)，eval取action_mean见[eval](/home/baoquanc/workspace/DoorDog-A2_Piper/gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py:8405)及后续执行链。这是代码合同，不能反推出已经量化随机探索对本次bank的贡献。

**尚未回答的机制问题**：周期性开爪为何被学到——可能涉及Stage2/3预期收益、接触反馈与循环策略、探索到确定性输出的差异或共享优化；现有观察没有隔离这些原因。B LEFT的Stage3缺逐侧联合轨迹，也不能套用push RIGHT的Stage2解释。

下一步优先围绕这个已观察行为检验，而不是同时更改左右份额、逐侧归一化与recovery bank。例如，在明确的新读回范围内，用同一C002 checkpoint和同一RIGHT场景短暂限定Stage2闭爪，观察K5/晋级是否恢复；它只用于定位，不作为policy通过证明。本轮未运行该干预。现有D074的7000/8000自然评估可观察该周期是否随既定续训消退，原实验继续按原合同。
