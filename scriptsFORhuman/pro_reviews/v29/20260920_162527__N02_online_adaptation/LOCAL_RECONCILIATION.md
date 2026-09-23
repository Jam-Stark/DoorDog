# N02 Pro回包：定向核对、模型更正与设计判断

2026-09-20 HKT；Main整合，两个只读子任务分别核对控制/信息合同及离线模型。状态：**归档与一次定向核对完成；设计继续，实施/实验未批准**。本地证据等级 **INSPECTED**；Pro的CPU模型执行证据单独标识，不能升级为本机仿真、N02在线收益或硬件证明。

## 1. 总体判断与来源

Pro没有预设感知网络是瓶颈，明确将可执行行为、训练暴露、信息/历史、网络表示分开；也没有把旧v27 shadow或UniFP/SixthSense结果直接套到C002。其收敛方向值得继续：当前交互有效性＋动作条件进展/通行风险，先比较已有LSTM，再决定辅助头。Teacher与Student分别定义输入、历史和监督，Student必须亲自执行。

当前回包有可追溯的CPU建模材料，主表的条件性姿态结论与已存数据一致；发现一项夹持法向力约束遗漏，详见第4节。控制建议还需要明确候选后的续接控制，以及fully_clear与逐tick stage收入的关系；这些是设计未决项，不是新发现的运行故障。

- 唯一答案来源是Owner本对话的ZIP。原ZIP和46份文件全部原样保留，含7份Python脚本、依赖说明、四份模型输入、数据/日志/数组和四张PNG。见[归档入口](README.md)和[接收记录](RECEIPT.json)。未从Drive寻找答案。
- 主底座为 `v29-c002-baseline`，审阅分支为 `codex/v29-n02-pro-20260920`，保留完整B05。四份返回模型输入与本地交付/当前URDF直接比较一致；URDF、delta动作、门参数及handle源四份文件与N02审阅分支一致，见[内容绑定](FOCUSED_INPUT_BINDING.json)。其余相关语义按当前source定向读取，没有全C002复审。
- 已存runtime范围沿用[输入事实](../../../v29/pro_handoff/20260920_n02_online_adaptation/LOCAL_FACTS.md)和[证据导航](../../../v29/pro_handoff/20260920_n02_online_adaptation/SOURCE_INDEX.md)。D056/D060是实现验收；输入包A3000/D064为对应时点的staged-training记录，不是自然成功率，打印0不是从未发生，数值loss仍NOT_OBSERVED。本次没有轮询当前训练任务。
- 本地没有执行附件脚本、安装依赖、重跑求解、仿真、训练、评估、GPU操作或测试，也没有修改生产源码、提交Git或外部发布。附件中的命令和接手文本只作材料。

## 2. source/config与信息、动作、历史

