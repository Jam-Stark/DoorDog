# PILOT_AND_IMPLEMENTATION_PLAN — 最小实现、可归因 pilot 与改方向条件

**仅为研究建议。** 本回包不授权本地修改、训练/评估、GPU 占用或新预算；GPU0/GPU1 既有任务继续原合同。下面的“执行”均指 Owner 以后明确授权后的本地步骤。没有声称这些步骤已发生。

主底座：完整 `v29-c002-baseline`、B05 七族保留。审阅分支：`codex/v29-n01-pro-20260920`。来源见 [SOURCES.md](SOURCES.md)，行为合同见 [RECOVERY_GRAPH.md](RECOVERY_GRAPH.md)，采样与记忆算法见 [TEACHER_STUDENT_PLAN.md](TEACHER_STUDENT_PLAN.md)。

## 1. 先做最小端到端，不开大工程

第一条可检验链路是：

**一个实际交互窗口 → 一次有实效的扰动 → Student 而非 Teacher 继续执行 → 一段正确的双历史/标签序列 → 一次有效 Student update → 无接管的再次执行检查。**

它证明接口有功能，不证明恢复方法有效。当前 C002 只有已存 Stage3 训练里程碑，不能为这一功能检查虚构成熟整任务 Teacher；可以先用本地后续明确选定的可到交互窗口策略，或真实 Teacher 前缀接手的诊断路线，且标明证据等级。[E04]

不要求先建大 regression suite、硬件力估计器、最终多相机 CAD、所有恢复边、多技能网络或可完全克隆 Isaac 的通用 snapshot 系统。

## 2. 源码落点：复用与最小修改

| 源码/config | 可复用事实 | 建议的最小改动 | 不能假称已有 |
|---|---|---|---|
| `base_v29_common.yaml` / `base_v29_baseline.yaml`、C002 resolved | B01/B04/B05/B07、v29 robot、30 s、阶段/奖励/动作基础 | 新 overlay 只写 N01 差异；对照共享同一完整 C002 组合 | 缺独立 B05 字段不是关闭；旧 Student defaults 不是 v29 resolved [C01,E03] |
| `door_open_a2_base.py` `_a2_v27_prepare_actor_state` | 小开爪命令注入的接线范例 | 从历史 v27 flag 解耦为本轮 injector；标计划/覆盖/实效/失效，随机窗口，首轮一集一次计划脉冲 | 命令为正不保证失抓；旧 pilot 不证明 C002收益 [C03,H04] |
| 同文件 `_update_a2_v27_recovery_state` | 接触资格、正常释放排除和旧 rollback 的参考 | 新的 event monitor、物理候选落点、hold epoch；不要直接启用旧“全部退2”当主方案 | C002 当前没有启用旧恢复 [C03,E03] |
| 同文件目标/阶段条件约 18701、29732–30073 | live G/pregrasp、现有 forward readiness | 将“当前目标 phase”和“已达进展”分开；L2 的在线 base 站位使用当前门几何，不依赖 Stage0 reset | 旧 G 并非总是静态；静态可达不证明动态可恢复 [C03] |
| `staged_task_base.py` 164–220、302–338、reset/snapshot 段 | 时间与奖励现有消费者 | 单调时间/信用账本、first-attainment mask；在线恢复单独接口，不借 reset callback | 局部 timer 清零不可增加任务寿命 [C02] |
| `door_open_a2_base.py` 15964/15977/16420/16452/17591 及 `_after_reward_components` | arm return、grasp/hold、handle 回升与部分重复收入处理 | 一个共享 recovery-goal mask 处理真正冲突，从开始重新获取时生效；高水位不清 | 改一个 hold reward 不等于完成 post-release regrasp 设计 [C03,H03] |
| `_apply_delta_action_overrides`、`delta_action_base.py`、`a2_base.py` | 12D→24D、积分/scale/clamp、冻结腿与 gripper primitive | 同一 stage-blind Student 执行 adapter；Teacher 有效 target→可行 delta 标签；明示 role/stage 相关 overrides | actor81 无 stage 不保证 controller 无 oracle [C03,C04] |
| `distill_trainer_a2_base_api.py` 340–436 | 当前状态 shadow Teacher、Student forward、选中动作派生腿动作、done reset | episode 分层控制权，不用确定性前缀；动作来源记录；禁失抓即接管；Teacher/Student state export 边界 | 当前没有自动比例课程、Teacher hidden storage [C05] |
| `distill_trainer.py` 264–433、482–488 | 12D BC、recurrent split/pad、当前 rollout mask | 独立有限 sequence repository、事件采样器、有效标签 mask、prefix 重算；原 rollout storage 保留在线用途 | 当前不是跨 batch 数据库，也不是 Student RL [C06] |
| `memory.py`、recurrent actor/vision actor | 两套独立 RNN、done reset/detach | 明确 `export_state/install_state/replay_prefix` 适配层；处理不同权重版本和 active collector hidden | 不假设现有局部 restore 能还原任意 snapshot；不复制 T hidden 给 S [C08] |
| 旧 `door_open_a2_base_dagger-lstm.yaml` 与 obs yaml | 81/133/138、12D、ResNet18 + 2×256 LSTM、单 RGB | 新建真正 v29 Student resolved 组合，只复用网络/观察/训练接口；锁定 actor 图像预算 | 旧 robot/reward/PhysX 参数不能直接冒充 C002 [C07] |
| `isaacsim.py` 2360、2800–2816 与 `_push_robots` | 后端能力边界 | 后续物理扰动明确 body/frame/backend 和回读；首轮不用空施力函数 | `apply_rigid_body_force_at_pos_tensor` 当前是 `pass` [C09] |

