# N01 Pro回包：一次定向核对与设计判断

2026-09-20 HKT；Main整合，动作/循环历史接口由一位只读IsaacLab reviewer独立核对。状态：**已归档、已定向核对；设计讨论继续，实施未批准**。证据等级为 **INSPECTED**。来源是Owner本对话附件，没有从Drive寻找答案。

## 结论

Pro对现有DAgger、Student信息边界和旧恢复局限的主要描述与当前源码一致，未发现需要推翻其研究方向的事实错误。值得继续的是：把恢复落点定义为可继续完成任务的物理条件；让Student在自己的失败轨迹上取得有效专家监督；把恢复后完成原任务作为目标。

需要保留三个限定：stage-blind执行适配器是控制接口改动；完整episode前缀重放是新增训练方案，不是“现有RNN每8 tick失忆”的修复；恢复目标与现有stage奖励/时间预算之间仍需设计。Pro的图、课程比例、采样窗口和比较方案均未成为Owner批准的实施合同。没有新增恢复或蒸馏效果证据。

## 1. 本次证据范围

- 主底座为完整 `v29-c002-baseline`，保留B05；研究分支为 `codex/v29-n01-pro-20260920`。选定的13份当前任务相关源码/config与审阅分支直接逐字节比较一致，清单见 [FOCUSED_SOURCE_BINDING.json](FOCUSED_SOURCE_BINDING.json)。这不是整个C002的再验收。
- 当前source优先；已存C002 resolved config、D056/D060验收与D061/D064运行记录从原[本地事实](../../../v29/pro_handoff/20260920_n01_recovery_transfer/LOCAL_FACTS.md)和[证据导航](../../../v29/pro_handoff/20260920_n01_recovery_transfer/SOURCE_INDEX.md)绑定。本次没有唤醒或轮询GPU0/GPU1日志。
- 原件全部保留，见[README中的六份原件](README.md)。其建议是研究材料，不是执行命令。附件内接手prompt与Owner本轮请求分开保存；Owner另要求的下一任务planner prompt仅在最终回复提供。
- 本次未修改生产source/config/assets，未运行仿真、训练、评估、GPU任务或测试，未创建实验预算，未进行Git提交或外部发布。

## 2. 实际源码/config事实