| 议题 | 当前事实及本次判断 | 证据/边界 |
|---|---|---|
| 先找能力缺口 | 当前Teacher已有133D、两层256 LSTM。其门质量/几何、门角、stage与sim指部净接触力不能当作部署可得信号。 | [Teacher观察](../../../../gr00t/rl/config/obs/wbmanip/door_open_a2_base.yaml)；[Student观察](../../../../gr00t/rl/config/obs/wbmanip/door_open_a2_base_dagger.yaml)。没有证据认定网络容量是首要瓶颈。 |
| Student信息 | 81D＋RGB，没有显式门角/门位姿/质量、stage、接触力或base linear velocity。q/qdot、gravity、base omega和动作/命令历史可用；硬件effort/电流精度与时序未核验。 | Teacher真值可作模拟监督/诊断，不可静默进入Student actor或部署候选选择器。依赖门坐标/几何的小模型也需说明Student如何获得它们。 |
| 力的含义 | net指部接触、handle-filtered contact、PD估计effort、实际关节力矩和全身wrench不是同一量；静止握持不等于零负载。 | [door env](../../../../gr00t/rl/envs/door/door_open_a2_base.py)接触helpers第18558行起、观察第28498行起。Pro正确保留无接触时负载undefined，而风险仍可定义。 |
| 动作能力 | 高层12D为base5＋arm6增量＋gripper1；A2_Base被冻结。不是自由TCP wrench或任意腿力矩接口。 | [a2_base](../../../../gr00t/rl/envs/base_task/a2_base.py)第1174–1220行；[delta动作](../../../../gr00t/rl/envs/base_task/delta_action_base.py)第59–105行。提出姿态/保持动作不等于低层已经兑现。 |
| 动作历史 | Student `actions`为12D腿动作＋6D累计arm target＋1D gripper，另有6D `delta_actions`；BC监督为12D高层动作。 | 沿用已完成的[N01定向核对](../20260920_153418__N01_recovery_transfer/LOCAL_RECONCILIATION.md)。原始动作、经限制的目标、实际运动与力都要区分。 |
| 默认DAgger | `enforce_teacher_rollout=true`、Teacher执行比例1.0，固定env前缀，无自动退火；当前数据按rollout更新。 | [配方](../../../../gr00t/rl/config/exp/wbmanip/door_open_a2_base_dagger-lstm.yaml)和[A2 trainer](../../../../gr00t/rl/trl/trainer/distill_trainer_a2_base_api.py)。Pro提出随机执行归属/聚合为新增设计，比例示例不是已批准参数。 |
| RNN与Student轨迹 | Teacher/Student各有hidden，在线沿实际轨迹推进、真实done时reset；8 tick是数据窗口而非每8 tick清零。 | Pro没有复制Teacher oracle hidden给Student。新增replay/relabel需要正确prefix；已在线保存的有效Teacher标签可直接使用，不能强制所有场景都先做完整快照工程。 |
| 当前与未来 | `p_useful_grasp`是当前交互估计；`Q(h,A,c)`是给定动作及后续控制的未来结果预测。 | Pro正确区分同窗估计、未来预测和未执行动作的反事实；短/失败/无接触及未来被终止截断的人口不能被补零为“安全”。 |
| C002/B05与旧shadow | 质量与closer交叉，接触几何/传力会影响响应。旧shadow有模拟effort/接触并排除部分短episode，未反馈actor。 | [门参数](../../../../gr00t/rl/isaac_utils/playground/env_rand/door_v29_parameters.py)及[handle](../../../../gr00t/rl/isaac_utils/playground/env_rand/handle_v29.py)已绑定分支。旧离线R²不证明C002可辨识或Student部署可用。 |

Pro保留q/target/真实响应的区分与IsaacLab target语义一致；设置target不直接写物理关节状态。API由本地IsaacLab与[官方文档](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.assets.html)定向核对，未扩展为物理引擎审计。

## 3. Owner行为目标与两项待定控制合同

| Owner目标 | 新信息能改变的动作 | 仍需的行为/奖励/暴露支持 |
|---|---|---|
| 普通门近中性、arm主导 | 在有效抓握下选较小arm推进；base可平移/转向维持可达性。 | arm主导不等于base固定。当前策略可能未到达相关后段，需能实际执行的对照和相应暴露。 |
| 困难门有条件roll/pitch | 对相同任务方向比较中性/重定位/倾斜的可达、PD和预期进展，收益确切时才倾斜。 | 不以质量或policy失败直接定义困难；控制跟踪、姿态代价和支撑仍须实际验证。 |
| quiet hold | 保持可靠抓握、抑制门速/冲击，同时调整base路径并继续通过。 | Stage4/5握持、接近handle、回臂/回柄及时间目标要一致；不能靠永不放手取得好指标。 |
| controlled swing | 联合选择有限开向速度、释放时机和身体通过路径。 | 当前旧controlled_fling函数scale=0；不能只打开一个奖励便认定完整模式选择已存在，也不能靠撞upper limit吸能。 |
| 强回弹时防止trunk碰撞 | 预测释放后门与全身包络的净空，必要时延迟释放、hold重定位或改路径。 | root越门不代表全身离开扫掠区；arm可达性与后腿/非授权arm接触都相关。无法hold时不能默认零base速度安全，也不能调用尚未实施的N01恢复。 |