可选新文件命名（**仅建议，不声称仓库已存在**）：`recovery_events.py` 管事件/计分，`recovery_targets.py` 管候选条件，`recovery_sequence_store.py` 管有限序列库，`base_v29_n01_common.yaml` / `door_open_a2_v29_recovery_dagger.yaml` 管显式 overlay。没有必要第一轮把整个 3 万行门任务文件重新拆分。

## 3. 新 v29 Student resolved 配方的最小合同

### 3.1 从 C002 向 Student 加接口，不从旧 Student 向 C002 猜补丁

采用已提供的 C002 task/source/assets、当前 B01/B04/B05/B07 与 robot/controller 为 authority，再加入 Student 观察、网络、Teacher loader、相机和本回包明确的执行/采样变化。只检查有机会被旧 Student defaults 覆写的关键字段，不重新审计整个 C002。

| 项目 | 本轮必须明确的值/关系 |
|---|---|
| 任务/robot | 完整 C002 push、左右侧域、`A2_Piper/a2_piper_v29`；B05 保留 |
| 物理/动作 | 当前 C002 gains、limits、gripper capability、动作 scale、delta scale/clamp、PhysX 配方；共享 stage-blind 执行差异单列 |
| Teacher/Student | Teacher actor133、Student actor81+RGB、critic138 仅训练用途、high action12、env boundary24、冻结腿接口1620/12 |
| RNN | Teacher/Student 各自 LSTM；当前可复用 2层×256；不先换网络做方法对照 |
| rollout/训练窗口 | 可保留短 rollout 作为采集分段，但跨段事件库及训练 prefix/unroll 明确；不是默认8 tick就称长历史训练 |
| 执行比例 | 新 episode assignment 实际生效；记录各实际执行者的 tick 数；旧 ratio 默认1不能留作隐式控制 |
| 成功/时间 | C002 原 task goal 保留；恢复不刷新 episode/阶段信用 |
| oracle边界 | actor白名单81+RGB；Student actuator 不使用真值 stage/contact/door 来回零、闭爪或 release |
| 评估 | Teacher执行=0、接管=0、staged reset=off、失败bank/reset=off、原K辅助=off，full loader 按既有合同 |

**一个容易遗漏的继承差异：**旧 Student YAML 明确含旧 robot/reward，还含 `num_velocity_iterations: 1`；C002 common 配方为 2。不能只改 robot 名称就认为已经得到完整 C002 Student 条件。[C01,C07] 具体合成顺序应由本地 config resolver 输出最终值，不能由 Pro 凭 YAML 片段声称已 resolved。