| 问题 | 核对结果 | 对N01设计的约束 |
|---|---|---|
| 动作由谁执行 | [DAgger配方](../../../../gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml)第52、64行附近：rollout为8 tick，`enforce_teacher_rollout=true`、`ratio_teacher_rollout=1.0`，配置提示人工分run降低，没有自动退火。[A2 trainer](../../../../gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py)第361、373、391–411行：每步查询Teacher并forward Student，固定batch前 `int(N*ratio)` 个env选Teacher高层动作，再由选中命令计算腿动作。 | 默认是Teacher控制的闭环；Student forward不代表Student访问了自己的失败状态。固定env前缀也不是随机、按episode分层的执行分配。 |
| 当前学习目标与数据窗口 | A2 trainer第437–464行用raw Teacher 12D动作做BC目标；[generic trainer](../../../../gr00t/rl/trl/trainer/distill_trainer.py)当前目标为BC。[PPO父循环](../../../../gr00t/rl/trl/trainer/ppo_trainer.py)第719行清当前rollout storage。 | 有Student执行＋在线专家查询的代码能力，但没有已实现的跨rollout事件序列库/DAgger数据聚合；也不能因继承PPO类就称Student已做RL恢复训练。8 tick是数据收集/更新窗口。 |
| Teacher循环状态 | A2 trainer第417–435行按真实done reset；[recurrent actor](../../../../gr00t/rl/trl/modules/actor_critic_modules_recurrent.py)第145–153行的`clear_rollout`只detach hidden。Teacher hidden未存入当前蒸馏storage。 | Teacher在线沿实际执行轨迹推进记忆，rollout边界不归零；新增离线重标注不能只取失败时物理状态而忽略此前Teacher输入历史。 |
| Student循环状态 | Student按done reset；[vision actor](../../../../gr00t/rl/trl/modules/vision_actor_critic_modules.py)第218–224行清观察buffer。PPO父循环第1003–1024行使用rollout时保存的边界hidden训练序列。 | 在线Student也不会每8 tick清零。更新权重后继续使用先前hidden是现有近似；尚无证据证明它就是当前瓶颈。 |
| Student 81D＋RGB | [观测配方](../../../../gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml)的Student view不含显式stage、sim contact/hand-force、door角/位姿真值。Teacher actor133D、critic138D有更丰富真值。冻结A2_Base的1620D（30×54）历史属于底层腿策略。 | 不能把Teacher判据直接放进部署Student恢复控制器，也不能把底层腿历史算成Student已具备的完整交互历史。RGB可能承载相关线索，但可辨识性与视野尚未证明。 |
| 81D中的动作历史 | [a2_base.py](../../../../gr00t/rl/envs/base_task/a2_base.py)第1170、1221、1348–1357行：`actions`为12D腿动作＋6D累计arm target＋1D gripper，共19D；[delta_action_base.py](../../../../gr00t/rl/envs/base_task/delta_action_base.py)第62、147–148行的`delta_actions`另含积分前6D增量。 | `actions`不是选中的12D高层command。扰动插入点与执行适配器必须说明哪些命令实际送出、哪些target进入历史，以及Teacher共享观测怎样保持一致。 |
| Stage0动作状态覆盖 | delta积分之后，[door env](../../../../gr00t/rl/envs/door/door_open_a2_base.py)第8899–8914行按Stage0覆盖arm accumulator：非canonical路径置零，canonical路径回到physical origin。 | 这是依赖真值stage的执行语义，值得纳入部署接口讨论。跳变的是命令target，不能写成关节物理位置/root被瞬移。 |
| 旧恢复路径 | source中保留v27路径；已存C002 resolved config没有 `a2_v27_recovery_*` / `a2_v27_perturb_*` 字段，解析结果为未启用。旧退边统一回Stage2。 | 源码存在旧恢复不代表C002已启用，不能据此宣称当前Teacher接受过有效恢复课程。 |