以下两项会实际影响实施，应由planner具体化，不能只停在概念：

**A. 候选之后的控制器 `c`。** Pro [FULL_REVIEW](original/FULL_REVIEW.md)第39行给出 `Q(h,A,c)`，候选约0.2s、风险窗0.6–1s；但[控制伪代码](original/CLOSED_LOOP_CONTROL_PLAN.md)第88–98行每次只执行首步后重规划，[采集伪代码](original/TEACHER_STUDENT_PLAN.md)第65–74行又含Teacher/Student执行分配。必须说明A是完整实际序列还是承诺的首段，之后由哪个版本/执行者续接、何时可重规划。预测窗内factual标签应对应同一个续接协议；记录了候选名不等于候选被完整执行。无需先建设精确反事实快照，最小随机factual动作采集可以解决首轮覆盖，但也要把续接条件固定或显式条件化。

**B. `fully_clear`与逐tick stage收入。** Pro要求完全离开后允许门正常回关，不再持续要求门打开。当前door env第29920–29939行的Stage5收入仍依赖root>0、handle<0.2及hinge阈值，完成条件另为root>1.5（第29941–29942行）；[staged task](../../../../gr00t/rl/envs/base_task/staged_task_base.py)第302–317行逐tick重算奖励，[env配置](../../../../gr00t/rl/config/env/door_open_a2_base.yaml)第236、241行保留阶段收入且禁用累积。若fully_clear先于最终完成成立，正常回关仍可能损失Stage5收入。因此 `need_door_assistance/fully_clear` 需同时解释stage收入与完成语义，不能只修改回臂/回柄，也不能把已有stage奖励当一次性里程碑。这是待设计的具体冲突，不是已经通过运行证实的主瓶颈。

## 4. 建模实际执行证据与一项更正

### 4.1 已交回什么、能证明什么

| 材料 | 一次只读核对结果 | 可支持的结论 |
|---|---|---|
| [execution_summary](original/results/execution_summary.json)、[run.log](original/results/run.log)、[states](original/results/states.json) | 42姿态，26解出/16未解；26×4方向＝104主记录。模型28 links、20 actuated DOF＋6维浮动基座，URDF质量45.6448083kg。 | Pro回包具有相互一致的CPU执行证据，非仅脚本存在。本机未复现，16未解不等于全局不可达。 |
| [PD日志](original/results/pd_envelope.log)、[PD数据](original/results/pd_target_limited_force.csv) | 同104键，求解状态均OPTIMAL；20N所需arm target在限位内。 | 末轮结论确已纳入PD目标角补算，不能只引用较早arm/足地表。 |
| [validation](original/results/validation.csv)、[独立平衡记录](original/results/independent_balance_checks.json) | 最大Jacobian差约2.738e−10、重力差4.304e−8，最小M特征值2.963e−4；104条主LP最大平衡残差5.522e−12。 | 支持该实现的数值/符号内部一致性；“独立平衡”仍共享同一模型输入，不是独立动力学库或实机验证。 |
| [脚本](original/modeling/run_analysis.py)、[刚体实现](original/modeling/robot_model.py)、[PD层](original/modeling/pd_envelope.py) | 固定世界TCP完整位姿、base xyz与四足球心，改变姿态后重新解腿/arm角；原始状态记录中q确实改变。力定义为机器人对门+Fd，反作用为−Fd；重力、浮动六维平衡和PD不对称限矩符号一致。 | 匹配姿态比较不只是旋转坐标标签；但仅在列出的F0-like工作点/方向、URDF和抽象接触下成立。 |