### 3.2 相机预算与部署可得性

本预研保守复用当前代码的**单路 216×384 RGB +81D**作为第一组 Student 方法比较的候选输入，不把未来三相机最终设计设成前置，也不宣布取消 Owner 的最终视觉路线。Teacher runtime 中的相机字段不是已建立的 v29 Student 配方。

旧 Student 候选为 trunk 上 `ego_camera`，有具体 pos/quat 和 `camera_update_period=0`；这些是软件配置，不是证明相机实际装得下、无遮挡或能以每个控制 tick 产出新画面。[C07] 在 P0 中用当前可实际安装的一路候选观察接近、握持和一次失抓；确认选定 view 对应真实 rig 的外参，再锁定它。若旧候选不对应 v29 实物安装，应在方法对照开始前换成一条现有可部署视路，并把这种基准建立与方法收益分开。

独立评估 actor 仍吃与训练相同的 216×384；`eval_camera_resolutions=[720,1280]` 只能作为录像配置，不能意外提升 actor 输入。记录真实新帧周期、到达年龄、重复帧和推理延迟；缺实测值时明确“时序未校准的仿真视觉 pilot”，不能宣称已具实机时间预算。所有 Student 比较组锁定同一实际 delivered-image schedule。

## 4. 分步实施与小范围验证

### P0-A：静态接口与一个真实输入检查

后续授权后只完成：解析新 Student resolved；确认完整 C002/B05/robot/controller；加载本地明确选定的 Teacher 三路径/既有 loader 所需资料；检查一段真实 env 观察与动作 12→24→dof 路径。没有 checkpoint 时此步停在静态设计，不伪造 checkpoint 运行。

记录 actor81、Teacher133、RGB实际shape、是否新帧、公开动作历史、raw/effective label/issued action 的一个短片段。检查 Stage0 gate 已不会在 Student 输出之外提供真值辅助，并验证 nominal arm-default 行为的转换没有目标跳变。只做一两个代表性交互序列检查，不新建庞大回归集。

### P0-B：一个事件贯穿采样和 update

在到达的真实握持窗口计划一次短脉冲，读回实效；至少有一个由 Student 执行的后续段，不能 ratio仍1。把事件跨过一个 rollout 边界写入库；以正确 prefix 完成一次更新；用零 Teacher 执行进行短闭环检查。确认：没有异常 hidden reset、没有重复奖励/补时间、没有把 auto-reset 图像接到上一集。

Student 若暂时到不了窗口，使用 **Teacher 真实前缀→Student 接手→再扰动** 的诊断路线，不用无历史 snapshot 替代；该结果只叫“接手后的局部功能验证”。一次 update 不叫 v29 蒸馏有效，更不叫全任务恢复成功。

### P1：先检查是否真的造出了可学的失败

在同一版本 Teacher 上比较短 pulse 及 sham（被分配但不实际扰动）的匹配场景。匹配指相同自然起点/门参数/随机种子和介入前轨迹，不要求不同策略在介入后的物理状态继续逐位一致。记录实际张开、接触/几何变化、短捕获域/长再接近两类比例。

若多数 pulse 没造成失抓，只校准时长/时机，不增加训练规模；若大多已经无安全落点，减弱或改变时机。保留全部 assigned 与 applied 分母，不只挑“看上去好恢复”的视频。

**必要时加一个极小的被动恢复诊断：**在少量可重现前缀中，pulse 后只维持原 arm target/名义闭爪或重放对应 sham 的短开环命令，不引入反馈纠正，再与完整策略比较新约束比例。若两者同样会自己合拢抓回，这个测试主要说明执行器恢复/几何容错，不足以证明学到了新恢复决策。它不是新增主训练组，不必遍历全域。

### P2：分离 Teacher 失败课程收益

从同一个可用 C002 起点、同样训练参数与新增兼容层，比较两臂：