IsaacLab本机 `articulation.py` 的 `set_joint_position_target` 与[官方实现说明](https://isaac-sim.github.io/IsaacLab/main/_modules/isaaclab/assets/articulation/articulation.html)均区分target buffer和实际状态；这一API核对仅支持上表的target/state区别。

## 3. 恢复图：可部署部分与真值依赖

Pro用A（获取接近条件）、C（建立握持）、M（操作门）、P（通过）组织四类目标，提出13条候选边。落点从原地重新闭合、实时pregrasp，扩展到base重新站位、重观察、直接通过或结束尝试。当前把手G已有实时更新；待解决的是目标可执行性、延迟与可达性，不是已确认存在“G不刷新”故障。

**训练图可以使用特权信息，部署执行接口必须单独交代。** Pro建议先用一个recurrent actor，Student不直接读取sim stage/contact；图可承担训练课程、奖励和标注组织。若实际执行还通过图中的oracle谓词改动作、清target或切换控制，单看actor的81D＋RGB便不足以证明部署信息闭合。当前Stage0覆盖是一个具体接口事实，不等于所有训练stage/reward真值都必须删除。

待定接口包括：

1. **恢复时保留哪些状态。** Pro主张在线恢复不物理reset、不把门速度归零，保留全局episode时间、已取得进展、arm动作累积、Teacher/Student hidden和底层腿历史；真实loss后只重新建立当前接触资格。它提出区分task phase、progress high-water、budget stage和epoch，另做shadow时间核算以避免反复领取预算/进展收入。这些都是新设计，当前没有完整实现。
2. **奖励能否支持落点。** Stage4/5的arm-return/握持冲突要讨论；L2 base重定位还受到Stage1 base-still/readiness（door env第18701、29785行附近）及Stage1/2 forward-creep惩罚（第17930行附近）影响。若把恢复仅写成“回到早期stage”，可能一边要求base移动、一边惩罚移动。这是根据当前source得出的接口问题，尚不是已运行发现的Pro代码缺陷。
3. **什么时候真的需要恢复。** 捕获失败、真实loss、接触短闪断、正常release、可继续通过和无可行恢复应分别定义；不能把“发出open command”或“曾经重新接触”直接计为成功恢复。

第一阶段先限定正常释放之前的捕获失败/失抓，并优先讨论L0原地闭合和L1实时pregrasp，是Main建议的最小起点。L2/L3是否必须首轮纳入由任务可行性决定，不要求先实现全部13条边。

释放后因回关重新控门的P→A，Pro建议可作为后续任务层恢复纳入N01。Owner在D023曾将强回弹后重抓把手移到N02；**本次未采纳分工变化，D023边界继续有效，交给Owner裁定。**

## 4. Teacher与Student：哪些是建议，哪些仍未知

| 分类 | Pro方案或本地判断 | 当前限制 |
|---|---|---|
| Pro推荐：Teacher | 同一起点、额外训练量匹配的名义续训Teacher与失败课程Teacher比较。先用自然失败和短开爪脉冲，读回夹爪运动与真实几何loss，学习恢复后继续完成原任务。3/6/12 control tick（.06/.12/.24s）、70/30名义/指定扰动、每集一次计划脉冲为起始建议。 | 数值没有经本地校准或Owner批准。gripper命令具有二值语义，幅度不等于扰动强度；保住原抓握、自动重新闭合和主动重抓需区分。 |
| Pro推荐：Student闭环 | 受扰Teacher示范warm start之后，由Student实际执行受扰闭环；Teacher在Student当下状态和真实历史上持续shadow查询。按episode随机、分层分配控制归属，Teacher前缀、失败后接管和自然起点全Student分别报告。 | Student失败分布上的Teacher标签可能不可信；有限输出不等于可用专家。无条件接管会污染“Student自主恢复”分母。 |
| Pro推荐：跨rollout序列 | 有限事件序列库、label有效性mask、事件均衡采样、保留正确RNN前缀；比较同数据的均匀采样与事件采样，避免把更多失败数据与采样收益混在一起。64–128 loss unroll及50/50配额是提案。 | 当前无该库。全episode前缀在当前权重下重放是Pro的一种较强一致性方案，涉及完整输入/图像处理与归一化、不得推进物理、不得重复消费当前观测；成本和必要性待设计。它不是N01所有实现的强制前置重构。 |
| Pro推荐：网络与接口 | 首候选保留ResNet18＋2×256 LSTM，使用stage-blind执行适配器和effective-increment标签；所有Student比较共享该接口并报告名义代价。 | 后两项改变了控制接口，不是单纯“换数据”。target与实测q、增量尺度/限幅、known-command pulse与hidden actuator fault的历史语义尚未定案。 |
| 本地推断 | Student执行分布、失败暴露、专家可靠性和信息条件均可能成为瓶颈；仅提高恢复片段比例不能解决不可观测的专家动作冲突。 | 未做消融或运行诊断，不能认定其中某项已被证实为主因。 |
| Local-only未知 | 可用Teacher在完整C002/B05上是否已形成足够名义/恢复能力；Student真实相机视野与v29组合配方；扰动实际loss人口；prefix/relabel内存与运行成本；自然起点自主完成率。 | Pro输入不含权重或本机Isaac环境。当前回包没有新的仿真、训练、推理或效果实验。 |

建议的结果漏斗是完整记录eligible→实际注入→物理扰动→抓握受损/真实loss→可恢复→重新接触/握持或直接通过→原任务完成，同时单列正常release、未失抓、接管与未知标签人口。当前仅作为研究定义，不在本轮建设统计框架。

## 5. 两个本地执行条件与已存runtime边界

- [IsaacSim backend](../../../../gr00t/rl/simulator/isaacsim/isaacsim.py)第2351–2370行的通用 `apply_rigid_body_force_at_pos_tensor` 当前为`pass`；[legged base](../../../../gr00t/rl/envs/legged_base_task/legged_robot_base.py)的`_push_robots`在Isaac路径触发设置速度事件。因而不能把该路径当成已实现的连续外力注入。它不证明IsaacLab所有外力接口不可用，本轮也不修复该backend。
- 旧DAgger配方的PhysX velocity iterations为1，C002 common为2；旧配方RGB为trunk ego、216×384、`camera_update_period=0`，eval分辨率另为720×1280。仅替换robot配置不能证明已经得到完整C002 Student resolved recipe。现有软件单相机默认只是候选；v29物理H180/F45 rig及Owner尚未最终裁定的部署光学不能被悄悄重选。

D056/D060证明的是C002实现的有界验收与既有训练批准。输入包所用最近已审阅的A组3000里程碑为D064：左右历史最高到Stage3，Stage2 both-contact打印.4098，grasp-complete/to3打印.0001，Stage4/5和goal打印0；这些是staged-training日志，四位小数的0不等于从未发生，也不是自然episode成功率。该归档尚无最终64自然评估，数值loss仍为NOT_OBSERVED。这里只引用既存记录，不声称代表本次归档时正在运行任务的最新状态。

GPU1为v29−B05消融，不能替代N01的完整C002＋B05底座。原GPU0/GPU1任务与持久化等待继续由原监督合同处理。

## 6. 文献结论与核对深度

Pro共列11项参考，完整出处及其自述检索限制见 [SOURCES.md](original/SOURCES.md)。本地只对以下三项的一手摘要/落地页做了一次身份与问题定位核对，没有复核全部论文全文，也没有完成新颖性审查：

| 一手来源 | 能支持的研究动机 | 不能外推的结论 |
|---|---|---|
| [DAgger，Ross等，2011](https://proceedings.mlr.press/v15/ross11a.html) | 在学习者诱导的状态分布上取得专家监督，是顺序决策模仿学习的重要问题。 | 不证明本项目默认Teacher rollout=1已形成同样分布，更不证明恢复能力自然传递。 |
| [A2D，Warrington等，2021](https://proceedings.mlr.press/v139/warrington21a.html) | 非对称信息下，固定特权专家的动作可能不适合部分可观测Student；专家适应值得考虑。 | 不证明必须立即加Teacher adaptation，也不指定本项目可部署的恢复接口。 |
| [RecoveryChaining，2024/2025](https://arxiv.org/abs/2410.13979) | 恢复可回到不同的名义技能/状态集合，目标选择可以成为方法问题。 | 不证明A2＋PiPER应采用相同技能架构、所有13条边都必要或本文N01已有novelty。 |

其余八项，包括Pro讨论的DART、Recovery RL、HG-DAgger、Miki、R2D2、ReSYNC、CritiQ/ReTRy及shaping，保持“Pro引用/未在本地逐项复核”的来源标记。本地没有将其实验结果升级为C002事实。

## 7. 待定选择与最小下一步

下一位N01 planner应先交付一个可审阅的最小设计，而不是重新审计C002或立刻启动PPO/蒸馏。需要收敛四组决定：

1. **范围与恢复语义：** 先覆盖哪些真实失败与L0/L1落点，L2/L3是否不可缺；如何保持原episode时间/进展并处理相关奖励。释放后重抓若改归N01，明确提交Owner采纳。
2. **Teacher资格与课程：** 哪个现有Teacher可用于最小功能链；open pulse如何真正造成目标失败；Teacher在Student状态上哪些标签可靠，何时才值得额外适应训练。
3. **Student执行与记忆：** stage-blind接口的最小改动、19D action history/6D delta/12D监督的一致关系；先采用哪种足够的循环状态与数据方案，再按实际需要增加跨rollout事件库及prefix重放。确认v29 Student resolved组合和相机输入。
4. **可区分的比较：** Teacher恢复与名义代价、Student自主恢复、Student执行数据与事件采样各自怎样比较。给出最小功能演示的实际操作路径和预期可见信号，预算/长跑待Owner另行授权。

建议采用“局部真实失抓→可达落点→恢复→继续原任务”的最小链条；先设计一条可执行路径及Teacher→Student监督路径，再按需要扩展图、网络或数据工程。Pro的P0/P1/P2/P3顺序可以作为候选拆分，不是已启动的执行队列。

当前已完成的授权工作是原件归档、一页解释、本次定向核对，以及[novelty研究结论和待决项](../../../novelty/documents/20260920_n01_pro_review_and_next_step.md)落盘。方法有效性、部署效果和新颖性仍待后续证据。