主模型基座高度从配置初始.55m调整到静态接地参考约.51467m，所有匹配姿态共用该高度；不能算作roll/pitch收益。base前后5cm另表处理，未检查门侧净空。足地用摩擦内棱锥，腿力矩可自由分配；它对真实圆摩擦锥较保守，对省略的抓握、碰撞及冻结低层兑现又较乐观，因此不是实际整机能力的严格上界或下界。

### 4.2 保留的关键数值

| CSV条件 | 中性→变化 | 应怎样解释 |
|---|---|---|
| `mid105 / opening_normal_tangent / neutral→roll+8` | arm 447.885→520.894N（＋16.30%）；足地/腿119.694→120.044N（＋0.292%）；同20N时峰值arm力矩反增1.300% | 容量上界、支撑瓶颈和当前负载下的低扭矩姿态不是同一个优化目标。 |
| `low90 / press_down`，含PD | 中性132.221N；pitch＋8为123.965N（−6.245%）；pitch−8为150.787N（＋14.042%） | 控制目标限位可以反转纯限矩下的姿态排序。 |
| 独立中性base前移5cm | 足地/腿119.694→138.865N | base重定位可能重要，但不属于纯倾斜收益；没有据此建议实际向门移动5cm。 |

数据来自[方向主表](original/results/directional_force.csv)、[PD表](original/results/pd_target_limited_force.csv)和[独立平移表](original/results/separate_base_translation.csv)。[图1](original/results/01_arm_vs_supported_capacity.png)和[图4](original/results/04_pd_constraint_reverses_ranking.png)已查看，与上述主数据相符。图表不含已验证真实B05抓握。

### 4.3 夹持法向力约束遗漏：原件保留，解读必须修正

Pro [模型报告](original/DYNAMICS_AND_FORCE_ANALYSIS.md)第90–94行及[run_analysis.py](original/modeling/run_analysis.py)第83–95行，在假设两指相反法向、各自 `0≤Ni≤Nmax` 下，仅采用：

`F (||d_t|| + μ |d·n|) ≤ 2 μ Nmax`。

这条不等式仍是一个较松的必要界，但不足以表示所述单指限力下的完整方向容量，还必须满足：

`F |d·n| = |N1 − N2| ≤ Nmax`。

因此，对非零法向分量，应再与 `Nmax / |d·n|` 取更紧界；纯法向最多Nmax，不是2Nmax。这仍只是在忽略完整接触力矩平衡的两指纯合力抽象下的必要界，不是实际抓柄能力。

[sensitivity.csv](original/results/sensitivity.csv)受影响共156行，均为 `direction=press_down`：

| kind | 行数 | 原grip_only_force_N | 加遗漏约束后的更紧必要界 |
|---|---:|---:|---:|
| `pinch_mu_two45N` | 78 | 90N | 45N |
| `pinch_mu_PD_q014` | 78 | 36.4N | 18.2N（仅在将18.2作为假设单指上限时） |

18.2N来自假设指位±.014m、目标0和Kp1300，不是实际接触读数。水平夹持情景18/36/72N及14.56N不受此遗漏影响，arm/足地/PD主表也不受影响；这些水平数值仍是条件模型，不是B05或硬件传力测量。

没有修改原脚本、CSV或图，也没有运行“修正后模型”。后续若继续使用该夹持模型，应先修正这一局部约束并针对受影响情景重算；当前可直接保留不受影响的主表与“条件性姿态”判断。这不要求先重建完整抓握仿真框架。

### 4.4 仍为UNKNOWN或NOT_RUN

- arm100N·m、finger45N是C002仿真配置，不能当作已确认硬件持续/峰值出力；finger的18.2N同样是条件假设。
- URDF与USD运行惯量/碰撞等价性、七族B05实际接触wrench、真实摩擦/形状承载、碰撞/相机塔净空、冻结A2_Base兑现、速度/温升/电流等均未验证。
- [惯性敏感性](original/results/inertial_sensitivity.csv)只在零速度瞬间使用 `g+M[:,arm]qdd`；没有非零速度Coriolis项、时间积分、门—机器人闭环动力学，也未给该瞬态加入PD envelope。它不是甩门实验。
- 原Isaac物理、Teacher/Student策略、在线适应与硬件：**NOT_RUN（本Pro回包范围）**。本地复现模型：**NOT_RUN**。这些状态与“Pro CPU离线模型已交回执行证据”并不矛盾。