| 臂 | 课程 | 共同条件 |
|---|---|---|
| **T_nom** | 名义继续训练；保留自然失败，不加计划失抓 | 同初始权重、完整门域、条件目标/连续状态/奖励修复、训练步数和 PPO 更新数 |
| **T_fail** | 同名义数据比例约束 + 校准后的计划失败课程 | 除课程外相同；实际失败数、自然/ staged 来源均记录 |

未改动的已冻结 C002 policy 可额外提供参考读数，但不能把 T_fail 额外训练后的效果直接归因成“恢复机制优于未继续训练的旧权重”。

评估两者的名义代价、受扰 assigned 总体成功，以及有效失效后新约束/完整后缀成功。只有 Teacher 从失效状态能继续完成后缀的区域，才进入可信 Student 标签区；不要求所有极端状态都成功才允许研究继续。

**图的收益不由这个两臂比较单独证明。** 如失败确实集中在错误落点，再增加一个有信息量的局部对照：固定退2 vs 条件落点，或条件落点 vs 无显式图 recurrent；共享时间/动作/奖励兼容层及失败采样。若一次性全做三图×两课程×多 Teacher，会把预研扩成无必要大网格。

### P3：固定同一 Teacher，分离 Student 访问分布与事件采样收益

选择一版 T_fail 或明确可靠区域的冻结 Teacher，统一 Student 初始化、网络、可部署相机输入、训练 token 数/更新数、Teacher query/env-step 预算。先不加辅助 loss、不做 Student RL、不换门域。

| 臂 | 实际采样策略 | 训练采样 | 能回答的问题 |
|---|---|---|---|
| **S_T** | Teacher 主导，**同样有计划扰动**；Student 只模仿 | 同样支持跨 rollout 的均匀序列库与正确 prefix | 受扰 Teacher 示范本身能传多少；不是只用干净轨迹的弱对照 |
| **S_C** | Student 主 cohort 闭环受扰，逐步 shadow Teacher 标注；无失抓即接管 | 均匀序列采样 | 访问 Student 自己的错误状态是否重要 |
| **S_E** | 与 S_C 同类采样路线 | 恢复事件平衡/保留，名义 quota 相同总量 | 短事件不被稀释是否带来额外收益 |

S_C 与 S_E 的首个 sampler 对照使用**同一份冻结 collector 数据库**、同一初始化和相同优化有效帧数，仅改变序列抽样概率，以免把不同 Student 随后收集出的不同数据误归因成 sampler。通过后才比较各自迭代采集+训练的完整闭环方法，并清楚标为综合方法结果。

S_T 与 S_C 的动作执行分布本来就是研究变量；实际失败率不可能强行相等。匹配总采集/query与优化资源，报告它们的有效失败剂量；必要时对同等事件剂量做小的补充分析，而不是隐瞒 Teacher 很少失败造成的分布差别。

### P4：决定是否升级模型/方法，而非预先全部添加

只有出现清晰问题才追加一个最有信息量的比较：标签 aliasing→observability-aware Teacher/选择性监督；接触判断不稳定→轻量辅助头；长片段训练不足→更长/连接的序列；BC闭环有稳定上限且任务reward有信号→固定条件下 Student RL finetune。每次只改变一个主因素，继续报告名义性能代价。

## 5. 样本规模：小 pilot，不宣布统计充分

第一轮完整评估可以沿用既有 **64 个自然首 episode 量级**的小评估形状；在本次建议的 64 总 episode 示例中，左右各32，七族尽量均衡，B01质量/closer按现有域记录。若本地既有64评估合同是另一种分组定义，保留原合同并写明真实分母，不擅自扩成更大预算。

从同一预先确定的场景集合做 assigned-perturb/sham 配对，配对在任务起点和注入规则上成立，不能从各策略恰好成功的交互窗口中事后挑相同“好样本”。这一级样本只用于判断主要阻断与方法方向，不足以证明每个家族/质量组合都泛化。优先看逐 episode 结果和区间，不以小样本小数点后四位包装确定性。

正式确认需要后续独立训练 seed/更多场景时，应由 Owner 再决定；本回包不申请或假定 GPU 时间，不给“先跑几百万步一定收敛”的预算承诺。

## 6. 指标：从全部 episode 到恢复后整任务成功

### 6.1 一个主漏斗，另列自然事件与正常释放

| 符号 | 定义 | 注意事项 |
|---|---|---|
| E | 所有已启动的有效物理 episode | 分 natural/staged、Student独立/Teacher前缀/assisted；工程失败另列 |
| I | 起点即分配到扰动协议的 episode | 尚未到把手也在 I 内，不能删掉 |
| W | 到达符合条件的交互窗口 | 报 W/E、W/I，暴露“根本没到失败发生处” |
| A | 实际施加命令覆盖/有效扰动调用 | 无操作的 backend 不能算A；图像扰动另列感知作用 |
| D | 实际改变 q、相对几何/速度或交付感知 | 计划值与实测效果分开 |
| F | 有效非正常失效 | 捕获失败、constraint_loss、recontrol_needed 分开；正常释放N不在F |
| R | 失效后策略确实执行一次恢复尝试 | 记录 maintain-close、reclose、撤离再接近、base重定位、重观察、bypass；不是 stage标签变化就计R |
| K | 新 constraint_epoch 内重新建立正确把手约束 | 新的 qualification，不能复用旧 streak；区分可能被动自动闭合 |
| B | 无需重抓、以有效续行/让位恢复可完成路径 | 与K分支分开，不伪称regrasp |
| G | 依 C002 原条件完成完整任务 | 同时报告恢复事件是否 assisted；K并不等于G |
| N | 正常释放 | 单列错误触发恢复次数；不人为加入失抓分母 |

自然 episode 的 F 不要求经过 A/D；它使用相同失败/后缀判据，独立汇报。一次 pulse 可以保持约束而无F，应记“抗扰保持”，不算“恢复0次所以失败”。

### 6.2 必报分母

主表至少包括：`G/E` 自然整任务成功，`G/I` 扰动分配后的总体任务成功（intention-to-treat），`W/I`，`D/A`，`F/A` 和 `F/E`，`R/F`，`K/F`，`G_after_K/F`，以及 `G_after_K/I`。无须重抓的 `G_after_B/F` 单列。

Teacher 接管救回的 G 不进入 Student independent G。Student 从自然起点独立闭环、Teacher真实前缀后独立恢复、失败后Teacher救援是三张不同表，不合并。

失败条件成功率高，可能只是策略只在容易状态失抓；失败条件率的改善不自动证明因果优势。因此同时看 assigned 总体成功、抗扰保持、名义性能，并用预先确定的匹配注入起点/少量物理失败 anchor 作机制诊断。恢复状态 anchor 的测试不是自然episode表现。

首轮主统计按“每 episode 第一个有效失效”计数，避免同一集反复开闭把分母刷大；额外给全部事件统计和重试次数，清楚标不同统计单位。

### 6.3 时延与失败原因

记录物理失效起点、监测器确认、策略动作响应、新约束、最终成功时刻。Teacher/评估器的真值确认时延不等于 Student 内部“意识到失败”的时间；主 Student 没有显式检测输出时，只报告可观察动作响应时延，不编造其隐状态检测时刻。

报告恢复成功样本的中位数/尾部时延，并同时给未恢复/超时比例；不能只对成功样本平均后声称所有失败都几百毫秒恢复。把图像 frame age 和实际感知更新间隔连到事件，检查可观察时是否已经错过可恢复窗口。

失败原因采用少量明确类别：未到交互窗口；扰动无效；空抓/抓偏；失抓后原地闭合无效；实时pregrasp不可达；base重定位失败；看不到/信息过期；回关窗口错过；握持重建但没有后缀进展；控制/时间/奖励状态不一致；Teacher未知/不可靠标签；安全终止/超时。unknown独立存在，不强制每条轨迹事后归因。

### 6.4 名义性能和正常释放代价

沿用 C002 原完成、姿态、heading、接触/力学质量口径，不降低旧门槛。额外报告完成时间、无扰动成功率变化、正常释放被误触发恢复的比例、不必要重抓/开闭次数、碰撞/不良姿态和安全终止。Stage4/5 为恢复取消局部 arm-return 冲突，不代表可以整体关闭姿态与接触质量要求。