## 5. 文献核对与适用边界

本地只围绕方法输入、时间语义和控制用途检查关键一手段落；没有复现论文，也没有进行全面新颖性审查。

- [UniFP v2 §3.2–3.3](https://arxiv.org/html/2505.20829v2)：历史状态估计连接低层力/位置命令控制，上层视觉模仿使用该低层接口。Pro的借鉴解释一致；不能由此认为冻结A2_Base已有同等force command能力，也不能自动选择fusion/diffusion。
- [SixthSense v1 §V-A/B/F](https://arxiv.org/html/2605.01427v1)：输入含归一化torque；50帧/50Hz用于同窗接触序列，非给定未来动作的门预测；文中实机配置报告约0.5s一次forward，已包含所述10次refinement，不能再机械乘10。Pro的时间/输入限制说明一致；它不证明C002的20ms控制时限或Student传感合同已满足。
- [Orsolino等的wrench可行性摘要](https://arxiv.org/abs/1712.06833)：执行器与接触约束共同限制能力，支持分层建模动机；不能替本回包自写模型证明正确。这里只核对摘要。
- DAgger一手问题定位沿用刚完成的N01核对；本次不重复全文审阅。其学习者分布观点不等于现有默认全Teacher采样已充分覆盖。

## 6. 修订后的研究判断、比较与下一步

Pro从“负载大→倾斜增强力”的初步想法，收敛到“先判断传力和命令兑现，再比较几何/PD/支撑与动作后果”。PD补算、正负姿态结果、base平移分表及最终结论均完整保留。回包没有提供完整云端迭代会话，本地不补写未提供的过程。

本地同意将**当前交互有效性＋动作条件进展/风险**作为候选，而不先估全套物理参数或全身wrench；但它们能否从Student81D＋RGB在短历史/遮挡下校准、能否改变动作，均为待验证推断。辅助头尚未成为Owner选定架构。

Pro的顺序对照可用于区分：A原C002；B相同行为支持＋相应暴露的原LSTM；C在B之上加辅助信息及控制连接。A→B只能称行为/暴露组合收益，B→C才检验辅助信息的额外收益；如要进一步分开行为与暴露，只增加针对性的比较。Teacher与Student在各自相同信息预算内比较，Student自然起点独立闭环不允许Teacher代控。头误差降低、head被使用与任务收益是不同层证据。

下一位planner只需先收敛四组选择：

1. 第一条可执行行为：quiet hold、有限推进、受控release＋身体路径选哪一小组；必要的assistance/clearance/stage收入/完成语义是什么。
2. 动作与标签合同：A承诺多久，c由谁/哪个版本执行，风险窗如何覆盖释放后的实际暴露；用最小factual数据先证明候选后果可区分。
3. Teacher/Student信息与历史：哪些输入真实可用、相机/时间延迟怎样处理；优先原LSTM对照，何时才需要小头/replay/更长前缀。局部模型只能提供条件裕量，不作在线真值。
4. 比较与N01边界：怎样分开行为、暴露、辅助信息和Student分布收益；N01只有预研/最小设计、未实施，D023强回弹重抓分工仍有效，任何接口/范围变化待Owner采纳。

建议的下一步是把上述四组问题形成一份小范围设计与未来功能操作路径，再按Owner后续要求推进。Pro的12门、±5–8°、0.2/0.5/1s、候选阈值和执行比例都是启动建议，不是获批样本、预算或硬验收门槛。GPU0/GPU1原合同与持久化等待保持不变。