## 7. Student 独立闭环评估合同

使用同一个完整 C002+B05 门域、同一个已锁定的可部署感知输入、同一个动作适配器。**Teacher高层执行=0；Teacher接管=0；训练staged reset/失败bank/K辅助=关闭；从自然初始分布开始；真实done才reset。**

Teacher参考与Student评估分别完整加载各自模型/配置/归一化资料，不把Teacher checkpoint直接当Student，也不在比较中只加载一部分权重而忽略输入统计。可保留不参与控制的真值评分器。若为了标签审查额外运行 Teacher，则必须是单独诊断，不可在线改 Student 动作。严禁将 training-only stage/contact/门状态以 target command、integrator override、重定位脚本等方式留在 Student controller。

至少保留：未参与训练的 pulse 持续/时机组合；一种命令保持闭合但实际失约束的自然/物理扰动；无计划扰动自然失败；正常释放与接近回关边界。未能实现其中一类时，应缩小结论范围，不把“未测试”写成通过。

机器人/门参数保持 C002 支持范围内；新家族或超范围门质量可以后续单列 OOD，不能第一轮混入后用 domain change 解释所有差别。视觉泛化和控制恢复首先分开，方法收益对照期间不换 camera/CAD。

## 8. 继续、简化与改方向条件

| 观察 | 下一步 | 不应做什么 |
|---|---|---|
| W/E很低 | 先改善/启动名义接近，或用真实Teacher前缀做局部功能研究 | 说恢复网络失败；大量制造从未真正到达的stage标签 |
| A多但D/F很少 | 校准实际作用时长/时机，检查空backend | 加训练步数或报“触发率很高” |
| 多数F已无安全目标/时间 | 缩轻训练课程、保留难例为边界评估；检查感知时延 | 把全部难例删除分母或无限延长episode |
| Teacher K高但后缀G低 | 优先修落点接续、回关/重新解锁、奖励/时间冲突 | 先加Student蒸馏复杂度 |
| T_fail相对T_nom没有可见收益 | 检查被动合拢/课程效应，必要时缩成更简单鲁棒baseline | 为了novelty继续堆恢复图 |
| Teacher可靠，S_C好于S_T | 保留Student执行和同状态标注主线 | 继续默认ratio1并假称Student有闭环训练 |
| 相同数据库S_E不优于S_C | 去掉无收益的过度分桶/重加权，保持简单序列库 | 以不同数据量掩盖sampler没有收益 |
| 条件图不优于无显式图 | 保留物理事件与防重置合同，简化图调度 | 因旧名称N01承诺了图而强行保留 |
| 相似Student历史对应相反Teacher标签 | 优先获取信息、适配Teacher或选择性监督 | 把不可辨识问题全部归为网络太小 |
| 独立评估比接管训练掉很多 | 看Student是否从未练到关键失败后段；减掉抢救，保留失败序列 | 把Teacher接管后的成功算自主恢复 |
| 名义性能显著受损 | 保留名义quota，检查新reward/Stage0适配器与正常释放误报 | 一味加大扰动覆盖所有极端样本 |

这些是决定下一步的诊断规则，不是需要先全部达成的庞大硬门槛。局部接口研究可以推进；整任务/传递结论必须等相应证据，二者不互相冒充。

## 9. 最小日志对象示例（拟新增，不是已存结果）

```text
episode_id, side, family, fixed_door_params_id, initial_seed
source = natural | staged | teacher_prefix
assigned_protocol, actual_executor_tick_counts, actor_input_recipe
interaction_window_count, applied_count, actual_effect_count
first_failure = {type, tick, physical_context, delivered_image_age}
recovery = {attempt_type, landing, new_constraint_tick, bypass,
            teacher_after_failure, teacher_ever_in_episode, task_goal_afterward}
outcome = {c002_goal, clean_quality_metrics, elapsed_ticks,
           termination_reason, label_unknown_fraction}
```

自动日志须从真实执行/状态生成；不能先填一份设计上“应该发生”的事件表再当 runtime evidence。
